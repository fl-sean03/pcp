#!/usr/bin/env python3
"""
Subagent Result Handler - Hook script for processing subagent completion.

This script is called by Claude Code's SubagentStop hook when PCP subagents complete.
It stores results in PCP's vault for persistence across sessions.

Usage (as hook):
    Called automatically by Claude Code when subagent completes.
    Input is JSON via stdin with subagent execution details.

Usage (CLI):
    python subagent_result_handler.py --agent-id ABC123 --status completed --summary "Did X, Y, Z"
"""

import os
import sys
import json
import argparse
from datetime import datetime

# Add scripts directory to path for imports
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from task_delegation import complete_subagent_execution, get_task, complete_task, process_chain_completion

# PCP subagent types we track
PCP_SUBAGENTS = {
    "pcp-worker",
    "homework-transcriber",
    "research-agent",
    "twitter-curator",
    "overleaf-sync"
}


def handle_subagent_stop(input_data: dict) -> dict:
    """
    Process a SubagentStop hook event.

    Args:
        input_data: Dict from Claude Code with:
            - agent_id: The subagent's agentId
            - agent_type: Type of subagent
            - status: Final status (completed, failed, paused)
            - result: Result/summary from the subagent (if available)
            - error: Error message (if failed)

    Returns:
        Dict with processing result
    """
    agent_id = input_data.get("agent_id", "unknown")
    agent_type = input_data.get("agent_type", "unknown")
    status = input_data.get("status", "completed")
    result = input_data.get("result", "")
    error = input_data.get("error")

    # Only process PCP subagents
    if agent_type not in PCP_SUBAGENTS:
        return {
            "processed": False,
            "reason": f"Not a PCP subagent: {agent_type}"
        }

    # Update subagent execution record
    result_summary = error if error else (result[:500] if result else None)
    complete_subagent_execution(
        agent_id=agent_id,
        result_summary=result_summary,
        status="failed" if error else status
    )

    # Store significant results in PCP vault
    stored_capture = None
    if result and len(result) > 50:
        try:
            from vault_v2 import store_capture
            capture_id = store_capture(
                content=f"[Subagent: {agent_type}]\n\n{result[:1000]}",
                capture_type="note",
                entities={"topics": [agent_type, "subagent-result", "automated"]}
            )
            stored_capture = capture_id
        except Exception as e:
            # Non-critical - just log
            print(f"Warning: Could not store capture: {e}", file=sys.stderr)

    # Check if this was linked to a delegated task and update it
    linked_task = _find_linked_task(agent_id)
    if linked_task:
        if error:
            complete_task(linked_task["id"], error=error)
        else:
            complete_task(linked_task["id"], result={"summary": result_summary})

        # Process chain completion (triggers dependent tasks)
        process_chain_completion(linked_task["id"])

    return {
        "processed": True,
        "agent_id": agent_id,
        "agent_type": agent_type,
        "status": status,
        "stored_capture": stored_capture,
        "linked_task_id": linked_task["id"] if linked_task else None
    }


def _find_linked_task(agent_id: str) -> dict:
    """Find a delegated task linked to this subagent."""
    try:
        import sqlite3
        VAULT_PATH = "/workspace/vault/vault.db"
        if not os.path.exists(os.path.dirname(VAULT_PATH)):
            VAULT_PATH = os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db")

        conn = sqlite3.connect(VAULT_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM delegated_tasks WHERE subagent_id = ?",
            (agent_id,)
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None
    except Exception:
        return None


def main():
    """Main entry point for both hook and CLI usage."""
    parser = argparse.ArgumentParser(description="Handle subagent completion")
    parser.add_argument("--agent-id", help="Agent ID")
    parser.add_argument("--agent-type", help="Agent type")
    parser.add_argument("--status", default="completed", help="Final status")
    parser.add_argument("--summary", help="Result summary")
    parser.add_argument("--error", help="Error message if failed")
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin (hook mode)")

    args = parser.parse_args()

    # Determine input source
    if args.stdin or not sys.stdin.isatty():
        # Hook mode: read JSON from stdin
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Invalid JSON on stdin", file=sys.stderr)
            return 1
    elif args.agent_id:
        # CLI mode
        input_data = {
            "agent_id": args.agent_id,
            "agent_type": args.agent_type or "unknown",
            "status": args.status,
            "result": args.summary,
            "error": args.error
        }
    else:
        parser.print_help()
        return 1

    result = handle_subagent_stop(input_data)

    if result.get("processed"):
        print(f"Processed subagent completion: {result['agent_type']} ({result['agent_id'][:8]}...)")
        if result.get("stored_capture"):
            print(f"  Stored capture: #{result['stored_capture']}")
        if result.get("linked_task_id"):
            print(f"  Updated task: #{result['linked_task_id']}")
    else:
        print(f"Skipped: {result.get('reason', 'unknown')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
