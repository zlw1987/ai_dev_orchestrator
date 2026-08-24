"""The ONE delegated path authority. EXPERIMENT ONLY, and Python only.

AR2D section 12.4 requires a **new, narrow entry point** rather than a reuse of
``PathPolicy.check_write``, for two reasons:

1. **Construction.** ``PathPolicy.from_project_config`` binds to
   ``ProjectConfig.repo.workspace_path``. A delegated capability's root is a
   disposable root, and it must never be constructible from a project config that
   names a real target project.
2. **Semantics.** ``check_write(path, allow_protected=True)`` means *"a human
   explicitly authorized this protected path"*. That is a **promotion** concept,
   and making it reachable from a runtime request would silently convert a
   human-authorization parameter into a runtime capability.

So this module defines :func:`evaluate_delegated_candidate`, which calls the
shipped lexical classifier with ``allow_protected`` **hard-wired to ``False`` and
not exposed as a parameter**, and returns a decision type distinct from
``PathDecision`` so no call site can confuse a writer authorization with an
implementer capability check.

    ``check_write``                    asks: may AIDO apply this
                                             human-approved change here?
    ``evaluate_delegated_candidate``   asks: may this runtime touch this file
                                             right now?

They share a lexical primitive and nothing else. **The production writer guard is
not weakened, not parameterized, and not touched.**

Per-request order (AR2D section 12.2), re-run in full for EVERY request, with no
verdict ever cached::

    1. protocol validation      (ar2.wire)
    2. L1 canonical guard       lexical gate -> lstat -> reparse -> strict resolve
    3. L2 capability domain     manifest membership, operation class,
                                verification-witness exclusion
    4. L3 exclusion classify    forbidden > outside-domain > protected > allowed
    5. open + fstat identity    (ar2.broker)
    6. perform, bounded         (ar2.broker)
    7. record, AIDO side        (ar2.broker)
"""

from __future__ import annotations

import os
import stat as stat_module
from dataclasses import dataclass

from ai_dev_orchestrator.models import PathRulesConfig, WorkspacePolicyConfig
from ai_dev_orchestrator.workspace.canonical import (
    CanonicalPathError,
    _reject_unsafe_write_target_form,
    canonicalize_existing_path_under_workspace,
    canonicalize_write_target_under_workspace,
)
from ai_dev_orchestrator.workspace.path_policy import (
    PathClassification,
    PathPolicy,
    PathPolicyError,
)

from .capability import (
    EDIT_FILE,
    READ_FILE,
    FORBIDDEN_READ_PATTERNS,
    StaticEligibilityDomain,
)

# The longest path candidate the broker will even look at. A candidate longer
# than this is refused on its length, before any filesystem call.
MAX_CANDIDATE_LENGTH = 4096


@dataclass(frozen=True)
class DelegatedDecision:
    """The verdict for ONE candidate, for ONE operation, at ONE instant.

    Deliberately NOT a ``PathDecision``: this answers the implementer-capability
    question, never the writer-authorization question.

    ``internal_reason`` is AIDO's own full diagnostic and is recorded on AIDO's
    side. It is **never** returned to the runtime -- the wire error is uniformly
    ``refused`` so the runtime cannot map the exclusion set by probing.
    """

    permitted: bool
    operation: str
    classification: str
    internal_reason: str
    relative_path: str | None
    resolved_path: str | None

    def as_diagnostic(self) -> dict[str, object]:
        """AIDO-side record. Carries the relative path, never the absolute one."""
        return {
            "permitted": self.permitted,
            "operation": self.operation,
            "classification": self.classification,
            "internal_reason": self.internal_reason,
            "relative_path": self.relative_path,
            "resolved_path_recorded": False,
        }


def _refuse(
    operation: str, classification: str, reason: str, relative: str | None = None
) -> DelegatedDecision:
    return DelegatedDecision(
        permitted=False,
        operation=operation,
        classification=classification,
        internal_reason=reason,
        relative_path=relative,
        resolved_path=None,
    )


def build_exclusion_policy(canonical_root: str, protected: frozenset[str]) -> PathPolicy:
    """Construct the shipped lexical classifier for ONE disposable root.

    Constructed directly, never via ``from_project_config``: a delegated
    capability must not be buildable from a config that names a real project.
    """
    rules = PathRulesConfig(
        allowed_paths=["*", "**/*"],
        protected_paths=sorted(protected),
        forbidden_paths=list(FORBIDDEN_READ_PATTERNS),
    )
    policy = WorkspacePolicyConfig(deny_outside_workspace=True, allow_symlinks=False)
    return PathPolicy(workspace_path=canonical_root, rules=rules, policy=policy)


def evaluate_delegated_candidate(
    sed: StaticEligibilityDomain,
    operation: str,
    path_candidate: str,
) -> DelegatedDecision:
    """Decide whether ONE nominated candidate is legal for ONE operation, NOW.

    This is **static eligibility plus the point-in-time filesystem form/kind
    checks**. Dynamic preconditions -- budgets, the read receipt, terminal flags,
    the single-flight slot -- are evaluated separately against
    :class:`~ar2.capability.RunState`, because a budget is not an eligibility
    condition (FU1 section 3.2).

    The candidate is an **opaque untrusted string**. Pi resolves the model's path
    before the ops seam, so it will usually be an absolute host path; that is
    accepted because Pi computed it from a ``cwd`` AIDO chose, so it introduces no
    new knowledge on the untrusted side. The asymmetry is one-way: a **response**
    never carries an absolute path back.
    """
    if operation not in sed.operation_classes:
        return _refuse(operation, "outside-domain", "operation_class_not_enabled")

    # -- shape ---------------------------------------------------------------
    if not isinstance(path_candidate, str) or not path_candidate:
        return _refuse(operation, "outside-domain", "candidate_not_a_non_empty_string")
    if "\x00" in path_candidate:
        return _refuse(operation, "outside-domain", "candidate_contains_nul")
    if len(path_candidate) > MAX_CANDIDATE_LENGTH:
        return _refuse(operation, "outside-domain", "candidate_length_over_cap")

    # -- L1a: the strict write-target lexical gate, applied to READS TOO ------
    #
    # AR2D section 12.3's one deliberate strictness increase. The read guard's
    # historical caller was a human-approved inspection path; the broker's caller
    # is an untrusted runtime, so refusing an alternate-data-stream or
    # drive-relative spelling on the read side costs nothing. This is layered ON
    # TOP of the shipped functions and changes neither of them.
    try:
        _reject_unsafe_write_target_form(path_candidate, role="delegated candidate")
    except CanonicalPathError as exc:
        return _refuse(
            operation, "outside-domain", f"unsafe_lexical_form:{type(exc).__name__}"
        )

    # -- L1b: the accepted canonical guard ------------------------------------
    try:
        if operation == EDIT_FILE:
            target = canonicalize_write_target_under_workspace(
                sed.canonical_root, path_candidate, change_type="modify"
            )
            resolved = target.resolved_destination
            relative_native = target.relative_destination
        else:
            decision = canonicalize_existing_path_under_workspace(
                sed.canonical_root, path_candidate
            )
            resolved = decision.resolved_candidate
            relative_native = decision.relative_path
    except CanonicalPathError as exc:
        return _refuse(operation, "outside-domain", f"canonical_guard:{type(exc).__name__}")

    # -- L1c: it must be an ordinary regular file -----------------------------
    #
    # "inside the workspace" and "is a file" are different questions, and the
    # read guard deliberately answers only the first.
    try:
        kind = os.lstat(resolved)
    except OSError:
        return _refuse(operation, "outside-domain", "resolved_candidate_cannot_be_stat_ed")
    if stat_module.S_ISDIR(kind.st_mode):
        return _refuse(operation, "outside-domain", "resolved_candidate_is_a_directory")
    if not stat_module.S_ISREG(kind.st_mode):
        return _refuse(operation, "outside-domain", "resolved_candidate_is_not_a_regular_file")

    relative_posix = relative_native.replace(os.sep, "/").replace("\\", "/")
    if relative_posix in (".", ""):
        return _refuse(operation, "outside-domain", "resolved_candidate_is_the_root")

    # -- L2: capability domain membership -------------------------------------
    canonical_spelling = sed.canonical_manifest_spelling(relative_posix)
    if canonical_spelling is None:
        return _refuse(
            operation, "outside-domain", "not_in_mint_time_manifest", relative_posix
        )

    # -- L3: exclusion classification -----------------------------------------
    #
    # ``allow_protected`` is HARD-WIRED to False here and is not a parameter of
    # this function. There is no human-promotion semantic reachable from a
    # runtime request.
    policy = build_exclusion_policy(sed.canonical_root, sed.protected_paths)
    try:
        classification = policy.classify(canonical_spelling)
    except PathPolicyError as exc:
        return _refuse(
            operation, "outside-domain", f"path_policy:{exc}", canonical_spelling
        )

    if classification is PathClassification.FORBIDDEN:
        return _refuse(operation, "forbidden", "forbidden_pattern", canonical_spelling)

    if not sed.is_read_eligible(canonical_spelling):
        return _refuse(
            operation, "outside-domain", "not_read_eligible", canonical_spelling
        )

    if operation == READ_FILE:
        return DelegatedDecision(
            permitted=True,
            operation=operation,
            classification=(
                "protected"
                if classification is PathClassification.PROTECTED
                else "allowed"
            ),
            internal_reason="read permitted: tracked, contained, ordinary, not excluded",
            relative_path=canonical_spelling,
            resolved_path=resolved,
        )

    # -- edit-only static eligibility -----------------------------------------
    if canonical_spelling in sed.verification_witness_paths:
        return _refuse(
            operation,
            "protected",
            "verification_witness_is_never_writable",
            canonical_spelling,
        )
    if classification is PathClassification.PROTECTED:
        return _refuse(
            operation, "protected", "protected_path_is_readable_not_writable", canonical_spelling
        )
    if not sed.is_write_eligible(canonical_spelling):
        return _refuse(
            operation, "outside-domain", "not_write_eligible", canonical_spelling
        )

    return DelegatedDecision(
        permitted=True,
        operation=operation,
        classification="allowed",
        internal_reason="write permitted: statically eligible; preconditions checked separately",
        relative_path=canonical_spelling,
        resolved_path=resolved,
    )
