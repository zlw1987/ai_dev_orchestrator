# Phase 5F3A-AR1 — Findings

Experiment executed 2026-08-21. Authoritative record:
`results/ar1_live_20260821T004934Z.json`. Supporting records:
`results/ar1_preflight_*.json`, `results/ar1_probe-env_*.json`.

**This is an experiment record, not a production ReviewPacket. No reviewer was
invoked. Nothing was promoted, committed, branched, pushed, or written to any
real workspace.**

## 0. AR1-FU1 — post-run safety/truthfulness closure

**AR1-FU1 made no new live run.** No prompt was sent, no model was called, and
`results/ar1_live_20260821T004934Z.json` is unmodified. It closes two latent
defects found by independent review of the *implementation*, not of the
historical result:

1. **H1 (the extension identity handshake) did not fail closed on an exact
   identity mismatch.** The pre-FU1 gate treated a same-named,
   extension-sourced sentinel as sufficient (`passed: sentinel is not None`),
   so the historical live run's `sentinel_extension_path_matched_expected:
   false` — a **reader limitation** (section 3 below), not evidence of a
   genuinely wrong extension — still let the one real prompt through. H1 now
   additionally requires the reported path to resolve to exactly the expected
   extension entry point and any reported `sourceInfo.source` to not
   contradict the known-expected `"cli"` value. **The original live run used
   the older, weaker gate — this document must never be read as claiming the
   historical real prompt was gated by exact extension-path matching.** A
   later no-prompt diagnostic run (`results/ar1_probe-env_20260821T005317Z.json`)
   already showed `sentinel_extension_path_matched_expected: true` and
   `sentinel_source_kind: "cli"` under the reader fix that predates FU1; FU1's
   change is to the *gate*, not the *reader*.
2. **A scrub finding did not prevent normal artifact emission.** `scrub_check`
   could detect an unsafe candidate record but the emission path wrote and
   echoed it regardless — detection without prevention. Emission now runs
   through one choke point that refuses a non-clean candidate outright and
   emits a small, fixed, independently-scrub-checked refusal record instead
   (never the offending value). **The historical artifact was scrub-clean; no
   secret or reasoning leak was ever recorded.** FU1 closes a latent defect,
   not a historical incident.

See `run_ar1.py`'s `evaluate_extension_identity()` and `emit_or_refuse()`, and
`tests/test_fu1_identity_and_emission.py`.

## 1. Headline

One Pi 0.84.2 RPC run, one prompt, one observation. Every gate passed, the
runtime settled on its own, AIDO reconstructed the repository state
independently, and authoritative verification passed.

| | |
|---|---|
| Real semantic prompts AIDO sent | **1** (the maximum authorized) |
| Provider HTTP requests inside that run | **not AIDO-observable** — Pi owns the agent loop and made at least 3 model turns (`turn_start` x3, `message_start` x7). One AIDO semantic prompt is NOT one HTTP request, and AIDO does not see the wire. |
| Phases that made zero inference | preflight, probe-env (all attempts), the `get_commands`/`get_state` diagnostic, and both handshakes of the live run |
| Turn outcome | `runtime_settled` in 9.5 s |
| Termination rung | `exited_after_stdin_close`, exit status 0 |
| Protocol violations | 0 (269 records, 81,878 bytes, all strict JSONL) |
| Tools the model called | `aido_read` x2, `aido_edit` x1, and **no other tool call was observed**. Stated exactly (5F3A-AR2D): the *configured* registry allowlist was `aido_read,aido_edit`; the *observed* live tool calls were those three; and the extension identity was independently handshaken. Pi 0.84.2 has no RPC command that enumerates tools, so this is **not** an RPC-registry query proving the active runtime registry contained only those two entries. |
| Non-allowlisted access attempts | 0 during the live run |
| AIDO-observed class | `clean_expected` — exactly ` M calc.py`, HEAD unchanged, index clean |
| Verification | 3 passed, exit 0 |
| Seeded bug fixed | **yes** (`<` → `<=`), incidental to the architecture question |

## 2. What the experiment actually establishes

### 2.1 B-fixed confinement works for this shape

The model was offered exactly two tools, both AIDO-authored, both backed by an
exact allowlist of concrete absolute paths AIDO computed before Pi launched. The
offline harness drove the **real Pi 0.84.2 tool factories** with those guarded
operations and proved, without any model:

- `aido_read(calc.py)`, `aido_read(test_calc.py)` and the relative spelling all
  succeed;
- `aido_edit(calc.py)` performs a real edit;
- an absolute out-of-fixture path is **refused**;
- traversal-shaped targets (`..\outside_canary.txt`, `../outside_canary.txt`) are
  **refused**;
- `aido_edit(outside_canary.txt)` is **refused**, and the canary file is byte-for-byte
  unchanged;
- `aido_edit(test_calc.py)` — readable but not editable — is **refused**;
- on **every** refusal the underlying filesystem implementation was **never
  invoked** (spy-instrumented, asserted per case);
- every filesystem call that did happen targeted an allowlisted path inside the
  temporary experiment root, and none referenced anything outside it.

The guard also never hands the model's string to the filesystem: it returns
AIDO's own allowlisted string, and the real call uses that.

### 2.2 The fail-closed property is the design, not a side effect

Pi collects extension load errors and continues. Overriding the built-in tool
**names** would therefore fail **open** — the unconfined built-in would survive
under an allowed name. Using distinct `aido_*` names means a failed load leaves
the `--tools` registry filter matching **nothing**, so the model gets no
filesystem capability at all and the run degrades to "no change observed", which
the classifier handles safely.

### 2.3 Ambient Pi state can be excluded harder than expected

Pi started, loaded the AIDO extension, resolved the intended provider/model, and
completed a full agent run with **`USERPROFILE`, `HOME` and `APPDATA` all
withheld**, a `PATH` narrowed to four entries, and a disposable
`PI_CODING_AGENT_DIR`. This resolves three AR0 unknowns at once:

- **U-2** — a narrowed `PATH` works (Node dir, Git dir, `System32`, `%SystemRoot%`).
- **U-3** — `PI_CODING_AGENT_DIR` redirection was sufficient here; no failure
  attributable to `~/.pi/agent` occurred. (This is evidence of sufficiency for
  this run, not proof that no Pi code path ever touches `~/.pi`.)
- **U-4** — the profile variables were **not** required. Withholding
  `USERPROFILE` is a second, independent barrier against `~/.pi/agent`
  resolution, and it cost nothing.

The launched environment held 15 variables. Nine sensitive names present in
AIDO's own process environment were forwarded: **zero**.

### 2.4 The endpoint needed no credential at all

The generated `models.json` resolves `apiKey` by `$ENV` interpolation from one
variable whose value is the fixed, non-secret literal `no_api_key`. **A
placeholder is not authentication.** No credential of any kind entered Pi's
environment, and `!shell` credential resolution was never used anywhere.

### 2.5 Runtime reports and observed state agreed — and only one of them counted

Pi claimed three tool calls and a successful edit. AIDO ignored that as
authority and re-derived the state with the accepted fixed Git operations in the
accepted preflight order: `status_porcelain` reported exactly `" M calc.py"`,
`rev_parse_head` matched `HEAD_before` exactly, the index was clean, no untracked
file appeared, and only then was `diff_one_path("calc.py")` requested. **Zero new
Git operations were added** — AR0's U-10 is answered again in practice.

### 2.6 Verification created no cache, so `unexpected_untracked` stayed sharp

Running the fixed command `python -B -m pytest -q -p no:cacheprovider -rf
test_calc.py` produced no `__pycache__` and no `.pytest_cache`. The post-run
untracked set is genuinely empty rather than empty-by-allowlist, and the
pre-verification and post-verification observations are recorded separately.

## 3. Two Pi 0.84.2 facts the shipped docs get wrong or under-describe

Both were found by running the thing, and both are recorded because they would
bite the next slice.

1. **`get_commands` reports the extension origin under `sourceInfo.path`, not the
   flat `path` field the shipped `docs/rpc.md` example shows.** Reading only the
   documented field made a genuine match look like a mismatch. The first live
   record therefore carries `sentinel_extension_path_matched_expected: false`
   — that was a **reader limitation, not a mismatch**. The reader now consults
   both, fails closed when neither is present, and a subsequent no-prompt probe
   confirms `true` with `sentinel_source_kind: "cli"`.
2. **Pi ships its own inline extension command** (`llama`, "Manage llama.cpp
   router models", `sourceInfo.source: "inline"`). So `get_commands` shows two
   extension-sourced commands even with `--no-extensions` and one explicit `-e`.
   It is a slash **command**, not a tool; the `--tools` registry filter governs
   tools regardless. The record now names it explicitly rather than leaving an
   unexplained count.

A third, non-Pi note: `BufferedReader.read(n)` blocks until `n` bytes or EOF,
which would stall a live protocol stream until process exit. The stdout/stderr
readers use `read1`. Any future stdio supervisor must do the same.

## 4. What this does NOT prove

- **Pi was not sandboxed.** B-fixed is capability restriction at the tool layer,
  inside Pi's own Node process, with the launching user's full Windows
  permissions. A Pi defect, a dependency defect, or a future Pi version adding an
  unconfined filesystem path bypasses it entirely.
- **No claim is made that no host file outside the fixture could have been read.**
  The accurate claim is narrower: the model was offered no tool able to name such
  a path, and AIDO's own code decided every operation those tools performed.
- **Pi's read-path resolver stats the filesystem before the operations seam is
  consulted** (Unicode/NFD variants of a resolved path). The claim covers reads
  and writes through AIDO's tools, not Pi's own existence probes.
- **`get_commands` proves the extension loaded, not the active tool registry's
  contents.** Pi 0.84.2 has no RPC command that enumerates tools.
- **AIDO's wait ending is not Pi stopping**, is not the provider request being
  cancelled, and is not backend inference stopping. In this run the direct child
  exited 0 after stdin close, which is the graceful path that runs Pi's own
  cleanup — that is all that is claimed. No descendant claim is made.
- **The repository was observed at one instant.** The observation timestamp and
  termination state are recorded; quiescence is not claimed.
- **One synthetic fixture AIDO wrote itself is not evidence about a real
  repository.**

## 5. Token policy

AIDO requested **no** output-token ceiling. The generated `models.json` omits
`maxTokens` entirely, so the record reads:

```json
{"aido_requested_max_output_tokens": null, "runtime_native_max_tokens": "pi_catalog_default"}
```

`get_state` independently reported the resolved model's `maxTokens` as `16384`,
which is exactly Pi's own catalog default (`definition.maxTokens ?? 16384`) and
confirms the `"pi_catalog_default"` label is literal rather than cautious. The
provider reported usage of 1,616 input / 67 output / 1,683 total tokens, recorded
as reported. Had it reported none, the record would say **unknown, never zero**.

## 6. Reasoning

127 reasoning delta records, 9 reasoning content blocks and 18 reasoning-bearing
keys were dropped **at ingestion**, before any record was stored, logged, hashed
or written. Only counts survive. The emitted record contains no reasoning field
or value (asserted by the record's own scrub check). No chain-of-thought
observability was built.

## 7. Architecture conclusions

### 7.1 Does Pi remain viable as an external runtime? — **Yes.**

Everything the supervision design depends on held under a real run: strict
LF-framed JSONL with zero protocol violations; `agent_settled` as a genuine
completion signal (`agent_end` arrived once, with `willRetry: false`, and was
correctly not treated as completion); stdin-close as a real in-protocol shutdown
lever that exits cleanly; `get_state` proving the model before any prompt; and
`get_commands` proving the extension loaded. Nothing needed a workaround, and no
fallback path was exercised.

The direct-vLLM Qwen3.6 route interoperated with Pi's OpenAI-completions client
**including tool calling** — AR0's U-7, which was the largest single technical
risk, is answered affirmatively.

### 7.2 Did B-fixed work for this synthetic PoC? — **Yes, and it was cheap.**

The security-critical surface is about 200 lines of TypeScript with no path
parsing in it. There is no second canonical-path implementation, no second IPC
channel, and no duplicated harness — Pi keeps the agent loop, the schemas and the
streaming; AIDO supplies only the operations. The correctness argument is one
sentence: *the resolved path must be an exact member of a list AIDO computed, and
the filesystem is handed AIDO's string, not the model's.*

### 7.3 What must change before any broader or real-repo experiment

1. **B-fixed does not survive contact with a real repository.** Its allowlist
   *is* the fixture. A real repo needs either **B-rpc** (the extension becomes a
   dumb proxy and AIDO decides every path in Python, keeping one authority) or
   **Option A** (an OS boundary). B-general — porting the 914-line canonical
   guard to TypeScript — remains the wrong trade.
2. **Option A is still the right escalation and is still unavailable.** Docker,
   Podman, WSL and Windows Sandbox are all absent and all need an elevated host
   change. Nothing in this run makes that less true; it makes it more urgent for
   any non-synthetic target.
3. **The tool registry needs positive proof.** `get_commands` proves load, not
   registry contents. A later slice should add a first-turn probe tool call, or
   an upstream request for a tool-enumeration RPC command.
4. **Pin the Pi version and re-review the seam on every upgrade.** The operations
   seam is not a stability contract. `pi --version` is asserted before every run
   for this reason.
5. **The reviewer adaptation is still owed.** The shipped reviewer prompt asserts
   the diff was human-approved before it was written, which is false for a
   runtime-produced change. AR1 deliberately ends at verification. Attaching a
   reviewer requires an experiment-local context and prompt that state the truth
   — runtime-produced, AIDO-observed, **not** human-pre-approved — and no change
   to `review-packet.v4` or any production reviewer semantic.
6. **Promotion remains unauthorized.** The 5F2C writer is the right *promotion*
   primitive and the wrong *implementation* primitive, and nothing here changes
   that.

### 7.4 Is AR2 justified? — **Yes, and its shape follows from this run.**

AR1 spent its risk budget on the questions that could have killed the approach,
and none of them did. The remaining unknowns are about *scale of trust*, not
feasibility. A justified AR2 would take exactly one step:

- **the negative controls AR1 did not run live** — N1 (ask the model to describe
  a change without making one; AIDO must observe zero changes), N3 (`--no-tools`,
  expect zero `tool_execution_start` events), and a live N4 (ask for an
  out-of-fixture path and observe the refusal as an `isError` tool result rather
  than inferring it from the offline harness);
- **a multi-file fixture** with more than one plausible edit target, which is
  what actually stresses `unexpected_change` and the exact-allowlist shape;
- **the B-rpc decision**, taken deliberately rather than by drift, because that
  is the boundary a non-synthetic repository needs.

AR2 should *not* add: `bash`, a second prompt, a relaunch, a fallback model or
route, a generic runtime abstraction, a production config field, or a CLI
command. And it should not touch a real workspace.

## 8. One defect found and fixed in the harness itself

`shutil.rmtree(..., ignore_errors=True)` silently failed to remove the
disposable roots: Git marks loose objects read-only, and Windows refuses to
unlink a read-only file, so every run left four orphaned `.git/objects` blobs
under the temp directory. **Only Git objects survived** — no `models.json`, no
`settings.json`, no extension file and no working file, so the generated
endpoint was never left on disk. Cleanup now clears the attribute, retries, and
**reports residue rather than claiming a success it cannot prove**; the nine
leftover roots from the probe and diagnostic runs were removed, and a test
covers it.
