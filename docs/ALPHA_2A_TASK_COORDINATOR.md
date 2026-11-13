# ALPHA-2A-T1 — Single-File Task Coordinator

Status: **ACCEPTED — Personal Alpha 2A Live Integrated Acceptance.** The
Product Owner accepted the ALPHA-2A-T2 live run `20261110T181352Z-e7cc70f6`
(§7). The ALPHA-2A-T3 preflight correction (§6: `task-doctor` and `task-start`
now check `read_only_workspace_content`) is implemented and **independently
reviewed and ACCEPTED**. ALPHA-2B-T1 (§9) adds one human-initiated correction
round; it is implemented and offline-tested only and awaits independent review.

## 1. What it is

Personal Alpha 2A's first task. Before it, one change needed about six
separate commands, approval wrappers assembled by hand (`docs/alpha0/a0_helper.py`),
a run directory and config per run, and a review packet that existed only on
stdout. ALPHA-2A-T1 adds four commands that carry one single-file task through
the **already accepted** stages, with the artifacts in one run directory:

```text
task-start     human task inputs -> run dir + deterministic L1 plan draft     (offline)
task-status    derived stage + the exact next command                          (read-only)
task-continue  run the current stage's accepted runner(s), record, stop        (per-stage flags)
task-doctor    gate check + reviewer endpoint block derived from the env       (read-only)
```

It is a **thin, fixed sequence**, not an orchestration framework. It adds no
authority, no gate, no model call, no subprocess and no approval.

## 2. Why not the DL-4B Alpha driver

`integration/alpha_driver.py` cannot run live on one Windows account:
`open_integration_session` proves an S0 boundary between separate identities
and has "no same-account mode"; it needs S1 SSH-signed attestations; it never
launches anything itself, only announces X-side commands; and its implementer
port is the write command fed from an inbox, with no model-implementer stage.
Making it live would reopen frozen S0/S1. It stays offline and untouched.

## 3. The sequence and its four human pauses

| Stage | Human does | `task-continue` flags | Runs (unchanged runner) |
|---|---|---|---|
| `plan_approval` | fills `approval` in `10-plan.draft.json` | `--prepare-supervised-implementation` | freeze plan, CRLF check, `_run_l2_supervised_implementer_prepare` |
| `implementer_consent` | fills `consent` in `20-authorization-<n>.json` | `--transmit-approved-source --real-implementer` | `_run_l2_supervised_implementer_run`, then writes the diff draft |
| `diff_approval` | reads `30-proposed.diff`, fills `approval` in `30-diff.draft.json` | `--apply-approved-plan --write-approved-file --verify-approved-file-edit --real-reviewer` | freeze diff, `_run_l2_apply_approved_file_edit`, then `_run_l2_review_approved_file_edit` |
| `awaiting_human_decision` | reads `summary.txt` and the packet; commits **by hand** or reverts | — | nothing |

Retry stages: `prepare_pending` and, before consumption, a fresh authorization
(`--prepare-supervised-implementation` at `implementer_consent`, since a consent
expires after 60 minutes); `apply_pending` after a write refused before writing
(exit 1); `review_pending` after a ROUND-1 review attempt exited 1, 2 or 4
(`--verify-approved-file-edit --real-reviewer`; in round 2 exit 1 or 4 is terminal, see §9). Terminal stages:
`no_change_proposed`, `implementer_failed`, `implementer_evidence_incomplete`,
`write_needs_inspection`, `workspace_untrusted`, `review_needs_inspection`,
`awaiting_human_decision`.

**Each stage accepts exactly its own flag set.** Any other set, including a
superset carrying another stage's flags, refuses with nothing done, so a flag
always confirms the stage it is typed for.

## 4. Authority rules (unchanged contracts it relies on)

- **Approvals stay human file edits (D-2).** Drafts carry four empty approval
  strings; P1B's authorization draft carries P1B's empty consent. Freezing
  refuses duplicate keys and any change outside the `approval` block, then the
  accepted strict parser decides. The frozen file is the human's exact bytes.
  `PlanApproval`'s "the orchestrator does not write this block" holds.
- **Endpoint authority stays project config (D-1, ALPHA-1A-FU1).** `task-doctor`
  derives the `controlled_review.endpoint` block from the reviewer base URL
  with the reviewer's own httpx parse and the accepted destination check, and
  prints it to paste once per machine. Nothing derives it at run time, which
  would only compare the environment with itself.
- **Single use stays the P1B ledger's.** The coordinator reads
  `implementer-evidence/<run_id>/` for display only; deleting it cannot replay a
  consumed authorization (tested).
- **One config per run.** `task.json` pins the project config's SHA-256; a
  changed config refuses every later step. The standalone commands remain
  available on the frozen artifacts if a human needs them.
- **No new execution surface.** The runners are called in-process; the only
  subprocesses remain the writer's fixed read-only Git set and the one 5F2D
  verification. The credential-ordering rule holds because the implementer
  stage and the review stage always run in separate invocations (the diff
  approval sits between them).
- **CRLF is refused before prepare.** The writer never normalizes line
  endings and the implementer refuses a proposal whose endings differ, so a
  CRLF working copy (Git's Windows `core.autocrlf=true` default) cannot take an
  LF reply. Check targets out with LF. The check (`task/preflight.py`) reuses
  the implementer's own read-only source read, so it cannot drift from what
  prepare reads; the CLI itself still never imports the P1A offline runner's
  module.

## 5. Run directory and evidence

```text
<runs_root>/<UTC-time>-<8 hex>/
  task.json                     inputs + pinned config digest      (AIDO, write-once)
  10-plan.draft.json            plan + empty approval              (human edits approval)
  11-plan.approved.json         frozen human bytes                 (AIDO, write-once)
  20-authorization-<n>.json     P1B draft                          (human edits consent)
  implementer-evidence/<run_id>/  P1B's own evidence
  30-proposed.diff              the diff to read                   (AIDO, write-once)
  30-diff.draft.json            approved-diff-proposal.v2 + empty approval
  31-diff.approved.json         frozen human bytes                 (AIDO, write-once)
  steps/NN-<step>.exit-<c>.stdout|.stderr   exact runner output    (AIDO, write-once)
  summary.txt                   DERIVED, labeled not-evidence      (AIDO, write-once)
```

The review packet is the review step's `.stdout`, exactly as the accepted
command emitted it. `summary.txt` separates AIDO-observed facts (write report,
embedded verification) from reviewer-model claims, and its readiness line is a
fixed mapping of the verification outcome and the verdict, not a judgment. The
raw reviewer model response is still not retained (5F2E design); keeping it
would be a separate contract change.

`runs_root` defaults to `%LOCALAPPDATA%\AIDO\runs` and is resolved to its
canonical path (P1B requires a canonically named evidence directory). It must
be outside the workspace and, per P1B, disjoint from the authorization ledger.

## 6. What `task-doctor` reads

It reports one `[OK]`/`[FIX]` line per gate a task needs, and exits 1 if any
needs fixing:

- `read_only_workspace_content.enabled: true` — the implementer's prepare step
  reads the one target through the 5D2 bounded read-only content read, which
  refuses without this opt-in (it ships disabled, and an absent block is the
  same as `enabled: false`);
- `workspace_write.enabled`;
- `controlled_verification` enabled with an existing absolute executable;
- the live `supervised_implementer` gate and an existing ledger directory;
- the `controlled_review` gate, and its `endpoint` matching the environment.

`task-start` refuses the same project-config gates (all but the environment
and filesystem checks) **before** it creates a run directory, so a config that
cannot reach prepare never gets as far as a human plan approval or an
authorization (ALPHA-2A-T3; before it, a missing `read_only_workspace_content`
block surfaced only at prepare, after the plan was approved). Prepare still
enforces it itself; the earlier check grants nothing.

The project config; exactly one environment value, the configured reviewer
provider's base URL name; the *presence* of its key name (never the value);
and, with `--target-path`, the workspace through the writer's read-only Git
preflight. It prints the endpoint's scheme, host, port and base path because
a human must paste them, and refuses a base URL with userinfo, a query or a
fragment without echoing it. It writes nothing.

## 7. Verification and the live acceptance run

Offline: `tests/test_task_coordinator.py` covers the end-to-end path through
all four pauses, per-stage flag refusals, unfilled, paraphrased and tampered
approvals, duplicate keys, byte-exact freezes and step records, ledger-owned
single use, a fresh authorization, no-change and failed implementer outcomes,
write and review retries, a dirtying verification, a runner that raises, the
pinned config, the CRLF refusal, start-time refusals, read-only status, the
absence of process/socket/client imports, and the doctor's derivation and
read set.

ALPHA-2A-T3 adds the `read_only_workspace_content` checks: the doctor's
missing, disabled and enabled reports, and `task-start` refusing a missing or
disabled block without creating a run.

Live acceptance (**performed as ALPHA-2A-T2 and ACCEPTED by the Product Owner**;
run `20261110T181352Z-e7cc70f6`, reaching `awaiting_human_decision`; the human
decision is recorded outside the run directory, which the coordinator never
rewrites, in the acceptance area's append-only `human-decisions.log`). It was
planned as: one small
single-file task on a disposable LF clone of a non-AIDO target (an AIDO clone
hits the editable-install shadowing hazard HB-1). Before it, confirm that
`qwen3.8-27b` is served on the current LiteLLM endpoint. Expected: the four
pauses; `diff_proposed`, then `written-and-verified`, then `review-packet.v5`;
one run directory holding every record; HEAD unchanged with exactly one
unstaged change; no commit or push.

## 8. Deferred

Model-backed planning, multi-file tasks, an automatic fixer or any
review/fix loop beyond §9's one human-initiated round, raw reviewer-response
retention, terminal approval capture, an implementer other than SUP-D, config
writing, HTTP transport security review before team use, and DL-4B/E-12 for
multi-user deployment.

## 9. ALPHA-2B-T1 — one human-supervised bounded correction round

Status: **IMPLEMENTED, offline-tested only, awaiting independent review.** No
live correction round has been run or is authorized. Baseline `0ebd9f65`.

Product Owner decisions (accepting ALPHA-2B-D1 Option C):

- **PO-1, governance exception.** Exactly ONE human-initiated correction round
  after an eligible round-1 result. A reviewer verdict may make a correction
  *available*; it never authorizes a model call, a write or an approval.
- **PO-2, implementer request extension.** The supervised implementer request
  may carry one optional, bounded `correction` data object: the previous
  approved diff, AIDO-observed verification facts and, for
  `changes_requested`, the reviewer's findings, all labelled untrusted data.
  Round 2 needs a NEW, independently consented, single-use authorization.
- **PO-3, human restoration.** The human restores the target to its Git
  baseline between rounds. AIDO never restores, and it verifies the clean
  tree, the round-1 HEAD and the round-1 source bytes itself before it
  prepares the round-2 authorization.

### 9.1 Eligibility

A correction is **offered** (stage `correction_offered`) only after round 1,
and only when the recorded evidence cross-checks (§9.3) and either:

- the review exited 0 with a valid packet whose verdict is `changes_requested`; or
- the review exited 2 with a valid `verification-failed` report whose
  postconditions say the workspace is still provably the approved state.

It is never offered for `approve`, `needs_human_review`, a workspace-untrusted
result (exit 3), a reviewer failure or stall (exit 4), a refusal (exit 1) or a
malformed or mismatched record; those keep their Alpha 2A stages, and the stage
message says why nothing is offered. At an offer the human chooses:

| Flags | Effect |
|---|---|
| `--begin-correction-round` | writes `40-correction.json` (the decision plus digests of every round-1 record it relies on) and prints the restore instruction. Sends, writes and approves nothing. |
| `--decline-correction` | writes `40-correction.declined.json`; terminal `awaiting_human_decision`. |
| `--verify-approved-file-edit --real-reviewer` | (exit-2 offers only) the unchanged Alpha 2A review retry. |

### 9.2 Round 2

```text
round2_restore_pending      the HUMAN runs: git restore -- "<target>"
                            ('git restore' DISCARDS the uncommitted round-1 candidate;
                            its records stay in the run directory)
  --prepare-supervised-implementation   P1B prepare WITH the correction (offline)
round2_implementer_consent  the human fills 'consent' in 50-authorization-<n>.json
  --transmit-approved-source --real-implementer   ONE request: original file + correction
round2_diff_approval        the human reads 60-proposed.diff, fills 60-diff.draft.json
  --apply-approved-plan --write-approved-file --verify-approved-file-edit --real-reviewer
round2_awaiting_human_decision | round2_verification_failed     (terminal; summary-r2.txt)
round2_review_failed | round2_evidence_inconsistent             (terminal; human inspection)
```

Round 2 regenerates the **complete** final file from the ORIGINAL baseline:
`current_file_text` is the baseline, the previous candidate is context only,
and `60-proposed.diff` is the whole change against the baseline. The writer,
verifier, reviewer, RS1 supervision, the P1B ledger and the authorization
schema are unchanged. Every round-2 outcome is terminal: there is no third
round, no retry after a completed verdict, and a round-2 verification failure
does not reopen the review retry. Only a **pre-write** writer refusal (apply
exit 1) keeps its Alpha 2A retry within round 2. A completed round-2 review
step that exited 1 or 4 is **terminal** (`round2_review_failed`): the reviewer
is never invoked again for round 2, no valid review is claimed, the change
stays written and unreviewed, and a human inspects. (ALPHA-2B-T1-FU1; round 1's
`review_pending` retry is unchanged.)

**Terminal evidence is validated, not inferred.** On every status read, before
`round2_awaiting_human_decision` or `round2_verification_failed` is reported,
AIDO strictly parses the recorded round-2 write report and review packet (exit
0) or verification report (exit 2) and binds them to round 2's frozen diff
approval, the original baseline, the target and the post-image size; the
review step must follow the write; the postconditions must be trusted; a
packet requires `verified`, a verification failure requires
`verification-failed`. Anything absent, malformed, mismatched or changed gives
the terminal `round2_evidence_inconsistent` (human inspection, nothing more
runs). The derived `summary-r2.txt` is not consulted and not authority.

**Byte-exact integrity of the round-2 write and review records
(ALPHA-2B-T1-FU2).** When AIDO records an `apply-r2` or `review-r2` step it
also creates, exclusively and last,
`steps/NN-<step>.exit-<code>.integrity.json`, holding the step name, sequence,
exit code and the SHA-256 and length of the exact stdout and stderr bytes.
Terminal consumption recomputes both and requires an exact match, so a
schema-valid, identity-preserving edit of the reviewer verdict, summary or
findings, the write report or the verification report is detected on the next
status read. A missing, partial, unreadable or disagreeing integrity record
(for example after an interruption) gives `round2_evidence_inconsistent`:
nothing more runs, no model is called and nothing is written. Round 1 records
get no integrity record.

**Crash-safe attempt accounting (ALPHA-2B-T1-FU3).** Before the coordinator
invokes a round-2 apply or review runner, it durably creates (exclusive,
fsynced) `steps/<step>.begun-NN`. If it cannot, nothing is run. After that, a
crash at any point (before the reviewer request, during it, or before the step
record is complete) leaves a begun marker with no complete record. Every
begun attempt must be matched by exactly one complete stdout+stderr record, and
every record by a marker; any mismatch gives the terminal
`round2_attempt_incomplete` (no actions, human repository inspection, treat the
change as possibly written and the diff as possibly sent). A completed, safely
refused round-2 write (apply exit 1 with a valid integrity record) is still
retryable; a round-2 review exit 1/4 is still terminal. Round 1 writes no
markers. A round-2 run begun before FU3 has records without markers and is
refused as incomplete.

**The accounting is checked FIRST.** It runs before any nonterminal round-2
stage can offer a draft, an approval, an apply or a review, so a begun attempt
cannot be made executable again by losing the evidence it consumed. Once any
round-2 attempt trace exists (a begun marker or any round-2 apply/review step
file), a missing `60-diff.draft.json` or `61-diff.approved.json`, a missing
round-2 authorization draft, or a missing round-2 implementer evidence
directory all give the same terminal `round2_attempt_incomplete`. Before any
attempt begins, none of this applies, and a pre-write refusal retry (which
keeps `61-diff.approved.json`) is unchanged.

**Limit:** the digests live in the same operator-controlled run directory as
the bytes they cover. They detect accidental, partial and content-only edits,
not a deliberate actor who can rewrite both a step file and its integrity
record; there is no signature, key or ACL. Treat the run directory as
trusted-operator storage.

### 9.3 Evidence provenance and binding

- The correction is built **only from recorded evidence**: the round-1
  consumed authorization (its evidence copy must equal the draft the human
  completed), the frozen round-1 diff approval (it must be this run's
  proposal with only the approval filled in, and its pre-image must be the
  baseline), the round-1 write report, and the round-1 review record, which
  must follow that write and name the same approval, target and post-image
  size. The verdict and findings are parsed from the recorded packet.
- `40-correction.json` pins those records' SHA-256 digests and an evidence
  digest. The round-2 prepare and run rebuild the evidence and refuse any
  difference (`round2_correction_evidence_mismatch`, terminal).
- P1B's `_derive` checks the correction's baseline (target path, source
  digest and size, HEAD) against what it observes on a clean tree, at both
  prepare and run, and refuses any mismatch (`correction_baseline_mismatch`)
  before an issuance record or a request exists. The correction enters the
  request, so the authorization's `request_sha256` binds it: a missing,
  changed or added correction refuses as `authorization_mismatch`, unconsumed.
- Before consent is offered, and again before the run, the round-2 draft must
  repeat round 1's role, candidate, model, provider, project, repo, issue,
  plan and config digests, target, change type, source digest and size, HEAD,
  Git state, and evidence and ledger directory digests, and must differ in
  `run_id`, `issuance_sha256`, `binding_sha256` and `request_sha256`. Anything
  else is `round2_correction_baseline_mismatch` (terminal). A consumed
  round-2 run must not be round 1's run and must record the same
  authorization bytes, or it is `round2_evidence_inconsistent`.
- The transmission copy is redacted with the shared secret-like redactor and
  has literal workspace-path spellings replaced by `<workspace>`; P1B refuses
  a correction that still names the workspace. The original evidence is never
  modified. Redaction is a backstop, not a guarantee.
- Round 2's records have their own names (`50-`, `60-`, `61-`, `-r2` steps,
  `summary-r2.txt`). A frozen diff approval is re-checked against its own
  round's draft on every use, so a round-1 approval cannot authorize the
  round-2 write. Any correction record without the round-1 result it needs, or
  both a begin and a decline record, is `correction_records_inconsistent`
  (terminal).

`summary-r2.txt` is the derived final summary. It separates round-2
AIDO-observed facts (including the workspace state as last observed at the end
of round-2 verification) from reviewer-model claims, says round 1 was
superseded, and never claims the correction succeeded because a model
proposed new code. `summary.txt` from round 1 is kept and does not block it.

Offline tests: `tests/test_task_correction_round.py`, alongside the unchanged
Alpha 2A suite in `tests/test_task_coordinator.py`.
