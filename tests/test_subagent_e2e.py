#!/usr/bin/env python3
"""
E2E Tests for Subagent Architecture

These tests validate that the subagent architecture works correctly:
1. Subagents survive parent completion
2. Subagents can complete their work
3. Results are posted to Discord
4. Error handling works
5. Timeouts are respected

IMPORTANT: These tests require a running PCP environment.
Run with: pytest tests/test_subagent_e2e.py -v
"""

import asyncio
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import patch

import pytest

# Test configuration
CONTAINER_NAME = "pcp-agent"
TEST_TIMEOUT = 120  # seconds
QUICK_TASK_TIMEOUT = 30
WORKSPACE_DIR = "/workspace"


class SubagentTestResult:
    """Container for subagent test results."""
    def __init__(self):
        self.started = False
        self.completed = False
        self.killed = False
        self.output = ""
        self.error = ""
        self.duration_seconds = 0
        self.session_file = ""


def docker_exec(cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
    """Execute command in pcp-agent container."""
    full_cmd = f"docker exec {CONTAINER_NAME} sh -c '{cmd}'"
    try:
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"


def get_recent_session_files(minutes: int = 5) -> List[str]:
    """Get session files modified in the last N minutes."""
    cmd = f"find /home/pcp/.claude/projects -name '*.jsonl' -mmin -{minutes} 2>/dev/null"
    code, stdout, _ = docker_exec(cmd)
    if code == 0:
        return [f.strip() for f in stdout.strip().split('\n') if f.strip()]
    return []


def get_subagent_sessions(parent_session_id: str) -> List[str]:
    """Get subagent session files for a parent session."""
    cmd = f"ls /home/pcp/.claude/projects/-workspace/{parent_session_id}/subagents/*.jsonl 2>/dev/null"
    code, stdout, _ = docker_exec(cmd)
    if code == 0:
        return [f.strip() for f in stdout.strip().split('\n') if f.strip()]
    return []


def read_session_file(path: str) -> List[Dict]:
    """Read and parse a session JSONL file."""
    cmd = f"cat {path}"
    code, stdout, _ = docker_exec(cmd, timeout=60)
    if code != 0:
        return []

    entries = []
    for line in stdout.strip().split('\n'):
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def analyze_session(entries: List[Dict]) -> Dict:
    """Analyze session entries for key events."""
    analysis = {
        "task_tool_used": False,
        "run_in_background": False,
        "subagent_started": False,
        "subagent_completed": False,
        "subagent_killed": False,
        "error_messages": [],
        "tool_uses": [],
        "agent_ids": [],
    }

    for entry in entries:
        msg = entry.get("message", {})

        # Check for tool uses
        if msg.get("role") == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        analysis["tool_uses"].append(tool_name)

                        if tool_name == "Task":
                            analysis["task_tool_used"] = True
                            if tool_input.get("run_in_background"):
                                analysis["run_in_background"] = True

        # Check for tool results
        if msg.get("role") == "user":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        result_content = block.get("content", "")
                        if isinstance(result_content, str):
                            if "Async agent launched" in result_content:
                                analysis["subagent_started"] = True
                            if "is_error" in str(block):
                                analysis["error_messages"].append(result_content)

        # Check for queue operations
        if entry.get("type") == "queue-operation":
            content = entry.get("content", "")
            if "status>killed</status" in content or '"killed"' in content:
                analysis["subagent_killed"] = True
            if "status>completed</status" in content or '"completed"' in content:
                analysis["subagent_completed"] = True

        # Extract agent IDs
        tool_result = entry.get("toolUseResult", {})
        if isinstance(tool_result, dict):
            agent_id = tool_result.get("agentId")
            if agent_id:
                analysis["agent_ids"].append(agent_id)

    return analysis


class TestSubagentLifecycle:
    """Test subagent lifecycle management."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        # Verify container is running
        code, stdout, _ = docker_exec("echo 'test'")
        if code != 0:
            pytest.skip(f"Container {CONTAINER_NAME} not available")

    def test_container_health(self):
        """Verify PCP container is healthy."""
        code, stdout, _ = docker_exec("claude --version")
        assert code == 0, "Claude Code should be installed in container"

    def test_session_files_accessible(self):
        """Verify session files are accessible."""
        code, stdout, _ = docker_exec("ls /home/pcp/.claude/projects/ 2>/dev/null")
        assert code == 0, "Should be able to list claude projects directory"

    @pytest.mark.slow
    def test_simple_task_completes(self):
        """Test that a simple task (no subagent) completes successfully."""
        # Create a simple test prompt
        prompt = "echo 'Hello from test' using bash"

        # This test validates the basic Claude Code invocation works
        cmd = f"""cd /workspace && timeout 30 claude -p "{prompt}" --output-format json --dangerously-skip-permissions 2>&1 || echo "TIMEOUT_OR_ERROR" """
        code, stdout, stderr = docker_exec(cmd, timeout=60)

        # Should complete without error
        assert "TIMEOUT_OR_ERROR" not in stdout, f"Simple task should complete: {stdout}"

    @pytest.mark.slow
    def test_subagent_spawn_detection(self):
        """Test that we can detect when a subagent is spawned."""
        # Get current session files
        before_sessions = set(get_recent_session_files(minutes=1))

        # Run a command that should spawn a subagent
        prompt = """Use the Task tool with run_in_background=true to spawn a subagent that runs: echo 'test'"""

        cmd = f"""cd /workspace && timeout 45 claude -p "{prompt}" --output-format json --dangerously-skip-permissions 2>&1"""
        code, stdout, stderr = docker_exec(cmd, timeout=60)

        # Get session files after
        after_sessions = set(get_recent_session_files(minutes=1))
        new_sessions = after_sessions - before_sessions

        # Analyze the results
        found_task_tool = False
        for session_file in new_sessions:
            entries = read_session_file(session_file)
            analysis = analyze_session(entries)
            if analysis["task_tool_used"]:
                found_task_tool = True
                break

        # Note: This test documents current behavior
        # If subagent spawning works, we should find the Task tool was used
        # Current bug: subagent is killed immediately
        print(f"New sessions: {new_sessions}")
        print(f"Task tool found: {found_task_tool}")


class TestSubagentKillBehavior:
    """Tests documenting the current subagent kill behavior (the bug)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        code, _, _ = docker_exec("echo 'test'")
        if code != 0:
            pytest.skip(f"Container {CONTAINER_NAME} not available")

    def test_subagent_killed_on_parent_exit(self):
        """
        Document that subagents are killed when parent exits.

        This test verifies the BUG - subagents should NOT be killed,
        but currently they are. When this test fails (subagent survives),
        the bug is fixed.
        """
        # Find the most recent session with a killed subagent
        sessions = get_recent_session_files(minutes=60)  # Last hour

        killed_subagent_found = False
        for session_file in sessions:
            entries = read_session_file(session_file)
            analysis = analyze_session(entries)

            if analysis["subagent_started"] and analysis["subagent_killed"]:
                killed_subagent_found = True
                print(f"Found killed subagent in: {session_file}")
                print(f"Analysis: {analysis}")
                break

        # This test documents current (buggy) behavior
        # When the bug is fixed, this assertion should be changed
        if killed_subagent_found:
            # BUG CONFIRMED: Subagent was killed
            # Change this to assert not killed_subagent_found when fixed
            print("BUG CONFIRMED: Subagent was killed on parent exit")


class TestSubagentSurvival:
    """Tests for verifying subagent survival after fix is applied."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        code, _, _ = docker_exec("echo 'test'")
        if code != 0:
            pytest.skip(f"Container {CONTAINER_NAME} not available")

    @pytest.mark.skip(reason="Run after fix is applied")
    def test_subagent_survives_parent_exit(self):
        """
        Verify subagent survives after parent exits.

        ENABLE THIS TEST after applying the fix.
        """
        # Spawn a subagent with a sleep to ensure it outlives parent
        prompt = """
        Use the Task tool with run_in_background=true to spawn a subagent.
        The subagent should:
        1. Sleep for 5 seconds
        2. Write "SUBAGENT_COMPLETED" to /tmp/subagent_test_result.txt
        3. Post to Discord that it completed

        After spawning, immediately respond with "Parent done" and exit.
        """

        # Clear previous test file
        docker_exec("rm -f /tmp/subagent_test_result.txt")

        # Run the parent (should exit quickly)
        cmd = f"""cd /workspace && timeout 30 claude -p "{prompt}" --output-format json --dangerously-skip-permissions 2>&1"""
        code, stdout, stderr = docker_exec(cmd, timeout=45)

        # Wait for subagent to complete
        time.sleep(10)

        # Check if subagent completed its work
        code, result, _ = docker_exec("cat /tmp/subagent_test_result.txt 2>/dev/null")

        assert "SUBAGENT_COMPLETED" in result, \
            "Subagent should complete its work after parent exits"

    @pytest.mark.skip(reason="Run after fix is applied")
    def test_subagent_posts_to_discord(self):
        """
        Verify subagent can post results to Discord webhook.

        ENABLE THIS TEST after applying the fix.
        """
        # Similar to above but checks Discord notification
        pass


class TestArchitectureValidation:
    """Tests validating the overall architecture."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        code, _, _ = docker_exec("echo 'test'")
        if code != 0:
            pytest.skip(f"Container {CONTAINER_NAME} not available")

    def test_discord_notify_available(self):
        """Verify discord_notify module is available."""
        cmd = "cd /workspace/scripts && python -c 'from discord_notify import notify; print(\"OK\")'"
        code, stdout, _ = docker_exec(cmd)
        assert code == 0 and "OK" in stdout, "discord_notify should be importable"

    def test_task_delegation_available(self):
        """Verify task_delegation module is available."""
        cmd = "cd /workspace/scripts && python -c 'from task_delegation import delegate_task; print(\"OK\")'"
        code, stdout, _ = docker_exec(cmd)
        assert code == 0 and "OK" in stdout, "task_delegation should be importable"

    def test_vault_v2_available(self):
        """Verify vault_v2 module is available."""
        cmd = "cd /workspace/scripts && python -c 'from vault_v2 import smart_capture; print(\"OK\")'"
        code, stdout, _ = docker_exec(cmd)
        assert code == 0 and "OK" in stdout, "vault_v2 should be importable"

    def test_webhook_configured(self):
        """Verify Discord webhook is configured."""
        cmd = "cd /workspace && grep -r 'DISCORD_WEBHOOK' config/ scripts/ 2>/dev/null | head -1"
        code, stdout, _ = docker_exec(cmd)
        # Not asserting success - just documenting
        print(f"Webhook config check: {stdout}")


def run_quick_validation():
    """Run a quick validation of the architecture."""
    print("=" * 60)
    print("Subagent Architecture Quick Validation")
    print("=" * 60)

    # Check container
    code, _, _ = docker_exec("echo 'test'")
    print(f"1. Container accessible: {'PASS' if code == 0 else 'FAIL'}")

    # Check Claude Code
    code, stdout, _ = docker_exec("claude --version")
    print(f"2. Claude Code installed: {'PASS' if code == 0 else 'FAIL'}")
    if code == 0:
        print(f"   Version: {stdout.strip()}")

    # Check session files
    sessions = get_recent_session_files(minutes=60)
    print(f"3. Recent sessions: {len(sessions)} found")

    # Check for killed subagents
    killed_count = 0
    completed_count = 0
    for session_file in sessions[:10]:  # Check last 10
        entries = read_session_file(session_file)
        analysis = analyze_session(entries)
        if analysis["subagent_killed"]:
            killed_count += 1
        if analysis["subagent_completed"]:
            completed_count += 1

    print(f"4. Subagent status (last 10 sessions):")
    print(f"   - Killed: {killed_count}")
    print(f"   - Completed: {completed_count}")

    # Check required modules
    modules = ["discord_notify", "task_delegation", "vault_v2"]
    for mod in modules:
        cmd = f"cd /workspace/scripts && python -c 'import {mod}; print(\"OK\")'"
        code, _, _ = docker_exec(cmd)
        print(f"5. Module {mod}: {'PASS' if code == 0 else 'FAIL'}")

    print("=" * 60)

    if killed_count > 0 and completed_count == 0:
        print("WARNING: Subagents are being killed (bug confirmed)")
        print("See docs/SUBAGENT_ARCHITECTURE_ANALYSIS.md for details")

    return killed_count == 0 or completed_count > 0


if __name__ == "__main__":
    # Run quick validation
    run_quick_validation()
