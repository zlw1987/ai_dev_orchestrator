"""The Node extension against the REAL Python broker, over a real local pipe.

This is the one seam that neither the Python-only nor the Node-only offline test
covers on its own: the wire protocol as spoken by ``ipc.ts`` and as parsed by
:mod:`ar2.wire`. Covering it here means the live run is not the first time the
two halves meet.

Still: no model, no network, no API key, and no Pi process.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import secrets
from pathlib import Path

import pytest

from ar2.broker import (
    STATE_CLOSED,
    TRIGGER_AIDO_TEARDOWN,
    BrokerBinding,
    BrokerDiagnostics,
    BrokerRequestHandler,
    BrokerServer,
)
from ar2.capability import RunState
from ar2.fixtures import R1

from conftest import mint_for

_EXTENSION_SOURCE = Path(__file__).resolve().parent.parent / "extension"
_PROBE = Path(__file__).resolve().parent / "extension_client_probe.mjs"


def _pi_node_modules() -> str | None:
    shim = shutil.which("pi")
    if not shim:
        return None
    candidate = os.path.realpath(
        os.path.join(
            os.path.dirname(os.path.realpath(shim)),
            "node_modules",
            "@earendil-works",
            "pi-coding-agent",
            "node_modules",
        )
    )
    return candidate if os.path.isdir(candidate) else None


@pytest.fixture()
def live_broker_and_probe(tmp_path, node_executable, r1_repo, git_executable):
    """Start the real broker, generate the real extension config, run the probe."""
    modules = _pi_node_modules()
    if modules is None:  # pragma: no cover - environment dependent
        pytest.skip("the installed Pi package's node_modules were not found")

    sed = mint_for(R1, git_executable, r1_repo)
    binding = BrokerBinding.mint(sed.capability_id)
    run_state = RunState(caps=sed.caps)
    handler = BrokerRequestHandler(
        sed=sed, run_state=run_state, binding=binding, diagnostics=BrokerDiagnostics()
    )
    server = BrokerServer(handler)
    server.start()

    sandbox = tmp_path / "ext"
    sandbox.mkdir()
    for name in ("ipc.ts", "tools.ts", "index.ts", "package.json"):
        shutil.copyfile(_EXTENSION_SOURCE / name, sandbox / name)
    (sandbox / "ar2_config.ts").write_text(
        "export interface AidoAr2Config {\n"
        "  readonly experiment: string;\n"
        "  readonly pipeName: string;\n"
        "  readonly capabilityId: string;\n"
        "  readonly token: string;\n"
        "}\n"
        "export const AIDO_AR2_CONFIG: AidoAr2Config = "
        + json.dumps(
            {
                "experiment": "5F3A-AR2-cross-language-test",
                "pipeName": server.pipe_name,
                "capabilityId": binding.capability_id,
                "token": binding.token,
            },
            indent=2,
        )
        + ";\n",
        encoding="utf-8",
    )
    link = sandbox / "node_modules"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), modules], capture_output=True, check=False
    )
    if not link.exists():  # pragma: no cover - environment dependent
        server.shutdown(TRIGGER_AIDO_TEARDOWN)
        pytest.skip("a node_modules junction could not be created")

    completed = subprocess.run(
        [node_executable, str(_PROBE), str(sandbox)],
        capture_output=True,
        cwd=str(sandbox),
        timeout=120,
        check=False,
    )
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
    stdout = completed.stdout.decode("utf-8", "replace")
    stderr = completed.stderr.decode("utf-8", "replace")
    if completed.returncode != 0:  # pragma: no cover - surfaced as a failure
        pytest.fail(f"the Node probe exited {completed.returncode}\n{stderr}\n{stdout}")
    return json.loads(stdout), handler, run_state, lifecycle, r1_repo, binding


def test_the_node_client_and_the_python_broker_speak_the_same_protocol(
    live_broker_and_probe,
):
    results, _handler, _state, lifecycle, _repo, _binding = live_broker_and_probe
    assert results["readAllowed"]["ok"] is True
    assert "return value < limit" in results["readAllowed"]["text"]
    assert len(str(results["readAllowed"]["details"]["sha256"])) == 64
    assert lifecycle["state_reached"] == STATE_CLOSED


def test_the_broker_refuses_an_untracked_and_a_forbidden_read_through_the_extension(
    live_broker_and_probe,
):
    results, _handler, _state, _lifecycle, _repo, _binding = live_broker_and_probe
    for label in ("readUntracked", "readForbidden"):
        assert results[label]["ok"] is False
        assert results[label]["name"] == "AidoBrokerRefusedError"
        assert "refused" in results[label]["message"]
        # The refusal reaches the model with no path and no reason.
        assert ".git" not in results[label]["message"]
        assert "nope.py" not in results[label]["message"]


def test_the_broker_refuses_a_write_to_the_verification_witness_through_the_extension(
    live_broker_and_probe,
):
    results, handler, _state, _lifecycle, repo, _binding = live_broker_and_probe
    assert results["editWitness"]["ok"] is False
    assert results["editWitness"]["name"] == "AidoBrokerRefusedError"
    # And the witness on disk is untouched.
    body = (Path(repo.repo_root) / "test_calc.py").read_text(encoding="utf-8")
    assert "assert within_limit(10, 10) is True" in body
    assert any(
        "verification_witness_is_never_writable" in reason
        for reason in handler.diagnostics.refusal_reasons
    )


def test_an_allowed_edit_applies_and_a_stale_base_is_then_refused(
    live_broker_and_probe,
):
    results, _handler, state, _lifecycle, repo, _binding = live_broker_and_probe
    assert results["editAllowed"]["ok"] is True
    assert results["editAllowed"]["details"]["applied"] is True
    body = (Path(repo.repo_root) / "calc.py").read_text(encoding="utf-8")
    assert "return value <= limit" in body
    # The receipt moved to the post-image hash, so the OLD hash is now stale.
    assert results["editStale"]["ok"] is False
    assert state.read_receipts["calc.py"] == results["editAllowed"]["details"]["sha256_after"]
    assert state.mutated_paths == ["calc.py"]


def test_no_response_reaching_the_extension_carried_a_secret_or_a_host_path(
    live_broker_and_probe,
):
    results, _handler, _state, _lifecycle, repo, binding = live_broker_and_probe
    serialized = json.dumps(results)
    assert binding.token not in serialized
    assert binding.capability_id not in serialized
    assert repo.repo_root not in serialized
    assert "C:\\" not in serialized
