"""Module system for statusline."""

from __future__ import annotations

from rich.console import RenderableType

from statusline.config import ThemeVars
from statusline.input import InputModel
from statusline.templates import render_template


class Module:
    """Base class for statusline modules."""

    name: str = ""
    __inputs__: list[type[InputModel]] = []
    """List of input models whose fields are available as template variables."""

    def render(
        self,
        inputs: dict[str, InputModel],
        theme_vars: ThemeVars,
        **kwargs,
    ) -> RenderableType:
        """Render the module output with Rich markup.

        Args:
            inputs: Dict mapping input names to their model instances.
            theme_vars: Theme variables including 'format' and 'label'.
            **kwargs: Extra options (e.g. expand) passed by the renderer.

        Returns:
            Rich renderable (string with markup, Table, etc.).
        """
        fmt, context = self.build_context(inputs, theme_vars)
        return render_template(fmt, context)

    def build_context(
        self, inputs: dict[str, InputModel], theme_vars: ThemeVars
    ) -> tuple[str, dict]:
        """Build namespaced template context.

        Returns (format_string, context_dict).
        Inputs namespaced under their model's `name` ClassVar.
        Theme vars under 'theme'. No model_dump() — Jinja2 uses attribute access.

        Raises:
            ValueError: If no format template is configured.
        """
        fmt = theme_vars.get("format", "")
        if not fmt:
            raise ValueError(f"module '{self.name}' has no format template")
        assert isinstance(fmt, str)
        ctx: dict = {key: input for key, input in inputs.items()}
        ctx["theme"] = theme_vars
        return fmt, ctx


# Module registry - maps module names to module classes
_registry: dict[str, type[Module]] = {}


def register(cls: type[Module]) -> type[Module]:
    """Decorator to register a module class."""
    _registry[cls.name] = cls
    return cls


def get_module(name: str) -> Module | None:
    """Get a module instance by name."""
    cls = _registry.get(name)
    if cls is None:
        return None
    return cls()


def get_all_modules() -> list[str]:
    """Get all registered module names."""
    return list(_registry.keys())


# Import modules to register them
from statusline.modules import (  # noqa: E402, F401
    context,
    context_bar,
    cost,
    events,
    git,
    model,
    version,
    workspace,
)

__all__ = ["Module", "register", "get_module", "get_all_modules"]
