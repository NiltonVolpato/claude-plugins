"""Database utilities for statusline."""

from __future__ import annotations

from pathlib import Path


def get_db_path(transcript_path: str) -> Path:
    """Get the SQLite database path for a project.

    The transcript_path from Claude Code is already in the correct project
    directory (e.g., ~/.claude/projects/{project-slug}/session.jsonl).
    We use its parent directory to store our database.
    """
    return Path(transcript_path).parent / "statusline-events.db"
