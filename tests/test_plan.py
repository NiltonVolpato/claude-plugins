#!/usr/bin/env python3
"""Tests for the plan management CLI."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from plan import (
    APPENDIX_TEMPLATE,
    PLAN_TEMPLATE,
    append_log_entry,
    cmd_approve,
    cmd_create,
    cmd_done,
    cmd_session_check,
    cmd_start,
    extract_slug_from_draft,
    find_draft,
    find_draft_appendix,
    find_latest_draft,
    find_unchecked_items,
    format_log_entry,
    get_identity,
    read_current_draft,
    remove_current_draft,
    parse_flags,
    plans_dir_for,
    read_current_plan,
    slug_to_title,
    validate_slug,
    write_current_plan,
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


# ── current-draft.json ───────────────────────────────────────────────────────


class TestCurrentDraft:
    def test_create_writes_current_draft(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        plans = tmp_path / ".claude" / "plans"
        draft = read_current_draft(plans)
        assert draft is not None
        assert draft["slug"] == "add-auth"
        assert draft["title"] == "Add Auth"
        assert "add-auth.md" in draft["plan_file"]
        assert "add-auth-appendix.md" in draft["appendix_file"]

    def test_approve_removes_current_draft(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        plans = tmp_path / ".claude" / "plans"
        assert read_current_draft(plans) is None

    def test_approve_no_slug_reads_current_draft(self, tmp_path: Path) -> None:
        cmd_create("my-feature", cwd=str(tmp_path), now=FIXED_NOW)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        plans = tmp_path / ".claude" / "plans"
        current = read_current_plan(plans)
        assert current["slug"] == "my-feature"

    def test_remove_current_draft_noop_when_missing(self, tmp_path: Path) -> None:
        remove_current_draft(tmp_path)  # should not raise


# ── read_current_plan / write_current_plan ───────────────────────────────────


class TestCurrentPlan:
    def test_read_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert read_current_plan(tmp_path) is None

    def test_roundtrip(self, tmp_path: Path) -> None:
        data = {"slug": "test", "status": "approved"}
        write_current_plan(tmp_path, data)
        assert read_current_plan(tmp_path) == data

    def test_write_creates_file(self, tmp_path: Path) -> None:
        write_current_plan(tmp_path, {"slug": "test"})
        assert (tmp_path / "current-plan.json").exists()

    def test_write_overwrites(self, tmp_path: Path) -> None:
        write_current_plan(tmp_path, {"slug": "old"})
        write_current_plan(tmp_path, {"slug": "new"})
        assert read_current_plan(tmp_path)["slug"] == "new"


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


class TestParseFlags:
    def test_no_flags(self) -> None:
        assert parse_flags(["slug"]) == (["slug"], {})

    def test_key_value_flag(self) -> None:
        assert parse_flags(["slug", "--agent=claude"]) == (["slug"], {"agent": "claude"})

    def test_multiple_flags(self) -> None:
        positional, flags = parse_flags(["slug", "--agent=claude", "--prompt=add auth"])
        assert positional == ["slug"]
        assert flags == {"agent": "claude", "prompt": "add auth"}

    def test_flag_without_value(self) -> None:
        assert parse_flags(["--verbose"]) == ([], {"verbose": None})

    def test_no_args(self) -> None:
        assert parse_flags([]) == ([], {})


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

    def test_creates_current_plan_json(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        plans = tmp_path / ".claude" / "plans"
        current = json.loads((plans / "current-plan.json").read_text())
        assert current == {
            "slug": "add-auth",
            "title": "Add Auth",
            "plan_file": str(
                plans / "approved" / f"{FIXED_NOW_STR}_add-auth.md"
            ),
            "appendix_file": str(
                plans / "approved" / f"{FIXED_NOW_STR}_add-auth-appendix.md"
            ),
            "approved_at": "2026-02-24T04:48:00",
            "status": "approved",
        }

    def test_no_current_draft_exits(self, tmp_path: Path) -> None:
        (tmp_path / ".claude" / "plans").mkdir(parents=True)
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
        plans = tmp_path / ".claude" / "plans"
        current = read_current_plan(plans)
        assert current["slug"] == "my-feature"
        assert current["status"] == "approved"

    def test_removes_current_draft_json(self, tmp_path: Path) -> None:
        self._create_draft(tmp_path)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)
        plans = tmp_path / ".claude" / "plans"
        assert read_current_draft(plans) is None


# ── cmd_start ────────────────────────────────────────────────────────────────


class TestCmdStart:
    def _setup_approved(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)

    def test_updates_status(self, tmp_path: Path) -> None:
        self._setup_approved(tmp_path)
        start_now = datetime(2026, 2, 24, 5, 0)
        cmd_start(cwd=str(tmp_path), now=start_now)
        plans = tmp_path / ".claude" / "plans"
        current = read_current_plan(plans)
        assert current["status"] == "in_progress"
        assert current["started_at"] == "2026-02-24T05:00:00"

    def test_no_plan_exits(self, tmp_path: Path) -> None:
        (tmp_path / ".claude" / "plans").mkdir(parents=True)
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

    def test_removes_current_plan_json(self, tmp_path: Path) -> None:
        self._setup_in_progress(tmp_path, "# Plan\n\n- [x] Done\n")
        cmd_done(cwd=str(tmp_path))
        plans = tmp_path / ".claude" / "plans"
        assert not (plans / "current-plan.json").exists()

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
        (tmp_path / ".claude" / "plans").mkdir(parents=True)
        with pytest.raises(SystemExit):
            cmd_done(cwd=str(tmp_path))

    def test_missing_plan_file_exits(self, tmp_path: Path) -> None:
        plans = tmp_path / ".claude" / "plans"
        plans.mkdir(parents=True)
        write_current_plan(
            plans,
            {
                "slug": "gone",
                "title": "Gone",
                "plan_file": str(tmp_path / "nonexistent.md"),
                "status": "in_progress",
            },
        )
        with pytest.raises(SystemExit):
            cmd_done(cwd=str(tmp_path))


# ── cmd_session_check ────────────────────────────────────────────────────────


class TestCmdSessionCheck:
    def _setup_approved(self, tmp_path: Path) -> None:
        cmd_create("add-auth", cwd=str(tmp_path), now=FIXED_NOW)
        cmd_approve(cwd=str(tmp_path), now=FIXED_NOW)

    def _setup_in_progress(self, tmp_path: Path) -> None:
        self._setup_approved(tmp_path)
        cmd_start(cwd=str(tmp_path), now=FIXED_NOW)

    def _script_path(self) -> str:
        return str(
            Path(__file__).resolve().parent.parent
            / "plugins" / "plan-mode" / "skills" / "plan+" / "scripts" / "plan.py"
        )

    def _approved_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".claude" / "plans" / "approved"

    def test_no_plan_outputs_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        cmd_session_check({"cwd": str(tmp_path)})
        assert capsys.readouterr().out == ""

    def test_no_cwd_outputs_nothing(self, capsys: pytest.CaptureFixture) -> None:
        cmd_session_check({})
        assert capsys.readouterr().out == ""

    def test_empty_cwd_outputs_nothing(self, capsys: pytest.CaptureFixture) -> None:
        cmd_session_check({"cwd": ""})
        assert capsys.readouterr().out == ""

    def test_approved_plan_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._setup_approved(tmp_path)
        capsys.readouterr()  # clear setup output
        cmd_session_check({"cwd": str(tmp_path)})
        out = capsys.readouterr().out
        result = json.loads(out)
        approved = self._approved_dir(tmp_path)
        plan_file = approved / f"{FIXED_NOW_STR}_add-auth.md"
        appendix_file = approved / f"{FIXED_NOW_STR}_add-auth-appendix.md"
        expected = "\n".join([
            "A plan has been approved but not started: **Add Auth**.",
            "",
            f"- Plan: `{plan_file}`",
            f"- Appendix: `{appendix_file}`",
            "",
            "Ask the user if they want to start implementing.",
            f"Run `python3 {self._script_path()} start` when ready.",
        ])
        assert result == {"hookSpecificOutput": {"additionalContext": expected}}

    def test_in_progress_plan_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        self._setup_in_progress(tmp_path)
        capsys.readouterr()  # clear setup output
        cmd_session_check({"cwd": str(tmp_path)})
        out = capsys.readouterr().out
        result = json.loads(out)
        approved = self._approved_dir(tmp_path)
        plan_file = approved / f"{FIXED_NOW_STR}_add-auth.md"
        appendix_file = approved / f"{FIXED_NOW_STR}_add-auth-appendix.md"
        expected = "\n".join([
            "A plan is in progress: **Add Auth**.",
            "",
            f"- Plan: `{plan_file}` (check checkboxes for progress)",
            f"- Appendix: `{appendix_file}`",
            "",
            "Continue from where it left off.",
            f"Run `python3 {self._script_path()} done` when all tasks are complete.",
        ])
        assert result == {"hookSpecificOutput": {"additionalContext": expected}}


# ── Full lifecycle ───────────────────────────────────────────────────────────


class TestLifecycle:
    def test_create_approve_start_done(self, tmp_path: Path) -> None:
        """Full lifecycle: create → approve → start → done."""
        # Create
        cmd_create("my-feature", cwd=str(tmp_path), now=FIXED_NOW)
        plans = tmp_path / ".claude" / "plans"
        drafts = plans / "drafts"
        plan_file = drafts / f"{FIXED_NOW_STR}_my-feature.md"
        assert plan_file.exists()

        # Write a complete plan (all checked)
        plan_file.write_text("# My Feature\n\n- [x] Implement\n- [x] Test\n")

        # Approve
        approve_now = datetime(2026, 2, 24, 5, 0)
        cmd_approve(cwd=str(tmp_path), now=approve_now)
        current = read_current_plan(plans)
        assert current["status"] == "approved"

        # Draft files are gone (moved)
        assert not plan_file.exists()

        # Session check shows approved
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = buf = io.StringIO()
        cmd_session_check({"cwd": str(tmp_path)})
        sys.stdout = old_stdout
        assert "approved but not started" in buf.getvalue()

        # Start
        start_now = datetime(2026, 2, 24, 5, 30)
        cmd_start(cwd=str(tmp_path), now=start_now)
        current = read_current_plan(plans)
        assert current["status"] == "in_progress"

        # Done
        cmd_done(cwd=str(tmp_path))
        assert not (plans / "current-plan.json").exists()

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
