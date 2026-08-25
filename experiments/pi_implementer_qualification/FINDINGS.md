# 5F3B-I1 Findings

> **OFFLINE QUALIFICATION HARNESS ONLY. NO MODEL QUALIFICATION HAS OCCURRED.
> NO CANDIDATE PASS/FAIL EXISTS YET. 5F3B-I2 / Q1 / Q2 ARE NOT AUTHORIZED.**

This document reports only facts about the **offline harness itself**. It
does not, and cannot, report anything about Candidate A (`qwen3-coder-next`)
or Candidate B (`minimax-m2.7`) as implementers, because neither has been
run. No external prior evidence is used to populate anything here.

## What was built

The frozen IQ-1/IQ-2/IQ-3 corpus (Sec. 12 of the design), each as an
`ar2.fixtures.CaseFixture` value, plus a `qualification` package implementing
the offline classifier/policy machinery Sec. 24's 5F3B-I1 slice authorizes:
outcome classification (Sec. 8/11), run validity (Sec. 17.3), refusal
attribution and scope metrics (Sec. 17), a conservative report-accuracy
comparator (QD-4), the hard qualification bar (Sec. 16), categorical ranking
(Sec. 18), a versioned record schema with fail-closed safe emission, and
immutable invalidation/replacement lineage evidence (Sec. 13/26).

## Offline suite result

```text
190 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

No test was skipped except (never observed in this run) a `git`-availability
skip guard inherited from the reused AR2 fixture pattern. No network call,
socket, model call, or credential lookup occurred anywhere in the run. The
only subprocess activity is local: `git` (fixture construction/inspection,
via the reused, unmodified `ar2.fixtures` builder and the production
`ai_dev_orchestrator.workspace.git_adapter` fixed read-only operation set)
and `python -m pytest` (each fixture's own fixed verification command,
executed against a synthetic disposable repository under a fresh temp
root -- never against this repository or any sibling project).

The suite leaves no thread alive and no `aido_ar2_iq*` temporary fixture
directory behind. (One unrelated `aido_ar2_r1_*` temp directory dated
2026-08-21 predates this work entirely; it is not produced by this suite and
was left untouched.)

## Fixture facts proven offline

- **IQ-1** (money rounding): baseline verification fails exactly the two
  seeded half-value cases (`2.5 -> 3`, `-2.5 -> -3`); a third half-value case
  (`3.5 -> 4`) and every non-half case already pass under the seeded defect,
  so a broad, non-minimal rewrite is distinguishable from a minimal fix. A
  known-correct single-file repair to `money/rounding.py` (never named in
  the prompt) makes all six assertions pass, and Git observes exactly that
  one path changed.
- **IQ-2** (sensor unit-conversion): baseline verification fails exactly
  three node ids -- the two independent unit tests plus the integration
  test that depends on both. Proven mechanically:
  - fixing only the sign-drop defect (`units/parse.py`) still fails;
  - fixing only the rounding defect (`units/convert.py`) still fails;
  - modifying only the already-correct integration file (`units/report.py`),
    leaving both seeded defects in place, still fails -- and in fact cannot
    do otherwise, since the two unit tests call `parse.py`/`convert.py`
    directly and never pass through `report.py` at all;
  - fixing both files (again, neither named in the prompt) passes, with Git
    observing exactly `{units/parse.py, units/convert.py}` changed.
- **IQ-3** (retry policy): the repository is already correct; baseline
  verification passes completely with zero failing tests. The prompt
  describes the reported problem and instructs "change only if actually
  wrong; if already correct, change nothing and say so" without ever
  stating the answer. The correct offline-proven outcome is a byte-identical
  tree: HEAD unchanged, zero observed changed paths.
- All three tasks' prompts were mechanically checked to name none of their
  own expected implementation file paths (full path or bare filename).

## Classifier/policy facts proven offline

- The autonomous outcome classifier (Sec. 8/11) was exercised on both sides
  of every required branch: complete success, settled-incomplete
  (`PREMATURE_SETTLE`), completed-but-verification-failed, deadline-with-
  injected-stall-evidence (`RUNTIME_STALLED`), deadline-without-stall-
  evidence (`RUNTIME_TIMEOUT`, both `False` and absent), operator
  continuation, automatic semantic retry, and pre-prompt infrastructure
  refusal (zero prompts, unscored). No stall threshold, repeat count, or
  timer is encoded anywhere in this module -- `stall_pattern_established`
  is consumed as an already-decided external fact, exactly as Sec. 11.3
  requires, and the offline suite supplies it directly rather than deriving
  it from any internal heuristic.
- Run validity (Sec. 17.3) was proven orthogonal to autonomous
  classification: `INFRASTRUCTURE_CONTAMINATED`, `ATTRIBUTION_UNDETERMINED`
  and `INVALIDATED_BY_FIXTURE_DEFECT` all yield `scoring_eligible = False`
  without being a candidate failure, and a post-prompt contaminated/
  undetermined run truthfully keeps `semantic_prompts_sent = 1`.
- Refusal attribution (Sec. 17.1/17.2) was proven to separate immediate,
  candidate-attributable hard disqualifiers (protected-witness write,
  protected-path write, a genuine third-distinct-implementation-file
  attempt) from protocol/binding anomalies, which require explicit,
  mechanically-established attribution and are never guessed into
  "candidate" by a bare reason code.
- The hard qualification bar (Sec. 16) was proven conjunctive (H-1..H-14),
  proven to treat a missing/ineligible task as `INCOMPLETE` rather than a
  failure, and proven to be the **identical evaluator** for two differently-
  named candidates.
- Categorical ranking (Sec. 18) was proven lexicographic over R-1..R-4, was
  proven to refuse to rank a non-hard-bar-qualified candidate, and was
  proven to withhold the R-4 bucket from any candidate carrying an actual
  timeout, stall, premature settle, operator continuation, or automatic
  retry.
- The record schema (`pi-implementer-qualification.v1`) carries
  `external_prior_not_scored: true` and `aido_requested_max_output_tokens:
  null` unconditionally.

---

# 5F3B-I1-FU1 -- Qualification Evidence Integrity Closure

An implementation-integrity review of the I1 harness found seven defects in
which the *code* did not actually enforce a rule the *design* fixes. None of
them concerned the corpus, the task concepts, or the outcome taxonomy --
all of which remain accepted and unchanged. FU1 closes them and nothing
else. What follows replaces the corresponding I1 claims above where they
were weaker than what is now proven.

## A. The hard-bar precondition now checks BOTH validity fields

`evaluate_hard_bar()` previously trusted `scoring_eligible` alone, so the
contradictory synthetic state `run_validity=INFRASTRUCTURE_CONTAMINATED`
with `scoring_eligible=True` could reach -- and pass -- the hard bar. Both
fields are now required to agree, in `evaluate_hard_bar()` and in
`validity.hard_bar_precondition_met()`/`is_scorable()` alike, and
`ValidityResult` additionally refuses to be constructed with a
self-inconsistent pair at all.

Proven: all three non-`VALID` values carrying `scoring_eligible=True`, and
`VALID` carrying `scoring_eligible=False`, and an absent `run_validity`, are
each `INCOMPLETE` / not-evaluable -- **never** `AUTONOMOUS_QUALIFIED` and
never scored as a candidate failure. A three-task sweep in which every task
is contaminated-but-mislabelled-eligible is `INCOMPLETE`. A
`TaskHardBarFacts` whose `task_id` disagrees with the map key it is filed
under now raises rather than being silently scored as a cross-task
substitution.

## B. The record builder is now a real invariant gate

`pi-implementer-qualification.v1` previously validated only
`supervised_recovery`. It now rejects -- never coerces -- every internally
impossible record, with negative tests for each:

- **candidate/model identity:** the frozen pairing `A <-> qwen3-coder-next`,
  `B <-> minimax-m2.7`. A reversed or mismatched pair, or an unknown
  candidate, is refused. `route_provenance.model_id`, when present, must
  equal the top-level `model_id`.
- **prompt/run shape:** a pre-prompt infrastructure refusal must carry
  `semantic_prompts_sent == 0`, absent `run_validity`, and
  `scoring_eligible == false`, and cannot also carry a model
  classification; a post-prompt primary run must carry exactly one prompt
  and a `run_validity` value.
- **validity:** `scoring_eligible` is true **if and only if**
  `run_validity == VALID`; all three non-`VALID` values force false.
- **classification coherence:** `PREMATURE_SETTLE`, `RUNTIME_TIMEOUT`,
  `RUNTIME_STALLED`, `COMPLETED_BUT_WRONG` and
  `UNTRUSTED_REPOSITORY_STATE` are subclassifications **of**
  `AUTONOMOUS_FAIL` (Sec. 8) and are refused under any other top-level
  value.
- **identity coherence:** `task_revision` (and `supersedes_task_revision`)
  must belong to the record's own `task_id`.
- **declared enums** for `candidate`, `task_id`, `run_validity`,
  `autonomous_classification`, `diagnostic_subclassification` and
  `supervised_recovery`, plus boolean type checks on the flag fields.

`IQ-4T` is accepted in the `task_id` enum because the design's Sec. 26
schema declares it. **No IQ-4T fixture, prompt, or contract exists**, and
Sec. 21's tie-break case remains unauthorized.

## C. Evidence writing is exclusive-create

The I1 writers used `open(path, "w")`, which silently truncates. That
contradicted "emitted artifacts are immutable after emission" in the one
place it matters most: a later **refusal** artifact could destroy an
earlier valid historical record merely because the same output pathname was
supplied.

All qualification evidence -- run record, artifact-emission refusal, and
lineage/invalidation evidence -- is now written by exactly one function,
`safety.write_evidence_exclusively()`, using `open(path, "x")`
(`O_CREAT | O_EXCL`). A second write to an occupied pathname raises
`EvidencePathCollisionError` and writes nothing.

Proven by collision tests: a second record write fails closed and leaves the
first file byte-for-byte unchanged; an **unsafe** later record cannot
overwrite an earlier valid record with its refusal artifact; lineage cannot
overwrite a qualification record; and lineage cannot overwrite earlier
lineage. Two source-level regression guards additionally prove the package
contains **no** truncating or appending `open()` mode anywhere, and exactly
one exclusive-create writer, in `safety.py`.

> The earlier I1 wording claimed "immutability was proven". That claim rested
> only on callers happening to choose fresh pathnames. It is now a property
> of the writer itself.

## D. The artifact safety context is explicit and mandatory

`emit_or_refuse(..., extra_forbidden=())` let a caller silently forget the
qualification-specific forbidden values, so a bare endpoint host could
survive into a retained artifact. The default is gone. A frozen
`ArtifactSafetyContext` (endpoint host, API key, bearer token, broker token,
pipe name, capability id, workspace absolute path) is now a **required**
argument on every emission API; a caller with nothing to declare must say so
explicitly via `ArtifactSafetyContext.none_declared()`. Omitting it is a
`TypeError`, proven for both the record and lineage writers.

Because a declared needle only catches a value the caller *knew* to declare,
one package-owned structural rule was added: a bare IPv4 literal is refused
even under an all-`None` context (the AR2 R1-b lesson that a bare host or IP
reaches an artifact by a route the base-URL needle does not cover). An
ordinary three-component version string such as `0.84.2` is proven not to
trip it. A false positive refuses a legitimate record, which is the intended
fail-closed direction.

Proven refused, with the value never reaching disk: all seven declared
needle kinds, an undeclared bare IPv4 endpoint, and reasoning content. Safe
records emit normally. All needles in the suite are synthetic
(`.example.invalid` hosts, `sk-synthetic-...`, TEST-NET-2/3 documentation
addresses); no real secret value exists anywhere in the tests.

## E. Lineage goes through the same choke point

`write_invalidation_evidence()` previously `json.dump`ed its payload
directly, bypassing the retained-evidence policy entirely -- in exactly the
artifact class that carries operator-supplied reasons and identifiers. It
now delegates to the shared `emit_evidence_or_refuse()`: same scrub, same
mandatory safety context, same exclusive-create write, same bounded refusal
artifact on failure.

Proven: a synthetic broker-token needle and a synthetic bare IP placed in a
lineage field are both refused and never reach disk; the refusal artifact
names the finding **code** (`broker_token_present`) and the refused record
kind, and never echoes the offending value.

## F. `task_revision` now covers the baseline contract

The per-task expected-baseline-failure sets lived inside validator
*functions*, so `_digest_case()` could not see them: a baseline-contract
change -- the very thing that decides whether a fixture is usable -- left
the revision identical.

The contract is now frozen structured data (`BaselineContract`: `mode` plus
`expected_failing_node_patterns`) held on `QualificationTask`, hashed into
`task_revision`, and interpreted by a single function
(`evaluate_baseline_contract`) so the hashed contract and the enforced
contract cannot be two different things. No Python function source is
hashed. **Task content itself is unchanged.**

Proven: rebuilding an unchanged task gives an identical revision, while
changing a file body, the prompt, the expected changed paths, the expected
baseline-failure set, the baseline mode, the verification command, or the
protected patterns each give a different one. The three task revisions are
distinct, each prefixed by its own task id, and the real corpus objects are
verified unmutated by any test variant.

## G. Report-accuracy inverse cases

Two explicit structured claims were only compared in one direction. Both are
now compared in both, because these are positive assertions, not absences:

- `claimed_no_change == False` with no observed diff at all is
  `CONTRADICTED` (the model explicitly asserted a change it did not make);
- `claimed_done == False` with authoritative verification passing is
  `CONTRADICTED`.

Both feed `MATERIAL_MISREPORT`. `UNKNOWN` behavior is unchanged and
re-proven: an absent claim is never automatically a lie, and an unavailable
verification outcome leaves the `done` claim `UNKNOWN` in **both**
directions.

## Design corrections applied

Two narrow wording/cross-reference fixes to
`docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md` Sec. 13, and no
other design change:

1. **(I1)** One sentence could be read as in-place mutation of an
   already-emitted record ("...is **marked** `run_validity:
   INVALIDATED_BY_FIXTURE_DEFECT`..."). Per Sec. 26's immutability rule it
   now states explicitly that this is **new, separate, linked evidence**
   about the original record, never an edit to it.
2. **(FU1)** Two `§17.5` cross-references in that same passage pointed at
   "Neutral / diagnostic (no ranking effect)". The `run_validity` /
   `scoring_eligible` mechanism and the `INFRASTRUCTURE_CONTAMINATED` /
   `ATTRIBUTION_UNDETERMINED` values are defined in **§17.3**; the two
   references were corrected.

---

# 5F3B-I1-FU2 -- Primary Record + Lineage Binding Closure

A further implementation-integrity review found two remaining gaps: the
primary record builder still permitted a handful of internally impossible
cross-field combinations FU1's invariant gate had not yet closed, and
`lineage.build_invalidation_evidence()` still trusted caller-supplied
identifiers about the old/replacement record files it referenced, rather
than reading and verifying those files. Corpus, classifier, hard bar,
ranking, task revision, and the FU1 safety/exclusive-create machinery are
unchanged and remain accepted.

## A. The AUTONOMOUS_PASS cross-field bundle is now enforced

The builder previously allowed `autonomous_classification = AUTONOMOUS_PASS`
to coexist with `operator_continuation = true` or
`automatic_semantic_retry = true`, and allowed a `VALID`, scoring-eligible
run to carry `autonomous_classification = None` or the pre-prompt-only
`INFRASTRUCTURE_REFUSAL` value. Both are now rejected.

A `VALID`, scoring-eligible primary run's `autonomous_classification` must
now be exactly `AUTONOMOUS_PASS` or `AUTONOMOUS_FAIL` -- never absent, never
`INFRASTRUCTURE_REFUSAL`. `AUTONOMOUS_PASS` additionally requires the full
bundle Sec. 9's one-shot policy describes: `semantic_prompts_sent == 1`,
`infrastructure_refusal == false`, `run_validity == VALID`,
`scoring_eligible == true`, `operator_continuation == false`,
`automatic_semantic_retry == false`, and
`diagnostic_subclassification == NONE`. A record with operator continuation
or an automatic semantic retry is now truthfully representable **only** as
`AUTONOMOUS_FAIL`, proven both ways (the `AUTONOMOUS_FAIL` form is accepted;
the `AUTONOMOUS_PASS` form is rejected). Generic `AUTONOMOUS_FAIL` +
`diagnostic_subclassification == NONE` remains valid for failures with no
more specific diagnostic subtype.

## B. Supervised recovery can no longer be embedded in a primary record

`build_qualification_record()` previously accepted
`supervised_recovery = PASS` or `FAIL` inside a `record_kind =
"qualification run record"` -- the PRIMARY evidence class, which is sealed
and immutable before any recovery probe may even be attempted (Sec. 10).
This builder now accepts **only** `supervised_recovery == "NOT_ATTEMPTED"`;
`PASS`/`FAIL` are rejected with `RecordInvariantError`. The full enum
(`VALID_SUPERVISED_RECOVERY`) is retained as documentation of the eventual
shape a **separate future recovery child artifact** will use -- that child
schema is explicitly **not** implemented by this slice.

## C. Lineage now reads and verifies the OLD record, not just its digest

`build_invalidation_evidence()` previously computed the old file's SHA-256
but accepted `invalidated_task_revision` as an independent caller-supplied
value, with no check against the file it named -- so lineage could assert
`invalidated_record_sha256 = SHA(actual file)` alongside
`invalidated_task_revision = <a value the file does not contain>` without
either fact contradicting the other mechanically. The old record is now
opened read-only, parsed, and its own `task_revision` is compared against
the caller's claim; any disagreement raises `LineageBindingError` before any
evidence is built. The same read additionally requires `record_kind ==
"qualification run record"` and `record_version ==
pi-implementer-qualification.v1` (rejecting, among other things, an
artifact-emission-refusal record supplied in place of a real run record),
a declared `task_id`, and non-empty `candidate`/`model_id` fields. Malformed
JSON is rejected with the same error.

## D. Lineage now reads and verifies a provided REPLACEMENT record

When `replacement_record_path` is supplied, the same read-only-and-verify
treatment now applies to it: `record_kind`/`record_version` must match: its
`candidate`, `model_id` and `task_id` must equal the invalidated record's;
and its own `supersedes_task_revision` field must equal the invalidated
record's `task_revision` exactly -- a replacement must declare, in its own
record, exactly what it supersedes, and a mismatch is rejected rather than
recorded. If `corrected_task_revision` is supplied, it must equal the
replacement's own `task_revision`. A fixture/prompt-defect invalidation with
a replacement **must** supply `corrected_task_revision` (the corrected
fixture necessarily produces a different revision); an
infrastructure-contamination replacement may legitimately carry the **same**
task revision as the run it replaces (the task/fixture did not change, only
the contaminated run did), and `corrected_task_revision` is optional in that
case. `replacement_record_sha256` is now computed from the exact replacement
bytes and recorded alongside `replacement_record_filename`.

## Proven (FU2)

- A caller-supplied wrong old task revision, a refusal artifact supplied as
  the old record, and malformed old-record JSON are each rejected.
- A replacement lacking `supersedes_task_revision`, superseding a different
  revision, belonging to another task, or belonging to another
  candidate/model are each rejected.
- A `corrected_task_revision` disagreeing with the replacement's own
  revision is rejected, and a fixture/prompt-defect replacement supplied
  without `corrected_task_revision` at all is rejected.
- A valid fixture-defect replacement produces a fully populated, internally
  consistent evidence record: old SHA, exact old revision, replacement SHA,
  exact replacement revision, and a verified supersedes relationship.
- Infrastructure-contamination lineage without any replacement remains
  representable, and an infrastructure replacement carrying the identical
  task revision as the run it replaces is representable, both with and
  without the caller separately restating `corrected_task_revision`.
- Neither the old nor the replacement file's bytes or mtime change during
  lineage construction -- both are opened read-only throughout.
- Every prior FU1 safety/exclusive-create/scrub/collision test remains
  green, unmodified.

## Offline suite result (FU2)

```text
217 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```
(190 at the end of FU1; +27 new focused tests for the two closures above.)
No design change was needed this round -- both gaps were code-only defects
against the already-accepted design text.

---

# 5F3B-I1-FU2A -- Lineage Reason/Revision Consistency

One remaining lineage gap: `invalidation_reason` was not checked against
whether the task revision it referenced actually changed. A
`fixture_or_prompt_defect` lineage reusing the old task revision (falsely
implying nothing about the frozen contract changed) or an
`infrastructure_contamination` lineage carrying a different revision
(mislabeling an actual task change as a pure infra re-run) could both be
built without error. New `_require_reason_matches_revision_change()` closes
this, checked both for a standalone `corrected_task_revision` (which may be
supplied before any replacement run exists) and for a supplied replacement
record's own `task_revision`:

- `fixture_or_prompt_defect`: the corrected/replacement revision **must
  differ** from the old revision.
- `infrastructure_contamination`: the corrected/replacement revision **must
  equal** the old revision.

Proven: a fixture-defect lineage reusing the old revision is rejected, both
standalone and via a same-revision replacement; an infrastructure-
contamination lineage with a differing replacement revision or a differing
standalone `corrected_task_revision` is rejected. All prior positive shapes
(differing fixture-defect replacement; same-revision infrastructure
replacement, with and without a restated `corrected_task_revision`;
infrastructure contamination with no replacement at all) remain accepted
and re-proven. No old or replacement file is modified by any of the new
checks -- they read already-verified in-memory values only.

```text
225 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```
(217 at the end of FU2; +8 new focused tests.) No design-doc change was
needed -- no wording typo was found this round, and this closes a code-only
gap against the already-accepted design text. Corpus, classifier, hard bar,
ranking, task-revision algorithm, safety context, and exclusive-create
emission are all unchanged.

## What this does NOT establish

- No candidate has been run. No PASS/FAIL, no ranking, no qualification
  verdict exists for Candidate A or Candidate B.
- Scrubbing and redaction remain **backstops, not guarantees**. Nothing here
  claims a retained artifact is provably secret-free.
- 5F3B-I2 (route integration, credential handling) is not authorized by
  this package and was not touched. The `ArtifactSafetyContext` defines the
  future safe-emission *contract* only; it reads no environment variable and
  implements no credential handling.
- The future supervised-recovery **child** record schema is not implemented
  here -- FU2 only closes the primary record against embedding it.
- 5F3B-Q1/Q2 (the first live sweeps) cannot execute until I2 ships.
