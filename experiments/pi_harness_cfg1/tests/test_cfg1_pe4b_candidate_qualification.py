"""PE-4B: the exact-candidate qualification path for the E4 request-builder run.

PE-4 qualification happened BEFORE PE-5 approval. In the frozen PE-4B execution source
state the committed APS head was genesis ``r0001``, which admits no profile, so the
installed Pi 1.0.3 candidate could not satisfy the ordinary T-3 gate (exact membership in
the sealed APS eligible set) -- that gate is deliberately left exactly as it is (it is
digest-pinned below). A SEPARATE candidate-qualification authority was therefore required,
and this module is it: it is bound, mechanically, to ONE immutable fact -- the PE-3
candidate committed at ``_SOURCE_COMMIT`` -- and to nothing a caller can choose.

That pre-approval fact is HISTORY, proved below against the exact ``r0001`` bytes. It does
not imply the profile stays unapproved after a later, independently accepted APS revision,
and the qualification path never consults the current APS: candidate staging is never
approval, and approval is only ever a committed APS revision.

What the authority is made of
-----------------------------
* fixed reviewed constants in THIS file: the payload fingerprint, the profile id, the
  mechanical floor, and the size + SHA-256 of each of the three committed artifacts;
* the three artifacts themselves, read from the one repository-owned fixed location
  through the accepted no-follow one-handle reader, and accepted only if every byte
  hashes to the pinned digest. A forged, untracked, staged-elsewhere or edited record
  has different bytes and is refused; a directory listing is never consulted;
* the candidate's facts RE-DERIVED from those bytes with the accepted PE-2a/PE-2b
  primitives (fingerprint, profile id, exposures, declared Node engine);
* a FRESH, complete, no-follow ``PI-PC1`` observation of the installed Pi, resolved
  with the accepted unchanged P1 selection, immediately BEFORE the one Node launch and
  again AFTER it exits -- each must equal the committed candidate exactly, or the E4
  result is unusable (and, before launch, Node never starts).

None of that takes a parameter. The authority functions below accept no Pi root, no
fingerprint, no profile id, no candidate path, no policy snapshot, no leaf binding and
no "mode"; ``test_pe4b_the_authority_functions_accept_exactly_the_stated_parameters``
proves it. The APS and the sealed policy are not consulted anywhere on this path.

Residuals, stated and not closed
--------------------------------
* TOCTOU / A->B->A. Observation is not prevention. Bytes could change between the
  pre-launch observation and Node's imports and be restored before the post-exit
  observation; nothing here can see that, and "continuity" is never claimed. What is
  claimed is only: the payload equalled the committed candidate at the pre-launch
  instant and again after the child exited, and a PERSISTENT difference is a failure.
* ``node.exe`` is identity-pinned for the run (same file identity before and after)
  but never byte-pinned, and its version is checked INSIDE the authorized Node process
  by the harness (no ``--version`` probe exists or may be added).
* The harness drives the request BUILDER only. It never imports the CLI, the main
  entry, RPC mode or extension loading; the Windows self-update quarantine delete that
  lives on the main startup path (PE-4A F-5) is therefore not reachable from here.
  That finding still blocks E5 / any full Pi launch / PE-6.

No ordinary execution surface exists; E4 was executed once, historically, externally
-----------------------------------------------------------------------------------------
There is no ordinary pytest, import-time, environment-variable, marker or option execution
surface for E4: no test, fixture, import-time statement, environment variable, pytest option,
marker or node-id reaches ``_run_candidate_e4`` (proved statically and by a tripwire below), and
``_run_candidate_e4`` still has no in-repository ordinary caller. PE-4B E4 was historically
executed exactly once, through the separately authorized, external, commit-bound one-shot. That
historical execution did not create a persistent or ambient execution authority: an ambient switch
(environment variable, option, marker, mode argument) is never an acceptable authority for running a
Pi candidate, and any further E4 execution would again need its own separate, explicit
authorization. The ordinary tests in this module remain offline Python and start no Node.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path
from typing import NamedTuple

import pytest

import test_cfg1_pi_conformance as ordinary
from cfg1_doubles import approve_profiles, build_synthetic_pi_tree
from pi_harness_cfg1 import pi_fs_leaves, pi_identity
from pi_harness_cfg1 import pi_profile_policy_loader as policy_loader
from pi_harness_cfg1.identity import CFG1_MODEL_ID
from pi_harness_cfg1.pi_manifest import (
    EXPOSURES_PROVEN_ABSENT,
    bundle_from_record,
    observe_exposure_absence,
    parse_manifest_strict,
)
from pi_harness_cfg1.pi_payload import inventory_from_record
from pi_harness_cfg1.pi_profile_floor import compute_profile_facts, policy_file_bytes

# ---------------------------------------------------------------------------
# 1. The fixed, reviewed identity of the ONE candidate this module may qualify
# ---------------------------------------------------------------------------

_SOURCE_COMMIT = "d7bdb230599a6c9e2d0948378529cabfec6e6948"
_PAYLOAD_FINGERPRINT = "66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc"
_PROFILE_ID = "56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67"
_MECHANICAL_FLOOR = "C3_SEAM_CHANGED"
_DECLARED_NODE_ENGINE = ">=22.19.0"

#: Derived from this module's own location, like the other fixed locations here. Not an argument.
_CANDIDATE_DIRECTORY = Path(__file__).resolve().parents[1] / "pi_profile_candidates"
_REAL_CANDIDATE_DIRECTORY = _CANDIDATE_DIRECTORY  # tests that redirect the former copy from this one
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: ``suffix -> (exact size, SHA-256 of the committed bytes)``.
_ARTIFACT_PINS = {
    ".candidate.json": (3734, "16d0e8573cabf5a381d1d067856f3e2ef854918e44829f6ad3b337ef86d80c75"),
    ".inventory.json": (2708753, "f84fb68dd4b90ae81b77049197373497b3b05e33cb679465cb513f6b86671e82"),
    ".manifest_bundle.json": (382200, "ebbc12b96729d53485f8d0dccee7b508a3e1a980209a255b64f1ede802ee72b2"),
}

#: The synthetic prompts ``ordinary._prepare_t3_harness`` hands the harness (tied by a test below).
_SYSTEM_PROMPT = "Synthetic CFG1 conformance system prompt."
_USER_PROMPT = "Synthetic CFG1 conformance user prompt."


class _Refusal(Exception):
    """A closed refusal code; raised before Node starts whenever it can be."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


# ---------------------------------------------------------------------------
# 2. The committed candidate -- loaded from fixed bytes, constructible only here
# ---------------------------------------------------------------------------

_AUTHORITY_KEY = object()


class _CommittedCandidate:
    """The exact PE-3 candidate's facts. Constructed ONLY by ``_load_committed_candidate``."""

    __slots__ = (
        "payload_fingerprint",
        "profile_id",
        "exposures",
        "inventory_file_bytes",
        "declared_node_engine",
    )

    def __init__(self, key: object, **values: object) -> None:
        if key is not _AUTHORITY_KEY:
            raise _Refusal("PE4B_CANDIDATE_NOT_LOADED_FROM_THE_COMMITTED_ARTIFACTS")
        for name in self.__slots__:
            object.__setattr__(self, name, values[name])

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("a committed candidate is immutable")


def _read_pinned_artifact(suffix: str) -> bytes:
    """One artifact's bytes from the fixed location, accepted only at its pinned digest."""
    size, digest = _ARTIFACT_PINS[suffix]
    path = str(_CANDIDATE_DIRECTORY / (_PAYLOAD_FINGERPRINT + suffix))
    read = pi_fs_leaves.read_payload_file_bytes(path, size)
    if (
        read.classification != pi_fs_leaves.CLASSIFICATION_REGULAR_FILE
        or read.within_bound is not True
        or read.stable is not True
        or read.content is None
        or read.size != size
        or read.sha256 != digest
    ):
        raise _Refusal("PE4B_CANDIDATE_ARTIFACT_PIN_MISMATCH", suffix)
    return read.content


def _load_committed_candidate() -> _CommittedCandidate:
    """Load and re-derive the committed candidate. Takes nothing; reads nothing but fixed bytes."""
    record_bytes = _read_pinned_artifact(".candidate.json")
    inventory_bytes = _read_pinned_artifact(".inventory.json")
    bundle_bytes = _read_pinned_artifact(".manifest_bundle.json")

    record = json.loads(record_bytes)
    expected = {
        "record_kind": "aido-pi-profile-candidate.v1",
        "authority": "NON_AUTHORITY_CANDIDATE",
        "payload_fingerprint": _PAYLOAD_FINGERPRINT,
        "profile_id": _PROFILE_ID,
        "floor": _MECHANICAL_FLOOR,
    }
    for name, value in expected.items():
        if record.get(name) != value:
            raise _Refusal("PE4B_CANDIDATE_RECORD_FACT_MISMATCH", name)

    inventory = inventory_from_record(json.loads(inventory_bytes))
    if inventory.payload_fingerprint != _PAYLOAD_FINGERPRINT:
        raise _Refusal("PE4B_CANDIDATE_INVENTORY_FINGERPRINT_MISMATCH")
    if policy_file_bytes(inventory.to_record()) != inventory_bytes:
        raise _Refusal("PE4B_CANDIDATE_INVENTORY_NOT_CANONICAL")
    bundle = bundle_from_record(json.loads(bundle_bytes), inventory)
    if policy_file_bytes(bundle.to_record()) != bundle_bytes:
        raise _Refusal("PE4B_CANDIDATE_BUNDLE_NOT_CANONICAL")

    facts = compute_profile_facts(inventory, bundle)
    if (
        facts.payload_fingerprint != _PAYLOAD_FINGERPRINT
        or facts.profile_id != _PROFILE_ID
        or facts.c5_reason is not None
        or facts.resolution_exposures is None
        or list(facts.resolution_exposures) != record["resolution_exposures"]
    ):
        raise _Refusal("PE4B_CANDIDATE_FACTS_NOT_REDERIVED")
    engines = parse_manifest_strict(bundle.manifest_bytes("package.json")).get("engines")
    if type(engines) is not dict or engines.get("node") != _DECLARED_NODE_ENGINE:
        raise _Refusal("PE4B_CANDIDATE_DECLARED_ENGINE_MISMATCH")

    return _CommittedCandidate(
        _AUTHORITY_KEY,
        payload_fingerprint=_PAYLOAD_FINGERPRINT,
        profile_id=_PROFILE_ID,
        exposures=tuple(facts.resolution_exposures),
        inventory_file_bytes=inventory_bytes,
        declared_node_engine=engines["node"],
    )


# ---------------------------------------------------------------------------
# 3. Resolving and observing the installed Pi -- the accepted P1/Payload primitives
# ---------------------------------------------------------------------------


class _Installation(NamedTuple):
    node_path: str
    node_identity: tuple
    root_path: str
    root_identity: tuple


def _resolve_installation() -> _Installation:
    """P1 exactly as accepted: the first admissible ``node.exe`` and ``pi.cmd`` on ``PATH``."""
    leaves = pi_identity.genuine_pi_proof_leaves()
    path_value = os.environ.get("PATH")
    if type(path_value) is not str:
        raise _Refusal("PE4B_PI_RESOLUTION_FAILED", "no PATH")
    entries = pi_identity._path_entries(path_value)
    node = pi_identity._resolve_node(leaves, entries)
    root = pi_identity._resolve_package_root(leaves, entries)
    if node is None or root is None:
        raise _Refusal("PE4B_PI_RESOLUTION_FAILED")
    return _Installation(node[0], node[1], root[0], root[1])


def _require_exact_candidate(candidate: _CommittedCandidate, installation: _Installation, phase: str) -> None:
    """A FRESH complete no-follow ``PI-PC1`` walk must equal the committed candidate exactly."""
    if type(candidate) is not _CommittedCandidate or type(installation) is not _Installation:
        raise _Refusal("PE4B_MALFORMED_AUTHORITY_ARGUMENT")
    leaves = pi_identity.genuine_pi_proof_leaves()
    observation = pi_identity._observe_payload(leaves, installation.root_path)
    if observation.complete is not True:
        raise _Refusal(f"PE4B_{phase}_PAYLOAD_UNPROVEN", str(observation.refusal_code))
    if observation.payload_fingerprint != candidate.payload_fingerprint:
        raise _Refusal(f"PE4B_{phase}_NOT_THE_COMMITTED_CANDIDATE")
    if policy_file_bytes(observation.inventory.to_record()) != candidate.inventory_file_bytes:
        raise _Refusal(f"PE4B_{phase}_INVENTORY_DIFFERS_FROM_THE_COMMITTED_CANDIDATE")
    absence = observe_exposure_absence(installation.root_path, candidate.exposures, inspect=leaves.inspect)
    if absence.status != EXPOSURES_PROVEN_ABSENT:
        raise _Refusal(f"PE4B_{phase}_EXPOSURE_NOT_PROVEN_ABSENT", str(absence.exposure))
    if not pi_identity._identity_still_holds(
        leaves,
        installation.root_path,
        classification=pi_fs_leaves.CLASSIFICATION_DIRECTORY,
        expected=installation.root_identity,
    ):
        raise _Refusal(f"PE4B_{phase}_PACKAGE_ROOT_IDENTITY_DRIFTED")
    if not pi_identity._identity_still_holds(
        leaves,
        installation.node_path,
        classification=pi_fs_leaves.CLASSIFICATION_REGULAR_FILE,
        expected=installation.node_identity,
    ):
        raise _Refusal(f"PE4B_{phase}_NODE_IDENTITY_DRIFTED")


def _prove_post_exit(candidate: _CommittedCandidate, installation: _Installation, execution_error) -> None:
    """The POST_EXIT proof, run once after an execution attempt, whatever that attempt did.

    A POST failure is NEVER swallowed: it is raised (chained from the execution failure when there
    was one), so a drifted payload cannot hide behind a child that also failed.
    """
    try:
        _require_exact_candidate(candidate, installation, "POST_EXIT")
    except Exception as post_error:
        failure = (
            post_error
            if isinstance(post_error, _Refusal)
            else _Refusal("PE4B_POST_EXIT_PROOF_UNAVAILABLE", type(post_error).__name__)
        )
        if execution_error is None:
            raise failure
        raise failure from execution_error


def _execute_candidate_with_total_proof(
    candidate: _CommittedCandidate, installation: _Installation, prepared: ordinary._PreparedHarness
) -> dict:
    """The ONE execution attempt, the TOTAL post-execution proof, and the E4 evidence -- as one unit.

    Once the harness call has been ATTEMPTED, a fresh POST_EXIT observation runs exactly once
    whatever the call did (success, non-zero child, engine refusal, timeout, malformed report,
    an interception assertion, anything). Only after that proof passes is an execution failure
    re-raised or the report validated; a report is returned only when the exact candidate was
    observed before launch, the harness ran, the exact candidate was observed again, AND the
    candidate-specific evidence checks pass. Its only caller is ``_run_candidate_e4``.
    """
    execution_error = None
    report = None
    try:
        report = ordinary._execute_t3_harness(prepared)
    except BaseException as error:  # noqa: BLE001 - the POST proof must run for every failure; it is re-raised below
        execution_error = error
    _prove_post_exit(candidate, installation, execution_error)
    if execution_error is not None:
        raise execution_error
    _assert_candidate_e4_evidence(report)
    return report


def _run_candidate_e4(tmp_path_factory) -> dict:
    """PREPARED, NOT CALLED: the ONE launch of the E4 harness against the committed candidate.

    No test, fixture, import-time path or ambient switch may invoke this. It is reachable only
    from a future, separately authorized, commit-bound entry point (not created here). A
    successful return means: exact candidate observed before launch, one harness attempt, the
    exact candidate observed again, and the candidate E4 evidence checks passed.
    """
    candidate = _load_committed_candidate()
    installation = _resolve_installation()
    workdir = tmp_path_factory.mktemp("pe4b_e4")
    prepared = ordinary._prepare_t3_harness(
        Path(installation.root_path),
        workdir,
        node_executable=os.path.realpath(installation.node_path),
    )
    _require_exact_candidate(candidate, installation, "PRE_LAUNCH")
    return _execute_candidate_with_total_proof(candidate, installation, prepared)


# ---------------------------------------------------------------------------
# 4. No execution surface: a runtime tripwire (the static proofs are in section 10)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_node_launch_from_this_module(monkeypatch):
    """Defense in depth: if any test here ever reached a Node launch, it fails instead of launching.

    Both the ordinary harness executor and the prepared candidate launcher are replaced for every
    test in this module. Nothing here selects, enables or bypasses it.
    """

    def _tripwire(*_args, **_kwargs):  # pragma: no cover - reaching it is the failure
        raise AssertionError("PE4B: a test in this module reached a Node/installed-Pi launch")

    monkeypatch.setattr(ordinary, "_execute_t3_harness", _tripwire)
    monkeypatch.setitem(globals(), "_run_candidate_e4", _tripwire)


# ---------------------------------------------------------------------------
# 5. The E4 evidence: candidate-specific shape + the ordinary generic invariants
# ---------------------------------------------------------------------------

_REPORT_TOP_LEVEL_KEYS = frozenset({"arms", "violations", "installed", "failedToInstall", "fetchCalls"})
_CONTROL_IDS = tuple(sorted(ordinary._EXTRA_CONTROL_COMPAT))
_ARM_IDS = ("Q", "R", "E", "H") + _CONTROL_IDS
_REASONING_ARMS = ("Q", "R") + _CONTROL_IDS  # reasoning_effort is sent exactly where it is not suppressed

_REQUEST_KEYS_WITH_EFFORT = frozenset(
    {"model", "messages", "stream", "stream_options", "store", "max_completion_tokens", "tools", "reasoning_effort"}
)
_REQUEST_KEYS_WITHOUT_EFFORT = _REQUEST_KEYS_WITH_EFFORT - {"reasoning_effort"}


def _expected_tools() -> list[dict]:
    """The two tools exactly as Pi 1.0.3 declares them: NO ``strict`` key at all."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in ordinary._TOOLS
    ]


def _assert_report_closed_shape(report: object) -> None:
    """The report has exactly the harness's members -- it can carry no identity claim."""
    assert type(report) is dict, "PE4B-REPORT: the report is not an object"
    assert set(report) == _REPORT_TOP_LEVEL_KEYS, (
        "PE4B-REPORT: the report's members are not exactly the harness's own: "
        f"{sorted(set(report) ^ _REPORT_TOP_LEVEL_KEYS)}"
    )
    assert type(report["arms"]) is dict and set(report["arms"]) == set(_ARM_IDS), "PE4B-REPORT: arms differ"
    assert type(report["fetchCalls"]) is list, "PE4B-REPORT: fetchCalls is not a list"
    for arm_id, arm in report["arms"].items():
        assert type(arm) is dict and arm.get("error") is None, f"PE4B-REPORT: arm {arm_id} refused"
        assert arm.get("fetchCallsForThisArm") == 1, f"PE4B-REPORT: arm {arm_id} did not use the injected transport once"


def _assert_candidate_request_shape(report: dict) -> None:
    """Candidate-specific evidence, on top of (never instead of) the ordinary generic invariants."""
    for arm_id in _ARM_IDS:
        params = ordinary._params(report, arm_id)
        expected_keys = _REQUEST_KEYS_WITH_EFFORT if arm_id in _REASONING_ARMS else _REQUEST_KEYS_WITHOUT_EFFORT
        assert set(params) == expected_keys, f"PE4B-SHAPE: arm {arm_id} request members: {sorted(set(params) ^ expected_keys)}"
        for tool in params["tools"]:
            # the key must be ABSENT -- a False, None or any other value is a different shape
            assert "strict" not in tool["function"], f"PE4B-SHAPE: arm {arm_id} carries a strict key"
        assert params["tools"] == _expected_tools(), f"PE4B-SHAPE: arm {arm_id} tool declarations differ"
        instruction, user = params["messages"][0], params["messages"][1:]
        assert instruction["content"] == _SYSTEM_PROMPT, f"PE4B-SHAPE: arm {arm_id} instruction text differs"
        assert user == [{"role": "user", "content": [{"type": "text", "text": _USER_PROMPT}]}], (
            f"PE4B-SHAPE: arm {arm_id} user message differs"
        )
    ordinary._assert_shared_payload_common(ordinary._params(report, "Q"))


#: The ordinary module's generic invariant checks, called VERBATIM on the candidate report. Each is a
#: plain function of the report; none consults an authority gate. ``test_t3_the_shared_payload_shape_...``
#: is deliberately NOT here: its generic ``strict is False`` line is the genesis shape, and the
#: candidate's shape is asserted above instead.
_GENERIC_INVARIANTS = (
    "test_t3_every_required_interception_point_was_installed",
    "test_t3_the_request_went_through_the_injected_transport_only",
    "test_t3_q_and_r_differ_only_in_the_system_message_role",
    "test_t3_q_and_e_differ_only_in_the_presence_of_reasoning_effort",
    "test_t3_h_combines_both_single_variable_effects",
    "test_t3_the_serialized_model_carries_exactly_the_declared_compat_shape",
    "test_t3_err1_p08_the_report_carries_a_path_only",
)

#: The REPORT semantic of the ordinary ``test_t3_no_real_credential_or_endpoint_was_used_anywhere`` --
#: the synthetic ``.invalid`` endpoint was used and no credential/backend marker appears in the
#: report -- WITHOUT its two parent-environment reads. What reaches the child is established by the
#: reviewed minimal child-environment construction and its static allowlist proofs, not by reading
#: the parent's credential or endpoint variables. This function reads no environment of any kind.
_FORBIDDEN_REPORT_MARKERS = ("PI_QUALIFICATION_B300_ROUTE_KEY_VALUE", "b300", "AIDO_LITELLM")


def _assert_candidate_report_uses_only_the_synthetic_endpoint(report: dict) -> None:
    serialized = json.dumps(report)
    assert ordinary.SYNTHETIC_BASE_URL in serialized, "PE4B-ENDPOINT: the synthetic endpoint was not used"
    for forbidden in _FORBIDDEN_REPORT_MARKERS:
        assert forbidden not in serialized, f"PE4B-ENDPOINT: the report carries {forbidden!r}"


def _assert_candidate_e4_evidence(report: dict) -> None:
    """Every check a future authorized E4 run's report must pass. A plain function: it runs no Node.

    It is called by ``_execute_candidate_with_total_proof`` after the POST_EXIT proof, so a candidate
    report cannot be returned without passing it. Its call graph reads no environment (proved
    statically in section 13). Today it is exercised only on fabricated reports (section 6); there
    is deliberately no test that produces a real one.
    """
    _assert_report_closed_shape(report)
    _assert_candidate_request_shape(report)
    _assert_candidate_report_uses_only_the_synthetic_endpoint(report)
    for name in _GENERIC_INVARIANTS:
        getattr(ordinary, name)(report)
    for control_id in _CONTROL_IDS:
        ordinary.test_t3_an_empty_or_explicitly_true_compat_block_is_payload_identical_to_q(control_id, report)


# ---------------------------------------------------------------------------
# 6. Offline: the evidence checks, proved on a synthetic report (no Node, no Pi)
# ---------------------------------------------------------------------------


def _synthetic_request(*, role: str, effort: bool) -> dict:
    params: dict = {
        "model": CFG1_MODEL_ID,
        "messages": [
            {"role": role, "content": _SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": _USER_PROMPT}]},
        ],
        "stream": True,
        "stream_options": {"include_usage": True},
        "store": False,
        "max_completion_tokens": 16384,
        "tools": _expected_tools(),
    }
    if effort:
        params["reasoning_effort"] = "medium"
    return params


def _synthetic_report() -> dict:
    """A report shaped like the candidate's expected E4 result. Fabricated; proves checks only."""
    path_key = next(key for key in sorted(ordinary._ALLOWED_ARM_REPORT_KEYS) if key.endswith("Path"))
    roles = {"Q": "developer", "R": "system", "E": "developer", "H": "system"}
    arms: dict[str, dict] = {}
    for arm_id in _ARM_IDS:
        entry: dict = {}
        if arm_id in roles:
            entry.update(ordinary._arm_report(arm_id))
        arms[arm_id] = {
            **entry,
            path_key: f"models_{arm_id}.json.sidecar",
            "params": _synthetic_request(role=roles.get(arm_id, "developer"), effort=arm_id in _REASONING_ARMS),
            "fetchCallsForThisArm": 1,
        }
    return {
        "arms": arms,
        "violations": [],
        "installed": [
            "globalThis.fetch", "net.connect", "net.createConnection", "tls.connect",
            "http.request", "https.request", "dns.lookup", "dns.resolve4",
        ],
        "failedToInstall": [],
        "fetchCalls": [f"{ordinary.SYNTHETIC_BASE_URL}/chat/completions"] * len(arms),
    }


def _copy(report: dict) -> dict:
    return json.loads(json.dumps(report))


def test_pe4b_the_positive_control_report_passes_every_check():
    _assert_candidate_e4_evidence(_synthetic_report())


@pytest.mark.parametrize(
    "label, mutate",
    [
        pytest.param(
            "a strict:false key is not 'no strict key'",
            lambda r: [t["function"].__setitem__("strict", False) for t in r["arms"]["Q"]["params"]["tools"]],
            id="strict-false",
        ),
        pytest.param(
            "a strict:true key",
            lambda r: [t["function"].__setitem__("strict", True) for t in r["arms"]["H"]["params"]["tools"]],
            id="strict-true",
        ),
        pytest.param(
            "a strict:null key",
            lambda r: r["arms"]["E"]["params"]["tools"][0]["function"].__setitem__("strict", None),
            id="strict-null",
        ),
        pytest.param(
            "tool order swapped",
            lambda r: r["arms"]["R"]["params"]["tools"].reverse(),
            id="tool-order",
        ),
        pytest.param(
            "tool schema altered",
            lambda r: r["arms"]["Q"]["params"]["tools"][0]["function"]["parameters"].__setitem__("x", 1),
            id="tool-schema",
        ),
        pytest.param(
            "an extra request member",
            lambda r: r["arms"]["Q"]["params"].__setitem__("prompt_cache_key", "k"),
            id="extra-member",
        ),
        pytest.param(
            "a request member missing",
            lambda r: r["arms"]["Q"]["params"].pop("store"),
            id="missing-member",
        ),
        pytest.param(
            "instruction text differs",
            lambda r: r["arms"]["Q"]["params"]["messages"][0].__setitem__("content", "other"),
            id="instruction-text",
        ),
        pytest.param(
            "user message differs",
            lambda r: r["arms"]["E"]["params"]["messages"].__setitem__(1, {"role": "user", "content": "x"}),
            id="user-message",
        ),
        pytest.param(
            "a transport that was not used",
            lambda r: r["arms"]["H"].__setitem__("fetchCallsForThisArm", 0),
            id="transport-unused",
        ),
    ],
)
def test_pe4b_a_report_that_departs_from_the_candidates_shape_is_rejected(label, mutate):
    report = _copy(_synthetic_report())
    mutate(report)
    with pytest.raises((AssertionError, KeyError)):
        _assert_candidate_e4_evidence(report)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda r: r["arms"]["R"]["params"]["messages"][0].__setitem__("role", "developer"), id="r-keeps-developer"),
        pytest.param(lambda r: r["arms"]["Q"]["params"]["messages"][0].__setitem__("role", "system"), id="q-loses-developer"),
        pytest.param(lambda r: r["arms"]["E"]["params"].__setitem__("reasoning_effort", "medium"), id="e-keeps-effort"),
        pytest.param(lambda r: r["arms"]["H"]["params"].__setitem__("reasoning_effort", "medium"), id="h-keeps-effort"),
        pytest.param(lambda r: r["arms"]["Q"]["params"].pop("reasoning_effort"), id="q-loses-effort"),
        pytest.param(lambda r: r["arms"]["CONTROL_EMPTY"]["params"].__setitem__("store", True), id="control-differs-from-q"),
        pytest.param(lambda r: r["arms"]["R"]["params"].__setitem__("stream", False), id="r-differs-beyond-role"),
    ],
)
def test_pe4b_each_retained_cfg1_cc1_contrast_still_fails_when_broken(mutate):
    """The generic CFG1-CC1 contrasts (Q/R role only, Q/E effort only, H combined, controls inert) are the
    ordinary module's own checks, retained verbatim -- not re-derived and not weakened."""
    report = _copy(_synthetic_report())
    mutate(report)
    with pytest.raises((AssertionError, KeyError)):
        for name in _GENERIC_INVARIANTS:
            getattr(ordinary, name)(report)
        for control_id in _CONTROL_IDS:
            ordinary.test_t3_an_empty_or_explicitly_true_compat_block_is_payload_identical_to_q(control_id, report)


def test_pe4b_the_ordinary_strict_expectation_still_refuses_the_candidates_shape():
    """The generic ordinary expectation is untouched: it fails closed on a no-strict-key declaration."""
    report = _synthetic_report()
    ordinary._assert_shared_payload_common(ordinary._params(report, "Q"))  # the shared part holds...
    with pytest.raises((KeyError, AssertionError)):
        ordinary.test_t3_the_shared_payload_shape_matches_the_source_derivation(report)  # ...strict does not


@pytest.mark.parametrize(
    "member",
    [
        "candidate", "payload_fingerprint", "payloadFingerprint", "profile_id", "profileId",
        "floor", "engine", "nodeVersion", "identity", "approved", "extra",
    ],
)
def test_pe4b_a_malformed_node_report_cannot_claim_candidate_identity_or_any_other_member(member):
    report = _synthetic_report()
    report[member] = _PAYLOAD_FINGERPRINT
    with pytest.raises(AssertionError, match="PE4B-REPORT"):
        _assert_report_closed_shape(report)
    arm_claim = _synthetic_report()
    arm_claim["arms"]["Q"][member] = _PROFILE_ID
    with pytest.raises(AssertionError):
        ordinary.test_t3_err1_p08_the_report_carries_a_path_only(arm_claim)
    del report[member]
    _assert_report_closed_shape(report)


def test_pe4b_the_identity_of_a_run_is_never_read_from_the_report():
    functions = _module_functions()
    for name in (
        "_run_candidate_e4", "_require_exact_candidate", "_load_committed_candidate",
        "_execute_candidate_with_total_proof", "_prove_post_exit",
    ):
        reads = [
            node
            for node in ast.walk(functions[name])
            if isinstance(node, (ast.Subscript, ast.Attribute))
            and isinstance(node.value, ast.Name)
            and node.value.id == "report"
        ]
        assert reads == [], (name, [ast.unparse(node) for node in reads])


# ---------------------------------------------------------------------------
# 7. Offline: the committed candidate and every way to forge or redirect it
# ---------------------------------------------------------------------------


def _copy_committed_artifacts(destination: Path) -> None:
    destination.mkdir(parents=True)
    for suffix in _ARTIFACT_PINS:
        name = _PAYLOAD_FINGERPRINT + suffix
        (destination / name).write_bytes((_REAL_CANDIDATE_DIRECTORY / name).read_bytes())


def test_pe4b_the_committed_candidate_loads_and_every_pinned_fact_is_rederived():
    candidate = _load_committed_candidate()
    assert candidate.payload_fingerprint == _PAYLOAD_FINGERPRINT
    assert candidate.profile_id == _PROFILE_ID
    assert candidate.declared_node_engine == _DECLARED_NODE_ENGINE
    assert len(candidate.exposures) == 31
    assert candidate.exposures == tuple(sorted(candidate.exposures))
    assert _CANDIDATE_DIRECTORY == _REPO_ROOT / "experiments" / "pi_harness_cfg1" / "pi_profile_candidates"
    # the fixed pins ARE the committed bytes' digests, not merely self-consistent
    for suffix, (size, digest) in _ARTIFACT_PINS.items():
        assert pi_fs_leaves.read_payload_file_digest(
            str(_CANDIDATE_DIRECTORY / (_PAYLOAD_FINGERPRINT + suffix)), size
        ).sha256 == digest


def test_pe4b_the_pins_equal_the_bytes_committed_at_the_source_commit(git_executable):
    for suffix, (size, digest) in _ARTIFACT_PINS.items():
        relative = f"experiments/pi_harness_cfg1/pi_profile_candidates/{_PAYLOAD_FINGERPRINT}{suffix}"
        completed = subprocess.run(  # noqa: S603 - fixed argv, shell=False, read-only git
            [git_executable, "-C", str(_REPO_ROOT), "cat-file", "blob", f"{_SOURCE_COMMIT}:{relative}"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode != 0:
            pytest.skip(f"the source commit is not available in this checkout ({suffix})")
        assert len(completed.stdout) == size and hashlib.sha256(completed.stdout).hexdigest() == digest


@pytest.mark.parametrize("suffix", sorted(_ARTIFACT_PINS))
def test_pe4b_an_edited_committed_artifact_is_refused(suffix, tmp_path, monkeypatch):
    forged = tmp_path / "forged"
    _copy_committed_artifacts(forged)
    target = forged / (_PAYLOAD_FINGERPRINT + suffix)
    data = bytearray(target.read_bytes())
    data[len(data) // 2] ^= 0x01
    target.write_bytes(bytes(data))
    monkeypatch.setitem(globals(), "_CANDIDATE_DIRECTORY", forged)
    with pytest.raises(_Refusal) as refused:
        _load_committed_candidate()
    assert refused.value.code == "PE4B_CANDIDATE_ARTIFACT_PIN_MISMATCH"


@pytest.mark.parametrize("suffix", sorted(_ARTIFACT_PINS))
def test_pe4b_a_truncated_extended_or_missing_artifact_is_refused(suffix, tmp_path, monkeypatch):
    for label in ("truncated", "extended", "missing"):
        forged = tmp_path / label
        _copy_committed_artifacts(forged)
        target = forged / (_PAYLOAD_FINGERPRINT + suffix)
        if label == "truncated":
            target.write_bytes(target.read_bytes()[:-1])
        elif label == "extended":
            target.write_bytes(target.read_bytes() + b"\n")
        else:
            target.unlink()
        monkeypatch.setitem(globals(), "_CANDIDATE_DIRECTORY", forged)
        with pytest.raises(_Refusal) as refused:
            _load_committed_candidate()
        assert refused.value.code == "PE4B_CANDIDATE_ARTIFACT_PIN_MISMATCH", label


def test_pe4b_a_forged_record_that_claims_authority_or_a_different_floor_is_refused(tmp_path, monkeypatch):
    """A staged look-alike with the right NAME and a record asserting approval has different bytes."""
    forged = tmp_path / "forged"
    _copy_committed_artifacts(forged)
    record_path = forged / (_PAYLOAD_FINGERPRINT + ".candidate.json")
    record = json.loads(record_path.read_bytes())
    for field, value in (("authority", "APPROVED"), ("floor", "C1_SEAM_EQUAL"), ("profile_id", "0" * 64)):
        tampered = dict(record, **{field: value})
        record_path.write_bytes(policy_file_bytes(tampered))
        monkeypatch.setitem(globals(), "_CANDIDATE_DIRECTORY", forged)
        with pytest.raises(_Refusal) as refused:
            _load_committed_candidate()
        assert refused.value.code == "PE4B_CANDIDATE_ARTIFACT_PIN_MISMATCH", field


def test_pe4b_other_staged_candidates_beside_the_real_one_are_never_consulted(tmp_path, monkeypatch):
    staged = tmp_path / "staged"
    _copy_committed_artifacts(staged)
    other = "ab" * 32
    for suffix in _ARTIFACT_PINS:
        (staged / (other + suffix)).write_bytes(b"forged: authority APPROVED\n")
    monkeypatch.setitem(globals(), "_CANDIDATE_DIRECTORY", staged)
    candidate = _load_committed_candidate()
    assert candidate.payload_fingerprint == _PAYLOAD_FINGERPRINT


def test_pe4b_a_link_in_place_of_a_committed_artifact_is_refused(tmp_path, monkeypatch):
    forged = tmp_path / "forged"
    _copy_committed_artifacts(forged)
    elsewhere = tmp_path / "elsewhere.json"
    target = forged / (_PAYLOAD_FINGERPRINT + ".candidate.json")
    elsewhere.write_bytes(target.read_bytes())  # byte-identical content, reached through a link
    target.unlink()
    try:
        os.symlink(str(elsewhere), str(target))
    except (OSError, NotImplementedError):  # pragma: no cover - needs the symlink privilege
        pytest.skip("symlink creation is not permitted here")
    monkeypatch.setitem(globals(), "_CANDIDATE_DIRECTORY", forged)
    with pytest.raises(_Refusal) as refused:
        _load_committed_candidate()
    assert refused.value.code == "PE4B_CANDIDATE_ARTIFACT_PIN_MISMATCH"


def test_pe4b_a_candidate_object_cannot_be_constructed_without_the_loader_key():
    with pytest.raises(_Refusal):
        _CommittedCandidate(
            object(), payload_fingerprint="0" * 64, profile_id="0" * 64, exposures=(),
            inventory_file_bytes=b"", declared_node_engine=_DECLARED_NODE_ENGINE,
        )
    with pytest.raises(AttributeError):
        _load_committed_candidate().payload_fingerprint = "0" * 64  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 8. Offline: the ordinary APS gate is unchanged, and (before PE-5) the candidate could not satisfy it
# ---------------------------------------------------------------------------

#: SHA-256 of each ordinary gate function's exact source, as it stood at the source commit's
#: working tree before PE-4B. Any edit to the ordinary authority gate breaks these on purpose.
_ORDINARY_GATE_DIGESTS = {
    "_installed_pi_root": "a58f7081ede3fb581a64ca965f1f0bba7c873c59aa53342ef4a922a3fa30c41e",
    "_require_installed_profile_approved": "48e48f56e144d35cde14d4d239ee5473d58dd29f470f86838fc02e546ad8eb7f",
    "test_the_installed_pi_payload_is_an_approved_hpp1_profile": (
        "fd9f0bb0843b7db6eac33bca016eedee89c05ea19fade22e3eb719875200a786"
    ),
}


def _ordinary_text() -> str:
    return Path(ordinary.__file__).read_text(encoding="utf-8")


def test_pe4b_the_ordinary_aps_gate_functions_are_byte_for_byte_unchanged():
    text = _ordinary_text()
    for name, digest in _ORDINARY_GATE_DIGESTS.items():
        assert ordinary._function_source_digest(text, name) == digest, name


def test_pe4b_the_ordinary_t3_fixture_still_calls_the_aps_gate_first_and_nothing_else_selects_authority():
    tree = ast.parse(_ordinary_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    def called(function: ast.FunctionDef) -> list[tuple[int, str | None]]:
        return [
            (node.lineno, node.func.id if isinstance(node.func, ast.Name) else None)
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
        ]

    # the ordinary fixture is the ONE function that both applies the gate and prepares the harness
    producers = [
        function
        for function in functions.values()
        if {"_installed_pi_root", "_prepare_t3_harness"} <= {name for _line, name in called(function)}
    ]
    assert len(producers) == 1
    calls = called(producers[0])
    gate = [line for line, name in calls if name == "_installed_pi_root"]
    prepare = [line for line, name in calls if name == "_prepare_t3_harness"]
    assert len(gate) == 1 and len(prepare) == 1 and gate[0] < prepare[0]
    # the ordinary module neither imports nor names anything of this module's authority
    referenced: set[str] = set()  # identifiers it USES, imports it makes, and functions it DEFINES
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.FunctionDef):
            referenced.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    for forbidden in (
        "_load_committed_candidate", "_CommittedCandidate", "_CANDIDATE_DIRECTORY", "_ARTIFACT_PINS",
        "_run_candidate_e4", "_require_exact_candidate", "_resolve_installation", "_AUTHORITY_KEY",
    ):
        assert forbidden not in referenced, forbidden
    # the harness-ordering tests it gained are named for PE-4B, but it imports nothing from this module
    assert not any("pe4b" in name.lower() or "qualification" in name.lower() for name in imported)
    # and it has no qualification parameter, flag or environment gate of its own
    for name in (
        "_installed_pi_root", "_require_installed_profile_approved", "_prepare_t3_harness",
        "_execute_t3_harness", "_minimal_node_environment",
    ):
        parameters = {argument.arg for argument in functions[name].args.args + functions[name].args.kwonlyargs}
        assert not parameters & {"mode", "qualification", "qualify", "candidate_mode", "allow_candidate"}, name
    for fixture in producers:  # the ordinary fixture itself takes only pytest's factory
        assert [a.arg for a in fixture.args.args] == ["tmp_path_factory"]
    # and no ambient switch of any kind selects what it runs (checked precisely in section 10)
    assert "_E4_GATE" not in _ordinary_text() and "E4_EXECUTION" not in _ordinary_text()


#: SHA-256 of the exact genesis ``aps.r0001.json`` -- the APS head of the PE-4B source state.
_PRE_PE5_APS_HEAD_SHA256 = "69922eb557e783b9a4bb6e504092a5de4c82812fa477a8bd59b28bf30a53c373"


def test_pe4b_before_pe5_the_candidate_was_not_eligible_in_the_exact_r0001_aps_so_the_ordinary_gate_refused_it(
    tmp_path,
):
    """History, proved mechanically: the PE-4B source state's APS head (exact ``r0001`` bytes,
    alone in an isolated tree, through the real loader) admitted no profile and named neither
    the candidate's profile id nor its fingerprint -- while the candidate already existed in
    staging. Staging was not approval. (The CURRENT APS is deliberately not asserted here.)"""
    data = (_PACKAGE_DIR / "pi_profile_policy" / "aps" / "aps.r0001.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == _PRE_PE5_APS_HEAD_SHA256
    aps = tmp_path / "pre_pe5" / "pi_profile_policy" / "aps"
    aps.mkdir(parents=True)
    (aps / "aps.r0001.json").write_bytes(data)
    load = policy_loader._load_policy_directory(str(aps.parent))
    snapshot = load.snapshot
    assert snapshot.aps_revision == 1 and snapshot.aps_head_sha256 == _PRE_PE5_APS_HEAD_SHA256
    assert _PROFILE_ID not in snapshot.eligible_profile_ids
    assert _PAYLOAD_FINGERPRINT not in {view.payload_fingerprint for view in snapshot.eligible_profiles}
    assert load.profile_declared_versions == ()  # not even present-but-ineligible
    assert _PAYLOAD_FINGERPRINT.encode() not in data and _PROFILE_ID.encode() not in data
    # ... yet the candidate was staged, as a NON-authority record: staging != approval
    candidate = _load_committed_candidate()  # refuses unless the record says NON_AUTHORITY_CANDIDATE
    assert candidate.profile_id == _PROFILE_ID and candidate.payload_fingerprint == _PAYLOAD_FINGERPRINT


def test_pe4b_the_ordinary_gate_accepts_exactly_an_aps_eligible_tree_and_refuses_the_same_tree_changed(
    tmp_path, monkeypatch
):
    """Positive control: the ordinary gate is still the APS membership gate and nothing weaker."""
    tree = build_synthetic_pi_tree(str(tmp_path / "approved"))
    # the synthetic profile is not eligible in the genuine APS, so the genuine gate refuses it
    assert tree.profile_id not in pi_identity.sealed_policy_snapshot().eligible_profile_ids
    with pytest.raises(pytest.fail.Exception, match="PI_PROFILE_UNAPPROVED"):
        ordinary._require_installed_profile_approved(Path(tree.package_root))
    approve_profiles(monkeypatch, tree)
    assert ordinary._require_installed_profile_approved(Path(tree.package_root)) == tree.profile_id
    changed = Path(tree.package_root) / sorted(tree.files)[0]
    changed.write_bytes(changed.read_bytes() + b" ")
    with pytest.raises(pytest.fail.Exception, match="PI_PROFILE_UNAPPROVED"):
        ordinary._require_installed_profile_approved(Path(tree.package_root))


# ---------------------------------------------------------------------------
# 9. Offline: a different install, a persistent drift, and the accepted A->B->A residual
# ---------------------------------------------------------------------------


#: These two prove the launcher's refusal points WITHOUT calling the launcher: they run its first
#: three steps (load, resolve, pre-launch observation) individually. That the launcher performs
#: them in this order, with nothing between the last one and Node, is proved statically in section 10.


def test_pe4b_a_different_pi_install_on_path_is_refused_by_the_pre_launch_observation(tmp_path, monkeypatch):
    decoy = build_synthetic_pi_tree(str(tmp_path / "decoy"))
    monkeypatch.setenv("PATH", decoy.path_value)
    candidate = _load_committed_candidate()
    installation = _resolve_installation()
    with pytest.raises(_Refusal) as refused:
        _require_exact_candidate(candidate, installation, "PRE_LAUNCH")
    assert refused.value.code == "PE4B_PRE_LAUNCH_NOT_THE_COMMITTED_CANDIDATE"


def test_pe4b_no_resolvable_pi_is_refused_at_resolution(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    _load_committed_candidate()
    with pytest.raises(_Refusal) as refused:
        _resolve_installation()
    assert refused.value.code == "PE4B_PI_RESOLUTION_FAILED"


def _candidate_for(tree) -> _CommittedCandidate:
    """TEST-ONLY: a candidate for a SYNTHETIC tree, to exercise the comparator itself.

    It is not an authority object for anything real: ``_run_candidate_e4`` obtains its candidate only
    from ``_load_committed_candidate``, and the static rows below prove no other non-test site
    constructs one.
    """
    leaves = pi_identity.genuine_pi_proof_leaves()
    observation = pi_identity._observe_payload(leaves, tree.package_root)
    assert observation.complete is True
    return _CommittedCandidate(
        _AUTHORITY_KEY,
        payload_fingerprint=observation.payload_fingerprint,
        profile_id="0" * 64,
        exposures=(),
        inventory_file_bytes=policy_file_bytes(observation.inventory.to_record()),
        declared_node_engine=_DECLARED_NODE_ENGINE,
    )


def test_pe4b_a_persistent_change_after_the_child_exits_makes_the_result_unusable(tmp_path, monkeypatch):
    tree = build_synthetic_pi_tree(str(tmp_path / "tree"))
    monkeypatch.setenv("PATH", tree.path_value)
    candidate = _candidate_for(tree)
    installation = _resolve_installation()
    _require_exact_candidate(candidate, installation, "PRE_LAUNCH")
    target = Path(tree.package_root) / sorted(tree.files)[0]
    original = target.read_bytes()
    target.write_bytes(original + b"drift")
    with pytest.raises(_Refusal) as refused:
        _require_exact_candidate(candidate, installation, "POST_EXIT")
    assert refused.value.code == "PE4B_POST_EXIT_NOT_THE_COMMITTED_CANDIDATE"


def test_pe4b_an_added_or_removed_payload_file_is_a_difference_too(tmp_path, monkeypatch):
    tree = build_synthetic_pi_tree(str(tmp_path / "tree"))
    monkeypatch.setenv("PATH", tree.path_value)
    candidate = _candidate_for(tree)
    installation = _resolve_installation()
    added = Path(tree.package_root) / "added_after_observation.js"
    added.write_text("// added", encoding="utf-8")
    with pytest.raises(_Refusal) as refused:
        _require_exact_candidate(candidate, installation, "POST_EXIT")
    assert refused.value.code == "PE4B_POST_EXIT_NOT_THE_COMMITTED_CANDIDATE"
    added.unlink()
    _require_exact_candidate(candidate, installation, "POST_EXIT")


def test_pe4b_a_replaced_node_executable_is_a_drift(tmp_path, monkeypatch):
    tree = build_synthetic_pi_tree(str(tmp_path / "tree"))
    monkeypatch.setenv("PATH", tree.path_value)
    candidate = _candidate_for(tree)
    installation = _resolve_installation()
    node = Path(tree.node_exe)
    replacement = node.read_bytes()
    node.unlink()
    node.write_bytes(replacement)  # same bytes, a different file
    with pytest.raises(_Refusal) as refused:
        _require_exact_candidate(candidate, installation, "POST_EXIT")
    assert refused.value.code == "PE4B_POST_EXIT_NODE_IDENTITY_DRIFTED"


def test_pe4b_the_aba_residual_is_real_and_is_not_claimed_closed(tmp_path, monkeypatch):
    """CHARACTERIZATION, not a guarantee: a change that is undone before the next observation is invisible.

    This is the accepted TOCTOU / A->B->A residual. The two observations bound what the payload WAS at
    two instants; they never prove it was unchanged in between, and nothing may be worded as if they did.
    """
    tree = build_synthetic_pi_tree(str(tmp_path / "tree"))
    monkeypatch.setenv("PATH", tree.path_value)
    candidate = _candidate_for(tree)
    installation = _resolve_installation()
    target = Path(tree.package_root) / sorted(tree.files)[0]
    original = target.read_bytes()
    target.write_bytes(original + b"B")  # state B, never observed...
    target.write_bytes(original)  # ...and restored to A before the next observation
    _require_exact_candidate(candidate, installation, "POST_EXIT")  # passes: the interval is unobserved


# ---------------------------------------------------------------------------
# 10. Offline: the authority surface, proved over this module's own source
# ---------------------------------------------------------------------------


def _module_tree() -> ast.Module:
    return ast.parse(Path(__file__).read_text(encoding="utf-8"))


def _module_functions() -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in _module_tree().body if isinstance(node, ast.FunctionDef)}


_AUTHORITY_FUNCTIONS = {
    "_read_pinned_artifact": ["suffix"],
    "_load_committed_candidate": [],
    "_resolve_installation": [],
    "_require_exact_candidate": ["candidate", "installation", "phase"],
    "_prove_post_exit": ["candidate", "installation", "execution_error"],
    "_execute_candidate_with_total_proof": ["candidate", "installation", "prepared"],
    "_run_candidate_e4": ["tmp_path_factory"],
}


def test_pe4b_the_authority_functions_accept_exactly_the_stated_parameters():
    """No Pi root, fingerprint, profile id, candidate path, policy snapshot, leaf binding or mode."""
    functions = _module_functions()
    for name, parameters in _AUTHORITY_FUNCTIONS.items():
        arguments = functions[name].args
        assert [a.arg for a in arguments.posonlyargs + arguments.args + arguments.kwonlyargs] == parameters, name
        assert arguments.vararg is None and arguments.kwarg is None, name
        assert arguments.defaults == [] and arguments.kw_defaults == [], name


def _names_in(function: ast.FunctionDef) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(node.value)
    return found


def test_pe4b_the_authority_path_consults_no_policy_no_search_and_names_no_launch_target():
    functions = _module_functions()
    forbidden = {
        "sealed_policy_snapshot", "eligible_profile_view", "eligible_profiles", "eligible_profile_ids",
        "SEALED_POLICY_SNAPSHOT", "prove_pi_identity", "pre_consumption_pi_identity_gate",
        "genuine_policy_snapshot", "which", "shutil", "Popen", "run", "subprocess",
        "cli.js", "main.js", "dist/cli.js", "dist/main.js", "rpc-mode.js",
    }
    for name in _AUTHORITY_FUNCTIONS:
        assert not _names_in(functions[name]) & forbidden, (name, _names_in(functions[name]) & forbidden)


def test_pe4b_the_one_launch_is_one_function_in_the_proven_order_with_no_gap_around_node():
    functions = _module_functions()
    launcher = functions["_run_candidate_e4"]

    def calls(statement: ast.stmt) -> list[str]:
        return [
            node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            for node in ast.walk(statement)
            if isinstance(node, ast.Call)
        ]

    def phase(statement: ast.stmt) -> str | None:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_require_exact_candidate":
                return ast.literal_eval(node.args[2])
        return None

    body = launcher.body
    index = {
        "load": next(i for i, s in enumerate(body) if "_load_committed_candidate" in calls(s)),
        "resolve": next(i for i, s in enumerate(body) if "_resolve_installation" in calls(s)),
        "prepare": next(i for i, s in enumerate(body) if "_prepare_t3_harness" in calls(s)),
        "pre": next(i for i, s in enumerate(body) if phase(s) == "PRE_LAUNCH"),
        "unit": next(i for i, s in enumerate(body) if "_execute_candidate_with_total_proof" in calls(s)),
    }
    assert index["load"] < index["resolve"] < index["prepare"] < index["pre"]
    assert index["unit"] == index["pre"] + 1, "a statement sits between the pre-launch observation and Node"
    assert index["unit"] == len(body) - 1, "the launcher continues after the execution unit"
    # the launcher itself never touches the executor, the POST proof or the evidence: the unit owns all three
    launcher_calls = {name for statement in body for name in calls(statement)}
    assert not launcher_calls & {"_execute_t3_harness", "_assert_candidate_e4_evidence", "_prove_post_exit"}
    # exactly one launch call site in all non-test code of this module, and it is the execution unit
    sites = []
    for name, function in functions.items():
        if name.startswith("test_"):
            continue
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") in (
                "_prepare_t3_harness", "_execute_t3_harness"
            ):
                sites.append((name, node.func.attr))
    assert sorted(sites) == [
        ("_execute_candidate_with_total_proof", "_execute_t3_harness"),
        ("_run_candidate_e4", "_prepare_t3_harness"),
    ]


def test_pe4b_only_the_loader_constructs_a_candidate():
    functions = _module_functions()
    constructors = []
    for name, function in functions.items():
        if name.startswith("test_") or name == "_candidate_for":
            continue
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_CommittedCandidate":
                constructors.append(name)
    assert constructors == ["_load_committed_candidate"]


def test_pe4b_the_only_environment_read_is_path_for_p1_and_the_child_environment_is_a_fixed_allowlist():
    tree = _module_tree()
    reads = [
        (function.name, node.attr)
        for function in tree.body
        if isinstance(function, ast.FunctionDef) and not function.name.startswith("test_")
        for node in ast.walk(function)
        if isinstance(node, ast.Attribute) and node.attr in {"environ", "environb", "getenv", "getenvb"}
    ]
    # non-test code only: the one dynamic row of section 14 swaps ``os.environ`` for a tripwire in a TEST
    assert reads == [("_resolve_installation", "environ")], reads
    resolution = ast.unparse(_module_functions()["_resolve_installation"])
    assert resolution.count("os.environ") == 1 and "os.environ.get('PATH')" in resolution
    environment = ordinary._minimal_node_environment(r"C:\synthetic\node.exe")
    assert "PE4B" not in "".join(environment)
    assert set(environment) <= {"SystemRoot", "SystemDrive", "windir", "ComSpec", "PATHEXT", "TEMP", "TMP", "PATH"}
    assert "PATH" in environment


# ---------------------------------------------------------------------------
# 11. Offline: what the launch plan hands Node -- the reach and the engine floor
# ---------------------------------------------------------------------------


def test_pe4b_the_launch_plan_names_four_request_builder_modules_and_no_entry_point(tmp_path):
    tree = build_synthetic_pi_tree(str(tmp_path / "tree"))
    workdir = tmp_path / "work"
    workdir.mkdir()
    prepared = ordinary._prepare_t3_harness(
        Path(tree.package_root), workdir, node_executable=r"C:\synthetic\nodejs\node.exe"
    )
    assert prepared.argv[0] == r"C:\synthetic\nodejs\node.exe"
    assert prepared.argv[1] == str(ordinary._HARNESS) and len(prepared.argv) == 3
    config = json.loads(Path(prepared.argv[2]).read_bytes())
    modules = {key: value for key, value in config.items() if key.endswith("Module")}
    assert set(modules) == {
        "modelConfigModule", "providerComposerModule", "openaiCompletionsModule", "transcriptModule",
    }
    relative = {
        key: Path(value).relative_to(tree.package_root).as_posix() for key, value in modules.items()
    }
    assert relative == {
        "modelConfigModule": "dist/core/model-config.js",
        "providerComposerModule": "dist/core/provider-composer.js",
        "openaiCompletionsModule": "node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js",
        "transcriptModule": "node_modules/@earendil-works/pi-ai/dist/utils/transcript.js",
    }
    for value in relative.values():
        assert not value.endswith(("cli.js", "main.js", "rpc-mode.js")) and "/extensions/" not in value
    assert config["systemPrompt"] == _SYSTEM_PROMPT and config["userPrompt"] == _USER_PROMPT
    # explicit, minimal child environment: no credential, endpoint, proxy or gate name
    for name in prepared.environment:
        upper = name.upper()
        assert not any(fragment in upper for fragment in ordinary._FORBIDDEN_ENVIRONMENT_FRAGMENTS), name
    assert config["apiKey"] == ordinary.SYNTHETIC_API_KEY == "cfg1-synthetic-key"
    assert ordinary.SYNTHETIC_BASE_URL == "http://cfg1-conformance.invalid/v1"  # reserved, non-resolving


def test_pe4b_the_in_process_engine_floor_equals_the_declared_floor_of_the_committed_manifest():
    candidate = _load_committed_candidate()
    match = re.fullmatch(r">=(\d+)\.(\d+)\.(\d+)", candidate.declared_node_engine)
    assert match is not None
    declared = tuple(int(group) for group in match.groups())
    harness_floor = tuple(int(token) for token in ordinary._js_tokens(ordinary._JS_NODE_FLOOR) if token.isdigit())
    # the harness compares the FULL major.minor.patch tuple, so patch is part of the equality
    assert harness_floor == declared == (22, 19, 0)


def test_pe4b_no_node_pi_npm_or_backend_is_started_by_anything_offline_in_this_module():
    """Static: every ``subprocess`` use here is the read-only git corroboration; ``_execute_t3_harness`` is
    reachable only from the one execution unit that the prepared launcher alone calls (section 12/13), never
    directly from a test."""
    tree = _module_tree()
    callers = []
    for function in tree.body:
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if isinstance(node, ast.Attribute) and node.attr in {"run", "Popen", "check_output", "call"}:
                if isinstance(node.value, ast.Name) and node.value.id == "subprocess":
                    callers.append(function.name)
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "_execute_t3_harness":
                callers.append(function.name)
    assert sorted(callers) == [
        "_execute_candidate_with_total_proof",
        "test_pe4b_the_pins_equal_the_bytes_committed_at_the_source_commit",
    ]


# ---------------------------------------------------------------------------
# 12. Offline: NO ordinary pytest path can execute the candidate (no ambient switch, no caller)
# ---------------------------------------------------------------------------
#
# The launcher is prepared and uncalled. These rows prove that over the whole test suite and the
# package, over import time, and over every ambient pytest selection mechanism.

_LAUNCHER = "_run_candidate_e4"
_PROVING_EXECUTOR = "_execute_candidate_with_total_proof"
_POST_PROOF = "_prove_post_exit"
_EXECUTOR = "_execute_t3_harness"
_PREPARER = "_prepare_t3_harness"
_ORDINARY_FILE = "test_cfg1_pi_conformance.py"
_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_TESTS_DIR = Path(__file__).resolve().parent
_THIS_FILE = Path(__file__).resolve().name


def _suite_files() -> list[Path]:
    return sorted(_TESTS_DIR.glob("*.py")) + sorted(_PACKAGE_DIR.glob("*.py"))


def _docstring_ids(tree: ast.AST) -> set[int]:
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                skip.add(id(first.value))
    return skip


def _reference_sites(name: str) -> set[tuple[str, str]]:
    """Every ``(file, top-level owner)`` that names ``name`` as an identifier, attribute, import or string.

    Docstrings are prose and skipped. A string literal counts, because ``getattr(module, "name")`` and
    ``monkeypatch.setattr(module, "name", ...)`` are references too.
    """
    sites: set[tuple[str, str]] = set()
    for path in _suite_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = _docstring_ids(tree)
        for top in tree.body:
            owner = top.name if isinstance(top, (ast.FunctionDef, ast.ClassDef)) else "<module>"
            for node in ast.walk(top):
                hit = (
                    (isinstance(node, ast.Name) and node.id == name)
                    or (isinstance(node, ast.Attribute) and node.attr == name)
                    or (isinstance(node, ast.alias) and node.name == name)
                    or (
                        isinstance(node, ast.Constant)
                        and isinstance(node.value, str)
                        and name in node.value
                        and id(node) not in skip
                    )
                )
                if hit:
                    sites.add((path.name, owner))
    return sites


def test_pe4b_the_prepared_launcher_has_no_caller_anywhere_in_the_suite_or_the_package():
    """The launcher may be NAMED only by the static proofs about it and by the tripwire that replaces it."""
    sites = _reference_sites(_LAUNCHER)
    assert sites == {
        (_THIS_FILE, "<module>"),  # _AUTHORITY_FUNCTIONS' key and _LAUNCHER itself
        (_THIS_FILE, "_no_node_launch_from_this_module"),  # the tripwire that REPLACES it
        (_THIS_FILE, "test_pe4b_the_identity_of_a_run_is_never_read_from_the_report"),
        (_THIS_FILE, "test_pe4b_the_ordinary_t3_fixture_still_calls_the_aps_gate_first_and_nothing_else_selects_authority"),
        (_THIS_FILE, "test_pe4b_the_one_launch_is_one_function_in_the_proven_order_with_no_gap_around_node"),
    }, sites
    # no identifier use of it anywhere in this module, not even from a test: a Name/Attribute is a call or hand-off
    for node in ast.walk(_module_tree()):
        assert not (isinstance(node, ast.Name) and node.id == _LAUNCHER), node.lineno
        assert not (isinstance(node, ast.Attribute) and node.attr == _LAUNCHER), node.lineno


def test_pe4b_the_launcher_is_not_a_fixture_a_test_a_hook_or_decorated():
    functions = _module_functions()
    launcher = functions[_LAUNCHER]
    assert launcher.decorator_list == []
    assert not launcher.name.startswith(("test_", "pytest_"))
    # nothing hands it to pytest through a decorator or default argument either
    for name, other in functions.items():
        if name == _LAUNCHER:
            continue
        evaluated = list(other.decorator_list) + list(other.args.defaults)
        for expression in evaluated:
            for node in ast.walk(expression):
                assert not (isinstance(node, ast.Name) and node.id == _LAUNCHER), name


def test_pe4b_the_tripwire_replaces_both_the_launcher_and_the_executor_for_every_test_here():
    with pytest.raises(AssertionError, match="PE4B"):
        globals()[_LAUNCHER](None)
    with pytest.raises(AssertionError, match="PE4B"):
        getattr(ordinary, _EXECUTOR)(None)


def test_pe4b_the_executor_has_exactly_two_runtime_callers_and_the_ordinary_one_is_aps_gated():
    """No direct ordinary T-3 caller bypasses the APS gate: only the ordinary module-scoped fixture (gate
    first) and the launcher run Node. The fixture is identified structurally, never by name."""
    ordinary_tree = ast.parse(_ordinary_text())

    def callers(name: str) -> set[str]:
        return {
            top.name
            for top in ordinary_tree.body
            if isinstance(top, ast.FunctionDef)
            for node in ast.walk(top)
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == name
        }

    (fixture_name,) = callers(_EXECUTOR)
    assert callers(_PREPARER) == {fixture_name}
    assert fixture_name in callers("_installed_pi_root")
    fixture = next(top for top in ordinary_tree.body if isinstance(top, ast.FunctionDef) and top.name == fixture_name)
    assert [argument.arg for argument in fixture.args.args] == ["tmp_path_factory"]
    assert any(
        isinstance(decorator, ast.Call) and getattr(decorator.func, "attr", "") == "fixture"
        for decorator in fixture.decorator_list
    )
    # in this module the executor is called by the launcher alone; the only other mentions are static
    # proofs about it and the tripwire that replaces it
    calls = {
        top.name
        for top in _module_tree().body
        if isinstance(top, ast.FunctionDef)
        for node in ast.walk(top)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == _EXECUTOR
    }
    assert calls == {_PROVING_EXECUTOR}
    unit_callers = {
        top.name
        for top in _module_tree().body
        if isinstance(top, ast.FunctionDef)
        for node in ast.walk(top)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == _PROVING_EXECUTOR
    }
    # the launcher, plus the fake-driven behavior tests of section 13 (the executor and the POST
    # observation are replaced there, so none of them can start Node)
    assert _LAUNCHER in unit_callers
    assert all(
        name == _LAUNCHER or name == "_run_unit" or name.startswith("test_pe4b_the_total_proof_unit_")
        for name in unit_callers
    ), unit_callers
    # no other file in the suite or the package names either T-3 entry point at all
    for name in (_EXECUTOR, _PREPARER):
        files = {file for file, _owner in _reference_sites(name)}
        assert files <= {_ORDINARY_FILE, _THIS_FILE}, (name, files)


_AMBIENT_SELECTION_NAMES = {
    "addoption", "getoption", "getini", "pytestconfig", "iter_markers", "get_closest_marker",
    "pytest_addoption", "pytest_configure", "pytest_collection_modifyitems", "pytest_generate_tests",
    "pytest_runtest_setup", "pytest_sessionstart", "pytest_collection_finish", "pytest_collect_file",
}


def test_pe4b_no_environment_option_marker_or_hook_can_select_an_execution():
    """There is no ambient switch: no option, ini value, marker lookup, collection hook or gate name exists
    anywhere in the suite or the package that could turn a static run into an executing one."""
    for path in _suite_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert node.name not in _AMBIENT_SELECTION_NAMES, (path.name, node.name)
            if path.name == _THIS_FILE:
                continue  # this module's own mentions are the names in the set above
            identifier = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
            assert identifier not in _AMBIENT_SELECTION_NAMES, (path.name, identifier)
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Name):
            assert node.id not in {"_E4_GATE_NAME", "_E4_GATE_VALUE", "candidate_e4_report"}, node.id
    for path in _suite_files():
        if path.name != _THIS_FILE:
            text = path.read_text(encoding="utf-8")
            for needle in ("PE4B_E4_EXECUTION", "RUN_E4_AGAINST"):
                assert needle not in text, (path.name, needle)
    # the project pytest configuration carries no option / marker / env / addopts that could do it either
    configuration = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_options = configuration.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert set(pytest_options) <= {"testpaths"}, sorted(pytest_options)
    for name in ("pytest.ini", "tox.ini", "setup.cfg", "conftest.py"):
        assert not (_REPO_ROOT / name).exists(), name


def test_pe4b_this_module_has_no_marker_or_skip_condition_that_selects_anything():
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
            assert not (node.value.attr == "mark" and node.attr in {"skipif", "xfail", "usefixtures"}), node.attr


_IMPORT_TIME_FORBIDDEN = {
    "subprocess", "Popen", "system", "spawnv", "spawnl", "startfile", "which",
    _EXECUTOR, _PREPARER, _LAUNCHER,
}


def _import_time_nodes(tree: ast.Module):
    """Every node evaluated when the module is imported: top-level statements, decorators, defaults."""
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = top.args
            defaults = list(arguments.defaults) + [d for d in arguments.kw_defaults if d is not None]
            for expression in list(top.decorator_list) + defaults:
                yield from ast.walk(expression)
        elif isinstance(top, ast.ClassDef):
            for expression in top.decorator_list:
                yield from ast.walk(expression)
            for statement in top.body:
                if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield from ast.walk(statement)
        else:
            yield from ast.walk(top)


def test_pe4b_nothing_executable_exists_at_import_time_in_either_t3_module():
    for path in (Path(__file__), Path(ordinary.__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _import_time_nodes(tree):
            identifier = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
            assert identifier not in _IMPORT_TIME_FORBIDDEN, (path.name, getattr(node, "lineno", None), identifier)


def test_pe4b_importing_either_t3_module_afresh_starts_no_process(monkeypatch):
    """Behavioural twin of the static row: execute both modules from source with every launcher tripwired."""
    hits: list[str] = []

    def _trip(*_args, **_kwargs):  # pragma: no cover - reaching it is the failure
        hits.append("launch")
        raise AssertionError("a T-3 module started a process at import time")

    monkeypatch.setattr(subprocess, "Popen", _trip)
    monkeypatch.setattr(subprocess, "run", _trip)
    monkeypatch.setattr(os, "system", _trip)
    for path in (Path(__file__), Path(ordinary.__file__)):
        spec = importlib.util.spec_from_file_location("_pe4b_fresh_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    assert hits == []


# ---------------------------------------------------------------------------
# 13. Offline: the execution unit's TOTAL post-execution proof, as structure (R-2) and as behavior
# ---------------------------------------------------------------------------
#
# ``_execute_candidate_with_total_proof`` is the only function that calls the harness. It must (a) run a
# fresh POST_EXIT observation exactly once after the execution call has been attempted, whatever that
# call did; (b) never let a POST failure disappear; and (c) return a report only after the
# candidate-specific evidence checks pass (R-5). The structure is proved over source text so that the
# same checker can be run against mutated copies; the behavior is proved with fakes -- no Node.


def _only(items: list, label: str):
    assert len(items) == 1, f"PE4B-PROOF: expected exactly one {label}, found {len(items)}"
    return items[0]


def _call_named(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Call) and (
        getattr(node.func, "id", None) == name or getattr(node.func, "attr", None) == name
    )


def _count_calls(node: ast.AST, name: str) -> int:
    return sum(1 for child in ast.walk(node) if _call_named(child, name))


def _check_total_proof_structure(source: str) -> None:
    """The unit and the launcher have exactly the stated shape, over ``source`` (this module's text)."""
    functions = {node.name: node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
    unit, prove, launcher = functions[_PROVING_EXECUTOR], functions[_POST_PROOF], functions[_LAUNCHER]
    body = unit.body

    # the harness call sits in the body of ONE top-level try that catches BaseException and nothing else
    attempt_index, attempt = _only(
        [(i, st) for i, st in enumerate(body) if isinstance(st, ast.Try)], "execution try"
    )
    assert attempt.orelse == [] and attempt.finalbody == [], "PE4B-PROOF: the execution try has an else/finally"
    handler = _only(attempt.handlers, "execution handler")
    assert ast.unparse(handler.type) == "BaseException", "PE4B-PROOF: the execution handler is not BaseException"
    assert not any(isinstance(n, (ast.Raise, ast.Return, ast.Pass)) for st in handler.body for n in ast.walk(st)), (
        "PE4B-PROOF: the execution handler must only record the failure"
    )
    assert _count_calls(unit, "_execute_t3_harness") == 1
    assert sum(_count_calls(st, "_execute_t3_harness") for st in attempt.body) == 1, (
        "PE4B-PROOF: the harness call is not inside the execution try"
    )

    # the POST proof is ONE unconditional top-level statement after the try, never inside a branch or handler
    proof_index = _only(
        [
            i
            for i, st in enumerate(body)
            if isinstance(st, ast.Expr) and _call_named(st.value, _POST_PROOF)
        ],
        "unconditional POST proof statement",
    )
    assert _count_calls(unit, _POST_PROOF) == 1, "PE4B-PROOF: the POST proof is called more than once"
    assert proof_index > attempt_index, "PE4B-PROOF: the POST proof does not follow the execution attempt"

    # the execution failure is re-raised only AFTER the proof; the evidence runs only after both
    reraise_index = _only(
        [
            i
            for i, st in enumerate(body)
            if isinstance(st, ast.If)
            and ast.unparse(st.test) == "execution_error is not None"
            and [ast.unparse(n) for n in st.body] == ["raise execution_error"]
            and st.orelse == []
        ],
        "execution-failure re-raise",
    )
    evidence_index = _only(
        [
            i
            for i, st in enumerate(body)
            if isinstance(st, ast.Expr) and _call_named(st.value, "_assert_candidate_e4_evidence")
        ],
        "unconditional evidence statement",
    )
    assert _count_calls(unit, "_assert_candidate_e4_evidence") == 1
    returns = [n for n in ast.walk(unit) if isinstance(n, ast.Return)]
    assert [ast.unparse(n) for n in returns] == ["return report"], "PE4B-PROOF: the unit returns something else"
    assert body[-1] is returns[0], "PE4B-PROOF: the report is not returned last"
    assert attempt_index < proof_index < reraise_index < evidence_index < len(body) - 1, (
        "PE4B-PROOF: the unit's steps are not execute -> POST proof -> re-raise -> evidence -> return"
    )

    # the POST proof: exactly one POST_EXIT observation, a handler that can only raise, never swallow
    observation = _only(
        [n for n in ast.walk(prove) if _call_named(n, "_require_exact_candidate")], "POST observation"
    )
    assert ast.literal_eval(observation.args[2]) == "POST_EXIT"
    proof_try = _only([st for st in prove.body if isinstance(st, ast.Try)], "proof try")
    assert [ast.unparse(st) for st in proof_try.body] == [ast.unparse(ast.Expr(observation))]
    assert proof_try.orelse == [] and proof_try.finalbody == []
    proof_handler = _only(proof_try.handlers, "proof handler")
    assert ast.unparse(proof_handler.type) == "Exception"
    assert not any(
        isinstance(n, (ast.Return, ast.Pass, ast.Continue, ast.Break)) for st in proof_handler.body for n in ast.walk(st)
    ), "PE4B-PROOF: the POST proof handler can swallow a failure"
    assert isinstance(proof_handler.body[-1], ast.Raise), "PE4B-PROOF: the POST proof handler does not end in a raise"
    assert ast.unparse(proof_handler.body[-1]) == "raise failure from execution_error"
    assert prove.body[-1] is proof_try, "PE4B-PROOF: code follows the POST proof try"

    # the launcher: the PRE proof, then the unit, then nothing -- and no branch/try around the PRE proof
    last = launcher.body[-1]
    assert isinstance(last, ast.Return) and _call_named(last.value, _PROVING_EXECUTOR)
    assert isinstance(launcher.body[-2], ast.Expr) and _call_named(launcher.body[-2].value, "_require_exact_candidate")
    assert ast.literal_eval(launcher.body[-2].value.args[2]) == "PRE_LAUNCH"
    assert not any(isinstance(st, (ast.Try, ast.If, ast.With)) for st in launcher.body)
    assert [n for n in ast.walk(launcher) if isinstance(n, ast.Return)] == [last]
    for name in ("_execute_t3_harness", "_assert_candidate_e4_evidence", _POST_PROOF):
        assert _count_calls(launcher, name) == 0, f"PE4B-PROOF: the launcher calls {name} itself"


def test_pe4b_the_real_execution_unit_has_the_total_proof_structure():
    _check_total_proof_structure(Path(__file__).read_text(encoding="utf-8"))


def _mutated_module_source(old: str, new: str) -> str:
    source = Path(__file__).read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


_UNIT_MUTATIONS = [
    pytest.param(
        "    _prove_post_exit(candidate, installation, execution_error)\n    if execution_error is not None:",
        "    if execution_error is not None:",
        id="post-proof-removed",
    ),
    pytest.param(
        "    _prove_post_exit(candidate, installation, execution_error)\n    if execution_error is not None:\n        raise execution_error\n",
        "    if execution_error is not None:\n        raise execution_error\n    _prove_post_exit(candidate, installation, execution_error)\n",
        id="post-proof-after-the-re-raise",
    ),
    pytest.param(
        "    except BaseException as error:  # noqa: BLE001 - the POST proof must run for every failure; it is re-raised below\n        execution_error = error\n    _prove_post_exit(candidate, installation, execution_error)\n",
        "    except BaseException as error:  # noqa: BLE001\n        execution_error = error\n    else:\n        _prove_post_exit(candidate, installation, execution_error)\n",
        id="post-proof-only-on-success",
    ),
    pytest.param(
        "    except BaseException as error:  # noqa: BLE001 - the POST proof must run for every failure; it is re-raised below\n        execution_error = error\n    _prove_post_exit(candidate, installation, execution_error)\n",
        "    except Exception as error:  # noqa: BLE001\n        execution_error = error\n    _prove_post_exit(candidate, installation, execution_error)\n",
        id="handler-narrowed-to-exception",
    ),
    pytest.param(
        "    _prove_post_exit(candidate, installation, execution_error)\n    if execution_error is not None:\n        raise execution_error\n    _assert_candidate_e4_evidence(report)\n    return report\n",
        "    _prove_post_exit(candidate, installation, execution_error)\n    _assert_candidate_e4_evidence(report)\n    if execution_error is not None:\n        raise execution_error\n    return report\n",
        id="evidence-before-the-re-raise",
    ),
    pytest.param(
        "    _assert_candidate_e4_evidence(report)\n    return report\n",
        "    return report\n",
        id="evidence-dropped",
    ),
    pytest.param(
        "    _prove_post_exit(candidate, installation, execution_error)\n    if execution_error is not None:\n        raise execution_error\n    _assert_candidate_e4_evidence(report)\n    return report\n",
        "    _prove_post_exit(candidate, installation, execution_error)\n    if execution_error is not None:\n        raise execution_error\n    return report\n    _assert_candidate_e4_evidence(report)\n",
        id="report-returned-before-the-evidence",
    ),
    pytest.param(
        "    if execution_error is not None:\n        raise execution_error\n    _assert_candidate_e4_evidence(report)\n",
        "    _assert_candidate_e4_evidence(report)\n",
        id="execution-failure-never-re-raised",
    ),
    pytest.param(
        "    try:\n        report = ordinary._execute_t3_harness(prepared)\n",
        "    report = ordinary._execute_t3_harness(prepared)\n    try:\n        pass\n",
        id="executor-outside-the-try",
    ),
    pytest.param(
        "        if execution_error is None:\n            raise failure\n        raise failure from execution_error",
        "        if execution_error is None:\n            raise failure\n        return",
        id="post-failure-swallowed-after-an-execution-failure",
    ),
    pytest.param(
        '    _require_exact_candidate(candidate, installation, "PRE_LAUNCH")\n    return _execute_candidate_with_total_proof(candidate, installation, prepared)\n',
        '    try:\n        _require_exact_candidate(candidate, installation, "PRE_LAUNCH")\n    except _Refusal:\n        pass\n    return _execute_candidate_with_total_proof(candidate, installation, prepared)\n',
        id="pre-launch-refusal-swallowed",
    ),
    pytest.param(
        '    _require_exact_candidate(candidate, installation, "PRE_LAUNCH")\n    return _execute_candidate_with_total_proof(candidate, installation, prepared)\n',
        '    _require_exact_candidate(candidate, installation, "PRE_LAUNCH")\n    report = ordinary._execute_t3_harness(prepared)\n    return report\n',
        id="launcher-bypasses-the-unit",
    ),
]


@pytest.mark.parametrize("old, new", _UNIT_MUTATIONS)
def test_pe4b_a_mutated_execution_unit_or_launcher_is_rejected_by_the_structure_proof(old, new):
    with pytest.raises((AssertionError, StopIteration)):
        _check_total_proof_structure(_mutated_module_source(old, new))


def test_pe4b_the_evidence_is_called_by_the_unit_and_by_no_other_non_test_function():
    callers = sorted(
        function.name
        for function in _module_tree().body
        if isinstance(function, ast.FunctionDef)
        and not function.name.startswith("test_")
        and _count_calls(function, "_assert_candidate_e4_evidence") > 0
    )
    assert callers == [_PROVING_EXECUTOR]


# -- behavior, with fakes: nothing here can start Node (the executor and the observation are replaced) ----


class _Placeholder:
    """Stands in for the candidate / installation / prepared plan; the fakes below never inspect them."""


def _arrange(monkeypatch, *, execute, observe=None):
    """Replace the harness call, the POST observation and the evidence recorder; return the event log."""
    events: list[str] = []

    def fake_execute(prepared):
        events.append("execute")
        return execute()

    def fake_observe(candidate, installation, phase):
        events.append(f"observe:{phase}")
        if observe is not None:
            observe()

    real_evidence = globals()["_assert_candidate_e4_evidence"]

    def spying_evidence(report):
        events.append("evidence")
        real_evidence(report)

    monkeypatch.setattr(ordinary, "_execute_t3_harness", fake_execute)
    monkeypatch.setitem(globals(), "_require_exact_candidate", fake_observe)
    monkeypatch.setitem(globals(), "_assert_candidate_e4_evidence", spying_evidence)
    return events


def _run_unit():
    return _execute_candidate_with_total_proof(_Placeholder(), _Placeholder(), _Placeholder())


def _raising(error):
    def execute():
        raise error

    return execute


def _post_drift():
    raise _Refusal("PE4B_POST_EXIT_NOT_THE_COMMITTED_CANDIDATE")


def test_pe4b_the_total_proof_unit_success_observes_post_exactly_once_then_checks_the_evidence(monkeypatch):
    report = _synthetic_report()
    events = _arrange(monkeypatch, execute=lambda: report)
    assert _run_unit() is report
    assert events == ["execute", "observe:POST_EXIT", "evidence"]


def _timeout_expired() -> Exception:
    """The exception the real executor raises on a timeout (constructed, never raised by a launch)."""
    return subprocess.TimeoutExpired(["node"], 180)


_EXECUTION_FAILURES = [
    pytest.param(lambda: AssertionError("child exited with a non-zero status"), id="child-non-zero"),
    pytest.param(lambda: AssertionError("CFG1-T3 refused: Node 22.19.0 or later is required"), id="node-engine-refusal"),
    pytest.param(lambda: _timeout_expired(), id="timeout"),
    pytest.param(lambda: json.JSONDecodeError("Expecting value", "not json", 0), id="malformed-report"),
    pytest.param(lambda: AssertionError("['globalThis.fetch'] could not be intercepted"), id="interception-assertion"),
    pytest.param(lambda: RuntimeError("anything else"), id="any-other-exception"),
    pytest.param(lambda: KeyboardInterrupt(), id="keyboard-interrupt"),
]


@pytest.mark.parametrize("make_error", _EXECUTION_FAILURES)
def test_pe4b_the_total_proof_unit_execution_raises_and_post_succeeds_preserves_the_execution_failure(
    monkeypatch, make_error
):
    error = make_error()
    events = _arrange(monkeypatch, execute=_raising(error))
    with pytest.raises(type(error)) as raised:
        _run_unit()
    assert raised.value is error
    assert events == ["execute", "observe:POST_EXIT"], "POST exactly once, and no evidence for a failed run"


def test_pe4b_the_total_proof_unit_execution_succeeds_and_post_fails_leaves_no_usable_report(monkeypatch):
    events = _arrange(monkeypatch, execute=_synthetic_report, observe=_post_drift)
    with pytest.raises(_Refusal) as raised:
        _run_unit()
    assert raised.value.code == "PE4B_POST_EXIT_NOT_THE_COMMITTED_CANDIDATE"
    assert events == ["execute", "observe:POST_EXIT"], "the evidence must not run after a failed POST proof"


@pytest.mark.parametrize("make_error", _EXECUTION_FAILURES)
def test_pe4b_the_total_proof_unit_execution_raises_and_post_also_fails_keeps_both_failures(monkeypatch, make_error):
    error = make_error()
    events = _arrange(monkeypatch, execute=_raising(error), observe=_post_drift)
    with pytest.raises(_Refusal) as raised:
        _run_unit()
    assert raised.value.code == "PE4B_POST_EXIT_NOT_THE_COMMITTED_CANDIDATE", "the POST failure disappeared"
    assert raised.value.__cause__ is error, "the execution failure is not chained as secondary context"
    assert events == ["execute", "observe:POST_EXIT"]


def test_pe4b_the_total_proof_unit_an_unavailable_post_observation_is_a_post_failure_not_a_pass(monkeypatch):
    def unavailable():
        raise OSError("handle lost")

    events = _arrange(monkeypatch, execute=_synthetic_report, observe=unavailable)
    with pytest.raises(_Refusal) as raised:
        _run_unit()
    assert raised.value.code == "PE4B_POST_EXIT_PROOF_UNAVAILABLE"
    assert isinstance(raised.value.__context__, OSError)
    assert events == ["execute", "observe:POST_EXIT"]
    error = RuntimeError("child failed too")
    events = _arrange(monkeypatch, execute=_raising(error), observe=unavailable)
    with pytest.raises(_Refusal) as raised:
        _run_unit()
    assert raised.value.code == "PE4B_POST_EXIT_PROOF_UNAVAILABLE" and raised.value.__cause__ is error


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda r: r["arms"]["Q"]["params"]["tools"][0]["function"].__setitem__("strict", False), id="strict-key"),
        pytest.param(lambda r: r.__setitem__("approved", True), id="report-claims-a-member"),
        pytest.param(lambda r: r["arms"]["H"].__setitem__("fetchCallsForThisArm", 0), id="transport-unused"),
        pytest.param(lambda r: r["fetchCalls"].append("https://example.invalid/real"), id="foreign-endpoint-call"),
    ],
)
def test_pe4b_the_total_proof_unit_a_report_that_fails_the_evidence_is_never_returned(monkeypatch, mutate):
    report = _copy(_synthetic_report())
    mutate(report)
    events = _arrange(monkeypatch, execute=lambda: report)
    with pytest.raises((AssertionError, KeyError)):
        _run_unit()
    assert events == ["execute", "observe:POST_EXIT", "evidence"], "the evidence runs AFTER the POST proof"


def test_pe4b_the_total_proof_unit_with_the_real_observation_a_drift_during_execution_is_caught(tmp_path, monkeypatch):
    tree = build_synthetic_pi_tree(str(tmp_path / "tree"))
    monkeypatch.setenv("PATH", tree.path_value)
    candidate = _candidate_for(tree)
    installation = _resolve_installation()
    target = Path(tree.package_root) / sorted(tree.files)[0]
    original = target.read_bytes()
    monkeypatch.setattr(ordinary, "_execute_t3_harness", lambda prepared: _drift_then(target, original, _synthetic_report))
    with pytest.raises(_Refusal) as raised:
        _execute_candidate_with_total_proof(candidate, installation, _Placeholder())
    assert raised.value.code == "PE4B_POST_EXIT_NOT_THE_COMMITTED_CANDIDATE"
    # the same drift while the harness FAILED: the drift is still reported, the failure is its cause
    target.write_bytes(original)
    failure = RuntimeError("harness failed")
    monkeypatch.setattr(ordinary, "_execute_t3_harness", lambda prepared: _drift_then(target, original, _raising(failure)))
    with pytest.raises(_Refusal) as raised:
        _execute_candidate_with_total_proof(candidate, installation, _Placeholder())
    assert raised.value.code == "PE4B_POST_EXIT_NOT_THE_COMMITTED_CANDIDATE" and raised.value.__cause__ is failure
    # no drift and a failing harness: the harness failure itself is what surfaces
    target.write_bytes(original)
    monkeypatch.setattr(ordinary, "_execute_t3_harness", lambda prepared: _raising(failure)())
    with pytest.raises(RuntimeError) as raised:
        _execute_candidate_with_total_proof(candidate, installation, _Placeholder())
    assert raised.value is failure
    # no drift and a good report: returned, after the real observation and the real evidence
    monkeypatch.setattr(ordinary, "_execute_t3_harness", lambda prepared: _synthetic_report())
    assert _execute_candidate_with_total_proof(candidate, installation, _Placeholder()) == _synthetic_report()


def _drift_then(target: Path, original: bytes, finish):
    target.write_bytes(original + b"drift")
    return finish()


# ---------------------------------------------------------------------------
# 14. Offline: the candidate evidence path reads no parent environment (R-5)
# ---------------------------------------------------------------------------

_ENVIRONMENT_PRIMITIVES = frozenset({"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"})
_ORDINARY_FILE_PATH = Path(ordinary.__file__).resolve()


def _symbol_table(source: str) -> dict[str, ast.AST]:
    """Top-level functions and top-level assignments, by name."""
    table: dict[str, ast.AST] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef):
            table[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    table[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            table[node.target.id] = node
    return table


def _reachable_environment_reads(
    entry: str, own_source: str, ordinary_source: str
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Walk the static call/reference graph from ``entry`` across this module and the ordinary one.

    An edge is any Name that is a top-level symbol of the current module, any ``ordinary.<name>``
    attribute, and any string constant (docstrings excepted) that names a top-level symbol -- which
    is what a ``getattr(ordinary, name)`` dispatch over a table of names is. Returns
    ``(reads, visited)``, where a read is any use of an environment primitive.
    """
    tables = {"own": _symbol_table(own_source), "ordinary": _symbol_table(ordinary_source)}
    visited: set[tuple[str, str]] = set()
    reads: set[tuple[str, str]] = set()
    pending = [("own", entry)]
    while pending:
        module, name = pending.pop()
        if (module, name) in visited or name not in tables[module]:
            continue
        visited.add((module, name))
        node = tables[module][name]
        skip = _docstring_ids(node)
        # a parameter or local name SHADOWS a same-named module symbol (a fixture parameter such as
        # ``conformance_report`` is a value here, not an edge to the fixture that produces it)
        local = {
            child.arg for child in ast.walk(node) if isinstance(child, ast.arg)
        } | {
            child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)
        }
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute):
                if child.attr in _ENVIRONMENT_PRIMITIVES:
                    reads.add((module, f"{name}:{child.attr}"))
                if isinstance(child.value, ast.Name) and child.value.id == "ordinary":
                    pending.append(("ordinary", child.attr))
            elif isinstance(child, ast.ImportFrom):
                for alias in child.names:
                    if alias.name in _ENVIRONMENT_PRIMITIVES:
                        reads.add((module, f"{name}:import {alias.name}"))
            elif isinstance(child, ast.Name):
                if child.id in _ENVIRONMENT_PRIMITIVES or child.id == "__import__":
                    reads.add((module, f"{name}:{child.id}"))
                if child.id not in local:
                    pending.append((module, child.id))
            elif isinstance(child, ast.Constant) and isinstance(child.value, str) and id(child) not in skip:
                pending.extend((m, child.value) for m in ("own", "ordinary"))
    return reads, visited


def _evidence_graph(own_source: str | None = None, ordinary_source: str | None = None):
    return _reachable_environment_reads(
        "_assert_candidate_e4_evidence",
        Path(__file__).read_text(encoding="utf-8") if own_source is None else own_source,
        _ORDINARY_FILE_PATH.read_text(encoding="utf-8") if ordinary_source is None else ordinary_source,
    )


def test_pe4b_the_candidate_evidence_call_graph_reads_no_environment_at_all():
    reads, visited = _evidence_graph()
    assert reads == set(), sorted(reads)
    # the walk is not vacuous: it reached every retained generic invariant and the shared helpers
    for name in _GENERIC_INVARIANTS:
        assert ("ordinary", name) in visited, name
    for name in ("_check_report_carries_path_only", "_params", "_assert_shared_payload_common"):
        assert ("ordinary", name) in visited, name
    for name in (
        "_assert_report_closed_shape", "_assert_candidate_request_shape",
        "_assert_candidate_report_uses_only_the_synthetic_endpoint", "_FORBIDDEN_REPORT_MARKERS",
    ):
        assert ("own", name) in visited, name
    # and it did NOT reach the two ordinary things that read the parent environment
    assert ("ordinary", "test_t3_no_real_credential_or_endpoint_was_used_anywhere") not in visited
    assert ("ordinary", "_minimal_node_environment") not in visited


def test_pe4b_the_walker_detects_an_environment_read_anywhere_in_the_evidence_graph():
    """Positive controls: the proof above is only meaningful if the walker CAN see these."""
    own = Path(__file__).read_text(encoding="utf-8")
    ordinary_text = _ORDINARY_FILE_PATH.read_text(encoding="utf-8")
    # (1) the ordinary credential test put back among the generic invariants (the pre-FU2 shape)
    restored = own.replace(
        '    "test_t3_err1_p08_the_report_carries_a_path_only",\n)',
        '    "test_t3_err1_p08_the_report_carries_a_path_only",\n    "test_t3_no_real_credential_or_endpoint_was_used_anywhere",\n)',
        1,
    )
    assert restored != own
    assert _evidence_graph(own_source=restored)[0], "a restored ordinary credential check was not detected"
    # (2) a direct read in the candidate-specific assertion
    direct = own.replace(
        "    serialized = json.dumps(report)\n    assert ordinary.SYNTHETIC_BASE_URL in serialized,",
        "    serialized = json.dumps(report)\n    os.environ.get('AIDO_LITELLM_BASE_URL')\n    assert ordinary.SYNTHETIC_BASE_URL in serialized,",
        1,
    )
    assert direct != own and _evidence_graph(own_source=direct)[0]
    # (3) a read two calls deep inside the ordinary module, behind a helper
    deep = ordinary_text.replace(
        "def _params(report, arm_id: str) -> dict:\n",
        "def _params(report, arm_id: str) -> dict:\n    os.getenv('PI_QUALIFICATION_B300_ROUTE_KEY')\n",
        1,
    )
    assert deep != ordinary_text and _evidence_graph(ordinary_source=deep)[0]
    # (4) an aliased import of the primitive
    aliased = own.replace(
        "def _assert_report_closed_shape(report: object) -> None:\n",
        "def _assert_report_closed_shape(report: object) -> None:\n    from os import environ as _e\n    _e.get('X')\n",
        1,
    )
    assert aliased != own
    assert _evidence_graph(own_source=aliased)[0], "an aliased import of an environment primitive was not detected"
    # (5) a dynamic import of the os module
    dynamic = own.replace(
        "def _assert_report_closed_shape(report: object) -> None:\n",
        "def _assert_report_closed_shape(report: object) -> None:\n    __import__('os')\n",
        1,
    )
    assert dynamic != own and _evidence_graph(own_source=dynamic)[0]
    # and neither module imports an environment primitive by name anywhere (module level included)
    for text in (own, ordinary_text):
        imported = {
            alias.name for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom) for alias in node.names
        }
        assert not imported & _ENVIRONMENT_PRIMITIVES


def test_pe4b_running_the_evidence_never_touches_the_process_environment():
    """Dynamic corroboration of the static proof: an environment that fails on ANY access.

    The tripwire is installed and removed INSIDE this body (not through ``monkeypatch``): pytest itself
    reads and writes ``os.environ`` around a test, so it must be restored before the test returns.
    """

    class _Tripwire:
        def _fail(self, *_a, **_k):
            raise AssertionError("PE4B: the candidate evidence path read the process environment")

        __getitem__ = get = __contains__ = __iter__ = keys = items = values = __len__ = copy = _fail

    report = _synthetic_report()  # built BEFORE the tripwire: constructing it is not under test
    saved_environ, saved_getenv = os.environ, os.getenv
    os.environ, os.getenv = _Tripwire(), _Tripwire._fail
    try:
        _assert_candidate_e4_evidence(report)
    finally:
        os.environ, os.getenv = saved_environ, saved_getenv


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda r: r["fetchCalls"].__setitem__(0, "https://b300.example/v1/chat/completions"), id="b300-endpoint"),
        pytest.param(lambda r: r.__setitem__("fetchCalls", []), id="synthetic-endpoint-never-used"),
        pytest.param(
            lambda r: r["arms"]["Q"].__setitem__("streamError", "AIDO_LITELLM_API_KEY leaked"),
            id="credential-marker-in-the-report",
        ),
    ],
)
def test_pe4b_the_report_only_endpoint_assertion_preserves_the_ordinary_semantic(mutate):
    report = _copy(_synthetic_report())
    _assert_candidate_report_uses_only_the_synthetic_endpoint(report)
    mutate(report)
    with pytest.raises(AssertionError, match="PE4B-ENDPOINT"):
        _assert_candidate_report_uses_only_the_synthetic_endpoint(report)


def test_pe4b_the_ordinary_credential_test_is_unchanged_and_not_used_by_the_candidate_path():
    """The ordinary T-3 test still reads the parent environment (unchanged, digest-pinned elsewhere);
    the candidate path simply does not call it."""
    assert "test_t3_no_real_credential_or_endpoint_was_used_anywhere" not in _GENERIC_INVARIANTS
    assert "test_t3_no_real_credential_or_endpoint_was_used_anywhere" not in _names_in(
        _module_functions()["_assert_candidate_e4_evidence"]
    )
    ordinary_source = _ordinary_text()
    assert 'os.environ.get("PI_QUALIFICATION_B300_ROUTE_KEY") is None' in ordinary_source
    assert 'os.environ.get("AIDO_LITELLM_BASE_URL") is None' in ordinary_source
