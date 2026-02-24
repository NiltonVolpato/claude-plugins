"""Plan management CLI for Claude Code.

Thin wrapper that re-exports from the plugin script so that the `plan`
console_scripts entry point works with `uv run plan ...`.
"""

from pathlib import Path
import importlib.util
import sys

_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "plugins"
    / "plan-mode"
    / "skills"
    / "plan"
    / "scripts"
    / "plan.py"
)


def _load_plan_module():
    """Dynamically load plan.py from the plugin directory."""
    spec = importlib.util.spec_from_file_location("_plan_impl", _SCRIPT)
    if spec is None or spec.loader is None:
        print(f"Error: Could not load plan script from {_SCRIPT}", file=sys.stderr)
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_plan_module()

# Re-export public API
validate_slug = _mod.validate_slug
slug_to_title = _mod.slug_to_title
plans_dir_for = _mod.plans_dir_for
find_draft = _mod.find_draft
find_draft_appendix = _mod.find_draft_appendix
read_current_plan = _mod.read_current_plan
write_current_plan = _mod.write_current_plan
find_unchecked_items = _mod.find_unchecked_items
cmd_create = _mod.cmd_create
cmd_approve = _mod.cmd_approve
cmd_start = _mod.cmd_start
cmd_done = _mod.cmd_done
cmd_session_check = _mod.cmd_session_check
PLAN_TEMPLATE = _mod.PLAN_TEMPLATE
APPENDIX_TEMPLATE = _mod.APPENDIX_TEMPLATE


def main():
    _mod.main()
