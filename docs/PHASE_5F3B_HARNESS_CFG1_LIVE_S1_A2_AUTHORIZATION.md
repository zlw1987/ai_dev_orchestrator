# Phase 5F3B-HARNESS-CFG1-LIVE-S1-A2-AUTH — Fresh Stage-1 Execution Authorization

```text
5F3B-HARNESS-CFG1-LIVE-S1-A2-AUTH CANDIDATE — PENDING INDEPENDENT REVIEW
```

> **THIS DOCUMENT IS A CANDIDATE. IT IS NOT YET AN AUTHORIZATION.**
>
> It carries no execution authority of any kind until an independent human
> reviewer has inspected the committed form of this file and explicitly
> accepted it. Until that acceptance is recorded, execution under
> `CFG1-S1-A2` is **NOT AUTHORIZED**.
>
> **Authoring this file is not, and never becomes, permission to run Stage 1 in
> the same turn, session, or agent invocation that produced it.** The turn that
> wrote this file imported no CFG1 module for execution, called neither
> `establish_stage_output_authority` nor `run_cfg1_stage`, launched no Pi
> process, contacted no B300 endpoint, opened no socket, made no model call,
> read no credential or endpoint value, created no directory under the CFG1
> results root, and produced no run artifact.

---

## 0. Document semantics

### 0.1 Status

| Item | Status after this document is written | Status after independent acceptance |
|---|---|---|
| `CFG1-S1-A1` | **consumed**, halted; historical evidence only | **consumed**, halted; historical evidence only — unchanged |
| `CFG1-S1-A2` | **NOT AUTHORIZED** (candidate only) | authorized for **exactly one** fresh Stage-1 execution |
| `CFG1-LIVE-S2` | **NO-GO** / separate conditional authorization | **NO-GO** / unchanged |
| arm `H` | not authorized | not authorized / unchanged |
| `DX1` | **NO-GO** | **NO-GO** / unchanged |
| `M4` | **HOLD / NO-GO** | **HOLD / NO-GO** / unchanged |
| Qualification (Q1/Q2/Q3) verdicts, rankings, lineage, OBS1 companions | frozen, untouched | frozen, untouched |
| `docs/PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md` | frozen, unmodified | frozen, unmodified |
| `docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_AUTHORIZATION.md` (the A1 authorization) | unmodified | unmodified |

Acceptance is recorded **outside** this file, by the reviewer. This document
contains no self-acceptance mechanism, no conditional activation clause, and no
"valid unless objected to" wording.

### 0.2 Authority relationship

This document is **subordinate** to, in order:

1. the frozen design,
   [`PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md);
2. the shipped CFG1 implementation, at the same code the A1 authorization
   covered — no production file under `experiments/pi_harness_cfg1/` has changed
   since, and the repository HEAD at authoring time is
   `eea76c100895ca0be028ba474682a15487a53c2e`;
3. the accepted A1 authorization,
   [`PHASE_5F3B_HARNESS_CFG1_LIVE_S1_AUTHORIZATION.md`](PHASE_5F3B_HARNESS_CFG1_LIVE_S1_AUTHORIZATION.md),
   whose scope A2 inherits (§3).

Where this document could be read as disagreeing with any of them, **they govern
and this document is wrong**. Where it could be read as disagreeing with the
shipped code, **the code's fail-closed refusal governs**. Nothing here instructs
the implementation to accept an input it would otherwise refuse, or to skip a
proof it would otherwise perform.

A1 authorization §3.7 and frozen design §14.1 item 4 require, for any Stage-1
execution after a halt, a "new, separately reviewed authorization document
naming a new, never-used `stage_execution_id`". **This document is currently
only a candidate for that role.** It satisfies that requirement **if, and only
if,** it is independently reviewed and explicitly accepted by a human, with that
acceptance recorded outside this file. Authoring this document, committing it,
or pushing it grants no authority of any kind. It does, however, already
answer the question those sections require such a document to answer
explicitly (§2.3): **no earlier run participates in any contrast.**

### 0.3 The entire delta from A1

A2 inherits the accepted A1 authorization scope **unchanged**, except for
exactly three items:

1. the new `stage_execution_id` literal `CFG1-S1-A2` (§1);
2. an explicit **operator-side** credential-carrier precondition (§4);
3. the explicit non-participation of all A1 evidence in A2 (§2).

Nothing else is supplied, selected, reopened, or relaxed.

---

## 1. Authorization-supplied fact: the `stage_execution_id`

### 1.1 The literal

```text
CFG1-S1-A2
```

This is the **only** authorization-supplied value in this document.

### 1.2 Grammar conformance

The shipped `stage_output._require_valid_stage_execution_id` requires
`type(value) is str` and `re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value)`.
`CFG1-S1-A2` is a plain ASCII `str` of length 10 drawn entirely from
`[A-Za-z0-9_-]`: no `/`, `\`, `.`, `:`, NUL, control character, whitespace, or
non-ASCII character. It cannot name a subdirectory, traverse, or widen
filesystem authority, for the same reasons A1 authorization §2.2 records. It is
transmitted **verbatim** — never trimmed, case-folded, normalized, suffixed, or
repaired by any layer (A1 authorization §2.3 applies unchanged).

It is a fixed, human-chosen literal. It encodes no clock value, counter,
hostname, or process id, and is not derived from anything at runtime.

### 1.3 Evidence that the literal is unused (established offline, at authoring)

Checks against this checkout at HEAD `eea76c100895ca0be028ba474682a15487a53c2e`:

| Check | Method | Result |
|---|---|---|
| present in any tracked file's content | `git grep -n "CFG1-S1-A2" -- .` | no match |
| present in working-tree content, tracked or not | recursive content grep excluding `.git/` and `.venv/` | no match |
| present in any commit reachable from any ref | `git log --all -S "CFG1-S1-A2"` | no commit |
| present as a path in any reachable commit | `git log --all --name-only`, filtered | no match |
| present as a file or directory **name** | recursive name search excluding `.git/` | no match |
| `RESULTS_ROOT/CFG1-S1-A2` exists | existence test only | **absent** |
| `RESULTS_ROOT` contents | listing only | exactly one child, `CFG1-S1-A1/` (§2.1) |

These checks created, modified, renamed, or deleted nothing. As with A1, they
cover **this checkout only** (A1 authorization §2.6). Reuse is refused
mechanically at runtime by exclusive create at `EXECUTION_DIRECTORY_EXISTS`,
which remains the authoritative check.

---

## 2. A1 isolation

### 2.1 What A1 is

`CFG1-S1-A1` was genuinely executed under the accepted A1 authorization and is
**permanently consumed**. Its durable evidence is exactly:

```text
RESULTS_ROOT/CFG1-S1-A1/S1_01_Q.json
RESULTS_ROOT/CFG1-S1-A1/S1_stage_closure.json
```

Its bounded, AIDO-emitted fields record: ordinal 1 (arm `Q`) classified
`REFUSED_PRE_DISPATCH` with `pre_dispatch_refusal_code =
CREDENTIAL_BOUNDARY_FAILED` at `refused_at_step = L4`, and the stage halted
after ordinal 1 with `halt_reason_code = PRE_DISPATCH_REFUSAL`. Ordinals 2–9
were not executed.

For the reviewer's integrity check only, the SHA-256 of each A1 artifact's
bytes as they existed at authoring time:

```text
315e5780a07ab3da3fdee5dd38f61b6797690db389217e1b8275200b28219cec  S1_01_Q.json
fee44394ed8a942bdaed805dd3336c8b90bf15e4d6075e768ac545aab22bcfb3  S1_stage_closure.json
```

These are digests of AIDO's own emitted evidence files, not of any credential
or endpoint.

### 2.2 A1 remains valid historical evidence

`CFG1-S1-A1` **remains valid historical evidence of a halted execution.** A1 is
**permanently consumed**. Nothing in this document retires, supersedes,
invalidates, reinterprets, or amends that evidence, and nothing in A2 depends
on it.

### 2.3 A1 does not participate in A2

- **No A1 ordinal participates in A2's contrasts.** No contrast, comparison,
  count, tally, or Stage-1 outcome computed for A2 includes any A1 run.
- **No A1 run is reused, replayed, substituted, merged, counted, or
  backfilled** into A2, in whole or in part, by any layer or any operator.
- **A2 begins again at Stage-1 ordinal 1**, and runs the full frozen schedule
  from its start. A2 is not a continuation of A1 and does not "resume after
  ordinal 1".
- **A2 gets its own fresh result namespace**, `RESULTS_ROOT/CFG1-S1-A2/`,
  created once by `establish_stage_output_authority`. A2 writes nothing into
  `RESULTS_ROOT/CFG1-S1-A1/`.
- **A1 artifacts remain untouched.** They must not be read as runtime
  authority, edited, normalized, pretty-printed, renamed, moved, copied,
  deleted, or regenerated — before, during, or after A2.

### 2.4 What A2 is not

A2 is a **completely fresh** Stage-1 execution under a new identifier. It is
**not** a retry of A1, **not** a resume of A1, **not** a replacement of A1's
ordinal 1, and **not** a second attempt within A1. This document grants no
authority whatsoever under `CFG1-S1-A1`, and `CFG1-S1-A1` may not be used again
for any purpose.

---

## 3. Inherited scope — referenced, unchanged

Upon acceptance, exactly one Stage-1 execution under `CFG1-S1-A2` may proceed,
bounded by **A1 authorization §3 through §7, inherited verbatim** with
`CFG1-S1-A1` read as `CFG1-S1-A2` wherever it names the execution id or the
execution directory. In summary — the A1 authorization and the frozen code
govern, and these rows are pointers, not selections:

| Bound | Value (frozen fact) |
|---|---|
| model | exactly `qwen3-coder-next` |
| provider id | exactly `b300_pi_qualification` |
| backend gateway class | exactly `b300_litellm_proxy` |
| Pi version / seam digests | exactly `0.85.1` / the shipped `PINNED_PI_SEAM_DIGESTS`, re-proven at L1 |
| live environment inputs read by the harness | exactly `AIDO_LITELLM_BASE_URL` and `PI_QUALIFICATION_B300_ROUTE_KEY`, at L4 only |
| schedule | `Q R E / R E Q / E Q R`, from `schedule.py`, never supplied |
| runs | at most 9 admitted, strictly sequential |
| prompt writes | at most one per admitted run |
| `GET /models` | at most one, at L7, per admitted run |
| retries | zero, at every layer |
| halt | stop; no resume |
| task / prompt / fixture | `CFG1-T1`, `fixture.CFG1_T1_PROMPT` verbatim, pinned revision |
| token policy | no AIDO `maxTokens` |
| output authority | exactly `RESULTS_ROOT/CFG1-S1-A2/` |
| qualification | isolated; no credit, no rerun, no authority-use |

Not reopened, in any respect: model, route, Pi version, seam digests, schedule,
prompt, fixture, lifecycle (L0–L30), closure predicates, halt behavior and
`HALT_REASON_CODES`, filesystem authority, qualification isolation, the retry
prohibition, the token policy, the child-environment policy, Stage 2, `DX1`,
`M4`.

The single covered invocation surface is A1 authorization §7, unchanged:
`stage_output.establish_stage_output_authority(stage_id="S1",
stage_execution_id="CFG1-S1-A2")`, whose result is passed positionally to
`stage_runner.run_cfg1_stage`, and nothing else.
`_run_cfg1_stage_with_injected_executor` is not covered. How the operator makes
the package importable in the launcher process is not an authorization
parameter, selects nothing, and grants nothing.

### 3.1 Consumption boundary

`CFG1-S1-A2` is **consumed the moment `establish_stage_output_authority` is
called with it**, whatever happens afterwards: an authority-establishment
refusal, a preflight refusal, a credential refusal, a route refusal, a Pi
failure, a run halt, an evidence failure, or completion. It is spent by that one
use. Any later Stage-1 execution requires another new, separately reviewed
document with another never-used identifier.

---

## 4. Operator-side credential-carrier precondition

### 4.1 Why this section exists

A1 halted at L4 with `CREDENTIAL_BOUNDARY_FAILED`. The operator subsequently
established, **by name-only checks**, that in the launcher environment
`AIDO_LITELLM_BASE_URL` is present, `PI_QUALIFICATION_B300_ROUTE_KEY` is
absent, and the existing operator-controlled B300 credential is held under the
name `AIDO_LITELLM_API_KEY`. No value was disclosed.

The frozen harness is **correct** to read only its own carrier name, and it is
**not** changed. The remedy is entirely outside the harness.

### 4.2 The precondition

> **`PI_QUALIFICATION_B300_ROUTE_KEY` must be present, holding a non-empty
> value, in the live launcher process before A2 is invoked. The source of that
> value is the already-existing, operator-controlled `AIDO_LITELLM_API_KEY`. The
> mapping is established by the operator, outside the harness, in the same
> launcher session only.**

Stated precisely:

1. **Session-scoped only.** The carrier exists only in the launcher process
   environment (for example, the one CMD session from which A2 is invoked). It
   is not persisted: not with `setx`, not in user or system environment
   settings, not in a script file, batch file, `.env` file, profile, or config
   file, and not in the repository.
2. **Value never exposed.** Neither value is printed, echoed, logged,
   displayed, copied to the clipboard, written to disk, hashed, measured, or
   partially rendered — no prefix, suffix, length, or fingerprint of either.
3. **Name-only checks only.** Before invocation, the operator may confirm by
   **name only** — a check that outputs `PRESENT`/`MISSING` and never the value
   — that `AIDO_LITELLM_API_KEY` is present, and afterwards that
   `PI_QUALIFICATION_B300_ROUTE_KEY` is present. Environment enumeration that
   prints values (for example, bare `set`) is not permitted.
4. **The carrier must hold the source's actual value.** The source variable must
   be confirmed present **before** the mapping is made. A carrier holding an
   empty value, a placeholder, or an **unexpanded variable-reference literal**
   is not a valid carrier. In CMD in particular, referencing an undefined
   variable can leave the literal reference text in place rather than an empty
   string. L4 accepts any non-empty value, so such a literal would pass L4 and
   then fail only at the L7 authenticated route check — after a `GET /models`
   has been issued and after `CFG1-S1-A2` has been consumed.
5. **The endpoint is unchanged.** `AIDO_LITELLM_BASE_URL` is already present and
   is used as-is. This document sets, changes, or selects no endpoint.

### 4.3 What this precondition does NOT authorize

- CFG1 source code reading `AIDO_LITELLM_API_KEY`, under that or any other name;
- any fallback credential discovery, alias table, or second credential name in
  production code;
- `.env` loading, config-file credentials, CLI credential flags, or interactive
  credential prompts;
- credential enumeration, by any tool or layer;
- printing, persisting, hashing, or measuring either value;
- credential aliasing inside production code, the harness, or the tests;
- any change to the frozen L4 boundary, its position after L1–L3, or what it
  reads;
- any change to which children receive the carrier.

### 4.4 Residual facts, stated honestly

- The launcher process will contain **both** names. The Pi child environment is
  constructed from a **positive allowlist**, into which the frozen carrier
  `PI_QUALIFICATION_B300_ROUTE_KEY` is explicitly inserted. The generic name is
  not on that allowlist, so **`AIDO_LITELLM_API_KEY` is not forwarded to the Pi
  child**. The allowlist, not the forbidden-name check, is what withholds it;
  the check is a secondary guard that refuses the launch if any
  non-carrier name matching a forbidden fragment is ever present in the built
  environment.
- The frozen `audit_withheld_names` helper, where it is used, returns only a
  **count** of sensitive ambient names detected, the list and count of
  sensitive names **actually forwarded** to the child, and the list of profile
  names actually forwarded. It does **not** return or expose a list of
  sensitive ambient names that were merely present and successfully withheld.
  The genuine CFG1 live path grants no durable-evidence field for the generic
  variable's name.
- **`AIDO_LITELLM_API_KEY` is not forwarded to the Pi child, and this A2
  authorization grants no authority to add its name or value to CFG1 durable
  evidence.** Nothing here changes the frozen child-environment policy.
- Both carriers hold the **same** secret value. The frozen L29 scrub needles
  therefore cover it through the carrier the harness reads.
- **Redaction and scrubbing remain a backstop.** Nothing here claims any
  retained artifact is provably secret-free, and nothing here claims the Pi
  child was sandboxed, its descendants stopped, or backend inference stopped.

---

## 5. What this document explicitly does NOT authorize

1. Any execution, retry, resume, continuation, replay, or reuse under
   **`CFG1-S1-A1`** — A1 is consumed.
2. Resuming A1 "from ordinal 2", or treating A2 as a continuation of A1.
3. **Stage 2 / `CFG1-LIVE-S2`** — not authorized, not made conditionally
   available, and not made eligible.
4. **Arm `H`** — no `H` run, config, or digest use.
5. **`DX1`** — NO-GO. **`M4`** — HOLD / NO-GO.
6. **Retries** of any kind within A2, at any layer.
7. **Reorder, replacement, replay, or repetition** of any A2 ordinal.
8. **Fallback, secondary, or substitute models**, or any other route.
9. **A second execution** under `CFG1-S1-A2`, in this repository or any other.
10. **Resumption after an A2 halt**, under this or any existing identifier.
11. **Any change** to production code, tests, the frozen design, the A1
    authorization, `CLAUDE.md`, OBS1, AR2, qualification code, or qualification
    artifacts.
12. **Any new capability**: no fixer, no model-backed implementer, no reviewer,
    no agent loop, no commit, branch, push, PR, or GitHub write.

---

## 6. Reviewer acceptance

An independent human reviewer should satisfy themselves, at minimum, that:

1. `CFG1-S1-A2` matches `re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ...)` and that
   `RESULTS_ROOT/CFG1-S1-A2` is still absent at review time;
2. the A1 artifacts still exist, unmodified, with the §2.1 digests;
3. §2 excludes every form of A1 reuse and §5 refuses every form of A1 retry or
   resume;
4. §4 is an operator-side precondition only, and changes no harness behavior;
5. no credential value, endpoint, host, port, URL, IP address, key, or
   secret-derivative appears anywhere in this file;
6. Stage 2, `H`, `DX1`, `M4`, retries, and fallback models are each refused;
7. the diff for this phase touches exactly this one file.

Until that acceptance is recorded, the status is, and remains:

```text
5F3B-HARNESS-CFG1-LIVE-S1-A2-AUTH CANDIDATE — PENDING INDEPENDENT REVIEW
CFG1-S1-A1    CONSUMED (halted after ordinal 1, PRE_DISPATCH_REFUSAL)
CFG1-S1-A2    NOT AUTHORIZED
CFG1-LIVE-S2  NO-GO / separate conditional authorization
DX1           NO-GO
M4            HOLD / NO-GO
```
