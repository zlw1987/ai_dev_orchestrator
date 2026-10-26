# DL-4B S3 — Exact-Diff Approval and Write Handoff

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `0b63e8bc6c3a03dcd4ca9a965f2e2fecf8688b1e` (S0, S1, S2 accepted and frozen for offline scope) |
| Contract | `docs/DL4B_REAL_INTEGRATION_BOUNDARY_DESIGN.md` (AMEND1): FD-6, FD-9 to FD-18, §§5.5, 5.8, 8, slice S3 (§11); `docs/DL4B_S2_INTEGRATION_AUTHORITY_STORE.md` §11 |
| Kind | Offline implementation. No live Alpha, no account, no credential, no model, no Git or subprocess in A |
| Not authorized | M2 and verification (S4), review evidence (S5), the acceptance lifecycle (S6), the Alpha driver (S7), E-6, E-12, any live run, any `CLAUDE.md` change |

S3 gives a step **one authorized write opportunity, with independently observed
evidence of its result**. It connects, mechanically and at every proof:

```text
signed exact-diff approval (H6) ─ binds ─► activated write-scope.v1 + the exact artifact bytes
          │ spent once, in the same transaction as
          ▼
durable write intent ─ bound to ─► the authorized implementer dispatch ticket + M0
          │ committed BEFORE
          ▼
handoff-<ticket> / outbox-<ticket>  ──►  the HUMAN runs the frozen 5F2C command as X
          │                                    │ stdout + completion marker
          ▼                                    ▼
M1 (A's own reads) ──► effect = as approved / no change / indeterminate   ◄── execution claim (receipt)
          │ only "as approved" + a binding claim
          ▼
IMPLEMENTATION_RETURNED (fixed AIDO report) — accepted only for that exact ticket
```

---

## 1. Modules

| Module | Kind | Content |
|---|---|---|
| `control_plane/integration_records.py` | changed, pure | `exact_diff_approval_subject_v1_sha256`, `WRITE_HANDOFF_REPORT_SUMMARY` |
| `integration/claim_readers.py` | new, pure | Mirror readers: `read_approved_diff` (`approved-diff-proposal.v2`), `read_write_claim` (`workspace-write-result.v1`), `read_project_config`; fixed size caps |
| `integration/authority_files.py` | new | The `AuthorityFiles` protocol and the production `WindowsAuthorityFiles` (S0's read-only facts, plus `CreateDirectoryW` with a descriptor and `CreateFileW CREATE_NEW`) |
| `integration/workspace_observation.py` | new | FD-18: `observe_git_control`, `observe_workspace`, `parse_manifest`, `classify_write`; fixed caps |
| `integration/claim_receiver.py` | new | FD-17: `await_completion`, `read_claim`; `CLAIM_WAIT_SECONDS`, `SystemWaiter` |
| `integration/exchange.py` | new | Per-ticket `handoff-<ticket>` / `outbox-<ticket>`: code-constant protected DACLs, exclusive creation, post-creation proof |
| `integration/state_blobs.py` | new | Write-once blobs under `evidence/{approved-diff,config,claims,observations}` using DL-4A's primitive |
| `integration/write_handoff.py` | new | `WriteHandoffAdapter` (DL-2's bound implementer port) and its private recorder |
| `integration/integration_store.py` | changed | Two new tables, the activation-time observation, `request_exact_diff_approval`, `record_exact_diff_approval`, the capability-gated write handoff, the S3 proofs, and `IMPLEMENTATION_RETURNED` acceptance |
| `integration/integration_session.py` | changed | Mints the recorder key into the store and the adapter; exposes `implementer`; library `files` / `waiter` |
| `tests/test_dl4b_s3_write_handoff.py` | new | See §10 |
| `tests/test_dl4b_s2_integration_store.py`, `tests/test_dl4b_s0_identity_boundary.py` | changed, narrowly | See §9 |

## 2. Pre-implementation adversarial analysis

Every object, who creates or changes it, and what it would take to make it lie.

| Object | Created / mutated by | What proves it | Supported-caller bypass considered | Mismatched valid objects | Re-checked at consumption |
|---|---|---|---|---|---|
| Approved artifact bytes | O places them in the inbox; A copies them write-once into the state root | sha256 inside the signed subject; re-hashed on every read | Caller-supplied bytes or model: no parameter accepts either; A reads O's file by name from the boundary's inbox, once, denying write sharing, owner must be O | Artifact path / pre-image vs scope; identity vs config; approval block vs attestation | Request, record, intent claim, every proof |
| Project config bytes | O (inbox); A write-once | Digest bound in the activation (`write-scope.v1.project_config_sha256`); re-hashed | Config read from a caller path: none | Workspace root vs activated clone (path **and** identity at consumption, path at proof); `workspace_write.enabled`; project and repo vs artifact | Request, intent, every proof |
| Exact-diff challenge / request | Store | Request row binds plan, step, scope, artifact and config digests; subject recomputed from stored bytes | A caller-built challenge answers nothing (unknown id) | Attestation for another kind or subject; for another state root | FD-5 pre-check, re-check in the write transaction |
| Exact-diff approval | Store, from a signed attestation | Signature re-verified against the current registry (FD-4) on every proof | A typed phrase, a matching digest, a `model_construct` attestation, another key: all refused | Second approval for the same step: `UNIQUE (plan, step)` | Intent claim (unspent), IMPLEMENTATION_RETURNED, every proof |
| Activation-time `.git` observation | Store, inside the activation transaction | Manifest blob re-derived; HEAD = scope base | No API records one | HEAD ≠ scope base → activation refused | M0, every proof |
| Implementer ticket | Store (DL-4A) | Persisted row; compared field by field | A stale or forged ticket: row equality, role, unconsumed, EXECUTING at its version | Ticket of another step / version | Every phase of the handoff |
| M0 / M1 | The store itself, through `AuthorityFiles` | Manifest blob re-derived and canonical; row columns equal the manifest | No API accepts an observation; the recorder takes only a ticket | M0 vs pre-image, base HEAD, activation `.git`; M1 vs M0 | Intent, settlement, every proof |
| Write intent | Store, in the transaction that spends the approval | Row bound to ticket, approval, scope, artifact, workspace, M0 | Re-entrant or concurrent claim: the write transaction re-checks everything | Intent of another ticket / approval | Every phase, every proof |
| Handoff / outbox directories | A, exclusive create with a protected DACL set at creation | Re-read after creation: owner A, protected, exactly A's ACEs, identity recorded | Pre-existing directory: refused, never adopted | Substituted outbox: identity and DACL re-proven before the claim is read | Before the claim read |
| Execution claim | X writes it; A reads it once | **Only a receipt** (FD-15) | No API accepts claim bytes; only the store's receiver reads, only the outbox it created, only while the ticket is EXECUTING | Path, approver, time, identity, sizes vs scope, H6, M0, M1 | Settlement, every proof (re-parsed) |
| Write evidence | Store, only when the effect is as approved and the claim binds | Re-derived from every row and blob above | — | — | IMPLEMENTATION_RETURNED, every proof |

Crash and partial-effect analysis is §6; disclosure: refusal messages carry
categories, repo-relative labels and digests, never artifact, diff, config or
claim content.

## 3. Exact-diff authority flow (H6)

```text
O → inbox:   approved-diff-proposal.v2 (with the frozen DiffEditApproval) + project.yaml
A: request_exact_diff_approval(execution_plan_sha256, step_id, artifact_name, config_name)
   1 re-prove boundary; activation re-proven (signature, scope, config digest, .git observation)
   2 read both inbox files ONCE (single link, regular, own path, owner = O, size cap)
   3 validate: config sha = scope's; artifact: one modify of scope.path from scope.pre_image,
     manual DiffEditApproval with the exact phrase, consistent identity, plan scope;
     config: workspace_write enabled, same project/repo, workspace root = activated clone
     (canonical path AND directory identity)
   4 publish both write-once into the state root
   5 ONE transaction: re-derive everything FROM THE STORED BYTES; the subject must equal
     step 3's; insert approval-challenge.v2 (exact_diff_approval) + exact_diff_requests row
O signs exact-diff-approval-subject.v1 (attested_at = the artifact's approved_at)
A: record_exact_diff_approval(attestation)
   FD-5: re-derive from stored bytes, artifact approval block = attested approver and time,
   verify OUTSIDE the transaction, re-check inside, insert the approval, consume the challenge
```

`exact-diff-approval-subject.v1` = sha256 of canonical
`{schema_version, kind, plan_activation_subject_sha256, execution_plan_sha256,
step_id, write_scope_sha256, approved_diff_artifact_sha256}`. Naming the
activation by its own signed v2 subject binds plan, policy, clone, scopes,
config and identity boundary transitively.

**One approval per step, ever** (`UNIQUE (execution_plan_sha256, step_id)`).
An identical repeat is a receipt while it re-proves.

## 4. Write-intent transaction ordering

All four phases run inside `IntegrationStore._perform_write_handoff(key,
ticket)`; each phase requires the recorder key and re-proves the boundary.

```text
1 INTENT   txn(read): ticket = stored row, implementer, unanswered, step EXECUTING @ ticket
           version, project ACTIVE; approval re-proven (signature) and UNSPENT; no intent
           re-prove the clone (path + identity) and the config workspace (path + identity)
           M0 = observe_workspace(): target = pre-image, HEAD = base, .git = activation's
           publish M0 manifest blob
           txn(write): all of the above again; INSERT M0 row; INSERT write intent 'pending';
           UPDATE approval SET consumed_by_ticket_id WHERE NULL (rowcount 1);
           INSERT execution_handoffs (unpublished)                       ── COMMIT ──
2 PUBLISH  create handoff-<ticket> (protected DACL at creation), prove it; write the two
           files exclusively, prove listing and bytes; create outbox-<ticket>, prove it
           txn(write): record both identities + published_at
3 RECEIVE  wait (fixed bound) for `complete`, listing only; re-prove boundary;
           txn(read): ticket still EXECUTING @ version, intent pending, no claim (late-claim rule)
           re-prove the outbox's identity and DACL; read the claim ONCE (FD-17)
4 SETTLE   M1; effect = classify_write(M0, M1); parse + bind the claim
           publish M1 and claim blobs
           txn(write): INSERT M1; INSERT claim receipt (if it parsed as write-result);
           UPDATE intent pending → completed | refused | indeterminate; INSERT write
           evidence iff completed                                         ── COMMIT ──
           completed → fixed ImplementationReport; otherwise raise (DL-2 → RECOVERY_REQUIRED)
```

A failure in phase 2 or 3 (refusal, protocol deviation, deadline) still
settles: M1 decides `refused` (no change) or `indeterminate`. A boundary
failure or a crash settles nothing; the intent stays `pending` and
`recover()` reduces the step.

## 5. FD-17 handoff protocol and FD-18 observations

**Exchange layout** (Claude's choice, §10.1): flat, in the boundary's exchange
root, `handoff-<ticket>` and `outbox-<ticket>`. DACLs are code constants,
protected, set at creation, owner A:

| Directory | ACEs |
|---|---|
| handoff | A full (OICI); X read+execute (OICI); SYSTEM, Administrators full |
| outbox | OWNER RIGHTS read+execute (OICI) — limits A, and X on its own files; A read+execute (OICI); X list + add-file (this folder); X read+write+delete (files only, inherit-only); O read+execute (OICI); SYSTEM, Administrators full |

A test evaluates these with S0's upper-bound evaluator: X gets no
`WRITE_DAC`, `WRITE_OWNER`, `DELETE` or `DELETE_CHILD` on either directory and
cannot add to the handoff; A cannot add to or re-permission the outbox.

**Claim protocol**: the human, in X's own `cmd.exe`, runs the frozen command
with `--project-config <handoff>\project.yaml --approved-diff-proposal
<handoff>\approved-diff-proposal.json --apply-approved-plan
--write-approved-file`, redirects stdout to `<outbox>\stdout.json`, and after
it exits creates an empty `<outbox>\complete`. (Windows PowerShell 5.1's `>`
writes UTF-16 with a BOM, which the strict reader refuses; S7's runbook must
use `cmd.exe` redirection or an equivalent byte-exact one.)

| Check | Constant / rule | Category on failure |
|---|---|---|
| Wait | `CLAIM_WAIT_SECONDS = 7200`, poll 2 s, listing only | `deadline_expired` |
| Entries | exactly `stdout.json` and `complete` | `missing_entry`, `unexpected_entry` |
| Each entry | regular, not reparse, one link, at its own path, owner X | `not_regular_file`, `reparse_point`, `hard_link`, `path_mismatch`, `wrong_owner` |
| Marker | empty | `marker_not_empty` |
| Claim | non-empty, ≤ `MAX_WRITE_CLAIM_BYTES = 4 MiB`, read once denying write/delete sharing | `empty`, `oversize`, `sharing_violation`, `read_failed` |
| Late claim | never read unless the ticket is still EXECUTING at its version | refusal, intent left pending |
| Outbox | same identity and DACL as created | `substituted`, `dacl_mismatch` |

**Observations** (`authority-observation.v1` manifest, canonical JSON, no time,
content-addressed): HEAD must be exactly one oid + LF; `.git` control =
HEAD, config, index, packed-refs, shallow, commondir, objects/info/alternates
and every file under refs/, hooks/, info/; `modules/` refuses. Tree = every
regular file outside the top-level `.git`. Refused: reparse points, files with
more than one link, nested `.git`, top-level `.gitmodules`, entries Win32
cannot address exactly, case-only duplicates, a handle whose final path is
not the opened path, and over-cap trees (`MAX_TREE_ENTRIES = 50 000`,
`MAX_TREE_BYTES = 1 GiB`, `MAX_FILE_BYTES = 64 MiB`, `.git` 10 000 entries /
256 MiB). Each file is read once from a write-sharing-denied handle.

| Observation | Taken | Must hold |
|---|---|---|
| activation | in the activation | detached HEAD = scope base; recorded `.git` digest |
| M0 | before the intent | target = pre-image; HEAD = base; `.git` = activation's |
| M1 | after the claim (or its failure) | `as_approved`: HEAD and `.git` unchanged and the tree differs in exactly the target, pre → post; `no_change`: identical; else `indeterminate` |

## 6. Failure matrix

| Point | Durable result | Step after `recover()` | Approval | Second write possible? |
|---|---|---|---|---|
| Any refusal before the intent commit (ticket, boundary, approval, workspace, config, M0) | nothing new | RECOVERY_REQUIRED (DL-2 reduces) | unspent | no: one attempt, and the store refuses a new ticket outside EXECUTING |
| Crash at any statement of the intent transaction | rolled back | RECOVERY_REQUIRED | unspent | no |
| Crash after the intent commit, before or during publication | pending intent, maybe a partial handoff | RECOVERY_REQUIRED | spent | no (intent per ticket, approval spent, directories never adopted) |
| Publication refused (pre-existing / substituted / DACL) | intent `refused` or `indeterminate` | RECOVERY_REQUIRED | spent | no |
| Deadline, protocol deviation, malformed claim | intent per M1 | RECOVERY_REQUIRED | spent | no |
| Ticket left EXECUTING while A waited | claim never read; intent pending | RECOVERY_REQUIRED | spent | no |
| M1 shows no change | `refused` | RECOVERY_REQUIRED | spent | no |
| M1 indeterminate, or as approved with a missing / contradicting claim | `indeterminate` | RECOVERY_REQUIRED | spent | no |
| Crash in the settlement transaction | rolled back; intent pending | RECOVERY_REQUIRED | spent | no |
| Completed, crash before / during IMPLEMENTATION_RETURNED | intent completed, ticket unanswered | RECOVERY_REQUIRED | spent | no |
| IMPLEMENTATION_RETURNED recorded | VERIFYING | (S4) — offline the verifier is refused → RECOVERY_REQUIRED | spent | no |

Nothing is retried, rolled back, restored, cleaned or repaired. A never
deletes a handoff or outbox.

## 7. Post-implementation adversarial review

| Id | Finding | Material? | Fix / regression |
|---|---|---|---|
| R3-1 | The internal phases (`_claim_write_intent`, `_publish_write_handoff`, `_receive_write_claim`, `_settle_write`) were reachable without the recorder key, so a T1 caller could spend the approval and publish a handoff around the adapter | Yes (defense in depth; FD-6) | Every phase requires the key and re-proves. `test_only_the_session_minted_recorder_can_hand_off_a_write` |
| R3-2 | A second session, or a re-entrant claim during M0, racing the first intent claim | Checked, sound | A second session cannot even open the store (DL-1's exclusive lock), including during A's wait; a session that later opens it must `recover()` first. A re-entrant claim during M0 is refused by the write transaction's full re-check. `test_racing_intent_claims_spend_the_approval_once`, `test_a_second_session_cannot_claim_the_spent_approval_concurrently` |
| R3-7 | A claim delivered while the step was reduced out of EXECUTING (another actor's transition during A's wait) | Checked, sound | The claim is never opened; the intent stays pending; recovery re-proves. `test_a_claim_is_never_read_after_its_ticket_left_executing` |
| R3-8 | Revocation of the approver between approval and dispatch | Checked, sound | The intent claim refuses (the approval no longer re-proves) and nothing is published; `recover()` escalates and the escalation persists after un-revoking. `test_revoking_the_approver…` |
| R3-3 | Exact-diff time agreement: the design requires the artifact's `approved_at` to equal the attested time, and the challenge window requires `issued_at ≤ attested_at ≤ now` | Procedural (C3-1) | The human writes a slightly future `approved_at` into the artifact before requesting the challenge, and signs with that time. Tested |
| R3-4 | `workspace-write-result.v1` carries no image digests, so "both hashes" (§5.5 step 7) cannot be bound from the claim | No: M0/M1 bind them | The claim binds target sizes to M0/M1 instead; the digests are A's own (C3-2) |
| R3-5 | Importing the frozen `file_editing` / `diff_proposal` models loads the Git adapter, `subprocess`, `httpx` and the LLM client | Yes, if imported | Mirror readers, pinned to the shipped models by test; a subprocess-isolated import test proves the A side loads none of them |
| R3-6 | A's store connection holds the store exclusively, so another session cannot open it during the two-hour wait | No (single A process) | Recorded for S7 |
| — | Late write after settlement: the handoff stays readable to X, so X could still apply it after M1 | Residual, not material: the step is already RECOVERY_REQUIRED and no AIDO record changes | §11 |

## 8. Contradictions and tensions

- **C3-1 (procedural).** FD-5 window + the design's `approved_at == attested_at`
  rule ⇒ the artifact must be written with its future approval time. No frozen
  contract changes.
- **C3-2 (factual).** §5.5 step 7 says the claim binds "both hashes"; the
  frozen report has none. A binds sizes; M0/M1 bind digests.
- **C3-3.** §8 lists `claim_write_intent` as a store API. S3 makes it
  capability-gated instead of public: strictly narrower, and no API accepts a
  caller's observation.
- **C3-4.** S2's provisional `execution_handoffs` identity columns become
  nullable until publication (an all-or-nothing CHECK), because the row must
  commit before the directories exist (FD-17 step 1). Two tables are added
  (`exact_diff_requests`, `activation_observations`). No v4 store exists
  outside tests.

No frozen DL-1/2/3/4A, S0, S1, 5F2C contract or `CLAUDE.md` was changed.

## 9. Changes to S0/S2 artifacts

- `integration_store.py`: S2's "any row in an S3 table is unexplained" rule is
  replaced by the S3 chain proofs; S4–S6 tables and every non-implementer role
  output are still refused. The activation records the `.git` observation.
- `tests/test_dl4b_s2_integration_store.py`: the synthetic clone gains a
  detached `.git` (HEAD, config, index) so activation can observe it; the
  public-method classification and the re-proof matrix list the two new
  methods; the session's public set lists `implementer`. No assertion was
  weakened.
- `tests/test_dl4b_s0_identity_boundary.py`: the package module-set pin lists
  the seven S3 modules.

## 10. Tests

`tests/test_dl4b_s3_write_handoff.py` — 51 functions, 147 cases.

| Acceptance criterion | Tests |
|---|---|
| 1 Approval binds the artifact and the scope | `…binds_the_stored_artifact_bytes…`, `…changing_the_artifact_in_the_inbox…`, `…outside_the_scope_or_the_5f2c_contract…` (×10), `…not_one_strict_json_object…` (×6), `…not_the_scope_s_or_the_clone_s…` (×5), `…inbox_files_must_be…` (×9), `…approval_block_must_be_the_attested…` (×2), `…forged_or_misdirected_signature…`, `…another_state_root…` |
| 2 Atomic, single-use consumption + intent | `…single_use_per_step…`, `…two_open_challenges…`, `…racing_intent_claims…`, `…second_session…` |
| 3 No handoff before the durable intent | `…no_handoff_is_visible_before_the_intent_is_durable`, M0 matrix (`w.handoff_dirs() == []`) |
| 4 M0 refuses pre-image, HEAD, `.git` | `…m0_refuses_and_nothing_is_spent…` (×10), `…over_cap_tree`, `…activation_refuses_a_head…` |
| 5 M1 identifies the effect independently of the claim | `…m1_decides_what_happened…` (×8), `…m1_classification_is_a_pure_function…` |
| 6 Every FD-17 deviation fails closed | `…every_claim_protocol_deviation…` (×13), `…deadline_is_a_code_constant…`, `…never_read_after_its_ticket_left_executing`, `…pre_existing_per_ticket_directory…` (×2), `…without_exactly_the_dacl…` (×3), `…outbox_replaced_while_a_waited…` |
| 7 Caller-injected claims / observations / reports establish nothing | `…only_the_session_minted_recorder…`, `…expose_no_recorder`, `…report_without_proven_write_evidence…`, `…only_the_fixed_report_returns`, `…contract_or_attempt_other_than…`, `…non_implementer_or_stale_ticket…`, `…no_s3_public_api_accepts_bytes…` |
| 8 Duplicate, concurrent, restarted | `…second_handoff_for_the_same_ticket…`, `…second_session…`, `…racing…`, `…after_recovery_nothing_can_hand_off…` |
| 9 Crash at every point | `…crash_in_the_write_handoff…` (×11 statements), `…crash_around_publication_or_reception…` (×5), `…crash_while_recording_the_implementation…` (×3) |
| 10 Direct store and DL-3 → DL-2 | `…orchestration_path_records_the_proven_write…` (incl. a second DL-3 call dispatching nothing), `…enforces_m0_like_the_direct_path`, `…reduces_an_unproven_write…`, `…forged_implementer_reaches_no_trusted_state` |
| Tamper → untrusted | `…tampered_s3_record…` (×23), `…revoking_the_approver…` |
| Production primitives | `…create_directories_with_exactly_the_requested_dacl`, `…read_denies_write_sharing…` |
| Static | `…no_execution_network_model_git_or_harness_surface`, `…importing_the_a_side_loads_no_harness…`, `…mirror_readers_restate_the_shipped_models`, `…agrees_with_the_frozen_parser…` |

Every refusal test that changes nothing asserts an unchanged snapshot of all
tables (and, for M0, that no handoff exists). The frozen 5F2C command is the
only thing that writes the clone, and only inside the simulated X step.

## 11. Remaining obligations and residuals

- **S4** — the review handoff (`handoff-<verifier ticket>`), claim
  classification of the review command's stdout, M2, `verification_evidence_v2`;
  the verifier ticket and M2 kind are still unexplained in S3.
- **S5** — review evidence from the same claim. **S6** — hold, bundle,
  acceptance subject v2 (binding M0/M1 digests from `write_evidence`). **S7** —
  the driver, the X runbook (cmd.exe redirection; the ticket's handoff paths),
  measuring the per-call proof cost (every proof now re-verifies the
  exact-diff signature and re-hashes the blobs), and the exclusive store lock
  during the wait.
- **E-12** must confirm: `CreateDirectoryW` with these descriptors as A; X can
  create and write `stdout.json`/`complete` but not re-permission them; the
  frozen writer accepts the detached HEAD and the read-only `.git`; the
  `.git` control digest is unchanged across a real 5F2C run.
- Residuals: alternate data streams and attributes are not observed; an
  observation is a moment (D-13); a late X write after settlement is possible
  because the handoff remains readable (the step is already
  RECOVERY_REQUIRED); in-process private access (DL-4A §2); D-7, D-8, R-5
  unchanged.

## 12. Validation

Run on Windows with the project venv on 2026-10-26, on top of `0b63e8b`.

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_dl4b_s3_write_handoff.py -q -p no:cacheprovider` | **146 passed** (517 s); the 147th case, `…enforces_m0_like_the_direct_path`, was added after that run and passed with the orchestration subset (4 passed) and in the full run |
| `… tests/test_dl4b_s0_identity_boundary.py tests/test_dl4b_s1_attestation_verifier.py tests/test_dl4b_s2_integration_store.py tests/test_control_plane_dl1.py tests/test_control_plane_dl2.py tests/test_control_plane_dl3.py tests/test_control_plane_dl4a.py` | **1258 passed** (DL-1/2/3/4A and S1 files unchanged; S0 and S2 changed only as §9 states) |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (`testpaths = ["tests"]`) | **5321 passed**, 0 failed, 1 warning, 1126 s. The warning is the existing, unrelated Pydantic serializer warning from `tests/test_supervised_implementer.py::test_a_post_load_forged_block_is_refused_by_revalidation` |

**Final status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**
