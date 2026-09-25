"""Shared scaffolding for the FU1 (R6 + AMEND1) offline regressions. Test-only.

Nothing here runs Node, Pi or JavaScript, opens a socket, or reads a
credential. The synthetic Pi tree's ``node.exe`` is an inert byte string: it is
never executed, and the one test that hands it to the REAL supervisor (AMEND1
Test AD(i)) does so precisely to prove that ``CreateProcess`` REFUSES it.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from cfg1_doubles import (
    SyntheticPiTree,
    build_doubled_ports,
    build_synthetic_pi_tree,
    use_test_owned_pin_table,
)

from pi_harness_cfg1 import pi_fs_leaves
from pi_harness_cfg1 import win_config_authority as win
from pi_harness_cfg1.pi_identity import PiProofLeaves, genuine_pi_proof_leaves
from pi_harness_cfg1.run_contract import Cfg1RunAdmission
from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position


def make_admission(run_ordinal: int = 1, *, run_id: str = "f" * 32) -> Cfg1RunAdmission:
    block, position = _schedule_block_position("S1", run_ordinal)
    return Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=run_ordinal,
        arm_id=_schedule_arm_for("S1", run_ordinal),
        block=block,
        position=position,
        run_id=run_id,
    )


def make_pi_world(tmp_path: Path, monkeypatch, name: str = "pi_world") -> SyntheticPiTree:
    """A fresh synthetic Pi tree under ``tmp_path`` with its OWN pin table."""
    tree = build_synthetic_pi_tree(str(tmp_path / name))
    use_test_owned_pin_table(monkeypatch, tree.pin_table)
    return tree


def replace_same_bytes(path: str) -> None:
    """Replace ``path`` with a NEW file record holding the IDENTICAL bytes."""
    data = Path(path).read_bytes()
    os.unlink(path)
    Path(path).write_bytes(data)


def replace_directory_with_identical_copy(path: str) -> None:
    """Move the directory aside and put a byte-identical copy at its path."""
    aside = path + ".moved_aside"
    os.rename(path, aside)
    shutil.copytree(aside, path)


def file_identity(path: str) -> tuple[int, int]:
    stat_result = os.stat(path)
    return stat_result.st_dev, stat_result.st_ino


# ---------------------------------------------------------------------------
# Access-recording ambient mapping (Test F)
# ---------------------------------------------------------------------------


class RecordingMapping(Mapping):
    """A mapping that records EVERY way it is read."""

    def __init__(self, values: dict) -> None:
        self._values = dict(values)
        self.lookups: list[str] = []
        self.iterations = 0

    def __getitem__(self, key):
        self.lookups.append(key)
        return self._values[key]

    def get(self, key, default=None):
        self.lookups.append(key)
        return self._values.get(key, default)

    def __contains__(self, key):
        self.lookups.append(key)
        return key in self._values

    def __iter__(self):
        self.iterations += 1
        return iter(self._values)

    def __len__(self):
        self.iterations += 1
        return len(self._values)

    def keys(self):
        self.iterations += 1
        return self._values.keys()

    def items(self):
        self.iterations += 1
        return self._values.items()

    def values(self):
        self.iterations += 1
        return self._values.values()


#: Decoys for every name R6 Sec. 6 / AMEND1 Test F excludes.
AMBIENT_DECOYS = {
    "SystemRoot": "C:\\decoy-systemroot",
    "NODE_OPTIONS": "--require C:\\decoy\\evil.js",
    "NODE_PATH": "C:\\decoy\\node_path",
    "PI_QUALIFICATION_B300_ROUTE_KEY": "decoy-route-key-7a1c",
    "AIDO_LITELLM_API_KEY": "decoy-litellm-key-7a1c",
    "AIDO_LITELLM_BASE_URL": "https://decoy.invalid/v1",
    "AWS_SECRET_ACCESS_KEY": "decoy-aws-secret-7a1c",
    "USERPROFILE": "C:\\decoy-profile",
    "TEMP": "C:\\decoy-temp",
}


# ---------------------------------------------------------------------------
# Leaf recording (call-order proofs)
# ---------------------------------------------------------------------------


class LeafRecorder:
    """Wraps the GENUINE leaves, recording every call in one ordered log.

    ``hook`` (optional) is called as ``hook(kind, path, log)`` BEFORE the
    genuine leaf runs; it may mutate the filesystem or raise.
    """

    def __init__(self, *, hook=None, log: list | None = None) -> None:
        self.log: list[tuple[str, str]] = [] if log is None else log
        self.hook = hook

    def _inspect(self, path):
        if self.hook is not None:
            self.hook("inspect", path, self.log)
        self.log.append(("inspect", path))
        return pi_fs_leaves.inspect_no_follow(path)

    def _digest(self, path, max_bytes):
        if self.hook is not None:
            self.hook("digest", path, self.log)
        self.log.append(("digest", path))
        return pi_fs_leaves.read_bounded_digest(path, max_bytes)

    def leaves(self, checkout_root: str | None = None) -> PiProofLeaves:
        genuine = genuine_pi_proof_leaves()
        return PiProofLeaves(
            inspect=self._inspect,
            read_digest=self._digest,
            checkout_root=checkout_root or genuine.checkout_root,
        )

    def digests(self) -> list[str]:
        return [path for kind, path in self.log if kind == "digest"]


def install_recording_genuine_leaves(monkeypatch, recorder: LeafRecorder) -> None:
    """Make ``genuine_pi_proof_leaves()`` itself return recording wrappers.

    Used for the GATE, which accepts no leaf parameter: the genuine binding
    looks its two effects up on :mod:`pi_fs_leaves` at call time.
    """
    real_inspect = pi_fs_leaves.inspect_no_follow
    real_digest = pi_fs_leaves.read_bounded_digest

    def _inspect(path):
        if recorder.hook is not None:
            recorder.hook("inspect", path, recorder.log)
        recorder.log.append(("inspect", path))
        return real_inspect(path)

    def _digest(path, max_bytes):
        if recorder.hook is not None:
            recorder.hook("digest", path, recorder.log)
        recorder.log.append(("digest", path))
        return real_digest(path, max_bytes)

    monkeypatch.setattr(pi_fs_leaves, "inspect_no_follow", _inspect)
    monkeypatch.setattr(pi_fs_leaves, "read_bounded_digest", _digest)


# ---------------------------------------------------------------------------
# Process-creation tripwire (Tests AA, AB, AF)
# ---------------------------------------------------------------------------


class _TripwireFired(Exception):
    """Raised by a non-delegating tripwire so no process is ever created."""


class ProcessTripwire:
    """Records every process-creation entry point, labelled with a phase.

    ``delegate=False``: every creation attempt is recorded and REFUSED (for
    the gate and for L1, which must create nothing). ``delegate=True``: the
    attempt is recorded and then performed (for a run that legitimately
    creates Git children after L2, and for Test AD(i)/AF's L14).
    """

    def __init__(self, monkeypatch, *, delegate: bool) -> None:
        import _winapi
        import multiprocessing
        import subprocess

        self.events: list[tuple[str, str, str]] = []
        self.phase = "armed"
        self.delegate = delegate
        real_create = _winapi.CreateProcess
        real_popen = subprocess.Popen

        def _create(application, command_line, *args, **kwargs):
            self.events.append((self.phase, "CreateProcess", str(command_line)))
            if not self.delegate:
                raise _TripwireFired("CreateProcess")
            return real_create(application, command_line, *args, **kwargs)

        class _Popen(real_popen):
            def __init__(inner, args, *a, **k):  # noqa: N805
                self.events.append((self.phase, "Popen", repr(args)))
                if not self.delegate:
                    raise _TripwireFired("Popen")
                super().__init__(args, *a, **k)

        def _refuse(name):
            def _call(*_a, **_k):
                self.events.append((self.phase, name, ""))
                raise _TripwireFired(name)

            return _call

        monkeypatch.setattr(_winapi, "CreateProcess", _create)
        monkeypatch.setattr(subprocess, "Popen", _Popen)
        monkeypatch.setattr(os, "system", _refuse("os.system"))
        monkeypatch.setattr(os, "startfile", _refuse("os.startfile"), raising=False)
        for name in dir(os):
            if name.startswith("spawn") or name.startswith("exec"):
                monkeypatch.setattr(os, name, _refuse(f"os.{name}"))
        monkeypatch.setattr(multiprocessing.Process, "start", _refuse("Process.start"))

    def in_phase(self, phase: str) -> list:
        return [event for event in self.events if event[0] == phase]

    @property
    def count(self) -> int:
        return len(self.events)


def fu1_ports(
    git_executable: str,
    tree: SyntheticPiTree,
    *,
    leaves: PiProofLeaves | None = None,
    ambient=None,
    overrides: dict | None = None,
):
    """The doubled executor ports, pointed at THIS test's synthetic Pi tree."""
    merged = dict(overrides or {})
    merged["ambient_environ"] = (
        ambient
        if ambient is not None
        else {"SystemRoot": "C:\\Windows", "PATH": tree.path_value}
    )
    merged["pi_proof_leaves"] = leaves if leaves is not None else genuine_pi_proof_leaves()
    return build_doubled_ports(git_executable=git_executable, overrides=merged)


class HandleLog:
    """Records scrub, disposition and close calls on writer children, in order.

    AMEND2 (Y6): a SCRUB (truncate -> flush -> ``EndOfFile == 0``) through the
    creating handle is what discharges an endpoint/token obligation; a
    disposition is namespace cleanup and is recorded only to prove it is never
    an input. ``retained_close_fails`` makes every retained-handle close a
    GENUINE failed close: the handle stays open, the leak is counted as
    ``"retained"``, and :meth:`release_leaks` closes it for real.
    """

    def __init__(self, monkeypatch) -> None:
        self.calls: list[tuple[str, str]] = []
        self.leaked: list[int] = []
        self.leaked_handles: list[int] = []
        self._monkeypatch = monkeypatch
        real_dispose = win.dispose_child_by_handle
        real_close = win.close_child_quietly
        real_scrub = win.scrub_child_through_creating_handle
        real_close_handle = win._close_handle
        self.dispose_result: dict[str, object] = {}
        self.scrub_result: dict[str, object] = {}
        self.close_fails: set[str] = set()
        self.retained_close_fails = False

        def _dispose(child):
            name = win.child_name(child)
            self.calls.append(("dispose", name))
            forced = self.dispose_result.get(name)
            if forced == "raise":
                raise RuntimeError("an injected disposition raise")
            if forced is False:
                return False
            return real_dispose(child)

        def _scrub(child):
            name = win.child_name(child)
            self.calls.append(("scrub", name))
            forced = self.scrub_result.get(name)
            if forced == "raise":
                raise RuntimeError("an injected scrub raise")
            if forced is False:
                return False  # the content is NOT scrubbed
            return real_scrub(child)

        def _close(child):
            try:
                name = win.child_name(child)
            except win.Cfg1DirectoryAuthorityError:
                name = "?"
            self.calls.append(("close", name))
            if name in self.close_fails:
                # A GENUINE failed close: the descriptor stays open (the delete
                # stays pending), the registry entry retires, and the leak is
                # counted -- exactly what a real close failure leaves behind.
                entry = win._CHILDREN.pop(child.nonce)
                self.leaked.append(entry[0])
                win._CLOSE_FAILURES.append("child")
                return False
            return real_close(child)

        def _close_handle(handle, kind):
            if kind == "retained" and self.retained_close_fails:
                self.leaked_handles.append(handle)
                return False
            return real_close_handle(handle, kind)

        monkeypatch.setattr(win, "dispose_child_by_handle", _dispose)
        monkeypatch.setattr(win, "scrub_child_through_creating_handle", _scrub)
        monkeypatch.setattr(win, "close_child_quietly", _close)
        monkeypatch.setattr(win, "_close_handle", _close_handle)

    def release_leaks(self) -> None:
        for fd in self.leaked:
            os.close(fd)
        self.leaked.clear()
        for handle in self.leaked_handles:
            win._K32.CloseHandle(handle)
        self.leaked_handles.clear()
        while "child" in win._CLOSE_FAILURES:
            win._CLOSE_FAILURES.remove("child")
        while "retained" in win._CLOSE_FAILURES:
            win._CLOSE_FAILURES.remove("retained")

    def scrubbed_before_closed(self, name: str) -> bool:
        return self.calls.index(("scrub", name)) < self.calls.index(("close", name))

    def disposed(self) -> bool:
        return any(op == "dispose" for op, _ in self.calls)
