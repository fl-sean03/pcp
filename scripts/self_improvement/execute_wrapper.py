"""
Task execution wrapper with self-improvement capabilities.

This module wraps task execution to detect capability gaps and
automatically attempt to acquire missing capabilities.
"""

import os
import traceback
from typing import Callable, Any, Dict, Optional, TypeVar, Union
from functools import wraps

from .exceptions import CapabilityGapError, CapabilityAcquisitionFailed, UserInputRequired
from .capability_detector import detect_capability_gap, log_capability_gap
from .risk_assessor import assess_risk, RiskLevel
from .capability_acquirer import CapabilityAcquirer, AcquisitionResult


T = TypeVar('T')


class ExecutionContext:
    """Context for a self-improving execution."""

    def __init__(
        self,
        task_description: str = "",
        auto_acquire: bool = True,
        max_retries: int = 2,
        notify_callback: Optional[Callable[[str], None]] = None,
        credentials: Optional[Dict[str, str]] = None
    ):
        """
        Initialize execution context.

        Args:
            task_description: Description of what the task is doing
            auto_acquire: Automatically acquire missing capabilities if low-risk
            max_retries: Maximum number of acquisition + retry attempts
            notify_callback: Callback for notifications (e.g., Discord message)
            credentials: Pre-provided credentials for service integrations
        """
        self.task_description = task_description
        self.auto_acquire = auto_acquire
        self.max_retries = max_retries
        self.notify_callback = notify_callback
        self.credentials = credentials or {}

        self.attempts = 0
        self.gaps_encountered = []
        self.acquisitions = []

    def notify(self, message: str):
        """Send a notification if callback is configured."""
        if self.notify_callback:
            self.notify_callback(message)


def execute_with_self_improvement(
    func: Callable[..., T],
    *args,
    task_description: str = "",
    auto_acquire: bool = True,
    max_retries: int = 2,
    notify_callback: Optional[Callable[[str], None]] = None,
    credentials: Optional[Dict[str, str]] = None,
    **kwargs
) -> Union[T, Dict[str, Any]]:
    """
    Execute a function with self-improvement capabilities.

    If the function fails due to a capability gap, this wrapper will:
    1. Detect the capability gap
    2. Assess the risk
    3. Acquire the capability if safe (or request user input)
    4. Retry the function

    Args:
        func: The function to execute
        *args: Arguments for the function
        task_description: Description of what the task is doing
        auto_acquire: Automatically acquire missing capabilities if low-risk
        max_retries: Maximum number of acquisition + retry attempts
        notify_callback: Callback for notifications
        credentials: Pre-provided credentials
        **kwargs: Keyword arguments for the function

    Returns:
        The function result, or a dict with error/user_action_required if failed

    Example:
        ```python
        def process_audio(path):
            import whisper
            model = whisper.load_model("base")
            return model.transcribe(path)

        result = execute_with_self_improvement(
            process_audio,
            "/path/to/audio.mp3",
            task_description="Transcribe audio file"
        )
        ```
    """
    ctx = ExecutionContext(
        task_description=task_description,
        auto_acquire=auto_acquire,
        max_retries=max_retries,
        notify_callback=notify_callback,
        credentials=credentials
    )

    return _execute_with_context(func, ctx, *args, **kwargs)


def _execute_with_context(
    func: Callable[..., T],
    ctx: ExecutionContext,
    *args,
    **kwargs
) -> Union[T, Dict[str, Any]]:
    """Execute function with context tracking."""
    acquirer = CapabilityAcquirer(
        auto_approve_low_risk=ctx.auto_acquire,
        notify_on_medium=True
    )

    while ctx.attempts < ctx.max_retries:
        ctx.attempts += 1

        try:
            # Attempt to execute the function
            result = func(*args, **kwargs)
            return result

        except CapabilityGapError as gap:
            # Explicit capability gap raised
            ctx.gaps_encountered.append(gap)
            acquisition_result = _handle_gap(gap, acquirer, ctx)

            if not acquisition_result.success:
                if acquisition_result.user_action_required:
                    return {
                        "success": False,
                        "user_action_required": acquisition_result.user_action_required,
                        "gap": gap.to_dict()
                    }
                return {
                    "success": False,
                    "error": acquisition_result.error,
                    "gap": gap.to_dict()
                }

            ctx.acquisitions.append(acquisition_result)
            # Continue to retry

        except ImportError as e:
            # Module not found - detect gap from error
            gap = detect_capability_gap(
                task_description=ctx.task_description,
                error_message=str(e)
            )

            if gap:
                ctx.gaps_encountered.append(gap)
                acquisition_result = _handle_gap(gap, acquirer, ctx)

                if not acquisition_result.success:
                    if acquisition_result.user_action_required:
                        return {
                            "success": False,
                            "user_action_required": acquisition_result.user_action_required,
                            "gap": gap.to_dict()
                        }
                    return {
                        "success": False,
                        "error": acquisition_result.error
                    }

                ctx.acquisitions.append(acquisition_result)
                # Continue to retry
            else:
                # Can't identify the gap
                return {
                    "success": False,
                    "error": f"Import error: {e}",
                    "traceback": traceback.format_exc()
                }

        except FileNotFoundError as e:
            # Command not found
            error_str = str(e)
            gap = detect_capability_gap(
                task_description=ctx.task_description,
                error_message=error_str
            )

            if gap:
                ctx.gaps_encountered.append(gap)
                acquisition_result = _handle_gap(gap, acquirer, ctx)

                if not acquisition_result.success:
                    return {
                        "success": False,
                        "error": acquisition_result.error
                    }

                ctx.acquisitions.append(acquisition_result)
            else:
                return {
                    "success": False,
                    "error": f"File not found: {e}"
                }

        except Exception as e:
            # General error - try to detect capability gap
            error_str = str(e)
            tb = traceback.format_exc()

            gap = detect_capability_gap(
                task_description=ctx.task_description,
                error_message=f"{error_str}\n{tb}"
            )

            if gap:
                ctx.gaps_encountered.append(gap)
                acquisition_result = _handle_gap(gap, acquirer, ctx)

                if acquisition_result.success:
                    ctx.acquisitions.append(acquisition_result)
                    continue  # Retry

            # Not a capability gap or acquisition failed
            return {
                "success": False,
                "error": str(e),
                "traceback": tb
            }

    # Max retries exceeded
    return {
        "success": False,
        "error": "Max retries exceeded",
        "gaps_encountered": [g.to_dict() for g in ctx.gaps_encountered],
        "acquisitions": [
            {"success": a.success, "method": a.method, "details": a.details}
            for a in ctx.acquisitions
        ]
    }


def _handle_gap(
    gap: CapabilityGapError,
    acquirer: CapabilityAcquirer,
    ctx: ExecutionContext
) -> AcquisitionResult:
    """Handle a detected capability gap."""
    # Assess risk
    assessment = assess_risk(gap)

    # Check if we need credentials
    if assessment.requires_credentials:
        required = acquirer.get_required_inputs(gap)
        provided = {k: v for k, v in ctx.credentials.items() if k in required}

        if len(provided) < len(required):
            missing = [k for k in required if k not in provided]
            instructions = acquirer.get_input_instructions(gap)

            return AcquisitionResult(
                success=False,
                user_action_required=f"Missing credentials: {', '.join(missing)}\n\n{instructions}"
            )

        # Have credentials, proceed
        return acquirer.acquire(gap, user_credentials=provided)

    # No credentials needed, proceed based on risk
    if assessment.level in (RiskLevel.LOW, RiskLevel.MEDIUM):
        return acquirer.acquire(gap)

    # High/Critical risk - need approval
    return AcquisitionResult(
        success=False,
        user_action_required=assessment.recommendation
    )


def self_improving(
    task_description: str = "",
    auto_acquire: bool = True,
    max_retries: int = 2
):
    """
    Decorator to make a function self-improving.

    Usage:
        ```python
        @self_improving(task_description="Process audio files")
        def transcribe_audio(path):
            import whisper
            model = whisper.load_model("base")
            return model.transcribe(path)

        # When whisper is not installed, it will be installed automatically
        result = transcribe_audio("/path/to/audio.mp3")
        ```
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Union[T, Dict[str, Any]]]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Union[T, Dict[str, Any]]:
            return execute_with_self_improvement(
                func,
                *args,
                task_description=task_description or func.__name__,
                auto_acquire=auto_acquire,
                max_retries=max_retries,
                **kwargs
            )
        return wrapper
    return decorator


def raise_capability_gap(
    gap_type: str,
    description: str,
    task: str = "",
    solutions: Optional[list] = None,
    pattern: str = ""
):
    """
    Explicitly raise a capability gap from within a function.

    Use this when you detect that a capability is missing but haven't
    encountered an error yet.

    Example:
        ```python
        def send_slack_message(channel, message):
            if not os.environ.get("SLACK_BOT_TOKEN"):
                raise_capability_gap(
                    gap_type="service_integration",
                    description="Slack API access",
                    task="Send Slack message",
                    pattern="slack_integration"
                )
            # ... proceed with sending
        ```
    """
    raise CapabilityGapError(
        gap_type=gap_type,
        gap_description=description,
        original_task=task,
        suggested_solutions=solutions or [],
        failure_pattern=pattern
    )


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test self-improving execution")
    parser.add_argument("--test", choices=["import", "cli", "gap"], help="Test type")

    args = parser.parse_args()

    if args.test == "import":
        # Test with a missing import
        def test_import():
            import nonexistent_module
            return "success"

        result = execute_with_self_improvement(
            test_import,
            task_description="Test import handling"
        )
        print(f"Result: {result}")

    elif args.test == "cli":
        # Test with a missing CLI tool
        import subprocess

        def test_cli():
            subprocess.run(["nonexistent_tool"], check=True)
            return "success"

        result = execute_with_self_improvement(
            test_cli,
            task_description="Test CLI handling"
        )
        print(f"Result: {result}")

    elif args.test == "gap":
        # Test explicit gap
        def test_gap():
            raise_capability_gap(
                gap_type="service_integration",
                description="Test service",
                task="Test task"
            )

        result = execute_with_self_improvement(
            test_gap,
            task_description="Test explicit gap"
        )
        print(f"Result: {result}")

    else:
        parser.print_help()
