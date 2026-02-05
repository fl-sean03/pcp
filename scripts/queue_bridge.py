#!/usr/bin/env python3
"""
Queue Bridge - Bridge between Discord bot and PCP message queue.

This module provides integration between the Discord gateway and the
PCP message queue system. It can be used by the Discord bot to:
1. Enqueue messages to the SQLite queue
2. Check queue status
3. Get responses when processing completes

For full v4.0 architecture, the orchestrator should run as a separate service.
This bridge provides the interface for the Discord side.

Usage:
    from queue_bridge import enqueue_discord_message, get_message_status

    # Enqueue a message
    queue_id = enqueue_discord_message(
        message_id="123456",
        channel_id="DISCORD_CHANNEL_ID",
        user_id="user123",
        user_name="User",
        content="Create a TIM workspace",
        attachments=[{"filename": "file.pdf", "path": "/tmp/file.pdf"}]
    )

    # Check status later
    status = get_message_status("123456")
"""

import os
import sys
from typing import Optional, Dict, List, Any

# Add scripts directory to path for imports
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from message_queue import MessageQueue, ParallelTaskManager, get_queue_stats


# Singleton queue instance
_queue: Optional[MessageQueue] = None
_parallel: Optional[ParallelTaskManager] = None


def get_queue() -> MessageQueue:
    """Get the message queue instance."""
    global _queue
    if _queue is None:
        _queue = MessageQueue()
    return _queue


def get_parallel() -> ParallelTaskManager:
    """Get the parallel task manager instance."""
    global _parallel
    if _parallel is None:
        _parallel = ParallelTaskManager()
    return _parallel


def enqueue_discord_message(
    message_id: str,
    channel_id: str,
    user_id: str,
    user_name: str,
    content: str,
    attachments: List[Dict] = None,
    priority: int = 5
) -> int:
    """
    Enqueue a Discord message for processing.

    This is the main entry point for the Discord bot. When a message arrives,
    the bot should call this function to persist it to the queue.

    Returns:
        Queue ID for the message
    """
    queue = get_queue()
    return queue.enqueue(
        message_id=message_id,
        channel_id=channel_id,
        user_id=user_id,
        user_name=user_name,
        content=content,
        attachments=attachments,
        priority=priority
    )


def get_message_status(message_id: str) -> Optional[Dict]:
    """
    Get the status of a message by Discord message ID.

    Returns:
        Message status dict or None if not found
    """
    queue = get_queue()
    return queue.get_status(message_id)


def get_pending_count() -> int:
    """Get count of pending messages."""
    queue = get_queue()
    return queue.get_pending_count()


def get_processing_count() -> int:
    """Get count of currently processing messages."""
    queue = get_queue()
    return queue.get_processing_count()


def create_parallel_task(
    description: str,
    focus_mode: str = 'general',
    context: Dict = None,
    queue_message_id: int = None,
    discord_channel_id: str = None
) -> int:
    """
    Create a parallel task for background work.

    Called by the agent when spawning parallel work.

    Returns:
        Task ID
    """
    parallel = get_parallel()
    return parallel.create_task(
        description=description,
        focus_mode=focus_mode,
        context=context,
        queue_message_id=queue_message_id,
        discord_channel_id=discord_channel_id
    )


def update_parallel_progress(task_id: int, message: str) -> bool:
    """Add a progress update to a parallel task."""
    parallel = get_parallel()
    return parallel.add_progress(task_id, message)


def complete_parallel_task(task_id: int, result: str = None) -> bool:
    """Mark a parallel task as completed."""
    parallel = get_parallel()
    return parallel.complete_task(task_id, result)


def fail_parallel_task(task_id: int, error: str = None) -> bool:
    """Mark a parallel task as failed."""
    parallel = get_parallel()
    return parallel.fail_task(task_id, error)


def get_parallel_task(task_id: int) -> Optional[Dict]:
    """Get a parallel task by ID."""
    parallel = get_parallel()
    return parallel.get_task(task_id)


def get_stats() -> Dict:
    """Get queue and parallel task statistics."""
    return get_queue_stats()


# HTTP API endpoints for external callers
def make_flask_routes(app):
    """
    Add Flask routes for queue management.

    Usage:
        from flask import Flask
        from queue_bridge import make_flask_routes

        app = Flask(__name__)
        make_flask_routes(app)
    """
    from flask import request, jsonify

    @app.route('/queue/enqueue', methods=['POST'])
    def api_enqueue():
        data = request.json
        queue_id = enqueue_discord_message(
            message_id=data['message_id'],
            channel_id=data['channel_id'],
            user_id=data['user_id'],
            user_name=data['user_name'],
            content=data['content'],
            attachments=data.get('attachments'),
            priority=data.get('priority', 5)
        )
        return jsonify({'queue_id': queue_id})

    @app.route('/queue/status/<message_id>', methods=['GET'])
    def api_status(message_id):
        status = get_message_status(message_id)
        if status:
            return jsonify(status)
        return jsonify({'error': 'Not found'}), 404

    @app.route('/queue/stats', methods=['GET'])
    def api_stats():
        return jsonify(get_stats())


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PCP Queue Bridge")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Enqueue command
    enqueue_parser = subparsers.add_parser('enqueue', help='Enqueue a test message')
    enqueue_parser.add_argument('content', help='Message content')
    enqueue_parser.add_argument('--user', default='test_user', help='User name')
    enqueue_parser.add_argument('--channel', default='test_channel', help='Channel ID')

    # Status command
    status_parser = subparsers.add_parser('status', help='Get message status')
    status_parser.add_argument('message_id', help='Message ID')

    # Stats command
    subparsers.add_parser('stats', help='Show queue statistics')

    args = parser.parse_args()

    if args.command == 'enqueue':
        import time
        message_id = str(int(time.time() * 1000))
        queue_id = enqueue_discord_message(
            message_id=message_id,
            channel_id=args.channel,
            user_id='test_user_id',
            user_name=args.user,
            content=args.content
        )
        print(f"Enqueued message {message_id} -> queue_id={queue_id}")

    elif args.command == 'status':
        status = get_message_status(args.message_id)
        if status:
            import json
            print(json.dumps(status, indent=2, default=str))
        else:
            print(f"Message {args.message_id} not found")

    elif args.command == 'stats':
        stats = get_stats()
        print("\nQueue Statistics:")
        print(f"  Pending:    {stats['queue']['pending']}")
        print(f"  Processing: {stats['queue']['processing']}")
        print(f"  Completed:  {stats['queue']['completed']}")
        print(f"  Failed:     {stats['queue']['failed']}")
        print("\nParallel Tasks:")
        print(f"  Pending:   {stats['parallel_tasks']['pending']}")
        print(f"  Running:   {stats['parallel_tasks']['running']}")
        print(f"  Completed: {stats['parallel_tasks']['completed']}")

    else:
        parser.print_help()
