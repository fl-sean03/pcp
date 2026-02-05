#!/usr/bin/env python3
"""
Microsoft Graph API Client - Base OAuth integration for PCP.

This module provides the foundation for Microsoft Graph API access,
used by email_processor.py and can replace the file-based auth in onedrive.py.

Setup:
1. Register an app in Azure AD (portal.azure.com)
2. Set redirect URI to http://localhost:8080
3. Get client_id, client_secret, tenant_id
4. Add API permissions: Mail.Read, Mail.ReadWrite, offline_access
5. Run: python microsoft_graph.py --configure CLIENT_ID CLIENT_SECRET TENANT_ID
6. Run: python microsoft_graph.py --auth to get auth URL and complete OAuth
"""

import sqlite3
import json
import os
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import urlencode

# Database path - container path, with fallback to local development path
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(VAULT_PATH):
    # Local development fallback
    _local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault", "vault.db")
    if os.path.exists(_local_path):
        VAULT_PATH = _local_path

# Microsoft Graph API endpoints
GRAPH_URL = "https://graph.microsoft.com/v1.0"

# Provider name for oauth_tokens table
PROVIDER = "microsoft"


class MicrosoftGraphClient:
    """Client for Microsoft Graph API operations."""

    def __init__(self):
        """Initialize the client."""
        self._config = None
        self._token = None

    def _get_db_connection(self):
        """Get a database connection."""
        conn = sqlite3.connect(VAULT_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_config(self) -> Optional[Dict]:
        """Load OAuth configuration from database."""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT access_token, refresh_token, expires_at, scopes
            FROM oauth_tokens
            WHERE provider = ?
            ORDER BY id DESC LIMIT 1
        """, (PROVIDER,))

        row = cursor.fetchone()
        conn.close()

        if row and row['access_token']:
            return {
                'access_token': row['access_token'],
                'refresh_token': row['refresh_token'],
                'expires_at': row['expires_at'],
                'scopes': json.loads(row['scopes']) if row['scopes'] else []
            }
        return None

    def _get_oauth_config(self) -> Optional[Dict]:
        """Get OAuth client config (client_id, client_secret, tenant_id) from DB.

        These are stored in the oauth_tokens table as a special row with
        access_token = NULL and config in the scopes field.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        # Config is stored with access_token NULL
        cursor.execute("""
            SELECT scopes
            FROM oauth_tokens
            WHERE provider = ? AND access_token IS NULL
            ORDER BY id DESC LIMIT 1
        """, (PROVIDER,))

        row = cursor.fetchone()
        conn.close()

        if row and row['scopes']:
            return json.loads(row['scopes'])
        return None

    def configure(self, client_id: str, client_secret: str, tenant_id: str = "common",
                  redirect_uri: str = "http://localhost:8080") -> bool:
        """Configure OAuth credentials.

        Stores client_id, client_secret, tenant_id in the database.
        These are stored in the scopes field of a config-only row (access_token NULL).

        Args:
            client_id: Azure AD application (client) ID
            client_secret: Client secret value
            tenant_id: Azure AD tenant ID (use "common" for multi-tenant)
            redirect_uri: OAuth redirect URI (must match Azure AD app registration)

        Returns:
            True if configuration saved successfully
        """
        config = {
            'client_id': client_id,
            'client_secret': client_secret,
            'tenant_id': tenant_id,
            'redirect_uri': redirect_uri
        }

        conn = self._get_db_connection()
        cursor = conn.cursor()

        # Remove existing config rows
        cursor.execute("""
            DELETE FROM oauth_tokens
            WHERE provider = ? AND access_token IS NULL
        """, (PROVIDER,))

        # Insert new config
        cursor.execute("""
            INSERT INTO oauth_tokens (provider, access_token, refresh_token, expires_at, scopes)
            VALUES (?, NULL, NULL, NULL, ?)
        """, (PROVIDER, json.dumps(config)))

        conn.commit()
        conn.close()

        self._config = None  # Clear cached config
        return True

    def is_configured(self) -> bool:
        """Check if OAuth credentials are configured.

        Returns:
            True if client_id, client_secret, and tenant_id are stored
        """
        config = self._get_oauth_config()
        if not config:
            return False
        return all(key in config for key in ['client_id', 'client_secret', 'tenant_id'])

    def get_auth_url(self, scopes: list = None) -> str:
        """Get the OAuth authorization URL.

        Args:
            scopes: List of Microsoft Graph scopes to request.
                    Defaults to Mail.Read, Mail.ReadWrite, offline_access

        Returns:
            Authorization URL to redirect user to

        Raises:
            ValueError: If not configured
        """
        config = self._get_oauth_config()
        if not config:
            raise ValueError("Not configured. Run configure() first.")

        if scopes is None:
            scopes = ["Mail.Read", "Mail.ReadWrite", "offline_access"]

        tenant_id = config.get('tenant_id', 'common')
        auth_base = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"

        params = {
            'client_id': config['client_id'],
            'response_type': 'code',
            'redirect_uri': config.get('redirect_uri', 'http://localhost:8080'),
            'scope': ' '.join(scopes),
            'response_mode': 'query'
        }

        return f"{auth_base}?{urlencode(params)}"

    def get_config(self) -> Optional[Dict]:
        """Get the current OAuth configuration (for debugging).

        Returns:
            Dict with client_id (masked), tenant_id, redirect_uri
        """
        config = self._get_oauth_config()
        if not config:
            return None

        # Return config with masked secret
        return {
            'client_id': config.get('client_id', ''),
            'client_secret': '***' if config.get('client_secret') else None,
            'tenant_id': config.get('tenant_id', 'common'),
            'redirect_uri': config.get('redirect_uri', 'http://localhost:8080')
        }

    def authenticate(self, auth_code: str, scopes: list = None) -> Dict:
        """Exchange authorization code for access and refresh tokens.

        After the user authorizes in the browser, they get redirected with a 'code'
        parameter. Pass that code to this method to exchange it for tokens.

        Args:
            auth_code: The authorization code from the OAuth redirect
            scopes: List of scopes (should match what was requested in get_auth_url)

        Returns:
            Dict with access_token, refresh_token, expires_at, scopes

        Raises:
            ValueError: If not configured
            requests.RequestException: If token exchange fails
        """
        config = self._get_oauth_config()
        if not config:
            raise ValueError("Not configured. Run configure() first.")

        if scopes is None:
            scopes = ["Mail.Read", "Mail.ReadWrite", "offline_access"]

        tenant_id = config.get('tenant_id', 'common')
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        # Prepare token request
        data = {
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'code': auth_code,
            'redirect_uri': config.get('redirect_uri', 'http://localhost:8080'),
            'grant_type': 'authorization_code',
            'scope': ' '.join(scopes)
        }

        # Exchange code for tokens
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()

        # Calculate expiration time
        expires_in = token_data.get('expires_in', 3600)
        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

        # Store tokens in database
        self._store_tokens(
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            expires_at=expires_at,
            scopes=scopes
        )

        return {
            'access_token': token_data['access_token'],
            'refresh_token': token_data.get('refresh_token'),
            'expires_at': expires_at,
            'scopes': scopes
        }

    def _store_tokens(self, access_token: str, refresh_token: str,
                      expires_at: str, scopes: list) -> bool:
        """Store OAuth tokens in the database.

        Args:
            access_token: The access token for API calls
            refresh_token: The refresh token for getting new access tokens
            expires_at: ISO timestamp when access_token expires
            scopes: List of granted scopes

        Returns:
            True if stored successfully
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        # Remove existing token rows (keep config rows)
        cursor.execute("""
            DELETE FROM oauth_tokens
            WHERE provider = ? AND access_token IS NOT NULL
        """, (PROVIDER,))

        # Insert new token row
        cursor.execute("""
            INSERT INTO oauth_tokens (provider, access_token, refresh_token, expires_at, scopes)
            VALUES (?, ?, ?, ?, ?)
        """, (PROVIDER, access_token, refresh_token, expires_at, json.dumps(scopes)))

        conn.commit()
        conn.close()

        self._token = None  # Clear cached token
        return True

    def get_token(self) -> Optional[Dict]:
        """Retrieve stored OAuth tokens from the database.

        Returns:
            Dict with access_token, refresh_token, expires_at, scopes
            or None if no tokens are stored
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT access_token, refresh_token, expires_at, scopes
            FROM oauth_tokens
            WHERE provider = ? AND access_token IS NOT NULL
            ORDER BY id DESC LIMIT 1
        """, (PROVIDER,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'access_token': row['access_token'],
                'refresh_token': row['refresh_token'],
                'expires_at': row['expires_at'],
                'scopes': json.loads(row['scopes']) if row['scopes'] else []
            }
        return None

    def is_authenticated(self) -> bool:
        """Check if we have valid tokens stored.

        Returns:
            True if access_token and refresh_token are stored
        """
        token = self.get_token()
        return token is not None and token.get('access_token') is not None

    def _is_token_expired(self, token: Dict) -> bool:
        """Check if the access token is expired or about to expire.

        Args:
            token: Token dict with expires_at field

        Returns:
            True if token is expired or will expire within 5 minutes
        """
        if not token or not token.get('expires_at'):
            return True

        try:
            expires_at = datetime.fromisoformat(token['expires_at'])
            # Consider expired if less than 5 minutes remaining
            buffer = timedelta(minutes=5)
            return datetime.now() >= (expires_at - buffer)
        except (ValueError, TypeError):
            return True

    def refresh_token(self) -> Dict:
        """Refresh the access token using the stored refresh token.

        Makes a request to Microsoft's token endpoint with the refresh token
        to get a new access token (and potentially a new refresh token).

        Returns:
            Dict with new access_token, refresh_token, expires_at, scopes

        Raises:
            ValueError: If not configured or no refresh token available
            requests.RequestException: If token refresh fails
        """
        config = self._get_oauth_config()
        if not config:
            raise ValueError("Not configured. Run configure() first.")

        token = self.get_token()
        if not token or not token.get('refresh_token'):
            raise ValueError("No refresh token available. Re-authenticate required.")

        tenant_id = config.get('tenant_id', 'common')
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        # Prepare refresh request
        data = {
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'refresh_token': token['refresh_token'],
            'grant_type': 'refresh_token',
            'scope': ' '.join(token.get('scopes', ['Mail.Read', 'Mail.ReadWrite', 'offline_access']))
        }

        # Request new tokens
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()

        # Calculate expiration time
        expires_in = token_data.get('expires_in', 3600)
        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

        # Microsoft may issue a new refresh token, or we keep the old one
        new_refresh_token = token_data.get('refresh_token', token['refresh_token'])
        scopes = token.get('scopes', ['Mail.Read', 'Mail.ReadWrite', 'offline_access'])

        # Store new tokens in database
        self._store_tokens(
            access_token=token_data['access_token'],
            refresh_token=new_refresh_token,
            expires_at=expires_at,
            scopes=scopes
        )

        return {
            'access_token': token_data['access_token'],
            'refresh_token': new_refresh_token,
            'expires_at': expires_at,
            'scopes': scopes
        }

    def get_valid_token(self) -> Dict:
        """Get a valid access token, auto-refreshing if expired.

        This is the primary method to use when making API calls. It checks
        if the current token is expired and automatically refreshes it.

        Returns:
            Dict with access_token, refresh_token, expires_at, scopes

        Raises:
            ValueError: If not authenticated or refresh fails
        """
        token = self.get_token()

        if not token:
            raise ValueError("Not authenticated. Run authenticate() first.")

        if self._is_token_expired(token):
            # Token is expired or about to expire, refresh it
            return self.refresh_token()

        return token

    def api_request(self, method: str, endpoint: str, data: Dict = None,
                    params: Dict = None) -> Dict:
        """Make an authenticated request to Microsoft Graph API.

        This method handles authentication, token refresh, and error handling
        for all Graph API calls.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint path (e.g., "/me/messages" or "/me/mailFolders")
                      Can be full URL or relative path (will be prefixed with GRAPH_URL)
            data: Request body for POST/PATCH requests (will be sent as JSON)
            params: URL query parameters

        Returns:
            Dict with the API response (parsed JSON)

        Raises:
            ValueError: If not authenticated
            requests.RequestException: If API request fails

        Example:
            # Get recent messages
            client.api_request("GET", "/me/messages", params={"$top": 10})

            # Create a draft email
            client.api_request("POST", "/me/messages", data={
                "subject": "Test",
                "body": {"contentType": "Text", "content": "Hello"},
                "toRecipients": [{"emailAddress": {"address": "test@example.com"}}]
            })
        """
        # Get valid token (auto-refreshes if needed)
        token = self.get_valid_token()

        # Build full URL
        if endpoint.startswith("http"):
            url = endpoint
        else:
            # Ensure endpoint starts with /
            if not endpoint.startswith("/"):
                endpoint = "/" + endpoint
            url = f"{GRAPH_URL}{endpoint}"

        # Build headers
        headers = {
            "Authorization": f"Bearer {token['access_token']}",
            "Content-Type": "application/json"
        }

        # Make request
        method = method.upper()
        if method == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, params=params)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=data, params=params)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, params=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Handle response
        response.raise_for_status()

        # Some endpoints return empty response (e.g., DELETE)
        if response.status_code == 204 or not response.content:
            return {"success": True, "status_code": response.status_code}

        return response.json()


# CLI Interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Microsoft Graph API Client for PCP")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Configure command
    configure_parser = subparsers.add_parser("configure", help="Configure OAuth credentials")
    configure_parser.add_argument("client_id", help="Azure AD client ID")
    configure_parser.add_argument("client_secret", help="Azure AD client secret")
    configure_parser.add_argument("--tenant", default="common", help="Azure AD tenant ID (default: common)")
    configure_parser.add_argument("--redirect-uri", default="http://localhost:8080",
                                  help="OAuth redirect URI (default: http://localhost:8080)")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show configuration status")

    # Auth URL command
    auth_parser = subparsers.add_parser("auth-url", help="Get OAuth authorization URL")
    auth_parser.add_argument("--scopes", nargs="+", help="OAuth scopes to request")

    # Authenticate command (exchange code for tokens)
    authenticate_parser = subparsers.add_parser("authenticate", help="Exchange auth code for tokens")
    authenticate_parser.add_argument("auth_code", help="Authorization code from OAuth redirect")
    authenticate_parser.add_argument("--scopes", nargs="+", help="OAuth scopes (should match auth-url)")

    # API request command (for testing)
    api_parser = subparsers.add_parser("api", help="Make an API request (for testing)")
    api_parser.add_argument("method", choices=["GET", "POST", "PATCH", "DELETE"],
                            help="HTTP method")
    api_parser.add_argument("endpoint", help="API endpoint (e.g., /me/messages)")
    api_parser.add_argument("--data", type=json.loads, help="JSON request body")
    api_parser.add_argument("--params", type=json.loads, help="URL query parameters as JSON")

    args = parser.parse_args()

    client = MicrosoftGraphClient()

    if args.command == "configure":
        client.configure(
            args.client_id,
            args.client_secret,
            args.tenant,
            args.redirect_uri
        )
        print("Configuration saved successfully.")
        print(f"Next step: Run 'python microsoft_graph.py auth-url' to get the OAuth URL")

    elif args.command == "status":
        if client.is_configured():
            config = client.get_config()
            print("Status: Configured")
            print(f"  Client ID: {config['client_id'][:8]}...{config['client_id'][-4:]}" if len(config.get('client_id', '')) > 12 else f"  Client ID: {config.get('client_id', 'N/A')}")
            print(f"  Tenant: {config.get('tenant_id', 'N/A')}")
            print(f"  Redirect URI: {config.get('redirect_uri', 'N/A')}")

            # Show token status
            if client.is_authenticated():
                token = client.get_token()
                print(f"\nAuthentication: Active")
                print(f"  Access token: {token['access_token'][:20]}...")
                print(f"  Refresh token: {'Present' if token['refresh_token'] else 'Not available'}")
                print(f"  Expires at: {token['expires_at']}")
            else:
                print(f"\nAuthentication: Not authenticated")
                print("Run: python microsoft_graph.py auth-url")
        else:
            print("Status: Not configured")
            print("Run: python microsoft_graph.py configure CLIENT_ID CLIENT_SECRET")

    elif args.command == "auth-url":
        try:
            url = client.get_auth_url(args.scopes)
            print("\nOpen this URL in your browser to authorize:")
            print(url)
            print("\nAfter authorizing, copy the 'code' parameter from the redirect URL.")
            print("Then run: python microsoft_graph.py authenticate <code>")
        except ValueError as e:
            print(f"Error: {e}")

    elif args.command == "authenticate":
        try:
            result = client.authenticate(args.auth_code, args.scopes)
            print("Authentication successful!")
            print(f"  Access token: {result['access_token'][:20]}...")
            print(f"  Refresh token: {'Present' if result['refresh_token'] else 'Not provided'}")
            print(f"  Expires at: {result['expires_at']}")
            print(f"  Scopes: {', '.join(result['scopes'])}")
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Authentication failed: {e}")

    elif args.command == "api":
        try:
            result = client.api_request(args.method, args.endpoint,
                                        data=args.data, params=args.params)
            print(json.dumps(result, indent=2))
        except ValueError as e:
            print(f"Error: {e}")
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"Response: {e.response.json()}")
                except:
                    print(f"Response: {e.response.text}")

    else:
        parser.print_help()
