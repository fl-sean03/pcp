#!/usr/bin/env python3
"""
Export Reflection Context - Aggregates all data for PCP self-reflection sessions.

This script collects data from:
- Discord message history (archive database)
- Vault state (captures, tasks, knowledge, people, projects)
- Previous reflection history
- Usage metrics

The output is a unified JSON context that the reflection agent uses to analyze
PCP usage and propose improvements.

Usage:
    python export_reflection_context.py --days 7 --output /tmp/reflection_context.json
    python export_reflection_context.py --days 30 --summary  # Print summary only
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db import get_db_connection, rows_to_dicts, execute_query

# Database paths
VAULT_PATH = "/workspace/vault/vault.db"
DISCORD_ARCHIVE_PATH = "/srv/agentops/data/discord-archive/messages.db"

# Fallback for local development
if not os.path.exists(VAULT_PATH):
    _local = os.path.join(os.path.dirname(__file__), "..", "vault", "vault.db")
    if os.path.exists(_local):
        VAULT_PATH = _local


def get_discord_history(days: int = 7) -> List[Dict[str, Any]]:
    """
    Get Discord messages from archive database.

    Args:
        days: Number of days to look back

    Returns:
        List of message dictionaries, chronologically ordered
    """
    if not os.path.exists(DISCORD_ARCHIVE_PATH):
        return []

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    try:
        conn = sqlite3.connect(DISCORD_ARCHIVE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Try to get messages - schema may vary
        try:
            cursor.execute("""
                SELECT * FROM messages
                WHERE created_at >= ?
                ORDER BY created_at ASC
            """, (cutoff,))
            messages = rows_to_dicts(cursor.fetchall())
        except sqlite3.OperationalError:
            # Try alternate schema
            cursor.execute("SELECT * FROM messages ORDER BY rowid DESC LIMIT 1000")
            messages = rows_to_dicts(cursor.fetchall())

        conn.close()
        return messages
    except Exception as e:
        print(f"Warning: Could not read Discord archive: {e}", file=sys.stderr)
        return []


def get_vault_snapshot() -> Dict[str, Any]:
    """
    Get current state of the vault database.

    Returns:
        Dictionary with all vault data:
        - captures: Recent captures
        - tasks: All tasks with status
        - knowledge: All knowledge entries
        - people: All people with stats
        - projects: All projects with health info
        - emails: Recent emails
        - decisions: All decisions
    """
    snapshot = {
        "captures": [],
        "tasks": [],
        "knowledge": [],
        "people": [],
        "projects": [],
        "emails": [],
        "decisions": [],
        "stats": {}
    }

    if not os.path.exists(VAULT_PATH):
        return snapshot

    try:
        conn = get_db_connection(VAULT_PATH)
        cursor = conn.cursor()

        # Recent captures (last 30 days)
        try:
            cursor.execute("""
                SELECT * FROM captures_v2
                WHERE created_at >= datetime('now', '-30 days')
                ORDER BY created_at DESC
            """)
            snapshot["captures"] = rows_to_dicts(cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # All tasks
        try:
            cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            snapshot["tasks"] = rows_to_dicts(cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # All knowledge
        try:
            cursor.execute("SELECT * FROM knowledge ORDER BY created_at DESC")
            snapshot["knowledge"] = rows_to_dicts(cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # All people
        try:
            cursor.execute("SELECT * FROM people ORDER BY mention_count DESC")
            snapshot["people"] = rows_to_dicts(cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # All projects
        try:
            cursor.execute("SELECT * FROM projects ORDER BY last_activity DESC")
            snapshot["projects"] = rows_to_dicts(cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # Recent emails (last 30 days)
        try:
            cursor.execute("""
                SELECT * FROM emails
                WHERE received_at >= datetime('now', '-30 days')
                ORDER BY received_at DESC
            """)
            snapshot["emails"] = rows_to_dicts(cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # All decisions
        try:
            cursor.execute("SELECT * FROM decisions ORDER BY created_at DESC")
            snapshot["decisions"] = rows_to_dicts(cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # Calculate stats
        snapshot["stats"] = calculate_vault_stats(cursor)

        conn.close()
    except Exception as e:
        print(f"Warning: Could not read vault: {e}", file=sys.stderr)

    return snapshot


def calculate_vault_stats(cursor) -> Dict[str, Any]:
    """Calculate high-level vault statistics."""
    stats = {}

    try:
        cursor.execute("SELECT COUNT(*) FROM captures_v2")
        stats["total_captures"] = cursor.fetchone()[0]
    except:
        stats["total_captures"] = 0

    try:
        cursor.execute("SELECT COUNT(*) FROM captures_v2 WHERE created_at >= datetime('now', '-7 days')")
        stats["captures_this_week"] = cursor.fetchone()[0]
    except:
        stats["captures_this_week"] = 0

    try:
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        stats["pending_tasks"] = cursor.fetchone()[0]
    except:
        stats["pending_tasks"] = 0

    try:
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'done' AND completed_at >= datetime('now', '-7 days')")
        stats["tasks_completed_this_week"] = cursor.fetchone()[0]
    except:
        stats["tasks_completed_this_week"] = 0

    try:
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE due_date < date('now') AND status = 'pending'")
        stats["overdue_tasks"] = cursor.fetchone()[0]
    except:
        stats["overdue_tasks"] = 0

    try:
        cursor.execute("SELECT COUNT(*) FROM knowledge")
        stats["total_knowledge"] = cursor.fetchone()[0]
    except:
        stats["total_knowledge"] = 0

    try:
        cursor.execute("SELECT COUNT(*) FROM people")
        stats["total_people"] = cursor.fetchone()[0]
    except:
        stats["total_people"] = 0

    try:
        cursor.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")
        stats["active_projects"] = cursor.fetchone()[0]
    except:
        stats["active_projects"] = 0

    return stats


def get_previous_reflections(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get recent reflection history for context.

    Args:
        limit: Maximum number of reflections to retrieve

    Returns:
        List of reflection dictionaries with outcomes
    """
    if not os.path.exists(VAULT_PATH):
        return []

    try:
        reflections = execute_query("""
            SELECT * FROM reflection_history
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,), VAULT_PATH)

        # Also get recommendations for each reflection
        for reflection in reflections:
            reflection["recommendations"] = execute_query("""
                SELECT * FROM reflection_recommendations
                WHERE reflection_id = ?
                ORDER BY priority ASC
            """, (reflection["id"],), VAULT_PATH)

        return reflections
    except sqlite3.OperationalError:
        # Tables don't exist yet
        return []
    except Exception as e:
        print(f"Warning: Could not read reflections: {e}", file=sys.stderr)
        return []


def get_friction_events(days: int = 7) -> List[Dict[str, Any]]:
    """
    Identify potential friction events from Discord history.

    Friction events are indicators of issues:
    - Messages quickly followed by retries
    - Error responses from bot
    - Clarification requests
    - Long gaps then retry

    Args:
        days: Number of days to analyze

    Returns:
        List of potential friction events
    """
    messages = get_discord_history(days)
    if not messages:
        return []

    friction_events = []

    # Look for patterns indicating friction
    for i, msg in enumerate(messages):
        content = msg.get("content", "").lower()

        # Bot error responses
        if "error" in content and msg.get("author_id") != msg.get("user_id"):
            friction_events.append({
                "type": "error_response",
                "message": msg,
                "timestamp": msg.get("created_at")
            })

        # "Try again" or retry patterns
        if any(phrase in content for phrase in ["try again", "retry", "not what i", "that's not"]):
            friction_events.append({
                "type": "retry_request",
                "message": msg,
                "timestamp": msg.get("created_at")
            })

        # Clarification requests
        if any(phrase in content for phrase in ["what do you mean", "i meant", "no i want", "actually"]):
            friction_events.append({
                "type": "clarification",
                "message": msg,
                "timestamp": msg.get("created_at")
            })

    return friction_events


def get_capability_gaps(days: int = 7) -> Dict[str, Any]:
    """
    Get capability gap data for reflection.

    Args:
        days: Number of days to analyze

    Returns:
        Dictionary with gap data and statistics
    """
    gap_data = {
        "recent_gaps": [],
        "unresolved_gaps": [],
        "statistics": {},
        "top_patterns": []
    }

    if not os.path.exists(VAULT_PATH):
        return gap_data

    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        # Recent gaps (within period)
        recent = execute_query("""
            SELECT * FROM capability_gaps
            WHERE detected_at >= ?
            ORDER BY detected_at DESC
        """, (cutoff,), VAULT_PATH)
        gap_data["recent_gaps"] = recent if recent else []

        # Unresolved gaps (any status that's not 'resolved')
        unresolved = execute_query("""
            SELECT * FROM capability_gaps
            WHERE status NOT IN ('resolved')
            ORDER BY detected_at DESC
            LIMIT 20
        """, (), VAULT_PATH)
        gap_data["unresolved_gaps"] = unresolved if unresolved else []

        # Statistics
        stats_result = execute_query("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'user_pending' THEN 1 ELSE 0 END) as user_pending
            FROM capability_gaps
        """, (), VAULT_PATH)
        if stats_result:
            s = stats_result[0]
            gap_data["statistics"] = {
                "total": s["total"] or 0,
                "resolved": s["resolved"] or 0,
                "failed": s["failed"] or 0,
                "user_pending": s["user_pending"] or 0,
                "resolution_rate": (s["resolved"] or 0) / s["total"] if s["total"] else 0
            }

        # Top patterns (most common gaps)
        patterns = execute_query("""
            SELECT pattern_id, gap_type, COUNT(*) as count
            FROM capability_gaps
            WHERE pattern_id IS NOT NULL
            GROUP BY pattern_id
            ORDER BY count DESC
            LIMIT 10
        """, (), VAULT_PATH)
        gap_data["top_patterns"] = patterns if patterns else []

    except sqlite3.OperationalError:
        # Table doesn't exist yet
        pass
    except Exception as e:
        print(f"Warning: Could not read capability gaps: {e}", file=sys.stderr)

    return gap_data


def calculate_usage_metrics(days: int = 7) -> Dict[str, Any]:
    """
    Calculate high-level usage metrics.

    Args:
        days: Period to analyze

    Returns:
        Dictionary of metrics
    """
    metrics = {
        "period_days": days,
        "discord_messages": 0,
        "captures_created": 0,
        "tasks_created": 0,
        "tasks_completed": 0,
        "knowledge_added": 0,
        "friction_events": 0,
        "capability_gaps_detected": 0,
        "capability_gaps_resolved": 0,
        "feature_usage": {}
    }

    # Count Discord messages
    messages = get_discord_history(days)
    metrics["discord_messages"] = len(messages)

    # Count friction events
    friction = get_friction_events(days)
    metrics["friction_events"] = len(friction)

    # Get vault metrics
    if os.path.exists(VAULT_PATH):
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            result = execute_query(
                "SELECT COUNT(*) as count FROM captures_v2 WHERE created_at >= ?",
                (cutoff,), VAULT_PATH
            )
            metrics["captures_created"] = result[0]["count"] if result else 0

            result = execute_query(
                "SELECT COUNT(*) as count FROM tasks WHERE created_at >= ?",
                (cutoff,), VAULT_PATH
            )
            metrics["tasks_created"] = result[0]["count"] if result else 0

            result = execute_query(
                "SELECT COUNT(*) as count FROM tasks WHERE completed_at >= ?",
                (cutoff,), VAULT_PATH
            )
            metrics["tasks_completed"] = result[0]["count"] if result else 0

            result = execute_query(
                "SELECT COUNT(*) as count FROM knowledge WHERE created_at >= ?",
                (cutoff,), VAULT_PATH
            )
            metrics["knowledge_added"] = result[0]["count"] if result else 0

            # Capability gaps
            try:
                result = execute_query(
                    "SELECT COUNT(*) as count FROM capability_gaps WHERE detected_at >= ?",
                    (cutoff,), VAULT_PATH
                )
                metrics["capability_gaps_detected"] = result[0]["count"] if result else 0

                result = execute_query(
                    "SELECT COUNT(*) as count FROM capability_gaps WHERE resolved_at >= ?",
                    (cutoff,), VAULT_PATH
                )
                metrics["capability_gaps_resolved"] = result[0]["count"] if result else 0
            except sqlite3.OperationalError:
                pass  # Table doesn't exist

        except Exception as e:
            print(f"Warning: Could not calculate metrics: {e}", file=sys.stderr)

    return metrics


def read_system_docs() -> Dict[str, str]:
    """
    Read key system documentation files.

    Returns:
        Dictionary mapping doc name to content
    """
    docs = {}

    doc_paths = {
        "VISION": "/workspace/VISION.md",
        "CLAUDE_MD": "/workspace/CLAUDE.md",
    }

    # Add local fallbacks
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_paths = {
        "VISION": os.path.join(base, "VISION.md"),
        "CLAUDE_MD": os.path.join(base, "CLAUDE.md"),
    }

    for name, path in doc_paths.items():
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    docs[name] = f.read()
            elif os.path.exists(local_paths.get(name, "")):
                with open(local_paths[name], 'r') as f:
                    docs[name] = f.read()
        except Exception as e:
            docs[name] = f"[Could not read: {e}]"

    return docs


def export_for_reflection(
    days: int = 7,
    output_path: Optional[str] = None,
    include_docs: bool = True
) -> Dict[str, Any]:
    """
    Export all context needed for a reflection session.

    Args:
        days: Number of days to analyze
        output_path: Optional path to save JSON export
        include_docs: Whether to include full doc content

    Returns:
        Complete context dictionary
    """
    now = datetime.now()

    context = {
        "export_metadata": {
            "exported_at": now.isoformat(),
            "period_start": (now - timedelta(days=days)).isoformat(),
            "period_end": now.isoformat(),
            "days_analyzed": days
        },
        "discord_history": get_discord_history(days),
        "vault_snapshot": get_vault_snapshot(),
        "previous_reflections": get_previous_reflections(5),
        "friction_events": get_friction_events(days),
        "usage_metrics": calculate_usage_metrics(days),
        "capability_gaps": get_capability_gaps(days),
    }

    if include_docs:
        context["system_docs"] = read_system_docs()

    # Save to file if path provided
    if output_path:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(context, f, indent=2, default=str)
        print(f"Exported reflection context to {output_path}")

    return context


def print_summary(context: Dict[str, Any]):
    """Print a human-readable summary of the exported context."""
    meta = context["export_metadata"]
    metrics = context["usage_metrics"]
    vault = context["vault_snapshot"]

    print("=" * 60)
    print("PCP REFLECTION CONTEXT SUMMARY")
    print("=" * 60)
    print(f"Period: {meta['days_analyzed']} days")
    print(f"Exported: {meta['exported_at']}")
    print()

    print("USAGE METRICS:")
    print(f"  Discord messages: {metrics['discord_messages']}")
    print(f"  Captures created: {metrics['captures_created']}")
    print(f"  Tasks created: {metrics['tasks_created']}")
    print(f"  Tasks completed: {metrics['tasks_completed']}")
    print(f"  Knowledge added: {metrics['knowledge_added']}")
    print(f"  Friction events: {metrics['friction_events']}")
    print()

    print("VAULT STATE:")
    stats = vault.get("stats", {})
    print(f"  Total captures: {stats.get('total_captures', 0)}")
    print(f"  Pending tasks: {stats.get('pending_tasks', 0)}")
    print(f"  Overdue tasks: {stats.get('overdue_tasks', 0)}")
    print(f"  Total knowledge: {stats.get('total_knowledge', 0)}")
    print(f"  Active projects: {stats.get('active_projects', 0)}")
    print()

    print("PREVIOUS REFLECTIONS:")
    reflections = context.get("previous_reflections", [])
    if reflections:
        for r in reflections[:3]:
            print(f"  - {r.get('created_at', 'Unknown')}: {r.get('status', 'unknown')}")
    else:
        print("  (No previous reflections)")
    print()

    print("FRICTION EVENTS:")
    friction = context.get("friction_events", [])
    if friction:
        by_type = {}
        for f in friction:
            t = f.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in by_type.items():
            print(f"  - {t}: {count}")
    else:
        print("  (No friction events detected)")
    print()

    print("CAPABILITY GAPS:")
    gaps = context.get("capability_gaps", {})
    gap_stats = gaps.get("statistics", {})
    if gap_stats.get("total", 0) > 0:
        print(f"  Total gaps: {gap_stats.get('total', 0)}")
        print(f"  Resolved: {gap_stats.get('resolved', 0)}")
        print(f"  Failed: {gap_stats.get('failed', 0)}")
        print(f"  Pending user input: {gap_stats.get('user_pending', 0)}")
        print(f"  Resolution rate: {gap_stats.get('resolution_rate', 0):.1%}")
        print()
        print("  Top patterns:")
        for p in gaps.get("top_patterns", [])[:5]:
            print(f"    - {p.get('pattern_id', 'unknown')}: {p.get('count', 0)} occurrences")
    else:
        print("  (No capability gaps recorded)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export PCP reflection context")
    parser.add_argument("--days", "-d", type=int, default=7,
                       help="Number of days to analyze (default: 7)")
    parser.add_argument("--output", "-o", type=str,
                       help="Output file path for JSON export")
    parser.add_argument("--summary", "-s", action="store_true",
                       help="Print summary instead of full export")
    parser.add_argument("--no-docs", action="store_true",
                       help="Exclude system docs from export")

    args = parser.parse_args()

    context = export_for_reflection(
        days=args.days,
        output_path=args.output,
        include_docs=not args.no_docs
    )

    if args.summary or not args.output:
        print_summary(context)

    if not args.output and not args.summary:
        print("\nUse --output to save full JSON export")
