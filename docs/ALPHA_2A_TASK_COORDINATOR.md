# ALPHA-2A-T1 — Single-File Task Coordinator

Status: **ACCEPTED — Personal Alpha 2A Live Integrated Acceptance.** The
Product Owner accepted the ALPHA-2A-T2 live run `20261110T181352Z-e7cc70f6`
(§7). The ALPHA-2A-T3 preflight correction (§6: `task-doctor` and `task-start`
now check `read_only_workspace_content`) is implemented and **independently
reviewed and ACCEPTED**. ALPHA-2B-T1 (§9) adds one human-initiated correction
round; it is implemented and offline-tested only and awaits independent review.
P0-UX1-T1 (§10) adds `task-approve`, the interactive D-2′ approval path; it is
implemented and offline-tested only and awaits independent review.

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
task-approve   show the pending artifact; record approve/reject (P0-UX1, §10)  (runs nothing)
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
| `plan_approval` | decides at `task-approve`, or fills `approval` in `10-plan.draft.json` | `--prepare-supervised-implementation` | freeze plan, CRLF check, `_run_l2_supervised_implementer_prepare` |
| `implementer_consent` | decides at `task-approve` (typing the endpoint), or fills `consent` in `20-authorization-<n>.json` | `--transmit-approved-source --real-implementer` | `_run_l2_supervised_implementer_run`, then writes the diff draft |
| `diff_approval` | decides at `task-approve`, or reads `30-proposed.diff` and fills `approval` in `30-diff.draft.json` | `--apply-approved-plan --write-approved-file --verify-approved-file-edit --real-reviewer` | freeze diff, `_run_l2_apply_approved_file_edit`, then `_run_l2_review_approved_file_edit` |
| `awaiting_human_decision` | reads `summary.txt` and the packet; commits **by hand** or reverts | — | nothing |

Retry stages: `prepare_pending` and, before consumption, a fresh authorization
(`--prepare-supervised-implementation` at `implementer_consent`, since a consent
expires after 60 minutes); `apply_pending` after a write refused before writing
(exit 1); `review_pending` after a ROUND-1 review attempt exited 1, 2 or 4
(`--verify-approved-file-edit --real-reviewer`; in round 2 exit 1 or 4 is terminal, see §9). Terminal stages:
`no_change_proposed`, `implementer_failed`, `implementer_evidence_incomplete`,
`write_needs_inspection`, `workspace_untrusted`, `review_needs_inspection`,
`awaiting_human_decision`, and (P0-UX1) `rejected` / `round2_rejected` and
`decision_record_invalid` / `round2_decision_record_invalid`.

**Each stage accepts exactly its own flag set.** Any other set, including a
superset carrying another stage's flags, refuses with nothing done, so a flag
always confirms the stage it is typed for.

## 4. Authority rules (unchanged contracts it relies on)

- **Approvals and consents are separate human decisions (D-2′, amending D-2).**
  H1 (plan), H2 (implementer consent), H3 (exact diff), and round 2's H2 and H3
  are each one decision about one exact presented artifact, made in one of two
  ways.

  (a) **Interactive (normal).** `task-approve` derives the stage and displays
  the complete artifact on the local terminal, with control, bidi and
  zero-width characters escaped. The human types `approve`, `reject`, or
  anything else, which cancels. For H2, after `approve` the human also types
  the endpoint they expect as `scheme://host:port`, which AIDO never shows or
  prefills. It must match the environment by P1B's own endpoint rules. The
  human then confirms the transmission (`transmit`) and, for `http`, the
  plaintext risk (`plaintext`), each separately.

  Only then does AIDO record a write-once decision, bound to the run, the
  config, the round, the stage and the exact draft bytes displayed. From it
  AIDO generates the block the strict parser requires: the stage's fixed
  phrase, AIDO's clock, `source: "manual"`, the observed local account name
  (not an authenticated identity), and for H2 the bound `binding_sha256`, the
  human-typed endpoint and the plaintext acknowledgement if it was confirmed.
  It does so only inside that stage's own `task-continue`, after re-validating
  the record. `reject` is recorded the same way and ends the task (round 1)
  or the correction round (round 2). Cancel records nothing.

  (b) **Manual (compatible).** The human edits the block of AIDO's draft, as
  before; freezing refuses duplicate keys and any change outside the block, and
  the frozen file is the human's exact bytes. One decision cannot mix (a) and
  (b).

  In both, the unchanged strict parsers and P1B's run-time checks decide. AIDO
  never approves, consents, infers, defaults, pre-selects, carries over,
  reuses or repairs a decision. A decision for one stage, round, run or draft
  never satisfies another. `task-approve` executes nothing; `task-continue`,
  with its unchanged per-stage flags, remains the only executor. A TTY check
  guards only against an accidental scripted approval; it does not prove a
  human is present (A-19).
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
  11-plan.approved.json         frozen human bytes, or serialized from 12- (AIDO, write-once)
  12-plan.decision.json         interactive H1 decision (P0-UX1)   (AIDO, write-once)
  20-authorization-<n>.json     P1B draft                          (human edits consent, or never edited)
  20-authorization-<n>.decision.json   interactive H2 decision     (AIDO, write-once)
  20-authorization-<n>.consented.json  consent serialized from it, consumed by P1B (AIDO, write-once)
  implementer-evidence/<run_id>/  P1B's own evidence
  30-proposed.diff              the diff to read                   (AIDO, write-once)
  30-diff.draft.json            approved-diff-proposal.v2 + empty approval
  31-diff.approved.json         frozen human bytes, or serialized from 32- (AIDO, write-once)
  32-diff.decision.json         interactive H3 decision (round 2: 62-) (AIDO, write-once)
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

(P0-MODEL-1 removed "an implementer other than SUP-D" from this list. A project
may now name the separately identified `SUP-M3` = `minimax-m3` instead. The
coordinator itself is unchanged; see policy §13.)

Model-backed planning, multi-file tasks, an automatic fixer or any
review/fix loop beyond §9's one human-initiated round, raw reviewer-response
retention, config writing, HTTP transport security review before team use, and DL-4B/E-12 for
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
  completed, or the `.consented.json` copy serialized from an interactive
  decision), the frozen round-1 diff approval (it must be this run's
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

## 10. P0-UX1-T1 — interactive human approval (D-2′)

Status: **IMPLEMENTED, offline-tested only, awaiting independent review.** No
live run used it. Baseline `dc2222d`. Product Owner: D-2′ accepted, with the H2
rule that the human types the endpoint (DEC-SUP-LIVE A-2 preserved); policy
§11.

```text
ai-dev-orchestrator task-approve --run-dir "<run>"
```

1. **Refusals.** Before showing anything, it refuses unless:
   - the stage is `plan_approval`, `implementer_consent`, `diff_approval`,
     `round2_implementer_consent` or `round2_diff_approval`;
   - stdin and stdout are terminals;
   - the config digest is unchanged;
   - the draft is AIDO's untouched original;
   - no decision exists for it yet;
   - for H2, the authorization is within its validity window.
2. **Display.** It shows the complete escaped artifact and what approving it
   leads to. Workspace, verification and reviewer facts come from the run's
   pinned project config, read from bytes that match the pinned digest; they
   are shown, never granted, and no credential is read (P0-UX1-T1-FU1):
   - **H1:** the configured Windows workspace root, the repository and issue,
     the target (and its on-disk path), the task title, and every plan field.
   - **H2:** the configured workspace and the source scope (exactly one file,
     with its on-disk path), provider, model, the file's size, digest and HEAD,
     what the one request carries (in round 2, including the correction data),
     the request digest, the expiry, and whether plaintext HTTP is permitted.
     The endpoint is deliberately not shown; it is still typed independently.
   - **H3:** the configured workspace, the target and its on-disk path, the
     complete diff with its pre-image and post-image digests, and the three
     consequences of the next step: the write; the configured verification
     (executable, each argument, its wait bound, not sandboxed); and the
     reviewer (provider, model, the configured endpoint's scheme, host and port
     with its TLS state, the request count, and what is sent).
3. **The decision.** Typing `approve` approves and `reject` rejects. Anything
   else cancels, including an empty line, EOF or Ctrl-C.
4. **H2 confirmations, after `approve`.** In order:
   - the human types `scheme://host:port`, with an explicit effective port;
   - AIDO reads exactly `AIDO_LITELLM_BASE_URL`, never the key, and compares
     it with P1B's `check_live_endpoint`. A mismatch is refused without
     revealing the environment's endpoint;
   - on a match, it shows the resolved destination, and the human types
     `transmit`;
   - for `http`, a banner follows and the human types `plaintext`.
5. **Recording.** It re-reads the draft and refuses if its bytes changed since
   they were displayed. It then creates the decision atomically (temporary file
   plus hard link, so it is whole or absent) and prints the next
   `task-continue` command.

At `task-continue`:
- The plan and diff freeze, and the implementer step, re-validate the decision
  before anything else: run, config, round, stage, kind, presented draft
  digest, binding data, timestamps, the consent answers, and the authorization
  window.
- They serialize the block, run the same "only the block changed" check and
  the unchanged strict parser, and write the frozen or `.consented.json` file.
  If the file already exists, they require byte equality, which is how an
  interrupted serialization resumes. A mismatch is refused, never replaced.
- P1B then consumes `.consented.json` and still compares the run-time endpoint
  with the consented one.
- `consumed_authorization` returns the file P1B consumed, so the correction
  round's evidence checks hold for both paths.

A `reject` decision derives the terminal `rejected` (or `round2_rejected`)
stage. A rejection contradicted by later records, and any unreadable or
mismatched decision record, derives the terminal `decision_record_invalid`
(or `round2_decision_record_invalid`) stage. Records are never repaired.

Every authorization-named file of a round is accounted for by its own name,
not reached through a draft (P0-UX1-T1-FU1). The round fails closed if a name
is not one AIDO writes, the drafts are not numbered 1..n, a decision has no
draft, a `.consented.json` has no decision, or more prepare steps succeeded
than drafts exist. So removing a rejected authorization's draft, with or
without its decision, cannot hide the rejection or make an earlier approved
authorization the latest again. A round-2 authorization file before the round
was begun is inconsistent.

Offline tests: `tests/test_task_approve.py`, alongside the unchanged
`tests/test_task_coordinator.py` and `tests/test_task_correction_round.py`.

**Residual limits:**
- The account name is an observation, not an identity.
- A same-account process can forge a decision exactly as it can hand-edit a
  draft (A-19).
- P1B's own expiry check at run time stays the authority.
- `task-doctor` still prints the implementer endpoint values.

## 11. P0-UX-H2-SIMPLE — one-confirmation H2 (opt-in)

Status: **IMPLEMENTED, offline-tested only, awaiting independent review.** No
live run used it. Baseline `7c63544`. Product Owner decision: policy §14
(H2S-1 to H2S-4). §10 is unchanged for every project that does not opt in.

**Opt-in.** Pin the implementer destination once in the project config. It is
the same representation as `controlled_review.endpoint`, and it authorizes
`AIDO_LITELLM_BASE_URL`; it does not replace it:

```yaml
supervised_implementer:
  # ... the existing fields, unchanged ...
  allow_insecure_http: true   # required when the pinned scheme is http
  endpoint:
    scheme: http
    host: gateway.example.invalid
    port: 8080                # always explicit
    base_path: /v1
```

A run is pinned to its config by SHA-256, so a run started without this block
keeps the typed H2 of §10 to its end, and adding the block means starting a new
task. Write the block by hand from the destination you intend; nothing
derives it from the environment.

**What changes at H2.**
1. Before showing anything, `task-approve` reads exactly
   `AIDO_LITELLM_BASE_URL` (never the key) and requires it to be the pinned
   destination: P1B's `check_live_endpoint`, then the reviewer's accepted egress
   comparison on the URL the client will request (scheme, host, effective port,
   exact path `<base_path>/chat/completions`, no userinfo, query or fragment).
   A trailing `/` is the same request and matches. A mismatch, including a
   missing or different `/v1`, refuses with nothing shown or recorded, and the
   URL is never echoed.
2. The screen shows the complete pinned destination, its environment match and
   its TLS state, plus everything §10 already showed. Sample (a synthetic
   offline run; the host is a test value, and digests are shortened here):

   ```text
   H2 IMPLEMENTER CONSENT — run 20261124T185235Z-448a25b5, round 1, 20-authorization-1.json
   workspace:  C:\...\workspace   (configured Windows workspace root)
   source scope: exactly ONE file, src/mod.py — on disk C:\...\workspace\src\mod.py. No other file, listing, tree or git history is sent.
   provider litellm, model qwen3.8-27b (supervised implementer SUP-D)
   WHAT WILL BE SENT, in exactly one model request with zero transport retries (wait bound 30.0 s):
     - the COMPLETE current content of exactly one file: src/mod.py (27 bytes, sha256 747b576e…f4f1f0) at HEAD 3b6f9fd2…c8d47d04
     - the approved plan's prose and AIDO's fixed implementer instructions
   request sha256 eb50a3a3…f198a190d31
   authorization 74930df0…bee93dd801, prepared 2026-11-24T18:52:35+00:00, expires 2026-11-24T19:52:35+00:00 (59 min left), single use

   DESTINATION (pinned by the project config, project_config.supervised_implementer.endpoint):
     http://fake-gateway.invalid:8080/v1
     scheme http, host fake-gateway.invalid, port 8080, base path /v1
     the one request goes to exactly http://fake-gateway.invalid:8080/v1/chat/completions
     environment: AIDO_LITELLM_BASE_URL matches this destination exactly (scheme, host, effective port and path; checked just now, again before your answer is recorded, and again by task-continue immediately before sending)
     transport: NOT TLS-ENCRYPTED (plaintext http)
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !!  PLAINTEXT HTTP: this source will be sent NOT TLS-ENCRYPTED.        !!
   !!  Anyone on the network path can read it. This is not secure.        !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

   Typing 'approve' consents to this ENTIRE transmission as shown above, including sending it NOT TLS-ENCRYPTED. It is the only confirmation. It records the decision only and sends nothing: the transmission happens only when you run task-continue --transmit-approved-source --real-implementer, within the authorization's validity.

   Type 'approve' to approve this implementer consent, 'reject' to reject it, anything else to cancel: approve
   APPROVED: recorded in 20-authorization-1.decision.json. Recording runs nothing: nothing was prepared, sent, written or verified.
   ```

   For `https` the transport line reads `TLS (https)` and there is no banner.
3. The human types `approve` once, or `reject`; anything else cancels and
   records nothing. There is no endpoint, `transmit` or `plaintext` prompt.
4. The environment is checked once more, the draft is re-read, and the
   write-once decision is recorded. Its binding carries
   `confirmation: "single_approval"`, the pinned destination with
   `endpoint_source`, `transport_tls`, `endpoint_matched_environment: true`,
   and `presented_screen` with `presented_screen_sha256`, the exact screen
   shown. It carries no `transmission_confirmed` or `plaintext_confirmed`,
   because nothing of the kind was typed.

**At `task-continue`.** The record is re-validated: run, config, round, stage,
kind, draft digest, every recomputed binding field (now also the candidate and
the pinned destination, from the pinned config), the screen digest and the
authorization window. A record whose shape is not the run's mode is refused.
AIDO then serializes the unchanged P1B consent block: the pinned scheme, host
and port, the fixed consent phrase and, for `http`, the fixed plaintext
acknowledgement phrase. P1B's run additionally checks the environment against
the pinned destination in full (`endpoint_not_authorized`, before
consumption) and keeps its unchanged comparison with the consented scheme,
host and port.

**Round 2.** A correction round in a pinned run uses the same one-confirmation
H2, on its own fresh authorization (`50-authorization-<n>.decision.json`).
Round 1's decision never satisfies it.

Offline tests: `tests/test_task_approve_single_h2.py`, alongside the unchanged
`tests/test_task_approve.py`, `tests/test_task_coordinator.py` and
`tests/test_task_correction_round.py`.

**Residual limits:**
- The host is authorized as text; DNS and routing are not observed, and over
  `http` nothing authenticates the server.
- The recorded screen is the text AIDO printed. It is not proof that a person
  read it (A-19).
- A hand-edited consent (§4 (b)) remains possible in a pinned project; P1B
  still requires the environment to match the pin.
- A malformed pin is refused with the shared validator's
  `controlled_review.endpoint` wording; the error location names
  `supervised_implementer.endpoint`.
