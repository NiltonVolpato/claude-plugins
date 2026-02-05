"""Unit tests for statusline renderer."""

from pathlib import Path

import pytest

from statusline.config import Config, ModuleConfig, load_config
from statusline.errors import StatuslineError
from statusline.input import (
    ContextWindowInfo,
    ModelInfo,
    StatuslineInput,
    WorkspaceInfo,
)
from statusline.renderer import render_statusline


def make_input(
    model: ModelInfo | None = None,
    workspace: WorkspaceInfo | None = None,
    version: str = "1.2.3",
    context_window: ContextWindowInfo | None = None,
) -> StatuslineInput:
    """Create a StatuslineInput with custom values."""
    return StatuslineInput(
        model=model or ModelInfo(id="test-model", display_name="Test Model"),
        workspace=workspace
        or WorkspaceInfo(
            current_dir="/home/user/my-project",
            project_dir="/home/user/my-project",
        ),
        version=version,
        context_window=context_window or ContextWindowInfo(),
    )


def make_config(**kwargs: object) -> Config:
    """Create a Config using defaults and overriding with kwargs.

    Uses /dev/null as config path to avoid loading user config for hermeticity.
    """
    config = load_config(Path("/dev/null"))
    return config.model_copy(update=kwargs)


class TestRenderer:
    def test_render_single_module(self):
        input_data = make_input()
        config = make_config(enabled=["model"], theme="minimal", color=False)
        result = render_statusline(input_data, config)
        assert result == "Test Model"

    def test_render_multiple_modules(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace"], theme="minimal", color=False
        )
        result = render_statusline(input_data, config)
        assert result == "Test Model | my-project"

    def test_render_custom_separator(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace"],
            theme="minimal",
            color=False,
            separator=" :: ",
        )
        result = render_statusline(input_data, config)
        assert result == "Test Model :: my-project"

    def test_render_empty_modules(self):
        input_data = make_input()
        config = make_config(enabled=[], color=False)
        result = render_statusline(input_data, config)
        assert result == ""

    def test_render_unknown_module_raises(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "nonexistent", "workspace"],
            theme="minimal",
            color=False,
        )
        with pytest.raises(StatuslineError):
            render_statusline(input_data, config)

    def test_render_all_modules(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace", "cost", "context", "version"],
            theme="minimal",
            color=False,
        )
        result = render_statusline(input_data, config)
        # Should contain all module outputs
        assert "Test Model" in result
        assert "my-project" in result
        assert "v1.2.3" in result


class TestRendererWithThemes:
    def test_render_with_ascii_theme(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace"],
            theme="ascii",
            color=False,
        )
        result = render_statusline(input_data, config)
        assert "Model:" in result
        assert "Directory:" in result
        assert "Test Model" in result
        assert "my-project" in result

    def test_render_with_emoji_theme(self):
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace"],
            theme="emoji",
            color=False,
        )
        result = render_statusline(input_data, config)
        assert "🤖" in result
        assert "📁" in result

    def test_render_with_nerd_theme(self):
        input_data = make_input()
        config = make_config(
            enabled=["model"],
            theme="nerd",
            color=False,
        )
        result = render_statusline(input_data, config)
        # Nerd font icon for model
        assert "" in result
        assert "Test Model" in result

    def test_render_with_color(self):
        input_data = make_input()
        config = make_config(
            enabled=["model"],
            theme="minimal",
            color=True,
        )
        result = render_statusline(input_data, config)
        # Should contain ANSI codes
        assert "\x1b[" in result
        assert "Test Model" in result


class TestRendererWithAliases:
    def test_render_same_module_twice_with_different_formats(self):
        """Test rendering the same module type twice with different configs."""
        input_data = make_input()

        config = make_config(
            enabled=["model_one", "model_two"],
            theme="minimal",
            color=False,
        )
        config = config.model_copy(
            update={
                "modules": {
                    **config.modules,
                    "model_one": ModuleConfig(
                        type="model",
                        format="{{ model.display_name }}",
                    ),
                    "model_two": ModuleConfig(
                        type="model",
                        format="[{{ model.display_name }}]",
                    ),
                }
            }
        )

        result = render_statusline(input_data, config)
        assert "Test Model" in result
        assert "[Test Model]" in result

    def test_render_mixed_aliases_and_direct_modules(self):
        """Test mixing aliases with direct module names."""
        input_data = make_input()

        config = make_config(
            enabled=["model", "ws_alias"],
            theme="minimal",
            color=False,
        )
        config = config.model_copy(
            update={
                "modules": {
                    **config.modules,
                    "ws_alias": ModuleConfig(
                        type="workspace",
                        format="Dir: {{ workspace.current_dir | basename }}",
                    ),
                }
            }
        )

        result = render_statusline(input_data, config)
        assert "Test Model" in result
        assert "Dir: my-project" in result

    def test_backward_compatibility_without_type_field(self):
        """Existing configs without type field still work."""
        input_data = make_input()
        config = make_config(
            enabled=["model", "workspace"],
            theme="minimal",
            color=False,
        )
        result = render_statusline(input_data, config)
        assert "Test Model" in result
        assert "my-project" in result


class TestRendererLeftRight:
    def test_left_right_alignment(self):
        """Left/right modules are rendered on same row with space between."""
        input_data = make_input()
        config = make_config(
            enabled={"left": ["model"], "right": ["workspace"]},
            theme="minimal",
            color=False,
            width=40,
        )
        result = render_statusline(input_data, config)
        assert "Test Model" in result
        assert "my-project" in result
        print(repr(result))
        assert result == "Test Model                    my-project"
        # Right-aligned text should be padded with spaces
        assert len(result) == 40

    def test_left_only_dict(self):
        """Dict with only left key works like flat list."""
        input_data = make_input()
        config = make_config(
            enabled={"left": ["model", "workspace"]},
            theme="minimal",
            color=False,
        )
        result = render_statusline(input_data, config)
        assert "Test Model" in result
        assert "my-project" in result

    def test_right_only(self):
        """Dict with only right key renders right-aligned."""
        input_data = make_input()
        config = make_config(
            enabled={"right": ["model"]},
            theme="minimal",
            color=False,
            width=80,
        )
        result = render_statusline(input_data, config)
        assert "Test Model" in result
        assert len(result) == 80


class TestRendererMultiRow:
    def test_multi_row_left_only(self):
        """Multiple rows, all left-only, joined by newline."""
        input_data = make_input()
        config = make_config(
            enabled={"0": ["model"], "1": ["workspace"]},
            theme="minimal",
            color=False,
        )
        result = render_statusline(input_data, config)
        lines = result.split("\n")
        assert len(lines) == 2
        assert "Test Model" in lines[0]
        assert "my-project" in lines[1]

    def test_multi_row_with_alignment(self):
        """Multiple rows with left/right alignment."""
        input_data = make_input()
        config = make_config(
            enabled={
                "0": {"left": ["model"], "right": ["workspace"]},
                "1": {"left": ["version"]},
            },
            theme="minimal",
            color=False,
            width=80,
        )
        result = render_statusline(input_data, config)
        lines = result.split("\n")
        assert len(lines) == 2
        assert "Test Model" in lines[0]
        assert "my-project" in lines[0]
        assert "v1.2.3" in lines[1]


class TestRendererExpand:
    def test_expandable_module_fills_width(self):
        """An expand=true module causes the row to fill available width."""
        input_data = make_input(
            context_window=ContextWindowInfo(used_percentage=50.0),
        )
        config = make_config(
            enabled=["context_bar"],
            theme="ascii",
            color=False,
            width=60,
        )
        config = config.model_copy(
            update={
                "modules": {
                    **config.modules,
                    "context_bar": config.modules["context_bar"].model_copy(
                        update={"expand": True}
                    ),
                }
            }
        )
        result = render_statusline(input_data, config)
        assert len(result) == 60

    def test_mixed_expand_and_fixed_modules(self):
        """Expandable and fixed modules in same row."""
        input_data = make_input(
            context_window=ContextWindowInfo(used_percentage=50.0),
        )
        config = make_config(
            enabled=["model", "context_bar"],
            theme="minimal",
            color=False,
            width=80,
        )
        config = config.model_copy(
            update={
                "modules": {
                    **config.modules,
                    "context_bar": config.modules["context_bar"].model_copy(
                        update={"expand": True}
                    ),
                }
            }
        )
        result = render_statusline(input_data, config)
        assert "Test Model" in result
        assert len(result) == 80

    def test_left_right_no_expand_gets_spacer(self):
        """Left/right with no expand still pads to full width."""
        input_data = make_input()
        config = make_config(
            enabled={"left": ["model"], "right": ["workspace"]},
            theme="minimal",
            color=False,
            width=80,
        )
        result = render_statusline(input_data, config)
        assert "Test Model" in result
        assert "my-project" in result
        assert len(result) == 80
