"""O1's corrected Pi compatibility policy: version is provenance, never a gate.

Proves, WITHOUT launching any real or fake Pi process (pure data/logic and
static source inspection only, per the corrected brief's "use fake Pi /
offline fixtures; no model; no network"):

- an exact version mismatch alone is never a refusal (there is no
  comparison against any pin left in the gate at all);
- the observed version is always recorded, truthfully, regardless of value;
- a Pi version different from AR2's historical pin may proceed when every
  named compatibility check passes;
- a missing/failed required capability check fails the gate closed, even
  when the version itself is fine;
- O1 does not define, import, or use AR2's ``PINNED_PI_VERSION`` as a gate
  anywhere in this package or in ``run_o1.py``;
- no semver-range authorization exists (no version comparison operator
  appears anywhere near ``reported_version`` in the gate logic);
- ``run_o1.py``'s control flow only ever sends the one semantic prompt
  after the compatibility gate (folded into ``gate_all_passed``) passed.
"""

from __future__ import annotations

import ast
import inspect
import re
from dataclasses import replace
from pathlib import Path

import pytest

from ar2.launch import RuntimeIdentity
from o1.pi_compat import (
    COMPATIBILITY_CHECK_NAMES,
    build_pi_runtime_provenance,
    resolve_pi_identity_provenance_only,
)

_O1_DIR = Path(__file__).resolve().parent.parent
_RUN_O1_SOURCE = (_O1_DIR / "run_o1.py").read_text(encoding="utf-8")
_PI_COMPAT_SOURCE = (_O1_DIR / "o1" / "pi_compat.py").read_text(encoding="utf-8")
_O1_INIT_SOURCE = (_O1_DIR / "o1" / "__init__.py").read_text(encoding="utf-8")


def _fake_identity(version: str) -> RuntimeIdentity:
    return RuntimeIdentity(
        node_executable="C:\\fake\\node.exe",
        pi_cli_js="C:\\fake\\cli.js",
        pi_package_root="C:\\fake\\pi",
        reported_version=version,
        launch_shape="node_direct",
    )


def _all_true_checks() -> dict[str, bool]:
    return dict.fromkeys(COMPATIBILITY_CHECK_NAMES, True)


# -- the observed version is recorded, and is never a gate by itself --------


def test_observed_version_is_recorded_verbatim_for_a_matching_ar2_version():
    result = build_pi_runtime_provenance(identity=_fake_identity("0.84.2"), checks=_all_true_checks())
    assert result["observed_version"] == "0.84.2"
    assert result["compatibility_gate_passed"] is True


def test_observed_version_is_recorded_verbatim_for_a_different_version():
    result = build_pi_runtime_provenance(identity=_fake_identity("0.84.3"), checks=_all_true_checks())
    assert result["observed_version"] == "0.84.3"


@pytest.mark.parametrize("version", ["0.84.2", "0.84.3", "1.0.0", "0.1.0", "not-a-semver-at-all"])
def test_exact_version_value_never_by_itself_causes_a_refusal(version: str):
    """No version string, including a nonsense one, changes the gate outcome
    on its own -- only the ``checks`` dict does."""
    result = build_pi_runtime_provenance(identity=_fake_identity(version), checks=_all_true_checks())
    assert result["compatibility_gate_passed"] is True
    assert result["observed_version"] == version


def test_a_version_different_from_ar2s_historical_pin_may_proceed():
    """0.84.3 (the operator-upgraded, currently installed version) passes
    the gate exactly like 0.84.2 would, given the same passing checks."""
    old_pin_result = build_pi_runtime_provenance(identity=_fake_identity("0.84.2"), checks=_all_true_checks())
    new_version_result = build_pi_runtime_provenance(
        identity=_fake_identity("0.84.3"), checks=_all_true_checks()
    )
    assert old_pin_result["compatibility_gate_passed"] is True
    assert new_version_result["compatibility_gate_passed"] is True
    assert old_pin_result["observed_version"] != new_version_result["observed_version"]


def test_provenance_block_never_claims_general_future_version_support():
    result = build_pi_runtime_provenance(identity=_fake_identity("0.84.3"), checks=_all_true_checks())
    assert result["exact_version_is_authorization_gate"] is False
    assert result["version_recorded_as_provenance"] is True
    assert result["no_semver_range_authorization"] is True
    assert "NONE" in result["future_version_support_claim"]


# -- a missing/failed required capability fails closed, even with a fine version --


def test_a_single_failed_check_fails_the_whole_gate_closed():
    checks = _all_true_checks()
    checks["h1_extension_identity_passed"] = False
    result = build_pi_runtime_provenance(identity=_fake_identity("0.84.3"), checks=checks)
    assert result["compatibility_gate_passed"] is False
    assert result["compatibility_checks"]["h1_extension_identity_passed"] is False


@pytest.mark.parametrize("name", COMPATIBILITY_CHECK_NAMES)
def test_every_named_check_is_individually_load_bearing(name: str):
    """No compatibility check is decorative: flipping ANY one of them alone
    fails the gate closed."""
    checks = _all_true_checks()
    checks[name] = False
    result = build_pi_runtime_provenance(identity=_fake_identity("0.84.3"), checks=checks)
    assert result["compatibility_gate_passed"] is False


def test_all_checks_true_is_required_and_sufficient_for_a_pass():
    result = build_pi_runtime_provenance(identity=_fake_identity("0.84.3"), checks=_all_true_checks())
    assert result["compatibility_gate_passed"] is True


def test_a_missing_check_key_is_a_wiring_bug_and_raises_rather_than_silently_passing():
    incomplete = _all_true_checks()
    del incomplete[COMPATIBILITY_CHECK_NAMES[0]]
    with pytest.raises(AssertionError):
        build_pi_runtime_provenance(identity=_fake_identity("0.84.3"), checks=incomplete)


# -- no version-comparison / semver-range logic exists in the gate ----------


def test_pi_compat_module_contains_no_comparison_against_reported_version():
    """``reported_version`` (or the ``identity.reported_version`` it becomes)
    is never compared with ==, !=, <, >, <= or >= anywhere in the gate logic
    -- there is no equality pin and no semver range hiding as a comparison."""
    forbidden = re.compile(r"reported_version\s*(==|!=|<=|>=|<|>)")
    assert not forbidden.search(_PI_COMPAT_SOURCE)


def test_pi_compat_module_never_hardcodes_ar2s_historical_pin_as_a_comparison_target():
    # The string may appear in prose/docstrings (it does, describing the
    # policy correction), but never as the right-hand side of a comparison.
    forbidden = re.compile(r'[=!<>]=\s*"0\.84\.2"')
    assert not forbidden.search(_PI_COMPAT_SOURCE)


def test_resolve_pi_identity_provenance_only_source_has_no_version_gate():
    source = inspect.getsource(resolve_pi_identity_provenance_only)
    assert "PINNED_PI_VERSION" not in source
    assert not re.search(r"reported\s*(==|!=|<=|>=|<|>)", source)
    assert not re.search(r"expected_version", source)


# -- O1 never imports AR2's PINNED_PI_VERSION as a gate ----------------------


def _imported_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def test_o1_package_init_does_not_import_pinned_pi_version():
    assert "PINNED_PI_VERSION" not in _imported_names(_O1_INIT_SOURCE)


def test_run_o1_does_not_import_pinned_pi_version():
    assert "PINNED_PI_VERSION" not in _imported_names(_RUN_O1_SOURCE)


def test_run_o1_does_not_import_ar2s_resolve_runtime_identity():
    assert "resolve_runtime_identity" not in _imported_names(_RUN_O1_SOURCE)


def test_pi_compat_does_not_import_ar2s_resolve_runtime_identity():
    assert "resolve_runtime_identity" not in _imported_names(_PI_COMPAT_SOURCE)


# -- zero prompts when the compatibility gate fails (control-flow proof) ----


def _phase_case_source() -> str:
    tree = ast.parse(_RUN_O1_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "phase_case":
            return ast.get_source_segment(_RUN_O1_SOURCE, node) or ""
    raise AssertionError("phase_case not found in run_o1.py")


def test_phase_case_folds_the_compatibility_gate_into_gate_all_passed():
    body = _phase_case_source()
    assert 'gate["pi_compatibility_gate_passed"] = run["pi_runtime"]["compatibility_gate_passed"]' in body
    assert "gate_all_passed = all(bool(v) for v in gate.values())" in body


def test_phase_case_only_sends_the_prompt_after_gate_all_passed_is_computed():
    body = _phase_case_source()
    gate_index = body.index("gate_all_passed = all(bool(v) for v in gate.values())")
    guard_index = body.index("if gate_all_passed and supervisor is not None:")
    prompt_index = body.index('"type": "prompt"')
    assert gate_index < guard_index < prompt_index, (
        "the prompt send must be lexically AFTER both the gate computation "
        "and the gate_all_passed guard"
    )


def test_phase_case_computes_compatibility_checks_before_the_prompt_guard():
    body = _phase_case_source()
    checks_index = body.index('run["pi_runtime"] = build_pi_runtime_provenance')
    guard_index = body.index("if gate_all_passed and supervisor is not None:")
    assert checks_index < guard_index
