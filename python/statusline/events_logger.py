"""Event logging for Claude Code hooks.

Logs events to SQLite as JSON blobs. Fields are extracted at query time
using SQLite's JSON functions (->> operator).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

from statusline.db import get_db_path


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create events_v2 table if missing.

    Schema: (id, ts, session_id, data)
    - ts: Unix timestamp
    - session_id: Claude session identifier
    - data: Full JSON blob from hook
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events_v2 (
            id INTEGER PRIMARY KEY,
            ts INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_v2_session_ts ON events_v2(session_id, ts)"
    )
    conn.commit()


def log_event(data: dict) -> None:
    """Log event to SQLite as JSON.

    Uses BEGIN IMMEDIATE to prevent concurrent write conflicts.
    Fails silently to avoid disrupting Claude Code.
    """
    cwd = data.get("cwd")
    if not cwd:
        return

    session_id = data.get("session_id", "")

    # Inject event name from env var if not in data
    if "hook_event_name" not in data:
        event_name = os.environ.get("CLAUDE_HOOK_EVENT_NAME")
        if event_name:
            data["hook_event_name"] = event_name

    db_path = get_db_path(cwd)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.execute("BEGIN IMMEDIATE")
            ensure_schema(conn)
            conn.execute(
                "INSERT INTO events_v2 (ts, session_id, data) VALUES (?, ?, json(?))",
                (int(time.time()), session_id, json.dumps(data)),
            )
            conn.commit()
    except sqlite3.Error:
        pass  # Silent fail - don't disrupt Claude Code


def log_event_from_stdin() -> None:
    """Entry point for CLI subcommand. Reads JSON from stdin."""
    try:
        data = json.loads(sys.stdin.read())
        log_event(data)
    except (json.JSONDecodeError, KeyError):
        pass  # Silent fail - malformed input shouldn't crash
