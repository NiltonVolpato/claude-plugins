"""Unit tests for statusline config."""

import tempfile
from pathlib import Path

from statusline.config import (
    Config,
    ModuleConfig,
    RowLayout,
    generate_default_config_toml,
    load_config,
    normalize_enabled,
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

    def test_expand_defaults_to_false(self):
        config = ModuleConfig()
        assert config.expand is False

    def test_expand_set_to_true(self):
        config = ModuleConfig(expand=True)
        assert config.expand is True


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

    def test_invalid_toml_raises_error(self):
        from statusline.errors import StatuslineError

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("this is not valid toml [[[")
            f.flush()
            try:
                load_config(Path(f.name))
                assert False, "Expected StatuslineError"
            except StatuslineError:
                pass  # Expected


class TestNormalizeEnabled:
    def test_flat_list(self):
        """Simple list → 1 row, left-only."""
        layout = normalize_enabled(["a", "b", "c"])
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["a", "b", "c"]
        assert layout.rows[0].right == []

    def test_dict_left_right(self):
        """Dict with left/right → 1 row with both sides."""
        layout = normalize_enabled({"left": ["a", "b"], "right": ["c"]})
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["a", "b"]
        assert layout.rows[0].right == ["c"]

    def test_dict_left_only(self):
        """Dict with only left → 1 row, left-only."""
        layout = normalize_enabled({"left": ["a", "b"]})
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["a", "b"]
        assert layout.rows[0].right == []

    def test_dict_right_only(self):
        """Dict with only right → 1 row, right-only."""
        layout = normalize_enabled({"right": ["c"]})
        assert len(layout.rows) == 1
        assert layout.rows[0].left == []
        assert layout.rows[0].right == ["c"]

    def test_numeric_keys_list_values(self):
        """Dict with numeric keys and list values → multi-row, left-only."""
        layout = normalize_enabled({"0": ["a", "b"], "1": ["c"]})
        assert len(layout.rows) == 2
        assert layout.rows[0].left == ["a", "b"]
        assert layout.rows[0].right == []
        assert layout.rows[1].left == ["c"]
        assert layout.rows[1].right == []

    def test_numeric_keys_dict_values(self):
        """Dict with numeric keys and dict values → multi-row with alignment."""
        layout = normalize_enabled({
            "0": {"left": ["a"], "right": ["b"]},
            "1": {"left": ["c"], "right": ["d"]},
        })
        assert len(layout.rows) == 2
        assert layout.rows[0] == RowLayout(left=["a"], right=["b"])
        assert layout.rows[1] == RowLayout(left=["c"], right=["d"])

    def test_numeric_keys_sorted(self):
        """Numeric keys are sorted numerically."""
        layout = normalize_enabled({"2": ["c"], "0": ["a"], "1": ["b"]})
        assert len(layout.rows) == 3
        assert layout.rows[0].left == ["a"]
        assert layout.rows[1].left == ["b"]
        assert layout.rows[2].left == ["c"]

    def test_empty_list(self):
        """Empty list → 1 row with empty left."""
        layout = normalize_enabled([])
        assert len(layout.rows) == 1
        assert layout.rows[0].left == []

    def test_mixed_numeric_list_and_dict(self):
        """Mix of list and dict values under numeric keys."""
        layout = normalize_enabled({
            "0": ["a", "b"],
            "1": {"left": ["c"], "right": ["d"]},
        })
        assert len(layout.rows) == 2
        assert layout.rows[0].left == ["a", "b"]
        assert layout.rows[0].right == []
        assert layout.rows[1].left == ["c"]
        assert layout.rows[1].right == ["d"]


class TestConfigLayout:
    def test_layout_from_list(self):
        """Config.layout normalizes a list enabled field."""
        config = Config(enabled=["model", "workspace"])
        layout = config.layout
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["model", "workspace"]

    def test_layout_from_dict(self):
        """Config.layout normalizes a dict enabled field."""
        config = Config(enabled={"left": ["model"], "right": ["context"]})
        layout = config.layout
        assert len(layout.rows) == 1
        assert layout.rows[0].left == ["model"]
        assert layout.rows[0].right == ["context"]

    def test_width_default_none(self):
        config = Config()
        assert config.width is None

    def test_width_override(self):
        config = Config(width=120)
        assert config.width == 120


class TestGenerateDefaultConfigToml:
    def test_generates_valid_toml(self):
        toml_content = generate_default_config_toml()
        assert "theme = " in toml_content
        assert "color = " in toml_content
        assert "enabled = " in toml_content
        assert "separator = " in toml_content

    def test_includes_layout_examples(self):
        toml_content = generate_default_config_toml()
        assert "enabled.left" in toml_content
        assert "enabled.right" in toml_content
