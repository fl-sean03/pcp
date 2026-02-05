#!/usr/bin/env python3
"""
Email Processor for PCP - Outlook email integration via Microsoft Graph API.

This module handles:
- Fetching new emails from Outlook
- Storing emails with full content
- Tracking sync timestamps

Setup:
1. Configure Microsoft Graph: python microsoft_graph.py configure CLIENT_ID SECRET
2. Authenticate: python microsoft_graph.py auth-url, then authenticate with the code
3. Fetch emails: python email_processor.py --fetch
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, List

# Import Microsoft Graph client
from microsoft_graph import MicrosoftGraphClient, VAULT_PATH


def _get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _detect_actionability(subject: str, body: str, sender: str) -> bool:
    """Detect if an email is actionable based on content.

    Actionable emails typically contain:
    - Questions directed at the recipient
    - Requests for action/response
    - Deadlines or time-sensitive content
    - Meeting invites or scheduling requests

    Args:
        subject: Email subject
        body: Email body content (plain text)
        sender: Sender email/name

    Returns:
        True if email appears to require action
    """
    text = f"{subject} {body}".lower()

    # Action indicators
    action_phrases = [
        'please ',
        'could you',
        'can you',
        'would you',
        'need you to',
        'asking you to',
        'request',
        'action required',
        'action needed',
        'urgent',
        'asap',
        'by tomorrow',
        'by end of day',
        'by eod',
        'by friday',
        'by monday',
        'deadline',
        'due date',
        'let me know',
        'get back to me',
        'waiting for your',
        'awaiting your',
        'your response',
        'your feedback',
        'your input',
        'your approval',
        'please review',
        'please confirm',
        'schedule a',
        'set up a meeting',
        'calendar invite',
        'rsvp',
    ]

    # Question indicators (often require response)
    question_indicators = [
        '?',
        'what do you think',
        'your thoughts',
        'your opinion',
        'how should we',
        'should we',
        'when can',
        'are you available',
    ]

    # Check for action phrases
    for phrase in action_phrases:
        if phrase in text:
            return True

    # Check for questions in subject or first 500 chars
    check_text = f"{subject} {body[:500]}".lower()
    for indicator in question_indicators:
        if indicator in check_text:
            return True

    return False


def store_email(data: Dict) -> Optional[int]:
    """Store an email in the database.

    Args:
        data: Dict with email data:
            - message_id: Unique Outlook message ID (required)
            - subject: Email subject
            - sender: Sender name and email
            - recipients: List of recipient emails
            - body_preview: First 500 chars (will be created if not provided)
            - body_full: Complete email content
            - received_at: When email was received
            - is_read: Whether email has been read
            - has_attachments: Whether email has attachments

    Returns:
        ID of stored email, or None if already exists (duplicate)
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if email already exists (by message_id)
        cursor.execute("SELECT id FROM emails WHERE message_id = ?", (data.get('message_id'),))
        if cursor.fetchone():
            conn.close()
            return None  # Already exists

        # Create body_preview if not provided (500 chars)
        body_full = data.get('body_full', '')
        body_preview = data.get('body_preview', '')
        if not body_preview and body_full:
            body_preview = body_full[:500]

        # Detect actionability
        is_actionable = _detect_actionability(
            data.get('subject', ''),
            body_full,
            data.get('sender', '')
        )

        # Store recipients as JSON
        recipients = data.get('recipients', [])
        if isinstance(recipients, list):
            recipients = json.dumps(recipients)

        cursor.execute("""
            INSERT INTO emails (
                message_id, subject, sender, recipients,
                body_preview, body_full,
                is_actionable, received_at, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('message_id'),
            data.get('subject'),
            data.get('sender'),
            recipients,
            body_preview,
            body_full,
            is_actionable,
            data.get('received_at'),
            datetime.now().isoformat()
        ))

        email_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return email_id

    except sqlite3.IntegrityError:
        # Duplicate message_id (unique constraint)
        conn.close()
        return None
    except Exception as e:
        conn.close()
        raise e


def _get_last_sync_timestamp() -> Optional[str]:
    """Get the timestamp of the last email sync.

    Returns:
        ISO timestamp string of last sync, or None if never synced
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT MAX(received_at) as last_sync
        FROM emails
    """)
    row = cursor.fetchone()
    conn.close()

    if row and row['last_sync']:
        return row['last_sync']
    return None


def _set_sync_metadata(key: str, value: str) -> None:
    """Store sync metadata in the database.

    Uses the oauth_tokens table with a special provider name for metadata storage.

    Args:
        key: Metadata key (e.g., 'email_last_sync')
        value: Metadata value
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    # Use oauth_tokens table with special provider for metadata
    metadata_provider = f"metadata_{key}"

    cursor.execute("""
        DELETE FROM oauth_tokens WHERE provider = ?
    """, (metadata_provider,))

    cursor.execute("""
        INSERT INTO oauth_tokens (provider, access_token, scopes)
        VALUES (?, NULL, ?)
    """, (metadata_provider, json.dumps({'value': value, 'updated_at': datetime.now().isoformat()})))

    conn.commit()
    conn.close()


def _get_sync_metadata(key: str) -> Optional[str]:
    """Get sync metadata from the database.

    Args:
        key: Metadata key

    Returns:
        Metadata value or None
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    metadata_provider = f"metadata_{key}"

    cursor.execute("""
        SELECT scopes FROM oauth_tokens WHERE provider = ?
    """, (metadata_provider,))

    row = cursor.fetchone()
    conn.close()

    if row and row['scopes']:
        try:
            data = json.loads(row['scopes'])
            return data.get('value')
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def fetch_new_emails(limit: int = 50) -> Dict:
    """Fetch new emails from Outlook via Microsoft Graph API.

    Fetches emails received since the last sync, or the most recent N emails
    if this is the first sync.

    Args:
        limit: Maximum number of emails to fetch (default 50)

    Returns:
        Dict with:
            - success: bool
            - fetched: int (number of emails fetched)
            - error: str (if not successful)
            - emails: list of email dicts (if successful)
    """
    client = MicrosoftGraphClient()

    # Check if configured
    if not client.is_configured():
        return {
            'success': False,
            'fetched': 0,
            'error': 'Microsoft Graph not configured. Run: python microsoft_graph.py configure CLIENT_ID SECRET'
        }

    # Check if authenticated
    if not client.is_authenticated():
        return {
            'success': False,
            'fetched': 0,
            'error': 'Not authenticated. Run: python microsoft_graph.py auth-url, then authenticate'
        }

    try:
        # Build query parameters
        params = {
            '$top': limit,
            '$orderby': 'receivedDateTime desc',
            '$select': 'id,subject,from,toRecipients,ccRecipients,bodyPreview,body,receivedDateTime,isRead,hasAttachments'
        }

        # Check for last sync to use filtering
        last_sync = _get_last_sync_timestamp()
        if last_sync:
            # Convert to Graph API filter format (ISO 8601)
            # Filter for emails received after last sync
            params['$filter'] = f"receivedDateTime gt {last_sync}"
            params.pop('$top', None)  # Get all new emails when filtering by date

        # Fetch emails from Graph API
        response = client.api_request('GET', '/me/messages', params=params)

        emails_data = response.get('value', [])

        # Process and store emails
        processed_emails = []
        stored_count = 0
        skipped_count = 0

        for email in emails_data:
            processed = {
                'message_id': email.get('id'),
                'subject': email.get('subject', '(No subject)'),
                'sender': _extract_email_address(email.get('from', {})),
                'recipients': _extract_recipients(email),
                'body_preview': email.get('bodyPreview', '')[:500],
                'body_full': _extract_body_content(email.get('body', {})),
                'received_at': email.get('receivedDateTime'),
                'is_read': email.get('isRead', False),
                'has_attachments': email.get('hasAttachments', False)
            }

            # Store the email in the database
            email_id = store_email(processed)
            if email_id:
                processed['id'] = email_id
                stored_count += 1
            else:
                skipped_count += 1  # Already exists (duplicate)

            processed_emails.append(processed)

        # Update last sync timestamp
        if processed_emails:
            _set_sync_metadata('email_last_fetch', datetime.now().isoformat())

        return {
            'success': True,
            'fetched': len(processed_emails),
            'stored': stored_count,
            'skipped': skipped_count,
            'emails': processed_emails
        }

    except Exception as e:
        return {
            'success': False,
            'fetched': 0,
            'error': str(e)
        }


def _row_to_dict(row) -> Dict:
    """Convert a database row to a dictionary.

    Args:
        row: sqlite3.Row object

    Returns:
        Dict with all row fields
    """
    if row is None:
        return None

    result = dict(row)
    # Parse recipients JSON
    if 'recipients' in result and result['recipients']:
        try:
            result['recipients'] = json.loads(result['recipients'])
        except (json.JSONDecodeError, TypeError):
            result['recipients'] = []
    return result


def search_emails(query: str, days: Optional[int] = None) -> List[Dict]:
    """Search emails by subject, sender, or body content.

    Args:
        query: Search query (searches subject, sender, body_preview, body_full)
        days: Optional limit to emails from last N days

    Returns:
        List of matching email dicts
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT id, message_id, subject, sender, recipients,
               body_preview, received_at, is_actionable, action_taken
        FROM emails
        WHERE (
            subject LIKE ? OR
            sender LIKE ? OR
            body_preview LIKE ? OR
            body_full LIKE ?
        )
    """
    params = [f"%{query}%"] * 4

    if days is not None:
        sql += " AND date(received_at) >= date(?, '-' || ? || ' days')"
        params.extend([datetime.now().isoformat(), days])

    sql += " ORDER BY received_at DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def get_email(email_id: int) -> Optional[Dict]:
    """Get a single email by ID with full content.

    Args:
        email_id: Database ID of the email

    Returns:
        Dict with full email data including body_full, or None if not found
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, message_id, subject, sender, recipients,
               body_preview, body_full, received_at, processed_at,
               is_actionable, action_taken, extracted_entities
        FROM emails
        WHERE id = ?
    """, (email_id,))

    row = cursor.fetchone()
    conn.close()

    return _row_to_dict(row)


def list_emails(days: int = 7, limit: int = 50) -> List[Dict]:
    """List recent emails.

    Args:
        days: Number of days to look back (default: 7)
        limit: Maximum number of emails to return (default: 50)

    Returns:
        List of email dicts (without body_full for performance)
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, message_id, subject, sender, recipients,
               body_preview, received_at, is_actionable, action_taken
        FROM emails
        WHERE date(received_at) >= date(?, '-' || ? || ' days')
        ORDER BY received_at DESC
        LIMIT ?
    """, (datetime.now().isoformat(), days, limit))

    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def get_actionable_emails(include_actioned: bool = False) -> List[Dict]:
    """Get emails marked as actionable.

    Args:
        include_actioned: If True, include emails where action has been taken

    Returns:
        List of actionable email dicts
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT id, message_id, subject, sender, recipients,
               body_preview, received_at, is_actionable, action_taken
        FROM emails
        WHERE is_actionable = 1
    """

    if not include_actioned:
        sql += " AND (action_taken IS NULL OR action_taken = '')"

    sql += " ORDER BY received_at DESC"

    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def _extract_email_address(email_from: Dict) -> str:
    """Extract email address from Graph API from field.

    Args:
        email_from: The 'from' field from Graph API

    Returns:
        Formatted string like "Name <email@example.com>" or just email
    """
    if not email_from:
        return ''

    email_address = email_from.get('emailAddress', {})
    name = email_address.get('name', '')
    address = email_address.get('address', '')

    if name and address:
        return f"{name} <{address}>"
    return address or name or ''


def _extract_recipients(email: Dict) -> List[str]:
    """Extract all recipients (To and CC) from email.

    Args:
        email: Email data from Graph API

    Returns:
        List of recipient email addresses
    """
    recipients = []

    # To recipients
    for r in email.get('toRecipients', []):
        addr = r.get('emailAddress', {}).get('address')
        if addr:
            recipients.append(addr)

    # CC recipients
    for r in email.get('ccRecipients', []):
        addr = r.get('emailAddress', {}).get('address')
        if addr:
            recipients.append(addr)

    return recipients


def _extract_body_content(body: Dict) -> str:
    """Extract body content, stripping HTML if needed.

    Args:
        body: The 'body' field from Graph API

    Returns:
        Plain text content
    """
    content = body.get('content', '')
    content_type = body.get('contentType', 'text')

    if content_type.lower() == 'html':
        # Basic HTML stripping - remove tags
        import re
        # Remove script and style elements
        content = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', content, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', ' ', content)
        # Decode common HTML entities
        content = content.replace('&nbsp;', ' ')
        content = content.replace('&amp;', '&')
        content = content.replace('&lt;', '<')
        content = content.replace('&gt;', '>')
        content = content.replace('&quot;', '"')
        # Normalize whitespace
        content = re.sub(r'\s+', ' ', content).strip()

    return content


def create_draft(to: str, subject: str, body: str, cc: str = None) -> Dict:
    """Create a draft email in Outlook.

    This function creates a DRAFT email only - it does NOT send.
    The draft will appear in the user's Drafts folder.

    Args:
        to: Recipient email address (comma-separated for multiple)
        subject: Email subject line
        body: Email body content (plain text)
        cc: CC recipient email address (optional, comma-separated for multiple)

    Returns:
        Dict with:
            - success: bool
            - draft_id: str (Graph API message ID if successful)
            - error: str (if not successful)
    """
    client = MicrosoftGraphClient()

    # Check if configured
    if not client.is_configured():
        return {
            'success': False,
            'error': 'Microsoft Graph not configured. Run: python microsoft_graph.py configure CLIENT_ID SECRET'
        }

    # Check if authenticated
    if not client.is_authenticated():
        return {
            'success': False,
            'error': 'Not authenticated. Run: python microsoft_graph.py auth-url, then authenticate'
        }

    try:
        # Parse recipients (comma-separated)
        to_recipients = []
        for addr in to.split(','):
            addr = addr.strip()
            if addr:
                to_recipients.append({
                    "emailAddress": {"address": addr}
                })

        if not to_recipients:
            return {
                'success': False,
                'error': 'At least one recipient is required'
            }

        # Build the draft message payload
        message_data = {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": body
            },
            "toRecipients": to_recipients
        }

        # Add CC recipients if provided
        if cc:
            cc_recipients = []
            for addr in cc.split(','):
                addr = addr.strip()
                if addr:
                    cc_recipients.append({
                        "emailAddress": {"address": addr}
                    })
            if cc_recipients:
                message_data["ccRecipients"] = cc_recipients

        # Create draft via Graph API
        # POST /me/messages creates a draft (not sent)
        response = client.api_request('POST', '/me/messages', data=message_data)

        return {
            'success': True,
            'draft_id': response.get('id'),
            'web_link': response.get('webLink', ''),
            'subject': subject,
            'to': to
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# CLI Interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Email Processor for PCP - Outlook integration")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch new emails from Outlook")
    fetch_parser.add_argument("--limit", type=int, default=50, help="Maximum emails to fetch (default: 50)")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search emails by subject, sender, or content")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--days", "-d", type=int, help="Limit to last N days")

    # List command
    list_parser = subparsers.add_parser("list", help="List recent emails")
    list_parser.add_argument("--days", "-d", type=int, default=7, help="Number of days to look back (default: 7)")
    list_parser.add_argument("--limit", "-l", type=int, default=50, help="Maximum emails to show (default: 50)")
    list_parser.add_argument("--actionable", "-a", action="store_true", help="Show only actionable emails")

    # Get command
    get_parser = subparsers.add_parser("get", help="Get full email by ID")
    get_parser.add_argument("id", type=int, help="Email ID")

    # Draft command
    draft_parser = subparsers.add_parser("draft", help="Create a draft email (does NOT send)")
    draft_parser.add_argument("--to", required=True, help="Recipient email (comma-separated for multiple)")
    draft_parser.add_argument("--subject", required=True, help="Email subject")
    draft_parser.add_argument("--body", required=True, help="Email body (plain text)")
    draft_parser.add_argument("--cc", help="CC recipients (comma-separated for multiple)")

    args = parser.parse_args()

    if args.command == "fetch":
        result = fetch_new_emails(limit=args.limit)

        if result['success']:
            stored = result.get('stored', 0)
            skipped = result.get('skipped', 0)
            print(f"Fetched {result['fetched']} emails ({stored} stored, {skipped} skipped)")
            for email in result.get('emails', []):
                subject = email['subject'][:50] + '...' if len(email['subject']) > 50 else email['subject']
                status = "[NEW]" if email.get('id') else "[DUP]"
                print(f"  {status} {email['received_at'][:10]} | {email['sender'][:30]} | {subject}")
        else:
            print(f"Error: {result['error']}")

    elif args.command == "search":
        results = search_emails(args.query, days=args.days)
        if results:
            print(f"Found {len(results)} emails matching '{args.query}':")
            for email in results:
                subject = email['subject'][:50] + '...' if len(email['subject']) > 50 else email['subject']
                actionable = "[!]" if email.get('is_actionable') else "   "
                received = email.get('received_at', '')[:10]
                sender = email.get('sender', '')[:30]
                print(f"  {actionable} [{email['id']:4}] {received} | {sender} | {subject}")
        else:
            print(f"No emails found matching '{args.query}'")

    elif args.command == "list":
        if args.actionable:
            results = get_actionable_emails()
            label = "actionable emails"
        else:
            results = list_emails(days=args.days, limit=args.limit)
            label = f"emails from last {args.days} days"

        if results:
            print(f"{len(results)} {label}:")
            for email in results:
                subject = email['subject'][:50] + '...' if len(email['subject']) > 50 else email['subject']
                actionable = "[!]" if email.get('is_actionable') else "   "
                received = email.get('received_at', '')[:10]
                sender = email.get('sender', '')[:30]
                print(f"  {actionable} [{email['id']:4}] {received} | {sender} | {subject}")
        else:
            print(f"No {label}")

    elif args.command == "get":
        email = get_email(args.id)
        if email:
            print(f"Email #{email['id']}")
            print(f"Subject: {email['subject']}")
            print(f"From: {email['sender']}")
            print(f"To: {', '.join(email.get('recipients', []))}")
            print(f"Received: {email['received_at']}")
            print(f"Actionable: {'Yes' if email.get('is_actionable') else 'No'}")
            if email.get('action_taken'):
                print(f"Action Taken: {email['action_taken']}")
            print("-" * 60)
            print(email.get('body_full', email.get('body_preview', '(No content)')))
        else:
            print(f"Email #{args.id} not found")

    elif args.command == "draft":
        result = create_draft(
            to=args.to,
            subject=args.subject,
            body=args.body,
            cc=args.cc
        )
        if result['success']:
            print("Draft created successfully!")
            print(f"  To: {result['to']}")
            print(f"  Subject: {result['subject']}")
            print(f"  Draft ID: {result['draft_id'][:20]}..." if result.get('draft_id') else "")
            if result.get('web_link'):
                print(f"  View in Outlook: {result['web_link']}")
            print("\nNOTE: This is a DRAFT - it has NOT been sent.")
        else:
            print(f"Error creating draft: {result['error']}")

    else:
        parser.print_help()
