"""Events module - displays a scrolling stream of activity icons."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from statusline.config import (
    EventsBackgrounds,
    EventsConfig,
    ModuleConfigUnion,
)
from statusline.input import EventsInfo, EventTuple, InputModel
from statusline.modules import Module, register
from statusline.modules.event_renderables import EventData, EventStyle, create_event
from statusline.renderables import TruncateLeft


@dataclass
class ProcessedEvent:
    """An event with pre-computed rendering properties."""

    event: str  # Original event name
    tool: str | None
    agent_id: str | None
    extra: str | None
    effective_event: str  # "StopUndone", "Interrupt", or same as event


RunContext = Literal["main", "user", "subagent"]


@dataclass
class Run:
    """A contiguous sequence of events in the same context."""

    context: RunContext
    events: list[ProcessedEvent] = field(default_factory=list)
    agent_id: str | None = None  # For subagent runs


def group_into_runs(events: list[EventTuple]) -> list[Run]:
    """Group events into runs by context.

    A run is a contiguous sequence of events in the same context:
    - "user": UserPromptSubmit, Interrupt events
    - "main": All other events (tool uses, Stop, SubagentStart/Stop)

    Subagent events are NOT separate runs - they're part of the main run.
    The SubagentStart/SubagentStop events within the main run provide
    visual markers (< >) to show which tools were invoked by subagents.

    Returns a list of Run objects ready for rendering.
    """
    if not events:
        return []

    runs: list[Run] = []
    current_run: Run | None = None

    # Track state for StopUndone detection and interrupt inference
    in_turn = events[0][0] not in ("UserPromptSubmit", None)
    prev_event = None

    for i, (event, tool, agent_id, extra) in enumerate(events):
        # Skip redundant SubagentStop after Stop
        if event == "SubagentStop" and prev_event == "Stop":
            prev_event = event
            continue

        # Detect StopUndone: Stop followed by tool use
        effective_event = event
        if event == "Stop":
            look_idx = i + 1
            while look_idx < len(events) and events[look_idx][0] == "SubagentStop":
                look_idx += 1
            if look_idx < len(events):
                next_event = events[look_idx][0]
                if next_event not in ("UserPromptSubmit", "Stop"):
                    effective_event = "StopUndone"

        # Infer interrupt: UserPromptSubmit while in a turn
        if event == "UserPromptSubmit" and in_turn:
            # First, append the current run (if any) before adding interrupt
            if current_run is not None:
                runs.append(current_run)
                current_run = None
            # Add synthetic interrupt as a user run
            interrupt_pe = ProcessedEvent(
                event="Interrupt",
                tool=None,
                agent_id=None,
                extra=None,
                effective_event="Interrupt",
            )
            interrupt_run = Run(context="user", events=[interrupt_pe])
            runs.append(interrupt_run)
            in_turn = False

        # Determine context for this event
        if event == "UserPromptSubmit":
            context: RunContext = "user"
        elif event == "Interrupt" or (
            event == "PostToolUseFailure" and extra == "interrupt"
        ):
            context = "user"
        else:
            # Everything else is main (including subagent events)
            context = "main"

        # Create ProcessedEvent
        pe = ProcessedEvent(
            event=event,
            tool=tool,
            agent_id=agent_id,
            extra=extra,
            effective_event=effective_event,
        )

        # Should we start a new run?
        start_new_run = False
        if current_run is None:
            start_new_run = True
        elif context != current_run.context:
            start_new_run = True

        if start_new_run:
            if current_run is not None:
                runs.append(current_run)
            current_run = Run(
                context=context,
                events=[pe],
            )
        else:
            current_run.events.append(pe)

        # Update state
        if event == "UserPromptSubmit":
            in_turn = True
        elif event == "Stop":
            in_turn = False

        prev_event = event

    # Don't forget the last run
    if current_run is not None:
        runs.append(current_run)

    return runs


def preprocess_events(events: list[EventTuple]) -> list[ProcessedEvent]:
    """Pre-process events to compute rendering properties.

    Pass 1: Classification and state tracking.
    - Detects StopUndone (Stop followed by tool use)
    - Detects Interrupts (UserPromptSubmit while in turn)
    """
    if not events:
        return []

    result: list[ProcessedEvent] = []

    # Initial state: if first event isn't UserPromptSubmit, we're mid-turn
    first_event = events[0][0]
    in_turn = first_event not in ("UserPromptSubmit", None)
    subagent_depth = 0
    prev_event = None

    for i, (event, tool, agent_id, extra) in enumerate(events):
        # Skip redundant SubagentStop after Stop
        if event == "SubagentStop" and prev_event == "Stop":
            prev_event = event
            continue

        is_interrupt = event == "PostToolUseFailure" and extra == "interrupt"

        # Infer interrupt: UserPromptSubmit while in a turn at depth 0
        if event == "UserPromptSubmit" and in_turn and subagent_depth == 0:
            # Insert synthetic interrupt event
            result.append(
                ProcessedEvent(
                    event="Interrupt",
                    tool=None,
                    agent_id=None,
                    extra=None,
                    effective_event="Interrupt",
                )
            )
            in_turn = False

        # Detect StopUndone: Stop followed by tool use (skip SubagentStop in lookahead)
        effective_event = event
        if event == "Stop":
            look_idx = i + 1
            while look_idx < len(events) and events[look_idx][0] == "SubagentStop":
                look_idx += 1
            if look_idx < len(events):
                next_event = events[look_idx][0]
                if next_event not in ("UserPromptSubmit", "Stop"):
                    effective_event = "StopUndone"

        result.append(
            ProcessedEvent(
                event=event,
                tool=tool,
                agent_id=agent_id,
                extra=extra,
                effective_event=effective_event,
            )
        )

        # Update state for next iteration
        if event == "UserPromptSubmit":
            in_turn = True
        elif (event == "Stop" or is_interrupt) and subagent_depth == 0:
            in_turn = False
        elif event == "SubagentStart":
            subagent_depth += 1
        elif event == "SubagentStop":
            subagent_depth = max(0, subagent_depth - 1)

        prev_event = event

    return result


@register
class EventsModule(Module):
    """Displays a scrolling stream of activity icons."""

    name = "events"
    __inputs__ = [EventsInfo]

    def render(
        self,
        inputs: dict[str, InputModel],
        config: ModuleConfigUnion,
        **kwargs,
    ):
        expand = kwargs.get("expand", False)
        events_info: EventsInfo | None = inputs.get("events")  # type: ignore[assignment]
        if not events_info or not events_info.events:
            return ""

        # Type narrow to EventsConfig
        if not isinstance(config, EventsConfig):
            return ""

        # Apply limit from config when not expanding
        limit = config.limit
        raw_events = events_info.events if expand else events_info.events[-limit:]

        # Group events into runs
        runs = group_into_runs(raw_events)
        if not runs:
            return ""

        # Spacing between events within a run
        spacing = config.spacing

        # Background styles
        backgrounds = config.backgrounds
        context_bg: dict[RunContext, str] = {
            "main": backgrounds.main,
            "user": backgrounds.user,
            "subagent": backgrounds.subagent,
        }

        # Bracket mode: show brackets around each run
        bracket_mode = config.brackets
        brackets_config = config.run_brackets

        # Compute boundary spacing (symmetric padding at run edges)
        boundary_spacing = spacing + (spacing % 2)  # Round up to even
        half_boundary = boundary_spacing // 2

        # Build run renderables
        run_renderables = []
        for run in runs:
            bg = context_bg.get(run.context, "")
            brackets = getattr(brackets_config, run.context, ("", ""))
            open_bracket, close_bracket = brackets if bracket_mode else ("", "")

            # Create EventStyle for this run context
            style = EventStyle(
                tool_icons=config.tool_icons,
                event_icons=config.event_icons,
                bash_icons=config.bash_icons,
                backgrounds=backgrounds,
                line_bars=config.line_bars,
                segment_bg=bg,
            )

            # Convert events to renderables
            icons = []
            for pe in run.events:
                data = EventData(
                    event=pe.effective_event,
                    tool=pe.tool,
                    agent_id=pe.agent_id,
                    extra=pe.extra,
                )
                event_renderable = create_event(data, style)
                icons.append(event_renderable)

            if not icons:
                continue

            # Inner grid: events with between-event spacing
            # Rich grid padding does NOT add space after last column
            inner = Table.grid(padding=(0, spacing, 0, 0))
            for _ in icons:
                inner.add_column()
            inner.add_row(*icons)

            # Apply background style to inner grid (flows into padding)
            styled_inner = Styled(inner, style=bg) if bg else inner

            # Add edge spacing only if needed (Table.grid gives empty cells min width 1)
            if half_boundary > 0:
                run_content = Table.grid(padding=0)
                run_content.add_column()  # leading edge
                run_content.add_column()  # inner content
                run_content.add_column()  # trailing edge
                run_content.add_row(
                    Text(" " * half_boundary, style=bg),
                    styled_inner,
                    Text(" " * half_boundary, style=bg),
                )
            else:
                run_content = styled_inner

            # Add brackets around the run
            open_text = Text.from_markup(open_bracket) if open_bracket else Text("")
            close_text = Text.from_markup(close_bracket) if close_bracket else Text("")

            bracketed = Table.grid()
            bracketed.add_row(open_text, run_content, close_text)
            run_renderables.append(bracketed)

        if not run_renderables:
            return ""

        # Combine all runs into a single grid
        runs_grid = Table.grid()
        for _ in run_renderables:
            runs_grid.add_column()
        runs_grid.add_row(*run_renderables)

        # Outer frame brackets
        left = Text.from_markup(config.left)
        right = Text.from_markup(config.right)
        background = config.background

        # Build events renderable with left-truncation
        events = TruncateLeft(runs_grid, expand=expand)
        if background:
            events = Styled(events, style=background)

        # Compose frame with Table.grid
        frame = Table.grid(padding=0)
        frame.add_column()  # left bracket
        frame.add_column(ratio=1 if expand else None)  # events
        frame.add_column()  # right bracket
        frame.add_row(left, events, right)
        return frame
