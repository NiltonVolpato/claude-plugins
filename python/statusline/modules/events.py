"""Events module - displays a scrolling stream of activity icons."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from statusline.config import ThemeVars
from statusline.input import EventsInfo, EventTuple, InputModel
from statusline.modules import Module, register
from statusline.renderables import TruncateLeft


def _lines_to_bar(count: int, chars: str, thresholds: list[int]) -> str:
    """Convert line count to a bar character (\u00a0 if 0)."""
    if count <= 0:
        return "\u00a0"  # Non-breaking space: invisible bar
    for i, threshold in enumerate(thresholds):
        if count < threshold:
            return chars[i]
    return chars[-1]


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
        theme_vars: ThemeVars,
        *,
        expand: bool = False,
    ):
        events_info: EventsInfo | None = inputs.get("events")  # type: ignore[assignment]
        if not events_info or not events_info.events:
            return ""

        # Apply limit from theme when not expanding
        limit = int(theme_vars["limit"])
        raw_events = events_info.events if expand else events_info.events[-limit:]

        # Group events into runs
        runs = group_into_runs(raw_events)
        if not runs:
            return ""

        # Get icon mappings from theme
        tool_icons = theme_vars["tool_icons"]
        event_icons = theme_vars["event_icons"]
        bash_icons = theme_vars["bash_icons"]
        line_bars = theme_vars["line_bars"]

        # Spacing between events within a run
        spacing = int(theme_vars["spacing"])

        # Background styles
        backgrounds = theme_vars["backgrounds"]
        context_bg: dict[RunContext, str] = {
            "main": backgrounds["main"],
            "user": backgrounds["user"],
            "subagent": backgrounds["subagent"],
        }

        # Bracket mode: show brackets around each run
        bracket_mode = theme_vars["brackets"]
        brackets_config = theme_vars["run_brackets"]

        # Compute boundary spacing (symmetric padding at run edges)
        boundary_spacing = spacing + (spacing % 2)  # Round up to even
        half_boundary = boundary_spacing // 2

        # Build run renderables
        run_renderables = []
        for run in runs:
            bg = context_bg.get(run.context, "")
            brackets = brackets_config.get(run.context, ["", ""])
            open_bracket, close_bracket = brackets if bracket_mode else ("", "")

            # Build run content as Text (simpler than grid for edge spacing)
            text = Text()

            # Leading space with background
            if half_boundary > 0:
                text.append(" " * half_boundary, style=bg)

            # Add events with spacing between them
            first = True
            for pe in run.events:
                icon = self._event_to_icon(
                    pe.effective_event,
                    pe.tool,
                    pe.extra,
                    tool_icons,
                    event_icons,
                    bash_icons,
                    backgrounds,
                    line_bars,
                    segment_bg=bg,
                )
                if not icon:
                    continue

                if not first and spacing > 0:
                    text.append(" " * spacing, style=bg)
                text.append_text(icon)
                first = False

            # Trailing space with background
            if half_boundary > 0:
                text.append(" " * half_boundary, style=bg)

            if not text.plain.strip():
                continue

            # Add brackets around the run
            open_text = Text.from_markup(open_bracket) if open_bracket else Text("")
            close_text = Text.from_markup(close_bracket) if close_bracket else Text("")

            bracketed = Table.grid()
            bracketed.add_row(open_text, text, close_text)
            run_renderables.append(bracketed)

        if not run_renderables:
            return ""

        # Combine all runs into a single grid
        runs_grid = Table.grid()
        for _ in run_renderables:
            runs_grid.add_column()
        runs_grid.add_row(*run_renderables)

        # Outer frame brackets
        left = Text.from_markup(str(theme_vars["left"]))
        right = Text.from_markup(str(theme_vars["right"]))
        background = str(theme_vars.get("background", ""))

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

    def _event_to_icon(
        self,
        event: str,
        tool: str | None,
        extra: str | None,
        tool_icons: dict,
        event_icons: dict,
        bash_icons: dict,
        backgrounds: dict,
        line_bars: dict,
        segment_bg: str | None = None,
    ) -> Text | None:
        """Convert an event to its styled Text representation.

        Args:
            segment_bg: Background style to apply to the icon. For Edit with bars,
                        this is applied to the icon but not the bars.
        """
        # PostToolUseFailure with interrupt flag -> show as Interrupt
        if event == "PostToolUseFailure" and extra == "interrupt":
            icon = event_icons.get("Interrupt", "")
            if icon:
                text = Text.from_markup(icon)
                if segment_bg:
                    text.stylize(segment_bg)
                return text
            return None

        # Tool use events (or legacy events with tool but no event type)
        if tool and (event == "PostToolUse" or not event):
            # For Bash, check if there's a command-specific icon
            if tool == "Bash" and extra:
                # Get first word and strip path prefix (e.g., /usr/bin/git -> git)
                words = extra.split()
                if words:
                    first_word = words[0]
                    cmd = first_word.split("/")[-1]
                    if cmd in bash_icons:
                        icon = bash_icons[cmd]
                        text = Text.from_markup(icon)
                        if segment_bg:
                            text.stylize(segment_bg)
                        return text
            # For Edit, show line change bars (Write just shows icon)
            if tool == "Edit" and extra and extra.startswith("+"):
                base_icon = tool_icons.get(tool, "✏")
                try:
                    # Parse "+N-M" format
                    parts = extra[1:].split("-")
                    added = int(parts[0]) if parts[0] else 0
                    removed = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                    chars = line_bars["chars"]
                    thresholds = line_bars["thresholds"]
                    add_bar = _lines_to_bar(added, chars, thresholds)
                    rem_bar = _lines_to_bar(removed, chars, thresholds)
                    # Always show 2 bar positions (additions + deletions)
                    # _lines_to_bar returns NBSP for 0 (invisible bar)
                    text = Text.from_markup(base_icon)
                    if segment_bg:
                        text.stylize(segment_bg)
                    bar_bg = backgrounds["edit_bar"]
                    text.append(add_bar, style=f"green on {bar_bg}")
                    text.append(rem_bar, style=f"red on {bar_bg}")
                    return text
                except (ValueError, IndexError):
                    pass
            icon = tool_icons.get(tool, "•")
            text = Text.from_markup(icon)
            if segment_bg:
                text.stylize(segment_bg)
            return text
        icon = event_icons.get(event, "")
        if icon:
            text = Text.from_markup(icon)
            if segment_bg:
                text.stylize(segment_bg)
            return text
        return None
