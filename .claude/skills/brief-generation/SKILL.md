---
name: brief-generation
description: brief, summary, daily, weekly, end of day, EOD, digest, morning, recap, meeting prep, what's due, status update, review
---

# Brief Generation Skill

## Quick Start

PCP generates intelligent briefs and summaries to keep the user informed:
- **Daily Brief**: Morning overview of activity, tasks
- **Weekly Summary**: Week-in-review with stats and highlights
- **End-of-Day Digest**: Day recap + tomorrow preview
- **Meeting Prep**: Context about attendees, history

All briefs use `scripts/brief.py` and include AI-generated insights.

## Brief Types

| Type | CLI | Function | When to Use |
|------|-----|----------|-------------|
| Daily | `python brief.py --daily` | `daily_brief()` | Morning overview |
| Weekly | `python brief.py --weekly` | `weekly_summary()` | Week review (Monday) |
| EOD | `python brief.py --eod` | `eod_digest()` | End of workday |
| Meeting Prep | `python brief.py --meeting-prep --people "X"` | `meeting_prep(people, topic)` | Before meetings |

## Daily Brief

Morning overview with urgent items first, then activity summary.

**Sections included:**
1. OVERDUE TASKS (urgent)
2. Upcoming Deadlines (next 7 days)
3. Activity Summary (captures, tasks completed)
4. Project Activity
5. People Recently Mentioned
6. Stale Relationships (14+ days)
7. Stalled Projects (14+ days)
8. Actionable Emails
9. Recently Added Knowledge
10. AI Insights

**Python:**
```python
from brief import daily_brief, generate_brief

# With AI insights (full brief)
text = daily_brief()
print(text)

# Structured data only (no AI)
data = generate_brief("daily")
print(data["tasks"]["overdue_count"])
```

**CLI:**
```bash
python brief.py              # Daily brief with AI insights
python brief.py --daily      # Same as above
python brief.py --json       # As JSON (no AI insights)
```

## Weekly Summary

Comprehensive week-in-review with statistics and highlights.

**Sections included:**
1. Activity Overview (captures by type, people, projects)
2. Task Summary (created, completed, rate)
3. Knowledge Added (by category)
4. Completed Tasks
5. Decisions Made
6. Most Active Contacts
7. Most Active Projects
8. Attention Needed (overdue items, stale relationships)
9. AI Insights

**Python:**
```python
from brief import weekly_summary, generate_weekly_summary

# With AI insights
text = weekly_summary()

# Structured data
data = generate_weekly_summary()
print(data["stats"]["tasks"]["completion_rate"])
print(data["highlights"]["top_people"])
```

**CLI:**
```bash
python brief.py --weekly         # Weekly with AI insights
python brief.py --weekly --json  # As JSON
```

## End-of-Day Digest

Day recap with tomorrow preview - perfect for closing out the workday.

**Sections included:**
1. Today's Summary (captures, tasks, people, knowledge, emails)
2. Completed Today
3. Knowledge Added
4. Tomorrow Preview (tasks due)
5. Attention Needed (overdue warnings)
6. Current Backlog
7. AI Insights

**Python:**
```python
from brief import eod_digest, generate_eod_digest

# With AI insights
text = eod_digest()

# Structured data
data = generate_eod_digest()
print(data["today"]["summary"]["tasks_completed_count"])
print(data["tomorrow"]["tasks_due"])
```

**CLI:**
```bash
python brief.py --eod         # EOD with AI insights
python brief.py --eod --json  # As JSON
```

## Meeting Prep

Context brief before meetings - shows relationship history and shared projects.

**Sections included:**
1. Each Attendee:
   - Role/relationship
   - Context
   - Interaction count and last contact
   - Shared projects
   - Recent history (captures)
2. Related Context (if topic provided)
3. Suggested Talking Points (auto-generated)
4. AI Insights

**Python:**
```python
from brief import meeting_prep, generate_meeting_prep

# Multiple people, with topic
text = meeting_prep(["John", "Jane"], topic="Q1 Planning")
print(text)

# Single person, no topic
text = meeting_prep(["John"])

# Structured data
data = generate_meeting_prep(["John", "Jane"], "Q1 Planning")
print(data["attendees"])
print(data["suggested_talking_points"])
```

**CLI:**
```bash
python brief.py --meeting-prep --people "John"
python brief.py --meeting-prep --people "John, Jane" --topic "Q1 Planning"
python brief.py --meeting-prep --people "John" --json
```

## When the User Says...

| User Request | Action |
|--------------|--------|
| "Give me a brief" | `daily_brief()` |
| "What's on my plate?" | `daily_brief()` |
| "Week in review" | `weekly_summary()` |
| "How did this week go?" | `weekly_summary()` |
| "What did I do today?" | `eod_digest()` |
| "End of day recap" | `eod_digest()` |
| "Prep me for meeting with John" | `meeting_prep(["John"])` |
| "What's my history with Jane?" | `meeting_prep(["Jane"])` or `get_relationship_summary()` |
| "What's overdue?" | `daily_brief()` or `get_overdue_tasks()` |
| "What's due tomorrow?" | `eod_digest()` or `get_upcoming_deadlines(1)` |

## Helper Functions

Access underlying data directly:

```python
from brief import (
    get_recent_captures,      # Captures from last N hours
    get_pending_tasks,        # All pending tasks
    get_overdue_tasks,        # Overdue tasks
    get_upcoming_deadlines,   # Tasks due in N days
    get_recent_people_mentions,  # Recently mentioned people
    get_project_activity,     # Project activity summary
    get_stale_relationships_summary,  # 14+ days without contact
    get_stalled_projects_summary,     # 14+ days without activity
    get_actionable_emails_summary,    # Emails needing action
    get_recent_knowledge_summary,     # Knowledge added recently
    get_week_stats,           # Weekly statistics
    get_week_highlights,      # Notable items from week
    get_today_activity,       # All activity from today
    get_tomorrow_preview,     # Tomorrow's due items
)

# Examples
captures = get_recent_captures(hours=24)
deadlines = get_upcoming_deadlines(days=3)
```

## Scheduled Briefs

Briefs are auto-generated on a schedule (see scheduler.py):

| Brief | Schedule | Config Key |
|-------|----------|------------|
| Daily Brief | 8:00 AM | `brief_hour: 8` |
| EOD Digest | 6:00 PM | `eod_digest_hour: 18` |
| Weekly Summary | Monday 9:00 AM | `weekly_summary_day: 0, weekly_summary_hour: 9` |

Run scheduler manually:
```bash
python scheduler.py --run brief    # Daily brief
python scheduler.py --run eod      # EOD digest
python scheduler.py --run weekly   # Weekly summary
```

## AI Insights

All briefs include AI-generated insights using Claude:
- 2-3 actionable bullet points
- Focus on priorities, blockers, patterns, recommendations

To get brief without AI insights (faster):
```python
# Use generate_* functions instead of brief-name functions
data = generate_brief("daily")      # No AI
text = daily_brief()                # With AI

data = generate_weekly_summary()    # No AI
text = weekly_summary()             # With AI
```

## Output Formats

**Text (default):**
Human-readable markdown with sections and bullet points.

**JSON:**
Structured data for programmatic access.

```bash
python brief.py --json              # Daily as JSON
python brief.py --weekly --json     # Weekly as JSON
python brief.py --eod --json        # EOD as JSON
python brief.py --meeting-prep --people "John" --json
```

## Integration with Other Skills

Briefs pull data from multiple sources:
- **vault-operations**: Captures, tasks, people, projects
- **email-processing**: Actionable emails
- **knowledge-base**: Recently added knowledge

## Tips

1. **Morning routine**: Run `daily_brief()` to see what needs attention
2. **Before meetings**: Use `meeting_prep()` to restore context about attendees
3. **End of day**: Run `eod_digest()` to review and plan tomorrow
4. **Weekly review**: Run `weekly_summary()` on Mondays to see patterns
5. **JSON for automation**: Use `--json` when integrating with other tools

## Related Skills

- `/vault-operations` - Underlying capture and task data
- `/email-processing` - Email integration
- `/relationship-intelligence` - People tracking
- `/project-health` - Project status
