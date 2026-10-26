"""DL-4B S3 — authority observations of the clone, without Git (FD-18).

The authority identity runs no Git (C-10). It observes the clone with plain,
reparse-refusing reads through :class:`~.authority_files.AuthorityFiles`, and
nothing else it learns about the workspace is a fact:

```text
HEAD           .git/HEAD must be exactly one object id and a line feed (detached).
               A symbolic ref or anything else refuses. No ref is resolved.
.git control   (path, size, SHA-256) of HEAD, config, index, packed-refs, shallow,
               commondir, objects/info/alternates and every file under refs/, hooks/
               and info/. A modules/ directory refuses (no submodules).
working tree   (path, size, SHA-256) of every regular file outside the top-level
               .git, bounded by fixed entry and byte caps. A reparse point, a file
               with more than one link, a nested .git, a top-level .gitmodules, an
               entry Win32 cannot address exactly, a case-only duplicate, an
               object whose handle reports another path, or an over-cap tree refuses.
```

Every file is read once, from one handle that denies write sharing, and
hashed from those bytes. An observation is the canonical JSON **manifest** of
those facts. It carries no time and no kind, so it is content-addressed; its
row records when and why it was taken.

:func:`classify_write` decides what a write did from two observations alone
(M0 before, M1 after). An execution claim never enters it.

What an observation cannot see, stated: alternate data streams, file
attributes other than the reparse flag, and anything that changes after the
read (D-13). It is a moment, not a lock.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import re
from dataclasses import dataclass
from typing import Literal

from ai_dev_orchestrator.control_plane.integration_records import AUTHORITY_OBSERVATION_SCHEMA_VERSION
from ai_dev_orchestrator.control_plane.models import canonical_json_bytes
from ai_dev_orchestrator.integration.authority_files import AuthorityFiles
from ai_dev_orchestrator.integration.boundary_facts import DirectoryEntry, ObjectFacts

#: Fixed bounds (code constants, never configuration; recorded in AUTH-PILOT).
MAX_TREE_ENTRIES = 50_000
MAX_TREE_BYTES = 1024 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_GIT_CONTROL_ENTRIES = 10_000
MAX_GIT_CONTROL_BYTES = 256 * 1024 * 1024
MAX_HEAD_BYTES = 256
MAX_MANIFEST_BYTES = 64 * 1024 * 1024

_GIT_CONTROL_FILES = ("HEAD", "config", "index", "packed-refs", "shallow", "commondir",
                      "objects/info/alternates")
_GIT_CONTROL_DIRECTORIES = ("refs", "hooks", "info")
_DETACHED_HEAD = re.compile(rb"([0-9a-f]{40}|[0-9a-f]{64})\n")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{base}{n}" for base in ("COM", "LPT") for n in "123456789¹²³"}
)
_FORBIDDEN_CHARACTERS = frozenset('<>:"/\\|?*') | {chr(c) for c in range(32)}

Effect = Literal["as_approved", "no_change", "indeterminate"]
Entry = tuple[str, int, str]


class ObservationError(Exception):
    """A clone could not be observed as FD-18 requires. ``category`` names why."""

    def __init__(self, category: str, detail: str) -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"observation_refused:{category}: {detail}")


@dataclass(frozen=True)
class Observation:
    """One authority observation, and its canonical manifest bytes."""

    head_oid: str
    git_control: tuple[Entry, ...]
    git_control_sha256: str
    tree: tuple[Entry, ...] | None
    target_path: str | None
    target_sha256: str | None
    target_size: int | None
    manifest: bytes
    manifest_sha256: str

    @property
    def entry_count(self) -> int:
        return len(self.tree) if self.tree is not None else len(self.git_control)


def _key(path: str) -> str:
    return ntpath.normcase(path)


def _checked_name(entry: object, what: str) -> DirectoryEntry:
    if (
        type(entry) is not DirectoryEntry
        or type(entry.name) is not str
        or type(entry.is_directory) is not bool
        or type(entry.is_reparse_point) is not bool
    ):
        raise ObservationError("fact_unavailable", f"the listing of {what} is malformed.")
    name = entry.name
    if (
        name in ("", ".", "..")
        or any(c in _FORBIDDEN_CHARACTERS for c in name)
        or name[-1] in ". "
        or name.split(".")[0].rstrip(" ").upper() in _RESERVED_NAMES
    ):
        raise ObservationError("ambiguous_path", f"{what} holds an entry Win32 cannot address exactly.")
    return entry


class _Walk:
    def __init__(self, files: AuthorityFiles, *, max_entries: int, max_bytes: int) -> None:
        self.files = files
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.entries = 0
        self.bytes = 0

    def call(self, what: str, method, *args):
        try:
            return method(*args)
        except ObservationError:
            raise
        except Exception as exc:  # noqa: BLE001 - an unreadable fact is no observation
            code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
            raise ObservationError(
                "fact_unavailable", f"{what} could not be read ({type(exc).__name__}{f' {code}' if code else ''})."
            ) from None

    def count(self, what: str) -> None:
        self.entries += 1
        if self.entries > self.max_entries:
            raise ObservationError("over_cap", f"{what} has more entries than an observation may hold.")

    @staticmethod
    def checked_facts(value: object, path: str, what: str, *, directory: bool) -> ObjectFacts:
        if (
            type(value) is not ObjectFacts
            or not (value.final_path is None or type(value.final_path) is str)
            or type(value.is_directory) is not bool
            or type(value.is_reparse_point) is not bool
            or type(value.link_count) is not int
        ):
            raise ObservationError("fact_unavailable", f"the facts of {what} are malformed.")
        if value.is_reparse_point:
            raise ObservationError("reparse_point", f"{what} is a reparse point.")
        if value.is_directory != directory:
            raise ObservationError("object_kind", f"{what} is not a {'directory' if directory else 'file'}.")
        if not directory and value.link_count != 1:
            raise ObservationError("hard_link", f"{what} has more than one link.")
        if value.final_path is None or _key(value.final_path) != _key(path):
            raise ObservationError("ambiguous_path", f"{what} is not at the path it was opened by.")
        return value

    def directory(self, path: str, what: str) -> None:
        value = self.call(f"the facts of {what}", self.files.object_facts, path)
        if value is None:
            raise ObservationError("missing", f"{what} does not exist.")
        self.checked_facts(value, path, what, directory=True)

    def file(self, path: str, what: str) -> tuple[int, str] | None:
        result = self.call(f"{what}", self.files.read_file, path, MAX_FILE_BYTES)
        if result is None:
            return None
        if type(result) is not tuple or len(result) != 2 or type(result[1]) is not bytes:
            raise ObservationError("fact_unavailable", f"the read of {what} is malformed.")
        facts, data = result
        self.checked_facts(facts, path, what, directory=False)
        if len(data) > MAX_FILE_BYTES:
            raise ObservationError("over_cap", f"{what} is larger than an observation may read.")
        self.bytes += len(data)
        if self.bytes > self.max_bytes:
            raise ObservationError("over_cap", "the observed files exceed the observation byte cap.")
        return len(data), hashlib.sha256(data).hexdigest()

    def listing(self, path: str, what: str) -> list[DirectoryEntry]:
        entries = self.call(f"the listing of {what}", self.files.list_directory, path)
        if type(entries) is not tuple:
            raise ObservationError("fact_unavailable", f"the listing of {what} is malformed.")
        checked = [_checked_name(entry, what) for entry in entries]
        folded = [entry.name.casefold() for entry in checked]
        if len(set(folded)) != len(folded):
            raise ObservationError("ambiguous_path", f"{what} holds two entries that differ only in case.")
        return sorted(checked, key=lambda entry: entry.name)

    def tree(self, root: str, prefix: str, what: str, *, top_skip: str | None) -> list[Entry]:
        """Every regular file below ``root``, as ``prefix``-relative POSIX paths."""
        found: list[Entry] = []
        stack = [(root, prefix)]
        while stack:
            directory, relative = stack.pop()
            for entry in self.listing(directory, f"{what}/{relative}" if relative else what):
                name = entry.name
                child_relative = f"{relative}/{name}" if relative else name
                label = f"{what}/{child_relative}"
                if directory == root and top_skip is not None and name.casefold() == top_skip:
                    continue
                if name.casefold() == ".git":
                    raise ObservationError("nested_repository", f"{label} is a nested Git directory.")
                if entry.is_reparse_point:
                    raise ObservationError("reparse_point", f"{label} is a reparse point.")
                self.count(what)
                child = ntpath.join(directory, name)
                if entry.is_directory:
                    self.directory(child, label)
                    stack.append((child, child_relative))
                    continue
                read = self.file(child, label)
                if read is None:
                    raise ObservationError("fact_unavailable", f"{label} vanished while being observed.")
                found.append((child_relative, read[0], read[1]))
        return sorted(found)


def _entries_sha256(entries: tuple[Entry, ...]) -> str:
    return hashlib.sha256(canonical_json_bytes({
        "schema_version": AUTHORITY_OBSERVATION_SCHEMA_VERSION,
        "git_control": [list(entry) for entry in entries],
    })).hexdigest()


def _observe_git(walk: _Walk, clone: str) -> tuple[str, tuple[Entry, ...]]:
    git = ntpath.join(clone, ".git")
    walk.directory(git, "clone/.git")
    if walk.call("clone/.git/modules", walk.files.object_facts, ntpath.join(git, "modules")) is not None:
        raise ObservationError("submodules_present", "clone/.git/modules exists; the Alpha has no submodules.")
    head_read = walk.call("clone/.git/HEAD", walk.files.read_file, ntpath.join(git, "HEAD"), MAX_HEAD_BYTES)
    if head_read is None:
        raise ObservationError("missing", "clone/.git/HEAD does not exist.")
    facts, head = head_read
    walk.checked_facts(facts, ntpath.join(git, "HEAD"), "clone/.git/HEAD", directory=False)
    match = _DETACHED_HEAD.fullmatch(head) if type(head) is bytes else None
    if match is None:
        raise ObservationError(
            "head_not_detached", "clone/.git/HEAD is not exactly one object id and a line feed."
        )
    walk.count("clone/.git")
    entries: list[Entry] = [("HEAD", len(head), hashlib.sha256(head).hexdigest())]
    for relative in _GIT_CONTROL_FILES[1:]:
        path = ntpath.join(git, *relative.split("/"))
        read = walk.file(path, f"clone/.git/{relative}")
        if read is not None:
            walk.count("clone/.git")
            entries.append((relative, read[0], read[1]))
    for relative in _GIT_CONTROL_DIRECTORIES:
        path = ntpath.join(git, relative)
        if walk.call(f"clone/.git/{relative}", walk.files.object_facts, path) is None:
            continue
        walk.directory(path, f"clone/.git/{relative}")
        entries.extend(walk.tree(path, relative, f"clone/.git", top_skip=None))
    return match.group(1).decode("ascii"), tuple(sorted(entries))


def _manifest(head_oid: str, git_control: tuple[Entry, ...], tree: tuple[Entry, ...] | None,
              target_path: str | None) -> Observation:
    git_digest = _entries_sha256(git_control)
    target = None
    if target_path is not None:
        assert tree is not None
        matches = [entry for entry in tree if entry[0] == target_path]
        if len(matches) != 1:
            raise ObservationError("target_missing", "the write scope's target is not a regular file in the clone.")
        target = {"path": target_path, "size": matches[0][1], "sha256": matches[0][2]}
    manifest = canonical_json_bytes({
        "schema_version": AUTHORITY_OBSERVATION_SCHEMA_VERSION,
        "head_oid": head_oid,
        "git_control": [list(entry) for entry in git_control],
        "git_control_sha256": git_digest,
        "tree": None if tree is None else [list(entry) for entry in tree],
        "target": target,
    })
    if len(manifest) > MAX_MANIFEST_BYTES:
        raise ObservationError("over_cap", "the observation manifest exceeds its size bound.")
    return Observation(
        head_oid=head_oid,
        git_control=git_control,
        git_control_sha256=git_digest,
        tree=tree,
        target_path=target_path,
        target_sha256=None if target is None else target["sha256"],
        target_size=None if target is None else target["size"],
        manifest=manifest,
        manifest_sha256=hashlib.sha256(manifest).hexdigest(),
    )


def observe_git_control(files: AuthorityFiles, clone: str) -> Observation:
    """HEAD and the ``.git`` control digest only (the activation-time record)."""
    walk = _Walk(files, max_entries=MAX_GIT_CONTROL_ENTRIES, max_bytes=MAX_GIT_CONTROL_BYTES)
    walk.directory(clone, "clone")
    head, git_control = _observe_git(walk, clone)
    return _manifest(head, git_control, None, None)


def observe_workspace(files: AuthorityFiles, clone: str, target_path: str) -> Observation:
    """A full FD-18 observation (M0, M1): HEAD, ``.git`` control and the
    working-tree manifest, with ``target_path`` (repo-relative POSIX) required
    to be one of its regular files."""
    git_walk = _Walk(files, max_entries=MAX_GIT_CONTROL_ENTRIES, max_bytes=MAX_GIT_CONTROL_BYTES)
    git_walk.directory(clone, "clone")
    head, git_control = _observe_git(git_walk, clone)
    walk = _Walk(files, max_entries=MAX_TREE_ENTRIES, max_bytes=MAX_TREE_BYTES)
    for entry in walk.listing(clone, "clone"):
        if entry.name.casefold() == ".gitmodules":
            raise ObservationError("submodules_present", "the clone has a .gitmodules file.")
    tree = tuple(walk.tree(clone, "", "clone", top_skip=".git"))
    return _manifest(head, git_control, tree, target_path)


def _entry_list(value: object, what: str) -> tuple[Entry, ...]:
    if not isinstance(value, list):
        raise ObservationError("manifest_invalid", f"the manifest's {what} is not a list.")
    entries = []
    for item in value:
        if (
            not isinstance(item, list) or len(item) != 3 or type(item[0]) is not str
            or type(item[1]) is not int or item[1] < 0 or type(item[2]) is not str
            or _HEX64.fullmatch(item[2]) is None
        ):
            raise ObservationError("manifest_invalid", f"the manifest's {what} holds a malformed entry.")
        entries.append((item[0], item[1], item[2]))
    if entries != sorted(entries) or len({entry[0] for entry in entries}) != len(entries):
        raise ObservationError("manifest_invalid", f"the manifest's {what} is not canonical.")
    return tuple(entries)


def parse_manifest(data: bytes) -> Observation:
    """Re-derive an observation from its stored manifest bytes, or refuse.

    Every derived digest is recomputed and the bytes must be exactly the
    canonical encoding, so a stored manifest is consistent or it is nothing.
    """
    if type(data) is not bytes or len(data) > MAX_MANIFEST_BYTES:
        raise ObservationError("manifest_invalid", "the manifest is not bounded bytes.")
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ObservationError("manifest_invalid", "the manifest is not JSON.") from None
    if not isinstance(document, dict) or set(document) != {
        "schema_version", "head_oid", "git_control", "git_control_sha256", "tree", "target",
    } or document["schema_version"] != AUTHORITY_OBSERVATION_SCHEMA_VERSION:
        raise ObservationError("manifest_invalid", "the manifest is not an authority-observation.v1.")
    head = document["head_oid"]
    if type(head) is not str or _OID.fullmatch(head) is None:
        raise ObservationError("manifest_invalid", "the manifest's HEAD is not an object id.")
    git_control = _entry_list(document["git_control"], "git control")
    tree = None if document["tree"] is None else _entry_list(document["tree"], "tree")
    target = document["target"]
    if target is not None and (not isinstance(target, dict) or set(target) != {"path", "size", "sha256"}
                               or type(target["path"]) is not str):
        raise ObservationError("manifest_invalid", "the manifest's target is malformed.")
    if (target is None) != (tree is None):
        raise ObservationError("manifest_invalid", "the manifest's target and tree disagree.")
    observation = _manifest(head, git_control, tree, None if target is None else target["path"])
    if observation.manifest != data or observation.git_control_sha256 != document["git_control_sha256"]:
        raise ObservationError("manifest_invalid", "the manifest is not its own canonical encoding.")
    return observation


def classify_write(m0: Observation, m1: Observation, *, target_path: str, pre_image_sha256: str,
                   post_image_sha256: str) -> Effect:
    """What the write did, from M0 and M1 alone (FD-18, §5.5 step 6).

    ``as_approved``: HEAD and ``.git`` unchanged, and the tree differs in
    exactly the target, which went from the pre-image to the post-image.
    ``no_change``: HEAD, ``.git`` and the tree are identical. Anything else,
    including any other difference, is ``indeterminate``.
    """
    if m0.tree is None or m1.tree is None:
        return "indeterminate"
    if (m0.head_oid, m0.git_control_sha256) != (m1.head_oid, m1.git_control_sha256):
        return "indeterminate"
    before = {path: (size, digest) for path, size, digest in m0.tree}
    after = {path: (size, digest) for path, size, digest in m1.tree}
    if before == after:
        return "no_change"
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    if (
        changed == {target_path}
        and target_path in before and target_path in after
        and before[target_path][1] == pre_image_sha256
        and after[target_path][1] == post_image_sha256
    ):
        return "as_approved"
    return "indeterminate"
