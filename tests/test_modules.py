"""Unit tests for statusline modules."""

from rich.console import Console, ConsoleOptions, RenderableType
from rich.table import Table
from statusline.config import (
    BarTheme,
    ContextBarConfig,
    ContextConfig,
    CostConfig,
    ModelConfig,
    VersionConfig,
    WorkspaceConfig,
)
from statusline.input import (
    ContextWindowInfo,
    CostInfo,
    ModelInfo,
    VersionInfo,
    WorkspaceInfo,
)
from statusline.modules import get_all_modules, get_module
from statusline.modules.bar import ExpandableBar


class TestModelModule:
    def test_render_display_name(self):
        module = get_module("model")
        assert module is not None
        inputs = {"model": ModelInfo(id="test-model", display_name="Test Model")}
        config = ModelConfig(
            type="model",
            color="cyan",
            format="{{ model.display_name }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "Test Model"

    def test_render_empty_display_name(self):
        module = get_module("model")
        assert module is not None
        inputs = {"model": ModelInfo(id="x", display_name="")}
        config = ModelConfig(
            type="model",
            color="cyan",
            format="{{ model.display_name }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == ""

    def test_render_with_label(self):
        module = get_module("model")
        assert module is not None
        inputs = {"model": ModelInfo(id="test-model", display_name="Test Model")}
        config = ModelConfig(
            type="model",
            color="cyan",
            format="[cyan]{{ theme.label }}{{ model.display_name }}[/cyan]",
            label="\uee0d ",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert "\uee0d" in result
        assert "Test Model" in result


class TestWorkspaceModule:
    def test_render_current_dir(self):
        module = get_module("workspace")
        assert module is not None
        inputs = {
            "workspace": WorkspaceInfo(
                current_dir="/home/user/my-project", project_dir="/home/user/my-project"
            )
        }
        config = WorkspaceConfig(
            type="workspace",
            color="blue",
            format="{{ workspace.current_dir | basename }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "my-project"

    def test_render_empty_workspace_falls_back_to_cwd(self):
        module = get_module("workspace")
        assert module is not None
        inputs = {
            "workspace": WorkspaceInfo(
                current_dir="/fallback/path", project_dir="/fallback/path"
            )
        }
        config = WorkspaceConfig(
            type="workspace",
            color="blue",
            format="{{ workspace.current_dir | basename }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "path"

    def test_render_empty_both_returns_tilde(self):
        module = get_module("workspace")
        assert module is not None
        inputs = {"workspace": WorkspaceInfo(current_dir="", project_dir="")}
        config = WorkspaceConfig(
            type="workspace",
            color="blue",
            format="{{ workspace.current_dir | basename }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "~"


class TestCostModule:
    def test_render_cost_cents(self):
        module = get_module("cost")
        assert module is not None
        inputs = {"cost": CostInfo(total_cost_usd=0.05)}
        config = CostConfig(
            type="cost",
            color="green",
            format="{{ cost.total_cost_usd | format_cost }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "$0.05"

    def test_render_cost_dollars(self):
        module = get_module("cost")
        assert module is not None
        inputs = {"cost": CostInfo(total_cost_usd=1.23)}
        config = CostConfig(
            type="cost",
            color="green",
            format="{{ cost.total_cost_usd | format_cost }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "$1.23"

    def test_render_cost_small(self):
        module = get_module("cost")
        assert module is not None
        inputs = {"cost": CostInfo(total_cost_usd=0.0012)}
        config = CostConfig(
            type="cost",
            color="green",
            format="{{ cost.total_cost_usd | format_cost }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "$0.0012"


class TestContextModule:
    def test_render_percentage(self):
        module = get_module("context")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=42.5)}
        config = ContextConfig(
            type="context",
            color="yellow",
            format="{{ context.used_percentage | format_percent }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == " 42%"

    def test_render_zero_percentage(self):
        module = get_module("context")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=0.0)}
        config = ContextConfig(
            type="context",
            color="yellow",
            format="{{ context.used_percentage | format_percent }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "  0%"


class TestVersionModule:
    def test_render_version(self):
        module = get_module("version")
        assert module is not None
        inputs = {"version": VersionInfo(version="2.0.76")}
        config = VersionConfig(
            type="version",
            color="dim",
            format="v{{ version.version }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "v2.0.76"

    def test_render_empty_version(self):
        module = get_module("version")
        assert module is not None
        inputs = {"version": VersionInfo(version="?")}
        config = VersionConfig(
            type="version",
            color="dim",
            format="v{{ version.version }}",
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert result == "v?"


class TestBuildContext:
    def test_build_context_structure(self):
        module = get_module("model")
        assert module is not None
        model_info = ModelInfo(id="test-model", display_name="Test Model")
        inputs = {"model": model_info}
        config = ModelConfig(
            type="model",
            color="cyan",
            format="{{ model.display_name }}",
            label="M: ",
            theme="nerd",
        )
        fmt, context = module.build_context(inputs, config)
        assert fmt == "{{ model.display_name }}"
        assert context["model"] is model_info
        assert context["theme"] is config

    def test_build_context_empty_format_raises(self):
        module = get_module("model")
        assert module is not None
        inputs = {"model": ModelInfo()}
        # ModelConfig requires format, so create one with empty string
        config = ModelConfig(
            type="model", color="cyan", format="", theme="nerd"
        )
        try:
            module.build_context(inputs, config)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "no format template" in str(e)


def _make_bar_theme(**overrides) -> BarTheme:
    """Create a BarTheme with defaults for testing."""
    defaults = {
        "left": "",
        "right": "",
        "full": "█",
        "empty": " ",
        "width": 10,
    }
    defaults.update(overrides)
    return BarTheme(**defaults)


class TestContextBarModule:
    def test_render_with_progress_bar_returns_grid(self):
        """context_bar with progress_bar() returns a grid renderable."""
        module = get_module("context_bar")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=42.5)}
        config = ContextBarConfig(
            type="context_bar",
            format="{{ progress_bar(**theme.bar) }} {{ context.used_percentage | format_percent }}",
            bar=_make_bar_theme(),
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert isinstance(result, Table)

    def test_render_without_progress_bar_returns_string(self):
        """context_bar without progress_bar() in format returns a string."""
        module = get_module("context_bar")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=42.5)}
        config = ContextBarConfig(
            type="context_bar",
            format="{{ context.used_percentage | format_percent }}",
            bar=_make_bar_theme(),
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert isinstance(result, str)
        assert result == " 42%"

    def test_progress_bar_accepts_overrides(self):
        """progress_bar() accepts inline overrides via kwargs."""
        module = get_module("context_bar")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=50.0)}
        config = ContextBarConfig(
            type="context_bar",
            format="{{ progress_bar(full='#', empty='.', left='[', right=']') }}",
            bar=_make_bar_theme(),
            theme="nerd",
        )
        result = module.render(inputs, config)
        assert isinstance(result, Table)

    def test_render_no_context_returns_empty(self):
        module = get_module("context_bar")
        assert module is not None
        config = ContextBarConfig(
            type="context_bar",
            format="{{ progress_bar() }}",
            bar=_make_bar_theme(),
            theme="nerd",
        )
        result = module.render({}, config)
        assert result == ""


class TestExpandableBar:
    def _make_console(self, width=80):
        return Console(width=width, force_terminal=False, no_color=True)

    def test_rich_measure_returns_fixed_width(self):
        bar = ExpandableBar(50.0, {"width": 10, "left": "[", "right": "]"})
        console = self._make_console()
        options = console.options
        measurement = bar.__rich_measure__(console, options)
        assert measurement.minimum == 12  # 10 + len("[") + len("]")
        assert measurement.maximum == 12

    def test_rich_console_fills_max_width(self):
        bar = ExpandableBar(50.0, {"width": 10, "left": "[", "right": "]"})
        console = self._make_console(width=40)
        options = console.options.update_width(40)
        segments = list(bar.__rich_console__(console, options))
        # Should produce a Text object whose length matches max_width
        text = segments[0]
        assert len(text) == 40  # [  + 38 bar chars

    def test_percentage_clamped(self):
        bar_low = ExpandableBar(-10.0)
        assert bar_low.percentage == 0.0
        bar_high = ExpandableBar(150.0)
        assert bar_high.percentage == 100.0

    def test_custom_chars(self):
        bar = ExpandableBar(
            50.0, {"full": "#", "empty": ".", "left": "<", "right": ">"}
        )
        console = self._make_console(width=12)
        options = console.options.update_width(12)
        segments = list(bar.__rich_console__(console, options))
        text_str = segments[0].plain
        assert text_str.startswith("<")
        assert text_str.endswith(">")
        assert "#" in text_str
        assert "." in text_str

    def test_fill_state_caps(self):
        """Fill-state caps replace first/last positions with half weight.

        6 chars = 2 caps (10% each) + 4 middle (20% each) = 100%.
        """
        opts = {
            "full": "X",
            "empty": "_",
            "full_left": "<",
            "empty_left": "(",
            "full_right": ">",
            "empty_right": ")",
            "width": 6,
        }
        console = self._make_console(width=6)
        options = console.options.update_width(6)

        def render(pct):
            bar = ExpandableBar(pct, opts)
            return list(bar.__rich_console__(console, options))[0].plain

        assert render(0) == "(____)"  # 0%
        assert render(10) == "<____)"  # 10%: left cap fills
        assert render(30) == "<X___)"  # 30%: +1 middle
        assert render(50) == "<XX__)"  # 50%: +2 middle
        assert render(70) == "<XXX_)"  # 70%: +3 middle
        assert render(90) == "<XXXX)"  # 90%: +4 middle
        assert render(100) == "<XXXX>"  # 100%: right cap fills

    def test_fill_state_caps_with_frame(self):
        """Fill-state caps work together with an outer frame."""
        opts = {
            "full": "X",
            "empty": "_",
            "left": "[",
            "right": "]",
            "full_left": "<",
            "empty_left": "(",
            "full_right": ">",
            "empty_right": ")",
            "width": 6,
        }
        console = self._make_console(width=8)
        options = console.options.update_width(8)

        def render(pct):
            bar = ExpandableBar(pct, opts)
            return list(bar.__rich_console__(console, options))[0].plain

        assert render(0) == "[(____)]"
        assert render(10) == "[<____)]"
        assert render(50) == "[<XX__)]"
        assert render(100) == "[<XXXX>]"


class TestModuleRegistry:
    def test_get_all_modules(self):
        modules = get_all_modules()
        assert "model" in modules
        assert "workspace" in modules
        assert "cost" in modules
        assert "context" in modules
        assert "context_bar" in modules
        assert "version" in modules
        assert "git" in modules

    def test_get_unknown_module_returns_none(self):
        module = get_module("nonexistent")
        assert module is None
