# PCP Background Task Architecture v2

## Executive Summary

The current subagent architecture is fundamentally broken: Claude Code's `Task` tool with `run_in_background=true` terminates subagents when the parent exits. This document proposes a robust, queue-based architecture that guarantees task completion.

## The Core Problem

When a Discord user asks PCP to do something that takes more than ~30 seconds:

```
User: "Search my emails for the D111 key request and draft a reply"
PCP: "Got it, spawning a subagent to search..."
     [Uses Task tool with run_in_background=true]
     [Subagent starts, tries to run Bash command]
     [Parent finishes response, exits]
     [Claude Code sends SIGTERM to all child processes]
     [Subagent dies after 5 seconds]
     [User never gets a response]
```

**The `run_in_background` flag does NOT create a truly detached process.** It only makes the Task tool return immediately without waiting. When the parent session exits, all child processes are killed.

## The Solution: Queue-Based Execution

Instead of trying to spawn subagents that survive parent exit (impossible with current Claude Code), we use a battle-tested pattern: **task queues with independent workers**.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Discord User                                │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     agent-discord                                ││
│  │  Receives message, routes to gateway                            ││
│  └─────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     agent-gateway                                ││
│  │  Routes to pcp-agent container, manages locks                   ││
│  └─────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │              pcp-agent (Primary Claude Session)                  ││
│  │                                                                  ││
│  │  QUICK TASKS (<30s):                                            ││
│  │  └─ Handle directly, respond immediately                        ││
│  │     Examples: search, capture, brief, lookup                    ││
│  │                                                                  ││
│  │  LONG TASKS (>30s):                                             ││
│  │  └─ Queue via delegate_task(), respond with acknowledgment     ││
│  │     Examples: email search, transcription, research             ││
│  │                                                                  ││
│  │  IMPORTANT: Never use Task tool with run_in_background         ││
│  └─────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                   (writes to database)                               │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    delegated_tasks table                         ││
│  │  status: pending → claimed → running → completed/failed         ││
│  └─────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│              (polled by supervisor running on HOST)                  │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    pcp-supervisor (HOST)                         ││
│  │                                                                  ││
│  │  • Runs independently on host machine (not in container)        ││
│  │  • Polls delegated_tasks every 30 seconds                       ││
│  │  • Can be woken immediately via SIGUSR1                         ││
│  │  • Spawns Claude Code sessions for each task                    ││
│  │  • Monitors completion, handles timeouts                        ││
│  │  • Posts results to Discord via webhook                         ││
│  │  • Managed by systemd for reliability                           ││
│  └─────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                      (spawns workers)                                │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    pcp-worker sessions                           ││
│  │                                                                  ││
│  │  • Started by supervisor via docker exec OR direct invocation   ││
│  │  • Completely independent process (no parent to kill it)        ││
│  │  • Has full access to all PCP capabilities                      ││
│  │  • Runs to completion (max 10 minutes by default)               ││
│  │  • Updates task status in database                              ││
│  │  • Posts results to Discord when done                           ││
│  └─────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                    (posts via webhook)                               │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     Discord Channel                              ││
│  │  "Task completed: Here's the draft email for D111 keys..."     ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

## Why This Works

1. **Process Independence**: Workers are started by the supervisor, not by the parent Claude. There's no parent to kill them.

2. **Host-Level Execution**: The supervisor runs on the host machine, outside any container. It survives container restarts.

3. **Database as Queue**: The task queue is in SQLite. If the supervisor restarts, it picks up where it left off.

4. **Webhook for Results**: Results go directly to Discord via webhook, not through the original request chain.

## Task Lifecycle

```
┌──────────┐    delegate_task()    ┌──────────┐
│          │──────────────────────▶│          │
│  pending │                       │ claimed  │
│          │◀─────────────────────│          │
└──────────┘    (supervisor)       └──────────┘
                                        │
                                        ▼
                                  ┌──────────┐
                                  │          │
                                  │ running  │
                                  │          │
                                  └──────────┘
                                   │        │
                         ┌─────────┘        └─────────┐
                         ▼                            ▼
                   ┌──────────┐                ┌──────────┐
                   │          │                │          │
                   │completed │                │  failed  │
                   │          │                │          │
                   └──────────┘                └──────────┘
                         │                            │
                         └────────────────────────────┘
                                        │
                                        ▼
                                  ┌──────────┐
                                  │ Discord  │
                                  │ notified │
                                  └──────────┘
```

## Implementation Components

### 1. Primary Agent Behavior (CLAUDE.md update)

The primary Claude agent should:

**Handle Directly (Quick Tasks):**
- Search queries: "what did I say about X?"
- Listing items: "show my tasks"
- Captures: "remember that..."
- Briefs: "give me a brief"
- Quick lookups: "who is John?"

**Queue for Background (Long Tasks):**
- Email operations: "search emails for X", "draft a reply"
- Transcription: "transcribe this homework"
- Research: "look into X and write a report"
- Multi-step: "create a workspace for X"
- File processing: "process all PDFs in folder"

**How to Queue:**
```python
from task_delegation import delegate_task

# Queue the task
task_id = delegate_task(
    description="Search emails for D111 keys and draft a reply",
    context={
        "search_query": "keys D111 JSCBB office",
        "days": 90
    },
    discord_channel_id="DISCORD_CHANNEL_ID"
)

# Respond immediately with acknowledgment
"Got it, I'll search your emails for that. I'll message you when I find something."
```

**What NOT to do:**
```python
# BROKEN - subagent dies when parent exits
Task(
    description="Search emails",
    run_in_background=True  # This flag is deceptive - it doesn't work
)
```

### 2. Supervisor Process

**File:** `scripts/pcp_supervisor.py` (renamed from worker_supervisor.py)

**Responsibilities:**
- Poll `delegated_tasks` table for pending tasks
- Claim tasks atomically (prevent duplicate processing)
- Spawn Claude Code workers for each task
- Monitor worker completion with timeouts
- Handle failures with configurable retries
- Post results to Discord via webhook
- Report status and metrics

**Run Modes:**
```bash
# Continuous supervisor (production)
python pcp_supervisor.py

# Process one task and exit (testing)
python pcp_supervisor.py --once

# Show status
python pcp_supervisor.py --status

# Dry run (claim but don't execute)
python pcp_supervisor.py --dry-run
```

### 3. Worker Execution

Workers are Claude Code sessions spawned by the supervisor:

```bash
# Inside container
claude -p "..." --output-format json --dangerously-skip-permissions --max-turns 50

# From host (via docker exec)
docker exec -i pcp-agent claude -p "..." --output-format json --dangerously-skip-permissions --max-turns 50
```

**Worker Prompt Template:**
```
You are a PCP Worker processing task #{task_id}.

## Task
{description}

## Context
{context}

## Instructions
1. Execute the task described above
2. When done, call complete_task({task_id}, result={"summary": "..."})
3. On failure, call complete_task({task_id}, error="Error message")
4. Post results to Discord using discord_notify.notify("...")

## Available Tools
- All PCP scripts in /workspace/scripts/
- Playwright MCP for browser automation
- Full file system access

Begin execution now.
```

### 4. Task Schema

```sql
CREATE TABLE delegated_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_description TEXT NOT NULL,
    context TEXT,  -- JSON

    -- Status tracking
    status TEXT DEFAULT 'pending',  -- pending/claimed/running/completed/failed
    claimed_by TEXT,      -- worker session ID
    claimed_at TEXT,
    started_at TEXT,
    completed_at TEXT,

    -- Result
    result TEXT,   -- JSON
    error TEXT,

    -- Retry handling
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Discord integration
    discord_channel_id TEXT,
    discord_user_id TEXT,
    notification_sent INTEGER DEFAULT 0,

    -- Metadata
    priority INTEGER DEFAULT 5,  -- 1=highest, 10=lowest
    tags TEXT,      -- JSON array
    created_by TEXT,
    created_at TEXT,
    updated_at TEXT,

    -- Dependencies (for task chains)
    depends_on TEXT,  -- JSON array of task IDs
    blocks TEXT,      -- JSON array of task IDs waiting on this
    group_id TEXT     -- Group related tasks
);
```

### 5. Systemd Service

**File:** `/etc/systemd/system/pcp-supervisor.service`

```ini
[Unit]
Description=PCP Background Task Supervisor
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=pcp
WorkingDirectory=/path/to/pcp
ExecStart=/usr/bin/python3 /path/to/pcp/scripts/pcp_supervisor.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

**Setup:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable pcp-supervisor
sudo systemctl start pcp-supervisor
```

## Decision Flow for Primary Agent

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Message Received                                 │
│                           │                                          │
│                           ▼                                          │
│              ┌────────────────────────┐                             │
│              │  Can I respond within  │                             │
│              │      ~30 seconds?      │                             │
│              └────────────────────────┘                             │
│                    │            │                                    │
│                   YES          NO                                    │
│                    │            │                                    │
│                    ▼            ▼                                    │
│         ┌──────────────┐  ┌──────────────────────┐                 │
│         │   Execute    │  │   Queue Task via     │                 │
│         │   Directly   │  │   delegate_task()    │                 │
│         └──────────────┘  └──────────────────────┘                 │
│                │                    │                                │
│                ▼                    ▼                                │
│         ┌──────────────┐  ┌──────────────────────┐                 │
│         │   Respond    │  │   Acknowledge:       │                 │
│         │   with       │  │   "Got it, I'll      │                 │
│         │   answer     │  │   work on that..."   │                 │
│         └──────────────┘  └──────────────────────┘                 │
│                                     │                                │
│                                     ▼                                │
│                         ┌──────────────────────┐                    │
│                         │   Supervisor picks   │                    │
│                         │   up task, executes  │                    │
│                         │   worker, posts      │                    │
│                         │   result to Discord  │                    │
│                         └──────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick vs Long Task Guidelines

| Quick (Handle Directly) | Long (Queue for Background) |
|-------------------------|---------------------------|
| Search vault | Search emails (requires API/browser) |
| List tasks | Process multiple files |
| Add capture | Transcribe images to LaTeX |
| Generate brief | Research and write report |
| Quick lookup | Create workspace/project |
| Show person info | Sync with external services |
| Project status | Complex multi-step workflows |

**Heuristic:** If it involves external APIs, browser automation, multiple files, or could take more than 30 seconds, queue it.

## Error Handling

### Task Failure
1. Mark task as `failed` with error message
2. If retry_count < max_retries, requeue with exponential backoff
3. Post failure notification to Discord
4. Log for debugging

### Supervisor Crash
1. Systemd automatically restarts
2. Tasks remain in database
3. `claimed` tasks older than 10 minutes are reset to `pending`
4. No work is lost

### Worker Timeout
1. Worker killed after 10 minutes (configurable)
2. Task marked as `failed` with timeout error
3. Can be retried

### Discord Webhook Failure
1. Log the notification
2. Can be retried later
3. Task status is already updated in database

## Monitoring

### Status Command
```bash
python pcp_supervisor.py --status
```
Output:
```
PCP Background Task Status
==========================
Pending:   3
Claimed:   1
Running:   0
Completed: 47 (last 24h)
Failed:    2 (last 24h)

Current Worker:
  Task #52: "Search emails for D111..."
  Started: 2 minutes ago

Recent Completions:
  #51: Completed in 45s - "Transcribe HW5"
  #50: Completed in 2m30s - "Create TIM workspace"
```

### Logs
```bash
tail -f /path/to/pcp/logs/supervisor.log
```

## Migration Plan

### Phase 1: Immediate (Fix the Bug)
1. Start supervisor process on host
2. Update CLAUDE.md with queue-based approach
3. Remove/deprecate "subagent" mode from task_delegation.py

### Phase 2: Reliability
1. Add systemd service
2. Add monitoring/alerting
3. Add retry logic

### Phase 3: Enhancement
1. Task priorities and scheduling
2. Task chains/dependencies
3. Worker pools for parallelism

## Files to Modify

| File | Change |
|------|--------|
| `scripts/pcp_supervisor.py` | Rename from worker_supervisor.py, enhance |
| `scripts/task_delegation.py` | Remove subagent mode, simplify |
| `CLAUDE.md` | Update task delegation section |
| `systemd/pcp-supervisor.service` | Create |
| `docs/BACKGROUND_TASK_ARCHITECTURE_V2.md` | This document |

## Summary

**The key insight:** Don't fight Claude Code's process model. Accept that subagents die with their parent. Use a queue.

**The solution:**
1. Quick tasks → handle directly
2. Long tasks → queue to database → independent supervisor processes them → webhook posts results

**The benefits:**
- Reliable completion (no more silent failures)
- Survives restarts
- Observable (logs, status)
- Scalable (can add worker parallelism later)
- Simple mental model

---

*Architecture document for PCP background task system. Supersedes any previous subagent-based approaches.*
