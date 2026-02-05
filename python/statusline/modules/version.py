"""Version module - displays Claude Code version."""

from __future__ import annotations

from statusline.input import VersionInfo
from statusline.modules import Module, register


@register
class VersionModule(Module):
    """Display the Claude Code version."""

    name = "version"
    __inputs__ = [VersionInfo]
