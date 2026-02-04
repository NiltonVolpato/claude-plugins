"""Unit tests for statusline modules."""

from rich.console import Console, ConsoleOptions, RenderableType
from rich.table import Table

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
        result = module.render(inputs, {"format": "{{ model.display_name }}"})
        assert result == "Test Model"

    def test_render_empty_display_name(self):
        module = get_module("model")
        assert module is not None
        inputs = {"model": ModelInfo(id="x", display_name="")}
        result = module.render(inputs, {"format": "{{ model.display_name }}"})
        assert result == ""

    def test_render_with_label(self):
        module = get_module("model")
        assert module is not None
        inputs = {"model": ModelInfo(id="test-model", display_name="Test Model")}
        result = module.render(
            inputs, {"format": "[cyan]{{ theme.label }}{{ model.display_name }}[/cyan]", "label": "\uee0d "}
        )
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
        result = module.render(inputs, {"format": "{{ workspace.current_dir | basename }}"})
        assert result == "my-project"

    def test_render_empty_workspace_falls_back_to_cwd(self):
        module = get_module("workspace")
        assert module is not None
        # Provider handles the fallback, so we test with the fallback already applied
        inputs = {
            "workspace": WorkspaceInfo(current_dir="/fallback/path", project_dir="/fallback/path")
        }
        result = module.render(inputs, {"format": "{{ workspace.current_dir | basename }}"})
        assert result == "path"

    def test_render_empty_both_returns_tilde(self):
        module = get_module("workspace")
        assert module is not None
        inputs = {"workspace": WorkspaceInfo(current_dir="", project_dir="")}
        result = module.render(inputs, {"format": "{{ workspace.current_dir | basename }}"})
        assert result == "~"


class TestCostModule:
    def test_render_cost_cents(self):
        module = get_module("cost")
        assert module is not None
        inputs = {"cost": CostInfo(total_cost_usd=0.05)}
        result = module.render(inputs, {"format": "{{ cost.total_cost_usd | format_cost }}"})
        assert result == "$0.05"

    def test_render_cost_dollars(self):
        module = get_module("cost")
        assert module is not None
        inputs = {"cost": CostInfo(total_cost_usd=1.23)}
        result = module.render(inputs, {"format": "{{ cost.total_cost_usd | format_cost }}"})
        assert result == "$1.23"

    def test_render_cost_small(self):
        module = get_module("cost")
        assert module is not None
        inputs = {"cost": CostInfo(total_cost_usd=0.0012)}
        result = module.render(inputs, {"format": "{{ cost.total_cost_usd | format_cost }}"})
        assert result == "$0.0012"


class TestContextModule:
    def test_render_percentage(self):
        module = get_module("context")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=42.5)}
        result = module.render(inputs, {"format": "{{ context.used_percentage | format_percent }}"})
        assert result == "42%"

    def test_render_zero_percentage(self):
        module = get_module("context")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=0.0)}
        result = module.render(inputs, {"format": "{{ context.used_percentage | format_percent }}"})
        assert result == "0%"


class TestVersionModule:
    def test_render_version(self):
        module = get_module("version")
        assert module is not None
        inputs = {"version": VersionInfo(version="2.0.76")}
        result = module.render(inputs, {"format": "v{{ version.version }}"})
        assert result == "v2.0.76"

    def test_render_empty_version(self):
        module = get_module("version")
        assert module is not None
        # Provider handles the fallback to "?"
        inputs = {"version": VersionInfo(version="?")}
        result = module.render(inputs, {"format": "v{{ version.version }}"})
        assert result == "v?"


class TestBuildContext:
    def test_build_context_structure(self):
        module = get_module("model")
        assert module is not None
        model_info = ModelInfo(id="test-model", display_name="Test Model")
        inputs = {"model": model_info}
        theme_vars = {"format": "{{ model.display_name }}", "label": "M: "}
        fmt, context = module.build_context(inputs, theme_vars)
        assert fmt == "{{ model.display_name }}"
        assert context["model"] is model_info
        assert context["theme"] is theme_vars

    def test_build_context_empty_format(self):
        module = get_module("model")
        assert module is not None
        inputs = {"model": ModelInfo()}
        fmt, context = module.build_context(inputs, {})
        assert fmt == ""


class TestContextBarModule:
    def test_render_with_progress_bar_returns_grid(self):
        """context_bar with progress_bar() returns a grid renderable."""
        module = get_module("context_bar")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=42.5)}
        result = module.render(
            inputs,
            {"format": "{{ progress_bar(**theme.bar) }} {{ context.used_percentage | format_percent }}"},
        )
        assert isinstance(result, Table)

    def test_render_without_progress_bar_returns_string(self):
        """context_bar without progress_bar() in format returns a string."""
        module = get_module("context_bar")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=42.5)}
        result = module.render(
            inputs,
            {"format": "{{ context.used_percentage | format_percent }}"},
        )
        assert isinstance(result, str)
        assert result == "42%"

    def test_progress_bar_accepts_overrides(self):
        """progress_bar() accepts inline overrides via kwargs."""
        module = get_module("context_bar")
        assert module is not None
        inputs = {"context": ContextWindowInfo(used_percentage=50.0)}
        result = module.render(
            inputs,
            {"format": "{{ progress_bar(full='#', empty='.', left='[', right=']') }}"},
        )
        assert isinstance(result, Table)

    def test_render_no_context_returns_empty(self):
        module = get_module("context_bar")
        assert module is not None
        result = module.render({}, {"format": "{{ progress_bar() }}"})
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
        bar = ExpandableBar(50.0, {"full": "#", "empty": ".", "left": "<", "right": ">"})
        console = self._make_console(width=12)
        options = console.options.update_width(12)
        segments = list(bar.__rich_console__(console, options))
        text_str = segments[0].plain
        assert text_str.startswith("<")
        assert text_str.endswith(">")
        assert "#" in text_str
        assert "." in text_str


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
