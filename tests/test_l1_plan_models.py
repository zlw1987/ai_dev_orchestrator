"""Phase 4B tests: typed L1Plan model validation.

Pure data-model tests. No file reads, no command execution, no GitHub or
model/network calls anywhere in this file.
"""

import pytest
from pydantic import ValidationError

from ai_dev_orchestrator.plan import L1Plan


def _minimal_kwargs(**overrides):
    kwargs = dict(
        issue_number=1,
        repo="owner/repo",
        title="Fix the thing",
        summary="Do the fix.",
        scope_summary="Only touch the thing module.",
        proposed_steps=["Update thing.py"],
        required_verification=["pytest -q"],
    )
    kwargs.update(overrides)
    return kwargs


def test_valid_minimal_plan_constructs():
    plan = L1Plan(**_minimal_kwargs())
    assert plan.issue_number == 1
    assert plan.repo == "owner/repo"
    assert plan.automation_level == "L1"
    assert plan.requires_human_approval is True
    assert plan.non_goals == []
    assert plan.files_likely_to_change == []
    assert plan.files_forbidden_or_out_of_scope == []
    assert plan.risks == []
    assert plan.open_questions == []


@pytest.mark.parametrize("issue_number", [0, -1])
def test_nonpositive_issue_number_fails(issue_number):
    with pytest.raises(ValidationError):
        L1Plan(**_minimal_kwargs(issue_number=issue_number))


@pytest.mark.parametrize("repo", ["", "   ", "no-slash", "owner/", "/repo", "a/b/c"])
def test_invalid_repo_fails(repo):
    with pytest.raises(ValidationError):
        L1Plan(**_minimal_kwargs(repo=repo))


@pytest.mark.parametrize("field", ["title", "summary", "scope_summary"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_required_string_fields_fail(field, blank):
    with pytest.raises(ValidationError):
        L1Plan(**_minimal_kwargs(**{field: blank}))


def test_empty_proposed_steps_fails():
    with pytest.raises(ValidationError):
        L1Plan(**_minimal_kwargs(proposed_steps=[]))


def test_empty_required_verification_fails():
    with pytest.raises(ValidationError):
        L1Plan(**_minimal_kwargs(required_verification=[]))


@pytest.mark.parametrize(
    "field",
    [
        "non_goals",
        "proposed_steps",
        "files_likely_to_change",
        "files_forbidden_or_out_of_scope",
        "required_verification",
        "risks",
        "open_questions",
    ],
)
@pytest.mark.parametrize("blank_item", ["", "   "])
def test_list_fields_reject_blank_items(field, blank_item):
    with pytest.raises(ValidationError):
        L1Plan(**_minimal_kwargs(**{field: [blank_item]}))


def test_automation_level_cannot_be_changed_to_l2():
    with pytest.raises(ValidationError):
        L1Plan(**_minimal_kwargs(automation_level="L2"))


def test_requires_human_approval_cannot_be_false():
    with pytest.raises(ValidationError):
        L1Plan(**_minimal_kwargs(requires_human_approval=False))


def test_path_like_fields_remain_plain_strings():
    weird_path = "../outside/thing.py"
    plan = L1Plan(
        **_minimal_kwargs(
            files_likely_to_change=[weird_path, "src/thing.py"],
            files_forbidden_or_out_of_scope=["C:\\dev\\mis_project\\secret.py"],
        )
    )
    # Values are stored verbatim: no resolution, normalization, or stat().
    assert plan.files_likely_to_change[0] == weird_path
    assert plan.files_forbidden_or_out_of_scope == ["C:\\dev\\mis_project\\secret.py"]
    assert isinstance(plan.files_likely_to_change[0], str)


def test_importing_plan_package_does_no_io(monkeypatch):
    # Guard against accidental network/subprocess calls at import time. (Python's
    # own import machinery needs real file IO, so file opening is not blocked here.)
    import importlib
    import socket
    import subprocess

    def _blocked(*args, **kwargs):
        raise AssertionError("plan package import must not perform network/process IO")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)

    import ai_dev_orchestrator.plan as plan_module

    importlib.reload(plan_module)
