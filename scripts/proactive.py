#!/usr/bin/env python3
"""
Proactive Intelligence Module - Surfaces insights without being asked.

This module makes PCP feel "alive" by proactively:
- Detecting repeated topics (potential patterns)
- Surfacing upcoming deadlines
- Suggesting task creation for repeated items
- Identifying attention items
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter

# Database path
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)):
    VAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "vault", "vault.db")


def get_repeated_topics(days: int = 7, threshold: int = 3) -> List[Dict[str, Any]]:
    """
    Find topics that have been mentioned repeatedly in recent captures.

    Repeated mentions might indicate:
    - Something important that needs attention
    - An emerging pattern
    - A topic worth creating a task for

    Args:
        days: Number of days to look back
        threshold: Minimum mentions to be considered "repeated"

    Returns:
        List of repeated topics with count and sample captures
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    since_date = (datetime.now() - timedelta(days=days)).isoformat()

    # Get recent captures with their extracted topics
    cursor.execute("""
        SELECT id, content, extracted_entities, created_at
        FROM captures_v2
        WHERE created_at >= ?
        ORDER BY created_at DESC
    """, (since_date,))

    # Count topic occurrences
    topic_counts = Counter()
    topic_captures = {}  # topic -> list of capture ids

    for row in cursor.fetchall():
        entities = json.loads(row['extracted_entities']) if row['extracted_entities'] else {}
        topics = entities.get('topics', []) + entities.get('projects', [])

        for topic in topics:
            topic_lower = topic.lower().strip()
            if topic_lower:
                topic_counts[topic_lower] += 1
                if topic_lower not in topic_captures:
                    topic_captures[topic_lower] = []
                topic_captures[topic_lower].append({
                    'id': row['id'],
                    'preview': row['content'][:100] if row['content'] else ''
                })

    conn.close()

    # Filter to repeated topics
    repeated = []
    for topic, count in topic_counts.most_common():
        if count >= threshold:
            repeated.append({
                'topic': topic,
                'count': count,
                'period_days': days,
                'sample_captures': topic_captures[topic][:3]  # Top 3 samples
            })

    return repeated


def get_upcoming_deadlines(days: int = 3) -> List[Dict[str, Any]]:
    """
    Get tasks with deadlines in the next N days.

    Args:
        days: Number of days to look ahead

    Returns:
        List of items with upcoming deadlines
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    today = datetime.now().date()
    future_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    upcoming = []

    # Get tasks with due dates
    cursor.execute("""
        SELECT id, content, due_date, priority, status
        FROM tasks
        WHERE due_date IS NOT NULL
        AND due_date <= ?
        AND status = 'pending'
        ORDER BY due_date ASC
    """, (future_date,))

    for row in cursor.fetchall():
        due_date = datetime.strptime(row['due_date'], "%Y-%m-%d").date()
        days_left = (due_date - today).days

        upcoming.append({
            'type': 'task',
            'id': row['id'],
            'content': row['content'],
            'due_date': row['due_date'],
            'days_left': days_left,
            'priority': row['priority'],
            'is_overdue': days_left < 0
        })

    conn.close()

    # Sort by days_left (most urgent first)
    upcoming.sort(key=lambda x: x['days_left'])

    return upcoming


def get_stale_relationships(days: int = 14) -> List[Dict[str, Any]]:
    """
    Find people who haven't been contacted recently.

    Args:
        days: Days since last contact to be considered "stale"

    Returns:
        List of people needing attention
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    stale_date = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT id, name, organization, relationship, last_contacted, interaction_count
        FROM people
        WHERE last_contacted IS NOT NULL
        AND last_contacted <= ?
        ORDER BY last_contacted ASC
        LIMIT 10
    """, (stale_date,))

    stale = []
    for row in cursor.fetchall():
        last_contact = datetime.fromisoformat(row['last_contacted'].replace('Z', '+00:00'))
        days_since = (datetime.now() - last_contact.replace(tzinfo=None)).days

        stale.append({
            'id': row['id'],
            'name': row['name'],
            'organization': row['organization'],
            'relationship': row['relationship'],
            'days_since_contact': days_since,
            'interaction_count': row['interaction_count']
        })

    conn.close()
    return stale


def get_attention_items() -> Dict[str, Any]:
    """
    Get a summary of items needing attention.

    Returns:
        Dict with counts and top items for each category
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    # Overdue tasks
    cursor.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE status = 'pending' AND due_date < ?
    """, (today,))
    overdue_tasks = cursor.fetchone()[0]

    # Due today
    cursor.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE status = 'pending' AND due_date = ?
    """, (today,))
    due_today = cursor.fetchone()[0]

    conn.close()

    return {
        'overdue_tasks': overdue_tasks,
        'due_today': due_today,
        'needs_attention': overdue_tasks + due_today > 0
    }


# ============================================================================
# Data Layer Functions (Agentic Pattern)
# These return raw data. Claude generates insights in conversation.
# ============================================================================

def get_proactive_data() -> Dict[str, Any]:
    """
    Return all proactive detection data. Claude generates insights.

    This is the agentic pattern: PCP detects patterns, Claude interprets.

    Returns:
        Dict with detection results (no insight generation, no formatting)
    """
    return {
        "repeated_topics": get_repeated_topics(days=7, threshold=3),
        "upcoming_deadlines": get_upcoming_deadlines(days=3),
        "stale_relationships": get_stale_relationships(days=14),
        "attention_items": get_attention_items(),
        "generated_at": datetime.now().isoformat()
    }


def get_proactive_insights(context: Optional[Dict] = None) -> List[str]:
    """
    DEPRECATED: Generate proactive insights based on current state.

    This is the main entry point for proactive intelligence.
    Call this after captures to surface relevant insights.

    Args:
        context: Optional context dict with current capture info

    Returns:
        List of natural language insight strings
    """
    insights = []

    # Check for repeated topics
    repeated = get_repeated_topics(days=7, threshold=3)
    for topic in repeated[:2]:  # Top 2 repeated topics
        insights.append(
            f"You've mentioned '{topic['topic']}' {topic['count']} times this week - "
            f"might be worth creating a task or project for it."
        )

    # Check upcoming deadlines
    upcoming = get_upcoming_deadlines(days=3)
    overdue = [u for u in upcoming if u['is_overdue']]
    due_soon = [u for u in upcoming if not u['is_overdue']]

    if overdue:
        for item in overdue[:2]:
            item_type = item['type']
            days_overdue = abs(item['days_left'])
            insights.append(
                f"Overdue {item_type}: \"{item['content'][:50]}...\" "
                f"({days_overdue} day{'s' if days_overdue > 1 else ''} past due)"
            )

    if due_soon:
        for item in due_soon[:2]:
            item_type = item['type']
            if item['days_left'] == 0:
                insights.append(f"Due today: \"{item['content'][:50]}...\"")
            else:
                insights.append(
                    f"{item_type.capitalize()} in {item['days_left']} day{'s' if item['days_left'] > 1 else ''}: "
                    f"\"{item['content'][:50]}...\""
                )

    # Check if context mentions a topic we've seen before
    if context and context.get('entities'):
        entities = context['entities']
        topics = entities.get('topics', []) + entities.get('projects', [])

        repeated_lookup = {r['topic']: r['count'] for r in repeated}
        for topic in topics:
            topic_lower = topic.lower().strip()
            if topic_lower in repeated_lookup and repeated_lookup[topic_lower] >= 3:
                # Already added above, skip
                pass

    return insights


def format_insights_for_response(insights: List[str]) -> str:
    """
    Format insights for inclusion in a capture response.

    Args:
        insights: List of insight strings

    Returns:
        Formatted string for display
    """
    if not insights:
        return ""

    if len(insights) == 1:
        return f"\n\nBy the way: {insights[0]}"

    formatted = "\n\nBy the way:"
    for insight in insights:
        formatted += f"\n- {insight}"

    return formatted


def get_daily_proactive_summary() -> Dict[str, Any]:
    """
    Get a comprehensive proactive summary for daily briefs.

    Returns:
        Dict with all proactive intelligence data
    """
    return {
        'attention_items': get_attention_items(),
        'upcoming_deadlines': get_upcoming_deadlines(days=7),
        'repeated_topics': get_repeated_topics(days=7, threshold=3),
        'stale_relationships': get_stale_relationships(days=14),
        'generated_at': datetime.now().isoformat()
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python proactive.py insights         - Get proactive insights")
        print("  python proactive.py repeated [days]  - Find repeated topics")
        print("  python proactive.py deadlines [days] - Get upcoming deadlines")
        print("  python proactive.py attention        - Get attention items summary")
        print("  python proactive.py summary          - Full daily summary")
        sys.exit(1)

    command = sys.argv[1]

    if command == "insights":
        insights = get_proactive_insights()
        if insights:
            print("Proactive Insights:")
            for i, insight in enumerate(insights, 1):
                print(f"  {i}. {insight}")
        else:
            print("No proactive insights at this time.")

    elif command == "repeated":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        repeated = get_repeated_topics(days=days)
        if repeated:
            print(f"Repeated topics (last {days} days):")
            for r in repeated:
                print(f"  - {r['topic']}: {r['count']} times")
        else:
            print(f"No repeated topics found in the last {days} days.")

    elif command == "deadlines":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        upcoming = get_upcoming_deadlines(days=days)
        if upcoming:
            print(f"Upcoming deadlines (next {days} days):")
            for u in upcoming:
                status = "OVERDUE" if u['is_overdue'] else f"in {u['days_left']}d"
                print(f"  [{u['type']}] {status}: {u['content'][:60]}")
        else:
            print(f"No deadlines in the next {days} days.")

    elif command == "attention":
        items = get_attention_items()
        print("Attention Items:")
        print(f"  Overdue tasks: {items['overdue_tasks']}")
        print(f"  Due today: {items['due_today']}")
        print(f"  Needs attention: {'Yes' if items['needs_attention'] else 'No'}")

    elif command == "summary":
        summary = get_daily_proactive_summary()
        print(json.dumps(summary, indent=2, default=str))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
