"""Shared fixtures for the AR1 offline test suite.

Rules this suite obeys, without exception:

- NO network. NO socket. NO model call. NO API key needed.
- Every repository is synthetic, created under pytest ``tmp_path``.
- The "Pi process" is a synthetic JSONL-emitting Python script written under
  ``tmp_path``. The real Pi binary is never launched by a test.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_EXPERIMENT_DIR = _HERE.parent
_REPO_SRC = _EXPERIMENT_DIR.parents[1] / "src"

for path in (str(_REPO_SRC), str(_EXPERIMENT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


FAKE_PI_SOURCE = '''\
"""Synthetic stand-in for a Pi RPC process. Test-only. Emits JSONL on stdout."""
import json
import sys
import time

script = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.stdout.buffer
err = sys.stderr.buffer


def emit_chunks(chunks):
    for chunk in chunks:
        out.write(chunk.encode("utf-8"))
        out.flush()
        time.sleep(script.get("chunk_delay_seconds", 0.0))


emit_chunks(script.get("startup_chunks", []))
if script.get("stderr_text"):
    err.write(script["stderr_text"].encode("utf-8"))
    err.flush()
if script.get("exit_immediately"):
    sys.exit(script.get("exit_code", 0))

responses = script.get("responses", {})
while True:
    line = sys.stdin.buffer.readline()
    if not line:
        if script.get("ignore_stdin_close"):
            time.sleep(script.get("hang_seconds", 120))
            continue
        sys.exit(script.get("exit_code", 0))
    try:
        command = json.loads(line.decode("utf-8").rstrip("\\r\\n"))
    except Exception:
        out.write(b'{"type":"response","command":"parse","success":false}\\n')
        out.flush()
        continue
    kind = command.get("type")
    time.sleep(script.get("response_delay_seconds", 0.0))
    entry = responses.get(kind)
    if entry is not None:
        payload = {
            "type": "response",
            "command": kind,
            "success": entry.get("success", True),
        }
        if command.get("id") is not None and not script.get("drop_response_id"):
            payload["id"] = command["id"]
        if "data" in entry:
            payload["data"] = entry["data"]
        out.write((json.dumps(payload) + "\\n").encode("utf-8"))
        out.flush()
    if kind == "prompt":
        time.sleep(script.get("settle_delay_seconds", 0.0))
        emit_chunks(script.get("prompt_chunks", []))
'''


@pytest.fixture()
def fake_pi(tmp_path: Path):
    """Return a factory that builds argv for a synthetic Pi process."""
    script_path = tmp_path / "fake_pi.py"
    script_path.write_text(FAKE_PI_SOURCE, encoding="utf-8")
    counter = {"n": 0}

    def _build(script: dict) -> tuple[str, ...]:
        counter["n"] += 1
        config_path = tmp_path / f"fake_pi_script_{counter['n']}.json"
        config_path.write_text(json.dumps(script), encoding="utf-8")
        return (sys.executable, str(script_path), str(config_path))

    return _build


@pytest.fixture()
def minimal_env() -> dict[str, str]:
    """A minimal explicit environment for the synthetic process. Never os.environ."""
    names = ("SystemRoot", "SystemDrive", "windir", "ComSpec", "PATHEXT", "TEMP", "TMP", "PATH")
    return {name: os.environ[name] for name in names if name in os.environ}


@pytest.fixture(scope="session")
def git_executable() -> str:
    found = shutil.which("git")
    if not found:  # pragma: no cover - environment dependent
        pytest.skip("git is not available")
    return os.path.realpath(found)


@pytest.fixture(scope="session")
def node_executable() -> str:
    found = shutil.which("node")
    if not found:  # pragma: no cover - environment dependent
        pytest.skip("node is not available")
    return os.path.realpath(found)


@pytest.fixture(scope="session")
def pi_dist_index() -> str:
    """Absolute path to the installed Pi 0.84.2 dist/index.js, or skip."""
    shim = shutil.which("pi")
    if not shim:  # pragma: no cover - environment dependent
        pytest.skip("pi is not installed")
    npm_bin = os.path.dirname(os.path.realpath(shim))
    candidate = os.path.realpath(
        os.path.join(
            npm_bin, "node_modules", "@earendil-works", "pi-coding-agent", "dist", "index.js"
        )
    )
    if not os.path.isfile(candidate):  # pragma: no cover - environment dependent
        pytest.skip("the installed Pi package layout was not found")
    return candidate


def build_synthetic_repo(root: Path, git_exe: str) -> tuple[str, str]:
    """Create a tiny synthetic Git repo under ``root``. Returns (repo_root, HEAD)."""
    from ar1.fixture import create_synthetic_repository

    fixture = create_synthetic_repository(str(root), git_executable=git_exe)
    return fixture.repo_root, fixture.head_before


def run_git(git_exe: str, args: list[str], cwd: str) -> str:
    """Test-only mutation helper for building adversarial repository states."""
    completed = subprocess.run(
        [git_exe, "-c", "user.name=T", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
    )
    return completed.stdout.decode("utf-8", "replace")
