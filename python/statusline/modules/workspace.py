"""Workspace module - displays the current directory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from statusline.modules import Module, register
from statusline.templates import render_template

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class WorkspaceModule(Module):
    """Display the current workspace directory."""

    name = "workspace"

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the workspace directory basename."""
        fmt = theme_vars.get("format", "{{ current_dir | basename }}")
        current_dir = input.workspace.current_dir or input.cwd
        context = {**input.workspace.model_dump(), "cwd": input.cwd, "current_dir": current_dir, **theme_vars}
        return render_template(fmt, context)
