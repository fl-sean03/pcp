#!/usr/bin/env python3
"""
PCP Vault v2 - Smart capture with entity extraction and semantic understanding.
"""

import sqlite3
import json
import subprocess
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("PCP_DEBUG") else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("pcp.vault")

# Import pattern suggestions for approval workflow
from patterns import get_suggested_tasks

# Import embeddings for semantic search (optional - graceful fallback)
try:
    from embeddings import store_embedding, search_similar, hybrid_search, get_embedding_stats
    EMBEDDINGS_AVAILABLE = True
except ImportError as e:
    EMBEDDINGS_AVAILABLE = False
    store_embedding = None
    search_similar = None
    hybrid_search = None
    get_embedding_stats = None
    logger.info("Embeddings module not available (ChromaDB may not be installed): %s", e)

# Import proactive intelligence (optional - graceful fallback)
try:
    from proactive import get_proactive_insights, format_insights_for_response, get_attention_items
    PROACTIVE_AVAILABLE = True
except ImportError as e:
    PROACTIVE_AVAILABLE = False
    get_proactive_insights = None
    format_insights_for_response = None
    get_attention_items = None
    logger.info("Proactive module not available: %s", e)

# Default container path, with fallback for local development
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)):
    VAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "vault", "vault.db")


# ============================================================================
# Data Storage Functions (Agentic Pattern - Claude extracts, PCP stores)
# ============================================================================

def store_capture(
    content: str,
    capture_type: str = "note",
    entities: Dict[str, Any] = None,
    temporal: Dict[str, Any] = None,
    source: str = "claude",
    source_id: str = None,
    context: str = None
) -> int:
    """
    Store a capture with pre-extracted data. No subprocess calls.

    This is the agentic pattern: Claude extracts entities/temporal during
    conversation and passes them here for storage.

    Args:
        content: The text content to capture
        capture_type: note|task|idea|decision|question (Claude determines this)
        entities: Pre-extracted entities dict with keys:
                  people, projects, topics, dates, action_items, sentiment
        temporal: Pre-extracted temporal dict with keys:
                  has_deadline, deadline_date, has_reminder, reminder_date
        source: Where this came from (discord, api, etc.)
        source_id: Optional source-specific ID
        context: Optional additional context

    Returns:
        capture_id: The ID of the created capture
    """
    entities = entities or {}
    temporal = temporal or {}

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Link to existing entities in database
    linked = link_to_existing_entities(entities, conn)

    # Store the capture
    cursor.execute("""
        INSERT INTO captures_v2 (
            content, content_type, capture_type,
            extracted_entities, temporal_refs,
            linked_people, linked_projects,
            source, source_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        content,
        "text",
        capture_type,
        json.dumps(entities),
        json.dumps(temporal),
        json.dumps(linked["people"]),
        json.dumps(linked["projects"]),
        source,
        source_id,
        datetime.now().isoformat()
    ))

    capture_id = cursor.lastrowid

    # Auto-create people if mentioned but not in DB
    for name in entities.get("people", []):
        cursor.execute("SELECT id FROM people WHERE name = ?", (name,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO people (name, mention_count, last_mentioned, created_at)
                VALUES (?, 1, ?, ?)
            """, (name, datetime.now().isoformat(), datetime.now().isoformat()))

    conn.commit()
    conn.close()

    # Update contact tracking for all linked people
    for person_id in linked["people"]:
        try:
            update_person_contact(person_id)
        except Exception:
            pass

    # Store embedding for semantic search (if available)
    if EMBEDDINGS_AVAILABLE and store_embedding:
        try:
            store_embedding(
                capture_id=capture_id,
                text=content,
                capture_type=capture_type,
                metadata={
                    "people": entities.get("people", []),
                    "projects": entities.get("projects", []),
                    "source": source
                }
            )
        except Exception as e:
            logger.debug("Embedding storage failed for capture %d: %s", capture_id, e)

    logger.debug("Stored capture %d (type=%s)", capture_id, capture_type)
    return capture_id


def store_task(
    content: str,
    due_date: str = None,
    reminder_at: str = None,
    priority: str = "normal",
    project_id: int = None,
    related_people: List[int] = None,
    related_captures: List[int] = None,
    context: str = None
) -> int:
    """
    Store a task. No subprocess calls - Claude determines all parameters.

    Args:
        content: Task description
        due_date: Optional due date (YYYY-MM-DD)
        reminder_at: Optional reminder datetime
        priority: low|normal|high|urgent
        project_id: Optional linked project
        related_people: Optional list of person IDs
        related_captures: Optional list of capture IDs
        context: Optional context/notes

    Returns:
        task_id: The ID of the created task
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tasks (
            content, due_date, reminder_at, priority,
            project_id, related_people, related_captures,
            context, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        content,
        due_date,
        reminder_at,
        priority,
        project_id,
        json.dumps(related_people or []),
        json.dumps(related_captures or []),
        context,
        datetime.now().isoformat()
    ))

    task_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.debug("Stored task %d: %s", task_id, content[:50])
    return task_id


# ============================================================================
# DEPRECATED: Entity Extraction (uses Claude subprocess - being phased out)
# These functions will be removed. Use store_capture() with pre-extracted data.
# ============================================================================

def extract_entities(text: str) -> Dict[str, Any]:
    """
    DEPRECATED: Extract people, projects, topics, dates, and intent from text.

    This function previously used Claude subprocess for extraction.
    In the agentic pattern, Claude extracts during conversation and passes
    pre-extracted data to store_capture().

    Now uses simple heuristics for backward compatibility.
    Use store_capture() with entities parameter for best results.
    """
    import re

    # Simple heuristic extraction for backward compatibility
    people = []
    projects = []
    topics = []
    dates = []
    intent = "note"

    # Extract capitalized names (simple heuristic)
    # Look for patterns like "John", "Sarah", "TestPerson", "John Smith"
    # Match: Capital + alphanumeric(s), optionally followed by another capitalized word
    name_pattern = r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b'
    potential_names = re.findall(name_pattern, text)
    # Filter out common words that are capitalized
    common_words = {'The', 'This', 'That', 'What', 'When', 'Where', 'How', 'Why',
                    'Need', 'Will', 'Can', 'Should', 'Must', 'May', 'Might',
                    'Meeting', 'Project', 'Task', 'Note', 'Idea', 'Decision',
                    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                    'Saturday', 'Sunday', 'January', 'February', 'March', 'April',
                    'May', 'June', 'July', 'August', 'September', 'October',
                    'November', 'December', 'API', 'Database', 'Server', 'TEST'}
    for name in potential_names:
        if name not in common_words and len(name) > 2:
            people.append(name)

    # Extract known project patterns
    project_keywords = ['MatterStack', 'PCP', 'Alpha-Trader', 'AgentOps', 'API']
    for kw in project_keywords:
        if kw.lower() in text.lower():
            projects.append(kw)

    # Extract date patterns
    date_patterns = [
        r'\b(tomorrow|today|yesterday)\b',
        r'\b(next\s+(?:week|month|year|Monday|Tuesday|Wednesday|Thursday|Friday))\b',
        r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?)\b',
        r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',
    ]
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        dates.extend(matches)

    # Detect intent
    text_lower = text.lower()
    if any(word in text_lower for word in ['need to', 'todo', 'task:', 'follow up', 'finish', 'complete', 'by tomorrow', 'by friday']):
        intent = "task"
    elif any(word in text_lower for word in ['decided', 'decision', 'we chose', 'going with']):
        intent = "decision"
    elif any(word in text_lower for word in ['maybe', 'idea:', 'what if', 'could we', 'should we']):
        intent = "idea"
    elif text.strip().endswith('?'):
        intent = "question"

    return {
        "intent": intent,
        "people": list(set(people)),
        "projects": list(set(projects)),
        "topics": topics,
        "dates": list(set(dates)),
        "action_items": [],
        "sentiment": "neutral"
    }


def parse_temporal(text: str) -> Dict[str, Any]:
    """
    DEPRECATED: Parse temporal references into concrete dates.

    This function previously used Claude subprocess for parsing.
    In the agentic pattern, Claude extracts temporal info during conversation
    and passes pre-extracted data to store_capture() or store_task().

    Now uses simple heuristics for backward compatibility.
    Use store_task() with due_date parameter for best results.
    """
    import re
    from datetime import datetime, timedelta

    text_lower = text.lower()
    has_deadline = False
    has_reminder = False
    deadline_date = None
    time_references = []

    # Deadline keywords
    deadline_patterns = [
        r'\bby\s+(tomorrow|today|friday|monday|tuesday|wednesday|thursday|saturday|sunday)\b',
        r'\b(due|deadline|finish|complete)\b.*\b(by|before|on)\b',
        r'\bby\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
        r'\b(need to|must|have to)\b.*\b(by|before)\b',
    ]
    for pattern in deadline_patterns:
        if re.search(pattern, text_lower):
            has_deadline = True
            break

    # Check for "tomorrow" specifically
    if 'tomorrow' in text_lower:
        has_deadline = True
        deadline_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        time_references.append('tomorrow')

    # Check for explicit dates
    date_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?', text_lower)
    if date_match:
        has_deadline = True
        time_references.append(date_match.group(0))

    # Reminder keywords
    reminder_patterns = [
        r'\bremind\s+(me|us)\b',
        r'\bdon\'t\s+forget\b',
        r'\bremember\s+to\b',
    ]
    for pattern in reminder_patterns:
        if re.search(pattern, text_lower):
            has_reminder = True
            break

    return {
        "has_deadline": has_deadline,
        "has_reminder": has_reminder,
        "deadline_date": deadline_date,
        "time_references": time_references
    }


def link_to_existing_entities(entities: Dict, conn: sqlite3.Connection) -> Dict[str, List[int]]:
    """Link extracted entity names to existing database records."""
    cursor = conn.cursor()
    linked = {"people": [], "projects": []}

    # Link people
    for name in entities.get("people", []):
        cursor.execute("""
            SELECT id FROM people
            WHERE name LIKE ? OR aliases LIKE ?
        """, (f"%{name}%", f"%{name}%"))
        row = cursor.fetchone()
        if row:
            linked["people"].append(row[0])
            # Update mention count
            cursor.execute("""
                UPDATE people SET mention_count = mention_count + 1, last_mentioned = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), row[0]))

    # Link projects
    for project in entities.get("projects", []):
        cursor.execute("""
            SELECT id, keywords FROM projects WHERE status = 'active'
        """)
        for row in cursor.fetchall():
            project_id, keywords = row
            if keywords and keywords.strip():
                try:
                    kw_list = json.loads(keywords)
                    if any(kw.lower() in project.lower() or project.lower() in kw.lower() for kw in kw_list):
                        linked["projects"].append(project_id)
                        break
                except json.JSONDecodeError:
                    # Invalid JSON in keywords, skip this project
                    pass

    conn.commit()
    return linked


# ============================================================================
# Smart Capture
# ============================================================================

def smart_capture(
    content: str,
    source: str = "discord",
    source_id: str = None,
    context: str = None,
    # Agentic pattern: Claude can provide pre-extracted data to avoid subprocess calls
    entities: Dict[str, Any] = None,
    temporal: Dict[str, Any] = None,
    capture_type: str = None
) -> Dict[str, Any]:
    """
    Capture content with entity extraction and linking.

    AGENTIC PATTERN: When entities/temporal/capture_type are provided by Claude,
    subprocess calls are skipped. Claude extracts during conversation.

    Args:
        content: Text to capture
        source: Source identifier
        source_id: Optional source-specific ID
        context: Optional context
        entities: Pre-extracted entities (skips subprocess if provided)
        temporal: Pre-extracted temporal refs (skips subprocess if provided)
        capture_type: Pre-determined type (skips extraction if provided)

    Returns:
        Dict with capture_id, task_id, type, entities, temporal, linked
    """
    # Agentic pattern: Use pre-extracted data if provided, else fall back to subprocess
    if entities is None:
        entities = extract_entities(content)
    if temporal is None:
        temporal = parse_temporal(content)
    if capture_type is None:
        capture_type = entities.get("intent", "note")

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Link to existing entities
    linked = link_to_existing_entities(entities, conn)

    # Store the capture
    cursor.execute("""
        INSERT INTO captures_v2 (
            content, content_type, capture_type,
            extracted_entities, temporal_refs,
            linked_people, linked_projects,
            source, source_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        content,
        "text",
        capture_type,
        json.dumps(entities),
        json.dumps(temporal),
        json.dumps(linked["people"]),
        json.dumps(linked["projects"]),
        source,
        source_id,
        datetime.now().isoformat()
    ))

    capture_id = cursor.lastrowid

    # Auto-create task if it's a task or has deadline
    if capture_type == "task" or temporal.get("has_deadline"):
        task_content = entities.get("action_items", [content])[0] if entities.get("action_items") else content

        due_date = temporal.get("deadline_date")
        reminder_date = temporal.get("reminder_date")

        cursor.execute("""
            INSERT INTO tasks (
                content, due_date, reminder_at,
                related_captures, related_people, project_id,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            task_content,
            due_date,
            reminder_date,
            json.dumps([capture_id]),
            json.dumps(linked["people"]),
            linked["projects"][0] if linked["projects"] else None,
            datetime.now().isoformat()
        ))

        task_id = cursor.lastrowid
    else:
        task_id = None

    # Auto-create decision record if it's a decision
    if capture_type == "decision":
        cursor.execute("""
            INSERT INTO decisions (content, capture_id, project_id, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            content,
            capture_id,
            linked["projects"][0] if linked["projects"] else None,
            datetime.now().isoformat()
        ))

    # Auto-create people if mentioned but not in DB
    for name in entities.get("people", []):
        cursor.execute("SELECT id FROM people WHERE name = ?", (name,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO people (name, mention_count, last_mentioned, created_at)
                VALUES (?, 1, ?, ?)
            """, (name, datetime.now().isoformat(), datetime.now().isoformat()))

    conn.commit()
    conn.close()

    # Update contact tracking for all linked people
    for person_id in linked["people"]:
        try:
            update_person_contact(person_id)
        except Exception:
            pass  # Don't fail capture if contact tracking fails

    # Store embedding for semantic search (if available)
    if EMBEDDINGS_AVAILABLE and store_embedding:
        try:
            store_embedding(
                capture_id=capture_id,
                text=content,
                capture_type=capture_type,
                metadata={
                    "people": entities.get("people", []),
                    "projects": entities.get("projects", []),
                    "source": source
                }
            )
        except Exception as e:
            # Don't fail capture if embedding storage fails
            logger.debug("Embedding storage failed for capture %d: %s", capture_id, e)

    return {
        "capture_id": capture_id,
        "task_id": task_id,
        "type": capture_type,
        "entities": entities,
        "temporal": temporal,
        "linked": linked
    }


def format_capture_confirmation(result: Dict[str, Any]) -> str:
    """
    Generate a natural language confirmation from a capture result.

    Args:
        result: Output from smart_capture()

    Returns:
        Human-readable confirmation string
    """
    parts = []

    # Main capture type
    capture_type = result.get("type", "note")
    type_phrases = {
        "note": "Noted",
        "task": "Got it - captured as task",
        "idea": "Captured your idea",
        "decision": "Recorded your decision",
        "question": "Got your question",
        "chat": "Got it"
    }
    parts.append(type_phrases.get(capture_type, "Captured"))

    # Entities extracted
    entities = result.get("entities", {})
    people = entities.get("people", [])
    projects = entities.get("projects", [])

    if people and projects:
        parts.append(f"linked to {', '.join(people[:2])} and {projects[0]}")
    elif people:
        parts.append(f"linked to {', '.join(people[:2])}")
    elif projects:
        parts.append(f"linked to {projects[0]}")

    # Task created
    if result.get("task_id"):
        temporal = result.get("temporal", {})
        if temporal.get("deadline_date"):
            parts.append(f"task created, due {temporal['deadline_date']}")
        else:
            parts.append("task created")

    # Build final message
    if len(parts) == 1:
        return parts[0] + "."
    else:
        return parts[0] + " - " + ", ".join(parts[1:]) + "."


def format_brain_dump_confirmation(result: Dict[str, Any]) -> str:
    """
    Generate a natural language confirmation from a brain dump result.

    Args:
        result: Output from brain_dump()

    Returns:
        Human-readable confirmation string
    """
    parts = []

    # Count by type
    task_count = len(result.get("task_ids", []))
    capture_count = len(result.get("capture_ids", []))
    knowledge_count = len(result.get("knowledge_ids", []))
    decision_count = len(result.get("decision_ids", []))

    if task_count:
        parts.append(f"{task_count} task{'s' if task_count > 1 else ''}")
    if capture_count:
        parts.append(f"{capture_count} note{'s' if capture_count > 1 else ''}")
    if knowledge_count:
        parts.append(f"{knowledge_count} fact{'s' if knowledge_count > 1 else ''}")
    if decision_count:
        parts.append(f"{decision_count} decision{'s' if decision_count > 1 else ''}")

    if not parts:
        return "Processed your brain dump."

    return f"Got it - captured {', '.join(parts)}."


def get_capture_response_with_insights(
    capture_result: Dict[str, Any],
    include_insights: bool = True
) -> str:
    """
    Generate a complete capture response with optional proactive insights.

    This is the recommended function to use for generating user-facing
    responses after captures, as it combines the confirmation with
    any relevant proactive insights.

    Args:
        capture_result: Output from smart_capture()
        include_insights: Whether to include proactive insights (default True)

    Returns:
        Complete response string with confirmation and insights
    """
    # Get basic confirmation
    response = format_capture_confirmation(capture_result)

    # Add proactive insights if available and requested
    if include_insights and PROACTIVE_AVAILABLE and get_proactive_insights:
        try:
            # Pass context from the capture for relevance
            context = {
                'entities': capture_result.get('entities', {}),
                'type': capture_result.get('type'),
                'linked': capture_result.get('linked', {})
            }
            insights = get_proactive_insights(context)

            # Only include top 2 insights to avoid overwhelming
            if insights:
                formatted = format_insights_for_response(insights[:2])
                response += formatted
        except Exception as e:
            # Don't fail if proactive insights fail
            logger.debug("Proactive insights generation failed: %s", e)

    return response


def format_attachment_confirmation(result: Dict[str, Any]) -> str:
    """
    Generate a natural language confirmation from attachment processing result.

    Args:
        result: Output from process_discord_attachments()

    Returns:
        Human-readable confirmation string
    """
    processed = result.get("processed", [])
    if not processed:
        return "No attachments were found to process."

    parts = []
    for item in processed:
        file_name = item.get("file_name", "file")
        summary = item.get("summary", "")
        if summary:
            parts.append(f"{file_name}: {summary[:100]}")
        else:
            parts.append(file_name)

    if len(processed) == 1:
        return f"Processed attachment: {parts[0]}"
    else:
        return f"Processed {len(processed)} attachments:\n- " + "\n- ".join(parts)


# ============================================================================
# Discord Attachment Processing
# ============================================================================

def process_discord_attachments(
    message: str,
    context: str = ""
) -> Dict[str, Any]:
    """
    Process Discord attachments embedded in a message.

    Discord messages may contain [ATTACHMENTS: [...]] with file info.
    This function extracts and processes each attachment using file_processor.

    Args:
        message: Full message content (may contain [ATTACHMENTS: ...])
        context: Additional context for processing

    Returns:
        Dict with:
        {
            "processed": [
                {
                    "capture_id": int,
                    "file_name": str,
                    "file_path": str,
                    "content_type": str,
                    "summary": str
                },
                ...
            ],
            "message_text": str,  # Message without attachment metadata
            "attachment_count": int
        }
    """
    import re

    result = {
        "processed": [],
        "message_text": message,
        "attachment_count": 0
    }

    # Look for attachment metadata in message
    # Format: [ATTACHMENTS: [{"filename": "...", "path": "...", ...}]]
    attachment_pattern = r'\[ATTACHMENTS:\s*(\[.+?\])\]'
    match = re.search(attachment_pattern, message, re.DOTALL)

    if not match:
        return result

    try:
        attachments = json.loads(match.group(1))
    except json.JSONDecodeError:
        return result

    # Remove attachment metadata from message text
    result["message_text"] = re.sub(attachment_pattern, '', message).strip()
    result["attachment_count"] = len(attachments)

    # Process each attachment
    for att in attachments:
        file_path = att.get("path")
        filename = att.get("filename", "unknown")
        content_type = att.get("content_type", "application/octet-stream")

        if not file_path:
            continue

        # Check if file exists
        if not os.path.exists(file_path):
            result["processed"].append({
                "capture_id": -1,
                "file_name": filename,
                "file_path": file_path,
                "content_type": content_type,
                "summary": "File not found",
                "error": True
            })
            continue

        try:
            # Import and use file_processor
            from file_processor import ingest_file, process_file

            # Process file to get summary
            file_info = process_file(
                file_path,
                original_name=filename,
                source="discord",
                context=context
            )

            # Ingest file to database
            capture_id = ingest_file(
                file_path,
                original_name=filename,
                source="discord",
                context=context
            )

            result["processed"].append({
                "capture_id": capture_id,
                "file_name": filename,
                "file_path": file_info.get("file_path", file_path),
                "content_type": content_type,
                "summary": file_info.get("summary", ""),
                "extracted_text": file_info.get("extracted_text", "")[:500] if file_info.get("extracted_text") else "",
                "entities": file_info.get("entities", {})
            })
        except Exception as e:
            result["processed"].append({
                "capture_id": -1,
                "file_name": filename,
                "file_path": file_path,
                "content_type": content_type,
                "summary": f"Error processing: {str(e)}",
                "error": True
            })

    return result


def smart_capture_with_attachments(
    content: str,
    source: str = "discord",
    source_id: str = None,
    context: str = None
) -> Dict[str, Any]:
    """
    Smart capture that also handles embedded attachments.

    This is the recommended entry point for Discord messages that may contain
    both text and attachments.

    Args:
        content: Message content (may include [ATTACHMENTS: ...])
        source: Source of the capture
        source_id: Source-specific ID
        context: Additional context

    Returns:
        Combined result from text capture and attachment processing
    """
    # Process any attachments first
    attachment_result = process_discord_attachments(content, context=context or "")

    # Get clean message text (without attachment metadata)
    clean_text = attachment_result.get("message_text", content)

    # Capture the text portion if there's meaningful content
    text_result = None
    if clean_text and clean_text.strip():
        text_result = smart_capture(
            clean_text,
            source=source,
            source_id=source_id,
            context=context
        )

    return {
        "text_capture": text_result,
        "attachments": attachment_result,
        "has_text": bool(text_result),
        "has_attachments": attachment_result["attachment_count"] > 0
    }


# ============================================================================
# Brain Dump Parser
# ============================================================================

def parse_brain_dump(text: str) -> Dict[str, Any]:
    """
    DEPRECATED: Parse a brain dump using Claude subprocess.

    In the agentic pattern, Claude (the conversational agent) should parse
    the brain dump during conversation and pass the parsed items directly
    to store_brain_dump_items().

    Now uses simple heuristics for backward compatibility.

    Expected items structure for store_brain_dump_items():
    {
        "items": [
            {
                "type": "task|note|idea|fact|decision",
                "content": "...",
                "context": "...",
                "people": ["..."],
                "projects": ["..."],
                "priority": "normal",
                "deadline": null,
                "group": null
            }
        ],
        "summary": "Brief description"
    }
    """
    import re

    items = []

    # Split by bullet points, numbers, or newlines
    lines = re.split(r'\n\s*[-•*]\s*|\n\s*\d+[.)]\s*|\n{2,}', text)

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Remove leading bullet/number if still present
        line = re.sub(r'^[-•*]\s*|\d+[.)]\s*', '', line).strip()
        if not line:
            continue

        line_lower = line.lower()

        # Determine type based on content
        item_type = "note"
        if any(word in line_lower for word in ['need to', 'todo', 'email', 'send', 'call', 'follow up', 'finish', 'complete', 'schedule', 'submit', 'buy', 'fix']):
            item_type = "task"
        elif any(word in line_lower for word in ['decided', 'we chose', 'going with', 'decision:', 'agreed']):
            item_type = "decision"
        elif any(word in line_lower for word in ['maybe', 'idea:', 'what if', 'could try', 'might', 'should look into', 'explore']):
            item_type = "idea"
        elif any(word in line_lower for word in ['remember that', 'always', 'prefers', 'uses', 'fact:']):
            item_type = "fact"

        # Extract people mentioned
        entities = extract_entities(line)
        people = entities.get("people", [])

        items.append({
            "type": item_type,
            "content": line,
            "context": "",
            "people": people,
            "projects": entities.get("projects", []),
            "priority": "normal",
            "deadline": None,
            "group": None
        })

    # If no items parsed, return original text as single note
    if not items:
        items = [{
            "type": "note",
            "content": text,
            "context": "",
            "people": [],
            "projects": [],
            "priority": "normal",
            "deadline": None,
            "group": None
        }]

    return {
        "items": items,
        "summary": f"Parsed {len(items)} items from brain dump"
    }


def store_brain_dump_items(
    parsed_result: Dict[str, Any],
    source_text: str,
    source: str = "discord"
) -> Dict[str, Any]:
    """
    Store items from a parsed brain dump. Handles mixed types:
    - tasks → tasks table
    - notes/ideas → captures_v2 table
    - facts → knowledge table
    - decisions → decisions table

    Args:
        parsed_result: Output from parse_brain_dump()
        source_text: Original brain dump text (for reference)
        source: Where this came from (discord, cli, etc.)

    Returns:
        Dict with created IDs by type and summary
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Count items by type for summary
    items = parsed_result.get("items", [])
    type_counts = {}
    for item in items:
        t = item.get("type", "note")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Create parent capture for the full brain dump
    cursor.execute("""
        INSERT INTO captures_v2 (
            content, content_type, capture_type,
            extracted_entities, source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        source_text,
        "text",
        "brain_dump",
        json.dumps({"item_counts": type_counts}),
        source,
        datetime.now().isoformat()
    ))
    parent_capture_id = cursor.lastrowid

    # Track created IDs
    created = {
        "task_ids": [],
        "capture_ids": [],
        "knowledge_ids": [],
        "decision_ids": []
    }

    for item_data in items:
        item_type = item_data.get("type", "note")

        # Find or create people
        linked_people = []
        for person_name in item_data.get("people", []):
            cursor.execute(
                "SELECT id FROM people WHERE name LIKE ?",
                (f"%{person_name}%",)
            )
            row = cursor.fetchone()
            if row:
                linked_people.append(row[0])
                cursor.execute("""
                    UPDATE people SET mention_count = mention_count + 1, last_mentioned = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), row[0]))
            else:
                cursor.execute("""
                    INSERT INTO people (name, mention_count, last_mentioned, created_at)
                    VALUES (?, 1, ?, ?)
                """, (person_name, datetime.now().isoformat(), datetime.now().isoformat()))
                linked_people.append(cursor.lastrowid)

        # Find project
        project_id = None
        for project_name in item_data.get("projects", []):
            cursor.execute("SELECT id FROM projects WHERE name LIKE ?", (f"%{project_name}%",))
            prow = cursor.fetchone()
            if prow:
                project_id = prow[0]
                break
            # Try keywords
            cursor.execute("SELECT id, keywords FROM projects WHERE status = 'active'")
            for row in cursor.fetchall():
                pid, keywords = row
                if keywords:
                    kw_list = json.loads(keywords)
                    if any(kw.lower() in project_name.lower() or project_name.lower() in kw.lower() for kw in kw_list):
                        project_id = pid
                        break
            if project_id:
                break

        # Build context JSON
        context_json = json.dumps({
            "source_text": item_data.get("context", ""),
            "background": item_data.get("context", ""),
            "group_tag": item_data.get("group"),
            "parsed_from_dump": parent_capture_id,
            "original_projects": item_data.get("projects", [])
        })

        # Store based on type
        if item_type == "task":
            priority_map = {"low": 1, "normal": 2, "high": 3, "urgent": 4}
            priority = priority_map.get(item_data.get("priority", "normal"), 2)

            cursor.execute("""
                INSERT INTO tasks (
                    content, context, priority, status, due_date,
                    related_captures, related_people, project_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_data.get("content", ""),
                context_json,
                priority,
                "pending",
                item_data.get("deadline"),
                json.dumps([parent_capture_id]),
                json.dumps(linked_people),
                project_id,
                datetime.now().isoformat()
            ))
            created["task_ids"].append(cursor.lastrowid)

        elif item_type == "fact":
            # Store as knowledge (directly, to avoid DB lock from external call)
            tags = item_data.get("people", []) if item_data.get("people") else None
            cursor.execute("""
                INSERT INTO knowledge (
                    content, category, project_id, confidence, source, tags, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_data.get("content", ""),
                "fact",
                project_id,
                1.0,
                f"brain_dump:{parent_capture_id}",
                json.dumps(tags) if tags else None,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            created["knowledge_ids"].append(cursor.lastrowid)

        elif item_type == "decision":
            cursor.execute("""
                INSERT INTO decisions (
                    content, context, project_id, capture_id, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                item_data.get("content", ""),
                item_data.get("context", ""),
                project_id,
                parent_capture_id,
                datetime.now().isoformat()
            ))
            created["decision_ids"].append(cursor.lastrowid)

        else:
            # note, idea, or anything else → capture
            cursor.execute("""
                INSERT INTO captures_v2 (
                    content, content_type, capture_type,
                    extracted_entities, linked_people, linked_projects,
                    source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_data.get("content", ""),
                "text",
                item_type,  # note, idea, etc.
                json.dumps({"context": item_data.get("context", ""), "group": item_data.get("group")}),
                json.dumps(linked_people),
                json.dumps([project_id] if project_id else []),
                source,
                datetime.now().isoformat()
            ))
            created["capture_ids"].append(cursor.lastrowid)

        # Update contact tracking for linked people
        for person_id in linked_people:
            try:
                cursor.execute("""
                    UPDATE people
                    SET last_contacted = ?,
                        interaction_count = COALESCE(interaction_count, 0) + 1,
                        first_contacted = COALESCE(first_contacted, ?)
                    WHERE id = ?
                """, (datetime.now().isoformat(), datetime.now().isoformat(), person_id))
            except Exception:
                pass

    conn.commit()
    conn.close()

    # Store embeddings for brain dump content (if available)
    if EMBEDDINGS_AVAILABLE and store_embedding:
        try:
            # Store embedding for the parent brain dump capture
            store_embedding(
                capture_id=parent_capture_id,
                text=source_text,
                capture_type="brain_dump",
                metadata={"item_counts": type_counts}
            )

            # Store embeddings for each capture (notes, ideas)
            # Re-query to get content for each capture_id
            conn2 = sqlite3.connect(VAULT_PATH)
            cursor2 = conn2.cursor()
            for cap_id in created["capture_ids"]:
                cursor2.execute(
                    "SELECT content, capture_type FROM captures_v2 WHERE id = ?",
                    (cap_id,)
                )
                row = cursor2.fetchone()
                if row and row[0]:
                    store_embedding(
                        capture_id=cap_id,
                        text=row[0],
                        capture_type=row[1] or "note"
                    )
            conn2.close()
        except Exception as e:
            # Don't fail brain dump if embedding storage fails
            logger.debug("Brain dump embedding storage failed: %s", e)

    # Build summary
    summary_parts = []
    if created["task_ids"]:
        summary_parts.append(f"{len(created['task_ids'])} tasks")
    if created["capture_ids"]:
        summary_parts.append(f"{len(created['capture_ids'])} captures")
    if created["knowledge_ids"]:
        summary_parts.append(f"{len(created['knowledge_ids'])} facts")
    if created["decision_ids"]:
        summary_parts.append(f"{len(created['decision_ids'])} decisions")

    return {
        "parent_capture_id": parent_capture_id,
        **created,
        "summary": parsed_result.get("summary", f"Created {', '.join(summary_parts)}")
    }


# Keep old name as alias for backwards compatibility
store_brain_dump_tasks = store_brain_dump_items


def brain_dump(text: str, source: str = "discord") -> Dict[str, Any]:
    """
    Complete brain dump processing: parse and store.

    This is the main entry point for brain dump processing.
    Handles ANY mix of content types (tasks, notes, ideas, facts, decisions).

    Args:
        text: Raw brain dump text (can be anything - tasks, ideas, notes, etc.)
        source: Where this came from

    Returns:
        Dict with full results including IDs by type and summary
    """
    # Parse the brain dump
    parsed = parse_brain_dump(text)

    # Store the results
    result = store_brain_dump_items(parsed, text, source)

    # Add the parsed items for reference
    result["parsed_items"] = parsed.get("items", [])

    return result


def get_task_with_context(task_id: int) -> Optional[Dict]:
    """
    Get a task with its full context for understanding.

    Returns task info plus:
    - Parsed context (background, group_tag, source)
    - Related captures content
    - Related people info
    - Project info

    Args:
        task_id: ID of the task

    Returns:
        Dict with full task context, or None if not found
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get task
    cursor.execute("""
        SELECT id, content, context, priority, status, due_date, reminder_at,
               related_captures, related_people, project_id, created_at, completed_at
        FROM tasks WHERE id = ?
    """, (task_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    task = {
        "id": row["id"],
        "content": row["content"],
        "priority": row["priority"],
        "status": row["status"],
        "due_date": row["due_date"],
        "reminder_at": row["reminder_at"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"]
    }

    # Parse context JSON
    context_raw = row["context"]
    if context_raw:
        try:
            task["context"] = json.loads(context_raw)
        except json.JSONDecodeError:
            task["context"] = {"raw": context_raw}
    else:
        task["context"] = {}

    # Get related captures
    related_captures = json.loads(row["related_captures"]) if row["related_captures"] else []
    task["related_captures"] = []
    for cap_id in related_captures:
        cursor.execute(
            "SELECT id, content, capture_type, created_at FROM captures_v2 WHERE id = ?",
            (cap_id,)
        )
        cap_row = cursor.fetchone()
        if cap_row:
            task["related_captures"].append({
                "id": cap_row["id"],
                "content": cap_row["content"][:200] if cap_row["content"] else "",
                "type": cap_row["capture_type"],
                "created_at": cap_row["created_at"]
            })

    # Get related people
    related_people = json.loads(row["related_people"]) if row["related_people"] else []
    task["related_people"] = []
    for person_id in related_people:
        cursor.execute(
            "SELECT id, name, organization, relationship FROM people WHERE id = ?",
            (person_id,)
        )
        person_row = cursor.fetchone()
        if person_row:
            task["related_people"].append({
                "id": person_row["id"],
                "name": person_row["name"],
                "organization": person_row["organization"],
                "relationship": person_row["relationship"]
            })

    # Get project info
    if row["project_id"]:
        cursor.execute(
            "SELECT id, name, description, status FROM projects WHERE id = ?",
            (row["project_id"],)
        )
        proj_row = cursor.fetchone()
        if proj_row:
            task["project"] = {
                "id": proj_row["id"],
                "name": proj_row["name"],
                "description": proj_row["description"],
                "status": proj_row["status"]
            }

    # Get other tasks in same group (if group_tag exists)
    group_tag = task["context"].get("group_tag") if task["context"] else None
    if group_tag:
        cursor.execute("""
            SELECT id, content, status, due_date
            FROM tasks
            WHERE context LIKE ? AND id != ?
        """, (f'%"group_tag": "{group_tag}"%', task_id))

        task["grouped_tasks"] = []
        for gt in cursor.fetchall():
            task["grouped_tasks"].append({
                "id": gt["id"],
                "content": gt["content"][:100] if gt["content"] else "",
                "status": gt["status"],
                "due_date": gt["due_date"]
            })

    conn.close()
    return task


def get_tasks_by_group(group_tag: str) -> List[Dict]:
    """
    Get all tasks with a specific group tag.

    Args:
        group_tag: The group tag to search for

    Returns:
        List of tasks with that group tag
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Search for tasks with this group tag in context
    cursor.execute("""
        SELECT id, content, context, priority, status, due_date, created_at
        FROM tasks
        WHERE context LIKE ?
        ORDER BY created_at ASC
    """, (f'%"group_tag": "{group_tag}"%',))

    tasks = []
    for row in cursor.fetchall():
        context = {}
        if row["context"]:
            try:
                context = json.loads(row["context"])
            except json.JSONDecodeError:
                pass

        tasks.append({
            "id": row["id"],
            "content": row["content"],
            "context": context,
            "priority": row["priority"],
            "status": row["status"],
            "due_date": row["due_date"],
            "created_at": row["created_at"]
        })

    conn.close()
    return tasks


# ============================================================================
# Smart Search
# ============================================================================

def smart_search(query: str, limit: int = 10) -> List[Dict]:
    """
    Intelligent search across all content.
    Combines keyword search with context awareness.
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    results = []

    # Search captures
    cursor.execute("""
        SELECT id, content, capture_type, extracted_entities, created_at
        FROM captures_v2
        WHERE content LIKE ? OR extracted_entities LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (f"%{query}%", f"%{query}%", limit))

    for row in cursor.fetchall():
        results.append({
            "type": "capture",
            "id": row[0],
            "content": row[1],
            "capture_type": row[2],
            "entities": json.loads(row[3]) if row[3] else {},
            "created_at": row[4]
        })

    # Search people
    cursor.execute("""
        SELECT id, name, context, last_mentioned
        FROM people
        WHERE name LIKE ? OR aliases LIKE ? OR context LIKE ?
        LIMIT 5
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))

    for row in cursor.fetchall():
        results.append({
            "type": "person",
            "id": row[0],
            "name": row[1],
            "context": row[2],
            "last_mentioned": row[3]
        })

    # Search projects
    cursor.execute("""
        SELECT id, name, description, status
        FROM projects
        WHERE name LIKE ? OR description LIKE ? OR keywords LIKE ?
        LIMIT 5
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))

    for row in cursor.fetchall():
        results.append({
            "type": "project",
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "status": row[3]
        })

    # Search files
    cursor.execute("""
        SELECT id, file_name, summary, extracted_text
        FROM captures_v2
        WHERE content_type IN ('image', 'file')
        AND (file_name LIKE ? OR summary LIKE ? OR extracted_text LIKE ?)
        LIMIT 5
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))

    for row in cursor.fetchall():
        results.append({
            "type": "file",
            "id": row[0],
            "file_name": row[1],
            "summary": row[2],
            "excerpt": row[3][:200] if row[3] else ""
        })

    conn.close()
    return results


def semantic_search(
    query: str,
    limit: int = 10,
    capture_types: Optional[List[str]] = None,
    include_hybrid: bool = True
) -> List[Dict[str, Any]]:
    """
    Search for similar captures using semantic similarity.

    Uses ChromaDB embeddings to find conceptually similar content,
    even if exact keywords don't match.

    Args:
        query: The search query
        limit: Maximum number of results
        capture_types: Optional filter by capture types (note, task, idea, decision)
        include_hybrid: If True, combines with keyword search for better recall

    Returns:
        List of matches with capture info and similarity scores

    Example:
        # Find captures about "making things faster" even if they use words like
        # "performance", "optimization", "speed up", etc.
        results = semantic_search("making things faster")
    """
    if not EMBEDDINGS_AVAILABLE:
        # Fall back to keyword search
        return smart_search(query, limit=limit)

    try:
        if include_hybrid and hybrid_search:
            # Use hybrid search for best results
            results = hybrid_search(query, limit=limit)
        elif search_similar:
            # Use pure semantic search
            results = search_similar(query, limit=limit, capture_types=capture_types)
        else:
            return smart_search(query, limit=limit)

        # Enrich results with full capture data
        enriched = []
        conn = sqlite3.connect(VAULT_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for r in results:
            capture_id = r.get('capture_id')
            if capture_id:
                cursor.execute("""
                    SELECT id, content, capture_type, created_at
                    FROM captures_v2 WHERE id = ?
                """, (capture_id,))
                row = cursor.fetchone()
                if row:
                    enriched.append({
                        "id": row['id'],
                        "content": row['content'],
                        "capture_type": row['capture_type'],
                        "created_at": row['created_at'],
                        "similarity": r.get('similarity', 0),
                        "match_type": "semantic" if r.get('has_semantic') else "keyword",
                        "combined_score": r.get('combined_score', 0)
                    })

        conn.close()
        return enriched
    except Exception as e:
        # Fall back to keyword search on error
        logger.debug("Semantic search failed, falling back to keyword search: %s", e)
        return smart_search(query, limit=limit)


# ============================================================================
# Task Management
# ============================================================================

def get_tasks(status: str = None, due_within_days: int = None) -> List[Dict]:
    """Get tasks with optional filters."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    query = "SELECT id, content, priority, status, due_date, project_id, created_at FROM tasks WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if due_within_days:
        future_date = (datetime.now() + timedelta(days=due_within_days)).strftime("%Y-%m-%d")
        query += " AND due_date <= ?"
        params.append(future_date)

    query += " ORDER BY due_date ASC NULLS LAST, priority DESC"

    cursor.execute(query, params)

    tasks = []
    for row in cursor.fetchall():
        tasks.append({
            "id": row[0],
            "content": row[1],
            "priority": row[2],
            "status": row[3],
            "due_date": row[4],
            "project_id": row[5],
            "created_at": row[6]
        })

    conn.close()
    return tasks


def complete_task(task_id: int) -> bool:
    """Mark a task as complete."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tasks SET status = 'done', completed_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), task_id))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# ============================================================================
# People & Projects
# ============================================================================

def get_person(name: str) -> Optional[Dict]:
    """Get person details by name."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, aliases, relationship, context, organization,
               mention_count, last_mentioned
        FROM people
        WHERE name LIKE ?
    """, (f"%{name}%",))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "name": row[1],
            "aliases": json.loads(row[2]) if row[2] else [],
            "relationship": row[3],
            "context": row[4],
            "organization": row[5],
            "mention_count": row[6],
            "last_mentioned": row[7]
        }
    return None


def add_person(name: str, relationship: str = None, context: str = None) -> int:
    """Add a new person to track."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO people (name, relationship, context, created_at)
        VALUES (?, ?, ?, ?)
    """, (name, relationship, context, datetime.now().isoformat()))

    person_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return person_id


def get_project(name: str) -> Optional[Dict]:
    """Get project details by name."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, description, status, keywords, capture_count, last_activity
        FROM projects
        WHERE name LIKE ?
    """, (f"%{name}%",))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "status": row[3],
            "keywords": json.loads(row[4]) if row[4] else [],
            "capture_count": row[5],
            "last_activity": row[6]
        }
    return None


# ============================================================================
# Relationship Tracking
# ============================================================================

def update_person_contact(person_id: int) -> bool:
    """
    Update last_contacted and interaction_count for a person.
    Called when there's an interaction (capture, email, etc.).
    Returns True if updated, False if person not found.
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Check if person exists
    cursor.execute("SELECT id FROM people WHERE id = ?", (person_id,))
    if not cursor.fetchone():
        conn.close()
        return False

    now = datetime.now().isoformat()

    # Update last_contacted and increment interaction_count
    # Also set first_contacted if NULL (first time tracking)
    cursor.execute("""
        UPDATE people
        SET last_contacted = ?,
            interaction_count = COALESCE(interaction_count, 0) + 1,
            first_contacted = COALESCE(first_contacted, ?)
        WHERE id = ?
    """, (now, now, person_id))

    conn.commit()
    conn.close()
    return True


def get_relationship_summary(person_id: int) -> Optional[Dict]:
    """
    Get a comprehensive relationship summary for a person.
    Includes contact history, shared projects, recent captures.
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get person details
    cursor.execute("""
        SELECT id, name, aliases, relationship, context, organization,
               mention_count, last_mentioned, last_contacted, interaction_count,
               first_contacted, shared_projects, relationship_notes
        FROM people WHERE id = ?
    """, (person_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    person = {
        "id": row["id"],
        "name": row["name"],
        "aliases": json.loads(row["aliases"]) if row["aliases"] else [],
        "relationship": row["relationship"],
        "context": row["context"],
        "organization": row["organization"],
        "mention_count": row["mention_count"] or 0,
        "last_mentioned": row["last_mentioned"],
        "last_contacted": row["last_contacted"],
        "interaction_count": row["interaction_count"] or 0,
        "first_contacted": row["first_contacted"],
        "shared_projects": json.loads(row["shared_projects"]) if row["shared_projects"] else [],
        "relationship_notes": row["relationship_notes"]
    }

    # Calculate days since last contact
    if person["last_contacted"]:
        last_contact_date = datetime.fromisoformat(person["last_contacted"])
        days_since_contact = (datetime.now() - last_contact_date).days
        person["days_since_contact"] = days_since_contact
    else:
        person["days_since_contact"] = None

    # Get recent captures mentioning this person
    cursor.execute("""
        SELECT id, content, capture_type, created_at
        FROM captures_v2
        WHERE linked_people LIKE ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (f'%{person_id}%',))

    person["recent_captures"] = []
    for cap in cursor.fetchall():
        person["recent_captures"].append({
            "id": cap["id"],
            "content": cap["content"][:100] if cap["content"] else "",
            "type": cap["capture_type"],
            "created_at": cap["created_at"]
        })

    conn.close()
    return person


def get_stale_relationships(days: int = 14) -> List[Dict]:
    """
    Get people who haven't been contacted in the specified number of days.
    Returns list of people sorted by staleness (most stale first).
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    # Find people with last_contacted before cutoff OR never contacted but mentioned
    cursor.execute("""
        SELECT id, name, relationship, organization, last_contacted,
               last_mentioned, interaction_count, mention_count
        FROM people
        WHERE (last_contacted IS NOT NULL AND last_contacted < ?)
           OR (last_contacted IS NULL AND last_mentioned IS NOT NULL)
        ORDER BY
            CASE WHEN last_contacted IS NULL THEN 1 ELSE 0 END,
            last_contacted ASC
    """, (cutoff_date,))

    stale = []
    for row in cursor.fetchall():
        person = {
            "id": row["id"],
            "name": row["name"],
            "relationship": row["relationship"],
            "organization": row["organization"],
            "last_contacted": row["last_contacted"],
            "last_mentioned": row["last_mentioned"],
            "interaction_count": row["interaction_count"] or 0,
            "mention_count": row["mention_count"] or 0
        }

        # Calculate days since contact
        if row["last_contacted"]:
            last_date = datetime.fromisoformat(row["last_contacted"])
            person["days_since_contact"] = (datetime.now() - last_date).days
        else:
            # Never contacted - use last mentioned or mark as "never"
            person["days_since_contact"] = None
            person["status"] = "never_contacted"

        stale.append(person)

    conn.close()
    return stale


# ============================================================================
# Project Health
# ============================================================================

def get_project_activity(project_id: int, days: int = 30) -> List[Dict]:
    """
    Get captures linked to a project within the specified timeframe.
    Returns list of captures sorted by recency.
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if project exists
    cursor.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not cursor.fetchone():
        conn.close()
        return []

    # Get captures linked to this project within timeframe
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT id, content, capture_type, created_at, extracted_entities
        FROM captures_v2
        WHERE linked_projects LIKE ?
          AND created_at > ?
        ORDER BY created_at DESC
    """, (f'%{project_id}%', cutoff_date))

    captures = []
    for row in cursor.fetchall():
        captures.append({
            "id": row["id"],
            "content": row["content"][:200] if row["content"] else "",
            "type": row["capture_type"],
            "created_at": row["created_at"],
            "entities": json.loads(row["extracted_entities"]) if row["extracted_entities"] else {}
        })

    conn.close()
    return captures


def get_project_health(project_id: int) -> Optional[Dict]:
    """
    Get health metrics for a project.
    Includes activity levels, task status, and staleness indicator.
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get project details
    cursor.execute("""
        SELECT id, name, description, status, keywords, capture_count, last_activity, created_at
        FROM projects WHERE id = ?
    """, (project_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    project = {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
        "capture_count": row["capture_count"] or 0,
        "last_activity": row["last_activity"],
        "created_at": row["created_at"]
    }

    # Calculate days since last activity
    if project["last_activity"]:
        last_date = datetime.fromisoformat(project["last_activity"])
        project["days_since_activity"] = (datetime.now() - last_date).days
    else:
        project["days_since_activity"] = None

    # Get capture counts for different timeframes
    for days, label in [(7, "week"), (30, "month"), (90, "quarter")]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM captures_v2
            WHERE linked_projects LIKE ? AND created_at > ?
        """, (f'%{project_id}%', cutoff))
        project[f"captures_{label}"] = cursor.fetchone()[0]

    # Get task counts
    cursor.execute("""
        SELECT status, COUNT(*) FROM tasks
        WHERE project_id = ?
        GROUP BY status
    """, (project_id,))
    project["tasks_by_status"] = dict(cursor.fetchall())

    # Get pending task count specifically
    cursor.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE project_id = ? AND status = 'pending'
    """, (project_id,))
    project["pending_tasks"] = cursor.fetchone()[0]

    # Get overdue task count
    cursor.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE project_id = ? AND status = 'pending'
          AND due_date IS NOT NULL AND due_date < date('now')
    """, (project_id,))
    project["overdue_tasks"] = cursor.fetchone()[0]

    # Determine health status
    days_inactive = project.get("days_since_activity")
    if project["status"] != "active":
        project["health"] = "inactive"
    elif days_inactive is None or days_inactive > 30:
        project["health"] = "stalled"
    elif days_inactive > 14:
        project["health"] = "needs_attention"
    elif project["overdue_tasks"] > 0:
        project["health"] = "has_overdue"
    else:
        project["health"] = "healthy"

    conn.close()
    return project


def get_project_context(project_id: int) -> Optional[Dict]:
    """
    Get comprehensive context for a project to help restore working memory.
    Returns structured data including recent activity, key decisions,
    related people, pending tasks, and knowledge items.

    Args:
        project_id: ID of the project

    Returns:
        Dict with structured project context, or None if project not found:
        {
            'project': {...},              # Basic project info
            'health': {...},               # Health metrics
            'recent_captures': [...],      # Last 10 captures
            'key_decisions': [...],        # Recent decisions
            'pending_tasks': [...],        # Pending tasks
            'related_people': [...],       # People linked to captures
            'knowledge': [...],            # Knowledge items for this project
        }
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get project details
    cursor.execute("""
        SELECT id, name, description, status, keywords, capture_count,
               last_activity, created_at
        FROM projects WHERE id = ?
    """, (project_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    context = {
        'project': {
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'status': row['status'],
            'keywords': json.loads(row['keywords']) if row['keywords'] else [],
            'capture_count': row['capture_count'] or 0,
            'last_activity': row['last_activity'],
            'created_at': row['created_at']
        }
    }

    # Get health metrics (reusing existing function logic)
    health = get_project_health(project_id)
    if health:
        context['health'] = {
            'status': health.get('health', 'unknown'),
            'days_since_activity': health.get('days_since_activity'),
            'captures_week': health.get('captures_week', 0),
            'captures_month': health.get('captures_month', 0),
            'pending_tasks': health.get('pending_tasks', 0),
            'overdue_tasks': health.get('overdue_tasks', 0)
        }

    # Get recent captures for this project (last 10)
    cursor.execute("""
        SELECT id, content, capture_type, extracted_entities, created_at
        FROM captures_v2
        WHERE linked_projects LIKE ?
        ORDER BY created_at DESC
        LIMIT 10
    """, (f'%{project_id}%',))

    context['recent_captures'] = []
    for cap in cursor.fetchall():
        entities = json.loads(cap['extracted_entities']) if cap['extracted_entities'] else {}
        context['recent_captures'].append({
            'id': cap['id'],
            'content': cap['content'][:200] if cap['content'] else '',
            'type': cap['capture_type'],
            'topics': entities.get('topics', []),
            'created_at': cap['created_at']
        })

    # Get key decisions for this project
    cursor.execute("""
        SELECT id, content, context, alternatives, created_at
        FROM decisions
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (project_id,))

    context['key_decisions'] = []
    for dec in cursor.fetchall():
        context['key_decisions'].append({
            'id': dec['id'],
            'content': dec['content'][:150] if dec['content'] else '',
            'context': dec['context'],
            'alternatives': dec['alternatives'],
            'created_at': dec['created_at']
        })

    # Get pending tasks for this project
    cursor.execute("""
        SELECT id, content, priority, status, due_date, created_at
        FROM tasks
        WHERE project_id = ? AND status = 'pending'
        ORDER BY due_date ASC NULLS LAST, priority DESC
        LIMIT 10
    """, (project_id,))

    context['pending_tasks'] = []
    for task in cursor.fetchall():
        context['pending_tasks'].append({
            'id': task['id'],
            'content': task['content'][:100] if task['content'] else '',
            'priority': task['priority'],
            'due_date': task['due_date'],
            'created_at': task['created_at']
        })

    # Get related people (from captures linked to this project)
    cursor.execute("""
        SELECT DISTINCT p.id, p.name, p.organization, p.relationship,
               p.last_contacted, p.interaction_count
        FROM people p
        INNER JOIN captures_v2 c ON c.linked_people LIKE '%' || p.id || '%'
        WHERE c.linked_projects LIKE ?
        ORDER BY p.last_contacted DESC NULLS LAST
        LIMIT 10
    """, (f'%{project_id}%',))

    context['related_people'] = []
    for person in cursor.fetchall():
        context['related_people'].append({
            'id': person['id'],
            'name': person['name'],
            'organization': person['organization'],
            'relationship': person['relationship'],
            'last_contacted': person['last_contacted'],
            'interaction_count': person['interaction_count'] or 0
        })

    # Get knowledge items for this project
    cursor.execute("""
        SELECT id, content, category, confidence, source, created_at
        FROM knowledge
        WHERE project_id = ?
        ORDER BY updated_at DESC
        LIMIT 10
    """, (project_id,))

    context['knowledge'] = []
    for k in cursor.fetchall():
        context['knowledge'].append({
            'id': k['id'],
            'content': k['content'][:150] if k['content'] else '',
            'category': k['category'],
            'confidence': k['confidence'],
            'source': k['source'],
            'created_at': k['created_at']
        })

    conn.close()
    return context


def restore_context(project_id: int) -> Optional[str]:
    """
    Generate a human-readable context restoration summary for a project.
    Designed to help quickly get back up to speed on a project.

    Args:
        project_id: ID of the project

    Returns:
        Human-readable string summary, or None if project not found
    """
    ctx = get_project_context(project_id)
    if not ctx:
        return None

    project = ctx['project']
    health = ctx.get('health', {})

    lines = []
    lines.append(f"# Context: {project['name']}")
    lines.append("")

    # Status and health
    status_str = f"Status: {project['status']}"
    if health:
        status_str += f" | Health: {health.get('status', 'unknown')}"
    lines.append(status_str)

    if project['description']:
        lines.append(f"Description: {project['description']}")
    lines.append("")

    # Activity summary
    if health:
        days = health.get('days_since_activity')
        if days is not None:
            lines.append(f"Last active: {days} days ago")
        else:
            lines.append("Last active: Never")
        lines.append(f"Activity: {health.get('captures_week', 0)} this week, {health.get('captures_month', 0)} this month")
        lines.append("")

    # Pending tasks
    if ctx['pending_tasks']:
        lines.append(f"## Pending Tasks ({len(ctx['pending_tasks'])})")
        for task in ctx['pending_tasks'][:5]:
            due = f" [due: {task['due_date']}]" if task['due_date'] else ""
            lines.append(f"- {task['content']}{due}")
        lines.append("")

    # Key decisions
    if ctx['key_decisions']:
        lines.append(f"## Key Decisions ({len(ctx['key_decisions'])})")
        for dec in ctx['key_decisions']:
            lines.append(f"- {dec['content']}")
        lines.append("")

    # Knowledge base
    if ctx['knowledge']:
        lines.append(f"## Knowledge ({len(ctx['knowledge'])})")
        for k in ctx['knowledge']:
            lines.append(f"- [{k['category']}] {k['content']}")
        lines.append("")

    # Related people
    if ctx['related_people']:
        lines.append(f"## Key People ({len(ctx['related_people'])})")
        for person in ctx['related_people'][:5]:
            org = f" ({person['organization']})" if person['organization'] else ""
            lines.append(f"- {person['name']}{org}")
        lines.append("")

    # Recent activity
    if ctx['recent_captures']:
        lines.append(f"## Recent Activity ({len(ctx['recent_captures'])} captures)")
        for cap in ctx['recent_captures'][:5]:
            date = cap['created_at'][:10] if cap['created_at'] else ''
            lines.append(f"- [{date}] {cap['content'][:60]}...")
        lines.append("")

    return "\n".join(lines)


def get_stalled_projects(days: int = 14) -> List[Dict]:
    """
    Get projects with no activity in the specified number of days.
    Only returns active projects (ignores archived/completed).
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    # Get active projects with no recent activity
    cursor.execute("""
        SELECT id, name, description, status, last_activity, capture_count
        FROM projects
        WHERE status = 'active'
          AND (last_activity IS NULL OR last_activity < ?)
        ORDER BY
            CASE WHEN last_activity IS NULL THEN 1 ELSE 0 END,
            last_activity ASC
    """, (cutoff_date,))

    stalled = []
    for row in cursor.fetchall():
        project = {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "status": row["status"],
            "last_activity": row["last_activity"],
            "capture_count": row["capture_count"] or 0
        }

        # Calculate days since activity
        if row["last_activity"]:
            last_date = datetime.fromisoformat(row["last_activity"])
            project["days_since_activity"] = (datetime.now() - last_date).days
        else:
            project["days_since_activity"] = None
            project["activity_status"] = "never_active"

        # Get pending task count for context
        cursor.execute("""
            SELECT COUNT(*) FROM tasks
            WHERE project_id = ? AND status = 'pending'
        """, (project["id"],))
        project["pending_tasks"] = cursor.fetchone()[0]

        stalled.append(project)

    conn.close()
    return stalled


# ============================================================================
# Unified Search
# ============================================================================

def unified_search(
    query: str,
    sources: Optional[List[str]] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search across all PCP data sources with consistent result format.

    Args:
        query: Search query string
        sources: Optional list of sources to search. Valid values:
                 'captures', 'knowledge', 'emails', 'tasks', 'semantic'
                 If None, searches all sources (including semantic if available).
        limit: Maximum results per source (default 10)

    Returns:
        List of search results with consistent format:
        {
            'source_type': 'captures'|'knowledge'|'emails'|'tasks'|'semantic',
            'id': int,
            'content': str (main content/text),
            'preview': str (short preview for display),
            'relevance': str (why it matched),
            'created_at': str (ISO timestamp),
            'metadata': dict (source-specific extra fields)
        }
    """
    valid_sources = ['captures', 'knowledge', 'emails', 'tasks', 'semantic']

    # Default to all sources if not specified
    if sources is None:
        sources = valid_sources
    else:
        # Validate sources
        sources = [s for s in sources if s in valid_sources]
        if not sources:
            sources = valid_sources

    results = []
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    search_pattern = f"%{query}%"

    # Search captures
    if 'captures' in sources:
        cursor.execute("""
            SELECT id, content, capture_type, extracted_entities, created_at,
                   linked_people, linked_projects
            FROM captures_v2
            WHERE content LIKE ? OR extracted_entities LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (search_pattern, search_pattern, limit))

        for row in cursor.fetchall():
            results.append({
                'source_type': 'captures',
                'id': row['id'],
                'content': row['content'] or '',
                'preview': (row['content'] or '')[:100],
                'relevance': f"capture ({row['capture_type']})",
                'created_at': row['created_at'],
                'metadata': {
                    'capture_type': row['capture_type'],
                    'entities': json.loads(row['extracted_entities']) if row['extracted_entities'] else {},
                    'linked_people': json.loads(row['linked_people']) if row['linked_people'] else [],
                    'linked_projects': json.loads(row['linked_projects']) if row['linked_projects'] else []
                }
            })

    # Search knowledge
    if 'knowledge' in sources:
        cursor.execute("""
            SELECT id, content, category, project_id, confidence, source, tags,
                   created_at, updated_at
            FROM knowledge
            WHERE content LIKE ? OR tags LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (search_pattern, search_pattern, limit))

        for row in cursor.fetchall():
            results.append({
                'source_type': 'knowledge',
                'id': row['id'],
                'content': row['content'] or '',
                'preview': (row['content'] or '')[:100],
                'relevance': f"knowledge ({row['category']})",
                'created_at': row['created_at'],
                'metadata': {
                    'category': row['category'],
                    'project_id': row['project_id'],
                    'confidence': row['confidence'],
                    'source': row['source'],
                    'tags': json.loads(row['tags']) if row['tags'] else [],
                    'updated_at': row['updated_at']
                }
            })

    # Search emails
    if 'emails' in sources:
        cursor.execute("""
            SELECT id, message_id, subject, sender, body_preview, body_full,
                   received_at, is_actionable, action_taken
            FROM emails
            WHERE subject LIKE ? OR sender LIKE ? OR body_preview LIKE ? OR body_full LIKE ?
            ORDER BY received_at DESC
            LIMIT ?
        """, (search_pattern, search_pattern, search_pattern, search_pattern, limit))

        for row in cursor.fetchall():
            # Use subject as content for display
            content = f"{row['subject']}: {row['body_preview'] or ''}"
            results.append({
                'source_type': 'emails',
                'id': row['id'],
                'content': content,
                'preview': f"{row['sender']}: {row['subject']}"[:100],
                'relevance': 'email' + (' (actionable)' if row['is_actionable'] else ''),
                'created_at': row['received_at'],
                'metadata': {
                    'message_id': row['message_id'],
                    'subject': row['subject'],
                    'sender': row['sender'],
                    'is_actionable': row['is_actionable'],
                    'action_taken': row['action_taken']
                }
            })

    # Search tasks
    if 'tasks' in sources:
        cursor.execute("""
            SELECT id, content, priority, status, due_date, project_id, created_at
            FROM tasks
            WHERE content LIKE ?
            ORDER BY
                CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
                due_date ASC NULLS LAST,
                created_at DESC
            LIMIT ?
        """, (search_pattern, limit))

        for row in cursor.fetchall():
            results.append({
                'source_type': 'tasks',
                'id': row['id'],
                'content': row['content'] or '',
                'preview': (row['content'] or '')[:100],
                'relevance': f"task ({row['status']})" + (f" due {row['due_date']}" if row['due_date'] else ''),
                'created_at': row['created_at'],
                'metadata': {
                    'priority': row['priority'],
                    'status': row['status'],
                    'due_date': row['due_date'],
                    'project_id': row['project_id']
                }
            })

    conn.close()

    # Search using semantic similarity (if available)
    if 'semantic' in sources and EMBEDDINGS_AVAILABLE and search_similar:
        try:
            semantic_results = search_similar(query, limit=limit)
            for sr in semantic_results:
                # Avoid duplicates - check if this capture_id is already in results
                capture_id = sr.get('capture_id')
                if capture_id and not any(
                    r['source_type'] == 'captures' and r['id'] == capture_id
                    for r in results
                ):
                    results.append({
                        'source_type': 'semantic',
                        'id': capture_id,
                        'content': sr.get('content_preview', ''),
                        'preview': sr.get('content_preview', '')[:100],
                        'relevance': f"semantic match ({sr.get('similarity', 0):.0%} similar)",
                        'created_at': sr.get('metadata', {}).get('created_at', ''),
                        'metadata': {
                            'similarity': sr.get('similarity', 0),
                            'capture_type': sr.get('capture_type', 'unknown'),
                            **sr.get('metadata', {})
                        }
                    })
        except Exception as e:
            # Don't fail search if semantic search fails
            logger.debug("Unified search semantic component failed: %s", e)

    # Sort results by created_at (most recent first) across all sources
    results.sort(key=lambda x: x.get('created_at') or '', reverse=True)

    return results


# ============================================================================
# Suggestion Approval
# ============================================================================

def approve_suggestion(suggestion_id: int, project_id: int = None) -> Optional[Dict]:
    """
    Approve a pattern-generated task suggestion and create an actual task.

    Args:
        suggestion_id: ID of the suggested_tasks entry
        project_id: Optional project ID to link the task to

    Returns:
        Dict with task_id and suggestion_id if successful, None if suggestion not found
    """
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get the suggestion
    cursor.execute("""
        SELECT id, content, reason, source_pattern, status
        FROM suggested_tasks
        WHERE id = ?
    """, (suggestion_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    # Check if already approved or dismissed
    if row["status"] != "pending":
        conn.close()
        return {
            "error": f"Suggestion already {row['status']}",
            "suggestion_id": suggestion_id,
            "task_id": None
        }

    # Create the task
    cursor.execute("""
        INSERT INTO tasks (content, context, project_id, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        row["content"],
        f"Generated from pattern: {row['source_pattern']}. Reason: {row['reason']}",
        project_id,
        datetime.now().isoformat()
    ))
    task_id = cursor.lastrowid

    # Update suggestion status to approved
    cursor.execute("""
        UPDATE suggested_tasks
        SET status = 'approved'
        WHERE id = ?
    """, (suggestion_id,))

    conn.commit()
    conn.close()

    return {
        "task_id": task_id,
        "suggestion_id": suggestion_id,
        "content": row["content"]
    }


def dismiss_suggestion(suggestion_id: int) -> bool:
    """
    Dismiss a suggested task (mark as not useful).

    Args:
        suggestion_id: ID of the suggested_tasks entry

    Returns:
        True if dismissed, False if not found or already processed
    """
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Check existence and status
    cursor.execute("""
        SELECT status FROM suggested_tasks WHERE id = ?
    """, (suggestion_id,))

    row = cursor.fetchone()
    if not row or row[0] != "pending":
        conn.close()
        return False

    # Update status
    cursor.execute("""
        UPDATE suggested_tasks
        SET status = 'dismissed'
        WHERE id = ?
    """, (suggestion_id,))

    conn.commit()
    conn.close()
    return True


# ============================================================================
# Statistics & Briefs
# ============================================================================

def get_stats() -> Dict[str, Any]:
    """Get comprehensive vault statistics."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    stats = {}

    # Capture stats
    cursor.execute("SELECT COUNT(*) FROM captures_v2")
    stats["total_captures"] = cursor.fetchone()[0]

    cursor.execute("SELECT capture_type, COUNT(*) FROM captures_v2 GROUP BY capture_type")
    stats["captures_by_type"] = dict(cursor.fetchall())

    cursor.execute("SELECT COUNT(*) FROM captures_v2 WHERE created_at > datetime('now', '-24 hours')")
    stats["captures_today"] = cursor.fetchone()[0]

    # Task stats
    cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
    stats["tasks_by_status"] = dict(cursor.fetchall())

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE due_date <= date('now') AND status = 'pending'")
    stats["overdue_tasks"] = cursor.fetchone()[0]

    # People stats
    cursor.execute("SELECT COUNT(*) FROM people")
    stats["total_people"] = cursor.fetchone()[0]

    # Project stats
    cursor.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")
    stats["active_projects"] = cursor.fetchone()[0]

    # File stats
    cursor.execute("SELECT COUNT(*) FROM captures_v2 WHERE content_type IN ('image', 'file')")
    stats["total_files"] = cursor.fetchone()[0]

    conn.close()
    return stats


def get_feature_status() -> Dict[str, Any]:
    """
    Get status of all PCP features and their availability.

    Returns dict showing which features are enabled and any relevant details.
    """
    status = {
        "timestamp": datetime.now().isoformat(),
        "features": {}
    }

    # Core features (always available)
    status["features"]["smart_capture"] = {"available": True, "status": "enabled"}
    status["features"]["brain_dump"] = {"available": True, "status": "enabled"}
    status["features"]["keyword_search"] = {"available": True, "status": "enabled"}
    status["features"]["tasks"] = {"available": True, "status": "enabled"}

    # Embeddings / Semantic Search
    status["features"]["semantic_search"] = {
        "available": EMBEDDINGS_AVAILABLE,
        "status": "enabled" if EMBEDDINGS_AVAILABLE else "disabled (ChromaDB not installed)"
    }
    if EMBEDDINGS_AVAILABLE and get_embedding_stats:
        try:
            embed_stats = get_embedding_stats()
            status["features"]["semantic_search"]["embeddings_count"] = embed_stats.get("count", 0)
        except Exception:
            pass

    # Proactive Intelligence
    status["features"]["proactive_intelligence"] = {
        "available": PROACTIVE_AVAILABLE,
        "status": "enabled" if PROACTIVE_AVAILABLE else "disabled (module not loaded)"
    }

    # Check optional modules
    try:
        from knowledge import query_knowledge
        status["features"]["knowledge_base"] = {"available": True, "status": "enabled"}
    except ImportError:
        status["features"]["knowledge_base"] = {"available": False, "status": "disabled"}

    try:
        from email_processor import fetch_new_emails
        status["features"]["email_processing"] = {"available": True, "status": "enabled (requires Azure AD config)"}
    except ImportError:
        status["features"]["email_processing"] = {"available": False, "status": "disabled"}

    try:
        from onedrive_rclone import OneDriveClient
        status["features"]["onedrive"] = {"available": True, "status": "enabled"}
    except ImportError:
        status["features"]["onedrive"] = {"available": False, "status": "disabled"}

    try:
        from system_queries import list_running_containers
        status["features"]["system_queries"] = {"available": True, "status": "enabled"}
    except ImportError:
        status["features"]["system_queries"] = {"available": False, "status": "disabled"}

    # Summary
    available_count = sum(1 for f in status["features"].values() if f["available"])
    total_count = len(status["features"])
    status["summary"] = f"{available_count}/{total_count} features available"

    return status


def get_recent(hours: int = 24, limit: int = 20) -> List[Dict]:
    """Get recent captures."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, content, capture_type, extracted_entities, created_at
        FROM captures_v2
        WHERE created_at > datetime('now', ?)
        ORDER BY created_at DESC
        LIMIT ?
    """, (f"-{hours} hours", limit))

    results = []
    for row in cursor.fetchall():
        results.append({
            "id": row[0],
            "content": row[1][:200],
            "type": row[2],
            "entities": json.loads(row[3]) if row[3] else {},
            "created_at": row[4]
        })

    conn.close()
    return results


# ============================================================================
# Main / CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="PCP Vault v2 - Smart capture with entity extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python vault_v2.py capture "your message here"
    python vault_v2.py search "query"
    python vault_v2.py search "query" --all
    python vault_v2.py search "query" --sources knowledge,tasks,semantic
    python vault_v2.py search "making things faster" --semantic  # Find similar content
    python vault_v2.py tasks [pending|done]
    python vault_v2.py stats
    python vault_v2.py recent [hours]
    python vault_v2.py person 1 --summary
    python vault_v2.py relationships --stale 14
    python vault_v2.py project 1 --health
    python vault_v2.py projects --stalled 14
    python vault_v2.py context PCP
    python vault_v2.py context 1
    python vault_v2.py suggestions
    python vault_v2.py suggestions --approve ID
    python vault_v2.py suggestions --approve ID --project 1

Brain Dump Examples:
    python vault_v2.py brain-dump "task 1, task 2, also do task 3"
    python vault_v2.py brain-dump --file /path/to/braindump.txt
    python vault_v2.py brain-dump "my tasks..." --dry-run
    python vault_v2.py task 42                    # Get task with context
    python vault_v2.py group oracle-setup         # Get tasks by group tag

Attachment Processing Examples:
    python vault_v2.py attachments 'message with [ATTACHMENTS: [...]]'
    python vault_v2.py attachments --file /path/to/discord_message.txt
    python vault_v2.py attachments 'message' --context "homework submission" --json
"""
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # capture command
    capture_parser = subparsers.add_parser("capture", help="Capture content")
    capture_parser.add_argument("content", nargs="+", help="Content to capture")

    # search command
    search_parser = subparsers.add_parser("search", help="Search across vault")
    search_parser.add_argument("query", nargs="+", help="Search query")
    search_parser.add_argument("--all", "-a", action="store_true",
                               help="Search all sources (captures, knowledge, emails, tasks, semantic)")
    search_parser.add_argument("--sources", "-S", type=str, metavar="SOURCES",
                               help="Comma-separated sources to search (captures,knowledge,emails,tasks,semantic)")
    search_parser.add_argument("--semantic", "-s", action="store_true",
                               help="Use semantic (similarity-based) search")

    # tasks command
    tasks_parser = subparsers.add_parser("tasks", help="List tasks")
    tasks_parser.add_argument("status", nargs="?", default="pending",
                              choices=["pending", "done", "all"],
                              help="Filter by status (default: pending)")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show vault statistics")

    # status command
    status_parser = subparsers.add_parser("status", help="Show feature availability status")
    status_parser.add_argument("--json", "-j", action="store_true",
                               help="Output as JSON")

    # recent command
    recent_parser = subparsers.add_parser("recent", help="Show recent captures")
    recent_parser.add_argument("hours", nargs="?", type=int, default=24,
                               help="Hours to look back (default: 24)")

    # person command
    person_parser = subparsers.add_parser("person", help="Get person info")
    person_parser.add_argument("person_id", type=int, help="Person ID")
    person_parser.add_argument("--summary", "-s", action="store_true",
                               help="Show full relationship summary")

    # relationships command
    rel_parser = subparsers.add_parser("relationships", help="Manage relationships")
    rel_parser.add_argument("--stale", "-s", type=int, metavar="DAYS",
                            help="Show people not contacted in N days")

    # project command
    project_parser = subparsers.add_parser("project", help="Get project info")
    project_parser.add_argument("project_id", type=int, help="Project ID")
    project_parser.add_argument("--health", action="store_true",
                                help="Show project health metrics")

    # projects command
    projects_parser = subparsers.add_parser("projects", help="Manage projects")
    projects_parser.add_argument("--stalled", "-s", type=int, metavar="DAYS",
                                 help="Show projects with no activity in N days")

    # context command
    context_parser = subparsers.add_parser("context", help="Restore project context")
    context_parser.add_argument("project", help="Project ID or name")
    context_parser.add_argument("--json", "-j", action="store_true",
                                help="Output as JSON instead of human-readable")

    # brain-dump command
    brain_dump_parser = subparsers.add_parser("brain-dump", help="Parse and store a brain dump of multiple tasks")
    brain_dump_parser.add_argument("text", nargs="*", help="Brain dump text (or use --file)")
    brain_dump_parser.add_argument("--file", "-f", type=str, metavar="FILE",
                                   help="Read brain dump from file")
    brain_dump_parser.add_argument("--json", "-j", action="store_true",
                                   help="Output result as JSON")
    brain_dump_parser.add_argument("--dry-run", "-n", action="store_true",
                                   help="Parse only, don't store (preview what would be created)")

    # task command (with context)
    task_parser = subparsers.add_parser("task", help="Get task with full context")
    task_parser.add_argument("task_id", type=int, help="Task ID")
    task_parser.add_argument("--json", "-j", action="store_true",
                             help="Output as JSON")

    # group command
    group_parser = subparsers.add_parser("group", help="Get tasks by group tag")
    group_parser.add_argument("group_tag", help="Group tag to search for")
    group_parser.add_argument("--json", "-j", action="store_true",
                              help="Output as JSON")

    # attachments command
    att_parser = subparsers.add_parser("attachments", help="Process Discord attachments from a message")
    att_parser.add_argument("message", nargs="*", help="Message containing [ATTACHMENTS: ...]")
    att_parser.add_argument("--file", "-f", type=str, metavar="FILE",
                            help="Read message from file")
    att_parser.add_argument("--context", "-c", type=str, default="",
                            help="Additional context for processing")
    att_parser.add_argument("--json", "-j", action="store_true",
                            help="Output result as JSON")

    # suggestions command
    suggestions_parser = subparsers.add_parser("suggestions", help="Manage pattern-generated task suggestions")
    suggestions_parser.add_argument("--approve", "-a", type=int, metavar="ID",
                                    help="Approve suggestion ID and create task")
    suggestions_parser.add_argument("--dismiss", "-d", type=int, metavar="ID",
                                    help="Dismiss suggestion ID")
    suggestions_parser.add_argument("--project", "-p", type=int, metavar="PROJECT_ID",
                                    help="Link approved task to project ID (use with --approve)")
    suggestions_parser.add_argument("--all", action="store_true",
                                    help="Show all suggestions (including approved/dismissed)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "capture":
        content = " ".join(args.content)
        result = smart_capture(content)
        print(f"Captured as {result['type']} (ID: {result['capture_id']})")
        if result.get("task_id"):
            print(f"Created task (ID: {result['task_id']})")
        if result["entities"].get("people"):
            print(f"People: {', '.join(result['entities']['people'])}")
        if result["linked"]["projects"]:
            print(f"Linked to projects: {result['linked']['projects']}")

    elif args.command == "search":
        query = " ".join(args.query)

        # Use semantic search if --semantic specified
        if getattr(args, 'semantic', False):
            results = semantic_search(query)
            if results:
                print(f"\nSemantic search for: '{query}'\n")
                for r in results:
                    similarity = r.get('similarity', 0)
                    match_type = r.get('match_type', 'unknown')
                    print(f"[{r.get('capture_type', 'unknown')}] ({similarity:.0%} {match_type})")
                    print(f"  {r.get('content', '')[:80]}...")
            else:
                print(f"No semantic matches for '{query}'")
                if not EMBEDDINGS_AVAILABLE:
                    print("Note: ChromaDB not available. Install with: pip install chromadb")

        # Use unified_search if --all or --sources specified
        elif getattr(args, 'all', False) or getattr(args, 'sources', None):
            sources = None
            if args.sources:
                sources = [s.strip() for s in args.sources.split(",")]
            results = unified_search(query, sources=sources)

            if results:
                for r in results:
                    source = r['source_type']
                    preview = r['preview'][:60] if r['preview'] else ''
                    relevance = r['relevance']
                    print(f"[{source}] {preview}")
                    print(f"         {relevance}")
            else:
                sources_str = ", ".join(sources) if sources else "all sources"
                print(f"No results for '{query}' in {sources_str}")
        else:
            # Default: use smart_search (existing behavior)
            results = smart_search(query)
            for r in results:
                if r["type"] == "capture":
                    print(f"[{r['type']}:{r['capture_type']}] {r['content'][:80]}")
                elif r["type"] == "person":
                    print(f"[person] {r['name']} - {r.get('context', 'No context')}")
                elif r["type"] == "project":
                    print(f"[project] {r['name']} ({r['status']})")
                elif r["type"] == "file":
                    print(f"[file] {r['file_name']} - {r.get('summary', '')[:50]}")

    elif args.command == "tasks":
        status = args.status if args.status != "all" else None
        tasks = get_tasks(status=status)
        for t in tasks:
            due = f" (due: {t['due_date']})" if t['due_date'] else ""
            print(f"[{t['id']}] {t['content'][:60]}{due}")

    elif args.command == "stats":
        stats = get_stats()
        print(f"Captures: {stats['total_captures']} ({stats['captures_today']} today)")
        print(f"Tasks: {stats.get('tasks_by_status', {})}")
        print(f"Overdue: {stats['overdue_tasks']}")
        print(f"People: {stats['total_people']}")
        print(f"Projects: {stats['active_projects']} active")
        print(f"Files: {stats['total_files']}")

    elif args.command == "status":
        feature_status = get_feature_status()
        if getattr(args, 'json', False):
            print(json.dumps(feature_status, indent=2))
        else:
            print(f"\nPCP Feature Status ({feature_status['summary']})")
            print("=" * 50)
            for name, info in feature_status["features"].items():
                icon = "✓" if info["available"] else "✗"
                print(f"  {icon} {name}: {info['status']}")
                if info.get("embeddings_count"):
                    print(f"      Embeddings: {info['embeddings_count']}")
            print()

    elif args.command == "recent":
        recent = get_recent(hours=args.hours)
        for r in recent:
            print(f"[{r['type']}] {r['content']}")

    elif args.command == "person":
        if args.summary:
            summary = get_relationship_summary(args.person_id)
            if summary:
                print(f"=== {summary['name']} ===")
                if summary['organization']:
                    print(f"Organization: {summary['organization']}")
                if summary['relationship']:
                    print(f"Relationship: {summary['relationship']}")
                if summary['context']:
                    print(f"Context: {summary['context']}")
                print()
                print(f"Interactions: {summary['interaction_count']}")
                print(f"Mentions: {summary['mention_count']}")
                if summary['first_contacted']:
                    print(f"First contacted: {summary['first_contacted'][:10]}")
                if summary['last_contacted']:
                    days = summary.get('days_since_contact')
                    days_str = f" ({days} days ago)" if days is not None else ""
                    print(f"Last contacted: {summary['last_contacted'][:10]}{days_str}")
                else:
                    print("Last contacted: Never")

                if summary['recent_captures']:
                    print()
                    print("Recent Captures:")
                    for cap in summary['recent_captures']:
                        print(f"  [{cap['type']}] {cap['content'][:60]}")
            else:
                print(f"Person not found: {args.person_id}")
        else:
            # Without --summary, just show basic info
            summary = get_relationship_summary(args.person_id)
            if summary:
                print(f"[{summary['id']}] {summary['name']}")
                if summary['organization']:
                    print(f"  Org: {summary['organization']}")
                if summary['relationship']:
                    print(f"  Relationship: {summary['relationship']}")
                days = summary.get('days_since_contact')
                if days is not None:
                    print(f"  Last contacted: {days} days ago")
                else:
                    print("  Last contacted: Never")
            else:
                print(f"Person not found: {args.person_id}")

    elif args.command == "relationships":
        if args.stale is not None:
            stale = get_stale_relationships(days=args.stale)
            if stale:
                print(f"People not contacted in {args.stale}+ days:")
                print()
                for p in stale:
                    days = p.get('days_since_contact')
                    if days is not None:
                        status = f"{days} days ago"
                    else:
                        status = "never contacted"
                    org = f" ({p['organization']})" if p.get('organization') else ""
                    print(f"  [{p['id']}] {p['name']}{org}")
                    print(f"       Last contact: {status}, Interactions: {p['interaction_count']}")
            else:
                print(f"No stale relationships (everyone contacted within {args.stale} days)")
        else:
            parser.parse_args(["relationships", "--help"])

    elif args.command == "project":
        if args.health:
            health = get_project_health(args.project_id)
            if health:
                print(f"=== {health['name']} ===")
                print(f"Status: {health['status']} | Health: {health['health']}")
                if health['description']:
                    print(f"Description: {health['description'][:80]}")
                print()

                # Activity summary
                days = health.get('days_since_activity')
                if days is not None:
                    last_str = f"{days} days ago"
                else:
                    last_str = "Never"
                print(f"Last activity: {last_str}")
                print(f"Total captures: {health['capture_count']}")
                print(f"  This week: {health.get('captures_week', 0)}")
                print(f"  This month: {health.get('captures_month', 0)}")
                print(f"  This quarter: {health.get('captures_quarter', 0)}")
                print()

                # Task summary
                print(f"Pending tasks: {health['pending_tasks']}")
                print(f"Overdue tasks: {health['overdue_tasks']}")
                if health.get('tasks_by_status'):
                    print(f"Tasks by status: {health['tasks_by_status']}")
            else:
                print(f"Project not found: {args.project_id}")
        else:
            # Without --health, just show basic info
            health = get_project_health(args.project_id)
            if health:
                print(f"[{health['id']}] {health['name']} ({health['status']})")
                if health['description']:
                    print(f"  {health['description'][:60]}")
                days = health.get('days_since_activity')
                if days is not None:
                    print(f"  Last activity: {days} days ago")
                else:
                    print("  Last activity: Never")
                print(f"  Health: {health['health']}")
            else:
                print(f"Project not found: {args.project_id}")

    elif args.command == "projects":
        if args.stalled is not None:
            stalled = get_stalled_projects(days=args.stalled)
            if stalled:
                print(f"Projects with no activity in {args.stalled}+ days:")
                print()
                for p in stalled:
                    days = p.get('days_since_activity')
                    if days is not None:
                        status = f"{days} days ago"
                    else:
                        status = "never active"
                    print(f"  [{p['id']}] {p['name']}")
                    if p.get('description'):
                        print(f"       {p['description'][:50]}")
                    print(f"       Last activity: {status}")
                    print(f"       Pending tasks: {p['pending_tasks']}, Total captures: {p['capture_count']}")
            else:
                print(f"No stalled projects (all active within {args.stalled} days)")
        else:
            parser.parse_args(["projects", "--help"])

    elif args.command == "context":
        # Resolve project by ID or name
        project_id = None

        # Try to parse as integer first
        try:
            project_id = int(args.project)
        except ValueError:
            # Not an integer, search by name
            conn = sqlite3.connect(VAULT_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM projects WHERE name LIKE ?",
                (f"%{args.project}%",)
            )
            row = cursor.fetchone()
            if row:
                project_id = row[0]
            conn.close()

        if not project_id:
            print(f"Project not found: {args.project}")
            sys.exit(1)

        if getattr(args, 'json', False):
            # JSON output
            ctx = get_project_context(project_id)
            if ctx:
                print(json.dumps(ctx, indent=2, default=str))
            else:
                print(f"Project not found: {project_id}")
        else:
            # Human-readable output
            summary = restore_context(project_id)
            if summary:
                print(summary)
            else:
                print(f"Project not found: {project_id}")

    elif args.command == "suggestions":
        if getattr(args, 'approve', None):
            # Approve a suggestion
            result = approve_suggestion(args.approve, project_id=getattr(args, 'project', None))
            if result is None:
                print(f"Suggestion not found: {args.approve}")
                sys.exit(1)
            elif result.get("error"):
                print(f"Cannot approve: {result['error']}")
                sys.exit(1)
            else:
                print(f"Created task [{result['task_id']}] from suggestion [{result['suggestion_id']}]")
                print(f"  Content: {result['content'][:60]}")

        elif getattr(args, 'dismiss', None):
            # Dismiss a suggestion
            success = dismiss_suggestion(args.dismiss)
            if success:
                print(f"Dismissed suggestion [{args.dismiss}]")
            else:
                print(f"Cannot dismiss: suggestion not found or already processed")
                sys.exit(1)

        else:
            # List suggestions
            if getattr(args, 'all', False):
                # Get all statuses
                all_suggestions = []
                for status in ['pending', 'approved', 'dismissed']:
                    all_suggestions.extend(get_suggested_tasks(status=status))
                suggestions = sorted(all_suggestions, key=lambda x: x.get('created_at', ''), reverse=True)
            else:
                suggestions = get_suggested_tasks(status='pending')

            if suggestions:
                status_label = "All" if getattr(args, 'all', False) else "Pending"
                print(f"# {status_label} Suggested Tasks\n")
                for s in suggestions:
                    status_indicator = {
                        'pending': '[ ]',
                        'approved': '[✓]',
                        'dismissed': '[x]'
                    }.get(s['status'], '[?]')
                    print(f"  {status_indicator} [{s['id']}] {s['content'][:60]}")
                    print(f"        Reason: {s['reason'][:50]}...")
                    print(f"        Pattern: {s['source_pattern']}")
                    print()
                print("Use --approve ID to create a task, --dismiss ID to dismiss")
            else:
                print("No pending suggested tasks")
                print("Run 'python patterns.py --suggest-tasks' to generate suggestions")

    elif args.command == "brain-dump":
        # Get the text from args or file
        if getattr(args, 'file', None):
            try:
                with open(args.file, 'r') as f:
                    text = f.read()
            except FileNotFoundError:
                print(f"File not found: {args.file}")
                sys.exit(1)
        elif args.text:
            text = " ".join(args.text)
        else:
            print("Please provide brain dump text or use --file")
            sys.exit(1)

        # Parse the brain dump
        print("Parsing brain dump...")
        parsed = parse_brain_dump(text)

        if getattr(args, 'dry_run', False):
            # Dry run - just show what would be created
            if getattr(args, 'json', False):
                print(json.dumps(parsed, indent=2, default=str))
            else:
                print(f"\n# Brain Dump Preview\n")
                print(f"Summary: {parsed.get('summary', 'N/A')}\n")

                items = parsed.get("items", [])

                # Group by type
                by_type = {}
                for item in items:
                    t = item.get("type", "note")
                    if t not in by_type:
                        by_type[t] = []
                    by_type[t].append(item)

                # Display type icons
                type_icons = {
                    "task": "☐",
                    "note": "📝",
                    "idea": "💡",
                    "fact": "📌",
                    "decision": "✓"
                }

                for item_type, type_items in by_type.items():
                    icon = type_icons.get(item_type, "•")
                    print(f"## {item_type.title()}s ({len(type_items)})\n")
                    for i, item in enumerate(type_items, 1):
                        print(f"{icon} {item.get('content', 'N/A')}")
                        if item.get('context'):
                            ctx = item['context'][:60]
                            print(f"   Context: {ctx}{'...' if len(item['context']) > 60 else ''}")
                        if item.get('people'):
                            print(f"   People: {', '.join(item['people'])}")
                        if item.get('projects'):
                            print(f"   Projects: {', '.join(item['projects'])}")
                        if item.get('deadline'):
                            print(f"   Deadline: {item['deadline']}")
                        if item.get('group'):
                            print(f"   Group: {item['group']}")
                        if item.get('priority') and item['priority'] != 'normal' and item_type == 'task':
                            print(f"   Priority: {item['priority']}")
                        print()

                print("(Use without --dry-run to actually create these)")
        else:
            # Actually store the items
            result = store_brain_dump_items(parsed, text, source="cli")

            if getattr(args, 'json', False):
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"\n# Brain Dump Processed\n")
                print(f"Summary: {parsed.get('summary', 'N/A')}")
                print(f"Parent capture: #{result['parent_capture_id']}")

                # Show what was created
                if result.get('task_ids'):
                    print(f"Tasks created: {len(result['task_ids'])}")
                if result.get('capture_ids'):
                    print(f"Captures created: {len(result['capture_ids'])}")
                if result.get('knowledge_ids'):
                    print(f"Knowledge added: {len(result['knowledge_ids'])}")
                if result.get('decision_ids'):
                    print(f"Decisions recorded: {len(result['decision_ids'])}")
                print()

                # Show items by type
                items = parsed.get("items", [])
                task_idx = 0
                capture_idx = 0
                knowledge_idx = 0
                decision_idx = 0

                for item in items:
                    t = item.get("type", "note")
                    content = item.get('content', 'N/A')[:60]

                    if t == "task" and task_idx < len(result.get('task_ids', [])):
                        print(f"  [task #{result['task_ids'][task_idx]}] {content}")
                        task_idx += 1
                    elif t == "fact" and knowledge_idx < len(result.get('knowledge_ids', [])):
                        print(f"  [fact #{result['knowledge_ids'][knowledge_idx]}] {content}")
                        knowledge_idx += 1
                    elif t == "decision" and decision_idx < len(result.get('decision_ids', [])):
                        print(f"  [decision #{result['decision_ids'][decision_idx]}] {content}")
                        decision_idx += 1
                    elif capture_idx < len(result.get('capture_ids', [])):
                        print(f"  [{t} #{result['capture_ids'][capture_idx]}] {content}")
                        capture_idx += 1

    elif args.command == "task":
        task = get_task_with_context(args.task_id)
        if not task:
            print(f"Task not found: {args.task_id}")
            sys.exit(1)

        if getattr(args, 'json', False):
            print(json.dumps(task, indent=2, default=str))
        else:
            print(f"# Task #{task['id']}\n")
            print(f"Content: {task['content']}")
            print(f"Status: {task['status']} | Priority: {task['priority']}")
            if task['due_date']:
                print(f"Due: {task['due_date']}")
            print()

            # Context
            ctx = task.get('context', {})
            if ctx:
                print("## Context\n")
                if ctx.get('background'):
                    print(f"Background: {ctx['background']}")
                if ctx.get('source_text'):
                    print(f"Original: {ctx['source_text'][:100]}...")
                if ctx.get('group_tag'):
                    print(f"Group: {ctx['group_tag']}")
                print()

            # Related people
            if task.get('related_people'):
                print("## People\n")
                for p in task['related_people']:
                    org = f" ({p['organization']})" if p.get('organization') else ""
                    print(f"- {p['name']}{org}")
                print()

            # Project
            if task.get('project'):
                print("## Project\n")
                print(f"{task['project']['name']} ({task['project']['status']})")
                print()

            # Grouped tasks
            if task.get('grouped_tasks'):
                print("## Related Tasks (same group)\n")
                for gt in task['grouped_tasks']:
                    status_icon = "✓" if gt['status'] == 'done' else "○"
                    print(f"  {status_icon} [{gt['id']}] {gt['content'][:50]}")
                print()

            # Related captures
            if task.get('related_captures'):
                print("## Source Captures\n")
                for cap in task['related_captures']:
                    print(f"  [{cap['id']}] {cap['content'][:60]}...")

    elif args.command == "group":
        tasks = get_tasks_by_group(args.group_tag)

        if getattr(args, 'json', False):
            print(json.dumps(tasks, indent=2, default=str))
        else:
            if tasks:
                print(f"# Tasks in group: {args.group_tag}\n")
                for t in tasks:
                    status_icon = "✓" if t['status'] == 'done' else "○"
                    due = f" (due: {t['due_date']})" if t['due_date'] else ""
                    print(f"  {status_icon} [{t['id']}] {t['content'][:60]}{due}")
            else:
                print(f"No tasks found with group tag: {args.group_tag}")

    elif args.command == "attachments":
        # Get the message from args or file
        if getattr(args, 'file', None):
            try:
                with open(args.file, 'r') as f:
                    message = f.read()
            except FileNotFoundError:
                print(f"File not found: {args.file}")
                sys.exit(1)
        elif args.message:
            message = " ".join(args.message)
        else:
            print("Please provide message text or use --file")
            sys.exit(1)

        context = getattr(args, 'context', "")
        result = process_discord_attachments(message, context=context)

        if getattr(args, 'json', False):
            print(json.dumps(result, indent=2, default=str))
        else:
            print(format_attachment_confirmation(result))
            if result["message_text"] and result["message_text"] != message:
                print(f"\nClean message text: {result['message_text'][:200]}...")

    else:
        print(f"Unknown command: {args.command}")
