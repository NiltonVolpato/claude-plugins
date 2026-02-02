"""Unit tests for statusline config."""

import tempfile
from pathlib import Path

from statusline.config import (
    Config,
    ModuleConfig,
    generate_default_config_toml,
    load_config,
)


class TestModuleConfig:
    def test_default_values(self):
        config = ModuleConfig()
        assert config.type is None
        assert config.color == ""
        assert config.theme is None
        assert config.themes == {}

    def test_custom_values(self):
        config = ModuleConfig(
            color="red",
            theme="ascii",
            themes={"nerd": {"label": ""}},
        )
        assert config.color == "red"
        assert config.theme == "ascii"
        assert config.themes["nerd"]["label"] == ""

    def test_type_field(self):
        config = ModuleConfig(type="context")
        assert config.type == "context"


class TestConfig:
    def test_default_values(self):
        config = Config()
        assert config.theme == "nerd"
        assert config.color is True
        assert config.enabled == ["model", "workspace"]
        assert config.separator == " | "

    def test_custom_values(self):
        config = Config(
            theme="ascii",
            color=False,
            enabled=["model", "cost"],
            separator=" :: ",
        )
        assert config.theme == "ascii"
        assert config.color is False
        assert config.enabled == ["model", "cost"]

    def test_get_module_config(self):
        config = Config(
            modules={
                "model": ModuleConfig(color="red", theme="ascii"),
            }
        )
        module_config = config.get_module_config("model")
        assert module_config.color == "red"
        assert module_config.theme == "ascii"

    def test_get_module_config_missing(self):
        config = Config()
        module_config = config.get_module_config("unknown")
        assert module_config.color == ""
        assert module_config.theme is None

    def test_get_theme_vars(self):
        config = Config(
            theme="nerd",
            modules={
                "model": ModuleConfig(
                    themes={
                        "nerd": {"label": ""},
                        "ascii": {"label": "Model:"},
                    }
                ),
            },
        )
        theme_vars = config.get_theme_vars("model")
        assert theme_vars == {"label": ""}

    def test_get_theme_vars_with_module_override(self):
        config = Config(
            theme="nerd",
            modules={
                "model": ModuleConfig(
                    theme="ascii",  # Override global theme
                    themes={
                        "nerd": {"label": ""},
                        "ascii": {"label": "Model:"},
                    },
                ),
            },
        )
        theme_vars = config.get_theme_vars("model")
        assert theme_vars == {"label": "Model:"}

    def test_get_module_type_without_type_field(self):
        """When no type field, alias is the module type."""
        config = Config(
            modules={
                "model": ModuleConfig(color="red"),
            }
        )
        assert config.get_module_type("model") == "model"

    def test_get_module_type_with_type_field(self):
        """When type field present, use it instead of alias."""
        config = Config(
            modules={
                "ctx_percent": ModuleConfig(type="context"),
            }
        )
        assert config.get_module_type("ctx_percent") == "context"

    def test_get_module_type_unknown_alias(self):
        """Unknown alias returns itself as type."""
        config = Config()
        assert config.get_module_type("unknown") == "unknown"


class TestLoadConfig:
    def test_loads_defaults(self):
        # Load with non-existent user config - should use defaults
        config = load_config(Path("/nonexistent/path/config.toml"))
        assert config.theme == "nerd"
        assert config.color is True
        # Check that defaults.toml was loaded
        assert "model" in config.modules
        theme_vars = config.get_theme_vars("model")
        # Nerd theme label includes the icon
        assert "label" in theme_vars
        assert "format" in theme_vars

    def test_user_config_overrides_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
theme = "ascii"
color = false
""")
            f.flush()
            config = load_config(Path(f.name))
            assert config.theme == "ascii"
            assert config.color is False
            # Defaults should still be loaded for module configs
            assert "model" in config.modules

    def test_invalid_toml_uses_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("this is not valid toml [[[")
            f.flush()
            config = load_config(Path(f.name))
            # Should return default config on parse error
            assert config.theme == "nerd"


class TestGenerateDefaultConfigToml:
    def test_generates_valid_toml(self):
        toml_content = generate_default_config_toml()
        assert "theme = " in toml_content
        assert "color = " in toml_content
        assert "enabled = " in toml_content
        assert "separator = " in toml_content
