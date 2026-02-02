"""Unit tests for statusline templates."""

from statusline.templates import render_template


class TestFormatProgressBar:
    def test_green_under_70_percent(self):
        result = render_template("{{ value | format_progress_bar }}", {"value": 42})
        assert "[green]" in result
        assert "████" in result
        assert "42%" in result

    def test_yellow_at_70_percent(self):
        result = render_template("{{ value | format_progress_bar }}", {"value": 70})
        assert "[yellow]" in result
        assert "70%" in result

    def test_yellow_at_84_percent(self):
        result = render_template("{{ value | format_progress_bar }}", {"value": 84})
        assert "[yellow]" in result
        assert "84%" in result

    def test_red_at_85_percent(self):
        result = render_template("{{ value | format_progress_bar }}", {"value": 85})
        assert "[red]" in result
        assert "85%" in result

    def test_red_at_100_percent(self):
        result = render_template("{{ value | format_progress_bar }}", {"value": 100})
        assert "[red]" in result
        assert "██████████" in result
        assert "100%" in result

    def test_zero_percent(self):
        result = render_template("{{ value | format_progress_bar }}", {"value": 0})
        assert "[green]" in result
        assert "0%" in result
