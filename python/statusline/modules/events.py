"""Events module - displays a scrolling stream of activity icons."""

from __future__ import annotations

from rich.cells import cell_len
from rich.measure import Measurement
from rich.segment import Segment
from rich.text import Text

from statusline.config import ThemeVars
from statusline.input import EventsInfo, InputModel
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
    "rm": "[red]\U000f01b4[/]",
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


EVENT_ICONS = {
    "PostToolUse": None,  # Uses TOOL_ICONS
    "PostToolUseFailure": None,  # Check extra for "interrupt"
    "SubagentStart": "[bold blue]\U000f0443[/] ",  # cod-run-all (play arrow)
    "SubagentStop": "[bold blue]\U000f0441[/] ",  # fa-stop
    "UserPromptSubmit": "[bright_white]\uf007[/] ",  # fa-user
    "Stop": "[green]\uf00c[/] ",  # fa-check
    "StopHookActive": "[yellow]\uf04c[/] ",  # fa-pause (stop with hook running)
    "Interrupt": "[red]\ue009[/] ",  # interrupted/cancelled (synthetic)
}


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
        events = events_info.events if expand else events_info.events[-limit:]

        # Get icon mappings from theme or use defaults
        tool_icons = theme_vars.get("tool_icons", TOOL_ICONS)
        event_icons = theme_vars.get("event_icons", EVENT_ICONS)

        # Get bash command icons from theme or use defaults
        bash_icons = theme_vars.get("bash_icons", BASH_ICONS)

        # Configurable spacing
        spacing_val = theme_vars.get("spacing", 1)
        spacing = int(spacing_val) if isinstance(spacing_val, (int, str)) else 1

        # Background styles (warm/cool contrast)
        turn_bg = "on #2a3a2a"  # Cool/greenish gray for main agent
        subagent_bg = "on #2a2a3a"  # Blue-ish for subagents
        user_bg = "on #3a2a2a"  # Warm/reddish gray for user prompts

        # Build segments with spacing
        # State: in_turn means we're inside an agent turn (after UserPromptSubmit, until Stop)
        segments: list[EventSegment] = []
        # If first event isn't UserPromptSubmit, we're mid-turn (truncated from left)
        first_event = events[0][0] if events else None
        in_turn = first_event not in ("UserPromptSubmit", None)
        is_first_in_turn = in_turn  # Treat first event as turn start if mid-turn
        subagent_depth = 0

        prev_event = None
        for event, tool, agent_id, extra in events:
            # Skip SubagentStop if it immediately follows Stop (redundant main agent ending)
            if event == "SubagentStop" and prev_event == "Stop":
                prev_event = event
                continue

            # Detect interrupt: PostToolUseFailure with extra="interrupt"
            is_interrupt = event == "PostToolUseFailure" and extra == "interrupt"

            # Infer interrupt: UserPromptSubmit while still in a turn means previous was interrupted
            if event == "UserPromptSubmit" and in_turn and subagent_depth == 0:
                # Insert synthetic interrupt icon with user background (user caused the interrupt)
                interrupt_icon = event_icons.get("Interrupt", "")
                if interrupt_icon:
                    int_text = Text.from_markup(interrupt_icon)
                    int_width = int_text.cell_len
                    # Build segment with user background and symmetric boundary
                    seg_text = Text()
                    seg_text.append(" ", style=user_bg)  # leading boundary
                    int_text.stylize(user_bg)
                    seg_text.append_text(int_text)
                    seg_text.append(" ", style=user_bg)  # trailing boundary
                    segments.append(EventSegment(seg_text, 1 + int_width + 1))
                in_turn = False

            icon_text, icon_width = self._event_to_icon(
                event, tool, extra, tool_icons, event_icons, bash_icons
            )
            if icon_text:
                # Determine background based on event type (not turn state)
                in_subagent = subagent_depth > 0 or event == "SubagentStart"

                if event == "UserPromptSubmit":
                    bg = user_bg
                elif event == "SubagentStop" or in_subagent:
                    bg = subagent_bg
                else:
                    # All other events (tools, Stop) get turn background
                    bg = turn_bg

                # Build segment
                text = Text()
                width = icon_width

                # Boundary events get 1 space padding before and after (symmetric)
                is_turn_start = is_first_in_turn or event == "SubagentStart"
                is_boundary = is_turn_start or event == "UserPromptSubmit"

                if is_boundary:
                    text.append(" ", style=bg)
                    width += 1
                    is_first_in_turn = False
                elif segments:
                    # Normal spacing from previous icon
                    prefix = " " * spacing
                    if bg:
                        text.append(prefix, style=bg)
                    else:
                        text.append(prefix)
                    width += len(prefix)

                # Icon with background
                if bg:
                    icon_text.stylize(bg)
                text.append_text(icon_text)

                # Trailing boundary padding: 1 space (symmetric with leading)
                is_turn_end = (
                    event in ("Stop", "SubagentStop", "UserPromptSubmit")
                    or is_interrupt
                )
                if is_turn_end:
                    text.append(" ", style=bg)
                    width += 1

                segments.append(EventSegment(text, width))

            # Update state after processing
            if event == "UserPromptSubmit":
                in_turn = True
                is_first_in_turn = True
            elif (event == "Stop" or is_interrupt) and subagent_depth == 0:
                in_turn = False
            elif event == "SubagentStart":
                subagent_depth += 1
            elif event == "SubagentStop":
                subagent_depth = max(0, subagent_depth - 1)

            prev_event = event

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
    ) -> tuple[Text | None, int]:
        """Convert an event to its styled Text representation and display width."""
        # PostToolUseFailure with interrupt flag -> show as Interrupt
        if event == "PostToolUseFailure" and extra == "interrupt":
            icon = event_icons.get("Interrupt", "")
            if icon:
                text = Text.from_markup(icon)
                return text, text.cell_len
            return None, 0

        # Stop with hook_active -> show as StopHookActive (pause icon)
        if event == "Stop" and extra == "hook_active":
            icon = event_icons.get("StopHookActive", "")
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
                        if add_bar:
                            text.append(add_bar, style="green on #4c4d4e")
                            width += cell_len(add_bar)
                        if rem_bar:
                            text.append(rem_bar, style="red on #4c4d4e")
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
