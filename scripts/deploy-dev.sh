#!/bin/bash
# PCP Development Deployment Script
# Usage: ./scripts/deploy-dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo "  PCP Development Deployment"
echo "========================================"
echo ""

# Check branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $BRANCH"

if [ "$BRANCH" = "main" ]; then
    echo "WARNING: You're on main branch. Consider using develop for testing."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Run tests
echo ""
echo "Running E2E tests..."
echo "----------------------------------------"
python3 scripts/test_e2e_comprehensive.py
TEST_RESULT=$?

if [ $TEST_RESULT -ne 0 ]; then
    echo ""
    echo "ERROR: Tests failed. Fix issues before deploying."
    exit 1
fi

echo ""
echo "All tests passed!"
echo ""

# Check for dev environment file
if [ ! -f "config/environments/dev.env" ]; then
    echo "WARNING: config/environments/dev.env not found"
    echo "Copy dev.env.example and configure your dev Discord webhook"
    echo ""
fi

# Build and deploy
echo "Building and deploying dev container..."
echo "----------------------------------------"
docker compose --profile dev down 2>/dev/null || true
docker compose --profile dev build
docker compose --profile dev up -d

echo ""
echo "========================================"
echo "  Development deployment complete!"
echo "========================================"
echo ""
echo "Container: pcp-agent-dev"
echo "Logs: docker logs -f pcp-agent-dev"
echo "Test via Discord channel: #sean-pcp-dev"
echo ""
