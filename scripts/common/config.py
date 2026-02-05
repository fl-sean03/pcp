"""
Configuration loader for PCP.

Loads settings from config/pcp.yaml and provides typed access.
"""

import os
import yaml
from typing import Any, Dict, Optional


# Find config file
_CONFIG_PATH = None
_config_cache = None

def _find_config_file() -> Optional[str]:
    """Locate the pcp.yaml config file."""
    # Check relative to this file (scripts/common -> config)
    local_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "pcp.yaml")
    if os.path.exists(local_path):
        return os.path.abspath(local_path)

    # Check container path
    container_path = "/workspace/config/pcp.yaml"
    if os.path.exists(container_path):
        return container_path

    return None


def load_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Load configuration from pcp.yaml.

    Args:
        force_reload: If True, reload from disk even if cached

    Returns:
        Configuration dictionary
    """
    global _config_cache

    if _config_cache is not None and not force_reload:
        return _config_cache

    config_path = _find_config_file()
    if not config_path:
        # Return sensible defaults if no config file
        return get_default_config()

    try:
        with open(config_path, 'r') as f:
            _config_cache = yaml.safe_load(f)
            return _config_cache
    except Exception as e:
        print(f"Warning: Could not load config from {config_path}: {e}")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """Return default configuration values."""
    return {
        "worker": {
            "timeout_seconds": 600,
            "max_concurrent": 1,
            "container_name": "pcp-agent",
            "poll_interval_seconds": 60
        },
        "scheduler": {
            "daily_brief_hour": 8,
            "eod_digest_hour": 18,
            "weekly_summary_day": 0,
            "reminder_interval_minutes": 60,
            "poll_interval_seconds": 300
        },
        "thresholds": {
            "stale_relationship_days": 14,
            "project_stale_days": 30,
            "project_needs_attention_days": 14,
            "repeated_topic_threshold": 3,
            "repeated_topic_days": 7
        },
        "briefs": {
            "default_lookback_days": 7,
            "meeting_prep_capture_limit": 10,
            "daily_capture_limit": 20,
            "max_stale_relationships": 10
        },
        "search": {
            "default_limit": 20,
            "semantic_enabled": True
        }
    }


def get(key: str, default: Any = None) -> Any:
    """
    Get a config value by dot-notation key.

    Args:
        key: Dot-notation key (e.g., "thresholds.stale_relationship_days")
        default: Default value if key not found

    Returns:
        Config value or default

    Example:
        >>> get("thresholds.stale_relationship_days", 14)
        14
        >>> get("worker.timeout_seconds")
        600
    """
    config = load_config()

    parts = key.split(".")
    value = config

    try:
        for part in parts:
            value = value[part]
        return value
    except (KeyError, TypeError):
        return default


def get_section(section: str) -> Dict[str, Any]:
    """
    Get an entire config section.

    Args:
        section: Section name (e.g., "thresholds", "worker")

    Returns:
        Section dictionary or empty dict
    """
    config = load_config()
    return config.get(section, {})


# Convenience functions for common settings
def get_timeout(name: str = "default") -> int:
    """Get a timeout value in seconds."""
    timeouts = {
        "default": get("worker.timeout_seconds", 600),
        "worker": get("worker.timeout_seconds", 600),
        "poll": get("scheduler.poll_interval_seconds", 300),
    }
    return timeouts.get(name, 600)


def get_threshold(name: str) -> int:
    """Get a threshold value."""
    return get(f"thresholds.{name}", 14)


# Module-level config access
CONFIG = load_config()
