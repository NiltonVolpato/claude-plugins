"""Workspace module - displays the current directory."""

from __future__ import annotations

from statusline.input import WorkspaceInfo
from statusline.modules import Module, register


@register
class WorkspaceModule(Module):
    """Display the current workspace directory."""

    name = "workspace"
    __inputs__ = [WorkspaceInfo]
