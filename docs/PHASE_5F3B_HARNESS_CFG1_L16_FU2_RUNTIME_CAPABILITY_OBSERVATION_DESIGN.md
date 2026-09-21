# Phase 5F3B-HARNESS-CFG1-L16-FU2 — Bounded Runtime Capability Observation

```text
CFG1-L16-FU2 DESIGN AMENDMENT CANDIDATE (R2) — PENDING INDEPENDENT REVIEW
```

**Revision R2** closes two blockers independent review found in R1 — the
probe-write versus shutdown-retirement race, and inconsistent duplicate-match
semantics — and freezes two implementation constraints (publication under the
reader lock; immutability of the expectation *bindings*). Every other R1
decision is preserved. §19 is the R2 changelog; §20 is the R2 concurrency
self-review.

**R2 final narrow correction (this text).** Independent review accepted R2's
architecture and left exactly two blockers, both closed here without reopening
anything R2 froze: (1) the §14 implementation gate named R1; it now requires
acceptance of **this exact R2 text**, and acceptance of R0 or R1 — or of any
earlier text of this file — grants nothing; (2) R2 gave the supervisor a
lifecycle but left `launch()` repeatable, so a supervisor could acquire a second
runtime lineage; §5.6.1 now makes launch authority **single-use, per-instance
and ordered against retirement** by the same lifecycle serialization. The
revision label stays **R2**. §19 (two added rows) and §21 (final full-lifecycle
self-review) record the change.

**R2 resource-authority correction (this text).** Independent review then
accepted the launch-authority design and left one authority defect: cleanup and
runtime operations still took their target from the public, assignable `process`
attribute, so a supported caller could substitute it after launch and steer a
write, poll, wait, signal or close at a resource AIDO did not create, stranding
the real child; the orphan path would have inherited the same flaw. §5.6.2 now
freezes a **child-resource ownership and provenance boundary**: the one object
returned by the one authorized child creation is bound by identity, in L3, into
exactly one AIDO-private role (runtime-child or orphan-child); every
authority-bearing operation derives its target from that binding; `process`
survives only as a compatibility observation. The §9 reopen list gains R-AR2-6;
§11.3c adds rows C-01…C-15; §21 asks the resource-authority question explicitly.
Nothing else R2 froze is reopened.

**R2 compatibility-authority correction (this text).** Independent review then
found that the compatibility observation was still allowed to be a plain,
caller-mutable attribute that the supervisor itself ignores. That is not sound,
because existing production code reads `supervisor.process` as an **input to
authority and lifecycle decisions** — the semantic adapter's P8 dispatch gate,
the qualification adapter's partial-launch ownership test, and CFG1's L14
`runtime_created` fact and L21 decision whether to call `shutdown()` at all. A
supported caller who could substitute it could alter those decisions even though
the supervisor's own operations were already protected. §5.6.2 now freezes
`PiRpcSupervisor.process` as a **read-only observation derived exclusively from
the genuine runtime-child binding** — there is no mutable alternative. The
private binding stays the sole operational authority; the observation is only a
projection of it and is not merged with it. §9 R-AR2-6, §7, §11.3c (C-01…C-15,
including the new C-13, C-14 and the static inventory C-15), §12.1, §15, §19 and
§21.2 are updated for this exact correction and nothing else.

**Normative-consistency cleanup (this text).** Two contradictions remained and are
removed by wording alone (§19 row E): the statements that nothing in AIDO reads
`process` (it is read by five production components, listed in §5.6.2), and the
treatment of every launch refused at L1 as a single `process` state (it is
state-dependent: §5.6.2's state rule).

**Revision R1** corrects three blocking inconsistencies found by independent
review of R0 — a sanitized state tree inside the authority-bearing observation,
post-validation mutation, and observation lifetime across shutdown — and
resolves R-31 by read-only source inspection of installed Pi 0.85.1. R0's
pre-drop bounded-classification direction is retained. §17 is the R1 changelog;
§18 is the R1 adversarial self-review.

**DESIGN AMENDMENT ONLY.** No production code or test was modified. CFG1 LIVE was
not run. No A3 authorization was created. Pi was not launched. B300 was not
contacted. No model was called. No credential or endpoint value was read. The
A1 and A2 result artifacts were opened read-only (digests in §13) and were not
modified. The installed Pi 0.85.1 `rpc-mode.js` was read, never executed (§16).
`CLAUDE.md`, the frozen CFG1 design, and the A1/A2 authorization documents were
not modified. Nothing was committed.

This document amends, and where it conflicts **governs over**, exactly the
sections enumerated in §9 of:

- [`PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md) (CFG1, frozen);
- the AR2 ingestion contract as shipped in
  [`experiments/pi_external_runtime_ar2/ar2/protocol.py`](../experiments/pi_external_runtime_ar2/ar2/protocol.py)
  and [`supervisor.py`](../experiments/pi_external_runtime_ar2/ar2/supervisor.py),
  which inherits AR0 §13.3.

Everything not enumerated in §9 remains frozen (§10).

Helper names, method names, dataclass layouts and module placement used below
are **illustrative, not frozen**. What is frozen is the authority, provenance,
containment, lifecycle and fail-closed behavior, and the regression matrix.

---

## 1. Accepted root cause

`CFG1-S1-A2` is permanently consumed. It halted at **L16** with
`CONFIG_SHAPE_MISMATCH`, zero prompt writes, `dispatch_state = NOT_ATTEMPTED`.
Its record shows H1 and H2 both matched, `runtime_reported_compat_shape =
ABSENT` (arm Q's declared shape), `runtime_reported_thinking_level = medium`,
and `runtime_reported_model_reasoning = OTHER`. The single failing conjunct of
`manipulation_check_agrees` was the reasoning flag.

The causal chain, as established by CFG1-L16-FU1 and accepted by independent
review, and re-verified against the shipped code for this amendment:

1. CFG1 generates Q's `models.json` with `{"id": <model>, "reasoning": true}`
   (`cfg1_pi_config.py`, the `provider["models"]` assignment). Pi's composed
   model object therefore carries `model.reasoning = true`, and Pi's
   `get_state` serializes that composed object (CFG1 §2.5).
2. `PiRpcSupervisor.launch` constructs one `RecordStreamReader` over Pi's stdout.
   Its reader thread does, for every framed record:
   `decode_record(raw)` → `ingest_record(decoded, stats)` → `_publish(...)`.
3. `ingest_record` ends in `drop_reasoning`, which removes **every** object key
   in `REASONING_KEYS` at any depth. `"reasoning"` is a member.
4. Therefore the published `get_state` response — the only object
   `PiRpcSupervisor.await_response` can return — has no `data.model.reasoning`.
5. CFG1's `_evaluate_model_identity` port hands `response["data"]` to
   `project_get_state`, which reads `model.get("reasoning")`, gets `None`, and
   maps it to `OTHER`.
6. `manipulation_check_agrees` requires `TRUE`; L16 refuses
   `CONFIG_SHAPE_MISMATCH`.

On the live path, as composed, **the L16 check could never pass for any arm.**
The instrument was structurally blind to the value it was specified to observe.

Classification, accepted:

- **Primary: design defect.** Two frozen contracts (§2) were each correct in
  isolation and were composed without anyone checking that the §8.2 input
  survives AR2 ingestion.
- **Secondary: test / mechanical-proof gap.** T-3
  (`test_cfg1_pi_conformance.py`) proves the installed composer serializes
  `reasoning: true`, then feeds a **hand-built dict** to `project_get_state`.
  It never passes a response through `RecordStreamReader`/`ingest_record`, so
  it could not see the drop. Its docstring's claim to "close the loop between
  §2.5's source derivation and §8.2's live manipulation check" is an overclaim
  (§11.6).
- **Not** evidence of a Pi 0.85.1 behavior change: A2 observed exactly the §2.5
  compat shape and thinking level, and the only discrepancy is fully explained
  by AIDO's own sanitizer.
- **Not** a production-code deviation: each module implements its frozen
  contract faithfully.

---

## 2. The frozen-contract contradiction

| # | Contract | Source | Requirement |
|---|---|---|---|
| C-A | AR2 ingestion / AR0 §13.3 | `protocol.py` module docstring, `RecordStreamReader` docstring, `REASONING_KEYS` | Reasoning-bearing material is removed **at ingestion, before any record is stored, counted, hashed, or written**. Removal is structural and name-based: any key in `REASONING_KEYS`, at any depth, disappears. "No reasoning-bearing value is ever stored by this process." |
| C-B | CFG1 §8.2 | frozen CFG1 design | The live `get_state` must show `runtime_reported_model_reasoning = TRUE` — exact boolean `true` at `data.model.reasoning` — or the run refuses pre-dispatch. |

Under the current composition these cannot both hold: C-B's input exists only
before the point at which C-A mandates it be gone, and the only consumer
interface (`await_response`) sits after that point.

Both security intents are **correct** and both are preserved:

- C-A's intent: no model-reasoning *content* (chain-of-thought, deltas, blocks,
  raw reasoning fields) is ever retained or exposed by AIDO.
- C-B's intent: prompt only a runtime proven, live, to have loaded the declared
  configuration — including the capability flag that couples the two compat
  decisions (`model.reasoning` gates `reasoning_effort` emission; CFG1 §2.4).

Resolution in one sentence: **before** C-A's structural drop runs, and **only**
for one AIDO-minted, AIDO-authored `get_state` command on one supervisor
instance, AIDO performs one identity test on the value at one fixed path and
keeps only a closed 4-value literal; C-A's drop then runs **unchanged** on the
same decoded object. §9 states exactly which sentence of C-A is narrowed to
permit this.

It would be false to claim the current composition "already" satisfies both;
it does not, and no re-reading of either contract makes it do so.

---

## 3. Why the capability flag is configuration metadata, not reasoning content

`REASONING_KEYS` is a **name-based**, deliberately over-inclusive structural rule.
It is correct for it to catch `model.reasoning`, and this amendment does not
narrow it. But what the key carries in this one position is not reasoning:

- **Provenance.** `data.model.reasoning` in a `get_state` response is Pi echoing
  the composed model definition. For CFG1 that definition is **authored by
  AIDO** in the generated `models.json` (`"reasoning": true`). It is a
  capability declaration AIDO wrote, read back.
- **Timing.** `get_state` triggers no inference (`handshakes.py`: H2
  `triggered_inference: False`; CFG1 L16 runs before L18's only prompt write).
  No model has produced any token when the value is observed.
- **Content.** On a conforming runtime it is a JSON boolean. It is not
  model-generated text, not a delta, not a block, not a summary, and not
  derivable from anything a model thought.
- **Information retained.** The retained literal ranges over four values
  (< 2 bits), all four fixed by AIDO. For any non-boolean input — including a
  hypothetical string that did contain text — the output is the constant
  `OTHER`, which carries zero bits about that input beyond "was not an exact
  boolean and was present".

This is why the classification is compatible with AR0 §13.3's *purpose* ("AIDO
builds no chain-of-thought observability"). It is **not** a reason to exempt the
key from the drop: C-A's structural drop runs on this key exactly as before, and
its statistics count it exactly as before (§6.3). The rule stays name-based and
conservative; only a pre-drop, fixed-path, closed-output test is added.

---

## 4. Candidate mechanisms considered

| Option | Verdict | Reason |
|---|---|---|
| A. Remove `"reasoning"` from `REASONING_KEYS`, or exempt `data.model.reasoning` from the drop | **Rejected** | The raw key/value would survive into the sanitized record. Silently redefines C-A. |
| B. Rewrite the key in place (e.g. replace the value with an enum, or rename the key) inside the sanitized record | **Rejected** | Alters the sanitized record shape seen by every AR2/O1/qualification consumer; any record carrying the rewritten key would become "evidence" by shape alone — exactly the shape-only inference the requirements forbid; no correlation. Also "generic redaction of the raw value instead of dropping it". |
| C. A pre-ingestion callback / raw-record hook / caller-supplied path or extractor | **Rejected (forbidden)** | Creates a reusable raw-runtime inspection API. |
| D. A second, unsanitized stdout channel or raw-record buffer for handshakes | **Rejected** | Same as C, and retains raw records. |
| E. Drop the live check; infer `TRUE` offline from the generated config | **Rejected** | Abandons C-B's intent: §8.2 exists precisely to catch Pi normalizing the composed model differently from the source derivation. |
| F. Have the TypeScript extension report the flag over the broker | **Rejected** | The broker protocol is closed at two operations (`wire.py`); adding one is a protocol change, and the extension is untrusted Pi-process code. |
| G0. (R0 of this amendment) A redeemable observation object carrying the literal **plus a deep copy of the sanitized `get_state` record** | **Withdrawn (R1)** | Self-contradictory ("carries no model subtree" while carrying the state tree); moves a mutable tree — which per §16 also carries `model.baseUrl` and `sessionFile` — across the authority boundary; leaves an outstanding redeemable object alive past shutdown. |
| **G. A supervisor-owned, one-shot, correlated state probe that, inside the reader thread and before the matched record is published, reduces that one record to four exact scalars (one bool, three closed-enum `str`), and returns them from a single parameterless call that arms, writes, waits and consumes in one transaction** | **Chosen (R1)** | The raw value never leaves the reader's existing pre-sanitization window; the sanitized record never crosses the authority boundary; every L16 fact derives from one object no other thread can yet reference; no redeemable authority can outlive the call. |

Option G is **not** a generic observer. It has one fixed command type, one fixed
raw path, fixed (statically bound, never injected) classifiers, one slot, one
use per supervisor lifetime, and a probe call with **no parameters** (not even a
timeout — it uses the existing `RunBounds.startup_deadline_seconds`). Its only
configuration is two exact `str` expectations — the provider id and model id
H2 compares against — bound **once, at supervisor construction**, never at probe
time; they select no path, key, record, or command and feed only H2's frozen
equality comparison (§5.2). If an implementation cannot realize G without a
parameter that selects a path, key, command type, extractor, predicate,
classifier or callback, it must **stop and report**, not generalize.

---

## 5. The bounded-observation authority model

### 5.1 Principals

| Principal | May | May not |
|---|---|---|
| `PiRpcSupervisor` instance (AIDO) | Mint the probe id; author the probe command (type fixed to `get_state`); arm, wait on, consume and retire **its own** slot; retire itself on shutdown | Accept an id, type, path, key, extractor, classifier or callback from any caller; return any mapping, list, record, subtree or id to the caller |
| The supervisor's own `RecordStreamReader` instance | Match one decoded record against the armed slot; classify one fixed raw path; reduce the sanitized form of that same record to the bounded facts **before** publishing it; resolve the slot | Retain the decoded record, `data`, the model subtree, or any raw value; expose any per-record hook |
| CFG1 L16 (the one consumer) | Invoke the probe once on `state.supervisor` (the object L14 launched), type-check the four scalars, and write them into `observations` in the same function | Accept bounded facts, literals, or an observation from **its own** caller; construct facts; call the probe on any other supervisor |
| Pi (observed runtime) | Report a state document | Gain any authority. Its report stays a `runtime_reported_*` **untrusted claim** (§5.7) |
| Any other caller of `send_command` | Send `get_state` with its own id | Obtain any observation from that response |

### 5.2 Construction-time binding (before launch)

The supervisor is constructed with an **optional** pair of exact expectations
`(expected_provider, expected_model)`. Each must be a non-empty `str`
(`type(x) is str`, so `str` subclasses are refused too); anything else refuses
construction. When absent (every AR2, AR2-O1 and qualification construction),
the probe is **unavailable** and refuses before sending anything, so AR2's
existing callers are untouched (§12.1).

**Binding immutability (R2, normative).** What must be immutable is the
**binding**, not merely the value's Python type. After construction, the
supported API offers **no** way to change which provider/model the probe will
compare against: no public attribute holding them is assignable, there is no
setter, no mutator method, no keyword on the probe or on any other method, and
no reconfiguration path through `launch()` or elsewhere. If the values are
exposed for diagnostics at all, they are read-only. The probe copies them into
the slot at arm time (§5.3), and H2 in §5.4 (e) reads only the slot's copy.
Scope, stated honestly: Python cannot stop code that deliberately rebinds a
private attribute from outside the supported API. That is outside this
boundary, as it is for every in-process AIDO object; the requirement is that no
*supported* path, and no public name, permits it (R-39).

**Provenance agreement (R2, normative).** CFG1's supervisor builder derives the
constructor expectations and `build_pi_argv`'s `provider=`/`model=` arguments
from the **same frozen module constants** (`PROVIDER_ID`, `CFG1_MODEL_ID`), with
no literal, environment, config-file or runtime-derived source for either. H2
therefore compares the runtime's report against exactly the identity AIDO
launched. The security property is **provenance and exact value agreement**,
never Python string object identity (R-40).

### 5.3 The probe transaction (one call, no parameters)

The probe is **one** supervisor method with no parameters. Its entire
lifecycle — arm, write, wait, consume — happens inside that one call, so no
armed, resolved or unconsumed slot, and no redeemable object, is ever
observable to any caller.

1–3. **Eligibility, mint, arm and write-commit — one critical section of the
   supervisor's lifecycle serialization (§5.6).** Atomically, with respect to
   retirement:
   - check eligibility: launch authority `INSTALLED` and lifecycle `OPEN`
     (that is, supervisor `ACTIVE`, §5.6.1 — the one successful launch's one
     lineage, with its one installed reader; a failed, retired or
     never-launched supervisor is not eligible), expectations bound, slot
     `UNARMED` (first and only use) — otherwise raise a fixed-text error and
     **nothing is written**. The probe operates only on the reader and slot
     that one install committed; launch authority is single-use, so nothing
     can replace them underneath a probe;
   - mint a fresh CSPRNG id (≥ 128 bits, ASCII `str`, e.g.
     `secrets.token_hex(16)`), refused if already a key of `activity.responses`;
   - arm, under the reader lock nested inside: slot ← `ARMED` with the id and
     the slot's copy of the two expectations (all immutable scalars);
   - **commit the write**: write state ← `WRITE_COMMITTED`. This is the probe
     write's **linearization point** (§5.6).

   A pre-write `ACTIVE` check followed by a write outside this critical section
   is **not** sufficient and is forbidden: retirement could linearize between
   the check and the write.
4. **Write** `{"id": <minted>, "type": "get_state"}` (type is a module
   constant), holding neither lock (§5.6 lock rules). The write's **target** is
   the stdin captured in the runtime-child ownership binding (§5.6.2), obtained
   and verified inside the steps 1–3 commit section so that it is the same
   binding the eligibility check examined; it is never re-read from `process` or
   any other public name. Then, inside the
   lifecycle serialization: write state ← `WRITE_DONE` on success; on failure,
   write state ← `WRITE_FAILED`, slot → `RETIRED` (unless already terminal),
   raise. Either way, anyone waiting for the write state to leave
   `WRITE_COMMITTED` is notified.
5. **Wait** on the existing monotonic `_wait` machinery with
   `startup_deadline_seconds`, until the slot leaves `ARMED`, a terminal stream
   outcome, process exit, deadline, or supervisor retirement (checked every
   iteration).
6. **Consume**, as one critical section of the lifecycle serialization with
   the reader lock nested inside (§5.6 linearization):
   - supervisor `RETIRED` → raise;
   - slot `POISONED` → slot `CONSUMED`, raise;
   - slot `RESOLVED` → read the four scalars, slot `CONSUMED`, return them;
   - slot still `ARMED` (no correlated response) → slot `CONSUMED`, return the
     **unobserved facts**: `(False, "NOT_OBSERVED", "NOT_OBSERVED",
     "NOT_OBSERVED")`.
7. A `finally` clause guarantees that **every** exit from the call other than a
   normal return leaves the slot `RETIRED` or `CONSUMED`, never `ARMED` or
   `RESOLVED`, and leaves the write state out of `WRITE_COMMITTED` (it becomes
   `WRITE_FAILED` if the write did not complete), notifying any waiting
   `shutdown()`.

The return value is a value, not an authority: a plain tuple or an equivalent
record whose fields are exactly **one `bool` and three `str`**. Its
immutability comes from those scalars being immutable, **not** from any
`frozen=True` wrapper, and no field is a container. It carries no id, no
mapping, no list, no response, no `data`, no model subtree, no base URL, and no
raw value. Nothing anywhere accepts it back as input (§5.5), so holding it
confers nothing.

### 5.4 Reader-side matching, classification and reduction (before publication)

For each record decoded by `decode_record`, the reader performs, **in this
order and in its own thread**:

**(a) Match — exact duplicate semantics (R2, normative).** Under the reader
lock, read the slot state. The slot keeps its expected id from arming until it
becomes `CONSUMED` or `RETIRED`.

| Slot state | Probe matching performed? | On a match |
|---|---|---|
| `UNARMED` | **No** | — |
| `ARMED` | Yes | proceed to (b)–(f): the one classification path |
| `RESOLVED` | Yes | **duplicate**: slot → `POISONED` **immediately**, in this same critical section, **without** running (b), (c) or (e); the stored facts are discarded |
| `POISONED` | **No** (already fails closed; nothing can un-poison it) | — |
| `CONSUMED` | **No** | — |
| `RETIRED` | **No** | — |

A record **matches** iff `type(record.get("type")) is str` and equals
`"response"`, and `type(record.get("id")) is str` and equals the slot's
expected id exactly (no case folding, trimming or normalization). Whatever the
outcome, the record itself then continues through (d) and publication exactly
like any other record. Only the reader thread resolves the slot, and it
processes records sequentially, so no other record can move the slot from
`ARMED` to `RESOLVED` between this step and (f).

**(b) Validate the correlation.** For a match while `ARMED`:
`type(record.get("command")) is str` and equals `"get_state"`, else
`POISONED`. `success_ok := record.get("success") is True`.

**(c) Classify the raw capability flag — before `ingest_record`.** Only if
`success_ok`, by exactly:

```text
data  = record.get("data")          -> not a dict            -> reasoning := NOT_OBSERVED
model = data.get("model")           -> not a dict            -> reasoning := OTHER
"reasoning" in model                -> False (key absent)    -> reasoning := OTHER
value = model["reasoning"]
value is True                       ->                          reasoning := TRUE
value is False                      ->                          reasoning := FALSE
otherwise                           ->                          reasoning := OTHER
```

If `data` is not a dict, all three state facts are `NOT_OBSERVED` and `h2`
is `False` (§8). The value is subjected to the two identity tests only (§6.2 I-6/I-7).

**(d) Sanitize.** `sanitized = ingest_record(record, stats)` — **unchanged**.
The raw `reasoning` key is structurally dropped exactly as today.

**(e) Reduce the sanitized record to bounded facts — before publication.**
Still in the reader thread, on the local `sanitized` object that **no other
thread yet references**:

- `h2 := evaluate_model_identity(sanitized, expected_provider=…,
  expected_model=…).get("passed") is True`, and additionally `False` unless
  `success_ok`. The frozen handshake function is called **unchanged**; its
  returned diagnostic dict is discarded immediately; only the exact `bool` is
  kept.
- `compat_shape`, `thinking_level` := the frozen §8.2 classifications applied
  to `sanitized["data"]` (mapping and domains verbatim, §8).

These classifiers are statically bound code with **exactly one definition**
each (placement not frozen; CFG1's current `_classify_compat_object` and the
thinking-level mapping are moved or re-exported, never duplicated). They are
never passed in at runtime.

**(f) Resolve and publish atomically.** In one critical section under the
reader lock: if the slot is still `ARMED` (not `RETIRED` by a racing shutdown),
store the four scalars and set `RESOLVED`; then publish `sanitized`. If the slot
was retired meanwhile, the facts are discarded and the slot stays `RETIRED`;
publication proceeds as today.

**Publication-lock constraint (R2, implementation).** The shipped
`RecordStreamReader._publish()` acquires the reader's non-reentrant `Lock`
through its `Condition`. Calling it while already holding that lock for (f)
would self-deadlock the reader thread. Implementation is therefore
**authorized** to refactor publication internally, e.g. a locked helper that
appends and calls `notify_all()` on the `Condition` while the caller already
holds it, with the existing `_publish()` delegating to it. Replacing the lock
with an `RLock` is **not required** and is not the preferred fix. The existing
post-publish `record_count()` cap check also acquires the lock, so it must stay
**outside** the (f) critical section. Observable publication behavior
(ordering, `notify_all` wake-ups, cap semantics) is unchanged (R-24, R-38).

**Exception containment.** Steps (a)–(c) and (e) are wrapped so that any
exception sets the slot `POISONED` with a fixed reason, never formats the
exception, and never reaches the reader's `read_error` (which does
`f"{type(exc).__name__}: {exc}"`). Step (d) is the unchanged `ingest_record`
and keeps its existing behavior. The reader never raises out of the probe
path.

After (a)–(f) the reader continues exactly as today. Non-matching records go
straight through (d) and publication, with no other change.

### 5.5 H2 and §8.2 derive from the same response — the proof

1. There is exactly **one** `get_state` at L16: the probe's. CFG1 no longer
   sends an `h2-…` `get_state`, so `commands_sent` is unchanged from the frozen
   lifecycle.
2. All four facts are computed in step (c)/(e) from **one** decoded record and
   its **one** sanitized form, in one reader-thread iteration, identified by one
   AIDO-minted id.
3. At the moment of step (e), the sanitized object is a local of the reader
   thread; it has not been published, so no supervisor method, `_absorb`,
   `activity.responses`, `sanitized_events()`, or CFG1 code can hold a reference
   to it. **No supported caller can mutate it between the H2 computation and the
   §8.2 computations.** The raw decoded object is likewise reader-local.
4. After step (e) only immutable scalars exist in the slot. Mutating the
   published sanitized record afterwards (through `activity.responses`,
   `sanitized_events()`, or anything else) cannot change any fact.
5. A second record with the same id while the slot is `RESOLVED` poisons it
   immediately without reclassification (§5.4 (a)), so the four facts can never
   be drawn from two records, and a duplicate can never overwrite them.
6. CFG1 L16 obtains the four scalars **only** by calling the probe itself on
   `state.supervisor`, in the same function that writes them into
   `observations`. That function has no parameter through which facts,
   literals, a response, a state document, or another supervisor's result can
   enter.

### 5.6 Lifecycle and retirement (normative)

**Supervisor lifecycle.** A supervisor begins **unlaunched**. It is `ACTIVE`
only after its one successful `launch()` (§5.6.1) and only until `shutdown()`
begins; then it is `RETIRED`, permanently. `shutdown()`'s **first** action,
before closing stdin or any rung of the ladder, is **retirement**: one critical
section of the lifecycle serialization, with the reader lock nested inside once
the slot is bound to a reader (§5.6.1 L3; before that, no reader thread can reach
the slot and the serialization alone orders it), that sets supervisor → `RETIRED` and any slot not
`CONSUMED` → `RETIRED`. Retirement is idempotent and monotonic: repeated
`shutdown()` never returns a supervisor or slot to any earlier state, and it
applies to a supervisor in **any** launch state, including one never launched
(which it makes permanently unlaunchable, §5.6.1). A supervisor whose `launch()`
failed is never `ACTIVE` and never probe-eligible, whether or not a child or
reader was created before the failure.

**Lifecycle serialization (R2).** The supervisor owns a lifecycle
serialization, **distinct from the reader lock**, that orders exactly these
critical sections: **launch commit, and launch install/failure/orphan commit
(§5.6.1)**; probe eligibility→mint→arm→write-commit (§5.3 steps 1–3); the
write-state update after the write (step 4); consumption (step 6); and
retirement. The mechanism is not frozen (a supervisor-owned lock with a
condition and a write-state field is sufficient). What is frozen:

- **Lock order.** Lifecycle serialization first, then the reader lock; never
  the reverse. The reader thread **never** takes the lifecycle serialization.
- **Never held across blocking I/O or waits.** Neither the lifecycle
  serialization nor the reader lock is held during the stdin write, during the
  §5.3 step-5 wait, **or during child-process creation** (§5.6.1 step L2). The
  reader lock in particular must never be held across
  the write. The reader thread needs that lock to publish; if it could not
  publish it would stop draining stdout, Pi could block on stdout and stop
  reading stdin, and the write would never finish. That deadlock must not be
  introduced.
- **Write state.** `WRITE_NONE → WRITE_COMMITTED → (WRITE_DONE | WRITE_FAILED)`,
  changed only inside the lifecycle serialization, monotonic, with at most one
  transition to `WRITE_COMMITTED` per supervisor lifetime.

#### 5.6.1 Launch authority (R2 final correction, normative)

**Defect closed.** The shipped `PiRpcSupervisor.launch()` is a public method
with no one-shot guard: each call runs `subprocess.Popen`, assigns a new
`process`, and constructs and starts a new stdout reader and a new stderr
reader, overwriting the previous ones. R2's lifecycle, probe slot and expectation
provenance are all defined per runtime lineage, and a second `launch()` on the
same supervisor would silently replace that lineage underneath them (and would
strand the first child). Without a guard the R2 lifecycle proves nothing about
which process and reader its slot belongs to.

**Frozen semantic invariant** (names below are illustrative; the invariant is
not):

1. A supervisor begins **unlaunched**.
2. **Exactly one** launch attempt may ever acquire runtime-creation authority.
3. A successful first launch establishes the supervisor's **one** `ACTIVE`
   runtime and **one** reader lineage.
4. A **failed** launch leaves that supervisor **permanently** ineligible for
   another launch attempt — including a launch that failed after a child had
   already been created.
5. `launch()` while `ACTIVE` **refuses before** creating any process, reader,
   thread or pipe.
6. `launch()` after retirement/shutdown **refuses before** creating any process,
   reader, thread or pipe.
7. **No supported method** returns a supervisor to an unlaunched or launchable
   state.

**State.** Two monotonic supervisor fields, written **only inside the lifecycle
serialization** (§5.6) and initialized only by construction:

```text
launch authority : UNUSED -> COMMITTED -> ( INSTALLED | FAILED )
lifecycle        : OPEN   -> RETIRED
```

The names used elsewhere in this document are derived, not separately stored:
`UNLAUNCHED` = UNUSED ∧ OPEN; `LAUNCHING` = COMMITTED ∧ OPEN; **`ACTIVE` =
INSTALLED ∧ OPEN**; launch-failed = FAILED ∧ OPEN; `RETIRED` = lifecycle
RETIRED, whatever the launch authority. Every "eligible" or "`ACTIVE`" check in
§5.3 means INSTALLED ∧ OPEN. Both fields only move forward along the arrows;
nothing writes `UNUSED` or `OPEN` after construction.

**Not an id.** The boundary is the supervisor **instance's own** launch-authority
field and the objects that one launch attempt committed — never a runtime id,
name, string, pid, counter or any text. The probe id of §5.3 is a per-frame correlation
nonce and confers no lineage authority. The guard is **per-instance state**:
nothing is a module-level or class-level flag, because CFG1 builds a fresh
supervisor per run and a process-wide flag would refuse the next run's legitimate
first launch. A new supervisor instance is a new, independent lineage; nothing
carries launch state from one instance to another.

**The launch protocol.** Three steps. L1, the L2 failure update and L3 are each
one critical section of the lifecycle serialization, and **neither lock is held
while the child is created**.

- **L1 — commit launch authority** (one lifecycle-serialization section).
  If lifecycle is RETIRED **or** launch authority is not UNUSED, raise a
  **fixed-text** `PiSupervisorError` (no argv, environment, path, id or state
  formatted into it) and return. Nothing was created: no `Popen`, no reader, no
  thread, no pipe. Otherwise launch authority ← `COMMITTED`. This is the launch's
  **linearization point** and it is **single-use**: it is the only transition out
  of UNUSED, so at most one call per supervisor lifetime ever passes it, and
  every other call — sequential, concurrent, or after retirement or failure —
  ends at the refusal above.
- **L2 — create the child** (no lock held). The shipped `Popen` call, with its
  shipped arguments, environment, working directory and pipes, unchanged. It is
  the module's **only** child-creation site and is reachable only after L1. Its
  return value is held in a local that is never stored under any public name; that
  exact object is the **only** object that can acquire this launch attempt's child
  authority (§5.6.2). If it raises `OSError` (no child exists), one
  lifecycle-serialization section sets launch authority ← `FAILED` and the shipped
  `RUNTIME_LAUNCH_FAILED` error is raised as today; no ownership binding is made
  and the compatibility observation `process` stays `None`.
- **L3 — bind, then install or orphan, atomically** (one lifecycle-serialization
  section, entered with the child already created). The section decides, by
  lifecycle, which of two mutually exclusive outcomes occurs, and in **either**
  outcome its first act is to bind the L2 object, by identity, into exactly one
  AIDO-private ownership role (§5.6.2) — never into a public name:
  - **Lifecycle OPEN — install.** The child is bound as the **runtime-child**
    (§5.6.2) first, before any reader exists; the compatibility observation
    `process` then reflects that binding; the stdout
    `RecordStreamReader` and the stderr `BoundedStreamReader` are constructed —
    from the pipe handles captured in that binding, not re-read from any public
    name — and started exactly as otherwise shipped; **last**, the supervisor's probe slot is bound to
    that one stdout reader (under the reader lock, nested), so a partially
    installed lineage never has a slot any reader thread can reach; launch
    authority ← `INSTALLED`. Until the slot is bound, that reader treats every
    record as having no armed probe (no matching, §5.4 (a) `UNARMED`). The
    reader construction and start are non-blocking with
    respect to Pi (they read nothing on the calling thread and wait on nothing
    outside this process), so they may run inside the section, and the reader
    threads never take the lifecycle serialization. Because L1 passes at most once,
    the runtime-child binding, both readers and the slot binding are installed
    **once and never replaced**, and nothing in a launch touches the expectation
    binding. If any install step raises, launch authority ← `FAILED` in the same
    section and the exception propagates as shipped: the supervisor is never
    `ACTIVE`, and the runtime-child binding **stays** — the compatibility
    observation `process` still shows that child, the shipped observable on which
    CFG1 L14 and the qualification adapter's partial-launch handling depend — so
    `shutdown()` owns its teardown, through that binding, exactly as it does today.
  - **Lifecycle RETIRED — orphan.** Retirement was ordered **after** the L1
    commit and **before** this section. The child exists; it is **never installed
    and never `ACTIVE`**. In the same section, before it is released, the L2
    object is bound as the **orphan-child** (§5.6.2), so it is attributed by an
    AIDO-private ownership binding rather than held only by a local variable;
    launch authority ← `FAILED`; **no** reader, thread, slot binding or runtime-child
    binding is made, and the compatibility observation `process` stays `None`.
    After the section, with no lock held, **the launching call itself** tears that
    one child down — consuming only the orphan-child binding, §5.6.2 — using the
    existing direct-child ladder's rungs, bounds and claim
    scope (close its stdin, wait, terminate, wait, kill, wait; then close the
    remaining pipe handles) — no new rung, no new signal, no new claim, and
    whether it shares a private routine with `shutdown()` is not frozen. Its
    outcome is stored in a distinct `orphan_termination` diagnostic field, then the
    call raises the same fixed-text refusal as L1. A cleanup problem that leaves
    the child unreaped is recorded truthfully, never claimed as termination.

**No stranded COMMITTED, no unattributed child.** Any exception after L1 — a
`BaseException` such as `KeyboardInterrupt` included — must leave launch authority
`FAILED`, never `COMMITTED` forever, before it propagates. If a child had already
been created and not yet bound when such an exception occurred, the unwinding path
binds that L2 object as the orphan-child (a lifecycle-serialization section) and
the launching call tears it down; if it had already been bound, the binding's role
stands. No wait anywhere in this design blocks on launch authority, so no waiter
can be stranded by a launch that never settles.

**One owner per child, decided by one order.** `shutdown()`'s ladder consumes only
the runtime-child binding; the orphan path consumes only the orphan-child binding.
The two are exclusive because L3 and retirement are sections of the same
serialization and L3 makes exactly one binding: if L3 is ordered **first**, the
child is bound as the runtime-child and the later retirement makes `shutdown()` its
sole owner; if retirement is ordered first, L3 makes the launching call the sole
owner of an orphan-child, and `shutdown()` — which by then either has not read the
runtime-child binding or read it empty — never touches it. Retirement therefore
needs **no** wait for an in-flight launch. No path installs a process or reader on
a retired supervisor.

**Race outcomes** (each execution is exactly one of these, by lock order):

| Interleaving | Result |
|---|---|
| Retirement before L1 | L1 refuses. **Zero** `Popen`, readers, threads, pipes. Launch authority stays UNUSED; lifecycle RETIRED refuses every later attempt. |
| L1 before retirement, L3 before retirement | One installed lineage (runtime-child binding, both readers, slot). Retirement then retires it; `shutdown()` tears it down through that binding. No second lineage can exist (L1 cannot pass again). |
| L1 before retirement, retirement before L3 | The child is an **orphan**: bound as the orphan-child, never installed, torn down by the launching call through that binding, which then raises. No reader or thread ever exists for it. `shutdown()` is unaffected. |
| Two concurrent `launch()` calls | Exactly one passes L1; the other refuses **before** `Popen`. At most one child and one reader lineage. |
| `launch()` while `ACTIVE`, or after RETIRED, or after FAILED | Refuses **before** `Popen`. The ownership bindings, both readers, the slot and the expectation copy are untouched. |

**No reset.** Every supported writer of the two fields is enumerated: the
constructor's initialization, L1, the L2 failure section, L3, and retirement —
each moving strictly forward. `launch()` never sets UNUSED or OPEN, `shutdown()`
never sets OPEN, no failure path resets to UNUSED, and no method (public or
private) re-arms launch. As with the expectation binding (§5.2), Python cannot
stop code that deliberately rebinds a private attribute or calls `__init__` again
on a live instance; that is outside this boundary, and no *supported* API does it.

**What is unchanged.** `launch()` stays parameterless; the `Popen` arguments,
`shell=False`, environment, cwd, pipes, and reader parameters are unchanged; the
shipped `RUNTIME_LAUNCH_FAILED` behavior on a `Popen` `OSError` is unchanged; a
single successful launch on a fresh supervisor behaves exactly as today. What
changes is only that a **second** call on one instance now refuses, that
retirement now also makes a never-launched supervisor permanently unlaunchable,
and that a launch racing retirement can no longer install onto a retired
supervisor. No existing caller launches one instance twice (verified for
`run_ar2.py`, AR2-O1's handshake, the qualification adapter and CFG1 L14). What
the launch may and may not bind, and what every later operation may target, is
frozen separately in §5.6.2.

#### 5.6.2 Child-resource ownership and provenance (R2 resource-authority correction, normative)

**Defect closed.** In the shipped supervisor the child is reachable only through
the public, freely assignable attribute `process`, and every authority-bearing
operation re-reads it at the moment of use: `send_command` (stdin write and
flush), `_wait` (`poll()`), `shutdown()` (stdin close, `wait`, `terminate`,
`kill`) and `launch()` (the pipes handed to the readers). §5.6.1 stops a second
`launch()`, but nothing stops a supported caller from assigning
`supervisor.process = <some other process-like object>` **after** launch. Every
later write, liveness poll and cleanup would then be steered at a resource AIDO
did not create, and the genuine child would never be written to, polled or
signalled — stranded. The new orphan path would have the same defect if its child
were held in a mutable attribute used as teardown authority. Even a public name
that holds the genuine child does not close the hole by itself, because the
child's `.stdin`, `.stdout` and `.stderr` are ordinary rebindable attributes of
that object.

**Frozen invariants** (the mechanism and names are **not** frozen; these are):

1. **Origin.** The object returned by the one authorized L2 creation is the
   **only** object that can acquire that launch attempt's child authority. No
   caller-supplied object, no value assigned to a public name, no object from
   another supervisor, and no pid, id, string or description can acquire it.
2. **One role, by identity.** At L3 that exact object is bound — by object
   identity, never by any textual attribute — into exactly **one** AIDO-private
   role: the **runtime-child** (the supervisor's one lineage child) or the
   **orphan-child** (§5.6.1). The two roles are **mutually exclusive** for one
   launch attempt: L3 makes exactly one binding, and no path makes the other.
3. **Private and write-once.** Neither binding is reachable through, or writable
   from, any supported API. Each is written only inside L3 (or the exception-
   unwinding orphan bind of §5.6.1) from the L2 object, once, and is **never**
   replaced, cleared or rebound. A refused or repeated `launch()` cannot touch
   either (L1 refuses first).
4. **The compatibility surface is a read-only projection of the runtime-child
   binding — never authority, and never mutable.** The public `process` is
   retained as a **read-only observation derived exclusively from the genuine
   runtime-child binding** (contract below). `PiRpcSupervisor` takes **no target**
   from it: it is not write, poll, wait, signal or cleanup authority, however
   much its value looks like a `Popen`. But other AIDO components read it as an
   **input to lifecycle, dispatch, cleanup and diagnostic decisions**, so it must be mechanically
   unforgeable: assignment and deletion through any supported API **refuse**.
   There is no plain-attribute option, and no "refuse or be inert" alternative.
5. **Every authority-bearing consumption derives its target from the genuine
   binding** (table below).
6. **Retirement never retargets.** Retirement invalidates *operation* authority
   (the probe's write and wait, §5.6) and changes no binding. *Cleanup* authority
   survives retirement — it is what `shutdown()` exists to consume — and remains
   bound to the same child. The orphan binding is spent by its one teardown.
7. **Cleanup proves its target.** A consumption may act only on a target it has
   verified (below), never on "whatever is currently stored".

**What a binding holds.** An immutable, AIDO-private ownership record created
only in L3: the child object, the child's stdin, stdout and stderr pipe handles
**captured from that exact child at bind time**, the role, and the owning
supervisor instance. Capturing the pipes is what makes a later assignment to the
exposed child's `.stdin`/`.stdout`/`.stderr` inert: writes and closes use the
captured handles, never a re-read of an attribute. No API accepts a binding, a
child or a pipe as input.

**Consumption table.** Every row derives its target from the named binding and
from nothing else:

| Operation | Consumes | Target |
|---|---|---|
| CFG1 probe stdin write (§5.3 step 4) | runtime-child (operation) | captured stdin, read inside the §5.3 step 1–3 commit section, i.e. the same binding the eligibility check examined |
| `send_command` (H1, L18 prompt, every generic command) | runtime-child (operation) | captured stdin; the shipped "no live process stdin" error when the binding is empty or stdin was `None` |
| `_wait` liveness `poll()` (probe step 5, `await_response`, `await_settled`) | runtime-child (operation) | the bound child; skipped, as shipped, when the binding is empty |
| `shutdown()`: stdin close, `wait`, `terminate`, `kill` | runtime-child (cleanup) | captured stdin and the bound child |
| L3 reader construction | runtime-child | the captured stdout and stderr |
| Orphan teardown: stdin close, `wait`, `terminate`, `kill`, pipe closes | orphan-child (cleanup) | the orphan binding only |

No `PiRpcSupervisor` operation takes a target from the public `process` (other AIDO
components do read that observation; see the inventory below). `shutdown()` reads the
runtime-child binding **inside its retirement section**, so its ownership decision
sits in the same total order as L3: it sees the binding if L3 was ordered first
and an empty binding otherwise (in which case a later child can only be an
orphan). An empty binding leaves `shutdown()` exactly where the shipped
`process is None` early return leaves it.

**Verification at consumption (defense in depth).** Each consumption obtains its
target through one private accessor that checks: the binding exists; its role is
the role that operation consumes; its owning supervisor is **this** instance; the
*other* role's binding is empty (mutual exclusion); and, for orphan teardown, that
the bound child is the identical object the L2 creation site returned to this very
call. On any failure the consumption **fails closed**: no write, poll, signal or
close is issued to the unverified target, and a fixed-text error is raised
(retirement still happens first in `shutdown()`). These checks are what make a
smuggled cross-role or cross-supervisor binding harmless. They do **not** extend
the supported-API boundary: code that deliberately rebinds a private attribute is
outside it, as in §5.2 and §5.6.1.

**The `process` compatibility surface — frozen contract.**
`PiRpcSupervisor.process` is a **read-only observation derived exclusively from
the genuine runtime-child ownership binding**. The Python mechanism is not frozen
(for example a read-only property with no setter and no deleter). A caller-mutable
plain attribute is **not** permitted, and there is no alternative shape.
Mechanically, all of the following hold:

1. **Before** a runtime-child binding has ever been established — unlaunched,
   mid-launch before L3, after an L2 `OSError`, after a retirement that preceded
   the first launch — `process` reads `None`.
2. **After** the runtime-child binding is made, `process` reads **exactly that
   genuine child object** (`is`), from then on.
3. **After a partial install failure** in which the runtime-child binding exists
   and `launch()` raised, `process` still reads that genuine child — preserving the
   shipped partial-launch handling.
4. **An orphan child is never exposed** as `process`: the observation is derived
   from the runtime-child binding only and never reads the orphan binding, so in
   the orphan path it reads `None`.
5. **Assignment refuses** through the supported/public API — of `None`, of a
   running or exited process-like object, and of a genuine `Popen` from another
   supervisor alike — and leaves the observation unchanged.
6. **Deletion refuses**, likewise.
7. **No other way to change it.** No public setter, mutator, `launch()` keyword,
   constructor parameter or alias, or reconfiguration method can substitute its
   value, and a value stored under the same name in the instance's own namespace
   must not shadow it.
8. **Retirement does not retarget it, and a refused or repeated `launch()` cannot
   replace it.** After `shutdown()` it keeps reading the same genuine child, as
   the shipped attribute does. L1 refusal itself never creates, clears, replaces
   or retargets the binding, so a launch refused at L1 leaves `process` exactly as
   it was — see the state rule below.
9. **Derived, never stored twice.** Its value is computed on each read from the
   private runtime-child binding; no second mutable storage location, cache or
   shadow holds the child (the shipped `__init__` assignment of `process` is
   removed). A read takes no lock and issues no action — one read of a write-once
   reference — so it can only ever observe `None` or the genuine child.

**State rule.** `process` is determined **solely** by whether a runtime-child
binding has ever been established, and by nothing else — not by the lifecycle
state (`OPEN`/`RETIRED`), not by whether the launch succeeded or failed once a
binding exists, and not by any L1 refusal:

| State | `process` |
|---|---|
| Never launched (including retired before its first launch); mid-launch before L3; after an L2 `OSError` | `None` |
| A runtime-child binding exists — after install, after a partial install failure, after retirement or `shutdown()` | that one genuine child, `is`-identical, permanently |
| Orphan path only (no runtime-child binding was ever made) | `None` |
| A launch refused at L1 (repeated, while `ACTIVE`, after `FAILED`, after `RETIRED`, or the concurrent loser) | **unchanged from before the call**: `None` if no binding was ever established (for example a never-launched supervisor retired before its first launch); the same genuine child if one exists |

**Two concepts, not one.** The private runtime-child binding is the **sole
operational resource authority** that `PiRpcSupervisor` uses to choose targets for
write, poll, wait, close, terminate, kill and reader construction. The public
`process` is a **read-only compatibility observation derived from that binding**.
It is **not** write, poll, wait, cleanup or signal authority for `PiRpcSupervisor`
and grants none: no supervisor operation takes a target from it. **Other AIDO
components deliberately read it** — as an input to lifecycle, dispatch, cleanup or
diagnostic decisions, exactly as in the inventory below — and those readers gain no
ability to retarget any of the supervisor's operational actions, because the
observation is read-only and always projects the genuine binding. That
integrity is why it is a read-only projection rather than a second, mutable copy.

**Existing production consumers — inventory and compatibility.** Reads of
`supervisor.process` found in production code of the four affected trees (test
files and fake supervisor classes excluded). Several are **not** diagnostic: they
feed authority, dispatch or ownership/cleanup decisions.

| Consumer | Read | Decision it feeds | Compatible because |
|---|---|---|---|
| Semantic adapter P8 (`qualification/semantic_live_adapters.py`) | `supervisor.process is None or supervisor.process.poll() is not None` | Refuses or allows the **one** semantic prompt write — a dispatch authorization gate | It can only see `None` or the genuine child, and `poll()` is on the genuine child, so its outcome reflects the genuine child's state alone; nothing can substitute it |
| Qualification adapter partial-launch handling (`qualification/i2b_live_adapters.py`) | `if supervisor.process is None: raise` / else retain and close the partial runtime | Whether an existing child is treated as an **AIDO-created partial runtime that needs ownership and cleanup** | `Popen` `OSError` → `None` → re-raise, as shipped; partial install failure → genuine child → retain and close, as shipped; an orphan reads `None`, which is correct because the launching call has already torn it down (and that case needs a concurrent shutdown, unreachable in this single-threaded flow) |
| CFG1 L21 teardown (`pi_harness_cfg1/run_executor.py`) | `getattr(state.supervisor, "process", None) is not None` | Whether `shutdown()` is **called at all** | A forgeable `None` here would leave the genuine child never torn down; read-only closes that. States match the shipped ones (a partial failure → `shutdown()` runs) |
| CFG1 L14 (`pi_harness_cfg1/run_executor.py`) | the same `getattr` | Sets the durable `runtime_created` fact | Same states as shipped |
| AR2-O1 handshake (`o1/handshake.py`) | `supervisor.process is not None` | Whether to fetch `stdout_state()` after a shutdown attempt (a diagnostic gate) | Same states; still non-`None` after `shutdown()`, as shipped |

`run_ar2.py` and `run_o1.py` read nothing. Every consumer above keeps its existing
code and its existing behavior, because the observation is now mechanically
read-only and derived from the genuine binding. The claim "readers of `process` are
not authority consumers" is **withdrawn**: they are not consumers of the
*binding*, but several use the *observation* as an authority-relevant input, and
that is precisely why it is frozen read-only.

**Scope, stated exactly.** The guarantee is that no *supported* path — no public
attribute, property, method argument or launch input — can make a write, poll,
wait, terminate, kill or close land on a resource AIDO did not create for this
supervisor lineage, and that the genuine child cannot be stranded by such a path.
It does not extend to code that rebinds private attributes, calls `__init__` on a
live instance, or patches the *methods* of the genuine `Popen` object it can read
through the compatibility observation: that changes how AIDO's own child behaves,
never which resource is targeted, and it is outside the in-process boundary
exactly as §5.2 and §5.6.1 already state. A caller that acts **directly** on the
genuine child it can observe (for example signals it or closes its stdin) is
acting on the resource AIDO created; that is not a retargeting of any AIDO
operation, and AIDO's operations still target the same child and report what they
observe. Launch inputs (`argv`, `cwd`, `environment`) and `bounds` select what AIDO
creates and how long AIDO waits, never *which existing resource* a write, poll,
wait, signal or close is applied to; they are construction-time values of the
caller that builds the supervisor and are unchanged by this amendment.

**Write-versus-retirement linearization (R2, normative).** The probe write
linearizes at its commit (§5.3 steps 1–3); retirement linearizes at its own
critical section. Both are critical sections of the same serialization, so
**every execution has exactly one total order between them**:

- **Retirement first.** The commit's eligibility check observes `RETIRED` and
  raises. The write state never reaches `WRITE_COMMITTED`, so **zero probe
  bytes are ever written** to Pi's stdin, and the slot is never armed.
- **Write commit first.** The write is authorized. Its bytes may physically
  reach the pipe before or after retirement linearizes; that is permitted
  because the write was ordered first. Retirement then proceeds, and every
  existing fail-closed rule still applies: the slot is `RETIRED` unless
  `CONSUMED`; §5.4 (f) discards any later facts; consumption raises; no facts
  are returned after `RETIRED`.

**No concurrent probe write and stdin close.** After retirement, and before
closing stdin, `shutdown()` waits for the write state to leave
`WRITE_COMMITTED`, so a committed probe write and the stdin close never overlap.
The wait is **bounded** by the existing `shutdown_deadline_seconds`. If the write
is still in flight at that deadline, `shutdown()` does **not** close stdin. It
proceeds to the existing terminate/kill rungs for the **direct child**, which do
not touch the stdin handle, and re-checks the write state within the existing
reap grace after each. If the write is still in flight after the last rung,
`shutdown()` leaves stdin **unclosed** and records that truthfully. If the
write leaves `WRITE_COMMITTED` during those rungs, stdin may then be closed as
usual
(`stdin_closed: False` already exists in the termination record; the claim
scope is unchanged). It never closes stdin concurrently with a committed write.
The stdin it closes and the stdin the probe wrote to are the **same** captured
handle of the runtime-child binding (§5.6.2), so this exclusion is about one
pipe, not two names for it.
In CFG1's single-threaded flow this branch is unreachable: the probe call
returns before L16 ends, and teardown runs later on the same thread. It exists
for adversarial concurrency and is exercised by the W-rows (§11.3a). When the
write state is `WRITE_NONE`, `WRITE_DONE` or `WRITE_FAILED`, the ladder runs
exactly as today.

**Slot lifecycle.**

```text
UNARMED --arm+commit--> ARMED --match, command ok--> RESOLVED --consume--> CONSUMED
                          |                             |
                          |                             '--matching duplicate (no reclassification)--> POISONED
                          |--bad command / exception--> POISONED --consume--> CONSUMED (raise)
                          '--no response by deadline--consume--> CONSUMED (unobserved facts)
 any non-CONSUMED state --retirement / write failure / exception in the call--> RETIRED

 Probe matching runs only in ARMED and RESOLVED (§5.4 (a)).

 Write state (lifecycle serialization only):
 WRITE_NONE --commit (with arm)--> WRITE_COMMITTED --> WRITE_DONE | WRITE_FAILED
```

`CONSUMED` and `RETIRED` are terminal. No transition leaves either.

**Consumption-versus-retirement linearization.** Retirement and consumption
are both critical sections of the lifecycle serialization, with the reader lock
nested inside; resolution (§5.4 (f)) takes the reader lock. For any race
between shutdown and consumption, exactly one of these holds:

- consumption linearizes first → the call returns facts produced while the
  supervisor was `ACTIVE`; shutdown then retires a `CONSUMED` slot (no effect);
- retirement linearizes first → the call raises; no facts are returned; any
  facts the reader computed later are discarded at (f).

There is no third outcome, and in particular no return of facts after the
supervisor is `RETIRED`.

**No outstanding authority.** Because arm, write, wait and consume live in one
call, and the return value is plain scalars that no API accepts back, there is
no "minted but unredeemed" or "consumed but unredeemed" object at any point.
Authority is not a thing a caller can hold; it is the call itself, gated by
`ACTIVE`, one-shot, on the run's own supervisor. Object identity is not the
security boundary; the supervisor's own `ACTIVE`/`RETIRED` state, checked
under its lock, is.

**CFG1 side.** L16 invokes the probe on `state.supervisor`, requires the
return to be exactly one `bool` and three `str` members of their closed enums
(`type(x) is bool` / `type(x) is str` and membership), and writes them. A probe
that raises, or a return that fails the type check, → the **existing**
refusal `RUNTIME_CORRELATION_FAILED` at `L16`. Teardown (L21+) shuts the
supervisor down, which retires it; nothing CFG1 retained afterwards is
authority-bearing.

### 5.7 What the provenance proves, and what it does not

It proves: all four facts were derived from the one response, framed on this
supervisor's own stdout reader while the supervisor was `ACTIVE`, that echoed
an id AIDO minted for a `get_state` AIDO authored, and that H2 and §8.2 used
that same response before any other code could reach it.

It does **not** prove Pi's claim is true. Anything controlling Pi's stdout can
read the id from stdin and answer with any value. The facts stay in the
`runtime_reported_*` namespace (and H2 stays a verdict over a runtime claim).
The mechanism closes *AIDO-side* confusion — wrong record, wrong run, wrong
supervisor, unsolicited, stale, duplicated, or post-hoc-mutated data — not
runtime honesty.

---

## 6. Reasoning-content containment invariants

### 6.1 Invariants that remain true (unchanged)

- I-1. Every published record is `ingest_record(decoded)`; `ingest_record`,
  `drop_reasoning`, `REASONING_KEYS`, `REASONING_DELTA_TYPES`,
  `REASONING_BLOCK_TYPES` and `contains_reasoning` are **unchanged**.
- I-2. No sanitized record, sanitized event list, `activity.responses` entry,
  run record, refusal record, stage-closure record, stderr capture or
  diagnostic contains any `REASONING_KEYS` key or reasoning block. The published
  `get_state` response still has **no** `data.model.reasoning` key.
- I-3. Thinking deltas are still replaced by the fixed marker; reasoning blocks
  are still dropped.
- I-4. `scrub_check` and every CFG1 scrub/backstop still runs and still fails
  closed on `reasoning_content_present`.
- I-5. With no probe in flight (every AR2, O1 and qualification caller, and
  CFG1 except inside the L16 call), the reader's published output and
  `ReasoningDropStats` are byte-for-byte / count-for-count identical to today.

### 6.2 Invariants on the probe

- I-6. The raw value at `data.model.reasoning` is subjected to **exactly** the
  two identity tests `is True` / `is False`, preceded by the key-membership test
  `"reasoning" in model`. Nothing else touches it.
- I-7. **Forbidden** on the raw value, the raw model subtree, or the decoded
  record anywhere in the probe path: `str()`, `repr()`, `format`/f-string, `%`,
  `json.dumps` or any serialization, `hash()`/hashlib, `len()`, slicing,
  `startswith`/`endswith`, `==`/`!=` on the value, `bool()`/truthiness,
  retaining `type(value)` or its name, logging, exception text containing it,
  copying it or its subtree, storing a reference to it, and in-place redaction.
- I-8. The slot and the probe's return value hold **only immutable scalars**:
  slot = the minted id, the two bound expectations, a state literal, and (once
  resolved) one `bool` and three `str`; return = one `bool` and three `str`.
  Neither ever holds a reference to the decoded record, the sanitized record,
  `data`, `model`, a response, or any container.
- I-9. **No sanitized state tree crosses the authority boundary.** The
  sanitized record is published to the existing stores exactly as today, and
  nothing else: no copy is made for the probe, and the probe returns none.
- I-10. The response id is not returned. The minted id lives only in the
  supervisor-private slot and in the (pre-existing) `activity.responses` key.

Honest scope of I-8: "not retained by an AIDO-reachable reference". Python
does not guarantee freed memory is erased, and nothing here claims it.

### 6.3 Statistics stay truthful

The probe does not touch `ReasoningDropStats`. The `get_state` response's
`reasoning` key is still dropped by `drop_reasoning` and still increments
`reasoning_keys_dropped`, exactly as it does today with or without the probe.
The statistic counts **keys dropped by name**; it never claimed every dropped
key was model-generated content, and it is not re-described now. No
"capability keys" exemption or sub-counter is added.

---

## 7. Adversarial analysis

### 7.1 Threats and dispositions

| Threat | Disposition |
|---|---|
| Who creates correlation authority | Only the supervisor, inside the one probe call (§5.3). No constructor, setter or parameter accepts an id or type. |
| Who may mutate it | Only the supervisor and its own reader, under the reader lock. The slot holds only immutable scalars. |
| Caller registers an invented id/type pair | No API accepts either. A caller's own `send_command({"type":"get_state","id":X})` never matches the slot. |
| Duplicate response ids | Matching runs only in `ARMED` and `RESOLVED` (§5.4 (a)). `ARMED` + match: the one classification path. `RESOLVED` + match: `POISONED` immediately, no reclassification, stored facts discarded → consumption raises → `RUNTIME_CORRELATION_FAILED`. `UNARMED`/`POISONED`/`CONSUMED`/`RETIRED`: no matching at all; after consumption nothing can change the returned scalars. |
| Response before registration | Arming precedes the write (§5.3 steps 3–4); the id is fresh CSPRNG output Pi can learn only from that write. |
| Stale response from a prior runtime | Each launch has its own reader and slot; a prior process's stdout is a different pipe. |
| Two supervisors with the same textual id | Each reader matches only its own slot. CFG1 calls the probe only on `state.supervisor`; nothing accepts another supervisor's result. The id text is never a security boundary. |
| Command id reuse | One probe per supervisor lifetime; ids never come from callers; the minted id is refused if already present. |
| Malformed id / type | Non-`str` / non-`"response"` `type`, non-`str` `id`: no match. Wrong/missing/non-`str` `command` on a matching id: `POISONED`. |
| `True` vs `1`; `False` vs `0` | Identity tests only; `1`, `0`, `1.0`, `0.0` → `OTHER`. `==` is forbidden because `1 == True` in Python. |
| `null` / missing | `null` → `OTHER`; key absent → `OTHER`; no correlated response → `NOT_OBSERVED` (§8). |
| `"true"`, list, dict, object values | `OTHER`, nothing about the value retained. |
| Post-validation mutation | All facts are reduced to immutable scalars **before** the sanitized record is published (§5.5 step 3). The raw and sanitized objects are reader-local until then. No frozen wrapper around a mutable container is relied on anywhere. |
| H2 and §8.2 from different snapshots | Impossible: one reader iteration, one local object, no reference held by any other thread (§5.5). |
| Repeated consumption / redemption | There is no separate redemption; the probe call is one-shot; a second call raises. |
| Minted/resolved but unconsumed authority surviving | Impossible: arm→consume is one call; its `finally` leaves the slot `CONSUMED` or `RETIRED`. |
| Shutdown racing the probe's **write** | Write commit and retirement are totally ordered in one serialization (§5.6). Retirement first → zero probe bytes. Commit first → the write may complete, and every consumption rule still fails closed. A pre-write `ACTIVE` check on its own is forbidden. |
| stdin close racing a committed probe write | `shutdown()` does not close stdin while the write state is `WRITE_COMMITTED`; the wait is bounded; if the write never finishes, stdin is left unclosed and recorded as such (§5.6). |
| Deadlock via the write | Neither lock is held across the write; the reader never takes the lifecycle serialization; the lock order is fixed (§5.6). |
| Shutdown racing consumption | Both are critical sections of the same serialization (§5.6); never facts after `RETIRED`. |
| Repeated shutdown | Idempotent, monotonic retirement. |
| Caller retains returned facts past teardown | They are plain scalars no API accepts; a new run's L16 obtains facts only from its own supervisor's probe. |
| Classifier or H2 exception leaking a value | Contained to `POISONED` with a fixed reason; never formatted; never reaches `read_error`. |
| Byte cap / record cap / protocol violation | Over-cap bytes are never framed, so never classified. A violation before resolution leaves the slot `ARMED` → unobserved facts → `H2_MISMATCH`. A violation after resolution does not un-resolve facts taken from a validly framed earlier record. |
| stdin write fails after arming (alone or concurrently with shutdown) | Write state `WRITE_FAILED`, slot `RETIRED`, raise; a waiting `shutdown()` is released; a late answer gains nothing. |
| Duplicate JSON keys inside the frame | `json.loads` keeps the last. Pi's `JSON.stringify` cannot emit duplicates; an adversarial runtime could, but can equally report any value — inside §5.7's runtime-claim residual. AR2 framing is not changed. |
| Unsolicited responses, including ones carrying `reasoning` | No match → no observation; sanitized as today. |
| Other `reasoning` keys at other paths | Not classified; dropped as today. |
| Shape-only inference | Classification runs only on the one id-matched, command-validated record; the published record never contains the key. |
| Caller supplies a hand-typed `"TRUE"` | The L16 function has no input for facts; it calls the probe itself. |
| Expectation tampering | The *binding* is immutable through the supported API: no public assignable name, setter, mutator or reconfiguration path; the slot holds its own copy from arm time (§5.2, R-39). Provenance: the same frozen constants feed argv and the expectations (R-40). They cannot select a path or record. |
| Reader self-deadlock at (f) | The lock-acquiring `_publish()` is never called while the reader lock is held; publication is refactored to a locked helper (§5.4 (f), R-38). |
| Repeated `launch()` replaces the lineage | Launch authority is single-use (§5.6.1 L1): the second call refuses **before** `Popen`, so `process`, both readers, the slot binding, the probe slot and the expectation copy cannot be replaced or duplicated. |
| Concurrent `launch()` calls | L1 is a lifecycle-serialization section; exactly one passes; at most one child and one reader lineage. |
| Launch after a failed launch | FAILED is terminal; L1 refuses before `Popen`, including when the failure happened after a child was created (that child stays with `shutdown()`). |
| Launch after retirement / on a never-launched-then-retired supervisor | Retirement is lifecycle RETIRED whatever the launch authority; L1 refuses before `Popen`. |
| Launch racing retirement | Total order in one serialization: retirement first → zero child; L1 then L3 first → one lineage, retired and torn down by `shutdown()`; L1 first then retirement before L3 → **orphan** child, attributed, never installed, torn down by the launching call, no reader ever created (§5.6.1). Never a new `ACTIVE` lineage on a retired supervisor. |
| Reset of launch or lifecycle state | Both fields are monotonic and written only by the enumerated sections; no supported path writes `UNUSED` or `OPEN` (§5.6.1). |
| Launch state shared across instances | Forbidden: the guard is per-instance; a fresh supervisor per run is a fresh lineage. |
| Caller assigns another process-like object to the public `process` after launch | Assignment and deletion **refuse** (§5.6.2 contract 5–6). Independently, the supervisor consumes no public name: probe write, `send_command`, `_wait` polling, the shutdown ladder and reader construction use the private runtime-child binding, so the substitute would receive no byte, no `poll` and no terminate/kill even if it could be stored. |
| Caller retargets what an external `process` reader observes (P8 dispatch gate, partial-launch ownership test, CFG1 L21 teardown gate, L14 `runtime_created`, O1 diagnostic gate) | The observation is read-only and derived on each read from the private runtime-child binding; it can only be `None` (no binding, orphan) or the genuine child; nothing supported can change which object that is (§5.6.2 contract 1–9; C-13, C-14, C-15). A forged `None` at L21 — which would skip `shutdown()` and strand the genuine child — is impossible. |
| Caller assigns to the exposed genuine child's `.stdin` / `.stdout` / `.stderr` | Writes and closes use the pipes **captured** at bind time, so the assignment retargets nothing (§5.6.2). |
| Caller aims the orphan path at a substitute | The orphan child lives only in the private orphan-child binding, is never exposed through `process`, and teardown consumes only that binding, verified against the L2 return value (§5.6.2). |
| Installed and orphan roles confused; a binding from another supervisor | Each consumption verifies role, owning supervisor and mutual exclusion and fails closed (§5.6.2). No API accepts a binding. |
| Retirement retargets or rebinds authority | Retirement changes no binding; it invalidates only the probe's operation authority (§5.6.2 invariant 6). |
| Repeated or refused `launch()` rebinds ownership | L1 refuses before any binding step (§5.6.1), and bindings are write-once. |

### 7.2 Pre-existing defects found during this analysis (scoped)

- F-1. `RuntimeActivity.responses[id] = record` is **last-write-wins** on a
  duplicate id, and `await_response` does not register sent ids. The probe does
  not use `activity.responses` at all, so L16 is closed. H1's `get_commands`
  path keeps the behavior; out of scope, recorded, not claimed closed.
- F-2. `RecordStreamReader._run` formats any exception into `read_error`; this
  is why §5.4's exception containment is mandatory.
- F-3. AR2's suite has no direct regression for `ingest_record` /
  `drop_reasoning` / thinking-delta replacement; these become required (R-09).
- F-5 (new, R2). The **generic** `send_command` (used by H1 and L18's prompt)
  is not serialized against `shutdown()`. CFG1 calls both on one thread, so the
  race is unreachable there. The probe's write is closed by §5.6; the generic
  path is out of scope, recorded, and not claimed closed.
- F-6 (new, R2 final correction). The shipped `PiRpcSupervisor.launch()` has **no
  one-shot guard**: repeated calls create a new child and readers and overwrite
  `process`, `_stdout` and `_stderr`, stranding the first child. Closed by
  §5.6.1. A residual disclosure comes with it (§15): in the adversarial
  launch-races-retirement case, `shutdown()`'s own returned record says nothing
  about an orphan child that the launching call tears down afterwards.
- F-8 (new, R2 resource-authority correction). In the shipped supervisor the
  public, assignable `process` is the target of every stdin write, liveness poll,
  reader-pipe hand-off and shutdown action, so a supported caller could steer them
  at an object AIDO did not create and strand the real child; the child's own
  `.stdin`/`.stdout`/`.stderr` were likewise re-read from a rebindable attribute
  at each use. Closed by §5.6.2 (R-AR2-6). It was not reachable in CFG1's flow,
  which never assigns `process`; the design closes it mechanically rather than by
  convention. The same mutable attribute was also an input to production
  decisions (semantic P8, partial-launch ownership, CFG1 L14/L21), so leaving it
  mutable — even ignored by the supervisor — would have left those decisions
  forgeable; §5.6.2 therefore freezes it read-only.
- F-7 (new, R2 final correction; recorded, **not** closed, not caused by this
  amendment). The shipped `shutdown()` calls `_drain()`, which asserts the stdout
  reader exists, *after* the ladder. On a partial launch failure that left
  `process` set but no stdout reader, the ladder still runs (the child is torn
  down) and the assertion then raises. R2's retirement step is prepended and
  changes neither behavior.
- F-4 (new, R1). Pi 0.85.1's `get_state` `data` also carries `sessionFile`,
  `sessionId` and the composed model's `baseUrl` (§16). R0's design would have
  carried these across the authority boundary inside the state copy. R1 carries
  none of them. Their pre-existing in-memory presence in `activity.responses`
  is unchanged and is not persisted by CFG1.

---

## 8. Malformed-input and closed-literal table (normative)

`h2` = `h2_provider_model_identity_matched`; `R`/`C`/`T` = reasoning / compat
shape / thinking level.

| Condition | `h2` | `R` | `C` | `T` | L16 outcome |
|---|---|---|---|---|---|
| Correlated, `command == "get_state"`, `success is True`, `data` dict, `data.model` dict with `reasoning is True`, provider/model match | `True` | `TRUE` | §8.2 classification | §8.2 classification | proceeds iff `C`/`T` also agree |
| … `reasoning is False` | per H2 | `FALSE` | §8.2 | §8.2 | `CONFIG_SHAPE_MISMATCH` (if H2 true) |
| … `reasoning` present, any other value/type (`1`, `0`, `"true"`, `null`, list, dict, float) | per H2 | `OTHER` | §8.2 | §8.2 | `CONFIG_SHAPE_MISMATCH` |
| … `model` dict without `reasoning` | per H2 | `OTHER` | §8.2 | §8.2 | `CONFIG_SHAPE_MISMATCH` |
| `success is True`, `data` dict, `data.model` not a dict | `False` | `OTHER` | `OTHER` | §8.2 | `H2_MISMATCH` |
| `success is True`, `data` not a dict | `False` | `NOT_OBSERVED` | `NOT_OBSERVED` | `NOT_OBSERVED` | `H2_MISMATCH` |
| Correlated, `success` not exactly `True` | `False` | `NOT_OBSERVED` | `NOT_OBSERVED` | `NOT_OBSERVED` | `H2_MISMATCH` |
| No correlated response (deadline, exit, stream terminal) | `False` | `NOT_OBSERVED` | `NOT_OBSERVED` | `NOT_OBSERVED` | `H2_MISMATCH` |
| Correlated id, `command` missing / non-`str` / ≠ `"get_state"` | — (`POISONED`, raise) | | | | `RUNTIME_CORRELATION_FAILED` |
| Duplicate correlated response before consumption | — (raise) | | | | `RUNTIME_CORRELATION_FAILED` |
| Classifier / H2 exception | — (raise) | | | | `RUNTIME_CORRELATION_FAILED` |
| Probe ineligible (second call, before launch, after shutdown began, no bound expectations), write failure, retirement race lost | — (raise) | | | | `RUNTIME_CORRELATION_FAILED` |
| Return fails CFG1's exact-type/enum check | — | | | | `RUNTIME_CORRELATION_FAILED` |

"§8.2 classification" means the frozen mapping, verbatim, applied to the
sanitized `data`: compat — no `compat` key → `ABSENT`; exactly
`{supportsDeveloperRole: false}` → `DEVELOPER_ROLE_FALSE_ONLY`; exactly
`{supportsReasoningEffort: false}` → `REASONING_EFFORT_FALSE_ONLY`; both →
`BOTH_FALSE_ONLY`; anything else (other keys, any value not exact `false`,
non-object) → `OTHER`. Thinking level — key absent → `NOT_OBSERVED`; one of
`off|minimal|low|medium|high|xhigh|max` → itself; anything else → `OTHER`.

The H2-first ordering and the `H2_MISMATCH` / `CONFIG_SHAPE_MISMATCH` precedence
at L16 are **unchanged**. The two rows with `data` not a dict or `success` not
`True` are the only places the table differs from the v1 code path, and only
because v1's port substituted `{}` for a missing `data` (yielding `OTHER`
rather than `NOT_OBSERVED`); H2 fails first in both, so no L16 outcome changes.
"Key absent → `OTHER`" preserves the frozen §8.2 mapping; what changes is that
absence is judged on Pi's **raw** report.

### Schema decision

The durable enums are **kept unchanged** — `TRUE | FALSE | OTHER | NOT_OBSERVED`
for reasoning, and the frozen compat and thinking-level domains. They represent
the corrected observation truthfully: §8.2 always *specified* Pi's reported
value; v1's defect was an instrument that failed its own specification. No field
is added, `RUN_RECORD_VERSION` (`pi-harness-cfg1-run.v1`) is not bumped, no
refusal code is added, and the manipulation predicate is unchanged. Artifacts
produced under the defective instrument are uniquely identified by their
never-reused `stage_execution_id` and are scoped explicitly in §13.

---

## 9. Contracts reopened (exactly)

### 9.1 AR2 (`experiments/pi_external_runtime_ar2/ar2/`)

- R-AR2-1. **AR0 §13.3 as inherited by AR2, and the `protocol.py` /
  `RecordStreamReader` sentence "dropped at ingestion, before any record is
  stored, counted, hashed, or written"** — narrowed by exactly one exception:
  *for the single record matching an armed probe slot, the value at
  `data.model.reasoning` is subjected to the two identity tests of §5.4 (c)
  before the drop; only the resulting closed literal is retained.* No other key,
  path, record or operation is excepted. "No reasoning-bearing value is ever
  stored by this process" remains true verbatim.
- R-AR2-2. **`RecordStreamReader` per-record pipeline** gains §5.4 (a)–(c)
  before `ingest_record` and (e)–(f) between `ingest_record` and publication,
  for the matched record only. No public hook, parameter or callback is added.
  The internal publication path may be refactored so that (f) can publish while
  holding the reader lock (§5.4 (f)); no `RLock` is required.
- R-AR2-3. **`PiRpcSupervisor`** gains: the optional construction-time
  expectations (§5.2); the single parameterless probe call (§5.3); the
  `ACTIVE`/`RETIRED` lifecycle with retirement as `shutdown()`'s first step
  (§5.6); the lifecycle serialization and write state; **the single-use,
  per-instance launch-authority guard of §5.6.1 — the one explicit reopening of
  `launch()`'s semantics (a second call on one instance now refuses before any
  process, reader or thread is created; a launch that loses to retirement never
  installs; `launch()` stays parameterless with unchanged `Popen` arguments,
  environment, pipes and reader parameters)**; and, **only while a
  committed probe write is still in flight**, the bounded wait before stdin
  close plus the permission to skip the stdin close and proceed directly to the
  existing direct-child terminate/kill rungs (§5.6). In every other case
  `shutdown()`'s ladder is unchanged, and its claim scope is unchanged in every
  case.
- R-AR2-4. **Placement of the §8.2 compat and thinking-level classifiers**: they
  must be reachable from the reader's step (e) as statically bound code with a
  single definition; CFG1's existing definitions are moved or re-exported.
  Mapping unchanged.
- R-AR2-5. AR2 test surface (§11).
- R-AR2-6. **Child-resource ownership (§5.6.2) — an explicit reopening of which
  attribute is authoritative.** Today the public, assignable `process` is the
  authoritative target of every child operation. It is **no longer operational
  authority for anything** (it remains only a read-only observation, below). The following shipped consumption paths are reopened **only in
  how they derive their target** (each still does exactly what it does today,
  with unchanged errors, bounds, rungs and claim scope) and now consume the
  AIDO-private runtime-child ownership binding:
  `send_command`'s stdin write and flush; `_wait`'s `poll()`; `shutdown()`'s
  stdin close, `wait`, `terminate` and `kill`; and `launch()`'s construction of
  the two readers (now from the pipes captured in that binding). The
  orphan-child path (§5.6.1) is new and consumes only the orphan-child binding.
  **The public `process` is reopened in its mutability, and only in that:** it
  becomes a **read-only observation derived exclusively from the genuine
  runtime-child binding** — never a caller-mutable attribute, with no alternative
  shape — that reads `None` before the binding, the genuine child afterwards
  (including after a partial install failure and after retirement) and `None` for
  an orphan, and whose assignment and deletion refuse (§5.6.2 contract). This is
  a shipped behavior change: assigning to `supervisor.process` on a real
  `PiRpcSupervisor`, which succeeded before, now refuses, and `__init__` no
  longer assigns it. No production code and no test on a real supervisor assigns
  it (verified: the only assignments in the four affected trees are to
  hand-written fake supervisor classes in tests, which keep their own attribute and
  are **not** required to adopt the property).
  **Existing readers are not otherwise changed, but they are not categorically
  "non-authority" readers.** The production readers — semantic P8 (the dispatch
  gate for the one prompt write), the qualification adapter's partial-launch
  ownership test, CFG1 L21 (whether `shutdown()` is called) and L14
  (`runtime_created`), and AR2-O1's diagnostic gate — use the observation as an
  input to authority, dispatch or ownership/cleanup decisions. They remain
  compatible unchanged because the observation is now mechanically read-only and
  derived from the genuine binding (inventory in §5.6.2; C-13, C-14, C-15).

### 9.2 CFG1 (`experiments/pi_harness_cfg1/` and the frozen design)

- R-CFG1-1. **§8.2 source of all three projections and of H2's verdict at L16**:
  from "project the `get_state` document" to "the four scalars returned by the
  AR2 probe". Domains, mappings, predicate unchanged.
- R-CFG1-2. **§16.2 L16 step and the `Cfg1RunPorts` inventory**: the
  `evaluate_model_identity` port is removed. L16 calls the probe directly on
  `state.supervisor` (built by the existing `build_supervisor` port, which now
  passes the bound expectations), type-checks, and writes. The run-executor
  docstring's "the raw `get_state` document" wording is removed.
- R-CFG1-3. **`project_get_state`** is replaced by the L16 function of §5.6
  (no state-document, facts, or literal parameter). Probe raise or type-check
  failure → existing `RUNTIME_CORRELATION_FAILED` at `L16`.
- R-CFG1-4. **§11.3 T-3's claimed scope** and the two T-3 tests whose wording
  overclaims (§11.6); new receive-boundary regressions (§11).

---

## 10. Contracts still frozen

Explicitly **not** reopened:

- `REASONING_KEYS`, `REASONING_DELTA_TYPES`, `REASONING_BLOCK_TYPES`,
  `drop_reasoning`, `ingest_record`, `contains_reasoning`, `ReasoningDropStats`
  (fields and semantics), `scrub_check`, `refusal_record`,
  `broker_secret_denylist`, `redact_value`.
- `decode_record`, `split_records`, LF framing, the byte/record caps, and
  `BoundedStreamReader`.
- `send_command`, `await_response`, `await_settled`, `shutdown()`'s ladder
  rungs and claim scope (only a retirement step is prepended, plus R-AR2-3's
  in-flight-probe-write branch), the reader's observable publication semantics, `RunBounds`
  values, `RuntimeActivity` fields and `_absorb` — **except** that the four
  consumption paths named in R-AR2-6 now derive their *target* from the
  ownership binding rather than the public `process`; their behavior, errors,
  bounds and claim scope are otherwise frozen. `launch()`'s `Popen` argv,
  `shell=False`, environment, cwd, pipes, creation flags, reader parameters and
  `RUNTIME_LAUNCH_FAILED` behavior are frozen; **only** §5.6.1's one-shot
  guard and install/orphan atomicity and §5.6.2's ownership binding are added
  (R-AR2-3, R-AR2-6). The public `process` keeps its name and its read
  semantics for every existing reader and changes in exactly one respect —
  it is read-only (§5.6.2 contract).
- The broker, `wire.py`'s closed two-operation protocol, capability, manifest,
  launch, environment, extension.
- `ar2.handshakes.evaluate_model_identity` and `evaluate_extension_identity`
  (both called unchanged).
- CFG1: arms, `ARM_SHAPE`, `EXPECTED_THINKING_LEVEL`, the compat-shape and
  thinking-level **mappings and domains**, `manipulation_check_agrees`'
  predicate, the L0–L30 order, H1, H2's pass condition, L16 refusal precedence,
  the closed refusal vocabulary, every record schema and validator (including
  `MANIPULATION_CHECK_DISAGREES_WITH_PROJECTION` and
  `DISPATCH_WITHOUT_AGREEING_MANIPULATION_CHECK`), `RUN_RECORD_VERSION`,
  stage-output authority, halt semantics, schedule, model, route, Pi version
  0.85.1, `PINNED_PI_SEAM_DIGESTS`, and every T-row not named in §9.2.
- The generated `models.json` (`"reasoning": true` stays; it is the declared
  configuration §8.2 checks).
- A1 and A2 authorization documents and their artifacts.
- Everything in `CLAUDE.md`, including the 5F2E-V2 rule that the reviewer never
  reads `message.reasoning` — unrelated to, and untouched by, this amendment.

---

## 11. Required adversarial regression matrix

All tests are offline. None launches Pi, contacts B300, reads a credential or
endpoint, or opens a socket to anything but a local synthetic peer.
Receive-path rows drive the **real** `PiRpcSupervisor` + `RecordStreamReader` +
`ingest_record` over a real pipe to a synthetic peer — a synthetic Python child
script written under `tmp_path`, launched with a pinned absolute argv, that
reads the probe command from stdin and writes scripted JSONL frames echoing (or
deliberately not echoing) its id. They must never substitute a hand-built dict
for the wire.

Test-only instrumentation (monkeypatching the reader's publish step, a
test-side decoder wrapper, a threading barrier, **a counting wrapper around
child-process creation and reader/thread construction**) is permitted **in tests
only** and must never become a production parameter. The §11.3b launch rows use
a synthetic child script under `tmp_path` (or a counting wrapper that delegates
to one); no real Pi, model, network or credential is involved.

**Oracle rule.** No row's oracle may inspect a state copy inside the returned
facts, because none exists. Rows assert on the four returned scalars, on the
published sanitized stream, on the supervisor/slot lifecycle, and on the absence
of sentinel values.

**Leak check** = serialize the published sanitized events, `activity.responses`,
the returned facts, the slot's fields after the call, `read_error`,
`protocol_violation`, captured logs and any emitted record; assert no injected
sentinel appears, and `contains_reasoning(...) is False` on each structured
object.

### 11.1 Minimum rows required by the phase prompt

| ID | Scenario | Required result |
|---|---|---|
| R-01 | Correlated `get_state`, raw `"reasoning": true`, correct provider/model, compat absent, `thinkingLevel: "medium"` | returns `(True, "TRUE", "ABSENT", "medium")` |
| R-02 | Same | the **published** sanitized record has no `data.model.reasoning` key; the returned facts contain no container |
| R-03 | Same | `contains_reasoning` false on every published record; `reasoning_keys_dropped` incremented by exactly the number of `REASONING_KEYS` keys in the frame |
| R-04 | Raw `false` | `R == "FALSE"` |
| R-05 | Raw `"true"`, `"x-sentinel-…"`, `{"k":"sentinel"}`, `["sentinel"]`, `null`, `1`, `0`, `1.0`, `0.0` (parametrized) | `R == "OTHER"` each; leak check clean |
| R-06 | Unrelated responses (other ids, `get_commands`, `prompt`) with `reasoning: true` at `data.model` and elsewhere, interleaved before and after the correlated one | facts come only from the correlated record; unrelated records sanitized as today |
| R-07a | Only a wrong-id response arrives | unobserved facts `(False, NOT_OBSERVED ×3)` at deadline |
| R-07b | A frame carrying an id from an earlier supervisor instance / earlier run | no effect on this supervisor's facts |
| R-07c | Caller `send_command({"type":"get_state","id":X})` and its response | no effect on the probe; the probe still requires its own id |
| R-08 | Two real supervisors A and B over two peers; B's peer reports `TRUE`, A's reports `FALSE`; run L16 for a run whose `state.supervisor` is A | L16 records `FALSE`; there is no parameter or path by which B's facts enter A's L16 (asserted by signature introspection, R-35) |
| R-09 | Existing reasoning stripping: thinking deltas → marker; `reasoning_content`, `thinking_blocks`, `reasoningDetails`, etc. at depth → dropped; reasoning blocks → dropped | unchanged results and counts, with no probe in flight **and** with a probe in flight on the same stream |
| R-10 | Full L16 through `run_executor` with the real supervisor over the synthetic peer, arm Q, raw `true`, compat absent, `medium` | `manipulation_check_agrees is True`, L16 passes, record validator accepts, `runtime_reported_model_reasoning == "TRUE"`, no `reasoning` key anywhere in the emitted record |

### 11.2 Same-response and mutation rows (Finding 2)

| ID | Scenario | Required result |
|---|---|---|
| R-11 | Test-side wrapper around the reader's publish step: upon receiving the correlated sanitized record, it mutates it (`data.model.id` → wrong, `data.model.provider` → wrong, `data.thinkingLevel` → `"off"`, `data.model.compat` → `{"x": 1}`, delete `data.model`) before letting publication continue | returned facts equal those of the unmutated frame (proves reduction happened **before** publication) |
| R-12 | Same wrapper also asserts, at the moment it is called for the correlated record, that the slot is already `RESOLVED` with scalar facts | holds |
| R-13 | After the probe returns: mutate `activity.responses[<id>]`, every dict/list in `sanitized_events()`, and attempt attribute/item assignment on the returned facts | returned facts unchanged; assignment to the facts raises or is impossible (tuple / scalars) |
| R-14 | Duplicate-match semantics, parametrized: (i) two frames with the probe id, the first passing H2 and the second failing it, and vice versa; (ii) the second frame carries a different `command` or malformed `data`; (iii) a third frame with the same id after poisoning. Test-side instrumentation records the slot state before and after each frame and counts calls to the raw classifier and to the H2/§8.2 reduction | (i)/(ii): the first frame takes `ARMED → RESOLVED` with exactly one classification and one reduction; the second takes `RESOLVED → POISONED` with **zero** further classifier/reduction calls and discards the stored facts; the probe raises → `RUNTIME_CORRELATION_FAILED`; never "H2 from one, §8.2 from the other". (iii): no matching in `POISONED`, no state change. Every frame is still sanitized and published normally |
| R-15 | A matching-id frame arriving after the probe returned (`CONSUMED`), after `RETIRED`, and while `UNARMED` (the id forced by test-side instrumentation only) | no matching in `UNARMED`/`CONSUMED`/`RETIRED`; zero classifier calls; returned facts unchanged; slot state unchanged |
| R-16 | Returned-facts contents: `len == 4`; field types exactly `(bool, str, str, str)`; no field `is` or contains a `dict`/`list`/`set`/`bytes`/mapping; the minted id, `"data"`, `"model"`, the synthetic base URL, the synthetic `sessionFile`, `"baseUrl"`, and the raw capability value (sentinel) appear nowhere in `repr` of the result or in the slot after the call | holds |
| R-17 | Slot fields after resolution and after the call: every field is `str`, `bool` or `None`; no reference to any record/`dict`/`list` (checked via `gc.get_referents` on the slot) | holds |

### 11.3 Lifecycle and retirement rows (Finding 3)

| ID | Scenario | Required result |
|---|---|---|
| L-01 | **Resolved, then shutdown before consumption**: a barrier holds the probe call between resolution and step 6; another thread calls `shutdown()` | the call raises; no facts returned; slot `RETIRED` |
| L-02 | **Consumed, then shutdown before "redemption"**: the call returns; `shutdown()`; then any attempt to use the probe or re-obtain facts | there is no redemption API (introspection: no method accepting facts/observations exists on the supervisor or in CFG1's L16 path); a second probe call raises |
| L-03 | **Shutdown racing consumption**: many iterations with a barrier releasing `shutdown()` and step 6 concurrently | every iteration is exactly one of {facts returned and slot `CONSUMED` before retirement; raise with no facts}; never facts returned after the supervisor is `RETIRED` (asserted via a lock-ordered sequence counter captured in the test) |
| L-04 | **Repeated shutdown** | idempotent; supervisor and slot stay `RETIRED`/`CONSUMED`; the probe still refuses |
| L-05 | **Repeated redemption/consumption**: call the probe twice | second call raises; no second `get_state` is written (peer records one command) |
| L-06 | **Genuine result from another supervisor** | as R-08; plus: CFG1's L16 function refuses to run against a supervisor object other than the one stored at L14 in the run state (identity of the run-state field, not id text), and a supervisor that has never launched or is `RETIRED` is refused |
| L-07 | **Result retained by a caller past stage teardown**: complete a run through teardown, keep the returned facts `TRUE`; start a new run whose peer reports `false` | new run records `FALSE`; the old result has no input path; the old supervisor's probe refuses |
| L-08 | Probe before `launch()`; after a failed `launch()`; with no bound expectations | raises; nothing written |
| L-09 | stdin write failure after arming (peer closes stdin) | slot `RETIRED`, raise; a later matching frame yields nothing |
| L-10 | Exception inside the call after arming (test-injected in the wait) | `finally` leaves the slot `RETIRED`; subsequent probe raises |
| L-11 | Retirement races resolution: shutdown linearizes before §5.4 (f) | facts discarded at (f); slot stays `RETIRED`; the sanitized record is still published as today |

### 11.3a Write-versus-retirement rows (R2)

Every W-row uses a synthetic peer that records **every byte it receives on
stdin**. Test-side instrumentation (barriers and a shared monotonic sequence
counter advanced at each observed linearization point) is used in tests only.
The oracle is twofold: **(1)** whether facts are returned, and **(2)** exactly
which probe bytes reached stdin relative to retirement. The peer's stdin
capture is authoritative for (2). Where a row's outcome is "retirement first",
it asserts that **zero** bytes of the probe frame, and zero `get_state` frames
at all, were received.

| ID | Scenario | Required result |
|---|---|---|
| W-01 | **Retirement after arm but before write**: barriers try to place retirement between the probe's arm and its write; `shutdown()` completes retirement; the probe is released | only two linearizations are observable: retirement before commit → the probe raises, the slot is never armed or is `RETIRED`, **zero probe bytes**; or commit before retirement → as W-03. No iteration shows retirement completed and probe bytes written afterwards by a probe that had not committed. A test-only "check-then-write" variant (eligibility checked outside the serialization) must fail this row, proving the row detects the defect |
| W-02 | **Shutdown racing the actual write**: many iterations releasing `shutdown()` and the probe from one barrier | each iteration is exactly W-03 or W-04; never probe bytes after a retirement that linearized first; never a stdin close overlapping a committed write (the peer sees either the complete frame then EOF, or EOF with no probe bytes, never a partial frame followed by an AIDO-caused EOF) |
| W-03 | **Write committed before retirement**: a barrier holds the physical write after commit; `shutdown()` runs and retires; the write is released | the complete frame arrives; `shutdown()` did not close stdin until the write state left `WRITE_COMMITTED`; the probe raises (supervisor `RETIRED`), no facts; slot `RETIRED` |
| W-04 | **Retirement committed before write**: `shutdown()` completes retirement, then the probe is called | the probe raises at eligibility; **zero** probe bytes; slot never armed; no probe `get_state` in `commands_sent` |
| W-05 | **Write failure concurrent with shutdown**: the peer closes its stdin read end while a committed write is in flight and `shutdown()` is waiting | write state `WRITE_FAILED`; slot `RETIRED`; the probe raises; `shutdown()` is released from its wait and continues the ladder; no facts |
| W-06 | **Write never finishes**: the peer stops reading stdin with the pipe pre-filled by the test, a committed probe write blocks, and `shutdown()` is called | `shutdown()` returns within `shutdown_deadline_seconds` plus two reap graces plus scheduling slack; stdin is never closed while the write state is `WRITE_COMMITTED`; the direct-child terminate/kill is recorded truthfully; no facts |
| W-07 | **No deadlock via the reader**: the peer floods stdout while a committed probe write is in flight | the reader keeps publishing (record count rises during the write); neither lock is held across the write (instrumented) |
| W-08 | **Lock order**: instrumentation records every acquisition, **including the launch sections of §5.6.1** | the reader thread never acquires the lifecycle serialization, and nothing acquires it while holding the reader lock |

### 11.3b Launch-authority rows (R2 final correction)

Every S-row uses a counting wrapper around child-process creation and around
reader/thread construction (tests only), driving a synthetic child script under
`tmp_path`. The oracle is **counts and object identity**: how many times child
creation was entered, how many stdout/stderr readers and threads exist, and
whether `process`, `_stdout`, `_stderr`, the probe slot and the expectation
binding are the *same objects* as before. "Refuses before creation" means the
creation count did not increase, no reader, thread or pipe appeared, and the
raised error is the fixed-text `PiSupervisorError`. Where a row says "race", it
runs many iterations under barriers whose release order is recorded by a shared
sequence counter advanced at each linearization point.

| ID | Scenario | Required result |
|---|---|---|
| S-01 | `launch()` twice sequentially on one supervisor | the second call refuses before creation; creation count is exactly 1; `process`, `_stdout`, `_stderr` are the identical objects; one child exists |
| S-02 | Successful `launch()` → `shutdown()` → `launch()` | the third step refuses before creation; count stays 1; no new process, reader, thread or pipe; the supervisor is `RETIRED` and its probe refuses |
| S-03 | Failed first launch → second `launch()`, in four variants: (i) child creation raises `OSError`; (ii) creation succeeds and reader construction/start is made to raise (a child exists, bound as the runtime-child, and `process` shows it); (iii) a `BaseException` is injected after L1 and before creation; (iv) a `BaseException` is injected after creation and before L3 | in every variant the second call refuses before creation (count unchanged) and launch authority is `FAILED`, never left `COMMITTED`; (i) and (iii): `process` stays `None`, no child; (ii): the runtime-child binding and `process` stay the same genuine child, the supervisor is never `ACTIVE`, the probe refuses with zero probe bytes, and `shutdown()` tears down that one child exactly as shipped and creates nothing; (iv): the child takes the orphan rule (bound as the orphan-child, no reader or thread, torn down by the launching call through that binding) |
| S-04 | Two concurrent `launch()` calls released from one barrier | exactly one passes L1 (asserted from the sequence counter); the other raises the fixed-text refusal **before** creation; creation count ≤ 1; at most one stdout reader and one stderr reader lineage exists |
| S-05 | Launch racing `shutdown()`, **retirement first**: retirement is ordered before L1; also `shutdown()` on a never-launched supervisor followed by `launch()` | `launch()` refuses; creation count **0**; no reader, thread or pipe ever created; the supervisor is `RETIRED` and can never be launched; probe refuses |
| S-06 | Launch racing `shutdown()`, **launch committed first**, in two orderings: (a) L3 before retirement; (b) retirement between L1 and L3 (a barrier inside the creation wrapper holds the launch after the child exists, `shutdown()` completes retirement and its ladder, then the launch is released) | (a) exactly one lineage: installed, then retired and torn down by `shutdown()`; creation count 1. (b) the child is an **orphan**: bound as the orphan-child before the section releases; **no** reader, thread or slot binding is created; `process` stays `None`; the launching call — not `shutdown()` — signals and reaps it and records `orphan_termination` with the shipped claim scope; the launch raises the fixed-text refusal; the supervisor never becomes `ACTIVE`; the probe refuses with zero probe bytes; the child is not left running (peer observes its exit) |
| S-07 | No reset: exhaustive sequences of length ≤ 4 over {`launch`, `shutdown`, probe, a refused-`launch` repeat}, in every order, with and without an injected creation/install failure; plus a source/AST check that the launch-authority and lifecycle fields are written only by the constructor, L1, the L2 failure section, L3 and retirement | the derived state never moves backward; child creation is entered at most once per sequence; nothing is ever `ACTIVE` after `RETIRED`; no other code path writes `UNUSED` or `OPEN` |
| S-08 | Repeated launch cannot replace lineage: after every refused `launch()` (while `ACTIVE`, after `RETIRED`, after `FAILED`, the concurrent loser) | `process`, `_stdout`, `_stderr`, the reader threads' identities, the probe slot object and its state, and the expectation binding and their provenance (R-39/R-40) are **identical objects with unchanged values** as before the call (where no runtime-child binding was ever established, `process` is unchanged `None`; where one exists, it is unchanged and the same genuine child) |
| S-09 | Per-instance guard: two supervisors in one test process | each launches once; refusing one has no effect on the other; the guard is not a module-level or class-level attribute (introspection) |
| S-10 | Locks and text: the creation wrapper asserts that neither the lifecycle serialization nor the reader lock is held at the moment of child creation; every refusal message is inspected; a refused `launch()` is issued while a probe is `ARMED` on the first lineage | no lock is held across creation; the reader thread never takes the lifecycle serialization (extends W-08); every refusal text is the one fixed string and contains no argv, environment, path, cwd or id sentinel; the refused launch neither disturbs the first lineage's probe nor its slot |

### 11.3c Child-resource ownership rows (R2 resource-authority correction)

Every C-row drives the **real** `PiRpcSupervisor` over a synthetic peer under
`tmp_path`. A test-side **substitute** is a process-like recorder whose `stdin`
(`write`, `flush`, `close`), `stdout`, `stderr`, `poll`, `wait`, `terminate`,
`kill` and every attribute access append to a call log; it also stands in for
"any process AIDO did not create". "Substitute every public process binding"
means: enumerate the supervisor's public names by introspection, and for each one
that is, or could hold, a process-shaped value (at minimum `process`, and any
public orphan diagnostic), attempt assignment **and deletion** through the
supported API. For `process` **both must refuse** and the row asserts the refusal
and the unchanged value — there is no "or is inert" outcome for `process`. The
oracle is threefold:
**(1)** the substitute's call log, which must be **empty**; **(2)** the peer's
capture of stdin bytes and observed exit, which must show the **genuine** child
received every byte and was torn down and reaped (not stranded); **(3)** an
identity log, recorded by test-side wrappers, of the object every consumption
acted on, which must be the genuine child (by `is`) every time. Rows marked
*white-box* deliberately rebind a **private** attribute, in tests only, to show
that the §5.6.2 verification fails closed for a smuggled binding; that is a
defense-in-depth demonstration, **not** a claim about the supported-API boundary.

| ID | Scenario | Required result |
|---|---|---|
| C-01 | After a successful `launch()`, attempt to substitute (assign and delete) every public process binding — each attempt on `process` refuses — then run a generic `send_command`, the L16 probe, `await_response` (which polls), and `shutdown()` | substitute log **empty**; the genuine peer received the generic command and the probe frame; facts come from the genuine peer; the genuine child exits under the `shutdown()` ladder and is reaped; no stranded child |
| C-02 | Boundary sweep: for each consumption boundary — before the probe commit; between commit and physical write (barrier); before each `_wait` poll; before shutdown's stdin close; before its `wait`; before `terminate`; before `kill` — attempt to substitute every public binding immediately before the boundary | every attempt on `process` refuses; at every boundary the action lands on the genuine child (identity log) and never on the substitute; the sweep also includes attempting substitution **before** `launch()` (refused as well, `process` reading `None`), after which the readers and `_wait` still use the genuine child |
| C-03 | Retire, **then** attempt to substitute `process` (refused), then `shutdown()`; and attempt substitution during a committed in-flight probe write while `shutdown()` waits (W-03/W-06 setups) | zero probe bytes after retirement-first, as W-04; every attempt on `process` refuses and `process` still reads the same genuine child after retirement; the genuine child is torn down by the ladder; the substitute log is empty; nothing is retargeted |
| C-04 | Through the compatibility observation, assign a recorder to the exposed genuine child's `.stdin`, `.stdout` and `.stderr` after install, then send, probe, and shut down | writes still reach the genuine peer through the **captured** stdin; the recorder receives nothing; shutdown closes the captured stdin (the peer sees EOF); the readers keep reading the genuine output |
| C-05 | **Orphan surface:** run the S-06(b) orphan scenario; while the launching call is held between L3 and its teardown, attempt to substitute every public binding, including any public orphan diagnostic and `process` (assignment and deletion of `process` refuse) | the launching call signals and reaps only the genuine orphan child (identity log; the peer observes its exit); the substitute log is empty; `process` reads `None` throughout (the orphan is never exposed as `process`); the orphan is not stranded |
| C-06 | *White-box:* (i) with a genuine runtime-child binding, place a genuine **orphan** binding (from another supervisor's orphan run) in the orphan slot; (ii) for an orphan teardown, place a genuine **runtime-child** binding in the orphan slot. Also assert that no public method, constructor parameter or launch input accepts a child, pipe or binding | in (i) and (ii) every consumption **fails closed** (role or mutual-exclusion check): no write, poll, signal or close is issued to any object, and the fixed-text error is raised; no supported API accepts a binding |
| C-07 | *White-box:* launch supervisors A and B against separate peers; place B's runtime-child binding in A's private slot. Through the supported API, attempt to assign B's genuine child to A's public `process` (refuses) | A's `send_command`, probe, poll and `shutdown()` refuse on the owner check with no action on either child; through the supported API, A's consumptions are unaffected and B's peer never receives A's probe bytes |
| C-08 | After install, mutate every compatibility-facing field that is mutable (`commands_sent`, `stdin_write_error`, `termination`, and any public diagnostic) and attempt to mutate `process` (which refuses), then re-run the sequence of C-01 | the trusted target — the identity captured by a test-side read of the binding at install — is unchanged, and every consumption acts on it |
| C-09 | After every refused or repeated `launch()` of S-01…S-04 (`ACTIVE`, `RETIRED`, `FAILED`, the concurrent loser) | the runtime-child binding, the orphan binding, each binding's child and captured pipes and its role are identical objects, unchanged — and a binding that was never established (as in S-05) is still not established; extends S-08 |
| C-10 | Retirement: retire an `ACTIVE` supervisor, then probe, then `shutdown()` | the probe refuses with zero bytes (operation authority invalid); the runtime-child binding is the identical object with the identical child; `shutdown()` still tears down that same genuine child through it; no retargeting |
| C-11 | Source/AST checks on `ar2/supervisor.py` | every `stdin` write/flush/close, every `poll`/`wait`/`terminate`/`kill` call and every reader-pipe argument takes its target from the ownership accessor; the only reads of the public `process` name are the compatibility observation itself; the only writers of either binding are L3 and the unwinding orphan bind, each from the L2 return value; the module has exactly one child-creation site; no method, constructor parameter or public signature accepts a child, process, pipe or binding (extends R-30) |
| C-12 | The `process` contract of §5.6.2, state by state | `process` is determined **solely** by whether a runtime-child binding has ever been established (the §5.6.2 state rule): it reads `None` before launch, mid-launch before L3, after an L2 `OSError`, after a never-launched supervisor is retired before its first launch, and in the orphan path; after install and after a partial install failure (S-03(ii)) it is the genuine child (`is`), and after retirement/`shutdown()` it is still that same object; a launch refused at L1 **leaves `process` exactly as it was** — `None` where no binding was ever established (for example the retired-before-first-launch supervisor, S-05), and the same genuine child where a binding exists (repeated launch while `ACTIVE`, after a partial-failure `FAILED`, after retirement of an installed supervisor, the concurrent loser); L1 refusal never creates, clears, replaces or retargets the binding; assignment (of `None`, a running fake, an exited fake, a real `Popen` from another supervisor) and deletion refuse in **every** one of those states and leave the value unchanged; introspection finds no public setter, mutator, `launch()` keyword, constructor parameter or alias that can change it; a value forced into the instance namespace under the same name (white-box) does not shadow it; a source check shows the value is computed from the runtime-child binding on read, that no second attribute stores the child, and that `__init__` does not assign it; no `PiRpcSupervisor` operation in any row takes a target from `process` (other AIDO components' reads of it are covered by C-13 to C-15) |
| C-13 | **Semantic P8 cannot be retargeted.** A real supervisor with a synthetic child. Attempt to assign `None`, a fake running process and a fake exited process to `supervisor.process`; then evaluate the P8 expression `supervisor.process is None or supervisor.process.poll() is not None`, once while the genuine child runs and once after the genuine child has exited | every assignment refuses and leaves the observation unchanged; the expression is `False` while the genuine child runs (even with a fake-exited object offered) and `True` after it exits (even with a fake-running object offered), i.e. it reflects **only** the genuine child; no substitute's `poll()` is ever called |
| C-14 | **Partial-launch ownership decision cannot be suppressed or forged.** Construct the partial-install failure in which the runtime-child binding exists and `launch()` raises (S-03(ii)). Before evaluating the qualification adapter's `if supervisor.process is None` check, attempt to assign `None` and a substitute process; then evaluate the check and its retain-and-close path. Also evaluate CFG1's L14 `getattr(supervisor, "process", None) is not None` and L21 decision. Then the opposite states: `Popen` `OSError` (no binding) and the orphan path | both assignments refuse; the check observes the **genuine** child and the existing partial-runtime ownership/cleanup path runs against it (the genuine child is torn down, the substitute is never touched); L14 records `runtime_created` and L21 calls `shutdown()`; for `Popen` `OSError` and for the orphan path `process is None` (the `OSError` case re-raises as shipped; the orphan child was already torn down by the launching call) |
| C-15 | **Static consumer inventory.** Enumerate every production read of a supervisor's `process` in `pi_external_runtime_ar2`, `pi_external_runtime_ar2_o1`, `pi_implementer_qualification` and `pi_harness_cfg1` (attribute reads and `getattr(..., "process", ...)`; tests, results and fake supervisor classes excluded) | the set equals the reviewed §5.6.2 inventory — semantic P8, qualification partial-launch, CFG1 L14, CFG1 L21, AR2-O1 diagnostic gate — so a new or moved reader fails the test until reviewed; **no** production write, `setattr`, `delattr` or namespace injection of `process` on a real supervisor exists; every reader is an expression valid under read-only semantics (read, `is None`/`is not None`, `.poll()`); none reads a mutable shadow value in place of the supervisor's `process` (and, per C-11, no attribute other than the private bindings stores the child); fake supervisor test classes are not required to adopt the property |

### 11.4 Correlation and malformed-input rows

| ID | Scenario | Required result |
|---|---|---|
| R-18 | Correlated id with `command` missing / `"get_commands"` / non-`str` | raise → `RUNTIME_CORRELATION_FAILED` |
| R-19 | Correlated, `success: false` / missing / `1` / `"true"` | unobserved facts; L16 `H2_MISMATCH` |
| R-20 | Correlated, `data` non-dict; `data.model` non-dict; `model` without `reasoning` | per §8 rows |
| R-21 | Arming precedes the write (the peer sees the command only after the test-side observer sees the slot `ARMED`) | holds |
| R-22 | Classifier / H2 forced to raise via a value whose `__eq__`/`__bool__`/`__repr__`/`__hash__`/`__len__` raise or record calls, injected by a test-side decoder wrapper | no dunder on the raw reasoning value is invoked; forced exceptions → `POISONED` with fixed reason; `read_error is None`; leak check clean |
| R-23 | Protocol violation / byte cap / record cap before resolution | unobserved facts; over-cap bytes never classified |
| R-24 | Stream parity: identical frames with no probe vs. the pre-change reader | published records and `ReasoningDropStats` identical |
| R-25 | Probe with expectations mismatching the peer's provider/model | `h2 is False`; other facts still classified; L16 `H2_MISMATCH` |

### 11.5 No-generic-capability rows (mechanical)

| ID | Required result |
|---|---|
| R-30 | The probe method has **no** parameters beyond `self`, and `launch()` keeps **no** parameters beyond `self`; no reader or supervisor public signature gains a path, key, command-type, extractor, predicate, classifier, hook or callback parameter |
| R-31 | See §11.6 (installed-source re-proof) |
| R-32 | The probe's command type is a module constant equal to `"get_state"`; no code path lets a caller influence it |
| R-33 | AST check on the raw-classification function: the value is used only in `Compare` nodes with `is` against `True`/`False`; no `Call` on it (`str`, `repr`, `len`, `hash`, `bool`, `format`, `json.*`, `type`), no `==`/`!=`, no subscripting, no attribute access |
| R-34 | Constructor expectations: non-`str`, empty, `bytes`, `str` subclass instances → construction refuses |
| R-35 | CFG1's L16 function signature has no parameter through which facts, a literal, a response, a state document or a supervisor other than the run state's can enter |
| R-36 | Exactly one definition exists of each §8.2 classifier (AST/import check); CFG1's existing classification tests pass against it unchanged in expectations |
| R-38 | Publication under the lock: slot resolution and publication of the matched record happen in one reader-lock critical section with no self-deadlock (the test completes within a short bound); the lock-acquiring `_publish()` is never entered while the lock is held (instrumented lock wrapper); ordering, `notify_all` wake-ups and record-cap behavior match R-24 |
| R-39 | Expectation-binding immutability through the supported API: after construction, attempt assignment and deletion on every public attribute name; enumerate the supervisor's and the probe's public surface for any setter, mutator or keyword that could change them; call `launch()`; then run the probe against a peer that reports the construction-time identity, and again against one that reports a different identity | no supported path changes the binding (assignments to public names raise, or no such names exist); H2 is `True` for the construction-time identity and `False` for any other; the slot's copied expectations equal the construction-time values |
| R-40 | Provenance and exact value agreement for CFG1's supervisor builder: (i) the provider/model values in the argv produced by `build_pi_argv` equal the supervisor's bound expectations, **and** both equal `PROVIDER_ID` / `CFG1_MODEL_ID` exactly; (ii) an AST/source check shows both call sites take them from those frozen module constants, with no literal, environment, config or runtime-derived source. Python object identity is **not** asserted and is not the property |

### 11.6 T-3 correction and installed-source re-proof

- `test_t3_the_cfg1_projection_agrees_with_the_installed_runtimes_own_shape`:
  its docstring must be corrected to say it proved **composer shape →
  projection logic** only and bypassed AR2 ingestion. Because the projection no
  longer accepts a state document, it is replaced by R-37.
- `test_t3_the_serialized_model_carries_exactly_the_declared_compat_shape`:
  unchanged in substance; its `serializedModelReasoning is True` stays a
  composer-level fact and must not be cited as live-path evidence.
- **R-37 (required).** Extend the T-3 harness report with the composed model
  object as `JSON.stringify` serializes it (synthetic `.invalid` base URL only).
  The synthetic peer wraps it exactly as §16 establishes Pi does —
  `{"id": <probe-minted id>, "type": "response", "command": "get_state",
  "success": true, "data": {"model": <that object>, "thinkingLevel": "medium",
  …}}` — as one LF-terminated line, and it goes through the real
  supervisor/reader/probe path and the real L16 function for each of Q/R/E/H.
  Required: `R == "TRUE"` and the correct `C` per arm, `h2 is True`, no
  `reasoning` key surviving anywhere, and the synthetic base URL absent from the
  returned facts and from every emitted record. This is the missing
  `wire → AR2 ingestion → supervisor → CFG1 projection` link.
- **R-31 (required, source inspection only; re-proves §16).** From the installed
  Pi package, with `rpc-mode.js` first verified against its
  `PINNED_PI_SEAM_DIGESTS` entry: assert the `success` helper returns
  `{ id, type: "response", command, success: true, data }`; the `get_state`
  case returns `success(id, "get_state", state)`; `handleCommand` binds
  `const id = command.id`; and the thrown-error path emits
  `error(command.id, command.type, …)` with `success: false`. A mismatch means
  the correlation design must be re-reviewed, never weakened.

### 11.7 Suites that must remain green

Full AR2, AR2-O1, `pi_implementer_qualification`, and CFG1 suites, including
every existing reasoning-drop, scrub, H1/H2, lifecycle and record-validator
test. No existing test may be deleted or weakened; the only permitted edits to
existing tests are the two T-3 docstring corrections, the replacement of the
one T-3 projection test by R-37, and migrating CFG1 tests and doubles that call
`project_get_state` or the removed `evaluate_model_identity` port (§12.2).

---

## 12. Migration and compatibility

### 12.1 AR2 and its other consumers

The expectations are an **optional** constructor input and the probe refuses
without them, so `run_ar2.py`, AR2-O1 and the qualification adapters construct
and drive `PiRpcSupervisor` exactly as today. With no probe in flight, the
reader's published records and `ReasoningDropStats` are identical (R-24).
Retirement as `shutdown()`'s first step changes no rung, no recorded field and
no claim; it only makes a probe impossible afterwards. The launch-authority guard
(§5.6.1) changes behavior only for a **second** `launch()` on one instance, for a
launch after retirement, and for a launch that loses a race to retirement; every
existing caller (`run_ar2.py`, AR2-O1's handshake, the qualification adapter's
one launch call, CFG1 L14) launches each instance at most once, and a single
launch on a fresh supervisor is unchanged. The ownership binding (§5.6.2,
R-AR2-6) changes only *which attribute each child operation reads its target from*;
every existing caller keeps reading `process` and none assigns it on a real
supervisor, so no caller's code or behavior changes. One shipped behavior does
change: assigning to, or deleting, `supervisor.process` on a real supervisor now
refuses (§5.6.2, R-AR2-6). Several of those readers use it as an input to
authority-relevant decisions (semantic P8, partial-launch ownership, CFG1 L14/L21),
which is why it is read-only rather than a mutable attribute the supervisor
ignores; the consumer inventory is in §5.6.2. AR1 has its own separate supervisor
copy, which this amendment does not touch. AR2's `reasoning_drop`
policy text remains accurate. No historical AR2/O1/qualification artifact is
reinterpreted.

### 12.2 CFG1

- L16 sends one `get_state` (the probe's) instead of one (`h2-…`): command count
  and order unchanged; no inference.
- `Cfg1RunPorts.evaluate_model_identity` is removed; `build_supervisor` passes
  the bound expectations; `project_get_state` is replaced by the L16 function.
- CFG1 test doubles that return a raw state document or a hand-made verdict for
  L16 must be migrated to a real supervisor over a synthetic peer, or a
  supervisor double whose probe returns scripted scalars and which is used
  **only** in rows asserting CFG1's type-check and refusal mapping.
- Record schemas, validators, enums, `RUN_RECORD_VERSION`, refusal vocabulary
  and the manipulation predicate: unchanged.

### 12.3 Authorization binding

The A1 and A2 authorizations are bound to HEAD
`eea76c100895ca0be028ba474682a15487a53c2e` and state that no production file
under `experiments/pi_harness_cfg1/` changed. Implementing this amendment
changes production files in CFG1 **and** AR2. Neither A1's nor A2's scope can be
reused; a new authorization is required (§14).

---

## 13. Status of A1 and A2 evidence

Artifacts, opened read-only for this amendment, unmodified:

| Artifact | SHA-256 |
|---|---|
| `CFG1-S1-A1/S1_01_Q.json` | `315e5780a07ab3da3fdee5dd38f61b6797690db389217e1b8275200b28219cec` |
| `CFG1-S1-A1/S1_stage_closure.json` | `fee44394ed8a942bdaed805dd3336c8b90bf15e4d6075e768ac545aab22bcfb3` |
| `CFG1-S1-A2/S1_01_Q.json` | `e9a50844f1eb03879c34c988de0e1a54983af1d44ef3546055c8c8953ea7b796` |
| `CFG1-S1-A2/S1_stage_closure.json` | `7027c35ce023c229dfab6fb54b7ba75a4938797ce65ca628e92ca7404d10d783` |

- **A1** (refused at L4, `CREDENTIAL_BOUNDARY_FAILED`, never reached L16) is
  unaffected and remains valid historical evidence exactly as recorded.
- **A2** remains valid historical evidence **of what the shipped instrument
  observed**: H1 matched, H2 matched, declared compat shape `ABSENT` observed,
  thinking level `medium` observed, zero prompt writes, stage halted at ordinal
  1. Its `runtime_reported_model_reasoning = OTHER` is a truthful record of the
  v1 projection over the **sanitized** document. It must **never** be read as
  "Pi reported a non-boolean reasoning flag", and **never** reinterpreted,
  re-projected, or upgraded to `TRUE`. It is not evidence that Pi would have
  reported `true`; AIDO has not observed that live.
- Neither A1 nor A2 participates in any contrast. Both stay consumed. Neither
  `stage_execution_id` may be reused.
- A2's positive facts are **context** for reviewing this amendment, never a
  substitute for a passing L16 under a future authorized run.

---

## 14. Conditions before implementation, and before any A3 authorization

Before implementation (`CFG1-L16-FU2-IMPL`) may start:

1. **This exact amendment — revision R2, including §5.6.1's launch-authority
   rules — is itself independently reviewed and explicitly accepted, with
   acceptance recorded outside this file.** The acceptance record must name
   revision **R2** and identify the reviewed text by the SHA-256 of the exact
   file bytes reviewed (a file cannot contain its own digest, which is why the
   record lives outside it). **Acceptance of R0 or R1 — or of any earlier text of
   this file, including an earlier copy that was also labelled R2 — grants no
   implementation authority for this R2.** The gate is bound to the text under
   review, never to a revision that preceded it.
2. The reviewer confirms the §9 reopen list (including R-AR2-3's launch-authority
   guard, R-AR2-4's classifier placement, **R-AR2-6's child-resource ownership
   binding**, and R-CFG1-2's port removal) is
   complete, the §10 frozen list is correct, and accepts the §8 schema decision.

Before any `CFG1-S1-A3` authorization may even be drafted:

3. `CFG1-L16-FU2-IMPL` is complete, offline only: every §11 row implemented and
   passing, §11.7's suites green, R-31 re-proven against installed Pi 0.85.1,
   and `PINNED_PI_SEAM_DIGESTS` still matching.
4. An independent implementation review accepts it, specifically confirming:
   no generic hook/parameter (R-30, R-32, R-33, R-35); no state tree or
   container crosses the boundary (R-16, R-17); reduction before publication
   (R-11, R-12); the lifecycle rows L-01…L-11; the write-race rows W-01…W-08;
   duplicate semantics (R-14, R-15); publication and bindings (R-38…R-40);
   the launch-authority rows S-01…S-10 (§11.3b); the child-resource ownership
   rows C-01…C-15 (§11.3c); R-10 and R-37 exercise the real
   receive boundary with no hand-built dict; and no existing test was weakened.
5. The frozen CFG1 design and AR2 docs gain a pointer to this amendment (a
   separate documentation-sync step, not this phase).
6. The A3 authorization is a **new**, separately reviewed document naming a new,
   never-used `stage_execution_id`, bound to the new HEAD, restating that A1 and
   A2 are consumed and non-participating. Authoring it grants no authority until
   accepted.

Nothing in this document authorizes implementation, a live run, a Pi launch, a
B300 contact, or A3. `CFG1-LIVE-S2` remains **NO-GO**.

---

## 15. Residual limitations (stated, not closed)

- The facts are **runtime claims** (H2 a verdict over one). AIDO correlation
  does not make Pi's report true (§5.7).
- I-8 is "not retained by an AIDO-reachable reference", not "erased from
  memory".
- F-1's last-write-wins `responses` map persists for non-probe commands (H1).
- The published sanitized `get_state` record in `activity.responses` still
  carries `baseUrl`/`sessionFile` in memory, as before this amendment; CFG1
  never persists it, and it no longer reaches any CFG1 code at L16.
- JSON duplicate-key collapse within a frame is not detected (§7.1).
- F-5: the generic `send_command` path is not serialized against `shutdown()`
  (unreachable in CFG1's single-threaded flow).
- If a committed probe write never completes, `shutdown()` leaves stdin
  unclosed (bounded, recorded truthfully). It is never closed concurrently with
  that write (§5.6).
- Expectation-binding immutability holds through the supported API only.
  Deliberately rebinding private attributes is outside the in-process boundary
  (§5.2). The same scope applies to launch and lifecycle state: code that
  rebinds a private attribute or re-invokes `__init__` on a live supervisor is
  outside the boundary (§5.6.1). It applies to the child-ownership bindings too
  (§5.6.2): the §5.6.2 verification makes a smuggled binding fail closed, but the
  supported-API guarantee is what is claimed.
- Patching the *methods* of the genuine `Popen` object, or acting directly on the
  genuine child through the compatibility observation, changes how AIDO's own
  child behaves and never which resource an AIDO operation targets, and never
  which object an external `process` reader observes (§5.6.2). The observation
  exposes the genuine `Popen` object itself, so a reader such as semantic P8
  sees that object's own reported state; that is the genuine child's state, not a
  forgeable one, and code that patches the object's methods is outside the
  supported-API boundary exactly as elsewhere in this section.
- If a §5.6.2 verification fails at consumption (only possible after a private
  rebinding), that consumption fails closed and issues no action; the child it
  would have acted on can be left running. The failure is loud (a fixed-text
  error), and it is unreachable through the supported API.
- In the adversarial launch-races-retirement case (an orphan child, §5.6.1),
  `shutdown()`'s own returned record does not describe that child: the launching
  call tears it down afterwards and records it in a separate diagnostic field.
  This is unreachable in CFG1's single-threaded flow (including CFG1 L14's
  `runtime_created` observation, which reads `process`) and is not a change to
  any persisted record schema.
- The orphan child's teardown carries the same claim scope as `shutdown()`'s:
  AIDO signalled only the direct child; nothing is claimed about descendants,
  inference or provider requests.
- F-7 (a pre-existing `_drain()` assertion after a partial-launch-failure
  ladder) is recorded and not closed.

---

## 16. Established fact: installed Pi 0.85.1 `get_state` response shape (R-31 resolved)

Resolved in R1 by **read-only source inspection**; Pi was not launched.

- Package: `@earendil-works/pi-coding-agent`, `package.json` `"version":
  "0.85.1"`.
- `dist/modes/rpc/rpc-mode.js` SHA-256
  `e7e4724aa55c5aac73cf36793653b26736200e5c59d58373990fc31028f86477` — equal to
  its `PINNED_PI_SEAM_DIGESTS` entry. (`dist/modes/rpc/jsonl.js`
  `049a9f8ca4242c79f1911ed977949e8d8906b4561f424c2729687f426fabaacf`, also
  equal to its pin.)
- The success helper is
  `const success = (id, command, data) => … return { id, type: "response",
  command, success: true, data };` (a `data === undefined` branch omits `data`).
- The error helper is
  `{ id, type: "response", command, success: false, error: message }`.
- `handleCommand` binds `const id = command.id;` and the `get_state` case
  returns `success(id, "get_state", state)`, where `state` includes `model:
  session.model`, `thinkingLevel`, and also `isStreaming`, `sessionFile`,
  `sessionId`, `sessionName`, message counts and mode fields.
- `handleInputLine` writes the returned object with `output(response)`, i.e.
  `serializeJsonLine`. A thrown command error emits
  `error(command.id, command.type, …)` — for our probe that is
  `command: "get_state", success: false`, handled by §8's `success` row. A
  parse failure emits `error(undefined, "parse", …)`: no `id`, never a match.

Therefore a successful `get_state` response **does** carry exact
`command: "get_state"` and **does** echo the request id as the same JSON value
AIDO sent (an ASCII string round-trips as that string). §5.4 (b)'s requirement
is an established design fact, not an implementation-time uncertainty. R-31
remains required as an implementation regression that re-proves it against the
installed, digest-verified file.

---

## 17. Changelog — R1 against R0

| Finding | R0 | R1 |
|---|---|---|
| 1. Full sanitized state inside the authority-bearing observation | Observation carried a deep copy of the sanitized `get_state` record while claiming "no model subtree" | No state tree crosses the boundary. The reader reduces the one correlated record to one `bool` + three closed `str` **before publication**; `evaluate_model_identity` is called unchanged there and only its `passed is True` is kept (§5.3–§5.5, §6.2 I-8–I-10, §8) |
| 2. Post-validation mutation | Relied on a deep copy inside an immutable wrapper | All facts are scalars computed on a reader-local object no other thread can reference; no frozen wrapper around a container is relied on; mutation rows R-11–R-17 (§5.5, §11.2) |
| 3. Observation lifetime across shutdown | Redemption did not require the minter to be live; an unredeemed object could outlive shutdown | Supervisor `ACTIVE`/`RETIRED` lifecycle, retirement as `shutdown()`'s first atomic step; arm→write→wait→consume in **one** parameterless call with a `finally`; no redeemable object exists; linearized race semantics; rows L-01–L-11 (§5.6, §11.3) |
| R-31 | Implementation-time uncertainty | Established from installed, digest-verified source (§16); retained as a re-proof regression |
| Construction-time H2 expectations | — | New, optional, exact-`str`, bound at construction (§5.2); required so H2 can be computed before publication without a probe-time parameter |
| Classifier placement | CFG1-only | Single statically bound definition reachable from the reader (R-AR2-4) |
| `Cfg1RunPorts.evaluate_model_identity` | Changed shape | Removed; L16 calls the probe on `state.supervisor` directly (R-CFG1-2) |
| Section numbering | §1–§15 | §1–§3 and §13 unchanged in content; §4–§12, §14, §15 revised; §16–§18 added |

---

## 18. Second adversarial self-review (against R1 as written)

Each question was re-asked of the revised text, not of the intent.

1. **Does any container cross the boundary?** The return is one `bool` + three
   `str` (§5.3); the slot holds only scalars (I-8); CFG1's L16 function accepts
   no facts (R-35). The only non-scalar objects are the pre-existing published
   stores, which the probe does not read. **Holds.**
2. **Can H2 and §8.2 see different snapshots?** Both are computed in §5.4 (e) on
   one reader-local object before (f) publishes it; the only other thread that
   could obtain a reference does so via publication, which happens after.
   Duplicates poison. **Holds.** Dependency: the implementation must not publish
   before reduction — pinned by R-11/R-12.
3. **Can authority survive shutdown?** No redeemable object exists. The only
   authority is the call, gated by `ACTIVE` under the lock; retirement is
   shutdown's first step and monotonic; the `finally` prevents a stranded
   `ARMED`/`RESOLVED` slot. **Holds.** Residual check: a CFG1 path that skips
   `shutdown()` entirely (e.g. a crash) leaves the supervisor `ACTIVE` but its
   slot `CONSUMED` or `RETIRED` (the call's `finally`), so the probe is still
   unusable — one-shot closes it even without retirement.
4. **Is anything generic?** One parameterless call; fixed type; fixed raw path;
   statically bound classifiers; the only configuration is two exact `str`
   expectations at construction that feed a frozen equality test. **Holds.**
   Watch item for implementation review: the classifier relocation (R-AR2-4)
   must not become a registry or an injectable table.
5. **Is the raw value touched beyond identity tests?** §5.4 (c) and I-6/I-7;
   R-22 and R-33 check it mechanically. **Holds.**
6. **Are statistics still truthful?** `ingest_record` is called unchanged on the
   same decoded object; the probe does not touch the stats. **Holds.**
7. **Does §8 contradict frozen §8.2?** Mappings and domains are verbatim; the
   only divergence from v1 *code* is the `{}` substitution removal in two rows
   where H2 already fails, so no L16 outcome changes. **No contradiction.**
8. **Is `h2 := … and success_ok` a change to H2?** The frozen handshake does not
   require `success`; §16 shows a Pi 0.85.1 failure response has no `data`, so
   `passed` is already `False` there. The conjunct changes no reachable outcome
   on the pinned Pi and is fail-closed otherwise. **Tightening, not a
   contradiction.**
9. **Does the reader computing H2 need anything it cannot have without a
   parameter?** It needs the expectations; §5.2 binds them at construction.
   This is a new AR2 constructor input — enumerated in R-AR2-3, optional, and
   inert for existing callers. **Disclosed, not hidden.**
10. **Does moving classifiers into reach of AR2 invert layering?** Placement is
    left to implementation, but CFG1 already imports AR2; the single definition
    should live on the AR2 side (Pi `get_state` vocabulary) with CFG1
    importing it. AR2 importing CFG1 would invert the dependency and should be
    rejected in implementation review. **Recorded as guidance, not frozen.**
11. **Is any earlier R0 statement left that R1 contradicts?** R0's state-copy
    wording, redemption checklist, and rows R-12/R-18/R-19/R-24/R-25 (R0
    numbering) whose oracles relied on the copy were removed or rewritten; §11
    carries an explicit oracle rule. **None found.**

New contradictions discovered in R1: **none.** Two new disclosures, both
enumerated as reopenings rather than contradictions: the optional
construction-time expectations (R-AR2-3) and classifier placement (R-AR2-4).

---

## 19. Changelog — R2 against R1

| Item | R1 | R2 |
|---|---|---|
| Blocker 1: probe write vs retirement | Arm under the reader lock, release, then write: retirement could fall between arm and write, and the probe could still write `get_state` afterwards | A supervisor lifecycle serialization, distinct from the reader lock, holds eligibility→mint→arm→**write-commit** as one critical section; retirement is a critical section of the same serialization; the two are totally ordered. Retirement first → zero probe bytes. Commit first → the write may complete and every fail-closed rule applies. `shutdown()` never closes stdin while a committed write is in flight, and its wait is bounded. Neither lock is held across the write. A pre-write check on its own is forbidden (§5.3, §5.6, §7.1; rows W-01…W-08) |
| Blocker 2: duplicate matching | The id was read only when `ARMED`, yet a match in `RESOLVED` was required to poison | Matching runs in `ARMED` and `RESOLVED` only. `ARMED` + match: the one classification path. `RESOLVED` + match: `POISONED` immediately, no reclassification, facts discarded. `UNARMED`/`POISONED`/`CONSUMED`/`RETIRED`: no matching (§5.4 (a), §5.5, §7.1; R-14, R-15) |
| Publication under the reader lock | Unstated; `_publish()` would self-deadlock | Internal publication refactor or locked helper authorized; `RLock` not required; the cap check stays outside the critical section (§5.4 (f); R-38) |
| Expectation bindings | "Stored as immutable `str`" | The *binding* is immutable through the supported API: no public assignable name, setter, mutator or reconfiguration; the slot holds its own copy. R-40 now proves provenance and exact value agreement from the same frozen constants, not object identity (§5.2; R-39, R-40) |
| Consumption vs retirement | Linearized under the reader lock | Linearized under the lifecycle serialization, with the reader lock nested (§5.6) |
| New pre-existing observation | — | F-5: the generic `send_command` is not serialized against `shutdown()` (unreachable in CFG1; recorded, not closed) |
| Final correction A: implementation gate | §14 item 1 required acceptance of "This amendment (R1)" — an earlier revision, so acceptance of R1 could have satisfied the gate for R2 | §14 item 1 requires independent review and explicit acceptance of **this exact R2 amendment**, recorded outside the file, naming revision R2 and the SHA-256 of the reviewed bytes; acceptance of R0, R1 or any earlier text — including an earlier R2-labelled copy — grants no authority. No other §14 condition weakened (§14) |
| Final correction B: launch authority | Lifecycle defined, `launch()` repeatable: a second call could replace `process` and both readers under an existing slot, strand the first child, or install onto a retired supervisor | Single-use, per-instance launch authority committed in the lifecycle serialization before any child exists (L1); a failed launch is terminal; child creation holds no lock (L2); install-or-orphan is one atomic section ordered against retirement (L3) so a launch can never install on a retired supervisor and a late child is attributed and torn down by the launching call; both state fields monotonic; rows S-01…S-10 (§5.6.1, §7.1, §9.1 R-AR2-3, §11.3b, §15, §21) |
| Reopen list | — | R-AR2-3 now also names `launch()`'s one-shot guard as an explicit reopening; §10 freezes everything else about `launch()` |
| Final correction C: child-resource authority | Cleanup and runtime operations (`send_command`'s write, `_wait`'s `poll()`, the shutdown ladder, reader-pipe hand-off) read the public, assignable `process` at each use; the orphan child was held in a mutable attribute used as teardown authority; the exposed child's `.stdin`/`.stdout`/`.stderr` were re-read at each use. A supported caller could substitute any of them and steer an operation at a resource AIDO did not create, stranding the genuine child | The object returned by the one authorized L2 creation is bound **by identity, in L3**, into exactly one AIDO-private, write-once role — **runtime-child** or **orphan-child**, mutually exclusive — together with the pipe handles captured from that exact child. Every authority-bearing operation derives its target from that binding and verifies role, owner and mutual exclusion, failing closed; `process` is a non-authoritative compatibility observation (read-only recommended) that never exposes the orphan child; retirement invalidates operation authority and never retargets (§5.6.2, §5.3 step 4, §7.1, §7.2 F-8, §9.1 R-AR2-6, §10, §11.3c C-01…C-12, §15, §21) |
| Reopen list (correction C) | — | New **R-AR2-6**: the four shipped consumption paths change *only how they derive their target*; the public `process` stops being authoritative; the orphan path is new. §10 and §14 item 2 updated |
| Final correction D: compatibility-binding authority | §5.6.2 allowed the public `process` to be either a read-only view or a plain mutable attribute the supervisor ignored, and called external readers categorically "not authority consumers". Production code actually uses `supervisor.process` to gate the semantic prompt write (P8), to decide whether an existing child is an AIDO-created partial runtime needing cleanup (qualification adapter), to record `runtime_created` (CFG1 L14) and to decide whether `shutdown()` is called at all (CFG1 L21) — so a substituted mutable attribute could still alter those decisions | `PiRpcSupervisor.process` is frozen as a **read-only observation derived exclusively from the genuine runtime-child binding**: `None` before the binding and for an orphan, the genuine child after it (including after a partial install failure and after retirement); assignment and deletion refuse; no setter, mutator, keyword, alias or shadow; no second storage. No mutable option remains. The binding stays the sole operational authority and the two are not merged. The "not authority consumers" claim is withdrawn and replaced by the accurate consumer inventory. Rows C-13 (P8), C-14 (partial-launch ownership), C-15 (static inventory) added; C-01, C-02, C-05, C-08, C-12 tightened to remove "or is inert" (§5.6.2, §7.1, §9.1, §11.3c, §12.1, §15, §21.2) |
| Reopen list (correction D) | — | R-AR2-6 amended: the public `process` is reopened in its **mutability** (assignment and deletion now refuse; `__init__` no longer assigns it). No new item; nothing else reopened |
| Normative-consistency cleanup (E) | §5.6.2 and §21.2 said "nothing AIDO does consults/reads" `process`, contradicting the consumer inventory in the same section; C-12 (and §5.6.2 item 1) treated every launch refused at L1 as one state, contradicting "a refused or repeated `launch()` leaves it unchanged" | Wording only: the private runtime-child binding is the sole operational resource authority `PiRpcSupervisor` uses to choose targets; `process` is a read-only compatibility observation derived from it; other AIDO components (semantic P8, qualification partial-launch handling, CFG1 L14 and L21, AR2-O1 diagnostic gate) deliberately read it and cannot retarget any operational action. `process` is determined solely by whether a runtime-child binding has ever been established, and an L1 refusal leaves it exactly as it was (`None` if no binding ever existed; the same genuine child if one does). §5.6.2 gains the explicit state rule table; C-09, C-12 and S-08 restated. No design, schema, row architecture, gate or status changed |
| Unchanged | — | Four-scalar observation, pre-drop classification, unchanged `drop_reasoning` and stats, reader-local same-response reduction, parameterless one-shot probe, no redeemable object, no state tree across the boundary, durable schemas and `RUN_RECORD_VERSION`, manipulation predicate, R-31 fact, A1/A2 status, A3 NOT AUTHORIZED, LIVE-S2 NO-GO |

---

## 20. R2 adversarial self-review of the concurrency state machine

Each question was asked of the R2 text as written.

**Locks and their scopes.** L = lifecycle serialization (supervisor-owned).
Q = reader lock (the reader's `Lock`/`Condition`). Critical sections:

| Section | Thread | Holds | Blocking inside? |
|---|---|---|---|
| Probe steps 1–3 (eligibility, mint, arm, commit) | caller | L, then Q nested | no |
| Probe step 4 write | caller | **none** | yes (pipe write) |
| Probe step 4 write-state update | caller | L | no |
| Probe step 5 wait | caller | none (Q only inside `Condition.wait`, which releases it) | yes, bounded |
| Probe step 6 consume | caller | L, then Q nested | no |
| Retirement | shutdown caller | L, then Q nested | no |
| Shutdown wait for write state | shutdown caller | L only inside a `Condition.wait` that releases it | yes, bounded |
| Reader (a) match / poison | reader | Q | no |
| Reader (f) resolve + publish | reader | Q (locked helper) | no |

1. **Deadlock by lock order?** The only nesting is L→Q. The reader takes only
   Q. No section takes Q then L. **No cycle.**
2. **Deadlock by blocking I/O under a lock?** The write holds neither lock, so
   the reader can always take Q, publish and keep draining stdout; Pi is never
   starved on stdout by AIDO holding Q. **Closed.**
3. **Can retirement slip between the eligibility check and the write?**
   Eligibility and commit are one L-section; retirement is an L-section. If
   retirement is ordered first, the commit sees `RETIRED`. If the commit is
   ordered first, the write is authorized. **Total order; no gap.** Dependency:
   the implementation must not split eligibility from commit (W-01's check-then-
   write variant pins this).
4. **Can probe bytes appear after retirement when retirement won?** Bytes are
   produced only by step 4, which runs only after a commit; a retirement-first
   execution never commits. **Zero bytes** (W-04, W-01).
5. **Can stdin close overlap a committed write?** Shutdown closes stdin only
   after observing, under L, a write state other than `WRITE_COMMITTED`. Every
   write-state change happens under L. **No overlap** (W-02, W-03).
6. **Is shutdown still bounded?** The write-state wait is bounded by the
   existing deadline and reap graces; after the last rung shutdown proceeds
   without closing stdin. **Bounded** (W-06). Cost: a stuck write leaves stdin
   unclosed, which is disclosed in §15.
7. **Does a committed write that completes after retirement resurrect facts?**
   The slot was retired at retirement; §5.4 (a) does no matching in `RETIRED`,
   and (f) discards facts unless the slot is `ARMED`; consumption raises on
   `RETIRED`. **No.**
8. **Can a write failure strand a waiter?** The failure path updates the write
   state under L and notifies. **No** (W-05). A raise between commit and the
   write-state update is covered by the §5.3 step-7 `finally`, which must also
   leave the write state out of `WRITE_COMMITTED` (it sets `WRITE_FAILED`).
   *R2 clarification:* the step-7 `finally` applies to the write state as well
   as the slot.
9. **Duplicate semantics consistent end to end?** (a) reads the id under Q in
   `ARMED` or `RESOLVED`; `RESOLVED` + match → `POISONED` in that same
   Q-section with no (b)/(c)/(e); (f) resolves only from `ARMED`; consumption
   of `POISONED` raises. A duplicate processed after consumption finds
   `CONSUMED` → no matching. **Consistent.** Race between a duplicate and
   consumption: the (a) Q-section and the consume section (L→Q) are ordered by
   Q, so either the duplicate poisons first (consume raises) or consume first
   (the duplicate is ignored). **Both fail closed or are correct.**
10. **Can (f) deadlock on publication?** Only if the lock-acquiring `_publish()`
    is called under Q. R2 forbids that and authorizes a locked helper. The cap
    check stays outside. **Closed** (R-38).
11. **Can retirement race resolution?** Retirement sets the slot `RETIRED`
    under Q; (f) re-checks `ARMED` under Q. **Ordered by Q** (L-11).
12. **Can the expectations change between construction and H2?** No supported
    path mutates the binding; the slot copies them at arm time inside the
    L-section; H2 reads the slot copy. **Closed through the supported API**
    (R-39). Deliberate private rebinding is disclosed as outside the boundary.
13. **Does R2 add a generic capability?** The lifecycle serialization and write
    state are internal and not parameterized, and they add no public method or
    parameter. **No** (R-30).
14. **Does R2 change a durable schema, the stats, the drop, or the predicate?**
    No. The only termination-record interaction is the existing
    `stdin_closed: False`, used truthfully. **No change.**

**Newly discovered contradictions in R2: none.** One clarification was made
during this review and is folded into item 8: §5.3 step 7's `finally` also
moves the write state out of `WRITE_COMMITTED`. Pre-existing F-5 is recorded,
not closed.

---

## 21. Final adversarial self-review — the whole supervisor lifecycle

Walked as one sequence, then re-walked under repetition and concurrency. Each
stage was checked against the text as written.

**Construction.** Launch authority `UNUSED`, lifecycle `OPEN`, slot `UNARMED`
and unbound, expectations bound (§5.2), both readers and the runtime-child and
orphan-child ownership bindings all empty, and the compatibility observation
`process` reading `None`. Per-instance state only. Nothing runs, nothing is
created. The only place either field is initialized. **Holds.**

**First launch attempt.**

1. L1 passes only from (`UNUSED`, `OPEN`) and moves to `COMMITTED` in one
   serialization section; every other input state refuses with fixed text before
   any creation. **The commit precedes the only child-creation site**, so no
   ordering of calls can reach creation twice. **Holds.**
2. L2 holds no lock. Its return value goes into a local held under no public
   name; nothing can reach it before L3. Failure with no child → `FAILED`, no
   binding, `process` `None`. Failure after a child exists is covered by L3 or the
   exception rule. **Holds.**
3. L3 is one section, and its lifecycle test is the *only* thing that decides
   between install and orphan, so "installs on a retired supervisor" is not an
   executable path: `INSTALLED` is set only inside an `OPEN` L3, and `ACTIVE` is
   derived as `INSTALLED ∧ OPEN`. **Holds.**
4. A late child is never stranded: it is bound as the orphan-child in the
   same section that observes `RETIRED`, and only the launching call tears it
   down, through that binding, with the shipped rungs and claim scope. A `BaseException` between L1 and
   L3 cannot leave `COMMITTED` forever or an unattributed child. **Holds.**

**ACTIVE or failed-terminal.** `ACTIVE` needs `INSTALLED`, which needs a
completed install; a half-installed lineage is `FAILED`, has an unbound slot no
reader thread can reach, and stays with `shutdown()` as shipped. `FAILED` and
`RETIRED` are terminal for launch. **Holds.**

**Probe.** Eligibility is `INSTALLED ∧ OPEN`, checked in the same section that
mints, arms and commits the write, and the write's target — the runtime-child
binding's captured stdin — is read and verified in that same section. The slot,
reader and child binding it acts on were installed once and cannot be replaced, so
probe authority is tied to the one lineage of the one launch attempt — by
construction of the supervisor instance, not by any id. A refused second `launch()` cannot disturb an armed probe (S-10).
**Holds.**

**Shutdown → RETIRED.** Retirement is the first action, sets lifecycle
`RETIRED` and retires the slot (nesting the reader lock once the slot is bound),
and is valid in every launch state. A never-launched supervisor becomes
permanently unlaunchable; a committed-but-uninstalled launch resolves to an
orphan. The ladder consumes the runtime-child binding — read inside the
retirement section, write-once, and written only by an `OPEN` L3 that necessarily
precedes retirement — so the ladder never races an install and never consults the
public `process`. Retirement changes no binding. **Holds.**

**Repetition.** Second `launch()` while `ACTIVE`/`FAILED`/`RETIRED`: L1 refuses
before creation, so no field, reader, thread, pipe or binding changes (S-01,
S-02, S-03, S-08). Repeated `shutdown()`: idempotent, monotonic. Repeated probe:
already one-shot. **Holds.**

**Concurrency.** Two `launch()`: one section wins (S-04). `launch()` vs
`shutdown()`: three total orders, all safe (S-05, S-06). `launch()` vs probe: a
probe cannot exist before `INSTALLED`. `launch()` vs write/consume: the launch
sections and the probe sections are all sections of one serialization with one
lock order, and the reader thread takes none of them (W-08, S-10). **Holds.**

**Lock discipline.** Creation holds no lock. L3 holds the serialization across
reader construction/start, which reads nothing from Pi and waits on nothing
outside this process; the reader threads never take it, so a reader started under
it cannot deadlock against it. **Holds.**

**Things checked and deliberately not changed.** `send_command` is still not
serialized against `shutdown()` (F-5, unchanged); its target is now the
write-once runtime-child binding, so it is at least stable. `shutdown()`'s record
does not describe an orphan (§15, disclosed). The `_drain()` assertion after a partial
failure is pre-existing (F-7, recorded).

**Was anything R2 froze reopened?** No. The four-scalar result, the fixed raw
path, identity-test classification, the unchanged structural drop, the absence of
any generic hook, same-response reduction, duplicate poisoning, write/retirement
ordering, the no-concurrent-stdin-close rule, publication under the reader lock,
expectation-binding immutability and provenance, the record schemas and
`RUN_RECORD_VERSION`, the manipulation predicate, A1/A2 evidence, A3 NOT
AUTHORIZED and LIVE-S2 NO-GO are all untouched. The only reopenings are the
explicit `launch()` guard (R-AR2-3) and the child-resource ownership binding
(R-AR2-6), each bounded by §10.

### 21.1 Resource-authority review (R2 resource-authority correction)

**The question.** *Can cleanup or command dispatch ever target a resource AIDO did
not create for this supervisor lineage?*

**The answer is mechanically no**, through any supported API, because of five
facts, each checked against the text as written:

1. **One origin.** The only object that can acquire a launch attempt's child
   authority is the value returned by the module's single child-creation site,
   which holds it in a local under no public name until L3 binds it (§5.6.1 L2,
   §5.6.2 invariant 1; C-11).
2. **One binding, by identity, write-once, mutually exclusive.** L3 makes exactly
   one AIDO-private binding — runtime-child *or* orphan-child — and nothing writes,
   replaces, clears or accepts either afterwards; L1 refuses before any binding
   step, so a refused launch cannot touch them (invariants 2–3; C-09, C-11).
3. **No consumption reads a public name.** Every write, flush, poll, wait,
   terminate, kill and close, and the reader-pipe hand-off, takes its target from
   the binding — and its **captured** pipes, so assigning to the exposed child's
   `.stdin`/`.stdout`/`.stderr` retargets nothing (§5.6.2 table; C-01, C-02, C-04).
4. **Each consumption verifies** role, owner and mutual exclusion and fails
   closed, so even a smuggled orphan-for-runtime or cross-supervisor binding
   causes no action (C-06, C-07).
5. **Retirement retargets nothing.** It invalidates the probe's operation
   authority only; cleanup authority stays bound to the same child (C-10).

**Walk, attempting supported/public substitution at every boundary.**

| Stage | Substitution attempted | Outcome |
|---|---|---|
| Construction | assign to or delete `process` (or a public diagnostic) | refused; the observation reads `None` because no binding exists; nothing is consumed from it; a later L3 binds the genuine child regardless |
| L2 → L3 | none reachable: the child is in a local under no public name | the binding is made from the L2 object only |
| L3 reader construction | assign to `process` before or during launch | refused; readers take the pipes captured in the binding, not `process` |
| H1 / L18 `send_command` | assign a substitute to `process` (refused); rebind `.stdin` on the exposed child | the write goes to the captured stdin of the runtime-child binding |
| L16 probe commit and write | attempt substitution at eligibility, between commit and write, or during the wait (refused) | target read and verified in the commit section; the write and the `_wait` polls use the binding |
| `_wait` polling | substitute `process` | `poll()` is on the bound child |
| Shutdown | substitute before stdin close, `wait`, `terminate` or `kill` | each acts on the bound child and captured stdin; the substitute log stays empty; the genuine child is reaped |
| Orphan teardown | substitute every public name; supply a runtime-child binding | consumes only the orphan binding, verified against the L2 return value; a wrong-role binding fails closed |
| Retirement | retire, then substitute, then shut down | binding unchanged; the genuine child is torn down through it |
| Repeated / refused `launch()` | any | refused at L1; bindings unchanged |

**Was anything R2 froze reopened?** Only where the consumption path had to be
enumerated (R-AR2-6). The four-scalar result, reasoning containment,
same-response reduction, duplicate poisoning, write/retirement ordering, lock
order, the launch state machine, failed-launch terminality, orphan attribution,
publication locking, expectation binding, the exact-R2 gate, the record schemas
and `RUN_RECORD_VERSION`, the A1/A2 evidence, A3 NOT AUTHORIZED and LIVE-S2 NO-GO
are untouched.

**Newly discovered contradictions: none.** Items tightened during these reviews
and folded into the text: the slot is bound as the *last* install step (so a
partial install never exposes a slot to a reader thread); the
`BaseException`/COMMITTED-forever rule; the exposed child's pipe attributes are
captured at bind time (a public name holding the genuine child would otherwise
still have let a caller rebind `.stdin`); `shutdown()` reads the runtime-child
binding inside its retirement section; and `orphaned_process`, a mutable attribute
used as teardown authority in the previous text, is replaced by the private
orphan-child binding. Two pre-existing observations are recorded and not closed:
F-7 (the `_drain()` assertion after a partial-launch-failure ladder) and F-5 (the
generic `send_command` is not serialized against `shutdown()`).

### 21.2 Compatibility-authority review (R2 compatibility-authority correction)

**The question.** *Can any supported operation change what object an existing
production `process` reader observes?*

**The answer is mechanically no.** The observation is read-only and derived on
each read from the private runtime-child binding, which is write-once and reachable
by no supported API. So the object a reader sees is fixed by exactly one event —
the L3 binding of the L2 object — and only two values are possible: `None` (while
no runtime-child binding has ever been established, including after an L2 failure,
and for an orphan) or that one genuine child. `process` depends solely on whether
that binding has ever been established, and on nothing else. Walked against every
supported operation:

| Supported operation | Effect on what a `process` reader observes |
|---|---|
| Assign to `process` (any value, including `None`, a running or exited fake, another supervisor's `Popen`) | refuses; unchanged |
| Delete `process` | refuses; unchanged |
| Constructor parameter, `launch()` keyword, setter, mutator, reconfiguration method | none exists (C-12) |
| Refused, repeated or concurrent-loser `launch()` | refused at L1 before any binding step; L1 never creates, clears, replaces or retargets the binding, so the observation is **left exactly as it was** — `None` if no binding was ever established (a never-launched supervisor retired before its first launch), the same genuine child if one exists (C-09, C-12) |
| A launch that fails after the binding exists | binding stays; still reads the genuine child, so the partial-launch ownership test and CFG1's L21 teardown still see it (C-14) |
| A launch that fails with no binding (`Popen` `OSError`) | stays `None` (C-14) |
| An orphan path | the orphan binding is never read by the observation; stays `None` (C-05, C-12) |
| Probe, `send_command`, `_wait`, reader construction | none writes the observation or the binding |
| Retirement / `shutdown()` | changes no binding; the observation keeps reading the same child (C-03, C-10, C-12) |
| Value written into the instance's own namespace | cannot shadow it (C-12, white-box) |
| A new production reader appears | fails the inventory test until reviewed (C-15) |

The **state** the genuine child reports (`poll()` returns `None` while it runs and
an exit code after) changes as the genuine child runs and exits; that is the
observation working, not a retargeting. The five production readers — semantic P8,
the qualification adapter's partial-launch test, CFG1 L14 and L21, and the AR2-O1
diagnostic gate — therefore each see only the genuine child's own state (C-13,
C-14), and the failure that a forgeable `None` at L21 would have caused (skipping
`shutdown()` and stranding the genuine child) cannot occur.

**Separation preserved.** The observation is a projection of the binding, never a
copy. The binding stays the sole operational resource authority `PiRpcSupervisor`
uses to choose targets; no supervisor operation takes a target from `process`.
Other AIDO components — the five production readers above — deliberately read the
observation as an input to lifecycle, dispatch, cleanup or diagnostic decisions,
and gain no ability to retarget any operational action, because it is read-only and
always projects the genuine binding (§5.6.2).

**Was anything else reopened?** No. Private runtime-child and orphan-child
ownership, captured pipe provenance, private binding verification, single-use
launch authority, launch/retirement ordering, probe write/retirement ordering, the
four-scalar observation, reasoning containment, duplicate poisoning, same-response
reduction, the schemas and `RUN_RECORD_VERSION`, the A1/A2 evidence, A3 NOT
AUTHORIZED and LIVE-S2 NO-GO are unchanged. R-AR2-6 is amended only in the
mutability of `process`.

**Newly discovered contradictions: one, and it is corrected.** §5.6.2 as written
before this correction allowed a plain mutable `process` while its own text and
§9.1 called the external readers "not authority consumers"; production code
(semantic P8, the qualification partial-launch ownership test, CFG1 L14 and L21)
uses the observation as an authority-relevant input, so that classification and
the permissive shape were both wrong. Both are corrected above and in §9.1, §7.1,
§12.1 and §19. No further contradiction was found.

---

## Final outcome

```text
CFG1-L16-FU2 DESIGN AMENDMENT CANDIDATE (R2) — PENDING INDEPENDENT REVIEW
IMPLEMENTATION NOT AUTHORIZED — CFG1-S1-A3 NOT AUTHORIZED — LIVE NOT AUTHORIZED
CFG1-LIVE-S2 NO-GO
```
