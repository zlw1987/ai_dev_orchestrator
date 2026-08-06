"""Phase 4J tests: the fail-closed real model planning gate (library only).

Nothing here reaches a real model or a real endpoint. Every HTTP interaction is
faked with ``httpx.MockTransport``, every environment value is a **literal dict**
injected into the gate (no ``AIDO_LITELLM_*`` is ever read from the real process
environment), every base URL uses a fake ``.invalid`` host, no audit file is
created, and no target project workspace is read, listed, stat'd, or resolved.

The ``LLMClient`` is always built by the *test* and injected; the gate itself
imports no transport and has no code path that could construct one.
"""

from __future__ import annotations

import builtins
import json
import os
import socket
import subprocess

import httpx
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.github.issue_parser import parse_issue_body
from ai_dev_orchestrator.github.models import GitHubIssue
from ai_dev_orchestrator.llm.client import LLMAuthError, LLMClient
from ai_dev_orchestrator.llm.config import LLMConfigError
from ai_dev_orchestrator.llm.models import LLMClientConfig
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.plan import (
    L1Plan,
    ModelPlannerPolicyError,
    ModelPlannerValidationError,
    RealModelPlanningGateError,
    build_real_model_provenance,
    check_real_model_planning_gate,
    create_real_model_l1_plan_with_gate,
    endpoint_host_from_base_url,
)

runner = CliRunner()

# A fake, non-routable-looking host. Nothing ever connects to it: MockTransport
# short-circuits every request before a socket could be created.
FAKE_BASE_URL = "http://fake-litellm.invalid/v1"
FAKE_HOST = "fake-litellm.invalid"
ALLOWED_MODEL = "fake-planner-model"
OTHER_ALLOWED_MODEL = "fake-planner-model-b"
ENV_DEFAULT_MODEL = "fake-env-default-model"
FAKE_API_KEY = "fake-key-not-a-real-secret"

ISSUE_BODY = """\
## Goal

Add a currency formatting helper for invoice totals.

## Current Context

Invoice totals are formatted inline in three different templates.

## Scope

Only `src/billing/format.py` and `tests/test_format.py`.

## Non-goals

- No changes to `external_auth/` or to the payment gateway client.

## Acceptance Criteria

- Totals render as `1,234.56`.

## Required Verification

- pytest -q
"""


def _env(**overrides) -> dict[str, str]:
    """A literal environment mapping. Never read from the real environment."""
    values = {
        "AIDO_LITELLM_BASE_URL": FAKE_BASE_URL,
        "AIDO_LITELLM_API_KEY": FAKE_API_KEY,
        # Deliberately different from the allowlisted model: the env default
        # must never select what is planned with.
        "AIDO_LITELLM_DEFAULT_MODEL": ENV_DEFAULT_MODEL,
        "AIDO_LITELLM_TIMEOUT_SECONDS": "5",
        "AIDO_LITELLM_MAX_RETRIES": "0",
    }
    for key, value in overrides.items():
        if value is None:
            values.pop(key, None)
        else:
            values[key] = value
    return values


def _issue(**overrides) -> GitHubIssue:
    values = {
        "number": 42,
        "title": "Add currency formatting helper",
        "body": ISSUE_BODY,
        "state": "open",
        "html_url": "https://github.example.invalid/demo/widgets/issues/42",
        "labels": ["enhancement"],
    }
    values.update(overrides)
    return GitHubIssue(**values)


def _project(real_model_planning: dict | None = None, **overrides) -> ProjectConfig:
    values = {
        "project_id": "demo_project",
        "display_name": "Demo Project",
        "repo": {
            # A configuration string only. No test resolves, stats, lists, or
            # reads this path.
            "workspace_path": "C:\\dev\\demo_project",
            "github_repo": "demo/widgets",
            "default_base_branch": "main",
            "branch_prefix": "ai/demo",
        },
        "allowed_paths": ["src/**", "tests/**"],
        "protected_paths": ["src/billing/**"],
        "forbidden_paths": [".git/**", ".env", "external_auth/**"],
    }
    if real_model_planning is not None:
        values["real_model_planning"] = real_model_planning
    values.update(overrides)
    return ProjectConfig(**values)


def _enabled_project(**block_overrides) -> ProjectConfig:
    block = {
        "enabled": True,
        "allowed_models": [ALLOWED_MODEL, OTHER_ALLOWED_MODEL],
        "allow_prompt_audit_files": False,
    }
    block.update(block_overrides)
    return _project(real_model_planning=block)


VALID_PAYLOAD = {
    "summary": "Add a currency formatting helper for invoice totals.",
    "scope_summary": "Only the billing formatter module and its tests.",
    "non_goals": ["No changes to the payment gateway client."],
    "proposed_steps": [
        "Review the issue goal, scope, and acceptance criteria.",
        "Describe the formatting helper needed inside the allowed paths.",
    ],
    "files_likely_to_change": ["src/billing/format.py", "tests/test_format.py"],
    "files_forbidden_or_out_of_scope": ["external_auth/**"],
    "required_verification": ["pytest -q"],
    "risks": ["The issue does not state the expected rounding behavior."],
    "open_questions": ["Which locale should the helper default to?"],
}


def _completion_text(**overrides) -> str:
    payload = dict(VALID_PAYLOAD)
    payload.update(overrides)
    return json.dumps(payload)


def _handler_returning(text: str, seen: list[dict] | None = None):
    """Build a MockTransport handler that echoes a fixed completion."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "model": ALLOWED_MODEL,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 2,
                    "total_tokens": 3,
                },
            },
        )

    return handler


def _fake_config() -> LLMClientConfig:
    """A config built entirely from literals — no environment read anywhere."""
    return LLMClientConfig(
        base_url=FAKE_BASE_URL,
        api_key=FAKE_API_KEY,
        default_model=ALLOWED_MODEL,
        timeout_seconds=5.0,
        max_retries=0,
    )


def _fake_client(text: str, seen: list[dict] | None = None) -> LLMClient:
    """An LLMClient over a MockTransport. Built by the test, never by the gate."""
    return LLMClient(
        _fake_config(),
        transport=httpx.MockTransport(_handler_returning(text, seen)),
        sleep=lambda _seconds: None,
    )


def _prebuilt_fake_client(text: str) -> LLMClient:
    """Same, but with the ``httpx.Client`` constructed up front.

    Used by the guard tests, so no httpx object is constructed while ``open`` /
    ``os.getenv`` / ``socket`` are monkeypatched to fail.
    """
    http_client = httpx.Client(transport=httpx.MockTransport(_handler_returning(text)))
    return LLMClient(_fake_config(), client=http_client, sleep=lambda _seconds: None)


def _exploding_client() -> LLMClient:
    """A client that fails the test if it is ever used."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the gate must fail before the client is used")

    return LLMClient(
        _fake_config(),
        transport=httpx.MockTransport(handler),
        sleep=lambda _seconds: None,
    )


def _status_client(status: int) -> LLMClient:
    """A client whose endpoint always returns ``status``."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "nope"})

    return LLMClient(
        _fake_config(),
        transport=httpx.MockTransport(handler),
        sleep=lambda _seconds: None,
    )


def _plan_with(client: LLMClient, **overrides) -> L1Plan:
    issue = overrides.pop("issue", None) or _issue()
    project = overrides.pop("project", None) or _enabled_project()
    kwargs = {
        "issue": issue,
        "parsed": parse_issue_body(issue.body),
        "project": project,
        "requested_model": ALLOWED_MODEL,
        "env": _env(),
        "client": client,
    }
    kwargs.update(overrides)
    return create_real_model_l1_plan_with_gate(**kwargs)


# -- 1. project opt-in fails closed -------------------------------------------


def test_missing_real_model_planning_block_fails_closed():
    # No block at all: identical to an explicitly disabled one (design §4.1).
    project = _project()

    assert project.real_model_planning.enabled is False
    with pytest.raises(RealModelPlanningGateError) as excinfo:
        check_real_model_planning_gate(
            project=project, requested_model=ALLOWED_MODEL, env=_env()
        )

    assert "does not enable real model planning" in str(excinfo.value)


def test_explicitly_disabled_block_fails_closed():
    project = _project(
        real_model_planning={"enabled": False, "allowed_models": [ALLOWED_MODEL]}
    )

    with pytest.raises(RealModelPlanningGateError):
        check_real_model_planning_gate(
            project=project, requested_model=ALLOWED_MODEL, env=_env()
        )


def test_disabled_project_fails_before_the_environment_is_parsed():
    # A perfectly valid environment does not rescue a project that is not
    # opted in; the project check runs first.
    with pytest.raises(RealModelPlanningGateError):
        check_real_model_planning_gate(
            project=_project(), requested_model=ALLOWED_MODEL, env=_env()
        )

    # And an entirely empty environment still fails as a *gate* error, not a
    # config error — nothing about the env is even looked at.
    with pytest.raises(RealModelPlanningGateError):
        check_real_model_planning_gate(
            project=_project(), requested_model=ALLOWED_MODEL, env={}
        )


# -- 2. model allowlist fails closed ------------------------------------------


def test_enabled_with_empty_allowed_models_fails_closed():
    project = _enabled_project(allowed_models=[])

    with pytest.raises(RealModelPlanningGateError) as excinfo:
        check_real_model_planning_gate(
            project=project, requested_model=ALLOWED_MODEL, env=_env()
        )

    # An empty list means "no model", never "any model".
    assert "allowed_models is empty" in str(excinfo.value)


@pytest.mark.parametrize("requested", ["", "   ", "\t\n"])
def test_blank_requested_model_fails(requested):
    with pytest.raises(RealModelPlanningGateError) as excinfo:
        check_real_model_planning_gate(
            project=_enabled_project(), requested_model=requested, env=_env()
        )

    assert "non-blank model name" in str(excinfo.value)


@pytest.mark.parametrize(
    "requested",
    [
        "fake-planner-model-c",  # simply not listed
        "fake-planner",  # prefix of an allowed name
        "fake-planner-model-b-extra",  # allowed name is a prefix of this
        "FAKE-PLANNER-MODEL",  # case differs
        " fake-planner-model",  # leading whitespace
        "fake-planner-model ",  # trailing whitespace
        "fake-planner-model*",  # glob-looking
        "*",
    ],
)
def test_requested_model_must_match_allowlist_exactly(requested):
    with pytest.raises(RealModelPlanningGateError) as excinfo:
        check_real_model_planning_gate(
            project=_enabled_project(), requested_model=requested, env=_env()
        )

    assert "not in real_model_planning.allowed_models" in str(excinfo.value)


def test_allowlisted_model_passes_the_gate():
    config = check_real_model_planning_gate(
        project=_enabled_project(), requested_model=OTHER_ALLOWED_MODEL, env=_env()
    )

    assert isinstance(config, LLMClientConfig)
    assert config.default_model == OTHER_ALLOWED_MODEL


def test_duplicate_allowed_models_stay_config_level_validation():
    # Phase 4I rejects duplicates at config-construction time, so the gate never
    # sees such a config and needs no dedupe logic of its own.
    with pytest.raises(ValidationError) as excinfo:
        _project(
            real_model_planning={
                "enabled": True,
                "allowed_models": [ALLOWED_MODEL, ALLOWED_MODEL],
            }
        )

    assert "duplicate model name" in str(excinfo.value)


def test_credential_shaped_config_fields_stay_rejected_by_the_config_model():
    # Phase 4I's ``extra="forbid"`` is what keeps secrets out of project YAML;
    # the gate is not a place a credential can enter.
    for field in ("api_key", "base_url", "endpoint"):
        with pytest.raises(ValidationError):
            _project(
                real_model_planning={
                    "enabled": True,
                    "allowed_models": [ALLOWED_MODEL],
                    field: "should-not-be-here",
                }
            )


# -- 3. environment handling ---------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "AIDO_LITELLM_BASE_URL",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_DEFAULT_MODEL",
    ],
)
def test_missing_required_env_value_fails_before_client_use(name):
    with pytest.raises(LLMConfigError) as excinfo:
        create_real_model_l1_plan_with_gate(
            issue=_issue(),
            parsed=parse_issue_body(ISSUE_BODY),
            project=_enabled_project(),
            requested_model=ALLOWED_MODEL,
            env=_env(**{name: None}),
            # Using this client at all fails the test.
            client=_exploding_client(),
        )

    assert name in str(excinfo.value)


@pytest.mark.parametrize(
    "name",
    [
        "AIDO_LITELLM_BASE_URL",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_DEFAULT_MODEL",
    ],
)
def test_blank_env_value_fails_before_client_use(name):
    with pytest.raises(LLMConfigError):
        create_real_model_l1_plan_with_gate(
            issue=_issue(),
            parsed=parse_issue_body(ISSUE_BODY),
            project=_enabled_project(),
            requested_model=ALLOWED_MODEL,
            env=_env(**{name: "   "}),
            client=_exploding_client(),
        )


def test_gate_refuses_a_missing_env_mapping_instead_of_reading_the_process_env():
    with pytest.raises(RealModelPlanningGateError) as excinfo:
        check_real_model_planning_gate(
            project=_enabled_project(),
            requested_model=ALLOWED_MODEL,
            env=None,  # type: ignore[arg-type]
        )

    assert "never reads the process environment" in str(excinfo.value)


def test_env_default_model_cannot_bypass_the_project_allowlist():
    # The env names a model that is NOT allowlisted. It must not become usable
    # just because it is the connection default.
    env = _env(AIDO_LITELLM_DEFAULT_MODEL=ENV_DEFAULT_MODEL)
    project = _enabled_project()

    assert ENV_DEFAULT_MODEL not in project.real_model_planning.allowed_models

    with pytest.raises(RealModelPlanningGateError):
        check_real_model_planning_gate(
            project=project, requested_model=ENV_DEFAULT_MODEL, env=env
        )

    # Requesting an allowlisted model succeeds, and the returned config's model
    # is the requested one — the env default is neutralized, not honored.
    config = check_real_model_planning_gate(
        project=project, requested_model=ALLOWED_MODEL, env=env
    )
    assert config.default_model == ALLOWED_MODEL
    assert config.default_model != ENV_DEFAULT_MODEL
    # Connection details still come from the env.
    assert config.base_url == FAKE_BASE_URL
    assert config.timeout_seconds == 5.0
    assert config.max_retries == 0


def test_requested_model_not_env_default_is_sent_to_the_client():
    seen: list[dict] = []
    plan = _plan_with(_fake_client(_completion_text(), seen))

    assert isinstance(plan, L1Plan)
    assert len(seen) == 1
    assert seen[0]["model"] == ALLOWED_MODEL
    assert seen[0]["model"] != ENV_DEFAULT_MODEL


def test_gate_reads_only_the_injected_env_mapping(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("the gate must not read the process environment")

    monkeypatch.setattr(os, "getenv", _blocked)
    monkeypatch.setattr(os.environ, "get", _blocked)

    config = check_real_model_planning_gate(
        project=_enabled_project(), requested_model=ALLOWED_MODEL, env=_env()
    )

    assert config.default_model == ALLOWED_MODEL


# -- 4. endpoint host helper ---------------------------------------------------


@pytest.mark.parametrize(
    "base_url, expected",
    [
        ("http://litellm.internal/v1", "litellm.internal"),
        ("https://litellm.internal:8443/v1/chat/completions", "litellm.internal:8443"),
        ("https://litellm.internal", "litellm.internal"),
        ("  http://litellm.internal/v1  ", "litellm.internal"),
        ("http://litellm.internal/v1?token=abc123#frag", "litellm.internal"),
    ],
)
def test_endpoint_host_strips_everything_but_host_and_port(base_url, expected):
    assert endpoint_host_from_base_url(base_url) == expected


def test_endpoint_host_never_exposes_userinfo_path_or_query():
    secret = "sk-super-secret-key"
    base_url = f"https://admin:{secret}@litellm.internal:8443/v1/chat?api_key={secret}"

    host = endpoint_host_from_base_url(base_url)

    assert host == "litellm.internal:8443"
    for leaked in (secret, "admin", "/v1", "chat", "api_key", "?", "@"):
        assert leaked not in host


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "   ",
        "litellm.internal/v1",  # no scheme, so no host
        "not a url",
        "http://",
        "http://litellm.internal:notaport/v1",
    ],
)
def test_invalid_base_url_raises_a_gate_error(base_url):
    with pytest.raises(RealModelPlanningGateError):
        endpoint_host_from_base_url(base_url)


def test_invalid_base_url_error_never_echoes_the_url():
    secret = "sk-super-secret-key"
    with pytest.raises(RealModelPlanningGateError) as excinfo:
        endpoint_host_from_base_url(f"http://admin:{secret}@host:notaport/v1")

    assert secret not in str(excinfo.value)


def test_gate_rejects_a_base_url_without_a_host():
    with pytest.raises(RealModelPlanningGateError):
        check_real_model_planning_gate(
            project=_enabled_project(),
            requested_model=ALLOWED_MODEL,
            env=_env(AIDO_LITELLM_BASE_URL="litellm.internal/v1"),
        )


def test_endpoint_host_helper_makes_no_network_call(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("the host helper must not touch the network")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "gethostbyname", _blocked)

    assert endpoint_host_from_base_url(FAKE_BASE_URL) == FAKE_HOST


# -- 5. audit_dir is a flag only ----------------------------------------------


def test_audit_dir_without_the_project_flag_fails():
    with pytest.raises(RealModelPlanningGateError) as excinfo:
        check_real_model_planning_gate(
            project=_enabled_project(allow_prompt_audit_files=False),
            requested_model=ALLOWED_MODEL,
            env=_env(),
            audit_dir="audit_out",
        )

    assert "allow_prompt_audit_files" in str(excinfo.value)


def test_audit_dir_with_the_project_flag_passes_the_gate_without_touching_disk(
    monkeypatch,
):
    def _blocked(*args, **kwargs):
        raise AssertionError("the gate must not touch the filesystem")

    monkeypatch.setattr(builtins, "open", _blocked)
    monkeypatch.setattr(os, "makedirs", _blocked)
    monkeypatch.setattr(os, "mkdir", _blocked)
    monkeypatch.setattr(os, "stat", _blocked)
    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os.path, "exists", _blocked)
    monkeypatch.setattr(os.path, "abspath", _blocked)
    monkeypatch.setattr(os.path, "realpath", _blocked)

    config = check_real_model_planning_gate(
        project=_enabled_project(allow_prompt_audit_files=True),
        requested_model=ALLOWED_MODEL,
        env=_env(),
        audit_dir="audit_out",
    )

    assert config.default_model == ALLOWED_MODEL


def test_blank_audit_dir_fails_even_when_auditing_is_allowed():
    with pytest.raises(RealModelPlanningGateError) as excinfo:
        check_real_model_planning_gate(
            project=_enabled_project(allow_prompt_audit_files=True),
            requested_model=ALLOWED_MODEL,
            env=_env(),
            audit_dir="   ",
        )

    assert "non-blank path" in str(excinfo.value)


def test_no_audit_dir_is_the_default_and_needs_no_flag():
    config = check_real_model_planning_gate(
        project=_enabled_project(allow_prompt_audit_files=False),
        requested_model=ALLOWED_MODEL,
        env=_env(),
    )

    assert config.default_model == ALLOWED_MODEL


# -- 6. the gated planner over a MockTransport-backed client ------------------


def test_gated_planner_returns_a_valid_l1_plan():
    plan = _plan_with(_fake_client(_completion_text()))

    assert isinstance(plan, L1Plan)
    assert plan.issue_number == 42
    assert plan.repo == "demo/widgets"
    assert plan.title == "Add currency formatting helper"
    assert plan.automation_level == "L1"
    assert plan.requires_human_approval is True
    assert plan.summary == VALID_PAYLOAD["summary"]
    assert plan.proposed_steps == VALID_PAYLOAD["proposed_steps"]
    # Project forbidden paths are merged in verbatim by the Phase 4F parser.
    assert plan.files_forbidden_or_out_of_scope == [
        ".git/**",
        ".env",
        "external_auth/**",
    ]


def test_gated_planner_fails_closed_for_a_disabled_project():
    with pytest.raises(RealModelPlanningGateError):
        _plan_with(_exploding_client(), project=_project())


def test_gated_planner_fails_closed_for_a_disallowed_model():
    with pytest.raises(RealModelPlanningGateError):
        _plan_with(_exploding_client(), requested_model="fake-planner-model-c")


@pytest.mark.parametrize(
    "trusted_field, value",
    [
        ("issue_number", 999),
        ("repo", "attacker/evil"),
        ("title", "Injected title"),
        ("automation_level", "L1"),
        ("requires_human_approval", False),
    ],
)
def test_gated_planner_rejects_model_supplied_trusted_fields(trusted_field, value):
    text = _completion_text(**{trusted_field: value})

    with pytest.raises(ModelPlannerValidationError) as excinfo:
        _plan_with(_fake_client(text))

    assert trusted_field in str(excinfo.value)
    # A parser failure is not a gate failure.
    assert not isinstance(excinfo.value, RealModelPlanningGateError)


@pytest.mark.parametrize(
    "overrides",
    [
        {"proposed_steps": ["Run the following command: pytest -q", "Report back."]},
        {"proposed_steps": ["Open a pull request with the formatting helper."]},
        {"proposed_steps": ["Create a branch ai/demo/currency-helper."]},
        {"risks": ["This plan can be applied without human approval."]},
        {"proposed_steps": ["Read the workspace files under C:/dev/demo to confirm."]},
    ],
)
def test_gated_planner_rejects_policy_violating_output(overrides):
    with pytest.raises(ModelPlannerPolicyError) as excinfo:
        _plan_with(_fake_client(_completion_text(**overrides)))

    assert not isinstance(excinfo.value, RealModelPlanningGateError)


def test_client_errors_propagate_and_are_not_converted_to_gate_errors():
    with pytest.raises(LLMAuthError) as excinfo:
        _plan_with(_status_client(401))

    assert not isinstance(excinfo.value, RealModelPlanningGateError)
    # The API key never appears in the error.
    assert FAKE_API_KEY not in str(excinfo.value)


# -- 7. provenance helper (pure, clock-free) ----------------------------------


def test_provenance_helper_is_pure_and_secret_free():
    issue, project = _issue(), _enabled_project()

    provenance = build_real_model_provenance(
        issue=issue,
        project=project,
        requested_model=ALLOWED_MODEL,
        endpoint_host=endpoint_host_from_base_url(FAKE_BASE_URL),
    )

    assert provenance == {
        "engine": "real-model",
        "real_call": True,
        "model": ALLOWED_MODEL,
        "endpoint_host": FAKE_HOST,
        "issue_number": 42,
        "repo": "demo/widgets",
        "title": "Add currency formatting helper",
        "project_id": "demo_project",
    }
    # Clock use is not authorized in Phase 4J.
    assert "generated_at" not in provenance
    # Deterministic, and never key- or path-bearing.
    assert provenance == build_real_model_provenance(
        issue=issue,
        project=project,
        requested_model=ALLOWED_MODEL,
        endpoint_host=FAKE_HOST,
    )
    serialized = json.dumps(provenance)
    assert FAKE_API_KEY not in serialized
    assert project.repo.workspace_path not in serialized


# -- 8. offline / isolation guarantees ----------------------------------------


def test_gated_planner_makes_no_real_network_call(monkeypatch):
    client = _prebuilt_fake_client(_completion_text())

    def _blocked(*args, **kwargs):
        raise AssertionError("the gate must not open a real socket")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "gethostbyname", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)

    plan = _plan_with(client)

    assert plan.issue_number == 42


def test_gated_planner_performs_no_file_or_workspace_io(monkeypatch):
    client = _prebuilt_fake_client(_completion_text())

    def _blocked(*args, **kwargs):
        raise AssertionError("the gate must not read files or the workspace")

    monkeypatch.setattr(builtins, "open", _blocked)
    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "stat", _blocked)
    monkeypatch.setattr(os.path, "exists", _blocked)
    monkeypatch.setattr(os.path, "isdir", _blocked)
    monkeypatch.setattr(os.path, "abspath", _blocked)
    monkeypatch.setattr(os.path, "realpath", _blocked)

    plan = _plan_with(client)

    # Path-like values stay plain, unresolved strings.
    assert plan.files_likely_to_change == VALID_PAYLOAD["files_likely_to_change"]


def test_gate_module_cannot_construct_a_client_or_reach_github():
    from ai_dev_orchestrator.plan import real_model_gate

    module_globals = vars(real_model_gate)
    for name in (
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "LLMClient",
        "GitHubClient",
        "GitHubError",
    ):
        assert name not in module_globals

    # The env loader is present, but only ever called with an injected mapping.
    assert "load_llm_client_config_from_env" in module_globals
    assert "os" not in module_globals


def test_gate_module_writes_nothing_and_fetches_nothing():
    from ai_dev_orchestrator.plan import real_model_gate

    source_names = set(vars(real_model_gate))
    for forbidden in ("open", "Path", "shutil", "tempfile", "urlopen", "urlretrieve"):
        assert forbidden not in source_names


# -- 9. no CLI behavior added -------------------------------------------------


def test_root_help_is_unchanged():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("version", "inspect-issue", "llm-smoke-test", "generate-plan"):
        assert command in result.stdout

    # Phase 4J wires nothing into the CLI.
    for absent in (
        "model-plan",
        "plan-from-model",
        "generate-model-plan",
        "real-model",
    ):
        assert absent not in result.stdout


def test_generate_plan_still_has_no_real_or_model_option():
    result = runner.invoke(app, ["generate-plan", "--help"])

    assert result.exit_code == 0
    for absent in (
        "--live",
        "--real",
        "--real-model",
        "--model",
        "--use-env",
        "--github",
        "--fetch",
        "--audit-dir",
    ):
        assert absent not in result.stdout


def test_llm_smoke_test_is_unchanged_and_still_fake_only():
    result = runner.invoke(app, ["llm-smoke-test", "--help"])

    assert result.exit_code == 0
    for absent in ("--live", "--real", "--real-model", "--use-env", "--audit-dir"):
        assert absent not in result.stdout

    # Its pre-existing ``--model`` names a *fake* model for the in-process fake
    # provider; Phase 4J does not repurpose it.
    assert "Fake model name" in result.stdout
