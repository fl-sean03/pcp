#!/usr/bin/env python3
"""
Verify Homework Flow Components

Tests all components of the homework transcription workflow to ensure
they're properly configured and accessible.

Run this to verify the system is ready:
    python verify_homework_flow.py
"""

import os
import sys
import json

# Add scripts directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check(name: str, condition: bool, message: str = ""):
    """Print check result."""
    status = "✓" if condition else "✗"
    msg = f" - {message}" if message else ""
    print(f"  {status} {name}{msg}")
    return condition


def main():
    print("\n" + "=" * 60)
    print(" Homework Workflow Verification")
    print("=" * 60)

    all_passed = True

    # 1. Check environment
    print("\n1. Environment")
    print("-" * 40)
    inside_container = os.path.exists("/workspace/CLAUDE.md")
    check("Environment detected", True,
          "Container" if inside_container else "Host")

    # 2. Check imports
    print("\n2. Module Imports")
    print("-" * 40)

    try:
        from homework_workflow import HomeworkWorkflow, transcribe_images_to_latex
        check("homework_workflow", True)
    except ImportError as e:
        check("homework_workflow", False, str(e))
        all_passed = False

    try:
        from onedrive_rclone import OneDriveClient
        check("onedrive_rclone", True)
    except ImportError as e:
        check("onedrive_rclone", False, str(e))
        all_passed = False

    try:
        from task_delegation import delegate_task, get_task
        check("task_delegation", True)
    except ImportError as e:
        check("task_delegation", False, str(e))
        all_passed = False

    try:
        from overleaf_helpers import (
            validate_overleaf_session,
            list_projects,
            get_playwright_create_project_steps
        )
        check("overleaf_helpers", True)
    except ImportError as e:
        check("overleaf_helpers", False, str(e))
        all_passed = False

    # 3. Check OneDrive
    print("\n3. OneDrive Connection")
    print("-" * 40)
    try:
        from onedrive_rclone import OneDriveClient
        client = OneDriveClient()
        dirs = client.list_dirs("")
        if dirs:
            check("OneDrive accessible", True, f"Found {len(dirs)} root directories")
        else:
            check("OneDrive accessible", False, "No directories found")
            all_passed = False
    except Exception as e:
        check("OneDrive accessible", False, str(e))
        all_passed = False

    # 4. Check Overleaf
    print("\n4. Overleaf Session")
    print("-" * 40)
    try:
        from overleaf_helpers import validate_overleaf_session
        session = validate_overleaf_session()
        if session['valid']:
            check("Overleaf session valid", True,
                  f"{session['project_count']} projects accessible")
        else:
            check("Overleaf session valid", False, session['message'])
            all_passed = False
    except Exception as e:
        check("Overleaf session valid", False, str(e))
        all_passed = False

    # 5. Check directories
    print("\n5. Directory Structure")
    print("-" * 40)

    if inside_container:
        paths = [
            "/workspace/scripts",
            "/workspace/vault",
            "/workspace/overleaf",
            "/workspace/overleaf/projects",
            "/workspace/overleaf/config",
            "/tmp/discord_attachments"
        ]
    else:
        paths = [
            "/workspace/scripts",
            os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault"),
            "/workspace/overleaf",
            "/workspace/overleaf/projects",
            "/tmp/discord_attachments"
        ]

    for path in paths:
        exists = os.path.exists(path)
        check(path, exists, "exists" if exists else "MISSING")
        if not exists and "discord_attachments" not in path:
            all_passed = False

    # 6. Check task delegation DB
    print("\n6. Task Delegation Database")
    print("-" * 40)
    try:
        from task_delegation import get_pending_count, list_tasks
        pending = get_pending_count()
        check("Database accessible", True, f"{pending} pending tasks")
    except Exception as e:
        check("Database accessible", False, str(e))
        all_passed = False

    # 7. Check Playwright MCP
    print("\n7. Playwright MCP")
    print("-" * 40)
    # Check if playwright is configured by searching config files
    playwright_configured = False
    claude_config_paths = [
        "/home/pcp/.claude.json",
        "/workspace/.claude.json",
        os.path.expanduser("~/.claude.json"),
    ]
    for config_path in claude_config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    content = f.read()
                if "playwright" in content.lower():
                    playwright_configured = True
                    break
            except:
                pass
    check("Playwright MCP configured", playwright_configured,
          "Found in config" if playwright_configured else "Not found - run: claude mcp add playwright")

    # 8. Summary
    print("\n" + "=" * 60)
    if all_passed:
        print(" All checks passed! System is ready for homework workflow.")
    else:
        print(" Some checks failed. Review issues above.")
    print("=" * 60 + "\n")

    # Return hints for fixing issues
    if not all_passed:
        print("Troubleshooting hints:")
        print("-" * 40)
        print("- Overleaf session expired: Login to Overleaf in browser, copy session cookie")
        print("- OneDrive not accessible: Check rclone config with 'rclone config'")
        print("- Missing directories: Check docker volume mounts")
        print("- Playwright not configured: Run 'claude mcp add playwright'")
        print()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
