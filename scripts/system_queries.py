#!/usr/bin/env python3
"""
System Queries Module - Query other containers and systems.

Enables PCP to act as a "control plane" by querying other agents and services
in the AgentOps platform via docker exec.
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any, List

# Known container configurations
KNOWN_CONTAINERS = {
    "alpha-trader": {
        "container_name": "alpha-trader-agent",
        "description": "Trading and market analysis agent",
        "status_script": "/workspace/scripts/status.py",
        "common_commands": ["status", "portfolio", "positions"]
    },
    "matterstack": {
        "container_name": "matterstack-agent",
        "description": "MatterStack development agent",
        "status_script": "/workspace/scripts/status.py",
        "common_commands": ["status", "health"]
    },
    "agent-gateway": {
        "container_name": "agent-gateway",
        "description": "Central agent coordination gateway",
        "status_script": None,
        "common_commands": ["health", "agents"]
    },
    "agent-discord": {
        "container_name": "agent-discord",
        "description": "Discord bot and message relay",
        "status_script": None,
        "common_commands": ["status"]
    }
}


def list_running_containers() -> List[Dict[str, Any]]:
    """
    List all running Docker containers.

    Returns:
        List of container info dicts
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"],
            capture_output=True, text=True, timeout=10
        )

        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    name = parts[0]
                    # Check if this is a known container
                    known_info = None
                    for key, info in KNOWN_CONTAINERS.items():
                        if info["container_name"] == name:
                            known_info = info
                            break

                    containers.append({
                        "name": name,
                        "status": parts[1],
                        "image": parts[2],
                        "known": known_info is not None,
                        "description": known_info["description"] if known_info else None
                    })

        return containers
    except subprocess.TimeoutExpired:
        return [{"error": "Timeout listing containers"}]
    except Exception as e:
        return [{"error": str(e)}]


def query_container(
    container: str,
    command: str,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Execute a command in a Docker container.

    Args:
        container: Container name or alias (e.g., "alpha-trader" or "alpha-trader-agent")
        command: Command to execute
        timeout: Command timeout in seconds

    Returns:
        Dict with stdout, stderr, return_code, and parsed JSON if applicable
    """
    # Resolve container alias to actual name
    container_name = container
    if container in KNOWN_CONTAINERS:
        container_name = KNOWN_CONTAINERS[container]["container_name"]

    try:
        # Split command into parts
        cmd_parts = command.split() if isinstance(command, str) else command

        result = subprocess.run(
            ["docker", "exec", container_name] + cmd_parts,
            capture_output=True, text=True, timeout=timeout
        )

        response = {
            "container": container_name,
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "success": result.returncode == 0,
            "queried_at": datetime.now().isoformat()
        }

        # Try to parse stdout as JSON
        if result.stdout:
            try:
                response["data"] = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass

        return response
    except subprocess.TimeoutExpired:
        return {
            "container": container_name,
            "command": command,
            "error": f"Command timed out after {timeout}s",
            "success": False
        }
    except Exception as e:
        return {
            "container": container_name,
            "command": command,
            "error": str(e),
            "success": False
        }


def query_alpha_trader(command: str = "status") -> Dict[str, Any]:
    """
    Query the alpha-trader agent.

    Common commands:
    - status: Get overall status
    - portfolio: Get portfolio summary
    - positions: Get current positions

    Args:
        command: Command to run (default: status)

    Returns:
        Query result dict
    """
    container_info = KNOWN_CONTAINERS.get("alpha-trader")
    if not container_info:
        return {"error": "alpha-trader not configured"}

    # If status and status_script exists, use it
    if command == "status" and container_info.get("status_script"):
        return query_container(
            "alpha-trader",
            f"python3 {container_info['status_script']}"
        )

    return query_container("alpha-trader", command)


def query_matterstack(command: str = "status") -> Dict[str, Any]:
    """
    Query the MatterStack development agent.

    Args:
        command: Command to run (default: status)

    Returns:
        Query result dict
    """
    container_info = KNOWN_CONTAINERS.get("matterstack")
    if not container_info:
        return {"error": "matterstack not configured"}

    if command == "status" and container_info.get("status_script"):
        return query_container(
            "matterstack",
            f"python3 {container_info['status_script']}"
        )

    return query_container("matterstack", command)


def get_container_logs(
    container: str,
    lines: int = 50,
    since: str = None
) -> Dict[str, Any]:
    """
    Get logs from a container.

    Args:
        container: Container name or alias
        lines: Number of lines to retrieve
        since: Time filter (e.g., "1h", "30m")

    Returns:
        Dict with log content
    """
    # Resolve container alias
    container_name = container
    if container in KNOWN_CONTAINERS:
        container_name = KNOWN_CONTAINERS[container]["container_name"]

    cmd = ["docker", "logs", "--tail", str(lines)]
    if since:
        cmd.extend(["--since", since])
    cmd.append(container_name)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )

        return {
            "container": container_name,
            "lines": lines,
            "since": since,
            "logs": result.stdout + result.stderr,
            "success": result.returncode == 0
        }
    except Exception as e:
        return {
            "container": container_name,
            "error": str(e),
            "success": False
        }


def get_system_overview() -> Dict[str, Any]:
    """
    Get an overview of all known systems and their status.

    Returns:
        Dict with status of all known containers
    """
    running = list_running_containers()
    running_names = {c["name"] for c in running if "name" in c}

    overview = {
        "queried_at": datetime.now().isoformat(),
        "containers": []
    }

    for alias, info in KNOWN_CONTAINERS.items():
        container_name = info["container_name"]
        is_running = container_name in running_names

        container_status = {
            "alias": alias,
            "name": container_name,
            "description": info["description"],
            "running": is_running
        }

        # If running, try to get status
        if is_running and info.get("status_script"):
            try:
                status_result = query_container(
                    alias,
                    f"python3 {info['status_script']}",
                    timeout=10
                )
                if status_result.get("success") and status_result.get("data"):
                    container_status["status_data"] = status_result["data"]
            except Exception:
                pass

        overview["containers"].append(container_status)

    # Add any unknown running containers
    for container in running:
        if container.get("name") and not container.get("known"):
            overview["containers"].append({
                "alias": None,
                "name": container["name"],
                "description": "Unknown container",
                "running": True,
                "image": container.get("image")
            })

    return overview


def check_container_health(container: str) -> Dict[str, Any]:
    """
    Check the health of a container.

    Args:
        container: Container name or alias

    Returns:
        Health status dict
    """
    # Resolve container alias
    container_name = container
    if container in KNOWN_CONTAINERS:
        container_name = KNOWN_CONTAINERS[container]["container_name"]

    try:
        # Get container inspect info
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}} {{.State.Health.Status}}", container_name],
            capture_output=True, text=True, timeout=10
        )

        if result.returncode != 0:
            return {
                "container": container_name,
                "running": False,
                "healthy": False,
                "error": "Container not found"
            }

        parts = result.stdout.strip().split()
        status = parts[0] if parts else "unknown"
        health = parts[1] if len(parts) > 1 else "no health check"

        return {
            "container": container_name,
            "running": status == "running",
            "status": status,
            "health": health,
            "healthy": health in ("healthy", "no health check") and status == "running"
        }
    except Exception as e:
        return {
            "container": container_name,
            "error": str(e),
            "healthy": False
        }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python system_queries.py list                    - List running containers")
        print("  python system_queries.py overview                - System overview")
        print("  python system_queries.py query <container> <cmd> - Query a container")
        print("  python system_queries.py logs <container> [N]    - Get container logs")
        print("  python system_queries.py health <container>      - Check container health")
        print("  python system_queries.py alpha-trader [cmd]      - Query alpha-trader")
        print("  python system_queries.py matterstack [cmd]       - Query MatterStack")
        print()
        print("Known containers:")
        for alias, info in KNOWN_CONTAINERS.items():
            print(f"  {alias}: {info['description']}")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        containers = list_running_containers()
        print("Running containers:")
        for c in containers:
            if "error" in c:
                print(f"  Error: {c['error']}")
            else:
                known = " (known)" if c.get("known") else ""
                print(f"  {c['name']}: {c['status']}{known}")

    elif command == "overview":
        overview = get_system_overview()
        print(json.dumps(overview, indent=2))

    elif command == "query":
        if len(sys.argv) < 4:
            print("Usage: python system_queries.py query <container> <command>")
            sys.exit(1)
        container = sys.argv[2]
        cmd = " ".join(sys.argv[3:])
        result = query_container(container, cmd)
        print(json.dumps(result, indent=2))

    elif command == "logs":
        if len(sys.argv) < 3:
            print("Usage: python system_queries.py logs <container> [lines]")
            sys.exit(1)
        container = sys.argv[2]
        lines = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        result = get_container_logs(container, lines=lines)
        if result.get("success"):
            print(result.get("logs", ""))
        else:
            print(f"Error: {result.get('error')}")

    elif command == "health":
        if len(sys.argv) < 3:
            print("Usage: python system_queries.py health <container>")
            sys.exit(1)
        container = sys.argv[2]
        result = check_container_health(container)
        print(json.dumps(result, indent=2))

    elif command == "alpha-trader":
        cmd = sys.argv[2] if len(sys.argv) > 2 else "status"
        result = query_alpha_trader(cmd)
        print(json.dumps(result, indent=2))

    elif command == "matterstack":
        cmd = sys.argv[2] if len(sys.argv) > 2 else "status"
        result = query_matterstack(cmd)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
