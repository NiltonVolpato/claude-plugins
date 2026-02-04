"""Unit tests for statusline style."""

from unittest import mock

import pytest

from statusline.style import CLAUDE_CODE_PADDING, get_terminal_width, render_to_ansi


class TestRenderToAnsi:
    def test_no_color_strips_markup(self):
        result = render_to_ansi("[cyan]test[/cyan]", use_color=False)
        assert result == "test"
        assert "\x1b[" not in result  # No ANSI codes

    def test_with_color_includes_ansi(self):
        result = render_to_ansi("[cyan]test[/cyan]", use_color=True)
        assert "test" in result
        # Should contain some ANSI escape sequence
        assert "\x1b[" in result

    def test_plain_text_unchanged(self):
        result = render_to_ansi("plain text", use_color=False)
        assert result == "plain text"

    def test_nested_markup(self):
        result = render_to_ansi("[bold][cyan]text[/cyan][/bold]", use_color=False)
        assert result == "text"

    def test_empty_string(self):
        result = render_to_ansi("", use_color=True)
        assert result == ""

    def test_custom_width(self):
        result = render_to_ansi("hello", use_color=False, width=80)
        assert result == "hello"

    def test_rich_renderable(self):
        """render_to_ansi accepts non-string Rich renderables."""
        from rich.table import Table

        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="right")
        grid.add_row("left", "right")
        result = render_to_ansi(grid, use_color=False, width=40)
        assert "left" in result
        assert "right" in result


class TestGetTerminalWidth:
    def test_config_width_takes_priority(self):
        assert get_terminal_width(100) == 100

    def test_columns_env(self):
        with mock.patch.dict("os.environ", {"COLUMNS": "120"}):
            assert get_terminal_width() == 120 - CLAUDE_CODE_PADDING

    def test_columns_env_non_numeric_ignored(self):
        with mock.patch.dict("os.environ", {"COLUMNS": "abc"}):
            # Should fall through to tty or default
            result = get_terminal_width()
            assert isinstance(result, int)

    def test_fallback_to_80(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch("os.open", side_effect=OSError):
                assert get_terminal_width() == 80
