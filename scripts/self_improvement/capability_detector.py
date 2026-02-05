"""
Capability gap detection for the self-improvement system.

This module detects when a task cannot be completed due to missing capabilities
and logs these gaps for analysis and resolution.
"""

import os
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from .capability_patterns import (
    CAPABILITY_PATTERNS,
    CLI_TOOL_INSTALLATIONS,
    find_matching_patterns,
    get_pattern_for_gap,
    GAP_TYPE_FILE_PROCESSING,
    GAP_TYPE_SERVICE_INTEGRATION,
    GAP_TYPE_CLOUD_PROVIDER,
    GAP_TYPE_CLI_TOOL,
    GAP_TYPE_API_ACCESS,
    GAP_TYPE_UNKNOWN,
)
from .exceptions import CapabilityGapError


# Database path - support dev environment
def _get_vault_path():
    """Get vault path, handling dev environment."""
    # Environment variable takes precedence
    if os.environ.get("PCP_VAULT_PATH"):
        return os.environ.get("PCP_VAULT_PATH")

    # Check for container path
    if os.path.exists("/workspace/vault"):
        return "/workspace/vault"

    # Check for dev path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dev_vault = os.path.join(script_dir, "..", "..", "vault")
    if os.path.exists(dev_vault):
        return os.path.abspath(dev_vault)

    # Default
    return "/workspace/vault"


VAULT_PATH = _get_vault_path()
DB_PATH = os.path.join(VAULT_PATH, "vault.db")


def get_db_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_capability_gaps_table():
    """Create the capability_gaps table if it doesn't exist."""
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS capability_gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gap_type TEXT NOT NULL,
                gap_description TEXT NOT NULL,
                pattern_id TEXT,

                -- Context
                original_task TEXT,
                error_message TEXT,
                file_type TEXT,
                service_name TEXT,

                -- Resolution tracking
                status TEXT DEFAULT 'detected',
                risk_level TEXT,
                resolution_method TEXT,
                resolution_details TEXT,
                skill_created TEXT,

                -- User interaction
                user_prompted BOOLEAN DEFAULT FALSE,
                user_approved BOOLEAN,
                user_response TEXT,

                -- Timestamps
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,

                -- Metadata
                context_json TEXT,
                attempts INTEGER DEFAULT 0
            )
        """)

        # Create indexes for common queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_capability_gaps_status
            ON capability_gaps(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_capability_gaps_type
            ON capability_gaps(gap_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_capability_gaps_pattern
            ON capability_gaps(pattern_id)
        """)

        conn.commit()
    finally:
        conn.close()


def detect_capability_gap(
    task_description: str = "",
    error_message: str = "",
    file_path: str = "",
    mime_type: str = "",
    context: Optional[Dict[str, Any]] = None
) -> Optional[CapabilityGapError]:
    """
    Analyze a failed task or error to detect capability gaps.

    Args:
        task_description: What the user was trying to do
        error_message: Any error message encountered
        file_path: Path to file being processed (if applicable)
        mime_type: MIME type of file (if applicable)
        context: Additional context dictionary

    Returns:
        CapabilityGapError if a gap is detected, None otherwise
    """
    context = context or {}

    # Extract file extension if file_path provided
    extension = ""
    if file_path:
        _, extension = os.path.splitext(file_path)

    # Find matching patterns
    matching_patterns = find_matching_patterns(
        text=task_description,
        mime_type=mime_type,
        extension=extension,
        error_message=error_message
    )

    if not matching_patterns:
        # Try to detect CLI tool gaps from error message
        cli_gap = _detect_cli_tool_gap(error_message)
        if cli_gap:
            return cli_gap

        # Try to detect generic gaps
        generic_gap = _detect_generic_gap(task_description, error_message)
        if generic_gap:
            return generic_gap

        return None

    # Use the first matching pattern (most specific)
    pattern_id = matching_patterns[0]
    pattern = get_pattern_for_gap(pattern_id)

    if not pattern:
        return None

    # Build the capability gap error
    gap_context = {
        "pattern_id": pattern_id,
        "file_path": file_path,
        "mime_type": mime_type,
        "extension": extension,
        **context
    }

    return CapabilityGapError(
        gap_type=pattern.get("gap_type", GAP_TYPE_UNKNOWN),
        gap_description=pattern.get("description", f"Missing capability: {pattern_id}"),
        original_task=task_description,
        context=gap_context,
        suggested_solutions=pattern.get("suggested_solutions", []),
        failure_pattern=pattern_id
    )


def _detect_cli_tool_gap(error_message: str) -> Optional[CapabilityGapError]:
    """Detect if error is due to a missing CLI tool."""
    if not error_message:
        return None

    error_lower = error_message.lower()

    # Common error patterns for missing commands
    patterns = [
        (r"command not found: (\w+)", 1),
        (r"'(\w+)' is not recognized", 1),
        (r"(\w+): command not found", 1),
        (r"No such file or directory.*?/(\w+)", 1),
        (r"executable file not found.*?(\w+)", 1),
    ]

    for pattern, group in patterns:
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            tool_name = match.group(group).lower()

            # Check if we know how to install this tool
            install_info = CLI_TOOL_INSTALLATIONS.get(tool_name, {})

            solutions = []
            if install_info:
                solutions.append({
                    "name": tool_name,
                    "type": "system_package",
                    "install_command": install_info.get("apt", f"sudo apt-get install -y {tool_name}"),
                    "description": install_info.get("description", f"Install {tool_name}"),
                    "test_command": f"which {tool_name}",
                })

            return CapabilityGapError(
                gap_type=GAP_TYPE_CLI_TOOL,
                gap_description=f"Missing CLI tool: {tool_name}",
                original_task="",
                context={"tool_name": tool_name, "install_info": install_info},
                suggested_solutions=solutions,
                failure_pattern="missing_cli_tool"
            )

    return None


def _detect_generic_gap(task_description: str, error_message: str) -> Optional[CapabilityGapError]:
    """Detect generic capability gaps from task description or error."""
    combined = f"{task_description} {error_message}".lower()

    # API/Authentication errors
    if any(term in combined for term in ["api key", "authentication", "unauthorized", "401", "403"]):
        return CapabilityGapError(
            gap_type=GAP_TYPE_API_ACCESS,
            gap_description="API authentication required",
            original_task=task_description,
            context={"error": error_message},
            suggested_solutions=[],
            failure_pattern="api_auth_required"
        )

    # Module not found errors
    module_match = re.search(r"no module named ['\"]?(\w+)['\"]?", combined)
    if module_match:
        module_name = module_match.group(1)
        return CapabilityGapError(
            gap_type=GAP_TYPE_CLI_TOOL,
            gap_description=f"Missing Python module: {module_name}",
            original_task=task_description,
            context={"module_name": module_name},
            suggested_solutions=[{
                "name": module_name,
                "type": "python_package",
                "install_command": f"pip install {module_name}",
                "description": f"Install {module_name} Python package",
                "test_command": f'python -c "import {module_name}; print(\'OK\')"',
            }],
            failure_pattern="missing_python_module"
        )

    return None


def log_capability_gap(
    gap: CapabilityGapError,
    status: str = "detected",
    risk_level: Optional[str] = None
) -> int:
    """
    Log a capability gap to the database for tracking.

    Args:
        gap: The CapabilityGapError to log
        status: Initial status (detected, resolving, resolved, failed, user_pending)
        risk_level: Risk level if already assessed

    Returns:
        The ID of the logged gap
    """
    ensure_capability_gaps_table()

    import json

    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO capability_gaps (
                gap_type, gap_description, pattern_id,
                original_task, error_message, file_type, service_name,
                status, risk_level, context_json, detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            gap.gap_type,
            gap.gap_description,
            gap.failure_pattern,
            gap.original_task,
            gap.context.get("error", ""),
            gap.context.get("extension", gap.context.get("mime_type", "")),
            gap.context.get("service_name", ""),
            status,
            risk_level,
            json.dumps(gap.to_dict()),
            datetime.now().isoformat()
        ))

        gap_id = cursor.lastrowid
        conn.commit()
        return gap_id

    finally:
        conn.close()


def update_gap_status(
    gap_id: int,
    status: str,
    resolution_method: Optional[str] = None,
    resolution_details: Optional[str] = None,
    skill_created: Optional[str] = None,
    user_approved: Optional[bool] = None,
    user_response: Optional[str] = None
):
    """Update the status of a capability gap."""
    ensure_capability_gaps_table()

    conn = get_db_connection()
    try:
        updates = ["status = ?", "attempts = attempts + 1"]
        params = [status]

        if resolution_method:
            updates.append("resolution_method = ?")
            params.append(resolution_method)

        if resolution_details:
            updates.append("resolution_details = ?")
            params.append(resolution_details)

        if skill_created:
            updates.append("skill_created = ?")
            params.append(skill_created)

        if user_approved is not None:
            updates.append("user_approved = ?")
            updates.append("user_prompted = TRUE")
            params.append(user_approved)

        if user_response:
            updates.append("user_response = ?")
            params.append(user_response)

        if status == "resolved":
            updates.append("resolved_at = ?")
            params.append(datetime.now().isoformat())

        params.append(gap_id)

        conn.execute(f"""
            UPDATE capability_gaps
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        conn.commit()
    finally:
        conn.close()


def get_gap_by_id(gap_id: int) -> Optional[Dict[str, Any]]:
    """Get a capability gap by ID."""
    ensure_capability_gaps_table()

    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM capability_gaps WHERE id = ?",
            (gap_id,)
        ).fetchone()

        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_gaps_by_status(status: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get capability gaps by status."""
    ensure_capability_gaps_table()

    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM capability_gaps
            WHERE status = ?
            ORDER BY detected_at DESC
            LIMIT ?
        """, (status, limit)).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_similar_gaps(pattern_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get similar capability gaps by pattern ID."""
    ensure_capability_gaps_table()

    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM capability_gaps
            WHERE pattern_id = ?
            ORDER BY detected_at DESC
            LIMIT ?
        """, (pattern_id, limit)).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_gap_statistics() -> Dict[str, Any]:
    """Get statistics about capability gaps."""
    ensure_capability_gaps_table()

    conn = get_db_connection()
    try:
        stats = {}

        # Total gaps
        stats["total"] = conn.execute(
            "SELECT COUNT(*) FROM capability_gaps"
        ).fetchone()[0]

        # By status
        status_rows = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM capability_gaps
            GROUP BY status
        """).fetchall()
        stats["by_status"] = {row["status"]: row["count"] for row in status_rows}

        # By type
        type_rows = conn.execute("""
            SELECT gap_type, COUNT(*) as count
            FROM capability_gaps
            GROUP BY gap_type
        """).fetchall()
        stats["by_type"] = {row["gap_type"]: row["count"] for row in type_rows}

        # Resolution rate
        resolved = stats["by_status"].get("resolved", 0)
        stats["resolution_rate"] = resolved / stats["total"] if stats["total"] > 0 else 0

        # Most common patterns
        pattern_rows = conn.execute("""
            SELECT pattern_id, COUNT(*) as count
            FROM capability_gaps
            WHERE pattern_id IS NOT NULL
            GROUP BY pattern_id
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()
        stats["top_patterns"] = [(row["pattern_id"], row["count"]) for row in pattern_rows]

        return stats

    finally:
        conn.close()


def check_existing_capability(pattern_id: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a capability for this pattern has already been acquired.

    Returns:
        Tuple of (has_capability, skill_name or None)
    """
    # Check if there's a resolved gap with a skill created
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT skill_created FROM capability_gaps
            WHERE pattern_id = ? AND status = 'resolved' AND skill_created IS NOT NULL
            ORDER BY resolved_at DESC
            LIMIT 1
        """, (pattern_id,)).fetchone()

        if row and row["skill_created"]:
            # Verify the skill still exists
            skill_path = f"/workspace/.claude/skills/{row['skill_created']}"
            if os.path.exists(skill_path):
                return True, row["skill_created"]

        return False, None

    finally:
        conn.close()


# CLI interface
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Capability gap detection")
    subparsers = parser.add_subparsers(dest="command")

    # Detect command
    detect_parser = subparsers.add_parser("detect", help="Detect capability gap")
    detect_parser.add_argument("--task", default="", help="Task description")
    detect_parser.add_argument("--error", default="", help="Error message")
    detect_parser.add_argument("--file", default="", help="File path")
    detect_parser.add_argument("--mime", default="", help="MIME type")

    # List command
    list_parser = subparsers.add_parser("list", help="List gaps")
    list_parser.add_argument("--status", default="detected", help="Filter by status")
    list_parser.add_argument("--limit", type=int, default=20, help="Limit results")

    # Stats command
    subparsers.add_parser("stats", help="Show gap statistics")

    # Init command
    subparsers.add_parser("init", help="Initialize database table")

    args = parser.parse_args()

    if args.command == "detect":
        gap = detect_capability_gap(
            task_description=args.task,
            error_message=args.error,
            file_path=args.file,
            mime_type=args.mime
        )
        if gap:
            print(json.dumps(gap.to_dict(), indent=2))
        else:
            print("No capability gap detected")

    elif args.command == "list":
        gaps = get_gaps_by_status(args.status, args.limit)
        print(json.dumps(gaps, indent=2, default=str))

    elif args.command == "stats":
        stats = get_gap_statistics()
        print(json.dumps(stats, indent=2))

    elif args.command == "init":
        ensure_capability_gaps_table()
        print("Capability gaps table initialized")

    else:
        parser.print_help()
