"""Phase 5E2 tests: unified diff proposal artifact models and the strict parser.

Everything here is a **literal JSON string** or a literal dict. Every diff below
was typed into this file by hand: none was generated, none is applied, no
artifact is read from disk, no environment variable is read, no socket is
opened, no command is run, no file is edited, and no target project workspace is
read, listed, stat'd, globbed, or resolved. No path below names a real project,
and the source lines inside the diffs describe an invented billing helper.

The parser under test is pure, so the IO tests below assert that directly:
``builtins.open``, the ``os`` environment/filesystem entry points, ``socket``,
and ``subprocess`` are all replaced with detonators for the duration of a
successful parse.
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
    DiffProposalError,
    DiffProposalFileChange,
    DiffProposalParseError,
    DiffProposalProvenance,
    DiffProposalValidationError,
    parse_diff_proposal_artifact,
)
from ai_dev_orchestrator.handoff import (
    REQUIRED_APPROVAL_TEXT,
    ApprovedL1PlanArtifact,
)
from ai_dev_orchestrator.patch_proposal import (
    PATCH_PROPOSAL_MODE,
    PATCH_PROPOSAL_SCHEMA_VERSION,
    PatchProposalArtifact,
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

VALID_APPROVAL: dict = {
    "approved_by": "operator@example.invalid",
    "approved_at": "2026-01-02T04:00:00+00:00",
    "approval_text": REQUIRED_APPROVAL_TEXT,
    "source": "manual",
}

VALID_APPROVED_PLAN: dict = {
    "approval": VALID_APPROVAL,
    "plan_provenance": VALID_PLAN_PROVENANCE,
    "plan": VALID_PLAN,
    "project_id": PROJECT_ID,
    "repo": REPO,
    "issue_number": ISSUE_NUMBER,
}

VALID_PROVENANCE: dict = {
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

NEXT_AUTHORIZATION = (
    "Phase 5E3 (diff generation) must be explicitly authorized before anything "
    "produces this artifact, and applying a diff is not authorized at all."
)


# -- Hand-written diff fixtures ------------------------------------------------


def _modify_diff(path: str = ALLOWED_PATH) -> str:
    """A minimal, hand-typed single-file modification diff for ``path``."""
    return (
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,4 +1,4 @@\n"
        " def format_total(amount):\n"
        '-    return str(amount)\n'
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


def _patch_proposal_change(path: str = ALLOWED_PATH) -> dict:
    """A Phase 5E0-shaped prose change — no diff, by design."""
    return {
        "path": path,
        "change_type": "modify",
        "rationale": "The shared helper belongs here.",
        "proposed_steps": ["Add a format_total helper that takes an amount."],
        "risks": ["Existing call sites may round differently today."],
        "requires_human_review": True,
    }


def _patch_proposal(changes: list[dict] | None = None) -> dict:
    """A fully valid Phase 5E0 proposal dict, for the optional snapshot field."""
    return {
        "schema_version": PATCH_PROPOSAL_SCHEMA_VERSION,
        "mode": PATCH_PROPOSAL_MODE,
        "provenance": {
            "engine": "deterministic",
            "operation": "patch-proposal",
            "real_call": False,
            "model": None,
            "generated_at": "2026-01-03T04:00:00+00:00",
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
            "title": TITLE,
        },
        "approved_plan": copy.deepcopy(VALID_APPROVED_PLAN),
        "changes": copy.deepcopy(changes)
        if changes is not None
        else [_patch_proposal_change(ALLOWED_PATH)],
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


def _artifact(
    changes: list[dict] | None = None, patch_proposal: dict | None = None
) -> dict:
    """A fresh, fully valid diff proposal dict. Callers mutate their own copy."""
    return {
        "schema_version": DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": DIFF_PROPOSAL_MODE,
        "provenance": copy.deepcopy(VALID_PROVENANCE),
        "approved_plan": copy.deepcopy(VALID_APPROVED_PLAN),
        "patch_proposal": copy.deepcopy(patch_proposal),
        "changes": copy.deepcopy(changes) if changes is not None else [],
        "omitted_paths": [ALLOWED_TEST_PATH],
        "assumptions": ["The helper has no existing callers outside billing."],
        "risks": ["A human may need to reconcile historical invoices."],
        "open_questions": ["Should the helper accept a locale argument?"],
        "source_contents_read": True,
        "diffs_generated": True,
        "files_edited": False,
        "commands_run": False,
        "applies_cleanly_checked": False,
        "requires_human_review": True,
        "next_authorization_required": NEXT_AUTHORIZATION,
    }


def _text(artifact: dict) -> str:
    return json.dumps(artifact)


# -- 1. The happy path ---------------------------------------------------------


def test_valid_artifact_parses():
    parsed = parse_diff_proposal_artifact(_text(_artifact()))

    assert isinstance(parsed, DiffProposalArtifact)
    assert isinstance(parsed.provenance, DiffProposalProvenance)
    assert isinstance(parsed.approved_plan, ApprovedL1PlanArtifact)
    assert parsed.schema_version == DIFF_PROPOSAL_SCHEMA_VERSION
    assert parsed.mode == DIFF_PROPOSAL_MODE
    assert parsed.diffs_generated is True
    assert parsed.files_edited is False
    assert parsed.commands_run is False
    assert parsed.applies_cleanly_checked is False
    assert parsed.requires_human_review is True
    assert parsed.next_authorization_required == NEXT_AUTHORIZATION


def test_valid_modify_diff_parses():
    parsed = parse_diff_proposal_artifact(
        _text(_artifact(changes=[_change(ALLOWED_PATH, "modify")]))
    )

    assert len(parsed.changes) == 1
    change = parsed.changes[0]
    assert isinstance(change, DiffProposalFileChange)
    assert change.path == ALLOWED_PATH
    assert change.change_type == "modify"
    assert change.requires_human_review is True
    # The diff is carried through verbatim: nothing is normalized or rewritten.
    assert change.unified_diff == _modify_diff(ALLOWED_PATH)


def test_valid_create_diff_parses():
    parsed = parse_diff_proposal_artifact(
        _text(_artifact(changes=[_change(ALLOWED_TEST_PATH, "create")]))
    )

    assert parsed.changes[0].change_type == "create"
    assert parsed.changes[0].path == ALLOWED_TEST_PATH
    assert parsed.changes[0].unified_diff.startswith("--- /dev/null\n")


def test_valid_artifact_with_two_distinct_changes():
    parsed = parse_diff_proposal_artifact(
        _text(
            _artifact(
                changes=[
                    _change(ALLOWED_PATH, "modify"),
                    _change(ALLOWED_TEST_PATH, "create"),
                ]
            )
        )
    )

    assert [change.path for change in parsed.changes] == [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
    ]


def test_valid_artifact_may_have_empty_changes():
    parsed = parse_diff_proposal_artifact(_text(_artifact(changes=[])))

    # "No diff proposed yet" is a well-formed statement, not a defect.
    assert parsed.changes == []


def test_valid_artifact_carries_an_unchanged_approved_plan_snapshot():
    parsed = parse_diff_proposal_artifact(_text(_artifact()))

    # The approved plan round-trips: nothing is normalized, reordered, defaulted
    # away, re-approved, or annotated with proposal metadata.
    assert parsed.approved_plan.plan.model_dump() == VALID_PLAN
    assert parsed.approved_plan.approval.approval_text == REQUIRED_APPROVAL_TEXT
    assert parsed.approved_plan.approval.source == "manual"
    assert parsed.approved_plan.approval.approved_at == datetime(
        2026, 1, 2, 4, 0, tzinfo=timezone.utc
    )
    assert parsed.approved_plan.plan.automation_level == "L1"
    assert parsed.approved_plan.plan.requires_human_approval is True


def test_patch_proposal_snapshot_may_be_absent():
    artifact = _artifact(changes=[_change()])
    artifact.pop("patch_proposal")

    parsed = parse_diff_proposal_artifact(_text(artifact))

    assert parsed.patch_proposal is None


def test_patch_proposal_snapshot_may_be_explicitly_null():
    parsed = parse_diff_proposal_artifact(_text(_artifact(changes=[_change()])))

    assert parsed.patch_proposal is None


def test_patch_proposal_snapshot_may_be_present():
    artifact = _artifact(
        changes=[_change(ALLOWED_PATH)], patch_proposal=_patch_proposal()
    )

    parsed = parse_diff_proposal_artifact(_text(artifact))

    assert isinstance(parsed.patch_proposal, PatchProposalArtifact)
    assert parsed.patch_proposal.changes[0].path == ALLOWED_PATH
    # The wrapped prose proposal still carries no diff of its own.
    assert "unified_diff" not in type(parsed.patch_proposal.changes[0]).model_fields


def test_empty_patch_proposal_changes_do_not_constrain_the_diffs():
    # A prose proposal that named no path means "none chosen yet", not "none
    # permitted": the approved plan is still the scope authority.
    artifact = _artifact(
        changes=[_change(ALLOWED_PATH)], patch_proposal=_patch_proposal(changes=[])
    )

    parsed = parse_diff_proposal_artifact(_text(artifact))

    assert parsed.patch_proposal.changes == []
    assert parsed.changes[0].path == ALLOWED_PATH


def test_optional_lists_default_to_empty():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0].pop("risks")
    for name in ("omitted_paths", "assumptions", "risks", "open_questions"):
        artifact.pop(name)

    parsed = parse_diff_proposal_artifact(_text(artifact))

    assert parsed.changes[0].risks == []
    assert parsed.omitted_paths == []
    assert parsed.assumptions == []
    assert parsed.risks == []
    assert parsed.open_questions == []


def test_parser_accepts_surrounding_whitespace():
    text = "\n\n\t  " + _text(_artifact(changes=[_change()])) + "  \n\t\n"

    parsed = parse_diff_proposal_artifact(text)

    assert parsed.approved_plan.issue_number == ISSUE_NUMBER


def test_error_types_share_one_base():
    assert issubclass(DiffProposalParseError, DiffProposalError)
    assert issubclass(DiffProposalValidationError, DiffProposalError)
    assert issubclass(DiffProposalError, Exception)


def test_constants_are_the_phase_5e2_values():
    assert DIFF_PROPOSAL_SCHEMA_VERSION == "diff-proposal.v1"
    assert DIFF_PROPOSAL_MODE == "proposal-only"


# -- 2. schema_version, mode, and the did/did-not-happen flags -----------------


@pytest.mark.parametrize(
    "schema_version",
    [
        "diff-proposal.v2",
        "diff-proposal.v1 ",
        "DIFF-PROPOSAL.V1",
        "diff-proposal",
        "patch-proposal.v1",
        "",
        None,
        1,
    ],
)
def test_schema_version_must_match_exactly(schema_version):
    artifact = _artifact()
    artifact["schema_version"] = schema_version

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "mode",
    ["apply", "proposal", "proposal-only ", "PROPOSAL-ONLY", "", None, True],
)
def test_mode_must_match_exactly(mode):
    artifact = _artifact()
    artifact["mode"] = mode

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("missing", ["schema_version", "mode"])
def test_schema_version_and_mode_have_no_defaults(missing):
    artifact = _artifact()
    artifact.pop(missing)

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "flag", ["files_edited", "commands_run", "applies_cleanly_checked"]
)
def test_did_not_happen_flags_true_rejected(flag):
    artifact = _artifact()
    artifact[flag] = True

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert flag in str(excinfo.value)


@pytest.mark.parametrize("value", [False, None, "true", 0])
def test_diffs_generated_must_be_true(value):
    artifact = _artifact()
    artifact["diffs_generated"] = value

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "diffs_generated" in str(excinfo.value)


@pytest.mark.parametrize("requires_human_review", [False, None, "true", 0])
def test_artifact_requires_human_review_must_be_true(requires_human_review):
    artifact = _artifact()
    artifact["requires_human_review"] = requires_human_review

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "flag",
    [
        "source_contents_read",
        "diffs_generated",
        "files_edited",
        "commands_run",
        "applies_cleanly_checked",
        "requires_human_review",
    ],
)
def test_flags_have_no_defaults(flag):
    artifact = _artifact()
    artifact.pop(flag)

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("claim", [True, False])
def test_source_contents_read_is_a_recorded_claim_either_way(claim, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the diff proposal parser read something")

    monkeypatch.setattr(builtins, "open", boom)
    monkeypatch.setattr(os, "stat", boom)

    artifact = _artifact(changes=[_change()])
    artifact["source_contents_read"] = claim

    parsed = parse_diff_proposal_artifact(_text(artifact))

    # The producer's claim is recorded. The parser reads nothing either way.
    assert parsed.source_contents_read is claim


def test_missing_next_authorization_required_rejected():
    artifact = _artifact()
    artifact.pop("next_authorization_required")

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "next_authorization_required" in str(excinfo.value)


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_blank_next_authorization_required_rejected(value):
    artifact = _artifact()
    artifact["next_authorization_required"] = value

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("field", ["assumptions", "risks", "open_questions"])
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_artifact_list_entries_rejected(field, value):
    artifact = _artifact()
    artifact[field] = [value]

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


# -- 3. Provenance identity must match the approved plan ----------------------


def test_provenance_project_id_must_match_approved_plan():
    artifact = _artifact()
    artifact["provenance"]["project_id"] = "other_project"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "project_id" in str(excinfo.value)


def test_provenance_repo_must_match_approved_plan():
    artifact = _artifact()
    artifact["provenance"]["repo"] = "acme/other"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "repo" in str(excinfo.value)


def test_provenance_issue_number_must_match_approved_plan():
    artifact = _artifact()
    artifact["provenance"]["issue_number"] = 41

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "issue_number" in str(excinfo.value)


def test_provenance_title_must_match_approved_plan_title():
    artifact = _artifact()
    artifact["provenance"]["title"] = "A different title"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "title" in str(excinfo.value)


def test_identity_matching_is_exact_not_normalized():
    artifact = _artifact()
    artifact["provenance"]["project_id"] = PROJECT_ID.upper()

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "field",
    ["engine", "operation", "real_call", "project_id", "repo", "issue_number", "title"],
)
def test_provenance_required_fields(field):
    artifact = _artifact()
    artifact["provenance"].pop(field)

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("field", ["project_id", "title"])
def test_provenance_blank_required_strings_rejected(field):
    artifact = _artifact()
    artifact["provenance"][field] = "   "

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("repo", ["widgets", "acme/", "/widgets", "a/b/c", "   "])
def test_provenance_repo_must_look_like_owner_repo(repo):
    artifact = _artifact()
    artifact["provenance"]["repo"] = repo

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("issue_number", [0, -1])
def test_provenance_issue_number_must_be_positive(issue_number):
    artifact = _artifact()
    artifact["provenance"]["issue_number"] = issue_number

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "operation", ["patch-proposal", "generate-model-plan", "apply", "", None]
)
def test_provenance_operation_must_be_diff_proposal(operation):
    artifact = _artifact()
    artifact["provenance"]["operation"] = operation

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("endpoint_host", "fake-litellm.invalid:8000"),
        ("base_url", "http://fake-litellm.invalid/v1"),
        ("api_key", "fake-key-not-a-real-secret"),
        ("prompt", "you are an implementer"),
        ("completion", '{"changes": []}'),
        ("messages", [{"role": "user", "content": "hi"}]),
        ("raw_response", '{"choices": []}'),
        ("workspace_path", "C:\\dev\\some_project"),
    ],
)
def test_provenance_rejects_secret_payload_and_workspace_fields(name, value):
    artifact = _artifact()
    artifact["provenance"][name] = value

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    # The rejection names the field but never echoes what it held.
    assert str(value) not in str(excinfo.value)


def test_provenance_extra_fields_rejected():
    artifact = _artifact()
    artifact["provenance"]["temperature"] = 0.2

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


# -- 4. Engine claims must be self-consistent, and still call nothing ----------


@pytest.mark.parametrize("engine", ["deterministic", "manual"])
def test_non_model_engines_accept_no_model_and_no_real_call(engine):
    artifact = _artifact()
    artifact["provenance"]["engine"] = engine

    parsed = parse_diff_proposal_artifact(_text(artifact))

    assert parsed.provenance.engine == engine
    assert parsed.provenance.model is None
    assert parsed.provenance.real_call is False


@pytest.mark.parametrize("engine", ["deterministic", "manual"])
def test_non_model_engine_with_a_model_name_rejected(engine):
    artifact = _artifact()
    artifact["provenance"]["engine"] = engine
    artifact["provenance"]["model"] = "fake-implementer-model"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "model" in str(excinfo.value)


@pytest.mark.parametrize("engine", ["deterministic", "manual"])
def test_non_model_engine_with_real_call_true_rejected(engine):
    artifact = _artifact()
    artifact["provenance"]["engine"] = engine
    artifact["provenance"]["real_call"] = True

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "real_call" in str(excinfo.value)


def test_model_engine_requires_a_model_name():
    artifact = _artifact()
    artifact["provenance"]["engine"] = "model"
    artifact["provenance"]["model"] = None

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "model" in str(excinfo.value)


@pytest.mark.parametrize("model", ["", "   "])
def test_model_engine_rejects_blank_model_name(model):
    artifact = _artifact()
    artifact["provenance"]["engine"] = "model"
    artifact["provenance"]["model"] = model

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_model_engine_parses_without_calling_any_model(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the diff proposal parser reached the network")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    monkeypatch.setattr(os, "getenv", boom)
    monkeypatch.setattr(os.environ, "get", boom)

    artifact = _artifact(changes=[_change()])
    artifact["provenance"]["engine"] = "model"
    artifact["provenance"]["model"] = "fake-implementer-model"
    artifact["provenance"]["real_call"] = True

    parsed = parse_diff_proposal_artifact(_text(artifact))

    # `engine: "model"` is a recorded claim about something that happened
    # elsewhere. Parsing it — diff and all — calls nothing.
    assert parsed.provenance.engine == "model"
    assert parsed.provenance.model == "fake-implementer-model"


@pytest.mark.parametrize("engine", ["real-model", "fake", "MODEL", "", None])
def test_unknown_engine_rejected(engine):
    artifact = _artifact()
    artifact["provenance"]["engine"] = engine

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_generated_at_is_parsed_when_present():
    parsed = parse_diff_proposal_artifact(_text(_artifact()))

    assert parsed.provenance.generated_at == datetime(
        2026, 1, 3, 5, 6, 7, tzinfo=timezone.utc
    )


def test_generated_at_is_never_produced_by_the_code():
    artifact = _artifact()
    artifact["provenance"].pop("generated_at")

    parsed = parse_diff_proposal_artifact(_text(artifact))

    assert parsed.provenance.generated_at is None
    assert parsed.model_dump()["provenance"]["generated_at"] is None


def test_module_has_no_clock_call():
    from ai_dev_orchestrator.diff_proposal import models as diff_models

    with open(diff_models.__file__, encoding="utf-8") as handle:
        text = handle.read()

    for forbidden in ("datetime.now", "datetime.utcnow", "time.time", "date.today"):
        assert forbidden not in text


# -- 5. Scope containment: a proposal may narrow, never widen -------------------


@pytest.mark.parametrize("path", [ALLOWED_PATH, ALLOWED_TEST_PATH])
def test_change_path_from_files_likely_to_change_is_accepted(path):
    parsed = parse_diff_proposal_artifact(_text(_artifact(changes=[_change(path)])))

    assert parsed.changes[0].path == path


@pytest.mark.parametrize(
    "path",
    [
        "src/billing/other.py",
        "src/billing/format.pyc",
        "SRC/BILLING/FORMAT.PY",
        "docs/README.md",
    ],
)
def test_change_path_outside_files_likely_to_change_rejected(path):
    artifact = _artifact(changes=[_change(path)])

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_change_path_in_forbidden_list_rejected():
    artifact = _artifact(changes=[_change(FORBIDDEN_PATH)])

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "forbidden" in str(excinfo.value)


def test_forbidden_wins_even_when_the_plan_lists_a_path_twice():
    # A plan that contradicts itself must not be resolved in the permissive
    # direction: forbidden is checked first and refuses the path.
    artifact = _artifact(changes=[_change(FORBIDDEN_PATH)])
    artifact["approved_plan"]["plan"]["files_likely_to_change"] = [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
        FORBIDDEN_PATH,
    ]

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "forbidden" in str(excinfo.value)


def test_duplicate_change_paths_rejected():
    # Deliberate decision: duplicates are rejected, not merged or concatenated.
    # Two diffs for one file have no defined precedence, and keeping one
    # silently would hide a change from the human reading this.
    artifact = _artifact(changes=[_change(ALLOWED_PATH), _change(ALLOWED_PATH)])

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "duplicate" in str(excinfo.value).lower()


def test_missing_approved_plan_rejected():
    artifact = _artifact()
    artifact.pop("approved_plan")

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_approved_plan_without_approval_rejected():
    artifact = _artifact()
    artifact["approved_plan"].pop("approval")

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_approved_plan_with_paraphrased_approval_rejected():
    artifact = _artifact()
    artifact["approved_plan"]["approval"]["approval_text"] = "looks fine to me"

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("automation_level", ["L2", "l1", "L3", ""])
def test_approved_plan_automation_level_must_be_l1(automation_level):
    artifact = _artifact()
    artifact["approved_plan"]["plan"]["automation_level"] = automation_level

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "automation_level" in str(excinfo.value)


def test_approved_plan_requires_human_approval_false_rejected():
    artifact = _artifact()
    artifact["approved_plan"]["plan"]["requires_human_approval"] = False

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "requires_human_approval" in str(excinfo.value)


def test_forged_approval_inside_the_wrapped_plan_rejected():
    artifact = _artifact()
    artifact["approved_plan"]["plan"]["approval"] = copy.deepcopy(VALID_APPROVAL)

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


# -- 6. The optional patch proposal snapshot must agree ------------------------


def test_patch_proposal_with_a_different_approved_plan_rejected():
    proposal = _patch_proposal()
    proposal["approved_plan"]["plan"]["summary"] = "A different summary."
    artifact = _artifact(changes=[_change(ALLOWED_PATH)], patch_proposal=proposal)

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "approved_plan" in str(excinfo.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "other_project"),
        ("repo", "acme/other"),
        ("issue_number", 41),
        ("title", "A different title"),
    ],
)
def test_patch_proposal_identity_mismatch_rejected(field, value):
    proposal = _patch_proposal()
    proposal["provenance"][field] = value
    artifact = _artifact(changes=[_change(ALLOWED_PATH)], patch_proposal=proposal)

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert field in str(excinfo.value)


def test_diff_for_a_path_the_patch_proposal_did_not_name_rejected():
    # The prose proposal named only ALLOWED_PATH; a diff for the other approved
    # path is still refused, because the two artifacts must describe one plan.
    proposal = _patch_proposal(changes=[_patch_proposal_change(ALLOWED_PATH)])
    artifact = _artifact(
        changes=[_change(ALLOWED_TEST_PATH, "create")], patch_proposal=proposal
    )

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "patch_proposal" in str(excinfo.value)


def test_diff_subset_of_patch_proposal_paths_accepted():
    proposal = _patch_proposal(
        changes=[
            _patch_proposal_change(ALLOWED_PATH),
            _patch_proposal_change(ALLOWED_TEST_PATH),
        ]
    )
    artifact = _artifact(changes=[_change(ALLOWED_PATH)], patch_proposal=proposal)

    parsed = parse_diff_proposal_artifact(_text(artifact))

    assert [change.path for change in parsed.changes] == [ALLOWED_PATH]


def test_malformed_patch_proposal_snapshot_rejected():
    proposal = _patch_proposal()
    proposal["mode"] = "apply"
    artifact = _artifact(changes=[_change(ALLOWED_PATH)], patch_proposal=proposal)

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_patch_proposal_extra_fields_rejected():
    proposal = _patch_proposal()
    proposal["auto_apply"] = True
    artifact = _artifact(changes=[_change(ALLOWED_PATH)], patch_proposal=proposal)

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


# -- 7. Path safety, lexically, on every path string ---------------------------


UNSAFE_PATHS = [
    "",
    "   ",
    "/etc/passwd",
    "\\windows\\system32\\config",
    "C:/dev/some_project/src/format.py",
    "C:\\dev\\some_project\\src\\format.py",
    "src:stream",
    "../../etc/passwd",
    "src/../../format.py",
    "src/billing/../format.py",
    "..",
    "\\\\server\\share\\format.py",
    "//server/share/format.py",
    "\\\\?\\C:\\dev\\some_project\\format.py",
    "\\\\.\\PhysicalDrive0",
    "src/billing/format.py.",
    "src/billing./format.py",
    "src/billing/format.py ",
    "src/billing /format.py",
    "src/PROGRA~1/format.py",
    "src/LONGFI~1.TXT",
    ".",
    "./src/billing/format.py",
    "src//billing/format.py",
]


@pytest.mark.parametrize("path", UNSAFE_PATHS)
def test_unsafe_change_paths_rejected(path):
    # Every one of these is refused as a *string*. Nothing is joined to a
    # workspace root, canonicalized, stat'd, or read to decide this — and the
    # diff headers naming the same unsafe path do not rescue it.
    artifact = _artifact(changes=[_change(path)])
    # Even if the plan itself listed the unsafe path, the change is still
    # refused: path safety is checked before scope containment.
    artifact["approved_plan"]["plan"]["files_likely_to_change"] = [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
        path,
    ]

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("path", UNSAFE_PATHS)
def test_unsafe_omitted_paths_rejected(path):
    artifact = _artifact()
    artifact["omitted_paths"] = [path]

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_omitted_paths_accept_safe_relative_paths():
    artifact = _artifact()
    artifact["omitted_paths"] = [ALLOWED_PATH, ALLOWED_TEST_PATH]

    parsed = parse_diff_proposal_artifact(_text(artifact))

    assert parsed.omitted_paths == [ALLOWED_PATH, ALLOWED_TEST_PATH]


def test_missing_change_path_rejected():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0].pop("path")

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_workspace_like_plan_paths_are_never_resolved():
    artifact = _artifact()
    # Workspace-shaped strings inside the wrapped plan stay plain strings:
    # nothing here resolves, stats, globs, or normalizes them.
    artifact["approved_plan"]["plan"]["files_likely_to_change"] = [
        "C:\\dev\\some_project\\src\\billing\\format.py",
        "../../etc/passwd",
    ]
    artifact["omitted_paths"] = []

    parsed = parse_diff_proposal_artifact(_text(artifact))

    assert parsed.approved_plan.plan.files_likely_to_change == [
        "C:\\dev\\some_project\\src\\billing\\format.py",
        "../../etc/passwd",
    ]
    # And they remain unusable as change paths: a proposal cannot reach them.
    assert parsed.changes == []


# -- 8. Change field validation ------------------------------------------------


@pytest.mark.parametrize(
    "change_type", ["delete", "rename", "apply", "MODIFY", "", None]
)
def test_unknown_change_type_rejected(change_type):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["change_type"] = change_type

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("rationale", ["", "   ", "\t\n"])
def test_blank_rationale_rejected(rationale):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["rationale"] = rationale

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_missing_rationale_rejected():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0].pop("rationale")

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("risk", ["", "   "])
def test_blank_change_risk_rejected(risk):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["risks"] = [risk]

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("requires_human_review", [False, None, "true", 0])
def test_change_requires_human_review_must_be_true(requires_human_review):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["requires_human_review"] = requires_human_review

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_change_requires_human_review_has_no_default():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0].pop("requires_human_review")

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_missing_unified_diff_rejected():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0].pop("unified_diff")

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert "unified_diff" in str(excinfo.value)


# -- 9. Unified diff shape validation -----------------------------------------


def _with_diff(diff: str, path: str = ALLOWED_PATH, change_type: str = "modify") -> dict:
    artifact = _artifact(changes=[_change(path, change_type)])
    artifact["changes"][0]["unified_diff"] = diff
    return artifact


@pytest.mark.parametrize("diff", ["", "   ", "\n\t "])
def test_blank_unified_diff_rejected(diff):
    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(_with_diff(diff)))


def test_modify_diff_header_must_name_the_change_path():
    diff = (
        f"--- a/{ALLOWED_TEST_PATH}\n"
        f"+++ b/{ALLOWED_TEST_PATH}\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert "unified_diff" in str(excinfo.value)


def test_modify_diff_with_a_dev_null_source_header_rejected():
    diff = f"--- /dev/null\n+++ b/{ALLOWED_PATH}\n@@ -0,0 +1 @@\n+new\n"

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(_with_diff(diff)))


def test_create_diff_must_use_dev_null_as_its_source_header():
    diff = (
        f"--- a/{ALLOWED_TEST_PATH}\n"
        f"+++ b/{ALLOWED_TEST_PATH}\n"
        "@@ -0,0 +1 @@\n"
        "+new\n"
    )
    artifact = _with_diff(diff, ALLOWED_TEST_PATH, "create")

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_create_diff_target_header_must_name_the_change_path():
    diff = f"--- /dev/null\n+++ b/{ALLOWED_PATH}\n@@ -0,0 +1 @@\n+new\n"
    artifact = _with_diff(diff, ALLOWED_TEST_PATH, "create")

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "diff",
    [
        # No 'a/' prefix.
        f"--- {ALLOWED_PATH}\n+++ b/{ALLOWED_PATH}\n@@ -1 +1 @@\n-old\n+new\n",
        # A timestamp suffix — common in `diff -u` output, not accepted here.
        f"--- a/{ALLOWED_PATH}\t2026-01-01\n+++ b/{ALLOWED_PATH}\n"
        "@@ -1 +1 @@\n-old\n+new\n",
        # An absolute path in the header.
        "--- a/C:/dev/some_project/src/billing/format.py\n"
        f"+++ b/{ALLOWED_PATH}\n@@ -1 +1 @@\n-old\n+new\n",
        # Parent traversal in the header.
        f"--- a/../../{ALLOWED_PATH}\n+++ b/{ALLOWED_PATH}\n"
        "@@ -1 +1 @@\n-old\n+new\n",
    ],
)
def test_unsafe_or_mismatched_source_headers_rejected(diff):
    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(_with_diff(diff)))


@pytest.mark.parametrize(
    "diff",
    [
        f"--- a/{ALLOWED_PATH}\n+++ {ALLOWED_PATH}\n@@ -1 +1 @@\n-old\n+new\n",
        f"--- a/{ALLOWED_PATH}\n+++ b/../../{ALLOWED_PATH}\n"
        "@@ -1 +1 @@\n-old\n+new\n",
        f"--- a/{ALLOWED_PATH}\n+++ b/{ALLOWED_TEST_PATH}\n"
        "@@ -1 +1 @@\n-old\n+new\n",
    ],
)
def test_unsafe_or_mismatched_target_headers_rejected(diff):
    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(_with_diff(diff)))


def test_missing_source_header_rejected():
    diff = f"+++ b/{ALLOWED_PATH}\n@@ -1 +1 @@\n-old\n+new\n"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert "'---'" in str(excinfo.value)


def test_missing_target_header_rejected():
    diff = f"--- a/{ALLOWED_PATH}\n@@ -1 +1 @@\n-old\n+new\n"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert "'+++'" in str(excinfo.value)


def test_headers_in_the_wrong_order_rejected():
    diff = f"+++ b/{ALLOWED_PATH}\n--- a/{ALLOWED_PATH}\n@@ -1 +1 @@\n-old\n+new\n"

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(_with_diff(diff)))


def test_missing_hunk_header_rejected():
    diff = f"--- a/{ALLOWED_PATH}\n+++ b/{ALLOWED_PATH}\n-old\n+new\n"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert "@@" in str(excinfo.value)


def test_hunk_header_before_the_file_headers_rejected():
    diff = f"@@ -1 +1 @@\n--- a/{ALLOWED_PATH}\n+++ b/{ALLOWED_PATH}\n-old\n+new\n"

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(_with_diff(diff)))


def test_multi_file_patch_rejected():
    diff = _modify_diff(ALLOWED_PATH) + _modify_diff(ALLOWED_TEST_PATH)

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert "single-file" in str(excinfo.value)


def test_git_patch_envelope_rejected():
    # Phase 5E2 accepts only the bare `---`/`+++`/`@@` form. `diff --git` is the
    # envelope that carries renames, modes, and multi-file patches, so it is
    # refused outright rather than partially understood.
    diff = (
        f"diff --git a/{ALLOWED_PATH} b/{ALLOWED_PATH}\n"
        "index 1111111..2222222 100644\n" + _modify_diff(ALLOWED_PATH)
    )

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert "diff --git" in str(excinfo.value)


@pytest.mark.parametrize(
    "marker",
    [
        "GIT binary patch",
        "Binary files ",
        "rename from ",
        "rename to ",
        "delete file mode",
        "old mode ",
        "new mode ",
        "similarity index ",
    ],
)
def test_binary_rename_delete_and_mode_metadata_rejected(marker):
    diff = _modify_diff(ALLOWED_PATH) + marker + "100644\n"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert marker.strip() in str(excinfo.value)


def test_diff_containing_a_nul_rejected():
    diff = _modify_diff(ALLOWED_PATH) + "+\x00\n"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert "NUL" in str(excinfo.value)


def test_over_long_diff_rejected():
    from ai_dev_orchestrator.diff_proposal.models import MAX_UNIFIED_DIFF_CHARS

    body = "+padding\n" * ((MAX_UNIFIED_DIFF_CHARS // 9) + 1)
    diff = _modify_diff(ALLOWED_PATH) + body
    assert len(diff) > MAX_UNIFIED_DIFF_CHARS

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    message = str(excinfo.value)
    assert "unified_diff" in message
    # The oversized payload is never echoed back.
    assert "padding" not in message


def test_a_long_but_permitted_diff_is_accepted():
    from ai_dev_orchestrator.diff_proposal.models import MAX_UNIFIED_DIFF_CHARS

    diff = _modify_diff(ALLOWED_PATH)
    diff += "+padding\n" * ((MAX_UNIFIED_DIFF_CHARS - len(diff)) // 9)
    assert len(diff) <= MAX_UNIFIED_DIFF_CHARS

    parsed = parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert parsed.changes[0].unified_diff == diff


def test_line_endings_inside_a_diff_are_not_normalized():
    diff = f"--- a/{ALLOWED_PATH}\n+++ b/{ALLOWED_PATH}\n@@ -1 +1 @@\r\n-old\r\n+new\r\n"

    parsed = parse_diff_proposal_artifact(_text(_with_diff(diff)))

    # Carried through byte for byte. Nothing rewrites, trims, or re-wraps it.
    assert parsed.changes[0].unified_diff == diff


def test_source_lines_inside_a_diff_are_carried_verbatim():
    diff = (
        f"--- a/{ALLOWED_PATH}\n"
        f"+++ b/{ALLOWED_PATH}\n"
        "@@ -1,2 +1,2 @@\n"
        " def format_total(amount, locale):\n"
        '-    return str(amount)\n'
        '+    return locale.currency(amount)\n'
    )

    parsed = parse_diff_proposal_artifact(_text(_with_diff(diff)))

    # Diff context is source text, and it is allowed *as data here*. The parser
    # did not read a file to get it and does not send it anywhere.
    assert parsed.changes[0].unified_diff == diff


def test_no_apply_check_is_performed(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the diff proposal parser tried to apply a patch")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(builtins, "open", boom)

    # A diff whose hunk counts are arithmetically nonsense and whose context
    # matches nothing real still parses: apply-cleanliness is never checked.
    diff = (
        f"--- a/{ALLOWED_PATH}\n"
        f"+++ b/{ALLOWED_PATH}\n"
        "@@ -900,7 +900,9 @@\n"
        " context that does not exist anywhere\n"
        "+added\n"
    )

    parsed = parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert parsed.applies_cleanly_checked is False
    assert parsed.changes[0].unified_diff == diff


# -- 10. No forbidden payload fields ------------------------------------------


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("raw_artifact_text", "{...}"),
        ("source_contents", {ALLOWED_PATH: "def format_total(): ..."}),
        ("file_contents", {ALLOWED_PATH: "def format_total(): ..."}),
        ("before_content", "old source"),
        ("after_content", "new source"),
        ("command", "pytest -q"),
        ("commands", ["pytest -q"]),
        ("command_output", "2 passed"),
        ("prompt", "you are an implementer"),
        ("completion", '{"changes": []}'),
        ("api_key", "fake-key-not-a-real-secret"),
        ("base_url", "http://fake-litellm.invalid/v1"),
        ("workspace_path", "C:\\dev\\some_project"),
        ("approval", VALID_APPROVAL),
        ("apply", True),
        ("auto_apply", True),
    ],
)
def test_artifact_rejects_content_command_secret_and_apply_fields(name, value):
    artifact = _artifact()
    artifact[name] = value

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert str(value) not in str(excinfo.value)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("before_content", "old source"),
        ("after_content", "new source"),
        ("content", "def format_total(): ..."),
        ("command", "pytest -q"),
        ("command_output", "2 passed"),
        ("apply", True),
        ("auto_apply", True),
        ("workspace_path", "C:\\dev\\some_project"),
    ],
)
def test_change_rejects_content_command_and_apply_fields(name, value):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0][name] = value

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert str(value) not in str(excinfo.value)


def test_no_content_command_or_apply_field_exists_on_the_change_model():
    for absent in (
        "before_content",
        "after_content",
        "content",
        "file_contents",
        "command",
        "commands",
        "command_output",
        "apply",
        "auto_apply",
        "workspace_path",
    ):
        assert absent not in DiffProposalFileChange.model_fields

    # The one payload field that *does* exist, and the only place source text
    # may live in this artifact.
    assert "unified_diff" in DiffProposalFileChange.model_fields


def test_no_payload_field_exists_on_the_artifact_model():
    for absent in (
        "raw_artifact_text",
        "source_contents",
        "file_contents",
        "before_content",
        "after_content",
        "command",
        "commands",
        "command_output",
        "prompt",
        "completion",
        "api_key",
        "base_url",
        "workspace_path",
        "approval",
        "apply",
        "auto_apply",
    ):
        assert absent not in DiffProposalArtifact.model_fields


def test_top_level_extra_fields_rejected():
    artifact = _artifact()
    artifact["auto_approved"] = True

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_approved_plan_extra_fields_rejected():
    artifact = _artifact()
    artifact["approved_plan"]["auto_approved"] = True

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


# -- 11. Strict parser surface -------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "\n\t  \n"])
def test_parser_rejects_empty_text(text):
    with pytest.raises(DiffProposalParseError):
        parse_diff_proposal_artifact(text)


@pytest.mark.parametrize(
    "text",
    ["{", "{not json}", '{"changes": }', '{"a": 1,}', "{'changes': []}"],
)
def test_parser_rejects_invalid_json(text):
    with pytest.raises(DiffProposalParseError):
        parse_diff_proposal_artifact(text)


def test_parser_rejects_markdown_fenced_json():
    text = "```json\n" + _text(_artifact()) + "\n```"

    with pytest.raises(DiffProposalParseError):
        parse_diff_proposal_artifact(text)


def test_parser_rejects_a_fenced_diff_block():
    text = "```diff\n" + _modify_diff() + "\n```"

    with pytest.raises(DiffProposalParseError):
        parse_diff_proposal_artifact(text)


def test_parser_rejects_prose_before_json():
    text = "Here is the diff proposal:\n" + _text(_artifact())

    with pytest.raises(DiffProposalParseError):
        parse_diff_proposal_artifact(text)


def test_parser_rejects_prose_after_json():
    text = _text(_artifact()) + "\nApply this with `git apply`."

    with pytest.raises(DiffProposalParseError):
        parse_diff_proposal_artifact(text)


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        '[{"changes": []}]',
        '"diff-proposal.v1"',
        "42",
        "3.14",
        "true",
        "false",
        "null",
    ],
)
def test_parser_rejects_non_object_json(text):
    with pytest.raises(DiffProposalParseError):
        parse_diff_proposal_artifact(text)


def test_parser_rejects_non_string_input():
    with pytest.raises(DiffProposalParseError):
        parse_diff_proposal_artifact(None)  # type: ignore[arg-type]


def test_parser_never_repairs_and_never_strips_unknown_fields():
    artifact = _artifact()
    artifact["provenance"]["unknown_field"] = "x"
    artifact.pop("mode")

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(artifact))


def test_parser_wraps_pydantic_validation_error():
    artifact = _artifact()
    artifact["mode"] = "apply"

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    assert isinstance(excinfo.value.__cause__, ValidationError)
    assert not isinstance(excinfo.value, ValidationError)


def test_validation_error_message_does_not_echo_the_artifact_or_the_diff():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["rationale"] = ""

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(artifact))

    message = str(excinfo.value)
    assert "rationale" in message
    assert "format_total" not in message
    assert VALID_PLAN["summary"] not in message
    assert NEXT_AUTHORIZATION not in message


def test_diff_rejection_message_does_not_echo_the_diff():
    diff = (
        f"--- a/{ALLOWED_PATH}\n"
        f"+++ b/{ALLOWED_PATH}\n"
        "-secret_token = 'not-a-real-secret'\n"
    )

    with pytest.raises(DiffProposalValidationError) as excinfo:
        parse_diff_proposal_artifact(_text(_with_diff(diff)))

    assert "secret_token" not in str(excinfo.value)


def test_parser_is_deterministic():
    text = _text(_artifact(changes=[_change()]))

    first = parse_diff_proposal_artifact(text)
    second = parse_diff_proposal_artifact(text)

    assert first.model_dump() == second.model_dump()


def test_parser_prints_nothing(capsys):
    parse_diff_proposal_artifact(_text(_artifact(changes=[_change()])))

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# -- 12. The parser performs no IO of any kind ---------------------------------


def test_parser_performs_no_file_network_process_env_or_workspace_io(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the diff proposal parser performed IO")

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

    parsed = parse_diff_proposal_artifact(
        _text(
            _artifact(
                changes=[_change(ALLOWED_PATH), _change(ALLOWED_TEST_PATH, "create")],
                patch_proposal=_patch_proposal(
                    changes=[
                        _patch_proposal_change(ALLOWED_PATH),
                        _patch_proposal_change(ALLOWED_TEST_PATH),
                    ]
                ),
            )
        )
    )

    assert [change.path for change in parsed.changes] == [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
    ]


def test_parser_failure_paths_also_perform_no_io(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the diff proposal parser performed IO")

    monkeypatch.setattr(builtins, "open", boom)
    monkeypatch.setattr(os, "getenv", boom)
    monkeypatch.setattr(os.environ, "get", boom)
    monkeypatch.setattr(os, "stat", boom)
    monkeypatch.setattr(os.path, "realpath", boom)
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)

    # An absolute, workspace-shaped path is refused lexically — never resolved.
    unsafe = _artifact(changes=[_change("C:\\dev\\some_project\\src\\format.py")])

    with pytest.raises(DiffProposalValidationError):
        parse_diff_proposal_artifact(_text(unsafe))
    with pytest.raises(DiffProposalParseError):
        parse_diff_proposal_artifact("not json at all")


def test_parser_writes_no_files(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())

    parse_diff_proposal_artifact(_text(_artifact(changes=[_change()])))

    assert sorted(p.name for p in tmp_path.iterdir()) == before


# -- 13. The implementation module cannot reach a model, a socket, or GitHub ---


def test_implementation_module_globals_are_inert():
    from ai_dev_orchestrator.diff_proposal import models as diff_models

    module_globals = vars(diff_models)
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
    from ai_dev_orchestrator.diff_proposal import models as diff_models

    with open(diff_models.__file__, encoding="utf-8") as handle:
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


def test_diff_proposal_package_exports_exactly_the_phase_5e2_surface():
    from ai_dev_orchestrator import diff_proposal

    expected = [
        "DIFF_PROPOSAL_MODE",
        "DIFF_PROPOSAL_SCHEMA_VERSION",
        "DiffProposalArtifact",
        "DiffProposalError",
        "DiffProposalFileChange",
        "DiffProposalParseError",
        "DiffProposalProvenance",
        "DiffProposalValidationError",
        "parse_diff_proposal_artifact",
    ]
    assert sorted(diff_proposal.__all__) == sorted(expected)
    for name in expected:
        assert hasattr(diff_proposal, name)

    # No generator, no applier, no loader, no writer. Later phases, if ever.
    for absent in (
        "build_diff_proposal",
        "generate_diff",
        "generate_unified_diff",
        "load_diff_proposal_artifact",
        "apply_diff_proposal",
        "write_diff_proposal",
        "DiffGenerator",
        "PatchApplier",
        "L2Implementer",
    ):
        assert not hasattr(diff_proposal, absent)


def test_importing_the_package_touches_nothing(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("importing diff_proposal performed IO")

    monkeypatch.setattr(os, "getenv", boom)
    monkeypatch.setattr(os.environ, "get", boom)
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)

    import importlib

    import ai_dev_orchestrator.diff_proposal as diff_proposal

    importlib.reload(diff_proposal)

    assert diff_proposal.DIFF_PROPOSAL_MODE == "proposal-only"


# -- 14. The CLI surface -------------------------------------------------------


# Phase 5E2 adds no command and no option. This is the Phase 5D2 surface,
# unchanged.
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


def test_importing_diff_proposal_adds_no_command():
    import ai_dev_orchestrator.diff_proposal  # noqa: F401

    registered = [
        info.name or info.callback.__name__.replace("_", "-")
        for info in app.registered_commands
    ]
    assert registered == EXPECTED_COMMANDS


def test_no_diff_apply_or_implement_command_exists():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for absent in (
        "generate-diff",
        "generate-diff-proposal",
        "propose-diff",
        "apply-diff",
        "apply-patch",
        "approve-plan",
        "implement",
    ):
        assert absent not in result.output

    for absent in (
        "generate-diff",
        "generate-diff-proposal",
        "propose-diff",
        "apply-diff",
        "apply-patch",
        "apply-patch-proposal",
        "implement-plan",
    ):
        assert runner.invoke(app, [absent, "--help"]).exit_code != 0


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
        "--diff",
        "--unified-diff",
        "--diff-proposal",
        "--propose-diff",
        "--generate-diff",
        "--apply-patch",
        "--edit-files",
        "--run-commands",
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
        "--diff",
        "--unified-diff",
        "--diff-proposal",
        "--with-diff",
        "--apply-patch",
        "--inspect-workspace",
        "--read-contents",
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
    for absent in ("--diff", "--diff-proposal", "--apply-patch", "--edit-files"):
        assert absent not in result.output


def test_l2_dry_run_options_unchanged():
    result = runner.invoke(app, ["l2-dry-run", "--help"])

    assert result.exit_code == 0
    for present in ("--project-config", "--approved-plan", "--format"):
        assert present in result.output
    for absent in ("--diff", "--diff-proposal", "--apply-patch", "--edit-files"):
        assert absent not in result.output


@pytest.mark.parametrize("command", ["generate-plan", "generate-model-plan"])
def test_plan_commands_gain_no_diff_option(command):
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0
    for absent in ("--diff", "--diff-proposal", "--apply-patch", "--implement"):
        assert absent not in result.output
