"""Run renderable - a contiguous sequence of events with brackets and background."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from statusline.modules.events.event import EventData, EventStyle, create_event

RunContext = Literal["main", "user", "subagent"]


@dataclass
class RunData:
    """Pure data for a run (contiguous sequence of events in same context)."""

    context: RunContext
    events: list[EventData] = field(default_factory=list)
    agent_id: str | None = None


@dataclass
class RunStyle:
    """Styling options for run rendering."""

    background: str
    open_bracket: str
    close_bracket: str
    spacing: int
    boundary_spacing: int
    event_style: EventStyle


class Run:
    """A renderable run of events with brackets and background."""

    def __init__(self, data: RunData, style: RunStyle) -> None:
        self.data = data
        self.style = style

    def __rich__(self) -> Table:
        # Convert EventData to renderables
        events = [create_event(ed, self.style.event_style) for ed in self.data.events]
        if not events:
            return Table.grid()

        style = self.style
        half_boundary = style.boundary_spacing // 2

        # Inner grid: events with between-event spacing
        inner = Table.grid(padding=(0, style.spacing, 0, 0))
        for _ in events:
            inner.add_column()
        inner.add_row(*events)

        # Apply background style
        styled_inner = Styled(inner, style=style.background) if style.background else inner

        # Add edge spacing if needed
        if half_boundary > 0:
            run_content = Table.grid(padding=0)
            run_content.add_column()
            run_content.add_column()
            run_content.add_column()
            run_content.add_row(
                Text(" " * half_boundary, style=style.background),
                styled_inner,
                Text(" " * half_boundary, style=style.background),
            )
        else:
            run_content = styled_inner

        # Add brackets
        open_text = Text.from_markup(style.open_bracket) if style.open_bracket else Text()
        close_text = Text.from_markup(style.close_bracket) if style.close_bracket else Text()

        bracketed = Table.grid()
        bracketed.add_row(open_text, run_content, close_text)
        return bracketed
