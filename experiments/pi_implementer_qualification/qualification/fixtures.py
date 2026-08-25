"""Disposable fixture construction and baseline validation (Phase 5F3B-I1, Sec. 12).

Every qualification fixture repository is built through
``ar2.fixtures.build_case_repository`` (which in turn always originates a
FRESH disposable root via ``ar2.fixtures.create_disposable_experiment_root``)
and torn down through ``ar2.fixtures.remove_disposable_tree`` -- the
identical accepted creation-time disposable-root authority pattern AR2/O1
use. Nothing here points a fixture at a pre-existing directory, and no real
AIDO/sibling project may ever become one: ``build_task_repository`` accepts
only a :class:`~qualification.corpus.QualificationTask`, whose ``case`` is a
:class:`~ar2.fixtures.CaseFixture` VALUE, not a caller-chosen path.

If a task's baseline does not match its frozen contract, the fixture is
INVALID and model behavior must not be classified against it (Sec. 15 /
Sec. 12 "Baseline contract"). ``BaselineCheck.matches`` is the fail-closed
gate a caller checks before treating a fixture as usable.
"""

from __future__ import annotations

from dataclasses import dataclass

from ar2.fixtures import BuiltFixture, build_case_repository, remove_disposable_tree
from ar2.verification import VerificationOutcome, run_verification

from .corpus import QualificationTask, evaluate_baseline_contract


def build_task_repository(task: QualificationTask, *, git_executable: str) -> BuiltFixture:
    """Build ONE task's disposable repository under a fresh, authorized root."""
    return build_case_repository(task.case, git_executable=git_executable)


def teardown_task_repository(built: BuiltFixture) -> dict[str, object]:
    """Remove one disposable fixture tree, verifying rather than assuming removal."""
    return remove_disposable_tree(built.experiment_root)


def run_task_verification(
    task: QualificationTask, built: BuiltFixture, *, python_executable: str
) -> VerificationOutcome:
    """Run the task's fixed, fixture-owned verification command once."""
    return run_verification(
        python_executable=python_executable,
        workspace_root=built.repo_root,
        args=task.case.verification_args,
    )


@dataclass(frozen=True)
class BaselineCheck:
    """Whether a built fixture's baseline verification matches its frozen contract."""

    task_id: str
    matches: bool
    detail: str


def validate_baseline(task: QualificationTask, outcome: VerificationOutcome) -> BaselineCheck:
    """The task's own declared baseline contract, evaluated against ``outcome``.

    A caller MUST check ``.matches`` before treating a fixture as valid for
    model-behavior classification: "If the baseline does not match the
    frozen task contract: fixture invalid; do not classify model behavior."

    The contract is the frozen :class:`~qualification.corpus.BaselineContract`
    that is also hashed into ``task.task_revision``, so a fixture cannot be
    validated against a different contract than the one its revision names.
    """
    matches, detail = evaluate_baseline_contract(task.baseline_contract, outcome)
    return BaselineCheck(task_id=task.task_id, matches=matches, detail=detail)
