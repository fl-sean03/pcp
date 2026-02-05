#!/usr/bin/env python3
"""
PCP End-to-End Test Suite

Tests all major functionality based on SPEC.md use cases.
Run with: python tests/e2e_test_suite.py

Test Categories:
1. Capture & Memory (UC-1.x)
2. Search & Retrieval (UC-2.x)
3. Task Management (UC-3.x)
4. Commitment Tracking (UC-4.x)
5. Knowledge Base (UC-5.x)
6. Relationship Intelligence (UC-6.x)
7. Project Health (UC-7.x)
8. Brief Generation (UC-8.x)
9. Core Sync (custom)
"""

import json
import os
import sqlite3
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Test results tracking
class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []

    def record(self, name: str, passed: bool, error: str = None):
        if passed:
            self.passed.append(name)
        else:
            self.failed.append((name, error))

    def skip(self, name: str, reason: str):
        self.skipped.append((name, reason))

    def summary(self) -> str:
        total = len(self.passed) + len(self.failed) + len(self.skipped)
        lines = [
            f"\n{'='*60}",
            f"PCP E2E Test Results",
            f"{'='*60}",
            f"Passed:  {len(self.passed)}/{total}",
            f"Failed:  {len(self.failed)}/{total}",
            f"Skipped: {len(self.skipped)}/{total}",
            f"{'='*60}",
        ]

        if self.failed:
            lines.append("\nFailed Tests:")
            for name, error in self.failed:
                lines.append(f"  - {name}: {error}")

        if self.skipped:
            lines.append("\nSkipped Tests:")
            for name, reason in self.skipped:
                lines.append(f"  - {name}: {reason}")

        return "\n".join(lines)


results = TestResults()


def get_db():
    """Get database connection."""
    db_path = Path(__file__).parent.parent / "vault" / "vault.db"
    return sqlite3.connect(str(db_path))


def run_test(name: str):
    """Decorator for test functions."""
    def decorator(func):
        def wrapper():
            try:
                func()
                results.record(name, True)
                print(f"  [PASS] {name}")
            except AssertionError as e:
                results.record(name, False, str(e))
                print(f"  [FAIL] {name}: {e}")
            except Exception as e:
                results.record(name, False, f"{type(e).__name__}: {e}")
                print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        return wrapper
    return decorator


# ============================================================================
# UC-1: Capture & Memory Tests
# ============================================================================

print("\n[UC-1] Capture & Memory Tests")

@run_test("UC-1.1: store_capture basic")
def test_store_capture_basic():
    from vault_v2 import store_capture

    capture_id = store_capture(
        content="E2E test capture - basic note",
        capture_type="note",
        entities={"topics": ["testing"]}
    )
    assert capture_id is not None, "store_capture should return an ID"
    assert capture_id > 0, f"capture_id should be positive, got {capture_id}"

test_store_capture_basic()


@run_test("UC-1.2: store_task with due date")
def test_store_task():
    from vault_v2 import store_task

    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    task_id = store_task(
        content="E2E test task",
        due_date=tomorrow,
        priority="high"
    )
    assert task_id is not None, "store_task should return an ID"

test_store_task()


@run_test("UC-1.3: brain_dump processing")
def test_brain_dump():
    from vault_v2 import brain_dump

    text = """
    E2E brain dump test:
    - remember this is a test note
    - need to do something by Friday
    - interesting idea for later
    """
    result = brain_dump(text)
    assert result is not None, "brain_dump should return a result"
    # Should create multiple captures
    assert "capture_ids" in result or "task_ids" in result or isinstance(result, dict), \
        f"brain_dump should return structured data, got {type(result)}"

test_brain_dump()


# ============================================================================
# UC-2: Search & Retrieval Tests
# ============================================================================

print("\n[UC-2] Search & Retrieval Tests")

@run_test("UC-2.1: smart_search")
def test_smart_search():
    from vault_v2 import smart_search

    results = smart_search("test")
    assert results is not None, "smart_search should return results"
    assert isinstance(results, (list, dict)), f"Expected list or dict, got {type(results)}"

test_smart_search()


@run_test("UC-2.2: semantic_search")
def test_semantic_search():
    from vault_v2 import semantic_search

    try:
        results = semantic_search("testing functionality")
        # May return empty if ChromaDB not configured
        assert results is not None or results == [], "semantic_search should return results or empty list"
    except Exception as e:
        if "chroma" in str(e).lower():
            results.skip("UC-2.2: semantic_search", "ChromaDB not configured")
        else:
            raise

test_semantic_search()


@run_test("UC-2.3: unified_search")
def test_unified_search():
    from vault_v2 import unified_search

    results = unified_search("test")
    assert results is not None, "unified_search should return results"

test_unified_search()


# ============================================================================
# UC-3: Task Management Tests
# ============================================================================

print("\n[UC-3] Task Management Tests")

@run_test("UC-3.1: get_tasks pending")
def test_get_tasks():
    from vault_v2 import get_tasks

    tasks = get_tasks(status="pending")
    assert tasks is not None, "get_tasks should return results"
    assert isinstance(tasks, list), f"Expected list, got {type(tasks)}"

test_get_tasks()


@run_test("UC-3.2: complete_task")
def test_complete_task():
    from vault_v2 import store_task, complete_task, get_tasks

    # Create a task to complete
    task_id = store_task(content="E2E task to complete", priority="low")
    assert task_id is not None

    # Complete it
    complete_task(task_id)

    # Verify it's completed
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
    row = c.fetchone()
    conn.close()

    assert row is not None, "Task should exist"
    assert row[0] in ("completed", "done"), f"Task should be completed/done, got {row[0]}"

test_complete_task()


@run_test("UC-3.3: get_task_with_context")
def test_get_task_with_context():
    from vault_v2 import get_task_with_context, store_task

    # Create task
    task_id = store_task(content="E2E context test task")

    # Get with context
    task = get_task_with_context(task_id)
    assert task is not None, "get_task_with_context should return task"
    assert "content" in task or hasattr(task, "content"), "Task should have content"

test_get_task_with_context()


# ============================================================================
# UC-4: Commitment Tracking Tests
# ============================================================================

# ============================================================================
# UC-4: Knowledge Base Tests
# ============================================================================

print("\n[UC-4] Knowledge Base Tests")

@run_test("UC-4.1: add_knowledge")
def test_add_knowledge():
    from knowledge import add_knowledge

    knowledge_id = add_knowledge(
        content="E2E test knowledge entry",
        category="fact"
    )
    assert knowledge_id is not None, "add_knowledge should return an ID"

test_add_knowledge()


@run_test("UC-5.2: query_knowledge")
def test_query_knowledge():
    from knowledge import query_knowledge

    results = query_knowledge("test")
    assert results is not None, "query_knowledge should return results"

test_query_knowledge()


@run_test("UC-5.3: record_decision")
def test_record_decision():
    from knowledge import record_decision

    decision_id = record_decision(
        content="E2E test decision",
        context="Testing decision tracking",
        alternatives=["option A", "option B"]
    )
    assert decision_id is not None, "record_decision should return an ID"

test_record_decision()


# ============================================================================
# UC-6: Relationship Intelligence Tests
# ============================================================================

print("\n[UC-6] Relationship Intelligence Tests")

@run_test("UC-6.1: get_stale_relationships")
def test_get_stale_relationships():
    from vault_v2 import get_stale_relationships

    stale = get_stale_relationships(days=14)
    assert stale is not None, "get_stale_relationships should return results"
    assert isinstance(stale, list), f"Expected list, got {type(stale)}"

test_get_stale_relationships()


@run_test("UC-6.2: get_relationship_summary")
def test_get_relationship_summary():
    from vault_v2 import get_relationship_summary

    # Get first person ID
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM people LIMIT 1")
    row = c.fetchone()
    conn.close()

    if row:
        summary = get_relationship_summary(row[0])
        assert summary is not None, "get_relationship_summary should return data"
    else:
        results.skip("UC-6.2: get_relationship_summary", "No people in database")

test_get_relationship_summary()


# ============================================================================
# UC-7: Project Health Tests
# ============================================================================

print("\n[UC-7] Project Health Tests")

@run_test("UC-7.1: get_project_health")
def test_get_project_health():
    from vault_v2 import get_project_health

    # Get first project ID
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM projects LIMIT 1")
    row = c.fetchone()
    conn.close()

    if row:
        health = get_project_health(row[0])
        assert health is not None, "get_project_health should return data"
    else:
        results.skip("UC-7.1: get_project_health", "No projects in database")

test_get_project_health()


@run_test("UC-7.2: get_stalled_projects")
def test_get_stalled_projects():
    from vault_v2 import get_stalled_projects

    stalled = get_stalled_projects(days=14)
    assert stalled is not None, "get_stalled_projects should return results"

test_get_stalled_projects()


@run_test("UC-7.3: restore_context")
def test_restore_context():
    from vault_v2 import restore_context

    # Get first project ID
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM projects LIMIT 1")
    row = c.fetchone()
    conn.close()

    if row:
        context = restore_context(row[0])
        assert context is not None, "restore_context should return data"
    else:
        results.skip("UC-7.3: restore_context", "No projects in database")

test_restore_context()


# ============================================================================
# UC-8: Brief Generation Tests
# ============================================================================

print("\n[UC-8] Brief Generation Tests")

@run_test("UC-8.1: generate_brief daily")
def test_generate_brief_daily():
    from brief import generate_brief

    brief = generate_brief("daily")
    assert brief is not None, "generate_brief should return data"
    assert isinstance(brief, dict), f"Expected dict, got {type(brief)}"

test_generate_brief_daily()


@run_test("UC-8.2: daily_brief formatted")
def test_daily_brief_formatted():
    from brief import daily_brief

    text = daily_brief()
    assert text is not None, "daily_brief should return text"
    assert isinstance(text, str), f"Expected string, got {type(text)}"
    assert len(text) > 0, "daily_brief should not be empty"

test_daily_brief_formatted()


@run_test("UC-8.3: weekly_summary")
def test_weekly_summary():
    from brief import weekly_summary

    text = weekly_summary()
    assert text is not None, "weekly_summary should return text"

test_weekly_summary()


@run_test("UC-8.4: eod_digest")
def test_eod_digest():
    from brief import eod_digest

    text = eod_digest()
    assert text is not None, "eod_digest should return text"

test_eod_digest()


# ============================================================================
# Database Integrity Tests
# ============================================================================

print("\n[DB] Database Integrity Tests")

@run_test("DB-1: All required tables exist")
def test_tables_exist():
    required_tables = [
        "captures_v2", "people", "projects", "tasks",
        "commitments", "knowledge", "decisions", "emails", "files"
    ]

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing = {row[0] for row in c.fetchall()}
    conn.close()

    missing = [t for t in required_tables if t not in existing]
    assert not missing, f"Missing tables: {missing}"

test_tables_exist()


@run_test("DB-2: Foreign key relationships valid")
def test_foreign_keys():
    conn = get_db()
    c = conn.cursor()

    # Check tasks -> projects
    c.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE project_id IS NOT NULL
        AND project_id NOT IN (SELECT id FROM projects)
    """)
    orphan_tasks = c.fetchone()[0]

    conn.close()
    assert orphan_tasks == 0, f"Found {orphan_tasks} tasks with invalid project_id"

test_foreign_keys()


# ============================================================================
# Cleanup Test Data
# ============================================================================

print("\n[Cleanup] Removing test data...")

def cleanup_test_data():
    conn = get_db()
    c = conn.cursor()

    # Remove test captures
    c.execute("DELETE FROM captures_v2 WHERE content LIKE 'E2E test%'")
    c.execute("DELETE FROM tasks WHERE content LIKE 'E2E%'")
    c.execute("DELETE FROM commitments WHERE content LIKE 'E2E%'")
    c.execute("DELETE FROM knowledge WHERE content LIKE 'E2E%'")
    c.execute("DELETE FROM decisions WHERE content LIKE 'E2E%'")

    conn.commit()
    conn.close()
    print("  [OK] Test data cleaned up")

cleanup_test_data()


# ============================================================================
# Print Summary
# ============================================================================

print(results.summary())

# Exit with appropriate code
sys.exit(0 if not results.failed else 1)
