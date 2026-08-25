"""Task-revision identity closure (Phase 5F3B-I1-FU1, item F).

``task_revision`` must change whenever ANYTHING that defines the task
changes -- including the structured baseline contract, which previously
lived only inside a validator function body and so could drift while the
revision stayed identical.

Every variant below is constructed with :func:`dataclasses.replace` on a
COPY; the real corpus values are never mutated, and the suite asserts that
at the end.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from qualification.corpus import (
    ALREADY_PASSING,
    REQUIRED_TASKS,
    SEEDED_FAILURE,
    BaselineContract,
    IQ1_BASELINE_CONTRACT,
    IQ1_CASE,
    IQ1_TASK,
    IQ2_TASK,
    IQ3_TASK,
    QualificationTask,
)


def _baseline_task() -> QualificationTask:
    return QualificationTask(
        task_id="IQ-1", case=IQ1_CASE, baseline_contract=IQ1_BASELINE_CONTRACT
    )


def test_rebuilding_an_unchanged_task_gives_an_identical_revision():
    assert _baseline_task().task_revision == IQ1_TASK.task_revision
    # Stable across repeated evaluation of the same object, too.
    assert IQ1_TASK.task_revision == IQ1_TASK.task_revision


def test_changing_one_file_body_changes_the_revision():
    mutated_files = dict(IQ1_CASE.files)
    mutated_files["money/tax.py"] = mutated_files["money/tax.py"] + "\n# incidental change\n"
    variant = replace(_baseline_task(), case=replace(IQ1_CASE, files=mutated_files))
    assert variant.task_revision != IQ1_TASK.task_revision


def test_changing_the_prompt_changes_the_revision():
    variant = replace(
        _baseline_task(), case=replace(IQ1_CASE, prompt=IQ1_CASE.prompt + " Please hurry.")
    )
    assert variant.task_revision != IQ1_TASK.task_revision


def test_changing_expected_changed_paths_changes_the_revision():
    variant = replace(
        _baseline_task(),
        case=replace(IQ1_CASE, expected_changed_paths=frozenset({"money/format.py"})),
    )
    assert variant.task_revision != IQ1_TASK.task_revision


def test_changing_the_baseline_expected_failure_contract_changes_the_revision():
    """The defect FU1 closes: this previously left the revision identical."""
    variant = replace(
        _baseline_task(),
        baseline_contract=BaselineContract(
            mode=SEEDED_FAILURE,
            expected_failing_node_patterns=(
                "test_round_half_up_positive_half_rounds_away_from_zero",
            ),
        ),
    )
    assert variant.task_revision != IQ1_TASK.task_revision


def test_changing_the_baseline_contract_mode_changes_the_revision():
    variant = replace(_baseline_task(), baseline_contract=BaselineContract(mode=ALREADY_PASSING))
    assert variant.task_revision != IQ1_TASK.task_revision


def test_changing_the_verification_command_changes_the_revision():
    variant = replace(
        _baseline_task(),
        case=replace(IQ1_CASE, verification_args=("-m", "pytest", "-q", "tests/test_money.py")),
    )
    assert variant.task_revision != IQ1_TASK.task_revision


def test_changing_the_protected_patterns_changes_the_revision():
    variant = replace(_baseline_task(), case=replace(IQ1_CASE, protected_patterns=("tests/*",)))
    assert variant.task_revision != IQ1_TASK.task_revision


def test_revision_is_prefixed_by_its_task_id():
    for task in REQUIRED_TASKS:
        assert task.task_revision.startswith(f"{task.task_id}@")


def test_the_three_task_revisions_are_distinct():
    revisions = {task.task_revision for task in REQUIRED_TASKS}
    assert len(revisions) == 3


def test_baseline_contract_rejects_incoherent_declarations():
    with pytest.raises(ValueError):
        BaselineContract(mode="whatever")
    with pytest.raises(ValueError):
        BaselineContract(mode=ALREADY_PASSING, expected_failing_node_patterns=("x",))
    with pytest.raises(ValueError):
        BaselineContract(mode=SEEDED_FAILURE, expected_failing_node_patterns=())


def test_the_real_corpus_was_not_mutated_by_any_variant_above():
    assert IQ1_TASK.baseline_contract is IQ1_BASELINE_CONTRACT
    assert IQ1_TASK.case is IQ1_CASE
    assert IQ1_TASK.baseline_contract.mode == SEEDED_FAILURE
    assert IQ2_TASK.baseline_contract.mode == SEEDED_FAILURE
    assert IQ3_TASK.baseline_contract.mode == ALREADY_PASSING
    assert IQ1_TASK.expected_changed_paths == frozenset({"money/rounding.py"})
