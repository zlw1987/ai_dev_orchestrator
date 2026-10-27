# DL-4B S4 — Verification Claim Adapter and M2

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `b4e6eeb87985704a03c36b4efc98c879b52a93b5` (S0–S3 accepted and frozen for offline scope) |
| Contract | `docs/DL4B_REAL_INTEGRATION_BOUNDARY_DESIGN.md` (AMEND1): FD-6, FD-8, FD-14–FD-18, §§5.2, 5.4, 5.6, 5.8, 7, slice S4 (§11); `docs/DL4B_S3_EXACT_DIFF_WRITE_HANDOFF.md` §11 |
| Kind | Offline implementation. No live Alpha, no account, no credential, no model, no Git, subprocess or network in A |
| Not authorized | S5 review evidence and `REVIEW_OBSERVED`, S6 acceptance, S7 driver, any live run, any change to the frozen review command or `CLAUDE.md` |

S4 lets AIDO record **what the frozen `l2-review-approved-file-edit` command
claimed**, while establishing the workspace facts itself:

```text
verifier ticket (store-issued, VERIFYING @ the version IMPLEMENTATION_RETURNED produced)
   │ bound to the attempt's proven write: answered implementer ticket → completed
   │ write intent → write evidence (H6 re-verified, M0, M1) — all re-derived
   ▼
execution_handoffs row (the write intent's artifact + config digests)   ── COMMIT ──
   ▼
handoff-<verifier ticket> / outbox-<verifier ticket>  ──►  HUMAN runs the frozen 5F2E
   │                                                       command as X (it runs 5F2D
   │                                                       once, then ≤ 2 RS1 requests)
   ▼                                                       stdout + completion marker
FD-17 receipt (read once) ─► strict classification by the bytes alone ─► shape + claimed outcome
   ▼
M2 (A's own reads) vs M1: target = post-image, every M1 path unchanged, HEAD/.git unchanged
   ▼                       additions listed, never refused
ONE transaction: claim receipt + M2 row + verification_evidence_v2 (iff claim binds AND M2 holds)
   ▼
VerificationObservation(outcome = the claim's own, evidence_sha256 = claim digest)
   ▼
VERIFICATION_OBSERVED — accepted only for that ticket, re-deriving everything above
```

The verification outcome stays an **execution claim** (FD-15). It selects one
of DL-1's existing branches toward a human; it never proves that the
verification executable ran, or ran honestly. What AIDO relies on as fact is
M2 and its own records.

---

## 1. Modules

| Module | Kind | Content |
|---|---|---|
| `control_plane/integration_records.py` | changed, pure | `REVIEW_CLAIM_OUTCOMES`: shape → the one outcome it permits |
| `integration/claim_readers.py` | changed, pure | `read_review_claim` (strict classifier of the review command's stdout), `ReviewClaimFacts`, `MAX_REVIEW_CLAIM_BYTES`, the review-packet mirror constants; `ProjectConfigFacts` gains the two opt-ins |
| `integration/workspace_observation.py` | changed, pure function added | `classify_verification(m1, m2, …)` → `VerificationEffect(holds, additions, issues)` |
| `integration/execution_claim.py` | new | `ExecutionClaimAdapter` (DL-2's bound verifier port) and its private `_ClaimRecorder` |
| `integration/integration_store.py` | changed | the capability-gated review handoff, `verification_evidence_v2`, the S4 proofs, `VERIFICATION_OBSERVED` acceptance, `UNIQUE (write_intent_id)` |
| `integration/integration_session.py` | changed | mints a second, distinct recorder key into the adapter; exposes `verifier` |
| `tests/test_dl4b_s4_verification_claim.py` | new | §10 |
| `tests/test_dl4b_s2_integration_store.py`, `tests/test_dl4b_s0_identity_boundary.py` | changed, one line each | the session's public set lists `verifier`; the package module pin lists `execution_claim.py` |

No other S0–S3 behavior changed. S3's write-chain code is untouched; its proof
loop now hands rows of a **verifier** ticket to the S4 chain.

## 2. Pre-implementation adversarial analysis

| Object | Created / mutated by | Authority | Provenance A requires | Mutability | Lifecycle and re-check |
|---|---|---|---|---|---|
| Verifier ticket | Store (DL-4A `issue_dispatch_ticket`), only at VERIFYING | Persisted row; one per `(step, version, role)` | Row equality field by field; role `verifier`; unanswered; step VERIFYING at its version and attempt; **its version is the `to_version` of the attempt's `IMPLEMENTATION_RETURNED`** | Consumed once by `VERIFICATION_OBSERVED` | Every phase; every proof |
| Proven write (S3) | S3 chain | Re-verified exact-diff approval, completed intent, M0, M1, write claim | `_write_evidence_issue` of the attempt's one answered implementer ticket | Write-once rows / blobs | Every phase; every proof |
| Review handoff row and directories | Store, row committed **before** publication; directories created exclusively with code-constant DACLs | Row binds the artifact and config digests of the write intent | Inputs come only from the stored blobs behind the spent approval; no caller path, digest or JSON | Published once; a pre-existing directory is refused, never adopted | Before the claim read (outbox identity and DACL re-proven); every proof |
| Execution claim | X writes stdout; A reads it once | **Receipt only** | FD-17: exactly `stdout.json` + `complete`, owner X, one link, not a reparse point, read once denying write sharing, only while the ticket is unanswered at VERIFYING | Write-once blob; one per ticket (PK) | Re-parsed and re-classified on every proof |
| M2 | Store, through `AuthorityFiles` | A's own observation | No API accepts one; taken after the claim is received | Write-once manifest blob + row | Re-derived from its manifest and compared with M1 on every proof |
| `verification_evidence_v2` | Store, in the claim transaction, only if the claim binds and M2 holds | Derived; provenance `execution_claim` | Ticket, step, attempt, write intent (UNIQUE), scope, workspace identity, claim digest, M2, outcome | Write-once | Every column re-derived on every proof; a settled dispatch has evidence **iff** its claim binds and its M2 holds |

Bypass routes considered before coding, and the rule that closes each:

- *Caller-supplied observation or digest at VERIFYING*: `_evidence_issue` is
  overridden; DL-4A's consumption path now demands the v2 row for exactly
  that ticket and re-derives it. A made-up digest, a different outcome, or an
  envelope for another ticket refuses.
- *Driving a store phase directly*: every phase requires the session-minted
  claim key, distinct from S3's write key.
- *Re-running verification for the same write*: the handoff row is per
  ticket; one verifier ticket per version; `UNIQUE (write_intent_id)` on the
  evidence.
- *Reusing S3's outbox or claim*: the receiver reads only
  `outbox-<verifier ticket>`; a write-result claim fails classification.
- *A claim after the step left VERIFYING*: the state is re-proven after the
  wait and before the outbox is opened.
- *Swapping config or artifact for the review run*: the handoff publishes the
  stored blobs behind the spent approval; the config's workspace is re-proven
  by path and identity, and both opt-ins must be enabled.

## 3. Review handoff ordering

```text
1 HANDOFF  txn(read): ticket = stored row, verifier, unanswered, step VERIFYING @ version,
           project ACTIVE; the attempt's answered implementer ticket, its IMPLEMENTATION_RETURNED
           to_version = ticket version; write evidence re-proves; config enables both opt-ins;
           nothing handed off yet
           re-prove clone (path + identity) and config workspace (path + identity)
           txn(write): all of the above again; INSERT execution_handoffs        ── COMMIT ──
2 PUBLISH  exchange.publish_handoff (S3's, unchanged): handoff-<ticket> with the two stored
           files, outbox-<ticket>; txn(write): record identities + published_at
3 RECEIVE  wait (CLAIM_WAIT_SECONDS) for `complete`; re-prove boundary; txn(read): still
           unanswered at VERIFYING, nothing received; outbox identity + DACL re-proven;
           read_claim(…, MAX_REVIEW_CLAIM_BYTES = 16 MiB)
4 SETTLE   read_review_claim(bytes) — unclassifiable → raise, record nothing
           M2 = observe_workspace; classify_verification(M1, M2); bind the claim
           publish claim blob (+ M2 manifest)
           txn(write): INSERT execution_claims (shape); INSERT M2; INSERT
           verification_evidence_v2 iff no reason                           ── COMMIT ──
           evidence → VerificationObservation; otherwise raise (DL-2 → RECOVERY_REQUIRED)
```

A publication failure, a protocol deviation or the deadline raise
`VerificationClaimRefusedError` with nothing recorded beyond the handoff row
(design §5.2 step 4). Each phase re-proves the FD-16 boundary.

## 4. Claim shapes and failure classifications

Classification is by the stdout bytes alone; the exit code is never an input.

| Frozen exit | Stdout | Shape | Claimed outcome | Step after `VERIFICATION_OBSERVED` |
|---|---|---|---|---|
| 0 | `review-packet.v5` embedding `verification-result.v1` | `review-packet` | `verified` | REVIEWING (S5 answers from the same claim) |
| 2 | bare report | `verification-failed` | `verification-failed` | ACCEPTANCE |
| 3 | bare report | `workspace-untrusted` | `workspace-state-untrusted` | RECOVERY_REQUIRED |
| 1, 4 | nothing | — (FD-17 `empty`) | — | RECOVERY_REQUIRED (DL-2) |

`read_review_claim` refusal categories (never repaired): `empty`, `oversize`,
`malformed` (BOM, duplicate key, non-standard constant, not one object, a
missing or unknown field, a non-shipped constant or type), `unexpected_shape`
(another schema, or a bare `verified` report the command never prints),
`outcome_unsupported` (the stated outcome is not the one the report's own
`execution.passed` and postcondition facts support, DL-4A's rule),
`contradictory` (a packet whose embedded verification did not pass, or whose
target, approval or identity differ from the embedded report's).

Store-side binding (recorded claim, no evidence, raise): the claim's target is
not the scope's path; its `approved_by`/`approved_at` are not the attested
exact-diff approver and time; its identity tuple is not the artifact's; its
`post_image_bytes` is not M2's target size.

## 5. M2

| Rule | Source |
|---|---|
| Target = the approved post-image (`approved-diff` facts) | M2 manifest |
| Every M1 path present with the same size and SHA-256 | M1 manifest (from the write evidence) vs M2 |
| Detached HEAD and `.git` control digest equal to M1's | M2 vs M1 (M1 already equals M0, base HEAD and the activation) |
| Additions | listed (`VerificationEffect.additions`), recorded in the manifest, never refused |
| A reparse point, nested `.git`, top-level `.gitmodules`, an over-cap tree | M2 cannot be taken → claim recorded, no M2 row, no evidence |

M2 is required for every outcome, not only `verified` (design §7 lists "M2
fails → RECOVERY_REQUIRED" for VERIFYING generally).

## 6. `verification_evidence_v2` and VERIFYING consumption

The row binds: verifier ticket, step run, attempt, write intent (**UNIQUE**),
write-scope digest, workspace identity digest, claim digest, M2 observation,
the claimed outcome, and provenance `execution_claim`.
`_verification_evidence_issue` re-derives every column from the verifier
ticket, the proven write chain, the published handoff of the same approved
bytes, the stored claim bytes (re-classified), M1 and M2.

At `VERIFICATION_OBSERVED` DL-4A's checks run unchanged (bound envelope,
ticket, payload equality, freshness) and then the overridden `_evidence_issue`:
the observation's outcome must be the evidence's, its `evidence_sha256` the
claim digest, and the whole chain must re-derive. The step proof does the same
for every recorded `VERIFICATION_OBSERVED` transition, including the
transition's recorded outcome.

## 7. Failure matrix

| Point | Durable result | Step | Can it be handed off again? |
|---|---|---|---|
| Any refusal before the handoff commit | nothing | VERIFYING → DL-2/`recover()` RECOVERY_REQUIRED | no: one verifier ticket per version |
| Crash in the handoff transaction | rolled back | RECOVERY_REQUIRED after `recover()` | no |
| Crash after the handoff commit (publication, wait, read) | unpublished or published handoff row | RECOVERY_REQUIRED | no (row exists; directories never adopted) |
| Pre-existing / substituted directory, deadline, FD-17 deviation, empty stdout | handoff row only | RECOVERY_REQUIRED | no |
| Unclassifiable claim | handoff row only | RECOVERY_REQUIRED | no |
| Classified claim that does not bind, or M2 fails / cannot be taken | claim receipt (+ M2), no evidence | RECOVERY_REQUIRED | no |
| Crash in the settlement transaction | rolled back | RECOVERY_REQUIRED | no |
| Evidence committed, crash before `VERIFICATION_OBSERVED` | evidence, ticket unanswered | RECOVERY_REQUIRED | no |
| `VERIFICATION_OBSERVED` recorded | REVIEWING / ACCEPTANCE / RECOVERY_REQUIRED per the claimed outcome | — | — |

Nothing is retried, repaired, restored or cleaned, and the review command is
never run twice by anything in AIDO.

## 8. Post-implementation adversarial review

Attacks run through supported APIs (the adapter, the store's public methods,
DL-3 → DL-2, the frozen command in the X step), each kept as a regression.

| Id | Finding | Material? | Fix / regression |
|---|---|---|---|
| R4-1 | DL-4A's verifier consumption path calls `_evidence_issue`, which reads the v3 `verification_evidence` table; store.v4 has no such table, so a verifier role output would have failed with an SQLite error instead of a refusal once the S3 role refusal was lifted | Yes (correctness of the consumption boundary) | `_evidence_issue` overridden to require and re-derive `verification_evidence_v2`. `test_no_caller_supplied_observation_or_digest_passes_verifying` |
| R4-2 | S3's proof loop explained every handoff, claim and observation as a write's. Verifier rows would have untrusted every verified run; skipping them would have left them unexplained | Yes | Rows are routed by ticket role to the S4 chain; a role flip untrusts. Tamper matrix (`verifier ticket role`, `evidence moved to the implementer ticket`, `m2 kind`) |
| R4-3 | Deleting the evidence of a settled but not yet consumed verification looked like an ordinary refused one | Yes (silent loss of a record the human relies on) | Proof rule: a settled dispatch has evidence **iff** its claim binds and its M2 holds. `test_a_settled_but_unconsumed_verification_still_needs_its_evidence` |
| R4-4 | Reusing one proven write for a second verification | Checked; closed by construction plus schema | One verifier ticket per version, handoff per ticket, `UNIQUE (write_intent_id)`. `test_verification_evidence_binds_exactly_one_write_intent`, `…handed_off_once_and_never_runs_twice` |
| R4-5 | Write recorder, a fresh key, or a forged adapter driving any review phase; implementer port with a verifier ticket | Checked, sound | `test_only_the_session_minted_claim_recorder_can_hand_off_a_review` |
| R4-6 | Replaying the write claim, or a packet placed in the write outbox | Checked, sound | Write-result bytes fail classification; only `outbox-<verifier ticket>` is read. `test_an_unclassifiable_claim_records_nothing[the write claim replayed]`, `test_a_claim_in_the_write_outbox_is_never_read_for_verification` |
| R4-7 | A claim delivered after the step left VERIFYING | Checked, sound | Never opened. `test_a_claim_is_never_read_after_its_ticket_left_verifying` |
| R4-8 | Approver revoked between the write and the review handoff | Checked, sound | The chain re-verifies H6; nothing is handed off. `test_revoking_the_approver_after_the_write_hands_off_no_review` |
| R4-9 | A forged `verified` packet (taken from a genuine run elsewhere) while the real verification fails, with M2 holding | **Residual D-2′**, by design (C-11) | Recorded as an execution claim (`provenance = execution_claim`) and reaches REVIEWING only; the same forgery with a changed target is refused. `test_a_forged_success_claim_is_recorded_as_a_claim…`, `test_the_same_forged_success_with_a_changed_target_is_refused` |
| — | Test-side: Python text-mode writes CRLF on Windows, so an early "HEAD moved" case actually exercised a non-detached HEAD | Not a defect (M2 still failed closed) | Both cases are now separate: `HEAD moved` (binary write, detached) and `HEAD not detached` |

## 9. Contradictions and tensions

- **C4-1 (factual).** §5.2 says the extended mirror reader returns "the
  post-image digest"; the frozen `verification-result.v1` target block has
  `post_image_bytes` and no digest. A binds the size; M2 binds the digest.
  (Same shape as S3's C3-2.)
- **C4-2 (choice).** §5.2 step 7 builds the observation "from the receipt";
  `VerificationObservation.evidence_sha256` is the claim digest, so S5's
  `ReviewProposal.evidence_sha256 == claim digest` rule (§5.4) names the same
  bytes.
- **C4-3 (narrow schema change).** `verification_evidence_v2.write_intent_id`
  is `UNIQUE`: one verification per proven write. No v4 store exists outside
  tests.
- **C4-4 (choice within the design).** A classified claim that does not bind,
  or whose M2 fails, is still recorded as a receipt with its M2 (they are the
  human's inspection material). The design's "record nothing" applies to the
  deadline, protocol violations and empty or unclassifiable stdout, which S4
  follows.

No frozen DL-1/2/3/4A, S0, S1, S3, 5F2D or 5F2E contract or `CLAUDE.md` was
changed. The review command's options, injection points, model-call policy,
credential handling, retries, exit codes and stdout are untouched (pinned by
test).

## 10. Tests

`tests/test_dl4b_s4_verification_claim.py`: 40 functions, 115 cases. Claims
are produced by the frozen command itself (`run_controlled_review` behind
`httpx.MockTransport`; a synthetic verification script under `tmp_path`).

| Requirement | Tests |
|---|---|
| Every frozen stdout shape, classified by bytes alone | `…classifies_every_frozen_stdout_shape` (×4, agreeing with DL-4A's reader), `…exits_1_and_4_print_no_claim` (×2) |
| Strict parse; forged / contradictory claims refused | `…forged_or_contradictory_packet…` (×13), `…forged_bare_report…` (×4), `…not_one_strict_json_object…` (×7), `…review_mirror_restates_the_shipped_models` |
| Handoff from re-proven S3 records only; evidence binding | `…passing_review_claim_binds_m2_and_advances_to_reviewing`, `…config_without_both_opt_ins…` |
| Outcome branches | `…claimed_failed_verification…goes_to_acceptance`, `…claimed_untrusted_workspace…recovery_required…`, `…ignored_addition_is_recorded…` |
| M2 (target, unrelated files, `.git`, HEAD, additions) | `…m2_classification_is_a_pure_function…`, `…verified_claim_with_a_failing_m2…` (×9) |
| Forged success, non-binding claims, unclassifiable claims | `…forged_success_claim…`, `…same_forged_success_with_a_changed_target…`, `…consistent_claim_that_does_not_bind…` (×5), `…unclassifiable_claim_records_nothing` (×6) |
| FD-17 deviations, stale outboxes, late claims | `…every_claim_protocol_deviation…` (×5), `…stale_outbox…never_adopted`, `…claim_in_the_write_outbox…`, `…never_read_after_its_ticket_left_verifying` |
| Mismatched tickets, recorders, caller-supplied authority | `…only_a_verifier_ticket_for_the_proven_write…`, `…only_the_session_minted_claim_recorder…`, `…expose_no_recorder`, `…no_caller_supplied_observation_or_digest…`, `…review_observations_are_still_refused_s5` |
| Duplicates, restarts, S3 evidence reuse, revocation | `…handed_off_once_and_never_runs_twice`, `…after_recovery_nothing…`, `…binds_exactly_one_write_intent`, `…revoking_the_approver…` |
| Crash points | `…crash_in_the_review_handoff…` (×7), `…crash_after_the_evidence_commit…` |
| Tamper → untrusted | `…tampered_s4_record…` (×24), `…settled_but_unconsumed…needs_its_evidence` |
| DL-3 → DL-2 | `…orchestration_path_records_the_bound_verification…` (incl. a second DL-3 call that dispatches and runs nothing), `…forged_verifier_reaches_no_trusted_state` |
| Static | `…s4_modules_have_no_execution…surface`, `…importing_the_a_side_with_s4…`, `…no_s4_public_api_accepts_bytes…`, `…frozen_review_command_is_unchanged_by_s4` |

## 11. Remaining obligations

- **S5** — `REVIEW_OBSERVED` answered by the same adapter from the claim
  recorded under this attempt's verifier ticket (must be shape
  `review-packet`; `ReviewProposal.evidence_sha256` = the claim digest; the
  verdict re-derived from the stored packet bytes); `review_evidence` rows;
  no second execution.
- **S6** — hold, bundle and `step-acceptance-subject.v2`, binding M0/M1/M2
  digests and labeling every claim (`claim_provenance`); the bundle should list
  M2's additions.
- **S7** — the driver and runbook: the X review console's reviewer
  environment (§5.7), `cmd.exe` redirection, the ticket's handoff paths, the
  exclusive store lock during the wait, and the proof cost (every proof now
  re-derives the write chain twice and re-hashes M1/M2 manifests and the claim).
- **E-12** must confirm a real 5F2D run against the X-owned detached clone
  with read-only `.git` leaves the `.git` control digest unchanged.

## 12. Validation

Run on Windows with the project venv on 2026-10-26, on top of `b4e6eeb`.

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_dl4b_s4_verification_claim.py -q -p no:cacheprovider` | **115 passed** in the full run below. During development, subset runs showed three test-side errors (one wrong refusal category expected in a forgery case, and the two §8 cases), each fixed and re-run green; no production change was needed for them |
| `… tests/test_dl4b_s0_identity_boundary.py tests/test_dl4b_s1_attestation_verifier.py tests/test_dl4b_s2_integration_store.py tests/test_dl4b_s3_write_handoff.py` | **966 passed** (S0 and S2 changed only as §1 states; S1 and S3 files unchanged) |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (`testpaths = ["tests"]`, includes DL-1/2/3/4A) | **5436 passed**, 0 failed, 1 warning, 2163 s. The warning is the existing, unrelated Pydantic serializer warning from `tests/test_supervised_implementer.py::test_a_post_load_forged_block_is_refused_by_revalidation` |

**Final status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**
