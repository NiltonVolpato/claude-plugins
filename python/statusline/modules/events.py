"""Events module - displays a scrolling stream of activity icons."""

from __future__ import annotations

from dataclasses import dataclass

from rich.cells import cell_len
from rich.measure import Measurement
from rich.segment import Segment
from rich.text import Text

from statusline.config import ThemeVars
from statusline.input import EventsInfo, EventTuple, InputModel
from statusline.modules import Module, register

# Default icon mappings (nerd font icons with trailing space for proper width)
TOOL_ICONS = {
    "Bash": "[bright_black]\uea85[/] ",  # cod-terminal
    "Edit": "[yellow]\uf4d2[/] ",  # fa-edit (pencil)
    "Write": "[green]\uea7f[/] ",  # fa-edit
    "Read": "[cyan]\U000f0dca[/] ",  # cod-eye
    "Glob": "[blue]\uf002[/] ",  # cod-search
    "Grep": "[blue]\uf002[/] ",  # cod-search
    "Task": "[magenta]\ueab3[/] ",  # cod-checklist
    "WebFetch": "[cyan]\ueb01[/] ",  # cod-globe
    "WebSearch": "[cyan]\ueb01[/] ",  # cod-globe
}

# Bash command-specific icons (extra field contains first word of command)
BASH_ICONS = {
    "git": "[#f05032]\ue702[/] ",  # dev-git (git orange)
    "cargo": "[#dea584]\ue7a8[/] ",  # dev-rust (rust orange)
    "uv": "[green]\ue73c[/] ",  # dev-python
    "python": "[green]\ue73c[/] ",  # dev-python
    "python3": "[green]\ue73c[/] ",  # dev-python
    "pytest": "[yellow]\ue87a[/] ",  # dev-pytest
    "npm": "[red]\ue71e[/] ",  # dev-npm
    "node": "[green]\ue71e[/] ",  # dev-npm (node green)
    "docker": "[#2496ed]\ue7b0[/] ",  # dev-docker (docker blue)
    "make": "[bright_black]\uf0ad[/] ",  # fa-wrench
    "sqlite3": "[blue]\uf472[/] ",  # cod-database
    "sleep": "[yellow]\U000f04b2[/] ",
    "chatterbox": "[cyan]\U000f050a[/] ",
    "rm": "[red]\U000f01b4[/] ",
}

# Bar characters for line counts (logarithmic scale)
LINE_BARS = "▂▃▄▅▆▇█"
LINE_THRESHOLDS = [1, 6, 16, 31, 51, 101, 201]


def _lines_to_bar(count: int) -> str:
    """Convert line count to a bar character."""
    if count <= 0:
        return ""
    for i, threshold in enumerate(LINE_THRESHOLDS):
        if count < threshold:
            return LINE_BARS[i]
    return LINE_BARS[-1]


# NOTE: Many Nerd Font icons are wider than 1 cell (1.5-2 chars) and overflow
# into the next character space. The trailing space in icon definitions is
# INTENTIONAL - it's part of the icon's visual width, not inter-icon spacing.
# Do not remove these spaces thinking they're redundant padding.
EVENT_ICONS = {
    "PostToolUse": None,  # Uses TOOL_ICONS
    "PostToolUseFailure": None,  # Check extra for "interrupt"
    "SubagentStart": "[bold blue]\U000f0443[/] ",  # cod-run-all (play arrow)
    "SubagentStop": "[bold blue]\U000f0441[/] ",  # fa-stop
    "UserPromptSubmit": "[bright_white]\uf007[/] ",  # fa-user
    "Stop": "[green]\uf4f0[/] ",  # nf-md-check_circle (final stop)
    "StopUndone": "[yellow]\uf0e2[/] ",  # fa-undo (stop that got cancelled by hook)
    "Interrupt": "[red]\ue009[/] ",  # interrupted/cancelled (synthetic)
}


@dataclass
class ProcessedEvent:
    """An event with pre-computed rendering properties."""

    event: str  # Original event name
    tool: str | None
    agent_id: str | None
    extra: str | None
    effective_event: str  # "StopUndone", "Interrupt", or same as event
    is_turn_start: bool
    is_turn_end: bool
    in_subagent: bool


def preprocess_events(events: list[EventTuple]) -> list[ProcessedEvent]:
    """Pre-process events to compute rendering properties.

    Pass 1: Classification and state tracking.
    - Detects StopUndone (Stop followed by tool use)
    - Detects Interrupts (UserPromptSubmit while in turn)
    - Marks turn boundaries and subagent context
    """
    if not events:
        return []

    result: list[ProcessedEvent] = []

    # Initial state: if first event isn't UserPromptSubmit, we're mid-turn
    first_event = events[0][0]
    in_turn = first_event not in ("UserPromptSubmit", None)
    is_first_in_turn = in_turn
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
                    is_turn_start=False,
                    is_turn_end=True,
                    in_subagent=False,
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

        # Determine turn boundary flags
        is_turn_start = is_first_in_turn or event == "SubagentStart"
        in_subagent_now = subagent_depth > 0 or event == "SubagentStart"
        is_turn_end = (
            effective_event in ("Stop", "SubagentStop", "UserPromptSubmit")
            or is_interrupt
        )

        result.append(
            ProcessedEvent(
                event=event,
                tool=tool,
                agent_id=agent_id,
                extra=extra,
                effective_event=effective_event,
                is_turn_start=is_turn_start,
                is_turn_end=is_turn_end,
                in_subagent=in_subagent_now,
            )
        )

        # Update state for next iteration
        if event == "UserPromptSubmit":
            in_turn = True
            is_first_in_turn = True
        elif (event == "Stop" or is_interrupt) and subagent_depth == 0:
            in_turn = False
            is_first_in_turn = False
        elif event == "SubagentStart":
            subagent_depth += 1
            is_first_in_turn = False
        elif event == "SubagentStop":
            subagent_depth = max(0, subagent_depth - 1)
        else:
            is_first_in_turn = False

        prev_event = event

    return result


class EventSegment:
    """A single event segment with its display width and styled text."""

    def __init__(self, text: Text, width: int):
        self.text = text
        self.width = width


class ExpandableEvents:
    """Rich renderable that displays events, truncating from the left to fit width."""

    def __init__(
        self,
        segments: list[EventSegment],
        *,
        expand: bool = False,
        left: str = "",
        right: str = "",
    ):
        self.segments = segments
        self.expand = expand
        self.left = left
        self.right = right

    def __rich_console__(self, console, options):
        width = options.max_width
        frame_width = cell_len(self.left) + cell_len(self.right)
        available = width - frame_width

        # Build from right (most recent), truncate from left
        result: list[EventSegment] = []
        used = 0
        overflow_seg = None  # The segment that didn't fit (for partial rendering)
        for seg in reversed(self.segments):
            if used + seg.width > available:
                overflow_seg = seg  # Save for potential partial rendering
                break
            result.append(seg)
            used += seg.width
        result.reverse()

        # Calculate remaining space and handle partial first segment
        remaining = available - used
        partial_text = None
        if remaining > 0 and overflow_seg is not None:
            # Crop the overflow segment to show only rightmost `remaining` characters
            # This preserves styles from the cropped portion
            partial_text = overflow_seg.text[-remaining:]
        elif self.expand and remaining > 0:
            # Normal padding when expanding (events align right)
            partial_text = Text(" " * remaining)

        # Yield left bracket
        yield Segment(self.left)

        # Yield partial/cropped segment if any
        if partial_text:
            yield from partial_text.render(console)

        # Yield each segment
        for seg in result:
            yield from seg.text.render(console)

        # Yield right bracket
        yield Segment(self.right)

    def __rich_measure__(self, console, options):
        frame_width = cell_len(self.left) + cell_len(self.right)
        total = sum(seg.width for seg in self.segments) + frame_width
        if self.expand:
            return Measurement(frame_width, options.max_width)
        return Measurement(total, total)


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
        limit_val = theme_vars.get("limit", 30)
        limit = int(limit_val) if isinstance(limit_val, (int, str)) else 30
        raw_events = events_info.events if expand else events_info.events[-limit:]

        # Pass 1: Pre-process events
        events = preprocess_events(raw_events)

        # Get icon mappings from theme or use defaults
        tool_icons = theme_vars.get("tool_icons", TOOL_ICONS)
        event_icons = theme_vars.get("event_icons", EVENT_ICONS)
        bash_icons = theme_vars.get("bash_icons", BASH_ICONS)

        # Configurable spacing
        spacing_val = theme_vars.get("spacing", 1)
        spacing = int(spacing_val) if isinstance(spacing_val, (int, str)) else 1

        # Background styles (configurable via theme_vars)
        backgrounds = theme_vars.get("backgrounds", {})
        turn_bg = backgrounds.get("turn", "on #2a3a2a")  # greenish for main agent
        subagent_bg = backgrounds.get("subagent", "on #2a2a3a")  # blue-ish
        user_bg = backgrounds.get("user", "on #3a2a2a")  # warm/reddish

        # Pass 2: Build segments (simple iteration, no state tracking)
        segments: list[EventSegment] = []
        prev_was_turn_end = False

        for pe in events:
            icon_text, icon_width = self._event_to_icon(
                pe.effective_event,
                pe.tool,
                pe.extra,
                tool_icons,
                event_icons,
                bash_icons,
                backgrounds,
            )
            if not icon_text:
                continue

            # Determine background based on event type
            if pe.event == "UserPromptSubmit" or pe.event == "Interrupt":
                bg = user_bg
            elif pe.event == "SubagentStop" or pe.in_subagent:
                bg = subagent_bg
            else:
                bg = turn_bg

            # Build segment
            text = Text()
            width = icon_width

            # Boundary events get 1 space padding before
            is_boundary = pe.is_turn_start or pe.event == "UserPromptSubmit"
            if is_boundary:
                text.append(" ", style=bg)
                width += 1
            elif segments and not prev_was_turn_end:
                # Normal spacing from previous icon
                prefix = " " * spacing
                text.append(prefix, style=bg if bg else None)
                width += len(prefix)

            # Icon with background
            if bg:
                icon_text.stylize(bg)
            text.append_text(icon_text)

            # Trailing boundary padding
            if pe.is_turn_end:
                text.append(" ", style=bg)
                width += 1

            segments.append(EventSegment(text, width))
            prev_was_turn_end = pe.is_turn_end

        left = str(theme_vars.get("left", "["))
        right = str(theme_vars.get("right", "]"))
        return ExpandableEvents(segments, expand=expand, left=left, right=right)

    def _event_to_icon(
        self,
        event: str,
        tool: str | None,
        extra: str | None,
        tool_icons: dict,
        event_icons: dict,
        bash_icons: dict,
        backgrounds: dict,
    ) -> tuple[Text | None, int]:
        """Convert an event to its styled Text representation and display width."""
        # PostToolUseFailure with interrupt flag -> show as Interrupt
        if event == "PostToolUseFailure" and extra == "interrupt":
            icon = event_icons.get("Interrupt", "")
            if icon:
                text = Text.from_markup(icon)
                return text, text.cell_len
            return None, 0

        # Tool use events (or legacy events with tool but no event type)
        if tool and (event == "PostToolUse" or not event):
            # For Bash, check if there's a command-specific icon
            if tool == "Bash" and extra:
                # Get first word and strip path prefix (e.g., /usr/bin/git -> git)
                first_word = extra.split()[0] if extra else ""
                cmd = first_word.split("/")[-1]
                if cmd in bash_icons:
                    icon = bash_icons[cmd]
                    text = Text.from_markup(icon)
                    return text, text.cell_len
            # For Edit, show line change bars (Write just shows icon)
            if tool == "Edit" and extra and extra.startswith("+"):
                base_icon = tool_icons.get(tool, "✏")
                try:
                    # Parse "+N-M" format
                    parts = extra[1:].split("-")
                    added = int(parts[0]) if parts[0] else 0
                    removed = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                    add_bar = _lines_to_bar(added)
                    rem_bar = _lines_to_bar(removed)
                    if add_bar or rem_bar:
                        text = Text.from_markup(base_icon)
                        width = text.cell_len
                        bar_bg = backgrounds.get("edit_bar", "#4c4d4e")
                        if add_bar:
                            text.append(add_bar, style=f"green on {bar_bg}")
                            width += cell_len(add_bar)
                        if rem_bar:
                            text.append(rem_bar, style=f"red on {bar_bg}")
                            width += cell_len(rem_bar)
                        return text, width
                except (ValueError, IndexError):
                    pass
                text = Text.from_markup(base_icon)
                return text, text.cell_len
            icon = tool_icons.get(tool, "•")
            text = Text.from_markup(icon)
            return text, text.cell_len
        icon = event_icons.get(event, "")
        if icon:
            text = Text.from_markup(icon)
            return text, text.cell_len
        return None, 0
