#!/usr/bin/env python3
"""
Phase validation runner for PCP Agentic Remediation.
Usage: python tests/validate_phase.py <phase_number>
"""
import sys
import subprocess
import os

# Change to scripts directory for imports
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'scripts')
PCP_ROOT = os.path.join(os.path.dirname(__file__), '..')

PHASES = {
    1: {
        "name": "Remove Subprocess Claude Calls",
        "checks": [
            ("No subprocess claude imports in vault_v2",
             f"grep -c 'subprocess.*claude\\|claude.*-p' {SCRIPTS_DIR}/vault_v2.py || true",
             "0"),
            ("No subprocess claude in brief.py",
             f"grep -c 'subprocess.*claude\\|claude.*-p' {SCRIPTS_DIR}/brief.py || true",
             "0"),
            ("vault_v2 imports cleanly",
             f"cd {SCRIPTS_DIR} && python3 -c 'import vault_v2' 2>&1 || echo 'IMPORT_FAILED'",
             "NO_ERROR"),
            ("store_capture function exists",
             f"cd {SCRIPTS_DIR} && python3 -c 'from vault_v2 import store_capture; print(\"OK\")' 2>&1",
             "OK"),
        ]
    },
    2: {
        "name": "Convert Intelligence to Data Functions",
        "checks": [
            ("get_brief_data exists and returns dict",
             f"cd {SCRIPTS_DIR} && python3 -c 'from brief import get_brief_data; d=get_brief_data(); print(type(d).__name__)' 2>&1",
             "dict"),
            ("get_proactive_data exists and returns dict",
             f"cd {SCRIPTS_DIR} && python3 -c 'from proactive import get_proactive_data; d=get_proactive_data(); print(type(d).__name__)' 2>&1",
             "dict"),
            ("get_pattern_data exists and returns dict",
             f"cd {SCRIPTS_DIR} && python3 -c 'from patterns import get_pattern_data; d=get_pattern_data(); print(type(d).__name__)' 2>&1",
             "dict"),
            ("generate_ai_insights returns empty (deprecated)",
             f"cd {SCRIPTS_DIR} && python3 -c 'from brief import generate_ai_insights; r=generate_ai_insights({{}}); print(\"EMPTY\" if r==\"\" else \"NOT_EMPTY\")' 2>&1",
             "EMPTY"),
        ]
    },
    3: {
        "name": "Refactor vault_v2.py",
        "checks": [
            ("vault_v2.py under 3500 lines (target: 2000 after CLI extraction)",
             f"wc -l < {SCRIPTS_DIR}/vault_v2.py",
             "UNDER_3500"),
            ("All imports work",
             f"cd {SCRIPTS_DIR} && python3 -c 'from vault_v2 import *; print(\"OK\")' 2>&1",
             "OK"),
            ("New data functions exist",
             f"cd {SCRIPTS_DIR} && python3 -c 'from vault_v2 import store_capture, store_task; print(\"OK\")' 2>&1",
             "OK"),
            ("Deprecated functions return defaults (no subprocess)",
             f"cd {SCRIPTS_DIR} && python3 -c 'from vault_v2 import extract_entities; e=extract_entities(\"test\"); print(\"OK\" if e[\"intent\"]==\"note\" else \"FAIL\")' 2>&1",
             "OK"),
        ]
    },
    4: {
        "name": "Consolidate Skills",
        "checks": [
            ("pcp-operations deleted",
             f"test -d {PCP_ROOT}/.claude/skills/pcp-operations && echo 'EXISTS' || echo 'DELETED'",
             "DELETED"),
            ("10 or fewer skills",
             f"ls -d {PCP_ROOT}/.claude/skills/*/ 2>/dev/null | wc -l",
             "UNDER_11"),
        ]
    },
    5: {
        "name": "Extract Shared Utilities",
        "checks": [
            ("common/ directory exists",
             f"test -d {SCRIPTS_DIR}/common && echo 'EXISTS' || echo 'MISSING'",
             "EXISTS"),
            ("db.py in common",
             f"test -f {SCRIPTS_DIR}/common/db.py && echo 'EXISTS' || echo 'MISSING'",
             "EXISTS"),
            ("environment.py in common",
             f"test -f {SCRIPTS_DIR}/common/environment.py && echo 'EXISTS' || echo 'MISSING'",
             "EXISTS"),
            ("config.py in common",
             f"test -f {SCRIPTS_DIR}/common/config.py && echo 'EXISTS' || echo 'MISSING'",
             "EXISTS"),
            ("common module importable",
             f"cd {SCRIPTS_DIR} && python3 -c 'from common import get_db_connection, load_config, is_in_container; print(\"OK\")' 2>&1",
             "OK"),
        ]
    },
    6: {
        "name": "Externalize Configuration",
        "checks": [
            ("config/pcp.yaml exists",
             f"test -f {PCP_ROOT}/config/pcp.yaml && echo 'EXISTS' || echo 'MISSING'",
             "EXISTS"),
            ("config loads and has sections",
             f"cd {SCRIPTS_DIR} && python3 -c 'from common import load_config; c=load_config(); print(\"OK\" if len(c)>=5 else \"FAIL\")' 2>&1",
             "OK"),
            ("config has key sections",
             f"cd {SCRIPTS_DIR} && python3 -c 'from common import load_config; c=load_config(); print(\"OK\" if all(k in c for k in [\"worker\",\"thresholds\",\"scheduler\"]) else \"MISSING\")' 2>&1",
             "OK"),
        ]
    },
    7: {
        "name": "Create Prompt Registry",
        "checks": [
            ("prompts/ directory exists",
             f"test -d {PCP_ROOT}/prompts && echo 'EXISTS' || echo 'MISSING'",
             "EXISTS"),
            ("has prompt files",
             f"ls {PCP_ROOT}/prompts/*.md 2>/dev/null | wc -l",
             "AT_LEAST_3"),
        ]
    },
}


def run_check(name, cmd, expected):
    """Run a validation check."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = result.stdout.strip()

    # Handle special expected values
    if expected == "NO_ERROR":
        passed = "IMPORT_FAILED" not in output and result.returncode == 0
    elif expected == "UNDER_2500":
        try:
            lines = int(output)
            passed = lines < 2500
            output = f"{lines} lines"
        except:
            passed = False
    elif expected == "UNDER_3500":
        try:
            lines = int(output)
            passed = lines < 3500
            output = f"{lines} lines"
        except:
            passed = False
    elif expected == "UNDER_11":
        try:
            count = int(output)
            passed = count <= 10
            output = f"{count} skills"
        except:
            passed = False
    elif expected == "AT_LEAST_3":
        try:
            count = int(output)
            passed = count >= 3
            output = f"{count} files"
        except:
            passed = False
    else:
        passed = expected in output

    status = "✓" if passed else "✗"
    print(f"  {status} {name}")
    if not passed:
        print(f"    Expected: {expected}")
        print(f"    Got: {output[:200]}")
        if result.stderr:
            print(f"    Stderr: {result.stderr[:200]}")

    return passed


def validate_phase(phase_num):
    """Validate a specific phase."""
    if phase_num not in PHASES:
        print(f"Unknown phase: {phase_num}")
        print(f"Available phases: {list(PHASES.keys())}")
        return False

    phase = PHASES[phase_num]
    print(f"\n{'='*60}")
    print(f"Phase {phase_num}: {phase['name']}")
    print('='*60 + "\n")

    all_passed = True
    for name, cmd, expected in phase["checks"]:
        if not run_check(name, cmd, expected):
            all_passed = False

    print()
    if all_passed:
        print("✓ All checks passed!")
    else:
        print("✗ Some checks failed.")

    return all_passed


def validate_all():
    """Validate all phases."""
    results = {}
    for phase_num in sorted(PHASES.keys()):
        results[phase_num] = validate_phase(phase_num)

    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    for phase_num, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"  {status} Phase {phase_num}: {PHASES[phase_num]['name']}")

    return all(results.values())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_phase.py <phase_number|all>")
        print("Phases: 1-7 or 'all'")
        sys.exit(1)

    arg = sys.argv[1]
    if arg == "all":
        success = validate_all()
    else:
        try:
            phase = int(arg)
            success = validate_phase(phase)
        except ValueError:
            print(f"Invalid phase: {arg}")
            sys.exit(1)

    sys.exit(0 if success else 1)
