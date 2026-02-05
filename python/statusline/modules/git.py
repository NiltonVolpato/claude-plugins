"""Git module - displays git repository status."""

from __future__ import annotations

from statusline.input import GitInfo
from statusline.modules import Module, register


@register
class GitModule(Module):
    """Display git repository status."""

    name = "git"
    __inputs__ = [GitInfo]

    def render(self, inputs, theme_vars, **kwargs):
        git_info = inputs.get("git")
        if not git_info or not git_info.branch:
            return ""
        return super().render(inputs, theme_vars, **kwargs)
