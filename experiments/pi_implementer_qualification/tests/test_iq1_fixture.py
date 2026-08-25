"""IQ-1 (money rounding) fixture and baseline proof."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ar2.fixtures import remove_disposable_tree
from qualification.corpus import (
    IQ1_CORRECT_ROUNDING,
    IQ1_TASK,
    prompt_names_no_implementation_file,
)
from qualification.fixtures import (
    build_task_repository,
    run_task_verification,
    validate_baseline,
)

from conftest import observed_changed_paths, tracked_manifest


@pytest.fixture()
def iq1_repo(git_executable: str):
    built = build_task_repository(IQ1_TASK, git_executable=git_executable)
    yield built
    remove_disposable_tree(built.experiment_root)


def test_iq1_builds_exact_tracked_path_shape(git_executable, iq1_repo):
    tracked = tracked_manifest(git_executable=git_executable, repo_root=iq1_repo.repo_root)
    assert tracked == (
        "NOTES.md",
        "money/__init__.py",
        "money/format.py",
        "money/parse.py",
        "money/report.py",
        "money/rounding.py",
        "money/tax.py",
        "tests/test_money.py",
    )


def test_iq1_protected_witness_is_test_money(iq1_repo):
    assert IQ1_TASK.verification_witness_paths == ("tests/test_money.py",)


def test_iq1_expected_changed_paths_is_exactly_one_file(iq1_repo):
    assert IQ1_TASK.expected_changed_paths == frozenset({"money/rounding.py"})


def test_iq1_prompt_does_not_name_the_implementation_file():
    assert prompt_names_no_implementation_file(IQ1_TASK)
    assert "money/rounding.py" not in IQ1_TASK.prompt
    assert "rounding.py" not in IQ1_TASK.prompt


def test_iq1_baseline_defect_shape(git_executable, iq1_repo):
    outcome = run_task_verification(IQ1_TASK, iq1_repo, python_executable=sys.executable)
    check = validate_baseline(IQ1_TASK, outcome)
    assert check.matches, check.detail
    # Exactly the two seeded half-value failures; the third half-value case
    # (3.5 -> 4) and every non-half case already pass under the defect.
    assert len(outcome.failed_node_ids) == 2
    joined = " ".join(outcome.failed_node_ids)
    assert "test_round_half_up_positive_half_rounds_away_from_zero" in joined
    assert "test_round_half_up_negative_half_rounds_away_from_zero" in joined
    assert "test_round_half_up_another_positive_half_rounds_away_from_zero" not in joined


def test_iq1_known_correct_repair_passes(git_executable, iq1_repo):
    target = Path(iq1_repo.repo_root) / "money" / "rounding.py"
    target.write_text(IQ1_CORRECT_ROUNDING, encoding="utf-8", newline="\n")

    outcome = run_task_verification(IQ1_TASK, iq1_repo, python_executable=sys.executable)
    assert outcome.passed, outcome.output_text

    changed = observed_changed_paths(git_executable=git_executable, repo_root=iq1_repo.repo_root)
    assert changed == frozenset({"money/rounding.py"})


def test_iq1_task_revision_is_deterministic():
    from qualification.corpus import IQ1_BASELINE_CONTRACT, IQ1_CASE, QualificationTask

    rebuilt = QualificationTask(
        task_id="IQ-1", case=IQ1_CASE, baseline_contract=IQ1_BASELINE_CONTRACT
    )
    assert rebuilt.task_revision == IQ1_TASK.task_revision
