"""Tests for the events logger and provider modules."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from statusline.db import get_db_path
from statusline.events_logger import log_event
from statusline.providers import EventsInfoProvider


class TestLogEvent:
    """Tests for log_event function (writes to events_v2)."""

    def test_stores_full_json(self):
        """Event data is stored as JSON in events_v2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = f"{tmpdir}/session.jsonl"
            data = {
                "transcript_path": transcript_path,
                "session_id": "test",
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "echo hello"},
            }
            log_event(data)

            db_path = get_db_path(transcript_path)
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT data FROM events_v2 WHERE session_id = 'test'"
            ).fetchone()
            assert row is not None
            stored = json.loads(row[0])
            assert stored["tool_name"] == "Bash"
            assert stored["tool_input"]["command"] == "echo hello"
            conn.close()

    def test_sql_injection_single_quote(self):
        """Single quote SQL injection attempt is safely stored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = f"{tmpdir}/session.jsonl"
            evil_session = "test'; DROP TABLE events_v2; --"
            data = {
                "transcript_path": transcript_path,
                "session_id": evil_session,
                "hook_event_name": "PostToolUse",
            }
            log_event(data)

            db_path = get_db_path(transcript_path)
            conn = sqlite3.connect(db_path)
            # Table should still exist and data preserved
            row = conn.execute(
                "SELECT session_id FROM events_v2"
            ).fetchone()
            assert row[0] == evil_session
            conn.close()

    def test_sql_injection_double_quote(self):
        """Double quote SQL injection attempt is safely stored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = f"{tmpdir}/session.jsonl"
            evil_session = 'test"; DROP TABLE events_v2; --'
            data = {
                "transcript_path": transcript_path,
                "session_id": evil_session,
                "hook_event_name": "PostToolUse",
            }
            log_event(data)

            db_path = get_db_path(transcript_path)
            conn = sqlite3.connect(db_path)
            # Table should still exist and data preserved
            row = conn.execute(
                "SELECT session_id FROM events_v2"
            ).fetchone()
            assert row[0] == evil_session
            conn.close()

    def test_missing_transcript_path_is_ignored(self):
        """Events without transcript_path are silently ignored."""
        data = {
            "session_id": "test",
            "hook_event_name": "PostToolUse",
        }
        # Should not raise
        log_event(data)

    def test_injects_event_name_from_env(self, monkeypatch):
        """Event name is injected from CLAUDE_HOOK_EVENT_NAME env var."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = f"{tmpdir}/session.jsonl"
            monkeypatch.setenv("CLAUDE_HOOK_EVENT_NAME", "Stop")
            data = {
                "transcript_path": transcript_path,
                "session_id": "test",
            }
            log_event(data)

            db_path = get_db_path(transcript_path)
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT data->>'hook_event_name' FROM events_v2"
            ).fetchone()
            assert row[0] == "Stop"
            conn.close()


class TestEventsCap:
    """Tests for the events_v2 table size cap trigger.

    The trigger fires every 100 inserts (WHEN NEW.id % 100 = 0) and:
    1. Keeps latest 250 events per session (for the inserting session)
    2. Deletes any event older than 7 days
    """

    NOW = int(time.time())

    def _insert_events(self, conn, count, session_id="test", ts=None):
        """Insert multiple events directly into the database."""
        if ts is None:
            ts = self.NOW
        for i in range(count):
            conn.execute(
                "INSERT INTO events_v2 (ts, session_id, data) VALUES (?, ?, json(?))",
                (ts, session_id, json.dumps({"hook_event_name": "PostToolUse", "n": i})),
            )
        conn.commit()

    def _setup_db(self, tmpdir, session_id="test"):
        """Create the DB with schema via log_event, return (db_path, conn)."""
        transcript_path = f"{tmpdir}/session.jsonl"
        log_event({
            "transcript_path": transcript_path,
            "session_id": session_id,
            "hook_event_name": "PostToolUse",
        })
        db_path = get_db_path(transcript_path)
        conn = sqlite3.connect(db_path)
        return db_path, conn

    def test_trigger_exists(self):
        """The cap trigger is created during schema setup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, conn = self._setup_db(tmpdir)
            triggers = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
            assert ("trg_events_v2_cap_v2",) in triggers
            conn.close()

    def test_per_session_cap(self):
        """Trigger prunes a session to 250 rows when it exceeds the cap."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, conn = self._setup_db(tmpdir)
            # 1 from log_event + 299 = 300 total, trigger fires at rowid 300
            self._insert_events(conn, 299)

            count = conn.execute("SELECT COUNT(*) FROM events_v2").fetchone()[0]
            assert count == 250
            conn.close()

    def test_under_250_no_pruning(self):
        """No rows are deleted when session has fewer than 250 rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, conn = self._setup_db(tmpdir)
            # 1 + 99 = 100 total, trigger fires at rowid 100 but nothing to prune
            self._insert_events(conn, 99)

            count = conn.execute("SELECT COUNT(*) FROM events_v2").fetchone()[0]
            assert count == 100
            conn.close()

    def test_keeps_newest_rows(self):
        """After pruning, the newest 250 rows are retained."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, conn = self._setup_db(tmpdir)
            self._insert_events(conn, 299)

            newest_n = conn.execute(
                "SELECT data->>'n' FROM events_v2 ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
            assert int(newest_n) == 298  # Last inserted

            count = conn.execute("SELECT COUNT(*) FROM events_v2").fetchone()[0]
            assert count == 250
            conn.close()

    def test_sessions_capped_independently(self):
        """Each session is capped at 250 independently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, conn = self._setup_db(tmpdir, session_id="session-a")
            # session-a: 1 (from log_event) + 299 = 300
            self._insert_events(conn, 299, session_id="session-a")
            # session-b: 300
            self._insert_events(conn, 300, session_id="session-b")

            count_a = conn.execute(
                "SELECT COUNT(*) FROM events_v2 WHERE session_id = 'session-a'"
            ).fetchone()[0]
            count_b = conn.execute(
                "SELECT COUNT(*) FROM events_v2 WHERE session_id = 'session-b'"
            ).fetchone()[0]
            assert count_a == 250
            assert count_b == 250
            conn.close()

    def test_other_session_not_pruned_by_cap(self):
        """Per-session cap only prunes the inserting session, not others."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, conn = self._setup_db(tmpdir, session_id="session-a")
            # session-a: 1 + 149 = 150 (under cap)
            self._insert_events(conn, 149, session_id="session-a")
            # session-b: 150 events, trigger fires at rowid 300
            self._insert_events(conn, 150, session_id="session-b")

            count_a = conn.execute(
                "SELECT COUNT(*) FROM events_v2 WHERE session_id = 'session-a'"
            ).fetchone()[0]
            count_b = conn.execute(
                "SELECT COUNT(*) FROM events_v2 WHERE session_id = 'session-b'"
            ).fetchone()[0]
            # Both under 250, nothing pruned
            assert count_a == 150
            assert count_b == 150
            conn.close()

    def test_old_events_pruned(self):
        """Events older than 7 days are deleted, regardless of session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, conn = self._setup_db(tmpdir, session_id="active")
            eight_days_ago = self.NOW - 8 * 86400
            self._insert_events(conn, 50, session_id="stale", ts=eight_days_ago)
            # Fill up to trigger: 1 (log_event) + 50 (stale) + 49 (active) = 100
            self._insert_events(conn, 49, session_id="active")

            stale_count = conn.execute(
                "SELECT COUNT(*) FROM events_v2 WHERE session_id = 'stale'"
            ).fetchone()[0]
            assert stale_count == 0

            active_count = conn.execute(
                "SELECT COUNT(*) FROM events_v2 WHERE session_id = 'active'"
            ).fetchone()[0]
            assert active_count == 50  # 1 + 49
            conn.close()

    def test_recent_events_not_pruned(self):
        """Events within 7 days are not deleted by the age check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, conn = self._setup_db(tmpdir, session_id="active")
            six_days_ago = self.NOW - 6 * 86400
            self._insert_events(conn, 50, session_id="recent", ts=six_days_ago)
            # 1 + 50 + 49 = 100, triggers cleanup
            self._insert_events(conn, 49, session_id="active")

            recent_count = conn.execute(
                "SELECT COUNT(*) FROM events_v2 WHERE session_id = 'recent'"
            ).fetchone()[0]
            assert recent_count == 50  # Not pruned
            conn.close()


class TestComputeExtra:
    """Tests for _compute_extra in EventsInfoProvider."""

    @pytest.fixture
    def provider(self):
        return EventsInfoProvider()

    def test_interrupt_detection(self, provider):
        """PostToolUseFailure with is_interrupt returns 'interrupt'."""
        data = {"is_interrupt": True}
        assert provider._compute_extra("PostToolUseFailure", "Bash", data) == "interrupt"

    def test_bash_command_truncation(self, provider):
        """Bash commands are truncated to 200 chars."""
        long_cmd = "x" * 300
        data = {"tool_input": {"command": long_cmd}}
        result = provider._compute_extra("PostToolUse", "Bash", data)
        assert result == "x" * 200

    def test_bash_empty_command(self, provider):
        """Empty bash command returns None."""
        data = {"tool_input": {"command": ""}}
        assert provider._compute_extra("PostToolUse", "Bash", data) is None

    def test_edit_line_counts(self, provider):
        """Edit returns +added-removed format."""
        data = {"tool_input": {"old_string": "a\nb", "new_string": "x\ny\nz"}}
        assert provider._compute_extra("PostToolUse", "Edit", data) == "+3-2"

    def test_unknown_tool_returns_none(self, provider):
        """Unknown tools return None for extra."""
        data = {"tool_input": {"some_field": "value"}}
        assert provider._compute_extra("PostToolUse", "Read", data) is None


@pytest.mark.parametrize(
    "event_name",
    [
        "PostToolUse",
        "PostToolUseFailure",
        "UserPromptSubmit",
        "Stop",
        "SubagentStart",
        "SubagentStop",
    ],
)
def test_all_event_types(event_name):
    """All hook event types are logged and queryable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        transcript_path = f"{tmpdir}/session.jsonl"
        data = {
            "transcript_path": transcript_path,
            "session_id": "test",
            "hook_event_name": event_name,
        }
        log_event(data)

        db_path = get_db_path(transcript_path)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT data->>'hook_event_name' FROM events_v2"
        ).fetchone()
        assert row[0] == event_name
        conn.close()


def test_end_to_end_cli():
    """Simulate a hook event via CLI and verify database state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        transcript_path = f"{tmpdir}/session.jsonl"
        input_json = json.dumps(
            {
                "transcript_path": transcript_path,
                "session_id": "test-session",
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "echo hello"},
            }
        )

        result = subprocess.run(
            ["uv", "run", "statusline", "log-event"],
            input=input_json,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0

        # Verify JSON storage
        db_path = get_db_path(transcript_path)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT data->>'tool_name', data->'tool_input'->>'command' FROM events_v2"
        ).fetchone()
        assert row == ("Bash", "echo hello")
        conn.close()
