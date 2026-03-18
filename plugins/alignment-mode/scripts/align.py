#!/usr/bin/env python3
"""Alignment mode state management.

State machine per session:
  inactive  --(activate)-->  planning
  planning  --(lgtm)------>  executing
  executing --(stop)------->  planning
  planning  --(activate)-->  planning  (re-entry, stays planning)

In 'planning' state, only read-safe tools are allowed. All other tools
are blocked by the PreToolUse hook.
"""

import json
import os
import re
import sys
from pathlib import Path

# Tools allowed during planning mode (allowlist).
# Everything not in this set is blocked.
ALLOWED_TOOLS_IN_PLANNING = {
    "Read",
    "Grep",
    "Glob",
    "WebFetch",
    "WebSearch",
    "Agent",
    "Skill",
    "ToolSearch",
    "LSP",
    "TodoRead",
    "TaskGet",
    "TaskList",
    "TaskOutput",
}


def get_data_dir() -> Path:
    """Get the plugin data directory from env var."""
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_dir:
        data_dir = os.path.expanduser("~/.claude/plugins/data/alignment-mode")
    return Path(data_dir)


def state_file_for(session_id: str) -> Path:
    return get_data_dir() / "sessions" / session_id


def get_state(session_id: str) -> str:
    path = state_file_for(session_id)
    if path.exists():
        return path.read_text().strip()
    return "inactive"


def set_state(session_id: str, state: str) -> None:
    path = state_file_for(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state)


def output_json(data: dict) -> None:
    json.dump(data, sys.stdout)


def read_hook_input() -> dict:
    return json.loads(sys.stdin.read())


def handle_activate(data_dir: str, session_id: str) -> None:
    """Called from /align skill via !`command`."""
    os.environ.setdefault("CLAUDE_PLUGIN_DATA", data_dir)
    set_state(session_id, "planning")


def handle_lgtm(data_dir: str, session_id: str) -> None:
    """Called from /lgtm skill via !`command`."""
    os.environ.setdefault("CLAUDE_PLUGIN_DATA", data_dir)
    if get_state(session_id) == "planning":
        set_state(session_id, "executing")


def handle_pre_tool_use() -> None:
    """PreToolUse hook: block non-allowlisted tools in planning state."""
    hook_input = read_hook_input()
    session_id = hook_input.get("session_id", "")

    if get_state(session_id) != "planning":
        return  # exit 0, no output = allow

    tool_name = hook_input.get("tool_name", "")
    if tool_name in ALLOWED_TOOLS_IN_PLANNING:
        return  # exit 0, no output = allow

    output_json({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Alignment mode: only read-only tools are allowed during "
                "planning. Present your understanding and plan to the user. "
                "The user will say LGTM or run /lgtm when ready."
            ),
        }
    })


def handle_user_prompt() -> None:
    """UserPromptSubmit hook: detect LGTM to unlock execution."""
    hook_input = read_hook_input()
    session_id = hook_input.get("session_id", "")

    if get_state(session_id) != "planning":
        return

    prompt = hook_input.get("prompt", "").strip()
    if re.match(r"^lgtm[!.]*$", prompt, re.IGNORECASE):
        set_state(session_id, "executing")
        output_json({
            "systemMessage": (
                "Alignment mode: plan approved! All tools are now unlocked. "
                "Execute the plan you presented."
            )
        })


def handle_stop() -> None:
    """Stop hook: return to planning after execution finishes."""
    hook_input = read_hook_input()
    session_id = hook_input.get("session_id", "")

    if get_state(session_id) == "executing":
        set_state(session_id, "planning")
        output_json({
            "systemMessage": (
                "Alignment mode: execution complete. Only read-only tools are "
                "allowed again. Present any new plans before executing."
            )
        })


def main() -> None:
    action = sys.argv[1]

    if action == "activate":
        handle_activate(data_dir=sys.argv[2], session_id=sys.argv[3])
    elif action == "lgtm":
        handle_lgtm(data_dir=sys.argv[2], session_id=sys.argv[3])
    elif action == "pre-tool-use":
        handle_pre_tool_use()
    elif action == "user-prompt":
        handle_user_prompt()
    elif action == "stop":
        handle_stop()
    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
