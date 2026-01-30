"""Version module - displays Claude Code version."""

from __future__ import annotations

from typing import TYPE_CHECKING

from statusline.input import VersionInfo
from statusline.modules import Module, register
from statusline.templates import render_template

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class VersionModule(Module):
    """Display the Claude Code version."""

    name = "version"
    __inputs__ = [VersionInfo]

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the Claude Code version."""
        fmt = theme_vars.get("format", "v{{ version }}")
        context = {"version": input.version or "?", **theme_vars}
        return render_template(fmt, context)
