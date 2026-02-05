#!/usr/bin/env python3
"""
PCP Database Schema v2 - Enhanced with files, entities, and intelligence.
Run this to migrate from v1 to v2.
"""

import sqlite3
import os
import json
from datetime import datetime

# Support both container and local development paths
VAULT_PATH = "/workspace/vault/vault.db"
if not os.path.exists(os.path.dirname(VAULT_PATH)) and os.path.exists(os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault")):
    VAULT_PATH = os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db")

SCHEMA_V2 = """
-- Enhanced captures with extraction and file support
CREATE TABLE IF NOT EXISTS captures_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'text',  -- text/image/file/url
    capture_type TEXT DEFAULT 'note',  -- note/task/idea/decision/question

    -- File/media info (if applicable)
    file_path TEXT,                    -- local path to file
    file_name TEXT,                    -- original filename
    file_size INTEGER,                 -- bytes
    mime_type TEXT,                    -- image/png, application/pdf, etc.

    -- Extracted content (for images/files)
    extracted_text TEXT,               -- OCR or file content
    summary TEXT,                      -- AI-generated summary

    -- Entity extraction
    extracted_entities TEXT,           -- JSON: {people:[], projects:[], topics:[]}
    linked_people TEXT,                -- JSON: [person_ids]
    linked_projects TEXT,              -- JSON: [project_ids]

    -- Temporal
    temporal_refs TEXT,                -- JSON: {deadline:, reminder:, mentions:[]}

    -- Metadata
    source TEXT DEFAULT 'discord',     -- discord/onedrive/api/manual
    source_id TEXT,                    -- original message ID, file ID, etc.
    tags TEXT,                         -- JSON array
    status TEXT DEFAULT 'active',      -- active/archived/deleted

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- People the user interacts with
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    aliases TEXT,                      -- JSON: ["Johnny", "J"]
    relationship TEXT,                 -- colleague/friend/client/family
    context TEXT,                      -- how the user knows them
    organization TEXT,                 -- company/group
    email TEXT,
    notes TEXT,

    -- Stats
    mention_count INTEGER DEFAULT 0,
    last_mentioned TIMESTAMP,

    -- Metadata
    metadata TEXT,                     -- JSON for extra data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- the user's projects
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',      -- active/paused/completed/archived

    -- Matching
    keywords TEXT,                     -- JSON: ["api", "backend"] for auto-linking
    folder_patterns TEXT,              -- JSON: OneDrive folder patterns to watch

    -- Relations
    related_people TEXT,               -- JSON: [person_ids]

    -- Stats
    capture_count INTEGER DEFAULT 0,
    last_activity TIMESTAMP,

    -- Metadata
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Explicit decisions
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    context TEXT,                      -- why this decision was made
    alternatives TEXT,                 -- JSON: what else was considered

    project_id INTEGER,
    capture_id INTEGER,                -- source capture

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (capture_id) REFERENCES captures_v2(id)
);

-- Tasks with full tracking
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,

    priority TEXT DEFAULT 'normal',    -- low/normal/high/urgent
    status TEXT DEFAULT 'pending',     -- pending/in_progress/done/cancelled

    due_date DATE,
    reminder_at TIMESTAMP,

    -- Context
    context TEXT,
    blockers TEXT,                     -- JSON: what's blocking

    -- Relations
    project_id INTEGER,
    related_captures TEXT,             -- JSON: [capture_ids]
    related_people TEXT,               -- JSON: [person_ids]

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Files from OneDrive and other sources
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source info
    source TEXT NOT NULL,              -- onedrive/local/discord
    source_id TEXT,                    -- OneDrive item ID, etc.
    source_path TEXT,                  -- full path in source

    -- Local cache
    local_path TEXT,                   -- cached local path

    -- File info
    name TEXT NOT NULL,
    extension TEXT,
    mime_type TEXT,
    size_bytes INTEGER,

    -- Content extraction
    extracted_text TEXT,
    summary TEXT,

    -- Linking
    linked_projects TEXT,              -- JSON: [project_ids]
    linked_captures TEXT,              -- JSON: [capture_ids]

    -- Sync status
    last_synced TIMESTAMP,
    last_modified_remote TIMESTAMP,
    sync_status TEXT DEFAULT 'synced', -- synced/pending/error

    -- Metadata
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- OneDrive sync configuration
CREATE TABLE IF NOT EXISTS onedrive_watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_path TEXT NOT NULL,         -- /Work/Projects/MatterStack
    project_id INTEGER,                -- auto-link to project

    recursive BOOLEAN DEFAULT TRUE,
    file_patterns TEXT,                -- JSON: ["*.pdf", "*.docx"]

    last_sync TIMESTAMP,
    sync_token TEXT,                   -- delta sync token

    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Learned patterns
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT,                 -- time_based/topic_cluster/behavior/preference
    description TEXT,

    -- Pattern data
    data TEXT,                         -- JSON: pattern-specific data
    confidence REAL DEFAULT 0.5,
    observations INTEGER DEFAULT 1,

    -- Actions
    action_type TEXT,                  -- suggest_task/remind/auto_link/etc.
    action_data TEXT,                  -- JSON: action parameters

    last_observed TIMESTAMP,
    last_acted TIMESTAMP,

    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase 4: Knowledge base - permanent facts and decisions
CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'fact',      -- architecture/decision/fact/preference

    -- Context
    project_id INTEGER,
    confidence REAL DEFAULT 1.0,       -- 0.0 to 1.0
    source TEXT,                       -- where this knowledge came from
    tags TEXT,                         -- JSON array

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Phase 4: Processed Outlook emails
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,   -- Outlook message ID (for dedup)
    subject TEXT,
    sender TEXT,
    recipients TEXT,                   -- JSON array

    -- Content
    body_preview TEXT,                 -- First 500 chars, stripped of HTML
    body_full TEXT,                    -- Complete email content

    -- Extraction
    extracted_entities TEXT,           -- JSON: {people:[], topics:[]}

    -- Actionability
    is_actionable BOOLEAN DEFAULT FALSE,
    action_taken TEXT,                 -- what action was taken
    draft_id TEXT,                     -- ID of draft reply if created

    -- Timestamps
    received_at TIMESTAMP,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase 4: OAuth tokens for Microsoft Graph API
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,            -- microsoft/google/etc.
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    scopes TEXT,                       -- JSON array of granted scopes

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase 4: Pattern-generated task suggestions
CREATE TABLE IF NOT EXISTS suggested_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,             -- suggested task content
    reason TEXT,                       -- why this was suggested
    source_pattern TEXT,               -- which pattern generated this

    status TEXT DEFAULT 'pending',     -- pending/approved/dismissed

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase 4: Social feed - platform-agnostic social content storage
CREATE TABLE IF NOT EXISTS social_feed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,            -- twitter/linkedin/mastodon/etc.
    post_id TEXT NOT NULL,             -- platform-specific post ID

    -- Author info
    author_name TEXT,                  -- display name
    author_handle TEXT,                -- @handle or username

    -- Content
    content TEXT,                      -- post text/content
    content_url TEXT,                  -- URL to original post
    engagement TEXT,                   -- JSON: {likes, retweets, replies, etc.}

    -- Scoring and actions
    relevance_score REAL,              -- 0.0 to 1.0, Claude-assessed
    suggested_action TEXT,             -- reply/quote/dm/like/ignore
    action_taken TEXT,                 -- what action was actually taken

    -- Timestamps
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Uniqueness constraint per platform
    UNIQUE(platform, post_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_captures_created ON captures_v2(created_at);
CREATE INDEX IF NOT EXISTS idx_captures_type ON captures_v2(capture_type);
CREATE INDEX IF NOT EXISTS idx_captures_source ON captures_v2(source);
CREATE INDEX IF NOT EXISTS idx_people_name ON people(name);
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_files_source ON files(source, source_id);

-- Phase 4 indexes
CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_project ON knowledge(project_id);
CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender);
CREATE INDEX IF NOT EXISTS idx_emails_actionable ON emails(is_actionable);
CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_at);
CREATE INDEX IF NOT EXISTS idx_suggested_tasks_status ON suggested_tasks(status);

-- Social feed indexes
CREATE INDEX IF NOT EXISTS idx_social_feed_platform ON social_feed(platform);
CREATE INDEX IF NOT EXISTS idx_social_feed_relevance ON social_feed(relevance_score);
CREATE INDEX IF NOT EXISTS idx_social_feed_action ON social_feed(action_taken);
CREATE INDEX IF NOT EXISTS idx_social_feed_captured ON social_feed(captured_at);

-- Phase 5: Delegated tasks for dual-agent architecture
CREATE TABLE IF NOT EXISTS delegated_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Task definition (natural language, not structured)
    task_description TEXT NOT NULL,  -- "Transcribe HW5 to Overleaf"
    context TEXT,                    -- JSON: {files: [], preferences: {}, related_captures: []}

    -- Status tracking
    status TEXT DEFAULT 'pending',   -- pending, claimed, running, completed, failed
    priority INTEGER DEFAULT 5,      -- 1=highest, 10=lowest

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    claimed_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Worker tracking
    worker_session_id TEXT,          -- Which Claude session claimed this

    -- Results
    result TEXT,                     -- JSON: success result
    error TEXT,                      -- Error message if failed

    -- Discord integration
    discord_channel_id TEXT,
    discord_user_id TEXT,
    notification_sent INTEGER DEFAULT 0,

    -- Metadata
    created_by TEXT DEFAULT 'main_agent',  -- main_agent or user
    tags TEXT                        -- JSON array for filtering
);

-- Delegated tasks indexes
CREATE INDEX IF NOT EXISTS idx_delegated_tasks_status ON delegated_tasks(status);
CREATE INDEX IF NOT EXISTS idx_delegated_tasks_priority ON delegated_tasks(priority, created_at);
CREATE INDEX IF NOT EXISTS idx_delegated_tasks_worker ON delegated_tasks(worker_session_id);

-- Phase 6: Subagent execution tracking
CREATE TABLE IF NOT EXISTS subagent_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Agent identification
    agent_id TEXT NOT NULL,              -- Claude Code's agentId for resumption
    agent_type TEXT NOT NULL,            -- pcp-worker, homework-transcriber, etc.

    -- Task linkage
    delegated_task_id INTEGER,           -- Link to delegated_tasks if applicable

    -- Status
    status TEXT DEFAULT 'running',       -- running, completed, failed, paused

    -- Context and results
    initial_prompt TEXT,                 -- Original prompt sent to subagent
    result_summary TEXT,                 -- Summary of what was accomplished

    -- Timestamps
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    -- Resumption
    can_resume BOOLEAN DEFAULT TRUE,     -- Whether this agent can be resumed
    resume_count INTEGER DEFAULT 0,      -- How many times it's been resumed

    FOREIGN KEY (delegated_task_id) REFERENCES delegated_tasks(id)
);

-- Subagent execution indexes
CREATE INDEX IF NOT EXISTS idx_subagent_agent_id ON subagent_executions(agent_id);
CREATE INDEX IF NOT EXISTS idx_subagent_type ON subagent_executions(agent_type);
CREATE INDEX IF NOT EXISTS idx_subagent_status ON subagent_executions(status);
CREATE INDEX IF NOT EXISTS idx_subagent_task ON subagent_executions(delegated_task_id);

-- Phase 7: Message Queue for v4.0 architecture
CREATE TABLE IF NOT EXISTS discord_message_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Discord context
    channel_id TEXT NOT NULL,
    message_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    user_name TEXT NOT NULL,

    -- Content
    content TEXT NOT NULL,
    attachments TEXT,  -- JSON array

    -- Processing state
    status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
    priority INTEGER DEFAULT 5,      -- 1=highest, 10=lowest

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results
    response TEXT,
    error TEXT,

    -- Parallel tracking
    spawned_parallel BOOLEAN DEFAULT FALSE,
    parallel_task_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_queue_status ON discord_message_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_created ON discord_message_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_queue_priority ON discord_message_queue(priority, created_at);

-- Phase 7: Parallel tasks for v4.0 architecture
CREATE TABLE IF NOT EXISTS parallel_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source
    queue_message_id INTEGER,

    -- Task info
    description TEXT NOT NULL,
    focus_mode TEXT DEFAULT 'general',
    context TEXT,  -- JSON context data

    -- Status
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed

    -- Process tracking
    pid INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results
    result TEXT,
    error TEXT,

    -- Discord notification
    notification_sent BOOLEAN DEFAULT FALSE,
    discord_channel_id TEXT,

    -- Progress updates
    progress_updates TEXT,  -- JSON array of progress messages

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (queue_message_id) REFERENCES discord_message_queue(id)
);

CREATE INDEX IF NOT EXISTS idx_parallel_status ON parallel_tasks(status);
CREATE INDEX IF NOT EXISTS idx_parallel_queue ON parallel_tasks(queue_message_id);

-- Phase 8: Self-Reflection System
-- Stores reflection session history and recommendations

CREATE TABLE IF NOT EXISTS reflection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    days_analyzed INTEGER NOT NULL,

    -- Full report content
    report_markdown TEXT,

    -- Structured data
    recommendations JSON,           -- Array of recommendation objects
    metrics JSON,                   -- Usage stats, health scores

    -- Status tracking
    status TEXT DEFAULT 'pending_review',  -- pending_review, reviewed, actioned
    reviewed_at TEXT,
    reviewed_notes TEXT,

    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    agent_model TEXT,               -- Which Claude model ran the reflection
    context_tokens INTEGER,         -- How much context was used

    -- Links
    discord_message_id TEXT         -- Message ID where summary was posted
);

-- Individual recommendations with status tracking
CREATE TABLE IF NOT EXISTS reflection_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reflection_id INTEGER NOT NULL,

    -- Recommendation content
    recommendation_id TEXT NOT NULL,  -- e.g., "QW-1", "MP-3"
    category TEXT NOT NULL,           -- quick_win, medium_improvement, major_proposal, wild_idea, anti
    title TEXT NOT NULL,
    observation TEXT,
    evidence TEXT,
    proposal TEXT,
    implementation TEXT,

    -- Status
    status TEXT DEFAULT 'pending',    -- pending, approved, rejected, implemented, deferred
    status_updated_at TEXT,
    status_notes TEXT,

    -- Outcome tracking (for implemented recommendations)
    outcome TEXT,
    outcome_date TEXT,
    outcome_assessment TEXT,          -- positive, negative, neutral, mixed

    -- Metadata
    priority INTEGER,                 -- 1 = highest
    effort_estimate TEXT,             -- "30min", "2h", "1d", etc.

    FOREIGN KEY (reflection_id) REFERENCES reflection_history(id)
);

-- Reflection indexes
CREATE INDEX IF NOT EXISTS idx_reflection_status ON reflection_history(status);
CREATE INDEX IF NOT EXISTS idx_reflection_created ON reflection_history(created_at);
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON reflection_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recommendations_category ON reflection_recommendations(category);
CREATE INDEX IF NOT EXISTS idx_recommendations_reflection ON reflection_recommendations(reflection_id);
"""

def migrate():
    """Migrate database to v2 schema."""
    print("Starting PCP database migration to v2...")

    # Backup existing
    if os.path.exists(VAULT_PATH):
        backup_path = VAULT_PATH + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.system(f"cp {VAULT_PATH} {backup_path}")
        print(f"Backed up existing database to {backup_path}")

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Create new tables
    cursor.executescript(SCHEMA_V2)
    print("Created v2 schema tables")

    # Migrate existing captures if old table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='captures'")
    if cursor.fetchone():
        print("Migrating existing captures...")
        cursor.execute("""
            INSERT INTO captures_v2 (content, capture_type, tags, status, created_at)
            SELECT content, capture_type, tags, status, created_at
            FROM captures
            WHERE id NOT IN (SELECT id FROM captures_v2)
        """)
        print(f"Migrated {cursor.rowcount} captures")

    # Add relationship fields to people table (Phase 4.1)
    migrate_people_relationship_fields(conn)

    # Add outcome fields to decisions table (Phase 4.2)
    migrate_decision_outcome_fields(conn)

    # Add dependency fields to delegated_tasks (Phase 6)
    migrate_delegated_tasks_dependencies(conn)

    conn.commit()
    conn.close()
    print("Migration complete!")


def migrate_decision_outcome_fields(conn):
    """Add outcome tracking fields to decisions table.

    New fields:
    - outcome: The actual outcome/result of the decision
    - outcome_date: When the outcome was observed
    - outcome_assessment: positive/negative/neutral assessment
    - lessons_learned: What was learned from this decision
    """
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(decisions)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Define new columns to add
    new_columns = [
        ("outcome", "TEXT"),
        ("outcome_date", "TIMESTAMP"),
        ("outcome_assessment", "TEXT"),  # positive/negative/neutral
        ("lessons_learned", "TEXT"),
    ]

    added = []
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE decisions ADD COLUMN {col_name} {col_type}")
                added.append(col_name)
            except sqlite3.OperationalError as e:
                # Column might already exist from a previous partial migration
                if "duplicate column name" not in str(e).lower():
                    raise

    if added:
        print(f"Added outcome fields to decisions: {', '.join(added)}")
    else:
        print("Decision outcome fields already exist")


def migrate_people_relationship_fields(conn):
    """Add relationship tracking fields to people table.

    New fields:
    - last_contacted: When the user last had contact with this person
    - interaction_count: Total number of interactions
    - first_contacted: When the user first contacted them
    - shared_projects: JSON array of project IDs they work on together
    - relationship_notes: Notes about the relationship
    """
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(people)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Define new columns to add
    new_columns = [
        ("last_contacted", "TIMESTAMP"),
        ("interaction_count", "INTEGER DEFAULT 0"),
        ("first_contacted", "TIMESTAMP"),
        ("shared_projects", "TEXT"),  # JSON array of project IDs
        ("relationship_notes", "TEXT"),
    ]

    added = []
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE people ADD COLUMN {col_name} {col_type}")
                added.append(col_name)
            except sqlite3.OperationalError as e:
                # Column might already exist from a previous partial migration
                if "duplicate column name" not in str(e).lower():
                    raise

    if added:
        print(f"Added relationship fields to people: {', '.join(added)}")
    else:
        print("People relationship fields already exist")

    # Create index on last_contacted if not exists
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_people_last_contacted ON people(last_contacted)")
    except sqlite3.OperationalError:
        pass  # Index might already exist

def migrate_delegated_tasks_dependencies(conn):
    """Add dependency tracking fields to delegated_tasks table.

    New fields:
    - depends_on: JSON array of task IDs this task depends on
    - blocks: JSON array of task IDs that depend on this task
    - group_id: Identifier for grouping related tasks
    - subagent: Preferred subagent to handle this task
    - mode: Execution mode (auto/subagent/legacy)
    - subagent_id: Claude Code agentId if executed via subagent
    """
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(delegated_tasks)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Define new columns to add
    new_columns = [
        ("depends_on", "TEXT"),           # JSON array of task IDs
        ("blocks", "TEXT"),               # JSON array of task IDs blocked by this
        ("group_id", "TEXT"),             # Group identifier for related tasks
        ("subagent", "TEXT"),             # Preferred subagent type
        ("mode", "TEXT DEFAULT 'auto'"),  # auto/subagent/legacy
        ("subagent_id", "TEXT"),          # Claude Code agentId for resumption
    ]

    added = []
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE delegated_tasks ADD COLUMN {col_name} {col_type}")
                added.append(col_name)
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise

    if added:
        print(f"Added dependency fields to delegated_tasks: {', '.join(added)}")
    else:
        print("Delegated tasks dependency fields already exist")

    # Create indexes for new columns
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_delegated_tasks_group ON delegated_tasks(group_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_delegated_tasks_subagent ON delegated_tasks(subagent)")
    except sqlite3.OperationalError:
        pass  # Indexes might already exist


def init_default_projects():
    """Initialize default projects based on the user's known work."""
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    projects = [
        {
            "name": "PCP",
            "description": "Personal Control Plane - this system",
            "keywords": json.dumps(["pcp", "personal control plane", "vault", "captures"]),
            "folder_patterns": json.dumps(["/PCP", "/Personal"])
        },
        {
            "name": "Alpha-Trader",
            "description": "Polymarket trading agent",
            "keywords": json.dumps(["trading", "polymarket", "alpha-trader", "positions", "markets"]),
            "folder_patterns": json.dumps(["/Trading", "/Alpha"])
        },
        {
            "name": "MatterStack",
            "description": "Computational chemistry platform",
            "keywords": json.dumps(["matterstack", "chemistry", "molecules", "pipeline", "compounds"]),
            "folder_patterns": json.dumps(["/MatterStack", "/Chemistry"])
        },
        {
            "name": "AgentOps",
            "description": "Homelab infrastructure and agent management",
            "keywords": json.dumps(["agentops", "infrastructure", "docker", "server", "homelab"]),
            "folder_patterns": json.dumps(["/AgentOps", "/Infrastructure"])
        }
    ]

    for p in projects:
        cursor.execute("""
            INSERT OR IGNORE INTO projects (name, description, keywords, folder_patterns)
            VALUES (?, ?, ?, ?)
        """, (p["name"], p["description"], p["keywords"], p["folder_patterns"]))

    conn.commit()
    conn.close()
    print("Initialized default projects")

if __name__ == "__main__":
    migrate()
    init_default_projects()
