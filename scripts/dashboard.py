#!/usr/bin/env python3
"""
PCP Session Dashboard - Rich TUI for session management.

A beautiful terminal dashboard showing active and recent Claude Code sessions.

Usage:
    python dashboard.py              # Interactive dashboard
    python dashboard.py --once       # Single render (no auto-refresh)
    python dashboard.py --watch      # Auto-refresh every 5 seconds

Or via CLI:
    sessions dashboard
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Rich imports
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.style import Style
from rich import box

# Add PCP scripts to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from session_manager import SessionManager, get_current_tty, get_running_claude_processes


console = Console()


def create_active_sessions_table(sessions: List[Dict], current_tty: str) -> Table:
    """Create a rich table for active sessions."""
    table = Table(
        title="[bold cyan]Active Sessions[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
        expand=True
    )

    table.add_column("#", style="dim", width=3)
    table.add_column("TTY", style="green", width=10)
    table.add_column("Project", style="yellow", width=18)
    table.add_column("Focus", style="white", width=30)
    table.add_column("Age", style="cyan", width=8)
    table.add_column("", width=6)  # Marker column

    if not sessions:
        table.add_row("", "[dim]No active sessions[/dim]", "", "", "", "")
    else:
        for i, s in enumerate(sessions, 1):
            tty = s.get('tty') or '?'
            project = s.get('project') or '?'
            focus = (s.get('focus') or '')[:29]
            age = s.get('age_display', '?')

            # Highlight current session
            is_current = tty == current_tty
            marker = "[bold green]<-YOU[/bold green]" if is_current else ""

            # Style based on running status
            row_style = "bold" if is_current else ""
            if not s.get('is_running', True):
                row_style = "dim"
                marker = "[dim yellow]idle?[/dim yellow]"

            table.add_row(
                str(i),
                tty,
                project,
                focus,
                age,
                marker,
                style=row_style
            )

    return table


def create_recent_sessions_table(sessions: List[Dict]) -> Table:
    """Create a rich table for recent sessions."""
    table = Table(
        title="[bold blue]Recent Sessions (24h)[/bold blue]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold blue",
        border_style="blue",
        expand=True
    )

    table.add_column("#", style="dim", width=3)
    table.add_column("Session ID", style="cyan", width=15)
    table.add_column("Project", style="yellow", width=18)
    table.add_column("Last Focus", style="white", width=25)
    table.add_column("Ended", style="magenta", width=12)

    if not sessions:
        table.add_row("", "[dim]No recent sessions[/dim]", "", "", "")
    else:
        for i, s in enumerate(sessions, 1):
            sid = s.get('id', '?')
            sid_short = sid[:12] + '...' if len(sid) > 15 else sid
            project = s.get('project') or '?'
            focus = (s.get('focus') or '')[:24]
            ended = s.get('ended_ago', '?')

            table.add_row(
                str(i),
                sid_short,
                project,
                focus,
                ended
            )

    return table


def create_running_processes_table(processes: List[Dict]) -> Table:
    """Create a table showing running Claude processes."""
    table = Table(
        title="[bold green]Running Claude Processes[/bold green]",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold green",
        expand=True
    )

    table.add_column("PID", style="cyan", width=8)
    table.add_column("TTY", style="green", width=10)
    table.add_column("CPU", style="yellow", width=6)
    table.add_column("MEM", style="yellow", width=6)
    table.add_column("Time", style="magenta", width=10)
    table.add_column("Resumed", style="blue", width=8)

    if not processes:
        table.add_row("[dim]No Claude processes running[/dim]", "", "", "", "", "")
    else:
        for p in processes[:10]:  # Limit to 10
            resumed = "[green]Yes[/green]" if p.get('is_resumed') else "[dim]No[/dim]"
            table.add_row(
                str(p.get('pid', '?')),
                p.get('tty') or '?',
                p.get('cpu', '?'),
                p.get('mem', '?'),
                p.get('time', '?'),
                resumed
            )

    return table


def create_help_panel() -> Panel:
    """Create help panel with commands."""
    help_text = Text()
    help_text.append("Quick Commands:\n", style="bold cyan")
    help_text.append("  sessions list", style="green")
    help_text.append(" - List all sessions\n", style="dim")
    help_text.append("  sessions register -p NAME", style="green")
    help_text.append(" - Register with project\n", style="dim")
    help_text.append("  sessions focus \"text\"", style="green")
    help_text.append(" - Update focus\n", style="dim")
    help_text.append("  claude --resume ID", style="green")
    help_text.append(" - Resume a session\n", style="dim")
    help_text.append("\n")
    help_text.append("PCP Commands:\n", style="bold cyan")
    help_text.append("  pcp capture \"text\"", style="green")
    help_text.append(" - Store in vault\n", style="dim")
    help_text.append("  pcp search \"query\"", style="green")
    help_text.append(" - Search vault\n", style="dim")
    help_text.append("  pcp brief", style="green")
    help_text.append(" - Daily brief\n", style="dim")

    return Panel(
        help_text,
        title="[bold]Help[/bold]",
        border_style="dim",
        box=box.ROUNDED
    )


def create_stats_panel(active_count: int, recent_count: int, process_count: int) -> Panel:
    """Create stats panel."""
    stats = Text()
    stats.append(f"Active: ", style="cyan")
    stats.append(f"{active_count}", style="bold green")
    stats.append(f"  Recent: ", style="cyan")
    stats.append(f"{recent_count}", style="bold blue")
    stats.append(f"  Processes: ", style="cyan")
    stats.append(f"{process_count}", style="bold yellow")

    return Panel(
        stats,
        title="[bold]Stats[/bold]",
        border_style="dim",
        box=box.ROUNDED
    )


def render_dashboard(sm: SessionManager, show_processes: bool = True) -> None:
    """Render the full dashboard."""
    current_tty = get_current_tty()

    # Get data
    active = sm.list_active()
    recent = sm.list_recent(hours=24)
    processes = get_running_claude_processes() if show_processes else []

    # Header
    console.print()
    console.print(
        Panel(
            "[bold cyan]PCP Session Dashboard[/bold cyan]\n"
            f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            box=box.DOUBLE,
            border_style="cyan"
        )
    )
    console.print()

    # Stats
    console.print(create_stats_panel(len(active), len(recent), len(processes)))
    console.print()

    # Active sessions
    console.print(create_active_sessions_table(active, current_tty))
    console.print()

    # Recent sessions
    if recent:
        console.print(create_recent_sessions_table(recent))
        console.print()

    # Running processes (optional)
    if show_processes and processes:
        console.print(create_running_processes_table(processes))
        console.print()

    # Help
    console.print(create_help_panel())
    console.print()


def watch_dashboard(sm: SessionManager, interval: int = 5) -> None:
    """Auto-refreshing dashboard."""
    console.print("[bold cyan]Starting live dashboard (Ctrl+C to exit)...[/bold cyan]")
    console.print()

    try:
        while True:
            console.clear()
            render_dashboard(sm)
            console.print(f"[dim]Auto-refresh in {interval}s (Ctrl+C to exit)[/dim]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="PCP Session Dashboard")
    parser.add_argument('--once', '-1', action='store_true',
                        help='Single render (no refresh)')
    parser.add_argument('--watch', '-w', action='store_true',
                        help='Auto-refresh mode')
    parser.add_argument('--interval', '-i', type=int, default=5,
                        help='Refresh interval in seconds (default: 5)')
    parser.add_argument('--no-processes', action='store_true',
                        help='Hide running processes section')

    args = parser.parse_args()

    sm = SessionManager()

    if args.watch:
        watch_dashboard(sm, interval=args.interval)
    else:
        render_dashboard(sm, show_processes=not args.no_processes)


if __name__ == "__main__":
    main()
