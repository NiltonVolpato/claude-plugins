"""Unit tests for the events module."""

from rich.console import Console
from rich.text import Text
from statusline.config import (
    EventsBackgrounds,
    EventsConfig,
    EventsLineBars,
    EventsRunBrackets,
)
from statusline.input import EventsInfo, EventTuple, StatuslineInput
from statusline.modules import get_module
from statusline.modules.events import _lines_to_bar
from statusline.renderables import TruncateLeft
from statusline.providers import EventsInfoProvider


def render_plain(renderable, width: int = 40) -> str:
    """Render a Rich renderable to plain text (no colors)."""
    console = Console(width=width, force_terminal=False, no_color=True)
    with console.capture() as capture:
        console.print(renderable, end="")
    return capture.get().rstrip("\n")


# ASCII icon set for predictable test output
ASCII_TOOL_ICONS = {
    "Bash": "$",
    "Edit": "E",
    "Write": "W",
    "Read": "R",
    "Glob": "G",
    "Grep": "?",
    "Task": "T",
    "WebFetch": "@",
    "WebSearch": "@",
}

ASCII_EVENT_ICONS = {
    "SubagentStart": ">",
    "SubagentStop": "<",
    "UserPromptSubmit": "U",
    "Stop": "S",
    "StopUndone": "~",  # Stop that got cancelled by hook
    "Interrupt": "X",
}

ASCII_BASH_ICONS = {
    "git": "g",
    "pytest": "p",
}


# Default line bar config for tests (matching defaults.toml)
LINE_BARS_CHARS = "▂▃▄▅▆▇█"
LINE_BARS_THRESHOLDS = [1, 6, 16, 31, 51, 101, 201]


class TestLinesToBar:
    """Tests for the _lines_to_bar helper."""

    def test_zero_returns_nbsp(self):
        """Zero lines returns non-breaking space (invisible bar)."""
        assert _lines_to_bar(0, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "\u00a0"

    def test_negative_returns_nbsp(self):
        """Negative lines returns non-breaking space (invisible bar)."""
        assert _lines_to_bar(-5, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "\u00a0"

    def test_one_to_five_lines(self):
        assert _lines_to_bar(1, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▃"
        assert _lines_to_bar(5, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▃"

    def test_six_to_fifteen_lines(self):
        assert _lines_to_bar(6, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▄"
        assert _lines_to_bar(15, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▄"

    def test_medium_changes(self):
        assert _lines_to_bar(16, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▅"
        assert _lines_to_bar(30, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▅"
        assert _lines_to_bar(31, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▆"
        assert _lines_to_bar(50, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▆"

    def test_large_changes(self):
        assert _lines_to_bar(51, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▇"
        assert _lines_to_bar(100, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "▇"
        assert _lines_to_bar(101, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "█"
        assert _lines_to_bar(201, LINE_BARS_CHARS, LINE_BARS_THRESHOLDS) == "█"


def render_with_styles(renderable, width: int = 40) -> list:
    """Render and return the list of Segments with their styles."""
    console = Console(width=width, force_terminal=True)
    lines = console.render_lines(renderable, pad=False)
    # Flatten all lines into single list of segments
    return [seg for line in lines for seg in line]


class TestTruncateLeftRendering:
    """Tests for TruncateLeft with grid frame composition."""

    def _framed(self, content, left: str = "[", right: str = "]", **kwargs):
        """Create a framed TruncateLeft using Table.grid."""
        from rich.table import Table

        events = TruncateLeft(content, **kwargs)
        grid = Table.grid(padding=0)
        grid.add_column()
        grid.add_column()
        grid.add_column()
        grid.add_row(Text(left), events, Text(right))
        return grid

    def test_empty_content_renders_brackets_only(self):
        framed = self._framed(Text(""))
        # Table.grid gives empty cells minimum width of 1
        assert render_plain(framed, width=10) == "[ ]"

    def test_single_text_exact_output(self):
        framed = self._framed(Text("ABC"))
        assert render_plain(framed, width=10) == "[ABC]"

    def test_truncation_keeps_most_recent(self):
        framed = self._framed(Text("ABCD"))
        # Width 4 = "[" + 2 chars + "]"
        assert render_plain(framed, width=4) == "[CD]"

    def test_truncation_with_styled_text(self):
        text = Text()
        text.append("AAA")
        text.append("BBB")
        text.append("CCC")
        framed = self._framed(text)
        # Width 7 = "[" + 5 chars + "]" = can fit "CCC" (3) + crop 2 from "BBB"
        assert render_plain(framed, width=7) == "[BBCCC]"

    def test_expand_mode_pads_left(self):
        framed = self._framed(Text("X"), expand=True)
        assert render_plain(framed, width=8) == "[     X]"

    def test_expand_mode_exact_fit(self):
        framed = self._framed(Text("ABC"), left="<", right=">", expand=True)
        assert render_plain(framed, width=5) == "<ABC>"

    def test_custom_brackets(self):
        framed = self._framed(Text("X"), left="<<", right=">>")
        assert render_plain(framed, width=10) == "<<X>>"

    def test_styled_text_plain_output(self):
        framed = self._framed(Text.from_markup("[red]R[/red]"))
        assert render_plain(framed, width=10) == "[R]"

    def test_overflow_crops_from_left(self):
        """When content overflows, it is cropped from left."""
        text = Text()
        text.append("AAA", style="on #ff0000")
        text.append("BBB", style="on #00ff00")
        text.append("CCC", style="on #0000ff")
        framed = self._framed(text)
        # Width 6 = "[" + 4 chars + "]" - fits CCC (3) + crop 1 char from BBB
        rendered_segments = render_with_styles(framed, width=6)

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
        """Cropping content preserves styles correctly."""
        text = Text()
        text.append("RRR", style="on #aa0000")
        text.append("BBB", style="on #0000aa")
        framed = self._framed(text)

        # Width 6 = "[" + 4 chars + "]" - fits BBB (3), crops 1 from RRR
        rendered_segments = render_with_styles(framed, width=6)

        # Cropped segment should be last char of RRR with red background
        crop_seg = rendered_segments[1]
        assert crop_seg.text == "R"
        assert crop_seg.style is not None
        assert "#aa0000" in str(crop_seg.style).lower()


# Default test config for events module
def make_test_events_config(**overrides) -> EventsConfig:
    """Create an EventsConfig for testing with ASCII icons."""
    defaults = {
        "type": "events",
        "theme": "nerd",
        "tool_icons": ASCII_TOOL_ICONS,
        "event_icons": ASCII_EVENT_ICONS,
        "bash_icons": ASCII_BASH_ICONS,
        "spacing": 0,
        "limit": 30,
        "left": "|",
        "right": "|",
        "brackets": True,
        "backgrounds": EventsBackgrounds(
            main="on #2a3a2a",
            user="on #3a2a2a",
            subagent="on #2a2a3a",
            edit_bar="#4c4d4e",
        ),
        "run_brackets": EventsRunBrackets(
            main=("[", "]"),
            user=("{", "}"),
            subagent=("<", ">"),
        ),
        "line_bars": EventsLineBars(
            chars=LINE_BARS_CHARS,
            thresholds=LINE_BARS_THRESHOLDS,
        ),
    }
    # Apply overrides
    for key, value in overrides.items():
        defaults[key] = value
    return EventsConfig(**defaults)


# Named configs to test with _render_events
TEST_CONFIGS = {
    "default": {},  # baseline (spacing=0)
    "spacing=1": {"spacing": 1},
}


class TestEventsModuleWithAsciiIcons:
    """Tests for EventsModule using ASCII icons for predictable output."""

    def _render_events(
        self, events: list[EventTuple], width: int = 30, **config_overrides
    ) -> dict[str, str]:
        """Render events with multiple configs, return dict of results."""
        module = get_module("events")
        assert module is not None
        inputs = {"events": EventsInfo(events=events)}

        results = {}
        for name, extra_overrides in TEST_CONFIGS.items():
            merged_overrides = {**config_overrides, **extra_overrides}
            config = make_test_events_config(**merged_overrides)
            result = module.render(inputs, config)
            results[name] = render_plain(result, width=width) if result else ""
        return results

    def test_empty_events_returns_empty_string(self):
        results = self._render_events([])
        assert results["default"] == ""
        assert results["spacing=1"] == ""

    def test_left_right_not_swapped(self):
        """Verify left and right frame brackets are in correct positions."""
        events: list[EventTuple] = [("PostToolUse", "Read", None, None)]
        results = self._render_events(events, width=15, left="(", right=")")
        assert results["default"] == "([R])"

    def test_single_read_tool(self):
        """Single tool renders as a main run."""
        events: list[EventTuple] = [("PostToolUse", "Read", None, None)]
        results = self._render_events(events, width=15)
        assert results["default"] == "|[R]|"
        assert results["spacing=1"] == "|[ R ]|"

    def test_single_edit_tool(self):
        events: list[EventTuple] = [("PostToolUse", "Edit", None, None)]
        results = self._render_events(events, width=15)
        assert results["default"] == "|[E]|"
        assert results["spacing=1"] == "|[ E ]|"

    def test_user_prompt_submit(self):
        events: list[EventTuple] = [("UserPromptSubmit", None, None, None)]
        # UserPromptSubmit is a user run
        results = self._render_events(events, width=15)
        assert results["default"] == "|{U}|"
        assert results["spacing=1"] == "|{ U }|"

    def test_stop_event(self):
        """Stop event alone is a main run."""
        events: list[EventTuple] = [("Stop", None, None, None)]
        results = self._render_events(events, width=15)
        assert results["default"] == "|[S]|"
        assert results["spacing=1"] == "|[ S ]|"

    def test_simple_turn_sequence(self):
        """UserPromptSubmit -> Read -> Stop becomes user run + main run."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
        ]
        # U is user run, R S is main run - uniform spacing within runs
        results = self._render_events(events, width=25)
        assert results["default"] == "|{U}[RS]|"
        assert results["spacing=1"] == "|{ U }[ R S ]|"

    def test_multiple_tools_in_turn(self):
        """UserPromptSubmit -> Glob -> Read -> Read -> Stop"""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Glob", None, None),
            ("PostToolUse", "Read", None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
        ]
        results = self._render_events(events, width=30)
        assert results["default"] == "|{U}[GRRS]|"
        assert results["spacing=1"] == "|{ U }[ G R R S ]|"

    def test_subagent_sequence(self):
        """UserPromptSubmit -> SubagentStart -> Read -> SubagentStop -> Stop"""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("SubagentStart", None, "a1", None),
            ("PostToolUse", "Read", "a1", None),
            ("SubagentStop", None, "a1", None),
            ("Stop", None, None, None),
        ]
        # user run (U) + main run with subagent markers (> R < S)
        # Subagent events are part of the main run
        results = self._render_events(events, width=35)
        assert results["default"] == "|{U}[>R<S]|"
        assert results["spacing=1"] == "|{ U }[ > R < S ]|"

    def test_bash_git_command(self):
        """Bash with git command uses git icon."""
        events: list[EventTuple] = [("PostToolUse", "Bash", None, "git status")]
        results = self._render_events(events, width=15)
        assert results["default"] == "|[g]|"
        assert results["spacing=1"] == "|[ g ]|"

    def test_bash_pytest_command(self):
        """Bash with pytest command uses pytest icon."""
        events: list[EventTuple] = [("PostToolUse", "Bash", None, "pytest tests/")]
        results = self._render_events(events, width=15)
        assert results["default"] == "|[p]|"
        assert results["spacing=1"] == "|[ p ]|"

    def test_bash_unknown_command_uses_default(self):
        """Bash with unknown command uses default bash icon."""
        events: list[EventTuple] = [("PostToolUse", "Bash", None, "echo hello")]
        results = self._render_events(events, width=15)
        assert results["default"] == "|[$]|"
        assert results["spacing=1"] == "|[ $ ]|"

    def test_explicit_interrupt(self):
        """PostToolUseFailure with interrupt extra goes to user run."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("PostToolUseFailure", None, None, "interrupt"),
        ]
        # user run (U) + main run (R) + user run (X)
        results = self._render_events(events, width=30)
        assert results["default"] == "|{U}[R]{X}|"
        assert results["spacing=1"] == "|{ U }[ R ]{ X }|"

    def test_inferred_interrupt(self):
        """UserPromptSubmit without prior Stop infers interrupt."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            # No Stop here - next UserPromptSubmit infers interrupt
            ("UserPromptSubmit", None, None, None),
            ("Stop", None, None, None),
        ]
        # Synthetic interrupt inserted: user(U) + main(R) + user(X) + user(U) + main(S)
        results = self._render_events(events, width=40)
        assert results["default"] == "|{U}[R]{X}{U}[S]|"
        assert results["spacing=1"] == "|{ U }[ R ]{ X }{ U }[ S ]|"

    def test_skip_redundant_subagent_stop(self):
        """SubagentStop immediately after Stop is skipped."""
        events: list[EventTuple] = [
            ("UserPromptSubmit", None, None, None),
            ("PostToolUse", "Read", None, None),
            ("Stop", None, None, None),
            ("SubagentStop", None, None, None),  # Should be skipped
        ]
        # SubagentStop skipped: user(U) + main(R S)
        results = self._render_events(events, width=25)
        assert results["default"] == "|{U}[RS]|"
        assert results["spacing=1"] == "|{ U }[ R S ]|"

    def test_limit_truncates_events(self):
        """Limit parameter truncates older events."""
        events: list[EventTuple] = [
            ("PostToolUse", "Glob", None, None),
            ("PostToolUse", "Read", None, None),
            ("PostToolUse", "Edit", None, None),
            ("PostToolUse", "Write", None, None),
        ]
        # With limit=2, should only process last 2 events
        results = self._render_events(events, width=20, limit=2)
        assert results["default"] == "|[EW]|"
        assert results["spacing=1"] == "|[ E W ]|"

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
        # user(U) + main(R S) + user(U) + main(E S)
        results = self._render_events(events, width=40)
        assert results["default"] == "|{U}[RS]{U}[ES]|"
        assert results["spacing=1"] == "|{ U }[ R S ]{ U }[ E S ]|"



class TestEventToIcon:
    """Tests for _event_to_icon method with ASCII icons."""

    def _get_icon(self, event: str, tool: str | None, extra: str | None) -> str:
        """Get the plain text icon for an event."""
        from statusline.modules.events import EventsModule

        module = EventsModule()
        backgrounds = EventsBackgrounds(
            main="on #2a3a2a",
            user="on #3a2a2a",
            subagent="on #2a2a3a",
            edit_bar="#4c4d4e",
        )
        line_bars = EventsLineBars(
            chars=LINE_BARS_CHARS,
            thresholds=LINE_BARS_THRESHOLDS,
        )
        text = module._event_to_icon(
            event,
            tool,
            extra,
            ASCII_TOOL_ICONS,
            ASCII_EVENT_ICONS,
            ASCII_BASH_ICONS,
            backgrounds,
            line_bars,
        )
        return text.plain if text else ""

    def test_read_tool(self):
        assert self._get_icon("PostToolUse", "Read", None) == "R"

    def test_edit_tool(self):
        assert self._get_icon("PostToolUse", "Edit", None) == "E"

    def test_bash_git(self):
        assert self._get_icon("PostToolUse", "Bash", "git status") == "g"

    def test_bash_default(self):
        assert self._get_icon("PostToolUse", "Bash", "ls -la") == "$"

    def test_user_prompt(self):
        assert self._get_icon("UserPromptSubmit", None, None) == "U"

    def test_stop(self):
        assert self._get_icon("Stop", None, None) == "S"

    def test_subagent_start(self):
        assert self._get_icon("SubagentStart", None, None) == ">"

    def test_subagent_stop(self):
        assert self._get_icon("SubagentStop", None, None) == "<"

    def test_interrupt(self):
        assert self._get_icon("PostToolUseFailure", None, "interrupt") == "X"

    def test_unknown_event(self):
        assert self._get_icon("UnknownEvent", None, None) == ""


class TestEditWithLineCounts:
    """Tests for Edit events with line count bars."""

    def _get_icon_call_args(self):
        """Get the common arguments for _event_to_icon calls."""
        return (
            ASCII_TOOL_ICONS,
            ASCII_EVENT_ICONS,
            ASCII_BASH_ICONS,
            EventsBackgrounds(
                main="on #2a3a2a",
                user="on #3a2a2a",
                subagent="on #2a2a3a",
                edit_bar="#4c4d4e",
            ),
            EventsLineBars(
                chars=LINE_BARS_CHARS,
                thresholds=LINE_BARS_THRESHOLDS,
            ),
        )

    def test_edit_with_additions_only(self):
        """Edit with only additions shows green bar + placeholder space."""
        from statusline.modules.events import EventsModule

        module = EventsModule()
        text = module._event_to_icon(
            "PostToolUse", "Edit", "+10-0", *self._get_icon_call_args()
        )
        assert text is not None
        plain = text.plain
        # Should have edit icon + green bar + placeholder space for deletions
        assert "▄" in plain  # 10 lines -> ▄
        # Always 2 bar positions: icon(1) + bars(2) = 3
        assert text.cell_len == 3, f"Expected width 3 but got {text.cell_len}"

    def test_edit_with_deletions_only(self):
        """Edit with only deletions shows placeholder space + red bar."""
        from statusline.modules.events import EventsModule

        module = EventsModule()
        text = module._event_to_icon(
            "PostToolUse", "Edit", "+0-50", *self._get_icon_call_args()
        )
        assert text is not None
        plain = text.plain
        # Should have edit icon + placeholder space + red bar
        assert "▆" in plain  # 50 lines -> ▆
        # Always 2 bar positions: icon(1) + bars(2) = 3
        assert text.cell_len == 3, f"Expected width 3 but got {text.cell_len}"

    def test_edit_bars_always_two_positions(self):
        """Edit bars always occupy 2 character positions."""
        from statusline.modules.events import EventsModule

        module = EventsModule()
        args = self._get_icon_call_args()

        # +5-2: both bars visible
        text1 = module._event_to_icon("PostToolUse", "Edit", "+5-2", *args)
        # +10-0: addition bar + placeholder
        text2 = module._event_to_icon("PostToolUse", "Edit", "+10-0", *args)
        # +0-10: placeholder + deletion bar
        text3 = module._event_to_icon("PostToolUse", "Edit", "+0-10", *args)

        # All should have same width: icon(1) + bars(2) = 3
        assert text1.cell_len == text2.cell_len == text3.cell_len == 3, (
            f"Widths differ: {text1.cell_len}, {text2.cell_len}, {text3.cell_len}"
        )

    def test_edit_with_both(self):
        from statusline.modules.events import EventsModule

        module = EventsModule()
        text = module._event_to_icon(
            "PostToolUse", "Edit", "+100-5", *self._get_icon_call_args()
        )
        assert text is not None
        plain = text.plain
        # Should have both bars
        assert "▇" in plain  # 100 lines -> ▇
        assert "▃" in plain  # 5 lines -> ▃

    def test_edit_bars_have_edit_bar_background(self):
        """Edit bars should have edit_bar background, not segment background."""
        from statusline.modules.events import EventsModule

        module = EventsModule()
        text = module._event_to_icon(
            "PostToolUse", "Edit", "+5-2", *self._get_icon_call_args()
        )
        assert text is not None

        # Check that the bar spans have the edit_bar background
        # Rich stores styles, we need to check the markup or spans
        markup = text.markup
        # The bars should have "on #4c4d4e" in their style
        assert "on #4c4d4e" in markup, f"Bars missing edit_bar background: {markup}"

    def test_edit_bars_keep_background_after_segment_styling(self):
        """When segment background is applied, bars should keep their own background."""
        from statusline.input import EventsInfo, EventTuple
        from statusline.modules import get_module

        # Render a full event with Edit in a segment
        events: list[EventTuple] = [
            ("PostToolUse", "Edit", None, "+5-2"),
        ]
        module = get_module("events")
        assert module is not None

        # Render with a custom edit_bar background
        config = make_test_events_config(
            backgrounds=EventsBackgrounds(
                main="on #2a3a2a",
                user="on #3a2a2a",
                subagent="on #2a2a3a",
                edit_bar="#abcdef",
            )
        )
        result = module.render(
            {"events": EventsInfo(events=events)},
            config,
        )

        # Get the segments and check bar backgrounds
        from rich.console import Console

        console = Console(force_terminal=True, width=80)
        lines = console.render_lines(result, pad=False)
        segments = [seg for line in lines for seg in line]

        # The bar background should be #abcdef (171, 205, 239), not main bg #2a3a2a
        # Check that we have segments with the edit_bar background color
        found_edit_bar_bg = False
        for seg in segments:
            if seg.style and seg.style.bgcolor:
                # Check if bgcolor has the RGB values for #abcdef
                if hasattr(seg.style.bgcolor, "triplet"):
                    triplet = seg.style.bgcolor.triplet
                    if (
                        triplet.red == 171
                        and triplet.green == 205
                        and triplet.blue == 239
                    ):
                        found_edit_bar_bg = True
                        break

        assert found_edit_bar_bg, (
            f"Edit bar background not found in segments: {segments}"
        )


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
    """Verify all expected icons are defined in defaults.toml."""

    def test_all_tools_have_icons(self):
        from statusline.config import EventsConfig, load_config

        config = load_config()
        events_config = config.get_module_config("events")
        assert events_config is not None
        assert isinstance(events_config, EventsConfig)
        tool_icons = events_config.tool_icons
        expected = [
            "Bash",
            "Edit",
            "Write",
            "Read",
            "Glob",
            "Grep",
            "Task",
            "WebFetch",
            "WebSearch",
        ]
        for tool in expected:
            assert tool in tool_icons, f"Missing tool icon: {tool}"

    def test_all_events_have_icons(self):
        from statusline.config import EventsConfig, load_config

        config = load_config()
        events_config = config.get_module_config("events")
        assert events_config is not None
        assert isinstance(events_config, EventsConfig)
        event_icons = events_config.event_icons
        # Note: PostToolUse and PostToolUseFailure intentionally don't have icons
        # (they use tool_icons instead)
        expected = [
            "SubagentStart",
            "SubagentStop",
            "UserPromptSubmit",
            "Stop",
            "Interrupt",
        ]
        for event in expected:
            assert event in event_icons, f"Missing event icon: {event}"

    def test_common_bash_commands_have_icons(self):
        from statusline.config import EventsConfig, load_config

        config = load_config()
        events_config = config.get_module_config("events")
        assert events_config is not None
        assert isinstance(events_config, EventsConfig)
        bash_icons = events_config.bash_icons
        expected = ["git", "cargo", "uv", "python", "pytest", "npm", "docker"]
        for cmd in expected:
            assert cmd in bash_icons, f"Missing bash icon: {cmd}"


class TestSpacingAfterTurnEnd:
    """Regression tests for spacing after turn-end events (Stop, SubagentStop).

    Turn-end events have trailing boundary padding, so the next icon should NOT
    get additional prefix spacing to avoid double-spacing.
    """

    def _render_events_plain(self, events: list[EventTuple], spacing: int = 1) -> str:
        """Render events and return plain text (no ANSI codes)."""
        import re
        from io import StringIO

        from rich.console import Console

        from statusline.input import EventsInfo
        from statusline.modules.events import EventsModule

        module = EventsModule()
        config = make_test_events_config(spacing=spacing)
        result = module.render(
            {"events": EventsInfo(events=events)},
            config,
        )
        # Convert Rich renderable to text
        console = Console(file=StringIO(), force_terminal=True, width=200)
        console.print(result, end="")
        raw = console.file.getvalue()
        # Strip ANSI escape codes
        return re.sub(r"\x1b\[[0-9;]*m", "", raw)

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
        assert "    " not in plain, (
            f"Found 4+ consecutive spaces (double spacing bug): {repr(plain)}"
        )

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
        assert "    " not in plain, (
            f"Found 4+ consecutive spaces (double spacing bug): {repr(plain)}"
        )


class TestStopUndoneDetection:
    """Tests for detecting Stop events that were cancelled by hooks."""

    def _render_events_plain(self, events: list[EventTuple]) -> str:
        """Render events and return plain text (no ANSI codes)."""
        import re
        from io import StringIO

        from rich.console import Console

        from statusline.input import EventsInfo
        from statusline.modules.events import EventsModule

        module = EventsModule()
        config = make_test_events_config(spacing=0)
        result = module.render({"events": EventsInfo(events=events)}, config)

        console = Console(file=StringIO(), force_terminal=True, width=200)
        console.print(result, end="")
        raw = console.file.getvalue()
        return re.sub(r"\x1b\[[0-9;]*m", "", raw)

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
        # With spacing=0, they should be directly adjacent
        assert bash_pos == undo_pos + 1, f"StopUndone spacing wrong: {repr(plain)}"
