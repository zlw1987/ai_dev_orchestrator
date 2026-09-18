# Phase 5F3B-HARNESS-CFG1-LIVE-S1-AUTH — Stage-1 Execution Authorization

```text
5F3B-HARNESS-CFG1-LIVE-S1-AUTH CANDIDATE — PENDING INDEPENDENT REVIEW
```

> **THIS DOCUMENT IS A CANDIDATE. IT IS NOT YET AN AUTHORIZATION.**
>
> It carries no execution authority of any kind until an independent human
> reviewer has inspected the committed form of this file and accepted it. Until
> that acceptance is recorded, `CFG1-LIVE-S1` remains **NOT AUTHORIZED**,
> exactly as the frozen design's own final outcome block states.
>
> **Authoring this file is not, and never becomes, permission to run Stage 1 in
> the same turn, session, or agent invocation that produced it.** The turn that
> wrote this file launched no Pi process, contacted no B300 endpoint, opened no
> socket, made no model call, read no credential or endpoint value, created no
> directory under the CFG1 results root, and produced no run artifact.

---

## 0. Document semantics, and what state this leaves the project in

### 0.1 Status

| Item | Status after this document is written | Status after independent acceptance |
|---|---|---|
| `CFG1-LIVE-S1` | **NOT AUTHORIZED** (candidate only) | authorized for **exactly one** Stage-1 execution, under §2's single identifier |
| `CFG1-LIVE-S2` | **NO-GO** / separate conditional authorization | **NO-GO** / unchanged |
| `DX1` | **NO-GO** | **NO-GO** / unchanged |
| `M4` | **HOLD / NO-GO** | **HOLD / NO-GO** / unchanged |
| Qualification (Q1/Q2/Q3) verdicts, rankings, lineage, OBS1 companions | frozen, untouched | frozen, untouched |
| `docs/PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md` | frozen, unmodified | frozen, unmodified |

Acceptance is recorded **outside** this file, by the reviewer, in the review
record for this phase. This document contains no self-acceptance mechanism, no
conditional activation clause, and no "valid unless objected to" wording.

### 0.2 Authority relationship to the frozen design

This document is **subordinate** to
[`PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md)
(hereafter "the frozen design"). It does not amend it, reinterpret it, extend
it, or resolve anything left open in it. Where this document and the frozen
design could be read as disagreeing, **the frozen design governs and this
document is wrong**.

It is also subordinate to the shipped implementation at the accepted
implementation HEAD `3e51e3c47d90a261895e58f54ab4f3024847f6a1`. Where this
document and the shipped code could be read as disagreeing, **the code's
fail-closed refusal governs**. Nothing here instructs the implementation to
accept an input it would otherwise refuse, or to skip a proof it would
otherwise perform.

This document discharges frozen design **§14.1 item 2** — and only that item.
It does not discharge §14.1 item 3 (`LIVE-S2`) or item 4 (resumption).

### 0.3 Offline green tests are not live authorization

The CFG1 offline regression suite passing, the implementation having passed
independent source review, and `CFG1-IMPL-FU4 (+FU4-FU1 + FU4-FU2)` being
accepted are **preconditions that were required before this document could be
written honestly**. They are not themselves authorization, they are not
evidence that any live behavior works, and they establish nothing about B300,
the proxy route, the model, or the network. A green offline suite proves what
AIDO does with synthetic inputs under `tmp_path`; it proves nothing about a
live run.

---

## 1. The one fact this document grants

Everything the Stage-1 experiment needs is already fixed, in the frozen design
or in the shipped implementation, with exactly one exception: there is no
`stage_execution_id`, so `establish_stage_output_authority(...)` cannot be
called and no output namespace can exist.

**That is the entire delta.** Upon independent acceptance, this document
grants:

> one concrete `stage_execution_id` literal, and, jointly with it, permission
> for **one** Stage-1 execution of the already-frozen, already-implemented CFG1
> harness to proceed against the live `b300_pi_qualification` route.

It grants nothing else. It supplies no schedule, no arm, no ordinal, no model
choice, no route choice, no endpoint, no credential, no output path, no
timeout, no retry budget, no prompt, no task, and no Pi version. Those are
frozen design-time facts (§4) or runtime-proven facts (§5), and **making any of
them caller-selectable would itself be a redesign of CFG1, which this document
is not permitted to perform.**

---

## 2. Authorization-supplied fact: the `stage_execution_id`

### 2.1 The literal

```text
CFG1-S1-A1
```

This is the **only** authorization-supplied value in this entire document.

### 2.2 Grammar conformance

The frozen design §16.3.1 and the shipped
`experiments/pi_harness_cfg1/stage_output.py::_require_valid_stage_execution_id`
require, in order:

1. `type(value) is str` — exactly `str`, not `isinstance`. A `pathlib.Path`,
   any `__fspath__` provider, a `str` subclass, an `int`, a `bool`, `None`, and
   any wrapper object are each refused before any filesystem access.
2. `re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value)` is not `None`.

`CFG1-S1-A1` is a plain ASCII `str` of length 10, drawn entirely from
`[A-Za-z0-9_-]`. It therefore contains:

- no `/` and no `\` — so it cannot name a subdirectory or escape one;
- no `.` at all — so `.` and `..` traversal are excluded mechanically, not by a
  separate traversal check;
- no `:` — so no drive-qualified or alternate-data-stream form;
- no NUL and no other control character;
- no whitespace, leading, trailing, or internal;
- nothing outside ASCII, so no confusable or normalization-sensitive character.

**Because the positive alphabet excludes every path-significant character, the
identifier cannot widen filesystem authority.** It is joined as exactly one
already-separator-free component, and containment is then proven
*structurally* (`resolved_exec.parent == resolved_root`, plus a
`resolved_root in resolved_exec.parents` check and a self-equality refusal),
never by lexical string concatenation.

### 2.3 No normalization, ever

The literal above is transmitted to the runtime **verbatim**. It must not be
stripped, trimmed, case-folded, upper-cased, lower-cased, truncated,
percent-decoded, Unicode-normalized, sanitized, slugified, suffixed, prefixed,
or "repaired" by any layer. The shipped validator performs none of these, and
no operator or tooling layer may perform them either. A value that would need
repair is a refusal, not an input.

### 2.4 Not a timestamp, not derived, not reused

`CFG1-S1-A1` is a fixed, human-chosen literal. It encodes no clock value, no
date, no counter read from disk, no hostname, and no process id. It is not
derived from anything at runtime, so there is no derivation to diverge and no
second run that could compute the same value "naturally".

### 2.5 Evidence that the literal is unused (established in this turn, offline)

Checks performed against this checkout at implementation HEAD
`3e51e3c47d90a261895e58f54ab4f3024847f6a1`, working tree clean:

| Check | Method | Result |
|---|---|---|
| present in any tracked file's content | `git grep -n "CFG1-S1-A1" -- .` | no match |
| present anywhere in the working tree, tracked or not | recursive content grep excluding `.git/` | no match |
| present in any commit reachable from any ref | `git log --all -S "CFG1-S1-A1"` | no commit |
| present as a file or directory **name** anywhere | recursive name search excluding `.git/` | no match |
| an execution directory of this name exists under the CFG1 results root | see next row | impossible — the root itself does not exist |
| the CFG1 results root exists at all | `experiments/pi_harness_cfg1/results`, the package-derived `RESULTS_ROOT` | **absent** |
| any CFG1 results artifact ever added in history | `git log --all --diff-filter=A --name-only`, filtered to `pi_harness_cfg1/results` | none |

The CFG1 results root **has never existed in this checkout**, so no CFG1
execution directory of any name has ever been created here, and `CFG1-S1-A1` in
particular is unused. The preferred literal from the phase request was
therefore available and was taken; no substitute was needed.

**No directory was created by these checks.** The results root was tested for
existence and left absent. Nothing under any results namespace — CFG1's or any
other experiment's — was created, read for authority, modified, renamed, or
deleted.

### 2.6 Scope of that evidence, stated honestly

The checks above cover **this checkout and its git history**. They do not, and
cannot, prove that no other machine, clone, or operator has ever used the
string `CFG1-S1-A1`. That residual is closed at runtime, not here: the
execution directory is created under an exclusive-create discipline, and an
already-existing directory refuses the **entire stage** before any run, at
`EXECUTION_DIRECTORY_EXISTS`, without reading, merging, appending to, renaming
around, or deleting its content (frozen design §16.3.6). Reuse is therefore
refused mechanically, not prevented by this document's diligence.

---

## 3. What this authorization covers — the exhaustive bound

Upon acceptance, and only then, exactly one Stage-1 execution may proceed,
bounded as follows. Every row is a **reference to a frozen fact**, not a new
selection made here.

### 3.1 Model and route

| Bound | Value | Source of authority |
|---|---|---|
| model | exactly `qwen3-coder-next` | `identity.CFG1_MODEL_ID`; frozen design §9, §8.3 |
| provider id | exactly `b300_pi_qualification` | `identity.PROVIDER_ID`; §8.3 |
| backend gateway class | exactly `b300_litellm_proxy` | `identity.BACKEND_GATEWAY_CLASS`; §8.3 |

Not authorized, in any circumstance, for any reason, at any point in the stage:
a fallback model; a replacement candidate; an automatic substitution after a
failure; a second model of any kind; Nemotron; MiniMax; GPT-OSS; any Qwen
variant other than the pinned id; any other model whatsoever; any other
provider id; any other gateway class; any direct-to-backend path that bypasses
the proxy; any alternate route, region, or endpoint.

A model-identity or route mismatch observed at runtime (`H2`, L16) is a
pre-dispatch refusal, never a substitution and never a retry.

### 3.2 Pi provenance

| Bound | Value | Source of authority |
|---|---|---|
| Pi version | exactly `0.85.1` | `identity.PINNED_PI_VERSION`; frozen design §1.2, §14.2 |
| seam digests | the shipped `preflight.PINNED_PI_SEAM_DIGESTS` | frozen design §14.2 plus its own mandated implementation-time extension |

All §14.2 pinned seam digests must agree before any live, model-influenced
execution. A mismatch is a **refusal**, at L1, strictly **before any credential
is read**. It is never an auto-update, never a compatibility guess, never a
warning to proceed past, and never evidence that Pi is incompatible — it means
this design's source derivations must be re-reviewed.

**This document recomputes no digest and replaces no expected digest.** Two
facts are recorded for the reviewer, both established by reading text only:

- the frozen design §14.2 pins **18** entries; the shipped
  `PINNED_PI_SEAM_DIGESTS` declares **20**. The two additional entries are
  `dist/modes/rpc/jsonl.js` and
  `node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js` — exactly the
  two §14.2 itself required the implementation phase to add at its own review.
  This is the design's own instruction being carried out, not drift;
- comparing §14.2's 18 literals against the shipped dictionary's corresponding
  entries found **zero** differences.

That comparison was **document-text against source-text**. It hashed nothing,
opened no installed Pi file, and is **not** evidence that the installed Pi tree
matches. Agreement with the installed tree is a runtime fact AIDO must prove
itself at L1 (§5).

### 3.3 Credentials and endpoint

Within that one accepted execution, exactly two live environment inputs may be
read, and only through the frozen credential-boundary ordering:

- `AIDO_LITELLM_BASE_URL` (`identity.BASE_URL_ENV_VAR_NAME`)
- `PI_QUALIFICATION_B300_ROUTE_KEY` (`identity.CREDENTIAL_ENV_VAR_NAME`)

Read at **L4** only, **once per admitted run**, after every non-secret gate of
L1–L3 has already passed — including the offline preflight, the workspace mint,
and the baseline verification, so repository-controlled fixture code runs
before any credential is in process memory. Their only permitted consumers are
the frozen ones: the L7 route check, the L12 `$ENV` carrier name into the Pi
child environment, and the L29 scrub needles.

**No value of either name was read while authoring this document, and no value
of either appears anywhere in it.** This document contains no endpoint, host,
port, scheme, path, URL, IP address, API key, bearer token, header, cookie,
session id, nor any hash, digest, fingerprint, prefix, suffix, length, or
partial rendering of a secret or endpoint. Recording a hash of a secret would
be recording the secret's derivative, and is prohibited here exactly as the
value itself is.

Not authorized: reading any other environment variable as a live input;
forwarding a credential or endpoint to a Git, fixture, or verification child;
writing either value to disk, to a record, to a console line, or to a log;
adding a `.env` file, a config-file fallback, a CLI flag, or an interactive
prompt for either value.

**Redaction and scrubbing remain a backstop.** Nothing in this document claims
any retained artifact is provably secret-free.

### 3.4 Connectivity checks

Within that one accepted execution: **at most one** authenticated, non-inference `GET /models` check
per admitted Stage-1 run, therefore **at most 9 in total** across the stage —
the frozen `observe_b300_route_serves_model` call at L7, once, with no retry,
no fallback endpoint, no fallback model, and no second request of any kind.

`9` here is a **ceiling implied by "one per admitted run" and "at most 9
admitted runs"**. It is not a budget, not a quota, not a pool that may be
redistributed, and not authority to issue a check outside an admitted run's own
L7. If the stage halts after ordinal 3, then at most 3 checks were authorized
and the remaining 6 are not available for any purpose.

Not authorized: arbitrary health checks; readiness probes; exploratory
requests; a `GET /models` outside L7; a second `GET /models` in the same run; a
warm-up request; a connectivity test performed before or after the stage;
pinging, tracerouting, or resolving the endpoint for diagnostic purposes.

### 3.5 Stage-1 schedule — referenced, never supplied

The Stage-1 schedule is a **frozen design-time fact** (frozen design §7.3),
implemented once in `schedule.py` as `_S1_SCHEDULE` / `_schedule_arm_for` and
consumed by identity of that one callable:

```text
block 1:  run 1 Q   run 2 R   run 3 E
block 2:  run 4 R   run 5 E   run 6 Q
block 3:  run 7 E   run 8 Q   run 9 R
```

**This authorization does not supply, select, confirm, or override any of it.**
It supplies no run count, no ordinal, no arm, no block, no position, no
ordering, and no per-run parameter of any kind. The count `9` is derived by the
implementation as `LAST_ORDINAL("S1") = max(SCHEDULE["S1"])`, from that same
table; the block above is reproduced only so a reviewer can see what is being
pointed at, and if this document's rendering ever disagreed with `schedule.py`,
then `schedule.py` is correct and this document is wrong.

Bounds that follow, all frozen:

- **9 runs maximum**, strictly sequential, each gated by the §19 admission rule;
- **at most one prompt write per run**, therefore at most 9 in the stage;
- **no retry** of a run, of a prompt, or of a request — of any kind, at any
  layer, semantic or transport;
- **no reorder**, **no replacement**, **no replay**, **no repeat**;
- **no extra control run**, no pilot run, no warm-up run, no discard-and-redo;
- **no automatic Stage-2 transition** on any outcome.

"9 runs maximum" is a ceiling, not a target. A stage that halts at ordinal 4 has
consumed its authorization; the unexecuted ordinals are `NOT_EXECUTED`, their
arms are indeterminate, and this document does not authorize anyone to go get
them.

### 3.6 Prompt, task, and fixture

| Bound | Value |
|---|---|
| task | `CFG1-T1`, the frozen synthetic fixture in `fixture.py` |
| named implementation file | `greeting/banner.py` |
| prompt | `fixture.CFG1_T1_PROMPT`, byte-identical, transmitted verbatim |
| manifest in prompt | `False` — bare transmission, nothing prepended or appended |
| fixture revision | `fixture.PINNED_CFG1_T1_REVISION` |
| tool allowlist | exactly `("aido_read", "aido_edit")` |
| workspace | a fresh disposable Git repository per run, removed at L27 |

Not authorized: an alternate prompt; a reworded prompt; a system-prompt
addition; a corrective prompt; a follow-up prompt; a clarifying prompt; a
second turn; a semantic retry; a reviewer-generated prompt; a manifest; a tool
hint; a file list; a different task; a real project file; a real workspace; any
task from the qualification corpus.

### 3.7 Lifecycle, admission, and halt

This authorization **explicitly inherits, unchanged**, the frozen design's §16
per-run lifecycle state machine (L0–L30), §17 closure predicates, §18
partial-failure semantics, and §19 admission and halt rules, including §19.4's
`HALT_REASON_CODES` vocabulary, §19.5's single shared precedence resolver, and
§19.6's three-way terminal transition. Nothing here relaxes, reorders,
shortcuts, or adds an exception to any of them.

**A halt terminates this authorization.** On any halt:

- there is **no resume** within `CFG1-S1-A1`, at any later time, by any
  operator, for any reason;
- the failed or missing ordinal is **not** replaced, re-run, or re-attempted;
- later ordinals are **not** continued, started, or back-filled;
- the stage-output authority is retired, and a retired authority is
  deliberately indistinguishable from an unknown one (`UNKNOWN_MINT_NONCE`), so
  a retained authority object cannot be reused to write anything further;
- no cleanup, repair, `git restore`, artifact rewrite, or partial-state
  reconciliation is authorized.

Any resumption, continuation, or repetition requires a **new, separately
reviewed authorization document** naming a **new, never-used**
`stage_execution_id`, and that document must state explicitly whether any
earlier completed run participates in any contrast — the frozen default being
**no** (frozen design §14.1 item 4). `CFG1-S1-A1` is spent by its one use,
whatever the outcome.

The frozen design's three narrow no-stage-closure-record exceptions (§16.3.7
stage-output authority failure, §16.3.10 L0 output-namespace preoccupation,
§16.3.8.3 terminal-decision mint failure) apply as frozen, with console-only
reporting. None of them is a licence to retry.

### 3.8 Filesystem authority

Durable output authority is limited to exactly:

```text
RESULTS_ROOT/CFG1-S1-A1/
```

where `RESULTS_ROOT` is the CFG1 package-owned root derived by the
implementation from its own captured package directory
(`stage_output._CAPTURED_PACKAGE_DIR` joined with `RESULTS_ROOT_NAME`), proven
at two levels before use.

Not authorized: a caller-selected output directory; an alternate root; an
environment variable, CLI flag, config key, or parameter that selects or
replaces the root; a path override; a fallback location; a temp-directory
mirror; a second copy anywhere; a nested subdirectory beyond what the frozen
writers create; writing outside the execution directory; touching another
experiment's results namespace.

**This document does not create that directory**, and nothing in this phase
created it. It is created exactly once, by
`establish_stage_output_authority`, at the start of the one authorized
execution, after the identifier and both root-provenance levels are proven, and
its prior existence refuses the whole stage.

Per-run disposable workspaces remain under the frozen disposable-root authority
and are removed at L27 with removal verified; they are not part of this
document's output authority.

### 3.9 Qualification isolation

The authorized execution must not, and the shipped implementation does not:

- re-run, re-score, reinterpret, or backfill Q1, Q2, or Q3;
- modify, rewrite, reissue, rename, or delete any qualification artifact,
  verdict, ranking, lineage record, hard-bar input, or OBS1 companion artifact;
- **use** any prior qualification artifact, verdict, ranking, lineage, or OBS1
  companion as **runtime authority** for anything in this stage;
- emit an `.activity.v1` companion, or write into the qualification results
  namespace at all;
- treat a previous `NOT_QUALIFIED` result as evidence of a model editing defect.

**CFG1 carries no qualification credit of any kind.** Its records are diagnostic
lineage only, exactly as `__init__.CLAIM_SCOPE` states, and a Stage-1 outcome —
in either direction — changes no verdict, no ranking, no hard-bar input, and no
candidate's status.

The historical attribution is unchanged and is restated here only so this
document cannot be read as revising it: the Qwen/MiniMax `PREMATURE_SETTLE`
outcomes **did not prove a model editing defect**, and `5F3B-HARNESS-ATTR1`
attributed the relevant problem to observability/harness behavior. CFG1 exists
to isolate a launch-configuration hypothesis about the harness; it is not a
retrial of any candidate.

---

## 4. Frozen design-time facts — NOT caller-selectable, not supplied here

Every item below is fixed by the frozen design and derived by the
implementation. **None of them may be turned into an authorization parameter, a
CLI flag, an environment variable, a config key, or a function argument** —
here, or in any operator tooling built around this authorization. Listing them
is the point: an authorization that could supply them would be a redesign.

1. the Stage-1 arm set `{Q, R, E}`, and that `H` never appears in Stage 1;
2. the run count (`9`), derived as `LAST_ORDINAL("S1")` from the schedule table
   itself, never a second pinned integer;
3. the per-ordinal arm assignment, block, and position — from the one shared
   `_schedule_arm_for` / `_schedule_block_position` derivation;
4. the ordering of blocks and of positions within them;
5. the per-arm `compat` subtree (`ARM_COMPAT`), the declared shape (`ARM_SHAPE`),
   and the derived effective values (`ARM_EFFECTIVE`);
6. the pinned per-arm redacted config digests and `PINNED_SETTINGS_SHA256`;
7. the task, prompt bytes, fixture file set, verification argv, witness paths,
   protected patterns, and `PINNED_CFG1_T1_REVISION`;
8. the model id, provider id, and backend gateway class;
9. the Pi version and the pinned seam digest set;
10. the tool allowlist;
11. the lifecycle step set L0–L30 and their ordering, preconditions, and closure
    transfers;
12. the §17 closure predicates and the `lifecycle_all_closed` conjunction;
13. the §19 admission conditions, halt semantics, `HALT_REASON_CODES`, the §19.5
    precedence, and the §19.6 three-way transition;
14. the output-root derivation, the execution-directory derivation, the one-shot
    creation rule, and the ACTIVE/RETIRED authority lifecycle;
15. the three record schemas, their versions, their closed field sets, their
    cross-field invariants, and the dispatched-validator rule;
16. the retry prohibition at every layer;
17. timeouts, deadlines, and bounds (`RunBounds()` defaults, broker deadlines,
    verification 300 s);
18. the token policy (no AIDO `maxTokens`);
19. the credential policy and the `$ENV` interpolation carrier;
20. the child-environment allowlist and forbidden-name fragments;
21. the artifact size bound `MAX_CFG1_ARTIFACT_BYTES`;
22. the §21 secret and diagnostic containment rules and scrub needles.

---

## 5. Runtime facts AIDO must independently re-prove

**A statement in this document is never a substitute for an observation.** The
implementation must prove each of the following for itself, at its frozen point
in the lifecycle, and must refuse or halt on failure — even where this document
asserts the same thing, and even where the assertion here is correct.

| Fact | Where it is proven | This document's status |
|---|---|---|
| `stage_execution_id` is exactly `str` and matches the §16.3.1 grammar | `_require_valid_stage_execution_id`, before any filesystem access | supplies the literal only; §2.2's argument is not the proof |
| `stage_id` is in the closed `{"S1","S2"}` domain | `_require_valid_stage_id` | asserts `S1`; the runtime proves it |
| the captured package directory is non-redirected and canonical (Level A) | `_reprove_trusted_package_directory`, before any write | not asserted here at all |
| `RESULTS_ROOT` is present, non-reparse, a directory, canonical (Level B) | `_prove_results_root`, unconditionally, every time | not asserted here at all |
| the execution directory is the root's immediate child, structurally | `_prove_execution_directory_containment` | §2.2's alphabet argument is necessary, not sufficient |
| the execution directory did not already exist | exclusive create plus immediate re-`lstat` | §2.5's evidence is this-checkout-only (§2.6) |
| the authority is genuine and still ACTIVE at every consumption boundary | `verify_stage_output_authority`, re-proven each time | not asserted here at all |
| Pi is installed, is `0.85.1`, and every pinned seam digest matches the installed tree | L1 offline preflight | §3.2's comparison was text-to-text, not against the installed tree |
| the base URL triggers no `detectCompat` substring | L6, in memory, URL never recorded | not asserted here at all |
| the credentials are available | L4, after every non-secret gate; availability observed **without exposing the value** | not asserted here; values were never read |
| the route is reachable and serves the pinned model | L7, one `GET /models`, correlated within that run | not asserted here at all |
| workspace root authority, tracked manifest, HEAD, clean status, witness digests | L2/L3, re-proven at L8, L24, L25, L27 | not asserted here at all |
| the baseline fails exactly as seeded | L3, one baseline verification | not asserted here at all |
| extension identity and RPC correlation (H1) | L15, by this run's own RPC id and supervisor | not asserted here at all |
| model/provider identity and the declared compat shape (H2, §8.2) | L16, from `get_state` | not asserted here at all |
| the actual ordinal→arm mapping used for this run | `_schedule_arm_for`, by callable identity | §3.5 reproduces the table for reading only |
| protocol activity, tool activity, and evidence counts | OBS1 projection at L20; broker counts at L22 | not asserted here at all |
| every §17 closure predicate, and `lifecycle_all_closed` | L21–L28 | not asserted here at all |
| cleanup state: scrubs verified, child reaped, workspace removed, zero residual | L24, L26, L27 | not asserted here at all |
| record validity, authority binding, and exact-byte emission | L29 writer sequence and its dispatched validator | not asserted here at all |

**Runtime and model claims are not authoritative.** Nothing reported *by* Pi,
*by* the model, or *by* the backend may substitute for an AIDO-observed
lifecycle, workspace, Git, protocol, or evidence fact. A model asserting it
edited a file is not an edit; a runtime asserting it settled is not settlement;
a backend asserting success is not an observation. The frozen `runtime_reported_*`
trust-namespace separation applies unchanged.

**Scope every negative claim.** Nothing in this document, and nothing in any
artifact produced under it, may claim that the Pi child was sandboxed, that its
descendants were tracked or stopped, that backend inference stopped, that GPU
work stopped, that no network access occurred, or that transmitted material is
provably secret-free.

---

## 6. What this document explicitly does NOT authorize

Stated as refusals, so no reader can find a gap to read permission into:

1. **Stage 2 / `CFG1-LIVE-S2`** — not authorized, not designed here, not made
   conditionally available, and not made eligible. Stage-2 eligibility cannot
   even be assessed before Stage-1 evidence exists, and if §13.2 row 4 were
   later to obtain, `LIVE-S2` still requires its own separately reviewed
   authorization with its own never-used `stage_execution_id`.
2. **Arm `H`** — `H` is a Stage-2 arm. No `H` run, no `H` config generation, no
   `H` digest use, no fourth arm in Stage 1.
3. **`DX1`** — NO-GO, unchanged.
4. **`M4`** — HOLD / NO-GO, unchanged.
5. **Retries** of any kind: no run retry, prompt retry, semantic retry,
   transport retry, request retry, connectivity retry, verification retry, or
   emission retry.
6. **Reorder, replacement, replay, or repetition** of any ordinal, block, or
   arm.
7. **Fallback models, secondary models, model failover, or substitution** — and
   no second model call of any kind anywhere in the stage.
8. **Qualification reruns**, or any write, amendment, or authority-use of
   qualification, lineage, or OBS1 artifacts.
9. **Resumption after a halt**, under this or any existing identifier.
10. **A second execution** under `CFG1-S1-A1`, in this repository or any other.
11. **Any change to production code, tests, the frozen design, `CLAUDE.md`,
    OBS1, AR2, or qualification code** as part of executing Stage 1. If the
    authorized execution appears to require a code change, that is a refusal and
    a new phase, not a patch.
12. **Any new capability**: no fixer, no model-backed implementer, no second
    reviewer, no agent loop, no commit, no branch, no push, no PR, no GitHub
    write, no real-workspace write, no generalized executor.

---

## 7. The single covered invocation surface

Recorded so the reviewer can confirm that acceptance widens nothing, and so
that no alternative entry point can later be claimed to fall under this
document.

Upon acceptance, the authorized execution consists of establishing the stage
output authority for `stage_id = "S1"` and `stage_execution_id = "CFG1-S1-A1"`
through `stage_output.establish_stage_output_authority`, and passing the
resulting authority to `stage_runner.run_cfg1_stage`, which takes that
authority **positionally and takes no other parameter of any kind** — no
executor, no ports, no probe, no schedule, no arm, no ordinal, no model, no
endpoint, no output path.

That is the whole surface. `_run_cfg1_stage_with_injected_executor` is the
offline dependency-injection seam and is **not** covered by this authorization;
the genuine executor is bound inside `run_cfg1_stage` itself and is never
accepted as an argument.

**This section describes the shape of a future, separately triggered execution.
It is not an instruction to perform it, and it does not become one by being
read.**

---

## 8. Adversarial authorization analysis

Performed before authoring, against the actual shipped source and the frozen
design, and recorded so a reviewer can check the reasoning rather than the
conclusion.

**1. What exact fact is granted that is currently absent?** Exactly one: a
concrete `stage_execution_id` literal, and with it permission for one Stage-1
execution. Everything else already exists as a frozen or implemented fact.

**2. What must not become caller-selectable?** §4's twenty-two items. The test
applied to every sentence in §3: does it *reference* a frozen fact, or does it
*supply* one? Only §2 supplies.

**3. What must AIDO re-prove rather than trust from here?** §5's table. The
design's own §14.1 item 2 already says the runtime "independently re-proves this
rather than trusting the authorization document"; §5 generalizes that discipline
to every fact this document mentions.

**4. Could a malformed, reused, normalized, or path-like id widen filesystem
authority?** No, on four independent grounds: the exact-`str` type check; the
closed positive alphabet, which excludes every path-significant character; the
structural parent-equality containment proof against an already-provenance-proven
root; and the exclusive-create plus re-`lstat` one-shot namespace rule. §2.3
additionally forbids normalization anywhere in the operator path, so there is no
repair step for a hostile value to survive. Reuse is refused at
`EXECUTION_DIRECTORY_EXISTS`, before any run.

**5. Could this accidentally authorize a different model, route, schedule,
retry, prompt count, output root, Stage 2, DX1, M4, or qualification rerun?**
Each is named and refused explicitly in §3 and §6. The schedule is referenced by
pointer to `schedule.py` with an explicit "if this document disagrees with the
code, the code is right" clause (§0.2, §3.5), so even a transcription error here
cannot become authority.

**6. Could credential values, endpoint values, secrets, or raw diagnostics enter
this document?** No value was read while authoring it. §3.3 forbids the values,
and also their hashes, fingerprints, prefixes, and lengths. Only environment
**names** — already public constants in `identity.py` — appear. No raw exception
text, no absolute path, and no unbounded diagnostic appears.

**7. Could "at most 9" be misread as authority to retry or replace failed
runs?** §3.4 and §3.5 state it as a ceiling implied by one-per-admitted-run,
explicitly not a budget, quota, pool, or target, and state that a halt leaves the
remainder unavailable rather than pending.

**8. Could this be read as permission to resume after a halt?** §3.7 forbids
resume, replacement of the failed ordinal, and continuation of later ordinals,
and requires a new document with a new never-used identifier. §2.4 and §3.7
together state that `CFG1-S1-A1` is spent by its one use regardless of outcome.

**9. Could Stage-1 schedule or order be supplied here instead of by the frozen
implementation?** §3.5 and §4 forbid it; the run count is explicitly described
as *derived* by `LAST_ORDINAL` from the schedule table, not pinned here.

**10. Could a runtime or model claim substitute for an AIDO-observed fact?**
§5's closing paragraphs forbid it, restating the frozen `runtime_reported_*`
trust separation and the negative-claim scoping rule.

**11. Could writing this document trigger live, network, or model behavior?**
No. The turn read repository text, ran `git` inspection and offline string
comparison, and wrote one Markdown file. The existence check on the results root
was a stat, not a creation. §0's banner and §7's closing sentence forbid flowing
from authoring into execution.

**12. Could this authorization outlive a halt, or be reused for a later stage
execution?** No — §3.7 and §6 items 9 and 10. Mechanically, the stage-output
authority is retired at stage exit and a retired authority is indistinguishable
from an unknown one, and the execution directory's existence refuses any second
stage under the same identifier.

### 8.1 Baseline observations recorded for the reviewer

Two facts found while inspecting, neither of which contradicts the requested
authorization or required any edit:

1. **The frozen design's FU16 status block predates `CFG1-IMPL-FU4`.** It states
   that `CFG1-IMPL-FU3`'s Finding 3 — `register_config_issuance` being able to
   mint a genuine issuance token without going through `write_cfg1_pi_config` —
   "remains under independent implementation review pending a separate
   implementation FU." At the accepted implementation HEAD `3e51e3c`, that
   separate FU exists and has landed: commit *"CFG1 FU4: close L9 issuance
   provenance and retirement authority"*, with
   `config_issuance.register_config_issuance` now asking the origin question
   first, `CFG1-IMPL-FU4-FU1` additionally requiring that L9 **returned**, and
   `tests/test_cfg1_impl_fu4_provenance.py` covering it. The design document's
   status paragraph is therefore **stale, not contradicted**. It was deliberately
   left unmodified: this phase must not edit the frozen design, and a stale
   status line is not an obstacle to authorizing what §14.1 item 2 already
   specifies.
2. **The seam-digest count difference (18 vs. 20) is the design's own
   instruction, not drift** — see §3.2.

No contradiction was found between the frozen design, the shipped source,
Windows semantics, the lifecycle authority, and the authorization requested
here. Nothing was silently repaired or broadened.

---

## 9. Reviewer acceptance

An independent human reviewer should satisfy themselves, at minimum, that:

1. `CFG1-S1-A1` matches `re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ...)` and has
   never been used — including that `experiments/pi_harness_cfg1/results` is
   still absent at review time;
2. §3 references frozen facts and supplies none, and §4's list is complete for
   their own reading of the frozen design;
3. no sentence anywhere in this file can be read as broader runtime authority
   than the frozen design already permits;
4. no credential, endpoint, host, key, or secret-derivative appears;
5. Stage 2, `H`, `DX1`, `M4`, retries, reorder, replacement, fallback models and
   qualification reruns are each refused, not merely unmentioned;
6. the diff for this phase touches exactly this one file.

Until that acceptance is recorded, the status is, and remains:

```text
5F3B-HARNESS-CFG1-LIVE-S1-AUTH CANDIDATE — PENDING INDEPENDENT REVIEW
CFG1-LIVE-S1  NOT AUTHORIZED
CFG1-LIVE-S2  NO-GO / separate conditional authorization
DX1           NO-GO
M4            HOLD / NO-GO
```
