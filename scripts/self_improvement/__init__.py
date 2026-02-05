"""
PCP Self-Improvement System

This module provides autonomous capability acquisition for PCP.
When the agent encounters a task it cannot complete, this system:

1. Detects the capability gap
2. Assesses the risk of acquiring the capability
3. Acquires the capability (or asks user if high-risk)
4. Creates a reusable skill
5. Retries the original task

Usage:
    from self_improvement import execute_with_self_improvement
    from self_improvement import CapabilityGapError, detect_capability_gap
    from self_improvement import acquire_capability
    from self_improvement import assess_risk, RiskLevel
"""

from .exceptions import (
    CapabilityGapError,
    CapabilityAcquisitionFailed,
    UserInputRequired,
)

from .capability_patterns import (
    CAPABILITY_PATTERNS,
    CLI_TOOL_INSTALLATIONS,
    find_matching_patterns,
    get_pattern_for_gap,
    get_cli_tool_install_command,
    GAP_TYPE_FILE_PROCESSING,
    GAP_TYPE_SERVICE_INTEGRATION,
    GAP_TYPE_CLOUD_PROVIDER,
    GAP_TYPE_CLI_TOOL,
    GAP_TYPE_API_ACCESS,
    GAP_TYPE_UNKNOWN,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
)

from .capability_detector import (
    detect_capability_gap,
    log_capability_gap,
    update_gap_status,
    get_gap_by_id,
    get_gaps_by_status,
    get_similar_gaps,
    get_gap_statistics,
    check_existing_capability,
    ensure_capability_gaps_table,
)

from .risk_assessor import (
    assess_risk,
    can_auto_acquire,
    get_risk_summary,
    RiskLevel,
    RiskAssessment,
    RISK_WEIGHTS,
)

from .capability_acquirer import (
    CapabilityAcquirer,
    AcquisitionResult,
    acquire_capability,
    get_acquisition_status,
)

from .execute_wrapper import (
    execute_with_self_improvement,
    self_improving,
    raise_capability_gap,
    ExecutionContext,
)

__all__ = [
    # Exceptions
    'CapabilityGapError',
    'CapabilityAcquisitionFailed',
    'UserInputRequired',

    # Patterns
    'CAPABILITY_PATTERNS',
    'CLI_TOOL_INSTALLATIONS',
    'find_matching_patterns',
    'get_pattern_for_gap',
    'get_cli_tool_install_command',
    'GAP_TYPE_FILE_PROCESSING',
    'GAP_TYPE_SERVICE_INTEGRATION',
    'GAP_TYPE_CLOUD_PROVIDER',
    'GAP_TYPE_CLI_TOOL',
    'GAP_TYPE_API_ACCESS',
    'GAP_TYPE_UNKNOWN',
    'RISK_LOW',
    'RISK_MEDIUM',
    'RISK_HIGH',
    'RISK_CRITICAL',

    # Detection
    'detect_capability_gap',
    'log_capability_gap',
    'update_gap_status',
    'get_gap_by_id',
    'get_gaps_by_status',
    'get_similar_gaps',
    'get_gap_statistics',
    'check_existing_capability',
    'ensure_capability_gaps_table',

    # Risk Assessment
    'assess_risk',
    'can_auto_acquire',
    'get_risk_summary',
    'RiskLevel',
    'RiskAssessment',
    'RISK_WEIGHTS',

    # Acquisition
    'CapabilityAcquirer',
    'AcquisitionResult',
    'acquire_capability',
    'get_acquisition_status',

    # Execution
    'execute_with_self_improvement',
    'self_improving',
    'raise_capability_gap',
    'ExecutionContext',
]

# Version
__version__ = '1.0.0'
