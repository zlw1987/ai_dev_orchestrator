# DL-4A — Real Integration Authority Foundation

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**

> **DL-4A FU1 (on `67897a9`)** corrected one independent-review finding: the
> authority-parameter consumption boundary of `apply_step_transition`. Every
> `role_output` and `human_attestation` is now either validly consumed for its
> event or refused; none is ignored, on a fresh request or on a replay. FU1
> changes no frozen model, schema or accepted transition authority. See §13.
> DL-4A is still **not accepted**.

| | |
|---|---|
| Baseline | `main` at `2ea54f0` (DL-1, DL-2, DL-3 and DL-3 FU1, each independently accepted within its offline scope) |
| Scope | Offline authority mechanisms that must exist before the dual-loop control plane may be connected to real runtime adapters |
| Not in scope | Any live execution, model call, Pi/Node process, credential, target-workspace write, plan activation of an existing run, project completion, or automatic exit from HUMAN_REQUIRED / RECOVERY_REQUIRED |

DL-4A does **not** authorize live execution. It adds the trusted issuance and
consumption boundaries a live integration will need, proves them offline with
fake adapters and synthetic evidence, and states exactly which part of each
gate still depends on an external trust source.

---

## 0. Gate summary

| # | Gate | DL-4A status | What is mechanically closed | What remains open (minimum requirement) |
|---|---|---|---|---|
| 1 | Human approval provenance | **PARTIALLY CLOSED** | A constructed `ProjectContractApproval` or `HumanStepAcceptance` is no longer authority in an authority store. Every approval must answer an AIDO-issued, persisted, single-use, expiring challenge, bound to one subject digest. It must be confirmed by the injected verifier and consumed atomically with the record it authorizes. Every later proof re-checks it. | **Human authenticity.** AIDO cannot tell a human from code in its own process. A real `HumanAttestationVerifier` must rest on something the AIDO process cannot produce (§4.1). The default verifier approves nothing. |
| 2 | Verification evidence provenance | **CLOSED for binding and persistence; OPEN for origin** | An observation is never authoritative by type in an authority store. It must name `verification-result.v1` bytes that meet three conditions. They were recorded through the session-only recorder for exactly this dispatch. They are persisted write-once under the state root and are re-hashed on every proof. Their stated outcome is re-derived from their own facts. | **That the bytes came from a genuine 5F2D run.** The recorder must be held only by an adapter that records the exact bytes the shipped verifier returned (§4.2). |
| 3 | Policy issuance | **CLOSED** (human authenticity inherited from gate 1) | Execution-affecting policy (`review_required`, `human_acceptance_required`, `max_attempts`) exists only in an `execution-policy.v1` that a human approves together with the plan and the target workspace. Step Contracts are issued with that policy, and the caller cannot name one. The unissued `record_*` methods are refused. Run and step creation, and every proof, re-check the issuance. | Gate 1's external verifier. A plan-activation authority for *existing* runs (re-planning) remains undesigned, and DL-3 FU1's pending stop stands. |
| 4 | Workspace and store containment | **CLOSED** at the path and identity level | There is an AIDO-owned state root: created empty, never inside a Git working tree, holding the store, write-once evidence and staging. The target workspace is human-authorized by canonical path *and* directory identity, and it must be disjoint from the state root. Both are re-proven on use. There are no reparse points, no `.`/`..`, no overwrite, and the only removal is identity-checked cleanup of AIDO's own staging file. | Races between a check and the next system call (no handle-relative OS API). The operator account. Real adapters must take the workspace only from `authorized_target_workspace()` (§4.4). |
| 5 | Role-output identity binding | **CLOSED** for binding; origin not authenticated | Each role output must answer a persisted, unpredictable, single-use `DispatchTicket`. There is at most one ticket per `(step_run_id, state_version, role)`. The ticket is enveloped with the Project Run, Step Run, contract, attempt and role, and consumed in the transition's transaction. Cross-run, cross-step, cross-version and cached replays are refused. | **Role origin.** A caller that holds the store can mint a ticket and answer it itself. Only verification (gate 2) and human acceptance (gate 1) have proven origin. The approved policy (`human_acceptance_required`) is the backstop (R-3). |

No gate is claimed closed merely because an interface exists. Gates 1 and 2
each have an explicitly fail-closed external dependency, named above.

---

## 1. What DL-4A is

DL-4A adds an **authority store**: a `ControlPlaneStore` opened only through an
AIDO state root, under a new schema version (`aido-control-plane-store.v3`).
Every DL-1 property still holds there unchanged: persist before exposing, one
owner, the recovery gate, proven reads only, the validator as the only
authority, re-validated caller models, and idempotent version-guarded
requests. DL-4A adds provenance to the proof.

```text
                     AIDO STATE ROOT (aido-state-root.v1)
                     ├── aido-state-root.json      marker + root id
                     ├── control-plane.sqlite3     authority store (store.v3)
                     ├── evidence/verification/    write-once verification-result.v1
                     └── staging/                  AIDO's own transient files
                                │
    HUMAN ──attests──► ApprovalChallenge (single-use, 60 min, subject digest)
                                │  confirmed by injected HumanAttestationVerifier
                                ▼
    ProjectContract ──► plan_activation(plan, ExecutionPolicy, target workspace)
                                │
                                ▼
    Planner proposal ──► issue_authorized_step_contract  (policy from the activation)
                                │
                                ▼
    ProjectRun / StepRun ──► DL-3 ──► DL-2 ──► DispatchTicket ──► port(dispatch=)
                                                    │                 │
                     VerificationEvidenceRecorder ◄─┘   BoundRoleOutput┘
                     (session-only; 5F2D bytes)              │
                                                             ▼
                                          apply_step_transition(role_output=,
                                                     human_attestation=)
                                          proof → replay → authority → validator
                                          → write → consume ticket/challenge
```

The offline (`store.v2`) path is unchanged byte for byte. All 277 DL-1/2/3
tests pass untouched, and the two kinds of store cannot open each other's
files.

### New and changed modules

| File | Kind | Content |
|---|---|---|
| `control_plane/authority.py` | new | `ExecutionPolicy`, `ApprovalChallenge`, `HumanAttestation`, `HumanAttestationVerifier` (protocol) and `UnavailableHumanAttestationVerifier`, the subject digests, `DispatchTicket`, `BoundRoleOutput`, `VerificationEvidenceReceipt`, the `verification-result.v1` mirror reader, `AuthorityRefusedError` |
| `control_plane/containment.py` | new | `AidoStateRoot`, `canonical_directory`, `require_disjoint`, `require_outside_git_worktrees`, `WorkspaceIdentity`, write-once publishing and identity-checked cleanup |
| `control_plane/authority_session.py` | new | `open_authority_session`, `AuthoritySession`, `VerificationEvidenceRecorder` |
| `control_plane/store.py` | changed | the v3 schema; refusal of the unissued `record_*` methods in authority mode; the issuance, challenge, ticket and evidence APIs; authority checks in `create_*`, `apply_step_transition` and both proof functions. The v2 path is unchanged |
| `control_plane/inner_loop.py` | changed | authority mode only: a ticket before each role call, `dispatch=` to the port, a `BoundRoleOutput` pre-check, `role_output=` to the store. Offline calls keep the exact DL-2 shape |
| `control_plane/ports.py` | changed | the `Bound*Port` protocols, and a docstring |
| `control_plane/transitions.py` | changed | the additive `RefusalCode.AUTHORITY_UNPROVEN` |
| `control_plane/__init__.py` | changed | additive exports |
| `tests/test_control_plane_dl4a.py` | new | 74 test functions (116 cases) |

`outer_loop.py` is unchanged: DL-3 drives the authority store through DL-2,
and every DL-4A check is enforced inside the store.

---

## 2. Trust and threat model

**Trust root.** The operator account; the composition root that calls
`open_authority_session` and decides which verifier and which adapters it
wires; and the SQLite and filesystem semantics of the host. This matches
DL-1's stated root (the P1B ledger precedent, A-19).

**Untrusted.** Every role port and role output, every caller-built Pydantic
object (including a `model_construct`ed or `model_copy`-mutated one, or a
subclass), every file a non-AIDO actor can place under the state root or the
workspace, and every library caller that does not hold a minted capability.

**Capabilities that exist only by issuance.**

| Capability | Minted by | Held by | Cannot be obtained by |
|---|---|---|---|
| `AidoStateRoot` | `create()` / `open()` after containment checks | the composition root | the constructor (token) |
| an authority store | `open_authority_session` (root identity bound in `store_meta`) | the session | `ControlPlaneStore.open` (refuses v3); another root's file (root-id mismatch) |
| `VerificationEvidenceRecorder` | `open_authority_session`, once per session | the session object only | any store method; its constructor (token); a foreign key object |
| `ApprovalChallenge` (answerable) | the store, persisted | the human, via the operator | construction: an unknown `challenge_id` answers nothing |
| `DispatchTicket` (answerable) | the store, persisted, once per version and role | DL-2's dispatch | construction: an unknown `ticket_id` answers nothing |

**Out of scope, stated rather than claimed.** In-process code that reaches
private attributes (`_conn`, `_authority`, `_record_verification_evidence`)
or calls `os` directly. A deliberate *consistent* rewrite of the database
together with the evidence blobs. A restore of an older state root. Races
between a containment check and the following system call. None of these is a
sandbox claim.

---

## 3. Adversarial analysis before implementation

For each authority: who creates and mutates it, its provenance, how it is
validated at consumption, and how it behaves on replay, recovery, partial
failure and bypass.

| Authority | Creator / mutators | Provenance | Validation at consumption | Identity and lifecycle | Replay / recovery | Persistence | Partial failure | Bypass by a supported caller? |
|---|---|---|---|---|---|---|---|---|
| Project Contract approval | the human (attestation); the store consumes it. Nobody mutates it | challenge row, plus the consumed attestation body and digest | `record_approved_project_contract` checks the challenge, subject, window, verifier and approval block. Every proof re-checks the consumed row against the contract | subject = content digest; the challenge is single-use and expires in 60 min | the identical attestation is a receipt; a fresh challenge for an approved contract is refused; restart trusts the consumed row (operator trust root) | `approval_challenges` | contract insert and consumption share one transaction | `record_project_contract` is refused in authority mode. A constructed approval answers no challenge. A forged proof fails the verifier |
| Plan activation (plan + policy + workspace) | the human; the store records it | consumed `plan_activation` challenge; `plan_issuances` row | `issue_execution_plan` recomputes the subject from the actual plan, policy and workspace identity. Run creation and proofs re-check it | subject = digest(pc, plan, policy, workspace identity) | the identical challenge is a receipt; a re-issue is refused | `plan_issuances`, `contracts` | one transaction | `record_execution_plan` is refused. An activation for another policy, workspace or kind is refused |
| Step Contract issuance | the store, from a Planner proposal | `step_contract_issuances` naming the plan and policy digest | `create_step_run` and every proof require the issuance, with policy fields equal to the approved policy | content-addressed; version 1 only in DL-4A | the identical issuance is a receipt | `step_contract_issuances`, `contracts` | one transaction | `record_step_contract` is refused. A hand-inserted contract has no issuance and is refused |
| Dispatch ticket | the store, for the in-flight (or ACCEPTANCE) step at its current version | `dispatch_tickets` row, UNIQUE(step, version, role) | `apply_step_transition` checks the envelope against the ticket row and the current step, and the payload against the envelope. Proofs require one consumed ticket per role-output transition | unpredictable id; single-use; stale once the step moves | a consumed ticket answers nothing; an identical request is a receipt; after a crash, recovery makes the step RECOVERY_REQUIRED and the ticket stale | `dispatch_tickets` | consumption shares the transition's transaction | a second ticket for the same version and role is refused, whoever asks |
| Verification evidence | the session recorder, for an unanswered verifier ticket | `verification_evidence` row plus the blob `evidence/verification/<sha>.json` | the observation's outcome and digest must equal the row; the blob is re-read, re-hashed and re-parsed, and its outcome re-derived. Repeated on every proof | bound to the ticket, step run and attempt | one record per ticket; identical bytes re-publish idempotently | DB row plus a write-once file | publish first, then insert. A failed publish leaves nothing; a failed insert leaves an unreferenced, harmless blob | a constructed observation, a hand-placed file, a mismatched outcome and tampered or deleted bytes are all refused |
| Target workspace | the human (inside the plan activation) | canonical path plus `(st_dev, st_ino)` digest in `plan_issuances` | `create_project_run` and `authorized_target_workspace()` re-resolve and compare it, and re-check disjointness | fixed per plan activation | re-proven on every read | `plan_issuances` | — | a junction, a respelling, a replacement directory or an overlap with the state root is refused |

---

## 4. Design and status per gate

### 4.1 Human approval provenance — PARTIALLY CLOSED

**Mechanism.** `request_project_contract_approval`, `request_plan_activation`
and `request_step_acceptance` persist an `approval-challenge.v1`. The fields
are `challenge_id` (random), `subject_kind`, `subject_sha256`, `issued_at`,
`expires_at` (60 minutes) and the exact required phrase. The human answers with a
`human-attestation.v1`: the same ids, `approver_id`, `attested_at`, the exact
phrase, and an opaque `proof`.

The store accepts the attestation only if every one of these holds:

1. It is exactly a `HumanAttestation` that re-validates.
2. It names an existing, unconsumed, unexpired challenge.
3. The challenge's subject equals the subject the store recomputes from the
   actual objects.
4. `issued_at ≤ attested_at ≤ now`.
5. The frozen DL-1 approval block (`approved_by`, `approved_at`) records
   exactly the attested approver and time.
6. The injected `HumanAttestationVerifier.verify(...)` returns exactly `True`.
   It receives fresh copies. Exceptions and truthy non-`True` values are
   refusals.

The challenge is consumed in the same transaction as the contract record, the
plan issuance, or the `decide_acceptance` transition. The proofs in
`_project_issues` and `_step_issues` re-check every consumed approval against
its subject on every authoritative read and on `recover()`.

**Step acceptance** binds the Project Run, Step Run, contract, attempt,
**state version** and the attempt's recorded verification-evidence digest. An
acceptance for an earlier attempt or version is therefore stale by
construction.

**What stays open, and what real integration must supply.** The verifier is
the external trust source. DL-4A ships only `UnavailableHumanAttestationVerifier`,
which returns `False`. With it, nothing can be approved, so nothing can be
issued, created or run. That is the default.

A real verifier must confirm a proof that the AIDO process cannot itself
produce. For example, an asymmetric signature whose private key is held only
by the human, outside the AIDO process and account; or an out-of-band channel
with its own authentication. It must not be:

- a shared secret readable by the AIDO process (an HMAC key in AIDO's
  environment or files);
- a typed phrase alone;
- a file whose only protection is the operator account AIDO runs as.

The test suite's `HmacHumanVerifier` is test-only. It demonstrates the
interface and is not shipped.

### 4.2 Verification evidence provenance — CLOSED for binding and persistence; origin OPEN

**Mechanism.** In an authority store, `VerificationObservation` is no longer
authoritative by type. `verification_observed` requires all of the following:

- a `BoundRoleOutput` answering the verifier ticket for this exact step version
  (gate 5);
- a `verification_evidence` row recorded **for that ticket** by the session's
  `VerificationEvidenceRecorder`;
- the observation's `outcome` and `evidence_sha256` equal to that row;
- the blob `evidence/verification/<sha256>.json` re-read from the state root,
  re-hashed to its name, and re-parsed by `verification_outcome_from_evidence`.

That reader requires a UTF-8 JSON object with exactly the shipped
`VerificationResultReport` fields, the shipped schema and mode, and no
duplicate keys or non-JSON constants. It **re-derives** the outcome exactly
as 5F2D's `_build_report` does: an untrusted workspace outranks a failed run.
A document whose stated outcome its own facts do not support is refused.

The outcome recorded is the one the bytes prove. The recorder never takes an
outcome from its caller.

**`verification-result.v1` is preserved.** The bytes are stored exactly as
produced, never normalized, and the shipped model still parses them. A test
pins the mirror (field set, schema, mode, trust fields, outcome literals) to
`VerificationResultReport`. `evidence_sha256` is the SHA-256 of those exact
bytes, which is DL-1 §5's "5F2D outcome and digest". The run binding lives
in AIDO's own row, never inside the 5F2D document.

**What stays open.** The recorder proves *where* the bytes are, *what* they
say and *which dispatch* they answer. It cannot prove the bytes were produced
by a genuine 5F2D run. Real integration must supply a verifier adapter that:

1. holds the session's recorder and gives it to nothing else;
2. obtains the workspace only from `authorized_target_workspace(project_run_id)`;
3. runs the shipped 5F2D library path (`verify_approved_file_edit`) unchanged;
4. records `report.model_dump_json().encode()` exactly.

DL-4B should also bind the report's own target facts (`target.path`, approval
identity) to the step's write scope, which the Step Contract does not yet
carry (roadmap §14.1).

### 4.3 Policy issuance — CLOSED

**Mechanism.** `ExecutionPolicy` (`execution-policy.v1`) holds the three
execution-affecting values. It is approved by a human inside the
`plan_activation` subject, together with the plan digest and the target
workspace identity, and is stored and re-hashed in `plan_issuances`.

`issue_authorized_step_contract(proposal, execution_plan_sha256=...)` takes
**no policy argument**. It calls the unchanged DL-1 `issue_step_contract` with
the approved policy's values. `record_project_contract`, `record_execution_plan`
and `record_step_contract` are refused in an authority store.

`create_project_run` requires an approved contract, an issued plan and a
re-proven workspace. `create_step_run` requires the step contract's issuance
under the run's plan, with policy fields equal to the approved policy. Every
proof repeats these checks, so a tampered policy, issuance, approval or
workspace digest makes the run untrusted, and `recover()` escalates it to
HUMAN_REQUIRED.

A successor plan can be issued only with its own activation. DL-3 FU1's
behavior is unchanged: a run on the older plan stops at
`PLAN_SUPERSESSION_PENDING` with no write. **No plan is ever activated for an
existing run.**

### 4.4 Workspace and store containment — CLOSED at path and identity level

**State root.** `AidoStateRoot.create(path)` imposes these conditions:

- the path is absolute;
- it has no `.` or `..` component;
- it exists, with no reparse point (symlink, junction, mount point) in any
  component;
- it is not inside any Git working tree (no `.git` in it or any ancestor);
- it is **empty**: AIDO adopts nothing it did not create, so it never has
  foreign files to "clean".

`open()` and `verify()` re-prove the canonical path, the marker and root id,
and the layout. Any entry AIDO did not create is refused and left untouched.
The store path is derived from the root and never supplied. The authority
store records the root id and refuses a database copied from another root.

**Target workspace.** It is authorized by canonical path *and*
`(st_dev, st_ino)`. It may not equal, contain or lie inside the state root,
whether by canonical path, case-insensitive spelling or directory identity.
`authorized_target_workspace(project_run_id)` re-proves all of this on every
call, so a directory renamed away and replaced, or swapped for a junction, is
refused. DL-4A has no API that writes, cleans or deletes anything in a target
workspace, and the tests prove the workspace bytes are identical after a full
run.

**Write-once evidence.** Evidence is written in four steps:

1. Stage with `O_CREAT | O_EXCL` in `staging/` and record its identity with
   `fstat`.
2. `fsync`.
3. Publish with a hard link, which cannot overwrite.
4. Remove the staging name.

An existing name with different bytes is refused, never replaced.

**Cleanup.** The only removal in DL-4A code is
`containment._remove_own_staged_file`, and a static test pins that. It
removes only the staging file the same call created, after re-proving three
things: the staging directory is still contained, the file has the same
identity, and it is not a reparse point. A substituted file is left in place
and reported.

**Residual (R-5).** Every check is path-based. A concurrent actor racing
between a check and the next system call is not excluded, because no
handle-relative OS API is used. This is containment checking, not a sandbox.

### 4.5 Role-output identity binding — CLOSED for binding; origin not authenticated

**Mechanism.** `issue_dispatch_ticket(step_run_id, role=, expected_state_version=)`
persists a `dispatch-ticket.v1` with these properties:

- its id is random;
- it carries the Project Run, Step Run, contract, attempt, role, step state
  and state version;
- it is issued only for the role's state (implementer/EXECUTING,
  verifier/VERIFYING, reviewer/REVIEWING, planner/ACCEPTANCE) at the step's
  current version, while the project is ACTIVE;
- at most one exists per `(step_run_id, state_version, role)`, **whoever
  asks**. So "at most one dispatch per persisted intent", which DL-2 enforced
  by convention inside one `run()`, is now a store constraint.

The port receives a copy as `dispatch=` and returns a `bound-role-output.v1`
envelope.

At consumption the store requires all of the following:

- the envelope's role answers the event;
- the request payload equals the envelope's output, by canonical JSON;
- the envelope's identity equals the current step's identity;
- the ticket row exists, is unconsumed, matches the envelope, and was issued
  for the current state and version.

The ticket is consumed in the transition's transaction. Every proof requires
exactly one consumed, matching ticket per role-output transition.

An event that consumes no role output (`MARK_READY`, `BEGIN_ATTEMPT`,
`ESCALATE`, `RECOVER_INTERRUPTED`) refuses a supplied `role_output` and a
supplied `human_attestation`. A replay is a receipt only when it presents
exactly the envelope and attestation its original transition consumed (FU1,
§13).

The frozen DL-1 outputs are unchanged and still required inside the envelope,
so DL-1's own `(step_contract_sha256, attempt)` binding check still runs.

**Closes** DL-2 §7 and DL-3 §7's binding gap: two runs of one contract share
`(step_contract_sha256, attempt)` but never a dispatch.
`test_the_dl3_role_output_binding_gap_is_closed_in_an_authority_store` is the
counterpart of DL-3's pinned limitation test, which still passes for offline
stores.

**What stays open (R-3).** Binding is not origin. A caller holding the store
can mint a ticket and answer it, as a planner or reviewer, itself. The
outputs with proven origin are verification (gate 2) and human acceptance
(gate 1). For the Alpha the approved policy should therefore set
`human_acceptance_required: true`. `test_role_output_origin_is_bound_not_authenticated`
pins that a forged planner `ACCEPT` still cannot reach COMPLETE without an
attestation.

---

## 5. Residuals

| Id | Residual | Mitigation now | Owner |
|---|---|---|---|
| R-1 | Human authenticity depends on an external verifier that does not exist yet | the default verifier refuses everything | DL-4B |
| R-2 | The origin of verification bytes depends on the adapter holding the recorder | session-only recorder; outcome re-derived from the bytes; the shipped model still parses them | DL-4B |
| R-3 | Planner, reviewer and implementer output origin is not authenticated | binding (gate 5); policy `human_acceptance_required` as backstop | DL-4B / policy |
| R-4 | Consistent rewrite of the DB together with the blobs; restore of an old root | none (operator trust root, as DL-1) | accepted residual |
| R-5 | Check-then-act races on the filesystem | identity checks; no overwrite; no foreign removal | accepted residual |
| R-6 | A crash after publishing evidence and before the DB insert leaves an unreferenced blob | harmless: never authority; identical bytes re-publish idempotently | accepted residual |
| R-7 | The external verifier is called inside the store's write transaction | offline only; a slow real verifier holds the store lock while it runs | DL-4B to decide |
| R-8 | The approval challenge TTL is fixed (60 min); the store clock is the opener's | the opener is the trust root | accepted residual |
| R-9 | In authority mode DL-2 escalates a human-required step at ACCEPTANCE (unchanged DL-2 rule), and its planner ticket for that version is spent | the human path works through the direct API before DL-2 decides; see §11 | DL-4B |

---

## 6. Frozen contracts

**No frozen model, schema, rule or offline behavior changed.** The following
models are byte-identical:

- `ProjectContract*`, `ExecutionPlan`, `StepContract`;
- the role outputs, `HumanStepAcceptance` and `VerificationObservation`;
- `ProjectRun`, `StepRun`;
- every DL-1 validator rule;
- `store.v2`;
- DL-2's offline call shape and DL-3.

A test pins the field sets of the two most affected models.

**One contradiction was identified and resolved by versioning, not
reinterpretation.** DL-1 made `VerificationObservation` "authoritative by
type", and the DL-4A prompt requires that "a role-produced observation is not
itself trusted verification". The two cannot both hold in one store. DL-4A
therefore leaves `store.v2` exactly as accepted, where the observation is
still authoritative by type, offline only. It introduces `store.v3`, where
the observation is accepted only with evidence. Neither store opens the
other's file.

**Versioned additions.** `aido-state-root.v1`, `aido-control-plane-store.v3`,
`execution-policy.v1`, `approval-challenge.v1`, `human-attestation.v1`,
`dispatch-ticket.v1`, `bound-role-output.v1`, and the additive
`RefusalCode.AUTHORITY_UNPROVEN`.

**DL-2 behavior changes, in authority mode only.**

1. A ticket precedes every role call. A refused ticket means the role is not
   called: an in-flight step is reduced to RECOVERY_REQUIRED, and a planner
   failure escalates.
2. Ports receive `dispatch=` and must return an envelope. A bare output is
   `malformed`.
3. The DL-2 §7 limitation "the Planner may be asked again at ACCEPTANCE after
   a crash" no longer applies. The persisted planner ticket forbids a second
   ask, and the step escalates instead.

The new `DispatchResult` value `ticket_refused` and the cause
`dispatch_ticket_refused` are additive.

**ROLE, HARNESS, BACKEND and MODEL stay separate.** Tickets and envelopes name
a **role** only. Verification evidence is **harness** output (the 5F2D
verifier), recorded by AIDO and never asserted by a role. No DL-4A record
names a backend, a model, a provider or an endpoint. DL-4A adds no token cap
and no CLI surface.

---

## 7. Second adversarial self-review (after coding)

| Finding | Material? | Resolution / regression |
|---|---|---|
| A store object whose `authority_mode` lies to DL-2 could make DL-2 send unbound outputs | No: enforcement is in the store | `test_enforcement_lives_in_the_store_not_in_the_loop` |
| A store-holding caller can mint and answer a planner or reviewer ticket itself | Yes, as a residual. It cannot be closed without an external role identity | pinned as R-3; the human-acceptance policy is the backstop; `test_role_output_origin_is_bound_not_authenticated` |
| Could any DL-4A path write outside the state root? | No | `test_aido_writes_nothing_outside_its_state_root`, `test_the_target_workspace_is_never_written_or_cleaned` |
| The DL-2 planner re-ask after a crash | Closed in authority mode | `test_a_planner_is_never_asked_twice_for_one_version_even_after_a_crash` |
| A port mutating its `dispatch` copy (`object.__setattr__`) | No: the port gets a copy, and the store re-reads its own row | `test_a_port_mutating_its_dispatch_ticket_cannot_widen_it` |
| `model_copy` and `model_construct` attestations and envelopes, subclasses, dicts | No: authority inputs must be exactly the class and re-validate | `test_malformed_attestations_are_refused` (×5), `test_malformed_role_output_envelopes_are_refused` (×4) |
| A legacy store file planted at the authority path | Fail-closed DoS only | `test_an_authority_session_refuses_an_offline_store_file` |
| Test defect found by the first full-suite run: three tamper cases overwrote a random digest's first character with a fixed letter, which is a no-op 1 time in 16 | Test-only (the store was right to report the untampered run as intact) | `_flip()` now always changes the value; the 9 tamper cases were re-run repeatedly |

---

## 8. Test evidence

`tests/test_control_plane_dl4a.py`: 74 functions, **116 cases**.

| Mandatory category | Tests |
|---|---|
| Forged approvals | `test_a_constructed_approval_is_not_a_recorded_approval`, `test_an_unconfirmed_attestation_is_refused` (×6), `test_a_proof_made_with_the_wrong_key_is_refused`, `test_an_attestation_for_another_subject_is_refused`, `test_the_approval_block_must_record_the_attested_approval` (×2), `test_a_paraphrased_attestation_is_refused`, `test_a_forged_human_step_acceptance_is_refused`, `test_without_a_verifier_nothing_can_be_approved` |
| Forged verification results | `test_a_constructed_verification_observation_is_not_verification`, `test_an_observation_must_state_exactly_its_recorded_evidence`, `test_malformed_or_self_contradicting_evidence_is_never_recorded` (×14), `test_evidence_placed_in_the_state_root_by_hand_is_not_evidence`, `test_a_verifier_port_cannot_choose_its_own_outcome`, `test_the_verification_recorder_exists_only_on_its_session` |
| Cross-run role outputs | `test_a_role_output_from_another_project_run_is_refused`, `test_the_dl3_role_output_binding_gap_is_closed_in_an_authority_store`, `test_a_cached_role_output_cannot_answer_a_later_dispatch` |
| Mismatched trusted objects | `test_the_payload_must_be_the_bound_output`, `test_a_ticket_for_another_role_or_version_is_refused`, `test_an_authority_store_refuses_another_state_roots_database` |
| Unauthorized plan issuance | `test_unissued_record_methods_are_refused_in_an_authority_store`, `test_a_plan_is_never_recorded_without_its_own_human_activation`, `test_a_plan_of_an_unapproved_contract_cannot_even_be_requested`, `test_a_run_needs_an_issued_plan`, `test_a_caller_cannot_choose_a_step_contracts_policy`, `test_a_hand_inserted_step_contract_cannot_start_a_step_run`, `test_a_successor_plan_needs_its_own_activation_and_leaves_the_run_pending` |
| Malformed types | `test_malformed_attestations_are_refused` (×5), `test_malformed_role_output_envelopes_are_refused` (×4), `test_an_authority_store_cannot_be_opened_around_the_state_root` |
| Replay | `test_an_approval_is_single_use_and_a_replay_is_a_receipt`, `test_an_identical_bound_request_replays_as_a_receipt`, `test_a_consumed_dispatch_cannot_answer_twice`, `test_a_step_version_is_dispatched_to_a_role_at_most_once_by_anyone` |
| Post-validation mutation | `test_mutating_an_input_after_it_is_consumed_changes_nothing`, `test_a_port_mutating_its_dispatch_ticket_cannot_widen_it`, `test_evidence_tampered_before_consumption_is_refused`, `test_damaged_evidence_makes_a_completed_run_untrusted` (×2) |
| Stale authority | `test_an_expired_challenge_is_refused`, `test_an_attestation_dated_outside_its_window_is_refused` (×2), `test_a_step_acceptance_goes_stale_when_the_step_moves`, `test_a_ticket_outstanding_at_a_crash_is_never_answerable`, `test_a_planner_is_never_asked_twice_for_one_version_even_after_a_crash` |
| Filesystem path substitution | `test_a_junction_is_refused_wherever_it_appears`, `test_a_replaced_target_workspace_is_refused`, `test_overlapping_state_root_and_workspace_are_refused`, `test_a_state_root_must_be_an_empty_absolute_canonical_directory` (×5), `test_a_state_root_inside_a_git_working_tree_is_refused` |
| Partial persistence failure | `test_a_failed_publish_records_nothing_and_removes_only_its_own_file`, `test_a_database_failure_after_publishing_leaves_only_an_unreferenced_blob`, `test_a_failed_transition_consumes_no_authority` |
| Unauthorized cleanup | `test_a_substituted_staging_file_is_never_removed`, `test_an_existing_evidence_name_is_never_overwritten`, `test_a_state_root_holding_foreign_entries_is_not_adopted`, `test_the_target_workspace_is_never_written_or_cleaned`, `test_the_only_file_removal_is_aidos_own_staging_cleanup` |
| Tampered authority records (proof and recovery) | `test_tampered_authority_records_make_the_run_untrusted` (×9, including a no-op control) |
| Direct API **and** normal orchestration path | direct: the `Driver` tests above. Orchestration (DL-3 → DL-2 → store): `test_the_full_chain_completes_through_the_normal_orchestration_path`, `test_the_normal_orchestration_path_never_supplies_human_acceptance`, `test_an_unbound_output_is_refused_on_both_paths`, `test_a_verifier_port_cannot_choose_its_own_outcome`, `test_enforcement_lives_in_the_store_not_in_the_loop` |
| No bypass by skipping a helper | `bind_role_output` and the `Driver` are conveniences. Every refusal above is the store's, reached with hand-built objects. `test_a_step_version_is_dispatched_to_a_role_at_most_once_by_anyone` shows a re-entrant port cannot take a second ticket |
| Boundaries | `test_dl4a_modules_have_no_execution_network_or_environment_surface`, `test_no_cli_command_reaches_dl4a`, `test_the_frozen_dl1_models_are_unchanged_by_dl4a`, `test_the_verification_mirror_matches_the_shipped_report`, `test_shipped_reports_prove_exactly_their_own_outcome` (×3), `test_project_completion_and_blocked_states_stay_unresolved`, plus DL-1's package-wide import guard over the three new modules |

---

## 9. Validation

Run on Windows with the project venv on 2026-10-22, on top of `2ea54f0`.

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_control_plane_dl4a.py -q -p no:cacheprovider` | 116 passed, 0 failed |
| `.venv/Scripts/python.exe -m pytest tests/test_control_plane_dl1.py tests/test_control_plane_dl2.py tests/test_control_plane_dl3.py -q -p no:cacheprovider` | 277 passed (DL-1 90, DL-2 94, DL-3 93), 0 failed. DL-1/2/3 test files unchanged |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (`testpaths = ["tests"]`) | **4309 passed**, 0 failed, 1 warning, 540.4 s (DL-3 FU1's 4193 + DL-4A's 116) |

The first full run had 1 failure, 4308 passed. It was the probabilistic tamper-test defect described in §7, fixed before the final run.

The one warning is the existing Pydantic serializer warning from `tests/test_supervised_implementer.py::test_a_post_load_forged_block_is_refused_by_revalidation`. DL-2 and DL-3 recorded the same warning, and it is unrelated to DL-4A.

The `experiments/` suites were not run. They are outside `testpaths` and
include Node/Pi-executing tests, which this phase forbids.

---

## 10. What DL-4A does not do

There is no real model or API connection, no semantic model call, no live
Pi/Node process, no credential, no environment read, no target-workspace
mutation, no production database, no plan activation for an existing run, no
project completion (DL-1's `request_complete` refusal stands), no automatic
resolution of HUMAN_REQUIRED or RECOVERY_REQUIRED, no product-level token cap,
no CLI command, and no change to `CLAUDE.md`. ALPHA-1B's S0 preflight still
STOPs while DL files are in `src/` (DL-1 §7).

---

## 11. DL-4B entry requirements

1. Independent review accepts DL-4A. This document's status changes only then.
2. **A real `HumanAttestationVerifier` (closes R-1).** It needs a design and
   an authorization that name the attestation mechanism, where the human's
   secret lives (outside the AIDO process and account), how approver identity
   is provisioned, and its failure modes. Its `True` must be unproducible by
   AIDO-side code. Decide R-7: verify before opening the write transaction,
   then re-check the challenge inside it.
3. **A real 5F2D verifier adapter (closes R-2).** It holds the session
   recorder exclusively, takes the workspace only from
   `authorized_target_workspace`, runs the shipped verifier unchanged, and
   records its exact bytes. Add a binding of the report's `target` and
   approval identity to the step's write scope, which needs a Step Contract
   version with write scope (roadmap §14.1, a versioned extension).
4. **The Alpha's human-acceptance stop (R-9).** In authority mode, a step whose
   approved policy requires human acceptance should stop at ACCEPTANCE,
   **without escalating**. The planner's bound decision is kept for the human
   driver, and the human completes through `request_step_acceptance` plus
   `apply_step_transition(human_attestation=...)`. This is not an automatic
   resolution: no exit from HUMAN_REQUIRED is added.
5. **Role-origin policy (R-3).** Either require `human_acceptance_required: true`
   for every Alpha policy, or design role-origin attestation for the reviewer
   (for example, bind the 5F2E `review-packet.v5` digest as review evidence
   the way gate 2 binds verification).
6. Real adapters for the implementer (the qualified harness, once M3/M4
   allow), the reviewer (shipped 5F2E) and the planner. Each inherits its
   shipped authority contract unchanged and is wired only through bound ports.
7. Nothing in DL-4B may relax a DL-4A refusal, open `store.v2` as an authority
   store, or treat an offline store's outputs as authority.

---

## 12. Plan: a bounded, human-supervised end-to-end Alpha

The goal is one Project, one plan, **one step**, one attempt budget, run end
to end against one disposable clone, with a human at every authority boundary.
Every phase below needs its own authorization.

1. **Preconditions (DL-4B done).** Real attestation verifier, real 5F2D
   adapter, the human-acceptance stop, and an authorization naming the
   repository, clone, file and model (the D-10 / AUTH-PILOT pattern).
2. **State root.** `AidoStateRoot.create` on an empty operator-owned
   directory outside every Git tree. The target workspace is a separate,
   disposable clone.
3. **Contract and activation (human ×2).** The human approves the Project
   Contract. They then approve one plan activation: a one-step plan, policy
   `{review_required: true, human_acceptance_required: true, max_attempts: 1}`,
   and the clone's identity.
4. **Issue and run.** Issue the step contract and create the run and step run.
   DL-3 drives DL-2, which dispatches:
   - the supervised implementer (P1B-style, proposal only), under its ticket;
   - the human exact-diff approval and the 5F2C write, outside the control
     plane, as today;
   - the 5F2D verifier adapter, which records evidence;
   - the 5F2E reviewer, under its ticket;
   - the planner, under its ticket.
5. **Stop at ACCEPTANCE (human ×1).** The human reads the evidence: the
   verification bytes by digest, the review packet and the diff. They then
   attest the step acceptance, bound to the attempt, version and evidence
   digest.
6. **End state.** The step is COMPLETE, and the project stays ACTIVE with
   `PLAN_WORK_COMPLETE`. Project completion remains refused. No branch,
   commit, push or PR. A human inspects the state root, re-runs `recover()`
   in a fresh session, and archives the state root as evidence.
7. **Abort rules.** Any refusal, RECOVERY_REQUIRED, HUMAN_REQUIRED,
   containment error or untrusted proof stops the Alpha with no retry, no
   repair and no cleanup beyond what DL-4A already allows.

---

## 13. DL-4A FU1 — authority-parameter consumption boundary

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.** Baseline `67897a9`.

### 13.1 Finding and root cause

The independent review found that `_authorize_step_request()` could return
without consuming or refusing a supplied `human_attestation`. The required
invariant is that every authority-bearing argument handed to an
authority-store transition is validly consumed for that event or explicitly
refused.

Probing the baseline located the silent path precisely:

- **Fresh requests were already refused.** The no-role-output branch of
  `_authorize_step_request()` refused a supplied `role_output` or
  `human_attestation` for `MARK_READY`, `BEGIN_ATTEMPT`, `ESCALATE` and
  `RECOVER_INTERRUPTED`. The new fresh-path regressions pass on the baseline,
  and they are kept as pins.
- **Replays were not.** `apply_step_transition()` returns a replay receipt
  *before* `_authorize_step_request()` runs. So for an already-applied
  `request_id`, any `role_output` and any `human_attestation` were accepted
  and ignored, on every event. That included a genuine, unconsumed
  attestation or dispatch envelope that belonged to another subject, an
  envelope from another run's dispatch with byte-identical output, and a
  replay of a human acceptance with a different or re-signed attestation, or
  with none.

Nothing was consumed on that path, so no authority was spent or widened. But
authority-bearing input was silently ignored, and a caller could read the
receipt as permission for what it had presented.

### 13.2 Correction

There is one rule on both paths: **an event's authority is consumed or
refused, never ignored; a replay is a receipt only for the identical
authorized call.**

- `_refuse_unconsumable_authority()` holds the no-role-output refusal. It is
  shared by the fresh and replay paths, and it names which input was refused.
- `_authorize_step_replay()` runs inside the transaction before a step
  receipt is returned, in an authority store only. It reads only.
  - **A no-role-output event** must present no `role_output` and no
    `human_attestation`.
  - **A role-output event** must present exactly the envelope its original
    transition consumed: the ticket whose `consumed_request_id` is this
    request, the same project run, step run, contract, attempt and role, and
    an output equal to the request payload.
  - **A human acceptance** must present exactly the attestation its original
    consumed, by `attestation_sha256` of the challenge whose `consumed_by` is
    this request. A non-acceptance must present none.
  - Omitting the consumed authority is refused too, so "identical replay"
    means the identical call.
- A receipt still consumes nothing, and it is never new permission. A consumed
  attestation or envelope under a new `request_id` is refused, as before.

Every refusal is an `AuthorityRefusedError` (`AUTHORITY_UNPROVEN`), raised
inside the transaction before anything is written. So a refusal changes no
state, consumes no ticket or challenge, and launches no role.

**Unchanged.** The offline (`store.v2`) path, which already refused both
arguments before any replay check; every frozen model and both store schemas;
every DL-1 validator rule; DL-2 and DL-3, whose replays already pass exactly
their own bound envelope; and the accepted DL-4A fresh-path checks.

### 13.3 Second adversarial review (after the fix)

| Finding | Material? | Resolution / regression |
|---|---|---|
| `issue_execution_plan`'s receipt compared only the `challenge_id`. A repeat activation of an issued plan that named **another policy**, **another target workspace** or a **forged proof** reusing that challenge id was answered as a receipt, and all three were ignored. | Yes, in this exact class. The stored issuance still governed, so no authority was widened, but authority-bearing input was ignored and answered as though activated. | The receipt now requires the identical activation: challenge id, consumed `attestation_sha256`, `policy_sha256` and `target_workspace_sha256`. `test_an_activation_receipt_is_only_for_the_identical_activation` |
| `record_approved_project_contract`'s receipt matched the attestation but not the contract's approval block (`approved_by` / `approved_at`), because the contract identity is its content digest. | Yes, the same class, minor. | The receipt now re-runs `_check_approval_matches`. `test_a_contract_receipt_is_only_for_the_identical_approval` |
| Malformed inputs (dict, subclass, `model_construct`, arbitrary object) on a no-role event, fresh or replayed | No. They are re-validated before the transaction, and so before the replay check. | `test_malformed_authority_on_a_no_role_event_is_refused` (×14) |
| A failure after the ticket is consumed but before the challenge is consumed | No. Both are in one transaction. | `test_a_failure_while_consuming_rolls_back_every_consumption` |
| Escalating the very step whose acceptance is pending, carrying its attestation or planner envelope | No. Refused, and the acceptance still completes afterwards. | `test_an_escalation_cannot_carry_away_the_steps_own_acceptance` |
| A replay of a `recover()`-written `RECOVER_INTERRUPTED` | No. It is a no-role-output event, so the same refusal applies. | covered by the replay matrix |

No other step-transition entry point accepts an authority argument.
`apply_project_transition` and `recover()` take none.

### 13.4 Tests

There are 11 new test functions in `tests/test_control_plane_dl4a.py`, adding
**46 cases** to the 116 already there, for 162 in total.

- `test_a_no_role_event_refuses_extraneous_authority` (×12): four events ×
  attestation / role output / both. Every case is a genuine, unconsumed
  input; after it, the identical bare request applies and the genuine
  acceptance still completes.
- `test_an_escalation_cannot_carry_away_the_steps_own_acceptance`
- `test_a_replayed_no_role_event_refuses_extraneous_authority` (×12)
- `test_a_replayed_role_output_event_must_carry_its_own_consumed_binding`
- `test_a_replayed_human_acceptance_is_a_receipt_only_with_its_own_attestation`
- `test_a_legitimate_acceptance_still_needs_its_exact_unconsumed_attestation`
- `test_malformed_authority_on_a_no_role_event_is_refused` (×14)
- `test_a_failure_while_consuming_rolls_back_every_consumption`
- `test_an_activation_receipt_is_only_for_the_identical_activation`
- `test_a_contract_receipt_is_only_for_the_identical_approval`
- `test_an_offline_store_refuses_a_human_attestation_too`

Each refusal asserts an unchanged snapshot of the transitions, dispatch
tickets, approval challenges, step runs and project runs.

**Against the original `store.py`**, 16 cases fail: the 12 replay-matrix
cases, the role-output replay, the human-acceptance replay, and the two
second-review receipt tests. The other 30 pass, because the baseline
fresh-path refusals were already correct. **With FU1**, all 162 pass.

### 13.5 Validation

Run on Windows with the project venv on 2026-10-22, on top of `67897a9`.

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_control_plane_dl1.py tests/test_control_plane_dl2.py tests/test_control_plane_dl3.py tests/test_control_plane_dl4a.py -q -p no:cacheprovider` | **439 passed**, 0 failed (DL-1/2/3 277, unchanged files; DL-4A 162) |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (`testpaths = ["tests"]`) | **4355 passed**, 0 failed, 1 warning, 583.4 s (DL-4A's 4309 + FU1's 46). The warning is the existing, unrelated Pydantic serializer warning recorded in §9 |

### 13.6 Still open, documented separately (not FU1 scope)

FU1 closes nothing below and does not expand into any of it.

- **External human-verifier trust remains open (R-1).** An attestation is only
  as authentic as the injected `HumanAttestationVerifier`. The default
  verifier approves nothing.
- **Real 5F2D evidence origin remains open (R-2).** The store proves that
  evidence was recorded for the dispatch and re-derives its outcome. It does
  not prove that the bytes came from a genuine 5F2D run.
- **Role-output origin is not authenticated by a dispatch ticket (R-3).** A
  ticket binds an output to one dispatch. It does not prove which component
  produced it, and a caller that holds the store can mint and answer one.
- **Filesystem containment is not a race-free sandbox (R-5).** The checks are
  path and identity based, with no handle-relative OS API. A concurrent
  actor between a check and the next system call is not excluded.
