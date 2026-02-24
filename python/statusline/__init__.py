"""Statusline CLI for Claude Code."""

from __future__ import annotations

import json
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Annotated

import typer
from rich import markup, table
from rich.console import Console
from rich.tree import Tree

from statusline.config import (
    CONFIG_PATH,
    Config,
    generate_default_config_toml,
    get_config_class,
    load_config,
)
from statusline.errors import StatuslineError, report_error
from statusline.events_logger import log_event_from_stdin
from statusline.input import get_sample_input, parse_input
from statusline.modules import get_module
from statusline.renderer import render_statusline

try:
    from tomli_w import _writer

    def format_string(s):
        return _writer.format_string(s, allow_multiline=True)
except ImportError:

    def format_string(s):
        return repr(s)


class Context(typer.Context):
    obj: Env


app = typer.Typer(
    help="A customizable status line for Claude Code.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

# Module-level flag so main() can access it outside the typer context.
_no_fail = False


class Env:
    __slots__ = ("console", "config_path")
    console: Console
    config_path: Path | None

    def __init__(self, **fields):
        for name, value in fields.items():
            setattr(self, name, value)


@app.callback()
def app_main(
    ctx: Context,
    force_terminal: bool | None = None,
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to config file (use /dev/null to skip user config).",
        ),
    ] = None,
    no_fail: Annotated[
        bool,
        typer.Option(
            "--no-fail",
            help="Exit 0 even on errors (shows error in status line instead of failing).",
        ),
    ] = False,
):
    global _no_fail
    _no_fail = no_fail
    ctx.obj = Env(
        console=Console(force_terminal=force_terminal, highlight=True),
        config_path=config_path,
    )


def parse_modules(modules_str: str) -> list[str]:
    """Parse comma-separated module names."""
    return [m.strip() for m in modules_str.split(",") if m.strip()]


def merge_cli_options(
    config: Config,
    modules: str | None,
    separator: str | None,
    theme: str | None,
    color: bool,
    width: int | None = None,
) -> Config:
    """Merge CLI options into config, with CLI taking precedence."""
    new_theme = theme if theme else config.theme
    new_modules = config.modules

    # If theme changed, update modules with new theme
    if new_theme != config.theme:
        # Assignment triggers model_validator to apply new theme's overrides
        new_modules = {}
        for name, module_config in config.modules.items():
            new_cfg = module_config.model_copy()
            new_cfg.theme = new_theme
            new_modules[name] = new_cfg

    return Config(
        theme=new_theme,
        color=color,
        enabled=parse_modules(modules) if modules else config.enabled,
        separator=separator if separator is not None else config.separator,
        width=width if width is not None else config.width,
        modules=new_modules,
    )


@app.command()
def render(
    ctx: Context,
    modules: Annotated[
        str | None,
        typer.Option(
            "--modules",
            "-m",
            help="Comma-separated list of modules to display.",
        ),
    ] = None,
    separator: Annotated[
        str | None,
        typer.Option(
            "--separator",
            "-s",
            help="Separator between modules.",
        ),
    ] = None,
    theme: Annotated[
        str | None,
        typer.Option(
            "--theme",
            "-t",
            help="Theme: nerd, ascii, emoji, or minimal.",
        ),
    ] = None,
    width: Annotated[
        int | None,
        typer.Option(
            "--width",
            "-w",
            help="Terminal width override for layout.",
        ),
    ] = None,
    color: Annotated[
        bool,
        typer.Option(
            "--color/--no-color",
            help="Enable or disable colors.",
        ),
    ] = True,
) -> None:
    """Render the status line (reads JSON from stdin)."""
    config = load_config(ctx.obj.config_path)
    config = merge_cli_options(config, modules, separator, theme, color, width)
    if ctx.command.name == "render":
        if sys.stdin.isatty():
            report_error(
                "no input",
                ValueError("'render' expects JSON input via stdin"),
            )
        input_data = parse_input(sys.stdin)
    else:
        input_data = get_sample_input()
    output = render_statusline(input_data, config)
    print(output)


preview = app.command(name="preview", help="Render a preview of the status line")(
    render
)


GITHUB_SOURCE = "git+https://github.com/NiltonVolpato/claude-plugins"


@app.command()
def install(
    local: bool = typer.Option(
        False, "--local", help="Use local code for development (editable install from local checkout)"
    ),
) -> None:
    """Configure Claude Code to use this statusline.

    This command:
    1. Installs the statusline tool via `uv tool install`
    2. Configures the statusLine render command in settings
    3. Prints instructions for enabling the event-logging plugin

    For --local: installs in editable mode from the local checkout.
    Otherwise: installs from GitHub.

    NOTE: The plugin must be installed/enabled separately for event logging.
    Without it, the statusline renders but the events module shows nothing.
    """
    # Find the project root (where pyproject.toml lives)
    project_root = Path(__file__).parent.parent.parent.resolve()

    # Install the tool persistently via uv tool install
    if local:
        install_cmd = ["uv", "tool", "install", "--force", "-e", str(project_root)]
    else:
        install_cmd = ["uv", "tool", "install", "--force", "--from", GITHUB_SOURCE, "nv-claude-plugins"]
    typer.echo(f"Running: {' '.join(install_cmd)}")
    subprocess.run(install_cmd, check=True)

    # Configure settings.json — tool is now on PATH
    settings_path = Path.home() / ".claude" / "settings.json"

    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            pass

    settings["statusLine"] = {
        "type": "command",
        "command": "statusline --no-fail render",
    }

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    typer.echo(f"Statusline render configured in {settings_path}")

    typer.echo("\nTo enable event logging, install the plugin:")
    typer.echo("  /plugin install statusline@nv-claude-plugins")

    if local:
        plugin_path = project_root / "plugins" / "statusline"
        typer.echo(f"\nTo test with the local plugin, restart Claude Code with:")
        typer.echo(f"  claude --plugin-dir {plugin_path}")
    else:
        typer.echo("\nRestart Claude Code to see the changes.")


@app.command(name="log-event", hidden=True)
def log_event_cmd() -> None:
    """Log an event to the database (called by hooks)."""
    log_event_from_stdin()


# `statusline module` - subcommand group
module_app = typer.Typer()
app.add_typer(module_app, name="module", help="Manage modules.")


@module_app.command(name="ls")
def module_ls(ctx: Context) -> None:
    """List all module types and configured aliases."""
    console = ctx.obj.console
    config = load_config(ctx.obj.config_path)

    t = table.Table(
        table.Column("Module Name", justify="left", style="blue"),
        table.Column("Description", justify="left"),
        box=None,
        pad_edge=False,
        header_style="bold dim",
    )
    for name, cfg in config.modules.items():
        module = get_module(cfg.type or name)
        description = module.__doc__ or ""
        if cfg.type is not None:
            description += f" [dim](type: {cfg.type})[/]"
        t.add_row(name, description)
    console.print(t)


# `statusline modules` - shorthand alias for `statusline module ls`
modules = app.command(
    name="modules", help="List available modules (alias for `module ls`)."
)(module_ls)


@module_app.command(name="info")
def module_info(
    ctx: Context,
    name: Annotated[str, typer.Argument(help="Module name or alias to inspect.")],
) -> None:
    """Show details about a module or alias."""
    console = ctx.obj.console
    config = load_config(ctx.obj.config_path)

    t = table.Table(
        table.Column(justify="right", style="bold"),
        table.Column(justify="left"),
        box=None,
        pad_edge=False,
        show_header=False,
    )
    module_config = config.modules.get(name)
    if module_config:
        module_type = module_config.type
        fmt = getattr(module_config, "format", None)
        module_format = markup.escape(format_string(fmt)) if fmt else None
    else:
        module_type = name
        module_format = None

    module = get_module(module_type or name)
    if module is None:
        report_error(
            f"unknown module '{name}'",
            ValueError(f"no module found for '{module_type or name}'"),
        )

    t.add_row("Name", name)
    if module_type is not None:
        t.add_row("Type", module_type)
    if module.__doc__:
        t.add_row("Description", module.__doc__)
    if module_format is not None:
        t.add_row("Format", module_format)

    # Render a preview with sample data
    preview_config = config.model_copy(update={"enabled": [name]})
    sample_input = get_sample_input()
    output = render_statusline(sample_input, preview_config)

    t.add_row("Preview", output)
    console.print(t)
    console.print()

    tree = Tree("[bold]Template variables[/]")

    # Inputs section — iterate __inputs__
    for input_cls in module.__inputs__:
        input_name = input_cls.name
        input_doc = input_cls.__doc__ or ""
        branch = tree.add(f"[green]{input_name}[/] [dim]({input_doc.strip()})[/]")
        for field_name, field_info in input_cls.model_fields.items():
            desc = field_info.description or ""
            branch.add(f"[bold red].[/][green]{field_name}[/] [dim]{desc}[/]")

    # Theme section — show theme vars from config
    def add_vars(branch: Tree, data: dict) -> None:
        for key, val in data.items():
            if isinstance(val, dict):
                child = branch.add(f"[bold red].[/][green]{key}[/]")
                add_vars(child, val)
            else:
                branch.add(
                    f"[bold red].[/][green]{key}[/] {markup.escape(format_string(val))}"
                )

    if module_config:
        for theme_name, theme_vars in sorted(module_config.themes.items()):
            theme_branch = tree.add(f"[green]theme[/] [dim].{theme_name}[/]")
            if isinstance(theme_vars, dict):
                add_vars(theme_branch, theme_vars)

    console.print(tree)

    # Configuration options section
    config_cls = get_config_class(module_type or name)
    if config_cls is not None:
        _INTERNAL_FIELDS = {"type", "theme", "themes"}

        def add_config_fields(branch: Tree, model_cls: type) -> None:
            from pydantic import BaseModel

            for field_name, field_info in model_cls.model_fields.items():
                if field_name in _INTERNAL_FIELDS:
                    continue
                desc = field_info.description or ""
                annotation = field_info.annotation
                # Check if annotation is a nested BaseModel class
                is_nested = isinstance(annotation, type) and issubclass(
                    annotation, BaseModel
                )
                if is_nested:
                    child = branch.add(
                        f"[bold red].[/][green]{field_name}[/] [dim]{desc}[/]"
                    )
                    add_config_fields(child, annotation)
                else:
                    default = field_info.default
                    default_str = ""
                    if default is not None and not repr(default).endswith(
                        "PydanticUndefined"
                    ):
                        default_str = f" [dim italic](default: {markup.escape(repr(default))})[/]"
                    branch.add(
                        f"[bold red].[/][green]{field_name}[/] [dim]{desc}[/]{default_str}"
                    )

        config_tree = Tree("[bold]Configuration options[/]")
        add_config_fields(config_tree, config_cls)
        console.print()
        console.print(config_tree)


@app.command()
def config(
    init: Annotated[
        bool,
        typer.Option(
            "--init",
            help="Initialize config file with defaults.",
        ),
    ] = False,
    show: Annotated[
        bool,
        typer.Option(
            "--show",
            help="Show current configuration.",
        ),
    ] = False,
) -> None:
    """Manage statusline configuration."""
    if init:
        # Create config file with defaults
        if CONFIG_PATH.exists():
            report_error(
                "config already exists",
                FileExistsError(str(CONFIG_PATH)),
            )

        CONFIG_PATH.write_text(generate_default_config_toml())
        typer.echo(f"Created config file at {CONFIG_PATH}")
        return

    # Default: show config info
    if CONFIG_PATH.exists():
        typer.echo(f"Config file: {CONFIG_PATH}")
        if show:
            typer.echo("")
            typer.echo(CONFIG_PATH.read_text())
    else:
        typer.echo(f"No config file found at {CONFIG_PATH}")
        typer.echo("Run 'statusline config --init' to create one.")


def main() -> None:
    """Entry point for the CLI."""
    try:
        try:
            app()
        except StatuslineError:
            raise
        except Exception as exc:
            report_error("unexpected error", exc)
    except StatuslineError:
        if _no_fail:
            traceback.print_exc(file=sys.stderr)
            return
        raise
