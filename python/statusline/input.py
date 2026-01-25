"""Input parsing for statusline CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TextIO


@dataclass
class ModelInfo:
    """Model information from Claude Code."""

    id: str = ""
    display_name: str = ""


@dataclass
class WorkspaceInfo:
    """Workspace information from Claude Code."""

    current_dir: str = ""
    project_dir: str = ""


@dataclass
class CostInfo:
    """Cost information from Claude Code."""

    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    total_api_duration_ms: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0


@dataclass
class ContextWindowInfo:
    """Context window information from Claude Code."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    context_window_size: int = 200000
    used_percentage: float = 0.0
    remaining_percentage: float = 100.0


@dataclass
class StatuslineInput:
    """Parsed input from Claude Code stdin."""

    hook_event_name: str = ""
    session_id: str = ""
    transcript_path: str = ""
    cwd: str = ""
    version: str = ""
    model: ModelInfo = field(default_factory=ModelInfo)
    workspace: WorkspaceInfo = field(default_factory=WorkspaceInfo)
    cost: CostInfo = field(default_factory=CostInfo)
    context_window: ContextWindowInfo = field(default_factory=ContextWindowInfo)


def parse_input(stdin: TextIO) -> StatuslineInput:
    """Parse JSON input from stdin into StatuslineInput."""
    try:
        data = json.load(stdin)
    except json.JSONDecodeError:
        return StatuslineInput()

    model_data = data.get("model", {})
    model = ModelInfo(
        id=model_data.get("id", ""),
        display_name=model_data.get("display_name", ""),
    )

    workspace_data = data.get("workspace", {})
    workspace = WorkspaceInfo(
        current_dir=workspace_data.get("current_dir", ""),
        project_dir=workspace_data.get("project_dir", ""),
    )

    cost_data = data.get("cost", {})
    cost = CostInfo(
        total_cost_usd=cost_data.get("total_cost_usd", 0.0),
        total_duration_ms=cost_data.get("total_duration_ms", 0),
        total_api_duration_ms=cost_data.get("total_api_duration_ms", 0),
        total_lines_added=cost_data.get("total_lines_added", 0),
        total_lines_removed=cost_data.get("total_lines_removed", 0),
    )

    context_data = data.get("context_window", {})
    context_window = ContextWindowInfo(
        total_input_tokens=context_data.get("total_input_tokens", 0),
        total_output_tokens=context_data.get("total_output_tokens", 0),
        context_window_size=context_data.get("context_window_size", 200000),
        used_percentage=context_data.get("used_percentage", 0.0),
        remaining_percentage=context_data.get("remaining_percentage", 100.0),
    )

    return StatuslineInput(
        hook_event_name=data.get("hook_event_name", ""),
        session_id=data.get("session_id", ""),
        transcript_path=data.get("transcript_path", ""),
        cwd=data.get("cwd", ""),
        version=data.get("version", ""),
        model=model,
        workspace=workspace,
        cost=cost,
        context_window=context_window,
    )


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
