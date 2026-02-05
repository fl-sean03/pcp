# PCP Self-Reflection System

## Overview

The Self-Reflection System is PCP's mechanism for continuous self-improvement. Rather than using hardcoded pattern detection or rule-based analysis, it leverages Claude's intelligence to analyze raw usage data, understand gaps between vision and reality, and propose improvements ranging from quick fixes to major architectural changes.

**Core Philosophy**: The analyzer IS just another Claude session with the right context loaded. No programmatic pattern matching - pure agentic intelligence applied to self-improvement.

---

## Design Principles

### 1. Vision-Driven Analysis
Every recommendation must trace back to the PCP vision. The reflection agent should deeply understand what PCP is trying to become and evaluate current state against that north star.

### 2. Evidence-Based Recommendations
All suggestions must cite actual usage data - specific Discord messages, patterns in captures, friction points observed. No theoretical improvements without grounding in real usage.

### 3. Scope Spectrum
Recommendations span the full range:
- **Quick wins** (< 30 min): Add a knowledge entry, fix a prompt, adjust a threshold
- **Medium improvements** (1-4 hours): New helper function, schema addition, skill refinement
- **Major proposals** (1+ days): Architectural changes, new subsystems, workflow redesigns
- **Wild ideas** (exploratory): Things to research, experiment with, or consider for future

### 4. Agentic Intelligence
The reflection agent has full access to:
- Read all code and documentation
- Search and explore the codebase
- Analyze data patterns
- Brainstorm freely without constraints
- Propose changes I (the user) wouldn't have thought of

### 5. Human-in-the-Loop
All recommendations require approval before implementation. The system surfaces insights; humans decide what to act on.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA AGGREGATION LAYER                       │
│                    (export_reflection_context.py)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Discord    │  │    Vault     │  │   Session    │           │
│  │   History    │  │    State     │  │  Transcripts │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│         │                 │                 │                    │
│         ▼                 ▼                 ▼                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Unified Context Export (JSON)               │    │
│  │  - Raw conversations (chronological)                     │    │
│  │  - Vault snapshot (captures, tasks, knowledge, etc.)     │    │
│  │  - System docs (VISION.md, CLAUDE.md, schema)            │    │
│  │  - Previous reflection outputs                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     REFLECTION SESSION                           │
│                    (Claude Code subagent)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Context Provided:                                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 1. VISION.md - The north star, what PCP should become   │    │
│  │ 2. CLAUDE.md - Current capabilities and patterns        │    │
│  │ 3. Usage data export - Raw Discord conversations        │    │
│  │ 4. Vault snapshot - Current state of all data           │    │
│  │ 5. Schema - Database structure                          │    │
│  │ 6. Previous reflections - What was tried, what worked   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Agent Capabilities:                                             │
│  - Full codebase access (read any file)                         │
│  - Search/grep across all code                                  │
│  - Analyze patterns in data                                     │
│  - Compare vision vs. reality                                   │
│  - Brainstorm without constraints                               │
│  - Propose code changes with diffs                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RECOMMENDATION OUTPUT                          │
│                   (Markdown report + structured data)            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Output Structure:                                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 1. Executive Summary                                     │    │
│  │    - Key findings (3-5 bullets)                         │    │
│  │    - Overall health assessment                          │    │
│  │    - Top priority recommendation                        │    │
│  │                                                          │    │
│  │ 2. Vision Alignment Assessment                          │    │
│  │    - What's working well toward the vision              │    │
│  │    - Gaps between current state and vision              │    │
│  │    - Opportunities to better fulfill the vision         │    │
│  │                                                          │    │
│  │ 3. Usage Pattern Analysis                               │    │
│  │    - How the user actually uses PCP                         │    │
│  │    - Friction points observed                           │    │
│  │    - Features used vs. underutilized                    │    │
│  │                                                          │    │
│  │ 4. Quick Wins (< 30 min)                                │    │
│  │    - Immediate improvements with low effort             │    │
│  │                                                          │    │
│  │ 5. Medium Improvements (1-4 hours)                      │    │
│  │    - Meaningful enhancements worth scheduling           │    │
│  │                                                          │    │
│  │ 6. Major Proposals (1+ days)                            │    │
│  │    - Architectural changes or new capabilities          │    │
│  │                                                          │    │
│  │ 7. Wild Ideas                                           │    │
│  │    - Exploratory concepts, research directions          │    │
│  │    - Things that might transform PCP                    │    │
│  │                                                          │    │
│  │ 8. Anti-Recommendations                                 │    │
│  │    - What NOT to do                                     │    │
│  │    - Patterns to avoid                                  │    │
│  │    - Complexity to resist                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STORAGE & TRACKING                          │
│                  (reflection_history table)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Each reflection session is stored:                              │
│  - Session ID, timestamp, period analyzed                       │
│  - Full report (markdown)                                       │
│  - Structured recommendations (JSON)                            │
│  - Status of each recommendation (pending/approved/rejected/    │
│    implemented/deferred)                                        │
│  - Outcome notes (what happened after implementation)           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     HUMAN REVIEW & APPROVAL                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Delivered via:                                                  │
│  - Discord message with summary and link to full report         │
│  - Weekly brief includes pending recommendations                │
│  - Direct conversation: "review my latest reflection"           │
│                                                                  │
│  User responds:                                                  │
│  - "Approve #1, #3, #5" → Marks for implementation              │
│  - "Reject #2" → Records rejection with reason                  │
│  - "Modify #4 to..." → Refines recommendation                   │
│  - "Defer #6" → Saves for later consideration                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      IMPLEMENTATION                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  For approved recommendations:                                   │
│  - Claude implements the change in pcp-dev                      │
│  - Runs tests to validate                                       │
│  - Deploys to production after verification                     │
│  - Records outcome in reflection history                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Sources

### 1. Discord Message History

**Location**: `/srv/agentops/data/discord-archive/messages.db` (SQLite)

**What to Extract**:
- All messages from/to the user in the reflection period
- Chronological conversation threads
- Attachments metadata
- Response times (how long did PCP take?)
- Error messages and retries

**Why It Matters**: Discord is the primary interface. Understanding how the user actually talks to PCP reveals:
- Natural language patterns
- Implicit expectations
- Friction when things don't work
- Features requested but not available
- Things the user does manually that could be automated

### 2. Vault State

**Location**: `/workspace/vault/vault.db` (SQLite)

**What to Extract**:
- Recent captures (with types, entities, timestamps)
- Tasks (created, completed, overdue, abandoned)
- Knowledge entries (categories, frequency of access)
- People (interaction patterns, staleness)
- Projects (health, activity levels)
- Emails (actionable vs processed)
- Patterns detected

**Why It Matters**: Shows what PCP actually stores and how data is structured. Reveals:
- What the user captures most
- Task completion patterns
- Knowledge growth
- Relationship tracking effectiveness
- Project engagement levels

### 3. Session Transcripts

**Location**: Claude session files (if available) or reconstructed from Discord

**What to Extract**:
- Full conversation flows
- Tool usage patterns
- Subagent delegations
- Errors and retries
- Processing times

**Why It Matters**: Shows HOW PCP handles requests, not just WHAT it handles. Reveals:
- Common tool sequences
- Failure patterns
- Efficiency opportunities
- Over/under-delegation patterns

### 4. System Documentation

**Files**:
- `/workspace/VISION.md` - The north star
- `/workspace/CLAUDE.md` - Current capabilities
- `/workspace/scripts/schema_v2.py` - Data model
- `/workspace/docs/*.md` - Architecture and guides

**Why It Matters**: Understanding intended design vs. actual implementation. The gap between vision and reality is where opportunities live.

### 5. Previous Reflections

**Location**: `reflection_history` table in vault.db

**What to Extract**:
- Past recommendations and their outcomes
- What worked, what didn't
- Patterns in approved vs rejected suggestions
- Evolution of the system over time

**Why It Matters**: Learning from history. Avoid repeating failed experiments. Build on successful patterns.

---

## The Reflection Prompt

The prompt is the heart of the system. It must guide Claude to:
1. Deeply understand the vision
2. Analyze usage patterns objectively
3. Think creatively about improvements
4. Be specific and actionable
5. Consider full scope (quick wins to architecture)

### Prompt Structure

```markdown
# PCP Self-Reflection Session

You are analyzing the user's Personal Control Plane (PCP) to identify opportunities for improvement.

## Your Mission

1. **Understand the Vision**: Read VISION.md deeply. This is what PCP is becoming.
2. **Assess Current State**: Review CLAUDE.md, the codebase, and actual usage.
3. **Analyze Usage**: Study the Discord conversations and vault data.
4. **Identify Opportunities**: Find gaps, friction, underutilized potential.
5. **Propose Improvements**: From quick wins to architectural changes.
6. **Think Beyond**: Suggest things the user wouldn't have thought of.

## Context Files Provided

1. **VISION.md**: The north star - what PCP should ultimately become
2. **CLAUDE.md**: Current capabilities and how PCP works today
3. **Usage Data**: {days} days of Discord conversations (JSON)
4. **Vault Snapshot**: Current state of captures, tasks, knowledge, etc.
5. **Schema**: Database structure (schema_v2.py)
6. **Previous Reflections**: Past analyses and their outcomes

## Analysis Framework

### Phase 1: Vision Alignment
- What aspects of the vision are well-implemented?
- What aspects are missing or underdeveloped?
- Are there capabilities that don't serve the vision? (bloat)
- What would move PCP closer to the vision?

### Phase 2: Usage Pattern Analysis
Read through the Discord conversations carefully. Look for:
- **Repeated patterns**: Things the user does often
- **Friction points**: Retries, clarifications, errors, "that's not what I meant"
- **Manual workarounds**: Things the user does that PCP could automate
- **Underutilized features**: Capabilities the user rarely uses (why?)
- **Missing capabilities**: Things the user asks for that don't exist
- **Language patterns**: How the user naturally phrases things

### Phase 3: Technical Assessment
Explore the codebase:
- Code quality and maintainability
- Performance bottlenecks
- Error handling gaps
- Testing coverage
- Architectural coherence

### Phase 4: Creative Exploration
Think freely:
- What would make PCP 10x more valuable?
- What's the "obvious" improvement no one has suggested?
- What could PCP do that would surprise and delight?
- What integrations or capabilities would be transformative?
- How could PCP better learn and adapt?

## Output Requirements

### Format
Produce a structured report with these sections:

1. **Executive Summary** (5-7 bullets)
   - Key findings
   - Overall health assessment
   - Top 3 priorities

2. **Vision Alignment**
   - Working well (with evidence)
   - Gaps identified (with evidence)
   - Opportunities

3. **Usage Analysis**
   - How the user uses PCP (patterns)
   - Friction observed (with specific examples from conversations)
   - Feature utilization assessment

4. **Quick Wins** (< 30 min each)
   Format for each:
   ```
   ### QW-1: [Title]
   **Observation**: What you noticed
   **Evidence**: Specific messages/data
   **Proposal**: What to change
   **Implementation**: Concrete steps
   ```

5. **Medium Improvements** (1-4 hours each)
   Same format, plus:
   - Files affected
   - Testing approach

6. **Major Proposals** (1+ days each)
   Same format, plus:
   - Architecture impact
   - Migration considerations
   - Risk assessment

7. **Wild Ideas**
   - Exploratory concepts
   - Things to research
   - Future possibilities

8. **Anti-Recommendations**
   - What to avoid
   - Complexity to resist
   - Temptations to skip

## Guidelines

- **Be specific**: Reference actual messages, line numbers, specific issues
- **Be actionable**: Every recommendation should be implementable
- **Be honest**: If something is working well, say so. If it's broken, say so.
- **Think independently**: Don't just echo what's in the docs - form your own assessment
- **Consider tradeoffs**: Every change has costs. Acknowledge them.
- **Prioritize ruthlessly**: What matters most? What can wait?

## Remember

PCP's philosophy:
- Minimal hardcoded rules - Claude handles intelligence
- Zero friction - just talk naturally
- Proactive value - add insight without being asked
- Continuous evolution - learn and adapt

Your recommendations should align with these principles.
```

---

## Scheduling

### Weekly Reflection Schedule

For the next 3 months, reflections run weekly:

**When**: Every Sunday at 10:00 PM (end of week, before Monday planning)

**Period Analyzed**: Previous 7 days

**Delivery**:
- Summary posted to Discord (the user's DM channel)
- Full report saved to `/workspace/vault/reflections/`
- Recommendations tracked in `reflection_history` table

### Trigger Methods

1. **Scheduled (cron)**
   ```bash
   # Every Sunday at 10 PM
   0 22 * * 0 cd /workspace && python scripts/trigger_reflection.py --weekly
   ```

2. **On-Demand (Discord)**
   ```
   "@a5sBot reflect" or "@a5sBot self-reflect"
   → Triggers immediate reflection for last 7 days

   "@a5sBot reflect --days 30"
   → Custom period
   ```

3. **Programmatic**
   ```python
   from reflection import trigger_reflection

   # Weekly reflection
   result = trigger_reflection(days=7)

   # Monthly deep dive
   result = trigger_reflection(days=30, deep=True)
   ```

---

## Database Schema Addition

Add to `schema_v2.py`:

```python
# Reflection history table
"""
CREATE TABLE IF NOT EXISTS reflection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    days_analyzed INTEGER NOT NULL,

    -- Full report content
    report_markdown TEXT,

    -- Structured data
    recommendations JSON,  -- Array of recommendation objects
    metrics JSON,          -- Usage stats, health scores

    -- Status tracking
    status TEXT DEFAULT 'pending_review',  -- pending_review, reviewed, actioned
    reviewed_at TEXT,
    reviewed_notes TEXT,

    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    agent_model TEXT,      -- Which Claude model ran the reflection
    context_tokens INTEGER, -- How much context was used

    -- Links
    discord_message_id TEXT  -- Message ID where summary was posted
);

-- Individual recommendations with status tracking
CREATE TABLE IF NOT EXISTS reflection_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reflection_id INTEGER NOT NULL,

    -- Recommendation content
    recommendation_id TEXT NOT NULL,  -- e.g., "QW-1", "MP-3"
    category TEXT NOT NULL,           -- quick_win, medium, major, wild_idea, anti
    title TEXT NOT NULL,
    observation TEXT,
    evidence TEXT,
    proposal TEXT,
    implementation TEXT,

    -- Status
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected, implemented, deferred
    status_updated_at TEXT,
    status_notes TEXT,

    -- Outcome tracking (for implemented recommendations)
    outcome TEXT,
    outcome_date TEXT,
    outcome_assessment TEXT,  -- positive, negative, neutral, mixed

    -- Metadata
    priority INTEGER,  -- 1 = highest
    effort_estimate TEXT,  -- "30min", "2h", "1d", etc.

    FOREIGN KEY (reflection_id) REFERENCES reflection_history(id)
);

-- Index for querying
CREATE INDEX IF NOT EXISTS idx_recommendations_status
ON reflection_recommendations(status);

CREATE INDEX IF NOT EXISTS idx_recommendations_category
ON reflection_recommendations(category);
```

---

## Implementation Files

### 1. export_reflection_context.py

**Location**: `/workspace/scripts/export_reflection_context.py`

**Purpose**: Aggregates all data sources into a unified context export for the reflection agent.

**Functions**:

```python
def export_for_reflection(days: int = 7, output_path: str = None) -> dict:
    """
    Export all context needed for a reflection session.

    Args:
        days: Number of days to analyze
        output_path: Optional path to save JSON export

    Returns:
        dict with all context data
    """

def get_discord_history(days: int) -> list[dict]:
    """
    Get Discord messages from archive database.
    Returns chronological list of conversations.
    """

def get_vault_snapshot() -> dict:
    """
    Get current state of vault:
    - Recent captures
    - All tasks with status
    - Knowledge entries
    - People with relationship data
    - Projects with health
    - Emails
    """

def get_session_transcripts(days: int) -> list[dict]:
    """
    Get Claude session transcripts if available.
    Reconstructs conversation flows.
    """

def get_previous_reflections(limit: int = 5) -> list[dict]:
    """
    Get recent reflection history for context.
    Includes outcomes of past recommendations.
    """

def get_friction_events(days: int) -> list[dict]:
    """
    Identify potential friction events:
    - Messages followed by quick retries
    - Error responses
    - Clarification requests
    - Long response times
    """

def calculate_usage_metrics(days: int) -> dict:
    """
    Calculate high-level metrics:
    - Messages per day
    - Capture rate
    - Task completion rate
    - Feature usage frequency
    - Response time distribution
    """
```

### 2. reflection_prompt.md

**Location**: `/workspace/prompts/reflection_prompt.md`

**Purpose**: The master prompt template for reflection sessions.

**Content**: Full prompt as specified in "The Reflection Prompt" section above.

### 3. trigger_reflection.py

**Location**: `/workspace/scripts/trigger_reflection.py`

**Purpose**: Orchestrates the reflection process.

**Functions**:

```python
def trigger_reflection(
    days: int = 7,
    deep: bool = False,
    notify_discord: bool = True,
    channel_id: str = None
) -> dict:
    """
    Trigger a reflection session.

    Args:
        days: Period to analyze
        deep: If True, use more thorough analysis (longer context)
        notify_discord: Send summary to Discord when complete
        channel_id: Discord channel for notification

    Returns:
        dict with reflection results and session ID
    """

def spawn_reflection_agent(context_file: str, output_file: str) -> str:
    """
    Spawn the reflection subagent with provided context.
    Returns session ID.
    """

def parse_reflection_output(report_path: str) -> dict:
    """
    Parse the reflection report into structured data.
    Extracts recommendations, categories, priorities.
    """

def store_reflection(session_id: str, report: str, recommendations: list) -> int:
    """
    Store reflection in database.
    Returns reflection_history.id
    """

def notify_reflection_complete(
    reflection_id: int,
    channel_id: str,
    summary: str
) -> bool:
    """
    Post reflection summary to Discord.
    """
```

### 4. manage_reflections.py

**Location**: `/workspace/scripts/manage_reflections.py`

**Purpose**: CLI for viewing and managing reflections.

**Commands**:

```bash
# View recent reflections
python manage_reflections.py list

# View specific reflection
python manage_reflections.py view <reflection_id>

# View pending recommendations
python manage_reflections.py pending

# Approve recommendations
python manage_reflections.py approve <reflection_id> --items "QW-1,QW-3,MP-2"

# Reject with reason
python manage_reflections.py reject <reflection_id> --item QW-2 --reason "Not worth the complexity"

# Defer for later
python manage_reflections.py defer <reflection_id> --item MP-4 --until "next quarter"

# Mark as implemented
python manage_reflections.py implemented <reflection_id> --item QW-1 --outcome "Worked great"

# Get stats
python manage_reflections.py stats
```

---

## Integration Points

### Weekly Brief Integration

Add reflection summary to weekly brief:

```python
# In brief.py
def generate_weekly_summary():
    # ... existing code ...

    # Add reflection section
    pending_recommendations = get_pending_recommendations()
    if pending_recommendations:
        brief["pending_improvements"] = pending_recommendations
```

### Discord Command Integration

Add reflection commands to Discord bot:

```python
# Commands:
# @a5sBot reflect - Trigger immediate reflection
# @a5sBot recommendations - Show pending recommendations
# @a5sBot approve QW-1, MP-2 - Approve specific items
# @a5sBot reflection status - Show recent reflection info
```

### Proactive Integration

Could trigger reflection automatically when:
- Friction events exceed threshold
- Usage patterns change significantly
- Major errors occur repeatedly

---

## Testing Strategy

### Unit Tests

1. **Data Export Tests**
   - Export functions return correct structure
   - Date filtering works
   - Missing data handled gracefully

2. **Storage Tests**
   - Reflections stored correctly
   - Recommendations tracked
   - Status updates work

3. **Parsing Tests**
   - Report parsing handles various formats
   - Recommendation extraction works

### Integration Tests

1. **Full Flow Test**
   - Export context
   - Mock reflection agent response
   - Parse and store
   - Verify notifications

2. **Discord Integration**
   - Commands trigger correctly
   - Notifications delivered

### Manual Validation

1. **Quality Assessment**
   - Are recommendations actionable?
   - Is evidence properly cited?
   - Does prioritization make sense?

---

## Rollout Plan

### Phase 1: Foundation (This Implementation)
- Export script
- Prompt template
- Trigger script
- Database schema
- Basic CLI

### Phase 2: Integration
- Discord commands
- Weekly brief integration
- Cron scheduling

### Phase 3: Feedback Loop
- Outcome tracking
- Trend analysis across reflections
- Automatic learning from approved/rejected patterns

---

## Success Metrics

How to know if the reflection system is working:

1. **Recommendation Quality**
   - % of recommendations approved (target: >60%)
   - % implemented successfully (target: >80% of approved)

2. **System Improvement**
   - Decrease in friction events over time
   - Increase in feature utilization
   - Faster response times

3. **Vision Alignment**
   - Qualitative assessment each month
   - Progress on VISION.md phase goals

4. **User Satisfaction**
   - the user's engagement with recommendations
   - Feedback on reflection quality

---

## Example Reflection Output

```markdown
# PCP Self-Reflection: Week of January 21-28, 2026

## Executive Summary

- **Overall Health**: Good with opportunities for improvement
- **Key Finding**: File organization requests are highly repetitive - prime automation target
- **Top Priority**: Implement course-to-folder mapping (QW-1)
- **Vision Gap**: Proactive insights underutilized - only 2 proactive messages this week

## Vision Alignment

### Working Well
- **Universal Capture**: 47 captures this week, all correctly categorized
- **Task Management**: 12 tasks created, 8 completed (67% rate)
- **Discord Interface**: Natural conversation flow, minimal command syntax

### Gaps Identified
- **Proactive Intelligence**: Vision says "adds value without being asked" but only 2 proactive
  messages this week. Pattern detection exists but doesn't surface insights.
- **Cloud Storage Integration**: OneDrive features exist but underutilized. The user manually
  navigated folders 4 times when PCP could have helped.
- **Self-Evolution**: Vision mentions learning patterns, but "the user's Patterns" section of
  CLAUDE.md hasn't been updated in 15 days.

## Usage Analysis

### Patterns Observed
1. **Homework workflow is primary use case** (62% of messages)
2. **File organization requests repeat** ("save to proper folder" 4x this week)
3. **Morning brief requested at 8:30 AM average**
4. **Most captures happen between 2-5 PM**

### Friction Observed
1. **Jan 28, 15:27**: Attachment not detected on first try
   > "I don't see any attachment in this message"
   The user had to resend with @mention

2. **Jan 25, 11:15**: Task due date ambiguity
   > User: "due Friday, complete Thursday"
   Only Friday captured, Thursday target lost

## Quick Wins

### QW-1: Course-to-Folder Mapping
**Observation**: 4 requests to save files to course folders this week
**Evidence**: Jan 28 "save to proper folder", Jan 25 "put in CHEN folder"...
**Proposal**: Store folder mappings in knowledge base, auto-suggest on file receipt
**Implementation**:
1. Add knowledge entries: `CHEN5838 → Desktop/CHEN5838/`
2. Modify file processing to query knowledge for folder
3. Auto-suggest: "Save to Desktop/CHEN5838/? (y/n)"

### QW-2: Soft Deadline Field
**Observation**: "due X, complete Y" pattern appears 6 times
**Evidence**: "Due friday, complete thursday before class"
**Proposal**: Add target_date column to tasks table
**Implementation**:
1. ALTER TABLE tasks ADD COLUMN target_date TEXT
2. Update smart_capture to parse "complete by" / "finish before"
3. Show target_date in task displays

## Medium Improvements

### MP-1: Attachment Detection Fix
**Observation**: Attachments missed when sent without @mention in same message
**Evidence**: Jan 28 15:27 - PS3.pdf not detected
**Proposal**: Check recent messages for orphaned attachments when context suggests file expected
**Implementation**:
1. In Discord adapter, maintain 60-second attachment buffer per user
2. When message mentions file but none attached, check buffer
3. Associate attachment if contextually relevant
**Files**: `/srv/agentops/services/agent-gateway/adapters/discord/`
**Testing**: Send attachment, then follow-up message mentioning it

## Major Proposals

### MP-1: Proactive Insight Delivery
**Observation**: Pattern detection exists but doesn't reach user proactively
**Evidence**: patterns.py generates insights, but they only appear in briefs
**Proposal**: Real-time proactive messages when significant patterns detected
**Architecture**:
```
Pattern detected → Threshold check → Queue for delivery →
Rate limit (max 3/day) → Deliver via Discord
```
**Implementation**: ~4 hours
- Create `proactive_delivery.py` with rate limiting
- Hook into pattern detection
- Add Discord notification channel

## Wild Ideas

1. **Voice Memos**: What if the user could send voice messages that get transcribed and captured?
2. **Calendar Integration**: Could PCP know about upcoming classes and pre-load context?
3. **Study Partner Tracking**: Track study groups per course (John for QUANTUM, etc.)

## Anti-Recommendations

1. **Don't add more brief types** - Daily, weekly, EOD is enough. Resist feature creep.
2. **Don't build custom file browser** - Use OneDrive integration, don't recreate.
3. **Don't auto-send emails** - Keep human in loop for external communication.
```

---

## Appendix: Why Weekly for 3 Months?

- **Rapid iteration**: PCP is actively evolving, weekly catches issues fast
- **Pattern emergence**: Need multiple data points to see real patterns
- **Feedback loop**: Quick approval/rejection improves recommendation quality
- **After 3 months**: Evaluate if weekly is too frequent, adjust to bi-weekly or monthly

---

*Document Version: 1.0*
*Created: 2026-01-28*
*Author: Claude (via the user's instruction)*
