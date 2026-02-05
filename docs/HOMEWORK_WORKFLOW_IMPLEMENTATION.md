# PCP Homework Transcription Workflow - Implementation Plan

**Created:** 2026-01-14
**Status:** Planning

---

## Overview

A comprehensive workflow that enables the user to:
1. Take photos of handwritten homework
2. Send images to PCP via Discord
3. Have PCP read the problem set PDF from OneDrive
4. Create a professional LaTeX document with full solutions
5. Create an Overleaf project and compile to PDF
6. Save everything (PDF + original images) to a new OneDrive folder

---

## Architecture

```
[Discord: Images] ──┐
                    ├──> [PCP Agent] ──> [Claude Vision: Transcribe]
[OneDrive: Problem Set PDF] ─┘                    │
                                                  v
                                          [LaTeX Generation]
                                                  │
                                                  v
                                    [Overleaf: Create Project]
                                                  │
                                                  v
                                    [Overleaf: Download PDF]
                                                  │
                                                  v
                                    [OneDrive: Upload to folder]
                                    - Compiled PDF
                                    - Original images
```

---

## Components Required

### 1. OneDrive Upload Capability (NEW)
**File:** `/path/to/pcp/scripts/onedrive_rclone.py`

Current capabilities:
- ✅ list_files()
- ✅ download()
- ✅ download_dir()
- ✅ search()
- ✅ get_info()
- ❌ **upload() - NEEDS IMPLEMENTATION**
- ❌ **upload_dir() - NEEDS IMPLEMENTATION**
- ❌ **mkdir() - NEEDS IMPLEMENTATION**

### 2. Discord Image Ingestion
**Status:** Already works via `/tmp/discord_attachments/`

Images are automatically saved with message containing:
```
[ATTACHMENTS: [{"filename": "...", "path": "...", "content_type": "..."}]]
```

### 3. Enhanced Transcription
**File:** `/path/to/pcp/scripts/transcribe_to_overleaf.py`

Needs enhancement for:
- Multiple image input (multi-page handwritten work)
- Problem set PDF context integration
- More comprehensive LaTeX output

### 4. Overleaf Integration
**Current:** Read-only API works (list, download)
**Needed:** Browser automation via Playwright MCP for:
- Create new project
- Upload files
- Trigger compilation
- Download compiled PDF

### 5. Homework Workflow Orchestrator (NEW)
**File:** `/path/to/pcp/scripts/homework_workflow.py`

New unified script that orchestrates the full workflow.

---

## Implementation Details

### Step 1: Add OneDrive Upload Methods

```python
# In onedrive_rclone.py

def upload(self, local_path: str, remote_path: str) -> bool:
    """
    Upload a file to OneDrive.

    Args:
        local_path: Local file path
        remote_path: Destination path in OneDrive

    Returns:
        True if successful
    """
    dst = f"{self.remote}:{remote_path}"
    result = self._run_rclone(["copyto", local_path, dst], timeout=300)
    return result.returncode == 0

def upload_dir(self, local_path: str, remote_path: str) -> bool:
    """
    Upload a directory to OneDrive.

    Args:
        local_path: Local directory path
        remote_path: Destination path in OneDrive

    Returns:
        True if successful
    """
    dst = f"{self.remote}:{remote_path}"
    result = self._run_rclone(["copy", local_path, dst], timeout=600)
    return result.returncode == 0

def mkdir(self, path: str) -> bool:
    """
    Create a directory in OneDrive.

    Args:
        path: Directory path to create

    Returns:
        True if successful
    """
    dst = f"{self.remote}:{path}"
    result = self._run_rclone(["mkdir", dst])
    return result.returncode == 0
```

### Step 2: Create Homework Workflow Orchestrator

```python
# homework_workflow.py

"""
PCP Homework Transcription Workflow

Full workflow for transcribing handwritten homework:
1. Process images from Discord
2. Download problem set from OneDrive
3. Transcribe to comprehensive LaTeX
4. Create Overleaf project
5. Download compiled PDF
6. Upload everything to OneDrive

Usage:
    python homework_workflow.py process \
        --images /tmp/discord_attachments/hw1_*.jpg \
        --problem-set "Desktop/CHEN5838/problem_sets/PS1.pdf" \
        --output-folder "Desktop/CHEN5838/homeworks/PS1" \
        --project-name "CHEN5838 Problem Set 1"
"""

import os
import glob
import json
import shutil
from datetime import datetime
from typing import List, Dict, Any

from onedrive_rclone import OneDriveClient
from transcribe_to_overleaf import transcribe_to_latex, validate_latex


class HomeworkWorkflow:
    """Orchestrates the full homework transcription workflow."""

    def __init__(self):
        self.onedrive = OneDriveClient()
        self.temp_dir = "/tmp/pcp_homework"
        self.overleaf_projects = "/workspace/overleaf/projects"

    def process(
        self,
        image_paths: List[str],
        problem_set_path: str,
        output_folder: str,
        project_name: str,
        subject: str = "Chemical Engineering"
    ) -> Dict[str, Any]:
        """
        Run the complete homework workflow.

        Args:
            image_paths: List of paths to handwritten work images
            problem_set_path: OneDrive path to problem set PDF
            output_folder: OneDrive folder for output
            project_name: Name for the Overleaf project
            subject: Subject for transcription context

        Returns:
            Dict with workflow results
        """
        result = {
            "started_at": datetime.now().isoformat(),
            "stages": {},
            "success": False
        }

        try:
            # Stage 1: Setup
            os.makedirs(self.temp_dir, exist_ok=True)
            result["stages"]["setup"] = {"success": True}

            # Stage 2: Download problem set
            ps_local = os.path.join(self.temp_dir, "problem_set.pdf")
            if self.onedrive.download(problem_set_path, ps_local):
                result["stages"]["download_ps"] = {
                    "success": True,
                    "path": ps_local
                }
            else:
                raise Exception(f"Failed to download: {problem_set_path}")

            # Stage 3: Transcribe with context
            latex_result = self._transcribe_with_context(
                image_paths, ps_local, subject
            )
            result["stages"]["transcribe"] = latex_result

            if not latex_result.get("success"):
                raise Exception(f"Transcription failed: {latex_result.get('error')}")

            # Stage 4: Create local project
            project_dir = self._create_project(
                project_name,
                latex_result["latex_content"],
                image_paths
            )
            result["stages"]["create_project"] = {
                "success": True,
                "project_dir": project_dir
            }

            # Stage 5: Create Overleaf project (via Playwright)
            # This returns instructions for Playwright MCP
            overleaf_instructions = self._get_overleaf_instructions(
                project_name, project_dir
            )
            result["stages"]["overleaf"] = overleaf_instructions

            # Stage 6: Upload to OneDrive
            # (After Overleaf PDF is downloaded)
            upload_instructions = {
                "output_folder": output_folder,
                "files_to_upload": [
                    {"type": "pdf", "description": "Compiled PDF from Overleaf"},
                    {"type": "images", "paths": image_paths},
                    {"type": "latex", "path": os.path.join(project_dir, "main.tex")}
                ]
            }
            result["stages"]["upload"] = upload_instructions

            result["success"] = True
            result["completed_at"] = datetime.now().isoformat()

        except Exception as e:
            result["error"] = str(e)

        return result

    def _transcribe_with_context(
        self,
        image_paths: List[str],
        problem_set_path: str,
        subject: str
    ) -> Dict[str, Any]:
        """Transcribe handwritten work using problem set as context."""
        # Build comprehensive context from problem set
        # Claude will see both the images AND the problem set
        context = f"""
        This is homework for {subject}.
        The problem set PDF is provided for reference.
        Transcribe ALL work shown in the handwritten images.
        Match solutions to the corresponding problems from the PDF.
        """

        # If multiple images, combine them
        all_content = []
        for img_path in image_paths:
            result = transcribe_to_latex(
                img_path,
                context=context,
                subject=subject
            )
            if result.get("success"):
                all_content.append(result.get("latex_content", ""))

        # Combine into single document
        if all_content:
            return {
                "success": True,
                "latex_content": self._combine_latex(all_content, subject)
            }

        return {"success": False, "error": "No content transcribed"}

    def _combine_latex(self, contents: List[str], subject: str) -> str:
        """Combine multiple LaTeX fragments into one document."""
        # Extract body content from each document
        bodies = []
        for content in contents:
            # Extract between \begin{document} and \end{document}
            import re
            match = re.search(
                r'\\begin\{document\}(.*?)\\end\{document\}',
                content,
                re.DOTALL
            )
            if match:
                bodies.append(match.group(1).strip())

        combined_body = "\n\n\\newpage\n\n".join(bodies)

        return f"""\\documentclass[11pt]{{article}}
\\usepackage{{amsmath,amssymb,amsthm}}
\\usepackage{{geometry}}
\\usepackage{{graphicx}}
\\usepackage{{enumitem}}
\\geometry{{margin=1in}}

\\title{{{subject} - Homework Solutions}}
\\author{{Student Name}}
\\date{{\\today}}

\\begin{{document}}
\\maketitle

{combined_body}

\\end{{document}}
"""

    def _create_project(
        self,
        name: str,
        latex: str,
        images: List[str]
    ) -> str:
        """Create local Overleaf project directory."""
        from transcribe_to_overleaf import slugify

        project_slug = slugify(name)
        project_dir = os.path.join(self.overleaf_projects, project_slug)
        source_dir = os.path.join(project_dir, "source")

        os.makedirs(source_dir, exist_ok=True)

        # Write main.tex
        with open(os.path.join(project_dir, "main.tex"), "w") as f:
            f.write(latex)

        # Copy source images
        for img in images:
            if os.path.exists(img):
                shutil.copy(img, source_dir)

        return project_dir

    def _get_overleaf_instructions(
        self,
        name: str,
        project_dir: str
    ) -> Dict:
        """Generate instructions for Playwright MCP to create Overleaf project."""
        return {
            "action": "create_overleaf_project",
            "steps": [
                {
                    "tool": "mcp__playwright__browser_navigate",
                    "url": "https://www.overleaf.com/project"
                },
                {
                    "tool": "mcp__playwright__browser_click",
                    "element": "New Project button"
                },
                {
                    "tool": "mcp__playwright__browser_click",
                    "element": "Blank Project"
                },
                {
                    "tool": "mcp__playwright__browser_type",
                    "element": "Project name input",
                    "text": name
                },
                {
                    "tool": "mcp__playwright__browser_click",
                    "element": "Create button"
                },
                {
                    "note": "Copy main.tex content to editor"
                },
                {
                    "note": "Wait for compilation"
                },
                {
                    "tool": "mcp__playwright__browser_click",
                    "element": "Download PDF button"
                }
            ],
            "local_project_dir": project_dir,
            "main_tex_path": os.path.join(project_dir, "main.tex")
        }
```

### Step 3: Create Homework Skill

**File:** `/path/to/pcp/.claude/skills/homework-workflow/SKILL.md`

```yaml
---
name: homework-workflow
description: Transcribe handwritten homework to LaTeX, create Overleaf project, save to OneDrive
allowed-tools: Read, Write, Bash, Glob, Grep, Task, mcp__playwright__*
---
```

### Step 4: Implement Scheduled Briefs

**Cron Configuration:**

```bash
# Add to crontab -e

# Daily brief at 8:00 AM
0 8 * * * /path/to/pcp/scripts/scheduled_brief.sh daily >> /path/to/pcp/.agent/cron.log 2>&1

# Weekly summary on Sundays at 9:00 AM
0 9 * * 0 /path/to/pcp/scripts/scheduled_brief.sh weekly >> /path/to/pcp/.agent/cron.log 2>&1

# End-of-day digest at 6:00 PM
0 18 * * * /path/to/pcp/scripts/scheduled_brief.sh eod >> /path/to/pcp/.agent/cron.log 2>&1
```

**New Script:** `/path/to/pcp/scripts/scheduled_brief.sh`

```bash
#!/bin/bash
# Scheduled Brief Generator with Discord Notification

SCRIPTS_DIR="/path/to/pcp/scripts"
DISCORD_CHANNEL="DISCORD_CHANNEL_ID"  # PCP channel

BRIEF_TYPE="${1:-daily}"

# Generate brief
BRIEF=$(python3 "$SCRIPTS_DIR/brief.py" --$BRIEF_TYPE 2>&1)

if [ $? -eq 0 ]; then
    # Send to Discord via webhook or bot
    python3 "$SCRIPTS_DIR/discord_notify.py" --channel "$DISCORD_CHANNEL" --message "$BRIEF"
    echo "[$(date)] $BRIEF_TYPE brief sent successfully"
else
    echo "[$(date)] Error generating $BRIEF_TYPE brief: $BRIEF"
    exit 1
fi
```

---

## Testing Plan

### Test 1: OneDrive Upload
```bash
# Create test file
echo "test" > /tmp/test.txt

# Test upload
python3 onedrive_rclone.py upload /tmp/test.txt "Documents/test.txt"

# Verify
python3 onedrive_rclone.py ls "Documents"
```

### Test 2: Full Homework Workflow
1. Manually place test images in `/tmp/discord_attachments/`
2. Run workflow with test problem set
3. Verify Overleaf project creation
4. Verify OneDrive folder creation

### Test 3: Scheduled Briefs
```bash
# Test brief generation
/path/to/pcp/scripts/scheduled_brief.sh daily

# Verify cron installation
crontab -l | grep brief
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `scripts/onedrive_rclone.py` | MODIFY | Add upload(), upload_dir(), mkdir() |
| `scripts/homework_workflow.py` | CREATE | Workflow orchestrator |
| `scripts/scheduled_brief.sh` | CREATE | Cron-triggered brief script |
| `scripts/discord_notify.py` | CREATE | Discord notification helper |
| `.claude/skills/homework-workflow/SKILL.md` | CREATE | Homework skill definition |

---

## Usage Examples

### Example 1: Process Homework

**User message (Discord):**
```
Hey, this is my work for CHEN5838 Problem Set 1.
[ATTACHMENTS: [{"path": "/tmp/discord_attachments/ps1_p1.jpg"}, {"path": "/tmp/discord_attachments/ps1_p2.jpg"}]]
Go ahead and check in the CHEN5838 folder for problem_set_1.pdf.
Create a full solutions document and save it to homeworks/PS1/.
```

**Agent action:**
```python
from homework_workflow import HomeworkWorkflow

workflow = HomeworkWorkflow()
result = workflow.process(
    image_paths=[
        "/tmp/discord_attachments/ps1_p1.jpg",
        "/tmp/discord_attachments/ps1_p2.jpg"
    ],
    problem_set_path="Desktop/CHEN5838/problem_sets/PS1.pdf",
    output_folder="Desktop/CHEN5838/homeworks/PS1",
    project_name="CHEN5838 Problem Set 1"
)
```

### Example 2: Scheduled Brief

**Automatic at 8:00 AM:**
```
# PCP Brief - Tuesday, January 14, 2026

## OVERDUE TASKS
  - Submit CHEN5838 PS1 (was due: 2026-01-13)

## Upcoming Deadlines
  - PHYS1140 grading (due: 2026-01-16)
  - MXene paper draft (due: 2026-01-20)

## Activity Summary
  - 12 captures in last 24h
  - 3 pending tasks
  - 2 tasks completed
  - Activity is UP from previous day
...
```

---

## Next Steps

1. [x] Create this implementation plan
2. [ ] Implement OneDrive upload methods
3. [ ] Create homework_workflow.py
4. [ ] Create scheduled_brief.sh with Discord notification
5. [ ] Create homework-workflow skill
6. [ ] Test each component individually
7. [ ] Test full end-to-end flow
8. [ ] Document in CLAUDE.md

---

*Plan created by PCP - 2026-01-14*
