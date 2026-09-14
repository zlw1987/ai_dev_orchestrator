# 5F3B-HARNESS-OBS1-CONTRACT-A1 — Explicit Additive Amendment to the Frozen
# Phase-2 Observation Contract

**DESIGN / CONTRACT-AMENDMENT ONLY.** No production code or test is modified
by this document. No model was run. Q1/Q2/Q3 were not re-run. OBS1 is not
implemented by this document.

**Status of this document.** This is a narrow, additive amendment against the
historical LIVE1 design (`docs/PHASE_5F3B_LIVE1_PI_SEMANTIC_LIVE_LAYER_DESIGN.md`)
and its accepted implementation. It does **not** rewrite that design. It
authorizes exactly one thing: adding one optional, immutable, non-scoring
field to `SemanticTurnObservation`'s frozen field set. Everything else about
LIVE1's phase-1/phase-2 contract is restated here only to prove it is
unaffected, never to redefine it.

---

## 1. Exact frozen evidence proving the old three-field contract

Two independent frozen sources establish the old contract, and both are
quoted verbatim rather than paraphrased.

**Source 1 — the regression test itself**
(`tests/test_semantic_session.py:103-110`):

```python
def test_turn_observation_carries_no_dispatch_fact_at_all() -> None:
    """The structural half of invariant I-1: there is NO field on a phase-2
    observation through which a turn outcome could carry, contradict, or
    rewrite the phase-1 send fact."""
    import dataclasses

    names = {f.name for f in dataclasses.fields(SemanticTurnObservation)}
    assert names == {"runtime_session_id", "turn_outcome", "agent_end_observed"}
    assert "dispatch" not in names
    assert "call_succeeded" not in names
    assert "semantic_prompts_sent" not in names
```

This is an exact-set equality assertion, not a subset check, and the test's
own docstring names it "the structural half of invariant I-1" — confirming
that this exact field set is not incidental but load-bearing for a named,
documented invariant.

**Source 2 — the frozen LIVE1 algorithm's own phase-2 return shape**
(`qualification/semantic_controller.py`, module docstring, ~line 146-156):

```text
PHASE 1  dispatch_semantic_prompt(SemanticPromptRequest)
           -> SemanticPromptDispatchObservation
         CONFIRMED_NOT_SENT | CONFIRMED_SENT | SEND_STATE_INDETERMINATE
              |
              v
         PROMPT-COUNT TRUTH FIXED HERE, ONCE, AND NEVER REWRITTEN
              |
              v  (only for CONFIRMED_SENT)
PHASE 2  observe_semantic_turn(SemanticTurnRequest)
           -> SemanticTurnObservation
         SETTLED | DEADLINE_REACHED | OBSERVATION_FAILED
```

immediately followed by the named, numbered invariant this amendment must not
disturb (`semantic_controller.py:161-166`):

```text
Invariant I-1 (monotonicity), mechanically: ``_DispatchIndeterminate`` is
raised from inside the phase-1 block and NOWHERE ELSE, and
``semantic_prompts_sent = 1`` dominates every statement that follows it. No
phase-2 outcome, no broker/repository/verification/report-claims failure, no
runtime-teardown, broker-shutdown, generated-config-cleanup, **workspace
removal** (Sec. 9.1.6) or evidence-emission failure can move it back to
``SEND_STATE_INDETERMINATE`` or to ``0``.
```

Independent review is correct: adding `tool_activity` to
`SemanticTurnObservation` is a change to a value both of these sources
freeze, and this document therefore treats it as an explicit, named
contract amendment — not an implementation detail folded into OBS1-FU1's
mechanism section.

---

## 2. Exact contract being amended

**Amended:** the field set of `SemanticTurnObservation`
(`qualification/semantic_session.py`), the phase-2 observation value object
returned by the frozen `observe_semantic_turn` port.

**Not amended by this document, and explicitly out of scope:**

- `SemanticPromptDispatchObservation`, `SemanticPromptDispatchState`,
  `SemanticTurnOutcome` — no field, member, or value added, removed, or
  renamed.
- The phase-1/phase-2 separation itself, or the ordering
  (`dispatch_semantic_prompt` then, only for `CONFIRMED_SENT`,
  `observe_semantic_turn`).
- `CONFIRMED_SENT` monotonicity (Invariant I-1) and `semantic_prompts_sent`
  semantics.
- The four semantic port callable names and parameter signatures.
- `TaskAdapterBundle`'s member set.
- `POST_PROMPT_GATES`, `GATING_POST_PROMPT_GATES`,
  `NON_GATING_POST_PROMPT_GATES`, `CLOSURE_GATES`, `SemanticGateName`,
  `SemanticFailureCode`, `CategoryBFailureCode`, `gate_statuses`,
  `failed_gate`.
- The hard bar (H-1..H-14), ranking, run validity, classification, scoring
  eligibility.
- The primary qualification schema/version, the attempt schema/version, the
  refusal schema, lineage, and `QUALIFICATION_POLICY_REVISION`.

---

## 3. Exact field being added

```python
@dataclass(frozen=True)
class SemanticTurnObservation:
    runtime_session_id: str
    turn_outcome: SemanticTurnOutcome
    agent_end_observed: bool = False
    tool_activity: "RuntimeToolActivitySnapshot | None" = None   # NEW — A1
```

One field. Optional. Defaults to `None`. Nothing else on the class changes:
not `__post_init__`'s existing checks on the three original fields, not
`agent_settled`/`deadline_reached`/`observation_failed`, not
`require_turn_matches_request`.

---

## 4. Why dispatch monotonicity (Invariant I-1) remains unchanged

Invariant I-1 is mechanically anchored to two things, neither of which
touches `tool_activity`:

1. **Where `_DispatchIndeterminate` may be raised** — "from inside the
   phase-1 block and NOWHERE ELSE." `tool_activity` is populated (or left
   `None`) entirely inside phase 2, inside `observe_semantic_turn`'s own
   implementation, strictly after `CONFIRMED_SENT` has already been
   established and `semantic_prompts_sent = 1` has already been fixed by
   phase 1. Nothing in phase 2 — old or new — can execute before that fact
   is fixed, so a field added to phase 2's *return value* cannot be a new
   path back into phase 1.
2. **What phase-2 outcomes are permitted to move.** The invariant enumerates
   an exhaustive list of things that must never rewrite
   `semantic_prompts_sent`/dispatch state: phase-2 outcome, broker/
   repository/verification/report-claims failure, runtime-teardown,
   broker-shutdown, generated-config-cleanup, workspace removal,
   evidence-emission failure. `tool_activity` is read by **nothing** in that
   chain — it is not consulted by `_require_category_a_cleanup_failure_shape`,
   not by the run-validity classifier, not by the hard bar, not by
   `evaluate_hard_bar`, not by anything that could re-derive or re-check
   `semantic_prompts_sent`. A field nothing reads cannot be the vector by
   which a downstream failure rewrites an upstream, already-fixed fact.

The **structural half** of I-1 (Source 1, §1) is updated, narrowly, per §7
below — but the property it was written to prove (no field through which a
turn outcome could carry, contradict, or rewrite the phase-1 send fact)
still holds for the new field, because `tool_activity` cannot carry a send
fact, a dispatch state, or an evidence code (§6) and is consumed by nothing
that computes one.

---

## 5. Why completion semantics remain unchanged

`turn_outcome`, `agent_end_observed`, and the three derived properties
(`agent_settled`, `deadline_reached`, `observation_failed`) are **untouched**
— same fields, same types, same `__post_init__` validation, same property
bodies. `tool_activity`'s presence, absence, or content plays no role in
computing any of the three properties, and nothing in `classify_outcome`,
the hard bar, or ranking reads `tool_activity` — only `turn_observation.agent_settled`
and `turn_observation.agent_end_observed`-shaped facts, exactly as before.

`require_turn_matches_request` (`semantic_session.py`) validates exactly two
things: `type(observation) is not SemanticTurnObservation` (exact type,
subclass refused) and `observation.runtime_session_id ==
request.runtime_session.runtime_session_id`. It reads no other field. A
`SemanticTurnObservation` carrying a populated `tool_activity` is still
exactly `SemanticTurnObservation` (the class is amended in place, not
subclassed), and its `runtime_session_id` is unaffected by the new field —
so this function's behavior is provably identical whether `tool_activity` is
`None`, populated, or (in a malformed instance) anything else. A
foreign-session observation with an otherwise-valid `tool_activity` still
refuses, on the existing `runtime_session_id` check alone; a subclass still
refuses, on the existing exact-type check alone. Matching semantics are
unaffected because they never depended on the field being added.

---

## 6. Type and mutability rules for the new field

```text
tool_activity : RuntimeToolActivitySnapshot | None
```

Enforced in `__post_init__`, in the same idiom this package already uses for
every other exact-type field (`records._is_exact_declared_str`,
`i2b_session.require_exact_bool`):

```python
if self.tool_activity is not None and type(self.tool_activity) is not RuntimeToolActivitySnapshot:
    raise ObservationError(
        "SemanticTurnObservation.tool_activity must be exactly None or an "
        "exact RuntimeToolActivitySnapshot instance; a subclass or a Mapping "
        "is refused, never coerced"
    )
```

- **`type(...) is not RuntimeToolActivitySnapshot`, never `isinstance`** — a
  subclass is refused, for the same reason a `str` subclass with a forged
  `__eq__` is refused elsewhere in this package: what a lookalike *reports*
  and what it *serializes/behaves as* need not agree.
- **No `Mapping`, no duck typing.** A `dict` shaped like a snapshot is not a
  snapshot.
- **`RuntimeToolActivitySnapshot` itself must be `@dataclass(frozen=True)`**,
  retaining only bounded primitive facts (exact `int`/`bool`/a small closed
  string enum for capture basis) — no nested mutable container, no reference
  to `activity`, `tool_calls`, or any live adapter object. This is exactly the
  shape OBS1-FU1 §6/§8 already specifies for that type; this amendment does
  not redefine it, only authorizes it as the value of this one field.
- **No mutable reference survives construction.** `SemanticTurnObservation`
  is itself `@dataclass(frozen=True)`, so once constructed neither
  `tool_activity` nor any of its own fields can be reassigned. Because
  `RuntimeToolActivitySnapshot` is separately frozen and holds only
  primitives, mutating the supervisor's underlying `activity.tool_calls`
  dict after construction cannot alter an already-constructed
  `SemanticTurnObservation` — there is no live reference inside it for such a
  mutation to reach. (This is the identical closure OBS1-FU1 already relies
  on; this amendment is what makes it authorized rather than merely
  proposed.)
- **Field order.** `tool_activity` is declared last, after
  `agent_end_observed`, which already has a default (`= False`). A
  dataclass field with a default may not precede one without a default, so
  this ordering is not a style choice — it is the only ordering Python's
  `dataclass` accepts here.

---

## 7. Exact old regression, and what a future implementation is authorized to change

**Old** (`tests/test_semantic_session.py:103-110`, quoted in full in §1):

```python
names = {f.name for f in dataclasses.fields(SemanticTurnObservation)}
assert names == {"runtime_session_id", "turn_outcome", "agent_end_observed"}
assert "dispatch" not in names
assert "call_succeeded" not in names
assert "semantic_prompts_sent" not in names
```

**New — the ONLY authorized change to this regression:**

```python
names = {f.name for f in dataclasses.fields(SemanticTurnObservation)}
assert names == {
    "runtime_session_id",
    "turn_outcome",
    "agent_end_observed",
    "tool_activity",
}
assert "dispatch" not in names
assert "call_succeeded" not in names
assert "semantic_prompts_sent" not in names
assert "dispatch_state" not in names
assert "dispatch_evidence_code" not in names
```

This is narrower than "assert the set grew by one" or "assert a field named
`tool_activity` exists": it is still an **exact** equality against a
literal, fully-enumerated set (never a subset check, never a generic
"contains" check), and it still asserts the **absence** of every dispatch-
shaped name the original test guarded against, **plus** the two additional
names (`dispatch_state`, `dispatch_evidence_code`) this amendment's own
authorizing prompt named explicitly. The test's docstring should be updated
to record that it now proves the structural half of I-1 **and** that the one
addition it permits (`tool_activity`) is non-dispatch, non-completion,
non-gating — but the assertion itself stays an exact set, never weakened to
a generic "field exists" test, exactly as required.

A future implementation is authorized to change **only** this one test's
literal set (plus its docstring), and to add the construction/typing tests
enumerated in OBS1-FU1 §17 items 5-6. It is not authorized to relax the
`assert names ==` to `assert names >=` or any other weakening.

---

## 8. `SemanticTaskAttemptResult` — investigated, found not separately frozen, deferred anyway

The authorizing prompt requires: do not amend `SemanticTaskAttemptResult` in
this phase unless source proves its field set is itself separately frozen by
its own exact-match contract, in which case STOP and report it rather than
bundling a second amendment silently.

**Investigation.** `SemanticTaskAttemptResult`'s field set was searched for
an exact-equality regression analogous to
`test_turn_observation_carries_no_dispatch_fact_at_all`. None exists.
Specifically:

- `tests/test_semantic_controller.py:909-916`
  (`test_no_reasoning_field_exists_anywhere_in_result`) checks only that no
  field *name* contains the substrings `"reasoning"`, `"chain_of_thought"`,
  or `"thinking"` — a substring exclusion, not an exact-set equality, and it
  is satisfied unchanged regardless of how many fields the class has.
- `tests/test_semantic_fu2a_fu1a_fu1.py:663-676`
  (`test_entire_foreign_result_field_set_cannot_reuse_its_consumed_issuance`)
  builds `every_field_of_success` **dynamically**, via
  `{f.name: getattr(success, f.name) for f in fields(success)}`, and proves
  the one-shot issuance registry still refuses a `replace()` built from every
  field of a different genuine result. This test's correctness does not
  depend on the field *count* or *names* — it would pass unchanged whether
  `SemanticTaskAttemptResult` had its current field set or one with an
  additional field, because it never enumerates the set literally.
- `tests/test_live1_c3_ranking_policy.py:153` likewise iterates
  `dataclasses.fields(SemanticTaskAttemptResult)` generically, to build an
  attacker-shaped clone via `object.__new__` + `setattr` per field — again
  field-count-agnostic.

**Conclusion: `SemanticTaskAttemptResult`'s field set is not separately
frozen by an exact-match contract the way `SemanticTurnObservation`'s is.**
No second frozen-contract amendment is mechanically forced by source. This
document therefore does **not** report a STOP condition for
`SemanticTaskAttemptResult`.

**Disposition: still deferred, not authorized here.** Per the authorizing
prompt's explicit scope ("Do NOT amend `SemanticTaskAttemptResult` in this
design phase"), this document authorizes **only** the `SemanticTurnObservation`
amendment in §3. A future `runtime_activity_companion` disposition field on
`SemanticTaskAttemptResult` (as OBS1-FU1 §12 anticipates) is a **separate**
future design/implementation decision, not pre-authorized by this document.

**Construction-time-only caution, recorded for that future decision.**
`SemanticTaskAttemptResult` is already, by its own accepted design, a
one-shot, issuance-backed, construction-time-only value: its own genuine
instances are produced by exactly one bypass-construction call inside
`run_semantic_task_attempt`, and `dataclasses.replace` against a genuine
instance is already refused by the one-shot issuance registry regardless of
which fields are touched (§8's own investigation, above). Any future
disposition field must therefore be **determined before that one genuine
construction call and passed into it directly** — never assigned or mutated
afterward, and never retrofitted via `replace()`. This is not a new rule this
document invents; it is the existing construction discipline the class
already enforces, restated here so a future OBS1 implementation phase does
not need to rediscover it.

---

## 9. Policy revision disposition

`QUALIFICATION_POLICY_REVISION` **remains `r1`**. `tool_activity` has no
scoring, eligibility, classification, ranking, or hard-bar meaning:

- it is not read by `classify_outcome`, `evaluate_hard_bar`, `ranking.py`, or
  `validity.py`;
- it does not appear in `_authorized_facts_fingerprint`;
- it does not appear in the primary qualification record, the attempt
  record, or the refusal record — those schemas are untouched by this
  amendment;
- its default (`None`) means every existing call site, offline double, and
  historical construction remains valid and produces the identical result it
  always did.

Under `QUALIFICATION_POLICY_REVISION`'s own declared rule (only a change that
alters the meaning, eligibility, classification, ranking, or comparability of
a qualification result moves the revision), this amendment is additive and
non-policy-bearing. No contradiction was found; no STOP is reported on this
point.

---

## 10. All contracts explicitly confirmed unchanged

```text
four semantic port callable names                         UNCHANGED
four semantic port callable parameter signatures           UNCHANGED
TaskAdapterBundle member set                               UNCHANGED

SemanticPromptDispatchObservation                          UNCHANGED
SemanticPromptDispatchState                                UNCHANGED
SemanticTurnOutcome                                        UNCHANGED

phase-1 / phase-2 separation                                UNCHANGED
CONFIRMED_SENT monotonicity (Invariant I-1)                 UNCHANGED (see Sec. 4)
semantic_prompts_sent semantics                             UNCHANGED

POST_PROMPT_GATES                                           UNCHANGED
GATING_POST_PROMPT_GATES                                    UNCHANGED
NON_GATING_POST_PROMPT_GATES                                UNCHANGED
CLOSURE_GATES                                               UNCHANGED

SemanticGateName                                            UNCHANGED
SemanticFailureCode                                         UNCHANGED
CategoryBFailureCode                                        UNCHANGED

gate_statuses                                               UNCHANGED
failed_gate                                                 UNCHANGED

hard bar H-1..H-14                                          UNCHANGED
ranking                                                      UNCHANGED
run validity                                                 UNCHANGED
classification                                               UNCHANGED
scoring eligibility                                          UNCHANGED

primary qualification schema/version                        UNCHANGED
attempt schema/version                                       UNCHANGED
refusal schema                                                UNCHANGED
lineage                                                       UNCHANGED
qualification policy revision                                 UNCHANGED (r1)

SemanticTaskAttemptResult field set                          NOT amended here
                                                              (Sec. 8; not
                                                              separately frozen
                                                              by source, but out
                                                              of scope regardless)
```

---

## 11. Relationship to the historical LIVE1 design

```text
LIVE1-I1 phase-2 observation originally froze three fields:
    runtime_session_id, turn_outcome, agent_end_observed.

HARNESS-OBS1-CONTRACT-A1 supersedes ONLY that field-set aspect, by adding
one optional, immutable, non-scoring diagnostic field, `tool_activity`,
defaulting to None.

All phase-2 completion semantics, all phase-1/phase-2 separation, and every
other LIVE1 invariant (including Invariant I-1's monotonicity guarantee)
remain unchanged, per Sec. 4 and Sec. 5 of this document.
```

The historical LIVE1 design document
(`docs/PHASE_5F3B_LIVE1_PI_SEMANTIC_LIVE_LAYER_DESIGN.md`) is **not** rewritten
by this amendment and remains the accepted historical record of what I1 froze
and why. This document is the narrow, additive, separately-numbered amendment
against exactly one aspect of it, in the same spirit as the existing
`PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md` precedent (a
separate FU document amending one aspect of the same design, rather than a
rewrite of it).

---

## 12. Relationship to OBS1-FU1

With this amendment authorized, OBS1-FU1's mechanism (§4.2 of
`PHASE_5F3B_HARNESS_OBS1_RUNTIME_ACTIVITY_COMPANION_DESIGN.md`) becomes
authorized exactly as designed there:

```text
observe_semantic_turn
    -> same existing port, same name
    -> same parameters
    -> same completion semantics (turn_outcome / agent_end_observed unchanged)
    -> extended immutable observation, now legitimately carrying an
       optional tool_activity, per this amendment
```

Everything else OBS1-FU1 designed remains a **separate OBS1 implementation
concern**, not authorized or re-authorized by this document, and not
re-litigated here:

- `_DispatchBaseline`'s `pre_dispatch_tool_call_ids` field and the
  event-count delta rule (OBS1-FU1 §5);
- the full cross-field invariant set for `RuntimeToolActivitySnapshot`
  (OBS1-FU1 §6);
- the companion artifact's binding, filename, emission ordering, and failure
  semantics (OBS1-FU1 §8-§12);
- any future `SemanticTaskAttemptResult` disposition field (§8 of this
  document, deferred).

This document authorizes only the observation-value extension in §3.

---

## 13. Final report summary

1. **Frozen evidence for the old contract:** §1 — the exact test assertion
   and the exact LIVE1 phase-1/phase-2 diagram plus Invariant I-1 text.
2. **Contract amended:** `SemanticTurnObservation`'s field set only (§2).
3. **Field added:** `tool_activity: RuntimeToolActivitySnapshot | None =
   None` (§3).
4. **Dispatch monotonicity unaffected:** §4 — the field is populated only
   inside phase 2, after `semantic_prompts_sent` is already fixed, and is
   read by nothing in the chain Invariant I-1 protects.
5. **Completion semantics unaffected:** §5 — `turn_outcome`,
   `agent_end_observed`, the three derived properties, and
   `require_turn_matches_request` are all untouched and provably unaffected
   by the new field's presence, absence, or content.
6. **Type/mutability rules:** §6 — exact type only (no subclass, no
   Mapping), itself a frozen dataclass of bounded primitives, no live
   reference survives construction.
7. **Old regression to be updated:** §7, quoted exactly.
8. **New regression semantics:** §7 — still an exact-set equality, still
   guards the same forbidden names, plus two more, never weakened to a
   generic existence check.
9. **`SemanticTaskAttemptResult`:** §8 — investigated; not separately frozen
   by any exact-match test; still deferred and NOT amended by this
   document; construction-time-only caution recorded for whenever it is
   addressed.
10. **Policy revision:** §9 — remains `r1`; no contradiction found.
11. **Contracts confirmed unchanged:** §10, the full checklist.
12. **Recommended verdict:** below.

---

*Design / contract-amendment only. No production code or test modified. No
model run. No commit, no push.*

```text
OBS1 CONTRACT A1 READY — OBS1 DESIGN MAY FREEZE
```
