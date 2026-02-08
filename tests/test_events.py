"""Unit tests for the events module."""

from rich.console import Console
from rich.text import Text

from statusline.input import EventsInfo, EventTuple, StatuslineInput
from statusline.modules import get_module
from statusline.modules.events import (
    BASH_ICONS,
    EVENT_ICONS,
    TOOL_ICONS,
    EventSegment,
    ExpandableEvents,
    _lines_to_bar,
)
from statusline.providers import EventsInfoProvider


def render_plain(renderable, width: int = 40) -> str:
    """Render a Rich renderable to plain text (no colors)."""
    console = Console(width=width, force_terminal=False, no_color=True)
    with console.capture() as capture:
        console.print(renderable, end="")
    return capture.get()


def render_markup(renderable, width: int = 40) -> str:
    """Render a Rich renderable and return the markup representation."""
    if isinstance(renderable, ExpandableEvents):
        # Build the text representation from segments
        console = Console(width=width, force_terminal=False, record=True)
        with console.capture():
            console.print(renderable, end="")
        # Get the Text object representation
        text = Text()
        text.append(renderable.left)
        for seg in renderable.segments:
            text.append_text(seg.text)
        text.append(renderable.right)
        return text.markup
    return str(renderable)


# ASCII icon set for predictable test output
ASCII_TOOL_ICONS = {
    "Bash": "$ ",
    "Edit": "E ",
    "Write": "W ",
    "Read": "R ",
    "Glob": "G ",
    "Grep": "? ",
    "Task": "T ",
    "WebFetch": "@ ",
    "WebSearch": "@ ",
}

ASCII_EVENT_ICONS = {
    "PostToolUse": None,
    "PostToolUseFailure": None,
    "SubagentStart": "> ",
    "SubagentStop": "< ",
    "UserPromptSubmit": "U ",
    "Stop": "S ",
    "StopUndone": "~ ",  # Stop that got cancelled by hook
    "Interrupt": "X ",
}

ASCII_BASH_ICONS = {
    "git": "g ",
    "pytest": "p ",
}


class TestLinesToBar:
    """Tests for the _lines_to_bar helper."""

    def test_zero_returns_empty(self):
        assert _lines_to_bar(0) == ""

    def test_negative_returns_empty(self):
        assert _lines_to_bar(-5) == ""

    def test_one_to_five_lines(self):
        assert _lines_to_bar(1) == "▃"
        assert _lines_to_bar(5) == "▃"

    def test_six_to_fifteen_lines(self):
        assert _lines_to_bar(6) == "▄"
        assert _lines_to_bar(15) == "▄"

    def test_medium_changes(self):
        assert _lines_to_bar(16) == "▅"
        assert _lines_to_bar(30) == "▅"
        assert _lines_to_bar(31) == "▆"
        assert _lines_to_bar(50) == "▆"

    def test_large_changes(self):
        assert _lines_to_bar(51) == "▇"
        assert _lines_to_bar(100) == "▇"
        assert _lines_to_bar(101) == "█"
        assert _lines_to_bar(201) == "█"


def render_with_styles(renderable, width: int = 40) -> list:
    """Render and return the list of Segments with their styles."""
    console = Console(width=width, force_terminal=True)

    class FakeOptions:
        max_width = width

    return list(renderable.__rich_console__(console, FakeOptions()))


class TestExpandableEventsRendering:
    """Tests for ExpandableEvents with full output comparison."""

    def _make_segment(self, text: str) -> EventSegment:
        """Create a simple EventSegment from plain text."""
        t = Text(text)
        return EventSegment(t, t.cell_len)

    def _make_styled_segment(self, markup: str) -> EventSegment:
        """Create an EventSegment from Rich markup."""
        t = Text.from_markup(markup)
        return EventSegment(t, t.cell_len)

    def _make_bg_segment(self, text: str, bg: str = "on #2a3a2a") -> EventSegment:
        """Create an EventSegment with background color."""
        t = Text()
        t.append(text, style=bg)
        return EventSegment(t, t.cell_len)

    def test_empty_segments_renders_brackets_only(self):
        events = ExpandableEvents([], left="[", right="]")
        assert render_plain(events, width=10) == "[]"

    def test_single_segment_exact_output(self):
        seg = self._make_segment("ABC")
        events = ExpandableEvents([seg], left="[", right="]")
        assert render_plain(events, width=10) == "[ABC]"

    def test_multiple_segments_exact_output(self):
        segments = [
            self._make_segment("A"),
            self._make_segment("B"),
            self._make_segment("C"),
        ]
        events = ExpandableEvents(segments, left="[", right="]")
        assert render_plain(events, width=10) == "[ABC]"

    def test_truncation_keeps_most_recent(self):
        segments = [
            self._make_segment("A"),
            self._make_segment("B"),
            self._make_segment("C"),
            self._make_segment("D"),
        ]
        # Width 4 = "[" + 2 chars + "]"
        events = ExpandableEvents(segments, left="[", right="]")
        assert render_plain(events, width=4) == "[CD]"

    def test_truncation_with_wider_segments(self):
        segments = [
            self._make_segment("AAA"),
            self._make_segment("BBB"),
            self._make_segment("CCC"),
        ]
        # Width 7 = "[" + 5 chars + "]" = can fit "CCC" (3) + crop 2 from "BBB"
        events = ExpandableEvents(segments, left="[", right="]")
        assert render_plain(events, width=7) == "[BBCCC]"

    def test_expand_mode_pads_left(self):
        seg = self._make_segment("X")
        events = ExpandableEvents([seg], left="[", right="]", expand=True)
        assert render_plain(events, width=8) == "[     X]"

    def test_expand_mode_exact_fit(self):
        seg = self._make_segment("ABC")
        events = ExpandableEvents([seg], left="<", right=">", expand=True)
        assert render_plain(events, width=5) == "<ABC>"

    def test_custom_brackets(self):
        seg = self._make_segment("X")
        events = ExpandableEvents([seg], left="<<", right=">>")
        assert render_plain(events, width=10) == "<<X>>"

    def test_styled_segment_plain_output(self):
        seg = self._make_styled_segment("[red]R[/red]")
        events = ExpandableEvents([seg], left="[", right="]")
        assert render_plain(events, width=10) == "[R]"

    def test_overflow_crops_segment_from_left(self):
        """When segments overflow, the overflow segment is cropped from left."""
        # Create segments with background colors
        segments = [
            self._make_bg_segment("AAA", "on #ff0000"),
            self._make_bg_segment("BBB", "on #00ff00"),
            self._make_bg_segment("CCC", "on #0000ff"),
        ]
        # Width 6 = "[" + 4 chars + "]" - fits CCC (3) + crop 1 char from BBB
        events = ExpandableEvents(segments, left="[", right="]")
        rendered_segments = render_with_styles(events, width=6)

        # Segment 0: left bracket "["
        assert rendered_segments[0].text == "["
        # Segment 1: cropped "B" from BBB with green background
        assert rendered_segments[1].text == "B"
        assert rendered_segments[1].style is not None
        assert "#00ff00" in str(rendered_segments[1].style).lower()
        # Segment 2: full CCC with blue background
        assert rendered_segments[2].text == "CCC"
        assert "#0000ff" in str(rendered_segments[2].style).lower()

    def test_overflow_crop_preserves_styles(self):
        """Cropping a segment preserves its styles correctly."""
        seg_red = self._make_bg_segment("RRR", "on #aa0000")
        seg_blue = self._make_bg_segment("BBB", "on #0000aa")
        events = ExpandableEvents([seg_red, seg_blue], left="[", right="]")

        # Width 6 = "[" + 4 chars + "]" - fits BBB (3), crops 1 from RRR
        rendered_segments = render_with_styles(events, width=6)

        # Cropped segment should be last char of RRR with red background
        crop_seg = rendered_segments[1]
        assert crop_seg.text == "R"
        assert crop_seg.style is not None
        assert "#aa0000" in str(crop_seg.style).lower()


class TestEventsModuleWithAsciiIcons:
    """Tests for EventsModule using ASCII icons for predictable output."""

    def _render_events(
        self, events: list[EventTuple], width: int = 30, **theme_vars
    ) -> str:
        """Render events with ASCII icons and return plain text output."""
        module = get_module("events")
        assert module is not None
        theme = {
            "tool_icons": ASCII_TOOL_ICONS,
            "event_icons": ASCII_EVENT_ICONS,
            "bash_icons": ASCII_BASH_ICONS,
            "spacing": 0,  # No spacing between icons for predictable output
            "left": "[",
            "right": "]",
            **theme_vars,
        }
        inputs = {"events": EventsInfo(events=events)}
        result = module.render(inputs, theme)
        if result == "":
            return ""
        return render_plain(result, width=width)

    def test_empty_events_returns_empty_string(self):
        assert self._render_events([]) == ""

    def test_single_read_tool(self):
        """Single tool with no context gets leading boundary space (mid-turn assumption)."""
        events: list[EventTuple] = [("PostToolUse", "Read", None, None)]
        assert self._render_events(events, width=10) == "[ R ]"

    def test_single_edit_tool(self):
        events: list[EventTuple] = [("PostToolUse", "Edit", None, None)]
        assert self._render_events(events, width=10) == "[ E ]"

    def test_user_prompt_submit(self):
        events: list[EventTuple] = [("UserPromptSubmit", None, None, None)]
        # UserPromptSubmit: leading boundary + icon + trailing boundary
        assert self._render_events(events, width=10) == "[ U  ]"

    def test_stop_event(self):
        """Stop event alone gets leading space (mid-turn) + trailing boundary."""
        events: list[EventTuple] = [("Stop", None, None, None)]
        assert self._render_events(events, width=10) == "[ S  ]"

    def test_simple_turn_sequence(self):
        """UserPromptSubmit -> Read -> Stop"""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
        ]
        # U gets leading+trailing boundary, R gets spacing, S gets trailing boundary
        output = self._render_events(events, width=20)
        assert output == "[ U   R S  ]"

    def test_multiple_tools_in_turn(self):
        """UserPromptSubmit -> Glob -> Read -> Read -> Stop"""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Glob", None, None),
            ("PostToolUse", "Read", None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
        ]
        output = self._render_events(events, width=25)
        assert output == "[ U   G R R S  ]"

    def test_subagent_sequence(self):
        """UserPromptSubmit -> SubagentStart -> Read -> SubagentStop -> Stop"""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("SubagentStart", None, "a1", None),
            ("PostToolUse", "Read", "a1", None),
            ("SubagentStop", None, "a1", None),
            ("Stop", None, None, None),
        ]
        output = self._render_events(events, width=30)
        assert output == "[ U   > R <  S  ]"

    def test_bash_git_command(self):
        """Bash with git command uses git icon."""
        events: list[EventTuple] = [("PostToolUse", "Bash", None, "git status")]
        assert self._render_events(events, width=10) == "[ g ]"

    def test_bash_pytest_command(self):
        """Bash with pytest command uses pytest icon."""
        events: list[EventTuple] = [("PostToolUse", "Bash", None, "pytest tests/")]
        assert self._render_events(events, width=10) == "[ p ]"

    def test_bash_unknown_command_uses_default(self):
        """Bash with unknown command uses default bash icon."""
        events: list[EventTuple] = [("PostToolUse", "Bash", None, "echo hello")]
        assert self._render_events(events, width=10) == "[ $ ]"

    def test_explicit_interrupt(self):
        """PostToolUseFailure with interrupt extra."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("PostToolUseFailure", None, None, "interrupt"),
        ]
        output = self._render_events(events, width=20)
        assert output == "[ U   R X  ]"

    def test_inferred_interrupt(self):
        """UserPromptSubmit without prior Stop infers interrupt."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            # No Stop here - next UserPromptSubmit infers interrupt
            ("UserPromptSubmit", None, None, None),
            ("Stop", None, None, None),
        ]
        output = self._render_events(events, width=25)
        # Synthetic interrupt inserted before second UserPromptSubmit
        assert output == "[ U   R  X   U   S  ]"

    def test_skip_redundant_subagent_stop(self):
        """SubagentStop immediately after Stop is skipped."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
            ("SubagentStop", None, None, None),  # Should be skipped
        ]
        output = self._render_events(events, width=20)
        # Only 3 segments: U, R, S (SubagentStop skipped)
        assert output == "[ U   R S  ]"

    def test_limit_truncates_events(self):
        """Limit parameter truncates older events."""
        events: list[EventTuple] = [
            ("PostToolUse", "Glob", None, None),
            ("PostToolUse", "Read", None, None),
            ("PostToolUse", "Edit", None, None),
            ("PostToolUse", "Write", None, None),
        ]
        # With limit=2, should only process last 2 events (mid-turn context)
        output = self._render_events(events, width=15, limit=2)
        assert output == "[ E W ]"

    def test_two_complete_turns(self):
        """Two complete turns with different tools."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Edit", None, None),
            ("Stop", None, None, None),
        ]
        output = self._render_events(events, width=30)
        assert output == "[ U   R S   U   E S  ]"


class TestEventToIcon:
    """Tests for _event_to_icon method with ASCII icons."""

    def _get_icon(self, event: str, tool: str | None, extra: str | None) -> str:
        """Get the plain text icon for an event."""
        from statusline.modules.events import EventsModule

        module = EventsModule()
        text, _ = module._event_to_icon(
            event, tool, extra, ASCII_TOOL_ICONS, ASCII_EVENT_ICONS, ASCII_BASH_ICONS, {}
        )
        return text.plain if text else ""

    def test_read_tool(self):
        assert self._get_icon("PostToolUse", "Read", None) == "R "

    def test_edit_tool(self):
        assert self._get_icon("PostToolUse", "Edit", None) == "E "

    def test_bash_git(self):
        assert self._get_icon("PostToolUse", "Bash", "git status") == "g "

    def test_bash_default(self):
        assert self._get_icon("PostToolUse", "Bash", "ls -la") == "$ "

    def test_user_prompt(self):
        assert self._get_icon("UserPromptSubmit", None, None) == "U "

    def test_stop(self):
        assert self._get_icon("Stop", None, None) == "S "

    def test_subagent_start(self):
        assert self._get_icon("SubagentStart", None, None) == "> "

    def test_subagent_stop(self):
        assert self._get_icon("SubagentStop", None, None) == "< "

    def test_interrupt(self):
        assert self._get_icon("PostToolUseFailure", None, "interrupt") == "X "

    def test_unknown_event(self):
        assert self._get_icon("UnknownEvent", None, None) == ""


class TestEditWithLineCounts:
    """Tests for Edit events with line count bars."""

    def test_edit_with_additions_only(self):
        from statusline.modules.events import EventsModule

        module = EventsModule()
        text, width = module._event_to_icon(
            "PostToolUse", "Edit", "+10-0", TOOL_ICONS, EVENT_ICONS, BASH_ICONS, {}
        )
        assert text is not None
        plain = text.plain
        # Should have edit icon + green bar
        assert "▄" in plain  # 10 lines -> ▄

    def test_edit_with_deletions_only(self):
        from statusline.modules.events import EventsModule

        module = EventsModule()
        text, width = module._event_to_icon(
            "PostToolUse", "Edit", "+0-50", TOOL_ICONS, EVENT_ICONS, BASH_ICONS, {}
        )
        assert text is not None
        plain = text.plain
        # Should have edit icon + red bar
        assert "▆" in plain  # 50 lines -> ▆

    def test_edit_with_both(self):
        from statusline.modules.events import EventsModule

        module = EventsModule()
        text, width = module._event_to_icon(
            "PostToolUse", "Edit", "+100-5", TOOL_ICONS, EVENT_ICONS, BASH_ICONS, {}
        )
        assert text is not None
        plain = text.plain
        # Should have both bars
        assert "▇" in plain  # 100 lines -> ▇
        assert "▃" in plain  # 5 lines -> ▃


class TestEventsInfoProvider:
    """Tests for the EventsInfoProvider."""

    def test_returns_events_from_input_directly(self):
        provider = EventsInfoProvider()
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
        ]
        input_data = StatuslineInput(
            session_id="test",
            cwd="/test",
            events=EventsInfo(events=events),
        )
        result = provider.provide(input_data)
        assert result.events == events

    def test_empty_without_session_id(self):
        provider = EventsInfoProvider()
        input_data = StatuslineInput(cwd="/test")
        result = provider.provide(input_data)
        assert result.events == []

    def test_empty_without_cwd(self):
        provider = EventsInfoProvider()
        input_data = StatuslineInput(session_id="test")
        result = provider.provide(input_data)
        assert result.events == []

    def test_empty_when_db_missing(self):
        provider = EventsInfoProvider()
        input_data = StatuslineInput(
            session_id="test",
            cwd="/nonexistent/path/xyz123",
        )
        result = provider.provide(input_data)
        assert result.events == []

    def test_db_path_format(self):
        provider = EventsInfoProvider()
        path = provider._get_db_path("/home/user/project")
        assert str(path).endswith("statusline-events.db")
        assert "-home-user-project" in str(path)


class TestToolIconsComplete:
    """Verify all expected icons are defined."""

    def test_all_tools_have_icons(self):
        expected = ["Bash", "Edit", "Write", "Read", "Glob", "Grep", "Task", "WebFetch", "WebSearch"]
        for tool in expected:
            assert tool in TOOL_ICONS

    def test_all_events_have_icons(self):
        expected = ["PostToolUse", "PostToolUseFailure", "SubagentStart", "SubagentStop", "UserPromptSubmit", "Stop", "Interrupt"]
        for event in expected:
            assert event in EVENT_ICONS

    def test_common_bash_commands_have_icons(self):
        expected = ["git", "cargo", "uv", "python", "pytest", "npm", "docker"]
        for cmd in expected:
            assert cmd in BASH_ICONS


class TestSpacingAfterTurnEnd:
    """Regression tests for spacing after turn-end events (Stop, SubagentStop).

    Turn-end events have trailing boundary padding, so the next icon should NOT
    get additional prefix spacing to avoid double-spacing.
    """

    def _render_events_plain(self, events: list[EventTuple], spacing: int = 1) -> str:
        """Render events and return plain text (no ANSI codes)."""
        from statusline.modules.events import EventsModule
        from statusline.input import EventsInfo
        import re

        module = EventsModule()
        theme_vars = {"spacing": spacing}
        result = module.render(
            {"events": EventsInfo(events=events)},
            theme_vars,
        )
        # Convert Rich renderable to text
        from rich.console import Console
        from io import StringIO

        console = Console(file=StringIO(), force_terminal=True, width=200)
        console.print(result, end="")
        raw = console.file.getvalue()
        # Strip ANSI escape codes
        return re.sub(r'\x1b\[[0-9;]*m', '', raw)

    def test_no_double_spacing_after_stop(self):
        """After Stop (turn-end), next icon should not get prefix spacing.

        Expected spacing after Stop:
        - Icon trailing space (1) + boundary padding (1) = 2 spaces
        Bug would give: icon (1) + boundary (1) + prefix (2) = 4 spaces
        """
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
            ("PostToolUse", "Bash", None, "echo test"),
        ]
        plain = self._render_events_plain(events, spacing=2)
        # Find the Stop icon (checkmark) and count spaces after it
        # The checkmark is \uf00c which renders as a special char
        # Just verify there aren't 4+ consecutive spaces anywhere
        assert "    " not in plain, f"Found 4+ consecutive spaces (double spacing bug): {repr(plain)}"

    def test_no_double_spacing_after_subagent_stop(self):
        """After SubagentStop (turn-end), next icon should not get prefix spacing."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("SubagentStart", None, "agent-1", None),
            ("PostToolUse", "Read", None, None),
            ("SubagentStop", None, "agent-1", None),
            ("PostToolUse", "Bash", None, "echo test"),
        ]
        plain = self._render_events_plain(events, spacing=2)
        assert "    " not in plain, f"Found 4+ consecutive spaces (double spacing bug): {repr(plain)}"


class TestStopUndoneDetection:
    """Tests for detecting Stop events that were cancelled by hooks."""

    def _render_events_plain(self, events: list[EventTuple]) -> str:
        """Render events and return plain text (no ANSI codes)."""
        from statusline.modules.events import EventsModule
        from statusline.input import EventsInfo
        import re

        module = EventsModule()
        # Use ASCII icons for predictable output
        theme_vars = {
            "event_icons": ASCII_EVENT_ICONS,
            "tool_icons": ASCII_TOOL_ICONS,
            "bash_icons": ASCII_BASH_ICONS,
            "spacing": 0,
        }
        result = module.render({"events": EventsInfo(events=events)}, theme_vars)
        from rich.console import Console
        from io import StringIO

        console = Console(file=StringIO(), force_terminal=True, width=200)
        console.print(result, end="")
        raw = console.file.getvalue()
        return re.sub(r'\x1b\[[0-9;]*m', '', raw)

    def test_stop_followed_by_tool_is_undone(self):
        """Stop followed by tool use should show as StopUndone (~)."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),  # Cancelled by hook
            ("PostToolUse", "Bash", None, "chatterbox"),  # Hook triggered this
            ("Stop", None, None, None),  # Final stop
        ]
        plain = self._render_events_plain(events)
        # First Stop should be ~ (undone), second should be S (final)
        assert "~" in plain, f"Expected StopUndone (~) but got: {repr(plain)}"
        assert "S" in plain, f"Expected Stop (S) but got: {repr(plain)}"

    def test_stop_followed_by_subagent_stop_then_tool_is_undone(self):
        """Stop → SubagentStop → tool use should show StopUndone.

        Claude Code fires both Stop and SubagentStop together, so we need
        to skip over SubagentStop when looking ahead.
        """
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),  # Cancelled
            ("SubagentStop", None, None, None),  # Skip this when looking ahead
            ("PostToolUse", "Bash", None, "chatterbox"),
            ("Stop", None, None, None),  # Final
            ("SubagentStop", None, None, None),
        ]
        plain = self._render_events_plain(events)
        assert "~" in plain, f"Expected StopUndone (~) but got: {repr(plain)}"

    def test_stop_followed_by_user_prompt_is_not_undone(self):
        """Stop followed by UserPromptSubmit is a normal stop."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
            ("UserPromptSubmit", None, None, None),  # New turn, not hook
        ]
        plain = self._render_events_plain(events)
        # Should have S (normal stop), not ~ (undone)
        assert "S" in plain, f"Expected Stop (S) but got: {repr(plain)}"
        assert plain.count("~") == 0, f"Unexpected StopUndone (~): {repr(plain)}"

    def test_final_stop_at_end_is_not_undone(self):
        """Stop at end of events (no following event) is normal."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
        ]
        plain = self._render_events_plain(events)
        assert "S" in plain, f"Expected Stop (S) but got: {repr(plain)}"
        assert "~" not in plain, f"Unexpected StopUndone (~): {repr(plain)}"

    def test_stop_undone_has_normal_spacing(self):
        """StopUndone should have same spacing as normal tools, not turn-end spacing.

        Regression test: StopUndone was getting turn-end boundary padding (2 spaces)
        instead of normal spacing (3 spaces with spacing=2).
        """
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),  # Will be StopUndone
            ("PostToolUse", "Bash", None, "test"),
            ("Stop", None, None, None),
        ]
        plain = self._render_events_plain(events)
        # With spacing=0, StopUndone (~) should NOT have extra boundary space
        # Find positions and check spacing is consistent
        undo_pos = plain.find("~")
        bash_pos = plain.find("$")  # Bash default icon
        assert undo_pos != -1, f"Expected StopUndone (~): {repr(plain)}"
        assert bash_pos != -1, f"Expected Bash ($): {repr(plain)}"
        # With spacing=0, they should be adjacent (just icon trailing spaces)
        assert bash_pos == undo_pos + 2, f"StopUndone spacing wrong: {repr(plain)}"
