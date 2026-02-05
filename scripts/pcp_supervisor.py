#!/usr/bin/env python3
"""
PCP Supervisor - Reliable background task execution for PCP.

This is the core background task processor for PCP. It runs on the HOST machine
(not inside a container) and processes tasks from the delegated_tasks queue.

Key design decisions:
1. Runs independently of any Claude session (survives parent exit)
2. Uses SQLite as a reliable task queue
3. Posts results to Discord via webhook
4. Managed by systemd for automatic restart

Usage:
    # Run supervisor (production mode)
    python pcp_supervisor.py

    # Process one task and exit (testing)
    python pcp_supervisor.py --once

    # Show status
    python pcp_supervisor.py --status

    # Dry run (show what would be processed)
    python pcp_supervisor.py --dry-run
"""

import os
import sys
import json
import time
import uuid
import signal
import argparse
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configuration - detect container vs host environment
if os.path.exists("/workspace/CLAUDE.md"):
    # Inside container
    PCP_DIR = "/workspace"
    CONTAINER_NAME = None  # Running directly
else:
    # On host
    PCP_DIR = os.environ.get("PCP_DIR", os.environ.get("PCP_DIR", "/workspace"))
    CONTAINER_NAME = "pcp-agent"

# Configuration
POLL_INTERVAL = int(os.environ.get("PCP_POLL_INTERVAL", "30"))
MAX_CONCURRENT = int(os.environ.get("PCP_MAX_CONCURRENT", "1"))
WORKER_TIMEOUT = int(os.environ.get("PCP_WORKER_TIMEOUT", "600"))  # 10 minutes
STALE_CLAIM_TIMEOUT = int(os.environ.get("PCP_STALE_CLAIM_TIMEOUT", "600"))  # 10 min

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

TWITTER_WEBHOOK_URL = os.environ.get(
    "TWITTER_WEBHOOK_URL",
    "http://localhost:8787/webhook/task-complete"
)

PID_FILE = "/tmp/pcp_supervisor.pid"
LOG_DIR = f"{PCP_DIR}/logs"
VAULT_PATH = f"{PCP_DIR}/vault/vault.db"

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"{LOG_DIR}/supervisor.log")
    ]
)
logger = logging.getLogger(__name__)

# Global state
running = True
wake_event = False
active_workers: Dict[int, subprocess.Popen] = {}


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False


def wake_handler(signum, frame):
    """Handle SIGUSR1 - wake up immediately to process tasks."""
    global wake_event
    logger.info("Received SIGUSR1, waking up to check for tasks")
    wake_event = True


def write_pid_file():
    """Write PID to file for signal-based communication."""
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"Wrote PID {os.getpid()} to {PID_FILE}")
    except IOError as e:
        logger.warning(f"Failed to write PID file: {e}")


def remove_pid_file():
    """Remove PID file on shutdown."""
    try:
        if os.path.exists(PID_FILE):
            os.unlink(PID_FILE)
    except IOError:
        pass


# ==============================================================================
# Database Operations
# ==============================================================================

def get_db_connection():
    """Get database connection."""
    import sqlite3
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    """Ensure delegated_tasks table exists with all required columns."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # The table is managed by schema_v2.py - just verify it exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='delegated_tasks'
    """)

    if not cursor.fetchone():
        # Create minimal schema if table doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delegated_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_description TEXT NOT NULL,
                context TEXT,
                status TEXT DEFAULT 'pending',
                worker_session_id TEXT,
                claimed_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT,
                discord_channel_id TEXT,
                discord_user_id TEXT,
                notification_sent INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 5,
                tags TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                depends_on TEXT,
                blocks TEXT,
                group_id TEXT,
                mode TEXT DEFAULT 'auto',
                subagent TEXT
            )
        """)
        conn.commit()

    conn.close()


def get_pending_count() -> int:
    """Get count of pending tasks."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM delegated_tasks WHERE status = 'pending'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def claim_next_task(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Claim the next pending task atomically.

    Returns task dict or None if no tasks available.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # First, reset any stale claimed tasks
    stale_cutoff = (datetime.now() - timedelta(seconds=STALE_CLAIM_TIMEOUT)).isoformat()
    cursor.execute("""
        UPDATE delegated_tasks
        SET status = 'pending', worker_session_id = NULL, claimed_at = NULL
        WHERE status = 'claimed' AND claimed_at < ?
    """, (stale_cutoff,))

    if cursor.rowcount > 0:
        logger.warning(f"Reset {cursor.rowcount} stale claimed tasks")

    # Find and claim next task (ordered by priority then creation time)
    cursor.execute("""
        SELECT * FROM delegated_tasks
        WHERE status = 'pending'
        AND (depends_on IS NULL OR depends_on = '[]' OR depends_on = '')
        ORDER BY priority ASC, created_at ASC
        LIMIT 1
    """)

    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    task = dict(row)

    # Claim it
    cursor.execute("""
        UPDATE delegated_tasks
        SET status = 'claimed', worker_session_id = ?, claimed_at = ?
        WHERE id = ? AND status = 'pending'
    """, (session_id, now, task['id']))

    if cursor.rowcount == 0:
        # Someone else claimed it
        conn.close()
        return None

    conn.commit()
    conn.close()

    return task


def update_task_status(task_id: int, status: str):
    """Update task status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    if status == 'running':
        cursor.execute("""
            UPDATE delegated_tasks
            SET status = ?, started_at = ?
            WHERE id = ?
        """, (status, now, task_id))
    else:
        cursor.execute("""
            UPDATE delegated_tasks
            SET status = ?
            WHERE id = ?
        """, (status, task_id))

    conn.commit()
    conn.close()


def complete_task(task_id: int, result: Dict = None, error: str = None):
    """Mark task as completed or failed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    if error:
        status = 'failed'
        cursor.execute("""
            UPDATE delegated_tasks
            SET status = ?, error = ?, completed_at = ?
            WHERE id = ?
        """, (status, error, now, task_id))
    else:
        status = 'completed'
        cursor.execute("""
            UPDATE delegated_tasks
            SET status = ?, result = ?, completed_at = ?
            WHERE id = ?
        """, (status, json.dumps(result) if result else None, now, task_id))

    conn.commit()
    conn.close()


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Get task by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM delegated_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_notification_sent(task_id: int):
    """Mark that Discord notification was sent."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE delegated_tasks SET notification_sent = 1 WHERE id = ?
    """, (task_id,))
    conn.commit()
    conn.close()


def get_tasks_needing_notification() -> List[Dict]:
    """Get completed tasks that need Discord notification."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM delegated_tasks
        WHERE status IN ('completed', 'failed')
        AND notification_sent = 0
        AND discord_channel_id IS NOT NULL
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stats() -> Dict[str, Any]:
    """Get task statistics."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Count by status
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM delegated_tasks
        GROUP BY status
    """)
    by_status = {row['status']: row['count'] for row in cursor.fetchall()}

    # Recent completions
    yesterday = (datetime.now() - timedelta(hours=24)).isoformat()
    cursor.execute("""
        SELECT COUNT(*) FROM delegated_tasks
        WHERE status = 'completed' AND completed_at > ?
    """, (yesterday,))
    completed_24h = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM delegated_tasks
        WHERE status = 'failed' AND completed_at > ?
    """, (yesterday,))
    failed_24h = cursor.fetchone()[0]

    conn.close()

    return {
        'pending': by_status.get('pending', 0),
        'claimed': by_status.get('claimed', 0),
        'running': by_status.get('running', 0),
        'completed': by_status.get('completed', 0),
        'failed': by_status.get('failed', 0),
        'completed_24h': completed_24h,
        'failed_24h': failed_24h
    }


# ==============================================================================
# Worker Management
# ==============================================================================

def build_worker_prompt(task: Dict) -> str:
    """Build the prompt for a worker session."""
    task_id = task['id']
    description = task['task_description']
    context = json.loads(task['context']) if task.get('context') else {}

    return f"""You are a PCP Background Worker processing task #{task_id}.

## Task Description
{description}

## Context
{json.dumps(context, indent=2) if context else "No additional context."}

## Instructions
1. Execute the task described above thoroughly
2. Use all available PCP tools in /workspace/scripts/
3. For browser tasks, use the Playwright MCP tools
4. When complete, post results to Discord:
   ```python
   from discord_notify import notify
   notify("Task #{task_id} complete: [your summary here]")
   ```
5. Update task status:
   ```python
   from task_delegation import complete_task
   complete_task({task_id}, result={{"summary": "...", "details": ...}})
   ```
6. On failure:
   ```python
   from task_delegation import complete_task
   complete_task({task_id}, error="Description of what failed")
   ```

## File Paths
- /workspace/ = PCP's own code and scripts (DO NOT save project output here)
- /hostworkspace/ = the user's full workspace (~/Workspace on host) - CREATE project directories here
- /hosthome/ = the user's home directory (read-only)

When creating research, project files, or any output:
- Save to /hostworkspace/<project-name>/ (e.g., /hostworkspace/autonomous-agents/)
- NEVER save project output under /workspace/ - that's PCP internal code only
- PCP tools are at /workspace/scripts/ (read from there, don't write project files there)

## Important
- Be thorough but efficient
- Always post results to Discord
- Always update task status

Begin execution now."""


def spawn_worker(task: Dict) -> subprocess.Popen:
    """
    Spawn a Claude Code session to process a task.

    Returns Popen subprocess object.
    """
    task_id = task['id']
    prompt = build_worker_prompt(task)

    if CONTAINER_NAME:
        # Running on host - execute via docker
        cmd = [
            "docker", "exec", "-i", CONTAINER_NAME,
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--dangerously-skip-permissions",
            "--max-turns", "50"
        ]
        cwd = None
    else:
        # Running inside container
        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--dangerously-skip-permissions",
            "--max-turns", "50"
        ]
        cwd = "/workspace"

    logger.info(f"Spawning worker for task #{task_id}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd
    )

    return process


def process_worker_output(task_id: int, process: subprocess.Popen):
    """Wait for worker to finish and process its output."""
    try:
        stdout, stderr = process.communicate(timeout=WORKER_TIMEOUT)

        if process.returncode == 0:
            try:
                result = json.loads(stdout)
                # Check if worker already called complete_task
                task = get_task(task_id)
                if task and task['status'] not in ('completed', 'failed'):
                    complete_task(task_id, result={"output": result.get("result", stdout)})
                logger.info(f"Task #{task_id} completed successfully")
            except json.JSONDecodeError:
                task = get_task(task_id)
                if task and task['status'] not in ('completed', 'failed'):
                    complete_task(task_id, result={"output": stdout})
                logger.info(f"Task #{task_id} completed (non-JSON output)")
        else:
            error_msg = stderr or f"Process exited with code {process.returncode}"
            task = get_task(task_id)
            if task and task['status'] not in ('completed', 'failed'):
                complete_task(task_id, error=error_msg)
            logger.error(f"Task #{task_id} failed: {error_msg}")

    except subprocess.TimeoutExpired:
        process.kill()
        complete_task(task_id, error=f"Task timed out after {WORKER_TIMEOUT}s")
        logger.error(f"Task #{task_id} timed out")

    except Exception as e:
        complete_task(task_id, error=str(e))
        logger.exception(f"Error processing task #{task_id}: {e}")


# ==============================================================================
# Discord Notifications
# ==============================================================================

def send_discord_notification(task: Dict):
    """Send Discord notification for completed task."""
    status = task.get('status')
    description = task.get('task_description', 'Unknown task')[:100]
    result = task.get('result')
    error = task.get('error')

    if status == 'completed':
        message = f"**Task #{task['id']} completed**\n{description}"
        if result:
            try:
                result_data = json.loads(result)
                if 'summary' in result_data:
                    message += f"\n\n{result_data['summary']}"
                elif 'output' in result_data:
                    output = str(result_data['output'])[:500]
                    message += f"\n\n{output}"
            except:
                pass
    else:
        message = f"**Task #{task['id']} failed**\n{description}\n\nError: {error or 'Unknown error'}"

    if DISCORD_WEBHOOK_URL:
        try:
            import requests
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json={"content": message[:2000]},  # Discord limit
                timeout=10
            )
            if response.status_code == 204:
                logger.info(f"Sent Discord notification for task #{task['id']}")
            else:
                logger.warning(f"Discord webhook returned {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to send webhook: {e}")
    else:
        logger.info(f"NOTIFICATION: {message}")

    mark_notification_sent(task['id'])


def send_twitter_notification(task: Dict):
    """Send task result to Twitter adapter via webhook for DM delivery."""
    context = json.loads(task['context']) if task.get('context') else {}
    user_handle = context.get('twitter_user_handle', '')
    description = task.get('task_description', 'Unknown task')[:200]
    result = task.get('result')
    error = task.get('error')

    if task['status'] == 'completed':
        summary = ''
        if result:
            try:
                result_data = json.loads(result)
                summary = result_data.get('summary', '')
                if not summary:
                    output = result_data.get('output', '')
                    if isinstance(output, str):
                        summary = output
                    elif isinstance(output, dict):
                        summary = output.get('result', str(output))
                    else:
                        summary = str(output)
            except (json.JSONDecodeError, TypeError):
                summary = str(result)[:1000]
        if not summary:
            summary = f"Task completed: {description}"
    else:
        summary = f"Task failed: {description}\n\nError: {error or 'Unknown error'}"

    try:
        import requests
        response = requests.post(
            TWITTER_WEBHOOK_URL,
            json={
                'task_id': task['id'],
                'result': summary,
                'summary': summary[:2000],
                'user_handle': user_handle,
                'status': task['status']
            },
            timeout=10
        )
        if response.status_code == 200:
            logger.info(f"Sent Twitter DM notification for task #{task['id']} to {user_handle}")
            mark_notification_sent(task['id'])
        else:
            logger.warning(f"Twitter webhook returned {response.status_code}: {response.text}")
    except Exception as e:
        logger.warning(f"Failed to send Twitter webhook for task #{task['id']}: {e}")


def get_tasks_needing_twitter_notification() -> List[Dict]:
    """Get completed tasks that need Twitter DM delivery."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM delegated_tasks
        WHERE status IN ('completed', 'failed')
        AND notification_sent = 0
        AND context LIKE '%twitter_dm%'
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def process_notifications():
    """Send any pending notifications (Discord and Twitter)."""
    # Twitter DM notifications (push via webhook)
    twitter_tasks = get_tasks_needing_twitter_notification()
    for task in twitter_tasks:
        send_twitter_notification(task)

    # Discord notifications (standard webhook)
    tasks = get_tasks_needing_notification()
    for task in tasks:
        send_discord_notification(task)


# ==============================================================================
# Main Loop
# ==============================================================================

def run_once() -> bool:
    """Process one task and exit. Returns True if a task was processed."""
    session_id = f"worker-{uuid.uuid4().hex[:8]}"

    task = claim_next_task(session_id)
    if not task:
        logger.info("No pending tasks")
        return False

    logger.info(f"Claimed task #{task['id']}: {task['task_description'][:50]}...")
    update_task_status(task['id'], 'running')

    process = spawn_worker(task)
    process_worker_output(task['id'], process)

    # Send notification based on delivery channel
    updated_task = get_task(task['id'])
    if updated_task:
        context = json.loads(updated_task['context']) if updated_task.get('context') else {}
        if context.get('delivery_channel') == 'twitter_dm':
            send_twitter_notification(updated_task)
        if updated_task.get('discord_channel_id'):
            send_discord_notification(updated_task)

    return True


def run_supervisor():
    """Run the continuous supervisor loop."""
    global running, wake_event

    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGUSR1, wake_handler)

    write_pid_file()
    ensure_schema()

    logger.info(f"PCP Supervisor started (PID: {os.getpid()})")
    logger.info(f"Poll interval: {POLL_INTERVAL}s, Worker timeout: {WORKER_TIMEOUT}s")
    logger.info(f"Container: {CONTAINER_NAME or 'running directly'}")

    session_id = f"supervisor-{uuid.uuid4().hex[:8]}"

    try:
        while running:
            # Check for pending tasks
            pending = get_pending_count()
            if pending > 0:
                logger.info(f"Found {pending} pending task(s)")

                # Process one task at a time (for now)
                task = claim_next_task(session_id)
                if task:
                    logger.info(f"Processing task #{task['id']}: {task['task_description'][:50]}...")
                    update_task_status(task['id'], 'running')

                    process = spawn_worker(task)
                    process_worker_output(task['id'], process)

                    # Notification based on delivery channel
                    updated_task = get_task(task['id'])
                    if updated_task:
                        context = json.loads(updated_task['context']) if updated_task.get('context') else {}
                        if context.get('delivery_channel') == 'twitter_dm':
                            send_twitter_notification(updated_task)
                        if updated_task.get('discord_channel_id'):
                            send_discord_notification(updated_task)

            # Process any pending notifications
            process_notifications()

            # Wait for next poll (or wake signal)
            wake_event = False
            for _ in range(POLL_INTERVAL):
                if not running or wake_event:
                    break
                time.sleep(1)

    finally:
        remove_pid_file()
        logger.info("PCP Supervisor stopped")


def show_status():
    """Show supervisor and task status."""
    ensure_schema()
    stats = get_stats()

    print("PCP Background Task Status")
    print("=" * 40)
    print(f"Pending:   {stats['pending']}")
    print(f"Claimed:   {stats['claimed']}")
    print(f"Running:   {stats['running']}")
    print(f"Completed: {stats['completed']} ({stats['completed_24h']} last 24h)")
    print(f"Failed:    {stats['failed']} ({stats['failed_24h']} last 24h)")

    # Check if supervisor is running
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pid = f.read().strip()
        try:
            os.kill(int(pid), 0)
            print(f"\nSupervisor: Running (PID {pid})")
        except:
            print(f"\nSupervisor: Not running (stale PID file)")
    else:
        print("\nSupervisor: Not running")


def main():
    parser = argparse.ArgumentParser(description="PCP Background Task Supervisor")
    parser.add_argument("--once", action="store_true",
                       help="Process one task and exit")
    parser.add_argument("--status", action="store_true",
                       help="Show status and exit")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be processed without executing")

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.dry_run:
        ensure_schema()
        pending = get_pending_count()
        print(f"Would process {pending} pending task(s)")
        if pending > 0:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, task_description, priority
                FROM delegated_tasks
                WHERE status = 'pending'
                ORDER BY priority ASC, created_at ASC
                LIMIT 5
            """)
            for row in cursor.fetchall():
                print(f"  #{row['id']} (priority {row['priority']}): {row['task_description'][:60]}...")
            conn.close()
    elif args.once:
        ensure_schema()
        run_once()
    else:
        run_supervisor()


if __name__ == "__main__":
    main()
