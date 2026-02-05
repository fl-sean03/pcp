#!/usr/bin/env python3
"""
PCP Production Smoke Test.

Quick validation that production deployment is working correctly.
Run after every production deployment.

Usage:
    python3 test_production_smoke.py
"""

import os
import sys
import sqlite3
import time
from datetime import datetime

# Add scripts directory to path
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

# Determine paths
VAULT_DB = os.environ.get('VAULT_DB_PATH', '/workspace/vault/vault.db')


class SmokeTestResult:
    """Track smoke test results."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def success(self, name: str, details: str = ""):
        self.passed += 1
        print(f"  ✅ {name}" + (f": {details}" if details else ""))

    def failure(self, name: str, error: str):
        self.failed += 1
        self.errors.append((name, error))
        print(f"  ❌ {name}: {error}")

    def all_passed(self) -> bool:
        return self.failed == 0


def run_smoke_tests():
    """Run production smoke tests."""
    print("=" * 60)
    print("PCP Production Smoke Test")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {VAULT_DB}")
    print("")

    results = SmokeTestResult()

    # Test 1: Database Connection
    print("Database Connectivity")
    print("-" * 40)
    try:
        conn = sqlite3.connect(VAULT_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        results.success("Database connection")
    except Exception as e:
        results.failure("Database connection", str(e))

    # Test 2: Core Tables Exist
    print("\nCore Tables")
    print("-" * 40)
    core_tables = [
        'captures_v2',
        'people',
        'projects',
        'tasks',
        'knowledge',
        'decisions'
    ]

    try:
        conn = sqlite3.connect(VAULT_DB)
        cursor = conn.cursor()
        for table in core_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            results.success(f"Table '{table}'", f"{count} records")
        conn.close()
    except Exception as e:
        results.failure("Core tables", str(e))

    # Test 3: Queue Tables Exist
    print("\nQueue Tables")
    print("-" * 40)
    queue_tables = ['discord_message_queue', 'parallel_tasks']

    try:
        conn = sqlite3.connect(VAULT_DB)
        cursor = conn.cursor()
        for table in queue_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            results.success(f"Table '{table}'", f"{count} records")
        conn.close()
    except Exception as e:
        results.failure("Queue tables", str(e))

    # Test 4: Discord Webhook Configuration
    print("\nDiscord Configuration")
    print("-" * 40)
    try:
        from discord_notify import DEFAULT_WEBHOOK
        if DEFAULT_WEBHOOK and len(DEFAULT_WEBHOOK) > 20:
            results.success("Webhook configured")
        else:
            results.failure("Webhook configured", "Webhook URL is empty or too short")
    except Exception as e:
        results.failure("Webhook configured", str(e))

    # Test 5: Import Core Modules
    print("\nCore Modules")
    print("-" * 40)
    modules_to_test = [
        ('message_queue', 'MessageQueue'),
        ('vault_v2', 'smart_capture'),
        ('brief', 'daily_brief'),
        ('discord_notify', 'notify'),
    ]

    for module_name, attr_name in modules_to_test:
        try:
            module = __import__(module_name)
            if hasattr(module, attr_name):
                results.success(f"Import {module_name}.{attr_name}")
            else:
                results.failure(f"Import {module_name}.{attr_name}", "Attribute not found")
        except Exception as e:
            results.failure(f"Import {module_name}", str(e))

    # Test 6: Focus Prompts Exist
    print("\nFocus Prompts")
    print("-" * 40)
    prompts_dir = os.path.join(os.path.dirname(SCRIPTS_DIR), 'prompts', 'focus')
    focus_modes = ['general', 'homework', 'research', 'writing', 'system']

    for mode in focus_modes:
        path = os.path.join(prompts_dir, f"{mode}.md")
        if os.path.exists(path):
            results.success(f"Focus prompt: {mode}.md")
        else:
            results.failure(f"Focus prompt: {mode}.md", "File not found")

    # Test 7: Recent Activity Check (production data exists)
    print("\nProduction Data")
    print("-" * 40)
    try:
        conn = sqlite3.connect(VAULT_DB)
        cursor = conn.cursor()

        # Check for recent captures (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) FROM captures_v2
            WHERE created_at > datetime('now', '-7 days')
        """)
        recent_captures = cursor.fetchone()[0]
        if recent_captures > 0:
            results.success("Recent captures", f"{recent_captures} in last 7 days")
        else:
            results.success("Recent captures", "None (new deployment?)")

        # Check for active tasks
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        pending_tasks = cursor.fetchone()[0]
        results.success("Pending tasks", str(pending_tasks))

        conn.close()
    except Exception as e:
        results.failure("Production data", str(e))

    # Summary
    print("\n" + "=" * 60)
    print("Smoke Test Summary")
    print("=" * 60)
    total = results.passed + results.failed
    print(f"  Passed: {results.passed}/{total}")
    print(f"  Failed: {results.failed}/{total}")

    if results.errors:
        print("\nFailures:")
        for name, error in results.errors:
            print(f"  - {name}: {error}")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    return 0 if results.all_passed() else 1


if __name__ == "__main__":
    sys.exit(run_smoke_tests())
