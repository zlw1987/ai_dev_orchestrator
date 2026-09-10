"""5F3B-LIVE1-I1 -- offline regression suite for ``run_semantic_sweep_live.py``.

**OFFLINE ONLY.** No test in this module calls
``run_one_primary_sweep_live``/``main`` with the live flag actually
authorized to proceed to a real sweep, launches Pi/Node, opens a broker
pipe, opens a socket, contacts B300, or reads a real credential. The runner
module is loaded as a plain Python module (it is a script, not a package)
so its functions can be imported and driven directly.
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import inspect
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_HERE = Path(__file__).resolve().parent
_RUNNER_PATH = _HERE.parent / "run_semantic_sweep_live.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_semantic_sweep_live_under_test", _RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def runner():
    return _load_runner()


with open(_RUNNER_PATH, "r", encoding="utf-8") as _f:
    _SOURCE_TEXT = _f.read()
_SOURCE_AST = ast.parse(_SOURCE_TEXT)


# ===========================================================================
# CLI surface
# ===========================================================================


def test_parser_declares_exactly_the_two_options(runner):
    """Matrix case 44."""
    parser = None
    for node in ast.walk(_SOURCE_AST):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "ArgumentParser"
        ):
            parser = node
            break
    assert parser is not None

    add_argument_calls = [
        node
        for node in ast.walk(_SOURCE_AST)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
    ]
    option_names = set()
    for call in add_argument_calls:
        for arg in call.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                option_names.add(arg.value)
    assert option_names == {"--candidate", "--run-primary-sweep-live"}


def test_candidate_is_required_with_no_default_and_declared_choices(runner):
    """Matrix case 27 (parser half)."""
    import argparse

    original_init = argparse.ArgumentParser.__init__
    captured = {}

    def _capture(self, *a, **kw):
        captured["parser"] = self
        return original_init(self, *a, **kw)

    argparse.ArgumentParser.__init__ = _capture
    try:
        # Triggers parser construction inside main(); missing --candidate
        # is itself an argparse usage error (SystemExit(2)), which is fine
        # -- the parser object is already captured by the time it raises.
        with pytest.raises(SystemExit):
            runner.main(["--run-primary-sweep-live"])
    finally:
        argparse.ArgumentParser.__init__ = original_init

    parser = captured["parser"]
    actions = {a.dest: a for a in parser._actions}
    candidate_action = actions["candidate"]
    assert candidate_action.required is True
    assert candidate_action.default is None
    assert tuple(candidate_action.choices) == tuple(sorted(runner.CANDIDATE_MODEL_IDS))

    flag_action = actions["run_primary_sweep_live"]
    assert flag_action.default is False


def test_no_workspace_ish_option_exists(runner):
    """Matrix case 28."""
    import argparse

    parser = argparse.ArgumentParser()
    # Re-derive the parser the same way main() does, by inspecting source
    # rather than re-executing main() with side effects.
    add_argument_calls = [
        node
        for node in ast.walk(_SOURCE_AST)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
    ]
    forbidden = (
        "--workspace",
        "--repo",
        "--path",
        "--project",
        "--task",
        "--tasks",
        "--model",
        "--provider",
        "--endpoint",
        "--base-url",
        "--api-key",
        "--max-tokens",
        "--retry",
        "--continue",
        "--resume",
        "--both",
        "--all-candidates",
        "--q2",
        "--timeout",
        "--force",
    )
    option_names = set()
    for call in add_argument_calls:
        for arg in call.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                option_names.add(arg.value)
    assert option_names.isdisjoint(forbidden)
    # And no supported code path anywhere in this script or in the adapter
    # module accepts an existing-path/workspace-ish parameter.
    sig = inspect.signature(runner.run_one_primary_sweep_live)
    assert set(sig.parameters) == {"candidate"}
    sig = inspect.signature(runner.build_adapters)
    assert set(sig.parameters) == {"candidate", "task"}


def test_refusing_without_the_live_flag_never_touches_live_machinery(runner, monkeypatch):
    def _boom(**kwargs):
        raise AssertionError("run_one_primary_sweep_live must not be called")

    monkeypatch.setattr(runner, "run_one_primary_sweep_live", _boom)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = runner.main(["--candidate", "A"])
    assert code == 1
    payload = json.loads(buf.getvalue())
    assert payload["refused"] is True
    assert payload["semantic_dispatch_attempts"] == 0


def test_missing_candidate_is_an_argparse_usage_error(runner):
    with pytest.raises(SystemExit) as excinfo:
        runner.main(["--run-primary-sweep-live"])
    assert excinfo.value.code == 2


def test_unknown_candidate_is_an_argparse_usage_error(runner):
    with pytest.raises(SystemExit) as excinfo:
        runner.main(["--candidate", "C", "--run-primary-sweep-live"])
    assert excinfo.value.code == 2


def test_pre_sweep_refusal_for_unknown_candidate_never_reaches_run_primary_sweep(runner, monkeypatch):
    calls = []
    monkeypatch.setattr(
        runner,
        "run_primary_sweep",
        lambda **kw: calls.append(kw) or (_ for _ in ()).throw(AssertionError("must not run")),
    )
    with pytest.raises(runner.PreSweepRefusal):
        runner._independent_pre_live_safety_check(candidate="Z")
    assert calls == []


# ===========================================================================
# FU2 issue 1 -- hostile candidate value must never leak through PreSweepRefusal
# ===========================================================================


class _ExplodingResultsDir:
    """Stands in for ``runner.RESULTS_DIR`` -- raises if ``mkdir`` is ever
    reached, proving a hostile/unknown candidate refuses strictly BEFORE any
    filesystem activity."""

    def mkdir(self, *a, **kw):
        raise AssertionError("RESULTS_DIR.mkdir must not be reached for an unknown candidate")


def test_hostile_candidate_value_never_leaks_through_pre_sweep_refusal(runner, monkeypatch):
    """FU2 issue 1. ``run_one_primary_sweep_live`` is a SUPPORTED Python
    entry point a caller can invoke directly with an ARBITRARY string --
    unlike the CLI's ``choices=``-restricted ``--candidate``. A hostile
    value planted with several recognizable needles (path-like, token-like,
    URL/endpoint-like, pipe/capability-like) must never reach
    ``PreSweepRefusal.reason`` or ``str(exception)``, and the refusal must
    happen strictly before any trusted-executable resolution, filesystem
    creation, or sweep invocation.
    """
    needles = (
        r"C:\Users\attacker\secret-dir\AIDO_workspace",
        "sk-fake-hostile-token-0001",
        "https://hostile-b300-proxy.example.invalid:8443/v1",
        r"\\.\pipe\hostile-broker-pipe",
        "cap-hostile-0001",
    )
    hostile_candidate = ";".join(needles)

    def _tripwire(name):
        def _fire(*a, **kw):
            raise AssertionError(f"{name} must not be called for an unknown candidate")

        return _fire

    monkeypatch.setattr(runner, "run_primary_sweep", _tripwire("run_primary_sweep"))
    monkeypatch.setattr(runner, "resolve_git_executable", _tripwire("resolve_git_executable"))
    monkeypatch.setattr(
        runner, "_ar2_resolve_node_executable", _tripwire("_ar2_resolve_node_executable")
    )
    monkeypatch.setattr(runner, "RESULTS_DIR", _ExplodingResultsDir())

    with pytest.raises(runner.PreSweepRefusal) as excinfo:
        runner.run_one_primary_sweep_live(candidate=hostile_candidate)

    assert excinfo.value.reason == runner._UNKNOWN_CANDIDATE_REASON
    rendered = str(excinfo.value)
    for needle in needles:
        assert needle not in excinfo.value.reason
        assert needle not in rendered
    assert hostile_candidate not in excinfo.value.reason
    assert hostile_candidate not in rendered


def test_every_pre_sweep_refusal_producer_uses_only_a_bounded_reason(runner):
    """FU2 issue 1 (mechanical guard). AST: every production
    ``PreSweepRefusal(reason=...)`` call site's ``reason`` argument is
    EITHER a fixed string literal, a reference to a module-level constant
    itself bound to a fixed string literal, or the exact
    ``type(exc).__name__`` shape -- never an f-string, a caller variable, a
    path, a candidate, an endpoint, a token, or any other runtime value.
    This guards against a FUTURE call site reintroducing the FU2 issue 1
    defect.
    """
    bounded_module_constants = {
        node.targets[0].id
        for node in ast.walk(_SOURCE_AST)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    assert "_UNKNOWN_CANDIDATE_REASON" in bounded_module_constants

    def _is_bounded(expr: ast.expr) -> bool:
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return True
        if isinstance(expr, ast.Name) and expr.id in bounded_module_constants:
            return True
        if (
            isinstance(expr, ast.Attribute)
            and expr.attr == "__name__"
            and isinstance(expr.value, ast.Call)
            and isinstance(expr.value.func, ast.Name)
            and expr.value.func.id == "type"
        ):
            return True
        return False

    call_sites = [
        node
        for node in ast.walk(_SOURCE_AST)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "PreSweepRefusal"
    ]
    assert len(call_sites) == 4  # keep this in sync with the actual producer count

    for call in call_sites:
        reason_kwargs = [kw for kw in call.keywords if kw.arg == "reason"]
        assert len(reason_kwargs) == 1, "PreSweepRefusal must be called with reason= exactly once"
        reason_expr = reason_kwargs[0].value
        assert _is_bounded(reason_expr), (
            f"PreSweepRefusal(reason=...) at line {call.lineno} is not a bounded "
            "literal / known constant / type(exc).__name__ shape"
        )
        # And never an f-string under any circumstance, redundantly checked.
        assert not isinstance(reason_expr, ast.JoinedStr)


# ===========================================================================
# `run_primary_sweep` call-site and no-serialization proofs
# ===========================================================================


def test_exactly_one_run_primary_sweep_call_site(runner):
    """Matrix case 19 (runner half) / 27."""
    calls = [
        node
        for node in ast.walk(_SOURCE_AST)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "run_primary_sweep")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "run_primary_sweep")
        )
    ]
    assert len(calls) == 1


def test_no_retry_fallback_or_run_both_path(runner):
    """Matrix case: no retry/fallback/run-both surface. AST: no comparison
    of ``candidate`` against a specific candidate LITERAL ("A"/"B") --
    the one legitimate ``candidate not in CANDIDATE_MODEL_IDS`` membership
    check treats every declared candidate identically and is not this. Also:
    no loop over the declared candidate set (a "run both" shape)."""
    for node in ast.walk(_SOURCE_AST):
        if isinstance(node, ast.Compare):
            left_is_candidate = isinstance(node.left, ast.Name) and node.left.id == "candidate"
            if left_is_candidate:
                for comparator in node.comparators:
                    if isinstance(comparator, ast.Constant) and comparator.value in ("A", "B"):
                        pytest.fail(
                            "candidate compared against a specific candidate literal"
                        )
        if isinstance(node, (ast.For, ast.While)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and sub.id == "CANDIDATE_MODEL_IDS":
                    pytest.fail("a loop over candidates was found in the runner")


def test_no_serialization_call_site(runner):
    """Matrix case 57. No file write anywhere in the runner: no
    ``json.dump``/``json.dumps`` targeting anything but stdout, no
    ``open(..., "w")``, no ``Path.write_text``/``write_bytes``, and no
    ``emit_evidence_or_refuse`` reference.
    """
    for node in ast.walk(_SOURCE_AST):
        if isinstance(node, ast.Attribute) and node.attr in ("write_text", "write_bytes"):
            pytest.fail(f"{node.attr} call found in the runner")
        if isinstance(node, ast.Name) and node.id == "emit_evidence_or_refuse":
            pytest.fail("emit_evidence_or_refuse referenced directly by the runner")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            pytest.fail("open() call found in the runner")
    dump_calls = [
        node
        for node in ast.walk(_SOURCE_AST)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "dump"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
    ]
    for call in dump_calls:
        assert len(call.args) >= 2
        target = call.args[1]
        assert (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "sys"
            and target.attr == "stdout"
        ), "json.dump target must be exactly sys.stdout"


def test_only_mkdir_touches_the_filesystem_for_results(runner):
    """The ONE filesystem write anywhere in this script is the results
    directory's own ``mkdir`` -- never a file write."""
    mkdir_calls = [
        node
        for node in ast.walk(_SOURCE_AST)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "mkdir"
    ]
    assert len(mkdir_calls) == 1


# ===========================================================================
# `build_adapters` inertness and wiring
# ===========================================================================


@pytest.mark.parametrize("task_name", ["IQ1_TASK", "IQ2_TASK", "IQ3_TASK"])
def test_build_adapters_is_completely_inert(runner, monkeypatch, task_name):
    """Matrix case 46. Every seam that COULD perform live activity is
    patched to a counting-and-raising fake, so a single stray call fails the
    test immediately rather than relying on object-state comments alone.
    Covers, per task: 0 subprocess.run, 0 subprocess.Popen, 0
    resolve_pi_identity, 0 IssuedRuntimeIdentity issuance, 0
    LiveCategoryBAdapters construction, 0 environment read, 0 credential
    read, 0 broker/pipe/runtime creation, 0 semantic transport, 0 semantic
    prompt.
    """
    import os
    import subprocess as subprocess_module

    import qualification.i2b_live_adapters as live_module
    import qualification.semantic_live_adapters as sla
    from qualification.corpus import IQ1_TASK, IQ2_TASK, IQ3_TASK
    from qualification.semantic_sweep import TaskAdapterBundle

    task = {"IQ1_TASK": IQ1_TASK, "IQ2_TASK": IQ2_TASK, "IQ3_TASK": IQ3_TASK}[task_name]

    calls: dict[str, int] = {
        "subprocess_run": 0,
        "subprocess_popen": 0,
        "resolve_pi_identity": 0,
        "issue_runtime_identity": 0,
        "live_category_b_construction": 0,
        "environment_read": 0,
        "credential_read": 0,
        "broker_server": 0,
        "pi_rpc_supervisor": 0,
        "grant_semantic_capability_issuance": 0,
        "build_semantic_task_live_adapters": 0,
    }

    def _tripwire(name):
        def _fire(*a, **kw):
            calls[name] += 1
            raise AssertionError(f"{name} must not be called by build_adapters() (inertness)")

        return _fire

    monkeypatch.setattr(subprocess_module, "run", _tripwire("subprocess_run"))
    monkeypatch.setattr(subprocess_module, "Popen", _tripwire("subprocess_popen"))
    monkeypatch.setattr(sla, "resolve_pi_identity", _tripwire("resolve_pi_identity"))
    monkeypatch.setattr(sla, "grant_semantic_capability_issuance", _tripwire(
        "grant_semantic_capability_issuance"
    ))
    monkeypatch.setattr(sla, "build_semantic_task_live_adapters", _tripwire(
        "build_semantic_task_live_adapters"
    ))
    monkeypatch.setattr(live_module, "_issue_runtime_identity", _tripwire("issue_runtime_identity"))
    monkeypatch.setattr(
        live_module.LiveCategoryBAdapters, "__init__", _tripwire("live_category_b_construction")
    )
    monkeypatch.setattr(live_module, "read_connection_values", _tripwire("credential_read"))
    monkeypatch.setattr(live_module, "BrokerServer", _tripwire("broker_server"))
    monkeypatch.setattr(live_module, "PiRpcSupervisor", _tripwire("pi_rpc_supervisor"))
    monkeypatch.setattr(os.environ, "get", _tripwire("environment_read"))

    bundle = runner.build_adapters("A", task)

    assert calls == {name: 0 for name in calls}
    assert type(bundle) is TaskAdapterBundle
    assert len(bundle.non_secret_gates) == 8
    adapters = bundle.read_connection.__self__
    assert adapters._base is None
    assert adapters._transport is None  # 0 semantic transport, 0 semantic prompt possible


def test_build_adapters_wires_a_fresh_adapter_and_binder_each_call(runner):
    from qualification.corpus import IQ1_TASK
    import qualification.semantic_live_adapters as sla

    bundle1 = runner.build_adapters("A", IQ1_TASK)
    bundle2 = runner.build_adapters("A", IQ1_TASK)

    assert bundle1.read_connection.__self__ is not bundle2.read_connection.__self__
    assert isinstance(bundle1.read_connection.__self__, sla.LiveSemanticAdapters)
    assert isinstance(bundle1.route_checker, runner._SemanticRouteCheckerBinder)


def test_runner_node_executable_matches_the_trusted_per_task_identity_resolver(
    runner, monkeypatch
):
    """Matrix case 51. Mechanically proves, with synthetic resolvers
    exercising the ACTUAL seams, that the runner's resolved
    ``node_executable`` is the SAME trusted identity the per-task
    activation's ``resolve_pi_identity`` trust check
    (``_require_runtime_identity_matches_trusted_resolution``) requires --
    not two independently-maintained resolvers that could silently drift.
    No Node is launched.
    """
    import ar2.launch as ar2_launch
    import qualification.i2b_live_adapters as live_module

    # Structural guarantee: both namespaces are bound to the EXACT SAME
    # underlying function object, imported from the same origin -- never a
    # second, independently-maintained resolver.
    assert runner._ar2_resolve_node_executable is ar2_launch._resolve_node_executable
    assert live_module._ar2_resolve_node_executable is ar2_launch._resolve_node_executable

    synthetic_node = r"C:\synthetic-fu1\node.exe"
    synthetic_package_root = r"C:\synthetic-fu1\pi"
    synthetic_cli_js = os.path.realpath(
        os.path.join(synthetic_package_root, "dist", "cli.js")
    )

    # Exercise the ACTUAL seams: patch BOTH namespace bindings -- the
    # runner's own imported name, and the per-task trust check's own -- to
    # the SAME synthetic resolver.
    monkeypatch.setattr(runner, "_ar2_resolve_node_executable", lambda: synthetic_node)
    monkeypatch.setattr(live_module, "_ar2_resolve_node_executable", lambda: synthetic_node)
    monkeypatch.setattr(
        live_module, "_ar2_resolve_pi_package_root", lambda: synthetic_package_root
    )

    resolved_by_runner = runner._ar2_resolve_node_executable()
    assert resolved_by_runner == synthetic_node

    from ar2.launch import RuntimeIdentity

    identity = RuntimeIdentity(
        node_executable=resolved_by_runner,
        pi_cli_js=synthetic_cli_js,
        pi_package_root=synthetic_package_root,
        reported_version="0.84.4",
        launch_shape="node_direct",
    )
    # Never raises: the runner-resolved node_executable satisfies EXACTLY
    # the trust check a freshly-issued per-task identity must pass.
    live_module._require_runtime_identity_matches_trusted_resolution(identity)

    # A DIFFERENT (not runner-resolved) node_executable is correctly
    # refused -- proving the check genuinely discriminates rather than
    # being vacuously satisfied.
    forged_identity = RuntimeIdentity(
        node_executable=r"C:\attacker\node.exe",
        pi_cli_js=synthetic_cli_js,
        pi_package_root=synthetic_package_root,
        reported_version="0.84.4",
        launch_shape="node_direct",
    )
    with pytest.raises(live_module.LiveAdapterError):
        live_module._require_runtime_identity_matches_trusted_resolution(forged_identity)


# ===========================================================================
# Route checker binder
# ===========================================================================


def test_route_checker_binder_has_exactly_two_constructor_parameters(runner):
    """Matrix case 53."""
    signature = inspect.signature(runner._SemanticRouteCheckerBinder.__init__)
    assert set(signature.parameters) == {"self", "candidate", "adapters"}


def test_route_checker_binder_never_activates_and_constructs_exactly_one_observer(
    runner, monkeypatch
):
    """Matrix case 52."""
    import qualification.semantic_live_adapters as sla

    probe_calls = []
    monkeypatch.setattr(sla, "resolve_pi_identity", lambda: probe_calls.append(1) or object())

    from qualification.corpus import IQ1_TASK

    adapters = sla.LiveSemanticAdapters(task=IQ1_TASK, environ_reader=lambda k, d=None: d)
    binder = runner._SemanticRouteCheckerBinder(candidate="A", adapters=adapters)

    with pytest.raises(sla.LiveSemanticAdapterError):
        binder("https://example.invalid", model_id="qwen3-coder-next")
    assert probe_calls == []  # never activates

    build_calls = []
    fake_observer_calls = []

    class _FakeObserver:
        def __call__(self, base_url, *, model_id):
            fake_observer_calls.append((base_url, model_id))
            return "route-observation-sentinel"

    def fake_build_checker(*, candidate, adapters):
        build_calls.append((candidate, adapters))
        return _FakeObserver()

    monkeypatch.setattr(runner, "build_authenticated_route_checker", fake_build_checker)
    monkeypatch.setattr(
        sla,
        "build_semantic_task_live_adapters",
        lambda **kw: SimpleNamespace(read_connection=lambda: "connection-values-sentinel"),
    )
    adapters.read_connection()

    result1 = binder("https://example.invalid", model_id="qwen3-coder-next")
    result2 = binder("https://example.invalid", model_id="qwen3-coder-next")
    assert result1 == "route-observation-sentinel"
    assert result2 == "route-observation-sentinel"
    assert len(build_calls) == 1  # constructed exactly once
    assert len(fake_observer_calls) == 2  # both calls delegate to the SAME observer


# ===========================================================================
# Exit codes and console summary
# ===========================================================================


def _fake_sweep_result(
    *,
    not_attempted=(),
    indeterminate=(),
    tasks=None,
    hard_bar_state="INCOMPLETE",
):
    return SimpleNamespace(
        candidate="A",
        model_id="qwen3-coder-next",
        confirmed_semantic_prompts_sent=0,
        semantic_dispatch_attempts=0,
        indeterminate_dispatch_task_ids=tuple(indeterminate),
        not_attempted_task_ids=tuple(not_attempted),
        hard_bar_result=SimpleNamespace(qualification_state=SimpleNamespace(value=hard_bar_state)),
        task_results=tasks or {},
    )


def test_exit_code_zero_when_nothing_outstanding(runner):
    assert runner._exit_code(_fake_sweep_result()) == 0


def test_exit_code_two_when_not_attempted(runner):
    assert runner._exit_code(_fake_sweep_result(not_attempted=("IQ-3",))) == 2


def test_exit_code_two_when_indeterminate(runner):
    assert runner._exit_code(_fake_sweep_result(indeterminate=("IQ-2",))) == 2


def test_console_summary_never_discloses_forbidden_needles(runner, capsys):
    """Matrix case 58: planted needles never reach stdout."""
    task_result = SimpleNamespace(
        gate_statuses={"broker_session": "PASSED"},
        dispatch_state=SimpleNamespace(value="CONFIRMED_SENT"),
        run_validity=SimpleNamespace(value="VALID"),
        scoring_eligible=True,
        failed_gate=None,
        evidence_emission=SimpleNamespace(
            path=r"C:\Users\secret-operator\AppData\Local\Temp\needle-dir\A_IQ-1.json",
            refused=False,
        ),
    )
    result = _fake_sweep_result(tasks={"IQ-1": task_result})

    runner.print_bounded_summary(result)
    captured = capsys.readouterr().out

    forbidden = (
        "secret-operator",
        "needle-dir",
        r"C:\Users",
        "sk-fake-api-key",
        r"\\.\pipe\fake",
        "cap-fake-0001",
    )
    for needle in forbidden:
        assert needle not in captured
    assert "A_IQ-1.json" in captured  # the FILE NAME alone is authorized
    assert '"aido_requested_max_output_tokens": null' in captured


def test_console_summary_is_valid_json_with_the_declared_bounded_fields(runner, capsys):
    task_result = SimpleNamespace(
        gate_statuses={"broker_session": "PASSED"},
        dispatch_state=SimpleNamespace(value="CONFIRMED_SENT"),
        run_validity=SimpleNamespace(value="VALID"),
        scoring_eligible=True,
        failed_gate=None,
        evidence_emission=SimpleNamespace(path="/tmp/A_IQ-1.json", refused=False),
    )
    result = _fake_sweep_result(tasks={"IQ-1": task_result})
    runner.print_bounded_summary(result)
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidate"] == "A"
    assert payload["phase"] == "5F3B-LIVE1-I1"
    assert payload["aido_requested_max_output_tokens"] is None
    assert payload["tasks"]["IQ-1"]["artifact_file_name"] == "A_IQ-1.json"
    assert payload["tasks"]["IQ-1"]["scrub_outcome"] == "clean"
