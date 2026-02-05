#!/usr/bin/env python3
"""
PCP System Smoke Test

Validates the full PCP system is operational from the host.
Run after deploy or as a health check.

Usage:
    python tests/smoke_test.py           # Run all checks
    python tests/smoke_test.py --quick   # Skip slow checks
"""

import subprocess
import sys
import json
import os
from datetime import datetime

PASS = 0
FAIL = 0
SKIP = 0
ERRORS = []


def check(name, condition, error_msg=""):
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {name}")
        PASS += 1
    else:
        print(f"  [FAIL] {name}: {error_msg}")
        FAIL += 1
        ERRORS.append(f"{name}: {error_msg}")


def skip(name, reason):
    global SKIP
    print(f"  [SKIP] {name}: {reason}")
    SKIP += 1


def run(cmd, timeout=30):
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def docker_exec(container, cmd, timeout=30):
    """Execute a command inside a Docker container."""
    return run(f"docker exec {container} {cmd}", timeout=timeout)


def main():
    quick = "--quick" in sys.argv
    print("=" * 60)
    print(f"  PCP System Smoke Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # === Section 1: Container Health ===
    print("\n--- Container Health ---")

    rc, out, _ = run("docker ps --format '{{.Names}}|{{.Status}}' 2>/dev/null")
    containers = dict(
        line.split("|", 1) for line in out.splitlines() if "|" in line
    )

    check(
        "pcp-agent container running",
        "pcp-agent" in containers,
        "Container not found in docker ps",
    )

    if "pcp-agent" in containers:
        check(
            "pcp-agent is healthy",
            "healthy" in containers.get("pcp-agent", ""),
            f"Status: {containers.get('pcp-agent', 'unknown')}",
        )
    else:
        skip("pcp-agent health", "container not running")

    # Dev container is optional
    if "pcp-agent-dev" in containers:
        check(
            "pcp-agent-dev container running",
            True,
        )
    else:
        skip("pcp-agent-dev", "not running (optional)")

    # === Section 2: Vault Database ===
    print("\n--- Vault Database ---")

    rc, out, err = docker_exec(
        "pcp-agent",
        "python3 -c \"import sqlite3; c=sqlite3.connect('/workspace/vault/vault.db'); print(c.execute('SELECT count(*) FROM captures_v2').fetchone()[0])\"",
    )
    if rc == 0:
        check("Vault DB accessible", True)
        check(f"Captures table has data ({out} rows)", int(out) > 0 if out.isdigit() else False, "Empty captures table")
    else:
        check("Vault DB accessible", False, err)

    rc, out, _ = docker_exec(
        "pcp-agent",
        "python3 -c \"import sqlite3; c=sqlite3.connect('/workspace/vault/vault.db'); tables=[r[0] for r in c.execute(\\\"SELECT name FROM sqlite_master WHERE type='table'\\\").fetchall()]; print(','.join(tables))\"",
    )
    if rc == 0:
        tables = out.split(",")
        for required in ["captures_v2", "people", "projects", "tasks", "knowledge"]:
            check(f"Table '{required}' exists", required in tables, f"Missing table. Found: {out}")
    else:
        check("Schema validation", False, err)

    # === Section 3: Python Imports ===
    print("\n--- Python Imports ---")

    modules = ["vault_v2", "knowledge", "brief", "task_delegation", "email_processor"]
    for mod in modules:
        rc, _, err = docker_exec(
            "pcp-agent",
            f"python3 -c \"import sys; sys.path.insert(0, '/workspace/scripts'); import {mod}\"",
        )
        check(f"Import {mod}", rc == 0, err[:100] if err else "")

    # === Section 4: Credentials ===
    print("\n--- Credentials ---")

    rc, out, _ = docker_exec(
        "pcp-agent",
        "python3 -c \"import json; d=json.load(open('/home/pcp/.claude/.credentials.json')); print(d['claudeAiOauth']['expiresAt'])\"",
    )
    if rc == 0 and out.isdigit():
        expires_ms = int(out)
        now_ms = int(datetime.now().timestamp() * 1000)
        remaining_hours = (expires_ms - now_ms) / 3600000
        check(
            f"Claude credentials valid ({remaining_hours:.1f}h remaining)",
            remaining_hours > 0,
            "Credentials expired!",
        )
    else:
        check("Claude credentials readable", False, "Could not read credentials")

    # === Section 5: File System ===
    print("\n--- File System ---")

    paths = {
        "/workspace/scripts/vault_v2.py": "Core vault script",
        "/workspace/config/pcp.yaml": "Configuration",
        "/workspace/vault/vault.db": "Vault database",
        "/workspace/prompts/worker_agent.md": "Worker prompt",
    }
    for path, desc in paths.items():
        rc, _, _ = docker_exec("pcp-agent", f"test -f {path}")
        check(f"{desc} exists ({path})", rc == 0, "File not found")

    # === Section 6: Supervisor ===
    print("\n--- Background Supervisor ---")

    rc, out, _ = run("systemctl is-active pcp-supervisor 2>/dev/null")
    check("pcp-supervisor service active", out.strip() == "active", f"Status: {out.strip()}")

    # === Section 7: Cron Jobs ===
    print("\n--- Cron Jobs ---")

    rc, out, _ = run("crontab -l 2>/dev/null")
    check("Crontab has PCP entries", "pcp" in out.lower(), "No PCP cron entries found")
    check(
        "Cron paths use pcp/prod/",
        "pcp/prod/" in out,
        "Old paths detected (should use pcp/prod/)",
    )

    # === Section 8: Network ===
    print("\n--- Network ---")

    rc, out, _ = run(
        "docker network inspect agentops-proxy --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null"
    )
    if rc == 0:
        check("pcp-agent on agentops-proxy network", "pcp-agent" in out, f"Connected: {out}")
    else:
        check("agentops-proxy network exists", False, "Network not found")

    # === Section 9: Functional Tests (unless --quick) ===
    if not quick:
        print("\n--- Functional Tests ---")

        # Test vault search
        rc, out, _ = docker_exec(
            "pcp-agent",
            "python3 -c \"import sys; sys.path.insert(0, '/workspace/scripts'); from vault_v2 import smart_search; r=smart_search('test'); print(type(r).__name__)\"",
        )
        check("Vault search executes", rc == 0 and "error" not in (out + "").lower(), out[:100] if out else "")

        # Test knowledge query
        rc, out, _ = docker_exec(
            "pcp-agent",
            "python3 -c \"import sys; sys.path.insert(0, '/workspace/scripts'); from knowledge import query_knowledge; r=query_knowledge('test'); print('ok')\"",
        )
        check("Knowledge query executes", rc == 0, out[:100] if out else "")
    else:
        skip("Functional tests", "--quick mode")

    # === Summary ===
    total = PASS + FAIL + SKIP
    print("\n" + "=" * 60)
    print(f"  Results: {PASS} passed, {FAIL} failed, {SKIP} skipped ({total} total)")
    if ERRORS:
        print(f"\n  Failures:")
        for e in ERRORS:
            print(f"    - {e}")
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
