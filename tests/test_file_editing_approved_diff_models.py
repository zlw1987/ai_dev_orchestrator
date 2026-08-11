"""Phase 5F0 tests: file-edit write gate models and the approved-diff parser.

Everything here is a **literal JSON string** or a literal dict. Every diff below
was typed into this file by hand: none was generated, none is applied, no
artifact is read from disk, no environment variable is read, no socket is
opened, no command is run, no file is edited, no branch is created, nothing is
committed or pushed, and no target project workspace is read, listed, stat'd,
globbed, or resolved. No path below names a real project, and the source lines
inside the diffs describe an invented billing helper.

The parser under test is pure, so the IO tests below assert that directly:
``builtins.open``, the ``os`` environment/filesystem entry points, ``socket``,
and ``subprocess`` are all replaced with detonators for the duration of a
successful parse and of failing ones.
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
from pydantic import ValidationError
from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.diff_proposal import (
    DIFF_PROPOSAL_MODE,
    DIFF_PROPOSAL_SCHEMA_VERSION,
    DiffProposalArtifact,
    DiffProposalFileChange,
    parse_diff_proposal_artifact,
)
from ai_dev_orchestrator.file_editing import (
    APPROVED_DIFF_PROPOSAL_MODE,
    APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
    REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    ApprovedDiffProposalArtifact,
    DiffEditApproval,
    FileEditingApprovalError,
    FileEditingApprovalParseError,
    FileEditingApprovalValidationError,
    parse_approved_diff_proposal_artifact,
)
from ai_dev_orchestrator.handoff import (
    REQUIRED_APPROVAL_TEXT,
    ApprovedL1PlanArtifact,
)

runner = CliRunner()

PROJECT_ID = "acme_widgets"
REPO = "acme/widgets"
ISSUE_NUMBER = 42
TITLE = "Add currency formatting helper"

ALLOWED_PATH = "src/billing/format.py"
ALLOWED_TEST_PATH = "tests/test_format.py"
FORBIDDEN_PATH = "external_auth/client.py"

# A Phase 5B-shaped approved plan. Constructed here as a literal, never loaded.
VALID_PLAN: dict = {
    "issue_number": ISSUE_NUMBER,
    "repo": REPO,
    "title": TITLE,
    "summary": "Format invoice totals through one shared helper.",
    "scope_summary": "Only the billing formatting helper and its tests.",
    "non_goals": ["No changes to the payment gateway client."],
    "proposed_steps": [
        "Review where invoice totals are formatted today.",
        "Describe a single shared helper for a human to implement.",
    ],
    "files_likely_to_change": [ALLOWED_PATH, ALLOWED_TEST_PATH],
    "files_forbidden_or_out_of_scope": [FORBIDDEN_PATH],
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

# The Phase 5B plan approval. A *different* approval, of a *different* thing.
VALID_PLAN_APPROVAL: dict = {
    "approved_by": "operator@example.invalid",
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
    "approved_by": "operator@example.invalid",
    "approved_at": "2026-01-04T06:00:00+00:00",
    "approval_text": REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    "source": "manual",
}

NEXT_AUTHORIZATION = (
    "A file-editing phase must be explicitly authorized before anything writes "
    "these diffs; this artifact records approval only and applies nothing."
)


# -- Hand-written fixtures -----------------------------------------------------


def _modify_diff(path: str = ALLOWED_PATH) -> str:
    """A minimal, hand-typed single-file modification diff for ``path``."""
    return (
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,4 +1,4 @@\n"
        " def format_total(amount):\n"
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


def _change(path: str = ALLOWED_PATH, change_type: str = "modify") -> dict:
    diff = _create_diff(path) if change_type == "create" else _modify_diff(path)
    return {
        "path": path,
        "change_type": change_type,
        "unified_diff": diff,
        "rationale": "The shared helper belongs here, next to the existing totals code.",
        "risks": ["Existing call sites may round differently today."],
        "requires_human_review": True,
    }


def _diff_proposal(changes: list[dict] | None = None) -> dict:
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
        "omitted_paths": [],
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


def _artifact(
    changes: list[dict] | None = None, diff_proposal: dict | None = None
) -> dict:
    """A fresh, fully valid Phase 5F0 wrapper. Callers mutate their own copy."""
    return {
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


def _text(artifact: dict) -> str:
    return json.dumps(artifact)


def _valid_proposal_object() -> DiffProposalArtifact:
    """A validated Phase 5E2 object, for the direct-construction tests below."""
    return parse_diff_proposal_artifact(json.dumps(_diff_proposal()))


def _construct(proposal: DiffProposalArtifact) -> ApprovedDiffProposalArtifact:
    """Build the wrapper directly around an already-validated proposal object.

    Pydantic does not re-validate a model instance it is handed, so this is the
    route by which a mutated or hand-built proposal could reach the write gate.
    Every invariant the gate re-checks exists for exactly this path.
    """
    return ApprovedDiffProposalArtifact(
        schema_version=APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
        mode=APPROVED_DIFF_PROPOSAL_MODE,
        approval=DiffEditApproval(**copy.deepcopy(VALID_EDIT_APPROVAL)),
        diff_proposal=proposal,
        project_id=PROJECT_ID,
        repo=REPO,
        issue_number=ISSUE_NUMBER,
        title=TITLE,
        next_authorization_required=NEXT_AUTHORIZATION,
    )


# -- 1. The happy path ---------------------------------------------------------


def test_valid_artifact_parses():
    parsed = parse_approved_diff_proposal_artifact(_text(_artifact()))

    assert isinstance(parsed, ApprovedDiffProposalArtifact)
    assert parsed.schema_version == APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION
    assert parsed.mode == APPROVED_DIFF_PROPOSAL_MODE
    assert parsed.project_id == PROJECT_ID
    assert parsed.repo == REPO
    assert parsed.issue_number == ISSUE_NUMBER
    assert parsed.title == TITLE
    assert parsed.next_authorization_required == NEXT_AUTHORIZATION


def test_valid_artifact_carries_a_diff_edit_approval():
    parsed = parse_approved_diff_proposal_artifact(_text(_artifact()))

    assert isinstance(parsed.approval, DiffEditApproval)
    assert parsed.approval.approved_by == "operator@example.invalid"
    assert parsed.approval.approval_text == REQUIRED_DIFF_EDIT_APPROVAL_TEXT
    assert parsed.approval.source == "manual"
    assert parsed.approval.approved_at == datetime(
        2026, 1, 4, 6, 0, tzinfo=timezone.utc
    )


def test_valid_artifact_carries_an_unchanged_diff_proposal_snapshot():
    proposal = _diff_proposal(changes=[_change(ALLOWED_PATH)])

    parsed = parse_approved_diff_proposal_artifact(
        _text(_artifact(diff_proposal=proposal))
    )

    assert isinstance(parsed.diff_proposal, DiffProposalArtifact)
    assert isinstance(parsed.diff_proposal.approved_plan, ApprovedL1PlanArtifact)
    # The proposal round-trips: nothing is normalized, re-approved, or annotated.
    assert parsed.diff_proposal.approved_plan.plan.model_dump() == VALID_PLAN
    assert parsed.diff_proposal.changes[0].unified_diff == _modify_diff(ALLOWED_PATH)
    assert (
        parsed.diff_proposal.approved_plan.approval.approval_text
        == REQUIRED_APPROVAL_TEXT
    )


def test_valid_artifact_may_wrap_a_modify_diff():
    parsed = parse_approved_diff_proposal_artifact(
        _text(_artifact(changes=[_change(ALLOWED_PATH, "modify")]))
    )

    change = parsed.diff_proposal.changes[0]
    assert isinstance(change, DiffProposalFileChange)
    assert change.change_type == "modify"
    assert change.path == ALLOWED_PATH


def test_valid_artifact_may_wrap_a_create_diff():
    parsed = parse_approved_diff_proposal_artifact(
        _text(_artifact(changes=[_change(ALLOWED_TEST_PATH, "create")]))
    )

    change = parsed.diff_proposal.changes[0]
    assert change.change_type == "create"
    assert change.path == ALLOWED_TEST_PATH
    assert change.unified_diff.startswith("--- /dev/null\n")


def test_valid_artifact_may_wrap_two_distinct_changes():
    parsed = parse_approved_diff_proposal_artifact(
        _text(
            _artifact(
                changes=[
                    _change(ALLOWED_PATH, "modify"),
                    _change(ALLOWED_TEST_PATH, "create"),
                ]
            )
        )
    )

    assert [change.path for change in parsed.diff_proposal.changes] == [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
    ]


def test_valid_artifact_may_wrap_empty_diff_changes():
    parsed = parse_approved_diff_proposal_artifact(_text(_artifact(changes=[])))

    # A human may approve a proposal that proposes nothing. A future apply phase
    # would simply have nothing to edit — that is well-formed, not a loophole.
    assert parsed.diff_proposal.changes == []


def test_direct_construction_around_a_valid_proposal_object_succeeds():
    """Positive control for every ``_construct`` rejection test below.

    Those tests mutate a validated proposal object and assert the wrapper
    rejects it. This one proves the unmutated object is accepted, so a rejection
    below is the gate firing rather than the construction path being broken.
    """
    built = _construct(_valid_proposal_object())

    assert isinstance(built, ApprovedDiffProposalArtifact)
    assert built.approval.approval_text == REQUIRED_DIFF_EDIT_APPROVAL_TEXT
    assert built.diff_proposal.changes[0].path == ALLOWED_PATH


def test_parser_accepts_surrounding_whitespace():
    text = "\n\n\t  " + _text(_artifact()) + "  \n\t\n"

    parsed = parse_approved_diff_proposal_artifact(text)

    assert parsed.issue_number == ISSUE_NUMBER


def test_constants_are_the_phase_5f0_values():
    assert (
        REQUIRED_DIFF_EDIT_APPROVAL_TEXT
        == "I approve this diff proposal for workspace file editing"
    )
    assert APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION == "approved-diff-proposal.v1"
    assert APPROVED_DIFF_PROPOSAL_MODE == "file-edit-approval-only"


def test_file_edit_approval_text_is_separate_from_the_l1_plan_approval_text():
    # Two distinct human acts, two distinct sentences. Neither implies the other.
    assert REQUIRED_DIFF_EDIT_APPROVAL_TEXT != REQUIRED_APPROVAL_TEXT
    assert REQUIRED_APPROVAL_TEXT not in REQUIRED_DIFF_EDIT_APPROVAL_TEXT
    assert REQUIRED_DIFF_EDIT_APPROVAL_TEXT not in REQUIRED_APPROVAL_TEXT


def test_error_types_share_one_base():
    assert issubclass(FileEditingApprovalParseError, FileEditingApprovalError)
    assert issubclass(FileEditingApprovalValidationError, FileEditingApprovalError)
    assert issubclass(FileEditingApprovalError, Exception)


# -- 2. The approval block -----------------------------------------------------


def test_approval_block_is_required():
    artifact = _artifact()
    artifact.pop("approval")

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_approval_block_may_not_be_null():
    artifact = _artifact()
    artifact["approval"] = None

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("field", ["approved_by", "approved_at", "approval_text", "source"])
def test_missing_approval_fields_rejected(field):
    artifact = _artifact()
    artifact["approval"].pop(field)

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_approved_by_must_not_be_blank(value):
    artifact = _artifact()
    artifact["approval"]["approved_by"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("value", ["not a timestamp", "", "2026-13-45T99:00:00Z"])
def test_approved_at_must_be_parseable(value):
    artifact = _artifact()
    artifact["approval"]["approved_at"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_approved_at_parses_a_real_timestamp():
    artifact = _artifact()
    artifact["approval"]["approved_at"] = "2026-02-03T04:05:06+00:00"

    parsed = parse_approved_diff_proposal_artifact(_text(artifact))

    assert parsed.approval.approved_at == datetime(
        2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    "value",
    [
        # Case variants.
        "i approve this diff proposal for workspace file editing",
        "I APPROVE THIS DIFF PROPOSAL FOR WORKSPACE FILE EDITING",
        "I Approve This Diff Proposal For Workspace File Editing",
        # Punctuation.
        "I approve this diff proposal for workspace file editing.",
        "I approve this diff proposal for workspace file editing!",
        # Whitespace.
        " I approve this diff proposal for workspace file editing",
        "I approve this diff proposal for workspace file editing ",
        "I approve  this diff proposal for workspace file editing",
        "I approve this diff proposal for workspace file editing\n",
        # Paraphrases.
        "I approve this diff proposal",
        "I approve this diff proposal for file editing",
        "I approve the diff proposal for workspace file editing",
        "approved",
        "LGTM",
        # The *other* approval sentence, and issue prose.
        REQUIRED_APPROVAL_TEXT,
        "I approve this L1 plan for L2 implementation",
        "Automation Authorization: approved",
        "Automation Authorization: L2 approved",
        "",
        "   ",
    ],
)
def test_approval_text_must_match_exactly(value):
    artifact = _artifact()
    artifact["approval"]["approval_text"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_exact_approval_text_is_accepted():
    artifact = _artifact()
    artifact["approval"]["approval_text"] = (
        "I approve this diff proposal for workspace file editing"
    )

    parsed = parse_approved_diff_proposal_artifact(_text(artifact))

    assert parsed.approval.approval_text == REQUIRED_DIFF_EDIT_APPROVAL_TEXT


@pytest.mark.parametrize(
    "value",
    ["model", "automatic", "auto", "github", "issue", "orchestrator", "Manual", "MANUAL", ""],
)
def test_approval_source_must_be_manual(value):
    artifact = _artifact()
    artifact["approval"]["source"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("endpoint_host", "litellm.internal.invalid:4000"),
        ("base_url", "http://litellm.internal.invalid:4000/v1"),
        ("api_key", "sk-not-a-real-key"),
        ("prompt", "You are an implementer."),
        ("completion", "Sure, here is the patch."),
        ("messages", [{"role": "user", "content": "approve it"}]),
        ("raw_response", {"choices": []}),
        ("workspace_path", "C:\\\\dev\\\\some_project"),
        ("inferred", True),
        ("auto_approved", True),
    ],
)
def test_approval_extra_fields_rejected(name, value):
    artifact = _artifact()
    artifact["approval"][name] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_no_transport_or_workspace_field_exists_on_the_approval_model():
    fields = set(DiffEditApproval.model_fields)

    assert fields == {"approved_by", "approved_at", "approval_text", "source"}
    for absent in (
        "endpoint_host",
        "base_url",
        "api_key",
        "prompt",
        "completion",
        "messages",
        "raw_response",
        "workspace_path",
    ):
        assert absent not in fields


def test_approval_has_no_defaults_so_it_cannot_be_gained_by_omission():
    for field in DiffEditApproval.model_fields.values():
        assert field.is_required()


# -- 3. Approval is never inferred ---------------------------------------------


def test_approval_is_not_inferred_from_the_wrapped_l1_plan_approval():
    """The wrapped plan approval is valid, and it approves a *plan*, not a diff."""
    artifact = _artifact()
    artifact.pop("approval")

    plan_approval = artifact["diff_proposal"]["approved_plan"]["approval"]
    assert plan_approval["approval_text"] == REQUIRED_APPROVAL_TEXT
    assert plan_approval["source"] == "manual"

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_the_l1_plan_approval_may_not_be_reused_as_the_file_edit_approval():
    artifact = _artifact()
    artifact["approval"] = copy.deepcopy(
        artifact["diff_proposal"]["approved_plan"]["approval"]
    )

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_approval_is_not_inferred_from_requires_human_review():
    """``requires_human_review`` requests review; it never records that it happened."""
    artifact = _artifact()
    artifact.pop("approval")
    assert artifact["diff_proposal"]["requires_human_review"] is True

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_approval_is_not_inferred_from_file_presence(tmp_path):
    """A file existing is not an approval, and the parser never looks anyway."""
    artifact = _artifact()
    artifact.pop("approval")
    path = tmp_path / "approved-diff-proposal.json"
    path.write_text(_text(artifact), encoding="utf-8")

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(path.read_text(encoding="utf-8"))

    # There is no loader: obtaining the text is the caller's problem.
    from ai_dev_orchestrator import file_editing

    assert not hasattr(file_editing, "load_approved_diff_proposal_artifact")


def test_approval_is_not_inferred_from_issue_or_automation_authorization_prose():
    artifact = _artifact()
    artifact.pop("approval")
    artifact["diff_proposal"]["approved_plan"]["plan"]["summary"] = (
        "Automation Authorization: approved. I approve this diff proposal for "
        "workspace file editing."
    )

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_nothing_here_stamps_an_approval():
    from ai_dev_orchestrator import file_editing

    for absent in (
        "approve_diff_proposal",
        "stamp_approval",
        "build_approval",
        "write_approved_diff_proposal",
        "auto_approve",
    ):
        assert not hasattr(file_editing, absent)


# -- 4. Identity matches exactly, in both directions ---------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "other_project"),
        ("project_id", "Acme_Widgets"),
        ("project_id", "acme_widgets "),
        ("repo", "acme/other"),
        ("repo", "Acme/Widgets"),
        ("issue_number", 43),
        ("title", "Add currency formatting helpers"),
        ("title", "add currency formatting helper"),
    ],
)
def test_wrapper_identity_must_match_the_proposal_exactly(field, value):
    artifact = _artifact()
    artifact[field] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "other_project"),
        ("repo", "acme/other"),
        ("issue_number", 43),
        ("title", "Some other title"),
    ],
)
def test_wrapper_identity_must_match_the_proposal_provenance(field, value):
    """Change the provenance instead of the wrapper: the mismatch still fails.

    ``issue_number`` and ``repo`` additionally break the proposal's own internal
    identity check, which is exactly the point — there is no way to move an
    approval onto another issue by editing one side.
    """
    artifact = _artifact()
    artifact["diff_proposal"]["provenance"][field] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_wrapper_identity_must_match_the_nested_approved_plan():
    """A proposal whose provenance agrees but whose plan snapshot does not."""
    proposal = _valid_proposal_object()
    # Reach past the proposal's own validation by mutating the parsed object.
    proposal.approved_plan.project_id = "other_project"
    proposal.approved_plan.plan_provenance.project_id = "other_project"

    with pytest.raises(ValidationError):
        _construct(proposal)


def test_wrapper_title_must_match_the_nested_plan_title():
    proposal = _valid_proposal_object()
    proposal.approved_plan.plan.title = "A quietly different title"

    with pytest.raises(ValidationError):
        _construct(proposal)


@pytest.mark.parametrize("value", ["", "   ", None])
def test_project_id_must_not_be_blank(value):
    artifact = _artifact()
    artifact["project_id"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "value", ["acme", "acme/", "/widgets", "acme/widgets/extra", "", "   ", "/"]
)
def test_repo_must_look_like_owner_repo(value):
    artifact = _artifact()
    artifact["repo"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("value", [0, -1, -42])
def test_issue_number_must_be_positive(value):
    artifact = _artifact()
    artifact["issue_number"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_title_must_not_be_blank(value):
    artifact = _artifact()
    artifact["title"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("value", ["", "   "])
def test_next_authorization_required_must_not_be_blank(value):
    artifact = _artifact()
    artifact["next_authorization_required"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "value",
    ["approved-diff-proposal.v2", "diff-proposal.v1", "APPROVED-DIFF-PROPOSAL.V1", ""],
)
def test_schema_version_must_be_exact(value):
    artifact = _artifact()
    artifact["schema_version"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "value", ["proposal-only", "apply", "file-edit", "File-Edit-Approval-Only", ""]
)
def test_mode_must_be_exact(value):
    artifact = _artifact()
    artifact["mode"] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


# -- 5. The wrapped diff proposal's invariants are re-checked ------------------


def test_diff_proposal_is_required():
    artifact = _artifact()
    artifact.pop("diff_proposal")

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_diff_proposal_may_not_be_null():
    artifact = _artifact()
    artifact["diff_proposal"] = None

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_malformed_diff_proposal_rejected_through_nested_validation():
    artifact = _artifact()
    artifact["diff_proposal"]["changes"][0]["unified_diff"] = "not a diff at all"

    with pytest.raises(FileEditingApprovalValidationError) as excinfo:
        parse_approved_diff_proposal_artifact(_text(artifact))

    assert "diff_proposal" in str(excinfo.value)


def test_diff_proposal_extra_fields_rejected():
    artifact = _artifact()
    artifact["diff_proposal"]["apply"] = True

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("files_edited", True),
        ("commands_run", True),
        ("applies_cleanly_checked", True),
        ("diffs_generated", False),
        ("requires_human_review", False),
    ],
)
def test_diff_proposal_flags_rejected_through_json(flag, value):
    artifact = _artifact()
    artifact["diff_proposal"][flag] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("files_edited", True),
        ("commands_run", True),
        ("applies_cleanly_checked", True),
        ("diffs_generated", False),
        ("requires_human_review", False),
    ],
)
def test_diff_proposal_flags_rechecked_on_a_mutated_object(flag, value):
    """The gate does not inherit its safety from a model instance it was handed."""
    proposal = _valid_proposal_object()
    setattr(proposal, flag, value)

    with pytest.raises(ValidationError):
        _construct(proposal)


def test_automation_level_must_be_l1_through_json():
    artifact = _artifact()
    artifact["diff_proposal"]["approved_plan"]["plan"]["automation_level"] = "L2"

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_automation_level_rechecked_on_a_mutated_object():
    proposal = _valid_proposal_object()
    proposal.approved_plan.plan.automation_level = "L2"

    with pytest.raises(ValidationError):
        _construct(proposal)


def test_requires_human_approval_must_be_true_through_json():
    artifact = _artifact()
    artifact["diff_proposal"]["approved_plan"]["plan"]["requires_human_approval"] = False

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_requires_human_approval_rechecked_on_a_mutated_object():
    proposal = _valid_proposal_object()
    proposal.approved_plan.plan.requires_human_approval = False

    with pytest.raises(ValidationError):
        _construct(proposal)


def test_duplicate_change_paths_rejected_through_json():
    artifact = _artifact(changes=[_change(ALLOWED_PATH), _change(ALLOWED_PATH)])

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_duplicate_change_paths_rechecked_on_a_mutated_object():
    """Duplicates are re-checked here even when the nested check was bypassed."""
    proposal = _valid_proposal_object()
    proposal.changes.append(
        DiffProposalFileChange(
            path=ALLOWED_PATH,
            change_type="modify",
            unified_diff=_modify_diff(ALLOWED_PATH),
            rationale="A second, contradictory diff for the same file.",
            requires_human_review=True,
        )
    )

    with pytest.raises(ValidationError):
        _construct(proposal)


def test_out_of_scope_change_path_rejected_through_json():
    artifact = _artifact(changes=[_change("src/billing/other.py")])

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_out_of_scope_change_path_rechecked_on_a_mutated_object():
    proposal = _valid_proposal_object()
    proposal.changes.append(
        DiffProposalFileChange(
            path="src/billing/other.py",
            change_type="modify",
            unified_diff=_modify_diff("src/billing/other.py"),
            rationale="A path the approved plan never listed.",
            requires_human_review=True,
        )
    )

    with pytest.raises(ValidationError):
        _construct(proposal)


def test_forbidden_change_path_rejected_through_json():
    artifact = _artifact(changes=[_change(FORBIDDEN_PATH)])

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_forbidden_change_path_rechecked_on_a_mutated_object():
    proposal = _valid_proposal_object()
    proposal.changes.append(
        DiffProposalFileChange(
            path=FORBIDDEN_PATH,
            change_type="modify",
            unified_diff=_modify_diff(FORBIDDEN_PATH),
            rationale="A path the approved plan explicitly forbade.",
            requires_human_review=True,
        )
    )

    with pytest.raises(ValidationError):
        _construct(proposal)


def test_a_forbidden_path_wins_over_an_allowed_one():
    """Even if a plan lists a path in both lists, forbidden decides."""
    proposal = _diff_proposal(changes=[_change(FORBIDDEN_PATH)])
    plan = proposal["approved_plan"]["plan"]
    plan["files_likely_to_change"] = [ALLOWED_PATH, ALLOWED_TEST_PATH, FORBIDDEN_PATH]

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(
            _text(_artifact(diff_proposal=proposal))
        )


def test_nested_patch_proposal_consistency_is_not_loosened():
    """A disagreeing patch proposal snapshot still fails, via Phase 5E2's rules."""
    proposal = _diff_proposal(changes=[_change(ALLOWED_PATH)])
    proposal["patch_proposal"] = {
        "schema_version": "patch-proposal.v1",
        "mode": "proposal-only",
        "provenance": {
            "engine": "deterministic",
            "operation": "patch-proposal",
            "real_call": False,
            "model": None,
            "generated_at": None,
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
            "title": "A different title entirely",
        },
        "approved_plan": copy.deepcopy(VALID_APPROVED_PLAN),
        "changes": [],
        "omitted_paths": [],
        "assumptions": [],
        "risks": [],
        "open_questions": [],
        "file_contents_read": False,
        "files_edited": False,
        "commands_run": False,
        "requires_human_review": True,
        "next_authorization_required": "Phase 5E2 must be authorized separately.",
    }

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(
            _text(_artifact(diff_proposal=proposal))
        )


# -- 6. No forbidden payload ---------------------------------------------------


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("raw_artifact_text", "{...}"),
        ("source_contents", "def format_total(amount): ..."),
        ("file_contents", {ALLOWED_PATH: "def format_total(amount): ..."}),
        ("before_content", "def format_total(amount): ..."),
        ("after_content", 'def format_total(amount): return f"{amount:.2f}"'),
        ("command", "pytest -q"),
        ("commands", ["pytest -q"]),
        ("command_output", "1 passed"),
        ("required_verification", ["pytest -q"]),
        ("prompt", "You are an implementer."),
        ("completion", "Sure, here is the patch."),
        ("messages", [{"role": "user", "content": "go"}]),
        ("raw_response", {"choices": []}),
        ("api_key", "sk-not-a-real-key"),
        ("base_url", "http://litellm.internal.invalid:4000/v1"),
        ("endpoint_host", "litellm.internal.invalid:4000"),
        ("workspace_path", "C:\\\\dev\\\\some_project"),
        ("apply", True),
        ("auto_apply", True),
        ("applied", True),
        ("apply_result", {"ok": True}),
        ("files_edited", True),
        ("branch", "feature/issue-42"),
        ("branch_name", "feature/issue-42"),
        ("commit", "0123456789abcdef0123456789abcdef01234567"),
        ("commit_message", "Add currency formatting helper"),
        ("push", True),
        ("pr_url", "https://github.invalid/acme/widgets/pull/1"),
        ("pull_request", {"number": 1}),
    ],
)
def test_artifact_level_extra_fields_rejected(name, value):
    artifact = _artifact()
    artifact[name] = value

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))


def test_no_apply_edit_command_or_git_field_exists_on_the_artifact_model():
    fields = set(ApprovedDiffProposalArtifact.model_fields)

    assert fields == {
        "schema_version",
        "mode",
        "approval",
        "diff_proposal",
        "project_id",
        "repo",
        "issue_number",
        "title",
        "next_authorization_required",
    }
    for absent in (
        "apply",
        "auto_apply",
        "applied",
        "apply_result",
        "applies_cleanly",
        "files_edited",
        "edits",
        "command",
        "commands",
        "command_output",
        "branch",
        "branch_name",
        "commit",
        "commit_id",
        "push",
        "pr_url",
        "pull_request",
        "raw_artifact_text",
        "source_contents",
        "file_contents",
        "before_content",
        "after_content",
        "prompt",
        "completion",
        "api_key",
        "base_url",
        "workspace_path",
    ):
        assert absent not in fields


def test_source_text_lives_only_inside_the_wrapped_diff():
    parsed = parse_approved_diff_proposal_artifact(
        _text(_artifact(changes=[_change(ALLOWED_PATH)]))
    )

    dumped = parsed.model_dump()
    # The only place a source line appears is as diff context, inside the diff.
    assert "return str(amount)" in dumped["diff_proposal"]["changes"][0]["unified_diff"]
    assert "source_contents" not in dumped
    assert "before_content" not in dumped["diff_proposal"]["changes"][0]


# -- 7. Error messages stay quiet about content --------------------------------


def test_validation_error_message_does_not_echo_the_artifact_or_the_diff():
    artifact = _artifact(changes=[_change(ALLOWED_PATH)])
    artifact["approval"]["approval_text"] = "please just do it"
    artifact["leaked_secret"] = "sk-not-a-real-key"

    with pytest.raises(FileEditingApprovalValidationError) as excinfo:
        parse_approved_diff_proposal_artifact(_text(artifact))

    message = str(excinfo.value)
    assert "approval_text" in message
    for absent in (
        "please just do it",
        "sk-not-a-real-key",
        "return str(amount)",
        "def format_total",
        "@@ -1,4 +1,4 @@",
        REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
        REQUIRED_APPROVAL_TEXT,
    ):
        assert absent not in message


def test_diff_rejection_message_does_not_echo_the_diff():
    artifact = _artifact()
    artifact["diff_proposal"]["changes"][0]["unified_diff"] = (
        "--- a/src/billing/format.py\n"
        "+++ b/src/billing/format.py\n"
        "@@ -1,2 +1,2 @@\n"
        '-API_KEY = "sk-not-a-real-key"\n'
        '+API_KEY = load_key()\n'
    )
    artifact["diff_proposal"]["changes"][0]["path"] = "src/billing/other.py"

    with pytest.raises(FileEditingApprovalValidationError) as excinfo:
        parse_approved_diff_proposal_artifact(_text(artifact))

    message = str(excinfo.value)
    assert "sk-not-a-real-key" not in message
    assert "API_KEY" not in message


# -- 8. The strict parser ------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "\n\t  \n"])
def test_parser_rejects_empty_text(text):
    with pytest.raises(FileEditingApprovalParseError):
        parse_approved_diff_proposal_artifact(text)


@pytest.mark.parametrize("text", ["{not json}", "{'single': 'quotes'}", "{", "{}}"])
def test_parser_rejects_invalid_json(text):
    with pytest.raises(FileEditingApprovalParseError):
        parse_approved_diff_proposal_artifact(text)


def test_parser_rejects_markdown_fenced_json():
    text = "```json\n" + _text(_artifact()) + "\n```"

    with pytest.raises(FileEditingApprovalParseError):
        parse_approved_diff_proposal_artifact(text)


def test_parser_rejects_prose_before_json():
    text = "Here is the approved diff proposal:\n" + _text(_artifact())

    with pytest.raises(FileEditingApprovalParseError):
        parse_approved_diff_proposal_artifact(text)


def test_parser_rejects_prose_after_json():
    text = _text(_artifact()) + "\n\nI approve this, go ahead and edit the files."

    with pytest.raises(FileEditingApprovalParseError):
        parse_approved_diff_proposal_artifact(text)


@pytest.mark.parametrize(
    "text", ["[]", '["approved"]', '"approved"', "42", "true", "false", "null"]
)
def test_parser_rejects_non_object_json(text):
    with pytest.raises(FileEditingApprovalParseError):
        parse_approved_diff_proposal_artifact(text)


@pytest.mark.parametrize("value", [None, 42, {"approval": {}}, b"{}"])
def test_parser_rejects_non_string_input(value):
    with pytest.raises(FileEditingApprovalParseError):
        parse_approved_diff_proposal_artifact(value)


def test_parser_never_repairs_and_never_strips_unknown_fields():
    artifact = _artifact()
    artifact["auto_apply"] = True

    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(artifact))

    # And a missing required field is never inferred into existence.
    missing = _artifact()
    missing.pop("next_authorization_required")
    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(missing))


def test_parser_wraps_pydantic_validation_error():
    artifact = _artifact()
    artifact["issue_number"] = 0

    with pytest.raises(FileEditingApprovalValidationError) as excinfo:
        parse_approved_diff_proposal_artifact(_text(artifact))

    assert isinstance(excinfo.value.__cause__, ValidationError)
    assert isinstance(excinfo.value, FileEditingApprovalError)


def test_parser_is_deterministic():
    text = _text(_artifact())

    first = parse_approved_diff_proposal_artifact(text)
    second = parse_approved_diff_proposal_artifact(text)

    assert first.model_dump() == second.model_dump()


def test_parser_prints_nothing(capsys):
    parse_approved_diff_proposal_artifact(_text(_artifact()))
    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text({"schema_version": "wrong"}))

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# -- 9. The parser performs no IO of any kind ----------------------------------


def _detonate(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("the approved diff proposal parser performed IO")

    monkeypatch.setattr(builtins, "open", boom)
    monkeypatch.setattr(os, "getenv", boom)
    monkeypatch.setattr(os.environ, "get", boom)
    monkeypatch.setattr(os, "stat", boom)
    monkeypatch.setattr(os, "lstat", boom)
    monkeypatch.setattr(os, "listdir", boom)
    monkeypatch.setattr(os, "scandir", boom)
    monkeypatch.setattr(os, "walk", boom)
    monkeypatch.setattr(os.path, "exists", boom)
    monkeypatch.setattr(os.path, "abspath", boom)
    monkeypatch.setattr(os.path, "realpath", boom)
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)


def test_parser_performs_no_file_network_process_env_or_workspace_io(monkeypatch):
    _detonate(monkeypatch)

    parsed = parse_approved_diff_proposal_artifact(
        _text(
            _artifact(
                changes=[
                    _change(ALLOWED_PATH, "modify"),
                    _change(ALLOWED_TEST_PATH, "create"),
                ]
            )
        )
    )

    assert [change.path for change in parsed.diff_proposal.changes] == [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
    ]


def test_parser_failure_paths_also_perform_no_io(monkeypatch):
    _detonate(monkeypatch)

    # An absolute, workspace-shaped path is refused lexically — never resolved.
    unsafe = _artifact(changes=[_change("C:\\dev\\some_project\\src\\format.py")])
    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(unsafe))

    bad_approval = _artifact()
    bad_approval["approval"]["approval_text"] = "approved"
    with pytest.raises(FileEditingApprovalValidationError):
        parse_approved_diff_proposal_artifact(_text(bad_approval))

    with pytest.raises(FileEditingApprovalParseError):
        parse_approved_diff_proposal_artifact("not json at all")


def test_parser_writes_no_files(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())

    parse_approved_diff_proposal_artifact(_text(_artifact()))

    assert sorted(p.name for p in tmp_path.iterdir()) == before


# -- 10. The implementation module cannot reach a model, a socket, or GitHub ---


def test_implementation_module_globals_are_inert():
    from ai_dev_orchestrator.file_editing import models as editing_models

    module_globals = vars(editing_models)
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
        "difflib",
    ):
        assert name not in module_globals, f"{name} must not be importable here"


def test_implementation_module_imports_no_transport_cli_workspace_or_differ():
    from ai_dev_orchestrator.file_editing import models as editing_models

    with open(editing_models.__file__, encoding="utf-8") as handle:
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
        "from ai_dev_orchestrator.workspace",
        "AIDO_LITELLM",
        "GITHUB_TOKEN",
    ):
        assert forbidden not in text, f"{forbidden!r} must not appear"


def test_file_editing_package_exports_exactly_the_phase_5f0_surface():
    from ai_dev_orchestrator import file_editing

    expected = [
        "APPROVED_DIFF_PROPOSAL_MODE",
        "APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION",
        "REQUIRED_DIFF_EDIT_APPROVAL_TEXT",
        "ApprovedDiffProposalArtifact",
        "DiffEditApproval",
        "FileEditingApprovalError",
        "FileEditingApprovalParseError",
        "FileEditingApprovalValidationError",
        "parse_approved_diff_proposal_artifact",
    ]
    assert sorted(file_editing.__all__) == sorted(expected)
    for name in expected:
        assert hasattr(file_editing, name)

    # No editor, no applier, no loader, no writer, no runner. Later phases, if
    # ever — and each needs its own explicit authorization.
    for absent in (
        "apply_approved_diff_proposal",
        "apply_diff",
        "apply_patch",
        "edit_files",
        "write_files",
        "check_applies_cleanly",
        "load_approved_diff_proposal_artifact",
        "write_approved_diff_proposal_artifact",
        "run_required_verification",
        "create_branch",
        "commit_changes",
        "push_branch",
        "open_pull_request",
        "DiffApplier",
        "FileEditor",
        "L2Implementer",
    ):
        assert not hasattr(file_editing, absent)


def test_importing_the_package_touches_nothing(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("importing file_editing performed IO")

    monkeypatch.setattr(os, "getenv", boom)
    monkeypatch.setattr(os.environ, "get", boom)
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)

    import importlib

    import ai_dev_orchestrator.file_editing as file_editing

    importlib.reload(file_editing)

    assert file_editing.APPROVED_DIFF_PROPOSAL_MODE == "file-edit-approval-only"


# -- 11. The CLI surface -------------------------------------------------------


# Phase 5F0 adds no command and no option. This is the Phase 5E3 list, unchanged.
EXPECTED_COMMANDS = [
    "version",
    "inspect-issue",
    "llm-smoke-test",
    "generate-plan",
    "real-llm-smoke-test",
    "generate-model-plan",
    "l2-dry-run",
    "l2-inspect-workspace",
    "generate-patch-proposal",
    "l2-read-workspace-files",
    "generate-diff-proposal",
]


def test_root_help_lists_exactly_the_shipped_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in EXPECTED_COMMANDS:
        assert command in result.output

    registered = [
        info.name or info.callback.__name__.replace("_", "-")
        for info in app.registered_commands
    ]
    assert registered == EXPECTED_COMMANDS


def test_importing_file_editing_adds_no_command():
    import ai_dev_orchestrator.file_editing  # noqa: F401

    registered = [
        info.name or info.callback.__name__.replace("_", "-")
        for info in app.registered_commands
    ]
    assert registered == EXPECTED_COMMANDS


def test_no_approve_apply_edit_or_git_command_exists():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for absent in (
        "approve-diff",
        "approve-diff-proposal",
        "apply-diff",
        "apply-patch",
        "edit-files",
        "implement",
        "create-branch",
        "commit",
        "push",
        "open-pr",
    ):
        assert absent not in result.output

    for absent in (
        "approve-diff",
        "approve-diff-proposal",
        "apply-diff",
        "apply-diff-proposal",
        "apply-patch",
        "edit-files",
        "implement-plan",
        "create-branch",
        "open-pr",
    ):
        assert runner.invoke(app, [absent, "--help"]).exit_code != 0


def test_generate_diff_proposal_behavior_unchanged():
    result = runner.invoke(app, ["generate-diff-proposal", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-plan",
        "--workspace-content",
        "--proposed-content",
        "--generate-diff",
        "--format",
    ):
        assert present in result.output
    for absent in (
        "--approve-diff",
        "--approved-diff",
        "--apply-diff",
        "--edit-files",
        "--write-files",
        "--run-commands",
        "--branch",
        "--commit",
        "--push",
    ):
        assert absent not in result.output


def test_l2_read_workspace_files_behavior_unchanged():
    result = runner.invoke(app, ["l2-read-workspace-files", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-plan",
        "--apply-approved-plan",
        "--read-contents",
        "--format",
    ):
        assert present in result.output
    for absent in (
        "--approve-diff",
        "--approved-diff",
        "--apply-diff",
        "--edit-files",
        "--write-files",
    ):
        assert absent not in result.output


def test_generate_patch_proposal_behavior_unchanged():
    result = runner.invoke(app, ["generate-patch-proposal", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-plan",
        "--generate-proposal",
        "--format",
    ):
        assert present in result.output
    for absent in (
        "--approve-diff",
        "--approved-diff",
        "--apply-diff",
        "--edit-files",
        "--write-files",
    ):
        assert absent not in result.output


def test_l2_inspect_workspace_options_unchanged():
    result = runner.invoke(app, ["l2-inspect-workspace", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-plan",
        "--apply-approved-plan",
        "--inspect-workspace",
        "--format",
    ):
        assert present in result.output
    for absent in (
        "--approve-diff",
        "--approved-diff",
        "--apply-diff",
        "--edit-files",
        "--write-files",
    ):
        assert absent not in result.output


def test_l2_dry_run_options_unchanged():
    result = runner.invoke(app, ["l2-dry-run", "--help"])

    assert result.exit_code == 0
    for present in ("--project-config", "--approved-plan", "--format"):
        assert present in result.output
    for absent in (
        "--approve-diff",
        "--approved-diff",
        "--apply-diff",
        "--edit-files",
        "--write-files",
    ):
        assert absent not in result.output


@pytest.mark.parametrize("command", ["generate-plan", "generate-model-plan"])
def test_plan_commands_gain_no_approval_or_edit_option(command):
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0
    for absent in (
        "--approve-diff",
        "--approved-diff",
        "--apply-diff",
        "--edit-files",
        "--implement",
    ):
        assert absent not in result.output
