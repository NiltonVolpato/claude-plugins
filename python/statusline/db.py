"""Database utilities for statusline."""

from __future__ import annotations

from pathlib import Path


def get_db_path(cwd: str) -> Path:
    """Get the SQLite database path for a project.

    Path format: ~/.claude/projects/{project-slug}/statusline-events.db
    where project-slug is cwd with '/' replaced by '-'.

    NOTE: This must match the path used by the original shell hook
    for backward compatibility with existing databases.
    """
    project_slug = cwd.replace("/", "-")
    return Path.home() / ".claude" / "projects" / project_slug / "statusline-events.db"
