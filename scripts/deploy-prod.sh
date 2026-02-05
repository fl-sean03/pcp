#!/bin/bash
# PCP Production Deployment Script
# Usage: ./scripts/deploy-prod.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo "  PCP Production Deployment"
echo "========================================"
echo ""

# Ensure on main branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $BRANCH"

if [ "$BRANCH" != "main" ]; then
    echo ""
    echo "ERROR: Production deployments must be from main branch"
    echo "Current branch: $BRANCH"
    echo ""
    echo "To deploy to production:"
    echo "  1. Merge your changes to main"
    echo "  2. git checkout main"
    echo "  3. Run this script again"
    exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo ""
    echo "WARNING: You have uncommitted changes"
    git status --short
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Run full test suite
echo ""
echo "Running full test suite (including live tests)..."
echo "----------------------------------------"
PCP_LIVE_TESTS=1 python3 scripts/test_e2e_comprehensive.py
TEST_RESULT=$?

if [ $TEST_RESULT -ne 0 ]; then
    echo ""
    echo "ERROR: Tests failed. Fix issues before deploying to production."
    exit 1
fi

echo ""
echo "All tests passed!"
echo ""

# Backup production database
echo "Backing up production database..."
echo "----------------------------------------"
BACKUP_FILE="vault/vault.db.backup_$(date +%Y%m%d_%H%M%S)"
if [ -f "vault/vault.db" ]; then
    cp vault/vault.db "$BACKUP_FILE"
    echo "Backup created: $BACKUP_FILE"
else
    echo "No existing database to backup"
fi

# Deploy
echo ""
echo "Deploying to production..."
echo "----------------------------------------"
docker compose --profile prod down 2>/dev/null || true
docker compose --profile prod build
docker compose --profile prod up -d

# Wait for container to start
echo ""
echo "Waiting for container to start..."
sleep 5

# Health check
echo ""
echo "Running health check..."
echo "----------------------------------------"
HEALTH=$(docker inspect --format='{{.State.Health.Status}}' pcp-agent 2>/dev/null || echo "unknown")
echo "Container health: $HEALTH"

if [ "$HEALTH" = "unhealthy" ]; then
    echo ""
    echo "ERROR: Container is unhealthy!"
    echo "Rolling back..."
    docker compose --profile prod down
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" vault/vault.db
    fi
    docker compose --profile prod up -d
    echo "Rollback complete. Please investigate."
    exit 1
fi

# Run smoke test
echo ""
echo "Running production smoke test..."
echo "----------------------------------------"
python3 scripts/test_production_smoke.py
SMOKE_RESULT=$?

if [ $SMOKE_RESULT -ne 0 ]; then
    echo ""
    echo "ERROR: Smoke test failed!"
    echo "Rolling back..."
    docker compose --profile prod down
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" vault/vault.db
    fi
    docker compose --profile prod up -d
    echo "Rollback complete. Please investigate."
    exit 1
fi

echo ""
echo "========================================"
echo "  Production deployment successful!"
echo "========================================"
echo ""
echo "Container: pcp-agent"
echo "Logs: docker logs -f pcp-agent"
echo "Backup: $BACKUP_FILE"
echo ""
echo "Monitor for the next hour for any issues."
echo ""
