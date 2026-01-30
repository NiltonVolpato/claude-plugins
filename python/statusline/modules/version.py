"""Version module - displays Claude Code version."""

from __future__ import annotations

from pydantic import BaseModel

from statusline.input import VersionInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class VersionModule(Module):
    """Display the Claude Code version."""

    name = "version"
    __inputs__ = [VersionInfo]

    def render(self, inputs: dict[str, BaseModel], theme_vars: dict[str, str]) -> str:
        """Render the Claude Code version."""
        version_info = inputs.get("version")
        if not version_info:
            return ""

        fmt = theme_vars.get("format", "v{{ version }}")
        context = {**version_info.model_dump(), **theme_vars}
        return render_template(fmt, context)
