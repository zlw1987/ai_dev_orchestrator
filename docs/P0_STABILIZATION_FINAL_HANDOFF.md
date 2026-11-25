# P0-STABILIZATION-FINAL — handoff for independent review

- **Baseline:** `76f6ccb54df27257caa8240dbc74ac0ba84b7bc3` (main, clean at start).
- **State:** implemented and tested **offline only**. Nothing is committed,
  pushed, installed or promoted. No live model request was made. No production
  workspace and no historical evidence were touched. `CLAUDE.md` is not edited.
- **Contract text:** policy §15 (STB-1..5) and coordinator §12.

## 1. What changed

| File | Change |
|---|---|
| `src/ai_dev_orchestrator/review/reviewer.py` | `run_controlled_review(..., on_verification_passed=None)`. It is called once with the verifier's own report object, right after the verifier returns `verified` and **before** `read_env`. Nothing else changes. |
| `src/ai_dev_orchestrator/cli.py` | `_run_l2_review_approved_file_edit` keeps that object. On exit 4 it prints the report on stdout with `_echo_json_model`, the serializer exit 2 and 3 use, and adds one stderr line (`VERIFICATION EVIDENCE PRESERVED ... NOT a review packet`). On an unexpected exception it prints the report and re-raises unchanged. `_run_task_continue` passes the pinned `ProjectConfig` to `correction_input`. |
| `src/ai_dev_orchestrator/task/run.py` | `preserved_verification_problem()` and `_preserved_verification_note()` are display only. The exit-4 `review_pending` and `round2_review_failed` messages now say whether the step's stdout holds a report attributable to that attempt. No stage, action or exit mapping changed. |
| `src/ai_dev_orchestrator/supervised_implementer/correction.py` | `local_path_redaction_table()` covers the workspace, the verification executable and argument directories, and the user-profile root. The scrubber is driven by it. There is a new `local_path_replacements` count, a new `redaction_note` wording, schema `supervised-implementer-correction.v2`, and `correction_mentions_local_path()`. |
| `src/ai_dev_orchestrator/supervised_implementer/live.py` | `_check_correction` also refuses `correction_contains_local_path`, at both the prepare and the run boundary. |
| `src/ai_dev_orchestrator/task/correction.py` | `correction_input(evidence, project)` takes the pinned config, so the prepare and the run derive identically. |
| `tests/test_p0_stabilization_final.py` | New: 23 tests. |
| `tests/review_fixtures.py`, `tests/test_cli_l2_review_{approved_file_edit,structured_output,supervision}.py` | 9 assertions of an **empty** exit-4 stdout now assert the new contract instead: a `verified` report and not a packet. That is the deliberate contract change. |
| `tests/test_task_correction_round.py` | One helper call updated to the new `correction_input(evidence, project)` signature. |
| `tests/test_p0_model1_model_choice.py`, `tests/test_review_egress.py` | Three more empty-exit-4-stdout assertions now assert the new contract. They were found by the full run. |
| `tests/test_dl4b_s4_verification_claim.py`, `src/ai_dev_orchestrator/integration/claim_readers.py` | DL-4B's claim reader takes stdout bytes without the exit code. It **already refused** a bare `verified` report, so the exit-4 stdout is still no claim. Behavior is unchanged: `VerificationClaimRefusedError`, and nothing is recorded. Only the refusal category moves from `empty` to `unexpected_shape`. The test, the docstring and that one message are updated. |
| `docs/AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md` | §15 amendment (STB-1..5) and the recommended pilot configuration. |
| `docs/ALPHA_2A_TASK_COORDINATOR.md` | New §12 (root cause, fix and limits for FU-A and FU-B); the §9.3 redaction bullet is updated. |

## 2. FU-A — verification evidence independent of the reviewer outcome

**Root cause.** `run_controlled_review` returns the verification report only
in two places: inside a packet, or alone for a non-`verified` outcome. Every
reviewer-stage failure after a `verified` verification raised
`ReviewerStageError`, which took the report with it:

- a stall (`LLMTimeoutError` or AIDO's deadline);
- a transport, HTTP or provider error;
- an unusable or malformed reply, including after the compact retry;
- an egress refusal;
- an environment error;
- a packet assembly error.

The CLI then exited 4 with an empty stdout. The coordinator recorded that empty
stdout, which is exactly what P0-M3-LIVE-1 round 2 shows.

**Fix (smallest, existing architecture).**
- **The report is handed to the caller.** A callback hands the caller the very
  object the packet would have embedded. No new schema and no wrapper are
  added. The report is not reconstructed: the tests compare exit-4 stdout
  byte-for-byte with the serialization of the object the library handed over.
- **One stdout rule.**
  - exit 0: a review packet;
  - exit 2, 3 or 4: the verification-result report;
  - exit 1: nothing.

  Successful-packet consumers are unaffected. Exit 4 still has **no packet**,
  and stderr says so.
- **Ordering is unchanged.** The callback runs after `verified` and before
  `read_env`, so no reviewer credential exists in the process at that point.
- **Exit semantics are unchanged.** RS1 bounds, the terminal stall, strict
  parsing and correction eligibility (exit 0 `changes_requested` or exit 2)
  are all unchanged. In the coordinator, round 1 exit 4 is still
  `review_pending` with the review flags only, and round 2 exit 4 is still the
  terminal `round2_review_failed`.
- **Attribution.**
  - The step record binds the attempt: its sequence, plus the integrity and
    begun-attempt records in round 2.
  - The coordinator checks that the report follows the round's write, names
    the round's frozen approval and target, matches the written post-image
    size and re-established the workspace state.
  - The verifier itself proved the exact `post_image_sha256` before and after
    execution.
  - The report carries no digests by 5F2D design, and this is stated, not
    papered over.

## 3. FU-B — configured local paths in the correction copy

**Root cause.** `_Scrubber` replaced only `repo.workspace_path` spellings. The
verification script is configured **outside** the workspace, so its absolute
path went out in every traceback frame, along with the Windows account name.

**Fix.** The trusted `controlled_verification.executable` and `args` now feed
the scrubber. The table (coordinator §12.2) replaces these **directories**:

| Directory | Becomes |
|---|---|
| the workspace | `<workspace>` |
| the executable's directory | `<verification-executable-dir>` |
| each drive-absolute argument's directory, or that of a `--name=<path>` value, when outside the workspace | `<verification-arg-dir>` |
| the `X:\Users\<account>` root of any of those | `<user-profile>` |

- **Spellings.** Each is replaced in its backslash, forward-slash and
  doubled-backslash forms, of both `abspath` and `realpath`, case-insensitively,
  longest first.
- **What stays.** File names, relative paths, line numbers, test names, inputs
  and exception text all remain.
- **What is never replaced.** Drive roots and `X:\Users` itself.
- **Boundary check.** The P1B boundary refuses any surviving spelling as
  `correction_contains_local_path`.
- **Local evidence** is byte-unchanged.

**Authorization binding.** The prepare and the run call the same function with
the same pinned config, and the request digest binds the result.

- **A stale authorization is refused.** A round-2 authorization prepared under
  the earlier derivation is refused by P1B as `authorization_mismatch`, before
  consumption, with nothing sent. A fresh prepare and consent are then
  required, and they succeed (tested).
- **A begun correction stays valid.** `40-correction.json` pins the raw
  evidence, so it does not have to be redone.

## 4. Tests and results

See `evidence/` in the package. Commands, run with the project venv
(`.venv\Scripts\python.exe`, Python 3.14):

```text
python -m pytest -q -p no:cacheprovider tests/test_p0_stabilization_final.py
python -m pytest -q -p no:cacheprovider tests          (full regression, once)
```

| Run | Result | Evidence |
|---|---|---|
| Full regression, once (`tests`, 1 h 54 min) | **6199 passed, 10 failed**. All 10 asserted the old empty exit-4 stdout. 6 are in `test_review_egress.py` (one parametrized test with 5 cases, plus one more test), 3 in `test_p0_model1_model_choice.py` (one test, 3 cases), and 1 in `test_dl4b_s4_verification_claim.py`. | `evidence/full-suite.txt`, `evidence/full-suite.junit.xml` |
| Re-run after updating those assertions: the 4 affected files in full, plus `tests/test_dl4b_s5_review_evidence.py` (which also reads review claims) and the new test file | **345 passed, 0 failed** (34 min) | `evidence/rerun-affected.txt`, `evidence/rerun-affected.junit.xml` |
| New tests alone (`tests/test_p0_stabilization_final.py`) | **23 passed** | `evidence/new-tests.txt`, `evidence/new-tests.junit.xml` |

- **Full run timing.** The full run started before the last three new tests
  were added. Those three are in the two later runs.
- **Failures vs. edits.** Every full-run failure is accounted for by a changed
  assertion, and no source was changed after the full run except the DL-4B
  docstring and refusal-message text in `claim_readers.py`. That module's own
  suites (S4, S5) were re-run in full.
- **Not re-run.** The full suite was not repeated, because the post-run edits
  touch only assertions and one message string.

**What the new tests show** (`tests/test_p0_stabilization_final.py`):

| Requirement | Test(s) |
|---|---|
| verified then successful review: stdout is only the packet, which embeds the handed-over report | `test_fu_a_a_verified_review_still_prints_only_the_packet` |
| verified then reviewer timeout: exit 4, the original report byte-exact on stdout, `REVIEW STALLED` | `test_fu_a_a_reviewer_timeout_keeps_the_original_verification_report` |
| verified then malformed reply (plain text, fenced JSON): exit 4, one request, report preserved | `test_fu_a_a_malformed_reply_keeps_the_original_verification_report[*]` |
| verified then transport error | `test_fu_a_a_transport_error_keeps_the_original_verification_report` |
| verified then egress refusal: exit 4, report preserved, no transport built (the smoke plan's zero-request check) | `test_fu_a_an_egress_refusal_keeps_the_report_with_no_transport_built` |
| failed verification: exit 2, no reviewer environment read, no transport built, no callback | `test_fu_a_a_failed_verification_never_reaches_the_reviewer` |
| unexpected internal error: propagates, report still printed | `test_fu_a_an_unexpected_error_after_verification_propagates_with_the_report` |
| the report is handed over before any credential is read; it is the same object as in the packet | `test_fu_a_the_library_hands_over_the_report_before_any_credential_is_read` |
| bound to the attempt; round 1 stays retryable and correction-ineligible; the earlier record is untouched by a retry | `test_fu_a_a_round1_stall_preserves_attributable_evidence_and_stays_retryable` |
| round 2 stays terminal; tampering is caught by the integrity record | `test_fu_a_a_round2_stall_is_terminal_with_attributable_evidence` |
| a record naming another approval, or a pre-FU-A empty record, is not attributed | `test_fu_a_an_exit4_record_naming_another_approval_or_empty_is_not_attributed` |
| synthetic reproduction of the observed 13× script-path disclosure; account name and paths removed; details kept | `test_fu_b_the_observed_script_path_disclosure_is_removed_and_details_kept` |
| end to end: the **actual serialized outbound round-2 request** has no script, executable, workspace or profile path in any spelling; the original evidence holds the path at least 13 times and is byte-unchanged; the payload equals the deterministic derivation | `test_fu_b_the_outbound_correction_request_carries_no_configured_local_path` |
| an authorization prepared under the old derivation is refused, nothing is sent, and a fresh prepare and consent succeed | `test_fu_b_an_authorization_prepared_under_the_old_derivation_is_refused` |
| the P1B boundary refuses a copy still naming a local path | `test_fu_b_the_live_boundary_refuses_a_copy_that_still_names_a_local_path` |
| no over-reach, determinism, no mutation of inputs, arguments inside the workspace, `--x=<path>` arguments | `test_fu_b_paths_the_configuration_does_not_name_pass_through_unchanged`, `..._drive_roots_...`, `..._inside_the_workspace_...`, `..._option_value_...`, `..._deterministic`, `..._never_mutated` |
| the recommended pilot config passes both gates; `SUP-D` stays selectable; no default names a pilot model | `test_the_recommended_pilot_configuration_passes_both_gates` |

**Existing behavior, covered by the unchanged suites in the full run:**

| Behavior | Suites |
|---|---|
| H2 (single confirmation and legacy typed) | `tests/test_task_approve_single_h2.py` (48), `tests/test_task_approve.py` |
| `SUP-D`/`SUP-M3` identity and selection | `tests/test_supervised_implementer*.py` |
| reviewer selection, egress and strict parsing | `tests/test_cli_l2_review_*.py`, `tests/test_review_*.py` |
| the correction round | `tests/test_task_correction_round.py` |
| the coordinator | `tests/test_task_coordinator.py` |

No test or source in the P0-UX-H2-SIMPLE area was modified.

## 5. H2 remains intact

No file in the H2 implementation changed: `task/approve.py`, `models.py`,
`supervised_implementer/live_authorization.py` and the endpoint pin code paths
in `live.py` are untouched. The only `live.py` change is one additional
refusal inside `_check_correction`, which runs only for a round-2 correction.
The full run includes `tests/test_task_approve_single_h2.py` and
`tests/test_task_approve.py` unchanged.

## 6. Contract clarification

- **Exit-4 stdout (STB-1).** Previously exit 4 emitted nothing on stdout. It
  now emits the verification report. This is the one consumer-visible change.
  The **"exits 4 with no packet"** statements in `CLAUDE.md` remain literally
  true.
- **Suggested `CLAUDE.md` sync, not made.** `CLAUDE.md` says nothing about
  exit-4 stdout or about verification-config path redaction. Suggested one-line
  sync, for the PO to authorize:
  - under the reviewer section: "Exit 4 prints the verification report AIDO
    produced (never a packet) on stdout";
  - in the correction-round section: "the transmission copy also replaces
    configured verification directories and the user-profile root".
- **Correction schema bumped.** The in-memory correction schema moved to
  `supervised-implementer-correction.v2`, because it gained a field and its
  `redaction_note` changed. It is never persisted as authority. Existing round-2
  authorizations refuse rather than reinterpret (STB-5).

## 7. Remaining material limitations

**Redaction (FU-B)**
- FU-B is configuration-derived, not DLP. These pass through:
  - another drive, a UNC path, an 8.3 short name (`NAME~1`), or a temp
    directory outside the profile;
  - a bare account name in prose;
  - a path that a verification child prints from its own environment.
- Matching is by substring. A configured directory also matches the prefix of
  a longer sibling name (for example `...\suite` inside `...\suite2`). That
  over-redacts; it never leaks more. This is the same as the pre-existing
  workspace rule.
- The **reviewer** request (5F2E `build_review_context`) is unchanged. Its
  verification output is redacted by its accepted rules only, so verification
  paths may still reach the reviewer model. That is outside this assignment.

**Verification evidence (FU-A)**
- The report carries no digest of the diff or the post-image (5F2D).
  Attribution is by identity fields, the frozen approval and the step record.
- A Ctrl-C (`KeyboardInterrupt`) during the reviewer wait is not caught. There
  is no step record in the coordinator, as before.
- Historical P0-M3-LIVE-1 records are unchanged. Their exit-4 stdout stays
  empty, and the coordinator now labels such a record "recorded by an AIDO
  version before FU-A".

**Unchanged operational issues**
- The Qwen 3.8 non-streaming ~300 s cutoff in the serving path.
- The 60-minute H2 TTL.

## 8. Recommended pilot configuration (prospective, not a default)

```yaml
controlled_review:
  enabled: true
  provider: litellm
  model: gpt-oss-20b
  endpoint: {scheme: <scheme>, host: <host>, port: <port>, base_path: <path>}  # from task-doctor
  attempt_timeout_seconds: 300
supervised_implementer:
  enabled: true
  live_transmission_enabled: true
  candidate: SUP-M3
  model: minimax-m3
  provider: litellm
  output_envelope: delimited_file
  structured_output: false
  attempt_timeout_seconds: 300
  authorization_ledger_dir: <%LOCALAPPDATA%\AIDO\ledger>
  endpoint: {scheme: <scheme>, host: <host>, port: <port>, base_path: <path>}  # pin = one-confirmation H2
  # allow_insecure_http: true   # only if the pinned scheme is http
```

## 9. Shortest installation and live smoke-acceptance plan (each step separately authorized)

1. **PO: commit.** The PO reviews and commits; the installer takes the
   committed `HEAD` only.
2. **Install side by side.** Do not promote.
   - `py -3.14 -I deploy\windows\install_aido.py install --venv %LOCALAPPDATA%\AIDO\venv-stab-<sha7>`
   - then `... check --venv ...`
3. **Run the offline acceptance on the installed venv.**
   - `run_installed_acceptance.py --venv ... --pytest-site ...`
   - plus `tests/test_p0_stabilization_final.py`
4. **Run one live task in a NEW disposable repo** with the §8 configuration:
   - `task-doctor`, `task-start`;
   - H1 via `task-approve`;
   - H2 as **one** confirmation via `task-approve`;
   - implementer `SUP-M3`;
   - H3;
   - write, verify and review with `gpt-oss-20b`.

   Acceptance means:
   - single-approval H2 worked;
   - the write was verified;
   - the reviewer produced a packet or exited 4;
   - if it exited 4, `steps/NN-review.exit-4.stdout` holds the `verified`
     report and `task-status` says it is attributable.
5. **FU-B live check (only if round 1 is correction-eligible).** If the
   human begins the correction round:
   - inspect the round-2 request evidence in
     `implementer-evidence/<run_id>/` for absence of the verification-script
     directory and of `Users\<account>`;
   - the round-1 records keep the raw paths.

   FU-B is otherwise proven offline only.
6. **Optional, with no model request: exercise FU-A live.** Run the
   standalone `l2-review-approved-file-edit` against a **copy** of the config
   whose `controlled_review.endpoint` deliberately mismatches the environment.
   - Expected: verification runs, then exit 4 `reviewer-egress-refused` with
     **no network request**, and the report on stdout.

Then close the supervised single-file Personal Alpha stabilization work.
