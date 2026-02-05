"""Expandable progress bar renderable for Rich."""

from __future__ import annotations

from rich.color import Color
from rich.measure import Measurement
from rich.style import Style
from rich.text import Text


class ExpandableBar:
    """Rich renderable progress bar that fills its allocated width."""

    def __init__(
        self, percentage: float, bar_opts: dict | None = None, *, expand: bool = False
    ):
        self.percentage = max(0.0, min(100.0, percentage))
        opts = bar_opts or {}
        self.full_char = str(opts.get("full", "█"))
        self.empty_char = str(opts.get("empty", " "))
        # Static outer frame (outside bar segments)
        self.left = str(opts.get("left", ""))
        self.right = str(opts.get("right", ""))
        # Fill-state end caps (replace first/last segment positions)
        self.full_left = str(opts.get("full_left", self.full_char))
        self.empty_left = str(opts.get("empty_left", self.empty_char))
        self.full_right = str(opts.get("full_right", self.full_char))
        self.empty_right = str(opts.get("empty_right", self.empty_char))
        self.width = int(opts.get("width", 10))
        self.expand = expand

    def __rich_console__(self, console, options):
        width = options.max_width
        ratio = self.percentage / 100

        # Space available for bar segments (after outer frame)
        bar_space = max(0, width - len(self.left) - len(self.right))

        # Total filled positions (out of bar_space)
        n_total = max(0, min(bar_space, int(bar_space * ratio)))

        # Choose caps based on fill state
        left_cap = self.full_left if n_total >= 1 else self.empty_left
        right_cap = self.full_right if n_total >= bar_space else self.empty_right

        # Middle segments (between caps)
        middle = max(0, bar_space - len(left_cap) - len(right_cap))
        if n_total >= bar_space:
            n_mid = middle
        elif n_total >= 1:
            n_mid = min(n_total - 1, middle)
        else:
            n_mid = 0

        bar_str = (
            left_cap
            + self.full_char * n_mid
            + self.empty_char * (middle - n_mid)
            + right_cap
        )

        # RGB: green (0%) → red (100%)
        r = int(255 * ratio)
        g = int(255 * (1 - ratio))
        color = Color.from_rgb(r, g, 0)

        text = Text()
        text.append(self.left + bar_str + self.right, style=Style(color=color))
        yield text

    def __rich_measure__(self, console, options):
        frame = len(self.left) + len(self.right)
        minimum = self.width + frame
        maximum = options.max_width if self.expand else minimum
        return Measurement(minimum, maximum)
