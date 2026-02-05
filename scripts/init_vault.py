#!/usr/bin/env python3
"""Initialize PCP vault database."""
import sqlite3
from pathlib import Path

VAULT_PATH = Path(os.path.join(os.environ.get("PCP_DIR", "/workspace"), "vault/vault.db"))


def init_db():
    """Initialize the vault database with required tables."""
    VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(VAULT_PATH)
    c = conn.cursor()

    # Captures: notes, tasks, ideas
    c.execute('''
        CREATE TABLE IF NOT EXISTS captures (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            capture_type TEXT DEFAULT 'note',
            tags TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Entities: people, projects, concepts
    c.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Artifacts: briefs, summaries
    c.execute('''
        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            artifact_type TEXT NOT NULL,
            title TEXT,
            content TEXT NOT NULL,
            source_ids TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Indexes for performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_captures_type ON captures(capture_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_captures_created ON captures(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_captures_status ON captures(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(artifact_type)')

    conn.commit()
    conn.close()
    print(f"Vault initialized at {VAULT_PATH}")


if __name__ == "__main__":
    init_db()
