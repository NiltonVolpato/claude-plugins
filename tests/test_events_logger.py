"""Tests for the events logger and provider modules."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
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
            data = {
                "cwd": tmpdir,
                "session_id": "test",
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "echo hello"},
            }
            log_event(data)

            db_path = get_db_path(tmpdir)
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
            evil_session = "test'; DROP TABLE events_v2; --"
            data = {
                "cwd": tmpdir,
                "session_id": evil_session,
                "hook_event_name": "PostToolUse",
            }
            log_event(data)

            db_path = get_db_path(tmpdir)
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
            evil_session = 'test"; DROP TABLE events_v2; --'
            data = {
                "cwd": tmpdir,
                "session_id": evil_session,
                "hook_event_name": "PostToolUse",
            }
            log_event(data)

            db_path = get_db_path(tmpdir)
            conn = sqlite3.connect(db_path)
            # Table should still exist and data preserved
            row = conn.execute(
                "SELECT session_id FROM events_v2"
            ).fetchone()
            assert row[0] == evil_session
            conn.close()

    def test_missing_cwd_is_ignored(self):
        """Events without cwd are silently ignored."""
        data = {
            "session_id": "test",
            "hook_event_name": "PostToolUse",
        }
        # Should not raise
        log_event(data)

    def test_injects_event_name_from_env(self, monkeypatch):
        """Event name is injected from CLAUDE_HOOK_EVENT_NAME env var."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setenv("CLAUDE_HOOK_EVENT_NAME", "Stop")
            data = {
                "cwd": tmpdir,
                "session_id": "test",
            }
            log_event(data)

            db_path = get_db_path(tmpdir)
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT data->>'hook_event_name' FROM events_v2"
            ).fetchone()
            assert row[0] == "Stop"
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
        data = {
            "cwd": tmpdir,
            "session_id": "test",
            "hook_event_name": event_name,
        }
        log_event(data)

        db_path = get_db_path(tmpdir)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT data->>'hook_event_name' FROM events_v2"
        ).fetchone()
        assert row[0] == event_name
        conn.close()


def test_end_to_end_cli():
    """Simulate a hook event via CLI and verify database state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_json = json.dumps(
            {
                "cwd": tmpdir,
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
        db_path = get_db_path(tmpdir)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT data->>'tool_name', data->'tool_input'->>'command' FROM events_v2"
        ).fetchone()
        assert row == ("Bash", "echo hello")
        conn.close()
