#!/usr/bin/env python3
"""Plan management CLI for Claude Code plugin.

Subcommands:
  create <slug>           Create a new draft plan
  approve                 Approve the current draft plan
  start                   Start implementing the current plan
  done                    Mark the current plan as done
  list                    List all pending plans
  session-check           Hook: check for active plan on session start
"""

import argparse
import getpass
import json
import os
import re
import socket
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

DB_FILENAME = "plans.db"

PLAN_TEMPLATE = """\
# {title}

## Context

## Verification
"""

APPENDIX_TEMPLATE = """\
# {title} — Appendix

## Codebase Findings

## Architecture Notes

## References
"""

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'in_progress', 'done')),
    plan_file TEXT NOT NULL,
    appendix_file TEXT,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS plan_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    session_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(plan_id, session_id)
);
"""


# ── Database helpers ─────────────────────────────────────────────────────────


def open_db(plans_dir: Path) -> sqlite3.Connection:
    """Open (or create) the plans database, ensuring schema exists."""
    plans_dir.mkdir(parents=True, exist_ok=True)
    db_path = plans_dir / DB_FILENAME
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def open_db_if_exists(plans_dir: Path) -> sqlite3.Connection | None:
    """Open the plans database only if it already exists. Returns None otherwise."""
    db_path = plans_dir / DB_FILENAME
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Convert a sqlite3.Row to a plain dict, or None if row is None."""
    if row is None:
        return None
    return dict(row)


def get_current_draft(conn: sqlite3.Connection) -> dict | None:
    """Get the most recent draft plan, or None."""
    row = conn.execute(
        "SELECT * FROM plans WHERE status = 'draft' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return _row_to_dict(row)


def get_current_plan(conn: sqlite3.Connection) -> dict | None:
    """Get the most recent approved or in-progress plan, or None."""
    row = conn.execute(
        "SELECT * FROM plans WHERE status IN ('approved', 'in_progress') "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return _row_to_dict(row)


def list_pending_plans(conn: sqlite3.Connection) -> list[dict]:
    """List all plans that are not done."""
    rows = conn.execute(
        "SELECT * FROM plans WHERE status != 'done' ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


def record_session(
    conn: sqlite3.Connection, plan_id: int, session_id: str, now: datetime
) -> None:
    """Record a session interaction with a plan (insert or update last_seen)."""
    timestamp = now.isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO plan_sessions (plan_id, session_id, first_seen_at, last_seen_at) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(plan_id, session_id) DO UPDATE SET last_seen_at = ?",
        (plan_id, session_id, timestamp, timestamp, timestamp),
    )


# ── Utility functions ────────────────────────────────────────────────────────


def get_identity(agent: str | None = None) -> str:
    """Return an identity string for log entries.

    If agent is provided, returns 'agent:<name>'.
    Otherwise returns 'user@hostname'.
    """
    if agent is not None:
        return f"agent:{agent}"
    return f"{getpass.getuser()}@{socket.gethostname()}"


def format_log_entry(now: datetime, identity: str, action: str) -> str:
    """Format a single log entry line."""
    timestamp = now.strftime("%Y-%m-%d %H:%M")
    return f"- {timestamp} — {action} by {identity}"


def append_log_entry(plan_file: Path, entry: str) -> None:
    """Append a log entry to a plan file, creating the Log section if needed."""
    text = plan_file.read_text()
    if "\n## Log\n" in text:
        text = text.rstrip("\n") + "\n" + entry + "\n"
    else:
        text = text.rstrip("\n") + "\n\n## Log\n\n" + entry + "\n"
    plan_file.write_text(text)


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


_UNCHECKED_PATTERNS = [
    re.compile(r"#+ \[ \] (.*)"),  # ### [ ] Heading
    re.compile(r"- \[ \] (.*)"),   # - [ ] Bullet
]


def find_unchecked_items(plan_file: Path) -> list[str]:
    """Find all unchecked checkbox items in a plan file.

    Skips items inside fenced code blocks (``` or ~~~).
    """
    text = plan_file.read_text()
    unchecked = []
    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for pattern in _UNCHECKED_PATTERNS:
            m = pattern.fullmatch(stripped)
            if m:
                unchecked.append(m.group(1).strip())
                break
    return unchecked


# ── Subcommands ──────────────────────────────────────────────────────────────


def cmd_create(
    slug: str,
    *,
    prompt: str | None = None,
    agent: str | None = None,
    force: bool = False,
    cwd: str | None = None,
    now: datetime | None = None,
) -> None:
    """Create a new draft plan with the given slug."""
    validate_slug(slug)

    if cwd is None:
        cwd = str(Path.cwd())
    if now is None:
        now = datetime.now()

    plans = plans_dir_for(cwd)
    conn = open_db(plans)

    existing_draft = get_current_draft(conn)
    if existing_draft is not None and not force:
        print(
            f"Error: A draft already exists: {existing_draft['title']}\n"
            f"  File: {existing_draft['plan_file']}\n"
            "Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)

    if existing_draft is not None and force:
        conn.execute(
            "UPDATE plans SET status = 'done', completed_at = ? WHERE id = ?",
            (now.isoformat(timespec="seconds"), existing_draft["id"]),
        )

    drafts = plans / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)

    datetime_str = now.strftime("%Y-%m-%d_%H-%M")
    title = slug_to_title(slug)

    plan_file = drafts / f"{datetime_str}_{slug}.md"
    appendix_file = drafts / f"{datetime_str}_{slug}-appendix.md"

    plan_file.write_text(PLAN_TEMPLATE.format(title=title))
    appendix_file.write_text(APPENDIX_TEMPLATE.format(title=title))

    identity = get_identity(agent)
    action = "Created"
    if prompt:
        action += f' (prompt: "{prompt}")'
    append_log_entry(plan_file, format_log_entry(now, identity, action))

    conn.execute(
        "INSERT INTO plans (slug, title, status, plan_file, appendix_file, created_at) "
        "VALUES (?, ?, 'draft', ?, ?, ?)",
        (slug, title, str(plan_file), str(appendix_file), now.isoformat(timespec="seconds")),
    )
    conn.commit()

    print(f"Draft plan created:")
    print(f"  Plan:     {plan_file}")
    print(f"  Appendix: {appendix_file}")
    print()
    print("Fill in the plan and appendix, then run `/plan-mode:plan+approve` when ready.")


def cmd_approve(
    *,
    agent: str | None = None,
    force: bool = False,
    cwd: str | None = None,
    now: datetime | None = None,
) -> None:
    """Approve the current draft plan."""
    if cwd is None:
        cwd = str(Path.cwd())
    if now is None:
        now = datetime.now()

    plans = plans_dir_for(cwd)
    conn = open_db(plans)

    existing_plan = get_current_plan(conn)
    if existing_plan is not None and not force:
        print(
            f"Error: A plan is already active: {existing_plan['title']} "
            f"(status: {existing_plan['status']})\n"
            f"  File: {existing_plan['plan_file']}\n"
            "Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)

    if existing_plan is not None and force:
        conn.execute(
            "UPDATE plans SET status = 'done', completed_at = ? WHERE id = ?",
            (now.isoformat(timespec="seconds"), existing_plan["id"]),
        )

    current_draft = get_current_draft(conn)
    if current_draft is None:
        print("Error: No current draft found. Run `plan create` first.", file=sys.stderr)
        sys.exit(1)

    slug = current_draft["slug"]
    plan_file = Path(current_draft["plan_file"])
    appendix_file_str = current_draft.get("appendix_file")
    appendix_file = Path(appendix_file_str) if appendix_file_str else None

    if not plan_file.exists():
        print(f"Error: Draft plan file not found: {plan_file}", file=sys.stderr)
        sys.exit(1)

    # Append approve log entry before moving
    identity = get_identity(agent)
    append_log_entry(plan_file, format_log_entry(now, identity, "Approved"))

    approved_dir = plans / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    datetime_str = now.strftime("%Y-%m-%d_%H-%M")
    title = slug_to_title(slug)

    approved_plan = approved_dir / f"{datetime_str}_{slug}.md"
    plan_file.rename(approved_plan)

    approved_appendix = None
    if appendix_file is not None and appendix_file.exists():
        approved_appendix = approved_dir / f"{datetime_str}_{slug}-appendix.md"
        appendix_file.rename(approved_appendix)

    conn.execute(
        "UPDATE plans SET status = 'approved', plan_file = ?, appendix_file = ?, approved_at = ? "
        "WHERE id = ?",
        (
            str(approved_plan),
            str(approved_appendix) if approved_appendix else None,
            now.isoformat(timespec="seconds"),
            current_draft["id"],
        ),
    )
    conn.commit()

    print(f"Plan approved: {title}")
    print(f"  Plan:     {approved_plan}")
    if approved_appendix:
        print(f"  Appendix: {approved_appendix}")


def cmd_start(cwd: str | None = None, now: datetime | None = None) -> None:
    """Start implementing the current approved plan."""
    if cwd is None:
        cwd = str(Path.cwd())
    if now is None:
        now = datetime.now()

    plans = plans_dir_for(cwd)
    conn = open_db(plans)
    current = get_current_plan(conn)

    if current is None:
        print("Error: No current plan found. Approve a plan first.", file=sys.stderr)
        sys.exit(1)

    if current["status"] == "in_progress":
        print(f"Plan already in progress: {current['title']}")
        print(f"  Plan: {current['plan_file']}")
        if current["appendix_file"]:
            print(f"  Appendix: {current['appendix_file']}")
        return

    conn.execute(
        "UPDATE plans SET status = 'in_progress', started_at = ? WHERE id = ?",
        (now.isoformat(timespec="seconds"), current["id"]),
    )
    conn.commit()

    print(f"Started plan: {current['title']}")
    print(f"  Plan: {current['plan_file']}")
    if current["appendix_file"]:
        print(f"  Appendix: {current['appendix_file']}")


def cmd_done(cwd: str | None = None, now: datetime | None = None) -> None:
    """Mark the current plan as done (if all checkboxes are ticked)."""
    if cwd is None:
        cwd = str(Path.cwd())
    if now is None:
        now = datetime.now()

    plans = plans_dir_for(cwd)
    conn = open_db(plans)
    current = get_current_plan(conn)

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

    conn.execute(
        "UPDATE plans SET status = 'done', completed_at = ? WHERE id = ?",
        (now.isoformat(timespec="seconds"), current["id"]),
    )
    conn.commit()

    print(f"Plan completed: {current['title']}")


def cmd_list(cwd: str | None = None) -> None:
    """List all pending plans with actionable instructions."""
    if cwd is None:
        cwd = str(Path.cwd())

    plans = plans_dir_for(cwd)
    conn = open_db_if_exists(plans)
    if conn is None:
        print("No pending plans.")
        return
    pending = list_pending_plans(conn)

    if not pending:
        print("No pending plans.")
        return

    # Group by status, preserving order
    by_status: dict[str, list[dict]] = {}
    for plan in pending:
        by_status.setdefault(plan["status"], []).append(plan)

    first = True
    for status, plans_in_status in by_status.items():
        if not first:
            print()
        first = False

        if status == "draft":
            print("Draft plans (finish writing, then approve):")
            for p in plans_in_status:
                print(f"  - {p['title']}")
                print(f"    Plan: {p['plan_file']}")
                if p["appendix_file"]:
                    print(f"    Appendix: {p['appendix_file']}")
            print("  Run `plan.py approve` when the user approves.")

        elif status == "approved":
            print("Approved plans (ready to start):")
            for p in plans_in_status:
                print(f"  - {p['title']}")
                print(f"    Plan: {p['plan_file']}")
            print("  Run `plan.py start` to begin implementation.")

        elif status == "in_progress":
            print("Plans in progress (resume working):")
            for p in plans_in_status:
                print(f"  - {p['title']}")
                print(f"    Plan: {p['plan_file']}")
            print("  Continue from where it left off. Check off items as you complete them:")
            print("    - `## [ ]` → `## [x]` for phase headings")
            print("    - `### [ ]` → `### [x]` for step headings")
            print("    - `- [ ]` → `- [x]` for bullet items")
            print("  Run `plan.py done` when all tasks are complete.")


def _export_scripts_to_path() -> None:
    """Append this script's directory to PATH via CLAUDE_ENV_FILE (if available)."""
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if not env_file:
        return
    scripts_dir = Path(__file__).resolve().parent
    with open(env_file, "a") as f:
        f.write(f'export PATH="$PATH:{scripts_dir}"\n')


def cmd_session_check(hook_input: dict) -> None:
    """Hook: check for active plan on session start."""
    _export_scripts_to_path()

    cwd = hook_input.get("cwd", "")
    if not cwd:
        return

    plans = plans_dir_for(cwd)
    conn = open_db_if_exists(plans)
    if conn is None:
        return
    pending = list_pending_plans(conn)
    if not pending:
        return

    # Record session interaction
    session_id = hook_input.get("session_id", "")
    if session_id:
        now = datetime.now()
        for plan in pending:
            record_session(conn, plan["id"], session_id, now)
        conn.commit()

    count = len(pending)
    noun = "plan" if count == 1 else "plans"
    message = (
        f"There are {count} pending {noun}. "
        "Ask the user if they are relevant.\n"
        "Check pending plans with: `plan.py list`"
    )

    output = {"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": message,
    }}
    print(json.dumps(output))


# ── CLI entry point ──────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="plan", description="Plan management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a new draft plan")
    create.add_argument("slug", help="Plan slug (e.g. add-auth)")
    create.add_argument("--prompt", help="Original user prompt")
    create.add_argument("--agent", help="Agent identity")
    create.add_argument("--force", action="store_true", help="Overwrite existing draft")

    approve = subparsers.add_parser("approve", help="Approve the current draft plan")
    approve.add_argument("--agent", help="Agent identity")
    approve.add_argument("--force", action="store_true", help="Overwrite existing active plan")

    subparsers.add_parser("start", help="Start implementing the current plan")
    subparsers.add_parser("done", help="Mark the current plan as done")
    subparsers.add_parser("list", help="List all pending plans")
    subparsers.add_parser("session-check", help="Hook: check for active plan on session start")

    return parser


def main(args: list[str] | None = None) -> None:
    parser = build_parser()
    parsed = parser.parse_args(args)

    if parsed.command == "create":
        cmd_create(
            parsed.slug,
            prompt=parsed.prompt,
            agent=parsed.agent,
            force=parsed.force,
        )

    elif parsed.command == "approve":
        cmd_approve(agent=parsed.agent, force=parsed.force)

    elif parsed.command == "start":
        cmd_start()

    elif parsed.command == "done":
        cmd_done()

    elif parsed.command == "list":
        cmd_list()

    elif parsed.command == "session-check":
        hook_input = json.loads(sys.stdin.read())
        cmd_session_check(hook_input)


if __name__ == "__main__":
    main()
