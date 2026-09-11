# Phase 5F3B-Q3-DESIGN — Second-Round Candidate C Authorization

> **DESIGN / STATUS DOCUMENTATION ONLY. NOTHING WAS IMPLEMENTED OR RUN IN THIS
> TURN.**
>
> No production module under `experiments/pi_implementer_qualification/` was
> read for the purpose of changing it, and none was modified.
> `qualification/records.py`'s `CANDIDATE_MODEL_IDS` is unchanged and still
> declares exactly `{"A": "qwen3-coder-next", "B": "minimax-m2.7"}`. No test
> file was modified. **No semantic prompt was sent, no Pi/Node process was
> launched, no credential was read, no socket was opened, no candidate was
> run, and B300 was not contacted.** The Q1/Q2 evidence files under
> `experiments/pi_implementer_qualification/results/` were opened read-only
> to confirm their recorded verdicts and were not rewritten, reissued,
> renamed, or deleted. `CLAUDE.md` was not modified. Nothing was committed,
> pushed, or opened as a PR.
>
> **Standing authority, stated in full:**
>
> ```text
> 5F3B-Q1                     Candidate A = qwen3-coder-next   NOT_QUALIFIED / FROZEN
> 5F3B-Q2                     Candidate B = minimax-m2.7       NOT_QUALIFIED / FROZEN
> 5F3B-Q3 (live sweep)        NO-GO — this document authorizes design only
> Real-workspace authority    NO-GO
> M4 (authoritative selection)                NO-GO
> QUALIFICATION_POLICY_REVISION   aido-implementer-role-capability-qualification-policy.r1 (unchanged)
> CANDIDATE_MODEL_IDS (production)            unchanged: {"A": "qwen3-coder-next", "B": "minimax-m2.7"}
> ```

---

## 0. What this document is, and what it amends

This document is a **narrow, additive amendment**. It does not reopen, rewrite,
or restate
[`PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`](PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md)
(hereafter "the canonical design"). Its §5 ("First-round candidate set") is
historical record and is preserved exactly as written: the first round was
`A = qwen3-coder-next` and `B = minimax-m2.7`, and its statement that
`Qwen3.6-27B-262K` was "not a candidate" is **not disturbed** — see §4 below.

This document exists only to:

1. record that the first round has concluded, with both candidates
   `NOT_QUALIFIED`;
2. establish, from the canonical design's own §20 Step 5, that a second
   candidate round is the correct next action;
3. name the second-round candidate identity (`Candidate C`) precisely enough
   that a future, separately authorized implementation prompt can extend
   `CANDIDATE_MODEL_IDS` without ambiguity; and
4. state exactly what is **not** authorized by this document.

No production source and no test file changes are needed to do this, because
nothing here changes behavior — it changes only which subject is *eligible* to
be added to the candidate domain in a future, separate implementation phase.

---

## 1. First-round disposition (verified from evidence, not asserted)

Both `A_IQ-*.json` and `B_IQ-*.json` are present under
`experiments/pi_implementer_qualification/results/`. Their SHA-256 digests were
verified, read-only, against the six digests already on record from
`5F3B-Q3-PRE1`, and are **byte-identical, unchanged**:

| File | SHA-256 |
|---|---|
| `A_IQ-1.json` | `b6237f5e40bbd07039fd7d0c0f5af62ef441d19eb86caf3a671e4769f072a4c4` |
| `A_IQ-2.json` | `bdf9292a879930c483e388b8a9208e80d9f89aa6ec7d8755dec4ec4165e2e2b1` |
| `A_IQ-3.json` | `989bb33dcd61388f0690af6b5975fa5753a7f775a36ddcd8b0438ae5d2dfbb73` |
| `B_IQ-1.json` | `51de3ae36a06bb00e19d3e1efbb2478fc0e9f2eeb15b882a8491daf643ed25b7` |
| `B_IQ-2.json` | `dd4cba33cf41e17b5645213fe6ee831e0b85373988b0df705dc0811ae336a4b7` |
| `B_IQ-3.json` | `604d984e04322d30270e0cb2bbd664a71420e01570334e06f158966aed70fdd9` |

Each record's own `candidate`, `model_id`, `run_validity`, `scoring_eligible`
and `autonomous_classification` fields read:

| Task | Candidate A (`qwen3-coder-next`) | Candidate B (`minimax-m2.7`) |
|---|---|---|
| IQ-1 | `VALID` / eligible / **`AUTONOMOUS_FAIL`** | `VALID` / eligible / **`AUTONOMOUS_FAIL`** |
| IQ-2 | `VALID` / eligible / **`AUTONOMOUS_FAIL`** | `VALID` / eligible / **`AUTONOMOUS_FAIL`** |
| IQ-3 | `VALID` / eligible / `AUTONOMOUS_PASS` | `VALID` / eligible / `AUTONOMOUS_PASS` |

Both candidates' evidence is scorable (§16's precondition: `VALID` +
`scoring_eligible` on all three tasks), so `qualification.hard_bar.
evaluate_hard_bar` reaches the conjunctive H-1..H-14 table rather than
returning `INCOMPLETE`. H-1 ("all three primary cases completed autonomously,
`AUTONOMOUS_PASS` each") fails for **both** candidates at IQ-1 and IQ-2
(`IQ-1:H-1`, `IQ-2:H-1`) — a single `AUTONOMOUS_PASS` at IQ-3 cannot compensate
under the hard bar's conjunctive, no-partial-credit rule (§16). This is exactly
the "valid/scorable candidate failure" the qualification design contemplates,
never an infrastructure or evidence defect.

**Both candidates therefore reach `QualificationState.NOT_QUALIFIED`, exactly
as the operator/architect's accepted current state states.** Consistent with
the canonical design's §20 Step 2 ("the other is recorded as not qualified,
with its exact failing condition") applied to *both* sides at once — the case
§20 Step 5 exists for.

---

## 2. §20 Step 5 is the active step

The canonical design's §20 ("Selection policy") is evaluated in order, and its
Step 5 is exactly:

> **Step 5 — Neither clears it.** **Do not lower the safety or correctness
> bar.** Stop, record both failures with their exact conditions, and design
> either a separate next candidate round or a supervision policy. Do not
> promote a failing model to "primary by default", and do not weaken a hard
> requirement to manufacture a winner.

§1 above is that record. Neither Step 3 (both clear) nor Step 4 (tie-break) is
reachable, because neither candidate cleared §16 at all — Step 2's "exactly one
clears it" is also not the case, since *neither* cleared it. Step 5 is the only
applicable branch, and it explicitly authorizes exactly the action taken here:
**designing** a separate next candidate round (as opposed to a supervision
policy, which is a different, not-chosen branch and is not addressed by this
document).

The hard bar itself is **not** touched, lowered, or reinterpreted by this
document or by opening a second round. §20 Step 5's own text forbids that, and
nothing below revisits H-1..H-14, R-1..R-4, the corpus, or the token policy.

---

## 3. Second-round candidate: identity, not yet added

The second-round candidate is named here for identification purposes only.
**No file that governs qualification behavior is changed by this document** —
in particular `qualification/records.py`'s `CANDIDATE_MODEL_IDS` still declares
exactly two entries, and every consumer of it (`i2_route`, `i2_pi_config`,
`i2_secret_context`, `i2b_controller`, `i2b_live_adapters`, `semantic_attempt`,
`semantic_controller`, `semantic_sweep`, `run_i2b_live`,
`run_semantic_sweep_live`) is unmodified.

The identity to be added, in a future, separately authorized implementation
turn:

```text
Candidate       C
Model id        qwen3.6-27b            (exact, case-sensitive; the served id
                                         AIDO would compare against, matching
                                         the existing exact-string-equality
                                         convention `CANDIDATE_MODEL_IDS`
                                         already uses for A and B)
Harness         Pi LIVE1 qualification harness (unchanged — the same
                harness A and B already run under)
Backend         existing B300 / LiteLLM qualification route (unchanged —
                the same `PROVIDER_ID = "b300_pi_qualification"` route
                identity A and B already use; see §3.1)
Role            implementer candidate (second round)
```

The operator-reported reachability path,

```text
pi --provider amax --model qwen3.6-27b
```

is Pi's own manual CLI invocation for connectivity purposes, and is **not** a
route or provider identity this repository's harness consumes. See §3.1.

### 3.1 Provider/backend distinction is preserved, unchanged

`qualification/i2_identity.py` declares `PROVIDER_ID = "b300_pi_qualification"`
as **the one qualification-owned provider id**, used identically for every
candidate today (Candidate A and Candidate B share it; nothing in
`i2_pi_config.py`, `i2_route.py`, or `i2_secret_context.py` makes it
per-candidate). This is a **globally frozen** route/provider identity, not a
per-candidate field, and this document does not propose changing that shape.

The operator's manual `pi --provider amax --model qwen3.6-27b` invocation names
Pi's own upstream-provider argument — how Pi itself reaches the B300-served
model — which is a fact about reachability, not about AIDO's qualification
route identity. Encoding `amax` into `CANDIDATE_MODEL_IDS`, into a new
per-candidate provider field, or into the frozen `PROVIDER_ID` would be an
unauthorized change to a globally frozen shape and is explicitly **not**
proposed here. When Candidate C is implemented (a separate, future prompt), it
is expected to reuse the *existing* `PROVIDER_ID` / B300 / LiteLLM proxy route
exactly as A and B do, needing only its own `model_id` value.

---

## 4. Critical identity clarification: `qwen3.6-27b` ≠ `Qwen3.6-27B-262K`, and neither claim beyond that is made

The canonical design's §5 states:

> **Qwen3.6-27B-262K is also not a candidate.** Its role is settled and
> different: it is the *architecture control* that made AR1/AR2/O1
> interpretable. It is not the model AIDO now needs to select for normal
> implementation work, and re-running it here would neither test the
> architecture (already proven) nor answer the selection question (it is not
> a candidate for the role).

That statement is a **first-round** design decision about a **specific served
identity**, `Qwen3.6-27B-262K`, in a **specific historical context**:

```text
Harness / runtime context   historical AR2 Pi architecture experiment
Route                       direct-vLLM logical route
Model id                    Qwen3.6-27B-262K
Role                        architecture control (AR1/AR2/O1)
```

The proposed second-round candidate is a **different, exact, served
identity**, in a different context:

```text
Harness      Pi LIVE1 qualification harness
Provider     amax (Pi's own upstream-provider argument; see §3.1)
Backend      existing B300 qualification route
Model id     qwen3.6-27b
Role         implementer candidate (second round)
```

AIDO's existing architecture treats served model identity as **exact and
case-sensitive** everywhere it is checked
(`qualification/records.py::_validate_identity`,
`qualification/i2_route.py::validate_candidate_model_pairing`,
`qualification/i2_pi_config.py`, `qualification/i2_secret_context.py`, and the
frozen `resolve_r2_bucket`/`build_qualification_record` identity checks all
compare model ids as ordinary, exact strings — never case-folded, never
family-matched, never substring-matched). Under that same convention,
`qwen3.6-27b` and `Qwen3.6-27B-262K` are two **distinct served model
identities**, independent of whatever family name they share.

**No source available to this repository proves or disproves that the two
served ids correspond to identical underlying model weights.** No config,
route manifest, or model card in this repository states a weights-identity
relationship between the two. This document therefore makes **exactly one**
claim, and refuses both stronger claims the second-round-design prompt warned
against:

- it does **not** claim `qwen3.6-27b` and `Qwen3.6-27B-262K` are the same
  weights (family-name similarity is not evidence of that);
- it does **not** claim they are *different* weights either (their both
  carrying the `Qwen3.6-27B` family name is likewise not evidence of
  difference);
- it claims only that they are **two distinct served model identities**,
  evaluated in **two distinct qualification/experimental contexts**, under
  AIDO's existing exact-string identity convention.

Consequently, **§5's historical decision about `Qwen3.6-27B-262K` is not
disturbed, not reinterpreted, and not extended to `qwen3.6-27b`.** §5 continues
to say exactly what it said: the first round was A and B, and the AR1/AR2/O1
architecture-control run does not count as first-round candidate evidence.
This document adds a **new** statement about a **new** identity entering a
**second**, later round from scratch — it does not retroactively make
`Qwen3.6-27B-262K` "have been a candidate all along," and it does not claim the
new identity inherits any standing from the old one.

---

## 5. Role separation is unchanged and binding for Candidate C

The canonical design's §6 ("Role-specific qualification principle") states
there is no single "best model," and that qualification is per-role. That
principle is preserved exactly, and is restated here as binding on Candidate C
specifically:

**Candidate C receives zero implementer credit from:**

- the historical `Qwen3.6-27B-262K` AR1/AR2/O1 architecture-control runs
  (§4 above establishes these are not even the same served identity, and even
  if they were the same weights, §6 already forbids one role's evidence from
  crediting another role);
- any historical reviewer-benchmark result for a model in the `qwen3.6-27b`
  family (e.g. `docs/PHASE_3_LITELLM_CLIENT_PLAN.md`'s "candidate **reviewer**
  model" framing, or any 5F2E controlled-reviewer trial) — reviewer evidence is
  a different role under a different bar, and none of it is implementer
  evidence;
- operator subjective preference or expectation about the model;
- model-family reputation of any kind.

**Candidate C must independently clear the exact same H-1..H-14 hard bar**
(§16 of the canonical design), under the exact same `IQ-1`/`IQ-2`/`IQ-3` tasks,
task revisions, fixtures, expected-changed-path contracts, and verification
commands A and B were evaluated under — evaluated fresh, from Candidate C's own
future primary sweep, whenever that sweep is separately authorized and run.
Nothing about Candidate C's qualification path differs from A's or B's.

---

## 6. Qualification policy is unchanged; `QUALIFICATION_POLICY_REVISION` remains `r1`

Inspected, read-only, for this document:

- `qualification/__init__.py` — the single declaration site of
  `QUALIFICATION_POLICY_REVISION = "aido-implementer-role-capability-qualification-policy.r1"`.
  Unmodified.
- `qualification/hard_bar.py` — H-1..H-14, `evaluate_hard_bar`,
  `QualificationState`. Unmodified. No candidate-specific branch exists in it
  (the module docstring states "The identical evaluator is used for Candidate
  A and Candidate B; there is no weaker backup bar" — a third candidate uses
  the same evaluator by construction, since it takes no candidate identity
  parameter at all).
- `qualification/ranking.py` — R-1..R-4, `compare_profiles`,
  `RankingInput`/`CandidateRankingProfile`, `_require_declared_policy_revision`.
  Unmodified. `compare_profiles(a, b)` is a genuinely pairwise comparator with
  no roster-size assumption baked in; nothing here treats "exactly two
  candidates" as a policy fact.
- `qualification/records.py` — `CANDIDATE_MODEL_IDS`,
  `_validate_identity`, `record_header`. Unmodified. Candidate membership is
  checked by exact dict-key membership; the policy revision is stamped from
  the one constant above, independent of which keys `CANDIDATE_MODEL_IDS`
  holds.

**Nowhere in this source does candidate-roster membership itself participate
in the qualification-policy-revision value or in any policy-eligibility
check.** `QUALIFICATION_POLICY_REVISION` governs classification, scoring,
hard-bar semantics, token policy, and comparability rules (§10A.3 of the
canonical design's LIVE1 layer: `compare_profiles` refuses to compare two
profiles carrying different revisions) — it says nothing about, and does not
enumerate, which candidates exist. Adding a subject to be evaluated under this
same, frozen policy is not a change to what the policy *means*.

No contradiction was found. `QUALIFICATION_POLICY_REVISION` **remains**
`aido-implementer-role-capability-qualification-policy.r1`. This document does
not bump it, and no future Candidate C implementation should either, absent a
separate, explicit reason unrelated to roster size.

The full frozen surface named in the second-round-design prompt —
`QUALIFICATION_POLICY_REVISION`, H-1..H-14, `IQ-1`/`IQ-2`/`IQ-3` and their task
revisions, fixtures, expected changed paths, verification commands,
prompt-count policy (`MAX_SEMANTIC_PROMPTS_PER_CANDIDATE = 3`), retry policy
(none — one semantic prompt per attempt), token policy (`TOKEN_POLICY`,
uncapped by default), timeouts, broker authority, workspace authority, Git
authority, evidence schema (`pi-implementer-qualification.v2`), the
`RunValidity`/`AutonomousClassification` taxonomies, and the R-1..R-4
definitions — is confirmed unchanged by inspection, and unchanged by this
document.

---

## 7. Q1/Q2 evidence and identity are preserved, permanently

- `A_IQ-1.json`, `A_IQ-2.json`, `A_IQ-3.json` mean, and continue to mean,
  `qwen3-coder-next`'s primary sweep. Their SHA-256 digests (§1) are
  unchanged.
- `B_IQ-1.json`, `B_IQ-2.json`, `B_IQ-3.json` mean, and continue to mean,
  `minimax-m2.7`'s primary sweep. Their SHA-256 digests (§1) are unchanged.
- None of the six was rewritten, reissued, renamed, reinterpreted, or deleted
  by this document.
- Candidate C's future evidence will use `C_IQ-1.json`, `C_IQ-2.json`,
  `C_IQ-3.json` — implied directly by the frozen writer's existing,
  candidate-generic filename rule
  (`f"{candidate}_{task.task_id}.json"` in
  `qualification/semantic_sweep.py`), not by any new naming logic.
- The second round is strictly **additive**: it adds a new candidate slot and,
  eventually, new `C_*` evidence. It does not touch, requalify, re-rank, or
  reinterpret A's or B's existing `NOT_QUALIFIED` disposition.

---

## 8. What this document does NOT authorize

- It does **not** modify `qualification/records.py::CANDIDATE_MODEL_IDS` or
  any other production source. Candidate C is **named**, not **added**.
- It does **not** authorize the `5F3B-Q3` live sweep (zero semantic prompts,
  zero Pi/Node launches, zero B300 requests, zero credential reads).
- It does **not** authorize real-workspace implementation authority — §22.1 of
  the canonical design stands, unchanged, and this document adds nothing to
  it.
- It does **not** authorize M4 (authoritative candidate selection / durable
  ranking artifact) for any of A, B, or C.
- It does **not** re-rank A against B, or admit C into any comparison, before
  C has its own qualification evidence — see §9 below.
- It does **not** change `CLAUDE.md`, the LIVE1 design document, or any other
  frozen historical design document.

---

## 9. Adversarial review

Each attack named in the second-round-design prompt, and why this document
refuses it:

**Treating Qwen3.6 family similarity as model identity.** Refused in §4:
identity is the exact served string (`qwen3.6-27b` vs `Qwen3.6-27B-262K`),
never a family-name match, and this document explicitly declines to assert
weight-identity in either direction.

**Allowing historical AR2 success to count as C's implementer evidence.**
Refused in §5: AR2/O1 evidence is architecture-control evidence for a
*different, unproven-identical* served id, under a *different* route
(direct-vLLM, not the B300 qualification route), and even under identical
weights §6's role-specific principle already forbids crossing it into
implementer credit.

**Allowing reviewer success to count as implementer evidence.** Refused in
§5, explicitly, by name.

**Changing the bar because A/B failed.** Refused in §2 and §6: §20 Step 5's
own text forbids lowering the bar, and this document does not touch H-1..H-14,
the corpus, or the token policy. The bar Candidate C must clear is textually
identical to the one A and B already failed.

**Treating second-round C as if it participated in the first-round A/B
comparison.** Refused in §0 and §4: §5's first-round record is explicitly
preserved unchanged, and C is stated to be entering "from scratch" in a
**second** round, not inserted retroactively into the first.

**Re-ranking A/B/C before C has its own qualification evidence.** Refused:
this document produces no `CandidateRankingProfile` for C (C has no primary
sweep evidence yet, so `build_profile` would have nothing to derive R-2 from,
and §16's precondition alone makes C `INCOMPLETE`, never rankable). §18
ranking is only ever defined among candidates that have already independently
cleared §16 (`eligible_for_ranking`); C is not run, so it is not eligible, so
no ranking of any kind against A or B is performed or implied here.

**Silently authorizing Q3 live execution.** Refused: §8 states it explicitly,
and the top banner restates zero live activity for this turn.

**Silently authorizing real-workspace implementation.** Refused: §8 states it
explicitly, and §22.1 of the canonical design is left untouched.

---

## 10. Verdict

```text
5F3B-Q1                         Candidate A = qwen3-coder-next   NOT_QUALIFIED / FROZEN
5F3B-Q2                         Candidate B = minimax-m2.7       NOT_QUALIFIED / FROZEN
5F3B-Q3-DESIGN                  ACCEPTED — Candidate C identity (qwen3.6-27b) authorized
                                 for design/naming purposes only
5F3B-Q3 (live sweep)            NO-GO — requires a separate, later authorization
CANDIDATE_MODEL_IDS (production)            UNCHANGED — still exactly {"A", "B"}
QUALIFICATION_POLICY_REVISION               UNCHANGED — remains r1
Real-workspace authority                    NO-GO
M4 (authoritative selection)                NO-GO
```

**Recommended verdict: `5F3B-Q3-DESIGN` — ACCEPT.** The identity clarification
in §4 is the one substantive judgment call this document makes; it is
conservative (asserts distinctness of served identity only, refuses both
stronger claims about weights) and is the correct precondition for a future,
separately authorized `5F3B-Q3-PRE1`/implementation prompt to extend
`CANDIDATE_MODEL_IDS` with `"C": "qwen3.6-27b"` without reopening this
question.
