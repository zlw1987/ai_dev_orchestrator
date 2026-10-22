# DL-1 — Offline Dual-Loop Control-Plane Foundation

> **OFFLINE IMPLEMENTATION NOTE. NOT A PHASE ACCEPTANCE, NOT A LIVE AUTHORIZATION.**
>
> DL-1 adds one importable package, `ai_dev_orchestrator.control_plane`, and
> its offline tests. No model was called, no endpoint was contacted, no Pi,
> Node, shell or subprocess was launched, and no target workspace was read
> while building or testing it. No CLI command reaches it. It qualifies no
> Implementer or any other role.

| | |
|---|---|
| Kind | Implementation note (offline) |
| Baseline | `163f3f5ba575ece6190d54bc4f6816008aa23429` |
| Roadmap mapping | A subset of **M5A** (`AIDO_RUNTIME_HARNESS_ROADMAP.md` §10–§15). DL-2 is the M6 inner loop and DL-3 the M6C outer loop (§16) |
| Status | **NOT ACCEPTED.** FU1 (§4.1) corrects four independent-review blockers. Implemented, uncommitted, **pending independent review** |

## 1. What DL-1 is

The smallest state and authority layer that the inner and outer loops need,
built before either loop exists:

```text
models.py       ProjectContract (+ exact-phrase approval bound to its digest),
                ExecutionPlan, StepContract, ProjectRun, StepRun,
                PlannerDecision and the other role-output types
contracts.py    issue_step_contract / validate_step_contract: Planner proposal
                -> AIDO-issued Step Contract
transitions.py  the deterministic transition validator (pure, no I/O)
store.py        SQLite persistence, duplicate handling, integrity, recovery
ports.py        Planner / Tester / Implementer / Verifier / Reviewer interfaces
                (no implementation ships; the tests inject fakes)
```

## 2. Authority map

| Layer (§10) | Type | Who may produce it | How it becomes authority |
|---|---|---|---|
| Human product authority | `ProjectContract` | A human: content plus `ProjectContractApproval` (exact phrase, `source: manual`, `contract_sha256` = the content digest) | Constructing it validates the approval. The store persists it by digest |
| AIDO-mutable plan | `ExecutionPlan` | AIDO. Version N names version N-1 by digest. A step may depend only on earlier steps, so every plan is acyclic | `record_execution_plan` checks the binding and the version chain |
| Derived contract | `StepContract` | **AIDO only**, from a Planner `StepContractProposal` via `issue_step_contract` | `validate_step_contract` checks the binding and that the objective and dependencies match the plan and no project invariant was dropped. Policy fields come from AIDO. The store re-runs the check on every insert |
| Worker proposals | `PlannerDecision`, `StepContractProposal`, `TestProposal`, `ImplementationReport`, `ReviewProposal` | Roles (fakes in DL-1) | **Never directly.** They are inputs to a `StepTransitionRequest`, and only the validator decides |
| AIDO-observed fact | `VerificationObservation` | AIDO's own deterministic verification only (in DL-2, an adapter over 5F2D) | The validator treats it as authoritative |

Every model is `extra="forbid"` and frozen. Some forged fields are rejected,
never stripped: a `PlannerDecision` with `next_state` or `reasoning`, a
`StepContractProposal` with `max_attempts` or `review_required`, a
`TestProposal` with `authoritative`, and a `ReviewProposal` with `commit`.

## 3. The validator

A request names an **event**, never a target state. The validator picks the
target by fixed rules:

| From | Event | To |
|---|---|---|
| PLANNED | `mark_ready` (every dependency's COMPLETE re-proven against its log) | READY |
| READY | `begin_attempt` (attempt += 1; persisted **before** any worker request) | EXECUTING |
| EXECUTING | `implementation_returned` (claims ignored) | VERIFYING |
| VERIFYING | `verification_observed`: `verified` + review required / `verified` or `verification-failed` / `workspace-state-untrusted` | REVIEWING / ACCEPTANCE / RECOVERY_REQUIRED (project too) |
| REVIEWING | `review_observed` (verdict recorded as a fact) | ACCEPTANCE |
| ACCEPTANCE | `decide_acceptance` with a `PlannerDecision` | see below |
| any non-terminal | `escalate` | HUMAN_REQUIRED |
| EXECUTING / VERIFYING / REVIEWING | `recover_interrupted` | RECOVERY_REQUIRED (project too) |

At ACCEPTANCE:

```text
RECOMMEND_STEP_ACCEPT  + verified + (approve if review required)
                       + (bound human acceptance if required)   -> COMPLETE
RECOMMEND_STEP_ACCEPT  against the recorded facts                -> HUMAN_REQUIRED
RECOMMEND_STEP_ACCEPT  missing a required human acceptance       -> refused (stays ACCEPTANCE)
RECOMMEND_RETRY_IMPLEMENTATION with attempts left / budget spent -> READY / FAILED
PROJECT_CONTRACT_CONFLICT                                        -> HUMAN_REQUIRED (project too)
RECOMMEND_RETRY_TEST, RECOMMEND_REPLAN, PLAN_CONFLICT,
HUMAN_REQUIRED                                                   -> HUMAN_REQUIRED (no Tester or re-plan in DL-1)
```

**Refusals change nothing.** The refusal codes are: a stale
`expected_state_version`, an out-of-order event, a terminal state, a project
that is not ACTIVE, a role output bound to another contract or attempt, a
missing human acceptance, a reused `request_id`, and project completion, which
is `unsupported_in_dl1` because the §20 integration gate does not exist.

## 4. Persistence and recovery

- **SQLite is the state authority and evidence stays outside it** (§13.2).
  Contracts are stored by content digest and re-hashed on every load. Role
  outputs carry evidence digests. The transition log keeps a digest of each
  request.
- **One atomic act per transition.** One `BEGIN IMMEDIATE` transaction covers
  the transition row, the run row (state, version, attempt, facts) and any
  project propagation, with `synchronous=FULL`. The caller gets the result only
  after `COMMIT`.
- **One owner.** `locking_mode=EXCLUSIVE` is taken at open. A second open is
  `StoreLockedError`, and a dead owner's lock is released by the OS.
- **A store exists only through `open()`.** The constructor refuses to wrap a
  connection that skipped the ownership lock and the schema check.
- **Recovery is a gate, enforced by the store** (FU1, B1). Each `open()` is a
  new session. A project run that this session did not create cannot be
  consumed until `recover()` has re-proven it in this session. That covers
  authoritative reads, transitions, new step runs and replays, and refusals
  raise `RecoveryRequiredError`. `recover()` moves EXECUTING, VERIFYING and
  REVIEWING to RECOVERY_REQUIRED, because "a request was issued" proves nothing
  about its effect (§12.4). A crash inside `recover()` rolls back and leaves
  the run gated. It is idempotent, and its effect on the gate is per session
  only.
- **Proof at every consumption boundary** (FU1, B2 and B3). Before a run's
  state is returned or acted on, the store re-proves the following, in one
  place:
  - **Creation binding.** The run's identity columns are the ones recorded in
    `run_bindings` when it was created. For a project run these are the
    contract digest, plan digest and plan version. For a step run they are the
    project run, step id and contract digest.
  - **Transition log.** The log explains the state, version, attempt,
    verification outcome and review verdict.
  - **Contracts.** Each contract still hashes to its identity.
  - **Combination.** The project contract, plan, project run, step contract
    and step run agree. The plan binds the contract. The step contract passes
    `validate_step_contract` against the run's contract and plan, and is the
    contract for this step id.
  - **Step set.** The project's step runs are exactly the ones created under
    it. Rows moved in, moved out or deleted fail this check, and a deleted
    step cannot be re-created fresh.

  Dependencies are proven the same way before their COMPLETE is believed.
  Individually valid objects that do not belong together are refused. This
  covers another step's contract, a weaker superseding version of the step's
  own contract, and a consistent swap of all the rows to another plan version.
- **Public reads are authoritative or plainly diagnostic** (B3).
  `get_project_run`, `get_step_run` and `list_step_runs` return only proven
  state and otherwise raise. `inspect_project_run`, `inspect_step_run` and
  `inspect_step_runs` return an `UnverifiedRunRow` of raw column values. It is
  not a `ProjectRun` or `StepRun`, so the validator cannot consume it, and DL-2
  must never convert one into either. `transitions_for` is an audit read, not
  proof.
- **Duplicates are receipts, not permissions** (B4). A replay of a recorded
  request is answered only after the same gate and proof as a new request. It
  returns the recorded transition, flagged `duplicate`, together with the
  subject's **current** proven `current_state` and `current_state_version`.
  After a restart, a replayed `begin_attempt` therefore reports
  RECOVERY_REQUIRED, not EXECUTING. A caller acts on the current state, never
  on a duplicate's `record`, and never dispatches an external effect because a
  duplicate came back. The same id with different content is still refused.
- **Caller models are re-validated.** Pydantic `model_copy(update=...)` and
  `model_construct()` skip validators. Every contract and transition request
  is re-parsed through its exact class at the store boundary, and only the
  re-parsed copy is used. A contract that fails is `ContractRefusedError`, and
  a request that fails is refused as `invalid_request`.
- **Untrusted state escalates.** When any proof above fails, `apply_*` and the
  authoritative reads raise `StateUntrustedError`, before the recovery gate is
  checked. `recover()` then records HUMAN_REQUIRED for the project and for
  every step that is not already HUMAN_REQUIRED and not provably terminal.
  That includes a claimed COMPLETE the log does not explain. If the escalated
  row is still unexplained, the run stays unreadable through the authoritative
  API. A project row that does not parse raises and writes nothing.

### 4.1 FU1 — what changed and why

Independent review found four reproducible failures. Each was reproduced
against the original code before it was fixed, and each now has regression
tests in `tests/test_control_plane_dl1.py`.

| | Failure | Fix |
|---|---|---|
| B1 | A step persisted EXECUTING could be advanced to COMPLETE after a reopen without `recover()` | Per-session recovery gate inside the store |
| B2 | Replacing step-a's contract digest with step-b's (valid, weaker policy) passed `recover()` with `integrity_ok=True` | Creation bindings plus full cross-object proof at consumption and in `recover()` |
| B3 | `get_step_run`, `list_step_runs` and `get_project_run` returned a forged COMPLETE | Authoritative reads re-prove. Raw rows are available only as `UnverifiedRunRow` |
| B4 | A replay returned `duplicate=True` from a tampered store before any integrity check | Gate and proof first, then the replay, which reports the current proven state |

The schema version is now `aido-control-plane-store.v2` because the
`run_bindings` table was added. A v1 file is refused as untrusted. No v1 store
was ever shipped.

### 4.2 What is mechanically enforced, and what is not

Enforced by the store and tested offline: the items in §4, within one owning
process, against a row edit made outside the store.

Not proven by DL-1, and **retained as DL-2 hard gates**:

- **Authenticated human approval provenance.** `ProjectContractApproval` and
  `HumanStepAcceptance` check only an exact phrase, `source: "manual"`, an
  aware timestamp and a digest binding. Any in-process code can construct one.
  Pydantic typing and an exact phrase do not prove that a human, or AIDO,
  produced it.
- **Trusted verification provenance and persisted evidence.** A
  `VerificationObservation` is authoritative by type only. `evidence_sha256`
  is validated for shape but not stored, and nothing proves it names a
  persisted 5F2D `verification-result.v1`.
- **Trusted policy issuance provenance.** `record_step_contract` re-runs the
  issuance rules, but any caller can choose the policy values
  (`review_required`, `human_acceptance_required`, `max_attempts`). Nothing
  proves which AIDO code path issued them.
- **Workspace/store containment and real adapter authorization.** The store
  path is checked only for being absolute with an existing parent, and no
  adapter or workspace exists.

## 5. How DL-1 supports DL-2 and DL-3

**DL-2 (inner step loop, M6).** It is a driver over existing pieces:

1. Derive the Step Contract: `PlannerPort.propose_step_contract`, then
   `issue_step_contract`, then `record_step_contract`.
2. Run the attempt: `begin_attempt` (persisted intent), the Implementer port,
   `implementation_returned`, the Verifier port (an adapter over 5F2D's
   `verification-result.v1` outcome and digest), `verification_observed`, the
   Reviewer port when required (an adapter over the 5F2E packet verdict and
   digest), `review_observed`, then the Planner's decision and
   `decide_acceptance`.

The test helper `drive_one_attempt` is this loop written out by hand with
fakes. DL-2 adds real adapters behind the ports, and each adapter inherits that
role's shipped authority contract unchanged. DL-2 must also add:

- a human resolution path out of HUMAN_REQUIRED;
- a re-proof path out of RECOVERY_REQUIRED (for example 5F2D-style HEAD and
  dirty-state proof against the attempt's recorded evidence);
- persistent evidence references per transition;
- the four hard gates in §4.2, before any real adapter is wired.

**DL-3 (outer project loop, M6C).** It needs:

- "select ready step": `mark_ready` against dependency state, which already
  works;
- re-planning: a new `ExecutionPlan` version (the chain already exists) plus a
  rule for superseding step runs bound to the old plan;
- project completion: an integration-gate fact that the validator requires
  before `request_complete`.

Each is an additive validator rule or event. The state model, identities and
store do not change shape.

## 6. Known limitations

- No loop runs. No real role is wired. Nothing leaves HUMAN_REQUIRED or
  RECOVERY_REQUIRED, and project COMPLETE is unreachable.
- Recovery is coarse. Every in-flight step goes to RECOVERY_REQUIRED, even
  where re-proof might show nothing happened.
- Integrity checking detects three kinds of edit: a row edited without its
  log, a run identity edited without its creation binding, and a contract body
  edited without its key. It does not detect a consistent rewrite of a row
  together with its log and binding, or the restore of an older database file.
  The operator account is the trust root, as for the P1B ledger (A-19).
- The recovery gate is in memory and per store session. It relies on the
  single-owner lock, and it does not defend against in-process code that
  writes through the store's private connection or subclasses the store.
- A project run whose own row is renamed or deleted cannot be recovered by its
  old id. It fails closed as `RecordNotFoundError`, but no escalation is
  recorded for it.
- There is no API to list project runs. After a restart, a DL-2 driver must
  already know which runs to `recover()`. Any run it does not recover stays
  unconsumable.
- `synchronous=FULL` is SQLite's durability, and Windows has no directory
  fsync. Power-loss durability is not claimed beyond that.
- The store needs an absolute path in an existing directory. It does **not**
  enforce §13.3's "never inside a target repository", because DL-1 has no
  target repository. DL-2 must add that check once a workspace exists.
- The Step Contract does not yet bind a baseline repository identity, a write
  scope, test authority or risk dimensions (§14.1). Those arrive with M5, M6A
  and §22.
- `VerificationObservation` is authoritative by type. Nothing stops in-process
  code from constructing one. Only DL-2's 5F2D adapter may produce it in
  production.
- Shipped vocabularies (`VerificationOutcome`, `ReviewVerdict`) are mirrored,
  not imported, to keep this package free of executing modules. A test pins
  each mirror to its source.

## 7. Interaction with ALPHA-1B

ALPHA-1B's S0 preflight requires `src/` and `pyproject.toml` to be clean and
identical to the source pin `44bf3be`. DL-1 adds files under `src/`. While
DL-1 is present in the runtime checkout, uncommitted or committed, that
preflight STOPs, which is correct fail-closed behavior. Before ALPHA-1B runs,
DL-1 must be on a separate branch, stashed, or covered by a separately
reviewed re-pin. DL-1 changes no ALPHA-1B, P1B, CFG1, writer, verifier or
reviewer code.
