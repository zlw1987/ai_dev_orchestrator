"""DL-4A — the AIDO-owned state root and target-workspace containment.

Two directories matter to a real integration, and DL-4A keeps them apart
mechanically (roadmap §13.3):

```text
AIDO STATE ROOT         AIDO-owned. Holds the authority store and write-once
                        evidence. Created empty by AIDO, never inside a Git
                        working tree, never inside or around a target workspace.
TARGET WORKSPACE        human-authorized, per plan activation. DL-4A records its
                        identity and re-proves it on every read; nothing here
                        writes, cleans or deletes anything in it.
```

Rules, all refusals and none of them repairs:

- **No path confusion.** A path must be absolute, contain no ``.`` or ``..``
  component, exist, and have no symlink, junction or other reparse point in any
  component. Its canonical form (``realpath``) is what is recorded and compared,
  case-insensitively where the platform is.
- **Disjointness.** The state root and a target workspace may not be equal, and
  neither may contain the other, by canonical path or by directory identity.
- **Identity, not just a name.** A target workspace is recorded as its canonical
  path *and* its directory identity ``(st_dev, st_ino)``. A directory renamed
  away and replaced, or swapped for a junction, is refused on the next read.
- **Write-once evidence.** Evidence is staged with an exclusive create, fsynced,
  and published by a hard link that cannot overwrite. An existing name is never
  replaced; a differing one is untrusted.
- **No unauthorized cleanup.** The only file AIDO ever removes is the staging
  file the same call created, and only after re-proving it is still that file
  (same identity, not a reparse point, still inside the staging directory). A
  substituted file is left in place and reported. There is no API that deletes
  evidence, the store, or anything in a target workspace.

What this does not provide: protection against another process racing between
an identity check and the following system call (no handle-relative OS API is
used), against the operator account, or against in-process code that calls
``os`` directly. Containment is checked; it is not a sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from os import PathLike
from pathlib import PurePath

from pydantic import StrictInt

from ai_dev_orchestrator.control_plane.models import _Strict, canonical_json_bytes, is_hex32

STATE_ROOT_SCHEMA_VERSION = "aido-state-root.v1"
STATE_ROOT_MARKER = "aido-state-root.json"
STORE_FILE_NAME = "control-plane.sqlite3"
VERIFICATION_EVIDENCE_PARTS = ("evidence", "verification")
STAGING_PARTS = ("staging",)
# Everything that may exist at the top of a state root. SQLite's rollback
# journal is transient, but survives a crash, so it is allowed.
_ROOT_ENTRIES = frozenset(
    {STATE_ROOT_MARKER, STORE_FILE_NAME, f"{STORE_FILE_NAME}-journal", "evidence", "staging"}
)
_MAX_MARKER_BYTES = 4_096
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

# Only create() and open() hold this, so a root object always passed their checks.
_ROOT_TOKEN = object()


class ContainmentError(Exception):
    """A path is not where AIDO's authority requires it to be. Nothing was
    written or removed. Messages never echo file contents."""


def _is_reparse(path: str) -> bool:
    info = os.lstat(path)
    return (
        os.path.islink(path)
        or os.path.isjunction(path)
        or bool(getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)
    )


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(left) == os.path.normcase(right)


def _within(child: str, parent: str) -> bool:
    """``child`` is ``parent`` or below it, by canonical path."""
    child_key, parent_key = os.path.normcase(child), os.path.normcase(parent)
    try:
        return os.path.commonpath([child_key, parent_key]) == parent_key
    except ValueError:  # different drives
        return False


def canonical_directory(path: str | PathLike[str], name: str) -> str:
    """The canonical form of an existing directory, or a refusal.

    Refuses a relative path, a ``.`` or ``..`` component, a missing component
    and a reparse point (symlink, junction, mount point) anywhere along it.
    """
    try:
        raw = os.fspath(path)
    except TypeError as exc:
        raise ContainmentError(f"the {name} must be a path.") from exc
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise ContainmentError(f"the {name} must be a non-empty text path.")
    if not os.path.isabs(raw):
        raise ContainmentError(f"the {name} must be absolute.")
    if any(part in (".", "..") for part in raw.replace("\\", "/").split("/")):
        raise ContainmentError(f"the {name} must not contain '.' or '..' components.")
    parts = PurePath(raw).parts
    current = parts[0]
    for part in parts[1:]:
        current = os.path.join(current, part)
        try:
            if _is_reparse(current):
                raise ContainmentError(
                    f"the {name} passes through a symlink, junction or other reparse point."
                )
        except FileNotFoundError as exc:
            raise ContainmentError(f"the {name} does not exist.") from exc
    if not os.path.isdir(current):
        raise ContainmentError(f"the {name} is not a directory.")
    return os.path.realpath(current, strict=True)


def require_outside_git_worktrees(path: str, name: str) -> None:
    """Refuse ``path`` if it, or any ancestor, holds a ``.git`` entry."""
    current = path
    while True:
        if os.path.lexists(os.path.join(current, ".git")):
            raise ContainmentError(f"the {name} is inside a Git working tree.")
        parent = os.path.dirname(current)
        if parent == current:
            return
        current = parent


def require_disjoint(state_root: str, target_workspace: str) -> None:
    """Refuse a target workspace that is, contains, or is inside the state root."""
    if _within(target_workspace, state_root) or _within(state_root, target_workspace):
        raise ContainmentError(
            "the target workspace and the AIDO state root overlap; each must be outside the other."
        )
    root_info, target_info = os.stat(state_root), os.stat(target_workspace)
    if (root_info.st_dev, root_info.st_ino) == (target_info.st_dev, target_info.st_ino):
        raise ContainmentError("the target workspace is the AIDO state root.")


class WorkspaceIdentity(_Strict):
    """A target workspace: its canonical path and its directory identity."""

    path: str
    device: StrictInt
    file_id: StrictInt

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical_json_bytes({
            "path": os.path.normcase(self.path),
            "device": self.device,
            "file_id": self.file_id,
        })).hexdigest()


def _read_regular_file(path: str, limit: int) -> bytes:
    try:
        if _is_reparse(path) or not os.path.isfile(path):
            raise ContainmentError("an AIDO file is not a regular file.")
        with open(path, "rb") as handle:
            data = handle.read(limit + 1)
    except FileNotFoundError as exc:
        raise ContainmentError("an AIDO file is missing.") from exc
    if len(data) > limit:
        raise ContainmentError("an AIDO file exceeds its size bound.")
    return data


class AidoStateRoot:
    """An AIDO-owned state root. Construct with :meth:`create` or :meth:`open`.

    Layout::

        <root>/aido-state-root.json            marker (root id), created once
        <root>/control-plane.sqlite3           the DL-4A authority store
        <root>/evidence/verification/<sha>.json   write-once verification-result.v1
        <root>/staging/                        AIDO's own transient files
    """

    def __init__(self, path: str, root_id: str, *, _token: object = None) -> None:
        if _token is not _ROOT_TOKEN:
            raise ContainmentError(
                "a state root is created only by AidoStateRoot.create() or AidoStateRoot.open()."
            )
        self._path = path
        self._root_id = root_id

    @property
    def path(self) -> str:
        return self._path

    @property
    def root_id(self) -> str:
        return self._root_id

    @property
    def store_path(self) -> str:
        return os.path.join(self._path, STORE_FILE_NAME)

    # --- lifecycle -------------------------------------------------------

    @classmethod
    def create(cls, path: str | PathLike[str]) -> AidoStateRoot:
        """Make an existing, **empty** directory an AIDO state root.

        AIDO adopts nothing it did not create, so a non-empty directory is
        refused rather than taken over (and later "cleaned").
        """
        root = canonical_directory(path, "state root")
        require_outside_git_worktrees(root, "state root")
        if os.listdir(root):
            raise ContainmentError("a new state root must be an empty directory.")
        marker = canonical_json_bytes(
            {"schema_version": STATE_ROOT_SCHEMA_VERSION, "root_id": uuid.uuid4().hex}
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        fd = os.open(os.path.join(root, STATE_ROOT_MARKER), flags, 0o600)
        try:
            os.write(fd, marker)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.mkdir(os.path.join(root, "evidence"))
        os.mkdir(os.path.join(root, *VERIFICATION_EVIDENCE_PARTS))
        os.mkdir(os.path.join(root, *STAGING_PARTS))
        return cls.open(root)

    @classmethod
    def open(cls, path: str | PathLike[str]) -> AidoStateRoot:
        """Open an existing state root, re-proving its location and layout."""
        root = canonical_directory(path, "state root")
        require_outside_git_worktrees(root, "state root")
        root_id = cls._read_marker(root)
        instance = cls(root, root_id, _token=_ROOT_TOKEN)
        instance.verify()
        return instance

    @staticmethod
    def _read_marker(root: str) -> str:
        data = _read_regular_file(os.path.join(root, STATE_ROOT_MARKER), _MAX_MARKER_BYTES)
        try:
            marker = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ContainmentError("the state root marker is not JSON.") from exc
        if (
            not isinstance(marker, dict)
            or set(marker) != {"schema_version", "root_id"}
            or marker["schema_version"] != STATE_ROOT_SCHEMA_VERSION
            or not is_hex32(marker["root_id"])
        ):
            raise ContainmentError("the directory is not an AIDO state root.")
        return marker["root_id"]

    def verify(self) -> None:
        """Re-prove the root's location, identity and layout. Called before every
        store open and every evidence or workspace operation."""
        if not _same_path(canonical_directory(self._path, "state root"), self._path):
            raise ContainmentError("the state root is no longer at its canonical path.")
        require_outside_git_worktrees(self._path, "state root")
        if self._read_marker(self._path) != self._root_id:
            raise ContainmentError("the state root marker changed.")
        entries = set(os.listdir(self._path))
        if not entries <= _ROOT_ENTRIES:
            raise ContainmentError("the state root holds entries AIDO did not create.")
        self.contained_directory(VERIFICATION_EVIDENCE_PARTS)
        self.contained_directory(STAGING_PARTS)
        if os.path.lexists(self.store_path) and (
            _is_reparse(self.store_path) or not os.path.isfile(self.store_path)
        ):
            raise ContainmentError("the state root's store is not a regular file.")

    def contained_directory(self, parts: tuple[str, ...]) -> str:
        """``<root>/<parts>``, re-proven to be real directories inside the root."""
        if _is_reparse(self._path):
            raise ContainmentError("the state root is a reparse point.")
        path = self._path
        for part in parts:
            path = os.path.join(path, part)
            try:
                if _is_reparse(path) or not os.path.isdir(path):
                    raise ContainmentError("a state root directory was replaced.")
            except FileNotFoundError as exc:
                raise ContainmentError("a state root directory is missing.") from exc
        if not _same_path(os.path.realpath(path, strict=True), path):
            raise ContainmentError("a state root directory resolves outside the state root.")
        return path

    # --- target workspace ------------------------------------------------

    def authorize_target_workspace(self, path: str | PathLike[str]) -> WorkspaceIdentity:
        """The identity of a target workspace that may be authorized, or a refusal."""
        self.verify()
        canonical = canonical_directory(path, "target workspace")
        require_disjoint(self._path, canonical)
        info = os.stat(canonical)
        return WorkspaceIdentity(path=canonical, device=info.st_dev, file_id=info.st_ino)

    def reverify_target_workspace(self, path: str, identity_sha256: str) -> WorkspaceIdentity:
        """Re-prove that ``path`` is still exactly the workspace a human authorized."""
        identity = self.authorize_target_workspace(path)
        if not _same_path(identity.path, path) or identity.sha256 != identity_sha256:
            raise ContainmentError(
                "the target workspace is no longer the directory a human authorized."
            )
        return identity

    # --- write-once evidence ---------------------------------------------

    def write_verification_evidence(self, sha256: str, data: bytes) -> None:
        """Publish ``data`` as ``evidence/verification/<sha256>.json``, write-once."""
        if hashlib.sha256(data).hexdigest() != sha256:
            raise ContainmentError("evidence bytes do not hash to their name.")
        self.verify()
        _write_once(self, VERIFICATION_EVIDENCE_PARTS, f"{sha256}.json", data)

    def read_verification_evidence(self, sha256: str, limit: int) -> bytes:
        """The evidence bytes named ``sha256``, re-hashed, or a refusal."""
        if not isinstance(sha256, str) or len(sha256) != 64 or not all(
            c in "0123456789abcdef" for c in sha256
        ):
            raise ContainmentError("an evidence name must be a SHA-256 digest.")
        directory = self.contained_directory(VERIFICATION_EVIDENCE_PARTS)
        data = _read_regular_file(os.path.join(directory, f"{sha256}.json"), limit)
        if hashlib.sha256(data).hexdigest() != sha256:
            raise ContainmentError("stored evidence no longer hashes to its identity.")
        return data


def _write_once(root: AidoStateRoot, parts: tuple[str, ...], name: str, data: bytes) -> None:
    directory = root.contained_directory(parts)
    staging = root.contained_directory(STAGING_PARTS)
    final = os.path.join(directory, name)
    temp = os.path.join(staging, f"{uuid.uuid4().hex}.partial")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(temp, flags, 0o600)
    identity: tuple[int, int] | None = None
    try:
        try:
            info = os.fstat(fd)
            identity = (info.st_dev, info.st_ino)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.link(temp, final)
        except FileExistsError:
            if _read_regular_file(final, len(data)) != data:
                raise ContainmentError(
                    "a different file already holds this evidence name; it is never overwritten."
                ) from None
    finally:
        _remove_own_staged_file(root, temp, identity)


def _remove_own_staged_file(
    root: AidoStateRoot, temp: str, identity: tuple[int, int] | None
) -> None:
    """Remove the staging file this call created, and nothing else."""
    if not _same_path(root.contained_directory(STAGING_PARTS), os.path.dirname(temp)):
        raise ContainmentError("the staging directory moved; nothing was removed.")
    try:
        info = os.lstat(temp)
    except FileNotFoundError:
        return
    if identity is None or (info.st_dev, info.st_ino) != identity or _is_reparse(temp):
        raise ContainmentError(
            "the staged file is no longer the one AIDO created; AIDO removes only its own "
            "file, so it was left in place."
        )
    os.unlink(temp)
