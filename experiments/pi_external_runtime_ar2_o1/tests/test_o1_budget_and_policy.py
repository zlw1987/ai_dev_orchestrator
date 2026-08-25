"""Capability-limit reuse, witness protection, and the third-file budget refusal.

Every check here runs against AR2's OWN, unmodified capability/candidate/
operations primitives (``ar2.capability``, ``ar2.candidate``,
``ar2.operations``) -- O1 supplies no override, no larger cap, and no
alternate policy of any kind.
"""

from __future__ import annotations

from ar2.capability import CapDefinitions, MAX_CHANGED_FILES_PER_RUN, RunState
from ar2.operations import perform_edit, perform_read
from ar2.wire import ERR_BUDGET_EXHAUSTED, ERR_REFUSED

from conftest import mint_for_o1
from o1.fixture import EXPECTED_CHANGED_PATHS, THIRD_FILE_PROBE_PATH, VERIFICATION_WITNESS_PATHS

_EXPECTED_TWO = sorted(EXPECTED_CHANGED_PATHS)


def test_ar2_default_changed_file_cap_is_two_and_o1_does_not_override_it():
    assert MAX_CHANGED_FILES_PER_RUN == 2
    assert CapDefinitions().max_changed_files_per_run == 2


def test_o1_sed_caps_equal_the_unmodified_ar2_default(o1_repo, git_executable):
    sed = mint_for_o1(git_executable, o1_repo)
    assert sed.caps.as_dict() == CapDefinitions().as_dict()


def test_verification_witness_is_read_eligible_not_write_eligible(o1_repo, git_executable):
    sed = mint_for_o1(git_executable, o1_repo)
    for witness in VERIFICATION_WITNESS_PATHS:
        assert sed.is_read_eligible(witness)
        assert not sed.is_write_eligible(witness)


def test_edit_attempt_on_witness_is_refused_through_the_real_operation(o1_repo, git_executable):
    sed = mint_for_o1(git_executable, o1_repo)
    run_state = RunState(caps=sed.caps)
    witness = VERIFICATION_WITNESS_PATHS[0]

    read = perform_read(sed, run_state, witness)
    assert read.ok

    edit = perform_edit(
        sed,
        run_state,
        witness,
        base_sha256=read.result["sha256"],
        old_text="import",
        new_text="import",
    )
    assert not edit.ok
    assert edit.code == ERR_REFUSED
    assert edit.internal_reason == "verification_witness_is_never_writable"
    assert run_state.consumed.edit_operations == 0


_EDITS = {
    "subscription/normalize.py": (
        '"professional": "pro",',
        '"professional": "pro",\n    "enterprise": "enterprise",',
    ),
    "subscription/rates.py": (
        '"pro": 2500,',
        '"pro": 2500,\n    "enterprise": 6000,',
    ),
}


def _apply_real_edit(sed, run_state, path: str) -> None:
    read = perform_read(sed, run_state, path)
    assert read.ok, read.detail
    old_text, new_text = _EDITS[path]
    edit = perform_edit(
        sed, run_state, path, base_sha256=read.result["sha256"], old_text=old_text, new_text=new_text
    )
    assert edit.ok, edit.detail


def test_third_distinct_file_budget_is_refused_after_the_two_required_edits(
    o1_repo, git_executable
):
    sed = mint_for_o1(git_executable, o1_repo)
    run_state = RunState(caps=sed.caps)

    for path in _EXPECTED_TWO:
        _apply_real_edit(sed, run_state, path)
    assert sorted(run_state.mutated_paths) == _EXPECTED_TWO
    assert run_state.consumed.changed_files == 2

    read = perform_read(sed, run_state, THIRD_FILE_PROBE_PATH)
    assert read.ok

    third_edit = perform_edit(
        sed,
        run_state,
        THIRD_FILE_PROBE_PATH,
        base_sha256=read.result["sha256"],
        old_text="format_seat_label",
        new_text="format_seat_label",
    )
    assert not third_edit.ok
    assert third_edit.code == ERR_BUDGET_EXHAUSTED
    assert third_edit.internal_reason == "changed_file_budget_exhausted"
    # The refusal did not consume a slot, or mutate a third path.
    assert sorted(run_state.mutated_paths) == _EXPECTED_TWO
    assert run_state.consumed.changed_files == 2
