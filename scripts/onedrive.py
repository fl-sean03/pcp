#!/usr/bin/env python3
"""
OneDrive Integration - Sync and monitor files from Microsoft OneDrive.
Uses Microsoft Graph API for access.

Setup required:
1. Register an app in Azure AD (portal.azure.com)
2. Get client_id and client_secret
3. Set permissions: Files.Read.All, offline_access
4. Run: python onedrive.py --auth to authenticate
"""

import os
import json
import sqlite3
import requests
import webbrowser
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
from urllib.parse import urlencode

# Configuration
VAULT_PATH = "/workspace/vault/vault.db"
CONFIG_PATH = "/workspace/.onedrive_config.json"
TOKEN_PATH = "/workspace/.onedrive_token.json"
CACHE_DIR = "/workspace/vault/onedrive_cache"

# Microsoft Graph API endpoints
GRAPH_URL = "https://graph.microsoft.com/v1.0"
AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0"

# Default scopes
SCOPES = ["Files.Read.All", "offline_access"]


class OneDriveClient:
    """Client for OneDrive operations via Microsoft Graph API."""

    def __init__(self):
        self.config = self._load_config()
        self.token = self._load_token()
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _load_config(self) -> Dict:
        """Load OAuth configuration."""
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        return {}

    def _save_config(self, config: Dict):
        """Save OAuth configuration."""
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        os.chmod(CONFIG_PATH, 0o600)

    def _load_token(self) -> Dict:
        """Load access token."""
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, "r") as f:
                return json.load(f)
        return {}

    def _save_token(self, token: Dict):
        """Save access token."""
        with open(TOKEN_PATH, "w") as f:
            json.dump(token, f, indent=2)
        os.chmod(TOKEN_PATH, 0o600)

    def configure(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8080"):
        """Configure OAuth credentials."""
        self.config = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri
        }
        self._save_config(self.config)
        print("Configuration saved. Run --auth to authenticate.")

    def get_auth_url(self) -> str:
        """Get the OAuth authorization URL."""
        if not self.config.get("client_id"):
            raise ValueError("Not configured. Run configure() first.")

        params = {
            "client_id": self.config["client_id"],
            "response_type": "code",
            "redirect_uri": self.config["redirect_uri"],
            "scope": " ".join(SCOPES),
            "response_mode": "query"
        }
        return f"{AUTH_URL}/authorize?{urlencode(params)}"

    def authenticate(self, auth_code: str) -> bool:
        """Exchange authorization code for tokens."""
        if not self.config.get("client_id"):
            raise ValueError("Not configured.")

        data = {
            "client_id": self.config["client_id"],
            "client_secret": self.config["client_secret"],
            "code": auth_code,
            "redirect_uri": self.config["redirect_uri"],
            "grant_type": "authorization_code",
            "scope": " ".join(SCOPES)
        }

        response = requests.post(f"{AUTH_URL}/token", data=data)

        if response.status_code == 200:
            token_data = response.json()
            token_data["expires_at"] = (
                datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))
            ).isoformat()
            self._save_token(token_data)
            self.token = token_data
            print("Authentication successful!")
            return True
        else:
            print(f"Authentication failed: {response.text}")
            return False

    def refresh_token(self) -> bool:
        """Refresh the access token."""
        if not self.token.get("refresh_token"):
            return False

        data = {
            "client_id": self.config["client_id"],
            "client_secret": self.config["client_secret"],
            "refresh_token": self.token["refresh_token"],
            "grant_type": "refresh_token",
            "scope": " ".join(SCOPES)
        }

        response = requests.post(f"{AUTH_URL}/token", data=data)

        if response.status_code == 200:
            token_data = response.json()
            token_data["expires_at"] = (
                datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))
            ).isoformat()
            # Keep refresh token if not returned
            if "refresh_token" not in token_data:
                token_data["refresh_token"] = self.token["refresh_token"]
            self._save_token(token_data)
            self.token = token_data
            return True
        return False

    def _get_headers(self) -> Dict:
        """Get authorization headers, refreshing token if needed."""
        if not self.token.get("access_token"):
            raise ValueError("Not authenticated. Run authenticate() first.")

        # Check if token expired
        expires_at = self.token.get("expires_at")
        if expires_at:
            if datetime.fromisoformat(expires_at) < datetime.now():
                if not self.refresh_token():
                    raise ValueError("Token expired and refresh failed.")

        return {"Authorization": f"Bearer {self.token['access_token']}"}

    def list_folder(self, path: str = "/", recursive: bool = False) -> List[Dict]:
        """List files in a OneDrive folder."""
        # Handle root vs specific path
        if path == "/" or path == "":
            endpoint = f"{GRAPH_URL}/me/drive/root/children"
        else:
            # Encode path for URL
            encoded_path = path.replace(" ", "%20")
            endpoint = f"{GRAPH_URL}/me/drive/root:{encoded_path}:/children"

        files = []

        while endpoint:
            response = requests.get(endpoint, headers=self._get_headers())

            if response.status_code != 200:
                print(f"Error listing folder: {response.text}")
                break

            data = response.json()

            for item in data.get("value", []):
                file_info = {
                    "id": item["id"],
                    "name": item["name"],
                    "path": path + "/" + item["name"],
                    "size": item.get("size", 0),
                    "is_folder": "folder" in item,
                    "modified": item.get("lastModifiedDateTime"),
                    "mime_type": item.get("file", {}).get("mimeType", "folder")
                }
                files.append(file_info)

                # Recurse into subfolders if requested
                if recursive and file_info["is_folder"]:
                    files.extend(self.list_folder(file_info["path"], recursive=True))

            # Handle pagination
            endpoint = data.get("@odata.nextLink")

        return files

    def download_file(self, file_id: str, dest_path: str) -> bool:
        """Download a file from OneDrive."""
        # Get download URL
        endpoint = f"{GRAPH_URL}/me/drive/items/{file_id}/content"
        response = requests.get(endpoint, headers=self._get_headers(), allow_redirects=True)

        if response.status_code == 200:
            with open(dest_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"Error downloading file: {response.status_code}")
            return False

    def get_recent_files(self, limit: int = 25) -> List[Dict]:
        """Get recently modified files."""
        endpoint = f"{GRAPH_URL}/me/drive/recent?$top={limit}"
        response = requests.get(endpoint, headers=self._get_headers())

        if response.status_code != 200:
            print(f"Error getting recent files: {response.text}")
            return []

        files = []
        for item in response.json().get("value", []):
            files.append({
                "id": item["id"],
                "name": item["name"],
                "path": item.get("parentReference", {}).get("path", "").replace("/drive/root:", ""),
                "size": item.get("size", 0),
                "modified": item.get("lastModifiedDateTime"),
                "mime_type": item.get("file", {}).get("mimeType", "unknown")
            })

        return files

    def search(self, query: str, limit: int = 25) -> List[Dict]:
        """Search for files in OneDrive."""
        endpoint = f"{GRAPH_URL}/me/drive/root/search(q='{query}')?$top={limit}"
        response = requests.get(endpoint, headers=self._get_headers())

        if response.status_code != 200:
            print(f"Error searching: {response.text}")
            return []

        files = []
        for item in response.json().get("value", []):
            files.append({
                "id": item["id"],
                "name": item["name"],
                "path": item.get("parentReference", {}).get("path", "").replace("/drive/root:", ""),
                "size": item.get("size", 0),
                "modified": item.get("lastModifiedDateTime"),
                "mime_type": item.get("file", {}).get("mimeType", "unknown")
            })

        return files


def sync_watched_folders():
    """Sync all watched OneDrive folders."""
    from file_processor import ingest_file

    client = OneDriveClient()

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Get watched folders
    cursor.execute("""
        SELECT id, folder_path, project_id, file_patterns, last_sync
        FROM onedrive_watches
        WHERE enabled = 1
    """)

    watches = cursor.fetchall()

    for watch in watches:
        watch_id, folder_path, project_id, file_patterns, last_sync = watch
        patterns = json.loads(file_patterns) if file_patterns else None

        print(f"Syncing: {folder_path}")

        # List files in folder
        files = client.list_folder(folder_path, recursive=True)

        for file_info in files:
            if file_info["is_folder"]:
                continue

            # Check if file matches patterns
            if patterns:
                matched = False
                for pattern in patterns:
                    if pattern.startswith("*."):
                        if file_info["name"].lower().endswith(pattern[1:].lower()):
                            matched = True
                            break
                if not matched:
                    continue

            # Check if already synced (by source_id)
            cursor.execute("""
                SELECT id FROM files WHERE source = 'onedrive' AND source_id = ?
            """, (file_info["id"],))

            if cursor.fetchone():
                continue  # Already synced

            # Download and ingest
            cache_path = os.path.join(CACHE_DIR, f"{file_info['id']}_{file_info['name']}")

            if client.download_file(file_info["id"], cache_path):
                capture_id = ingest_file(
                    cache_path,
                    original_name=file_info["name"],
                    source="onedrive",
                    source_id=file_info["id"],
                    context=f"From OneDrive: {file_info['path']}"
                )

                # Link to project if specified
                if project_id and capture_id > 0:
                    cursor.execute("""
                        UPDATE captures_v2
                        SET linked_projects = ?
                        WHERE id = ?
                    """, (json.dumps([project_id]), capture_id))

        # Update last sync time
        cursor.execute("""
            UPDATE onedrive_watches SET last_sync = ? WHERE id = ?
        """, (datetime.now().isoformat(), watch_id))

    conn.commit()
    conn.close()
    print("Sync complete!")


def add_watch(folder_path: str, project_name: str = None, patterns: List[str] = None):
    """Add a folder to watch for sync."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    project_id = None
    if project_name:
        cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
        row = cursor.fetchone()
        if row:
            project_id = row[0]

    cursor.execute("""
        INSERT INTO onedrive_watches (folder_path, project_id, file_patterns)
        VALUES (?, ?, ?)
    """, (folder_path, project_id, json.dumps(patterns) if patterns else None))

    conn.commit()
    conn.close()
    print(f"Added watch for: {folder_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("""OneDrive Integration for PCP

Usage:
    python onedrive.py --configure <client_id> <client_secret>
    python onedrive.py --auth
    python onedrive.py --list [path]
    python onedrive.py --recent
    python onedrive.py --search <query>
    python onedrive.py --sync
    python onedrive.py --watch <folder_path> [project_name] [patterns...]
""")
        sys.exit(1)

    client = OneDriveClient()
    cmd = sys.argv[1]

    if cmd == "--configure":
        if len(sys.argv) < 4:
            print("Usage: --configure <client_id> <client_secret>")
            sys.exit(1)
        client.configure(sys.argv[2], sys.argv[3])

    elif cmd == "--auth":
        auth_url = client.get_auth_url()
        print(f"\nOpen this URL in your browser:\n{auth_url}\n")
        print("After authorizing, you'll be redirected to localhost.")
        print("Copy the 'code' parameter from the URL and paste it here:")
        auth_code = input("Authorization code: ").strip()
        client.authenticate(auth_code)

    elif cmd == "--list":
        path = sys.argv[2] if len(sys.argv) > 2 else "/"
        files = client.list_folder(path)
        for f in files:
            icon = "📁" if f["is_folder"] else "📄"
            print(f"{icon} {f['name']} ({f['size']} bytes)")

    elif cmd == "--recent":
        files = client.get_recent_files()
        for f in files:
            print(f"📄 {f['name']} - {f['path']} (modified: {f['modified']})")

    elif cmd == "--search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        files = client.search(query)
        for f in files:
            print(f"📄 {f['name']} - {f['path']}")

    elif cmd == "--sync":
        sync_watched_folders()

    elif cmd == "--watch":
        if len(sys.argv) < 3:
            print("Usage: --watch <folder_path> [project_name] [patterns...]")
            sys.exit(1)
        folder = sys.argv[2]
        project = sys.argv[3] if len(sys.argv) > 3 else None
        patterns = sys.argv[4:] if len(sys.argv) > 4 else None
        add_watch(folder, project, patterns)

    else:
        print(f"Unknown command: {cmd}")
