"""Version module - displays Claude Code version."""

from __future__ import annotations

from statusline.config import ThemeVars
from statusline.input import InputModel, VersionInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class VersionModule(Module):
    """Display the Claude Code version."""

    name = "version"
    __inputs__ = [VersionInfo]

    def render(self, inputs: dict[str, InputModel], theme_vars: ThemeVars) -> str:
        """Render the Claude Code version."""
        fmt, context = self.build_context(inputs, theme_vars)
        if not fmt:
            return ""
        return render_template(fmt, context)
