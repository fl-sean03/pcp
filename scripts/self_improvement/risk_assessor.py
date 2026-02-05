"""
Risk assessment framework for capability acquisition.

Determines whether a capability can be acquired automatically or requires
user approval based on various risk factors.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .capability_patterns import (
    CAPABILITY_PATTERNS,
    get_pattern_for_gap,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
    GAP_TYPE_FILE_PROCESSING,
    GAP_TYPE_SERVICE_INTEGRATION,
    GAP_TYPE_CLOUD_PROVIDER,
    GAP_TYPE_CLI_TOOL,
    GAP_TYPE_API_ACCESS,
)
from .exceptions import CapabilityGapError


class RiskLevel(Enum):
    """Risk levels for capability acquisition."""
    LOW = "low"           # Just do it
    MEDIUM = "medium"     # Do it + notify
    HIGH = "high"         # Ask first
    CRITICAL = "critical" # Explicit approval required


@dataclass
class RiskAssessment:
    """Result of a risk assessment."""
    level: RiskLevel
    score: float  # 0.0 to 1.0
    factors: List[str]
    requires_approval: bool
    requires_credentials: bool
    estimated_cost: Optional[str]
    reversible: bool
    recommendation: str


# Risk factor weights
RISK_WEIGHTS = {
    # Gap type base weights
    "type_file_processing": 0.1,
    "type_cli_tool": 0.15,
    "type_api_access": 0.4,
    "type_service_integration": 0.5,
    "type_cloud_provider": 0.7,

    # Credential requirements
    "requires_credentials": 0.3,
    "requires_api_key": 0.25,
    "requires_oauth": 0.35,

    # Cost factors
    "has_usage_cost": 0.2,
    "has_subscription_cost": 0.4,

    # Security factors
    "network_access": 0.15,
    "filesystem_access": 0.2,
    "sudo_required": 0.25,
    "external_api_calls": 0.2,

    # Reversibility
    "irreversible_action": 0.3,
    "data_modification": 0.25,

    # Scope
    "system_wide_change": 0.35,
    "container_only": -0.1,
}


def assess_risk(gap: CapabilityGapError) -> RiskAssessment:
    """
    Assess the risk level of acquiring a capability.

    Args:
        gap: The capability gap to assess

    Returns:
        RiskAssessment with level, score, and recommendations
    """
    factors = []
    score = 0.0

    # Get pattern if available
    pattern = get_pattern_for_gap(gap.failure_pattern) if gap.failure_pattern else {}

    # 1. Base risk from gap type
    type_factor = _get_type_risk(gap.gap_type)
    score += type_factor
    factors.append(f"Gap type: {gap.gap_type}")

    # 2. Credential requirements
    if pattern.get("requires_user_input", False):
        score += RISK_WEIGHTS["requires_credentials"]
        factors.append("Requires credentials/API keys")

    required_inputs = pattern.get("required_inputs", [])
    if any("API_KEY" in inp or "TOKEN" in inp for inp in required_inputs):
        score += RISK_WEIGHTS["requires_api_key"]
        factors.append("Requires API key")

    if any("OAUTH" in inp for inp in required_inputs):
        score += RISK_WEIGHTS["requires_oauth"]
        factors.append("Requires OAuth")

    # 3. Analyze suggested solutions
    solutions = gap.suggested_solutions or pattern.get("suggested_solutions", [])
    for solution in solutions:
        sol_type = solution.get("type", "")
        install_cmd = solution.get("install_command", "")

        if "sudo" in install_cmd:
            score += RISK_WEIGHTS["sudo_required"]
            factors.append("Requires sudo")

        if sol_type == "system_package":
            score += RISK_WEIGHTS["system_wide_change"] * 0.5
            factors.append("System package installation")

        if sol_type == "python_package":
            score += RISK_WEIGHTS["container_only"]  # Negative - lower risk
            factors.append("Python package (container-scoped)")

    # 4. Check for cost implications
    estimated_cost = _estimate_cost(gap, pattern)
    if estimated_cost:
        if "subscription" in estimated_cost.lower():
            score += RISK_WEIGHTS["has_subscription_cost"]
            factors.append("Has subscription cost")
        elif "usage" in estimated_cost.lower() or "pay" in estimated_cost.lower():
            score += RISK_WEIGHTS["has_usage_cost"]
            factors.append("Has usage-based cost")

    # 5. Check reversibility
    reversible = _check_reversibility(gap, pattern, solutions)
    if not reversible:
        score += RISK_WEIGHTS["irreversible_action"]
        factors.append("May not be easily reversible")

    # Normalize score to 0-1
    score = max(0.0, min(1.0, score))

    # Determine risk level
    level = _score_to_level(score)

    # Determine if approval is required
    requires_approval = (
        level in (RiskLevel.HIGH, RiskLevel.CRITICAL) or
        pattern.get("requires_user_input", False)
    )

    # Build recommendation
    recommendation = _build_recommendation(level, gap, pattern, factors)

    return RiskAssessment(
        level=level,
        score=score,
        factors=factors,
        requires_approval=requires_approval,
        requires_credentials=pattern.get("requires_user_input", False),
        estimated_cost=estimated_cost,
        reversible=reversible,
        recommendation=recommendation
    )


def _get_type_risk(gap_type: str) -> float:
    """Get base risk score for gap type."""
    type_weights = {
        GAP_TYPE_FILE_PROCESSING: RISK_WEIGHTS["type_file_processing"],
        GAP_TYPE_CLI_TOOL: RISK_WEIGHTS["type_cli_tool"],
        GAP_TYPE_API_ACCESS: RISK_WEIGHTS["type_api_access"],
        GAP_TYPE_SERVICE_INTEGRATION: RISK_WEIGHTS["type_service_integration"],
        GAP_TYPE_CLOUD_PROVIDER: RISK_WEIGHTS["type_cloud_provider"],
    }
    return type_weights.get(gap_type, 0.3)


def _score_to_level(score: float) -> RiskLevel:
    """Convert numeric score to risk level."""
    if score < 0.25:
        return RiskLevel.LOW
    elif score < 0.50:
        return RiskLevel.MEDIUM
    elif score < 0.75:
        return RiskLevel.HIGH
    else:
        return RiskLevel.CRITICAL


def _estimate_cost(gap: CapabilityGapError, pattern: Dict) -> Optional[str]:
    """Estimate cost implications of acquiring the capability."""
    # Check known cost patterns
    cost_patterns = {
        "openai_api": "Pay-per-use API costs (charged to your OpenAI account)",
        "aws_access": "AWS resource costs (charged to your AWS account)",
        "gcp_access": "GCP resource costs (charged to your GCP account)",
        "oracle_cloud_access": "OCI resource costs (charged to your Oracle account)",
    }

    if gap.failure_pattern in cost_patterns:
        return cost_patterns[gap.failure_pattern]

    # Check input instructions for cost mentions
    instructions = pattern.get("input_instructions", "")
    if "charged" in instructions.lower() or "cost" in instructions.lower():
        return "May incur usage costs"

    return None


def _check_reversibility(
    gap: CapabilityGapError,
    pattern: Dict,
    solutions: List[Dict]
) -> bool:
    """Check if the acquisition is reversible."""
    # Most package installations are reversible
    for solution in solutions:
        sol_type = solution.get("type", "")
        if sol_type in ("python_package", "system_package"):
            return True  # Can uninstall

    # Service integrations are generally reversible (can delete API key)
    if gap.gap_type == GAP_TYPE_SERVICE_INTEGRATION:
        return True

    # Cloud provider access can be revoked
    if gap.gap_type == GAP_TYPE_CLOUD_PROVIDER:
        return True

    # Default to reversible
    return True


def _build_recommendation(
    level: RiskLevel,
    gap: CapabilityGapError,
    pattern: Dict,
    factors: List[str]
) -> str:
    """Build a human-readable recommendation."""
    if level == RiskLevel.LOW:
        return (
            f"Safe to proceed automatically. "
            f"This is a low-risk {gap.gap_type} operation."
        )

    elif level == RiskLevel.MEDIUM:
        return (
            f"Can proceed but notify user afterward. "
            f"Risk factors: {', '.join(factors[:3])}"
        )

    elif level == RiskLevel.HIGH:
        if pattern.get("requires_user_input"):
            required = pattern.get("required_inputs", [])
            return (
                f"User input required before proceeding. "
                f"Needed: {', '.join(required)}"
            )
        return (
            f"Ask user for approval before proceeding. "
            f"Risk factors: {', '.join(factors[:3])}"
        )

    else:  # CRITICAL
        return (
            f"Explicit user approval required. "
            f"This operation has significant implications: {', '.join(factors[:3])}"
        )


def can_auto_acquire(gap: CapabilityGapError) -> Tuple[bool, str]:
    """
    Quick check if a capability can be acquired automatically.

    Returns:
        Tuple of (can_auto, reason)
    """
    assessment = assess_risk(gap)

    if assessment.level == RiskLevel.LOW:
        return True, "Low risk - proceeding automatically"

    if assessment.level == RiskLevel.MEDIUM:
        return True, "Medium risk - will notify after completion"

    if assessment.requires_credentials:
        return False, f"Requires credentials: {assessment.recommendation}"

    return False, assessment.recommendation


def get_risk_summary(assessment: RiskAssessment) -> str:
    """Get a brief summary of the risk assessment."""
    level_emoji = {
        RiskLevel.LOW: "🟢",
        RiskLevel.MEDIUM: "🟡",
        RiskLevel.HIGH: "🟠",
        RiskLevel.CRITICAL: "🔴",
    }

    emoji = level_emoji[assessment.level]
    cost_info = f" (Cost: {assessment.estimated_cost})" if assessment.estimated_cost else ""

    return (
        f"{emoji} Risk: {assessment.level.value.upper()}{cost_info}\n"
        f"Score: {assessment.score:.2f}\n"
        f"Approval required: {'Yes' if assessment.requires_approval else 'No'}\n"
        f"Credentials needed: {'Yes' if assessment.requires_credentials else 'No'}\n"
        f"Reversible: {'Yes' if assessment.reversible else 'No'}\n"
        f"\nRecommendation: {assessment.recommendation}"
    )


# CLI interface
if __name__ == "__main__":
    import argparse
    import json

    from .capability_detector import detect_capability_gap

    parser = argparse.ArgumentParser(description="Risk assessment for capability gaps")
    parser.add_argument("--pattern", help="Pattern ID to assess")
    parser.add_argument("--task", default="", help="Task description")
    parser.add_argument("--error", default="", help="Error message")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Create a gap to assess
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
    elif args.task or args.error:
        gap = detect_capability_gap(
            task_description=args.task,
            error_message=args.error
        )
        if not gap:
            print("No capability gap detected")
            exit(0)
    else:
        parser.print_help()
        exit(1)

    # Assess risk
    assessment = assess_risk(gap)

    if args.json:
        result = {
            "level": assessment.level.value,
            "score": assessment.score,
            "factors": assessment.factors,
            "requires_approval": assessment.requires_approval,
            "requires_credentials": assessment.requires_credentials,
            "estimated_cost": assessment.estimated_cost,
            "reversible": assessment.reversible,
            "recommendation": assessment.recommendation,
        }
        print(json.dumps(result, indent=2))
    else:
        print(get_risk_summary(assessment))
