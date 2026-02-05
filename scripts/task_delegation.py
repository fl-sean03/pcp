#!/usr/bin/env python3
"""
Task Delegation Module - Queue-based background task execution.

IMPORTANT: For Discord interactions, use this module instead of Claude Code's
Task tool with run_in_background=true. The Task tool's background processes
die when the session ends, but tasks queued here persist and are processed
by pcp-supervisor (a systemd service).

Quick Start (recommended for most cases):
    from task_delegation import background_task

    # One line - queues task and returns acknowledgment text
    ack, task_id = background_task("Research Ground State outreach contacts")
    # ack = "Got it - I'll research Ground State outreach contacts. I'll message you when it's ready."
    # Now just respond with 'ack' to the user

Full Control:
    from task_delegation import delegate_task

    task_id = delegate_task(
        description="Research Ground State outreach contacts",
        context={"look_at": "recent conversations about Ground State"},
        discord_channel_id=os.environ.get("PCP_DISCORD_CHANNEL", ""),
        priority=3
    )

Task Chains:
    from task_delegation import create_task_chain

    task_ids = create_task_chain([
        {"description": "Extract text from PDF"},
        {"description": "Convert to LaTeX", "depends_on": [0]},
        {"description": "Push to Overleaf", "depends_on": [1]}
    ])
"""

import os
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

# Vault path detection
# Priority: Container path > PCP_DIR env > production fallback
# For dev testing from host, set PCP_DIR=/path/to/pcp/dev
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)):
    # Not in container, check host paths
    pcp_dir = os.environ.get("PCP_DIR", "")
    if pcp_dir and os.path.exists(f"{pcp_dir}/vault"):
        VAULT_PATH = f"{pcp_dir}/vault/vault.db"
    elif os.path.exists(os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault")):
        # Default to production on host
        VAULT_PATH = os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db")


def get_db_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# SIMPLE INTERFACE (recommended for most cases)
# =============================================================================

# Default Discord channel for PCP notifications
# Set via environment variable or detect based on environment
_is_dev = "pcp-dev" in VAULT_PATH or os.environ.get("PCP_ENV") == "dev"
DEFAULT_DISCORD_CHANNEL = os.environ.get(
    "PCP_DISCORD_CHANNEL_DEV" if _is_dev else "PCP_DISCORD_CHANNEL",
    ""  # Empty string if not configured
)


def background_task(
    description: str,
    context: Dict[str, Any] = None,
    priority: int = 5,
    discord_channel_id: str = None
) -> tuple:
    """
    Queue a background task and get an acknowledgment message.

    This is the simplest way to delegate work. One line does everything:
    - Queues the task for pcp-supervisor to pick up
    - Returns a ready-to-use acknowledgment for the user

    Args:
        description: What needs to be done (natural language)
        context: Optional dict with additional context
        priority: 1 (urgent) to 10 (low), default 5
        discord_channel_id: Channel for notification (defaults to PCP channel)

    Returns:
        Tuple of (acknowledgment_text, task_id)

    Example:
        ack, task_id = background_task("Research React state management libraries")
        # Now just respond with: ack
        # The supervisor will handle the rest and notify when done
    """
    channel = discord_channel_id or DEFAULT_DISCORD_CHANNEL

    task_id = delegate_task(
        description=description,
        context=context,
        discord_channel_id=channel,
        priority=priority,
        mode="legacy",  # Use supervisor, not broken subagent mode
        spawn_immediately=True
    )

    # Generate a natural acknowledgment
    # Truncate description for the ack if too long
    short_desc = description[:80] + "..." if len(description) > 80 else description
    ack = f"Got it - I'll {short_desc.lower()}. I'll message you when it's ready."

    return ack, task_id


# =============================================================================
# MAIN AGENT FUNCTIONS (for delegating tasks)
# =============================================================================

def delegate_task(
    description: str,
    context: Dict[str, Any] = None,
    discord_channel_id: str = None,
    discord_user_id: str = None,
    priority: int = 5,
    tags: List[str] = None,
    created_by: str = "main_agent",
    spawn_immediately: bool = True,
    mode: str = "auto",
    subagent: str = None,
    depends_on: List[int] = None,
    group_id: str = None
) -> int:
    """
    Delegate a task to background processing.

    Args:
        description: Natural language description of the task
        context: Dict with files, preferences, related_captures, etc.
        discord_channel_id: Channel to notify when complete
        discord_user_id: User to mention in notification
        priority: 1 (highest) to 10 (lowest), default 5
        tags: List of tags for filtering/grouping
        created_by: Who created this task (main_agent, user, etc.)
        spawn_immediately: If True, triggers execution immediately
        mode: Execution mode:
            - "auto": Use subagent if available, fallback to legacy
            - "subagent": Force native subagent (returns info for Claude to use)
            - "legacy": Force worker_supervisor.py pattern
        subagent: Specific subagent to use (e.g., "homework-transcriber")
            If not specified, auto-selects based on task description
        depends_on: List of task IDs this task depends on
        group_id: Identifier for grouping related tasks

    Returns:
        The task ID
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Auto-select subagent based on task description if not specified
    if mode in ("auto", "subagent") and subagent is None:
        subagent = _infer_subagent(description)

    cursor.execute("""
        INSERT INTO delegated_tasks (
            task_description, context, discord_channel_id, discord_user_id,
            priority, tags, created_by, status, created_at,
            mode, subagent, depends_on, group_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
    """, (
        description,
        json.dumps(context) if context else None,
        discord_channel_id,
        discord_user_id,
        priority,
        json.dumps(tags) if tags else None,
        created_by,
        datetime.now().isoformat(),
        mode,
        subagent,
        json.dumps(depends_on) if depends_on else None,
        group_id
    ))

    task_id = cursor.lastrowid
    conn.commit()

    # Update blocks field for dependent tasks
    if depends_on:
        for dep_id in depends_on:
            _add_blocked_by(conn, dep_id, task_id)

    conn.close()

    # Only trigger legacy worker if in legacy mode or auto with no subagent
    if spawn_immediately and mode == "legacy":
        _trigger_worker()
    elif spawn_immediately and mode == "auto" and subagent is None:
        _trigger_worker()
    # Note: subagent mode tasks are handled by Claude Code directly

    return task_id


def _infer_subagent(description: str) -> Optional[str]:
    """
    Infer the best subagent for a task based on its description.

    Returns:
        Subagent name or None if no specific subagent matches
    """
    desc_lower = description.lower()

    # Homework/LaTeX transcription
    if any(kw in desc_lower for kw in ["homework", "transcribe", "latex", "overleaf", "math"]):
        return "homework-transcriber"

    # Twitter/social media
    if any(kw in desc_lower for kw in ["twitter", "tweet", "timeline", "social", "x.com"]):
        return "twitter-curator"

    # Research/exploration
    if any(kw in desc_lower for kw in ["research", "explore", "investigate", "find out", "look into"]):
        return "research-agent"

    # Overleaf sync
    if any(kw in desc_lower for kw in ["overleaf sync", "push to overleaf", "pull from overleaf"]):
        return "overleaf-sync"

    # Default to general worker
    return "pcp-worker"


def _add_blocked_by(conn, blocking_task_id: int, blocked_task_id: int):
    """Add a task to the blocks list of another task."""
    cursor = conn.cursor()
    cursor.execute("SELECT blocks FROM delegated_tasks WHERE id = ?", (blocking_task_id,))
    row = cursor.fetchone()

    if row:
        current_blocks = json.loads(row[0]) if row[0] else []
        if blocked_task_id not in current_blocks:
            current_blocks.append(blocked_task_id)
            cursor.execute(
                "UPDATE delegated_tasks SET blocks = ? WHERE id = ?",
                (json.dumps(current_blocks), blocking_task_id)
            )
    conn.commit()


def _trigger_worker():
    """
    Trigger worker to process tasks immediately (event-driven).

    Uses multiple strategies in order of preference:
    1. Signal existing supervisor process (SIGUSR1)
    2. Spawn worker directly via subprocess
    """
    import subprocess
    import signal

    # Strategy 1: Signal existing supervisor
    pid_file = "/tmp/pcp_worker_supervisor.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
            # Send SIGUSR1 to wake up supervisor
            os.kill(pid, signal.SIGUSR1)
            return  # Success
        except (ValueError, OSError, ProcessLookupError):
            pass  # Supervisor not running or stale PID

    # Strategy 2: Spawn worker directly (fire-and-forget)
    # Check if we're inside a container
    if os.path.exists("/workspace/CLAUDE.md"):
        # Inside container - run worker_supervisor.py --once directly
        scripts_dir = "/workspace/scripts"
        subprocess.Popen(
            ["python3", f"{scripts_dir}/worker_supervisor.py", "--once"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )
    else:
        # On host - spawn via docker exec
        subprocess.Popen(
            ["docker", "exec", "-d", "pcp-agent",
             "python3", "/workspace/scripts/worker_supervisor.py", "--once"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a task by ID.

    Returns:
        Dict with task details or None if not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM delegated_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)


def list_tasks(
    status: str = None,
    limit: int = 20,
    include_completed: bool = False
) -> List[Dict[str, Any]]:
    """
    List tasks with optional filtering.

    Args:
        status: Filter by status (pending, claimed, running, completed, failed)
        limit: Max tasks to return
        include_completed: Include completed/failed tasks in results

    Returns:
        List of task dicts
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM delegated_tasks"
    params = []

    conditions = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    elif not include_completed:
        conditions.append("status NOT IN ('completed', 'failed')")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY priority ASC, created_at ASC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_pending_count() -> int:
    """Get count of pending tasks."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM delegated_tasks WHERE status = 'pending'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# =============================================================================
# WORKER AGENT FUNCTIONS (for processing tasks)
# =============================================================================

def claim_next_task(worker_session_id: str) -> Optional[Dict[str, Any]]:
    """
    Claim the next available task for processing.
    Uses atomic update to prevent race conditions.

    Args:
        worker_session_id: Unique identifier for this worker session

    Returns:
        The claimed task dict, or None if no tasks available
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Atomic claim: update the first pending task
    cursor.execute("""
        UPDATE delegated_tasks
        SET status = 'claimed',
            claimed_at = ?,
            worker_session_id = ?
        WHERE id = (
            SELECT id FROM delegated_tasks
            WHERE status = 'pending'
            ORDER BY priority ASC, created_at ASC
            LIMIT 1
        )
    """, (datetime.now().isoformat(), worker_session_id))

    if cursor.rowcount == 0:
        conn.close()
        return None

    # Get the claimed task
    cursor.execute(
        "SELECT * FROM delegated_tasks WHERE worker_session_id = ? AND status = 'claimed'",
        (worker_session_id,)
    )
    row = cursor.fetchone()
    conn.commit()
    conn.close()

    if row:
        return dict(row)
    return None


def update_task_status(task_id: int, status: str, error: str = None):
    """
    Update task status.

    Args:
        task_id: The task ID
        status: New status (claimed, running, completed, failed)
        error: Error message if status is 'failed'
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    timestamp_field = None
    if status == "running":
        timestamp_field = "started_at"
    elif status in ("completed", "failed"):
        timestamp_field = "completed_at"

    if timestamp_field:
        cursor.execute(f"""
            UPDATE delegated_tasks
            SET status = ?, {timestamp_field} = ?, error = ?
            WHERE id = ?
        """, (status, datetime.now().isoformat(), error, task_id))
    else:
        cursor.execute("""
            UPDATE delegated_tasks SET status = ?, error = ? WHERE id = ?
        """, (status, error, task_id))

    conn.commit()
    conn.close()


def complete_task(task_id: int, result: Dict[str, Any] = None, error: str = None):
    """
    Mark a task as completed (success or failure).

    Args:
        task_id: The task ID
        result: Success result dict (if successful)
        error: Error message (if failed)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    status = "completed" if not error else "failed"

    cursor.execute("""
        UPDATE delegated_tasks
        SET status = ?,
            completed_at = ?,
            result = ?,
            error = ?
        WHERE id = ?
    """, (
        status,
        datetime.now().isoformat(),
        json.dumps(result) if result else None,
        error,
        task_id
    ))

    conn.commit()
    conn.close()


def mark_notification_sent(task_id: int):
    """Mark that a notification was sent for this task."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE delegated_tasks SET notification_sent = 1 WHERE id = ?",
        (task_id,)
    )
    conn.commit()
    conn.close()


def get_completed_tasks_needing_notification() -> List[Dict[str, Any]]:
    """Get tasks that are completed but haven't been notified yet."""
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


# =============================================================================
# TASK CHAIN AND DEPENDENCY FUNCTIONS
# =============================================================================

def create_task_chain(
    tasks: List[Dict[str, Any]],
    group_id: str = None,
    discord_channel_id: str = None,
    mode: str = "auto"
) -> List[int]:
    """
    Create a chain of dependent tasks.

    Args:
        tasks: List of task dicts with:
            - description (required): Task description
            - depends_on (optional): List of indices (0-based) of tasks this depends on
            - context (optional): Additional context
            - priority (optional): Task priority
            - subagent (optional): Specific subagent to use
        group_id: Identifier for the group (auto-generated if not provided)
        discord_channel_id: Channel for notifications
        mode: Execution mode for all tasks

    Returns:
        List of created task IDs in order

    Example:
        create_task_chain([
            {"description": "Extract text from PDF"},
            {"description": "Convert to LaTeX", "depends_on": [0]},
            {"description": "Push to Overleaf", "depends_on": [1]}
        ])
    """
    if not group_id:
        group_id = f"chain-{uuid.uuid4().hex[:8]}"

    task_ids = []

    for i, task_def in enumerate(tasks):
        # Convert index-based depends_on to task IDs
        depends_on_ids = None
        if task_def.get("depends_on"):
            depends_on_ids = [task_ids[idx] for idx in task_def["depends_on"]]

        task_id = delegate_task(
            description=task_def["description"],
            context=task_def.get("context"),
            discord_channel_id=discord_channel_id,
            priority=task_def.get("priority", 5),
            mode=mode,
            subagent=task_def.get("subagent"),
            depends_on=depends_on_ids,
            group_id=group_id,
            spawn_immediately=False  # Don't spawn until chain is created
        )
        task_ids.append(task_id)

    # Now trigger execution of tasks with no dependencies
    ready_tasks = get_ready_tasks(group_id=group_id)
    if ready_tasks and mode == "legacy":
        _trigger_worker()

    return task_ids


def get_ready_tasks(group_id: str = None) -> List[Dict[str, Any]]:
    """
    Get tasks whose dependencies are all completed.

    Args:
        group_id: Filter by group (optional)

    Returns:
        List of tasks ready for execution
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT * FROM delegated_tasks
        WHERE status = 'pending'
    """
    params = []

    if group_id:
        query += " AND group_id = ?"
        params.append(group_id)

    query += " ORDER BY priority ASC, created_at ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    ready = []
    for row in rows:
        task = dict(row)
        depends_on = json.loads(task.get("depends_on") or "[]")

        if not depends_on:
            # No dependencies, ready to run
            ready.append(task)
        else:
            # Check if all dependencies are completed
            all_completed = all(
                _is_task_completed(dep_id) for dep_id in depends_on
            )
            if all_completed:
                ready.append(task)

    return ready


def _is_task_completed(task_id: int) -> bool:
    """Check if a task is completed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM delegated_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return row and row[0] == "completed"


def get_task_chain_status(group_id: str) -> Dict[str, Any]:
    """
    Get status of all tasks in a chain/group.

    Returns:
        Dict with:
            - group_id: The group identifier
            - total: Total number of tasks
            - pending: Number pending
            - running: Number running
            - completed: Number completed
            - failed: Number failed
            - tasks: List of task summaries
            - progress: Percentage complete
            - next_ready: Tasks ready to execute
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM delegated_tasks WHERE group_id = ? ORDER BY created_at",
        (group_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {"error": f"No tasks found for group {group_id}"}

    tasks = [dict(row) for row in rows]
    status_counts = {"pending": 0, "claimed": 0, "running": 0, "completed": 0, "failed": 0}

    for task in tasks:
        status = task.get("status", "pending")
        if status in status_counts:
            status_counts[status] += 1

    total = len(tasks)
    completed = status_counts["completed"]
    progress = (completed / total * 100) if total > 0 else 0

    return {
        "group_id": group_id,
        "total": total,
        **status_counts,
        "progress": round(progress, 1),
        "tasks": [
            {
                "id": t["id"],
                "description": t["task_description"][:50] + "..." if len(t["task_description"]) > 50 else t["task_description"],
                "status": t["status"],
                "depends_on": json.loads(t.get("depends_on") or "[]"),
            }
            for t in tasks
        ],
        "next_ready": [t["id"] for t in get_ready_tasks(group_id)]
    }


def process_chain_completion(task_id: int):
    """
    Process completion of a task in a chain, triggering dependent tasks.

    Call this after completing a task to check if blocked tasks can now run.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get the completed task
    cursor.execute("SELECT blocks, group_id, mode FROM delegated_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return

    blocks = json.loads(row[0]) if row[0] else []
    group_id = row[1]
    mode = row[2] or "auto"

    if blocks:
        # Check each blocked task
        ready = get_ready_tasks(group_id)
        if ready and mode == "legacy":
            _trigger_worker()


# =============================================================================
# SUBAGENT TRACKING FUNCTIONS
# =============================================================================

def record_subagent_execution(
    agent_id: str,
    agent_type: str,
    delegated_task_id: int = None,
    initial_prompt: str = None
) -> int:
    """
    Record a subagent execution for tracking and resumption.

    Args:
        agent_id: Claude Code's agentId
        agent_type: Type of subagent (pcp-worker, homework-transcriber, etc.)
        delegated_task_id: Link to delegated_tasks if applicable
        initial_prompt: The prompt sent to the subagent

    Returns:
        The execution record ID
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO subagent_executions (
            agent_id, agent_type, delegated_task_id, initial_prompt,
            status, started_at
        ) VALUES (?, ?, ?, ?, 'running', ?)
    """, (
        agent_id,
        agent_type,
        delegated_task_id,
        initial_prompt,
        datetime.now().isoformat()
    ))

    exec_id = cursor.lastrowid
    conn.commit()

    # Also update the delegated task with the subagent_id
    if delegated_task_id:
        cursor.execute(
            "UPDATE delegated_tasks SET subagent_id = ? WHERE id = ?",
            (agent_id, delegated_task_id)
        )
        conn.commit()

    conn.close()
    return exec_id


def complete_subagent_execution(
    agent_id: str,
    result_summary: str = None,
    status: str = "completed"
):
    """
    Mark a subagent execution as completed.

    Args:
        agent_id: The agent ID to update
        result_summary: Summary of what was accomplished
        status: Final status (completed, failed, paused)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE subagent_executions
        SET status = ?, result_summary = ?, completed_at = ?
        WHERE agent_id = ? AND status = 'running'
    """, (
        status,
        result_summary,
        datetime.now().isoformat(),
        agent_id
    ))

    conn.commit()
    conn.close()


def get_resumable_subagents(agent_type: str = None) -> List[Dict[str, Any]]:
    """
    Get subagent executions that can be resumed.

    Args:
        agent_type: Filter by agent type (optional)

    Returns:
        List of resumable execution records
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT * FROM subagent_executions
        WHERE can_resume = 1 AND status IN ('paused', 'running')
    """
    params = []

    if agent_type:
        query += " AND agent_type = ?"
        params.append(agent_type)

    query += " ORDER BY started_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def mark_subagent_resumed(agent_id: str):
    """Mark that a subagent was resumed, incrementing resume count."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE subagent_executions
        SET resume_count = resume_count + 1, status = 'running'
        WHERE agent_id = ?
    """, (agent_id,))

    conn.commit()
    conn.close()


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Task Delegation Management")
    subparsers = parser.add_subparsers(dest="command")

    # List tasks
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--all", action="store_true", help="Include completed")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--group", help="Filter by group ID")

    # Get task
    get_parser = subparsers.add_parser("get", help="Get task details")
    get_parser.add_argument("task_id", type=int)

    # Create task (delegate)
    create_parser = subparsers.add_parser("delegate", help="Delegate a task")
    create_parser.add_argument("description", help="Task description")
    create_parser.add_argument("--priority", type=int, default=5)
    create_parser.add_argument("--channel", help="Discord channel ID")
    create_parser.add_argument("--mode", choices=["auto", "subagent", "legacy"], default="auto")
    create_parser.add_argument("--subagent", help="Specific subagent to use")

    # Create task chain
    chain_parser = subparsers.add_parser("chain", help="Create a task chain")
    chain_parser.add_argument("tasks", nargs="+", help="Task descriptions (use 'depends:N' for dependencies)")
    chain_parser.add_argument("--channel", help="Discord channel ID")
    chain_parser.add_argument("--mode", choices=["auto", "subagent", "legacy"], default="auto")

    # Get chain status
    chain_status_parser = subparsers.add_parser("chain-status", help="Get task chain status")
    chain_status_parser.add_argument("group_id", help="Group ID of the chain")

    # Get ready tasks
    ready_parser = subparsers.add_parser("ready", help="List tasks ready to execute")
    ready_parser.add_argument("--group", help="Filter by group ID")

    # Subagent commands
    subagent_parser = subparsers.add_parser("subagents", help="List resumable subagents")
    subagent_parser.add_argument("--type", help="Filter by agent type")

    # Stats
    subparsers.add_parser("stats", help="Show task stats")

    # Backward compatibility alias
    create_alias = subparsers.add_parser("create", help="Alias for delegate")
    create_alias.add_argument("description", help="Task description")
    create_alias.add_argument("--priority", type=int, default=5)
    create_alias.add_argument("--channel", help="Discord channel ID")

    args = parser.parse_args()

    if args.command == "list":
        tasks = list_tasks(
            status=args.status,
            limit=args.limit,
            include_completed=args.all
        )
        for t in tasks:
            mode_info = f" [{t.get('mode', 'auto')}]" if t.get('mode') else ""
            subagent_info = f" -> {t.get('subagent')}" if t.get('subagent') else ""
            print(f"[{t['id']}] [{t['status']}]{mode_info}{subagent_info} {t['task_description'][:50]}...")

    elif args.command == "get":
        task = get_task(args.task_id)
        if task:
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"Task {args.task_id} not found")
            sys.exit(1)

    elif args.command in ("delegate", "create"):
        task_id = delegate_task(
            description=args.description,
            discord_channel_id=getattr(args, "channel", None),
            priority=args.priority,
            mode=getattr(args, "mode", "auto"),
            subagent=getattr(args, "subagent", None),
            created_by="cli"
        )
        task = get_task(task_id)
        print(f"Created task #{task_id}")
        if task.get("subagent"):
            print(f"  Subagent: {task['subagent']}")
        if task.get("mode"):
            print(f"  Mode: {task['mode']}")

    elif args.command == "chain":
        # Parse task descriptions with optional dependencies
        task_defs = []
        for i, desc in enumerate(args.tasks):
            task_def = {"description": desc}
            # Check for dependency syntax: "Task description depends:0,1"
            if " depends:" in desc:
                parts = desc.rsplit(" depends:", 1)
                task_def["description"] = parts[0]
                task_def["depends_on"] = [int(x) for x in parts[1].split(",")]
            task_defs.append(task_def)

        task_ids = create_task_chain(
            tasks=task_defs,
            discord_channel_id=args.channel,
            mode=args.mode
        )
        print(f"Created task chain with {len(task_ids)} tasks:")
        for i, tid in enumerate(task_ids):
            task = get_task(tid)
            deps = json.loads(task.get("depends_on") or "[]")
            dep_str = f" (depends on: {deps})" if deps else ""
            print(f"  [{tid}] {task['task_description'][:40]}...{dep_str}")
        print(f"Group ID: {get_task(task_ids[0]).get('group_id')}")

    elif args.command == "chain-status":
        status = get_task_chain_status(args.group_id)
        if "error" in status:
            print(status["error"])
            sys.exit(1)

        print(f"Chain: {status['group_id']}")
        print(f"Progress: {status['progress']}% ({status['completed']}/{status['total']} completed)")
        print(f"Status: pending={status['pending']}, running={status['running']}, completed={status['completed']}, failed={status['failed']}")
        print("\nTasks:")
        for t in status["tasks"]:
            deps = f" (deps: {t['depends_on']})" if t["depends_on"] else ""
            ready = " [READY]" if t["id"] in status["next_ready"] else ""
            print(f"  [{t['id']}] [{t['status']}] {t['description']}{deps}{ready}")

    elif args.command == "ready":
        tasks = get_ready_tasks(group_id=args.group)
        if not tasks:
            print("No tasks ready to execute")
        else:
            print(f"Tasks ready to execute ({len(tasks)}):")
            for t in tasks:
                print(f"  [{t['id']}] {t['task_description'][:50]}...")

    elif args.command == "subagents":
        subagents = get_resumable_subagents(agent_type=args.type)
        if not subagents:
            print("No resumable subagents")
        else:
            print(f"Resumable subagents ({len(subagents)}):")
            for s in subagents:
                print(f"  [{s['agent_id'][:8]}...] {s['agent_type']} - {s['status']} (resumed {s['resume_count']}x)")

    elif args.command == "stats":
        conn = get_db_connection()
        cursor = conn.cursor()

        print("=== Task Statistics ===")
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM delegated_tasks
            GROUP BY status
        """)
        print("\nBy Status:")
        for row in cursor.fetchall():
            print(f"  {row['status']}: {row['count']}")

        cursor.execute("""
            SELECT mode, COUNT(*) as count
            FROM delegated_tasks
            WHERE mode IS NOT NULL
            GROUP BY mode
        """)
        rows = cursor.fetchall()
        if rows:
            print("\nBy Mode:")
            for row in rows:
                print(f"  {row['mode']}: {row['count']}")

        cursor.execute("""
            SELECT subagent, COUNT(*) as count
            FROM delegated_tasks
            WHERE subagent IS NOT NULL
            GROUP BY subagent
        """)
        rows = cursor.fetchall()
        if rows:
            print("\nBy Subagent:")
            for row in rows:
                print(f"  {row['subagent']}: {row['count']}")

        # Subagent executions
        cursor.execute("SELECT COUNT(*) FROM subagent_executions")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"\nSubagent Executions: {count}")
            cursor.execute("""
                SELECT agent_type, status, COUNT(*) as count
                FROM subagent_executions
                GROUP BY agent_type, status
            """)
            for row in cursor.fetchall():
                print(f"  {row['agent_type']} ({row['status']}): {row['count']}")

        conn.close()

    else:
        parser.print_help()
