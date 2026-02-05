---
name: claude-code-history
description: Query and summarize Claude Code terminal session history
triggers:
  - claude code sessions
  - what was I working on
  - terminal history
  - continue where I left off
  - last session
  - what did I do in claude
---

# Claude Code History

## Purpose

Query the user's Claude Code terminal session history to:
- See what projects were worked on recently
- Summarize specific sessions
- Provide context for picking up where he left off
- Search across terminal conversations

**Note:** This is read-only and on-demand. We don't auto-sync or store this data.

## Data Location

Claude Code stores data at `/hosthome/.claude/`:

| Path | Contains |
|------|----------|
| `history.jsonl` | User messages with timestamps, projects, session IDs |
| `projects/<project-path>/` | Full conversation logs per session |
| `todos/` | Task lists from sessions |

## Common Queries

### List Recent Sessions

```bash
# Get recent messages with projects and timestamps
tail -50 /hosthome/.claude/history.jsonl | \
  jq -r '[.timestamp, .project, .display[:80]] | @tsv' | \
  column -t -s $'\t'
```

### Find Sessions for a Project

```bash
# List sessions for a specific project (e.g., myproject)
ls -lt /hosthome/.claude/projects/-home-user-Workspace-myproject/ 2>/dev/null | head -10

# Or search history for project mentions
grep -i "myproject" /hosthome/.claude/history.jsonl | \
  jq -r '[(.timestamp/1000 | strftime("%Y-%m-%d %H:%M")), .display[:60]] | @tsv' | \
  tail -20
```

### Read a Session's Conversation

```bash
# Session files are JSONL with message objects
# Find the most recent session file for a project
LATEST=$(ls -t /hosthome/.claude/projects/-home-user-Workspace-myproject/*.jsonl 2>/dev/null | head -1)

# Extract user messages from that session
cat "$LATEST" | jq -r 'select(.type == "human") | .message.content' | head -50
```

### Search Across All Sessions

```bash
# Search for a topic across all session history
grep -r "API design" /hosthome/.claude/projects/ 2>/dev/null | head -20
```

## How to Use This

### "What was I working on in Claude Code?"

1. Read recent history: `tail -30 /hosthome/.claude/history.jsonl`
2. Parse out projects and messages
3. Summarize the recent activity

### "Summarize my last session on [project]"

1. Find the project directory: `ls /hosthome/.claude/projects/ | grep -i <project>`
2. Get the latest session: `ls -t <project-dir>/*.jsonl | head -1`
3. Read the conversation
4. Generate a summary

### "Continue where I left off on [project]"

1. Find the latest session for that project
2. Read the last ~20 messages
3. Summarize the state and any pending work
4. Provide context for the new session

## Important Notes

1. **Read-only** - Never modify Claude Code's data
2. **On-demand** - Only query when asked, don't background sync
3. **Summarize, don't dump** - Generate useful summaries, not raw logs
4. **Privacy-aware** - This is the user's terminal history, treat it appropriately
5. **Session-specific** - Each .jsonl file is one conversation session

## Example Workflow

**User:** "What was I working on in Claude Code recently?"

**PCP:**
```bash
# Get last 20 distinct project/message pairs
tail -100 /hosthome/.claude/history.jsonl | \
  jq -r '[(.timestamp/1000 | strftime("%m-%d %H:%M")), .project, .display[:50]] | @tsv' | \
  sort -u | tail -20
```

Then summarize: "In the last few hours, you worked on:
- myproject: Positioning and workspace setup
- personal-site: Thesis-related content
- pcp: [this conversation]"
