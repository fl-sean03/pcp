"""
Capability acquisition engine for the self-improvement system.

This module handles the actual process of acquiring missing capabilities:
- Installing packages
- Setting up integrations
- Creating skills
- Managing user interactions for credentials
"""

import os
import subprocess
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .capability_patterns import (
    CAPABILITY_PATTERNS,
    get_pattern_for_gap,
    get_cli_tool_install_command,
    GAP_TYPE_CLI_TOOL,
    GAP_TYPE_FILE_PROCESSING,
)
from .exceptions import (
    CapabilityGapError,
    CapabilityAcquisitionFailed,
    UserInputRequired,
)
from .risk_assessor import assess_risk, RiskLevel, RiskAssessment
from .capability_detector import (
    log_capability_gap,
    update_gap_status,
    check_existing_capability,
)


@dataclass
class AcquisitionResult:
    """Result of a capability acquisition attempt."""
    success: bool
    gap_id: Optional[int] = None
    method: str = ""
    details: str = ""
    skill_created: Optional[str] = None
    error: Optional[str] = None
    user_action_required: Optional[str] = None
    notifications: List[str] = field(default_factory=list)


class CapabilityAcquirer:
    """
    Engine for acquiring missing capabilities.

    This class orchestrates the acquisition process including:
    - Risk assessment
    - User interaction for credentials
    - Package installation
    - Skill creation
    - Result logging
    """

    def __init__(self, auto_approve_low_risk: bool = True, notify_on_medium: bool = True):
        """
        Initialize the capability acquirer.

        Args:
            auto_approve_low_risk: Automatically approve low-risk acquisitions
            notify_on_medium: Send notification for medium-risk acquisitions
        """
        self.auto_approve_low_risk = auto_approve_low_risk
        self.notify_on_medium = notify_on_medium

    def acquire(
        self,
        gap: CapabilityGapError,
        user_credentials: Optional[Dict[str, str]] = None,
        force: bool = False
    ) -> AcquisitionResult:
        """
        Attempt to acquire a missing capability.

        Args:
            gap: The capability gap to resolve
            user_credentials: Pre-provided credentials (if any)
            force: Force acquisition even if risk is high

        Returns:
            AcquisitionResult with success status and details
        """
        # Check if we already have this capability
        has_cap, skill_name = check_existing_capability(gap.failure_pattern)
        if has_cap:
            return AcquisitionResult(
                success=True,
                method="existing",
                details=f"Capability already exists as skill: {skill_name}",
                skill_created=skill_name
            )

        # Log the gap
        gap_id = log_capability_gap(gap, status="resolving")

        try:
            # Assess risk
            assessment = assess_risk(gap)

            # Check if we can proceed
            if not force:
                can_proceed, reason = self._check_can_proceed(assessment, user_credentials)
                if not can_proceed:
                    update_gap_status(gap_id, "user_pending")
                    return AcquisitionResult(
                        success=False,
                        gap_id=gap_id,
                        user_action_required=reason
                    )

            # Get pattern for resolution strategy
            pattern = get_pattern_for_gap(gap.failure_pattern) if gap.failure_pattern else {}

            # Execute acquisition based on gap type
            result = self._execute_acquisition(gap, pattern, user_credentials, assessment)
            result.gap_id = gap_id

            # Update gap status
            if result.success:
                update_gap_status(
                    gap_id,
                    "resolved",
                    resolution_method=result.method,
                    resolution_details=result.details,
                    skill_created=result.skill_created
                )

                # Add notification if medium risk
                if self.notify_on_medium and assessment.level == RiskLevel.MEDIUM:
                    result.notifications.append(
                        f"Capability acquired: {gap.gap_description} ({result.method})"
                    )
            else:
                update_gap_status(
                    gap_id,
                    "failed",
                    resolution_details=result.error
                )

            return result

        except Exception as e:
            update_gap_status(gap_id, "failed", resolution_details=str(e))
            return AcquisitionResult(
                success=False,
                gap_id=gap_id,
                error=str(e)
            )

    def _check_can_proceed(
        self,
        assessment: RiskAssessment,
        user_credentials: Optional[Dict]
    ) -> Tuple[bool, str]:
        """Check if we can proceed with acquisition."""
        # Low risk - always proceed if auto_approve is on
        if assessment.level == RiskLevel.LOW and self.auto_approve_low_risk:
            return True, ""

        # Medium risk - proceed but will notify
        if assessment.level == RiskLevel.MEDIUM:
            return True, ""

        # High/Critical risk - need approval or credentials
        if assessment.requires_credentials:
            if not user_credentials:
                return False, assessment.recommendation
            return True, ""

        # High risk without credentials - need explicit approval
        return False, assessment.recommendation

    def _execute_acquisition(
        self,
        gap: CapabilityGapError,
        pattern: Dict,
        credentials: Optional[Dict],
        assessment: RiskAssessment
    ) -> AcquisitionResult:
        """Execute the acquisition based on gap type and solutions."""
        solutions = gap.suggested_solutions or pattern.get("suggested_solutions", [])

        if not solutions:
            return AcquisitionResult(
                success=False,
                error="No known solutions for this capability gap"
            )

        # Try each solution in order
        for solution in solutions:
            sol_type = solution.get("type", "")

            if sol_type == "python_package":
                result = self._install_python_package(solution)
                if result.success:
                    # Create skill if template exists
                    skill_template = pattern.get("skill_template")
                    if skill_template:
                        skill_result = self._create_skill(skill_template, gap, credentials)
                        if skill_result:
                            result.skill_created = skill_result
                    return result

            elif sol_type == "system_package":
                result = self._install_system_package(solution)
                if result.success:
                    skill_template = pattern.get("skill_template")
                    if skill_template:
                        skill_result = self._create_skill(skill_template, gap, credentials)
                        if skill_result:
                            result.skill_created = skill_result
                    return result

            elif sol_type == "mcp_server":
                result = self._install_mcp_server(solution)
                if result.success:
                    return result

        return AcquisitionResult(
            success=False,
            error="All solution attempts failed"
        )

    def _install_python_package(self, solution: Dict) -> AcquisitionResult:
        """Install a Python package."""
        install_cmd = solution.get("install_command", "")
        test_cmd = solution.get("test_command", "")
        name = solution.get("name", "unknown")

        try:
            # Run install command
            result = subprocess.run(
                install_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                return AcquisitionResult(
                    success=False,
                    method="python_package",
                    error=f"Install failed: {result.stderr}"
                )

            # Run test command if provided
            if test_cmd:
                test_result = subprocess.run(
                    test_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if test_result.returncode != 0:
                    return AcquisitionResult(
                        success=False,
                        method="python_package",
                        error=f"Package test failed: {test_result.stderr}"
                    )

            return AcquisitionResult(
                success=True,
                method="python_package",
                details=f"Installed {name} via pip"
            )

        except subprocess.TimeoutExpired:
            return AcquisitionResult(
                success=False,
                method="python_package",
                error="Installation timed out"
            )
        except Exception as e:
            return AcquisitionResult(
                success=False,
                method="python_package",
                error=str(e)
            )

    def _install_system_package(self, solution: Dict) -> AcquisitionResult:
        """Install a system package via apt."""
        install_cmd = solution.get("install_command", "")
        test_cmd = solution.get("test_command", "")
        name = solution.get("name", "unknown")

        try:
            # Run install command
            result = subprocess.run(
                install_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                return AcquisitionResult(
                    success=False,
                    method="system_package",
                    error=f"Install failed: {result.stderr}"
                )

            # Run test command if provided
            if test_cmd:
                test_result = subprocess.run(
                    test_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if test_result.returncode != 0:
                    return AcquisitionResult(
                        success=False,
                        method="system_package",
                        error=f"Package test failed: {test_result.stderr}"
                    )

            return AcquisitionResult(
                success=True,
                method="system_package",
                details=f"Installed {name} via apt"
            )

        except subprocess.TimeoutExpired:
            return AcquisitionResult(
                success=False,
                method="system_package",
                error="Installation timed out"
            )
        except Exception as e:
            return AcquisitionResult(
                success=False,
                method="system_package",
                error=str(e)
            )

    def _install_mcp_server(self, solution: Dict) -> AcquisitionResult:
        """Install an MCP server."""
        install_cmd = solution.get("install_command", "")
        name = solution.get("name", "unknown")

        try:
            result = subprocess.run(
                install_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                return AcquisitionResult(
                    success=False,
                    method="mcp_server",
                    error=f"MCP install failed: {result.stderr}"
                )

            return AcquisitionResult(
                success=True,
                method="mcp_server",
                details=f"Installed MCP server: {name}"
            )

        except Exception as e:
            return AcquisitionResult(
                success=False,
                method="mcp_server",
                error=str(e)
            )

    def _create_skill(
        self,
        template_name: str,
        gap: CapabilityGapError,
        credentials: Optional[Dict]
    ) -> Optional[str]:
        """Create a skill from a template."""
        skill_dir = f"/workspace/.claude/skills/{template_name}"

        # Check if skill already exists
        if os.path.exists(skill_dir):
            return template_name

        # Generate skill content
        skill_content = self._generate_skill_content(template_name, gap, credentials)

        try:
            os.makedirs(skill_dir, exist_ok=True)

            skill_path = os.path.join(skill_dir, "SKILL.md")
            with open(skill_path, "w") as f:
                f.write(skill_content)

            return template_name

        except Exception as e:
            print(f"Failed to create skill: {e}")
            return None

    def _generate_skill_content(
        self,
        template_name: str,
        gap: CapabilityGapError,
        credentials: Optional[Dict]
    ) -> str:
        """Generate skill content from template."""
        pattern = get_pattern_for_gap(gap.failure_pattern) or {}

        # Build trigger keywords
        triggers = []
        if pattern.get("triggers"):
            triggers = pattern["triggers"].get("text_patterns", [])[:5]

        triggers_yaml = "\n".join(f"  - {t}" for t in triggers) if triggers else "  - " + template_name

        # Build requirements
        requires = []
        for sol in pattern.get("suggested_solutions", []):
            if sol.get("type") == "python_package":
                requires.append(f"    - {sol.get('name', 'unknown')}")

        requires_yaml = "\n".join(requires) if requires else ""

        # Build the skill markdown
        content = f"""---
name: {template_name}
description: {gap.gap_description}
triggers:
{triggers_yaml}
"""

        if requires_yaml:
            content += f"""requires:
  scripts:
{requires_yaml}
"""

        content += f"""---

# {template_name.replace('-', ' ').title()}

## Purpose
{gap.gap_description}

This skill was automatically created by the self-improvement system.

## When to Use
Use this skill when:
- {gap.original_task or f"Processing {gap.gap_type} tasks"}
- Error encountered: {gap.failure_pattern}

## How to Execute
"""

        # Add solution-specific instructions
        for sol in pattern.get("suggested_solutions", []):
            content += f"""
### Using {sol.get('name', 'the tool')}
{sol.get('description', '')}

```python
# Example usage
{sol.get('test_command', '# See documentation')}
```
"""

        # Add credential setup if needed
        if pattern.get("requires_user_input"):
            content += f"""
## Configuration Required
{pattern.get('input_instructions', 'See documentation for setup.')}
"""

        content += f"""
---
Auto-generated: {datetime.now().isoformat()}
Pattern: {gap.failure_pattern}
"""

        return content

    def get_required_inputs(self, gap: CapabilityGapError) -> List[str]:
        """Get list of required inputs for a capability gap."""
        pattern = get_pattern_for_gap(gap.failure_pattern) if gap.failure_pattern else {}
        return pattern.get("required_inputs", [])

    def get_input_instructions(self, gap: CapabilityGapError) -> str:
        """Get instructions for user to provide required inputs."""
        pattern = get_pattern_for_gap(gap.failure_pattern) if gap.failure_pattern else {}
        return pattern.get("input_instructions", "Please provide the required credentials.")


def acquire_capability(
    gap: CapabilityGapError,
    credentials: Optional[Dict[str, str]] = None,
    auto_approve: bool = True
) -> AcquisitionResult:
    """
    Convenience function to acquire a capability.

    Args:
        gap: The capability gap to resolve
        credentials: Pre-provided credentials
        auto_approve: Auto-approve low-risk acquisitions

    Returns:
        AcquisitionResult
    """
    acquirer = CapabilityAcquirer(auto_approve_low_risk=auto_approve)
    return acquirer.acquire(gap, user_credentials=credentials)


def get_acquisition_status(gap_id: int) -> Optional[Dict[str, Any]]:
    """Get the status of an acquisition attempt."""
    from .capability_detector import get_gap_by_id
    return get_gap_by_id(gap_id)


# CLI interface
if __name__ == "__main__":
    import argparse

    from .capability_detector import detect_capability_gap

    parser = argparse.ArgumentParser(description="Capability acquisition")
    subparsers = parser.add_subparsers(dest="command")

    # Acquire command
    acquire_parser = subparsers.add_parser("acquire", help="Acquire a capability")
    acquire_parser.add_argument("--pattern", help="Pattern ID")
    acquire_parser.add_argument("--task", default="", help="Task description")
    acquire_parser.add_argument("--error", default="", help="Error message")
    acquire_parser.add_argument("--force", action="store_true", help="Force acquisition")

    # Status command
    status_parser = subparsers.add_parser("status", help="Get acquisition status")
    status_parser.add_argument("gap_id", type=int, help="Gap ID")

    # Required inputs command
    inputs_parser = subparsers.add_parser("inputs", help="Get required inputs")
    inputs_parser.add_argument("pattern", help="Pattern ID")

    args = parser.parse_args()

    if args.command == "acquire":
        if args.pattern:
            pattern = get_pattern_for_gap(args.pattern)
            if pattern:
                gap = CapabilityGapError(
                    gap_type=pattern.get("gap_type", "unknown"),
                    gap_description=pattern.get("description", ""),
                    original_task=args.task,
                    suggested_solutions=pattern.get("suggested_solutions", []),
                    failure_pattern=args.pattern
                )
            else:
                print(f"Unknown pattern: {args.pattern}")
                exit(1)
        else:
            gap = detect_capability_gap(
                task_description=args.task,
                error_message=args.error
            )
            if not gap:
                print("No capability gap detected")
                exit(0)

        result = acquire_capability(gap, auto_approve=not args.force)
        print(json.dumps({
            "success": result.success,
            "method": result.method,
            "details": result.details,
            "skill_created": result.skill_created,
            "error": result.error,
            "user_action_required": result.user_action_required,
        }, indent=2))

    elif args.command == "status":
        status = get_acquisition_status(args.gap_id)
        if status:
            print(json.dumps(status, indent=2, default=str))
        else:
            print(f"Gap {args.gap_id} not found")

    elif args.command == "inputs":
        pattern = get_pattern_for_gap(args.pattern)
        if pattern:
            print("Required inputs:", pattern.get("required_inputs", []))
            print("\nInstructions:")
            print(pattern.get("input_instructions", "No instructions available"))
        else:
            print(f"Unknown pattern: {args.pattern}")

    else:
        parser.print_help()
