"""IQ-3 (retry policy) fixture and no-change proof."""

from __future__ import annotations

import sys

import pytest

from ar2.fixtures import remove_disposable_tree
from qualification.corpus import IQ3_TASK, prompt_names_no_implementation_file
from qualification.fixtures import (
    build_task_repository,
    run_task_verification,
    validate_baseline,
)

from conftest import observed_changed_paths, rev_parse_head, tracked_manifest


@pytest.fixture()
def iq3_repo(git_executable: str):
    built = build_task_repository(IQ3_TASK, git_executable=git_executable)
    yield built
    remove_disposable_tree(built.experiment_root)


def test_iq3_builds_exact_tracked_path_shape(git_executable, iq3_repo):
    tracked = tracked_manifest(git_executable=git_executable, repo_root=iq3_repo.repo_root)
    assert tracked == (
        "NOTES.md",
        "retry/__init__.py",
        "retry/backoff.py",
        "retry/classify.py",
        "retry/log.py",
        "retry/policy.py",
        "tests/test_retry.py",
    )


def test_iq3_protected_witness_is_test_retry(iq3_repo):
    assert IQ3_TASK.verification_witness_paths == ("tests/test_retry.py",)


def test_iq3_expected_changed_paths_is_empty(iq3_repo):
    assert IQ3_TASK.expected_changed_paths == frozenset()


def test_iq3_prompt_does_not_claim_the_implementation_is_already_correct():
    # The prompt instructs conditional behavior ("...if it is already
    # correct, change nothing...") and must never reveal the answer to the
    # very question it asks the model to determine.
    assert "the implementation is already correct" not in IQ3_TASK.prompt.lower()
    assert "is already correct" in IQ3_TASK.prompt.lower()  # the conditional wording is present


def test_iq3_prompt_names_no_implementation_file():
    # Vacuously true (expected_changed_paths is empty), asserted anyway so a
    # future edit to the helper's semantics cannot silently stop checking IQ-3.
    assert prompt_names_no_implementation_file(IQ3_TASK)


def test_iq3_baseline_passes_completely(git_executable, iq3_repo):
    outcome = run_task_verification(IQ3_TASK, iq3_repo, python_executable=sys.executable)
    check = validate_baseline(IQ3_TASK, outcome)
    assert check.matches, check.detail
    assert outcome.passed
    assert not outcome.failed_node_ids


def test_iq3_byte_identical_no_change_is_the_expected_outcome(git_executable, iq3_repo):
    head_before = rev_parse_head(git_executable=git_executable, repo_root=iq3_repo.repo_root)

    # The correct implementation outcome for IQ-3 is a trusted, unmodified
    # tree: nothing is written here, matching what a correct "no edit"
    # candidate result would leave behind (the AR2 R4 no_change_observed shape).
    outcome = run_task_verification(IQ3_TASK, iq3_repo, python_executable=sys.executable)
    assert outcome.passed

    head_after = rev_parse_head(git_executable=git_executable, repo_root=iq3_repo.repo_root)
    assert head_after == head_before

    changed = observed_changed_paths(git_executable=git_executable, repo_root=iq3_repo.repo_root)
    assert changed == frozenset()


def test_iq3_task_revision_is_deterministic():
    from qualification.corpus import IQ3_BASELINE_CONTRACT, IQ3_CASE, QualificationTask

    rebuilt = QualificationTask(
        task_id="IQ-3", case=IQ3_CASE, baseline_contract=IQ3_BASELINE_CONTRACT
    )
    assert rebuilt.task_revision == IQ3_TASK.task_revision
