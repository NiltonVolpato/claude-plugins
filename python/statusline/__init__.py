"""Statusline CLI for Claude Code."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from statusline.config import (
    CONFIG_PATH,
    Config,
    generate_default_config_toml,
    load_config,
)
from statusline.input import get_sample_input, parse_input
from statusline.modules import get_all_modules, get_module_class
from statusline.renderer import render_statusline

app = typer.Typer(
    help="A customizable status line for Claude Code.",
    no_args_is_help=True,
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
    ctx: typer.Context,
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


def _list_modules() -> None:
    """List all module types and configured aliases."""
    config = load_config()
    builtin_modules = get_all_modules()

    typer.echo("Module types:")
    for name in builtin_modules:
        typer.echo(f"  {name}")

    # Find aliases (config entries with a 'type' field)
    aliases = [
        (alias, cfg.type)
        for alias, cfg in config.modules.items()
        if cfg.type is not None
    ]
    if aliases:
        typer.echo("\nConfigured aliases:")
        for alias, module_type in aliases:
            typer.echo(f"  {alias} -> {module_type}")


# `statusline modules` - shorthand alias for `statusline module ls`
@app.command(name="modules")
def modules_shorthand() -> None:
    """List available modules (alias for 'module ls')."""
    _list_modules()


# `statusline module` - subcommand group
module_app = typer.Typer()
app.add_typer(module_app, name="module", help="Manage modules.")


@module_app.command(name="ls")
def module_ls() -> None:
    """List all module types and configured aliases."""
    _list_modules()


@module_app.command(name="info")
def module_info(
    name: Annotated[str, typer.Argument(help="Module name or alias to inspect.")],
) -> None:
    """Show details about a module or alias."""
    config = load_config()

    # Check if it's an alias
    module_config = config.modules.get(name)
    if module_config and module_config.type:
        typer.echo(f"Alias: {name}")
        typer.echo(f"Type: {module_config.type}")
        if module_config.format:
            typer.echo(f"Format: {module_config.format}")
        module_type = module_config.type
    else:
        module_type = name

    # Get module class info
    module_cls = get_module_class(module_type)
    if module_cls is None:
        typer.echo(f"Unknown module: {module_type}", err=True)
        raise typer.Exit(1)

    typer.echo(f"\nTemplate variables for '{module_type}':")
    for var_name, description in module_cls.get_template_vars().items():
        if description:
            typer.echo(f"  {{ {var_name} }} - {description}")
        else:
            typer.echo(f"  {{ {var_name} }}")

    # Render a preview with sample data
    preview_config = config.model_copy(update={"enabled": [name]})
    sample_input = get_sample_input()
    output = render_statusline(sample_input, preview_config)
    typer.echo(f"\nPreview: {output}")


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


def main() -> None:
    """Entry point for the CLI."""
    app()
