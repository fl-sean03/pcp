---
name: native-tools
description: GitHub CLI, docker commands, git operations, curl, native CLI tools, gh issue, gh pr, container, repository, API calls (project)
---

# Native Tools Skill

Use native CLI tools directly instead of building custom integrations. Claude Code has full terminal access - use it.

## Quick Start

PCP follows the **native-first principle**: if a CLI tool exists, use it directly. Don't build wrapper scripts.

**Available CLI tools:**
- `gh` - GitHub CLI (issues, PRs, repos)
- `docker` - Container management
- `git` - Version control
- `curl` - HTTP/API calls
- Standard Unix tools (grep, find, ls, etc.)

## Native-First Principle

> **Rule:** Only build custom scripts for things that require:
> 1. OAuth complexity (Microsoft Graph)
> 2. Structured data schema (knowledge base, vault)
> 3. NLP extraction (entity detection)
>
> Everything else? Use the CLI directly.

## GitHub CLI (`gh`)

### Issues

```bash
# Create issue
gh issue create --repo owner/repo --title "Bug: login fails" --body "Description here"

# List issues
gh issue list --assignee @me
gh issue list --repo owner/repo --state open

# View issue
gh issue view 123 --repo owner/repo

# Close issue
gh issue close 123 --repo owner/repo

# Comment on issue
gh issue comment 123 --body "Fixed in PR #456"
```

### Pull Requests

```bash
# Create PR
gh pr create --title "Fix login bug" --body "Fixes #123"

# List PRs
gh pr list --author @me
gh pr list --state open

# View PR
gh pr view 456

# Review PR
gh pr review 456 --approve
gh pr review 456 --request-changes --body "Please fix X"

# Merge PR
gh pr merge 456 --squash
```

### Other gh Commands

```bash
# Search code
gh search code "function_name" --repo owner/repo

# View repo
gh repo view owner/repo

# Clone repo
gh repo clone owner/repo

# Releases
gh release list --repo owner/repo
gh release create v1.0.0 --generate-notes
```

## Docker

### Container Management

```bash
# List running containers
docker ps

# List all containers
docker ps -a

# View container logs
docker logs container_name
docker logs -f container_name  # Follow

# Execute command in container
docker exec container_name command
docker exec -it container_name bash  # Interactive shell

# Container stats
docker stats container_name

# Inspect container
docker inspect container_name
```

### Compose Operations

```bash
# Start stack
docker compose up -d

# Stop stack
docker compose down

# Rebuild and start
docker compose up -d --build

# View logs
docker compose logs -f service_name
```

### Images

```bash
# List images
docker images

# Pull image
docker pull image:tag

# Build image
docker build -t name:tag .
```

## Git

### Status and History

```bash
# Status
git status

# Log
git log --oneline -10
git log --oneline --all --graph

# Diff
git diff
git diff --staged
git diff branch1..branch2
```

### Branching

```bash
# Create and switch
git checkout -b feature/new-thing

# Switch branch
git checkout main

# List branches
git branch -a
```

### Commits and Push

```bash
# Add and commit
git add .
git commit -m "feat: add new feature"

# Push
git push origin branch-name
git push -u origin branch-name  # Set upstream
```

### Stash

```bash
git stash
git stash pop
git stash list
```

## HTTP/API Calls (`curl`)

### Basic Requests

```bash
# GET request
curl -s https://api.example.com/endpoint | jq .

# POST request with JSON
curl -s -X POST https://api.example.com/endpoint \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}' | jq .

# With authentication
curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/protected | jq .
```

### Common Patterns

```bash
# Check API status
curl -s https://api.example.com/health | jq .

# Download file
curl -L -o filename.zip https://example.com/file.zip

# Follow redirects
curl -L https://example.com/redirect
```

## When the User Says...

| User Request | Command |
|--------------|---------|
| "Create a GitHub issue for X" | `gh issue create --title "X" --body "..."` |
| "What PRs need review?" | `gh pr list --state open` |
| "What containers are running?" | `docker ps` |
| "Show me the logs for X" | `docker logs X` |
| "What's the git status?" | `git status` |
| "Commit these changes" | `git add . && git commit -m "..."` |
| "Call this API endpoint" | `curl -s URL \| jq .` |
| "What's the latest release?" | `gh release list --repo owner/repo` |

## What NOT to Build Custom Scripts For

| Need | Use This | NOT This |
|------|----------|----------|
| GitHub issues | `gh issue create` | custom GitHub API script |
| Container logs | `docker logs` | custom Docker API script |
| Git operations | `git` commands | custom git wrapper |
| API testing | `curl` | custom HTTP client |
| File search | `find`, `grep` | custom file finder |

## What TO Build Custom Scripts For

| Need | Why Custom? | Script |
|------|-------------|--------|
| Microsoft Graph | OAuth token management | `microsoft_graph.py` |
| Knowledge base | Structured schema + search | `knowledge.py` |
| Entity extraction | NLP with Claude | `vault_v2.py` |
| Email processing | OAuth + structured storage | `email_processor.py` |

## Tips

1. **Always check if a CLI tool exists first** - Most common operations have excellent CLI tools
2. **Use `jq` for JSON output** - Pipe API responses through `jq .` for formatting
3. **Use `-s` (silent) with curl** - Hides progress bars for cleaner output
4. **Use `--help`** - Every CLI tool has help: `gh issue --help`, `docker --help`
5. **Combine with PCP** - Use CLI tools then capture results to vault if needed

## Related Skills

- **pcp-operations** - For PCP-specific functions
- **vault-operations** - For capturing CLI outputs to vault
- **knowledge-base** - For storing permanent facts from CLI exploration
