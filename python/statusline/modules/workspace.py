"""Workspace module - displays the current directory."""

from __future__ import annotations

from pydantic import BaseModel

from statusline.input import WorkspaceInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class WorkspaceModule(Module):
    """Display the current workspace directory."""

    name = "workspace"
    __inputs__ = [WorkspaceInfo]

    def render(self, inputs: dict[str, BaseModel], theme_vars: dict[str, str]) -> str:
        """Render the workspace directory basename."""
        workspace_info = inputs.get("workspace")
        if not workspace_info:
            return ""

        fmt = theme_vars.get("format", "{{ current_dir | basename }}")
        context = {**workspace_info.model_dump(), **theme_vars}
        return render_template(fmt, context)
