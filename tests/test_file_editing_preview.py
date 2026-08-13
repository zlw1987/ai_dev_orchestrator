"""Phase 5F1 tests: the dry-run file-edit preview builder.

Everything here is a **literal JSON string**, a literal dict, or a
``ProjectConfig`` constructed in memory. Every diff below was typed into this
file by hand: none was generated, none is applied, no artifact is read from
disk, no environment variable is read, no socket is opened, no command is run,
no file is edited, no branch is created, nothing is committed or pushed, and no
target project workspace is read, listed, stat'd, globbed, walked, resolved, or
canonicalized. No path below names a real project, and the source lines inside
the diffs describe an invented billing helper.

The builder under test is pure, so the IO tests below assert that directly:
``builtins.open``, the ``os`` filesystem and environment entry points,
``socket``, and ``subprocess`` are all replaced with detonators for the duration
of a successful build and of failing ones.
"""

from __future__ import annotations

import builtins
import copy
import json
import os
import socket
import subprocess
from datetime import datetime, timezone

import pytest

from ai_dev_orchestrator.diff_proposal import (
    DIFF_PROPOSAL_MODE,
    DIFF_PROPOSAL_SCHEMA_VERSION,
)
from ai_dev_orchestrator.file_editing import (
    APPROVED_DIFF_PROPOSAL_MODE,
    APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
    FILE_EDIT_PREVIEW_CANDIDATE_SOURCE,
    FILE_EDIT_PREVIEW_MODE,
    FILE_EDIT_PREVIEW_SCHEMA_VERSION,
    REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    FileEditPreviewChange,
    FileEditPreviewError,
    FileEditPreviewReport,
    build_file_edit_preview,
    parse_approved_diff_proposal_artifact,
)
from ai_dev_orchestrator.file_editing import preview as preview_module
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.models import ProjectConfig, RepoConfig, WorkspacePolicyConfig

PROJECT_ID = "acme_widgets"
REPO = "acme/widgets"
ISSUE_NUMBER = 42
TITLE = "Add currency formatting helper"
APPROVER = "operator@example.invalid"

# Path-shaped strings. Nothing below is ever opened, stat'd, listed, globbed,
# walked, or resolved: they are compared and copied as strings only.
ALLOWED_PATH = "src/billing/format.py"
ALLOWED_TEST_PATH = "tests/test_format.py"
PROTECTED_PATH = "src/billing/protected_rates.py"
UNLISTED_PATH = "docs/billing_notes.md"
POLICY_FORBIDDEN_PATH = "secrets/billing.env"

# Out of scope for the *plan*, which is a different list from the project's
# forbidden path rules and is enforced by the Phase 5E2/5F0 models.
PLAN_FORBIDDEN_PATH = "external_auth/client.py"

# A distinctive source line, so a test can prove diff text never reaches output.
SOURCE_MARKER = "SENTINEL_SOURCE_LINE_NEVER_PREVIEWED"

# The workspace path exists only as a **string**. It is never created, read,
# listed, stat'd, or resolved, and it must never appear in a report.
WORKSPACE_PATH = "C:/never_touched_preview_workspace"


def _project(
    *,
    project_id: str = PROJECT_ID,
    github_repo: str = REPO,
    max_changed_files: int = 20,
    allowed_paths: list[str] | None = None,
    protected_paths: list[str] | None = None,
    forbidden_paths: list[str] | None = None,
) -> ProjectConfig:
    """A project config built in memory. No YAML is loaded and no file is read."""
    return ProjectConfig(
        project_id=project_id,
        display_name="Acme Widgets",
        repo=RepoConfig(
            workspace_path=WORKSPACE_PATH,
            github_repo=github_repo,
            default_base_branch="main",
            branch_prefix="ai/acme",
        ),
        workspace_policy=WorkspacePolicyConfig(
            deny_outside_workspace=True,
            allow_symlinks=False,
            max_changed_files=max_changed_files,
        ),
        allowed_paths=["src/**", "tests/**"] if allowed_paths is None else allowed_paths,
        protected_paths=["src/billing/protected_*.py"]
        if protected_paths is None
        else protected_paths,
        forbidden_paths=[".git/**", "secrets/**"]
        if forbidden_paths is None
        else forbidden_paths,
    )


VALID_PLAN: dict = {
    "issue_number": ISSUE_NUMBER,
    "repo": REPO,
    "title": TITLE,
    "summary": "Format invoice totals through one shared helper.",
    "scope_summary": "Only the billing formatting helper and its tests.",
    "non_goals": ["No changes to the payment gateway client."],
    "proposed_steps": ["Describe a single shared helper for a human to write."],
    # Deliberately wider than the project's path rules allow: the plan's list and
    # the project's path policy are independent, and the preview must apply both.
    "files_likely_to_change": [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
        PROTECTED_PATH,
        UNLISTED_PATH,
        POLICY_FORBIDDEN_PATH,
    ],
    "files_forbidden_or_out_of_scope": [PLAN_FORBIDDEN_PATH],
    "required_verification": ["pytest -q"],
    "risks": ["Rounding differences against previously issued invoices."],
    "open_questions": ["Which locale should totals use?"],
    "automation_level": "L1",
    "requires_human_approval": True,
}

VALID_PLAN_PROVENANCE: dict = {
    "engine": "real-model",
    "operation": "generate-model-plan",
    "real_call": True,
    "model": "fake-planner-model",
    "endpoint_host": "fake-litellm.invalid:8000",
    "generated_at": "2026-01-02T03:04:05+00:00",
    "project_id": PROJECT_ID,
    "repo": REPO,
    "issue_number": ISSUE_NUMBER,
    "title": TITLE,
}

VALID_PLAN_APPROVAL: dict = {
    "approved_by": APPROVER,
    "approved_at": "2026-01-02T04:00:00+00:00",
    "approval_text": REQUIRED_APPROVAL_TEXT,
    "source": "manual",
}

VALID_APPROVED_PLAN: dict = {
    "approval": VALID_PLAN_APPROVAL,
    "plan_provenance": VALID_PLAN_PROVENANCE,
    "plan": VALID_PLAN,
    "project_id": PROJECT_ID,
    "repo": REPO,
    "issue_number": ISSUE_NUMBER,
}

VALID_DIFF_PROVENANCE: dict = {
    "engine": "deterministic",
    "operation": "diff-proposal",
    "real_call": False,
    "model": None,
    "generated_at": "2026-01-03T05:06:07+00:00",
    "project_id": PROJECT_ID,
    "repo": REPO,
    "issue_number": ISSUE_NUMBER,
    "title": TITLE,
}

# The Phase 5F0 file-edit approval. Written by a human, never by this code.
VALID_EDIT_APPROVAL: dict = {
    "approved_by": APPROVER,
    "approved_at": "2026-01-04T06:00:00+00:00",
    "approval_text": REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    "source": "manual",
}

NEXT_AUTHORIZATION = (
    "A file-editing phase must be explicitly authorized before anything writes "
    "these diffs; this artifact records approval only and applies nothing."
)


# -- Hand-written fixtures -----------------------------------------------------

# Two headers, one hunk, one added line, one removed line, two context lines.
MODIFY_DIFF_LINES = 7
MODIFY_DIFF_HUNKS = 1
MODIFY_DIFF_ADDED = 1
MODIFY_DIFF_REMOVED = 1
MODIFY_DIFF_CONTEXT = 2

# Two headers, one hunk, two added lines, no removed lines, no context.
CREATE_DIFF_LINES = 5
CREATE_DIFF_HUNKS = 1
CREATE_DIFF_ADDED = 2
CREATE_DIFF_REMOVED = 0
CREATE_DIFF_CONTEXT = 0


def _modify_diff(path: str = ALLOWED_PATH) -> str:
    """A minimal, hand-typed single-file modification diff for ``path``."""
    return (
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,4 +1,4 @@\n"
        f" def format_total(amount):  # {SOURCE_MARKER}\n"
        "-    return str(amount)\n"
        '+    return f"{amount:.2f}"\n'
        " \n"
    )


def _create_diff(path: str = ALLOWED_TEST_PATH) -> str:
    """A minimal, hand-typed single-file addition diff for ``path``."""
    return (
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1,2 @@\n"
        "+def test_format_total():\n"
        '+    assert format_total(1) == "1.00"\n'
    )


# Phase 5F2C image identities. These fixtures exercise artifact *shape*, so
# the digests only have to be well-formed lowercase 64-hex values; the writer
# is what compares them against real bytes.
PRE_IMAGE_SHA256 = "3f79bb7b435b05321651daefd374cdc681dc06faa65e374e38337b88ca046dea"
POST_IMAGE_SHA256 = "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"


def _change(path: str = ALLOWED_PATH, change_type: str = "modify") -> dict:
    diff = _create_diff(path) if change_type == "create" else _modify_diff(path)
    return {
        "path": path,
        "change_type": change_type,
        "unified_diff": diff,
        # Phase 5F2C: diff-proposal.v2 binds both ends of the transformation.
        # A create has no original, so its pre-image digest is null.
        "pre_image_sha256": None if change_type == "create" else PRE_IMAGE_SHA256,
        "post_image_sha256": POST_IMAGE_SHA256,
        "rationale": "The shared helper belongs here, next to the totals code.",
        "risks": ["Existing call sites may round differently today."],
        "requires_human_review": True,
    }


def _diff_proposal(
    changes: list[dict] | None = None, omitted_paths: list[str] | None = None
) -> dict:
    """A fresh, fully valid Phase 5E2 proposal dict."""
    return {
        "schema_version": DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": DIFF_PROPOSAL_MODE,
        "provenance": copy.deepcopy(VALID_DIFF_PROVENANCE),
        "approved_plan": copy.deepcopy(VALID_APPROVED_PLAN),
        "patch_proposal": None,
        "changes": copy.deepcopy(changes)
        if changes is not None
        else [_change(ALLOWED_PATH)],
        "omitted_paths": [] if omitted_paths is None else list(omitted_paths),
        "assumptions": ["The helper has no existing callers outside billing."],
        "risks": ["A human may need to reconcile historical invoices."],
        "open_questions": [],
        "source_contents_read": True,
        "diffs_generated": True,
        "files_edited": False,
        "commands_run": False,
        "applies_cleanly_checked": False,
        "requires_human_review": True,
        "next_authorization_required": "Phase 5F0 approval is required separately.",
    }


def _artifact_dict(
    changes: list[dict] | None = None,
    diff_proposal: dict | None = None,
    **overrides,
) -> dict:
    """A fresh, fully valid Phase 5F0 wrapper. Callers mutate their own copy."""
    payload = {
        "schema_version": APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": APPROVED_DIFF_PROPOSAL_MODE,
        "approval": copy.deepcopy(VALID_EDIT_APPROVAL),
        "diff_proposal": copy.deepcopy(diff_proposal)
        if diff_proposal is not None
        else _diff_proposal(changes),
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
        "title": TITLE,
        "next_authorization_required": NEXT_AUTHORIZATION,
    }
    payload.update(overrides)
    return payload


def _artifact(changes: list[dict] | None = None, **kwargs):
    """Parse a literal artifact dict through the Phase 5F0 strict parser."""
    return parse_approved_diff_proposal_artifact(
        json.dumps(_artifact_dict(changes, **kwargs))
    )


def _build(changes: list[dict] | None = None, project=None, **kwargs):
    return build_file_edit_preview(
        approved_diff=_artifact(changes, **kwargs),
        project=_project() if project is None else project,
    )


# -- 1. The happy path ---------------------------------------------------------


def test_modify_change_produces_a_preview_report():
    report = _build([_change(ALLOWED_PATH, "modify")])

    assert isinstance(report, FileEditPreviewReport)
    assert report.schema_version == FILE_EDIT_PREVIEW_SCHEMA_VERSION
    assert report.mode == FILE_EDIT_PREVIEW_MODE
    assert report.mode == "dry-run-preview-only"
    assert report.preview.candidate_source == FILE_EDIT_PREVIEW_CANDIDATE_SOURCE
    assert report.preview.paths_count == 1

    change = report.preview.changes[0]
    assert isinstance(change, FileEditPreviewChange)
    assert change.path == ALLOWED_PATH
    assert change.change_type == "modify"
    assert change.policy_result == "allowed"
    assert change.protected_path is False
    assert change.would_attempt_write_in_future_phase is True
    assert change.notes


def test_create_change_produces_a_preview_report():
    report = _build([_change(ALLOWED_TEST_PATH, "create")])

    assert report.preview.paths_count == 1
    change = report.preview.changes[0]
    assert change.path == ALLOWED_TEST_PATH
    assert change.change_type == "create"
    assert change.policy_result == "allowed"
    assert change.diff_stats.added_lines == CREATE_DIFF_ADDED


def test_empty_changes_produce_a_valid_preview_with_no_paths():
    report = _build([])

    assert report.preview.paths_count == 0
    assert report.preview.changes == []
    assert report.approved_diff.change_count == 0
    # An empty change set is a well-formed statement that a future phase would
    # attempt no write, not a defect and not a licence.
    assert report.files_edited is False
    assert report.requires_future_authorization is True


def test_multiple_changes_preserve_input_order():
    report = _build(
        [
            _change(ALLOWED_TEST_PATH, "create"),
            _change(ALLOWED_PATH, "modify"),
        ]
    )

    assert [change.path for change in report.preview.changes] == [
        ALLOWED_TEST_PATH,
        ALLOWED_PATH,
    ]
    assert report.preview.paths_count == 2
    assert report.approved_diff.change_count == 2


def test_project_and_approval_identity_are_reported():
    report = _build()

    assert report.project.project_id == PROJECT_ID
    assert report.project.repo == REPO
    assert report.project.workspace_policy.deny_outside_workspace is True
    assert report.project.workspace_policy.allow_symlinks is False
    assert report.project.workspace_policy.max_changed_files == 20

    assert report.approved_diff.approved_by == APPROVER
    assert report.approved_diff.source == "manual"
    assert report.approved_diff.issue_number == ISSUE_NUMBER
    assert report.approved_diff.title == TITLE
    assert report.approved_diff.approved_at == datetime(
        2026, 1, 4, 6, 0, tzinfo=timezone.utc
    )


def test_omitted_paths_are_carried_through_in_order():
    report = _build(
        changes=[_change(ALLOWED_PATH)],
        diff_proposal=_diff_proposal(
            changes=[_change(ALLOWED_PATH)],
            omitted_paths=[ALLOWED_TEST_PATH, UNLISTED_PATH],
        ),
    )

    assert report.preview.omitted_paths == [ALLOWED_TEST_PATH, UNLISTED_PATH]
    # Omitted paths are named, never previewed as write candidates.
    assert [change.path for change in report.preview.changes] == [ALLOWED_PATH]


def test_the_builder_is_deterministic():
    first = _build()
    second = _build()

    assert first.model_dump_json() == second.model_dump_json()


# -- 2. Approval comes from Phase 5F0 and is never inferred --------------------


def test_the_wrapped_plan_approval_alone_is_not_a_file_edit_approval():
    from ai_dev_orchestrator.file_editing import FileEditingApprovalValidationError

    payload = _artifact_dict()
    # The wrapped L1 plan approval is untouched and valid; only the file-edit
    # sentence is replaced by it. That is an approval of a different thing.
    payload["approval"]["approval_text"] = REQUIRED_APPROVAL_TEXT

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(json.dumps(payload))


def test_requires_human_review_is_not_an_approval():
    from ai_dev_orchestrator.file_editing import FileEditingApprovalValidationError

    payload = _artifact_dict()
    del payload["approval"]

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(json.dumps(payload))


def test_the_builder_never_stamps_or_widens_an_approval():
    artifact = _artifact()
    before = artifact.model_dump_json()

    report = build_file_edit_preview(approved_diff=artifact, project=_project())

    # The artifact travels through unchanged, and the report carries no
    # approval text and nothing that could be mistaken for a new approval.
    assert artifact.model_dump_json() == before
    dumped = report.model_dump_json()
    assert "approval_text" not in dumped
    assert REQUIRED_DIFF_EDIT_APPROVAL_TEXT not in dumped
    assert REQUIRED_APPROVAL_TEXT not in dumped


# -- 3. Exact identity matching ------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"project_id": "some_other_project"},
        {"github_repo": "other/widgets"},
        # Case differences are a mismatch: string equality only.
        {"project_id": PROJECT_ID.upper()},
        {"github_repo": REPO.upper()},
    ],
)
def test_identity_mismatch_with_the_project_config_is_refused(overrides):
    with pytest.raises(FileEditPreviewError) as excinfo:
        _build(project=_project(**overrides))

    assert "does not match this project config" in str(excinfo.value)


def test_identity_mismatch_names_every_field_that_disagrees():
    with pytest.raises(FileEditPreviewError) as excinfo:
        _build(project=_project(project_id="elsewhere", github_repo="other/repo"))

    message = str(excinfo.value)
    for field in (
        "project_id",
        "repo",
        "diff_proposal.provenance.project_id",
        "diff_proposal.provenance.repo",
        "diff_proposal.approved_plan.project_id",
        "diff_proposal.approved_plan.repo",
    ):
        assert field in message


def test_a_mutated_provenance_identity_is_caught():
    artifact = _artifact()
    artifact.diff_proposal.provenance.project_id = "smuggled_project"

    with pytest.raises(FileEditPreviewError) as excinfo:
        build_file_edit_preview(approved_diff=artifact, project=_project())

    assert "diff_proposal.provenance.project_id" in str(excinfo.value)


def test_a_mutated_nested_plan_identity_is_caught():
    artifact = _artifact()
    artifact.diff_proposal.approved_plan.repo = "smuggled/repo"

    with pytest.raises(FileEditPreviewError) as excinfo:
        build_file_edit_preview(approved_diff=artifact, project=_project())

    assert "diff_proposal.approved_plan.repo" in str(excinfo.value)


# -- 4. Change-set discipline --------------------------------------------------


def test_change_count_above_max_changed_files_is_refused():
    with pytest.raises(FileEditPreviewError) as excinfo:
        _build(
            [_change(ALLOWED_PATH), _change(ALLOWED_TEST_PATH, "create")],
            project=_project(max_changed_files=1),
        )

    assert "max_changed_files" in str(excinfo.value)


def test_change_count_exactly_at_the_cap_succeeds():
    report = _build(
        [_change(ALLOWED_PATH), _change(ALLOWED_TEST_PATH, "create")],
        project=_project(max_changed_files=2),
    )

    assert report.preview.paths_count == 2


def test_zero_changes_succeed_under_a_zero_cap():
    report = _build([], project=_project(max_changed_files=0))

    assert report.preview.paths_count == 0


def test_duplicate_paths_are_rejected_even_on_a_mutated_object():
    artifact = _artifact([_change(ALLOWED_PATH)])
    # Pydantic does not re-validate an instance it is handed, so this is the
    # route by which a duplicate reaches the builder at all.
    artifact.diff_proposal.changes.append(
        copy.deepcopy(artifact.diff_proposal.changes[0])
    )

    with pytest.raises(FileEditPreviewError) as excinfo:
        build_file_edit_preview(approved_diff=artifact, project=_project())

    assert "more than one change" in str(excinfo.value)


def test_duplicate_paths_are_rejected_by_the_parser_too():
    from ai_dev_orchestrator.file_editing import FileEditingApprovalValidationError

    with pytest.raises(FileEditingApprovalValidationError):
        _artifact([_change(ALLOWED_PATH), _change(ALLOWED_PATH)])


# -- 5. The lexical write policy -----------------------------------------------


def test_a_forbidden_path_is_refused():
    with pytest.raises(FileEditPreviewError) as excinfo:
        _build([_change(POLICY_FORBIDDEN_PATH)])

    message = str(excinfo.value)
    assert POLICY_FORBIDDEN_PATH in message
    assert "forbidden" in message


def test_an_unlisted_path_is_refused():
    with pytest.raises(FileEditPreviewError) as excinfo:
        _build([_change(UNLISTED_PATH)])

    message = str(excinfo.value)
    assert UNLISTED_PATH in message
    assert "unlisted" in message


def test_a_protected_path_is_refused_in_this_phase():
    with pytest.raises(FileEditPreviewError) as excinfo:
        _build([_change(PROTECTED_PATH)])

    message = str(excinfo.value)
    assert PROTECTED_PATH in message
    assert "PROTECTED" in message
    # There is no flag to permit one, and the report never says "denied".
    assert "no flag to permit" in message


def test_one_refused_path_fails_the_whole_preview():
    with pytest.raises(FileEditPreviewError):
        _build([_change(ALLOWED_PATH), _change(PROTECTED_PATH)])


def test_an_allowed_path_succeeds():
    report = _build([_change(ALLOWED_PATH)])

    assert report.preview.changes[0].policy_result == "allowed"
    assert report.preview.changes[0].protected_path is False


def test_the_path_policy_write_check_is_the_one_that_runs(monkeypatch):
    """The preview must use ``check_write``, never ``check_read``."""
    calls: list[str] = []
    real_check_write = preview_module.PathPolicy.check_write
    real_check_read = preview_module.PathPolicy.check_read

    def tracking_write(self, raw_path, **kwargs):
        calls.append(("write", raw_path, kwargs))
        return real_check_write(self, raw_path, **kwargs)

    def tracking_read(self, raw_path):
        calls.append(("read", raw_path, {}))
        return real_check_read(self, raw_path)

    monkeypatch.setattr(preview_module.PathPolicy, "check_write", tracking_write)
    monkeypatch.setattr(preview_module.PathPolicy, "check_read", tracking_read)

    _build([_change(ALLOWED_PATH), _change(ALLOWED_TEST_PATH, "create")])

    assert [call[0] for call in calls] == ["write", "write"]
    assert [call[1] for call in calls] == [ALLOWED_PATH, ALLOWED_TEST_PATH]
    # allow_protected is never passed, so it keeps its fail-closed default.
    assert all(call[2] == {} for call in calls)


def test_the_policy_is_built_from_the_project_config(monkeypatch):
    seen: list[str] = []
    real_from_config = preview_module.PathPolicy.from_project_config.__func__

    def tracking(cls, config):
        seen.append(config.project_id)
        return real_from_config(cls, config)

    monkeypatch.setattr(
        preview_module.PathPolicy,
        "from_project_config",
        classmethod(tracking),
    )

    _build()

    assert seen == [PROJECT_ID]


# -- 6. Diff statistics --------------------------------------------------------


def test_modify_diff_stats_are_computed_correctly():
    report = _build([_change(ALLOWED_PATH, "modify")])

    stats = report.preview.changes[0].diff_stats
    diff = _modify_diff(ALLOWED_PATH)
    assert stats.diff_bytes_utf8 == len(diff.encode("utf-8"))
    assert stats.diff_lines == MODIFY_DIFF_LINES
    assert stats.hunk_count == MODIFY_DIFF_HUNKS
    assert stats.added_lines == MODIFY_DIFF_ADDED
    assert stats.removed_lines == MODIFY_DIFF_REMOVED
    assert stats.context_lines == MODIFY_DIFF_CONTEXT


def test_create_diff_stats_are_computed_correctly():
    report = _build([_change(ALLOWED_TEST_PATH, "create")])

    stats = report.preview.changes[0].diff_stats
    diff = _create_diff(ALLOWED_TEST_PATH)
    assert stats.diff_bytes_utf8 == len(diff.encode("utf-8"))
    assert stats.diff_lines == CREATE_DIFF_LINES
    assert stats.hunk_count == CREATE_DIFF_HUNKS
    assert stats.added_lines == CREATE_DIFF_ADDED
    assert stats.removed_lines == CREATE_DIFF_REMOVED
    assert stats.context_lines == CREATE_DIFF_CONTEXT


def test_file_headers_are_excluded_from_added_and_removed_counts():
    modify = _build([_change(ALLOWED_PATH, "modify")]).preview.changes[0].diff_stats
    create = (
        _build([_change(ALLOWED_TEST_PATH, "create")]).preview.changes[0].diff_stats
    )

    # Both diffs carry a '--- ' and a '+++ ' header. Counting them would push
    # these to 2/2 and 3/1 respectively.
    assert (modify.added_lines, modify.removed_lines) == (1, 1)
    assert (create.added_lines, create.removed_lines) == (2, 0)

    # And headers are context either, so every line is accounted for exactly
    # once: two headers per single-file diff.
    for stats, expected_lines in (
        (modify, MODIFY_DIFF_LINES),
        (create, CREATE_DIFF_LINES),
    ):
        counted = (
            stats.hunk_count
            + stats.added_lines
            + stats.removed_lines
            + stats.context_lines
        )
        assert counted == expected_lines - 2


def test_multiple_hunks_are_counted():
    diff = (
        f"--- a/{ALLOWED_PATH}\n"
        f"+++ b/{ALLOWED_PATH}\n"
        "@@ -1,3 +1,3 @@\n"
        " def one():\n"
        "-    return 1\n"
        "+    return 11\n"
        "@@ -10,3 +10,3 @@\n"
        " def two():\n"
        "-    return 2\n"
        "+    return 22\n"
    )
    change = _change(ALLOWED_PATH)
    change["unified_diff"] = diff

    stats = _build([change]).preview.changes[0].diff_stats

    assert stats.hunk_count == 2
    assert stats.added_lines == 2
    assert stats.removed_lines == 2
    assert stats.context_lines == 2
    assert stats.diff_lines == 10


def test_diff_bytes_count_utf8_not_characters():
    diff = (
        f"--- a/{ALLOWED_PATH}\n"
        f"+++ b/{ALLOWED_PATH}\n"
        "@@ -1,2 +1,2 @@\n"
        " def label():\n"
        '-    return "EUR"\n'
        '+    return "\u20ac"\n'
    )
    change = _change(ALLOWED_PATH)
    change["unified_diff"] = diff

    stats = _build([change]).preview.changes[0].diff_stats

    assert stats.diff_bytes_utf8 == len(diff.encode("utf-8"))
    assert stats.diff_bytes_utf8 > len(diff)


def test_line_endings_are_not_normalized_before_counting():
    """``splitlines`` is the only thing applied; nothing rewrites the diff.

    A CRLF diff cannot reach the builder through a valid artifact — the Phase
    5E2 header check splits on ``"\\n"`` and rejects the trailing ``"\\r"`` — so
    the statistics helper is exercised directly. The point being made is about
    the helper: it counts bytes of the string it was handed, and does not
    rewrite, re-encode, or repair it.
    """
    diff = (
        f"--- a/{ALLOWED_PATH}\r\n"
        f"+++ b/{ALLOWED_PATH}\r\n"
        "@@ -1,2 +1,2 @@\r\n"
        " def one():\r\n"
        "-    return 1\r\n"
        "+    return 11\r\n"
    )

    stats = preview_module._diff_stats(diff)

    assert stats["diff_bytes_utf8"] == len(diff.encode("utf-8"))
    assert stats["diff_lines"] == 6
    assert stats["hunk_count"] == 1
    assert stats["added_lines"] == 1
    assert stats["removed_lines"] == 1
    assert stats["context_lines"] == 1


# -- 7. What the report does and does not carry --------------------------------


def _dumped(report) -> str:
    return report.model_dump_json()


def test_the_report_carries_no_unified_diff_and_no_source_content():
    report = _build([_change(ALLOWED_PATH), _change(ALLOWED_TEST_PATH, "create")])

    text = _dumped(report)
    assert SOURCE_MARKER not in text
    assert "unified_diff" not in text
    assert "return str(amount)" not in text
    assert "def test_format_total" not in text
    assert "@@" not in text


def test_the_report_carries_no_workspace_path_or_absolute_path():
    report = _build()

    text = _dumped(report)
    assert WORKSPACE_PATH not in text
    assert "workspace_path" not in text
    assert "never_touched_preview_workspace" not in text
    assert ":\\" not in text
    assert "C:/" not in text


def test_the_report_carries_no_command_apply_or_git_field():
    report = _build()

    dumped = report.model_dump()
    for absent in (
        "command",
        "commands",
        "command_output",
        "apply",
        "auto_apply",
        "apply_result",
        "branch",
        "commit",
        "push",
        "pr_url",
        "prompt",
        "completion",
        "api_key",
        "base_url",
        "raw_artifact_text",
        "source_contents",
        "before_content",
        "after_content",
    ):
        assert absent not in dumped


def test_the_top_level_flags_state_what_did_not_happen():
    report = _build()

    assert report.files_edited is False
    assert report.commands_run is False
    assert report.applies_cleanly_checked is False
    assert report.workspace_touched is False
    assert report.requires_future_authorization is True
    assert "5F2" in report.next_authorization_required


def test_checks_performed_are_accurate():
    performed = _build().checks_performed

    assert performed.approved_diff_approval_validated is True
    assert performed.diff_proposal_validated is True
    assert performed.project_identity_matched is True
    assert performed.lexical_write_policy_checked is True
    assert performed.max_changed_files_checked is True


def test_checks_not_performed_are_accurate():
    not_performed = _build().checks_not_performed

    for field, value in not_performed.model_dump().items():
        assert value is False, f"{field} must be reported as not performed"

    assert not_performed.workspace_touched is False
    assert not_performed.canonicalization_checked is False
    assert not_performed.current_file_contents_read is False
    assert not_performed.current_file_existence_checked is False
    assert not_performed.diff_applied is False
    assert not_performed.applies_cleanly_checked is False
    assert not_performed.commands_run is False
    assert not_performed.verification_run is False
    assert not_performed.branch_created is False
    assert not_performed.commit_created is False
    assert not_performed.pushed is False
    assert not_performed.pr_opened is False
    assert not_performed.model_called is False


def test_every_report_model_forbids_extra_fields():
    payload = json.loads(_build().model_dump_json())
    payload["applied"] = True

    with pytest.raises(Exception):
        FileEditPreviewReport.model_validate(payload)

    nested = json.loads(_build().model_dump_json())
    nested["preview"]["changes"][0]["unified_diff"] = "smuggled"
    with pytest.raises(Exception):
        FileEditPreviewReport.model_validate(nested)


def test_the_report_round_trips_through_its_own_model():
    report = _build([_change(ALLOWED_PATH), _change(ALLOWED_TEST_PATH, "create")])

    again = FileEditPreviewReport.model_validate(json.loads(report.model_dump_json()))

    assert again.model_dump_json() == report.model_dump_json()


# -- 8. The builder touches nothing --------------------------------------------


def _detonate_filesystem(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("build_file_edit_preview performed IO")

    monkeypatch.setattr(builtins, "open", boom)
    for name in (
        "stat",
        "lstat",
        "listdir",
        "scandir",
        "walk",
        "mkdir",
        "remove",
        "rename",
        "getenv",
    ):
        monkeypatch.setattr(os, name, boom)
    for name in ("realpath", "abspath", "exists", "isfile", "isdir", "islink"):
        monkeypatch.setattr(os.path, name, boom)
    monkeypatch.setattr(os.environ, "get", boom)
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(os, "system", boom)


def test_a_successful_build_performs_no_io(monkeypatch):
    artifact = _artifact([_change(ALLOWED_PATH), _change(ALLOWED_TEST_PATH, "create")])
    project = _project()

    _detonate_filesystem(monkeypatch)
    report = build_file_edit_preview(approved_diff=artifact, project=project)

    assert report.preview.paths_count == 2


@pytest.mark.parametrize(
    "changes, project_kwargs",
    [
        ([_change(PROTECTED_PATH)], {}),
        ([_change(UNLISTED_PATH)], {}),
        ([_change(POLICY_FORBIDDEN_PATH)], {}),
        ([_change(ALLOWED_PATH)], {"project_id": "elsewhere"}),
        (
            [_change(ALLOWED_PATH), _change(ALLOWED_TEST_PATH, "create")],
            {"max_changed_files": 1},
        ),
    ],
)
def test_every_failure_path_performs_no_io(monkeypatch, changes, project_kwargs):
    artifact = _artifact(changes)
    project = _project(**project_kwargs)

    _detonate_filesystem(monkeypatch)
    with pytest.raises(FileEditPreviewError):
        build_file_edit_preview(approved_diff=artifact, project=project)


def test_no_workspace_path_is_ever_passed_to_a_filesystem_call(monkeypatch):
    """A positive control: nothing joins a path to the configured root."""
    touched: list[str] = []
    real_join = os.path.join

    def tracking_join(*args, **kwargs):
        touched.append(str(args[0]) if args else "")
        return real_join(*args, **kwargs)

    monkeypatch.setattr(os.path, "join", tracking_join)

    _build()

    assert not [item for item in touched if WORKSPACE_PATH in item]


def test_the_builder_writes_no_file(tmp_path):
    before = sorted(item.name for item in tmp_path.iterdir())

    _build()

    assert sorted(item.name for item in tmp_path.iterdir()) == before


# -- 9. The implementation module cannot reach a model, a socket, or GitHub ----


def test_preview_module_globals_are_inert():
    module_globals = vars(preview_module)
    for name in (
        "httpx",
        "requests",
        "LLMClient",
        "LLMClientConfig",
        "load_llm_client_config_from_env",
        "GitHubClient",
        "typer",
        "Path",
        "os",
        "socket",
        "subprocess",
        "yaml",
        "git",
        "apply_patch",
        "difflib",
    ):
        assert name not in module_globals, f"{name} must not be importable here"


def test_preview_module_imports_no_transport_cli_or_differ():
    with open(preview_module.__file__, encoding="utf-8") as handle:
        text = handle.read()

    for forbidden in (
        "import httpx",
        "import requests",
        "import os",
        "import socket",
        "import subprocess",
        "import difflib",
        "from pathlib",
        "from ai_dev_orchestrator.cli",
        "from ai_dev_orchestrator.llm",
        "from ai_dev_orchestrator.github",
        "apply_patch",
        "git apply",
        "AIDO_LITELLM",
        "GITHUB_TOKEN",
    ):
        assert forbidden not in text, f"{forbidden!r} must not appear"

    # The one workspace import is the Phase 1 *lexical* path policy, which reads
    # nothing. The Phase 5D0 canonical guard is deliberately not imported: it
    # resolves real paths, which would mean touching the workspace.
    assert "from ai_dev_orchestrator.workspace.path_policy import" in text
    assert "workspace.canonical" not in text
    assert "canonical" not in vars(preview_module)


def test_the_path_policy_module_itself_is_lexical():
    from ai_dev_orchestrator.workspace import path_policy

    module_globals = vars(path_policy)
    for name in ("os", "Path", "socket", "subprocess", "httpx"):
        assert name not in module_globals


def test_the_package_exposes_no_editor_applier_or_git_helper():
    from ai_dev_orchestrator import file_editing

    for absent in (
        "apply_approved_diff_proposal",
        "apply_diff",
        "apply_patch",
        "edit_files",
        "write_files",
        "check_applies_cleanly",
        "run_required_verification",
        "create_branch",
        "commit_changes",
        "push_branch",
        "open_pull_request",
        "DiffApplier",
        "FileEditor",
        "L2Implementer",
        "write_file_edit_preview",
        "load_approved_diff_proposal_artifact",
    ):
        assert not hasattr(file_editing, absent)


def test_the_preview_module_defines_no_apply_edit_or_git_error():
    names = [name for name in vars(preview_module) if name.endswith("Error")]

    assert "FileEditPreviewError" in names
    for absent in (
        "FileEditApplyError",
        "FileEditWriteError",
        "CommandExecutionError",
        "GitError",
    ):
        assert absent not in names
