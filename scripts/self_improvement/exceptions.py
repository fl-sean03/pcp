"""
Exception classes for the self-improvement system.
"""

from typing import Optional, Dict, Any


class CapabilityGapError(Exception):
    """
    Raised when a task cannot be completed due to a missing capability.

    This exception signals to the self-improvement system that it should
    attempt to acquire the missing capability.

    Attributes:
        gap_type: Category of the gap (file_processing, service_integration, etc.)
        gap_description: Human-readable description of what's missing
        original_task: What the user was trying to do
        context: Additional context for resolution
        suggested_solutions: List of potential solutions
    """

    def __init__(
        self,
        gap_type: str,
        gap_description: str,
        original_task: str = "",
        context: Optional[Dict[str, Any]] = None,
        suggested_solutions: Optional[list] = None,
        failure_pattern: str = ""
    ):
        self.gap_type = gap_type
        self.gap_description = gap_description
        self.original_task = original_task
        self.context = context or {}
        self.suggested_solutions = suggested_solutions or []
        self.failure_pattern = failure_pattern

        message = f"Capability gap detected: {gap_type} - {gap_description}"
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "gap_type": self.gap_type,
            "gap_description": self.gap_description,
            "original_task": self.original_task,
            "context": self.context,
            "suggested_solutions": self.suggested_solutions,
            "failure_pattern": self.failure_pattern,
        }


class CapabilityAcquisitionFailed(Exception):
    """
    Raised when capability acquisition fails.

    Attributes:
        reason: Why acquisition failed
        gap_type: The type of gap that couldn't be resolved
        attempted_solutions: What was tried
        user_action_required: If user needs to do something
    """

    def __init__(
        self,
        reason: str,
        gap_type: str = "",
        attempted_solutions: Optional[list] = None,
        user_action_required: Optional[str] = None
    ):
        self.reason = reason
        self.gap_type = gap_type
        self.attempted_solutions = attempted_solutions or []
        self.user_action_required = user_action_required

        message = f"Failed to acquire capability: {reason}"
        if user_action_required:
            message += f" (User action required: {user_action_required})"
        super().__init__(message)


class UserInputRequired(Exception):
    """
    Raised when user input is required to proceed with acquisition.

    This is not an error - it's a signal that the system needs user input
    before it can continue.
    """

    def __init__(
        self,
        prompt: str,
        required_inputs: list,
        context: Optional[Dict[str, Any]] = None
    ):
        self.prompt = prompt
        self.required_inputs = required_inputs
        self.context = context or {}
        super().__init__(prompt)
