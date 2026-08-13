"""Phase 5E3 tests: the deterministic unified diff proposal generator.

The generator is a **pure function over four already-loaded objects** — an
approved L1 plan, a project config, a Phase 5D2 ``l2-read-workspace-files``
packet, and a proposed-content input — that runs ``difflib`` over strings it was
handed and returns a validated Phase 5E2 ``DiffProposalArtifact``.

It generates diff text and does nothing with it, so these tests assert absence
at least as hard as presence: no file is opened, no target workspace is read,
listed, stat'd, or resolved, no diff is applied, no apply-cleanliness is
checked, no file is edited, no command is executed, no environment variable is
read, no socket is opened, no model is called, nothing is fetched from or
written to GitHub, no artifact file is written, and no approval is stamped.

Every input here is a literal dict or a literal string. The paths in them are
never opened: the *only* source of original file text is the packet's
``content_text``, and a path the packet does not cover is a path whose diff
cannot be generated — never a path to go and read.
"""

from __future__ import annotations

import builtins
import copy
import os
import socket
import subprocess

import pytest

from ai_dev_orchestrator.diff_proposal import (
    DIFF_PROPOSAL_MODE,
    DIFF_PROPOSAL_SCHEMA_VERSION,
    PROPOSED_CONTENT_MODE,
    PROPOSED_CONTENT_SCHEMA_VERSION,
    DiffProposalGenerationError,
    DiffProposalInputParseError,
    DiffProposalInputValidationError,
    build_deterministic_diff_proposal,
    parse_diff_proposal_artifact,
    parse_proposed_content_input,
    parse_workspace_content_packet,
)
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.handoff.models import ApprovedL1PlanArtifact
from ai_dev_orchestrator.models import ProjectConfig

PROJECT_ID = "demo_project"
REPO = "demo/widgets"
ISSUE_NUMBER = 42
TITLE = "Add currency formatting helper"
APPROVER = "operator@example.invalid"
APPROVED_AT = "2026-01-02T04:00:00+00:00"

# Path-shaped strings. Nothing below is ever opened, stat'd, listed, or
# resolved: they are compared and copied as strings only.
PLAN_FILE_A = "src/billing/sentinel_never_opened_a.py"
PLAN_FILE_B = "tests/test_sentinel_never_opened_b.py"
PLAN_FILE_NEW = "src/billing/sentinel_never_opened_new.py"
PLAN_FORBIDDEN = "secrets/sentinel_never_opened.env"

ORIGINAL_A = "def total(amount):\n    return amount\n"
PROPOSED_A = "def total(amount):\n    return round(amount, 2)\n"

ORIGINAL_B = "def test_total():\n    assert total(1) == 1\n"
PROPOSED_B = "def test_total():\n    assert total(1.005) == 1.01\n"

CREATED_TEXT = "def helper():\n    return 'new'\n"

# A marker that must never leak out of an error message.
SECRET_VALUE = "SENTINEL_SECRET_VALUE_NEVER_ECHOED"

VALID_PLAN: dict = {
    "issue_number": ISSUE_NUMBER,
    "repo": REPO,
    "title": TITLE,
    "summary": "Format invoice totals through one shared helper.",
    "scope_summary": "Only the billing formatting helper and its tests.",
    "non_goals": ["No changes to the payment gateway client."],
    "proposed_steps": ["Describe a single shared helper for a human to write."],
    "files_likely_to_change": [PLAN_FILE_A, PLAN_FILE_B, PLAN_FILE_NEW],
    "files_forbidden_or_out_of_scope": [PLAN_FORBIDDEN],
    "required_verification": ["pytest -q"],
    "risks": ["Rounding differences on reissued invoices."],
    "open_questions": ["Which locale should totals use?"],
    "automation_level": "L1",
    "requires_human_approval": True,
}

VALID_PROVENANCE: dict = {
    "engine": "real-model",
    "operation": "l1-plan",
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
    "approved_by": APPROVER,
    "approved_at": APPROVED_AT,
    "approval_text": REQUIRED_APPROVAL_TEXT,
    "source": "manual",
}


def _approved_plan(**plan_overrides) -> ApprovedL1PlanArtifact:
    """A fresh, fully valid approved-plan object. Never read from disk."""
    plan = copy.deepcopy(VALID_PLAN)
    plan.update(plan_overrides)
    return ApprovedL1PlanArtifact.model_validate(
        {
            "approval": copy.deepcopy(VALID_APPROVAL),
            "plan_provenance": copy.deepcopy(VALID_PROVENANCE),
            "plan": plan,
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
        }
    )


def _project(project_id: str = PROJECT_ID, github_repo: str = REPO) -> ProjectConfig:
    """A project config built in memory. ``workspace_path`` is a string only."""
    return ProjectConfig.model_validate(
        {
            "project_id": project_id,
            "display_name": "Demo Project",
            "repo": {
                "workspace_path": "Z:/sentinel_workspace_never_touched",
                "github_repo": github_repo,
                "default_base_branch": "main",
                "branch_prefix": "ai/demo",
            },
        }
    )


def _read_item(path: str, content: str, **overrides) -> dict:
    """A Phase 5D2 row for a path that was successfully read."""
    item = {
        "original_plan_path": path,
        "canonical_relative_path": path,
        "status": "read",
        "kind": "file",
        "size_bytes": len(content.encode("utf-8")),
        "bytes_read": len(content.encode("utf-8")),
        "encoding": "utf-8",
        "redacted": False,
        "redaction_count": 0,
        "redaction_kinds": [],
        "content_text": content,
    }
    item.update(overrides)
    return item


def _empty_item(path: str, status: str, **overrides) -> dict:
    """A Phase 5D2 row for a path whose contents were deliberately not read."""
    item = {
        "original_plan_path": path,
        "canonical_relative_path": None,
        "status": status,
        "kind": None,
        "size_bytes": None,
        "bytes_read": 0,
        "encoding": None,
        "redacted": False,
        "redaction_count": 0,
        "redaction_kinds": [],
        "content_text": None,
    }
    item.update(overrides)
    return item


def _packet_dict(items: list[dict] | None = None, **overrides) -> dict:
    """The shape ``l2-read-workspace-files`` prints, notice and policies and all."""
    packet = {
        "notice": "L2 READ-ONLY FILE-CONTENT INSPECTION ONLY",
        "mode": "l2-read-workspace-files",
        "project": {
            "project_id": PROJECT_ID,
            "repo": REPO,
            "workspace_policy": {
                "deny_outside_workspace": True,
                "allow_symlinks": False,
                "max_changed_files": 20,
            },
            "content_policy": {
                "enabled": True,
                "max_files": 10,
                "max_file_bytes": 65536,
                "max_total_bytes": 262144,
                "allow_protected_paths": False,
                "redaction": "mandatory_basic_secret_like_redaction",
            },
        },
        "approved_plan": {
            "approved_by": APPROVER,
            "approved_at": APPROVED_AT,
            "source": "manual",
            "plan_engine": "real-model",
            "real_call": True,
            "model": "fake-planner-model",
            "issue_number": ISSUE_NUMBER,
            "title": TITLE,
        },
        "workspace_content": {
            "note": "Bounded content only.",
            "candidate_source": "approved_plan.files_likely_to_change",
            "file_contents_read": True,
            "directories_listed": False,
            "commands_run": False,
            "model_called": False,
            "diffs_generated": False,
            "files_edited": False,
            "total_bytes_read": 0,
            "items": [
                _read_item(PLAN_FILE_A, ORIGINAL_A),
                _read_item(PLAN_FILE_B, ORIGINAL_B),
                _empty_item(PLAN_FILE_NEW, "missing"),
            ]
            if items is None
            else items,
        },
    }
    for key, value in overrides.items():
        packet[key] = value
    return packet


def _packet(items: list[dict] | None = None, **overrides):
    return parse_workspace_content_packet(_json(_packet_dict(items, **overrides)))


def _change(
    path: str = PLAN_FILE_A,
    content: str = PROPOSED_A,
    change_type: str = "modify",
    **overrides,
) -> dict:
    change = {
        "path": path,
        "change_type": change_type,
        "content_text": content,
        "rationale": "Round invoice totals to two decimal places.",
        "risks": ["Reissued invoices may differ by a cent."],
        "requires_human_review": True,
    }
    change.update(overrides)
    return change


def _proposed_dict(changes: list[dict] | None = None, **overrides) -> dict:
    payload = {
        "schema_version": PROPOSED_CONTENT_SCHEMA_VERSION,
        "mode": PROPOSED_CONTENT_MODE,
        "changes": [_change()] if changes is None else changes,
        "assumptions": [],
        "risks": [],
        "open_questions": [],
        "requires_human_review": True,
        "next_authorization_required": "A human must review before anything is applied.",
    }
    payload.update(overrides)
    return payload


def _proposed(changes: list[dict] | None = None, **overrides):
    return parse_proposed_content_input(_json(_proposed_dict(changes, **overrides)))


def _json(payload: dict) -> str:
    import json

    return json.dumps(payload)


def _build(
    *,
    approved_plan: ApprovedL1PlanArtifact | None = None,
    project: ProjectConfig | None = None,
    workspace_content=None,
    proposed_content=None,
):
    return build_deterministic_diff_proposal(
        approved_plan=_approved_plan() if approved_plan is None else approved_plan,
        project=_project() if project is None else project,
        workspace_content=_packet() if workspace_content is None else workspace_content,
        proposed_content=_proposed()
        if proposed_content is None
        else proposed_content,
    )


# -- 1. the success path -------------------------------------------------------


def test_modify_generates_a_diff_proposal_artifact():
    artifact = _build()

    assert artifact.schema_version == DIFF_PROPOSAL_SCHEMA_VERSION
    assert artifact.mode == DIFF_PROPOSAL_MODE
    assert [change.path for change in artifact.changes] == [PLAN_FILE_A]

    change = artifact.changes[0]
    assert change.change_type == "modify"
    assert change.requires_human_review is True
    assert change.unified_diff.splitlines()[0] == f"--- a/{PLAN_FILE_A}"
    assert change.unified_diff.splitlines()[1] == f"+++ b/{PLAN_FILE_A}"
    assert any(line.startswith("@@") for line in change.unified_diff.splitlines())
    assert "-    return amount" in change.unified_diff
    assert "+    return round(amount, 2)" in change.unified_diff


def test_create_generates_a_dev_null_diff():
    artifact = _build(
        proposed_content=_proposed(
            [_change(PLAN_FILE_NEW, CREATED_TEXT, change_type="create")]
        )
    )

    change = artifact.changes[0]
    assert change.change_type == "create"
    assert change.unified_diff.splitlines()[0] == "--- /dev/null"
    assert change.unified_diff.splitlines()[1] == f"+++ b/{PLAN_FILE_NEW}"
    assert "+def helper():" in change.unified_diff
    # A create has no original, so nothing recorded was consumed as source.
    assert artifact.source_contents_read is False


def test_generated_artifact_parses_with_the_phase_5e2_parser():
    artifact = _build()

    reparsed = parse_diff_proposal_artifact(artifact.model_dump_json())

    assert reparsed.model_dump() == artifact.model_dump()
    assert reparsed.provenance.operation == "diff-proposal"


def test_generation_is_deterministic():
    assert _build().model_dump_json() == _build().model_dump_json()


def test_approved_plan_snapshot_travels_through_unchanged():
    approved_plan = _approved_plan()
    before = approved_plan.model_dump()

    artifact = _build(approved_plan=approved_plan)

    assert artifact.approved_plan.model_dump() == before
    assert approved_plan.model_dump() == before
    assert artifact.approved_plan.approval.approval_text == REQUIRED_APPROVAL_TEXT


def test_multiple_changes_preserve_the_proposed_order():
    proposed = _proposed(
        [
            _change(PLAN_FILE_B, PROPOSED_B),
            _change(PLAN_FILE_NEW, CREATED_TEXT, change_type="create"),
            _change(PLAN_FILE_A, PROPOSED_A),
        ]
    )

    artifact = _build(proposed_content=proposed)

    assert [change.path for change in artifact.changes] == [
        PLAN_FILE_B,
        PLAN_FILE_NEW,
        PLAN_FILE_A,
    ]


def test_rationale_and_risks_come_from_the_proposed_input():
    proposed = _proposed(
        [_change(rationale="SENTINEL_RATIONALE", risks=["SENTINEL_RISK"])]
    )

    change = _build(proposed_content=proposed).changes[0]

    assert change.rationale == "SENTINEL_RATIONALE"
    assert change.risks == ["SENTINEL_RISK"]


def test_input_risks_assumptions_and_open_questions_are_carried_through():
    proposed = _proposed(
        assumptions=["SENTINEL_ASSUMPTION"],
        risks=["SENTINEL_INPUT_RISK"],
        open_questions=["SENTINEL_OPEN_QUESTION"],
    )

    artifact = _build(proposed_content=proposed)

    assert "SENTINEL_ASSUMPTION" in artifact.assumptions
    assert "SENTINEL_INPUT_RISK" in artifact.risks
    assert artifact.open_questions == ["SENTINEL_OPEN_QUESTION"]


def test_assumptions_state_the_packet_source_and_the_missing_apply_check():
    artifact = _build()

    joined = " ".join(artifact.assumptions)
    assert "Phase 5D2" in joined
    assert "read no target workspace file directly" in joined
    assert "apply cleanly was not checked" in joined
    assert any("not applied" in risk for risk in artifact.risks)


# -- 2. no-op changes are omitted, never fabricated ----------------------------


def test_noop_modify_is_omitted_not_emitted_as_a_fake_diff():
    proposed = _proposed([_change(PLAN_FILE_A, ORIGINAL_A)])

    artifact = _build(proposed_content=proposed)

    assert artifact.changes == []
    assert artifact.omitted_paths == [PLAN_FILE_A]
    assert artifact.diffs_generated is True


def test_noop_and_real_change_together():
    proposed = _proposed(
        [_change(PLAN_FILE_A, ORIGINAL_A), _change(PLAN_FILE_B, PROPOSED_B)]
    )

    artifact = _build(proposed_content=proposed)

    assert [change.path for change in artifact.changes] == [PLAN_FILE_B]
    assert artifact.omitted_paths == [PLAN_FILE_A]


def test_empty_proposed_changes_generates_a_valid_empty_artifact():
    artifact = _build(proposed_content=_proposed([]))

    assert artifact.changes == []
    assert artifact.omitted_paths == []
    assert artifact.source_contents_read is False
    assert any("no diff" in assumption for assumption in artifact.assumptions)
    parse_diff_proposal_artifact(artifact.model_dump_json())


def test_a_trailing_newline_only_difference_is_a_noop():
    """``splitlines()`` cannot see it, and the artifact says so rather than lying."""
    proposed = _proposed([_change(PLAN_FILE_A, ORIGINAL_A.rstrip("\n"))])

    artifact = _build(proposed_content=proposed)

    assert artifact.changes == []
    assert artifact.omitted_paths == [PLAN_FILE_A]
    assert any("trailing newline" in item for item in artifact.assumptions)


# -- 3. scope containment ------------------------------------------------------


def test_path_outside_files_likely_to_change_is_rejected():
    proposed = _proposed([_change("src/somewhere_else.py", PROPOSED_A)])

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(
            workspace_content=_packet(
                [
                    _read_item(PLAN_FILE_A, ORIGINAL_A),
                    _read_item("src/somewhere_else.py", ORIGINAL_A),
                ]
            ),
            proposed_content=proposed,
        )

    assert "files_likely_to_change" in str(excinfo.value)


def test_forbidden_path_is_rejected_even_when_the_plan_contradicts_itself():
    approved_plan = _approved_plan(
        files_likely_to_change=[PLAN_FILE_A, PLAN_FORBIDDEN],
        files_forbidden_or_out_of_scope=[PLAN_FORBIDDEN],
    )
    proposed = _proposed([_change(PLAN_FORBIDDEN, PROPOSED_A)])

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(
            approved_plan=approved_plan,
            workspace_content=_packet([_read_item(PLAN_FORBIDDEN, ORIGINAL_A)]),
            proposed_content=proposed,
        )

    assert "files_forbidden_or_out_of_scope" in str(excinfo.value)


def test_path_missing_from_the_packet_is_rejected():
    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(workspace_content=_packet([_read_item(PLAN_FILE_B, ORIGINAL_B)]))

    assert "does not appear in the workspace-content packet" in str(excinfo.value)
    # And the refusal is a refusal, not an instruction to go and read it.
    assert "l2-read-workspace-files" in str(excinfo.value)


def test_plan_prose_is_never_treated_as_a_proposable_path():
    approved_plan = _approved_plan(files_likely_to_change=[])
    proposed = _proposed([_change("pytest -q", PROPOSED_A)])

    with pytest.raises(DiffProposalGenerationError):
        _build(approved_plan=approved_plan, proposed_content=proposed)


# -- 4. original content must be real, present, and unredacted -----------------


@pytest.mark.parametrize(
    "status",
    [
        "missing",
        "directory_no_content",
        "other_no_content",
        "too_large",
        "skipped_total_limit",
        "binary_or_non_utf8",
    ],
)
def test_modify_requires_a_read_item(status):
    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(workspace_content=_packet([_empty_item(PLAN_FILE_A, status)]))

    assert status in str(excinfo.value)
    assert "no original content is available" in str(excinfo.value)


def test_modify_of_a_directory_read_as_non_file_is_rejected():
    item = _read_item(PLAN_FILE_A, ORIGINAL_A, kind="directory")

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(workspace_content=_packet([item]))

    assert "rather than 'file'" in str(excinfo.value)


def test_modify_of_a_read_item_without_content_text_is_rejected():
    item = _read_item(PLAN_FILE_A, ORIGINAL_A, content_text=None)

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(workspace_content=_packet([item]))

    assert "carries no content_text" in str(excinfo.value)


def test_modify_from_a_redacted_source_fails_closed():
    item = _read_item(
        PLAN_FILE_A,
        "api_key = '[REDACTED]'\n",
        redacted=True,
        redaction_count=1,
        redaction_kinds=["secret_assignment"],
    )

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(workspace_content=_packet([item]))

    message = str(excinfo.value)
    assert "redacted" in message
    assert "misleading" in message
    assert PLAN_FILE_A in message


def test_create_over_an_existing_read_item_fails_closed():
    proposed = _proposed([_change(PLAN_FILE_A, CREATED_TEXT, change_type="create")])

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(proposed_content=proposed)

    assert "already exists" in str(excinfo.value)
    assert "does not overwrite" in str(excinfo.value)


@pytest.mark.parametrize(
    "status", ["directory_no_content", "too_large", "binary_or_non_utf8"]
)
def test_create_requires_a_missing_item(status):
    proposed = _proposed([_change(PLAN_FILE_NEW, CREATED_TEXT, change_type="create")])

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(
            workspace_content=_packet([_empty_item(PLAN_FILE_NEW, status)]),
            proposed_content=proposed,
        )

    assert "rather than 'missing'" in str(excinfo.value)


def test_create_with_empty_content_is_refused_not_silently_omitted():
    proposed = _proposed([_change(PLAN_FILE_NEW, "", change_type="create")])

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(proposed_content=proposed)

    assert "no unified diff hunk can express" in str(excinfo.value)


def test_modify_may_empty_a_file():
    proposed = _proposed([_change(PLAN_FILE_A, "")])

    change = _build(proposed_content=proposed).changes[0]

    assert change.change_type == "modify"
    assert "-def total(amount):" in change.unified_diff


# -- 5. identity matching ------------------------------------------------------


@pytest.mark.parametrize(
    "project_overrides, expected",
    [
        pytest.param({"project_id": "other_project"}, "project_id", id="project-id"),
        pytest.param({"github_repo": "someone/else"}, "repo", id="repo"),
        pytest.param({"github_repo": REPO.upper()}, "repo", id="case-folded-repo"),
    ],
)
def test_plan_config_identity_mismatch_fails(project_overrides, expected):
    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(project=_project(**project_overrides))

    assert "does not match this project config exactly" in str(excinfo.value)
    assert expected in str(excinfo.value)


@pytest.mark.parametrize(
    "mutate, expected",
    [
        pytest.param(
            lambda packet: packet["project"].update(project_id="other_project"),
            "project.project_id",
            id="packet-project-id",
        ),
        pytest.param(
            lambda packet: packet["project"].update(repo="someone/else"),
            "project.repo",
            id="packet-repo",
        ),
        pytest.param(
            lambda packet: packet["approved_plan"].update(issue_number=99),
            "approved_plan.issue_number",
            id="packet-issue-number",
        ),
        pytest.param(
            lambda packet: packet["approved_plan"].update(title="A different title"),
            "approved_plan.title",
            id="packet-title",
        ),
    ],
)
def test_packet_identity_mismatch_fails(mutate, expected):
    payload = _packet_dict()
    mutate(payload)
    packet = parse_workspace_content_packet(_json(payload))

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(workspace_content=packet)

    assert "does not match this project config and approved plan exactly" in str(
        excinfo.value
    )
    assert expected in str(excinfo.value)


def test_an_escalated_plan_is_refused():
    approved_plan = _approved_plan()
    # Bypass the artifact's own guard the way a corrupt in-memory object would.
    object.__setattr__(approved_plan.plan, "automation_level", "L2")

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(approved_plan=approved_plan)

    assert "automation_level must be exactly 'L1'" in str(excinfo.value)


def test_a_plan_not_requiring_approval_is_refused():
    approved_plan = _approved_plan()
    object.__setattr__(approved_plan.plan, "requires_human_approval", False)

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(approved_plan=approved_plan)

    assert "requires_human_approval must be True" in str(excinfo.value)


# -- 6. the flags describing what did and did not happen -----------------------


def test_provenance_is_deterministic_and_calls_nothing():
    provenance = _build().provenance

    assert provenance.engine == "deterministic"
    assert provenance.operation == "diff-proposal"
    assert provenance.real_call is False
    assert provenance.model is None
    assert provenance.generated_at is None
    assert provenance.project_id == PROJECT_ID
    assert provenance.repo == REPO
    assert provenance.issue_number == ISSUE_NUMBER
    assert provenance.title == TITLE


def test_no_apply_no_edit_no_command_and_no_apply_check_are_recorded():
    artifact = _build()

    assert artifact.diffs_generated is True
    assert artifact.files_edited is False
    assert artifact.commands_run is False
    assert artifact.applies_cleanly_checked is False
    assert artifact.requires_human_review is True
    assert artifact.patch_proposal is None
    assert artifact.next_authorization_required.startswith("Phase 5F or later")


@pytest.mark.parametrize(
    "changes, expected",
    [
        pytest.param([_change()], True, id="modify-uses-recorded-content"),
        pytest.param(
            [_change(PLAN_FILE_NEW, CREATED_TEXT, change_type="create")],
            False,
            id="create-uses-none",
        ),
        pytest.param([], False, id="nothing-proposed"),
    ],
)
def test_source_contents_read_reflects_whether_original_content_was_used(
    changes, expected
):
    assert _build(proposed_content=_proposed(changes)).source_contents_read is expected


def test_a_noop_modify_still_counts_as_having_consulted_the_source():
    artifact = _build(proposed_content=_proposed([_change(PLAN_FILE_A, ORIGINAL_A)]))

    assert artifact.source_contents_read is True


# -- 7. secret-like generated diffs fail closed --------------------------------


@pytest.mark.parametrize(
    "proposed_line, category",
    [
        pytest.param(f'api_key = "{SECRET_VALUE}"', "secret_assignment", id="assignment"),
        pytest.param(f"AUTH = 'Bearer {SECRET_VALUE}'", "bearer_token", id="bearer"),
        pytest.param(f"KEY = 'sk-{SECRET_VALUE}'", "openai_style_key", id="sk-key"),
    ],
)
def test_secret_like_generated_diff_fails_without_echoing_the_secret(
    proposed_line, category
):
    proposed = _proposed([_change(PLAN_FILE_A, ORIGINAL_A + proposed_line + "\n")])

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(proposed_content=proposed)

    message = str(excinfo.value)
    assert category in message
    assert PLAN_FILE_A in message
    # The category is loud; the value stays quiet, and so does the diff.
    assert SECRET_VALUE not in message
    assert "discarded rather than redacted" in message


def test_a_secret_like_context_line_also_fails_closed():
    """Even when the secret is only *context*, the diff still carries it."""
    original = f'api_key = "{SECRET_VALUE}"\ndef total(amount):\n    return amount\n'
    proposed = _proposed(
        [_change(PLAN_FILE_A, original.replace("return amount", "return 0"))]
    )

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(
            workspace_content=_packet([_read_item(PLAN_FILE_A, original)]),
            proposed_content=proposed,
        )

    assert SECRET_VALUE not in str(excinfo.value)


# -- 8. a generated artifact that would not validate is discarded --------------


def test_a_source_line_that_forges_a_file_header_is_refused():
    """A removed ``-- x`` line becomes ``--- x``, which is not a real header."""
    original = "-- a note\ndef total(amount):\n    return amount\n"
    proposed = _proposed([_change(PLAN_FILE_A, "def total(amount):\n    return 0\n")])

    with pytest.raises(DiffProposalGenerationError) as excinfo:
        _build(
            workspace_content=_packet([_read_item(PLAN_FILE_A, original)]),
            proposed_content=proposed,
        )

    assert "failed Phase 5E2 artifact validation" in str(excinfo.value)


def test_an_unsafe_plan_path_is_refused_by_the_artifact_model():
    approved_plan = _approved_plan(files_likely_to_change=["../outside.py"])
    proposed_payload = _proposed_dict([_change("../outside.py", PROPOSED_A)])

    with pytest.raises(DiffProposalInputValidationError):
        parse_proposed_content_input(_json(proposed_payload))

    # The unsafe path is in the plan, so the plan alone cannot put it into an
    # artifact: only a proposed change can, and no proposed change can name it.
    artifact = _build(
        approved_plan=approved_plan,
        workspace_content=_packet([]),
        proposed_content=_proposed([]),
    )
    assert artifact.changes == []
    assert artifact.omitted_paths == []


# -- 9. the proposed-content parser --------------------------------------------


def test_valid_proposed_content_parses():
    parsed = parse_proposed_content_input(_json(_proposed_dict()))

    assert parsed.schema_version == PROPOSED_CONTENT_SCHEMA_VERSION
    assert parsed.mode == PROPOSED_CONTENT_MODE
    assert parsed.requires_human_review is True
    assert [change.path for change in parsed.changes] == [PLAN_FILE_A]


def test_proposed_content_tolerates_surrounding_whitespace():
    assert parse_proposed_content_input("\n  " + _json(_proposed_dict()) + "  \n")


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "not json at all",
        '{"schema_version": ',
        "```json\n{}\n```",
        "[]",
        '"a string"',
        "17",
        "true",
        "null",
        _json(_proposed_dict()) + " trailing prose",
    ],
)
def test_proposed_content_requires_exactly_one_json_object(text):
    with pytest.raises(DiffProposalInputParseError):
        parse_proposed_content_input(text)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "   ",
        "/etc/passwd",
        "C:/Windows/system32/config",
        "../outside.py",
        "src/../../outside.py",
        "//server/share/file.py",
        "\\\\?\\C:\\file.py",
        "src/./file.py",
        "src//file.py",
        "src/file.py.",
        "src/file.py ",
        "PROGRA~1/file.py",
        ".",
    ],
)
def test_proposed_content_rejects_unsafe_paths(path):
    with pytest.raises(DiffProposalInputValidationError):
        parse_proposed_content_input(_json(_proposed_dict([_change(path, PROPOSED_A)])))


def test_proposed_content_rejects_duplicate_paths():
    payload = _proposed_dict([_change(), _change(content="other\n")])

    with pytest.raises(DiffProposalInputValidationError) as excinfo:
        parse_proposed_content_input(_json(payload))

    assert "duplicates are rejected" in str(excinfo.value)


@pytest.mark.parametrize(
    "extra",
    [
        {"unified_diff": "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b"},
        {"diff": "anything"},
        {"command": "rm -rf /"},
        {"apply": True},
        {"workspace_path": "C:/dev/somewhere"},
        {"before_content": "old"},
        {"after_content": "new"},
    ],
)
def test_proposed_change_rejects_forbidden_extra_fields(extra):
    with pytest.raises(DiffProposalInputValidationError):
        parse_proposed_content_input(_json(_proposed_dict([_change(**extra)])))


@pytest.mark.parametrize(
    "extra",
    [
        {"approval": dict(VALID_APPROVAL)},
        {"approval_text": REQUIRED_APPROVAL_TEXT},
        {"prompt": "you are a helpful assistant"},
        {"completion": "sure"},
        {"api_key": "sk-abcdefghijkl"},
        {"base_url": "https://litellm.invalid"},
        {"command_output": "ok"},
        {"apply_patch": True},
    ],
)
def test_proposed_input_rejects_forbidden_extra_fields(extra):
    with pytest.raises(DiffProposalInputValidationError):
        parse_proposed_content_input(_json(_proposed_dict(**extra)))


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": "proposed-content.v2"},
        {"mode": "apply"},
        {"requires_human_review": False},
        {"next_authorization_required": "   "},
        {"risks": ["  "]},
        {"open_questions": [""]},
    ],
)
def test_proposed_input_rejects_bad_field_values(overrides):
    with pytest.raises(DiffProposalInputValidationError):
        parse_proposed_content_input(_json(_proposed_dict(**overrides)))


@pytest.mark.parametrize(
    "overrides",
    [
        {"change_type": "delete"},
        {"change_type": "rename"},
        {"requires_human_review": False},
        {"rationale": "   "},
        {"risks": [""]},
        {"content_text": "has a \x00 NUL"},
    ],
)
def test_proposed_change_rejects_bad_field_values(overrides):
    with pytest.raises(DiffProposalInputValidationError):
        parse_proposed_content_input(_json(_proposed_dict([_change(**overrides)])))


def test_proposed_content_rejects_oversized_content():
    payload = _proposed_dict([_change(content="x" * 1_000_001)])

    with pytest.raises(DiffProposalInputValidationError) as excinfo:
        parse_proposed_content_input(_json(payload))

    assert "content_text" in str(excinfo.value)


def test_empty_proposed_changes_parse():
    assert parse_proposed_content_input(_json(_proposed_dict([]))).changes == []


# -- 10. the workspace-content packet parser -----------------------------------


def test_valid_packet_parses_including_fields_this_generator_ignores():
    packet = parse_workspace_content_packet(_json(_packet_dict()))

    assert packet.mode == "l2-read-workspace-files"
    assert packet.project.project_id == PROJECT_ID
    assert packet.approved_plan.issue_number == ISSUE_NUMBER
    assert packet.workspace_content.file_contents_read is True
    assert [item.original_plan_path for item in packet.workspace_content.items] == [
        PLAN_FILE_A,
        PLAN_FILE_B,
        PLAN_FILE_NEW,
    ]
    # The packet's own approval metadata is never lifted into anything.
    assert not hasattr(packet.approved_plan, "approved_by")


@pytest.mark.parametrize(
    "text",
    ["", "not json", "```json\n{}\n```", "[]", '"x"', "null", "42"],
)
def test_packet_requires_exactly_one_json_object(text):
    with pytest.raises(DiffProposalInputParseError):
        parse_workspace_content_packet(text)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda p: p.update(mode="l2-inspect-workspace"), id="wrong-mode"
        ),
        pytest.param(lambda p: p.pop("mode"), id="missing-mode"),
        pytest.param(lambda p: p.pop("project"), id="missing-project"),
        pytest.param(lambda p: p.pop("approved_plan"), id="missing-approved-plan"),
        pytest.param(
            lambda p: p.pop("workspace_content"), id="missing-workspace-content"
        ),
        pytest.param(lambda p: p["project"].update(project_id="  "), id="blank-id"),
        pytest.param(lambda p: p["project"].update(repo="not-owner-repo"), id="repo"),
        pytest.param(
            lambda p: p["approved_plan"].update(issue_number=0), id="issue-number"
        ),
        pytest.param(lambda p: p["approved_plan"].update(title=""), id="blank-title"),
    ],
)
def test_packet_rejects_a_wrong_mode_or_broken_identity(mutate):
    payload = _packet_dict()
    mutate(payload)

    with pytest.raises(DiffProposalInputValidationError):
        parse_workspace_content_packet(_json(payload))


@pytest.mark.parametrize(
    "overrides",
    [
        {"candidate_source": "somewhere_else"},
        {"file_contents_read": False},
        {"directories_listed": True},
        {"commands_run": True},
        {"model_called": True},
        {"diffs_generated": True},
        {"files_edited": True},
    ],
)
def test_packet_rejects_a_report_claiming_more_than_a_read(overrides):
    payload = _packet_dict()
    payload["workspace_content"].update(overrides)

    with pytest.raises(DiffProposalInputValidationError):
        parse_workspace_content_packet(_json(payload))


def test_packet_rejects_duplicate_items():
    payload = _packet_dict(
        [_read_item(PLAN_FILE_A, ORIGINAL_A), _read_item(PLAN_FILE_A, PROPOSED_A)]
    )

    with pytest.raises(DiffProposalInputValidationError) as excinfo:
        parse_workspace_content_packet(_json(payload))

    assert "duplicates are rejected" in str(excinfo.value)


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "invented_status"},
        {"kind": "symlink"},
        {"encoding": "latin-1"},
        {"bytes_read": -1},
        {"redaction_count": -1},
        {"size_bytes": -1},
        {"original_plan_path": "../outside.py"},
        {"canonical_relative_path": "C:/absolute.py"},
        {"apply": True},
        {"command_output": "ok"},
        {"workspace_path": "C:/dev/somewhere"},
        {"absolute_path": "C:/dev/somewhere/file.py"},
    ],
)
def test_packet_item_rejects_bad_or_extra_fields(overrides):
    payload = _packet_dict([_read_item(PLAN_FILE_A, ORIGINAL_A, **overrides)])

    with pytest.raises(DiffProposalInputValidationError):
        parse_workspace_content_packet(_json(payload))


def test_packet_parses_a_redacted_item_that_the_generator_later_refuses():
    """Parsing records the claim; refusing to diff it is the generator's job."""
    item = _read_item(
        PLAN_FILE_A, "api_key = '[REDACTED]'\n", redacted=True, redaction_count=1
    )
    packet = parse_workspace_content_packet(_json(_packet_dict([item])))

    assert packet.workspace_content.items[0].redacted is True
    with pytest.raises(DiffProposalGenerationError):
        _build(workspace_content=packet)


@pytest.mark.parametrize(
    "status",
    ["missing", "too_large", "binary_or_non_utf8", "skipped_total_limit"],
)
def test_packet_parses_non_read_statuses_that_cannot_be_modified(status):
    packet = parse_workspace_content_packet(
        _json(_packet_dict([_empty_item(PLAN_FILE_A, status)]))
    )

    assert packet.workspace_content.items[0].status == status
    with pytest.raises(DiffProposalGenerationError):
        _build(workspace_content=packet)


def test_packet_tolerates_unknown_container_keys_without_acting_on_them():
    payload = _packet_dict()
    payload["some_future_field"] = "ignored"
    payload["workspace_content"]["another_future_field"] = "ignored"

    packet = parse_workspace_content_packet(_json(payload))

    assert not hasattr(packet, "some_future_field")
    assert not hasattr(packet.workspace_content, "another_future_field")


# -- 11. no IO of any kind -----------------------------------------------------


def _detonate(monkeypatch):
    """Replace every IO entry point that matters with an exploding stub."""

    def boom(*args, **kwargs):
        raise AssertionError("the Phase 5E3 generator performed IO")

    for module, name in (
        (builtins, "open"),
        (os, "getenv"),
        (os.environ, "get"),
        (os, "stat"),
        (os, "lstat"),
        (os, "listdir"),
        (os, "scandir"),
        (os, "walk"),
        (os, "system"),
        (os.path, "exists"),
        (os.path, "realpath"),
        (os.path, "abspath"),
        (socket, "socket"),
        (socket, "create_connection"),
        (socket, "getaddrinfo"),
        (subprocess, "run"),
        (subprocess, "Popen"),
    ):
        monkeypatch.setattr(module, name, boom)


def test_generation_performs_no_file_env_network_or_process_io(monkeypatch):
    # Build the inputs first, then detonate: the parsers are covered separately.
    approved_plan = _approved_plan()
    project = _project()
    packet = _packet()
    proposed = _proposed()

    _detonate(monkeypatch)

    artifact = build_deterministic_diff_proposal(
        approved_plan=approved_plan,
        project=project,
        workspace_content=packet,
        proposed_content=proposed,
    )

    assert artifact.changes


def test_no_apply_cleanliness_check_is_performed(monkeypatch):
    """A diff whose context matches nothing real is still generated happily."""
    approved_plan = _approved_plan()
    project = _project()
    packet = _packet()
    proposed = _proposed()

    _detonate(monkeypatch)

    artifact = build_deterministic_diff_proposal(
        approved_plan=approved_plan,
        project=project,
        workspace_content=packet,
        proposed_content=proposed,
    )

    assert artifact.applies_cleanly_checked is False


def test_both_parsers_perform_no_io(monkeypatch):
    packet_text = _json(_packet_dict())
    proposed_text = _json(_proposed_dict())
    bad_text = "definitely not json"

    _detonate(monkeypatch)

    assert parse_workspace_content_packet(packet_text)
    assert parse_proposed_content_input(proposed_text)
    for parser in (parse_workspace_content_packet, parse_proposed_content_input):
        with pytest.raises(DiffProposalInputParseError):
            parser(bad_text)


def test_generation_writes_no_file(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())

    _build()

    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_plan_paths_are_never_opened(monkeypatch):
    opened: list[str] = []
    real_open = builtins.open

    def tracking_open(*args, **kwargs):
        if args:
            opened.append(str(args[0]))
        return real_open(*args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracking_open)

    _build()

    assert opened == []


# -- 12. the implementation module cannot reach a client, a shell, or a path ---


def test_generator_module_globals_are_inert():
    from ai_dev_orchestrator.diff_proposal import generator

    module_globals = vars(generator)
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


def test_generator_module_imports_no_transport_cli_shell_or_path():
    from ai_dev_orchestrator.diff_proposal import generator

    with open(generator.__file__, encoding="utf-8") as handle:
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
        "apply_patch",
        "git apply",
        "AIDO_LITELLM",
        "GITHUB_TOKEN",
    ):
        assert forbidden not in text, f"{forbidden!r} must not appear"


def test_generator_defines_no_apply_edit_or_command_error():
    from ai_dev_orchestrator.diff_proposal import generator

    for absent in (
        "DiffProposalApplyError",
        "DiffProposalEditError",
        "DiffProposalCommandError",
        "apply_diff_proposal",
        "write_diff_proposal",
        "PatchApplier",
        "L2Implementer",
    ):
        assert not hasattr(generator, absent)


def test_the_error_hierarchy_is_the_declared_one():
    assert issubclass(DiffProposalInputParseError, DiffProposalGenerationError)
    assert issubclass(DiffProposalInputValidationError, DiffProposalGenerationError)
    assert issubclass(DiffProposalGenerationError, Exception)


# -- Phase 5F2C: the generator computes exact image identities -----------------


def _sha256_of(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_a_modify_binds_the_exact_recorded_original_and_proposed_bytes():
    proposal = _build()
    change = proposal.changes[0]

    assert change.pre_image_sha256 == _sha256_of(ORIGINAL_A)
    assert change.post_image_sha256 == _sha256_of(PROPOSED_A)


def test_a_create_binds_a_null_pre_image_and_a_real_post_image():
    proposal = _build(
        proposed_content=_proposed(
            [_change(PLAN_FILE_NEW, CREATED_TEXT, change_type="create")]
        )
    )
    change = proposal.changes[0]

    assert change.pre_image_sha256 is None
    assert change.post_image_sha256 == _sha256_of(CREATED_TEXT)


def test_the_digests_are_over_unnormalized_bytes():
    """A trailing-newline-only difference is invisible in the diff, not in the digest.

    ``difflib`` works on ``splitlines()`` output, so a change that exists only in
    the file's terminal newline produces no diff at all. The post-image digest,
    computed over the exact bytes, still records it — which is exactly why a
    writer that applies the diff and re-hashes the result catches the
    disagreement instead of writing something nobody approved.
    """
    without_newline = PROPOSED_A.rstrip("\n")

    assert _sha256_of(PROPOSED_A) != _sha256_of(without_newline)

    proposal = _build(
        proposed_content=_proposed([_change(PLAN_FILE_A, without_newline)])
    )
    change = proposal.changes[0]

    assert change.post_image_sha256 == _sha256_of(without_newline)
    assert change.pre_image_sha256 == _sha256_of(ORIGINAL_A)


def test_crlf_content_is_hashed_as_written():
    crlf_original = "a\r\nb\r\n"
    crlf_proposed = "a\r\nB\r\n"
    packet = _packet(
        [
            _read_item(PLAN_FILE_A, crlf_original),
            _read_item(PLAN_FILE_B, ORIGINAL_B),
            _empty_item(PLAN_FILE_NEW, "missing"),
        ]
    )
    proposal = _build(
        workspace_content=packet,
        proposed_content=_proposed([_change(PLAN_FILE_A, crlf_proposed)]),
    )
    change = proposal.changes[0]

    assert change.pre_image_sha256 == _sha256_of(crlf_original)
    assert change.post_image_sha256 == _sha256_of(crlf_proposed)


def test_the_digests_are_deterministic():
    first = _build()
    second = _build()

    assert first.model_dump_json() == second.model_dump_json()
