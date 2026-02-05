#!/usr/bin/env python3
"""
PCP Message Queue - Queue-first message handling for v4.0 architecture.

This module provides:
- SQLite-based message queue that persists immediately
- Never lose messages, even if the system crashes
- FIFO ordering with priority support
- Parallel task tracking

Usage:
    from message_queue import MessageQueue

    queue = MessageQueue()
    queue_id = queue.enqueue(message_id, channel_id, user_id, user_name, content)
    message = queue.get_next_pending()
    queue.mark_completed(queue_id, response="Done!")
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

# Support both container and local development paths
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)) and os.path.exists(os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault")):
    VAULT_PATH = os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db")


def _safe_json_loads(value: Any, default: Any = None) -> Any:
    """Safely parse JSON, returning default on error."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value  # Already parsed
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


# Queue schema - will be added by migration
QUEUE_SCHEMA = """
-- Discord message queue for queue-first architecture
CREATE TABLE IF NOT EXISTS discord_message_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Discord context
    channel_id TEXT NOT NULL,
    message_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    user_name TEXT NOT NULL,

    -- Content
    content TEXT NOT NULL,
    attachments TEXT,  -- JSON array

    -- Processing state
    status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
    priority INTEGER DEFAULT 5,      -- 1=highest, 10=lowest

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results
    response TEXT,
    error TEXT,

    -- Parallel tracking
    spawned_parallel BOOLEAN DEFAULT FALSE,
    parallel_task_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_queue_status ON discord_message_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_created ON discord_message_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_queue_priority ON discord_message_queue(priority, created_at);

-- Parallel tasks spawned by agent instances
CREATE TABLE IF NOT EXISTS parallel_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source
    queue_message_id INTEGER,

    -- Task info
    description TEXT NOT NULL,
    focus_mode TEXT DEFAULT 'general',
    context TEXT,  -- JSON context data

    -- Status
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed

    -- Process tracking
    pid INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results
    result TEXT,
    error TEXT,

    -- Discord notification
    notification_sent BOOLEAN DEFAULT FALSE,
    discord_channel_id TEXT,

    -- Progress updates
    progress_updates TEXT,  -- JSON array of progress messages

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (queue_message_id) REFERENCES discord_message_queue(id)
);

CREATE INDEX IF NOT EXISTS idx_parallel_status ON parallel_tasks(status);
CREATE INDEX IF NOT EXISTS idx_parallel_queue ON parallel_tasks(queue_message_id);
"""


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_queue_schema():
    """Initialize the queue schema if not exists."""
    conn = get_connection()
    conn.executescript(QUEUE_SCHEMA)
    conn.commit()
    conn.close()


class MessageQueue:
    """
    SQLite-based message queue for Discord messages.

    Guarantees:
    - Message received = Message persisted (atomic enqueue)
    - Survives process restarts
    - FIFO ordering with priority support
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or VAULT_PATH
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure queue tables exist."""
        conn = sqlite3.connect(self.db_path)
        conn.executescript(QUEUE_SCHEMA)
        conn.commit()
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with WAL mode for better concurrency."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def enqueue(
        self,
        message_id: str,
        channel_id: str,
        user_id: str,
        user_name: str,
        content: str,
        attachments: List[Dict] = None,
        priority: int = 5
    ) -> int:
        """
        Add message to queue. Returns queue ID.

        This is atomic - if it returns, the message is persisted.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO discord_message_queue
                (message_id, channel_id, user_id, user_name, content, attachments, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id,
                channel_id,
                user_id,
                user_name,
                content,
                json.dumps(attachments) if attachments else None,
                priority
            ))
            conn.commit()
            queue_id = cursor.lastrowid
            return queue_id
        except sqlite3.IntegrityError:
            # Message already in queue (duplicate)
            cursor.execute(
                "SELECT id FROM discord_message_queue WHERE message_id = ?",
                (message_id,)
            )
            row = cursor.fetchone()
            return row['id'] if row else None
        finally:
            conn.close()

    def get_next_pending(self) -> Optional[Dict]:
        """
        Get next pending message, ordered by priority then creation time.
        Returns None if queue is empty.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM discord_message_queue
            WHERE status = 'pending'
            ORDER BY priority ASC, created_at ASC
            LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            if result.get('attachments'):
                result['attachments'] = _safe_json_loads(result['attachments'], [])
            return result
        return None

    def get_pending_count(self) -> int:
        """Get count of pending messages."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM discord_message_queue WHERE status = 'pending'")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_processing_count(self) -> int:
        """Get count of currently processing messages."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM discord_message_queue WHERE status = 'processing'")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def mark_processing(self, queue_id: int) -> bool:
        """Mark message as being processed. Returns True if successful."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE discord_message_queue
            SET status = 'processing', started_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending'
        """, (queue_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def mark_completed(self, queue_id: int, response: str = None) -> bool:
        """Mark message as completed with optional response."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE discord_message_queue
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                response = ?
            WHERE id = ?
        """, (response, queue_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def mark_failed(self, queue_id: int, error: str = None) -> bool:
        """Mark message as failed with optional error message."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE discord_message_queue
            SET status = 'failed',
                completed_at = CURRENT_TIMESTAMP,
                error = ?
            WHERE id = ?
        """, (error, queue_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def mark_parallel(self, queue_id: int, parallel_task_id: int) -> bool:
        """Mark message as having spawned a parallel task."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE discord_message_queue
            SET spawned_parallel = TRUE,
                parallel_task_id = ?
            WHERE id = ?
        """, (parallel_task_id, queue_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def get_status(self, message_id: str) -> Optional[Dict]:
        """Get status of a message by Discord message ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM discord_message_queue WHERE message_id = ?",
            (message_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            if result.get('attachments'):
                result['attachments'] = _safe_json_loads(result['attachments'], [])
            return result
        return None

    def get_by_id(self, queue_id: int) -> Optional[Dict]:
        """Get message by queue ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM discord_message_queue WHERE id = ?",
            (queue_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            if result.get('attachments'):
                result['attachments'] = _safe_json_loads(result['attachments'], [])
            return result
        return None

    def cleanup_old(self, days: int = 7) -> int:
        """Remove completed/failed messages older than N days. Returns count removed."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cutoff = datetime.now() - timedelta(days=days)

        cursor.execute("""
            DELETE FROM discord_message_queue
            WHERE status IN ('completed', 'failed')
            AND completed_at < ?
        """, (cutoff.isoformat(),))

        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count

    def get_stale_processing(self, timeout_minutes: int = 10) -> List[Dict]:
        """Get messages stuck in processing state longer than timeout."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cutoff = datetime.now() - timedelta(minutes=timeout_minutes)

        cursor.execute("""
            SELECT * FROM discord_message_queue
            WHERE status = 'processing'
            AND started_at < ?
        """, (cutoff.isoformat(),))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def reset_stale(self, timeout_minutes: int = 10) -> int:
        """Reset stale processing messages back to pending. Returns count reset."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cutoff = datetime.now() - timedelta(minutes=timeout_minutes)

        cursor.execute("""
            UPDATE discord_message_queue
            SET status = 'pending', started_at = NULL
            WHERE status = 'processing'
            AND started_at < ?
        """, (cutoff.isoformat(),))

        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count

    def get_recent(self, limit: int = 20) -> List[Dict]:
        """Get recent messages across all statuses."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM discord_message_queue
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]


class ParallelTaskManager:
    """
    Manager for parallel tasks spawned by agent instances.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or VAULT_PATH

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with WAL mode for better concurrency."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def create_task(
        self,
        description: str,
        focus_mode: str = 'general',
        context: Dict = None,
        queue_message_id: int = None,
        discord_channel_id: str = None
    ) -> int:
        """Create a new parallel task. Returns task ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO parallel_tasks
            (description, focus_mode, context, queue_message_id, discord_channel_id, progress_updates)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            description,
            focus_mode,
            json.dumps(context) if context else None,
            queue_message_id,
            discord_channel_id,
            json.dumps([])  # Empty progress array
        ))

        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id

    def start_task(self, task_id: int, pid: int = None) -> bool:
        """Mark task as running with optional process ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE parallel_tasks
            SET status = 'running',
                started_at = CURRENT_TIMESTAMP,
                pid = ?
            WHERE id = ? AND status = 'pending'
        """, (pid, task_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def complete_task(self, task_id: int, result: str = None) -> bool:
        """Mark task as completed with optional result."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE parallel_tasks
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                result = ?
            WHERE id = ?
        """, (result, task_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def fail_task(self, task_id: int, error: str = None) -> bool:
        """Mark task as failed with optional error."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE parallel_tasks
            SET status = 'failed',
                completed_at = CURRENT_TIMESTAMP,
                error = ?
            WHERE id = ?
        """, (error, task_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def add_progress(self, task_id: int, message: str) -> bool:
        """Add a progress update to a task."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get current progress
        cursor.execute("SELECT progress_updates FROM parallel_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False

        progress = _safe_json_loads(row['progress_updates'], [])
        progress.append({
            'message': message,
            'timestamp': datetime.now().isoformat()
        })

        cursor.execute("""
            UPDATE parallel_tasks
            SET progress_updates = ?
            WHERE id = ?
        """, (json.dumps(progress), task_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def mark_notified(self, task_id: int) -> bool:
        """Mark task as having sent Discord notification."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE parallel_tasks
            SET notification_sent = TRUE
            WHERE id = ?
        """, (task_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def get_task(self, task_id: int) -> Optional[Dict]:
        """Get a parallel task by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM parallel_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            if result.get('context'):
                result['context'] = _safe_json_loads(result['context'], {})
            if result.get('progress_updates'):
                result['progress_updates'] = _safe_json_loads(result['progress_updates'], [])
            return result
        return None

    def get_pending_tasks(self) -> List[Dict]:
        """Get all pending parallel tasks."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM parallel_tasks
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_running_tasks(self) -> List[Dict]:
        """Get all running parallel tasks."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM parallel_tasks
            WHERE status = 'running'
            ORDER BY started_at ASC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_completed_unnotified(self) -> List[Dict]:
        """Get completed tasks that haven't sent Discord notification."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM parallel_tasks
            WHERE status = 'completed'
            AND notification_sent = FALSE
            AND discord_channel_id IS NOT NULL
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]


def get_queue_stats() -> Dict:
    """Get queue statistics."""
    queue = MessageQueue()

    conn = queue._get_conn()
    cursor = conn.cursor()

    # Get counts by status
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM discord_message_queue
        GROUP BY status
    """)
    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}

    # Get parallel task counts
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM parallel_tasks
        GROUP BY status
    """)
    parallel_counts = {row['status']: row['count'] for row in cursor.fetchall()}

    conn.close()

    return {
        'queue': {
            'pending': status_counts.get('pending', 0),
            'processing': status_counts.get('processing', 0),
            'completed': status_counts.get('completed', 0),
            'failed': status_counts.get('failed', 0),
            'total': sum(status_counts.values())
        },
        'parallel_tasks': {
            'pending': parallel_counts.get('pending', 0),
            'running': parallel_counts.get('running', 0),
            'completed': parallel_counts.get('completed', 0),
            'failed': parallel_counts.get('failed', 0),
            'total': sum(parallel_counts.values())
        }
    }


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PCP Message Queue Management")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Stats command
    subparsers.add_parser('stats', help='Show queue statistics')

    # List command
    list_parser = subparsers.add_parser('list', help='List recent messages')
    list_parser.add_argument('--limit', type=int, default=10, help='Number of messages to show')

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Remove old completed messages')
    cleanup_parser.add_argument('--days', type=int, default=7, help='Remove messages older than N days')

    # Reset stale command
    reset_parser = subparsers.add_parser('reset-stale', help='Reset stale processing messages')
    reset_parser.add_argument('--timeout', type=int, default=10, help='Timeout in minutes')

    # Init command
    subparsers.add_parser('init', help='Initialize queue schema')

    args = parser.parse_args()

    if args.command == 'stats':
        stats = get_queue_stats()
        print("\nQueue Statistics:")
        print(f"  Pending:    {stats['queue']['pending']}")
        print(f"  Processing: {stats['queue']['processing']}")
        print(f"  Completed:  {stats['queue']['completed']}")
        print(f"  Failed:     {stats['queue']['failed']}")
        print(f"  Total:      {stats['queue']['total']}")
        print("\nParallel Tasks:")
        print(f"  Pending:   {stats['parallel_tasks']['pending']}")
        print(f"  Running:   {stats['parallel_tasks']['running']}")
        print(f"  Completed: {stats['parallel_tasks']['completed']}")
        print(f"  Failed:    {stats['parallel_tasks']['failed']}")

    elif args.command == 'list':
        queue = MessageQueue()
        messages = queue.get_recent(args.limit)

        print(f"\nRecent {len(messages)} messages:")
        for msg in messages:
            status_icon = {
                'pending': '⏳',
                'processing': '🔄',
                'completed': '✅',
                'failed': '❌'
            }.get(msg['status'], '❓')

            content_preview = msg['content'][:50] + '...' if len(msg['content']) > 50 else msg['content']
            print(f"  {status_icon} [{msg['id']}] {msg['user_name']}: {content_preview}")

    elif args.command == 'cleanup':
        queue = MessageQueue()
        count = queue.cleanup_old(args.days)
        print(f"Removed {count} old messages")

    elif args.command == 'reset-stale':
        queue = MessageQueue()
        count = queue.reset_stale(args.timeout)
        print(f"Reset {count} stale messages to pending")

    elif args.command == 'init':
        init_queue_schema()
        print("Queue schema initialized")

    else:
        parser.print_help()
