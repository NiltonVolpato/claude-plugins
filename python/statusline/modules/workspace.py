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

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the workspace directory basename."""
        fmt = theme_vars.get("format", "{basename}")
        current_dir = input.workspace.current_dir or input.cwd
        if not current_dir:
            basename = "~"
        else:
            basename = os.path.basename(current_dir) or current_dir
        values = {**input.workspace.model_dump(), "cwd": input.cwd, "basename": basename, **theme_vars}
        return fmt.format(**values)
