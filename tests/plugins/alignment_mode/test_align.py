"""Tests for the alignment-mode plugin state management script."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parent.parent.parent.parent
    / "plugins"
    / "alignment-mode"
    / "scripts"
    / "align.py"
)


@pytest.fixture
def data_dir(tmp_path):
    """Create a temporary data directory for test state files."""
    return str(tmp_path / "align-data")


def run_align(action, *, stdin_data=None, data_dir=None, extra_args=None):
    """Run align.py with the given action and return (stdout, stderr, returncode)."""
    cmd = [sys.executable, str(SCRIPT), action]
    if extra_args:
        cmd.extend(extra_args)
    env = None
    if data_dir:
        env = {**os.environ, "CLAUDE_PLUGIN_DATA": data_dir}
    result = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout, result.stderr, result.returncode


def make_hook_input(session_id="test-session", **kwargs):
    """Create a JSON hook input string."""
    data = {"session_id": session_id, **kwargs}
    return json.dumps(data)


class TestActivate:
    def test_creates_planning_state(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        state_file = Path(data_dir) / "sessions" / "sess-1"
        assert state_file.read_text() == "planning"

    def test_overwrites_existing_state(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        state_file = Path(data_dir) / "sessions" / "sess-1"
        state_file.write_text("executing")
        run_align("activate", extra_args=[data_dir, "sess-1"])
        assert state_file.read_text() == "planning"

    def test_multiple_sessions(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        run_align("activate", extra_args=[data_dir, "sess-2"])
        assert (Path(data_dir) / "sessions" / "sess-1").read_text() == "planning"
        assert (Path(data_dir) / "sessions" / "sess-2").read_text() == "planning"


class TestLgtm:
    def test_transitions_planning_to_executing(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        run_align("lgtm", extra_args=[data_dir, "sess-1"])
        state_file = Path(data_dir) / "sessions" / "sess-1"
        assert state_file.read_text() == "executing"

    def test_noop_when_inactive(self, data_dir):
        run_align("lgtm", extra_args=[data_dir, "sess-1"])
        state_file = Path(data_dir) / "sessions" / "sess-1"
        assert not state_file.exists()

    def test_noop_when_already_executing(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        run_align("lgtm", extra_args=[data_dir, "sess-1"])
        run_align("lgtm", extra_args=[data_dir, "sess-1"])
        state_file = Path(data_dir) / "sessions" / "sess-1"
        assert state_file.read_text() == "executing"


class TestPreToolUse:
    def test_blocks_write_tools_when_planning(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        for tool in ["Bash", "Write", "Edit", "NotebookEdit"]:
            stdin = make_hook_input(session_id="sess-1", tool_name=tool, tool_input={})
            stdout, _, rc = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
            assert rc == 0
            result = json.loads(stdout)
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny", (
                f"Expected {tool} to be denied in planning state"
            )

    def test_blocks_mcp_tools_when_planning(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(
            session_id="sess-1", tool_name="mcp__server__write_file", tool_input={}
        )
        stdout, _, rc = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
        assert rc == 0
        result = json.loads(stdout)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_allows_read_tools_when_planning(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        for tool in ["Read", "Grep", "Glob", "WebFetch", "WebSearch", "Agent",
                      "Skill", "ToolSearch", "LSP", "TodoRead", "TaskGet",
                      "TaskList", "TaskOutput"]:
            stdin = make_hook_input(session_id="sess-1", tool_name=tool, tool_input={})
            stdout, _, rc = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
            assert rc == 0
            assert stdout == "", f"Expected {tool} to be allowed in planning state"

    def test_allows_when_inactive(self, data_dir):
        stdin = make_hook_input(session_id="sess-1", tool_name="Bash", tool_input={})
        stdout, _, rc = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
        assert rc == 0
        assert stdout == ""

    def test_allows_when_executing(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        run_align("lgtm", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-1", tool_name="Write", tool_input={})
        stdout, _, rc = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
        assert rc == 0
        assert stdout == ""

    def test_different_sessions_independent(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-2", tool_name="Bash", tool_input={})
        stdout, _, _ = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
        assert stdout == ""


class TestUserPrompt:
    def test_lgtm_transitions_to_executing(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-1", prompt="LGTM")
        stdout, _, rc = run_align("user-prompt", stdin_data=stdin, data_dir=data_dir)
        assert rc == 0
        result = json.loads(stdout)
        assert "approved" in result["systemMessage"]
        state = (Path(data_dir) / "sessions" / "sess-1").read_text()
        assert state == "executing"

    def test_lgtm_case_insensitive(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-1", prompt="lgtm")
        stdout, _, _ = run_align("user-prompt", stdin_data=stdin, data_dir=data_dir)
        assert json.loads(stdout)["systemMessage"]

    def test_lgtm_with_punctuation(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-1", prompt="LGTM!")
        stdout, _, _ = run_align("user-prompt", stdin_data=stdin, data_dir=data_dir)
        assert json.loads(stdout)["systemMessage"]

    def test_lgtm_with_whitespace(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-1", prompt="  LGTM  ")
        stdout, _, _ = run_align("user-prompt", stdin_data=stdin, data_dir=data_dir)
        assert json.loads(stdout)["systemMessage"]

    def test_no_match_when_lgtm_in_longer_text(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-1", prompt="LGTM but fix the tests first")
        stdout, _, _ = run_align("user-prompt", stdin_data=stdin, data_dir=data_dir)
        assert stdout == ""
        state = (Path(data_dir) / "sessions" / "sess-1").read_text()
        assert state == "planning"

    def test_noop_when_inactive(self, data_dir):
        stdin = make_hook_input(session_id="sess-1", prompt="LGTM")
        stdout, _, _ = run_align("user-prompt", stdin_data=stdin, data_dir=data_dir)
        assert stdout == ""

    def test_noop_when_executing(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        run_align("lgtm", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-1", prompt="LGTM")
        stdout, _, _ = run_align("user-prompt", stdin_data=stdin, data_dir=data_dir)
        assert stdout == ""


class TestStop:
    def test_transitions_executing_to_planning(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        run_align("lgtm", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-1")
        stdout, _, rc = run_align("stop", stdin_data=stdin, data_dir=data_dir)
        assert rc == 0
        result = json.loads(stdout)
        assert "read-only" in result["systemMessage"]
        state = (Path(data_dir) / "sessions" / "sess-1").read_text()
        assert state == "planning"

    def test_noop_when_planning(self, data_dir):
        run_align("activate", extra_args=[data_dir, "sess-1"])
        stdin = make_hook_input(session_id="sess-1")
        stdout, _, _ = run_align("stop", stdin_data=stdin, data_dir=data_dir)
        assert stdout == ""
        state = (Path(data_dir) / "sessions" / "sess-1").read_text()
        assert state == "planning"

    def test_noop_when_inactive(self, data_dir):
        stdin = make_hook_input(session_id="sess-1")
        stdout, _, _ = run_align("stop", stdin_data=stdin, data_dir=data_dir)
        assert stdout == ""


class TestFullLifecycle:
    def test_plan_approve_execute_cycle(self, data_dir):
        sid = "lifecycle-test"

        # 1. Activate alignment mode
        run_align("activate", extra_args=[data_dir, sid])
        assert (Path(data_dir) / "sessions" / sid).read_text() == "planning"

        # 2. Write tool should be blocked
        stdin = make_hook_input(session_id=sid, tool_name="Write", tool_input={})
        stdout, _, _ = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
        assert json.loads(stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

        # 3. Read tool should be allowed
        stdin = make_hook_input(session_id=sid, tool_name="Read", tool_input={})
        stdout, _, _ = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
        assert stdout == ""

        # 4. User says LGTM
        stdin = make_hook_input(session_id=sid, prompt="lgtm")
        stdout, _, _ = run_align("user-prompt", stdin_data=stdin, data_dir=data_dir)
        assert "approved" in json.loads(stdout)["systemMessage"]

        # 5. Write tool should now be allowed
        stdin = make_hook_input(session_id=sid, tool_name="Write", tool_input={})
        stdout, _, _ = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
        assert stdout == ""

        # 6. Agent stops → back to planning
        stdin = make_hook_input(session_id=sid)
        stdout, _, _ = run_align("stop", stdin_data=stdin, data_dir=data_dir)
        assert "read-only" in json.loads(stdout)["systemMessage"]

        # 7. Write tool blocked again
        stdin = make_hook_input(session_id=sid, tool_name="Edit", tool_input={})
        stdout, _, _ = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
        assert json.loads(stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_multiple_cycles(self, data_dir):
        sid = "multi-cycle"

        for _ in range(3):
            run_align("activate", extra_args=[data_dir, sid])
            # Blocked
            stdin = make_hook_input(session_id=sid, tool_name="Bash", tool_input={})
            stdout, _, _ = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
            assert json.loads(stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
            # Approve
            run_align("lgtm", extra_args=[data_dir, sid])
            # Allowed
            stdout, _, _ = run_align("pre-tool-use", stdin_data=stdin, data_dir=data_dir)
            assert stdout == ""
            # Stop → planning
            stdin_stop = make_hook_input(session_id=sid)
            run_align("stop", stdin_data=stdin_stop, data_dir=data_dir)
