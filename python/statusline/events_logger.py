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
    # Migration: replace ASC index with DESC (matches ORDER BY ts DESC queries)
    conn.execute("DROP INDEX IF EXISTS idx_events_v2_session_ts")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_v2_session_ts_desc"
        " ON events_v2(session_id, ts DESC)"
    )
    # Migration: replace v1 trigger with simplified cleanup logic
    conn.execute("DROP TRIGGER IF EXISTS trg_events_v2_cap")
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_events_v2_cap_v2
        AFTER INSERT ON events_v2
        WHEN NEW.id % 100 = 0
        BEGIN
            -- Keep latest 250 events per session
            DELETE FROM events_v2
            WHERE session_id = NEW.session_id
            AND id <= (
                SELECT id FROM events_v2
                WHERE session_id = NEW.session_id
                ORDER BY id DESC
                LIMIT 1 OFFSET 250
            );
            -- Delete events older than 7 days
            DELETE FROM events_v2
            WHERE ts < unixepoch('now', '-7 days');
        END
    """)
    conn.commit()


def log_event(data: dict) -> None:
    """Log event to SQLite as JSON.

    Uses BEGIN IMMEDIATE to prevent concurrent write conflicts.
    Fails silently to avoid disrupting Claude Code.
    """
    transcript_path = data.get("transcript_path")
    if not transcript_path:
        return

    session_id = data.get("session_id", "")

    # Inject event name from env var if not in data
    if "hook_event_name" not in data:
        event_name = os.environ.get("CLAUDE_HOOK_EVENT_NAME")
        if event_name:
            data["hook_event_name"] = event_name

    db_path = get_db_path(transcript_path)

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
