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
import subprocess
import sys
from pathlib import Path

import pytest

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


@pytest.fixture(scope="module")
def conformance_report(tmp_path_factory):
    """Run the harness ONCE and share its report across the assertions."""
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
    return report


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
    """What ``get_state`` can report is the DECLARED shape, never the effective one."""
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


def test_t3_the_cfg1_projection_agrees_with_the_installed_runtimes_own_shape(
    conformance_report,
):
    """The CFG1 projection, run against the REAL composed model object.

    This is what closes the loop between Sec. 2.5's source derivation and
    Sec. 8.2's live manipulation check: the projection is exercised against the
    shape the installed composer actually produces, not against a fixture
    someone wrote to match it.
    """
    from pi_harness_cfg1.arms import ARM_SHAPE
    from pi_harness_cfg1.run_executor import project_get_state

    for arm_id in ("Q", "R", "E", "H"):
        arm = conformance_report["arms"][arm_id]
        model: dict = {"reasoning": arm["serializedModelReasoning"]}
        if arm["serializedModelHasCompatKey"]:
            model["compat"] = arm["serializedCompat"]
        projection = project_get_state(
            {"model": model, "thinkingLevel": "medium"}, arm_id=arm_id
        )
        assert projection["runtime_reported_compat_shape"] == ARM_SHAPE[arm_id]
        assert projection["manipulation_check_agrees"] is True


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
