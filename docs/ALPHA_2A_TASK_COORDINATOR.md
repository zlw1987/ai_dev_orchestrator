# ALPHA-2A-T1 — Single-File Task Coordinator

Status: **ACCEPTED — Personal Alpha 2A Live Integrated Acceptance.** The
Product Owner accepted the ALPHA-2A-T2 live run `20261110T181352Z-e7cc70f6`
(§7). The ALPHA-2A-T3 preflight correction (§6: `task-doctor` and `task-start`
now check `read_only_workspace_content`) is implemented and **independently
reviewed and ACCEPTED**.

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
(exit 1); `review_pending` after a review attempt exited 1, 2 or 4
(`--verify-approved-file-edit --real-reviewer`). Terminal stages:
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

Model-backed planning, multi-file tasks, a fixer or review/fix loop, raw
reviewer-response retention, terminal approval capture, an implementer other
than SUP-D, config writing, HTTP transport security review before team use,
and DL-4B/E-12 for multi-user deployment.
