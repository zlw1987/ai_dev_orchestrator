"""READ and EDIT semantics.

Read: exact bytes, CRLF preserved, SHA correct, per-file cap, aggregate cap, and
**no truncation ever** -- an over-cap file is refused, because a truncated read
would let the model edit against a picture that is missing content.

Edit: write-after-read, stale hash, zero match, multiple matches, unique match,
size caps, receipt update, witness refusal, and the absence of any create/delete/
rename path.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from ar2.capability import RunState, mint_capability
from ar2.candidate import evaluate_delegated_candidate
from ar2.fixtures import R1, R2
from ar2.operations import perform_edit, perform_read
from ar2.wire import (
    ERR_NO_UNIQUE_MATCH,
    ERR_REFUSED,
    ERR_STALE_BASE,
    ERR_TOO_LARGE,
)

from conftest import mint_for, tracked_manifest


# -- read ----------------------------------------------------------------------


def test_read_returns_exact_bytes_text_and_hash(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    outcome = perform_read(sed, state, "calc.py")
    assert outcome.ok is True
    on_disk = open(os.path.join(r1_repo.repo_root, "calc.py"), "rb").read()
    assert outcome.result["bytes"] == len(on_disk)
    assert outcome.result["sha256"] == hashlib.sha256(on_disk).hexdigest()
    assert outcome.result["text"] == on_disk.decode("utf-8")
    assert outcome.result["encoding"] == "utf-8"


def test_read_preserves_crlf_and_reports_it(git_executable):
    """Needs ``-c core.autocrlf=false`` per-invocation, which ``custom_repo``
    does not parameterize, so this builds directly on top of a FRESH authorized
    root -- never a pre-existing or caller-chosen one."""
    from ar2.fixtures import create_disposable_experiment_root, remove_disposable_tree

    authority = create_disposable_experiment_root(case_id="crlf")
    try:
        repo = Path(authority.repo_root)
        repo.mkdir()
        (repo / "windows.py").write_bytes(b"line one\r\nline two\r\n")
        (repo / "unix.py").write_bytes(b"line one\nline two\n")
        (repo / "test_x.py").write_bytes(b"def test_x():\n    assert True\n")
        # -c core.autocrlf=false so Git stores the bytes exactly as written.
        subprocess.run(
            [git_executable, "-c", "core.autocrlf=false", "init", "-b", "main", "-q"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            [git_executable, "-c", "core.autocrlf=false", "add", "-A"], cwd=repo, check=True
        )
        subprocess.run(
            [
                git_executable, "-c", "core.autocrlf=false", "-c", "user.name=T",
                "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "f",
            ],
            cwd=repo,
            check=True,
        )
        root = authority.repo_root
        sed = mint_capability(
            authority=authority,
            tracked_manifest=tracked_manifest(git_executable, root),
            protected_patterns=("test_*.py",),
            verification_witness_paths=("test_x.py",),
        )
        state = RunState(caps=sed.caps)
        windows = perform_read(sed, state, "windows.py")
        unix = perform_read(sed, state, "unix.py")
        assert windows.result["contains_crlf"] is True
        assert unix.result["contains_crlf"] is False
        assert windows.result["text"] == "line one\r\nline two\r\n"
        assert "\r\n" in windows.result["text"]
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_an_over_cap_file_is_refused_and_never_truncated(custom_repo, git_executable):
    body = "x = 1  # padding\n" * 20000  # comfortably over 256 KiB
    built = custom_repo(
        {
            "big.py": body,
            "small.py": "y = 2\n",
            "test_x.py": "def test_x():\n    assert True\n",
        },
        case_id="big",
    )
    root = built.repo_root
    sed = mint_capability(
        authority=built.authority,
        tracked_manifest=tracked_manifest(git_executable, root),
        protected_patterns=("test_*.py",),
        verification_witness_paths=("test_x.py",),
    )
    state = RunState(caps=sed.caps)
    outcome = perform_read(sed, state, "big.py")
    assert outcome.code == ERR_TOO_LARGE
    assert outcome.result is None
    # Nothing partial was recorded, and no budget was consumed for it.
    assert state.consumed.read_operations == 0
    assert "big.py" not in state.read_receipts


def test_the_aggregate_read_cap_bounds_total_volume(custom_repo, git_executable):
    from ar2.capability import CapDefinitions

    files = {f"m{index}.py": "z = 0\n" * 200 for index in range(4)}
    files["test_x.py"] = "def test_x():\n    assert True\n"
    built = custom_repo(files, case_id="aggregate")
    root = built.repo_root
    sed = mint_capability(
        authority=built.authority,
        tracked_manifest=tracked_manifest(git_executable, root),
        protected_patterns=("test_*.py",),
        verification_witness_paths=("test_x.py",),
        caps=CapDefinitions(max_read_bytes_per_run=2500),
    )
    state = RunState(caps=sed.caps)
    codes = [perform_read(sed, state, f"m{i}.py").code for i in range(4)]
    assert codes[0] is None and codes[1] is None
    assert "budget_exhausted" in codes[2:]
    assert state.consumed.read_bytes <= 2500


# -- edit ----------------------------------------------------------------------


def test_edit_requires_a_prior_read(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    on_disk = open(os.path.join(r1_repo.repo_root, "calc.py"), "rb").read()
    digest = hashlib.sha256(on_disk).hexdigest()
    outcome = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=digest,  # even a CORRECT hash is not enough without a receipt
        old_text="return value < limit",
        new_text="return value <= limit",
    )
    assert outcome.code == ERR_REFUSED
    assert outcome.internal_reason == "write_after_read_precondition_unsatisfied"
    assert open(os.path.join(r1_repo.repo_root, "calc.py"), "rb").read() == on_disk


def test_a_stale_base_hash_is_refused(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    perform_read(sed, state, "calc.py")
    outcome = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256="a" * 64,
        old_text="return value < limit",
        new_text="return value <= limit",
    )
    assert outcome.code == ERR_STALE_BASE


def test_a_file_changed_since_the_read_is_refused_by_the_content_precondition(
    r1_repo, git_executable
):
    """The strongest check available without a transactional filesystem."""
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    read = perform_read(sed, state, "calc.py")
    digest = read.result["sha256"]
    # Something outside the broker changes the file after the read.
    target = os.path.join(r1_repo.repo_root, "calc.py")
    with open(target, "a", encoding="utf-8", newline="\n") as handle:
        handle.write("# changed by something else\n")
    outcome = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=digest,
        old_text="return value < limit",
        new_text="return value <= limit",
    )
    assert outcome.code == ERR_STALE_BASE
    assert outcome.internal_reason == "on_disk_bytes_do_not_match_presented_base"


def test_zero_matches_is_refused(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    read = perform_read(sed, state, "calc.py")
    outcome = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=read.result["sha256"],
        old_text="this text is absent",
        new_text="anything",
    )
    assert outcome.code == ERR_NO_UNIQUE_MATCH
    assert outcome.internal_reason == "occurrence_count_0"


def test_multiple_matches_is_refused(custom_repo, git_executable):
    built = custom_repo(
        {"dup.py": "a = 1\na = 1\n", "test_x.py": "def test_x():\n    assert True\n"},
        case_id="dup",
    )
    root = built.repo_root
    sed = mint_capability(
        authority=built.authority,
        tracked_manifest=tracked_manifest(git_executable, root),
        protected_patterns=("test_*.py",),
        verification_witness_paths=("test_x.py",),
    )
    state = RunState(caps=sed.caps)
    read = perform_read(sed, state, "dup.py")
    outcome = perform_edit(
        sed,
        state,
        "dup.py",
        base_sha256=read.result["sha256"],
        old_text="a = 1",
        new_text="a = 2",
    )
    assert outcome.code == ERR_NO_UNIQUE_MATCH
    assert outcome.internal_reason == "occurrence_count_2"
    assert open(os.path.join(root, "dup.py"), encoding="utf-8").read() == "a = 1\na = 1\n"


def test_an_empty_old_text_is_refused(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    read = perform_read(sed, state, "calc.py")
    outcome = perform_edit(
        sed, state, "calc.py", base_sha256=read.result["sha256"], old_text="", new_text="x"
    )
    assert outcome.code == ERR_NO_UNIQUE_MATCH
    assert outcome.internal_reason == "empty_old_text"


def test_a_unique_match_is_applied_byte_exactly(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    read = perform_read(sed, state, "calc.py")
    before = read.result["text"]
    outcome = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=read.result["sha256"],
        old_text="return value < limit",
        new_text="return value <= limit",
    )
    assert outcome.ok is True
    expected = before.replace("return value < limit", "return value <= limit")
    on_disk = open(os.path.join(r1_repo.repo_root, "calc.py"), "rb").read()
    assert on_disk == expected.encode("utf-8")
    assert outcome.result["bytes_after"] == len(on_disk)
    assert outcome.result["sha256_after"] == hashlib.sha256(on_disk).hexdigest()
    assert outcome.result["applied"] is True


def test_a_post_image_over_the_size_cap_is_refused(custom_repo, git_executable):
    from ar2.capability import CapDefinitions

    built = custom_repo(
        {"grow.py": "MARKER = 1\n", "test_x.py": "def test_x():\n    assert True\n"},
        case_id="grow",
    )
    root = built.repo_root
    sed = mint_capability(
        authority=built.authority,
        tracked_manifest=tracked_manifest(git_executable, root),
        protected_patterns=("test_*.py",),
        verification_witness_paths=("test_x.py",),
        caps=CapDefinitions(max_post_image_bytes=64),
    )
    state = RunState(caps=sed.caps)
    read = perform_read(sed, state, "grow.py")
    outcome = perform_edit(
        sed,
        state,
        "grow.py",
        base_sha256=read.result["sha256"],
        old_text="MARKER = 1",
        new_text="MARKER = " + "1" * 500,
    )
    assert outcome.code == ERR_TOO_LARGE
    assert outcome.internal_reason == "post_image_over_cap"
    assert open(os.path.join(root, "grow.py"), encoding="utf-8").read() == "MARKER = 1\n"


def test_write_byte_budget_is_enforced(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    read = perform_read(sed, state, "calc.py")
    state.consumed.write_bytes = sed.caps.max_write_bytes_per_run
    outcome = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=read.result["sha256"],
        old_text="return value < limit",
        new_text="return value <= limit",
    )
    assert outcome.internal_reason == "write_byte_budget_exhausted"


def test_there_is_no_create_delete_or_rename_operation():
    """The operation set is closed: only read_file and edit_file exist."""
    import ar2.operations as operations_module
    from ar2.capability import OPERATION_CLASSES
    from ar2.wire import SUPPORTED_OPERATIONS

    assert OPERATION_CLASSES == frozenset({"read_file", "edit_file"})
    assert SUPPORTED_OPERATIONS == frozenset({"read_file", "edit_file"})
    exported = {n for n in dir(operations_module) if n.startswith("perform_")}
    assert exported == {"perform_read", "perform_edit"}


def test_edit_cannot_create_a_new_file(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    outcome = perform_edit(
        sed, state, "brand_new.py", base_sha256="0" * 64, old_text="a", new_text="b"
    )
    assert outcome.code == ERR_REFUSED
    assert not os.path.exists(os.path.join(r1_repo.repo_root, "brand_new.py"))


def test_edit_never_deletes_or_empties_a_file_on_refusal(r2_repo, git_executable):
    sed = mint_for(R2, git_executable, r2_repo)
    state = RunState(caps=sed.caps)
    target = os.path.join(r2_repo.repo_root, "shipping", "weights.py")
    before = open(target, "rb").read()
    read = perform_read(sed, state, "shipping/weights.py")
    for old, new in (("absent text", "x"), ("def ", "def ")):
        perform_edit(
            sed,
            state,
            "shipping/weights.py",
            base_sha256=read.result["sha256"],
            old_text=old,
            new_text=new,
        )
    assert open(target, "rb").read() == before


def test_two_distinct_files_consume_the_changed_file_budget_once_each(
    r2_repo, git_executable
):
    sed = mint_for(R2, git_executable, r2_repo)
    state = RunState(caps=sed.caps)
    for relative, old, new in (
        ("shipping/weights.py", "return grams // 1000 + 1", "return (grams + 999) // 1000"),
        ("shipping/labels.py", '"""Label rendering."""', '"""Label rendering (v2)."""'),
    ):
        read = perform_read(sed, state, relative)
        assert perform_edit(
            sed, state, relative, base_sha256=read.result["sha256"], old_text=old, new_text=new
        ).ok is True
    assert state.consumed.changed_files == 2
    assert sorted(state.mutated_paths) == ["shipping/labels.py", "shipping/weights.py"]


# -- FU-B: the path/handle identity revalidation is COMPLETE -------------------
#
# The pre-existing revalidation proved only that the second validation's
# RELATIVE-PATH STRING matched, and that the open handle's own fstat identity
# had not drifted from itself -- a tautology, since fstat on a still-open
# descriptor cannot observe anything else. Neither proved that the resolved
# PATH still names the same FILESYSTEM OBJECT the handle has open. This test
# forces that exact gap deterministically, by making the revalidation's
# ``resolved_path`` disagree with the open handle -- never by racing a real
# filesystem operation.


def test_a_path_that_resolves_elsewhere_between_open_and_revalidation_is_refused(
    r1_repo, git_executable, monkeypatch
):
    """Simulates the TOCTOU window deterministically: the pre-mutation
    revalidation reports a DIFFERENT resolved file than the one the handle has
    open. Neither file may be touched, and no run state may be mutated."""
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)

    decoy_path = os.path.join(r1_repo.repo_root, "decoy.py")
    with open(decoy_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("DECOY = 'not calc.py'\n")

    calc_before = open(os.path.join(r1_repo.repo_root, "calc.py"), "rb").read()
    decoy_before = open(decoy_path, "rb").read()

    read = perform_read(sed, state, "calc.py")
    assert read.ok is True

    calls = {"n": 0}
    real = evaluate_delegated_candidate

    def swap_resolved_path_on_second_call(sed_arg, operation, path_candidate):
        decision = real(sed_arg, operation, path_candidate)
        calls["n"] += 1
        if calls["n"] == 2 and decision.permitted:
            # The revalidation call: same relative path, same "permitted"
            # verdict, but resolved to a DIFFERENT file on disk -- exactly what
            # a rename-and-replace or delete-and-recreate in the TOCTOU window
            # would produce, without needing to actually race one.
            decision = dataclasses.replace(decision, resolved_path=decoy_path)
        return decision

    monkeypatch.setattr(
        "ar2.operations.evaluate_delegated_candidate", swap_resolved_path_on_second_call
    )

    outcome = perform_edit(
        sed,
        state,
        "calc.py",
        base_sha256=read.result["sha256"],
        old_text="return value < limit",
        new_text="return value <= limit",
    )

    assert outcome.ok is False
    assert outcome.code == ERR_REFUSED
    assert outcome.internal_reason == "resolved_path_no_longer_names_the_open_handle"

    # No truncate, no write, on EITHER file.
    assert open(os.path.join(r1_repo.repo_root, "calc.py"), "rb").read() == calc_before
    assert open(decoy_path, "rb").read() == decoy_before

    # No run-state mutation: no edit consumed, no receipt replaced, nothing
    # added to the mutated-paths list.
    assert state.consumed.edit_operations == 0
    assert state.consumed.write_bytes == 0
    assert state.mutated_paths == []
    assert state.read_receipts["calc.py"] == read.result["sha256"]
