"""Jinja2 templating for statusline."""

from __future__ import annotations

import os

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
    return f"{value:.0f}%"


def _format_progress_bar(value: float, width: int = 10) -> str:
    """Format a progress bar with color based on usage.

    Colors: green (<70%), yellow (70-85%), red (>=85%)
    """
    filled = int(value / 100 * width)
    empty = width - filled
    bar = "█" * filled + " " * empty

    if value >= 85:
        color = "red"
    elif value >= 70:
        color = "yellow"
    else:
        color = "green"

    return f"[{color}]\\[{bar}][/{color}] {value:.0f}%"


def create_environment() -> Environment:
    """Create Jinja2 environment with custom filters."""
    env = Environment()
    env.filters["basename"] = _basename
    env.filters["format_cost"] = _format_cost
    env.filters["format_percent"] = _format_percent
    env.filters["format_progress_bar"] = _format_progress_bar
    return env


_env = create_environment()


def render_template(template_str: str, context: dict) -> str:
    """Render a Jinja2 template string with the given context."""
    return _env.from_string(template_str).render(context)
