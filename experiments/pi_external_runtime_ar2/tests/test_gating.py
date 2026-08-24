"""GATING -- every mechanically evaluated live gate, and what a failure costs.

The rule under test is uniform: **a failed gate means ZERO prompts for that
case.** Not a weakened check, not a retry, and not a consumed attempt for any
other case.

The end-to-end tests here drive the real :func:`run_ar2.phase_case` against a
SYNTHETIC Pi process. No model, no network, no API key, and no real Pi binary.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

import run_ar2
from ar2.handshakes import evaluate_extension_identity, evaluate_model_identity
from ar2.launch import LaunchIdentityError, RuntimeIdentity, resolve_runtime_identity
from ar2.manifest import ManifestTooLargeError, build_prompt_manifest
from ar2.pi_config import SENTINEL_COMMAND_NAME
from ar2.route_check import RouteModelCheck, check_route_serves_model


# -- H1: exact extension identity ----------------------------------------------


def test_h1_passes_only_on_exact_identity(tmp_path):
    entry = tmp_path / "index.ts"
    entry.write_text("// extension\n", encoding="utf-8")
    result = evaluate_extension_identity(
        [
            {
                "name": SENTINEL_COMMAND_NAME,
                "source": "extension",
                "sourceInfo": {"source": "cli", "path": str(entry)},
            }
        ],
        extension_entry=str(entry),
    )
    assert result["passed"] is True
    assert result["extension_path_matched"] is True


@pytest.mark.parametrize(
    "commands, why",
    [
        ([], "no sentinel at all"),
        ([{"name": "something_else", "source": "extension"}], "wrong name"),
        ([{"name": SENTINEL_COMMAND_NAME, "source": "builtin"}], "not extension-sourced"),
        ([{"name": SENTINEL_COMMAND_NAME, "source": "extension"}], "no path reported"),
        (
            [
                {
                    "name": SENTINEL_COMMAND_NAME,
                    "source": "extension",
                    "sourceInfo": {"source": "cli", "path": "C:\\somewhere\\else.ts"},
                }
            ],
            "a different path",
        ),
        (
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension", "sourceInfo": "junk"}],
            "malformed sourceInfo",
        ),
        (
            [{"name": SENTINEL_COMMAND_NAME, "source": "extension", "path": 17}],
            "a non-string flat path",
        ),
    ],
)
def test_h1_fails_closed_on_every_ambiguity(tmp_path, commands, why):
    entry = tmp_path / "index.ts"
    entry.write_text("// extension\n", encoding="utf-8")
    result = evaluate_extension_identity(commands, extension_entry=str(entry))
    assert result["passed"] is False, why
    assert result["failure_reasons"]


def test_h1_refuses_a_contradictory_source_origin(tmp_path):
    entry = tmp_path / "index.ts"
    entry.write_text("// extension\n", encoding="utf-8")
    result = evaluate_extension_identity(
        [
            {
                "name": SENTINEL_COMMAND_NAME,
                "source": "extension",
                "sourceInfo": {"source": "project", "path": str(entry)},
            }
        ],
        extension_entry=str(entry),
    )
    assert result["passed"] is False
    assert result["noncontradictory_source_origin"] is False


def test_h1_records_what_it_does_not_prove(tmp_path):
    entry = tmp_path / "index.ts"
    entry.write_text("//\n", encoding="utf-8")
    result = evaluate_extension_identity([], extension_entry=str(entry))
    assert "tool registry" in result["does_not_prove"]
    assert "no RPC command that enumerates tools" in result["does_not_prove"]
    assert "the intended extension loaded" in result["proves"]


# -- H2: exact provider/model identity -----------------------------------------


def test_h2_passes_only_on_an_exact_provider_and_model_match():
    response = {
        "success": True,
        "data": {"model": {"provider": "p", "id": "Qwen3.6-27B-262K", "api": "openai-completions"}},
    }
    assert evaluate_model_identity(
        response, expected_provider="p", expected_model="Qwen3.6-27B-262K"
    )["passed"] is True
    assert evaluate_model_identity(
        response, expected_provider="other", expected_model="Qwen3.6-27B-262K"
    )["passed"] is False
    assert evaluate_model_identity(
        response, expected_provider="p", expected_model="some-other-model"
    )["passed"] is False
    assert evaluate_model_identity(None, expected_provider="p", expected_model="m")["passed"] is False


def test_h2_never_records_the_base_url_and_never_triggers_inference():
    result = evaluate_model_identity(
        {"success": True, "data": {"model": {"provider": "p", "id": "m", "baseUrl": "http://x"}}},
        expected_provider="p",
        expected_model="m",
    )
    assert result["reported_base_url_recorded"] is False
    assert result["triggered_inference"] is False
    assert "http://" not in json.dumps(result)


# -- Pi version ----------------------------------------------------------------


def test_a_pi_version_mismatch_is_terminal():
    with pytest.raises(LaunchIdentityError, match="version mismatch"):
        resolve_runtime_identity(expected_version="0.0.0-not-this-one")


def test_no_fallback_launch_architecture_exists():
    """Node-direct or nothing: no ``pi.cmd``, no ``cmd.exe``, no ``shell=True``."""
    from ar2 import launch

    source = inspect.getsource(launch)
    assert "no fallback launch architecture is attempted" in source

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Only string LITERALS in code matter; docstrings are excluded below.
            continue
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    docstrings = {
        ast.get_docstring(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))
    }
    code_literals = literals - {d for d in docstrings if d}
    for banned in ("pi.cmd", "cmd.exe", "/c"):
        assert banned not in code_literals
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "shell":
                    assert getattr(keyword.value, "value", None) is False


# -- manifest caps -------------------------------------------------------------


def test_a_fixture_over_the_manifest_entry_cap_is_refused_before_any_model_call():
    from ar2.capability import mint_capability
    from ar2.fixtures import create_disposable_experiment_root, remove_disposable_tree

    authority = create_disposable_experiment_root(case_id="t")
    manifest = tuple(f"src/module_{i:04d}.py" for i in range(250))
    try:
        sed = mint_capability(
            authority=authority,
            tracked_manifest=manifest + ("tests/test_all.py",),
            protected_patterns=("tests/*",),
            verification_witness_paths=("tests/test_all.py",),
        )
        with pytest.raises(ManifestTooLargeError, match="entries"):
            build_prompt_manifest(sed)
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_a_fixture_over_the_manifest_byte_cap_is_refused():
    from ar2.capability import mint_capability
    from ar2.fixtures import create_disposable_experiment_root, remove_disposable_tree

    authority = create_disposable_experiment_root(case_id="t")
    long_name = "src/" + ("d" * 180) + "_{}.py"
    manifest = tuple(long_name.format(i) for i in range(60))
    try:
        sed = mint_capability(
            authority=authority,
            tracked_manifest=manifest + ("tests/test_all.py",),
            protected_patterns=("tests/*",),
            verification_witness_paths=("tests/test_all.py",),
        )
        with pytest.raises(ManifestTooLargeError, match="bytes"):
            build_prompt_manifest(sed)
    finally:
        remove_disposable_tree(authority.experiment_root)


def test_the_manifest_names_no_discovery_tool(r2_repo, git_executable):
    from conftest import mint_for
    from ar2.fixtures import R2

    manifest = build_prompt_manifest(mint_for(R2, git_executable, r2_repo))
    described = manifest.as_dict()
    for key in ("list_tool", "find_tool", "grep_tool", "search_tool", "glob_tool"):
        assert described[key] is False
    assert "no list, find, search or glob tool" in manifest.text
    assert "shipping/weights.py" in manifest.text
    assert "tests/test_shipping.py" in manifest.text
    editable_line = [ln for ln in manifest.text.splitlines() if ln.startswith("Files you may edit")][0]
    assert "tests/test_shipping.py" not in editable_line


def test_the_prompt_carries_no_absolute_path_or_binding(r2_repo, git_executable):
    from conftest import mint_for
    from ar2.fixtures import R2
    from ar2.manifest import compose_prompt

    sed = mint_for(R2, git_executable, r2_repo)
    prompt = compose_prompt(R2.prompt, build_prompt_manifest(sed))
    assert sed.canonical_root not in prompt
    assert "C:\\" not in prompt
    assert "\\\\.\\pipe\\" not in prompt
    assert sed.capability_id not in prompt


# -- the prompt is sent from exactly one place, behind the gate ----------------


def test_the_only_semantic_prompt_send_is_inside_the_gate_branch():
    """Structural proof that a failed gate cannot reach a prompt."""
    tree = ast.parse(inspect.getsource(run_ar2))
    phase_case = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "phase_case"
    )
    prompt_sends = []
    for node in ast.walk(phase_case):
        if isinstance(node, ast.Constant) and node.value == "prompt":
            prompt_sends.append(node)
    assert len(prompt_sends) == 1, "exactly one place may send a semantic prompt"

    gate_branches = [
        node
        for node in ast.walk(phase_case)
        if isinstance(node, ast.If)
        and "gate_all_passed" in ast.dump(node.test)
    ]
    assert gate_branches, "the prompt must sit behind the gate test"
    guarded = any(
        any(n is prompt_sends[0] for n in ast.walk(branch)) for branch in gate_branches
    )
    assert guarded is True


def test_the_total_semantic_prompt_budget_is_four():
    assert run_ar2.MAX_SEMANTIC_PROMPTS_TOTAL == 4
    from ar2.fixtures import REQUIRED_CASES

    assert len(REQUIRED_CASES) == 4
    assert [c.case_id for c in REQUIRED_CASES] == ["R1", "R2", "R3", "R4"]


def test_case_requires_both_explicit_flags(tmp_path, monkeypatch, capsys):
    config = tmp_path / "experiment_config.json"
    config.write_text(
        json.dumps(
            {
                "provider_id": "p",
                "model_id": "Qwen3.6-27B-262K",
                "base_url_env_name": "AR2_TEST_UNSET_VARIABLE",
                "python_executable": sys.executable,
            }
        ),
        encoding="utf-8",
    )
    code = run_ar2.main(["--phase", "case", "--case", "R1", "--config", str(config)])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["refused"] is True
    assert payload["semantic_prompts_sent"] == 0
    assert "requires BOTH" in payload["reason"]


def test_an_absent_config_file_is_a_refusal(tmp_path, capsys):
    code = run_ar2.main(["--phase", "preflight", "--config", str(tmp_path / "nope.json")])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["refused"] is True
    assert "ships absent deliberately" in payload["reason"]


def test_a_model_other_than_the_pinned_one_is_refused(tmp_path, capsys):
    config = tmp_path / "experiment_config.json"
    config.write_text(
        json.dumps(
            {
                "provider_id": "p",
                "model_id": "google/gemma-4-26B-A4B-it",
                "base_url_env_name": "AR2_TEST_UNSET_VARIABLE",
                "python_executable": sys.executable,
            }
        ),
        encoding="utf-8",
    )
    code = run_ar2.main(["--phase", "preflight", "--config", str(config)])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert "pinned to the AR1-proven model" in payload["reason"]


# -- end to end, against a SYNTHETIC Pi process --------------------------------


@pytest.fixture()
def stub_case_environment(tmp_path, monkeypatch, fake_pi):
    """Patch the runtime identity and argv so ``phase_case`` drives a fake Pi."""
    log = tmp_path / "commands.log"

    def build(script_extra: dict) -> dict:
        script = {"command_log": str(log), **script_extra}
        argv = fake_pi(script)
        identity = RuntimeIdentity(
            node_executable=sys.executable,
            pi_cli_js=argv[1],
            pi_package_root=str(tmp_path),
            reported_version="0.84.2",
            launch_shape="node_direct",
        )
        monkeypatch.setattr(run_ar2, "resolve_runtime_identity", lambda **_kw: identity)
        monkeypatch.setattr(run_ar2, "build_pi_argv", lambda *_a, **_k: argv)
        monkeypatch.setattr(
            run_ar2, "_resolve_base_url", lambda _c: "http://stub.invalid:1/v1"
        )
        # The route check is a REAL HTTP call in the live harness. The offline
        # suite makes no network call at all, so it is stubbed to "served" here
        # and is exercised properly against httpx.MockTransport below.
        monkeypatch.setattr(
            run_ar2,
            "check_route_serves_model",
            lambda _base, *, model_id: RouteModelCheck(
                reachable=True,
                status_code=200,
                configured_model_served=True,
                served_model_ids=(model_id,),
                endpoint_host="stub.invalid",
                endpoint_scheme="http",
                transport_tls=False,
                failure=None,
            ),
        )
        return {
            "provider_id": "aido-ar2-qwen36-direct-vllm",
            "model_id": "Qwen3.6-27B-262K",
            "base_url_env_name": "AR2_TEST_UNSET_VARIABLE",
            "python_executable": sys.executable,
        }

    return build, log


def test_h1_failure_sends_zero_prompts_end_to_end(stub_case_environment):
    build, log = stub_case_environment
    config = build(
        {
            "responses": {
                # A same-named command that is NOT extension-sourced: the pre-FU1
                # weak gate would have accepted this.
                "get_commands": {
                    "success": True,
                    "data": {"commands": [{"name": SENTINEL_COMMAND_NAME, "source": "builtin"}]},
                },
                "get_state": {
                    "success": True,
                    "data": {
                        "model": {
                            "provider": "aido-ar2-qwen36-direct-vllm",
                            "id": "Qwen3.6-27B-262K",
                        }
                    },
                },
            }
        }
    )
    run = run_ar2.phase_case(config, case_id="R1", profile_names=())
    from ar2.fixtures import remove_disposable_tree

    remove_disposable_tree(run["_internal"]["fixture"].experiment_root)

    assert run["gate_passed"] is False
    assert run["live_run_gate"]["extension_identity_handshake_passed"] is False
    assert run["prompt_sent"] is False
    assert run["semantic_prompts_sent"] == 0
    assert run["turn_outcome"] == "not_attempted"
    sent = log.read_text(encoding="utf-8").split()
    assert "prompt" not in sent
    assert sent == ["get_commands", "get_state"]
    assert run["broker_recorded_lifecycle"]["state_reached"] == "CLOSED"


def test_h2_failure_sends_zero_prompts_end_to_end(stub_case_environment, monkeypatch):
    build, log = stub_case_environment
    monkeypatch.setattr(
        run_ar2,
        "evaluate_extension_identity",
        lambda *_a, **_k: {"passed": True, "stubbed_for_offline_test": True},
    )
    config = build(
        {
            "responses": {
                "get_commands": {"success": True, "data": {"commands": []}},
                "get_state": {
                    "success": True,
                    "data": {"model": {"provider": "someone-else", "id": "some-other-model"}},
                },
            }
        }
    )
    run = run_ar2.phase_case(config, case_id="R1", profile_names=())
    from ar2.fixtures import remove_disposable_tree

    remove_disposable_tree(run["_internal"]["fixture"].experiment_root)

    assert run["live_run_gate"]["model_identity_handshake_passed"] is False
    assert run["gate_passed"] is False
    assert run["semantic_prompts_sent"] == 0
    assert "prompt" not in log.read_text(encoding="utf-8").split()


def test_a_broker_that_cannot_reach_ready_sends_zero_prompts(
    stub_case_environment, monkeypatch
):
    build, log = stub_case_environment
    config = build({"responses": {}})

    class RefusingServer(run_ar2.BrokerServer):
        def start(self, **_kwargs):  # noqa: D102 - test double
            from ar2.winpipe import WindowsPipeError

            raise WindowsPipeError("pipe error: synthetic READY failure")

        def shutdown(self, trigger):  # noqa: D102 - test double
            return super().shutdown(trigger)

    monkeypatch.setattr(run_ar2, "BrokerServer", RefusingServer)
    run = run_ar2.phase_case(config, case_id="R1", profile_names=())
    from ar2.fixtures import remove_disposable_tree

    remove_disposable_tree(run["_internal"]["fixture"].experiment_root)

    assert run["live_run_gate"]["broker_reached_ready_before_runtime_launch"] is False
    assert run["gate_passed"] is False
    assert run["semantic_prompts_sent"] == 0
    # Pi was never launched at all, so not even a handshake was sent.
    assert not log.exists() or log.read_text(encoding="utf-8").strip() == ""


def test_an_untrusted_baseline_sends_zero_prompts(stub_case_environment, monkeypatch):
    build, log = stub_case_environment
    monkeypatch.setattr(
        run_ar2,
        "evaluate_extension_identity",
        lambda *_a, **_k: {"passed": True, "stubbed_for_offline_test": True},
    )
    config = build(
        {
            "responses": {
                "get_commands": {"success": True, "data": {"commands": []}},
                "get_state": {
                    "success": True,
                    "data": {
                        "model": {
                            "provider": "aido-ar2-qwen36-direct-vllm",
                            "id": "Qwen3.6-27B-262K",
                        }
                    },
                },
            }
        }
    )
    real_preflight = run_ar2.phase_preflight

    def dirty_preflight(cfg, *, case_id):
        report = real_preflight(cfg, case_id=case_id)
        report["baseline_is_clean"] = False
        return report

    monkeypatch.setattr(run_ar2, "phase_preflight", dirty_preflight)
    run = run_ar2.phase_case(config, case_id="R1", profile_names=())
    from ar2.fixtures import remove_disposable_tree

    remove_disposable_tree(run["_internal"]["fixture"].experiment_root)

    assert run["live_run_gate"]["baseline_repository_trusted"] is False
    assert run["gate_passed"] is False
    assert run["semantic_prompts_sent"] == 0
    assert "prompt" not in log.read_text(encoding="utf-8").split()


def test_a_passing_gate_sends_exactly_one_prompt(stub_case_environment, monkeypatch):
    """The happy path, against a synthetic Pi that settles immediately."""
    build, log = stub_case_environment
    monkeypatch.setattr(
        run_ar2,
        "evaluate_extension_identity",
        lambda *_a, **_k: {"passed": True, "stubbed_for_offline_test": True},
    )
    config = build(
        {
            "responses": {
                "get_commands": {"success": True, "data": {"commands": []}},
                "get_state": {
                    "success": True,
                    "data": {
                        "model": {
                            "provider": "aido-ar2-qwen36-direct-vllm",
                            "id": "Qwen3.6-27B-262K",
                        }
                    },
                },
                "prompt": {"success": True},
            },
            "prompt_chunks": [
                json.dumps({"type": "agent_settled"}) + "\n",
            ],
        }
    )
    run = run_ar2.phase_case(config, case_id="R4", profile_names=())
    from ar2.fixtures import remove_disposable_tree

    remove_disposable_tree(run["_internal"]["fixture"].experiment_root)

    assert run["gate_passed"] is True
    assert run["prompt_sent"] is True
    assert run["semantic_prompts_sent"] == 1
    assert run["turn_outcome"] == "runtime_settled"
    assert log.read_text(encoding="utf-8").split() == ["get_commands", "get_state", "prompt"]
    # A synthetic runtime made no tool call, so R4's no-change shape holds.
    assert run["case_assessment"]["accepted_edit_operations"] == 0
    assert run["orchestrator_observed"]["classification"]["changed_tracked_paths"] == []
    assert run["broker_recorded_lifecycle"]["state_reached"] == "CLOSED"
    assert run["cross_check"]["agree"] is True


# -- the non-inference route/model gate ----------------------------------------
#
# Exercised against ``httpx.MockTransport``: no socket, no network, no model.


def _mock_route_check(
    handler, *, model_id: str, base_url: str = "http://route.invalid/v1", capture=None
):
    """Force ``ar2.route_check``'s ``httpx.Client(trust_env=False)`` onto a
    ``MockTransport`` -- no socket, no network -- while still exercising the
    REAL construction call, so a regression that dropped ``trust_env=False``
    would be caught by ``capture`` rather than silently passing.
    """
    import httpx

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    class _FixedTransportClient(real_client_cls):
        def __init__(self, *args, **kwargs):
            if capture is not None:
                capture.append(dict(kwargs))
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.Client = _FixedTransportClient
    try:
        return check_route_serves_model(base_url, model_id=model_id)
    finally:
        httpx.Client = real_client_cls


def test_the_route_gate_passes_when_the_backend_serves_the_configured_model():
    import httpx

    result = _mock_route_check(
        lambda request: httpx.Response(200, json={"data": [{"id": "Qwen3.6-27B-262K"}]}),
        model_id="Qwen3.6-27B-262K",
    )
    assert result.configured_model_served is True
    assert result.reachable is True
    assert result.served_model_ids == ("Qwen3.6-27B-262K",)
    assert result.failure is None


def test_the_route_gate_fails_when_the_backend_serves_a_different_id():
    """Exactly the R1-a mismatch, as an offline regression test."""
    import httpx

    result = _mock_route_check(
        lambda request: httpx.Response(200, json={"data": [{"id": "Qwen3.6-27B-262K"}]}),
        model_id="Qwen3.6-27B-131K",
    )
    assert result.configured_model_served is False
    assert "not among the ids this route serves" in result.failure


def test_the_route_gate_never_prefix_or_family_matches():
    import httpx

    for served, configured in (
        ("Qwen3.6-27B-262K", "Qwen3.6-27B"),
        ("Qwen3.6-27B", "Qwen3.6-27B-262K"),
        ("qwen3.6-27b-262k", "Qwen3.6-27B-262K"),
    ):
        result = _mock_route_check(
            lambda request, served=served: httpx.Response(200, json={"data": [{"id": served}]}),
            model_id=configured,
        )
        assert result.configured_model_served is False


def test_an_unreachable_route_fails_closed():
    import httpx

    def boom(request):
        raise httpx.ConnectError("refused", request=request)

    result = _mock_route_check(boom, model_id="Qwen3.6-27B-262K")
    assert result.reachable is False
    assert result.configured_model_served is False
    assert "route unreachable" in result.failure


def test_a_non_200_listing_fails_closed():
    import httpx

    result = _mock_route_check(
        lambda request: httpx.Response(503, text="unavailable"), model_id="m"
    )
    assert result.configured_model_served is False
    assert "HTTP 503" in result.failure


def test_an_unparseable_listing_fails_closed():
    import httpx

    result = _mock_route_check(
        lambda request: httpx.Response(200, text="not json at all"), model_id="m"
    )
    assert result.configured_model_served is False
    assert "could not be parsed" in result.failure


def test_the_route_check_never_records_the_base_url_and_is_not_a_prompt():
    import httpx

    result = _mock_route_check(
        lambda request: httpx.Response(200, json={"data": [{"id": "m"}]}),
        model_id="m",
        base_url="http://10.9.8.7:8000/v1",
    )
    described = result.as_dict()
    assert described["base_url_recorded"] is False
    assert described["is_a_semantic_prompt"] is False
    assert described["tokens_generated"] == 0
    assert described["endpoint_scheme"] == "http"
    assert described["transport_tls"] is False
    assert described["transport_note"] == "NOT TLS-ENCRYPTED"
    # AR2 R1-b leaked a bare endpoint IP into a written result exactly here, so
    # the host is now carried in memory for the gate decision and NEVER rendered.
    assert described["endpoint_host_recorded"] is False
    assert "endpoint_host" not in described
    serialized = json.dumps(described)
    assert "10.9.8.7" not in serialized
    assert "http://10.9.8.7:8000/v1" not in serialized
    assert "8000" not in serialized


def test_the_endpoint_host_is_denylisted_by_the_scrub():
    from ar2.record import broker_secret_denylist, scrub_check

    denylist = broker_secret_denylist(
        token=None, capability_id=None, pipe_name=None, endpoint_host="10.9.8.7"
    )
    result = scrub_check({"leaked": "reached 10.9.8.7 fine"}, extra_forbidden=denylist)
    assert result["clean"] is False
    assert "endpoint_host_value_present" in result["findings"]
    assert "10.9.8.7" not in json.dumps(result)


def test_the_route_gate_is_evaluated_before_any_prompt_is_sent():
    """Structural: the gate is built, and the prompt sits behind the whole gate."""
    tree = ast.parse(inspect.getsource(run_ar2))
    phase_case = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "phase_case"
    )
    source = ast.unparse(phase_case)
    assert "route_serves_the_configured_model" in source
    gate_index = source.index("route_serves_the_configured_model")
    prompt_index = source.index("'prompt'")
    assert gate_index < prompt_index


# -- a no-change case is a TRUSTED shape, and AIDO still verifies it -----------


def test_a_no_change_case_is_trusted_and_still_gets_verified(
    stub_case_environment, monkeypatch
):
    """AR2's R4 run recorded ``verification: run=false`` for the CORRECT outcome.

    ``no_change_observed`` is the trusted shape for a case whose declared expected
    change set is empty, and suppressing verification there made "did not run"
    read as "failed". This is the regression test for that.
    """
    build, log = stub_case_environment
    monkeypatch.setattr(
        run_ar2,
        "evaluate_extension_identity",
        lambda *_a, **_k: {"passed": True, "stubbed_for_offline_test": True},
    )
    config = build(
        {
            "responses": {
                "get_commands": {"success": True, "data": {"commands": []}},
                "get_state": {
                    "success": True,
                    "data": {
                        "model": {
                            "provider": "aido-ar2-qwen36-direct-vllm",
                            "id": "Qwen3.6-27B-262K",
                        }
                    },
                },
                "prompt": {"success": True},
            },
            "prompt_chunks": [json.dumps({"type": "agent_settled"}) + "\n"],
        }
    )
    run = run_ar2.phase_case(config, case_id="R4", profile_names=())
    from ar2.fixtures import remove_disposable_tree

    remove_disposable_tree(run["_internal"]["fixture"].experiment_root)

    observed = run["orchestrator_observed"]
    assert observed["classification"]["workspace_class"] == "no_change_observed"
    assert observed["no_change_is_the_expected_shape_for_this_case"] is True
    verification = observed["verification"]
    assert verification.get("run") is not False, "AIDO must verify a no-change case"
    assert verification["passed"] is True
    assert verification["counts"] == {"passed": 4}
    assert run["case_assessment"]["verification_passed"] is True
    assert run["case_assessment"]["passed"] is True


def test_a_case_expecting_a_change_is_still_untrusted_when_nothing_changed(
    stub_case_environment, monkeypatch
):
    """The relaxation is scoped to cases that declare an EMPTY expected set."""
    build, log = stub_case_environment
    monkeypatch.setattr(
        run_ar2,
        "evaluate_extension_identity",
        lambda *_a, **_k: {"passed": True, "stubbed_for_offline_test": True},
    )
    config = build(
        {
            "responses": {
                "get_commands": {"success": True, "data": {"commands": []}},
                "get_state": {
                    "success": True,
                    "data": {
                        "model": {
                            "provider": "aido-ar2-qwen36-direct-vllm",
                            "id": "Qwen3.6-27B-262K",
                        }
                    },
                },
                "prompt": {"success": True},
            },
            "prompt_chunks": [json.dumps({"type": "agent_settled"}) + "\n"],
        }
    )
    run = run_ar2.phase_case(config, case_id="R1", profile_names=())
    from ar2.fixtures import remove_disposable_tree

    remove_disposable_tree(run["_internal"]["fixture"].experiment_root)

    observed = run["orchestrator_observed"]
    assert observed["no_change_is_the_expected_shape_for_this_case"] is False
    assert observed["verification"].get("run") is False
    assert run["case_assessment"]["passed"] is False


# -- FU-C: the route/model listing must not depend on ambient proxy state ------


def test_the_route_listing_client_is_constructed_with_trust_env_false():
    """Proves the REAL construction call in ar2.route_check disables ambient
    proxy/certificate trust, rather than merely asserting prose says so."""
    import httpx

    captured: list[dict] = []
    result = _mock_route_check(
        lambda request: httpx.Response(200, json={"data": [{"id": "m"}]}),
        model_id="m",
        capture=captured,
    )
    assert result.configured_model_served is True
    assert len(captured) == 1
    assert captured[0].get("trust_env") is False


def test_an_ambient_proxy_variable_does_not_change_the_route_gate_result(monkeypatch):
    """A regression test for exactly the defect FU-C closes: before
    ``trust_env=False``, a default httpx client would honor these variables and
    could silently route the listing request through an unrelated proxy."""
    import httpx

    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:1/definitely-not-a-real-proxy")

    result = _mock_route_check(
        lambda request: httpx.Response(200, json={"data": [{"id": "Qwen3.6-27B-262K"}]}),
        model_id="Qwen3.6-27B-262K",
    )
    # The MockTransport intercepted the request regardless of the ambient proxy
    # variables, which is exactly what trust_env=False guarantees: those
    # variables were never consulted.
    assert result.configured_model_served is True
    assert result.reachable is True


def test_route_check_source_never_constructs_a_default_trusting_client():
    """Structural: no code path in route_check.py may build a Client (or call
    the shorthand httpx.get, which is itself trust_env=True) without explicitly
    passing trust_env=False."""
    import ast
    import inspect

    from ar2 import route_check as route_check_module

    tree = ast.parse(inspect.getsource(route_check_module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "get":
            # httpx.get(...) / httpx.post(...) shorthand calls always honor
            # ambient trust_env and must never appear in this module.
            if isinstance(node.value, ast.Name) and node.value.id == "httpx":
                pytest.fail("route_check.py must not use the httpx.get(...) shorthand")
        if isinstance(node, ast.Call):
            func = node.func
            is_client_call = (
                isinstance(func, ast.Attribute)
                and func.attr == "Client"
                and isinstance(func.value, ast.Name)
                and func.value.id == "httpx"
            )
            if is_client_call:
                kwarg_names = {kw.arg for kw in node.keywords}
                assert "trust_env" in kwarg_names, (
                    "every httpx.Client(...) construction must pass trust_env"
                )
