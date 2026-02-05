#!/usr/bin/env python3
"""
PCP Sync Manager - Bi-directional sync between Core docs and Vault KB.

This module orchestrates the synchronization between:
1. Core Documents (OneDrive + Git) - Canonical source of truth
2. Vault Knowledge Base (SQLite) - Dynamic, queryable storage

Sync Operations:
- Core → KB: Parse Core docs and ensure KB has all facts
- KB → Core: Promote significant KB items to Core docs
- Conflict Detection: Find discrepancies between sources
"""

import re
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

# Import local modules
try:
    from core_docs import CoreDocsManager
    from knowledge import add_knowledge, query_knowledge, list_knowledge, update_knowledge
    from knowledge_promoter import KnowledgePromoter, check_pending_promotions
except ImportError:
    import sys
    sys.path.insert(0, '/workspace/scripts')
    from core_docs import CoreDocsManager
    from knowledge import add_knowledge, query_knowledge, list_knowledge, update_knowledge
    from knowledge_promoter import KnowledgePromoter, check_pending_promotions


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    items_synced: int
    items_skipped: int
    errors: List[str]
    details: List[str]


@dataclass
class Conflict:
    """Represents a conflict between Core docs and KB."""
    source: str  # "core" or "kb"
    document: str
    kb_content: str
    core_content: str
    description: str


# ============================================================================
# Sync Manager Class
# ============================================================================

class SyncManager:
    """
    Orchestrate bi-directional sync between Core docs and Vault KB.

    The SyncManager ensures that:
    1. All facts in Core docs are indexed in the KB
    2. Significant KB knowledge gets promoted to Core docs
    3. Conflicts are detected and can be resolved
    """

    def __init__(self):
        """Initialize SyncManager."""
        self.core_docs = CoreDocsManager()
        self.promoter = KnowledgePromoter()

    # -------------------------------------------------------------------------
    # Core → KB Sync
    # -------------------------------------------------------------------------

    def sync_core_to_kb(self) -> SyncResult:
        """
        Parse Core docs and ensure KB has all facts.

        This extracts structured information from Core documents
        and adds it to the knowledge base if not already present.

        Returns:
            SyncResult with details of the sync
        """
        result = SyncResult(
            success=True,
            items_synced=0,
            items_skipped=0,
            errors=[],
            details=[]
        )

        try:
            # Sync each Core doc
            for doc_name in self.core_docs.list_docs():
                if doc_name == "CHANGELOG.md":
                    continue

                doc_result = self._sync_doc_to_kb(doc_name)
                result.items_synced += doc_result.items_synced
                result.items_skipped += doc_result.items_skipped
                result.errors.extend(doc_result.errors)
                result.details.extend(doc_result.details)

        except Exception as e:
            result.success = False
            result.errors.append(f"Sync failed: {str(e)}")

        return result

    def _sync_doc_to_kb(self, doc_name: str) -> SyncResult:
        """Sync a single Core doc to KB."""
        result = SyncResult(
            success=True,
            items_synced=0,
            items_skipped=0,
            errors=[],
            details=[]
        )

        content = self.core_docs.read_doc(doc_name)

        # Extract facts based on document type
        if doc_name == "PROFILE.md":
            facts = self._extract_profile_facts(content)
        elif doc_name == "PROJECTS.md":
            facts = self._extract_project_facts(content)
        elif doc_name == "GOALS.md":
            facts = self._extract_goal_facts(content)
        elif doc_name == "SKILLS.md":
            facts = self._extract_skill_facts(content)
        elif doc_name == "PEOPLE.md":
            facts = self._extract_people_facts(content)
        elif doc_name == "RESEARCH.md":
            facts = self._extract_research_facts(content)
        else:
            facts = []

        # Add facts to KB if not already present
        for fact in facts:
            if not self._fact_exists_in_kb(fact['content']):
                try:
                    add_knowledge(
                        content=fact['content'],
                        category=fact.get('category', 'fact'),
                        source=f"Core:{doc_name}",
                        tags=fact.get('tags', [])
                    )
                    result.items_synced += 1
                    result.details.append(f"Added: {fact['content'][:50]}...")
                except Exception as e:
                    result.errors.append(f"Failed to add fact: {e}")
            else:
                result.items_skipped += 1

        return result

    def _fact_exists_in_kb(self, content: str) -> bool:
        """Check if a fact already exists in KB."""
        # Search for similar content
        results = query_knowledge(content[:50])
        for r in results:
            # Simple similarity check
            if content.lower()[:100] in r['content'].lower() or \
               r['content'].lower()[:100] in content.lower():
                return True
        return False

    # -------------------------------------------------------------------------
    # Fact Extraction from Core Docs
    # -------------------------------------------------------------------------

    def _extract_profile_facts(self, content: str) -> List[Dict]:
        """Extract facts from PROFILE.md."""
        facts = []

        # Extract table rows
        for match in re.finditer(r'\| \*\*(.+?)\*\* \| (.+?) \|', content):
            field, value = match.groups()
            if value.strip() and value.strip() not in ['Value', '---']:
                facts.append({
                    'content': f"User {field}: {value.strip()}",
                    'category': 'fact',
                    'tags': ['profile', field.lower().replace(' ', '_')]
                })

        return facts

    def _extract_project_facts(self, content: str) -> List[Dict]:
        """Extract facts from PROJECTS.md."""
        facts = []

        # Extract project names and status
        for match in re.finditer(r'### (.+?)\n.*?\| \*\*Status\*\* \| (.+?) \|', content, re.DOTALL):
            name, status = match.groups()
            facts.append({
                'content': f"Project '{name}' is {status}",
                'category': 'fact',
                'tags': ['project', name.lower().replace(' ', '_')]
            })

        return facts

    def _extract_goal_facts(self, content: str) -> List[Dict]:
        """Extract facts from GOALS.md."""
        facts = []

        # Extract fellowship targets
        for match in re.finditer(r'\| \*\*(.+?)\*\* \| (.+?) \|', content):
            name, status = match.groups()
            if 'Applied' in status or 'Exploring' in status:
                facts.append({
                    'content': f"Fellowship target: {name} - {status}",
                    'category': 'fact',
                    'tags': ['goal', 'fellowship']
                })

        # Extract achievements
        achievements = re.findall(r'\| (\w+ \d{4}) \| (.+?) \|', content)
        for date, achievement in achievements:
            facts.append({
                'content': f"Achievement ({date}): {achievement}",
                'category': 'fact',
                'tags': ['achievement', 'milestone']
            })

        return facts

    def _extract_skill_facts(self, content: str) -> List[Dict]:
        """Extract facts from SKILLS.md."""
        facts = []

        # Extract tool proficiencies
        for match in re.finditer(r'\| (.+?) \| (Expert|Proficient|Familiar) \|', content):
            tool, level = match.groups()
            if tool.strip() and tool.strip() not in ['Tool', '---']:
                facts.append({
                    'content': f"Skill: {tool.strip()} ({level})",
                    'category': 'fact',
                    'tags': ['skill', tool.strip().lower()]
                })

        return facts

    def _extract_people_facts(self, content: str) -> List[Dict]:
        """Extract facts from PEOPLE.md."""
        facts = []

        # Extract key people
        for match in re.finditer(r'### (.+?)\n.*?\| \*\*Role\*\* \| (.+?) \|', content, re.DOTALL):
            name, role = match.groups()
            facts.append({
                'content': f"{name}: {role}",
                'category': 'fact',
                'tags': ['person', 'relationship']
            })

        return facts

    def _extract_research_facts(self, content: str) -> List[Dict]:
        """Extract facts from RESEARCH.md."""
        facts = []

        # Extract thesis title
        title_match = re.search(r'\*\*(.+?)\*\*', content)
        if title_match:
            facts.append({
                'content': f"PhD thesis: {title_match.group(1)}",
                'category': 'architecture',
                'tags': ['research', 'thesis']
            })

        return facts

    # -------------------------------------------------------------------------
    # KB → Core Sync
    # -------------------------------------------------------------------------

    def sync_kb_to_core(self) -> SyncResult:
        """
        Check KB for items that should be promoted to Core docs.

        Returns:
            SyncResult with details of promotions
        """
        result = SyncResult(
            success=True,
            items_synced=0,
            items_skipped=0,
            errors=[],
            details=[]
        )

        try:
            pending = self.promoter.get_pending_promotions()

            for item in pending:
                promotion = self.promoter.evaluate_knowledge_item(item['knowledge_id'])
                if promotion:
                    success = self.promoter.promote(promotion)
                    if success:
                        result.items_synced += 1
                        result.details.append(
                            f"Promoted to {promotion.target_doc}: {item['content'][:40]}..."
                        )
                    else:
                        result.items_skipped += 1
                        result.errors.append(f"Failed to promote: {item['content'][:40]}...")

        except Exception as e:
            result.success = False
            result.errors.append(f"KB → Core sync failed: {str(e)}")

        return result

    # -------------------------------------------------------------------------
    # Full Sync
    # -------------------------------------------------------------------------

    def full_sync(self) -> SyncResult:
        """
        Run complete bi-directional sync.

        1. Sync from OneDrive to local
        2. Sync Core docs to KB
        3. Sync KB to Core docs
        4. Push changes to OneDrive and Git

        Returns:
            Combined SyncResult
        """
        result = SyncResult(
            success=True,
            items_synced=0,
            items_skipped=0,
            errors=[],
            details=[]
        )

        # Step 1: Sync from OneDrive
        result.details.append("Step 1: Syncing from OneDrive...")
        self.core_docs.sync_from_onedrive()

        # Step 2: Core → KB
        result.details.append("Step 2: Syncing Core docs to KB...")
        core_to_kb = self.sync_core_to_kb()
        result.items_synced += core_to_kb.items_synced
        result.items_skipped += core_to_kb.items_skipped
        result.errors.extend(core_to_kb.errors)
        result.details.extend(core_to_kb.details)

        # Step 3: KB → Core
        result.details.append("Step 3: Syncing KB to Core docs...")
        kb_to_core = self.sync_kb_to_core()
        result.items_synced += kb_to_core.items_synced
        result.items_skipped += kb_to_core.items_skipped
        result.errors.extend(kb_to_core.errors)
        result.details.extend(kb_to_core.details)

        # Check for errors
        if core_to_kb.errors or kb_to_core.errors:
            result.success = False

        return result

    # -------------------------------------------------------------------------
    # Conflict Detection
    # -------------------------------------------------------------------------

    def detect_conflicts(self) -> List[Conflict]:
        """
        Find discrepancies between Core docs and KB.

        Returns:
            List of conflicts found
        """
        conflicts = []

        # Get all facts from KB that came from Core docs
        kb_facts = list_knowledge(limit=500)
        core_facts = [f for f in kb_facts if f.get('source', '').startswith('Core:')]

        for kb_fact in core_facts:
            source_doc = kb_fact['source'].replace('Core:', '')

            try:
                core_content = self.core_docs.read_doc(source_doc)

                # Check if the fact still exists in Core doc
                if kb_fact['content'][:50].lower() not in core_content.lower():
                    conflicts.append(Conflict(
                        source="kb",
                        document=source_doc,
                        kb_content=kb_fact['content'],
                        core_content="(not found in Core doc)",
                        description=f"KB fact not found in {source_doc}"
                    ))
            except FileNotFoundError:
                conflicts.append(Conflict(
                    source="kb",
                    document=source_doc,
                    kb_content=kb_fact['content'],
                    core_content="(document not found)",
                    description=f"Source document {source_doc} not found"
                ))

        return conflicts

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current sync state.

        Returns:
            Dict with sync status information
        """
        # Get last commit info
        history = self.core_docs.get_git_history(1)
        last_commit = history[0] if history else None

        # Get KB stats
        kb_facts = list_knowledge(limit=1000)
        core_sourced = len([f for f in kb_facts if f.get('source', '').startswith('Core:')])
        promoted = len([f for f in kb_facts if 'promoted' in (f.get('tags') or [])])

        # Get pending promotions
        pending = check_pending_promotions()

        return {
            'last_git_commit': last_commit,
            'kb_total_facts': len(kb_facts),
            'kb_from_core': core_sourced,
            'kb_promoted': promoted,
            'pending_promotions': len(pending),
            'core_docs': self.core_docs.list_docs()
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def run_full_sync() -> SyncResult:
    """Run a full bi-directional sync."""
    manager = SyncManager()
    return manager.full_sync()


def get_sync_status() -> Dict[str, Any]:
    """Get current sync status."""
    manager = SyncManager()
    return manager.get_sync_status()


def seed_kb_from_core() -> SyncResult:
    """Initial seed of KB from Core docs."""
    manager = SyncManager()
    return manager.sync_core_to_kb()


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PCP Sync Manager - Bi-directional sync between Core docs and KB"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Full sync command
    sync_parser = subparsers.add_parser("sync", help="Run full bi-directional sync")

    # Core to KB command
    core_to_kb_parser = subparsers.add_parser("core-to-kb", help="Sync Core docs to KB")

    # KB to Core command
    kb_to_core_parser = subparsers.add_parser("kb-to-core", help="Sync KB to Core docs")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show sync status")

    # Conflicts command
    conflicts_parser = subparsers.add_parser("conflicts", help="Detect conflicts")

    # Seed command
    seed_parser = subparsers.add_parser("seed", help="Initial seed of KB from Core docs")

    args = parser.parse_args()
    manager = SyncManager()

    if args.command == "sync":
        print("Running full sync...\n")
        result = manager.full_sync()
        print(f"Success: {result.success}")
        print(f"Items synced: {result.items_synced}")
        print(f"Items skipped: {result.items_skipped}")
        if result.errors:
            print(f"\nErrors:")
            for err in result.errors:
                print(f"  - {err}")
        if result.details:
            print(f"\nDetails:")
            for detail in result.details[:10]:
                print(f"  - {detail}")

    elif args.command == "core-to-kb":
        print("Syncing Core docs to KB...\n")
        result = manager.sync_core_to_kb()
        print(f"Items synced: {result.items_synced}")
        print(f"Items skipped: {result.items_skipped}")

    elif args.command == "kb-to-core":
        print("Syncing KB to Core docs...\n")
        result = manager.sync_kb_to_core()
        print(f"Items synced: {result.items_synced}")
        print(f"Items skipped: {result.items_skipped}")

    elif args.command == "status":
        status = manager.get_sync_status()
        print("Sync Status:\n")
        print(f"  Core Documents: {len(status['core_docs'])}")
        for doc in status['core_docs']:
            print(f"    - {doc}")
        print(f"\n  KB Total Facts: {status['kb_total_facts']}")
        print(f"  KB From Core: {status['kb_from_core']}")
        print(f"  KB Promoted: {status['kb_promoted']}")
        print(f"  Pending Promotions: {status['pending_promotions']}")
        if status['last_git_commit']:
            print(f"\n  Last Git Commit:")
            print(f"    {status['last_git_commit']['hash'][:8]} - {status['last_git_commit']['message']}")

    elif args.command == "conflicts":
        conflicts = manager.detect_conflicts()
        if conflicts:
            print(f"Found {len(conflicts)} conflict(s):\n")
            for c in conflicts:
                print(f"  Document: {c.document}")
                print(f"  Description: {c.description}")
                print(f"  KB Content: {c.kb_content[:50]}...")
                print()
        else:
            print("No conflicts detected")

    elif args.command == "seed":
        print("Seeding KB from Core docs...\n")
        result = manager.sync_core_to_kb()
        print(f"Items added: {result.items_synced}")
        print(f"Items skipped (already exist): {result.items_skipped}")
        if result.details:
            print(f"\nAdded:")
            for detail in result.details[:10]:
                print(f"  - {detail}")

    else:
        parser.print_help()
