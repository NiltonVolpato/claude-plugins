"""Git module - displays git repository status."""

from __future__ import annotations

from pydantic import BaseModel

from statusline.config import ThemeVars
from statusline.input import GitInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class GitModule(Module):
    """Display git repository status."""

    name = "git"
    __inputs__ = [GitInfo]

    def render(self, inputs: dict[str, BaseModel], theme_vars: ThemeVars) -> str:
        """Render git status info."""
        git_info = inputs.get("git")
        if not git_info or not git_info.branch:
            return ""

        fmt, context = self.build_context(inputs, theme_vars)
        if not fmt:
            return ""
        return render_template(fmt, context)
