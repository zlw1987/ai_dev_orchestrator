# Phase 5F3A-AR2 — Delegated Synthetic Workspace Broker PoC

> **EXPERIMENT ONLY.** This is not production Pi integration. It adds no
> `ProjectConfig` field, no CLI command, no production broker, and no
> `AgentRuntime` / `PiRuntime` / `BaseRuntime` / `RuntimePlugin` abstraction.
> Nothing under `src/`, `tests/`, `projects/`, `CLAUDE.md` or the root
> `README.md` was modified. Nothing was committed and nothing was pushed. The
> whole directory is deletable as one experiment.

**Authority followed**

- `docs/PHASE_5F3A_AR2D_DELEGATED_WORKSPACE_AUTHORITY_DESIGN.md` (AR2D)
- `docs/PHASE_5F3A_AR2D_FU1_CAPABILITY_STATE_AND_BROKER_LIFECYCLE.md` (FU1 —
  **supersedes AR2D wherever they conflict**)
- `experiments/pi_external_runtime_ar1/` — the accepted AR1 experiment, reused
  where its machinery genuinely fits. **No AR1 result JSON was altered.**

---

## The one question AR2 exists to answer

AR1 proved a **fixed concrete path capability**: AIDO chose exactly which files
were readable and editable, so the model was handed the answer to the interesting
question before the question was asked.

AR2 asks the next one:

> Can an external Pi runtime **nominate** repository paths inside a bounded
> synthetic workspace while AIDO's Python broker remains the sole authority that
> decides, **per operation**, whether each candidate is permitted?

The distinction is load-bearing:

```text
the runtime NOMINATES a repository-relative path candidate
AIDO AUTHORIZES, per operation, from its own accepted Python primitives
```

**No model output authorizes a filesystem operation.**

## Architecture

```text
Pi / Qwen3.6
    |  tool call (aido_read / aido_edit)
thin TypeScript extension          <- a serializer and a single-flight queue
    |  Windows named-pipe IPC       (LF-framed strict JSONL, one client)
AIDO-owned Python broker            <- the ONE path/security authority
    |  workspace/canonical.py + capability domain + exclusion classifier
disposable synthetic Git repository
```

AR1's ~200 lines of security-critical TypeScript — a comparison key, an allowlist
`Map`, a `realpathSync.native` cross-check — are **deleted**, not ported. That is
a *reduction* in security-critical TypeScript, and it is the strongest argument
for this shape.

## What the broker can and cannot do

**Exactly two operations:** `read_file` and `edit_file`. There is no `verify`,
`stat`, `list`, `search`, `glob`, `execute`, `shell`, `create`, `delete` or
`rename`, and no cancellation verb.

| | |
|---|---|
| Root | ONE canonical disposable synthetic repository under temp. Never a real project workspace, never `C:\dev\ai_dev_orchestrator` or any parent — the mint refuses those by name |
| Read domain | Tracked regular strict-UTF-8 files from the mint-time `ls_files_stage` manifest, minus exclusions; ≤ 256 KiB per file, ≤ 1 MiB and ≤ 32 reads per run |
| Write domain | A **proper subset**: existing tracked files only, not protected, not a verification witness, **previously read this run**; ≤ 2 changed files, ≤ 16 edits, ≤ 512 KiB total |
| Discovery | An AIDO-computed prompt manifest (≤ 200 entries, ≤ 8 KiB). No traversal primitive exists |
| Verification | AIDO-only, **after** the runtime settles, argv fixed by the fixture. The model gets no `aido_verify` |
| Reviewer | **Not invoked.** No packet, no `ApprovedDiffProposalArtifact`, no `review-packet` bump |
| Promotion | None. No branch, commit, push, PR, or real-workspace write |

### Capability state — the FU1 two-layer model

> The static read/write eligibility domains are immutable after mint and never
> expand. Runtime events may satisfy fixed operation preconditions, such as the
> write-after-read precondition, while consumption budgets can only reduce
> remaining authority. **No runtime request can add a new path, operation class,
> exclusion exception, cap, root, or privilege to the minted capability.**

```text
SED                  IMMUTABLE       never expands, never contracts
remaining budgets    NON-INCREASING  consumption only; never refilled
terminal flags       MONOTONE        once terminal, terminal for the run
OPERATIONALLY-       NOT MONOTONE    a read receipt makes an ALREADY write-eligible
INVOCABLE SET                        path invocable; that is a precondition being
                                     satisfied, not domain growth
```

**AR2 never describes the capability as "monotonically shrinking".**

### Broker lifecycle

`CREATED → READY → SERVING → DRAINING → CLOSED`, or `TEARDOWN_INCOMPLETE`.

One in-process daemon thread, **overlapped** named-pipe I/O throughout, an
explicit shutdown event, and a bounded, *observed* teardown. There is no
synchronous blocking `ConnectNamedPipe`/`ReadFile`/`WriteFile` on the protocol
path: FU1 measured that a controller-side `CloseHandle` with a synchronous
connect pending did not return in ~19 s.

**The broker thread owns its handles. The controller signals; it does not close.**
Its one escalation lever is `Overlapped.cancel()`. It never closes a handle, never
releases an `Overlapped` buffer, never kills a thread, never sleeps and assumes.

The broker reaches `READY` **before Pi is launched**.

## Truthfulness rules this experiment holds

- **Not a sandbox.** The broker is a capability boundary for operations AIDO
  performs *on the runtime's behalf*. The extension runs inside Pi's Node process
  with the launching user's full Windows permissions. Never write "sandboxed",
  "isolated", "OS-confined", or "no host file outside the workspace was touched".
- **The pipe DACL and token are integrity and attribution controls, not access
  control** against a same-user adversary — that adversary does not need the
  broker at all.
- **Overlapped cancellation bounds NAMED-PIPE I/O only.** It does not prove a
  synchronous local filesystem call (`stat`, `open`, `read`, `write`, `fstat`)
  can be cancelled from the controller. If teardown occurs while the worker is
  inside one and it does not terminate within the broker deadline, the outcome is
  `TEARDOWN_INCOMPLETE` — recorded, never claimed away.

```text
AIDO wait ended  !=  broker thread stopped  !=  pending I/O completed
                 !=  handle released        !=  capability provably withdrawn
```

- **Three trust namespaces, kept disjoint.** `runtime_reported_*` (untrusted
  claim), `broker_recorded_*` (AIDO-authored, **diagnostic only**),
  `orchestrator_observed_*` (authoritative). A broker log is **not** repository
  truth even though AIDO wrote it.
- **`get_commands` proves extension LOAD, not registry contents.** Pi 0.84.2 has
  no RPC command that enumerates the tool registry. Equally, a broker that
  received only `read_file` and `edit_file` frames is evidence about what was
  *requested through the broker*, never proof of what the registry contained.
- **AIDO imposes no model output-token ceiling.** The generated `models.json`
  omits `maxTokens`; `aido_requested_max_output_tokens` is `null`, meaning
  *AIDO did not request a cap* — never `0`, `-1` or "unlimited". Process, IPC,
  semantic-turn and broker-teardown limits are **not** token limits.

## Layout

```text
ar2/
  capability.py   SED (immutable) + RunState (AIDO-owned) + caps + exclusions
  candidate.py    evaluate_delegated_candidate -- the ONE delegated path authority
  operations.py   read/edit through identity-verified handles
  wire.py         the two-operation protocol and the closed error set
  broker.py       BrokerRequestHandler (authority) + BrokerServer (lifecycle)
  winpipe.py      narrow _winapi surface + the ctypes user-scoped DACL
  manifest.py     the bounded prompt manifest (discovery without a traversal tool)
  fixtures.py     the R1-R4 disposable synthetic repositories
  route_check.py  non-inference "does this route serve the configured model?" gate
  handshakes.py   H1 (extension identity) and H2 (provider/model identity)
  verification.py AIDO's own bounded verification runner
  observation.py  independent Git observation and classification
  record.py       the run record, the scrub denylist, the refusal record
  pi_config.py    disposable PI_CODING_AGENT_DIR and generated extension config
  launch.py environment.py protocol.py supervisor.py ascii_json.py   (from AR1)
extension/
  index.ts  tools.ts  ipc.ts  package.json      <- NO path authority anywhere
tests/    the offline suite (no model, no network, no socket to a remote host)
results/  sanitized run records
```

## Running it

Gating is two explicit flags plus an explicitly named config file that **ships
absent** — an absent config is a refusal, not a default.

```bash
copy experiment_config.example.json experiment_config.json
```

`experiment_config.json` is listed in this directory's `.gitignore` and **must
never be committed**. AR1 committed its operator-local copy by accident
(AR2D §2.3); AR2 does not repeat that.

Four phases, in increasing cost. The first three send **zero prompts**:

```bash
python run_ar2.py --phase preflight --case R2
```

```bash
python run_ar2.py --phase broker --case R1
```

```bash
python run_ar2.py --phase handshake --case R1
```

`handshake` launches the real Pi with the real extension and runs H1 and H2.
Neither triggers inference, so it costs no semantic prompt — it exists so a broken
extension, generated config or broker is found **before** a case's single
irreplaceable attempt is spent.

The live case requires **both** flags and sends **exactly one** prompt:

```bash
python run_ar2.py --phase case --case R2 --run-pi-delegated-broker-experiment --send-one-real-model-prompt
```

### The live-run gate

Ten conditions, **all mechanically evaluated in `phase_case`**: pinned Pi
`0.84.2`, Node-direct launch, broker `READY` before launch, baseline repository
trusted, baseline matches that case's contract, prompt manifest within caps,
route configuration available, **the route actually serves the configured model**,
H1 passed, H2 passed. Any failure means **zero prompts for that case**, and no
other case's attempt is consumed.

> **The offline suite being green is an OPERATOR/EXECUTION prerequisite and is
> deliberately NOT among them.** `phase_case` does not execute or attest pytest,
> and no test-attestation framework was built merely to make a sentence true.
> Every *other* listed condition **is** evaluated there.

```bash
python -m pytest experiments/pi_external_runtime_ar2/tests -q
```

## Evidence retention

Committed: bounded scripts, sanitized structured result records, findings,
fixtures, and `experiment_config.example.json`.

Never committed: credentials, `Authorization` material, operator-local runtime
config, any file containing a base URL, host or IP, reasoning content, disposable
repositories, generated extension directories, caches.

Every emitted artifact passes the `emit_or_refuse` choke point. AR2 adds the
per-run broker token, the capability id, the pipe name and the **endpoint host**
to what the scrub refuses; a finding records a bounded **code**, never the needle.

Result records are append-only history. See `FINDINGS.md` for the one
post-hoc safety redaction that was applied, and why.
