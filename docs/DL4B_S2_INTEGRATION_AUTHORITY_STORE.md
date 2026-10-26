# DL-4B S2 — Integration Authority Store

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `d3581794a24e3764b0087a3d8ed076072c673fe2` (S0 + FU1 and S1 accepted and frozen for offline scope) |
| Contract | `docs/DL4B_REAL_INTEGRATION_BOUNDARY_DESIGN.md` (AMEND1): FD-3 to FD-6, FD-8a, FD-10, FD-15, FD-16, §8, slice S2 (§11) |
| Kind | Offline implementation. No exact-diff approval, write intent, handoff publication, claim reception, observation, reviewer, acceptance hold or Alpha driver. No subprocess, Git, network, model, credential, account, ACL or workspace write |
| Not authorized | S3–S7, E-6, E-12, any live run, any `CLAUDE.md` change |

S2 joins S0's identity boundary proof and S1's attestation verifier into one
**mechanically enforced authority store**, `aido-control-plane-store.v4`. It is
DL-4A's authority store with three versioned changes:

```text
WHO MAY HOLD IT      only a session whose FD-16 proof passed; the proof is re-run at
                     EVERY consumption boundary, pinned to one boundary digest, and
                     bound to this state root and to the boundary's clone
HOW A HUMAN APPROVES approval-challenge.v2 / human-attestation.v2: verified by S1 before
                     the write transaction, re-checked inside it, consumed once, and
                     re-verified against the current registry on every proof (FD-4/5)
WHAT IT ACTIVATES    plan-activation-subject.v2: plan + the Alpha policy + the clone +
                     write-scope.v1 + project-config digest + identity-boundary digest
```

It also fixes the store.v4 tables that S3–S6 will write. **S2 writes none of
them, mints no recorder and has no API that accepts claim, observation or
evidence bytes.** Every role-output event is therefore refused here.

---

## 1. Modules

| Module | Kind | Content |
|---|---|---|
| `control_plane/integration_records.py` | new, pure | `WriteScopeV1` (`write-scope.v1`), `ALPHA_EXECUTION_POLICY`, `is_alpha_policy`, `write_scopes_sha256`, `plan_activation_subject_v2_sha256`, and the closed vocabularies of the later records (claim shapes, observation kinds, write-intent states, the two provenance labels) |
| `integration/integration_store.py` | new | `IntegrationStore` (store.v4), its schema, `IsolationUnprovenError`, `LATER_SLICE_TABLES` |
| `integration/integration_session.py` | new | `IntegrationSession`, `open_integration_session` (production), `open_integration_session_from_facts` (library) |
| `control_plane/store.py` | changed | `_open` reads its schema, table set, version and `store_meta` entries from three overridable class hooks (`_layout`, `_meta`, `_meta_refusal`). The base hooks return exactly what `_open` hard-coded before; no v2 or v3 behavior, message or schema changed |
| `integration/__init__.py` | changed | docstring |
| `tests/test_dl4b_s0_identity_boundary.py` | changed | the package module-set pin lists the two S2 modules (as S1 did for its three); no S0 test logic changed |
| `tests/test_dl4b_s2_integration_store.py` | new | 70 functions, 154 cases |

The store lives in `integration/`, not `control_plane/`, because it must call
S0 and S1, and `control_plane/` may import neither (DL-1 import guard, S0/S1
static tests). `control_plane/` still imports nothing from `integration/`.

## 2. Public contract

```python
open_integration_session(state_root: AidoStateRoot) -> IntegrationSession          # production
open_integration_session_from_facts(state_root, facts, *, clock) -> IntegrationSession  # library

IntegrationSession: .state_root  .store  .boundary_sha256  .is_production  .close()
```

- **Production takes the state root and nothing else.** The prover is S0's
  `prove_identity_boundary`, the verifier S1's `RegistryHumanAttestationVerifier()`,
  the clock the system's. No parameter, flag, config key or environment variable
  supplies a proof, facts, a verifier, a digest or a clock, and there is no
  same-account mode (static test).
- **Library sessions are never production.** Every proof and verifier record is
  `injected`, and the store records `authority_origin = injected` at creation.
  A production session refuses an injected store and the reverse
  (`store_meta`), so synthetic authority is never consumable as production
  authority.
- **Order at open:** prove → check the proof's origin and the verifier's origin
  agree (and a `windows` proof is independently evaluated) → require the
  boundary's declared `state_root` to be this `AidoStateRoot` → re-verify the
  root's layout → only then create or open the database → if a plan activation
  exists, require its bound boundary digest. A failure creates nothing.
- **The session exposes no recorder**, no verifier and no prover; it is
  immutable, unsubclassable and uncopyable.

### Store API in store.v4

| Method | store.v4 behavior |
|---|---|
| `request_project_contract_approval(content)` | `approval-challenge.v2` |
| `record_approved_project_contract(contract, attestation: HumanAttestationV2)` | FD-5 ordering (§5) |
| `request_plan_activation(*, execution_plan, execution_policy, write_scopes)` | Alpha profile; subject v2. **No workspace parameter:** the workspace is the proven boundary's clone |
| `issue_execution_plan(plan, *, execution_policy, write_scopes, attestation)` | FD-5 ordering; records the activation and its scopes |
| `issue_authorized_step_contract`, `create_project_run`, `create_step_run`, `issue_dispatch_ticket`, `apply_project_transition`, `recover`, the `get_*`/`list_*` reads, `authorized_target_workspace` | DL-4A's, behind the boundary re-proof, with v4 proofs (§4). One project run per activation |
| `apply_step_transition` | DL-4A's for `MARK_READY`, `BEGIN_ATTEMPT`, `ESCALATE`, `RECOVER_INTERRUPTED`. **Every role-output event is refused** (S3–S6 evidence does not exist). Any `human_attestation` is refused (S6) |
| `request_step_acceptance` | refused (S6) |
| `record_project_contract`, `record_execution_plan`, `record_step_contract` | refused (DL-4A) |
| `inspect_*`, `transitions_for` | raw diagnostic reads, never proof, no re-proof (DL-4A semantics) |

Refusals are `AuthorityRefusedError` (`authority_unproven`). A boundary failure
is its subclass `IsolationUnprovenError`, message
`authority_unproven: isolation_unproven:<category>: …`, with S0's category or
one of the store's binding categories (`state_root_unbound`, `clone_unbound`,
`origin_mismatch`, `proof_invalid`). An attestation refusal is S1's
`HumanAttestationRefusedError`; the store raises `challenge_spent`,
`challenge_expired`, `statement_mismatch` and `timestamp_invalid` itself.

## 3. Pre-implementation adversarial analysis

| Object | Who creates / mutates it | What proves provenance | Supported-caller bypass? | Can valid objects disagree? | Checked at consumption | Partial failure | Claim promoted? | Disclosure |
|---|---|---|---|---|---|---|---|---|
| **Boundary proof** | S0's prover only (private token) | Minted record; origin fixed by entry point | Caller supplies a proof: no parameter accepts one. Caller supplies a prover (private context): the store type-checks every result, refuses an object it already accepted, and pins origin and digest | Proof of another boundary, state root, origin → refused | Re-run at every public call and in every hook a base path reaches (§5.2) | No state | — | S0 messages: roles, SIDs, relative labels |
| **Verifier record** | S1's verifier only | Minted record | Recycled record, record for another challenge, truthy non-record → refused | Record vs challenge, attestation, state root, boundary, origin → all compared | At consumption (`consumption`) and every proof (`reproof`) | No state | — | Categories only; verifier exceptions reduced to a type name |
| **Approval challenge v2** | Store, persisted | Row; the challenge handed to S1 is rebuilt from the row, never the caller's | A caller-built challenge answers nothing (unknown id → `statement_mismatch`) | Attestation for another kind or subject → refused | Pre-check, then re-check inside the write transaction (FD-5) | Consumed in the same transaction as what it authorizes | — | — |
| **Consumed attestation** | Store, in the consuming transaction | Signature, re-verified against the **current** registry on every proof; audit columns (statement, signature, fingerprint, flags, counter) must equal the re-proof | Tampered body, digest, audit, origin, subject → untrusted | Contract approval block vs attestation → refused | Every authoritative proof and `recover()` (FD-4) | — | — | Proof never echoed |
| **Plan activation v2** | Store, from a signed subject | Consumed `plan_activation` challenge | `record_execution_plan` refused; workspace never a caller's path | Policy ≠ Alpha, ≠ 1 step, ≠ 1 scope, scope step ≠ plan step, config digests ≠, boundary ≠ pinned, workspace ≠ clone | Subject v2 recomputed from stored rows at every proof | One transaction | — | — |
| **Write scope** | The human, inside the activation | Row digest + scopes digest inside the signed subject | No API records one outside activation | Scope vs plan step | Every proof | Same transaction as the activation | — | Repo-relative path only |
| **Integration store / session** | `open_integration_session*` only | Proof-first open; `store_meta` origin and root id | `IntegrationStore.open`, `_open_authority`, `_open` without the v4 context → refused; base methods called unbound → hooks re-prove (§7 R-1) | v2/v3/v4 files → refused across | Every open | Creation commits schema + meta atomically | — | — |
| **Dispatch ticket** | Store (DL-4A unchanged) | Row | DL-4A closed | — | DL-4A; in S2 no ticket may be answered or held | DL-4A | A ticket answers nothing in S2 | — |
| **Execution claim / observation / write intent / handoff / exact-diff / evidence rows** | **Nobody in S2** | — | No API accepts their bytes; no recorder exists | — | Any row present → every run untrusted | — | Role-output events refused; a claim cannot exist, let alone be promoted | — |
| **DL-4A v3 recorder and v1 records** | DL-4A | — | v3 recorder pointed at a v4 store → refused; v1 paths called unbound → their v3 tables do not exist in v4 | — | — | — | — | — |

## 4. The store.v4 schema

DL-1's tables (`store_meta`, `contracts`, `project_runs`, `step_runs`,
`run_bindings`, `transitions`), unchanged, plus:

| Table | Written in S2 | Content |
|---|---|---|
| `approval_challenges_v2` | yes | v2 challenge; on consumption: `consumed_by`, the attestation and its digest, and the **approver-key audit**: statement, signature and key fingerprint digests, authenticator flags and counter, UV, registry and boundary digests, `facts_origin`, `verified_at`. A CHECK makes the audit all-or-nothing with consumption |
| `plan_activations` | yes | plan, contract, policy (+digest), workspace (+identity digest), `write_scopes_sha256`, `project_config_sha256`, `identity_boundary_sha256`, challenge |
| `write_scopes` | yes | one row per scope: body and digest |
| `step_contract_issuances` | yes | DL-4A's, referencing `plan_activations` |
| `dispatch_tickets` | yes (DL-4A columns) | DL-4A's, plus S6's held columns (`held_envelope`, digest, `held_at`), all-or-nothing |
| `exact_diff_approvals` | **no** (S3) | plan, step, scope digest, artifact digest, challenge, consuming ticket |
| `authority_observations` | **no** (S3/S4) | ticket, kind `m0`/`m1`/`m2`, target digest, HEAD oid, `.git` control digest, manifest digest, entry count, provenance fixed `authority_observation` |
| `write_intents` | **no** (S3) | ticket, exact-diff approval, scope and artifact digests, workspace identity, M0, state ∈ {pending, completed, refused, indeterminate} |
| `execution_handoffs` | **no** (S3/S4) | ticket, artifact and config digests, handoff and outbox directory identities |
| `execution_claims` | **no** (S3/S4) | ticket, claim digest, length, shape ∈ the four §8 shapes, provenance fixed `execution_claim` |
| `write_evidence`, `verification_evidence_v2`, `review_evidence` | **no** (S3–S5) | the bindings of §5.2; provenance fixed `execution_claim` |

The provenance labels are **schema CHECKs**: no row can relabel a claim as
authority. v4 has no `verification_evidence`, `plan_issuances` or
`approval_challenges` table, so any v3 path that reaches a v4 store fails on a
missing table rather than reading v4 rows with v3 meaning.

**Column details of the S3–S6 tables are provisional.** S2 refuses any row in
them, so no stored state depends on their shape; their slice may amend them
before any v4 store holds such a row (no v4 store exists outside tests).

## 5. Trust boundaries and transaction ordering

### 5.1 Approval (FD-5)

```text
1  re-prove the boundary (pinned digest, state root, origin)
2  short transaction, reads only: receipt check; the store's OWN challenge row:
     subject recomputed from the actual objects, unconsumed, unexpired, window
3  S1 verify_for_consumption(state_root_id = this root, challenge = rebuilt from the row)
     OUTSIDE any transaction; the record must be fresh, of this origin (production:
     is_production), for this root, challenge, subject, approver, time, attestation
     digest and pinned boundary
4  write transaction: re-check step 2 completely (consumed? expired? same challenge?),
     insert the record it authorizes, consume the challenge with the audit columns
     (UPDATE ... WHERE consumed_by IS NULL, rowcount 1)
```

A challenge consumed or expired while S1 was verifying is refused at step 4
(tested by consuming it from inside the verification, and by expiring it
there). An identical repeat is a receipt only while the recorded approval
still re-proves.

### 5.2 Re-proof at every consumption boundary (FD-16)

Each of the 19 public methods in the `REPROVED` set re-runs the S0 proof once,
before anything is read or validated (`@_reproving`). The hooks every base
path must pass through (`_transaction`, `_project_integrity`, `_load_contract`)
re-prove by themselves whenever no re-proven call is running, so calling a
`ControlPlaneStore` method unbound on a v4 store cannot skip it. Each proof is
checked: exact type, not already accepted, the store's origin, the pinned
digest, this state root. The root's DL-4A layout is re-verified with it.

A boundary failure refuses **everything**, `recover()` included: if the boundary
does not hold, nothing in the store is read as authority or written. An
in-flight step therefore stays as persisted until a later, proven session's
`recover()` reduces it to RECOVERY_REQUIRED. That is the same end state DL-2's
reduction would reach, without writing to a store whose boundary is unproven.

### 5.3 Proofs (FD-4) and `recover()`

Every authoritative proof re-derives, from stored rows: the contract approval
(re-verified against the current registry); the activation (Alpha profile,
each scope digest, the scopes digest, one config digest, the pinned boundary
digest, the boundary's clone, the v2 subject, the plan-activation approval,
re-verified); one project run per activation; no answered or held ticket; no
row in an S3–S6 table; no challenge of an S3/S6 kind; every consumed challenge
explained by what it approved; no role-output transition. Any issue makes the
run untrusted; `recover()` escalates it to HUMAN_REQUIRED (DL-1 unchanged).
Revocation, deletion, rotation, an unreadable or unprotected registry all fail
the re-proof, so revocation invalidates historical authority (FD-3, D-11).

### 5.4 Crash matrix

| Crash at | Durable result | After restart |
|---|---|---|
| Any statement of an approval's write transaction, or its `COMMIT` | Nothing (rolled back) | The challenge is unconsumed; the same attestation consumes it exactly once |
| Right after the approval's `COMMIT` | Consumed once | The identical call is a receipt |
| Between verification (step 3) and step 4 | Nothing | As above |
| Any statement of an activation | Nothing | As above |
| A transition or ticket insert in EXECUTING | Rolled back | `recover()` → RECOVERY_REQUIRED; the ticket never answers; nothing is dispatched twice; `recover()` is idempotent |

## 6. Evidence classes in S2 (FD-15)

The only authority-plane facts S2 holds are the authority identity's own
records: challenges and their consumption, activations, scopes, issuances,
tickets, transitions. No execution claim and no observation exists. So:

- no role-output event (`IMPLEMENTATION_RETURNED`, `VERIFICATION_OBSERVED`,
  `REVIEW_OBSERVED`, `DECIDE_ACCEPTANCE`) is accepted, even with a genuine
  ticket and a structurally valid envelope;
- through DL-3 → DL-2, a port answering its genuine implementer ticket with a
  self-made report leaves the step at RECOVERY_REQUIRED, the ticket
  unconsumed, and no role-output transition (tested);
- DL-4A's `VerificationEvidenceRecorder` pointed at a v4 store is refused;
- no public store or session method takes bytes, or a parameter named like a
  claim, observation, evidence, report, stdout, manifest or recorder (static).

## 7. Second adversarial review (after coding) and regressions

Every guard below was also checked by mutation (disabled, its regression run,
restored): each disabled guard fails its regression, with the one exception
noted.

| Id | Finding | Material? | Fix / regression |
|---|---|---|---|
| R-1 | Calling a base method unbound (`ControlPlaneStore.get_step_run(store, …)`) skipped the subclass's re-proof wrapper. The v4 authority hooks still ran, but FD-16's boundary proof did not | **Yes** (FD-16) | Re-proof moved into the hooks every base path uses, with a depth counter so a normal call still proves once. `test_calling_a_base_class_method_unbound_cannot_skip_the_boundary`, `test_one_public_call_proves_the_boundary_once` |
| R-2 | DL-4A's v1/v3 paths (challenge, attestation, activation, acceptance) called unbound on a v4 store | No: their tables do not exist in v4, so they raise and change nothing | `test_v3_authority_paths_called_unbound_fail_closed` (this is why v4 table names differ from v3's) |
| R-3 | DL-4A's verification recorder against a v4 store would have raised `AttributeError` (no recorder key) | Fail-closed but outside the refusal contract | `_record_verification_evidence` refuses. `test_dl4a_verification_recorder_cannot_record_into_an_integration_store` |
| R-4 | Inherited `open` / `_open_authority` could build an `IntegrationStore` around a v2 or v3 schema | Defence in depth (`_open` already required the v4 context) | All three refuse. `test_the_integration_store_has_no_other_way_to_open` |
| R-5 | `max_attempts: 1` is per step run, so a second project run of one activation would be a second attempt line | Yes (FD-8a intent) | One project run per activation, at creation and in every proof. `test_an_activation_authorizes_one_project_run` |
| R-6 | A prover or verifier returning a previously accepted object | Yes against a mis-wired context | Identity-tracked refusal. `test_a_previously_valid_proof_object_is_never_accepted_again`, `test_a_recycled_or_foreign_verifier_record_is_refused` |
| R-7 | A v1 `HumanAttestation` handed to `apply_step_transition` was refused only incidentally, with a v1 message | No | Any attestation is refused explicitly (S6). `test_a_human_attestation_is_refused_on_every_transition` |
| R-8 | Harness defect: a crash-at-`COMMIT` test hit the pre-check transaction's `COMMIT`, not the consuming one | Test-only | Crash proxy counts occurrences |
| — | Mutation **not** caught: removing the Alpha-profile re-check from the proof | No | Unreachable alone: any change to the policy, plan or scopes also changes the signed v2 subject, which fails the re-proof first. Kept as defence in depth |

Also examined and found sound: cross-kind attestation confusion (an
activation signature presented as a contract approval, and the reverse); a
signature for another state root, an unregistered key, another approver's
binding, missing presence, a typed phrase as proof; malformed attestation types
(v1, dict, `model_construct`, subclass, `None`); a boundary changed mid-session
and between sessions; a tampered bound boundary digest (the store does not
open); a planted file in the state root; a replaced clone directory.

## 8. Tests

`tests/test_dl4b_s2_integration_store.py`, 70 functions, 154 cases.

State roots and clones are real `tmp_path` directories. The boundary, registry
and every security fact come from S0's and S1's synthetic worlds, with the
boundary's `state_root` and `clone` pointed at those directories (their
ancestors provisioned admin-owned and protected). Signatures come from S1's
test-only software keys. Harness-bound tests run on Windows only (the paths
must be Windows paths); static tests run everywhere.

| Acceptance criterion | Tests |
|---|---|
| 1 v4 creation, reopening, version separation, schema integrity | `…has_the_v4_schema_and_is_bound`, `…reopens_and_keeps_its_state`, `test_v2_v3_and_v4_stores_never_open_each_other`, `…no_other_way_to_open`, `…another_origin…`, `…another_state_roots_database…`, `…refuses_relabelled_provenance…` |
| 2 Production session requires the complete S0 proof | `…takes_nothing_but_the_state_root`, `…refuses_on_this_host_before_touching_the_state_root`, `…without_the_complete_boundary_proof` (×5), `…state_root_the_boundary_does_not_declare`, `…pinned_for_the_whole_session`, `…only_the_bound_boundary_opens_the_store`, `…every_consumption_boundary_reproves…`, `…unbound_cannot_skip_the_boundary` |
| 3 Injected or forged proofs and verifier results cannot establish authority | `…library_session_is_never_production`, `…other_origin_verifier…`, `…previously_valid_proof_object…`, `…returns_no_proof…` (×4), `…raises_anything…`, `…proof_of_another_world…`, `…recycled_or_foreign_verifier_record…`, `…verifier_failure_is_a_refusal_without_detail` |
| 4 Atomic, single-use challenge consumption | `…single_use_and_a_replay_is_a_receipt`, `…consumed_while_it_was_being_verified…`, `…expires_during_verification…`, `…expired_challenge…`, `…own_challenge_and_state_root`, `…another_kind_of_subject…`, malformed attestations (×5) |
| 5 Revoked or modified registry entries invalidate re-proof | `…revoked_rotated_or_unprotected_registry…` (×5), `…revocation_is_total_and_persists…`, `…revoked_key` (new challenge), another approver unaffected |
| 6 Activation binds scope, config and boundary | `…binds_scope_config_and_boundary`, `…only_the_alpha_profile_is_activated` (×7), scope type and content (×28), `…receipt_is_only_for_the_identical_activation`, `…one_project_run`, `…replaced_clone…`, `…workspace_is_the_boundary_clone…` |
| 7 Session APIs cannot expose recorders | `…exposes_no_recorder_and_cannot_be_altered`, `…dl4a_verification_recorder…`, `…no_public_store_or_session_api_accepts_bytes` |
| 8 Caller-supplied claims cannot become authoritative evidence | `…no_role_output_event_is_accepted…`, `…caller_supplied_verification_review_or_decision…` (×3), `…orchestration_path_cannot_promote…`, the tamper rows for every S3–S6 table |
| 9 Crash and recovery matrices | `…crash_while_recording_a_contract_approval…` (×3), `…crash_after_the_commit…`, `…crash_while_activating…` (×4), `…crash_in_the_attempt…` (×3), `…not_consumable_before_recover` |
| Tamper matrix → untrusted | `test_tampered_authority_records_make_the_run_untrusted` (×30: attestation body, digest, audit columns, origin, subject, consumption, policy, scopes, config, workspace, activation challenge, issuance, held and answered tickets, an S3 challenge kind, a row in each S3–S6 table), a no-op control, the bound-boundary tamper |
| Static | no subprocess/socket/HTTP/`os`/`ctypes`/threading/harness/Win32-facts import in S2 modules; no `environ`, file-writing or `max_tokens` name; only the production entry wires production trust sources; no CLI or `control_plane` module reaches S2; v4 records pure; frozen models unchanged |

Every refusal test asserts an unchanged snapshot of every table. No test
creates an account, needs elevation, changes an ACL, opens a socket, runs a
subprocess, or writes inside a clone.

## 9. Compatibility with frozen contracts

- **DL-1/2/3 and DL-4A:** unchanged. The `store.py` change is a hook
  extraction; the v2 and v3 suites pass unmodified (§11).
- **S0 and S1:** no source line changed. The integration store uses only their
  public entry points (`prove_identity_boundary`, `prove_identity_boundary_from_facts`,
  `RegistryHumanAttestationVerifier()`, `.from_facts`, `verify_for_consumption`,
  `reprove`) and public types. S1's §2.1 obligations are met: `verify_for_consumption`
  before the transaction with the store's own challenge and root id; the
  in-transaction re-check; `reprove` on every proof and `recover()`;
  `is_production` required in production; `identity_boundary_sha256` compared
  with the pinned (and activation-bound) digest.
- **ROLE ≠ HARNESS ≠ BACKEND ≠ MODEL:** no v4 record names a backend, provider,
  model or endpoint.
- **No token cap, no CLI surface, no subprocess, no Git, no network, no model,
  no credential, no `CLAUDE.md` change.**
- **No frozen contract contradiction was found.**

## 10. Implementation choices the reviewer should confirm

1. **The workspace is the boundary's clone, never a parameter.** v4 activation
   has no `target_workspace` argument; the human signs the identity of the
   clone the proven boundary declares.
2. **One identity boundary per store.** Every consumed approval records the
   boundary digest it was verified under and must equal the session's pinned
   digest on re-proof. Re-provisioning the boundary (E-12) must happen before
   the first approval, not between approvals. A changed boundary makes the
   store refuse to open once an activation binds it, and makes earlier
   approvals untrusted before that.
3. **A boundary failure blocks `recover()` too** (§5.2).
4. **The project config is bound by digest only.** The scope's
   `project_config_sha256` is what the human approves; S2 neither reads nor
   parses config bytes.
5. **`write-scope.v1` paths are printable ASCII** (a pure module cannot
   normalize Unicode), refuse 8.3 short names, reserved device names and any
   `.git` component, and `base_head_oid` is a 40- or 64-hex object id.
6. **One project run per activation**, beyond the design's FD-8a text (R-5).
7. **The approver-key audit** (statement, signature, fingerprint, flags,
   counter) is stored and must equal every re-proof; the registry digest is
   stored for audit but may legitimately change.

## 11. Remaining S3–S7 obligations

- **S3** — `request/record_exact_diff_approval` (`exact_diff_approval`
  challenges are unexplained in S2); `claim_write_intent` consuming the
  approval; the FD-18 observer (M0/M1) and the **activation-time `.git`
  control digest**, which S2 does not record (it has no observer); the FD-17
  claim receiver; the claim and observation **recorders**, minted inside the
  session only into `WriteHandoffAdapter`; the state-root layout for handoff,
  outbox, claim and manifest blobs (DL-4A's `AidoStateRoot` admits only
  `evidence/verification` and `staging` today); replacing S2's
  "any row is unexplained" rule for its tables with their real explanation;
  allowing `IMPLEMENTATION_RETURNED` only with a completed intent, the write
  claim and M0/M1 for the ticket.
- **S4** — review handoff, claim classification, M2, verification binding;
  checking the session's config bytes against the scope's digest and the
  config's workspace root against the clone; `verification_evidence_v2`.
- **S5** — review observation from the same claim; `review_evidence`.
- **S6** — the DL-2 hold branch, `hold_acceptance_decision` (held columns),
  `held_acceptance_bundle`, `step-acceptance-subject.v2`,
  `AlphaPlannerRule`, bundle publication; the signed v2 acceptance through
  `apply_step_transition` (refused in S2).
- **S7** — the non-model driver over `open_integration_session`; launching A
  with an isolated interpreter (S0 §8 item 1); presenting statements to sign.
- **E-12** — the production proof's duration per call: store.v4 re-proves at
  every public call (S0 walks the install roots and the state root each time).

## 12. Residuals

- **Production success is unproven on this host.** The production session
  refuses here (no provisioned A, X, O, boundary or registry) before touching
  the state root; only E-12 can show it passing.
- **In-process code reaching private attributes** (`_authority`, `_conn`,
  `_accepted`, the S0/S1 tokens) is out of scope (DL-4A §2).
- **Diagnostic reads** (`inspect_*`, `transitions_for`) are not re-proven, as
  in DL-4A; they are never proof.
- **A proof is a moment** (S0 §9). Re-proof narrows, not closes, the window.
- **`_accepted` grows with each call** for the life of a session (one boundary
  proof and up to two verifier records per call). Sessions are short-lived;
  S7's long attempt invocation should be measured in E-12.
- D-7 (restored state root), D-8 (host clock), R-5 (path races) are unchanged.

## 13. Validation

Run on Windows with the project venv on 2026-10-26, on top of `d358179`.

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_dl4b_s2_integration_store.py -q -p no:cacheprovider` | **154 passed** |
| `… tests/test_control_plane_dl1.py tests/test_control_plane_dl2.py tests/test_control_plane_dl3.py tests/test_control_plane_dl4a.py tests/test_dl4b_s0_identity_boundary.py tests/test_dl4b_s1_attestation_verifier.py` | **1104 passed** (DL-1/2/3 and DL-4A files unchanged; S0 file changed only in its module-set pin) |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (`testpaths = ["tests"]`) | **5174 passed**, 0 failed, 1 warning, 601 s. The warning is the existing, unrelated Pydantic serializer warning from `tests/test_supervised_implementer.py::test_a_post_load_forged_block_is_refused_by_revalidation` (DL-4A §9) |

**Final status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**
