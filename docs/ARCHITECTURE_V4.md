# PCP Architecture v4.0 - Universal Agent with Parallel Execution

**Version:** 4.0
**Date:** 2026-01-27
**Status:** Implementation Plan

---

## Executive Summary

This document describes the evolution of PCP from a single-threaded agent with specialized subagents to a **universal agent architecture** with parallel execution capabilities. The key changes:

1. **One Universal Agent** - No more specialized subagents; one PCP brain with focus modes
2. **Queue-First** - Messages are never lost; persistent queue handles all input
3. **Parallel Execution** - Multiple agent instances can run simultaneously
4. **Agentic Routing** - The agent decides how to handle tasks, not hard-coded rules
5. **Unified Learning** - All instances share state; system evolves as one entity

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DISCORD INPUT                             │
│  Messages, attachments, commands                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MESSAGE QUEUE (SQLite)                        │
│                                                                  │
│  discord_message_queue table:                                    │
│  • id, channel_id, message_id, user_name, content               │
│  • attachments (JSON), status, created_at                        │
│  • processed_at, response, error                                 │
│                                                                  │
│  Guarantees:                                                     │
│  • Message received = Message persisted                          │
│  • Survives process restarts                                     │
│  • FIFO ordering preserved                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR SERVICE                          │
│                    (pcp_orchestrator.py)                         │
│                                                                  │
│  Responsibilities:                                               │
│  • Poll queue for pending messages                               │
│  • Spawn PCP agent instances (max N concurrent)                  │
│  • Track instance completion                                     │
│  • Route responses back to Discord                               │
│  • Handle timeouts and failures                                  │
│                                                                  │
│  NOT responsible for:                                            │
│  • Understanding messages (no intelligence)                      │
│  • Deciding how to handle tasks (agent decides)                  │
│  • Classifying complexity (no tiers)                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PCP AGENT (Universal)                         │
│                                                                  │
│  ONE agent type with FULL capabilities:                          │
│  • All vault operations (capture, search, tasks, etc.)           │
│  • All integrations (email, OneDrive, Overleaf)                  │
│  • All knowledge and patterns                                    │
│  • Can spawn parallel instances of itself                        │
│                                                                  │
│  Agentic Decision Making:                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ For each message, the agent evaluates:                   │    │
│  │                                                          │    │
│  │ "Can I respond meaningfully within ~30 seconds?"         │    │
│  │   YES → Handle directly, respond                         │    │
│  │   NO  → Acknowledge, spawn parallel instance             │    │
│  │                                                          │    │
│  │ This is JUDGMENT, not rules. The agent considers:        │    │
│  │ • Estimated time/complexity                              │    │
│  │ • External dependencies                                  │    │
│  │ • User's likely expectations                             │    │
│  │ • Current context and patterns                           │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌──────────────────────┐          ┌──────────────────────┐
│   DIRECT RESPONSE    │          │  PARALLEL INSTANCE   │
│                      │          │                      │
│  Quick tasks:        │          │  Heavy tasks:        │
│  • Search queries    │          │  • Research          │
│  • List tasks        │          │  • Workspace setup   │
│  • Add simple items  │          │  • Document creation │
│  • Generate briefs   │          │  • Complex analysis  │
│  • Quick lookups     │          │  • Multi-step work   │
│                      │          │                      │
│  Response: Immediate │          │  Response: ACK now,  │
│                      │          │  result via webhook  │
└──────────────────────┘          └──────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SHARED STATE                                │
│                                                                  │
│  SQLite Database (vault.db):                                     │
│  • captures_v2, tasks, knowledge, decisions                      │
│  • people, projects, patterns                                    │
│  • discord_message_queue, parallel_tasks                         │
│                                                                  │
│  All agent instances read/write to same database.                │
│  Learning is unified - system evolves as one brain.              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DISCORD OUTPUT                                │
│                                                                  │
│  Direct responses: Sent immediately via bot                      │
│  Parallel results: Sent via webhook when complete                │
│                                                                  │
│  Reactions:                                                      │
│  ⏳ = Queued/Processing                                          │
│  ✅ = Complete (direct)                                          │
│  🔄 = Working in background                                      │
│  ✨ = Background task complete                                   │
│  ❌ = Error                                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Message Queue

**Location:** `scripts/message_queue.py`

**Schema:**
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
    parallel_task_id INTEGER,

    -- Indexes for efficient querying
    UNIQUE(channel_id, message_id)
);

CREATE INDEX idx_queue_status ON discord_message_queue(status);
CREATE INDEX idx_queue_created ON discord_message_queue(created_at);
```

**API:**
```python
class MessageQueue:
    def enqueue(message_id, channel_id, user_id, user_name, content, attachments=None) -> int
    def get_next_pending() -> Optional[dict]
    def mark_processing(queue_id: int) -> bool
    def mark_completed(queue_id: int, response: str) -> bool
    def mark_failed(queue_id: int, error: str) -> bool
    def mark_parallel(queue_id: int, task_id: int) -> bool
    def get_status(message_id: str) -> dict
    def get_pending_count() -> int
    def cleanup_old(days: int = 7) -> int
```

### 2. Orchestrator Service

**Location:** `scripts/pcp_orchestrator.py`

**Responsibilities:**
- Run as persistent service (systemd or Docker)
- Poll message queue every 500ms
- Manage worker pool (default: 3 concurrent)
- Spawn Claude CLI processes
- Handle process completion and timeouts
- Route responses to Discord

**Configuration:**
```yaml
orchestrator:
  max_concurrent_workers: 3
  poll_interval_ms: 500
  worker_timeout_seconds: 600  # 10 minutes max
  ack_timeout_seconds: 30      # Must ACK within 30s

  discord:
    webhook_url: "..."

  claude:
    container: pcp-agent
    working_dir: /workspace
    session_resume: true
```

**Worker Lifecycle:**
```
1. Get message from queue
2. Mark as 'processing'
3. Add ⏳ reaction
4. Spawn Claude process
5. Wait for response (with timeout)
6. If direct response:
   - Send to Discord
   - Mark completed
   - Add ✅ reaction
7. If parallel spawned:
   - Send ACK to Discord
   - Add 🔄 reaction
   - Track parallel task
8. On parallel completion:
   - Send result via webhook
   - Add ✨ reaction
```

### 3. PCP Agent Prompt Update

**Location:** `CLAUDE.md` (updated section)

```markdown
## Agentic Execution Model

You are PCP - the user's unified external brain. You can run as multiple parallel
instances, all sharing the same knowledge and state.

### How to Handle Messages

When you receive a Discord message, use your judgment:

**Respond Directly** when you can provide a meaningful response quickly:
- Search queries ("what did I say about X?")
- Listing items ("show my tasks", "what's pending?")
- Adding simple items ("add task: do X")
- Generating briefs ("give me a brief")
- Quick lookups ("who is John?")

**Spawn Parallel Work** when the task requires significant effort:
- Research and exploration ("look into X", "analyze Y")
- Content creation ("write a blog post about...", "create a workspace for...")
- Multi-step workflows ("transcribe homework and upload to Overleaf")
- Heavy processing ("process all my emails", "sync with OneDrive")

### Spawning Parallel Work

When you determine a task needs parallel execution:

1. **Acknowledge immediately:**
   "Got it - I'll [brief description of task]. Working on it now, I'll message
   you when it's ready."

2. **Use the Task tool to spawn yourself:**
   The Task tool creates a parallel instance of you (same capabilities, same
   access) focused on this specific task.

3. **The parallel instance will:**
   - Do the work
   - Post results to Discord via webhook when complete
   - Store relevant data in the shared vault

### Focus Modes (Not Different Agents)

When spawning parallel work, you can specify a focus mode. This doesn't change
your capabilities - you always have full access. It just sets initial context:

- **general**: Default, full flexibility
- **homework**: Focus on LaTeX, transcription, Overleaf workflows
- **research**: Focus on exploration, analysis, documentation
- **writing**: Focus on content creation, drafting, editing

### Key Principles

1. **You decide** - No hard-coded rules about what's "quick" vs "heavy"
2. **Continuous spectrum** - Tasks aren't discrete categories
3. **User experience first** - Quick ACK is better than long wait
4. **Unified brain** - All instances share state, learn together
```

### 4. Parallel Task Tracking

**Schema addition:**
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
    notification_sent BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (queue_message_id) REFERENCES discord_message_queue(id)
);
```

### 5. Focus Prompts

**Location:** `prompts/focus/`

These are NOT different agents - they're context primers for the same universal agent.

```
prompts/focus/
├── general.md      # Default - full flexibility
├── homework.md     # LaTeX, transcription, Overleaf focus
├── research.md     # Exploration, analysis focus
├── writing.md      # Content creation focus
└── system.md       # System administration focus
```

**Example: `homework.md`**
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

## Quality Checks
- Verify LaTeX compiles
- Check mathematical notation
- Ensure all problems transcribed

Remember: You have FULL PCP capabilities. This focus just sets initial context.
```

---

## Implementation Plan

### Phase 1: Infrastructure (Queue + Schema)
- [ ] Create `message_queue.py` with full API
- [ ] Add schema to `schema_v2.py`
- [ ] Run migrations
- [ ] Unit tests for queue operations

### Phase 2: Orchestrator Service
- [ ] Create `pcp_orchestrator.py`
- [ ] Implement worker pool management
- [ ] Add Discord webhook integration
- [ ] Add process timeout handling
- [ ] Create systemd service file

### Phase 3: Discord Bot Updates
- [ ] Modify bot to enqueue messages (not process directly)
- [ ] Update reaction handling for new states
- [ ] Remove lock-based concurrency (queue handles this)
- [ ] Add queue status commands

### Phase 4: Agent Prompt Updates
- [ ] Update CLAUDE.md with agentic execution model
- [ ] Create focus prompt files
- [ ] Update Task tool usage for parallel spawning
- [ ] Test prompt effectiveness

### Phase 5: Integration & Testing
- [ ] End-to-end message flow test
- [ ] Parallel execution test
- [ ] Failure recovery test
- [ ] Load test (multiple concurrent messages)
- [ ] User experience validation

### Phase 6: Migration
- [ ] Deploy queue system
- [ ] Switch Discord bot to queue mode
- [ ] Start orchestrator service
- [ ] Monitor and tune
- [ ] Document operational procedures

---

## Verification Checklist

### Functional Requirements
- [ ] Messages are never lost (queue persistence)
- [ ] Multiple messages can be processed in parallel
- [ ] Agent decides routing (no hard-coded rules)
- [ ] Quick tasks get quick responses
- [ ] Heavy tasks get immediate ACK + background processing
- [ ] All instances share state
- [ ] Results are delivered via Discord

### Non-Functional Requirements
- [ ] ACK within 30 seconds for all messages
- [ ] Queue survives service restarts
- [ ] Graceful handling of process failures
- [ ] Proper cleanup of old messages
- [ ] Observable (logs, metrics)

### User Experience
- [ ] Clear feedback at every stage (reactions)
- [ ] No "Agent Busy" message loss
- [ ] Parallel tasks complete and notify
- [ ] System feels responsive

---

## Rollback Plan

If issues arise:
1. Stop orchestrator service
2. Revert Discord bot to direct processing mode
3. Queue messages will be preserved
4. Can replay queue once fixed

---

## Future Enhancements

- **Priority queuing**: Urgent messages processed first
- **Smart batching**: Combine related messages
- **Predictive spawning**: Pre-spawn workers based on patterns
- **Cross-device sync**: Queue accessible from mobile
- **Voice input**: Queue voice transcriptions

---

*Document Version: 4.0 - Universal Agent Architecture*
