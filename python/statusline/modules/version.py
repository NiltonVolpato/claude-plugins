"""Version module - displays Claude Code version."""

from __future__ import annotations

from typing import TYPE_CHECKING

from statusline.modules import Module, register

if TYPE_CHECKING:
    from statusline.input import StatuslineInput


@register
class VersionModule(Module):
    """Display the Claude Code version."""

    name = "version"

    def render(
        self, input: StatuslineInput, theme_vars: dict[str, str], color: str
    ) -> str:
        """Render the Claude Code version."""
        label = theme_vars.get("label", "")
        version = input.version
        if not version:
            value = "v?"
        else:
            value = f"v{version}"
        space = " " if label else ""
        return f"[{color}]{label}{space}{value}[/{color}]"
