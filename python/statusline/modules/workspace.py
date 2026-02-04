"""Workspace module - displays the current directory."""

from __future__ import annotations

from statusline.config import ThemeVars
from statusline.input import InputModel, WorkspaceInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class WorkspaceModule(Module):
    """Display the current workspace directory."""

    name = "workspace"
    __inputs__ = [WorkspaceInfo]

    def render(self, inputs: dict[str, InputModel], theme_vars: ThemeVars) -> str:
        """Render the workspace directory basename."""
        fmt, context = self.build_context(inputs, theme_vars)
        return render_template(fmt, context)
