#!/usr/bin/env python3
"""
PCP Knowledge Base - Permanent facts, decisions, and learnings.

Unlike captures (transient observations), knowledge represents
permanent facts that should be retained and referenced.

Examples:
- "MatterStack uses Redis for caching" (architecture)
- "API rate limit is 100 req/min" (decision)
- "the user prefers concise responses" (preference)
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

# Support both container and local development paths
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)) and os.path.exists(os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault")):
    VAULT_PATH = os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db")


# ============================================================================
# Core Functions
# ============================================================================

def add_knowledge(
    content: str,
    category: str = "fact",
    project_id: Optional[int] = None,
    confidence: float = 1.0,
    source: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> int:
    """
    Add a new piece of knowledge to the knowledge base.

    Args:
        content: The knowledge content (fact, decision, etc.)
        category: One of: architecture, decision, fact, preference
        project_id: Optional link to a project
        confidence: Confidence level 0.0 to 1.0 (default 1.0)
        source: Where this knowledge came from
        tags: List of tags for categorization

    Returns:
        The ID of the created knowledge entry
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO knowledge (
            content, category, project_id, confidence, source, tags, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        content,
        category,
        project_id,
        confidence,
        source,
        json.dumps(tags) if tags else None,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))

    knowledge_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return knowledge_id


def get_knowledge(knowledge_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a knowledge entry by ID.

    Args:
        knowledge_id: The ID of the knowledge entry

    Returns:
        Dict with knowledge details or None if not found
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, content, category, project_id, confidence, source, tags,
               created_at, updated_at
        FROM knowledge
        WHERE id = ?
    """, (knowledge_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "content": row["content"],
            "category": row["category"],
            "project_id": row["project_id"],
            "confidence": row["confidence"],
            "source": row["source"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    return None


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert a database row to a knowledge dict."""
    return {
        "id": row["id"],
        "content": row["content"],
        "category": row["category"],
        "project_id": row["project_id"],
        "confidence": row["confidence"],
        "source": row["source"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }


def query_knowledge(
    query: str,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search knowledge by content.

    Uses SQLite LIKE for text search. Searches content field.
    Multi-word queries match entries containing ALL words.

    Args:
        query: Search query string (multi-word searches match ALL words)
        category: Optional filter by category

    Returns:
        List of matching knowledge entries
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Split query into words and match ALL
    words = query.strip().split()

    # Build query with optional category filter
    sql = """
        SELECT id, content, category, project_id, confidence, source, tags,
               created_at, updated_at
        FROM knowledge
        WHERE 1=1
    """
    params = []

    # Each word must be present (AND logic)
    for word in words:
        sql += " AND content LIKE ?"
        params.append(f"%{word}%")

    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY updated_at DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def list_knowledge(
    category: Optional[str] = None,
    project_id: Optional[int] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List knowledge entries with optional filters.

    Args:
        category: Optional filter by category
        project_id: Optional filter by project
        limit: Maximum number of results (default 50)

    Returns:
        List of knowledge entries
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build query with optional filters
    sql = """
        SELECT id, content, category, project_id, confidence, source, tags,
               created_at, updated_at
        FROM knowledge
        WHERE 1=1
    """
    params = []

    if category:
        sql += " AND category = ?"
        params.append(category)

    if project_id is not None:
        sql += " AND project_id = ?"
        params.append(project_id)

    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def update_knowledge(
    knowledge_id: int,
    content: Optional[str] = None,
    category: Optional[str] = None,
    project_id: Optional[int] = None,
    confidence: Optional[float] = None,
    source: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> bool:
    """
    Update an existing knowledge entry.

    Only the provided fields will be updated; others remain unchanged.

    Args:
        knowledge_id: The ID of the knowledge entry to update
        content: New content (optional)
        category: New category (optional)
        project_id: New project ID (optional)
        confidence: New confidence level (optional)
        source: New source (optional)
        tags: New tags list (optional)

    Returns:
        True if update succeeded, False if entry not found
    """
    # First check if the entry exists
    existing = get_knowledge(knowledge_id)
    if not existing:
        return False

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Build dynamic UPDATE query with only provided fields
    updates = []
    params = []

    if content is not None:
        updates.append("content = ?")
        params.append(content)

    if category is not None:
        updates.append("category = ?")
        params.append(category)

    if project_id is not None:
        updates.append("project_id = ?")
        params.append(project_id)

    if confidence is not None:
        updates.append("confidence = ?")
        params.append(confidence)

    if source is not None:
        updates.append("source = ?")
        params.append(source)

    if tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(tags))

    # Always update the updated_at timestamp
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())

    # Add the ID for WHERE clause
    params.append(knowledge_id)

    sql = f"UPDATE knowledge SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(sql, params)

    conn.commit()
    conn.close()

    return True


def delete_knowledge(knowledge_id: int) -> bool:
    """
    Delete a knowledge entry by ID.

    Args:
        knowledge_id: The ID of the knowledge entry to delete

    Returns:
        True if deletion succeeded, False if entry not found
    """
    # First check if the entry exists
    existing = get_knowledge(knowledge_id)
    if not existing:
        return False

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM knowledge WHERE id = ?", (knowledge_id,))

    conn.commit()
    conn.close()

    return True


# ============================================================================
# Decision Tracking Functions
# ============================================================================

def record_decision(
    content: str,
    context: Optional[str] = None,
    project_id: Optional[int] = None,
    alternatives: Optional[List[str]] = None,
    capture_id: Optional[int] = None
) -> int:
    """
    Record a decision in the decisions table.

    Decisions are significant choices with potential long-term impact.
    Use this when the user makes or records an explicit decision.

    Args:
        content: The decision that was made
        context: Why this decision was made (rationale)
        project_id: Optional link to a project
        alternatives: What alternatives were considered
        capture_id: Optional link to source capture

    Returns:
        The ID of the created decision
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO decisions (
            content, context, alternatives, project_id, capture_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        content,
        context,
        json.dumps(alternatives) if alternatives else None,
        project_id,
        capture_id,
        datetime.now().isoformat()
    ))

    decision_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return decision_id


def get_decision(decision_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a decision by ID.

    Args:
        decision_id: The ID of the decision

    Returns:
        Dict with decision details or None if not found
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, content, context, alternatives, project_id, capture_id,
               outcome, outcome_date, outcome_assessment, lessons_learned,
               created_at
        FROM decisions
        WHERE id = ?
    """, (decision_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "content": row["content"],
            "context": row["context"],
            "alternatives": json.loads(row["alternatives"]) if row["alternatives"] else [],
            "project_id": row["project_id"],
            "capture_id": row["capture_id"],
            "outcome": row["outcome"],
            "outcome_date": row["outcome_date"],
            "outcome_assessment": row["outcome_assessment"],
            "lessons_learned": row["lessons_learned"],
            "created_at": row["created_at"]
        }
    return None


def link_outcome(
    decision_id: int,
    outcome: str,
    assessment: Optional[str] = None,
    lessons_learned: Optional[str] = None
) -> bool:
    """
    Link an outcome to a recorded decision.

    Use this to track how decisions turned out, enabling learning
    from past choices.

    Args:
        decision_id: The ID of the decision to update
        outcome: What actually happened as a result of this decision
        assessment: One of: positive, negative, neutral
        lessons_learned: Optional lessons/reflections from this decision

    Returns:
        True if update succeeded, False if decision not found
    """
    # First check if the decision exists
    existing = get_decision(decision_id)
    if not existing:
        return False

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE decisions
        SET outcome = ?,
            outcome_date = ?,
            outcome_assessment = ?,
            lessons_learned = ?
        WHERE id = ?
    """, (
        outcome,
        datetime.now().isoformat(),
        assessment,
        lessons_learned,
        decision_id
    ))

    conn.commit()
    conn.close()

    return True


def get_decisions_pending_outcome(days_old: int = 30) -> List[Dict[str, Any]]:
    """
    Get decisions that don't have outcomes recorded.

    These are decisions that were made at least N days ago but haven't
    been followed up on to record what happened.

    Args:
        days_old: Only include decisions older than N days (default 30)

    Returns:
        List of decisions without outcomes, oldest first
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, content, context, alternatives, project_id, capture_id,
               outcome, outcome_date, outcome_assessment, lessons_learned,
               created_at
        FROM decisions
        WHERE outcome IS NULL
          AND date(created_at) <= date(?, '-' || ? || ' days')
        ORDER BY created_at ASC
    """, (datetime.now().isoformat(), days_old))

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "content": row["content"],
            "context": row["context"],
            "alternatives": json.loads(row["alternatives"]) if row["alternatives"] else [],
            "project_id": row["project_id"],
            "capture_id": row["capture_id"],
            "outcome": row["outcome"],
            "outcome_date": row["outcome_date"],
            "outcome_assessment": row["outcome_assessment"],
            "lessons_learned": row["lessons_learned"],
            "created_at": row["created_at"]
        })

    return results


def list_decisions(
    project_id: Optional[int] = None,
    with_outcome: Optional[bool] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List decisions with optional filters.

    Args:
        project_id: Filter by project
        with_outcome: If True, only with outcomes; if False, only without
        limit: Maximum results

    Returns:
        List of decisions
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql = """
        SELECT id, content, context, alternatives, project_id, capture_id,
               outcome, outcome_date, outcome_assessment, lessons_learned,
               created_at
        FROM decisions
        WHERE 1=1
    """
    params = []

    if project_id is not None:
        sql += " AND project_id = ?"
        params.append(project_id)

    if with_outcome is True:
        sql += " AND outcome IS NOT NULL"
    elif with_outcome is False:
        sql += " AND outcome IS NULL"

    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "content": row["content"],
            "context": row["context"],
            "alternatives": json.loads(row["alternatives"]) if row["alternatives"] else [],
            "project_id": row["project_id"],
            "capture_id": row["capture_id"],
            "outcome": row["outcome"],
            "outcome_date": row["outcome_date"],
            "outcome_assessment": row["outcome_assessment"],
            "lessons_learned": row["lessons_learned"],
            "created_at": row["created_at"]
        })

    return results


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="PCP Knowledge Base - Permanent facts and decisions"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add new knowledge")
    add_parser.add_argument("content", help="The knowledge content")
    add_parser.add_argument(
        "--category", "-c",
        default="fact",
        choices=["architecture", "decision", "fact", "preference"],
        help="Category of knowledge"
    )
    add_parser.add_argument("--project", "-p", type=int, help="Project ID to link to")
    add_parser.add_argument(
        "--confidence", "-C",
        type=float,
        default=1.0,
        help="Confidence level 0.0-1.0"
    )
    add_parser.add_argument("--source", "-s", help="Source of this knowledge")
    add_parser.add_argument("--tags", "-t", help="Comma-separated tags")

    # Get command
    get_parser = subparsers.add_parser("get", help="Get knowledge by ID")
    get_parser.add_argument("id", type=int, help="Knowledge ID")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search knowledge by content")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--category", "-c",
        choices=["architecture", "decision", "fact", "preference"],
        help="Filter by category"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List knowledge entries")
    list_parser.add_argument(
        "--category", "-c",
        choices=["architecture", "decision", "fact", "preference"],
        help="Filter by category"
    )
    list_parser.add_argument("--project", "-p", type=int, help="Filter by project ID")
    list_parser.add_argument("--limit", "-l", type=int, default=50, help="Max results")

    # Decision command - record a new decision
    decision_parser = subparsers.add_parser("decision", help="Record a new decision")
    decision_parser.add_argument("content", help="The decision that was made")
    decision_parser.add_argument("--context", "-c", help="Why this decision was made (rationale)")
    decision_parser.add_argument("--project", "-p", type=int, help="Project ID to link to")
    decision_parser.add_argument("--alternatives", "-a", help="Comma-separated alternatives considered")

    # Outcome command - link an outcome to a decision
    outcome_parser = subparsers.add_parser("outcome", help="Link an outcome to a decision")
    outcome_parser.add_argument("id", type=int, help="Decision ID")
    outcome_parser.add_argument("result", help="What actually happened")
    outcome_parser.add_argument(
        "--assessment", "-a",
        choices=["positive", "negative", "neutral"],
        help="Assessment of the outcome"
    )
    outcome_parser.add_argument("--lessons", "-l", help="Lessons learned from this decision")

    # Decisions list command - list decisions
    decisions_parser = subparsers.add_parser("decisions", help="List decisions")
    decisions_parser.add_argument("--project", "-p", type=int, help="Filter by project ID")
    decisions_parser.add_argument("--pending", action="store_true", help="Show only decisions without outcomes")
    decisions_parser.add_argument("--with-outcome", action="store_true", help="Show only decisions with outcomes")
    decisions_parser.add_argument("--limit", type=int, default=50, help="Max results")

    args = parser.parse_args()

    if args.command == "add":
        tags = args.tags.split(",") if args.tags else None
        knowledge_id = add_knowledge(
            content=args.content,
            category=args.category,
            project_id=args.project,
            confidence=args.confidence,
            source=args.source,
            tags=tags
        )
        print(f"Added knowledge (ID: {knowledge_id})")
        print(f"  Category: {args.category}")
        print(f"  Content: {args.content[:80]}{'...' if len(args.content) > 80 else ''}")

    elif args.command == "get":
        knowledge = get_knowledge(args.id)
        if knowledge:
            print(f"ID: {knowledge['id']}")
            print(f"Category: {knowledge['category']}")
            print(f"Content: {knowledge['content']}")
            print(f"Confidence: {knowledge['confidence']}")
            if knowledge['project_id']:
                print(f"Project ID: {knowledge['project_id']}")
            if knowledge['source']:
                print(f"Source: {knowledge['source']}")
            if knowledge['tags']:
                print(f"Tags: {', '.join(knowledge['tags'])}")
            print(f"Created: {knowledge['created_at']}")
        else:
            print(f"Knowledge with ID {args.id} not found")
            sys.exit(1)

    elif args.command == "search":
        results = query_knowledge(args.query, category=args.category)
        if results:
            print(f"Found {len(results)} result(s) for '{args.query}':\n")
            for k in results:
                print(f"[{k['id']}] ({k['category']}) {k['content'][:80]}{'...' if len(k['content']) > 80 else ''}")
        else:
            print(f"No results found for '{args.query}'")

    elif args.command == "list":
        results = list_knowledge(
            category=args.category,
            project_id=args.project,
            limit=args.limit
        )
        if results:
            print(f"Knowledge entries ({len(results)}):\n")
            for k in results:
                print(f"[{k['id']}] ({k['category']}) {k['content'][:80]}{'...' if len(k['content']) > 80 else ''}")
        else:
            print("No knowledge entries found")

    elif args.command == "decision":
        alternatives = args.alternatives.split(",") if args.alternatives else None
        decision_id = record_decision(
            content=args.content,
            context=args.context,
            project_id=args.project,
            alternatives=alternatives
        )
        print(f"Recorded decision (ID: {decision_id})")
        print(f"  Decision: {args.content[:80]}{'...' if len(args.content) > 80 else ''}")
        if args.context:
            print(f"  Context: {args.context[:60]}{'...' if len(args.context) > 60 else ''}")
        if alternatives:
            print(f"  Alternatives: {', '.join(alternatives)}")

    elif args.command == "outcome":
        success = link_outcome(
            decision_id=args.id,
            outcome=args.result,
            assessment=args.assessment,
            lessons_learned=args.lessons
        )
        if success:
            print(f"Linked outcome to decision {args.id}")
            print(f"  Outcome: {args.result[:80]}{'...' if len(args.result) > 80 else ''}")
            if args.assessment:
                print(f"  Assessment: {args.assessment}")
            if args.lessons:
                print(f"  Lessons: {args.lessons[:60]}{'...' if len(args.lessons) > 60 else ''}")
        else:
            print(f"Decision with ID {args.id} not found")
            sys.exit(1)

    elif args.command == "decisions":
        # Determine with_outcome filter
        with_outcome = None
        if args.pending:
            with_outcome = False
        elif args.with_outcome:
            with_outcome = True

        results = list_decisions(
            project_id=args.project,
            with_outcome=with_outcome,
            limit=args.limit
        )
        if results:
            print(f"Decisions ({len(results)}):\n")
            for d in results:
                outcome_status = "[+]" if d["outcome"] else "[ ]"
                print(f"{outcome_status} [{d['id']}] {d['content'][:70]}{'...' if len(d['content']) > 70 else ''}")
                if d["context"]:
                    print(f"      Context: {d['context'][:50]}{'...' if len(d['context']) > 50 else ''}")
        else:
            print("No decisions found")

    else:
        parser.print_help()
