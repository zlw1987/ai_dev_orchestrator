# DL-4B S6 — Human Acceptance Authority and Durable Hold

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `76d00d7525d40739cade77bb07946853a4a3b99c` (S0–S5 accepted and frozen for offline scope) |
| Contract | `docs/DL4B_REAL_INTEGRATION_BOUNDARY_DESIGN.md` (AMEND1): §5.3, FD-7, FD-8, FD-8a, §5.4, §8, slice S6 (§11); `docs/DL4B_S5_REVIEW_EVIDENCE.md` §8 (C5-4) and R5-8 |
| Kind | Offline implementation. No live Alpha, no E-12, no account, no credential, no model, no Git, subprocess, network or repository code in A |
| Not authorized | S7 driver, E-12, any live run, any change to `CLAUDE.md` or to a frozen harness |

S6 makes one rule mechanical: **only a valid, current human attestation over
the exact `step-acceptance-subject.v2` completes a step in store.v4.** No
execution claim, model verdict, cached step field, planner recommendation or
matching digest can do it alone.

```text
ACCEPTANCE @ v  (entered by REVIEW_OBSERVED, or by a claimed failed verification)
   │ DL-2: held_acceptance_decision(step, v)? ── yes ──► AWAITING_HUMAN_ACCEPTANCE (no ticket, no planner)
   │ no
   ▼
planner ticket (DL-4A, one per version) → AlphaPlannerRule → the store's own derivation:
   facts = the attempt's ONE write (M0, M1), ONE verification (M2, claimed outcome), ONE review
           (claimed verdict), each re-derived from stored rows and blobs — never step_runs
   RECOMMEND_STEP_ACCEPT iff all proven ∧ outcome 'verified' ∧ verdict 'approve'; else HUMAN_REQUIRED
   ▼
DECIDE_ACCEPTANCE (no acceptance)          the store accepts ONLY the rule's exact decision
   ├─ HUMAN_REQUIRED decision → validator applies it → HUMAN_REQUIRED (ticket consumed)
   └─ accept decision → validator refuses HUMAN_ACCEPTANCE_MISSING (nothing written)
        ▼
      hold_acceptance_decision — ONE transaction: re-prove step @ v; DL-4A ticket + envelope checks;
        decision == rule; unchanged validator dry run == exactly HUMAN_ACCEPTANCE_MISSING;
        canonical envelope + digest + held_at on the ticket. No transition; version unchanged
        ▼
      AWAITING_HUMAN_ACCEPTANCE   (survives crash and restart: ACCEPTANCE is not in flight)

fresh session:
   publish_acceptance_bundle → published/  (A writes once; O reads; X has nothing — FD-14, S0)
   request_step_acceptance   → bundle (re)verified, then challenge(step_acceptance, subject v2)
   human signs (SSHSIG, S1)
   apply_step_transition(DECIDE_ACCEPTANCE + HumanStepAcceptance, role_output = held envelope,
                         human_attestation = v2)
     read txn: hold re-proven; presented envelope == held (canonical bytes); decision == held;
               acceptance == attested approver and time exactly; challenge open for subject v2
     published bundle re-verified byte for byte
     S1 verify_for_consumption OUTSIDE any transaction (FD-5)
     write txn: all of the above again → unchanged validator → COMPLETE only; held ticket and
                challenge consumed in the SAME transaction
decline: ESCALATE → HUMAN_REQUIRED (unchanged DL-1; no attestation); the held ticket goes stale
```

---

## 1. Modules

| Module | Kind | Content |
|---|---|---|
| `control_plane/integration_records.py` | changed, pure | `StepAcceptanceSubjectV2` (`step-acceptance-subject.v2`), `CLAIM_PROVENANCE_UNAUTHENTICATED`, `evidence_record_sha256`, `envelope_bytes`, `ALPHA_PLANNER_RATIONALE`, `alpha_planner_decision` |
| `control_plane/inner_loop.py` | changed | `InnerLoopStop.AWAITING_HUMAN_ACCEPTANCE` and cause `awaiting_human_acceptance` (additive); the FD-7 branch of `_decide`, taken only when `store.holds_acceptance_decisions` |
| `control_plane/store.py` | changed, additive | `ControlPlaneStore.holds_acceptance_decisions` → `False`. Nothing else |
| `integration/integration_store.py` | changed | the Alpha rule's derivation, `hold_acceptance_decision`, `held_acceptance_decision`, `held_acceptance_bundle`, `publish_acceptance_bundle`, `request_step_acceptance` (v2), the signed completion path, planner-decision authorization, S6 proofs; DL-4A's v3 subject helpers refuse explicitly |
| `integration/alpha_planner.py` | new | `AlphaPlannerRule`, DL-2's planner port: no model, no recorder; asks the store for its derivation |
| `integration/acceptance_bundle.py` | new | the bundle's fixed texts and types, and publication into `published/` |
| `integration/integration_session.py` | changed | `planner` property: the session-minted `AlphaPlannerRule` |
| `integration/__init__.py` | changed, docstring | S6 paragraph |
| `tests/test_dl4b_s6_human_acceptance.py` | new | §9 |
| `tests/test_dl4b_s2_integration_store.py` | changed | the public-method classification moves `request_step_acceptance` from "always refused" to "re-proven" and adds the four new methods (each with a boundary-failure call); the session's public set lists `planner`. No assertion weakened: `test_refused_methods_stay_refused` still requires `request_step_acceptance` to refuse without a hold |
| `tests/test_dl4b_s3_write_handoff.py` | changed, harness | `TestFiles.published`: a file A creates in `published/` reports A as owner (as handoff files already did) |
| `tests/test_dl4b_s0_identity_boundary.py` | changed, one constant | the package's module set lists S6's two modules, as S1–S4 extended it |

No S0–S5 semantics changed. DL-3 is unchanged: a step DL-2 leaves at
ACCEPTANCE is already `STEP_NOT_SETTLED` without escalation.

## 2. Pre-implementation adversarial analysis

| Object / transition | Creator, mutators | Provenance | Supported-API bypass considered | Cross-object consistency | Consumption-boundary check | Malformed type / truthiness | Crash / partial write | Claim promoted to authority? | Filesystem substitution |
|---|---|---|---|---|---|---|---|---|---|
| **Planner decision** | `AlphaPlannerRule` (any caller can mint one: R-3) | none by origin; **by content**: the store re-derives the rule and accepts only byte-equal output | forged `RECOMMEND_STEP_ACCEPT` for a non-approved review; a decision bound to another ticket/step/attempt | decision ↔ the attempt's write, verification and review evidence | `_authorize_decision`, `hold_acceptance_decision`, every proof (`_decision_transition_issue`) | exact `BoundRoleOutput`/`PlannerDecision` types, re-parsed | no write of its own | the outcome and verdict it reads are claims; it **recommends** only | none |
| **Rule inputs** | S3–S5 records | re-derived write, verification and review evidence; never `step_runs` (R5-8) | tampered cached verdict; transition verdict rewritten consistently with the row | transition outcome/verdict ↔ evidence row ↔ claim bytes | `_proven_alpha_facts` | — | — | no: any failure → `evidence_unproven` → HUMAN_REQUIRED | a replaced blob fails its content address |
| **Held decision** | `hold_acceptance_decision` only; nobody mutates it | the ticket's held columns, all-or-nothing (S2 CHECK) | a second planner ticket (UNIQUE), a different envelope, a hold of a decision the validator would apply, hold at a stale version | envelope ↔ ticket (ids, attempt, role) ↔ rule ↔ validator dry run | re-proven in every proof (`_s6_issues`) and every use (`_current_hold`) | canonical bytes and digest re-checked | one `UPDATE … WHERE consumed_request_id IS NULL AND held_envelope IS NULL` in the hold's transaction | no | none |
| **Acceptance subject v2** | the store, at `request_step_acceptance` | recomputed from re-proven records every time | caller-supplied digest; DL-4A's v3 subject path | each digest ↔ its record; envelope digest ↔ held envelope; boundary ↔ activation | at challenge issue, at completion (both transactions), at every proof | strict frozen model, fixed provenance literal | — | it **labels** claims (`claim_provenance`) | — |
| **Step-acceptance challenge** | `request_step_acceptance` | `approval_challenges_v2`, kind `step_acceptance` | a challenge for another subject or kind; an unconsumed forged row | subject ↔ a held decision's subject | `_open_challenge` (unconsumed, unexpired, window), proofs (`_s6_issues`) | — | consumed in the COMPLETE transaction | — | — |
| **Signed acceptance** | the human (SSHSIG, S1) | signature over the store's own statement | typed phrase, v1 attestation, other kind, other root, other key, replay | `HumanStepAcceptance` ↔ attested approver and time (exact JSON); presented envelope ↔ held | FD-5 order; FD-4 re-verification in every proof | exact `HumanAttestationV2` | ticket and challenge consumed with the COMPLETE transition, atomically | no | — |
| **Bundle** | the store, from re-proven records | content-addressed copies of write-once blobs | X or anyone replacing `published/` files; a file planted under the bundle's name | bundle ↔ subject digest ↔ blobs | re-verified before a challenge is issued and before completion | — | publication is outside the DB; re-runnable; never overwrites | separates `aido_observed` from `execution_claims` | exclusive create, then re-read: single link, own path, owner A, exact bytes; never read as authority |
| **ACCEPTANCE → COMPLETE** | the human, fresh session | as above | `apply_step_transition` without attestation; unbound base calls; `request_step_acceptance` unbound | — | `_apply_signed_acceptance`, then the unchanged validator | — | one transaction | no | — |
| **ACCEPTANCE → HUMAN_REQUIRED** (decline) | the human (`ESCALATE`) | DL-1 unchanged | escalation carrying an envelope or attestation | — | DL-4A FU1 | — | atomic | — | — |

## 3. The deterministic planner (`AlphaPlannerRule`)

The store derives, for the planner ticket's attempt and version:

1. the one transition that entered ACCEPTANCE at that version: a
   `VERIFICATION_OBSERVED` or a `REVIEW_OBSERVED`;
2. the attempt's one answered implementer dispatch, whose write evidence
   re-derives (approval re-verified, completed intent, M0/M1 as approved,
   write claim bound);
3. the one answered verifier dispatch, whose `verification_evidence_v2`
   re-derives (claim bytes, M2 against M1), and whose transition recorded the
   evidence's outcome;
4. when ACCEPTANCE came from a review: the one answered reviewer dispatch,
   whose `review_evidence` re-derives from the claim bytes, and whose
   transition recorded the evidence's verdict.

| Ground | When | Recommendation |
|---|---|---|
| `accept` | 1–4 hold, outcome `verified`, verdict `approve` | `RECOMMEND_STEP_ACCEPT` |
| `verification_not_verified` | proven, outcome not `verified` | `HUMAN_REQUIRED` |
| `review_not_approve` | proven, verdict `changes_requested` or `needs_human_review` | `HUMAN_REQUIRED` |
| `evidence_unproven` | anything in 1–4 fails | `HUMAN_REQUIRED` |

The decision's rationale is fixed AIDO text per ground; its `evidence_refs`
name the write, verification and review evidence record digests and the
M0/M1/M2 manifest digests. The rule reads no `step_runs` field and no
`step_run` handed to the port (R5-8). The store accepts a planner output only
when it equals this derivation byte for byte, so the rule's origin is never
what makes it authority (R-3 stands), and a `RECOMMEND_STEP_ACCEPT` never
completes anything without §6.

## 4. The durable hold (FD-7)

`hold_acceptance_decision(step_run_id, *, expected_state_version, role_output)`,
one transaction:

1. re-prove the step (the full store.v4 proof), the project ACTIVE, the step at
   ACCEPTANCE at exactly `expected_state_version`;
2. DL-4A's ticket checks on the envelope (unanswered planner ticket for this
   step, version, attempt, contract and run; payload = envelope output);
3. the decision equals the rule's derivation;
4. the **unchanged** DL-1 validator, as a dry run, must refuse with exactly
   `HUMAN_ACCEPTANCE_MISSING`; a decision it would apply is applied, never held,
   and any other refusal refuses the hold;
5. store the canonical envelope bytes, their digest and `held_at` on the
   ticket. No transition; the version does not change.

An identical repeat is a receipt (`duplicate=True`); a different envelope for
a held ticket is refused. DL-2 asks `held_acceptance_decision` **before** it
requests a planner ticket, so a held version is never decided twice. A crash
before the hold commits leaves an issued, unheld ticket: the next DL-2 call
finds no hold, its ticket request is refused, and the step escalates to
HUMAN_REQUIRED — the decision is never silently regenerated. A crash after the
commit leaves the hold, which `recover()` does not touch (ACCEPTANCE is not in
flight) and which every proof re-derives.

## 5. `step-acceptance-subject.v2` and the bundle

| Field | Value (all recomputed from re-proven records) |
|---|---|
| `schema_version`, `kind` | `step-acceptance-subject.v2`, `step_acceptance` |
| `project_run_id`, `step_run_id`, `step_contract_sha256`, `attempt`, `state_version` | DL-4A's fields: the held ticket's |
| `verification_evidence_sha256` | DL-4A's field, v4 meaning (§8: evidence = claim + authority observation): the digest of the `verification_evidence_v2` record — verifier ticket, write intent, claim digest, M2 digest, claimed outcome |
| `write_scope_sha256` | the activated `write-scope.v1` |
| `write_evidence_sha256` | the write evidence record — implementer ticket, intent, scope, artifact, workspace identity, write claim digest, M0, M1 |
| `review_evidence_sha256` | the review evidence record — reviewer ticket, verifier ticket, claim digest, claimed verdict |
| `planner_envelope_sha256` | SHA-256 of the held envelope's canonical bytes |
| `identity_boundary_sha256` | the pinned boundary digest (= the activation's) |
| `m0/m1/m2_observation_sha256` | the three authority observation manifest digests |
| `claim_provenance` | fixed `execution_identity_unauthenticated` |

C5-4 is resolved by versioning, not by changing v3: DL-4A's
`_attempt_evidence_sha256` and `_step_acceptance_subject` stay as they were
for store.v3, and an integration store overrides both to refuse explicitly.
`request_step_acceptance` refuses without a current held decision.

**The bundle** (`held-acceptance-bundle.v1`, canonical JSON) carries the
acceptance subject and its digest, the step contract, the write scope, the
held envelope, and two sections that never mix:

- `aido_observed` — the approved change (path, pre/post-image, artifact and
  config digests, the verified exact-diff approval), M0/M1/M2 (manifest,
  target, HEAD, `.git` control digest, entries, time), M2's additions, the
  write intent, the recorded lifecycle (states and rules only), and the
  identity boundary and workspace identity digests;
- `execution_claims` — the write report and the review command's stdout (by
  digest, length, shape), the claimed verification outcome, the claimed
  verdict and finding count, with the fixed statement that repository code
  could have produced all of them and that M2 authenticates neither the
  verifier nor the reviewer.

`publish_acceptance_bundle` writes the bundle and a copy of every blob it
references into `published/` as `<kind>-<sha256>` and
`acceptance-bundle-<subject>.json`, each exclusively created and re-read
(single link, its own path, owner A, exact bytes). A file already there is
never replaced: different bytes refuse. `published/` is A-owned and protected,
O reads, X has no right (FD-14), and S0 re-proves that — including every
descendant's owner and rights — at every store call. Nothing in `published/`
is ever an authority input: A reads it only to verify what it wrote.

## 6. Signed completion and decline

`apply_step_transition(DECIDE_ACCEPTANCE, planner_decision = held output,
human_acceptance = HumanStepAcceptance, role_output = held envelope,
human_attestation = HumanAttestationV2)` is the only way to COMPLETE, under
FD-5 (the diagram above). The `HumanStepAcceptance` must equal, as canonical
JSON, the one built from the attestation's approver and time, so every
proof can rebuild the exact request and match the recorded `request_sha256`.
Every proof re-derives the hold, re-verifies the consumed attestation against
the current registry (FD-4; revocation is total) and rebuilds the request.

Every other route refuses: `DECIDE_ACCEPTANCE` with an acceptance but no
attestation; a held envelope without one; an attestation with no envelope; a
v1 attestation; base-class calls made unbound; any attestation on another
event (the S2 refusal, now naming S6).

**Decline** is DL-1's `ESCALATE` → HUMAN_REQUIRED, unchanged: no attestation,
and an escalation carrying the envelope or an attestation is refused (DL-4A
FU1). The held ticket stays unconsumed and stale; nothing can complete it, and
it still re-proves.

## 7. Post-implementation adversarial review

Findings from reviewing the actual code, each turned into a fix or a test:

| Id | Counterexample through a supported API | Result | Fix / test |
|---|---|---|---|
| R6-1 | The DL-2 hold branch was never taken: `IntegrationStore` did not report `holds_acceptance_decisions` | found while wiring DL-2; fixed before any test ran | property override; `test_the_orchestration_path_holds_restarts_…` |
| R6-2 | An unheld `RECOMMEND_STEP_ACCEPT` relies on FD-8a (every contract requires human acceptance) for the validator to refuse it; a contract without that requirement would reach COMPLETE unsigned (proofs would flag it afterwards, not before) | defense in depth added | `_authorize_decision` refuses any decision for a contract that does not require human acceptance |
| R6-3 | A signed request whose `approved_at` names the same instant in another UTC offset passes DL-1's equality but changes `request_sha256`, so a proof could not rebuild it | refused at completion | exact-JSON equality with the attestation-built acceptance; `test_mismatched_or_replayed_…` |
| R6-4 | A forged accept decision for a `changes_requested` review, bound to the genuine planner ticket | refused at apply and at hold | `test_a_forged_planner_decision_is_neither_applied_nor_held` |
| R6-5 | Cached verdict rewritten to `approve` (row only, and row + transition) | untrusted; the rule still reads `review_not_approve`; recovery escalates | `test_a_tampered_cached_verdict_never_becomes_a_favorable_decision` |
| R6-6 | A published file altered, deleted, or planted before publication | completion and challenge refused; deletion is republished from the store, never adopted | `test_a_tampered_published_bundle_…`, `test_a_file_planted_under_the_bundle_name_…` |
| R6-7 | Replay of a completed acceptance with another envelope or a second, unconsumed attestation | refused; the identical replay is a receipt | `test_a_signed_acceptance_completes_the_held_step_exactly_once`, `test_mismatched_or_replayed_…` |

Residuals, stated rather than closed: D-2′ (the outcome and verdict are
execution claims; S6 labels them and never lets them complete a step); D-13
(the working tree can change after M2: the subject binds M2 as observed); R-3
(planner origin unauthenticated; mitigated by content equality and the
signature over the envelope digest); D-7 (restoring an older state root).

## 8. Contradictions and tensions

No frozen contract was changed. Notes:

- **C6-1 (interpretation).** §5.3 lists DL-4A's subject fields; DL-4A's
  `verification_evidence_sha256` named the v3 evidence bytes. In v2 it names
  the `verification_evidence_v2` record, under §8's v4 meaning of "evidence".
  The claim digest itself is inside that record.
- **C6-2 (tightening, within FD-8).** §5.4 lets a store holder answer a
  planner ticket (R-3). S6 accepts only the rule's exact decision, so a
  store-held planner cannot steer even toward HUMAN_REQUIRED-vs-FAILED.
- **C6-3 (addition).** The bundle's published copies of the referenced blobs
  are an S6 choice so O can review what A shows without access to the state
  root. They are content-addressed, A-owned and never read back as authority.
- **C6-4 (addition).** `ControlPlaneStore.holds_acceptance_decisions` (always
  `False`) is the one line added to `store.py`, so DL-2 can tell store.v4
  apart without importing the integration package.

## 9. Tests

`tests/test_dl4b_s6_human_acceptance.py` (§10 gives the counts).

| Required case | Tests |
|---|---|
| 1 Missing S4 or S5 evidence | `…without_s4_and_s5_evidence` (×3), `…anything_short_of_verified_and_approve…[verification_failed]` |
| 2 Forged or tampered cached verdict | `…forged_planner_decision…`, `…tampered_cached_verdict…` (×2) |
| 3 Verified but verdict ≠ approve | `…anything_short_of_verified_and_approve…` (×2) |
| 4 Correct verdict, changed M0/M1/M2 | tamper matrix: `m2 target`, `m1 deleted`, `m0 manifest blob` |
| 5 Envelope of another step/attempt/ticket/version | `…envelope_for_another_ticket_step_or_run…` (×5), `…stale_version_or_attempt…` |
| 6 DECIDE_ACCEPTANCE without a hold | `…without_a_held_decision_completes_nothing` |
| 7 Hold without the exact refusal | `…anything_short_of_verified_and_approve…` ("applied, never held") |
| 8 Duplicate hold | `…repeated_hold_is_a_receipt…` |
| 9 Restart, no second planner dispatch | `…survives_restart_and_the_planner_is_never_asked_again` |
| 10 Crash before / after hold persistence | `…crash_around_the_hold…` (×2), `…crash_while_completing…` |
| 11 Challenge for another subject | `…another_subject_kind_or_root…` |
| 12 Valid signature, stale or other envelope | `…another_or_stale_envelope` |
| 13 Expired, revoked, replayed, mismatched | `…expired_challenge…`, `…mismatched_or_replayed…`, `…revoking_the_accepting_key…` |
| 14 Tampered bundle or published artifact | `…tampered_published_bundle…` (×3), `…file_planted…` |
| 15 Deleted or modified review evidence after hold | tamper matrix: `review evidence deleted`, `review verdict` |
| 16 Revocation after hold, before completion | `…revocation_after_the_hold…` |
| 17 Direct store/API bypass | `…no_api_completes_a_held_step…` (9 routes), tamper matrices |
| 18 Decline then completion | `…declined_hold_goes_stale…` |
| 19 Recovery with a tampered cached verdict | `…tampered_cached_verdict…` |
| 20 v2/v3 unchanged | `…v2_and_v3_stores_hold_nothing_and_keep_r9`; DL-1/2/3/4A suites unchanged |
| 21 DL-3 → DL-2 → planner → hold → restart → signed completion | `…orchestration_path_holds_restarts_and_completes…` |
| 22 No model, Git, subprocess, network or repository execution in A | `…no_model_git_subprocess…` (static), `NoSecondRun` in the rule and hold tests, reviewer request counts in the end-to-end test |

## 10. Validation

All runs used `.venv/Scripts/python.exe -m pytest -p no:cacheprovider` on the
baseline `76d00d7` plus this slice, on Windows, with no network and no model.

| Run | Result |
|---|---|
| `tests/test_dl4b_s6_human_acceptance.py` | 60 passed |
| `tests/test_dl4b_s0_identity_boundary.py` + `tests/test_dl4b_s1_*` | 665 passed |
| `tests/test_dl4b_s2_integration_store.py` | 154 passed |
| `tests/test_dl4b_s3_write_handoff.py` | 147 passed |
| `tests/test_dl4b_s4_*` | 115 passed |
| `tests/test_dl4b_s5_*` | 104 passed |
| `tests/test_control_plane_dl*` (DL-1, DL-2, DL-3, DL-4A) | 439 passed (count unchanged) |
| full suite (`-q -rA`) | **5600 passed**, 1 warning, 0 skipped, in 1:19:39 |

Notes:

- The single warning is pre-existing and unrelated: a Pydantic serializer
  warning from `tests/test_supervised_implementer.py::test_a_post_load_forged_block_is_refused_by_revalidation`,
  which deliberately forges a non-bool `enabled`.
- A first full run with `-v` stopped with a pytest `INTERNALERROR` after 1572
  passes. The cause is pre-existing:
  `tests/test_controlled_review_config.py::test_the_gate_reads_no_environment_variable`
  patches `os.environ.get`, and pytest's verbose terminal writer reads
  `PY_COLORS` through it. The `-q -rA` rerun above is the result of record.
- The first S2 run failed its static surface test because a local variable in
  `IntegrationStore._bundle` was named `write_bytes`, a forbidden name. It was
  renamed to `write_claim`. No test was changed to accommodate it.
- The first S6 run had one skip (an envelope the `BoundRoleOutput` type itself
  refuses) and one wrong expectation (a tampered cached verdict whose
  transition contradicts the evidence is grounded `evidence_unproven`, not
  `verification_not_verified`). The skip was replaced by asserting the type
  refusal and an unchanged store; the expectation was corrected per case.

## 11. Remaining obligations

- **S7** — the non-model driver over `open_integration_session`: run DL-3 to
  the hold, call `publish_acceptance_bundle`, present the challenge statement
  to the human, and submit the signed acceptance in a fresh invocation; the
  runbook for reading the bundle in O's session. Proof cost grows again: a
  held decision re-derives the write, verification and review chains in both
  the project and the step proof.
- **E-12** — the live isolation rehearsal must also show that X cannot write,
  delete or re-permission `published/` or anything in it, and that A's
  published files carry the inherited protected DACL.
- **E-6** — signing a real step-acceptance statement with the real
  authenticator.

**Final status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**
