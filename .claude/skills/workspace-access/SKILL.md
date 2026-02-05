---
name: workspace-access
description: Access and work on any project in the user's development environment
triggers:
  - workspace
  - projects
  - what am I working on
  - help me with
  - look at
  - check my
  - work on
---

# Workspace Access

## Purpose

You have full read-write access to the user's entire development environment at `/hostworkspace`. This skill teaches you how to discover, understand, and work on any project.

## When This Applies

- the user asks about "my projects", "my workspace", "what I'm working on"
- the user references a project by name (check if it exists at `/hostworkspace/<name>`)
- the user asks you to work on, modify, or explore something outside PCP
- the user asks "do you have access to X" - check `/hostworkspace` first

## How to Discover Projects

**Always discover dynamically - never assume what exists:**

```bash
# List all projects
ls /hostworkspace/

# See details (modification times show recent activity)
ls -lt /hostworkspace/

# Find a specific project (case-insensitive)
ls /hostworkspace/ | grep -i "searchterm"
```

## How to Understand a Project

Before working on any project, understand it:

```bash
# Priority 1: AI context file
cat /hostworkspace/<project>/CLAUDE.md 2>/dev/null

# Priority 2: Standard README
cat /hostworkspace/<project>/README.md 2>/dev/null

# Priority 3: Find all documentation
find /hostworkspace/<project> -maxdepth 2 -name "*.md" -type f

# Priority 4: See structure
ls -la /hostworkspace/<project>/
```

## How to Work on a Project

```bash
# Navigate and explore
cd /hostworkspace/<project>

# Check git status if it's a repo
git status 2>/dev/null

# Read, modify, create files as needed
# All changes sync instantly to the host filesystem
```

## Key Paths

| Path | Access | Contains |
|------|--------|----------|
| `/hostworkspace` | read-write | All projects (dynamic) |
| `/hosthome` | read-only | Home directory, configs, dotfiles |
| `/workspace` | read-write | PCP's own code |

## Important Notes

1. **Projects are dynamic** - New projects appear, old ones get archived. Always check what exists.
2. **Changes are real** - When you modify files, they change on the actual filesystem instantly.
3. **Read before writing** - Understand a project's structure before modifying it.
4. **Home is read-only** - `/hosthome` is for reading configs, not modifying.

## Example Interactions

**"What projects am I working on?"**
→ `ls -lt /hostworkspace/` (sorted by recent activity)
→ Read READMEs of the most recently modified ones

**"Help me with the opportunities tracker"**
→ `ls /hostworkspace/ | grep -i opport` (find it)
→ `cat /hostworkspace/opportunities/README.md` (understand it)
→ Then work on it

**"Do you have access to my twitter automation?"**
→ `ls /hostworkspace/ | grep -i twitter` (check if it exists)
→ If found: "Yes, I can see it at /hostworkspace/twitter-automation"

**"Make a change to the groundstate project"**
→ First read its CLAUDE.md or README.md
→ Understand the structure
→ Then make the requested change
