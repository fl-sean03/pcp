#!/usr/bin/env python3
"""
PCP Reminder System - Manages time-based reminders and deadline notifications.
Can send reminders via Discord webhook or other notification channels.
"""

import sqlite3
import json
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

VAULT_PATH = "/workspace/vault/vault.db"
CONFIG_PATH = "/workspace/.reminder_config.json"


def load_config() -> Dict:
    """Load reminder configuration."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {"discord_webhook": None, "notification_enabled": True}


def save_config(config: Dict):
    """Save reminder configuration."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def set_discord_webhook(webhook_url: str):
    """Configure Discord webhook for notifications."""
    config = load_config()
    config["discord_webhook"] = webhook_url
    save_config(config)
    print(f"Discord webhook configured.")


def check_due_reminders() -> List[Dict]:
    """Get all reminders that are due now."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    cursor.execute("""
        SELECT id, content, reminder_at, due_date, project_id
        FROM tasks
        WHERE status = 'pending'
        AND reminder_at IS NOT NULL
        AND reminder_at <= ?
        ORDER BY reminder_at ASC
    """, (now,))

    reminders = []
    for row in cursor.fetchall():
        reminders.append({
            "id": row[0],
            "content": row[1],
            "reminder_at": row[2],
            "due_date": row[3],
            "project_id": row[4]
        })

    conn.close()
    return reminders


def get_approaching_deadlines(hours: int = 24) -> List[Dict]:
    """Get tasks with deadlines approaching within N hours."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT id, content, due_date, project_id, priority
        FROM tasks
        WHERE status = 'pending'
        AND due_date >= ? AND due_date <= ?
        ORDER BY due_date ASC
    """, (now, future))

    deadlines = []
    for row in cursor.fetchall():
        deadlines.append({
            "id": row[0],
            "content": row[1],
            "due_date": row[2],
            "project_id": row[3],
            "priority": row[4]
        })

    conn.close()
    return deadlines


def get_overdue_tasks() -> List[Dict]:
    """Get tasks that are past their due date."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT id, content, due_date, project_id, priority
        FROM tasks
        WHERE status = 'pending'
        AND due_date < ?
        ORDER BY due_date ASC
    """, (today,))

    overdue = []
    for row in cursor.fetchall():
        overdue.append({
            "id": row[0],
            "content": row[1],
            "due_date": row[2],
            "project_id": row[3],
            "priority": row[4]
        })

    conn.close()
    return overdue


def schedule_reminder(task_id: int, reminder_time: str):
    """Set a reminder for a specific task."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tasks SET reminder_at = ?
        WHERE id = ?
    """, (reminder_time, task_id))

    conn.commit()
    conn.close()
    print(f"Reminder set for task {task_id} at {reminder_time}")


def clear_reminder(task_id: int):
    """Clear a reminder after it has been sent."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tasks SET reminder_at = NULL
        WHERE id = ?
    """, (task_id,))

    conn.commit()
    conn.close()


def snooze_reminder(task_id: int, hours: int = 1):
    """Snooze a reminder by N hours."""
    new_time = (datetime.now() + timedelta(hours=hours)).isoformat()
    schedule_reminder(task_id, new_time)
    print(f"Reminder snoozed for {hours} hour(s)")


def send_discord_notification(message: str) -> bool:
    """Send a notification via Discord webhook."""
    config = load_config()
    webhook_url = config.get("discord_webhook")

    if not webhook_url:
        print("Discord webhook not configured.")
        return False

    try:
        response = requests.post(webhook_url, json={"content": message})
        return response.status_code == 204
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")
        return False


def format_reminder_message(reminders: List[Dict], deadlines: List[Dict], overdue: List[Dict]) -> str:
    """Format all notifications into a single message."""
    lines = []

    if overdue:
        lines.append("**OVERDUE:**")
        for task in overdue[:5]:
            lines.append(f"  - {task['content'][:80]} (was due: {task['due_date']})")
        lines.append("")

    if reminders:
        lines.append("**Reminders:**")
        for r in reminders[:5]:
            lines.append(f"  - {r['content'][:80]}")
        lines.append("")

    if deadlines:
        lines.append("**Upcoming (24h):**")
        for d in deadlines[:5]:
            lines.append(f"  - {d['content'][:80]} (due: {d['due_date']})")

    return "\n".join(lines) if lines else None


def run_reminder_check(notify: bool = True) -> Dict[str, Any]:
    """
    Check all reminders and deadlines.
    Optionally send notifications.
    """
    reminders = check_due_reminders()
    deadlines = get_approaching_deadlines(24)
    overdue = get_overdue_tasks()

    result = {
        "checked_at": datetime.now().isoformat(),
        "due_reminders": len(reminders),
        "approaching_deadlines": len(deadlines),
        "overdue_tasks": len(overdue),
        "reminders": reminders,
        "deadlines": deadlines,
        "overdue": overdue
    }

    # Send notification if there's anything to report
    if notify and (reminders or deadlines or overdue):
        message = format_reminder_message(reminders, deadlines, overdue)
        if message:
            success = send_discord_notification(message)
            result["notification_sent"] = success

            # Clear sent reminders so they don't fire again
            if success:
                for r in reminders:
                    clear_reminder(r["id"])

    return result


def escalate_approaching_deadlines():
    """
    Check for deadlines and escalate priority if needed.
    Called periodically (e.g., every hour).
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Get tasks due within 24 hours that aren't high priority
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        UPDATE tasks
        SET priority = CASE
            WHEN priority IS NULL OR priority < 8 THEN 8
            ELSE priority
        END
        WHERE status = 'pending'
        AND due_date >= ? AND due_date <= ?
        AND (priority IS NULL OR priority < 8)
    """, (today, tomorrow))

    escalated = cursor.rowcount
    conn.commit()
    conn.close()

    if escalated > 0:
        print(f"Escalated {escalated} task(s) approaching deadline")

    return escalated


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("""PCP Reminder System

Usage:
    python reminders.py --check              Check and send due reminders
    python reminders.py --status             Show current reminder status
    python reminders.py --webhook <url>      Set Discord webhook URL
    python reminders.py --schedule <id> <time>  Set reminder for task
    python reminders.py --snooze <id> [hours]   Snooze a reminder
    python reminders.py --escalate           Escalate approaching deadlines
""")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--check":
        result = run_reminder_check(notify=True)
        print(f"Checked at: {result['checked_at']}")
        print(f"Due reminders: {result['due_reminders']}")
        print(f"Approaching deadlines: {result['approaching_deadlines']}")
        print(f"Overdue tasks: {result['overdue_tasks']}")
        if result.get("notification_sent"):
            print("Notification sent!")

    elif cmd == "--status":
        result = run_reminder_check(notify=False)
        print(json.dumps(result, indent=2))

    elif cmd == "--webhook":
        if len(sys.argv) < 3:
            print("Usage: --webhook <url>")
            sys.exit(1)
        set_discord_webhook(sys.argv[2])

    elif cmd == "--schedule":
        if len(sys.argv) < 4:
            print("Usage: --schedule <task_id> <datetime>")
            sys.exit(1)
        schedule_reminder(int(sys.argv[2]), sys.argv[3])

    elif cmd == "--snooze":
        if len(sys.argv) < 3:
            print("Usage: --snooze <task_id> [hours]")
            sys.exit(1)
        hours = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        snooze_reminder(int(sys.argv[2]), hours)

    elif cmd == "--escalate":
        escalated = escalate_approaching_deadlines()
        print(f"Escalated {escalated} tasks")

    else:
        print(f"Unknown command: {cmd}")
