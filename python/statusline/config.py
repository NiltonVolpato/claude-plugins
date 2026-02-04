"""Configuration system for statusline."""

from __future__ import annotations

import importlib.resources
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

type ThemeVars = dict[str, str | int | ThemeVars]

CONFIG_PATH = Path.home() / ".claude" / "statusline.toml"


class ModuleConfig(BaseModel):
    """Configuration for a single module."""

    type: str | None = None  # Module type to use (defaults to config key)
    color: str = ""
    format: str = ""  # Default format string with Rich markup
    theme: str | None = None  # Per-module theme override
    themes: dict[str, ThemeVars] = Field(default_factory=dict)


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
    if isinstance(enabled, list):
        return StatuslineLayout(rows=[RowLayout(left=enabled)])

    if isinstance(enabled, dict):
        # Single row with left/right keys
        if "left" in enabled or "right" in enabled:
            return StatuslineLayout(rows=[RowLayout(
                left=enabled.get("left", []),
                right=enabled.get("right", []),
            )])

        # Multi-row with numeric string keys
        rows: list[RowLayout] = []
        for key in sorted(enabled.keys(), key=int):
            value = enabled[key]
            if isinstance(value, list):
                rows.append(RowLayout(left=value))
            elif isinstance(value, dict):
                rows.append(RowLayout(
                    left=value.get("left", []),
                    right=value.get("right", []),
                ))
        return StatuslineLayout(rows=rows)

    return StatuslineLayout(rows=[])


class Config(BaseModel):
    """Global statusline configuration."""

    theme: str = "nerd"
    color: bool = True
    enabled: list[str] | dict[str, Any] = Field(
        default_factory=lambda: ["model", "workspace"]
    )
    separator: str = " | "
    width: int | None = None
    modules: dict[str, ModuleConfig] = Field(default_factory=dict)

    @property
    def layout(self) -> StatuslineLayout:
        """Get the normalized layout from the enabled field."""
        return normalize_enabled(self.enabled)

    def get_module_config(self, alias: str) -> ModuleConfig:
        """Get configuration for a module alias."""
        return self.modules.get(alias, ModuleConfig())

    def get_module_type(self, alias: str) -> str:
        """Get the module type for an alias.

        If the alias has a 'type' field in its config, use that.
        Otherwise, the alias itself is the module type.
        """
        module_config = self.modules.get(alias)
        if module_config and module_config.type:
            return module_config.type
        return alias

    def get_theme_vars(self, module_name: str) -> ThemeVars:
        """Get the resolved theme variables for a module.

        Merges module-level format with theme-specific variables.
        Theme vars can override the format.
        """
        module_config = self.get_module_config(module_name)
        theme_name = module_config.theme or self.theme

        # Start with module-level format
        result: ThemeVars = {}
        if module_config.format:
            result["format"] = module_config.format

        # Theme vars override (including format if specified)
        theme_vars = module_config.themes.get(theme_name, {})
        result.update(theme_vars)

        return result

    def get_module_color(self, module_name: str) -> str:
        """Get the color for a module."""
        return self.get_module_config(module_name).color


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _parse_config(data: dict[str, Any]) -> Config:
    """Parse configuration from TOML data."""
    try:
        return Config.model_validate(data)
    except Exception:
        # Fall back to defaults on validation error
        return Config()


def _load_defaults() -> dict[str, Any]:
    """Load default configuration from bundled defaults.toml."""
    files = importlib.resources.files("statusline")
    defaults_path = files.joinpath("defaults.toml")
    content = defaults_path.read_text()
    return tomllib.loads(content)


def _load_user_config(path: Path | None = None) -> dict[str, Any]:
    """Load user configuration from TOML file."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        return {}
    try:
        return tomllib.loads(config_path.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}


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
