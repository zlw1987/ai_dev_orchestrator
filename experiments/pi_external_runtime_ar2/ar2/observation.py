"""AIDO's INDEPENDENT post-run observation of the disposable repository.

The rule this module exists to enforce (AR0 section 10.1):

    Pi is not an authority for repository truth. Every Pi event is
    observational. A fact becomes authoritative only when AIDO derives it
    independently, from the repository, using AIDO-owned primitives.

Everything here goes through the ACCEPTED production primitives -- the fixed
Git operation set, its ordering, and the canonical path guard. **No new fixed
Git operation is added** (AR0-FU1 section 12 answered AR0's U-10: zero
widening), and there is deliberately no whole-repository diff. ``diff_one_path``
runs only when the observed state is exactly the one expected shape; every other
shape classifies the workspace untrusted and stops.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from ai_dev_orchestrator.workspace.canonical import (
    CanonicalPathError,
    canonicalize_existing_path_under_workspace,
)
from ai_dev_orchestrator.workspace.git_adapter import (
    GitAdapterError,
    find_unsupported_config_keys,
    ordered_preflight_operations,
    parse_config_name_only,
    parse_ls_files_stage,
    parse_ls_files_verbose,
    parse_status_porcelain,
    run_fixed_git_operation,
    status_record_path,
)

# Classification outcomes (AR0 section 10.5).
CLEAN_EXPECTED = "clean_expected"
DIRTY_BENIGN = "dirty_benign"
NO_CHANGE_OBSERVED = "no_change_observed"
UNEXPECTED_CHANGE = "unexpected_change"
UNEXPECTED_UNTRACKED = "unexpected_untracked"
HEAD_MOVED = "head_moved"
INDEX_DIRTY = "index_dirty"
CONFIG_POISONED = "config_poisoned"
INDEX_SHAPE_UNTRUSTED = "index_shape_untrusted"
IDENTITY_LOST = "identity_lost"
OBSERVATION_FAILED = "observation_failed"

TRUSTED_CLASSES: frozenset[str] = frozenset({CLEAN_EXPECTED, DIRTY_BENIGN})

# Index modes that make Git's answers stop meaning what they usually mean.
_GITLINK_MODE = "160000"
_SYMLINK_MODE = "120000"

# ls-files -v tags for assume-unchanged (lowercase) and skip-worktree.
_SKIP_WORKTREE_TAG = "S"


class ObservationError(Exception):
    """The repository state could not be established. Fails closed."""


@dataclass
class ScopedConfigKeys:
    """Config key names by scope. NAMES only -- no configuration value is read."""

    by_scope: dict[str, list[str]] = field(default_factory=dict)

    def unsupported_by_scope(self) -> dict[str, list[str]]:
        return {
            scope: list(find_unsupported_config_keys(tuple(keys)))
            for scope, keys in self.by_scope.items()
        }

    def all_keys(self) -> tuple[str, ...]:
        return tuple(key for keys in self.by_scope.values() for key in keys)


def parse_config_scoped_with_scope(stdout: str) -> ScopedConfigKeys:
    """Scope-aware parse of ``config --list --show-scope --name-only -z``.

    The production parser deliberately collapses scopes, because for a *writer*
    an execution-capable key is unsupported wherever it lives. The experiment
    needs the scope in order to tell "planted in this repository during the run"
    apart from "present on this host before the experiment existed" -- and that
    distinction is evidence, not leniency: a key that appears only after the run
    is treated as poisoning regardless of scope.

    This adds no Git operation. It re-parses output the accepted fixed operation
    already produced.
    """
    known_scopes = {"system", "global", "local", "worktree", "command", "submodule"}
    fields = stdout.split("\0")
    result = ScopedConfigKeys()
    index = 0
    while index < len(fields):
        scope = fields[index]
        if not scope:
            index += 1
            continue
        if scope not in known_scopes:
            raise ObservationError(
                "observation error: an unrecognized Git configuration scope was "
                "reported. Refused rather than guessed at."
            )
        if index + 1 >= len(fields):
            raise ObservationError(
                "observation error: a Git configuration scope was reported with no key."
            )
        key = fields[index + 1]
        index += 2
        if scope == "command":
            continue
        if key:
            result.by_scope.setdefault(scope, []).append(key)
    return result


@dataclass
class StatusEntry:
    """One parsed porcelain-v1 record."""

    raw: str
    index_code: str
    worktree_code: str
    path: str

    @property
    def is_untracked(self) -> bool:
        return self.index_code == "?" and self.worktree_code == "?"

    @property
    def is_staged(self) -> bool:
        return not self.is_untracked and self.index_code not in (" ", "?", "!")

    @property
    def is_unmerged(self) -> bool:
        return "U" in (self.index_code, self.worktree_code) or (
            self.index_code == self.worktree_code and self.index_code in ("A", "D")
        )

    @property
    def is_unstaged_modification(self) -> bool:
        return self.index_code == " " and self.worktree_code == "M"


@dataclass
class ObservationSnapshot:
    """One complete, independent observation. Authoritative by construction."""

    top_level: str
    head: str
    config_keys_local: tuple[str, ...]
    scoped_config: ScopedConfigKeys
    index_entries: tuple[Any, ...]
    ls_files_verbose: tuple[tuple[str, str], ...]
    status_entries: tuple[StatusEntry, ...]
    observed_at_monotonic: float

    def status_raw_records(self) -> tuple[str, ...]:
        return tuple(entry.raw for entry in self.status_entries)


def observe_repository(*, git_executable: str, workspace_root: str) -> ObservationSnapshot:
    """Run the accepted preflight ordering and return what Git actually said.

    The ordering is the production ``ordered_preflight_operations()`` ordering,
    for the production reason: prove the repository is safe to read *before*
    reading its content, so a planted ``filter.*`` or ``core.hookspath`` is
    refused before Git is asked to hash a working file.
    """
    expected_order = ordered_preflight_operations()
    results: dict[str, Any] = {}
    import time as _time

    for operation in expected_order:
        allowed = (0,) if operation != "rev_parse_head" else (0,)
        try:
            results[operation] = run_fixed_git_operation(
                operation,
                git_executable=git_executable,
                workspace_root=workspace_root,
                allowed_returncodes=allowed,
            )
        except GitAdapterError as exc:
            raise ObservationError(f"observation error: {exc}") from exc

    status_entries: list[StatusEntry] = []
    for raw in parse_status_porcelain(results["status_porcelain"].stdout):
        path = status_record_path(raw)
        status_entries.append(
            StatusEntry(
                raw=raw, index_code=raw[0], worktree_code=raw[1], path=path
            )
        )

    return ObservationSnapshot(
        top_level=results["rev_parse_show_toplevel"].stdout.strip(),
        head=results["rev_parse_head"].stdout.strip(),
        config_keys_local=parse_config_name_only(results["config_list_local"].stdout),
        scoped_config=parse_config_scoped_with_scope(results["config_list_scoped"].stdout),
        index_entries=parse_ls_files_stage(results["ls_files_stage"].stdout),
        ls_files_verbose=parse_ls_files_verbose(results["ls_files_verbose"].stdout),
        status_entries=tuple(status_entries),
        observed_at_monotonic=_time.monotonic(),
    )


def _canonical_identity_ok(workspace_root: str, top_level: str) -> bool:
    try:
        return os.path.normcase(os.path.realpath(top_level)) == os.path.normcase(
            os.path.realpath(workspace_root)
        )
    except OSError:
        return False


@dataclass
class Classification:
    """The single verdict, with the evidence that produced it."""

    workspace_class: str
    trusted: bool
    reasons: list[str]
    changed_tracked_paths: list[str]
    untracked_paths: list[str]
    staged_paths: list[str]
    head_moved: bool
    newly_unsupported_config_keys: list[str]
    local_scope_unsupported_config_keys: list[str]
    baseline_host_unsupported_config_keys: dict[str, list[str]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace_class": self.workspace_class,
            "trusted": self.trusted,
            "reasons": self.reasons,
            "changed_tracked_paths": self.changed_tracked_paths,
            "untracked_paths": self.untracked_paths,
            "staged_paths": self.staged_paths,
            "head_moved": self.head_moved,
            "newly_unsupported_config_keys": self.newly_unsupported_config_keys,
            "local_scope_unsupported_config_keys": self.local_scope_unsupported_config_keys,
            "baseline_host_unsupported_config_keys": self.baseline_host_unsupported_config_keys,
        }


def classify(
    snapshot: ObservationSnapshot,
    *,
    workspace_root: str,
    head_before: str,
    expected_changed_paths: frozenset[str],
    tolerated_untracked_paths: frozenset[str] = frozenset(),
    baseline: ObservationSnapshot | None = None,
) -> Classification:
    """Classify one observation. Fails closed on every unexpected shape.

    ``baseline`` is the pre-launch observation. When supplied, host-wide
    configuration keys that were already present before the run are separated
    from keys that appeared during it; a key that appeared during the run is
    poisoning in any scope.
    """
    reasons: list[str] = []

    baseline_unsupported: dict[str, list[str]] = (
        baseline.scoped_config.unsupported_by_scope() if baseline else {}
    )
    current_unsupported = snapshot.scoped_config.unsupported_by_scope()
    baseline_all = {key for keys in baseline_unsupported.values() for key in keys}
    newly_unsupported = sorted(
        {key for keys in current_unsupported.values() for key in keys} - baseline_all
    )
    local_unsupported = sorted(
        set(current_unsupported.get("local", []))
        | set(current_unsupported.get("worktree", []))
        | set(current_unsupported.get("submodule", []))
    )
    local_only_unsupported = sorted(
        set(local_unsupported) | set(find_unsupported_config_keys(snapshot.config_keys_local))
    )

    changed_tracked = sorted(
        entry.path for entry in snapshot.status_entries if not entry.is_untracked
    )
    untracked = sorted(entry.path for entry in snapshot.status_entries if entry.is_untracked)
    staged = sorted(entry.path for entry in snapshot.status_entries if entry.is_staged)

    def verdict(workspace_class: str) -> Classification:
        return Classification(
            workspace_class=workspace_class,
            trusted=workspace_class in TRUSTED_CLASSES,
            reasons=reasons,
            changed_tracked_paths=changed_tracked,
            untracked_paths=untracked,
            staged_paths=staged,
            head_moved=snapshot.head != head_before,
            newly_unsupported_config_keys=newly_unsupported,
            local_scope_unsupported_config_keys=local_only_unsupported,
            baseline_host_unsupported_config_keys=baseline_unsupported,
        )

    # 1. Identity. The repository must still be exactly the disposable root.
    if not _canonical_identity_ok(workspace_root, snapshot.top_level):
        reasons.append("git top level is no longer the disposable root AIDO created")
        return verdict(IDENTITY_LOST)
    try:
        canonicalize_existing_path_under_workspace(workspace_root, workspace_root)
    except CanonicalPathError as exc:
        reasons.append(f"canonical guard refused the repository root: {exc}")
        return verdict(IDENTITY_LOST)

    # 2. The configuration gate, BEFORE any content interpretation.
    if local_only_unsupported:
        reasons.append(
            "repository-local Git configuration carries execution- or "
            "indirection-capable keys: " + ", ".join(local_only_unsupported)
        )
        return verdict(CONFIG_POISONED)
    if newly_unsupported:
        reasons.append(
            "unsupported Git configuration keys appeared during the run: "
            + ", ".join(newly_unsupported)
        )
        return verdict(CONFIG_POISONED)

    # 3. Index shape.
    for entry in snapshot.index_entries:
        if entry.mode in (_GITLINK_MODE, _SYMLINK_MODE):
            reasons.append(f"index carries a gitlink or symlink mode for {entry.path!r}")
            return verdict(INDEX_SHAPE_UNTRUSTED)
        if entry.stage != 0:
            reasons.append(f"index entry {entry.path!r} is not at stage 0")
            return verdict(INDEX_SHAPE_UNTRUSTED)
    for tag, path in snapshot.ls_files_verbose:
        if tag == _SKIP_WORKTREE_TAG or tag.islower():
            reasons.append(
                f"index entry {path!r} is marked skip-worktree or assume-unchanged"
            )
            return verdict(INDEX_SHAPE_UNTRUSTED)

    # 4. HEAD must be exactly unchanged.
    if snapshot.head != head_before:
        reasons.append("HEAD moved during the run (commit, checkout, reset or similar)")
        return verdict(HEAD_MOVED)

    # 5. The index must be clean.
    if staged:
        reasons.append("the index carries staged entries: " + ", ".join(staged))
        return verdict(INDEX_DIRTY)

    # 6. Tracked changes must be exactly the expected shape.
    for entry in snapshot.status_entries:
        if entry.is_untracked:
            continue
        if entry.is_unmerged:
            reasons.append(f"unmerged index entry for {entry.path!r}")
            return verdict(INDEX_DIRTY)
        if not entry.is_unstaged_modification:
            reasons.append(
                f"tracked path {entry.path!r} is not a plain unstaged modification "
                f"(status {entry.raw[:2]!r}); a delete or rename is never expected"
            )
            return verdict(UNEXPECTED_CHANGE)
        if entry.path not in expected_changed_paths:
            reasons.append(f"unexpected tracked path modified: {entry.path!r}")
            return verdict(UNEXPECTED_CHANGE)

    # 7. Untracked files are never silently ignored and never auto-deleted.
    unexpected_untracked = [p for p in untracked if p not in tolerated_untracked_paths]
    if unexpected_untracked:
        reasons.append(
            "untracked paths appeared that are not in the pre-declared tolerated set: "
            + ", ".join(unexpected_untracked)
        )
        return verdict(UNEXPECTED_UNTRACKED)

    if not changed_tracked:
        reasons.append("no tracked modification was observed")
        return verdict(NO_CHANGE_OBSERVED)

    if untracked:
        reasons.append(
            "expected tracked modification plus pre-declared tolerated untracked paths"
        )
        return verdict(DIRTY_BENIGN)

    reasons.append("exactly the expected tracked modification, HEAD unchanged, index clean")
    return verdict(CLEAN_EXPECTED)


def diff_expected_path(
    *, git_executable: str, workspace_root: str, repo_relative_path: str
) -> str:
    """Run ``diff_one_path`` for exactly one path. Only for the trusted shape."""
    try:
        result = run_fixed_git_operation(
            "diff_one_path",
            git_executable=git_executable,
            workspace_root=workspace_root,
            repo_relative_path=repo_relative_path,
        )
    except GitAdapterError as exc:
        raise ObservationError(f"observation error: {exc}") from exc
    return result.stdout


def snapshot_for_record(snapshot: ObservationSnapshot) -> dict[str, Any]:
    """A recordable view. Repository-relative paths only; no absolute host path."""
    return {
        "head": snapshot.head,
        "status_records": list(snapshot.status_raw_records()),
        "tracked_index_paths": sorted(entry.path for entry in snapshot.index_entries),
        "local_config_key_names": sorted(snapshot.config_keys_local),
        "scoped_config_key_counts": {
            scope: len(keys) for scope, keys in snapshot.scoped_config.by_scope.items()
        },
        "scoped_unsupported_config_key_names": snapshot.scoped_config.unsupported_by_scope(),
    }
