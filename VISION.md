# PCP Vision: Your External Brain

## The Core Insight

PCP is not a note-taking app. It's not a todo list. It's not a vault.

**PCP is the control plane for your cognitive load** - an AI system that extends your memory, understands your context, takes action on your behalf, and gets smarter over time.

Think of it as: What if you had a perfect assistant who knew everything you've ever told them, understood all your projects and relationships, could take action across all your systems, and proactively surfaced the right information at the right time?

---

## Target User Profile

PCP is designed for knowledge workers who are:

- **Builders**: Create sophisticated systems and manage technical projects
- **Multi-threaded**: Multiple active projects, contexts, relationships
- **Automation-minded**: Value systems that work without hand-holding
- **Time-constrained**: Need things to just work, minimal friction
- **Privacy-conscious**: Local-first, self-hosted, full control
- **Discord-native**: Primary communication channel (configurable)

---

## What PCP Should Actually Do

### 1. Universal Capture (Zero Friction)

**Current**: "capture [text]" - requires syntax, categorization
**Vision**: Just talk. Or drop a file. Or share an image. PCP handles it all.

```
"John mentioned the API might need rate limiting"
→ PCP extracts: Person(John), Topic(API, rate limiting), Project(inferred from context)
→ Stores with full context, linked to relevant entities
→ No command needed

[Upload screenshot of error message]
→ PCP OCRs it, extracts the error, links to relevant project
→ "Got it - looks like a Redis connection timeout in MatterStack"

[Drop a PDF document]
→ PCP extracts text, summarizes, stores searchable
→ Links to relevant projects/people mentioned
```

**Multi-Modal Input**:
- **Text**: Natural conversation
- **Images**: Screenshots, photos, diagrams → OCR + vision understanding
- **Files**: PDFs, documents, code → text extraction + indexing
- **OneDrive Sync**: Proactively monitors your cloud storage

Everything you share gets captured, understood, and connected. You never have to decide "is this a note or a task or an idea?" - PCP figures it out.

### 2. Contextual Memory (Actually Useful Retrieval)

**Current**: Keyword search
**Vision**: Semantic understanding + knowledge graph

```
"What was that thing about performance?"
→ Not just keyword match, but semantic search
→ Finds related items even if "performance" wasn't mentioned
→ Returns with context: "On Jan 5, you mentioned MatterStack was slow. You decided to add caching. Here's what you captured..."
```

PCP should answer questions like:
- "What did I decide about X?"
- "What's the status of project Y?"
- "When did I last talk to John?"
- "What's pending from last week?"

### 3. Proactive Intelligence (Adds Value Without Asking)

**Current**: Passive storage
**Vision**: Active participant in your work

**Morning Brief** (not just stats):
```
Good morning.

OVERNIGHT:
- Alpha-trader: +2.3% overnight, 3 positions open
- MatterStack pipeline completed, 847 molecules processed

TODAY:
- You mentioned following up with John about the API (3 days ago)
- Task pending: Review alpha-trader risk parameters

PATTERNS I'VE NOTICED:
- You've mentioned "database performance" 4 times this week
- Might be worth creating a focused task?
```

**Proactive Nudges**:
- "You captured this 3 times - should I create a task?"
- "You mentioned deadline Friday - that's in 2 days"
- "This seems related to what you were working on yesterday"

### 4. Cloud Storage Integration (OneDrive)

**Current**: Manual capture only
**Vision**: PCP proactively monitors your cloud storage

```
[New file appears in OneDrive/Work/Projects/]
→ PCP detects it, indexes content
→ Links to relevant project based on folder/content
→ Next brief: "New document in MatterStack folder: 'Q1 Analysis.docx' - want a summary?"

"What's in my recent documents?"
→ PCP queries OneDrive, returns recent files with context

"Find that spreadsheet about budgets"
→ Searches both vault AND OneDrive
→ Returns: "Found 'Budget_2024.xlsx' in OneDrive/Finance, last modified 3 days ago"
```

**What this enables**:
- Seamless integration between captures and files
- Never lose track of documents
- Proactive awareness of new/changed files
- Search across everything in one place

### 5. Native-First Orchestration

**Current**: Isolated PCP
**Vision**: Central nervous system using native tools

**Key Principle**: PCP runs Claude Code with terminal access. Don't build integrations for things Claude Code can do natively with CLI tools.

```
"Create a GitHub issue for the rate limiting thing"
→ PCP uses `gh issue create` directly (not a custom integration)
→ Pulls context from vault to populate the issue body
→ Returns: "Created issue #47 in repo/name"

"What containers are running?"
→ PCP runs `docker ps` directly
→ Returns formatted status

"What's in my recent commits?"
→ PCP runs `git log --oneline -10`
→ Returns summary
```

**Available Native Tools**:
- `gh` - GitHub CLI (issues, PRs, repos)
- `docker` - Container management
- `git` - Version control
- `curl` - HTTP/API calls
- Standard Unix tools

**What DOES need custom scripts**:
- Microsoft Graph API (OneDrive, Outlook) - OAuth flow, token management
- Smart capture with NLP extraction - entity detection, temporal parsing
- Knowledge base - structured permanent storage
- Briefs and patterns - aggregation logic

PCP becomes the orchestration layer - using native tools where they exist, custom scripts only where necessary.

### 5. Temporal Awareness

**Current**: Static captures
**Vision**: Time-aware system

```
"Remind me about this tomorrow"
→ Stores with temporal trigger
→ Tomorrow's brief includes it

"What did I work on last week?"
→ Temporal query across all captures

"I need to do X before Friday"
→ Creates time-bound task
→ Escalates in brief as deadline approaches
```

### 6. Self-Evolution (Gets Smarter)

**Current**: Static scripts
**Vision**: Learns and adapts

```
PCP notices: "User always captures project updates on Monday"
→ Adds to patterns
→ Prompts on Monday if no update captured

PCP notices: "User refers to 'John' frequently, always in API context"
→ Builds entity profile
→ When you mention John, automatically links to API project

PCP notices: "User's briefs work better with bullet points"
→ Adapts output format
```

---

## Technical Architecture

### Data Model

```
┌─────────────────────────────────────────────────────────────┐
│                     KNOWLEDGE GRAPH                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐            │
│  │ CAPTURES │────▶│ ENTITIES │────▶│ PROJECTS │            │
│  └──────────┘     └──────────┘     └──────────┘            │
│       │                │                │                   │
│       ▼                ▼                ▼                   │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐            │
│  │EMBEDDINGS│     │  PEOPLE  │     │DECISIONS │            │
│  └──────────┘     └──────────┘     └──────────┘            │
│       │                │                │                   │
│       ▼                ▼                ▼                   │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐            │
│  │ TEMPORAL │     │RELATIONS │     │  TASKS   │            │
│  └──────────┘     └──────────┘     └──────────┘            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Core Tables**:

```sql
-- Everything the user says
captures (
    id, content, raw_input,
    capture_type,  -- auto-detected: note/task/idea/decision/question
    embedding,     -- vector for semantic search
    extracted_entities,  -- JSON: people, projects, topics mentioned
    temporal_refs,       -- JSON: dates, deadlines, reminders
    context,             -- what was happening when captured
    created_at, updated_at
)

-- People the user interacts with
people (
    id, name, aliases,
    relationship,    -- colleague/friend/client/etc
    context,         -- relationship context
    last_mentioned,
    capture_count,   -- how often mentioned
    metadata         -- JSON: email, company, notes
)

-- User's projects
projects (
    id, name, description,
    status,          -- active/paused/completed
    key_decisions,   -- JSON array
    related_people,
    last_activity,
    metadata
)

-- Explicit decisions made
decisions (
    id, content,
    context,         -- why this decision
    project_id,
    alternatives_considered,
    created_at
)

-- Actionable items
tasks (
    id, content,
    priority,        -- auto-detected or explicit
    due_date,
    status,
    blockers,
    related_captures,
    created_at
)

-- Learned patterns
patterns (
    id, pattern_type,
    description,
    confidence,
    last_observed,
    action_taken     -- what PCP does with this pattern
)
```

### Semantic Search (ChromaDB)

Every capture gets embedded and stored in ChromaDB for semantic retrieval:

```python
# When capturing
embedding = get_embedding(content)
chroma_collection.add(
    documents=[content],
    embeddings=[embedding],
    metadatas=[{"capture_id": id, "type": type, "date": date}],
    ids=[str(id)]
)

# When searching
results = chroma_collection.query(
    query_texts=["that performance thing"],
    n_results=5
)
# Returns semantically similar captures even without exact keyword match
```

### Entity Extraction Pipeline

Every input goes through NLP extraction:

```python
def process_input(text):
    # 1. Detect intent
    intent = classify_intent(text)  # capture/query/action/chat

    # 2. Extract entities
    entities = extract_entities(text)
    # Returns: {
    #   "people": ["John"],
    #   "projects": ["API"],
    #   "dates": ["tomorrow", "Friday"],
    #   "topics": ["rate limiting", "performance"]
    # }

    # 3. Link to existing entities
    linked = link_entities(entities)
    # John → people.id=5, API → projects.id=3

    # 4. Detect temporal references
    temporal = extract_temporal(text)
    # "tomorrow" → 2024-01-14, "before Friday" → deadline:2024-01-17

    # 5. Store with full context
    capture = store_capture(text, intent, entities, linked, temporal)

    return capture
```

### Integration Layer

```python
class IntegrationHub:
    """Central hub for all system integrations"""

    async def query_alpha_trader(self, question):
        """Ask alpha-trader agent about trading status"""
        # Uses Docker exec to query alpha-trader
        pass

    async def query_matterstack(self, question):
        """Get MatterStack pipeline status"""
        # Reads logs or queries API
        pass

    async def create_github_issue(self, title, body, repo):
        """Create GitHub issue with context"""
        pass

    async def get_calendar(self, date_range):
        """Get calendar events"""
        pass

    async def send_notification(self, message, channel):
        """Send to Discord/other channels"""
        pass
```

### Proactive System

```python
class ProactiveEngine:
    """Generates proactive insights and actions"""

    async def generate_morning_brief(self):
        """Create intelligent morning summary"""
        brief = []

        # Overnight activity
        brief.append(await self.get_overnight_activity())

        # Today's context
        brief.append(await self.get_todays_context())

        # Pending items
        brief.append(await self.get_pending_items())

        # Patterns noticed
        brief.append(await self.get_pattern_insights())

        # Upcoming deadlines
        brief.append(await self.get_upcoming_deadlines())

        return format_brief(brief)

    async def check_patterns(self):
        """Detect patterns in the user's behavior"""
        # Repeated mentions → suggest task
        # Time-based patterns → adapt timing
        # Topic clusters → suggest connections
        pass

    async def check_reminders(self):
        """Check for time-triggered items"""
        pass
```

---

## Implementation Phases

### Phase 1: Foundation ✅ COMPLETE
- [x] Conversational interface (no commands)
- [x] Basic vault (captures, search)
- [x] Self-modification capability
- [x] Isolated session (no cross-contamination)
- [x] Docker-based deployment

### Phase 2: Intelligence ✅ COMPLETE
- [x] Entity extraction (people, projects, topics)
- [x] Auto-categorization of captures
- [x] Temporal reference parsing
- [x] File processing (images, PDFs)
- [x] Context-aware responses

**Delivered**:
- `scripts/vault_v2.py` - Smart capture with NLP
- `scripts/file_processor.py` - Image/PDF handling
- Enhanced database schema

### Phase 3: Proactivity ✅ COMPLETE
- [x] Intelligent daily briefs
- [x] Pattern detection engine
- [x] Time-aware reminders
- [x] Deadline tracking and escalation

**Delivered**:
- `scripts/brief.py` - Smart brief generation
- `scripts/patterns.py` - Pattern detection
- `scripts/reminders.py` - Reminder system
- `scripts/scheduler.py` - Scheduled tasks

### Phase 4: Native-First + Knowledge + Email ✅ COMPLETE
- [x] Native CLI tools documented (gh, docker, git, curl)
- [x] Knowledge base (permanent facts/decisions) - `knowledge.py`
- [x] Email processing (Outlook via Microsoft Graph) - `email_processor.py`
- [x] OneDrive integration - `onedrive_rclone.py`
- [x] Semantic search with embeddings (ChromaDB) - `embeddings.py`
- [x] Cross-system queries - `system_queries.py`
- [x] Proactive intelligence - `proactive.py`

**Key Principle**: Use native CLI tools where available. Only build custom scripts for:
- Microsoft Graph API (requires OAuth)
- Knowledge base (structured storage)
- NLP extraction (entity detection)

### Phase 5: Future
- [ ] Browser extension for quick capture
- [ ] Voice input
- [ ] Mobile PWA
- [ ] Adaptive learning (personalized thresholds)

---

## What Makes It Truly Effective

### 1. Zero Friction
The interface is just talking. No syntax, no commands, no categories to choose. You tell PCP something, PCP handles it. This is critical - any friction reduces usage.

### 2. Actually Useful Memory
Not just storage, but retrieval that works. When you ask "what was that thing about X?", you get the right answer with context. This requires semantic search + knowledge graph.

### 3. Proactive Value
PCP should add value without being asked. Morning briefs that surface what matters. Reminders at the right time. Connections you didn't see. This transforms it from tool to partner.

### 4. Context Awareness
PCP knows who John is, what project you're talking about, what you decided last week. It maintains context across conversations, days, weeks.

### 5. Cross-System Power
One interface to everything. Ask PCP about trading, it queries alpha-trader. Ask about MatterStack, it knows. Create a GitHub issue, done. This is the "control plane" aspect.

### 6. Continuous Evolution
PCP learns your patterns, adapts to your needs, builds new capabilities. It gets better over time, not stale.

---

## The Ultimate Test

**In 6 months, PCP should be able to:**

1. "What's going on?"
   → Full status across all systems and pending items

2. "What did I decide about the database thing?"
   → Retrieves decision with context, even if vaguely asked

3. "I need to follow up with John about the API before the deadline"
   → Creates task, links to John and API project, sets deadline, will remind

4. "How did alpha-trader do this week?"
   → Queries trading system, returns performance summary

5. "Brief me"
   → Intelligent summary: overnight activity, today's context, pending items, deadlines, patterns noticed

6. "Remember that MatterStack uses Redis for caching"
   → Stores as decision/knowledge, links to MatterStack project, retrievable later

7. [You mention "performance" 5 times in a week]
   → PCP proactively: "You've mentioned performance a lot - want me to create a focused task?"

---

## Next Steps

To move toward this vision:

1. **Enhance the data model** - Add entity extraction and linking
2. **Add ChromaDB** - Enable semantic search
3. **Build the brief engine** - Make proactive briefs actually useful
4. **Add integrations** - Start with alpha-trader status queries

The foundation is solid. Now it's about layering intelligence on top.

---

*This document is the north star. Individual implementations may vary, but this is what PCP is becoming.*
