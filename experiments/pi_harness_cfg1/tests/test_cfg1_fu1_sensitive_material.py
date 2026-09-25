"""FU1 (R6 + AMEND1): the sensitive-material state machines and their authority.

Tests Q (L9 / OC-11, AM-13), R (the L11 transactional writer, AM-9), W (L9
step 9a, AM-11), X (foreign same-name objects at L24, AMEND2-amended), Z (AM-14 pinned inputs and the frozen golden
vector) and the AM-10 typed-interval boundary, of
``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` Sec. 9.2a-9.2c / 11.

Everything runs the GENUINE writers and the GENUINE Win32 primitive against
synthetic workspaces under pytest's temporary directories, with a synthetic
``.invalid`` endpoint and synthetic broker values. Faults are injected at the
exact seams the design names; every injected close failure closes its leaked
descriptor itself before the test ends, so the suite's handle hygiene holds.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from cfg1_issuance_cleanup import discard_config_for_test, discard_extension_for_test
from cfg1_doubles import FakeSupervisor, build_doubled_ports, seam_digests_all_match
from cfg1_fu1_support import HandleLog as _HandleLog
from cfg1_fu1_support import make_admission

from pi_harness_cfg1 import (
    cfg1_extension,
    cfg1_pi_config,
    config_issuance,
    extension_issuance,
    extension_pins,
    run_executor,
    run_workspace,
)
from pi_harness_cfg1 import win_config_authority as win
from pi_harness_cfg1.arms import ARM_COMPAT, ARM_REDACTED_DIGEST
from pi_harness_cfg1.cfg1_extension import Cfg1ExtensionError, write_cfg1_extension
from pi_harness_cfg1.cfg1_pi_config import (
    CFG1_CONFIG_DIR_NAME,
    Cfg1PiConfigError,
    models_document,
    redacted_models_digest,
    serialize_config_document,
    write_cfg1_pi_config,
)
from pi_harness_cfg1.records import _require_valid_cfg1_run_payload_v2, build_cfg1_run_payload
from pi_harness_cfg1.run_executor import execute_cfg1_run

SYNTHETIC_BASE_URL = "https://cfg1-fu1-sensitive.invalid/v1"
SYNTHETIC_PIPE = "\\\\.\\pipe\\cfg1-fu1-synthetic-pipe"
SYNTHETIC_CAPABILITY = "cfg1-fu1-synthetic-capability"
SYNTHETIC_TOKEN = "cfg1-fu1-synthetic-token-not-a-secret"

_REPO = Path(__file__).resolve().parents[3]
_FROZEN_EXTENSION_DIR = _REPO / "experiments" / "pi_external_runtime_ar2" / "extension"

#: Test Z's OWN literal pin table -- independent of the writer's pin module.
TEST_OWNED_SOURCE_PINS = {
    "ipc.ts": (8589, "789831482abf353254aa2ff5af20d90634f2caad1fa7366bfe7776c4a35c2024"),
    "tools.ts": (5896, "c03de727ae73d58babef459c753852a7b53439ddd1c0db571a2f0443abe9f5b4"),
    "index.ts": (2182, "ffc2dee8198d51f0f914a67a2370e1149040e0616f8789526b9253f53bcfcb3c"),
    "package.json": (295, "4571c0f2552eefaadd40a99885f4d73930bfb540fe9ece4f23fed6a4a05058fc"),
}
TEST_OWNED_TEMPLATE_PIN = (748, "819f1f1d7909020a701d9527f37138ecaab08494d3ad06923863bf407043094f")
#: R6 Sec. 9.2c-D -- the FROZEN golden vector, as design literals.
GOLDEN_EXPERIMENT_ID = "golden_vector_experiment"
GOLDEN_PIPE_NAME = "\\\\.\\pipe\\golden_vector_pipe"
GOLDEN_CAPABILITY_ID = "golden-capability-0001"
GOLDEN_TOKEN = "golden-vector-token-not-a-secret-0000"
GOLDEN_ON_DISK_SHA256 = "e7916cd3c878626369684cde06e0919d15affaea80f9700871024999ee163715"


@pytest.fixture()
def workspace(git_executable):
    handle, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    root = handle.experiment_root
    try:
        yield handle
    finally:
        run_workspace.discard_cfg1_run_workspace(handle)
        shutil.rmtree(root, ignore_errors=True)


def _config_dir(handle) -> Path:
    return Path(handle.experiment_root) / CFG1_CONFIG_DIR_NAME


def _extension_dir(handle) -> Path:
    return Path(handle.experiment_root) / "pi_extension"


def _write_extension(handle, **kwargs):
    values = dict(pipe_name=SYNTHETIC_PIPE, capability_id=SYNTHETIC_CAPABILITY, token=SYNTHETIC_TOKEN)
    values.update(kwargs)
    return write_cfg1_extension(handle, **values)


def _pathname_deletion_spy(monkeypatch) -> list:
    calls: list = []
    for module, name in ((os, "unlink"), (os, "remove"), (os, "rmdir"), (shutil, "rmtree")):
        real = getattr(module, name)
        monkeypatch.setattr(
            module, name, lambda *a, _r=real, _n=name, **k: (calls.append(_n), _r(*a, **k))[1]
        )
    return calls


# ---------------------------------------------------------------------------
# Q -- L9's endpoint-material state machine (OC-11, AM-13), the genuine writer
# ---------------------------------------------------------------------------


def _inject_models_write_partial(monkeypatch):
    real = win.write_child_text
    calls: list[int] = []

    def _write(child, text):
        calls.append(1)
        if len(calls) == 2:
            real(child, text[:20])
            raise win.Cfg1DirectoryAuthorityError("CONFIG_FILES_NOT_WRITTEN")
        return real(child, text)

    monkeypatch.setattr(win, "write_child_text", _write)


_Q_KNOWN_FAILURES = {
    "models_write_partial": _inject_models_write_partial,
    "step_9_readback": lambda mp: mp.setattr(
        win, "read_child_bytes",
        lambda child: (_ for _ in ()).throw(win.Cfg1DirectoryAuthorityError("CONFIG_FILES_UNREADABLE")),
    ),
    "step_9a_mismatch": lambda mp: mp.setitem(ARM_REDACTED_DIGEST, "Q", "0" * 64),
    "step_10_refusal": lambda mp: mp.setattr(
        config_issuance, "register_config_issuance",
        lambda **k: (_ for _ in ()).throw(config_issuance.ConfigIssuanceError("INJECTED")),
    ),
    "unanticipated_body_exception": lambda mp: mp.setattr(
        cfg1_pi_config, "_require_actual_bytes_match_pins",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("unanticipated 71ab")),
    ),
}


def _models_object_is_scrubbed(workspace) -> bool:
    """The exact ``models.json`` object reads zero bytes, or its name is gone.

    AMEND2 Q: "the object's ``EndOfFile == 0`` in every ``False`` row (the name
    may or may not remain; the test does not assert name absence)".
    """
    path = _config_dir(workspace) / "models.json"
    return (not path.exists()) or path.stat().st_size == 0


#: For each injected fault: does ``endpoint_material_outstanding`` become True?
#: A disposition outcome is deliberately NOT here as an input (AMEND2 §9): a
#: failed or raising disposition leaves the bool False when the scrub and every
#: material release succeeded.
_Q_OUTSTANDING = {
    "none": False,
    "dispose_false": False,
    "dispose_raises": False,
    "scrub_fails": True,
    "scrub_raises": True,
    "models_close_fails": True,
    "settings_close_fails": False,
}


@pytest.mark.parametrize("failure", sorted(_Q_KNOWN_FAILURES))
@pytest.mark.parametrize(
    "handle_fault", sorted(_Q_OUTSTANDING) + ["retained_release_fails"]
)
def test_q_b_a_known_failure_after_the_endpoint_write_reports_outstanding_exactly(
    failure, handle_fault, workspace, monkeypatch
):
    log = _HandleLog(monkeypatch)
    deletions = _pathname_deletion_spy(monkeypatch)
    if handle_fault == "dispose_false":
        log.dispose_result["models.json"] = False
    elif handle_fault == "dispose_raises":
        log.dispose_result["models.json"] = "raise"
    elif handle_fault == "scrub_fails":
        log.scrub_result["models.json"] = False
    elif handle_fault == "scrub_raises":
        log.scrub_result["models.json"] = "raise"
    elif handle_fault == "models_close_fails":
        log.close_fails.add("models.json")
    elif handle_fault == "settings_close_fails":
        log.close_fails.add("settings.json")
    elif handle_fault == "retained_release_fails":
        log.retained_close_fails = True
    _Q_KNOWN_FAILURES[failure](monkeypatch)
    tokens_before = config_issuance.issued_token_count()
    try:
        with pytest.raises(Cfg1PiConfigError) as excinfo:
            write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        error = excinfo.value
        # Only a failure at step 10 happens AFTER the retained handle exists.
        retained_acquired = failure == "step_10_refusal"
        expected_outstanding = (
            handle_fault == "retained_release_fails" and retained_acquired
        ) or _Q_OUTSTANDING.get(handle_fault, False)
        assert type(error.endpoint_material_outstanding) is bool
        assert error.endpoint_material_outstanding is expected_outstanding
        # The SCRUB strictly precedes the same handle's close.
        assert log.scrubbed_before_closed("models.json")
        assert deletions == []  # nothing is ever deleted by pathname
        assert config_issuance.issued_token_count() == tokens_before
        assert win.held_retained_count() == 0  # released, never stranded
        if not expected_outstanding:
            assert _models_object_is_scrubbed(workspace)
        for text in (str(error), repr(error)):
            assert "cfg1-fu1-sensitive" not in text and "71ab" not in text
    finally:
        log.release_leaks()


@pytest.mark.parametrize(
    "release_fault", ["config_pin", "root_pin", "models_close", "settings_close"]
)
def test_q_s_prime_a_release_failure_after_success_reclaims_scrubs_and_raises(
    release_fault, workspace, monkeypatch
):
    log = _HandleLog(monkeypatch)
    reclaimed: list[bool] = []
    real_reclaim = config_issuance.reclaim_config_issuance
    monkeypatch.setattr(
        config_issuance, "reclaim_config_issuance",
        lambda retained: (reclaimed.append(real_reclaim(retained)), reclaimed[-1])[1],
    )
    if release_fault in ("config_pin", "root_pin"):
        real_release = win.release_pin_quietly
        order = {"config_pin": 1, "root_pin": 2}[release_fault]
        seen: list[int] = []

        def _release(pin):
            seen.append(1)
            real_release(pin)
            return len(seen) != order

        monkeypatch.setattr(win, "release_pin_quietly", _release)
    else:
        log.close_fails.add("models.json" if release_fault == "models_close" else "settings.json")
    registered: list[str] = []
    real_register = config_issuance.register_config_issuance
    monkeypatch.setattr(
        config_issuance, "register_config_issuance",
        lambda **k: (lambda t: (registered.append(t), t)[1])(real_register(**k)),
    )
    try:
        with pytest.raises(Cfg1PiConfigError) as excinfo:
            write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        # A failure first discovered DURING release CAN now reach back: the
        # registered entry is reclaimed and scrubbed through the retained
        # handle before the closed code is raised. No disposition, no scrub
        # through the (already closed) creating handle.
        assert not log.disposed()
        assert ("scrub", "models.json") not in log.calls
        assert registered and reclaimed == [True]
        assert config_issuance.issued_token_count() == 0
        assert win.held_retained_count() == 0
        # ``True`` only where the creating handle's own close failed (the
        # object may still be held open) -- otherwise SCRUB-R proved the scrub.
        assert excinfo.value.endpoint_material_outstanding is (release_fault == "models_close")
        if release_fault != "models_close":
            assert _models_object_is_scrubbed(workspace)
    finally:
        log.release_leaks()


@pytest.mark.parametrize("step", ["open_interval", "root_pin", "mkdir", "config_pin", "children", "gate", "settings_write"])
def test_q_a_failure_before_the_endpoint_write_is_never_outstanding(step, workspace, monkeypatch):
    failure = win.Cfg1DirectoryAuthorityError("INJECTED")
    target = {
        "open_interval": "open_generation_interval",
        "root_pin": "acquire_root_pin",
        "config_pin": "acquire_config_pin",
        "gate": "prove_config_parentage",
    }.get(step)
    if target is not None:
        monkeypatch.setattr(win, target, lambda *a, **k: (_ for _ in ()).throw(failure))
    elif step == "mkdir":
        _config_dir(workspace).mkdir()
    elif step == "children":
        real = win.create_exclusive_child
        calls: list[int] = []

        def _create(**kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise failure
            return real(**kwargs)

        monkeypatch.setattr(win, "create_exclusive_child", _create)
    else:
        monkeypatch.setattr(
            win, "write_child_text", lambda child, text: (_ for _ in ()).throw(failure)
        )
    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.endpoint_material_outstanding is False
    assert win.held_interval_count() == 0


class _LoggingObservations(dict):
    def __init__(self, *args, log: list, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._log = log

    def __setitem__(self, key, value):
        self._log.append(("set", key, value))
        super().__setitem__(key, value)


def _run_with_l9(monkeypatch, git_executable, write_config, *, log=None):
    seam_digests_all_match(monkeypatch)
    if log is not None:
        real_initial = run_executor._initial_observations
        monkeypatch.setattr(
            run_executor, "_initial_observations",
            lambda: _LoggingObservations(real_initial(), log=log),
        )
    ports, made = build_doubled_ports(
        git_executable=git_executable, overrides={"write_config": write_config}
    )
    return execute_cfg1_run(make_admission(), ports=ports), made


def test_q_the_scrub_fact_is_written_false_before_write_config_is_entered(
    monkeypatch, git_executable
):
    log: list = []

    def _write_config(**_k):
        log.append(("write_config_entered",))
        raise Cfg1PiConfigError("INJECTED", False)

    outcome, _made = _run_with_l9(monkeypatch, git_executable, _write_config, log=log)
    entered = log.index(("write_config_entered",))
    last_scrub = [event for event in log[:entered] if event[:2] == ("set", "generated_config_scrub_verified")]
    assert last_scrub and last_scrub[-1][2] is False
    # An exact False outstanding moves it to True, and nothing else does.
    assert outcome.observations["generated_config_scrub_verified"] is True
    assert outcome.observations["refused_at_step"] == "L9"
    assert outcome.observations["pre_dispatch_refusal_code"] == "CONFIG_GENERATION_FAILED"


@pytest.mark.parametrize(
    "raised",
    [
        Cfg1PiConfigError("INJECTED", True),
        Cfg1PiConfigError("INJECTED", 0),
        Cfg1PiConfigError("INJECTED", None),
        RuntimeError("untyped"),
        type("SubclassedError", (Cfg1PiConfigError,), {})("INJECTED", False),
    ],
    ids=["outstanding_true", "non_bool_zero", "non_bool_none", "untyped", "subclass"],
)
def test_q_anything_but_an_exact_false_leaves_the_fact_false_and_l27_never_upgrades_it(
    raised, monkeypatch, git_executable
):
    outcome, made = _run_with_l9(
        monkeypatch, git_executable, lambda **_k: (_ for _ in ()).throw(raised)
    )
    observations = outcome.observations
    assert observations["generated_config_scrub_verified"] is False
    assert "L24" in observations["lifecycle_failure_steps"]
    # L27's whole-root removal succeeded independently -- and upgraded nothing.
    assert observations["workspace_removed_verified"] is True
    assert not Path(made["workspace"].experiment_root).exists()
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations
    )
    _require_valid_cfg1_run_payload_v2(payload)
    assert payload["run_classification"] == "INDETERMINATE_LIFECYCLE"


def test_q_a_genuine_known_failure_through_the_executor_is_proven_clean(
    monkeypatch, git_executable
):
    monkeypatch.setattr(
        config_issuance, "register_config_issuance",
        lambda **k: (_ for _ in ()).throw(config_issuance.ConfigIssuanceError("INJECTED")),
    )
    outcome, _made = _run_with_l9(
        monkeypatch, git_executable,
        lambda *, workspace, arm_id, base_url: write_cfg1_pi_config(
            workspace, arm_id=arm_id, base_url=base_url
        ),
    )
    observations = outcome.observations
    assert observations["refused_at_step"] == "L9"
    assert observations["generated_config_scrub_verified"] is True
    assert observations["lifecycle_all_closed"] is True


# ---------------------------------------------------------------------------
# W -- step 9a compares ACTUAL on-disk bytes with the independent arm pin
# ---------------------------------------------------------------------------


def _perturbed_models_text(kind: str, base_url: str) -> str:
    text = serialize_config_document(models_document(arm_id="Q", base_url=base_url))
    if kind == "extra_space":
        return text.replace('"api": ', '"api":  ', 1)
    if kind == "swapped_key_order":
        document = models_document(arm_id="Q", base_url=base_url)
        provider = document["providers"]["b300_pi_qualification"]
        reordered = {key: provider[key] for key in ("api", "baseUrl", "apiKey", "models")}
        return serialize_config_document({"providers": {"b300_pi_qualification": reordered}})
    if kind == "url_twice":
        return text.replace('"api": "openai-completions"', '"api": ' + json.dumps(base_url), 1)
    if kind == "non_ascii_escaping":
        return json.dumps(models_document(arm_id="Q", base_url=base_url), indent=2, ensure_ascii=False) + "\n"
    raise AssertionError(kind)


@pytest.mark.parametrize(
    "kind", ["extra_space", "swapped_key_order", "bare_newline", "url_twice", "non_ascii_escaping"]
)
def test_w_actual_bytes_that_disagree_with_the_pin_refuse_before_issuance(
    kind, workspace, monkeypatch
):
    base_url = "https://cfg1-fu1-ü.invalid/v1" if kind == "non_ascii_escaping" else SYNTHETIC_BASE_URL
    # The in-memory expected digest still agrees -- which proves nothing.
    assert redacted_models_digest(arm_id="Q") == ARM_REDACTED_DIGEST["Q"]
    real_write = win.write_child_text
    calls: list[int] = []

    def _write(child, text):
        calls.append(1)
        if len(calls) != 2:
            return real_write(child, text)
        if kind == "bare_newline":
            return win.write_child_bytes(child, text.encode("utf-8"))
        return real_write(child, _perturbed_models_text(kind, base_url))

    monkeypatch.setattr(win, "write_child_text", _write)
    tokens_before = config_issuance.issued_token_count()
    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=base_url)
    assert excinfo.value.reason_code == "GENERATED_CONFIG_SHAPE_MISMATCH"
    assert excinfo.value.endpoint_material_outstanding is False
    assert config_issuance.issued_token_count() == tokens_before
    assert os.listdir(_config_dir(workspace)) == []  # both children disposed by handle
    assert "cfg1-fu1" not in str(excinfo.value) and "cfg1-fu1" not in repr(excinfo.value)


@pytest.mark.parametrize("arm_id", sorted(ARM_COMPAT))
def test_w_every_unperturbed_arm_passes_step_9a(arm_id, workspace):
    generated = write_cfg1_pi_config(workspace, arm_id=arm_id, base_url=SYNTHETIC_BASE_URL)
    try:
        record = config_issuance.verify_config_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        on_disk = Path(record.models_path).read_bytes()
        assert hashlib.sha256(on_disk).hexdigest() == record.models_sha256
        canonical = on_disk.replace(b"\r\n", b"\n").replace(
            json.dumps(SYNTHETIC_BASE_URL).encode(), json.dumps("<REDACTED>").encode()
        )
        assert hashlib.sha256(canonical).hexdigest() == ARM_REDACTED_DIGEST[arm_id]
    finally:
        discard_config_for_test(generated.issuance_token)


# ---------------------------------------------------------------------------
# R -- the CFG1 transactional extension writer (AM-9), the genuine writer
# ---------------------------------------------------------------------------


def test_r_a_successful_tree_is_byte_identical_to_the_frozen_writers_output(
    workspace, tmp_path, monkeypatch
):
    from ar2 import pi_config as frozen

    frozen_calls: list[str] = []
    for name in ("write_disposable_extension", "scrub_generated_extension_config"):
        real = getattr(frozen, name)
        monkeypatch.setattr(frozen, name, lambda *a, _r=real, _n=name, **k: (frozen_calls.append(_n), _r(*a, **k))[1])
    deletions = _pathname_deletion_spy(monkeypatch)
    generated = _write_extension(workspace)
    try:
        assert frozen_calls == [] and deletions == []
        assert type(generated) is cfg1_extension.GeneratedCfg1Extension
        assert "pi_extension" not in repr(generated) and SYNTHETIC_TOKEN not in repr(generated)
        record = extension_issuance.verify_extension_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        monkeypatch.undo()
        reference_root = tmp_path / "frozen_reference"
        reference_root.mkdir()
        reference = frozen.write_disposable_extension(
            str(reference_root),
            source_dir=str(_FROZEN_EXTENSION_DIR),
            experiment_id="pi_harness_cfg1",
            pipe_name=SYNTHETIC_PIPE,
            capability_id=SYNTHETIC_CAPABILITY,
            token=SYNTHETIC_TOKEN,
        )
        ours = _extension_dir(workspace)
        assert sorted(os.listdir(ours)) == sorted(os.listdir(reference.extension_dir))
        for name in os.listdir(ours):
            assert (ours / name).read_bytes() == (Path(reference.extension_dir) / name).read_bytes(), name
        assert record.entry_path == str(ours / "index.ts")
    finally:
        discard_extension_for_test(generated.issuance_token)


def _inject_extension_fault(point: str, monkeypatch):
    failure = win.Cfg1DirectoryAuthorityError("INJECTED")
    if point in ("E0", "E1", "E4"):
        target = {"E0": "open_generation_interval", "E1": "acquire_root_pin", "E4": "acquire_config_pin"}[point]
        monkeypatch.setattr(win, target, lambda *a, **k: (_ for _ in ()).throw(failure))
        return False
    if point == "E6":
        real = win.create_exclusive_child
        calls: list[int] = []

        def _create(**kwargs):
            calls.append(1)
            if len(calls) == 3:
                raise failure
            return real(**kwargs)

        monkeypatch.setattr(win, "create_exclusive_child", _create)
        return False
    if point == "E7":
        monkeypatch.setattr(win, "prove_config_parentage", lambda *a, **k: (_ for _ in ()).throw(failure))
        return False
    if point == "E8_before_token":
        real = win.write_child_bytes
        calls = []

        def _bytes(child, data):
            calls.append(1)
            if len(calls) == 2:
                raise failure
            return real(child, data)

        monkeypatch.setattr(win, "write_child_bytes", _bytes)
        return False
    if point == "E8_after_token":
        real = win.write_child_text

        def _text(child, text):
            real(child, text[:40])
            raise failure

        monkeypatch.setattr(win, "write_child_text", _text)
        return True
    if point == "E9":
        real = win.read_child_bytes
        monkeypatch.setattr(win, "read_child_bytes", lambda child: real(child) + b" ")
        return True
    assert point == "E10"
    monkeypatch.setattr(
        extension_issuance, "register_extension_issuance",
        lambda **k: (_ for _ in ()).throw(extension_issuance.ExtensionIssuanceError("INJECTED")),
    )
    return True


@pytest.mark.parametrize(
    "point", ["E0", "E1", "E4", "E6", "E7", "E8_before_token", "E8_after_token", "E9", "E10"]
)
@pytest.mark.parametrize(
    "handle_fault",
    ["none", "token_dispose_false", "token_scrub_fails", "token_close_fails", "retained_release_fails"],
)
def test_r_every_failure_point_reports_token_material_exactly(
    point, handle_fault, workspace, monkeypatch
):
    log = _HandleLog(monkeypatch)
    token_written = _inject_extension_fault(point, monkeypatch)
    if handle_fault == "token_dispose_false":
        log.dispose_result["ar2_config.ts"] = False
    elif handle_fault == "token_scrub_fails":
        log.scrub_result["ar2_config.ts"] = False
    elif handle_fault == "token_close_fails":
        log.close_fails.add("ar2_config.ts")
    elif handle_fault == "retained_release_fails":
        log.retained_close_fails = True
    deletions = _pathname_deletion_spy(monkeypatch)
    try:
        with pytest.raises(Cfg1ExtensionError) as excinfo:
            _write_extension(workspace)
        error = excinfo.value
        # A disposition outcome is never an input (AMEND2 section 10); only a
        # failed scrub, a failed token close, or a failed retained release
        # (and only once E9a acquired it, i.e. at E10) leaves it outstanding.
        faulted = token_written and (
            handle_fault in ("token_scrub_fails", "token_close_fails")
            or (handle_fault == "retained_release_fails" and point == "E10")
        )
        assert type(error.token_material_outstanding) is bool
        assert error.token_material_outstanding is faulted
        if token_written:
            assert log.scrubbed_before_closed("ar2_config.ts")
        assert deletions == []
        assert extension_issuance.issued_extension_token_count() == 0
        assert win.held_retained_count() == 0
        # The writer never removes the directory; only L27 may.
        if point not in ("E0", "E1"):
            assert _extension_dir(workspace).is_dir()
        assert SYNTHETIC_TOKEN not in str(error) and SYNTHETIC_TOKEN not in repr(error)
    finally:
        log.release_leaks()


@pytest.mark.parametrize("release_fault", ["extension_pin", "root_pin", "token_close"])
def test_r_a_release_failure_after_registration_reclaims_scrubs_and_raises(
    release_fault, workspace, monkeypatch
):
    log = _HandleLog(monkeypatch)
    if release_fault == "token_close":
        log.close_fails.add("ar2_config.ts")
    else:
        real_release = win.release_pin_quietly
        order = {"extension_pin": 1, "root_pin": 2}[release_fault]
        seen: list[int] = []

        def _release(pin):
            seen.append(1)
            real_release(pin)
            return len(seen) != order

        monkeypatch.setattr(win, "release_pin_quietly", _release)
    try:
        with pytest.raises(Cfg1ExtensionError) as excinfo:
            _write_extension(workspace)
        assert excinfo.value.token_material_outstanding is (release_fault == "token_close")
        assert not log.disposed()
        assert extension_issuance.issued_extension_token_count() == 0
        assert win.held_retained_count() == 0
        token_path = _extension_dir(workspace) / "ar2_config.ts"
        if release_fault != "token_close":
            assert token_path.exists() and token_path.stat().st_size == 0
    finally:
        log.release_leaks()


def test_r_an_unanticipated_raise_is_released_but_never_credited(workspace, monkeypatch, git_executable):
    log = _HandleLog(monkeypatch)
    monkeypatch.setattr(
        extension_issuance, "register_extension_issuance",
        lambda **k: (_ for _ in ()).throw(RuntimeError("unanticipated 71ab")),
    )
    with pytest.raises(RuntimeError):
        _write_extension(workspace)
    # Released exactly like a known failure (scrubbed by handle, then closed)...
    assert log.scrubbed_before_closed("ar2_config.ts")
    assert extension_issuance.issued_extension_token_count() == 0
    assert win.held_retained_count() == 0
    monkeypatch.undo()

    # ...but through the executor the fact STAYS False: an untyped raise is
    # assumed to leave token material.
    seam_digests_all_match(monkeypatch)
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={
            "write_extension": lambda **_k: (_ for _ in ()).throw(RuntimeError("untyped"))
        },
    )
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    observations = outcome.observations
    assert observations["refused_at_step"] == "L11"
    assert observations["pre_dispatch_refusal_code"] == "EXTENSION_GENERATION_FAILED"
    assert observations["extension_binding_scrub_verified"] is False
    assert "L24" in observations["lifecycle_failure_steps"]
    assert observations["workspace_removed_verified"] is True


@pytest.mark.parametrize("outstanding", [False, True, "False", None])
def test_r_the_executor_credits_only_an_exact_false(outstanding, monkeypatch, git_executable):
    seam_digests_all_match(monkeypatch)
    raised = Cfg1ExtensionError("INJECTED", outstanding)
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"write_extension": lambda **_k: (_ for _ in ()).throw(raised)},
    )
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    assert outcome.observations["extension_binding_scrub_verified"] is (outstanding is False)
    assert outcome.observations["refused_at_step"] == "L11"


# ---------------------------------------------------------------------------
# X -- a foreign same-name object at L24 is never touched (AMEND2)
# ---------------------------------------------------------------------------


def _run_with_l21_hook(monkeypatch, git_executable, hook, *, at_removal=None):
    seam_digests_all_match(monkeypatch)
    made_holder: dict = {}

    class _HookedSupervisor(FakeSupervisor):
        def shutdown(self):
            # L21 runs strictly before L24, after L11 and L9 succeeded.
            hook(made_holder["made"]["workspace"])
            return super().shutdown()

    supervisor = _HookedSupervisor()
    ports, made = build_doubled_ports(
        git_executable=git_executable, overrides={"build_supervisor": lambda **_k: supervisor}
    )
    made_holder["made"] = made
    removals: list[dict] = []
    real_remove = run_workspace.remove_cfg1_run_workspace

    def _remove(handle):
        root = Path(handle.experiment_root)
        removals.append({str(p.relative_to(root)) for p in root.rglob("*")})
        if at_removal is not None:
            at_removal(handle)
        return real_remove(handle)

    monkeypatch.setattr(run_workspace, "remove_cfg1_run_workspace", _remove)
    return execute_cfg1_run(make_admission(), ports=ports), made, removals


@pytest.mark.parametrize("swap", ["same_bytes", "different_bytes", "reparse", "directory"])
def test_x_l24_never_touches_a_foreign_same_name_object(swap, monkeypatch, git_executable, tmp_path):
    """AMEND2 X: the foreign object is untouched; the ISSUED object is scrubbed.

    L24 opens no pathname, so a foreign object at the old name is neither
    opened, modified nor deleted; the fact is ``True`` because SCRUB-R
    completed on the exact issued object, which is still held by handle.
    """
    foreign_marker = b"// a foreign object CFG1 never created\n"
    seen: dict = {}

    def _hook(handle):
        extension = Path(handle.experiment_root) / "pi_extension"
        token = extension / "ar2_config.ts"
        if swap == "same_bytes":
            data = token.read_bytes()
            token.unlink()
            token.write_bytes(data)
            seen["expected"] = data
        elif swap == "different_bytes":
            token.unlink()
            token.write_bytes(foreign_marker)
            seen["expected"] = foreign_marker
        elif swap == "reparse":
            from conftest import make_file_symlink

            elsewhere = tmp_path / "elsewhere.ts"
            elsewhere.write_bytes(foreign_marker)
            token.unlink()
            try:
                make_file_symlink(token, elsewhere)
            except (OSError, NotImplementedError):
                token.write_bytes(foreign_marker)
            seen["expected"] = foreign_marker
        else:
            try:
                os.rename(extension, extension.parent / "pi_extension_moved")
            except OSError:
                # Observed host behavior: a directory holding an open handle
                # (H_r) to a child cannot be renamed. Nothing was swapped, so
                # the token object is simply scrubbed in place.
                seen["dir_rename_refused"] = True
                seen["expected"] = b""
            else:
                extension.mkdir()
                (extension / "ar2_config.ts").write_bytes(foreign_marker)
                seen["expected"] = foreign_marker
        seen["identity"] = os.stat(token, follow_symlinks=False).st_ino

    def _at_removal(handle):
        token = Path(handle.experiment_root) / "pi_extension" / "ar2_config.ts"
        seen["after"] = token.read_bytes()
        seen["after_identity"] = os.stat(token, follow_symlinks=False).st_ino

    outcome, made, removals = _run_with_l21_hook(
        monkeypatch, git_executable, _hook, at_removal=_at_removal
    )
    observations = outcome.observations
    assert observations["extension_binding_scrub_verified"] is True
    assert observations["generated_config_scrub_verified"] is True
    assert "L24" not in observations["lifecycle_failure_steps"]
    # The foreign object was still present, byte-identical, when L27 took the root.
    assert removals and "pi_extension\\ar2_config.ts" in removals[0]
    assert seen["after"] == seen["expected"]
    assert seen["after_identity"] == seen["identity"]
    assert extension_issuance.issued_extension_token_count() == 0
    assert win.held_retained_count() == 0
    assert observations["workspace_removed_verified"] is True
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations
    )
    _require_valid_cfg1_run_payload_v2(payload)


# ---------------------------------------------------------------------------
# Z -- AM-14 pinned inputs and the frozen golden vector
# ---------------------------------------------------------------------------


@pytest.fixture()
def synthetic_sources(tmp_path, monkeypatch):
    source = tmp_path / "synthetic_extension_sources"
    shutil.copytree(_FROZEN_EXTENSION_DIR, source)
    monkeypatch.setattr(cfg1_extension, "_extension_source_directory", lambda: str(source))
    return source


def test_z_the_production_pins_equal_the_tests_own_literals():
    assert extension_pins.PINNED_EXTENSION_SOURCES == TEST_OWNED_SOURCE_PINS
    assert extension_pins.EXTENSION_SOURCE_NAMES == ("ipc.ts", "tools.ts", "index.ts", "package.json")
    assert (
        extension_pins.GENERATED_CONFIG_TEMPLATE_BYTES,
        extension_pins.GENERATED_CONFIG_TEMPLATE_SHA256,
    ) == TEST_OWNED_TEMPLATE_PIN
    assert extension_pins.GOLDEN_VECTOR_ON_DISK_SHA256 == GOLDEN_ON_DISK_SHA256
    assert len(extension_pins.GOLDEN_VECTOR_PIPE_NAME) == len(GOLDEN_PIPE_NAME) == 27
    from ar2.pi_config import EXTENSION_SOURCE_FILES

    assert tuple(EXTENSION_SOURCE_FILES) == extension_pins.EXTENSION_SOURCE_NAMES


def _perturb(path: Path, how: str) -> None:
    data = path.read_bytes()
    if how == "one_byte_changed":
        path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    elif how == "appended":
        path.write_bytes(data + b"\n")
    elif how == "truncated":
        path.write_bytes(data[:-1])
    elif how == "same_size_different":
        path.write_bytes(bytes(len(data)))
    else:
        path.write_bytes(data + b"// longer\n" * 50)


@pytest.mark.parametrize("name", ["tools.ts", "index.ts", "package.json", "ipc.ts"])
@pytest.mark.parametrize("how", ["one_byte_changed", "appended", "truncated", "same_size_different", "longer"])
def test_z1_a_modified_source_refuses_before_anything_exists(
    name, how, synthetic_sources, workspace, monkeypatch
):
    _perturb(synthetic_sources / name, how)
    opened: list[int] = []
    real_open = win.open_generation_interval
    monkeypatch.setattr(win, "open_generation_interval", lambda: (opened.append(1), real_open())[1])
    writes: list[int] = []
    for writer in ("write_child_bytes", "write_child_text"):
        real = getattr(win, writer)
        monkeypatch.setattr(win, writer, lambda *a, _r=real, **k: (writes.append(1), _r(*a, **k))[1])
    with pytest.raises(Cfg1ExtensionError) as excinfo:
        _write_extension(workspace)
    assert excinfo.value.reason_code == "EXTENSION_SOURCE_UNPINNED"
    assert excinfo.value.token_material_outstanding is False
    assert opened == [] and writes == []
    assert not _extension_dir(workspace).exists()


@pytest.mark.parametrize("how", ["one_char_changed", "extra_percent_s", "extra_bare_percent"])
def test_z3_a_template_that_differs_from_its_pin_refuses_before_anything_exists(
    how, workspace, monkeypatch
):
    from ar2 import pi_config as frozen

    template = frozen._GENERATED_CONFIG_HEADER
    if how == "one_char_changed":
        template = template.replace("GENERATED", "GENERATEd", 1)
    elif how == "extra_percent_s":
        template = template + "// %s\n"
    else:
        template = template.replace("Disposable.", "Disposable 100%.", 1)
    monkeypatch.setattr(frozen, "_GENERATED_CONFIG_HEADER", template)
    with pytest.raises(Cfg1ExtensionError) as excinfo:
        _write_extension(workspace)
    assert excinfo.value.reason_code == "EXTENSION_TEMPLATE_UNPINNED"
    assert excinfo.value.token_material_outstanding is False
    assert not _extension_dir(workspace).exists()


def test_z2_and_z5_sources_are_read_once_and_later_edits_never_reach_disk(
    synthetic_sources, workspace, monkeypatch
):
    (synthetic_sources / "extra_file.ts").write_bytes(b"// never read, never copied\n")
    reads: list[str] = []
    real_read = cfg1_extension._read_source_once
    monkeypatch.setattr(
        cfg1_extension, "_read_source_once",
        lambda path, limit: (reads.append(os.path.basename(path)), real_read(path, limit))[1],
    )
    real_create = win.create_exclusive_child
    edited: list[int] = []

    def _create(**kwargs):
        if not edited:
            edited.append(1)
            for name in TEST_OWNED_SOURCE_PINS:
                _perturb(synthetic_sources / name, "one_byte_changed")
        return real_create(**kwargs)

    monkeypatch.setattr(win, "create_exclusive_child", _create)
    generated = _write_extension(workspace)
    try:
        assert reads == ["ipc.ts", "tools.ts", "index.ts", "package.json"]
        directory = _extension_dir(workspace)
        assert sorted(os.listdir(directory)) == sorted(list(TEST_OWNED_SOURCE_PINS) + ["ar2_config.ts"])
        for name, (size, digest) in TEST_OWNED_SOURCE_PINS.items():
            data = (directory / name).read_bytes()
            assert len(data) == size and hashlib.sha256(data).hexdigest() == digest
        record = extension_issuance.verify_extension_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        recorded = dict(record.child_sha256)
        for name, (_size, digest) in TEST_OWNED_SOURCE_PINS.items():
            assert recorded[name] == digest
    finally:
        discard_extension_for_test(generated.issuance_token)


@pytest.mark.parametrize("shape", ["directory", "symlink", "oversize"])
def test_z6_a_source_that_is_not_the_pinned_regular_file_refuses(
    shape, synthetic_sources, workspace
):
    target = synthetic_sources / "tools.ts"
    if shape == "directory":
        target.unlink()
        target.mkdir()
    elif shape == "symlink":
        from conftest import make_file_symlink

        real = synthetic_sources / "tools_real.ts"
        os.rename(target, real)
        try:
            make_file_symlink(target, real)
        except (OSError, NotImplementedError):
            pytest.skip("file symlinks need a privilege this session lacks")
    else:
        target.write_bytes(target.read_bytes() * 3)
    with pytest.raises(Cfg1ExtensionError) as excinfo:
        _write_extension(workspace)
    assert excinfo.value.reason_code == "EXTENSION_SOURCE_UNPINNED"
    assert not _extension_dir(workspace).exists()


def _golden_document_by_hand(template: str) -> str:
    backslash = "\\"
    escaped_pipe = GOLDEN_PIPE_NAME.replace(backslash, backslash * 2)
    body = (
        "{\n"
        f'  "experiment": "{GOLDEN_EXPERIMENT_ID}",\n'
        f'  "pipeName": "{escaped_pipe}",\n'
        f'  "capabilityId": "{GOLDEN_CAPABILITY_ID}",\n'
        f'  "token": "{GOLDEN_TOKEN}"\n'
        "}"
    )
    return template % body


def test_z4_the_golden_vector_is_reproduced_on_disk_by_the_genuine_writer(workspace, monkeypatch):
    from ar2 import pi_config as frozen

    template = frozen._GENERATED_CONFIG_HEADER
    encoded = template.encode("utf-8")
    assert (len(encoded), hashlib.sha256(encoded).hexdigest()) == TEST_OWNED_TEMPLATE_PIN
    # Built INDEPENDENTLY, twice, from the four frozen input literals -- never
    # by asking the production serializer what the answer is.
    by_hand = _golden_document_by_hand(template)
    by_json = template % json.dumps(
        {
            "experiment": GOLDEN_EXPERIMENT_ID,
            "pipeName": GOLDEN_PIPE_NAME,
            "capabilityId": GOLDEN_CAPABILITY_ID,
            "token": GOLDEN_TOKEN,
        },
        indent=2,
        ensure_ascii=True,
    )
    assert by_hand == by_json
    on_disk = by_hand.replace("\n", "\r\n").encode("ascii")
    assert len(by_hand) == 937 and len(on_disk) == 962
    assert hashlib.sha256(on_disk).hexdigest() == GOLDEN_ON_DISK_SHA256

    # The genuine writer, given the golden inputs, writes EXACTLY those bytes.
    monkeypatch.setattr(cfg1_extension, "EXTENSION_EXPERIMENT_ID", GOLDEN_EXPERIMENT_ID)
    generated = write_cfg1_extension(
        workspace, pipe_name=GOLDEN_PIPE_NAME, capability_id=GOLDEN_CAPABILITY_ID, token=GOLDEN_TOKEN
    )
    try:
        written = (_extension_dir(workspace) / "ar2_config.ts").read_bytes()
        assert hashlib.sha256(written).hexdigest() == GOLDEN_ON_DISK_SHA256
        record = extension_issuance.verify_extension_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        assert dict(record.child_sha256)["ar2_config.ts"] == GOLDEN_ON_DISK_SHA256
    finally:
        discard_extension_for_test(generated.issuance_token)


def test_z_the_pin_module_is_loaded_by_the_audited_executor_lineage():
    """G4 imports ``pi_harness_cfg1.run_executor``; G5 audits every module then
    loaded. The pin module, the static proof and its leaves must be among them.
    A plain Python child (never Node) checks this in a clean interpreter."""
    probe = (
        "import sys\n"
        f"sys.path[:0] = [{str(_REPO / 'src')!r}, {str(_REPO / 'experiments' / 'pi_external_runtime_ar2')!r},"
        f" {str(_REPO / 'experiments' / 'pi_implementer_qualification')!r}, {str(_REPO / 'experiments')!r}]\n"
        "import pi_harness_cfg1.run_executor\n"
        "wanted = ('extension_pins', 'pi_identity', 'pi_fs_leaves', 'cfg1_extension', 'extension_issuance')\n"
        "print(','.join(n for n in wanted if 'pi_harness_cfg1.' + n in sys.modules))\n"
        "print(','.join(sorted(n for n in sys.modules if n in ('ar2.broker', 'ar2.supervisor', 'ar2.launch'))))\n"
    )
    completed = subprocess.run(  # noqa: S603 - a fixed Python argv, shell=False
        [sys.executable, "-B", "-c", probe], capture_output=True, timeout=120, check=False
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    loaded, live = completed.stdout.decode("utf-8").splitlines()
    assert loaded == "extension_pins,pi_identity,pi_fs_leaves,cfg1_extension,extension_issuance"
    assert live == ""


# ---------------------------------------------------------------------------
# AM-10 -- exactly two bound generators, typed intervals
# ---------------------------------------------------------------------------


def test_am10_the_extension_writer_binding_is_one_shot_and_self_derived():
    import inspect

    assert inspect.signature(win.bind_extension_writer_authority).parameters == {}
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.bind_extension_writer_authority()
    assert excinfo.value.reason_code == "EXTENSION_WRITER_AUTHORITY_ALREADY_BOUND"
    assert win._EXTENSION_WRITER_CODE is write_cfg1_extension.__code__
    assert win._GENERATOR_CODE is write_cfg1_pi_config.__code__

    def _impostor():
        return win.open_generation_interval()

    _impostor.__name__ = _impostor.__qualname__ = "write_cfg1_extension"  # same NAME, other code
    with pytest.raises(win.Cfg1DirectoryAuthorityError):
        _impostor()
    assert win.held_interval_count() == 0


def test_am10_a_config_interval_cannot_mint_extension_provenance(workspace, monkeypatch):
    attempts: dict = {}
    real_prove = win.prove_config_parentage

    def _prove(pin, *, children, interval=None):
        proven = real_prove(pin, children=children, interval=interval)
        try:
            win.require_extension_issuance_provenance(proven, tuple(children))
            attempts["extension_from_config"] = "ACCEPTED"
        except win.Cfg1DirectoryAuthorityError as exc:
            attempts["extension_from_config"] = exc.reason_code
        return proven

    monkeypatch.setattr(win, "prove_config_parentage", _prove)
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    discard_config_for_test(generated.issuance_token)
    assert attempts["extension_from_config"] == "GENERATION_INTERVAL_KIND_MISMATCH"


def test_am10_an_extension_interval_cannot_mint_config_provenance(workspace, monkeypatch):
    attempts: dict = {}
    real_prove = win.prove_config_parentage

    def _prove(pin, *, children, interval=None):
        proven = real_prove(pin, children=children, interval=interval)
        try:
            win.require_production_issuance_provenance(proven, tuple(children))
            attempts["config_from_extension"] = "ACCEPTED"
        except win.Cfg1DirectoryAuthorityError as exc:
            attempts["config_from_extension"] = exc.reason_code
        return proven

    monkeypatch.setattr(win, "prove_config_parentage", _prove)
    generated = _write_extension(workspace)
    discard_extension_for_test(generated.issuance_token)
    assert attempts["config_from_extension"] == "GENERATION_INTERVAL_KIND_MISMATCH"
    assert win.held_interval_count() == 0
