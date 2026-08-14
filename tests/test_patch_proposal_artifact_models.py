"""Phase 5E0 tests: typed patch proposal artifact models and the strict parser.

Everything here is a **literal JSON string** or a literal dict. No artifact is
read from disk, no environment variable is read, no socket is opened, no command
is run, no patch is generated, no file is edited, and no target project
workspace is read, listed, stat'd, or resolved. No path below names a real
project.

The parser under test is pure, so the IO tests below assert that directly:
``builtins.open``, the ``os`` environment/filesystem entry points, ``socket``,
and ``subprocess.Popen`` are all replaced with detonators for the duration of a
successful parse.
"""

from __future__ import annotations

import builtins
import copy
import inspect
import json
import os
import socket
import subprocess
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.handoff import (
    REQUIRED_APPROVAL_TEXT,
    ApprovedL1PlanArtifact,
)
from ai_dev_orchestrator.patch_proposal import (
    PATCH_PROPOSAL_MODE,
    PATCH_PROPOSAL_SCHEMA_VERSION,
    PatchProposalArtifact,
    PatchProposalChange,
    PatchProposalError,
    PatchProposalParseError,
    PatchProposalProvenance,
    PatchProposalValidationError,
    parse_patch_proposal_artifact,
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
    "operation": "patch-proposal",
    "real_call": False,
    "model": None,
    "generated_at": "2026-01-03T05:06:07+00:00",
    "project_id": PROJECT_ID,
    "repo": REPO,
    "issue_number": ISSUE_NUMBER,
    "title": TITLE,
}

NEXT_AUTHORIZATION = (
    "Phase 5E1 (deterministic proposal generation) must be explicitly authorized "
    "before anything produces this artifact."
)


def _change(path: str = ALLOWED_PATH, change_type: str = "modify") -> dict:
    return {
        "path": path,
        "change_type": change_type,
        "rationale": "The shared helper belongs here, next to the existing totals code.",
        "proposed_steps": [
            "Add a format_total helper that takes an amount and a locale.",
            "Route the two existing call sites through it.",
        ],
        "risks": ["Existing call sites may round differently today."],
        "requires_human_review": True,
    }


def _artifact(changes: list[dict] | None = None) -> dict:
    """A fresh, fully valid proposal dict. Callers mutate their own copy."""
    return {
        "schema_version": PATCH_PROPOSAL_SCHEMA_VERSION,
        "mode": PATCH_PROPOSAL_MODE,
        "provenance": copy.deepcopy(VALID_PROVENANCE),
        "approved_plan": copy.deepcopy(VALID_APPROVED_PLAN),
        "changes": copy.deepcopy(changes) if changes is not None else [],
        "omitted_paths": [ALLOWED_TEST_PATH],
        "assumptions": ["The helper has no existing callers outside billing."],
        "risks": ["A human may need to reconcile historical invoices."],
        "open_questions": ["Should the helper accept a locale argument?"],
        "file_contents_read": False,
        "files_edited": False,
        "commands_run": False,
        "requires_human_review": True,
        "next_authorization_required": NEXT_AUTHORIZATION,
    }


def _text(artifact: dict) -> str:
    return json.dumps(artifact)


# -- 1. The happy path ---------------------------------------------------------


def test_valid_artifact_parses():
    parsed = parse_patch_proposal_artifact(_text(_artifact()))

    assert isinstance(parsed, PatchProposalArtifact)
    assert isinstance(parsed.provenance, PatchProposalProvenance)
    assert isinstance(parsed.approved_plan, ApprovedL1PlanArtifact)
    assert parsed.schema_version == PATCH_PROPOSAL_SCHEMA_VERSION
    assert parsed.mode == PATCH_PROPOSAL_MODE
    assert parsed.file_contents_read is False
    assert parsed.files_edited is False
    assert parsed.commands_run is False
    assert parsed.requires_human_review is True
    assert parsed.next_authorization_required == NEXT_AUTHORIZATION


def test_valid_artifact_carries_an_unchanged_approved_plan_snapshot():
    parsed = parse_patch_proposal_artifact(_text(_artifact()))

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


def test_valid_artifact_may_have_empty_changes():
    parsed = parse_patch_proposal_artifact(_text(_artifact(changes=[])))

    # "No patch proposed yet" is a well-formed statement, not a defect.
    assert parsed.changes == []


def test_valid_artifact_with_one_modify_change():
    parsed = parse_patch_proposal_artifact(
        _text(_artifact(changes=[_change(change_type="modify")]))
    )

    assert len(parsed.changes) == 1
    change = parsed.changes[0]
    assert isinstance(change, PatchProposalChange)
    assert change.path == ALLOWED_PATH
    assert change.change_type == "modify"
    assert change.requires_human_review is True
    assert len(change.proposed_steps) == 2


def test_valid_artifact_with_one_create_change():
    parsed = parse_patch_proposal_artifact(
        _text(
            _artifact(
                changes=[_change(path=ALLOWED_TEST_PATH, change_type="create")]
            )
        )
    )

    assert parsed.changes[0].change_type == "create"
    assert parsed.changes[0].path == ALLOWED_TEST_PATH


def test_valid_artifact_with_two_distinct_changes():
    parsed = parse_patch_proposal_artifact(
        _text(
            _artifact(
                changes=[
                    _change(path=ALLOWED_PATH),
                    _change(path=ALLOWED_TEST_PATH, change_type="create"),
                ]
            )
        )
    )

    assert [change.path for change in parsed.changes] == [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
    ]


def test_optional_change_and_artifact_lists_default_to_empty():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0].pop("risks")
    for name in ("omitted_paths", "assumptions", "risks", "open_questions"):
        artifact.pop(name)

    parsed = parse_patch_proposal_artifact(_text(artifact))

    assert parsed.changes[0].risks == []
    assert parsed.omitted_paths == []
    assert parsed.assumptions == []
    assert parsed.risks == []
    assert parsed.open_questions == []


def test_error_types_share_one_base():
    assert issubclass(PatchProposalParseError, PatchProposalError)
    assert issubclass(PatchProposalValidationError, PatchProposalError)
    assert issubclass(PatchProposalError, Exception)


def test_constants_are_the_phase_5e0_values():
    assert PATCH_PROPOSAL_SCHEMA_VERSION == "patch-proposal.v1"
    assert PATCH_PROPOSAL_MODE == "proposal-only"


# -- 2. schema_version and mode are exact -------------------------------------


@pytest.mark.parametrize(
    "schema_version",
    [
        "patch-proposal.v2",
        "patch-proposal.v1 ",
        "PATCH-PROPOSAL.V1",
        "patch-proposal",
        "",
        None,
        1,
    ],
)
def test_schema_version_must_match_exactly(schema_version):
    artifact = _artifact()
    artifact["schema_version"] = schema_version

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "mode",
    ["apply", "proposal", "proposal-only ", "PROPOSAL-ONLY", "", None, True],
)
def test_mode_must_match_exactly(mode):
    artifact = _artifact()
    artifact["mode"] = mode

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("missing", ["schema_version", "mode"])
def test_schema_version_and_mode_have_no_defaults(missing):
    artifact = _artifact()
    artifact.pop(missing)

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


# -- 3. Provenance identity must match the approved plan ----------------------


def test_provenance_project_id_must_match_approved_plan():
    artifact = _artifact()
    artifact["provenance"]["project_id"] = "other_project"

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "project_id" in str(excinfo.value)


def test_provenance_repo_must_match_approved_plan():
    artifact = _artifact()
    artifact["provenance"]["repo"] = "acme/other"

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "repo" in str(excinfo.value)


def test_provenance_issue_number_must_match_approved_plan():
    artifact = _artifact()
    artifact["provenance"]["issue_number"] = 41

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "issue_number" in str(excinfo.value)


def test_provenance_title_must_match_approved_plan_title():
    artifact = _artifact()
    artifact["provenance"]["title"] = "A different title"

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "title" in str(excinfo.value)


def test_identity_matching_is_exact_not_normalized():
    artifact = _artifact()
    artifact["provenance"]["project_id"] = PROJECT_ID.upper()

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize(
    "field", ["engine", "operation", "real_call", "project_id", "repo",
              "issue_number", "title"]
)
def test_provenance_required_fields(field):
    artifact = _artifact()
    artifact["provenance"].pop(field)

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("field", ["project_id", "title"])
def test_provenance_blank_required_strings_rejected(field):
    artifact = _artifact()
    artifact["provenance"][field] = "   "

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("repo", ["widgets", "acme/", "/widgets", "a/b/c", "   "])
def test_provenance_repo_must_look_like_owner_repo(repo):
    artifact = _artifact()
    artifact["provenance"]["repo"] = repo

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("issue_number", [0, -1])
def test_provenance_issue_number_must_be_positive(issue_number):
    artifact = _artifact()
    artifact["provenance"]["issue_number"] = issue_number

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("operation", ["generate-model-plan", "apply", "", None])
def test_provenance_operation_must_be_patch_proposal(operation):
    artifact = _artifact()
    artifact["provenance"]["operation"] = operation

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


# -- 4. Provenance carries no secret, payload, or workspace field --------------


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

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    # The rejection names the field but never echoes what it held.
    assert str(value) not in str(excinfo.value)


def test_provenance_extra_fields_rejected():
    artifact = _artifact()
    artifact["provenance"]["temperature"] = 0.2

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


# -- 5. Engine claims must be self-consistent ---------------------------------


@pytest.mark.parametrize("engine", ["deterministic", "manual"])
def test_non_model_engines_accept_no_model_and_no_real_call(engine):
    artifact = _artifact()
    artifact["provenance"]["engine"] = engine

    parsed = parse_patch_proposal_artifact(_text(artifact))

    assert parsed.provenance.engine == engine
    assert parsed.provenance.model is None
    assert parsed.provenance.real_call is False


@pytest.mark.parametrize("engine", ["deterministic", "manual"])
def test_non_model_engine_with_a_model_name_rejected(engine):
    artifact = _artifact()
    artifact["provenance"]["engine"] = engine
    artifact["provenance"]["model"] = "fake-implementer-model"

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "model" in str(excinfo.value)


@pytest.mark.parametrize("engine", ["deterministic", "manual"])
def test_non_model_engine_with_real_call_true_rejected(engine):
    artifact = _artifact()
    artifact["provenance"]["engine"] = engine
    artifact["provenance"]["real_call"] = True

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "real_call" in str(excinfo.value)


def test_model_engine_requires_a_model_name():
    artifact = _artifact()
    artifact["provenance"]["engine"] = "model"
    artifact["provenance"]["model"] = None

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "model" in str(excinfo.value)


@pytest.mark.parametrize("model", ["", "   "])
def test_model_engine_rejects_blank_model_name(model):
    artifact = _artifact()
    artifact["provenance"]["engine"] = "model"
    artifact["provenance"]["model"] = model

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_model_engine_parses_without_calling_any_model(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the patch proposal parser reached the network")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    monkeypatch.setattr(os, "getenv", boom)
    monkeypatch.setattr(os.environ, "get", boom)

    artifact = _artifact()
    artifact["provenance"]["engine"] = "model"
    artifact["provenance"]["model"] = "fake-implementer-model"
    artifact["provenance"]["real_call"] = True

    parsed = parse_patch_proposal_artifact(_text(artifact))

    # `engine: "model"` is a recorded claim about something that happened
    # elsewhere. Parsing it calls nothing.
    assert parsed.provenance.engine == "model"
    assert parsed.provenance.model == "fake-implementer-model"


@pytest.mark.parametrize("engine", ["real-model", "fake", "MODEL", "", None])
def test_unknown_engine_rejected(engine):
    artifact = _artifact()
    artifact["provenance"]["engine"] = engine

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_generated_at_is_parsed_when_present():
    parsed = parse_patch_proposal_artifact(_text(_artifact()))

    assert parsed.provenance.generated_at == datetime(
        2026, 1, 3, 5, 6, 7, tzinfo=timezone.utc
    )


def test_generated_at_is_never_produced_by_the_code():
    artifact = _artifact()
    artifact["provenance"].pop("generated_at")

    parsed = parse_patch_proposal_artifact(_text(artifact))

    assert parsed.provenance.generated_at is None
    assert parsed.model_dump()["provenance"]["generated_at"] is None


def test_module_has_no_clock_call():
    from ai_dev_orchestrator.patch_proposal import models as proposal_models

    with open(proposal_models.__file__, encoding="utf-8") as handle:
        text = handle.read()

    for forbidden in ("datetime.now", "datetime.utcnow", "time.time", "date.today"):
        assert forbidden not in text


# -- 6. Scope containment: a proposal may narrow, never widen ------------------


@pytest.mark.parametrize("path", [ALLOWED_PATH, ALLOWED_TEST_PATH])
def test_change_path_from_files_likely_to_change_is_accepted(path):
    parsed = parse_patch_proposal_artifact(_text(_artifact(changes=[_change(path)])))

    assert parsed.changes[0].path == path


@pytest.mark.parametrize(
    "path",
    [
        "src/billing/other.py",
        "src/billing/format.pyc",
        "SRC/BILLING/FORMAT.PY",
        "src/billing/format.py ",
        "docs/README.md",
    ],
)
def test_change_path_outside_files_likely_to_change_rejected(path):
    artifact = _artifact(changes=[_change(path)])

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_change_path_in_forbidden_list_rejected():
    artifact = _artifact(changes=[_change(FORBIDDEN_PATH)])

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

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

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "forbidden" in str(excinfo.value)


def test_duplicate_change_paths_rejected():
    # Deliberate decision: duplicates are rejected, not merged. Two proposals
    # for one file have no defined precedence, and keeping one silently would
    # hide work from the human reading this.
    artifact = _artifact(
        changes=[_change(ALLOWED_PATH), _change(ALLOWED_PATH, change_type="create")]
    )

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "duplicate" in str(excinfo.value).lower()


def test_missing_approved_plan_rejected():
    artifact = _artifact()
    artifact.pop("approved_plan")

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_approved_plan_without_approval_rejected():
    artifact = _artifact()
    artifact["approved_plan"].pop("approval")

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_approved_plan_with_paraphrased_approval_rejected():
    artifact = _artifact()
    artifact["approved_plan"]["approval"]["approval_text"] = "looks fine to me"

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("automation_level", ["L2", "l1", "L3", ""])
def test_approved_plan_automation_level_must_be_l1(automation_level):
    artifact = _artifact()
    artifact["approved_plan"]["plan"]["automation_level"] = automation_level

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "automation_level" in str(excinfo.value)


def test_approved_plan_requires_human_approval_false_rejected():
    artifact = _artifact()
    artifact["approved_plan"]["plan"]["requires_human_approval"] = False

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "requires_human_approval" in str(excinfo.value)


def test_forged_approval_inside_the_wrapped_plan_rejected():
    artifact = _artifact()
    artifact["approved_plan"]["plan"]["approval"] = copy.deepcopy(VALID_APPROVAL)

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


# -- 7. Path safety, lexically, on every path string --------------------------


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
    # workspace root, canonicalized, stat'd, or read to decide this.
    artifact = _artifact(changes=[_change(path)])
    # Even if the plan itself listed the unsafe path, the change is still
    # refused: path safety is checked before scope containment.
    artifact["approved_plan"]["plan"]["files_likely_to_change"] = [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
        path,
    ]

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("path", UNSAFE_PATHS)
def test_unsafe_omitted_paths_rejected(path):
    artifact = _artifact()
    artifact["omitted_paths"] = [path]

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_omitted_paths_accept_safe_relative_paths():
    artifact = _artifact()
    artifact["omitted_paths"] = [ALLOWED_PATH, ALLOWED_TEST_PATH]

    parsed = parse_patch_proposal_artifact(_text(artifact))

    assert parsed.omitted_paths == [ALLOWED_PATH, ALLOWED_TEST_PATH]


def test_missing_change_path_rejected():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0].pop("path")

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


# -- 8. Change field validation ------------------------------------------------


@pytest.mark.parametrize("change_type", ["delete", "rename", "apply", "MODIFY", "", None])
def test_unknown_change_type_rejected(change_type):
    artifact = _artifact(changes=[_change(change_type=change_type)])

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("rationale", ["", "   ", "\t\n"])
def test_blank_rationale_rejected(rationale):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["rationale"] = rationale

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_missing_rationale_rejected():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0].pop("rationale")

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_empty_proposed_steps_rejected():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["proposed_steps"] = []

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("step", ["", "   "])
def test_blank_proposed_step_rejected(step):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["proposed_steps"] = ["A real step.", step]

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("risk", ["", "   "])
def test_blank_change_risk_rejected(risk):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["risks"] = [risk]

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("requires_human_review", [False, None, "true", 0])
def test_change_requires_human_review_must_be_true(requires_human_review):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["requires_human_review"] = requires_human_review

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_change_requires_human_review_has_no_default():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0].pop("requires_human_review")

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


# -- 9. The artifact carries no diff, content, command, or prompt --------------


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("diff", "--- a/src/billing/format.py\n+++ b/src/billing/format.py\n"),
        ("unified_diff", "@@ -1 +1 @@\n-old\n+new\n"),
        ("patch", "diff --git a/x b/x"),
        ("hunks", [{"start": 1, "lines": ["+new"]}]),
        ("edits", [{"path": ALLOWED_PATH, "replace": "x"}]),
        ("content", "def format_total(): ..."),
        ("file_contents", {ALLOWED_PATH: "def format_total(): ..."}),
        ("before", "old source"),
        ("after", "new source"),
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
        ("raw_artifact_text", "{...}"),
        ("approval", VALID_APPROVAL),
    ],
)
def test_artifact_rejects_diff_content_command_and_prompt_shaped_fields(name, value):
    artifact = _artifact()
    artifact[name] = value

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert str(value) not in str(excinfo.value)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("diff", "@@ -1 +1 @@\n-old\n+new\n"),
        ("patch", "diff --git a/x b/x"),
        ("content", "def format_total(): ..."),
        ("new_content", "def format_total(): ..."),
        ("before", "old source"),
        ("after", "new source"),
        ("command", "pytest -q"),
        ("command_output", "2 passed"),
        ("apply", True),
        ("auto_apply", True),
    ],
)
def test_change_rejects_diff_content_and_command_shaped_fields(name, value):
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0][name] = value

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert str(value) not in str(excinfo.value)


def test_no_diff_field_exists_on_the_change_model():
    for absent in (
        "diff",
        "unified_diff",
        "patch",
        "hunks",
        "edits",
        "content",
        "file_contents",
        "before",
        "after",
        "command",
        "commands",
    ):
        assert absent not in PatchProposalChange.model_fields


def test_no_payload_field_exists_on_the_artifact_model():
    for absent in (
        "diff",
        "patch",
        "file_contents",
        "raw_artifact_text",
        "prompt",
        "completion",
        "api_key",
        "base_url",
        "workspace_path",
        "command_output",
        "approval",
    ):
        assert absent not in PatchProposalArtifact.model_fields


def test_top_level_extra_fields_rejected():
    artifact = _artifact()
    artifact["auto_approved"] = True

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_approved_plan_extra_fields_rejected():
    artifact = _artifact()
    artifact["approved_plan"]["auto_approved"] = True

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


# -- 10. The "did not happen" flags ------------------------------------------


@pytest.mark.parametrize(
    "flag", ["file_contents_read", "files_edited", "commands_run"]
)
def test_did_not_happen_flags_true_rejected(flag):
    artifact = _artifact()
    artifact[flag] = True

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert flag in str(excinfo.value)


@pytest.mark.parametrize(
    "flag", ["file_contents_read", "files_edited", "commands_run"]
)
def test_did_not_happen_flags_have_no_defaults(flag):
    artifact = _artifact()
    artifact.pop(flag)

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("requires_human_review", [False, None, "true", 0])
def test_artifact_requires_human_review_must_be_true(requires_human_review):
    artifact = _artifact()
    artifact["requires_human_review"] = requires_human_review

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_artifact_requires_human_review_has_no_default():
    artifact = _artifact()
    artifact.pop("requires_human_review")

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_missing_next_authorization_required_rejected():
    artifact = _artifact()
    artifact.pop("next_authorization_required")

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert "next_authorization_required" in str(excinfo.value)


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_blank_next_authorization_required_rejected(value):
    artifact = _artifact()
    artifact["next_authorization_required"] = value

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


@pytest.mark.parametrize("field", ["assumptions", "risks", "open_questions"])
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_artifact_list_entries_rejected(field, value):
    artifact = _artifact()
    artifact[field] = [value]

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


# -- 11. Strict parser surface ------------------------------------------------


def test_parser_accepts_surrounding_whitespace():
    text = "\n\n\t  " + _text(_artifact()) + "  \n\t\n"

    parsed = parse_patch_proposal_artifact(text)

    assert parsed.approved_plan.issue_number == ISSUE_NUMBER


@pytest.mark.parametrize("text", ["", "   ", "\n\t  \n"])
def test_parser_rejects_empty_text(text):
    with pytest.raises(PatchProposalParseError):
        parse_patch_proposal_artifact(text)


@pytest.mark.parametrize(
    "text",
    ["{", "{not json}", '{"changes": }', '{"a": 1,}', "{'changes': []}"],
)
def test_parser_rejects_invalid_json(text):
    with pytest.raises(PatchProposalParseError):
        parse_patch_proposal_artifact(text)


def test_parser_rejects_markdown_fenced_json():
    text = "```json\n" + _text(_artifact()) + "\n```"

    with pytest.raises(PatchProposalParseError):
        parse_patch_proposal_artifact(text)


def test_parser_rejects_prose_before_json():
    text = "Here is the patch proposal:\n" + _text(_artifact())

    with pytest.raises(PatchProposalParseError):
        parse_patch_proposal_artifact(text)


def test_parser_rejects_prose_after_json():
    text = _text(_artifact()) + "\nApply this with `git apply`."

    with pytest.raises(PatchProposalParseError):
        parse_patch_proposal_artifact(text)


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        '[{"changes": []}]',
        '"patch-proposal.v1"',
        "42",
        "3.14",
        "true",
        "false",
        "null",
    ],
)
def test_parser_rejects_non_object_json(text):
    with pytest.raises(PatchProposalParseError):
        parse_patch_proposal_artifact(text)


def test_parser_rejects_non_string_input():
    with pytest.raises(PatchProposalParseError):
        parse_patch_proposal_artifact(None)  # type: ignore[arg-type]


def test_parser_never_repairs_and_never_strips_unknown_fields():
    artifact = _artifact()
    artifact["provenance"]["unknown_field"] = "x"
    artifact.pop("mode")

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(artifact))


def test_parser_wraps_pydantic_validation_error():
    artifact = _artifact()
    artifact["mode"] = "apply"

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    assert isinstance(excinfo.value.__cause__, ValidationError)
    assert not isinstance(excinfo.value, ValidationError)


def test_validation_error_message_does_not_echo_the_artifact():
    artifact = _artifact(changes=[_change()])
    artifact["changes"][0]["rationale"] = ""

    with pytest.raises(PatchProposalValidationError) as excinfo:
        parse_patch_proposal_artifact(_text(artifact))

    message = str(excinfo.value)
    assert "rationale" in message
    assert VALID_PLAN["summary"] not in message
    assert NEXT_AUTHORIZATION not in message


def test_parser_is_deterministic():
    text = _text(_artifact(changes=[_change()]))

    first = parse_patch_proposal_artifact(text)
    second = parse_patch_proposal_artifact(text)

    assert first.model_dump() == second.model_dump()


def test_parser_prints_nothing(capsys):
    parse_patch_proposal_artifact(_text(_artifact(changes=[_change()])))

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# -- 12. The parser performs no IO of any kind --------------------------------


def test_parser_performs_no_file_network_process_env_or_workspace_io(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the patch proposal parser performed IO")

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
    monkeypatch.setattr(subprocess, "Popen", boom)

    parsed = parse_patch_proposal_artifact(_text(_artifact(changes=[_change()])))

    assert parsed.changes[0].path == ALLOWED_PATH


def test_parser_failure_paths_also_perform_no_io(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the patch proposal parser performed IO")

    monkeypatch.setattr(builtins, "open", boom)
    monkeypatch.setattr(os, "getenv", boom)
    monkeypatch.setattr(os.environ, "get", boom)
    monkeypatch.setattr(os, "stat", boom)
    monkeypatch.setattr(os.path, "realpath", boom)
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)

    # An absolute, workspace-shaped path is refused lexically — never resolved.
    unsafe = _artifact(changes=[_change("C:\\dev\\some_project\\src\\format.py")])

    with pytest.raises(PatchProposalValidationError):
        parse_patch_proposal_artifact(_text(unsafe))
    with pytest.raises(PatchProposalParseError):
        parse_patch_proposal_artifact("not json at all")


def test_parser_writes_no_files(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())

    parse_patch_proposal_artifact(_text(_artifact(changes=[_change()])))

    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_workspace_like_plan_paths_are_never_resolved():
    artifact = _artifact()
    # Workspace-shaped strings inside the wrapped plan stay plain strings:
    # nothing here resolves, stats, globs, or normalizes them.
    artifact["approved_plan"]["plan"]["files_likely_to_change"] = [
        "C:\\dev\\some_project\\src\\billing\\format.py",
        "../../etc/passwd",
    ]
    artifact["omitted_paths"] = []

    parsed = parse_patch_proposal_artifact(_text(artifact))

    assert parsed.approved_plan.plan.files_likely_to_change == [
        "C:\\dev\\some_project\\src\\billing\\format.py",
        "../../etc/passwd",
    ]
    # And they remain unusable as change paths: a proposal cannot reach them.
    assert parsed.changes == []


# -- 13. The implementation module cannot reach a model, a socket, or GitHub ---


def test_implementation_module_globals_are_inert():
    from ai_dev_orchestrator.patch_proposal import models as proposal_models

    module_globals = vars(proposal_models)
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
    ):
        assert name not in module_globals, f"{name} must not be importable here"


def test_implementation_module_imports_no_transport_cli_or_workspace():
    from ai_dev_orchestrator.patch_proposal import models as proposal_models

    with open(proposal_models.__file__, encoding="utf-8") as handle:
        text = handle.read()

    for forbidden in (
        "import httpx",
        "import requests",
        "import os",
        "import socket",
        "import subprocess",
        "from pathlib",
        "from ai_dev_orchestrator.cli",
        "from ai_dev_orchestrator.llm",
        "from ai_dev_orchestrator.github",
        "from ai_dev_orchestrator.workspace",
        "AIDO_LITELLM",
        "GITHUB_TOKEN",
    ):
        assert forbidden not in text, f"{forbidden!r} must not appear"


def test_patch_proposal_package_still_exports_the_phase_5e0_surface():
    from ai_dev_orchestrator import patch_proposal

    # Phase 5E1 added a deterministic generator alongside these; the nine names
    # Phase 5E0 shipped are unchanged, and the models and parser below are still
    # exactly what this file exercises.
    for name in (
        "PATCH_PROPOSAL_MODE",
        "PATCH_PROPOSAL_SCHEMA_VERSION",
        "PatchProposalArtifact",
        "PatchProposalChange",
        "PatchProposalError",
        "PatchProposalParseError",
        "PatchProposalProvenance",
        "PatchProposalValidationError",
        "parse_patch_proposal_artifact",
    ):
        assert name in patch_proposal.__all__
        assert hasattr(patch_proposal, name)

    # No applier, no loader, no writer, no diff generator. Later phases.
    for absent in (
        "load_patch_proposal_artifact",
        "apply_patch_proposal",
        "write_patch_proposal",
        "generate_diff",
        "PatchApplier",
        "L2Implementer",
    ):
        assert not hasattr(patch_proposal, absent)


# -- 14. The CLI surface -------------------------------------------------------


# Phase 5E0 added no command. Phase 5E1 then added exactly one —
# `generate-patch-proposal`, which generates a proposal offline and prints it —
# and changed nothing else.
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
    # Phase 5D2 later added one more read-only command; it still produces no
    # diff, edits nothing, and runs nothing.
    "l2-read-workspace-files",
    # Phase 5E3 added a diff *proposal* producer. It writes diff text to stdout
    # and applies nothing, edits nothing, and runs nothing.
    "generate-diff-proposal",
    "l2-preview-file-edits",
    # Phase 5F2C. The FIRST command that writes a file into a target
    # workspace: one exact approved modification of one tracked UTF-8 file in
    # one clean Windows Git repository. It runs no project verification
    # command, calls no model, opens no socket, and creates no
    # branch/commit/push/PR.
    "l2-apply-approved-file-edit",
    # Phase 5F2D. The FIRST command that executes repository-controlled
    # code: one project-configured verification process, once, bound to
    # one already-applied approved modification. Controlled invocation,
    # NOT a sandbox. It calls no model, contacts no GitHub, and creates no
    # branch/commit/push/PR.
    "l2-verify-approved-file-edit",
    # Phase 5F2E. The FIRST command that deliberately sends source-derived code
    # to a model: it runs the Phase 5F2D verification itself, and only after a
    # `verified` outcome sends ONE approved unified diff, selected plan prose,
    # and the redacted verification output to ONE project-configured reviewer
    # model. The verdict is advisory: no fixer, no re-review, no patch, no file
    # edit, and no branch/commit/push/PR.
    "l2-review-approved-file-edit",
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


def test_no_apply_or_implement_command_exists():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    # `generate-patch-proposal` (Phase 5E1) produces prose and prints it. No
    # command applies a patch, edits a file, implements a plan, or stamps an
    # approval.
    for absent in (
        "propose-patch",
        "apply-patch",
        "apply-approved-plan",
        "approve-plan",
        "implement",
    ):
        assert absent not in result.output

    for absent in (
        "propose-patch",
        "generate-patch",
        "apply-patch",
        "apply-patch-proposal",
        "implement-plan",
    ):
        assert runner.invoke(app, [absent, "--help"]).exit_code != 0


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
        "--propose-patch",
        "--patch-proposal",
        "--diff",
        "--apply-patch",
        "--edit-files",
        "--run-commands",
        "--read-contents",
    ):
        assert absent not in result.output


def test_l2_dry_run_options_unchanged():
    result = runner.invoke(app, ["l2-dry-run", "--help"])

    assert result.exit_code == 0
    for present in ("--project-config", "--approved-plan", "--format"):
        assert present in result.output
    for absent in (
        "--propose-patch",
        "--patch-proposal",
        "--diff",
        "--apply-patch",
        "--inspect-workspace",
    ):
        assert absent not in result.output


def test_generate_plan_remains_offline_only_and_unchanged():
    result = runner.invoke(app, ["generate-plan", "--help"])

    assert result.exit_code == 0
    for absent in (
        "--real",
        "--real-model",
        "--live",
        "--model",
        "--approved-plan",
        "--apply",
        "--propose-patch",
        "--patch-proposal",
        "--audit-dir",
    ):
        assert absent not in result.output


def test_generate_model_plan_options_unchanged():
    result = runner.invoke(app, ["generate-model-plan", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--issue",
        "--title",
        "--body-file",
        "--model",
        "--real-model",
        "--format",
    ):
        assert present in result.output
    for absent in (
        "--approved-plan",
        "--apply",
        "--propose-patch",
        "--patch-proposal",
        "--approve",
        "--audit-dir",
    ):
        assert absent not in result.output


def test_cli_imports_the_patch_proposal_package_lazily_and_only_to_generate():
    from ai_dev_orchestrator import cli

    # Phase 5E1's command imports the generator *inside* its own body, matching
    # every other command here, so importing the CLI still pulls in nothing.
    assert "patch_proposal" not in vars(cli)
    assert "parse_patch_proposal_artifact" not in vars(cli)
    assert "PatchProposalArtifact" not in vars(cli)

    # And the only thing it reaches for is the generator — never an applier or a
    # writer. (Phase 5E3 later added a *separate* command that generates diff
    # text, so `generate_diff` now appears in the CLI as that command's own
    # consent flag. It applies nothing either.)
    source = inspect.getsource(cli)
    assert "build_deterministic_patch_proposal" in source
    for absent in (
        "apply_patch_proposal",
        "write_patch_proposal",
        "apply_diff_proposal",
        "write_diff_proposal",
    ):
        assert absent not in source


def test_importing_patch_proposal_adds_no_command():
    import importlib

    from ai_dev_orchestrator import patch_proposal  # noqa: F401

    importlib.reload(patch_proposal)

    registered = [
        info.name or info.callback.__name__.replace("_", "-")
        for info in app.registered_commands
    ]
    assert registered == EXPECTED_COMMANDS
