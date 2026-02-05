"""Jinja2 templating for statusline."""

from __future__ import annotations

import os

import humanize
from jinja2 import Environment


def _basename(path: str) -> str:
    """Extract basename from path, or return ~ if empty."""
    if not path:
        return "~"
    return os.path.basename(path) or path


def _format_cost(value: float) -> str:
    """Format USD cost value."""
    if value < 0.01:
        return f"${value:.4f}"
    return f"${value:.2f}"


def _format_percent(value: float) -> str:
    """Format percentage value."""
    return f"{value:3.0f}%"


def _format_progress_bar(value: float, bar: dict | None = None) -> str:
    """Format a progress bar with color based on usage.

    Colors: green (<70%), yellow (70-85%), red (>=85%)

    Bar dict keys:
        full, empty — middle segment chars (default █, space)
        left, right — static caps (default [, ])
        full_left, empty_left — override left based on fill state
        full_right, empty_right — override right based on fill state
        width — bar width in segments (default 10)
    """
    bar = bar or {}
    width = int(bar.get("width", 10))
    full_char = str(bar.get("full", "█"))
    empty_char = str(bar.get("empty", " "))
    left = str(bar.get("left", "\\["))
    right = str(bar.get("right", "]"))
    full_left = str(bar.get("full_left", left))
    empty_left = str(bar.get("empty_left", left))
    full_right = str(bar.get("full_right", right))
    empty_right = str(bar.get("empty_right", right))

    n = int(value / 100 * width)
    left_cap = full_left if n > 0 else empty_left
    right_cap = full_right if n == width else empty_right
    segments = full_char * n + empty_char * (width - n)

    # Escape Rich markup in bar characters (e.g., literal "[" and "]")
    bar_text = (left_cap + segments + right_cap).replace("[", "\\[")

    if value >= 85:
        color = "red"
    elif value >= 70:
        color = "yellow"
    else:
        color = "green"

    return f"[{color}]{bar_text}[/{color}] {value:.0f}%"


def _humanize_metric(value: int | float, *, spaces: bool = True, **kwargs) -> str:
    """Wrap humanize.metric with optional space removal."""
    result = humanize.metric(value, **kwargs)
    if not spaces:
        return result.replace(" ", "")
    return result


def create_environment() -> Environment:
    """Create Jinja2 environment with custom filters."""
    env = Environment()
    env.filters["basename"] = _basename
    env.filters["format_cost"] = _format_cost
    env.filters["format_percent"] = _format_percent
    env.filters["format_progress_bar"] = _format_progress_bar
    env.filters["humanize.metric"] = _humanize_metric
    env.filters["humanize.intword"] = humanize.intword
    env.filters["humanize.intcomma"] = humanize.intcomma
    return env


_env = create_environment()


def render_template(template_str: str, context: dict) -> str:
    """Render a Jinja2 template string with the given context."""
    return _env.from_string(template_str).render(context)
