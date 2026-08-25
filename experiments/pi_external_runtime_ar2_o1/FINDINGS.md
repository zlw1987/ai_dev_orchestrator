# O1 Findings

**Status: O1 PASSED.** Offline suite green (65/65). The corrected, capability-
based Pi compatibility gate passed against the actually-installed Pi
`0.84.3`. Exactly ONE semantic prompt was sent, and the model correctly
edited exactly the two required implementation files
(`subscription/normalize.py`, `subscription/rates.py`), with the test
witness untouched, authoritative verification passing 9/9, the broker/Git
cross-check agreeing in both directions, HEAD unchanged, a clean index, and
broker teardown reaching CLOSED.

## 0. History: two invocations of this harness

1. **First invocation** -- inherited AR2's exact Pi-version gate unchanged
   and stopped at `preflight`, before any broker, before any Pi launch,
   before any prompt, because the installed Pi reported `"0.84.3"` against
   an inherited `"0.84.2"` comparison. **This was a harness-policy defect,
   not a model failure and not a runtime incompatibility** -- nothing about
   the actual runtime seam had been exercised yet. Zero semantic prompts
   were sent, and none of O1's one-prompt budget was consumed.
2. **Second invocation** (this one) -- the exact-version gate was removed
   for O1 and replaced with the capability-based compatibility gate
   described below. All prerequisites (offline suite, compatibility gate,
   route/model gate, H1, H2, baseline, broker READY) passed, and the one
   authorized live case was then run.

## 1. Old policy vs. corrected policy

| | Old (first invocation) | Corrected (this invocation) |
|---|---|---|
| What Pi version means | Authorization: `reported == "0.84.2"` or refuse | Provenance: always recorded, never compared |
| Gate mechanism | One string equality check, in `phase_preflight`, before any launch | 13 named, mechanically evaluated checks against the real RPC launch/handshake, in `phase_case`, before any prompt |
| Outcome on a different version | Terminal `LaunchIdentityError`, zero prompts, regardless of actual compatibility | Proceeds if and only if every named check passes against the ACTUAL seam |
| Failure attribution | Generic "version mismatch" | The exact failed capability/behavior name (e.g. `h1_extension_identity_passed`) |
| Where it lives | `ar2.launch.resolve_runtime_identity` (AR2, frozen, unchanged) | `o1.pi_compat` (O1-only; does not import `PINNED_PI_VERSION` from `ar2` at all) |

AR2 itself is untouched: `ar2.launch.PINNED_PI_VERSION = "0.84.2"` and every
R1-R4 historical record remain exactly as they were, and remain truthful
evidence of the Pi version AR2 actually used when it ran. This correction
applies to O1 only, and to the recommended future runtime policy.

## 2. Observed installed Pi version

```
0.84.3
```

Recorded in every O1 record as `pi_runtime.observed_version`, with
`version_recorded_as_provenance: true` and
`exact_version_is_authorization_gate: false`. No `PINNED_PI_VERSION =
"0.84.3"` was introduced anywhere, and no semver range was introduced either
-- `o1/pi_compat.py` contains zero comparison operators against
`reported_version` (asserted by `tests/test_o1_pi_compat.py`).

## 3. Zero-prompt Pi compatibility gate: checks and results

**Correction (5F3A-AR2-O1-FU1):** an earlier version of this section
overstated what the standalone `--phase handshake` run demonstrated,
claiming the complete 13-check gate was "proven twice." That is not
accurate, and the wording below replaces it. The historical `O1` live
result and PASS verdict are unchanged by this correction -- only the
description of what the standalone handshake run, specifically, proved.

The standalone `--phase handshake` run (`o1.handshake.launch_and_handshake`,
via `run_o1.py`'s `phase_handshake`) really did launch the real Pi
`0.84.3` with the real generated extension and exchange real H1
(`get_commands`) / H2 (`get_state`) RPC frames, with no prompt sent. That
run is genuine, independent evidence for: Pi version observability, Node-
direct launch, RPC process launch and JSONL request/response correlation
for both H1 and H2, both response shapes being understood, H1 extension
identity passing, H2 model/provider identity passing, and the launch argv
being accepted. It does **not**, by itself, evaluate `o1.pi_compat`'s
formal 13-named-check `compatibility_checks` dict or call
`build_pi_runtime_provenance` at all -- `phase_handshake` never constructs
that structure. It also does **not** perform the non-inference `/models`
route check (`check_route_serves_model`), because `phase_handshake` never
calls it; that check exists only inside `phase_case`, immediately before
the prompt decision.

So the complete, formally-composed 13-check gate (the exact table below,
including the route check) was evaluated and recorded **once**: inline,
inside the live `--phase case` run itself, immediately before the prompt
decision. The standalone handshake run is corroborating evidence that the
underlying RPC/extension/model seam facts it exercises hold for `0.84.3`;
it is not a second, independent execution of the 13-check gate.

All 13 named checks passed, as recorded by that one `--phase case` run:

| # | Check | Brief item | Result |
|---|---|---|---|
| 1 | `pi_version_observable` | 1 | PASS |
| 2 | `node_direct_launch_constructed` | 2 | PASS |
| 3 | `rpc_process_launched_and_alive` | 3 | PASS |
| 4 | `jsonl_request_response_correlation_h1_worked` | 4 | PASS |
| 5 | `get_commands_response_shape_understood` | 5 | PASS |
| 6 | `h1_extension_identity_passed` | 6 | PASS (sentinel matched, source=="extension", path matched, non-contradictory source origin) |
| 7 | `jsonl_request_response_correlation_h2_worked` | 4/7 | PASS |
| 8 | `get_state_response_shape_understood` | 7 | PASS |
| 9 | `h2_model_identity_passed` | 8 | PASS (`provider=="aido-ar2-qwen36-direct-vllm"`, `model=="Qwen3.6-27B-262K"`) |
| 10 | `required_launch_flags_accepted` | 9, 10 | PASS (the full `--mode rpc --no-session --no-extensions --extension ... --tools aido_read,aido_edit --no-builtin-tools --no-skills --no-prompt-templates --no-themes --no-context-files --no-approve --offline --provider ... --model ...` argv from AR2's own unmodified `build_pi_argv` was accepted; the process reached H1/H2 without an early exit) |
| 11a | `no_protocol_violation_during_handshake` | 11 | PASS |
| 11b | `no_extension_errors_during_handshake` | 11 | PASS |
| 12 | `route_serves_configured_model` | 12 | PASS (non-inference `/models`: `served_model_ids == ["Qwen3.6-27B-262K"]`) |

`compatibility_gate_passed: true`. No semantic prompt was made to test this
-- every check above came from H1 (`get_commands`) and H2 (`get_state`),
neither of which triggers inference, plus the non-inference `/models` check.

## 4. Offline suite

`python -m pytest experiments/pi_external_runtime_ar2_o1/tests -q`

```
65 passed
[ar2-o1] session finish: ar2-owned threads still alive = none
```

30 tests carried forward unchanged from the first invocation (fixture shape,
baseline two-behavior necessity, changed-file budget/witness protection,
prompt/manifest non-disclosure, record identity, scrub reuse), plus 35 new
tests in `tests/test_o1_pi_compat.py` proving, without any real or fake Pi
process:

- an exact version mismatch alone is never a refusal (parametrized over
  `"0.84.2"`, `"0.84.3"`, `"1.0.0"`, `"0.1.0"`, and a non-semver string --
  all pass the gate given passing checks);
- the observed version is always recorded verbatim;
- a version different from AR2's historical pin may proceed
  (`test_a_version_different_from_ar2s_historical_pin_may_proceed`);
- a single failed required check fails the whole gate closed, individually
  proven for **every one** of the 13 named checks
  (`test_every_named_check_is_individually_load_bearing`, parametrized);
- a missing check key (a harness wiring bug) raises rather than silently
  passing;
- no comparison operator against `reported_version` exists anywhere in
  `o1/pi_compat.py`, and AR2's historical pin string is never used as a
  comparison target;
- `o1/__init__.py` and `run_o1.py` do not import `PINNED_PI_VERSION` (AST
  import-name inspection, not a substring grep);
- neither `run_o1.py` nor `o1/pi_compat.py` imports
  `ar2.launch.resolve_runtime_identity`;
- `run_o1.py`'s `phase_case` folds the compatibility gate into
  `gate_all_passed` and only sends the prompt lexically after that guard
  (source-segment position proof, in the same spirit as AR2's own
  `test_root_authority.py` AST checks).

## 5. Compatibility-fails case

Not exercised live in this invocation (the real gate passed), which is the
correct and expected outcome to report truthfully rather than fabricate. The
offline suite instead proves the FAILURE PATH mechanically at the unit
level: `test_a_single_failed_check_fails_the_whole_gate_closed` and the
per-check parametrized test show that any one of the 13 checks being false
makes `compatibility_gate_passed` false, and the `phase_case` source-position
tests show the prompt-send statement is unreachable unless
`gate_all_passed` (which now includes `pi_compatibility_gate_passed`) is
true first.

## 6. The live case

Run: `python run_o1.py --phase case --run-pi-delegated-broker-experiment --send-one-real-model-prompt`

- **Semantic prompts sent this invocation: 1** (`semantic_prompts_sent: 1`,
  `prompt_sent: true`).
- **Total O1 semantic prompts ever sent, across both invocations: 1** (the
  first invocation sent zero, refused at `preflight`).
- **Runtime terminal outcome:** `turn_outcome: "runtime_settled"` --
  `agent_settled` was observed, not merely `agent_end`
  (`agent_end_is_not_completion: true` is recorded alongside it, per AR2's
  own unmodified activity tracking).
- **Runtime-reported tool activity (untrusted claim):** `aido_read` x 6,
  `aido_edit` x 2, zero tool errors.
- **Runtime-reported usage:** input 3821 tokens, output 180 tokens, total
  4001 -- `aido_requested_max_output_tokens: null` throughout; no numeric
  cap was ever sent.
- **Reasoning drop:** 168 reasoning-delta records, 23 reasoning keys and 9
  reasoning blocks dropped at ingestion; none stored, logged, or counted.
- **Broker-accepted operations:** 6 `read_file`, 2 `edit_file`; 0 refused.
- **Broker-recorded mutated paths:** `subscription/normalize.py`,
  `subscription/rates.py`.
- **Orchestrator-observed changed paths (authoritative):**
  `subscription/normalize.py`, `subscription/rates.py`.
- **Cross-check:** agrees in both directions
  (`broker_recorded_but_not_observed: []`,
  `observed_but_not_explained_by_the_broker: []`).
- **Authoritative verification:** `passed: true`, `counts: {"passed": 9}`,
  0 failed.
- **Changed-file budget:** 2 of 2 consumed; `third_file_write_attempted:
  false`; no third distinct file was attempted or refused during the live
  run (the model completed the task with exactly the two necessary edits).
- **HEAD:** unchanged. **Index:** clean. **Untracked paths:** none.
  `workspace_class: "clean_expected"`, `trusted: true`.
- **Route/transport:** `configured_model_served: true`,
  `served_model_ids: ["Qwen3.6-27B-262K"]`, `transport_tls: false`
  (`NOT TLS-ENCRYPTED`, recorded truthfully, matching AR2's own transport
  reality for this route -- unrelated to the version-gate correction).
- **Cleanup:** the disposable fixture and generated extension/model config
  were removed and the removal verified, because the run was fully
  trusted and anomaly-free (`fixture_preserved: false`).

### The two diffs (authoritative, `git diff` via the accepted fixed operation)

```diff
--- a/subscription/normalize.py
+++ b/subscription/normalize.py
@@ -5,6 +5,7 @@ _CANONICAL_TIERS = {
     "std": "standard",
     "pro": "pro",
     "professional": "pro",
+    "enterprise": "enterprise",
 }
```

```diff
--- a/subscription/rates.py
+++ b/subscription/rates.py
@@ -3,6 +3,7 @@
 RATE_CENTS_PER_SEAT = {
     "standard": 900,
     "pro": 2500,
+    "enterprise": 6000,
 }
```

Both diffs are minimal, correct, and touch nothing else. `quote.py` was read
(part of the 6 reads) but never edited, exactly as the fixture's design
intended.

## 7. O1 PASS/FAIL

**PASS.** All 13 case-assessment criteria in `case_assessment` are true:
exactly the two required files changed, no third file, test witness
untouched, verification passed, cross-check agrees, broker teardown CLOSED,
runtime settled normally, no protocol anomaly, no capability anomaly.

## 8. Qualification statement now supported

> Qwen3.6-27B-262K + Pi (observed version `0.84.3`, not `0.84.2`) demonstrated
> a two-file coordinated implementation over the accepted delegated broker
> synthetic capability, under the unmodified accepted two-file changed-file
> cap, with neither implementation file named in the prompt.

This is **not** "production-qualified implementer," **not** "safe for real
repositories," and **not** "production Pi integration." It is also not a
general claim that Pi `0.84.3` is supported -- only that THIS observed
version passed the required compatibility gate for THIS run.

## 9. What remains unproven

- Whether this result generalizes across repeated runs, different task
  shapes, or a third implementation file genuinely required.
- Whether `agent_settled` semantics or the compatibility-gate checks remain
  stable across further Pi upgrades -- each future run re-proves its own
  gate; no version is assumed compatible from this one result.
- Deeper completion-semantics probing (the brief explicitly defers this to a
  future dedicated Pi compatibility suite, not spent as part of O1's one
  prompt).
- Whether the BASIC synthetic implementer corpus is closed by this result --
  that determination is out of scope for this experiment to make for itself
  and should be made conservatively, separately.

## 10. Recommended next step

A third, genuinely-independent case (different domain, different defect
shape) to see whether the two-file result replicates, still under the
unmodified two-file cap and the same capability-based compatibility gate --
rather than assuming this one PASS generalizes.

## 11. FU1 -- Compatibility Failure Lifecycle Closure (offline only)

5F3A-AR2-O1-FU1 is a narrow, OFFLINE-ONLY follow-up. It changed nothing
about the historical live O1 result above (section 6-7): no Pi was run, no
model was called, no network request was made, and O1's live case was not
re-executed.

### 11.1 Defect

In `run_o1.py`'s `phase_case`, the broker is started (and reaches READY)
*before* the launch-and-handshake sequence runs. If that sequence raised --
a Pi launch failure, a stdin/RPC failure, or any other compatibility-seam
exception -- the exception escaped all the way to `main()`'s top-level
`except` tuple *before* the broker had a chance to shut down and before the
disposable fixture could be cleaned up or explicitly preserved as evidence.
The broker thread and any live Pi child could be left in an undefined state
relative to the rest of the harness's bookkeeping.

### 11.2 Fix

The launch-and-handshake sequence was extracted from a private function
inside `run_o1.py` into a proper library function,
`o1.handshake.launch_and_handshake` (new file: `o1/handshake.py`), with the
**exact same body** on the happy path -- no behavior change there. It is
now wrapped in one `try`/`except Exception` block. On ANY exception:

1. if a `PiRpcSupervisor` had already been constructed, its bounded
   `shutdown()` (AR2's own, unmodified) is attempted immediately, and its
   truthful termination record is captured;
2. if a real process existed, `stdout_state()` is also captured (guarded,
   since AR2's own `stdout_state()` asserts a launched process and would
   itself raise otherwise);
3. the original exception's exact class and message, the termination
   record, the stdout state (or `None`), the generated extension directory
   (if any), and whatever partial report fields were already populated are
   packaged into a new `CompatibilityHandshakeError` and re-raised.

`CompatibilityHandshakeError` subclasses AR2's own `PiSupervisorError`, so
`main()`'s existing top-level `except` tuple keeps catching it with **no
change** to that tuple.

`run_o1.py`'s `phase_case` now wraps its call to `launch_and_handshake` in
its own `try`/`except CompatibilityHandshakeError`. On catch: the exception
is recorded verbatim in `run["compatibility_handshake_exception"]`,
`extension_dir` is taken from the exception (so cleanup can still scrub
it), `shutdown_trigger` is set to `TRIGGER_PI_EXITED` only if the captured
termination actually observed an exit status, and -- critically --
`supervisor` is left `None` and is **never reassigned** inside that handler.
Execution then falls through to exactly the same code path `phase_case`
already used for "broker never reached READY": every compatibility check
stays `False`, `gate_all_passed` is `False`, broker shutdown
(`server.shutdown(shutdown_trigger)`) always runs next, and the existing
trusted/untrusted fixture-preservation logic in `main()` applies unchanged
(an unmet case criterion means `no_anomaly` is `False`, so the disposable
fixture is preserved as evidence rather than deleted).

No thread is killed, no retry is attempted, no fallback launch or runtime is
tried, and no claim is made that Pi/provider inference or GPU work stopped
-- only what AIDO itself observed about its own direct child, if one ever
existed.

### 11.3 Injected-failure offline tests

New file: `tests/test_o1_handshake_lifecycle.py` (11 tests), injecting
failures at both points named in the brief, deterministically and offline:

- **Pi launch failure after broker READY** -- `identity.node_executable`
  points at a nonexistent path, so the real `subprocess.Popen` inside AR2's
  own `PiRpcSupervisor.launch()` raises `FileNotFoundError`, wrapped by AR2
  into `PiSupervisorError`. No process is ever created. Proven:
  `CompatibilityHandshakeError` is raised, is a `PiSupervisorError`,
  `original_exception_class == "PiSupervisorError"`; the bounded shutdown
  attempt reports `rung_reached: "none"` and `exit_status_observed: None`
  (truthfully: there was nothing to reap); `stdout_state` is `None`
  (never fetched for a process that never launched); and the `as_dict()`
  claim-scope text explicitly disclaims inference/GPU stoppage, thread
  killing, and fallback.
- **Handshake/RPC failure after Pi process creation** -- a REAL child
  process is launched (`sys.executable` running a tiny script that blocks
  reading stdin and exits 0 on EOF), so `launch()` genuinely succeeds and a
  live process exists. `PiRpcSupervisor.send_command` is then monkeypatched
  to raise `PiSupervisorError("... injected test failure")` on its first
  call (simulating a stdin/RPC failure), deterministically and without
  racing real subprocess timing. Proven: `CompatibilityHandshakeError` is
  raised with the exact injected reason; the REAL child is reaped through
  AR2's own, **unmodified** termination ladder --
  `rung_reached: "exited_after_stdin_close"`, `exit_status_observed: 0`,
  neither `terminate` nor `kill` was sent (the first rung already
  succeeded); `stdout_state` IS populated (a real process existed);
  `extension_dir` is populated and the directory genuinely exists on disk
  (written before the injected failure, so cleanup can still scrub it); and
  the partial report carries no `handshake_extension`/`handshake_model`
  keys (neither handshake ever got a response) while still carrying the
  pre-launch config/argv description.
- Six more tests statically prove `run_o1.py`'s `phase_case` control flow:
  it catches exactly `CompatibilityHandshakeError`; the handler never
  reassigns `supervisor`; the handler never calls `.shutdown()` a second
  time (already attempted inside `launch_and_handshake`); broker shutdown
  is lexically guaranteed to run after the try/except regardless of which
  branch was taken; and the prompt-send guard
  (`gate_all_passed and supervisor is not None`) remains structurally
  unreachable after a caught exception, exactly as it already was for the
  "broker never reached READY" path.

### 11.4 Test count/result

```
python -m pytest experiments/pi_external_runtime_ar2_o1/tests -q
76 passed
[ar2-o1] session finish: ar2-owned threads still alive = none
```

11 new tests (`test_o1_handshake_lifecycle.py`) plus the 65 carried forward
unchanged from before FU1 (fixture shape, baseline, budget/policy,
prompt/manifest, record identity, and the Pi compatibility-policy suite).
Re-run three consecutive times with no flake (`11 passed` each time, ~0.7s),
confirming the real-subprocess test (child launch + monkeypatched failure +
real reap) is deterministic, not timing-dependent.

### 11.5 Proof no worker/process remains

The autouse `_no_leaked_ar2_threads` fixture in `tests/conftest.py` (an
existing, unmodified check from the original O1 suite) applies to every
test in the suite, including all 11 new ones: it fails any test that
leaves an `ar2-`-prefixed thread alive, and `pytest_sessionfinish` reports
the same check at the session level. Both are green
(`ar2-owned threads still alive = none`). The one test that launches a
REAL fake-Pi child (`test_handshake_rpc_failure_after_real_process_creation_reaps_the_child`)
additionally asserts, directly, that AR2's own termination ladder reaped it
(`exit_status_observed == 0`) rather than merely trusting the thread check.
No additional process inspection tooling was needed or added.

### 11.6 Files changed by FU1

- `run_o1.py` -- removed the local `_launch_and_handshake`; both call sites
  (`phase_handshake`, `phase_case`) now call `o1.handshake.launch_and_handshake`;
  `phase_case` gained the `try`/`except CompatibilityHandshakeError` guard
  described above; the truthfulness correction in this file's section 3 was
  written as part of the same follow-up. Trimmed now-unused imports
  (`build_pi_argv`, `TOOL_ALLOWLIST`, `describe_generated_config`,
  `write_disposable_extension`, `write_disposable_pi_config`,
  `audit_withheld_names`, `build_launch_environment`,
  `evaluate_extension_identity`, `evaluate_model_identity` -- all now used
  only inside `o1/handshake.py`).
- `o1/handshake.py` -- new. `launch_and_handshake` (the exact prior launch
  sequence, now exception-safe) and `CompatibilityHandshakeError`.
- `tests/test_o1_handshake_lifecycle.py` -- new. The 11 tests above.
- `FINDINGS.md` -- this section, plus the section 3 truthfulness correction.

Nothing under `experiments/pi_external_runtime_ar2/` was read-and-modified.
`o1/handshake.py` reads AR2's real extension source directory
(`experiments/pi_external_runtime_ar2/extension/`) exactly the way the
pre-FU1 code already did, for the same reason (the generated disposable
extension is a copy of AR2's own extension source) -- this is a read, not a
modification, and the injected-failure tests read it too (to build a
realistic disposable extension before the injected failure occurs).

`phase_handshake` (the standalone zero-prompt diagnostic phase) was left
otherwise unchanged: it still has no broker/fixture-cleanup guarantee of its
own on an exception, because that was not in this follow-up's two-issue
scope. It DOES now benefit automatically from the supervisor-shutdown
attempt, because that guarantee lives inside `launch_and_handshake` itself
and applies to every caller -- but the broker- and fixture-level guarantee
described above is specific to `phase_case`, as the brief scoped it.

**This residual gap in `phase_handshake` was closed next, by FU1A (below).**

## 12. FU1A -- Handshake Resource/Scrub Closure (offline only)

5F3A-AR2-O1-FU1A is a second, narrow, OFFLINE-ONLY follow-up to FU1. It
changed nothing about the historical live O1 result (section 6-7): no Pi
was run, no model was called, no network request was made, and O1's live
case was not re-executed. The successful O1 PASS, its semantic-prompt
count, its result JSON, and every qualification statement already supported
remain exactly as recorded.

### 12.1 Three closed issues

**A. Standalone `phase_handshake` now closes its broker/fixture lifecycle on
failure.** Before FU1A, `phase_handshake` called `launch_and_handshake()`
with no `try`/`except` at all: a compatibility failure there escaped
straight to `main()`, bypassing broker shutdown, resource scrubbing and
fixture cleanup entirely -- the exact defect FU1 had already closed for
`phase_case`, still open here. `phase_handshake` now wraps the call in
`try`/`except CompatibilityHandshakeError`, records the exact failure
reason (`report["compatibility_handshake_exception"] = exc.as_dict()`), and
falls through to broker shutdown (attempted exactly once, on every
outcome), independent resource scrubbing, and unconditional fixture removal
-- unchanged from this phase's original always-remove shape, since it is a
diagnostic-only phase that carries no case evidence to preserve. This phase
never sends a prompt in any case (no prompt-send statement exists in its
source at all), so "zero semantic prompts" was always structurally true
here; what changed is that a failure no longer bypasses cleanup.

**B. The Pi-config-before-extension failure window is closed.** Write order
inside `launch_and_handshake` is Pi config first, then the extension. The
pre-FU1A `CompatibilityHandshakeError` carried only `extension_dir`; if the
Pi config write succeeded and the LATER extension write then failed,
`extension_dir` was empty, and both `run_o1.py` cleanup sites scrubbed the
Pi config only `if extension_dir:` -- so a genuinely-generated,
endpoint-bearing `models.json` could survive into preserved evidence.
`CompatibilityHandshakeError` now tracks `pi_config_dir` and `extension_dir`
as two independent fields (neither's presence is inferred from the other),
and both `run_o1.py` cleanup sites (`phase_handshake`, and `main()`'s
live-case cleanup) now scrub each resource on its own `if`, never nested
inside or gated by the other. Both raw paths are INTERNAL-ONLY: they exist
solely for the caller's own scrub/cleanup calls and are never written into
`as_dict()`, `run[...]`, or any other emitted evidence -- only their
booleans (`pi_config_dir_generated`, `extension_dir_generated`) are.

**C. A failing shutdown can no longer mask the original compatibility
failure.** Before FU1A, `supervisor.shutdown()` was called unguarded inside
the exception handler; had it itself raised, THAT exception -- not the
original launch/RPC failure -- would have propagated, losing the truth of
what actually went wrong first. The shutdown call is now itself wrapped:
the ORIGINAL exception is always what `CompatibilityHandshakeError` reports
as `original_exception_class`/`original_exception_reason`. Whether a
shutdown was attempted (`shutdown_attempted`) and whether it ALSO raised
(`shutdown_exception_class`/`shutdown_exception_reason`) are recorded as
separate, independent facts. A failed shutdown is never reported as though
the child stopped -- `termination` stays `{}` in that case, the same
"nothing observed" shape used when no shutdown was attempted at all. No
retry, no thread kill, no fallback was added. `as_dict()` exposes only
bounded fields: exception class names and reason strings capped at 500
characters (`_MAX_REASON_LENGTH`), never a raw traceback and never a
credential.

### 12.2 Files changed by FU1A

- `o1/handshake.py` -- `CompatibilityHandshakeError` gained `pi_config_dir`,
  `shutdown_attempted`, `shutdown_exception_class`,
  `shutdown_exception_reason`; `launch_and_handshake` now tracks
  `pi_config_dir` the instant it is written, and wraps the
  `supervisor.shutdown()` call in its own `try`/`except`.
- `run_o1.py` -- `phase_handshake` gained the `try`/`except
  CompatibilityHandshakeError` guard described in issue A, with broker
  shutdown, independent resource scrubbing, and fixture removal now always
  reached; `phase_case` and `main()`'s live-case cleanup both now track and
  scrub `pi_config_dir` independently of `extension_dir` (issue B).
- `tests/test_o1_fu1a_lifecycle_closure.py` -- new. 13 tests covering all
  three issues.
- `FINDINGS.md` -- this section.

Nothing under `experiments/pi_external_runtime_ar2/` was read-and-modified.

### 12.3 New injected-failure tests

`tests/test_o1_fu1a_lifecycle_closure.py`, 13 tests, all offline and
deterministic:

- **Issue A (7 tests, source inspection):** `phase_handshake` never sends a
  prompt (no `"type": "prompt"` string anywhere in its source); catches
  `CompatibilityHandshakeError`; broker shutdown is lexically after the
  `try`/`except` and appears exactly once; the Pi-config scrub `if` and the
  extension scrub `if` are independent, top-level, unnested statements;
  fixture cleanup is always reached; the exception handler never reassigns
  `supervisor` and never calls `.shutdown()` a second time.
- **Issue B (3 tests, real regression):** `write_disposable_pi_config`
  genuinely succeeds (using a synthetic, non-network endpoint needle,
  `http://synthetic-fu1a-test-endpoint.invalid:9999/v1`, written into a
  REAL `models.json` on disk) and `write_disposable_extension` is injected
  to raise immediately after. Proven: the original exception is the exact
  injected `RuntimeError`, never generic; `pi_config_dir` is populated and
  `extension_dir` is empty (proving the independent-tracking claim
  concretely, not just in principle); the synthetic needle IS present on
  disk before scrub (proving the failure window is real); `scrub_generated_
  pi_config(exc.pi_config_dir)` (AR2's own, unmodified function, called
  exactly as the fixed cleanup code calls it) removes the file and reports
  verified removal; the needle is absent from disk afterward; and
  `as_dict()` never contains the needle or the raw temp-path string.
- **Issue C (2 tests, real fake child + injected double failure):** a REAL
  child process is launched (blocks on stdin, exits 0 on EOF -- the same
  pattern used in FU1's own tests), `PiRpcSupervisor.send_command` is
  monkeypatched to raise (the RPC failure), AND `PiRpcSupervisor.shutdown`
  is ALSO monkeypatched to raise. The injected shutdown stub is itself
  responsible for reaping the real child (closing stdin and waiting on it
  directly, bypassing its own broken method) before raising its simulated
  failure -- so the fake child is bounded and fully reaped by the test's
  own injected code, never left running merely because the AIDO shutdown
  path was deliberately broken for the test. Proven: the ORIGINAL RPC
  failure remains `original_exception_class`/`original_exception_reason`,
  never replaced by the shutdown's `RuntimeError`; the shutdown failure is
  recorded separately (`shutdown_attempted: true`,
  `shutdown_exception_class: "RuntimeError"`); `termination == {}` (no
  false claim the child stopped, even though it actually had, by the time
  the stub raised); `stdout_state` remains independently fetchable; the
  test's own reaping bookkeeping confirms the child's exit code (`0`); and
  a second test proves `as_dict()`'s exposed shutdown-failure reason is
  length-capped rather than a raw, unbounded string.

### 12.4 Total offline test count/result

```
python -m pytest experiments/pi_external_runtime_ar2_o1/tests -q
89 passed
[ar2-o1] session finish: ar2-owned threads still alive = none
```

13 new (FU1A) + 76 carried forward unchanged (30 from the original suite +
35 from the Pi-compatibility-policy suite + 11 from FU1). The FU1A file
alone, and combined with FU1's own real-child test, was re-run three
consecutive times with no flake.

### 12.5 Proof no worker/process/child survives

The autouse `_no_leaked_ar2_threads` fixture in `tests/conftest.py`
(unmodified since the original suite) covers all 89 tests, including the 13
new ones: `ar2-owned threads still alive = none` on every run. The Issue C
test additionally proves, directly and not merely by omission, that the
one real fake-Pi child it launches was actually reaped: the injected
shutdown stub's own bookkeeping (`reaped["waited"] is True`,
`reaped["exit_code"] == 0`) confirms `Popen.wait()` returned before the
test ends, regardless of the fact that the "real" `PiRpcSupervisor.shutdown`
path was deliberately broken for the test.

### 12.6 Proof no generated endpoint-bearing config can survive the tested failure path

`test_pi_config_survives_before_scrub_when_extension_write_fails` reads the
generated `models.json` from disk twice: once BEFORE scrub (confirming the
synthetic endpoint needle is genuinely present -- the failure window is
real) and once AFTER calling `scrub_generated_pi_config(exc.pi_config_dir)`
(confirming the file no longer exists at all).
`test_compatibility_handshake_error_as_dict_never_contains_the_endpoint`
additionally proves the needle never appears in the exception's own
serialized `as_dict()` output. Together with the source-level proof that
`run_o1.py`'s two cleanup sites scrub the Pi config unconditionally (never
gated on `extension_dir`), this closes the exact failure window the brief
described, both in the unit-level function and in the calling code.
