"""Input providers for statusline modules.

Providers know how to produce input data for modules. Each provider is responsible
for a specific input type (e.g., GitInfo, ModelInfo) and can extract data from
StatuslineInput or compute it independently (e.g., via subprocess).
"""

from __future__ import annotations

import sqlite3
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from statusline.db import get_db_path
from statusline.input import (
    ContextWindowInfo,
    CostInfo,
    EventsInfo,
    EventTuple,
    GitInfo,
    InputModel,
    ModelInfo,
    SessionInfo,
    VersionInfo,
    WorkspaceInfo,
)

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


class InputProvider(ABC):
    """Base class for input providers."""

    input_type: type[InputModel]
    """The Pydantic model this provider produces."""

    @abstractmethod
    def provide(self, input: StatuslineInput) -> InputModel | None:
        """Produce the input data.

        Args:
            input: The parsed StatuslineInput from Claude Code.

        Returns:
            The input model instance, or None if unavailable.
        """
        ...


# Provider registry - maps input types to provider classes
_provider_registry: dict[type[InputModel], type[InputProvider]] = {}


def provider(cls: type[InputProvider]) -> type[InputProvider]:
    """Decorator to register an input provider."""
    _provider_registry[cls.input_type] = cls
    return cls


def get_provider(input_type: type[InputModel]) -> InputProvider | None:
    """Get a provider instance for the given input type."""
    provider_cls = _provider_registry.get(input_type)
    if provider_cls is None:
        return None
    return provider_cls()


def get_all_providers() -> dict[type[InputModel], type[InputProvider]]:
    """Get all registered providers."""
    return _provider_registry.copy()


# --- Built-in Providers ---


@provider
class ModelInfoProvider(InputProvider):
    """Provides model information from StatuslineInput."""

    input_type = ModelInfo

    def provide(self, input: StatuslineInput) -> ModelInfo:
        return input.model


@provider
class WorkspaceInfoProvider(InputProvider):
    """Provides workspace information from StatuslineInput."""

    input_type = WorkspaceInfo

    def provide(self, input: StatuslineInput) -> WorkspaceInfo:
        # Ensure current_dir has a fallback to cwd
        if not input.workspace.current_dir and input.cwd:
            return WorkspaceInfo(
                current_dir=input.cwd,
                project_dir=input.workspace.project_dir or input.cwd,
            )
        return input.workspace


@provider
class CostInfoProvider(InputProvider):
    """Provides cost information from StatuslineInput."""

    input_type = CostInfo

    def provide(self, input: StatuslineInput) -> CostInfo:
        return input.cost


@provider
class ContextWindowInfoProvider(InputProvider):
    """Provides context window information from StatuslineInput."""

    input_type = ContextWindowInfo

    def provide(self, input: StatuslineInput) -> ContextWindowInfo:
        return input.context_window


@provider
class VersionInfoProvider(InputProvider):
    """Provides version information from StatuslineInput."""

    input_type = VersionInfo

    def provide(self, input: StatuslineInput) -> VersionInfo:
        return VersionInfo(version=input.version or "?")


@provider
class SessionInfoProvider(InputProvider):
    """Provides session information from StatuslineInput."""

    input_type = SessionInfo

    def provide(self, input: StatuslineInput) -> SessionInfo:
        return SessionInfo(
            session_id=input.session_id,
            cwd=input.cwd,
        )


@provider
class EventsInfoProvider(InputProvider):
    """Provides events from database or StatuslineInput."""

    input_type = EventsInfo

    def provide(self, input: StatuslineInput) -> EventsInfo:
        # If events are provided directly in input, use them (for preview/testing)
        if input.events.events:
            return input.events

        # Otherwise query from database
        if not input.session_id or not input.cwd:
            return EventsInfo()

        db_path = self._get_db_path(input.cwd)
        if not db_path.exists():
            return EventsInfo()

        events = self._query_events(db_path, input.session_id, limit=500)
        return EventsInfo(events=events)

    def _get_db_path(self, cwd: str) -> Path:
        """Get the SQLite database path for this project."""
        return get_db_path(cwd)

    def _query_events(
        self, db_path: Path, session_id: str, limit: int
    ) -> list[EventTuple]:
        """Query recent events from events_v2 table using SQLite JSON operators."""
        try:
            conn = sqlite3.connect(db_path, timeout=1.0)
            cursor = conn.execute(
                """
                SELECT
                    data->>'hook_event_name' as event,
                    data->>'tool_name' as tool,
                    data->>'agent_id' as agent_id,
                    data as raw_data
                FROM events_v2
                WHERE session_id = ?
                ORDER BY ts DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = list(reversed(cursor.fetchall()))
            conn.close()
            return [self._row_to_event(row) for row in rows]
        except sqlite3.Error:
            return []

    def _row_to_event(self, row: tuple) -> EventTuple:
        """Convert a raw database row to EventTuple, computing extra from JSON."""
        import json

        event, tool, agent_id, raw_data = row
        extra = None

        if raw_data:
            try:
                data = json.loads(raw_data)
                extra = self._compute_extra(event, tool, data)
            except json.JSONDecodeError:
                pass

        return (event or "", tool, agent_id, extra)

    def _compute_extra(
        self, event: str | None, tool: str | None, data: dict
    ) -> str | None:
        """Compute extra field from JSON data."""
        # Interrupt detection
        if event == "PostToolUseFailure" and data.get("is_interrupt"):
            return "interrupt"

        # Stop with hook active
        if event == "Stop" and data.get("stop_hook_active"):
            return "hook_active"

        tool_input = data.get("tool_input") or {}

        # Bash command (truncated)
        if tool == "Bash":
            cmd = tool_input.get("command") or ""
            return cmd[:200] if cmd else None

        # Edit line counts
        if tool == "Edit":
            old = tool_input.get("old_string") or ""
            new = tool_input.get("new_string") or ""
            old_lines = (old.count("\n") + 1) if old else 0
            new_lines = (new.count("\n") + 1) if new else 0
            return f"+{new_lines}-{old_lines}"

        return None


@provider
class GitInfoProvider(InputProvider):
    """Provides git repository status by running git commands."""

    input_type = GitInfo

    def provide(self, input: StatuslineInput) -> GitInfo | None:
        cwd = input.workspace.current_dir or input.cwd
        if not cwd:
            return None
        return self._get_git_info(cwd)

    def _get_git_info(self, cwd: str) -> GitInfo | None:
        """Get git status info by running git command."""
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
            return self._parse_git_status(proc.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    def _parse_git_status(self, output: str) -> GitInfo:
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
                oid = raw_oid[:7] if raw_oid != "(initial)" else ""
            elif line.startswith("# branch.upstream "):
                upstream = line[18:]
            elif line.startswith("# branch.ab "):
                parts = line[12:].split()
                if len(parts) >= 2:
                    ahead = int(parts[0][1:])
                    behind = int(parts[1][1:])
            elif line and not line.startswith("#"):
                dirty = True

        # Handle detached HEAD
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


class InputResolver:
    """Resolves and caches inputs for modules.

    Collects required input types from modules, computes each once,
    and provides them to modules during rendering.
    """

    def __init__(self, input: StatuslineInput):
        self.input = input
        self._cache: dict[type[InputModel], InputModel | None] = {}

    def resolve(self, input_type: type[InputModel]) -> InputModel | None:
        """Resolve an input type, using cache if available."""
        if input_type in self._cache:
            return self._cache[input_type]

        provider = get_provider(input_type)
        if provider is None:
            self._cache[input_type] = None
            return None

        result = provider.provide(self.input)
        self._cache[input_type] = result
        return result

    def resolve_for_module(self, input_types: list[type[InputModel]]) -> dict[str, InputModel]:
        """Resolve all inputs for a module.

        Args:
            input_types: List of input types the module declares.

        Returns:
            Dict mapping input type name (lowercase, without 'Info' suffix) to instance.
        """
        result: dict[str, InputModel] = {}
        for input_type in input_types:
            instance = self.resolve(input_type)
            if instance is not None:
                key = input_type.name
                result[key] = instance
        return result
