"""Unit tests for statusline style."""

import pytest

from statusline.style import render_to_ansi


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
