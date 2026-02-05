# PCP v4.0 Comprehensive End-to-End Test Design

**Version:** 1.0
**Date:** 2026-01-27
**Status:** Implementation

---

## Executive Summary

This document describes a comprehensive end-to-end test suite for verifying the PCP v4.0 implementation. The test suite covers:

- **16 test categories** covering all major components
- **100+ individual test cases**
- **Observability hooks** for debugging
- **Automated verification** of architecture requirements

---

## Test Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TEST RUNNER                                   │
│  • Orchestrates all test categories                              │
│  • Collects results and generates reports                        │
│  • Provides observability into failures                          │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ UNIT TESTS       │ │ INTEGRATION      │ │ E2E FLOW         │
│                  │ │ TESTS            │ │ TESTS            │
│ • Isolated       │ │ • Component      │ │ • Full system    │
│ • Fast           │ │   interaction    │ │ • Real DB        │
│ • Mock external  │ │ • Real DB        │ │ • Simulated      │
│                  │ │ • Mock external  │ │   Discord        │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

---

## Test Categories

### Category 1: Message Queue System

**Purpose:** Verify queue-first architecture works correctly

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| MQ-001 | Enqueue Message | Message is persisted immediately | Critical |
| MQ-002 | FIFO Ordering | Messages processed in order | Critical |
| MQ-003 | Priority Ordering | Higher priority messages first | High |
| MQ-004 | Duplicate Handling | Same message_id returns existing ID | High |
| MQ-005 | Status Transitions | pending→processing→completed | Critical |
| MQ-006 | Failed Status | Error marks as failed | High |
| MQ-007 | Parallel Task Link | Queue links to parallel task | High |
| MQ-008 | Stale Cleanup | Old completed messages removed | Medium |
| MQ-009 | Processing Count | Accurate count of processing items | Medium |
| MQ-010 | Concurrent Access | Thread-safe operations | High |

### Category 2: Parallel Task Manager

**Purpose:** Verify parallel task lifecycle

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| PT-001 | Create Task | Task created with focus mode | Critical |
| PT-002 | Start Task | Transitions to running | Critical |
| PT-003 | Progress Updates | Progress messages stored | High |
| PT-004 | Complete Task | Result stored correctly | Critical |
| PT-005 | Fail Task | Error stored correctly | High |
| PT-006 | Notification Flag | Mark as notified works | Medium |
| PT-007 | Queue Linkage | Links back to queue message | High |
| PT-008 | Focus Mode Storage | Focus mode persisted | Medium |

### Category 3: Orchestrator

**Purpose:** Verify orchestrator process management

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| OR-001 | Initialize | Orchestrator starts correctly | Critical |
| OR-002 | Poll Queue | Retrieves pending messages | Critical |
| OR-003 | Spawn Worker | Process spawned for message | Critical |
| OR-004 | Worker Timeout | Timeout kills worker | High |
| OR-005 | Completion Detection | Detects when worker finishes | Critical |
| OR-006 | Error Handling | Failed workers handled | High |
| OR-007 | Concurrent Workers | Respects max_workers limit | High |

### Category 4: Capture System

**Purpose:** Verify all capture types work correctly

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| CP-001 | Simple Note | Basic text capture | Critical |
| CP-002 | With Entities | People/projects extracted | Critical |
| CP-003 | With Deadline | Auto-creates task | High |
| CP-004 | With Task Deadline | Auto-creates task with due date | High |
| CP-005 | Brain Dump | Multiple items categorized | High |
| CP-006 | Decision Capture | Decision recorded | Medium |
| CP-007 | Entity Linking | Links to existing people/projects | High |
| CP-008 | Return Structure | Correct result object | Medium |

### Category 5: Search System

**Purpose:** Verify all search types work correctly

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| SR-001 | Keyword Search | Finds exact matches | Critical |
| SR-002 | Partial Match | Finds partial matches | High |
| SR-003 | Person Search | Searches people table | High |
| SR-004 | Project Search | Searches projects table | High |
| SR-005 | Unified Search | Searches all sources | High |
| SR-006 | Source Filter | Filters by source type | Medium |
| SR-007 | No Results | Returns empty gracefully | Medium |

### Category 6: Task Management

**Purpose:** Verify task lifecycle

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| TM-001 | Create Task | Task stored correctly | Critical |
| TM-002 | List Pending | Returns pending tasks | Critical |
| TM-003 | List Overdue | Returns overdue tasks | High |
| TM-004 | Complete Task | Marks as completed | Critical |
| TM-005 | Task with Context | Returns full context | High |
| TM-006 | Tasks by Group | Groups tasks correctly | Medium |
| TM-007 | Due Date Filter | Filters by due date | Medium |

### Category 7: Knowledge Base

**Purpose:** Verify knowledge storage and retrieval

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| KB-001 | Add Knowledge | Knowledge stored | Critical |
| KB-002 | Query Knowledge | Finds by query | Critical |
| KB-003 | Category Filter | Filters by category | High |
| KB-004 | Project Link | Links to project | Medium |
| KB-005 | Record Decision | Decision with context | High |
| KB-006 | Link Outcome | Outcome attached | Medium |
| KB-007 | Pending Outcomes | Finds decisions needing outcomes | Medium |

### Category 8: Relationship Intelligence

**Purpose:** Verify people tracking

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| RI-001 | Create Person | Person stored | Critical |
| RI-002 | Update Contact | Contact info updated | High |
| RI-003 | Stale Relationships | Finds stale contacts | High |
| RI-004 | Relationship Summary | Full summary returned | High |
| RI-005 | Interaction Count | Count increments | Medium |

### Category 9: Project Health

**Purpose:** Verify project monitoring

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| PH-001 | Create Project | Project stored | Critical |
| PH-002 | Project Health | Returns health metrics | High |
| PH-003 | Stalled Projects | Finds inactive projects | High |
| PH-004 | Project Context | Full context returned | High |
| PH-005 | Activity Tracking | Tracks recent activity | Medium |

### Category 10: Brief Generation

**Purpose:** Verify brief data collection

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| BG-001 | Daily Brief Data | Returns all sections | Critical |
| BG-002 | Weekly Summary | Returns week stats | High |
| BG-003 | EOD Digest | Returns today's activity | High |
| BG-004 | Meeting Prep | Returns attendee context | High |
| BG-005 | Attention Items | Returns urgent items | High |

### Category 11: Pattern Detection

**Purpose:** Verify pattern analysis

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| PD-001 | Repeated Topics | Detects repeated topics | High |
| PD-002 | Pattern Data | Returns pattern analysis | Medium |
| PD-003 | Suggestions | Generates suggestions | Medium |

### Category 12: Discord Notification

**Purpose:** Verify Discord integration

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| DN-001 | Webhook Config | Webhook URL configured | Critical |
| DN-002 | Send Notification | Message sent successfully | Critical |
| DN-003 | Task Complete | Completion notification works | High |
| DN-004 | Error Handling | Failed sends handled | Medium |

### Category 13: Focus Prompts

**Purpose:** Verify focus mode configuration

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| FP-001 | General Exists | general.md exists | Critical |
| FP-002 | Homework Exists | homework.md exists | Critical |
| FP-003 | Research Exists | research.md exists | Critical |
| FP-004 | Writing Exists | writing.md exists | Critical |
| FP-005 | System Exists | system.md exists | Critical |
| FP-006 | Full Capabilities | All mention full access | High |
| FP-007 | Notification Guidance | All have Discord guidance | Medium |

### Category 14: Database Schema

**Purpose:** Verify all tables exist with correct structure

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| DB-001 | Queue Table | discord_message_queue exists | Critical |
| DB-002 | Parallel Table | parallel_tasks exists | Critical |
| DB-003 | Captures Table | captures_v2 exists | Critical |
| DB-004 | People Table | people exists | Critical |
| DB-005 | Projects Table | projects exists | Critical |
| DB-006 | Tasks Table | tasks exists | Critical |
| DB-007 | Files Table | files exists | Critical |
| DB-008 | Knowledge Table | knowledge exists | Critical |
| DB-009 | Decisions Table | decisions exists | Critical |
| DB-010 | Indexes Exist | All indexes present | High |

### Category 15: Queue Bridge

**Purpose:** Verify bridge layer works

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| QB-001 | Enqueue Message | Bridge enqueues correctly | Critical |
| QB-002 | Get Status | Bridge retrieves status | High |
| QB-003 | Get Stats | Returns aggregate stats | High |
| QB-004 | Create Parallel | Creates parallel task | High |
| QB-005 | Complete Parallel | Completes parallel task | High |

### Category 16: Documentation Verification

**Purpose:** Verify docs are up to date

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| DC-001 | SPEC v4.0 | SPEC.md at v4.0 | Critical |
| DC-002 | CLAUDE v8.0 | CLAUDE.md at v8.0 | Critical |
| DC-003 | Architecture | ARCHITECTURE_V4.md exists | Critical |
| DC-004 | Universal Agent | Docs mention universal agent | High |
| DC-005 | Queue-First | Docs mention queue-first | High |
| DC-006 | Agentic Routing | Docs mention agentic routing | High |

---

## Observability Features

### Test Output Format

Each test produces structured output:

```json
{
  "test_id": "MQ-001",
  "test_name": "Enqueue Message",
  "category": "Message Queue",
  "status": "passed|failed|skipped",
  "duration_ms": 45,
  "details": "Message persisted with queue_id=42",
  "error": null,
  "stack_trace": null
}
```

### Debugging Support

1. **Verbose Mode**: Shows all database queries and results
2. **Single Test Run**: Run individual tests for debugging
3. **Category Run**: Run single category
4. **Failure Analysis**: Detailed error context on failures
5. **Database Snapshots**: Capture DB state before/after tests

### Metrics Collected

- Total tests run
- Pass/fail counts by category
- Average test duration
- Slowest tests
- Most common failure types

---

## Test Data Management

### Test Database

Tests use a separate test database to avoid polluting production data:

```python
TEST_DB_PATH = "/tmp/pcp_test_vault.db"
```

### Test Data Fixtures

```python
FIXTURES = {
    "people": [
        {"name": "John Smith", "organization": "Acme Corp"},
        {"name": "Sarah Chen", "organization": "StartupX"}
    ],
    "projects": [
        {"name": "PCP", "status": "active"},
        {"name": "Alpha-Trader", "status": "active"}
    ],
    "captures": [
        {"content": "Test capture about API performance", "capture_type": "note"}
    ]
}
```

### Cleanup

All test data is cleaned up after test run unless `--keep-data` flag is passed.

---

## Running Tests

### Full Suite

```bash
python3 test_e2e_comprehensive.py
```

### Single Category

```bash
python3 test_e2e_comprehensive.py --category "Message Queue"
```

### Single Test

```bash
python3 test_e2e_comprehensive.py --test MQ-001
```

### Verbose Mode

```bash
python3 test_e2e_comprehensive.py --verbose
```

### Keep Test Data

```bash
python3 test_e2e_comprehensive.py --keep-data
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All tests passed |
| 1 | One or more tests failed |
| 2 | Configuration error |
| 3 | Database connection error |

---

## Integration with CI/CD

Tests can be integrated into deployment pipeline:

```yaml
# Example GitHub Actions
- name: Run E2E Tests
  run: python3 scripts/test_e2e_comprehensive.py
  env:
    PCP_TEST_MODE: true
```

---

*Document Version: 1.0 - E2E Test Design*
