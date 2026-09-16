"""Shared fixtures for the 5F3B-HARNESS-CFG1 offline suite.

Rules this suite obeys, without exception (T-10 proves them mechanically):

- NO network, NO socket, NO DNS, NO model call, NO Pi model session, NO real
  credential or endpoint read, NO B300 contact. No API key is needed to run it.
- Every repository, every results root and every artifact lives under pytest's
  ``tmp_path`` or under a fresh ``ar2``-minted disposable root. The real package
  ``results/`` directory is never created, written to, or read.
- The one authorized use of the installed Pi package is T-3's offline request
  conformance check, which runs the installed JavaScript request builder under
  Node with network and DNS interception installed FIRST. It never launches a
  Pi model session.
- Real symlinks and (where the platform permits) real junctions are created,
  under test-controlled temporary directories only, because the defects those
  regressions close are specifically about what real ``resolve()`` does through
  a real redirect.

**Retargeting ``_CAPTURED_PACKAGE_DIR`` is test-harness memory manipulation,
and that is deliberate.** The design forbids any parameter, flag, environment
variable or config key that selects ``RESULTS_ROOT`` -- and it is right to. But
T-43 requires replacing the package directory's own leaf or an ancestor with a
real symlink, which cannot be done to the live repository, and every other
filesystem regression would otherwise write into the real package. Same-process
memory manipulation by the harness is explicitly outside this design's own
threat model (Sec. 16.3.4), so the suite rebinds the module global -- never
through any supported API, and never in production code.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_PACKAGE_DIR = _HERE.parent
_EXPERIMENTS_DIR = _PACKAGE_DIR.parent
_REPO_ROOT = _EXPERIMENTS_DIR.parent

for _path in (
    str(_REPO_ROOT / "src"),
    str(_EXPERIMENTS_DIR / "pi_external_runtime_ar2"),
    str(_EXPERIMENTS_DIR / "pi_implementer_qualification"),
    str(_EXPERIMENTS_DIR),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)


# ---------------------------------------------------------------------------
# Results-root retargeting
# ---------------------------------------------------------------------------


@pytest.fixture()
def cfg1_package_dir(tmp_path, monkeypatch):
    """A synthetic, canonical stand-in for the CFG1 package directory.

    Yields the directory. ``results/`` is deliberately ABSENT inside it, so the
    first ``establish_stage_output_authority`` call exercises Sec. 16.3.2's
    create-then-prove first-run path and later calls exercise the
    already-present path -- both through the identical sequence, as the design
    requires the offline fixture to do.
    """
    from pi_harness_cfg1 import stage_output

    package = tmp_path / "synthetic_cfg1_package"
    package.mkdir()
    canonical = str(package.resolve())
    monkeypatch.setattr(stage_output, "_CAPTURED_PACKAGE_DIR", canonical, raising=True)
    yield Path(canonical)


@pytest.fixture()
def results_root(cfg1_package_dir):
    """The lexical results root under the synthetic package directory."""
    return cfg1_package_dir / "results"


@pytest.fixture()
def make_authority(cfg1_package_dir):
    """Factory: mint a genuine, ACTIVE stage-output authority.

    Every authority it mints is retired when the test ends, so a leaked ACTIVE
    mint can never make a later test pass for the wrong reason.
    """
    from pi_harness_cfg1.stage_output import (
        _retire_stage_output_authority,
        establish_stage_output_authority,
    )

    minted = []

    def _make(stage_execution_id: str = "S1-X1", *, stage_id: str = "S1"):
        authority = establish_stage_output_authority(
            stage_id=stage_id, stage_execution_id=stage_execution_id
        )
        minted.append(authority)
        return authority

    yield _make
    for authority in minted:
        _retire_stage_output_authority(authority)


# ---------------------------------------------------------------------------
# Registry hygiene -- a leaked entry must never make a later test pass
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_leaked_cfg1_registry_state():
    """Assert the runner-managed registries are empty, THEN reset everything.

    The two stage-decision registries are wholly owned by the stage runner's
    own bounded cleanup, so a surviving entry after any test is a genuine leak
    -- and asserting before clearing is what makes that detectable. A fixture
    that only cleared would MASK exactly the defect T-136 and T-139 exist to
    prove absent.

    The clear still runs afterwards (in a ``finally``) so one leak fails one
    test instead of cascading through every later one. The remaining
    registries are reset without assertion: several tests legitimately mint
    without a stage run to retire them.
    """
    from pi_harness_cfg1 import config_issuance, run_workspace, stage_decision, stage_output

    try:
        yield
        assert stage_decision._STAGE_DECISION_SEALED == {}, (
            "a sealed-decision registry entry survived the test: the stage "
            "runner's bounded cleanup did not run, or did not cover it"
        )
        assert stage_decision._STAGE_TERMINAL_SEAL_HISTORY == set(), (
            "a terminal-seal history entry survived the test"
        )
    finally:
        stage_output._STAGE_OUTPUT_MINTED.clear()
        stage_decision._STAGE_DECISION_SEALED.clear()
        stage_decision._STAGE_TERMINAL_SEAL_HISTORY.clear()
        config_issuance._ISSUED.clear()
        run_workspace._MINTED.clear()
        run_workspace._CLAIMED.clear()


#: Every environment name this experiment's live phase would ever read. The
#: suite deletes all of them for the duration of EVERY test, so no regression
#: can read a real endpoint or credential even on a machine where one is set.
_LIVE_CONNECTION_ENV_NAMES = (
    "AIDO_LITELLM_BASE_URL",
    "PI_QUALIFICATION_B300_ROUTE_KEY",
    "AIDO_LITELLM_API_KEY",
    "AIDO_LITELLM_DEFAULT_MODEL",
    "AIDO_VLLM_BASE_URL",
    "AIDO_VLLM_API_KEY",
)


def _refuse_network(*_args, **_kwargs):  # pragma: no cover - a failure path
    raise AssertionError(
        "the CFG1 offline suite may never open a socket or perform DNS: "
        "no network, no model call, no B300 contact"
    )


@pytest.fixture(autouse=True)
def _offline_only(monkeypatch):
    """T-10, enforced MECHANICALLY rather than asserted about the suite.

    Two guarantees, for every test without exception:

    1. no real endpoint or credential is readable at all -- the names are
       removed from the environment, so a regression that tried would find
       nothing rather than silently succeeding on a configured machine;
    2. no socket is opened and no DNS lookup is performed from Python.

    T-3's authorized Node subprocess installs its OWN interception before any
    installed Pi module is imported, and is bounded by that harness, not this
    one -- a Python-level guard cannot reach inside another process.
    """
    import socket

    for name in _LIVE_CONNECTION_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setattr(socket, "socket", _refuse_network)
    monkeypatch.setattr(socket, "create_connection", _refuse_network)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse_network)
    monkeypatch.setattr(socket, "gethostbyname", _refuse_network, raising=False)
    yield


@pytest.fixture(autouse=True)
def _the_real_package_results_root_is_never_touched():
    """The suite itself must never write into the live package's ``results/``.

    Every regression retargets ``_CAPTURED_PACKAGE_DIR`` at a synthetic
    directory under ``tmp_path``. This guard is what makes a missed retarget --
    or a ``monkeypatch.undo()`` that silently reverts one mid-test -- a loud
    failure instead of a stray artifact in the repository.
    """
    real_results = _PACKAGE_DIR / "results"
    existed_before = real_results.exists()
    yield
    assert real_results.exists() is existed_before, (
        "a CFG1 offline test wrote into the REAL package results root at "
        f"{real_results}; every test must retarget _CAPTURED_PACKAGE_DIR"
    )


@pytest.fixture(scope="session")
def git_executable() -> str:
    """AIDO's OWN accepted Git resolution -- never a re-spelling of it.

    The exact STRING the production resolver returns, not merely the same
    target: on Windows ``realpath`` normalizes the extension's case, and an
    alias-tolerant comparison would let a different spelling reach a consumer
    that requires exact equality.
    """
    import shutil

    from ai_dev_orchestrator.workspace.git_adapter import (
        GitExecutableError,
        resolve_git_executable,
    )

    if not shutil.which("git"):  # pragma: no cover - environment dependent
        pytest.skip("git is not available")
    try:
        return resolve_git_executable(workspace_root=str(_PACKAGE_DIR))
    except GitExecutableError:  # pragma: no cover - environment dependent
        pytest.skip("git could not be resolved by AIDO's own resolver")


@pytest.fixture(autouse=True)
def _no_leaked_threads():
    """A green suite leaves no AR2-owned worker behind."""
    yield
    leaked = [
        thread.name
        for thread in threading.enumerate()
        if thread.name.startswith("ar2-") and thread.is_alive()
    ]
    assert not leaked, f"AR2-owned threads are still alive after the test: {leaked}"


# ---------------------------------------------------------------------------
# Filesystem-operation spies (T-22's discipline, reused throughout)
# ---------------------------------------------------------------------------


class FilesystemSpy:
    """Counts every mutating filesystem entry point the CFG1 code can reach."""

    def __init__(self) -> None:
        self.mkdir_calls: list[str] = []
        self.open_calls: list[str] = []
        self.lstat_calls: list[str] = []
        self.unlink_calls: list[str] = []
        self.rename_calls: list[str] = []
        self.truncate_calls: list[str] = []

    @property
    def total_mutations(self) -> int:
        return len(self.mkdir_calls) + len(self.open_calls) + len(self.unlink_calls) + len(
            self.rename_calls
        ) + len(self.truncate_calls)


@pytest.fixture()
def filesystem_spy(monkeypatch):
    """Wrap ``os.mkdir`` / ``Path.mkdir`` / ``open`` / ``os.lstat`` and friends.

    Used to prove "refused before any filesystem operation" MECHANICALLY,
    rather than by inspecting a refusal message and taking its word for it.
    """
    spy = FilesystemSpy()

    real_os_mkdir = os.mkdir
    real_path_mkdir = Path.mkdir
    real_open = open
    real_lstat = os.lstat
    real_unlink = os.unlink
    real_rename = os.rename
    real_truncate = os.truncate

    def _os_mkdir(path, *args, **kwargs):
        spy.mkdir_calls.append(str(path))
        return real_os_mkdir(path, *args, **kwargs)

    def _path_mkdir(self, *args, **kwargs):
        spy.mkdir_calls.append(str(self))
        return real_path_mkdir(self, *args, **kwargs)

    def _open(file, *args, **kwargs):
        spy.open_calls.append(str(file))
        return real_open(file, *args, **kwargs)

    def _lstat(path, *args, **kwargs):
        spy.lstat_calls.append(str(path))
        return real_lstat(path, *args, **kwargs)

    def _unlink(path, *args, **kwargs):
        spy.unlink_calls.append(str(path))
        return real_unlink(path, *args, **kwargs)

    def _rename(src, dst, *args, **kwargs):
        spy.rename_calls.append(f"{src}->{dst}")
        return real_rename(src, dst, *args, **kwargs)

    def _truncate(path, length, *args, **kwargs):
        spy.truncate_calls.append(str(path))
        return real_truncate(path, length, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", _os_mkdir)
    monkeypatch.setattr(Path, "mkdir", _path_mkdir)
    monkeypatch.setattr("builtins.open", _open)
    monkeypatch.setattr(os, "lstat", _lstat)
    monkeypatch.setattr(os, "unlink", _unlink)
    monkeypatch.setattr(os, "rename", _rename)
    monkeypatch.setattr(os, "truncate", _truncate)
    return spy


# ---------------------------------------------------------------------------
# Real-redirect helpers (platform-conditional, never silently skipped whole)
# ---------------------------------------------------------------------------


def make_directory_redirect(link_path: Path, target: Path) -> str:
    """Create a REAL redirect at ``link_path`` pointing at ``target``.

    Returns the mechanism actually used: ``"symlink"`` or ``"junction"``. Raises
    :class:`OSError` if neither is available (Windows without the required
    privilege, and no junction support), which callers turn into a
    platform-conditional skip of THAT VARIANT only -- never of the underlying
    invariant, which the POSIX symlink form always exercises where available.
    """
    try:
        os.symlink(str(target), str(link_path), target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError, AttributeError):
        pass
    if os.name != "nt":
        raise OSError("no directory-redirect mechanism is available on this platform")
    import subprocess

    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target)],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not os.path.exists(str(link_path)):
        raise OSError("junction creation was refused by the platform")
    return "junction"


def make_file_symlink(link_path: Path, target: Path) -> None:
    """Create a REAL file symlink, or raise for a platform-conditional skip."""
    os.symlink(str(target), str(link_path), target_is_directory=False)
