#!/usr/bin/env python3
"""
PCP Scheduler - Manages scheduled tasks for PCP.
Can be run as a daemon or from cron.

Scheduled tasks:
- Daily brief at 8 AM
- Reminder checks every hour
- Pattern analysis daily
- OneDrive sync every 4 hours (when configured)
- Email sync every 2 hours (when configured)
- EOD digest at 6 PM
- Weekly summary on Mondays at 9 AM
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional

WORKSPACE = "/workspace"
CONFIG_PATH = f"{WORKSPACE}/.scheduler_config.json"
LOG_FILE = f"{WORKSPACE}/.agent/scheduler.log"


def log(message: str):
    """Log a message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    # Also write to file
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")


def load_config() -> Dict:
    """Load scheduler configuration."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {
        "daily_brief_hour": 8,
        "reminder_interval_minutes": 60,
        "pattern_analysis_hour": 9,
        "onedrive_sync_interval_hours": 4,
        "email_sync_interval_hours": 2,
        "eod_digest_hour": 18,
        "weekly_summary_day": 0,  # 0 = Monday
        "weekly_summary_hour": 9,
        "enabled": True
    }


def save_config(config: Dict):
    """Save scheduler configuration."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def run_daily_brief():
    """Run the daily brief generation."""
    log("Running daily brief...")
    try:
        result = subprocess.run(
            ["python3", f"{WORKSPACE}/scripts/brief.py"],
            capture_output=True, text=True, timeout=120
        )
        log(f"Daily brief completed. Output length: {len(result.stdout)}")
        return result.stdout
    except Exception as e:
        log(f"Daily brief failed: {e}")
        return None


def run_reminder_check():
    """Check and process reminders."""
    log("Running reminder check...")
    try:
        result = subprocess.run(
            ["python3", f"{WORKSPACE}/scripts/reminders.py", "--check"],
            capture_output=True, text=True, timeout=60
        )
        log(f"Reminder check completed")
        return result.stdout
    except Exception as e:
        log(f"Reminder check failed: {e}")
        return None


def run_pattern_analysis():
    """Run pattern analysis."""
    log("Running pattern analysis...")
    try:
        result = subprocess.run(
            ["python3", f"{WORKSPACE}/scripts/patterns.py"],
            capture_output=True, text=True, timeout=120
        )
        log(f"Pattern analysis completed")
        return result.stdout
    except Exception as e:
        log(f"Pattern analysis failed: {e}")
        return None


def run_onedrive_sync():
    """Sync OneDrive watched folders."""
    log("Running OneDrive sync...")
    try:
        result = subprocess.run(
            ["python3", f"{WORKSPACE}/scripts/onedrive.py", "--sync"],
            capture_output=True, text=True, timeout=300
        )
        log(f"OneDrive sync completed")
        return result.stdout
    except Exception as e:
        log(f"OneDrive sync failed: {e}")
        return None


def run_escalation():
    """Escalate approaching deadlines."""
    log("Running deadline escalation...")
    try:
        result = subprocess.run(
            ["python3", f"{WORKSPACE}/scripts/reminders.py", "--escalate"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except Exception as e:
        log(f"Escalation failed: {e}")
        return None


def run_email_sync():
    """Sync emails from Outlook via Microsoft Graph."""
    log("Running email sync...")
    try:
        result = subprocess.run(
            ["python3", f"{WORKSPACE}/scripts/email_processor.py", "fetch"],
            capture_output=True, text=True, timeout=300
        )
        log(f"Email sync completed")
        return result.stdout
    except Exception as e:
        log(f"Email sync failed: {e}")
        return None


def run_eod_digest():
    """Generate end-of-day digest."""
    log("Running EOD digest...")
    try:
        result = subprocess.run(
            ["python3", f"{WORKSPACE}/scripts/brief.py", "--eod"],
            capture_output=True, text=True, timeout=120
        )
        log(f"EOD digest completed. Output length: {len(result.stdout)}")
        return result.stdout
    except Exception as e:
        log(f"EOD digest failed: {e}")
        return None


def run_weekly_summary():
    """Generate weekly summary."""
    log("Running weekly summary...")
    try:
        result = subprocess.run(
            ["python3", f"{WORKSPACE}/scripts/brief.py", "--weekly"],
            capture_output=True, text=True, timeout=180
        )
        log(f"Weekly summary completed. Output length: {len(result.stdout)}")
        return result.stdout
    except Exception as e:
        log(f"Weekly summary failed: {e}")
        return None


class Scheduler:
    """Simple scheduler for PCP tasks."""

    def __init__(self):
        self.config = load_config()
        self.last_brief = None
        self.last_reminder = None
        self.last_pattern = None
        self.last_sync = None
        self.last_email_sync = None
        self.last_eod = None
        self.last_weekly = None

    def should_run_brief(self) -> bool:
        """Check if daily brief should run."""
        now = datetime.now()
        brief_hour = self.config.get("daily_brief_hour", 8)

        if now.hour == brief_hour:
            if self.last_brief is None or self.last_brief.date() < now.date():
                return True
        return False

    def should_run_reminder(self) -> bool:
        """Check if reminder check should run."""
        now = datetime.now()
        interval = self.config.get("reminder_interval_minutes", 60)

        if self.last_reminder is None:
            return True

        if (now - self.last_reminder).total_seconds() >= interval * 60:
            return True
        return False

    def should_run_pattern(self) -> bool:
        """Check if pattern analysis should run."""
        now = datetime.now()
        pattern_hour = self.config.get("pattern_analysis_hour", 9)

        if now.hour == pattern_hour:
            if self.last_pattern is None or self.last_pattern.date() < now.date():
                return True
        return False

    def should_run_sync(self) -> bool:
        """Check if OneDrive sync should run."""
        now = datetime.now()
        interval = self.config.get("onedrive_sync_interval_hours", 4)

        if self.last_sync is None:
            return True

        if (now - self.last_sync).total_seconds() >= interval * 3600:
            return True
        return False

    def should_run_email_sync(self) -> bool:
        """Check if email sync should run."""
        now = datetime.now()
        interval = self.config.get("email_sync_interval_hours", 2)

        if self.last_email_sync is None:
            return True

        if (now - self.last_email_sync).total_seconds() >= interval * 3600:
            return True
        return False

    def should_run_eod(self) -> bool:
        """Check if EOD digest should run."""
        now = datetime.now()
        eod_hour = self.config.get("eod_digest_hour", 18)

        if now.hour == eod_hour:
            if self.last_eod is None or self.last_eod.date() < now.date():
                return True
        return False

    def should_run_weekly(self) -> bool:
        """Check if weekly summary should run."""
        now = datetime.now()
        weekly_day = self.config.get("weekly_summary_day", 0)  # 0 = Monday
        weekly_hour = self.config.get("weekly_summary_hour", 9)

        # Only run on the specified day at the specified hour
        if now.weekday() == weekly_day and now.hour == weekly_hour:
            # Check if we haven't run this week
            if self.last_weekly is None:
                return True
            # Check if last run was before this week's day
            days_since = (now - self.last_weekly).days
            if days_since >= 7:
                return True
        return False

    def run_cycle(self):
        """Run one scheduling cycle."""
        now = datetime.now()

        if self.should_run_brief():
            run_daily_brief()
            self.last_brief = now

        if self.should_run_reminder():
            run_reminder_check()
            run_escalation()
            self.last_reminder = now

        if self.should_run_pattern():
            run_pattern_analysis()
            self.last_pattern = now

        if self.should_run_sync():
            run_onedrive_sync()
            self.last_sync = now

        if self.should_run_email_sync():
            run_email_sync()
            self.last_email_sync = now

        if self.should_run_eod():
            run_eod_digest()
            self.last_eod = now

        if self.should_run_weekly():
            run_weekly_summary()
            self.last_weekly = now

    def run_daemon(self, check_interval: int = 300):
        """Run as a daemon, checking every N seconds."""
        log(f"Scheduler daemon started (check interval: {check_interval}s)")

        while True:
            if self.config.get("enabled", True):
                self.run_cycle()
            time.sleep(check_interval)


def run_once(task: str):
    """Run a specific task once."""
    if task == "brief":
        return run_daily_brief()
    elif task == "reminder":
        return run_reminder_check()
    elif task == "pattern":
        return run_pattern_analysis()
    elif task == "sync":
        return run_onedrive_sync()
    elif task == "escalate":
        return run_escalation()
    elif task == "email":
        return run_email_sync()
    elif task == "eod":
        return run_eod_digest()
    elif task == "weekly":
        return run_weekly_summary()
    elif task == "all":
        run_daily_brief()
        run_reminder_check()
        run_escalation()
        run_pattern_analysis()
        run_onedrive_sync()
        run_email_sync()
    else:
        print(f"Unknown task: {task}")
        return None


def print_crontab():
    """Print suggested crontab entries."""
    print("""# PCP Scheduled Tasks
# Add to crontab with: crontab -e

# Daily brief at 8 AM
0 8 * * * docker exec pcp-agent python3 /workspace/scripts/scheduler.py --run brief

# Reminder check every hour
0 * * * * docker exec pcp-agent python3 /workspace/scripts/scheduler.py --run reminder

# Pattern analysis at 9 AM
0 9 * * * docker exec pcp-agent python3 /workspace/scripts/scheduler.py --run pattern

# OneDrive sync every 4 hours (when configured)
0 */4 * * * docker exec pcp-agent python3 /workspace/scripts/scheduler.py --run sync

# Escalate approaching deadlines every 2 hours
0 */2 * * * docker exec pcp-agent python3 /workspace/scripts/scheduler.py --run escalate

# Email sync every 2 hours (when Microsoft Graph configured)
0 */2 * * * docker exec pcp-agent python3 /workspace/scripts/scheduler.py --run email

# End-of-day digest at 6 PM
0 18 * * * docker exec pcp-agent python3 /workspace/scripts/scheduler.py --run eod

# Weekly summary on Mondays at 9 AM
0 9 * * 1 docker exec pcp-agent python3 /workspace/scripts/scheduler.py --run weekly
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""PCP Scheduler

Usage:
    python scheduler.py --daemon           Run as daemon
    python scheduler.py --run <task>       Run specific task
    python scheduler.py --crontab          Print suggested crontab entries
    python scheduler.py --config           Show current configuration

Tasks:
    brief       - Daily brief generation
    reminder    - Check and process reminders
    pattern     - Run pattern analysis
    sync        - OneDrive sync (when configured)
    escalate    - Escalate approaching deadlines
    email       - Email sync (when Microsoft Graph configured)
    eod         - End-of-day digest
    weekly      - Weekly summary
    all         - Run all tasks
""")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--daemon":
        scheduler = Scheduler()
        scheduler.run_daemon()

    elif cmd == "--run":
        if len(sys.argv) < 3:
            print("Usage: --run <task>")
            sys.exit(1)
        run_once(sys.argv[2])

    elif cmd == "--crontab":
        print_crontab()

    elif cmd == "--config":
        config = load_config()
        print(json.dumps(config, indent=2))

    else:
        print(f"Unknown command: {cmd}")
