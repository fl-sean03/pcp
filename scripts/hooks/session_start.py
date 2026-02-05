#!/usr/bin/env python3
"""
Claude Code Session Start Hook - Auto-registers sessions in PCP.

This hook runs automatically when a Claude Code session starts.
It detects the project from CWD and registers the session.

Install by adding to ~/.claude/settings.json:
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "python3 /workspace/scripts/hooks/session_start.py"
      }
    ]
  }
}
"""

import os
import sys
import json
from datetime import datetime

# Add PCP scripts to path
sys.path.insert(0, '/workspace/scripts')

from session_manager import SessionManager, detect_project_from_cwd, get_current_tty


def main():
    """Auto-register session on start."""
    try:
        sm = SessionManager()

        # Detect project from current directory
        project, project_path = detect_project_from_cwd()

        # Get session info from environment if available
        session_id = os.environ.get('CLAUDE_SESSION_ID')

        # Register the session
        sid = sm.register(
            project=project,
            focus=f"Started in {project or 'home'}",
            session_id=session_id
        )

        # Log to file for debugging
        log_file = '/workspace/logs/session_hooks.log'
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        with open(log_file, 'a') as f:
            f.write(json.dumps({
                'timestamp': datetime.now().isoformat(),
                'event': 'session_start',
                'session_id': sid,
                'project': project,
                'project_path': project_path,
                'tty': get_current_tty(),
                'cwd': os.getcwd()
            }) + '\n')

        # Don't print anything - hooks should be silent

    except Exception as e:
        # Log error but don't fail the session start
        try:
            log_file = '/workspace/logs/session_hooks.log'
            with open(log_file, 'a') as f:
                f.write(json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'event': 'session_start_error',
                    'error': str(e)
                }) + '\n')
        except:
            pass


if __name__ == "__main__":
    main()
