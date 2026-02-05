#!/usr/bin/env python3
"""Vault operations for PCP agent."""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

VAULT_DB = Path("/workspace/vault/vault.db")


def _get_conn():
    """Get database connection."""
    return sqlite3.connect(VAULT_DB)


# === CAPTURES ===

def capture(content: str, capture_type: str = "note", tags: list = None, status: str = "active") -> str:
    """
    Save a capture to the vault.

    Args:
        content: The text content to capture
        capture_type: One of 'note', 'task', 'idea', 'question'
        tags: Optional list of tags
        status: Status for tasks ('active', 'done', 'archived')

    Returns:
        The capture ID
    """
    conn = _get_conn()
    c = conn.cursor()

    capture_id = str(uuid.uuid4())[:8]
    tags_json = json.dumps(tags) if tags else None

    c.execute(
        "INSERT INTO captures (id, content, capture_type, tags, status) VALUES (?, ?, ?, ?, ?)",
        (capture_id, content, capture_type, tags_json, status)
    )
    conn.commit()
    conn.close()

    return capture_id


def search(query: str, capture_type: str = None, limit: int = 10) -> list:
    """
    Search captures by content.

    Args:
        query: Search term
        capture_type: Optional filter by type
        limit: Max results

    Returns:
        List of matching captures
    """
    conn = _get_conn()
    c = conn.cursor()

    if capture_type:
        c.execute(
            "SELECT id, content, capture_type, tags, status, created_at FROM captures WHERE content LIKE ? AND capture_type = ? ORDER BY created_at DESC LIMIT ?",
            (f"%{query}%", capture_type, limit)
        )
    else:
        c.execute(
            "SELECT id, content, capture_type, tags, status, created_at FROM captures WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{query}%", limit)
        )

    results = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "content": r[1],
            "type": r[2],
            "tags": json.loads(r[3]) if r[3] else [],
            "status": r[4],
            "created": r[5]
        }
        for r in results
    ]


def get_recent(limit: int = 10, capture_type: str = None) -> list:
    """Get recent captures."""
    conn = _get_conn()
    c = conn.cursor()

    if capture_type:
        c.execute(
            "SELECT id, content, capture_type, tags, status, created_at FROM captures WHERE capture_type = ? ORDER BY created_at DESC LIMIT ?",
            (capture_type, limit)
        )
    else:
        c.execute(
            "SELECT id, content, capture_type, tags, status, created_at FROM captures ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )

    results = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "content": r[1],
            "type": r[2],
            "tags": json.loads(r[3]) if r[3] else [],
            "status": r[4],
            "created": r[5]
        }
        for r in results
    ]


def get_tasks(status: str = "active") -> list:
    """Get tasks by status."""
    conn = _get_conn()
    c = conn.cursor()

    c.execute(
        "SELECT id, content, tags, status, created_at FROM captures WHERE capture_type = 'task' AND status = ? ORDER BY created_at DESC",
        (status,)
    )

    results = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "content": r[1],
            "tags": json.loads(r[2]) if r[2] else [],
            "status": r[3],
            "created": r[4]
        }
        for r in results
    ]


def complete_task(task_id: str) -> bool:
    """Mark a task as done."""
    conn = _get_conn()
    c = conn.cursor()

    c.execute(
        "UPDATE captures SET status = 'done', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND capture_type = 'task'",
        (task_id,)
    )

    updated = c.rowcount > 0
    conn.commit()
    conn.close()

    return updated


# === ENTITIES ===

def add_entity(name: str, entity_type: str, description: str = None, metadata: dict = None) -> str:
    """
    Add an entity (person, project, concept).

    Args:
        name: Entity name
        entity_type: One of 'person', 'project', 'concept', 'event'
        description: Optional description
        metadata: Optional dict of additional data

    Returns:
        The entity ID
    """
    conn = _get_conn()
    c = conn.cursor()

    entity_id = str(uuid.uuid4())[:8]
    metadata_json = json.dumps(metadata) if metadata else None

    c.execute(
        "INSERT INTO entities (id, entity_type, name, description, metadata) VALUES (?, ?, ?, ?, ?)",
        (entity_id, entity_type, name, description, metadata_json)
    )
    conn.commit()
    conn.close()

    return entity_id


def find_entity(name: str = None, entity_type: str = None) -> list:
    """Search for entities."""
    conn = _get_conn()
    c = conn.cursor()

    if name and entity_type:
        c.execute(
            "SELECT id, entity_type, name, description, metadata, created_at FROM entities WHERE name LIKE ? AND entity_type = ?",
            (f"%{name}%", entity_type)
        )
    elif name:
        c.execute(
            "SELECT id, entity_type, name, description, metadata, created_at FROM entities WHERE name LIKE ?",
            (f"%{name}%",)
        )
    elif entity_type:
        c.execute(
            "SELECT id, entity_type, name, description, metadata, created_at FROM entities WHERE entity_type = ?",
            (entity_type,)
        )
    else:
        c.execute("SELECT id, entity_type, name, description, metadata, created_at FROM entities")

    results = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "type": r[1],
            "name": r[2],
            "description": r[3],
            "metadata": json.loads(r[4]) if r[4] else {},
            "created": r[5]
        }
        for r in results
    ]


# === ARTIFACTS ===

def save_artifact(content: str, artifact_type: str, title: str = None, source_ids: list = None) -> str:
    """
    Save an artifact (brief, summary, report).

    Args:
        content: The artifact content
        artifact_type: One of 'brief', 'summary', 'report'
        title: Optional title
        source_ids: Optional list of source capture/entity IDs

    Returns:
        The artifact ID
    """
    conn = _get_conn()
    c = conn.cursor()

    artifact_id = str(uuid.uuid4())[:8]
    source_json = json.dumps(source_ids) if source_ids else None

    c.execute(
        "INSERT INTO artifacts (id, artifact_type, title, content, source_ids) VALUES (?, ?, ?, ?, ?)",
        (artifact_id, artifact_type, title, content, source_json)
    )
    conn.commit()
    conn.close()

    return artifact_id


def get_artifacts(artifact_type: str = None, limit: int = 10) -> list:
    """Get recent artifacts."""
    conn = _get_conn()
    c = conn.cursor()

    if artifact_type:
        c.execute(
            "SELECT id, artifact_type, title, content, source_ids, created_at FROM artifacts WHERE artifact_type = ? ORDER BY created_at DESC LIMIT ?",
            (artifact_type, limit)
        )
    else:
        c.execute(
            "SELECT id, artifact_type, title, content, source_ids, created_at FROM artifacts ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )

    results = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "type": r[1],
            "title": r[2],
            "content": r[3],
            "source_ids": json.loads(r[4]) if r[4] else [],
            "created": r[5]
        }
        for r in results
    ]


# === STATS ===

def stats() -> dict:
    """Get vault statistics."""
    conn = _get_conn()
    c = conn.cursor()

    # Total counts
    c.execute("SELECT COUNT(*) FROM captures")
    total_captures = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM entities")
    total_entities = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM artifacts")
    total_artifacts = c.fetchone()[0]

    # Captures by type
    c.execute("SELECT capture_type, COUNT(*) FROM captures GROUP BY capture_type")
    captures_by_type = dict(c.fetchall())

    # Active tasks
    c.execute("SELECT COUNT(*) FROM captures WHERE capture_type = 'task' AND status = 'active'")
    active_tasks = c.fetchone()[0]

    # Entities by type
    c.execute("SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type")
    entities_by_type = dict(c.fetchall())

    # Recent activity
    c.execute("SELECT MAX(created_at) FROM captures")
    last_capture = c.fetchone()[0]

    conn.close()

    return {
        "captures": {
            "total": total_captures,
            "by_type": captures_by_type,
            "last": last_capture
        },
        "entities": {
            "total": total_entities,
            "by_type": entities_by_type
        },
        "artifacts": {
            "total": total_artifacts
        },
        "tasks": {
            "active": active_tasks
        }
    }


if __name__ == "__main__":
    # Quick test
    print("Vault stats:", stats())
