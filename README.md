# PCP - Personal Control Plane

A framework for building AI-powered personal assistants that capture, understand, remember, and act on your behalf.

PCP runs as a containerized Claude Code agent with persistent memory (SQLite + ChromaDB), integrations (email, calendar, OneDrive, Twitter/X), and a background task system. Talk naturally through Discord - PCP handles the rest.

## What PCP Does

- **Universal Capture** - Share text, images, files, or voice notes. PCP extracts people, projects, topics, and deadlines automatically.
- **Intelligent Search** - Keyword and semantic search across everything you've captured, including emails and files.
- **Task Management** - Auto-detects action items from conversation. Tracks deadlines, sends reminders.
- **Smart Briefs** - Daily, weekly, and end-of-day digests with AI-generated insights.
- **Background Processing** - Long-running tasks (research, transcription, file processing) execute asynchronously and report back.
- **Relationship Intelligence** - Tracks who you interact with, detects stale relationships, provides meeting prep.
- **Self-Reflection** - Weekly automated analysis of usage patterns with improvement recommendations.
- **Skill System** - Extensible capabilities via modular skills. Create new skills as you discover gaps.

## Architecture

```
Discord / Webhook
       |
  Agent Gateway
       |
  PCP Container (Claude Code)
       |
  +----+----+----+----+
  |    |    |    |    |
Vault  Email  OneDrive  Background
(SQLite)  (Graph)  (rclone)  Supervisor
```

PCP runs inside a Docker container with:
- **Claude Code** as the reasoning engine
- **SQLite** for structured data (captures, tasks, people, projects)
- **ChromaDB** for semantic search embeddings
- **Playwright** for browser automation (Twitter, Overleaf)
- **rclone** for cloud storage access

## Quick Start

### Prerequisites

- Docker and Docker Compose
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) with valid credentials
- A Discord bot (for the conversational interface)

### Setup

```bash
# Clone the repo
git clone https://github.com/fl-sean03/pcp.git
cd pcp

# Copy environment template
cp config/environments/.env.example config/environments/prod.env
# Edit prod.env with your Discord webhook URL and other settings

# Build and start
docker compose up -d --build

# Verify
docker ps  # Should show pcp-agent as healthy
```

### Configuration

Edit `config/pcp.yaml` to customize:
- Discord webhook URLs
- Scheduled task timing
- Integration credentials
- Capture behavior

## Project Structure

```
pcp/
├── README.md               # This file
├── VISION.md               # Project vision and philosophy
├── SPEC.md                 # Technical specification (v4.0)
├── CLAUDE.md               # AI agent context (instructions for Claude)
├── Dockerfile              # Container definition
├── docker-compose.yaml     # Container orchestration
├── config/
│   ├── pcp.yaml            # Main configuration
│   └── environments/       # Environment-specific settings
├── scripts/
│   ├── vault_v2.py         # Core: capture, search, tasks
│   ├── knowledge.py        # Permanent knowledge base
│   ├── brief.py            # Smart brief generation
│   ├── email_processor.py  # Outlook/Graph integration
│   ├── pcp_supervisor.py   # Background task supervisor
│   ├── task_delegation.py  # Async task queue
│   ├── skill_loader.py     # Skill system
│   ├── common/             # Shared utilities
│   ├── self_improvement/   # Capability gap detection
│   └── hooks/              # Session lifecycle hooks
├── prompts/                # System prompts for different modes
├── skills/                 # Custom user-created skills
├── .claude/skills/         # Claude Code managed skills
├── tests/                  # Test suite
└── docs/
    ├── ARCHITECTURE_V4.md          # System architecture
    ├── DEVELOPMENT_GUIDE.md        # Development workflow
    ├── BACKGROUND_TASK_ARCHITECTURE_V2.md
    ├── SELF_REFLECTION_SYSTEM.md
    └── archived/                   # Historical planning docs
```

## Development

PCP uses a dev/prod split:

```
~/Workspace/pcp/
├── dev/       # Development - make changes here
├── prod/      # Production - deployed from dev
└── backups/   # Automated vault backups
```

### Workflow

1. Make changes in `dev/`
2. Test in the dev container: `docker compose up -d --build`
3. Run tests: `docker exec pcp-agent-dev python3 /workspace/scripts/test_pcp.py`
4. Deploy to prod: `../deploy.sh`

### Running Tests

```bash
# Unit tests
docker exec pcp-agent-dev python3 /workspace/scripts/test_pcp.py

# E2E smoke test
docker exec pcp-agent-dev python3 /workspace/tests/e2e_test_suite.py
```

## Key Concepts

### Captures vs Knowledge

| | Captures | Knowledge |
|---|---|---|
| Nature | Transient observations | Permanent facts |
| Source | Conversations, notes | Verified/confirmed info |
| Example | "John said API is slow" | "API rate limit is 100/min" |

### Background Tasks

Tasks that take >30 seconds are delegated to a background supervisor:

```
User message -> PCP acknowledges -> Supervisor picks up task -> Worker executes -> Result posted to Discord
```

### Skills

Skills are modular capabilities. Create new ones in `skills/`:

```
skills/
└── my-skill/
    ├── SKILL.md      # Instructions + metadata
    └── helper.py     # Optional helper scripts
```

## Documentation

| Document | Description |
|----------|-------------|
| [VISION.md](VISION.md) | Project philosophy and goals |
| [SPEC.md](SPEC.md) | Complete technical specification |
| [Architecture](docs/ARCHITECTURE_V4.md) | System architecture (v4) |
| [Development Guide](docs/DEVELOPMENT_GUIDE.md) | Dev workflow and conventions |
| [Background Tasks](docs/BACKGROUND_TASK_ARCHITECTURE_V2.md) | Async task system |
| [Self-Reflection](docs/SELF_REFLECTION_SYSTEM.md) | Automated improvement system |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
