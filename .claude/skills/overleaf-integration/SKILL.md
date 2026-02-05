---
name: overleaf-integration
description: Create and manage Overleaf LaTeX documents. Use when transcribing handwritten work to LaTeX, creating academic documents, homework solutions, problem sets, or any LaTeX/Overleaf operations. Handles PDF/image to LaTeX conversion. Homework transcription workflow.
allowed-tools: Read, Write, Bash, Glob, Grep, Task, mcp__playwright__*
---

# Overleaf Integration & Homework Workflow

Create, manage, and sync Overleaf LaTeX documents. Full homework transcription pipeline.

## Quick Start

```bash
# Add CLI to PATH
export PATH="$PATH:/workspace/overleaf/bin"

# Common operations
overleaf list                     # List all projects
overleaf status                   # Check sync status
overleaf pull                     # Download from Overleaf
overleaf push                     # Push local changes
```

## Important Directories

**All Overleaf work happens in:**
```
/workspace/overleaf/projects/
```

Each project gets its own subdirectory:
```
projects/
├── hw5-solutions/
│   ├── main.tex
│   ├── .overleaf/       # Sync metadata
│   └── figures/
└── research-paper/
    ├── main.tex
    └── .overleaf/
```

---

## Homework Transcription Workflow

### When to Use

Trigger phrases:
- "This is my work for homework/problem set X"
- "Transcribe this to LaTeX"
- "Create solutions document for [class]"
- Any combination of: homework images + class name + request to create document

### Quick Reference

| Step | Action | Tool/Method |
|------|--------|-------------|
| 1. Receive images | Extract from Discord attachments | Parse `[ATTACHMENTS: ...]` |
| 2. Get problem set | Download from OneDrive | `OneDriveClient.download()` |
| 3. Transcribe | Claude vision on images | `homework_workflow.transcribe_images_to_latex()` |
| 4. Create local project | Save LaTeX + sources | `homework_workflow.create_project_directory()` |
| 5. Create Overleaf | Browser automation | Playwright MCP tools |
| 6. Download PDF | Get compiled document | Playwright MCP |
| 7. Upload to OneDrive | Save all files | `OneDriveClient.upload()` |

### Delegation Pattern (Recommended)

For homework tasks, **delegate the entire workflow** so you stay responsive:

```python
from task_delegation import delegate_task

task_id = delegate_task(
    description="Process CHEN5838 Problem Set 1 homework submission",
    context={
        "original_prompt": user_message,
        "user_instructions": "Box final answers",  # Extracted from user message
        "image_paths": ["/tmp/discord_attachments/page1.jpg"],
        "problem_set_source": "Desktop/CHEN5838/problem_sets/PS1.pdf",
        "class_name": "CHEN5838",
        "assignment": "PS1",
        "subject": "Chemical Engineering",
        "workflow": "homework"
    },
    discord_channel_id="DISCORD_CHANNEL_ID",
    priority=3
)

# Respond immediately:
f"On it! I've started processing your PS1 submission (task #{task_id})."
```

### Full Workflow (For Sub-Agent)

```python
from homework_workflow import HomeworkWorkflow

workflow = HomeworkWorkflow()
result = workflow.process(
    image_paths=["/tmp/discord_attachments/page1.jpg"],
    problem_set_path="Desktop/CHEN5838/problem_sets/PS1.pdf",
    output_folder="Desktop/CHEN5838/homeworks/PS1",
    project_name="CHEN5838 Problem Set 1 Solutions",
    subject="Chemical Engineering",
    user_instructions="Box final answers"
)
```

---

## Overleaf Operations

### API Operations (Fast - Do Directly)

```python
import sys
sys.path.insert(0, '/workspace/overleaf/scripts')
from overleaf_api import OverleafAPI, load_cookie

api = OverleafAPI(load_cookie())
projects = api.get_enriched_projects()
```

### Quick Reference

| Task | Command |
|------|---------|
| List projects | `overleaf list` |
| Find project ID | `overleaf list --filter "name"` |
| Link to project | `overleaf link <project_id>` |
| Download project | `overleaf pull` |
| Check changes | `overleaf status` |
| Push changes | `overleaf push` |
| Validate session | `python3 scripts/overleaf_api.py validate` |

### Sync Operations

For bidirectional sync, use the **overleaf-sync** skill or CLI:

```bash
# Link local directory to Overleaf project
cd /path/to/local/project
overleaf link 507f1f77bcf86cd799439011

# Pull from Overleaf
overleaf pull

# Edit files locally...
# Check what changed
overleaf status

# Push changes (generates Playwright steps)
overleaf push
```

---

## Write Operations (Playwright MCP)

Write operations require browser automation.

### Create New Project

1. Navigate: `browser_navigate` to https://www.overleaf.com/project
2. Click "New Project" button
3. Select "Blank Project"
4. Enter project name
5. Get project ID from URL

### Playwright Sequence for Project Creation

```
1. mcp__playwright__browser_navigate → https://www.overleaf.com/project
2. mcp__playwright__browser_snapshot → Get page state
3. mcp__playwright__browser_click → "New Project" button
4. mcp__playwright__browser_click → "Blank Project"
5. mcp__playwright__browser_type → Enter project name
6. mcp__playwright__browser_click → "Create"
7. mcp__playwright__browser_wait_for → time: 3
8. mcp__playwright__browser_press_key → "Control+a"
9. mcp__playwright__browser_type → Paste LaTeX content
10. mcp__playwright__browser_wait_for → time: 10 (compilation)
```

---

## LaTeX Templates

### Basic Article
```latex
\documentclass{article}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{geometry}
\geometry{margin=1in}

\title{Document Title}
\author{Student Name}
\date{\today}

\begin{document}
\maketitle

\section{Introduction}

\end{document}
```

### Problem Set
```latex
\documentclass{article}
\usepackage{amsmath,amssymb}
\usepackage{enumitem}

\begin{document}

\textbf{Problem 1.}
\begin{align}
    % solution here
\end{align}

\end{document}
```

---

## Session Management

Session cookie location: `/workspace/overleaf/.credentials`

If session expires:
1. Login to Overleaf in browser
2. Open DevTools (F12) → Application → Cookies
3. Copy `overleaf_session2` value
4. Update `.credentials` file

---

## Error Handling

| Error | Solution |
|-------|----------|
| "Session invalid" | Update session cookie |
| "Project not found" | Check project ID with `overleaf list` |
| "Not linked to Overleaf" | Run `overleaf link <id>` first |
| "Problem set not found" | Ask user for correct OneDrive path |
| "Transcription failed" | Try with fewer images |

---

## When User Says...

| Request | Action |
|---------|--------|
| "Create an Overleaf project" | Use Playwright MCP to create |
| "Transcribe this to LaTeX" | Delegate if complex, do directly if simple |
| "This is my homework for X" | Full homework workflow (delegate) |
| "List my Overleaf projects" | `overleaf list` |
| "Download my project" | `overleaf pull` |
| "Push my changes" | `overleaf push` |
| "Is my Overleaf session valid?" | `python3 scripts/overleaf_api.py validate` |

---

## OneDrive Paths

Common locations for the user's classes:
- `Desktop/CHEN5838/` - Chemical Engineering course
- `Desktop/PHYS1140/` - Physics TA materials

---

## Related Skills

- `/overleaf-sync` - Bidirectional sync with Overleaf (push/pull)
- `/task-delegation` - For delegating complex Overleaf tasks
- `/browser-automation` - Playwright MCP reference
