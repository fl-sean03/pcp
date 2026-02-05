#!/usr/bin/env python3
"""
Overleaf Helper Functions for PCP Workflows

Bridges homework_workflow.py with Overleaf integration.
Uses overleaf_api.py for reads and provides Playwright instructions for writes.

Usage:
    from overleaf_helpers import (
        validate_overleaf_session,
        get_overleaf_api,
        find_or_create_project,
        get_playwright_create_project_steps,
        get_playwright_download_pdf_steps
    )
"""

import os
import sys
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

# Path detection - container vs host
if os.path.exists("/workspace/CLAUDE.md"):
    # Inside container
    OVERLEAF_DIR = "/workspace/overleaf"
    OVERLEAF_SCRIPTS = "/workspace/overleaf/scripts"
else:
    # On host
    OVERLEAF_DIR = "/workspace/overleaf"
    OVERLEAF_SCRIPTS = "/workspace/overleaf/scripts"

# Add overleaf scripts to path
sys.path.insert(0, OVERLEAF_SCRIPTS)

# Import from overleaf-integration
try:
    from overleaf_api import (
        OverleafAPI,
        load_cookie,
        SessionExpiredError,
        OverleafAPIError
    )
    OVERLEAF_API_AVAILABLE = True
except ImportError:
    OVERLEAF_API_AVAILABLE = False


def validate_overleaf_session() -> Dict[str, Any]:
    """
    Check if Overleaf session is valid.

    Returns:
        Dict with valid, message, and project_count
    """
    if not OVERLEAF_API_AVAILABLE:
        return {
            "valid": False,
            "message": "overleaf_api module not available",
            "project_count": 0
        }

    try:
        cookie = load_cookie()
        if not cookie:
            return {
                "valid": False,
                "message": "No session cookie found. Check .credentials or config/session_cookie.txt",
                "project_count": 0
            }

        api = OverleafAPI(cookie, validate=True)
        projects = api.get_projects()
        return {
            "valid": True,
            "message": "Session is valid",
            "project_count": len(projects)
        }
    except SessionExpiredError:
        return {
            "valid": False,
            "message": "Session cookie expired. Please refresh from browser.",
            "project_count": 0
        }
    except OverleafAPIError as e:
        return {
            "valid": False,
            "message": f"API error: {e}",
            "project_count": 0
        }


def get_overleaf_api() -> Optional['OverleafAPI']:
    """
    Get authenticated Overleaf API instance.

    Returns:
        OverleafAPI instance or None if unavailable
    """
    if not OVERLEAF_API_AVAILABLE:
        return None

    try:
        cookie = load_cookie()
        if not cookie:
            return None
        return OverleafAPI(cookie, validate=False)  # Skip validation for speed
    except Exception:
        return None


def find_project_by_name(name: str) -> Optional[Dict]:
    """
    Find an Overleaf project by name.

    Args:
        name: Project name (partial match)

    Returns:
        Project dict or None
    """
    api = get_overleaf_api()
    if not api:
        return None

    try:
        matches = api.find_project(name)
        return matches[0] if matches else None
    except Exception:
        return None


def list_projects() -> List[Dict]:
    """
    List all Overleaf projects.

    Returns:
        List of project dicts
    """
    api = get_overleaf_api()
    if not api:
        return []

    try:
        return api.get_enriched_projects()
    except Exception:
        return []


def download_project_sources(project_id: str, output_dir: str) -> Dict[str, Any]:
    """
    Download Overleaf project source files.

    Args:
        project_id: Overleaf project ID
        output_dir: Local directory to save to

    Returns:
        Dict with success and file info
    """
    api = get_overleaf_api()
    if not api:
        return {"success": False, "error": "API not available"}

    try:
        result = api.download_project(project_id, output_dir)
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Playwright MCP Instructions
# These generate step-by-step instructions for the worker agent to execute
# =============================================================================

def get_playwright_create_tag_steps(tag_name: str) -> Dict[str, Any]:
    """
    Generate Playwright MCP steps to create a new tag in Overleaf.

    Args:
        tag_name: Name for the new tag (e.g., "CHEN5838")

    Returns:
        Dict with steps to create tag via Playwright
    """
    return {
        "success": True,
        "action": "create_overleaf_tag",
        "tag_name": tag_name,
        "steps": [
            {
                "step": 1,
                "action": "navigate",
                "description": "Go to Overleaf dashboard",
                "tool": "mcp__playwright__browser_navigate",
                "params": {"url": "https://www.overleaf.com/project"}
            },
            {
                "step": 2,
                "action": "wait",
                "description": "Wait for dashboard to load",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 2}
            },
            {
                "step": 3,
                "action": "snapshot",
                "description": "Get page state to find sidebar",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 4,
                "action": "click",
                "description": "Click 'Create new tag' or '+' button in tags section",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "New Tag button or Create new tag link", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 5,
                "action": "snapshot",
                "description": "Get tag creation dialog",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 6,
                "action": "type",
                "description": f"Enter tag name: {tag_name}",
                "tool": "mcp__playwright__browser_type",
                "params": {
                    "element": "Tag name input field",
                    "ref": "FIND_IN_SNAPSHOT",
                    "text": tag_name
                }
            },
            {
                "step": 7,
                "action": "click",
                "description": "Click 'Create' button",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "Create button", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 8,
                "action": "wait",
                "description": "Wait for tag to be created",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 1}
            },
            {
                "step": 9,
                "action": "snapshot",
                "description": "Verify tag appears in sidebar",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            }
        ],
        "notes": [
            f"This will create a new tag named '{tag_name}'",
            "Check if tag already exists before calling (use api.tag_exists())",
            "After creation, verify tag appears in the sidebar"
        ]
    }


def get_playwright_assign_tag_steps(project_id: str, tag_name: str) -> Dict[str, Any]:
    """
    Generate Playwright MCP steps to assign a tag to an Overleaf project.

    Args:
        project_id: The project ID to tag
        tag_name: Name of the tag to assign

    Returns:
        Dict with steps to assign tag via Playwright
    """
    return {
        "success": True,
        "action": "assign_tag_to_project",
        "project_id": project_id,
        "tag_name": tag_name,
        "steps": [
            {
                "step": 1,
                "action": "navigate",
                "description": "Go to Overleaf dashboard",
                "tool": "mcp__playwright__browser_navigate",
                "params": {"url": "https://www.overleaf.com/project"}
            },
            {
                "step": 2,
                "action": "wait",
                "description": "Wait for dashboard to load",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 2}
            },
            {
                "step": 3,
                "action": "snapshot",
                "description": "Get project list",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 4,
                "action": "hover",
                "description": "Hover over the project row to reveal options",
                "tool": "mcp__playwright__browser_hover",
                "params": {"element": f"Project row for project", "ref": "FIND_PROJECT_IN_SNAPSHOT"}
            },
            {
                "step": 5,
                "action": "click",
                "description": "Click the three-dot menu (more options) on the project",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "More options menu (three dots)", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 6,
                "action": "snapshot",
                "description": "Get context menu",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 7,
                "action": "click",
                "description": "Click 'Add to tag' or similar option",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "Add to tag option", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 8,
                "action": "snapshot",
                "description": "Get tag selection dialog",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 9,
                "action": "click",
                "description": f"Select tag: {tag_name}",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": f"Tag checkbox for '{tag_name}'", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 10,
                "action": "click",
                "description": "Confirm or close the dialog",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "Apply/Close button", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 11,
                "action": "snapshot",
                "description": "Verify tag is assigned",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            }
        ],
        "notes": [
            f"This will assign tag '{tag_name}' to project {project_id}",
            "Tag must exist before assigning - create it first if needed",
            "The project should appear in the dashboard for selection",
            "Look for 'Tags', 'Add to folder', or similar menu option"
        ]
    }


def get_playwright_create_project_with_upload_steps(
    project_name: str,
    zip_file_path: str,
    tag_name: str = None
) -> Dict[str, Any]:
    """
    Generate Playwright MCP steps to create an Overleaf project using ZIP UPLOAD.

    This is the PREFERRED method - more robust than typing content into the editor.

    IMPORTANT: Overleaf's "Upload project" feature REQUIRES a ZIP file, not raw .tex files.

    Workflow:
        1. Create a directory with main.tex and any other files
        2. ZIP the directory contents: cd project_dir && zip -r ../project.zip .
        3. Copy ZIP to $HOME/ (Playwright MCP only allows files in home dir)
        4. Call this function with the ZIP path

    Args:
        project_name: Name for the new project (Overleaf may extract from \\title{} in LaTeX)
        zip_file_path: Path to ZIP file containing main.tex (MUST be in $HOME/)
        tag_name: Optional tag to assign to the project after creation

    Returns:
        Dict with steps for creating project via ZIP upload
    """
    if not zip_file_path:
        return {"success": False, "error": "zip_file_path is required for ZIP upload approach"}

    import os
    if not os.path.exists(zip_file_path):
        return {"success": False, "error": f"ZIP file not found: {zip_file_path}"}

    if not zip_file_path.endswith('.zip'):
        return {"success": False, "error": "File must be a .zip file"}

    if not zip_file_path.startswith('/home/'):
        return {"success": False, "error": "ZIP file must be in $HOME/ for Playwright MCP access"}

    steps = [
        # Step 1-8: Create the blank project (same as before)
        {
            "step": 1,
            "action": "navigate",
            "description": "Go to Overleaf dashboard",
            "tool": "mcp__playwright__browser_navigate",
            "params": {"url": "https://www.overleaf.com/project"}
        },
        {
            "step": 2,
            "action": "wait",
            "description": "Wait for dashboard to load",
            "tool": "mcp__playwright__browser_wait_for",
            "params": {"time": 2}
        },
        {
            "step": 3,
            "action": "snapshot",
            "description": "Get page state",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": 4,
            "action": "click",
            "description": "Click 'New Project' button",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": "New Project button", "ref": "FIND_IN_SNAPSHOT"}
        },
        {
            "step": 5,
            "action": "snapshot",
            "description": "Get dropdown menu",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": 6,
            "action": "click",
            "description": "Select 'Blank Project'",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": "Blank Project option", "ref": "FIND_IN_SNAPSHOT"}
        },
        {
            "step": 7,
            "action": "snapshot",
            "description": "Get project name dialog",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": 8,
            "action": "type",
            "description": f"Enter project name: {project_name}",
            "tool": "mcp__playwright__browser_type",
            "params": {
                "element": "Project Name input",
                "ref": "FIND_IN_SNAPSHOT",
                "text": project_name
            }
        },
        {
            "step": 9,
            "action": "click",
            "description": "Click 'Create' button",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": "Create button", "ref": "FIND_IN_SNAPSHOT"}
        },
        {
            "step": 10,
            "action": "wait",
            "description": "Wait for editor to load",
            "tool": "mcp__playwright__browser_wait_for",
            "params": {"time": 3}
        },
        # Step 11-16: Upload main.tex to replace default content
        {
            "step": 11,
            "action": "snapshot",
            "description": "Get editor state - look for upload button",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": 12,
            "action": "click",
            "description": "Click upload button (folder icon with arrow, or 'Upload' menu)",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": "Upload button or menu", "ref": "FIND_IN_SNAPSHOT"}
        },
        {
            "step": 13,
            "action": "snapshot",
            "description": "Get upload dialog/modal",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": 14,
            "action": "upload",
            "description": f"Upload main.tex file: {main_tex_path}",
            "tool": "mcp__playwright__browser_file_upload",
            "params": {"paths": [main_tex_path]}
        },
        {
            "step": 15,
            "action": "wait",
            "description": "Wait for upload processing",
            "tool": "mcp__playwright__browser_wait_for",
            "params": {"time": 2}
        },
        {
            "step": 16,
            "action": "snapshot",
            "description": "Check for overwrite confirmation",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": 17,
            "action": "click_if_present",
            "description": "Click 'Overwrite' if file already exists dialog appears",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": "Overwrite button", "ref": "FIND_IN_SNAPSHOT"},
            "optional": True,
            "note": "Only click if overwrite confirmation appears"
        },
        {
            "step": 18,
            "action": "wait",
            "description": "Wait for compilation to complete",
            "tool": "mcp__playwright__browser_wait_for",
            "params": {"time": 8}
        },
        {
            "step": 19,
            "action": "snapshot",
            "description": "Verify compilation succeeded (check for PDF preview)",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": 20,
            "action": "get_url",
            "description": "Get the project URL to extract project ID",
            "note": "URL will be like https://www.overleaf.com/project/XXXXXX - extract the ID"
        }
    ]

    result = {
        "success": True,
        "action": "create_overleaf_project_with_upload",
        "project_name": project_name,
        "main_tex_path": main_tex_path,
        "steps": steps,
        "notes": [
            "This uses FILE UPLOAD instead of typing - more robust",
            "After step 16, check if overwrite dialog appears for main.tex",
            "If overwrite dialog appears, click 'Overwrite' to replace default content",
            "If no dialog, the upload succeeded and compilation should start",
            "The project URL contains the project ID (after /project/)"
        ]
    }

    if tag_name:
        result["tag_to_assign"] = tag_name
        result["notes"].append(f"After creation, use assign_tag_steps to add tag '{tag_name}'")

    return result


def get_playwright_create_project_steps(
    project_name: str,
    latex_content: str = None,
    main_tex_path: str = None
) -> Dict[str, Any]:
    """
    Generate Playwright MCP steps to create an Overleaf project.

    DEPRECATED: Prefer get_playwright_create_project_with_upload_steps() for file upload.
    This older method uses paste/type which can be unreliable for large content.

    Args:
        project_name: Name for the new project
        latex_content: LaTeX content to paste (or None to read from file)
        main_tex_path: Path to main.tex file (if latex_content is None)

    Returns:
        Dict with steps and context
    """
    # Read content if path provided
    if not latex_content and main_tex_path:
        try:
            with open(main_tex_path, 'r') as f:
                latex_content = f.read()
        except Exception as e:
            return {"success": False, "error": f"Cannot read {main_tex_path}: {e}"}

    return {
        "success": True,
        "action": "create_overleaf_project",
        "project_name": project_name,
        "deprecated": True,
        "prefer": "get_playwright_create_project_with_upload_steps",
        "steps": [
            {
                "step": 1,
                "action": "navigate",
                "description": "Go to Overleaf dashboard",
                "tool": "mcp__playwright__browser_navigate",
                "params": {"url": "https://www.overleaf.com/project"}
            },
            {
                "step": 2,
                "action": "snapshot",
                "description": "Get page state to find elements",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 3,
                "action": "click",
                "description": "Click 'New Project' button",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "New Project button", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 4,
                "action": "snapshot",
                "description": "Get dropdown menu",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 5,
                "action": "click",
                "description": "Select 'Blank Project'",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "Blank Project option", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 6,
                "action": "snapshot",
                "description": "Get project name dialog",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 7,
                "action": "type",
                "description": f"Enter project name: {project_name}",
                "tool": "mcp__playwright__browser_type",
                "params": {
                    "element": "Project Name input",
                    "ref": "FIND_IN_SNAPSHOT",
                    "text": project_name
                }
            },
            {
                "step": 8,
                "action": "click",
                "description": "Click 'Create' button",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "Create button", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 9,
                "action": "wait",
                "description": "Wait for editor to load",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 3}
            },
            {
                "step": 10,
                "action": "snapshot",
                "description": "Get editor state",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 11,
                "action": "select_all",
                "description": "Select all text in editor (Ctrl+A)",
                "tool": "mcp__playwright__browser_press_key",
                "params": {"key": "Control+a"}
            },
            {
                "step": 12,
                "action": "paste_content",
                "description": "The worker should now paste the LaTeX content. Use browser_type with the editor element.",
                "note": "IMPORTANT: The LaTeX content is provided below. Paste it into the editor.",
                "latex_content_preview": latex_content[:500] + "..." if latex_content and len(latex_content) > 500 else latex_content
            },
            {
                "step": 13,
                "action": "wait",
                "description": "Wait for compilation to complete",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 10}
            },
            {
                "step": 14,
                "action": "snapshot",
                "description": "Verify compilation succeeded (check for PDF preview)",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            }
        ],
        "latex_content": latex_content,
        "notes": [
            "DEPRECATED: This uses paste which can be unreliable",
            "PREFER: get_playwright_create_project_with_upload_steps() for file upload",
            "After step 10, find the code editor element in the snapshot",
            "Use browser_type to paste the full latex_content into the editor",
            "Watch for compilation errors in the snapshot after waiting",
            "The project URL will contain the new project ID"
        ]
    }


def get_playwright_download_pdf_steps(project_url: str = None, output_path: str = None) -> Dict[str, Any]:
    """
    Generate Playwright MCP steps to download compiled PDF from Overleaf.

    Args:
        project_url: URL of the Overleaf project (or None if already on project page)
        output_path: Where to save the PDF

    Returns:
        Dict with steps
    """
    steps = []
    step_num = 1

    if project_url:
        steps.append({
            "step": step_num,
            "action": "navigate",
            "description": "Go to project",
            "tool": "mcp__playwright__browser_navigate",
            "params": {"url": project_url}
        })
        step_num += 1

        steps.append({
            "step": step_num,
            "action": "wait",
            "description": "Wait for project to load and compile",
            "tool": "mcp__playwright__browser_wait_for",
            "params": {"time": 5}
        })
        step_num += 1

    steps.extend([
        {
            "step": step_num,
            "action": "snapshot",
            "description": "Get page state",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": step_num + 1,
            "action": "click",
            "description": "Click Menu button (hamburger icon or 'Menu')",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": "Menu button", "ref": "FIND_IN_SNAPSHOT"}
        },
        {
            "step": step_num + 2,
            "action": "snapshot",
            "description": "Get menu options",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": step_num + 3,
            "action": "click",
            "description": "Click 'Download PDF' option",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": "Download PDF", "ref": "FIND_IN_SNAPSHOT"}
        },
        {
            "step": step_num + 4,
            "action": "wait",
            "description": "Wait for download to start",
            "tool": "mcp__playwright__browser_wait_for",
            "params": {"time": 3}
        }
    ])

    return {
        "success": True,
        "action": "download_pdf",
        "steps": steps,
        "output_path": output_path,
        "notes": [
            "The PDF will download to the browser's download directory",
            "Check /tmp/ or ~/Downloads for the file",
            "File will be named after the project",
            f"Move the downloaded PDF to: {output_path}" if output_path else "Move to desired location"
        ]
    }


def get_playwright_upload_file_steps(project_url: str, file_path: str) -> Dict[str, Any]:
    """
    Generate Playwright MCP steps to upload a file to Overleaf project.

    Args:
        project_url: URL of the Overleaf project
        file_path: Local path to file to upload

    Returns:
        Dict with steps
    """
    return {
        "success": True,
        "action": "upload_file",
        "project_url": project_url,
        "file_path": file_path,
        "steps": [
            {
                "step": 1,
                "action": "navigate",
                "description": "Go to project",
                "tool": "mcp__playwright__browser_navigate",
                "params": {"url": project_url}
            },
            {
                "step": 2,
                "action": "wait",
                "description": "Wait for editor to load",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 3}
            },
            {
                "step": 3,
                "action": "snapshot",
                "description": "Get page state",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 4,
                "action": "click",
                "description": "Click upload button (usually folder icon with arrow)",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "Upload button", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 5,
                "action": "snapshot",
                "description": "Get upload dialog",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 6,
                "action": "upload",
                "description": f"Upload file: {file_path}",
                "tool": "mcp__playwright__browser_file_upload",
                "params": {"paths": [file_path]}
            },
            {
                "step": 7,
                "action": "wait",
                "description": "Wait for upload to complete",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 2}
            },
            {
                "step": 8,
                "action": "snapshot",
                "description": "Verify file appears in project",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            }
        ]
    }


def get_playwright_folder_creation_steps(project_url: str, folder_path: str) -> Dict[str, Any]:
    """
    Generate Playwright MCP steps to create a folder in Overleaf.

    Must be called BEFORE uploading files to that folder.

    Args:
        project_url: URL of the Overleaf project
        folder_path: Path of folder to create (e.g., "figures" or "sections/chapter1")

    Returns:
        Dict with steps to create folder via Playwright
    """
    return {
        "success": True,
        "action": "create_folder",
        "project_url": project_url,
        "folder_path": folder_path,
        "steps": [
            {
                "step": 1,
                "action": "navigate",
                "description": "Go to project",
                "tool": "mcp__playwright__browser_navigate",
                "params": {"url": project_url}
            },
            {
                "step": 2,
                "action": "wait",
                "description": "Wait for editor to load",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 3}
            },
            {
                "step": 3,
                "action": "snapshot",
                "description": "Get file tree",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 4,
                "action": "click",
                "description": "Click New Folder button (+ menu or folder icon with plus)",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "New Folder button or + menu", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 5,
                "action": "snapshot",
                "description": "Get folder name dialog",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 6,
                "action": "type",
                "description": f"Enter folder name: {folder_path}",
                "tool": "mcp__playwright__browser_type",
                "params": {
                    "element": "Folder name input",
                    "ref": "FIND_IN_SNAPSHOT",
                    "text": folder_path
                }
            },
            {
                "step": 7,
                "action": "click",
                "description": "Click Create button",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "Create button", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 8,
                "action": "wait",
                "description": "Wait for folder creation",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 1}
            },
            {
                "step": 9,
                "action": "snapshot",
                "description": "Verify folder appears in file tree",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            }
        ],
        "notes": [
            f"This will create folder '{folder_path}' in the project",
            "Create parent folders first if they don't exist",
            "After creation, verify folder appears in the file tree"
        ]
    }


def get_playwright_file_delete_steps(project_url: str, file_path: str) -> Dict[str, Any]:
    """
    Generate Playwright MCP steps to delete a file from Overleaf.

    WARNING: This is a destructive operation. Always confirm with user first.

    Args:
        project_url: URL of the Overleaf project
        file_path: Path of file to delete (e.g., "old_file.tex" or "figures/old.png")

    Returns:
        Dict with steps to delete file via Playwright
    """
    return {
        "success": True,
        "action": "delete_file",
        "project_url": project_url,
        "file_path": file_path,
        "warning": f"This will permanently delete '{file_path}' from Overleaf",
        "steps": [
            {
                "step": 1,
                "action": "navigate",
                "description": "Go to project",
                "tool": "mcp__playwright__browser_navigate",
                "params": {"url": project_url}
            },
            {
                "step": 2,
                "action": "wait",
                "description": "Wait for editor to load",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 3}
            },
            {
                "step": 3,
                "action": "snapshot",
                "description": "Get file tree",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 4,
                "action": "right_click",
                "description": f"Right-click file: {file_path}",
                "tool": "mcp__playwright__browser_click",
                "params": {
                    "element": f"File '{file_path}' in file tree",
                    "ref": "FIND_IN_SNAPSHOT",
                    "button": "right"
                }
            },
            {
                "step": 5,
                "action": "snapshot",
                "description": "Get context menu",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 6,
                "action": "click",
                "description": "Click Delete option",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "Delete option", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 7,
                "action": "snapshot",
                "description": "Get confirmation dialog",
                "tool": "mcp__playwright__browser_snapshot",
                "params": {}
            },
            {
                "step": 8,
                "action": "click",
                "description": "Confirm deletion",
                "tool": "mcp__playwright__browser_click",
                "params": {"element": "Confirm/Delete button", "ref": "FIND_IN_SNAPSHOT"}
            },
            {
                "step": 9,
                "action": "wait",
                "description": "Wait for deletion",
                "tool": "mcp__playwright__browser_wait_for",
                "params": {"time": 1}
            }
        ],
        "notes": [
            f"WARNING: This permanently deletes '{file_path}'",
            "Always confirm with user before executing",
            "Deletion cannot be undone (no trash in Overleaf)",
            "Consider using --no-delete flag in sync to skip deletions"
        ]
    }


def get_playwright_upload_file_to_folder_steps(
    project_url: str,
    file_path: str,
    target_folder: str = None
) -> Dict[str, Any]:
    """
    Generate Playwright MCP steps to upload a file to a specific folder in Overleaf.

    IMPORTANT: file_path must be in $HOME/ due to Playwright MCP restrictions.

    Args:
        project_url: URL of the Overleaf project
        file_path: Local path to file to upload (MUST be in $HOME/)
        target_folder: Optional folder to upload to (select folder before upload)

    Returns:
        Dict with steps to upload file via Playwright
    """
    if not file_path.startswith('/home/'):
        return {
            "success": False,
            "error": "File must be in $HOME/ for Playwright MCP access",
            "hint": f"Copy file to $HOME/tmp/ first: cp {file_path} $HOME/tmp/"
        }

    steps = [
        {
            "step": 1,
            "action": "navigate",
            "description": "Go to project",
            "tool": "mcp__playwright__browser_navigate",
            "params": {"url": project_url}
        },
        {
            "step": 2,
            "action": "wait",
            "description": "Wait for editor to load",
            "tool": "mcp__playwright__browser_wait_for",
            "params": {"time": 3}
        },
        {
            "step": 3,
            "action": "snapshot",
            "description": "Get file tree",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        }
    ]

    step_num = 4

    # If target folder specified, select it first
    if target_folder and target_folder != ".":
        steps.append({
            "step": step_num,
            "action": "click",
            "description": f"Select folder: {target_folder}",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": f"Folder '{target_folder}' in file tree", "ref": "FIND_IN_SNAPSHOT"}
        })
        step_num += 1
        steps.append({
            "step": step_num,
            "action": "snapshot",
            "description": "Get updated state",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        })
        step_num += 1

    steps.extend([
        {
            "step": step_num,
            "action": "click",
            "description": "Click Upload button (folder icon with arrow)",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": "Upload button", "ref": "FIND_IN_SNAPSHOT"}
        },
        {
            "step": step_num + 1,
            "action": "snapshot",
            "description": "Get upload dialog",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": step_num + 2,
            "action": "upload",
            "description": f"Upload file: {file_path}",
            "tool": "mcp__playwright__browser_file_upload",
            "params": {"paths": [file_path]}
        },
        {
            "step": step_num + 3,
            "action": "wait",
            "description": "Wait for upload",
            "tool": "mcp__playwright__browser_wait_for",
            "params": {"time": 2}
        },
        {
            "step": step_num + 4,
            "action": "snapshot",
            "description": "Check for overwrite dialog",
            "tool": "mcp__playwright__browser_snapshot",
            "params": {}
        },
        {
            "step": step_num + 5,
            "action": "click_if_present",
            "description": "Click Overwrite if file exists",
            "tool": "mcp__playwright__browser_click",
            "params": {"element": "Overwrite button", "ref": "FIND_IF_EXISTS"},
            "optional": True
        },
        {
            "step": step_num + 6,
            "action": "wait",
            "description": "Wait for completion",
            "tool": "mcp__playwright__browser_wait_for",
            "params": {"time": 1}
        }
    ])

    return {
        "success": True,
        "action": "upload_file_to_folder",
        "project_url": project_url,
        "file_path": file_path,
        "target_folder": target_folder,
        "steps": steps,
        "notes": [
            f"Uploading {file_path}" + (f" to folder '{target_folder}'" if target_folder else ""),
            "File must be in $HOME/ for Playwright access",
            "If file exists, overwrite dialog will appear",
            "Wait for file to appear in tree after upload"
        ]
    }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Overleaf Helper Functions")
    parser.add_argument("command", choices=["validate", "list", "find", "create-steps", "download-steps"],
                       help="Command to run")
    parser.add_argument("--name", help="Project name for find/create")
    parser.add_argument("--url", help="Project URL for download")
    parser.add_argument("--tex", help="Path to main.tex for create")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "validate":
        result = validate_overleaf_session()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Valid: {result['valid']}")
            print(f"Message: {result['message']}")
            if result['project_count']:
                print(f"Projects: {result['project_count']}")

    elif args.command == "list":
        projects = list_projects()
        if args.json:
            print(json.dumps(projects, indent=2))
        else:
            for p in projects[:10]:
                print(f"{p['name']} ({p['id']})")
            if len(projects) > 10:
                print(f"... and {len(projects) - 10} more")

    elif args.command == "find":
        if not args.name:
            print("Error: --name required")
            sys.exit(1)
        project = find_project_by_name(args.name)
        if project:
            print(json.dumps(project, indent=2))
        else:
            print(f"No project found matching: {args.name}")

    elif args.command == "create-steps":
        if not args.name:
            print("Error: --name required")
            sys.exit(1)
        steps = get_playwright_create_project_steps(args.name, main_tex_path=args.tex)
        print(json.dumps(steps, indent=2))

    elif args.command == "download-steps":
        steps = get_playwright_download_pdf_steps(args.url)
        print(json.dumps(steps, indent=2))
