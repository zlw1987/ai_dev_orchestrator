"""T-1, T-2, T-4 - T-10: composing frozen modules without amending any of them.

The single most important property here is **arm symmetry**: arm Q's generated
documents are byte-identical to the frozen qualification generator's for the
same inputs, and R, E and H differ from Q by exactly one provider-level
``compat`` subtree and nothing else. If that were not true, the experiment's
one manipulated variable would not be the only difference between its arms.

Pure Python, ``tmp_path``-scoped, no live Pi/network/model/credential activity.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pi_harness_cfg1 import arms, cfg1_pi_config, obs1, preflight, run_executor
from pi_harness_cfg1.cfg1_pi_config import (
    models_document,
    redacted_models_digest,
    settings_digest,
    settings_document,
    write_cfg1_pi_config,
)
from pi_harness_cfg1.identity import CFG1_MODEL_ID, CREDENTIAL_ENV_VAR_NAME, PROVIDER_ID

_PACKAGE_DIR = Path(__file__).resolve().parent.parent

#: A reserved, non-resolving synthetic endpoint. Never a real base URL, and
#: never one that could match a Pi compat-detection substring.
SYNTHETIC_BASE_URL = "https://cfg1-conformance.invalid/v1"
SYNTHETIC_CREDENTIAL = "cfg1-synthetic-key"


# ---------------------------------------------------------------------------
# T-1 -- arm Q is BYTE-identical to the frozen generator's output
# ---------------------------------------------------------------------------


def test_t1_arm_q_generated_documents_are_byte_identical_to_the_frozen_generator(
    tmp_path,
):
    from qualification import i2_issuance
    from qualification.i2_pi_config import write_qualification_pi_config

    frozen_root = tmp_path / "frozen"
    cfg1_root = tmp_path / "cfg1"
    frozen_root.mkdir()
    cfg1_root.mkdir()

    frozen = write_qualification_pi_config(
        str(frozen_root), model_id=CFG1_MODEL_ID, base_url=SYNTHETIC_BASE_URL
    )
    try:
        generated = write_cfg1_pi_config(
            str(cfg1_root), arm_id="Q", base_url=SYNTHETIC_BASE_URL
        )

        assert (
            Path(generated.settings_path).read_bytes()
            == Path(frozen.settings_path).read_bytes()
        )
        assert (
            Path(generated.models_path).read_bytes()
            == Path(frozen.models_path).read_bytes()
        )
        # Identity facts agree too, not merely the bytes.
        assert generated.provider_id == frozen.provider_id == PROVIDER_ID
        assert generated.model_id == frozen.model_id == CFG1_MODEL_ID
    finally:
        i2_issuance._discard_issuance(
            token=frozen.authority_token, config_dir=frozen.config_dir
        )


def test_the_generated_documents_never_contain_a_credential_value(tmp_path):
    cfg1_root = tmp_path / "cfg1"
    cfg1_root.mkdir()
    generated = write_cfg1_pi_config(
        str(cfg1_root), arm_id="Q", base_url=SYNTHETIC_BASE_URL
    )
    models_text = Path(generated.models_path).read_text(encoding="utf-8")
    assert SYNTHETIC_CREDENTIAL not in models_text
    # Exactly the `$ENV_NAME` interpolation form -- never `$$`, never `!shell`.
    assert f'"apiKey": "${CREDENTIAL_ENV_VAR_NAME}"' in models_text
    assert "$$" not in models_text
    assert "!" not in models_text
    # And no maxTokens at any level: AIDO imposes no output-token ceiling here.
    assert "maxTokens" not in models_text


def test_a_redacted_digest_is_a_shape_detector_never_an_endpoint_fingerprint():
    """Two DIFFERENT endpoints must produce the SAME redacted digest."""
    first = models_document(arm_id="Q", base_url="https://one.invalid/v1")
    second = models_document(arm_id="Q", base_url="https://two.invalid/v1")
    assert first != second
    assert redacted_models_digest(arm_id="Q") == arms.ARM_REDACTED_DIGEST["Q"]
    # The digest depends on the arm, not on the endpoint.
    for arm_id in ("Q", "R", "E", "H"):
        assert redacted_models_digest(arm_id=arm_id) == arms.ARM_REDACTED_DIGEST[arm_id]


# ---------------------------------------------------------------------------
# T-2 -- every other arm differs from Q by EXACTLY the compat subtree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("arm_id", ["R", "E", "H"])
def test_t2_each_variant_arm_differs_from_q_by_exactly_one_compat_subtree(arm_id):
    q_document = models_document(arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    variant = models_document(arm_id=arm_id, base_url=SYNTHETIC_BASE_URL)

    q_provider = q_document["providers"][PROVIDER_ID]
    variant_provider = variant["providers"][PROVIDER_ID]

    # Exactly one added key, and it is `compat`.
    assert set(variant_provider) - set(q_provider) == {"compat"}
    assert set(q_provider) - set(variant_provider) == set()
    assert variant_provider["compat"] == arms.ARM_COMPAT[arm_id]

    # Every other key is untouched, value for value.
    for key in q_provider:
        assert variant_provider[key] == q_provider[key], key

    # And the surrounding document is otherwise identical.
    assert set(variant) == set(q_document) == {"providers"}
    assert set(variant["providers"]) == {PROVIDER_ID}


@pytest.mark.parametrize("arm_id", ["R", "E", "H"])
def test_t2_the_compat_subtree_sits_exactly_between_apikey_and_models(arm_id):
    """Key ORDER matters for byte-identity, not only key membership."""
    variant = models_document(arm_id=arm_id, base_url=SYNTHETIC_BASE_URL)
    keys = list(variant["providers"][PROVIDER_ID])
    assert keys == ["baseUrl", "api", "apiKey", "compat", "models"]

    q_keys = list(models_document(arm_id="Q", base_url=SYNTHETIC_BASE_URL)["providers"][PROVIDER_ID])
    assert q_keys == ["baseUrl", "api", "apiKey", "models"]


def test_t2_the_settings_document_is_identical_for_every_arm():
    """The settings document carries no arm-dependent content at all."""
    assert settings_digest() == arms.PINNED_SETTINGS_SHA256
    document = settings_document()
    assert "defaultThinkingLevel" not in document
    assert document["retry"] == {
        "enabled": True,
        "maxRetries": 3,
        "baseDelayMs": 2000,
        "provider": {"maxRetries": 0},
    }


def test_the_declared_shape_and_effective_values_agree_with_the_compat_subtree():
    assert arms.ARM_COMPAT["Q"] is None
    assert arms.ARM_SHAPE["Q"] == "ABSENT"
    assert arms.ARM_COMPAT["R"] == {"supportsDeveloperRole": False}
    assert arms.ARM_EFFECTIVE["R"]["derived_system_role"] == "system"
    assert arms.ARM_EFFECTIVE["R"]["derived_reasoning_effort_sent"] == "medium"
    assert arms.ARM_COMPAT["E"] == {"supportsReasoningEffort": False}
    assert arms.ARM_EFFECTIVE["E"]["derived_system_role"] == "developer"
    assert arms.ARM_EFFECTIVE["E"]["derived_reasoning_effort_sent"] is None
    assert arms.ARM_COMPAT["H"] == {
        "supportsDeveloperRole": False,
        "supportsReasoningEffort": False,
    }


# ---------------------------------------------------------------------------
# T-4 -- the CFG1 child environment equals I2's policy for identical inputs
# ---------------------------------------------------------------------------


def test_t4_the_cfg1_child_environment_matches_the_frozen_i2_builder(tmp_path):
    from qualification import i2_issuance
    from qualification.i2_environment import build_child_environment
    from qualification.i2_pi_config import write_qualification_pi_config
    from qualification.i2_secret_context import build_secret_context

    from pi_harness_cfg1.environment import build_cfg1_child_environment

    ambient = {
        "SystemRoot": r"C:\Windows",
        "SystemDrive": "C:",
        "TEMP": r"C:\Temp",
        "PATHEXT": ".COM;.EXE",
        # Hostile decoys, none of which may propagate.
        "AIDO_LITELLM_BASE_URL": "https://decoy.invalid",
        "OPENAI_API_KEY": "decoy",
        "GITHUB_TOKEN": "decoy",
        "USERPROFILE": r"C:\Users\decoy",
        "HTTPS_PROXY": "http://decoy.invalid",
        "PATH": r"C:\decoy",
    }
    node_executable = r"C:\Program Files\nodejs\node.exe"

    frozen_root = tmp_path / "frozen"
    cfg1_root = tmp_path / "cfg1"
    frozen_root.mkdir()
    cfg1_root.mkdir()

    frozen_config = write_qualification_pi_config(
        str(frozen_root), model_id=CFG1_MODEL_ID, base_url=SYNTHETIC_BASE_URL
    )
    try:
        secret_context = build_secret_context(
            base_url=SYNTHETIC_BASE_URL,
            api_key=SYNTHETIC_CREDENTIAL,
            model_id=CFG1_MODEL_ID,
        )
        frozen_env = build_child_environment(
            ambient_environ=ambient,
            node_executable=node_executable,
            generated_config=frozen_config,
            secret_context=secret_context,
        )

        cfg1_config = write_cfg1_pi_config(
            str(cfg1_root), arm_id="Q", base_url=SYNTHETIC_BASE_URL
        )
        cfg1_env = build_cfg1_child_environment(
            ambient_environ=ambient,
            node_executable=node_executable,
            generated_config=cfg1_config,
            credential_value=SYNTHETIC_CREDENTIAL,
        )

        frozen_values = dict(frozen_env.environment)
        cfg1_values = cfg1_env.as_launch_snapshot()

        # Identical NAME set, exactly.
        assert sorted(cfg1_values) == sorted(frozen_values)
        # Identical values for every name except the one that legitimately
        # differs: each builder points the child at its OWN generated config.
        for name in frozen_values:
            if name == "PI_CODING_AGENT_DIR":
                assert cfg1_values[name] == cfg1_config.config_dir
                assert frozen_values[name] == frozen_config.config_dir
                continue
            assert cfg1_values[name] == frozen_values[name], name
    finally:
        i2_issuance._discard_issuance(
            token=frozen_config.authority_token, config_dir=frozen_config.config_dir
        )


def test_no_decoy_name_and_no_profile_name_ever_reaches_the_child(tmp_path):
    from pi_harness_cfg1.environment import audit_withheld_names, build_cfg1_child_environment

    ambient = {
        "SystemRoot": r"C:\Windows",
        "PATH": r"C:\decoy",
        "AIDO_LITELLM_BASE_URL": "https://decoy.invalid",
        "PI_QUALIFICATION_B300_ROUTE_KEY": "decoy",
        "OPENAI_API_KEY": "decoy",
        "ANTHROPIC_API_KEY": "decoy",
        "HTTPS_PROXY": "http://decoy.invalid",
        "GIT_DIR": r"C:\decoy\.git",
        "USERPROFILE": r"C:\Users\decoy",
        "HOME": r"C:\Users\decoy",
        "APPDATA": r"C:\Users\decoy\AppData",
        "EDITOR": "notepad",
    }
    cfg1_root = tmp_path / "cfg1"
    cfg1_root.mkdir()
    config = write_cfg1_pi_config(str(cfg1_root), arm_id="R", base_url=SYNTHETIC_BASE_URL)
    built = build_cfg1_child_environment(
        ambient_environ=ambient,
        node_executable=r"C:\Program Files\nodejs\node.exe",
        generated_config=config,
        credential_value=SYNTHETIC_CREDENTIAL,
    )
    audit = audit_withheld_names(
        ambient_environ=ambient, built_environment=built.environment
    )
    assert audit["sensitive_names_forwarded_to_child"] == []
    assert audit["profile_names_forwarded_to_child"] == []
    # The credential carrier IS present, under its one exact name, and is the
    # only forbidden-fragment name allowed through by exact identity.
    assert built.environment[CREDENTIAL_ENV_VAR_NAME] == SYNTHETIC_CREDENTIAL
    assert "PI_OFFLINE" in built.environment
    # The read-only view cannot be mutated into carrying something else.
    with pytest.raises(TypeError):
        built.environment["OPENAI_API_KEY"] = "oops"  # type: ignore[index]


def test_the_child_environment_builder_takes_no_arm_parameter():
    """Arm symmetry is STRUCTURAL here, not a policy that could be violated."""
    import inspect

    from pi_harness_cfg1.environment import build_cfg1_child_environment

    parameters = inspect.signature(build_cfg1_child_environment).parameters
    assert "arm_id" not in parameters
    assert "arm" not in parameters


# ---------------------------------------------------------------------------
# T-5 -- the baseline, and the frozen positive-allowlist outcome mapping
# ---------------------------------------------------------------------------


class _FakeActivity:
    def __init__(self, event_counts, tool_calls):
        self.event_type_counts = dict(event_counts)
        self.tool_calls = dict(tool_calls)
        self.unmatched_response_ids: list[str] = []
        self.agent_end_count = 0
        self.settled = False
        self.auto_retry_events = 0
        self.extension_errors: list[str] = []


class _FakeSupervisor:
    def __init__(self, activity):
        self.activity = activity

    def stdout_state(self):
        return {"records_ingested": 7}


def test_t5_the_cfg1_baseline_captures_what_the_frozen_adapter_captures():
    from qualification.semantic_live_adapters import _DispatchBaseline

    from pi_harness_cfg1.baseline import capture_cfg1_dispatch_baseline

    activity = _FakeActivity(
        {"tool_execution_start": 3, "tool_execution_end": 2, "agent_end": 1},
        {"call-a": {"toolName": "aido_read"}, "call-b": {"toolName": "aido_edit"}},
    )
    supervisor = _FakeSupervisor(activity)

    frozen = _DispatchBaseline.capture(supervisor)
    cfg1 = capture_cfg1_dispatch_baseline(supervisor)

    assert cfg1.agent_loop_event_counts == frozen.agent_loop_event_counts
    assert cfg1.pre_dispatch_tool_call_ids == frozen.pre_dispatch_tool_call_ids
    # Frozen, not live: mutating the supervisor afterwards cannot reach it.
    activity.tool_calls["call-c"] = {"toolName": "aido_read"}
    assert "call-c" not in cfg1.pre_dispatch_tool_call_ids


def test_t5_the_turn_outcome_mapping_is_the_frozen_positive_allowlist():
    from ar2 import supervisor as ar2_supervisor
    from qualification.semantic_session import SemanticTurnOutcome

    from pi_harness_cfg1.baseline import map_turn_wait_outcome

    expected = {
        ar2_supervisor.RUNTIME_SETTLED: SemanticTurnOutcome.SETTLED,
        ar2_supervisor.RUNTIME_DEADLINE_EXPIRED: SemanticTurnOutcome.DEADLINE_REACHED,
        ar2_supervisor.RUNTIME_PROTOCOL_VIOLATION: SemanticTurnOutcome.OBSERVATION_FAILED,
        ar2_supervisor.RUNTIME_OUTPUT_CAP_EXCEEDED: SemanticTurnOutcome.OBSERVATION_FAILED,
        ar2_supervisor.RUNTIME_EVENT_CAP_EXCEEDED: SemanticTurnOutcome.OBSERVATION_FAILED,
        ar2_supervisor.RUNTIME_READ_ERROR: SemanticTurnOutcome.OBSERVATION_FAILED,
        ar2_supervisor.RUNTIME_EXITED_EARLY: SemanticTurnOutcome.OBSERVATION_FAILED,
    }
    for literal, outcome in expected.items():
        assert map_turn_wait_outcome(literal) is outcome

    # Every literal the FROZEN adapter recognizes as a turn-wait outcome is
    # covered -- the table is not a convenient subset. (The supervisor also
    # declares dispatch-wait literals such as ``runtime_response_received``,
    # which are not turn-wait outcomes and are correctly absent here.)
    from qualification.semantic_live_adapters import _RECOGNIZED_TURN_WAIT_OUTCOMES

    assert set(expected) == set(_RECOGNIZED_TURN_WAIT_OUTCOMES)

    # ...plus an UNKNOWN literal, and every non-str, fail closed.
    for unknown in ("runtime_something_new", "", None, 7, True, object()):
        assert map_turn_wait_outcome(unknown) is SemanticTurnOutcome.OBSERVATION_FAILED


def test_the_wait_outcome_literal_mapping_never_guesses():
    from ar2 import supervisor as ar2_supervisor

    from pi_harness_cfg1.baseline import map_runtime_wait_outcome_literal

    assert map_runtime_wait_outcome_literal(ar2_supervisor.RUNTIME_SETTLED) == "SETTLED"
    assert (
        map_runtime_wait_outcome_literal(ar2_supervisor.RUNTIME_DEADLINE_EXPIRED)
        == "DEADLINE_EXPIRED"
    )
    for unknown in ("something_new", None, 7, True):
        assert map_runtime_wait_outcome_literal(unknown) == "UNRECOGNIZED"


# ---------------------------------------------------------------------------
# T-6 -- OBS1 is imported and called, never copied or subclassed
# ---------------------------------------------------------------------------


def test_t6_the_obs1_projection_and_snapshot_are_imported_not_redefined(monkeypatch):
    import qualification.runtime_activity as frozen_obs1

    # No CFG1 module defines either name at module level.
    for name in ("project_runtime_tool_activity", "RuntimeToolActivitySnapshot"):
        assert not hasattr(obs1, name), name
        for source_path in sorted(_PACKAGE_DIR.glob("*.py")):
            source = source_path.read_text(encoding="utf-8")
            assert f"def {name}" not in source, source_path
            assert f"class {name}" not in source, source_path

    # And the CFG1 wrapper genuinely calls the FROZEN function object.
    called: list[tuple] = []
    real = frozen_obs1.project_runtime_tool_activity

    def _spy(activity, baseline, *, turn_outcome):
        called.append((activity, baseline, turn_outcome))
        return real(activity, baseline, turn_outcome=turn_outcome)

    monkeypatch.setattr(frozen_obs1, "project_runtime_tool_activity", _spy)

    from qualification.semantic_session import SemanticTurnOutcome

    from pi_harness_cfg1.baseline import Cfg1DispatchBaseline

    activity = _FakeActivity({"tool_execution_start": 0, "tool_execution_end": 0}, {})
    fields = obs1.project_cfg1_runtime_activity(
        activity=activity,
        baseline=Cfg1DispatchBaseline(
            agent_loop_event_counts={"tool_execution_start": 0, "tool_execution_end": 0},
            pre_dispatch_tool_call_ids=frozenset(),
        ),
        turn_outcome=SemanticTurnOutcome.SETTLED,
    )
    assert len(called) == 1
    assert fields["runtime_reported_tool_activity_available"] is True
    assert fields["runtime_reported_tool_activity_capture_basis"] == "agent_settled"


def test_a_projection_failure_is_bounded_and_retains_no_exception_text(monkeypatch):
    import qualification.runtime_activity as frozen_obs1

    monkeypatch.setattr(
        frozen_obs1,
        "project_runtime_tool_activity",
        lambda *a, **k: (_ for _ in ()).throw(
            frozen_obs1.ActivityRecordInvariantError("a distinctive needle 41ab")
        ),
    )
    fields = obs1.project_cfg1_runtime_activity(
        activity=object(), baseline=object(), turn_outcome=object()
    )
    assert fields["runtime_reported_tool_activity_available"] is False
    assert fields["activity_unavailable_reason"] == "PROJECTION_REFUSED"
    assert "41ab" not in json.dumps(fields)
    assert all(
        value == 0
        for key, value in fields.items()
        if key.endswith(("_events", "_call_ids", "_end_observed", "_error_results"))
    )


def test_cfg1_emits_no_obs1_companion_artifact():
    """The F2 decision: CFG1 is an independent, non-qualification lineage.

    Scans for the companion's EMISSION machinery, not for prose that names it:
    the CFG1 module docstrings deliberately explain what is not emitted and
    why, and a literal-substring scan would flag that explanation as the
    violation it exists to rule out.
    """
    from pi_harness_cfg1 import (
        REFUSAL_RECORD_VERSION,
        RUN_RECORD_VERSION,
        STAGE_CLOSURE_RECORD_VERSION,
    )

    for source_path in sorted(_PACKAGE_DIR.glob("*.py")):
        source = source_path.read_text(encoding="utf-8")
        assert "emit_activity_companion" not in source, source_path
        assert "ACTIVITY_RECORD_VERSION" not in source, source_path
        assert "AttemptIdentity(" not in source, source_path

    # The three CFG1 families are the ONLY record versions this package writes.
    declared = {RUN_RECORD_VERSION, REFUSAL_RECORD_VERSION, STAGE_CLOSURE_RECORD_VERSION}
    version_pattern = re.compile(r'"(pi-[a-z0-9-]+\.v\d+)"')
    for source_path in sorted(_PACKAGE_DIR.glob("*.py")):
        for found in version_pattern.findall(source_path.read_text(encoding="utf-8")):
            assert found in declared, (source_path, found)


# ---------------------------------------------------------------------------
# T-7 -- stop reasons are enum counts, from message_end records only
# ---------------------------------------------------------------------------


def test_t7_stop_reasons_are_projected_from_captured_shape_records():
    events = [
        {"type": "message_end", "message": {"stopReason": "stop"}},
        {"type": "message_end", "message": {"stopReason": "toolUse"}},
        {"type": "message_end", "message": {"stopReason": "toolUse"}},
        {"type": "agent_end", "message": {"stopReason": "stop"}},  # not message_end
    ]
    available, counts = run_executor.project_stop_reasons(events)
    assert available is True
    assert counts == {
        "stop": 1,
        "length": 0,
        "toolUse": 2,
        "error": 0,
        "aborted": 0,
        "other": 0,
    }


def test_t7_an_unrecognized_stop_reason_is_bucketed_never_retained_verbatim():
    events = [{"type": "message_end", "message": {"stopReason": "a-new-reason-9f2"}}]
    available, counts = run_executor.project_stop_reasons(events)
    assert available is True
    assert counts["other"] == 1
    assert "a-new-reason-9f2" not in json.dumps(counts)


@pytest.mark.parametrize(
    "events",
    [
        [],
        None,
        [{"type": "message_end"}],
        [{"type": "message_end", "message": {}}],
        [{"type": "message_end", "message": None}],
        [{"type": "agent_settled"}],
    ],
)
def test_t7_absent_stop_reasons_set_availability_false_not_zero_errors(events):
    """Sec. 12.1 row 10 treats this as INDETERMINATE_PROVIDER, never as "clean"."""
    available, counts = run_executor.project_stop_reasons(events)
    assert available is False
    assert set(counts.values()) == {0}


# ---------------------------------------------------------------------------
# T-8 / T-9 -- CFG1 borrows no qualification SCORING authority, in any direction
# ---------------------------------------------------------------------------


_FORBIDDEN_QUALIFICATION_MODULES = (
    "hard_bar",
    "ranking",
    "validity",
    "outcomes",
    "lineage",
    "semantic_sweep",
    "semantic_controller",
)


def test_t8_cfg1_imports_nothing_from_the_frozen_scoring_modules():
    pattern = re.compile(
        r"^\s*(?:from|import)\s+(?:qualification\.)?(" + "|".join(_FORBIDDEN_QUALIFICATION_MODULES) + r")\b",
        re.MULTILINE,
    )
    for source_path in sorted(_PACKAGE_DIR.glob("*.py")):
        source = source_path.read_text(encoding="utf-8")
        assert pattern.search(source) is None, source_path
    # The qualification record BUILDERS are likewise never imported; only the
    # pure scrub check and the pure OBS1 projection are.
    for source_path in sorted(_PACKAGE_DIR.glob("*.py")):
        source = source_path.read_text(encoding="utf-8")
        assert "build_refusal_record" not in source, source_path
        assert "emit_evidence_or_refuse" not in source, source_path


def test_t9_no_cfg1_artifact_is_accepted_by_a_qualification_binder(
    make_authority, tmp_path
):
    from qualification.lineage import _require_run_record_shape
    from qualification.runtime_activity import verify_activity_companion_binding

    from cfg1_builders import refusal_payload, run_payload, stage_closure_payload

    for payload in (run_payload(), refusal_payload(), stage_closure_payload()):
        with pytest.raises(Exception):
            _require_run_record_shape(payload, context="cfg1 artifact")

    # And the companion binder refuses a CFG1 artifact at both of its paths.
    primary = tmp_path / "primary.json"
    companion = tmp_path / "companion.json"
    primary.write_text(json.dumps(run_payload()), encoding="utf-8")
    companion.write_text(json.dumps(run_payload()), encoding="utf-8")
    assert verify_activity_companion_binding(str(companion), str(primary)) is False


def test_the_cfg1_fixture_is_absent_from_the_qualification_corpus():
    from qualification.corpus import REQUIRED_TASKS
    from qualification.records import VALID_TASK_IDS

    from pi_harness_cfg1.fixture import CFG1_TASK_ID

    assert CFG1_TASK_ID not in VALID_TASK_IDS
    assert CFG1_TASK_ID not in {task.task_id for task in REQUIRED_TASKS}


# ---------------------------------------------------------------------------
# T-10 -- the offline guarantee, enforced rather than asserted
# ---------------------------------------------------------------------------


def test_t10_no_socket_and_no_dns_is_reachable_from_this_suite():
    import socket

    with pytest.raises(AssertionError):
        socket.socket()
    with pytest.raises(AssertionError):
        socket.create_connection(("cfg1.invalid", 443))
    with pytest.raises(AssertionError):
        socket.getaddrinfo("cfg1.invalid", 443)


def test_t10_no_real_endpoint_or_credential_is_readable():
    import os

    for name in (
        "AIDO_LITELLM_BASE_URL",
        "PI_QUALIFICATION_B300_ROUTE_KEY",
        "AIDO_VLLM_BASE_URL",
        "AIDO_VLLM_API_KEY",
    ):
        assert os.environ.get(name) is None, name


def test_t10_binding_the_live_ports_performs_no_live_action_by_itself():
    """Every port is BOUND, and merely building the set does nothing live.

    ``default_cfg1_run_ports`` composes the frozen AR2 broker, extension writer,
    supervisor and handshakes -- but composing a port set must not open a pipe,
    launch a process, read a credential, or contact anything. Only CALLING a
    port does, and only a live authorization may do that.
    """
    ports = run_executor.default_cfg1_run_ports(ambient_environ={})
    for name in (
        "build_broker",
        "write_extension",
        "evaluate_extension_identity",
        "evaluate_model_identity",
        "build_supervisor",
        "read_connection",
        "observe_route",
    ):
        assert callable(getattr(ports, name)), name
    # No port is a refusing placeholder any more.
    assert not any(
        getattr(getattr(ports, name), "__name__", "") == "_refuse"
        for name in vars(ports)
    )
    # And the one port that would read a real endpoint refuses while the
    # conftest has removed both names from the environment.
    with pytest.raises(RuntimeError):
        ports.read_connection()


def test_the_base_url_compat_classification_is_pure_and_never_retains_the_url():
    assert preflight.base_url_compat_detection_clear(SYNTHETIC_BASE_URL) is True
    for matching in (
        "https://api.openai.com/v1",
        "https://openrouter.ai/api/v1",
        "https://api.z.ai/v1",
        "https://gateway.ai.cloudflare.com/x",
        "https://API.X.AI/v1",
    ):
        assert preflight.base_url_compat_detection_clear(matching) is False
    for malformed in (None, 7, True, b"https://x.invalid"):
        assert preflight.base_url_compat_detection_clear(malformed) is False


def test_the_pinned_pi_seam_digest_table_covers_both_deferred_files():
    """The two pins the design deferred to the implementation phase."""
    assert "dist/modes/rpc/jsonl.js" in preflight.PINNED_PI_SEAM_DIGESTS
    assert (
        "node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js"
        in preflight.PINNED_PI_SEAM_DIGESTS
    )
    assert len(preflight.PINNED_PI_SEAM_DIGESTS) == 20
    for relative, digest in preflight.PINNED_PI_SEAM_DIGESTS.items():
        assert re.fullmatch(r"[0-9a-f]{64}", digest), relative
        assert "\\" not in relative, relative


def test_importing_the_cfg1_package_pulls_in_no_live_runtime_module():
    """The claim :mod:`run_executor`'s docstring makes, checked mechanically.

    ``ar2.broker`` and ``ar2.supervisor`` own the named pipe and the Pi child
    process. If importing CFG1 pulled either in, "importing this module does
    not import them" would be prose rather than a property -- and the offline
    suite's isolation would rest on that prose.
    """
    import subprocess
    import sys
    import textwrap

    probe = textwrap.dedent(
        """
        import sys
        sys.path[:0] = [
            "src",
            "experiments/pi_external_runtime_ar2",
            "experiments/pi_implementer_qualification",
            "experiments",
        ]
        import importlib, pkgutil
        import pi_harness_cfg1
        for info in pkgutil.iter_modules(pi_harness_cfg1.__path__):
            importlib.import_module("pi_harness_cfg1." + info.name)
        live = sorted(
            name
            for name in sys.modules
            if name in ("ar2.broker", "ar2.supervisor", "ar2.winpipe")
        )
        print(",".join(live))
        """
    )
    completed = subprocess.run(  # noqa: S603 - fixed argv, shell=False
        [sys.executable, "-c", probe],
        cwd=str(_PACKAGE_DIR.parents[1]),
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    pulled_in = completed.stdout.decode("utf-8").strip()
    assert pulled_in == "", f"importing CFG1 pulled in live runtime modules: {pulled_in}"
