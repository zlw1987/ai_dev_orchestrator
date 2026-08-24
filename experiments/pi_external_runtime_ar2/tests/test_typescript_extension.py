"""TYPESCRIPT -- the extension is a serializer and a single-flight queue, and
nothing else.

These tests run the REAL extension sources under Node against a stub named-pipe
server implemented in the harness. No model, no network, no Pi process, and no
Python broker is involved.

The property under test is a NEGATIVE one, and it is the strongest argument for
B-rpc: AR1's ~200 lines of security-critical TypeScript (a comparison key, an
allowlist ``Map``, a ``realpathSync.native`` cross-check) are GONE. All path
authority moved into AIDO's accepted Python primitives.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import secrets
import sys
from pathlib import Path

import pytest

_EXTENSION_SOURCE = Path(__file__).resolve().parent.parent / "extension"
_HARNESS = Path(__file__).resolve().parent / "extension_harness.mjs"


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


@pytest.fixture(scope="module")
def harness_output(tmp_path_factory, node_executable) -> dict:
    """Run the real extension sources under Node once, and return its JSON report."""
    modules = _pi_node_modules()
    if modules is None:  # pragma: no cover - environment dependent
        pytest.skip("the installed Pi package's node_modules were not found")

    sandbox = tmp_path_factory.mktemp("ar2_extension")
    for name in ("ipc.ts", "tools.ts", "index.ts", "package.json"):
        shutil.copyfile(_EXTENSION_SOURCE / name, sandbox / name)
    pipe_name = "\\\\.\\pipe\\aido-ar2-tstest-" + secrets.token_hex(16)
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
                "experiment": "5F3A-AR2-offline-test",
                "pipeName": pipe_name,
                "capabilityId": "ar2-cap-test",
                "token": "offline-test-token-not-a-secret",
            },
            indent=2,
        )
        + ";\n",
        encoding="utf-8",
    )
    # A directory junction is enough for Node's resolver, needs no elevation, and
    # copies nothing.
    link = sandbox / "node_modules"
    junction = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), modules],
        capture_output=True,
        check=False,
    )
    if not link.exists():  # pragma: no cover - environment dependent
        pytest.skip(
            "a node_modules junction could not be created: "
            + junction.stderr.decode("utf-8", "replace").strip()
        )

    completed = subprocess.run(
        [node_executable, str(_HARNESS), str(sandbox), pipe_name],
        capture_output=True,
        cwd=str(sandbox),
        timeout=120,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", "replace")
    stderr = completed.stderr.decode("utf-8", "replace")
    if completed.returncode != 0:  # pragma: no cover - surfaced as a test failure
        pytest.fail(f"the Node harness exited {completed.returncode}\n{stderr}\n{stdout}")
    return json.loads(stdout)


# -- exactly two tools, with distinct names ------------------------------------


def test_exactly_aido_read_and_aido_edit_are_exported(harness_output):
    assert harness_output["exportedToolNames"] == ["aido_read", "aido_edit"]


def test_the_extension_registers_exactly_two_tools_and_one_sentinel(harness_output):
    assert harness_output["registeredToolNames"] == ["aido_read", "aido_edit"]
    assert harness_output["registeredToolCount"] == 2
    assert harness_output["registeredCommandNames"] == ["aido_ar2_broker_active"]
    assert harness_output["everyToolHasParameters"] is True
    assert harness_output["everyToolHasExecute"] is True


def test_the_tool_names_do_not_shadow_a_pi_builtin(harness_output):
    """Distinct names ARE the fail-closed control against a built-in fallback."""
    builtins = {"read", "edit", "write", "bash", "list", "glob", "grep", "multiedit"}
    assert not (set(harness_output["registeredToolNames"]) & builtins)


def test_the_configured_registry_allowlist_matches_the_registered_names(harness_output):
    """``--tools aido_read,aido_edit``: a failed load leaves ZERO matching tools."""
    from ar2.pi_config import TOOL_ALLOWLIST

    assert list(TOOL_ALLOWLIST) == harness_output["registeredToolNames"]
    assert set(TOOL_ALLOWLIST) == {"aido_read", "aido_edit"}


def test_no_builtin_tools_is_not_relied_on_as_the_security_property():
    from ar2.launch import build_pi_argv
    import inspect

    source = inspect.getsource(build_pi_argv)
    assert "--tools" in source
    assert "SECURITY CONTROL" in source
    assert "must not be relied on" in source


# -- the extension serializes verbatim, and authorizes nothing ------------------


def test_the_candidate_is_sent_verbatim_with_no_normalization(harness_output):
    for entry in harness_output["verbatimCandidates"]:
        assert entry["sent"] == entry["given"], (
            "the extension must send the Pi-resolved candidate verbatim as "
            "untrusted input; it performs no path parsing or normalization"
        )


def test_the_request_shape_is_exactly_the_designed_one(harness_output):
    assert harness_output["readFrameKeys"] == [
        "cap", "id", "op", "path_candidate", "tok", "v"
    ]
    assert harness_output["editFrameKeys"] == [
        "base_sha256", "cap", "id", "new_text", "old_text", "op", "path_candidate",
        "tok", "v",
    ]
    assert harness_output["protocolVersions"] == [1]
    assert harness_output["operationsSeen"] == ["edit_file", "read_file"]
    assert harness_output["distinctRequestIds"] == harness_output["totalFrames"]


def test_requests_are_single_flight(harness_output):
    """Pi may dispatch tool calls in parallel; the broker's pipe allows one client."""
    assert harness_output["maxConcurrentBrokerRequests"] == 1


def test_a_broker_refusal_becomes_a_tool_error_with_no_path(harness_output):
    assert harness_output["refusalThrew"] is True
    assert harness_output["refusalErrorName"] == "AidoBrokerRefusedError"
    message = harness_output["refusalMessage"]
    assert "refused" in message
    assert "REFUSE_ME" not in message
    assert "C:" not in message
    assert "\\" not in message


def test_a_successful_read_surfaces_the_sha256_the_model_must_echo(harness_output):
    text = harness_output["readResultText"]
    assert "sha256=" + "a" * 64 in text
    assert "Pass that sha256 as base_sha256" in text
    assert "stub content" in text


def test_a_malformed_broker_response_fails_closed(harness_output):
    """Optional hardening: a response missing the fields its own ``ok`` value
    requires (here ``ok: true`` with no ``result``) is rejected exactly like a
    non-JSON line or an uncorrelated id -- never resolved as if it were valid."""
    assert harness_output["malformedResponseThrew"] is True
    assert harness_output["malformedResponseErrorName"] in (
        "AidoBrokerUnavailableError",
        "AidoBrokerRefusedError",
    )


# -- static properties of the sources -----------------------------------------


def _source(name: str) -> str:
    return (_EXTENSION_SOURCE / name).read_text(encoding="utf-8")


def _code_only(name: str) -> str:
    """The source with block and line comments stripped, so prose cannot trip a check."""
    body = re.sub(r"/\*.*?\*/", "", _source(name), flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", body, flags=re.MULTILINE)


@pytest.mark.parametrize("name", ["ipc.ts", "tools.ts", "index.ts"])
def test_the_extension_contains_no_path_authority(name):
    code = _code_only(name)
    for banned in (
        "realpath",
        "realpathSync",
        "allowlist",
        "Allowlist",
        "comparisonKey",
        "path.resolve",
        "resolvePath",
        "normalize",
        "toLowerCase",
        "isAbsolute",
        "startsWith(",
        "commonpath",
        "node:path",
    ):
        assert banned not in code, f"{name} must contain no path authority ({banned})"


@pytest.mark.parametrize("name", ["ipc.ts", "tools.ts", "index.ts"])
def test_the_extension_runs_no_command_and_reads_no_file_itself(name):
    code = _code_only(name)
    for banned in (
        "child_process",
        "spawn(",
        "exec(",
        "execSync",
        "node:fs",
        "readFileSync",
        "writeFileSync",
        "pi.exec",
    ):
        assert banned not in code, f"{name} must not reach the filesystem or a shell ({banned})"


def test_the_only_node_builtin_the_extension_imports_is_net():
    imports = set()
    for name in ("ipc.ts", "tools.ts", "index.ts"):
        imports.update(re.findall(r'from "(node:[a-z/]+)"', _source(name)))
    assert imports == {"node:net"}


def test_ar1s_confinement_module_was_not_carried_forward():
    """AR1's security-critical TypeScript is DELETED in AR2, not ported."""
    assert not (_EXTENSION_SOURCE / "confinement.ts").exists()
    assert not (_EXTENSION_SOURCE / "confinement_harness.ts").exists()
    present = sorted(p.name for p in _EXTENSION_SOURCE.iterdir())
    assert present == ["index.ts", "ipc.ts", "package.json", "tools.ts"]


def test_there_is_no_third_tool_and_no_verify_or_shell_tool():
    code = "\n".join(_code_only(n) for n in ("ipc.ts", "tools.ts", "index.ts"))
    for banned in ("aido_write", "aido_list", "aido_search", "aido_verify", "aido_bash",
                   "aido_run", "aido_glob", "aido_grep", "aido_delete", "aido_create"):
        assert banned not in code
    assert code.count("registerTool") == 2


def test_the_wire_protocol_the_extension_speaks_matches_the_python_one():
    from ar2.wire import OP_EDIT_FILE, OP_READ_FILE, PROTOCOL_VERSION

    code = _code_only("ipc.ts") + _code_only("tools.ts")
    assert f"PROTOCOL_VERSION = {PROTOCOL_VERSION}" in code
    assert f'"{OP_READ_FILE}"' in code
    assert f'"{OP_EDIT_FILE}"' in code


def test_response_shape_is_validated_before_a_response_is_ever_resolved():
    """Structural: the shape check must run BEFORE entry.resolve(parsed), so a
    malformed response can never reach a waiting caller."""
    code = _source("ipc.ts")
    assert "isWellFormedBrokerResponse" in code
    guard_index = code.index("isWellFormedBrokerResponse(raw)")
    resolve_index = code.index("entry.resolve(parsed)")
    assert guard_index < resolve_index
