#!/usr/bin/env python3
"""
PCP Core Documents Manager - Read, write, and update Core documents.

Core documents are the canonical source of truth for the user's profile,
projects, goals, skills, and relationships. They live on OneDrive and
are version-controlled via Git.

This module provides:
- Read/write access to Core docs via rclone
- Git versioning for all changes
- Section-level updates
- Changelog management
- Rollback capability
"""

import os
import re
import subprocess
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


# ============================================================================
# Configuration
# ============================================================================

# Local git repo path
CORE_DOCS_LOCAL = Path(os.environ.get("PCP_DIR", "/workspace")) / "core-docs"
# OneDrive path
ONEDRIVE_PATH = "Documents/Core"
# Git remote
GIT_REMOTE = "origin"
GIT_BRANCH = "main"

# Core document names
CORE_DOCS = [
    "PROFILE.md",
    "SKILLS.md",
    "RESEARCH.md",
    "PROJECTS.md",
    "GOALS.md",
    "PEOPLE.md",
    "CHANGELOG.md"
]


# ============================================================================
# Core Functions
# ============================================================================

class CoreDocsManager:
    """Manage Core documents with OneDrive sync and Git versioning."""

    def __init__(self,
                 local_path: Path = CORE_DOCS_LOCAL,
                 onedrive_path: str = ONEDRIVE_PATH):
        """
        Initialize CoreDocsManager.

        Args:
            local_path: Path to local git repo for Core docs
            onedrive_path: OneDrive path (e.g., "Documents/Core")
        """
        self.local_path = Path(local_path)
        self.onedrive_path = onedrive_path

        # Ensure local path exists
        if not self.local_path.exists():
            raise FileNotFoundError(f"Core docs local path not found: {self.local_path}")

    # -------------------------------------------------------------------------
    # Read Operations
    # -------------------------------------------------------------------------

    def read_doc(self, doc_name: str, from_onedrive: bool = False) -> str:
        """
        Read a Core document.

        Args:
            doc_name: Document name (e.g., "PROFILE.md")
            from_onedrive: If True, read from OneDrive; else from local

        Returns:
            Document content as string
        """
        if from_onedrive:
            result = subprocess.run(
                ["rclone", "cat", f"onedrive:{self.onedrive_path}/{doc_name}"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                raise FileNotFoundError(f"Could not read {doc_name} from OneDrive: {result.stderr}")
            return result.stdout
        else:
            doc_path = self.local_path / doc_name
            if not doc_path.exists():
                raise FileNotFoundError(f"Document not found: {doc_path}")
            return doc_path.read_text()

    def list_docs(self) -> List[str]:
        """List all Core documents."""
        docs = []
        for f in self.local_path.iterdir():
            if f.suffix == ".md" and f.name != ".gitignore":
                docs.append(f.name)
        return sorted(docs)

    def get_section(self, doc_name: str, section_header: str) -> Optional[str]:
        """
        Get content of a specific section from a document.

        Args:
            doc_name: Document name
            section_header: Section header (e.g., "## Active Projects")

        Returns:
            Section content or None if not found
        """
        content = self.read_doc(doc_name)

        # Find the section
        pattern = rf"(^|\n){re.escape(section_header)}\s*\n"
        match = re.search(pattern, content)
        if not match:
            return None

        start = match.end()

        # Find the next section (same or higher level heading)
        level = section_header.count('#')
        next_section = re.search(rf"\n#{{{1},{level}}}\s+", content[start:])

        if next_section:
            end = start + next_section.start()
        else:
            end = len(content)

        return content[start:end].strip()

    # -------------------------------------------------------------------------
    # Write Operations
    # -------------------------------------------------------------------------

    def write_doc(self, doc_name: str, content: str, reason: str) -> bool:
        """
        Write entire document content.

        Args:
            doc_name: Document name
            content: Full document content
            reason: Reason for the change (for changelog and commit)

        Returns:
            True if successful
        """
        doc_path = self.local_path / doc_name

        # Update the "Last updated" line if present
        content = self._update_last_modified(content)

        # Write to local
        doc_path.write_text(content)

        # Add changelog entry
        self._add_changelog_entry(doc_name, reason)

        # Git commit
        self._git_commit(f"Update {doc_name}: {reason}")

        # Sync to OneDrive
        self._sync_to_onedrive()

        return True

    def update_section(self, doc_name: str, section_header: str,
                       new_content: str, reason: str) -> bool:
        """
        Update a specific section within a document.

        Args:
            doc_name: Document name
            section_header: Section header to update (e.g., "## Active Projects")
            new_content: New content for the section (without header)
            reason: Reason for the change

        Returns:
            True if successful
        """
        content = self.read_doc(doc_name)

        # Find the section
        pattern = rf"(^|\n)({re.escape(section_header)}\s*\n)"
        match = re.search(pattern, content)
        if not match:
            raise ValueError(f"Section '{section_header}' not found in {doc_name}")

        section_start = match.end()

        # Find the next section (same or higher level heading)
        level = section_header.count('#')
        next_section = re.search(rf"\n#{{{1},{level}}}\s+", content[section_start:])

        if next_section:
            section_end = section_start + next_section.start()
        else:
            # Find the last "---" separator or end of file
            last_sep = content.rfind("\n---\n")
            if last_sep > section_start:
                section_end = last_sep
            else:
                section_end = len(content)

        # Reconstruct document
        new_doc = (
            content[:section_start] +
            new_content.strip() + "\n\n" +
            content[section_end:].lstrip()
        )

        return self.write_doc(doc_name, new_doc, reason)

    def append_to_section(self, doc_name: str, section_header: str,
                          item: str, reason: str) -> bool:
        """
        Append an item to a section.

        Args:
            doc_name: Document name
            section_header: Section header (e.g., "## Active Projects")
            item: Content to append
            reason: Reason for the change

        Returns:
            True if successful
        """
        current_content = self.get_section(doc_name, section_header)
        if current_content is None:
            raise ValueError(f"Section '{section_header}' not found in {doc_name}")

        new_content = current_content + "\n\n" + item.strip()
        return self.update_section(doc_name, section_header, new_content, reason)

    # -------------------------------------------------------------------------
    # Changelog Management
    # -------------------------------------------------------------------------

    def _add_changelog_entry(self, doc_name: str, change: str,
                             source: str = "PCP"):
        """Add an entry to CHANGELOG.md."""
        changelog_path = self.local_path / "CHANGELOG.md"
        if not changelog_path.exists():
            return

        content = changelog_path.read_text()
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")

        # Check if today's section exists
        date_header = f"## {date_str}"
        if date_header not in content:
            # Add new date section after the header
            insert_pos = content.find("\n---\n")
            if insert_pos == -1:
                insert_pos = content.find("\n## ")
            if insert_pos == -1:
                insert_pos = len(content)

            new_section = f"\n{date_header}\n\n| Time | Document | Change | Source |\n|------|----------|--------|--------|\n"
            content = content[:insert_pos] + new_section + content[insert_pos:]

        # Add entry to today's table
        entry = f"| {time_str} | {doc_name} | {change} | {source} |"

        # Find the table under today's date
        date_pos = content.find(date_header)
        table_end = content.find("\n\n---", date_pos)
        if table_end == -1:
            table_end = content.find("\n\n## ", date_pos + len(date_header))
        if table_end == -1:
            table_end = len(content)

        # Insert entry at end of table
        content = content[:table_end] + "\n" + entry + content[table_end:]

        changelog_path.write_text(content)

    def get_changelog(self, limit: int = 20) -> List[Dict[str, str]]:
        """
        Get recent changelog entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of changelog entries
        """
        content = self.read_doc("CHANGELOG.md")
        entries = []

        # Parse table rows
        for line in content.split("\n"):
            if line.startswith("| ") and not line.startswith("| Time") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    entries.append({
                        "time": parts[0],
                        "document": parts[1],
                        "change": parts[2],
                        "source": parts[3]
                    })
                    if len(entries) >= limit:
                        break

        return entries

    # -------------------------------------------------------------------------
    # Git Operations
    # -------------------------------------------------------------------------

    def _git_commit(self, message: str):
        """Create a git commit with the given message."""
        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.local_path,
            capture_output=True
        )

        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.local_path,
            capture_output=True, text=True
        )
        if not result.stdout.strip():
            return  # No changes to commit

        # Commit
        full_message = f"{message}\n\n🤖 Auto-updated by PCP"
        subprocess.run(
            ["git", "commit", "-m", full_message],
            cwd=self.local_path,
            capture_output=True
        )

        # Push to remote
        subprocess.run(
            ["git", "push", GIT_REMOTE, GIT_BRANCH],
            cwd=self.local_path,
            capture_output=True
        )

    def get_git_history(self, limit: int = 20) -> List[Dict[str, str]]:
        """
        Get git commit history.

        Args:
            limit: Maximum number of commits

        Returns:
            List of commits with hash, date, and message
        """
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--pretty=format:%H|%ai|%s"],
            cwd=self.local_path,
            capture_output=True, text=True
        )

        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|", 2)
                if len(parts) >= 3:
                    commits.append({
                        "hash": parts[0],
                        "date": parts[1],
                        "message": parts[2]
                    })

        return commits

    def revert_to_commit(self, commit_hash: str, reason: str) -> bool:
        """
        Revert Core docs to a specific commit.

        Args:
            commit_hash: Git commit hash to revert to
            reason: Reason for the revert

        Returns:
            True if successful
        """
        # Revert
        result = subprocess.run(
            ["git", "revert", "--no-commit", f"{commit_hash}..HEAD"],
            cwd=self.local_path,
            capture_output=True, text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Git revert failed: {result.stderr}")

        # Commit the revert
        self._git_commit(f"Revert to {commit_hash[:8]}: {reason}")

        # Sync to OneDrive
        self._sync_to_onedrive()

        return True

    # -------------------------------------------------------------------------
    # OneDrive Sync
    # -------------------------------------------------------------------------

    def _sync_to_onedrive(self):
        """Push local changes to OneDrive."""
        subprocess.run(
            ["rclone", "sync",
             str(self.local_path),
             f"onedrive:{self.onedrive_path}",
             "--exclude", ".git/**"],
            capture_output=True
        )

    def sync_from_onedrive(self) -> bool:
        """
        Pull latest from OneDrive to local.

        Returns:
            True if any changes were pulled
        """
        # Get current state
        before = self._get_files_hash()

        # Sync from OneDrive
        subprocess.run(
            ["rclone", "sync",
             f"onedrive:{self.onedrive_path}",
             str(self.local_path),
             "--exclude", ".git/**"],
            capture_output=True
        )

        # Check if anything changed
        after = self._get_files_hash()
        if before != after:
            self._git_commit("Sync from OneDrive")
            return True

        return False

    def _get_files_hash(self) -> str:
        """Get a hash of all file contents for change detection."""
        import hashlib
        h = hashlib.md5()
        for doc in sorted(self.list_docs()):
            content = (self.local_path / doc).read_text()
            h.update(content.encode())
        return h.hexdigest()

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    def _update_last_modified(self, content: str) -> str:
        """Update the 'Last updated' line in document content."""
        now = datetime.now().strftime("%Y-%m-%d")
        pattern = r"\*Last updated:.*\*"
        replacement = f"*Last updated: {now} by PCP*"

        if re.search(pattern, content):
            return re.sub(pattern, replacement, content)
        return content


# ============================================================================
# Convenience Functions
# ============================================================================

def get_manager() -> CoreDocsManager:
    """Get a CoreDocsManager instance."""
    return CoreDocsManager()


def read_profile() -> str:
    """Read PROFILE.md."""
    return get_manager().read_doc("PROFILE.md")


def read_projects() -> str:
    """Read PROJECTS.md."""
    return get_manager().read_doc("PROJECTS.md")


def read_goals() -> str:
    """Read GOALS.md."""
    return get_manager().read_doc("GOALS.md")


def add_project(name: str, project_type: str, focus: str,
                status: str = "Active", key_files: str = "") -> bool:
    """
    Add a new project to PROJECTS.md.

    Args:
        name: Project name
        project_type: Type (Research, Startup, Personal, etc.)
        focus: What the project focuses on
        status: Project status (default: Active)
        key_files: Path to key files

    Returns:
        True if successful
    """
    manager = get_manager()

    project_entry = f"""### {name}
| Field | Value |
|-------|-------|
| **Status** | {status} |
| **Type** | {project_type} |
| **Focus** | {focus} |
| **Started** | {datetime.now().strftime("%B %Y")} |
| **Key Files** | {key_files} |

---
"""
    return manager.append_to_section(
        "PROJECTS.md",
        "## Active Projects",
        project_entry,
        f"Added new project: {name}"
    )


def update_project_status(name: str, new_status: str) -> bool:
    """
    Update a project's status.

    Args:
        name: Project name
        new_status: New status

    Returns:
        True if successful
    """
    manager = get_manager()
    content = manager.read_doc("PROJECTS.md")

    # Find the project and update its status
    pattern = rf"(### {re.escape(name)}.*?\| \*\*Status\*\* \| )(\w+)( \|)"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        raise ValueError(f"Project '{name}' not found in PROJECTS.md")

    new_content = content[:match.start(2)] + new_status + content[match.end(2):]

    return manager.write_doc(
        "PROJECTS.md",
        new_content,
        f"Updated {name} status to {new_status}"
    )


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PCP Core Documents Manager"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List all Core documents")

    # Read command
    read_parser = subparsers.add_parser("read", help="Read a Core document")
    read_parser.add_argument("doc", help="Document name (e.g., PROFILE.md)")
    read_parser.add_argument("--onedrive", action="store_true",
                             help="Read from OneDrive instead of local")

    # Section command
    section_parser = subparsers.add_parser("section", help="Get a section from a document")
    section_parser.add_argument("doc", help="Document name")
    section_parser.add_argument("header", help="Section header (e.g., '## Active Projects')")

    # History command
    history_parser = subparsers.add_parser("history", help="Show git history")
    history_parser.add_argument("--limit", "-l", type=int, default=10)

    # Changelog command
    changelog_parser = subparsers.add_parser("changelog", help="Show changelog")
    changelog_parser.add_argument("--limit", "-l", type=int, default=20)

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync with OneDrive")
    sync_parser.add_argument("--from-onedrive", action="store_true",
                             help="Pull from OneDrive")

    # Add project command
    add_project_parser = subparsers.add_parser("add-project", help="Add a new project")
    add_project_parser.add_argument("name", help="Project name")
    add_project_parser.add_argument("--type", "-t", required=True, help="Project type")
    add_project_parser.add_argument("--focus", "-f", required=True, help="Project focus")
    add_project_parser.add_argument("--files", help="Key files path")

    args = parser.parse_args()
    manager = CoreDocsManager()

    if args.command == "list":
        docs = manager.list_docs()
        print("Core Documents:")
        for doc in docs:
            print(f"  - {doc}")

    elif args.command == "read":
        content = manager.read_doc(args.doc, from_onedrive=args.onedrive)
        print(content)

    elif args.command == "section":
        content = manager.get_section(args.doc, args.header)
        if content:
            print(content)
        else:
            print(f"Section '{args.header}' not found in {args.doc}")

    elif args.command == "history":
        history = manager.get_git_history(args.limit)
        print("Git History:")
        for commit in history:
            print(f"  {commit['hash'][:8]} | {commit['date'][:10]} | {commit['message']}")

    elif args.command == "changelog":
        entries = manager.get_changelog(args.limit)
        print("Recent Changes:")
        for entry in entries:
            print(f"  {entry['time']} | {entry['document']} | {entry['change']}")

    elif args.command == "sync":
        if args.from_onedrive:
            changed = manager.sync_from_onedrive()
            if changed:
                print("Synced changes from OneDrive")
            else:
                print("No changes to sync")
        else:
            manager._sync_to_onedrive()
            print("Synced to OneDrive")

    elif args.command == "add-project":
        success = add_project(
            args.name,
            args.type,
            args.focus,
            key_files=args.files or ""
        )
        if success:
            print(f"Added project: {args.name}")

    else:
        parser.print_help()
