#!/usr/bin/env python3
"""
PCP Pattern Detection - Identifies patterns in the user's activity and captures.
Detects repeated mentions, time-based patterns, and generates suggestions.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from collections import Counter
from typing import Dict, List, Any, Optional

import os

# Support both container and local development paths
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)) and os.path.exists(os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault")):
    VAULT_PATH = os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db")


def detect_repeated_topics(threshold: int = 3, days: int = 7) -> List[Dict]:
    """
    Find topics mentioned multiple times within a time window.
    These might indicate something important that needs action.
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT extracted_entities, content
        FROM captures_v2
        WHERE created_at > datetime('now', ?)
        AND extracted_entities IS NOT NULL
    """, (f"-{days} days",))

    # Count topic mentions
    topic_counter = Counter()
    topic_contexts = {}

    for row in cursor.fetchall():
        try:
            entities = json.loads(row[0])
            content = row[1]

            for topic in entities.get("topics", []):
                topic_lower = topic.lower()
                topic_counter[topic_lower] += 1
                if topic_lower not in topic_contexts:
                    topic_contexts[topic_lower] = []
                topic_contexts[topic_lower].append(content[:100])

            for project in entities.get("projects", []):
                project_lower = project.lower()
                topic_counter[project_lower] += 1
                if project_lower not in topic_contexts:
                    topic_contexts[project_lower] = []
                topic_contexts[project_lower].append(content[:100])

        except (json.JSONDecodeError, TypeError):
            continue

    conn.close()

    # Return topics above threshold
    repeated = []
    for topic, count in topic_counter.most_common():
        if count >= threshold:
            repeated.append({
                "topic": topic,
                "count": count,
                "contexts": topic_contexts.get(topic, [])[:3]  # First 3 contexts
            })

    return repeated


def detect_repeated_people(threshold: int = 3, days: int = 7) -> List[Dict]:
    """Find people mentioned frequently."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, mention_count, last_mentioned, context
        FROM people
        WHERE mention_count >= ?
        AND last_mentioned > datetime('now', ?)
        ORDER BY mention_count DESC
    """, (threshold, f"-{days} days"))

    people = []
    for row in cursor.fetchall():
        people.append({
            "name": row[0],
            "mention_count": row[1],
            "last_mentioned": row[2],
            "context": row[3]
        })

    conn.close()
    return people


def detect_time_patterns() -> Dict[str, Any]:
    """
    Analyze when the user captures the most.
    Useful for scheduling briefs and reminders.
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Get captures by hour
    cursor.execute("""
        SELECT strftime('%H', created_at) as hour, COUNT(*) as count
        FROM captures_v2
        WHERE created_at > datetime('now', '-30 days')
        GROUP BY hour
        ORDER BY count DESC
    """)

    hour_counts = {}
    for row in cursor.fetchall():
        hour_counts[int(row[0])] = row[1]

    # Get captures by day of week
    cursor.execute("""
        SELECT strftime('%w', created_at) as dow, COUNT(*) as count
        FROM captures_v2
        WHERE created_at > datetime('now', '-30 days')
        GROUP BY dow
        ORDER BY count DESC
    """)

    dow_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    dow_counts = {}
    for row in cursor.fetchall():
        dow_counts[dow_names[int(row[0])]] = row[1]

    conn.close()

    # Find peak hours
    peak_hours = sorted(hour_counts.keys(), key=lambda h: hour_counts.get(h, 0), reverse=True)[:3]
    peak_days = sorted(dow_counts.keys(), key=lambda d: dow_counts.get(d, 0), reverse=True)[:3]

    return {
        "peak_hours": peak_hours,
        "peak_days": peak_days,
        "hour_distribution": hour_counts,
        "day_distribution": dow_counts
    }


def detect_stale_mentions(days: int = 14) -> List[Dict]:
    """
    Find people or projects mentioned but not followed up on.
    These might need attention.
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # People mentioned but not recently
    cursor.execute("""
        SELECT name, last_mentioned, context, mention_count
        FROM people
        WHERE last_mentioned < datetime('now', ?)
        AND last_mentioned > datetime('now', '-60 days')
        AND mention_count >= 2
        ORDER BY mention_count DESC
    """, (f"-{days} days",))

    stale = []
    for row in cursor.fetchall():
        stale.append({
            "type": "person",
            "name": row[0],
            "last_mentioned": row[1],
            "context": row[2],
            "mention_count": row[3]
        })

    conn.close()
    return stale


def detect_incomplete_tasks_patterns() -> Dict[str, Any]:
    """
    Analyze patterns in task completion/incompletion.
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Tasks that have been pending the longest
    cursor.execute("""
        SELECT id, content, created_at, due_date, project_id
        FROM tasks
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT 10
    """)

    oldest_pending = []
    for row in cursor.fetchall():
        days_pending = (datetime.now() - datetime.fromisoformat(row[2])).days if row[2] else 0
        oldest_pending.append({
            "id": row[0],
            "content": row[1],
            "created_at": row[2],
            "days_pending": days_pending,
            "due_date": row[3],
            "project_id": row[4]
        })

    # Completion rate
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'done'")
    completed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tasks")
    total = cursor.fetchone()[0]

    conn.close()

    return {
        "oldest_pending": oldest_pending,
        "completion_rate": completed / total if total > 0 else 0,
        "total_tasks": total,
        "completed_tasks": completed
    }


def save_pattern(pattern_type: str, data: Dict, significance: str = "medium"):
    """Save a detected pattern for future reference."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO patterns (pattern_type, data, significance, detected_at)
        VALUES (?, ?, ?, ?)
    """, (
        pattern_type,
        json.dumps(data),
        significance,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


# ============================================================================
# Data Layer Functions (Agentic Pattern)
# These return raw pattern detections. Claude interprets and suggests.
# ============================================================================

def get_pattern_data() -> Dict[str, Any]:
    """
    Return all pattern detection data. Claude generates suggestions.

    This is the agentic pattern: PCP detects patterns, Claude interprets.

    Returns:
        Dict with pattern detections (no suggestion generation)
    """
    return {
        "repeated_topics": detect_repeated_topics(threshold=3, days=7),
        "repeated_people": detect_repeated_people(threshold=3, days=7),
        "time_patterns": detect_time_patterns(),
        "stale_mentions": detect_stale_mentions(days=14),
        "task_patterns": detect_incomplete_tasks_patterns(),
        "generated_at": datetime.now().isoformat()
    }


def generate_suggestions(patterns: Dict) -> List[str]:
    """DEPRECATED: Generate actionable suggestions from detected patterns.

    Use get_pattern_data() instead - Claude generates suggestions in conversation.
    """
    suggestions = []

    # Repeated topics suggest need for action
    if patterns.get("repeated_topics"):
        for topic in patterns["repeated_topics"][:3]:
            if topic["count"] >= 5:
                suggestions.append(
                    f"'{topic['topic']}' has been mentioned {topic['count']} times. "
                    f"Consider creating a task or decision about it."
                )

    # Stale mentions suggest follow-up
    if patterns.get("stale_mentions"):
        for item in patterns["stale_mentions"][:3]:
            suggestions.append(
                f"Haven't mentioned {item['name']} in a while (last: {item['last_mentioned'][:10]}). "
                f"Need to follow up?"
            )

    # Old pending tasks
    if patterns.get("task_patterns", {}).get("oldest_pending"):
        old_tasks = [t for t in patterns["task_patterns"]["oldest_pending"] if t["days_pending"] > 7]
        for task in old_tasks[:2]:
            suggestions.append(
                f"Task '{task['content'][:50]}...' has been pending for {task['days_pending']} days. "
                f"Still relevant?"
            )

    return suggestions


def generate_task_suggestions(save: bool = True) -> List[Dict]:
    """
    Generate task suggestions from detected patterns and optionally save to suggested_tasks table.

    Returns list of generated suggestions with:
    - content: The suggested task content
    - reason: Why this was suggested
    - source_pattern: Which pattern type generated it
    - id: The database ID if saved (None if not saved)
    """
    suggestions = []

    # 1. Suggestions from repeated topics
    repeated_topics = detect_repeated_topics(threshold=3, days=7)
    for topic in repeated_topics:
        if topic["count"] >= 5:
            suggestion = {
                "content": f"Review and organize notes about '{topic['topic']}'",
                "reason": f"'{topic['topic']}' mentioned {topic['count']} times in the last 7 days - may need structured attention",
                "source_pattern": "repeated_topic",
                "id": None
            }
            suggestions.append(suggestion)
        elif topic["count"] >= 3:
            suggestion = {
                "content": f"Consider creating a task or decision about '{topic['topic']}'",
                "reason": f"'{topic['topic']}' mentioned {topic['count']} times recently",
                "source_pattern": "repeated_topic",
                "id": None
            }
            suggestions.append(suggestion)

    # 2. Suggestions from stale mentions (people not followed up with)
    stale = detect_stale_mentions(days=14)
    for item in stale[:5]:  # Limit to top 5 stale items
        suggestion = {
            "content": f"Follow up with {item['name']}",
            "reason": f"Last mentioned on {item['last_mentioned'][:10]} ({item['mention_count']} mentions total) - may need follow-up",
            "source_pattern": "stale_mention",
            "id": None
        }
        suggestions.append(suggestion)

    # 3. Suggestions from old pending tasks (review/archive old items)
    task_patterns = detect_incomplete_tasks_patterns()
    for task in task_patterns.get("oldest_pending", []):
        if task["days_pending"] > 14:
            suggestion = {
                "content": f"Review old task: '{task['content'][:50]}...' - still relevant?",
                "reason": f"Task has been pending for {task['days_pending']} days - consider completing, delegating, or archiving",
                "source_pattern": "old_pending_task",
                "id": None
            }
            suggestions.append(suggestion)

    # 4. Suggestions from repeated people (relationships needing attention)
    repeated_people = detect_repeated_people(threshold=5, days=7)
    for person in repeated_people[:3]:  # Top 3 most mentioned
        suggestion = {
            "content": f"Schedule dedicated time with {person['name']}",
            "reason": f"{person['name']} mentioned {person['mention_count']} times recently - may warrant dedicated attention",
            "source_pattern": "repeated_person",
            "id": None
        }
        suggestions.append(suggestion)

    # Save to database if requested
    if save and suggestions:
        conn = sqlite3.connect(VAULT_PATH)
        cursor = conn.cursor()

        for suggestion in suggestions:
            # Check if similar suggestion already exists (avoid duplicates)
            cursor.execute("""
                SELECT id FROM suggested_tasks
                WHERE content = ? AND status = 'pending'
            """, (suggestion["content"],))

            if cursor.fetchone():
                # Skip duplicate
                continue

            cursor.execute("""
                INSERT INTO suggested_tasks (content, reason, source_pattern, status, created_at)
                VALUES (?, ?, ?, 'pending', ?)
            """, (
                suggestion["content"],
                suggestion["reason"],
                suggestion["source_pattern"],
                datetime.now().isoformat()
            ))
            suggestion["id"] = cursor.lastrowid

        conn.commit()
        conn.close()

    return suggestions


def get_suggested_tasks(status: str = "pending", limit: int = 20) -> List[Dict]:
    """Get suggested tasks from the database."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, content, reason, source_pattern, status, created_at
        FROM suggested_tasks
        WHERE status = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (status, limit))

    results = []
    for row in cursor.fetchall():
        results.append({
            "id": row["id"],
            "content": row["content"],
            "reason": row["reason"],
            "source_pattern": row["source_pattern"],
            "status": row["status"],
            "created_at": row["created_at"]
        })

    conn.close()
    return results


def run_full_analysis() -> Dict[str, Any]:
    """Run complete pattern analysis."""
    analysis = {
        "generated_at": datetime.now().isoformat(),
        "repeated_topics": detect_repeated_topics(),
        "repeated_people": detect_repeated_people(),
        "time_patterns": detect_time_patterns(),
        "stale_mentions": detect_stale_mentions(),
        "task_patterns": detect_incomplete_tasks_patterns()
    }

    analysis["suggestions"] = generate_suggestions(analysis)

    return analysis


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PCP Pattern Detection - Analyze patterns and generate task suggestions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python patterns.py                  # Run full analysis
  python patterns.py --json           # Output as JSON
  python patterns.py --suggest-tasks  # Generate and save task suggestions
  python patterns.py --list-suggested # List pending suggested tasks
        """
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--suggest-tasks", action="store_true",
                       help="Generate task suggestions from patterns and save to database")
    parser.add_argument("--list-suggested", action="store_true",
                       help="List pending suggested tasks")
    parser.add_argument("--no-save", action="store_true",
                       help="With --suggest-tasks: don't save to database, just show suggestions")

    args = parser.parse_args()

    if args.suggest_tasks:
        # Generate task suggestions
        suggestions = generate_task_suggestions(save=not args.no_save)

        if args.json:
            print(json.dumps(suggestions, indent=2))
        else:
            print("# Generated Task Suggestions\n")
            if suggestions:
                saved_count = sum(1 for s in suggestions if s.get("id"))
                if not args.no_save:
                    print(f"Generated {len(suggestions)} suggestions ({saved_count} new, {len(suggestions) - saved_count} duplicates skipped)\n")
                else:
                    print(f"Generated {len(suggestions)} suggestions (not saved)\n")

                for s in suggestions:
                    status = f"[{s['id']}]" if s.get("id") else "[dup]"
                    print(f"  {status} {s['content']}")
                    print(f"        Reason: {s['reason']}")
                    print(f"        Pattern: {s['source_pattern']}")
                    print()
            else:
                print("No suggestions generated - not enough pattern data")

    elif args.list_suggested:
        # List existing suggested tasks
        suggestions = get_suggested_tasks(status="pending")

        if args.json:
            print(json.dumps(suggestions, indent=2))
        else:
            print("# Pending Suggested Tasks\n")
            if suggestions:
                for s in suggestions:
                    print(f"  [{s['id']}] {s['content']}")
                    print(f"        Reason: {s['reason']}")
                    print(f"        Created: {s['created_at'][:10]}")
                    print()
            else:
                print("No pending suggested tasks")

    elif args.json:
        analysis = run_full_analysis()
        print(json.dumps(analysis, indent=2))

    else:
        # Default: run full analysis
        analysis = run_full_analysis()

        print("# PCP Pattern Analysis\n")

        if analysis["repeated_topics"]:
            print("## Repeated Topics")
            for topic in analysis["repeated_topics"][:5]:
                print(f"  - {topic['topic']}: {topic['count']} mentions")
            print()

        if analysis["repeated_people"]:
            print("## Frequently Mentioned People")
            for person in analysis["repeated_people"][:5]:
                print(f"  - {person['name']}: {person['mention_count']} mentions")
            print()

        if analysis["time_patterns"]["peak_hours"]:
            hours = [f"{h}:00" for h in analysis["time_patterns"]["peak_hours"]]
            print(f"## Peak Activity Hours: {', '.join(hours)}")
            print()

        if analysis["stale_mentions"]:
            print("## May Need Follow-up")
            for item in analysis["stale_mentions"][:3]:
                print(f"  - {item['name']} (last: {item['last_mentioned'][:10]})")
            print()

        if analysis["suggestions"]:
            print("## Suggestions")
            for suggestion in analysis["suggestions"]:
                print(f"  - {suggestion}")
