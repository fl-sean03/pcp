#!/usr/bin/env python3
"""
OneDrive Integration via rclone - Simple wrapper for PCP.

rclone handles all the OAuth complexity. This module provides
a clean Python interface for PCP to use.

Usage:
    from onedrive_rclone import OneDriveClient

    client = OneDriveClient()

    # List files
    files = client.list_files("Documents")

    # Search
    results = client.search("homework")

    # Download
    client.download("Documents/file.pdf", "/tmp/file.pdf")

    # Get file info
    info = client.get_info("Documents/file.pdf")
"""

import os
import json
import subprocess
from typing import List, Dict, Optional
from datetime import datetime


class OneDriveClient:
    """OneDrive client using rclone as the backend."""

    def __init__(self, remote_name: str = "onedrive"):
        """
        Initialize the OneDrive client.

        Args:
            remote_name: The rclone remote name (default: "onedrive")
        """
        self.remote = remote_name
        self._verify_remote()

    def _verify_remote(self):
        """Verify rclone remote is configured."""
        result = subprocess.run(
            ["rclone", "listremotes"],
            capture_output=True, text=True
        )
        if f"{self.remote}:" not in result.stdout:
            raise ValueError(
                f"rclone remote '{self.remote}' not configured. "
                f"Run: rclone config"
            )

    def _run_rclone(self, args: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
        """Run an rclone command."""
        cmd = ["rclone"] + args
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )

    def list_files(self, path: str = "", recursive: bool = False,
                   max_depth: int = None) -> List[Dict]:
        """
        List files in a directory.

        Args:
            path: Path within OneDrive (empty for root)
            recursive: Include subdirectories
            max_depth: Maximum recursion depth

        Returns:
            List of file info dicts with keys: name, path, size, modified, is_dir
        """
        remote_path = f"{self.remote}:{path}"

        args = ["lsjson", remote_path]
        if recursive:
            args.append("--recursive")
        if max_depth:
            args.extend(["--max-depth", str(max_depth)])

        result = self._run_rclone(args)

        if result.returncode != 0:
            raise RuntimeError(f"rclone error: {result.stderr}")

        files = json.loads(result.stdout) if result.stdout else []

        # Normalize the output
        normalized = []
        for f in files:
            normalized.append({
                "name": f.get("Name", ""),
                "path": f.get("Path", ""),
                "size": f.get("Size", 0),
                "modified": f.get("ModTime", ""),
                "is_dir": f.get("IsDir", False),
                "mime_type": f.get("MimeType", "")
            })

        return normalized

    def list_dirs(self, path: str = "") -> List[str]:
        """
        List only directories.

        Args:
            path: Path within OneDrive

        Returns:
            List of directory names
        """
        remote_path = f"{self.remote}:{path}"
        result = self._run_rclone(["lsd", remote_path])

        if result.returncode != 0:
            return []

        dirs = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                # lsd format: "          -1 2024-06-04 05:13:40         7 Documents"
                parts = line.split()
                if len(parts) >= 5:
                    dirs.append(parts[-1])

        return dirs

    def search(self, query: str, path: str = "",
               file_types: List[str] = None) -> List[Dict]:
        """
        Search for files matching a pattern.

        Args:
            query: Search pattern (supports glob patterns like *.pdf)
            path: Path to search in (empty for all)
            file_types: List of extensions to include (e.g., ["pdf", "docx"])

        Returns:
            List of matching file info dicts
        """
        remote_path = f"{self.remote}:{path}"

        # Build include filters
        args = ["lsjson", remote_path, "--recursive"]

        if file_types:
            for ext in file_types:
                args.extend(["--include", f"*.{ext}"])

        if query and not file_types:
            # Use query as include pattern
            args.extend(["--include", f"*{query}*"])

        result = self._run_rclone(args, timeout=120)

        if result.returncode != 0:
            return []

        files = json.loads(result.stdout) if result.stdout else []

        # Filter by query if we also had file_types
        if query and file_types:
            query_lower = query.lower()
            files = [f for f in files if query_lower in f.get("Name", "").lower()]

        return [{
            "name": f.get("Name", ""),
            "path": f.get("Path", ""),
            "size": f.get("Size", 0),
            "modified": f.get("ModTime", ""),
            "is_dir": f.get("IsDir", False)
        } for f in files]

    def download(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from OneDrive.

        Args:
            remote_path: Path in OneDrive
            local_path: Local destination path

        Returns:
            True if successful
        """
        src = f"{self.remote}:{remote_path}"

        # Ensure local directory exists
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)

        result = self._run_rclone(["copyto", src, local_path], timeout=300)

        return result.returncode == 0

    def download_dir(self, remote_path: str, local_path: str) -> bool:
        """
        Download a directory from OneDrive.

        Args:
            remote_path: Path in OneDrive
            local_path: Local destination directory

        Returns:
            True if successful
        """
        src = f"{self.remote}:{remote_path}"

        os.makedirs(local_path, exist_ok=True)

        result = self._run_rclone(["copy", src, local_path], timeout=600)

        return result.returncode == 0

    def get_info(self, path: str) -> Optional[Dict]:
        """
        Get information about a file or directory.

        Args:
            path: Path in OneDrive

        Returns:
            File info dict or None if not found
        """
        remote_path = f"{self.remote}:{path}"

        result = self._run_rclone(["lsjson", remote_path, "--stat"])

        if result.returncode != 0:
            return None

        info = json.loads(result.stdout) if result.stdout else None

        if info:
            return {
                "name": info.get("Name", ""),
                "path": path,
                "size": info.get("Size", 0),
                "modified": info.get("ModTime", ""),
                "is_dir": info.get("IsDir", False),
                "mime_type": info.get("MimeType", "")
            }

        return None

    def exists(self, path: str) -> bool:
        """Check if a file or directory exists."""
        return self.get_info(path) is not None

    def upload(self, local_path: str, remote_path: str) -> bool:
        """
        Upload a file to OneDrive.

        Args:
            local_path: Local file path
            remote_path: Destination path in OneDrive

        Returns:
            True if successful
        """
        if not os.path.exists(local_path):
            return False

        dst = f"{self.remote}:{remote_path}"
        result = self._run_rclone(["copyto", local_path, dst], timeout=300)
        return result.returncode == 0

    def upload_dir(self, local_path: str, remote_path: str) -> bool:
        """
        Upload a directory to OneDrive.

        Args:
            local_path: Local directory path
            remote_path: Destination path in OneDrive

        Returns:
            True if successful
        """
        if not os.path.isdir(local_path):
            return False

        dst = f"{self.remote}:{remote_path}"
        result = self._run_rclone(["copy", local_path, dst], timeout=600)
        return result.returncode == 0

    def mkdir(self, path: str) -> bool:
        """
        Create a directory in OneDrive.

        Args:
            path: Directory path to create

        Returns:
            True if successful
        """
        dst = f"{self.remote}:{path}"
        result = self._run_rclone(["mkdir", dst])
        return result.returncode == 0

    def get_recent_files(self, days: int = 7, limit: int = 50) -> List[Dict]:
        """
        Get recently modified files.

        Args:
            days: Look back this many days
            limit: Maximum files to return

        Returns:
            List of file info dicts, sorted by modification time (newest first)
        """
        # Get all files
        all_files = self.list_files(recursive=True, max_depth=3)

        # Filter to non-directories and parse dates
        files_with_dates = []
        for f in all_files:
            if not f["is_dir"] and f.get("modified"):
                try:
                    # Parse ISO format date
                    mod_time = datetime.fromisoformat(
                        f["modified"].replace("Z", "+00:00")
                    )
                    f["_mod_datetime"] = mod_time
                    files_with_dates.append(f)
                except:
                    pass

        # Sort by modification time (newest first)
        files_with_dates.sort(key=lambda x: x["_mod_datetime"], reverse=True)

        # Remove internal field and limit
        result = []
        for f in files_with_dates[:limit]:
            del f["_mod_datetime"]
            result.append(f)

        return result

    def get_storage_quota(self) -> Dict:
        """
        Get storage quota information.

        Returns:
            Dict with used, total, free (in bytes)
        """
        result = self._run_rclone(["about", f"{self.remote}:", "--json"])

        if result.returncode != 0:
            return {"error": result.stderr}

        info = json.loads(result.stdout) if result.stdout else {}

        return {
            "used": info.get("used", 0),
            "total": info.get("total", 0),
            "free": info.get("free", 0),
            "trashed": info.get("trashed", 0)
        }


# CLI Interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OneDrive via rclone")
    subparsers = parser.add_subparsers(dest="command")

    # List command
    list_parser = subparsers.add_parser("ls", help="List files")
    list_parser.add_argument("path", nargs="?", default="", help="Path to list")
    list_parser.add_argument("-r", "--recursive", action="store_true")
    list_parser.add_argument("-d", "--depth", type=int, default=None)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for files")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("-t", "--type", nargs="+", help="File extensions")

    # Download command
    dl_parser = subparsers.add_parser("download", help="Download a file")
    dl_parser.add_argument("remote", help="Remote path")
    dl_parser.add_argument("local", help="Local path")

    # Upload command
    ul_parser = subparsers.add_parser("upload", help="Upload a file")
    ul_parser.add_argument("local", help="Local path")
    ul_parser.add_argument("remote", help="Remote path")

    # Mkdir command
    mkdir_parser = subparsers.add_parser("mkdir", help="Create a directory")
    mkdir_parser.add_argument("path", help="Directory path to create")

    # Recent command
    recent_parser = subparsers.add_parser("recent", help="Recently modified files")
    recent_parser.add_argument("-n", "--limit", type=int, default=20)

    # Quota command
    subparsers.add_parser("quota", help="Show storage quota")

    args = parser.parse_args()

    try:
        client = OneDriveClient()

        if args.command == "ls":
            files = client.list_files(args.path, args.recursive, args.depth)
            for f in files:
                prefix = "d" if f["is_dir"] else "-"
                size = f"{f['size']:>10}" if not f["is_dir"] else "         -"
                print(f"{prefix} {size}  {f['path'] or f['name']}")

        elif args.command == "search":
            results = client.search(args.query, file_types=args.type)
            for f in results:
                print(f"{f['size']:>10}  {f['path']}")

        elif args.command == "download":
            if client.download(args.remote, args.local):
                print(f"Downloaded: {args.local}")
            else:
                print("Download failed")

        elif args.command == "upload":
            if client.upload(args.local, args.remote):
                print(f"Uploaded: {args.local} -> {args.remote}")
            else:
                print("Upload failed")

        elif args.command == "mkdir":
            if client.mkdir(args.path):
                print(f"Created directory: {args.path}")
            else:
                print("mkdir failed")

        elif args.command == "recent":
            files = client.get_recent_files(limit=args.limit)
            for f in files:
                print(f"{f['modified'][:19]}  {f['path']}")

        elif args.command == "quota":
            quota = client.get_storage_quota()
            if "error" not in quota:
                used_gb = quota["used"] / (1024**3)
                total_gb = quota["total"] / (1024**3)
                free_gb = quota["free"] / (1024**3)
                print(f"Used:  {used_gb:.2f} GB")
                print(f"Free:  {free_gb:.2f} GB")
                print(f"Total: {total_gb:.2f} GB")
            else:
                print(f"Error: {quota['error']}")

        else:
            parser.print_help()

    except Exception as e:
        print(f"Error: {e}")
