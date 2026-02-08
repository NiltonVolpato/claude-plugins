"""Event logging for Claude Code hooks.

Logs events to SQLite with parameterized queries (no SQL injection).
Schema is compatible with the original shell hook for backward compatibility.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

from statusline.db import get_db_path


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if missing.

    NOTE: Schema matches the original shell hook for compatibility:
    - events: (id, ts, session_id, event, tool, agent_id, extra)
    - idx_session_ts: index on (session_id, ts)

    The shell hook also created a debug_log table which we don't need.
    Existing debug_log tables are left in place (no harm).
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            ts INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            event TEXT NOT NULL,
            tool TEXT,
            agent_id TEXT,
            extra TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session_ts ON events(session_id, ts)")
    conn.commit()


def extract_extra(event_name: str, tool_name: str, data: dict) -> str | None:
    """Extract context-specific extra info.

    Returns:
        - "interrupt" for PostToolUseFailure with is_interrupt=True
        - First 200 chars of command for Bash
        - "+added-removed" line counts for Edit/Write
        - None otherwise
    """
    if event_name == "PostToolUseFailure" and data.get("is_interrupt"):
        return "interrupt"

    tool_input = data.get("tool_input") or {}

    if tool_name == "Bash":
        cmd = tool_input.get("command") or ""
        return cmd[:200] if cmd else None

    if tool_name in ("Edit", "Write"):
        # Handle None, empty string, and missing keys uniformly
        old = tool_input.get("old_string") or ""
        new = tool_input.get("new_string") or tool_input.get("content") or ""
        # Count lines: empty string = 0 lines, non-empty = newlines + 1
        old_lines = (old.count("\n") + 1) if old else 0
        new_lines = (new.count("\n") + 1) if new else 0
        return f"+{new_lines}-{old_lines}"

    return None


def log_event(data: dict) -> None:
    """Log event to SQLite with parameterized queries (no SQL injection).

    Uses BEGIN IMMEDIATE to prevent concurrent write conflicts.
    Fails silently to avoid disrupting Claude Code.
    """
    cwd = data.get("cwd")
    if not cwd:
        return

    # Event name from env var (preferred) or JSON field
    session_id = data.get("session_id", "")
    event_name = os.environ.get("CLAUDE_HOOK_EVENT_NAME") or data.get(
        "hook_event_name", ""
    )
    tool_name = data.get("tool_name") or ""
    agent_id = data.get("agent_id") or ""
    extra = extract_extra(event_name, tool_name, data)

    db_path = get_db_path(cwd)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.execute("BEGIN IMMEDIATE")
            ensure_schema(conn)
            conn.execute(
                "INSERT INTO events (ts, session_id, event, tool, agent_id, extra) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(time.time()),
                    session_id,
                    event_name,
                    tool_name or None,
                    agent_id or None,
                    extra,
                ),
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
