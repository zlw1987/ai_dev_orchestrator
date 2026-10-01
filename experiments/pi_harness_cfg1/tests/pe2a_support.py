"""Shared scaffolding for the PE-2a offline regressions. Test-only.

Every payload here is SYNTHETIC: JSON manifests and inert bytes written under
pytest ``tmp_path``, or an in-memory tree served by leaf doubles. Nothing here
runs Node, Pi or npm, reads the installed Pi, opens a socket, or reads a
credential. The synthetic ``node.exe`` is inert bytes that nothing executes.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
from collections import defaultdict
from pathlib import Path

from pi_harness_cfg1.pi_fs_leaves import (
    CLASSIFICATION_DIRECTORY,
    CLASSIFICATION_MISSING,
    CLASSIFICATION_OTHER,
    CLASSIFICATION_REGULAR_FILE,
    CLASSIFICATION_REPARSE_POINT,
    ENTRY_KIND_DIRECTORY,
    ENTRY_KIND_FILE,
    ENTRY_KIND_REPARSE,
    DirectoryListing,
    NoFollowObservation,
    PayloadFileRead,
)
from pi_harness_cfg1.pi_manifest import build_manifest_bundle, bundle_manifest_paths
from pi_harness_cfg1.pi_payload import (
    PI_SC1_PATHS,
    PayloadLeaves,
    inventory_from_entries,
    observe_payload,
)
from pi_harness_cfg1.pi_profile_floor import compute_profile_facts

PI_AI = "@earendil-works/pi-ai"
PI_AGENT_CORE = "@earendil-works/pi-agent-core"
ROOT_NAME = "@earendil-works/pi-coding-agent"

SYNTHETIC_NODE_BYTES = b"MZ synthetic inert node.exe bytes -- never executed\n"
SYNTHETIC_PI_CMD_BYTES = b"@rem synthetic pi.cmd -- never read, never executed\n"


def manifest_bytes(document: dict, *, indent: int | None = 2) -> bytes:
    """Deterministic JSON bytes for one synthetic manifest (key order kept)."""
    return (json.dumps(document, indent=indent) + "\n").encode("utf-8")


def root_manifest(**overrides) -> dict:
    document = {
        "name": ROOT_NAME,
        "version": "1.0.0",
        "type": "module",
        "bin": {"pi": "dist/cli.js"},
        "dependencies": {
            PI_AI: "^1.0.0",
            PI_AGENT_CORE: "^1.0.0",
            "left-pad": "1.3.0",
            "@scope/util": "2.0.0",
        },
        "optionalDependencies": {"fsevents": "2.3.3"},
    }
    document.update(overrides)
    return document


def pi_ai_manifest(**overrides) -> dict:
    document = {"name": PI_AI, "version": "1.0.0", "dependencies": {"zod": "3.0.0"}}
    document.update(overrides)
    return document


def pi_agent_core_manifest(**overrides) -> dict:
    document = {"name": PI_AGENT_CORE, "version": "1.0.0", "peerDependencies": {PI_AI: "^1.0.0"}}
    document.update(overrides)
    return document


def synthetic_payload_files() -> tuple[dict[str, bytes], tuple[str, ...]]:
    """``(files, empty_dirs)`` for a synthetic, approvable, exposure-free payload."""
    files: dict[str, bytes] = {}
    for relative in PI_SC1_PATHS:
        files[relative] = b"synthetic pe2a seam file: " + relative.encode("ascii") + b"\n"
    files["package.json"] = manifest_bytes(root_manifest())
    files["node_modules/@earendil-works/pi-ai/package.json"] = manifest_bytes(pi_ai_manifest())
    files["node_modules/@earendil-works/pi-agent-core/package.json"] = manifest_bytes(
        pi_agent_core_manifest()
    )
    files.update(
        {
            "dist/cli/setup.js": b"export const setup = 1;\n",
            "dist/other.js": b"export const other = 2;\n",
            "dist/native/addon.node": bytes(range(256)),
            "dist/wasm/module.wasm": b"\x00asm\x01\x00\x00\x00",
            "dist/cli.js.map": b'{"version":3}',
            "README.md": b"# synthetic\n",
            "LICENSE": b"synthetic licence\n",
            ".npmignore": b"*.log\n",
            "node_modules/.bin/pi": b"#!/bin/sh\n",
            "node_modules/left-pad/package.json": manifest_bytes({"name": "left-pad", "version": "1.3.0"}),
            "node_modules/left-pad/index.js": b"module.exports = 1;\n",
            "node_modules/left-pad/node_modules/nested-dep/package.json": manifest_bytes(
                {"name": "nested-dep", "version": "0.1.0"}
            ),
            "node_modules/left-pad/node_modules/nested-dep/data.bin": b"\x01\x02\x03",
            "node_modules/@scope/util/package.json": manifest_bytes({"name": "@scope/util", "version": "2.0.0"}),
            "node_modules/@scope/util/lib/x.cjs": b"module.exports = 'x';\n",
            "node_modules/fsevents/package.json": manifest_bytes({"name": "fsevents", "version": "2.3.3"}),
            "node_modules/zod/package.json": manifest_bytes({"name": "zod", "version": "3.0.0"}),
            "node_modules/zod/index.mjs": b"export default 1;\n",
            # A nested fixture manifest that is NOT a package root: bound by
            # bytes only, never parsed, so its malformed JSON is irrelevant.
            "dist/fixtures/broken/package.json": b"{ not json",
        }
    )
    return files, ("empty_dir", "dist/empty_nested/deeper")


def write_tree(root: Path, files: dict[str, bytes], empty_dirs=()) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for relative, data in files.items():
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for relative in empty_dirs:
        root.joinpath(*relative.split("/")).mkdir(parents=True, exist_ok=True)


def expected_entries(files: dict[str, bytes], empty_dirs=()) -> tuple:
    """The inventory entries the spec says a payload with these files has."""
    dirs: set[str] = set()
    for relative in list(files) + list(empty_dirs):
        parts = relative.split("/")
        limit = len(parts) - 1 if relative in files else len(parts)
        for length in range(1, limit + 1):
            dirs.add("/".join(parts[:length]))
    entries = [("dir", path) for path in dirs]
    entries += [
        ("file", path, hashlib.sha256(data).hexdigest(), len(data)) for path, data in files.items()
    ]
    entries.sort(key=lambda entry: entry[1])
    return tuple(entries)


def facts_for(files: dict[str, bytes], empty_dirs=()):
    """Profile facts computed purely from a file mapping (no filesystem)."""
    inventory = inventory_from_entries(expected_entries(files, empty_dirs))
    bundle = build_manifest_bundle(
        inventory, {path: files[path] for path in bundle_manifest_paths(inventory)}
    )
    return compute_profile_facts(inventory, bundle)


# ---------------------------------------------------------------------------
# An in-memory tree served through the GENUINE leaf contracts (doubles)
# ---------------------------------------------------------------------------


class FakeTree:
    """In-memory payload tree. Node kinds: dir, file, reparse, other.

    ``order`` permutes enumeration order (``"forward"``, ``"reverse"``) so
    order-independence can be proven. Failure injection sets: ``enum_fail``,
    ``read_fail``, ``unstable``, ``vanish_on_read``, ``kind_swap_on_read``.
    ``log`` records every leaf call as ``(kind, path)``.
    """

    def __init__(self, root: str = "C:\\fake\\npm\\node_modules\\@earendil-works\\pi-coding-agent") -> None:
        self.root = root
        self.nodes: dict[str, tuple] = {root: ("dir",)}
        self.children: dict[str, list[str]] = defaultdict(list)
        self.order = "forward"
        self.enum_fail: set[str] = set()
        self.read_fail: set[str] = set()
        self.unstable: set[str] = set()
        self.vanish_on_read: set[str] = set()
        self.kind_swap_on_read: set[str] = set()
        self.log: list[tuple[str, str]] = []
        self.hook = None

    def abs(self, relative: str) -> str:
        return self.root if relative == "" else ntpath.join(self.root, *relative.split("/"))

    def _add(self, relative: str, node: tuple) -> None:
        parts = relative.split("/")
        parent = ""
        for part in parts[:-1]:
            current = part if parent == "" else parent + "/" + part
            if self.abs(current) not in self.nodes:
                self._add(current, ("dir",))
            parent = current
        absolute = self.abs(relative)
        if absolute not in self.nodes:
            self.children[self.abs(parent)].append(parts[-1])
        self.nodes[absolute] = node

    def add_dir(self, relative: str) -> None:
        self._add(relative, ("dir",))

    def add_file(self, relative: str, data: bytes) -> None:
        self._add(relative, ("file", data))

    def add_reparse(self, relative: str, *, directory: bool) -> None:
        self._add(relative, ("reparse", directory))

    def add_other(self, relative: str) -> None:
        self._add(relative, ("other",))

    def add_raw_name(self, parent_relative: str, name: str, node: tuple) -> None:
        """Insert a child under a RAW name (possibly grammar-invalid)."""
        parent = self.abs(parent_relative)
        self.children[parent].append(name)
        self.nodes[parent + "\\" + name] = node

    def populate(self, files: dict[str, bytes], empty_dirs=()) -> FakeTree:
        for relative, data in files.items():
            self.add_file(relative, data)
        for relative in empty_dirs:
            self.add_dir(relative)
        return self

    # -- leaf doubles -----------------------------------------------------

    def enumerate_directory(self, path: str, max_entries: int) -> DirectoryListing:
        self.log.append(("enumerate", path))
        if self.hook is not None:
            self.hook("enumerate", path)
        node = self.nodes.get(path)
        if node is None:
            return DirectoryListing(CLASSIFICATION_MISSING, False, False, None)
        if node[0] == "reparse":
            return DirectoryListing(CLASSIFICATION_REPARSE_POINT, False, False, None)
        if node[0] == "file":
            return DirectoryListing(CLASSIFICATION_REGULAR_FILE, False, False, None)
        if node[0] == "other":
            return DirectoryListing(CLASSIFICATION_OTHER, False, False, None)
        if path in self.enum_fail:
            return DirectoryListing(CLASSIFICATION_DIRECTORY, False, False, None)
        names = list(self.children.get(path, ()))
        if self.order == "reverse":
            names.reverse()
        entries = []
        for name in names:
            child = self.nodes.get(path + "\\" + name) or self.nodes[ntpath.join(path, name)]
            if child[0] == "reparse":
                kind = ENTRY_KIND_REPARSE
            elif child[0] == "dir":
                kind = ENTRY_KIND_DIRECTORY
            else:
                kind = ENTRY_KIND_FILE
            entries.append((name, kind))
            if len(entries) > max_entries:
                return DirectoryListing(CLASSIFICATION_DIRECTORY, False, True, None)
        return DirectoryListing(CLASSIFICATION_DIRECTORY, True, False, tuple(entries))

    def read_file(self, path: str, max_bytes: int) -> PayloadFileRead:
        self.log.append(("read", path))
        if self.hook is not None:
            self.hook("read", path)
        if path in self.vanish_on_read:
            return PayloadFileRead(CLASSIFICATION_MISSING, False, False, None, None, None)
        if path in self.kind_swap_on_read:
            return PayloadFileRead(CLASSIFICATION_DIRECTORY, False, False, None, None, None)
        if path in self.read_fail:
            return PayloadFileRead(CLASSIFICATION_OTHER, False, False, None, None, None)
        node = self.nodes.get(path)
        if node is None:
            return PayloadFileRead(CLASSIFICATION_MISSING, False, False, None, None, None)
        if node[0] == "reparse":
            return PayloadFileRead(CLASSIFICATION_REPARSE_POINT, False, False, None, None, None)
        if node[0] == "dir":
            return PayloadFileRead(CLASSIFICATION_DIRECTORY, False, False, None, None, None)
        if node[0] == "other":
            return PayloadFileRead(CLASSIFICATION_OTHER, False, False, None, None, None)
        data = node[1]
        if len(data) > max_bytes:
            return PayloadFileRead(CLASSIFICATION_REGULAR_FILE, False, False, None, None, None)
        if path in self.unstable:
            return PayloadFileRead(CLASSIFICATION_REGULAR_FILE, True, False, None, None, None)
        return PayloadFileRead(
            CLASSIFICATION_REGULAR_FILE, True, True, len(data), hashlib.sha256(data).hexdigest(), None
        )

    def read_bytes(self, path: str, max_bytes: int) -> PayloadFileRead:
        result = self.read_file(path, max_bytes)
        if result.stable and result.within_bound:
            return PayloadFileRead(
                result.classification, True, True, result.size, result.sha256, self.nodes[path][1]
            )
        return result

    def leaves(self) -> PayloadLeaves:
        return PayloadLeaves(enumerate_directory=self.enumerate_directory, read_file=self.read_file)

    def observe(self):
        return observe_payload(self.root, leaves=self.leaves())


class RecordingInspect:
    """A no-follow inspect double over a ``{path: classification}`` map.

    Paths absent from the map are ``missing``. Records every call; ``forbid``
    is a predicate marking calls the test must never see.
    """

    def __init__(self, classifications: dict[str, str] | None = None, *, forbid=None, raise_on=None) -> None:
        self.classifications = dict(classifications or {})
        self.calls: list[str] = []
        self.forbidden_calls: list[str] = []
        self.forbid = forbid
        self.raise_on = raise_on or set()

    def __call__(self, path: str) -> NoFollowObservation:
        self.calls.append(path)
        if self.forbid is not None and self.forbid(path):
            self.forbidden_calls.append(path)
        if path in self.raise_on:
            raise OSError("injected observation failure")
        classification = self.classifications.get(path, CLASSIFICATION_MISSING)
        identity = (1, abs(hash(path)) % (2**60)) if classification in (
            CLASSIFICATION_DIRECTORY,
            CLASSIFICATION_REGULAR_FILE,
        ) else None
        return NoFollowObservation(classification, identity)


# ---------------------------------------------------------------------------
# An on-disk discovery world (synthetic node.exe + pi.cmd + payload)
# ---------------------------------------------------------------------------


class DiscoveryWorld:
    def __init__(self, base: Path, files: dict[str, bytes] | None = None, empty_dirs=None) -> None:
        if files is None:
            files, default_dirs = synthetic_payload_files()
            empty_dirs = default_dirs if empty_dirs is None else empty_dirs
        self.base = base
        self.node_dir = base / "nodejs"
        self.npm_dir = base / "npm"
        self.payload_root = self.npm_dir / "node_modules" / "@earendil-works" / "pi-coding-agent"
        self.node_dir.mkdir(parents=True)
        self.npm_dir.mkdir(parents=True)
        (self.node_dir / "node.exe").write_bytes(SYNTHETIC_NODE_BYTES)
        (self.npm_dir / "pi.cmd").write_bytes(SYNTHETIC_PI_CMD_BYTES)
        self.files = dict(files)
        self.empty_dirs = tuple(empty_dirs or ())
        write_tree(self.payload_root, self.files, self.empty_dirs)

    @property
    def path_value(self) -> str:
        return f"{self.node_dir};{self.npm_dir}"

    @property
    def payload_root_str(self) -> str:
        return str(self.payload_root)


def staging_listing(staging: Path) -> list[str]:
    return sorted(os.listdir(staging)) if staging.exists() else []
