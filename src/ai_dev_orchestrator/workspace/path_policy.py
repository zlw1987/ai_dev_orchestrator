"""Workspace path policy — pure, lexical boundary enforcement.

Phase 1: this module reasons about path STRINGS only. It never reads, writes,
stats, or resolves real files in any target project. That is what makes it safe
to evaluate paths for ``C:\\dev\\mis_project`` without ever touching that folder.

Rules enforced:

- Project-relative paths are normalized; ``.`` / ``..`` resolved lexically.
- Absolute paths are accepted only if they sit under the configured workspace
  root (compared component-by-component); otherwise rejected.
- ``..`` traversal that escapes the workspace root is rejected.
- Classification precedence: forbidden > protected > allowed > unlisted.
- Writes require an allowed (or explicitly authorized protected) path that is
  not forbidden.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from enum import Enum

from ai_dev_orchestrator.models import (
    PathRulesConfig,
    ProjectConfig,
    WorkspacePolicyConfig,
)

_DRIVE_RE = re.compile(r"^[A-Za-z]:$")


class PathPolicyError(Exception):
    """Raised when a path violates a hard boundary (outside workspace / traversal)."""


class PathClassification(str, Enum):
    """How a normalized path is classified against the rule lists."""

    FORBIDDEN = "forbidden"
    PROTECTED = "protected"
    ALLOWED = "allowed"
    UNLISTED = "unlisted"


@dataclass(frozen=True)
class PathDecision:
    """Result of evaluating a path for a read or write operation."""

    path: str
    classification: PathClassification
    permitted: bool
    requires_authorization: bool
    reason: str


def _split(raw: str) -> tuple[bool, list[str]]:
    """Split a path into (is_absolute, components), normalizing separators."""
    s = raw.replace("\\", "/")
    parts = [p for p in s.split("/") if p != ""]
    is_abs = s.startswith("/") or bool(parts and _DRIVE_RE.match(parts[0]))
    return is_abs, parts


def _resolve(parts: list[str]) -> list[str]:
    """Lexically resolve ``.`` and ``..``. Raises if traversal escapes the root."""
    out: list[str] = []
    for part in parts:
        if part == ".":
            continue
        if part == "..":
            if not out:
                raise PathPolicyError("path traversal escapes the workspace root")
            out.pop()
        else:
            out.append(part)
    return out


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pat) for pat in patterns)


class PathPolicy:
    """Evaluate project-relative or absolute paths against workspace rules."""

    def __init__(
        self,
        workspace_path: str,
        rules: PathRulesConfig,
        policy: WorkspacePolicyConfig | None = None,
    ) -> None:
        self._policy = policy or WorkspacePolicyConfig()
        self._rules = rules
        # Workspace root components, casefolded for case-insensitive comparison
        # (Windows paths are commonly case-insensitive).
        _, ws_parts = _split(workspace_path)
        self._workspace_parts = [p.casefold() for p in ws_parts]

    @classmethod
    def from_project_config(cls, config: ProjectConfig) -> "PathPolicy":
        return cls(
            workspace_path=config.repo.workspace_path,
            rules=config.path_rules,
            policy=config.workspace_policy,
        )

    @property
    def allow_symlinks(self) -> bool:
        """Whether symlinks are permitted by policy (filesystem checks deferred)."""
        return self._policy.allow_symlinks

    def normalize(self, raw_path: str) -> str:
        """Return a clean workspace-relative POSIX path, or raise PathPolicyError.

        Absolute paths must resolve inside the workspace root. Relative paths must
        not escape it via ``..``.
        """
        is_abs, parts = _split(raw_path)

        if is_abs:
            target = [p.casefold() for p in parts]
            ws = self._workspace_parts
            inside = target[: len(ws)] == ws and len(target) >= len(ws)
            if self._policy.deny_outside_workspace and not inside:
                raise PathPolicyError(
                    f"absolute path is outside the workspace: {raw_path}"
                )
            # Preserve original casing for the relative remainder.
            rel_parts = parts[len(ws):]
        else:
            rel_parts = parts

        resolved = _resolve(rel_parts)
        return "/".join(resolved)

    def classify(self, raw_path: str) -> PathClassification:
        """Classify a path. Raises PathPolicyError on boundary violations."""
        norm = self.normalize(raw_path)
        if _matches_any(norm, self._rules.forbidden_paths):
            return PathClassification.FORBIDDEN
        if _matches_any(norm, self._rules.protected_paths):
            return PathClassification.PROTECTED
        if _matches_any(norm, self._rules.allowed_paths):
            return PathClassification.ALLOWED
        return PathClassification.UNLISTED

    def check_read(self, raw_path: str) -> PathDecision:
        """Reads are controlled by classification, mirroring write strictness.

        FORBIDDEN/UNLISTED are denied; ALLOWED is permitted; PROTECTED is
        permitted but flagged as requiring review/authorization.
        """
        try:
            norm = self.normalize(raw_path)
        except PathPolicyError as exc:
            return PathDecision(raw_path, PathClassification.FORBIDDEN, False, False, str(exc))

        classification = self.classify(norm)

        if classification is PathClassification.FORBIDDEN:
            return PathDecision(norm, classification, False, False, "path is forbidden")
        if classification is PathClassification.UNLISTED:
            return PathDecision(
                norm, classification, False, False, "path is not in allowed_paths"
            )
        if classification is PathClassification.PROTECTED:
            return PathDecision(
                norm,
                classification,
                permitted=True,
                requires_authorization=True,
                reason="protected read should be reviewed/authorized",
            )
        return PathDecision(norm, classification, True, False, "read permitted")

    def check_write(self, raw_path: str, *, allow_protected: bool = False) -> PathDecision:
        """Writes require an allowed (or authorized protected) non-forbidden path."""
        try:
            norm = self.normalize(raw_path)
        except PathPolicyError as exc:
            return PathDecision(raw_path, PathClassification.FORBIDDEN, False, False, str(exc))

        classification = self.classify(norm)

        if classification is PathClassification.FORBIDDEN:
            return PathDecision(norm, classification, False, False, "path is forbidden")
        if classification is PathClassification.UNLISTED:
            return PathDecision(
                norm, classification, False, False, "path is not in allowed_paths"
            )
        if classification is PathClassification.PROTECTED:
            return PathDecision(
                norm,
                classification,
                permitted=allow_protected,
                requires_authorization=True,
                reason=(
                    "protected path written with authorization"
                    if allow_protected
                    else "protected path requires explicit authorization"
                ),
            )
        return PathDecision(norm, classification, True, False, "write permitted")
