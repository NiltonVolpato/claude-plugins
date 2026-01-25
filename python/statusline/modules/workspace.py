"""Workspace module - displays the current directory."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from statusline.modules import Module, register

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class WorkspaceModule(Module):
    """Display the current workspace directory."""

    name = "workspace"

    def render(
        self, input: StatuslineInput, theme_vars: dict[str, str], color: str
    ) -> str:
        """Render the workspace directory basename."""
        label = theme_vars.get("label", "")
        current_dir = input.workspace.current_dir or input.cwd
        if not current_dir:
            value = "~"
        else:
            value = os.path.basename(current_dir) or current_dir
        space = " " if label else ""
        return f"[{color}]{label}{space}{value}[/{color}]"
