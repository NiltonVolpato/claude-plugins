#!/usr/bin/env python3
"""Plan management CLI for Claude Code plugin.

Subcommands:
  create <slug>     Create a new draft plan
  approve <slug>    Approve a draft plan
  start             Start implementing the current plan
  done              Mark the current plan as done
  session-check     Hook: check for active plan on session start
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

PLAN_TEMPLATE = """\
# {title}

## Context

<!-- Why is this change needed? What problem does it solve? -->

## Implementation Steps

<!-- Each step should be a checkbox. Be specific enough that a fresh session can follow. -->

- [ ] Step 1
- [ ] Step 2

## Verification

<!-- How to verify the implementation is correct -->

- [ ] Tests pass
- [ ] Manual verification
"""

APPENDIX_TEMPLATE = """\
# {title} — Appendix

## Codebase Findings

<!-- File paths, API notes, patterns with file:line references -->

## Architecture Notes

<!-- Key design decisions, constraints, trade-offs -->

## References

<!-- Links, docs, related issues -->
"""


def validate_slug(slug: str) -> None:
    """Validate that a slug matches the required pattern."""
    if not SLUG_PATTERN.match(slug):
        print(
            f"Error: Invalid slug '{slug}'. "
            "Must be lowercase letters, digits, and hyphens only "
            "(e.g., 'add-authentication').",
            file=sys.stderr,
        )
        sys.exit(1)


def slug_to_title(slug: str) -> str:
    """Convert a slug to a human-readable title."""
    return " ".join(word.capitalize() for word in slug.split("-"))


def plans_dir_for(cwd: str) -> Path:
    """Return the plans directory for a given working directory."""
    return Path(cwd) / ".claude" / "plans"


def extract_slug_from_draft(path: Path) -> str:
    """Extract the slug from a draft filename like '2026-02-24_04-48_add-auth.md'."""
    stem = path.stem
    # Remove the datetime prefix (YYYY-MM-DD_HH-MM_)
    parts = stem.split("_", 2)
    if len(parts) >= 3:
        return parts[2]
    return stem


def find_draft(drafts_dir: Path, slug: str) -> Path | None:
    """Find the most recent draft matching the given slug."""
    pattern = f"*_{slug}.md"
    matches = sorted(drafts_dir.glob(pattern), reverse=True)
    if matches:
        return matches[0]
    return None


def find_latest_draft(drafts_dir: Path) -> Path | None:
    """Find the most recent draft plan (excluding appendices)."""
    all_drafts = sorted(drafts_dir.glob("*.md"), reverse=True)
    for draft in all_drafts:
        if not draft.stem.endswith("-appendix"):
            return draft
    return None


def find_draft_appendix(drafts_dir: Path, slug: str) -> Path | None:
    """Find the most recent draft appendix matching the given slug."""
    pattern = f"*_{slug}-appendix.md"
    matches = sorted(drafts_dir.glob(pattern), reverse=True)
    if matches:
        return matches[0]
    return None


def read_current_draft(plans_dir: Path) -> dict | None:
    """Read current-draft.json, returning None if it doesn't exist."""
    draft_file = plans_dir / "current-draft.json"
    if not draft_file.exists():
        return None
    return json.loads(draft_file.read_text())


def write_current_draft(plans_dir: Path, data: dict) -> None:
    """Write current-draft.json."""
    draft_file = plans_dir / "current-draft.json"
    draft_file.write_text(json.dumps(data, indent=2) + "\n")


def remove_current_draft(plans_dir: Path) -> None:
    """Remove current-draft.json if it exists."""
    draft_file = plans_dir / "current-draft.json"
    if draft_file.exists():
        draft_file.unlink()


def read_current_plan(plans_dir: Path) -> dict | None:
    """Read current-plan.json, returning None if it doesn't exist."""
    current_file = plans_dir / "current-plan.json"
    if not current_file.exists():
        return None
    return json.loads(current_file.read_text())


def write_current_plan(plans_dir: Path, data: dict) -> None:
    """Write current-plan.json."""
    current_file = plans_dir / "current-plan.json"
    current_file.write_text(json.dumps(data, indent=2) + "\n")


def find_unchecked_items(plan_file: Path) -> list[str]:
    """Find all unchecked checkbox items in a plan file."""
    text = plan_file.read_text()
    unchecked = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            unchecked.append(stripped[6:].strip())
    return unchecked


# ── Subcommands ──────────────────────────────────────────────────────────────


def cmd_create(slug: str, cwd: str | None = None, now: datetime | None = None) -> None:
    """Create a new draft plan with the given slug."""
    validate_slug(slug)

    if cwd is None:
        cwd = str(Path.cwd())
    if now is None:
        now = datetime.now()

    plans = plans_dir_for(cwd)
    drafts = plans / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)

    datetime_str = now.strftime("%Y-%m-%d_%H-%M")
    title = slug_to_title(slug)

    plan_file = drafts / f"{datetime_str}_{slug}.md"
    appendix_file = drafts / f"{datetime_str}_{slug}-appendix.md"

    plan_file.write_text(PLAN_TEMPLATE.format(title=title))
    appendix_file.write_text(APPENDIX_TEMPLATE.format(title=title))

    write_current_draft(plans, {
        "slug": slug,
        "title": title,
        "plan_file": str(plan_file),
        "appendix_file": str(appendix_file),
        "created_at": now.isoformat(timespec="seconds"),
    })

    print(f"Draft plan created:")
    print(f"  Plan:     {plan_file}")
    print(f"  Appendix: {appendix_file}")
    print()
    print("Fill in the plan and appendix, then run `/plan-mode:plan-approve` when ready.")


def cmd_approve(slug: str | None = None, cwd: str | None = None, now: datetime | None = None) -> None:
    """Approve a draft plan by slug, or the most recent draft if no slug given."""
    if slug is not None:
        validate_slug(slug)

    if cwd is None:
        cwd = str(Path.cwd())
    if now is None:
        now = datetime.now()

    plans = plans_dir_for(cwd)
    drafts = plans / "drafts"

    if slug is not None:
        plan_file = find_draft(drafts, slug)
        if plan_file is None:
            print(f"Error: No draft plan found matching slug '{slug}'.", file=sys.stderr)
            sys.exit(1)
    else:
        # Try current-draft.json first, then fall back to latest draft file
        current_draft = read_current_draft(plans)
        if current_draft is not None:
            slug = current_draft["slug"]
            plan_file = find_draft(drafts, slug)
        else:
            plan_file = find_latest_draft(drafts)
        if plan_file is None:
            print("Error: No draft plans found.", file=sys.stderr)
            sys.exit(1)
        if slug is None:
            slug = extract_slug_from_draft(plan_file)

    appendix_file = find_draft_appendix(drafts, slug)

    approved_dir = plans / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    datetime_str = now.strftime("%Y-%m-%d_%H-%M")
    title = slug_to_title(slug)

    approved_plan = approved_dir / f"{datetime_str}_{slug}.md"
    approved_plan.write_text(plan_file.read_text())

    approved_appendix = None
    if appendix_file is not None:
        approved_appendix = approved_dir / f"{datetime_str}_{slug}-appendix.md"
        approved_appendix.write_text(appendix_file.read_text())

    current_plan_data = {
        "slug": slug,
        "title": title,
        "plan_file": str(approved_plan),
        "approved_at": now.isoformat(timespec="seconds"),
        "status": "approved",
    }
    if approved_appendix is not None:
        current_plan_data["appendix_file"] = str(approved_appendix)

    write_current_plan(plans, current_plan_data)
    remove_current_draft(plans)

    print(f"Plan approved: {title}")
    print(f"  Plan:     {approved_plan}")
    if approved_appendix:
        print(f"  Appendix: {approved_appendix}")
    print(f"  Status:   {plans / 'current-plan.json'}")


def cmd_start(cwd: str | None = None, now: datetime | None = None) -> None:
    """Start implementing the current approved plan."""
    if cwd is None:
        cwd = str(Path.cwd())
    if now is None:
        now = datetime.now()

    plans = plans_dir_for(cwd)
    current = read_current_plan(plans)

    if current is None:
        print("Error: No current plan found. Approve a plan first.", file=sys.stderr)
        sys.exit(1)

    if current["status"] == "in_progress":
        print(f"Plan already in progress: {current['title']}")
        print(f"  Plan: {current['plan_file']}")
        if "appendix_file" in current:
            print(f"  Appendix: {current['appendix_file']}")
        return

    current["status"] = "in_progress"
    current["started_at"] = now.isoformat(timespec="seconds")
    write_current_plan(plans, current)

    print(f"Started plan: {current['title']}")
    print(f"  Plan: {current['plan_file']}")
    if "appendix_file" in current:
        print(f"  Appendix: {current['appendix_file']}")


def cmd_done(cwd: str | None = None) -> None:
    """Mark the current plan as done (if all checkboxes are ticked)."""
    if cwd is None:
        cwd = str(Path.cwd())

    plans = plans_dir_for(cwd)
    current = read_current_plan(plans)

    if current is None:
        print("Error: No current plan found.", file=sys.stderr)
        sys.exit(1)

    plan_file = Path(current["plan_file"])
    if not plan_file.exists():
        print(f"Error: Plan file not found: {plan_file}", file=sys.stderr)
        sys.exit(1)

    unchecked = find_unchecked_items(plan_file)
    if unchecked:
        print(f"Error: {len(unchecked)} unchecked item(s) remain:", file=sys.stderr)
        for item in unchecked:
            print(f"  - [ ] {item}", file=sys.stderr)
        sys.exit(1)

    (plans / "current-plan.json").unlink()
    print(f"Plan completed: {current['title']}")


def cmd_session_check(hook_input: dict) -> None:
    """Hook: check for active plan on session start."""
    cwd = hook_input.get("cwd", "")
    if not cwd:
        return

    plans = plans_dir_for(cwd)
    current = read_current_plan(plans)
    if current is None:
        return

    status = current["status"]
    title = current["title"]
    plan_file = current["plan_file"]
    appendix_file = current.get("appendix_file", "")

    if status == "approved":
        message = (
            f"A plan has been approved but not started: **{title}**. "
            f"Read the plan at `{plan_file}`"
        )
        if appendix_file:
            message += f" and appendix at `{appendix_file}`"
        message += (
            ". Ask the user if they want to start implementing. "
            "Run `plan start` when ready."
        )
    elif status == "in_progress":
        message = (
            f"A plan is in progress: **{title}**. "
            f"Read the plan at `{plan_file}` (check checkboxes for progress)"
        )
        if appendix_file:
            message += f" and appendix at `{appendix_file}`"
        message += (
            ". Continue from where it left off. "
            "Run `plan done` when all tasks are complete."
        )
    else:
        return

    output = {"hookSpecificOutput": {"additionalContext": message}}
    print(json.dumps(output))


# ── CLI entry point ──────────────────────────────────────────────────────────


def main(args: list[str] | None = None) -> None:
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: plan <create|approve|start|done|session-check> [args]", file=sys.stderr)
        sys.exit(1)

    command = args[0]

    if command == "create":
        if len(args) < 2:
            print("Usage: plan create <slug>", file=sys.stderr)
            sys.exit(1)
        cmd_create(args[1])

    elif command == "approve":
        cmd_approve(args[1] if len(args) >= 2 else None)

    elif command == "start":
        cmd_start()

    elif command == "done":
        cmd_done()

    elif command == "session-check":
        hook_input = json.loads(sys.stdin.read())
        cmd_session_check(hook_input)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
