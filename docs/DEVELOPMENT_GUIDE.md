# PCP Development Guide

**Version:** 2.0
**Date:** 2026-01-27
**Status:** Active

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture: Fully Separated Environments](#architecture-fully-separated-environments)
3. [Initial Setup](#initial-setup)
4. [Development Workflow](#development-workflow)
5. [Testing Strategy](#testing-strategy)
6. [Promoting Changes to Production](#promoting-changes-to-production)
7. [Configuration Reference](#configuration-reference)
8. [Troubleshooting](#troubleshooting)

---

## Overview

PCP uses **two completely separate installations** to isolate development from production:

```
/path/to/workspace/
├── pcp/           # PRODUCTION - Your live personal PCP
│   ├── vault/vault.db    # Your real data
│   └── (stable code)
│
└── pcp-dev/       # DEVELOPMENT - Experimentation zone
    ├── vault/vault_dev.db    # Test data only
    └── (bleeding edge code)
```

### Why Full Separation?

| Concern | Single Directory Approach | Full Separation |
|---------|--------------------------|-----------------|
| Accidental prod changes | Possible (wrong branch) | Impossible (different folder) |
| Run both simultaneously | Complex | Easy |
| Test destructive changes | Risky | Safe |
| Database isolation | Config-dependent | Guaranteed |
| Mental model | "Which branch am I on?" | "Which folder am I in?" |

---

## Architecture: Fully Separated Environments

```
┌──────────────────────────────────────────────────────────────────┐
│                         PRODUCTION                                │
│                      /path/to/pcp/                   │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │   Code      │  │   Database   │  │   Discord Channel       │  │
│  │  (stable)   │  │  vault.db    │  │   #sean-pcp             │  │
│  └─────────────┘  └──────────────┘  └─────────────────────────┘  │
│         │                │                      │                 │
│         └────────────────┼──────────────────────┘                 │
│                          │                                        │
│                 ┌────────▼────────┐                               │
│                 │   pcp-agent     │  Container                    │
│                 │   Port: 8080    │                               │
│                 └─────────────────┘                               │
└──────────────────────────────────────────────────────────────────┘

                    Changes flow UP after testing
                              ▲
                              │
                    [Merge when stable]
                              │

┌──────────────────────────────────────────────────────────────────┐
│                        DEVELOPMENT                                │
│                    /path/to/pcp/dev/                 │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │   Code      │  │   Database   │  │   Discord Channel       │  │
│  │  (latest)   │  │vault_dev.db  │  │   #sean-pcp-dev         │  │
│  └─────────────┘  └──────────────┘  └─────────────────────────┘  │
│         │                │                      │                 │
│         └────────────────┼──────────────────────┘                 │
│                          │                                        │
│                 ┌────────▼────────┐                               │
│                 │ pcp-agent-dev   │  Container                    │
│                 │   Port: 8081    │                               │
│                 └─────────────────┘                               │
└──────────────────────────────────────────────────────────────────┘
```

### What's Isolated

| Component | Production (`pcp/`) | Development (`pcp-dev/`) |
|-----------|---------------------|--------------------------|
| Directory | `/path/to/pcp/` | `/path/to/pcp/dev/` |
| Database | `vault/vault.db` | `vault/vault_dev.db` |
| Container | `pcp-agent` | `pcp-agent-dev` |
| Port | 8080 | 8081 |
| Discord | `#sean-pcp` | `#sean-pcp-dev` |
| Git Remote | `origin` | `origin` + `prod` |

---

## Initial Setup

### Step 1: Stabilize Current Production

First, commit the current working state as your production baseline:

```bash
cd /path/to/pcp

# Create a clean .gitignore
cat >> .gitignore << 'EOF'
# Runtime files
.claude/debug/
.claude/projects/
.claude/todos/
.claude/statsig/
.claude/stats-cache.json
.claude/shell-snapshots/
*.pyc
__pycache__/
logs/*.log

# Environment files with secrets
config/environments/*.env
!config/environments/*.env.example

# Test databases
vault/vault_dev.db*
/tmp/pcp_*

# Backups
vault/*.backup*
EOF

# Commit current stable state
git add -A
git commit -m "chore: Stabilize production baseline for v4.0"

# Tag this as the production baseline
git tag -a v4.0-prod-baseline -m "Production baseline before dev/prod split"
git push origin master --tags
```

### Step 2: Create Development Clone

```bash
cd /path/to/workspace

# Clone to new directory
git clone pcp pcp-dev

# Enter dev directory
cd pcp-dev

# Add production as a remote (for easy syncing)
git remote add prod ../pcp

# Create develop branch
git checkout -b develop

# Verify remotes
git remote -v
# origin  ../pcp (fetch)
# origin  ../pcp (push)
# prod    ../pcp (fetch)
# prod    ../pcp (push)
```

### Step 3: Create Dev Discord Channel

1. In Discord, create channel `#sean-pcp-dev`
2. Create a webhook for this channel:
   - Channel Settings → Integrations → Webhooks → New Webhook
   - Name it "PCP Dev"
   - Copy the webhook URL

### Step 4: Configure Development Environment

```bash
cd /path/to/pcp/dev

# Create dev environment config
mkdir -p config/environments

cat > config/environments/dev.env << 'EOF'
# PCP Development Environment
PCP_ENV=development
VAULT_DB_PATH=/workspace/vault/vault_dev.db
DISCORD_WEBHOOK_URL=YOUR_DEV_WEBHOOK_URL_HERE
DISCORD_CHANNEL_ID=YOUR_DEV_CHANNEL_ID
LOG_LEVEL=DEBUG
TEST_MODE=true
EOF

# Edit to add your webhook URL
nano config/environments/dev.env
```

### Step 5: Update Dev Docker Compose

Create/update `docker-compose.yaml` in pcp-dev:

```yaml
# pcp-dev/docker-compose.yaml
services:
  pcp-agent-dev:
    build: .
    container_name: pcp-agent-dev
    restart: unless-stopped
    env_file:
      - config/environments/dev.env
    volumes:
      - .:/workspace:rw
      - ./.claude:/home/pcp/.claude:rw
      - /var/lock:/var/lock:rw
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /tmp/discord_attachments_dev:/tmp/discord_attachments:rw
    environment:
      - HOME=/home/pcp
      - PCP_ENV=development
    networks:
      - agentops-proxy
    ports:
      - "8081:8080"
    healthcheck:
      test: ["CMD", "python3", "-c", "import sqlite3; sqlite3.connect('/workspace/vault/vault_dev.db').execute('SELECT 1')"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  agentops-proxy:
    external: true
```

### Step 6: Initialize Dev Database

```bash
cd /path/to/pcp/dev

# Create dev database with schema
python3 scripts/schema_v2.py

# The schema will create vault_dev.db based on PCP_ENV=development

# Or manually specify
sqlite3 vault/vault_dev.db < scripts/schema_v2.sql
```

### Step 7: Start Development Environment

```bash
cd /path/to/pcp/dev

# Build and start
docker compose up -d --build

# Verify running
docker ps | grep pcp-agent-dev

# Check logs
docker logs -f pcp-agent-dev
```

---

## Development Workflow

### Daily Development

```bash
# Always work in pcp-dev
cd /path/to/pcp/dev

# Ensure container is running
docker compose up -d

# Make changes to code
# ... edit files ...

# Run tests
python3 scripts/test_e2e_comprehensive.py

# Test via Discord (send message to #sean-pcp-dev)

# Commit changes
git add -A
git commit -m "feat: Add new feature X"
```

### Running Full Integration Tests

```bash
cd /path/to/pcp/dev

# Run all 88+ tests
python3 scripts/test_e2e_comprehensive.py

# Run with live Discord tests
PCP_LIVE_TESTS=1 python3 scripts/test_e2e_comprehensive.py

# Run specific category
python3 scripts/test_e2e_comprehensive.py --category "Stress Tests"

# Verbose output for debugging
python3 scripts/test_e2e_comprehensive.py --test ST-002 --verbose
```

### Testing Real Message Flow

You can safely test the full Discord → Queue → Worker → Response flow:

1. Send a message in `#sean-pcp-dev`
2. Watch the queue:
   ```bash
   sqlite3 vault/vault_dev.db "SELECT * FROM discord_message_queue ORDER BY created_at DESC LIMIT 5;"
   ```
3. Check container logs:
   ```bash
   docker logs -f pcp-agent-dev
   ```
4. Verify response appears in `#sean-pcp-dev`

This uses your dev database and dev Discord channel - production is untouched.

---

## Testing Strategy

### Test Pyramid

```
                    ┌───────────────┐
                    │  Production   │  After deploy
                    │  Smoke Tests  │  (pcp/)
                    └───────────────┘
                           │
              ┌────────────┴────────────┐
              │    Staging Integration  │  Full flow
              │    (pcp-dev/ + Discord) │  with dev channel
              └─────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         │       E2E Comprehensive Tests     │  88 tests
         │           (pcp-dev/)              │  automated
         └───────────────────────────────────┘
                           │
    ┌──────────────────────┴──────────────────────┐
    │              Unit/Integration Tests         │  Fast
    │              (any environment)              │  isolated
    └─────────────────────────────────────────────┘
```

### What to Test Where

| Test Type | Where | Command |
|-----------|-------|---------|
| Quick unit tests | pcp-dev/ | `python3 scripts/test_v4_architecture.py` |
| Full E2E suite | pcp-dev/ | `python3 scripts/test_e2e_comprehensive.py` |
| Discord integration | pcp-dev/ | Send messages to #sean-pcp-dev |
| Stress tests | pcp-dev/ | `--category "Stress Tests"` |
| Production smoke | pcp/ | `python3 scripts/test_production_smoke.py` |

### Pre-Merge Checklist

Before promoting dev → prod:

- [ ] All 88+ E2E tests pass
- [ ] Stress tests pass (concurrent access)
- [ ] Manually tested in #sean-pcp-dev
- [ ] No obvious bugs in 1+ hour of use
- [ ] Database migrations tested (if schema changed)

---

## Promoting Changes to Production

When development is stable and tested, promote to production:

### Step 1: Final Testing in Dev

```bash
cd /path/to/pcp/dev

# Run full test suite
python3 scripts/test_e2e_comprehensive.py

# Run live tests
PCP_LIVE_TESTS=1 python3 scripts/test_e2e_comprehensive.py

# Manual testing complete?
```

### Step 2: Commit and Tag in Dev

```bash
cd /path/to/pcp/dev

# Ensure all changes committed
git status
git add -A
git commit -m "feat: Complete feature X implementation"

# Tag the release
git tag -a v4.1.0 -m "Release v4.1.0: Feature X"
```

### Step 3: Pull Changes into Production

```bash
cd /path/to/pcp

# Backup production database
cp vault/vault.db vault/vault.db.backup_$(date +%Y%m%d_%H%M%S)

# Fetch from dev
git fetch ../pcp-dev develop:develop-incoming

# Review what's coming
git log master..develop-incoming --oneline

# Merge (or cherry-pick specific commits)
git merge develop-incoming -m "Merge develop: Feature X"

# Or cherry-pick specific commits:
# git cherry-pick <commit-hash>
```

### Step 4: Deploy Production

```bash
cd /path/to/pcp

# Rebuild and restart container
docker compose down
docker compose up -d --build

# Run smoke test
python3 scripts/test_production_smoke.py

# Monitor logs
docker logs -f pcp-agent
```

### Step 5: Verify in Production

1. Send a test message in `#sean-pcp`
2. Verify response is correct
3. Check no errors in logs
4. Monitor for 1 hour

### Rollback if Needed

```bash
cd /path/to/pcp

# Stop container
docker compose down

# Revert git
git reset --hard HEAD~1

# Restore database backup
cp vault/vault.db.backup_YYYYMMDD_HHMMSS vault/vault.db

# Restart
docker compose up -d
```

---

## Configuration Reference

### Directory Structure

```
pcp/                          # PRODUCTION
├── config/
│   └── environments/
│       └── prod.env          # Production config (secrets)
├── vault/
│   └── vault.db              # Production database
├── docker-compose.yaml       # Production container
└── ...

pcp-dev/                      # DEVELOPMENT
├── config/
│   └── environments/
│       └── dev.env           # Dev config (test webhook)
├── vault/
│   └── vault_dev.db          # Dev database
├── docker-compose.yaml       # Dev container
└── ...
```

### Environment Variables

| Variable | Production | Development |
|----------|------------|-------------|
| `PCP_ENV` | `production` | `development` |
| `VAULT_DB_PATH` | `/workspace/vault/vault.db` | `/workspace/vault/vault_dev.db` |
| `DISCORD_WEBHOOK_URL` | Prod webhook | Dev webhook |
| `LOG_LEVEL` | `INFO` | `DEBUG` |
| `TEST_MODE` | `false` | `true` |

### Docker Containers

| Container | Port | Database | Discord |
|-----------|------|----------|---------|
| `pcp-agent` | 8080 | vault.db | #sean-pcp |
| `pcp-agent-dev` | 8081 | vault_dev.db | #sean-pcp-dev |

---

## Troubleshooting

### "Which environment am I in?"

```bash
# Check current directory
pwd
# /path/to/pcp     = PRODUCTION
# /path/to/pcp/dev = DEVELOPMENT

# Check running containers
docker ps | grep pcp
```

### Database Issues

```bash
# Check which database
sqlite3 vault/vault.db "SELECT COUNT(*) FROM captures_v2;"      # Prod
sqlite3 vault/vault_dev.db "SELECT COUNT(*) FROM captures_v2;"  # Dev

# Verify container is using correct DB
docker exec pcp-agent-dev env | grep VAULT
# Should show: VAULT_DB_PATH=/workspace/vault/vault_dev.db
```

### Git Confusion

```bash
# In pcp-dev, check remotes
git remote -v
# origin = the dev repo
# prod   = production repo

# Pull latest from prod (if needed)
git fetch prod master
git merge prod/master
```

### Container Won't Start

```bash
# Check logs
docker logs pcp-agent-dev

# Verify network exists
docker network ls | grep agentops-proxy
docker network create agentops-proxy  # If missing

# Check port conflicts
sudo lsof -i :8081
```

---

## Quick Reference Card

### Development (Daily)

```bash
cd /path/to/pcp/dev
docker compose up -d
python3 scripts/test_e2e_comprehensive.py
# ... develop ...
git commit -am "feat: Something new"
```

### Promote to Production

```bash
# In pcp-dev: tag and push
git tag -a v4.x.x -m "Release"

# In pcp: pull and deploy
cd /path/to/pcp
cp vault/vault.db vault/vault.db.backup_$(date +%Y%m%d_%H%M%S)
git fetch ../pcp-dev develop:incoming
git merge incoming
docker compose up -d --build
python3 scripts/test_production_smoke.py
```

### Emergency Rollback

```bash
cd /path/to/pcp
docker compose down
git reset --hard HEAD~1
cp vault/vault.db.backup_LATEST vault/vault.db
docker compose up -d
```

---

*Document Version: 2.0 - Full Environment Separation*
