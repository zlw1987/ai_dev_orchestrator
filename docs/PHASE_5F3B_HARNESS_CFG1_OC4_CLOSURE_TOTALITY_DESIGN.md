# Phase 5F3B-HARNESS-CFG1-OC4 — Closure-Ladder Totality (Design)

```text
5F3B-HARNESS-CFG1-OC4-CLOSURE-TOTALITY-DESIGN        CANDIDATE — PENDING REVIEW
(FU1 applied: OC4-R1 D-3 bound to AIDO's own launch attempt;
 OC4-R2 exception-totality domain narrowed to continued execution)
REPOSITORY HEAD AT START   2e8e6a96310e46cde40e49ad684ec1911f011f57
                           (documentation-only governance commit; no runtime
                            file differs from 7f31217 — verified: git diff --stat
                            7f31217 HEAD touches two docs/ files only)
EFFECTIVE FROZEN IMPLEMENTATION
                           7f31217580b21027556b2061d5e765c7eef162c0
EFFECTIVE FROZEN DESIGN CHAIN (read together; none is edited here)
  (1) FU1 R6 base design
      docs/PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md
      SHA-256  f9287e8929fb0093f8e99a67b8a665387a249bf27ad5c414a465c0c067058bd0
      git blob c5d2f86ecbe6281afec5737b5d3592d4fd49d6ff
  (2) OC3 AMEND1   frozen at e1910c9e4c9846686604d8607d67ca4c9d554ec8
      docs/PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_OC3_AMEND1_DESIGN.md
      SHA-256  bd8569e460e5e2ffccb33d63f3d70e41ea3007246207a43ee27a754ba055c14e
      git blob 9b20c4631102ef3637005c4fb0d326524a7fb220
  (3) Y6 AMEND2    frozen at 90d45ff47caf05a116ba32cf62a067121961ad12
      docs/PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_Y6_AMEND2_DESIGN.md
      SHA-256  b43b9c1a34c6176876425223ed420802e7bc3242c589b4954ae292dc0643ec9d
      git blob 0ad760021c78fa00d5496bf958d9873114e9c4e8
  (4) FU1 implementation   ACCEPTED / FROZEN at 7f31217
GOVERNING POLICY
      docs/AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md
      SHA-256  c4f19366f125d5a30aebdfccae9c083480d67ae7c29aae4b2d533365637db206
      git blob 50fe2e8a1f013940246162fede5da14e17112dd8
(all identities re-verified by the turn that wrote this file:
 sha256sum + git hash-object)

OC-3        CLOSED BY PROBE REMOVAL
OC-4        OPEN — THIS DOCUMENT IS ITS DESIGN (explicit pre-A4 barrier item 4)
OC-5        OPEN — separate later phase (NOT touched here)
A4          NO-GO
Stage 2     NO-GO
AR2 live    NO-GO while OC-6 remains unresolved

DURABLE SCHEMA GROWTH        NONE (§8)
NEW RECORD KIND              NONE
NEW LIFECYCLE STEP           NONE
NEW HALT REASON              NONE
NEW CONSOLE CODE             NONE
GRANTS NOTHING. NO IMPLEMENTATION AUTHORITY.
```

> **THIS DOCUMENT IS A DESIGN CANDIDATE. IT GRANTS NOTHING.**
>
> It freezes **what must be true** of the L21 → L27 closure ladder after a
> future, separately authorized implementation phase. It does not edit any
> frozen design file, any production source, any test, any governance or
> authorization document, or `CLAUDE.md`. It authorizes no live run, no A4, no
> Stage 2, and reserves no identifier.
>
> **Disclosure of what the turn that wrote this file did (exact).** It read
> `run_executor.py`, `run_contract.py`, `lifecycle.py`, `stage_runner.py`,
> `run_workspace.py`, `halt.py` (admission + precedence), `records.py` (v2 run
> validator and builder), the L24 scrub entry points of `config_issuance.py` /
> `extension_issuance.py`, `win_config_authority.held_retained_count`, the AR2
> `PiRpcSupervisor.shutdown` / `stdout_state` / `stderr_snapshot` / `process`
> definitions, the offline doubles in `tests/cfg1_doubles.py`, and the source
> audits that name `_closure_phase`. It ran the existing offline CFG1 suite
> with every Node/Pi-executing test deselected. It ran no Node, no Pi, no
> model, no network, touched no credential, and wrote exactly this one file.

---

## 1. Status, base, and frozen dependencies

See the header block. The runtime code this design analyses is byte-identical
at `2e8e6a9` and `7f31217` (the only commit between them adds two `docs/`
files). Every line reference below is to `2e8e6a9`:

| File | git blob at `2e8e6a9` |
|---|---|
| `experiments/pi_harness_cfg1/run_executor.py` | `8e36f1dc28ab506545ab5bd1730baf20c2b0cf25` |
| `experiments/pi_harness_cfg1/stage_runner.py` | `3f4aa9e7b12a59b86575ac28cb491f56513befb9` |
| `experiments/pi_harness_cfg1/run_workspace.py` | `d7a7d776cd6385ce39bcf338bec69e7594ad38e0` |
| `experiments/pi_harness_cfg1/lifecycle.py` | `e9c8fecfd5271a8d10fa9a11b1abd2cdc192cbca` |

Everything frozen by R6, AMEND1 and AMEND2 stays frozen. In particular this
design does **not** reopen: W semantics (R6 §8), the three executor modes (R6
§9.2), the dispatch write-ahead (R6 §9.3), the L9/L11 write-ahead scrub facts
(R6 §9.2a), retained-handle authority H_c/H_r/H_s, the exact-object content
scrub, writer-failure cleanup, the L24/L27 separation, foreign same-name
handling, the same-user-copy residual (all AMEND2), the Sec. 37.4.1 repository
exactness predicate, the Sec. 37.4.2 verification-count refusal sentinel, the
L26 eligibility conjunction, `compute_lifecycle_closure_v2`, the v2 record
validator, the six-code halt vocabulary, or its precedence.

---

## 2. The OC-4 defect, stated exactly

The frozen finding (R6 §16, OC-4 row; R6 D-5):

> `_closure_phase` is not total: a non-`dict` from `supervisor.shutdown()` or
> `shutdown_for_cfg1()` raises out of `execute_cfg1_run`, skipping remaining
> closure (incl. L27) and producing no record (`RUN_EXECUTOR_RAISED`).

Mechanically, at `2e8e6a9`:

1. `execute_cfg1_run` (`run_executor.py:522-567`) wraps **only**
   `_dispatch_phase` in `try`. The call `_closure_phase(...)` at `:552` is
   unguarded.
2. Inside `_closure_phase` (`:1085-1340`) each step guards **the port call**
   but, at several sites, **consumes the returned object outside the guard**,
   and at other sites touches a port-supplied object before any guard.
3. Any `Exception` escaping `_closure_phase` escapes `execute_cfg1_run`. The
   stage runner (`stage_runner.py:526-530`) reduces it to
   `Cfg1StageRunnerError("RUN_EXECUTOR_RAISED")` after retiring the authority.

Consequences of one such escape (all observable today):

- every later closure step is **skipped** — including the L24 handle-bound
  scrub of endpoint- and token-bearing material and the L27 workspace removal;
- `compute_lifecycle_closure_v2` never runs; no `lifecycle_all_closed` /
  `lifecycle_failure_steps` is finalized;
- no run record and no refusal record exists for the ordinal; the stage ends by
  exception, with no stage-closure record;
- the run-scoped registries (issuance, retained handles, workspace) are left
  populated in the process.

This is fail-closed in the weak sense (the stage does not continue) but it is
**not closure-total** and it **loses authoritative evidence**. Under
`AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md` §1 it blocks because it can
skip required cleanup (including the L24 sensitive-material scrub), lose
authoritative run evidence, and make the required closure lifecycle
mechanically non-total.

---

## 3. Actual escape-point and malformed-consumption inventory (L21-L27)

Every operation in the current closure ladder that can execute foreign code or
consume a foreign value, with its current guard status. **E-n** = an escape out
of `execute_cfg1_run` today. **M-n** = a contained site that nonetheless
commits a malformed or manufactured fact. **OK** = total and truthful today.

### 3.1 L21 — runtime teardown (`:1096-1115`)

Owns: the direct runtime child's exit observation and both reader EOFs.
Durable facts: `runtime_exit_observed`, `runtime_transport_eof_observed`
(and, as the applicability input, `runtime_created` from L14).

| # | Operation | Foreign code? | Guarded? | Status |
|---|---|---|---|---|
| E-1 | `getattr(state.supervisor, "process", None)` in the applicability test (`:1097`) | attribute lookup / property on a port-built object | **no** | escape |
| — | `state.supervisor.shutdown()` (`:1099`) | yes | yes → `record = {}` | OK |
| E-2 | `record.get("exit_status_observed")` (`:1102`) | `.get` on the returned object; a non-`dict` raises `AttributeError`, a hostile mapping runs code | **no** | escape |
| M-1 | `... is not None` as the exit proof (`:1102`) | none | — | any non-`None` value (`"x"`, `[]`, a foreign object) becomes `runtime_exit_observed = true` — a malformed shutdown result manufactures a positive closure fact |
| — | `stdout_state()`, `stderr_snapshot()` (`:1105`, `:1110`) | yes | yes → `{}` | OK |
| E-3 | `stdout_state.get("eof")` (`:1114`) | `.get` on returned object | **no** | escape |
| E-4 | `stderr_state.get("eof")` (`:1115`) | `.get` on returned object (only reached if stdout EOF is exactly `True`) | **no** | escape |

Raw-diagnostic exposure: the genuine AR2 `shutdown()` record carries
`claim_scope` prose and, on an `OSError`, `stdin_close_error` text; the genuine
`stderr_snapshot()` carries `text_tail` (up to 4000 characters of Pi stderr).
Today only `exit_status_observed` and `eof` are read and neither dict is
retained — that property must be preserved (§10).

### 3.2 L22 — broker diagnostic counts (`:1118-1141`)

Owns: diagnostic evidence only (not teardown). Durable facts:
`broker_recorded_activity_available` and four
`broker_recorded_*_count` fields.

| # | Operation | Status |
|---|---|---|
| — | `diagnostics_counts()` and all four subscripts are inside one `try` | no escape — **OK for totality** |
| M-2 | partial commit: when **one** of the four raw values is malformed, `available` becomes `False` but the other three are still committed as their exact (possibly non-zero) values (`:1132-1139`) | the v2 validator refuses an unavailable broker family that carries any non-zero count (`records.py:1350-1353`, `UNAVAILABLE_BROKER_FAMILY_CARRIES_COUNTS`), so a malformed diagnostic with any non-zero sibling converts the run record into a self-validation refusal and a `RUN_RECORD_SELF_VALIDATION_FAILED` halt instead of the designed `INDETERMINATE_NO_ACTIVITY_EVIDENCE` routing. Not an escape, but the committed state is not one the frozen validator accepts. (Unexercised today: every offline double returns all-zero counts.) |
| — | container is not required to be an exact `dict`: a mapping subclass's `__getitem__` runs inside the `try` | contained; see §6.2 for the exact-type requirement |

### 3.3 L23 — broker shutdown (`:1144-1156`)

Owns: broker state closure, pending-operation reaping, worker termination.
Durable facts: `broker_state_closed`, `broker_pending_unreaped_zero`,
`broker_worker_terminated_or_absent`.

| # | Operation | Status |
|---|---|---|
| — | `state.broker.shutdown_for_cfg1()` | guarded → `lifecycle = {}` — OK |
| E-5 | `lifecycle.get(...)` ×3 (`:1149-1156`) on the returned object | **escape** on a non-`dict`; hostile `.get` runs code |
| E-6 / M-3 | `lifecycle.get("state_reached") == "CLOSED"` (`:1149`) | the **left** operand is foreign: its `__eq__` runs, can **raise** (escape), or can return a non-`bool` object that is then **committed** as `broker_state_closed` — a foreign live object inside `observations`, which (a) fails the v2 validator's bool check and (b) falsifies the "outcome carries no live reference" property (§9) |
| E-7 | the L26 eligibility conjunction `observations["runtime_exit_observed"] and ... and observations["broker_state_closed"] and ...` (`:1201-1207`) | if M-3 committed a foreign object, `and` invokes its `__bool__` — **escape** (or a truthy foreign object makes verification run on a closure that was never proven) |
| M-4 | `lifecycle.get("worker_termination_observed", True)` (`:1155`) | a **missing** member defaults to `True`: `broker_worker_terminated_or_absent` is manufactured from a default. The genuine adapter always supplies the member (as an exact `bool`), so this fires only on a malformed return — which is exactly the domain OC-4 must make fail closed |

### 3.4 L24 — generated sensitive-material scrub (`:1165-1168`, helpers `:1038-1082`)

Owns: the two AMEND2 handle-bound content scrubs. Durable facts:
`generated_config_scrub_verified`, `extension_binding_scrub_verified`.

| # | Operation | Status |
|---|---|---|
| E-8 | `getattr(state.generated_config, "issuance_token", None)` (`:1053`) — **before** the helper's `try` | escape on a hostile port-returned config object; **and** because the escape leaves `_closure_phase`, the extension scrub is skipped — a violation of AMEND2's independence rule |
| E-9 | `getattr(state.extension, "issuance_token", None)` (`:1073`) — **before** the helper's `try` | escape |
| — | `scrub_*_issuance(...) is True` inside `try` → `False` on raise | OK. The callees type-check the token with `type(token) is not str` before any registry access, so a foreign token object never has code executed inside them |

Everything else about L24 is total and is left exactly as AMEND2 froze it.

### 3.5 L25 — Git observation #1 (`:1171-1198`)

Owns: an observation, not a closure fact. Durable facts:
`git_observation_1_performed`, `head_moved`, `changed_tracked_paths`,
`untracked_path_count`, `staged_path_count`, `broker_git_cross_check_agrees`.

| # | Operation | Status |
|---|---|---|
| — | authority re-verification, `observe_repository`, `registered_baseline`, the Sec. 37.4.1 predicate, projection and cross-check are all inside one `try` | **OK** — total. Commit order sets `performed = True` before the other fields, but nothing after that point can raise (every projected value is already an exact `str`/`int`/`list[str]`), so no partial state is reachable. §6.5 still freezes locals-then-commit so a future edit cannot create one. |

### 3.6 L26 — verification + Git observation #2 (`:1200-1300`)

Owns: `verification_child_reaped_or_not_started` (closure fact) and the
verification/observation-#2 facts.

| # | Operation | Status |
|---|---|---|
| — | eligibility reads only executor-owned facts (but see E-7) | OK once M-3 is fixed |
| — | `ports.run_verification(...)` | guarded → `outcome = None` — OK |
| E-10 | `getattr(outcome, "started"/"completed"/"timed_out"/"output_limit_exceeded"/"return_code"/"counts"/"passed", ...)` (`:1227-1241`, `:1276`) — **outside** any `try` | escape on a hostile outcome object; and a partially completed projection has already committed earlier members |
| E-11 | `getattr(outcome, "counts", {}) or {}` (`:1241`) | foreign `__bool__` runs — escape |
| E-12 | `raw_counts.get(key, sentinel)` (`:1261`) | `AttributeError` on a non-mapping `counts` (e.g. a `list`) — escape; hostile `.get` runs code |
| M-5 | `verification_child_reaped_or_not_started = return_code is not None` (`:1280`) | a malformed non-`None`, non-`int` return code (e.g. `"0"`) commits **reaped = true** while `verification_return_code` is committed as `None`. A malformed value manufactures a positive L26 closure fact |
| — | Git observation #2: `observe_repository` + predicate inside `try` | OK |
| — | **consequence of E-10..E-12**: Git observation #2 and all of L27 are skipped | the headline OC-4 harm |

### 3.7 L27 — workspace closure (`:1307-1340`, `run_workspace.py:236-257`)

Owns: `workspace_authority_reproved`, `workspace_removed_verified`,
`workspace_residual_file_count`, and — by the registry — the run workspace's
in-memory authority.

| # | Operation | Status |
|---|---|---|
| — | applicability reads W (executor-owned `str`) and `state.workspace is not None` | OK |
| — | `verify_cfg1_run_workspace` inside `try` | OK |
| — | `remove_cfg1_run_workspace` + `removal.get(...)` inside `try` | OK for totality; `removal` is not required to be an exact `dict` (a hostile `.get` runs code inside the guard) — §6.7 tightens |
| E-13 | `discard_cfg1_run_workspace(state.workspace)` in the no-authority branch (`:1340`) — **unguarded** | By inspection the genuine function is two `dict.pop` calls on an exact type and cannot raise in ordinary operation; but it is a supported closure call site, OC-4's domain covers "an in-memory retirement that itself raises" (required case 27), and it is currently the last unguarded statement in the ladder |
| — | registry retirement **after a failed removal** | `remove_cfg1_run_workspace` calls `discard` only after `remove_disposable_tree` returns (`run_workspace.py:255-256`): a raising remover leaves the `_MINTED`/`_CLAIMED` entry **live**. That is correct and must stay so — the surviving entry is what makes stranded authority visible to L30 (§9) |

### 3.8 The transition out of closure

| Site | Status |
|---|---|
| `execute_cfg1_run` → `_closure_phase` (`:552`) | unguarded — the carrier of every E-n |
| `compute_lifecycle_closure_v2(observations)` (`:556`) | reads only executor-owned keys with `is not True` / `type(...) is` comparisons; cannot raise once every committed value is plain (§6.0 R-PLAIN) |
| `Cfg1RunOutcome(...)` (`:562-567`) | plain construction; `live_references_released=True` constant (§9) |
| stage runner: executor call (`stage_runner.py:526-533`) | `except Exception` → `RUN_EXECUTOR_RAISED`; foreign outcome type → `RUN_EXECUTOR_RETURNED_FOREIGN_OUTCOME` |
| stage runner: `build_cfg1_run_payload` (`:537`) | requires an exact `dict` with the exact v2 key set; recomputes classification. Receives only values the executor already produces today (§11) |
| stage runner: L29 emit, L30 admission, precedence, registry emptiness (`:553-651`) | unchanged by OC-4 |

**Inventory result:** 13 escape points (E-1 … E-13; E-6 and E-7 are the same
defect seen at two sites) and 5 manufactured/malformed commits (M-1 … M-5).
Every one lies inside L21 … L27. No escape exists in L25 or in Git
observation #2. The list is exhaustive for the current code: every other
closure-phase expression reads only executor-owned values of exact type.

---

## 4. The totality domain

### 4.1 What totality means here

For every run that reaches the closure phase, `execute_cfg1_run` **returns a
`Cfg1RunOutcome`** whose observations are a truthful, fail-closed account of
what each closure obligation did — given the following fault domain.

### 4.2 IN the domain (totality is required)

1. Any ordinary `Exception` **delivered through Python exception control flow**
   — one that reaches the step-local handler while the interpreter remains able
   to continue executing (including subclasses such as `AssertionError`,
   `OSError`, `KeyError`, and a `MemoryError` or `RecursionError` that a test
   double raises deliberately and after which Python keeps running; such an
   instance is handled like any other contained `Exception`, with no special
   case by type) — raised from **any** operation inside a closure step's protected region (§6.0):
   a port call, a CFG1 module function the step calls (`verify_cfg1_run_workspace`,
   `scrub_*_issuance`, `remove_cfg1_run_workspace`,
   `discard_cfg1_run_workspace`, `registered_baseline`, …), a test's
   monkeypatched replacement of one of those, or a foreign object's executable
   accessor (`__getattr__`, a property, `__getitem__`, `.get`, `__eq__`,
   `__bool__`, `__iter__`, `__len__`, `__index__`, `__int__`, `__hash__`).
2. A **malformed value** returned by a supported or injected closure port or
   helper: wrong container type, `None`, a `list`/`str`/foreign object in place
   of a `dict`, a missing member, a member of the wrong exact type (including
   `bool` where `int` is required and `int` where `bool` is required), a
   negative or out-of-domain value.
3. A malformed **applicability input** read from a port-built object (the L21
   `process` probe — read only where §6.1 permits it at all).
4. Partial failure **within** one step (one sub-obligation fails, another
   succeeds) and failure of **several** steps in the same run.

### 4.3 OUT of the domain (explicitly not claimed)

- **Persistent resource exhaustion and interpreter/runtime conditions that
  prevent continued execution** of the handler, the remaining ladder,
  observation mutation, outcome construction, or L29/L30. A synthetically
  raised `MemoryError`/`RecursionError` that a test catches is in domain (§4.2);
  *actual* persistent memory or stack exhaustion is not, because Python cannot
  be assumed able to finish the handler or any later closure step. No recovery,
  no completed outcome and no successful-completion claim is made for that
  condition, and production code does **not** special-case any exception type
  (no type test, no new error code, no new field).
- **Loss of control outside ordinary Python exception flow:** process
  termination, `TerminateProcess`/`os._exit`, power loss, OS crash, interpreter
  crash (access violation, fatal error, stack overflow in C code).
- **`BaseException` that is not an `Exception`:** `KeyboardInterrupt`,
  `SystemExit`, `GeneratorExit`, and any custom `BaseException` subclass. The
  codebase's containment convention is `except Exception` everywhere
  (dispatch phase, stage runner); OC-4 keeps that boundary. Such a raise
  propagates exactly as today.
- **Non-termination (liveness).** A port that never returns blocks the ladder.
  Totality here is over *raising and malformed return*, not over *hanging*.
  Wait bounds remain those already frozen for each resource (AR2 shutdown
  deadlines, verification timeout); OC-4 adds none and claims none.
- **Same-process tampering** with CFG1's own module state beyond the supported
  call sites (rebinding registries, patching `observations` from another
  thread, patching `compute_lifecycle_closure_v2`), and arbitrary memory
  corruption.
- **Defects in the executor's own sequencing code between steps** — i.e. a raise
  from code that touches only executor-owned, exact-typed values. By
  construction (§6.0 R-PLAIN) such code cannot raise in ordinary operation; if
  an implementation bug makes it raise, that is an implementation defect and
  must continue to surface as `RUN_EXECUTOR_RAISED` (I-8), never be laundered
  into ordinary evidence.
- **Faults after `execute_cfg1_run` returns** (L29 writer, L30, sealing): owned
  by the frozen stage runner and not changed here.
- **Finalizer output.** A foreign object's `__del__` raising is reported by
  CPython's unraisable-exception hook to `sys.stderr`, outside any AIDO sink.
  Only test doubles can do this; residual (§15).

---

## 5. Frozen closure-totality invariants

**I-1 (order and opportunity).** For every run that reaches closure, the steps
are evaluated in the fixed order L21, L22, L23, L24 (config, then extension),
L25, L26 (verification, then Git observation #2), L27. Each **applicable**
obligation is given **exactly one** permitted opportunity, in that order.

**I-2 (semantic skip only).** An obligation is skipped **only** because its
own frozen applicability predicate (§7) says it is inapplicable. No step is
ever skipped, shortened, or reordered because an earlier step raised or
returned malformed data. L26's `LIFECYCLE_UNPROVEN` / `PRE_DISPATCH_REFUSAL`
skip is a semantic skip and is preserved.

**I-3 (step-local containment).** Every in-domain fault (§4.2) is contained
**inside the protected region of the obligation it occurred in** (§6.0). It
never crosses into another obligation's region, never reaches the sequencing
code, and never leaves `execute_cfg1_run`.

**I-4 (no false success).** A contained fault never marks its obligation
successful. Each closure fact is `True` only when every input it depends on was
received, validated **before** consumption, and proven with exact type and
exact value. No default, truthiness, `==` on a foreign operand, or numeric
conversion ever produces a positive fact.

**I-5 (no rewrite of earlier facts).** A closure step never changes a fact
owned by an earlier step or by the dispatch phase — with the single, monotone,
fail-closed exception frozen as D-3 (§6.1): L21 may move `runtime_created` from
`false` to `true` (never the reverse) **only** when AIDO's own executor-owned
`runtime_launch_attempted` provenance fact is `true` and AIDO cannot prove that
no process exists. No port-, supervisor- or model-supplied claim, and no
`process` value by itself, ever supplies that authority. L27 never touches an L24 fact (AMEND2 G5). No step writes a
refusal field, `unexpected_failure_step`, `dispatch_state`, or W.

**I-6 (no second cleanup attempt).** A contained fault never triggers a retry,
a fallback remover, a second scrub, a second shutdown, a registry retirement
that the frozen contract did not already perform, or any cleanup by name or
path.

**I-7 (raw-diagnostic containment).** No exception object is bound, formatted,
stored, chained into a later raise, or read (not even its type) in a closure
handler. No port-returned container is retained past its step. Only exact
scalars defined in §6 cross a step boundary (§10).

**I-8 (no outer laundering).** There is **no** catch-all around the closure
phase as a whole (or around any span covering more than one obligation) that
converts an escape into a `Cfg1RunOutcome`. Totality is achieved by step-local
containment **only**. A raise that escapes every step-local region is, by
§4.3, an implementation defect and still surfaces as `RUN_EXECUTOR_RAISED`.

**I-9 (plain outcome).** Every value any closure step commits into
`observations` is of an exact plain type drawn from the field's existing
domain (`bool`, non-`bool` `int`, `str` literal, `None`, `list[str]`, the
verification-count `dict[str, int | None]`). No port-returned object, foreign
subclass instance, or live reference is ever committed (§9).

**I-10 (state-space closure).** Every observation state a contained fault
produces is a state the executor **already** produces today through an
existing guarded-raise path, or (D-3 only) a combination the frozen v2
validator already accepts. OC-4 routes new fault inputs to existing states; it
invents none (§8, §11).

---

## 6. Per-step failure semantics

### 6.0 Common construction rules (apply to every step)

**R-REGION.** Each obligation has one protected region comprising, in order:
(a) any applicability probe that touches a port-built object; (b) the
invocation; (c) validation of the returned value's **container** by exact type
(`type(x) is dict`, never `isinstance`, never `Mapping`); (d) reading each
required member **once** into a local; (e) validation of each local by exact
type and exact value/range; (f) the commit. Everything from (a) through (e) is
inside the containment. Containment may be finer than one step (L21, L24, L26
and L27 contain several independent obligations — each gets its own region)
but **never coarser** (I-8).

**R-COMMIT.** The commit (f) consists solely of assigning already-validated
plain locals to `observations`; it therefore cannot raise. Where a step's
facts are an all-or-nothing observation (L22 counts, L25/L26 repository
snapshots, the L26 verification outcome projection) nothing is committed until
**every** member validated. Where each fact is an independent proof whose
fail-closed value is `False` (L21 exit, L23's three facts, L27's two), each
may be committed independently, because "not proven" is already the truthful
value for a malformed member.

**R-FAILVALUE.** On any fault in a region, each fact the region owns ends at
its **fail-closed value**: the value it held at step entry when that value is
already fail-closed, or an explicit fail-closed write when the entry value
means "not created" and creation may have occurred
(`verification_child_reaped_or_not_started`, `git_observation_*_performed`).
The per-step tables below name each one.

**R-PLAIN.** No foreign value is compared with `==`/`!=` as the left operand,
tested for truthiness, iterated, `len()`-ed, hashed, or converted before its
exact type has been established; after that, only operations whose
implementation for that exact built-in type runs no foreign code are used.
`x is None`, `x is True`, `type(x) is T` and `x is y` are always safe.

**R-HANDLER.** Closure handlers are `except Exception:` **without** `as`, and
their bodies contain only constant assignments to locals or `observations`
(no call, no formatting, nothing that can raise — so no contained exception can
become the `__context__` of a later one).

**R-NOAUTHORITY-FROM-DEFAULT.** No `.get(name, <positive default>)`,
`getattr(obj, name, <positive default>)`, or `x or {}` may appear on a
closure consumption path. A missing member is a malformed input.

### 6.1 L21 — runtime teardown

Three independent observation obligations over the run's own supervisor, plus
one applicability decision.

**Launch-attempt provenance (executor-owned).** The executor keeps one
in-memory boolean, here `runtime_launch_attempted` (exact name and holder are
implementation-discretionary; a `_RunState` attribute or an executor local
both qualify):

- `false` initially;
- set `true` **immediately before** the one L14 `state.supervisor.launch()`
  invocation (`run_executor.py:871`) — i.e. after the identity re-proof has
  passed and after every earlier L14 refusal point, so a run refused before
  that call never has it set;
- **never reset** to `false`;
- **not durable**: not written to `observations`, to any record, to any port, or
  to any console/halt surface — it is not a new record field and not a new port
  field;
- **not caller-supplied**: set only by the executor's own line, never read from
  a port, a supervisor, a model, a config, an argument, or `state.supervisor`;
- **never inferred from `process`**.

It is the mechanical record of one fact only: *AIDO itself called the
side-effecting launch boundary*.

**Applicability (D-3).** Let `probe` be the contained evaluation of
`getattr(state.supervisor, "process", None) is not None`, with outcomes
`ABSENT` (exactly `None`), `PRESENT` (anything else), or `RAISED`. The probe is
**evaluated only** when `state.supervisor is not None`, `runtime_created` is
`false`, **and** `runtime_launch_attempted` is `true`. Otherwise the accessor
is not consulted at all.

| `state.supervisor` | `runtime_created` (L14) | `runtime_launch_attempted` | `probe` | L21 |
|---|---|---|---|---|
| `None` | any | any | not evaluated | not applicable |
| not `None` | `True` | (`true` necessarily) | not evaluated | **applicable** |
| not `None` | `False` | `False` | **not evaluated** | **not applicable**; `runtime_created` stays `False`; a `process` value — present, absent or raising — grants no authority |
| not `None` | `False` | `True` | `ABSENT` | not applicable (no runtime process proven) |
| not `None` | `False` | `True` | `PRESENT` or `RAISED` | **applicable**, and `runtime_created` ← `True` (D-3) |

Every L21 shutdown attempt is therefore mechanically traceable to exactly one
of two authorities: (i) `runtime_created` already `true` from the existing L14
path (`run_executor.py:878`, or `:876` after a failed launch), or (ii) AIDO's
own recorded launch attempt plus an inability to prove that no process exists.
Nothing else can make L21 applicable.

*Justification of D-3 (R6 §9.2a Category B).* Frozen runtime ownership is
`L14 PiRpcSupervisor.launch()` → this run's `Popen` → L21 shutdown on that same
supervisor/handle. Category-B facts may pessimistically increase a cleanup
obligation only where AIDO **itself** may already have caused the side effect.
When AIDO has called `launch()` and the launch raised, `runtime_created` is
`false` only if L14's own `process` probe (`:875`) reported `None` or was
itself never completed (that probe is unguarded — B-1); closure then cannot
exclude a partially created process, and leaving `runtime_created = false`
would make `compute_lifecycle_closure_v2` treat L21 as "not created, therefore
closed" — a positive closure claim about a process AIDO may have launched.
That is precisely a Category-B case: the side-effecting boundary was AIDO's own
call. In contrast, a supervisor that was merely **built** by a port, and on
which AIDO never called `launch()`, has produced no AIDO-caused side effect; a
`process` value on it is a port-supplied claim. A port-built supervisor's
`process` property is not authority, and a runtime/model/port claim cannot
create cleanup authority. A pre-launch foreign process claim is therefore
**not** reinterpreted as an AIDO-created resource and cannot cause a shutdown
call.

The write is monotone (`false -> true` only) and is the **only** permitted D-3
transition. Once E-1 is contained the fact must be corrected in the
fail-closed direction — but only under AIDO's own launch-attempt provenance —
or OC-4 would *introduce* false evidence for the launch-raised case. The
resulting combination (an L14 refusal — `RUNTIME_LAUNCH_FAILED` or
`UNEXPECTED_STEP_FAILURE` — with `runtime_created = true`) carries no v2
validator constraint (`records.py` binds `runtime_created` only in the
`NOT_ATTEMPTED` W branch, which is L1-only and never has a supervisor). A test
must prove the validator accepts it (§13, G-L21-7C/7D). With the genuine
`PiRpcSupervisor`, `process` is a read-only property derived from a private
binding and cannot raise or appear late, so D-3 changes nothing for the genuine
binding; it closes a hole that only a launch that raised can open.

The existing L16-FU2 source audit (`test_cfg1_l16_fu2.py`, the `process`-read
census) requires the closure's `process` read to be a `getattr(..., "process",
None)` directly inside an `is not` comparison. That shape is preserved; if the
implementation moves the probe into a helper, the audit's expected *owner*
entry is retargeted to that helper — never deleted or widened. The audit must
additionally continue to show that the closure's `process` read is reachable
only behind the launch-attempt condition.

**Sub-obligations (each its own region; all three are attempted whenever L21
is applicable, regardless of the others' outcome):**

| Sub-obligation | Call | Accepted shape | Proven iff | Fault → |
|---|---|---|---|---|
| exit | `shutdown()` | exact `dict`; member `exit_status_observed` present | the member is an exact `int` (not `bool`) | `runtime_exit_observed = False` |
| stdout EOF | `stdout_state()` | exact `dict`; member `eof` present | member `is True` | stdout-EOF local = `False` |
| stderr EOF | `stderr_snapshot()` | exact `dict`; member `eof` present | member `is True` | stderr-EOF local = `False` |

`runtime_transport_eof_observed = stdout_eof and stderr_eof`, computed from
the two exact-`bool` locals only after **both** calls were attempted (the
current short-circuit that skips reading stderr is removed; reading is
harmless and the two readers are independent).

- A malformed shutdown result (None, list, str, foreign object, missing member,
  `True`, `"0"`, a foreign int-like) **never** yields
  `runtime_exit_observed = true` (fixes M-1: `is not None` → exact `int`).
- A malformed stdout/stderr state **never** yields
  `runtime_transport_eof_observed = true`.
- Only the two named members are read. `text_tail`, `stdin_close_error`,
  `claim_scope` and every other member are never read; the returned dicts are
  dropped at the end of the region.
- The claim remains exactly "AIDO observed the DIRECT child's exit status and
  both reader EOFs". It is never strengthened to model, backend, inference,
  GPU, or descendant termination.
- Any L21 fault leaves L22–L27 to run.

### 6.2 L22 — broker diagnostics (diagnostic, not teardown)

Applicability unchanged: `state.broker is not None`.

One all-or-nothing region: `diagnostics_counts()` → exact `dict` → the four
members `read_operations`, `edit_operations`, `edited_paths`, `refusals` each
present and each an exact non-negative `int` (not `bool`).

| Outcome | `broker_recorded_activity_available` | four counts |
|---|---|---|
| all four exact | `True` | the four observed values |
| call raised; container not an exact `dict`; any member missing, `bool`, negative, float, str, foreign | `False` | **all four remain at the initial `0`** |

The second row fixes M-2: `available = false` with non-zero siblings is a
state the frozen v2 validator refuses (`UNAVAILABLE_BROKER_FAMILY_CARRIES_COUNTS`).
The zeros are **not** observations: `available = false` is the frozen gate
that says the family carries no evidence (classification row 5 routes it to
`INDETERMINATE_NO_ACTIVITY_EVIDENCE`). No malformed value is coerced into a
plausible count; no new field is added. The meaning of
`broker_recorded_activity_available` ("every one of the four raw facts was an
exact non-negative int") is unchanged. Any L22 fault leaves L23 to run.

### 6.3 L23 — broker shutdown

Applicability unchanged: `broker_resource_created is True`.

One region for the call; each of the three facts is an independent proof:

| Fact | Member | Proven iff |
|---|---|---|
| `broker_state_closed` | `state_reached` | member present, `type(v) is str` **and** `v == "CLOSED"` (the comparison is made only after the exact-`str` check, so no foreign `__eq__` ever runs) |
| `broker_pending_unreaped_zero` | `pending_operations_unreaped` | member present, exact `int` (not `bool`), `== 0` |
| `broker_worker_terminated_or_absent` | `worker_termination_observed` | member present and `is True` — a **missing** member is `False` (fixes M-4; the `True` default is removed) |

- Call raises or returns a non-exact-`dict` → all three `False`.
- One malformed member → only that fact is `False`; the others still reflect
  their own members (required case 15).
- The distinction between "state closed", "pending proven zero" and "worker
  termination observed/absent" is preserved; none is inferred from another.
- Only these three members are read; `worker_error` (raw text) is never read.
- Fixes E-5, E-6/M-3 and, as a consequence, E-7: every committed L23 value is
  an exact `bool`, so the L26 eligibility conjunction runs no foreign code.
- Any L23 fault leaves L24–L27 to run.

The genuine `_Cfg1BrokerAdapter.shutdown_for_cfg1` is **unchanged**: it already
returns an exact `dict` with all three members and pre-reduces only
`worker_termination_observed` with `_exact_bool`, which the FU2 source audit
pins.

### 6.4 L24 — sensitive-material scrub (AMEND2 preserved exactly)

Applicability unchanged: config iff `state.generated_config is not None`;
extension iff `state.extension is not None`.

Two independent regions. The **only** change is that the token read
`getattr(state.<object>, "issuance_token", None)` moves **inside** its helper's
containment (fixes E-8, E-9). A raise from that read is an unproven scrub:
the fact stays at its L9/L11 write-ahead value `False` (the helper returns
`False`), and the other scrub is still attempted.

Everything AMEND2 froze is untouched: the token is only a lookup key; the
callee type-checks it exactly before any registry access; ownership is the
ACTIVE issuance entry whose nonce matches this run's still-registered
workspace; single-shot retirement; no pathname opened, re-derived or
consulted; `True` only after the retained handle scrubbed the exact object and
released every handle; a foreign same-name object is never touched; L24
deletes no name; L27 never upgrades an L24 fact. A `False`, a raise, or a
malformed token on one scrub never skips, upgrades or masks the other.

Any L24 fault leaves L25–L27 to run. A `False` L24 fact still makes L26's
eligibility false (`LIFECYCLE_UNPROVEN`) — a semantic skip — and never
prevents L27.

### 6.5 L25 — Git observation #1

Already total (§3.5). Frozen semantics unchanged: authority re-verification
failure, observer raise, or any Sec. 37.4.1 predicate failure →
`git_observation_1_performed = False` with the not-performed shape; never
blocks closure. The implementation must keep all projection in locals and
commit `performed = True` together with its companions only after the
predicate and the cross-check computed (R-COMMIT), so no partially performed
state can ever become reachable. `broker_git_cross_check_agrees` keeps its
frozen initial value and D-4 gating (not reopened; §15 B-4).

### 6.6 L26 — verification and Git observation #2

Eligibility unchanged (`PRE_DISPATCH_REFUSAL` → skip; otherwise
`LIFECYCLE_UNPROVEN` unless the frozen five-fact conjunction holds; with M-3
fixed the conjunction reads exact bools only).

When verification is attempted, **three** regions:

**(a) invocation** — `run_verification(...)`; a raise → outcome unusable.

**(b) outcome projection** (all-or-nothing into locals; fixes E-10, E-11):

| Member | Accepted | Local |
|---|---|---|
| `started`, `completed`, `timed_out`, `output_limit_exceeded`, `passed` | read via `getattr(outcome, name, missing)`; value `is True` → `True`, anything else `False` (today's `_exact_bool` meaning) | exact `bool` |
| `return_code` | exact `int` (not `bool`) → that int; anything else → `None` | `int` or `None` |
| `counts` | see (c) | — |

If **any** accessor in (b) raises, the whole projection is discarded and the
run takes **exactly the frozen port-raise path**: `verification_child_reaped_or_not_started = False`
and every other `verification_*` fact stays at its current value (initial,
fail-closed). No member of a partially read outcome is committed. This reuses
an existing state (I-10); it invents no verification fact.

**(c) counts** — Sec. 37.4.2 is preserved exactly and extended to the
container only in the way its own rule already implies:

- `counts` must be an exact `dict`; a missing attribute, `None`, a `list`, a
  `str`, a dict subclass or any foreign object is treated as a container
  holding **no** members → all three keys become the frozen
  `_MALFORMED_VERIFICATION_COUNT` sentinel (the same result today's code
  already gives a *missing* `counts` via `{}`). No truthiness, no `.get` on a
  foreign object (fixes E-11, E-12).
- For an exact `dict`, each of `passed`/`failed`/`error` present and an exact
  non-negative `int` → that value; anything else → the sentinel.
- `verification_passed = passed_local is True and every count exact`.
- The sentinel's frozen consequence (the run record fails its own validator at
  L29 step 6 → refusal record with `RECORD_INVARIANT` → unconditional halt) is
  unchanged.

**Closure fact** (fixes M-5): `verification_child_reaped_or_not_started` is
`True` **iff** the projected return code is an exact `int`; a malformed return
code is not a reaped child.

**(d) Git observation #2** — its own region, attempted whenever verification
was attempted, **regardless** of (a)–(c)'s outcome. Frozen semantics unchanged
(Sec. 37.4.1 predicate, all-or-nothing, not-performed shape on any fault).

Any L26 fault leaves L27 to run.

### 6.7 L27 — workspace closure (W semantics preserved)

Applicability unchanged, decided by W only:

- `NOT_ATTEMPTED` → nothing to close.
- `ATTEMPTED_NO_AUTHORITY` → nothing is deleted, by name or by path; facts stay
  unproven (`L27` in `lifecycle_failure_steps`).
- `AUTHORITY_RETURNED` (and `state.workspace is not None`) → the three regions
  below.

| Region | Operation | Proven iff | Fault → | Then |
|---|---|---|---|---|
| re-proof | `verify_cfg1_run_workspace(state.workspace)` | returned without raising | `workspace_authority_reproved = False` | the **discard** region; **never** removal |
| removal (only if re-proven) | `remove_cfg1_run_workspace(state.workspace)` → exact `dict` | `removed is True` **and** `residual_file_count` exact non-negative `int` | `workspace_removed_verified = False` (container not exact `dict`, member missing/malformed, or raise) | **no** discard, **no** retry — a surviving registry entry is left live and visible to L30 |
| discard (only if not re-proven) | `discard_cfg1_run_workspace(state.workspace)` | — (in-memory retirement; no fact) | contained; no fact changes (reproved is already `False`) | a surviving registry entry, if any, is left visible to L30 |

`workspace_residual_file_count` keeps its existing reduction (`_exact_count`
of the member when the container is an exact `dict`; the initial `0`
otherwise). It is gated by `workspace_removed_verified`, which is `False`
whenever the residual was malformed — the frozen CFG1-IMPL-FU2 Finding 3 rule,
unchanged.

- No pathname is authority. A failed re-proof never deletes the tree.
- A failure while retiring the in-memory claim (in `discard`, or inside
  `remove_cfg1_run_workspace` after the tree was removed) never escapes, never
  produces `workspace_removed_verified = true`, and is **not** hidden: the
  registry entry it failed to retire survives and `minted_workspace_count()`
  reports it at L30. No caller-supplied bool stands in for that observation.
- L27 never writes an L24 fact.

---

## 7. Dependency and skip rules

| Step | Frozen applicability predicate (the ONLY reason it may be skipped) | Depends on an earlier step's *result*? |
|---|---|---|
| L21 | §6.1 table (supervisor, `runtime_created`, executor-owned `runtime_launch_attempted`, and — only when a launch was attempted — the contained `process` probe) | no |
| L22 | `state.broker is not None` | no |
| L23 | `broker_resource_created is True` | no |
| L24 config | `state.generated_config is not None` | no (the callee checks the workspace registry itself) |
| L24 extension | `state.extension is not None` | no |
| L25 | `state.workspace is not None` | no (L22's counts feed only the cross-check value, whose input is always an exact `int`) |
| L26 verification | `pre_dispatch_refusal_code is None` **and** the frozen five-fact conjunction of L21/L23/L24 results | **yes — semantic, frozen**: an unproven L21/L23/L24 → skip with `LIFECYCLE_UNPROVEN` |
| L26 Git #2 | verification was attempted | only on the *attempt*, never on the verification result |
| L27 | W; `state.workspace is not None` | no — never on L21–L26 |

Every "no" is mechanically true: each later step reads only executor-owned
exact values or its own state reference, so it can run without the failed
step's result. The only result-dependent skip is L26's, which is frozen and is
a semantic skip (I-2). **L27 never depends on L24, L25 or L26** (required case
30).

---

## 8. Durable-evidence / schema decision

**Decision: the existing durable field set is sufficient. OC-4 adds no durable
field, no record kind, no lifecycle step, no halt reason, and no console code.**

Proof by exhaustion over fault class → existing representation:

| Fault class | Existing fact(s) that record it truthfully | `lifecycle_failure_steps` | Already produced today by |
|---|---|---|---|
| any L21 sub-fault | `runtime_exit_observed` and/or `runtime_transport_eof_observed` = `false` | `L21` (if `runtime_created`) | `shutdown()` raising |
| launch was attempted by AIDO, `runtime_created` false, probe `PRESENT`/`RAISED` (D-3) | `runtime_created = true` + the two L21 facts | `L21` unless exit+EOF proven | L14 launch failure with a process (validator-accepted combination; §6.1) |
| any L22 fault | `broker_recorded_activity_available = false`, counts `0` | none (diagnostic, not closure) | `diagnostics_counts()` raising |
| any L23 fault / member fault | the corresponding L23 fact(s) `false` | `L23` | `shutdown_for_cfg1()` raising |
| any L24 fault | the corresponding scrub fact `false` (its write-ahead value) | `L24` | scrub callee raising |
| any L25 fault | `git_observation_1_performed = false` + not-performed shape | none (observation) | observer raising |
| L26 invocation/projection fault | `verification_child_reaped_or_not_started = false` | `L26` | `run_verification` raising |
| L26 malformed counts / container | Sec. 37.4.2 sentinel → record self-refusal | (record refused; stage halts) | missing `counts` attribute |
| L26 Git #2 fault | `git_observation_2_performed = false` | none (observation) | observer raising |
| L27 re-proof fault | `workspace_authority_reproved = false` | `L27` | re-proof raising |
| L27 removal fault / malformed | `workspace_removed_verified = false` | `L27` | remover raising |
| L27 retirement (discard) fault | no fact (reproved already `false`); **registry count** at L30 | `L27` | — (registry already observed by L30) |
| several of the above in one run | the union | the union (sorted) | — |

No row requires a new durable value. *Which* sub-operation failed, and whether
it raised or returned malformed data, is deliberately not recorded: the
existing facts record *what was not proven*, which is the authoritative
content; an exception-kind or error-text field is exactly the raw-diagnostic
channel §10 forbids. Fields such as `closure_exception_step`,
`closure_error_text`, or `cleanup_error` are **not** introduced.

---

## 9. `live_references_released` and registry emptiness

**What the frozen design means.** `Cfg1RunOutcome.live_references_released`
is "the run's own contribution to Sec. 19.1 item 4"; the four process-level
registries are checked by the runner itself (`run_contract.py:63-64`,
`stage_runner.py:632-651`). The outcome's docstring defines the property it
certifies: `observations` carries no live object (no supervisor, activity,
broker, `RunState`, `Popen`, handle, `Path` or authority). The executor sets it
to the constant `True`.

**Is the constant truthful after OC-4?** Yes, **by construction, conditional on
I-9**, and the condition is not met today:

- `_RunState` (every live handle) is a local of `execute_cfg1_run` and is
  unreachable from the outcome after return. `safety` is the frozen
  `ArtifactSafetyContext` of needle strings. `console_codes` is a tuple of
  closed literals.
- The only way a live reference can reach the outcome is through
  `observations`. Today M-3 can place a foreign, port-returned object there
  (`broker_state_closed = <foreign __eq__ result>`), which makes the constant
  `True` **false**. §6.3 removes that; I-9 forbids any recurrence; the
  regression matrix asserts it (G-X-3).

**Can a closure failure strand a run-owned reference?** Yes — but not in the
outcome. A failed L24 leaves an issuance entry and/or a retained handle; a
failed L27 removal or discard leaves a `_MINTED`/`_CLAIMED` entry. These are
**authority**, and each already has an independent registry count
(`issued_token_count`, `issued_extension_token_count`, `held_retained_count`,
`minted_workspace_count`) read directly by `_run_scoped_registries_empty` at
L30. Stranded authority is therefore detected **mechanically, independently of
the bool**. A live runtime process or broker thread left by a failed L21/L23
is a *resource*, not a reference held by the outcome; it is recorded by the
L21/L23 lifecycle facts and halts through `LIFECYCLE_CLOSURE_UNPROVEN`.

**Conclusion.** No change to `live_references_released` or to
`_run_scoped_registries_empty` is needed or permitted. The bool must **not**
be made conditional on closure results (that would duplicate, and could mask,
the registry observation); it stays the constant `True`, and I-9 is what makes
that constant true. Registry survival must never be hidden by setting any
caller-supplied bool.

---

## 10. Raw-diagnostic containment rule

Frozen for every closure region (R-HANDLER, I-7):

1. No `str(exc)`, `repr(exc)`, `type(exc)`, `exc.args`, traceback, or any
   attribute of a closure-phase exception is read, formatted, stored, logged,
   serialized, or printed. Handlers bind no name.
2. From each port-returned container only the members named in §6 are read.
   The genuine AR2 `stderr_snapshot()["text_tail"]`, `shutdown()["stdin_close_error"]`
   and `["claim_scope"]`, the broker's `worker_error`, verification output, and
   any provider or broker body are never read, never copied, and the container
   is not retained past its region.
3. A malformed value is never committed, echoed, or used in a message; it is
   replaced by the fixed fail-closed value of §6 (or the frozen Sec. 37.4.2
   sentinel, which is a constant `None`, not the malformed value).
4. No new console code is emitted for a closure fault; the durable
   `lifecycle_failure_steps` and the fail-closed facts are the whole report.
5. Nothing is raised inside a handler, so no contained exception is ever
   attached as `__context__` to an escaping one.

---

## 11. Stage-level L29 / L30 consequences

For every in-domain closure fault, after OC-4:

```text
closure fault (any step, any count)
  → contained step-locally; later steps still run (I-1..I-3)
  → compute_lifecycle_closure_v2 finalizes lifecycle_all_closed / failure steps
  → execute_cfg1_run RETURNS a Cfg1RunOutcome          (never RUN_EXECUTOR_RAISED)
  → L29: build_cfg1_run_payload + emit_cfg1_run_record, exactly as frozen
  → L30: _admission_conditions_hold + _resolve_halt_reason_code, exactly as frozen
```

- Because of I-10, the payload builder, classifier, validator, writer and L30
  logic see only observation states the executor already produces today; OC-4
  requires **no** change to any of them, and none is permitted.
- A closure fault in L21/L23/L24/L26/L27 makes `lifecycle_all_closed = false`.
  Under the frozen precedence (emission collision → emission failed →
  self-validation → **lifecycle** → pre-dispatch refusal → registry), such a
  run halts with `LIFECYCLE_CLOSURE_UNPROVEN` unless an emission or
  self-validation condition takes precedence.
- A fault confined to L22 or L25 or Git #2 does not affect lifecycle closure;
  the run is classified by the frozen rows (e.g. `INDETERMINATE_*`), exactly
  as for today's raising-port equivalents.
- A malformed verification count takes the frozen Sec. 37.4.2 self-refusal
  path (`RUN_RECORD_SELF_VALIDATION_FAILED`).
- A surviving registry entry makes `_run_scoped_registries_empty` return
  `False`; the stage is never admitted past that ordinal (item 4). The halt
  code is whatever the frozen precedence yields — in practice
  `LIFECYCLE_CLOSURE_UNPROVEN`, because every reachable registry survival
  coincides with an unproven L24 or L27 fact; `RUN_SCOPED_REGISTRY_NOT_EMPTY`
  applies when it is the first failing condition.
- `RUN_EXECUTOR_RAISED` remains reachable only for out-of-domain events (§4.3).

---

## 12. Partial-failure matrix

`✓` attempted and proven, `✗` attempted and unproven/failed, `—` not
applicable (semantic), `→` still attempted. Rows assume a run that reached
L18+ (all resources created) unless stated.

| # | Fault(s) | L21 | L22 | L23 | L24 cfg / ext | L25 | L26 verif. | L26 Git#2 | L27 | failure steps | stage |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | `shutdown()` returns `None` | ✗ exit, EOF → | → | → | → / → | → | — `LIFECYCLE_UNPROVEN` | — | → removal | `L21` | halt `LIFECYCLE_CLOSURE_UNPROVEN` |
| P2 | `stdout_state()` raises | exit ✓, EOF ✗ | → | → | → / → | → | — | — | → | `L21` | halt lifecycle |
| P3 | `diagnostics_counts()` returns a `list` | → | ✗ (unavailable, zeros) | → | → / → | → | → runs if closure proven | → | → | none | classified by frozen rows |
| P4 | `shutdown_for_cfg1()` returns `"CLOSED"` | → | → | ✗ ×3 | → / → | → | — | — | → | `L23` | halt lifecycle |
| P5 | L23 `state_reached` hostile `__eq__` | → | → | ✗ state; others per member | → / → | → | — | — | → | `L23` | halt lifecycle |
| P6 | config token accessor raises | → | → | → | ✗ / → **still attempted** | → | — | — | → | `L24` | halt lifecycle |
| P7 | extension scrub returns `False` | → | → | → | ✓ / ✗ | → | — | — | → **still removed** | `L24` | halt lifecycle |
| P8 | `observe_repository` #1 raises | → | → | → | → / → | ✗ not performed | → | → | → | none | frozen classification |
| P9 | verification outcome accessor raises | → | → | → | → / → | → | ✗ reaped `false` | → **still observed** | → | `L26` | halt lifecycle |
| P10 | `counts` is a `list` | → | → | → | → / → | → | sentinel ×3 | → | → | per facts | self-refusal halt (frozen 37.4.2) |
| P11 | `return_code = "0"` | → | → | → | → / → | → | reaped `false` | → | → | `L26` | halt lifecycle |
| P12 | L27 re-proof raises | → | → | → | → / → | → | … | … | ✗ reproved; **discard**, no deletion | `L27` | halt lifecycle |
| P13 | remover raises | → | → | → | → / → | → | … | … | ✗ removed; registry entry **survives** | `L27` | halt lifecycle; registries non-empty |
| P14 | discard raises (no-authority branch) | → | → | → | → / → | → | … | … | ✗ reproved; registry entry **survives** | `L27` | halt lifecycle; registries non-empty |
| P15 | P1 + P4 + P6 + P9-impossible(L26 skipped) + P13 | ✗ | → | ✗ | ✗ / → | → | — | — | ✗ | `L21 L23 L24 L27` | halt lifecycle |
| P16 | AIDO called `launch()`, it raised, later `process` probe raises/present (D-3; launch-attempt fact true) | applicable; `runtime_created ← true`; shutdown attempted | → | → | → / → | → | — `PRE_DISPATCH_REFUSAL` | — | → | `L21` unless exit+EOF proven | halt (lifecycle, else pre-dispatch) |
| P16b | supervisor built, L14 refused **before** `launch()` (launch-attempt fact false); `process` would report an object or raise | not applicable; `runtime_created` stays `false`; accessor not consulted | → | → | → / → | → | — `PRE_DISPATCH_REFUSAL` | — | → | none from L21 | frozen pre-dispatch classification |
| P17 | W = `ATTEMPTED_NO_AUTHORITY` + any L21–L26 fault | as applicable | … | … | … | — (no workspace) | — | — | nothing deleted | `… L27` | halt lifecycle |

---

## 13. Required regression matrix

All tests offline, synthetic, under `tmp_path`, driven through
`execute_cfg1_run` with `build_doubled_ports` overrides or `monkeypatch` of the
named CFG1 function; the stage-level group through
`_run_cfg1_stage_with_injected_executor` with a retargeted results root. No
Node, no Pi, no socket, no credential. Tests that deliberately leave a registry
entry must restore registry state afterwards so no later test is contaminated.

Each fault test asserts, at minimum: (i) `execute_cfg1_run` **returns** a
`Cfg1RunOutcome`; (ii) the faulting step's fact(s) are at the §6 fail-closed
value; (iii) **every later applicable step's call was made**, recorded by a
call recorder; (iv) `lifecycle_failure_steps` equals
`compute_lifecycle_closure_v2` of the observations and names the owning step;
(v) no hostile marker string appears anywhere in the outcome (G-X-1).

**G-L21 — runtime teardown**
1. `shutdown()` raises. (min. case 1)
2. `shutdown()` returns `None`. (2)
3. `shutdown()` returns a `list`, a `str`, a foreign object, a dict subclass,
   and an exact dict whose `exit_status_observed` is `True`, `"0"`, `0.0`, a
   foreign int-like, or missing. (3) — `runtime_exit_observed is False` in
   every case; an exact `int` (including `0` and a negative) is `True`.
4. Returned object whose `.get`/`__getitem__`/`__getattr__` raises. (4)
5. `stdout_state()` raises; malformed (non-dict, `eof` missing, `eof = 1`,
   `eof = "true"`). (5, 6)
6. `stderr_snapshot()` raises; malformed. (7, 8) — and stderr is **read even
   when stdout is not at EOF**.
7. D-3 / launch-attempt provenance (replaces the earlier single case):
   - **7A.** Supervisor built, `launch()` **never attempted** (L14 refused
     earlier), `process` accessor returns an object -> **no** shutdown call,
     `runtime_created` stays `False`.
   - **7B.** Supervisor built, `launch()` never attempted, `process` accessor
     would raise -> no shutdown call, `runtime_created` stays `False`, and
     preferably the accessor is **not consulted at all** (assert via an access
     counter on the double).
   - **7C.** Launch-attempt fact set `true` before `launch()`, `launch()`
     raises, later `process` is `PRESENT` -> `runtime_created` `False -> True`,
     L21 shutdown attempted, v2 validator accepts the record.
   - **7D.** Launch-attempt fact `true`, `launch()` raises, `process` accessor
     **raises** -> `runtime_created` `False -> True`, L21 shutdown attempted,
     later closure steps still proceed, v2 validator accepts the record.
   - **7E.** Launch-attempt fact `true`, `process` exactly `None` ->
     `runtime_created` stays `False`, no shutdown.
   - **7F (adversarial).** No supported injected **pre-launch** process claim
     (a port that builds a supervisor whose `process` is pre-populated, whose
     accessor raises, or whose `shutdown` records calls) can cause a shutdown of
     a resource AIDO never attempted to launch: across every refusal point
     before L14's `launch()` call, the double's `shutdown` call count is `0`.
   - **7G.** The launch-attempt fact is not in `outcome.observations`, not in
     the emitted run/refusal record bytes, and cannot be supplied through any
     port, argument or config (source audit: the only assignment is the single
     executor line immediately preceding `launch()`).
8. All three L21 sub-operations fail in one run. (9)

**G-L22 — broker diagnostics**
1. `diagnostics_counts()` raises. (10)
2. Returns `list`, `None`, dict subclass, foreign mapping. (11)
3. One member `bool`, negative, float, numeric string, int-like, missing —
   **with non-zero exact siblings** — → `available is False` and **all four
   counts are `0`**, and the run record validates. (12)
4. L23 is still called after each.

**G-L23 — broker shutdown**
1. `shutdown_for_cfg1()` raises. (13)
2. Returns non-dict (`None`, `"CLOSED"`, list, foreign mapping). (14)
3. Each member malformed independently while the other two are well formed —
   only the malformed member's fact is `False`; missing
   `worker_termination_observed` → `False`; `state_reached` object with a
   raising or non-bool-returning `__eq__` → `False` and no foreign object in
   observations. (15)
4. L24–L27 still run after each.

**G-L24 — scrub independence (AMEND2)**
1. Config scrub raises / returns `False` / token accessor raises → extension
   scrub still attempted. (16)
2. Extension scrub raises / returns `False` / token accessor raises → L25 and
   L27 still executed. (17)
3. The existing AMEND2 suite passes unchanged.

**G-L25 — Git observation #1**
1. Workspace authority verification fails. (18)
2. `observe_repository` raises. (19)
3. Malformed snapshot (existing Sec. 37.4.1 cases). (20)
4. L26 eligibility / L27 still proceed.

**G-L26 — verification**
1. `run_verification` raises. (21)
2. Outcome accessor raises (property, `__getattr__`); `counts` is a `list`,
   `None`, a `str`, a dict subclass, an object with raising `__bool__`;
   `return_code` is `"0"`, `True`, `1.0`. (22) — reaped `False` for
   accessor-raise and non-int return code; sentinel for malformed counts.
3. Git observation #2 raises / malformed — and it **is** attempted after 1
   and 2. (23)
4. L27 runs after every G-L26 case.

**G-L27 — workspace closure**
1. Re-proof raises → no removal call, discard called. (24)
2. Remover raises → no discard, no retry, registry entry survives. (25)
3. Remover returns `None`, a list, a dict subclass, a dict with `removed`
   missing/`1`/`"true"` or residual `-1`/`True`/`"0"` →
   `workspace_removed_verified is False`. (26)
4. `discard_cfg1_run_workspace` raises (monkeypatched) → contained, no fact
   changes, registry entry survives. (27)

**G-MULTI — combined and ordering**
1. Two or more steps fail in one run (at least: L21 + L23 + L24 + L27; and
   L22 + L25 + L26-Git#2). (28)
2. Earliest step (L21) fails and the recorded call sequence is exactly
   `shutdown, stdout_state, stderr_snapshot, diagnostics_counts,
   shutdown_for_cfg1, scrub_config, scrub_extension, observe_repository,
   remove` (with L26 absent for `LIFECYCLE_UNPROVEN`). (29)
3. L24 failure → `verification_skip_reason == "LIFECYCLE_UNPROVEN"` **and**
   the workspace is removed / `remove_cfg1_run_workspace` was called. (30)

**G-X — containment and plain-outcome**
1. Hostile marker strings placed in every raised exception message, in
   `text_tail`, `stdin_close_error`, `worker_error`, and in the `__repr__`/
   `__str__` of every malformed object: absent from `outcome.observations`
   (serialized), `outcome.console_codes`, the emitted run/refusal record bytes,
   and `capsys` stdout/stderr. (31)
2. Every value in `outcome.observations` after every G-L* case has an exact
   type from the field's existing domain (I-9); no foreign object.
3. Source audits: closure handlers bind no exception name; no closure
   consumption path contains `.get(…, True)`, `getattr(…, …, True)`, or
   `or {}`; the call that enters the closure phase in `execute_cfg1_run` is not
   lexically inside a `try` whose handler constructs or returns a
   `Cfg1RunOutcome` (I-8).
4. The pre-existing audits that name `_closure_phase`
   (`test_cfg1_l16_fu2.py` `process`-read census; `test_cfg1_fu15_evidence.py`
   T-156 laundering guard) are retargeted to whatever function(s) now contain
   those sites, so they keep auditing the same code — never deleted, never
   left pointing at a function that no longer contains the site (which would
   pass vacuously).

**G-STAGE — stage-level integration**
1. Closure fault (L21 `shutdown()` → `None`) → executor returns an outcome →
   L29 attempted and the run record is `EMITTED` with
   `lifecycle_all_closed is False` and `"L21" in lifecycle_failure_steps` →
   L30 halts with `LIFECYCLE_CLOSURE_UNPROVEN` → a stage-closure record exists
   → **no** `Cfg1StageRunnerError("RUN_EXECUTOR_RAISED")`. (32)
2. Registry-survival variant: remover raises → `_run_scoped_registries_empty`
   returns `False` (asserted directly) → the stage is **not** admitted to the
   next ordinal and halts under the frozen precedence. (33)
3. Out-of-domain control: a `BaseException` (e.g. `KeyboardInterrupt`) raised
   from a closure port propagates unchanged (not converted into an outcome).

**G-REGRESS** — the full existing offline CFG1 suite passes, with only the
retargeting of G-X-4 and any test whose assertion encoded an escape or a
manufactured value that this design removes (none were found at `2e8e6a9`:
no test asserts `RUN_EXECUTOR_RAISED`, and every double already returns exact
dicts with exact members).

---

## 14. Pre-implementation adversarial review

| # | Challenge | Answer |
|---|---|---|
| A-1 | "Wrap `_closure_phase` in one `try` and return a fail-closed outcome." | Forbidden (I-8). It skips every step after the fault, which is the defect. G-MULTI-2/3 fail against it. |
| A-2 | `isinstance(x, dict)` instead of `type(x) is dict`? | No. A dict subclass can override `get`/`__getitem__`/`__contains__`; exact type guarantees the member read runs CPython's own `dict` code. |
| A-3 | `bool` is an `int`. | Every count/return-code check is `type(v) is int`; every bool proof is `v is True`. `True` never passes as a count or exit status. |
| A-4 | Hostile `__eq__` on `state_reached`. | Exact-`str` check first; the comparison then runs `str.__eq__` only. Fixes E-6/M-3/E-7. |
| A-5 | Hostile `__bool__`. | No truthiness on any foreign value (R-PLAIN): `or {}` removed; `_exact_bool`-style `is True` only; the L26 conjunction sees exact bools. |
| A-6 | Custom `__iter__`/`__getitem__`/`.get`. | Containers are validated exact before access; iteration only over exact `list`/`tuple` (the existing 37.4.1 predicate). |
| A-7 | Post-validation mutation (the port keeps a reference and mutates the dict). | Each member is read once into a local; the local — an immutable scalar — is what is validated and committed. |
| A-8 | Numeric conversion (`__int__`, `__index__`). | Never performed; `type(v) is int` rejects int-likes. |
| A-9 | `.get(k, True)` / `getattr(o, k, True)` defaults. | Forbidden (R-NOAUTHORITY-FROM-DEFAULT); M-4 removed; audited (G-X-3). |
| A-10 | Could containment hide a *real* positive (e.g. exit observed but EOF read raised)? | Sub-obligations are independent: the exit fact is still committed from its own region. Only the fact whose input failed is unproven. |
| A-11 | Could a contained fault be retried to "fix" it? | No (I-6). One opportunity per obligation. |
| A-12 | Does D-3 rewrite history, or let a port grant cleanup authority? | It moves one "may exist" flag in the fail-closed direction only, never back, and **only** when AIDO's own executor-owned `runtime_launch_attempted` fact proves AIDO called `launch()` (Category B). A merely built supervisor's `process` — present, absent or raising — is never consulted and never grants authority (G-L21-7A/7B/7F). Flagged for explicit reviewer acceptance. |
| A-13 | A malformed L22 count laundered to `0`? | Only under `available = false`, which the frozen validator and classifier treat as "no evidence"; with the fix, zeros never coexist with partial real counts. |
| A-14 | Does the L26 port-raise path invent verification facts when the outcome object was malformed? | It commits nothing from the malformed object; the remaining fields are the frozen initial values, i.e. the state already emitted when the port raises. |
| A-15 | Can a registry survival be masked? | No bool is consulted for it; L30 reads the four counts. `live_references_released` stays a constant truthful only under I-9 (§9). |
| A-16 | Could exception chaining leak text? | Handlers bind nothing and raise nothing (R-HANDLER); the stage runner already raises `from None`. |
| A-17 | Could L27 run before L24 scrubbed, deleting the object before its content was scrubbed? | No — order is frozen (I-1) and L27 runs after L24 regardless of L24's result; AMEND2's L24/L27 separation unchanged. |
| A-18 | Could the verification child (repository-controlled code) run on an unproven closure because of containment? | No. The eligibility conjunction now reads exact bools only; a foreign truthy object can no longer satisfy it (E-7 closed). |
| A-19 | Does totality mask an executor bug? | No — I-8 leaves out-of-domain raises as `RUN_EXECUTOR_RAISED`. |
| A-20 | Source audits pinned to `_closure_phase` pass vacuously after refactor. | G-X-4 requires retargeting. |
| A-21 | `MemoryError` / `RecursionError` inside a region. | If delivered as an ordinary `Exception` to the step-local handler and Python keeps executing, it is contained like any other `Exception` and the facts it leaves are unproven; production code does not special-case the type. *Persistent* memory/stack exhaustion that prevents the handler, later steps, outcome construction or L29/L30 from completing is **out of domain** (§4.3): no recovery and no successful-completion claim is made for it. |
| A-22 | Is `discard` raising even reachable? | Not with genuine code; required anyway because the domain includes supported-call-site raises and it is the last unguarded statement. Cost: one guard. |

**Blocking findings:** none that stop this design. E-1 … E-13 and M-1 … M-5 are
the OC-4 correction itself. D-3 is a new, narrowly scoped decision requiring
explicit reviewer acceptance; it is bound to AIDO's own recorded launch attempt
(§6.1). If rejected, the alternative is to STOP and report — leaving
`runtime_created = false` after AIDO's own failed `launch()` while L21 cannot
exclude a process would make OC-4's own evidence false.

---

## 15. Residuals and non-goals

**Residuals (documented, not fixed here):**

- R-1 Out-of-domain events of §4.3 (process/interpreter/OS loss, non-`Exception`
  `BaseException`, hangs, same-process tampering).
- R-2 Descendant processes, abandoned reader/worker threads, backend inference
  and GPU lifetime — unchanged frozen claim scope; L21 proves only the direct
  child's exit and both reader EOFs.
- R-3 A foreign object's finalizer output via CPython's unraisable hook
  (test-double-only).
- R-4 A step that fails leaves its resource in whatever state the failure left
  it (live process, broker thread, orphan tree, unscrubbed file); OC-4 makes
  that **truthfully recorded and halting**, not cleaned.

**Deferred, non-blocking backlog (found during inspection; out of OC-4 scope):**

- B-1 L14's `except` branch reads `getattr(state.supervisor, "process", None)`
  unguarded; a raise there reaches the dispatch catch-all with
  `runtime_created = false`. Dispatch-phase and not fixed here. Its closure
  consequence is **not** neutralized by any pre-launch claim: because that read
  sits after AIDO's own `launch()` call, the executor-owned
  `runtime_launch_attempted` fact is already `true` at that point, so closure's
  contained probe (§6.1) is evaluated and a `PRESENT`/`RAISED` outcome moves
  `runtime_created` `false -> true` under AIDO's own launch-attempt provenance.
- B-2 L3 `getattr(baseline_verification, "passed", True)` truthiness and
  default — **OC-5** (explicitly not touched).
- B-3 L20 `len(getattr(activity, "extension_errors", ()) or ())` truthiness on
  a foreign value — dispatch-phase; contained by the POST_DISPATCH_UNEXPECTED
  catch-all today.
- B-4 `broker_git_cross_check_agrees` initial `true` when observation #1 is not
  performed — frozen D-4 gating on `git_observation_1_performed`; not reopened.
- B-5 After a verification port raise, `verification_counts` stays at the
  initial zeros with `verification_attempted = true` — frozen port-raise shape;
  not reopened.
- B-6 L10's safety-context `getattr(state.broker, …)` on a port object —
  dispatch-phase; contained by the REFUSAL catch-all.

**Non-goals (not added, not touched):** OC-5; Pi identity; package or Node
pinning; OC-6; Git resolution OC-7; qualification policy; Candidate C/D;
reviewer qualification; M5A; crash recovery; journaling; rollback; process
supervision redesign; job objects / process trees; forensic secure erase;
same-process tampering defences; new durable fields, record kinds, lifecycle
steps, halt reasons or console codes; any change to L29, L30, the validator,
the classifier, the halt precedence, the writers, AMEND2's scrub machinery, or
the genuine port adapters.

---

## 16. Acceptance criteria (for the future implementation phase)

The implementation is acceptable only if **all** hold:

1. Every escape point E-1 … E-13 and every manufactured commit M-1 … M-5 of §3
   is closed as §6 specifies; a fresh adversarial inventory of the
   implemented ladder finds no operation touching a foreign value outside a
   step-local region.
2. I-1 … I-10 hold, with I-8 proven by the G-X-3 audit and by G-MULTI.
3. D-3 is implemented exactly as §6.1 (monotone, `false → true` only, only on
   `RAISED`/`PRESENT` with `runtime_created = false` **and** the executor-owned,
   in-memory, non-durable, never-reset, caller-unsettable launch-attempt fact
   `true`; the `process` accessor is never consulted, and L21 never called, for
   a supervisor AIDO never attempted to launch) — or, if the reviewer
   rejected D-3, the phase stopped and reported instead of shipping without it.
4. No durable field, record kind, record version, lifecycle step, halt reason,
   console code, CLI surface, or port field is added or changed; the v2
   validator, classifier, `compute_lifecycle_closure_v2`, halt precedence,
   writers, stage runner, and genuine port adapters are byte-unchanged.
5. AMEND2 L24 semantics are unchanged except that the token read moved inside
   containment; the AMEND2 test suite passes unchanged.
6. The §13 regression matrix exists and passes (every numbered minimum case
   1–33 mapped, with G-L21-7A–7G distinct), and the full offline CFG1 suite passes with Node/Pi-executing
   tests deselected, with only the G-X-4 audit retargeting as an intended
   test edit to pre-existing tests.
7. G-STAGE-1 demonstrates an in-domain closure fault ending in an emitted run
   record and a `LIFECYCLE_CLOSURE_UNPROVEN` halt, never `RUN_EXECUTOR_RAISED`.
8. G-X-1 demonstrates no hostile marker text in any sink.
9. No Node, Pi, model, network, or credential was used; no frozen design file,
   governance document, authorization document, or `CLAUDE.md` was edited.

---

## 17. Can OC-4 be recorded CLOSED?

**Yes — once, and only once,** a separately authorized implementation phase
satisfies every criterion of §16 and is reviewed and accepted. At that point
the OC-4 finding ("`_closure_phase` is not total … producing no record") is
mechanically false over the §4.2 domain: every run that reaches closure gives
every applicable obligation its one opportunity in order, records each failure
as an existing fail-closed fact, and returns a bounded `Cfg1RunOutcome` that
the frozen L29/L30 path turns into evidence and a halt.

Closing OC-4 does **not** move A4, Stage 2, or AR2 live off NO-GO. The pre-A4
barrier sequence continues with OC-5, the operator restore of approved Pi
0.85.1, the read-only pre-A4 identity/seam verification, and a separately
reviewed A4 authorization. The residuals of §15 remain residuals and are not
claimed closed by OC-4.
