"""Event renderables - Rich-renderable event components."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel
from rich.text import Text

from statusline.config import EventsBackgrounds, EventsLineBars


class EventData(BaseModel):
    """Pure data for an event."""

    event: str  # Original event name (e.g., "PostToolUse", "Stop")
    tool: str | None = None
    agent_id: str | None = None
    extra: str | None = None
    effective_event: str = ""  # "StopUndone", "Interrupt", or same as event

    def model_post_init(self, __context) -> None:
        if not self.effective_event:
            self.effective_event = self.event


@dataclass
class EventStyle:
    """Styling options for event rendering.

    Note: Run-level backgrounds are applied in events.py via Styled(),
    not here. This keeps event renderables pure and composable.
    """

    tool_icons: dict[str, str]
    event_icons: dict[str, str]
    bash_icons: dict[str, str]
    backgrounds: EventsBackgrounds
    line_bars: EventsLineBars


class EventBase(ABC):
    """Base class for renderable events."""

    def __init__(self, data: EventData, style: EventStyle) -> None:
        self.data = data
        self.style = style

    @abstractmethod
    def __rich__(self) -> Text:
        """Render this event as styled Text."""
        ...


class IconEvent(EventBase):
    """Generic icon-based event rendering."""

    def __rich__(self) -> Text:
        return Text.from_markup(self._get_icon())

    def _get_icon(self) -> str:
        """Get the icon for this event."""
        data = self.data
        style = self.style

        # Tool use events
        if data.tool and (data.event == "PostToolUse" or not data.event):
            # TaskUpdate: different icons based on status
            if data.tool == "TaskUpdate" and data.extra and data.extra.startswith("status="):
                status = data.extra[7:]  # Remove "status=" prefix
                if status == "completed":
                    return style.tool_icons.get("TaskUpdate:completed", style.tool_icons.get(data.tool, "•"))
                return style.tool_icons.get("TaskUpdate:other", style.tool_icons.get(data.tool, "•"))
            return style.tool_icons.get(data.tool, "•")

        # Non-tool events (Stop, UserPromptSubmit, etc.)
        return style.event_icons.get(data.effective_event, "")


class BashEvent(EventBase):
    """Bash command event with command-specific icons."""

    def __rich__(self) -> Text:
        icon = self._get_icon()
        return Text.from_markup(icon)

    def _get_icon(self) -> str:
        """Get icon based on bash command."""
        extra = self.data.extra
        if extra:
            # Get first word and strip path prefix (e.g., /usr/bin/git -> git)
            words = extra.split()
            if words:
                first_word = words[0]
                cmd = first_word.split("/")[-1]
                if cmd in self.style.bash_icons:
                    return self.style.bash_icons[cmd]
        # Fall back to generic Bash icon
        return self.style.tool_icons.get("Bash", "•")


class EditEvent(EventBase):
    """Edit event with line change bars."""

    def __rich__(self) -> Text:
        base_icon = self.style.tool_icons.get("Edit", "✏")
        text = Text.from_markup(base_icon)

        # Parse line counts from extra ("+N-M" format)
        added, removed = self._parse_line_counts()
        if added is not None and removed is not None:
            chars = self.style.line_bars.chars
            thresholds = self.style.line_bars.thresholds
            add_bar = _lines_to_bar(added, chars, thresholds)
            rem_bar = _lines_to_bar(removed, chars, thresholds)
            bar_bg = self.style.backgrounds.edit_bar
            text.append(add_bar, style=f"green on {bar_bg}")
            text.append(rem_bar, style=f"red on {bar_bg}")

        return text

    def _parse_line_counts(self) -> tuple[int | None, int | None]:
        """Parse '+N-M' format from extra field."""
        extra = self.data.extra
        if not extra or not extra.startswith("+"):
            return None, None
        try:
            parts = extra[1:].split("-")
            added = int(parts[0]) if parts[0] else 0
            removed = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            return added, removed
        except (ValueError, IndexError):
            return None, None


class InterruptEvent(EventBase):
    """Interrupt event (PostToolUseFailure with interrupt flag)."""

    def __rich__(self) -> Text:
        icon = self.style.event_icons.get("Interrupt", "")
        return Text.from_markup(icon)


def _lines_to_bar(count: int, chars: str, thresholds: list[int]) -> str:
    """Convert line count to a bar character (NBSP if 0)."""
    if count <= 0:
        return "\u00a0"  # Non-breaking space: invisible bar
    for i, threshold in enumerate(thresholds):
        if count < threshold:
            return chars[i]
    return chars[-1]


def create_event(data: EventData, style: EventStyle) -> EventBase:
    """Factory function to create the appropriate event renderable."""
    # Interrupt detection
    if data.event == "PostToolUseFailure" and data.extra == "interrupt":
        return InterruptEvent(data, style)

    # Tool use events
    if data.tool and (data.event == "PostToolUse" or not data.event):
        if data.tool == "Bash":
            return BashEvent(data, style)
        if data.tool == "Edit":
            return EditEvent(data, style)
        return IconEvent(data, style)

    # Non-tool events (Stop, UserPromptSubmit, etc.)
    return IconEvent(data, style)
