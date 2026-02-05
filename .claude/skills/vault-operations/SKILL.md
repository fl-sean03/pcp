---
name: vault-operations
description: capture, remember, store, search, find, tasks, task list, todo, people, projects, vault, relationship, stale, contact, project health, stalled
---

# Vault Operations - Core PCP Data Layer

## Quick Start

Vault is PCP's core data layer. It handles:
- **Capturing** anything the user shares (text, observations, ideas)
- **Searching** across all captured content
- **Task management** (auto-created from captures or manual)
- **Entity linking** (people, projects, topics)
- **Relationships** (contact tracking, stale relationship detection)
- **Project Health** (activity monitoring, stalled project detection)

**Script:** `vault_v2.py`

---

## Smart Capture

### What Happens When the User Shares Something

When you receive content to remember, use `smart_capture()`:

```python
from vault_v2 import smart_capture

result = smart_capture("John mentioned the API needs rate limiting by Friday")
# Returns:
# {
#   'capture_id': 123,
#   'task_id': 456,          # Auto-created if deadline detected
#   'type': 'note',          # note|task|idea|decision|question
#   'entities': {...},       # Extracted people, projects, topics
#   'linked': {...}          # Linked to existing DB records
# }
```

### Auto-Detection Features

The capture system automatically:
1. **Extracts entities**: People, projects, topics mentioned
2. **Detects intent**: Is this a note, task, idea, or decision?
3. **Parses dates**: "tomorrow", "next Friday", "by EOD"
4. **Creates tasks**: When deadlines or action items detected
5. **Links to existing records**: Matches people/projects in DB
6. **Updates contact history**: When people are mentioned

### CLI Usage

```bash
# Capture text
python vault_v2.py capture "Meeting with John - decided to use Redis for caching"

# Output shows what was detected
Captured as decision (ID: 123)
Created task (ID: 456)
People: John
Linked to projects: [1]
```

---

## Search

### Smart Search (Default)

Searches captures, people, projects, and files:

```python
from vault_v2 import smart_search

results = smart_search("rate limiting")
# Returns list of matches from different sources
```

### Unified Search (Cross-System)

Searches ALL PCP data sources with consistent format:

```python
from vault_v2 import unified_search

# Search everything
results = unified_search("budget")

# Search specific sources only
results = unified_search("budget", sources=["knowledge", "tasks"])
```

**Valid sources:** `captures`, `knowledge`, `emails`, `tasks`

### CLI Usage

```bash
# Default search (captures, people, projects)
python vault_v2.py search "rate limiting"

# Search all sources (captures, knowledge, emails, tasks)
python vault_v2.py search "rate limiting" --all

# Search specific sources
python vault_v2.py search "budget" --sources knowledge,tasks
```

---

## Task Management

### Functions

```python
from vault_v2 import get_tasks, complete_task

# Get pending tasks
pending = get_tasks(status="pending")

# Get tasks due within N days
urgent = get_tasks(due_within_days=3)

# Complete a task
complete_task(task_id=42)
```

### CLI Usage

```bash
# List pending tasks (default)
python vault_v2.py tasks

# List completed tasks
python vault_v2.py tasks done

# List all tasks
python vault_v2.py tasks all
```

---

## Commitment Tracking

Commitments are things the user has committed to do or follow up on.

### Commitment Types

| Type | Examples |
|------|----------|
| `follow_up` | "I'll follow up with John", "Let me get back to you" |
| `promise` | "I'll send the document", "I will review it by Friday" |
| `deadline` | "Due by EOD", "Deadline is January 15" |

---

## Relationship Intelligence

PCP tracks people the user interacts with, maintaining relationship history.

### Automatic Tracking

When `smart_capture()` processes text:
1. Entity extraction identifies people mentions
2. People are auto-created if not found
3. `last_contacted` and `interaction_count` updated automatically

```python
result = smart_capture("Had coffee with John about the API project")
# -> John's last_contacted updated to now
# -> John's interaction_count incremented
```

### People Functions

```python
from vault_v2 import get_person, add_person, get_relationship_summary, get_stale_relationships

# Find person by name
person = get_person("John")

# Add new person
person_id = add_person("Jane Doe", relationship="colleague", context="From Acme Corp")

# Get full relationship summary
summary = get_relationship_summary(person_id)
# Includes: contact history, recent captures, shared projects

# Find people not contacted recently
stale = get_stale_relationships(days=14)
```

### CLI Usage

```bash
# Basic person info
python vault_v2.py person 1

# Full relationship summary
python vault_v2.py person 1 --summary

# Find stale relationships (not contacted in N days)
python vault_v2.py relationships --stale 14
```

### Stale Relationship Detection

People are "stale" if:
1. **Contacted before, but too long ago**: More than N days since last contact
2. **Never contacted despite mentions**: Has mentions but no `last_contacted`

Results are sorted with most urgent first.

---

## Project Health & Context

PCP tracks project health automatically.

### Health Status Definitions

| Status | Meaning |
|--------|---------|
| `healthy` | Active in last 14 days, no overdue tasks |
| `needs_attention` | No activity in 14-30 days |
| `stalled` | No activity in 30+ days |
| `has_overdue` | Active but has overdue tasks |
| `inactive` | Project status is not "active" |

### Functions

```python
from vault_v2 import get_project, get_project_health, get_stalled_projects, restore_context, get_project_context

# Get project by name
project = get_project("PCP")

# Get health metrics
health = get_project_health(project_id)
# Includes: activity levels, task counts, staleness indicator

# Find stalled projects
stalled = get_stalled_projects(days=14)

# Restore full project context (for getting back up to speed)
context = restore_context(project_id)

# Get structured context data
ctx = get_project_context(project_id)
# Returns: project info, health, captures, decisions, tasks, people, knowledge
```

### CLI Usage

```bash
# Basic project info
python vault_v2.py project 1

# Full health metrics
python vault_v2.py project 1 --health

# Find stalled projects
python vault_v2.py projects --stalled 14

# Restore context (by ID or name)
python vault_v2.py context PCP
python vault_v2.py context 1
python vault_v2.py context PCP --json
```

---

## Suggestion Approval

Pattern detection generates task suggestions. Use vault_v2.py to approve them:

```python
from vault_v2 import approve_suggestion, dismiss_suggestion
from patterns import get_suggested_tasks

# Get pending suggestions
suggestions = get_suggested_tasks(status="pending")

# Approve and create task
result = approve_suggestion(suggestion_id=1, project_id=5)

# Dismiss (mark as not useful)
dismiss_suggestion(suggestion_id=2)
```

### CLI Usage

```bash
# List pending suggestions
python vault_v2.py suggestions

# Approve and create task
python vault_v2.py suggestions --approve 1

# Dismiss
python vault_v2.py suggestions --dismiss 2
```

---

## Statistics

```bash
# Get vault statistics
python vault_v2.py stats

# Output:
# Captures: 150 (5 today)
# Tasks: {'pending': 12, 'done': 45}
# Overdue: 2
# People: 25
# Projects: 4 active
# Files: 18
```

---

## When To Use What

| User Says... | Function/Command |
|--------------|------------------|
| "Remember this..." | `smart_capture(content)` |
| "What did X say about..." | `smart_search(query)` |
| "Find everything about..." | `unified_search(query)` |
| "What tasks are pending?" | `get_tasks(status="pending")` |
| "Mark that done" | `complete_task(task_id)` |
| "I'll follow up with John" | Create task with `store_task()` |
| "What's overdue?" | `get_tasks(status="pending", overdue=True)` |
| "Who is John?" | `get_person("John")` or `get_relationship_summary(id)` |
| "Who haven't I talked to?" | `get_stale_relationships(days=14)` |
| "How's project X doing?" | `get_project_health(id)` |
| "Get me up to speed on X" | `restore_context(id)` |
| "What projects need attention?" | `get_stalled_projects(days=14)` |

---

## Key Patterns

### Capture vs Knowledge

- **Capture** (vault_v2.py): Transient observations, conversations, notes
- **Knowledge** (knowledge.py): Permanent facts, architecture decisions

Use `smart_capture()` for what the user shares in conversation.
Use `add_knowledge()` for facts that should persist permanently.

### Entity Detection

Captures automatically extract:
- **People**: Names mentioned (auto-created if new)
- **Projects**: Keywords matched to active projects
- **Topics**: Key themes for pattern detection
- **Dates**: Deadlines, reminders, time references

### Contact Tracking

When a capture mentions a person, the system automatically:
1. Updates `last_contacted` timestamp
2. Increments `interaction_count`
3. Sets `first_contacted` if first time

This enables stale relationship detection.

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `captures_v2` | All captured content |
| `people` | People tracked |
| `projects` | Projects tracked |
| `tasks` | Action items |
| `suggested_tasks` | Pattern-generated suggestions |

---

## Related Skills

- `/knowledge-base` - Permanent facts and decisions
- `/brief-generation` - Briefs include stale relationships, stalled projects
