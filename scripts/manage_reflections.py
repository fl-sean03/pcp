#!/usr/bin/env python3
"""
Manage Reflections - CLI for viewing and managing PCP self-reflection history.

Usage:
    python manage_reflections.py list              # List recent reflections
    python manage_reflections.py view <id>         # View specific reflection
    python manage_reflections.py pending           # View pending recommendations
    python manage_reflections.py approve <id> QW-1,QW-2  # Approve recommendations
    python manage_reflections.py reject <id> QW-3 --reason "Not worth it"
    python manage_reflections.py implemented <id> QW-1 --outcome "Worked great"
    python manage_reflections.py stats             # Show reflection statistics
"""

import os
import sys
import json
from datetime import datetime
from typing import Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db import get_db_connection, execute_query, execute_write

# Database path
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(VAULT_PATH):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    VAULT_PATH = os.path.join(base, "vault", "vault.db")


def list_reflections(limit: int = 10) -> List[dict]:
    """List recent reflection sessions."""
    try:
        reflections = execute_query("""
            SELECT id, session_id, days_analyzed, status, created_at,
                   (SELECT COUNT(*) FROM reflection_recommendations
                    WHERE reflection_id = reflection_history.id) as rec_count
            FROM reflection_history
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,), VAULT_PATH)
        return reflections
    except Exception as e:
        print(f"Error: {e}")
        return []


def view_reflection(reflection_id: int) -> Optional[dict]:
    """Get a specific reflection with its recommendations."""
    try:
        reflections = execute_query("""
            SELECT * FROM reflection_history WHERE id = ?
        """, (reflection_id,), VAULT_PATH)

        if not reflections:
            return None

        reflection = reflections[0]

        # Get recommendations
        recommendations = execute_query("""
            SELECT * FROM reflection_recommendations
            WHERE reflection_id = ?
            ORDER BY category, priority
        """, (reflection_id,), VAULT_PATH)

        reflection['recommendations'] = recommendations
        return reflection
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_pending_recommendations() -> List[dict]:
    """Get all pending recommendations across all reflections."""
    try:
        return execute_query("""
            SELECT r.*, h.session_id, h.created_at as reflection_date
            FROM reflection_recommendations r
            JOIN reflection_history h ON r.reflection_id = h.id
            WHERE r.status = 'pending'
            ORDER BY r.category, r.priority
        """, (), VAULT_PATH)
    except Exception as e:
        print(f"Error: {e}")
        return []


def update_recommendation_status(
    reflection_id: int,
    rec_id: str,
    status: str,
    notes: Optional[str] = None
) -> bool:
    """Update the status of a recommendation."""
    try:
        execute_write("""
            UPDATE reflection_recommendations
            SET status = ?, status_updated_at = ?, status_notes = ?
            WHERE reflection_id = ? AND recommendation_id = ?
        """, (status, datetime.now().isoformat(), notes, reflection_id, rec_id), VAULT_PATH)
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def record_outcome(
    reflection_id: int,
    rec_id: str,
    outcome: str,
    assessment: str = "positive"
) -> bool:
    """Record the outcome of an implemented recommendation."""
    try:
        execute_write("""
            UPDATE reflection_recommendations
            SET status = 'implemented',
                outcome = ?,
                outcome_date = ?,
                outcome_assessment = ?,
                status_updated_at = ?
            WHERE reflection_id = ? AND recommendation_id = ?
        """, (
            outcome,
            datetime.now().isoformat(),
            assessment,
            datetime.now().isoformat(),
            reflection_id,
            rec_id
        ), VAULT_PATH)
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def get_stats() -> dict:
    """Get reflection statistics."""
    stats = {
        "total_reflections": 0,
        "total_recommendations": 0,
        "by_status": {},
        "by_category": {},
        "approval_rate": 0,
        "implementation_rate": 0
    }

    try:
        # Total reflections
        result = execute_query(
            "SELECT COUNT(*) as count FROM reflection_history", (), VAULT_PATH)
        stats["total_reflections"] = result[0]["count"] if result else 0

        # Total recommendations
        result = execute_query(
            "SELECT COUNT(*) as count FROM reflection_recommendations", (), VAULT_PATH)
        stats["total_recommendations"] = result[0]["count"] if result else 0

        # By status
        result = execute_query("""
            SELECT status, COUNT(*) as count
            FROM reflection_recommendations
            GROUP BY status
        """, (), VAULT_PATH)
        stats["by_status"] = {r["status"]: r["count"] for r in result}

        # By category
        result = execute_query("""
            SELECT category, COUNT(*) as count
            FROM reflection_recommendations
            GROUP BY category
        """, (), VAULT_PATH)
        stats["by_category"] = {r["category"]: r["count"] for r in result}

        # Calculate rates
        total = stats["total_recommendations"]
        if total > 0:
            approved = stats["by_status"].get("approved", 0) + stats["by_status"].get("implemented", 0)
            stats["approval_rate"] = round(approved / total * 100, 1)

            implemented = stats["by_status"].get("implemented", 0)
            stats["implementation_rate"] = round(implemented / total * 100, 1)

    except Exception as e:
        print(f"Error getting stats: {e}")

    return stats


def print_reflections_list(reflections: List[dict]):
    """Print formatted list of reflections."""
    if not reflections:
        print("No reflections found.")
        return

    print("\n" + "=" * 70)
    print("REFLECTION HISTORY")
    print("=" * 70)

    for r in reflections:
        status_icon = {
            'pending_review': '⏳',
            'reviewed': '✓',
            'actioned': '✅'
        }.get(r.get('status', ''), '?')

        print(f"\n[{r['id']}] Session: {r['session_id']} {status_icon}")
        print(f"    Period: {r['days_analyzed']} days | Created: {r['created_at'][:10]}")
        print(f"    Recommendations: {r.get('rec_count', 0)} | Status: {r.get('status', 'unknown')}")


def print_reflection_detail(reflection: dict):
    """Print detailed view of a reflection."""
    print("\n" + "=" * 70)
    print(f"REFLECTION: {reflection['session_id']}")
    print("=" * 70)

    print(f"\nPeriod: {reflection['period_start'][:10]} to {reflection['period_end'][:10]}")
    print(f"Days Analyzed: {reflection['days_analyzed']}")
    print(f"Status: {reflection['status']}")
    print(f"Created: {reflection['created_at']}")

    if reflection.get('metrics'):
        try:
            metrics = json.loads(reflection['metrics']) if isinstance(reflection['metrics'], str) else reflection['metrics']
            print(f"\nMetrics: {json.dumps(metrics, indent=2)}")
        except:
            pass

    recommendations = reflection.get('recommendations', [])
    if recommendations:
        print(f"\n{'=' * 70}")
        print("RECOMMENDATIONS")
        print("=" * 70)

        # Group by category
        by_cat = {}
        for r in recommendations:
            cat = r.get('category', 'other')
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(r)

        for cat, recs in by_cat.items():
            print(f"\n## {cat.upper().replace('_', ' ')}")
            for r in recs:
                status_icon = {
                    'pending': '⏳',
                    'approved': '✓',
                    'rejected': '✗',
                    'implemented': '✅',
                    'deferred': '⏸'
                }.get(r.get('status', ''), '?')

                print(f"\n  [{r['recommendation_id']}] {r['title']} {status_icon}")
                if r.get('proposal'):
                    proposal = r['proposal'][:100] + "..." if len(r['proposal']) > 100 else r['proposal']
                    print(f"      Proposal: {proposal}")
                print(f"      Status: {r.get('status', 'unknown')}")


def print_pending(recommendations: List[dict]):
    """Print pending recommendations."""
    if not recommendations:
        print("No pending recommendations.")
        return

    print("\n" + "=" * 70)
    print("PENDING RECOMMENDATIONS")
    print("=" * 70)

    current_cat = None
    for r in recommendations:
        cat = r.get('category', 'other')
        if cat != current_cat:
            print(f"\n## {cat.upper().replace('_', ' ')}")
            current_cat = cat

        print(f"\n  [{r['reflection_id']}:{r['recommendation_id']}] {r['title']}")
        print(f"      From: {r.get('reflection_date', 'unknown')[:10]}")
        if r.get('proposal'):
            proposal = r['proposal'][:150] + "..." if len(r['proposal']) > 150 else r['proposal']
            print(f"      Proposal: {proposal}")


def print_stats(stats: dict):
    """Print reflection statistics."""
    print("\n" + "=" * 70)
    print("REFLECTION STATISTICS")
    print("=" * 70)

    print(f"\nTotal Reflections: {stats['total_reflections']}")
    print(f"Total Recommendations: {stats['total_recommendations']}")

    print(f"\nApproval Rate: {stats['approval_rate']}%")
    print(f"Implementation Rate: {stats['implementation_rate']}%")

    if stats['by_status']:
        print("\nBy Status:")
        for status, count in stats['by_status'].items():
            print(f"  {status}: {count}")

    if stats['by_category']:
        print("\nBy Category:")
        for cat, count in stats['by_category'].items():
            print(f"  {cat}: {count}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage PCP reflections")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List command
    list_parser = subparsers.add_parser("list", help="List recent reflections")
    list_parser.add_argument("--limit", "-l", type=int, default=10)

    # View command
    view_parser = subparsers.add_parser("view", help="View a specific reflection")
    view_parser.add_argument("reflection_id", type=int)

    # Pending command
    pending_parser = subparsers.add_parser("pending", help="View pending recommendations")

    # Approve command
    approve_parser = subparsers.add_parser("approve", help="Approve recommendations")
    approve_parser.add_argument("reflection_id", type=int)
    approve_parser.add_argument("items", help="Comma-separated recommendation IDs (e.g., QW-1,QW-2)")

    # Reject command
    reject_parser = subparsers.add_parser("reject", help="Reject a recommendation")
    reject_parser.add_argument("reflection_id", type=int)
    reject_parser.add_argument("item", help="Recommendation ID (e.g., QW-1)")
    reject_parser.add_argument("--reason", "-r", help="Reason for rejection")

    # Defer command
    defer_parser = subparsers.add_parser("defer", help="Defer a recommendation")
    defer_parser.add_argument("reflection_id", type=int)
    defer_parser.add_argument("item", help="Recommendation ID")
    defer_parser.add_argument("--until", "-u", help="When to revisit")

    # Implemented command
    impl_parser = subparsers.add_parser("implemented", help="Mark recommendation as implemented")
    impl_parser.add_argument("reflection_id", type=int)
    impl_parser.add_argument("item", help="Recommendation ID")
    impl_parser.add_argument("--outcome", "-o", required=True, help="Outcome description")
    impl_parser.add_argument("--assessment", "-a", default="positive",
                            choices=["positive", "negative", "neutral", "mixed"])

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show reflection statistics")

    args = parser.parse_args()

    if args.command == "list":
        reflections = list_reflections(args.limit)
        print_reflections_list(reflections)

    elif args.command == "view":
        reflection = view_reflection(args.reflection_id)
        if reflection:
            print_reflection_detail(reflection)
        else:
            print(f"Reflection {args.reflection_id} not found")

    elif args.command == "pending":
        pending = get_pending_recommendations()
        print_pending(pending)

    elif args.command == "approve":
        items = [i.strip() for i in args.items.split(",")]
        for item in items:
            if update_recommendation_status(args.reflection_id, item, "approved"):
                print(f"Approved: {item}")
            else:
                print(f"Failed to approve: {item}")

    elif args.command == "reject":
        if update_recommendation_status(args.reflection_id, args.item, "rejected", args.reason):
            print(f"Rejected: {args.item}")
        else:
            print(f"Failed to reject: {args.item}")

    elif args.command == "defer":
        notes = f"Deferred until: {args.until}" if args.until else None
        if update_recommendation_status(args.reflection_id, args.item, "deferred", notes):
            print(f"Deferred: {args.item}")
        else:
            print(f"Failed to defer: {args.item}")

    elif args.command == "implemented":
        if record_outcome(args.reflection_id, args.item, args.outcome, args.assessment):
            print(f"Marked as implemented: {args.item}")
        else:
            print(f"Failed to update: {args.item}")

    elif args.command == "stats":
        stats = get_stats()
        print_stats(stats)

    else:
        parser.print_help()
