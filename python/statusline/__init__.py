"""Statusline CLI for Claude Code."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich import markup, table
from rich.console import Console

from statusline.config import (
    CONFIG_PATH,
    Config,
    generate_default_config_toml,
    load_config,
)
from statusline.input import get_sample_input, parse_input
from statusline.modules import get_module
from statusline.renderer import render_statusline


class Context(typer.Context):
    obj: Env


app = typer.Typer(
    help="A customizable status line for Claude Code.",
    no_args_is_help=True,
)


class Env:
    __slots__ = ("console",)
    console: Console

    def __init__(self, **fields):
        for name, value in fields.items():
            setattr(self, name, value)


@app.callback()
def main(ctx: Context, force_terminal: bool | None = None):
    ctx.obj = Env(console=Console(force_terminal=force_terminal))


def parse_modules(modules_str: str) -> list[str]:
    """Parse comma-separated module names."""
    return [m.strip() for m in modules_str.split(",") if m.strip()]


def merge_cli_options(
    config: Config,
    modules: str | None,
    separator: str | None,
    theme: str | None,
    color: bool,
) -> Config:
    """Merge CLI options into config, with CLI taking precedence."""
    return Config(
        theme=theme if theme else config.theme,
        color=color,
        enabled=parse_modules(modules) if modules else config.enabled,
        separator=separator if separator is not None else config.separator,
        modules=config.modules,
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
    color: Annotated[
        bool,
        typer.Option(
            "--color/--no-color",
            help="Enable or disable colors.",
        ),
    ] = True,
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to config file (use /dev/null to skip user config).",
        ),
    ] = None,
) -> None:
    """Render the status line (reads JSON from stdin)."""
    config = load_config(config_path)
    config = merge_cli_options(config, modules, separator, theme, color)
    if ctx.command.name == "render":
        if sys.stdin.isatty():
            typer.echo(
                "Error: 'render' expects JSON input via stdin.\n"
                "Use 'statusline preview' to see sample output, or pipe JSON to this command.",
                err=True,
            )
            raise typer.Exit(1)
        input_data = parse_input(sys.stdin)
    else:
        input_data = get_sample_input()
    output = render_statusline(input_data, config)
    print(output)


preview = app.command(name="preview", help="Render a preview of the status line")(
    render
)


@app.command()
def install() -> None:
    """Configure Claude Code to use this statusline."""
    settings_path = Path.home() / ".claude" / "settings.json"

    # Load existing settings or create new
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            pass

    # Update statusLine configuration
    settings["statusLine"] = {
        "type": "command",
        "command": "uvx --from git+https://github.com/NiltonVolpato/claude-plugins statusline render",
    }

    # Ensure directory exists
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Write settings
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    typer.echo(f"Statusline configured in {settings_path}")
    typer.echo("Restart Claude Code to see the changes.")


# `statusline module` - subcommand group
module_app = typer.Typer()
app.add_typer(module_app, name="module", help="Manage modules.")


@module_app.command(name="ls")
def module_ls(ctx: Context) -> None:
    """List all module types and configured aliases."""
    console = ctx.obj.console
    config = load_config()

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
    config = load_config()

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
        module_format = markup.escape(module_config.format)
    else:
        module_type = name
        module_format = None

    module = get_module(module_type or name)
    if module is None:
        typer.secho(f"Module [b]{name} unknown")
        raise typer.Exit(code=2)

    t.add_row("Name", name)
    if module_type is not None:
        t.add_row("Type", module_type)
    if module.__doc__:
        t.add_row("Doc", module.__doc__)
    if module_format is not None:
        t.add_row("Format", module_format)

    # Render a preview with sample data
    preview_config = config.model_copy(update={"enabled": [name]})
    sample_input = get_sample_input()
    output = render_statusline(sample_input, preview_config)

    t.add_row("Preview", output)
    console.print(t)
    console.print()

    console.print("[bold]Template variables:[/]")
    t = table.Table(
        table.Column(style="green", justify="right"), show_header=False, box=None
    )
    for name, description in module.get_template_vars().items():
        t.add_row(name, description)
    console.print(t)


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
            typer.echo(f"Config file already exists at {CONFIG_PATH}")
            raise typer.Exit(1)

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
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


# def main() -> None:
#     """Entry point for the CLI."""
#     app()
