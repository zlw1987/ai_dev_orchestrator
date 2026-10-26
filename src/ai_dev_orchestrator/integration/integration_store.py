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

The schema also fixes the tables S3–S6 will write (exact-diff approvals, write
intents, execution handoffs, execution claims, authority observations and the
evidence that binds them). **S2 has no writer for any of them, and no API that
accepts claim, observation or evidence bytes.** A row in one of them is
therefore unexplained, and every proof reports it as untrusted. For the same
reason every role-output event is refused here: the claim *and* the authority
observation each one requires (FD-8, FD-15) cannot exist yet, and a caller's
report, digest or model is never a substitute.

No subprocess, Git, network, model, environment read or workspace write
happens here; the boundary proof and the verifier read security facts and two
admin-owned files, nothing else. See
``docs/DL4B_S2_INTEGRATION_AUTHORITY_STORE.md``.
"""

from __future__ import annotations

import functools
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
    ExecutionPolicy,
)
from ai_dev_orchestrator.control_plane.containment import AidoStateRoot
from ai_dev_orchestrator.control_plane.contracts import validate_plan_against_contract
from ai_dev_orchestrator.control_plane.integration_records import (
    AUTHORITY_OBSERVATION_PROVENANCE,
    CLAIM_SHAPES,
    EXECUTION_CLAIM_PROVENANCE,
    OBSERVATION_KINDS,
    WRITE_INTENT_STATES,
    WriteScopeV1,
    is_alpha_policy,
    plan_activation_subject_v2_sha256,
    write_scopes_sha256,
)
from ai_dev_orchestrator.control_plane.models import (
    ExecutionPlan,
    ProjectContract,
    ProjectContractContent,
    ProjectRun,
    ReviewVerdict,
    StepContract,
    StepContractProposal,
    StepRun,
    VerificationOutcome,
)
from ai_dev_orchestrator.control_plane.store import (
    _EVENT_ROLE,
    _LOGGED_EVENT_ROLE,
    _ROLES,
    _SCHEMA,
    _TABLES,
    ControlPlaneStore,
    StateUntrustedError,
    StoreError,
    _in_list,
    _PlanIssuance,
)
from ai_dev_orchestrator.control_plane.transitions import StepTransitionRequest
from ai_dev_orchestrator.integration.attestation_verifier import (
    AttestationRefusal,
    HumanAttestationRefusedError,
    RegistryHumanAttestationVerifier,
    VerifiedHumanAttestation,
)
from ai_dev_orchestrator.integration.identity_boundary import (
    IdentityBoundaryError,
    IdentityBoundaryProof,
    IsolationCategory,
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
CREATE TABLE exact_diff_approvals (
    approval_id TEXT PRIMARY KEY,
    execution_plan_sha256 TEXT NOT NULL REFERENCES plan_activations (execution_plan_sha256),
    step_id TEXT NOT NULL,
    write_scope_sha256 TEXT NOT NULL,
    approved_diff_artifact_sha256 TEXT NOT NULL,
    challenge_id TEXT NOT NULL UNIQUE REFERENCES approval_challenges_v2 (challenge_id),
    consumed_by_ticket_id TEXT UNIQUE REFERENCES dispatch_tickets (ticket_id),
    recorded_at TEXT NOT NULL
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
    handoff_directory_identity TEXT NOT NULL,
    outbox_directory_identity TEXT NOT NULL,
    created_at TEXT NOT NULL
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
_V4_TABLES = _TABLES | {
    "approval_challenges_v2",
    "plan_activations",
    "write_scopes",
    "step_contract_issuances",
    "dispatch_tickets",
    *LATER_SLICE_TABLES,
}
#: The approval kinds S2 issues and consumes. Exact-diff approval is S3's and
#: step acceptance v2 is S6's: a challenge of either kind is unexplained here.
_S2_KINDS = (_K.PROJECT_CONTRACT, _K.PLAN_ACTIVATION)

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
    ) -> IntegrationStore:
        """Prove the boundary, bind it to ``root``, then open ``root``'s store.

        Nothing on disk is created or opened before the first proof passes and
        names this state root. The origin of that proof (``windows`` or
        ``injected``) is the store's, for its whole life.
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
        context = _IntegrationContext(root=root, prove=prove, verifier=verifier, origin=origin)
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
        """Rows no S2 authority wrote. Each one makes every run untrusted."""
        issues = []
        for table in LATER_SLICE_TABLES:
            if self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:
                issues.append(f"{table} holds a record no authority in this store recorded.")
        if self._conn.execute(
            "SELECT COUNT(*) FROM dispatch_tickets WHERE consumed_request_id IS NOT NULL "
            "OR held_envelope IS NOT NULL OR held_envelope_sha256 IS NOT NULL OR held_at IS NOT NULL"
        ).fetchone()[0]:
            issues.append("a dispatch ticket is answered or held, which nothing in this store can do.")
        kinds = _in_list(kind.value for kind in _S2_KINDS)
        if self._conn.execute(
            f"SELECT COUNT(*) FROM approval_challenges_v2 WHERE subject_kind NOT IN ({kinds})"
        ).fetchone()[0]:
            issues.append("an approval challenge is of a kind this store never issues.")
        for row in self._conn.execute(
            "SELECT subject_kind, subject_sha256, consumed_by FROM approval_challenges_v2 "
            "WHERE consumed_by IS NOT NULL"
        ):
            if row["subject_kind"] == _K.PROJECT_CONTRACT.value:
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
        return issues

    def _authority_step_issues(self, step: StepRun, contract: StepContract, project: ProjectRun) -> list[str]:
        issues = []
        if (issue := self._step_issuance_issue(contract, project)) is not None:
            issues.append(issue)
        for row in self._conn.execute(
            "SELECT seq, event FROM transitions WHERE subject_kind = 'step' AND subject_id = ? ORDER BY seq",
            (step.step_run_id,),
        ):
            if row["event"] in _LOGGED_EVENT_ROLE:
                issues.append(
                    f"transition {row['seq']} records a role output, which needs an execution claim "
                    "and an authority observation this store cannot hold yet."
                )
        return issues

    # --- what an integration store refuses in S2 ---------------------------------

    def _authorize_step_request(
        self,
        step: StepRun,
        request: StepTransitionRequest,
        role_output: BoundRoleOutput | None,
        attestation: object,
    ) -> None:
        role = _EVENT_ROLE.get(request.event)
        if role is None:
            self._refuse_unconsumable_authority(request, role_output, attestation)
            return None
        raise AuthorityRefusedError(_unconsumable(request.event.value, role))

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
