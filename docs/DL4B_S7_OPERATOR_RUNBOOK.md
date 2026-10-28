# DL-4B S7 — Operator Runbook for the Human-Supervised Alpha

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.** Offline-verified only.
Nothing in this runbook is authorized to run live until E-12, E-6 and
AUTH-PILOT are complete (§10). Read `docs/DL4B_S7_ALPHA_DRIVER.md` for what the
driver proves and does not prove.

The Alpha has three identities, and **every action below names exactly one**:

| Identity | Who | Runs | Never |
|---|---|---|---|
| **A** authority | Dedicated standard account | `alpha_driver` only, with an isolated interpreter | Repository code, any harness, Git, a model, a credential |
| **X** execution | Fresh standard account for this Alpha (new SID) | The frozen commands `l2-apply-approved-file-edit` and `l2-review-approved-file-edit` (and P1B before the Alpha) | Anything on the authority plane |
| **O** operator | The human's own account | `alpha_operator`, `ssh-keygen -Y sign`, a text viewer | Repository code; A's or X's work |

Each identity works in its **own** logon session (secure logon UI, fast user
switching, or an admin-provisioned S4U task for A). `runas`,
`Start-Process -Credential`, or starting one identity's process on another's
desktop is forbidden (FD-13). One Windows account for all three is **not** a
supported mode; there is no fallback.

---

## 1. Paths and names

All paths come from `identity-boundary.v1` (`%ProgramData%\AIDO\identity-boundary.v1.json`,
readable by A, X and O). Below they are written as `<state_root>`, `<inbox>`,
`<published>`, `<exchange>` and `<clone>`.

| Inbox name (O writes, A reads) | Content |
|---|---|
| `alpha-definition.json` | `alpha-definition.v1` (§3) |
| the definition's `approved_diff_name` | the H6 `approved-diff-proposal.v2` with its `DiffEditApproval` block |
| the definition's `project_config_name` | the project config the write scope binds |
| `attestation-project-contract.json` | `human-attestation.v2` for the contract challenge |
| `attestation-plan-activation.json` | … for the activation challenge |
| `attestation-exact-diff-approval.json` | … for the exact-diff challenge |
| `attestation-step-acceptance.json` | … for the step-acceptance challenge |

Every inbox file must be UTF-8 **without a BOM**, written by O (A checks the
owner), a single-link regular file.

## 2. How each identity launches its tool

**A** (in A's own session, or the provisioned task's fixed action), always
from `cmd.exe`, always isolated (`-I`; the driver refuses otherwise):

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-001-status.json"
```

The verbs are `status`, `request-approval`, `record-approval`, `run` and
`decline-acceptance`. The report is JSON on stdout. Redirect it with `cmd.exe`
into `<published>` (A owns it, O reads it, X has no access) under a new name
each time (`driver-<nnn>-<verb>.json`); that file is how A's report reaches O.
Exit codes: `0` APPROVAL_REQUIRED / READY_TO_RUN / AWAITING_HUMAN_ACCEPTANCE /
COMPLETE, `1` REFUSED, `2` HUMAN_REQUIRED, `3` RECOVERY_REQUIRED.

Only **one** A process can hold the store (DL-1's exclusive lock). While `run`
is waiting for X, a second A invocation is refused (`StoreLockedError`).

**O** (in O's session):

```bat
python -I -m ai_dev_orchestrator.integration.alpha_operator statement   --report "<published>\driver-002-request-approval.json" --approver-id <id> --key-fingerprint SHA256:<fp> --attested-at <instant> > "%USERPROFILE%\aido\statement-002.json"
ssh-keygen -Y sign -f "%USERPROFILE%\.ssh\id_ed25519_sk_aido" -n aido-approval@v1 "%USERPROFILE%\aido\statement-002.json"
python -I -m ai_dev_orchestrator.integration.alpha_operator attestation --report "<published>\driver-002-request-approval.json" --approver-id <id> --attested-at <instant> --signature "%USERPROFILE%\aido\statement-002.json.sig" > "<inbox>\attestation-<kind>.json"
```

The same `--attested-at` value must be used for both helper calls. It must be
an RFC 3339 instant with an offset, at or after the challenge's `issued_at`,
before its `expires_at` (60 minutes), and not later than A's clock when A
records it. For the **exact-diff** approval it must equal the artifact's
`DiffEditApproval.approved_at` exactly (C3-1, §4 step 5). The helper only
prepares bytes; S1's verifier rebuilds the statement from A's own records, so
a wrong helper output can only fail verification.

**X** (in X's session, `cmd.exe`, a **fresh console per command**): exactly
the two lines the driver printed (§5). Never PowerShell 5.1 `>`, which writes
UTF-16 with a BOM that the claim reader refuses.

## 3. The Alpha definition

O writes `<inbox>\alpha-definition.json` once, before the first A invocation:

```json
{
  "schema_version": "alpha-definition.v1",
  "project_contract": { "schema_version": "project-contract.v1", "project_id": "...", "goal": "...",
                        "requirements": ["..."], "protected_invariants": ["..."], "acceptance_criteria": ["..."] },
  "step": { "step_id": "step-a", "objective": "...", "depends_on": [] },
  "execution_policy": { "schema_version": "execution-policy.v1", "review_required": true,
                        "human_acceptance_required": true, "max_attempts": 1 },
  "write_scope": { "schema_version": "write-scope.v1", "step_id": "step-a", "path": "src/...",
                   "change_type": "modify", "pre_image_sha256": "<64 hex>", "base_head_oid": "<40 hex>",
                   "project_config_sha256": "<64 hex of the config file's bytes>" },
  "step_contract_proposal": { "step_id": "step-a", "requirements": ["..."], "protected_invariants": ["..."] },
  "approved_diff_name": "approved-diff-proposal.json",
  "project_config_name": "project.yaml"
}
```

It is parsed strictly (no extra field, no duplicate key, no string for a
number or a boolean). It is **not** authority: every value the store records
is bound by a signature over a subject the driver presents, and re-validated
by the store. Do not change it once the contract is approved: a definition
that no longer describes what the state root records refuses every verb
(`foreign_record`), and that ends the Alpha.

## 4. The procedure

Each row is one invocation or one human action. Run `status` whenever unsure;
it only reports (plus DL-1 `recover()` of an interrupted run).

| # | Who | Action | Expect |
|---|---|---|---|
| 0 | admin | Provision A, X (fresh), O, `identity-boundary.v1`, the approver registry, FD-14 ACLs, A's task (AUTH-PILOT). X clones, detached at `base_head_oid`; admin locks `.git` | E-5, E-9 |
| 1 | O | Place `alpha-definition.json` and the project config in `<inbox>` | — |
| 2 | A | `status` | `APPROVAL_REQUIRED`, stage `contract_approval` |
| 3 | A | `request-approval` → `driver-…-request-approval.json` | a `challenge`, the `subject` (the contract content and its digest), a `statement_template` |
| 4 | O | Review `subject.project_contract_content`. Prepare, sign, place `attestation-project-contract.json` (§2) | — |
| 5 | A | `record-approval` | stage `plan_activation` |
| 6 | A, O, A | `request-approval`; review the plan, policy, write scope, target workspace and digests; sign; `record-approval` | stage `exact_diff_approval` |
| 7 | X | P1B (`l2-supervised-implementer-prepare` / `-run`, per the ALPHA-P1B runbook). No repository code has run as X before this Alpha's review command | the proposal (outside the control plane) |
| 8 | O | H6: review the exact diff. Write the `approved-diff-proposal.v2` with `DiffEditApproval` (`approved_by` = your approver id, `approved_at` = **T**, a time a few minutes ahead). Place it in `<inbox>` under `approved_diff_name` | — |
| 9 | A | `request-approval` (issued before T) | `subject.approved_diff_artifact_sha256` = SHA-256 of the inbox artifact (check with `certutil -hashfile <file> SHA256`) |
| 10 | O | After T has passed: sign with `--attested-at` **= T**; place `attestation-exact-diff-approval.json` | — |
| 11 | A | `record-approval` | `READY_TO_RUN`, stage `attempt` |
| 12 | A | `run` (long: up to two waits of `CLAIM_WAIT_SECONDS` = 7200 s each) | first, an `announced_x_actions` entry for the **write** |
| 13 | X | New `cmd.exe` with **no** reviewer variables. Run the two printed lines (frozen writer, then `type nul > …\complete`) | A continues: M1, `IMPLEMENTATION_RETURNED`, then announces the **review** |
| 14 | X | New `cmd.exe`. Set the configured reviewer provider's variables **in this console only** (§5.7 of the design). Run the two printed lines. Close the console | A continues: M2, `VERIFICATION_OBSERVED`, `REVIEW_OBSERVED`, planner rule, hold |
| 15 | A | (`run` returns) | `AWAITING_HUMAN_ACCEPTANCE`, stage `acceptance`, `held.recommendation` = `RECOMMEND_STEP_ACCEPT` |
| 16 | A | `request-approval` | the bundle is published; the `subject` names it and the `step-acceptance-subject.v2` |
| 17 | O | Inspect the bundle (§6). **Decide.** | — |
| 18a | O, A | Accept: sign, place `attestation-step-acceptance.json`; A `record-approval` | `COMPLETE` |
| 18b | A | Decline: `decline-acceptance` (nothing is signed) | `HUMAN_REQUIRED` |
| 19 | A, admin | `status` (final recover); archive the state root; disable X | — |

Any other outcome ends the Alpha (E-10): **no retry, repair, rollback, cleanup,
second attempt, `git restore`, branch, commit, push or PR**. Inspect, then stop.

## 5. The X steps exactly

For each X step the driver prints an `announced_x_actions` entry like:

```json
{"actor": "X", "action": "run_frozen_write_command", "role": "implementer", "ticket_id": "<32 hex>",
 "handoff_directory": "<exchange>\\handoff-<ticket>", "outbox_directory": "<exchange>\\outbox-<ticket>",
 "cmd_exe_lines": ["ai-dev-orchestrator l2-apply-approved-file-edit --project-config \"…\\project.yaml\" --approved-diff-proposal \"…\\approved-diff-proposal.json\" --apply-approved-plan --write-approved-file > \"…\\stdout.json\"",
                   "type nul > \"…\\complete\""],
 "a_waits_seconds": 7200}
```

- Type the lines **as printed**, one after the other, in X's `cmd.exe`. Create
  `complete` only after the command has exited, whatever its exit code.
- Put **nothing else** in the outbox. One `stdout.json`, one empty `complete`.
- The handoff directory is read-only to X and holds exactly the artifact and
  config bytes A approved. Do not copy inputs from anywhere else.
- If the command cannot be run, do nothing: A's wait expires and the step is
  `RECOVERY_REQUIRED`. Never write a `stdout.json` by hand.
- The write console must not hold reviewer variables. The review console holds
  only the configured provider's names and is closed afterwards.

## 6. What O inspects, and what each thing is

| Material | Where | Class |
|---|---|---|
| Contract content and its digest | `subject` of the contract `request-approval` report | what you sign (by digest) |
| Plan, policy, write scope, target workspace, config digest, boundary digest | `subject` of the activation report; `subject_sha256_recomputed_by_driver` must equal `challenge.subject_sha256` (the driver refuses to present otherwise) | what you sign |
| The exact diff | the artifact you placed (`<inbox>`); `subject.approved_diff_artifact_sha256` is its digest as A read it | what you sign |
| The step contract and write scope that ran | the bundle (built from the store's records); `acceptance.subject.step_contract_sha256` binds the step contract | AIDO-recorded; signed at acceptance |
| M0 / M1 / M2 | bundle `aido_observed.observations` and the `observations-<sha256>` files in `<published>` | **AIDO-observed facts** (A's own Git-free reads) |
| Approved change, approvals, lifecycle | bundle `aido_observed.approved_change`, `.lifecycle`, `.write_intent` | AIDO-observed |
| Write report | bundle `execution_claims.write_report`, file `claims-<sha256>` | **execution claim** |
| Verification outcome and output | bundle `execution_claims.review_command.verification_outcome`, the review claim file | **execution claim** |
| Review verdict and findings | bundle `execution_claims.review_command.review_verdict`, the review packet in the claim file | **execution claim** (model output, advisory) |
| M2 additions | bundle `aido_observed.m2_additions` | AIDO-observed; files the verification left behind |
| The held planner decision | bundle `planner.held_envelope` | AIDO's deterministic rule over the records above; it recommends, never completes |
| What you sign at acceptance | bundle `acceptance.subject` (`step-acceptance-subject.v2`) = report `subject.step_acceptance_subject_v2`; its digest = `challenge.subject_sha256` | what you sign |

**An execution claim is never proof.** Repository code ran in X during the
review command, and it could have printed any verification outcome or verdict.
A successful M2 shows only that the clone was exactly as approved when A
looked. A model's `approve` is **not permission to complete**: only your
signature over the acceptance subject completes the step, and you may decline
without signing anything. The statement file you sign is the exact byte string
the verifier rebuilds; open it and check `subject_sha256` before signing.

## 7. Files that may cross, and files that must never cross

| From → to | May cross | Must never cross |
|---|---|---|
| O → A | inbox files (§1) | O's private key, PIN, anything from X |
| A → O | `<published>`: driver reports, acceptance bundle and its blob copies | A's store, `evidence/`, staging, A's profile |
| A → X | `<exchange>\handoff-<ticket>\` (read-only to X) | anything else on the authority plane |
| X → A | exactly `stdout.json` and `complete` in `<exchange>\outbox-<ticket>\` | any other file; any file into the inbox, `<published>`, or the state root |
| X ↔ O | nothing | reviewer credentials, the clone's files as "evidence" |
| anyone → A's environment | nothing | `AIDO_LITELLM_*`, `AIDO_VLLM_*`, `GITHUB_TOKEN`, `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `PYTHONUSERBASE` (the boundary proof refuses them) |

## 8. Interruption and restart

| Interrupted at | Next invocation sees | Do |
|---|---|---|
| any approval (request or record) | the stage the store holds: a recorded approval is never asked for again; an unrecorded one is still pending | `request-approval` for a fresh challenge if the old one expired |
| `run`, before the attempt began (contract issued, run or step created, step READY) | `READY_TO_RUN` | `run` again; the human X steps happen then |
| `run`, after the attempt began (EXECUTING, VERIFYING, REVIEWING) | `RECOVERY_REQUIRED` (DL-1 `recover()`); never resumed, never re-dispatched; a late claim is never read | stop (E-10) |
| `run`, after `REVIEW_OBSERVED`, before the planner ticket | `READY_TO_RUN`, stage `decision` | `run`: it decides and holds; no X step repeats |
| `run`, after the planner ticket, before the hold | `READY_TO_RUN`, stage `decision`; `run` ends `HUMAN_REQUIRED` (a planner is never asked twice) | stop |
| after the hold | `AWAITING_HUMAN_ACCEPTANCE`, unchanged across any number of restarts | continue at step 16 |
| `record-approval` at acceptance, before its commit | `AWAITING_HUMAN_ACCEPTANCE`; nothing consumed | `record-approval` again (same signature, while the challenge is open) |
| after COMPLETE | `COMPLETE`; nothing can be applied again | close out |

## 9. Refusals you may see

| Category | Meaning |
|---|---|
| `interpreter_not_isolated` | A was not started with `-I` |
| `IsolationUnprovenError:<category>` | the FD-16 boundary proof failed; nothing was opened or consumed. Fix provisioning (admin) |
| `definition_unreadable` / `definition_invalid` | the definition is missing, not O's file, or not strict `alpha-definition.v1` |
| `foreign_record` | the state root records something this definition does not describe (another contract, plan, approval or step contract). The Alpha has ended |
| `no_pending_approval`, `not_runnable`, `nothing_to_decline` | the verb is not the stage's next authorized action; nothing changed |
| `attestation_unreadable` / `attestation_invalid` / `attestation_kind_mismatch` | the inbox attestation is missing, malformed, or answers another kind of challenge |
| `HumanAttestationRefusedError:<category>` | S1/S2 refused the signature (expired challenge, wrong key, revoked key, statement mismatch, timestamp) |
| `subject_unconfirmed` | the driver's re-derivation of the subject disagrees with the challenge: **do not sign**; the challenge expires unused |
| `StateUntrustedError` | a recorded approval or record no longer re-proves (for example a revoked key, or more than one project run). The Alpha has ended |

## 10. Not yet authorized

E-12 (live isolation rehearsal), E-6 (real-authenticator rehearsal) and
AUTH-PILOT (E-1…E-13) must each be completed and separately authorized before
step 0 of a live Alpha. In particular E-12 must confirm, on the provisioned
host, that A can create `driver-*.json` files in `<published>` by `cmd.exe`
redirection with the protected DACL inherited, that X cannot touch them, and
how long each re-proven A invocation takes.
