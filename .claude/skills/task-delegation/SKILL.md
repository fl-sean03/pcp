---
name: task-delegation
description: Delegate long-running tasks to background processing using native subagents or the legacy worker pattern. Use when operations will take more than 30 seconds, involve multi-step workflows, or require extended processing like transcription, bulk file processing, or complex document creation.
allowed-tools: Read, Write, Bash
---

# Task Delegation

Delegate complex tasks to background processing so you can stay responsive.

## Architecture

```
Discord Message → You (main agent) → Quick response
                                   ↓
                          (if complex task)
                                   ↓
                          delegate_task()
                                   ↓
                          pcp_supervisor (systemd service)
                                   ↓
                          Spawns Claude worker session
                                   ↓
                          Worker completes task
                                   ↓
                          Discord webhook notification
```

**The supervisor runs continuously as a systemd service (`pcp-supervisor`)** and processes delegated tasks.

## Quick Decision: Delegate or Not?

| Do Directly (< 30s) | Delegate to Background (> 30s) |
|---------------------|-------------------------------|
| Search vault | Process multiple files |
| List tasks | Transcribe images to LaTeX |
| Add capture | Research and write report |
| Generate brief | Create workspace/project |
| Quick lookup | Bulk document processing |
| Show person info | Multi-step workflows |

## ⚠️ CRITICAL: Never Use Task Tool with run_in_background

**Claude Code's Task tool with `run_in_background=true` is BROKEN for Discord.**
The subprocess dies when your session ends (seconds after responding).

**ALWAYS use `delegate_task()` or `background_task()` instead.**

## How to Delegate

### Option 1: Simple (Recommended)

```python
from task_delegation import background_task

# One line does everything
ack, task_id = background_task("Research React state management libraries")
# Just respond with: ack
# → "Got it - I'll research react state management libraries. I'll message you when it's ready."
```

### Option 2: Full Control

```python
from task_delegation import delegate_task

task_id = delegate_task(
    description="""
    Research React state management libraries (Redux, Zustand, Jotai, Recoil, MobX).
    Compare their bundle size, learning curve, TypeScript support.
    Write a summary with recommendations.
    """,
    context={
        "original_request": "Research the best React state management libraries",
        "format": "markdown comparison"
    },
    discord_channel_id="DISCORD_CHANNEL_ID",
    priority=5
)
# Then acknowledge: "Got it! I'll research that and message you when it's ready."
```

### Step 3: The supervisor handles the rest

The `pcp_supervisor` systemd service:
1. Polls for pending tasks every 30s
2. Claims and runs tasks via `docker exec pcp-agent claude ...`
3. Posts results to Discord via webhook
4. Marks task as completed

## Key Functions

```python
from task_delegation import delegate_task, get_task, list_tasks

# Create a task
task_id = delegate_task(
    description="What needs to be done",
    context={"any": "relevant context"},
    discord_channel_id="DISCORD_CHANNEL_ID",  # For notification
    priority=5  # 1=urgent, 10=low
)

# Check task status
task = get_task(task_id)
print(task['status'])  # pending, claimed, running, completed, failed

# List tasks
pending = list_tasks(status='pending')
recent = list_tasks(limit=10, include_completed=True)
```

## Task Chains (Dependencies)

For multi-step workflows:

```python
from task_delegation import create_task_chain

task_ids = create_task_chain([
    {"description": "Extract text from PDF"},
    {"description": "Convert to LaTeX", "depends_on": [0]},
    {"description": "Push to Overleaf", "depends_on": [1]}
])
# Tasks execute in order as dependencies complete
```

## Priority Levels

| Priority | Use For |
|----------|---------|
| 1-2 | Urgent, time-sensitive |
| 3-4 | Important, user waiting |
| 5 | Normal (default) |
| 6-7 | Background, not urgent |
| 8-10 | Low priority, whenever |

## Checking Status

```bash
# CLI commands
python scripts/pcp_supervisor.py --status
python scripts/task_delegation.py list
python scripts/task_delegation.py get 42
```

```python
# Python
from task_delegation import get_task, list_tasks, get_pending_count

count = get_pending_count()
tasks = list_tasks(status='running')
```

## Service Management

```bash
# Check supervisor status
sudo systemctl status pcp-supervisor

# View logs
tail -f /workspace/logs/supervisor.log

# Restart if needed
sudo systemctl restart pcp-supervisor
```

## Example: Full Delegation Flow

```
User: "Transcribe this homework to Overleaf" [with PDF attachment]

You:
1. Save attachment to /workspace/vault/files/
2. Acknowledge: "I'll transcribe this to Overleaf and create a project for you!"
3. Call delegate_task():
   ```python
   delegate_task(
       description="Transcribe homework PDF to LaTeX and create Overleaf project",
       context={
           "file_path": "/workspace/vault/files/homework.pdf",
           "original_request": "Transcribe to Overleaf"
       },
       discord_channel_id="DISCORD_CHANNEL_ID",
       priority=3
   )
   ```
4. The supervisor picks it up, spawns a worker, transcribes, creates Overleaf project
5. Worker posts to Discord: "Task #42 completed! Your Overleaf project is ready..."
```

## Related Files

| File | Purpose |
|------|---------|
| `scripts/task_delegation.py` | Core delegation functions |
| `scripts/pcp_supervisor.py` | Background task processor |
| `/etc/systemd/system/pcp-supervisor.service` | Systemd service |
| `logs/supervisor.log` | Supervisor logs |
