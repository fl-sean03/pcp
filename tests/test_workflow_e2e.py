#!/usr/bin/env python3
"""
End-to-End Workflow Test Script

Tests the full PCP workflow including:
- Discord attachment handling
- Task delegation
- Transcription workflow
- Worker execution

Run inside pcp-agent container:
    docker exec pcp-agent python3 /workspace/scripts/test_workflow_e2e.py

Or from host:
    python3 scripts/test_workflow_e2e.py --host
"""

import os
import sys
import json
import time
import subprocess
import tempfile
from pathlib import Path

# Add scripts to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test status tracking
passed = []
failed = []


def test(name):
    """Decorator for test functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"\n{'='*60}")
            print(f"TEST: {name}")
            print('='*60)
            try:
                result = func(*args, **kwargs)
                if result:
                    print(f"  PASSED: {name}")
                    passed.append(name)
                else:
                    print(f"  FAILED: {name}")
                    failed.append(name)
                return result
            except Exception as e:
                print(f"  FAILED: {name} - {e}")
                failed.append(name)
                return False
        return wrapper
    return decorator


@test("Database Connection")
def test_database():
    """Test database is accessible and has required tables."""
    import sqlite3

    vault_path = "/workspace/vault/vault.db"
    if not os.path.exists(vault_path):
        print(f"  Database not found at {vault_path}")
        return False

    conn = sqlite3.connect(vault_path)
    cursor = conn.cursor()

    # Check required tables exist
    required_tables = [
        "captures_v2", "people", "projects", "tasks",
        "knowledge", "delegated_tasks"
    ]

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing = {row[0] for row in cursor.fetchall()}

    missing = set(required_tables) - existing
    if missing:
        print(f"  Missing tables: {missing}")
        return False

    print(f"  All required tables present")
    conn.close()
    return True


@test("Vault Smart Capture")
def test_smart_capture():
    """Test vault capture functionality."""
    from vault_v2 import smart_capture, smart_search

    test_content = f"E2E test capture at {time.time()}"
    result = smart_capture(test_content)

    if not result.get("capture_id"):
        print(f"  Capture failed: {result}")
        return False

    print(f"  Created capture #{result['capture_id']}")

    # Verify search finds it
    search_results = smart_search("E2E test capture")
    if not search_results:
        print(f"  Search found no results")
        return False

    print(f"  Search found {len(search_results)} results")
    return True


@test("Task Delegation - Create")
def test_task_delegation_create():
    """Test creating a delegated task."""
    from task_delegation import delegate_task, get_task

    task_id = delegate_task(
        description="E2E Test Task - should be auto-cleaned",
        context={"test": True},
        priority=10,  # Low priority
        tags=["test", "e2e"]
    )

    if not task_id:
        print(f"  Failed to create task")
        return False

    print(f"  Created task #{task_id}")

    # Verify task exists
    task = get_task(task_id)
    if not task:
        print(f"  Could not retrieve task")
        return False

    print(f"  Task status: {task['status']}")
    return True


@test("Task Delegation - List")
def test_task_delegation_list():
    """Test listing delegated tasks."""
    from task_delegation import list_tasks, get_pending_count

    tasks = list_tasks(limit=5)
    pending = get_pending_count()

    print(f"  Found {len(tasks)} tasks, {pending} pending")
    return True


@test("Task Delegation - Claim/Complete Flow")
def test_task_delegation_flow():
    """Test the full claim -> running -> complete flow."""
    from task_delegation import (
        delegate_task, claim_next_task, update_task_status,
        complete_task, get_task
    )

    # Create a test task with HIGH priority (1) to ensure it's claimed first
    task_id = delegate_task(
        description="Flow test task",
        priority=1,  # Highest priority - will be claimed before other pending tasks
        tags=["test"]
    )
    print(f"  Created task #{task_id}")

    # Claim it
    session_id = f"test-{time.time()}"
    claimed = claim_next_task(session_id)

    if not claimed or claimed["id"] != task_id:
        print(f"  Failed to claim task (got: {claimed})")
        # Clean up anyway
        if claimed:
            complete_task(claimed["id"], error="Test cleanup")
        return False

    print(f"  Claimed task #{task_id}")

    # Mark running
    update_task_status(task_id, "running")
    task = get_task(task_id)
    if task["status"] != "running":
        print(f"  Status not updated to running")
        return False

    print(f"  Status updated to running")

    # Complete it
    complete_task(task_id, result={"test": "success"})
    task = get_task(task_id)
    if task["status"] != "completed":
        print(f"  Status not updated to completed")
        return False

    print(f"  Task completed successfully")
    return True


@test("File Processor - Image")
def test_file_processor_image():
    """Test image processing (if test image available)."""
    from file_processor import process_file

    # Create a simple test image using imagemagick if available
    test_image = "/tmp/test_image.png"

    try:
        subprocess.run([
            "convert", "-size", "100x100", "xc:white",
            "-font", "Helvetica", "-pointsize", "12",
            "-annotate", "+10+50", "Test",
            test_image
        ], check=True, capture_output=True)
    except:
        print(f"  Skipping: imagemagick not available")
        return True  # Skip, not fail

    result = process_file(test_image)

    if "error" in result:
        print(f"  Processing error: {result['error']}")
        return False

    print(f"  Processed image: mime={result.get('mime_type')}")
    return True


@test("Transcription Workflow - LaTeX Generation")
def test_transcription_latex():
    """Test LaTeX template generation (without actual transcription)."""
    # Just test the module imports correctly
    try:
        from transcribe_to_overleaf import slugify, validate_latex

        # Test slugify
        assert slugify("Hello World!") == "hello-world"
        print(f"  slugify works")

        # Test validation
        valid_latex = r"""\documentclass{article}
\begin{document}
Hello
\end{document}"""

        result = validate_latex(valid_latex)
        if not result["valid"]:
            print(f"  Validation failed on valid LaTeX: {result}")
            return False

        print(f"  LaTeX validation works")
        return True

    except ImportError as e:
        print(f"  Import error: {e}")
        return False


@test("Overleaf Directory Structure")
def test_overleaf_dirs():
    """Test Overleaf directories are accessible."""
    overleaf_dir = "/workspace/overleaf"
    projects_dir = "/workspace/overleaf/projects"

    if not os.path.exists(overleaf_dir):
        print(f"  Overleaf dir not mounted: {overleaf_dir}")
        return False

    os.makedirs(projects_dir, exist_ok=True)

    if not os.path.exists(projects_dir):
        print(f"  Could not create projects dir: {projects_dir}")
        return False

    print(f"  Overleaf directories accessible")
    return True


@test("Discord Attachments Directory")
def test_attachments_dir():
    """Test Discord attachments directory is accessible."""
    attachments_dir = "/tmp/discord_attachments"

    if not os.path.exists(attachments_dir):
        print(f"  Attachments dir not found: {attachments_dir}")
        return False

    # Test write access
    test_file = os.path.join(attachments_dir, "test_write.txt")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print(f"  Attachments directory writable")
        return True
    except Exception as e:
        print(f"  Cannot write to attachments dir: {e}")
        return False


@test("Knowledge Base")
def test_knowledge():
    """Test knowledge base operations."""
    from knowledge import add_knowledge, query_knowledge, list_knowledge

    # Add test knowledge
    kid = add_knowledge(
        content="E2E Test fact - safe to delete",
        category="fact",
        confidence=0.5
    )

    if not kid:
        print(f"  Failed to add knowledge")
        return False

    print(f"  Added knowledge #{kid}")

    # Query it
    results = query_knowledge("E2E Test fact")
    if not results:
        print(f"  Query returned no results")
        return False

    print(f"  Query found {len(results)} results")
    return True


@test("Brief Generation")
def test_brief():
    """Test daily brief generation."""
    from brief import generate_brief

    try:
        data = generate_brief("daily")

        if not data:
            print(f"  No data returned")
            return False

        print(f"  Brief generated with {len(data)} sections")
        return True

    except Exception as e:
        print(f"  Brief generation failed: {e}")
        return False


def run_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("PCP End-to-End Workflow Tests")
    print("="*60)

    # Run all tests
    test_database()
    test_smart_capture()
    test_task_delegation_create()
    test_task_delegation_list()
    test_task_delegation_flow()
    test_file_processor_image()
    test_transcription_latex()
    test_overleaf_dirs()
    test_attachments_dir()
    test_knowledge()
    test_brief()

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"  Passed: {len(passed)}")
    print(f"  Failed: {len(failed)}")

    if failed:
        print(f"\nFailed tests:")
        for name in failed:
            print(f"  - {name}")
        return 1
    else:
        print(f"\nAll tests passed!")
        return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", action="store_true",
                        help="Running from host (use docker exec)")
    args = parser.parse_args()

    if args.host:
        # Re-run inside container
        result = subprocess.run([
            "docker", "exec", "pcp-agent",
            "python3", "/workspace/scripts/test_workflow_e2e.py"
        ])
        sys.exit(result.returncode)
    else:
        sys.exit(run_tests())
