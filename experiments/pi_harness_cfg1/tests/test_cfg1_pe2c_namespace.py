"""PE-2c (R1, B10): the G9 bound execution-namespace precheck primitive (C-27).

Every results root is the synthetic, retargeted package directory under
``tmp_path`` (the suite's accepted ``_CAPTURED_PACKAGE_DIR`` seam). The
primitive is waste avoidance only: it creates nothing, writes nothing, never
calls ``establish_stage_output_authority`` and establishes no authority.
This is NOT the PE-6 launcher.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from pi_harness_cfg1 import execution_namespace, pi_fs_leaves, stage_output
from pi_harness_cfg1.execution_namespace import (
    BURNED_STAGE_EXECUTION_IDS,
    G9_BOUND_ID_INVALID,
    G9_EXECUTION_NAMESPACE_ABSENT,
    G9_EXECUTION_NAMESPACE_OCCUPIED,
    G9_EXECUTION_NAMESPACE_UNOBSERVABLE,
    G9_PRECHECK_CODES,
    precheck_bound_execution_namespace,
)
from pi_harness_cfg1.pi_fs_leaves import NoFollowObservation

_PACKAGE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture()
def results(cfg1_package_dir):
    root = cfg1_package_dir / "results"
    root.mkdir()
    return root


class _StrSubclass(str):
    pass


def test_c27_the_vocabulary_is_closed_and_the_signature_takes_only_the_id():
    assert G9_PRECHECK_CODES == {
        G9_EXECUTION_NAMESPACE_ABSENT,
        G9_BOUND_ID_INVALID,
        G9_EXECUTION_NAMESPACE_OCCUPIED,
        G9_EXECUTION_NAMESPACE_UNOBSERVABLE,
    }
    parameters = list(inspect.signature(precheck_bound_execution_namespace).parameters.values())
    assert [(p.name, p.kind) for p in parameters] == [("stage_execution_id", inspect.Parameter.POSITIONAL_ONLY)]
    assert BURNED_STAGE_EXECUTION_IDS == {"CFG1-S1-A1", "CFG1-S1-A2", "CFG1-S1-A3", "CFG1-S1-A4"}


def test_c27_an_absent_bound_namespace_passes_and_nothing_is_created(results, filesystem_spy):
    before = filesystem_spy.total_mutations
    assert precheck_bound_execution_namespace("CFG1-S1-PE6-FRESH") == G9_EXECUTION_NAMESPACE_ABSENT
    assert filesystem_spy.total_mutations == before
    assert not (results / "CFG1-S1-PE6-FRESH").exists()
    assert sorted(results.iterdir()) == []


@pytest.mark.parametrize(
    "bad",
    [
        "CFG1-S1-A1",
        "CFG1-S1-A2",
        "CFG1-S1-A3",
        "CFG1-S1-A4",
        "",
        "x" * 65,
        "..",
        "a/b",
        "a\\b",
        "C:x",
        "has space",
        "nul\x00",
        _StrSubclass("CFG1-S1-OK"),
        7,
        None,
        b"CFG1-S1-OK",
        True,
    ],
)
def test_c27_an_invalid_or_burned_id_is_refused_before_any_filesystem_access(bad, results, filesystem_spy):
    lstats = len(filesystem_spy.lstat_calls)
    observed: list[str] = []
    real = pi_fs_leaves.inspect_no_follow
    pi_fs_leaves_inspect = lambda path: (observed.append(path), real(path))[1]  # noqa: E731
    original = pi_fs_leaves.inspect_no_follow
    pi_fs_leaves.inspect_no_follow = pi_fs_leaves_inspect
    try:
        assert precheck_bound_execution_namespace(bad) == G9_BOUND_ID_INVALID
    finally:
        pi_fs_leaves.inspect_no_follow = original
    assert len(filesystem_spy.lstat_calls) == lstats
    assert observed == []


@pytest.mark.parametrize("occupant", ["directory", "file"])
def test_c27_an_occupied_namespace_is_refused(occupant, results, filesystem_spy):
    target = results / "CFG1-S1-PE6-FRESH"
    if occupant == "directory":
        target.mkdir()
    else:
        target.write_bytes(b"occupant")
    before = filesystem_spy.total_mutations
    assert precheck_bound_execution_namespace("CFG1-S1-PE6-FRESH") == G9_EXECUTION_NAMESPACE_OCCUPIED
    assert filesystem_spy.total_mutations == before


def test_c27_a_reparse_point_occupant_is_occupied_and_never_followed(results, tmp_path):
    from conftest import make_directory_redirect

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    try:
        make_directory_redirect(results / "CFG1-S1-PE6-FRESH", elsewhere)
    except OSError:
        pytest.skip("no directory redirect available on this platform")
    assert precheck_bound_execution_namespace("CFG1-S1-PE6-FRESH") == G9_EXECUTION_NAMESPACE_OCCUPIED


def test_c27_an_other_classification_is_occupied(results, monkeypatch):
    monkeypatch.setattr(pi_fs_leaves, "inspect_no_follow", lambda path: NoFollowObservation("other", None))
    assert precheck_bound_execution_namespace("CFG1-S1-PE6-FRESH") == G9_EXECUTION_NAMESPACE_OCCUPIED


@pytest.mark.parametrize(
    "leaf",
    [
        lambda path: (_ for _ in ()).throw(OSError("observation failed")),
        lambda path: "missing",
        lambda path: NoFollowObservation("vanished", None),
        lambda path: NoFollowObservation(_StrSubclass("missing"), None),
    ],
)
def test_c27_an_observation_failure_is_unobservable(leaf, results, monkeypatch):
    monkeypatch.setattr(pi_fs_leaves, "inspect_no_follow", leaf)
    assert precheck_bound_execution_namespace("CFG1-S1-PE6-FRESH") == G9_EXECUTION_NAMESPACE_UNOBSERVABLE


def test_c27_an_unprovable_results_root_is_unobservable_and_is_never_created(cfg1_package_dir):
    assert not (cfg1_package_dir / "results").exists()
    assert precheck_bound_execution_namespace("CFG1-S1-PE6-FRESH") == G9_EXECUTION_NAMESPACE_UNOBSERVABLE
    assert not (cfg1_package_dir / "results").exists()


def test_c27_the_root_comes_only_from_stage_outputs_audited_derivation(results, monkeypatch):
    calls: list[bool] = []
    real = stage_output._establish_results_root

    def _spy(*, create_if_absent):
        calls.append(create_if_absent)
        return real(create_if_absent=create_if_absent)

    monkeypatch.setattr(stage_output, "_establish_results_root", _spy)
    precheck_bound_execution_namespace("CFG1-S1-PE6-FRESH")
    assert calls == [False]


def test_c27_it_never_calls_establishment_or_writes(results, monkeypatch):
    monkeypatch.setattr(
        stage_output,
        "establish_stage_output_authority",
        lambda **_k: (_ for _ in ()).throw(AssertionError("establishment must never be called")),
    )
    assert precheck_bound_execution_namespace("CFG1-S1-PE6-FRESH") == G9_EXECUTION_NAMESPACE_ABSENT
    source = (_PACKAGE_DIR / "execution_namespace.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "establish_stage_output_authority" not in called
    for forbidden in ("mkdir", "makedirs", "open", "write_bytes", "write_text", "unlink", "rename", "rmdir", "remove"):
        assert forbidden not in called, forbidden


def test_c27_the_namespace_race_after_g9_remains_the_accepted_residual(results, make_authority):
    """R-NAMESPACE-RACE, stated not solved: a namespace created AFTER a passing
    precheck still makes establishment refuse -- independently fail-closed."""
    assert precheck_bound_execution_namespace("CFG1-S1-PE6-RACE") == G9_EXECUTION_NAMESPACE_ABSENT
    (results / "CFG1-S1-PE6-RACE").mkdir()  # another process wins the race
    with pytest.raises(stage_output.StageOutputAuthorityError) as excinfo:
        make_authority("CFG1-S1-PE6-RACE")
    assert excinfo.value.reason_code == "EXECUTION_DIRECTORY_EXISTS"


def test_c27_the_primitive_is_called_by_nothing_in_the_package():
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        if path.name == "execution_namespace.py":
            continue
        assert "precheck_bound_execution_namespace" not in path.read_text(encoding="utf-8"), path.name
        assert "execution_namespace" not in path.read_text(encoding="utf-8"), path.name
