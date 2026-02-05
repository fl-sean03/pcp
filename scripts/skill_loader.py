#!/usr/bin/env python3
"""
PCP Skill Loader

Enhanced skill loading system inspired by Moltbot's AgentSkills pattern.
Features:
- Requirements gating (bins, env vars, scripts, config)
- OS-specific skill filtering
- Per-skill configuration
- Skill enable/disable
- Load-time validation

Usage:
    from skill_loader import load_skills, check_skill_requirements, get_skill_status

    # Load all available skills
    skills = load_skills()

    # Check if a specific skill's requirements are met
    status = check_skill_requirements("voice-transcription")

    # Get status of all skills
    all_status = get_skill_status()
"""

import os
import sys
import yaml
import shutil
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# Add common to path
sys.path.insert(0, str(Path(__file__).parent / "common"))

try:
    from config import load_config
except ImportError:
    def load_config():
        config_path = Path(__file__).parent.parent / "config" / "pcp.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {}


@dataclass
class SkillRequirements:
    """Requirements for a skill to be loaded."""
    bins: List[str] = field(default_factory=list)        # Required CLI tools
    any_bins: List[str] = field(default_factory=list)    # At least one must exist
    env: List[str] = field(default_factory=list)         # Required env vars
    scripts: List[str] = field(default_factory=list)     # Required script files
    config: List[str] = field(default_factory=list)      # Required config values
    os_list: List[str] = field(default_factory=list)     # Allowed operating systems


@dataclass
class Skill:
    """Represents a loaded skill."""
    name: str
    description: str
    path: Path
    requirements: SkillRequirements
    content: str                                          # Full SKILL.md content
    enabled: bool = True
    triggers: List[str] = field(default_factory=list)    # Keyword triggers
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillStatus:
    """Status of a skill's requirements check."""
    name: str
    available: bool
    enabled: bool
    missing_bins: List[str] = field(default_factory=list)
    missing_env: List[str] = field(default_factory=list)
    missing_scripts: List[str] = field(default_factory=list)
    missing_config: List[str] = field(default_factory=list)
    wrong_os: bool = False
    reason: str = ""


def get_skill_directories() -> List[Path]:
    """Get skill directories in precedence order (highest first)."""
    dirs = []

    # Workspace skills (highest priority)
    workspace_skills = Path("/workspace/skills")
    if workspace_skills.exists():
        dirs.append(workspace_skills)

    # Dev workspace skills
    dev_workspace_skills = Path(__file__).parent.parent / "skills"
    if dev_workspace_skills.exists() and dev_workspace_skills not in dirs:
        dirs.append(dev_workspace_skills)

    # User skills (Claude Code convention)
    claude_skills = Path(__file__).parent.parent / ".claude" / "skills"
    if claude_skills.exists():
        dirs.append(claude_skills)

    # Bundled skills (lowest priority)
    bundled = Path(__file__).parent / "bundled_skills"
    if bundled.exists():
        dirs.append(bundled)

    return dirs


def parse_skill_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from SKILL.md content."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].strip()
        return frontmatter or {}, body
    except yaml.YAMLError:
        return {}, content


def parse_requirements(frontmatter: Dict[str, Any]) -> SkillRequirements:
    """Parse requirements from frontmatter."""
    req = frontmatter.get("requires", {})

    return SkillRequirements(
        bins=req.get("bins", []) or [],
        any_bins=req.get("anyBins", []) or req.get("any_bins", []) or [],
        env=req.get("env", []) or [],
        scripts=req.get("scripts", []) or [],
        config=req.get("config", []) or [],
        os_list=frontmatter.get("os", []) or []
    )


def check_bin_exists(bin_name: str) -> bool:
    """Check if a binary exists on PATH."""
    return shutil.which(bin_name) is not None


def check_env_exists(env_name: str) -> bool:
    """Check if an environment variable is set."""
    return bool(os.environ.get(env_name))


def check_script_exists(script_name: str, skill_path: Path) -> bool:
    """Check if a script exists (in skill dir or scripts dir)."""
    # Check in skill directory
    if (skill_path / script_name).exists():
        return True

    # Check in scripts directory
    scripts_dir = Path(__file__).parent
    if (scripts_dir / script_name).exists():
        return True

    # Check in workspace scripts
    workspace_scripts = Path("/workspace/scripts")
    if (workspace_scripts / script_name).exists():
        return True

    return False


def check_config_value(config_path: str, config: Dict[str, Any]) -> bool:
    """Check if a config value exists and is truthy."""
    parts = config_path.split(".")
    current = config

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False

    return bool(current)


def get_current_os() -> str:
    """Get current OS in Moltbot format."""
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "win32"
    return system


def check_skill_requirements(
    skill_name: str,
    skill_path: Optional[Path] = None,
    requirements: Optional[SkillRequirements] = None
) -> SkillStatus:
    """Check if a skill's requirements are met."""
    config = load_config()
    skills_config = config.get("skills", {}).get("entries", {})
    skill_config = skills_config.get(skill_name, {})

    # Check if explicitly disabled
    enabled = skill_config.get("enabled", True)

    status = SkillStatus(
        name=skill_name,
        available=True,
        enabled=enabled
    )

    if not enabled:
        status.available = False
        status.reason = "Skill is disabled in configuration"
        return status

    if requirements is None:
        # Try to load requirements from skill path
        if skill_path is None:
            for dir in get_skill_directories():
                potential_path = dir / skill_name
                if potential_path.exists():
                    skill_path = potential_path
                    break

        if skill_path is None or not skill_path.exists():
            status.available = False
            status.reason = f"Skill directory not found: {skill_name}"
            return status

        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            status.available = False
            status.reason = "SKILL.md not found"
            return status

        with open(skill_md) as f:
            content = f.read()

        frontmatter, _ = parse_skill_frontmatter(content)
        requirements = parse_requirements(frontmatter)

    # Check OS
    if requirements.os_list:
        current_os = get_current_os()
        if current_os not in requirements.os_list:
            status.wrong_os = True
            status.available = False
            status.reason = f"OS mismatch: requires {requirements.os_list}, got {current_os}"
            return status

    # Check required binaries
    for bin_name in requirements.bins:
        if not check_bin_exists(bin_name):
            status.missing_bins.append(bin_name)

    # Check any_bins (at least one must exist)
    if requirements.any_bins:
        if not any(check_bin_exists(b) for b in requirements.any_bins):
            status.missing_bins.extend(requirements.any_bins)

    # Check environment variables
    for env_name in requirements.env:
        if not check_env_exists(env_name):
            status.missing_env.append(env_name)

    # Check scripts
    if skill_path:
        for script_name in requirements.scripts:
            if not check_script_exists(script_name, skill_path):
                status.missing_scripts.append(script_name)

    # Check config values
    for config_path in requirements.config:
        if not check_config_value(config_path, config):
            status.missing_config.append(config_path)

    # Determine availability
    if (status.missing_bins or status.missing_env or
        status.missing_scripts or status.missing_config):
        status.available = False
        reasons = []
        if status.missing_bins:
            reasons.append(f"missing bins: {status.missing_bins}")
        if status.missing_env:
            reasons.append(f"missing env: {status.missing_env}")
        if status.missing_scripts:
            reasons.append(f"missing scripts: {status.missing_scripts}")
        if status.missing_config:
            reasons.append(f"missing config: {status.missing_config}")
        status.reason = "; ".join(reasons)

    return status


def load_skill(skill_path: Path) -> Optional[Skill]:
    """Load a skill from a directory."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    with open(skill_md) as f:
        content = f.read()

    frontmatter, body = parse_skill_frontmatter(content)

    name = frontmatter.get("name", skill_path.name)
    description = frontmatter.get("description", "")
    triggers = frontmatter.get("triggers", [])

    # Parse triggers from description if not explicit
    if not triggers and description:
        triggers = [t.strip() for t in description.split(",")]

    requirements = parse_requirements(frontmatter)

    # Get config for this skill
    config = load_config()
    skill_config = config.get("skills", {}).get("entries", {}).get(name, {})
    enabled = skill_config.get("enabled", True)

    return Skill(
        name=name,
        description=description,
        path=skill_path,
        requirements=requirements,
        content=content,
        enabled=enabled,
        triggers=triggers,
        metadata=frontmatter
    )


def load_skills(
    check_requirements: bool = True,
    include_unavailable: bool = False
) -> Dict[str, Skill]:
    """
    Load all skills from skill directories.

    Args:
        check_requirements: If True, skip skills whose requirements aren't met
        include_unavailable: If True, include unavailable skills in result

    Returns:
        Dict mapping skill names to Skill objects
    """
    skills = {}
    seen_names = set()

    for skill_dir in get_skill_directories():
        if not skill_dir.exists():
            continue

        for item in skill_dir.iterdir():
            if not item.is_dir():
                continue

            skill = load_skill(item)
            if skill is None:
                continue

            # Skip if already loaded (higher priority location wins)
            if skill.name in seen_names:
                continue

            seen_names.add(skill.name)

            if check_requirements:
                status = check_skill_requirements(
                    skill.name,
                    skill.path,
                    skill.requirements
                )

                if not status.available:
                    if include_unavailable:
                        skill.enabled = False
                        skills[skill.name] = skill
                    continue

            skills[skill.name] = skill

    return skills


def get_skill_status() -> Dict[str, SkillStatus]:
    """Get status of all skills."""
    statuses = {}
    seen_names = set()

    for skill_dir in get_skill_directories():
        if not skill_dir.exists():
            continue

        for item in skill_dir.iterdir():
            if not item.is_dir():
                continue

            skill = load_skill(item)
            if skill is None:
                continue

            if skill.name in seen_names:
                continue

            seen_names.add(skill.name)

            status = check_skill_requirements(
                skill.name,
                skill.path,
                skill.requirements
            )
            statuses[skill.name] = status

    return statuses


def format_skill_status_report() -> str:
    """Generate a formatted report of skill status."""
    statuses = get_skill_status()

    lines = ["# PCP Skill Status Report", ""]

    available = [s for s in statuses.values() if s.available]
    unavailable = [s for s in statuses.values() if not s.available]

    lines.append(f"**Available:** {len(available)} | **Unavailable:** {len(unavailable)}")
    lines.append("")

    if available:
        lines.append("## Available Skills")
        for status in sorted(available, key=lambda s: s.name):
            lines.append(f"- ✅ {status.name}")
        lines.append("")

    if unavailable:
        lines.append("## Unavailable Skills")
        for status in sorted(unavailable, key=lambda s: s.name):
            lines.append(f"- ❌ {status.name}: {status.reason}")
        lines.append("")

    return "\n".join(lines)


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PCP Skill Loader")
    parser.add_argument("command", nargs="?", default="status",
                       choices=["status", "list", "check", "dirs"],
                       help="Command to run")
    parser.add_argument("--skill", "-s", help="Specific skill to check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "dirs":
        print("Skill directories (highest priority first):")
        for i, dir in enumerate(get_skill_directories(), 1):
            exists = "✓" if dir.exists() else "✗"
            print(f"  {i}. [{exists}] {dir}")

    elif args.command == "list":
        skills = load_skills(check_requirements=False, include_unavailable=True)
        for name, skill in sorted(skills.items()):
            status = "✓" if skill.enabled else "✗"
            print(f"[{status}] {name}: {skill.description[:60]}...")

    elif args.command == "check":
        if args.skill:
            status = check_skill_requirements(args.skill)
            print(f"Skill: {status.name}")
            print(f"Available: {status.available}")
            print(f"Enabled: {status.enabled}")
            if status.reason:
                print(f"Reason: {status.reason}")
        else:
            print("Specify --skill to check a specific skill")

    elif args.command == "status":
        if args.json:
            import json
            statuses = get_skill_status()
            print(json.dumps({
                name: {
                    "available": s.available,
                    "enabled": s.enabled,
                    "reason": s.reason
                }
                for name, s in statuses.items()
            }, indent=2))
        else:
            print(format_skill_status_report())
