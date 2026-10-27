# DL-4B S5 — Review Evidence and REVIEW_OBSERVED

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `39a6d55390f855b5cc37868ffede80b4302d5e88` (S0–S4 accepted and frozen for offline scope) |
| Contract | `docs/DL4B_REAL_INTEGRATION_BOUNDARY_DESIGN.md` (AMEND1): FD-6, FD-8, FD-14–FD-18, §5.4, slice S5 (§11); `docs/DL4B_S4_VERIFICATION_CLAIM_ADAPTER.md` §11 |
| Kind | Offline implementation. No live Alpha, no account, no credential, no model, no Git, subprocess or network in A |
| Not authorized | S6 human acceptance, S7 driver, E-12, any live run, any change to the frozen review command or `CLAUDE.md` |

S5 answers DL-2's **reviewer** dispatch from the execution claim S4 already
recorded, and from nothing else. The frozen `l2-review-approved-file-edit`
command ran **once**, inside the verifier dispatch's handoff; its stored stdout
is the only source of the review proposal. S5 runs, waits for, observes,
publishes and sends nothing.

```text
reviewer ticket (store-issued at REVIEWING @ the version VERIFICATION_OBSERVED produced)
   │  ExecutionClaimAdapter.review(step_contract, attempt, dispatch) — the same adapter,
   │  the same session-minted claim key, no new execution surface
   ▼
_reviewer_chain (all from the store, never from the caller)
   ├─ the attempt's ONE answered verifier dispatch
   ├─ its VERIFICATION_OBSERVED: VERIFYING@v → REVIEWING@(this ticket's version), outcome `verified`
   ├─ verification_evidence_v2 re-derived NOW (write chain + H6 re-verified, handoff, claim, M1, M2)
   ├─ execution_claims: shape `review-packet`, digest = the evidence's claim digest
   └─ the blob re-hashed, re-classified (S4 reader), review re-read strictly (S5 reader) → verdict
   ▼
ONE transaction: review_evidence(reviewer ticket, verifier ticket UNIQUE, claim digest, verdict,
                                  provenance = execution_claim)                    ── COMMIT ──
   ▼
ReviewProposal(verdict = re-derived, evidence_sha256 = the S4 claim digest), bound to the ticket
   ▼
REVIEW_OBSERVED — accepted only for that reviewer ticket, re-deriving everything above,
                  with the payload equal to the re-derived proposal → ACCEPTANCE (DL-1)
```

The verdict is model output, advisory by contract, **and** an execution claim
(FD-15, D-2′). It never becomes an independently verified authority fact.

---

## 1. Modules

| Module | Kind | Content |
|---|---|---|
| `integration/claim_readers.py` | changed, pure | `read_review_verdict` (strict re-derivation of the packet's review), `ReviewVerdictFacts`, the restated `ModelReviewResult` / `ReviewFinding` rules (pinned by test). `read_review_claim` is **unchanged** |
| `integration/integration_store.py` | changed | `_reviewer_chain`, `_reviewer_state`, the capability-gated `_perform_review_observation`, `_review_evidence_issue`; `REVIEW_OBSERVED` acceptance; step and row proofs for review evidence; `review_evidence.verifier_ticket_id` UNIQUE; `ReviewEvidenceRefusedError`; `S5_TABLES`; `UNWRITTEN_TABLES` now empty |
| `integration/execution_claim.py` | changed | `ExecutionClaimAdapter.review` (DL-2's `BoundReviewerPort`) and the recorder's `observe_review`; same adapter, same key |
| `integration/integration_session.py` | changed | `reviewer` property: the **same** `ExecutionClaimAdapter` as `verifier` (no second recorder) |
| `tests/test_dl4b_s5_review_evidence.py` | new | §9 |
| `tests/test_dl4b_s2_integration_store.py` | changed, one line | the session's public set lists `reviewer` |
| `tests/test_dl4b_s4_verification_claim.py` | changed, three lines | the adapter's public set is `{verify, review}`; two comments in the stub-reviewer DL-3 test no longer say "S5 does not exist". No assertion weakened |

No S0–S4 semantics changed. S4's classifier, review handoff, M2, evidence
binding and `VERIFICATION_OBSERVED` acceptance are untouched.

## 2. Pre-implementation adversarial analysis

| Object | Created / mutated by | Authority | Provenance A requires | Mutability | Re-check |
|---|---|---|---|---|---|
| Reviewer ticket | Store (DL-4A `issue_dispatch_ticket`), only at REVIEWING | Persisted row; one per `(step, version, role)` | Row equality; role `reviewer`; unanswered; step REVIEWING at its version and attempt; project ACTIVE; **its version is the `to_version` of the attempt's verified `VERIFICATION_OBSERVED`** | Consumed once by `REVIEW_OBSERVED` | Recording; consumption; every proof |
| Verifier transition | DL-1/DL-4A, through S4's acceptance | Persisted transition consuming the verifier ticket | Exactly one answered verifier ticket for `(step, attempt)`; its transition VERIFYING@ticket version → REVIEWING@reviewer version, outcome `verified`; same run and contract | Immutable row | Every derivation |
| S4 claim and M2 | S4 | Receipt (claim) + A's observation (M2) | `verification_evidence_v2` re-derives (`_verification_evidence_issue`: H6 re-verified against the current registry, completed intent, M0, M1, handoff, claim bytes re-classified, M2 vs M1, every column); claim row shape `review-packet`, digest = evidence's | Write-once rows; content-addressed blob | Every derivation |
| Review proposal | **Derived**, never received | None of its own | Built only by `_reviewer_chain` from the re-read bytes; `evidence_sha256` = claim digest; verdict read again on every check | Not stored as a document | Equality with the re-derived proposal at consumption |
| `review_evidence` | Store, in one transaction, via the claim key | Derived; provenance `execution_claim` | Reviewer ticket (PK), verifier ticket (**UNIQUE**), claim digest (reference, not a copy), verdict | Write-once | Every column re-derived on every proof |
| `REVIEW_OBSERVED` | DL-1 through `apply_step_transition` | Consumes the reviewer ticket | DL-4A binding + `_review_evidence_issue(ticket, payload)` | Immutable transition | Every step proof (incl. the transition's recorded verdict) |

Bypass routes considered before coding, and the rule that closes each:

- *Caller-supplied `ReviewProposal`, verdict or digest* (store API, forged
  envelope, a "correct" proposal): consumption requires the `review_evidence`
  row of exactly that ticket **and** payload equality with the proposal
  re-derived from the bytes. A right proposal before the adapter recorded
  anything is refused.
- *Driving `_perform_review_observation` directly*: requires S4's claim key,
  minted only into the session's adapter; S3's write key and a fresh key are
  refused.
- *Mismatched objects*: a verifier, implementer or planner ticket; a reviewer
  ticket of another step, run, attempt, contract or version; a ticket AIDO did
  not issue — all refused by row equality and the chain's version rule.
- *Reviewing before or without a verified verification*: no reviewer ticket
  can be issued outside REVIEWING; a forged reviewer ticket names no issued
  row; a claimed `verification-failed` goes to ACCEPTANCE and never REVIEWING.
- *A bare report, or another packet*: the claim must be the evidence's
  `review-packet`, re-hashed under its content-addressed name; a different
  packet cannot share the digest.
- *Re-running the review*: S5 has no handoff, wait, claim read, observation
  or publication call (static test); the review command and reviewer
  transport are armed to fail during S5 in tests.
- *Recording twice*: `review_evidence` PK on the reviewer ticket and UNIQUE
  on the verifier ticket; the state check refuses a second recording.

## 3. Review proposal derivation and verdict binding

`claim_readers.read_review_verdict(bytes)`:

1. `read_review_claim(bytes)` — S4's classifier, unchanged. Shape must be
   `review-packet` (`review-packet.v5`, embedded verification `verified` and
   consistent with the packet's target, approval and identity); a bare report
   is refused (`unexpected_shape`).
2. The packet's `review` must be exactly a shipped `ModelReviewResult`:
   exact field set; closed verdict, severity and category vocabularies;
   `summary`, `message`, `suggested_action` and note entries non-blank and
   within their shipped length bounds; `findings` ≤ 20, each finding exactly
   its shipped fields (`line` optional, `null`, or a positive JSON integer —
   never a string, float or boolean); `residual_risks` and `human_notes` ≤ 20.
3. The verdict must be one its own findings support (`changes_requested`
   names a `blocker`/`major`; `approve` names none) — the shipped consistency
   rule, `verdict_unsupported` otherwise.

Nothing is normalized, repaired, coerced or reinterpreted: the reader only
accepts or refuses. A test pins every restated constant to `review.models`,
and for every refused mutation also shows the shipped strict parser refuses
it (and for every accepted variation, that it accepts it).

The proposal is `ReviewProposal(step_contract_sha256 = the ticket's,
attempt = the ticket's, verdict = the re-derived verdict, evidence_sha256 =
the S4 claim digest)`. The `review_evidence.verdict` column is never trusted:
it is compared with a fresh re-derivation on every check.

## 4. How the same S4 claim is reused

- **Located by the store.** The reviewer adapter is handed only the ticket.
  The store finds the attempt's single consumed verifier ticket and reads its
  `verification_evidence_v2` and `execution_claims` rows; no path, digest or
  packet comes from a caller.
- **Same bytes.** `review_evidence.claim_sha256` must equal the verification
  evidence's `claim_sha256` and the claim row's, and the blob must re-hash to
  it. `ReviewProposal.evidence_sha256` is that digest, which is also the
  `VerificationObservation.evidence_sha256` S4 recorded (S4 C4-2).
- **Same verification portion.** The packet's embedded verification is
  re-classified from those same bytes; S4's evidence (and M2) must re-prove.
- **Reference, not copy.** No blob is written by S5.

## 5. REVIEW_OBSERVED

DL-4A's checks run unchanged (bound envelope, role, payload equality, run /
step / contract / attempt binding, unanswered issued ticket, freshness), then
`_review_evidence_issue(ticket, request.review)` re-derives the chain and
requires the payload to equal the re-derived proposal. DL-1 then moves
REVIEWING → ACCEPTANCE for every verdict and records it (`approve`,
`changes_requested` and `needs_human_review` alike — the frozen contract).
The step proof does the same for every recorded `REVIEW_OBSERVED`, including
the transition's recorded verdict. `_unexplained_issues` now explains an
answered reviewer ticket only by its `REVIEW_OBSERVED`; an answered planner
ticket remains unexplained (S6).

## 6. Failure matrix

| Point | Durable result | Step | Can the review be recorded again? |
|---|---|---|---|
| Any refusal (ticket, chain, revocation, S4 evidence, unaccepted review) | nothing | REVIEWING → DL-2 RECOVERY_REQUIRED | no: one reviewer ticket per version |
| Crash in the review-evidence transaction | rolled back | RECOVERY_REQUIRED after `recover()` | no |
| Evidence committed, crash before `REVIEW_OBSERVED` | `review_evidence`, ticket unanswered, re-proven | RECOVERY_REQUIRED after `recover()` | no |
| `REVIEW_OBSERVED` recorded | ACCEPTANCE with the verdict | — | — |

Nothing is retried, and nothing in S5 can cause the review command or a
model to run.

## 7. Post-implementation adversarial review

See §9 for the regressions. Findings:

| Id | Finding | Material? | Resolution |
|---|---|---|---|
| R5-1 | S4's classifier checks only the review's field set and verdict vocabulary. A packet whose review the frozen command could never print (e.g. `approve` with a blocker, a string `line`) binds at S4 and reaches REVIEWING | Yes, for S5: such a verdict is not one "re-derived" under the frozen contract | S5's strict reader refuses it; nothing is recorded; DL-2 → RECOVERY_REQUIRED. S4's classifier is left unchanged (S4 semantics preserved). `test_a_recorded_packet_whose_review_the_command_never_prints_answers_no_reviewer` |
| R5-2 | The S2 schema let one verification back two review rows (`verifier_ticket_id` not unique) | Yes (defense in depth; the state check already refused it) | `UNIQUE (verifier_ticket_id)`. `test_review_evidence_binds_exactly_one_verification` |
| R5-3 | A forged, coherent `approve` printed by X while the model really asked for changes | **Residual D-2′**, by design (C-11) | Recorded with provenance `execution_claim`, reaches ACCEPTANCE only; S6's signed human acceptance remains required (FD-8a). `test_a_forged_but_coherent_review_is_recorded_only_as_an_execution_claim` |
| R5-4 | Supported-call attacks: proposal with forged verdict, correct verdict with another digest (incl. the M2 manifest's), correct proposal bound to the verifier ticket or an unissued ticket, no role output, a verification observation in its place | Checked, sound | `test_no_caller_supplied_proposal_verdict_or_digest_passes_reviewing` |
| R5-5 | Approver revocation after S4 (before, and after, review evidence) | Checked, sound | `test_revoking_the_approver_after_s4_records_no_review`, `…after_the_review_evidence_refuses_review_observed` |
| R5-6 | S4 evidence deleted or altered between `review_evidence` and `REVIEW_OBSERVED` (rows, M2, claim blob altered or deleted) | Checked, sound | `test_s4_evidence_lost_between_review_evidence_and_review_observed_is_never_consumed` (×7) |
| R5-7 | A different packet written under the S4 claim's digest name | Checked, sound (content addressing) | `test_a_replacement_packet_under_the_same_digest_name_is_refused` |
| R5-8 | Tampering the cached `step_runs.review_verdict`. DL-1's frozen `recover()` detects it (`integrity_ok = False`, "not explained by its log") and escalates the run to HUMAN_REQUIRED, but its integrity-escalation transition copies the step row's facts, so afterwards the step reads (as HUMAN_REQUIRED) with the tampered cached verdict | Detected and fail-closed; **not changed** (frozen DL-1 recovery, pre-existing for `verification_outcome` too) | `review_evidence` and the `REVIEW_OBSERVED` transition still re-derive the claim's verdict. S6 obligation: take the verdict from those, never from `step_runs`. `test_a_tampered_step_run_verdict_is_detected_and_escalated` |
| R5-9 | Test-side: a forged ticket naming an unknown step run is refused as `RecordNotFoundError` (a `StoreError`) before any authority check | Not a defect (fails closed, nothing recorded) | The test accepts `StoreError` and asserts the store is unchanged |

## 8. Contradictions and tensions

- **C5-1 (choice).** §5.4 says the verdict "must equal the verdict re-derived
  from the packet bytes". S4's reader extracts a vocabulary-checked verdict;
  S5 re-derives it under the full shipped `ModelReviewResult` rules. Tightening
  S4's classifier instead would have changed which claims S4 records, so the
  stricter rule lives at the S5 boundary (R5-1).
- **C5-2 (narrow schema change).** `review_evidence.verifier_ticket_id` is
  `UNIQUE`. The S2-fixed column set is otherwise unchanged; no v4 store exists
  outside tests (same shape as S4's C4-3).
- **C5-3 (fact).** `review_evidence` carries no step-run or attempt column (S2
  fixed it); both are re-derived from the reviewer ticket and must match the
  verifier ticket's.
- **C5-4 (S6 obligation, not a contradiction).** DL-4A's
  `_attempt_evidence_sha256` / `_step_acceptance_subject` read v3's
  `verification_evidence` table; store.v4 refuses `request_step_acceptance`
  outright today. S6's `step-acceptance-subject.v2` must bind the S4 claim
  digest, M0/M1/M2 and the review evidence instead.

No frozen DL-1/2/3/4A, S0–S4, 5F2D or 5F2E contract or `CLAUDE.md` was
changed. The review command's options and injection points are untouched
(S4's pin still passes).

## 9. Tests

`tests/test_dl4b_s5_review_evidence.py`: 33 functions, 104 cases. Claims are
produced by the frozen review command itself, run once per scenario in the S4
harness; no socket, model, endpoint or credential is involved.

| Required case | Tests |
|---|---|
| 1 Reviewer ticket for another step or attempt | `…reviewer_ticket_for_another_step_attempt_or_role_is_refused` (×9), `…adapter_checks_contract_and_attempt…` |
| 2 Reviewer dispatch before a verified S4 transition | `…no_reviewer_dispatch_exists_before_a_verified_verification_transition`, `…failed_verification_never_reaches_a_reviewer` |
| 3 Bare verification report instead of a packet | `…bare_verification_report_carries_no_review`; tamper `claim shape` |
| 4 Forged reviewer verdict | `…no_caller_supplied_proposal…`, `…recorded_packet_whose_review_the_command_never_prints…` (×5), `…forged_but_coherent_review…`, DL-3 forged reviewer |
| 5 Correct verdict, another claim digest | `…no_caller_supplied_proposal…` |
| 6 Correct digest, another packet or ticket | `…no_caller_supplied_proposal…`, `…replacement_packet_under_the_same_digest_name…` |
| 7 Deleted or altered S4 verification evidence | `…s4_evidence_lost…` (×7); tampers |
| 8 Deleted or altered review evidence | `…tampered_s5_record…` (×19), `…tampered_step_run_verdict_is_detected_and_escalated` |
| 9 Approver revocation after S4 | `…revoking_the_approver_after_s4…`, `…after_the_review_evidence…` |
| 10 Duplicate dispatch, repeated consumption | `…review_is_recorded_once_and_consumed_once`, `…binds_exactly_one_verification` |
| 11 Crash before and after persistence | `…crash_while_recording_review_evidence…` (×2), `…crash_after_the_review_evidence_commit…`, `…reopened_store_re_proves…` |
| 12 Direct store transition without valid evidence | `…no_caller_supplied_proposal…`, `…only_the_session_minted_claim_recorder…` |
| 13 DL-3 → DL-2 | `…orchestration_path_records_the_review_from_the_s4_claim`, `…with_a_forged_reviewer_reaches_no_trusted_state` |
| 14 No second model or review-command run | `NoSecondRun` guard in the happy path, duplicate and crash tests (mocked reviewer request count, waiter sleeps, exchange directories, claim blobs; the command, transport and env reader armed to fail); `…s5_code_has_no_execution…surface` (static) |
| Reader strictness | `…review_mirror_restates_the_shipped_review_model`, `…re_derives_every_frozen_verdict` (×3), `…never_prints_is_refused_never_repaired` (×29), `…shipped_model_accepts_is_accepted` (×3) |
| Happy path per verdict | `…answered_from_the_s4_claim_and_reaches_acceptance` (×3), `…references_the_s4_blob_and_copies_nothing` |

## 10. Validation

Run on Windows with the project venv on 2026-10-26, on top of `39a6d55`.

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_dl4b_s5_review_evidence.py -q -p no:cacheprovider` (in subsets during development) | **104 passed** in the full run below. The first store-path subset showed three test-side failures (R5-8, R5-9 and a static check that flagged the pre-existing `issue_authorized_step_contract(proposal)` parameter); no production change was needed for them |
| S0–S4 files (`test_dl4b_s0…s4…`: 425 + 240 + 154 + 147 + 115 cases) | **1081 passed** in the full run below (S2 and S4 changed only as §1 states) |
| DL-1/2/3/4A files (`test_control_plane_dl1…dl4a`: 90 + 94 + 93 + 162 cases) | **439 passed** in the full run below (unchanged) |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (`testpaths = ["tests"]`) | **5540 passed**, 0 failed, 1 warning, 2833 s. 5540 = S4's 5436 + S5's 104. The warning is the existing, unrelated Pydantic serializer warning from `tests/test_supervised_implementer.py::test_a_post_load_forged_block_is_refused_by_revalidation` |

## 11. Remaining obligations

- **S6** — the planner hold and `step-acceptance-subject.v2`, binding the S4
  claim digest, M0/M1/M2 digests and the `review_evidence` verdict, labeling
  the claimed verification outcome and verdict as execution claims; replace
  DL-4A's v3 `_attempt_evidence_sha256` path (C5-4); the answered planner
  ticket and held envelopes become explainable. The verdict an acceptance
  binds comes from `review_evidence` and the `REVIEW_OBSERVED` transition
  (re-derived from the claim), never from the cached `step_runs.review_verdict`
  (R5-8).
- **S7** — driver and runbook (S4 §11 items), plus the proof cost: every proof
  now re-derives the write chain three times (write, verification, review).
- **E-12** unchanged from S4.

**Final status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**
