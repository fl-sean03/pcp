#!/usr/bin/env python3
"""
PCP Knowledge Promoter - Decide what knowledge gets promoted to Core docs.

This module implements the "significance filter" that determines when
knowledge from the Vault KB should be promoted to Core documents.

Not everything goes to Core docs - only significant, stable facts that
represent canonical knowledge about the user's profile, projects, goals, etc.

Promotion Rules:
- New project started → PROJECTS.md
- Project status change → PROJECTS.md
- New relationship → PEOPLE.md
- Career milestone → GOALS.md
- Skill acquisition → SKILLS.md
- Major decision → RESEARCH.md or Core docs
"""

import re
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any, NamedTuple
from dataclasses import dataclass

# Import local modules
try:
    from core_docs import CoreDocsManager, add_project, update_project_status
    from knowledge import add_knowledge, query_knowledge, get_knowledge
except ImportError:
    import sys
    sys.path.insert(0, '/workspace/scripts')
    from core_docs import CoreDocsManager, add_project, update_project_status
    from knowledge import add_knowledge, query_knowledge, get_knowledge


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class Promotion:
    """Represents a pending promotion to Core docs."""
    knowledge_id: int
    target_doc: str
    section: str
    content: str
    reason: str
    rule_matched: str


@dataclass
class PromotionRule:
    """Defines a rule for promoting knowledge."""
    name: str
    triggers: List[str]  # Keywords/phrases that trigger this rule
    target_doc: str
    section: str
    content_template: Optional[str] = None
    action: str = "append"  # append, update, or move


# ============================================================================
# Promotion Rules
# ============================================================================

PROMOTION_RULES = {
    "new_project": PromotionRule(
        name="new_project",
        triggers=[
            "started working on",
            "new project",
            "kicked off",
            "beginning work on",
            "launching",
            "starting a new"
        ],
        target_doc="PROJECTS.md",
        section="## Active Projects",
        action="append"
    ),
    "project_complete": PromotionRule(
        name="project_complete",
        triggers=[
            "finished",
            "completed",
            "submitted",
            "published",
            "shipped",
            "released",
            "done with"
        ],
        target_doc="PROJECTS.md",
        section="## Completed Projects",
        action="move"
    ),
    "project_paused": PromotionRule(
        name="project_paused",
        triggers=[
            "pausing",
            "putting on hold",
            "shelving",
            "taking a break from"
        ],
        target_doc="PROJECTS.md",
        section="## Paused Projects",
        action="move"
    ),
    "new_person": PromotionRule(
        name="new_person",
        triggers=[
            "met with",
            "introduced to",
            "new collaborator",
            "joined my committee",
            "working with",
            "partnering with"
        ],
        target_doc="PEOPLE.md",
        section="## Collaborators",
        action="append"
    ),
    "career_milestone": PromotionRule(
        name="career_milestone",
        triggers=[
            "accepted to",
            "awarded",
            "received fellowship",
            "got the position",
            "promoted to",
            "selected for"
        ],
        target_doc="GOALS.md",
        section="## Achievements",
        action="append"
    ),
    "goal_change": PromotionRule(
        name="goal_change",
        triggers=[
            "no longer pursuing",
            "withdrawing from",
            "decided against",
            "changed goals",
            "new target"
        ],
        target_doc="GOALS.md",
        section="## Active Fellowship Targets",
        action="update"
    ),
    "skill_acquired": PromotionRule(
        name="skill_acquired",
        triggers=[
            "learned",
            "now proficient in",
            "picked up",
            "mastered",
            "trained in",
            "certified in"
        ],
        target_doc="SKILLS.md",
        section="## Programming & ML",
        action="append"
    ),
    "research_pivot": PromotionRule(
        name="research_pivot",
        triggers=[
            "switching to",
            "pivoting research",
            "new research direction",
            "changing focus to",
            "decided to use"
        ],
        target_doc="RESEARCH.md",
        section="## Current Research Projects",
        action="update"
    )
}


# ============================================================================
# Knowledge Promoter Class
# ============================================================================

class KnowledgePromoter:
    """
    Evaluate and promote knowledge from Vault KB to Core docs.

    The promoter uses pattern matching on knowledge content to determine
    if it should be promoted to Core documents. It checks for duplicates
    and manages the promotion process.
    """

    def __init__(self):
        """Initialize the KnowledgePromoter."""
        self.core_docs = CoreDocsManager()
        self.rules = PROMOTION_RULES

    def evaluate(self, content: str,
                 category: str = None,
                 metadata: Dict = None) -> Optional[Promotion]:
        """
        Evaluate if content should be promoted to Core docs.

        Args:
            content: The knowledge content to evaluate
            category: Knowledge category (fact, architecture, decision, etc.)
            metadata: Additional metadata about the knowledge

        Returns:
            Promotion object if should be promoted, None otherwise
        """
        content_lower = content.lower()

        for rule_name, rule in self.rules.items():
            for trigger in rule.triggers:
                if trigger.lower() in content_lower:
                    # Check for duplicate
                    if self._is_duplicate(content, rule.target_doc):
                        continue

                    # Create promotion
                    return Promotion(
                        knowledge_id=0,  # Set by caller
                        target_doc=rule.target_doc,
                        section=rule.section,
                        content=self._format_content(content, rule),
                        reason=f"Matched rule: {rule_name}",
                        rule_matched=rule_name
                    )

        return None

    def evaluate_knowledge_item(self, knowledge_id: int) -> Optional[Promotion]:
        """
        Evaluate a knowledge item from the KB for promotion.

        Args:
            knowledge_id: ID of the knowledge item

        Returns:
            Promotion object if should be promoted, None otherwise
        """
        knowledge = get_knowledge(knowledge_id)
        if not knowledge:
            return None

        promotion = self.evaluate(
            knowledge['content'],
            knowledge.get('category'),
            {"tags": knowledge.get('tags', [])}
        )

        if promotion:
            promotion.knowledge_id = knowledge_id

        return promotion

    def _is_duplicate(self, content: str, target_doc: str) -> bool:
        """
        Check if content already exists in target document.

        Uses fuzzy matching to detect near-duplicates.
        """
        try:
            doc_content = self.core_docs.read_doc(target_doc).lower()

            # Extract key phrases from content (words > 4 chars)
            key_words = [w for w in content.lower().split() if len(w) > 4]

            # Check if most key words appear in doc
            if len(key_words) > 0:
                matches = sum(1 for w in key_words if w in doc_content)
                if matches / len(key_words) > 0.7:
                    return True

            return False
        except FileNotFoundError:
            return False

    def _format_content(self, content: str, rule: PromotionRule) -> str:
        """Format content for insertion into Core doc."""
        # For now, return content as-is
        # Future: use rule.content_template to format
        return content

    def promote(self, promotion: Promotion) -> bool:
        """
        Execute a promotion to Core docs.

        Args:
            promotion: Promotion object with details

        Returns:
            True if successful
        """
        try:
            if promotion.rule_matched == "new_project":
                # Extract project details and add
                # For now, append raw content
                self.core_docs.append_to_section(
                    promotion.target_doc,
                    promotion.section,
                    f"\n### {promotion.content}\n- **Added**: {datetime.now().strftime('%Y-%m-%d')}\n- **Source**: Auto-promoted from conversation\n",
                    promotion.reason
                )
            else:
                # Generic append
                self.core_docs.append_to_section(
                    promotion.target_doc,
                    promotion.section,
                    f"- {promotion.content} ({datetime.now().strftime('%Y-%m-%d')})",
                    promotion.reason
                )

            # Mark knowledge as promoted in KB
            if promotion.knowledge_id > 0:
                self._mark_promoted(promotion.knowledge_id, promotion.target_doc)

            return True

        except Exception as e:
            print(f"Promotion failed: {e}")
            return False

    def _mark_promoted(self, knowledge_id: int, target_doc: str):
        """Mark a knowledge item as promoted in the KB."""
        # Update the knowledge item's tags to include "promoted"
        from knowledge import update_knowledge, get_knowledge

        knowledge = get_knowledge(knowledge_id)
        if knowledge:
            tags = knowledge.get('tags', []) or []
            if 'promoted' not in tags:
                tags.append('promoted')
                tags.append(f'promoted_to:{target_doc}')
                update_knowledge(knowledge_id, tags=tags)

    def get_pending_promotions(self, limit: int = 20) -> List[Dict]:
        """
        Get knowledge items that might be candidates for promotion.

        Returns items that haven't been promoted yet and match promotion rules.
        """
        from knowledge import list_knowledge

        pending = []
        all_knowledge = list_knowledge(limit=100)

        for item in all_knowledge:
            tags = item.get('tags', []) or []
            if 'promoted' in tags:
                continue

            promotion = self.evaluate(item['content'], item.get('category'))
            if promotion:
                pending.append({
                    'knowledge_id': item['id'],
                    'content': item['content'],
                    'suggested_doc': promotion.target_doc,
                    'suggested_section': promotion.section,
                    'rule': promotion.rule_matched
                })

                if len(pending) >= limit:
                    break

        return pending


# ============================================================================
# Convenience Functions
# ============================================================================

def evaluate_and_promote(content: str, auto_promote: bool = True) -> Optional[Promotion]:
    """
    Evaluate content and optionally auto-promote to Core docs.

    Args:
        content: Content to evaluate
        auto_promote: If True, automatically promote if eligible

    Returns:
        Promotion object if promoted, None otherwise
    """
    promoter = KnowledgePromoter()
    promotion = promoter.evaluate(content)

    if promotion and auto_promote:
        success = promoter.promote(promotion)
        if success:
            return promotion

    return promotion


def check_pending_promotions() -> List[Dict]:
    """Get list of knowledge items pending promotion."""
    promoter = KnowledgePromoter()
    return promoter.get_pending_promotions()


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PCP Knowledge Promoter - Evaluate and promote knowledge to Core docs"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate content for promotion")
    eval_parser.add_argument("content", help="Content to evaluate")
    eval_parser.add_argument("--promote", "-p", action="store_true",
                             help="Auto-promote if eligible")

    # Pending command
    pending_parser = subparsers.add_parser("pending", help="Show pending promotions")
    pending_parser.add_argument("--limit", "-l", type=int, default=20)

    # Promote command
    promote_parser = subparsers.add_parser("promote", help="Promote a knowledge item")
    promote_parser.add_argument("knowledge_id", type=int, help="Knowledge ID to promote")

    # Rules command
    rules_parser = subparsers.add_parser("rules", help="Show promotion rules")

    args = parser.parse_args()
    promoter = KnowledgePromoter()

    if args.command == "evaluate":
        promotion = promoter.evaluate(args.content)
        if promotion:
            print(f"✓ Eligible for promotion:")
            print(f"  Target: {promotion.target_doc}")
            print(f"  Section: {promotion.section}")
            print(f"  Rule: {promotion.rule_matched}")

            if args.promote:
                success = promoter.promote(promotion)
                if success:
                    print(f"  ✓ Promoted successfully!")
                else:
                    print(f"  ✗ Promotion failed")
        else:
            print("✗ Not eligible for promotion (no rules matched)")

    elif args.command == "pending":
        pending = promoter.get_pending_promotions(args.limit)
        if pending:
            print(f"Pending Promotions ({len(pending)}):\n")
            for item in pending:
                print(f"  [{item['knowledge_id']}] → {item['suggested_doc']}")
                print(f"      {item['content'][:60]}...")
                print(f"      Rule: {item['rule']}")
                print()
        else:
            print("No pending promotions")

    elif args.command == "promote":
        promotion = promoter.evaluate_knowledge_item(args.knowledge_id)
        if promotion:
            success = promoter.promote(promotion)
            if success:
                print(f"✓ Promoted knowledge {args.knowledge_id} to {promotion.target_doc}")
            else:
                print(f"✗ Promotion failed")
        else:
            print(f"✗ Knowledge {args.knowledge_id} not eligible for promotion")

    elif args.command == "rules":
        print("Promotion Rules:\n")
        for name, rule in PROMOTION_RULES.items():
            print(f"  {name}:")
            print(f"    Target: {rule.target_doc} → {rule.section}")
            print(f"    Triggers: {', '.join(rule.triggers[:3])}...")
            print(f"    Action: {rule.action}")
            print()

    else:
        parser.print_help()
