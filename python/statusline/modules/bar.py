"""Expandable progress bar renderable for Rich."""

from __future__ import annotations

from rich.color import Color
from rich.measure import Measurement
from rich.style import Style
from rich.text import Text


class ExpandableBar:
    """Rich renderable progress bar that fills its allocated width."""

    def __init__(self, percentage: float, bar_opts: dict | None = None):
        self.percentage = max(0.0, min(100.0, percentage))
        opts = bar_opts or {}
        self.full_char = str(opts.get("full", "█"))
        self.empty_char = str(opts.get("empty", " "))
        left = str(opts.get("left", "["))
        right = str(opts.get("right", "]"))
        self.full_left = str(opts.get("full_left", left))
        self.empty_left = str(opts.get("empty_left", left))
        self.full_right = str(opts.get("full_right", right))
        self.empty_right = str(opts.get("empty_right", right))
        self.width = int(opts.get("width", 10))

    def __rich_console__(self, console, options):
        width = options.max_width
        bar_width = max(0, width - len(self.full_left) - len(self.full_right))
        ratio = self.percentage / 100
        n = int(bar_width * ratio)

        left_cap = self.full_left if n > 0 else self.empty_left
        right_cap = self.full_right if n == bar_width else self.empty_right
        segments = self.full_char * n + self.empty_char * (bar_width - n)

        # RGB: green (0%) → red (100%)
        r = int(255 * ratio)
        g = int(255 * (1 - ratio))
        color = Color.from_rgb(r, g, 0)

        text = Text()
        text.append(left_cap + segments + right_cap, style=Style(color=color))
        yield text

    def __rich_measure__(self, console, options):
        total = self.width + len(self.full_left) + len(self.full_right)
        return Measurement(total, total)
