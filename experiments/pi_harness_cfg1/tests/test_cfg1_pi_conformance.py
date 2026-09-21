"""T-3: offline Pi request-shape conformance, under total network interception.

This is the ONE authorized use of the installed Pi package in this suite, and
it is bounded exactly as the design freezes it:

1. Node runs with an EXPLICIT MINIMAL environment containing no ``AIDO_*``, no
   ``PI_QUALIFICATION_*`` and no proxy variable -- asserted here, in Python,
   BEFORE Node is launched;
2. every network and DNS entry point is replaced with a refusing stub BEFORE
   the first ``import()`` of any installed Pi module;
3. any attempted real network or DNS operation is a test failure, never
   swallowed;
4. the endpoint and key are synthetic literals only -- a reserved,
   non-resolving ``.invalid`` name and a synthetic key. The real base URL and
   real credential are never read, and the conftest has already removed both
   names from the environment entirely;
5. the captured payload is TEST-LOCAL: it is never written to the CFG1 results
   directory and is not experiment evidence;
6. the assertions are exactly the four the design names.

**No Pi model session is launched.** This runs the installed request BUILDER --
the composer and ``streamSimple`` -- against an injected transport that returns
a synthetic streamed response.
"""

from __future__ import annotations

import json
import os
import shutil
import ast
import hashlib
import re
import stat
import subprocess
import sys
import textwrap
import types
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest

from pi_harness_cfg1.arms import ARM_COMPAT
from pi_harness_cfg1.cfg1_pi_config import models_document, serialize_config_document
from pi_harness_cfg1.identity import CFG1_MODEL_ID, PROVIDER_ID

_HARNESS = Path(__file__).resolve().parent / "cfg1_t3_conformance.mjs"

#: Reserved, non-resolving. Chosen so that even a defect that reached the
#: network could not contact anything real.
SYNTHETIC_BASE_URL = "http://cfg1-conformance.invalid/v1"
SYNTHETIC_API_KEY = "cfg1-synthetic-key"

#: The two tools the experiment offers, in the shape the installed converter
#: consumes. Frozen across every arm (Sec. 8.3).
_TOOLS = [
    {
        "name": "aido_read",
        "description": "Read a file from the task's file list.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "aido_edit",
        "description": "Replace the contents of a file the task names.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "sha": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "sha", "content"],
            "additionalProperties": False,
        },
    },
]

#: Arms Q/R/E/H, plus the two Sec. 2.3 controls that must be payload-identical
#: to Q: an EMPTY compat block, and one stating the detected defaults
#: explicitly. Block presence alone is request-inert; absence is equivalent to
#: explicit ``true`` for both flags, never to ``false``.
_EXTRA_CONTROL_COMPAT = {
    "CONTROL_EMPTY": {},
    "CONTROL_EXPLICIT_TRUE": {
        "supportsDeveloperRole": True,
        "supportsReasoningEffort": True,
    },
}


def _installed_pi_root() -> Path:
    shim = shutil.which("pi")
    if not shim:
        pytest.skip("the installed Pi CLI shim is not on PATH")
    npm_bin = Path(os.path.realpath(shim)).parent
    for candidate in (
        npm_bin / "node_modules" / "@earendil-works" / "pi-coding-agent",
        npm_bin.parent / "node_modules" / "@earendil-works" / "pi-coding-agent",
    ):
        resolved = Path(os.path.realpath(candidate))
        if (resolved / "package.json").is_file():
            return resolved
    pytest.skip("the installed Pi package root could not be located")


def _minimal_node_environment() -> dict[str, str]:
    """An explicit, minimal child environment -- never the parent's.

    Asserted by the caller before Node is launched: no ``AIDO_*``, no
    ``PI_QUALIFICATION_*``, no proxy variable, and no credential-looking name.
    """
    environment: dict[str, str] = {}
    for name in ("SystemRoot", "SystemDrive", "windir", "ComSpec", "PATHEXT", "TEMP", "TMP"):
        if name in os.environ:
            environment[name] = os.environ[name]
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available")
    environment["PATH"] = str(Path(os.path.realpath(node)).parent)
    return environment


_FORBIDDEN_ENVIRONMENT_FRAGMENTS = (
    "AIDO_",
    "PI_QUALIFICATION",
    "PROXY",
    "API_KEY",
    "APIKEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
)


class _T3Run(NamedTuple):
    """ERR1 P-10's ONE private, test-local Python-workdir carrier.

    Exactly two members and nothing else: the parsed Node report, and the exact
    ``Path`` that the PYTHON fixture obtained from
    ``tmp_path_factory.mktemp("cfg1_t3")`` in the same run. Its sole purpose is to
    preserve Python's own authority over the T-3 work directory, because the
    report is produced by Node and so cannot be the source of the directory that
    its own claimed sidecar path is checked against (ERR1 P-01/P-02).

    It holds no sidecar path, no model text, no manifest and no schema, and only
    ``test_t3_r37_...`` may request it besides ``conformance_report`` below.
    """

    report: dict
    workdir: Path


@pytest.fixture(scope="module")
def _t3_run(tmp_path_factory):
    """Run the harness ONCE; keep the report AND the work directory Python made."""
    if not shutil.which("node"):  # pragma: no cover - environment dependent
        pytest.skip("node is not available")

    pi_root = _installed_pi_root()
    pi_ai = pi_root / "node_modules" / "@earendil-works" / "pi-ai"
    workdir = tmp_path_factory.mktemp("cfg1_t3")

    arms = []
    for arm_id in ("Q", "R", "E", "H"):
        document = models_document(arm_id=arm_id, base_url=SYNTHETIC_BASE_URL)
        # The `$ENV` apiKey reference is left EXACTLY as CFG1 generates it.
        # Nothing resolves it: the key is supplied through request options
        # instead, so no environment variable is read for it at all.
        path = workdir / f"models_{arm_id}.json"
        path.write_text(serialize_config_document(document), encoding="utf-8")
        arms.append({"armId": arm_id, "modelsJsonPath": str(path)})

    for control_id, compat in _EXTRA_CONTROL_COMPAT.items():
        document = models_document(arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        provider = document["providers"][PROVIDER_ID]
        rebuilt = {}
        for key, value in provider.items():
            if key == "models":
                rebuilt["compat"] = compat
            rebuilt[key] = value
        document["providers"][PROVIDER_ID] = rebuilt
        path = workdir / f"models_{control_id}.json"
        path.write_text(serialize_config_document(document), encoding="utf-8")
        arms.append({"armId": control_id, "modelsJsonPath": str(path)})

    harness_config = {
        "providerId": PROVIDER_ID,
        "modelId": CFG1_MODEL_ID,
        "apiKey": SYNTHETIC_API_KEY,
        "systemPrompt": "Synthetic CFG1 conformance system prompt.",
        "userPrompt": "Synthetic CFG1 conformance user prompt.",
        "tools": _TOOLS,
        "arms": arms,
        "modelConfigModule": str(pi_root / "dist" / "core" / "model-config.js"),
        "providerComposerModule": str(pi_root / "dist" / "core" / "provider-composer.js"),
        "openaiCompletionsModule": str(
            pi_ai / "dist" / "api" / "openai-completions.js"
        ),
    }
    config_path = workdir / "harness_config.json"
    config_path.write_text(json.dumps(harness_config), encoding="utf-8")

    environment = _minimal_node_environment()
    # Rule 1, asserted in PYTHON, BEFORE Node is launched.
    for name in environment:
        upper = name.upper()
        assert not any(
            fragment in upper for fragment in _FORBIDDEN_ENVIRONMENT_FRAGMENTS
        ), name

    completed = subprocess.run(  # noqa: S603 - pinned argv, shell=False
        [os.path.realpath(shutil.which("node")), str(_HARNESS), str(config_path)],
        cwd=str(workdir),
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=180,
        check=False,
    )
    stderr = completed.stderr.decode("utf-8", "replace")
    assert completed.returncode == 0, stderr
    report = json.loads(completed.stdout.decode("utf-8"))

    # Rule 3: any attempted real network or DNS operation is a failure.
    assert report["violations"] == [], report["violations"]
    assert report["failedToInstall"] == [], report["failedToInstall"]
    # Rule 5: the captured payload stays test-local.
    assert str(workdir) not in str(_HARNESS)
    return _T3Run(report=report, workdir=workdir)


@pytest.fixture(scope="module")
def conformance_report(_t3_run):
    """Share the harness's report across the assertions.

    Returns EXACTLY the report object every pre-existing consumer has always
    received -- the same value, with no key added, removed or changed, and never
    carrying the work directory (ERR1 P-10).
    """
    return _t3_run.report


def _params(report, arm_id: str) -> dict:
    arm = report["arms"][arm_id]
    assert arm.get("error") is None, arm
    assert arm["params"] is not None, arm
    return arm["params"]


# ---------------------------------------------------------------------------
# Rule 2 -- interception was genuinely installed, and genuinely used
# ---------------------------------------------------------------------------


def test_t3_every_required_interception_point_was_installed(conformance_report):
    installed = set(conformance_report["installed"])
    for required in (
        "globalThis.fetch",
        "net.connect",
        "net.createConnection",
        "tls.connect",
        "http.request",
        "https.request",
        "dns.lookup",
    ):
        assert required in installed, required
    assert any(name.startswith("dns.resolve") for name in installed)


def test_t3_the_request_went_through_the_injected_transport_only(conformance_report):
    """The fake fetch was genuinely exercised, not merely supplied."""
    assert conformance_report["fetchCalls"], conformance_report
    for url in conformance_report["fetchCalls"]:
        assert "cfg1-conformance.invalid" in url, url
    for arm_id in ("Q", "R", "E", "H"):
        assert conformance_report["arms"][arm_id]["fetchCallsForThisArm"] == 1


# ---------------------------------------------------------------------------
# Assertion 1 -- Q vs R differ ONLY in messages[0].role
# ---------------------------------------------------------------------------


def test_t3_q_and_r_differ_only_in_the_system_message_role(conformance_report):
    q = _params(conformance_report, "Q")
    r = _params(conformance_report, "R")

    assert q["messages"][0]["role"] == "developer"
    assert r["messages"][0]["role"] == "system"

    q_normalized = json.loads(json.dumps(q))
    r_normalized = json.loads(json.dumps(r))
    q_normalized["messages"][0]["role"] = "<role>"
    r_normalized["messages"][0]["role"] = "<role>"
    assert q_normalized == r_normalized


# ---------------------------------------------------------------------------
# Assertion 2 -- Q vs E differ ONLY in the presence of reasoning_effort
# ---------------------------------------------------------------------------


def test_t3_q_and_e_differ_only_in_the_presence_of_reasoning_effort(conformance_report):
    q = _params(conformance_report, "Q")
    e = _params(conformance_report, "E")

    assert q["reasoning_effort"] == "medium"
    assert "reasoning_effort" not in e or e["reasoning_effort"] is None

    q_normalized = {k: v for k, v in q.items() if k != "reasoning_effort"}
    e_normalized = {k: v for k, v in e.items() if k != "reasoning_effort"}
    assert q_normalized == e_normalized
    # And the role is UNAFFECTED by the effort flag -- the two decisions read
    # different compat fields and are coupled only through `model.reasoning`.
    assert e["messages"][0]["role"] == "developer"


def test_t3_h_combines_both_single_variable_effects(conformance_report):
    h = _params(conformance_report, "H")
    assert h["messages"][0]["role"] == "system"
    assert "reasoning_effort" not in h or h["reasoning_effort"] is None


# ---------------------------------------------------------------------------
# Assertion 3 -- block PRESENCE alone is request-inert (Sec. 2.3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("control_id", sorted(_EXTRA_CONTROL_COMPAT))
def test_t3_an_empty_or_explicitly_true_compat_block_is_payload_identical_to_q(
    control_id, conformance_report
):
    """Option A ("compat block only") is not a live variable, proven offline.

    Resolution is per-field ``??``, so a block holding only the two named flags
    changes exactly those effective fields -- and a block holding neither, or
    holding them at their detected values, changes nothing at all. Absence is
    equivalent to explicit ``true`` for both, never to ``false``.
    """
    assert _params(conformance_report, control_id) == _params(conformance_report, "Q")


# ---------------------------------------------------------------------------
# Assertion 4 -- the SERIALIZED model object's compat shape, per arm (Sec. 2.5)
# ---------------------------------------------------------------------------


def test_t3_the_serialized_model_carries_exactly_the_declared_compat_shape(
    conformance_report,
):
    """What ``get_state`` can report is the DECLARED shape, never the effective one.

    CFG1-L16-FU2 scope correction (Sec. 11.6): ``serializedModelReasoning is
    True`` below is a COMPOSER-LEVEL fact about the installed serializer. It is
    not, and must never be cited as, live-path evidence: AR2 ingestion drops
    every ``reasoning`` key before any record is published, which is exactly
    why the v1 L16 projection could never observe it. The live-path link is
    R-37, below.
    """
    q = conformance_report["arms"]["Q"]
    assert q["serializedModelHasCompatKey"] is False  # JSON.stringify drops undefined
    assert q["serializedCompat"] is None

    assert conformance_report["arms"]["R"]["serializedCompat"] == {
        "supportsDeveloperRole": False
    }
    assert conformance_report["arms"]["E"]["serializedCompat"] == {
        "supportsReasoningEffort": False
    }
    assert conformance_report["arms"]["H"]["serializedCompat"] == {
        "supportsDeveloperRole": False,
        "supportsReasoningEffort": False,
    }
    for arm_id in ("Q", "R", "E", "H"):
        assert conformance_report["arms"][arm_id]["serializedModelReasoning"] is True


#: R-37's ``get_state`` response frame, as literal CONSTANTS. The model operand
#: between them is the sidecar text and nothing else (ERR1 P-07): the frame is
#: assembled by plain concatenation, never by parsing and rebuilding the model.
_R37_FRAME_PREFIX = (
    '{"id":"__ID__","type":"response","command":"get_state","success":true,'
    '"data":{"model":'
)
_R37_FRAME_SUFFIX = (
    ',"thinkingLevel":"medium","isStreaming":false,'
    '"sessionFile":"C:/synthetic/session.jsonl","sessionId":"synthetic-session"}}'
)


def test_t3_r37_the_installed_composers_model_survives_the_real_receive_boundary(
    conformance_report, _t3_run, tmp_path, tmp_path_factory
):
    """R-37: ``wire -> AR2 ingestion -> supervisor -> CFG1 L16``, per arm.

    REPLACES the former T-3 projection test, whose docstring claimed to "close
    the loop between Sec. 2.5's source derivation and Sec. 8.2's live
    manipulation check". That was an overclaim (CFG1-L16-FU2 Sec. 11.6): it
    proved only COMPOSER SHAPE -> PROJECTION LOGIC, by handing a hand-built dict
    to the projection, and so bypassed AR2 ingestion -- the exact place the
    ``reasoning`` flag was being dropped.

    Transport per ERR1 (which supersedes R-37's one transport sentence): the
    installed composer's model object, serialized by ``JSON.stringify``
    (synthetic ``.invalid`` base URL only), is written by the harness to a
    TEST-LOCAL sidecar beside that arm's ``models.json``; the report carries only
    that path, because the frozen no-``b300`` regression scans the whole report
    and the model legitimately contains the frozen provider id. The path is a
    CLAIM: it is verified against pytest's base temp and against the work
    directory the PYTHON fixture itself created (P-01, P-02), never trusted. The
    exact text is then embedded VERBATIM in one LF-terminated ``get_state`` frame
    shaped exactly as Sec. 16 establishes Pi emits it. A synthetic peer under
    ``tmp_path`` answers the REAL supervisor's probe with that frame, echoing the
    probe-minted id, and the REAL L16 function consumes the result. No Pi
    process is launched.

    Row map (ERR1 Sec. 5): P-01/P-02 provenance, P-03 exact text, P-04
    synthetic-only, P-06 per-arm isolation, P-07 verbatim frame, P-09 no durable
    evidence. P-05/P-08/P-10 are proved by the static rows in the ERR1 section
    at the end of THIS module (ERR1 keeps every check in this one module).
    """
    from ar2.protocol import contains_reasoning
    from cfg1_fu2_support import cfg1_supervisor, support

    from pi_harness_cfg1.arms import ARM_SHAPE
    from pi_harness_cfg1.records import build_cfg1_run_payload
    from pi_harness_cfg1.run_executor import (
        _initial_observations,
        _RunState,
        observe_l16_runtime_capabilities,
    )

    # P-02(i): the report this test uses and the work directory it holds come
    # from the ONE fixture run; and the report is the value every existing test sees
    assert conformance_report is _t3_run.report
    basetemp = tmp_path_factory.getbasetemp()
    assert len({ARM_SHAPE[arm] for arm in ("Q", "R", "E", "H")}) == 4  # P-06's premise
    claimed_paths: dict[str, str] = {}
    texts: dict[str, str] = {}

    for arm_id in ("Q", "R", "E", "H"):
        arm_report = conformance_report["arms"][arm_id]
        claimed = arm_report["serializedModelPath"]
        resolved = _check_claimed_path(claimed, basetemp=basetemp)  # P-01
        expected = _check_provenance(  # P-02
            claimed, resolved, arm_id=arm_id, workdir=_t3_run.workdir,
            basetemp=basetemp, base_url=SYNTHETIC_BASE_URL,
        )
        model_text = _read_exact_sidecar_text(expected, arm_report)  # P-03
        _check_synthetic_only(  # P-04
            model_text, synthetic_base_url=SYNTHETIC_BASE_URL,
            provider_id=PROVIDER_ID, synthetic_api_key=SYNTHETIC_API_KEY,
        )
        _check_report_carries_path_only(conformance_report, model_text, PROVIDER_ID)  # P-08
        claimed_paths[arm_id], texts[arm_id] = claimed, model_text

        frame = _R37_FRAME_PREFIX + model_text + _R37_FRAME_SUFFIX  # P-07
        _assert_verbatim_frame(frame, model_text, _R37_FRAME_PREFIX, _R37_FRAME_SUFFIX)
        peer = support.make_peer(tmp_path, f"r37_{arm_id}", **support.respond_config([frame]))
        _assert_peer_serves_exactly(peer, frame, support.PEER_SOURCE)
        supervisor = cfg1_supervisor(peer)
        supervisor.launch()
        try:
            state = _RunState(supervisor=supervisor, l14_launched_supervisor=supervisor)
            l16 = observe_l16_runtime_capabilities(state, arm_id=arm_id)
            wire_bytes = supervisor.stdout_state()["bytes_seen"]
        finally:
            support.close(supervisor)
        # the reader saw exactly the frame (probe id substituted for the
        # placeholder: a 32-hex-character id) plus ONE LF -- nothing else
        assert wire_bytes == len(frame.encode("utf-8")) - len("__ID__") + 32 + 1
        assert l16["h2_provider_model_identity_matched"] is True
        assert l16["runtime_reported_model_reasoning"] == "TRUE"
        assert l16["runtime_reported_compat_shape"] == ARM_SHAPE[arm_id]  # a crossed sidecar cannot pass
        assert l16["runtime_reported_thinking_level"] == "medium"
        assert l16["manipulation_check_agrees"] is True
        for record in supervisor.sanitized_events():
            assert contains_reasoning(record) is False
        observations = _initial_observations()
        observations.update(l16)
        payload = build_cfg1_run_payload(
            stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1,
            observations=observations,
        )
        emitted = _emitted_text(l16, payload)
        assert SYNTHETIC_BASE_URL not in emitted
        assert '"reasoning"' not in emitted
        assert contains_reasoning(payload) is False
        _check_nothing_emitted_names_the_sidecar(emitted, claimed, model_text)  # P-09

    _check_arm_isolation(claimed_paths, texts)  # P-06
    _check_results_dir_has_no_sidecar()  # P-09


def test_t3_err1_p08_the_report_carries_a_path_only(conformance_report):
    """ERR1 P-08/P-10 on the REAL report: the sidecar reaches it only as a path.

    The composed model's text and the frozen provider id are absent from the
    report (the frozen no-``b300`` regression above scans it whole and is
    unchanged), and the only new arm member is ``serializedModelPath``.
    """

    _check_report_carries_path_only(conformance_report, "\x00never-present\x00", PROVIDER_ID)
    _check_harness_source(_HARNESS.read_text(encoding="utf-8"))  # P-03(c), P-05


# ---------------------------------------------------------------------------
# The rest of the Sec. 3.4 payload is frozen and identical across every arm
# ---------------------------------------------------------------------------


def test_t3_the_shared_payload_shape_matches_the_source_derivation(conformance_report):
    q = _params(conformance_report, "Q")
    assert q["model"] == CFG1_MODEL_ID
    assert q["stream"] is True
    assert q["stream_options"] == {"include_usage": True}
    assert q["store"] is False
    assert [tool["function"]["name"] for tool in q["tools"]] == [
        "aido_read",
        "aido_edit",
    ]
    assert all(tool["function"]["strict"] is False for tool in q["tools"])
    assert isinstance(q["max_completion_tokens"], int)
    # Explicitly NOT sent, per Sec. 3.4.
    for absent in ("tool_choice", "temperature", "prompt_cache_key", "priority",
                   "chat_template_kwargs", "max_tokens"):
        assert q.get(absent) is None, absent


def test_t3_no_real_credential_or_endpoint_was_used_anywhere(conformance_report):
    serialized = json.dumps(conformance_report)
    assert SYNTHETIC_BASE_URL in serialized  # the synthetic one WAS used
    for forbidden in ("PI_QUALIFICATION_B300_ROUTE_KEY_VALUE", "b300", "AIDO_LITELLM"):
        assert forbidden not in serialized, forbidden
    assert os.environ.get("PI_QUALIFICATION_B300_ROUTE_KEY") is None
    assert os.environ.get("AIDO_LITELLM_BASE_URL") is None


# ---------------------------------------------------------------------------
# The design's own DEFERRED offline checks, discharged mechanically
# ---------------------------------------------------------------------------


def test_the_pinned_seam_digests_match_the_installed_package_exactly():
    """Sec. 14.2's pinned set, INCLUDING the two this phase was to add.

    A mismatch means the derivation this experiment rests on must be
    re-reviewed -- never that Pi is incompatible, and never that a run may
    proceed with a warning.
    """
    import hashlib

    from pi_harness_cfg1.preflight import (
        PINNED_PI_SEAM_DIGESTS,
        verify_pi_seam_digests,
    )

    pi_root = _installed_pi_root()
    all_match, mismatched = verify_pi_seam_digests(str(pi_root))
    assert mismatched == (), mismatched
    assert all_match is True

    # And the two the design explicitly deferred to CFG1-IMPL are present and
    # genuinely computed from the installed files, not copied from elsewhere.
    for relative in (
        "dist/modes/rpc/jsonl.js",
        "node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js",
    ):
        absolute = pi_root.joinpath(*relative.split("/"))
        actual = hashlib.sha256(absolute.read_bytes()).hexdigest()
        assert actual == PINNED_PI_SEAM_DIGESTS[relative], relative


def test_the_installed_get_state_shape_matches_the_frozen_derivation():
    """The third deferred check: Sec. 2.5 / Sec. 8.2's ``get_state`` shape.

    Confirmed by SOURCE INSPECTION of the installed package, deliberately: the
    only other way to observe a ``get_state`` response is to launch a Pi RPC
    session, which this phase is explicitly forbidden to do. The three facts
    the derivation actually depends on are each asserted separately.
    """
    pi_root = _installed_pi_root()

    # 1. `get_state` returns `session.model` and `session.thinkingLevel`, in a
    #    flat response object -- so `data.model` and `data.thinkingLevel` are
    #    exactly where the projection reads them.
    rpc_mode = (pi_root / "dist" / "modes" / "rpc" / "rpc-mode.js").read_text(
        encoding="utf-8"
    )
    block_start = rpc_mode.index('case "get_state"')
    block = rpc_mode[block_start : rpc_mode.index("return success(id,", block_start)]
    assert "model: session.model," in block
    assert "thinkingLevel: session.thinkingLevel," in block
    # It is the COMPOSED model object, not a projection or a normalized copy.
    assert "getCompat" not in block
    assert "compat:" not in block

    # 2. `session.model` IS `agent.state.model` -- the composed, unnormalized
    #    object whose `compat` key is the merged provider block (or absent).
    agent_session = (pi_root / "dist" / "core" / "agent-session.js").read_text(
        encoding="utf-8"
    )
    model_getter = agent_session[
        agent_session.index("get model()") : agent_session.index("get thinkingLevel()")
    ]
    assert "return this.agent.state.model;" in model_getter

    # 3. The response is serialized with PLAIN `JSON.stringify`, which is what
    #    drops an `undefined` `compat` key entirely for arm Q.
    jsonl = (pi_root / "dist" / "modes" / "rpc" / "jsonl.js").read_text(encoding="utf-8")
    # A RAW string: the source contains the two characters backslash-n inside a
    # template literal, not an actual newline.
    assert r"return `${JSON.stringify(value)}\n`;" in jsonl
    # No replacer, no reviver, no custom serializer -- which is precisely why an
    # `undefined` compat key is DROPPED rather than rendered as null.
    assert "replacer" not in jsonl
    assert "toJSON" not in jsonl


def test_r31_the_installed_rpc_mode_echoes_the_probe_id_and_command_exactly():
    """R-31 (CFG1-L16-FU2 Sec. 16): re-proven by READ-ONLY source inspection.

    ``rpc-mode.js`` is first verified against its ``PINNED_PI_SEAM_DIGESTS``
    entry, then the four facts the probe's correlation rests on are asserted
    in that exact, digest-verified text. Pi is never launched. A mismatch means
    the correlation design must be re-reviewed -- never weakened.
    """
    import hashlib
    import re

    from pi_harness_cfg1.preflight import PINNED_PI_SEAM_DIGESTS

    pi_root = _installed_pi_root()
    relative = "dist/modes/rpc/rpc-mode.js"
    raw = pi_root.joinpath(*relative.split("/")).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PINNED_PI_SEAM_DIGESTS[relative]
    assert (
        PINNED_PI_SEAM_DIGESTS[relative]
        == "e7e4724aa55c5aac73cf36793653b26736200e5c59d58373990fc31028f86477"
    )
    source = raw.decode("utf-8")

    # 1. the success helper returns exactly { id, type: "response", command,
    #    success: true, data }
    assert re.search(
        r'const success = \(id, command, data\) =>.*?'
        r'return \{ id, type: "response", command, success: true, data \};',
        source,
        re.DOTALL,
    )
    # 2. the get_state case returns success(id, "get_state", state)
    block_start = source.index('case "get_state"')
    block = source[block_start : source.index("}", source.index("return success(", block_start))]
    assert 'return success(id, "get_state", state)' in block
    # 3. handleCommand binds the id straight from the command
    assert re.search(
        r"const handleCommand = async \(command\) => \{\s*const id = command\.id;", source
    )
    # 4. a thrown command error echoes the id and the type, with success: false
    assert re.search(r'const error = \(id, command, message\) =>.*?success: false', source, re.DOTALL)
    assert "error(command.id, command.type," in source


def test_the_unregistered_tool_name_derivation_still_holds_in_the_installed_loop():
    """Why Sec. 12.1 row 6 is sound: an unexpected call never reaches AIDO.

    An unregistered tool name gets an immediate "not found" error result inside
    Pi's own agent loop, so it never reaches an extension or the broker -- which
    is exactly why a hallucinated call proves nothing about the intended AIDO
    tool path, and why row 6 routes it to indeterminate BEFORE ``ACTIVE``.
    """
    pi_root = _installed_pi_root()
    agent_loop = (
        pi_root
        / "node_modules"
        / "@earendil-works"
        / "pi-agent-core"
        / "dist"
        / "agent-loop.js"
    ).read_text(encoding="utf-8")
    assert "not found" in agent_loop
    assert "tool_execution_start" in agent_loop
    assert "tool_execution_end" in agent_loop

# ---------------------------------------------------------------------------
# CFG1-L16-FU2-ERR1 -- the R-37 sidecar's verification machinery and rows
#
# ERR1 keeps the exact ``JSON.stringify(model)`` text OUT of the T-3 harness report (the frozen
# no-``b300`` regression scans the whole report) and delivers it through a TEST-LOCAL sidecar.
# Node's report can therefore only CLAIM where that file is; everything below VERIFIES the claim
# against Python-owned anchors (pytest's base temp and the work directory the fixture itself
# created) and never trusts it.
#
# ALL of it lives in this one module, per ERR1 Sec. 5/P-10: the ONLY test-side artifact ADDED is
# the private ``_T3Run`` carrier above; the ``_``-prefixed helpers, the fabricated-claim fixture
# and the rows below are the checks P-01..P-10 themselves, for THIS purpose only. Each helper
# raises ``AssertionError`` beginning with the row (and step) it enforces, so a negative row can
# prove WHICH check caught a fabricated claim. Nothing here grants runtime or filesystem
# authority, none of it is a general artifact/file-handoff mechanism, and nothing deletes,
# replaces, repairs or cleans up any file.
#
# ERR1 row -> where it is proved
#   P-01  R-37 (real) + the P-01 rows        P-06  R-37 (real) + the crossed-sidecar row
#   P-02  R-37 (real) + the P-02 rows         P-07  R-37 (real) + the P-07 rows
#   P-03  R-37 (real) + the P-03 rows         P-08  the frozen-digest and report rows
#   P-04  R-37 (real) + the P-04 row          P-09  R-37 (real) + the P-09 rows
#   P-05  the harness-source rows             P-10  the carrier and single-module rows
# ---------------------------------------------------------------------------

#: This file lives at ``experiments/pi_harness_cfg1/tests/``.
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parents[2]
_EXPERIMENTS_DIR = _REPO_ROOT / "experiments"
_RESULTS_DIR = _EXPERIMENTS_DIR / "pi_harness_cfg1" / "results"

_SIDECAR_SUFFIX = ".composed-model.json"
_FRAME_PLACEHOLDER = "__ID__"

#: The two tokens no non-test module may reference (ERR1 P-09).
_SIDECAR_TOKENS = ("composed-model", "serializedModelPath")

#: SHA-256 of ``test_t3_no_real_credential_or_endpoint_was_used_anywhere``'s exact
#: source segment as it stood at commit ``3a59157`` (and unchanged since its
#: parent): the existing broad no-``b300`` assertion must stay byte-identical
#: (ERR1 P-08).
_FROZEN_NO_B300_TEST_NAME = "test_t3_no_real_credential_or_endpoint_was_used_anywhere"
_FROZEN_NO_B300_TEST_SHA256 = "aa8e1388f4370ff6c1e4f525574f28741a16521ecb55f05ee6539f3025dc621b"

#: The report fields a T-3 arm entry may carry. Exactly ONE is new for ERR1
#: (``serializedModelPath``); every other is pre-existing.
_ALLOWED_ARM_REPORT_KEYS = frozenset(
    {
        "serializedModelHasCompatKey",
        "serializedCompat",
        "serializedModelReasoning",
        "serializedModelPath",
        "params",
        "fetchCallsForThisArm",
        "streamError",
        "error",
    }
)

_URL_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^\"\\\s]*")


def _require(condition: object, label: str, detail: str) -> None:
    if not condition:
        raise AssertionError(f"{label}: {detail}")


# ---------------------------------------------------------------------------
# P-01 -- claimed-path integrity, in the frozen order
# ---------------------------------------------------------------------------


def _is_link_or_reparse(status) -> bool:
    if stat.S_ISLNK(status.st_mode):
        return True
    attributes = getattr(status, "st_file_attributes", None)
    return attributes is not None and bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _check_claimed_path(
    claimed: object,
    *,
    basetemp: Path,
    repo_root: Path = _REPO_ROOT,
    results_dir: Path = _RESULTS_DIR,
    lstat=os.lstat,
) -> Path:
    """ERR1 P-01. Returns the resolved path; the FIRST failure raises.

    Order, exactly: claimed report path -> exact type check -> the lexical path
    itself is not a symlink / reparse point (``lstat``, which never follows) ->
    it is a regular file -> ``resolve(strict=True)`` -> containment on the
    RESOLVED path. Nothing is resolved before the lexical checks, because
    ``resolve()`` and ``stat()`` follow a link and would hide it.
    """
    # (a) exact type
    _require(type(claimed) is str, "P-01(a)", "the claimed path is not an exact str")
    _require(
        claimed != "" and "\x00" not in claimed and os.path.isabs(claimed),
        "P-01(a)",
        "the claimed path is empty, NUL-bearing or not absolute",
    )
    # (b) the LEXICAL path itself, as reported, without following anything
    try:
        status = lstat(claimed)
    except OSError as exc:
        raise AssertionError(f"P-01(b): lstat of the claimed path failed ({exc.__class__.__name__})") from exc
    _require(not stat.S_ISLNK(status.st_mode), "P-01(b)", "the claimed path itself is a symlink")
    _require(not _is_link_or_reparse(status), "P-01(b)", "the claimed path itself is a reparse point")
    # (c) existence and type, from that same lstat result
    _require(stat.S_ISREG(status.st_mode), "P-01(c)", "the claimed path is not a regular file")
    # (d) strict resolution
    try:
        resolved = Path(claimed).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AssertionError(f"P-01(d): strict resolution failed ({exc.__class__.__name__})") from exc
    # (e) containment, on the RESOLVED path only
    base = Path(basetemp).resolve()
    _require(resolved.is_relative_to(base), "P-01(e)", "outside pytest's base temp directory")
    _require(
        not resolved.is_relative_to(Path(results_dir).resolve()),
        "P-01(e)",
        "inside the CFG1 results directory",
    )
    _require(
        not resolved.is_relative_to(Path(repo_root).resolve()),
        "P-01(e)",
        "inside the repository",
    )
    return resolved


# ---------------------------------------------------------------------------
# P-02 -- provenance against the PYTHON-OWNED work directory
# ---------------------------------------------------------------------------


def _expected_arm_paths(workdir: Path, arm_id: str) -> tuple[Path, Path]:
    """``(models_X.json, models_X.json.composed-model.json)``, from workdir + arm id ONLY."""
    models = Path(workdir) / f"models_{arm_id}.json"
    return models, Path(workdir) / f"models_{arm_id}.json{_SIDECAR_SUFFIX}"


def _check_provenance(
    claimed: str,
    resolved: Path,
    *,
    arm_id: str,
    workdir: Path,
    basetemp: Path,
    base_url: str,
    lstat=os.lstat,
) -> Path:
    """ERR1 P-02. Returns the EXPECTED sidecar path every later step reads from.

    ``workdir`` is the ``Path`` the Python fixture itself obtained from
    ``tmp_path_factory.mktemp("cfg1_t3")``. It is never recovered from the
    claimed path, that path's parent, a directory scan or a name prefix.
    """
    from pi_harness_cfg1.cfg1_pi_config import models_document, serialize_config_document

    workdir = Path(workdir)
    try:
        workdir_status = lstat(str(workdir))
    except OSError as exc:
        raise AssertionError("P-02(ii): lstat of the authoritative work directory failed") from exc
    _require(
        stat.S_ISDIR(workdir_status.st_mode) and not _is_link_or_reparse(workdir_status),
        "P-02(ii)",
        "the authoritative work directory is not a real directory",
    )
    _require(
        workdir.parent.resolve() == Path(basetemp).resolve(),
        "P-02(ii)",
        "the authoritative work directory is not directly under pytest's base temp",
    )

    models, expected = _expected_arm_paths(workdir, arm_id)
    _require(
        claimed == str(expected),
        "P-02 path equality",
        "the claimed path is not the sidecar derived from the Python-owned work directory",
    )
    try:
        expected_resolved = expected.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AssertionError("P-02 path equality: the expected sidecar does not resolve") from exc
    _require(
        resolved == expected_resolved,
        "P-02 path equality",
        "the resolved claimed path is not the expected sidecar",
    )
    _require(models.is_file(), "P-02 models.json", "this arm's generated models.json is missing")
    regenerated = serialize_config_document(models_document(arm_id=arm_id, base_url=base_url))
    # decoded text, not bytes: the fixture wrote it with ``write_text``, which
    # translates newlines on Windows
    _require(
        models.read_text(encoding="utf-8") == regenerated,
        "P-02 models.json",
        "this arm's models.json is not the independently regenerated document",
    )
    return expected


# ---------------------------------------------------------------------------
# P-03 / P-04 -- exact text, synthetic-only content
# ---------------------------------------------------------------------------


def _read_exact_sidecar_text(expected: Path, arm_report: dict) -> str:
    """ERR1 P-03. The exact ``JSON.stringify`` text, checked but never re-built.

    Parsing happens HERE, for checks only; the returned value is the decoded
    string itself and no parsed copy leaves this function.
    """
    raw = Path(expected).read_bytes()
    _require(raw != b"", "P-03", "the sidecar is empty")
    _require(not raw.startswith(b"\xef\xbb\xbf"), "P-03", "the sidecar starts with a BOM")
    _require(b"\r" not in raw and b"\n" not in raw, "P-03", "the sidecar contains a CR or LF byte")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AssertionError("P-03: the sidecar is not strict UTF-8") from exc
    _require(text == text.strip(), "P-03", "the sidecar has leading or trailing whitespace")
    _require(_FRAME_PLACEHOLDER not in text, "P-03", "the sidecar contains the frame id placeholder")
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        raise AssertionError("P-03: the sidecar is not JSON") from exc
    _require(isinstance(parsed, dict), "P-03", "the sidecar is not a JSON object")
    _require(
        ("compat" in parsed) == arm_report["serializedModelHasCompatKey"],
        "P-03(b)",
        "compat presence disagrees with the report's scalar",
    )
    _require(
        parsed.get("compat") == arm_report["serializedCompat"],
        "P-03(b)",
        "compat disagrees with the report's scalar",
    )
    _require(
        "reasoning" in parsed and parsed["reasoning"] is arm_report["serializedModelReasoning"],
        "P-03(b)",
        "reasoning disagrees with the report's scalar",
    )
    return text


def _check_synthetic_only(
    text: str, *, synthetic_base_url: str, provider_id: str, synthetic_api_key: str
) -> None:
    """ERR1 P-04."""
    urls = _URL_TOKEN.findall(text)
    _require(urls, "P-04", "no URL token in the sidecar")
    _require(
        all(url == synthetic_base_url for url in urls),
        "P-04",
        "a URL token other than the synthetic base URL",
    )
    _require(
        (urlsplit(synthetic_base_url).hostname or "").endswith(".invalid"),
        "P-04",
        "the synthetic host does not end .invalid",
    )
    for forbidden in ("PI_QUALIFICATION_B300_ROUTE_KEY_VALUE", "AIDO_LITELLM", synthetic_api_key):
        _require(forbidden not in text, "P-04", "a credential-shaped literal is present")
    _require(
        "b300" not in text.replace(provider_id, ""),
        "P-04",
        "lower-case b300 occurs other than as the frozen provider id",
    )


# ---------------------------------------------------------------------------
# P-06 / P-07 -- isolation and the verbatim frame
# ---------------------------------------------------------------------------


def _check_arm_isolation(paths_by_arm: dict[str, str], texts_by_arm: dict[str, str]) -> None:
    """ERR1 P-06: four distinct sidecars and four pairwise-distinct texts."""
    _require(set(paths_by_arm) == {"Q", "R", "E", "H"} == set(texts_by_arm), "P-06", "arm set")
    _require(len(set(paths_by_arm.values())) == 4, "P-06", "sidecar paths are not pairwise distinct")
    _require(len(set(texts_by_arm.values())) == 4, "P-06", "sidecar texts are not pairwise distinct")


def _assert_verbatim_frame(frame: str, text: str, prefix: str, suffix: str) -> None:
    """ERR1 P-07 (runtime half): the model operand is the sidecar text, unaltered."""
    _require(frame == prefix + text + suffix, "P-07", "the frame is not prefix + text + suffix")
    _require(frame[len(prefix) : len(frame) - len(suffix)] == text, "P-07", "the model slice differs from the text")
    _require(frame.count(text) == 1, "P-07", "the text does not occur exactly once")
    _require(frame.count(_FRAME_PLACEHOLDER) == 1, "P-07", "the frame has other than one id placeholder")
    _require("\n" not in frame and "\r" not in frame, "P-07", "the frame is not a single line")


def _assert_peer_serves_exactly(peer, frame: str, peer_source: str) -> None:
    """ERR1 P-07: the peer's configured response IS that frame, plus one LF from the peer."""
    config = json.loads(Path(peer.argv[2]).read_text(encoding="utf-8"))
    _require(config["responses"]["get_state"] == [frame], "P-07", "the peer serves other than the frame")
    _require(
        'line.replace("__ID__", command_id)' in peer_source
        and 'out.write(text.encode("utf-8") + b"\\n")' in peer_source,
        "P-07",
        "the peer's emit routine substitutes other than the placeholder or adds other than one LF",
    )


_JSON_NAMES = frozenset({"json", "_json"})
_FRAME_HELPER_CALLS = frozenset({"_check_synthetic_only", "_assert_verbatim_frame", "_read_exact_sidecar_text"})


def _check_frame_construction_source(function_source: str) -> None:
    """ERR1 P-07 (AST half): the frame is ``PREFIX + model_text + SUFFIX`` and nothing more.

    The single ``frame`` assignment is a chain of ``+`` whose only leaves are the
    three names, in order; ``model_text`` is bound exactly once, from
    ``_read_exact_sidecar_text``; and the function makes no JSON call and names no
    ``json`` module at all, so no parsed copy can reach the frame.
    """
    function = ast.parse(textwrap.dedent(function_source)).body[0]
    _require(isinstance(function, ast.FunctionDef), "P-07", "not a function")
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and node.id in _JSON_NAMES:
            raise AssertionError("P-07: the test body references a json module")
    frames = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "frame"
    ]
    _require(len(frames) == 1, "P-07", "the frame is not assigned exactly once")

    leaves: list[str] = []

    def _flatten(expression: ast.AST) -> None:
        if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
            _flatten(expression.left)
            _flatten(expression.right)
        elif isinstance(expression, ast.Name):
            leaves.append(expression.id)
        else:
            raise AssertionError(
                f"P-07: the frame expression contains a {type(expression).__name__}, "
                "not a plain concatenation of names"
            )

    _flatten(frames[0].value)
    _require(
        leaves == ["_R37_FRAME_PREFIX", "model_text", "_R37_FRAME_SUFFIX"],
        "P-07",
        f"the frame operands are {leaves}",
    )
    bindings = [
        node
        for node in ast.walk(function)
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id == "model_text"
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        )
    ]
    _require(len(bindings) == 1, "P-07", "model_text is not bound exactly once")
    value = bindings[0].value
    _require(
        isinstance(bindings[0], ast.Assign)
        and isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "_read_exact_sidecar_text",
        "P-07",
        "model_text is not the direct result of _read_exact_sidecar_text",
    )


def _check_r37_provenance_call_sites(function_source: str) -> None:
    """ERR1 P-02 (AST half): R-37 hands the verifiers PYTHON-owned anchors only.

    On an honest run the report's parent IS the work directory, so a test that
    derived its anchor from the report would still pass -- which is exactly why
    the call site must be pinned mechanically rather than by behaviour.
    """
    function = ast.parse(textwrap.dedent(function_source)).body[0]
    provenance = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_check_provenance"
    ]
    _require(len(provenance) == 1, "P-02", "R-37 does not call _check_provenance exactly once")
    workdir = [keyword for keyword in provenance[0].keywords if keyword.arg == "workdir"]
    _require(
        len(workdir) == 1 and ast.unparse(workdir[0].value) == "_t3_run.workdir",
        "P-02",
        "the work directory handed to _check_provenance is not exactly _t3_run.workdir",
    )
    basetemps = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "basetemp"
    ]
    _require(
        len(basetemps) == 1 and ast.unparse(basetemps[0].value) == "tmp_path_factory.getbasetemp()",
        "P-01",
        "the containment anchor is not exactly tmp_path_factory.getbasetemp()",
    )
    for node in ast.walk(function):
        _require(
            not (isinstance(node, ast.Attribute) and node.attr in {"parent", "parents"}),
            "P-02",
            "R-37 derives a path from another path's parent",
        )
        _require(
            not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path"),
            "P-02",
            "R-37 builds a Path from the claimed string",
        )


def _check_r37_reads_no_environment(function_source: str) -> None:
    """ERR1 P-05 (AST half): the R-37 test body reads no environment and no file itself.

    Its only file read is ``_read_exact_sidecar_text``, whose target is the
    verified expected path. (The synthetic peer's launch helper builds a minimal
    OS-launch environment elsewhere; that is a shared, pre-existing helper and is
    not part of this body.)
    """
    function = ast.parse(textwrap.dedent(function_source)).body[0]
    for node in ast.walk(function):
        _require(
            not (isinstance(node, ast.Attribute) and node.attr in {"environ", "environb", "getenv"}),
            "P-05",
            "the R-37 body reads the process environment",
        )
        _require(
            not (isinstance(node, ast.Name) and node.id in {"os", "environ", "getenv", "open"}),
            "P-05",
            "the R-37 body names os/environ/getenv/open",
        )
        _require(
            not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"read_text", "read_bytes", "open"}
            ),
            "P-05",
            "the R-37 body reads a file directly instead of through the verified reader",
        )


# ---------------------------------------------------------------------------
# P-08 / P-09 / P-10
# ---------------------------------------------------------------------------


def _function_source_digest(file_text: str, name: str) -> str:
    """SHA-256 of one top-level function's exact source segment (LF-normalized text)."""
    text = file_text.replace("\r\n", "\n")
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return hashlib.sha256(ast.get_source_segment(text, node).encode("utf-8")).hexdigest()
    raise AssertionError(f"P-08: {name} does not exist")


def _walk(value: object):
    yield value
    if isinstance(value, dict):
        for member in value.values():
            yield from _walk(member)
    elif isinstance(value, list):
        for member in value:
            yield from _walk(member)


def _check_report_carries_path_only(report: dict, model_text: str, provider_id: str) -> None:
    """ERR1 P-08/P-10: the sidecar reaches the report only as a path string.

    The model can be embedded in three ways, and a raw substring test against
    ``json.dumps(report)`` catches only one of them (a string is quote-escaped
    there, and an object is re-rendered with different separators). So all three
    are checked: the text as a string value, its JSON-escaped and compact forms,
    and the parsed object as a structural member.
    """
    for form in (json.dumps(report), json.dumps(report, separators=(",", ":"))):
        _require(model_text not in form, "P-08", "the serialized model text is in the report")
        _require(
            json.dumps(model_text)[1:-1] not in form,
            "P-08",
            "the serialized model text is in the report (JSON-escaped)",
        )
    try:
        parsed = json.loads(model_text)
    except ValueError:
        parsed = None
    for node in _walk(report):
        _require(
            not (isinstance(node, str) and model_text in node),
            "P-08",
            "a report string contains the serialized model text",
        )
        _require(
            not (isinstance(parsed, dict) and node == parsed),
            "P-08",
            "the composed model object is embedded in the report",
        )
    _require(provider_id not in json.dumps(report), "P-08", "the provider id is in the report")
    for arm_id in ("Q", "R", "E", "H"):
        arm = report["arms"][arm_id]
        _require(isinstance(arm.get("serializedModelPath"), str), "P-08", "serializedModelPath is not a str")
        _require(
            set(arm) <= _ALLOWED_ARM_REPORT_KEYS,
            "P-10",
            f"the arm entry gained a member: {sorted(set(arm) - _ALLOWED_ARM_REPORT_KEYS)}",
        )


def _emitted_text(*objects: object) -> str:
    """What CFG1 would emit for these objects, as one string (the R-37 test has no JSON call)."""
    return json.dumps(list(objects))


def _check_nothing_emitted_names_the_sidecar(emitted: str, claimed: str, model_text: str) -> None:
    """ERR1 P-09: neither the path, its filename nor its text reaches emitted evidence."""
    _require(claimed not in emitted, "P-09", "the emitted text carries the sidecar path")
    _require(json.dumps(claimed)[1:-1] not in emitted, "P-09", "the emitted text carries the escaped sidecar path")
    _require(_SIDECAR_SUFFIX not in emitted, "P-09", "the emitted text carries the sidecar filename")
    _require(model_text not in emitted, "P-09", "the emitted text carries the sidecar text")


def _check_results_dir_has_no_sidecar(results_dir: Path = _RESULTS_DIR) -> None:
    """ERR1 P-09: no ``*composed-model*`` file anywhere under the CFG1 results directory."""
    if Path(results_dir).exists():
        leaked = sorted(str(path) for path in Path(results_dir).rglob("*composed-model*"))
        _require(not leaked, "P-09", "a sidecar file exists under the results directory")


_SKIPPED_PARTS = frozenset({"tests", "results", "__pycache__", "node_modules", ".git"})


def _nontest_files_referencing_the_sidecar(root: Path = _EXPERIMENTS_DIR) -> list[str]:
    """ERR1 P-09: every NON-TEST source file under ``root`` naming either sidecar token."""
    found: list[str] = []
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".mjs", ".js", ".cjs", ".ts"}:
            continue
        parts = set(path.relative_to(root).parts)
        if parts & _SKIPPED_PARTS or path.name.startswith("test_"):
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if any(token in content for token in _SIDECAR_TOKENS):
            found.append(str(path))
    return found


# ---------------------------------------------------------------------------
# ERR1 P-03(c) / P-05 -- the harness SOURCE proof, over TOKENS (not regexes)
# ---------------------------------------------------------------------------
#
# A regex over the source can prove that something IS present but never that
# nothing ELSE uses a value. So the proof is a token-level one: comments are
# dropped, every string and template chunk becomes one opaque token, and for
# each identifier that can carry model-derived content (or reach the process)
# the harness must contain EXACTLY the authorized statements that mention it,
# and the identifier's total token count must equal what those statements
# account for. Any additional mention -- an alias, a spread, a destructure, a
# base64/hex/escape wrapper, a use inside an existing report field -- adds a
# token and fails. The lexer refuses (rather than guesses) a bare ``/``, i.e.
# a regex literal or a division, because it cannot tokenize those reliably.

_JS_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_JS_NUMBER = re.compile(r"[0-9][0-9A-Za-z_.]*")
_JS_PUNCT = re.compile(
    r"\.\.\.|===|!==|=>|\?\?=?|\?\.|&&|\|\||==|!=|<=|>=|\+\+|--|[-+*%&|^<>]=?|[=!]|[(){}\[\];,.:?~]"
)
_JS_TEMPLATE_CHUNK = "\x01"  # marks a literal template chunk, so it can never equal an identifier


def _js_lex(source: str, index: int, *, inside_template_expression: bool) -> tuple[list[str], int]:
    tokens: list[str] = []
    depth = 0
    length = len(source)
    while index < length:
        char = source[index]
        if char.isspace():
            index += 1
        elif source.startswith("//", index):
            newline = source.find("\n", index)
            index = length if newline == -1 else newline
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            _require(end != -1, "P-05", "an unterminated block comment in the harness")
            index = end + 2
        elif char in "\"'":
            end = index + 1
            while end < length and source[end] != char:
                end += 2 if source[end] == "\\" else 1
            _require(end < length, "P-05", "an unterminated string literal in the harness")
            tokens.append(source[index : end + 1])
            index = end + 1
        elif char == "`":
            tokens.append("`")
            index += 1
            chunk_start = index
            while index < length and source[index] != "`":
                if source[index] == "\\":
                    index += 2
                elif source.startswith("${", index):
                    if index > chunk_start:
                        tokens.append(_JS_TEMPLATE_CHUNK + source[chunk_start:index])
                    tokens.append("${")
                    inner, index = _js_lex(source, index + 2, inside_template_expression=True)
                    tokens.extend(inner)
                    tokens.append("}")
                    chunk_start = index
                else:
                    index += 1
            _require(index < length, "P-05", "an unterminated template literal in the harness")
            if index > chunk_start:
                tokens.append(_JS_TEMPLATE_CHUNK + source[chunk_start:index])
            tokens.append("`")
            index += 1
        elif char == "/":
            raise AssertionError(
                "P-05: the harness has a '/' outside a comment or string (a regex literal or a "
                "division), which the source proof does not tokenize"
            )
        else:
            match = _JS_IDENT.match(source, index) or _JS_NUMBER.match(source, index)
            if match is not None:
                tokens.append(match.group(0))
                index = match.end()
                continue
            match = _JS_PUNCT.match(source, index)
            _require(match is not None, "P-05", f"an unrecognized character {char!r} in the harness")
            text = match.group(0)
            if text == "{":
                depth += 1
            elif text == "}":
                if depth == 0 and inside_template_expression:
                    return tokens, index + 1
                depth -= 1
            tokens.append(text)
            index = match.end()
    _require(not inside_template_expression, "P-05", "an unterminated template expression")
    return tokens, index


def _js_tokens(source: str) -> list[str]:
    """Comment-free tokens of ``source``. Strings/template chunks are single opaque tokens."""
    return _js_lex(source, 0, inside_template_expression=False)[0]


def _js_occurrences(tokens: list[str], snippet: list[str]) -> int:
    width = len(snippet)
    return sum(1 for start in range(len(tokens) - width + 1) if tokens[start : start + width] == snippet)


def _js_check_uses(tokens: list[str], table: dict[str, tuple[tuple[str, int], ...]], label: str) -> None:
    """For each identifier: the authorized statements occur the stated number of times, and
    the identifier appears NOWHERE ELSE (its token total equals what those statements hold)."""
    for name, uses in table.items():
        accounted = 0
        for text, times in uses:
            snippet = _js_tokens(text)
            found = _js_occurrences(tokens, snippet)
            _require(
                found == times,
                label,
                f"an authorized use of `{name}` occurs {found} time(s), not {times}: {text[:70]!r}",
            )
            accounted += times * snippet.count(name)
        total = tokens.count(name)
        _require(
            total == accounted,
            label,
            f"`{name}` is used {total - accounted} time(s) beyond its authorized statements",
        )


# The statements, written once. Each is tokenized by the same lexer as the harness.
_JS_FIND_MODEL = "const model = models.find((entry) => entry.id === config.modelId);"
_JS_NOT_FOUND = "if (!model) {"
_JS_STRINGIFY = "const serializedModelJson = JSON.stringify(model);"
_JS_STREAM_CALL = "const stream = streamSimple(model, context, {"
_JS_SIDECAR_PATH = "const serializedModelPath = `${arm.modelsJsonPath}.composed-model.json`;"
_JS_SIDECAR_WRITE = 'writeFileSync(serializedModelPath, serializedModelJson, "utf-8");'
_JS_PARSE = "const serializedModel = JSON.parse(serializedModelJson);"
_JS_GET_MODELS = "const models = provider.getModels();"
_JS_PROVIDER = "const provider = composeModelProvider("
_JS_LOAD_CONFIG = "const modelConfig = await ModelConfig.load(arm.modelsJsonPath);"
_JS_LOAD_ERROR = "const loadError = modelConfig.getError();"
_JS_COMPOSE_ARGS = "config.providerId, undefined, modelConfig, undefined,"
_JS_CAPTURE_DECL = "let capturedParams = null;"
_JS_ON_PAYLOAD = (
    "onPayload: (params) => { capturedParams = JSON.parse(JSON.stringify(params)); return undefined; },"
)
_JS_READ_CONFIG = 'const config = JSON.parse(readFileSync(process.argv[2], "utf-8"));'
_JS_WRITE_REPORT = "process.stdout.write(JSON.stringify(report, null, 2));"
_JS_REPORT_DECL = "const report = { arms: {}, violations, installed, failedToInstall, fetchCalls: [] };"
_JS_REPORT_LOAD_ERROR = "report.arms[arm.armId] = { error: `models.json refused: ${loadError}` };"
_JS_REPORT_NO_MODEL = (
    'report.arms[arm.armId] = { error: "the composed provider served no such model" };'
)
_JS_REPORT_STREAM_ERROR = (
    "report.arms[arm.armId] = { ...(report.arms[arm.armId] ?? {}), "
    "streamError: String(error && error.message ? error.message : error), };"
)
_JS_REPORT_FINAL = (
    "report.arms[arm.armId] = { ...(report.arms[arm.armId] ?? {}), "
    'serializedModelHasCompatKey: Object.prototype.hasOwnProperty.call(serializedModel, "compat",), '
    "serializedCompat: serializedModel.compat ?? null, "
    "serializedModelReasoning: serializedModel.reasoning, "
    "serializedModelPath, params: capturedParams, "
    "fetchCallsForThisArm: fetchCalls.length - before, };"
)
_JS_REPORT_FETCH_CALLS = "report.fetchCalls = fetchCalls;"
_JS_IMPORTS = (
    'import net from "node:net";',
    'import tls from "node:tls";',
    'import http from "node:http";',
    'import https from "node:https";',
    'import dns from "node:dns";',
    'import { readFileSync, writeFileSync } from "node:fs";',
    'import { pathToFileURL } from "node:url";',
)
_JS_DYNAMIC_IMPORTS = (
    "const { ModelConfig } = await import(pathToFileURL(config.modelConfigModule).href);",
    "const { composeModelProvider } = await import(pathToFileURL(config.providerComposerModule).href);",
    "const { streamSimple } = await import(pathToFileURL(config.openaiCompletionsModule).href);",
)

#: P-03(c): everything that can carry model-derived content, and where it may be used.
#:  * ``model``           -- lookup/binding, the existing not-found check, the ONE
#:                           ``JSON.stringify(model)``, the existing ``streamSimple(model, ...)``;
#:  * ``serializedModelJson`` -- its declaration, the sidecar write, ONE ``JSON.parse``;
#:  * ``serializedModel`` -- the parse binding and the THREE frozen report scalars
#:                           (compat-key presence, compat value, reasoning value), nothing else;
#:  * ``models``/``provider``/``modelConfig`` -- the routes to the model, each used only to reach it;
#:  * ``capturedParams``/``params`` -- the request payload, reported as-is;
#:  * ``report``          -- every statement that writes into the report, exactly.
_JS_MODEL_FAMILY_USES: dict[str, tuple[tuple[str, int], ...]] = {
    "model": (
        (_JS_FIND_MODEL, 1), (_JS_NOT_FOUND, 1), (_JS_STRINGIFY, 1), (_JS_STREAM_CALL, 1),
    ),
    "models": ((_JS_GET_MODELS, 1), (_JS_FIND_MODEL, 1)),
    "provider": ((_JS_PROVIDER, 1), (_JS_GET_MODELS, 1)),
    "modelConfig": ((_JS_LOAD_CONFIG, 1), (_JS_LOAD_ERROR, 1), (_JS_COMPOSE_ARGS, 1)),
    "serializedModelJson": ((_JS_STRINGIFY, 1), (_JS_SIDECAR_WRITE, 1), (_JS_PARSE, 1)),
    "serializedModel": ((_JS_PARSE, 1), (_JS_REPORT_FINAL, 1)),
    "serializedModelPath": ((_JS_SIDECAR_PATH, 1), (_JS_SIDECAR_WRITE, 1), (_JS_REPORT_FINAL, 1)),
    "capturedParams": ((_JS_CAPTURE_DECL, 1), (_JS_ON_PAYLOAD, 1), (_JS_REPORT_FINAL, 1)),
    "params": ((_JS_ON_PAYLOAD, 1), (_JS_REPORT_FINAL, 1)),
    "streamError": ((_JS_REPORT_STREAM_ERROR, 1),),
    "report": (
        (_JS_REPORT_DECL, 1), (_JS_REPORT_LOAD_ERROR, 1), (_JS_REPORT_NO_MODEL, 1),
        (_JS_REPORT_STREAM_ERROR, 1), (_JS_REPORT_FINAL, 1), (_JS_REPORT_FETCH_CALLS, 1),
        (_JS_WRITE_REPORT, 1),
    ),
    "writeFileSync": (('import { readFileSync, writeFileSync } from "node:fs";', 1), (_JS_SIDECAR_WRITE, 1)),
}

#: P-05: the process, the modules, and filesystem READS, closed by exact statement.
#: ``readFileSync`` is frozen to its import plus the ONE config read (``_JS_READ_CONFIG``), so
#: any other read -- a second call, an alias (``const r = readFileSync``), a computed path -- adds a
#: token beyond what those two statements hold. The WRITE side (``writeFileSync``: its import
#: plus the ONE sidecar write) is frozen by the same kind of entry in the model-family table above.
_JS_PROCESS_USES: dict[str, tuple[tuple[str, int], ...]] = {
    "process": ((_JS_READ_CONFIG, 1), (_JS_WRITE_REPORT, 1)),
    "globalThis": (('install(globalThis, "fetch", "globalThis.fetch");', 1),),
    "import": tuple((text, 1) for text in _JS_IMPORTS + _JS_DYNAMIC_IMPORTS),
    "readFileSync": (('import { readFileSync, writeFileSync } from "node:fs";', 1), (_JS_READ_CONFIG, 1)),
}

#: Not used by the harness, and never authorized: reaching the process or an encoder by another name.
_JS_FORBIDDEN_IDENTIFIERS = (
    "global", "eval", "Function", "require", "createRequire", "Reflect", "Proxy",
    "Buffer", "btoa", "atob", "TextEncoder", "TextDecoder", "crypto", "zlib",
)


def _check_harness_source(source: str) -> None:
    """ERR1 P-03(c) and P-05: the token-level source proof over ``cfg1_t3_conformance.mjs``."""
    tokens = _js_tokens(source)
    # P-05: EXACTLY the two authorized process expressions and no other ``process`` token, in any
    # form -- bracket access, aliasing, destructuring, ``Reflect.get``, a string, a module name.
    _require(
        sum(token.count("process") for token in tokens) == 2,
        "P-05",
        "a `process` token exists beyond the two authorized expressions",
    )
    _js_check_uses(tokens, _JS_PROCESS_USES, "P-05")
    for name in _JS_FORBIDDEN_IDENTIFIERS:
        _require(name not in tokens, "P-05", f"the harness uses `{name}`")
    # P-03(c): no model-derived content can reach the report by ANY transport, encoded or not.
    _js_check_uses(tokens, _JS_MODEL_FAMILY_USES, "P-03(c)")


_ARMS = ("Q", "R", "E", "H")
_R37_NAME = "test_t3_r37_the_installed_composers_model_survives_the_real_receive_boundary"
_CONFORMANCE_PATH = Path(__file__).resolve()


# ---------------------------------------------------------------------------
# A fabricated world: an AUTHORITATIVE work directory and a look-alike sibling
# ---------------------------------------------------------------------------


def _plausible_text(arm_id: str, *, reasoning: bool = True, base_url: str = SYNTHETIC_BASE_URL) -> str:
    """A plausible composed-model text, compact like ``JSON.stringify`` output."""
    model: dict[str, object] = {
        "id": CFG1_MODEL_ID, "name": CFG1_MODEL_ID, "api": "openai-completions",
        "provider": PROVIDER_ID, "baseUrl": base_url, "reasoning": reasoning,
        "input": ["text"], "contextWindow": 128000, "maxTokens": 16384,
    }
    compat = ARM_COMPAT[arm_id]
    if compat is not None:
        model["compat"] = dict(compat)
    return json.dumps(model, separators=(",", ":"))


def _arm_report(arm_id: str) -> dict:
    """The report scalars Node would derive for ``arm_id``."""
    compat = ARM_COMPAT[arm_id]
    return {
        "serializedModelHasCompatKey": compat is not None,
        "serializedCompat": None if compat is None else dict(compat),
        "serializedModelReasoning": True,
    }


def _populate(directory: Path) -> None:
    for arm_id in _ARMS:
        models, sidecar = _expected_arm_paths(directory, arm_id)
        models.write_text(
            serialize_config_document(models_document(arm_id=arm_id, base_url=SYNTHETIC_BASE_URL)),
            encoding="utf-8",
        )
        sidecar.write_bytes(_plausible_text(arm_id).encode("utf-8"))


class _World(NamedTuple):
    basetemp: Path
    auth: Path      # the work directory "Python created" -- the provenance anchor
    sibling: Path   # a look-alike: same base, same ``cfg1_t3`` prefix, plausible contents


@pytest.fixture()
def world(tmp_path_factory) -> _World:
    auth = tmp_path_factory.mktemp("cfg1_t3")
    sibling = tmp_path_factory.mktemp("cfg1_t3")
    _populate(auth)
    _populate(sibling)
    return _World(tmp_path_factory.getbasetemp(), auth, sibling)


def _chain(world: _World, claimed, arm_id: str, *, workdir: Path | None = None, lstat=os.lstat) -> str:
    """The exact chain R-37 runs, P-01 -> P-04, over a (possibly fabricated) claim."""
    workdir = world.auth if workdir is None else workdir
    resolved = _check_claimed_path(claimed, basetemp=world.basetemp, lstat=lstat)
    expected = _check_provenance(
        claimed, resolved, arm_id=arm_id, workdir=workdir, basetemp=world.basetemp,
        base_url=SYNTHETIC_BASE_URL, lstat=lstat,
    )
    text = _read_exact_sidecar_text(expected, _arm_report(arm_id))
    _check_synthetic_only(
        text, synthetic_base_url=SYNTHETIC_BASE_URL, provider_id=PROVIDER_ID,
        synthetic_api_key=SYNTHETIC_API_KEY,
    )
    return text


def _sidecar(directory: Path, arm_id: str) -> Path:
    return _expected_arm_paths(directory, arm_id)[1]


def _fake_lstat(target: str, *, mode: int, attributes: int | None = None):
    """``os.lstat`` that reports ``mode`` for ``target`` and the real result elsewhere."""

    def _lstat(path, *args, **kwargs):
        if str(path) != target:
            return os.lstat(path, *args, **kwargs)
        fields = {"st_mode": mode}
        if attributes is not None:
            fields["st_file_attributes"] = attributes
        return types.SimpleNamespace(**fields)

    return _lstat


def _record_resolve(monkeypatch) -> list[str]:
    """Record every ``Path.resolve`` call (then delegate), to prove ORDER."""
    events: list[str] = []
    real = Path.resolve

    def _resolve(self, *args, **kwargs):
        events.append("resolve")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", _resolve)
    return events


# ---------------------------------------------------------------------------
# Row 0 -- the positive control: the fabricated world passes, so every negative
# below fails for the reason it names and not because the world is malformed
# ---------------------------------------------------------------------------


def test_err1_positive_control_the_fabricated_world_passes_every_check(world):
    for arm_id in _ARMS:
        claimed = str(_sidecar(world.auth, arm_id))
        assert _chain(world, claimed, arm_id) == _plausible_text(arm_id)
    assert world.sibling.name.startswith("cfg1_t3") and world.sibling != world.auth
    assert world.sibling.parent == world.auth.parent == world.basetemp


# ---------------------------------------------------------------------------
# P-01 -- claimed-path integrity, in the frozen order
# ---------------------------------------------------------------------------


def test_err1_p01_counterexample_a_a_real_symlink_at_the_expected_location_is_rejected(
    world, monkeypatch
):
    """The claim equals the expected LEXICAL path; the file there is a symlink to
    another plausible regular file. ``resolve()`` would follow it and hide it."""
    other = world.auth / "other_plausible.json"
    other.write_bytes(_plausible_text("Q").encode("utf-8"))
    link = _sidecar(world.auth, "Q")
    link.unlink()  # our own fabricated file, under this test's temp dir
    try:
        os.symlink(str(other), str(link))
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted on this platform (the stubbed variant still runs)")
    assert link.is_symlink() and other.is_file()
    resolves = _record_resolve(monkeypatch)
    with pytest.raises(AssertionError, match=r"P-01\(b\).*symlink"):
        _check_claimed_path(str(link), basetemp=world.basetemp)
    assert resolves == []  # rejected BEFORE any resolution
    with pytest.raises(AssertionError, match=r"P-01\(b\)"):
        _chain(world, str(link), "Q")


def test_err1_p01_counterexample_a_a_reported_symlink_is_rejected_before_resolution(world, monkeypatch):
    """Platform-independent form: the lexical ``lstat`` says symlink."""
    claimed = str(_sidecar(world.auth, "Q"))
    fake = _fake_lstat(claimed, mode=stat.S_IFLNK | 0o777)
    resolves = _record_resolve(monkeypatch)
    with pytest.raises(AssertionError, match=r"P-01\(b\).*symlink"):
        _check_claimed_path(claimed, basetemp=world.basetemp, lstat=fake)
    assert resolves == []


def test_err1_p01_a_reported_reparse_point_is_rejected_before_resolution(world, monkeypatch):
    claimed = str(_sidecar(world.auth, "Q"))
    fake = _fake_lstat(
        claimed, mode=stat.S_IFREG | 0o644, attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
    )
    resolves = _record_resolve(monkeypatch)
    with pytest.raises(AssertionError, match=r"P-01\(b\).*reparse"):
        _check_claimed_path(claimed, basetemp=world.basetemp, lstat=fake)
    assert resolves == []


def test_err1_p01_the_checks_run_in_the_frozen_order(world, monkeypatch):
    """type -> lexical lstat -> regular file -> strict resolve -> containment."""
    claimed = str(_sidecar(world.auth, "Q"))
    events: list[str] = []
    real_lstat = os.lstat

    def _lstat(path, *args, **kwargs):
        events.append("lstat")
        return real_lstat(path, *args, **kwargs)

    real_resolve = Path.resolve

    def _resolve(self, *args, **kwargs):
        events.append("resolve")
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", _resolve)
    _check_claimed_path(claimed, basetemp=world.basetemp, lstat=_lstat)
    assert events[:2] == ["lstat", "resolve"]
    assert events.count("lstat") == 1  # the lexical path is examined once, first

    # a claim failing an EARLIER step never reaches a LATER one
    for bad in (b"C:\\x", "", "rel/path.json", "C:\\x\x00y", 7, None, ["a"]):
        events.clear()
        with pytest.raises(AssertionError, match=r"P-01\(a\)"):
            _check_claimed_path(bad, basetemp=world.basetemp, lstat=_lstat)
        assert events == []

    class _StrSubclass(str):
        pass

    events.clear()
    with pytest.raises(AssertionError, match=r"P-01\(a\).*exact str"):
        _check_claimed_path(_StrSubclass(claimed), basetemp=world.basetemp, lstat=_lstat)
    assert events == []


def test_err1_p01_a_missing_or_non_regular_claim_is_rejected_before_resolution(world, monkeypatch):
    resolves = _record_resolve(monkeypatch)
    with pytest.raises(AssertionError, match=r"P-01\(b\).*lstat"):
        _check_claimed_path(str(world.auth / "no_such.json"), basetemp=world.basetemp)
    with pytest.raises(AssertionError, match=r"P-01\(c\).*regular"):
        _check_claimed_path(str(world.auth), basetemp=world.basetemp)  # a directory
    assert resolves == []


def test_err1_p01_containment_is_judged_on_the_resolved_path(world):
    claimed = str(_sidecar(world.auth, "Q"))
    # outside pytest's base temp
    with pytest.raises(AssertionError, match=r"P-01\(e\).*base temp"):
        _check_claimed_path(claimed, basetemp=world.auth / "elsewhere")
    # inside the CFG1 results directory / the repository (the anchors are injected
    # ONLY so the rows can be exercised without writing into the real ones)
    with pytest.raises(AssertionError, match=r"P-01\(e\).*results"):
        _check_claimed_path(claimed, basetemp=world.basetemp, results_dir=world.auth)
    with pytest.raises(AssertionError, match=r"P-01\(e\).*repository"):
        _check_claimed_path(claimed, basetemp=world.basetemp, repo_root=world.auth)


# ---------------------------------------------------------------------------
# P-02 -- provenance from the PYTHON-OWNED work directory
# ---------------------------------------------------------------------------


def test_err1_p02_counterexample_b_a_sibling_cfg1_t3_directory_is_rejected(world):
    """The claim points into a look-alike directory under the same pytest base,
    whose name also begins ``cfg1_t3`` and which holds a plausible regenerated
    ``models_Q.json`` and a plausible sidecar. P-01 alone cannot tell it apart --
    only the Python-owned work directory can."""
    claimed = str(_sidecar(world.sibling, "Q"))
    resolved = _check_claimed_path(claimed, basetemp=world.basetemp)  # P-01 PASSES
    assert resolved.is_relative_to(world.basetemp)
    with pytest.raises(AssertionError, match=r"P-02 path equality"):
        _check_provenance(
            claimed, resolved, arm_id="Q", workdir=world.auth, basetemp=world.basetemp,
            base_url=SYNTHETIC_BASE_URL,
        )
    with pytest.raises(AssertionError, match=r"P-02 path equality"):
        _chain(world, claimed, "Q")
    # every arm, and a plausible arbitrary sidecar there, is rejected the same way
    for arm_id in _ARMS:
        with pytest.raises(AssertionError, match=r"P-02 path equality"):
            _chain(world, str(_sidecar(world.sibling, arm_id)), arm_id)


def test_err1_p02_a_claim_for_the_wrong_arm_is_rejected(world):
    for claimed_arm, checked_arm in (("Q", "R"), ("R", "Q"), ("E", "H"), ("H", "E")):
        claimed = str(_sidecar(world.auth, claimed_arm))
        with pytest.raises(AssertionError, match=r"P-02 path equality"):
            _chain(world, claimed, checked_arm)


def test_err1_p02_the_expected_paths_never_come_from_the_claimed_path(world):
    """Same-named files elsewhere never help a claim: authority is workdir + arm id only."""
    models, sidecar = _expected_arm_paths(world.auth, "Q")
    assert models == world.auth / "models_Q.json"
    assert sidecar == world.auth / "models_Q.json.composed-model.json"
    # a claim with a non-normalized spelling of the RIGHT file is not the expected string
    variants = (
        str(sidecar).replace("\\", "/"),
        str(world.auth / ".." / world.auth.name / sidecar.name),
        str(sidecar).upper(),
    )
    for claimed in variants:
        if claimed == str(sidecar):
            continue
        with pytest.raises(AssertionError):
            _chain(world, claimed, "Q")


def test_err1_p02_a_tampered_models_json_or_workdir_is_rejected(world, tmp_path_factory):
    claimed = str(_sidecar(world.auth, "Q"))
    models = _expected_arm_paths(world.auth, "Q")[0]
    original = models.read_bytes()
    models.write_bytes(original + b" ")
    try:
        with pytest.raises(AssertionError, match=r"P-02 models\.json"):
            _chain(world, claimed, "Q")
    finally:
        models.write_bytes(original)
    models.unlink()
    with pytest.raises(AssertionError, match=r"P-02 models\.json.*missing"):
        _chain(world, claimed, "Q")
    # the authoritative directory must itself be a real directory directly under the base
    nested = world.auth / "nested"
    nested.mkdir()
    _populate(nested)
    with pytest.raises(AssertionError, match=r"P-02\(ii\)"):
        _chain(world, str(_sidecar(nested, "Q")), "Q", workdir=nested)
    with pytest.raises(AssertionError, match=r"P-02\(ii\)"):
        _chain(world, claimed, "Q", workdir=world.auth / "does_not_exist")


def test_err1_p02_a_linked_authoritative_work_directory_is_rejected(world):
    claimed = str(_sidecar(world.auth, "Q"))
    for mode, attributes in ((stat.S_IFLNK | 0o777, None), (stat.S_IFDIR | 0o755, stat.FILE_ATTRIBUTE_REPARSE_POINT)):
        fake = _fake_lstat(str(world.auth), mode=mode, attributes=attributes)
        with pytest.raises(AssertionError, match=r"P-02\(ii\)"):
            _chain(world, claimed, "Q", lstat=fake)


# ---------------------------------------------------------------------------
# P-03 / P-04 -- exact text, and text that disagrees with the report
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(_plausible_text("Q").encode() + b"\n", id="trailing-LF"),
        pytest.param(_plausible_text("Q").encode() + b"\r\n", id="trailing-CRLF"),
        pytest.param(b"\xef\xbb\xbf" + _plausible_text("Q").encode(), id="BOM"),
        pytest.param(_plausible_text("Q").replace('"id":', '"id":\n', 1).encode(), id="interior-LF"),
        pytest.param(_plausible_text("Q").replace('"id":"', '"id":"__ID__', 1).encode(), id="id-placeholder"),
        pytest.param(b" " + _plausible_text("Q").encode(), id="leading-space"),
        pytest.param(b"", id="empty"),
        pytest.param(b"\xff\xfe" + _plausible_text("Q").encode(), id="not-utf8"),
        pytest.param(b"not json", id="not-json"),
        pytest.param(b"[1,2]", id="not-an-object"),
    ],
)
def test_err1_p03_a_sidecar_that_is_not_the_exact_clean_text_is_rejected(world, raw):
    _sidecar(world.auth, "Q").write_bytes(raw)
    with pytest.raises(AssertionError, match=r"P-03"):
        _chain(world, str(_sidecar(world.auth, "Q")), "Q")


def test_err1_p03_a_file_that_disagrees_with_the_report_scalars_is_rejected(world):
    sidecar = _sidecar(world.auth, "Q")
    claimed = str(sidecar)
    sidecar.write_bytes(_plausible_text("Q", reasoning=False).encode())  # report says True
    with pytest.raises(AssertionError, match=r"P-03\(b\).*reasoning"):
        _chain(world, claimed, "Q")
    sidecar.write_bytes(_plausible_text("R").encode())  # compat present; report says absent
    with pytest.raises(AssertionError, match=r"P-03\(b\).*compat"):
        _chain(world, claimed, "Q")
    sidecar.write_bytes(_plausible_text("Q").encode())
    assert _chain(world, claimed, "Q") == _plausible_text("Q")  # restored


def test_err1_p06_a_crossed_qreh_sidecar_is_rejected(world):
    """Another arm's genuine text placed at this arm's expected location."""
    for stored, arm_id in (("Q", "R"), ("R", "Q"), ("R", "E"), ("E", "H"), ("H", "R")):
        sidecar = _sidecar(world.auth, arm_id)
        sidecar.write_bytes(_plausible_text(stored).encode())
        with pytest.raises(AssertionError, match=r"P-03\(b\)"):
            _chain(world, str(sidecar), arm_id)
        sidecar.write_bytes(_plausible_text(arm_id).encode())
    # pairwise distinctness is required across arms
    paths = {arm: str(_sidecar(world.auth, arm)) for arm in _ARMS}
    texts = {arm: _plausible_text(arm) for arm in _ARMS}
    _check_arm_isolation(paths, texts)
    with pytest.raises(AssertionError, match=r"P-06.*texts"):
        _check_arm_isolation(paths, {**texts, "R": texts["Q"]})
    with pytest.raises(AssertionError, match=r"P-06.*paths"):
        _check_arm_isolation({**paths, "R": paths["Q"]}, texts)


def test_err1_p04_non_synthetic_content_is_rejected(world):
    def check(text):
        _check_synthetic_only(
            text, synthetic_base_url=SYNTHETIC_BASE_URL, provider_id=PROVIDER_ID,
            synthetic_api_key=SYNTHETIC_API_KEY,
        )

    check(_plausible_text("Q"))  # the frozen provider id alone is fine
    for bad in (
        _plausible_text("Q", base_url="https://models.example.com/v1"),
        _plausible_text("Q").replace(SYNTHETIC_BASE_URL, SYNTHETIC_BASE_URL + "/x"),
        _plausible_text("Q").replace('"input"', '"token":"PI_QUALIFICATION_B300_ROUTE_KEY_VALUE","input"'),
        _plausible_text("Q").replace('"input"', '"k":"AIDO_LITELLM","input"'),
        _plausible_text("Q").replace('"input"', f'"k":"{SYNTHETIC_API_KEY}","input"'),
        _plausible_text("Q").replace('"input"', '"h":"host-b300-gpu","input"'),
        json.dumps({"provider": PROVIDER_ID, "note": "no url here"}),
    ):
        with pytest.raises(AssertionError, match=r"P-04"):
            check(bad)


def test_err1_p02_the_real_r37_test_hands_the_verifiers_python_owned_anchors_only():
    _check_r37_provenance_call_sites(_r37_source())


def test_err1_p02_a_r37_call_site_that_takes_its_anchor_from_the_report_is_caught():
    real = _r37_source()
    for old, new in (
        ("workdir=_t3_run.workdir,", "workdir=Path(claimed).parent,"),
        ("workdir=_t3_run.workdir,", "workdir=resolved.parent,"),
        ("workdir=_t3_run.workdir,", "workdir=expected_dir,"),
        ("basetemp = tmp_path_factory.getbasetemp()", "basetemp = resolved.parent.parent"),
        ("basetemp = tmp_path_factory.getbasetemp()", "basetemp = tmp_path"),
    ):
        assert real.count(old) == 1, old
        with pytest.raises(AssertionError, match=r"P-0[12]"):
            _check_r37_provenance_call_sites(real.replace(old, new, 1))
    # dropping the provenance call altogether is caught too
    with pytest.raises(AssertionError, match=r"P-02"):
        _check_r37_provenance_call_sites(
            real.replace("expected = _check_provenance(", "expected = check_something_else(", 1)
        )


def test_err1_p05_the_real_r37_test_reads_no_environment_and_no_file_itself():
    _check_r37_reads_no_environment(_r37_source())


def test_err1_p05_an_r37_body_that_reads_the_environment_or_a_file_is_caught():
    real = _r37_source()
    anchor = "    basetemp = tmp_path_factory.getbasetemp()\n"
    assert real.count(anchor) == 1
    for injected in (
        "    key = os.environ.get('PI_QUALIFICATION_B300_ROUTE_KEY')\n",
        "    key = __import__('os').getenv('AIDO_LITELLM_API_KEY')\n",
        "    handle = open('credentials.txt')\n",
        "    leaked = tmp_path.read_text()\n",
        "    leaked = tmp_path.read_bytes()\n",
    ):
        with pytest.raises(AssertionError, match=r"P-05"):
            _check_r37_reads_no_environment(real.replace(anchor, anchor + injected, 1))


# ---------------------------------------------------------------------------
# P-07 -- the frame is verbatim text; a parse-and-rebuild is caught
# ---------------------------------------------------------------------------


def _r37_source() -> str:
    text = _CONFORMANCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == _R37_NAME)
    return ast.get_source_segment(text, node)


def test_err1_p07_the_real_r37_test_builds_its_frame_by_plain_concatenation():
    _check_frame_construction_source(_r37_source())


_GOOD_R37_SKELETON = '''
def r37(x):
    model_text = _read_exact_sidecar_text(expected, arm_report)
    frame = _R37_FRAME_PREFIX + model_text + _R37_FRAME_SUFFIX
'''


@pytest.mark.parametrize(
    "mutation, expected_message",
    [
        pytest.param(
            "    frame = _R37_FRAME_PREFIX + json.dumps(json.loads(model_text)) + _R37_FRAME_SUFFIX\n",
            "json module", id="rebuilt-from-parsed-json"),
        pytest.param(
            "    frame = _R37_FRAME_PREFIX + _json.dumps(_json.loads(model_text)) + _R37_FRAME_SUFFIX\n",
            "json module", id="rebuilt-via-alias"),
        pytest.param(
            "    frame = f'{_R37_FRAME_PREFIX}{model_text}{_R37_FRAME_SUFFIX}'\n",
            "JoinedStr", id="f-string"),
        pytest.param(
            "    frame = _R37_FRAME_PREFIX + model_text.replace('a', 'b') + _R37_FRAME_SUFFIX\n",
            "Call", id="edited-text"),
        pytest.param(
            "    frame = _R37_FRAME_PREFIX + model_text[:-1] + _R37_FRAME_SUFFIX\n",
            "Subscript", id="sliced-text"),
        pytest.param(
            "    frame = _R37_FRAME_PREFIX + rebuilt + _R37_FRAME_SUFFIX\n",
            "frame operands", id="another-name"),
        pytest.param(
            "    frame = _R37_FRAME_SUFFIX + model_text + _R37_FRAME_PREFIX\n",
            "frame operands", id="wrong-order"),
        pytest.param(
            "    frame = _R37_FRAME_PREFIX + model_text + '}' + _R37_FRAME_SUFFIX\n",
            "Constant", id="extra-literal"),
    ],
)
def test_err1_p07_an_attempt_to_rebuild_the_frame_from_parsed_json_is_caught(mutation, expected_message):
    source = _GOOD_R37_SKELETON.replace(
        "    frame = _R37_FRAME_PREFIX + model_text + _R37_FRAME_SUFFIX\n", mutation
    )
    assert source != _GOOD_R37_SKELETON
    _check_frame_construction_source(_GOOD_R37_SKELETON)  # the skeleton itself is fine
    with pytest.raises(AssertionError, match=r"P-07"):
        _check_frame_construction_source(source)


def test_err1_p07_the_text_must_be_the_direct_result_of_the_exact_reader():
    for source in (
        # model_text bound from something else
        '''
def r37():
    model_text = path.read_text()
    frame = _R37_FRAME_PREFIX + model_text + _R37_FRAME_SUFFIX
''',
        # model_text derived from a parsed object
        '''
def r37():
    model_text = _read_exact_sidecar_text(a, b)
    model_text = model_text.strip()
    frame = _R37_FRAME_PREFIX + model_text + _R37_FRAME_SUFFIX
''',
        # frame assigned twice (a second assignment could rebuild it)
        '''
def r37():
    model_text = _read_exact_sidecar_text(a, b)
    frame = _R37_FRAME_PREFIX + model_text + _R37_FRAME_SUFFIX
    frame = _R37_FRAME_PREFIX + model_text + _R37_FRAME_SUFFIX
''',
    ):
        with pytest.raises(AssertionError, match=r"P-07"):
            _check_frame_construction_source(source)


def test_err1_p07_a_frame_that_differs_from_prefix_text_suffix_is_caught_at_runtime():
    prefix, suffix = "PRE:__ID__:", ":SUF"
    text = _plausible_text("R")
    _assert_verbatim_frame(prefix + text + suffix, text, prefix, suffix)
    rebuilt = json.dumps(json.loads(text))  # default separators: re-spaced text
    assert rebuilt != text
    for frame in (
        prefix + rebuilt + suffix,           # parse-and-rebuild
        prefix + text + " " + suffix,        # extra character
        prefix + text[:-1] + suffix,         # truncated
        prefix + text + suffix + "\n",       # a stray LF
        "PRE:__ID__:__ID__:" + text + suffix,  # a second placeholder
    ):
        with pytest.raises(AssertionError, match=r"P-07"):
            _assert_verbatim_frame(frame, text, prefix, suffix)


# ---------------------------------------------------------------------------
# P-03(c) / P-05 -- the harness source
# ---------------------------------------------------------------------------


def _harness_source() -> str:
    return _HARNESS.read_text(encoding="utf-8")


def _mutate_harness(old: str, new: str) -> str:
    source = _harness_source()
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


_HARNESS_CONTEXT = "const context = {"
_HARNESS_STREAM_ERROR = "      streamError: String(error && error.message ? error.message : error),\n"
_HARNESS_PARAMS_FIELD = "    params: capturedParams,\n"
_HARNESS_FETCH_FIELD = "    fetchCallsForThisArm: fetchCalls.length - before,\n"
_HARNESS_COMPAT_FIELD = "    serializedCompat: serializedModel.compat ?? null,\n"
_HARNESS_REASONING_FIELD = "    serializedModelReasoning: serializedModel.reasoning,\n"


def _inserted_before_context(statement: str) -> tuple[str, str]:
    return _HARNESS_CONTEXT, statement + _HARNESS_CONTEXT


def test_err1_p05_the_real_harness_source_passes_every_source_check():
    _check_harness_source(_harness_source())
    tokens = _js_tokens(_harness_source())
    # EXACTLY the two authorized process expressions, and no other `process` token in any form
    assert sum(token.count("process") for token in tokens) == 2
    assert tokens.count("process") == 2
    assert _js_occurrences(tokens, _js_tokens(_JS_READ_CONFIG)) == 1
    assert _js_occurrences(tokens, _js_tokens(_JS_WRITE_REPORT)) == 1


def test_err1_p05_the_token_lexer_drops_comments_keeps_strings_opaque_and_refuses_regex_literals():
    assert _js_tokens("a /* b */ // c\n d") == ["a", "d"]
    assert _js_tokens('x = "process";') == ["x", "=", '"process"', ";"]
    assert _js_tokens("x = 'a\\'b';") == ["x", "=", "'a\\'b'", ";"]
    assert _js_tokens("`a${process}b`") == ["`", _JS_TEMPLATE_CHUNK + "a", "${", "process", "}", _JS_TEMPLATE_CHUNK + "b", "`"]
    assert _js_tokens("`${ {a: 1}.a }`") == ["`", "${", "{", "a", ":", "1", "}", ".", "a", "}", "`"]
    with pytest.raises(AssertionError, match=r"P-05.*regex literal or a division"):
        _js_tokens("const r = /x/;")
    for broken in ('const s = "open;', "const t = `open", "/* never closed"):
        with pytest.raises(AssertionError, match=r"P-05.*unterminated"):
            _js_tokens(broken)


def test_err1_p05_comments_are_excluded_and_a_harmless_local_is_accepted():
    """Positive controls: the proof is about USES, so a comment naming an API or an unrelated
    local changes nothing -- which is also what makes the negatives below meaningful."""
    for statement in (
        "// process.env, Buffer.from(JSON.stringify(serializedModel)), model\n",
        '/* process["env"] serializedModel Reflect.get(process, "env") */\n',
        "const harmless = 1;\n",
    ):
        old, new = _inserted_before_context(statement)
        _check_harness_source(_mutate_harness(old, new))


@pytest.mark.parametrize(
    "old, new",
    [
        pytest.param("JSON.stringify(model);", "JSON.stringify(model, null, 2);", id="indented"),
        pytest.param("JSON.stringify(model);", "JSON.stringify(model, (k, v) => v);", id="replacer"),
        pytest.param(
            'writeFileSync(serializedModelPath, serializedModelJson, "utf-8");',
            'writeFileSync(serializedModelPath, serializedModelJson.trim(), "utf-8");',
            id="post-processed-write"),
        pytest.param(
            'writeFileSync(serializedModelPath, serializedModelJson, "utf-8");',
            'writeFileSync(serializedModelPath, serializedModelJson, "utf-8");\n'
            '  writeFileSync("x.json", serializedModelJson, "utf-8");',
            id="second-write"),
        pytest.param(
            "const serializedModel = JSON.parse(serializedModelJson);",
            "const serializedModel = JSON.parse(JSON.stringify(model));",
            id="parse-of-another-stringify"),
        pytest.param(
            "    serializedModelPath,\n",
            "    serializedModelPath,\n    serializedModelText: serializedModelJson,\n",
            id="text-in-the-report"),
        pytest.param(
            "const config = JSON.parse(",
            "const leaked = process.env.PI_QUALIFICATION_B300_ROUTE_KEY;\nconst config = JSON.parse(",
            id="environment-read"),
        pytest.param(
            "const serializedModelPath = `${arm.modelsJsonPath}.composed-model.json`;",
            "const serializedModelPath = `/tmp/elsewhere.json`;",
            id="path-elsewhere"),
    ],
)
def test_err1_p05_a_harness_source_that_departs_from_the_exact_text_is_rejected(old, new):
    with pytest.raises(AssertionError, match=r"P-0[35]|P-10"):
        _check_harness_source(_mutate_harness(old, new))


# -- item 2: encoded / transformed / model-derived transport into an EXISTING report field ---------

#: Each puts model-derived content, plain or encoded, into a report field that already exists.
#: An encoded form would slip past the frozen literal-``b300`` assertion; only this proof stops it.
_ENCODED_TRANSPORT_MUTATIONS = {
    "base64-of-stringified-parsed-model-into-streamError": (
        _HARNESS_STREAM_ERROR,
        '      streamError: Buffer.from(JSON.stringify(serializedModel)).toString("base64"),\n'),
    "stringified-parsed-model-into-an-existing-field": (
        _HARNESS_PARAMS_FIELD, "    params: JSON.stringify(serializedModel),\n"),
    "hex-of-a-parsed-model-field": (
        _HARNESS_FETCH_FIELD,
        '    fetchCallsForThisArm: Buffer.from(String(serializedModel.baseUrl)).toString("hex"),\n'),
    "base64-of-a-parsed-model-field-via-btoa": (
        _HARNESS_COMPAT_FIELD, "    serializedCompat: btoa(serializedModel.id),\n"),
    "wrapped-reasoning-scalar": (
        _HARNESS_REASONING_FIELD, "    serializedModelReasoning: String(serializedModel.reasoning),\n"),
    "compat-scalar-reading-another-field": (
        _HARNESS_COMPAT_FIELD, "    serializedCompat: serializedModel.baseUrl ?? null,\n"),
    "stringified-composed-model-into-streamError": (
        _HARNESS_STREAM_ERROR, "      streamError: JSON.stringify(model),\n"),
    "hex-of-the-composed-model-into-streamError": (
        _HARNESS_STREAM_ERROR,
        '      streamError: Buffer.from(JSON.stringify(model)).toString("hex"),\n'),
    "a-composed-model-field-into-streamError": (
        _HARNESS_STREAM_ERROR, "      streamError: String(model.id),\n"),
    "the-models-array-into-an-existing-field": (
        _HARNESS_PARAMS_FIELD, "    params: JSON.stringify(models),\n"),
    "the-provider-into-an-existing-field": (
        _HARNESS_PARAMS_FIELD, "    params: String(provider),\n"),
    "the-model-config-into-an-existing-field": (
        _HARNESS_PARAMS_FIELD, "    params: JSON.stringify(modelConfig),\n"),
    "the-exact-text-into-streamError": (
        _HARNESS_STREAM_ERROR, "      streamError: serializedModelJson,\n"),
    "an-alias-of-the-composed-model": _inserted_before_context("const alias = model;\n"),
    "an-alias-of-the-parsed-model": _inserted_before_context("const alias = serializedModel;\n"),
    "a-destructure-of-the-parsed-model": _inserted_before_context(
        "const { reasoning, ...rest } = serializedModel;\n"),
    "a-spread-of-the-parsed-model-into-the-report": (
        "    serializedModelPath,\n", "    serializedModelPath,\n    ...serializedModel,\n"),
    "an-assignment-onto-an-existing-arm-entry": (
        "report.fetchCalls = fetchCalls;",
        'report.arms.Q.streamError = "x";\nreport.fetchCalls = fetchCalls;'),
    "a-new-report-member": (
        "report.fetchCalls = fetchCalls;",
        'report.debug = "x";\nreport.fetchCalls = fetchCalls;'),
    "the-composed-model-read-a-second-time": _inserted_before_context("console.log(model);\n"),
}


@pytest.mark.parametrize("label", sorted(_ENCODED_TRANSPORT_MUTATIONS))
def test_err1_p03c_a_model_derived_transport_into_an_existing_report_field_is_rejected(label):
    old, new = _ENCODED_TRANSPORT_MUTATIONS[label]
    mutated = _mutate_harness(old, new)
    with pytest.raises(AssertionError, match=r"P-0[35]"):
        _check_harness_source(mutated)
    # ...and it is the USAGE proof, not merely the forbidden-identifier backstop, that catches it:
    with pytest.raises(AssertionError, match=r"P-03\(c\)"):
        _js_check_uses(_js_tokens(mutated), _JS_MODEL_FAMILY_USES, "P-03(c)")


def test_err1_p03c_the_parsed_model_is_used_only_for_the_three_frozen_scalars():
    tokens = _js_tokens(_harness_source())
    uses = dict(_JS_MODEL_FAMILY_USES["serializedModel"])
    assert set(uses) == {_JS_PARSE, _JS_REPORT_FINAL}
    # the one report statement that may read it holds EXACTLY compat presence, compat value, reasoning
    final = _js_tokens(_JS_REPORT_FINAL)
    assert final.count("serializedModel") == 3
    for scalar in (
        'serializedModelHasCompatKey: Object.prototype.hasOwnProperty.call(serializedModel, "compat",)',
        "serializedCompat: serializedModel.compat ?? null",
        "serializedModelReasoning: serializedModel.reasoning",
    ):
        assert _js_occurrences(final, _js_tokens(scalar)) == 1
    assert tokens.count("serializedModel") == 4  # the binding + those three, nothing else
    # the composed model: lookup, not-found check, the ONE stringify, the ONE streamSimple call
    assert dict(_JS_MODEL_FAMILY_USES["model"]) == {
        _JS_FIND_MODEL: 1, _JS_NOT_FOUND: 1, _JS_STRINGIFY: 1, _JS_STREAM_CALL: 1,
    }
    assert tokens.count("model") == 4
    # the exact text: declaration, sidecar write, ONE JSON.parse
    assert dict(_JS_MODEL_FAMILY_USES["serializedModelJson"]) == {
        _JS_STRINGIFY: 1, _JS_SIDECAR_WRITE: 1, _JS_PARSE: 1,
    }
    assert tokens.count("serializedModelJson") == 3


def test_err1_p03c_encoded_transport_evades_the_literal_b300_assertion_so_only_the_source_proof_stops_it():
    """The premise of the source proof, demonstrated rather than assumed (ERR1 Sec. 2)."""
    import base64
    import codecs

    text = _plausible_text("Q")
    assert "b300" in text
    encodings = {
        "base64": base64.b64encode(text.encode()).decode(),
        "urlsafe-base64": base64.urlsafe_b64encode(text.encode()).decode(),
        "hex": text.encode().hex(),
        "unicode-escaped": text.replace("b", "\\u0062"),
        "rot13": codecs.encode(text, "rot13"),
        "reversed": text[::-1],
    }
    for name, encoded in encodings.items():
        report = {"arms": {"Q": {"streamError": encoded}}, "fetchCalls": [SYNTHETIC_BASE_URL]}
        serialized = json.dumps(report)
        # the FROZEN assertion's own loop, applied to a report carrying the encoded model:
        for forbidden in ("PI_QUALIFICATION_B300_ROUTE_KEY_VALUE", "b300", "AIDO_LITELLM"):
            assert forbidden not in serialized, (name, forbidden)
        # a report-level check cannot see it either -- which is why the SOURCE is what is proved
        _check_report_carries_path_only(
            {"arms": {arm: {**_arm_report(arm), "serializedModelPath": "x", "streamError": encoded}
                      for arm in _ARMS}},
            text, PROVIDER_ID,
        )
    for label in _ENCODED_TRANSPORT_MUTATIONS:
        old, new = _ENCODED_TRANSPORT_MUTATIONS[label]
        with pytest.raises(AssertionError, match=r"P-0[35]"):
            _check_harness_source(_mutate_harness(old, new))


# -- item 3: every way to reach the process, not only ``process.<name>`` --------------------------


@pytest.mark.parametrize(
    "injected",
    [
        pytest.param('const leaked = process["env"];\n', id="bracket-access"),
        pytest.param("const p = process;\nconst leaked = p.env;\n", id="alias-then-dot"),
        pytest.param("const { env } = process;\n", id="destructure"),
        pytest.param('const leaked = Reflect.get(process, "env");\n', id="reflect-get"),
        pytest.param("const leaked = process.env.PI_QUALIFICATION_B300_ROUTE_KEY;\n", id="dot-env"),
        pytest.param("const leaked = `${process.env.X}`;\n", id="inside-a-template-expression"),
        pytest.param('const leaked = globalThis["process"].env;\n', id="globalthis-bracket"),
        pytest.param("const leaked = globalThis.process.env;\n", id="globalthis-dot"),
        pytest.param("const g = globalThis;\n", id="a-second-globalthis"),
        pytest.param('const proc = await import("node:process");\n', id="dynamic-import-of-the-module"),
        pytest.param('const name = "process";\n', id="a-string-naming-it"),
        pytest.param('const f = Function("return process")();\n', id="function-constructor"),
        pytest.param('const r = require("node:process");\n', id="require"),
        pytest.param('const e = eval("process.env");\n', id="eval"),
    ],
)
def test_err1_p05_every_unauthorized_process_access_form_is_rejected(injected):
    old, new = _inserted_before_context(injected)
    with pytest.raises(AssertionError, match=r"P-05"):
        _check_harness_source(_mutate_harness(old, new))


def test_err1_p05_an_unauthorized_import_or_reach_for_an_encoder_is_rejected():
    for old, new in (
        ('import dns from "node:dns";', 'import dns from "node:dns";\nimport zlib from "node:zlib";'),
        ('import dns from "node:dns";', 'import dns from "node:dns";\nimport { env } from "node:process";'),
        _inserted_before_context('const c = crypto.createHash("sha256");\n'),
        _inserted_before_context('const b = Buffer.from("x");\n'),
        _inserted_before_context('const t = new TextEncoder();\n'),
        _inserted_before_context('const p = new Proxy({}, {});\n'),
    ):
        with pytest.raises(AssertionError, match=r"P-05"):
            _check_harness_source(_mutate_harness(old, new))


# -- filesystem I/O is closed: exactly one config READ and exactly one sidecar WRITE ---------------


def test_err1_p05_the_real_harness_has_exactly_one_authorized_read_and_one_authorized_write():
    tokens = _js_tokens(_harness_source())
    fs_import = _js_tokens('import { readFileSync, writeFileSync } from "node:fs";')
    # READ: the import, and exactly one invocation -- the existing config read
    assert tokens.count("readFileSync") == 2
    assert _js_occurrences(tokens, fs_import) == 1
    assert _js_occurrences(tokens, _js_tokens(_JS_READ_CONFIG)) == 1
    assert _js_occurrences(tokens, ["readFileSync", "("]) == 1
    assert dict(_JS_PROCESS_USES["readFileSync"]) == {
        'import { readFileSync, writeFileSync } from "node:fs";': 1, _JS_READ_CONFIG: 1,
    }
    # WRITE: the import, and exactly one invocation -- the sidecar write
    assert tokens.count("writeFileSync") == 2
    assert _js_occurrences(tokens, _js_tokens(_JS_SIDECAR_WRITE)) == 1
    assert _js_occurrences(tokens, ["writeFileSync", "("]) == 1
    assert dict(_JS_MODEL_FAMILY_USES["writeFileSync"]) == {
        'import { readFileSync, writeFileSync } from "node:fs";': 1, _JS_SIDECAR_WRITE: 1,
    }


@pytest.mark.parametrize(
    "injected",
    [
        pytest.param('const leaked = readFileSync("C:/secret.txt", "utf-8");\n', id="a-literal-secret-path"),
        pytest.param(
            'const r = readFileSync;\nconst leaked = r("C:/secret.txt", "utf-8");\n', id="an-alias-then-a-call"),
        pytest.param(
            'const leaked = readFileSync(config.modelConfigModule, "utf-8");\n', id="a-config-supplied-path"),
        pytest.param(
            'const second = JSON.parse(readFileSync(arm.modelsJsonPath, "utf-8"));\n',
            id="a-second-ordinary-config-file-read"),
        pytest.param('const leaked = readFileSync(config.apiKey);\n', id="no-encoding-argument"),
        pytest.param('const { readFileSync: rf } = await import("node:fs");\n', id="a-second-import-of-the-module"),
    ],
)
def test_err1_p05_an_unauthorized_filesystem_read_is_rejected(injected):
    old, new = _inserted_before_context(injected)
    mutated = _mutate_harness(old, new)
    with pytest.raises(AssertionError, match=r"P-05"):
        _check_harness_source(mutated)


@pytest.mark.parametrize(
    "injected",
    [
        pytest.param('const leaked = readFileSync("C:/secret.txt", "utf-8");\n', id="a-literal-secret-path"),
        pytest.param(
            'const r = readFileSync;\nconst leaked = r("C:/secret.txt", "utf-8");\n', id="an-alias-then-a-call"),
        pytest.param(
            'const leaked = readFileSync(config.modelConfigModule, "utf-8");\n', id="a-config-supplied-path"),
        pytest.param(
            'const second = JSON.parse(readFileSync(arm.modelsJsonPath, "utf-8"));\n',
            id="a-second-ordinary-config-file-read"),
    ],
)
def test_err1_p05_the_read_entry_itself_is_what_catches_an_unauthorized_read(injected):
    """These reads touch no ``process``, import, encoder or model-family token, so before the
    ``readFileSync`` entry existed NOTHING in the proof would have rejected them."""
    old, new = _inserted_before_context(injected)
    tokens = _js_tokens(_mutate_harness(old, new))
    other_tables = {name: uses for name, uses in _JS_PROCESS_USES.items() if name != "readFileSync"}
    _js_check_uses(tokens, other_tables, "P-05")  # every OTHER P-05 entry is satisfied...
    _js_check_uses(tokens, _JS_MODEL_FAMILY_USES, "P-03(c)")  # ...and so is the model-family proof
    with pytest.raises(AssertionError, match=r"P-05.*readFileSync"):
        _js_check_uses(tokens, {"readFileSync": _JS_PROCESS_USES["readFileSync"]}, "P-05")


def test_err1_p05_a_second_sidecar_write_is_still_rejected_beside_the_read_entry():
    old, new = _inserted_before_context('writeFileSync("C:/x.txt", "y", "utf-8");\n')
    with pytest.raises(AssertionError, match=r"P-0[35]"):
        _check_harness_source(_mutate_harness(old, new))


# ---------------------------------------------------------------------------
# P-08 -- the existing broad no-b300 assertion is unchanged
# ---------------------------------------------------------------------------


def test_err1_p08_the_frozen_no_b300_test_is_byte_identical_to_its_3a59157_text():
    digest = _function_source_digest(
        _CONFORMANCE_PATH.read_text(encoding="utf-8"), _FROZEN_NO_B300_TEST_NAME
    )
    assert digest == _FROZEN_NO_B300_TEST_SHA256
    # and the pin is sensitive: a weakened copy would not match
    weakened = _CONFORMANCE_PATH.read_text(encoding="utf-8").replace(
        '("PI_QUALIFICATION_B300_ROUTE_KEY_VALUE", "b300", "AIDO_LITELLM")',
        '("PI_QUALIFICATION_B300_ROUTE_KEY_VALUE", "AIDO_LITELLM")',
    )
    assert weakened != _CONFORMANCE_PATH.read_text(encoding="utf-8")
    assert _function_source_digest(weakened, _FROZEN_NO_B300_TEST_NAME) != digest


def _synthetic_report(world: _World) -> dict:
    """A report shaped like Node's, whose arm entries carry a PATH and scalars only."""
    return {
        "arms": {
            arm_id: {
                **_arm_report(arm_id),
                "serializedModelPath": str(_sidecar(world.auth, arm_id)),
                "params": {"model": CFG1_MODEL_ID},
                "fetchCallsForThisArm": 1,
            }
            for arm_id in _ARMS
        },
        "fetchCalls": [SYNTHETIC_BASE_URL],
    }


def test_err1_p08_a_report_that_embeds_the_model_or_gains_a_member_is_caught(world):
    """(The REAL report is checked in ``test_cfg1_pi_conformance.py``, whose module-scoped
    fixture owns it: ``test_t3_err1_p08_the_report_carries_a_path_only``.)"""
    sentinel = "\x00never-present\x00"
    report = _synthetic_report(world)
    _check_report_carries_path_only(report, sentinel, PROVIDER_ID)  # the control passes
    text = _plausible_text("Q")

    tampered = json.loads(json.dumps(report))
    tampered["arms"]["Q"]["serializedModel"] = {"id": "x"}
    with pytest.raises(AssertionError, match=r"P-10.*gained a member"):
        _check_report_carries_path_only(tampered, sentinel, PROVIDER_ID)

    tampered = json.loads(json.dumps(report))
    tampered["arms"]["R"]["params"] = {"note": PROVIDER_ID}
    with pytest.raises(AssertionError, match=r"P-08.*provider id"):
        _check_report_carries_path_only(tampered, sentinel, PROVIDER_ID)

    # the model embedded three different ways -- each caught by its OWN check, before the
    # provider-id backstop, which alone would only happen to catch the real model
    scrubbed = _plausible_text("Q").replace(PROVIDER_ID, "provider-x")  # no provider id at all
    for label, member, message in (
        ("as a string", lambda: scrubbed, r"P-08.*model text"),
        ("as a nested string", lambda: {"note": "prefix " + scrubbed + " suffix"}, r"P-08.*model text"),
        ("as a structural object", lambda: json.loads(scrubbed), r"P-08.*(model text|model object)"),
        ("as a nested object", lambda: {"deep": [json.loads(scrubbed)]}, r"P-08.*(model text|model object)"),
    ):
        tampered = json.loads(json.dumps(report))
        tampered["arms"]["Q"]["streamError"] = member()
        with pytest.raises(AssertionError, match=message):
            _check_report_carries_path_only(tampered, scrubbed, PROVIDER_ID)

    # a re-ordered copy of the object is invisible to any substring test: only the structural walk catches it
    reordered = dict(reversed(list(json.loads(scrubbed).items())))
    assert json.dumps(reordered, separators=(",", ":")) != scrubbed
    tampered = json.loads(json.dumps(report))
    tampered["arms"]["Q"]["streamError"] = reordered
    with pytest.raises(AssertionError, match=r"P-08.*model object"):
        _check_report_carries_path_only(tampered, scrubbed, PROVIDER_ID)

    # ...and the real text (which carries the provider id) is caught too
    tampered = json.loads(json.dumps(report))
    tampered["arms"]["Q"]["streamError"] = text
    with pytest.raises(AssertionError, match=r"P-08"):
        _check_report_carries_path_only(tampered, text, PROVIDER_ID)

    tampered = json.loads(json.dumps(report))
    tampered["arms"]["E"]["serializedModelPath"] = {"path": "x"}
    with pytest.raises(AssertionError, match=r"P-08.*not a str"):
        _check_report_carries_path_only(tampered, sentinel, PROVIDER_ID)


# ---------------------------------------------------------------------------
# P-09 -- no durable evidence
# ---------------------------------------------------------------------------


def test_err1_p09_no_non_test_module_references_the_sidecar():
    assert _nontest_files_referencing_the_sidecar() == []


def test_err1_p09_the_scan_and_the_results_check_catch_a_violation(tmp_path):
    tree = tmp_path / "experiments"
    (tree / "pkg" / "tests").mkdir(parents=True)
    (tree / "pkg" / "runtime.py").write_text('SIDE = "x.composed-model.json"\n', encoding="utf-8")
    (tree / "pkg" / "other.mjs").write_text("const p = serializedModelPath;\n", encoding="utf-8")
    (tree / "pkg" / "clean.py").write_text("x = 1\n", encoding="utf-8")
    (tree / "pkg" / "tests" / "helper.py").write_text('T = "composed-model"\n', encoding="utf-8")
    (tree / "pkg" / "test_thing.py").write_text('T = "composed-model"\n', encoding="utf-8")
    found = _nontest_files_referencing_the_sidecar(tree)
    assert sorted(Path(path).name for path in found) == ["other.mjs", "runtime.py"]

    results = tmp_path / "results" / "CFG1-S1-A9"
    results.mkdir(parents=True)
    _check_results_dir_has_no_sidecar(tmp_path / "results")
    (results / "models_Q.json.composed-model.json").write_text("{}", encoding="utf-8")
    with pytest.raises(AssertionError, match=r"P-09.*results"):
        _check_results_dir_has_no_sidecar(tmp_path / "results")

    claimed, text = r"C:\tmp\pytest\cfg1_t30\models_Q.json.composed-model.json", _plausible_text("Q")
    _check_nothing_emitted_names_the_sidecar('{"a": 1}', claimed, text)
    for emitted in (claimed, json.dumps(claimed), "x.composed-model.json", text):
        with pytest.raises(AssertionError, match=r"P-09"):
            _check_nothing_emitted_names_the_sidecar(emitted, claimed, text)


# ---------------------------------------------------------------------------
# P-10 -- no general handoff; one private carrier, requested only by R-37
# ---------------------------------------------------------------------------


def _carrier_violations(source: str) -> list[str]:
    tree = ast.parse(source)
    problems: list[str] = []
    functions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    requesters = {
        name for name, fn in functions.items() if any(a.arg == "_t3_run" for a in fn.args.args)
    }
    if requesters != {"conformance_report", _R37_NAME}:
        problems.append(f"requesters of _t3_run: {sorted(requesters)}")

    carrier = next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "_T3Run"), None)
    if carrier is None:
        problems.append("no _T3Run carrier")
    else:
        fields = [n.target.id for n in carrier.body if isinstance(n, ast.AnnAssign)]
        if fields != ["report", "workdir"]:
            problems.append(f"carrier members: {fields}")
        if any(isinstance(n, ast.FunctionDef) for n in carrier.body):
            problems.append("the carrier defines behaviour")

    fixture = functions.get("conformance_report")
    if fixture is not None:
        body = [
            n for n in fixture.body
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
        ]
        returns_report = (
            len(body) == 1
            and isinstance(body[0], ast.Return)
            and isinstance(body[0].value, ast.Attribute)
            and isinstance(body[0].value.value, ast.Name)
            and body[0].value.value.id == "_t3_run"
            and body[0].value.attr == "report"
        )
        if not returns_report:
            problems.append("conformance_report is not exactly `return _t3_run.report`")

    producer = functions.get("_t3_run")
    if producer is not None:
        makes_workdir = any(
            isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "workdir"
            and ast.unparse(n.value) == "tmp_path_factory.mktemp('cfg1_t3')"
            for n in ast.walk(producer)
        )
        returns = [n for n in ast.walk(producer) if isinstance(n, ast.Return)]
        carries_workdir = len(returns) == 1 and ast.unparse(returns[0].value) == "_T3Run(report=report, workdir=workdir)"
        if not makes_workdir:
            problems.append("the workdir is not Python's own mktemp('cfg1_t3') result")
        if not carries_workdir:
            problems.append("_t3_run does not return exactly _T3Run(report=report, workdir=workdir)")
    else:
        problems.append("no _t3_run fixture")
    return problems


def test_err1_p10_the_real_conformance_module_has_exactly_the_one_private_carrier():
    assert _carrier_violations(_CONFORMANCE_PATH.read_text(encoding="utf-8")) == []
    assert _T3Run._fields == ("report", "workdir")


def test_err1_p10_carrier_violations_are_caught():
    real = _CONFORMANCE_PATH.read_text(encoding="utf-8")
    mutations = {
        "another test requests the carrier": (
            "def test_t3_every_required_interception_point_was_installed(conformance_report):",
            "def test_t3_every_required_interception_point_was_installed(conformance_report, _t3_run):",
        ),
        "a third member": ("    report: dict\n    workdir: Path\n", "    report: dict\n    workdir: Path\n    sidecars: dict\n"),
        "the workdir is added to the report": (
            "    return _t3_run.report\n", "    return {**_t3_run.report, 'workdir': _t3_run.workdir}\n"),
        "the workdir does not come from mktemp": (
            'workdir = tmp_path_factory.mktemp("cfg1_t3")', 'workdir = Path(report_dir)'),
        "the carrier drops the workdir": (
            "return _T3Run(report=report, workdir=workdir)", "return _T3Run(report=report, workdir=None)"),
    }
    for label, (old, new) in mutations.items():
        assert real.count(old) >= 1, label
        assert _carrier_violations(real.replace(old, new, 1)), label


def test_err1_p10_no_helper_or_test_module_exists_beside_the_conformance_module():
    """ERR1 Sec. 5: P-01..P-10 add checks to ONE replaced test and ONE harness, plus the ONE carrier.

    Everything lives in this module. Two FU1 modules that exceeded that scope are gone, and
    nothing may replace them: no other file in the tests directory names the carrier or the
    sidecar, or is named for this erratum.
    """
    assert not (_TESTS_DIR / "cfg1_err1_sidecar.py").exists()
    assert not (_TESTS_DIR / "test_cfg1_err1_sidecar_provenance.py").exists()
    named_carrier, named_sidecar = set(), set()
    for path in sorted(_TESTS_DIR.iterdir()):
        if path.suffix not in {".py", ".mjs"}:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if "_t3_run" in content or "_T3Run" in content:
            named_carrier.add(path.name)
        if any(token in content for token in _SIDECAR_TOKENS):
            named_sidecar.add(path.name)
    assert named_carrier == {"test_cfg1_pi_conformance.py"}, named_carrier
    assert named_sidecar == {"cfg1_t3_conformance.mjs", "test_cfg1_pi_conformance.py"}, named_sidecar
    assert [path.name for path in _TESTS_DIR.iterdir() if "err1" in path.name.lower()] == []
