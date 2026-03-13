#!/usr/bin/env python3
"""Tests for the plan management CLI."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from plan import (
    APPENDIX_TEMPLATE,
    DB_FILENAME,
    PLAN_TEMPLATE,
    _export_scripts_to_path,
    append_log_entry,
    build_parser,
    cmd_approve,
    cmd_create,
    cmd_done,
    cmd_list,
    cmd_session_check,
    cmd_start,
    extract_slug_from_draft,
    find_draft,
    find_draft_appendix,
    find_latest_draft,
    find_unchecked_items,
    format_log_entry,
    get_current_draft,
    get_current_plan,
    get_identity,
    list_pending_plans,
    open_db,
    open_db_if_exists,
    plans_dir_for,
    record_session,
    slug_to_title,
    validate_slug,
)

FIXED_NOW = datetime(2026, 2, 24, 4, 48)
FIXED_NOW_STR = "2026-02-24_04-48"


# ── validate_slug ────────────────────────────────────────────────────────────


class TestValidateSlug:
    def test_valid_simple(self) -> None:
        validate_slug("add-auth")  # should not raise

    def test_valid_with_digits(self) -> None:
        validate_slug("phase-2-cleanup")

    def test_valid_single_word(self) -> None:
        validate_slug("auth")

    def test_invalid_uppercase(self) -> None:
        with pytest.raises(SystemExit):
            validate_slug("Add-Auth")

    def test_invalid_spaces(self) -> None:
        with pytest.raises(SystemExit):
            validate_slug("add auth")

    def test_invalid_underscores(self) -> None:
        with pytest.raises(SystemExit):
            validate_slug("add_auth")

    def test_invalid_special_chars(self) -> None:
        with pytest.raises(SystemExit):
            validate_slug("add-auth!")

    def test_invalid_empty(self) -> None:
        with pytest.raises(SystemExit):
            validate_slug("")

    def test_invalid_leading_hyphen(self) -> None:
        with pytest.raises(SystemExit):
            validate_slug("-add-auth")

    def test_invalid_trailing_hyphen(self) -> None:
        with pytest.raises(SystemExit):
            validate_slug("add-auth-")

    def test_invalid_consecutive_hyphens(self) -> None:
        with pytest.raises(SystemExit):
            validate_slug("add--auth")


# ── slug_to_title ────────────────────────────────────────────────────────────


class TestSlugToTitle:
    def test_simple(self) -> None:
        assert slug_to_title("add-authentication") == "Add Authentication"

    def test_single_word(self) -> None:
        assert slug_to_title("auth") == "Auth"

    def test_with_digits(self) -> None:
        assert slug_to_title("phase-2-cleanup") == "Phase 2 Cleanup"

    def test_multiple_words(self) -> None:
        assert slug_to_title("fix-login-bug-on-mobile") == "Fix Login Bug On Mobile"


# ── plans_dir_for ────────────────────────────────────────────────────────────


class TestPlansDirFor:
    def test_returns_correct_path(self) -> None:
        assert plans_dir_for("/home/user/project") == Path(
            "/home/user/project/.claude/plans"
        )

    def test_relative_path(self) -> None:
        assert plans_dir_for("myproject") == Path("myproject/.claude/plans")


# ── find_draft / find_draft_appendix ─────────────────────────────────────────


class TestFindDraft:
    def test_finds_matching_draft(self, tmp_path: Path) -> None:
        draft = tmp_path / "2026-02-24_04-48_add-auth.md"
        draft.write_text("# plan")
        assert find_draft(tmp_path, "add-auth") == draft

    def test_returns_most_recent(self, tmp_path: Path) -> None:
        old = tmp_path / "2026-02-20_10-00_add-auth.md"
        old.write_text("old")
        new = tmp_path / "2026-02-24_04-48_add-auth.md"
        new.write_text("new")
        assert find_draft(tmp_path, "add-auth") == new

    def test_returns_none_when_no_match(self, tmp_path: Path) -> None:
        (tmp_path / "2026-02-24_04-48_other-slug.md").write_text("x")
        assert find_draft(tmp_path, "add-auth") is None

    def test_returns_none_in_empty_dir(self, tmp_path: Path) -> None:
        assert find_draft(tmp_path, "add-auth") is None


class TestFindDraftAppendix:
    def test_finds_matching_appendix(self, tmp_path: Path) -> None:
        appendix = tmp_path / "2026-02-24_04-48_add-auth-appendix.md"
        appendix.write_text("# appendix")
        assert find_draft_appendix(tmp_path, "add-auth") == appendix

    def test_returns_none_when_no_match(self, tmp_path: Path) -> None:
        assert find_draft_appendix(tmp_path, "add-auth") is None


# ── extract_slug_from_draft / find_latest_draft ──────────────────────────────


class TestExtractSlugFromDraft:
    def test_standard_filename(self) -> None:
        assert extract_slug_from_draft(Path("2026-02-24_04-48_add-auth.md")) == "add-auth"

    def test_multi_word_slug(self) -> None:
        assert (
            extract_slug_from_draft(Path("2026-02-24_04-48_fix-login-bug.md"))
            == "fix-login-bug"
        )

    def test_no_datetime_prefix(self) -> None:
        assert extract_slug_from_draft(Path("something.md")) == "something"


class TestFindLatestDraft:
    def test_returns_most_recent(self, tmp_path: Path) -> None:
        old = tmp_path / "2026-02-20_10-00_old-plan.md"
        old.write_text("old")
        new = tmp_path / "2026-02-24_04-48_new-plan.md"
        new.write_text("new")
        assert find_latest_draft(tmp_path) == new

    def test_skips_appendices(self, tmp_path: Path) -> None:
        (tmp_path / "2026-02-24_04-48_my-plan-appendix.md").write_text("appendix")
        plan = tmp_path / "2026-02-24_04-48_my-plan.md"
        plan.write_text("plan")
        assert find_latest_draft(tmp_path) == plan

    def test_returns_none_in_empty_dir(self, tmp_path: Path) -> None:
        assert find_latest_draft(tmp_path) is None

    def test_returns_none_when_only_appendices(self, tmp_path: Path) -> None:
        (tmp_path / "2026-02-24_04-48_my-plan-appendix.md").write_text("appendix")
        assert find_latest_draft(tmp_path) is None


# ── open_db ──────────────────────────────────────────────────────────────────


class TestOpenDb:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        plans = tmp_path / ".claude" / "plans"
        open_db(plans)
        assert (plans / DB_FILENAME).exists()

    def test_creates_tables(self, tmp_path: Path) -> None:
        plans = tmp_path / ".claude" / "plans"
        conn = open_db(plans)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "plans" in tables
        assert "plan_sessions" in tables

    def test_idempotent(self, tmp_path: Path) -> None:
        plans = tmp_path / ".claude" / "plans"
        conn1 = open_db(plans)
        conn1.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'draft', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn1.commit()
        conn1.close()
        # Opening again should not lose data
        conn2 = open_db(plans)
        row = conn2.execute("SELECT slug FROM plans").fetchone()
        assert row["slug"] == "test"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        plans = tmp_path / "deep" / "nested" / ".claude" / "plans"
        open_db(plans)
        assert (plans / DB_FILENAME).exists()


# ── open_db_if_exists ─────────────────────────────────────────────────────────


class TestOpenDbIfExists:
    def test_returns_none_when_no_db(self, tmp_path: Path) -> None:
        plans = tmp_path / ".claude" / "plans"
        assert open_db_if_exists(plans) is None

    def test_returns_none_when_dir_missing(self, tmp_path: Path) -> None:
        plans = tmp_path / "nonexistent" / ".claude" / "plans"
        assert open_db_if_exists(plans) is None

    def test_returns_connection_when_db_exists(self, tmp_path: Path) -> None:
        plans = tmp_path / ".claude" / "plans"
        open_db(plans)  # create the DB
        conn = open_db_if_exists(plans)
        assert conn is not None
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "plans" in tables
        assert "plan_sessions" in tables


# ── get_current_draft / get_current_plan / list_pending_plans ────────────────


class TestDbQueries:
    def test_get_current_draft_none(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        assert get_current_draft(conn) is None

    def test_get_current_draft_returns_draft(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'draft', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        draft = get_current_draft(conn)
        assert draft is not None
        assert draft["slug"] == "test"
        assert draft["status"] == "draft"

    def test_get_current_draft_ignores_non_draft(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'approved', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        assert get_current_draft(conn) is None

    def test_get_current_plan_none(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        assert get_current_plan(conn) is None

    def test_get_current_plan_returns_approved(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'approved', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        plan = get_current_plan(conn)
        assert plan is not None
        assert plan["status"] == "approved"

    def test_get_current_plan_returns_in_progress(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'in_progress', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        plan = get_current_plan(conn)
        assert plan is not None
        assert plan["status"] == "in_progress"

    def test_get_current_plan_ignores_done(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'done', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        assert get_current_plan(conn) is None

    def test_get_current_plan_ignores_draft(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'draft', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        assert get_current_plan(conn) is None

    def test_list_pending_plans_empty(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        assert list_pending_plans(conn) == []

    def test_list_pending_plans_excludes_done(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'done', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        assert list_pending_plans(conn) == []

    def test_list_pending_plans_includes_all_non_done(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        for status in ("draft", "approved", "in_progress"):
            conn.execute(
                "INSERT INTO plans (slug, title, status, plan_file, created_at) "
                "VALUES (?, ?, ?, '/tmp/test.md', '2026-01-01T00:00:00')",
                (f"test-{status}", f"Test {status}", status),
            )
        conn.commit()
        pending = list_pending_plans(conn)
        assert len(pending) == 3
        assert [p["status"] for p in pending] == ["draft", "approved", "in_progress"]


# ── record_session ───────────────────────────────────────────────────────────


class TestRecordSession:
    def test_inserts_new_session(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'draft', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        record_session(conn, 1, "session-abc", FIXED_NOW)
        conn.commit()
        row = conn.execute("SELECT * FROM plan_sessions WHERE plan_id = 1").fetchone()
        assert row["session_id"] == "session-abc"
        assert row["first_seen_at"] == "2026-02-24T04:48:00"
        assert row["last_seen_at"] == "2026-02-24T04:48:00"

    def test_updates_last_seen(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'draft', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        record_session(conn, 1, "session-abc", FIXED_NOW)
        conn.commit()
        later = datetime(2026, 2, 25, 10, 0)
        record_session(conn, 1, "session-abc", later)
        conn.commit()
        row = conn.execute("SELECT * FROM plan_sessions WHERE plan_id = 1").fetchone()
        assert row["first_seen_at"] == "2026-02-24T04:48:00"
        assert row["last_seen_at"] == "2026-02-25T10:00:00"

    def test_multiple_sessions(self, tmp_path: Path) -> None:
        conn = open_db(tmp_path)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('test', 'Test', 'draft', '/tmp/test.md', '2026-01-01T00:00:00')"
        )
        conn.commit()
        record_session(conn, 1, "session-abc", FIXED_NOW)
        record_session(conn, 1, "session-def", FIXED_NOW)
        conn.commit()
        rows = conn.execute("SELECT * FROM plan_sessions WHERE plan_id = 1").fetchall()
        assert len(rows) == 2
        session_ids = {row["session_id"] for row in rows}
        assert session_ids == {"session-abc", "session-def"}


# ── find_unchecked_items ─────────────────────────────────────────────────────


class TestFindUncheckedItems:
    def test_all_checked(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("- [x] Done\n- [x] Also done\n")
        assert find_unchecked_items(f) == []

    def test_some_unchecked(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("- [x] Done\n- [ ] Not done\n- [ ] Also not\n")
        assert find_unchecked_items(f) == ["Not done", "Also not"]

    def test_none_checked(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("- [ ] First\n- [ ] Second\n")
        assert find_unchecked_items(f) == ["First", "Second"]

    def test_no_checkboxes(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("# Plan\n\nSome text.\n")
        assert find_unchecked_items(f) == []

    def test_indented_checkboxes(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("  - [ ] Indented\n    - [ ] More indented\n")
        assert find_unchecked_items(f) == ["Indented", "More indented"]

    def test_step_heading_unchecked(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("### [ ] 1. Add migration\n")
        assert find_unchecked_items(f) == ["1. Add migration"]

    def test_step_heading_checked(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("### [x] 1. Add migration\n")
        assert find_unchecked_items(f) == []

    def test_phase_heading_unchecked(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("## [ ] Phase 1 of 2: Database changes\n")
        assert find_unchecked_items(f) == ["Phase 1 of 2: Database changes"]

    def test_phase_heading_checked(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("## [x] Phase 1 of 2: Database changes\n")
        assert find_unchecked_items(f) == []

    def test_mixed_headings_and_bullets(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text(
            "## [ ] Phase 1 of 2\n"
            "### [x] 1. Done step\n"
            "### [ ] 2. Pending step\n"
            "- [x] Done bullet\n"
            "- [ ] Pending bullet\n"
        )
        assert find_unchecked_items(f) == [
            "Phase 1 of 2",
            "2. Pending step",
            "Pending bullet",
        ]

    def test_skips_fenced_code_blocks(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text(
            "### [x] 1. Done\n"
            "\n"
            "```markdown\n"
            "## [ ] Phase 1 of 2: Example\n"
            "### [ ] 1. Example step\n"
            "- [ ] Example bullet\n"
            "```\n"
            "\n"
            "- [ ] Real bullet\n"
        )
        assert find_unchecked_items(f) == ["Real bullet"]

    def test_skips_tilde_code_blocks(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text(
            "~~~\n"
            "- [ ] Inside code block\n"
            "~~~\n"
            "- [ ] Outside\n"
        )
        assert find_unchecked_items(f) == ["Outside"]

    def test_multi_phase_plan_with_per_phase_verification(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text(
            "# My Plan\n"
            "\n"
            "## Context\n"
            "\n"
            "Some context.\n"
            "\n"
            "## [x] Phase 1 of 2: Database changes\n"
            "\n"
            "### [x] 1. Add migration\n"
            "\n"
            "Details.\n"
            "\n"
            "### [x] 2. Update model and tests\n"
            "\n"
            "Details.\n"
            "\n"
            "### Files\n"
            "- `src/db/migrations/`\n"
            "\n"
            "### Verification\n"
            "- [x] `pytest tests/test_models.py` passes\n"
            "\n"
            "## [ ] Phase 2 of 2: API layer\n"
            "\n"
            "### [x] 3. Add endpoint\n"
            "\n"
            "Details.\n"
            "\n"
            "### [ ] 4. Add integration tests\n"
            "\n"
            "Details.\n"
            "\n"
            "### Files\n"
            "- `src/api/preferences.py`\n"
            "\n"
            "### Verification\n"
            "- [ ] `pytest tests/test_preferences_api.py` passes\n"
            "\n"
            "## Verification\n"
            "\n"
            "- [ ] Full `pytest` passes\n"
        )
        assert find_unchecked_items(f) == [
            "Phase 2 of 2: API layer",
            "4. Add integration tests",
            "`pytest tests/test_preferences_api.py` passes",
            "Full `pytest` passes",
        ]


# ── get_identity / format_log_entry / append_log_entry ───────────────────


class TestGetIdentity:
    def test_default_is_user_at_hostname(self) -> None:
        import getpass
        import socket

        expected = f"{getpass.getuser()}@{socket.gethostname()}"
        assert get_identity() == expected

    def test_agent_identity(self) -> None:
        assert get_identity(agent="claude") == "agent:claude"

    def test_agent_identity_custom_name(self) -> None:
        assert get_identity(agent="plan-reviewer") == "agent:plan-reviewer"


class TestFormatLogEntry:
    def test_simple_action(self) -> None:
        assert format_log_entry(FIXED_NOW, "alice@mac", "Created") == (
            "- 2026-02-24 04:48 — Created by alice@mac"
        )

    def test_action_with_prompt(self) -> None:
        assert format_log_entry(FIXED_NOW, "agent:claude", 'Created (prompt: "add auth")') == (
            '- 2026-02-24 04:48 — Created (prompt: "add auth") by agent:claude'
        )


class TestAppendLogEntry:
    def test_creates_log_section(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("# Plan\n\n- [ ] Step 1\n")
        append_log_entry(f, "- 2026-02-24 04:48 — Created by alice@mac")
        assert f.read_text() == (
            "# Plan\n\n- [ ] Step 1\n\n"
            "## Log\n\n"
            "- 2026-02-24 04:48 — Created by alice@mac\n"
        )

    def test_appends_to_existing_log(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text(
            "# Plan\n\n## Log\n\n"
            "- 2026-02-24 04:48 — Created by alice@mac\n"
        )
        append_log_entry(f, "- 2026-02-24 05:00 — Approved by bob@mac")
        assert f.read_text() == (
            "# Plan\n\n## Log\n\n"
            "- 2026-02-24 04:48 — Created by alice@mac\n"
            "- 2026-02-24 05:00 — Approved by bob@mac\n"
        )

    def test_strips_trailing_whitespace(self, tmp_path: Path) -> None:
        f = tmp_path / "plan.md"
        f.write_text("# Plan\n\n- [ ] Step 1\n\n\n")
        append_log_entry(f, "- 2026-02-24 04:48 — Created by alice@mac")
        assert f.read_text() == (
            "# Plan\n\n- [ ] Step 1\n\n"
            "## Log\n\n"
            "- 2026-02-24 04:48 — Created by alice@mac\n"
        )


class TestBuildParser:
    def test_create_slug_only(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["create", "add-auth"])
        assert args.command == "create"
        assert args.slug == "add-auth"
        assert args.prompt is None
        assert args.agent is None
        assert args.force is False

    def test_create_all_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["create", "add-auth", "--prompt=do stuff", "--agent=claude", "--force"])
        assert args.slug == "add-auth"
        assert args.prompt == "do stuff"
        assert args.agent == "claude"
        assert args.force is True

    def test_create_missing_slug_exits(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["create"])

    def test_approve_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["approve"])
        assert args.command == "approve"
        assert args.agent is None
        assert args.force is False

    def test_approve_with_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["approve", "--agent=reviewer", "--force"])
        assert args.agent == "reviewer"
        assert args.force is True

    def test_start(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["start"])
        assert args.command == "start"

    def test_done(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["done"])
        assert args.command == "done"

    def test_list(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_session_check(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["session-check"])
        assert args.command == "session-check"

    def test_no_command_exits(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_unknown_command_exits(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["bogus"])


# ── cmd_create ───────────────────────────────────────────────────────────────


class TestCmdCreate:
    def _plan_path(self, tmp_path: Path, slug: str = "add-auth") -> Path:
        return tmp_path / ".claude" / "plans" / "drafts" / f"{FIXED_NOW_STR}_{slug}.md"

    def _appendix_path(self, tmp_path: Path, slug: str = "add-auth") -> Path:
        return tmp_path / ".claude" / "plans" / "drafts" / f"{FIXED_NOW_STR}_{slug}-appendix.md"

    def _default_identity(self) -> str:
        import getpass
        import socket

        return f"{getpass.getuser()}@{socket.gethostname()}"

    def test_creates_plan_and_appendix(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        assert self._plan_path(tmp_path).exists()
        assert self._appendix_path(tmp_path).exists()

    def test_plan_content_with_log(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        expected = (
            PLAN_TEMPLATE.format(title="Add Auth").rstrip("\n")
            + "\n\n## Log\n\n"
            + f"- 2026-02-24 04:48 — Created by {self._default_identity()}\n"
        )
        assert self._plan_path(tmp_path).read_text() == expected

    def test_plan_content_with_prompt(self, tmp_path: Path) -> None:
        cmd_create("add-auth", prompt="add user authentication", cwd=str(tmp_path), now=FIXED_NOW)
        expected = (
            PLAN_TEMPLATE.format(title="Add Auth").rstrip("\n")
            + "\n\n## Log\n\n"
            + f'- 2026-02-24 04:48 — Created (prompt: "add user authentication") by {self._default_identity()}\n'
        )
        assert self._plan_path(tmp_path).read_text() == expected

    def test_plan_content_with_agent(self, tmp_path: Path) -> None:
        cmd_create("add-auth", agent="claude", cwd=str(tmp_path), now=FIXED_NOW)
        expected = (
            PLAN_TEMPLATE.format(title="Add Auth").rstrip("\n")
            + "\n\n## Log\n\n"
            + "- 2026-02-24 04:48 — Created by agent:claude\n"
        )
        assert self._plan_path(tmp_path).read_text() == expected

    def test_plan_content_with_prompt_and_agent(self, tmp_path: Path) -> None:
        cmd_create("add-auth", prompt="add auth", agent="claude", cwd=str(tmp_path), now=FIXED_NOW)
        expected = (
            PLAN_TEMPLATE.format(title="Add Auth").rstrip("\n")
            + "\n\n## Log\n\n"
            + '- 2026-02-24 04:48 — Created (prompt: "add auth") by agent:claude\n'
        )
        assert self._plan_path(tmp_path).read_text() == expected

    def test_appendix_content(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        assert self._appendix_path(tmp_path).read_text() == APPENDIX_TEMPLATE.format(title="Add Auth")

    def test_creates_directories(self, tmp_path: Path) -> None:
        cmd_create("test-slug", cwd=str(tmp_path), now=FIXED_NOW)
        assert (tmp_path / ".claude" / "plans" / "drafts").is_dir()

    def test_prints_paths(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        out = capsys.readouterr().out
        assert "Draft plan created:" in out
        assert "add-auth.md" in out
        assert "add-auth-appendix.md" in out

    def test_invalid_slug_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            cmd_create("INVALID", cwd=str(tmp_path), now=FIXED_NOW)

    def test_inserts_into_database(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        draft = get_current_draft(conn)
        assert draft is not None
        assert draft["slug"] == "add-auth"
        assert draft["title"] == "Add Auth"
        assert draft["status"] == "draft"
        assert "add-auth.md" in draft["plan_file"]
        assert "add-auth-appendix.md" in draft["appendix_file"]

    def test_fails_if_draft_exists(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        with pytest.raises(SystemExit):
            cmd_create("other-plan", cwd=str(tmp_path), now=FIXED_NOW)
        err = capsys.readouterr().err
        assert "A draft already exists: Add Auth" in err
        assert "--force" in err

    def test_force_overwrites_existing_draft(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        second_now = datetime(2026, 2, 25, 10, 0)
        cmd_create("other-plan", force=True, cwd=str(tmp_path), now=second_now)
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        draft = get_current_draft(conn)
        assert draft["slug"] == "other-plan"
        assert draft["title"] == "Other Plan"

    def test_force_archives_old_draft(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        second_now = datetime(2026, 2, 25, 10, 0)
        cmd_create("other-plan", force=True, cwd=str(tmp_path), now=second_now)
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        # Old draft is archived as done
        rows = conn.execute("SELECT * FROM plans WHERE slug = 'add-auth'").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "done"

    def test_creates_db_file(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        plans = plans_dir_for(str(tmp_path))
        assert (plans / DB_FILENAME).exists()

    def test_no_json_files_created(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        plans = plans_dir_for(str(tmp_path))
        assert not (plans / "current-draft.json").exists()
        assert not (plans / "current-plan.json").exists()


# ── cmd_approve ──────────────────────────────────────────────────────────────


class TestCmdApprove:
    def _default_identity(self) -> str:
        import getpass
        import socket

        return f"{getpass.getuser()}@{socket.gethostname()}"

    def _create_draft(self, tmp_path: Path, slug: str = "add-auth") -> None:
        cmd_create(slug, cwd=str(tmp_path), now=FIXED_NOW)

    def test_moves_to_approved(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        approve_now = datetime(2026, 2, 24, 5, 0)
        cmd_approve(cwd=str(tmp_path), now=approve_now)
        approved = tmp_path / ".claude" / "plans" / "approved"
        drafts = tmp_path / ".claude" / "plans" / "drafts"
        # Approved files exist
        assert (approved / "2026-02-24_05-00_add-auth.md").exists()
        assert (approved / "2026-02-24_05-00_add-auth-appendix.md").exists()
        # Draft files are gone
        assert not (drafts / f"{FIXED_NOW_STR}_add-auth.md").exists()
        assert not (drafts / f"{FIXED_NOW_STR}_add-auth-appendix.md").exists()

    def test_updates_database_status(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        plan = get_current_plan(conn)
        assert plan is not None
        assert plan["slug"] == "add-auth"
        assert plan["status"] == "approved"
        assert plan["approved_at"] == "2026-02-24T04:48:00"
        # No more draft
        assert get_current_draft(conn) is None

    def test_updates_plan_file_path(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        plan = get_current_plan(conn)
        assert "approved" in plan["plan_file"]
        assert "approved" in plan["appendix_file"]

    def test_no_current_draft_exits(self, tmp_path: Path) -> None:
        # Create the plans directory and database but no draft
        plans = plans_dir_for(str(tmp_path))
        open_db(plans)
        with pytest.raises(SystemExit):
            cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)

    def test_appends_approve_log_entry(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        approve_now = datetime(2026, 2, 24, 5, 0)
        cmd_approve(cwd=str(tmp_path), now=approve_now)
        approved = (
            tmp_path / ".claude" / "plans" / "approved" / "2026-02-24_05-00_add-auth.md"
        )
        content = approved.read_text()
        identity = self._default_identity()
        # Should have both create and approve log entries
        assert f"- 2026-02-24 04:48 — Created by {identity}" in content
        assert f"- 2026-02-24 05:00 — Approved by {identity}" in content

    def test_appends_approve_log_with_agent(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        cmd_approve(agent="plan-reviewer", cwd=str(tmp_path), now=FIXED_NOW)
        approved = (
            tmp_path / ".claude" / "plans" / "approved" / f"{FIXED_NOW_STR}_add-auth.md"
        )
        content = approved.read_text()
        assert "- 2026-02-24 04:48 — Approved by agent:plan-reviewer" in content

    def test_preserves_plan_content(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        # Modify the draft to have custom content
        draft = (
            tmp_path / ".claude" / "plans" / "drafts" / f"{FIXED_NOW_STR}_add-auth.md"
        )
        custom = "# Custom Plan\n\n- [ ] Step 1\n"
        draft.write_text(custom)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        approved = (
            tmp_path / ".claude" / "plans" / "approved" / f"{FIXED_NOW_STR}_add-auth.md"
        )
        content = approved.read_text()
        # The custom content is preserved, plus an approve log entry is appended
        assert content.startswith(custom.rstrip("\n"))
        assert "Approved by" in content

    def test_prints_approval_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._create_draft(tmp_path)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        out = capsys.readouterr().out
        assert "Plan approved: Add Auth" in out

    def test_reads_from_current_draft(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path, "my-feature")
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        plan = get_current_plan(conn)
        assert plan["slug"] == "my-feature"
        assert plan["status"] == "approved"

    def test_fails_if_plan_already_active(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._create_draft(tmp_path)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        # Create a second draft and try to approve it
        cmd_create("other-plan", force=True, cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        with pytest.raises(SystemExit):
            cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        err = capsys.readouterr().err
        assert "A plan is already active: Add Auth" in err
        assert "status: approved" in err
        assert "--force" in err

    def test_fails_if_plan_in_progress(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._create_draft(tmp_path)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        cmd_create("other-plan", force=True, cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        with pytest.raises(SystemExit):
            cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        err = capsys.readouterr().err
        assert "A plan is already active: Add Auth" in err
        assert "status: in_progress" in err

    def test_force_overwrites_active_plan(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_create("other-plan", force=True, cwd=str(tmp_path), now=FIXED_NOW)
        approve_now = datetime(2026, 2, 25, 10, 0)
        cmd_approve(force=True, cwd=str(tmp_path), now=approve_now)
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        plan = get_current_plan(conn)
        assert plan["slug"] == "other-plan"
        assert plan["status"] == "approved"

    def test_no_json_files_created(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        plans = plans_dir_for(str(tmp_path))
        assert not (plans / "current-draft.json").exists()
        assert not (plans / "current-plan.json").exists()


# ── cmd_start ────────────────────────────────────────────────────────────────


class TestCmdStart:
    def _setup_approved(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)

    def test_updates_status(self, tmp_path: Path) -> None:
        self._setup_approved(tmp_path)
        start_now = datetime(2026, 2, 24, 5, 0)
        cmd_start(cwd=str(tmp_path), now=start_now)
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        plan = get_current_plan(conn)
        assert plan["status"] == "in_progress"
        assert plan["started_at"] == "2026-02-24T05:00:00"

    def test_no_plan_exits(self, tmp_path: Path) -> None:
        plans = plans_dir_for(str(tmp_path))
        open_db(plans)
        with pytest.raises(SystemExit):
            cmd_start(cwd=str(tmp_path))

    def test_already_in_progress_is_noop(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._setup_approved(tmp_path)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()  # clear
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)
        out = capsys.readouterr().out
        assert "already in progress" in out

    def test_prints_plan_path(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._setup_approved(tmp_path)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)
        out = capsys.readouterr().out
        assert "Started plan: Add Auth" in out
        assert "add-auth.md" in out


# ── cmd_done ─────────────────────────────────────────────────────────────────


class TestCmdDone:
    def _setup_in_progress(self, tmp_path: Path, plan_content: str = "") -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        if plan_content:
            draft = (
                tmp_path
                / ".claude"
                / "plans"
                / "drafts"
                / f"{FIXED_NOW_STR}_add-auth.md"
            )
            draft.write_text(plan_content)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)

    def test_all_checked_completes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._setup_in_progress(
            tmp_path, "# Plan\n\n- [x] Done\n- [x] Also done\n"
        )
        cmd_done(cwd=str(tmp_path))
        out = capsys.readouterr().out
        assert "Plan completed: Add Auth" in out

    def test_updates_database_to_done(self, tmp_path: Path) -> None:
        self._setup_in_progress(tmp_path, "# Plan\n\n- [x] Done\n")
        done_now = datetime(2026, 2, 25, 10, 0)
        cmd_done(cwd=str(tmp_path), now=done_now)
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        # No active plan
        assert get_current_plan(conn) is None
        # But plan exists as done in database
        row = conn.execute("SELECT * FROM plans WHERE slug = 'add-auth' AND status = 'done'").fetchone()
        assert row is not None
        assert row["completed_at"] == "2026-02-25T10:00:00"

    def test_unchecked_items_exits(self, tmp_path: Path) -> None:
        self._setup_in_progress(
            tmp_path, "# Plan\n\n- [x] Done\n- [ ] Not done\n"
        )
        with pytest.raises(SystemExit):
            cmd_done(cwd=str(tmp_path))

    def test_unchecked_lists_items(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._setup_in_progress(
            tmp_path, "# Plan\n\n- [ ] Task A\n- [ ] Task B\n"
        )
        with pytest.raises(SystemExit):
            cmd_done(cwd=str(tmp_path))
        err = capsys.readouterr().err
        assert "2 unchecked item(s)" in err
        assert "Task A" in err
        assert "Task B" in err

    def test_no_plan_exits(self, tmp_path: Path) -> None:
        plans = plans_dir_for(str(tmp_path))
        open_db(plans)
        with pytest.raises(SystemExit):
            cmd_done(cwd=str(tmp_path))

    def test_missing_plan_file_exits(self, tmp_path: Path) -> None:
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        conn.execute(
            "INSERT INTO plans (slug, title, status, plan_file, created_at) "
            "VALUES ('gone', 'Gone', 'in_progress', ?, '2026-01-01T00:00:00')",
            (str(tmp_path / "nonexistent.md"),),
        )
        conn.commit()
        with pytest.raises(SystemExit):
            cmd_done(cwd=str(tmp_path))

    def test_no_json_files_after_done(self, tmp_path: Path) -> None:
        self._setup_in_progress(tmp_path, "# Plan\n\n- [x] Done\n")
        cmd_done(cwd=str(tmp_path))
        plans = plans_dir_for(str(tmp_path))
        assert not (plans / "current-plan.json").exists()
        assert not (plans / "current-draft.json").exists()


# ── cmd_list ─────────────────────────────────────────────────────────────────


class TestCmdList:

    def test_no_db_shows_no_plans(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_list(cwd=str(tmp_path))
        out = capsys.readouterr().out
        assert out == "No pending plans.\n"
        # Should NOT create the database
        plans = plans_dir_for(str(tmp_path))
        assert not (plans / DB_FILENAME).exists()

    def test_no_plans_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        # Create the database but no plans
        plans = plans_dir_for(str(tmp_path))
        open_db(plans)
        cmd_list(cwd=str(tmp_path))
        out = capsys.readouterr().out
        assert out == "No pending plans.\n"

    def test_draft_only(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()  # clear create output
        cmd_list(cwd=str(tmp_path))
        out = capsys.readouterr().out
        assert "Draft plans (finish writing, then approve):" in out
        assert "Add Auth" in out
        assert "add-auth.md" in out
        assert "add-auth-appendix.md" in out
        assert "plan.py approve" in out

    def test_approved_only(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        cmd_list(cwd=str(tmp_path))
        out = capsys.readouterr().out
        assert "Approved plans (ready to start):" in out
        assert "Add Auth" in out
        assert "plan.py start" in out

    def test_in_progress_only(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        cmd_list(cwd=str(tmp_path))
        out = capsys.readouterr().out
        assert "Plans in progress (resume working):" in out
        assert "Add Auth" in out
        assert "## [ ]" in out
        assert "### [ ]" in out
        assert "plan.py done" in out

    def test_multiple_statuses(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        # Create a draft
        cmd_create("draft-plan", cwd=str(tmp_path), now=FIXED_NOW)
        # Create and start another plan (force to override existing draft)
        second_now = datetime(2026, 2, 25, 10, 0)
        cmd_create("active-plan", force=True, cwd=str(tmp_path), now=second_now)
        cmd_approve(cwd=str(tmp_path), now=second_now)
        cmd_start(cwd=str(tmp_path), now=second_now)
        capsys.readouterr()
        cmd_list(cwd=str(tmp_path))
        out = capsys.readouterr().out
        # The first draft was archived (force), so only in_progress shows
        assert "Plans in progress (resume working):" in out
        assert "Active Plan" in out

    def test_done_not_shown(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        # Write all-checked plan
        draft = (
            tmp_path / ".claude" / "plans" / "drafts" / f"{FIXED_NOW_STR}_add-auth.md"
        )
        draft.write_text("# Plan\n\n- [x] Done\n")
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_done(cwd=str(tmp_path))
        capsys.readouterr()
        cmd_list(cwd=str(tmp_path))
        out = capsys.readouterr().out
        assert out == "No pending plans.\n"


# ── cmd_session_check ────────────────────────────────────────────────────────


class TestCmdSessionCheck:
    def _setup_approved(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)

    def _setup_in_progress(self, tmp_path: Path) -> None:
        self._setup_approved(tmp_path)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)

    def test_no_plan_outputs_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_session_check({"cwd": str(tmp_path)})
        assert capsys.readouterr().out == ""
        # Should NOT create the database
        plans = plans_dir_for(str(tmp_path))
        assert not (plans / DB_FILENAME).exists()

    def test_no_cwd_outputs_nothing(self, capsys: pytest.CaptureFixture) -> None:
        cmd_session_check({})
        assert capsys.readouterr().out == ""

    def test_empty_cwd_outputs_nothing(self, capsys: pytest.CaptureFixture) -> None:
        cmd_session_check({"cwd": ""})
        assert capsys.readouterr().out == ""

    def test_draft_plan_shows_pending(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path)})
        out = capsys.readouterr().out
        result = json.loads(out)
        expected = (
            "There are 1 pending plan. "
            "Ask the user if they are relevant.\n"
            "Check pending plans with: `plan.py list`"
        )
        assert result == {"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": expected,
        }}

    def test_approved_plan_shows_pending(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._setup_approved(tmp_path)
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path)})
        out = capsys.readouterr().out
        result = json.loads(out)
        context = result["hookSpecificOutput"]["additionalContext"]
        assert "1 pending plan" in context
        assert "list`" in context

    def test_in_progress_plan_shows_pending(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._setup_in_progress(tmp_path)
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path)})
        out = capsys.readouterr().out
        result = json.loads(out)
        context = result["hookSpecificOutput"]["additionalContext"]
        assert "1 pending plan" in context

    def test_done_plan_no_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        draft = (
            tmp_path / ".claude" / "plans" / "drafts" / f"{FIXED_NOW_STR}_add-auth.md"
        )
        draft.write_text("# Plan\n\n- [x] Done\n")
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_done(cwd=str(tmp_path))
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path)})
        assert capsys.readouterr().out == ""

    def test_multiple_plans_shows_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        # Create a draft, approve it, then create another draft
        cmd_create("first-plan", cwd=str(tmp_path), now=FIXED_NOW)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)
        second_now = datetime(2026, 2, 25, 10, 0)
        cmd_create("second-plan", cwd=str(tmp_path), now=second_now)
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path)})
        out = capsys.readouterr().out
        result = json.loads(out)
        context = result["hookSpecificOutput"]["additionalContext"]
        assert "2 pending plans" in context


# ── _export_scripts_to_path ────────────────────────────────────────────────────


class TestExportScriptsToPath:
    def test_appends_path_when_env_file_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "env"
        env_file.touch()
        monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
        _export_scripts_to_path()
        content = env_file.read_text()
        scripts_dir = str(Path(__file__).resolve().parent.parent
            / "plugins" / "plan-mode" / "skills" / "plan+" / "scripts")
        assert content == f'export PATH="$PATH:{scripts_dir}"\n'

    def test_no_op_when_env_file_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
        _export_scripts_to_path()  # should not raise

    def test_appends_to_existing_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "env"
        env_file.write_text('export FOO=bar\n')
        monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
        _export_scripts_to_path()
        content = env_file.read_text()
        assert content.startswith('export FOO=bar\n')
        assert 'export PATH="$PATH:' in content

    def test_session_check_calls_export(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "env"
        env_file.touch()
        monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
        cmd_session_check({"cwd": str(tmp_path)})
        content = env_file.read_text()
        assert 'export PATH="$PATH:' in content


# ── Session tracking in session-check ────────────────────────────────────────


class TestSessionTracking:
    def test_session_check_records_session(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path), "session_id": "ses-abc123"})
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        rows = conn.execute("SELECT * FROM plan_sessions").fetchall()
        assert len(rows) == 1
        assert rows[0]["session_id"] == "ses-abc123"

    def test_session_check_updates_last_seen(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path), "session_id": "ses-abc123"})
        capsys.readouterr()
        # Second check with same session
        cmd_session_check({"cwd": str(tmp_path), "session_id": "ses-abc123"})
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        rows = conn.execute("SELECT * FROM plan_sessions").fetchall()
        assert len(rows) == 1  # Still one row, not two
        # last_seen_at should be updated (we can't check exact time since datetime.now() is used)

    def test_multiple_sessions_recorded(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path), "session_id": "ses-abc"})
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path), "session_id": "ses-def"})
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        rows = conn.execute("SELECT * FROM plan_sessions").fetchall()
        assert len(rows) == 2
        session_ids = {row["session_id"] for row in rows}
        assert session_ids == {"ses-abc", "ses-def"}

    def test_no_session_id_no_record(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        capsys.readouterr()
        cmd_session_check({"cwd": str(tmp_path)})
        plans = plans_dir_for(str(tmp_path))
        conn = open_db(plans)
        rows = conn.execute("SELECT * FROM plan_sessions").fetchall()
        assert len(rows) == 0


# ── Full lifecycle ───────────────────────────────────────────────────────────


class TestLifecycle:
    def test_create_approve_start_done(self, tmp_path: Path) -> None:
        """Full lifecycle: create → approve → start → done."""
        # Create
        cmd_create("my-feature", cwd=str(tmp_path), now=FIXED_NOW)
        plans = plans_dir_for(str(tmp_path))
        drafts = plans / "drafts"
        plan_file = drafts / f"{FIXED_NOW_STR}_my-feature.md"
        assert plan_file.exists()

        # Write a complete plan (all checked)
        plan_file.write_text("# My Feature\n\n- [x] Implement\n- [x] Test\n")

        # Approve
        approve_now = datetime(2026, 2, 24, 5, 0)
        cmd_approve(cwd=str(tmp_path), now=approve_now)
        conn = open_db(plans)
        plan = get_current_plan(conn)
        assert plan["status"] == "approved"

        # Draft files are gone (moved)
        assert not plan_file.exists()

        # Session check shows pending
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = buf = io.StringIO()
        cmd_session_check({"cwd": str(tmp_path)})
        sys.stdout = old_stdout
        assert "pending plan" in buf.getvalue()

        # Start
        start_now = datetime(2026, 2, 24, 5, 30)
        cmd_start(cwd=str(tmp_path), now=start_now)
        conn = open_db(plans)
        plan = get_current_plan(conn)
        assert plan["status"] == "in_progress"

        # Done
        cmd_done(cwd=str(tmp_path))
        conn = open_db(plans)
        assert get_current_plan(conn) is None

    def test_approved_files_preserved_after_done(self, tmp_path: Path) -> None:
        """Approved files remain in approved/ after plan is completed."""
        cmd_create("cleanup", cwd=str(tmp_path), now=FIXED_NOW)
        # Write all-checked plan
        draft = (
            tmp_path
            / ".claude"
            / "plans"
            / "drafts"
            / f"{FIXED_NOW_STR}_cleanup.md"
        )
        draft.write_text("# Cleanup\n\n- [x] Done\n")
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)
        cmd_done(cwd=str(tmp_path))

        approved = tmp_path / ".claude" / "plans" / "approved"
        assert (approved / f"{FIXED_NOW_STR}_cleanup.md").exists()
