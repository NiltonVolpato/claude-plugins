"""Input parsing for statusline CLI."""

from __future__ import annotations

import os
from typing import ClassVar, TextIO

from pydantic import BaseModel, Field, ValidationError


class InputModel(BaseModel):
    """Base class for statusline input models."""

    name: ClassVar[str]


class ModelInfo(InputModel):
    """Model information from Claude Code."""

    name: ClassVar[str] = "model"

    id: str = Field(default="", description="Model identifier (e.g., 'claude-opus-4-5-20251101')")
    display_name: str = Field(default="", description="Human-readable model name (e.g., 'Opus 4.5')")


class WorkspaceInfo(InputModel):
    """Workspace information from Claude Code."""

    name: ClassVar[str] = "workspace"

    current_dir: str = Field(default="", description="Current working directory path")
    project_dir: str = Field(default="", description="Project root directory path")


class CostInfo(InputModel):
    """Cost information from Claude Code."""

    name: ClassVar[str] = "cost"

    total_cost_usd: float = Field(default=0.0, description="Total session cost in USD")
    total_duration_ms: int = Field(default=0, description="Total session duration in milliseconds")
    total_api_duration_ms: int = Field(default=0, description="Total API call duration in milliseconds")
    total_lines_added: int = Field(default=0, description="Total lines of code added")
    total_lines_removed: int = Field(default=0, description="Total lines of code removed")


class ContextWindowInfo(InputModel):
    """Context window information from Claude Code."""

    name: ClassVar[str] = "context"

    total_input_tokens: int = Field(default=0, description="Total input tokens used")
    total_output_tokens: int = Field(default=0, description="Total output tokens generated")
    context_window_size: int = Field(default=200000, description="Maximum context window size")
    used_percentage: float = Field(default=0.0, description="Percentage of context window used")
    remaining_percentage: float = Field(default=100.0, description="Percentage of context window remaining")


class GitInfo(InputModel):
    """Git repository status information."""

    name: ClassVar[str] = "git"

    branch: str = Field(default="", description="Current branch name (or commit hash if detached)")
    oid: str = Field(default="", description="Short commit hash (first 7 characters)")
    upstream: str = Field(default="", description="Upstream branch name (e.g., 'origin/main')")
    ahead: int = Field(default=0, description="Number of commits ahead of upstream")
    behind: int = Field(default=0, description="Number of commits behind upstream")
    dirty: bool = Field(default=False, description="True if there are uncommitted changes")
    dirty_indicator: str = Field(default="", description="'*' if dirty, empty otherwise")
    ahead_behind: str = Field(default="", description="Formatted string (e.g., '↑2↓1')")


class VersionInfo(InputModel):
    """Version information."""

    name: ClassVar[str] = "version"

    version: str = Field(default="", description="Claude Code version string")


class StatuslineInput(BaseModel):
    """Parsed input from Claude Code stdin."""

    hook_event_name: str = ""
    session_id: str = ""
    transcript_path: str = ""
    cwd: str = ""
    version: str = Field(default="", description="Claude Code version string")
    model: ModelInfo = ModelInfo()
    workspace: WorkspaceInfo = WorkspaceInfo()
    cost: CostInfo = CostInfo()
    context_window: ContextWindowInfo = ContextWindowInfo()
    git: GitInfo = GitInfo()


def parse_input(stdin: TextIO) -> StatuslineInput:
    """Parse JSON input from stdin into StatuslineInput."""
    try:
        return StatuslineInput.model_validate_json(stdin.read())
    except ValidationError:
        return StatuslineInput()


def get_sample_input() -> StatuslineInput:
    """Get sample input for preview mode."""
    # Use actual cwd so git module can show real status in preview
    cwd = os.getcwd()
    return StatuslineInput(
        hook_event_name="Status",
        session_id="sample-session-id",
        transcript_path="/path/to/transcript.json",
        cwd=cwd,
        version="2.0.76",
        model=ModelInfo(
            id="claude-opus-4-5-20251101",
            display_name="Opus 4.5",
        ),
        workspace=WorkspaceInfo(
            current_dir=cwd,
            project_dir=cwd,
        ),
        cost=CostInfo(
            total_cost_usd=0.0123,
            total_duration_ms=45000,
            total_api_duration_ms=2300,
            total_lines_added=156,
            total_lines_removed=23,
        ),
        context_window=ContextWindowInfo(
            total_input_tokens=15234,
            total_output_tokens=4521,
            context_window_size=200000,
            used_percentage=42.5,
            remaining_percentage=57.5,
        ),
    )
