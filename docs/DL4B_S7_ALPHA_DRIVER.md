# DL-4B S7 — Offline Alpha Driver

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `b93121950950b199ecc4cc4cd851625e9ac9aee3` (S0–S6 accepted and frozen for offline scope) |
| Contract | `docs/DL4B_REAL_INTEGRATION_BOUNDARY_DESIGN.md` (AMEND1): §5.6, §5.8, §6, §7, slice S7 (§11); the S0–S6 records' S7 obligations |
| Kind | Offline integration. No live Alpha, no E-12, E-6 or AUTH-PILOT, no account, no credential, no model, no Git, subprocess, network or repository code in A |
| Operator procedure | `docs/DL4B_S7_OPERATOR_RUNBOOK.md` |

S7 connects S0–S6 into one human-supervised Alpha, and adds **no authority**.
The driver is a non-model A-side entry point: it opens an integration session
(S0's proof), derives the Alpha's stage from what the store has recorded, and
calls the accepted store APIs and the DL-3 outer loop, which keep every check
they had. It never launches, runs, sends or signs anything, and it never
executes an X-side command: it presents them.

```text
inbox (O)                      A: alpha_driver (one verb per invocation, fresh session each time)
 alpha-definition.json ──────►  derive:  definition (strict) + store.alpha_inventory() (re-proven)
 attestation-<kind>.json         [+ recover(run) + re-proven run reads]  ──► stage
 approved diff, config                │
                                      ├─ status             report only
                                      ├─ request-approval   store.request_*  → subject re-derived by the driver,
                                      │                     must equal the challenge's, else not presented
                                      ├─ record-approval    store.record_* / issue_execution_plan /
                                      │                     apply_step_transition(human_attestation=v2)
                                      ├─ run                issue/create (only if absent) → ProjectOuterLoop
                                      │                     (DL-3 → DL-2 → S3/S4/S5 adapters → S6 rule → hold)
                                      │                     announcing each X step; X runs it while A waits
                                      └─ decline-acceptance ESCALATE → HUMAN_REQUIRED (nothing signed)
published/ (O reads) ◄────────  the report (cmd.exe redirection), the S6 bundle (the store publishes it)
```

---

## 1. Modules

| Module | Kind | Content |
|---|---|---|
| `integration/alpha_driver.py` | new | `AlphaDriver` (the five verbs), `AlphaDefinitionV1` / `parse_definition`, `AlphaStage`, `DriverOutcome`, `DriverReport`, the announcing port wrappers, and `main` (the production entry point) |
| `integration/alpha_operator.py` | new, pure | O's helper: `presented_challenge`, `statement_bytes`, `attestation_bytes`, `main`. Imports only `control_plane` |
| `integration/integration_store.py` | changed, additive | `alpha_inventory()` and `read_inbox_document()` (both `@_reproving`, read-only), `AlphaInventory`, `RecordedExactDiffApproval`, `OperatorDocument`, `MAX_OPERATOR_DOCUMENT_BYTES`; docstring paragraph. Nothing existing changed |
| `integration/__init__.py` | changed, docstring | S7 paragraph |
| `tests/test_dl4b_s7_alpha_driver.py` | new | §8 |
| `tests/test_dl4b_s2_integration_store.py` | changed, additive | the public-method classification lists the two S7 reads as re-proven, each with a boundary-failure call. No assertion weakened |
| `tests/test_dl4b_s0_identity_boundary.py` | changed, one constant | the package's module set lists S7's two modules, as S1–S6 extended it |

No S0–S6 public contract or semantics changed. DL-1/2/3/4A are unchanged.
`CLAUDE.md` is unchanged: the driver is not a model-calling command, and no
CLI command reaches it.

### 1.1 C7-1: two discovery reads (additive)

The prompt requires that every invocation decides from **persisted,
re-proven** state and never from a caller's statement. The accepted public
API could not answer three questions without a caller's help: *which project
contract is approved* (it is found by digest, and the digest depends on the
approval), *whether the step's exact-diff approval is recorded and unspent*
(no public read at all), and *which project run exists* (its id is a fresh
UUID the store returns once, at creation). Without them the driver would have to trust the
operator's word, or begin an attempt to find out (which spends the attempt
budget). So S7 adds two read-only, re-proven methods, in the S6 manner
(classified in S2's suite, boundary-failure tested):

- `alpha_inventory()` — every recorded project contract (approval re-proven),
  every plan (activation re-proven by `_plan_issuance_issue`), every exact-diff
  approval (re-proven by `_exact_diff_proof`, with `spent`), the ids of the
  project runs (discovery only: a run is authority only after `recover()` and
  a re-proven read), and the proven boundary for presentation. A record that
  does not re-prove raises `StateUntrustedError`.
- `read_inbox_document(name)` — S3's private `_read_inbox` (O's single-link
  regular file at its own path) behind the boundary proof, bounded by
  `MAX_OPERATOR_DOCUMENT_BYTES` (= `MAX_APPROVED_DIFF_BYTES`), returning an
  `OperatorDocument` (name, content, SHA-256). It takes a name and nothing
  else. Never authority by itself.

This is not a frozen-contract change: no existing method, record, schema,
table or meaning changes, and both methods only read.

## 2. Pre-implementation adversarial analysis

The driver was analyzed as a potential authority bypass before it was written.
The question for every row: can a supported call through the driver reach a
state the store would not grant to a direct caller?

| Threat | Route considered | Design answer |
|---|---|---|
| **Stage skipping** | `run` before the exact-diff approval; `record-approval` reading a later stage's attestation; `decline` before a hold; `request-approval` after the last approval | Every verb first derives the stage from the store and refuses if it is not that stage's next authorized action. Each stage reads exactly one fixed inbox name. `run` is allowed only at `attempt` (approval recorded **and unspent**, no begun attempt) or `decision`. The store still refuses on its own |
| **Cross-project / cross-attempt confusion** | A state root holding another contract, plan, approval, step contract, or a second run; a changed definition | The definition must describe **every** record the inventory lists (`foreign_record` otherwise, nothing written). One run, one step, the step contract re-derived from the definition and compared |
| **Reusing an old approval or challenge** | A consumed attestation copied under the next stage's name; an expired challenge's signature; a contract attestation replayed | The kind is checked before any store call (`attestation_kind_mismatch`); S2's `_open_challenge` refuses consumed, expired or mismatched challenges; recorded approvals are receipts only for the identical attestation |
| **Reusing an execution claim** | A claim from an earlier ticket; re-running the attempt after a claim was recorded | Per-ticket outboxes (S3/S4); an interrupted attempt is reduced by `recover()` and the verb set has no way to resume it |
| **Repeated invocation after partial failure** | Any verb after a crash at any commit | Each invocation is a fresh session; the stage is re-derived; creation calls run only when the inventory shows nothing (`issue_authorized_step_contract` is the store's receipt) |
| **Restart between every durable operation** | A kill after each commit of `run` and of each approval | §5; tested at 13 attempt boundaries and 3 approval boundaries |
| **Caller-controlled paths, digests, identities, statuses** | Arguments naming a run, a challenge, a digest, a path, an outcome | The driver takes **only** a verb (and `main` a state root, which the boundary proof must declare). Inbox names come from the definition and pass S3's name check; nothing names a run, ticket, challenge, digest, claim or status |
| **Malformed arguments, truthiness** | `invoke(True)`, `"RUN"`; a definition with a string for an int, an extra field, a duplicate key, a BOM | Exact `str` membership; the definition parses strictly (`extra="forbid"`, pydantic strict mode, duplicate keys refused, UTF-8 only) |
| **Recovery misclassification** | Treating an interrupted in-flight step as resumable; treating a planner ticket without a hold as decidable again | In-flight → `recover()` → RECOVERY_REQUIRED; an untrusted run → HUMAN_REQUIRED (`untrusted`); a planner ticket without a hold is left to DL-2, which refuses to ask again (HUMAN_REQUIRED) |
| **X-side work executed as A** | The driver importing or calling the frozen command bodies, Git, `subprocess` | No such import exists (static AST test and a subprocess-isolated `sys.modules` test); at run time a guard wraps both frozen command bodies and fails if either runs outside the simulated human X step |
| **COMPLETE without S6's signature** | `run` at ACCEPTANCE; DL-3 after a hold; a decision from the driver | The only completion path is `apply_step_transition(..., human_attestation=v2)` over the store's own held envelope. `run` at a held step is refused; DL-2 never applies an accept decision (S6) |
| **Announcement as a side channel** | The display callback altering what the adapters receive | The wrappers forward the exact keyword arguments DL-2 passed to the session's own adapters. An announcement is computed from the dispatch ticket only and is display |

## 3. Entry points and stages

| Verb | Allowed at | Calls |
|---|---|---|
| `status` | always | the derivation only (which runs `recover()` on a recorded run) |
| `request-approval` | `contract_approval`, `plan_activation`, `exact_diff_approval`, `acceptance` | `request_project_contract_approval`, `request_plan_activation`, `request_exact_diff_approval`, `request_step_acceptance` (+ `held_acceptance_bundle`) |
| `record-approval` | the same four | `record_approved_project_contract`, `issue_execution_plan`, `record_exact_diff_approval`, `apply_step_transition(DECIDE_ACCEPTANCE, human_attestation=…)` |
| `run` | `attempt`, `decision` | `issue_authorized_step_contract`, `create_project_run` / `create_step_run` only when absent, then `ProjectOuterLoop.run` |
| `decline-acceptance` | `acceptance` | `apply_step_transition(ESCALATE)` |

| Stage | Derived when | Outcome |
|---|---|---|
| `contract_approval` | no recorded contract | APPROVAL_REQUIRED |
| `plan_activation` | contract, no activated plan | APPROVAL_REQUIRED |
| `exact_diff_approval` | plan activated, no exact-diff approval | APPROVAL_REQUIRED |
| `attempt` | approval recorded and unspent; no run, or the step PLANNED/READY at attempt 0 | READY_TO_RUN |
| `decision` | step at ACCEPTANCE, no held decision | READY_TO_RUN |
| `acceptance` | step at ACCEPTANCE with a held decision | AWAITING_HUMAN_ACCEPTANCE |
| `complete` | step COMPLETE | COMPLETE |
| `human_required`, `failed` | step HUMAN_REQUIRED or FAILED, or the project not ACTIVE | HUMAN_REQUIRED |
| `recovery_required` | step RECOVERY_REQUIRED (also an in-flight step, which `recover()` makes impossible) | RECOVERY_REQUIRED |
| `untrusted` | `recover()` found integrity issues, or a spent approval no run explains | HUMAN_REQUIRED |

A refused verb reports `REFUSED` with a category; if the failure itself moved
the Alpha into an ended stage (an attempt that raised, a run escalated by
`recover()`), the outcome is that stage's and the refusal is kept.

**Presenting a challenge.** The driver re-derives each subject independently
and refuses to present a challenge (`subject_unconfirmed`) unless its digest
equals the challenge's: the contract content digest; the
`plan-activation-subject.v2` from the plan, policy, scope, the clone's
workspace identity and the boundary digest; the `exact-diff-approval-subject.v1`
from that activation subject and the SHA-256 of the inbox artifact read again
(so an inbox changed after the store read it is caught). For the step
acceptance the driver does not recompute the v2 subject (it binds digests of
the store's re-proven records); it confirms that the challenge names exactly
the subject of the bundle O reads in `published/`
(`subject_sha256_matches_published_bundle`). The report carries the `statement_template` with
O's three fields open.

## 4. Operator workflow

See the runbook. In short: O places the definition; A
`request-approval` → O signs with the helper and the security key → A
`record-approval`, three times; X runs P1B and O writes the H6 artifact; A
`run`, during which the human runs the two printed X commands in X's session;
A `request-approval` publishes the bundle; O accepts (sign, A
`record-approval`) or declines (A `decline-acceptance`).

## 5. Durable restart behavior

| Boundary (commit) | Next invocation | Then |
|---|---|---|
| step contract issued / project run created / step run created / marked READY | `attempt` | `run` creates only what is missing and attempts once |
| attempt begun / implementer ticket / write intent / implementation returned / verifier ticket / verification observed | `recovery_required` | every verb refuses; no handoff, claim read, model request or X step repeats |
| review observed | `decision` | `run` issues the planner ticket and holds; no X step repeats |
| planner ticket issued | `decision` | `run` ends HUMAN_REQUIRED (DL-2 never asks the planner twice) |
| hold persisted | `acceptance` | survives any number of restarts; `run` refuses |
| an approval consumed | the next stage | the approval is never requested again |
| completion (before its commit) | `acceptance` | the same signature completes, once |
| COMPLETE | `complete` | every verb but `status` refuses; nothing is applied twice |

## 6. Offline Alpha execution trace

From `test_the_complete_offline_alpha_reaches_complete_only_through_every_human_step`
(every row is a fresh session):

```text
status               APPROVAL_REQUIRED           contract_approval
request-approval     APPROVAL_REQUIRED           contract_approval
record-approval      APPROVAL_REQUIRED           plan_activation
request-approval     APPROVAL_REQUIRED           plan_activation
record-approval      APPROVAL_REQUIRED           exact_diff_approval
request-approval     APPROVAL_REQUIRED           exact_diff_approval
record-approval      READY_TO_RUN                attempt
run                  AWAITING_HUMAN_ACCEPTANCE   acceptance     (X: frozen write, then frozen review)
status               AWAITING_HUMAN_ACCEPTANCE   acceptance
status               AWAITING_HUMAN_ACCEPTANCE   acceptance
request-approval     AWAITING_HUMAN_ACCEPTANCE   acceptance     (bundle published, challenge issued)
record-approval      COMPLETE                    complete
status               COMPLETE                    complete
```

Exactly two frozen command bodies ran, both inside the simulated X step; one
model request; one planner ticket; the target holds the approved post-image.

## 7. Post-implementation review

The actual code was reviewed against §2 with supported-API counterexamples.

| Id | Finding | Material? | Resolution / regression |
|---|---|---|---|
| R7-1 | A second project run for the same activation would let the driver attach to either | Checked, sound | store.v4 already authorizes exactly one project run per activation (`create_project_run` refuses a second). A second run row written into the file makes the store's own inventory proof refuse every verb (`StateUntrustedError`); the driver's one-run rule is a further backstop. `test_a_second_project_run_can_be_neither_created_nor_adopted` |
| R7-2 | A changed definition after records exist (another contract or another step contract) | Yes | Every record must be the definition's; the step contract is re-derived and compared. `test_a_definition_that_does_not_describe_the_recorded_alpha_refuses_everything` |
| R7-3 | An inbox artifact changed between the store's read and the presentation would show O a digest that is not the subject | Yes (presentation) | The driver re-reads and re-derives the subject; mismatch refuses to present. `test_an_inbox_changed_after_the_diff_challenge_is_not_presented_for_signing` |
| R7-4 | `run` at a stage without the exact-diff approval would spend the attempt budget (BEGIN_ATTEMPT then a refused handoff) | Yes | `run` only at `attempt`, which requires a recorded, unspent approval. `test_run_without_the_exact_diff_approval_begins_no_attempt` |
| R7-5 | A boundary refusal raised while reading an inbox document must not be reported as a missing document | Yes (classification) | Only an exact `AuthorityRefusedError` is an unreadable document; subclasses propagate. Covered by the boundary and revocation tests |
| R7-6 | The announcement callback failing (e.g. a broken stdout) during `run` | No (fail closed) | The exception reaches DL-2 as a port failure → RECOVERY_REQUIRED before anything is handed off. An unannounced handoff must not proceed |
| R7-7 | A definition edited after activation (scope or policy) but describing the same plan digest | No | The store uses its own activated records; the driver's re-derived subjects then disagree and it refuses to present (fail closed). Residual: detected at the next presentation, not at `status` |
| R7-8 | `status` writes when `recover()` reduces an interrupted step | No (design) | DL-1 requires `recover()` before a fresh session reads a run; documented |
| R7-10 | A forged, genuine-shaped `approve` review packet with M2 holding reaches the hold | No (accepted D-2′) | It is indistinguishable from a real claim by construction (the reviewer runs in X with repository code, C-11). It completes nothing: the bundle labels it `execution_identity_unauthenticated`, `run` and an unsigned `record-approval` refuse, and the human may decline. `test_a_forged_review_packet_is_only_a_labeled_claim_and_completes_nothing_by_itself` |
| R7-9 | Unbounded challenge issuance by repeated `request-approval` | No | Challenges are single-use and expire after 60 minutes; none is consumable without a signature |
| R7-11 | `decline-acceptance` takes no signature, so whoever can run A can decline | No (fail-safe direction) | A decline can only end the step at HUMAN_REQUIRED; it can never complete anything, and A is the human-supervised authority identity. The prompt requires that the human can decline without signing |
| R7-12 | X copies an earlier ticket's claim (the write report) into the review outbox, so the attempt "reuses" a recorded execution claim | Checked, sound | Claims are per-ticket and kind-checked by S4's reader; the copy is not a review-command claim, so the attempt ends RECOVERY_REQUIRED with no planner ticket. `test_a_failed_or_indeterminate_execution_ends_in_recovery_and_never_runs_again[a previous ticket's claim reused]` |
| R7-13 | The step contract proposal comes from O's inbox definition, not from a signature at activation | No (accepted S2/DL-4A contract) | `issue_authorized_step_contract` takes every policy value from the activated plan, and `step-acceptance-subject.v2` binds `step_contract_sha256`, so the human signs the step contract that ran at acceptance. A definition changed after a step run exists refuses every verb (R7-2) |

## 8. Tests

`tests/test_dl4b_s7_alpha_driver.py`: the complete chain with the trace; the
restart matrix (13 attempt boundaries, 3 approval boundaries); stage
discipline and refused verbs with unchanged snapshots; cross-project and
cross-attempt definitions; a second project run (refused by the store, and
not adopted by the driver if forced into the file); malformed definitions and verbs; subject
re-derivation and the racing-inbox case; stale, missing, malformed,
wrong-kind, wrong-key, wrong-approver and replayed approvals; revocation;
a changed boundary; a config for another workspace; eight execution failures
(wrong claim owner, a write that is not the exact diff, missing claim, missing
marker, unparseable or empty verification claim, an earlier ticket's claim
reused, M2 mismatch); a forged review
packet that reaches only a labeled hold; a non-approve verdict; a claimed failed verification; repeated `run`;
missing and invalid acceptances; decline; completion exactly once; a crash
while completing; state the driver did not create; a tampered hold; the
operator helper against S1's independent statement builder; the production
entry points (no isolation; an unprovisioned host); static boundaries (AST and
subprocess-isolated imports, no private attribute of anything but the driver
itself, no `cli` reference).

## 9. Residuals

- **Proof cost.** Every invocation after the attempt re-derives the write,
  verification and review chains several times (S5/S6). Offline, a `status`
  at the hold takes about ten seconds; E-12 must measure it on the host.
- **The announcement reaches the human through A's stdout.** The runbook has
  the human redirect it into `published/` with `cmd.exe`. E-12 must confirm
  that A can create those files with the inherited protected DACL and that X
  cannot reach them.
- **The O helper is not the signer.** It prepares bytes; S1 rebuilds and
  verifies the statement. E-6 still has to sign a real statement with the
  real authenticator.
- **R7-7** as above; D-7, D-8, D-13, R-5 unchanged.

## 10. Remaining obligations

- **E-12** — the live isolation rehearsal (§5.8.10), plus S7's items: the
  per-invocation proof duration, the long `run` invocation with the exclusive
  store lock across the human's two X steps, and `cmd.exe` redirection of A's
  report into `published/`.
- **E-6** — one throwaway challenge, presented by the driver, signed with the
  real authenticator through `alpha_operator` and `ssh-keygen -Y sign`, and
  verified, in a throwaway state root.
- **AUTH-PILOT (E-1…E-13)** — naming the accounts and SIDs, the A launch
  (`python -I -m ai_dev_orchestrator.integration.alpha_driver`, task action or
  interactive session), the repository, clone, file, scope, config digest,
  verification argv, reviewer provider and credential arrangement, signing
  device, boundary digest and the FD-17/FD-18 constants.

## 11. Validation

Runs on this host (Windows 11, `.venv` interpreter, 2026-10-27):

| Run | Result |
|---|---|
| `tests/test_dl4b_s7_alpha_driver.py` | 81 passed (24 min 48 s) |
| the execution-failure matrix (with the R7-12 case added after that run) and the complete chain, `-s` for the trace | 9 passed (3 min) |
| full repository suite (`pytest -q`), including S0–S6 and DL-1/2/3/4A | 5681 passed, 1 pre-existing warning (1 h 42 min); collected before the R7-12 case was added |
