"""Git module - displays git repository status."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from statusline.modules import Module, register
from statusline.templates import render_template

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


def _parse_git_status(output: str) -> dict[str, str | int | bool]:
    """Parse git status --porcelain=v2 --branch output.

    Returns dict with: branch, oid, upstream, ahead, behind, dirty
    """
    result: dict[str, str | int | bool] = {
        "branch": "",
        "oid": "",
        "upstream": "",
        "ahead": 0,
        "behind": 0,
        "dirty": False,
    }

    for line in output.splitlines():
        if line.startswith("# branch.head "):
            result["branch"] = line[14:]
        elif line.startswith("# branch.oid "):
            oid = line[13:]
            # Store short hash (first 7 chars)
            result["oid"] = oid[:7] if oid != "(initial)" else ""
        elif line.startswith("# branch.upstream "):
            result["upstream"] = line[18:]
        elif line.startswith("# branch.ab "):
            # Format: # branch.ab +<ahead> -<behind>
            parts = line[12:].split()
            if len(parts) >= 2:
                result["ahead"] = int(parts[0][1:])  # Remove '+'
                result["behind"] = int(parts[1][1:])  # Remove '-'
        elif line and not line.startswith("#"):
            # Any non-header line means dirty
            result["dirty"] = True

    # Handle detached HEAD - show commit hash instead of branch
    if result["branch"] == "(detached)":
        result["branch"] = str(result["oid"]) if result["oid"] else "detached"

    return result


def _get_git_info(cwd: str) -> dict[str, str | int | bool] | None:
    """Get git status info by running git command.

    Returns None if not in a git repo or command fails.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain=v2", "--branch"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return None
        return _parse_git_status(proc.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


@register
class GitModule(Module):
    """Display git repository status."""

    name = "git"

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render git status info."""
        # Get git info from cwd
        cwd = input.workspace.current_dir or input.cwd
        git_info = _get_git_info(cwd)

        # Return empty to hide module if not in git repo
        if git_info is None or not git_info["branch"]:
            return ""

        # Build computed fields
        dirty_indicator = "*" if git_info["dirty"] else ""

        ahead = int(git_info["ahead"])
        behind = int(git_info["behind"])
        ahead_behind_parts = []
        if ahead > 0:
            ahead_behind_parts.append(f"↑{ahead}")
        if behind > 0:
            ahead_behind_parts.append(f"↓{behind}")
        ahead_behind = "".join(ahead_behind_parts)

        # Build context with all available data
        fmt = theme_vars.get(
            "format", "{{ label }}{{ branch }}{{ dirty_indicator }}{{ ahead_behind }}"
        )
        context = {
            **git_info,
            "dirty_indicator": dirty_indicator,
            "ahead_behind": ahead_behind,
            **theme_vars,
        }
        return render_template(fmt, context)
