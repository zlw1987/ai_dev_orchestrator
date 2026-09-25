"""OC-5: L3 consumes the baseline verification outcome by exact type only.

A malformed falsy ``passed`` used to satisfy "the seeded baseline failed" via
truthiness. Every malformed or unproven L3 baseline fact must refuse at L3,
BEFORE the L4 credential read. Synthetic repositories and doubles only.
"""

from __future__ import annotations

import ast
import inspect
import json

import pytest
from cfg1_doubles import (
    FakeVerificationOutcome,
    build_doubled_ports,
    seam_digests_all_match,
)

from pi_harness_cfg1 import run_executor
from pi_harness_cfg1.run_contract import Cfg1RunAdmission
from pi_harness_cfg1.run_executor import execute_cfg1_run
from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

MARKER = "hostile-marker-9d41"


@pytest.fixture()
def admission():
    block, position = _schedule_block_position("S1", 1)
    return Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="a" * 32,
    )


@pytest.fixture(autouse=True)
def _seam_digests(monkeypatch):
    seam_digests_all_match(monkeypatch)


class _Hostile:
    """Every conversion hook records itself; none may ever be invoked."""

    def __init__(self):
        self.touched = []

    def __bool__(self):
        self.touched.append("bool")
        raise RuntimeError(MARKER)

    def __int__(self):
        self.touched.append("int")
        raise RuntimeError(MARKER)

    def __index__(self):
        self.touched.append("index")
        raise RuntimeError(MARKER)

    def __eq__(self, other):
        self.touched.append("eq")
        return True

    __hash__ = object.__hash__

    def __repr__(self):
        return MARKER


class _FalsyBool:
    def __bool__(self):
        raise AssertionError("__bool__ must not be invoked")


class _RaisingMember:
    """A result whose named member raises on access."""

    def __init__(self, member, **rest):
        self._member = member
        self._rest = rest

    def __getattr__(self, name):
        if name == self._member:
            raise RuntimeError(MARKER)
        try:
            return self._rest[name]
        except KeyError:
            raise AttributeError(name) from None


class _Missing:
    """A result lacking one member entirely."""

    def __init__(self, **members):
        for key, value in members.items():
            setattr(self, key, value)


def _run(admission, git_executable, run_verification):
    reads = {"n": 0}
    calls = {"n": 0}

    def _read():
        reads["n"] += 1
        return ("http://127.0.0.1:1/v1", "synthetic-credential")

    def _verify(*, workspace_root, args):
        calls["n"] += 1
        return run_verification()

    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"run_verification": _verify, "read_connection": _read},
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    return outcome, reads, calls


def _assert_refused_at_l3(outcome, reads):
    obs = outcome.observations
    assert obs["pre_dispatch_refusal_code"] == "WORKSPACE_BASELINE_FAILED"
    assert obs["refused_at_step"] == "L3"
    assert reads["n"] == 0
    assert obs["dispatch_state"] == "NOT_ATTEMPTED"
    blob = json.dumps(obs, default=str) + repr(outcome.console_codes)
    assert MARKER not in blob


def test_exact_false_with_exact_int_return_code_proceeds_to_l4(
    admission, git_executable
):
    outcome, reads, calls = _run(
        admission, git_executable, lambda: FakeVerificationOutcome()
    )
    assert reads["n"] >= 1
    assert outcome.observations["refused_at_step"] != "L3"
    assert outcome.observations["verification_child_reaped_or_not_started"] is True


def test_passed_true_refuses(admission, git_executable):
    outcome, reads, _ = _run(
        admission,
        git_executable,
        lambda: FakeVerificationOutcome(return_code=0, passed=True),
    )
    _assert_refused_at_l3(outcome, reads)
    assert outcome.observations["verification_child_reaped_or_not_started"] is True


@pytest.mark.parametrize("value", [0, "", [], (), None, 0.0, "False"])
def test_malformed_falsy_or_foreign_passed_refuses(admission, git_executable, value):
    outcome, reads, _ = _run(
        admission,
        git_executable,
        lambda: FakeVerificationOutcome(return_code=1, passed=value),
    )
    _assert_refused_at_l3(outcome, reads)


def test_foreign_bool_object_is_never_invoked(admission, git_executable):
    outcome, reads, _ = _run(
        admission,
        git_executable,
        lambda: FakeVerificationOutcome(return_code=1, passed=_FalsyBool()),
    )
    _assert_refused_at_l3(outcome, reads)


def test_hostile_passed_object_conversions_never_invoked(admission, git_executable):
    hostile = _Hostile()
    outcome, reads, _ = _run(
        admission,
        git_executable,
        lambda: FakeVerificationOutcome(return_code=1, passed=hostile),
    )
    _assert_refused_at_l3(outcome, reads)
    assert hostile.touched == []


def test_passed_accessor_raises(admission, git_executable):
    outcome, reads, _ = _run(
        admission, git_executable, lambda: _RaisingMember("passed", return_code=1)
    )
    _assert_refused_at_l3(outcome, reads)
    # An exact int return code was still observed.
    assert outcome.observations["verification_child_reaped_or_not_started"] is True


def test_passed_missing(admission, git_executable):
    outcome, reads, _ = _run(
        admission, git_executable, lambda: _Missing(return_code=1)
    )
    _assert_refused_at_l3(outcome, reads)


@pytest.mark.parametrize("code", [None, True, False, "1", 1.0, b"1"])
def test_non_exact_return_code_is_unreaped_and_refuses(
    admission, git_executable, code
):
    outcome, reads, _ = _run(
        admission,
        git_executable,
        lambda: FakeVerificationOutcome(return_code=code, passed=False),
    )
    _assert_refused_at_l3(outcome, reads)
    obs = outcome.observations
    assert obs["verification_child_reaped_or_not_started"] is False
    assert obs["lifecycle_all_closed"] is False


def test_int_like_return_code_is_not_converted(admission, git_executable):
    hostile = _Hostile()
    outcome, reads, _ = _run(
        admission,
        git_executable,
        lambda: FakeVerificationOutcome(return_code=hostile, passed=False),
    )
    _assert_refused_at_l3(outcome, reads)
    assert hostile.touched == []
    assert outcome.observations["verification_child_reaped_or_not_started"] is False


def test_return_code_accessor_raises(admission, git_executable):
    outcome, reads, _ = _run(
        admission, git_executable, lambda: _RaisingMember("return_code", passed=False)
    )
    _assert_refused_at_l3(outcome, reads)
    assert outcome.observations["verification_child_reaped_or_not_started"] is False


def test_return_code_missing(admission, git_executable):
    outcome, reads, _ = _run(admission, git_executable, lambda: _Missing(passed=False))
    _assert_refused_at_l3(outcome, reads)
    assert outcome.observations["verification_child_reaped_or_not_started"] is False


def test_run_verification_raising_is_conservatively_unreaped(
    admission, git_executable
):
    def _boom():
        raise RuntimeError(MARKER)

    outcome, reads, calls = _run(admission, git_executable, _boom)
    _assert_refused_at_l3(outcome, reads)
    obs = outcome.observations
    assert calls["n"] == 1
    assert obs["verification_child_reaped_or_not_started"] is False
    assert obs["lifecycle_all_closed"] is False
    # OC-4 closure still ran: the genuine workspace was closed.
    assert obs["workspace_removed_verified"] is True


def test_exactly_one_baseline_call_on_refusal(admission, git_executable):
    _, _, calls = _run(
        admission,
        git_executable,
        lambda: FakeVerificationOutcome(return_code=0, passed=True),
    )
    assert calls["n"] == 1


def test_source_audit_l3_has_no_truthiness_default_or_coercion():
    source = inspect.getsource(run_executor)
    start = source.index("# ---------------- L3 WORKSPACE BASELINE")
    end = source.index("# ---------------- L4 CREDENTIAL BOUNDARY")
    l3 = source[start:end]
    func = ast.parse(
        inspect.getsource(run_executor._l3_project_baseline)
    ).body[0]
    # Code only: drop the docstring, which legitimately names what is forbidden.
    helper = "\n".join(ast.unparse(node) for node in func.body[1:])
    assert 'getattr(baseline_verification, "passed", True)' not in l3
    for text in (l3, helper):
        assert "bool(" not in text
        assert "int(" not in text
        assert "'passed', True" not in text
    assert "type(return_code) is int" in helper
    assert "getattr(outcome, 'passed') is False" in helper
