"""
Common database utilities for PCP.

This module provides centralized database connection and helper functions
to eliminate duplication across scripts.
"""

import os
import sqlite3
from typing import Dict, Any, Optional


# Resolve VAULT_PATH once at module load
# Check container path first, then local development path
_VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(_VAULT_PATH)):
    _local_path = os.path.join(os.path.dirname(__file__), "..", "..", "vault", "vault.db")
    if os.path.exists(_local_path):
        _VAULT_PATH = _local_path


def get_vault_path() -> str:
    """Return the resolved vault database path."""
    return _VAULT_PATH


def get_db_connection(path: Optional[str] = None) -> sqlite3.Connection:
    """
    Get a database connection with row factory enabled.

    Args:
        path: Optional path to database. Defaults to VAULT_PATH.

    Returns:
        sqlite3.Connection with Row factory enabled
    """
    db_path = path or _VAULT_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """
    Convert a sqlite3.Row to a dictionary.

    Args:
        row: A sqlite3.Row object

    Returns:
        Dictionary with column names as keys
    """
    if row is None:
        return {}
    return dict(zip(row.keys(), row))


def rows_to_dicts(rows: list) -> list:
    """
    Convert a list of sqlite3.Row objects to a list of dictionaries.

    Args:
        rows: List of sqlite3.Row objects

    Returns:
        List of dictionaries
    """
    return [row_to_dict(row) for row in rows]


def execute_query(query: str, params: tuple = (), path: Optional[str] = None) -> list:
    """
    Execute a read query and return results as list of dicts.

    Args:
        query: SQL query string
        params: Query parameters
        path: Optional database path

    Returns:
        List of result dictionaries
    """
    conn = get_db_connection(path)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return rows_to_dicts(cursor.fetchall())
    finally:
        conn.close()


def execute_write(query: str, params: tuple = (), path: Optional[str] = None) -> int:
    """
    Execute a write query and return the last row ID.

    Args:
        query: SQL query string
        params: Query parameters
        path: Optional database path

    Returns:
        Last inserted row ID
    """
    conn = get_db_connection(path)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# For backwards compatibility, also expose VAULT_PATH as a module-level constant
VAULT_PATH = _VAULT_PATH
