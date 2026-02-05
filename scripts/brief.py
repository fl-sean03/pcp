#!/usr/bin/env python3
"""
PCP Smart Brief Engine - Generates intelligent daily briefs and summaries.
Analyzes patterns, pending tasks, recent activity, and provides actionable insights.
"""

import sqlite3
import json
import subprocess
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger("pcp.brief")

# Import relationship and project functions
from vault_v2 import get_stale_relationships, get_stalled_projects

# Import email functions
from email_processor import get_actionable_emails

# Import knowledge functions
from knowledge import list_knowledge

# Import additional vault functions for meeting prep
from vault_v2 import get_person, get_relationship_summary, unified_search

# Import Twitter intelligence (optional - fails gracefully if not available)
try:
    import sys
    sys.path.insert(0, '/workspace/scripts')
    from pcp_integration import get_twitter_brief_section, get_twitter_stats, has_urgent_twitter_activity
    TWITTER_AVAILABLE = True
except ImportError:
    TWITTER_AVAILABLE = False

# Import system queries (optional - for system status in briefs)
try:
    from system_queries import get_system_overview, list_running_containers
    SYSTEM_QUERIES_AVAILABLE = True
except ImportError:
    SYSTEM_QUERIES_AVAILABLE = False

VAULT_PATH = "/workspace/vault/vault.db"

# Local development fallback
if not os.path.exists(os.path.dirname(VAULT_PATH)):
    VAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "vault", "vault.db")


def get_recent_captures(hours: int = 24) -> List[Dict]:
    """Get captures from the last N hours."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, content, capture_type, extracted_entities, created_at
        FROM captures_v2
        WHERE created_at > datetime('now', ?)
        ORDER BY created_at DESC
    """, (f"-{hours} hours",))

    captures = []
    for row in cursor.fetchall():
        entities = {}
        try:
            entities = json.loads(row[3]) if row[3] else {}
        except:
            pass

        captures.append({
            "id": row[0],
            "content": row[1],
            "type": row[2],
            "entities": entities,
            "created_at": row[4]
        })

    conn.close()
    return captures


def get_pending_tasks() -> List[Dict]:
    """Get all pending tasks."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, content, priority, due_date, reminder_at, project_id, created_at
        FROM tasks
        WHERE status = 'pending'
        ORDER BY
            CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
            due_date ASC,
            priority DESC
    """)

    tasks = []
    for row in cursor.fetchall():
        tasks.append({
            "id": row[0],
            "content": row[1],
            "priority": row[2],
            "due_date": row[3],
            "reminder_at": row[4],
            "project_id": row[5],
            "created_at": row[6]
        })

    conn.close()
    return tasks


def get_overdue_tasks() -> List[Dict]:
    """Get tasks that are overdue."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT id, content, priority, due_date, project_id
        FROM tasks
        WHERE status = 'pending' AND due_date < ?
        ORDER BY due_date ASC
    """, (today,))

    tasks = []
    for row in cursor.fetchall():
        tasks.append({
            "id": row[0],
            "content": row[1],
            "priority": row[2],
            "due_date": row[3],
            "project_id": row[4]
        })

    conn.close()
    return tasks


def get_upcoming_deadlines(days: int = 7) -> List[Dict]:
    """Get tasks with deadlines in the next N days."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT id, content, due_date, project_id
        FROM tasks
        WHERE status = 'pending'
        AND due_date >= ? AND due_date <= ?
        ORDER BY due_date ASC
    """, (today, future))

    tasks = []
    for row in cursor.fetchall():
        tasks.append({
            "id": row[0],
            "content": row[1],
            "due_date": row[2],
            "project_id": row[3]
        })

    conn.close()
    return tasks


def get_recent_people_mentions() -> List[Dict]:
    """Get people mentioned recently."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, relationship, mention_count, last_mentioned, context
        FROM people
        WHERE last_mentioned > datetime('now', '-7 days')
        ORDER BY last_mentioned DESC
        LIMIT 10
    """)

    people = []
    for row in cursor.fetchall():
        people.append({
            "id": row[0],
            "name": row[1],
            "relationship": row[2],
            "mention_count": row[3],
            "last_mentioned": row[4],
            "context": row[5]
        })

    conn.close()
    return people


def get_project_activity() -> List[Dict]:
    """Get recent activity by project."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id, p.name, p.status,
               COUNT(DISTINCT c.id) as capture_count,
               COUNT(DISTINCT t.id) as task_count
        FROM projects p
        LEFT JOIN captures_v2 c ON c.linked_projects LIKE '%' || p.id || '%'
            AND c.created_at > datetime('now', '-7 days')
        LEFT JOIN tasks t ON t.project_id = p.id AND t.status = 'pending'
        WHERE p.status = 'active'
        GROUP BY p.id
        ORDER BY capture_count DESC
    """)

    projects = []
    for row in cursor.fetchall():
        projects.append({
            "id": row[0],
            "name": row[1],
            "status": row[2],
            "recent_captures": row[3],
            "pending_tasks": row[4]
        })

    conn.close()
    return projects


def get_stale_relationships_summary(days: int = 14) -> Dict[str, Any]:
    """Get stale relationships data for the brief."""
    stale = get_stale_relationships(days=days)

    return {
        "stale_count": len(stale),
        "stale": [
            {
                "id": p["id"],
                "name": p["name"],
                "relationship": p.get("relationship"),
                "organization": p.get("organization"),
                "last_contacted": p.get("last_contacted"),
                "days_since_contact": p.get("days_since_contact"),
                "status": p.get("status")
            }
            for p in stale[:10]  # Limit to 10 for brief
        ]
    }


def get_stalled_projects_summary(days: int = 14) -> Dict[str, Any]:
    """Get stalled projects data for the brief."""
    stalled = get_stalled_projects(days=days)

    return {
        "stalled_count": len(stalled),
        "stalled": [
            {
                "id": p["id"],
                "name": p["name"],
                "status": p.get("status"),
                "days_since_activity": p.get("days_since_activity"),
                "pending_tasks": p.get("pending_tasks", 0)
            }
            for p in stalled[:10]  # Limit to 10 for brief
        ]
    }


def get_actionable_emails_summary() -> Dict[str, Any]:
    """Get actionable emails data for the brief."""
    try:
        emails = get_actionable_emails(include_actioned=False)
    except Exception:
        # Graph API not configured or other error
        emails = []

    return {
        "actionable_count": len(emails),
        "emails": [
            {
                "id": e["id"],
                "subject": e.get("subject", "")[:80],
                "sender": e.get("sender", ""),
                "received_at": e.get("received_at"),
                "body_preview": e.get("body_preview", "")[:100]
            }
            for e in emails[:10]  # Limit to 10 for brief
        ]
    }


def get_recent_knowledge_summary(days: int = 7) -> Dict[str, Any]:
    """Get recently added knowledge for the brief."""
    try:
        # Get recent knowledge entries (all categories)
        all_knowledge = list_knowledge(limit=100)

        # Filter to last N days
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent = [
            k for k in all_knowledge
            if k.get("created_at", "") >= cutoff
        ]
    except Exception:
        recent = []

    return {
        "recent_count": len(recent),
        "recent": [
            {
                "id": k["id"],
                "content": k["content"][:100] if k.get("content") else "",
                "category": k.get("category"),
                "created_at": k.get("created_at")
            }
            for k in recent[:10]  # Limit to 10 for brief
        ]
    }


def get_twitter_intelligence_summary() -> Dict[str, Any]:
    """Get Twitter intelligence for the brief."""
    if not TWITTER_AVAILABLE:
        return {"available": False}

    try:
        stats = get_twitter_stats()
        return {
            "available": True,
            "drafts_ready": stats.get("drafts_ready", 0),
            "high_value_count": stats.get("high_value_count", 0),
            "posts_monitored": stats.get("posts_monitored", 0),
            "summary": stats.get("summary", ""),
            "stale": stats.get("stale", True),
            "has_urgent": has_urgent_twitter_activity()
        }
    except Exception:
        return {"available": False}


def get_system_status_summary() -> Dict[str, Any]:
    """Get system/container status for the brief."""
    if not SYSTEM_QUERIES_AVAILABLE:
        return {"available": False}

    try:
        overview = get_system_overview()
        containers = list_running_containers()

        # Build summary
        running_count = len(containers)
        container_list = []

        for c in containers[:10]:  # Limit to 10 for brief
            container_list.append({
                "name": c.get("name", "unknown"),
                "status": c.get("status", "unknown"),
                "image": c.get("image", "").split(":")[0] if c.get("image") else ""
            })

        return {
            "available": True,
            "running_count": running_count,
            "containers": container_list,
            "overview": overview
        }
    except Exception:
        return {"available": False}


def get_stats_comparison() -> Dict:
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Last 24 hours
    cursor.execute("""
        SELECT COUNT(*) FROM captures_v2
        WHERE created_at > datetime('now', '-24 hours')
    """)
    last_24h = cursor.fetchone()[0]

    # Previous 24 hours
    cursor.execute("""
        SELECT COUNT(*) FROM captures_v2
        WHERE created_at > datetime('now', '-48 hours')
        AND created_at <= datetime('now', '-24 hours')
    """)
    prev_24h = cursor.fetchone()[0]

    # Tasks completed recently
    cursor.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE completed_at > datetime('now', '-24 hours')
    """)
    tasks_completed = cursor.fetchone()[0]

    conn.close()

    return {
        "captures_24h": last_24h,
        "captures_prev_24h": prev_24h,
        "capture_trend": "up" if last_24h > prev_24h else "down" if last_24h < prev_24h else "same",
        "tasks_completed_24h": tasks_completed
    }


# ============================================================================
# Data Layer Functions (Agentic Pattern)
# These return raw data. Claude formats and adds insights in conversation.
# ============================================================================

def get_brief_data(days: int = 7) -> Dict[str, Any]:
    """
    Return all data needed for brief generation. Claude formats and adds insights.

    This is the agentic pattern: PCP provides raw data, Claude provides intelligence.

    Args:
        days: How many days of history to include

    Returns:
        Dict with all brief data sections (no formatting, no insights)
    """
    return {
        "generated_at": datetime.now().isoformat(),
        "captures": get_recent_captures(hours=days * 24),
        "tasks": {
            "pending": get_pending_tasks(),
            "overdue": get_overdue_tasks(),
            "upcoming": get_upcoming_deadlines(days=days)
        },
        "people": get_recent_people_mentions(),
        "projects": get_project_activity(),
        "stale_relationships": get_stale_relationships_summary(days=14),
        "stalled_projects": get_stalled_projects_summary(days=14),
        "emails": get_actionable_emails_summary(),
        "knowledge": get_recent_knowledge_summary(days=days),
        "twitter": get_twitter_intelligence_summary(),
        "system": get_system_status_summary(),
        "stats": get_stats_comparison()
    }


def generate_brief(brief_type: str = "daily") -> Dict[str, Any]:
    """
    DEPRECATED: Generate a comprehensive brief.

    Use get_brief_data() instead - it returns raw data that Claude formats.
    This function still works for backwards compatibility.

    Types:
    - daily: Full daily brief
    - quick: Quick status check
    - focused: Focus on specific project or topic
    """
    brief = {
        "generated_at": datetime.now().isoformat(),
        "type": brief_type
    }

    # Recent activity
    recent = get_recent_captures(24 if brief_type == "daily" else 12)
    brief["recent_activity"] = {
        "count": len(recent),
        "items": [{"content": c["content"][:100], "type": c["type"]} for c in recent[:10]]
    }

    # Pending tasks
    pending = get_pending_tasks()
    overdue = get_overdue_tasks()
    upcoming = get_upcoming_deadlines(3 if brief_type == "quick" else 7)

    brief["tasks"] = {
        "pending_count": len(pending),
        "overdue_count": len(overdue),
        "overdue": [{"content": t["content"], "due": t["due_date"]} for t in overdue],
        "upcoming_deadlines": [{"content": t["content"], "due": t["due_date"]} for t in upcoming]
    }

    # People activity
    people = get_recent_people_mentions()
    brief["people"] = {
        "recently_mentioned": [{"name": p["name"], "count": p["mention_count"]} for p in people[:5]]
    }

    # Stale relationships (not contacted in 14+ days)
    brief["stale_relationships"] = get_stale_relationships_summary(days=14)

    # Project status
    projects = get_project_activity()
    brief["projects"] = [
        {"name": p["name"], "captures": p["recent_captures"], "tasks": p["pending_tasks"]}
        for p in projects if p["recent_captures"] > 0 or p["pending_tasks"] > 0
    ]

    # Stalled projects (no activity in 14+ days)
    brief["stalled_projects"] = get_stalled_projects_summary(days=14)

    # Actionable emails
    brief["actionable_emails"] = get_actionable_emails_summary()

    # Recently added knowledge
    brief["recent_knowledge"] = get_recent_knowledge_summary(days=7)

    # Twitter intelligence (if available)
    brief["twitter"] = get_twitter_intelligence_summary()

    # System status (if available)
    brief["system_status"] = get_system_status_summary()

    # Stats comparison
    brief["stats"] = get_stats_comparison()

    return brief


def format_brief_text(brief: Dict) -> str:
    """Format brief as conversational, friendly text for Discord."""
    lines = []

    # Greeting based on time of day
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    day_name = datetime.now().strftime('%A')
    lines.append(f"{greeting}! Here's your {day_name} rundown:")
    lines.append("")

    # Count urgent items
    overdue_tasks = brief["tasks"]["overdue_count"]

    # Urgent section - only if there are overdue items
    if overdue_tasks > 0:
        lines.append(f"**Needs attention** ({overdue_tasks} overdue)")
        for task in brief["tasks"]["overdue"][:5]:  # Limit to 5
            lines.append(f"• {task['content']}")
        lines.append("")

    # Coming up soon
    upcoming_tasks = brief["tasks"].get("upcoming_deadlines", [])

    if upcoming_tasks:
        lines.append("**Coming up**")
        for task in upcoming_tasks[:3]:
            lines.append(f"• {task['content']} (due {task['due']})")
        lines.append("")

    # Quick stats - one line summary
    pending = brief['tasks']['pending_count']
    completed = brief['stats']['tasks_completed_24h']
    captures = brief['recent_activity']['count']

    stats_parts = []
    if pending > 0:
        stats_parts.append(f"{pending} tasks pending")
    if completed > 0:
        stats_parts.append(f"{completed} completed yesterday")
    if captures > 0:
        stats_parts.append(f"{captures} new captures")

    if stats_parts:
        lines.append(f"**Quick stats**: {', '.join(stats_parts)}")
        lines.append("")

    # People worth reaching out to (stale relationships) - more conversational
    stale = brief.get("stale_relationships", {}).get("stale", [])
    if stale:
        # Filter to just 3 most relevant
        stale_names = [p["name"] for p in stale[:3]]
        if len(stale_names) == 1:
            lines.append(f"**Consider reaching out to** {stale_names[0]} - been a while since you connected.")
        elif stale_names:
            names_str = ", ".join(stale_names[:-1]) + f" or {stale_names[-1]}"
            lines.append(f"**Maybe reconnect with** {names_str}?")
        lines.append("")

    # Actionable emails - brief mention
    emails = brief.get("actionable_emails", {})
    if emails.get("actionable_count", 0) > 0:
        count = emails["actionable_count"]
        if count == 1:
            email = emails["emails"][0]
            lines.append(f"**Email needs response**: {email.get('subject', 'No subject')} from {email.get('sender', 'Unknown')}")
        else:
            lines.append(f"**{count} emails** need your attention")
        lines.append("")

    # Twitter - casual mention if relevant
    twitter = brief.get("twitter", {})
    if twitter.get("available") and (twitter.get("drafts_ready", 0) > 0 or twitter.get("high_value_count", 0) > 0):
        parts = []
        if twitter.get("drafts_ready", 0) > 0:
            parts.append(f"{twitter['drafts_ready']} drafts ready to post")
        if twitter.get("high_value_count", 0) > 0:
            parts.append(f"{twitter['high_value_count']} engagement opportunities")
        lines.append(f"**Twitter**: {', '.join(parts)}")
        lines.append("")

    # System health - only mention if something notable
    system = brief.get("system_status", {})
    if system.get("available"):
        running = system.get("running_count", 0)
        if running > 0:
            # Check for any unhealthy containers
            unhealthy = [c for c in system.get("containers", []) if "unhealthy" in c.get("status", "").lower()]
            if unhealthy:
                lines.append(f"**Heads up**: {len(unhealthy)} container(s) unhealthy")
            else:
                lines.append(f"**Systems**: {running} containers running, all good")
            lines.append("")

    # Sign off
    if overdue_tasks > 0:
        lines.append("Let me know if you want to tackle any of those overdue items!")
    elif pending > 5:
        lines.append("Busy day ahead - let me know how I can help!")
    else:
        lines.append("Looking manageable today. What would you like to focus on?")

    return "\n".join(lines)


def get_week_stats() -> Dict[str, Any]:
    """Get statistics for the past week."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Captures this week
    cursor.execute("""
        SELECT COUNT(*) as count FROM captures_v2
        WHERE created_at > datetime('now', '-7 days')
    """)
    captures_week = cursor.fetchone()["count"]

    # Captures by type this week
    cursor.execute("""
        SELECT capture_type, COUNT(*) as count FROM captures_v2
        WHERE created_at > datetime('now', '-7 days')
        GROUP BY capture_type
    """)
    captures_by_type = {row["capture_type"]: row["count"] for row in cursor.fetchall()}

    # Tasks created this week
    cursor.execute("""
        SELECT COUNT(*) as count FROM tasks
        WHERE created_at > datetime('now', '-7 days')
    """)
    tasks_created = cursor.fetchone()["count"]

    # Tasks completed this week
    cursor.execute("""
        SELECT COUNT(*) as count FROM tasks
        WHERE completed_at > datetime('now', '-7 days')
    """)
    tasks_completed = cursor.fetchone()["count"]

    # Tasks still pending
    cursor.execute("""
        SELECT COUNT(*) as count FROM tasks
        WHERE status = 'pending'
    """)
    tasks_pending = cursor.fetchone()["count"]

    # Tasks overdue
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT COUNT(*) as count FROM tasks
        WHERE status = 'pending' AND due_date < ?
    """, (today,))
    tasks_overdue = cursor.fetchone()["count"]

    # People mentioned this week
    cursor.execute("""
        SELECT COUNT(DISTINCT p.id) as count
        FROM people p
        WHERE p.last_mentioned > datetime('now', '-7 days')
    """)
    people_mentioned = cursor.fetchone()["count"]

    # New people added this week
    cursor.execute("""
        SELECT COUNT(*) as count FROM people
        WHERE created_at > datetime('now', '-7 days')
    """)
    people_added = cursor.fetchone()["count"]

    # Knowledge entries added this week
    cursor.execute("""
        SELECT COUNT(*) as count FROM knowledge
        WHERE created_at > datetime('now', '-7 days')
    """)
    knowledge_added = cursor.fetchone()["count"]

    # Knowledge by category this week
    cursor.execute("""
        SELECT category, COUNT(*) as count FROM knowledge
        WHERE created_at > datetime('now', '-7 days')
        GROUP BY category
    """)
    knowledge_by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

    # Projects with activity this week
    cursor.execute("""
        SELECT COUNT(DISTINCT p.id) as count
        FROM projects p
        INNER JOIN captures_v2 c ON c.linked_projects LIKE '%' || p.id || '%'
        WHERE c.created_at > datetime('now', '-7 days')
    """)
    projects_active = cursor.fetchone()["count"]

    conn.close()

    return {
        "captures": {
            "total": captures_week,
            "by_type": captures_by_type
        },
        "tasks": {
            "created": tasks_created,
            "completed": tasks_completed,
            "pending": tasks_pending,
            "overdue": tasks_overdue,
            "completion_rate": round(tasks_completed / max(tasks_created, 1) * 100, 1)
        },
        "people": {
            "mentioned": people_mentioned,
            "added": people_added
        },
        "knowledge": {
            "added": knowledge_added,
            "by_category": knowledge_by_category
        },
        "projects": {
            "active": projects_active
        }
    }


def get_week_highlights() -> Dict[str, Any]:
    """Get notable items from the past week."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Most mentioned people
    cursor.execute("""
        SELECT id, name, mention_count, organization
        FROM people
        WHERE last_mentioned > datetime('now', '-7 days')
        ORDER BY mention_count DESC
        LIMIT 5
    """)
    top_people = [dict(row) for row in cursor.fetchall()]

    # Most active projects
    cursor.execute("""
        SELECT p.id, p.name, COUNT(c.id) as capture_count
        FROM projects p
        INNER JOIN captures_v2 c ON c.linked_projects LIKE '%' || p.id || '%'
        WHERE c.created_at > datetime('now', '-7 days')
        GROUP BY p.id
        ORDER BY capture_count DESC
        LIMIT 5
    """)
    top_projects = [dict(row) for row in cursor.fetchall()]

    # Recent decisions (from captures)
    cursor.execute("""
        SELECT id, content, created_at
        FROM captures_v2
        WHERE capture_type = 'decision'
        AND created_at > datetime('now', '-7 days')
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_decisions = [dict(row) for row in cursor.fetchall()]

    # Completed tasks
    cursor.execute("""
        SELECT id, content, completed_at
        FROM tasks
        WHERE completed_at > datetime('now', '-7 days')
        ORDER BY completed_at DESC
        LIMIT 10
    """)
    completed_tasks = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "top_people": top_people,
        "top_projects": top_projects,
        "recent_decisions": recent_decisions,
        "completed_tasks": completed_tasks
    }


def generate_weekly_summary() -> Dict[str, Any]:
    """Generate a comprehensive weekly summary."""
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = datetime.now().strftime("%Y-%m-%d")

    summary = {
        "generated_at": datetime.now().isoformat(),
        "type": "weekly",
        "period": {
            "start": week_start,
            "end": week_end
        },
        "stats": get_week_stats(),
        "highlights": get_week_highlights(),
        # Include current status for comparison
        "current_status": {
            "overdue_tasks": get_overdue_tasks(),
            "stale_relationships": get_stale_relationships(days=14),
            "stalled_projects": get_stalled_projects(days=14)
        }
    }

    return summary


def format_weekly_text(summary: Dict) -> str:
    """Format weekly summary as human-readable text."""
    lines = []
    lines.append(f"# PCP Weekly Summary")
    lines.append(f"## Week of {summary['period']['start']} to {summary['period']['end']}")
    lines.append("")

    stats = summary["stats"]
    highlights = summary["highlights"]
    current = summary.get("current_status", {})

    # Activity Overview
    lines.append("## Activity Overview")
    lines.append(f"  - Total captures: {stats['captures']['total']}")
    if stats['captures']['by_type']:
        for ctype, count in stats['captures']['by_type'].items():
            lines.append(f"    - {ctype}: {count}")
    lines.append(f"  - People mentioned: {stats['people']['mentioned']}")
    lines.append(f"  - New contacts added: {stats['people']['added']}")
    lines.append(f"  - Projects with activity: {stats['projects']['active']}")
    lines.append("")

    # Task Summary
    lines.append("## Task Summary")
    lines.append(f"  - Tasks created: {stats['tasks']['created']}")
    lines.append(f"  - Tasks completed: {stats['tasks']['completed']}")
    lines.append(f"  - Completion rate: {stats['tasks']['completion_rate']}%")
    lines.append(f"  - Currently pending: {stats['tasks']['pending']}")
    if stats['tasks']['overdue'] > 0:
        lines.append(f"  - OVERDUE: {stats['tasks']['overdue']}")
    lines.append("")

    # Knowledge Summary
    if stats['knowledge']['added'] > 0:
        lines.append("## Knowledge Added")
        lines.append(f"  - Total entries: {stats['knowledge']['added']}")
        if stats['knowledge']['by_category']:
            for cat, count in stats['knowledge']['by_category'].items():
                lines.append(f"    - {cat}: {count}")
        lines.append("")

    # Completed Tasks
    if highlights['completed_tasks']:
        lines.append("## Completed Tasks")
        for task in highlights['completed_tasks'][:5]:
            content = task['content'][:60]
            if len(task['content']) > 60:
                content += "..."
            lines.append(f"  - {content}")
        if len(highlights['completed_tasks']) > 5:
            lines.append(f"  - ... and {len(highlights['completed_tasks']) - 5} more")
        lines.append("")

    # Recent Decisions
    if highlights['recent_decisions']:
        lines.append("## Decisions Made")
        for d in highlights['recent_decisions']:
            content = d['content'][:60]
            if len(d['content']) > 60:
                content += "..."
            lines.append(f"  - {content}")
        lines.append("")

    # Top People
    if highlights['top_people']:
        lines.append("## Most Active Contacts")
        for person in highlights['top_people']:
            org = f" ({person['organization']})" if person.get('organization') else ""
            lines.append(f"  - {person['name']}{org}: {person['mention_count']}x mentions")
        lines.append("")

    # Top Projects
    if highlights['top_projects']:
        lines.append("## Most Active Projects")
        for proj in highlights['top_projects']:
            lines.append(f"  - {proj['name']}: {proj['capture_count']} captures")
        lines.append("")

    # Current Issues (items needing attention)
    overdue_tasks = current.get("overdue_tasks", [])
    stale_relationships = current.get("stale_relationships", [])
    stalled_projects = current.get("stalled_projects", [])

    issues_count = len(overdue_tasks) + len(stale_relationships) + len(stalled_projects)
    if issues_count > 0:
        lines.append("## Attention Needed")
        if overdue_tasks:
            lines.append(f"  - {len(overdue_tasks)} overdue task(s)")
        if stale_relationships:
            lines.append(f"  - {len(stale_relationships)} stale relationship(s) (14+ days)")
        if stalled_projects:
            lines.append(f"  - {len(stalled_projects)} stalled project(s)")
        lines.append("")

    return "\n".join(lines)


def weekly_summary() -> str:
    """Generate the full weekly summary with AI insights."""
    summary = generate_weekly_summary()
    text = format_weekly_text(summary)

    # Add AI insights
    insights = generate_ai_insights(summary)
    if insights:
        text += "\n## AI Insights\n" + insights

    return text


def get_today_activity() -> Dict[str, Any]:
    """Get comprehensive activity from today."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    # Captures today
    cursor.execute("""
        SELECT id, content, capture_type, created_at
        FROM captures_v2
        WHERE date(created_at) = ?
        ORDER BY created_at DESC
    """, (today,))
    captures = [dict(row) for row in cursor.fetchall()]

    # Tasks completed today
    cursor.execute("""
        SELECT id, content, completed_at
        FROM tasks
        WHERE date(completed_at) = ?
        ORDER BY completed_at DESC
    """, (today,))
    tasks_completed = [dict(row) for row in cursor.fetchall()]

    # Tasks created today
    cursor.execute("""
        SELECT id, content, due_date, priority
        FROM tasks
        WHERE date(created_at) = ?
        ORDER BY created_at DESC
    """, (today,))
    tasks_created = [dict(row) for row in cursor.fetchall()]

    # People mentioned today
    cursor.execute("""
        SELECT id, name, mention_count, organization
        FROM people
        WHERE date(last_mentioned) = ?
        ORDER BY mention_count DESC
        LIMIT 10
    """, (today,))
    people_mentioned = [dict(row) for row in cursor.fetchall()]

    # Knowledge added today
    cursor.execute("""
        SELECT id, content, category
        FROM knowledge
        WHERE date(created_at) = ?
        ORDER BY created_at DESC
    """, (today,))
    knowledge_added = [dict(row) for row in cursor.fetchall()]

    # Emails processed today (if available)
    try:
        cursor.execute("""
            SELECT id, subject, sender, is_actionable
            FROM emails
            WHERE date(processed_at) = ?
            ORDER BY processed_at DESC
        """, (today,))
        emails_processed = [dict(row) for row in cursor.fetchall()]
    except:
        emails_processed = []

    conn.close()

    return {
        "date": today,
        "captures": captures,
        "tasks_completed": tasks_completed,
        "tasks_created": tasks_created,
        "people_mentioned": people_mentioned,
        "knowledge_added": knowledge_added,
        "emails_processed": emails_processed
    }


def get_tomorrow_preview() -> Dict[str, Any]:
    """Get what's coming up tomorrow."""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Tasks due tomorrow
    cursor.execute("""
        SELECT id, content, priority, project_id
        FROM tasks
        WHERE status = 'pending' AND due_date = ?
        ORDER BY priority DESC
    """, (tomorrow,))
    tasks_due = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "date": tomorrow,
        "tasks_due": tasks_due
    }


def generate_eod_digest() -> Dict[str, Any]:
    """Generate end-of-day digest with today's activity and tomorrow's preview."""
    today_activity = get_today_activity()
    tomorrow_preview = get_tomorrow_preview()

    # Also get current pending items for context
    pending_tasks = get_pending_tasks()
    overdue_tasks = get_overdue_tasks()

    digest = {
        "generated_at": datetime.now().isoformat(),
        "type": "eod",
        "today": {
            "date": today_activity["date"],
            "summary": {
                "captures_count": len(today_activity["captures"]),
                "tasks_completed_count": len(today_activity["tasks_completed"]),
                "tasks_created_count": len(today_activity["tasks_created"]),
                "people_mentioned_count": len(today_activity["people_mentioned"]),
                "knowledge_added_count": len(today_activity["knowledge_added"]),
                "emails_processed_count": len(today_activity["emails_processed"])
            },
            "highlights": {
                "tasks_completed": [
                    {"id": t["id"], "content": t["content"][:80]}
                    for t in today_activity["tasks_completed"][:5]
                ],
                "captures": [
                    {"id": c["id"], "content": c["content"][:80], "type": c["capture_type"]}
                    for c in today_activity["captures"][:5]
                ],
                "knowledge_added": [
                    {"id": k["id"], "content": k["content"][:80], "category": k["category"]}
                    for k in today_activity["knowledge_added"][:5]
                ],
                "people_mentioned": [
                    {"id": p["id"], "name": p["name"], "mentions": p["mention_count"]}
                    for p in today_activity["people_mentioned"][:5]
                ]
            }
        },
        "tomorrow": {
            "date": tomorrow_preview["date"],
            "tasks_due_count": len(tomorrow_preview["tasks_due"]),
            "tasks_due": [
                {"id": t["id"], "content": t["content"][:80], "priority": t.get("priority")}
                for t in tomorrow_preview["tasks_due"]
            ]
        },
        "current_status": {
            "pending_tasks_count": len(pending_tasks),
            "overdue_tasks_count": len(overdue_tasks)
        },
        "twitter": get_twitter_intelligence_summary()
    }

    return digest


def format_eod_text(digest: Dict) -> str:
    """Format end-of-day digest as human-readable text."""
    lines = []
    today = digest["today"]["date"]
    tomorrow = digest["tomorrow"]["date"]

    lines.append(f"# End of Day Digest - {datetime.now().strftime('%A, %B %d, %Y')}")
    lines.append("")

    # Today's Summary
    summary = digest["today"]["summary"]
    lines.append("## Today's Summary")
    lines.append(f"  - Captures: {summary['captures_count']}")
    lines.append(f"  - Tasks completed: {summary['tasks_completed_count']}")
    lines.append(f"  - Tasks created: {summary['tasks_created_count']}")
    lines.append(f"  - People mentioned: {summary['people_mentioned_count']}")
    if summary['knowledge_added_count'] > 0:
        lines.append(f"  - Knowledge entries added: {summary['knowledge_added_count']}")
    if summary['emails_processed_count'] > 0:
        lines.append(f"  - Emails processed: {summary['emails_processed_count']}")
    lines.append("")

    # Completed Tasks Today
    highlights = digest["today"]["highlights"]
    if highlights["tasks_completed"]:
        lines.append("## Completed Today")
        for task in highlights["tasks_completed"]:
            content = task["content"]
            if len(content) > 60:
                content = content[:57] + "..."
            lines.append(f"  ✓ {content}")
        lines.append("")

    # Knowledge Added Today
    if highlights["knowledge_added"]:
        lines.append("## Knowledge Added")
        for k in highlights["knowledge_added"]:
            content = k["content"]
            if len(content) > 50:
                content = content[:47] + "..."
            lines.append(f"  - [{k['category']}] {content}")
        lines.append("")

    # Tomorrow Preview Section
    tomorrow_section = digest["tomorrow"]
    if tomorrow_section["tasks_due_count"] > 0:
        lines.append("## Tomorrow Preview")

        if tomorrow_section["tasks_due"]:
            lines.append(f"### Tasks Due ({tomorrow_section['tasks_due_count']})")
            for task in tomorrow_section["tasks_due"]:
                content = task["content"]
                if len(content) > 60:
                    content = content[:57] + "..."
                priority_str = f" [P{task['priority']}]" if task.get("priority") else ""
                lines.append(f"  - {content}{priority_str}")
        lines.append("")
    else:
        lines.append("## Tomorrow Preview")
        lines.append("  No tasks due tomorrow.")
        lines.append("")

    # Current Status / Warnings
    status = digest["current_status"]
    warnings = []
    if status["overdue_tasks_count"] > 0:
        warnings.append(f"{status['overdue_tasks_count']} overdue task(s)")

    if warnings:
        lines.append("## ⚠️ Attention Needed")
        for w in warnings:
            lines.append(f"  - {w}")
        lines.append("")

    # Current backlog
    lines.append("## Current Backlog")
    lines.append(f"  - {status['pending_tasks_count']} pending tasks total")
    lines.append("")

    # Twitter
    twitter = digest.get("twitter", {})
    if twitter.get("available") and twitter.get("has_urgent"):
        lines.append("## Twitter")
        if twitter.get("drafts_ready", 0) > 0:
            lines.append(f"  - {twitter['drafts_ready']} drafts ready in Twitter app")
        if twitter.get("high_value_count", 0) > 0:
            lines.append(f"  - {twitter['high_value_count']} high-value opportunities")
        lines.append("")

    return "\n".join(lines)


def eod_digest() -> str:
    """Generate the full end-of-day digest with AI insights."""
    digest = generate_eod_digest()
    text = format_eod_text(digest)

    # Add AI insights
    insights = generate_ai_insights(digest)
    if insights:
        text += "\n## AI Insights\n" + insights

    return text


def generate_ai_insights(brief: Dict) -> str:
    """
    DEPRECATED: This function used Claude subprocess for insights.

    In the agentic pattern, Claude (the conversational agent) IS the insight
    generator. This function should not spawn a subprocess to ask Claude
    for insights - Claude is already in the conversation and can provide
    insights naturally when presenting the brief.

    Returns empty string. Claude should add insights when displaying brief data.
    """
    logger.warning("generate_ai_insights() is deprecated - Claude provides insights in conversation")
    # Return empty - Claude adds insights naturally in conversation
    return ""


def daily_brief() -> str:
    """Generate the full daily brief with AI insights."""
    brief = generate_brief("daily")
    text = format_brief_text(brief)

    # Add AI insights
    insights = generate_ai_insights(brief)
    if insights:
        text += "\n## AI Insights\n" + insights

    return text


# ============================================================================
# Meeting Prep
# ============================================================================

def get_person_context_for_meeting(person_name: str) -> Optional[Dict]:
    """
    Get comprehensive context about a person for meeting prep.
    Returns all relevant info: relationship, captures, shared projects.
    """
    # First, find the person by name
    person = get_person(person_name)
    if not person:
        return None

    person_id = person["id"]

    # Get full relationship summary
    summary = get_relationship_summary(person_id)
    if not summary:
        return None

    # Get additional captures about this person (more than the 5 in relationship summary)
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get recent captures mentioning this person (up to 20)
    cursor.execute("""
        SELECT id, content, capture_type, created_at
        FROM captures_v2
        WHERE linked_people LIKE ?
        ORDER BY created_at DESC
        LIMIT 20
    """, (f'%{person_id}%',))

    captures = []
    for row in cursor.fetchall():
        captures.append({
            "id": row["id"],
            "content": row["content"],
            "type": row["capture_type"],
            "created_at": row["created_at"]
        })

    # Get shared projects if any
    shared_projects = summary.get("shared_projects", [])
    project_details = []
    if shared_projects:
        for proj_id in shared_projects:
            cursor.execute("""
                SELECT id, name, status, description
                FROM projects WHERE id = ?
            """, (proj_id,))
            proj = cursor.fetchone()
            if proj:
                project_details.append({
                    "id": proj["id"],
                    "name": proj["name"],
                    "status": proj["status"],
                    "description": proj["description"]
                })

    conn.close()

    return {
        "person": {
            "id": person_id,
            "name": summary["name"],
            "organization": summary.get("organization"),
            "relationship": summary.get("relationship"),
            "context": summary.get("context"),
            "mention_count": summary.get("mention_count", 0),
            "interaction_count": summary.get("interaction_count", 0),
            "last_contacted": summary.get("last_contacted"),
            "days_since_contact": summary.get("days_since_contact"),
            "first_contacted": summary.get("first_contacted")
        },
        "captures": captures,
        "shared_projects": project_details
    }


def generate_meeting_prep(people: List[str], topic: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate a meeting prep brief for one or more people.

    Args:
        people: List of person names to look up
        topic: Optional topic to include in context search

    Returns:
        Dict with person contexts, topic-related captures, and suggested talking points
    """
    prep = {
        "generated_at": datetime.now().isoformat(),
        "type": "meeting_prep",
        "topic": topic,
        "attendees": [],
        "topic_context": [],
        "suggested_talking_points": []
    }

    # Get context for each person
    for person_name in people:
        person_context = get_person_context_for_meeting(person_name.strip())
        if person_context:
            prep["attendees"].append(person_context)
        else:
            # Person not found - add placeholder
            prep["attendees"].append({
                "person": {
                    "name": person_name.strip(),
                    "not_found": True
                },
                "captures": [],
                "shared_projects": []
            })

    # If topic provided, search for related content
    if topic:
        try:
            topic_results = unified_search(topic, sources=["captures", "knowledge"], limit=10)
            prep["topic_context"] = [
                {
                    "source_type": r["source_type"],
                    "content": r["content"][:200] if r.get("content") else "",
                    "relevance": r.get("relevance"),
                    "created_at": r.get("created_at")
                }
                for r in topic_results
            ]
        except Exception:
            prep["topic_context"] = []

    # Generate suggested talking points based on data
    talking_points = []

    # Add shared projects as talking points
    for attendee in prep["attendees"]:
        if attendee.get("shared_projects"):
            person_name = attendee["person"]["name"]
            for proj in attendee["shared_projects"]:
                talking_points.append({
                    "type": "project",
                    "person": person_name,
                    "content": f"Discuss {proj['name']}: {proj.get('description', '')[:60]}",
                    "status": proj.get("status")
                })

    # Add stale relationships as talking points
    for attendee in prep["attendees"]:
        days = attendee.get("person", {}).get("days_since_contact")
        if days and days > 14:
            talking_points.append({
                "type": "relationship",
                "person": attendee["person"]["name"],
                "content": f"Reconnect - last contact was {days} days ago"
            })

    prep["suggested_talking_points"] = talking_points

    return prep


def format_meeting_prep_text(prep: Dict) -> str:
    """Format meeting prep as human-readable text."""
    lines = []
    lines.append(f"# Meeting Prep - {datetime.now().strftime('%A, %B %d, %Y')}")

    if prep.get("topic"):
        lines.append(f"## Topic: {prep['topic']}")
    lines.append("")

    # Attendees Section
    lines.append("## Attendees")
    lines.append("")

    for attendee in prep.get("attendees", []):
        person = attendee.get("person", {})
        name = person.get("name", "Unknown")

        if person.get("not_found"):
            lines.append(f"### {name}")
            lines.append("  ⚠️ Not found in contacts")
            lines.append("")
            continue

        org = f" ({person.get('organization')})" if person.get("organization") else ""
        lines.append(f"### {name}{org}")

        # Relationship info
        if person.get("relationship"):
            lines.append(f"  Role: {person['relationship']}")
        if person.get("context"):
            lines.append(f"  Context: {person['context'][:100]}")

        # Contact info
        if person.get("interaction_count"):
            lines.append(f"  Interactions: {person['interaction_count']}")
        if person.get("days_since_contact") is not None:
            lines.append(f"  Last contact: {person['days_since_contact']} days ago")
        elif person.get("last_contacted"):
            lines.append(f"  Last contact: {person['last_contacted'][:10]}")
        lines.append("")

        # Shared projects
        projects = attendee.get("shared_projects", [])
        if projects:
            lines.append("  **Shared Projects:**")
            for proj in projects:
                status = f" [{proj.get('status', 'active')}]" if proj.get("status") else ""
                lines.append(f"    - {proj['name']}{status}")
            lines.append("")

        # Recent captures (history)
        captures = attendee.get("captures", [])
        if captures:
            lines.append("  **Recent History:**")
            for cap in captures[:5]:
                date_str = cap["created_at"][:10] if cap.get("created_at") else ""
                content = cap["content"][:60] if cap.get("content") else ""
                if len(cap.get("content", "")) > 60:
                    content += "..."
                lines.append(f"    - {date_str}: {content}")
            if len(captures) > 5:
                lines.append(f"    - ... and {len(captures) - 5} more items")
            lines.append("")

    # Topic Context Section
    if prep.get("topic_context"):
        lines.append("## Related Context")
        lines.append(f"Content related to \"{prep.get('topic')}\":")
        lines.append("")
        for ctx in prep["topic_context"]:
            source = ctx.get("source_type", "unknown")
            content = ctx.get("content", "")[:80]
            if len(ctx.get("content", "")) > 80:
                content += "..."
            lines.append(f"  - [{source}] {content}")
        lines.append("")

    # Suggested Talking Points
    if prep.get("suggested_talking_points"):
        lines.append("## Suggested Talking Points")
        for tp in prep["suggested_talking_points"]:
            tp_type = tp.get("type", "general")
            person = tp.get("person", "")
            content = tp.get("content", "")

            if tp.get("due"):
                lines.append(f"  - [{tp_type}] {person}: {content} (due: {tp['due']})")
            else:
                lines.append(f"  - [{tp_type}] {person}: {content}")
        lines.append("")

    return "\n".join(lines)


def meeting_prep(people: List[str], topic: Optional[str] = None) -> str:
    """Generate meeting prep with AI insights."""
    prep = generate_meeting_prep(people, topic)
    text = format_meeting_prep_text(prep)

    # Add AI insights
    insights = generate_ai_insights(prep)
    if insights:
        text += "\n## AI Insights\n" + insights

    return text


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PCP Smart Brief Engine - Generate briefs and summaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python brief.py              # Daily brief with AI insights
  python brief.py --daily      # Same as above
  python brief.py --weekly     # Weekly summary
  python brief.py --eod        # End-of-day digest
  python brief.py --json       # Daily brief as JSON
  python brief.py --weekly --json  # Weekly summary as JSON
  python brief.py --eod --json     # EOD digest as JSON
  python brief.py --meeting-prep --people "John, Jane" --topic "Q1 Planning"
"""
    )

    parser.add_argument("--daily", action="store_true", help="Generate daily brief (default)")
    parser.add_argument("--weekly", action="store_true", help="Generate weekly summary")
    parser.add_argument("--eod", action="store_true", help="Generate end-of-day digest")
    parser.add_argument("--meeting-prep", action="store_true", help="Generate meeting prep brief")
    parser.add_argument("--people", type=str, help="Comma-separated list of people for meeting prep")
    parser.add_argument("--topic", type=str, help="Optional topic for meeting prep")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of text")

    args = parser.parse_args()

    # Determine brief type (default to daily)
    if args.meeting_prep:
        if not args.people:
            print("Error: --meeting-prep requires --people argument")
            print("Example: python brief.py --meeting-prep --people 'John, Jane'")
            exit(1)
        people_list = [p.strip() for p in args.people.split(",")]
        if args.json:
            prep = generate_meeting_prep(people_list, args.topic)
            print(json.dumps(prep, indent=2))
        else:
            print(meeting_prep(people_list, args.topic))
    elif args.weekly:
        if args.json:
            summary = generate_weekly_summary()
            print(json.dumps(summary, indent=2))
        else:
            print(weekly_summary())
    elif args.eod:
        if args.json:
            digest = generate_eod_digest()
            print(json.dumps(digest, indent=2))
        else:
            print(eod_digest())
    else:
        # Daily is default
        if args.json:
            brief = generate_brief("daily")
            print(json.dumps(brief, indent=2))
        else:
            print(daily_brief())
