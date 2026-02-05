#!/usr/bin/env python3
"""
Discord Notification Utility - Send messages to Discord via webhook.

Usage:
    from discord_notify import notify, notify_task_complete

    # Simple notification
    notify("Task completed successfully!")

    # Task completion with details
    notify_task_complete(
        task_id=42,
        result="Created TIM workspace at /workspace/tim-roadmap",
        success=True
    )

CLI:
    python discord_notify.py "Your message here"
    python discord_notify.py --task-complete 42 "Result message"
"""

import json
import os
import sys
import urllib.request
from typing import Optional

# PCP Discord webhook - set via DISCORD_WEBHOOK_URL environment variable
DEFAULT_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")


def notify(message: str, webhook_url: str = None) -> bool:
    """Send a message to Discord.

    Args:
        message: The message to send
        webhook_url: Optional webhook URL (uses PCP default if not specified)

    Returns:
        True if successful, False otherwise
    """
    webhook = webhook_url or DEFAULT_WEBHOOK
    if not webhook:
        print("WARNING: DISCORD_WEBHOOK_URL not set, skipping notification", file=sys.stderr)
        return False

    payload = json.dumps({"content": message}).encode('utf-8')
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "PCP-Bot/1.0"
        }
    )

    try:
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"Discord notification failed: {e}", file=sys.stderr)
        return False


def notify_with_webhook(message: str, webhook_url: str) -> bool:
    """Send a message to Discord using a specific webhook.

    This is an alias for notify() with explicit webhook requirement.
    Used by the orchestrator for explicit webhook configuration.

    Args:
        message: The message to send
        webhook_url: The webhook URL to use

    Returns:
        True if successful, False otherwise
    """
    return notify(message, webhook_url)


def notify_task_complete(
    task_id: int,
    result: str,
    success: bool = True,
    webhook_url: str = None
) -> bool:
    """Send task completion notification to Discord.

    Args:
        task_id: The task ID that completed
        result: Description of the result
        success: Whether the task succeeded
        webhook_url: Optional webhook URL

    Returns:
        True if successful
    """
    icon = "✅" if success else "❌"
    status = "Complete" if success else "Failed"

    message = f"**Task {status}** {icon}\n\nTask #{task_id}: {result}"
    return notify(message, webhook_url)


def notify_progress(
    task_description: str,
    progress: str,
    webhook_url: str = None
) -> bool:
    """Send progress update to Discord.

    Args:
        task_description: What task is running
        progress: Current progress/status
        webhook_url: Optional webhook URL

    Returns:
        True if successful
    """
    message = f"⏳ **Working on:** {task_description}\n\n{progress}"
    return notify(message, webhook_url)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send Discord notifications")
    parser.add_argument("message", nargs="?", help="Message to send")
    parser.add_argument("--task-complete", "-t", type=int, help="Task ID for completion notification")
    parser.add_argument("--failed", "-f", action="store_true", help="Mark task as failed")
    parser.add_argument("--webhook", "-w", help="Custom webhook URL")

    args = parser.parse_args()

    if args.task_complete and args.message:
        success = notify_task_complete(
            args.task_complete,
            args.message,
            success=not args.failed,
            webhook_url=args.webhook
        )
    elif args.message:
        success = notify(args.message, args.webhook)
    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0 if success else 1)
