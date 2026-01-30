"""Git module - displays git repository status."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from statusline.input import GitInfo
from statusline.modules import Module, register
from statusline.templates import render_template

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


def _parse_git_status(output: str) -> GitInfo:
    """Parse git status --porcelain=v2 --branch output into GitInfo."""
    branch = ""
    oid = ""
    upstream = ""
    ahead = 0
    behind = 0
    dirty = False

    for line in output.splitlines():
        if line.startswith("# branch.head "):
            branch = line[14:]
        elif line.startswith("# branch.oid "):
            raw_oid = line[13:]
            # Store short hash (first 7 chars)
            oid = raw_oid[:7] if raw_oid != "(initial)" else ""
        elif line.startswith("# branch.upstream "):
            upstream = line[18:]
        elif line.startswith("# branch.ab "):
            # Format: # branch.ab +<ahead> -<behind>
            parts = line[12:].split()
            if len(parts) >= 2:
                ahead = int(parts[0][1:])  # Remove '+'
                behind = int(parts[1][1:])  # Remove '-'
        elif line and not line.startswith("#"):
            # Any non-header line means dirty
            dirty = True

    # Handle detached HEAD - show commit hash instead of branch
    if branch == "(detached)":
        branch = oid if oid else "detached"

    # Build computed fields
    dirty_indicator = "*" if dirty else ""

    ahead_behind_parts = []
    if ahead > 0:
        ahead_behind_parts.append(f"↑{ahead}")
    if behind > 0:
        ahead_behind_parts.append(f"↓{behind}")
    ahead_behind = "".join(ahead_behind_parts)

    return GitInfo(
        branch=branch,
        oid=oid,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        dirty=dirty,
        dirty_indicator=dirty_indicator,
        ahead_behind=ahead_behind,
    )


def _get_git_info(cwd: str) -> GitInfo | None:
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
    __inputs__ = [GitInfo]

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render git status info."""
        # Get git info from cwd (fetched live, not from input)
        cwd = input.workspace.current_dir or input.cwd
        git_info = _get_git_info(cwd)

        # Return empty to hide module if not in git repo
        if git_info is None or not git_info.branch:
            return ""

        # Build context with all available data
        fmt = theme_vars.get(
            "format", "{{ label }}{{ branch }}{{ dirty_indicator }}{{ ahead_behind }}"
        )
        context = {
            **git_info.model_dump(),
            **theme_vars,
        }
        return render_template(fmt, context)
