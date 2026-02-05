#!/usr/bin/env python3
"""
Validation tests for the self-improvement system.

Run with: python -m self_improvement.test_self_improvement
Or: python scripts/self_improvement/test_self_improvement.py
"""

import os
import sys
import json

# Ensure we can import from parent
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(script_dir))

from self_improvement import (
    # Exceptions
    CapabilityGapError,
    CapabilityAcquisitionFailed,
    UserInputRequired,

    # Detection
    detect_capability_gap,
    log_capability_gap,
    get_gap_by_id,
    get_gap_statistics,
    ensure_capability_gaps_table,
    find_matching_patterns,

    # Risk Assessment
    assess_risk,
    can_auto_acquire,
    RiskLevel,

    # Acquisition
    acquire_capability,
    CapabilityAcquirer,

    # Execution
    execute_with_self_improvement,
    self_improving,
    raise_capability_gap,
)


def test_imports():
    """Test that all imports work."""
    print("✓ All imports successful")
    return True


def test_gap_detection():
    """Test capability gap detection."""
    print("\nTesting gap detection...")

    # Test file type detection
    gap = detect_capability_gap(file_path="/tmp/audio.mp3")
    assert gap is not None, "Should detect audio file gap"
    assert gap.gap_type == "file_processing", f"Expected file_processing, got {gap.gap_type}"
    print("  ✓ Audio file gap detection")

    # Test error message detection
    gap = detect_capability_gap(error_message="ModuleNotFoundError: No module named 'requests'")
    assert gap is not None, "Should detect missing module"
    assert "requests" in gap.gap_description.lower()
    print("  ✓ Missing module detection")

    # Test CLI tool detection
    gap = detect_capability_gap(error_message="jq: command not found")
    assert gap is not None, "Should detect missing CLI tool"
    assert gap.gap_type == "cli_tool"
    print("  ✓ CLI tool detection")

    # Test text pattern detection
    gap = detect_capability_gap(task_description="Send a message to Slack channel")
    assert gap is not None, "Should detect Slack integration need"
    assert "slack" in gap.failure_pattern.lower()
    print("  ✓ Text pattern detection")

    print("✓ Gap detection tests passed")
    return True


def test_pattern_matching():
    """Test pattern matching."""
    print("\nTesting pattern matching...")

    # Test text patterns
    patterns = find_matching_patterns(text="send slack message")
    assert "slack_integration" in patterns
    print("  ✓ Slack pattern match")

    patterns = find_matching_patterns(text="upload to aws s3")
    assert "aws_access" in patterns
    print("  ✓ AWS pattern match")

    # Test file extension
    patterns = find_matching_patterns(extension=".mp3")
    assert "audio_transcription" in patterns
    print("  ✓ Audio extension match")

    patterns = find_matching_patterns(extension=".mp4")
    assert "video_processing" in patterns
    print("  ✓ Video extension match")

    # Test MIME type
    patterns = find_matching_patterns(mime_type="audio/mpeg")
    assert "audio_transcription" in patterns
    print("  ✓ MIME type match")

    print("✓ Pattern matching tests passed")
    return True


def test_risk_assessment():
    """Test risk assessment."""
    print("\nTesting risk assessment...")

    # Low risk - file processing
    gap = CapabilityGapError(
        gap_type="file_processing",
        gap_description="Audio transcription",
        failure_pattern="audio_transcription"
    )
    assessment = assess_risk(gap)
    assert assessment.level == RiskLevel.LOW, f"Expected LOW, got {assessment.level}"
    assert not assessment.requires_approval
    print(f"  ✓ Audio transcription: {assessment.level.value} (score: {assessment.score:.2f})")

    # Medium risk - service integration
    gap = CapabilityGapError(
        gap_type="service_integration",
        gap_description="Slack integration",
        failure_pattern="slack_integration"
    )
    assessment = assess_risk(gap)
    assert assessment.requires_credentials
    print(f"  ✓ Slack integration: {assessment.level.value} (requires credentials: {assessment.requires_credentials})")

    # High risk - cloud provider
    gap = CapabilityGapError(
        gap_type="cloud_provider",
        gap_description="AWS access",
        failure_pattern="aws_access"
    )
    assessment = assess_risk(gap)
    assert assessment.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert assessment.requires_approval
    print(f"  ✓ AWS access: {assessment.level.value} (requires approval: {assessment.requires_approval})")

    print("✓ Risk assessment tests passed")
    return True


def test_database():
    """Test database operations."""
    print("\nTesting database operations...")

    # Initialize table
    ensure_capability_gaps_table()
    print("  ✓ Table initialization")

    # Log a gap
    gap = CapabilityGapError(
        gap_type="cli_tool",
        gap_description="Test gap",
        failure_pattern="test_pattern"
    )
    gap_id = log_capability_gap(gap)
    assert gap_id > 0
    print(f"  ✓ Gap logged with ID: {gap_id}")

    # Retrieve gap
    stored = get_gap_by_id(gap_id)
    assert stored is not None
    assert stored["gap_type"] == "cli_tool"
    print("  ✓ Gap retrieved")

    # Get statistics
    stats = get_gap_statistics()
    assert stats["total"] >= 1
    print(f"  ✓ Statistics: {stats['total']} total gaps")

    print("✓ Database tests passed")
    return True


def test_execution_wrapper():
    """Test self-improving execution wrapper."""
    print("\nTesting execution wrapper...")

    # Test successful function
    def success_func():
        return "success"

    result = execute_with_self_improvement(success_func)
    assert result == "success"
    print("  ✓ Successful function execution")

    # Test function with missing import
    def missing_import_func():
        import totally_fake_module_xyz123
        return "never reached"

    result = execute_with_self_improvement(missing_import_func)
    assert isinstance(result, dict)
    assert result.get("success") == False
    print("  ✓ Graceful handling of missing import")

    # Test decorator
    @self_improving()
    def decorated_func():
        return "decorated success"

    result = decorated_func()
    assert result == "decorated success"
    print("  ✓ Decorator works")

    print("✓ Execution wrapper tests passed")
    return True


def test_can_auto_acquire():
    """Test auto-acquire decision logic."""
    print("\nTesting auto-acquire logic...")

    # Pure Python package - should auto-acquire (low risk)
    gap = CapabilityGapError(
        gap_type="cli_tool",
        gap_description="Missing Python package",
        suggested_solutions=[{
            "type": "python_package",
            "name": "requests",
            "install_command": "pip install requests"
        }],
        failure_pattern="missing_python_module"
    )
    can_auto, reason = can_auto_acquire(gap)
    print(f"  Python package: can_auto={can_auto}")
    assert can_auto, f"Python package should auto-acquire: {reason}"

    # System package with sudo - should NOT auto-acquire
    gap = CapabilityGapError(
        gap_type="file_processing",
        gap_description="Video processing",
        failure_pattern="video_processing"
    )
    can_auto, reason = can_auto_acquire(gap)
    print(f"  Video processing (sudo): can_auto={can_auto}")
    # This requires sudo, so it should NOT auto-acquire
    assert not can_auto, "System packages with sudo should require approval"

    # High risk with credentials - should not auto-acquire
    gap = CapabilityGapError(
        gap_type="cloud_provider",
        gap_description="AWS access",
        failure_pattern="aws_access"
    )
    can_auto, reason = can_auto_acquire(gap)
    print(f"  AWS access: can_auto={can_auto}")
    assert not can_auto

    print("✓ Auto-acquire logic tests passed")
    return True


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("PCP Self-Improvement System - Validation Tests")
    print("=" * 60)

    tests = [
        test_imports,
        test_gap_detection,
        test_pattern_matching,
        test_risk_assessment,
        test_database,
        test_execution_wrapper,
        test_can_auto_acquire,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
