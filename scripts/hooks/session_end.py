#!/usr/bin/env python3
"""
Claude Code Session End Hook - Marks sessions as completed in PCP.

This hook runs automatically when a Claude Code session ends.

Install by adding to ~/.claude/settings.json:
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "python3 /workspace/scripts/hooks/session_end.py"
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

from session_manager import SessionManager


def main():
    """Mark session as completed on end."""
    try:
        sm = SessionManager()

        # Complete the current session
        sm.complete()

        # Log for debugging
        log_file = '/workspace/logs/session_hooks.log'
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        with open(log_file, 'a') as f:
            f.write(json.dumps({
                'timestamp': datetime.now().isoformat(),
                'event': 'session_end',
                'session_id': sm.session_id
            }) + '\n')

    except Exception as e:
        # Log error but don't fail
        try:
            log_file = '/workspace/logs/session_hooks.log'
            with open(log_file, 'a') as f:
                f.write(json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'event': 'session_end_error',
                    'error': str(e)
                }) + '\n')
        except:
            pass


if __name__ == "__main__":
    main()
