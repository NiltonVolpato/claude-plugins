"""Module system for statusline."""

from __future__ import annotations

from rich.console import RenderableType

from statusline.config import ModuleConfigUnion
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
        config: ModuleConfigUnion,
        **kwargs,
    ) -> RenderableType:
        """Render the module output with Rich markup.

        Args:
            inputs: Dict mapping input names to their model instances.
            config: Module configuration with theme already applied.
            **kwargs: Extra options (e.g. expand) passed by the renderer.

        Returns:
            Rich renderable (string with markup, Table, etc.).
        """
        fmt, context = self.build_context(inputs, config)
        return render_template(fmt, context)

    def build_context(
        self, inputs: dict[str, InputModel], config: ModuleConfigUnion
    ) -> tuple[str, dict]:
        """Build namespaced template context.

        Returns (format_string, context_dict).
        Inputs namespaced under their model's `name` ClassVar.
        Config available under 'theme' for template compatibility.

        Raises:
            ValueError: If no format template is configured.
        """
        fmt = getattr(config, "format", "")
        if not fmt:
            raise ValueError(f"module '{self.name}' has no format template")
        ctx: dict = {key: input for key, input in inputs.items()}
        # Templates access config via 'theme' (e.g., {{ theme.label }})
        ctx["theme"] = config
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
