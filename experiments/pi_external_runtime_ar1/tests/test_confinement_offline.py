"""Offline tests 19-23: the MANDATORY confinement negative test.

No model call. No network. No Pi process. The REAL Pi 0.84.2 tool factories are
loaded from an absolute path and driven by a Node harness, so what is exercised
is the same code path a model tool call would take -- with AIDO's guarded
operations wired in.

Topology (all under one temporary root):

    temp/
      repo/
        calc.py
        test_calc.py
      outside_canary.txt
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parents[1] / "extension" / "confinement_harness.ts"


@pytest.fixture(scope="module")
def confinement_result(tmp_path_factory, request):
    node = request.getfixturevalue("node_executable")
    pi_index = request.getfixturevalue("pi_dist_index")
    git = request.getfixturevalue("git_executable")

    from ar1.fixture import create_synthetic_repository

    root = tmp_path_factory.mktemp("ar1_confinement")
    fixture = create_synthetic_repository(
        str(root), git_executable=git, with_outside_canary=True
    )
    topology = {
        "cwd": fixture.repo_root,
        "repoDir": fixture.repo_root,
        "calcPath": fixture.calc_path,
        "testPath": fixture.test_path,
        "outsideCanaryPath": fixture.outside_canary_path,
    }
    topology_path = Path(fixture.experiment_root) / "topology.json"
    topology_path.write_text(json.dumps(topology), encoding="utf-8")

    completed = subprocess.run(
        [node, str(_HARNESS), pi_index, str(topology_path)],
        capture_output=True,
        check=False,
        timeout=180,
    )
    if completed.returncode != 0:  # pragma: no cover - surfaced as a failure
        pytest.fail(
            "confinement harness failed:\n"
            + completed.stderr.decode("utf-8", "replace")[-4000:]
        )
    payload = json.loads(completed.stdout.decode("utf-8"))
    payload["_topology"] = topology
    payload["_canary_text_after"] = Path(fixture.outside_canary_path).read_text(
        encoding="utf-8"
    )
    payload["_calc_text_after"] = Path(fixture.calc_path).read_text(encoding="utf-8")
    return payload


def test_tools_are_named_aido_read_and_aido_edit(confinement_result):
    assert confinement_result["tool_names"] == ["aido_read", "aido_edit"]


# -- 19. allowed reads ---------------------------------------------------------


def test_aido_read_allows_calc_py(confinement_result):
    case = confinement_result["cases"]["read_calc_allowed"]
    assert case["ok"] is True
    assert "within_limit" in case["text"]
    assert "readFile" in case["underlying_fs_calls"]


def test_aido_read_allows_test_calc_py(confinement_result):
    case = confinement_result["cases"]["read_test_allowed"]
    assert case["ok"] is True
    assert "within_limit" in case["text"]


def test_aido_read_allows_the_relative_spelling_of_an_allowed_file(confinement_result):
    case = confinement_result["cases"]["read_calc_relative_allowed"]
    assert case["ok"] is True


# -- 20. allowed edit ----------------------------------------------------------


def test_aido_edit_performs_the_allowed_synthetic_edit(confinement_result):
    case = confinement_result["cases"]["edit_calc_allowed"]
    assert case["ok"] is True
    assert "writeFile" in case["underlying_fs_calls"]
    assert "return value <= limit" in confinement_result["_calc_text_after"]


# -- 21/22. refusals -----------------------------------------------------------


def test_aido_read_refuses_the_outside_canary_absolute_path(confinement_result):
    case = confinement_result["cases"]["read_outside_canary_absolute_refused"]
    assert case["ok"] is False
    assert case["error_name"] == "AidoPathRefusedError"
    assert case["underlying_fs_calls"] == []


@pytest.mark.parametrize(
    "case_name", ["read_traversal_refused", "read_traversal_posix_refused"]
)
def test_aido_read_refuses_traversal_shaped_targets(confinement_result, case_name):
    case = confinement_result["cases"][case_name]
    assert case["ok"] is False
    assert case["error_name"] == "AidoPathRefusedError"
    assert case["underlying_fs_calls"] == []


def test_aido_edit_refuses_the_outside_canary(confinement_result):
    case = confinement_result["cases"]["edit_outside_canary_refused"]
    assert case["ok"] is False
    assert case["underlying_fs_calls"] == []
    assert "CANARY" in confinement_result["_canary_text_after"]
    assert "TOUCHED" not in confinement_result["_canary_text_after"]


def test_aido_edit_refuses_a_readable_but_non_editable_file(confinement_result):
    case = confinement_result["cases"]["edit_test_calc_refused"]
    assert case["ok"] is False
    assert case["underlying_fs_calls"] == []


# -- 23. refused operations never reach the filesystem implementation ----------


def test_no_refused_operation_reached_the_underlying_implementation(confinement_result):
    refused_cases = [
        name for name, case in confinement_result["cases"].items() if not case["ok"]
    ]
    assert refused_cases, "the harness must exercise at least one refusal"
    for name in refused_cases:
        assert confinement_result["cases"][name]["underlying_fs_calls"] == [], name
    assert confinement_result["audit_refusals"], "refusals must be audited"
    for refusal in confinement_result["audit_refusals"]:
        assert refusal["tool"] in ("aido_read", "aido_edit")
        assert "path" not in refusal  # a refused path is never retained


def test_every_underlying_filesystem_call_targeted_an_allowlisted_path(
    confinement_result,
):
    topology = confinement_result["_topology"]
    allowed = {
        os.path.normcase(topology["calcPath"]),
        os.path.normcase(topology["testPath"]),
    }
    for call in confinement_result["all_underlying_fs_call_paths"]:
        assert os.path.normcase(call["path"]) in allowed, call


def test_no_path_outside_the_temporary_experiment_root_was_referenced(
    confinement_result,
):
    topology = confinement_result["_topology"]
    experiment_root = os.path.normcase(os.path.dirname(topology["repoDir"]))
    for call in confinement_result["all_underlying_fs_call_paths"]:
        assert os.path.normcase(call["path"]).startswith(experiment_root), call
