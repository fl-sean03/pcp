# PCP Knowledge System Implementation Plan

**Date**: 2026-01-14
**Status**: Implementation Ready

---

## Executive Summary

This document captures the complete design and implementation plan for PCP's self-evolving knowledge system. The system consists of:

1. **Core Documents** - Human-readable, Git-versioned markdown files on cloud storage
2. **Vault Knowledge Base** - SQLite database for dynamic, queryable knowledge
3. **Bi-directional Sync** - Autonomous updates between both layers
4. **Git Versioning** - Full history and rollback capability via private repo

---

## Part 1: Architecture Design

### 1.1 Two-Layer Knowledge System

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    CORE DOCUMENTS                            │    │
│  │              (Cloud Storage + Git Versioned)                 │    │
│  │                                                              │    │
│  │  Location: CloudStorage/Documents/Core/                      │    │
│  │  Backup: Private git repository                              │    │
│  │                                                              │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐               │    │
│  │  │ PROFILE.md │ │RESEARCH.md │ │PROJECTS.md │               │    │
│  │  └────────────┘ └────────────┘ └────────────┘               │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐               │    │
│  │  │  GOALS.md  │ │ PEOPLE.md  │ │ SKILLS.md  │               │    │
│  │  └────────────┘ └────────────┘ └────────────┘               │    │
│  │  ┌────────────┐                                              │    │
│  │  │CHANGELOG.md│ ← Master log of all changes                  │    │
│  │  └────────────┘                                              │    │
│  │                                                              │    │
│  │  Properties:                                                 │    │
│  │  • Human-readable markdown                                   │    │
│  │  • Git-versioned (full history, rollback)                    │    │
│  │  • Synced to cloud (accessible anywhere)                     │    │
│  │  • PCP can update autonomously                               │    │
│  │  • Source of truth for stable facts                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ▲                                       │
│                              │ Bi-directional Sync                   │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    VAULT KNOWLEDGE BASE                      │    │
│  │                  (SQLite in PCP container)                   │    │
│  │                                                              │    │
│  │  Location: /workspace/vault/vault.db                         │    │
│  │                                                              │    │
│  │  Tables:                                                     │    │
│  │  • knowledge   - Permanent facts (derived from Core + dynamic)│   │
│  │  • decisions   - Choices with outcome tracking               │    │
│  │  • captures    - Transient observations                      │    │
│  │  • people      - Relationship graph                          │    │
│  │  • projects    - Project tracking                            │    │
│  │  • patterns    - Detected patterns                           │    │
│  │                                                              │    │
│  │  Properties:                                                 │    │
│  │  • Machine-queryable (SQL)                                   │    │
│  │  • Includes dynamic knowledge (interactions, status)         │    │
│  │  • Enables semantic search (ChromaDB)                        │    │
│  │  • Fast retrieval for briefs                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Knowledge Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                       KNOWLEDGE FLOW                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                         ┌─────────┐                                  │
│                         │  USER   │                                  │
│                         └────┬────┘                                  │
│                              │                                       │
│         ┌────────────────────┼────────────────────┐                  │
│         ▼                    ▼                    ▼                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
│  │Conversations│     │ Direct Edit │     │File Uploads │            │
│  │(Discord/PCP)│     │(Core docs)  │     │(PDFs, etc.) │            │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘            │
│         │                   │                   │                    │
│         └───────────────────┼───────────────────┘                    │
│                             ▼                                        │
│              ┌──────────────────────────────┐                        │
│              │     KNOWLEDGE PROCESSOR      │                        │
│              │  • Entity extraction         │                        │
│              │  • Significance scoring      │                        │
│              │  • Classification            │                        │
│              └──────────────┬───────────────┘                        │
│                             │                                        │
│         ┌───────────────────┼───────────────────┐                    │
│         ▼                   ▼                   ▼                    │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
│  │Capture Only │     │  KB Update  │     │Core Doc     │            │
│  │(transient)  │     │  (dynamic)  │     │Update       │            │
│  └─────────────┘     └─────────────┘     │(significant)│            │
│                                          └──────┬──────┘            │
│                                                 │                    │
│                                                 ▼                    │
│                                    ┌────────────────────┐            │
│                                    │   Git Commit       │            │
│                                    │   + Cloud Sync     │            │
│                                    └────────────────────┘            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Significance Filter (What Gets Promoted to Core)

| Trigger | Target Doc | Section | Example |
|---------|------------|---------|---------|
| New project started | PROJECTS.md | Active Projects | "Starting reliability study" |
| Project status change | PROJECTS.md | (move between sections) | "Paper submitted" |
| Project completed | PROJECTS.md | Completed Projects | "Finished ML predictor" |
| New relationship | PEOPLE.md | Key Relationships | "Dr. Smith joined committee" |
| Relationship change | PEOPLE.md | (update entry) | "John moved to new org" |
| Career milestone | GOALS.md | Achievements | "Accepted to fellowship" |
| Goal change | GOALS.md | Active Targets | "No longer pursuing X" |
| Skill acquisition | SKILLS.md | Technical Stack | "Now proficient in PyTorch" |
| Major decision | DECISIONS.md | Decisions | "Switching from X to Y" |
| Personal fact change | PROFILE.md | (relevant section) | "New contact info" |

### 1.4 Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Update frequency | Immediate + Daily summary | Real-time updates, daily digest of changes |
| Approval flow | Fully autonomous | User rarely edits Core docs manually |
| Conflict resolution | Core docs win | If conflict, prefer canonical source |
| Rollback capability | Yes, via Git | Every change is a commit, can revert |
| Storage location | Cloud/Documents/Core/ | Accessible everywhere, syncs automatically |
| Version control | Private git repo | Full history, collaboration-ready |

---

## Part 2: Implementation Plan

### 2.1 Components to Build

```
pcp/scripts/
├── core_docs.py           # Read/write/update Core docs (rclone + git)
├── knowledge_promoter.py  # Significance filter + promotion logic
├── sync_manager.py        # Bi-directional sync orchestration
├── knowledge.py           # (existing) KB operations
└── onedrive_rclone.py     # (existing) Cloud storage access
```

### 2.2 Repository Setup

**Structure**:
```
core-docs/
├── PROFILE.md
├── RESEARCH.md
├── PROJECTS.md
├── GOALS.md
├── PEOPLE.md
├── SKILLS.md
├── CHANGELOG.md
└── .gitignore
```

**Sync Flow**:
1. Core docs live on cloud storage (primary)
2. Changes are committed to git (versioning)
3. Local clone in PCP container for operations
4. Push to both cloud and git after updates

### 2.3 Core Docs Structure Templates

#### PROFILE.md
```markdown
# Profile

## Identity
- **Name**: [Your Name]
- **Email**: [Your Email]
- **Location**: [Your Location]

## Current Position
- **Role**: [Your Role]
- **Organization**: [Your Organization]
- **Start Date**: [Date]

---
*Last updated: [Date] by PCP*
```

#### PROJECTS.md
```markdown
# Active Projects

## Project Name
- **Status**: Active
- **Type**: Research/Startup/Open-Source
- **Focus**: Brief description
- **Started**: [Date]
- **Key Files**: [Location]

---

## Paused Projects
(none currently)

---

## Completed Projects
(populated as projects complete)

---
*Last updated: [Date] by PCP*
```

### 2.4 Implementation Sequence

| Step | Task | Output |
|------|------|--------|
| 1 | Create private git repo | Version-controlled docs |
| 2 | Create cloud storage folder | CloudStorage/Documents/Core/ |
| 3 | Write initial Core docs | All .md files with templates |
| 4 | Implement core_docs.py | Script for doc operations |
| 5 | Implement knowledge_promoter.py | Significance filter |
| 6 | Implement sync_manager.py | Bi-directional sync |
| 7 | Seed KB from Core docs | knowledge table populated |
| 8 | Test end-to-end flow | Verify promotion and sync work |
| 9 | Update PCP CLAUDE.md | Document new knowledge system |

---

## Part 3: API Reference (Planned)

### core_docs.py

```python
class CoreDocsManager:
    """Manage Core documents on cloud storage with Git versioning."""

    def __init__(self,
                 cloud_path: str = "Documents/Core",
                 git_repo_path: str = "/workspace/core-docs"):
        """Initialize with cloud and local git paths."""

    def read_doc(self, doc_name: str) -> str:
        """Read a Core doc from cloud storage."""

    def write_doc(self, doc_name: str, content: str, reason: str) -> bool:
        """Write entire doc with changelog and git commit."""

    def update_section(self, doc_name: str, section: str,
                       content: str, reason: str) -> bool:
        """Update a specific section within a doc."""

    def append_to_section(self, doc_name: str, section: str,
                          item: str, reason: str) -> bool:
        """Add an item to a section (e.g., new project)."""

    def get_changelog(self, doc_name: str = None,
                      limit: int = 20) -> List[dict]:
        """Get recent changes from CHANGELOG.md or git log."""

    def revert_to_commit(self, commit_hash: str) -> bool:
        """Revert Core docs to a specific git commit."""

    def sync_to_cloud(self) -> bool:
        """Push local changes to cloud via rclone."""

    def sync_from_cloud(self) -> bool:
        """Pull latest from cloud to local."""
```

### knowledge_promoter.py

```python
class KnowledgePromoter:
    """Evaluate and promote knowledge from KB to Core docs."""

    PROMOTION_RULES = {
        "new_project": {...},
        "project_status": {...},
        "new_person": {...},
        "career_milestone": {...},
        "skill_acquired": {...},
        "major_decision": {...},
    }

    def evaluate(self, knowledge_item: dict) -> Optional[Promotion]:
        """Evaluate if item should be promoted to Core docs."""

    def check_duplicate(self, content: str, target_doc: str) -> bool:
        """Check if knowledge already exists in target doc."""

    def promote(self, knowledge_id: int) -> bool:
        """Execute promotion to Core doc with git commit."""

    def get_pending_promotions(self) -> List[dict]:
        """Get KB items flagged for potential promotion."""
```

### sync_manager.py

```python
class SyncManager:
    """Orchestrate bi-directional sync between Core docs and KB."""

    def sync_core_to_kb(self) -> SyncResult:
        """Parse Core docs and ensure KB has all facts."""

    def sync_kb_to_core(self) -> SyncResult:
        """Promote significant KB items to Core docs."""

    def full_sync(self) -> SyncResult:
        """Run complete bi-directional sync."""

    def detect_conflicts(self) -> List[Conflict]:
        """Find discrepancies between Core docs and KB."""

    def get_sync_status(self) -> dict:
        """Get current sync state and last sync times."""
```

---

## Part 4: Success Criteria

### Functional Requirements
- [ ] Core docs created on cloud storage with profile template
- [ ] Git repo created and syncing with Core docs
- [ ] PCP can read Core docs via rclone
- [ ] PCP can update Core docs programmatically
- [ ] Every update creates a git commit
- [ ] KB seeded from Core docs
- [ ] Promotion rules working (new project → PROJECTS.md)
- [ ] Daily brief includes Core doc changes
- [ ] Rollback works via git revert

### Non-Functional Requirements
- [ ] Updates complete in < 10 seconds
- [ ] Git history is clean and meaningful
- [ ] Docs are human-readable and well-formatted
- [ ] System recovers gracefully from sync failures

---

## Appendix: Key Files Reference

| File | Location | Purpose |
|------|----------|---------|
| vault.db | /workspace/vault/ | SQLite knowledge database |
| rclone.conf | ~/.config/rclone/ | Cloud storage OAuth config |
| Core docs | CloudStorage/Documents/Core/ | Canonical knowledge |
| Git repo | Private repository | Version control |
| knowledge.py | pcp/scripts/ | KB operations |
| core_docs.py | pcp/scripts/ | Core doc operations |
| knowledge_promoter.py | pcp/scripts/ | Promotion logic |
| sync_manager.py | pcp/scripts/ | Sync orchestration |

---

*Document created: 2026-01-14*
*This is the implementation blueprint for PCP's self-evolving knowledge system.*
