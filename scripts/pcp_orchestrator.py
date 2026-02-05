#!/usr/bin/env python3
"""
PCP Orchestrator - Process manager for v4.0 architecture.

This is a DUMB process manager with NO intelligence. Its only job is to:
1. Poll the message queue for pending messages
2. Spawn Claude CLI processes to handle them
3. Track worker completion and timeouts
4. Route responses to Discord

The AGENT decides how to handle each message - this orchestrator just
spawns processes and routes results.

Usage:
    # Run as service
    python pcp_orchestrator.py

    # Run with custom settings
    python pcp_orchestrator.py --workers 3 --poll-interval 0.5

    # One-shot mode (process one message and exit)
    python pcp_orchestrator.py --once
"""

import subprocess
import json
import os
import time
import signal
import sys
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, Future

# Import our modules
from message_queue import MessageQueue, ParallelTaskManager
from discord_notify import notify, notify_with_webhook

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('pcp_orchestrator')


@dataclass
class WorkerConfig:
    """Configuration for the orchestrator."""
    max_workers: int = 3
    poll_interval_seconds: float = 0.5
    worker_timeout_seconds: int = 600  # 10 minutes max
    ack_timeout_seconds: int = 30  # Must ACK within 30s
    container_name: str = 'pcp-agent'
    working_dir: str = '/workspace'
    discord_webhook_url: Optional[str] = None


@dataclass
class ActiveWorker:
    """Tracks an active worker process."""
    queue_id: int
    message: Dict
    process: subprocess.Popen
    started_at: datetime
    channel_id: str


class Orchestrator:
    """
    Main orchestrator class.

    Responsibilities:
    - Poll queue for pending messages
    - Spawn Claude CLI processes
    - Track worker completion
    - Handle timeouts
    - Route responses to Discord
    """

    def __init__(self, config: WorkerConfig = None):
        self.config = config or WorkerConfig()
        self.queue = MessageQueue()
        self.parallel_tasks = ParallelTaskManager()
        self.active_workers: Dict[int, ActiveWorker] = {}
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self.running = False
        self._shutdown_event = threading.Event()

        # Load Discord webhook from environment
        if not self.config.discord_webhook_url:
            self.config.discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

    def start(self):
        """Start the orchestrator main loop."""
        self.running = True
        logger.info(f"Starting PCP Orchestrator (max_workers={self.config.max_workers})")

        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        try:
            self._main_loop()
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            raise
        finally:
            self._cleanup()

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        self._shutdown_event.set()

    def _main_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                # Check for completed workers
                self._check_completions()

                # Check for timeouts
                self._check_timeouts()

                # Spawn new workers if capacity available
                if len(self.active_workers) < self.config.max_workers:
                    message = self.queue.get_next_pending()
                    if message:
                        self._spawn_worker(message)

                # Check for completed parallel tasks that need notifications
                self._check_parallel_notifications()

            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            # Sleep with ability to wake on shutdown
            if self._shutdown_event.wait(timeout=self.config.poll_interval_seconds):
                break

    def _spawn_worker(self, message: Dict):
        """Spawn a Claude CLI process to handle a message."""
        queue_id = message['id']

        # Mark as processing
        if not self.queue.mark_processing(queue_id):
            logger.warning(f"Failed to mark message {queue_id} as processing")
            return

        logger.info(f"Spawning worker for message {queue_id}: {message['content'][:50]}...")

        # Build the prompt for Claude
        prompt = self._build_prompt(message)

        # Build Claude CLI command
        cmd = self._build_claude_command(prompt)

        try:
            # Spawn process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.config.working_dir
            )

            # Track worker
            worker = ActiveWorker(
                queue_id=queue_id,
                message=message,
                process=process,
                started_at=datetime.now(),
                channel_id=message['channel_id']
            )
            self.active_workers[queue_id] = worker

            # Add ⏳ reaction via webhook
            self._add_reaction(message['channel_id'], message['message_id'], '⏳')

        except Exception as e:
            logger.error(f"Failed to spawn worker: {e}")
            self.queue.mark_failed(queue_id, str(e))

    def _build_prompt(self, message: Dict) -> str:
        """Build the prompt for Claude."""
        # Include Discord context
        prompt = f"""Discord Message from {message['user_name']}:

{message['content']}
"""

        # Add attachment info if present
        if message.get('attachments'):
            attachments = message['attachments']
            if isinstance(attachments, str):
                attachments = json.loads(attachments)
            if attachments:
                prompt += f"\n[ATTACHMENTS: {json.dumps(attachments)}]\n"

        # Add channel context
        prompt += f"\n[Channel ID: {message['channel_id']}, Message ID: {message['message_id']}]"

        return prompt

    def _build_claude_command(self, prompt: str) -> List[str]:
        """Build the Claude CLI command."""
        # Use docker exec to run inside container
        cmd = [
            'docker', 'exec', '-i',
            self.config.container_name,
            'claude',
            '--print',  # Print response to stdout
            '--dangerously-skip-permissions',  # Skip permission prompts
            '-p', prompt
        ]
        return cmd

    def _check_completions(self):
        """Check for completed worker processes."""
        completed = []

        for queue_id, worker in self.active_workers.items():
            return_code = worker.process.poll()

            if return_code is not None:
                # Process completed
                stdout, stderr = worker.process.communicate()

                if return_code == 0:
                    # Success
                    response = stdout.strip()
                    self._handle_success(worker, response)
                else:
                    # Failure
                    error = stderr.strip() or f"Process exited with code {return_code}"
                    self._handle_failure(worker, error)

                completed.append(queue_id)

        # Remove completed workers
        for queue_id in completed:
            del self.active_workers[queue_id]

    def _handle_success(self, worker: ActiveWorker, response: str):
        """Handle successful worker completion."""
        queue_id = worker.queue_id
        message = worker.message

        logger.info(f"Worker {queue_id} completed successfully")

        # Check if response indicates parallel work was spawned
        if self._indicates_parallel_spawn(response):
            # Mark as parallel, add 🔄 reaction
            # The agent should have created the parallel task
            self.queue.mark_completed(queue_id, response)
            self._swap_reaction(message['channel_id'], message['message_id'], '⏳', '🔄')
        else:
            # Direct response, mark complete
            self.queue.mark_completed(queue_id, response)
            self._swap_reaction(message['channel_id'], message['message_id'], '⏳', '✅')

        # Send response to Discord
        self._send_discord_response(message['channel_id'], message['message_id'], response)

    def _handle_failure(self, worker: ActiveWorker, error: str):
        """Handle worker failure."""
        queue_id = worker.queue_id
        message = worker.message

        logger.error(f"Worker {queue_id} failed: {error}")

        self.queue.mark_failed(queue_id, error)
        self._swap_reaction(message['channel_id'], message['message_id'], '⏳', '❌')

        # Notify of failure
        error_msg = f"❌ Error processing message: {error[:200]}"
        self._send_discord_response(message['channel_id'], message['message_id'], error_msg)

    def _check_timeouts(self):
        """Check for timed out workers."""
        now = datetime.now()
        timeout = timedelta(seconds=self.config.worker_timeout_seconds)

        timed_out = []

        for queue_id, worker in self.active_workers.items():
            if now - worker.started_at > timeout:
                logger.warning(f"Worker {queue_id} timed out")
                timed_out.append((queue_id, worker))

        for queue_id, worker in timed_out:
            # Kill the process
            try:
                worker.process.kill()
            except Exception:
                pass

            # Mark as failed
            self._handle_failure(worker, f"Worker timed out after {self.config.worker_timeout_seconds}s")
            del self.active_workers[queue_id]

    def _check_parallel_notifications(self):
        """Check for completed parallel tasks that need Discord notifications."""
        unnotified = self.parallel_tasks.get_completed_unnotified()

        for task in unnotified:
            channel_id = task.get('discord_channel_id')
            if channel_id:
                result = task.get('result', 'Task completed')
                self._send_discord_message(channel_id, f"✨ {result}")
                self.parallel_tasks.mark_notified(task['id'])

    def _indicates_parallel_spawn(self, response: str) -> bool:
        """Check if response indicates parallel work was spawned."""
        indicators = [
            "working on it",
            "I'll message you when",
            "working in background",
            "spawned",
            "delegated",
            "I'll let you know when"
        ]
        response_lower = response.lower()
        return any(indicator in response_lower for indicator in indicators)

    def _add_reaction(self, channel_id: str, message_id: str, emoji: str):
        """Add a reaction to a Discord message."""
        # This would use Discord API - for now, log it
        logger.debug(f"Adding reaction {emoji} to {message_id}")
        # TODO: Implement via Discord bot API

    def _swap_reaction(self, channel_id: str, message_id: str, old_emoji: str, new_emoji: str):
        """Swap one reaction for another."""
        logger.debug(f"Swapping reaction {old_emoji} -> {new_emoji} on {message_id}")
        # TODO: Implement via Discord bot API

    def _send_discord_response(self, channel_id: str, message_id: str, response: str):
        """Send a response to Discord as a reply."""
        if self.config.discord_webhook_url:
            try:
                notify_with_webhook(response, self.config.discord_webhook_url)
            except Exception as e:
                logger.error(f"Failed to send Discord response: {e}")
        else:
            logger.warning("No Discord webhook configured, response not sent")

    def _send_discord_message(self, channel_id: str, message: str):
        """Send a message to a Discord channel."""
        if self.config.discord_webhook_url:
            try:
                notify_with_webhook(message, self.config.discord_webhook_url)
            except Exception as e:
                logger.error(f"Failed to send Discord message: {e}")

    def _cleanup(self):
        """Cleanup on shutdown."""
        logger.info("Cleaning up...")

        # Kill active workers
        for queue_id, worker in self.active_workers.items():
            try:
                worker.process.kill()
                self.queue.mark_failed(queue_id, "Orchestrator shutdown")
            except Exception:
                pass

        self.executor.shutdown(wait=False)
        logger.info("Cleanup complete")

    def process_one(self) -> Optional[Dict]:
        """Process a single message and return. For testing."""
        message = self.queue.get_next_pending()
        if not message:
            return None

        self._spawn_worker(message)

        # Wait for completion
        worker = self.active_workers.get(message['id'])
        if worker:
            worker.process.wait(timeout=self.config.worker_timeout_seconds)
            self._check_completions()

        return self.queue.get_by_id(message['id'])


def run_orchestrator():
    """Run the orchestrator as a service."""
    config = WorkerConfig(
        max_workers=int(os.environ.get('MAX_WORKERS', 3)),
        poll_interval_seconds=float(os.environ.get('POLL_INTERVAL', 0.5)),
        worker_timeout_seconds=int(os.environ.get('WORKER_TIMEOUT', 600)),
        container_name=os.environ.get('PCP_CONTAINER', 'pcp-agent'),
        discord_webhook_url=os.environ.get('DISCORD_WEBHOOK_URL')
    )

    orchestrator = Orchestrator(config)
    orchestrator.start()


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PCP Orchestrator - Process Manager")
    parser.add_argument('--workers', type=int, default=3, help='Max concurrent workers')
    parser.add_argument('--poll-interval', type=float, default=0.5, help='Poll interval in seconds')
    parser.add_argument('--timeout', type=int, default=600, help='Worker timeout in seconds')
    parser.add_argument('--container', default='pcp-agent', help='Docker container name')
    parser.add_argument('--webhook', help='Discord webhook URL')
    parser.add_argument('--once', action='store_true', help='Process one message and exit')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = WorkerConfig(
        max_workers=args.workers,
        poll_interval_seconds=args.poll_interval,
        worker_timeout_seconds=args.timeout,
        container_name=args.container,
        discord_webhook_url=args.webhook
    )

    orchestrator = Orchestrator(config)

    if args.once:
        result = orchestrator.process_one()
        if result:
            print(f"Processed message {result['id']}: {result['status']}")
            if result.get('response'):
                print(f"Response: {result['response'][:200]}...")
        else:
            print("No pending messages")
    else:
        print(f"Starting orchestrator (workers={args.workers}, poll={args.poll_interval}s)")
        orchestrator.start()
