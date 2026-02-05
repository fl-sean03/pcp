#!/usr/bin/env python3
"""
Worker Supervisor - Manages background Claude Code workers for delegated tasks.

This script runs on the HOST system (not inside a container) and:
1. Polls the delegated_tasks table for pending tasks
2. Spawns Claude Code sessions to process them
3. Monitors task completion
4. Sends Discord notifications when tasks finish

Usage:
    # Run supervisor (polls every 30 seconds)
    python worker_supervisor.py

    # Run once (process one task then exit)
    python worker_supervisor.py --once

    # Check status
    python worker_supervisor.py --status
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
from datetime import datetime
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_delegation import (
    claim_next_task, update_task_status, complete_task,
    get_pending_count, mark_notification_sent,
    get_completed_tasks_needing_notification, get_task
)

# Configuration - detect container vs host environment
if os.path.exists("/workspace/CLAUDE.md"):
    # Inside container
    PCP_DIR = "/workspace"
else:
    # On host
    PCP_DIR = os.environ.get("PCP_DIR", "/workspace")

# Increase poll interval since we now have event-driven triggering
POLL_INTERVAL = int(os.environ.get("WORKER_POLL_INTERVAL", "300"))  # 5 minutes fallback
MAX_CONCURRENT = int(os.environ.get("WORKER_MAX_CONCURRENT", "1"))
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
PCP_DISCORD_CHANNEL = os.environ.get("PCP_DISCORD_CHANNEL", "")
PID_FILE = "/tmp/pcp_worker_supervisor.pid"

# Ensure log directory exists before setting up logging
LOG_DIR = f"{PCP_DIR}/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"{LOG_DIR}/worker_supervisor.log")
    ]
)
logger = logging.getLogger(__name__)

# Global state
running = True
active_workers = {}  # session_id -> subprocess
wake_event = False  # Set by SIGUSR1 to wake up immediately


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


def spawn_worker(task: dict) -> subprocess.Popen:
    """
    Spawn a Claude Code session to handle a task.

    Args:
        task: The task dict from database

    Returns:
        Popen subprocess object
    """
    task_id = task["id"]
    description = task["task_description"]
    context = json.loads(task["context"]) if task["context"] else {}

    # Build the prompt for the worker
    prompt = f"""You are a PCP Worker Agent processing task #{task_id}.

## Task Description
{description}

## Context
{json.dumps(context, indent=2) if context else "No additional context provided."}

## Instructions
1. Read /workspace/WORKER_CLAUDE.md for worker-specific instructions
2. Execute the task described above
3. When done, update the task status using task_delegation.py:
   - On success: complete_task({task_id}, result={{"summary": "...", ...}})
   - On failure: complete_task({task_id}, error="Error message")
4. DO NOT respond conversationally - just execute and report

## Important
- Work in /workspace/overleaf/projects for Overleaf tasks
- Use the existing PCP scripts in /workspace/scripts/
- Be thorough but efficient

Begin execution now."""

    # Detect environment and build appropriate command
    inside_container = os.path.exists("/workspace/CLAUDE.md")

    if inside_container:
        # Inside container - run claude directly
        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--dangerously-skip-permissions",
            "--max-turns", "50"
        ]
        cwd = "/workspace"
    else:
        # On host - run via docker exec
        cmd = [
            "docker", "exec", "-i", "pcp-agent",
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--dangerously-skip-permissions",
            "--max-turns", "50"
        ]
        cwd = None

    logger.info(f"Spawning worker for task #{task_id} (container: {inside_container})")

    # Start the subprocess
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd
    )

    return process


def process_worker_output(task_id: int, process: subprocess.Popen):
    """
    Wait for worker to finish and process its output.

    Args:
        task_id: The task ID being processed
        process: The subprocess object
    """
    try:
        stdout, stderr = process.communicate(timeout=600)  # 10 minute timeout

        if process.returncode == 0:
            # Try to parse result
            try:
                result = json.loads(stdout)
                complete_task(task_id, result={"output": result.get("result", stdout)})
                logger.info(f"Task #{task_id} completed successfully")
            except json.JSONDecodeError:
                complete_task(task_id, result={"output": stdout})
                logger.info(f"Task #{task_id} completed (non-JSON output)")
        else:
            error_msg = stderr or f"Process exited with code {process.returncode}"
            complete_task(task_id, error=error_msg)
            logger.error(f"Task #{task_id} failed: {error_msg}")

    except subprocess.TimeoutExpired:
        process.kill()
        complete_task(task_id, error="Task timed out after 10 minutes")
        logger.error(f"Task #{task_id} timed out")

    except Exception as e:
        complete_task(task_id, error=str(e))
        logger.exception(f"Error processing task #{task_id}: {e}")


def send_discord_notification(task: dict):
    """
    Send Discord notification for completed task.

    Uses Discord webhook if configured, otherwise logs.
    """
    channel_id = task.get("discord_channel_id")
    status = task.get("status")
    description = task.get("task_description", "Unknown task")[:100]
    result = task.get("result")
    error = task.get("error")

    if status == "completed":
        message = f"Task #{task['id']} completed!\n**{description}**"
        if result:
            try:
                result_data = json.loads(result)
                if "summary" in result_data:
                    message += f"\n\nSummary: {result_data['summary']}"
            except:
                pass
    else:
        message = f"Task #{task['id']} failed\n**{description}**\n\nError: {error or 'Unknown error'}"

    # Try webhook first
    if DISCORD_WEBHOOK_URL:
        try:
            import requests
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
            logger.info(f"Sent Discord notification for task #{task['id']}")
        except Exception as e:
            logger.warning(f"Failed to send webhook: {e}")
    else:
        # Log the notification for manual pickup
        logger.info(f"NOTIFICATION (channel {channel_id}): {message}")

    mark_notification_sent(task["id"])


def run_once():
    """Process one task and exit."""
    session_id = f"worker-{uuid.uuid4().hex[:8]}"

    task = claim_next_task(session_id)
    if not task:
        logger.info("No pending tasks")
        return False

    logger.info(f"Claimed task #{task['id']}: {task['task_description'][:50]}...")
    update_task_status(task["id"], "running")

    process = spawn_worker(task)
    process_worker_output(task["id"], process)

    # Send notification
    updated_task = get_task(task["id"])
    if updated_task and updated_task.get("discord_channel_id"):
        send_discord_notification(updated_task)

    return True


def run_supervisor():
    """Run the supervisor loop with event-driven wake-up support."""
    global running, wake_event

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGUSR1, wake_handler)

    # Write PID file so delegate_task() can signal us
    write_pid_file()

    logger.info(f"Worker supervisor started (poll interval: {POLL_INTERVAL}s, PID: {os.getpid()})")
    logger.info(f"Event-driven: send SIGUSR1 to wake immediately")

    try:
        while running:
            try:
                # Check for pending tasks
                pending = get_pending_count()
                if pending > 0 and len(active_workers) < MAX_CONCURRENT:
                    run_once()

                # Send any pending notifications
                for task in get_completed_tasks_needing_notification():
                    send_discord_notification(task)

                # Sleep with interruptible wait (wake_event checked after signal)
                wake_event = False
                sleep_remaining = POLL_INTERVAL
                while sleep_remaining > 0 and running and not wake_event:
                    time.sleep(min(1, sleep_remaining))  # Check every second
                    sleep_remaining -= 1

                if wake_event:
                    logger.info("Wake event triggered, processing immediately")

            except Exception as e:
                logger.exception(f"Supervisor error: {e}")
                time.sleep(5)  # Back off on error

    finally:
        remove_pid_file()
        logger.info("Worker supervisor stopped")


def show_status():
    """Show supervisor status."""
    pending = get_pending_count()
    print(f"Pending tasks: {pending}")
    print(f"Active workers: {len(active_workers)}")
    print(f"Max concurrent: {MAX_CONCURRENT}")
    print(f"Poll interval: {POLL_INTERVAL}s")


def main():
    parser = argparse.ArgumentParser(description="PCP Worker Supervisor")
    parser.add_argument("--once", action="store_true", help="Process one task and exit")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.once:
        success = run_once()
        sys.exit(0 if success else 1)
    else:
        run_supervisor()


if __name__ == "__main__":
    main()
