"""SQLite database layer for Star Office UI.

Provides connection management, schema initialization, and helpers.
Uses WAL mode for better concurrent read performance.
"""

import sqlite3
import os
import threading

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "star-office.db")

_local = threading.local()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','working','complete')),
    assigned_agent_id TEXT,
    department_id INTEGER REFERENCES departments(id),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT NOT NULL,
    action TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    description TEXT DEFAULT '',
    source TEXT DEFAULT 'local',
    path TEXT,
    last_scanned_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    UNIQUE(agent_id, skill_name)
);

CREATE TABLE IF NOT EXISTS security_settings (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    port_scan_enabled INTEGER DEFAULT 1,
    port_scan_interval_hours INTEGER DEFAULT 6,
    prompt_guard_enabled INTEGER DEFAULT 0,
    prompt_guard_api_key TEXT DEFAULT '',
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS port_scan_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    port INTEGER NOT NULL,
    service TEXT DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('open','closed','filtered')),
    risk_level TEXT DEFAULT 'safe' CHECK(risk_level IN ('safe','low','medium','high')),
    scanned_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prompt_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_path TEXT,
    request_method TEXT,
    prompt_text TEXT,
    risk_level TEXT DEFAULT 'safe' CHECK(risk_level IN ('safe','low','medium','high','critical')),
    confidence REAL DEFAULT 0.0,
    blocked INTEGER DEFAULT 0,
    api_available INTEGER DEFAULT 1,
    evaluated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    date TEXT NOT NULL,
    conversations INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    token_usage INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    praises INTEGER DEFAULT 0,
    task_completions INTEGER DEFAULT 0,
    UNIQUE(agent_id, date)
);

CREATE TABLE IF NOT EXISTS token_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    model TEXT DEFAULT '',
    logged_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS office_layout (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    layout_data TEXT DEFAULT '{}',
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

# Seed data: insert default security settings row if missing
SEED_SQL = """
INSERT OR IGNORE INTO security_settings (id) VALUES (1);
"""


def get_db():
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def close_db():
    """Close the thread-local connection (call at request teardown)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    db = get_db()
    db.executescript(SCHEMA_SQL)
    db.executescript(SEED_SQL)
    db.commit()
    print(f"[database] SQLite initialized: {DB_PATH}")


def dict_from_row(row):
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)
