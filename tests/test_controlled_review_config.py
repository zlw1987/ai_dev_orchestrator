"""Phase 5F2E tests: the ``controlled_review`` project-config block and its gate.

Config-shape and gate tests only. Nothing here reads an environment variable,
builds a client, opens a socket, touches a workspace, or launches a process.

The load-bearing properties: the block fails closed when absent, it holds no
credential of any kind, it is the **only** place a reviewer model may be named,
and ``real_model_planning`` never authorizes a review.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_dev_orchestrator.models import ControlledReviewConfig, ProjectConfig
from ai_dev_orchestrator.review import (
    ReviewRefusedError,
    check_controlled_review_gate,
)

BASE = {
    "project_id": "demo_project",
    "display_name": "Demo",
    "repo": {
        "workspace_path": "C:/never/touched",
        "github_repo": "demo/widgets",
        "branch_prefix": "ai/demo",
    },
}


# ALPHA-1A-FU1: a synthetic authorized reviewer endpoint. ``.invalid`` never
# resolves, and no real endpoint appears in this file.
ENDPOINT = {
    "scheme": "https",
    "host": "reviewer.invalid",
    "port": 443,
    "base_path": "/v1",
}


def _project(**review) -> ProjectConfig:
    payload = dict(BASE)
    if review:
        payload["controlled_review"] = review
    return ProjectConfig.model_validate(payload)


# =============================================================================
# Defaults and fail-closed behavior
# =============================================================================


def test_the_block_defaults_to_disabled_with_no_model():
    settings = ControlledReviewConfig()

    assert settings.enabled is False
    assert settings.model is None
    assert settings.provider == "litellm"


def test_an_absent_block_is_identical_to_an_explicitly_disabled_one():
    absent = _project()
    explicit = _project(enabled=False)

    assert absent.controlled_review.model_dump() == explicit.controlled_review.model_dump()


def test_the_block_rejects_unknown_fields():
    for extra in (
        {"api_key": "sk-not-a-real-key"},
        {"base_url": "http://endpoint.invalid"},
        # ALPHA-1A-FU1 added a structured ``endpoint`` AUTHORIZATION; a URL
        # string is still not accepted in its place.
        {"endpoint": "http://endpoint.invalid"},
        {"api_key_env": "AIDO_LITELLM_API_KEY"},
        {"prompt_template": "review this"},
        {"headers": {"X": "y"}},
        {"max_retries": 3},
        {"retry_count": 3},
        {"fixer": {"enabled": True}},
        {"allowed_models": ["a"]},
        {"send_full_file": True},
    ):
        with pytest.raises(ValidationError):
            ControlledReviewConfig(enabled=True, model="m", **extra)


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_blank_model_is_rejected_at_load(blank):
    with pytest.raises(ValidationError):
        ControlledReviewConfig(enabled=True, model=blank)


def test_a_blank_provider_is_rejected_at_load():
    with pytest.raises(ValidationError):
        ControlledReviewConfig(enabled=True, provider="  ", model="m")


def test_an_unsupported_provider_still_loads_so_other_commands_are_unaffected():
    """Shape at load, support at the gate — the Phase 5F2D executable precedent.

    A disabled or mis-set reviewer block must never make an unrelated command
    fail to load the project config.
    """
    project = _project(enabled=False, provider="openai", model="gpt-whatever")

    assert project.controlled_review.provider == "openai"


# =============================================================================
# The gate
# =============================================================================


def test_the_gate_returns_the_exact_configured_provider_and_model():
    authority = check_controlled_review_gate(
        _project(enabled=True, model="qwen3-coder-next", endpoint=ENDPOINT)
    )

    assert authority.model == "qwen3-coder-next"
    assert authority.provider == "litellm"


def test_an_absent_block_refuses():
    with pytest.raises(ReviewRefusedError) as excinfo:
        check_controlled_review_gate(_project())

    assert "opt-in error" in str(excinfo.value)


def test_a_disabled_block_refuses():
    with pytest.raises(ReviewRefusedError):
        check_controlled_review_gate(_project(enabled=False, model="m"))


def test_an_enabled_block_with_no_model_refuses():
    with pytest.raises(ReviewRefusedError) as excinfo:
        check_controlled_review_gate(_project(enabled=True))

    assert "model error" in str(excinfo.value)


@pytest.mark.parametrize("provider", ["openai", "anthropic", "LiteLLM", "litellm "])
def test_an_unsupported_provider_refuses_at_the_gate(provider):
    with pytest.raises(ReviewRefusedError) as excinfo:
        check_controlled_review_gate(
            _project(enabled=True, provider=provider, model="m")
        )

    assert "provider error" in str(excinfo.value)


def test_real_model_planning_does_not_authorize_review():
    """Planning authorization and review authorization are separate capabilities."""
    payload = dict(BASE)
    payload["real_model_planning"] = {
        "enabled": True,
        "allowed_models": ["some-planner-model"],
        "allow_prompt_audit_files": False,
    }
    project = ProjectConfig.model_validate(payload)

    with pytest.raises(ReviewRefusedError):
        check_controlled_review_gate(project)


def test_the_review_gate_ignores_the_planning_allowlist_entirely():
    """A model allowlisted for planning is not thereby a permitted reviewer."""
    payload = dict(BASE)
    payload["real_model_planning"] = {
        "enabled": True,
        "allowed_models": ["planner-only-model"],
        "allow_prompt_audit_files": False,
    }
    payload["controlled_review"] = {
        "enabled": True,
        "model": "reviewer-only-model",
        "endpoint": ENDPOINT,
    }
    project = ProjectConfig.model_validate(payload)

    assert check_controlled_review_gate(project).model == "reviewer-only-model"


def test_the_gate_reads_no_environment_variable(monkeypatch):
    """A gate failure must not depend on — or touch — the process environment."""
    import os

    def boom(*args, **kwargs):
        raise AssertionError("the review gate read the process environment")

    monkeypatch.setattr(os.environ, "get", boom)
    monkeypatch.setattr(os.environ.__class__, "__getitem__", lambda self, key: boom())

    assert (
        check_controlled_review_gate(
            _project(enabled=True, model="m", endpoint=ENDPOINT)
        ).model
        == "m"
    )


# =============================================================================
# ALPHA-1A-FU1 — controlled_review.endpoint (the reviewer egress authority)
# =============================================================================


def test_an_enabled_block_without_an_endpoint_loads_but_the_gate_refuses():
    project = _project(enabled=True, model="m")

    assert project.controlled_review.endpoint is None
    with pytest.raises(ReviewRefusedError) as excinfo:
        check_controlled_review_gate(project)

    message = str(excinfo.value)
    assert "endpoint authorization error" in message
    assert "controlled_review.endpoint" in message


def test_the_gate_returns_a_frozen_copy_of_the_endpoint_authority():
    from ai_dev_orchestrator.review import ReviewerEndpointAuthority

    authority = check_controlled_review_gate(
        _project(enabled=True, model="m", endpoint=ENDPOINT)
    )

    assert authority.endpoint == ReviewerEndpointAuthority(**ENDPOINT)
    with pytest.raises(Exception):
        authority.endpoint.port = 1  # type: ignore[misc]


def test_a_disabled_block_needs_no_endpoint():
    assert _project(enabled=False, model="m").controlled_review.endpoint is None


@pytest.mark.parametrize(
    "endpoint",
    [
        ENDPOINT,
        {**ENDPOINT, "scheme": "http", "port": 8000},
        {**ENDPOINT, "base_path": ""},
        {**ENDPOINT, "base_path": "/openai/v1"},
        {**ENDPOINT, "host": "10.0.0.7"},
        {**ENDPOINT, "host": "a-b.c-d.invalid"},
        {**ENDPOINT, "port": 1},
        {**ENDPOINT, "port": 65535},
    ],
)
def test_a_well_formed_endpoint_loads(endpoint):
    project = _project(enabled=True, model="m", endpoint=endpoint)
    assert project.controlled_review.endpoint.model_dump() == endpoint


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scheme", "HTTP"),
        ("scheme", "ftp"),
        ("scheme", ""),
        ("host", ""),
        ("host", "Reviewer.invalid"),
        ("host", "reviewer.invalid."),
        ("host", "-reviewer.invalid"),
        ("host", "reviewer-.invalid"),
        ("host", "re viewer.invalid"),
        ("host", "reviewer.invalid:443"),
        ("host", "user@reviewer.invalid"),
        ("host", "reviewer.invalid/v1"),
        ("host", "reviewer%2einvalid"),
        ("host", "xn--bcher-kva.invalid"),
        ("host", "bücher.invalid"),
        ("host", "::1"),
        ("host", "[::1]"),
        ("host", "127.1"),
        ("host", "2130706433"),
        ("host", "010.0.0.1"),
        ("host", "256.0.0.1"),
        ("host", "a" * 64 + ".invalid"),
        ("port", 0),
        ("port", 65536),
        ("port", -1),
        ("port", "443"),
        ("port", True),
        ("port", 443.0),
        ("port", None),
        ("base_path", "v1"),
        ("base_path", "/"),
        ("base_path", "/v1/"),
        ("base_path", "//v1"),
        ("base_path", "/v1//x"),
        ("base_path", "/./v1"),
        ("base_path", "/v1/.."),
        ("base_path", "/v1%2f"),
        ("base_path", "/v1?x=1"),
        ("base_path", "/v1#f"),
        ("base_path", "/v1\\x"),
        ("base_path", "/v 1"),
        ("base_path", None),
    ],
)
def test_a_malformed_endpoint_is_refused_at_load(field, value):
    with pytest.raises(ValidationError):
        _project(enabled=True, model="m", endpoint={**ENDPOINT, field: value})


@pytest.mark.parametrize("missing", ["scheme", "host", "port", "base_path"])
def test_every_endpoint_field_is_required(missing):
    endpoint = {key: value for key, value in ENDPOINT.items() if key != missing}
    with pytest.raises(ValidationError):
        _project(enabled=True, model="m", endpoint=endpoint)


@pytest.mark.parametrize(
    "extra",
    [
        {"url": "https://reviewer.invalid/v1"},
        {"base_url": "https://reviewer.invalid/v1"},
        {"api_key": "sk-not-a-real-key"},
        {"api_key_env": "AIDO_VLLM_API_KEY"},
        {"proxy": "http://proxy.invalid:3128"},
        {"query": "x=1"},
    ],
)
def test_the_endpoint_block_rejects_unknown_fields(extra):
    with pytest.raises(ValidationError):
        _project(enabled=True, model="m", endpoint={**ENDPOINT, **extra})


def test_the_endpoint_authority_is_checked_after_the_earlier_gate_rules():
    """An unsupported provider or missing model still names its own error."""
    with pytest.raises(ReviewRefusedError) as excinfo:
        check_controlled_review_gate(_project(enabled=True, provider="openai", model="m"))
    assert "provider error" in str(excinfo.value)

    with pytest.raises(ReviewRefusedError) as excinfo:
        check_controlled_review_gate(_project(enabled=True))
    assert "model error" in str(excinfo.value)
