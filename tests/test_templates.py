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

    def test_custom_bar_chars(self):
        bar = {"full": "#", "empty": ".", "left": "[", "right": "]"}
        result = render_template(
            "{{ value | format_progress_bar(bar) }}", {"value": 50, "bar": bar}
        )
        assert "#####....." in result
        assert "50%" in result

    def test_no_caps(self):
        bar = {"left": "", "right": ""}
        result = render_template(
            "{{ value | format_progress_bar(bar) }}", {"value": 50, "bar": bar}
        )
        assert "█████" in result
        assert "\\[" not in result

    def test_asymmetric_caps(self):
        """Nerd font style: different caps based on fill state."""
        bar = {
            "full": "F", "empty": "E",
            "full_left": "A", "empty_left": "a",
            "full_right": "Z", "empty_right": "z",
        }
        # Partial fill: full_left + filled + empty + empty_right
        result = render_template(
            "{{ value | format_progress_bar(bar) }}", {"value": 40, "bar": bar}
        )
        assert "AFFFFEEEEEEz" in result

        # 100%: full_left + filled + full_right
        result = render_template(
            "{{ value | format_progress_bar(bar) }}", {"value": 100, "bar": bar}
        )
        assert "AFFFFFFFFFFZ" in result

        # 0%: empty_left + empty + empty_right
        result = render_template(
            "{{ value | format_progress_bar(bar) }}", {"value": 0, "bar": bar}
        )
        assert "aEEEEEEEEEEz" in result

    def test_custom_width(self):
        bar = {"width": 5, "left": "", "right": ""}
        result = render_template(
            "{{ value | format_progress_bar(bar) }}", {"value": 40, "bar": bar}
        )
        assert "██" in result
        assert "40%" in result

    def test_no_bar_dict_uses_defaults(self):
        result = render_template("{{ value | format_progress_bar }}", {"value": 50})
        assert "█████" in result
        assert "50%" in result
