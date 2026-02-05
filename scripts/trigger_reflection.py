#!/usr/bin/env python3
"""
Trigger Reflection - Orchestrates PCP self-reflection sessions.

This script:
1. Exports context data for the analysis period
2. Spawns a reflection subagent with the context
3. Parses and stores the reflection output
4. Optionally notifies via Discord

Usage:
    # Weekly reflection (default)
    python trigger_reflection.py

    # Custom period
    python trigger_reflection.py --days 30

    # Without Discord notification
    python trigger_reflection.py --no-notify

    # Dry run (export only, don't spawn agent)
    python trigger_reflection.py --dry-run
"""

import os
import sys
import json
import re
import uuid
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_reflection_context import export_for_reflection
from discord_notify import notify
from common.db import get_db_connection, execute_write, execute_query

# Paths
VAULT_PATH = "/workspace/vault/vault.db"
REFLECTIONS_DIR = "/workspace/vault/reflections"
PROMPTS_DIR = "/workspace/prompts"

# Fallback for local development
if not os.path.exists(os.path.dirname(VAULT_PATH)):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    VAULT_PATH = os.path.join(base, "vault", "vault.db")
    REFLECTIONS_DIR = os.path.join(base, "vault", "reflections")
    PROMPTS_DIR = os.path.join(base, "prompts")


def ensure_schema():
    """Ensure reflection tables exist in the database."""
    if not os.path.exists(VAULT_PATH):
        print(f"Warning: Vault database not found at {VAULT_PATH}")
        return False

    conn = get_db_connection(VAULT_PATH)
    cursor = conn.cursor()

    # Create reflection_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reflection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            days_analyzed INTEGER NOT NULL,

            -- Full report content
            report_markdown TEXT,

            -- Structured data
            recommendations JSON,
            metrics JSON,

            -- Status tracking
            status TEXT DEFAULT 'pending_review',
            reviewed_at TEXT,
            reviewed_notes TEXT,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            agent_model TEXT,
            context_tokens INTEGER,

            -- Links
            discord_message_id TEXT
        )
    """)

    # Create reflection_recommendations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reflection_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reflection_id INTEGER NOT NULL,

            recommendation_id TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            observation TEXT,
            evidence TEXT,
            proposal TEXT,
            implementation TEXT,

            status TEXT DEFAULT 'pending',
            status_updated_at TEXT,
            status_notes TEXT,

            outcome TEXT,
            outcome_date TEXT,
            outcome_assessment TEXT,

            priority INTEGER,
            effort_estimate TEXT,

            FOREIGN KEY (reflection_id) REFERENCES reflection_history(id)
        )
    """)

    # Create indices
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_recommendations_status
        ON reflection_recommendations(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_recommendations_category
        ON reflection_recommendations(category)
    """)

    conn.commit()
    conn.close()
    return True


def get_reflection_prompt() -> str:
    """Load the reflection prompt template."""
    prompt_path = os.path.join(PROMPTS_DIR, "reflection_prompt.md")

    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Reflection prompt not found at {prompt_path}")

    with open(prompt_path, 'r') as f:
        return f.read()


def extract_json_from_report(report: str) -> Optional[Dict[str, Any]]:
    """
    Extract the structured JSON block from the reflection report.

    The reflection agent outputs a JSON block at the end of the report
    wrapped in ```json ... ``` markers.
    """
    # Find JSON block in the report
    json_pattern = r'```json\s*(\{[\s\S]*?\})\s*```'
    matches = list(re.finditer(json_pattern, report))

    if not matches:
        return None

    # Take the last JSON block (the structured output)
    last_match = matches[-1]
    json_str = last_match.group(1)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse JSON from report: {e}")
        return None


def parse_recommendations(report: str) -> List[Dict[str, Any]]:
    """
    Extract recommendations from the reflection report.

    Looks for the structured JSON block that the reflection agent outputs.
    Falls back to empty list if no JSON found.
    """
    data = extract_json_from_report(report)

    if not data or 'recommendations' not in data:
        print("Warning: No structured recommendations found in report")
        return []

    recommendations = []
    for rec in data['recommendations']:
        # Normalize to our database schema
        normalized = {
            'recommendation_id': rec.get('id', ''),
            'category': rec.get('category', 'other'),
            'title': rec.get('title', ''),
            'observation': rec.get('observation', ''),
            'evidence': rec.get('evidence', ''),
            'proposal': rec.get('proposal', rec.get('description', '')),
            'implementation': rec.get('implementation', ''),
            'priority': extract_priority(rec.get('id', '')),
            'effort_estimate': rec.get('effort', ''),
        }
        recommendations.append(normalized)

    return recommendations


def extract_priority(rec_id: str) -> int:
    """Extract priority number from recommendation ID like 'QW-1' -> 1"""
    match = re.search(r'-(\d+)$', rec_id)
    return int(match.group(1)) if match else 99


def get_report_summary(report: str) -> Optional[Dict[str, Any]]:
    """Extract the summary section from the JSON block."""
    data = extract_json_from_report(report)
    return data.get('summary') if data else None


def store_reflection(
    session_id: str,
    days: int,
    report: str,
    recommendations: List[Dict],
    metrics: Dict
) -> int:
    """
    Store reflection in the database.

    Returns:
        The reflection_history.id
    """
    now = datetime.now()
    period_start = (now - timedelta(days=days)).isoformat()
    period_end = now.isoformat()

    # Insert main reflection record
    conn = get_db_connection(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reflection_history
        (session_id, period_start, period_end, days_analyzed, report_markdown,
         recommendations, metrics, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_review', ?)
    """, (
        session_id,
        period_start,
        period_end,
        days,
        report,
        json.dumps(recommendations),
        json.dumps(metrics),
        now.isoformat()
    ))

    reflection_id = cursor.lastrowid

    # Insert individual recommendations
    for rec in recommendations:
        cursor.execute("""
            INSERT INTO reflection_recommendations
            (reflection_id, recommendation_id, category, title, observation,
             evidence, proposal, implementation, priority, effort_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            reflection_id,
            rec.get('recommendation_id'),
            rec.get('category'),
            rec.get('title'),
            rec.get('observation'),
            rec.get('evidence'),
            rec.get('proposal'),
            rec.get('implementation'),
            rec.get('priority'),
            rec.get('effort_estimate')
        ))

    conn.commit()
    conn.close()

    return reflection_id


def generate_summary(report: str, recommendations: List[Dict]) -> str:
    """Generate a Discord-friendly summary of the reflection."""
    # Try to extract executive summary from report
    exec_summary = ""
    if "Executive Summary" in report:
        # Extract the executive summary section
        match = re.search(r'## Executive Summary\n(.+?)(?=\n##|\Z)', report, re.DOTALL)
        if match:
            exec_summary = match.group(1).strip()[:500]

    # Count recommendations by category
    by_category = {}
    for rec in recommendations:
        cat = rec.get('category', 'other')
        by_category[cat] = by_category.get(cat, 0) + 1

    # Build summary
    lines = ["**PCP Self-Reflection Complete**\n"]

    if exec_summary:
        lines.append(exec_summary[:300] + "..." if len(exec_summary) > 300 else exec_summary)
        lines.append("")

    lines.append("**Recommendations:**")
    if by_category.get('quick_win'):
        lines.append(f"- Quick Wins: {by_category['quick_win']}")
    if by_category.get('medium_improvement'):
        lines.append(f"- Medium Improvements: {by_category['medium_improvement']}")
    if by_category.get('major_proposal'):
        lines.append(f"- Major Proposals: {by_category['major_proposal']}")
    if by_category.get('wild_idea'):
        lines.append(f"- Wild Ideas: {by_category['wild_idea']}")

    lines.append("")
    lines.append("Use `python manage_reflections.py pending` to review recommendations.")

    return '\n'.join(lines)


def trigger_reflection(
    days: int = 7,
    notify_discord: bool = True,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Trigger a self-reflection session.

    Args:
        days: Number of days to analyze
        notify_discord: Whether to send Discord notification
        dry_run: If True, only export context without spawning agent

    Returns:
        Dictionary with session info and results
    """
    session_id = str(uuid.uuid4())[:8]
    now = datetime.now()

    print(f"Starting reflection session {session_id}")
    print(f"Analyzing last {days} days")

    # Ensure schema exists
    if not ensure_schema():
        print("Warning: Could not ensure database schema")

    # Create reflections directory
    os.makedirs(REFLECTIONS_DIR, exist_ok=True)

    # Export context
    context_file = os.path.join(REFLECTIONS_DIR, f"context_{session_id}.json")
    context = export_for_reflection(days=days, output_path=context_file)

    print(f"Exported context to {context_file}")
    print(f"  - Discord messages: {len(context.get('discord_history', []))}")
    print(f"  - Vault captures: {len(context.get('vault_snapshot', {}).get('captures', []))}")
    print(f"  - Friction events: {len(context.get('friction_events', []))}")

    if dry_run:
        print("\nDry run - not spawning reflection agent")
        return {
            "session_id": session_id,
            "context_file": context_file,
            "dry_run": True
        }

    # Get reflection prompt
    try:
        prompt = get_reflection_prompt()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return {"error": str(e)}

    # Build the full prompt with context
    full_prompt = f"""
{prompt}

## Context Data

The following context has been exported for your analysis:

**Period**: Last {days} days
**Export file**: {context_file}

### Usage Metrics
```json
{json.dumps(context.get('usage_metrics', {}), indent=2)}
```

### Vault Statistics
```json
{json.dumps(context.get('vault_snapshot', {}).get('stats', {}), indent=2)}
```

### Friction Events Detected: {len(context.get('friction_events', []))}

Please begin your analysis by reading the VISION.md and CLAUDE.md files,
then analyze the exported context file for detailed Discord history and vault data.

Save your full report to: {REFLECTIONS_DIR}/report_{session_id}.md
"""

    # Write the prompt to a file for the agent
    prompt_file = os.path.join(REFLECTIONS_DIR, f"prompt_{session_id}.md")
    with open(prompt_file, 'w') as f:
        f.write(full_prompt)

    print(f"\nReflection prompt saved to {prompt_file}")
    print("\nTo run the reflection agent, execute:")
    print(f"  claude --prompt-file {prompt_file}")
    print("\nOr use the Task tool to spawn a reflection subagent.")

    # For now, return the setup info
    # In production, this would spawn the actual agent
    result = {
        "session_id": session_id,
        "context_file": context_file,
        "prompt_file": prompt_file,
        "output_file": os.path.join(REFLECTIONS_DIR, f"report_{session_id}.md"),
        "days_analyzed": days,
        "metrics": context.get('usage_metrics', {}),
        "status": "ready_to_run"
    }

    if notify_discord:
        notify(f"Reflection session {session_id} prepared. {days} days of data exported. Ready for analysis.")

    return result


def complete_reflection(
    session_id: str,
    report_path: Optional[str] = None,
    notify_discord: bool = True
) -> Dict[str, Any]:
    """
    Complete a reflection session by parsing and storing the report.

    Call this after the reflection agent has generated its report.

    Args:
        session_id: The session ID from trigger_reflection
        report_path: Path to the generated report (defaults to standard location)
        notify_discord: Whether to send Discord notification

    Returns:
        Dictionary with completion info
    """
    if not report_path:
        report_path = os.path.join(REFLECTIONS_DIR, f"report_{session_id}.md")

    if not os.path.exists(report_path):
        return {"error": f"Report not found at {report_path}"}

    # Read the report
    with open(report_path, 'r') as f:
        report = f.read()

    # Parse recommendations
    recommendations = parse_recommendations(report)
    print(f"Parsed {len(recommendations)} recommendations")

    # Load context for metrics
    context_file = os.path.join(REFLECTIONS_DIR, f"context_{session_id}.json")
    metrics = {}
    days = 7
    if os.path.exists(context_file):
        with open(context_file, 'r') as f:
            context = json.load(f)
            metrics = context.get('usage_metrics', {})
            days = context.get('export_metadata', {}).get('days_analyzed', 7)

    # Store in database
    try:
        reflection_id = store_reflection(
            session_id=session_id,
            days=days,
            report=report,
            recommendations=recommendations,
            metrics=metrics
        )
        print(f"Stored reflection with ID {reflection_id}")
    except Exception as e:
        print(f"Warning: Could not store reflection: {e}")
        reflection_id = None

    # Generate and send summary
    if notify_discord:
        summary = generate_summary(report, recommendations)
        notify(summary)

    return {
        "session_id": session_id,
        "reflection_id": reflection_id,
        "recommendations_count": len(recommendations),
        "report_path": report_path,
        "status": "completed"
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Trigger PCP self-reflection")
    parser.add_argument("--days", "-d", type=int, default=7,
                       help="Number of days to analyze (default: 7)")
    parser.add_argument("--no-notify", action="store_true",
                       help="Skip Discord notification")
    parser.add_argument("--dry-run", action="store_true",
                       help="Export context only, don't prepare agent")
    parser.add_argument("--complete", "-c", type=str,
                       help="Complete a reflection session (provide session_id)")
    parser.add_argument("--report", "-r", type=str,
                       help="Path to report file (for --complete)")

    args = parser.parse_args()

    if args.complete:
        result = complete_reflection(
            session_id=args.complete,
            report_path=args.report,
            notify_discord=not args.no_notify
        )
    else:
        result = trigger_reflection(
            days=args.days,
            notify_discord=not args.no_notify,
            dry_run=args.dry_run
        )

    print("\nResult:")
    print(json.dumps(result, indent=2))
