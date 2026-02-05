"""
Common utilities for PCP scripts.

This package provides shared functionality to eliminate duplication:
- db: Database connection and helpers
- environment: Runtime environment detection
- config: Configuration loading and access
"""

from .db import (
    get_db_connection,
    get_vault_path,
    row_to_dict,
    rows_to_dicts,
    execute_query,
    execute_write,
    VAULT_PATH,
)

from .environment import (
    is_in_container,
    get_workspace_path,
    get_vault_directory,
    get_scripts_directory,
    get_config_directory,
    resolve_path,
    RUNNING_IN_CONTAINER,
    WORKSPACE_ROOT,
)

from .config import (
    load_config,
    get as get_config,
    get_section,
    get_timeout,
    get_threshold,
    CONFIG,
)

__all__ = [
    # Database
    "get_db_connection",
    "get_vault_path",
    "row_to_dict",
    "rows_to_dicts",
    "execute_query",
    "execute_write",
    "VAULT_PATH",
    # Environment
    "is_in_container",
    "get_workspace_path",
    "get_vault_directory",
    "get_scripts_directory",
    "get_config_directory",
    "resolve_path",
    "RUNNING_IN_CONTAINER",
    "WORKSPACE_ROOT",
    # Config
    "load_config",
    "get_config",
    "get_section",
    "get_timeout",
    "get_threshold",
    "CONFIG",
]
