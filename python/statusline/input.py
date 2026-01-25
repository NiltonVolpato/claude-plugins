"""Input parsing for statusline CLI."""

from __future__ import annotations

from typing import TextIO

from pydantic import BaseModel, ValidationError


class ModelInfo(BaseModel):
    """Model information from Claude Code."""

    id: str = ""
    display_name: str = ""


class WorkspaceInfo(BaseModel):
    """Workspace information from Claude Code."""

    current_dir: str = ""
    project_dir: str = ""


class CostInfo(BaseModel):
    """Cost information from Claude Code."""

    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    total_api_duration_ms: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0


class ContextWindowInfo(BaseModel):
    """Context window information from Claude Code."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    context_window_size: int = 200000
    used_percentage: float = 0.0
    remaining_percentage: float = 100.0


class StatuslineInput(BaseModel):
    """Parsed input from Claude Code stdin."""

    hook_event_name: str = ""
    session_id: str = ""
    transcript_path: str = ""
    cwd: str = ""
    version: str = ""
    model: ModelInfo = ModelInfo()
    workspace: WorkspaceInfo = WorkspaceInfo()
    cost: CostInfo = CostInfo()
    context_window: ContextWindowInfo = ContextWindowInfo()


def parse_input(stdin: TextIO) -> StatuslineInput:
    """Parse JSON input from stdin into StatuslineInput."""
    try:
        return StatuslineInput.model_validate_json(stdin.read())
    except ValidationError:
        return StatuslineInput()


def get_sample_input() -> StatuslineInput:
    """Get sample input for preview mode."""
    return StatuslineInput(
        hook_event_name="Status",
        session_id="sample-session-id",
        transcript_path="/path/to/transcript.json",
        cwd="/home/user/my-project",
        version="2.0.76",
        model=ModelInfo(
            id="claude-opus-4-5-20251101",
            display_name="Opus 4.5",
        ),
        workspace=WorkspaceInfo(
            current_dir="/home/user/my-project",
            project_dir="/home/user/my-project",
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
