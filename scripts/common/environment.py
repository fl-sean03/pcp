"""
Environment detection utilities for PCP.

Provides utilities for detecting the runtime environment (container vs local)
and resolving workspace paths appropriately.
"""

import os
from typing import Optional


def is_in_container() -> bool:
    """
    Detect if running inside a Docker container.

    Returns:
        True if running in a container, False otherwise
    """
    # Check for Docker-specific files/paths
    if os.path.exists("/.dockerenv"):
        return True
    if os.path.exists("/run/.containerenv"):
        return True
    # Check cgroup (Linux containers)
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read() or "lxc" in f.read()
    except (FileNotFoundError, PermissionError):
        pass
    # Check for /workspace which is our container mount point
    return os.path.exists("/workspace") and os.path.isdir("/workspace/vault")


def get_workspace_path() -> str:
    """
    Get the workspace root path.

    Returns:
        /workspace in container, or local project root otherwise
    """
    if is_in_container():
        return "/workspace"
    # Local development - find project root
    current = os.path.dirname(os.path.abspath(__file__))
    # Go up from scripts/common to project root
    return os.path.normpath(os.path.join(current, "..", ".."))


def get_vault_directory() -> str:
    """
    Get the vault data directory.

    Returns:
        Path to vault directory
    """
    return os.path.join(get_workspace_path(), "vault")


def get_scripts_directory() -> str:
    """
    Get the scripts directory.

    Returns:
        Path to scripts directory
    """
    return os.path.join(get_workspace_path(), "scripts")


def get_config_directory() -> str:
    """
    Get the config directory.

    Returns:
        Path to config directory
    """
    return os.path.join(get_workspace_path(), "config")


def resolve_path(relative_path: str) -> str:
    """
    Resolve a relative path to absolute based on workspace root.

    Args:
        relative_path: Path relative to workspace root

    Returns:
        Absolute path
    """
    return os.path.join(get_workspace_path(), relative_path)


# Runtime environment info
RUNNING_IN_CONTAINER = is_in_container()
WORKSPACE_ROOT = get_workspace_path()


# =============================================================================
# Development vs Production Environment
# =============================================================================

def get_pcp_environment() -> str:
    """Get current PCP environment (development or production)."""
    return os.environ.get('PCP_ENV', 'development')


def is_production() -> bool:
    """Check if running in production environment."""
    return get_pcp_environment() == 'production'


def is_development() -> bool:
    """Check if running in development environment."""
    return get_pcp_environment() == 'development'


def is_test_mode() -> bool:
    """Check if running in test mode."""
    return os.environ.get('TEST_MODE', 'false').lower() == 'true'


def get_vault_db_path() -> str:
    """Get database path based on environment."""
    # Explicit environment variable takes precedence
    explicit_path = os.environ.get('VAULT_DB_PATH')
    if explicit_path:
        return explicit_path

    # Default paths based on environment
    vault_dir = get_vault_directory()
    if is_production():
        return os.path.join(vault_dir, 'vault.db')
    else:
        return os.path.join(vault_dir, 'vault_dev.db')


def get_discord_webhook() -> Optional[str]:
    """Get Discord webhook URL based on environment."""
    # Check for environment-specific webhook first
    if is_development():
        webhook = os.environ.get('DISCORD_WEBHOOK_DEV')
        if webhook:
            return webhook

    # Fall back to general webhook
    return os.environ.get('DISCORD_WEBHOOK_URL')


def get_discord_channel_id() -> Optional[str]:
    """Get Discord channel ID based on environment."""
    return os.environ.get('DISCORD_CHANNEL_ID')


def get_log_level() -> str:
    """Get log level based on environment."""
    default = 'DEBUG' if is_development() else 'INFO'
    return os.environ.get('LOG_LEVEL', default)


def get_log_directory() -> str:
    """Get log directory based on environment."""
    base = os.path.join(get_workspace_path(), 'logs')
    if is_development():
        return os.path.join(base, 'dev')
    return base


def print_environment_info():
    """Print current environment configuration."""
    print(f"PCP Environment: {get_pcp_environment()}")
    print(f"  Container: {RUNNING_IN_CONTAINER}")
    print(f"  Workspace: {WORKSPACE_ROOT}")
    print(f"  Database: {get_vault_db_path()}")
    print(f"  Log Level: {get_log_level()}")
    print(f"  Log Directory: {get_log_directory()}")
    print(f"  Test Mode: {is_test_mode()}")
    print(f"  Discord Webhook: {'configured' if get_discord_webhook() else 'not configured'}")


if __name__ == "__main__":
    print_environment_info()
