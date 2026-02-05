#!/usr/bin/env python3
"""
PCP Session Manager - Track and manage AI agent sessions.

Usage:
    from session_manager import SessionManager
    sm = SessionManager()

    # Register current session
    sm.register(project="alpha-trader", focus="backtesting momentum strategy")

    # Update focus
    sm.update_focus("now working on risk parameters")

    # List active sessions
    sessions = sm.list_active()

    # List recent sessions (past 24h)
    recent = sm.list_recent(hours=24)

    # Get session details
    session = sm.get_session(session_id)

    # Mark session complete
    sm.complete()

CLI:
    python session_manager.py list
    python session_manager.py list --recent
    python session_manager.py register -p PROJECT -f "focus description"
    python session_manager.py focus "new focus"
    python session_manager.py complete
    python session_manager.py dashboard
"""

import sqlite3
import os
import json
import subprocess
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import argparse

# Support both container and local development paths
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)) and os.path.exists(os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault")):
    VAULT_PATH = os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db")

# Session schema
SESSIONS_SCHEMA = """
-- Agent sessions tracking
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,              -- Claude session ID or generated UUID
    tty TEXT,                         -- Terminal (pts/X)
    pid INTEGER,                      -- Process ID

    -- Context
    project TEXT,                     -- Project name (alpha-trader, VC, etc.)
    project_path TEXT,                -- Full path to project
    focus TEXT,                       -- Current focus/task description

    -- Status
    status TEXT DEFAULT 'active',     -- active, idle, completed

    -- Timestamps
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,

    -- Stats
    message_count INTEGER DEFAULT 0,

    -- Extra data
    metadata TEXT                     -- JSON for extra info
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity_at);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);

-- Session events for history
CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,         -- started, focus_changed, captured, completed
    data TEXT,                        -- JSON event data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id);
"""


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(VAULT_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema():
    """Initialize sessions schema."""
    conn = get_db()
    conn.executescript(SESSIONS_SCHEMA)
    conn.commit()
    conn.close()


def get_current_tty() -> Optional[str]:
    """Get current terminal TTY."""
    try:
        result = subprocess.run(['tty'], capture_output=True, text=True)
        tty = result.stdout.strip()
        if tty and tty != 'not a tty':
            # Extract pts/X from /dev/pts/X
            if '/dev/' in tty:
                return tty.replace('/dev/', '')
            return tty
    except:
        pass
    return None


def get_current_pid() -> int:
    """Get current process ID."""
    return os.getpid()


def get_claude_session_id() -> Optional[str]:
    """Try to get Claude Code session ID from environment or process."""
    # Check environment variables that Claude might set
    session_id = os.environ.get('CLAUDE_SESSION_ID')
    if session_id:
        return session_id

    # Try to find from process info or generate one
    # For now, generate based on tty and timestamp
    tty = get_current_tty()
    if tty:
        return f"session_{tty.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return f"session_{get_current_pid()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def detect_project_from_cwd() -> tuple[Optional[str], Optional[str]]:
    """Detect project from current working directory."""
    cwd = os.getcwd()

    # Check if we're in a workspace project
    workspace_path = os.path.expanduser("~/Workspace")
    if cwd.startswith(workspace_path):
        rel_path = cwd[len(workspace_path):].strip('/')
        project_name = rel_path.split('/')[0] if rel_path else None
        if project_name:
            return project_name, os.path.join(workspace_path, project_name)

    return None, cwd


def get_running_claude_processes() -> List[Dict[str, Any]]:
    """Get list of running Claude Code processes."""
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )

        processes = []
        for line in result.stdout.split('\n'):
            if 'claude' in line.lower() and 'grep' not in line:
                parts = line.split()
                if len(parts) >= 11:
                    # Parse ps aux output
                    pid = int(parts[1])
                    tty = parts[6] if parts[6] != '?' else None

                    # Extract command
                    cmd = ' '.join(parts[10:])

                    # Check for --resume flag
                    is_resumed = '--resume' in cmd

                    processes.append({
                        'pid': pid,
                        'tty': tty,
                        'cmd': cmd,
                        'is_resumed': is_resumed,
                        'user': parts[0],
                        'cpu': parts[2],
                        'mem': parts[3],
                        'start': parts[8],
                        'time': parts[9]
                    })

        return processes
    except Exception as e:
        print(f"Error getting Claude processes: {e}")
        return []


class SessionManager:
    """Manage AI agent sessions."""

    def __init__(self):
        init_schema()
        self._session_id = None

    @property
    def session_id(self) -> str:
        """Get or generate current session ID."""
        if not self._session_id:
            self._session_id = get_claude_session_id()
        return self._session_id

    def register(
        self,
        project: Optional[str] = None,
        focus: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Register current session."""
        sid = session_id or self.session_id
        tty = get_current_tty()
        pid = get_current_pid()

        # Auto-detect project if not provided
        if not project:
            project, project_path = detect_project_from_cwd()
        else:
            project_path = os.path.expanduser(f"~/Workspace/{project}")
            if not os.path.exists(project_path):
                project_path = os.getcwd()

        conn = get_db()
        cursor = conn.cursor()

        # Check if session exists
        cursor.execute("SELECT id FROM sessions WHERE id = ?", (sid,))
        exists = cursor.fetchone()

        if exists:
            # Update existing
            cursor.execute("""
                UPDATE sessions
                SET tty = ?, pid = ?, project = ?, project_path = ?, focus = ?,
                    status = 'active', last_activity_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (tty, pid, project, project_path, focus, sid))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO sessions (id, tty, pid, project, project_path, focus, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (sid, tty, pid, project, project_path, focus))

            # Log event
            cursor.execute("""
                INSERT INTO session_events (session_id, event_type, data)
                VALUES (?, 'started', ?)
            """, (sid, json.dumps({'project': project, 'focus': focus})))

        conn.commit()
        conn.close()

        self._session_id = sid
        return sid

    def update_focus(self, focus: str, session_id: Optional[str] = None) -> bool:
        """Update current session focus."""
        sid = session_id or self.session_id

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions
            SET focus = ?, last_activity_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (focus, sid))

        # Log event
        cursor.execute("""
            INSERT INTO session_events (session_id, event_type, data)
            VALUES (?, 'focus_changed', ?)
        """, (sid, json.dumps({'focus': focus})))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        return success

    def heartbeat(self, session_id: Optional[str] = None):
        """Update last activity timestamp."""
        sid = session_id or self.session_id

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions
            SET last_activity_at = CURRENT_TIMESTAMP,
                message_count = message_count + 1
            WHERE id = ?
        """, (sid,))
        conn.commit()
        conn.close()

    def complete(self, session_id: Optional[str] = None) -> bool:
        """Mark session as completed."""
        sid = session_id or self.session_id

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions
            SET status = 'completed', ended_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (sid,))

        # Log event
        cursor.execute("""
            INSERT INTO session_events (session_id, event_type, data)
            VALUES (?, 'completed', '{}')
        """, (sid,))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        return success

    def list_active(self) -> List[Dict[str, Any]]:
        """List active sessions."""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM sessions
            WHERE status = 'active'
            ORDER BY last_activity_at DESC
        """)

        sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Enrich with process info
        running = get_running_claude_processes()
        running_ttys = {p['tty'] for p in running if p['tty']}
        running_pids = {p['pid'] for p in running}

        for session in sessions:
            session['is_running'] = (
                session['tty'] in running_ttys or
                session['pid'] in running_pids
            )
            # Calculate age
            if session['started_at']:
                started = datetime.fromisoformat(session['started_at'].replace('Z', '+00:00').replace('+00:00', ''))
                age = datetime.now() - started
                session['age_minutes'] = int(age.total_seconds() / 60)
                session['age_display'] = self._format_age(age)

        return sessions

    def list_recent(self, hours: int = 24) -> List[Dict[str, Any]]:
        """List recent sessions (completed within N hours)."""
        conn = get_db()
        cursor = conn.cursor()

        cutoff = datetime.now() - timedelta(hours=hours)

        cursor.execute("""
            SELECT * FROM sessions
            WHERE status = 'completed'
              AND ended_at > ?
            ORDER BY ended_at DESC
        """, (cutoff.isoformat(),))

        sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()

        for session in sessions:
            if session['ended_at']:
                ended = datetime.fromisoformat(session['ended_at'].replace('Z', '+00:00').replace('+00:00', ''))
                ago = datetime.now() - ended
                session['ended_ago'] = self._format_age(ago) + ' ago'

        return sessions

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_resume_command(self, session_id: str) -> str:
        """Get command to resume a session."""
        return f"claude --resume {session_id}"

    def cleanup_stale(self, hours: int = 48):
        """Mark stale sessions as completed."""
        conn = get_db()
        cursor = conn.cursor()

        cutoff = datetime.now() - timedelta(hours=hours)

        cursor.execute("""
            UPDATE sessions
            SET status = 'completed', ended_at = last_activity_at
            WHERE status = 'active' AND last_activity_at < ?
        """, (cutoff.isoformat(),))

        count = cursor.rowcount
        conn.commit()
        conn.close()

        return count

    def _format_age(self, delta: timedelta) -> str:
        """Format timedelta as human-readable string."""
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes}m" if minutes else f"{hours}h"
        else:
            days = total_seconds // 86400
            return f"{days}d"

    def sync_with_processes(self):
        """Sync session status with running processes."""
        running = get_running_claude_processes()
        running_ttys = {p['tty'] for p in running if p['tty']}
        running_pids = {p['pid'] for p in running}

        active = self.list_active()

        for session in active:
            is_running = (
                session['tty'] in running_ttys or
                session['pid'] in running_pids
            )

            if not is_running:
                # Mark as idle or completed based on age
                age_hours = session.get('age_minutes', 0) / 60
                if age_hours > 2:
                    self.complete(session['id'])

    def dashboard(self) -> str:
        """Generate dashboard view."""
        active = self.list_active()
        recent = self.list_recent(hours=24)

        lines = []

        # Header
        lines.append("=" * 70)
        lines.append(" ACTIVE SESSIONS")
        lines.append("=" * 70)

        if active:
            lines.append(f"{'#':<3} {'TTY':<10} {'PROJECT':<18} {'FOCUS':<25} {'AGE':<6}")
            lines.append("-" * 70)

            current_tty = get_current_tty()
            for i, s in enumerate(active, 1):
                marker = " <-YOU" if s['tty'] == current_tty else ""
                focus = (s['focus'] or '')[:24]
                age = s.get('age_display', '?')
                lines.append(f"{i:<3} {s['tty'] or '?':<10} {s['project'] or '?':<18} {focus:<25} {age:<6}{marker}")
        else:
            lines.append("  No active sessions")

        lines.append("")
        lines.append("=" * 70)
        lines.append(" RECENT (past 24h)")
        lines.append("=" * 70)

        if recent:
            lines.append(f"{'#':<3} {'SESSION':<15} {'PROJECT':<18} {'LAST FOCUS':<20} {'ENDED':<12}")
            lines.append("-" * 70)

            for i, s in enumerate(recent, len(active) + 1):
                sid_short = s['id'][:12] + '...' if len(s['id']) > 15 else s['id']
                focus = (s['focus'] or '')[:19]
                ended = s.get('ended_ago', '?')
                lines.append(f"{i:<3} {sid_short:<15} {s['project'] or '?':<18} {focus:<20} {ended:<12}")
        else:
            lines.append("  No recent sessions")

        lines.append("")
        lines.append("-" * 70)
        lines.append(" RESUME: claude --resume <session_id>")
        lines.append("=" * 70)

        return "\n".join(lines)


def main():
    """CLI interface."""
    parser = argparse.ArgumentParser(description="PCP Session Manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # list
    list_parser = subparsers.add_parser('list', help='List sessions')
    list_parser.add_argument('--recent', '-r', action='store_true', help='Include recent completed')
    list_parser.add_argument('--all', '-a', action='store_true', help='Show all (active + recent)')
    list_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # register
    reg_parser = subparsers.add_parser('register', help='Register current session')
    reg_parser.add_argument('--project', '-p', help='Project name')
    reg_parser.add_argument('--focus', '-f', help='Current focus')

    # focus
    focus_parser = subparsers.add_parser('focus', help='Update session focus')
    focus_parser.add_argument('focus', help='New focus description')

    # complete
    subparsers.add_parser('complete', help='Mark session complete')

    # dashboard
    subparsers.add_parser('dashboard', help='Show dashboard')

    # resume
    resume_parser = subparsers.add_parser('resume', help='Get resume command')
    resume_parser.add_argument('session_id', help='Session ID')

    # sync
    subparsers.add_parser('sync', help='Sync with running processes')

    # cleanup
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup stale sessions')
    cleanup_parser.add_argument('--hours', type=int, default=48, help='Hours threshold')

    args = parser.parse_args()
    sm = SessionManager()

    if args.command == 'list':
        if args.all or args.recent:
            active = sm.list_active()
            recent = sm.list_recent() if args.all or args.recent else []
            sessions = active + recent
        else:
            sessions = sm.list_active()

        if args.json:
            print(json.dumps(sessions, indent=2, default=str))
        else:
            if not sessions:
                print("No sessions found")
            else:
                print(f"{'ID':<20} {'TTY':<10} {'PROJECT':<15} {'FOCUS':<25} {'STATUS':<10}")
                print("-" * 80)
                for s in sessions:
                    focus = (s['focus'] or '')[:24]
                    print(f"{s['id'][:18]:<20} {s['tty'] or '?':<10} {s['project'] or '?':<15} {focus:<25} {s['status']:<10}")

    elif args.command == 'register':
        sid = sm.register(project=args.project, focus=args.focus)
        print(f"Registered session: {sid}")
        if args.project:
            print(f"Project: {args.project}")
        if args.focus:
            print(f"Focus: {args.focus}")

    elif args.command == 'focus':
        if sm.update_focus(args.focus):
            print(f"Focus updated: {args.focus}")
        else:
            print("Failed to update focus (session not found)")

    elif args.command == 'complete':
        if sm.complete():
            print("Session marked complete")
        else:
            print("Failed to complete session")

    elif args.command == 'dashboard' or args.command is None:
        # Try rich dashboard first, fallback to simple text
        try:
            from dashboard import render_dashboard
            render_dashboard(sm)
        except ImportError:
            print(sm.dashboard())

    elif args.command == 'resume':
        print(sm.get_resume_command(args.session_id))

    elif args.command == 'sync':
        sm.sync_with_processes()
        print("Synced with running processes")

    elif args.command == 'cleanup':
        count = sm.cleanup_stale(hours=args.hours)
        print(f"Cleaned up {count} stale sessions")


if __name__ == "__main__":
    main()
