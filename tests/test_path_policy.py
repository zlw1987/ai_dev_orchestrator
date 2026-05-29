"""Phase 1 tests: workspace path policy (pure, lexical — no real file access)."""

import pytest

from ai_dev_orchestrator.models import PathRulesConfig, WorkspacePolicyConfig
from ai_dev_orchestrator.workspace import (
    PathClassification,
    PathPolicy,
    PathPolicyError,
)

WORKSPACE = "C:/dev/mis_project"

RULES = PathRulesConfig(
    allowed_paths=["documents/**", "config/**", "requirements.txt", "manage.py"],
    protected_paths=["config/settings.py", "requirements.txt", "**/migrations/**"],
    forbidden_paths=[
        ".git",
        ".git/**",
        ".env",
        "*.pyc",
        "media",
        "media/**",
        "__pycache__/**",
        "**/__pycache__/**",
        ".ai_runs",
        ".ai_runs/**",
    ],
)


def make_policy(**policy_kwargs) -> PathPolicy:
    return PathPolicy(
        workspace_path=WORKSPACE,
        rules=RULES,
        policy=WorkspacePolicyConfig(**policy_kwargs),
    )


def test_outside_workspace_absolute_path_rejected():
    policy = make_policy()
    with pytest.raises(PathPolicyError):
        policy.normalize("C:/Windows/system32/cmd.exe")
    # A sibling that shares a prefix string but not a path component is outside.
    with pytest.raises(PathPolicyError):
        policy.normalize("C:/dev/mis_project_evil/secrets.txt")


def test_absolute_path_inside_workspace_is_relativized():
    policy = make_policy()
    assert policy.normalize("C:/dev/mis_project/documents/readme.md") == "documents/readme.md"


def test_path_traversal_rejected():
    policy = make_policy()
    with pytest.raises(PathPolicyError):
        policy.normalize("../../etc/passwd")
    with pytest.raises(PathPolicyError):
        policy.normalize("documents/../../escape.txt")


def test_forbidden_path_rejected_for_write():
    policy = make_policy()
    decision = policy.check_write(".env")
    assert decision.permitted is False
    assert decision.classification is PathClassification.FORBIDDEN


def test_protected_path_detected():
    policy = make_policy()
    assert policy.classify("config/settings.py") is PathClassification.PROTECTED
    decision = policy.check_write("config/settings.py")
    assert decision.permitted is False
    assert decision.requires_authorization is True
    # With explicit authorization the protected write is permitted.
    authorized = policy.check_write("config/settings.py", allow_protected=True)
    assert authorized.permitted is True


def test_allowed_path_accepted_for_write():
    policy = make_policy()
    decision = policy.check_write("documents/spec.md")
    assert decision.permitted is True
    assert decision.classification is PathClassification.ALLOWED


def test_unlisted_path_rejected_for_write():
    policy = make_policy()
    decision = policy.check_write("some/random/file.txt")
    assert decision.permitted is False
    assert decision.classification is PathClassification.UNLISTED


def test_forbidden_beats_allowed():
    # 'config/cache.pyc' matches allowed 'config/**' AND forbidden '*.pyc'.
    policy = make_policy()
    assert policy.classify("config/cache.pyc") is PathClassification.FORBIDDEN
    assert policy.check_write("config/cache.pyc").permitted is False


def test_unlisted_read_denied():
    policy = make_policy()
    decision = policy.check_read("some/random/file.txt")
    assert decision.permitted is False
    assert decision.classification is PathClassification.UNLISTED


def test_allowed_read_permitted():
    policy = make_policy()
    decision = policy.check_read("documents/spec.md")
    assert decision.permitted is True
    assert decision.classification is PathClassification.ALLOWED
    assert decision.requires_authorization is False


def test_protected_read_permitted_but_requires_authorization():
    policy = make_policy()
    decision = policy.check_read("config/settings.py")
    assert decision.permitted is True
    assert decision.requires_authorization is True
    assert decision.classification is PathClassification.PROTECTED


def test_forbidden_read_denied():
    policy = make_policy()
    decision = policy.check_read(".env")
    assert decision.permitted is False
    assert decision.classification is PathClassification.FORBIDDEN


def test_nested_pycache_path_is_forbidden():
    policy = make_policy()
    assert policy.classify("accounts/sub/__pycache__/x.pyc") is PathClassification.FORBIDDEN
    assert policy.check_read("accounts/sub/__pycache__/mod.py").permitted is False


def test_git_root_path_is_forbidden():
    policy = make_policy()
    assert policy.classify(".git") is PathClassification.FORBIDDEN
    assert policy.classify(".git/config") is PathClassification.FORBIDDEN


def test_ai_runs_root_path_is_forbidden():
    policy = make_policy()
    assert policy.classify(".ai_runs") is PathClassification.FORBIDDEN
    assert policy.classify(".ai_runs/run-1/log.txt") is PathClassification.FORBIDDEN


def test_allow_symlinks_flag_surfaced():
    assert make_policy(allow_symlinks=False).allow_symlinks is False
    assert make_policy(allow_symlinks=True).allow_symlinks is True
