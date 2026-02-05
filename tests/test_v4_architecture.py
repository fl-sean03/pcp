#!/usr/bin/env python3
"""
Test Suite for PCP v4.0 Architecture.

This suite verifies:
1. Message Queue - SQLite persistence and operations
2. Parallel Task Manager - Task lifecycle
3. Queue Bridge - Integration layer
4. Focus Prompts - Existence and content
5. Orchestrator - Basic functionality

Run with: python test_v4_architecture.py
"""

import os
import sys
import json
import tempfile
import sqlite3
from datetime import datetime, timedelta

# Add scripts directory to path
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


class TestResult:
    """Test result container."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def success(self, name: str):
        self.passed += 1
        print(f"  ✅ {name}")

    def failure(self, name: str, error: str):
        self.failed += 1
        self.errors.append((name, error))
        print(f"  ❌ {name}: {error}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed ({self.failed} failed)")
        if self.errors:
            print("\nFailures:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        return self.failed == 0


def test_message_queue(results: TestResult):
    """Test MessageQueue functionality."""
    print("\n1. Message Queue Tests")
    print("-" * 40)

    from message_queue import MessageQueue

    # Create queue with temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        queue = MessageQueue(test_db)

        # Test enqueue
        try:
            queue_id = queue.enqueue(
                message_id="test_123",
                channel_id="channel_456",
                user_id="user_789",
                user_name="TestUser",
                content="Test message content",
                attachments=[{"filename": "test.pdf"}],
                priority=3
            )
            assert queue_id is not None and queue_id > 0
            results.success("Enqueue message")
        except Exception as e:
            results.failure("Enqueue message", str(e))

        # Test get_pending_count
        try:
            count = queue.get_pending_count()
            assert count == 1, f"Expected 1, got {count}"
            results.success("Get pending count")
        except Exception as e:
            results.failure("Get pending count", str(e))

        # Test get_next_pending
        try:
            message = queue.get_next_pending()
            assert message is not None
            assert message['content'] == "Test message content"
            assert message['priority'] == 3
            results.success("Get next pending")
        except Exception as e:
            results.failure("Get next pending", str(e))

        # Test mark_processing
        try:
            success = queue.mark_processing(queue_id)
            assert success
            count = queue.get_pending_count()
            assert count == 0, "Should be no pending after marking processing"
            results.success("Mark processing")
        except Exception as e:
            results.failure("Mark processing", str(e))

        # Test get_processing_count
        try:
            count = queue.get_processing_count()
            assert count == 1, f"Expected 1 processing, got {count}"
            results.success("Get processing count")
        except Exception as e:
            results.failure("Get processing count", str(e))

        # Test mark_completed
        try:
            success = queue.mark_completed(queue_id, "Done!")
            assert success
            status = queue.get_status("test_123")
            assert status['status'] == 'completed'
            assert status['response'] == "Done!"
            results.success("Mark completed")
        except Exception as e:
            results.failure("Mark completed", str(e))

        # Test get_recent
        try:
            recent = queue.get_recent(10)
            assert len(recent) >= 1
            results.success("Get recent messages")
        except Exception as e:
            results.failure("Get recent messages", str(e))

        # Test duplicate handling
        try:
            dup_id = queue.enqueue(
                message_id="test_123",  # Same message ID
                channel_id="channel_456",
                user_id="user_789",
                user_name="TestUser",
                content="Duplicate content"
            )
            # Should return existing ID, not create duplicate
            assert dup_id == queue_id
            results.success("Handle duplicate messages")
        except Exception as e:
            results.failure("Handle duplicate messages", str(e))

    finally:
        os.unlink(test_db)


def test_parallel_task_manager(results: TestResult):
    """Test ParallelTaskManager functionality."""
    print("\n2. Parallel Task Manager Tests")
    print("-" * 40)

    from message_queue import ParallelTaskManager

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        from message_queue import MessageQueue
        # Initialize schema
        MessageQueue(test_db)

        manager = ParallelTaskManager(test_db)

        # Test create_task
        try:
            task_id = manager.create_task(
                description="Test parallel task",
                focus_mode="research",
                context={"key": "value"},
                discord_channel_id="channel_123"
            )
            assert task_id is not None and task_id > 0
            results.success("Create parallel task")
        except Exception as e:
            results.failure("Create parallel task", str(e))

        # Test get_task
        try:
            task = manager.get_task(task_id)
            assert task is not None
            assert task['description'] == "Test parallel task"
            assert task['focus_mode'] == "research"
            assert task['status'] == "pending"
            results.success("Get parallel task")
        except Exception as e:
            results.failure("Get parallel task", str(e))

        # Test start_task
        try:
            success = manager.start_task(task_id, pid=12345)
            assert success
            task = manager.get_task(task_id)
            assert task['status'] == 'running'
            assert task['pid'] == 12345
            results.success("Start parallel task")
        except Exception as e:
            results.failure("Start parallel task", str(e))

        # Test add_progress
        try:
            success = manager.add_progress(task_id, "Step 1 complete")
            success = manager.add_progress(task_id, "Step 2 complete")
            assert success
            task = manager.get_task(task_id)
            assert len(task['progress_updates']) == 2
            results.success("Add progress updates")
        except Exception as e:
            results.failure("Add progress updates", str(e))

        # Test complete_task
        try:
            success = manager.complete_task(task_id, "Task finished successfully")
            assert success
            task = manager.get_task(task_id)
            assert task['status'] == 'completed'
            assert task['result'] == "Task finished successfully"
            results.success("Complete parallel task")
        except Exception as e:
            results.failure("Complete parallel task", str(e))

        # Test get_pending_tasks
        try:
            # Create another pending task
            task_id2 = manager.create_task("Second task", "general")
            pending = manager.get_pending_tasks()
            assert len(pending) == 1
            assert pending[0]['id'] == task_id2
            results.success("Get pending tasks")
        except Exception as e:
            results.failure("Get pending tasks", str(e))

    finally:
        os.unlink(test_db)


def test_queue_bridge(results: TestResult):
    """Test queue bridge functions."""
    print("\n3. Queue Bridge Tests")
    print("-" * 40)

    # Import will use the default database path
    from queue_bridge import (
        enqueue_discord_message, get_message_status,
        get_pending_count, get_stats,
        create_parallel_task, complete_parallel_task
    )

    # Test enqueue
    try:
        import time
        test_msg_id = f"bridge_test_{int(time.time() * 1000)}"
        queue_id = enqueue_discord_message(
            message_id=test_msg_id,
            channel_id="bridge_channel",
            user_id="bridge_user",
            user_name="BridgeTest",
            content="Bridge test message"
        )
        assert queue_id is not None
        results.success("Bridge: Enqueue message")
    except Exception as e:
        results.failure("Bridge: Enqueue message", str(e))

    # Test get status
    try:
        status = get_message_status(test_msg_id)
        assert status is not None
        assert status['content'] == "Bridge test message"
        results.success("Bridge: Get message status")
    except Exception as e:
        results.failure("Bridge: Get message status", str(e))

    # Test stats
    try:
        stats = get_stats()
        assert 'queue' in stats
        assert 'parallel_tasks' in stats
        assert stats['queue']['pending'] >= 0
        results.success("Bridge: Get stats")
    except Exception as e:
        results.failure("Bridge: Get stats", str(e))


def test_focus_prompts(results: TestResult):
    """Test focus prompt files exist and have correct content."""
    print("\n4. Focus Prompts Tests")
    print("-" * 40)

    prompts_dir = os.path.join(os.path.dirname(SCRIPTS_DIR), 'prompts', 'focus')

    expected_prompts = ['general.md', 'homework.md', 'research.md', 'writing.md', 'system.md']

    for prompt_file in expected_prompts:
        try:
            path = os.path.join(prompts_dir, prompt_file)
            assert os.path.exists(path), f"File not found: {path}"

            with open(path, 'r') as f:
                content = f.read()

            # Check for required content
            assert '# Focus:' in content, "Missing Focus header"
            assert 'FULL PCP capabilities' in content or 'FULL capabilities' in content, \
                "Missing reminder about full capabilities"
            assert 'notify' in content.lower() or 'discord' in content.lower(), \
                "Missing notification guidance"

            results.success(f"Focus prompt: {prompt_file}")
        except Exception as e:
            results.failure(f"Focus prompt: {prompt_file}", str(e))


def test_spec_update(results: TestResult):
    """Test that SPEC.md has been updated to v4.0."""
    print("\n5. Documentation Tests")
    print("-" * 40)

    spec_path = os.path.join(os.path.dirname(SCRIPTS_DIR), 'SPEC.md')

    try:
        with open(spec_path, 'r') as f:
            content = f.read()

        # Check version
        assert 'Version:** 4.0' in content or 'Version: 4.0' in content, \
            "SPEC.md not updated to v4.0"
        results.success("SPEC.md version 4.0")
    except Exception as e:
        results.failure("SPEC.md version 4.0", str(e))

    try:
        # Check for universal agent content
        assert 'Universal Agent' in content or 'universal agent' in content, \
            "Missing Universal Agent concept"
        results.success("SPEC.md has Universal Agent")
    except Exception as e:
        results.failure("SPEC.md has Universal Agent", str(e))

    try:
        # Check for queue content
        assert 'Queue' in content or 'queue' in content, \
            "Missing Queue documentation"
        results.success("SPEC.md has Queue documentation")
    except Exception as e:
        results.failure("SPEC.md has Queue documentation", str(e))

    try:
        # Check for focus modes
        assert 'Focus Mode' in content or 'focus_mode' in content, \
            "Missing Focus Modes documentation"
        results.success("SPEC.md has Focus Modes")
    except Exception as e:
        results.failure("SPEC.md has Focus Modes", str(e))


def test_claude_md_update(results: TestResult):
    """Test that CLAUDE.md has been updated for v4.0."""
    print("\n6. Agent Prompt Tests")
    print("-" * 40)

    claude_path = os.path.join(os.path.dirname(SCRIPTS_DIR), 'CLAUDE.md')

    try:
        with open(claude_path, 'r') as f:
            content = f.read()

        # Check version
        assert 'Version: 8.0' in content or '8.0' in content, \
            "CLAUDE.md version not updated"
        results.success("CLAUDE.md version updated")
    except Exception as e:
        results.failure("CLAUDE.md version updated", str(e))

    try:
        # Check for agentic execution model
        assert 'Agentic Execution' in content or 'agentic' in content.lower(), \
            "Missing Agentic Execution guidance"
        results.success("CLAUDE.md has Agentic Execution")
    except Exception as e:
        results.failure("CLAUDE.md has Agentic Execution", str(e))

    try:
        # Check for judgment guidance
        assert 'judgment' in content.lower() or 'JUDGMENT' in content, \
            "Missing judgment-based routing"
        results.success("CLAUDE.md has judgment-based routing")
    except Exception as e:
        results.failure("CLAUDE.md has judgment-based routing", str(e))


def test_architecture_doc(results: TestResult):
    """Test that ARCHITECTURE_V4.md exists and has correct content."""
    print("\n7. Architecture Document Tests")
    print("-" * 40)

    arch_path = os.path.join(os.path.dirname(SCRIPTS_DIR), 'docs', 'ARCHITECTURE_V4.md')

    try:
        assert os.path.exists(arch_path), "ARCHITECTURE_V4.md not found"
        results.success("ARCHITECTURE_V4.md exists")
    except Exception as e:
        results.failure("ARCHITECTURE_V4.md exists", str(e))
        return

    try:
        with open(arch_path, 'r') as f:
            content = f.read()

        # Check for key sections
        checks = [
            ('Message Queue', 'MESSAGE QUEUE' in content or 'Message Queue' in content),
            ('Orchestrator', 'ORCHESTRATOR' in content or 'Orchestrator' in content),
            ('Universal Agent', 'Universal Agent' in content or 'UNIVERSAL AGENT' in content),
            ('Focus Modes', 'Focus Mode' in content or 'focus mode' in content),
            ('Implementation Plan', 'Implementation' in content),
        ]

        for name, check in checks:
            try:
                assert check, f"Missing {name} section"
                results.success(f"Architecture: {name}")
            except AssertionError as e:
                results.failure(f"Architecture: {name}", str(e))
    except Exception as e:
        results.failure("Architecture document content", str(e))


def run_all_tests():
    """Run all test suites."""
    print("=" * 60)
    print("PCP v4.0 Architecture Test Suite")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = TestResult()

    # Run test suites
    test_message_queue(results)
    test_parallel_task_manager(results)
    test_queue_bridge(results)
    test_focus_prompts(results)
    test_spec_update(results)
    test_claude_md_update(results)
    test_architecture_doc(results)

    # Summary
    success = results.summary()

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
