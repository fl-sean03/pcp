#!/usr/bin/env python3
"""
PCP Core Sync - Bidirectional sync between PCP database and OneDrive Core docs.

This script:
1. CORE → PCP: Reads Core docs from OneDrive and updates PCP database
2. PCP → CORE: Reads PCP database and updates Core docs in OneDrive
3. DISCOVERY: Scans OneDrive for important docs and indexes them

Usage:
    python core_sync.py                    # Full bidirectional sync
    python core_sync.py --core-to-pcp      # Only sync Core → PCP
    python core_sync.py --pcp-to-core      # Only sync PCP → Core
    python core_sync.py --discovery        # Only scan for new docs
    python core_sync.py --report           # Generate sync report only
    python core_sync.py --dry-run          # Show what would be synced
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Database path
DB_PATH = Path(__file__).parent.parent / "vault" / "vault.db"

# OneDrive Core docs path
CORE_PATH = "Documents/Core"

# Core doc files to sync
CORE_FILES = ["PROJECTS.md", "PEOPLE.md", "GOALS.md", "RESEARCH.md", "SKILLS.md"]


def get_db():
    """Get database connection."""
    return sqlite3.connect(str(DB_PATH))


def run_rclone(cmd: List[str]) -> Tuple[bool, str]:
    """Run rclone command and return (success, output)."""
    full_cmd = ["rclone"] + cmd
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def read_onedrive_file(path: str) -> Optional[str]:
    """Read a file from OneDrive."""
    success, output = run_rclone(["cat", f"onedrive:{path}"])
    return output if success else None


def write_onedrive_file(path: str, content: str) -> bool:
    """Write content to OneDrive file."""
    # Write to temp file first
    temp_path = f"/tmp/core_sync_{Path(path).name}"
    with open(temp_path, "w") as f:
        f.write(content)

    success, _ = run_rclone(["copyto", temp_path, f"onedrive:{path}"])
    os.remove(temp_path)
    return success


def parse_projects_md(content: str) -> List[Dict]:
    """Parse PROJECTS.md into structured data."""
    projects = []
    current_project = None
    in_table = False

    lines = content.split("\n")
    for i, line in enumerate(lines):
        # New project heading
        if line.startswith("### "):
            if current_project:
                projects.append(current_project)
            name = line[4:].strip()
            current_project = {"name": name, "status": "active", "description": ""}
            in_table = False

        # Table row
        elif current_project and "|" in line and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                field = parts[1].replace("**", "").lower()
                value = parts[2].replace("**", "")

                if "status" in field:
                    current_project["status"] = value.lower()
                elif "type" in field:
                    current_project["type"] = value
                elif "focus" in field:
                    current_project["focus"] = value
                elif "description" in field:
                    current_project["description"] = value

        # Description paragraph
        elif current_project and line.startswith("**Description**:"):
            current_project["description"] = line.replace("**Description**:", "").strip()

    if current_project:
        projects.append(current_project)

    return projects


def parse_people_md(content: str) -> List[Dict]:
    """Parse PEOPLE.md into structured data."""
    people = []
    current_person = None

    lines = content.split("\n")
    for line in lines:
        if line.startswith("### "):
            if current_person:
                people.append(current_person)
            name = line[4:].strip()
            current_person = {"name": name, "organization": "", "relationship": "", "context": ""}

        elif current_person and "|" in line and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                field = parts[1].replace("**", "").lower()
                value = parts[2].replace("**", "")

                if "institution" in field or "organization" in field:
                    current_person["organization"] = value
                elif "role" in field:
                    current_person["relationship"] = value
                elif "relationship" in field:
                    current_person["context"] = value

    if current_person:
        people.append(current_person)

    return people


def sync_core_to_pcp(dry_run: bool = False) -> Dict:
    """Sync OneDrive Core docs to PCP database."""
    report = {"projects_added": 0, "projects_updated": 0, "people_added": 0, "people_updated": 0}

    conn = get_db()
    c = conn.cursor()

    # Sync PROJECTS.md
    projects_content = read_onedrive_file(f"{CORE_PATH}/PROJECTS.md")
    if projects_content:
        projects = parse_projects_md(projects_content)

        for proj in projects:
            # Check if exists
            c.execute("SELECT id, description FROM projects WHERE name = ?", (proj["name"],))
            existing = c.fetchone()

            if existing:
                # Update if different
                if not dry_run:
                    desc = proj.get("description") or proj.get("focus", "")
                    c.execute("UPDATE projects SET description = ?, status = ? WHERE name = ?",
                              (desc, proj["status"], proj["name"]))
                report["projects_updated"] += 1
            else:
                # Insert new
                if not dry_run:
                    desc = proj.get("description") or proj.get("focus", "")
                    c.execute("""
                        INSERT INTO projects (name, description, status, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (proj["name"], desc, proj["status"], datetime.now().isoformat()))
                report["projects_added"] += 1

    # Sync PEOPLE.md
    people_content = read_onedrive_file(f"{CORE_PATH}/PEOPLE.md")
    if people_content:
        people = parse_people_md(people_content)

        for person in people:
            # Check if exists
            c.execute("SELECT id FROM people WHERE name = ?", (person["name"],))
            existing = c.fetchone()

            if existing:
                if not dry_run:
                    c.execute("""
                        UPDATE people SET organization = ?, relationship = ?, context = ?
                        WHERE name = ?
                    """, (person["organization"], person["relationship"],
                          person["context"], person["name"]))
                report["people_updated"] += 1
            else:
                if not dry_run:
                    c.execute("""
                        INSERT INTO people (name, organization, relationship, context, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (person["name"], person["organization"], person["relationship"],
                          person["context"], datetime.now().isoformat()))
                report["people_added"] += 1

    if not dry_run:
        conn.commit()
    conn.close()

    return report


def sync_pcp_to_core(dry_run: bool = False) -> Dict:
    """Sync PCP database to OneDrive Core docs."""
    report = {"projects_synced": 0, "people_synced": 0}

    conn = get_db()
    c = conn.cursor()

    # Read existing PROJECTS.md
    projects_content = read_onedrive_file(f"{CORE_PATH}/PROJECTS.md")
    if not projects_content:
        conn.close()
        return report

    existing_projects = parse_projects_md(projects_content)
    existing_names = {p["name"] for p in existing_projects}

    # Get PCP projects not in Core
    c.execute("SELECT name, description, status FROM projects WHERE status = 'active'")
    pcp_projects = c.fetchall()

    new_projects = []
    for name, desc, status in pcp_projects:
        if name not in existing_names:
            new_projects.append({"name": name, "description": desc, "status": status})

    # Append new projects to PROJECTS.md
    if new_projects and not dry_run:
        additions = "\n\n---\n\n## Recently Added from PCP\n\n"
        for proj in new_projects:
            additions += f"""### {proj['name']}
| Field | Value |
|-------|-------|
| **Status** | {proj['status'].capitalize()} |
| **Description** | {proj['description'] or 'TBD'} |

---

"""

        updated_content = projects_content.rstrip() + additions
        write_onedrive_file(f"{CORE_PATH}/PROJECTS.md", updated_content)
        report["projects_synced"] = len(new_projects)
    elif new_projects:
        report["projects_synced"] = len(new_projects)

    # Similar for PEOPLE.md
    people_content = read_onedrive_file(f"{CORE_PATH}/PEOPLE.md")
    if people_content:
        existing_people = parse_people_md(people_content)
        existing_names = {p["name"] for p in existing_people}

        c.execute("SELECT name, organization, relationship, context FROM people")
        pcp_people = c.fetchall()

        new_people = []
        for name, org, rel, ctx in pcp_people:
            if name not in existing_names and not name.startswith("E2E"):
                new_people.append({"name": name, "organization": org, "relationship": rel, "context": ctx})

        if new_people and not dry_run:
            additions = "\n\n---\n\n## Recently Added from PCP\n\n"
            for person in new_people:
                additions += f"""### {person['name']}
| Field | Value |
|-------|-------|
| **Organization** | {person['organization'] or 'TBD'} |
| **Relationship** | {person['relationship'] or 'TBD'} |

---

"""
            updated_content = people_content.rstrip() + additions
            write_onedrive_file(f"{CORE_PATH}/PEOPLE.md", updated_content)
            report["people_synced"] = len(new_people)
        elif new_people:
            report["people_synced"] = len(new_people)

    conn.close()
    return report


def discover_important_docs(days: int = 7, dry_run: bool = False) -> Dict:
    """Scan OneDrive for recently modified important docs."""
    report = {"scanned": 0, "found": 0, "indexed": 0}

    # Get recently modified files
    success, output = run_rclone([
        "lsf", "onedrive:", "--recursive", "--max-depth", "3",
        "--include", "*.md", "--include", "*.pdf", "--include", "*.docx"
    ])

    if not success:
        return report

    files = output.strip().split("\n")
    report["scanned"] = len(files)

    # Filter to important-looking files (exclude node_modules, .venv, etc.)
    important_patterns = ["meeting", "notes", "summary", "report", "decision", "proposal"]
    exclude_patterns = ["node_modules", ".venv", "dist", "build", "__pycache__"]

    important_files = []
    for f in files:
        f_lower = f.lower()
        if any(ex in f_lower for ex in exclude_patterns):
            continue
        if any(imp in f_lower for imp in important_patterns):
            important_files.append(f)

    report["found"] = len(important_files)

    if not dry_run and important_files:
        conn = get_db()
        c = conn.cursor()

        for f in important_files[:10]:  # Limit to 10 per run
            # Check if already indexed
            c.execute("SELECT id FROM files WHERE source_path = ?", (f,))
            if not c.fetchone():
                c.execute("""
                    INSERT INTO files (source, source_path, created_at)
                    VALUES ('onedrive', ?, ?)
                """, (f, datetime.now().isoformat()))
                report["indexed"] += 1

        conn.commit()
        conn.close()

    return report


def generate_sync_report(core_report: Dict, pcp_report: Dict, discovery_report: Dict) -> str:
    """Generate human-readable sync report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"**PCP Core Sync Report** - {now}",
        "",
        "**Core → PCP:**",
        f"  Projects: +{core_report.get('projects_added', 0)} added, {core_report.get('projects_updated', 0)} updated",
        f"  People: +{core_report.get('people_added', 0)} added, {core_report.get('people_updated', 0)} updated",
        "",
        "**PCP → Core:**",
        f"  Projects synced: {pcp_report.get('projects_synced', 0)}",
        f"  People synced: {pcp_report.get('people_synced', 0)}",
        "",
        "**Discovery:**",
        f"  Files scanned: {discovery_report.get('scanned', 0)}",
        f"  Important found: {discovery_report.get('found', 0)}",
        f"  Newly indexed: {discovery_report.get('indexed', 0)}",
    ]

    return "\n".join(lines)


def send_to_discord(message: str, webhook_url: str = None) -> bool:
    """Send sync report to Discord."""
    if not webhook_url:
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        print("WARNING: DISCORD_WEBHOOK_URL not set, skipping notification", file=sys.stderr)
        return False

    import json
    import urllib.request

    payload = json.dumps({"content": message}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"Failed to send to Discord: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="PCP Core Sync")
    parser.add_argument("--core-to-pcp", action="store_true", help="Only sync Core → PCP")
    parser.add_argument("--pcp-to-core", action="store_true", help="Only sync PCP → Core")
    parser.add_argument("--discovery", action="store_true", help="Only run discovery")
    parser.add_argument("--report", action="store_true", help="Generate report only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced")
    parser.add_argument("--discord", action="store_true", help="Send report to Discord")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    core_report = {}
    pcp_report = {}
    discovery_report = {}

    # Run requested sync operations
    if args.core_to_pcp or (not args.pcp_to_core and not args.discovery and not args.report):
        if not args.quiet:
            print("Syncing Core → PCP...")
        core_report = sync_core_to_pcp(dry_run=args.dry_run)

    if args.pcp_to_core or (not args.core_to_pcp and not args.discovery and not args.report):
        if not args.quiet:
            print("Syncing PCP → Core...")
        pcp_report = sync_pcp_to_core(dry_run=args.dry_run)

    if args.discovery or (not args.core_to_pcp and not args.pcp_to_core and not args.report):
        if not args.quiet:
            print("Running discovery...")
        discovery_report = discover_important_docs(dry_run=args.dry_run)

    # Generate report
    report = generate_sync_report(core_report, pcp_report, discovery_report)

    if args.dry_run:
        print("\n[DRY RUN - No changes made]")

    print(report)

    if args.discord:
        send_to_discord(report)
        print("\nReport sent to Discord")


if __name__ == "__main__":
    main()
