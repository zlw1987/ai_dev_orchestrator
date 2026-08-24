"""CAPABILITY STATE -- the FU1 two-layer model, asserted rather than commented.

    SED                  IMMUTABLE       never expands, never contracts
    remaining budgets    NON-INCREASING  consumption only; never refilled
    terminal flags       MONOTONE        once terminal, terminal for the run
    OPERATIONALLY-       NOT MONOTONE    a read receipt can make an already
    INVOCABLE SET                        write-eligible path invocable

All three are true at once, and no test here asserts monotonic shrinkage of the
capability as a whole.
"""

from __future__ import annotations

import dataclasses

import pytest

from ar2.capability import (
    EDIT_FILE,
    READ_FILE,
    CapDefinitions,
    CapabilityMintError,
    ConsumedBudgets,
    RunState,
    mint_capability,
)
from ar2.fixtures import R1, R2
from ar2.operations import perform_edit, perform_read
from ar2.wire import ERR_BUDGET_EXHAUSTED, ERR_REFUSED

from conftest import mint_for


# -- SED immutability ----------------------------------------------------------


def test_sed_is_frozen_after_mint(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    with pytest.raises(dataclasses.FrozenInstanceError):
        sed.canonical_root = "somewhere else"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        sed.read_eligible = frozenset()  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        sed.caps = CapDefinitions()  # type: ignore[misc]


def test_sed_domains_are_frozensets_and_cannot_be_mutated_in_place(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    assert isinstance(sed.read_eligible, frozenset)
    assert isinstance(sed.write_eligible, frozenset)
    with pytest.raises(AttributeError):
        sed.read_eligible.add("smuggled.py")  # type: ignore[attr-defined]


def test_write_domain_is_a_proper_subset_of_the_read_domain(r1_repo, r2_repo, git_executable):
    for case, built in ((R1, r1_repo), (R2, r2_repo)):
        sed = mint_for(case, git_executable, built)
        assert sed.write_eligible < sed.read_eligible
        assert sed.write_eligible != sed.read_eligible
        assert sed.summary()["write_domain_is_proper_subset_of_read_domain"] is True


def test_mint_refuses_when_write_domain_would_equal_read_domain():
    """Needs no repository content on disk: mint_capability's proper-subset
    check runs on ``tracked_manifest`` strings, so a bare authorized root
    (mint_capability does not stat repo_root itself) is enough."""
    from ar2.fixtures import create_disposable_experiment_root, remove_disposable_tree

    authority = create_disposable_experiment_root(case_id="t")
    try:
        with pytest.raises(CapabilityMintError, match="PROPER subset"):
            mint_capability(
                authority=authority,
                tracked_manifest=("a.py", "b.py"),
                protected_patterns=(),
                verification_witness_paths=(),
            )
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_mint_refuses_a_root_that_is_the_orchestrator_repository():
    """The belt-and-braces denylist still refuses the orchestrator repository,
    and it does so BEFORE any marker-file access -- a claimed authority whose
    token is simply wrong (never validated against a real marker) is refused on
    the string check alone."""
    import ar2.capability as capability_module
    import os

    from ar2.capability import DisposableRootAuthority

    orchestrator = os.path.realpath(
        os.path.join(os.path.dirname(capability_module.__file__), "..", "..", "..")
    )
    forged_authority = DisposableRootAuthority(
        experiment_id="ar2-test",
        case_id="orchestrator-substitution-attempt",
        experiment_root=os.path.dirname(orchestrator),
        repo_root=orchestrator,
        repo_child_name=os.path.basename(orchestrator),
        nonce="irrelevant--the-denylist-check-runs-first",
    )
    with pytest.raises(CapabilityMintError, match="orchestrator repository"):
        mint_capability(
            authority=forged_authority,
            tracked_manifest=("a.py", "tests/test_a.py"),
            verification_witness_paths=("tests/test_a.py",),
        )


# -- run state -----------------------------------------------------------------


def test_read_receipt_makes_an_already_eligible_path_invocable_without_changing_the_sed(
    r1_repo, git_executable
):
    """The exact FU1 section 2 sequence, asserted end to end."""
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    domain_before = (sed.read_eligible, sed.write_eligible, sed.caps)

    # t0: calc.py is ALREADY in the static write eligibility domain...
    assert sed.is_write_eligible("calc.py")
    # ...and edit is refused anyway, for want of a read receipt.
    refused = perform_edit(
        sed, state, "calc.py", base_sha256="0" * 64, old_text="x", new_text="y"
    )
    assert refused.ok is False
    assert refused.code == ERR_REFUSED
    assert refused.internal_reason == "write_after_read_precondition_unsatisfied"

    # t1: a successful read records an AIDO-owned receipt.
    read = perform_read(sed, state, "calc.py")
    assert read.ok is True
    digest = read.result["sha256"]
    assert state.read_receipts["calc.py"] == digest

    # t2: the same edit is now authorized. The SED did not change.
    applied = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=digest,
        old_text="return value < limit",
        new_text="return value <= limit",
    )
    assert applied.ok is True
    assert (sed.read_eligible, sed.write_eligible, sed.caps) == domain_before


def test_edit_replaces_the_receipt_with_the_post_image_hash(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    read = perform_read(sed, state, "calc.py")
    first = read.result["sha256"]
    applied = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=first,
        old_text="return value < limit",
        new_text="return value <= limit",
    )
    post = applied.result["sha256_after"]
    assert post != first
    assert state.read_receipts["calc.py"] == post

    # A second edit therefore needs NO second read -- and no budget was refilled.
    second = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=post,
        old_text="return value <= limit",
        new_text="return value <= int(limit)",
    )
    assert second.ok is True
    assert state.consumed.read_operations == 1
    assert state.consumed.edit_operations == 2
    assert state.consumed.changed_files == 1


def test_budgets_are_never_refilled(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    perform_read(sed, state, "calc.py")
    perform_read(sed, state, "test_calc.py")
    snapshot = ConsumedBudgets(**state.consumed.as_dict())
    # Every later operation, successful or refused, only ever adds.
    perform_read(sed, state, "does_not_exist.py")
    assert state.consumed.read_operations >= snapshot.read_operations
    assert state.consumed.read_bytes >= snapshot.read_bytes
    assert not hasattr(state.consumed, "refill")
    assert not any("refill" in name for name in dir(state))


def test_read_operation_budget_is_enforced_and_is_a_dynamic_precondition(
    r1_repo, git_executable
):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    state.consumed.read_operations = sed.caps.max_read_operations_per_run
    outcome = perform_read(sed, state, "calc.py")
    assert outcome.code == ERR_BUDGET_EXHAUSTED
    # Exhausting a budget removes NO path from the domain.
    assert sed.is_read_eligible("calc.py")


def test_aggregate_read_byte_budget_is_enforced(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    state.consumed.read_bytes = sed.caps.max_read_bytes_per_run
    outcome = perform_read(sed, state, "calc.py")
    assert outcome.code == ERR_BUDGET_EXHAUSTED
    assert outcome.internal_reason == "aggregate_read_byte_budget_exhausted"


def test_changed_file_budget_is_enforced(r2_repo, git_executable):
    sed = mint_for(R2, git_executable, r2_repo)
    state = RunState(caps=sed.caps)
    editable = sorted(sed.write_eligible)
    assert len(editable) > sed.caps.max_changed_files_per_run

    changed = 0
    last_refusal = None
    for relative in editable:
        read = perform_read(sed, state, relative)
        assert read.ok is True
        body = read.result["text"]
        marker = body.splitlines()[0]
        outcome = perform_edit(
            sed,
            state,
            relative,
            base_sha256=read.result["sha256"],
            old_text=marker,
            new_text=marker + "  # touched",
        )
        if outcome.ok:
            changed += 1
        else:
            last_refusal = outcome
            break
    assert changed == sed.caps.max_changed_files_per_run
    assert last_refusal is not None
    assert last_refusal.code == ERR_BUDGET_EXHAUSTED
    assert last_refusal.internal_reason == "changed_file_budget_exhausted"


def test_edit_operation_budget_is_enforced(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    read = perform_read(sed, state, "calc.py")
    state.read_receipts["calc.py"] = read.result["sha256"]
    state.consumed.edit_operations = sed.caps.max_edit_operations_per_run
    outcome = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=read.result["sha256"],
        old_text="return value < limit",
        new_text="return value <= limit",
    )
    assert outcome.code == ERR_BUDGET_EXHAUSTED
    assert outcome.internal_reason == "edit_operation_budget_exhausted"


def test_terminal_flags_are_monotone(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    assert state.terminal is False
    state.mark_terminal("protocol_terminal")
    assert state.terminal is True
    state.mark_terminal("protocol_terminal")
    assert sorted(state.terminal_flags) == ["protocol_terminal"]
    assert state.terminal is True


def test_operationally_invocable_set_is_not_monotone(r1_repo, git_executable):
    """It may become satisfiable AND may become unsatisfiable, within a fixed SED."""
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)

    def invocable(op: str, path: str) -> bool:
        if op == READ_FILE:
            return sed.is_read_eligible(path) and state.read_budget_allows(1) is None
        return (
            sed.is_write_eligible(path)
            and state.has_read_receipt(path)
            and state.edit_budget_allows(path, 1) is None
        )

    assert invocable(EDIT_FILE, "calc.py") is False       # no receipt yet
    perform_read(sed, state, "calc.py")
    assert invocable(EDIT_FILE, "calc.py") is True        # became satisfiable
    state.consumed.edit_operations = sed.caps.max_edit_operations_per_run
    assert invocable(EDIT_FILE, "calc.py") is False       # became unsatisfiable
    assert sed.is_write_eligible("calc.py") is True       # the SED never moved
