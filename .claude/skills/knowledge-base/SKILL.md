---
name: knowledge-base
description: fact, decision, architecture, knowledge, permanent, remember forever, always know, decisions, outcomes, lessons learned
---

# Knowledge Base - Permanent Facts and Decisions

## Quick Start

Knowledge is PCP's permanent memory for facts that should never be forgotten:
- **Facts**: "API rate limit is 100 req/min"
- **Architecture**: "MatterStack uses Redis for caching"
- **Preferences**: "the user prefers concise responses"
- **Decisions**: Explicit choices with rationale and outcomes

**Script:** `knowledge.py`

## Capture vs Knowledge - When To Use Each

| Use Case | Tool | Example |
|----------|------|---------|
| Something the user says in conversation | `smart_capture()` | "John mentioned the API is slow" |
| Permanent fact to remember forever | `add_knowledge()` | "API rate limit is 100 req/min" |
| Explicit decision with rationale | `record_decision()` | "Decided to use Redis for caching" |

**Rule of thumb:**
- **Capture**: Transient observations, conversations, notes
- **Knowledge**: Permanent facts, architecture, preferences
- **Decision**: Explicit choices that may need outcome tracking

## Knowledge Functions

### Add Knowledge

```python
from knowledge import add_knowledge

# Basic usage
knowledge_id = add_knowledge("MatterStack uses Redis for session caching")

# Full options
knowledge_id = add_knowledge(
    content="API rate limit is 100 requests per minute",
    category="architecture",     # architecture|decision|fact|preference
    project_id=5,                # Link to project
    confidence=0.9,              # 0.0-1.0 confidence level
    source="John's email",       # Where this came from
    tags=["api", "limits"]       # Tags for organization
)
```

### Query Knowledge

```python
from knowledge import query_knowledge, list_knowledge, get_knowledge

# Search by content
results = query_knowledge("Redis")
results = query_knowledge("rate limit", category="architecture")

# List all or filtered
all_knowledge = list_knowledge()
facts = list_knowledge(category="fact")
project_knowledge = list_knowledge(project_id=5)

# Get by ID
knowledge = get_knowledge(42)
```

### Update and Delete

```python
from knowledge import update_knowledge, delete_knowledge

# Update (only provided fields change)
update_knowledge(42, content="Updated content", category="decision")

# Delete
delete_knowledge(42)
```

### CLI Usage

```bash
# Add knowledge
python knowledge.py add "MatterStack uses Redis" --category architecture
python knowledge.py add "the user prefers concise responses" --category preference --source "Observation"
python knowledge.py add "API limit is 100/min" --category fact --project 1 --tags "api,limits"

# Search
python knowledge.py search "Redis"
python knowledge.py search "rate limit" --category architecture

# List
python knowledge.py list
python knowledge.py list --category fact
python knowledge.py list --project 1 --limit 10

# Get by ID
python knowledge.py get 42
```

## Decision Tracking

Decisions are special - they have outcomes that should be tracked.

### Record a Decision

```python
from knowledge import record_decision

decision_id = record_decision(
    content="Use Redis for caching instead of Memcached",
    context="Redis supports more data structures, team has experience",
    project_id=5,
    alternatives=["Memcached", "No caching", "In-memory only"]
)
```

### Link Outcome (Later)

When you learn how a decision turned out:

```python
from knowledge import link_outcome

link_outcome(
    decision_id=42,
    outcome="Redis worked well, 50% latency reduction",
    assessment="positive",       # positive|negative|neutral
    lessons_learned="Should have configured eviction policy earlier"
)
```

### Find Decisions Needing Follow-up

```python
from knowledge import get_decisions_pending_outcome, list_decisions

# Get old decisions without outcomes (default: 30+ days old)
pending = get_decisions_pending_outcome(days_old=30)

# List decisions with filters
all_decisions = list_decisions()
project_decisions = list_decisions(project_id=5)
decisions_with_outcomes = list_decisions(with_outcome=True)
pending_decisions = list_decisions(with_outcome=False)
```

### CLI for Decisions

```bash
# Record a decision
python knowledge.py decision "Use Redis for caching" --context "Team experience" --project 1
python knowledge.py decision "Hire contractor for UI" --alternatives "hire full-time,use agency"

# Link outcome
python knowledge.py outcome 42 "Redis reduced latency 50%" --assessment positive
python knowledge.py outcome 42 "Didn't work, too complex" --assessment negative --lessons "Start simpler"

# List decisions
python knowledge.py decisions
python knowledge.py decisions --pending           # Without outcomes
python knowledge.py decisions --with-outcome      # With outcomes
python knowledge.py decisions --project 1
```

## Categories Explained

| Category | Use For | Examples |
|----------|---------|----------|
| `fact` | Objective truths | "API limit is 100/min", "John's email is x@y.com" |
| `architecture` | Technical decisions | "Uses Redis", "Frontend is React" |
| `decision` | Explicit choices | "Decided to use X over Y" |
| `preference` | the user's preferences | "Prefers concise responses" |

## When User Says...

| User Says... | Action |
|--------------|--------|
| "Remember that X uses Y" | `add_knowledge(content, category="architecture")` |
| "It's a fact that..." | `add_knowledge(content, category="fact")` |
| "I prefer X" | `add_knowledge(content, category="preference")` |
| "We decided to..." | `record_decision(content, context)` |
| "That decision worked out because..." | `link_outcome(id, outcome, assessment)` |
| "What do we know about X?" | `query_knowledge(query)` |
| "What decisions have we made about X?" | `list_decisions(project_id=X)` |
| "What decisions need follow-up?" | `get_decisions_pending_outcome()` |

## Database Tables

| Table | Purpose |
|-------|---------|
| `knowledge` | Permanent facts, preferences, architecture |
| `decisions` | Explicit decisions with outcome tracking |

### Knowledge Table Fields

- `id`, `content`, `category` (architecture/decision/fact/preference)
- `project_id` (optional link to project)
- `confidence` (0.0-1.0)
- `source` (where it came from)
- `tags` (JSON array)
- `created_at`, `updated_at`

### Decisions Table Fields

- `id`, `content`, `context` (rationale)
- `alternatives` (JSON array of alternatives considered)
- `project_id`, `capture_id` (optional links)
- `outcome`, `outcome_date`, `outcome_assessment` (positive/negative/neutral)
- `lessons_learned`
- `created_at`

## Related Skills

- `/vault-operations` - Transient captures and searches
- `/brief-generation` - Briefs include recently added knowledge
- `/project-health` - Project context includes related knowledge
