# Phase 5F3B-HARNESS-OBS1 — Durable Runtime-Activity Companion Evidence

**DESIGN ONLY.** No production code is modified by this document. No model was
run. Q1/Q2/Q3 were not re-run. DX-1 was not run. M4 was not entered.

**This revision is 5F3B-HARNESS-OBS1-DESIGN-FU1**, a narrow correction against
the original OBS1 draft. FU1 does not implement OBS1, run a model, or modify
production source/tests. It exists because independent review found the
original draft's proposed mechanism silently amended two frozen contracts
(a fifth semantic port, a new `TaskAdapterBundle` member) and a frozen gate
topology (a new `RUNTIME_ACTIVITY_SNAPSHOT` gate), and left two correlation
claims — the per-dispatch binding of tool-call facts, and several cross-field
invariants — asserted in prose rather than proven from source. See §15 for the
itemized changelog against the prior draft.

**Contract authorization note (5F3B-HARNESS-OBS1-CONTRACT-A1).** §4.2 below
widens `SemanticTurnObservation`'s field set, which a further independent
review correctly identified as an explicit amendment to a *separately*
frozen contract (`tests/test_semantic_session.py`'s exact-set regression),
not a mere implementation detail. That amendment is authorized by the
narrow, separate document
[PHASE_5F3B_HARNESS_OBS1_CONTRACT_A1_PHASE2_OBSERVATION_AMENDMENT.md](PHASE_5F3B_HARNESS_OBS1_CONTRACT_A1_PHASE2_OBSERVATION_AMENDMENT.md),
which this design relies on rather than re-argues. Read that document
alongside §4 below.

**This revision also incorporates 5F3B-HARNESS-OBS1-DESIGN-FU2**, a further
narrow correction. FU2 does not implement OBS1, run a model, or modify
production source/tests. It exists because independent review found that,
although §10 (below) correctly *stated* the requirement that cross-artifact
binding be re-derived from the actual retained artifact, the proposed
`emit_activity_companion_or_refuse(record, *, path, safety)` signature had no
parameter through which it could ever receive the primary artifact's path —
so the re-derivation FU1 described was caller convention performed *before*
the call, not mechanical validation performed *by* the emission boundary
itself. FU2 redesigns the emission-boundary API so it receives the trusted
primary path directly and performs every re-derivation step internally (new
§10), fixes the resulting caller-supplied-path contradiction in §11.1, makes
the `SemanticTaskAttemptResult` disposition field and its construction
ordering explicit (§11.3, §12.1), and corrects a cosmetic defect in this
introduction (the FU1 authorization note was previously spliced into the
middle of this paragraph). See the FU2 changelog appended to §15.

**This revision also incorporates 5F3B-HARNESS-OBS1-DESIGN-FU3**, a further
narrow correction, closing two remaining gaps. **Finding 1:** FU2's own
pseudocode expanded `build_activity_companion_record(**facts, ...,
bound_primary_sha256=..., ...)`, but FU2's own adversarial tests deliberately
called the emitter with hostile `proposed_facts` carrying exactly those
binding keys — a shape that raises an uncontrolled Python duplicate-keyword
`TypeError` rather than a bounded refusal. FU3 closes this by giving
`proposed_facts` a strict, exactly-enumerated closed key set, checked and
refused *before* any `**`-expansion or builder call (new §10.2). **Finding
2:** the design never mechanically totalized what happens if companion
code — after the primary/attempt/refusal artifact is already sealed — raises
an ordinary, unexpected exception; nothing prevented such an exception from
propagating past the one genuine `SemanticTaskAttemptResult` construction.
FU3 adds an explicit failure-containment boundary (new §12.2) that catches
`Exception` (never `BaseException`) around the companion attempt only, maps
every expected failure to its existing bounded disposition, and adds exactly
one new catch-all disposition, `UNAVAILABLE_INTERNAL_ERROR`, for a genuinely
unexpected companion-only fault — carrying no exception text, repr,
traceback, or path. FU3 also corrects an overreaching §9.2 sentence. See the
FU3 changelog appended to §15.

**This revision also incorporates 5F3B-HARNESS-OBS1-DESIGN-FU4**, a final
narrow correction, closing two remaining gaps in FU3's own mechanism.
**Finding 1:** FU3's closed-key check (§10.2) validated `set(proposed_facts)`
— the live, caller-supplied `Mapping` — but canonicalization into `facts`
happened separately, later. A hostile `Mapping`/`dict` subclass can report
one key set to that first check and a different one (smuggling in
`bound_primary_sha256` or any other reserved key) to whatever
`json.dumps` actually walks during canonicalization — a time-of-check/
time-of-use gap the first check alone cannot close. FU4 fixes this by
re-checking the **canonical snapshot itself** — the genuine `dict`
`json.loads` produces — immediately before it is ever expanded, and by
stating explicitly that the original `proposed_facts` object is never read
again once canonicalization completes (revised §10.2/§10.3). **Finding 2:**
FU3's containment boundary caught `FileNotFoundError`/`OSError` around the
**entire** companion attempt, which would misclassify an unrelated,
later companion-write failure (permission denied, out of space, …) as
"the primary is missing," purely because both happen to be `OSError`
subclasses. FU4 fixes this by normalizing primary-read failures into one
dedicated, single-origin exception, `PrimaryArtifactUnavailableError`, at
the exact point the primary is read — and removing every broad
`OSError`/`FileNotFoundError` clause from the outer boundary, so a later
write failure has nothing type-specific to fall into and reaches the
generic catch-all instead (revised §12.2/§12.3). See the FU4 changelog
appended to §15.

---

## 0. Status block

```text
5F3B-HARNESS-OBS1     DESIGN, FU1 REVISION — NOT IMPLEMENTED

Q1 / Candidate A / qwen3-coder-next      NOT_QUALIFIED   (frozen)
Q2 / Candidate B / minimax-m2.7          NOT_QUALIFIED   (frozen)
Q3 / Candidate C / qwen3.6-27b           NOT_QUALIFIED   (frozen)
5F3B-HARNESS-ATTR1                       ACCEPTED        (frozen)

QUALIFICATION_POLICY_REVISION            r1              UNCHANGED by this design
records.RECORD_VERSION                   .v2             UNCHANGED by this design

Frozen four semantic ports                               UNCHANGED (names, signatures, count)
TaskAdapterBundle                                          UNCHANGED (member count and names)
SemanticGateName / POST_PROMPT_GATES / CLOSURE_GATES       UNCHANGED
gate_statuses / failed_gate / *FailureCode enums           UNCHANGED
_authorized_facts_fingerprint                              UNCHANGED
```

This design proposes a **new, separate, non-scoring companion artifact**. It
proposes **no change whatsoever** to the primary qualification record, to the
attempt record, to the refusal record, to lineage, to the hard bar, to
ranking, to classification, or to the qualification policy revision. FU1 adds
one further constraint the original draft violated: it also proposes no
change to the four-port semantic contract, to `TaskAdapterBundle`'s member
set, or to the frozen gate topology. What it does require — disclosed
explicitly, not hidden — is one minimal, additive widening of a single
existing **value-object return shape** (`SemanticTurnObservation`), justified
in §4 as mechanically unavoidable given a separate, absolute, tested
invariant: the live adapter's candidate-blindness.

---

## 1. Exact sources inspected

Sources inspected for the original OBS1 draft (§1 of that draft) are carried
forward unchanged and not repeated in full here except where FU1 adds detail.
New sources read for this FU1 pass:

| Source | What was established from it |
|---|---|
| `qualification/semantic_session.py:494-560` | `SemanticTurnObservation` is `@dataclass(frozen=True)` with exactly three real fields (`runtime_session_id`, `turn_outcome`, `agent_end_observed`) and three derived properties (`agent_settled`, `deadline_reached`, `observation_failed`); `require_turn_matches_request` does an **exact-type** check (`type(observation) is not SemanticTurnObservation`), which a same-class field addition still satisfies |
| `qualification/semantic_session.py:560-565` | `BrokerActivityObservation` is likewise `@dataclass(frozen=True)` |
| `qualification/semantic_live_adapters.py:640-693` | `dispatch_semantic_prompt`'s exact body: `baseline = _DispatchBaseline.capture(supervisor)` runs **before** `supervisor.send_command(...)` (the prompt write) — confirms the baseline is genuinely pre-dispatch, not merely asserted to be |
| `qualification/semantic_live_adapters.py:275-276` | `_DispatchBaseline` is `@dataclass(frozen=True)`, module-private (leading underscore), **not** part of the port/bundle public contract — safe to extend with one more field without touching any frozen port surface |
| `qualification/semantic_live_adapters.py:849-869` (`observe_semantic_turn`'s tail, previously read) | the port's return is constructed as the very last statement after `transport.turn_observed = True`, immediately after the wait for settlement/deadline resolves — the natural, minimal-latency point to also read `supervisor.activity` |
| `experiments/pi_external_runtime_ar2/ar2/supervisor.py:330-367` (`_wait`, `await_settled`) | `_wait`'s loop calls `self._drain()` **before** every `satisfied()` check, including the one that resolves `await_settled`; `_drain()` absorbs everything the reader has buffered via `records_since(self._consumed)`. This is the mechanical half of the settled-stream completeness proof (§5.3) |
| `experiments/pi_external_runtime_ar2/ar2/capability.py:568-670` (`ConsumedBudgets`, `RunState`) | `RunState`'s edit-acceptance path increments `self.consumed.edit_operations += 1` unconditionally per accepted edit, and appends to `self.mutated_paths` only `if relative_path not in self.mutated_paths` (deduplicating) — **in the same code path**. This proves `len(mutated_paths) <= edit_operations`, a real invariant among broker counts (§6.2) |

---

## 2. Why the primary record is NOT changed — the mechanical proof

Unchanged from the original draft. Reproduced for completeness, since it
remains the load-bearing justification for the whole companion architecture.

1. `qualification/lineage.py:60` — `from .records import RECORD_KIND, RECORD_VERSION`.
2. `qualification/lineage.py:117` — `if record.get("record_version") != RECORD_VERSION: raise LineageBindingError(...)`,
   inside `_require_run_record_shape`, called by both `_read_and_verify_old_record`
   and `_read_and_verify_replacement_record`.
3. `tests/test_live1_c4_policy_binding.py:851-858` —
   `test_lineage_reads_the_record_version_symbol_rather_than_a_stale_literal`
   asserts `"pi-implementer-qualification" not in source` and that the import
   line is present, so lineage is *required by test* to follow the current
   constant, never a hand-pinned literal.

A bump to `pi-implementer-qualification.v3` would make the nine already-emitted
`.v2` files in `results/` begin raising `LineageBindingError` on every lineage
read, and the adjacent test documents that a compatibility shim is
deliberately absent. **Conclusion, unchanged: the companion architecture is
required, not merely preferred.** `pi-implementer-qualification.v2` stays
byte-identical in meaning and shape. There is no `.v3`.

---

## 3. Chosen artifact topology

Unchanged from the original draft.

```text
results/
  A_IQ-1.json            pi-implementer-qualification.v2       PRIMARY   (frozen, unchanged)
  A_IQ-1.activity.json   pi-implementer-qualification-activity.v1
                                                                COMPANION (new, non-scoring)
```

```text
PRIMARY (or ATTEMPT, or REFUSAL) ARTIFACT
    authority: scoring, hard bar, run validity, classification, Git truth
    knows nothing about the companion            <-- one-directional, no cycle
          ^
          | bound by: emitted-bytes SHA-256 + filename + identity tuple
          |
COMPANION ARTIFACT
    authority: NONE. observational provenance only.
```

Exactly **one** companion per invoked task attempt, at most. Never a
sweep-level artifact. Never a second raw JSON writer — it goes through
`qualification.safety.emit_evidence_or_refuse`, unmodified.

```python
ACTIVITY_RECORD_VERSION = "pi-implementer-qualification-activity.v1"   # in qualification/__init__.py
ACTIVITY_RECORD_KIND    = "qualification runtime activity companion"   # in the new module
```

The kind string is deliberately unequal to `records.RECORD_KIND`, to
`ATTEMPT_RECORD_KIND`, and to `"artifact emission refusal"`, so
`lineage._require_run_record_shape` already rejects a companion handed where a
run record was claimed — with no edit to `lineage.py`. `ACTIVITY_RECORD_VERSION`
is an independent lineage; it may be bumped later with zero effect on
`RECORD_VERSION`, lineage binding, or the nine frozen Q1/Q2/Q3 artifacts.

---

## 4. Finding 1 resolved — capture without a fifth port or a bundle member

### 4.1 The adversarial elimination, stated in full

The frozen surface has exactly four semantic ports (`dispatch_semantic_prompt`,
`observe_semantic_turn`, `collect_broker_activity`,
`collect_final_report_claims`), and `TaskAdapterBundle` carries exactly those
four callables plus the non-secret-gate/route-checker/shutdown members already
accepted. `LiveSemanticAdapters.__init__` accepts **exactly** `task` and
`environ_reader` — no `candidate`, no `model`, no `model_id`. This
candidate-blindness is not incidental: it is a documented, tested invariant
("no `candidate`/`model`/`model_id`/`provider`/… parameter exists anywhere on
it"), enforced at construction, and is the mechanism that keeps the live
adapter's behavior identical across candidates.

The companion artifact needs two things that live on *opposite sides* of that
boundary:

- **runtime tool-call facts**, which exist only inside the adapter's private
  `_LiveSemanticTransport.supervisor.activity` — the controller never receives
  a supervisor or an activity object, only session-id-shaped observation
  values returned by the four ports;
- **candidate identity and filename authority**, which the adapter must
  *never* hold (candidate-blindness), and which live only in
  `semantic_sweep.run_primary_sweep`'s per-task loop and the controller's own
  `candidate` parameter.

Four mechanisms were considered and eliminated before adopting the one below:

1. **A fifth port** (`collect_runtime_tool_activity(session)`), as the
   original draft proposed. **Rejected** — explicitly forbidden by this FU.
2. **A new `TaskAdapterBundle` member** carrying a retrieval callable.
   **Rejected** — explicitly forbidden by this FU.
3. **A script-level side-channel dict**, populated by `run_semantic_sweep_live.py`'s
   `build_adapters` closure as a side effect, read back after
   `run_primary_sweep` returns. **Rejected** — its lifetime spans multiple
   task attempts within one process invocation, which is exactly the shape of
   the explicitly forbidden "process-global cross-attempt registry"; it would
   also contradict the script's own documented claim that it "sequences
   nothing itself beyond resolving two trusted executables, assembling a
   fresh adapter bundle per task, and calling `run_primary_sweep` exactly
   once."
4. **Widening `BrokerActivityObservation`** (the `collect_broker_activity`
   port's return) to also carry tool-call facts. **Rejected** on modeling
   grounds, not authority grounds: it would blur the `broker_recorded_*` and
   `runtime_reported_*` trust namespaces this design (and ATTR1's own
   attribution question) depend on keeping distinct, and `collect_broker_activity`
   is not the port that already reads `supervisor.activity` for its own
   purpose — `observe_semantic_turn` is.

### 4.2 Adopted mechanism: widen `SemanticTurnObservation`, once, additively

`observe_semantic_turn`'s existing implementation already reads
`supervisor.activity` for its own return value (`agent_end_observed =
supervisor.activity.agent_end_count > 0`), at the exact point — immediately
after the wait for settlement/deadline resolves — that is temporally correct
for a tool-activity snapshot too. The adopted mechanism adds **one new,
optional field** to that port's return type:

```python
@dataclass(frozen=True)
class SemanticTurnObservation:
    runtime_session_id: str
    turn_outcome: SemanticTurnOutcome
    agent_end_observed: bool = False
    tool_activity: "RuntimeToolActivitySnapshot | None" = None   # NEW, FU1
```

`observe_semantic_turn`'s implementation projects the snapshot (§5) and passes
it in this same, single, already-existing return statement. **No new port. No
new `TaskAdapterBundle` member. No new call the controller must make.** The
controller already receives and retains `turn_observation` as a local variable
across the remainder of `run_semantic_task_attempt` (it already reads
`turn_observation.agent_settled` for classification), so it already has
everything needed to build the companion without any new accessor.

**This is not claimed as a zero-touch change, and Finding 5 explicitly asks
that such touches never be hidden under implementation detail — so it is
named here precisely.** The four port **callables** (names, parameter lists,
count, and `TaskAdapterBundle`'s member set) are unchanged. What changes is
the **shape of one value object** one of those ports already returns — an
additive field with a default, read by nothing in the hard bar, ranking,
classification, or fingerprint today, and consumed only by the new,
non-scoring companion-building step. See §10 for the itemized "what actually
changes" table, and §4.3 for why this is not, in this design's judgment, the
kind of amendment Finding 1 was written to prevent.

### 4.3 Why this does not trigger "FROZEN FOUR-PORT CONTRACT AMENDMENT REQUIRED"

Finding 1's own text names two specific protected surfaces — "the four-port
semantic contract" and "the frozen `TaskAdapterBundle` contract" — and defines
the escape hatch as triggering "if preserving the four-port contract is
mechanically impossible." Both of those exact surfaces **are** preserved: the
same four callables exist, with the same names and the same parameter shapes,
and `TaskAdapterBundle` gains no member. What is touched is a narrower,
different kind of thing — the return **shape** of one port — which Finding 1's
own adversarial checklist (5th port / bundle member / caller-visible mutable
state / process-global registry / new authority token / candidate-specific
behavior) does not list. Given the candidate-blindness invariant is absolute
and the tool-activity data structurally cannot cross the adapter boundary any
other way without violating one of those six explicitly-forbidden things
(§4.1), this design's judgment is that the value-object widening is the
correct exercise of the "implementation-shape discretion" the FU grants, not a
silent contract amendment. It is reported, not hidden, in §10's surface table.

---

## 5. Finding 3 resolved — per-dispatch correlation for every retained count

### 5.1 Event-count totals: `post_dispatch_count - dispatch_baseline_count`

`_DispatchBaseline.capture(supervisor)` already runs, and is already stored on
`transport.baseline`, **before** `supervisor.send_command(...)` writes the one
authorized prompt (`semantic_live_adapters.py:666-668`). Its existing
`agent_loop_event_counts` field already snapshots
`activity.event_type_counts.get(kind, 0)` for both `tool_execution_start` and
`tool_execution_end` (they are members of `_AGENT_LOOP_EVENT_TYPES`) at that
pre-dispatch instant.

The retained totals are therefore defined, exactly, as:

```text
runtime_reported_tool_execution_start_events =
    activity.event_type_counts.get("tool_execution_start", 0)
    - baseline.agent_loop_event_counts["tool_execution_start"]

runtime_reported_tool_execution_end_events =
    activity.event_type_counts.get("tool_execution_end", 0)
    - baseline.agent_loop_event_counts["tool_execution_end"]
```

read at the post-wait point inside `observe_semantic_turn` (§4.2), using the
`baseline` this same transport already stored at dispatch time. This is the
identical delta-from-baseline mechanism `_AGENT_LOOP_EVENT_TYPES` already uses
elsewhere in this module to prove agent-loop activity resulted from *this*
dispatch — no new correlation policy is introduced, only its application to
two counts already inside the existing baseline.

### 5.2 Tool-call entries: extend `_DispatchBaseline`, project only new keys

`_DispatchBaseline` has no field for `activity.tool_calls` today — the FU's
own finding. Per-tool-name absolute counts (`distinct_tool_call_ids`,
`aido_read_*`, `aido_edit_*`, `unexpected_tool_*`) cannot be correlated to
*this* dispatch merely by delta-of-count, because `tool_calls` is a dict keyed
by call id, not a monotonic counter — a key present before dispatch would
silently persist and be miscounted as this attempt's own activity if only
`len()` were diffed.

**Adopted: option 1 from Finding 3 — mechanical pre-dispatch snapshotting,
not a prose assumption.** `_DispatchBaseline` gains one new field:

```python
@dataclass(frozen=True)
class _DispatchBaseline:
    records_ingested: int
    agent_loop_event_counts: dict[str, int]
    unmatched_response_ids: int
    agent_end_count: int
    settled: bool
    pre_dispatch_tool_call_ids: frozenset[str]     # NEW, FU1
```

captured in the same `capture(supervisor)` static method, as
`frozenset(supervisor.activity.tool_calls.keys())`, at the same pre-send
instant as every other baseline field. The tool-activity projection then
includes **only** entries whose key is *not* in
`baseline.pre_dispatch_tool_call_ids`:

```text
post_dispatch_entries = {
    call_id: entry
    for call_id, entry in supervisor.activity.tool_calls.items()
    if call_id not in baseline.pre_dispatch_tool_call_ids
}
```

This is a real projection, not an assumed-empty baseline: had a prior task
attempt (impossible today, since one adapter instance owns exactly one
transport and one supervisor, refused on a second `launch_runtime` call) or
any other pre-dispatch source left entries in `tool_calls`, they would be
excluded mechanically, not by relying on the invariant holding.

`_DispatchBaseline` is module-private (`semantic_live_adapters.py:275-276`,
leading underscore) and is not part of the port/bundle public contract, so
this extension touches no frozen surface named in Finding 1.

### 5.3 Settled-stream completeness proof, stated in two parts

Finding 3 requires stating *precisely* why every `tool_execution_*` record has
already been absorbed by the time a snapshot is taken from the settled
stream. The proof has two independent halves, and they must not be
conflated:

**Part A — AIDO's own read completeness (mechanical, source-proven).**
`await_settled` calls `self._wait(deadline, lambda: self.activity.settled)`.
`_wait`'s loop body (`ar2/supervisor.py:330-346`) calls `self._drain()`
**before** every check of `satisfied()`, and `_drain()` absorbs every record
`records_since(self._consumed)` returns — i.e. everything the reader has
received from the child's stdout up to that instant. A single process's
stdout is one ordered byte stream; the reader consumes it strictly in the
order it was written, with no reordering possible. Therefore: **the instant
`_wait` returns because `self.activity.settled` became true, every record
that was written to stdout *before* the `agent_settled` record has already
been drained and absorbed into `activity`** — this is a fact about AIDO's own
reader discipline, not an assumption about Pi.

**Part B — Pi's own emission ordering (an assumed, untrusted protocol
property, exactly as `runtime_reported_*` is already labeled).** Part A only
proves completeness *up to whatever Pi wrote before the settled record*. That
every `tool_execution_start`/`tool_execution_end` event belonging to *this*
turn is written by Pi strictly before that turn's `agent_settled` record is a
property of Pi's own protocol behavior, which AIDO does not control and
cannot independently verify — it is exactly the kind of fact this package
already marks `UNTRUSTED CLAIM (the runtime's own account of itself)` in
`TRUST_NAMESPACES`. The companion inherits that same trust boundary: the
counts are retained under the `runtime_reported_*` prefix precisely because
their *completeness*, not merely their *content*, ultimately rests on trusting
Pi's own emission order for a settled turn.

**Consequence for the non-settled case.** The completeness argument (Part A)
applies to *whatever was absorbed by the time `_wait` returned*, regardless of
outcome — but Part B's assumption (Pi finishes emitting a turn's tool events
before ending it) is only meaningful when the turn actually reached
`agent_settled`. For `DEADLINE_REACHED` or any other non-settled
`turn_outcome`, AIDO stopped waiting before Pi (if it was ever going to)
signaled completion, so there is no basis to assume all of *this* turn's tool
events have been emitted yet. The companion therefore records which basis
applied:

```text
runtime_reported_tool_activity_capture_basis:
    "agent_settled"              completeness proof (Parts A+B) applies
    "wait_ended_before_settled"  best-effort only; counts may understate
                                 this turn's true tool activity
```

populated from `turn_outcome is SemanticTurnOutcome.SETTLED` at the exact
point the snapshot is taken, never guessed afterward.

### 5.4 Indeterminate dispatch and pre-prompt refusal: unavailable, never guessed

For `SEND_STATE_INDETERMINATE`, the controller never reaches
`observe_semantic_turn`/`TURN_COMPLETION` at all — the whole post-prompt flow
is skipped and control goes straight to `build_attempt_record`. `turn_observation`
is therefore `None` in that branch, exactly as it already is for
`turn_observation.agent_settled if turn_observation is not None else False` in
the existing classification call. The companion reuses that same `is not
None` check: when `turn_observation is None`,
`runtime_reported_tool_activity_available` is `false` and no count is
populated. This is not a special case added for the companion — it falls out
of control flow the controller already has, for the identical reason
(`semantic_prompts_sent` is unestablished, so nothing downstream of the
prompt write can be correlated to it).

For a pre-prompt refusal (`infrastructure_refusal`), post-prompt gates,
including `TURN_COMPLETION`, are never reached either, for the same reason:
no dispatch was ever attempted, so there is no baseline and no post-dispatch
read to diff. `runtime_reported_tool_activity_available` is `false` and
`broker_recorded_activity_available` is `false` (broker activity collection
is likewise a post-prompt-only gate).

---

## 6. Finding 4 resolved — the full cross-field invariant set

Every invariant below is either (a) proven from the frozen source read for
this design, or (b) explicitly declined with the reason no proof exists.
**Nothing is asserted that source does not prove**, per the FU's explicit
instruction not to invent equalities.

### 6.1 Availability implications

```text
runtime_reported_tool_activity_available == false
    => runtime_reported_tool_execution_start_events == 0
    => runtime_reported_tool_execution_end_events == 0
    => runtime_reported_distinct_tool_call_ids == 0
    => runtime_reported_aido_read_call_ids == 0
    => runtime_reported_aido_edit_call_ids == 0
    => runtime_reported_unexpected_tool_call_ids == 0
    => runtime_reported_unidentified_tool_call_id_seen == false
    => runtime_reported_tool_activity_capture_basis is absent/null

broker_recorded_activity_available == false
    => broker_recorded_read_operation_count == 0
    => broker_recorded_edit_operation_count == 0
    => broker_recorded_edited_path_count == 0
    => broker_recorded_refusal_count == 0
```

Both mirror an existing, already-proven rule: `BrokerActivityObservation.__post_init__`
already refuses "a failed call cannot also report observed activity"
(`call_succeeded=False` alongside nonzero counts). The companion's own
availability flags enforce the identical shape for both fact families,
independently re-derived at the companion's own gate (never inherited by
reference from the port's validation).

### 6.2 Ordering invariants, per category — proven from the observation model

When `runtime_reported_tool_activity_available` is `true`:

```text
aido_read_end_observed         <= aido_read_call_ids
aido_read_error_results        <= aido_read_end_observed
aido_edit_end_observed         <= aido_edit_call_ids
aido_edit_error_results        <= aido_edit_end_observed
unexpected_tool_end_observed   <= unexpected_tool_call_ids
unexpected_tool_error_results  <= unexpected_tool_end_observed
```

Proof: `*_call_ids` counts distinct keys assigned to a category by (possibly
overwritten) `toolName`; `*_end_observed` counts, among that same bucket, only
keys whose entry has `"isError" in entry` — a strict subset by construction,
since the bucket membership test runs first. `*_error_results` counts, among
`*_end_observed`'s keys, only those with `entry.get("isError") is True` — a
subset of "has the `isError` key at all". Each `<=` is therefore a partition
subset relationship, not an assumption.

**A necessary precision, not previously stated:** `*_call_ids` does **not**
mean "a start was observed for this call id." The absorb logic
(`setdefault` in both the start and end handlers) creates the dict entry on
whichever event arrives first; an entry created *only* by an end event (no
prior start, however that could arise) is indistinguishable, in the frozen
representation, from one that also had a start. The field names retained
avoid the word "start" for exactly this reason, and this document does not
claim otherwise.

### 6.3 The exact partition identity — proven, not assumed

```text
aido_read_call_ids + aido_edit_call_ids + unexpected_tool_call_ids
    == distinct_tool_call_ids
```

Proof: the projection (§5.2, §7) classifies **every** post-dispatch key into
**exactly one** of the three buckets by its (possibly last-overwritten)
`toolName`, with no key skipped and no key double-counted. This holds
regardless of the `toolCallId == ""` collapse (§6.4): the collapsed key is
still exactly one key, classified into exactly one bucket. This is an
**equality**, proven by the builder's own construction (a partition), and is
re-derived (by literally summing) at the emission-boundary gate rather than
merely asserted.

### 6.4 The `toolCallId == ""` collapse: bounded, one-directional, no invented equality

```text
distinct_tool_call_ids <= tool_execution_start_events + tool_execution_end_events
```

Proof: every distinct key in `tool_calls` was created by at least one
absorbed `tool_execution_start` or `tool_execution_end` record (the first
such record for that id triggers `setdefault`); each absorbed record
contributes exactly one to the sum on the right. So the number of
distinct keys can never exceed the number of absorbed records, though it can
be far smaller (duplicate starts/ends for one id, or many id-less calls
collapsing to the single key `""`).

**No equality, and no other inequality, is asserted** between the raw
per-event totals and the per-category breakdown. Declined explicitly, per
source:

- **`distinct_tool_call_ids` vs. `tool_execution_start_events` alone**: no
  relationship provable — an id could exist from an end-only record with zero
  observed starts for it, and duplicate starts for one id inflate the raw
  total without inflating the distinct count.
- **Any fixed ratio or equality across id-less collapses**: `unidentified_tool_call_id_seen`
  records the fact of a collapse (at least one call with a missing/blank id
  was observed) but does not — and cannot — reconstruct how many distinct
  calls collapsed into the shared `""` key, nor which of possibly several
  different tool names among them survived as the entry's final `toolName`.
  When this flag is `true`, a reader must treat the corresponding bucket
  count as a **potential undercount with unreliable category attribution**
  for the collapsed entry specifically — stated in the fixed `claim_scope`
  literal (§8), not left implicit.

### 6.5 Broker-count invariant — proven from `ar2/capability.py`

```text
broker_recorded_edited_path_count <= broker_recorded_edit_operation_count
```

Proof: `RunState`'s accepted-edit path (`ar2/capability.py:646-661`)
unconditionally increments `self.consumed.edit_operations` and appends to
`self.mutated_paths` **only if the path is not already present** — both in
the same code path, for the same accepted edit. Every distinct path in
`mutated_paths` therefore required at least one `edit_operations` increment
to be appended, and is appended at most once. No relationship is asserted
between `read_operation_count` and `edit_operation_count`, or between either
and `refusal_count` — nothing in `ar2/capability.py`'s read path, edit path,
or refusal-recording path ties those counters together, and none is invented
here.

### 6.6 Enforcement: builder and emission-boundary gate independently, no truthiness

Every invariant above is checked **twice** — once when the companion payload
is built, and again, independently, re-derived from the payload's own
declared facts at the emission boundary — mirroring
`records._require_valid_primary_payload`'s own "a caller convention to invoke
the builder first is not an authority invariant" discipline. Every count uses
`type(value) is int and not isinstance(value, bool)` before any range or
inequality check (`bool` never masquerades as a count), every count is
`>= 0` and bounded (§9.1), and violation refuses the companion — it is never
clamped, coerced, or silently corrected.

---

## 7. Facts explicitly prohibited from retention

Unchanged from the original draft.

```text
tool arguments                        model text / assistant content
tool result bodies                    reasoning content of any kind
raw event JSON                        raw exception text
raw broker diagnostic reason          a literal unexpected tool name
credential / API key                  base URL / endpoint host
pipe name / broker token              capability id
absolute workspace path               run id / broker session id / runtime session id
the attempt authority token           a Git changed-path list
final_assistant_text                  provider usage tokens
time-to-first-token / timing series   per-call chronology or ordering
```

**Literal unexpected tool names** collapse to the bounded category
`unexpected_tool` by exact, case-sensitive match against the frozen
`TOOL_ALLOWLIST = ("aido_read", "aido_edit")` value already duplicated in
`i2b_live_adapters.py:392`. No alias table, no normalization, no case
folding.

**The attempt authority token** (`_attempt_authority_token =
secrets.token_hex(16)`, `semantic_controller.py:3242`) is a live,
one-shot in-memory authority value gating `EvidenceEmission`/
`_AttemptIdentityProvenance` minting. It is never persisted into any
artifact, including this one — see §11, Option C, rejected.

**Ingestion already helps, but is not the guarantee.** `ar2/protocol.py` drops
reasoning at ingestion, before the supervisor absorbs anything, and the two
`tool_execution_*` handlers read only `toolCallId`, `toolName` and `isError` —
never `arguments`, never `result`. That is a welcome second layer, not the
design's guarantee: the guarantee is a closed schema of exact `bool`s and
exact `int`s plus fixed literals, with no free-text field for any of the
above to occupy even if it were available.

---

## 8. The retained field set (revised: capture-basis field added)

```text
--- header (fixed AIDO metadata; caller may not supply) ----------------------
experiment                          "pi_implementer_qualification"
record_version                      "pi-implementer-qualification-activity.v1"
record_kind                         "qualification runtime activity companion"
qualification_policy_revision       r1  (binding only; see Sec. 12.1)
is_review_packet                    false
reviewer_invoked                    false
scoring_authority                   false        <- exact bool, always false
claim_scope                         fixed literal (below)

--- identity (from the controller's own trusted locals) ---------------------
candidate                           "A" | "B" | "C"
model_id                            the CANDIDATE_MODEL_IDS-paired id
task_id                             "IQ-1" | "IQ-2" | "IQ-3" | "IQ-4T"
task_revision                       e.g. "IQ-1@57c89e4c13596723"

--- cross-artifact binding (Sec. 10, FU2) -------------------------------------
bound_primary_filename              basename only, RE-DERIVED from the trusted
                                     path by the emission boundary itself, never
                                     accepted as a caller claim (Sec. 10.2)
bound_primary_sha256                computed by RE-READING the emitted bytes at
                                     the trusted path, by the emission boundary
                                     itself (Sec. 10.2)
bound_primary_record_kind           parsed FROM THE FILE by the emission
                                     boundary itself; one of exactly three
bound_primary_identity_cross_check_performed
                                     exact bool. true for a run/attempt-record
                                     binding (identity was compared against the
                                     file); false for a refusal-record binding
                                     (Sec. 10.4) — mechanical, never inferred
                                     by a reader from `bound_primary_record_kind`
                                     alone

--- runtime tool-call observation (untrusted-claim namespace) ----------------
runtime_reported_tool_activity_available            exact bool
runtime_reported_tool_activity_capture_basis        "agent_settled" |
                                                     "wait_ended_before_settled" |
                                                     null (iff unavailable)
runtime_reported_tool_execution_start_events        int, NOT name-attributable
runtime_reported_tool_execution_end_events          int, NOT name-attributable
runtime_reported_distinct_tool_call_ids             int
runtime_reported_unidentified_tool_call_id_seen     exact bool  (the "" collapse)
runtime_reported_aido_read_call_ids                 int
runtime_reported_aido_read_end_observed             int
runtime_reported_aido_read_error_results            int
runtime_reported_aido_edit_call_ids                 int
runtime_reported_aido_edit_end_observed             int
runtime_reported_aido_edit_error_results            int
runtime_reported_unexpected_tool_call_ids           int
runtime_reported_unexpected_tool_end_observed       int
runtime_reported_unexpected_tool_error_results      int

--- broker observation (AIDO-authored, diagnostic only) ---------------------
broker_recorded_activity_available                exact bool
broker_recorded_read_operation_count              int, 0..32
broker_recorded_edit_operation_count              int, 0..16
broker_recorded_edited_path_count                 int, 0..16   (COUNT ONLY)
broker_recorded_refusal_count                     int, 0..256

--- trust namespaces (the same three-way map the primary already declares) ---
trust_namespaces                    exact declared mapping
```

`*_call_ids` fields are deliberately not named `*_start_count`: §6.2
establishes precisely why a start-specific count cannot be claimed.

Fixed `claim_scope` literal (extended from the original draft to name the
capture-basis and collapse-undercount facts explicitly):

> This artifact is OBSERVATIONAL PROVENANCE ONLY. It carries no scoring
> authority, no hard-bar input, no run-validity input, and no classification
> input. A tool call observed here is a request the runtime reported; it is
> NOT evidence that a file changed. Repository truth is Git-observed and
> lives only in the bound primary artifact. Tool-call counts are the
> runtime's own account of itself. When
> `runtime_reported_tool_activity_capture_basis` is
> `"wait_ended_before_settled"`, these counts are best-effort only and may
> understate this turn's true tool activity. When
> `runtime_reported_unidentified_tool_call_id_seen` is true, the per-category
> breakdown may undercount distinct calls and misattribute the category of
> the collapsed entry. Absence of this artifact is NOT evidence that no tool
> call occurred. Controlled invocation is not sandboxed execution.

Field-name prefixes remain load-bearing per the package's existing
`TRUST_NAMESPACES` contract: `runtime_reported_*` is an untrusted claim,
`broker_recorded_*` is AIDO-authored and diagnostic-only, never repository
truth. No field carries `orchestrator_observed_*`, because nothing here is
repository authority.

### 8.1 The required attribution distinctions, satisfied

Unchanged from the original draft:

| Required distinction | Mechanically satisfied by |
|---|---|
| no observed model tool call | `distinct_tool_call_ids == 0` **and** both `tool_execution_*_events == 0` |
| `aido_read` requested by the model | `runtime_reported_aido_read_call_ids > 0` |
| `aido_edit` requested by the model | `runtime_reported_aido_edit_call_ids > 0` |
| tool execution reported an error before broker success | per-category `*_error_results > 0` alongside `broker_recorded_*_count` |
| broker accepted read operations | `broker_recorded_read_operation_count > 0` |
| broker accepted edit operations | `broker_recorded_edit_operation_count > 0` |
| broker recorded refusals | `broker_recorded_refusal_count > 0` |
| filesystem mutation observed by Git | **the bound primary's `scope_result.observed_changed_paths`** — never this artifact |

Git truth is preserved by omission, mechanically: the companion carries no
Git field at all, so it structurally cannot express "mutation occurred."

---

## 9. Counts: caps and Finding "count-cap disposition" resolved

### 9.1 Broker counts: reuse existing frozen caps, duplicated as values

Unchanged: `broker_recorded_read_operation_count` (0..32),
`broker_recorded_edit_operation_count` (0..16), `broker_recorded_edited_path_count`
(0..16), `broker_recorded_refusal_count` (0..256) reuse
`semantic_session.py`'s private `_MAX_READ_OPERATIONS` /
`_MAX_EDIT_OPERATIONS` / `_MAX_REFUSAL_EVENTS` **values**, duplicated as
literals in the new module per the package's own established precedent
(`TOOL_ALLOWLIST`'s "duplicated as a VALUE — never imported" convention,
`i2b_live_adapters.py:388-393`), with an offline test asserting the two agree.

### 9.2 Runtime tool-activity counts: derived from an existing frozen bound, not a new magic number

The original draft's `MAX_ACTIVITY_TOOL_COUNT = 4096` is **withdrawn** as an
arbitrary new policy value. Adopted instead:

```python
from ar2.supervisor import RunBounds

MAX_ACTIVITY_TOOL_COUNT = RunBounds().max_events   # 200_000 today; imported, not duplicated
```

`RunBounds.max_events` is the run's own existing, frozen, already-enforced
cap on the **total** number of stream records absorbed in one run
(`RUNTIME_EVENT_CAP_EXCEEDED` is a real, already-handled terminal outcome if
it is exceeded). Since `tool_execution_start`/`tool_execution_end` events are
a strict subset of all absorbed records, and `distinct_tool_call_ids` can
never exceed the sum of those two event counts (§6.4), the proven property
is: **a valid bounded run cannot exceed the frozen `max_events` bound
without triggering the existing `RUNTIME_EVENT_CAP_EXCEEDED` failure** — it
is a real ceiling derived from an already-accepted frozen policy, not an
independent invented one. (FU3 correction: the earlier wording — "cannot
reach this bound" — overreached. This document does not inspect the exact
`>` vs. `>=` comparison the cap-check itself uses and does not claim a
genuinely correlated count can never equal `max_events`; it claims only the
narrower, source-proven inequality stated above, which is what actually
makes `MAX_ACTIVITY_TOOL_COUNT` a non-arbitrary ceiling.) `RunBounds` is
already imported in `semantic_live_adapters.py` (`_DEFAULT_BOUNDS =
RunBounds()`), so this is a real import of a public type, not a
private-name duplication.

Exceeding it still refuses the companion outright — never clamped — and still
never touches the qualification verdict (§12).

---

## 10. Finding 5 resolved (FU2) — the emission boundary itself re-derives binding, not the caller

**What FU1 got wrong, stated precisely.** FU1's §10 correctly *argued* that
binding facts must be re-derived from the actual retained bytes, but the
function it actually specified —
`emit_activity_companion_or_refuse(record, *, path, safety)` — has no
parameter carrying the primary's path at all. `path` there names the
**companion's own output destination**, not the primary. A function with no
access to the primary cannot open it, hash it, or parse it; every
re-derivation FU1 described (`primary_bytes = _read_file_bytes(evidence_path)`,
`primary_sha256 = hashlib.sha256(...)`, …) was therefore code FU1 placed in
the **caller**, one scope above the emission boundary, using a local variable
the boundary itself never sees. That is caller convention wearing the
appearance of mechanical validation: a caller who built the payload some
other way, or who called the emission function directly (as every regression
in §17 that "bypasses the builder" must be able to do), would face a function
that has nothing to check the caller's claims against. This is the exact
contradiction independent review identified, and it is closed here by moving
the primary's path — not the caller's pre-computed digest/filename/kind —
across the boundary.

### 10.1 The corrected authority shape

```python
def emit_activity_companion_or_refuse(
    proposed_facts: Mapping[str, Any],   # ONLY the companion's own observed
                                          # facts: tool-activity counts, broker
                                          # counts, availability flags, capture
                                          # basis — NEVER a trusted source for
                                          # bound_primary_* or an output path
    *,
    bound_primary_path: str,             # THE trusted, AIDO-owned path this
                                          # SAME attempt just used to emit the
                                          # primary/attempt/refusal artifact
    identity: "AttemptIdentity",         # this attempt's trusted (candidate,
                                          # model_id, task_id, task_revision)
                                          # tuple — the SAME locals already
                                          # used to build the primary's record
    safety: ArtifactSafetyContext,
) -> dict[str, Any]:
    ...
```

The exact helper name and internal decomposition are implementation
discretion, exactly as the authorizing prompt states. The invariant that is
**not** discretionary: **the function receives the actual, AIDO-owned
retained-artifact path, and independently derives every cross-artifact
binding fact from it — nothing about the binding is ever accepted as a
parameter the caller computed.** Concretely, `record`/`path` are **withdrawn**
from the emission boundary's signature; `bound_primary_path` and `identity`
replace them as the only new inputs, and there is no `activity_path`
parameter of any kind (§10.2).

`bound_primary_path` is not a new authority object: at the one real call
site, it is exactly the same `evidence_path` local
`run_semantic_task_attempt` already computed and already passed to
`emit_or_refuse`/`emit_attempt_or_refuse` for the primary, one statement
earlier, in the same function invocation. `identity` is likewise not new
authority: it is the same `candidate`/`model_id`/`task.task_id`/
`task.task_revision` locals already used to build the primary record. FU2
does not introduce a new trusted value anywhere — it only moves two values
the caller already possessed from "used to compute claims before the call"
to "passed into the call, so the call can compute the claims itself."

### 10.2 `proposed_facts` is a strict closed key set (Finding 1, FU3)

**What FU2 got wrong, stated precisely.** FU2's own §10.2 pseudocode expanded
`build_activity_companion_record(**facts, ..., bound_primary_sha256=...,
bound_primary_filename=..., bound_primary_record_kind=..., ...)`. FU2's own
§17 adversarial regressions then deliberately called the emitter with a
hostile `proposed_facts` that *also* declared `bound_primary_sha256` (or
`bound_primary_filename`, or `bound_primary_record_kind`) — precisely to
prove the recomputed value wins. But Python raises `TypeError: … got multiple
values for keyword argument 'bound_primary_sha256'` the moment a dict already
containing that key is expanded with `**facts` alongside an explicit
`bound_primary_sha256=...` keyword — **before** `build_activity_companion_record`
or `_require_valid_activity_payload` ever run a single check. The bug was
real: an uncontrolled Python exception, not this design's bounded refusal
machinery, would have been what "closed" that adversarial test.

**The fix is a closed namespace, checked first, not a smarter merge.**
`proposed_facts` is given a strict, exactly-enumerated key set — **only** the
observational runtime/broker facts a caller ever needs to supply — checked
for **exact set equality** (the identical `_REQUIRED_...TOP_LEVEL_KEYS`
idiom `records.py` already uses for the primary's own closed key set).

**FU4 correction: checking the live `Mapping` once is not enough.** The
sequence below originally checked `set(proposed_facts)` at step (0) and then,
separately, canonicalized `proposed_facts` into `facts` at step (9) —
**two different reads of the same caller-supplied object, at two different
points in time.** A hostile `Mapping`/`dict` subclass can legitimately report
one key set to `set(...)` (a `__iter__`-driven enumeration) and a *different*
key set — one that smuggles in `bound_primary_sha256` or any other reserved
name — to whatever `json.dumps` actually walks during canonicalization (which
may call `.items()`, `.keys()`, or `__getitem__` in a different pattern). A
check on the object performed at step (0) proves nothing about what
canonicalization produces at step (9). That gap is exactly what FU4 closes.

**FU4's two-check sequence, in the order the authorizing prompt specifies:**

1. **Preliminary, non-authoritative.** `_require_closed_facts_keys(set(proposed_facts),
   context="proposed_facts")` still runs first, as the **very first operation** inside
   `emit_activity_companion_or_refuse`, before `bound_primary_path` is even
   opened. Its only purpose is a cheap fail-fast for the overwhelmingly
   common case — an ordinary, well-behaved `dict` — so an obviously invalid
   `proposed_facts` refuses before any filesystem I/O. **Passing this check
   proves nothing about the canonical snapshot** and is never treated as
   authority.
2. **Canonicalize.** `proposed_facts` — whatever object the caller actually
   passed, regardless of how it behaves under repeated introspection — is
   collapsed into `facts`, ONE concrete, ordinary `dict`, via the companion
   module's own `json.dumps`/`json.loads` round trip (§10.3, step (9a)).
   **From the line this completes onward, `proposed_facts` — the original
   parameter — is never read again by any code in this function or anything
   it calls.** Only `facts` is used from here on.
3. **Re-check, authoritatively, on the canonical snapshot itself.** Exact-set
   equality is checked **again** — this is the check that actually matters —
   against `facts`, the plain `dict` `json.loads` produced. Because `facts`
   is a genuine `dict` built by parsing JSON text, repeated introspection of
   it cannot disagree with itself the way a hostile `Mapping` can: whatever
   the round trip served is exactly what this check inspects, and exactly
   what the builder consumes immediately afterward. A reserved or unknown
   key surviving into the canonical snapshot is refused here — `REFUSED_INVARIANT`
   — never a Python duplicate-keyword `TypeError` (§10.3, step (9b)).
4. **Only after step 3 passes** may `facts` be expanded (`**facts`) or
   passed to `build_activity_companion_record`.

**Canonicalization failure is not a new failure mode.** If
`proposed_facts`'s shape cannot be safely serialized at all (an unserializable
value, a pathological recursive structure), the companion module's own
canonicalization helper raises the **same** `ActivityRecordInvariantError`
step (3) raises — the smallest existing contract this design already has for
"the caller's facts were not an acceptable shape" — never a raw `TypeError`/
`ValueError`/`RecursionError`, and never any text describing what made the
value unserializable.

The original, single-check description below is retained for the parts that
are still accurate — the key SET this checks against, and why exact equality
(not "absence of reserved keys") is the right shape — but every place it
previously implied ONE check now means the TWO checks above.

The **very first operation** inside `emit_activity_companion_or_refuse` is
still the preliminary check, before `bound_primary_path` is even opened:

```python
#: The ENTIRE allowed input namespace for `proposed_facts`. Nothing else may
#: ever appear as a key, whether reserved (Sec. 8's header/identity/binding
#: fields — the emitter owns every one of those itself) or simply unknown
#: (a typo, a future field added to the wrong namespace).
_ALLOWED_PROPOSED_FACTS_KEYS: frozenset[str] = frozenset({
    "runtime_reported_tool_activity_available",
    "runtime_reported_tool_activity_capture_basis",
    "runtime_reported_tool_execution_start_events",
    "runtime_reported_tool_execution_end_events",
    "runtime_reported_distinct_tool_call_ids",
    "runtime_reported_unidentified_tool_call_id_seen",
    "runtime_reported_aido_read_call_ids",
    "runtime_reported_aido_read_end_observed",
    "runtime_reported_aido_read_error_results",
    "runtime_reported_aido_edit_call_ids",
    "runtime_reported_aido_edit_end_observed",
    "runtime_reported_aido_edit_error_results",
    "runtime_reported_unexpected_tool_call_ids",
    "runtime_reported_unexpected_tool_end_observed",
    "runtime_reported_unexpected_tool_error_results",
    "broker_recorded_activity_available",
    "broker_recorded_read_operation_count",
    "broker_recorded_edit_operation_count",
    "broker_recorded_edited_path_count",
    "broker_recorded_refusal_count",
})

def _require_closed_facts_keys(keys: "set[str] | frozenset[str]", *, context: str) -> None:
    """The ONE key-set check, called TWICE (Sec. 10.2 steps 1 and 3) with
    two different `keys` values and two different meanings -- preliminary
    (on `set(proposed_facts)`) and authoritative (on `set(facts)`, the
    canonical snapshot). Factored into one function so the two call sites
    can never drift into checking two different key sets.
    """
    if keys != _ALLOWED_PROPOSED_FACTS_KEYS:
        # ANY reserved header/identity/binding/path key, and ANY unknown key,
        # refuses here -- a bounded ActivityRecordInvariantError, never a
        # Python TypeError from a later **-expansion collision.
        raise ActivityRecordInvariantError(
            f"{context} must carry EXACTLY the declared observational fact "
            "keys -- no header, identity, binding, or path field may be "
            "supplied by the caller; the emitter owns and stamps every one "
            "of those itself. Nothing was written."
        )
```

Reserved names this refuses — at **both** call sites, before any expansion is
attempted — the complete list, exactly as enumerated in the authorizing
prompt: `experiment`, `record_kind`, `record_version`,
`qualification_policy_revision`, `is_review_packet`, `reviewer_invoked`,
`scoring_authority`, `claim_scope`, `candidate`, `model_id`, `task_id`,
`task_revision`, `bound_primary_filename`, `bound_primary_sha256`,
`bound_primary_record_kind`, `bound_primary_identity_cross_check_performed`,
`path`, `activity_path`, `bound_primary_path`, `run_validity`,
`scoring_eligible`, `autonomous_classification`,
`diagnostic_subclassification`, `gate_statuses`, `failed_gate` — plus any key
that is simply unrecognized (not merely "not reserved"). The check is
**exact-set equality**, not "absence of reserved keys": an equality check is
the only shape that also catches an unknown, non-reserved key (a typo, a
future field added to the wrong namespace) with the same bounded refusal,
rather than letting it ride along silently or crash some other way inside
the builder. Equality on the **preliminary** call (step 1) is a convenience,
not a guarantee; equality on the **authoritative** call (step 3, against the
canonical snapshot) is what the design actually relies on.

**The governing rule, stated as the authorizing prompt states it:** *the
caller supplies observational facts only; the emitter stamps every header,
identity, and binding field itself.* No caller is ever required to correctly
supply a binding claim the emitter already owns — because no caller is
ever *permitted* to supply one at all. This is strictly narrower, and
therefore strictly safer, than "accept a binding claim and detect that it
disagrees": the claim cannot be expressed in the first place, so there is
nothing for a later stage to get wrong.

### 10.3 The sequence, now genuinely internal to the emission boundary, with a canonical-snapshot recheck and source-specific primary-read normalization (FU4)

```python
def emit_activity_companion_or_refuse(proposed_facts, *, bound_primary_path, identity, safety):
    # (1) PRELIMINARY, NON-AUTHORITATIVE closed-key check on the RAW,
    # caller-supplied Mapping -- before bound_primary_path is even opened,
    # before any dict expansion, before any builder call. Fails fast for the
    # common case (an ordinary dict). Passing this proves NOTHING about what
    # canonicalization will later produce from a hostile Mapping (Sec. 10.2).
    _require_closed_facts_keys(set(proposed_facts), context="proposed_facts")

    # (2)-(3) re-read the actual emitted file and compute its digest ITSELF —
    # never accept either from proposed_facts or from any other caller input.
    # FU4: the read is wrapped HERE, at the exact primary-read operation, and
    # normalized into ONE dedicated, bounded exception -- never left as a
    # bare OSError/FileNotFoundError that an outer, broader except clause
    # would otherwise have to guess the origin of.
    try:
        primary_bytes = _read_file_bytes(bound_primary_path)
    except OSError:
        # Fixed message. No path, no errno, no raw OS diagnostic text.
        raise PrimaryArtifactUnavailableError(
            "the bound primary artifact could not be read"
        ) from None
    primary_sha256 = hashlib.sha256(primary_bytes).hexdigest()

    # (4)-(5) parse, and require one of exactly the three accepted kinds.
    # A file that does not parse as a JSON object, or whose record_kind is
    # none of the three, RAISES a distinct, bounded UnboundPrimaryError HERE
    # -- deliberately NOT folded into the general invariant gate below, and
    # deliberately a DIFFERENT type from PrimaryArtifactUnavailableError just
    # above, so the containment boundary (Sec. 12.2/12.3) can tell "the file
    # is not there/not readable" (UNAVAILABLE_NO_PRIMARY) apart from "the
    # file is there and readable, but its content is not a bindable primary"
    # (UNAVAILABLE_UNBOUND_PRIMARY) -- two different facts about two
    # different things, never merged by sharing an exception type.
    bound_record = _parse_json_object_or_raise(primary_bytes)   # UnboundPrimaryError on failure
    bound_kind = _require_known_kind_or_raise(bound_record)     # UnboundPrimaryError if none of the 3

    # (6) where the bound kind carries identity (run record, attempt record),
    # cross-check against THIS attempt's trusted identity parameter — never
    # against anything proposed_facts claims (proposed_facts cannot claim an
    # identity at all, per Sec. 10.2 -- it has no candidate/model_id/task_id/
    # task_revision key in its closed namespace).
    identity_cross_check_performed = bound_kind in (_RUN_RECORD_KIND, _ATTEMPT_RECORD_KIND)
    if identity_cross_check_performed:
        _require_identity_matches(bound_record, identity)     # refuse on any mismatch

    # (7) derive the sibling filename from the ACTUAL trusted path, never from
    # proposed_facts (which cannot carry one) and never from bound_record.
    bound_primary_filename = os.path.basename(bound_primary_path)

    # (8) derive the companion's OWN output path from bound_primary_path,
    # by the one fixed suffix rule (Sec. 11.1) — there is no parameter through
    # which a caller can supply an independent activity output path.
    activity_path = _derive_activity_path(bound_primary_path)

    # (9a) CANONICALIZE. Collapse `proposed_facts` -- whatever object the
    # caller actually passed, regardless of how it behaves under repeated
    # introspection -- into `facts`, ONE concrete, ordinary `dict`, via this
    # module's own json.dumps/json.loads round trip. A shape that cannot be
    # safely serialized at all raises the SAME ActivityRecordInvariantError
    # step (9b) raises -- never a raw TypeError/ValueError/RecursionError,
    # and never any text describing what made the value unserializable.
    #
    # FROM THIS LINE ON, `proposed_facts` -- the ORIGINAL parameter -- IS
    # NEVER READ AGAIN, by this function or by anything it calls. Every
    # remaining step below reads ONLY `facts`.
    facts = _canonicalize_activity_facts_or_refuse(proposed_facts)

    # (9b) THE AUTHORITY CHECK -- re-validated on the CANONICAL SNAPSHOT
    # itself, not on the live Mapping a hostile caller controls. `facts` is
    # now a genuine `dict` produced by `json.loads`, so its key set cannot
    # disagree with itself between this check and the `**facts` expansion
    # three lines below -- there is no live object left to lie twice. A
    # reserved or unknown key surviving canonicalization is refused HERE,
    # as ActivityRecordInvariantError -> REFUSED_INVARIANT, never as a
    # Python duplicate-keyword TypeError from the expansion that follows.
    _require_closed_facts_keys(set(facts), context="the canonical proposed_facts snapshot")

    # assemble the FULL payload: `facts` is now TWICE-VERIFIED (steps 1 and
    # 9b) to carry EXACTLY the 20 observational keys, and is the canonical
    # snapshot -- not the original, possibly-hostile `proposed_facts` -- so
    # there is no key-collision hazard left in this expansion. Every
    # header/identity/binding field is stamped here, by the function itself,
    # from values it alone computed above.
    payload = build_activity_companion_record(
        **facts,
        candidate=identity.candidate, model_id=identity.model_id,
        task_id=identity.task_id, task_revision=identity.task_revision,
        bound_primary_filename=bound_primary_filename,
        bound_primary_sha256=primary_sha256,
        bound_primary_record_kind=bound_kind,
        bound_primary_identity_cross_check_performed=identity_cross_check_performed,
    )

    # (10) an independent re-derivation gate over the FULLY ASSEMBLED payload
    # (Sec. 10.4) -- defense in depth against a payload that reached this
    # point some other way than through this function's own steps above.
    _require_valid_activity_payload(payload, bound_primary_path=bound_primary_path)

    # (11)-(12) scrub, then exclusive-create -- the SAME shared choke point,
    # unmodified. Any OSError raised BY THIS CALL (permission denied, out of
    # space, the destination's parent directory disappearing, ...) is a
    # LATER, companion-write-only failure, deliberately NOT wrapped into
    # PrimaryArtifactUnavailableError or any other primary-read-shaped
    # exception -- it propagates as an ordinary Exception and is classified
    # only by the OUTER containment boundary's generic clause (Sec. 12.2/
    # 12.3), never misattributed to the primary being missing.
    return emit_evidence_or_refuse(payload, path=activity_path, safety=safety)
```

No caller-supplied digest, filename, or record kind is ever authoritative,
and — after this fix — **none can even be expressed** through
`proposed_facts`: the closed-key check (now performed twice — steps 1 and
9b, with 9b binding on the canonical snapshot) refuses any such key
outright, so the recomputation in steps (2)-(8) has no forged value to ever
compete against for this function's one real caller. No arbitrary unrelated
file can be bound merely because its digest matches a caller's claim,
because the file that is opened, hashed, and parsed is **always** the one at
`bound_primary_path` — there is no second path anywhere in this function
through which a different file could be substituted.

### 10.4 Payload-declared binding facts: checked claims at the internal gate, never authority, never reachable through the public parameter

Two distinct layers now exist, and the adversarial property FU2 asked for
lives at the **second** one, not the first:

1. **The public boundary — `emit_activity_companion_or_refuse`'s
   `proposed_facts` parameter.** After §10.2's fix, this parameter
   structurally **cannot** carry `bound_primary_filename`/
   `bound_primary_sha256`/`bound_primary_record_kind`/any identity field at
   all — the closed-key check refuses before either value could ever be
   compared. There is nothing to forge here because there is nowhere to put
   a forgery.
2. **The internal re-derivation gate — `_require_valid_activity_payload(payload,
   bound_primary_path=...)`.** This function operates on the **fully
   assembled** payload dict (the shape that is actually scrubbed and
   written), which legitimately contains the three binding fields as part of
   its own schema — because they are real facts about the emitted companion.
   Called both at the tail of `build_activity_companion_record` and,
   independently, at `emit_activity_companion_or_refuse`'s own step (10) —
   the identical two-call discipline `records._require_valid_primary_payload`
   already establishes for the primary artifact. **This is where the
   authorizing prompt's "hostile hand-built record with internally
   self-consistent filename/digest/kind must still refuse" property is
   proven**: a hand-built full-payload dict, constructed directly and handed
   to `_require_valid_activity_payload` without ever going through
   `build_activity_companion_record` or `proposed_facts` at all (exactly the
   "test the consumption boundary directly without going through the
   canonical builder" instruction), is refused if its declared
   `bound_primary_sha256`/`bound_primary_filename`/`bound_primary_record_kind`
   disagree with what re-reading `bound_primary_path` actually produces —
   re-derived and compared, not trusted, exactly as `records.py`'s own
   `_require_exact_declared_str` re-checks its two fixed header fields at
   the primary's emission boundary rather than trusting the builder's
   output.

**Why this is a strictly stronger closure than FU2's, not merely a renamed
one.** FU2 closed the property by "detect a forged claim through
`proposed_facts` and refuse." FU3 closes it by making the forgery
**inexpressible** through the one supported public parameter, and keeps the
detect-and-refuse property alive only as defense-in-depth at an internal
gate a caller cannot reach without deliberately bypassing every documented
entry point. "Cannot be expressed" is a strictly stronger property than
"expressible but rejected," and §17's regressions (items 33+) are revised to
prove both layers separately rather than conflating them.

### 10.5 Refusal-record binding: no fabricated identity, stated mechanically

When `bound_kind` is the refusal kind (`safety.build_refusal_record` takes no
payload and declares no candidate/task identity), step (6) above sets
`identity_cross_check_performed = False` and performs no comparison —
**the companion never invents candidate/task identity from the refusal
artifact.** The companion's own `candidate`/`model_id`/`task_id`/
`task_revision` fields are still populated, but from `identity` — this
attempt's own trusted controller-local identity, the same value passed to
every other artifact this attempt produces — never from the bound file. The
new field `bound_primary_identity_cross_check_performed` (§8) makes this
mechanical for a reader: `false` means exactly "the bound file carried no
identity to check, so none was checked," never "the check passed silently."

### 10.6 This is the only remaining touch to Finding 5

No new authority object is introduced: `bound_primary_path` and `identity`
are the same two facts (a path, and an identity tuple) the caller already
held before FU1; FU2 only relocates *where* they are consumed — from the
caller's own scope into the emission boundary's own parameter list — so the
boundary can mechanically enforce what FU1 could previously only describe.
FU3's §10.2 closed-key fix adds no new authority either: it only narrows
`proposed_facts`'s own already-intended shape (observational facts only) into
a mechanically checked one, closing the exact spot where FU2's own binding
fields could otherwise collide with it.

---

## 11. Filename authority and emission ordering (gate topology preserved)

### 11.1 Filename (revised, FU2: derived inside the emission boundary, not by the caller)

`evidence_path` (the primary's path) is still derived exactly as before, in
`run_primary_sweep`'s per-task scope, by the same fixed rule:

```python
evidence_path = str(evidence_root / f"{candidate}_{task.task_id}.json")
```

**What FU2 changes:** the companion's own output path is **no longer**
computed by that same caller scope and handed in as a second, independent
parameter. §10.2's `_derive_activity_path(bound_primary_path)` runs **inside**
`emit_activity_companion_or_refuse`, applied to the *same*
`bound_primary_path` value the caller passed in for hashing/parsing:

```python
def _derive_activity_path(bound_primary_path: str) -> str:
    root, ext = os.path.splitext(bound_primary_path)
    if ext != ".json" or not os.path.basename(root) or root.endswith(".activity"):
        raise ActivityRecordInvariantError(
            "the bound primary artifact path is not the fixed retained-evidence "
            "'<name>.json' shape this companion's own destination is derived "
            "from, or is itself already a companion path. Nothing was written."
        )
    return f"{root}.activity.json"
```

> **ACCEPTED IMPLEMENTATION ERRATUM (5F3B-HARNESS-OBS1-IMPL).** An earlier
> revision of this section illustrated the rule with a bare
> `assert ext == ".json"`. **A bare `assert` must NOT be used as this
> invariant's authority**: `python -O` strips assertions, which would silently
> remove the path-shape check and let a non-`.json` `bound_primary_path`
> produce an arbitrary destination. The implementation uses explicit
> fail-closed validation raising the companion's own bounded
> `ActivityRecordInvariantError` (-> `REFUSED_INVARIANT`), so the invariant
> holds at every interpreter optimization level. The rule additionally refuses
> a path that is ALREADY a companion (`*.activity.json`), so a companion can
> never be bound as though it were a primary and produce a
> `*.activity.activity.json` sibling.

`emit_activity_companion_or_refuse` has **no `activity_path` parameter at
all** — there is no signature shape through which a caller could supply
`primary_path=X` and an independently chosen `activity_path=Y` where `Y` need
not be `X`'s fixed companion. The only path a caller ever supplies is
`bound_primary_path`; the companion's destination is a pure function of that
one value, computed by the callee, every time. No timestamp, no sequence
suffix, no caller override, no overwrite (`O_CREAT|O_EXCL`, unchanged, §17).

### 11.2 Finding 2 resolved — no new gate, no gate-topology change

The original draft's `RUNTIME_ACTIVITY_SNAPSHOT` post-prompt gate and its
terminal `RUNTIME_ACTIVITY_COMPANION` closure stage are **both withdrawn**.
There is no new `SemanticGateName` member, no new entry in
`POST_PROMPT_GATES` / `GATING_POST_PROMPT_GATES` / `NON_GATING_POST_PROMPT_GATES`
/ `CLOSURE_GATES`, no new `gate_statuses` key, no effect on `failed_gate`, no
new `SemanticFailureCode` or `CategoryBFailureCode` member, and no entry in
`_authorized_facts_fingerprint`.

This is possible, without weakening anything, because §4.2 already moved
tool-activity **capture** inside the existing, already-gated
`TURN_COMPLETION` step (it rides in `observe_semantic_turn`'s existing return
value), and §10 establishes that **companion emission** needs nothing beyond
values the controller already holds in scope after `EVIDENCE_SAFETY`
completes — `turn_observation`, `broker_activity` (to build the proposed
facts), and `evidence_path`/`candidate`/`model_id`/`task` (passed as
`bound_primary_path`/`identity` into the emission boundary, which does the
re-derivation itself, §10.1-§10.2). No gate is needed to make any of this
available; it is all ordinary local scope. The topology is therefore:

```text
… existing, unchanged POST_PROMPT_GATES …
    TURN_COMPLETION          <- observe_semantic_turn's return now ALSO carries
                                tool_activity (Sec. 4.2); gate semantics for
                                TURN_COMPLETION itself are UNCHANGED — pass/fail
                                still governed by turn_outcome exactly as today
    BROKER_ACTIVITY
    REPOSITORY_OBSERVATION
    VERIFICATION
    FINAL_REPORT_CLAIMS
… existing, unchanged CLOSURE_GATES …
    RUNTIME_TEARDOWN
    BROKER_SHUTDOWN
    GENERATED_CONFIG_CLEANUP
    SEMANTIC_WORKSPACE_REMOVAL
    EVIDENCE_SAFETY          -> the ONE primary/attempt/refusal artifact, unchanged
--- entirely OUTSIDE the gate system, after everything above ---
    companion build + bind + emit, using ONLY already-in-scope local
    variables; no gate name, no gate_statuses entry, no failed_gate effect,
    no fingerprint entry
```

A companion build/bind/emit failure is recorded on the in-memory
`SemanticTaskAttemptResult` as a plain, non-gating, non-fingerprinted field
(§12) — never as a gate outcome, never as a `SemanticFailureCode`, and never
capable of setting `failed_gate`.

The `activity.tool_calls`-mutation hazard the original draft's freeze-timing
argument addressed is now resolved even more directly: the snapshot is
projected inside `observe_semantic_turn`'s own port call (§4.2, §5.2), into
plain `int`/`bool`/`frozenset`-derived values on a frozen dataclass, before
that call even returns — strictly before `RUNTIME_TEARDOWN` and every other
closure step, with no separate "freeze gate" required to make that ordering
true.

### 11.3 Why the companion is still emitted last — and exactly where, relative to `SemanticTaskAttemptResult`

Unchanged reasoning: it must hash the primary's actual emitted bytes, so the
primary must already exist; the primary must never wait on the companion; and
teardown/shutdown/cleanup/workspace-removal must not be delayed by
observability work. This ordering is achieved by ordinary sequential
statements after `EVIDENCE_SAFETY` passes, not by a declared gate.

**FU2 pins the ordering down against a concrete source point.** In the
current controller, `EVIDENCE_SAFETY`'s pass/fail is set, then
`_register_attempt_authority(...)` runs (registering this attempt's one-shot
issuance fingerprint), then `result = SemanticTaskAttemptResult(...)` — an
ordinary constructor call, the **one** genuine construction — runs, as the
function's final statement. The companion build-and-emit call
(`emit_activity_companion_or_refuse`, §10) is inserted **after**
`EVIDENCE_SAFETY`'s pass/fail (so the primary/attempt/refusal artifact is
already sealed on disk) and **before** the `SemanticTaskAttemptResult(...)`
call (so its resulting disposition, §12, can be passed as one ordinary
keyword argument to that single constructor call — never assigned
afterward, never applied via `dataclasses.replace`). This is not a new rule
invented for the companion: it is the same "compute every fact first, then
make the one genuine construction call" discipline
`_register_attempt_authority`'s own placement already demonstrates one
statement earlier.

### 11.4 Scope narrowing, unchanged

The companion is emitted only for an invoked attempt that produced a durable,
parseable artifact at `evidence_path` carrying one of the three known kinds
(primary, attempt, refusal). It is not emitted for a task the sweep never
invoked, or for an attempt whose `EVIDENCE_SAFETY` gate failed before writing
anything at all (`SAFETY_CONTEXT_UNPROVABLE`) — in both cases there is no
qualification record to attribute, and an unbound companion would be
strictly worse than none.

---

## 12. Companion failure semantics (dispositions unchanged, triggers now gate-free)

A companion failure never rewrites, annotates, or reopens the already-sealed
qualification verdict — the primary is immutable and was written first, by a
separate, earlier statement, through a separate emission call.

```text
runtime_activity_companion:
    EMITTED                      the artifact exists and is bound
    UNAVAILABLE_NO_TURN_OBSERVATION   turn_observation was None (indeterminate
                                      dispatch or pre-prompt refusal, Sec. 5.4)
    UNAVAILABLE_NO_PRIMARY       the retained primary could not be OPENED or
                                 READ at the primary-read boundary (Sec. 10.3
                                 steps (2)-(3)) -- a missing file, or any other
                                 OSError encountered reading it
    UNAVAILABLE_UNBOUND_PRIMARY  the file WAS read successfully, but its
                                 CONTENT was not a valid bindable retained
                                 artifact: it did not parse as a JSON object,
                                 or its record_kind was none of the three
                                 known kinds
    REFUSED_INVARIANT            the companion payload failed its own gate --
                                 a reserved/unknown proposed_facts key (Sec.
                                 10.2), an over-cap count, bool-as-count, a
                                 cross-field invariant in Sec. 6, an identity
                                 mismatch, or a digest/filename/kind mismatch
                                 at the internal re-derivation gate (Sec. 10.4)
    REFUSED_SCRUB                the shared choke point substituted a bounded
                                 refusal record for it
    REFUSED_PATH_COLLISION       a file already existed at the companion path
    UNAVAILABLE_INTERNAL_ERROR   (FU3, Sec. 12.2) a genuinely unexpected
                                 ordinary Exception was caught at the
                                 companion failure-containment boundary; no
                                 exception text, repr, traceback, or path is
                                 ever retained -- only this bounded name
```

> **ACCEPTED PROSE ERRATUM (5F3B-HARNESS-OBS1-IMPL).** An earlier revision
> described an "unreadable" artifact as `UNAVAILABLE_UNBOUND_PRIMARY`. That
> phrasing is **withdrawn**: it collapses exactly the distinction FU4's
> single-origin exception types exist to keep apart. Stated once, exactly:
>
> ```text
> UNAVAILABLE_NO_PRIMARY       the file could not be OPENED/READ
>                              (PrimaryArtifactUnavailableError, raised at the
>                              primary-read operation and nowhere else)
>
> UNAVAILABLE_UNBOUND_PRIMARY  the file WAS read; its CONTENT disqualifies it
>                              (UnboundPrimaryError, raised at primary-content
>                              classification, strictly after the read succeeded)
> ```
>
> "Unreadable" belongs to the first; it is never the second.

### 12.1 `SemanticTaskAttemptResult` disposition field — now authorized (FU2)

`5F3B-HARNESS-OBS1-CONTRACT-A1` §8 investigated `SemanticTaskAttemptResult`'s
field set directly and found **no** exact-match regression freezing it the
way `test_turn_observation_carries_no_dispatch_fact_at_all` freezes
`SemanticTurnObservation`'s. CONTRACT-A1 therefore did not authorize adding a
field there (it was out of that document's narrow scope), but recorded that
no contradiction blocks a future decision to do so. **FU2 makes that future
decision now, narrowly:** a future OBS1 implementation **may** add one
bounded, non-scoring `runtime_activity_companion` field to
`SemanticTaskAttemptResult`, carrying exactly the closed-vocabulary
disposition enumerated above (an enum or an equivalent exact-string literal
set — never a free-form string), subject to every rule already stated for it
in this document and in CONTRACT-A1 §8's caution:

```text
closed vocabulary only            (the eight values in Sec. 12's list above,
                                    as extended by FU3's Sec. 12.2; nothing else)
exact type / enum                 (never bool, never free text)
non-scoring                       read by nothing in classify_outcome,
                                   evaluate_hard_bar, or ranking.py
non-fingerprinted                 absent from _authorized_facts_fingerprint
not serialized                    absent from qualification_record,
                                   attempt_record, and the refusal shape —
                                   it describes the companion, which is
                                   itself outside all three of those schemas
determined before construction     computed by the sequential code in
                                   §11.3, using facts already fixed, BEFORE
                                   the one `SemanticTaskAttemptResult(...)`
                                   call — never assigned afterward, never
                                   applied via dataclasses.replace, and
                                   never a second issuance (it rides on the
                                   SAME one-shot `_attempt_authority_token`/
                                   `_register_attempt_authority` mechanism
                                   already governing every other field
                                   passed into that one construction)
```

This is a plain field on `SemanticTaskAttemptResult`, populated by ordinary
sequential code after `EVIDENCE_SAFETY` and passed into the class's one
genuine constructor call (§11.3), printed in the runner's bounded console
summary — not a gate outcome, not a `SemanticFailureCode`, not an entry in
`_authorized_facts_fingerprint`. Every property from the original draft
still holds exactly: the qualification result remains valid, scoring-
eligible, and classified exactly as sealed **before** the companion is ever
attempted — this field records what happened to a companion for an already-
finalized verdict, and cannot itself change that verdict, because every
qualification-facing value (`run_validity`, `scoring_eligible`,
`autonomous_classification`, `diagnostic_subclassification`, `gate_statuses`,
`failed_gate`) is computed and fixed earlier in the same function, strictly
before the companion is even attempted. The primary is never rewritten
(`O_CREAT|O_EXCL` makes that structurally impossible); `REFUSED_SCRUB` still
produces a durable file via the existing shared choke point, unmodified.

### 12.2 Finding 2 resolved (FU3) — the companion failure-containment boundary

**What was missing.** §11.3/§12.1 established *where* the companion
build-and-emit step runs (after `EVIDENCE_SAFETY`, before the one
`SemanticTaskAttemptResult(...)` call) and that its outcome is a bounded
disposition value. Neither section mechanically totalized what happens if
that step raises an **ordinary, unexpected exception** — a bug in a helper,
a monkeypatched dependency in a test, an environment fault specific to the
companion path. Nothing in the design prevented such an exception from
propagating past the one genuine construction call, which would be exactly
the failure mode Finding 2 names: non-scoring observational code preventing
construction of the genuine qualification result.

**The fix: one narrow containment boundary, around the companion attempt only
— and, per FU4, `except` clauses mapped by exception TYPE, where each type is
itself raised only at the exact operation whose failure it means, never by
Python-superclass-guessing across multiple, unrelated authority boundaries.**

**What FU3's own boundary got wrong, stated precisely.** FU3's `except
FileNotFoundError: ... except OSError: ...` pair wrapped the **entire**
`try` body — the primary read *and* the eventual companion write (inside
`emit_activity_companion_or_refuse`'s call to `emit_evidence_or_refuse`).
`OSError` is a broad superclass: `PermissionError`, `FileNotFoundError`
(again, if the companion's own destination directory vanished mid-run), and
a bare `OSError` for `ENOSPC` can **all** arise from the companion's own
**write**, which has nothing to do with the primary being absent. Classifying
by superclass alone, across two structurally different operations (reading
an already-sealed primary vs. writing a not-yet-existing companion), would
misreport a companion-write fault as `UNAVAILABLE_NO_PRIMARY` — a false claim
about the primary. FU4 fixes this the way §10.3 already fixes it at the
source: the primary-read operation normalizes its own failures into one
dedicated, unambiguous exception type (`PrimaryArtifactUnavailableError`,
§10.3 step (2)-(3)) **at the exact point the primary is read**, and the
outer boundary below catches that specific type — never a bare `OSError` —
so a later, unrelated write failure has nothing type-specific to be
misclassified into and falls through to the generic catch-all instead.

```python
def _attempt_runtime_activity_companion(
    *,
    turn_observation: SemanticTurnObservation | None,
    broker_activity: BrokerActivityObservation | None,
    bound_primary_path: str,
    identity: "AttemptIdentity",
    safety: ArtifactSafetyContext,
) -> "RuntimeActivityCompanionDisposition":
    """THE failure-containment boundary. Called exactly once, strictly after
    EVIDENCE_SAFETY has sealed the primary/attempt/refusal artifact and
    strictly before the one genuine SemanticTaskAttemptResult(...) call.
    Every qualification-facing fact this function's caller will pass into
    that constructor is ALREADY fixed before this function is ever entered
    -- nothing in this function's body can reach back and change one.
    """
    if turn_observation is None:
        return RuntimeActivityCompanionDisposition.UNAVAILABLE_NO_TURN_OBSERVATION
    try:
        proposed_facts = _build_proposed_facts(turn_observation, broker_activity)
        emission = emit_activity_companion_or_refuse(
            proposed_facts,
            bound_primary_path=bound_primary_path,
            identity=identity,
            safety=safety,
        )
    except PrimaryArtifactUnavailableError:
        # RAISED ONLY at the exact primary-read operation (Sec. 10.3 steps
        # (2)-(3)) -- missing file, permission denied, or any other OSError
        # encountered opening/reading bound_primary_path SPECIFICALLY. A
        # later, unrelated OSError from the companion's OWN write cannot
        # reach this clause, because nothing else in this module raises
        # this type -- it is a NARROW, single-origin exception, not a
        # Python-superclass classification applied across the whole `try`.
        return RuntimeActivityCompanionDisposition.UNAVAILABLE_NO_PRIMARY
    except UnboundPrimaryError:
        # unparseable JSON, non-object top level, or an unrecognized
        # record_kind -- Sec. 10.3 step (4)-(5); the file WAS read
        # successfully, its CONTENT is what disqualifies it.
        return RuntimeActivityCompanionDisposition.UNAVAILABLE_UNBOUND_PRIMARY
    except ActivityRecordInvariantError:
        # the Sec. 10.2 closed-key refusal (raised at EITHER the preliminary
        # check or the canonical-snapshot recheck), an identity mismatch, a
        # canonicalization failure, a malformed/overflowing count, a Sec. 6
        # cross-field violation, or a Sec. 10.4 binding-mismatch at the
        # internal re-derivation gate
        return RuntimeActivityCompanionDisposition.REFUSED_INVARIANT
    except EvidencePathCollisionError:
        # raised ONLY by the shared safety writer's own FileExistsError
        # normalization, for the companion's OWN destination -- never
        # confusable with a primary-read failure, because it is a
        # completely different, already-existing, already-narrow type
        return RuntimeActivityCompanionDisposition.REFUSED_PATH_COLLISION
    except Exception:
        # ANY other ordinary Exception -- most notably, an OSError (or any
        # other exception) raised by the COMPANION'S OWN WRITE inside
        # emit_evidence_or_refuse (permission denied, out of space, the
        # destination's parent directory disappearing, ...), which is
        # deliberately NOT given its own except clause: it is a LATER
        # failure than the primary read, about a DIFFERENT file, and
        # attributing it to "the primary is unavailable" would be a false
        # claim. Also catches any other unanticipated companion-only fault
        # (a bug in a helper, a monkeypatched dependency). The exception
        # object is discarded HERE -- never stringified, never logged,
        # never attached to the disposition, never re-raised. This is the
        # ONLY generic `except Exception:` in this design, and it exists
        # ONLY around this one call.
        return RuntimeActivityCompanionDisposition.UNAVAILABLE_INTERNAL_ERROR
        # BaseException subclasses (KeyboardInterrupt, SystemExit,
        # GeneratorExit) are NOT listed above and therefore propagate
        # unmodified -- this boundary never uses `except BaseException` and
        # never uses a bare `except:`.

    if emission["refused"]:
        return RuntimeActivityCompanionDisposition.REFUSED_SCRUB
    return RuntimeActivityCompanionDisposition.EMITTED
```

Three properties make this a genuine boundary rather than a hopeful `try`:

- **It catches exactly `Exception`, never `BaseException`, never a bare
  `except:`.** `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` are
  deliberately absent from every `except` clause above and therefore
  propagate through this function exactly as they would through any
  ordinary Python code — OBS1 does not, and must not, keep a process alive
  through an operator-requested interrupt or an interpreter shutdown merely
  to finish writing a non-scoring companion.
- **Every *expected* companion failure has its own specific `except` clause,
  keyed to a TYPE that is raised at exactly one authority boundary, never a
  broad Python superclass that several unrelated operations could raise**
  (the table in §12.3 below); only a failure that matches **none** of them
  falls through to the generic `except Exception:` and becomes
  `UNAVAILABLE_INTERNAL_ERROR`. `PrimaryArtifactUnavailableError` in
  particular exists **specifically** so that "the primary could not be
  read" and "something else, later, failed" can never share a Python
  built-in exception class and therefore can never be confused by this
  `except` chain.
- **No exception-derived content ever reaches the disposition, the
  companion artifact, the primary artifact, or the console.** The `except
  Exception:` branch above does not call `str(exc)`, does not format a
  traceback, does not read `exc.args`, and does not bind the exception to
  any name that survives the `except` block. The disposition is a bare enum
  member; that is the *only* thing this function's caller, the console
  printer (§16), or `SemanticTaskAttemptResult` ever sees. This is not a
  weaker version of logging with the details stripped out — no logging
  channel of any kind is introduced by this design; the exception is
  discarded at the point it is caught. `PrimaryArtifactUnavailableError`'s
  own fixed message (§10.3) carries no path, errno, or raw OS diagnostic
  either, so even the narrower, specific clauses carry nothing that needs
  scrubbing at this boundary.

**Two return-value branches, not exceptions.** `REFUSED_SCRUB` is reached by
inspecting `emission["refused"]` after a **successful** call to
`emit_activity_companion_or_refuse` — `emit_evidence_or_refuse`
(`qualification.safety`, unmodified) does not raise on a scrub failure, it
returns a dict and writes a bounded refusal record in the companion's own
place. `EMITTED` is the same successful-return path with `refused` false.
Neither is an exception the containment boundary needs to catch; both are
ordinary control flow over an ordinary return value, exactly as
`emit_evidence_or_refuse` already behaves for the primary artifact.

### 12.3 Expected vs. unexpected failures — the exhaustive mapping (FU4: by exception origin, not superclass)

| Failure | Where it originates | Mechanism | Disposition |
|---|---|---|---|
| No turn observation (indeterminate dispatch, pre-prompt refusal) | before the companion is attempted at all | early return, no exception, checked before entering `try` | `UNAVAILABLE_NO_TURN_OBSERVATION` |
| Bound primary missing, or any `OSError` while opening/reading it | **the primary-read operation, §10.3 steps (2)-(3), and nowhere else** | that operation's own `try`/`except OSError: raise PrimaryArtifactUnavailableError(...) from None`; the outer boundary catches ONLY `PrimaryArtifactUnavailableError` | `UNAVAILABLE_NO_PRIMARY` |
| Primary read successfully, but does not parse as a JSON object, or its `record_kind` is none of the three known literals | **primary-content classification, §10.3 steps (4)-(5), strictly after the read above already succeeded** | `UnboundPrimaryError`, a type distinct from `PrimaryArtifactUnavailableError` precisely so a content problem is never confused with a read problem | `UNAVAILABLE_UNBOUND_PRIMARY` |
| `proposed_facts` (preliminary check) or the canonical snapshot (authoritative recheck) carries a reserved or unknown key | **§10.2/§10.3 steps (1) and (9b)** | `ActivityRecordInvariantError` from `_require_closed_facts_keys` | `REFUSED_INVARIANT` |
| Canonicalization of `proposed_facts` fails (unserializable shape) | **§10.3 step (9a)** | same `ActivityRecordInvariantError`, no exception text retained | `REFUSED_INVARIANT` |
| Run/attempt identity mismatch | **§10.3 step (6)** | `ActivityRecordInvariantError` from `_require_identity_matches` | `REFUSED_INVARIANT` |
| Malformed count / bool-as-int / count overflow / cross-field invariant violation (§6) | **the invariant gate, §6.6** | same `ActivityRecordInvariantError` | `REFUSED_INVARIANT` |
| Binding-field mismatch at the internal re-derivation gate | **§10.4, step (10)** | same `ActivityRecordInvariantError` | `REFUSED_INVARIANT` |
| Scrub refusal | **inside `emit_evidence_or_refuse`, after every check above already passed** | **not an exception** — `emission["refused"] is True` on a normal return | `REFUSED_SCRUB` |
| The companion's own destination already exists | **the shared safety writer's exclusive-create, for the companion path only** | `EvidencePathCollisionError` (`qualification.safety`, unmodified — the ONLY case that module normalizes into a dedicated type) | `REFUSED_PATH_COLLISION` |
| A later, companion-write-only `OSError` (permission denied, out of space, the destination's parent directory disappearing, …) — **occurring only AFTER the primary was already successfully read and bound** | **the companion's own write, inside `emit_evidence_or_refuse`, §10.3 step (11)-(12)** | falls through every specific clause above (none of them names a bare `OSError`) to the generic `except Exception:` | `UNAVAILABLE_INTERNAL_ERROR` — **never** `UNAVAILABLE_NO_PRIMARY` |
| Any other unanticipated companion-only fault (a bug in a helper, a monkeypatched dependency raising `RuntimeError`, …) | anywhere in the companion attempt not covered above | the generic `except Exception:` clause, §12.2 | `UNAVAILABLE_INTERNAL_ERROR` |
| `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` / any other `BaseException` | anywhere | **not caught anywhere in this boundary** | propagates; no disposition is ever assigned, because the enclosing call never returns |

**The load-bearing distinction, stated once more because it is the entire
point of Finding 2:** the table above is organized by *where in the sequence
an exception type is raised*, never by *which Python built-in class it
happens to be a subclass of*. `PrimaryArtifactUnavailableError` exists as its
own type, raised at exactly one place (§10.3 steps (2)-(3)), so that a
structurally identical `OSError` raised **later**, at the companion's own
write, cannot be caught by the same clause merely because both are
`OSError`s. There is no `except OSError:` and no `except FileNotFoundError:`
anywhere in `_attempt_runtime_activity_companion` — those broad built-in
types are never named in this function's `except` chain at all; only the
module's own narrow, single-origin exception types are.

Every row above resolves to a disposition value only — **no row modifies**
`run_validity`, `scoring_eligible`, `autonomous_classification`,
`diagnostic_subclassification`, `gate_statuses`, `failed_gate`, the hard-bar
result, or ranking. This is not an additional check this function performs;
it is a structural consequence of §11.3's ordering — every one of those
values is already a fixed local variable, computed earlier in
`run_semantic_task_attempt`, before `_attempt_runtime_activity_companion` is
ever called, and this function has no parameter, return value, or side
channel through which it could reach back and change one.

### 12.4 The primary artifact remains authority, in every disposition including the catch-all

`_attempt_runtime_activity_companion` and everything it calls open
`bound_primary_path` **read-only** (`"rb"`); no code reachable from this
function ever opens that path — or any path other than the companion's own
derived `.activity.json` sibling — in a write, append, or exclusive-create
mode. This holds in the `UNAVAILABLE_INTERNAL_ERROR` branch exactly as it
holds in every other branch: there is no cleanup step, no delete, no
rewrite, no rename, and no substitution of the retained primary/attempt/
refusal artifact anywhere in this design, regardless of what the companion
attempt did or failed to do. A companion that ends in
`UNAVAILABLE_INTERNAL_ERROR` leaves exactly the same on-disk state for the
primary as a companion that never ran at all.

Absence of a companion — under `UNAVAILABLE_INTERNAL_ERROR` or any other
`UNAVAILABLE_*`/`REFUSED_*` value — means, and only ever means, "runtime
activity evidence unavailable." It is never to be read, printed, or written
up as "no tool activity occurred": that claim would require the companion
to exist and say so, and an absent companion says nothing at all (§8's fixed
`claim_scope` literal already states this; `UNAVAILABLE_INTERNAL_ERROR` does
not carve out an exception to it).

### 12.5 One call, unconditionally, still exactly once

Nothing about §12.2's containment boundary changes §11.3's ordering or
construction discipline: `_attempt_runtime_activity_companion` is called
exactly once, its return value is bound to a local variable, and that local
variable is passed as one keyword argument into the one, unguarded,
unconditional `SemanticTaskAttemptResult(...)` call that follows it in
source order. There is no `try`/`except` around the constructor call itself
(none is needed — nothing about the containment boundary's own body can
raise past its own `except Exception:`, and the constructor call is
downstream of it, never inside it), no retry loop, and no code path anywhere
that attempts a second construction after an ordinary companion failure.

---

## 13. Dispositions

### 13.1 Policy revision

`QUALIFICATION_POLICY_REVISION` **remains `r1`**. Nothing in this design
alters the meaning, eligibility, classification, ranking or comparability of
a qualification result — the companion is built and emitted after the
verdict is already sealed by a separate, earlier statement, using local
variables the controller retains regardless of whether a companion is ever
attempted.

### 13.2 Hard bar and ranking

Unchanged:

```text
tool-call count           NOT a hard-bar criterion
read count                NOT a hard-bar criterion
edit count                NOT a hard-bar criterion
absence of tool calls     does NOT change PREMATURE_SETTLE classification
companion presence        does NOT change scoring eligibility
companion absence         does NOT change scoring eligibility
```

`evaluate_hard_bar` gains no parameter. `ranking.py` is not opened.
`SemanticTurnObservation`'s new `tool_activity` field is read by nothing in
`classify_outcome`, the hard bar, or ranking — only the new,
non-scoring companion-building step reads it.

### 13.3 Lineage

Unchanged, and needs no change: the companion's distinct `record_kind` means
`_require_run_record_shape` already rejects it where a run record is
claimed. The companion is not an invalidation artifact and can never, by
itself, cause `infrastructure_contamination`, `fixture_or_prompt_defect`, or
supersession.

### 13.4 Historical Q1/Q2/Q3

Unchanged: no backfill, no inference, no manufactured evidence. No
`A_IQ-*.activity.json` / `B_IQ-*.activity.json` / `C_IQ-*.activity.json` for
any historical run. The truthful historical state remains "runtime-activity
companion evidence UNAVAILABLE" — never evidence that no tool call occurred.

### 13.5 CFG1 — explicitly separated

Unchanged. This design changes no `compat` block, no `supportsDeveloperRole`,
no `supportsReasoningEffort`, no `reasoning_effort`, no system/developer role
behavior. `qualification/i2_pi_config.py` is not opened.

### 13.6 DX1 — explicitly not authorized

Unchanged. No DX1 prompt is designed here. No existing IQ task may be reused
for a future probe without separate authority.

---

## 14. Explicit non-goals of this phase

Unchanged from the original draft, with three items added by this FU1 pass:

- any change to `pi-implementer-qualification.v2`, the attempt record, the
  refusal record, or lineage;
- a `pi-implementer-qualification.v3`;
- a historical-version compatibility shim in lineage;
- a sweep-level or run-level aggregate artifact;
- a second raw JSON writer, or any overwrite/append/force/replace write mode;
- retention of tool arguments, tool results, assistant text, reasoning, raw
  events, raw exception text, or raw broker diagnostic reasons;
- retention of literal unexpected tool names;
- a per-call chronology, ordering, timing series, or time-to-first-token;
- promotion of any companion fact into the hard bar, ranking, run validity,
  scoring eligibility, or classification;
- a backfill, reconstruction, or inference of historical companion evidence;
- any change to Pi launch configuration (that is CFG1);
- a diagnostic probe or probe prompt (that is DX1);
- a model call, a network call, or a credential read of any kind;
- **(FU1) a fifth semantic port, under any name;**
- **(FU1) a new `TaskAdapterBundle` member, under any name;**
- **(FU1) a new `SemanticGateName` member, `POST_PROMPT_GATES`/`CLOSURE_GATES`
  entry, `SemanticFailureCode`/`CategoryBFailureCode` member, or
  `_authorized_facts_fingerprint` entry, to support companion capture or
  emission.**

---

## 15. Changelog against the original OBS1 draft

| # | Original draft | This revision (FU1) |
|---|---|---|
| 1 | New port `collect_runtime_tool_activity(session)` | Withdrawn. Tool-activity data rides in a new optional field on `SemanticTurnObservation`, the existing `observe_semantic_turn` port's return type (§4). |
| 2 | New `TaskAdapterBundle` member | Withdrawn. No bundle member added; the controller already retains `turn_observation` as a local variable. |
| 3 | New `RUNTIME_ACTIVITY_SNAPSHOT` post-prompt gate | Withdrawn. Capture happens inside the existing `TURN_COMPLETION`/`observe_semantic_turn` call; no new gate name exists (§11.2). |
| 4 | New terminal `RUNTIME_ACTIVITY_COMPANION` closure gate | Withdrawn. Companion build/bind/emit is ordinary sequential code after `EVIDENCE_SAFETY`, not a gate (§11.2, §12). |
| 5 | "The freeze must happen before RUNTIME_TEARDOWN" (prose-only ordering argument) | Superseded: the snapshot is projected inside `observe_semantic_turn` itself, before that call even returns — no separate freeze-timing argument is needed (§11.2). |
| 6 | Baseline-vs-post-dispatch correlation for event counts asserted but not derived from `_DispatchBaseline`'s actual fields | Made exact: `post_dispatch_count - baseline.agent_loop_event_counts[kind]`, using the already-existing pre-dispatch baseline (§5.1). |
| 7 | No baseline for `tool_calls` entries; correlation to "this dispatch" asserted in prose | `_DispatchBaseline` gains `pre_dispatch_tool_call_ids: frozenset[str]`; only keys absent from that frozenset are projected (§5.2). |
| 8 | "AIDO's wait ended" completeness argument, undifferentiated | Split into Part A (AIDO's own read completeness, mechanically proven from `_wait`/`_drain`) and Part B (Pi's own emission ordering, an untrusted protocol assumption) — and a new `runtime_reported_tool_activity_capture_basis` field distinguishes the settled case (both parts apply) from the non-settled case (Part A only) (§5.3). |
| 9 | Availability implications stated for the two `*_available` flags only | Extended to a full explicit implication chain (§6.1), plus per-category ordering proofs (§6.2), the exact partition identity (§6.3), the collapse bound (§6.4), and a proven broker-count inequality (§6.5) — all independently re-derived at the emission gate (§6.6), none assumed. |
| 10 | `bound_primary_sha256`/filename/identity binding described as re-derived, but the consumption boundary's inputs were not specified precisely | Made exact: the binding computation reuses the same `evidence_path` local the primary's own emission call already used, in the same function invocation — no new authority object, no caller-supplied path or digest ever trusted (§10). **⚠ FU2 found this row's own claim still incomplete — see §15.1 below.** |
| 11 | `MAX_ACTIVITY_TOOL_COUNT = 4096`, an arbitrary new cap | Withdrawn. Replaced by `RunBounds().max_events` (the run's own existing, frozen, already-enforced event cap), justified as a real, non-invented ceiling (§9.2). |
| 12 | Implementation surface claimed the four ports and `TaskAdapterBundle` as touched (a new port, a new member) without separately naming a narrower amendment | Reframed: the four port callables and `TaskAdapterBundle` are unchanged; the one genuine touch — `SemanticTurnObservation`'s shape — is named explicitly, not hidden (§4.2, §4.3, §16). |

### 15.1 Changelog: FU2 corrections against FU1

| # | FU1 draft | This revision (FU2) |
|---|---|---|
| F1 | `emit_activity_companion_or_refuse(record, *, path, safety)` — no parameter carries the primary's path, so the "re-derivation" FU1 §10.2 described was code in the *caller*, one scope above the actual trust boundary | Withdrawn. Signature is now `emit_activity_companion_or_refuse(proposed_facts, *, bound_primary_path, identity, safety)`. The function itself opens, hashes, and parses `bound_primary_path` — the caller no longer computes any binding fact before calling it (§10.1-§10.2). |
| F2 | The companion's output path (`activity_path`) was computed by the caller (`run_primary_sweep`/`semantic_sweep.py`) and passed in as an independent parameter | Withdrawn. `_derive_activity_path` runs inside the emission boundary, applied only to `bound_primary_path` — there is no `activity_path` parameter through which a caller could supply a mismatched destination (§11.1). `semantic_sweep.py` needs no change at all (§16). |
| F3 | Payload-declared `bound_primary_sha256`/`bound_primary_filename`/`bound_primary_record_kind` were described as re-derived/refused-on-mismatch, but no call sequence existed that could perform that comparison without the primary path | Closed: the emission boundary always recomputes the three facts from `bound_primary_path` (§10.3) and, at the internal re-derivation gate, refuses (never silently corrects) any payload-declared value that disagrees (§10.4). **FU3 subsequently found this same mechanism had a duplicate-keyword hazard — see §15.2.** |
| F4 | Refusal-record binding stated "no cross-check possible" narratively | Made mechanical: a new companion field, `bound_primary_identity_cross_check_performed` (exact bool), is set by the emission boundary itself and never inferred by a reader from `bound_primary_record_kind` alone (§8, §10.5). |
| F5 | `SemanticTaskAttemptResult`'s companion-disposition field was left "deferred, not authorized" pending a future decision | Authorized narrowly, per CONTRACT-A1's own finding that no exact-field-set freeze exists for that class: the field may be added, determined before and passed into the one genuine construction call, never assigned afterward (§12.1). |
| F6 | The FU1 introduction spliced the CONTRACT-A1 authorization note into the middle of the FU1 summary sentence | Corrected: the CONTRACT-A1 note now follows the complete FU1 paragraph (cosmetic only, no semantic change). |

### 15.2 Changelog: FU3 corrections against FU2

| # | FU2 draft | This revision (FU3) |
|---|---|---|
| G1 | §10.2's (now §10.3's) pseudocode expanded `build_activity_companion_record(**facts, ..., bound_primary_sha256=..., bound_primary_filename=..., bound_primary_record_kind=..., ...)`, while FU2's own §17 adversarial tests deliberately called the emitter with `proposed_facts` carrying exactly those keys | Closed. `proposed_facts` now has a strict, exactly-enumerated closed key set (twenty observational fact names, nothing else), checked by exact-set equality as the very first operation inside the emitter — before `bound_primary_path` is opened and before any `**`-expansion — so a reserved or unknown key is a bounded `ActivityRecordInvariantError` → `REFUSED_INVARIANT`, never a Python `TypeError` (new §10.2). |
| G2 | The "hostile hand-built record with self-consistent binding claims must still refuse" adversarial property was described as exercised through `proposed_facts` | Relocated to the correct layer: `proposed_facts` can no longer express a binding claim at all (G1), so this property is now proven at the internal re-derivation gate, `_require_valid_activity_payload(payload, bound_primary_path=...)`, exercised directly with a hand-built **full** payload that never passed through `proposed_facts` or the builder (new §10.4; §17 item 42). The public-boundary property is now the *stronger* "cannot be expressed," proven positively by item 43. |
| G3 | No mechanism existed to guarantee that an ordinary, unexpected exception inside companion build/bind/emit could not propagate past the one genuine `SemanticTaskAttemptResult` construction | Closed: a new, narrow failure-containment boundary, `_attempt_runtime_activity_companion`, wraps exactly the companion attempt in a `try`/`except Exception:` (never `BaseException`, never a bare `except:`), mapping every expected failure to its existing bounded disposition and any genuinely unexpected one to a new closed-vocabulary value, `UNAVAILABLE_INTERNAL_ERROR` (new §12.2/§12.3). |
| G4 | No disposition existed for "companion code raised something nobody anticipated" | Added exactly one: `UNAVAILABLE_INTERNAL_ERROR`, carrying no exception text, repr, traceback, or path — the bare enum member is the only thing that ever reaches the disposition, the console, or `SemanticTaskAttemptResult` (§12, §12.2). |
| G5 | §9.2 claimed a genuinely correlated run "cannot reach" `RunBounds.max_events`, which overreaches beyond what source proves (it does not establish whether the exact boundary value itself is reachable, only that exceeding it is impossible without triggering the existing event-cap failure) | Corrected to the proven property only: "a valid bounded run cannot exceed the frozen `max_events` bound without triggering the existing event-cap failure" (§9.2). No semantic design change. |

### 15.3 Changelog: FU4 corrections against FU3

| # | FU3 draft | This revision (FU4) |
|---|---|---|
| H1 | The closed-key check (§10.2) ran once, on the live `proposed_facts` Mapping (`set(proposed_facts)`), and canonicalization into `facts` happened separately, later, at step (9) — two different reads of the same caller-controlled object, at two different times | Closed. The check now runs twice against two DIFFERENT things: once, preliminarily and non-authoritatively, on `set(proposed_facts)` (step 1, unchanged position — before any I/O); and again, authoritatively, on `set(facts)` — the canonical snapshot `json.loads` actually produced (step 9b, immediately before `**facts` is ever expanded). A hostile `Mapping`/`dict` subclass that reports one key set to `set(...)` and a different one to `json.dumps` cannot survive the round trip: whatever `facts` (an ordinary `dict`) actually contains is exactly what step 9b inspects and exactly what the builder consumes (new §10.2, §10.3). |
| H2 | No statement existed that the original `proposed_facts` object is never consulted again after canonicalization | Made explicit: "from this line on, `proposed_facts` — the original parameter — is never read again by any code in this function or anything it calls" is now a stated invariant of §10.2/§10.3, and §17's TOCTOU regression (item 38, revised) proves it mechanically. |
| H3 | Canonicalization failure (an unserializable `proposed_facts` shape) had no stated disposition | Closed: the companion's own canonicalization helper, `_canonicalize_activity_facts_or_refuse`, raises the same `ActivityRecordInvariantError` the closed-key check raises — `REFUSED_INVARIANT` — never a raw `TypeError`/`ValueError`/`RecursionError` (§10.3 step (9a)). |
| H4 | The containment boundary's `except FileNotFoundError: ... except OSError: ...` pair wrapped the ENTIRE companion attempt, including the eventual companion write — so a write-time `PermissionError`/`ENOSPC`/etc., unrelated to the primary, would be misclassified as `UNAVAILABLE_NO_PRIMARY` purely because both share the `OSError` superclass | Closed. The primary-read operation now normalizes ITS OWN failures, at the exact point it reads `bound_primary_path`, into one dedicated, single-origin exception, `PrimaryArtifactUnavailableError` (§10.3 steps (2)-(3)). The outer containment boundary catches ONLY that specific type for `UNAVAILABLE_NO_PRIMARY` — there is no `except OSError:` or `except FileNotFoundError:` anywhere in `_attempt_runtime_activity_companion` (new §12.2). A later companion-write `OSError` has no type-specific clause to fall into and reaches the generic `except Exception:` → `UNAVAILABLE_INTERNAL_ERROR`, exactly as a genuinely unattributable companion-only fault should (§12.3, revised). |
| H5 | The exception/disposition table organized rows loosely by "what happened," without stating WHERE each exception type originates | Rebuilt as an explicit origin-first table: every row now names the exact operation (primary read vs. primary-content classification vs. facts validation vs. companion write) an exception type is raised at, so no two structurally different operations can ever share a classification merely by sharing a Python built-in superclass (§12.3). |

---

## 16. Future implementation surface — revised

```text
semantic ports (names, signatures, count)     unchanged
TaskAdapterBundle (member set)                unchanged
qualification gates (SemanticGateName)        unchanged
POST_PROMPT_GATES / CLOSURE_GATES             unchanged
gate_statuses / failed_gate semantics         unchanged
SemanticFailureCode / CategoryBFailureCode    unchanged
_authorized_facts_fingerprint                 unchanged
primary result schema (pi-implementer-qualification.v2)   unchanged
attempt/refusal schema                        unchanged
hard bar / ranking                            unchanged
lineage                                       unchanged

SemanticTurnObservation (value object)        AMENDED — one new optional
                                               field, `tool_activity`,
                                               default None, read by nothing
                                               in scoring/classification/
                                               fingerprint (Sec. 4.2; authority:
                                               CONTRACT-A1)
_DispatchBaseline (module-private)            AMENDED — one new field,
                                               `pre_dispatch_tool_call_ids`
                                               (Sec. 5.2)
SemanticTaskAttemptResult                     AMENDED — one new bounded,
                                               non-scoring, non-fingerprinted,
                                               non-serialized disposition
                                               field, determined before and
                                               passed into the ONE genuine
                                               construction call (Sec. 12.1;
                                               authority: this FU2 document,
                                               §12.1, following CONTRACT-A1's
                                               finding that no separate
                                               exact-field-set freeze exists
                                               for this class)
```

Proposed new/modified files, **not implemented**:

**New — `qualification/runtime_activity.py`**

- `ACTIVITY_RECORD_KIND`; `MAX_ACTIVITY_TOOL_COUNT = RunBounds().max_events`
  (imported, §9.2); `ACTIVITY_TOOL_CATEGORIES = ("aido_read", "aido_edit",
  "unexpected_tool")`; duplicated broker caps (§9.1); `_ALLOWED_PROPOSED_FACTS_KEYS`
  (§10.2, FU3).
- `class ActivityRecordInvariantError(ValueError)` **(FU3)** — the companion's
  own bounded invariant-gate exception, raised for a closed-key violation
  (§10.2), an identity mismatch, a malformed/overflowing count, a §6
  cross-field violation, or a §10.4 binding mismatch. Carries only a fixed,
  literal message naming no runtime value, in the exact lineage of
  `records.RecordInvariantError`.
- `class UnboundPrimaryError(ValueError)` **(FU3)** — raised when the bound
  file does not parse as a JSON object or its `record_kind` is none of the
  three known literals (§10.3 steps (4)-(5)); kept **distinct** from
  `ActivityRecordInvariantError` precisely so the containment boundary
  (§12.2/§12.3) can map it to `UNAVAILABLE_UNBOUND_PRIMARY` rather than
  `REFUSED_INVARIANT`.
- `class PrimaryArtifactUnavailableError(Exception)` **(FU4)** — raised
  ONLY at the exact primary-read operation (§10.3 steps (2)-(3)), wrapping
  any `OSError` encountered opening/reading `bound_primary_path`. Its fixed
  message names no path, errno, or raw OS diagnostic. Kept **distinct** from
  every other exception type in this module — including any `OSError` the
  companion's own later write might raise — so the containment boundary
  never has to classify a failure by Python superclass across two
  structurally different operations (§12.2/§12.3).
- `@dataclass(frozen=True) RuntimeToolActivitySnapshot` — plain ints/bools/an
  enum-like literal for capture basis; validated in `__post_init__` against
  every invariant in §6.
- `project_runtime_tool_activity(activity, baseline, *, turn_outcome) ->
  RuntimeToolActivitySnapshot` — the **only** place `tool_calls` and
  `event_type_counts` are read; pure; retains no reference; applies the
  baseline projection (§5.2) and the settled/non-settled basis distinction
  (§5.3).
- `_require_closed_facts_keys(keys, *, context)` **(FU3, revised FU4)** — the
  §10.2 closed-key-set check, factored so it can be called identically on
  two different key sets: `set(proposed_facts)` (the preliminary,
  non-authoritative check, the first operation
  `emit_activity_companion_or_refuse` performs) and `set(facts)`, the
  **canonical snapshot's own key set** (the authoritative recheck, §10.3
  step (9b), immediately before any `**facts` expansion).
- `_canonicalize_activity_facts_or_refuse(proposed_facts) -> dict` **(FU4)**
  — this module's own `json.dumps`/`json.loads` round trip over
  `proposed_facts`, producing the one canonical snapshot every later step
  consumes; raises `ActivityRecordInvariantError` (never a raw
  `TypeError`/`ValueError`/`RecursionError`) if the shape cannot be safely
  serialized. Structurally identical to `records._canonicalize_or_refuse`'s
  mechanism, but a companion-owned function raising the companion's own
  exception type — not a cross-module call into `records.py`'s private
  helper.
- `build_activity_companion_record(...)` — the invariant gate (builder half):
  assembles the payload from caller-proposed facts plus the binding fields a
  caller passes to it (used internally by the emission boundary, §10.3 — this
  function is never itself the trust boundary; §10's emission function is).
- `_require_valid_activity_payload(payload, *, bound_primary_path)` — the
  independent re-derivation gate over the **fully assembled** payload
  (header + identity + binding + facts together — a wider key set than
  `_ALLOWED_PROPOSED_FACTS_KEYS`), called both when
  `build_activity_companion_record` finishes and, independently, at the
  emission boundary's own step (10), with its own
  `_canonicalize_activity_payload_or_refuse` round trip first (§10.4) —
  **a distinct helper from `_canonicalize_activity_facts_or_refuse` above**:
  one canonicalizes `proposed_facts` alone (step (9a), producing `facts`),
  the other canonicalizes the full, already-assembled payload (this
  function's own first action), and neither is ever substituted for the
  other. **(FU3: now takes `bound_primary_path` so it can itself re-derive
  and compare the three binding fields, rather than merely re-checking the
  shape of values already stamped by its own caller.)**
- `emit_activity_companion_or_refuse(proposed_facts, *, bound_primary_path,
  identity, safety)` **(revised, FU2; closed-key-checked first, FU3;
  canonical-snapshot rechecked and primary-read errors normalized, FU4)** —
  the actual consumption/trust boundary: refuses immediately on a
  non-closed `proposed_facts` key set (preliminary, §10.2), then reads
  `bound_primary_path`'s bytes (wrapping any `OSError` into
  `PrimaryArtifactUnavailableError`), computes the digest, parses and
  classifies the bound kind, cross-checks identity when available, derives
  both `bound_primary_filename` and the companion's own output path from
  `bound_primary_path` alone, canonicalizes `proposed_facts` and re-checks
  the **canonical snapshot's own** key set (authoritative, §10.3 step (9b))
  before ever expanding it, stamps the re-derived binding fields, and
  independently re-validates the fully assembled payload (§10.4). Delegates
  to `qualification.safety.emit_evidence_or_refuse` for the actual write.
  **No new writer.** **No `record`/`path`/`activity_path` parameter
  survives from the FU1 draft** — `proposed_facts` carries observed facts
  only, and there is no parameter through which a caller supplies the
  companion's destination or any binding claim.
- `verify_activity_companion_binding(companion_path, primary_path) -> bool`.
- `class RuntimeActivityCompanionDisposition(str, Enum)` **(FU3)** — the
  closed eight-value vocabulary of §12, including `UNAVAILABLE_INTERNAL_ERROR`.
- `_attempt_runtime_activity_companion(...) -> RuntimeActivityCompanionDisposition`
  **(FU3)** — the failure-containment boundary of §12.2. The **only**
  function in this module with a generic `except Exception:` clause; every
  other function in this module raises the specific, bounded exception types
  above and lets them propagate to this one caller.

**Modified — `qualification/__init__.py`**: add `ACTIVITY_RECORD_VERSION`
only.

**Modified — `qualification/semantic_session.py`**: add `tool_activity:
RuntimeToolActivitySnapshot | None = None` to `SemanticTurnObservation`, with
`__post_init__` accepting `None` or an exact `RuntimeToolActivitySnapshot`
instance; no other field, method, or class in this module changes. (Authority:
CONTRACT-A1.)

**Modified — `qualification/semantic_live_adapters.py`**: `_DispatchBaseline`
gains `pre_dispatch_tool_call_ids`; `_DispatchBaseline.capture` snapshots it;
`observe_semantic_turn`'s existing final return statement gains the
projected `tool_activity` value. **No new method, no new port, no signature
change to any existing method.**

**Modified — `qualification/semantic_controller.py`**: after the existing
`EVIDENCE_SAFETY` block and before the one `SemanticTaskAttemptResult(...)`
construction call, ordinary sequential code (not a gate) calls
`runtime_activity._attempt_runtime_activity_companion(...)` **(FU3)**, passing
`turn_observation` / `broker_activity` and `evidence_path` / `candidate` /
`model_id` / `task` (passed as `bound_primary_path`/`identity`, all already
in scope); its resulting bounded disposition (§12, §12.2) is passed as one
keyword argument into that single constructor call — never assigned
afterward, never via `dataclasses.replace`. No `SemanticGateName` member, no
`gate_statuses`/`failed_gate` interaction, no `SemanticFailureCode` member.
The controller itself contains no `try`/`except` for this call — the
containment boundary is entirely inside `_attempt_runtime_activity_companion`
in `runtime_activity.py`.

**Modified — `qualification/semantic_sweep.py`**: none. **(Revised, FU2.)**
The companion's output path is no longer derived in this module at all —
§11.1 moved that derivation inside `emit_activity_companion_or_refuse`
itself, applied to `evidence_path`. This file's only continued relevance is
that it is where `evidence_path` is already computed and already passed
down to `run_semantic_task_attempt`, unchanged.

**Modified — `run_semantic_sweep_live.py`**: one bounded console line per
task reporting the companion disposition. No new CLI flag.

**Untouched**: `records.py`, `lineage.py`, `safety.py`, `hard_bar.py`,
`ranking.py`, `validity.py`, `outcomes.py`, `scope.py`, `corpus.py`,
`refusal_projection.py`, every existing artifact schema, `TaskAdapterBundle`'s
definition, every `SemanticGateName` member, `POST_PROMPT_GATES`,
`CLOSURE_GATES`, every `SemanticFailureCode`/`CategoryBFailureCode` member,
`_authorized_facts_fingerprint`.

---

## 17. Required regressions for a future implementation — revised

Minimum required evidence, not exhaustive. All offline; no model call and no
socket anywhere; no API key needed. Superseding the original draft's list
where the mechanism changed.

**Frozen-contract preservation (new, FU1)**

1. Source-level: `TaskAdapterBundle`'s field set, read via
   `dataclasses.fields`, is byte-identical before and after the change.
2. Source-level: the four port callables' names and parameter lists
   (inspected via `inspect.signature`) are unchanged.
3. Source-level: `SemanticGateName`, `POST_PROMPT_GATES`,
   `GATING_POST_PROMPT_GATES`, `NON_GATING_POST_PROMPT_GATES`,
   `CLOSURE_GATES` are unchanged (compared as tuples/sets against their
   current values).
4. Source-level: no new `SemanticFailureCode`/`CategoryBFailureCode` member
   exists; `_authorized_facts_fingerprint`'s own field list (inspected from
   source or via a frozen fixture) does not include the companion
   disposition field.
5. `SemanticTurnObservation(runtime_session_id=..., turn_outcome=...)`
   (omitting `tool_activity`) still constructs successfully with
   `tool_activity is None` — the default preserves every existing call site
   and every existing test construction.
6. `require_turn_matches_request` still returns `True`/`False` identically
   for a `SemanticTurnObservation` carrying a populated `tool_activity`,
   proving the exact-type check is unaffected by the new field.

**Correlation correctness (new, FU1)**

7. A synthetic `activity.tool_calls` entry present **before**
   `_DispatchBaseline.capture` is called → excluded from the projected
   snapshot even though it remains in `activity.tool_calls` afterward.
8. A synthetic pre-dispatch `event_type_counts["tool_execution_start"] = 5`,
   post-dispatch `= 8` → `runtime_reported_tool_execution_start_events == 3`.
9. `turn_outcome is SemanticTurnOutcome.SETTLED` →
   `runtime_reported_tool_activity_capture_basis == "agent_settled"`.
10. `turn_outcome is SemanticTurnOutcome.DEADLINE_REACHED` (or any other
    non-settled outcome) →
    `runtime_reported_tool_activity_capture_basis == "wait_ended_before_settled"`.
11. `turn_observation is None` (indeterminate dispatch, or pre-prompt
    refusal) → `runtime_reported_tool_activity_available is False`,
    disposition `UNAVAILABLE_NO_TURN_OBSERVATION`.

**Cross-field invariants (new, FU1, per §6)**

12. `runtime_reported_tool_activity_available is False` → every count in
    §6.1's implication chain is exactly `0`/`False`/`null`; a payload
    violating any one link is refused.
13. `aido_read_end_observed > aido_read_call_ids` → refused (and the
    symmetric case for `aido_edit_*` and `unexpected_tool_*`).
14. `aido_read_error_results > aido_read_end_observed` → refused (and the
    symmetric cases).
15. `aido_read_call_ids + aido_edit_call_ids + unexpected_tool_call_ids !=
    distinct_tool_call_ids` → refused (the partition identity, §6.3).
16. `distinct_tool_call_ids > tool_execution_start_events +
    tool_execution_end_events` → refused (§6.4).
17. Source-level: no test or gate asserts an equality between
    `distinct_tool_call_ids` and `tool_execution_start_events` alone, or
    between `read_operation_count` and `edit_operation_count`/`refusal_count`
    — proving the declined invariants were not silently reintroduced.
18. `broker_recorded_edited_path_count > broker_recorded_edit_operation_count`
    → refused (§6.5).

**Content prohibition** (unchanged from the original draft)

19. A synthetic `tool_calls` entry carrying `arguments`/`input`/`parameters`/
    `result`/`output`/`content`/`text` keys → none appear anywhere in the
    emitted companion bytes.
20. A synthetic record stream containing `reasoning`, `reasoningContent`,
    `thinking`, `redacted_thinking` → none reach the companion.
21. A scrub-context test: endpoint host, API key, broker token, pipe name,
    capability id, workspace absolute path each declared as needles → clean
    companion; a poisoned payload is refused.

**Bounded vocabulary** (unchanged from the original draft)

22. `toolName = "shell"` → `unexpected_tool_call_ids == 1`; the literal
    `"shell"` never appears in the emitted bytes.
23. `toolName` of `"AIDO_READ"`, `" aido_read"`, `"aido_read2"`, `None`,
    `123`, or a `str` subclass comparing equal to `"aido_read"` → each counts
    as `unexpected_tool`.

**Count integrity**

24. `True`/`False` where a count is expected → refused.
25. `-1` → refused.
26. `MAX_ACTIVITY_TOOL_COUNT + 1` → refused, not clamped.
27. A broker count above 32/16/256 → refused.

**Isolation and binding**

28. A snapshot whose `runtime_session_id` is a foreign session → refused
    (checked before projection, inside `observe_semantic_turn`).
29. Candidate/model mismatch (`identity.candidate="A"`,
    `identity.model_id="minimax-m2.7"`) → refused.
30. `task_revision` not prefixed by its `task_id` → refused.
31. A bound file whose `record_kind` is none of the three known literals →
    no companion, `UNAVAILABLE_UNBOUND_PRIMARY`.
32. Bound to an attempt record, and separately to a refusal record → each
    emitted with the correct `bound_primary_record_kind`; the refusal case
    asserts `bound_primary_identity_cross_check_performed is False` and that
    the companion's `candidate`/`model_id`/`task_id`/`task_revision` still
    equal `identity`'s values (this attempt's OWN trusted identity), never a
    value invented from the (identity-less) refusal bytes.

**`proposed_facts` closed key set (new, FU3, §10.2) — no `TypeError` may ever be the mechanism**

33. `emit_activity_companion_or_refuse(proposed_facts, bound_primary_path=P1,
    identity=I1, safety=S)` called with an ordinary `dict` `proposed_facts`
    additionally declaring `bound_primary_sha256` (any value, including one
    that would be internally self-consistent with a hand-invented
    filename/kind) → **refused at step (1), before `P1` is even opened** —
    the disposition is `REFUSED_INVARIANT`, and the test explicitly asserts
    **no `TypeError` is raised and no traceback occurs**: the failure is
    `ActivityRecordInvariantError`, caught and mapped by the containment
    boundary, never an uncontrolled Python argument-collision exception. The
    identical test is repeated for `bound_primary_filename` and
    `bound_primary_record_kind` individually, and for a payload declaring
    all three at once.
34. The same shape with `proposed_facts` additionally declaring `candidate`,
    `model_id`, `task_id`, or `task_revision` (individually and together) →
    refused at step (1), `REFUSED_INVARIANT`, no `TypeError`.
35. The same shape with `proposed_facts` additionally declaring `path`,
    `activity_path`, or `bound_primary_path` → refused at step (1),
    `REFUSED_INVARIANT`, no `TypeError` — proving the companion's own output
    destination cannot be smuggled in through the facts parameter either.
36. `proposed_facts` carrying one **unrecognized** key that is not on the
    reserved list at all (e.g. a typo,
    `"runtime_reported_aido_reed_call_ids"`) → refused, `REFUSED_INVARIANT` —
    proving the check is exact-set equality, not merely "absence of the
    reserved names."
37. `proposed_facts` missing one of the twenty required observational keys →
    refused, `REFUSED_INVARIANT` — the same exact-set check catches omission
    as readily as addition.

**The canonical-snapshot TOCTOU regression (new, FU4, §10.2/§10.3) — the load-bearing addition of this revision**

38. **The hostile-Mapping regression the authorizing prompt requires,
    stated exactly.** Construct a `Mapping` (or `dict`) subclass,
    `_HostileFacts`, whose `__iter__`/`keys()` — the path `set(proposed_facts)`
    at step (1) walks — reports precisely the twenty allowed keys, but whose
    `.items()` (or whatever `json.dumps` actually calls while walking it at
    step (9a)) additionally yields `("bound_primary_sha256", "<any value>")`
    — i.e., a Mapping that answers the FIRST, preliminary enumeration
    honestly and a DIFFERENT, hostile shape to the SECOND, canonicalizing
    one. Call `emit_activity_companion_or_refuse(_HostileFacts(), bound_primary_path=P1,
    identity=I1, safety=S)` and mechanically assert **all** of the following
    in one test:
    - the preliminary check at step (1) **passes** (proving the hostile
      object's disguise works against that check alone, which is exactly
      why it cannot be the authority check);
    - canonicalization at step (9a) produces a `facts` dict that DOES
      contain the smuggled `bound_primary_sha256` key;
    - the re-check at step (9b), against `set(facts)` — the canonical
      snapshot, not the live `_HostileFacts` instance — **refuses**,
      `ActivityRecordInvariantError` → `REFUSED_INVARIANT`;
    - **no `TypeError` is ever raised** (in particular, no duplicate-keyword
      `TypeError` from the `**facts` expansion three lines later, because
      execution never reaches that line);
    - the primary artifact at `P1` is **byte-for-byte unchanged** after the
      call;
    - no file exists at the companion's derived output path (nothing was
      ever written, since the refusal happens before `emit_evidence_or_refuse`
      is ever called);
    - a genuine `SemanticTaskAttemptResult` is still constructed exactly
      once by the surrounding `run_semantic_task_attempt`, with every
      qualification-facing field identical to an otherwise-identical run
      with the companion mechanism disabled.
    The identical construction (a Mapping honest on the first enumeration,
    hostile on the second) is repeated with the smuggled key being
    `bound_primary_filename`, `bound_primary_record_kind`, and `candidate`
    individually, proving the fix is general, not specific to one reserved
    name.
39. **The original object is never consulted again — proven, not merely
    stated.** Using the same `_HostileFacts` instance, additionally
    instrument it so any method call on it **after** step (9a)'s
    canonicalization completes raises an assertion failure if invoked (e.g.
    every dunder/`.items()`/`.keys()` access after a one-shot "already
    canonicalized" flag is set on the instance raises). The call above must
    still complete (refusing at step (9b) as described in item 38) without
    ever triggering that instrumented failure — mechanically proving no
    later code path in `emit_activity_companion_or_refuse`,
    `build_activity_companion_record`, or `_require_valid_activity_payload`
    reads `proposed_facts` (the original parameter) a second time.
40. A `dict` subclass supplied as `proposed_facts` that behaves consistently
    (no TOCTOU shape) but is mutated by the **caller**, from outside, after
    the call returns → the `facts` canonical snapshot inside the completed
    call is unaffected, because `_canonicalize_activity_facts_or_refuse`
    already produced an independent, ordinary `dict` before the call
    returned; the emitted companion (if any) reflects the state at
    canonicalization time only.
41. Canonicalization itself fails — `proposed_facts` (an ordinary `dict`,
    passing the preliminary key check) contains a value that is not
    JSON-serializable at all (e.g. a raw `object()` instance under one of
    the twenty allowed keys) → refused, `ActivityRecordInvariantError` →
    `REFUSED_INVARIANT`; the test asserts the emitted companion disposition
    carries no exception text, and that no raw `TypeError`/`ValueError`
    escapes past `_canonicalize_activity_facts_or_refuse`.

**Isolation and binding — FU2 mechanism, now proven at the correct layer (revised, FU3)**

42. **(Internal gate, white-box.)** A hand-built **full** companion payload
    dict (never constructed via `build_activity_companion_record`, never
    passed through `proposed_facts`) whose `bound_primary_sha256` is
    internally self-consistent with its own hand-invented
    `bound_primary_filename`/`bound_primary_record_kind` but disagrees with
    the actual bytes at `P1`, handed directly to
    `_require_valid_activity_payload(payload, bound_primary_path=P1)` →
    refused. Repeated for a filename-only mismatch and a kind-only mismatch
    (§10.4's "test the consumption boundary directly without going through
    the canonical builder" property, preserved at its correct layer).
43. **(Public boundary, black-box, positive proof.)** `emit_activity_companion_or_refuse`
    called twice with the *same* well-formed, closed-key `proposed_facts` but
    two different genuine primaries, `P1` (candidate A / IQ-1) and `P2`
    (candidate A / IQ-2) → the two emitted companions' `bound_primary_sha256`
    and `bound_primary_filename` each match **their own** file and differ
    from each other — proving per-call recomputation from `bound_primary_path`
    without relying on any forged-claim-rejection test through
    `proposed_facts`, which (per items 33-37) can no longer carry such a
    claim at all. This is the FU3 replacement for the FU2-era "hostile
    `proposed_facts`" tests at the public boundary: the property proven is
    now *stronger* ("cannot be expressed") rather than *weaker*
    ("expressible but rejected").
44. There is no parameter combination through which primary `X`'s
    `bound_primary_path` can cause a companion to be written at any path
    other than `X`'s own fixed `.activity.json` sibling — proven by
    `emit_activity_companion_or_refuse`'s signature itself carrying no
    `activity_path`/`path` parameter (source-level: `inspect.signature`
    contains no such name).
45. `_derive_activity_path` is a pure function of `bound_primary_path` alone
    — called with the same input twice in the same test, both outputs are
    identical, and calling it from two different tests with two different
    primary paths for the *same* candidate/task never collide (proven from
    the fixed suffix rule, §11.1).
46. A genuine run-record binding: `bound_record["candidate"] != identity.candidate`
    (or `model_id`/`task_id`/`task_revision`) → refused, `REFUSED_INVARIANT`.
47. A genuine attempt-record binding: the same four identity mismatches,
    each independently → refused (the attempt schema carries all four
    fields, per §7.2 of the earlier draft).
48. A refusal-record binding succeeds (`EMITTED`) using only `identity` for
    the companion's own identity fields, with
    `bound_primary_identity_cross_check_performed is False` recorded — and a
    source-level assertion that no code path attempts to read
    `candidate`/`model_id`/`task_id`/`task_revision` off a parsed refusal
    record (its schema, per `safety.build_refusal_record`, has none to read).

**Mutation and overwrite**

49. Mutate the source `tool_calls` dict *after* `observe_semantic_turn`
    returns → the already-returned `SemanticTurnObservation.tool_activity`
    values are unchanged (frozen dataclass, no retained reference).
50. A second companion write to the same path → `EvidencePathCollisionError`;
    the first file is byte-for-byte unchanged.
51. Mutate the bytes of an already-emitted primary artifact *after* its
    companion was emitted (rewrite the file on disk out-of-band) →
    `verify_activity_companion_binding(companion_path, primary_path)` returns
    `False` — proving the verifier re-reads and re-hashes at call time rather
    than trusting the companion's stored digest as self-certifying.

**`SemanticTaskAttemptResult` construction ordering (FU2, extended FU3)**

52. Source-level / call-order test: the companion disposition value passed
    into `SemanticTaskAttemptResult`'s one genuine construction is computed
    from a call to `_attempt_runtime_activity_companion` that executes
    strictly *before* that constructor call in `run_semantic_task_attempt`'s
    source — never after.
53. There is no code path anywhere that constructs a genuine
    `SemanticTaskAttemptResult` and then later assigns or `dataclasses.replace`s
    its companion-disposition field; attempting the latter against a genuine
    result raises exactly as `test_entire_foreign_result_field_set_cannot_reuse_its_consumed_issuance`
    already proves for every other field, because it consumes the same
    one-shot `_attempt_authority_token` issuance.
54. `run_validity`, `scoring_eligible`, `autonomous_classification`,
    `diagnostic_subclassification`, `gate_statuses`, and `failed_gate` are
    identical whether the companion disposition ends up `EMITTED` or any
    refused/unavailable value, **including `UNAVAILABLE_INTERNAL_ERROR`** —
    computed from a genuine sweep run repeated once per disposition, with
    the companion mechanism forced into each outcome in turn, asserting
    every one of those fields is byte-identical across all runs. (Superseded
    by the consolidated five-way comparison below, which is the same
    property stated as the single strongest regression.)

**Failure containment — exception ORIGIN, not superclass (FU3, revised/extended FU4, §12.2/§12.3)**

**Methodological requirement, stated once for the whole group below.** Every
test in this group injects its exception (or missing file, or malformed
content) at the SPECIFIC internal operation named — the primary open/read
call inside §10.3 steps (2)-(3), vs. the companion's own write call inside
`emit_evidence_or_refuse` at step (11)-(12) — never at
`_attempt_runtime_activity_companion`'s own outer `try` block directly. A
test that merely monkeypatches the outer boundary to raise a generic
`OSError` proves nothing about *origin-based* classification; these tests
must go through the real call sequence so the SAME exception TYPE, if it
arose from two different origins, would be told apart correctly.

55. A missing bound primary file (nothing at `bound_primary_path`) →
    `FileNotFoundError` at the primary-read operation, wrapped into
    `PrimaryArtifactUnavailableError`, mapped to `UNAVAILABLE_NO_PRIMARY` —
    **and** a genuine `SemanticTaskAttemptResult` is still constructed, with
    every qualification-facing field identical to an otherwise-identical run
    with the companion mechanism disabled.
56. A permission/read `OSError` while *opening* the bound primary (e.g. a
    mocked filesystem that raises `PermissionError` specifically from the
    `bound_primary_path` open call) → the same `PrimaryArtifactUnavailableError`
    → `UNAVAILABLE_NO_PRIMARY`, with the same construction guarantee as item
    55 — proving the wrapping catches `OSError` broadly **at this one
    origin**, not merely the `FileNotFoundError` special case.
57. The bound primary is read **successfully** (a genuine, well-formed
    primary file), and only afterward — during the companion's own write,
    inside `emit_evidence_or_refuse` — a mocked filesystem raises
    `PermissionError` → `UNAVAILABLE_INTERNAL_ERROR`, **explicitly asserted
    NOT to be `UNAVAILABLE_NO_PRIMARY`** — and a genuine
    `SemanticTaskAttemptResult` is still constructed with unchanged
    qualification-facing fields.
58. The bound primary is read successfully, and only afterward the
    companion's own destination directory disappears out from under the
    write (a mocked filesystem raises `FileNotFoundError` from the
    **companion's** write call specifically, not from the primary-read call)
    → `UNAVAILABLE_INTERNAL_ERROR`, **explicitly asserted NOT to be
    `UNAVAILABLE_NO_PRIMARY`** even though the raised exception class is the
    identical `FileNotFoundError` type item 55 uses — proving the
    classification is driven by which operation raised it, never by the
    Python class alone. Result still constructed, fields unchanged.
59. The bound primary is read successfully, and only afterward a generic,
    unclassified `OSError` (not `PermissionError`, not
    `FileNotFoundError`) is raised from the companion's write call (e.g.
    simulating `OSError` for `ENOSPC`) → `UNAVAILABLE_INTERNAL_ERROR`, same
    construction guarantee.
60. The companion's own destination already exists at the derived path
    (created out-of-band before the run) → `EvidencePathCollisionError`
    (raised by the shared safety writer, unmodified) → `REFUSED_PATH_COLLISION`,
    with the same construction guarantee, and the primary artifact's bytes
    unchanged.
61. A malformed bound primary — content that is not valid JSON, or a JSON
    object whose `record_kind` is none of the three known literals — with
    the file itself fully readable → `UnboundPrimaryError` →
    `UNAVAILABLE_UNBOUND_PRIMARY`, **explicitly distinguished from** items 55
    and 56 (both of which are read/open failures, never a content problem),
    with the same construction guarantee.
62. An identity mismatch (a genuine, readable, well-formed primary whose
    declared candidate/model/task/revision disagrees with `identity`) →
    `ActivityRecordInvariantError` → `REFUSED_INVARIANT`, with the same
    construction guarantee.
63. A scrub refusal (the assembled companion payload itself is well-formed
    but fails the shared safety scrub) → **not an exception**, the normal
    `emission["refused"] is True` return path → `REFUSED_SCRUB`, with the
    same construction guarantee, and a durable refusal record written at the
    companion's path via the existing shared choke point.
64. A monkeypatched internal companion helper (e.g.
    `project_runtime_tool_activity`, or `build_activity_companion_record`)
    raising a plain `RuntimeError` — a fault with no relationship to the
    primary read or the companion write at all — → `_attempt_runtime_activity_companion`
    returns `UNAVAILABLE_INTERNAL_ERROR`; a genuine `SemanticTaskAttemptResult`
    is still constructed **exactly once** (asserted via a call-count on a
    wrapped/spied constructor, or equivalent); every qualification-facing
    field is identical to an otherwise-identical run with the companion
    mechanism fully disabled; and the raised `RuntimeError` instance's
    `__str__`/`__repr__` are asserted **never called** (a custom exception
    subclass whose `__str__` raises if invoked is used to prove this) — no
    exception text reaches the disposition, the companion artifact, the
    primary artifact, or the console.
65. A monkeypatched internal companion helper raising `KeyboardInterrupt` (and
    separately, `SystemExit`) inside the containment boundary's `try` body →
    the exception **propagates all the way out of `run_semantic_task_attempt`
    uncaught**; no `SemanticTaskAttemptResult` is constructed for that
    invocation; no disposition value is ever produced. This proves the
    containment boundary is not swallowing `BaseException`.
66. Source-level: exactly one `except Exception:` clause (and no bare
    `except:`, and no `except BaseException:`) exists anywhere in
    `qualification/runtime_activity.py`, and it is the one inside
    `_attempt_runtime_activity_companion`.
67. Source-level: `_attempt_runtime_activity_companion`'s `except` chain
    names `PrimaryArtifactUnavailableError`, `UnboundPrimaryError`,
    `ActivityRecordInvariantError`, and `EvidencePathCollisionError` —
    **never** `OSError`, **never** `FileNotFoundError`, and **never** any
    other Python built-in exception class — before its one generic `except
    Exception:` clause. This is what makes items 57-59 mechanically
    provable rather than incidentally true of the current test doubles.
68. Source-level: no code path in `qualification/semantic_controller.py`
    wraps the call to `_attempt_runtime_activity_companion` or the
    `SemanticTaskAttemptResult(...)` construction in its own `try`/`except` —
    the containment boundary lives entirely inside `runtime_activity.py`.

**Non-interference — the consolidated five-way comparison (strongest regression, FU3)**

69. One identical synthetic qualification attempt (same fixture, same
    corpus task, same synthetic runtime/broker facts) is driven through the
    companion mechanism five times, once forced into each of `EMITTED`,
    `REFUSED_INVARIANT`, `REFUSED_SCRUB`, `REFUSED_PATH_COLLISION`, and
    `UNAVAILABLE_INTERNAL_ERROR`. The test asserts, across all five runs,
    byte-for-byte or value-for-value identical: `semantic_prompts_sent`,
    `dispatch_state` (the semantic dispatch facts), `gate_statuses`,
    `failed_gate`, `run_validity`, `scoring_eligible`,
    `autonomous_classification`, `diagnostic_subclassification`, the
    hard-bar result, and the primary artifact's raw bytes. The **only**
    permitted differences across the five runs are the
    `runtime_activity_companion` disposition value itself and whether/what a
    companion file exists on disk at the companion's derived path.

**Remaining, renumbered from the earlier drafts**

70. `records.RECORD_VERSION == "pi-implementer-qualification.v2"` and
    `QUALIFICATION_POLICY_REVISION == "…policy.r1"` (pinned literal
    assertions).
71. Source-level: no companion symbol is imported by `hard_bar.py`,
    `ranking.py`, `validity.py`, `outcomes.py`, or `records.py`.
72. Source-level: the companion disposition field name is absent from
    `_authorized_facts_fingerprint`'s own field list.
73. `lineage._require_run_record_shape` refuses a companion artifact handed
    where a run record was claimed.
74. The whole companion suite runs with no network, no socket, no
    credential, and no model call — every input a synthetic dict under
    `pytest` `tmp_path`.

---

## 18. Recommended next phase

Unchanged: **`5F3B-HARNESS-OBS1-IMPL`** — implement exactly the mechanism in
§4–§13 (including §10.2's closed `proposed_facts` key set and §12.2/§12.3's
failure-containment boundary) and the regression set in §17, with no scoring
surface added, no primary schema change, no frozen
four-port/`TaskAdapterBundle`/gate-topology amendment beyond the one
disclosed, minimal, additive `SemanticTurnObservation`/`_DispatchBaseline`
widening, no `except BaseException`/bare `except:` anywhere in the companion
path, and no historical backfill.

Then, in order:

1. **`5F3B-HARNESS-CFG1`** (separately authorized).
2. **`5F3B-HARNESS-DX1`** (separately authorized, after OBS1 is implemented),
   on a NEW task, never a reused IQ task.

---

*Design only. No production code modified. No model run. No commit, no push.*
