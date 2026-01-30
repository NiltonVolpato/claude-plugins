"""Git module - displays git repository status."""

from __future__ import annotations

from pydantic import BaseModel

from statusline.input import GitInfo
from statusline.modules import Module, register
from statusline.templates import render_template


@register
class GitModule(Module):
    """Display git repository status."""

    name = "git"
    __inputs__ = [GitInfo]

    def render(self, inputs: dict[str, BaseModel], theme_vars: dict[str, str]) -> str:
        """Render git status info."""
        git_info = inputs.get("git")
        if not git_info or not git_info.branch:
            return ""

        fmt = theme_vars.get(
            "format", "{{ label }}{{ branch }}{{ dirty_indicator }}{{ ahead_behind }}"
        )
        context = {**git_info.model_dump(), **theme_vars}
        return render_template(fmt, context)
