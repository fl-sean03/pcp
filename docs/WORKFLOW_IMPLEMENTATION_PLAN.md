# PCP Workflow Implementation Plan

**Version:** 2.0
**Created:** 2026-01-13
**Updated:** 2026-01-13
**Status:** Planning → Implementation

---

## Executive Summary

This plan transforms PCP from a feature-complete but unused system into an active external brain with a killer workflow.

**The Vision:**
```
Handwritten task sheet (photo)
    → PCP extracts and organizes tasks
    → Connects to OneDrive for source materials
    → Creates Overleaf document
    → Transcribes handwritten work to LaTeX
    → Updates via Discord throughout
    → All while the user continues chatting
```

**Key Architecture Decision:** Dual-agent system with task delegation
- **Main Agent:** Always responsive, handles conversation + quick tasks
- **Worker Agent:** Full Claude Code session for complex, long-running tasks

**Timeline:** 2-3 focused implementation sessions

---

## Architecture: Dual-Agent Task Delegation

### The Problem with Single-Agent

```
❌ Single Agent (Blocking):
User: "Transcribe my homework to Overleaf"
PCP: [blocked for 5 minutes doing the task]
User: "Hey, what's my schedule today?"
[no response - agent busy]
```

### The Solution: Main Agent + Worker Agent

```
✅ Dual Agent (Non-Blocking):
User: "Transcribe my homework to Overleaf"
PCP: "On it! I've started the transcription. I'll notify you when done."
User: "What's my schedule today?"
PCP: [responds immediately with schedule]
[5 minutes later]
PCP: "Done! Your Overleaf project is ready: [link]"
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DISCORD #pcp                                 │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ @mention
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PCP MAIN AGENT (Conversational)                   │
│                                                                      │
│  ALWAYS RESPONSIVE - Never blocks on long tasks                     │
│                                                                      │
│  Quick Operations (do directly):                                    │
│  ├── smart_capture() - Store information                            │
│  ├── smart_search() - Find information                              │
│  ├── daily_brief() - Generate brief                                 │
│  ├── get_tasks() - List tasks                                       │
│  ├── get_person() - Lookup person                                   │
│  └── Any operation < 30 seconds                                     │
│                                                                      │
│  Complex Operations (delegate to worker):                           │
│  ├── Transcribe handwritten → LaTeX → Overleaf                      │
│  ├── Process folder of PDFs                                         │
│  ├── Multi-step workflows                                           │
│  └── Any operation > 30 seconds                                     │
│                                                                      │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ create_delegated_task()
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TASK QUEUE (SQLite)                             │
│                                                                      │
│  Table: delegated_tasks                                             │
│  ├── id, task_type, prompt (natural language)                       │
│  ├── context (JSON: files, references, preferences)                 │
│  ├── status: pending → claimed → running → completed/failed         │
│  ├── discord_channel_id, discord_user_id                            │
│  ├── created_at, claimed_at, completed_at                           │
│  ├── result (JSON), error                                           │
│  └── worker_session_id                                              │
│                                                                      │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ worker polls every 10s
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 PCP WORKER AGENT (Full Claude Code Session)          │
│                                                                      │
│  NOT a Python script - Full Claude Code with all capabilities:      │
│  ├── Claude reasoning and planning                                  │
│  ├── All PCP scripts and tools                                      │
│  ├── Playwright MCP for browser automation                          │
│  ├── Error handling and recovery                                    │
│  └── Adaptive execution                                             │
│                                                                      │
│  Workflow:                                                          │
│  1. Poll for pending tasks                                          │
│  2. Claim task (set status=claimed, worker_session_id)              │
│  3. Execute task using full Claude capabilities                     │
│  4. Update result/error in database                                 │
│  5. Send Discord notification via webhook                           │
│  6. Return to polling                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DISCORD WEBHOOK NOTIFICATION                      │
│                                                                      │
│  "✅ Task completed: Transcribe HW5 to Overleaf                     │
│   - Overleaf project: https://www.overleaf.com/project/xyz          │
│   - 12 problems transcribed                                          │
│   - Source: OneDrive/Problem_Sets/HW5/work.pdf"                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Task Classification: Direct vs Delegated

| Operation | Type | Reason |
|-----------|------|--------|
| `smart_capture()` | Direct | < 5 seconds |
| `smart_search()` | Direct | < 5 seconds |
| `daily_brief()` | Direct | < 10 seconds |
| `get_tasks()` | Direct | < 1 second |
| `unified_search()` | Direct | < 5 seconds |
| Image → extract tasks | Direct | < 30 seconds (Claude vision) |
| Transcribe to LaTeX | **Delegated** | 1-5 minutes |
| Create Overleaf project + upload | **Delegated** | 1-3 minutes |
| Process OneDrive folder | **Delegated** | Variable, could be long |
| Bulk PDF summarization | **Delegated** | Variable |
| Multi-step research | **Delegated** | Variable |

### Why Worker Must Be Full Claude Code (Not Python Script)

A Python worker script can only execute pre-defined logic. A Claude Code worker can:

1. **Reason about the task** - Understand what's actually needed
2. **Adapt to errors** - Try alternative approaches when things fail
3. **Use all tools** - Playwright MCP, file operations, web search
4. **Handle ambiguity** - Make intelligent decisions
5. **Chain operations** - Multi-step workflows without pre-programming

**Example:** "Transcribe my homework to Overleaf"
- Python script: Fixed steps, fails if any step unexpected
- Claude worker: Reads image, figures out structure, generates appropriate LaTeX, handles compilation errors, creates project with right template

---

## File Organization

### Overleaf Projects Directory

All Overleaf-related work happens in:
```
/path/to/workspace/overleaf-integration/projects/
```

This directory already exists and is the standard location for:
- Downloaded Overleaf projects
- Generated LaTeX files before upload
- Work-in-progress transcriptions
- Project templates

**Structure:**
```
/path/to/workspace/overleaf-integration/
├── projects/                      # ALL Overleaf work happens here
│   ├── hip2025-report/           # Existing project
│   │   └── main.tex
│   ├── hw5-solutions/            # New project from transcription
│   │   ├── main.tex
│   │   ├── source/               # Original images/PDFs
│   │   └── .sync_manifest.json
│   └── [project-name]/           # Future projects
├── scripts/
│   └── overleaf_api.py           # API client (will be symlinked to PCP)
├── config/
│   └── session_cookie.txt        # Overleaf authentication
└── .sync_manifest.json           # Global sync tracking
```

### PCP Directory Structure

```
/path/to/pcp/
├── scripts/
│   ├── vault_v2.py               # Core capture/search
│   ├── brief.py                  # Brief generation
│   ├── task_delegation.py        # NEW: Task queue management
│   ├── worker_loop.py            # NEW: Worker orchestration
│   └── overleaf_api.py           # Symlink → overleaf-integration
├── vault/
│   └── vault.db                  # SQLite database
├── .claude/
│   └── skills/
│       ├── overleaf-integration/ # NEW: Overleaf skill
│       └── task-delegation/      # NEW: Delegation skill
└── worker/                       # NEW: Worker agent workspace
    ├── WORKER_CLAUDE.md          # Worker-specific instructions
    ├── current_task.json         # Current task being processed
    └── logs/                     # Worker execution logs
```

### Cross-Repository Integration

```
PCP Container                     Host Filesystem
─────────────────                 ─────────────────
/workspace/                   →   /path/to/pcp/
/workspace/overleaf/          →   /path/to/workspace/overleaf-integration/projects/
```

Both main agent and worker agent have access to the same Overleaf projects directory.

---

## 1. Current State

### 1.1 What's Running
| Component | Status | Notes |
|-----------|--------|-------|
| pcp-agent container | ✅ Healthy | Up 18+ hours |
| agent-gateway | ✅ Healthy | Routes Discord → PCP |
| Discord bot | ✅ Running | #pcp channel configured |
| SQLite database | ✅ Working | Minimal data (2 captures) |

### 1.2 Implemented Features (67 Stories Complete)
- Smart capture with entity extraction
- Unified search across all sources
- Knowledge base with decision tracking
- Commitment auto-detection
- Daily/weekly/EOD briefs
- Relationship intelligence
- Project health monitoring
- 11 Claude Code skills
- Pattern detection
- Email processing (needs OAuth)
- OneDrive integration (needs OAuth)
- Twitter integration (needs Playwright MCP)

### 1.3 Database State
```
Captures: 2
People: 1
Projects: 24
Tasks: 1
Knowledge: 3
```
**Assessment:** System is implemented but effectively unused.

---

## 2. Target State

### 2.1 Core Workflow: Task Sheet to Overleaf

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DISCORD #pcp                                 │
│  User uploads photo of handwritten task sheet                       │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PCP AGENT                                       │
│  1. Receives image via Discord attachment                           │
│  2. OCR + Vision analysis extracts tasks                            │
│  3. Creates structured task list in vault                           │
│  4. Posts organized tasks back to Discord                           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKGROUND TASK QUEUE                             │
│  User says: "Now take my work from OneDrive/Problem_Sets/HW5        │
│              and create an Overleaf doc with the LaTeX transcription"│
│                                                                      │
│  PCP responds: "On it. I'll update you when done."                  │
│                                                                      │
│  [the user continues chatting about other things]                       │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌─────────────────────┐         ┌─────────────────────┐
│     ONEDRIVE        │         │     OVERLEAF        │
│  - Fetch PDF/images │         │  - Create project   │
│  - Download locally │         │  - Upload template  │
│  - Extract content  │         │  - Add transcribed  │
└─────────┬───────────┘         │    LaTeX content    │
          │                     └─────────┬───────────┘
          │                               │
          └───────────┬───────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DISCORD NOTIFICATION                              │
│  "Done! Your problem set is transcribed:                            │
│   - Overleaf: https://www.overleaf.com/project/xyz                  │
│   - 15 problems transcribed                                          │
│   - Source: OneDrive/Problem_Sets/HW5/work.pdf"                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Supporting Workflows

**Workflow A: Quick Task Capture**
```
User: [uploads photo of whiteboard/notes]
PCP: Extracted 7 items:
     - [ ] Review API design doc (deadline: Friday)
     - [ ] Follow up with John about budget
     - [ ] ...
     Created 3 tasks, 2 commitments, linked to Project: MatterStack
```

**Workflow B: Daily Brief with Context**
```
User: "What's my day look like?"
PCP: [generates brief with]
     - Overdue commitments
     - Tasks due today
     - Stale relationships
     - Project health
     - Recent captures needing attention
```

**Workflow C: Background Document Processing**
```
User: "Process all the PDFs in OneDrive/Research/Papers and summarize them"
PCP: "Starting background task. I'll notify you when complete."
[continues conversation]
PCP: "Done! Processed 12 PDFs. Key findings: ..."
```

---

## 3. Gap Analysis

### 3.1 Critical Gaps (Must Fix)

| Gap | Impact | Current State | Required State |
|-----|--------|---------------|----------------|
| Discord attachment handling | 🔴 Blocks image workflow | Bot ignores file attachments | Bot extracts files, passes to PCP |
| Overleaf not connected | 🔴 Blocks transcription | Separate repo, not in PCP | Scripts in PCP, skill created |
| No background tasks | 🔴 Blocks async workflows | Synchronous only | Task queue + worker |
| OneDrive OAuth | 🟡 Blocks file access | Code exists, not configured | OAuth configured |

### 3.2 Secondary Gaps

| Gap | Impact | Notes |
|-----|--------|-------|
| LaTeX transcription workflow | 🟡 Medium | Claude can do it, needs orchestration |
| Discord progress updates | 🟡 Medium | Need webhook for background task updates |
| Error handling/retry | 🟢 Low | Current error handling is basic |

### 3.3 What's NOT a Gap
- Core PCP features (capture, search, briefs) - all working
- AgentGate routing - working
- SQLite persistence - working
- Claude Code skills - all created

---

## 4. Implementation Phases

### Phase 0: Validation & Seeding (30 minutes)
**Goal:** Verify existing system works, seed basic context

#### 0.1 Verify Discord → PCP Flow
```bash
# Test from Discord #pcp channel
@AgentBot "Remember: I'm testing the PCP system"

# Expected: PCP responds, capture created in database
```

#### 0.2 Verify Core Scripts Work
```bash
# In pcp-agent container
docker exec -it pcp-agent bash

# Test smart capture
python3 scripts/vault_v2.py capture "Test capture with John about API design"

# Test search
python3 scripts/vault_v2.py search "API"

# Test brief
python3 scripts/brief.py --daily
```

#### 0.3 Seed Foundation Data
Via Discord #pcp:
```
"Remember these are my active projects: PCP (personal AI system),
Alpha-Trader (autonomous trading), MatterStack (computational chemistry),
and my academic coursework"

"Key people: [your collaborators]"

"I prefer: concise responses, systematic organization,
LaTeX for academic work, markdown for notes"
```

#### 0.4 Validation Checklist
- [ ] Message to #pcp gets response
- [ ] Capture appears in database
- [ ] Search returns results
- [ ] Brief generates without errors
- [ ] Entities extracted correctly

---

### Phase 1: Discord Attachment Handling (2-3 hours)
**Goal:** Discord bot receives images/files and passes them to PCP

#### 1.1 Modify Discord Bot

**File:** `/srv/agentops/services/agent-gateway/adapters/discord/bot.py`

**Changes needed:**
```python
# In on_message handler, detect attachments
@bot.event
async def on_message(message: discord.Message):
    # ... existing code ...

    # NEW: Handle attachments
    attachments_info = []
    if message.attachments:
        for attachment in message.attachments:
            # Download attachment to temp location
            file_path = f"/tmp/discord_attachments/{message.id}_{attachment.filename}"
            await attachment.save(file_path)
            attachments_info.append({
                "filename": attachment.filename,
                "path": file_path,
                "content_type": attachment.content_type,
                "size": attachment.size
            })

    # Pass attachments info to agent router
    if attachments_info:
        content = f"{content}\n\n[ATTACHMENTS: {json.dumps(attachments_info)}]"
```

#### 1.2 Update Agent Router

**File:** `/srv/agentops/services/agent-gateway/adapters/discord/agent_router.py`

Mount temp directory in docker-compose for attachment access.

#### 1.3 Handle Attachments in PCP

**File:** `/path/to/pcp/scripts/vault_v2.py`

Add attachment detection in smart_capture:
```python
def smart_capture(content: str, attachments: List[dict] = None):
    """
    Enhanced capture that handles attachments.
    """
    # Detect [ATTACHMENTS: ...] in content
    attachment_match = re.search(r'\[ATTACHMENTS: (.+?)\]', content)
    if attachment_match:
        attachments = json.loads(attachment_match.group(1))
        content = re.sub(r'\[ATTACHMENTS: .+?\]', '', content).strip()

    if attachments:
        for att in attachments:
            # Process each attachment via file_processor
            from file_processor import ingest_file
            result = ingest_file(att['path'], context=content)
            # Link to capture
```

#### 1.4 Validation Checklist
- [ ] Upload image to Discord #pcp
- [ ] Bot acknowledges receipt
- [ ] Image saved to temp location
- [ ] PCP processes image via file_processor
- [ ] OCR text extracted and stored
- [ ] Tasks auto-created if detected

---

### Phase 2: Overleaf Integration (2-3 hours)
**Goal:** PCP can create Overleaf projects and upload content

#### 2.1 Port Overleaf Scripts to PCP

```bash
# Copy scripts
cp /path/to/workspace/overleaf-integration/scripts/overleaf_api.py \
   /path/to/pcp/scripts/

# Copy config (if needed)
cp /path/to/workspace/overleaf-integration/config/session_cookie.txt \
   /path/to/pcp/config/
```

#### 2.2 Create Overleaf Skill

Based on Claude Code skills best practices:
- **Model-invoked**: Skills are discovered via `description` field
- **Progressive disclosure**: Keep SKILL.md under 500 lines, use reference files
- **Trigger keywords**: Include words users naturally say

**File:** `/path/to/pcp/.claude/skills/overleaf-integration/SKILL.md`

```markdown
---
name: overleaf-integration
description: Create and manage Overleaf LaTeX documents. Use when transcribing handwritten work to LaTeX, creating academic documents, homework solutions, problem sets, or any LaTeX/Overleaf operations. Handles PDF/image to LaTeX conversion.
allowed-tools: Read, Write, Bash, Glob, Grep
---

# Overleaf Integration

Create, manage, and sync Overleaf LaTeX documents.

## Important Directories

**All Overleaf work happens in:**
```
/path/to/workspace/overleaf-integration/projects/
```

Each project gets its own subdirectory:
```
projects/
├── hw5-solutions/
│   ├── main.tex
│   ├── source/       # Original images/PDFs
│   └── figures/
└── research-paper/
    └── main.tex
```

## Quick Reference

| Task | Method |
|------|--------|
| List projects | `python3 overleaf_api.py list` |
| Download project | `python3 overleaf_api.py download <id> --output <dir>` |
| Validate session | `python3 overleaf_api.py validate` |
| Search by tag | `python3 overleaf_api.py tags` |

## Complex Operations → Delegate

For operations that take more than 30 seconds (transcription, project creation with content), **delegate to worker agent**:

```python
from task_delegation import delegate_task

task_id = delegate_task(
    description="Transcribe /path/to/hw5.pdf to LaTeX and create Overleaf project 'HW5 Solutions'",
    context={"files": ["/path/to/hw5.pdf"], "subject": "Math 301"},
    discord_channel_id="DISCORD_CHANNEL_ID"
)
# Respond immediately: "Started task #{task_id}, I'll notify you when done."
```

## Read Operations (Fast - Do Directly)

### List Projects
```python
from overleaf_api import OverleafAPI
api = OverleafAPI()
projects = api.list_projects()
```

### Download Project
```bash
python3 scripts/overleaf_api.py download 69669a15e090dead4603cc97 \
    --output /path/to/workspace/overleaf-integration/projects/my-project/
```

### Check Session
```python
api = OverleafAPI()
valid = api.validate_session()
if not valid:
    print("Session expired - check config/session_cookie.txt")
```

## Write Operations (Slow - Use Playwright MCP)

Write operations require browser automation:

### Create New Project
1. Navigate: `browser_navigate` to https://www.overleaf.com/project
2. Click "New Project" button
3. Select template
4. Enter project name
5. Get project ID from URL

### Upload File to Project
1. Navigate to project
2. Click upload button
3. Use file upload tool

## Transcription Workflow

For complex transcription (handwritten → LaTeX → Overleaf):

1. **If quick check** (< 30s): Do directly
2. **If full transcription**: Delegate to worker

### Direct transcription (small/simple):
```python
# Read image with Claude vision
# Generate LaTeX
latex = """
\\documentclass{article}
\\usepackage{amsmath}
\\begin{document}
[transcribed content]
\\end{document}
"""
# Write to project directory
with open("/path/to/workspace/overleaf-integration/projects/hw5/main.tex", "w") as f:
    f.write(latex)
```

### Delegated transcription (complex):
```python
delegate_task(
    description="Transcribe handwritten calculus work to LaTeX...",
    context={...}
)
```

## LaTeX Templates

Common templates for academic work:

### Basic Article
```latex
\\documentclass{article}
\\usepackage{amsmath,amssymb,amsthm}
\\usepackage{geometry}
\\geometry{margin=1in}

\\title{Document Title}
\\author{Student Name}
\\date{\\today}

\\begin{document}
\\maketitle

\\section{Introduction}

\\end{document}
```

### Problem Set
```latex
\\documentclass{article}
\\usepackage{amsmath,amssymb}
\\usepackage{enumitem}

\\begin{document}

\\textbf{Problem 1.}
\\begin{align}
    % solution here
\\end{align}

\\end{document}
```

## Session Management

Session cookie location: `/path/to/workspace/overleaf-integration/config/session_cookie.txt`

If session expires:
1. Login to Overleaf in browser
2. Extract `overleaf_session2` cookie
3. Update `session_cookie.txt`

## Error Handling

| Error | Solution |
|-------|----------|
| "Session invalid" | Update session cookie |
| "Project not found" | Check project ID with `list` |
| "Rate limited" | Wait and retry |
| "Browser timeout" | Increase Playwright timeout |

## Related Skills

- `/task-delegation` - For delegating complex Overleaf tasks
- `/vault-operations` - For capturing Overleaf-related notes
```

#### 2.3 Create Transcription Workflow Script

**File:** `/path/to/pcp/scripts/transcribe_to_overleaf.py`

```python
#!/usr/bin/env python3
"""
Transcribe handwritten work to Overleaf LaTeX document.

Workflow:
1. Read source (image/PDF) with Claude vision
2. Generate LaTeX from handwritten content
3. Create Overleaf project
4. Upload LaTeX content
5. Return project URL
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any

from overleaf_api import OverleafAPI
from file_processor import extract_text_from_image, extract_text_from_pdf


def transcribe_to_latex(source_path: str, context: str = "") -> str:
    """
    Use Claude to transcribe handwritten work to LaTeX.
    """
    # Determine file type
    ext = os.path.splitext(source_path)[1].lower()

    prompt = f"""Transcribe this handwritten mathematical/academic work to LaTeX.

Context: {context}

Requirements:
1. Use proper LaTeX math environments (equation, align, etc.)
2. Preserve the structure (problem numbers, parts)
3. Include all work shown, not just answers
4. Use standard LaTeX packages (amsmath, amssymb)
5. Format cleanly with proper spacing

Return ONLY the LaTeX content (no markdown code blocks).
Start with \\documentclass{{article}} and end with \\end{{document}}.
"""

    # Call Claude with the image/PDF
    cmd = [
        "claude", "-p", prompt,
        "--image", source_path,
        "--output-format", "text",
        "--max-turns", "1"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.stdout.strip()


def create_overleaf_document(
    name: str,
    latex_content: str,
    source_info: str = ""
) -> Dict[str, Any]:
    """
    Create Overleaf project with transcribed content.
    """
    api = OverleafAPI()

    # Validate session
    if not api.validate_session():
        return {"success": False, "error": "Overleaf session invalid"}

    # Create project
    # Note: This requires Playwright MCP for creation
    # For now, return instructions

    return {
        "success": True,
        "latex_content": latex_content,
        "suggested_name": name,
        "source": source_info,
        "instructions": "Use Playwright MCP to create project and upload content"
    }


def full_transcription_workflow(
    source_path: str,
    project_name: str,
    context: str = ""
) -> Dict[str, Any]:
    """
    Complete workflow: source → LaTeX → Overleaf
    """
    results = {
        "started_at": datetime.now().isoformat(),
        "source": source_path,
        "project_name": project_name
    }

    # Step 1: Transcribe to LaTeX
    try:
        latex = transcribe_to_latex(source_path, context)
        results["latex_generated"] = True
        results["latex_preview"] = latex[:500] + "..." if len(latex) > 500 else latex
    except Exception as e:
        results["latex_generated"] = False
        results["error"] = f"Transcription failed: {e}"
        return results

    # Step 2: Create Overleaf document
    try:
        overleaf_result = create_overleaf_document(
            project_name,
            latex,
            source_path
        )
        results["overleaf"] = overleaf_result
    except Exception as e:
        results["overleaf"] = {"success": False, "error": str(e)}

    results["completed_at"] = datetime.now().isoformat()
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transcribe handwritten work to Overleaf")
    parser.add_argument("source", help="Source file (image or PDF)")
    parser.add_argument("--name", "-n", required=True, help="Project name")
    parser.add_argument("--context", "-c", default="", help="Additional context")

    args = parser.parse_args()

    result = full_transcription_workflow(args.source, args.name, args.context)
    print(json.dumps(result, indent=2))
```

#### 2.4 Validation Checklist
- [ ] overleaf_api.py works in PCP container
- [ ] Session validation succeeds
- [ ] Can list existing projects
- [ ] transcribe_to_latex generates valid LaTeX
- [ ] Skill is recognized by Claude Code
- [ ] End-to-end: image → LaTeX → Overleaf project

---

### Phase 3: OneDrive OAuth Setup (1-2 hours)
**Goal:** PCP can access OneDrive files

#### 3.1 Azure App Registration

1. Go to https://portal.azure.com
2. Azure Active Directory → App registrations → New registration
3. Name: "PCP Integration"
4. Redirect URI: http://localhost:8080/callback
5. Note: client_id, tenant_id
6. Certificates & secrets → New client secret
7. API permissions:
   - Files.Read
   - Files.Read.All
   - offline_access

#### 3.2 Configure PCP

```bash
# In pcp-agent container
docker exec -it pcp-agent bash

# Configure Microsoft Graph
python3 scripts/microsoft_graph.py --configure \
    --client-id YOUR_CLIENT_ID \
    --client-secret YOUR_CLIENT_SECRET \
    --tenant-id YOUR_TENANT_ID

# Get auth URL and complete OAuth flow
python3 scripts/microsoft_graph.py --auth-url
# Visit URL, authorize, paste code back

python3 scripts/microsoft_graph.py --authenticate CODE_FROM_URL
```

#### 3.3 Test OneDrive Access

```python
from onedrive import OneDriveClient

client = OneDriveClient()
files = client.get_recent_files()
print(files)

# Search for specific folder
results = client.search("Problem_Sets")
```

#### 3.4 Validation Checklist
- [ ] OAuth tokens stored in database
- [ ] Can list OneDrive files
- [ ] Can download files to local cache
- [ ] Can search OneDrive by name
- [ ] Token refresh works automatically

---

### Phase 4: Dual-Agent Task Delegation (4-5 hours)
**Goal:** Main agent stays responsive while worker agent handles complex tasks

This is the **most critical architectural piece** - getting this right enables the entire workflow.

#### 4.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    MAIN AGENT (Always Responsive)                │
│                                                                  │
│  Receives Discord message → Classifies task:                    │
│  ├── Quick task? → Execute directly, respond                    │
│  └── Complex task? → Delegate to worker, respond "on it"        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ delegate_task()
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DELEGATED_TASKS TABLE                       │
│                                                                  │
│  - id, task_description (natural language prompt)               │
│  - context (JSON: files, preferences, related captures)         │
│  - status: pending → claimed → running → completed/failed       │
│  - discord_channel_id, discord_user_id                          │
│  - worker_session_id (which worker claimed it)                  │
│  - result (JSON), error, created_at, completed_at               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ worker polls every 10s
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              WORKER AGENT (Full Claude Code Session)             │
│                                                                  │
│  NOT a Python script - Full Claude with:                        │
│  ├── Reasoning and planning                                     │
│  ├── All PCP tools and scripts                                  │
│  ├── Playwright MCP for Overleaf                                │
│  ├── Error recovery and adaptation                              │
│  └── Natural language task understanding                        │
│                                                                  │
│  Loop:                                                          │
│  1. Check for pending tasks                                     │
│  2. Claim task, execute with full capabilities                  │
│  3. Write result to database                                    │
│  4. Send Discord notification                                   │
│  5. Return to step 1                                            │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.2 Why Full Claude Code Worker (Not Python)

| Approach | Pros | Cons |
|----------|------|------|
| Python Worker | Simple, predictable | Can't reason, can't adapt, limited to pre-programmed steps |
| Claude Code Worker | Full reasoning, uses all tools, handles unexpected situations | More complex setup |

**Example: "Transcribe my homework to Overleaf"**

Python worker would need:
```python
def transcribe_to_overleaf(source_path, project_name):
    # Fixed steps - fails if anything unexpected
    text = ocr(source_path)
    latex = convert_to_latex(text)  # What template? What packages?
    project_id = create_overleaf_project(project_name)  # What if name taken?
    upload_file(project_id, latex)  # What if upload fails?
    return project_id
```

Claude Code worker:
```
"Transcribe the handwritten work in /path/to/hw5.pdf to LaTeX and
create an Overleaf project called 'HW5 Solutions'. The work is for
Math 301 and includes integration problems."

→ Claude reads image, understands it's calculus
→ Chooses appropriate LaTeX template with amsmath
→ Transcribes with proper notation
→ Handles multi-page if needed
→ Creates project, deals with name conflicts
→ Uploads, verifies compilation
→ Returns URL with summary
```

#### 4.3 Schema Addition

**File:** `/path/to/pcp/scripts/schema_v2.py`

```python
# Add to schema migrations
"""
CREATE TABLE IF NOT EXISTS delegated_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Task definition (natural language, not structured)
    task_description TEXT NOT NULL,  -- "Transcribe HW5 to Overleaf"
    context TEXT,  -- JSON: {files: [], preferences: {}, related_captures: []}

    -- Status tracking
    status TEXT DEFAULT 'pending',  -- pending, claimed, running, completed, failed
    priority INTEGER DEFAULT 5,     -- 1=highest, 10=lowest

    -- Timestamps
    created_at TEXT,
    claimed_at TEXT,
    started_at TEXT,
    completed_at TEXT,

    -- Worker tracking
    worker_session_id TEXT,  -- Which Claude session claimed this

    -- Results
    result TEXT,      -- JSON: success result
    error TEXT,       -- Error message if failed

    -- Discord integration
    discord_channel_id TEXT,
    discord_user_id TEXT,
    notification_sent INTEGER DEFAULT 0,

    -- Metadata
    created_by TEXT,  -- "main_agent" or "user"
    tags TEXT         -- JSON array for filtering
);

CREATE INDEX IF NOT EXISTS idx_delegated_tasks_status ON delegated_tasks(status);
CREATE INDEX IF NOT EXISTS idx_delegated_tasks_priority ON delegated_tasks(priority, created_at);
"""
```

#### 4.4 Task Delegation Module

**File:** `/path/to/pcp/scripts/task_delegation.py`

```python
#!/usr/bin/env python3
"""
PCP Task Delegation System

Enables the main agent to delegate complex tasks to a worker Claude session.
Tasks are described in natural language - the worker Claude figures out how to execute them.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)):
    VAULT_PATH = "/path/to/pcp/vault/vault.db"


def delegate_task(
    description: str,
    context: Dict[str, Any] = None,
    discord_channel_id: str = None,
    discord_user_id: str = None,
    priority: int = 5,
    tags: List[str] = None
) -> int:
    """
    Delegate a task to the worker agent.

    Args:
        description: Natural language task description
                    "Transcribe the handwritten work in /path/to/hw5.pdf
                     to LaTeX and create an Overleaf project called 'HW5 Solutions'"
        context: Additional context (files, preferences, etc.)
        discord_channel_id: Channel to send completion notification
        priority: 1=highest, 10=lowest

    Returns:
        task_id: ID of the created task
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO delegated_tasks
        (task_description, context, status, priority, created_at,
         discord_channel_id, discord_user_id, created_by, tags)
        VALUES (?, ?, 'pending', ?, ?, ?, ?, 'main_agent', ?)
    """, (
        description,
        json.dumps(context) if context else None,
        priority,
        datetime.now().isoformat(),
        discord_channel_id,
        discord_user_id,
        json.dumps(tags) if tags else None
    ))

    task_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return task_id


def claim_task(worker_session_id: str) -> Optional[Dict[str, Any]]:
    """
    Claim the highest priority pending task for a worker.
    Returns None if no tasks available.
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get highest priority pending task
    cursor.execute("""
        SELECT * FROM delegated_tasks
        WHERE status = 'pending'
        ORDER BY priority ASC, created_at ASC
        LIMIT 1
    """)
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    task = dict(row)
    task_id = task['id']

    # Claim it
    cursor.execute("""
        UPDATE delegated_tasks
        SET status = 'claimed', claimed_at = ?, worker_session_id = ?
        WHERE id = ? AND status = 'pending'
    """, (datetime.now().isoformat(), worker_session_id, task_id))

    conn.commit()
    conn.close()

    return task


def start_task(task_id: int) -> bool:
    """Mark task as actively running."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE delegated_tasks
        SET status = 'running', started_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), task_id))
    conn.commit()
    conn.close()
    return True


def complete_task(task_id: int, result: Dict[str, Any]) -> bool:
    """Mark task as completed with result."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE delegated_tasks
        SET status = 'completed', completed_at = ?, result = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), json.dumps(result), task_id))
    conn.commit()
    conn.close()
    return True


def fail_task(task_id: int, error: str) -> bool:
    """Mark task as failed."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE delegated_tasks
        SET status = 'failed', completed_at = ?, error = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), error, task_id))
    conn.commit()
    conn.close()
    return True


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Get task by ID."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM delegated_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def list_tasks(status: str = None, limit: int = 20) -> List[Dict[str, Any]]:
    """List tasks with optional status filter."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if status:
        cursor.execute("""
            SELECT * FROM delegated_tasks
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (status, limit))
    else:
        cursor.execute("""
            SELECT * FROM delegated_tasks
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_pending_count() -> int:
    """Get count of pending tasks."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM delegated_tasks WHERE status = 'pending'")
    count = cursor.fetchone()[0]
    conn.close()
    return count
```

#### 4.5 Worker Agent Implementation

The worker is a **full Claude Code session**, not a Python script. It runs in a loop, checking for tasks and executing them with full Claude capabilities.

**File:** `/path/to/pcp/worker/WORKER_CLAUDE.md`

This is the CLAUDE.md for the worker agent - it tells Claude how to be a worker:

```markdown
# PCP Worker Agent

You are the PCP Worker Agent. Your job is to execute delegated tasks from the main PCP agent.

## Your Role

The main PCP agent handles the user's Discord conversations. When the user requests something complex
(like transcribing homework to Overleaf), the main agent delegates it to you so it can stay
responsive.

## Your Loop

1. Check for pending tasks: `python3 scripts/task_delegation.py --check`
2. If a task exists, claim it and execute
3. Write result back to database
4. Send Discord notification
5. Return to step 1

## Executing Tasks

Tasks come as natural language descriptions. Use your full capabilities:
- Read files with the Read tool
- Use Playwright MCP for Overleaf
- Access all PCP scripts
- Reason about what's needed

## Example Task

```
Task: "Transcribe the handwritten work in /workspace/vault/files/hw5.pdf
       to LaTeX and create an Overleaf project called 'HW5 Solutions'.
       This is for Math 301 and includes integration problems."

Context: {
  "files": ["/workspace/vault/files/hw5.pdf"],
  "preferences": {"latex_template": "article"},
  "discord_channel_id": "DISCORD_CHANNEL_ID"
}
```

Your approach:
1. Read the PDF/image
2. Understand it's calculus integration
3. Generate appropriate LaTeX with amsmath
4. Create Overleaf project in /path/to/workspace/overleaf-integration/projects/hw5-solutions/
5. Upload to Overleaf via Playwright
6. Return result with project URL

## Completion

When done, update the task:
```python
from task_delegation import complete_task
complete_task(task_id, {
    "success": True,
    "overleaf_url": "https://www.overleaf.com/project/xyz",
    "summary": "Transcribed 12 integration problems",
    "local_path": "/path/to/workspace/overleaf-integration/projects/hw5-solutions/"
})
```

Then send Discord notification and check for next task.

## Important Directories

- Overleaf projects: `/path/to/workspace/overleaf-integration/projects/`
- PCP vault files: `/workspace/vault/files/`
- Worker logs: `/workspace/worker/logs/`
```

**File:** `/path/to/pcp/scripts/worker_supervisor.py`

Python supervisor that launches and manages the Claude Code worker session:

```python
#!/usr/bin/env python3
"""
PCP Worker Supervisor

Launches and manages a Claude Code session that acts as the worker agent.
The worker executes delegated tasks with full Claude capabilities.
"""

import subprocess
import time
import os
import signal
import logging
from datetime import datetime

from task_delegation import get_pending_count, claim_task, start_task, complete_task, fail_task

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = "/path/to/pcp"
WORKER_DIR = f"{WORKSPACE}/worker"
POLL_INTERVAL = 10  # seconds


def generate_worker_prompt(task: dict) -> str:
    """Generate the prompt for the worker Claude session."""
    return f"""You are the PCP Worker Agent. Execute this delegated task:

## Task #{task['id']}
{task['task_description']}

## Context
{task.get('context', 'No additional context')}

## Instructions
1. Execute this task using your full capabilities
2. All Overleaf work should be in: /path/to/workspace/overleaf-integration/projects/
3. When complete, run:
   python3 /workspace/scripts/task_delegation.py complete {task['id']} --result '<JSON result>'
4. If failed, run:
   python3 /workspace/scripts/task_delegation.py fail {task['id']} --error '<error message>'

## Discord Notification
After updating the task, send notification to channel {task.get('discord_channel_id', 'N/A')}

Begin execution now.
"""


def run_worker_session(task: dict) -> bool:
    """Run a Claude Code session to execute the task."""
    prompt = generate_worker_prompt(task)
    session_id = f"worker_{task['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"Starting worker session {session_id} for task #{task['id']}")

    # Mark task as running
    start_task(task['id'])

    try:
        # Run Claude Code with the task prompt
        result = subprocess.run(
            [
                "claude",
                "--dangerously-skip-permissions",
                "-p", prompt,
                "--max-turns", "50",
                "--output-format", "text"
            ],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode == 0:
            logger.info(f"Worker session {session_id} completed successfully")
            return True
        else:
            logger.error(f"Worker session failed: {result.stderr}")
            fail_task(task['id'], f"Worker session failed: {result.stderr[:500]}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"Worker session {session_id} timed out")
        fail_task(task['id'], "Task timed out after 10 minutes")
        return False
    except Exception as e:
        logger.exception(f"Worker session error: {e}")
        fail_task(task['id'], str(e))
        return False


def supervisor_loop():
    """Main supervisor loop - check for tasks and spawn workers."""
    logger.info("Starting PCP Worker Supervisor")
    logger.info(f"Workspace: {WORKSPACE}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")

    while True:
        try:
            # Check for pending tasks
            pending = get_pending_count()

            if pending > 0:
                logger.info(f"Found {pending} pending task(s)")

                # Claim a task
                session_id = f"supervisor_{os.getpid()}"
                task = claim_task(session_id)

                if task:
                    logger.info(f"Claimed task #{task['id']}: {task['task_description'][:50]}...")
                    run_worker_session(task)
                else:
                    logger.warning("Failed to claim task (race condition?)")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Supervisor shutting down")
            break
        except Exception as e:
            logger.exception(f"Supervisor error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PCP Worker Supervisor")
    parser.add_argument("--once", action="store_true", help="Process one task and exit")
    parser.add_argument("--poll", type=int, default=10, help="Poll interval in seconds")

    args = parser.parse_args()
    POLL_INTERVAL = args.poll

    if args.once:
        from task_delegation import claim_task
        task = claim_task(f"manual_{os.getpid()}")
        if task:
            run_worker_session(task)
        else:
            print("No pending tasks")
    else:
        supervisor_loop()
```

#### 4.6 Task Delegation Skill

This skill teaches the main agent WHEN and HOW to delegate tasks.

**File:** `/path/to/pcp/.claude/skills/task-delegation/SKILL.md`

```markdown
---
name: task-delegation
description: Delegate long-running tasks to a background worker agent. Use when operations will take more than 30 seconds, involve multi-step workflows, or require extended processing like transcription, bulk file processing, or complex document creation.
allowed-tools: Read, Write, Bash
---

# Task Delegation

Delegate complex tasks to the PCP Worker Agent so you can stay responsive.

## The Core Principle

**YOU are the conversational agent.** You must always be responsive to the user.

- **Quick tasks** (< 30 seconds): Do directly
- **Complex tasks** (> 30 seconds): Delegate to worker

## When to Delegate

| Delegate | Don't Delegate |
|----------|----------------|
| Transcribe PDF to LaTeX | List Overleaf projects |
| Process folder of files | Search for a capture |
| Create Overleaf project + upload content | Generate a brief |
| Multi-step research | Look up a person |
| Bulk PDF summarization | Check task status |
| Any operation > 30 seconds | Any operation < 30 seconds |

## How to Delegate

```python
from task_delegation import delegate_task, get_task, list_tasks

# Create the task with natural language description
task_id = delegate_task(
    description="""
    [Clear natural language description of what needs to be done]
    Include all relevant details the worker needs.
    """,
    context={
        "files": ["/path/to/relevant/files"],
        "preferences": {"any": "preferences"},
        "related_captures": [123, 456]  # Optional related data
    },
    discord_channel_id="DISCORD_CHANNEL_ID",  # For notification
    priority=5  # 1=highest, 10=lowest
)

# Respond to user IMMEDIATELY
f"I've started working on that (task #{task_id}). I'll notify you when it's done."
```

## Response Pattern

**Always respond immediately after delegating:**

```
User: "Transcribe my homework to Overleaf"

You: "On it! I've started the transcription (task #42).
     I'll send you a notification when your Overleaf project is ready.

     In the meantime, is there anything else I can help with?"
```

## Checking Task Status

```python
# Get specific task
task = get_task(task_id=42)
print(task['status'])  # pending, claimed, running, completed, failed

# List recent tasks
recent = list_tasks(limit=10)
pending = list_tasks(status='pending')
```

## Task Description Best Practices

Write descriptions as if briefing a capable assistant:

**Good:**
```
Transcribe the handwritten calculus work in /workspace/vault/files/hw5.pdf
to LaTeX and create an Overleaf project called 'HW5 Solutions'.

This is Math 301 homework covering integration by parts and substitution.
Use the amsmath package for equations. Put the project in:
/path/to/workspace/overleaf-integration/projects/hw5-solutions/
```

**Bad:**
```
Do hw5
```

## Context Object

The context object provides additional information:

```python
context = {
    # Files the worker should access
    "files": ["/path/to/source.pdf"],

    # User preferences
    "preferences": {
        "latex_template": "article",
        "include_figures": True
    },

    # Related PCP data
    "related_captures": [123, 456],
    "project_id": 5,

    # Any other relevant info
    "subject": "Math 301",
    "deadline": "Friday"
}
```

## Priority Levels

| Priority | Use For |
|----------|---------|
| 1-2 | Urgent, time-sensitive |
| 3-4 | Important, user waiting |
| 5 | Normal (default) |
| 6-7 | Background, not urgent |
| 8-10 | Low priority, whenever |

## Notification Flow

1. Main agent delegates task
2. Worker agent picks it up
3. Worker completes task
4. Worker updates database
5. Worker sends Discord notification to the channel

The main agent does NOT need to poll for completion - notifications go directly to Discord.

## Example Delegations

### Transcription
```python
delegate_task(
    description="Transcribe /workspace/vault/files/notes.jpg to LaTeX",
    context={"subject": "Physics 201"},
    discord_channel_id="DISCORD_CHANNEL_ID"
)
```

### Bulk Processing
```python
delegate_task(
    description="Process all PDFs in OneDrive/Research/Papers and create summaries",
    context={"output_format": "markdown"},
    discord_channel_id="DISCORD_CHANNEL_ID"
)
```

### Multi-Step Workflow
```python
delegate_task(
    description="""
    1. Download project X from Overleaf
    2. Add the new figures from /workspace/vault/files/figures/
    3. Update the results section with the data in results.csv
    4. Upload back to Overleaf
    """,
    context={"project_id": "abc123"},
    discord_channel_id="DISCORD_CHANNEL_ID"
)
```

## Related Skills

- `/overleaf-integration` - For Overleaf-specific operations
- `/vault-operations` - For quick captures and searches
```

#### 4.7 Integration with Main Agent

When the main PCP agent receives a complex request:

```python
# Main agent detects complex task and delegates
from task_delegation import delegate_task

task_id = delegate_task(
    description="""
    Transcribe the handwritten work in /workspace/vault/files/hw5.pdf
    to LaTeX and create an Overleaf project called 'HW5 Solutions'.
    This is for Math 301 and includes integration problems.
    """,
    context={
        "files": ["/workspace/vault/files/hw5.pdf"],
        "preferences": {"latex_template": "article"},
    },
    discord_channel_id="DISCORD_CHANNEL_ID"
)

# Respond to user IMMEDIATELY
f"Started background task #{task_id}. I'll notify you when it's done."
```

#### 4.6 Validation Checklist
- [ ] background_tasks table created
- [ ] Can create tasks via create_task()
- [ ] Worker picks up pending tasks
- [ ] Tasks execute correctly
- [ ] Discord notifications sent on completion
- [ ] Failed tasks marked with error
- [ ] Can continue chatting while task runs

---

### Phase 5: Full Workflow Integration (2-3 hours)
**Goal:** Everything works together seamlessly

#### 5.1 Create Workflow Skill

**File:** `/path/to/pcp/.claude/skills/document-workflows/SKILL.md`

```markdown
---
name: document-workflows
description: transcribe, LaTeX, Overleaf, problem set, homework, handwritten, PDF, OneDrive, background task
---

# Document Workflows

Complex document processing workflows that run in the background.

## Workflow: Transcribe to Overleaf

```python
from task_queue import create_task

# Create background task
task_id = create_task(
    task_type="transcribe_to_overleaf",
    payload={
        "source_path": "/path/to/source.pdf",
        "project_name": "Document Name",
        "context": "Optional context"
    },
    discord_channel_id=CHANNEL_ID
)

# Respond immediately
f"Started transcription task #{task_id}. I'll notify you when done."
```

## Workflow: Process OneDrive Folder

```python
task_id = create_task(
    task_type="process_onedrive_folder",
    payload={
        "folder_path": "Problem_Sets/HW5"
    },
    discord_channel_id=CHANNEL_ID
)
```

## When the User Says...

| Request | Action |
|---------|--------|
| "Transcribe this to LaTeX and put it in Overleaf" | Create transcribe_to_overleaf task |
| "Process all PDFs in OneDrive/Research" | Create process_onedrive_folder task |
| "What's the status of my background task?" | Check task_queue.get_task(id) |
| "Show me running tasks" | task_queue.list_tasks(status="running") |

## Important

- Background tasks run asynchronously
- Always provide task ID so the user can check status
- Discord notification sent on completion
- Continue conversation while tasks run
```

#### 5.2 Update CLAUDE.md

Add section:
```markdown
### 15. Background Tasks

For long-running operations, use the background task system:

```python
from task_queue import create_task, get_task, list_tasks

# Create a task
task_id = create_task(
    task_type="transcribe_to_overleaf",
    payload={"source_path": "...", "project_name": "..."},
    discord_channel_id="..."
)

# Check status
task = get_task(task_id)
print(task["status"])  # pending, running, completed, failed

# List all tasks
all_tasks = list_tasks()
running = list_tasks(status="running")
```

**Task Types:**
| Type | Description |
|------|-------------|
| transcribe_to_overleaf | Image/PDF → LaTeX → Overleaf project |
| process_onedrive_folder | Process all files in OneDrive folder |
| bulk_pdf_summary | Summarize multiple PDFs |

When the user requests long operations, create a background task and continue the conversation.
```

#### 5.3 End-to-End Test Script

**File:** `/path/to/pcp/scripts/test_full_workflow.py`

```python
#!/usr/bin/env python3
"""
End-to-end test of the full PCP workflow.
"""

import os
import sys
import time

def test_phase_0():
    """Test basic PCP functionality."""
    print("=== Phase 0: Basic Functionality ===")

    from vault_v2 import smart_capture, smart_search

    # Test capture
    result = smart_capture("Test capture for workflow validation")
    assert result.get("capture_id"), "Capture failed"
    print(f"  Capture: OK (ID: {result['capture_id']})")

    # Test search
    results = smart_search("workflow validation")
    assert len(results) > 0, "Search failed"
    print(f"  Search: OK ({len(results)} results)")

    # Test brief
    from brief import generate_brief
    brief = generate_brief("daily")
    assert brief, "Brief generation failed"
    print("  Brief: OK")

    return True


def test_phase_1():
    """Test file processing."""
    print("\n=== Phase 1: File Processing ===")

    from file_processor import ingest_file

    # Create test image
    test_file = "/tmp/test_image.txt"
    with open(test_file, "w") as f:
        f.write("Test content for processing")

    result = ingest_file(test_file, context="Test file")
    assert result, "File processing failed"
    print(f"  File ingest: OK")

    return True


def test_phase_2():
    """Test Overleaf integration."""
    print("\n=== Phase 2: Overleaf Integration ===")

    try:
        from overleaf_api import OverleafAPI
        api = OverleafAPI()
        valid = api.validate_session()
        print(f"  Session valid: {valid}")

        if valid:
            projects = api.list_projects()
            print(f"  Projects: {len(projects)} found")

        return valid
    except ImportError:
        print("  Overleaf API not yet installed")
        return False


def test_phase_3():
    """Test OneDrive integration."""
    print("\n=== Phase 3: OneDrive Integration ===")

    try:
        from microsoft_graph import MicrosoftGraphClient
        client = MicrosoftGraphClient()
        configured = client.is_configured()
        print(f"  Configured: {configured}")
        return configured
    except Exception as e:
        print(f"  Not configured: {e}")
        return False


def test_phase_4():
    """Test background task system."""
    print("\n=== Phase 4: Background Tasks ===")

    try:
        from task_queue import create_task, get_task, list_tasks

        # Create test task
        task_id = create_task(
            task_type="test",
            payload={"test": True},
            priority=10
        )
        print(f"  Create task: OK (ID: {task_id})")

        # Get task
        task = get_task(task_id)
        assert task["status"] == "pending"
        print(f"  Get task: OK (status: {task['status']})")

        # List tasks
        tasks = list_tasks()
        print(f"  List tasks: OK ({len(tasks)} tasks)")

        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    print("PCP Full Workflow Validation\n")

    results = {
        "Phase 0 - Basic": test_phase_0(),
        "Phase 1 - Files": test_phase_1(),
        "Phase 2 - Overleaf": test_phase_2(),
        "Phase 3 - OneDrive": test_phase_3(),
        "Phase 4 - Tasks": test_phase_4(),
    }

    print("\n=== Summary ===")
    for phase, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {phase}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
```

#### 5.4 Validation Checklist
- [ ] Full workflow test passes
- [ ] Can upload image to Discord
- [ ] PCP extracts tasks from image
- [ ] Can create background transcription task
- [ ] Overleaf project created with LaTeX
- [ ] Discord notification received
- [ ] Can continue chatting during task
- [ ] OneDrive files accessible
- [ ] Error handling works correctly

---

## 5. Technical Specifications

### 5.1 File Locations

| Component | Location |
|-----------|----------|
| Discord bot | `/srv/agentops/services/agent-gateway/adapters/discord/bot.py` |
| Agent router | `/srv/agentops/services/agent-gateway/adapters/discord/agent_router.py` |
| Agents config | `/srv/agentops/config/agents.yaml` |
| PCP scripts | `/path/to/pcp/scripts/` |
| PCP skills | `/path/to/pcp/.claude/skills/` |
| PCP database | `/path/to/pcp/vault/vault.db` |
| Overleaf integration | `/path/to/workspace/overleaf-integration/` |

### 5.2 New Files to Create

| File | Purpose |
|------|---------|
| `scripts/task_queue.py` | Background task queue management |
| `scripts/task_worker.py` | Background task execution worker |
| `scripts/transcribe_to_overleaf.py` | Transcription workflow |
| `scripts/overleaf_api.py` | (copy from overleaf-integration) |
| `.claude/skills/overleaf-integration/SKILL.md` | Overleaf skill |
| `.claude/skills/document-workflows/SKILL.md` | Workflow skill |
| `scripts/test_full_workflow.py` | End-to-end validation |

### 5.3 Database Changes

```sql
-- New table for background tasks
CREATE TABLE IF NOT EXISTS background_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    payload TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    result TEXT,
    error TEXT,
    discord_channel_id TEXT,
    discord_message_id TEXT,
    created_by TEXT
);
```

### 5.4 Docker Changes

Add to `docker-compose.yaml` for pcp-agent:
```yaml
volumes:
  # Add temp directory for Discord attachments
  - /tmp/discord_attachments:/tmp/discord_attachments:rw
```

---

## 6. Validation Strategy

### 6.1 Unit Tests (Per Component)

| Component | Test |
|-----------|------|
| smart_capture | Entities extracted correctly |
| file_processor | OCR works on images |
| task_queue | CRUD operations work |
| overleaf_api | Session validation works |
| transcribe_to_latex | Generates valid LaTeX |

### 6.2 Integration Tests (Cross-Component)

| Test | Components |
|------|------------|
| Discord → PCP | Bot, Router, Capture |
| Image → Tasks | Bot, Capture, File Processor |
| Background task flow | Queue, Worker, Notification |
| Full transcription | Image, LaTeX, Overleaf |

### 6.3 End-to-End Tests

1. **Task Image Workflow**
   - Upload photo of task list to Discord
   - PCP extracts and organizes tasks
   - Verify tasks in database

2. **Transcription Workflow**
   - Upload handwritten work image
   - Request Overleaf transcription
   - Verify project created
   - Verify notification received

3. **Background Processing**
   - Start long task
   - Continue chatting
   - Receive completion notification

### 6.4 Acceptance Criteria

| Workflow | Criteria |
|----------|----------|
| Task extraction | 90%+ tasks correctly identified from image |
| LaTeX transcription | Compilable LaTeX, matches original structure |
| Background tasks | Completes within 5 minutes, notification sent |
| Chat continuity | Can send 5+ messages while task runs |

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Overleaf session expires | Medium | High | Add session refresh, clear error message |
| Discord attachment too large | Low | Medium | Size validation, chunking |
| LaTeX compilation fails | Medium | Medium | Validate LaTeX before upload |
| OneDrive OAuth expires | Low | Medium | Token refresh implemented |
| Background worker crashes | Low | High | Supervisor process, restart |

---

## 8. Success Metrics

### 8.1 Functional Metrics
- [ ] Can process task image in < 30 seconds
- [ ] Can transcribe 1-page handwritten work in < 2 minutes
- [ ] Background tasks complete reliably (99%+)
- [ ] Discord notifications arrive within 10 seconds of completion

### 8.2 Usage Metrics (After 1 Week)
- [ ] 10+ captures from Discord
- [ ] 3+ transcription workflows completed
- [ ] 5+ background tasks run
- [ ] Daily brief generated at least 3 times

---

## 9. Implementation Order

```
Week 1:
├── Phase 0: Validation & Seeding (Day 1, 30 min)
├── Phase 1: Discord Attachments (Day 1-2, 2-3 hours)
└── Phase 2: Overleaf Integration (Day 2-3, 2-3 hours)

Week 2:
├── Phase 3: OneDrive OAuth (Day 1, 1-2 hours)
├── Phase 4: Background Tasks (Day 1-2, 3-4 hours)
└── Phase 5: Full Integration (Day 2-3, 2-3 hours)

Total: ~15 hours of focused implementation
```

---

## 10. Next Actions

**Immediate (Today):**
1. Run Phase 0 validation
2. Test Discord → PCP flow
3. Seed basic context

**Tomorrow:**
1. Implement Discord attachment handling
2. Port Overleaf integration
3. Test image → tasks flow

**This Week:**
1. Complete all phases
2. Run full workflow test
3. Start using PCP daily

---

## Appendix A: Quick Reference Commands

```bash
# Test PCP container
docker exec -it pcp-agent python3 scripts/vault_v2.py capture "Test"
docker exec -it pcp-agent python3 scripts/brief.py --daily

# Check database
docker exec pcp-agent sqlite3 /workspace/vault/vault.db "SELECT COUNT(*) FROM captures_v2"

# View logs
docker logs pcp-agent --tail 50

# Restart containers
cd /path/to/pcp && docker compose restart
cd /srv/agentops/services/agent-gateway && docker compose restart
```

## Appendix B: Discord Channel IDs

| Channel | ID | Purpose |
|---------|-----|---------|
| #pcp | DISCORD_CHANNEL_ID | PCP agent |
| #alpha-trader | 1457980979393204225 | Trading agent |

---

## Appendix C: Skill Files Created

The following Claude Code skills have been created to support this workflow:

### Overleaf Integration Skill
**Location:** `/path/to/pcp/.claude/skills/overleaf-integration/SKILL.md`

Triggered by: transcribing, LaTeX, Overleaf, problem set, homework, handwritten, PDF
- Lists/downloads Overleaf projects via API
- Creates projects via Playwright MCP
- Transcribes handwritten work to LaTeX
- Delegates complex transcription to worker

### Task Delegation Skill
**Location:** `/path/to/pcp/.claude/skills/task-delegation/SKILL.md`

Triggered by: long task, background, async, delegate, worker
- Teaches main agent WHEN to delegate
- Provides `delegate_task()` usage patterns
- Explains priority levels and context objects
- Shows notification flow

---

*Document Version: 2.0*
*Last Updated: 2026-01-14*
*Skills Created: overleaf-integration, task-delegation*
