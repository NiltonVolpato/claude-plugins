"""Tests for the events logger module."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import pytest

from statusline.db import get_db_path
from statusline.events_logger import extract_extra, log_event


class TestExtractExtra:
    """Tests for extract_extra function."""

    def test_interrupt_detection(self):
        """PostToolUseFailure with is_interrupt returns 'interrupt'."""
        data = {"is_interrupt": True}
        assert extract_extra("PostToolUseFailure", "Bash", data) == "interrupt"

    def test_bash_command_truncation(self):
        """Bash commands are truncated to 200 chars."""
        long_cmd = "x" * 300
        data = {"tool_input": {"command": long_cmd}}
        result = extract_extra("PostToolUse", "Bash", data)
        assert result == "x" * 200

    def test_bash_empty_command(self):
        """Empty bash command returns None."""
        data = {"tool_input": {"command": ""}}
        assert extract_extra("PostToolUse", "Bash", data) is None

    def test_edit_line_counts(self):
        """Edit returns +added-removed format."""
        data = {"tool_input": {"old_string": "a\nb", "new_string": "x\ny\nz"}}
        assert extract_extra("PostToolUse", "Edit", data) == "+3-2"

    def test_write_line_counts(self):
        """Write uses 'content' field instead of 'new_string'."""
        data = {"tool_input": {"content": "line1\nline2\nline3"}}
        assert extract_extra("PostToolUse", "Write", data) == "+3-0"

    def test_none_value(self):
        """Verify None value is handled."""
        assert (
            extract_extra(
                "PostToolUse", "Edit", {"tool_input": {"old_string": None, "new_string": "x"}}
            )
            == "+1-0"
        )

    def test_empty_string(self):
        """Verify empty string is handled."""
        assert (
            extract_extra(
                "PostToolUse", "Edit", {"tool_input": {"old_string": "", "new_string": ""}}
            )
            == "+0-0"
        )

    def test_missing_keys(self):
        """Verify missing keys are handled."""
        assert extract_extra("PostToolUse", "Edit", {"tool_input": {}}) == "+0-0"

    def test_missing_tool_input(self):
        """Verify missing tool_input is handled."""
        assert extract_extra("PostToolUse", "Edit", {}) == "+0-0"

    def test_unknown_tool_returns_none(self):
        """Unknown tools return None for extra."""
        data = {"tool_input": {"some_field": "value"}}
        assert extract_extra("PostToolUse", "Read", data) is None

    def test_non_interrupt_failure(self):
        """PostToolUseFailure without is_interrupt doesn't return 'interrupt'."""
        data = {"is_interrupt": False, "tool_input": {"command": "ls"}}
        assert extract_extra("PostToolUseFailure", "Bash", data) == "ls"


class TestLogEvent:
    """Tests for log_event function."""

    def test_sql_injection_prevented(self):
        """Apostrophes and special chars don't break SQL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            evil_cmd = "echo \"it's working; DROP TABLE events;\""
            data = {
                "cwd": tmpdir,
                "session_id": "test",
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": evil_cmd},
            }
            log_event(data)

            # Verify event was logged with exact command preserved
            db_path = get_db_path(tmpdir)
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT extra FROM events WHERE session_id = 'test'"
            ).fetchone()
            assert row is not None
            assert row[0] == evil_cmd
            conn.close()

    def test_all_fields_stored(self):
        """All event fields are stored correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                "cwd": tmpdir,
                "session_id": "sess-123",
                "hook_event_name": "SubagentStart",
                "tool_name": "",
                "agent_id": "agent-456",
            }
            log_event(data)

            db_path = get_db_path(tmpdir)
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT session_id, event, agent_id FROM events"
            ).fetchone()
            assert row == ("sess-123", "SubagentStart", "agent-456")
            conn.close()

    def test_missing_cwd_is_ignored(self):
        """Events without cwd are silently ignored."""
        data = {
            "session_id": "test",
            "hook_event_name": "PostToolUse",
        }
        # Should not raise
        log_event(data)

    def test_empty_tool_name_stored_as_null(self):
        """Empty tool names are stored as NULL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                "cwd": tmpdir,
                "session_id": "test",
                "hook_event_name": "Stop",
                "tool_name": "",
            }
            log_event(data)

            db_path = get_db_path(tmpdir)
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT tool FROM events").fetchone()
            assert row[0] is None
            conn.close()


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
    """All hook event types are logged correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = {
            "cwd": tmpdir,
            "session_id": "test",
            "hook_event_name": event_name,
        }
        log_event(data)

        db_path = get_db_path(tmpdir)
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT event FROM events").fetchone()
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

        # Verify database
        db_path = get_db_path(tmpdir)
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT event, tool, extra FROM events").fetchone()
        assert row == ("PostToolUse", "Bash", "echo hello")
        conn.close()
