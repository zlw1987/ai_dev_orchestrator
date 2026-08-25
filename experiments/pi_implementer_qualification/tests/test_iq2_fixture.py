"""IQ-2 (sensor unit-conversion) fixture and two-file necessity proof."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ar2.fixtures import remove_disposable_tree
from qualification.corpus import (
    IQ2_CONVERT_FIXED,
    IQ2_PARSE_FIXED,
    IQ2_TASK,
    prompt_names_no_implementation_file,
)
from qualification.fixtures import (
    build_task_repository,
    run_task_verification,
    validate_baseline,
)

from conftest import observed_changed_paths, tracked_manifest


@pytest.fixture()
def iq2_repo(git_executable: str):
    built = build_task_repository(IQ2_TASK, git_executable=git_executable)
    yield built
    remove_disposable_tree(built.experiment_root)


def _parse_path(repo_root: str) -> Path:
    return Path(repo_root) / "units" / "parse.py"


def _convert_path(repo_root: str) -> Path:
    return Path(repo_root) / "units" / "convert.py"


def _report_path(repo_root: str) -> Path:
    return Path(repo_root) / "units" / "report.py"


def test_iq2_builds_exact_tracked_path_shape(git_executable, iq2_repo):
    tracked = tracked_manifest(git_executable=git_executable, repo_root=iq2_repo.repo_root)
    assert tracked == (
        "NOTES.md",
        "tests/test_units.py",
        "units/__init__.py",
        "units/convert.py",
        "units/labels.py",
        "units/parse.py",
        "units/report.py",
        "units/validate.py",
    )


def test_iq2_at_least_five_non_test_files(iq2_repo):
    non_test = [p for p in IQ2_TASK.case.files if not p.startswith("tests/") and p != "NOTES.md"]
    assert len(non_test) >= 5


def test_iq2_protected_witness_is_test_units(iq2_repo):
    assert IQ2_TASK.verification_witness_paths == ("tests/test_units.py",)


def test_iq2_expected_changed_paths_is_exactly_two_files(iq2_repo):
    assert IQ2_TASK.expected_changed_paths == frozenset({"units/parse.py", "units/convert.py"})


def test_iq2_prompt_does_not_name_the_implementation_files():
    assert prompt_names_no_implementation_file(IQ2_TASK)
    assert "units/parse.py" not in IQ2_TASK.prompt
    assert "units/convert.py" not in IQ2_TASK.prompt
    assert "parse.py" not in IQ2_TASK.prompt
    assert "convert.py" not in IQ2_TASK.prompt


def test_iq2_baseline_fails_both_independent_defects_and_integration(git_executable, iq2_repo):
    outcome = run_task_verification(IQ2_TASK, iq2_repo, python_executable=sys.executable)
    check = validate_baseline(IQ2_TASK, outcome)
    assert check.matches, check.detail
    assert len(outcome.failed_node_ids) == 3
    joined = " ".join(outcome.failed_node_ids)
    assert "test_parse_negative_reading" in joined
    assert "test_to_fahrenheit_rounding" in joined
    assert "test_report_negative_reading_end_to_end" in joined


def test_iq2_one_file_repair_a_parse_only_still_fails(git_executable, iq2_repo):
    _parse_path(iq2_repo.repo_root).write_text(IQ2_PARSE_FIXED, encoding="utf-8", newline="\n")

    outcome = run_task_verification(IQ2_TASK, iq2_repo, python_executable=sys.executable)
    assert not outcome.passed
    joined = " ".join(outcome.failed_node_ids)
    assert "test_to_fahrenheit_rounding" in joined
    assert "test_report_negative_reading_end_to_end" in joined
    assert "test_parse_negative_reading" not in joined


def test_iq2_one_file_repair_b_convert_only_still_fails(git_executable, iq2_repo):
    _convert_path(iq2_repo.repo_root).write_text(IQ2_CONVERT_FIXED, encoding="utf-8", newline="\n")

    outcome = run_task_verification(IQ2_TASK, iq2_repo, python_executable=sys.executable)
    assert not outcome.passed
    joined = " ".join(outcome.failed_node_ids)
    assert "test_parse_negative_reading" in joined
    assert "test_report_negative_reading_end_to_end" in joined
    assert "test_to_fahrenheit_rounding" not in joined


def test_iq2_integration_only_workaround_does_not_satisfy_contract(git_executable, iq2_repo):
    # Touch ONLY the already-correct integration file; leave both seeded
    # defects in place. The two unit tests bypass report.py entirely, so no
    # change confined to report.py can supply either missing behavior.
    report_path = _report_path(iq2_repo.repo_root)
    report_path.write_text(report_path.read_text(encoding="utf-8") + "\n# workaround attempt\n",
                            encoding="utf-8", newline="\n")

    outcome = run_task_verification(IQ2_TASK, iq2_repo, python_executable=sys.executable)
    assert not outcome.passed
    joined = " ".join(outcome.failed_node_ids)
    assert "test_parse_negative_reading" in joined
    assert "test_to_fahrenheit_rounding" in joined

    changed = observed_changed_paths(git_executable=git_executable, repo_root=iq2_repo.repo_root)
    assert changed == frozenset({"units/report.py"})
    assert not IQ2_TASK.expected_changed_paths.issubset(changed)


def test_iq2_both_correct_repairs_pass(git_executable, iq2_repo):
    _parse_path(iq2_repo.repo_root).write_text(IQ2_PARSE_FIXED, encoding="utf-8", newline="\n")
    _convert_path(iq2_repo.repo_root).write_text(IQ2_CONVERT_FIXED, encoding="utf-8", newline="\n")

    outcome = run_task_verification(IQ2_TASK, iq2_repo, python_executable=sys.executable)
    assert outcome.passed, outcome.output_text

    changed = observed_changed_paths(git_executable=git_executable, repo_root=iq2_repo.repo_root)
    assert changed == frozenset({"units/parse.py", "units/convert.py"})


def test_iq2_task_revision_is_deterministic():
    from qualification.corpus import IQ2_BASELINE_CONTRACT, IQ2_CASE, QualificationTask

    rebuilt = QualificationTask(
        task_id="IQ-2", case=IQ2_CASE, baseline_contract=IQ2_BASELINE_CONTRACT
    )
    assert rebuilt.task_revision == IQ2_TASK.task_revision
