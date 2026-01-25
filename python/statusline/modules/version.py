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

    def render(self, input: StatuslineInput, theme_vars: dict[str, str]) -> str:
        """Render the Claude Code version."""
        fmt = theme_vars.get("format", "v{version}")
        values = {"version": input.version or "?", **theme_vars}
        return fmt.format(**values)
