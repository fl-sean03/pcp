---
name: overleaf-sync
description: Sync local LaTeX projects with Overleaf. Bidirectional sync for .tex, .bib, images, folders. Use when pushing local changes to Overleaf, pulling updates, or checking sync status.
allowed-tools: Read, Write, Bash, Glob, Grep, mcp__playwright__*
---

# Overleaf Sync Skill

Bidirectional sync between local LaTeX projects and Overleaf without requiring Premium (Git access).

## Quick Start

```bash
# Add to PATH (one-time setup)
export PATH="$PATH:/workspace/overleaf/bin"

# Link local directory to an Overleaf project
cd /workspace/overleaf/projects/my-project
overleaf link <project_id>

# Pull current state from Overleaf
overleaf pull

# Check what's changed locally
overleaf status

# Push local changes (generates Playwright steps)
overleaf push
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `overleaf link <id>` | Link local directory to Overleaf project |
| `overleaf unlink` | Remove link (keeps local files) |
| `overleaf status` | Show added/modified/deleted files |
| `overleaf push` | Generate Playwright steps to upload changes |
| `overleaf push --dry-run` | Preview push plan without staging files |
| `overleaf push --no-delete` | Push but skip file deletions |
| `overleaf pull` | Download from Overleaf to local |
| `overleaf pull --force` | Overwrite local changes |
| `overleaf init <name>` | Initialize new project with template |
| `overleaf sync-complete` | Mark sync as complete after push |
| `overleaf cleanup` | Clean up staging directory |
| `overleaf list` | List all Overleaf projects (find IDs) |

## Architecture

```
Local Project           Sync Engine              Overleaf
     │                       │                       │
     ├── .overleaf/          │                       │
     │   ├── config.json     │                       │
     │   └── sync_state.json │                       │
     │                       │                       │
     └───────────────────────┼───────────────────────┤
         PULL (API)          │         PUSH (Playwright)
         Download ZIP ←──────┤───────→ Upload files
```

**Why Hybrid?**
- Overleaf free plan has no Git access
- API handles reads (list, download)
- Playwright handles writes (upload, delete)

## File Types Supported

- `.tex` - LaTeX source files
- `.bib` - Bibliography files
- `.cls`, `.sty` - Style and class files
- `.png`, `.jpg`, `.pdf` - Images and figures
- Any file type Overleaf accepts

## Project Structure

Each synced project has a `.overleaf/` metadata directory:

```
my-project/
├── main.tex
├── references.bib
├── figures/
│   └── diagram.png
└── .overleaf/           # Sync metadata (gitignored)
    ├── config.json      # Project ID, URL, link timestamp
    └── sync_state.json  # File hashes from last sync
```

## Workflow Examples

### Scenario 1: Work on Existing Overleaf Project

```bash
# Find project ID
overleaf list --filter "thesis"

# Create local directory and link
cd ~/Workspace/overleaf-integration/projects
mkdir thesis && cd thesis
overleaf link 507f1f77bcf86cd799439011
overleaf pull

# Edit locally...
vim main.tex
mkdir figures && cp ~/image.png figures/

# Check status
overleaf status
# → M main.tex
# → A figures/image.png

# Push changes
overleaf push
# → Generates Playwright steps for agent to execute
```

### Scenario 2: Check Sync Status

```bash
overleaf status

# Output:
# Project: My Thesis
# Overleaf ID: 507f1f77bcf86cd799439011
# URL: https://www.overleaf.com/project/507f1f77bcf86cd799439011
# Last sync: 2026-01-16T10:30:00 (pull)
#
# Added (2):
#   + figures/diagram.png
#   + appendix.tex
#
# Modified (1):
#   M main.tex
```

### Scenario 3: Push with Dry Run

```bash
overleaf push --dry-run

# Shows what would be synced without staging files
# Useful for previewing before actual push
```

## Important Constraints

### 1. Playwright File Path Restriction

Files must be in the user's home directory (`$HOME/`) for Playwright MCP to access them.

The sync engine automatically stages files to `$HOME/tmp/overleaf-staging/` before upload.

### 2. No Git Access (Free Plan)

- All reads via Overleaf API (download ZIP)
- All writes via Playwright browser automation
- No real-time collaboration sync

### 3. Deletions Require Confirmation

Deletions are dangerous - files removed from Overleaf cannot be recovered.

- `--no-delete` flag skips deletion operations
- Push shows warnings before deleting
- Always confirm with user first

## After Push: Executing Playwright Steps

When `overleaf push` runs, it:
1. Calculates diff (added/modified/deleted)
2. Stages files to `$HOME/tmp/overleaf-staging/`
3. Outputs Playwright MCP steps to execute

**You (the agent) must execute these steps:**

```
--- Operation 1: create_folder ---
Target: figures
Steps: 8

--- Operation 2: upload_file ---
Target: main.tex
Steps: 11
```

After successful execution:
```bash
overleaf sync-complete  # Updates sync state
```

## When the User Says...

| Request | Action |
|---------|--------|
| "Sync my Overleaf project" | `overleaf pull` then edit, then `overleaf push` |
| "Push my changes to Overleaf" | `overleaf push` (then execute Playwright steps) |
| "What files have I changed?" | `overleaf status` |
| "Download latest from Overleaf" | `overleaf pull` |
| "Link this folder to Overleaf" | `overleaf link <project_id>` |
| "What's the project ID for X?" | `overleaf list --filter "X"` |
| "Initialize a new LaTeX project" | `overleaf init "Project Name"` |

## Python API

```python
from overleaf_sync import OverleafProject, SyncEngine
from pathlib import Path

# Work with a project
project = OverleafProject(Path("/path/to/project"))

# Check if linked
if project.is_linked:
    print(f"Linked to: {project.project_name}")

# Get status
status = project.get_status()
if status.has_changes:
    print(f"Changes: {status.diff.summary()}")

# Create sync engine
engine = SyncEngine(project)

# Pull from Overleaf
result = engine.pull(force=False)

# Generate push plan
plan = engine.push(dry_run=False, skip_delete=True)
print(f"Operations: {len(plan.operations)}")
```

## Related Skills

- **overleaf-integration** - Read-only API operations, list projects
- **browser-automation** - Playwright MCP reference for executing steps
- **homework-workflow** - Uses Overleaf for transcription output
- **task-delegation** - Complex syncs can be delegated to worker

## File Locations

| Component | Path |
|-----------|------|
| CLI Script | `/workspace/overleaf/scripts/overleaf_cli.py` |
| Sync Engine | `/workspace/overleaf/scripts/overleaf_sync.py` |
| Diff Engine | `/workspace/overleaf/scripts/overleaf_diff.py` |
| CLI Wrapper | `/workspace/overleaf/bin/overleaf` |
| Projects | `/workspace/overleaf/projects/` |
| Staging | `$HOME/tmp/overleaf-staging/` |

## Troubleshooting

### "Not linked to Overleaf"
Run `overleaf link <project_id>` first. Find project IDs with `overleaf list`.

### "Local changes would be overwritten"
Your local files have changes. Either:
- Push first: `overleaf push`
- Or force pull: `overleaf pull --force`

### "Session cookie expired"
Refresh cookie from browser DevTools and update `.credentials` file.

### "File must be in $HOME/"
Playwright MCP restriction. The sync engine handles this automatically by staging files.

### Playwright execution fails
1. Take fresh snapshot: `browser_snapshot`
2. Find correct element refs
3. Retry the step
