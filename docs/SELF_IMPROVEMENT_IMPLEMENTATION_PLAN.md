# PCP Self-Improvement System - Implementation Plan

**Status:** Implemented
**Created:** 2026-02-01
**Implemented:** 2026-02-01
**Author:** Claude + User

---

## Executive Summary

This document outlines the implementation plan for PCP's autonomous self-improvement capabilities. The system will enable PCP to:

1. **Detect capability gaps** when attempting tasks it cannot complete
2. **Autonomously acquire** missing capabilities (when safe to do so)
3. **Ask for user input** when credentials, costs, or high-risk actions are involved
4. **Persist new capabilities** as reusable skills
5. **Reflect weekly** on patterns and propose proactive improvements

The goal is to create an **agentic system that gets smarter over time** based on actual usage patterns.

---

## Table of Contents

1. [Current State](#1-current-state)
2. [Target State](#2-target-state)
3. [Architecture](#3-architecture)
4. [Implementation Phases](#4-implementation-phases)
5. [Detailed Design](#5-detailed-design)
6. [Testing Strategy](#6-testing-strategy)
7. [Migration Plan](#7-migration-plan)
8. [Risk Mitigation](#8-risk-mitigation)
9. [Success Metrics](#9-success-metrics)
10. [Timeline](#10-timeline)

---

## 1. Current State

### What Works

| Component | Status | Notes |
|-----------|--------|-------|
| Task Delegation | ✅ Working | `delegate_task()`, `background_task()` |
| Supervisor | ✅ Running | systemd service, processes tasks reliably |
| Discord Notifications | ✅ Working | Webhook notifications on task completion |
| Skill System | ✅ Exists | `skill_loader.py`, can load/validate skills |
| Reflection Scripts | ✅ Exist | `trigger_reflection.py`, tables created |
| Weekly Cron | ❌ Not configured | Documented but not set up |

### What's Missing

| Component | Status | Notes |
|-----------|--------|-------|
| Capability Gap Detection | ❌ Not implemented | No system to detect "I can't do this" |
| Autonomous Acquisition | ❌ Not implemented | No system to acquire new capabilities |
| Risk Assessment | ❌ Not implemented | No framework for ask vs do decisions |
| Self-Improvement Skill | ❌ Not implemented | No skill for "add capability for X" |
| Gap Tracking Database | ❌ Not implemented | No logging of capability gaps |
| Reflection → Task Pipeline | ❌ Not implemented | Reflections don't create tasks |

---

## 2. Target State

### The Vision

```
User sends request
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PCP AGENT (intelligent)                      │
│                                                                 │
│  1. ATTEMPT: Try to complete with current capabilities          │
│     ├─ Success → Done                                           │
│     └─ Failure → Capability Gap Detected                        │
│                                                                 │
│  2. ASSESS: What's missing? Can I get it safely?                │
│     ├─ Low Risk → Acquire autonomously                          │
│     ├─ Medium Risk → Acquire, notify user                       │
│     └─ High Risk → Ask user for permission/input                │
│                                                                 │
│  3. ACQUIRE: Get the capability                                 │
│     ├─ Research solutions                                       │
│     ├─ Implement in pcp-dev                                     │
│     ├─ Test thoroughly                                          │
│     └─ Sync to production                                       │
│                                                                 │
│  4. RETRY: Complete original task with new capability           │
│                                                                 │
│  5. PERSIST: Save as skill for future use                       │
│                                                                 │
│  6. LEARN: Log what happened for weekly reflection              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Behaviors

1. **Try first, ask second** - Don't ask "should I try?" Just try. Ask when blocked.
2. **Learn from every failure** - Every gap is data for improvement
3. **Persist learnings** - Don't solve the same problem twice
4. **Minimize user burden** - Do work autonomously when safe
5. **Be transparent** - Tell user what you're doing

---

## 3. Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PCP SYSTEM                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │  Discord Agent  │────▶│  Task Executor  │────▶│  Skill System   │       │
│  │  (main entry)   │     │  (tries tasks)  │     │  (capabilities) │       │
│  └─────────────────┘     └────────┬────────┘     └─────────────────┘       │
│                                   │                        ▲               │
│                          (capability gap)                  │               │
│                                   │                        │               │
│                                   ▼                        │               │
│  ┌─────────────────────────────────────────────────────────┴───────┐       │
│  │                    SELF-IMPROVEMENT ENGINE                      │       │
│  │                                                                 │       │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │       │
│  │  │ Gap Detector │─▶│Risk Assessor │─▶│  Acquirer    │          │       │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │       │
│  │         │                                    │                  │       │
│  │         ▼                                    ▼                  │       │
│  │  ┌──────────────┐                   ┌──────────────┐           │       │
│  │  │ Gap Tracker  │                   │Skill Creator │───────────┘       │
│  │  │  (database)  │                   │(persistence) │                   │
│  │  └──────────────┘                   └──────────────┘                   │
│  │         │                                                              │
│  └─────────┼──────────────────────────────────────────────────────────────┘
│            │                                                               │
│            ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐      │
│  │                    REFLECTION SYSTEM                            │      │
│  │                                                                 │      │
│  │  Weekly Analysis:                                               │      │
│  │  - Review capability gaps from past week                        │      │
│  │  - Identify patterns (repeated requests, common failures)       │      │
│  │  - Propose proactive improvements                               │      │
│  │  - Create tasks for approved improvements                       │      │
│  │                                                                 │      │
│  └─────────────────────────────────────────────────────────────────┘      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. User Request
   └─▶ Task Executor attempts task
       ├─▶ Success: Return result
       └─▶ CapabilityGapError raised
           └─▶ Self-Improvement Engine
               ├─▶ Detect: What capability is missing?
               ├─▶ Research: How can I acquire it?
               ├─▶ Assess: Risk level?
               │   ├─▶ Low: Proceed autonomously
               │   ├─▶ Medium: Proceed, notify user
               │   └─▶ High: Ask user
               ├─▶ Acquire: Implement in pcp-dev
               │   ├─▶ Create scripts/code
               │   ├─▶ Create skill file
               │   ├─▶ Test
               │   └─▶ Sync to production
               ├─▶ Retry: Complete original task
               └─▶ Log: Record gap and resolution

2. Weekly Cron (Sunday 10 PM)
   └─▶ Reflection System
       ├─▶ Export: Gather usage data
       ├─▶ Analyze: Patterns, gaps, failures
       ├─▶ Propose: Recommendations
       ├─▶ Notify: Post to Discord
       └─▶ (After approval) Create delegated tasks
```

---

## 4. Implementation Phases

### Phase 1: Foundation (Core Infrastructure)

**Goal:** Build the basic capability gap detection and tracking system.

| Task | Description | Effort |
|------|-------------|--------|
| 1.1 | Create `capability_gaps` database table | Small |
| 1.2 | Create `CapabilityGapError` exception class | Small |
| 1.3 | Create `capability_detector.py` module | Medium |
| 1.4 | Create gap pattern library (file types, services, etc.) | Medium |
| 1.5 | Add gap logging to task execution | Small |
| 1.6 | Test: Trigger gaps, verify logging | Medium |

**Deliverables:**
- Database schema for tracking gaps
- Exception class for signaling gaps
- Detection module that identifies common gap patterns
- Logging of all detected gaps

### Phase 2: Risk Assessment Framework

**Goal:** Build the decision framework for "ask vs do".

| Task | Description | Effort |
|------|-------------|--------|
| 2.1 | Create `risk_assessor.py` module | Medium |
| 2.2 | Define risk categories and criteria | Small |
| 2.3 | Create risk assessment rules engine | Medium |
| 2.4 | Add configuration for risk thresholds | Small |
| 2.5 | Test: Various scenarios, verify correct risk levels | Medium |

**Deliverables:**
- Risk assessment module
- Configurable risk rules
- Clear decision framework

### Phase 3: Capability Acquisition Engine

**Goal:** Build the system that actually acquires new capabilities.

| Task | Description | Effort |
|------|-------------|--------|
| 3.1 | Create `capability_acquirer.py` module | Large |
| 3.2 | Research phase: Query knowledge, web search | Medium |
| 3.3 | Implementation phase: Code generation, testing | Large |
| 3.4 | Skill creation: Auto-generate skill files | Medium |
| 3.5 | Dev→Prod sync: Automated deployment | Medium |
| 3.6 | Rollback: Undo failed acquisitions | Medium |
| 3.7 | Test: End-to-end acquisition scenarios | Large |

**Deliverables:**
- Full acquisition pipeline
- Skill auto-generation
- Safe deployment with rollback

### Phase 4: Self-Improvement Skill

**Goal:** Create a skill that handles explicit improvement requests.

| Task | Description | Effort |
|------|-------------|--------|
| 4.1 | Create `self-improvement` skill | Medium |
| 4.2 | Handle "add skill for X" requests | Medium |
| 4.3 | Handle "improve X capability" requests | Medium |
| 4.4 | Integration with acquisition engine | Small |
| 4.5 | Test: Various improvement requests | Medium |

**Deliverables:**
- Self-improvement skill
- Natural language understanding for improvement requests

### Phase 5: Task Execution Wrapper

**Goal:** Wrap task execution to catch gaps and trigger acquisition.

| Task | Description | Effort |
|------|-------------|--------|
| 5.1 | Create `execute_with_self_improvement()` wrapper | Medium |
| 5.2 | Integrate with existing task delegation | Medium |
| 5.3 | Add retry logic after acquisition | Small |
| 5.4 | Add user notification for acquisition events | Small |
| 5.5 | Test: Full flow from gap to retry | Large |

**Deliverables:**
- Seamless integration with existing task system
- Automatic retry after capability acquisition

### Phase 6: Weekly Reflection Integration

**Goal:** Connect reflection system to self-improvement.

| Task | Description | Effort |
|------|-------------|--------|
| 6.1 | Set up weekly cron job | Small |
| 6.2 | Add gap analysis to reflection export | Medium |
| 6.3 | Generate improvement recommendations from gaps | Medium |
| 6.4 | Create delegated tasks for approved recommendations | Medium |
| 6.5 | Discord notification for reflection results | Small |
| 6.6 | Test: Full weekly cycle | Medium |

**Deliverables:**
- Automated weekly reflection
- Gap-informed recommendations
- Seamless task creation from approvals

### Phase 7: Production Migration & Hardening

**Goal:** Migrate to production and ensure reliability.

| Task | Description | Effort |
|------|-------------|--------|
| 7.1 | Sync all changes to pcp | Medium |
| 7.2 | Update CLAUDE.md with new capabilities | Small |
| 7.3 | Update skill documentation | Small |
| 7.4 | Production smoke tests | Medium |
| 7.5 | Monitor for first week | Ongoing |
| 7.6 | Fix any issues discovered | Variable |

**Deliverables:**
- Production-ready system
- Updated documentation
- Monitoring in place

---

## 5. Detailed Design

### 5.1 Database Schema

```sql
-- Track capability gaps as they're detected
CREATE TABLE capability_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- When and what
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    original_task TEXT NOT NULL,           -- What user asked for
    gap_type TEXT NOT NULL,                -- file_type, service, tool, etc.
    gap_description TEXT NOT NULL,         -- Human-readable description

    -- Detection details
    failure_pattern TEXT,                  -- What error/pattern triggered detection
    context JSON,                          -- Additional context

    -- Resolution
    resolution_status TEXT DEFAULT 'pending',  -- pending, in_progress, resolved, failed, user_declined
    resolution_approach TEXT,              -- How we decided to resolve
    risk_level TEXT,                       -- low, medium, high
    user_prompted BOOLEAN DEFAULT FALSE,   -- Did we ask user?
    user_response TEXT,                    -- What user said (if asked)

    -- Outcome
    skill_created TEXT,                    -- Name of skill created (if any)
    resolution_notes TEXT,                 -- What happened
    resolved_at TIMESTAMP,

    -- Indexing
    session_id TEXT                        -- Link to conversation
);

-- Index for weekly analysis
CREATE INDEX idx_gaps_detected ON capability_gaps(detected_at);
CREATE INDEX idx_gaps_status ON capability_gaps(resolution_status);
CREATE INDEX idx_gaps_type ON capability_gaps(gap_type);
```

### 5.2 Capability Gap Patterns

```python
# capability_patterns.py

CAPABILITY_PATTERNS = {
    # File type gaps
    "audio_file": {
        "triggers": [
            {"mime_type": ["audio/*"]},
            {"extension": [".mp3", ".wav", ".m4a", ".ogg", ".flac"]},
        ],
        "gap_type": "file_processing",
        "description": "Audio file processing/transcription",
        "default_risk": "low",
        "suggested_solutions": [
            {"name": "whisper", "type": "local", "install": "pip install openai-whisper"},
            {"name": "deepgram", "type": "api", "requires": ["DEEPGRAM_API_KEY"]},
        ]
    },

    "video_file": {
        "triggers": [
            {"mime_type": ["video/*"]},
            {"extension": [".mp4", ".mov", ".avi", ".mkv"]},
        ],
        "gap_type": "file_processing",
        "description": "Video file processing",
        "default_risk": "low",
        "suggested_solutions": [
            {"name": "ffmpeg", "type": "tool", "install": "apt install ffmpeg"},
        ]
    },

    # Service integrations
    "notion": {
        "triggers": [
            {"text_match": ["notion", "notion.so"]},
        ],
        "gap_type": "service_integration",
        "description": "Notion workspace access",
        "default_risk": "medium",
        "requires_user_input": ["NOTION_API_KEY"],
        "suggested_solutions": [
            {"name": "notion-client", "type": "api", "install": "pip install notion-client"},
        ]
    },

    "slack": {
        "triggers": [
            {"text_match": ["slack", "slack message"]},
        ],
        "gap_type": "service_integration",
        "description": "Slack workspace access",
        "default_risk": "medium",
        "requires_user_input": ["SLACK_BOT_TOKEN"],
    },

    # Cloud providers
    "aws": {
        "triggers": [
            {"text_match": ["aws", "amazon", "ec2", "s3", "lambda"]},
            {"error_match": ["NoCredentialsError", "aws configure"]},
        ],
        "gap_type": "cloud_provider",
        "description": "AWS cloud access",
        "default_risk": "high",
        "requires_user_input": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
    },

    "oracle_cloud": {
        "triggers": [
            {"text_match": ["oracle cloud", "oci", "oracle vm"]},
        ],
        "gap_type": "cloud_provider",
        "description": "Oracle Cloud access",
        "default_risk": "high",
        "requires_user_input": ["OCI config"],
    },

    # CLI tools
    "missing_tool": {
        "triggers": [
            {"error_match": ["command not found", "not recognized", "not installed"]},
        ],
        "gap_type": "cli_tool",
        "description": "Missing CLI tool",
        "default_risk": "low",
        "dynamic_resolution": True,  # Determine tool from error message
    },
}
```

### 5.3 Risk Assessment Rules

```python
# risk_assessor.py

class RiskLevel:
    LOW = "low"       # Just do it
    MEDIUM = "medium" # Do it, notify user
    HIGH = "high"     # Ask user first
    CRITICAL = "critical"  # Require explicit confirmation

RISK_RULES = {
    # Actions that are low risk
    "low_risk_actions": [
        "pip install *",           # Python packages
        "npm install *",           # Node packages
        "create file in workspace",
        "create skill file",
        "modify own code",
        "run tests",
    ],

    # Actions that are medium risk
    "medium_risk_actions": [
        "install system package",  # apt install
        "modify configuration",
        "create new integration",
        "store credentials",       # Even user-provided
    ],

    # Actions that are high risk
    "high_risk_actions": [
        "access external API",     # Could cost money
        "provision cloud resources",
        "send emails/messages",
        "modify production",
        "access user accounts",
    ],

    # Actions that are critical
    "critical_actions": [
        "delete data",
        "expose secrets",
        "irreversible changes",
        "financial transactions",
    ],
}

def assess_risk(action: str, context: dict) -> RiskLevel:
    """
    Assess the risk level of an action.

    Considers:
    - Type of action
    - Whether it requires credentials
    - Whether it costs money
    - Whether it's reversible
    - Whether it affects external systems
    """
    # Implementation details...
```

### 5.4 Acquisition Engine

```python
# capability_acquirer.py

class CapabilityAcquirer:
    """
    Acquires missing capabilities through research, implementation, and testing.
    """

    def acquire(
        self,
        gap: CapabilityGap,
        context: dict
    ) -> AcquisitionResult:
        """
        Main entry point for capability acquisition.

        Flow:
        1. Research solutions
        2. Assess risk
        3. Get user input if needed
        4. Implement in pcp-dev
        5. Test
        6. Create skill
        7. Sync to production
        """

        # 1. Research
        solutions = self.research_solutions(gap)

        # 2. Assess risk
        risk = self.assess_risk(solutions, context)

        # 3. User input if needed
        if risk.requires_user_input:
            user_response = self.prompt_user(risk.prompt)
            if not user_response.approved:
                return AcquisitionResult(
                    success=False,
                    reason="user_declined",
                    message=user_response.message
                )
            context.update(user_response.inputs)

        # 4. Implement
        implementation = self.implement(
            solution=solutions[0],
            context=context,
            in_dev=True  # Always start in pcp-dev
        )

        if not implementation.success:
            return AcquisitionResult(
                success=False,
                reason="implementation_failed",
                error=implementation.error
            )

        # 5. Test
        test_result = self.test(implementation)

        if not test_result.passed:
            self.rollback(implementation)
            return AcquisitionResult(
                success=False,
                reason="tests_failed",
                error=test_result.error
            )

        # 6. Create skill
        skill = self.create_skill(gap, implementation)

        # 7. Sync to production
        sync_result = self.sync_to_production(implementation, skill)

        return AcquisitionResult(
            success=True,
            skill_created=skill.name,
            ready_to_retry=True
        )
```

### 5.5 Task Execution Wrapper

```python
# execute_with_improvement.py

def execute_with_self_improvement(
    task_fn: Callable,
    *args,
    max_acquisition_attempts: int = 1,
    **kwargs
) -> Any:
    """
    Execute a task, and if it fails due to missing capability,
    try to acquire that capability and retry.
    """
    attempts = 0

    while attempts <= max_acquisition_attempts:
        try:
            return task_fn(*args, **kwargs)

        except CapabilityGapError as e:
            attempts += 1

            if attempts > max_acquisition_attempts:
                raise

            # Log the gap
            gap_id = log_capability_gap(
                original_task=task_fn.__name__,
                gap=e
            )

            # Attempt acquisition
            acquirer = CapabilityAcquirer()
            result = acquirer.acquire(
                gap=e.gap,
                context={
                    "args": args,
                    "kwargs": kwargs,
                    "original_task": task_fn.__name__
                }
            )

            if not result.success:
                # Update gap record
                update_gap_status(gap_id, "failed", result.reason)
                raise CapabilityAcquisitionFailed(result.reason)

            # Update gap record
            update_gap_status(gap_id, "resolved", result.skill_created)

            # Notify user
            notify(f"I've acquired {result.skill_created} capability. Retrying your request...")

            # Loop will retry

    raise RuntimeError("Max acquisition attempts exceeded")
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

| Module | Tests |
|--------|-------|
| `capability_detector.py` | Pattern matching, gap identification |
| `risk_assessor.py` | Risk level determination |
| `capability_acquirer.py` | Research, implementation, rollback |
| `skill_creator.py` | Skill file generation |

### 6.2 Integration Tests

| Scenario | Description |
|----------|-------------|
| Audio File Gap | Send audio → detect gap → install whisper → transcribe |
| Missing Tool | Command fails → detect tool → install → retry |
| Service Integration | Request Notion → detect gap → get API key → connect |
| Cloud Provider | Request AWS → detect gap → ask user → configure |

### 6.3 End-to-End Tests

| Test | Steps |
|------|-------|
| Full Acquisition Cycle | 1. Send request that triggers gap<br>2. Verify gap detected<br>3. Verify acquisition starts<br>4. Verify skill created<br>5. Verify original task completes |
| Risk Escalation | 1. Trigger low-risk gap → auto-resolve<br>2. Trigger high-risk gap → verify user prompted |
| Weekly Reflection | 1. Generate test gaps<br>2. Run reflection<br>3. Verify recommendations generated<br>4. Approve recommendation<br>5. Verify task created |

### 6.4 Test Fixtures

```python
# Test scenarios to validate
TEST_SCENARIOS = [
    {
        "name": "audio_transcription",
        "input": "Transcribe this audio file",
        "file": "test.mp3",
        "expected_gap": "audio_file",
        "expected_risk": "low",
        "expected_resolution": "whisper installation"
    },
    {
        "name": "notion_integration",
        "input": "Check my Notion for meeting notes",
        "expected_gap": "notion",
        "expected_risk": "medium",
        "expected_prompt": "NOTION_API_KEY"
    },
    {
        "name": "aws_vm",
        "input": "Spin up an EC2 instance",
        "expected_gap": "aws",
        "expected_risk": "high",
        "expected_prompt": "AWS credentials"
    },
]
```

---

## 7. Migration Plan

### 7.1 Development Phase (pcp-dev)

1. **Implement all phases** in pcp-dev
2. **Run full test suite** for each phase
3. **Manual testing** with real scenarios
4. **Fix issues** before proceeding

### 7.2 Pre-Migration Checklist

- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] End-to-end tests passing
- [ ] Manual testing completed
- [ ] Documentation updated
- [ ] CLAUDE.md updated
- [ ] Skill files updated
- [ ] No breaking changes to existing functionality

### 7.3 Migration Steps

```bash
# 1. Backup production
cp -r /path/to/pcp /path/to/pcp-backup-$(date +%Y%m%d)

# 2. Sync files (selective)
rsync -av --exclude='vault/' --exclude='logs/' \
    /path/to/pcp/dev/ /path/to/pcp/

# 3. Run migrations (if any database changes)
cd /path/to/pcp/scripts
python3 -c "from capability_detector import ensure_schema; ensure_schema()"

# 4. Restart supervisor
sudo systemctl restart pcp-supervisor

# 5. Smoke tests
python3 -c "from capability_detector import detect_gap; print('OK')"
python3 -c "from risk_assessor import assess_risk; print('OK')"
python3 -c "from capability_acquirer import CapabilityAcquirer; print('OK')"
```

### 7.4 Post-Migration Validation

1. **Create test task** that triggers a known gap
2. **Verify detection** works
3. **Verify acquisition** completes
4. **Verify skill created** and works
5. **Check Discord** notifications

### 7.5 Rollback Plan

If issues are discovered:

```bash
# Restore from backup
rm -rf /path/to/pcp
mv /path/to/pcp-backup-YYYYMMDD /path/to/pcp

# Restart supervisor
sudo systemctl restart pcp-supervisor
```

---

## 8. Risk Mitigation

### 8.1 Technical Risks

| Risk | Mitigation |
|------|------------|
| Acquisition creates broken skill | Test in pcp-dev first; rollback on failure |
| Infinite loop (gap → acquire → gap) | Max acquisition attempts limit |
| User credentials mishandled | Store in vault with encryption |
| Production disruption | Backup before migration; quick rollback |

### 8.2 Operational Risks

| Risk | Mitigation |
|------|------------|
| Unexpected costs (API calls) | High-risk classification for paid services |
| Security exposure | Never auto-acquire credentials; always ask |
| Breaking existing functionality | Comprehensive test suite |

### 8.3 Guardrails

```python
# Safety limits
MAX_ACQUISITION_ATTEMPTS = 1  # Per task
MAX_ACQUISITIONS_PER_HOUR = 5  # Prevent runaway
REQUIRE_USER_APPROVAL_FOR = [
    "cloud_provider",
    "paid_api",
    "credentials",
    "external_service"
]
NEVER_AUTO_ACQUIRE = [
    "production_access",
    "financial_services",
    "authentication_tokens"
]
```

---

## 9. Success Metrics

### 9.1 Quantitative

| Metric | Target |
|--------|--------|
| Capability gaps detected | Track count |
| Gaps auto-resolved | > 50% of low-risk gaps |
| User-resolved gaps | Track count |
| Skills created | Track count |
| Retry success rate | > 90% after acquisition |

### 9.2 Qualitative

- User doesn't have to manually add capabilities
- System gets smarter over time
- Reduced friction for new use cases
- Clear communication about what's happening

---

## 10. Timeline

### Estimated Schedule

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Foundation | 2-3 hours | None |
| Phase 2: Risk Assessment | 1-2 hours | Phase 1 |
| Phase 3: Acquisition Engine | 3-4 hours | Phase 1, 2 |
| Phase 4: Self-Improvement Skill | 1-2 hours | Phase 3 |
| Phase 5: Task Wrapper | 1-2 hours | Phase 3 |
| Phase 6: Reflection Integration | 2-3 hours | Phase 1, 5 |
| Phase 7: Production Migration | 1-2 hours | All above |

**Total: ~12-18 hours of implementation**

### Suggested Order

1. Start with Phase 1 (foundation) - everything depends on this
2. Phase 2 (risk assessment) - needed before any acquisition
3. Phase 3 (acquisition) - core functionality
4. Phase 5 (task wrapper) - integrates acquisition
5. Phase 4 (skill) - uses wrapper
6. Phase 6 (reflection) - can be done in parallel
7. Phase 7 (migration) - after all testing complete

---

## Appendix A: File Structure

```
pcp-dev/
├── scripts/
│   ├── self_improvement/           # NEW: Self-improvement modules
│   │   ├── __init__.py
│   │   ├── capability_detector.py  # Gap detection
│   │   ├── capability_patterns.py  # Pattern definitions
│   │   ├── risk_assessor.py        # Risk assessment
│   │   ├── capability_acquirer.py  # Acquisition engine
│   │   ├── skill_creator.py        # Auto skill generation
│   │   └── execute_wrapper.py      # Task execution wrapper
│   ├── trigger_reflection.py       # UPDATE: Add gap analysis
│   └── task_delegation.py          # UPDATE: Integrate wrapper
├── .claude/
│   └── skills/
│       └── self-improvement/       # NEW: Self-improvement skill
│           └── SKILL.md
├── tests/
│   └── test_self_improvement.py    # NEW: Test suite
├── vault/
│   └── vault.db                    # UPDATE: Add capability_gaps table
└── docs/
    └── SELF_IMPROVEMENT_IMPLEMENTATION_PLAN.md  # This document
```

---

## Appendix B: Example Interactions

### Example 1: Automatic Acquisition (Low Risk)

```
User: [sends voice.mp3] "What's in this recording?"

Agent (internal):
- Received audio file
- Check capabilities: No audio handler
- CapabilityGapError: audio_file
- Research: Whisper is best option
- Risk: LOW (pip install, local, free)
- Decision: Auto-acquire

Agent: "I don't have audio transcription yet, but I can set it up quickly.
       Installing Whisper (runs locally, free)... done!

       Here's what was said:
       [transcription content]

       I've added this capability for future use."
```

### Example 2: User Input Required (High Risk)

```
User: "Check my AWS for running instances"

Agent (internal):
- Check capabilities: No AWS access
- CapabilityGapError: aws
- Risk: HIGH (credentials, costs)
- Decision: Ask user

Agent: "I don't have AWS access configured. To set this up, I'll need:

       1. Your AWS Access Key ID
       2. Your AWS Secret Access Key

       Would you like me to walk you through getting these,
       or do you have them ready?

       Note: I'll store these securely and can revoke access anytime."

User: "Here they are: AKIA... and ..."

Agent: "Setting up AWS access... done!

       You have 3 running instances:
       - web-server (t2.micro)
       - database (t2.medium)
       - worker (t2.small)

       I've saved this capability for future AWS requests."
```

### Example 3: Weekly Reflection

```
[Sunday 10 PM - Automated]

Reflection Agent analyzes past week:
- 3 audio files received → whisper installed (auto)
- 2 Notion requests → API key obtained
- 1 AWS request → credentials configured
- 5 "command not found" errors → tools installed

Generates recommendations:
- QW-1: "Consider adding video transcription (3 related requests)"
- MP-1: "Slack integration frequently requested but not available"

Posts to Discord:
"Weekly PCP Reflection

This week I:
- Added 3 new capabilities
- Resolved 8 capability gaps
- Created 2 new skills

Recommendations:
1. [QW-1] Add video transcription
2. [MP-1] Set up Slack integration

Reply with numbers to approve (e.g., '1,2' or 'all')"
```

---

**End of Planning Document**
