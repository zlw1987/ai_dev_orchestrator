"""DL-1 — SQLite persistence of control-plane state (roadmap §12–§13).

SQLite is the orchestration **state** authority: mutable, transactional, the
current position. Immutable evidence artifacts stay the provenance authority,
and this store holds only their digests (``evidence_sha256`` on role outputs is
validated but not stored here in DL-1; the transition log keeps each request's
digest). The two never merge.

Properties this module provides, each tested offline:

- **Persist before exposing.** Every write runs in one ``BEGIN IMMEDIATE``
  transaction with ``synchronous=FULL``. A transition is returned to the caller
  only after ``COMMIT`` has returned; an exception anywhere before that rolls
  the whole act back (state row, transition row, attempt counter, project
  propagation together), so a half-applied transition cannot exist.
- **One owner.** The connection uses ``locking_mode=EXCLUSIVE`` and takes the
  exclusive lock at open, so a second store on the same file is refused
  (:class:`StoreLockedError`) rather than racing. The OS releases the lock when
  an owning process dies, which is what makes :meth:`ControlPlaneStore.recover`
  meaningful. A store exists only through :meth:`ControlPlaneStore.open`.
- **Recovery is a gate, not a convention.** Each :meth:`ControlPlaneStore.open`
  is a new session. A project run this session did not create is **not
  consumable** — no authoritative read, no transition, no new step run, no
  idempotent replay — until :meth:`ControlPlaneStore.recover` has re-proven it
  in this session (:class:`RecoveryRequiredError`). So a step left EXECUTING,
  VERIFYING or REVIEWING by an earlier session can never be advanced as though
  its external effect were still AIDO's to resume.
- **Only proven state is handed out.** Every authority-consuming path — the
  public ``get_*_run`` / ``list_step_runs`` reads, every transition, every
  dependency check and every replay — first re-proves, in one place, that:
  the run's identity is the identity it was created with (``run_bindings``);
  its transition log explains its state, version, attempt and facts; its
  contracts hash to their identities; and the project contract, execution plan,
  project run, step contract and step run agree with each other. A
  combination of individually valid objects that do not belong together is
  refused (:class:`StateUntrustedError`). The ``inspect_*`` reads return raw,
  untyped rows for diagnosis and cannot be fed to any decision.
- **Only the validator authorizes.** Every state change is decided by
  :mod:`ai_dev_orchestrator.control_plane.transitions`; this module never picks
  a state itself.
- **Caller models are re-validated.** Pydantic's ``model_copy(update=...)``
  and ``model_construct()`` skip validation, so a model reaching the store is
  no proof it ever passed its validators. Every contract and request is
  re-parsed through its exact class before use, and only that copy is used.
- **Idempotent, version-guarded requests.** A replayed request (same
  ``request_id``, same digest) returns the recorded transition and changes
  nothing — but only after the subject has been re-proven exactly as for a new
  request, and with the subject's *current* proven state alongside, so a
  duplicate is a receipt, never a permission. A reused ``request_id`` with
  different content is refused, and a stale ``expected_state_version`` is
  refused.
- **Contracts by content identity.** Each contract row is keyed by its
  SHA-256 and re-hashed on every load. A row whose body no longer hashes to its
  key is untrusted, never repaired.
- **Recovery re-proves; it never assumes.** :meth:`ControlPlaneStore.recover`
  moves every in-flight step (EXECUTING, VERIFYING, REVIEWING) to
  RECOVERY_REQUIRED, because a request having been issued says nothing about
  whether its effect happened. Any proof failure above escalates to
  HUMAN_REQUIRED.

What it does not provide: durability across power loss beyond what SQLite's
``synchronous=FULL`` gives (Windows has no directory fsync); defense against a
deliberate *consistent* rewrite of a row together with its transition log and
its creation binding, or a restore of an older database file (the operator
account is the trust root, as for the P1B ledger); defense against in-process
code that reaches the private connection; and any re-proof that would let a run
leave RECOVERY_REQUIRED or HUMAN_REQUIRED, which is later work. The database
must live under an AIDO-owned state root, never in a target repository (roadmap
§13.3); DL-1 has no target repository and only requires an absolute path in an
existing directory.
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from os import PathLike
from pathlib import Path
from typing import Any, Literal, NamedTuple, TypeVar

from pydantic import BaseModel, ValidationError

from ai_dev_orchestrator.control_plane.contracts import (
    ContractRefusedError,
    validate_plan_against_contract,
    validate_step_contract,
)
from ai_dev_orchestrator.control_plane.models import (
    IN_FLIGHT_STEP_STATES,
    TERMINAL_STEP_STATES,
    ExecutionPlan,
    ProjectContract,
    ProjectRun,
    ProjectState,
    StepContract,
    StepRun,
    StepState,
    _Strict,
    canonical_json_bytes,
)
from ai_dev_orchestrator.control_plane.transitions import (
    ProjectTransitionRequest,
    RefusalCode,
    StepEvent,
    StepTransition,
    StepTransitionRequest,
    TransitionRefused,
    decide_integrity_escalation,
    decide_project_transition,
    decide_step_transition,
    propagated_project_state,
)

STORE_SCHEMA_VERSION = "aido-control-plane-store.v2"

ContractKind = Literal["project_contract", "execution_plan", "step_contract"]
_CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "project_contract": ProjectContract,
    "execution_plan": ExecutionPlan,
    "step_contract": StepContract,
}

# The columns that fix what a run *is*. They are recorded once, at creation, in
# ``run_bindings``; no DL-1 rule ever changes them.
_PROJECT_IDENTITY = (
    "project_run_id",
    "project_id",
    "project_contract_sha256",
    "execution_plan_sha256",
    "execution_plan_version",
)
_STEP_IDENTITY = ("step_run_id", "project_run_id", "step_id", "step_contract_sha256")


def _in_list(values) -> str:
    return ", ".join(f"'{value}'" for value in values)


_STEP_STATES = _in_list(state.value for state in StepState)
_PROJECT_STATES = _in_list(state.value for state in ProjectState)

_SCHEMA = f"""
CREATE TABLE store_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE contracts (
    sha256 TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('project_contract', 'execution_plan', 'step_contract')),
    project_id TEXT NOT NULL,
    scope_sha256 TEXT NOT NULL,
    step_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    body TEXT NOT NULL,
    UNIQUE (kind, scope_sha256, step_id, version)
);
CREATE TABLE project_runs (
    project_run_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    project_contract_sha256 TEXT NOT NULL REFERENCES contracts (sha256),
    execution_plan_sha256 TEXT NOT NULL REFERENCES contracts (sha256),
    execution_plan_version INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ({_PROJECT_STATES})),
    state_version INTEGER NOT NULL CHECK (state_version >= 0)
);
CREATE TABLE step_runs (
    step_run_id TEXT PRIMARY KEY,
    project_run_id TEXT NOT NULL REFERENCES project_runs (project_run_id),
    step_id TEXT NOT NULL,
    step_contract_sha256 TEXT NOT NULL REFERENCES contracts (sha256),
    state TEXT NOT NULL CHECK (state IN ({_STEP_STATES})),
    state_version INTEGER NOT NULL CHECK (state_version >= 0),
    attempt INTEGER NOT NULL CHECK (attempt >= 0),
    verification_outcome TEXT,
    review_verdict TEXT,
    UNIQUE (project_run_id, step_id)
);
CREATE TABLE run_bindings (
    subject_id TEXT PRIMARY KEY,
    subject_kind TEXT NOT NULL CHECK (subject_kind IN ('project', 'step')),
    project_run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    binding TEXT NOT NULL,
    UNIQUE (subject_kind, project_run_id, step_id)
);
CREATE TABLE transitions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    request_sha256 TEXT NOT NULL,
    subject_kind TEXT NOT NULL CHECK (subject_kind IN ('project', 'step')),
    subject_id TEXT NOT NULL,
    event TEXT NOT NULL,
    rule TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    from_version INTEGER NOT NULL,
    to_version INTEGER NOT NULL,
    attempt INTEGER,
    verification_outcome TEXT,
    review_verdict TEXT,
    recorded_at TEXT NOT NULL
);
CREATE INDEX transitions_by_subject ON transitions (subject_kind, subject_id, seq);
"""
_TABLES = frozenset(
    {"store_meta", "contracts", "project_runs", "step_runs", "run_bindings", "transitions"}
)

# Only :meth:`ControlPlaneStore.open` holds this, so a store cannot be built
# around a connection that skipped the ownership lock and the schema check.
_OPEN_TOKEN = object()


class StoreError(Exception):
    """Base class for store failures. Messages never echo contract text."""


class StoreLockedError(StoreError):
    """Another connection owns the store. Nothing was read or written."""


class StateUntrustedError(StoreError):
    """Persisted state cannot be trusted. Nothing proceeds from it.

    :meth:`ControlPlaneStore.recover` converts this into a recorded
    HUMAN_REQUIRED escalation wherever the affected rows are still parseable.
    """


class RecoveryRequiredError(StateUntrustedError):
    """The project run has not been re-proven since this store was opened.

    Nothing was read out or changed. Call :meth:`ControlPlaneStore.recover`
    for the run first; it is what decides whether an earlier session's
    in-flight work may be trusted (it may not: it becomes RECOVERY_REQUIRED).
    """


class RecordNotFoundError(StoreError):
    """No run or contract has the requested identity."""


class TransitionRecord(_Strict):
    seq: int
    request_id: str
    request_sha256: str
    subject_kind: Literal["project", "step"]
    subject_id: str
    event: str
    rule: str
    from_state: str
    to_state: str
    from_version: int
    to_version: int
    attempt: int | None
    verification_outcome: str | None
    review_verdict: str | None
    recorded_at: str


class AppliedTransition(_Strict):
    """A committed transition, or the receipt for one already committed.

    ``duplicate`` means an identical request had already been applied and
    nothing changed now. A duplicate is a **receipt, not a permission**: its
    ``record`` may describe a state the subject has long since left (an
    EXECUTING that recovery has since made RECOVERY_REQUIRED). ``current_state``
    and ``current_state_version`` are the subject's proven state at the time of
    this call; a caller acts on those, never on a duplicate's ``record``, and
    never dispatches an external effect because a duplicate came back.
    """

    record: TransitionRecord
    duplicate: bool
    current_state: str
    current_state_version: int


class RecoveryReport(_Strict):
    project_run_id: str
    integrity_ok: bool
    integrity_issues: tuple[str, ...]
    recovered_step_run_ids: tuple[str, ...]
    escalated_step_run_ids: tuple[str, ...]
    project_state: ProjectState


class UnverifiedRunRow(_Strict):
    """A run row exactly as stored, **not** re-proven. Diagnostic only.

    It is deliberately not a :class:`ProjectRun` or :class:`StepRun`: its
    values are raw column values, so it cannot be handed to the validator, and
    nothing about it is proof of anything. Authoritative reads are
    :meth:`ControlPlaneStore.get_project_run`,
    :meth:`ControlPlaneStore.get_step_run` and
    :meth:`ControlPlaneStore.list_step_runs`.
    """

    subject_kind: Literal["project", "step"]
    columns: dict[str, Any]


class _ProjectContext(NamedTuple):
    project_contract: ProjectContract
    plan: ExecutionPlan


_M = TypeVar("_M", bound=BaseModel)


def _revalidated(model_type: type[_M], value: object) -> _M:
    """Re-parse a caller's model through ``model_type`` and return the copy.

    ``model_copy(update=...)`` and ``model_construct()`` build instances that
    never ran their validators, and a subclass may override any property. The
    JSON round trip through the exact class re-runs every field and model
    validator, and the returned copy is the only object the store then uses.
    """
    if not isinstance(value, model_type):
        raise TypeError(f"expected a {model_type.__name__}.")
    return model_type.model_validate_json(value.model_dump_json(warnings=False))


_REVALIDATION_ERRORS = (ValueError, TypeError, AttributeError)


def new_request_id() -> str:
    """A fresh AIDO idempotency key for one transition request."""
    return uuid.uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _derived_request_id(request_id: str, label: str) -> str:
    return hashlib.sha256(f"{request_id}:{label}".encode()).hexdigest()[:32]


def _binding(subject_kind: str, run: ProjectRun | StepRun) -> str:
    names = _PROJECT_IDENTITY if subject_kind == "project" else _STEP_IDENTITY
    return canonical_json_bytes({name: getattr(run, name) for name in names}).decode("utf-8")


def _untrusted(issues: list[str]) -> StateUntrustedError:
    return StateUntrustedError(" ".join(issues) + " recover() records the escalation.")


class ControlPlaneStore:
    """The single writer of DL-1 control-plane state. Open with :meth:`open`."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        clock: Callable[[], datetime],
        *,
        _open_token: object = None,
    ) -> None:
        if _open_token is not _OPEN_TOKEN:
            raise StoreError(
                "a store is created only by ControlPlaneStore.open(), which takes ownership "
                "and checks the schema."
            )
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
        self._clock = clock
        # Project runs this session may consume: created here, or re-proven by
        # recover() here. Deliberately in memory only, so every open starts
        # empty and an earlier session's state is never trusted by default.
        self._proven_runs: set[str] = set()

    # --- lifecycle -------------------------------------------------------

    @classmethod
    def open(
        cls, path: str | PathLike[str], *, clock: Callable[[], datetime] | None = None
    ) -> ControlPlaneStore:
        """Open (creating if new) the store at ``path`` and take ownership.

        Refuses a relative path and a missing parent directory. Refuses a file
        that is not this store's schema as untrusted, and a store another
        connection owns as locked. Creates no directory. Every run already in
        the file must be re-proven with :meth:`recover` before it is consumed.
        """
        db_path = Path(path)
        if not db_path.is_absolute():
            raise StoreError("the store path must be absolute.")
        if not db_path.parent.is_dir():
            raise StoreError("the store's parent directory must already exist.")
        connection = sqlite3.connect(str(db_path), isolation_level=None, timeout=0)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("PRAGMA locking_mode = EXCLUSIVE")
            connection.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            connection.close()
            if "locked" in str(exc):
                raise StoreLockedError("another connection owns this store.") from exc
            raise StateUntrustedError("the store file could not be opened as a database.") from exc
        except sqlite3.DatabaseError as exc:
            connection.close()
            raise StateUntrustedError("the store file is not a database.") from exc
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
            if not tables:
                for statement in _SCHEMA.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                connection.execute(
                    "INSERT INTO store_meta (key, value) VALUES ('schema_version', ?)",
                    (STORE_SCHEMA_VERSION,),
                )
            else:
                row = (
                    connection.execute(
                        "SELECT value FROM store_meta WHERE key = 'schema_version'"
                    ).fetchone()
                    if "store_meta" in tables
                    else None
                )
                if tables != _TABLES or row is None or row[0] != STORE_SCHEMA_VERSION:
                    raise StateUntrustedError(
                        "the store file does not carry this store's schema version."
                    )
            connection.execute("COMMIT")
        except BaseException as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            connection.close()
            if isinstance(exc, sqlite3.DatabaseError):
                raise StateUntrustedError("the store file is not a readable database.") from exc
            raise
        return cls(connection, clock or _utc_now, _open_token=_OPEN_TOKEN)

    def close(self) -> None:
        """Release ownership. Committed state is already durable."""
        self._conn.close()

    def __enter__(self) -> ControlPlaneStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    # --- contracts -------------------------------------------------------

    def record_project_contract(self, contract: ProjectContract) -> str:
        """Persist an approved Project Contract; returns its identity."""
        contract = self._revalidated_contract(ProjectContract, contract)
        with self._transaction():
            self._insert_contract(
                "project_contract", contract, contract.project_id, contract.sha256, "", 1
            )
        return contract.sha256

    def record_execution_plan(self, plan: ExecutionPlan) -> str:
        """Persist one plan version. Version N must supersede stored version N-1."""
        plan = self._revalidated_contract(ExecutionPlan, plan)
        with self._transaction():
            project_contract = self._load_contract(
                plan.project_contract_sha256, "project_contract"
            )
            validate_plan_against_contract(plan, project_contract)
            if plan.supersedes_sha256 is not None:
                previous = self._load_contract(plan.supersedes_sha256, "execution_plan")
                if (
                    previous.project_contract_sha256 != plan.project_contract_sha256
                    or previous.plan_version != plan.plan_version - 1
                ):
                    raise ContractRefusedError(
                        "execution plan does not supersede the previous version of this "
                        "project contract's plan."
                    )
            self._insert_contract(
                "execution_plan",
                plan,
                plan.project_id,
                plan.project_contract_sha256,
                "",
                plan.plan_version,
            )
        return plan.sha256

    def record_step_contract(self, contract: StepContract) -> str:
        """Persist a Step Contract after re-running every issuance rule."""
        contract = self._revalidated_contract(StepContract, contract)
        with self._transaction():
            project_contract = self._load_contract(
                contract.project_contract_sha256, "project_contract"
            )
            plan = self._load_contract(contract.execution_plan_sha256, "execution_plan")
            validate_step_contract(
                contract, project_contract=project_contract, execution_plan=plan
            )
            if contract.supersedes_sha256 is not None:
                previous = self._load_contract(contract.supersedes_sha256, "step_contract")
                if (
                    previous.project_id != contract.project_id
                    or previous.step_id != contract.step_id
                    or previous.step_contract_version != contract.step_contract_version - 1
                ):
                    raise ContractRefusedError(
                        "step contract does not supersede the previous version of this step's "
                        "contract."
                    )
            self._insert_contract(
                "step_contract",
                contract,
                contract.project_id,
                contract.execution_plan_sha256,
                contract.step_id,
                contract.step_contract_version,
            )
        return contract.sha256

    def get_project_contract(self, sha256: str) -> ProjectContract:
        return self._load_contract(sha256, "project_contract")

    def get_execution_plan(self, sha256: str) -> ExecutionPlan:
        return self._load_contract(sha256, "execution_plan")

    def get_step_contract(self, sha256: str) -> StepContract:
        return self._load_contract(sha256, "step_contract")

    def list_execution_plans(self, project_contract_sha256: str) -> tuple[ExecutionPlan, ...]:
        """Every recorded plan version of one Project Contract, oldest first.

        Added for DL-3, read-only. Each plan is re-proven like any contract
        load, and the set must be the unbroken chain ``record_execution_plan``
        builds — versions 1..N, each superseding the one before — or the read
        raises :class:`StateUntrustedError`. Recording a plan authorizes
        nothing, so this is a statement of what is *recorded*, never of which
        plan any run may execute: a project run executes only the plan it was
        created with.
        """
        rows = self._conn.execute(
            "SELECT sha256, project_id, version FROM contracts "
            "WHERE kind = 'execution_plan' AND scope_sha256 = ? ORDER BY version",
            (project_contract_sha256,),
        ).fetchall()
        plans: list[ExecutionPlan] = []
        for row in rows:
            plan = self._load_contract(row["sha256"], "execution_plan")
            previous = plans[-1] if plans else None
            if (
                plan.project_contract_sha256 != project_contract_sha256
                or plan.project_id != row["project_id"]
                or plan.plan_version != row["version"]
                or plan.plan_version != len(plans) + 1
                or plan.supersedes_sha256 != (previous.sha256 if previous else None)
            ):
                raise StateUntrustedError(
                    "the recorded execution plans of this project contract are not one "
                    "unbroken version chain."
                )
            plans.append(plan)
        return tuple(plans)

    @staticmethod
    def _revalidated_contract(model_type: type[_M], contract: object) -> _M:
        try:
            return _revalidated(model_type, contract)
        except _REVALIDATION_ERRORS as exc:
            raise ContractRefusedError(
                f"the {model_type.__name__} does not validate; a model built without "
                "validation is never persisted."
            ) from exc

    def _insert_contract(
        self,
        kind: ContractKind,
        contract: BaseModel,
        project_id: str,
        scope_sha256: str,
        step_id: str,
        version: int,
    ) -> None:
        sha256 = contract.sha256  # type: ignore[attr-defined]
        existing = self._conn.execute(
            "SELECT kind FROM contracts WHERE sha256 = ?", (sha256,)
        ).fetchone()
        if existing is not None:
            if existing["kind"] != kind:
                raise StateUntrustedError("a stored contract of another kind has this digest.")
            self._load_contract(sha256, kind)  # re-proves the stored body
            return
        try:
            self._conn.execute(
                "INSERT INTO contracts (sha256, kind, project_id, scope_sha256, step_id, "
                "version, body) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sha256, kind, project_id, scope_sha256, step_id, version,
                 contract.model_dump_json()),
            )
        except sqlite3.IntegrityError as exc:
            raise ContractRefusedError(
                f"a different {kind} already holds version {version} in this scope."
            ) from exc

    def _load_contract(self, sha256: str, kind: ContractKind):
        row = self._conn.execute(
            "SELECT kind, body FROM contracts WHERE sha256 = ?", (sha256,)
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"no stored {kind} has that digest.")
        if row["kind"] != kind:
            raise StateUntrustedError(f"the stored contract with that digest is not a {kind}.")
        try:
            contract = _CONTRACT_MODELS[kind].model_validate_json(row["body"])
        except ValidationError as exc:
            raise StateUntrustedError(f"a stored {kind} no longer validates.") from exc
        if contract.sha256 != sha256:  # type: ignore[attr-defined]
            raise StateUntrustedError(f"a stored {kind} no longer hashes to its identity.")
        return contract

    # --- runs ------------------------------------------------------------

    def create_project_run(
        self, *, project_contract_sha256: str, execution_plan_sha256: str
    ) -> ProjectRun:
        """Start a project run bound to one contract and one plan version."""
        with self._transaction():
            project_contract = self._load_contract(project_contract_sha256, "project_contract")
            plan = self._load_contract(execution_plan_sha256, "execution_plan")
            validate_plan_against_contract(plan, project_contract)
            run = ProjectRun(
                project_run_id=uuid.uuid4().hex,
                project_id=project_contract.project_id,
                project_contract_sha256=project_contract.sha256,
                execution_plan_sha256=plan.sha256,
                execution_plan_version=plan.plan_version,
                state=ProjectState.ACTIVE,
                state_version=0,
            )
            self._conn.execute(
                "INSERT INTO project_runs (project_run_id, project_id, project_contract_sha256, "
                "execution_plan_sha256, execution_plan_version, state, state_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run.project_run_id, run.project_id, run.project_contract_sha256,
                 run.execution_plan_sha256, run.execution_plan_version, run.state.value,
                 run.state_version),
            )
            self._insert_binding("project", run, run.project_run_id, "")
        self._proven_runs.add(run.project_run_id)
        return run

    def create_step_run(self, *, project_run_id: str, step_contract_sha256: str) -> StepRun:
        """Start a step run under an ACTIVE, proven project run, bound to one contract."""
        with self._transaction():
            project, context = self._proven_project(project_run_id)
            if project.state is not ProjectState.ACTIVE:
                raise TransitionRefused(
                    RefusalCode.PROJECT_NOT_ACTIVE, f"project is {project.state.value}."
                )
            contract = self._load_contract(step_contract_sha256, "step_contract")
            try:
                validate_step_contract(
                    contract,
                    project_contract=context.project_contract,
                    execution_plan=context.plan,
                )
            except ContractRefusedError as exc:
                raise ContractRefusedError(
                    "step contract binds a different project contract or execution plan than "
                    f"the project run: {exc}"
                ) from exc
            step = StepRun(
                step_run_id=uuid.uuid4().hex,
                project_run_id=project.project_run_id,
                step_id=contract.step_id,
                step_contract_sha256=contract.sha256,
                state=StepState.PLANNED,
                state_version=0,
                attempt=0,
            )
            try:
                self._conn.execute(
                    "INSERT INTO step_runs (step_run_id, project_run_id, step_id, "
                    "step_contract_sha256, state, state_version, attempt) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (step.step_run_id, step.project_run_id, step.step_id,
                     step.step_contract_sha256, step.state.value, step.state_version,
                     step.attempt),
                )
                # Also refuses re-creating a step whose earlier run row is gone.
                self._insert_binding("step", step, step.project_run_id, step.step_id)
            except sqlite3.IntegrityError as exc:
                raise ContractRefusedError(
                    "this project run already has a step run for that step."
                ) from exc
        return step

    def _insert_binding(
        self, subject_kind: str, run: ProjectRun | StepRun, project_run_id: str, step_id: str
    ) -> None:
        subject_id = run.project_run_id if subject_kind == "project" else run.step_run_id
        self._conn.execute(
            "INSERT INTO run_bindings (subject_id, subject_kind, project_run_id, step_id, "
            "binding) VALUES (?, ?, ?, ?, ?)",
            (subject_id, subject_kind, project_run_id, step_id, _binding(subject_kind, run)),
        )

    # --- authoritative reads ----------------------------------------------

    def get_project_run(self, project_run_id: str) -> ProjectRun:
        """The project run, re-proven. Raises rather than return unproven state."""
        project, _ = self._proven_project(project_run_id)
        return project

    def get_step_run(self, step_run_id: str) -> StepRun:
        """The step run, re-proven together with its project and contracts."""
        step, _, _ = self._proven_step_by_id(step_run_id)
        return step

    def list_step_runs(self, project_run_id: str) -> tuple[StepRun, ...]:
        """Every step run of a project run, each re-proven. One failure fails all."""
        project, context = self._project_integrity(project_run_id)
        rows = self._conn.execute(
            "SELECT * FROM step_runs WHERE project_run_id = ? ORDER BY rowid", (project_run_id,)
        ).fetchall()
        steps = tuple(
            self._proven_step(self._parse_step_row(row), project, context)[0] for row in rows
        )
        self._require_recovered(project_run_id)
        return steps

    # --- diagnostic reads (never proof) -----------------------------------

    def inspect_project_run(self, project_run_id: str) -> UnverifiedRunRow:
        """The raw project row. Diagnostic only; see :class:`UnverifiedRunRow`."""
        row = self._conn.execute(
            "SELECT * FROM project_runs WHERE project_run_id = ?", (project_run_id,)
        ).fetchone()
        if row is None:
            raise RecordNotFoundError("no project run has that id.")
        return UnverifiedRunRow(subject_kind="project", columns=dict(row))

    def inspect_step_run(self, step_run_id: str) -> UnverifiedRunRow:
        """The raw step row. Diagnostic only; see :class:`UnverifiedRunRow`."""
        row = self._conn.execute(
            "SELECT * FROM step_runs WHERE step_run_id = ?", (step_run_id,)
        ).fetchone()
        if row is None:
            raise RecordNotFoundError("no step run has that id.")
        return UnverifiedRunRow(subject_kind="step", columns=dict(row))

    def inspect_step_runs(self, project_run_id: str) -> tuple[UnverifiedRunRow, ...]:
        """The raw step rows of a project run. Diagnostic only."""
        rows = self._conn.execute(
            "SELECT * FROM step_runs WHERE project_run_id = ? ORDER BY rowid", (project_run_id,)
        ).fetchall()
        return tuple(UnverifiedRunRow(subject_kind="step", columns=dict(row)) for row in rows)

    def transitions_for(self, subject_id: str) -> tuple[TransitionRecord, ...]:
        """The raw transition log of one subject. An audit read, not proof."""
        rows = self._conn.execute(
            "SELECT * FROM transitions WHERE subject_id = ? ORDER BY seq", (subject_id,)
        ).fetchall()
        try:
            return tuple(TransitionRecord.model_validate(dict(row)) for row in rows)
        except ValidationError as exc:
            raise StateUntrustedError("a stored transition record no longer validates.") from exc

    def _load_project_run(self, project_run_id: str) -> ProjectRun:
        row = self._conn.execute(
            "SELECT * FROM project_runs WHERE project_run_id = ?", (project_run_id,)
        ).fetchone()
        if row is None:
            raise RecordNotFoundError("no project run has that id.")
        try:
            return ProjectRun.model_validate(dict(row))
        except ValidationError as exc:
            raise StateUntrustedError("a stored project run no longer validates.") from exc

    def _load_step_run(self, step_run_id: str) -> StepRun:
        row = self._conn.execute(
            "SELECT * FROM step_runs WHERE step_run_id = ?", (step_run_id,)
        ).fetchone()
        if row is None:
            raise RecordNotFoundError("no step run has that id.")
        return self._parse_step_row(row)

    @staticmethod
    def _parse_step_row(row: sqlite3.Row) -> StepRun:
        try:
            return StepRun.model_validate(dict(row))
        except ValidationError as exc:
            raise StateUntrustedError("a stored step run no longer validates.") from exc

    # --- proof at the consumption boundary ---------------------------------

    def _proven_project(self, project_run_id: str) -> tuple[ProjectRun, _ProjectContext]:
        """The project run and its contracts, or a refusal. Every consumer of a
        project run, and of any step in it, comes through here."""
        project, context = self._project_integrity(project_run_id)
        self._require_recovered(project_run_id)
        return project, context

    def _project_integrity(self, project_run_id: str) -> tuple[ProjectRun, _ProjectContext]:
        project = self._load_project_run(project_run_id)
        issues, context = self._project_issues(project)
        if issues:
            raise _untrusted(issues)
        return project, context

    def _require_recovered(self, project_run_id: str) -> None:
        if project_run_id not in self._proven_runs:
            raise RecoveryRequiredError(
                f"project run {project_run_id} has not been re-proven by recover() since this "
                "store was opened; nothing in it may be read as authority or advanced."
            )

    def _proven_step_by_id(
        self, step_run_id: str
    ) -> tuple[StepRun, StepContract, tuple[ProjectRun, _ProjectContext]]:
        step = self._load_step_run(step_run_id)
        # The row names its own project; prove that name before following it.
        if (issue := self._binding_issue("step", step)) is not None:
            raise _untrusted([issue])
        project, context = self._project_integrity(step.project_run_id)
        step, contract = self._proven_step(step, project, context)
        # Integrity first, so an untrusted row is reported as untrusted; then
        # the session gate, which no proven row gets past either.
        self._require_recovered(step.project_run_id)
        return step, contract, (project, context)

    def _proven_step(
        self, step: StepRun, project: ProjectRun, context: _ProjectContext
    ) -> tuple[StepRun, StepContract]:
        issues, contract = self._step_issues(step, project, context)
        if issues:
            raise _untrusted(issues)
        return step, contract

    def _project_issues(
        self, project: ProjectRun
    ) -> tuple[list[str], _ProjectContext | None]:
        """Every reason the project run is not what AIDO created and recorded."""
        issues = [
            issue
            for issue in (self._binding_issue("project", project),
                          self._chain_issue("project", project))
            if issue is not None
        ]
        bound = {
            row[0]
            for row in self._conn.execute(
                "SELECT subject_id FROM run_bindings WHERE subject_kind = 'step' "
                "AND project_run_id = ?",
                (project.project_run_id,),
            )
        }
        present = {
            row[0]
            for row in self._conn.execute(
                "SELECT step_run_id FROM step_runs WHERE project_run_id = ?",
                (project.project_run_id,),
            )
        }
        if bound != present:
            issues.append(
                f"project {project.project_run_id}: its step runs are not the step runs created "
                "under it."
            )
        try:
            project_contract = self._load_contract(
                project.project_contract_sha256, "project_contract"
            )
            plan = self._load_contract(project.execution_plan_sha256, "execution_plan")
            validate_plan_against_contract(plan, project_contract)
        except (StoreError, ContractRefusedError) as exc:
            issues.append(f"project {project.project_run_id}: {exc}")
            return issues, None
        if (
            project.project_id != project_contract.project_id
            or project.execution_plan_version != plan.plan_version
        ):
            issues.append(
                f"project {project.project_run_id}: run does not match its project contract "
                "and plan."
            )
        return issues, _ProjectContext(project_contract, plan)

    def _step_issues(
        self, step: StepRun, project: ProjectRun, context: _ProjectContext | None
    ) -> tuple[list[str], StepContract | None]:
        """Every reason the step run, with its contract, does not belong to this
        project run, contract and plan exactly as created."""
        issues = [
            issue
            for issue in (self._binding_issue("step", step), self._chain_issue("step", step))
            if issue is not None
        ]
        if step.project_run_id != project.project_run_id:
            issues.append(f"step {step.step_run_id}: belongs to another project run.")
        try:
            contract = self._load_contract(step.step_contract_sha256, "step_contract")
        except StoreError as exc:
            issues.append(f"step {step.step_run_id}: {exc}")
            return issues, None
        if contract.step_id != step.step_id:
            issues.append(f"step {step.step_run_id}: its contract is another step's contract.")
        if context is None:
            issues.append(f"step {step.step_run_id}: its project contract and plan are unproven.")
        else:
            try:
                validate_step_contract(
                    contract,
                    project_contract=context.project_contract,
                    execution_plan=context.plan,
                )
            except ContractRefusedError as exc:
                issues.append(f"step {step.step_run_id}: contract binds another run: {exc}")
        return issues, contract

    def _binding_issue(self, subject_kind: str, run: ProjectRun | StepRun) -> str | None:
        """Why the run's identity is not the identity it was created with."""
        subject_id = run.project_run_id if subject_kind == "project" else run.step_run_id
        row = self._conn.execute(
            "SELECT subject_kind, binding FROM run_bindings WHERE subject_id = ?", (subject_id,)
        ).fetchone()
        if (
            row is None
            or row["subject_kind"] != subject_kind
            or row["binding"] != _binding(subject_kind, run)
        ):
            return (
                f"{subject_kind} {subject_id}: identity or contract binding is not the one it was "
                "created with."
            )
        return None

    # --- transitions -----------------------------------------------------

    def apply_step_transition(
        self, step_run_id: str, request: StepTransitionRequest
    ) -> AppliedTransition:
        """Decide one step event with the validator and persist it atomically.

        Returns only after the transaction has committed. Raises
        :class:`TransitionRefused` (nothing changed),
        :class:`RecoveryRequiredError` (nothing changed; run :meth:`recover`
        first) or :class:`StateUntrustedError` (nothing changed; run
        :meth:`recover`). The step is re-proven before anything else, a replay
        included.
        """
        request = self._revalidated_request(StepTransitionRequest, request)
        with self._transaction():
            step, contract, (project, context) = self._proven_step_by_id(step_run_id)
            replay = self._replayed(request.request_id, request.request_sha256, "step", step_run_id)
            if replay is not None:
                return AppliedTransition(
                    record=replay,
                    duplicate=True,
                    current_state=step.state.value,
                    current_state_version=step.state_version,
                )
            decision = decide_step_transition(
                step=step,
                contract=contract,
                project_state=project.state,
                dependencies_complete=self._dependencies_complete(
                    project, context, contract.depends_on
                ),
                request=request,
            )
            record = self._write_step(step, decision, request.request_id,
                                      request.request_sha256, request.event.value)
            self._propagate(project, decision, request.request_id, request.request_sha256)
        return AppliedTransition(
            record=record,
            duplicate=False,
            current_state=record.to_state,
            current_state_version=record.to_version,
        )

    def apply_project_transition(
        self, project_run_id: str, request: ProjectTransitionRequest
    ) -> AppliedTransition:
        """Decide one project event with the validator and persist it atomically.

        The project is re-proven before anything else, a replay included.
        """
        request = self._revalidated_request(ProjectTransitionRequest, request)
        with self._transaction():
            project, _ = self._proven_project(project_run_id)
            replay = self._replayed(
                request.request_id, request.request_sha256, "project", project_run_id
            )
            if replay is not None:
                return AppliedTransition(
                    record=replay,
                    duplicate=True,
                    current_state=project.state.value,
                    current_state_version=project.state_version,
                )
            decision = decide_project_transition(project=project, request=request)
            record = self._write_project(
                project, decision.to_state, decision.rule, request.request_id,
                request.request_sha256, request.event.value,
            )
        return AppliedTransition(
            record=record,
            duplicate=False,
            current_state=record.to_state,
            current_state_version=record.to_version,
        )

    @staticmethod
    def _revalidated_request(model_type: type[_M], request: object) -> _M:
        try:
            return _revalidated(model_type, request)
        except _REVALIDATION_ERRORS as exc:
            raise TransitionRefused(
                RefusalCode.INVALID_REQUEST,
                f"the {model_type.__name__} does not validate; a request built without "
                "validation is never applied.",
            ) from exc

    def _replayed(
        self, request_id: str, request_sha256: str, subject_kind: str, subject_id: str
    ) -> TransitionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM transitions WHERE request_id = ?", (request_id,)
        ).fetchone()
        if row is None:
            return None
        if (
            row["request_sha256"] != request_sha256
            or row["subject_kind"] != subject_kind
            or row["subject_id"] != subject_id
        ):
            raise TransitionRefused(
                RefusalCode.DUPLICATE_REQUEST_CONFLICT,
                "this request_id was already used for a different request.",
            )
        return TransitionRecord.model_validate(dict(row))

    def _dependencies_complete(
        self, project: ProjectRun, context: _ProjectContext, depends_on: tuple[str, ...]
    ) -> bool:
        """Every dependency has a step run whose COMPLETE is fully re-proven.

        A dependency is proven exactly like the step itself — binding, log,
        contract and project — before its state is believed, so a COMPLETE
        written outside the transition log, or a dependency re-bound to another
        contract, raises :class:`StateUntrustedError` instead of releasing its
        dependents.
        """
        for step_id in depends_on:
            row = self._conn.execute(
                "SELECT * FROM step_runs WHERE project_run_id = ? AND step_id = ?",
                (project.project_run_id, step_id),
            ).fetchone()
            if row is None:
                return False
            dependency, _ = self._proven_step(self._parse_step_row(row), project, context)
            if dependency.state is not StepState.COMPLETE:
                return False
        return True

    def _write_step(
        self,
        step: StepRun,
        decision: StepTransition,
        request_id: str,
        request_sha256: str,
        event: str,
    ) -> TransitionRecord:
        record = self._insert_transition(
            request_id=request_id,
            request_sha256=request_sha256,
            subject_kind="step",
            subject_id=step.step_run_id,
            event=event,
            rule=decision.rule,
            from_state=decision.from_state.value,
            to_state=decision.to_state.value,
            from_version=decision.from_version,
            to_version=decision.to_version,
            attempt=decision.attempt,
            verification_outcome=decision.verification_outcome,
            review_verdict=decision.review_verdict,
        )
        self._update_step_row(step.step_run_id, decision)
        return record

    def _update_step_row(self, step_run_id: str, decision: StepTransition) -> None:
        updated = self._conn.execute(
            "UPDATE step_runs SET state = ?, state_version = ?, attempt = ?, "
            "verification_outcome = ?, review_verdict = ? "
            "WHERE step_run_id = ? AND state_version = ?",
            (decision.to_state.value, decision.to_version, decision.attempt,
             decision.verification_outcome, decision.review_verdict, step_run_id,
             decision.from_version),
        ).rowcount
        if updated != 1:
            raise StateUntrustedError("the step run changed underneath its own transaction.")

    def _write_project(
        self,
        project: ProjectRun,
        to_state: ProjectState,
        rule: str,
        request_id: str,
        request_sha256: str,
        event: str,
    ) -> TransitionRecord:
        record = self._insert_transition(
            request_id=request_id,
            request_sha256=request_sha256,
            subject_kind="project",
            subject_id=project.project_run_id,
            event=event,
            rule=rule,
            from_state=project.state.value,
            to_state=to_state.value,
            from_version=project.state_version,
            to_version=project.state_version + 1,
            attempt=None,
            verification_outcome=None,
            review_verdict=None,
        )
        updated = self._conn.execute(
            "UPDATE project_runs SET state = ?, state_version = ? "
            "WHERE project_run_id = ? AND state_version = ?",
            (to_state.value, project.state_version + 1, project.project_run_id,
             project.state_version),
        ).rowcount
        if updated != 1:
            raise StateUntrustedError("the project run changed underneath its own transaction.")
        return record

    def _propagate(
        self, project: ProjectRun, decision: StepTransition, request_id: str, request_sha256: str
    ) -> ProjectRun:
        if decision.project_effect is None:
            return project
        to_state = propagated_project_state(project.state, decision.project_effect)
        if to_state is None:
            return project
        self._write_project(
            project, to_state, f"propagated:{decision.rule}",
            _derived_request_id(request_id, "project"), request_sha256, "step_propagation",
        )
        return self._load_project_run(project.project_run_id)

    def _insert_transition(self, **fields) -> TransitionRecord:
        fields["recorded_at"] = self._clock().astimezone(timezone.utc).isoformat()
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cursor = self._conn.execute(
            f"INSERT INTO transitions ({columns}) VALUES ({placeholders})", tuple(fields.values())
        )
        return TransitionRecord(seq=cursor.lastrowid, **fields)

    # --- integrity and recovery -----------------------------------------

    def _chain_issue(self, subject_kind: str, run: ProjectRun | StepRun) -> str | None:
        """Why the transition log does not explain the run's row, or ``None``."""
        if subject_kind == "project":
            subject_id, state = run.project_run_id, ProjectState.ACTIVE.value
        else:
            subject_id, state = run.step_run_id, StepState.PLANNED.value
        rows = self._conn.execute(
            "SELECT * FROM transitions WHERE subject_kind = ? AND subject_id = ? ORDER BY seq",
            (subject_kind, subject_id),
        ).fetchall()
        version = 0
        last = None
        for row in rows:
            if (
                row["from_version"] != version
                or row["to_version"] != version + 1
                or row["from_state"] != state
            ):
                return f"{subject_kind} {subject_id}: transition log is not a contiguous chain."
            state, version, last = row["to_state"], version + 1, row
        if version != run.state_version or state != run.state.value:
            return f"{subject_kind} {subject_id}: state row is not explained by its transition log."
        if subject_kind == "step":
            expected = (
                (last["attempt"], last["verification_outcome"], last["review_verdict"])
                if last is not None
                else (0, None, None)
            )
            if expected != (run.attempt, run.verification_outcome, run.review_verdict):
                return f"step {subject_id}: attempt or facts are not explained by its log."
        return None

    def recover(self, project_run_id: str) -> RecoveryReport:
        """Re-prove one project run after a restart; never resume on hope.

        Required, once per store session, before anything in a run this session
        did not create is read as authority or advanced. In one transaction it
        either (a) escalates the project, and every step that is not already
        HUMAN_REQUIRED and is not provably terminal, to HUMAN_REQUIRED when any
        identity binding, contract, cross-object relationship or transition log
        fails to explain the stored state, or (b) moves every in-flight step to
        RECOVERY_REQUIRED, because AIDO cannot prove whether the effect it had
        requested happened. Repeating it changes nothing further. A project row
        that does not parse raises :class:`StateUntrustedError`, writes nothing,
        and leaves the run unconsumable.
        """
        with self._transaction():
            project = self._load_project_run(project_run_id)
            issues, context = self._project_issues(project)

            steps: list[tuple[StepRun, StepContract | None]] = []
            suspect: set[str] = set()
            for row in self._conn.execute(
                "SELECT * FROM step_runs WHERE project_run_id = ? ORDER BY rowid",
                (project_run_id,),
            ).fetchall():
                try:
                    step = self._parse_step_row(row)
                except StateUntrustedError:
                    issues.append(f"step {row['step_run_id']}: row does not validate.")
                    continue
                step_issues, contract = self._step_issues(step, project, context)
                steps.append((step, contract))
                if step_issues:
                    suspect.add(step.step_run_id)
                    issues.extend(step_issues)

            if issues:
                escalated = []
                for step, _ in steps:
                    if step.state is StepState.HUMAN_REQUIRED:
                        continue
                    if step.state in TERMINAL_STEP_STATES and step.step_run_id not in suspect:
                        continue
                    decision = decide_integrity_escalation(step)
                    self._write_step(
                        step, decision,
                        _derived_request_id(f"{step.step_run_id}:{step.state_version}", "integrity"),
                        hashlib.sha256(b"integrity_failure").hexdigest(), "integrity_failure",
                    )
                    escalated.append(step.step_run_id)
                if project.state is not ProjectState.HUMAN_REQUIRED:
                    self._write_project(
                        project, ProjectState.HUMAN_REQUIRED, "state_integrity_failed",
                        _derived_request_id(
                            f"{project.project_run_id}:{project.state_version}", "integrity"
                        ),
                        hashlib.sha256(b"integrity_failure").hexdigest(), "integrity_failure",
                    )
                report = RecoveryReport(
                    project_run_id=project_run_id,
                    integrity_ok=False,
                    integrity_issues=tuple(issues),
                    recovered_step_run_ids=(),
                    escalated_step_run_ids=tuple(escalated),
                    project_state=ProjectState.HUMAN_REQUIRED,
                )
            else:
                recovered = []
                for step, contract in steps:
                    if step.state not in IN_FLIGHT_STEP_STATES:
                        continue
                    request = StepTransitionRequest(
                        request_id=new_request_id(),
                        expected_state_version=step.state_version,
                        event=StepEvent.RECOVER_INTERRUPTED,
                        reason="AIDO restarted while this step had requested an external effect.",
                    )
                    decision = decide_step_transition(
                        step=step,
                        contract=contract,
                        project_state=project.state,
                        dependencies_complete=False,
                        request=request,
                    )
                    self._write_step(step, decision, request.request_id, request.request_sha256,
                                     request.event.value)
                    project = self._propagate(project, decision, request.request_id,
                                              request.request_sha256)
                    recovered.append(step.step_run_id)
                report = RecoveryReport(
                    project_run_id=project_run_id,
                    integrity_ok=True,
                    integrity_issues=(),
                    recovered_step_run_ids=tuple(recovered),
                    escalated_step_run_ids=(),
                    project_state=project.state,
                )
        # Only after COMMIT. Consumers still re-prove on every call, so a run
        # whose escalation left an unexplained row stays unconsumable.
        self._proven_runs.add(project_run_id)
        return report
