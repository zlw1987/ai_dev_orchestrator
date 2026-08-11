"""Phase 5E1 tests: the deterministic patch proposal generator.

Everything here is built from **literal dicts** validated into models. No file
is read or written, no environment variable is read, no socket is opened, no
command is run, no patch or diff is generated, no file is edited, and no target
project workspace is read, listed, stat'd, or resolved. No path below names a
real project.

The generator under test is a pure function over two already-loaded objects, so
the IO tests assert that directly: ``builtins.open``, the ``os``
environment/filesystem entry points, ``socket``, and ``subprocess.Popen`` are
all replaced with detonators for the duration of a successful generation.
"""

from __future__ import annotations

import builtins
import copy
import os
import socket
import subprocess

import pytest

from ai_dev_orchestrator.handoff import (
    REQUIRED_APPROVAL_TEXT,
    ApprovedL1PlanArtifact,
)
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.patch_proposal import (
    PATCH_PROPOSAL_MODE,
    PATCH_PROPOSAL_SCHEMA_VERSION,
    PatchProposalArtifact,
    PatchProposalGenerationError,
    build_deterministic_patch_proposal,
    parse_patch_proposal_artifact,
)

PROJECT_ID = "acme_widgets"
REPO = "acme/widgets"
ISSUE_NUMBER = 42
TITLE = "Add currency formatting helper"

ALLOWED_PATH = "src/billing/format.py"
ALLOWED_TEST_PATH = "tests/test_format.py"
THIRD_PATH = "docs/billing.md"
FORBIDDEN_PATH = "external_auth/client.py"

# A workspace path that is a **string in a literal config only**: never created,
# never read, never resolved. It deliberately names nothing real.
WORKSPACE_PATH = "C:/nonexistent_test_workspace/acme_widgets"

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

VALID_CONFIG: dict = {
    "project_id": PROJECT_ID,
    "display_name": "Acme Widgets",
    "repo": {
        "workspace_path": WORKSPACE_PATH,
        "github_repo": REPO,
        "default_base_branch": "main",
        "branch_prefix": "ai/acme",
    },
    "workspace_policy": {
        "deny_outside_workspace": True,
        "allow_symlinks": False,
        "max_changed_files": 20,
    },
    "allowed_paths": ["src/**", "tests/**", "docs/**"],
    "forbidden_paths": [".git/**"],
}


def _approved_plan(**plan_overrides) -> ApprovedL1PlanArtifact:
    """Build a valid approved-plan artifact, with optional plan field overrides."""
    plan = copy.deepcopy(VALID_PLAN)
    plan.update(plan_overrides)
    return ApprovedL1PlanArtifact.model_validate(
        {
            "approval": copy.deepcopy(VALID_APPROVAL),
            "plan_provenance": copy.deepcopy(VALID_PLAN_PROVENANCE),
            "plan": plan,
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
        }
    )


def _project(**overrides) -> ProjectConfig:
    """Build a valid project config from a literal dict, with overrides."""
    config = copy.deepcopy(VALID_CONFIG)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return ProjectConfig.model_validate(config)


def _build(**overrides) -> PatchProposalArtifact:
    approved_plan = overrides.pop("approved_plan", None) or _approved_plan()
    project = overrides.pop("project", None) or _project()
    return build_deterministic_patch_proposal(
        approved_plan=approved_plan, project=project
    )


# -- 1. the happy path ---------------------------------------------------------


def test_valid_approved_plan_generates_a_patch_proposal_artifact():
    proposal = _build()

    assert isinstance(proposal, PatchProposalArtifact)
    assert proposal.schema_version == PATCH_PROPOSAL_SCHEMA_VERSION
    assert proposal.mode == PATCH_PROPOSAL_MODE
    assert proposal.requires_human_review is True


def test_generated_artifact_round_trips_through_the_phase_5e0_parser():
    proposal = _build()

    reparsed = parse_patch_proposal_artifact(proposal.model_dump_json())

    assert reparsed.model_dump() == proposal.model_dump()


def test_generation_is_deterministic_for_the_same_inputs():
    first = _build()
    second = _build()

    assert first.model_dump_json() == second.model_dump_json()


def test_approved_plan_snapshot_travels_through_unchanged():
    approved_plan = _approved_plan()
    before = approved_plan.model_dump()

    proposal = _build(approved_plan=approved_plan)

    assert proposal.approved_plan.model_dump() == before
    # The input object itself was not mutated either.
    assert approved_plan.model_dump() == before
    assert proposal.approved_plan.approval.approval_text == REQUIRED_APPROVAL_TEXT
    assert proposal.approved_plan.approval.approved_by == "operator@example.invalid"


# -- 2. path selection ---------------------------------------------------------


def test_one_likely_path_generates_one_modify_change():
    proposal = _build(approved_plan=_approved_plan(files_likely_to_change=[ALLOWED_PATH]))

    assert len(proposal.changes) == 1
    change = proposal.changes[0]
    assert change.path == ALLOWED_PATH
    assert change.change_type == "modify"
    assert change.requires_human_review is True
    assert "files_likely_to_change" in change.rationale
    assert "No file contents were read" in change.rationale
    assert len(change.proposed_steps) == 2
    assert change.risks


def test_multiple_paths_generate_multiple_changes_preserving_order():
    proposal = _build(
        approved_plan=_approved_plan(
            files_likely_to_change=[THIRD_PATH, ALLOWED_PATH, ALLOWED_TEST_PATH]
        )
    )

    assert [change.path for change in proposal.changes] == [
        THIRD_PATH,
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
    ]
    assert all(change.change_type == "modify" for change in proposal.changes)


def test_duplicate_likely_paths_are_deduped_preserving_first_position():
    proposal = _build(
        approved_plan=_approved_plan(
            files_likely_to_change=[
                ALLOWED_PATH,
                ALLOWED_TEST_PATH,
                ALLOWED_PATH,
                THIRD_PATH,
                ALLOWED_TEST_PATH,
            ]
        )
    )

    assert [change.path for change in proposal.changes] == [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
        THIRD_PATH,
    ]


def test_empty_files_likely_to_change_generates_a_valid_empty_proposal():
    proposal = _build(approved_plan=_approved_plan(files_likely_to_change=[]))

    assert proposal.changes == []
    assert any("no file paths" in item.lower() for item in proposal.assumptions)
    # Still a fully valid Phase 5E0 artifact.
    assert parse_patch_proposal_artifact(proposal.model_dump_json()).changes == []


def test_forbidden_paths_are_never_proposed():
    proposal = _build()

    proposed = [change.path for change in proposal.changes]
    assert FORBIDDEN_PATH not in proposed
    assert proposed == [ALLOWED_PATH, ALLOWED_TEST_PATH]
    # And the forbidden path is not smuggled in as an omitted path either.
    assert proposal.omitted_paths == []


def test_prose_fields_are_never_treated_as_candidate_paths():
    proposal = _build(
        approved_plan=_approved_plan(
            files_likely_to_change=[],
            proposed_steps=["src/steps_are_not_paths.py"],
            required_verification=["tests/verification_is_not_a_path.py"],
            risks=["src/risks_are_not_paths.py"],
            open_questions=["src/questions_are_not_paths.py"],
        )
    )

    assert proposal.changes == []


# -- 3. fail closed ------------------------------------------------------------


def test_path_listed_as_both_likely_and_forbidden_fails():
    approved_plan = _approved_plan(
        files_likely_to_change=[ALLOWED_PATH, FORBIDDEN_PATH],
        files_forbidden_or_out_of_scope=[FORBIDDEN_PATH],
    )

    with pytest.raises(PatchProposalGenerationError) as excinfo:
        _build(approved_plan=approved_plan)

    assert "self-contradicting" in str(excinfo.value)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.py",
        "/etc/passwd",
        "C:/Windows/system32/config.sys",
        "\\\\server\\share\\file.py",
        "src/../../escape.py",
        "src/stream.py:hidden",
        ".",
        "./src/format.py",
        "src//double.py",
        "src/trailing./file.py",
        "PROGRA~1/app.py",
        "   ",
    ],
)
def test_unsafe_path_in_files_likely_to_change_fails(unsafe_path):
    # A blank entry is rejected by L1Plan itself; every other form must be
    # rejected by the generator's artifact validation.
    try:
        approved_plan = _approved_plan(files_likely_to_change=[unsafe_path])
    except Exception:
        return

    with pytest.raises(PatchProposalGenerationError) as excinfo:
        _build(approved_plan=approved_plan)

    assert "validation" in str(excinfo.value)


def test_too_many_paths_for_max_changed_files_fails():
    paths = [f"src/module_{index}.py" for index in range(4)]
    approved_plan = _approved_plan(files_likely_to_change=paths)
    project = _project(workspace_policy={"max_changed_files": 3})

    with pytest.raises(PatchProposalGenerationError) as excinfo:
        _build(approved_plan=approved_plan, project=project)

    message = str(excinfo.value)
    assert "max_changed_files" in message
    assert "No proposal was generated" in message


def test_the_cap_counts_deduped_paths_not_raw_entries():
    approved_plan = _approved_plan(
        files_likely_to_change=[ALLOWED_PATH, ALLOWED_PATH, ALLOWED_TEST_PATH]
    )
    project = _project(workspace_policy={"max_changed_files": 2})

    proposal = _build(approved_plan=approved_plan, project=project)

    assert [change.path for change in proposal.changes] == [
        ALLOWED_PATH,
        ALLOWED_TEST_PATH,
    ]


def test_zero_max_changed_files_still_allows_an_empty_proposal():
    approved_plan = _approved_plan(files_likely_to_change=[])
    project = _project(workspace_policy={"max_changed_files": 0})

    assert _build(approved_plan=approved_plan, project=project).changes == []


@pytest.mark.parametrize(
    "config_overrides, expected_field",
    [
        pytest.param({"project_id": "a_different_project"}, "project_id", id="project"),
        pytest.param(
            {"repo": {"github_repo": "someone-else/widgets"}}, "repo", id="repo"
        ),
        pytest.param({"repo": {"github_repo": REPO.upper()}}, "repo", id="case-folded"),
    ],
)
def test_identity_mismatch_against_the_project_config_fails(
    config_overrides, expected_field
):
    with pytest.raises(PatchProposalGenerationError) as excinfo:
        _build(project=_project(**config_overrides))

    message = str(excinfo.value)
    assert "does not match this project config exactly" in message
    assert expected_field in message


def test_repo_mismatch_names_every_repo_bearing_field():
    with pytest.raises(PatchProposalGenerationError) as excinfo:
        _build(project=_project(repo={"github_repo": "someone-else/widgets"}))

    message = str(excinfo.value)
    for field in ("repo", "plan.repo", "plan_provenance.repo"):
        assert field in message


def test_errors_never_echo_plan_prose_or_the_approval_text():
    marker = "SENTINEL_PLAN_SUMMARY_PROSE"
    approved_plan = _approved_plan(
        summary=f"Format invoice totals. {marker}",
        files_likely_to_change=["../escape.py"],
    )

    with pytest.raises(PatchProposalGenerationError) as excinfo:
        _build(approved_plan=approved_plan)

    message = str(excinfo.value)
    assert marker not in message
    assert REQUIRED_APPROVAL_TEXT not in message
    assert "operator@example.invalid" not in message


def test_generation_error_is_a_plain_exception_and_not_an_apply_error():
    from ai_dev_orchestrator.patch_proposal import generator

    assert issubclass(PatchProposalGenerationError, Exception)
    for absent in (
        "PatchApplyError",
        "PatchEditError",
        "CommandExecutionError",
        "PatchProposalApplyError",
    ):
        assert not hasattr(generator, absent)


# -- 4. the artifact says what it is (and is not) ------------------------------


def test_generated_provenance_is_deterministic_and_manual_safe():
    provenance = _build().provenance

    assert provenance.engine == "deterministic"
    assert provenance.operation == "patch-proposal"
    assert provenance.real_call is False
    assert provenance.model is None
    assert provenance.generated_at is None
    assert provenance.project_id == PROJECT_ID
    assert provenance.repo == REPO
    assert provenance.issue_number == ISSUE_NUMBER
    assert provenance.title == TITLE


def test_provenance_does_not_inherit_the_plans_real_model_claim():
    # The wrapped plan was produced by a real model call. The *proposal* was
    # not, and its provenance describes the generator, not the planner.
    proposal = _build()

    assert proposal.approved_plan.plan_provenance.real_call is True
    assert proposal.approved_plan.plan_provenance.model == "fake-planner-model"
    assert proposal.provenance.real_call is False
    assert proposal.provenance.model is None


def test_the_three_did_not_happen_flags_are_all_false():
    proposal = _build()

    assert proposal.file_contents_read is False
    assert proposal.files_edited is False
    assert proposal.commands_run is False


def test_assumptions_state_the_limits_of_this_phase():
    assumptions = " ".join(_build().assumptions).lower()

    assert "no workspace contents were read" in assumptions
    assert "existence" in assumptions
    assert "change_type" in assumptions
    assert "modify" in assumptions


def test_risks_state_that_there_is_no_diff_and_no_content():
    risks = " ".join(_build().risks).lower()

    assert "no diff was generated" in risks
    assert "no file contents were read" in risks


def test_open_questions_are_copied_from_the_approved_plan_as_prose():
    proposal = _build()

    assert proposal.open_questions == list(VALID_PLAN["open_questions"])


def test_next_authorization_required_names_the_unauthorized_phases():
    text = _build().next_authorization_required

    assert "Phase 5D2/5E2" in text
    for action in (
        "reading file contents",
        "generating diffs",
        "editing files",
        "running commands",
        "committing",
        "pushing",
        "opening PRs",
    ):
        assert action in text


def test_the_artifact_has_no_diff_content_or_command_field():
    proposal = _build()
    payload = proposal.model_dump()

    for absent in (
        "diff",
        "unified_diff",
        "patch",
        "hunks",
        "edit_script",
        "content",
        "new_content",
        "old_content",
        "before",
        "after",
        "source",
        "command",
        "commands",
        "command_output",
        "stdout",
        "workspace_path",
        "prompt",
        "completion",
        "api_key",
        "base_url",
    ):
        assert absent not in payload
        assert absent not in PatchProposalArtifact.model_fields
        for change in proposal.changes:
            assert absent not in change.model_dump()

    for change in proposal.changes:
        assert set(change.model_dump()) == {
            "path",
            "change_type",
            "rationale",
            "proposed_steps",
            "risks",
            "requires_human_review",
        }


def test_serialized_proposal_carries_no_workspace_path_or_secret():
    text = _build().model_dump_json()

    for absent in (
        WORKSPACE_PATH,
        "nonexistent_test_workspace",
        "workspace_path",
        "api_key",
        "AIDO_LITELLM",
        "Bearer ",
        "http://",
    ):
        assert absent not in text


# -- 5. no IO of any kind ------------------------------------------------------


def test_generator_performs_no_file_env_network_or_process_io(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("the generator must perform no IO")

    for module, name in (
        (builtins, "open"),
        (os, "getenv"),
        (os.environ, "get"),
        (os, "stat"),
        (os, "lstat"),
        (os, "listdir"),
        (os, "scandir"),
        (os, "walk"),
        (os.path, "exists"),
        (os.path, "abspath"),
        (os.path, "realpath"),
        (socket, "socket"),
        (socket, "create_connection"),
        (socket, "getaddrinfo"),
        (subprocess, "Popen"),
        (subprocess, "run"),
    ):
        monkeypatch.setattr(module, name, _blocked)

    proposal = _build()

    assert len(proposal.changes) == 2


def test_generator_performs_no_io_on_the_failure_path_either(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("the generator must perform no IO")

    for module, name in (
        (builtins, "open"),
        (os, "getenv"),
        (os, "stat"),
        (os, "listdir"),
        (os.path, "realpath"),
        (socket, "socket"),
        (subprocess, "Popen"),
    ):
        monkeypatch.setattr(module, name, _blocked)

    with pytest.raises(PatchProposalGenerationError):
        _build(project=_project(project_id="a_different_project"))


def test_generator_prints_nothing(capsys):
    _build()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_generator_builds_no_client_and_calls_no_model(monkeypatch):
    import ai_dev_orchestrator.github.client as github_client
    import ai_dev_orchestrator.llm.client as llm_client
    import ai_dev_orchestrator.llm.config as llm_config

    def _blocked(*args, **kwargs):
        raise AssertionError("the generator must build no client")

    monkeypatch.setattr(github_client.GitHubClient, "__init__", _blocked)
    monkeypatch.setattr(llm_client.LLMClient, "__init__", _blocked)
    monkeypatch.setattr(llm_config, "load_llm_client_config_from_env", _blocked)

    assert _build().provenance.engine == "deterministic"


def test_generator_writes_no_file(tmp_path):
    before = sorted(item.name for item in tmp_path.iterdir())

    _build()

    assert sorted(item.name for item in tmp_path.iterdir()) == before


# -- 6. implementation source constraints --------------------------------------


def test_generator_module_imports_no_transport_cli_or_path_symbol():
    from ai_dev_orchestrator.patch_proposal import generator

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


def test_generator_module_source_names_no_forbidden_import():
    from ai_dev_orchestrator.patch_proposal import generator

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
        "AIDO_LITELLM",
        "GITHUB_TOKEN",
        "open(",
        "read_text",
        "write_text",
    ):
        assert forbidden not in text, f"{forbidden!r} must not appear"


def test_patch_proposal_package_exports_the_phase_5e1_surface():
    from ai_dev_orchestrator import patch_proposal

    assert sorted(patch_proposal.__all__) == [
        "PATCH_PROPOSAL_MODE",
        "PATCH_PROPOSAL_SCHEMA_VERSION",
        "PatchProposalArtifact",
        "PatchProposalChange",
        "PatchProposalError",
        "PatchProposalGenerationError",
        "PatchProposalParseError",
        "PatchProposalProvenance",
        "PatchProposalValidationError",
        "build_deterministic_patch_proposal",
        "parse_patch_proposal_artifact",
    ]

    # Still no applier, no loader, no writer, no implementer. Later phases.
    for absent in (
        "load_patch_proposal_artifact",
        "apply_patch_proposal",
        "write_patch_proposal",
        "generate_diff",
        "PatchApplier",
        "L2Implementer",
    ):
        assert not hasattr(patch_proposal, absent)
