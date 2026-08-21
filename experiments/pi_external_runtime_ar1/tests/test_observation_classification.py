"""Offline tests 24-28: independent Git observation and fail-closed classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from ar1.fixture import EXPECTED_CHANGED_PATH, create_synthetic_repository
from ar1.observation import (
    CLEAN_EXPECTED,
    HEAD_MOVED,
    INDEX_DIRTY,
    NO_CHANGE_OBSERVED,
    UNEXPECTED_CHANGE,
    UNEXPECTED_UNTRACKED,
    classify,
    diff_expected_path,
    observe_repository,
)

from conftest import run_git

EXPECTED = frozenset({EXPECTED_CHANGED_PATH})


@pytest.fixture()
def repo(tmp_path: Path, git_executable: str):
    return create_synthetic_repository(str(tmp_path), git_executable=git_executable)


def _observe(git_executable: str, repo):
    return observe_repository(git_executable=git_executable, workspace_root=repo.repo_root)


def test_pristine_fixture_shows_no_change(git_executable, repo):
    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
    )
    assert verdict.workspace_class == NO_CHANGE_OBSERVED
    assert verdict.changed_tracked_paths == []
    assert verdict.untracked_paths == []


# -- 24. the exact expected modification --------------------------------------


def test_exact_expected_modification_is_clean_expected(git_executable, repo):
    calc = Path(repo.calc_path)
    calc.write_text(
        calc.read_text(encoding="utf-8").replace("value < limit", "value <= limit"),
        encoding="utf-8",
        newline="\n",
    )
    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
    )
    assert verdict.workspace_class == CLEAN_EXPECTED
    assert verdict.trusted is True
    assert verdict.changed_tracked_paths == ["calc.py"]

    diff = diff_expected_path(
        git_executable=git_executable,
        workspace_root=repo.repo_root,
        repo_relative_path="calc.py",
    )
    assert "-    return value < limit" in diff
    assert "+    return value <= limit" in diff


# -- 25. HEAD moved ------------------------------------------------------------


def test_head_movement_makes_the_workspace_untrusted(git_executable, repo):
    calc = Path(repo.calc_path)
    calc.write_text(calc.read_text(encoding="utf-8") + "\n# touched\n", encoding="utf-8")
    run_git(git_executable, ["add", "--", "calc.py"], cwd=repo.repo_root)
    run_git(git_executable, ["commit", "--quiet", "-m", "moved"], cwd=repo.repo_root)

    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
    )
    assert verdict.workspace_class == HEAD_MOVED
    assert verdict.trusted is False
    assert verdict.head_moved is True


# -- 26. staged change ---------------------------------------------------------


def test_a_staged_change_makes_the_workspace_untrusted(git_executable, repo):
    calc = Path(repo.calc_path)
    calc.write_text(calc.read_text(encoding="utf-8") + "\n# staged\n", encoding="utf-8")
    run_git(git_executable, ["add", "--", "calc.py"], cwd=repo.repo_root)

    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
    )
    assert verdict.workspace_class == INDEX_DIRTY
    assert verdict.trusted is False
    assert verdict.staged_paths == ["calc.py"]


# -- 27. an unexpected tracked path --------------------------------------------


def test_an_unexpected_tracked_modification_is_refused(git_executable, repo):
    test_file = Path(repo.test_path)
    test_file.write_text(
        test_file.read_text(encoding="utf-8") + "\n# not allowed\n", encoding="utf-8"
    )
    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
    )
    assert verdict.workspace_class == UNEXPECTED_CHANGE
    assert verdict.trusted is False
    assert "test_calc.py" in verdict.changed_tracked_paths


def test_a_deleted_tracked_path_is_refused(git_executable, repo):
    Path(repo.calc_path).unlink()
    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
    )
    assert verdict.workspace_class == UNEXPECTED_CHANGE
    assert verdict.trusted is False


# -- 28. unexpected untracked paths --------------------------------------------


def test_an_unexpected_untracked_path_is_classified_not_ignored(git_executable, repo):
    (Path(repo.repo_root) / "scratch.txt").write_text("stray", encoding="utf-8")
    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
    )
    assert verdict.workspace_class == UNEXPECTED_UNTRACKED
    assert verdict.trusted is False
    assert "scratch.txt" in verdict.untracked_paths
    # It is enumerated for evidence, never auto-deleted.
    assert (Path(repo.repo_root) / "scratch.txt").is_file()


def test_a_tolerated_untracked_path_is_reported_but_permitted(git_executable, repo):
    calc = Path(repo.calc_path)
    calc.write_text(
        calc.read_text(encoding="utf-8").replace("value < limit", "value <= limit"),
        encoding="utf-8",
        newline="\n",
    )
    (Path(repo.repo_root) / "tolerated.txt").write_text("ok", encoding="utf-8")
    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
        tolerated_untracked_paths=frozenset({"tolerated.txt"}),
    )
    assert verdict.workspace_class == "dirty_benign"
    assert verdict.untracked_paths == ["tolerated.txt"]


# -- the configuration gate ----------------------------------------------------


def test_a_planted_repository_local_filter_key_is_config_poisoned(git_executable, repo):
    run_git(
        git_executable,
        ["config", "--local", "filter.evil.clean", "cmd"],
        cwd=repo.repo_root,
    )
    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
    )
    assert verdict.workspace_class == "config_poisoned"
    assert verdict.trusted is False
    assert "filter.evil.clean" in verdict.local_scope_unsupported_config_keys


def test_a_key_that_appears_only_after_the_baseline_is_poisoning(git_executable, repo):
    baseline = _observe(git_executable, repo)
    run_git(
        git_executable,
        ["config", "--local", "core.hookspath", "hooks"],
        cwd=repo.repo_root,
    )
    snapshot = _observe(git_executable, repo)
    verdict = classify(
        snapshot,
        workspace_root=repo.repo_root,
        head_before=repo.head_before,
        expected_changed_paths=EXPECTED,
        baseline=baseline,
    )
    assert verdict.workspace_class == "config_poisoned"
    assert "core.hookspath" in verdict.newly_unsupported_config_keys


def test_the_preflight_ordering_puts_every_gate_before_content_reads():
    from ai_dev_orchestrator.workspace.git_adapter import (
        CONTENT_READING_OPERATIONS,
        ordered_preflight_operations,
    )

    order = ordered_preflight_operations()
    first_content = min(
        index for index, name in enumerate(order) if name in CONTENT_READING_OPERATIONS
    )
    gates = {"config_list_local", "config_list_scoped", "ls_files_stage", "ls_files_verbose"}
    for gate in gates:
        assert order.index(gate) < first_content
