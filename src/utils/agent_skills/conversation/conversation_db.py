"""
Tool: Conversation History Database
Purpose: SQLite CRUD for verbatim conversation history ingested from Claude Code JSONL transcripts

Schema:
    - sessions: per-session metadata (slug, branch, timestamps, message count)
    - messages: verbatim user/assistant text (UUID-deduped)
    - messages_fts: FTS5 virtual table for full-text search
    - ingest_state: per-file ingestion tracking (size + mtime for skip logic)

Usage:
    Imported by conversation_ingest.py and conversation_read.py.
    Not intended for direct CLI use.

Dependencies:
    - sqlite3 (stdlib)
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Database path
DB_PATH = (Path(__file__).parent.parent.parent.parent.parent / "database" / "conversation_history.db").resolve()


def get_connection():
    """Get database connection, creating tables if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    cursor = conn.cursor()

    # Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            slug TEXT,
            source_file TEXT,
            git_branch TEXT,
            first_message_at TEXT,
            last_message_at TEXT,
            message_count INTEGER DEFAULT 0,
            ingested_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    ''')

    # Messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            uuid TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            parent_uuid TEXT,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            git_branch TEXT,
            sequence_num INTEGER,
            ingested_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    ''')

    # FTS5 virtual table
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            content,
            role,
            content='messages',
            content_rowid='rowid'
        )
    ''')

    # Triggers to keep FTS in sync
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, content, role)
            VALUES (new.rowid, new.content, new.role);
        END
    ''')
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content, role)
            VALUES ('delete', old.rowid, old.content, old.role);
        END
    ''')
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content, role)
            VALUES ('delete', old.rowid, old.content, old.role);
            INSERT INTO messages_fts(rowid, content, role)
            VALUES (new.rowid, new.content, new.role);
        END
    ''')

    # Ingest state tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ingest_state (
            file_name TEXT PRIMARY KEY,
            file_size INTEGER,
            file_mtime REAL,
            lines_processed INTEGER,
            last_ingested_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_sequence ON messages(session_id, sequence_num)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_slug ON sessions(slug)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_first_msg ON sessions(first_message_at)')

    conn.commit()
    return conn


def row_to_dict(row) -> Optional[Dict]:
    """Convert sqlite3.Row to dictionary."""
    if row is None:
        return None
    return dict(row)


def upsert_session(
    conn,
    session_id: str,
    slug: Optional[str] = None,
    source_file: Optional[str] = None,
    git_branch: Optional[str] = None,
    first_message_at: Optional[str] = None,
    last_message_at: Optional[str] = None,
    message_count: int = 0
):
    """Insert or update session metadata."""
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    conn.execute('''
        INSERT INTO sessions (session_id, slug, source_file, git_branch,
                              first_message_at, last_message_at, message_count,
                              ingested_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            slug = COALESCE(excluded.slug, sessions.slug),
            source_file = COALESCE(excluded.source_file, sessions.source_file),
            git_branch = COALESCE(excluded.git_branch, sessions.git_branch),
            first_message_at = MIN(COALESCE(excluded.first_message_at, sessions.first_message_at),
                                   COALESCE(sessions.first_message_at, excluded.first_message_at)),
            last_message_at = MAX(COALESCE(excluded.last_message_at, sessions.last_message_at),
                                  COALESCE(sessions.last_message_at, excluded.last_message_at)),
            message_count = excluded.message_count,
            updated_at = excluded.updated_at
    ''', (session_id, slug, source_file, git_branch,
          first_message_at, last_message_at, message_count, now, now))


def insert_message(
    conn,
    uuid: str,
    session_id: str,
    role: str,
    content: str,
    timestamp: str,
    parent_uuid: Optional[str] = None,
    git_branch: Optional[str] = None,
    sequence_num: Optional[int] = None
) -> bool:
    """Insert a message, ignoring duplicates. Returns True if inserted."""
    try:
        conn.execute('''
            INSERT OR IGNORE INTO messages
            (uuid, session_id, parent_uuid, role, content, timestamp, git_branch, sequence_num)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (uuid, session_id, parent_uuid, role, content, timestamp, git_branch, sequence_num))
        return conn.total_changes > 0
    except sqlite3.IntegrityError:
        return False


def get_session(conn, session_id: str) -> Optional[Dict]:
    """Get a single session by ID."""
    cursor = conn.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
    return row_to_dict(cursor.fetchone())


def list_sessions(
    conn,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None
) -> List[Dict]:
    """List sessions, optionally filtering by slug search."""
    if search:
        cursor = conn.execute('''
            SELECT * FROM sessions
            WHERE slug LIKE ? OR session_id LIKE ?
            ORDER BY first_message_at DESC
            LIMIT ? OFFSET ?
        ''', (f'%{search}%', f'%{search}%', limit, offset))
    else:
        cursor = conn.execute('''
            SELECT * FROM sessions
            ORDER BY first_message_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
    return [row_to_dict(row) for row in cursor.fetchall()]


def get_session_messages(
    conn,
    session_id: str,
    role: Optional[str] = None
) -> List[Dict]:
    """Fetch messages for a session, ordered by sequence_num."""
    if role:
        cursor = conn.execute('''
            SELECT * FROM messages
            WHERE session_id = ? AND role = ?
            ORDER BY sequence_num, timestamp
        ''', (session_id, role))
    else:
        cursor = conn.execute('''
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY sequence_num, timestamp
        ''', (session_id,))
    return [row_to_dict(row) for row in cursor.fetchall()]


def search_messages(
    conn,
    query: str,
    session_id: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """Full-text search across messages using FTS5."""
    # Build FTS query — quote terms for safety
    fts_query = ' '.join(f'"{w}"' for w in query.split())

    if session_id and role:
        cursor = conn.execute('''
            SELECT m.*, snippet(messages_fts, 0, '>>>', '<<<', '...', 40) as snippet
            FROM messages m
            JOIN messages_fts fts ON m.rowid = fts.rowid
            WHERE messages_fts MATCH ?
              AND m.session_id = ?
              AND m.role = ?
            ORDER BY rank
            LIMIT ?
        ''', (fts_query, session_id, role, limit))
    elif session_id:
        cursor = conn.execute('''
            SELECT m.*, snippet(messages_fts, 0, '>>>', '<<<', '...', 40) as snippet
            FROM messages m
            JOIN messages_fts fts ON m.rowid = fts.rowid
            WHERE messages_fts MATCH ?
              AND m.session_id = ?
            ORDER BY rank
            LIMIT ?
        ''', (fts_query, session_id, limit))
    elif role:
        cursor = conn.execute('''
            SELECT m.*, snippet(messages_fts, 0, '>>>', '<<<', '...', 40) as snippet
            FROM messages m
            JOIN messages_fts fts ON m.rowid = fts.rowid
            WHERE messages_fts MATCH ?
              AND m.role = ?
            ORDER BY rank
            LIMIT ?
        ''', (fts_query, role, limit))
    else:
        cursor = conn.execute('''
            SELECT m.*, snippet(messages_fts, 0, '>>>', '<<<', '...', 40) as snippet
            FROM messages m
            JOIN messages_fts fts ON m.rowid = fts.rowid
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        ''', (fts_query, limit))

    return [row_to_dict(row) for row in cursor.fetchall()]


def get_ingest_state(conn, file_name: str) -> Optional[Dict]:
    """Get ingestion state for a file."""
    cursor = conn.execute('SELECT * FROM ingest_state WHERE file_name = ?', (file_name,))
    return row_to_dict(cursor.fetchone())


def set_ingest_state(conn, file_name: str, file_size: int, file_mtime: float, lines_processed: int):
    """Update ingestion state for a file."""
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    conn.execute('''
        INSERT INTO ingest_state (file_name, file_size, file_mtime, lines_processed, last_ingested_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(file_name) DO UPDATE SET
            file_size = excluded.file_size,
            file_mtime = excluded.file_mtime,
            lines_processed = excluded.lines_processed,
            last_ingested_at = excluded.last_ingested_at
    ''', (file_name, file_size, file_mtime, lines_processed, now))


def get_stats(conn) -> Dict[str, Any]:
    """Get database statistics."""
    stats = {}

    cursor = conn.execute('SELECT COUNT(*) as c FROM sessions')
    stats['total_sessions'] = cursor.fetchone()['c']

    cursor = conn.execute('SELECT COUNT(*) as c FROM messages')
    stats['total_messages'] = cursor.fetchone()['c']

    cursor = conn.execute('SELECT COUNT(*) as c FROM messages WHERE role = "user"')
    stats['user_messages'] = cursor.fetchone()['c']

    cursor = conn.execute('SELECT COUNT(*) as c FROM messages WHERE role = "assistant"')
    stats['assistant_messages'] = cursor.fetchone()['c']

    cursor = conn.execute('SELECT MIN(first_message_at) as earliest, MAX(last_message_at) as latest FROM sessions')
    row = cursor.fetchone()
    stats['earliest_session'] = row['earliest']
    stats['latest_session'] = row['latest']

    cursor = conn.execute('SELECT COUNT(*) as c FROM ingest_state')
    stats['files_ingested'] = cursor.fetchone()['c']

    # DB file size
    if DB_PATH.exists():
        stats['db_size_mb'] = round(DB_PATH.stat().st_size / (1024 * 1024), 2)

    return stats
