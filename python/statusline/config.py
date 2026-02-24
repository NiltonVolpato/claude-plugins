"""Configuration system for statusline."""

from __future__ import annotations

import importlib.resources
import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal, Self, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator

from statusline.errors import report_error

CONFIG_PATH = Path.home() / ".claude" / "statusline.toml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# =============================================================================
# Theme Classes (no defaults - all values come from TOML)
# =============================================================================


class SimpleModuleTheme(BaseModel):
    """Theme fields for simple modules (model, workspace, git, cost, context, version)."""

    color: str = Field(description="Text color (e.g., 'cyan', '#ff0000')")
    format: str = Field(description="Jinja2 format template")
    label: str = Field(default="", description="Label prefix (set by theme)")


class BarTheme(BaseModel):
    """Theme fields for progress bar rendering."""

    left: str = Field(description="Left frame character (outside the bar)")
    right: str = Field(description="Right frame character (outside the bar)")
    full: str = Field(description="Character for filled bar segments")
    empty: str = Field(description="Character for empty bar segments")
    full_left: str = Field(default="", description="Left end cap when filled")
    empty_left: str = Field(default="", description="Left end cap when empty")
    full_right: str = Field(default="", description="Right end cap when filled")
    empty_right: str = Field(default="", description="Right end cap when empty")
    width: int = Field(default=10, description="Bar width in characters")


class ContextBarTheme(BaseModel):
    """Theme fields for context_bar module."""

    format: str = Field(description="Jinja2 format template")
    bar: BarTheme = Field(description="Progress bar appearance")


class EventsBackgrounds(BaseModel):
    """Background colors for different run contexts."""

    main: str = Field(description="Background for main context")
    user: str = Field(description="Background for user context")
    subagent: str = Field(description="Background for subagent context")
    edit_bar: str = Field(description="Background for edit bar")


class EventsRunBrackets(BaseModel):
    """Bracket pairs for each run context."""

    main: tuple[str, str] = Field(description="Bracket pair for main context")
    user: tuple[str, str] = Field(description="Bracket pair for user context")
    subagent: tuple[str, str] = Field(description="Bracket pair for subagent context")


class EventsLineBars(BaseModel):
    """Line count bar configuration."""

    chars: str = Field(description="Characters for bar height levels")
    thresholds: list[int] = Field(description="Line count thresholds for each bar level")


class EventsTheme(BaseModel):
    """Theme fields for events module."""

    spacing: int = Field(description="Spacing between events")
    run_spacing: str = Field(default="", description="Spacing between runs")
    limit: int = Field(description="Maximum number of events to display")
    left: str = Field(description="Left bracket character")
    right: str = Field(description="Right bracket character")
    brackets: bool = Field(description="Show brackets around runs")
    background: str = Field(default="", description="Default background color")
    backgrounds: EventsBackgrounds = Field(description="Per-context background colors")
    run_brackets: EventsRunBrackets = Field(description="Per-context bracket pairs")
    tool_icons: dict[str, str] = Field(description="Tool name to icon mapping")
    bash_icons: dict[str, str] = Field(description="Bash command to icon mapping")
    event_icons: dict[str, str] = Field(description="Event type to icon mapping")
    line_bars: EventsLineBars = Field(description="Line count bar visualization")


# =============================================================================
# Base Module Config with Theme Application
# =============================================================================


class BaseModuleConfig(BaseModel):
    """Base class for all module configs.

    The model_validator applies theme overrides on construction and when
    theme changes (via validate_assignment). All defaults come from TOML.
    """

    model_config = ConfigDict(validate_assignment=True)

    type: str  # Required - discriminator field
    theme: str = ""  # Selected theme name (set by config loading)
    themes: dict[str, Any] = Field(default_factory=dict)
    expand: bool = Field(default=False, description="Expand to fill available space")

    @model_validator(mode="after")
    def apply_theme_overrides(self) -> Self:
        """Apply selected theme's overrides to this config."""
        if self.theme not in self.themes:
            return self
        theme_overrides = self.themes[self.theme]
        if not isinstance(theme_overrides, dict):
            return self
        for field, value in theme_overrides.items():
            if field in ("theme", "themes"):  # Don't override meta fields
                continue
            current = getattr(self, field, None)
            # Deep-merge nested models
            if current is not None and hasattr(current, "model_dump"):
                merged = _deep_merge(current.model_dump(), value)
                value = type(current).model_validate(merged)
            object.__setattr__(self, field, value)
        return self


# =============================================================================
# Per-Module Config Classes
# =============================================================================


class ModelConfig(SimpleModuleTheme, BaseModuleConfig):
    """Config for model module."""

    type: Literal["model"] = "model"


class WorkspaceConfig(SimpleModuleTheme, BaseModuleConfig):
    """Config for workspace module."""

    type: Literal["workspace"] = "workspace"


class GitConfig(SimpleModuleTheme, BaseModuleConfig):
    """Config for git module."""

    type: Literal["git"] = "git"


class CostConfig(SimpleModuleTheme, BaseModuleConfig):
    """Config for cost module."""

    type: Literal["cost"] = "cost"


class ContextConfig(SimpleModuleTheme, BaseModuleConfig):
    """Config for context module."""

    type: Literal["context"] = "context"


class VersionConfig(SimpleModuleTheme, BaseModuleConfig):
    """Config for version module."""

    type: Literal["version"] = "version"


class ContextBarConfig(ContextBarTheme, BaseModuleConfig):
    """Config for context_bar module."""

    type: Literal["context_bar"] = "context_bar"


class EventsConfig(EventsTheme, BaseModuleConfig):
    """Config for events module."""

    type: Literal["events"] = "events"


# =============================================================================
# Discriminated Union
# =============================================================================

ModuleConfigUnion = Annotated[
    Union[
        ModelConfig,
        WorkspaceConfig,
        GitConfig,
        CostConfig,
        ContextConfig,
        VersionConfig,
        ContextBarConfig,
        EventsConfig,
    ],
    Field(discriminator="type"),
]

# Type alias for backward compatibility during migration
ModuleConfig = ModuleConfigUnion


def get_config_class(module_type: str) -> type[BaseModuleConfig] | None:
    """Get the config class for a module type string.

    Inspects the ModuleConfigUnion discriminated union to find the config class
    whose ``type`` literal matches *module_type*.
    """
    # Unwrap Annotated[Union[...], Field(...)] → Union[...] → individual classes
    annotated_args = get_args(ModuleConfigUnion)
    for arg in annotated_args:
        if get_origin(arg) is Union:
            # This is the Union — unwrap its members
            for cls in get_args(arg):
                if not isinstance(cls, type):
                    continue
                type_field = cls.model_fields.get("type")
                if type_field is None:
                    continue
                literal_args = get_args(type_field.annotation)
                if literal_args and module_type in literal_args:
                    return cls
    return None


class RowLayout(BaseModel):
    """Layout for a single row with optional left/right alignment."""

    left: list[str] = Field(default_factory=list)
    right: list[str] = Field(default_factory=list)


class StatuslineLayout(BaseModel):
    """Normalized layout with one or more rows."""

    rows: list[RowLayout]


def normalize_enabled(enabled: list[str] | dict[str, Any]) -> StatuslineLayout:
    """Convert raw TOML `enabled` value into a StatuslineLayout.

    Supported shapes:
    - list[str]                          → 1 row, left=list
    - dict with left/right keys          → 1 row with both sides
    - dict with numeric string keys      → multi-row (sorted by key)
      each value can be list (left-only) or dict with left/right
    """
    try:
        if isinstance(enabled, list):
            return StatuslineLayout(rows=[RowLayout(left=enabled)])

        if isinstance(enabled, dict):
            # Single row with left/right keys
            if "left" in enabled or "right" in enabled:
                return StatuslineLayout(
                    rows=[
                        RowLayout(
                            left=enabled.get("left", []),
                            right=enabled.get("right", []),
                        )
                    ]
                )

            # Multi-row with numeric string keys
            rows: list[RowLayout] = []
            for key in sorted(enabled.keys(), key=lambda k: int(k)):
                value = enabled[key]
                if isinstance(value, list):
                    rows.append(RowLayout(left=value))
                elif isinstance(value, dict):
                    rows.append(
                        RowLayout(
                            left=value.get("left", []),
                            right=value.get("right", []),
                        )
                    )
            return StatuslineLayout(rows=rows)

        return StatuslineLayout(rows=[])
    except Exception as exc:
        report_error("parsing 'enabled' layout config", exc)


class Config(BaseModel):
    """Global statusline configuration."""

    theme: str = "nerd"
    color: bool = True
    enabled: list[str] | dict[str, Any] = Field(
        default_factory=lambda: ["model", "workspace"]
    )
    separator: str = " | "
    width: int | None = None
    modules: dict[str, ModuleConfigUnion] = Field(default_factory=dict)

    @property
    def layout(self) -> StatuslineLayout:
        """Get the normalized layout from the enabled field."""
        return normalize_enabled(self.enabled)

    def get_module_config(self, alias: str) -> ModuleConfigUnion | None:
        """Get configuration for a module alias."""
        return self.modules.get(alias)

    def get_module_type(self, alias: str) -> str:
        """Get the module type for an alias."""
        module_config = self.modules.get(alias)
        if module_config:
            return module_config.type
        return alias


def _parse_config(data: dict[str, Any]) -> Config:
    """Parse configuration from TOML data."""
    try:
        return Config.model_validate(data)
    except Exception as exc:
        report_error("validating config", exc)


def _load_defaults() -> dict[str, Any]:
    """Load default configuration from bundled defaults.toml."""
    try:
        files = importlib.resources.files("statusline")
        defaults_path = files.joinpath("defaults.toml")
        content = defaults_path.read_text()
        return tomllib.loads(content)
    except Exception as exc:
        report_error("loading bundled defaults.toml", exc)


def _load_user_config(path: Path | None = None) -> dict[str, Any]:
    """Load user configuration from TOML file."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        return {}
    try:
        return tomllib.loads(config_path.read_text())
    except Exception as exc:
        report_error(f"parsing config file '{config_path}'", exc)


def load_config(path: Path | None = None) -> Config:
    """Load configuration, merging defaults with user config.

    Args:
        path: Path to user config file. Defaults to ~/.claude/statusline.toml

    Returns:
        Merged Config with user values overriding defaults.
    """
    defaults = _load_defaults()
    user = _load_user_config(path)
    merged = _deep_merge(defaults, user)

    # Inject global theme into each module for theme resolution
    # Also handle aliases: if module has type different from key, inherit from base type
    global_theme = merged.get("theme", "nerd")
    modules = merged.get("modules", {})

    for alias, module_data in list(modules.items()):
        if not isinstance(module_data, dict):
            continue

        # Inject global theme if not set
        if "theme" not in module_data:
            module_data["theme"] = global_theme

        # Handle aliases: inherit from base type's config
        module_type = module_data.get("type", alias)
        if module_type != alias and module_type in modules:
            base_config = modules[module_type]
            if isinstance(base_config, dict):
                # Deep-merge: base first, then alias overrides
                modules[alias] = _deep_merge(base_config, module_data)

    return _parse_config(merged)


def generate_default_config_toml() -> str:
    """Generate default config file content for users to customize."""
    return """\
# Statusline configuration
# Location: ~/.claude/statusline.toml

# Global defaults
# theme = "nerd"      # nerd | ascii | emoji | minimal
# color = true
# enabled = ["model", "workspace", "context"]
# separator = " | "
# width = 120         # Terminal width override (auto-detected by default)

# Layout options — `enabled` supports several formats:
#
# Simple list (default):
# enabled = ["model", "workspace", "context"]
#
# Left/right alignment:
# enabled.left = ["model", "workspace"]
# enabled.right = ["context"]
#
# Multi-line:
# enabled.0 = ["model", "workspace"]
# enabled.1 = ["context"]
#
# Combined multi-line with alignment:
# [enabled.0]
# left = ["model", "workspace"]
# right = ["context"]

# Per-module overrides (uncomment to customize)
# [modules.model]
# color = "cyan"
# theme = "ascii"   # Override theme for this module only
#
# [modules.model.themes.nerd]
# label = ""
#
# [modules.model.themes.custom]  # Create your own theme
# label = "MODEL:"
"""
