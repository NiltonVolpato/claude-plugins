"""Tests for event renderables."""

import pytest
from rich.console import Console
from rich.text import Text

from statusline.config import EventsBackgrounds, EventsLineBars
from statusline.modules.events.event import (
    BashEvent,
    EditEvent,
    EventData,
    EventStyle,
    IconEvent,
    InterruptEvent,
    _lines_to_bar,
    create_event,
)


@pytest.fixture
def style() -> EventStyle:
    """Create a test EventStyle."""
    return EventStyle(
        tool_icons={
            "Bash": "[bright_black]B[/]\u00a0",
            "Edit": "[yellow]E[/]\u00a0",
            "Read": "[cyan]R[/]\u00a0",
            "TaskUpdate": "[yellow]T[/]\u00a0",
            "TaskUpdate:completed": "[green]✓[/]\u00a0",
            "TaskUpdate:other": "[yellow]~[/]\u00a0",
        },
        event_icons={
            "Stop": "[green]S[/]\u00a0",
            "UserPromptSubmit": "[white]U[/]\u00a0",
            "Interrupt": "[red]![/]\u00a0",
        },
        bash_icons={
            "git": "[#f05032]G[/]\u00a0",
            "pytest": "[yellow]P[/]\u00a0",
        },
        backgrounds=EventsBackgrounds(
            main="on #2a3a2a",
            user="on #3a2a2a",
            subagent="on #2a2a3a",
            edit_bar="#4c4d4e",
        ),
        line_bars=EventsLineBars(
            chars="▂▃▄▅▆▇█",
            thresholds=[1, 6, 16, 31, 51, 101, 201],
        ),
    )


def render_to_text(renderable) -> str:
    """Render a Rich renderable to plain text."""
    console = Console(force_terminal=True, width=80)
    with console.capture() as capture:
        console.print(renderable, end="")
    return capture.get()


class TestEventData:
    def test_effective_event_defaults_to_event(self):
        data = EventData(event="Stop")
        assert data.effective_event == "Stop"

    def test_effective_event_can_be_overridden(self):
        data = EventData(event="Stop", effective_event="StopUndone")
        assert data.effective_event == "StopUndone"

    def test_tool_event(self):
        data = EventData(event="PostToolUse", tool="Read")
        assert data.tool == "Read"
        assert data.event == "PostToolUse"


class TestIconEvent:
    def test_tool_icon(self, style):
        data = EventData(event="PostToolUse", tool="Read")
        event = IconEvent(data, style)
        output = render_to_text(event)
        assert "R" in output

    def test_event_icon(self, style):
        data = EventData(event="Stop")
        event = IconEvent(data, style)
        output = render_to_text(event)
        assert "S" in output

    def test_task_update_completed(self, style):
        data = EventData(event="PostToolUse", tool="TaskUpdate", extra="status=completed")
        event = IconEvent(data, style)
        output = render_to_text(event)
        assert "✓" in output

    def test_task_update_other(self, style):
        data = EventData(event="PostToolUse", tool="TaskUpdate", extra="status=in_progress")
        event = IconEvent(data, style)
        output = render_to_text(event)
        assert "~" in output


class TestBashEvent:
    def test_command_specific_icon(self, style):
        data = EventData(event="PostToolUse", tool="Bash", extra="git status")
        event = BashEvent(data, style)
        output = render_to_text(event)
        assert "G" in output  # git icon

    def test_command_with_path(self, style):
        data = EventData(event="PostToolUse", tool="Bash", extra="/usr/bin/git status")
        event = BashEvent(data, style)
        output = render_to_text(event)
        assert "G" in output  # git icon (path stripped)

    def test_unknown_command_fallback(self, style):
        data = EventData(event="PostToolUse", tool="Bash", extra="some_unknown_cmd")
        event = BashEvent(data, style)
        output = render_to_text(event)
        assert "B" in output  # generic Bash icon


class TestEditEvent:
    def test_edit_with_line_bars(self, style):
        data = EventData(event="PostToolUse", tool="Edit", extra="+10-5")
        event = EditEvent(data, style)
        output = render_to_text(event)
        assert "E" in output  # Edit icon
        # Should have bar characters
        assert "▃" in output or "▄" in output  # line bar chars

    def test_edit_no_extra(self, style):
        data = EventData(event="PostToolUse", tool="Edit")
        event = EditEvent(data, style)
        output = render_to_text(event)
        assert "E" in output


class TestInterruptEvent:
    def test_interrupt_icon(self, style):
        data = EventData(event="PostToolUseFailure", extra="interrupt")
        event = InterruptEvent(data, style)
        output = render_to_text(event)
        assert "!" in output


class TestCreateEvent:
    def test_creates_interrupt_event(self, style):
        data = EventData(event="PostToolUseFailure", extra="interrupt")
        event = create_event(data, style)
        assert isinstance(event, InterruptEvent)

    def test_creates_bash_event(self, style):
        data = EventData(event="PostToolUse", tool="Bash", extra="git status")
        event = create_event(data, style)
        assert isinstance(event, BashEvent)

    def test_creates_edit_event(self, style):
        data = EventData(event="PostToolUse", tool="Edit", extra="+5-3")
        event = create_event(data, style)
        assert isinstance(event, EditEvent)

    def test_creates_icon_event_for_other_tools(self, style):
        data = EventData(event="PostToolUse", tool="Read")
        event = create_event(data, style)
        assert isinstance(event, IconEvent)

    def test_creates_icon_event_for_non_tool(self, style):
        data = EventData(event="Stop")
        event = create_event(data, style)
        assert isinstance(event, IconEvent)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEventDataEdgeCases:
    """Edge cases for EventData validation and defaults."""

    def test_empty_event_string(self):
        """Empty event string should be accepted (tool events may have empty event)."""
        data = EventData(event="")
        assert data.event == ""
        # effective_event defaults to event, so also empty
        assert data.effective_event == ""

    def test_empty_effective_event_defaults_to_event(self):
        """Explicitly passing empty string for effective_event should default to event."""
        data = EventData(event="Stop", effective_event="")
        # model_post_init sets effective_event to event when empty
        assert data.effective_event == "Stop"

    def test_none_optional_fields(self):
        """None values for optional fields should be accepted."""
        data = EventData(event="PostToolUse", tool=None, agent_id=None, extra=None)
        assert data.tool is None
        assert data.agent_id is None
        assert data.extra is None

    def test_unicode_event_name(self):
        """Unicode characters in event name should work."""
        data = EventData(event="Stop\u200b")  # Zero-width space
        assert data.event == "Stop\u200b"
        assert data.effective_event == "Stop\u200b"

    def test_unicode_extra_field(self):
        """Unicode in extra field (e.g., file paths with unicode)."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+5-3 /tmp/\u4e2d\u6587.txt")
        assert "\u4e2d\u6587" in data.extra

    def test_whitespace_only_event(self):
        """Whitespace-only event string (edge case, likely invalid but should not crash)."""
        data = EventData(event="   ")
        assert data.event == "   "
        assert data.effective_event == "   "

    def test_very_long_extra_field(self):
        """Very long extra field (stress test for memory/performance)."""
        long_extra = "x" * 10000
        data = EventData(event="PostToolUse", tool="Bash", extra=long_extra)
        assert len(data.extra) == 10000


class TestEditEventParsingEdgeCases:
    """Edge cases for EditEvent._parse_line_counts parsing."""

    def test_parse_plus_only(self, style):
        """'+' alone should return 0, 0 (empty strings become 0)."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        # parts = [''], empty string is falsy so returns 0
        assert added == 0
        assert removed == 0

    def test_parse_plus_minus_only(self, style):
        """'+-' should parse as added=0, removed=0 (empty strings become 0)."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+-")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        # parts = ['', ''], both empty -> 0
        assert added == 0
        assert removed == 0

    def test_parse_zero_lines(self, style):
        """'+0-0' should parse correctly as zero added and removed."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+0-0")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        assert added == 0
        assert removed == 0

    def test_parse_non_numeric_values(self, style):
        """'+abc-def' should return None, None (ValueError on int conversion)."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+abc-def")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        assert added is None
        assert removed is None

    def test_parse_missing_plus_prefix(self, style):
        """'10-5' without leading '+' should return None, None."""
        data = EventData(event="PostToolUse", tool="Edit", extra="10-5")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        assert added is None
        assert removed is None

    def test_parse_leading_minus(self, style):
        """'-5-10' should return None, None (doesn't start with '+')."""
        data = EventData(event="PostToolUse", tool="Edit", extra="-5-10")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        assert added is None
        assert removed is None

    def test_parse_added_only_no_minus(self, style):
        """'+10' with no minus should parse as added=10, removed=0."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+10")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        # parts = ['10'], len(parts) == 1, so removed = 0
        assert added == 10
        assert removed == 0

    def test_parse_trailing_minus(self, style):
        """'+10-' should parse as added=10, removed=0 (empty string)."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+10-")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        assert added == 10
        assert removed == 0

    def test_parse_huge_numbers(self, style):
        """Very large numbers should parse without overflow."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+999999999-888888888")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        assert added == 999999999
        assert removed == 888888888

    def test_parse_negative_in_added(self, style):
        """'+-5-10' parses as added=0, removed=5 due to split behavior."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+-5-10")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        # extra[1:] = "-5-10", split("-") = ['', '5', '10']
        # parts[0] = '' (empty, falsy) -> added = 0
        # parts[1] = '5' -> removed = 5
        assert added == 0
        assert removed == 5

    def test_parse_multiple_minus_signs(self, style):
        """'+10-5-3' has multiple '-' signs, split gives ['10', '5', '3']."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+10-5-3")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        # Only first two parts used
        assert added == 10
        assert removed == 5

    def test_parse_float_values(self, style):
        """'+1.5-2.3' should return None, None (int() fails on floats)."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+1.5-2.3")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        assert added is None
        assert removed is None

    def test_parse_whitespace_in_numbers(self, style):
        """'+ 10 - 5' with whitespace parses successfully (int strips whitespace)."""
        data = EventData(event="PostToolUse", tool="Edit", extra="+ 10 - 5")
        event = EditEvent(data, style)
        added, removed = event._parse_line_counts()
        # Python's int() strips leading/trailing whitespace
        # extra[1:] = " 10 - 5", split("-") = [' 10 ', ' 5']
        assert added == 10
        assert removed == 5

    def test_edit_renders_with_malformed_extra(self, style):
        """EditEvent should still render icon even with malformed extra."""
        data = EventData(event="PostToolUse", tool="Edit", extra="garbage")
        event = EditEvent(data, style)
        output = render_to_text(event)
        # Should have Edit icon, no bars
        assert "E" in output
        # Should NOT have bar characters (only icon)
        assert "▂" not in output


class TestBashEventEdgeCases:
    """Edge cases for BashEvent command parsing."""

    def test_empty_extra(self, style):
        """Empty extra string should fall back to generic Bash icon."""
        data = EventData(event="PostToolUse", tool="Bash", extra="")
        event = BashEvent(data, style)
        output = render_to_text(event)
        assert "B" in output

    def test_none_extra(self, style):
        """None extra should fall back to generic Bash icon."""
        data = EventData(event="PostToolUse", tool="Bash", extra=None)
        event = BashEvent(data, style)
        output = render_to_text(event)
        assert "B" in output

    def test_whitespace_only_extra(self, style):
        """Whitespace-only extra should fall back to generic Bash icon."""
        data = EventData(event="PostToolUse", tool="Bash", extra="   ")
        event = BashEvent(data, style)
        output = render_to_text(event)
        # split() on whitespace gives [], so falls back
        assert "B" in output

    def test_only_path_separators(self, style):
        """Extra with only path separators like '///' should get empty cmd."""
        data = EventData(event="PostToolUse", tool="Bash", extra="///")
        event = BashEvent(data, style)
        output = render_to_text(event)
        # cmd = ''.split('/')[-1] = '', not in bash_icons, falls back
        assert "B" in output

    def test_command_with_leading_spaces(self, style):
        """Extra with leading spaces should still parse command."""
        data = EventData(event="PostToolUse", tool="Bash", extra="  git status")
        event = BashEvent(data, style)
        output = render_to_text(event)
        # split() handles leading whitespace
        assert "G" in output

    def test_command_only_no_args(self, style):
        """Single command with no arguments."""
        data = EventData(event="PostToolUse", tool="Bash", extra="pytest")
        event = BashEvent(data, style)
        output = render_to_text(event)
        assert "P" in output

    def test_very_long_command(self, style):
        """Very long command string should not crash."""
        long_cmd = "git " + "a" * 10000
        data = EventData(event="PostToolUse", tool="Bash", extra=long_cmd)
        event = BashEvent(data, style)
        output = render_to_text(event)
        assert "G" in output


class TestIconFallbacks:
    """Tests for icon fallback behavior when icons are missing."""

    def test_missing_tool_icon_fallback(self, style):
        """Unknown tool should fall back to bullet character."""
        data = EventData(event="PostToolUse", tool="UnknownTool")
        event = IconEvent(data, style)
        output = render_to_text(event)
        # Default fallback is bullet
        assert "\u2022" in output  # Unicode bullet

    def test_missing_event_icon_returns_empty(self, style):
        """Unknown event should return empty string (no output)."""
        data = EventData(event="UnknownEvent")
        event = IconEvent(data, style)
        output = render_to_text(event)
        # No icon configured, _get_icon returns '', no output
        assert output == ""

    def test_missing_bash_icon_fallback(self):
        """Unknown bash command should fall back to generic Bash icon."""
        # Create style with no Bash icon to test ultimate fallback
        style_no_bash = EventStyle(
            tool_icons={},  # No Bash icon either
            event_icons={},
            bash_icons={},
            backgrounds=EventsBackgrounds(
                main="", user="", subagent="", edit_bar=""
            ),
            line_bars=EventsLineBars(chars="x", thresholds=[1]),
        )
        data = EventData(event="PostToolUse", tool="Bash", extra="unknown_cmd")
        event = BashEvent(data, style_no_bash)
        output = render_to_text(event)
        # Falls back to tool_icons.get("Bash", bullet) -> bullet
        assert "\u2022" in output

    def test_missing_interrupt_icon_no_output(self):
        """Missing Interrupt icon should yield nothing."""
        style_no_interrupt = EventStyle(
            tool_icons={},
            event_icons={},  # No Interrupt icon
            bash_icons={},
            backgrounds=EventsBackgrounds(
                main="", user="", subagent="", edit_bar=""
            ),
            line_bars=EventsLineBars(chars="x", thresholds=[1]),
        )
        data = EventData(event="PostToolUseFailure", extra="interrupt")
        event = InterruptEvent(data, style_no_interrupt)
        output = render_to_text(event)
        # No icon, yields nothing
        assert output == ""

    def test_missing_edit_icon_fallback(self):
        """Missing Edit icon should use default pencil."""
        style_no_edit = EventStyle(
            tool_icons={},  # No Edit icon
            event_icons={},
            bash_icons={},
            backgrounds=EventsBackgrounds(
                main="", user="", subagent="", edit_bar="black"
            ),
            line_bars=EventsLineBars(chars="x", thresholds=[1]),
        )
        data = EventData(event="PostToolUse", tool="Edit", extra="+5-3")
        event = EditEvent(data, style_no_edit)
        output = render_to_text(event)
        # Falls back to default pencil
        assert "\u270f" in output  # Pencil character


class TestLinesToBarEdgeCases:
    """Direct tests for _lines_to_bar function."""

    def test_zero_count_returns_nbsp(self):
        """Zero count should return non-breaking space."""
        result = _lines_to_bar(0, "abc", [1, 5, 10])
        assert result == "\u00a0"

    def test_negative_count_returns_nbsp(self):
        """Negative count should return non-breaking space."""
        result = _lines_to_bar(-5, "abc", [1, 5, 10])
        assert result == "\u00a0"

    def test_count_below_first_threshold(self):
        """Count below first threshold should return first char."""
        # If thresholds start at 1, count=0 returns nbsp (handled above)
        # But if thresholds start at 5, count=1 should return first char
        result = _lines_to_bar(1, "abc", [5, 10, 20])
        assert result == "a"

    def test_count_at_exact_threshold(self):
        """Count exactly at threshold boundary should move to next char."""
        # count=5, thresholds=[5, 10], chars="ab"
        # 5 is NOT < 5, so skips 'a'; 5 < 10, returns 'b'
        result = _lines_to_bar(5, "ab", [5, 10])
        assert result == "b"

    def test_count_above_all_thresholds(self):
        """Count above all thresholds should return last char."""
        result = _lines_to_bar(1000, "abc", [1, 5, 10])
        assert result == "c"

    def test_single_threshold(self):
        """Single threshold should work correctly."""
        # count=5, threshold=[10], chars="x"
        # 5 < 10, returns 'x'
        result = _lines_to_bar(5, "x", [10])
        assert result == "x"
        # count=15, threshold=[10], chars="x"
        # 15 >= 10, returns last char 'x'
        result = _lines_to_bar(15, "x", [10])
        assert result == "x"

    def test_empty_thresholds_returns_last_char(self):
        """Empty thresholds list should return last char immediately."""
        result = _lines_to_bar(5, "abc", [])
        # Loop doesn't iterate, returns chars[-1]
        assert result == "c"

    def test_huge_count_no_overflow(self):
        """Very large count should not cause issues."""
        result = _lines_to_bar(10**18, "xyz", [1, 100, 10000])
        assert result == "z"


class TestTaskUpdateEdgeCases:
    """Edge cases for TaskUpdate icon selection."""

    def test_task_update_no_extra(self, style):
        """TaskUpdate with no extra should use generic TaskUpdate icon."""
        data = EventData(event="PostToolUse", tool="TaskUpdate", extra=None)
        event = IconEvent(data, style)
        output = render_to_text(event)
        # No "status=" prefix, so gets generic TaskUpdate icon
        assert "T" in output

    def test_task_update_empty_extra(self, style):
        """TaskUpdate with empty extra should use generic icon."""
        data = EventData(event="PostToolUse", tool="TaskUpdate", extra="")
        event = IconEvent(data, style)
        output = render_to_text(event)
        assert "T" in output

    def test_task_update_status_prefix_no_value(self, style):
        """TaskUpdate with 'status=' but no value should use 'other' icon."""
        data = EventData(event="PostToolUse", tool="TaskUpdate", extra="status=")
        event = IconEvent(data, style)
        output = render_to_text(event)
        # status = '' (empty), not 'completed', so 'other'
        assert "~" in output

    def test_task_update_status_unknown(self, style):
        """TaskUpdate with unknown status should use 'other' icon."""
        data = EventData(event="PostToolUse", tool="TaskUpdate", extra="status=unknown_status")
        event = IconEvent(data, style)
        output = render_to_text(event)
        assert "~" in output


class TestCreateEventEdgeCases:
    """Edge cases for the create_event factory function."""

    def test_tool_with_empty_event(self, style):
        """Tool with empty event string should be treated as tool event."""
        data = EventData(event="", tool="Read")
        event = create_event(data, style)
        assert isinstance(event, IconEvent)
        output = render_to_text(event)
        assert "R" in output

    def test_post_tool_use_failure_not_interrupt(self, style):
        """PostToolUseFailure with non-interrupt extra should be IconEvent."""
        data = EventData(event="PostToolUseFailure", extra="timeout")
        event = create_event(data, style)
        # Not an interrupt, so becomes IconEvent
        assert isinstance(event, IconEvent)

    def test_post_tool_use_failure_with_tool(self, style):
        """PostToolUseFailure with tool and interrupt should still be InterruptEvent."""
        data = EventData(event="PostToolUseFailure", tool="Bash", extra="interrupt")
        event = create_event(data, style)
        # Interrupt detection happens first
        assert isinstance(event, InterruptEvent)
