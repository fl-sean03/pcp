# Contributing to PCP

Thanks for your interest in PCP. This document covers how to get involved.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment (see README.md)
4. Create a feature branch from `main`

## Development Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/pcp.git
cd pcp

# Copy environment template
cp config/environments/.env.example config/environments/dev.env

# Build dev container
docker compose up -d --build

# Run tests
docker exec pcp-agent-dev python3 /workspace/scripts/test_pcp.py
```

## Making Changes

### Code Style

- Python: Follow PEP 8. Use type hints where practical.
- Shell scripts: Use `set -euo pipefail`. Quote variables.
- Keep functions focused and small. Prefer clarity over cleverness.

### Commit Messages

Write clear, descriptive commit messages:
- Use imperative mood ("Add feature" not "Added feature")
- First line: 50 chars or less, summarize the change
- Body (if needed): Explain why, not what

### What to Work On

- Check [Issues](https://github.com/fl-sean03/pcp/issues) for open tasks
- Bug fixes are always welcome
- New skills and integrations
- Documentation improvements
- Test coverage

## Pull Requests

1. Keep PRs focused on a single change
2. Include tests for new functionality
3. Update documentation if behavior changes
4. Ensure all tests pass before submitting

## Architecture Guidelines

- **Let Claude handle intelligence** - Don't build regex parsers or classifiers. Provide raw data and let Claude analyze it.
- **Fail gracefully** - Return sensible defaults, don't crash. Log clearly.
- **Structured output** - When producing programmatic output, include JSON alongside human-readable text.
- **Avoid over-engineering** - Solve the current problem. Don't design for hypothetical requirements.

## Adding a New Skill

Create a directory under `skills/`:

```
skills/my-skill/
├── SKILL.md        # Required: metadata + instructions
└── helper.py       # Optional: helper scripts
```

See `skills/voice-transcription/` for an example.

## Questions?

Open an issue or start a discussion on the repository.
