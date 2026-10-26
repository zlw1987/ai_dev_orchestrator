"""DL-4B S2 — the integration authority store (``aido-control-plane-store.v4``).

store.v4 is DL-4A's authority store with three things changed, each by a
versioned addition rather than by reinterpreting v3:

```text
WHO MAY HOLD IT      only a session whose FD-16 identity boundary proof passed;
                     the proof is re-run at EVERY public consumption boundary
                     (every read that is authority, every request, issuance,
                     dispatch, transition and recover()), pinned to one
                     boundary digest, and bound to this state root and clone
HOW A HUMAN APPROVES approval-challenge.v2 / human-attestation.v2, verified by
                     S1's RegistryHumanAttestationVerifier BEFORE the write
                     transaction (FD-5), re-checked inside it, consumed once,
                     and re-verified against the current registry on every
                     proof and recover() (FD-4; revocation is total)
WHAT IT ACTIVATES    plan-activation-subject.v2: plan + the FD-8a Alpha policy
                     + the boundary's clone + write-scope.v1 + project config
                     digest + identity boundary digest
```

The schema also fixes the tables S3–S6 write. **No API accepts claim,
observation or evidence bytes.** DL-4B S3 adds, all re-proven at every proof:

```text
ACTIVATION         A's own Git-free observation of the clone's .git (detached HEAD
                   = the scope's base) is recorded in the activation transaction
EXACT DIFF (H6)    request_exact_diff_approval reads the approved artifact and the
                   config from the inbox (O's files), stores them write-once, and
                   issues exact-diff-approval-subject.v1 over the STORED bytes;
                   record_exact_diff_approval consumes it once per step (FD-5)
WRITE HANDOFF      capability-gated (_perform_write_handoff, reachable only through
                   the session's WriteHandoffAdapter): M0 → one transaction spending
                   the approval and persisting the intent and handoff row → publish
                   → FD-17 claim → M1 → the effect, decided by M0/M1 alone
IMPLEMENTATION_    accepted only for the exact ticket whose write the store proves
RETURNED           (approval, completed intent, claim receipt, M0, M1, as approved)
```

Every other role-output event is still refused (S4–S6), and a row in an S4–S6
table is unexplained. A caller's report, digest or model is never a
substitute for the claim *and* the authority observation (FD-8, FD-15).

No subprocess, Git, network, model, environment read or workspace write
happens here. Besides the security facts and the two admin-owned files, A
reads the clone (observations), its inbox, and the outbox it created, and
creates only its own blobs and per-ticket exchange directories. See
``docs/DL4B_S2_INTEGRATION_AUTHORITY_STORE.md`` and
``docs/DL4B_S3_EXACT_DIFF_WRITE_HANDOFF.md``.
"""

from __future__ import annotations

import functools
import hashlib
import ntpath
import sqlite3
import typing
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Literal, NamedTuple

from pydantic import ValidationError

from ai_dev_orchestrator.control_plane.attestation_v2 import (
    APPROVAL_CHALLENGE_V2_SCHEMA_VERSION,
    APPROVAL_TEXT_V2,
    ApprovalChallengeV2,
    ApprovalSubjectKindV2,
    HumanAttestationV2,
)
from ai_dev_orchestrator.control_plane.authority import (
    APPROVAL_CHALLENGE_TTL,
    AuthorityRefusedError,
    BoundRoleOutput,
    DispatchTicket,
    ExecutionPolicy,
)
from ai_dev_orchestrator.control_plane.containment import AidoStateRoot, ContainmentError
from ai_dev_orchestrator.control_plane.contracts import validate_plan_against_contract
from ai_dev_orchestrator.control_plane.integration_records import (
    AUTHORITY_OBSERVATION_PROVENANCE,
    CLAIM_SHAPES,
    EXECUTION_CLAIM_PROVENANCE,
    OBSERVATION_KINDS,
    WRITE_HANDOFF_REPORT_SUMMARY,
    WRITE_INTENT_STATES,
    WriteScopeV1,
    exact_diff_approval_subject_v1_sha256,
    is_alpha_policy,
    plan_activation_subject_v2_sha256,
    write_scopes_sha256,
)
from ai_dev_orchestrator.control_plane.models import (
    ExecutionPlan,
    ImplementationReport,
    ProjectContract,
    ProjectContractContent,
    ProjectRun,
    ProjectState,
    ReviewVerdict,
    StepContract,
    StepContractProposal,
    StepRun,
    StepState,
    VerificationOutcome,
)
from ai_dev_orchestrator.control_plane.store import (
    _EVENT_ROLE,
    _LOGGED_EVENT_ROLE,
    _ROLES,
    _SCHEMA,
    _TABLES,
    ControlPlaneStore,
    RecordNotFoundError,
    StateUntrustedError,
    StoreError,
    _in_list,
    _PlanIssuance,
)
from ai_dev_orchestrator.control_plane.transitions import StepEvent, StepTransitionRequest
from ai_dev_orchestrator.integration.attestation_verifier import (
    AttestationRefusal,
    HumanAttestationRefusedError,
    RegistryHumanAttestationVerifier,
    VerifiedHumanAttestation,
)
from ai_dev_orchestrator.integration import claim_readers, claim_receiver, exchange, state_blobs
from ai_dev_orchestrator.integration.authority_files import AuthorityFiles
from ai_dev_orchestrator.integration.boundary_facts import ObjectFacts
from ai_dev_orchestrator.integration.claim_readers import ClaimReadError
from ai_dev_orchestrator.integration.claim_receiver import ClaimProtocolError, ReceivedClaim, Waiter
from ai_dev_orchestrator.integration.exchange import ExchangeError
from ai_dev_orchestrator.integration.identity_boundary import (
    IdentityBoundaryError,
    IdentityBoundaryProof,
    IsolationCategory,
)
from ai_dev_orchestrator.integration.security_descriptor import DescriptorError, parse_security_descriptor
from ai_dev_orchestrator.integration.workspace_observation import (
    MAX_MANIFEST_BYTES,
    Observation,
    ObservationError,
    classify_write,
    observe_git_control,
    observe_workspace,
    parse_manifest,
)

STORE_INTEGRATION_SCHEMA_VERSION = "aido-control-plane-store.v4"

_KINDS = _in_list(kind.value for kind in ApprovalSubjectKindV2)
_K = ApprovalSubjectKindV2
_R = AttestationRefusal
_AUDIT_COLUMNS = (
    "attestation", "attestation_sha256", "statement_sha256", "signature_sha256",
    "key_fingerprint_sha256", "authenticator_flags", "authenticator_counter", "user_verified",
    "registry_sha256", "identity_boundary_sha256", "facts_origin", "verified_at",
)


def _all(columns: tuple[str, ...], test: str) -> str:
    return " AND ".join(f"{column} {test}" for column in columns)


_V4_SCHEMA = f"""
CREATE TABLE approval_challenges_v2 (
    challenge_id TEXT PRIMARY KEY,
    subject_kind TEXT NOT NULL CHECK (subject_kind IN ({_KINDS})),
    subject_sha256 TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_by TEXT UNIQUE,
    attestation TEXT,
    attestation_sha256 TEXT,
    statement_sha256 TEXT,
    signature_sha256 TEXT,
    key_fingerprint_sha256 TEXT,
    authenticator_flags INTEGER,
    authenticator_counter INTEGER,
    user_verified INTEGER CHECK (user_verified IN (0, 1)),
    registry_sha256 TEXT,
    identity_boundary_sha256 TEXT,
    facts_origin TEXT CHECK (facts_origin IN ('windows', 'injected')),
    verified_at TEXT,
    CHECK ((consumed_by IS NULL AND {_all(_AUDIT_COLUMNS, "IS NULL")})
        OR (consumed_by IS NOT NULL AND {_all(_AUDIT_COLUMNS, "IS NOT NULL")}))
);
CREATE TABLE plan_activations (
    execution_plan_sha256 TEXT PRIMARY KEY REFERENCES contracts (sha256),
    project_contract_sha256 TEXT NOT NULL REFERENCES contracts (sha256),
    policy TEXT NOT NULL,
    policy_sha256 TEXT NOT NULL,
    target_workspace TEXT NOT NULL,
    target_workspace_sha256 TEXT NOT NULL,
    write_scopes_sha256 TEXT NOT NULL,
    project_config_sha256 TEXT NOT NULL,
    identity_boundary_sha256 TEXT NOT NULL,
    challenge_id TEXT NOT NULL UNIQUE REFERENCES approval_challenges_v2 (challenge_id),
    issued_at TEXT NOT NULL
);
CREATE TABLE activation_observations (
    execution_plan_sha256 TEXT PRIMARY KEY REFERENCES plan_activations (execution_plan_sha256),
    head_oid TEXT NOT NULL,
    git_control_sha256 TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    provenance TEXT NOT NULL CHECK (provenance = '{AUTHORITY_OBSERVATION_PROVENANCE}'),
    observed_at TEXT NOT NULL
);
CREATE TABLE write_scopes (
    execution_plan_sha256 TEXT NOT NULL REFERENCES plan_activations (execution_plan_sha256),
    step_id TEXT NOT NULL,
    body TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (execution_plan_sha256, step_id)
);
CREATE TABLE step_contract_issuances (
    step_contract_sha256 TEXT PRIMARY KEY REFERENCES contracts (sha256),
    execution_plan_sha256 TEXT NOT NULL REFERENCES plan_activations (execution_plan_sha256),
    policy_sha256 TEXT NOT NULL,
    issued_at TEXT NOT NULL
);
CREATE TABLE dispatch_tickets (
    ticket_id TEXT PRIMARY KEY,
    project_run_id TEXT NOT NULL,
    step_run_id TEXT NOT NULL REFERENCES step_runs (step_run_id),
    step_contract_sha256 TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ({_ROLES})),
    step_state TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    issued_at TEXT NOT NULL,
    consumed_request_id TEXT UNIQUE,
    held_envelope TEXT,
    held_envelope_sha256 TEXT,
    held_at TEXT,
    UNIQUE (step_run_id, state_version, role),
    CHECK ((held_envelope IS NULL) = (held_envelope_sha256 IS NULL)
        AND (held_envelope IS NULL) = (held_at IS NULL))
);
CREATE TABLE exact_diff_requests (
    challenge_id TEXT PRIMARY KEY REFERENCES approval_challenges_v2 (challenge_id),
    execution_plan_sha256 TEXT NOT NULL REFERENCES plan_activations (execution_plan_sha256),
    step_id TEXT NOT NULL,
    write_scope_sha256 TEXT NOT NULL,
    approved_diff_artifact_sha256 TEXT NOT NULL,
    project_config_sha256 TEXT NOT NULL,
    requested_at TEXT NOT NULL
);
CREATE TABLE exact_diff_approvals (
    approval_id TEXT PRIMARY KEY,
    execution_plan_sha256 TEXT NOT NULL REFERENCES plan_activations (execution_plan_sha256),
    step_id TEXT NOT NULL,
    write_scope_sha256 TEXT NOT NULL,
    approved_diff_artifact_sha256 TEXT NOT NULL,
    challenge_id TEXT NOT NULL UNIQUE REFERENCES exact_diff_requests (challenge_id),
    consumed_by_ticket_id TEXT UNIQUE REFERENCES dispatch_tickets (ticket_id),
    recorded_at TEXT NOT NULL,
    UNIQUE (execution_plan_sha256, step_id)
);
CREATE TABLE authority_observations (
    observation_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES dispatch_tickets (ticket_id),
    kind TEXT NOT NULL CHECK (kind IN ({_in_list(OBSERVATION_KINDS)})),
    target_sha256 TEXT NOT NULL,
    head_oid TEXT NOT NULL,
    git_control_sha256 TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    entry_count INTEGER NOT NULL CHECK (entry_count >= 0),
    provenance TEXT NOT NULL CHECK (provenance = '{AUTHORITY_OBSERVATION_PROVENANCE}'),
    observed_at TEXT NOT NULL,
    UNIQUE (ticket_id, kind)
);
CREATE TABLE write_intents (
    intent_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL UNIQUE REFERENCES dispatch_tickets (ticket_id),
    exact_diff_approval_id TEXT NOT NULL UNIQUE REFERENCES exact_diff_approvals (approval_id),
    write_scope_sha256 TEXT NOT NULL,
    approved_diff_artifact_sha256 TEXT NOT NULL,
    workspace_identity_sha256 TEXT NOT NULL,
    m0_observation_id TEXT NOT NULL REFERENCES authority_observations (observation_id),
    state TEXT NOT NULL CHECK (state IN ({_in_list(WRITE_INTENT_STATES)})),
    created_at TEXT NOT NULL,
    settled_at TEXT,
    CHECK ((state = 'pending') = (settled_at IS NULL))
);
CREATE TABLE execution_handoffs (
    ticket_id TEXT PRIMARY KEY REFERENCES dispatch_tickets (ticket_id),
    approved_diff_artifact_sha256 TEXT NOT NULL,
    project_config_sha256 TEXT NOT NULL,
    handoff_directory_identity TEXT,
    outbox_directory_identity TEXT,
    created_at TEXT NOT NULL,
    published_at TEXT,
    CHECK ((handoff_directory_identity IS NULL) = (outbox_directory_identity IS NULL)
        AND (handoff_directory_identity IS NULL) = (published_at IS NULL))
);
CREATE TABLE execution_claims (
    ticket_id TEXT PRIMARY KEY REFERENCES execution_handoffs (ticket_id),
    claim_sha256 TEXT NOT NULL,
    byte_length INTEGER NOT NULL CHECK (byte_length > 0),
    shape TEXT NOT NULL CHECK (shape IN ({_in_list(CLAIM_SHAPES)})),
    provenance TEXT NOT NULL CHECK (provenance = '{EXECUTION_CLAIM_PROVENANCE}'),
    received_at TEXT NOT NULL
);
CREATE TABLE write_evidence (
    ticket_id TEXT PRIMARY KEY REFERENCES execution_claims (ticket_id),
    intent_id TEXT NOT NULL UNIQUE REFERENCES write_intents (intent_id),
    m0_observation_id TEXT NOT NULL REFERENCES authority_observations (observation_id),
    m1_observation_id TEXT NOT NULL REFERENCES authority_observations (observation_id),
    write_scope_sha256 TEXT NOT NULL,
    workspace_identity_sha256 TEXT NOT NULL,
    provenance TEXT NOT NULL CHECK (provenance = '{EXECUTION_CLAIM_PROVENANCE}'),
    recorded_at TEXT NOT NULL
);
CREATE TABLE verification_evidence_v2 (
    ticket_id TEXT PRIMARY KEY REFERENCES execution_claims (ticket_id),
    step_run_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    write_intent_id TEXT NOT NULL REFERENCES write_intents (intent_id),
    write_scope_sha256 TEXT NOT NULL,
    workspace_identity_sha256 TEXT NOT NULL,
    claim_sha256 TEXT NOT NULL,
    m2_observation_id TEXT NOT NULL REFERENCES authority_observations (observation_id),
    outcome TEXT NOT NULL CHECK (outcome IN ({_in_list(typing.get_args(VerificationOutcome))})),
    provenance TEXT NOT NULL CHECK (provenance = '{EXECUTION_CLAIM_PROVENANCE}'),
    recorded_at TEXT NOT NULL
);
CREATE TABLE review_evidence (
    ticket_id TEXT PRIMARY KEY REFERENCES dispatch_tickets (ticket_id),
    verifier_ticket_id TEXT NOT NULL REFERENCES verification_evidence_v2 (ticket_id),
    claim_sha256 TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ({_in_list(typing.get_args(ReviewVerdict))})),
    provenance TEXT NOT NULL CHECK (provenance = '{EXECUTION_CLAIM_PROVENANCE}'),
    recorded_at TEXT NOT NULL
);
"""

#: Tables whose records a later slice writes (S3 to S6). S2 writes none of
#: them, so any row in one is unexplained and makes every run untrusted.
LATER_SLICE_TABLES = (
    "exact_diff_approvals",
    "authority_observations",
    "write_intents",
    "execution_handoffs",
    "execution_claims",
    "write_evidence",
    "verification_evidence_v2",
    "review_evidence",
)
#: DL-4B S3's tables: the exact-diff approval and the write handoff. Every row
#: in one must be explained by a re-proving chain (``_s3_issues``).
S3_TABLES = (
    "activation_observations",
    "exact_diff_requests",
    "exact_diff_approvals",
    "authority_observations",
    "write_intents",
    "execution_handoffs",
    "execution_claims",
    "write_evidence",
)
#: Tables S4-S6 will write. Nothing writes them yet, so any row is unexplained.
UNWRITTEN_TABLES = ("verification_evidence_v2", "review_evidence")
_V4_TABLES = _TABLES | {
    "approval_challenges_v2",
    "plan_activations",
    "write_scopes",
    "step_contract_issuances",
    "dispatch_tickets",
    *LATER_SLICE_TABLES,
    *S3_TABLES,
}
#: The approval kinds this store issues and consumes. Step acceptance v2 is
#: S6's: a challenge of that kind is unexplained here.
_ISSUED_KINDS = (_K.PROJECT_CONTRACT, _K.PLAN_ACTIVATION, _K.EXACT_DIFF_APPROVAL)
#: The one write each implementer dispatch may report, AIDO's own words.
_INTENT_COMPLETED = "completed"

Origin = Literal["windows", "injected"]


class IsolationUnprovenError(AuthorityRefusedError):
    """The FD-16 identity boundary, or its binding to this store, is not
    proven at a consumption boundary. Nothing was read as authority, consumed
    or written. ``category`` is S0's, or one of the store's own binding
    categories (``state_root_unbound``, ``clone_unbound``, ``origin_mismatch``,
    ``proof_invalid``)."""

    def __init__(self, category: str, detail: str) -> None:
        self.category = category
        super().__init__(f"isolation_unproven:{category}: {detail}")


class _IntegrationContext(NamedTuple):
    """What an integration store was opened with. Built only by
    :meth:`IntegrationStore._open_integration` after the first proof."""

    root: AidoStateRoot
    prove: Callable[..., IdentityBoundaryProof]
    verifier: RegistryHumanAttestationVerifier
    origin: Origin
    #: A's file access (FD-17/FD-18); ``None`` when the opener supplied none.
    files: AuthorityFiles | None
    waiter: Waiter
    #: The capability the write handoff adapter's recorder holds. Only the
    #: session that opened the store knows it.
    write_key: object | None


class _Activation(NamedTuple):
    execution_plan_sha256: str
    project_contract_sha256: str
    policy: ExecutionPolicy
    target_workspace: str
    target_workspace_sha256: str
    write_scopes: tuple[WriteScopeV1, ...]
    write_scopes_sha256: str
    project_config_sha256: str
    identity_boundary_sha256: str
    challenge_id: str


class _DiffContext(NamedTuple):
    """What one exact-diff approval binds, re-derived from stored rows and bytes."""

    activation: _Activation
    scope: WriteScopeV1
    subject: str
    artifact: bytes
    artifact_sha256: str
    config: bytes
    config_sha256: str
    facts: claim_readers.ApprovedDiffFacts
    config_facts: claim_readers.ProjectConfigFacts


class _WriteState(NamedTuple):
    """The re-proven state an implementer dispatch hands off a write from."""

    activation: _Activation
    scope: WriteScopeV1
    approval_id: str
    context: _DiffContext
    attestation: HumanAttestationV2
    git_control_sha256: str
    intent: sqlite3.Row | None
    handoff: sqlite3.Row | None


#: The columns an exact-diff approval shares with its request.
_DIFF_KEYS = ("execution_plan_sha256", "step_id", "write_scope_sha256", "approved_diff_artifact_sha256")


class WriteHandoffRefusedError(AuthorityRefusedError):
    """A write handoff ended without proving exactly the approved write. Its
    intent is settled ``refused`` or ``indeterminate``; the approval is spent
    and nothing will hand off a second write for the step."""


def _exact_diff_consumer(plan_sha256: str, step_id: str) -> str:
    return f"exact_diff:{plan_sha256}:{step_id}"


_INBOX_FORBIDDEN = frozenset('<>:"/\\|?*')
_INBOX_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{base}{n}" for base in ("COM", "LPT") for n in "123456789"}
)


def _inbox_name(name: object) -> str:
    """One inbox entry name in its only spelling, or a refusal."""
    if (
        type(name) is not str or not 1 <= len(name) <= 255
        or any(not " " <= c <= "~" or c in _INBOX_FORBIDDEN for c in name)
        or name in (".", "..") or name[-1] in ". "
        or name.split(".")[0].rstrip(" ").upper() in _INBOX_RESERVED
    ):
        raise AuthorityRefusedError("an inbox name is one printable ASCII file name Win32 addresses exactly.")
    return name


def _names_workspace(path: object, workspace: str) -> bool:
    """``path`` (from config) spells the activated workspace, folding ASCII case."""
    if type(path) is not str or not ntpath.isabs(path) or "\x00" in path:
        return False
    return _same_spelling(ntpath.normpath(path), workspace)


def _write_claim_issue(claim: claim_readers.WriteClaimFacts, state: _WriteState,
                       m0: Observation, m1: Observation | None) -> str | None:
    """Why a parsed write claim does not bind to the scope, the attested
    approval, the approved artifact and A's own observations, or ``None``."""
    if claim.path != state.scope.path:
        return "the write claim names another target."
    if (claim.approved_by, claim.approved_at) != (state.attestation.approver_id, state.attestation.attested_at):
        return "the write claim's approval is not the attested exact-diff approval."
    if claim.identity != state.context.facts.identity:
        return "the write claim's identity is not the approved artifact's."
    if m1 is None or (claim.pre_image_bytes, claim.post_image_bytes) != (m0.target_size, m1.target_size):
        return "the write claim's sizes are not what A observed."
    return None


def _write_handoff_report(step_contract_sha256: str, attempt: int) -> ImplementationReport:
    """The only report an implementer dispatch returns in store.v4: AIDO's
    fixed words, no claims (§5.5 step 7)."""
    return ImplementationReport(
        step_contract_sha256=step_contract_sha256, attempt=attempt,
        summary=WRITE_HANDOFF_REPORT_SUMMARY, claims=(),
    )


_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def _same_spelling(left: str, right: str) -> bool:
    """Equal Windows paths, folding ASCII letters only (S0's identity rule)."""
    return left.translate(_ASCII_LOWER) == right.translate(_ASCII_LOWER)


def _unconsumable(event: str, role: str) -> str:
    return (
        f"{event} needs the {role} dispatch's execution claim and authority observation, "
        "which an integration store records only through the DL-4B S3-S6 adapters; no "
        "caller-supplied output, report or digest replaces them."
    )


def _reproving(method: Callable) -> Callable:
    """Re-prove the identity boundary before ``method`` reads or changes
    anything, and mark the call proven for the hooks it reaches."""

    @functools.wraps(method)
    def reproved(self: IntegrationStore, *args, **kwargs):
        self._reprove_boundary()
        self._proven_depth += 1
        try:
            return method(self, *args, **kwargs)
        finally:
            self._proven_depth -= 1

    return reproved


class IntegrationStore(ControlPlaneStore):
    """``aido-control-plane-store.v4``. Opened only by
    :func:`~ai_dev_orchestrator.integration.integration_session.open_integration_session`
    (or its library form). Every public method below that reads authority or
    changes state re-runs the identity boundary proof first."""

    def __init__(self, connection: sqlite3.Connection, clock: Callable[[], datetime], *,
                 _open_token: object = None) -> None:
        super().__init__(connection, clock, _open_token=_open_token)
        self._boundary_sha256: str | None = None
        self._last_proof: IdentityBoundaryProof | None = None
        # Every proof and verifier record this store accepted, by identity and
        # kept alive (so an id is never reused), so that an object returned
        # twice is recognized and refused.
        self._accepted: dict[int, object] = {}
        # How many re-proven public calls are running. The hooks every base
        # path goes through re-prove themselves when it is zero, so calling a
        # ControlPlaneStore method unbound on this store cannot skip FD-16.
        self._proven_depth = 0

    # --- opening --------------------------------------------------------------

    @classmethod
    def open(cls, path, *, clock=None) -> ControlPlaneStore:  # type: ignore[override]
        raise StoreError("an integration store is opened only through open_integration_session().")

    @classmethod
    def _open_authority(cls, context, clock):  # type: ignore[override]
        raise StoreError("an integration store is opened only through open_integration_session().")

    @classmethod
    def _open(cls, path, clock, authority):  # type: ignore[override]
        if type(authority) is not _IntegrationContext:
            raise StoreError("an integration store is opened only through open_integration_session().")
        return super()._open(path, clock, authority)

    @classmethod
    def _layout(cls, authority: object) -> tuple[str, frozenset[str], str]:
        return _SCHEMA + _V4_SCHEMA, _V4_TABLES, STORE_INTEGRATION_SCHEMA_VERSION

    @classmethod
    def _meta(cls, authority: object) -> tuple[tuple[str, str], ...]:
        return (("state_root_id", authority.root.root_id), ("authority_origin", authority.origin))

    @classmethod
    def _meta_refusal(cls, key: str) -> str:
        if key == "authority_origin":
            return (
                "the integration store was created by the other kind of session; a production "
                "store and a library (injected-facts) store never open each other."
            )
        return super()._meta_refusal(key)

    @classmethod
    def _open_integration(
        cls,
        root: AidoStateRoot,
        *,
        prove: Callable[..., IdentityBoundaryProof],
        verifier: RegistryHumanAttestationVerifier,
        clock: Callable[[], datetime] | None,
        files: Callable[[], AuthorityFiles] | None = None,
        waiter: Waiter | None = None,
        write_key: object | None = None,
    ) -> IntegrationStore:
        """Prove the boundary, bind it to ``root``, then open ``root``'s store.

        Nothing on disk is created or opened before the first proof passes and
        names this state root. The origin of that proof (``windows`` or
        ``injected``) is the store's, for its whole life. ``files`` builds A's
        file access only after that proof; ``write_key`` is the capability the
        opening session minted for its write handoff adapter.
        """
        if type(root) is not AidoStateRoot:
            raise StoreError("an integration session needs an AidoStateRoot.")
        if type(verifier) is not RegistryHumanAttestationVerifier:
            raise StoreError("an integration session needs the DL-4B attestation verifier.")
        proof = _run_prover(prove, None)
        if type(proof) is not IdentityBoundaryProof:
            raise IsolationUnprovenError("proof_invalid", "the prover did not return a boundary proof.")
        origin: Origin = proof.facts_origin
        if origin == "windows" and not proof.is_production:
            raise IsolationUnprovenError(
                "proof_invalid", "a production proof must be confirmed by the independent evaluator."
            )
        if verifier.is_production != (origin == "windows"):
            raise IsolationUnprovenError(
                "origin_mismatch", "the attestation verifier and the boundary proof have different origins."
            )
        _require_state_root(root, proof)
        root.verify()
        try:
            file_access = files() if files is not None else None
        except Exception as exc:  # noqa: BLE001 - no file access means nothing is observed
            raise StoreError(f"the authority identity's file access is unavailable ({type(exc).__name__}).") from None
        context = _IntegrationContext(
            root=root, prove=prove, verifier=verifier, origin=origin, files=file_access,
            waiter=waiter if waiter is not None else claim_receiver.SystemWaiter(), write_key=write_key,
        )
        store = cls._open(root.store_path, clock, context)
        try:
            store._authority = context
            store._accept_proof(proof)
            store._boundary_sha256 = proof.boundary_sha256
            bound = {
                row[0] for row in store._conn.execute(
                    "SELECT DISTINCT identity_boundary_sha256 FROM plan_activations"
                )
            }
            if bound and bound != {proof.boundary_sha256}:
                raise IsolationUnprovenError(
                    IsolationCategory.BOUNDARY_DIGEST_MISMATCH.value,
                    "the identity boundary is not the one this store's plan activation bound.",
                )
        except BaseException:
            store.close()
            raise
        return store

    @property
    def boundary_sha256(self) -> str:
        """The identity boundary digest this session is pinned to. Not authority."""
        return self._boundary_sha256

    @property
    def is_production(self) -> bool:
        return self._require_authority().origin == "windows"

    # --- the boundary at every consumption ----------------------------------

    def _reprove_boundary(self) -> IdentityBoundaryProof:
        """Re-run the FD-16 proof now, pinned to this session's boundary, and
        re-prove the state root. Raises :class:`IsolationUnprovenError`."""
        authority = self._require_authority()
        proof = _run_prover(authority.prove, self._boundary_sha256)
        self._accept_proof(proof)
        authority.root.verify()
        return proof

    def _accept_proof(self, proof: object) -> None:
        authority = self._require_authority()
        if type(proof) is not IdentityBoundaryProof:
            raise IsolationUnprovenError("proof_invalid", "the prover did not return a boundary proof.")
        self._require_fresh(proof, "boundary proof")
        if proof.facts_origin != authority.origin or (
            authority.origin == "windows" and not proof.is_production
        ):
            raise IsolationUnprovenError(
                "origin_mismatch", "the boundary proof's origin is not this store's origin."
            )
        if self._boundary_sha256 is not None and proof.boundary_sha256 != self._boundary_sha256:
            raise IsolationUnprovenError(
                IsolationCategory.BOUNDARY_DIGEST_MISMATCH.value,
                "the identity boundary changed during this session.",
            )
        _require_state_root(authority.root, proof)
        self._last_proof = proof

    def _require_proven_call(self) -> None:
        if self._proven_depth == 0:
            self._reprove_boundary()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._require_proven_call()
        with super()._transaction():
            yield

    def _project_integrity(self, project_run_id: str):
        self._require_proven_call()
        return super()._project_integrity(project_run_id)

    def _load_contract(self, sha256: str, kind):
        self._require_proven_call()
        return super()._load_contract(sha256, kind)

    def _require_fresh(self, value: object, what: str) -> None:
        if id(value) in self._accepted:
            raise IsolationUnprovenError(
                "proof_invalid", f"a {what} already used by this store is never accepted again."
            )
        self._accepted[id(value)] = value

    def _require_clone(self, path: str) -> None:
        if not _same_spelling(path, self._last_proof.boundary.paths.clone):
            raise IsolationUnprovenError(
                "clone_unbound", "the target workspace is not the clone the identity boundary declares."
            )

    # --- public entry points: re-prove first ---------------------------------
    #
    # Each is decorated with @_reproving: one proof per call, before anything
    # is read or validated. The hooks above are the backstop.

    @_reproving
    def get_project_contract(self, sha256: str) -> ProjectContract:
        return super().get_project_contract(sha256)

    @_reproving
    def get_execution_plan(self, sha256: str) -> ExecutionPlan:
        return super().get_execution_plan(sha256)

    @_reproving
    def get_step_contract(self, sha256: str) -> StepContract:
        return super().get_step_contract(sha256)

    @_reproving
    def list_execution_plans(self, project_contract_sha256: str) -> tuple[ExecutionPlan, ...]:
        return super().list_execution_plans(project_contract_sha256)

    @_reproving
    def create_project_run(self, *, project_contract_sha256: str, execution_plan_sha256: str) -> ProjectRun:
        return super().create_project_run(
            project_contract_sha256=project_contract_sha256, execution_plan_sha256=execution_plan_sha256
        )

    @_reproving
    def create_step_run(self, *, project_run_id: str, step_contract_sha256: str) -> StepRun:
        return super().create_step_run(project_run_id=project_run_id, step_contract_sha256=step_contract_sha256)

    @_reproving
    def get_project_run(self, project_run_id: str) -> ProjectRun:
        return super().get_project_run(project_run_id)

    @_reproving
    def get_step_run(self, step_run_id: str) -> StepRun:
        return super().get_step_run(step_run_id)

    @_reproving
    def list_step_runs(self, project_run_id: str) -> tuple[StepRun, ...]:
        return super().list_step_runs(project_run_id)

    @_reproving
    def apply_step_transition(self, step_run_id, request, *, role_output=None, human_attestation=None):
        """DL-4A's transition, behind the boundary proof. A human attestation
        is refused: store.v4's human acceptance is S6's signed v2 acceptance
        over a held decision, which does not exist yet."""
        if human_attestation is not None:
            raise AuthorityRefusedError(
                "a human step acceptance in an integration store is DL-4B S6's signed "
                "step-acceptance-subject.v2; this store accepts none yet."
            )
        return super().apply_step_transition(step_run_id, request, role_output=role_output)

    @_reproving
    def apply_project_transition(self, project_run_id, request):
        return super().apply_project_transition(project_run_id, request)

    @_reproving
    def recover(self, project_run_id: str):
        return super().recover(project_run_id)

    @_reproving
    def issue_dispatch_ticket(self, step_run_id, *, role, expected_state_version):
        return super().issue_dispatch_ticket(
            step_run_id, role=role, expected_state_version=expected_state_version
        )

    @_reproving
    def issue_authorized_step_contract(self, proposal: StepContractProposal, *,
                                       execution_plan_sha256: str) -> StepContract:
        return super().issue_authorized_step_contract(proposal, execution_plan_sha256=execution_plan_sha256)

    # --- approvals v2 ----------------------------------------------------------

    @_reproving
    def request_project_contract_approval(self, content: ProjectContractContent) -> ApprovalChallengeV2:
        """Issue an ``approval-challenge.v2`` for this contract content."""
        self._require_authority()
        content = self._revalidated_authority(ProjectContractContent, content)
        with self._transaction():
            return self._insert_challenge_v2(_K.PROJECT_CONTRACT, content.sha256)

    @_reproving
    def record_approved_project_contract(self, contract: ProjectContract,
                                         attestation: HumanAttestationV2) -> str:
        """Record a Project Contract a human signed.

        FD-5: the persisted challenge is checked, the signature is verified
        against the registry **outside** the write transaction, and inside it
        the challenge is re-checked unconsumed and unexpired and the consumed
        attestation must be the one just verified.
        """
        self._require_authority()
        contract = self._revalidated_authority(ProjectContract, contract)
        attestation = self._revalidated_authority(HumanAttestationV2, attestation)
        consumed_by = f"project_contract:{contract.sha256}"
        with self._transaction():
            existing = self._conn.execute(
                "SELECT challenge_id, attestation_sha256 FROM approval_challenges_v2 "
                "WHERE consumed_by = ?", (consumed_by,)
            ).fetchone()
            if existing is not None:
                if (existing["challenge_id"], existing["attestation_sha256"]) != (
                    attestation.challenge_id, attestation.sha256
                ):
                    raise AuthorityRefusedError("this project contract is already approved.")
                # A receipt only for the identical approval, and only while it re-proves.
                self._check_approval_matches(
                    contract.approval.approved_by, contract.approval.approved_at, attestation
                )
                if (issue := self._contract_approval_issue(contract)) is not None:
                    raise StateUntrustedError(issue)
                return contract.sha256
            challenge = self._open_challenge(attestation, _K.PROJECT_CONTRACT, contract.sha256)
        self._check_approval_matches(contract.approval.approved_by, contract.approval.approved_at, attestation)
        verified = self._verify_for_consumption(challenge, attestation)
        with self._transaction():
            if self._open_challenge(attestation, _K.PROJECT_CONTRACT, contract.sha256) != challenge:
                raise AuthorityRefusedError("the challenge changed while it was being verified.")
            self._insert_contract("project_contract", contract, contract.project_id, contract.sha256, "", 1)
            self._consume_challenge_v2(challenge.challenge_id, consumed_by, attestation, verified)
        return contract.sha256

    @_reproving
    def request_plan_activation(
        self,
        *,
        execution_plan: ExecutionPlan,
        execution_policy: ExecutionPolicy,
        write_scopes: tuple[WriteScopeV1, ...],
    ) -> ApprovalChallengeV2:
        """Issue the challenge a human signs to activate this plan under the
        Alpha policy, against the identity boundary's clone, with these write
        scopes. The workspace is never a caller's path: it is the clone the
        proven boundary declares."""
        authority = self._require_authority()
        plan = self._revalidated_authority(ExecutionPlan, execution_plan)
        policy = self._revalidated_authority(ExecutionPolicy, execution_policy)
        scopes = self._revalidated_scopes(write_scopes)
        proof = self._last_proof
        workspace = authority.root.authorize_target_workspace(proof.boundary.paths.clone)
        self._require_clone(workspace.path)
        with self._transaction():
            project_contract = self._approved_project_contract(plan.project_contract_sha256)
            validate_plan_against_contract(plan, project_contract)
            if (issue := _alpha_profile_issue(plan, policy, scopes)) is not None:
                raise AuthorityRefusedError(issue)
            subject = self._activation_subject(
                project_contract.sha256, plan, policy, workspace.sha256, scopes
            )
            return self._insert_challenge_v2(_K.PLAN_ACTIVATION, subject)

    @_reproving
    def issue_execution_plan(  # type: ignore[override]
        self,
        execution_plan: ExecutionPlan,
        *,
        execution_policy: ExecutionPolicy,
        write_scopes: tuple[WriteScopeV1, ...],
        attestation: HumanAttestationV2,
    ) -> str:
        """Record one human-signed plan activation (``plan-activation-subject.v2``)."""
        authority = self._require_authority()
        plan = self._revalidated_authority(ExecutionPlan, execution_plan)
        policy = self._revalidated_authority(ExecutionPolicy, execution_policy)
        scopes = self._revalidated_scopes(write_scopes)
        attestation = self._revalidated_authority(HumanAttestationV2, attestation)
        consumed_by = f"execution_plan:{plan.sha256}"
        proof = self._last_proof
        workspace = authority.root.authorize_target_workspace(proof.boundary.paths.clone)
        self._require_clone(workspace.path)

        def checked() -> tuple[ApprovalChallengeV2 | None, str]:
            project_contract = self._approved_project_contract(plan.project_contract_sha256)
            validate_plan_against_contract(plan, project_contract)
            if (issue := _alpha_profile_issue(plan, policy, scopes)) is not None:
                raise AuthorityRefusedError(issue)
            subject = self._activation_subject(project_contract.sha256, plan, policy, workspace.sha256, scopes)
            existing = self._conn.execute(
                "SELECT a.*, c.attestation_sha256 FROM plan_activations a "
                "LEFT JOIN approval_challenges_v2 c ON c.consumed_by = ? "
                "WHERE a.execution_plan_sha256 = ?", (consumed_by, plan.sha256),
            ).fetchone()
            if existing is not None:
                if (
                    existing["challenge_id"], existing["attestation_sha256"], existing["policy_sha256"],
                    existing["target_workspace_sha256"], existing["write_scopes_sha256"],
                    existing["project_config_sha256"], existing["identity_boundary_sha256"],
                ) != (
                    attestation.challenge_id, attestation.sha256, policy.sha256, workspace.sha256,
                    write_scopes_sha256(scopes), scopes[0].project_config_sha256, self._boundary_sha256,
                ):
                    raise AuthorityRefusedError("this execution plan is already activated.")
                _, issue = self._plan_issuance_issue(plan, project_contract.sha256)
                if issue is not None:
                    raise StateUntrustedError(issue)
                return None, subject
            self._check_plan_supersession(plan)
            return self._open_challenge(attestation, _K.PLAN_ACTIVATION, subject), subject

        with self._transaction():
            challenge, subject = checked()
        if challenge is None:
            return plan.sha256  # the identical, still re-proving activation: a receipt
        verified = self._verify_for_consumption(challenge, attestation)
        # S3: A's own record of the clone's .git as activated (FD-14, FD-18).
        # M0 must later find exactly this control state; a symbolic HEAD, a
        # HEAD other than the scope's base, or submodules refuse the activation.
        observation = self._observe(observe_git_control, workspace.path)
        if observation.head_oid != scopes[0].base_head_oid:
            raise AuthorityRefusedError(
                "the clone's detached HEAD is not the write scope's base_head_oid."
            )
        self._publish_blob("observations", observation.manifest)
        with self._transaction():
            again, again_subject = checked()
            if again != challenge or again_subject != subject:
                raise AuthorityRefusedError("the activation changed while it was being verified.")
            self._insert_contract(
                "execution_plan", plan, plan.project_id, plan.project_contract_sha256, "", plan.plan_version
            )
            self._conn.execute(
                "INSERT INTO plan_activations (execution_plan_sha256, project_contract_sha256, policy, "
                "policy_sha256, target_workspace, target_workspace_sha256, write_scopes_sha256, "
                "project_config_sha256, identity_boundary_sha256, challenge_id, issued_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (plan.sha256, plan.project_contract_sha256, policy.model_dump_json(), policy.sha256,
                 workspace.path, workspace.sha256, write_scopes_sha256(scopes),
                 scopes[0].project_config_sha256, self._boundary_sha256, challenge.challenge_id,
                 self._now().isoformat()),
            )
            for scope in scopes:
                self._conn.execute(
                    "INSERT INTO write_scopes (execution_plan_sha256, step_id, body, sha256) "
                    "VALUES (?, ?, ?, ?)",
                    (plan.sha256, scope.step_id, scope.model_dump_json(), scope.sha256),
                )
            self._conn.execute(
                "INSERT INTO activation_observations (execution_plan_sha256, head_oid, git_control_sha256, "
                "manifest_sha256, provenance, observed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (plan.sha256, observation.head_oid, observation.git_control_sha256,
                 observation.manifest_sha256, AUTHORITY_OBSERVATION_PROVENANCE, self._now().isoformat()),
            )
            self._consume_challenge_v2(challenge.challenge_id, consumed_by, attestation, verified)
        return plan.sha256

    def request_step_acceptance(self, step_run_id: str):
        raise AuthorityRefusedError(
            "a step acceptance in an integration store is DL-4B S6's step-acceptance-subject.v2 "
            "over a held planner decision; S2 issues none."
        )

    @_reproving
    def authorized_target_workspace(self, project_run_id: str):
        authority = self._require_authority()
        with self._transaction():
            project, _ = self._proven_project(project_run_id)
            issuance = self._load_plan_issuance(project.execution_plan_sha256)
        self._require_clone(issuance.target_workspace)
        return authority.root.reverify_target_workspace(
            issuance.target_workspace, issuance.target_workspace_sha256
        )

    # --- challenges, verification, consumption ------------------------------

    def _insert_challenge_v2(self, kind: ApprovalSubjectKindV2, subject: str) -> ApprovalChallengeV2:
        now = self._now()
        challenge = ApprovalChallengeV2(
            schema_version=APPROVAL_CHALLENGE_V2_SCHEMA_VERSION,
            challenge_id=uuid.uuid4().hex,
            subject_kind=kind,
            subject_sha256=subject,
            issued_at=now,
            expires_at=now + APPROVAL_CHALLENGE_TTL,
            required_approval_text=APPROVAL_TEXT_V2[kind],
        )
        self._conn.execute(
            "INSERT INTO approval_challenges_v2 (challenge_id, subject_kind, subject_sha256, "
            "issued_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (challenge.challenge_id, kind.value, subject, challenge.issued_at.isoformat(),
             challenge.expires_at.isoformat()),
        )
        return challenge

    @staticmethod
    def _challenge_v2_from_row(row: sqlite3.Row) -> ApprovalChallengeV2:
        try:
            kind = ApprovalSubjectKindV2(row["subject_kind"])
            return ApprovalChallengeV2(
                schema_version=APPROVAL_CHALLENGE_V2_SCHEMA_VERSION,
                challenge_id=row["challenge_id"],
                subject_kind=kind,
                subject_sha256=row["subject_sha256"],
                issued_at=datetime.fromisoformat(row["issued_at"]),
                expires_at=datetime.fromisoformat(row["expires_at"]),
                required_approval_text=APPROVAL_TEXT_V2[kind],
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise StateUntrustedError("a stored approval challenge no longer validates.") from exc

    def _open_challenge(
        self, attestation: HumanAttestationV2, kind: ApprovalSubjectKindV2, subject: str
    ) -> ApprovalChallengeV2:
        """The store's own persisted challenge that ``attestation`` may consume
        now, or a refusal. Reads only; the verifier is not consulted here."""
        if attestation.subject_kind is not kind or attestation.subject_sha256 != subject:
            raise HumanAttestationRefusedError(_R.STATEMENT_MISMATCH, "the attestation names a different subject.")
        row = self._conn.execute(
            "SELECT * FROM approval_challenges_v2 WHERE challenge_id = ?", (attestation.challenge_id,)
        ).fetchone()
        if row is None:
            raise HumanAttestationRefusedError(
                _R.STATEMENT_MISMATCH, "the attestation answers no challenge this store issued."
            )
        challenge = self._challenge_v2_from_row(row)
        if challenge.subject_kind is not kind or challenge.subject_sha256 != subject:
            raise HumanAttestationRefusedError(
                _R.STATEMENT_MISMATCH, "the challenge was issued for a different subject."
            )
        if row["consumed_by"] is not None:
            raise HumanAttestationRefusedError(
                _R.CHALLENGE_SPENT, "the challenge was already answered; approval is single-use."
            )
        now = self._now()
        if now >= challenge.expires_at:
            raise HumanAttestationRefusedError(_R.CHALLENGE_EXPIRED, "the challenge expired before it was answered.")
        if not challenge.issued_at <= attestation.attested_at <= now:
            raise HumanAttestationRefusedError(
                _R.TIMESTAMP_INVALID, "the attestation is dated outside its challenge's window."
            )
        return challenge

    def _verify_for_consumption(
        self, challenge: ApprovalChallengeV2, attestation: HumanAttestationV2
    ) -> VerifiedHumanAttestation:
        """FD-5: the signature check, outside any write transaction, over the
        store's own challenge and state root id."""
        authority = self._require_authority()
        try:
            record = authority.verifier.verify_for_consumption(
                state_root_id=authority.root.root_id,
                challenge=ApprovalChallengeV2.model_validate(challenge.model_dump()),
                attestation=attestation,
            )
        except AuthorityRefusedError:
            raise
        except Exception as exc:  # noqa: BLE001 - a verifier failure is a refusal, never approval
            raise AuthorityRefusedError(
                f"the attestation verifier failed ({type(exc).__name__}); nothing was approved."
            ) from None
        self._accept_record(record, "consumption", challenge, attestation)
        return record

    def _accept_record(
        self,
        record: object,
        purpose: str,
        challenge: ApprovalChallengeV2,
        attestation: HumanAttestationV2,
    ) -> VerifiedHumanAttestation:
        """``record`` is a fresh verifier result of this store's origin, for
        exactly this state root, challenge, attestation and boundary."""
        authority = self._require_authority()
        if type(record) is not VerifiedHumanAttestation:
            raise AuthorityRefusedError("the attestation verifier did not return a verification record.")
        if id(record) in self._accepted:
            raise AuthorityRefusedError("a verification record already used by this store is never accepted again.")
        if (
            record.purpose != purpose
            or record.facts_origin != authority.origin
            or (authority.origin == "windows" and not record.is_production)
            or record.state_root_id != authority.root.root_id
            or record.challenge_id != challenge.challenge_id
            or record.subject_kind is not challenge.subject_kind
            or record.subject_sha256 != challenge.subject_sha256
            or record.approver_id != attestation.approver_id
            or record.attested_at != attestation.attested_at
            or record.attestation_sha256 != attestation.sha256
            or record.identity_boundary_sha256 != self._boundary_sha256
        ):
            raise AuthorityRefusedError(
                "the verification record is not for this store, challenge, attestation and boundary."
            )
        self._accepted[id(record)] = record
        return record

    def _consume_challenge_v2(
        self,
        challenge_id: str,
        consumed_by: str,
        attestation: HumanAttestationV2,
        record: VerifiedHumanAttestation,
    ) -> None:
        if record.attestation_sha256 != attestation.sha256:
            raise AuthorityRefusedError("the consumed attestation is not the one just verified.")
        try:
            updated = self._conn.execute(
                "UPDATE approval_challenges_v2 SET consumed_by = ?, attestation = ?, "
                "attestation_sha256 = ?, statement_sha256 = ?, signature_sha256 = ?, "
                "key_fingerprint_sha256 = ?, authenticator_flags = ?, authenticator_counter = ?, "
                "user_verified = ?, registry_sha256 = ?, identity_boundary_sha256 = ?, "
                "facts_origin = ?, verified_at = ? WHERE challenge_id = ? AND consumed_by IS NULL",
                (consumed_by, attestation.model_dump_json(), attestation.sha256, record.statement_sha256,
                 record.signature_sha256, record.key_fingerprint_sha256, record.authenticator_flags,
                 record.authenticator_counter, int(record.user_verified), record.registry_sha256,
                 record.identity_boundary_sha256, record.facts_origin, record.verified_at.isoformat(),
                 challenge_id),
            ).rowcount
        except sqlite3.IntegrityError as exc:
            raise AuthorityRefusedError("this subject was already approved.") from exc
        if updated != 1:
            raise HumanAttestationRefusedError(
                _R.CHALLENGE_SPENT, "the challenge was already answered; approval is single-use."
            )

    def _consumed_approval_v2(
        self, consumed_by: str, kind: ApprovalSubjectKindV2, subject: str
    ) -> tuple[HumanAttestationV2 | None, str | None]:
        """The recorded attestation that approved ``subject``, re-verified now
        against the current registry (FD-4), or why it does not stand."""
        authority = self._require_authority()
        row = self._conn.execute(
            "SELECT * FROM approval_challenges_v2 WHERE consumed_by = ?", (consumed_by,)
        ).fetchone()
        if row is None:
            return None, f"no recorded human approval for {kind.value}."
        try:
            attestation = HumanAttestationV2.model_validate_json(row["attestation"] or "")
            challenge = self._challenge_v2_from_row(row)
        except (ValidationError, StateUntrustedError):
            return None, f"the recorded {kind.value} approval no longer validates."
        if (
            row["subject_kind"] != kind.value
            or row["subject_sha256"] != subject
            or attestation.sha256 != row["attestation_sha256"]
            or attestation.challenge_id != row["challenge_id"]
            or attestation.subject_kind is not kind
            or attestation.subject_sha256 != subject
            or row["facts_origin"] != authority.origin
            or row["identity_boundary_sha256"] != self._boundary_sha256
        ):
            return None, f"the recorded {kind.value} approval does not match its subject."
        try:
            record = authority.verifier.reprove(
                state_root_id=authority.root.root_id, challenge=challenge, attestation=attestation
            )
            self._accept_record(record, "reproof", challenge, attestation)
        except HumanAttestationRefusedError as exc:
            return None, f"the recorded {kind.value} approval no longer re-proves: {exc.category.value}."
        except AuthorityRefusedError as exc:
            return None, f"the recorded {kind.value} approval no longer re-proves: {exc}"
        except Exception as exc:  # noqa: BLE001 - an unverifiable approval is not an approval
            return None, f"the recorded {kind.value} approval could not be re-verified ({type(exc).__name__})."
        if (
            record.statement_sha256, record.signature_sha256, record.key_fingerprint_sha256,
            record.authenticator_flags, record.authenticator_counter, int(record.user_verified),
        ) != (
            row["statement_sha256"], row["signature_sha256"], row["key_fingerprint_sha256"],
            row["authenticator_flags"], row["authenticator_counter"], row["user_verified"],
        ):
            return None, f"the recorded {kind.value} approval's audit record is not its re-proof."
        return attestation, None

    def _contract_approval_issue(self, contract: ProjectContract) -> str | None:
        attestation, issue = self._consumed_approval_v2(
            f"project_contract:{contract.sha256}", _K.PROJECT_CONTRACT, contract.sha256
        )
        if issue is not None:
            return issue
        if (
            contract.approval.approved_by != attestation.approver_id
            or contract.approval.approved_at != attestation.attested_at
        ):
            return "the project contract's approval block is not the attested approval."
        return None

    # --- plan activation v2 -----------------------------------------------------

    def _revalidated_scopes(self, value: object) -> tuple[WriteScopeV1, ...]:
        if type(value) is not tuple:
            raise AuthorityRefusedError("write_scopes must be a tuple of write-scope.v1 records.")
        return tuple(self._revalidated_authority(WriteScopeV1, scope) for scope in value)

    def _activation_subject(
        self,
        project_contract_sha256: str,
        plan: ExecutionPlan,
        policy: ExecutionPolicy,
        target_workspace_sha256: str,
        scopes: tuple[WriteScopeV1, ...],
    ) -> str:
        return plan_activation_subject_v2_sha256(
            project_contract_sha256=project_contract_sha256,
            execution_plan_sha256=plan.sha256,
            execution_policy_sha256=policy.sha256,
            target_workspace_sha256=target_workspace_sha256,
            write_scopes_sha256=write_scopes_sha256(scopes),
            project_config_sha256=scopes[0].project_config_sha256,
            identity_boundary_sha256=self._boundary_sha256,
        )

    def _load_activation(self, plan_sha256: str) -> _Activation:
        row = self._conn.execute(
            "SELECT * FROM plan_activations WHERE execution_plan_sha256 = ?", (plan_sha256,)
        ).fetchone()
        if row is None:
            raise AuthorityRefusedError("the execution plan was never activated.")
        try:
            policy = ExecutionPolicy.model_validate_json(row["policy"])
            scope_rows = self._conn.execute(
                "SELECT * FROM write_scopes WHERE execution_plan_sha256 = ? ORDER BY step_id",
                (plan_sha256,),
            ).fetchall()
            scopes = tuple(WriteScopeV1.model_validate_json(r["body"]) for r in scope_rows)
        except ValidationError as exc:
            raise StateUntrustedError("a stored plan activation no longer validates.") from exc
        if policy.sha256 != row["policy_sha256"]:
            raise StateUntrustedError("a stored execution policy no longer hashes to its identity.")
        if any(
            scope.sha256 != r["sha256"] or scope.step_id != r["step_id"]
            for scope, r in zip(scopes, scope_rows)
        ):
            raise StateUntrustedError("a stored write scope no longer hashes to its identity.")
        return _Activation(
            execution_plan_sha256=plan_sha256,
            project_contract_sha256=row["project_contract_sha256"],
            policy=policy,
            target_workspace=row["target_workspace"],
            target_workspace_sha256=row["target_workspace_sha256"],
            write_scopes=scopes,
            write_scopes_sha256=row["write_scopes_sha256"],
            project_config_sha256=row["project_config_sha256"],
            identity_boundary_sha256=row["identity_boundary_sha256"],
            challenge_id=row["challenge_id"],
        )

    def _load_plan_issuance(self, plan_sha256: str) -> _PlanIssuance:
        activation = self._load_activation(plan_sha256)
        return _PlanIssuance(
            project_contract_sha256=activation.project_contract_sha256,
            policy=activation.policy,
            target_workspace=activation.target_workspace,
            target_workspace_sha256=activation.target_workspace_sha256,
            challenge_id=activation.challenge_id,
        )

    def _plan_issuance_issue(
        self, plan: ExecutionPlan, project_contract_sha256: str
    ) -> tuple[_PlanIssuance | None, str | None]:
        """Why the plan's activation does not stand now, or its issuance.

        Re-derives every bound value from the stored rows: the Alpha profile,
        each write scope's digest and the scopes' digest, one config digest,
        this session's boundary digest, the boundary's clone, the v2 subject,
        and the signed approval, re-verified against the current registry.
        """
        try:
            activation = self._load_activation(plan.sha256)
        except (AuthorityRefusedError, StateUntrustedError) as exc:
            return None, str(exc)
        if activation.project_contract_sha256 != project_contract_sha256:
            return None, "the plan was activated under another project contract."
        if (issue := _alpha_profile_issue(plan, activation.policy, activation.write_scopes)) is not None:
            return None, f"the stored activation is outside the Alpha profile: {issue}"
        if write_scopes_sha256(activation.write_scopes) != activation.write_scopes_sha256:
            return None, "the stored write scopes are not the scopes the activation bound."
        if {scope.project_config_sha256 for scope in activation.write_scopes} != {
            activation.project_config_sha256
        }:
            return None, "the stored write scopes bind a different project config."
        if activation.identity_boundary_sha256 != self._boundary_sha256:
            return None, "the activation bound a different identity boundary."
        if not _same_spelling(activation.target_workspace, self._last_proof.boundary.paths.clone):
            return None, "the activated workspace is not the identity boundary's clone."
        runs = self._conn.execute(
            "SELECT COUNT(*) FROM project_runs WHERE execution_plan_sha256 = ?", (plan.sha256,)
        ).fetchone()[0]
        if runs > 1:
            return None, "the activation authorizes one project run, and more than one exists."
        if (issue := self._activation_observation_issue(activation)) is not None:
            return None, issue
        subject = self._activation_subject(
            project_contract_sha256, plan, activation.policy, activation.target_workspace_sha256,
            activation.write_scopes,
        )
        attestation, issue = self._consumed_approval_v2(
            f"execution_plan:{plan.sha256}", _K.PLAN_ACTIVATION, subject
        )
        if issue is not None:
            return None, issue
        if attestation.challenge_id != activation.challenge_id:
            return None, "the plan activation names a different approval."
        return self._load_plan_issuance(plan.sha256), None

    def _require_run_authority(self, project_contract: ProjectContract, plan: ExecutionPlan) -> None:
        if (issue := self._contract_approval_issue(project_contract)) is not None:
            raise AuthorityRefusedError(issue)
        issuance, issue = self._plan_issuance_issue(plan, project_contract.sha256)
        if issue is not None:
            raise AuthorityRefusedError(issue)
        if self._conn.execute(
            "SELECT 1 FROM project_runs WHERE execution_plan_sha256 = ?", (plan.sha256,)
        ).fetchone() is not None:
            raise AuthorityRefusedError("this plan activation already authorized its one project run.")
        self._require_clone(issuance.target_workspace)
        self._require_authority().root.reverify_target_workspace(
            issuance.target_workspace, issuance.target_workspace_sha256
        )

    # --- S3: A's file access, blobs and observations ----------------------------

    def _files(self) -> AuthorityFiles:
        files = self._require_authority().files
        if files is None:
            raise AuthorityRefusedError("this integration session has no authority file access.")
        return files

    def _observe(self, observer: Callable[..., Observation], *args: str) -> Observation:
        try:
            return observer(self._files(), *args)
        except ObservationError as exc:
            raise AuthorityRefusedError(f"the clone could not be observed: {exc}") from None

    def _publish_blob(self, kind: str, data: bytes) -> str:
        try:
            return state_blobs.write_blob(self._require_authority().root, kind, data)
        except ContainmentError as exc:
            raise AuthorityRefusedError(f"a write-once {kind} blob could not be published: {exc}") from None
        except OSError as exc:
            raise AuthorityRefusedError(
                f"a write-once {kind} blob could not be published ({type(exc).__name__})."
            ) from None

    def _blob(self, kind: str, sha256: str, limit: int) -> bytes:
        try:
            return state_blobs.read_blob(self._require_authority().root, kind, sha256, limit)
        except OSError as exc:
            raise ContainmentError(f"a stored {kind} blob cannot be read ({type(exc).__name__}).") from None

    def _stored_observation(self, sha256: str) -> Observation:
        observation = parse_manifest(self._blob("observations", sha256, MAX_MANIFEST_BYTES))
        if observation.manifest_sha256 != sha256:
            raise ObservationError("manifest_invalid", "a stored manifest is not the one named.")
        return observation

    def _activation_observation_issue(self, activation: _Activation) -> str | None:
        """Why the activation-time ``.git`` observation does not stand, or ``None``."""
        row = self._conn.execute(
            "SELECT * FROM activation_observations WHERE execution_plan_sha256 = ?",
            (activation.execution_plan_sha256,),
        ).fetchone()
        if row is None:
            return "the activation has no authority observation of the clone's .git."
        try:
            observation = self._stored_observation(row["manifest_sha256"])
        except (ContainmentError, ObservationError) as exc:
            return f"the activation's .git observation cannot be re-derived: {exc}"
        if (
            observation.tree is not None
            or observation.head_oid != row["head_oid"]
            or observation.git_control_sha256 != row["git_control_sha256"]
            or row["provenance"] != AUTHORITY_OBSERVATION_PROVENANCE
        ):
            return "the activation's .git observation is not its recorded manifest."
        if any(scope.base_head_oid != row["head_oid"] for scope in activation.write_scopes):
            return "the activation's observed HEAD is not the write scope's base."
        return None

    def _read_inbox(self, name: object, limit: int) -> bytes:
        """One file the operator identity placed in the inbox, read once from
        a handle that denies write sharing, or a refusal."""
        name = _inbox_name(name)
        boundary = self._last_proof.boundary
        path = ntpath.join(boundary.paths.inbox, name)
        try:
            read = self._files().read_file(path, limit)
        except AuthorityRefusedError:
            raise
        except Exception as exc:  # noqa: BLE001 - an unreadable inbox file approves nothing
            raise AuthorityRefusedError(f"inbox/{name} could not be read ({type(exc).__name__}).") from None
        if read is None:
            raise AuthorityRefusedError(f"inbox/{name} does not exist.")
        facts, data = read
        if (
            type(facts) is not ObjectFacts or facts.is_directory is not False
            or facts.is_reparse_point is not False or facts.link_count != 1
            or facts.final_path is None or ntpath.normcase(facts.final_path) != ntpath.normcase(path)
        ):
            raise AuthorityRefusedError(f"inbox/{name} is not a single-link regular file at its own path.")
        try:
            owner = parse_security_descriptor(facts.security_descriptor).owner
        except DescriptorError:
            raise AuthorityRefusedError(f"the owner of inbox/{name} cannot be read.") from None
        if owner != boundary.operator.sid:
            raise AuthorityRefusedError(f"inbox/{name} was not placed by the operator identity.")
        if type(data) is not bytes or len(data) > limit:
            raise AuthorityRefusedError(f"inbox/{name} exceeds its size bound.")
        return data

    # --- S3: exact-diff approval (H6) ---------------------------------------------

    def _diff_context(
        self,
        plan_sha256: str,
        step_id: str,
        artifact_sha256: str,
        config_sha256: str,
        *,
        artifact: bytes | None = None,
        config: bytes | None = None,
    ) -> _DiffContext:
        """Everything an exact-diff approval binds, re-derived from the stored
        activation and (unless given fresh from the inbox) the stored bytes.
        Raises :class:`AuthorityRefusedError` for any disagreement."""
        activation = self._load_activation(plan_sha256)
        scopes = [scope for scope in activation.write_scopes if scope.step_id == step_id]
        if len(scopes) != 1:
            raise AuthorityRefusedError("the activation has no write scope for that step.")
        scope = scopes[0]
        try:
            if artifact is None:
                artifact = self._blob("approved-diff", artifact_sha256, claim_readers.MAX_APPROVED_DIFF_BYTES)
            if config is None:
                config = self._blob("config", config_sha256, claim_readers.MAX_PROJECT_CONFIG_BYTES)
        except ContainmentError as exc:
            raise AuthorityRefusedError(f"the approved diff or config bytes cannot be resolved: {exc}") from None
        if (
            hashlib.sha256(artifact).hexdigest() != artifact_sha256
            or hashlib.sha256(config).hexdigest() != config_sha256
        ):
            raise AuthorityRefusedError("the approved diff or config bytes are not the bytes named.")
        if config_sha256 != scope.project_config_sha256:
            raise AuthorityRefusedError("the project config is not the config the write scope binds.")
        try:
            facts = claim_readers.read_approved_diff(artifact)
            config_facts = claim_readers.read_project_config(config)
        except ClaimReadError as exc:
            raise AuthorityRefusedError(f"the approved diff or project config is refused: {exc}") from None
        if facts.path != scope.path:
            raise AuthorityRefusedError("the approved change is not the write scope's path.")
        if facts.pre_image_sha256 != scope.pre_image_sha256:
            raise AuthorityRefusedError("the approved change does not start from the write scope's pre-image.")
        if not config_facts.workspace_write_enabled:
            raise AuthorityRefusedError("the project config does not enable workspace_write.")
        if (config_facts.project_id, config_facts.github_repo) != (
            facts.identity.project_id, facts.identity.repo
        ):
            raise AuthorityRefusedError("the project config is not the approved artifact's project.")
        if not _names_workspace(config_facts.workspace_path, activation.target_workspace):
            raise AuthorityRefusedError("the project config's workspace is not the activated clone.")
        activation_subject = plan_activation_subject_v2_sha256(
            project_contract_sha256=activation.project_contract_sha256,
            execution_plan_sha256=plan_sha256,
            execution_policy_sha256=activation.policy.sha256,
            target_workspace_sha256=activation.target_workspace_sha256,
            write_scopes_sha256=activation.write_scopes_sha256,
            project_config_sha256=activation.project_config_sha256,
            identity_boundary_sha256=activation.identity_boundary_sha256,
        )
        subject = exact_diff_approval_subject_v1_sha256(
            plan_activation_subject_sha256=activation_subject,
            execution_plan_sha256=plan_sha256,
            step_id=step_id,
            write_scope_sha256=scope.sha256,
            approved_diff_artifact_sha256=artifact_sha256,
        )
        return _DiffContext(activation, scope, subject, artifact, artifact_sha256, config, config_sha256,
                            facts, config_facts)

    def _require_config_workspace(self, context: _DiffContext) -> None:
        """The config's workspace root is the activated clone by canonical path
        **and** directory identity (a consumption-boundary check)."""
        try:
            identity = self._require_authority().root.authorize_target_workspace(
                context.config_facts.workspace_path
            )
        except ContainmentError as exc:
            raise AuthorityRefusedError(f"the project config's workspace is refused: {exc}") from None
        if identity.sha256 != context.activation.target_workspace_sha256:
            raise AuthorityRefusedError("the project config's workspace is not the activated clone.")

    def _exact_diff_preconditions(self, plan_sha256: str, step_id: str) -> None:
        try:
            plan = self._load_contract(plan_sha256, "execution_plan")
        except RecordNotFoundError:
            raise AuthorityRefusedError("the execution plan was never activated.") from None
        project_contract = self._approved_project_contract(plan.project_contract_sha256)
        _, issue = self._plan_issuance_issue(plan, project_contract.sha256)
        if issue is not None:
            raise AuthorityRefusedError(issue)
        if step_id not in {step.step_id for step in plan.steps}:
            raise AuthorityRefusedError("the step is not a step of the activated plan.")
        if self._conn.execute(
            "SELECT 1 FROM exact_diff_approvals WHERE execution_plan_sha256 = ? AND step_id = ?",
            (plan_sha256, step_id),
        ).fetchone() is not None:
            raise AuthorityRefusedError("this step already has its one exact-diff approval.")

    @_reproving
    def request_exact_diff_approval(
        self, *, execution_plan_sha256: str, step_id: str, artifact_name: str, config_name: str
    ) -> ApprovalChallengeV2:
        """Issue the challenge a human signs to approve one exact diff (H6).

        ``artifact_name`` and ``config_name`` name files the operator identity
        placed in the boundary's inbox: the ``approved-diff-proposal.v2`` with
        its frozen ``DiffEditApproval`` block, and the project config. A reads
        each once, validates both against the activated write scope, publishes
        them write-once into the state root and binds the artifact's exact
        bytes, by digest, into ``exact-diff-approval-subject.v1``. The subject
        is computed from those stored bytes, never from a caller's value.
        """
        self._require_authority()
        for value in (execution_plan_sha256, step_id, artifact_name, config_name):
            if type(value) is not str:
                raise AuthorityRefusedError("an exact-diff approval request names its inputs as strings.")
        with self._transaction():
            self._exact_diff_preconditions(execution_plan_sha256, step_id)
        artifact = self._read_inbox(artifact_name, claim_readers.MAX_APPROVED_DIFF_BYTES)
        config = self._read_inbox(config_name, claim_readers.MAX_PROJECT_CONFIG_BYTES)
        artifact_sha256 = hashlib.sha256(artifact).hexdigest()
        config_sha256 = hashlib.sha256(config).hexdigest()
        with self._transaction():
            fresh = self._diff_context(execution_plan_sha256, step_id, artifact_sha256, config_sha256,
                                       artifact=artifact, config=config)
        self._require_config_workspace(fresh)
        self._publish_blob("approved-diff", artifact)
        self._publish_blob("config", config)
        with self._transaction():
            self._exact_diff_preconditions(execution_plan_sha256, step_id)
            stored = self._diff_context(execution_plan_sha256, step_id, artifact_sha256, config_sha256)
            if stored.subject != fresh.subject:
                raise AuthorityRefusedError("the stored bytes are not the bytes read from the inbox.")
            challenge = self._insert_challenge_v2(_K.EXACT_DIFF_APPROVAL, stored.subject)
            self._conn.execute(
                "INSERT INTO exact_diff_requests (challenge_id, execution_plan_sha256, step_id, "
                "write_scope_sha256, approved_diff_artifact_sha256, project_config_sha256, requested_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (challenge.challenge_id, execution_plan_sha256, step_id, stored.scope.sha256,
                 artifact_sha256, config_sha256, self._now().isoformat()),
            )
        return challenge

    @_reproving
    def record_exact_diff_approval(self, attestation: HumanAttestationV2) -> str:
        """Record the human's signed exact-diff approval; returns its id.

        FD-5 ordering, as every v4 approval: the store's own challenge and the
        subject re-derived from the stored bytes are checked, the signature is
        verified outside the write transaction, and inside it everything is
        re-checked before the challenge is consumed. The artifact's
        ``DiffEditApproval`` must record exactly the attested approver and
        time. One approval per step, ever: a second one is refused.
        """
        self._require_authority()
        attestation = self._revalidated_authority(HumanAttestationV2, attestation)
        if attestation.subject_kind is not _K.EXACT_DIFF_APPROVAL:
            raise HumanAttestationRefusedError(_R.STATEMENT_MISMATCH, "the attestation is not an exact-diff approval.")

        def checked() -> tuple[ApprovalChallengeV2 | None, _DiffContext | None, sqlite3.Row | str]:
            request = self._conn.execute(
                "SELECT * FROM exact_diff_requests WHERE challenge_id = ?", (attestation.challenge_id,)
            ).fetchone()
            if request is None:
                raise HumanAttestationRefusedError(
                    _R.STATEMENT_MISMATCH, "the attestation answers no exact-diff challenge this store issued."
                )
            existing = self._conn.execute(
                "SELECT * FROM exact_diff_approvals WHERE execution_plan_sha256 = ? AND step_id = ?",
                (request["execution_plan_sha256"], request["step_id"]),
            ).fetchone()
            if existing is not None:
                challenge_row = self._conn.execute(
                    "SELECT attestation_sha256 FROM approval_challenges_v2 WHERE challenge_id = ?",
                    (existing["challenge_id"],),
                ).fetchone()
                if existing["challenge_id"] != attestation.challenge_id or challenge_row is None or (
                    challenge_row["attestation_sha256"] != attestation.sha256
                ):
                    raise AuthorityRefusedError("this step already has its one exact-diff approval.")
                _, _, issue = self._exact_diff_proof(existing)
                if issue is not None:
                    raise StateUntrustedError(issue)
                return None, None, existing["approval_id"]  # the identical, still re-proving approval
            self._exact_diff_preconditions(request["execution_plan_sha256"], request["step_id"])
            context = self._diff_context(
                request["execution_plan_sha256"], request["step_id"],
                request["approved_diff_artifact_sha256"], request["project_config_sha256"],
            )
            if context.scope.sha256 != request["write_scope_sha256"]:
                raise AuthorityRefusedError("the exact-diff request no longer names its write scope.")
            return self._open_challenge(attestation, _K.EXACT_DIFF_APPROVAL, context.subject), context, request

        with self._transaction():
            challenge, context, request = checked()
        if challenge is None:
            return request
        self._check_approval_matches(context.facts.approved_by, context.facts.approved_at, attestation)
        verified = self._verify_for_consumption(challenge, attestation)
        approval_id = uuid.uuid4().hex
        with self._transaction():
            again, again_context, again_request = checked()
            if again != challenge or again_context is None or again_context.subject != context.subject:
                raise AuthorityRefusedError("the exact-diff approval changed while it was being verified.")
            self._conn.execute(
                "INSERT INTO exact_diff_approvals (approval_id, execution_plan_sha256, step_id, "
                "write_scope_sha256, approved_diff_artifact_sha256, challenge_id, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (approval_id, again_request["execution_plan_sha256"], again_request["step_id"],
                 context.scope.sha256, context.artifact_sha256, challenge.challenge_id, self._now().isoformat()),
            )
            self._consume_challenge_v2(
                challenge.challenge_id,
                _exact_diff_consumer(again_request["execution_plan_sha256"], again_request["step_id"]),
                attestation, verified,
            )
        return approval_id

    def _exact_diff_proof(
        self, row: sqlite3.Row
    ) -> tuple[_DiffContext | None, HumanAttestationV2 | None, str | None]:
        """An ``exact_diff_approvals`` row, re-proven now: its request, the
        stored bytes, the activation, the subject, and the signature against
        the current registry (FD-4)."""
        try:
            request = self._conn.execute(
                "SELECT * FROM exact_diff_requests WHERE challenge_id = ?", (row["challenge_id"],)
            ).fetchone()
            if request is None or tuple(request[k] for k in _DIFF_KEYS) != tuple(row[k] for k in _DIFF_KEYS):
                return None, None, "an exact-diff approval is not its request."
            context = self._diff_context(
                row["execution_plan_sha256"], row["step_id"], row["approved_diff_artifact_sha256"],
                request["project_config_sha256"],
            )
        except (AuthorityRefusedError, StoreError) as exc:
            return None, None, f"an exact-diff approval does not re-derive: {exc}"
        if context.scope.sha256 != row["write_scope_sha256"]:
            return None, None, "an exact-diff approval names another write scope."
        attestation, issue = self._consumed_approval_v2(
            _exact_diff_consumer(row["execution_plan_sha256"], row["step_id"]), _K.EXACT_DIFF_APPROVAL,
            context.subject,
        )
        if issue is not None:
            return None, None, issue
        if attestation.challenge_id != row["challenge_id"]:
            return None, None, "an exact-diff approval names a different challenge."
        if (context.facts.approved_by, context.facts.approved_at) != (
            attestation.approver_id, attestation.attested_at
        ):
            return None, None, "the artifact's DiffEditApproval is not the attested approver and time."
        return context, attestation, None

    # --- S3: the write handoff (capability-gated) ----------------------------------

    def _write_state(self, ticket: DispatchTicket, *, fresh: bool) -> _WriteState:
        """Inside a transaction: the re-proven state one implementer dispatch
        may hand off a write from, or a refusal. ``fresh`` requires that no
        intent exists yet; otherwise this ticket's intent must be pending."""
        step, contract, (project, _) = self._proven_step_by_id(ticket.step_run_id)
        row = self._conn.execute(
            "SELECT * FROM dispatch_tickets WHERE ticket_id = ?", (ticket.ticket_id,)
        ).fetchone()
        if row is None or self._ticket_from_row(row) != ticket:
            raise AuthorityRefusedError("the ticket is not one AIDO issued.")
        if ticket.role != "implementer" or row["consumed_request_id"] is not None:
            raise AuthorityRefusedError("the ticket is not an unanswered implementer dispatch.")
        if project.state is not ProjectState.ACTIVE:
            raise AuthorityRefusedError(f"the project is {project.state.value}.")
        if (step.state, step.state_version, step.attempt) != (
            StepState.EXECUTING, ticket.state_version, ticket.attempt
        ):
            raise AuthorityRefusedError("the implementer ticket is stale: its step left that state.")
        activation = self._load_activation(project.execution_plan_sha256)
        approval = self._conn.execute(
            "SELECT * FROM exact_diff_approvals WHERE execution_plan_sha256 = ? AND step_id = ?",
            (project.execution_plan_sha256, contract.step_id),
        ).fetchone()
        if approval is None:
            raise AuthorityRefusedError("no recorded exact-diff approval authorizes a write for this step.")
        context, attestation, issue = self._exact_diff_proof(approval)
        if issue is not None:
            raise AuthorityRefusedError(issue)
        observed = self._conn.execute(
            "SELECT git_control_sha256 FROM activation_observations WHERE execution_plan_sha256 = ?",
            (project.execution_plan_sha256,),
        ).fetchone()
        intent = self._conn.execute(
            "SELECT * FROM write_intents WHERE ticket_id = ?", (ticket.ticket_id,)
        ).fetchone()
        handoff = self._conn.execute(
            "SELECT * FROM execution_handoffs WHERE ticket_id = ?", (ticket.ticket_id,)
        ).fetchone()
        if fresh:
            if approval["consumed_by_ticket_id"] is not None:
                raise AuthorityRefusedError("the exact-diff approval was already spent; it authorizes one write.")
            if intent is not None or handoff is not None:
                raise AuthorityRefusedError("this dispatch already has a write intent.")
        elif (
            intent is None or intent["state"] != "pending" or handoff is None
            or approval["consumed_by_ticket_id"] != ticket.ticket_id
            or intent["exact_diff_approval_id"] != approval["approval_id"]
        ):
            raise AuthorityRefusedError("the dispatch has no pending write intent.")
        return _WriteState(activation, context.scope, approval["approval_id"], context, attestation,
                           observed["git_control_sha256"], intent, handoff)

    @_reproving
    def _perform_write_handoff(self, key: object, ticket: DispatchTicket) -> ImplementationReport:
        """The write handoff of one implementer dispatch (§5.5, FD-9, FD-17,
        FD-18). Reachable only with the capability the session minted into
        its :class:`~.write_handoff.WriteHandoffAdapter`; it takes the ticket
        and nothing else, so no caller supplies a path, an artifact, a config,
        claim bytes or an observation.

        ```text
        1  M0, then ONE transaction: re-prove ticket, boundary, activation and
           approval; consume the approval; insert M0, the pending intent and
           the handoff row. COMMIT before anything is visible to X.
        2  publish handoff-<ticket> and outbox-<ticket>; record their identities
        3  wait (fixed bound) for the completion marker; re-prove; read the
           claim ONCE, only while the ticket is still EXECUTING
        4  M1; classify from M0/M1 alone; ONE transaction: M1, the claim
           receipt, the intent's final state, and the write evidence
        ```

        Any failure after step 1 settles the intent ``refused`` (M1 equals M0)
        or ``indeterminate`` (anything else) and raises: DL-2 reduces the step
        to RECOVERY_REQUIRED. The approval is spent at step 1, so nothing here
        or anywhere can hand off a second write for the step.
        """
        self._require_write_key(key)
        ticket = self._revalidated_authority(DispatchTicket, ticket)
        m0 = self._claim_write_intent(key, ticket)
        received: ReceivedClaim | None = None
        failure: Exception | None = None
        try:
            self._reprove_boundary()
            self._publish_write_handoff(key, ticket)
            self._reprove_boundary()
            received = self._receive_write_claim(key, ticket)
        except IsolationUnprovenError:
            raise
        except (AuthorityRefusedError, ExchangeError, ClaimProtocolError) as exc:
            failure = exc
        self._reprove_boundary()
        return self._settle_write(key, ticket, m0, received, failure)

    def _require_write_key(self, key: object) -> None:
        """Every phase of a write handoff requires the recorder's capability,
        so no phase is reachable around :meth:`_perform_write_handoff`."""
        authority = self._require_authority()
        if key is None or key is not authority.write_key:
            raise AuthorityRefusedError("only this session's write handoff adapter may hand off a write.")
        self._require_proven_call()

    def _claim_write_intent(self, key: object, ticket: DispatchTicket) -> Observation:
        self._require_write_key(key)
        authority = self._require_authority()
        with self._transaction():
            state = self._write_state(ticket, fresh=True)
        activation = state.activation
        self._require_clone(activation.target_workspace)
        try:
            authority.root.reverify_target_workspace(
                activation.target_workspace, activation.target_workspace_sha256
            )
        except ContainmentError as exc:
            raise AuthorityRefusedError(f"the workspace is not the activated clone: {exc}") from None
        self._require_config_workspace(state.context)
        m0 = self._observe(observe_workspace, activation.target_workspace, state.scope.path)
        if m0.target_sha256 != state.scope.pre_image_sha256:
            raise AuthorityRefusedError("M0: the target does not hold the approved pre-image.")
        if m0.head_oid != state.scope.base_head_oid:
            raise AuthorityRefusedError("M0: the clone's detached HEAD is not the write scope's base.")
        if m0.git_control_sha256 != state.git_control_sha256:
            raise AuthorityRefusedError("M0: the clone's .git control state is not the activation-time state.")
        self._publish_blob("observations", m0.manifest)
        with self._transaction():
            again = self._write_state(ticket, fresh=True)
            if (again.approval_id, again.context.subject) != (state.approval_id, state.context.subject):
                raise AuthorityRefusedError("the approval changed while M0 was being taken.")
            now = self._now().isoformat()
            m0_id = uuid.uuid4().hex
            self._insert_observation(m0_id, ticket.ticket_id, "m0", m0, now)
            self._conn.execute(
                "INSERT INTO write_intents (intent_id, ticket_id, exact_diff_approval_id, write_scope_sha256, "
                "approved_diff_artifact_sha256, workspace_identity_sha256, m0_observation_id, state, "
                "created_at, settled_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL)",
                (uuid.uuid4().hex, ticket.ticket_id, state.approval_id, state.scope.sha256,
                 state.context.artifact_sha256, activation.target_workspace_sha256, m0_id, now),
            )
            if self._conn.execute(
                "UPDATE exact_diff_approvals SET consumed_by_ticket_id = ? "
                "WHERE approval_id = ? AND consumed_by_ticket_id IS NULL",
                (ticket.ticket_id, state.approval_id),
            ).rowcount != 1:
                raise StateUntrustedError("an exact-diff approval changed underneath its own transaction.")
            self._conn.execute(
                "INSERT INTO execution_handoffs (ticket_id, approved_diff_artifact_sha256, "
                "project_config_sha256, created_at) VALUES (?, ?, ?, ?)",
                (ticket.ticket_id, state.context.artifact_sha256, state.context.config_sha256, now),
            )
        return m0

    def _publish_write_handoff(self, key: object, ticket: DispatchTicket) -> None:
        self._require_write_key(key)
        with self._transaction():
            state = self._write_state(ticket, fresh=False)
            if state.handoff["published_at"] is not None:
                raise StateUntrustedError("the write handoff was already published.")
        boundary = self._last_proof.boundary
        published = exchange.publish_handoff(
            self._files(), exchange_root=boundary.paths.exchange_root, ticket_id=ticket.ticket_id,
            authority_sid=boundary.authority.sid, execution_sid=boundary.execution.sid,
            operator_sid=boundary.operator.sid, artifact=state.context.artifact, config=state.context.config,
        )
        with self._transaction():
            self._write_state(ticket, fresh=False)
            if self._conn.execute(
                "UPDATE execution_handoffs SET handoff_directory_identity = ?, outbox_directory_identity = ?, "
                "published_at = ? WHERE ticket_id = ? AND published_at IS NULL",
                (published.handoff_identity, published.outbox_identity, self._now().isoformat(),
                 ticket.ticket_id),
            ).rowcount != 1:
                raise StateUntrustedError("a write handoff changed underneath its own transaction.")

    def _receive_write_claim(self, key: object, ticket: DispatchTicket) -> ReceivedClaim:
        self._require_write_key(key)
        authority = self._require_authority()
        with self._transaction():
            state = self._write_state(ticket, fresh=False)
        if state.handoff["published_at"] is None:
            raise AuthorityRefusedError("the write handoff was never published.")
        _, outbox = exchange.ticket_directories(self._last_proof.boundary.paths.exchange_root, ticket.ticket_id)
        deadline = authority.waiter.monotonic() + claim_receiver.CLAIM_WAIT_SECONDS
        claim_receiver.await_completion(self._files(), outbox, authority.waiter, deadline)
        # FD-16 and FD-17: re-prove, and never read a claim for a ticket that
        # left its permitted state while A waited.
        self._reprove_boundary()
        with self._transaction():
            state = self._write_state(ticket, fresh=False)
            if self._conn.execute(
                "SELECT 1 FROM execution_claims WHERE ticket_id = ?", (ticket.ticket_id,)
            ).fetchone() is not None:
                raise StateUntrustedError("this dispatch already has a recorded claim.")
        boundary = self._last_proof.boundary
        exchange.outbox_still_published(
            self._files(), boundary.paths.exchange_root, ticket.ticket_id,
            authority_sid=boundary.authority.sid, execution_sid=boundary.execution.sid,
            operator_sid=boundary.operator.sid, identity=state.handoff["outbox_directory_identity"],
        )
        return claim_receiver.read_claim(self._files(), outbox, boundary.execution.sid,
                                         claim_readers.MAX_WRITE_CLAIM_BYTES)

    def _settle_write(
        self,
        key: object,
        ticket: DispatchTicket,
        m0: Observation,
        received: ReceivedClaim | None,
        failure: Exception | None,
    ) -> ImplementationReport:
        self._require_write_key(key)
        with self._transaction():
            state = self._write_state(ticket, fresh=False)
        scope = state.scope
        reasons = [] if failure is None else [str(failure)]
        m1: Observation | None = None
        try:
            m1 = observe_workspace(self._files(), state.activation.target_workspace, scope.path)
        except ObservationError as exc:
            reasons.append(f"M1 could not be taken: {exc}")
        effect = "indeterminate" if m1 is None else classify_write(
            m0, m1, target_path=scope.path, pre_image_sha256=scope.pre_image_sha256,
            post_image_sha256=state.context.facts.post_image_sha256,
        )
        if effect != "as_approved":
            reasons.append(f"M1 shows {'no change' if effect == 'no_change' else 'an indeterminate effect'}")
        claim = None
        if received is not None:
            try:
                claim = claim_readers.read_write_claim(received.data)
            except ClaimReadError as exc:
                reasons.append(f"the claim is not a workspace-write-result.v1: {exc}")
        if claim is not None and (issue := _write_claim_issue(claim, state, m0, m1)) is not None:
            reasons.append(issue)
        if effect == "as_approved" and claim is not None and not reasons:
            final = _INTENT_COMPLETED
        elif effect == "no_change":
            final = "refused"
        else:
            final = "indeterminate"
        if m1 is not None:
            self._publish_blob("observations", m1.manifest)
        if claim is not None:
            self._publish_blob("claims", received.data)
        with self._transaction():
            current = self._write_state(ticket, fresh=False)
            now = self._now().isoformat()
            m1_id = None
            if m1 is not None:
                m1_id = uuid.uuid4().hex
                self._insert_observation(m1_id, ticket.ticket_id, "m1", m1, now)
            if claim is not None:
                self._conn.execute(
                    "INSERT INTO execution_claims (ticket_id, claim_sha256, byte_length, shape, provenance, "
                    "received_at) VALUES (?, ?, ?, 'write-result', ?, ?)",
                    (ticket.ticket_id, received.sha256, len(received.data), EXECUTION_CLAIM_PROVENANCE, now),
                )
            if self._conn.execute(
                "UPDATE write_intents SET state = ?, settled_at = ? WHERE ticket_id = ? AND state = 'pending'",
                (final, now, ticket.ticket_id),
            ).rowcount != 1:
                raise StateUntrustedError("a write intent changed underneath its own transaction.")
            if final == _INTENT_COMPLETED:
                self._conn.execute(
                    "INSERT INTO write_evidence (ticket_id, intent_id, m0_observation_id, m1_observation_id, "
                    "write_scope_sha256, workspace_identity_sha256, provenance, recorded_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (ticket.ticket_id, current.intent["intent_id"], current.intent["m0_observation_id"], m1_id,
                     scope.sha256, state.activation.target_workspace_sha256, EXECUTION_CLAIM_PROVENANCE, now),
                )
        if final != _INTENT_COMPLETED:
            raise WriteHandoffRefusedError(f"the write handoff ended {final}: " + "; ".join(reasons))
        return _write_handoff_report(ticket.step_contract_sha256, ticket.attempt)

    def _insert_observation(self, observation_id: str, ticket_id: str, kind: str,
                            observation: Observation, now: str) -> None:
        self._conn.execute(
            "INSERT INTO authority_observations (observation_id, ticket_id, kind, target_sha256, head_oid, "
            "git_control_sha256, manifest_sha256, entry_count, provenance, observed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (observation_id, ticket_id, kind, observation.target_sha256, observation.head_oid,
             observation.git_control_sha256, observation.manifest_sha256, observation.entry_count,
             AUTHORITY_OBSERVATION_PROVENANCE, now),
        )

    # --- S3: proofs of the write chain ----------------------------------------------

    def _observation_row(self, observation_id: object, ticket_id: str,
                         kind: str) -> tuple[Observation | None, str | None]:
        row = self._conn.execute(
            "SELECT * FROM authority_observations WHERE observation_id = ?", (observation_id,)
        ).fetchone()
        if row is None or (row["ticket_id"], row["kind"], row["provenance"]) != (
            ticket_id, kind, AUTHORITY_OBSERVATION_PROVENANCE
        ):
            return None, f"the {kind.upper()} observation of the dispatch is missing or misbound."
        try:
            observation = self._stored_observation(row["manifest_sha256"])
        except (ContainmentError, ObservationError) as exc:
            return None, f"the {kind.upper()} observation cannot be re-derived: {exc}"
        if observation.tree is None or (
            row["target_sha256"], row["head_oid"], row["git_control_sha256"], row["entry_count"]
        ) != (observation.target_sha256, observation.head_oid, observation.git_control_sha256,
              observation.entry_count):
            return None, f"the {kind.upper()} observation row is not its manifest."
        return observation, None

    def _m0_issue(self, m0: Observation, context: _DiffContext) -> str | None:
        observed = self._conn.execute(
            "SELECT git_control_sha256 FROM activation_observations WHERE execution_plan_sha256 = ?",
            (context.activation.execution_plan_sha256,),
        ).fetchone()
        if (
            m0.target_path != context.scope.path
            or m0.target_sha256 != context.scope.pre_image_sha256
            or m0.head_oid != context.scope.base_head_oid
            or observed is None or m0.git_control_sha256 != observed["git_control_sha256"]
        ):
            return "M0 is not the approved pre-image, base HEAD and activation-time .git state."
        return None

    def _write_evidence_issue(self, ticket_id: str) -> str | None:
        """Why one implementer dispatch's write is not proven exactly as
        approved, or ``None``. Re-derived entirely from stored rows and blobs:
        the consumed approval (re-verified), the completed intent, M0 and M1,
        the effect classified from them alone, the recorded claim and its
        binding, and the published handoff."""
        try:
            evidence = self._conn.execute(
                "SELECT * FROM write_evidence WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if evidence is None:
                return "the implementer dispatch has no write evidence."
            intent = self._conn.execute(
                "SELECT * FROM write_intents WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if intent is None or intent["intent_id"] != evidence["intent_id"] or intent["state"] != "completed":
                return "the write evidence is not a completed write intent of this dispatch."
            approval = self._conn.execute(
                "SELECT * FROM exact_diff_approvals WHERE approval_id = ?", (intent["exact_diff_approval_id"],)
            ).fetchone()
            if approval is None or approval["consumed_by_ticket_id"] != ticket_id:
                return "the write intent's exact-diff approval was not spent by this dispatch."
            context, attestation, issue = self._exact_diff_proof(approval)
            if issue is not None:
                return issue
            bound = (context.scope.sha256, context.activation.target_workspace_sha256)
            if (intent["write_scope_sha256"], intent["workspace_identity_sha256"]) != bound or (
                evidence["write_scope_sha256"], evidence["workspace_identity_sha256"]) != bound or (
                intent["approved_diff_artifact_sha256"] != context.artifact_sha256
            ) or evidence["m0_observation_id"] != intent["m0_observation_id"] or (
                evidence["provenance"] != EXECUTION_CLAIM_PROVENANCE
            ):
                return "the write evidence binds another scope, artifact, workspace or observation."
            m0, issue = self._observation_row(intent["m0_observation_id"], ticket_id, "m0")
            if issue is not None:
                return issue
            m1, issue = self._observation_row(evidence["m1_observation_id"], ticket_id, "m1")
            if issue is not None:
                return issue
            if (issue := self._m0_issue(m0, context)) is not None:
                return issue
            if classify_write(m0, m1, target_path=context.scope.path,
                              pre_image_sha256=context.scope.pre_image_sha256,
                              post_image_sha256=context.facts.post_image_sha256) != "as_approved":
                return "M0 and M1 do not show exactly the approved change."
            claim_row = self._conn.execute(
                "SELECT * FROM execution_claims WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if claim_row is None or (claim_row["shape"], claim_row["provenance"]) != (
                "write-result", EXECUTION_CLAIM_PROVENANCE
            ):
                return "the dispatch has no recorded write-result claim."
            data = self._blob("claims", claim_row["claim_sha256"], claim_readers.MAX_WRITE_CLAIM_BYTES)
            if len(data) != claim_row["byte_length"]:
                return "the recorded claim is not its stored bytes."
            claim = claim_readers.read_write_claim(data)
            state = _WriteState(context.activation, context.scope, approval["approval_id"], context,
                                attestation, "", intent, None)
            if (issue := _write_claim_issue(claim, state, m0, m1)) is not None:
                return issue
            handoff = self._conn.execute(
                "SELECT * FROM execution_handoffs WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if handoff is None or handoff["published_at"] is None or (
                handoff["approved_diff_artifact_sha256"], handoff["project_config_sha256"]
            ) != (context.artifact_sha256, context.config_sha256):
                return "the dispatch's handoff is not the published approved bytes."
        except (ContainmentError, ObservationError, ClaimReadError, StoreError) as exc:
            return f"the write evidence cannot be re-derived: {exc}"
        return None

    def _s3_issues(self) -> list[str]:
        """Every S3 row, explained by a chain that re-proves now, or why not."""
        issues: list[str] = []
        conn = self._conn

        def check(label: str, test: Callable[[], str | None]) -> None:
            try:
                issue = test()
            except (AuthorityRefusedError, StoreError, ContainmentError, ObservationError, ClaimReadError,
                    ValueError, TypeError, IndexError) as exc:
                issue = f"{exc}"
            if issue is not None:
                issues.append(f"{label}: {issue}")

        for row in conn.execute("SELECT * FROM activation_observations").fetchall():
            check("an activation observation", lambda row=row: None if conn.execute(
                "SELECT 1 FROM plan_activations WHERE execution_plan_sha256 = ?",
                (row["execution_plan_sha256"],)).fetchone() else "it names no activation.")

        def request_issue(row: sqlite3.Row) -> str | None:
            challenge = conn.execute(
                "SELECT subject_kind, subject_sha256 FROM approval_challenges_v2 WHERE challenge_id = ?",
                (row["challenge_id"],),
            ).fetchone()
            context = self._diff_context(row["execution_plan_sha256"], row["step_id"],
                                         row["approved_diff_artifact_sha256"], row["project_config_sha256"])
            if challenge is None or (challenge["subject_kind"], challenge["subject_sha256"]) != (
                _K.EXACT_DIFF_APPROVAL.value, context.subject
            ) or context.scope.sha256 != row["write_scope_sha256"]:
                return "it is not its challenge's subject."
            return None

        for row in conn.execute("SELECT * FROM exact_diff_requests").fetchall():
            check("an exact-diff request", lambda row=row: request_issue(row))

        def approval_issue(row: sqlite3.Row) -> str | None:
            issue = self._exact_diff_proof(row)[2]
            if issue is None and row["consumed_by_ticket_id"] is not None and conn.execute(
                "SELECT 1 FROM write_intents WHERE ticket_id = ? AND exact_diff_approval_id = ?",
                (row["consumed_by_ticket_id"], row["approval_id"]),
            ).fetchone() is None:
                issue = "it was spent by a dispatch with no write intent."
            return issue

        for row in conn.execute("SELECT * FROM exact_diff_approvals").fetchall():
            check("an exact-diff approval", lambda row=row: approval_issue(row))

        def intent_issue(row: sqlite3.Row) -> str | None:
            ticket = conn.execute("SELECT role FROM dispatch_tickets WHERE ticket_id = ?",
                                  (row["ticket_id"],)).fetchone()
            approval = conn.execute("SELECT * FROM exact_diff_approvals WHERE approval_id = ?",
                                    (row["exact_diff_approval_id"],)).fetchone()
            if ticket is None or ticket["role"] != "implementer" or approval is None or (
                approval["consumed_by_ticket_id"] != row["ticket_id"]
            ):
                return "it is not an implementer dispatch's spending of an approval."
            context, _, issue = self._exact_diff_proof(approval)
            if issue is not None:
                return issue
            if (row["write_scope_sha256"], row["approved_diff_artifact_sha256"], row["workspace_identity_sha256"]) != (
                context.scope.sha256, context.artifact_sha256, context.activation.target_workspace_sha256
            ):
                return "it binds another scope, artifact or workspace."
            m0, issue = self._observation_row(row["m0_observation_id"], row["ticket_id"], "m0")
            if issue is not None or (issue := self._m0_issue(m0, context)) is not None:
                return issue
            if conn.execute("SELECT 1 FROM execution_handoffs WHERE ticket_id = ?",
                            (row["ticket_id"],)).fetchone() is None:
                return "it has no handoff record."
            m1_rows = conn.execute(
                "SELECT observation_id FROM authority_observations WHERE ticket_id = ? AND kind = 'm1'",
                (row["ticket_id"],),
            ).fetchall()
            claimed = conn.execute("SELECT 1 FROM execution_claims WHERE ticket_id = ?",
                                   (row["ticket_id"],)).fetchone() is not None
            if row["state"] == "pending":
                return "a pending intent has an M1 or a claim." if m1_rows or claimed else None
            if row["state"] == _INTENT_COMPLETED:
                return self._write_evidence_issue(row["ticket_id"])
            if conn.execute("SELECT 1 FROM write_evidence WHERE ticket_id = ?",
                            (row["ticket_id"],)).fetchone() is not None:
                return "an unsuccessful intent has write evidence."
            if row["state"] == "refused":
                if len(m1_rows) != 1:
                    return "a refused intent has no M1."
                m1, issue = self._observation_row(m1_rows[0]["observation_id"], row["ticket_id"], "m1")
                if issue is not None:
                    return issue
                if classify_write(m0, m1, target_path=context.scope.path,
                                  pre_image_sha256=context.scope.pre_image_sha256,
                                  post_image_sha256=context.facts.post_image_sha256) != "no_change":
                    return "a refused intent's M1 shows a change."
            return None

        for row in conn.execute("SELECT * FROM write_intents").fetchall():
            check("a write intent", lambda row=row: intent_issue(row))

        def observation_issue(row: sqlite3.Row) -> str | None:
            intent = conn.execute("SELECT * FROM write_intents WHERE ticket_id = ?",
                                  (row["ticket_id"],)).fetchone()
            if row["kind"] not in ("m0", "m1") or intent is None:
                return "it is not an observation of a write handoff."
            if row["kind"] == "m0" and intent["m0_observation_id"] != row["observation_id"]:
                return "it is not its intent's M0."
            if row["kind"] == "m1" and intent["state"] == "pending":
                return "it is an M1 of a pending intent."
            return self._observation_row(row["observation_id"], row["ticket_id"], row["kind"])[1]

        for row in conn.execute("SELECT * FROM authority_observations").fetchall():
            check("an authority observation", lambda row=row: observation_issue(row))

        def handoff_issue(row: sqlite3.Row) -> str | None:
            intent = conn.execute("SELECT * FROM write_intents WHERE ticket_id = ?",
                                  (row["ticket_id"],)).fetchone()
            if intent is None:
                return "it has no write intent."
            request = conn.execute(
                "SELECT r.project_config_sha256 FROM exact_diff_approvals a JOIN exact_diff_requests r "
                "ON r.challenge_id = a.challenge_id WHERE a.approval_id = ?", (intent["exact_diff_approval_id"],)
            ).fetchone()
            if request is None or (row["approved_diff_artifact_sha256"], row["project_config_sha256"]) != (
                intent["approved_diff_artifact_sha256"], request["project_config_sha256"]
            ):
                return "it does not hand off the approved bytes."
            return None

        for row in conn.execute("SELECT * FROM execution_handoffs").fetchall():
            check("an execution handoff", lambda row=row: handoff_issue(row))

        def claim_issue(row: sqlite3.Row) -> str | None:
            intent = conn.execute("SELECT state FROM write_intents WHERE ticket_id = ?",
                                  (row["ticket_id"],)).fetchone()
            if intent is None or intent["state"] == "pending" or (row["shape"], row["provenance"]) != (
                "write-result", EXECUTION_CLAIM_PROVENANCE
            ):
                return "it is not the write-result claim of a settled write intent."
            data = self._blob("claims", row["claim_sha256"], claim_readers.MAX_WRITE_CLAIM_BYTES)
            if len(data) != row["byte_length"]:
                return "it is not its stored bytes."
            claim_readers.read_write_claim(data)
            return None

        for row in conn.execute("SELECT * FROM execution_claims").fetchall():
            check("an execution claim", lambda row=row: claim_issue(row))

        for row in conn.execute("SELECT ticket_id FROM write_evidence").fetchall():
            check("write evidence", lambda row=row: self._write_evidence_issue(row["ticket_id"]))

        for table in UNWRITTEN_TABLES:
            if conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:
                issues.append(f"{table} holds a record no authority in this store recorded.")
        return issues

    # --- proofs -------------------------------------------------------------------

    def _authority_project_issues(self, project_contract: ProjectContract, plan: ExecutionPlan) -> list[str]:
        issues = []
        if (issue := self._contract_approval_issue(project_contract)) is not None:
            issues.append(issue)
        _, issue = self._plan_issuance_issue(plan, project_contract.sha256)
        if issue is not None:
            issues.append(issue)
        issues.extend(self._unexplained_issues())
        return issues

    def _unexplained_issues(self) -> list[str]:
        """Rows no authority of this store wrote, or that no longer re-prove.
        Each one makes every run untrusted."""
        issues = []
        if self._conn.execute(
            "SELECT COUNT(*) FROM dispatch_tickets WHERE held_envelope IS NOT NULL "
            "OR held_envelope_sha256 IS NOT NULL OR held_at IS NOT NULL"
        ).fetchone()[0]:
            issues.append("a dispatch ticket is held, which nothing in this store can do yet (S6).")
        if self._conn.execute(
            "SELECT COUNT(*) FROM dispatch_tickets WHERE consumed_request_id IS NOT NULL "
            "AND role != 'implementer'"
        ).fetchone()[0]:
            issues.append("a non-implementer dispatch is answered, which nothing in this store can do yet.")
        for row in self._conn.execute(
            "SELECT t.ticket_id FROM dispatch_tickets t WHERE t.consumed_request_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM transitions r WHERE r.request_id = t.consumed_request_id "
            "AND r.event = ?)", (StepEvent.IMPLEMENTATION_RETURNED.value,)
        ):
            issues.append(f"dispatch {row['ticket_id']} is answered by no recorded implementation.")
        kinds = _in_list(kind.value for kind in _ISSUED_KINDS)
        if self._conn.execute(
            f"SELECT COUNT(*) FROM approval_challenges_v2 WHERE subject_kind NOT IN ({kinds})"
        ).fetchone()[0]:
            issues.append("an approval challenge is of a kind this store never issues.")
        if self._conn.execute(
            "SELECT COUNT(*) FROM approval_challenges_v2 c WHERE c.subject_kind = ? AND NOT EXISTS "
            "(SELECT 1 FROM exact_diff_requests r WHERE r.challenge_id = c.challenge_id)",
            (_K.EXACT_DIFF_APPROVAL.value,),
        ).fetchone()[0]:
            issues.append("an exact-diff challenge was issued for no recorded request.")
        for row in self._conn.execute(
            "SELECT challenge_id, subject_kind, subject_sha256, consumed_by FROM approval_challenges_v2 "
            "WHERE consumed_by IS NOT NULL"
        ):
            if row["subject_kind"] == _K.EXACT_DIFF_APPROVAL.value:
                approval = self._conn.execute(
                    "SELECT execution_plan_sha256, step_id FROM exact_diff_approvals WHERE challenge_id = ?",
                    (row["challenge_id"],),
                ).fetchone()
                explained = approval is not None and row["consumed_by"] == _exact_diff_consumer(
                    approval["execution_plan_sha256"], approval["step_id"]
                )
            elif row["subject_kind"] == _K.PROJECT_CONTRACT.value:
                explained = row["consumed_by"] == f"project_contract:{row['subject_sha256']}" and (
                    self._conn.execute(
                        "SELECT 1 FROM contracts WHERE sha256 = ? AND kind = 'project_contract'",
                        (row["subject_sha256"],),
                    ).fetchone() is not None
                )
            else:
                plan = row["consumed_by"].removeprefix("execution_plan:")
                explained = row["consumed_by"].startswith("execution_plan:") and (
                    self._conn.execute(
                        "SELECT 1 FROM plan_activations p JOIN approval_challenges_v2 c "
                        "ON c.challenge_id = p.challenge_id WHERE p.execution_plan_sha256 = ? "
                        "AND c.consumed_by = ?",
                        (plan, row["consumed_by"]),
                    ).fetchone() is not None
                )
            if not explained:
                issues.append("a consumed approval challenge is not explained by what it approved.")
        issues.extend(self._s3_issues())
        return issues

    def _authority_step_issues(self, step: StepRun, contract: StepContract, project: ProjectRun) -> list[str]:
        issues = []
        if (issue := self._step_issuance_issue(contract, project)) is not None:
            issues.append(issue)
        rows = self._conn.execute(
            "SELECT * FROM transitions WHERE subject_kind = 'step' AND subject_id = ? ORDER BY seq",
            (step.step_run_id,),
        ).fetchall()
        consumed = {
            ticket["consumed_request_id"]: ticket
            for ticket in self._conn.execute(
                "SELECT * FROM dispatch_tickets WHERE step_run_id = ? AND consumed_request_id IS NOT NULL",
                (step.step_run_id,),
            )
        }
        role_rows = [row for row in rows if row["event"] in _LOGGED_EVENT_ROLE]
        if len(consumed) != len(role_rows):
            issues.append("its consumed dispatch tickets are not its role-output transitions.")
        for row in role_rows:
            if row["event"] != StepEvent.IMPLEMENTATION_RETURNED.value:
                issues.append(
                    f"transition {row['seq']} records a role output, which needs an execution claim "
                    "and an authority observation this store cannot hold yet."
                )
                continue
            ticket = consumed.get(row["request_id"])
            if ticket is None or (
                ticket["role"], ticket["state_version"], ticket["attempt"], ticket["step_state"],
                ticket["project_run_id"], ticket["step_contract_sha256"],
            ) != (
                "implementer", row["from_version"], row["attempt"], row["from_state"],
                step.project_run_id, step.step_contract_sha256,
            ):
                issues.append(f"transition {row['seq']} was not bound to an AIDO dispatch.")
                continue
            if (issue := self._write_evidence_issue(ticket["ticket_id"])) is not None:
                issues.append(f"transition {row['seq']}: {issue}")
        return issues

    # --- what an integration store accepts and refuses ----------------------------

    def _authorize_step_request(
        self,
        step: StepRun,
        request: StepTransitionRequest,
        role_output: BoundRoleOutput | None,
        attestation: object,
    ):
        """S3: ``IMPLEMENTATION_RETURNED`` is accepted only for the exact
        implementer ticket whose write the store itself proves: a re-verified,
        spent exact-diff approval, a completed intent, the recorded write
        claim, M0 and M1 showing exactly the approved change, and AIDO's own
        fixed report as the payload. Every other role output is still refused
        (S4-S6)."""
        role = _EVENT_ROLE.get(request.event)
        if role is None:
            self._refuse_unconsumable_authority(request, role_output, attestation)
            return None
        if role != "implementer":
            raise AuthorityRefusedError(_unconsumable(request.event.value, role))
        consumption = ControlPlaneStore._authorize_step_request(self, step, request, role_output, attestation)
        if (issue := self._write_evidence_issue(consumption.ticket_id)) is not None:
            raise AuthorityRefusedError(f"{_unconsumable(request.event.value, role)} ({issue})")
        if request.implementation != _write_handoff_report(step.step_contract_sha256, step.attempt):
            raise AuthorityRefusedError(
                "an implementer dispatch in an integration store reports only AIDO's fixed write-handoff report."
            )
        return consumption

    def _record_verification_evidence(self, recorder_key, ticket, data):  # type: ignore[override]
        raise AuthorityRefusedError(
            "an integration store records no verification-result.v1 evidence: verification is an "
            "execution claim bound to an authority observation (FD-15), recorded only by S4's adapter."
        )


def _alpha_profile_issue(
    plan: ExecutionPlan, policy: ExecutionPolicy, scopes: tuple[WriteScopeV1, ...]
) -> str | None:
    """Why ``plan``, ``policy`` and ``scopes`` are not the FD-8a Alpha profile."""
    if not is_alpha_policy(policy):
        return (
            "an integration store activates only the Alpha policy (review and human acceptance "
            "required, one attempt)."
        )
    if len(plan.steps) != 1:
        return "an integration store activates only a one-step plan."
    if len(scopes) != 1:
        return "an integration store activates exactly one write scope."
    if scopes[0].step_id != plan.steps[0].step_id:
        return "the write scope is not for the plan's step."
    return None


def _run_prover(prove: Callable[..., IdentityBoundaryProof], expected: str | None) -> IdentityBoundaryProof:
    try:
        return prove(expected_boundary_sha256=expected)
    except IdentityBoundaryError as exc:
        raise IsolationUnprovenError(exc.category.value, exc.detail) from None
    except Exception as exc:  # noqa: BLE001 - an unprovable boundary is not a boundary
        raise IsolationUnprovenError(
            IsolationCategory.SECURITY_FACT_UNAVAILABLE.value,
            f"the identity boundary prover failed ({type(exc).__name__}).",
        ) from None


def _require_state_root(root: AidoStateRoot, proof: IdentityBoundaryProof) -> None:
    if not _same_spelling(root.path, proof.boundary.paths.state_root):
        raise IsolationUnprovenError(
            "state_root_unbound", "the state root is not the one the identity boundary declares."
        )
