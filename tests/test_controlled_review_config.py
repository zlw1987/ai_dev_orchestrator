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
        _project(enabled=True, model="qwen3-coder-next")
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
    payload["controlled_review"] = {"enabled": True, "model": "reviewer-only-model"}
    project = ProjectConfig.model_validate(payload)

    assert check_controlled_review_gate(project).model == "reviewer-only-model"


def test_the_gate_reads_no_environment_variable(monkeypatch):
    """A gate failure must not depend on — or touch — the process environment."""
    import os

    def boom(*args, **kwargs):
        raise AssertionError("the review gate read the process environment")

    monkeypatch.setattr(os.environ, "get", boom)
    monkeypatch.setattr(os.environ.__class__, "__getitem__", lambda self, key: boom())

    assert check_controlled_review_gate(_project(enabled=True, model="m")).model == "m"
