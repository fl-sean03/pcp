---
name: email-processing
description: Email, inbox, Outlook, Microsoft 365, mail, messages, fetch emails, search emails, draft, reply, email processing (project)
triggers:
  - email
  - inbox
  - outlook
  - mail
  - messages
  - draft
  - reply
requires:
  scripts:
    - email_processor.py
    - microsoft_graph.py
  config:
    - skills.entries.email-processing.enabled
os:
  - linux
  - darwin
---

# Email Processing

Outlook email integration via Microsoft Graph API. Fetch, search, and manage emails - including creating drafts (but **NEVER sending** automatically).

## Quick Start

```bash
# Setup (one-time)
python microsoft_graph.py configure CLIENT_ID SECRET --tenant TENANT_ID
python microsoft_graph.py auth-url  # Follow the URL to authenticate

# Fetch new emails
python email_processor.py fetch

# Search emails
python email_processor.py search "budget report"

# Create a draft (NEVER sends automatically)
python email_processor.py draft --to "user@example.com" --subject "Subject" --body "Body text"
```

## ⚠️ CRITICAL: Draft-Only Policy

**The email system creates DRAFTS only - it NEVER sends emails automatically.**

When the user asks to "send an email" or "reply to X":
1. Create a draft using `create_draft()`
2. Inform the user: "I've created a draft - please review and send from Outlook"
3. Provide the web link if available

This is a deliberate safety feature. the user must manually send all emails.

## Setup Requirements

Before using email features, Microsoft Graph must be configured:

### 1. Azure AD App Registration
1. Go to https://portal.azure.com
2. Azure AD → App registrations → New registration
3. Name: "PCP Integration"
4. Redirect URI: http://localhost:8080
5. Note: client_id, tenant_id
6. Certificates & secrets → New client secret

### 2. API Permissions
Required permissions:
- `Mail.Read` - Read user's emails
- `Mail.ReadWrite` - Create drafts
- `offline_access` - Maintain access (refresh tokens)

### 3. Configure PCP
```bash
python microsoft_graph.py configure CLIENT_ID CLIENT_SECRET --tenant TENANT_ID
python microsoft_graph.py auth-url
# Visit the URL, sign in, copy the code from redirect URL
python microsoft_graph.py authenticate CODE
python microsoft_graph.py status  # Verify: "Authenticated: Yes"
```

## Functions

### Fetching Emails

```python
from email_processor import fetch_new_emails

# Fetch new emails since last sync
result = fetch_new_emails(limit=50)
# Returns: {success, fetched, stored, skipped, emails}

if result['success']:
    for email in result['emails']:
        print(f"{email['sender']}: {email['subject']}")
```

### Searching Emails

```python
from email_processor import search_emails, get_email

# Search by subject, sender, or body content
results = search_emails("project update", days=7)

# Get full email content by ID
email = get_email(42)
print(email['body_full'])  # Full email body
```

### Listing Emails

```python
from email_processor import list_emails, get_actionable_emails

# List recent emails
recent = list_emails(days=7, limit=50)

# Get actionable emails (questions, requests, deadlines)
actionable = get_actionable_emails()
for email in actionable:
    print(f"[!] {email['sender']}: {email['subject']}")
```

### Creating Drafts (NEVER Sends)

```python
from email_processor import create_draft

# Create a draft - does NOT send
result = create_draft(
    to="user@example.com, other@example.com",  # Comma-separated
    subject="Re: Project Update",
    body="Here's the update you requested...",
    cc="manager@example.com"  # Optional
)

if result['success']:
    print(f"Draft created: {result['draft_id']}")
    print(f"View in Outlook: {result['web_link']}")
    print("NOTE: Draft must be sent manually from Outlook!")
```

## CLI Commands

```bash
# Fetch new emails from Outlook
python email_processor.py fetch --limit 50

# Search emails
python email_processor.py search "query" --days 7

# List recent emails
python email_processor.py list --days 7 --limit 50
python email_processor.py list --actionable  # Only actionable emails

# Get full email by ID
python email_processor.py get 42

# Create a draft (DOES NOT SEND)
python email_processor.py draft --to "user@example.com" --subject "Subject" --body "Body text" --cc "cc@example.com"
```

## Actionability Detection

Emails are automatically flagged as "actionable" based on content:

| Category | Detected Phrases |
|----------|------------------|
| Requests | please, could you, would you, need you to |
| Urgency | urgent, ASAP, by tomorrow, deadline |
| Questions | ?, what do you think, your thoughts |
| Responses | let me know, get back to me, waiting for |
| Meetings | schedule a, set up a meeting, calendar invite |

```python
# In CLI output: [!] indicates actionable
#   [!] [  42] 2026-01-13 | John <john@ex.com> | Please review...
#       [  43] 2026-01-13 | Jane <jane@ex.com> | FYI: Notes from...
```

## When User Says...

| User Says | Action |
|-----------|--------|
| "Check my email" | `python email_processor.py fetch && python email_processor.py list --actionable` |
| "Any urgent emails?" | `get_actionable_emails()` |
| "Search for email about X" | `search_emails("X")` |
| "Show me that email from John" | `search_emails("John")` then `get_email(ID)` |
| "Reply to that email" / "Send email" | `create_draft(...)` + tell the user "Draft created, please send from Outlook" |
| "What did Sarah say about the budget?" | `search_emails("Sarah budget")` |

## Integration with Briefs

Actionable emails appear in daily briefs:

```python
from brief import daily_brief
brief = daily_brief()
# Includes "## Actionable Emails" section
```

## Scheduled Sync

The scheduler can auto-fetch emails:

```bash
# Check scheduler configuration
python scheduler.py --config
# email_sync_interval_hours: 2

# Manual sync
python scheduler.py --run email
```

## Database Table

Emails are stored in the `emails` table:

| Column | Description |
|--------|-------------|
| id | Database ID |
| message_id | Outlook message ID (unique) |
| subject | Email subject |
| sender | "Name <email>" format |
| recipients | JSON array of recipient emails |
| body_preview | First 500 chars of body |
| body_full | Complete email content |
| is_actionable | Auto-detected actionability |
| action_taken | Notes on action taken |
| received_at | When email was received |
| processed_at | When PCP processed it |

## Error Handling

```python
result = fetch_new_emails()

if not result['success']:
    error = result['error']
    if 'not configured' in error.lower():
        print("Run: python microsoft_graph.py configure ...")
    elif 'not authenticated' in error.lower():
        print("Run: python microsoft_graph.py auth-url")
    else:
        print(f"API Error: {error}")
```

## Related Skills

- **pcp-operations**: System overview
- **vault-operations**: Captures and search
- **brief-generation**: Briefs include email sections

---

**Remember**: Draft-only policy. Never send emails automatically. Always inform the user that a draft was created and needs manual sending.
