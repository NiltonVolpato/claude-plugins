"""Events module - displays a scrolling stream of activity icons."""

from __future__ import annotations

from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from statusline.config import (
    EventsConfig,
    ModuleConfigUnion,
)
from statusline.input import EventsInfo, EventTuple, InputModel
from statusline.modules import Module, register
from statusline.modules.events.event import (
    EventData,
    EventStyle,
)
from statusline.modules.events.run import (
    Run,
    RunContext,
    RunData,
    RunStyle,
)
from statusline.modules.events.truncate_left import TruncateLeft


def group_into_runs(events: list[EventTuple]) -> list[RunData]:
    """Group events into runs by context.

    A run is a contiguous sequence of events in the same context:
    - "user": UserPromptSubmit, Interrupt events
    - "main": All other events (tool uses, Stop, SubagentStart/Stop)

    Subagent events are NOT separate runs - they're part of the main run.
    The SubagentStart/SubagentStop events within the main run provide
    visual markers (< >) to show which tools were invoked by subagents.

    Returns a list of RunData objects ready for rendering.
    """
    if not events:
        return []

    runs: list[RunData] = []
    current_run: RunData | None = None

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
            interrupt_event = EventData(event="Interrupt")
            interrupt_run = RunData(context="user", events=[interrupt_event])
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

        # Create EventData
        event_data = EventData(
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
            current_run = RunData(
                context=context,
                events=[event_data],
            )
        else:
            current_run.events.append(event_data)

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

        # Shared EventStyle for all runs
        event_style = EventStyle(
            tool_icons=config.tool_icons,
            event_icons=config.event_icons,
            bash_icons=config.bash_icons,
            backgrounds=backgrounds,
            line_bars=config.line_bars,
        )

        # Build run renderables
        run_renderables: list[Run] = []
        for run_data in runs:
            if not run_data.events:
                continue

            bg = context_bg.get(run_data.context, "")
            brackets = getattr(brackets_config, run_data.context, ("", ""))
            open_bracket, close_bracket = brackets if bracket_mode else ("", "")

            run_style = RunStyle(
                background=bg,
                open_bracket=open_bracket,
                close_bracket=close_bracket,
                spacing=spacing,
                boundary_spacing=boundary_spacing,
                event_style=event_style,
            )
            run_renderables.append(Run(run_data, run_style))

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
