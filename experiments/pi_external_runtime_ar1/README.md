# Phase 5F3A-AR1 — Pi External Runtime Synthetic PoC (EXPERIMENT ONLY)

> **This is an experiment. It is not production Pi integration.**
>
> - It adds no `ProjectConfig` field, no CLI command, and no production Pi support.
> - It modifies nothing under `src/`, `tests/`, `projects/`, `CLAUDE.md` or `README.md`.
> - It creates no `AgentRuntime`, no `PiRuntime`, and no generic runtime abstraction.
> - It invokes **no reviewer**. It emits no `review-packet.v4` and fabricates no
>   `ApprovedDiffProposalArtifact`.
> - Deleting this directory removes the experiment entirely.

## Authority

- `docs/PHASE_5F3A_AR0_PI_EXTERNAL_RUNTIME_BOUNDARY_DESIGN.md`
- `docs/PHASE_5F3A_AR0_FU1_PI_RUNTIME_CONFINEMENT_DESIGN.md` — **supersedes AR0
  wherever they conflict.**

Neither document was modified by this work.

## The question

Can AIDO supervise **one** Pi RPC coding run against a synthetic repository while
exposing only AIDO-authored, fixed-path filesystem tools; minimizing Pi ambient
state; proving the intended model before prompting; bounding the outer runtime
honestly; dropping reasoning at ingestion; independently reconstructing
repository state; running authoritative verification; and never trusting Pi's
repository claims?

**The experiment succeeds by producing architectural evidence. "The model fixed
the bug" is neither necessary nor sufficient.**

## The confinement decision — FU1 Option B-fixed

Pi's built-in filesystem tools resolve a model-supplied path as roughly
`path.resolve(cwd, input)` with no containment check, so `cwd` is a starting
point, not a jail. AR1 therefore exposes **none of them**:

| Surface | AR1 |
|---|---|
| `read` / `write` / `edit` / `grep` / `find` / `ls` / `bash` | **not in the registry** |
| `aido_read` | AIDO-authored, exact-allowlist: `calc.py`, `test_calc.py` |
| `aido_edit` | AIDO-authored, exact-allowlist: `calc.py` |
| `aido_write` | **does not exist in AR1** — no architecture question here needs whole-file creation or overwrite |

The **security control is `--tools aido_read,aido_edit`**, which filters Pi's tool
*registry*. `--no-builtin-tools` is passed as belt-and-braces only: it does not
filter the registry and must never be relied on.

Because the tool names are **distinct** rather than overrides, a failed extension
load fails **closed** — the registry ends up with zero matching tools and the
model gets no filesystem capability at all.

### What this proves, and what it does not

> B-fixed is capability restriction at the tool layer, enforced inside the
> runtime's own process. **It is not an OS sandbox.** It proves the model was
> offered no tool capable of naming a path outside the allowlist, and that AIDO's
> own code decided every filesystem operation those tools performed. It does
> **not** prove that no host file outside the disposable repository was read or
> written: the extension runs inside Pi's Node process with the launching user's
> full Windows permissions.

Never write "Pi was sandboxed", "OS-isolated", "no host path outside the fixture
was touched in any sense", or "the Node/Pi process lacked host permissions".

## Layout

```text
experiments/pi_external_runtime_ar1/
  README.md
  run_ar1.py                     harness entry point (NOT a CLI command)
  experiment_config.example.json  template; see the note below on the real file
  ar1/
    ascii_json.py      ASCII-safe emission for Windows legacy consoles
    fixture.py         the disposable synthetic Git repository + seeded bug
    pi_config.py       disposable PI_CODING_AGENT_DIR + disposable extension
    environment.py     the explicit minimal launch environment (names only)
    launch.py          pinned Node + Pi 0.84.2 identity and argv
    protocol.py        strict LF-only JSONL framing + reasoning drop
    supervisor.py      one launch, bounded, AIDO-owned monotonic deadlines
    observation.py     independent Git observation + fail-closed classification
    verification.py    authoritative verification via the accepted bounded runner
    record.py          the experiment run record (NOT a ReviewPacket)
  extension/
    confinement.ts           the exact-allowlist guard (no general path policy)
    tools.ts                 AIDO tool construction with Pi factories injected
    index.ts                 the one explicitly loaded extension
    confinement_harness.ts   OFFLINE confinement harness (no model, no network)
    package.json
  tests/                     the offline suite (no network, no model, no socket)
  results/                   run records
```

## Gating

Nothing runs by accident, and there is no production gate:

1. an explicitly-named config file, `experiment_config.json` — an absent file is
   a refusal.

   > **Repository-state correction (recorded by 5F3A-AR2D; status updated by
   > 5F3A-AR2D-FU1).** The intent was that this operator-local file ship
   > **absent**. It was in fact committed in `331174d`, and a separate operator
   > action untracked it in `30d54b7`. It carried no credential and no endpoint
   > value — only a provider id, a model id, an environment variable *name*, and
   > a local interpreter path — so nothing secret was published; but an
   > operator-local runtime config is exactly the class the evidence-retention
   > policy says not to commit. The remaining step is the operator's to perform
   > deliberately: add the file to an experiment-local `.gitignore`, leaving
   > `experiment_config.example.json` as the only committed template. Neither
   > AR2D nor AR2D-FU1 performs a git operation.

2. two explicit flags for the live phase:
   `--run-pi-external-runtime-experiment` and `--send-one-real-model-prompt`.

```bash
python experiments/pi_external_runtime_ar1/run_ar1.py --phase preflight
```

```bash
python experiments/pi_external_runtime_ar1/run_ar1.py --phase probe-env
```

```bash
python experiments/pi_external_runtime_ar1/run_ar1.py --phase live --run-pi-external-runtime-experiment --send-one-real-model-prompt
```

`preflight` and `probe-env` send **no prompt** and trigger **no inference**.

## Live-run gate

The one real prompt is authorized only if every one of these holds.

**One of them is an operator/execution prerequisite rather than a mechanically
attested condition, and the distinction matters:** `phase_live()` does not
execute the pytest suite and does not attest it. "The offline suite is green"
was required by the execution procedure and was satisfied by the operator before
the run; it is **not** one of the gate booleans recorded in `live_run_gate`.
Every other item below *is* evaluated inside `phase_live()`.

- **(operator/execution prerequisite, not attested by `phase_live()`)** every
  offline test is green;
- `pi --version` resolves to exactly `0.84.2`, via the pinned Node-direct launch;
- **H1, the extension identity handshake** (`get_commands`) proves, together:
  a command named `aido_confinement_active` exists; its reported `source` is
  exactly `"extension"`; its reported path (`sourceInfo.path`, or the flat
  `path` field if that is absent) resolves to exactly the extension entry
  point AIDO itself passed via `--extension`; and any reported
  `sourceInfo.source` does not contradict the one known-expected value for a
  CLI-loaded extension (`"cli"`). Any missing, wrong, or malformed piece fails
  the whole gate — a same-named command existing is **not** sufficient
  (AR1-FU1; see FINDINGS.md for why the pre-FU1 gate was weaker);
- the `get_state` provider/model handshake matched exactly;
- the direct-Qwen route configuration is available without exposing secrets;
- the baseline repository state is trusted;
- baseline verification shows exactly the seeded equality failure.

Any failure means **no prompt is sent**.

## Safe artifact emission (AR1-FU1)

Every record this harness writes or prints goes through one choke point,
`emit_or_refuse()`. It runs the existing `scrub_check` on the candidate
artifact; a clean result writes and echoes it as before. Anything else — an
actual finding, or `scrub_check` itself raising on a malformed candidate —
refuses the candidate outright: it is **never** written or echoed, and a small,
fixed, independently-scrub-checked refusal record (`outcome:
"artifact_emission_refused"`, plus finding counts and bounded category codes —
never the offending value) is emitted in its place. Detection was already
correct before this change; this closes the gap between detecting an unsafe
artifact and actually refusing to emit it.

## Live invocation count

**Exactly one real semantic prompt, ever.** No retry for a bad implementation, a
failed verification, noisy output, a disappointing result, or an infrastructure
failure that happened after the prompt. Evidence is preserved instead.

## Token policy

AIDO imposes **no** model output-token ceiling. The generated `models.json`
**omits `maxTokens` entirely**, so the record can truthfully say:

```json
{"aido_requested_max_output_tokens": null, "runtime_native_max_tokens": "pi_catalog_default"}
```

`null` means exactly *AIDO did not request a cap* — never `0`, `-1`, or
`"unlimited"`. The process/time/output bounds in `supervisor.py` are **runtime
supervision bounds, not token limits**.

## Reasoning

Reasoning-bearing content — thinking deltas, `thinking` blocks,
`reasoning_content` and equivalents — is dropped **at ingestion**, before any
record is stored, logged, hashed, or written. Only counts of what was dropped are
kept. No chain-of-thought observability exists here.

## Two disjoint namespaces

| Prefix | Source | Trust |
|---|---|---|
| `runtime_reported_*` | Pi's JSONL events | **untrusted claim** |
| `orchestrator_observed_*` | AIDO's own Git/filesystem reads | **authoritative** |

Pi's account of what it changed is never repository authority.

## Destroying the experiment

Delete this directory. The disposable repository and disposable Pi configuration
live under the system temp directory and are removed after the record is written
— except when the classification is untrusted or an anomaly occurred, in which
case they are **preserved for inspection** and the record says so.
