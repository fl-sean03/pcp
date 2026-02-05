# PCP (Personal Control Plane) - Complete Specification

**Version:** 4.0
**Last Updated:** 2026-01-27
**Architecture:** Universal Agent with Queue-First Parallel Execution

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Principles](#core-principles)
4. [Use Cases by Category](#use-cases-by-category)
   - [Capture & Memory](#1-capture--memory)
   - [Search & Retrieval](#2-search--retrieval)
   - [Task Management](#3-task-management)
   - [Knowledge Base](#4-knowledge-base)
   - [Relationship Intelligence](#6-relationship-intelligence)
   - [Project Health](#7-project-health)
   - [Brief Generation](#8-brief-generation)
   - [Email Processing](#9-email-processing)
   - [File & Document Processing](#10-file--document-processing)
   - [OneDrive Integration](#11-onedrive-integration)
   - [Overleaf & LaTeX](#12-overleaf--latex)
   - [Parallel Execution & Focus Modes](#13-parallel-execution--focus-modes)
   - [Twitter/Social Media](#14-twittersocial-media)
   - [Pattern Detection](#15-pattern-detection)
   - [System Queries](#16-system-queries)
5. [Message Queue System](#message-queue-system)
6. [Data Flow Diagrams](#data-flow-diagrams)
7. [API Reference](#api-reference)
8. [Configuration Reference](#configuration-reference)
9. [Database Schema](#database-schema)

---

## Overview

PCP is the user's external brain - a personal data platform that captures, organizes, and surfaces information.

### The Universal Agent Model

PCP uses a **single universal agent** that can run multiple parallel instances. There are no specialized "subagents" - just one PCP brain with different focus modes when needed.

```
Discord Message
       ↓
Message Queue (never lose messages)
       ↓
Orchestrator (spawns agent instances)
       ↓
PCP Agent (universal, full capabilities)
       ↓
Agent decides: respond now OR spawn parallel instance
       ↓
Shared State (all instances learn together)
```

**Key Principles:**
- **One brain, many instances** - All agent instances are the same PCP with full capabilities
- **Queue-first** - Messages are persisted immediately, never lost
- **Agentic routing** - The agent decides how to handle tasks, not hard-coded rules
- **Parallel execution** - Multiple instances can work simultaneously
- **Unified learning** - All instances share state; system evolves as one entity

**PCP provides:**
- Data storage and retrieval
- External API integrations (email, OneDrive, Overleaf)
- System queries (containers, files)
- Parallel execution via agent spawning
- Message queue for reliability

**The Agent provides:**
- Natural language understanding
- Entity extraction
- Decision making (including when to spawn parallel work)
- Response formatting
- Self-spawning for heavy tasks

---

## Architecture

### Message Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        DISCORD INPUT                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    MESSAGE QUEUE (SQLite)                        │
│  • Instant persistence                                           │
│  • Never loses messages                                          │
│  • Tracks: pending → processing → completed                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR SERVICE                          │
│  • Polls queue for pending messages                              │
│  • Spawns PCP agent instances (max N concurrent)                 │
│  • Tracks completion, handles timeouts                           │
│  • Routes responses to Discord                                   │
│  • NO INTELLIGENCE - just process management                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PCP AGENT (Universal)                         │
│                                                                  │
│  Full capabilities - every instance has:                         │
│  • All vault operations                                          │
│  • All integrations (email, OneDrive, Overleaf, etc.)           │
│  • All knowledge and patterns                                    │
│  • Ability to spawn parallel instances                           │
│                                                                  │
│  Agentic decision for each message:                              │
│  • "Quick response?" → Handle directly                           │
│  • "Heavy work?" → ACK + spawn parallel instance                 │
│                                                                  │
│  No hard-coded rules. Agent uses judgment.                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      SHARED STATE                                │
│  • SQLite database (vault)                                       │
│  • All instances read/write same data                            │
│  • Unified learning and evolution                                │
└─────────────────────────────────────────────────────────────────┘
```

### Focus Modes (Not Different Agents)

When spawning parallel work, the agent can set a focus mode. This is context priming, not capability restriction:

| Focus Mode | Context | Still Has Full Access |
|------------|---------|----------------------|
| `general` | Default, full flexibility | Yes |
| `homework` | LaTeX, transcription, Overleaf | Yes |
| `research` | Exploration, analysis, documentation | Yes |
| `writing` | Content creation, drafting | Yes |
| `system` | System administration, DevOps | Yes |

Focus modes are just initial prompts that help the agent orient to the task. Every instance has identical capabilities.

---

## Core Principles

### 1. One Universal Agent
There is ONE PCP agent type. It can run multiple instances in parallel, but they're all the same brain with the same capabilities. No specialized "subagents."

### 2. Queue-First, Never Lose Messages
Every Discord message is immediately persisted to the queue before any processing. Messages are never lost, even if the system crashes.

### 3. Agentic Routing (Agent Decides)
The agent uses judgment to decide how to handle each message. There are no hard-coded rules, tiers, or classifications. Tasks exist on a continuous spectrum of complexity.

### 4. Parallel Execution via Self-Spawning
When a task requires significant work, the agent acknowledges immediately and spawns a parallel instance of itself. The user gets quick feedback; heavy work happens in background.

### 5. Unified Learning
All agent instances share the same database. Patterns learned by one instance benefit all future work. The system evolves as one coherent brain.

### 6. Claude Extracts, PCP Stores
Claude analyzes content during conversation and passes structured data to PCP. PCP never calls Claude via subprocess.

### 7. Data Functions Over Intelligence Functions
Functions return raw data. The agent formats and adds insights.

---

## Use Cases by Category

### 1. Capture & Memory

#### UC-1.1: Simple Note Capture
**Trigger:** the user shares information to remember
**Example:** "John mentioned the API needs rate limiting"

**Flow:**
```python
# Claude extracts during conversation:
entities = {"people": ["John"], "projects": ["API"], "topics": ["rate limiting"]}
intent = "note"

# Claude calls PCP:
from vault_v2 import store_capture
capture_id = store_capture(
    content="John mentioned the API needs rate limiting",
    capture_type="note",
    entities=entities
)

# Claude responds:
"Got it - captured as note. Linked to John and the API project."
```

**Confirmation includes:**
- Capture type (note/task/idea/decision)
- Entities extracted (people, projects, topics)
- Any auto-created items (tasks)

---

#### UC-1.2: Capture with Deadline (Auto-Task)
**Trigger:** Content mentions a deadline
**Example:** "Need to finish the API docs by Friday"

**Flow:**
```python
# Claude extracts:
entities = {"projects": ["API"], "topics": ["documentation"]}
temporal = {"has_deadline": True, "deadline_date": "2026-01-24"}
intent = "task"

# Claude calls PCP:
from vault_v2 import store_capture, store_task
capture_id = store_capture(content, capture_type="task", entities=entities, temporal=temporal)
task_id = store_task(
    content="Finish API docs",
    due_date="2026-01-24",
    related_captures=[capture_id]
)

# Claude responds:
"Got it - created task 'Finish API docs' due Friday (Jan 24)."
```

---

#### UC-1.3: Brain Dump (Multiple Items)
**Trigger:** the user sends multiple items in one message
**Example:**
```
Random thoughts:
- need to email Gary about the contract
- the API might be slow because of the database
- John prefers morning meetings
- should look into Redis caching
```

**Flow:**
```python
# Claude analyzes each item and categorizes:
items = [
    {"content": "Email Gary about the contract", "type": "task", "people": ["Gary"]},
    {"content": "API slow - possible database issue", "type": "note", "topics": ["API", "database"]},
    {"content": "John prefers morning meetings", "type": "fact", "people": ["John"]},
    {"content": "Look into Redis caching", "type": "idea", "topics": ["Redis", "caching"]}
]

# Claude calls PCP for each:
from vault_v2 import store_capture, store_task
from knowledge import add_knowledge

task_id = store_task("Email Gary about the contract", related_people=[gary_id])
store_capture("API slow - possible database issue", capture_type="note", entities={...})
add_knowledge("John prefers morning meetings", category="preference")
store_capture("Look into Redis caching", capture_type="idea", entities={...})

# Claude responds:
"Processed your brain dump:
- Created task: Email Gary about the contract
- Noted: API performance observation
- Stored fact: John prefers morning meetings
- Captured idea: Redis caching"
```

---

#### UC-1.5: Decision Capture
**Trigger:** the user records a decision
**Example:** "We decided to use PostgreSQL instead of MySQL for the main database"

**Flow:**
```python
# Claude extracts:
intent = "decision"
entities = {"topics": ["PostgreSQL", "MySQL", "database"]}

# Claude calls PCP:
from knowledge import record_decision
decision_id = record_decision(
    content="Use PostgreSQL instead of MySQL for the main database",
    context="Better JSON support and more mature ecosystem",
    alternatives=["MySQL", "SQLite"],
    project_id=project_id
)

# Claude responds:
"Recorded decision: Using PostgreSQL for the main database. I'll track the outcome."
```

---

### 2. Search & Retrieval

#### UC-2.1: Keyword Search
**Trigger:** the user asks about past content
**Example:** "What did I say about rate limiting?"

**Flow:**
```python
from vault_v2 import smart_search
results = smart_search("rate limiting")

# Claude synthesizes results:
"You mentioned rate limiting twice:
1. Jan 20: John said the API needs rate limiting
2. Jan 18: Discussed rate limit of 100 req/min for the public API"
```

---

#### UC-2.2: Semantic Search (Similarity-Based)
**Trigger:** Finding conceptually related content
**Example:** "Find anything about making the app faster"

**Flow:**
```python
from vault_v2 import semantic_search
results = semantic_search("making the app faster")
# Finds: "performance optimization", "caching strategy", "slow API response"

# Claude synthesizes:
"Found related content about performance:
- API response times could be improved with caching
- Database queries taking too long
- Consider Redis for session caching"
```

---

#### UC-2.3: Unified Search (All Sources)
**Trigger:** Comprehensive search across all data
**Example:** "Find everything about the budget"

**Flow:**
```python
from vault_v2 import unified_search
results = unified_search("budget", sources=["captures", "knowledge", "emails", "tasks"])

# Returns results from all sources with source_type indicator
```

---

#### UC-2.4: Person Lookup
**Trigger:** the user asks about a person
**Example:** "Who is John?"

**Flow:**
```python
from vault_v2 import get_person, get_relationship_summary
person = get_person("John")
summary = get_relationship_summary(person['id'])

# Claude responds:
"John Smith is a colleague at Acme Corp (Engineering lead).
- Last contacted: 3 days ago
- 15 interactions total
- Recent: Discussed rate limiting, API performance"
```

---

### 3. Task Management

#### UC-3.1: List Pending Tasks
**Trigger:** "What do I need to do?" / "Show my tasks"

**Flow:**
```python
from vault_v2 import get_tasks
tasks = get_tasks(status="pending")

# Claude formats:
"You have 5 pending tasks:
1. [Due today] Finish API documentation
2. [Due tomorrow] Email Gary about contract
3. [Overdue] Review PR #42
4. Send proposal to Sarah
5. Look into Redis caching"
```

---

#### UC-3.2: Complete a Task
**Trigger:** "Mark the API docs task as done"

**Flow:**
```python
from vault_v2 import complete_task
complete_task(task_id=42)

# Claude responds:
"Done! Marked 'Finish API documentation' as complete."
```

---

#### UC-3.3: Get Task with Context
**Trigger:** "Tell me about task 42" / "What's the context for that task?"

**Flow:**
```python
from vault_v2 import get_task_with_context
task = get_task_with_context(42)

# Returns:
# - Task content
# - Original capture context
# - Related people
# - Related project
# - Group tag (if part of a group)
```

---

#### UC-3.4: Get Tasks by Group
**Trigger:** "Show me the Oracle setup tasks"

**Flow:**
```python
from vault_v2 import get_tasks_by_group
tasks = get_tasks_by_group("oracle-setup")

# Returns all tasks with that group tag
```

---

### 4. Knowledge Base

#### UC-4.1: Store Permanent Fact
**Trigger:** the user states a permanent fact
**Example:** "Remember that MatterStack uses Redis for caching"

**Flow:**
```python
from knowledge import add_knowledge
knowledge_id = add_knowledge(
    content="MatterStack uses Redis for caching",
    category="architecture",
    project_id=matterstack_id
)

# Claude responds:
"Stored as architecture knowledge for MatterStack."
```

**Knowledge Categories:**
- `fact` - General facts
- `architecture` - System/code design
- `decision` - Choices made
- `preference` - Personal/team preferences

---

#### UC-5.2: Query Knowledge
**Trigger:** "What do I know about Redis?"

**Flow:**
```python
from knowledge import query_knowledge
results = query_knowledge("Redis", category="architecture")
```

---

#### UC-5.3: Record Decision with Outcome Tracking
**Trigger:** Recording important decisions

**Flow:**
```python
from knowledge import record_decision
decision_id = record_decision(
    content="Use PostgreSQL for main database",
    context="Better JSON support",
    alternatives=["MySQL", "SQLite"]
)

# Later, record outcome:
from knowledge import link_outcome
link_outcome(
    decision_id,
    outcome="Working great, queries are fast",
    assessment="positive",
    lessons_learned="Should have done this sooner"
)
```

---

#### UC-5.4: Find Decisions Pending Outcome
**Trigger:** Periodic review of decisions

**Flow:**
```python
from knowledge import get_decisions_pending_outcome
pending = get_decisions_pending_outcome(days_old=30)
```

---

### 6. Relationship Intelligence

#### UC-6.1: Find Stale Relationships
**Trigger:** "Who haven't I talked to recently?"

**Flow:**
```python
from vault_v2 import get_stale_relationships
stale = get_stale_relationships(days=14)

# Claude formats:
"People you haven't contacted in 14+ days:
- Sarah Chen (21 days) - last discussed budget
- Mike Johnson (never contacted despite 3 mentions)"
```

---

#### UC-6.2: Get Relationship Summary
**Trigger:** "Tell me about my relationship with John"

**Flow:**
```python
from vault_v2 import get_relationship_summary
summary = get_relationship_summary(person_id)

# Returns:
# - Contact history (first, last, count)
# - Recent captures mentioning them
# - Shared projects
```

---

#### UC-6.3: Update Contact (Automatic)
**Trigger:** Any capture mentioning a person

**Flow:**
```python
# Automatic when store_capture is called with entities containing people
# Updates: last_contacted, interaction_count, first_contacted (if first time)
```

---

### 7. Project Health

#### UC-7.1: Check Project Health
**Trigger:** "How's the MatterStack project doing?"

**Flow:**
```python
from vault_v2 import get_project_health
health = get_project_health(project_id)

# Returns:
# - Activity levels (week/month/quarter)
# - Days since activity
# - Pending/overdue tasks
# - Health status (healthy/needs_attention/stalled/has_overdue)
```

---

#### UC-7.2: Find Stalled Projects
**Trigger:** "What projects need attention?"

**Flow:**
```python
from vault_v2 import get_stalled_projects
stalled = get_stalled_projects(days=14)

# Claude formats:
"Projects with no activity in 14+ days:
- Old Project (20 days, 3 pending tasks)
- Abandoned Idea (never had activity)"
```

---

#### UC-7.3: Restore Project Context
**Trigger:** "Get me up to speed on PCP"

**Flow:**
```python
from vault_v2 import restore_context
context = restore_context(project_id)

# Returns comprehensive markdown summary:
# - Project info and health
# - Recent captures
# - Key decisions
# - Pending tasks
# - People involved
# - Related knowledge
```

---

### 8. Brief Generation

#### UC-8.1: Daily Brief
**Trigger:** "Give me my daily brief" / Morning startup

**Flow:**
```python
from brief import get_brief_data
data = get_brief_data(days=7)

# Claude formats the brief with sections:
# - Overdue items (urgent)
# - Due today
# - Upcoming deadlines
# - Activity summary
# - Stale relationships
# - Stalled projects
```

**Data returned:**
```python
{
    "generated_at": "2026-01-23T08:00:00",
    "captures": [...],
    "tasks": {"pending": [...], "overdue": [...], "due_today": [...]},
    "people": {...},
    "projects": {...},
    "knowledge": {...},
    "proactive": {...}
}
```

---

#### UC-8.2: Weekly Summary
**Trigger:** "Give me a weekly summary"

**Flow:**
```python
from brief import generate_weekly_summary
data = generate_weekly_summary()

# Includes: stats, completion rates, highlights, top people/projects
```

---

#### UC-8.3: End-of-Day Digest
**Trigger:** "What did I accomplish today?"

**Flow:**
```python
from brief import generate_eod_digest
data = generate_eod_digest()

# Today's activity + tomorrow preview
```

---

#### UC-8.4: Meeting Prep
**Trigger:** "Prepare me for a meeting with John and Sarah about the API"

**Flow:**
```python
from brief import generate_meeting_prep
data = generate_meeting_prep(
    people=["John", "Sarah"],
    topic="API"
)

# Per-person context + topic-related captures + suggested talking points
```

---

### 9. Email Processing

#### UC-9.1: Fetch New Emails
**Trigger:** Scheduled or "Check my email"

**Flow:**
```python
from email_processor import fetch_new_emails
result = fetch_new_emails(limit=50)

# Returns: fetched count, stored count, actionable items
```

---

#### UC-9.2: Search Emails
**Trigger:** "Find emails about the budget"

**Flow:**
```python
from email_processor import search_emails
results = search_emails("budget", days=30)
```

---

#### UC-9.3: Get Actionable Emails
**Trigger:** "What emails need my attention?"

**Flow:**
```python
from email_processor import get_actionable_emails
emails = get_actionable_emails()

# Returns emails flagged as actionable that haven't been actioned
```

---

#### UC-9.4: Create Email Draft
**Trigger:** "Draft an email to John about the API"

**Flow:**
```python
from email_processor import create_draft
result = create_draft(
    to="john@example.com",
    subject="Follow-up on API discussion",
    body="Hi John,\n\n..."
)

# Creates draft in Outlook - NEVER auto-sends
# Returns: draft_id, web_link
```

---

### 10. File & Document Processing

#### UC-10.1: Process Image (OCR + Vision)
**Trigger:** the user sends an image

**Flow:**
```python
from file_processor import ingest_file
capture_id = ingest_file(
    "/tmp/screenshot.png",
    context="Meeting whiteboard"
)

# Extracts text, generates summary, links entities
```

---

#### UC-10.2: Process PDF
**Trigger:** the user sends a PDF

**Flow:**
```python
from file_processor import ingest_file
capture_id = ingest_file("/tmp/document.pdf")

# Extracts text page by page, generates summary
```

---

#### UC-10.3: Process Discord Attachments
**Trigger:** Message contains `[ATTACHMENTS: [...]]`

**Flow:**
```python
from vault_v2 import process_discord_attachments
result = process_discord_attachments(message, context="homework")

# Processes all attachments, returns capture IDs and summaries
```

---

### 11. OneDrive Integration

#### UC-11.1: List Files
**Trigger:** "What's in my Documents folder?"

**Flow:**
```python
from onedrive_rclone import OneDriveClient
client = OneDriveClient()
files = client.list_files("Documents")
```

---

#### UC-11.2: Search OneDrive
**Trigger:** "Find my homework files"

**Flow:**
```python
results = client.search("homework", file_types=["pdf", "docx"])
```

---

#### UC-11.3: Download File
**Trigger:** "Get the budget spreadsheet"

**Flow:**
```python
client.download("Documents/budget.xlsx", "/tmp/budget.xlsx")
```

---

#### UC-11.4: Get Recent Files
**Trigger:** "What files did I work on recently?"

**Flow:**
```python
recent = client.get_recent_files(days=7)
```

---

### 12. Overleaf & LaTeX

#### UC-12.1: List Overleaf Projects
**Trigger:** "Show my Overleaf projects"

**Flow:**
```bash
overleaf list
```

---

#### UC-12.2: Homework Transcription Workflow
**Trigger:** the user sends homework images

**Flow:**
```python
from task_delegation import delegate_task

task_id = delegate_task(
    description="Transcribe CHEN5838 PS1 homework",
    context={
        "image_paths": ["/tmp/page1.jpg", "/tmp/page2.jpg"],
        "problem_set_source": "Desktop/CHEN5838/problem_sets/PS1.pdf",
        "class_name": "CHEN5838",
        "user_instructions": "Box final answers"
    },
    discord_channel_id="...",
    priority=3,
    subagent="homework-transcriber"  # Explicit subagent
)

# Claude responds immediately:
"Started processing your homework using the homework-transcriber (task #42). I'll notify you when done."
```

**Subagent performs:**
1. Download problem set from OneDrive
2. Transcribe images to LaTeX using Claude vision
3. Create Overleaf project via Playwright
4. Download compiled PDF
5. Upload all files to OneDrive
6. Store result in PCP vault
7. Notify via Discord

---

#### UC-12.3: Sync Overleaf Project
**Trigger:** "Push my changes to Overleaf"

**Flow:**
```bash
cd /path/to/project
overleaf status  # Check changes
overleaf push    # Push to Overleaf
```

Or via subagent:
```python
delegate_task(
    description="Sync my PCP docs to Overleaf",
    subagent="overleaf-sync"
)
```

---

### 13. Parallel Execution & Focus Modes

The v4.0 architecture uses **one universal agent** that can run multiple parallel instances. There are no specialized "subagents" - just PCP instances with different focus modes.

#### UC-13.1: Agent Decides How to Handle Tasks
**Trigger:** Any Discord message

**Flow:**
The agent uses judgment (not rules) to decide how to handle each message:

```
┌─────────────────────────────────────────────────────────────────┐
│  "Can I respond meaningfully within ~30 seconds?"               │
│                                                                 │
│  YES → Handle directly, respond                                 │
│  NO  → Acknowledge, spawn parallel instance                     │
│                                                                 │
│  This is JUDGMENT, not rules. The agent considers:              │
│  • Estimated time/complexity                                    │
│  • External dependencies (APIs, file processing)                │
│  • User's likely expectations                                   │
│  • Current context and patterns                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Direct Response Examples:**
- Search queries ("what did I say about X?")
- Listing items ("show my tasks", "what's pending?")
- Adding simple items ("add task: do X")
- Generating briefs ("give me a brief")
- Quick lookups ("who is John?")

**Parallel Instance Examples:**
- Research and exploration ("look into X", "analyze Y")
- Content creation ("write a blog post about...", "create a workspace for...")
- Multi-step workflows ("transcribe homework and upload to Overleaf")
- Heavy processing ("process all my emails", "sync with OneDrive")

---

#### UC-13.2: Spawn Parallel Work
**Trigger:** Agent determines task needs significant work

**Flow:**
```python
# Agent acknowledges immediately:
"Got it - I'll set up the TIM workspace. Working on it now, I'll message you when it's ready."

# Agent spawns parallel instance via Task tool:
# The parallel instance has:
# - Same capabilities as the main agent
# - Full access to vault, integrations, everything
# - Optional focus mode for initial context

# Parallel instance:
# 1. Does the work
# 2. Stores results in shared vault
# 3. Posts to Discord via webhook when complete
```

**Key Principle:** Every instance has full PCP capabilities. Focus modes just set initial context.

---

#### UC-13.3: Focus Modes
**Trigger:** Spawning parallel work for specific task types

Focus modes are NOT different agents - they're context primers for the same universal agent:

| Focus Mode | Context Primed | Still Has Full Access |
|------------|----------------|----------------------|
| `general` | Default, full flexibility | Yes |
| `homework` | LaTeX, transcription, Overleaf workflows | Yes |
| `research` | Exploration, analysis, documentation | Yes |
| `writing` | Content creation, drafting, editing | Yes |
| `system` | System administration, DevOps | Yes |

**Example - Homework Focus:**
```markdown
# Focus: Homework Processing

You're working on a homework-related task. Key context:

## Workflow
1. Receive homework images/PDFs
2. Transcribe to LaTeX using vision
3. Create/update Overleaf project
4. Compile and verify
5. Store results in vault

## Tools Available
- file_processor.py for image/PDF handling
- Overleaf API via overleaf_api.py
- Playwright MCP for browser automation if needed
- OneDrive for file storage

Remember: You have FULL PCP capabilities. This focus just sets context.
```

---

#### UC-13.4: Check Parallel Task Status
**Trigger:** "How's the TIM workspace coming?"

**Flow:**
```python
from message_queue import MessageQueue
from parallel_tasks import get_parallel_task

# Check queue status
queue = MessageQueue()
pending = queue.get_pending_count()

# Check specific parallel task
task = get_parallel_task(task_id)
# Returns:
{
    "id": 42,
    "description": "Create TIM workspace",
    "focus_mode": "general",
    "status": "running",
    "started_at": "2026-01-27T10:00:00",
    "progress_updates": [
        "Analyzing OneDrive files...",
        "Creating folder structure..."
    ]
}
```

---

#### UC-13.5: Progress Updates for Long Tasks
**Trigger:** Parallel instance wants to update user on progress

**Flow:**
```python
from discord_notify import notify

# During long-running work, post updates
notify("⏳ Still working on TIM workspace - found 15 relevant files in OneDrive...")

# When complete
notify("✅ TIM workspace ready at ~/Workspace/tim-roadmap")
```

---

#### UC-13.6: Unified Learning
**Trigger:** Any agent instance completes work

**Flow:**
All parallel instances share the same database:

```
Instance A stores capture → Instance B can search it
Instance B learns pattern → Instance A benefits
Instance C makes decision → All instances know about it
```

The system evolves as ONE brain, not fragmented knowledge.

---

### 14. Twitter/Social Media

#### UC-14.1: Curate Twitter Feed
**Trigger:** "Check my Twitter feed" / "What's happening on Twitter?"

**Flow:**
```python
delegate_task(
    description="Curate my Twitter feed and find engagement opportunities",
    subagent="twitter-curator"
)
```

**Subagent performs:**
1. Extract feed via Playwright MCP
2. Score each post for relevance (per Operating Manual)
3. Draft responses for high-relevance posts
4. Store drafts in social_feed table
5. Return top opportunities

**Response:**
```
"Found 3 high-relevance posts:

1. @researcher_jane - AI for protein folding
   Draft: "Interesting approach to..."
   Score: 0.95

2. @hpc_guru - New GPU cluster benchmarks
   Draft: "Have you considered..."
   Score: 0.92

Drafts saved - review and post manually."
```

---

#### UC-14.2: Draft Tweet
**Trigger:** "Draft a tweet about..."

**Flow:**
Creates draft in social_feed table, user must review and post manually.

**CRITICAL:** Never auto-post. Drafts only.

---

### 15. Pattern Detection

#### UC-15.1: Detect Repeated Topics
**Trigger:** Automatic / "What topics keep coming up?"

**Flow:**
```python
from patterns import detect_repeated_topics
repeated = detect_repeated_topics(threshold=3, days=7)

# Returns topics mentioned 3+ times in 7 days
```

---

#### UC-15.2: Get Pattern Suggestions
**Trigger:** Brief generation / "Any patterns I should know about?"

**Flow:**
```python
from patterns import get_pattern_data
data = get_pattern_data()

# Returns:
# - repeated_topics
# - repeated_people
# - activity_patterns
# - suggested_tasks
```

---

#### UC-15.3: Approve Suggestion
**Trigger:** "Yes, create that task"

**Flow:**
```python
from vault_v2 import approve_suggestion
result = approve_suggestion(suggestion_id, project_id=5)
```

---

### 16. System Queries

#### UC-16.1: Query Other Containers
**Trigger:** "How's alpha-trader doing?"

**Flow:**
```python
from system_queries import query_alpha_trader
status = query_alpha_trader("status")
```

---

#### UC-16.2: Get System Overview
**Trigger:** "What's running on the system?"

**Flow:**
```python
from system_queries import get_system_overview
overview = get_system_overview()
```

---

## Message Queue System

The queue-first architecture ensures messages are never lost.

### Queue Schema

```sql
CREATE TABLE discord_message_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Discord context
    channel_id TEXT NOT NULL,
    message_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    user_name TEXT NOT NULL,

    -- Content
    content TEXT NOT NULL,
    attachments TEXT,  -- JSON array

    -- Processing state
    status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
    priority INTEGER DEFAULT 5,      -- 1=highest, 10=lowest

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results
    response TEXT,
    error TEXT,

    -- Parallel tracking
    spawned_parallel BOOLEAN DEFAULT FALSE,
    parallel_task_id INTEGER
);
```

### Queue API

```python
from message_queue import MessageQueue

queue = MessageQueue()

# Enqueue (called by Discord bot immediately on message receive)
queue_id = queue.enqueue(
    message_id="123456",
    channel_id="DISCORD_CHANNEL_ID",
    user_id="user123",
    user_name="User",
    content="Create a TIM workspace",
    attachments=None
)

# Get next pending (called by orchestrator)
message = queue.get_next_pending()

# Update status
queue.mark_processing(queue_id)
queue.mark_completed(queue_id, response="Done!")
queue.mark_failed(queue_id, error="Something went wrong")
queue.mark_parallel(queue_id, parallel_task_id=42)

# Queries
count = queue.get_pending_count()
status = queue.get_status(message_id="123456")
queue.cleanup_old(days=7)  # Remove old completed messages
```

### Parallel Tasks Schema

```sql
CREATE TABLE parallel_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source
    queue_message_id INTEGER REFERENCES discord_message_queue(id),

    -- Task info
    description TEXT NOT NULL,
    focus_mode TEXT DEFAULT 'general',

    -- Status
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed

    -- Process tracking
    pid INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results
    result TEXT,
    error TEXT,

    -- Discord notification
    notification_sent BOOLEAN DEFAULT FALSE
);
```

### Orchestrator Service

The orchestrator is a dumb process manager with no intelligence:

```python
# pcp_orchestrator.py

class Orchestrator:
    def __init__(self, max_workers=3, poll_interval=0.5):
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self.active_workers = {}

    def run(self):
        """Main loop - poll queue, spawn workers."""
        while True:
            if len(self.active_workers) < self.max_workers:
                message = self.queue.get_next_pending()
                if message:
                    self.spawn_worker(message)

            self.check_completions()
            self.handle_timeouts()
            time.sleep(self.poll_interval)

    def spawn_worker(self, message):
        """Spawn Claude CLI process for message."""
        # Mark processing, add ⏳ reaction
        # Spawn: claude --print --dangerously-skip-permissions ...
        # Track in active_workers

    def check_completions(self):
        """Check for completed workers, route responses."""
        # If direct response: send to Discord, mark completed, ✅
        # If parallel spawned: send ACK, mark parallel, 🔄
```

### Discord Reactions

| Reaction | Meaning |
|----------|---------|
| ⏳ | Queued/Processing |
| ✅ | Complete (direct response) |
| 🔄 | Working in background |
| ✨ | Background task complete |
| ❌ | Error |

### Focus Prompts Reference

Focus prompts are stored in `prompts/focus/` and loaded when spawning parallel work:

| File | Focus | Purpose |
|------|-------|---------|
| `general.md` | Default | Full flexibility, no specific context |
| `homework.md` | Homework | LaTeX, transcription, Overleaf workflows |
| `research.md` | Research | Exploration, analysis, documentation |
| `writing.md` | Writing | Content creation, drafting, editing |
| `system.md` | System | System administration, DevOps |

Each focus prompt reminds the agent it has FULL capabilities - focus just sets initial context.

---

## Data Flow Diagrams

### Capture Flow
```
User Message
    ↓
Claude (extracts entities, intent, temporal)
    ↓
store_capture(content, entities, temporal)
    ↓
┌─────────────────────────────────────────┐
│ Creates capture record                   │
│ Links to people (updates contact info)   │
│ Links to projects                        │
│ Creates task if deadline detected        │
│ Indexes for semantic search              │
└─────────────────────────────────────────┘
    ↓
Returns: capture_id, task_id, linked entities
    ↓
Claude (formats confirmation)
    ↓
User Response
```

### Brief Generation Flow
```
Brief Request
    ↓
get_brief_data(days=7)
    ↓
┌─────────────────────────────────────────┐
│ Queries: captures, tasks, people,        │
│ projects, knowledge, proactive           │
│ Returns: raw data dictionary             │
└─────────────────────────────────────────┘
    ↓
Claude (formats with insights)
    ↓
Formatted Brief to User
```

### Subagent Delegation Flow
```
Complex Task Request
    ↓
delegate_task(description, context, mode="auto")
    ↓
┌─────────────────────────────────────────┐
│ 1. Infer subagent from description       │
│ 2. Create task record (status: pending)  │
│ 3. Store subagent type and mode          │
│ 4. Return task_id immediately            │
└─────────────────────────────────────────┘
    ↓
Immediate Response: "Started task #42 with homework-transcriber"
    ↓
    ↓ (Claude Code Background)
    ↓
Claude Code Task Tool (subagent_type="homework-transcriber")
    ↓
┌─────────────────────────────────────────┐
│ Subagent executes with full tool access  │
│ Transcript persists for resumption       │
│ May take minutes to complete             │
└─────────────────────────────────────────┘
    ↓
SubagentStop Hook Fires
    ↓
┌─────────────────────────────────────────┐
│ subagent_result_handler.py               │
│ - Updates subagent_executions table      │
│ - Stores result in captures (if sig.)    │
│ - Updates delegated_tasks status         │
│ - Triggers dependent tasks               │
└─────────────────────────────────────────┘
    ↓
Discord Notification (if configured)
```

### Task Chain Flow
```
create_task_chain([T1, T2→T1, T3→T2])
    ↓
┌─────────────────────────────────────────┐
│ Create T1 (no deps) → status: pending    │
│ Create T2 (deps: T1) → status: pending   │
│ Create T3 (deps: T2) → status: pending   │
│ Set group_id on all tasks                │
│ Update blocks field on dependencies      │
└─────────────────────────────────────────┘
    ↓
T1 executes (only ready task)
    ↓
T1 completes → process_chain_completion(T1)
    ↓
T2 now ready (T1 complete) → executes
    ↓
T2 completes → process_chain_completion(T2)
    ↓
T3 now ready (T2 complete) → executes
    ↓
T3 completes → Chain complete
    ↓
Final Discord Notification
```

---

## API Reference

### Core Storage Functions

| Function | Purpose | Parameters |
|----------|---------|------------|
| `store_capture()` | Store with pre-extracted data | content, capture_type, entities, temporal, source |
| `store_task()` | Create task directly | content, due_date, priority, related_people, context |
| `smart_capture()` | Legacy capture (supports pre-extracted) | content, entities (optional), temporal (optional) |

### Search Functions

| Function | Purpose | Parameters |
|----------|---------|------------|
| `smart_search()` | Keyword search (captures, people, projects) | query |
| `semantic_search()` | Similarity-based search | query, limit |
| `unified_search()` | All sources | query, sources (optional) |

### Data Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `get_brief_data()` | All data for brief generation | dict |
| `get_proactive_data()` | Attention items, deadlines, stale items | dict |
| `get_pattern_data()` | Detected patterns and suggestions | dict |

### Query Functions

| Function | Purpose | Parameters |
|----------|---------|------------|
| `get_tasks()` | List tasks | status, due_within_days |
| `get_stale_relationships()` | People not contacted | days |
| `get_stalled_projects()` | Inactive projects | days |
| `get_relationship_summary()` | Full person context | person_id |
| `get_project_context()` | Full project context | project_id |
| `restore_context()` | Human-readable project summary | project_id |

### Task Delegation Functions

| Function | Purpose | Parameters |
|----------|---------|------------|
| `delegate_task()` | Create delegated task | description, context, mode, subagent, depends_on, group_id |
| `create_task_chain()` | Create dependent task chain | tasks (list), group_id, discord_channel_id, mode |
| `get_task()` | Get task by ID | task_id |
| `list_tasks()` | List tasks with filters | status, limit, include_completed |
| `get_ready_tasks()` | Get tasks ready to execute | group_id (optional) |
| `get_task_chain_status()` | Get chain progress | group_id |
| `complete_task()` | Mark task complete | task_id, result, error |
| `process_chain_completion()` | Trigger dependent tasks | task_id |

### Subagent Tracking Functions

| Function | Purpose | Parameters |
|----------|---------|------------|
| `record_subagent_execution()` | Record subagent start | agent_id, agent_type, delegated_task_id, initial_prompt |
| `complete_subagent_execution()` | Mark subagent complete | agent_id, result_summary, status |
| `get_resumable_subagents()` | List resumable subagents | agent_type (optional) |
| `mark_subagent_resumed()` | Mark subagent as resumed | agent_id |

---

## Configuration Reference

**File:** `config/pcp.yaml`

```yaml
# Key configuration sections:

worker:
  timeout_seconds: 600      # Max worker task time
  max_concurrent: 1         # Concurrent worker tasks
  container_name: pcp-agent # Docker container name

scheduler:
  daily_brief_hour: 8       # When to generate daily brief
  eod_digest_hour: 18       # When to generate EOD digest
  reminder_interval_minutes: 60

thresholds:
  stale_relationship_days: 14    # When relationship is "stale"
  project_stale_days: 30         # When project is "stalled"
  repeated_topic_threshold: 3    # Mentions to be "repeated"

briefs:
  default_lookback_days: 7
  max_stale_relationships: 10

search:
  default_limit: 20
  semantic_enabled: true

subagents:
  default_mode: auto              # auto, subagent, or legacy
  auto_select_enabled: true       # Enable keyword-based selection
```

---

## Database Schema

### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `captures_v2` | All captured content | content, capture_type, extracted_entities, temporal_refs |
| `people` | People tracked | name, organization, last_contacted, interaction_count |
| `projects` | Projects | name, status, last_activity |
| `tasks` | Action items | content, due_date, status, context |
| `knowledge` | Permanent facts | content, category, confidence |
| `decisions` | Tracked decisions | content, context, outcome, assessment |
| `emails` | Processed emails | subject, sender, is_actionable |
| `files` | Indexed files | source_path, extracted_text, summary |
| `patterns` | Detected patterns | pattern_type, data, significance |
| `suggested_tasks` | Pattern suggestions | content, source_pattern_id, status |
| `social_feed` | Social media posts | platform, post_id, relevance_score, suggested_action |

### Task Delegation Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `delegated_tasks` | Background task queue | task_description, status, mode, subagent, depends_on, group_id |
| `subagent_executions` | Subagent tracking | agent_id, agent_type, status, can_resume, resume_count |

### delegated_tasks Schema

```sql
CREATE TABLE delegated_tasks (
    id INTEGER PRIMARY KEY,
    task_description TEXT NOT NULL,
    context TEXT,                    -- JSON
    status TEXT DEFAULT 'pending',   -- pending/claimed/running/completed/failed
    priority INTEGER DEFAULT 5,

    -- Timestamps
    created_at TIMESTAMP,
    claimed_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Worker tracking
    worker_session_id TEXT,

    -- Results
    result TEXT,                     -- JSON
    error TEXT,

    -- Discord
    discord_channel_id TEXT,
    discord_user_id TEXT,
    notification_sent INTEGER DEFAULT 0,

    -- Metadata
    created_by TEXT DEFAULT 'main_agent',
    tags TEXT,                       -- JSON array

    -- Subagent support (v3.0)
    mode TEXT DEFAULT 'auto',        -- auto/subagent/legacy
    subagent TEXT,                   -- pcp-worker, homework-transcriber, etc.
    subagent_id TEXT,                -- Claude Code agentId for resumption

    -- Dependencies (v3.0)
    depends_on TEXT,                 -- JSON array of task IDs
    blocks TEXT,                     -- JSON array of task IDs blocked by this
    group_id TEXT                    -- Chain/group identifier
);
```

### subagent_executions Schema

```sql
CREATE TABLE subagent_executions (
    id INTEGER PRIMARY KEY,

    -- Agent identification
    agent_id TEXT NOT NULL,          -- Claude Code's agentId
    agent_type TEXT NOT NULL,        -- pcp-worker, homework-transcriber, etc.

    -- Task linkage
    delegated_task_id INTEGER,       -- Link to delegated_tasks

    -- Status
    status TEXT DEFAULT 'running',   -- running/completed/failed/paused

    -- Context and results
    initial_prompt TEXT,
    result_summary TEXT,

    -- Timestamps
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Resumption
    can_resume BOOLEAN DEFAULT TRUE,
    resume_count INTEGER DEFAULT 0,

    FOREIGN KEY (delegated_task_id) REFERENCES delegated_tasks(id)
);
```

### Relationship Fields

- `captures_v2.linked_people` → `people.id`
- `captures_v2.linked_projects` → `projects.id`
- `tasks.project_id` → `projects.id`
- `tasks.related_people` → JSON array of `people.id`
- `knowledge.project_id` → `projects.id`
- `decisions.project_id` → `projects.id`
- `delegated_tasks.depends_on` → JSON array of `delegated_tasks.id`
- `subagent_executions.delegated_task_id` → `delegated_tasks.id`

---

## Quick Reference Card

### When the user says... → Do this

| Input | Action |
|-------|--------|
| "Remember X" | `store_capture(X)` |
| "Task: do Z by Friday" | `store_task(Z, due_date=...)` |
| "What did I say about X?" | `smart_search(X)` |
| "Find similar to X" | `semantic_search(X)` |
| "What's pending?" | `get_tasks(status="pending")` |
| "Who haven't I talked to?" | `get_stale_relationships(14)` |
| "How's project X?" | `get_project_health(X)` |
| "Get me up to speed on X" | `restore_context(X)` |
| "Give me a brief" | `get_brief_data()` + format |
| "Check my email" | `fetch_new_emails()` |
| [Sends image] | `ingest_file(path)` |
| [Multiple items] | Process each, categorize, store appropriately |
| "Transcribe my homework" | `delegate_task(..., subagent="homework-transcriber")` |
| "Research X for me" | `delegate_task(..., subagent="research-agent")` |
| "Check my Twitter" | `delegate_task(..., subagent="twitter-curator")` |
| "Do X then Y then Z" | `create_task_chain([X, Y→X, Z→Y])` |
| "How's the chain doing?" | `get_task_chain_status(group_id)` |
| "Continue the homework" | Resume subagent with agent_id |
| "What subagents can I resume?" | `get_resumable_subagents()` |

### Subagent Selection Cheat Sheet

| Task Type | Subagent | Model |
|-----------|----------|-------|
| General background work | `pcp-worker` | inherit |
| Homework → LaTeX | `homework-transcriber` | sonnet |
| Deep research | `research-agent` | haiku |
| Twitter curation | `twitter-curator` | sonnet |
| Overleaf sync | `overleaf-sync` | inherit |

---

*Document Version: 4.0 - Last Updated: 2026-01-27*
*Changes: Universal agent architecture, queue-first message handling, parallel execution via self-spawning, focus modes replacing subagents, agentic routing*
