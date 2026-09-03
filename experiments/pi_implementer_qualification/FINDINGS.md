# 5F3B-I1 / I2 Findings

> **NO MODEL QUALIFICATION HAS OCCURRED. NO CANDIDATE PASS/FAIL EXISTS.
> NO SEMANTIC PROMPT HAS EVER BEEN SENT. Q1/Q2 REMAIN UNAUTHORIZED.**

> **TOP-LEVEL CORRECTION (5F3B-I2B-L1).** Exactly **one** zero-prompt
> Category-B live attempt has now occurred -- Candidate A,
> `results/i2b_live_A_20260831T192543Z.json`, observed Pi `0.84.4`. It
> launched a real Node/Pi process, opened a real named pipe and read a real
> credential, sent **zero** semantic prompts, never reached model inference,
> refused fail-closed, and tore down, shut down and cleaned up verifiably.
> So the blanket claim that previously stood here -- "NO ZERO-PROMPT LIVE
> GATE HAS RUN" -- is **no longer true as of that attempt** and is corrected
> in place. **No candidate model has run**, and no further live attempt is
> authorized.
>
> **5F3B-I2B-L1-LF1** then established that that refusal's ATTRIBUTION was
> wrong, and **5F3B-I2B-L1-LF1-FU1** established that the LF1 correction was
> itself still over-attributing -- see those sections below.

> **HOW TO READ THE HISTORICAL SECTIONS BELOW.** Every section in this
> document is a **phase record**, written when that phase was accepted, and
> is retained unedited except for time scope. Where such a section says
> something like "no zero-prompt live gate has ever run" or "Category-B live
> execution not run", read it as **a fact as of that phase's acceptance**,
> not as a claim about now: those statements were true when written and are
> superseded by the TOP-LEVEL CORRECTION above. Nothing below is rewritten
> to pretend the live attempt did not happen, and no historical result
> artifact is edited.

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

---

# 5F3B-I2 -- Offline B300/Pi Route + Credential Boundary Machinery

> **AS OF THIS PHASE'S ACCEPTANCE: I2 OFFLINE IMPLEMENTATION ONLY. NO
> ZERO-PROMPT LIVE GATE HAD RUN. NO CANDIDATE MODEL HAD RUN. Q1/Q2 REMAINED
> UNAUTHORIZED.** (One zero-prompt live attempt has since occurred -- see the
> TOP-LEVEL CORRECTION at the head of this document. No candidate model has
> run, then or now.)

This section reports facts about the **offline I2 machinery itself**,
implemented per
`docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md` (I2A,
frozen, including its FU1/FU2 corrections) Sec. 23's slices I2-1 through
I2-5. It reports nothing about Candidate A (`qwen3-coder-next`) or Candidate
B (`minimax-m2.7`) as implementers -- neither has ever been run, and no
network request, socket, Pi/Node process, or real credential value was ever
involved in producing this section.

## What was built

Six new I2-owned modules under `qualification/`, none of which modify or
import the frozen `ar2` live-runtime machinery:

- **`i2_environment.py`** (I2-1) -- a positive-allowlist child-environment
  builder that takes its ambient environment as an INJECTED
  `Mapping[str, str]` (never reads real `os.environ`): Windows baseline
  names, a narrowed `PATH`, the Pi-owned `PI_*` variables, and exactly ONE
  credential carrier, `PI_QUALIFICATION_B300_ROUTE_KEY`. No profile names
  (`USERPROFILE`/`HOME`/`APPDATA`) are ever forwarded, and there is no
  keyless placeholder path -- a blank/missing credential value is refused.
- **`i2_secret_context.py`** -- a frozen, run-scoped
  `QualificationRouteSecretContext` whose secret- and endpoint-bearing
  fields (`api_key`, `base_url`, `endpoint_host`) are both `field(repr=False)`
  AND covered by a custom bounded `__repr__` -- two independent reasons the
  default dataclass repr can never print them. It carries a
  `to_safety_context()` method that populates the ALREADY-accepted I1
  `ArtifactSafetyContext` (never a new safety schema), and no
  `to_dict`/`asdict`/`model_dump`-style serialization helper exists on it
  anywhere.
- **`i2_pi_config.py`** (I2-2) -- the disposable `settings.json`
  (`defaultProjectTrust: "never"`, telemetry disabled, provider
  `maxRetries: 0`) + `models.json` (one provider, `api:
  "openai-completions"`, `apiKey: "$PI_QUALIFICATION_B300_ROUTE_KEY"`,
  exactly one model entry, `maxTokens` omitted) generator. Its credential
  parameter, `credential_env_var_name`, is a variable NAME -- the function
  signature carries no `api_key`/`credential_value`/`secret` parameter of
  any kind, proven by a signature-introspection test.
- **`i2_route.py`** (I2-3) -- `route_descriptor_for_candidate("A"|"B")`,
  whose model-id pairing is imported directly from
  `qualification.records.CANDIDATE_MODEL_IDS` (never re-declared, so the two
  cannot drift), always `backend_gateway_class = "b300_litellm_proxy"`,
  never direct vLLM. `run_offline_route_check` wires the future zero-prompt
  `ar2.route_check.check_route_serves_model` gate via dependency injection
  only -- no real call is ever made by this package.
- **`i2_credentials.py`** (I2-4) -- `read_connection_values` resolves
  `AIDO_LITELLM_BASE_URL`/`AIDO_LITELLM_API_KEY` through an INJECTED reader
  callback with no default environment read; a missing/blank value raises
  `ConnectionValueError` naming the variable NAME only, never a value.
  `resolve_connection_after_preflight` enforces the I2A Sec. 8/16 ordering:
  every non-secret gate must report `passed=True` before the connection
  reader is invoked at all.
- **`i2_cleanup.py`** (I2-5) -- `scrub_generated_qualification_config`
  deletes the disposable config directory and verifies absence by `stat`
  (never a forensic-erasure claim); `classify_cleanup_failure` implements
  I2A Sec. 16/18's phase-aware rule; `prepare_diagnostic_text_for_retention`
  is the pre-persistence safety boundary for any future raw Pi/RPC output,
  reusing `qualification.safety.qualification_scrub_check` UNMODIFIED
  rather than building a second secret scanner.

## Offline suite result

```text
300 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(225 at the end of I1-FU2A; +75 new focused I2 tests across six new test
modules. No existing I1 test was modified, weakened, or removed.) No
network call, socket, model call, Pi/Node process, or credential lookup
occurred anywhere in the run -- confirmed both by manual review of every new
module (no `os.environ`, `httpx`, `socket`, `subprocess`, or `requests`
usage anywhere outside docstrings) and by the suite's existing autouse
thread-leak guard reporting no surviving `ar2-`-owned thread.

The frozen `experiments/pi_external_runtime_ar2/tests` suite (290 tests) was
also re-run, unmodified, to confirm the reused interface shapes
(`route_check.check_route_serves_model`'s call signature, the generated-config
shape, the environment-builder shape) I2 structurally models itself on
remain compatible: **290 passed, 0 failed**, no `ar2/` file touched.

## Facts proven offline

**Environment safety (I2-1).** Using synthetic ambient-environment mappings
containing decoy `OPENAI_API_KEY`, `MINIMAX_API_KEY`,
`QWEN_TOKEN_PLAN_API_KEY`, `AIDO_LITELLM_API_KEY`, `AIDO_LITELLM_BASE_URL`,
`AIDO_VLLM_API_KEY`, `AIDO_VLLM_BASE_URL`, `GITHUB_TOKEN`,
`ANTHROPIC_API_KEY`, `AWS_SECRET_ACCESS_KEY`, `HOME`, `APPDATA`, and
`USERPROFILE` values: none of those names, and none of their decoy values,
ever appear anywhere in the built child environment. Only the accepted
Windows baseline names, a narrowed `PATH`, the four Pi-owned variables, and
the one credential carrier are present -- proven by an exact set-equality
assertion, not a subset check. A blank/missing credential value is refused
(`EnvironmentPolicyError`); there is no keyless placeholder constant
anywhere in the module. Candidate A and Candidate B use an identical
environment-building call shape (the builder takes no candidate parameter
at all).

**Secret-context safety.** `repr()` and `str()` of a constructed
`QualificationRouteSecretContext` never contain the synthetic API key, the
synthetic base URL, or even the synthetic endpoint host -- proven against a
realistic synthetic value, not an empty string. `dataclasses.fields()`
confirms `api_key`/`base_url`/`endpoint_host` are all `repr=False`. No
`to_dict`/`asdict`/`model_dump`/`as_dict`/`to_json` attribute exists on the
constructed object.

**Config generation (I2-2).** The generated `models.json` contains the
synthetic base URL (necessarily, per design Sec. 10) and the literal string
`apiKey: "$PI_QUALIFICATION_B300_ROUTE_KEY"`, and never the synthetic
credential VALUE, under any of the settings/models files, in any of the
generator's tests. `maxTokens` never appears in the serialized `models.json`
text. `settings.json`'s `retry.provider.maxRetries` is exactly `0`.
Candidate A and Candidate B configs, generated by calling the SAME function
twice, are proven identical except for `models[0].id`. A signature
introspection test proves `write_qualification_pi_config` has no
`api_key`/`apikey`/`credential_value`/`secret`/`credential` parameter --
only `credential_env_var_name`, a NAME.

**Route descriptors + offline route-check wiring (I2-3).** Candidate A/B
route descriptors resolve to `qwen3-coder-next`/`minimax-m2.7` exactly,
matching `qualification.records.CANDIDATE_MODEL_IDS` by import, not
duplication. `validate_candidate_model_pairing` refuses an unknown
candidate and a REVERSED pairing (candidate `"A"` proposed with candidate
B's model id, and vice versa). `backend_gateway_class` is always
`"b300_litellm_proxy"` for both candidates; the string `"vllm"` never
appears in it. Using an injected synthetic checker: the descriptor's exact
`model_id` is what is passed to the checker (proven by capturing the call
arguments), an unreachable result fails closed, and a reachable-but-
wrong-model result fails closed -- with no fallback model ever substituted
in either case.

**Credential read ordering (I2-4).** A failing non-secret gate raises
`InfrastructureRefusal` and the credential/connection reader -- wrapped in a
call-counting double -- is never invoked (count stays `0`); a later gate in
the sequence is proven not to run at all after an earlier one fails
(assertion-raising stand-in gate). When every gate passes, the reader is
called EXACTLY once. `read_connection_values` rejects a missing or blank
`AIDO_LITELLM_BASE_URL`/`AIDO_LITELLM_API_KEY` with an error message
containing the variable NAME and never the co-located synthetic value,
`Authorization`, or `Bearer` text.

**Cleanup + phase-aware classification (I2-5).** Before cleanup, the
generated `models.json` is proven to exist, contain the synthetic endpoint
and the `$PI_QUALIFICATION_B300_ROUTE_KEY` reference, and never the
synthetic credential value. After a successful
`scrub_generated_qualification_config`, both the config directory and the
`models.json` path are proven absent via `os.path.exists`. An injected
`shutil.rmtree` failure proves a failed deletion is truthfully reported
(`removed=False`, `scrub_verified=False`) rather than silently treated as
success. `classify_cleanup_failure(semantic_prompts_sent=0)` yields
`AutonomousClassification.INFRASTRUCTURE_REFUSAL` with no `run_validity`;
`classify_cleanup_failure(semantic_prompts_sent=1)` yields
`RunValidity.INFRASTRUCTURE_CONTAMINATED` with `scoring_eligible=False` and
no top-level autonomous classification -- proven as two DISTINCT branches,
never the other way around, and `semantic_prompts_sent` is proven unchanged
by the classification call in both cases. Any other prompt count is
refused (`CleanupClassificationError`).

**Diagnostic safety boundary.** Using synthetic needles (API key, endpoint
host, absolute workspace path, pipe name, capability id, and a
`"reasoning"`-keyed value), `prepare_diagnostic_text_for_retention` refuses
every one of them (`retention_ready=False`, `text=None`) while safe
diagnostic text is retention-ready under both an empty and a fully-populated
`ArtifactSafetyContext`. A refused result's serialized form is proven never
to contain the offending synthetic value. This reuses I1's existing
`qualification_scrub_check` unmodified -- no second secret scanner was
built.

**Token policy.** No test anywhere in the I2 suite passes, asserts, or
depends on a numeric `maxTokens`/`max_output_tokens` value for the
qualification route; `aido_requested_max_output_tokens` stays `null` per
the unchanged I1 record schema, and the generated `models.json`'s
`maxTokens` omission is independently proven for both candidates. The
Pi-internal `16384` registry-default fact from I2A Sec. 12 is not
represented anywhere in this offline slice's code or tests -- it remains
source provenance in the design document only, never a gate or scoring
fact here.

**No live activity.** No test in `test_i2_*.py` opens a socket, calls
`httpx`, launches a subprocess, or reads a real environment variable value.
No `Pi`/`Node` executable path is ever invoked. No `AIDO_LITELLM_BASE_URL`
or `AIDO_LITELLM_API_KEY` real value was read at any point while building
or testing this slice -- every "connection value" and every "credential
value" used anywhere in this package is a hard-coded synthetic literal.

## What this does NOT establish

- At the time this phase was accepted, no zero-prompt live gate (I2A
  Sec. 15: Node-direct launch, RPC broker reaching `READY`, H1/H2,
  `get_commands`/`get_state`, the real `/models` listing) had run. (One such
  attempt has since occurred and refused fail-closed before `/models` -- see
  the TOP-LEVEL CORRECTION at the head of this document.)
- No candidate model has ever run. No PASS/FAIL, no ranking, no
  qualification verdict exists for Candidate A or Candidate B.
- 5F3B-Q1/Q2 (the first live candidate sweeps) remain **NOT authorized** and
  cannot execute until a future, separately authorized phase wires this
  offline machinery to a real Pi/Node launch and a real environment reader.
- Whether the B300 LiteLLM proxy actually validates the `Authorization`
  header for this route is still unresolved (I2A Sec. 24 item 1) -- this
  slice implements BOTH the pre-prompt (`INFRASTRUCTURE_REFUSAL`) and
  post-prompt (`INFRASTRUCTURE_CONTAMINATED`) attribution paths so that
  question's eventual answer does not require new code.
- Redaction/scrubbing remain **backstops, not guarantees** here too --
  nothing in I2 claims a retained artifact or a retention-ready diagnostic
  is provably secret-free.

---

# 5F3B-I2-FU1 -- Credential/Route Boundary Integrity Closure

> **AS OF THIS PHASE'S ACCEPTANCE: STILL OFFLINE ONLY. NO ZERO-PROMPT LIVE
> GATE HAD RUN. NO CANDIDATE MODEL HAD RUN. Q1/Q2 REMAINED UNAUTHORIZED.**
> (One zero-prompt live attempt has since occurred -- see the TOP-LEVEL
> CORRECTION at the head of this document. No candidate model has run, then
> or now.)

Independent review of the actual I2 source (not the design document) found
seven concrete implementation gaps between what I2A's architecture requires
and what I2's first cut of code actually enforced. None of them reopen the
accepted architecture -- `$ENV` credential interpolation, the B300 route
choice, the candidate set, the credential-read-ordering concept, the
`maxTokens` policy, the cleanup-classification rule, and the provider-
request/wire-`maxTokens` non-observability policy are all unchanged. FU1
closes exactly the gaps below and nothing else.

## 1. Every I2 secret-bearing object is now repr-safe

Mechanically demonstrated by review: `repr(ConnectionValues(...))` printed
both the base URL and the API key, and `repr(LaunchEnvironment(...))`
printed the entire child environment dict, including the credential value
under `PI_QUALIFICATION_B300_ROUTE_KEY`. Both are now `field(repr=False)`
on every secret-bearing field, each with its own bounded custom `__repr__`
as a second, independent protection.

**`ArtifactSafetyContext` (narrow, explicitly authorized I1 change).** I2 is
the first phase to populate this context with a REAL future value, and its
default dataclass repr printed every populated field. All seven fields are
now `field(repr=False)`, and a custom `__repr__` reports only which fields
were DECLARED (by name), never their values --
`ArtifactSafetyContext(declared_fields=('api_key', 'endpoint_host'))`, for
example. `forbidden_needles()`, `none_declared()`,
`qualification_scrub_check`, exclusive-create emission, and every other I1
scrub/emission semantic are proven unchanged (`test_safety_repr.py`).

`QualificationRouteSecretContext` was already protected from I2's first cut
and is unchanged.

## 2. The `narrow_path` bypass is removed, not defaulted away

`build_child_environment(..., narrow_path=False)` forwarded the ambient PATH
unchanged -- a live contradiction of the frozen I2A child-environment
policy. The parameter is REMOVED (proven by signature introspection); the
narrowed PATH is now unconditional. A synthetic hostile PATH containing
decoy entries (`C:\evil\credential-stealer`, `C:\Users\synthetic\.secret-tools`,
`C:\malicious\payload`) is proven never to survive into the built
environment; only the Node directory, `System32`, and `SystemRoot` ever
appear. `LaunchEnvironment.path_narrowed` remains, always `True`.

## 3. The config generator is secure by construction

Review demonstrated the prior API accepted
`provider_id="openai"` / `model_id="some-unauthorized-model"` /
`credential_env_var_name="OPENAI_API_KEY"` and wrote a valid-looking,
unauthorized `models.json`. `write_qualification_pi_config` now takes only
`model_id` and `base_url` -- `provider_id` and `credential_env_var_name` are
fixed internal constants with NO parameter through which to override them
(proven: calling with either kwarg raises `TypeError` before any file
exists). `model_id` is validated against
`qualification.records.CANDIDATE_MODEL_IDS` -- the single source of truth,
not a third drifting declaration -- BEFORE any directory or file is
created, so an unauthorized model id leaves nothing on disk (proven:
`os.listdir(root) == []` after a rejected call). The locally-duplicated
`CANDIDATE_A_MODEL_ID`/`CANDIDATE_B_MODEL_ID` constants were removed from
`i2_pi_config.py` for the same reason.

## 4. Raw route-check failure text is never retained

`run_offline_route_check` no longer reads `result.failure` at all.
`RouteCheckOutcome` now carries a bounded `failure_code`
(`RouteFailureCode.ROUTE_UNREACHABLE` / `MODEL_NOT_SERVED`), derived purely
from the `reachable`/`configured_model_served` booleans it already
inspected. A regression test injects a `checker.failure` string containing
a synthetic endpoint, a synthetic API key, and literal
`Authorization: Bearer ...` text, and proves none of it appears in the
outcome, `repr(outcome)`, or `str(outcome)` -- and that `RouteCheckOutcome`
has no `failure` attribute at all.

## 5. Missing/blank/malformed connection values are a true pre-prompt refusal

`resolve_connection_after_preflight` now catches `ConnectionValueError`
(missing/blank `AIDO_LITELLM_BASE_URL`/`_API_KEY`) and
`InvalidBaseUrlError` (malformed base URL, item 7) raised while resolving
the connection, and re-raises the SAME bounded `InfrastructureRefusal`
shape every other pre-prompt gate produces
(`gate_name="connection_values"`, `failure_code="CONNECTION_VALUE_MISSING_OR_BLANK"`
or `"CONNECTION_VALUE_INVALID"`). Proven for a missing base URL, a blank API
key, and a malformed base URL -- none of the three low-level exception
types escapes this function's boundary any more.

## 6. Preflight failure detail is a bounded code, not free prose

`PreflightGateResult.detail` (arbitrary caller-authored text) is REMOVED
and replaced by `failure_code`, validated at construction against
`PREFLIGHT_FAILURE_CODES` (a small declared set). `gate_name` is validated
against a `lowercase_with_underscores` identifier pattern. Both
`PreflightGateResult` and `InfrastructureRefusal` reject an unknown code and
a prose-shaped/needle-shaped `gate_name` -- proven directly with synthetic
credential-, endpoint-, and path-shaped strings, none of which can pass the
identifier pattern, so none can ever reach `repr()`/the exception message.

## 7. The B300 base URL is validated before it becomes safety context

`build_secret_context(base_url="not-a-url")` previously produced
`endpoint_host="<unparsed>"`, silently defeating
`ArtifactSafetyContext`'s endpoint-host backstop (a needle that is never
populated can never be matched). The new, single, qualification-owned
`validate_b300_base_url` (in `i2_secret_context.py`, reused by
`i2_credentials.read_connection_values` and `build_secret_context` alike)
requires scheme exactly `http`/`https`, a present hostname, no embedded
username/password, no query string, and no fragment. `extract_endpoint_host`
now raises `InvalidBaseUrlError` for anything that fails validation rather
than ever returning `"<unparsed>"` -- proven across four malformed inputs
(no scheme, blank, unsupported scheme, embedded credentials). The
`InvalidBaseUrlError` message is proven never to echo the offending URL,
host, or embedded credential text.

## 8. The diagnostic-scrub boundary is preserved, not weakened

`prepare_diagnostic_text_for_retention` and I1's `qualification_scrub_check`
are unchanged. Three new integration-style tests feed realistic
route-check-shaped, preflight-shaped, and B300-provider-shaped raw error
text (each carrying a synthetic endpoint and/or API key) through the SAME
scrub path and prove each is refused, while a genuinely safe summary of
each same scenario remains retention-ready. A source-identity test proves
`i2_cleanup.qualification_scrub_check is qualification.safety.qualification_scrub_check`
-- no second scanner exists anywhere in this package.

## Offline suite result (FU1)

```text
353 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(300 at the end of the first I2 offline slice: 225 I1 + 75 I2. FU1 adds 53
new regression tests -- one new file, `test_safety_repr.py`, for the narrow
`ArtifactSafetyContext` repr fix, plus additions to each of the six existing
`test_i2_*.py` modules for the fix it corresponds to. No existing I1 test
was modified, weakened, or removed; every I1-owned test file
[`test_records.py`, `test_lineage.py`, `test_outcomes.py`,
`test_run_validity.py`, `test_scope.py`, `test_report_accuracy.py`,
`test_hard_bar.py`, `test_ranking.py`, `test_baselines.py`,
`test_task_revision.py`, `test_iq1_fixture.py`, `test_iq2_fixture.py`,
`test_iq3_fixture.py`] is byte-for-byte untouched by this closure.)

The frozen `experiments/pi_external_runtime_ar2/tests` suite was re-run,
unmodified: **290 passed, 0 failed**, no `ar2/` file touched.

## API signature changes (intentional; call sites updated, semantics not weakened)

- `i2_environment.build_child_environment`: the `narrow_path` parameter is
  REMOVED (was: optional, default `True`).
- `i2_pi_config.write_qualification_pi_config`: `provider_id` and
  `credential_env_var_name` parameters are REMOVED; the function now takes
  only `experiment_root`, `model_id`, `base_url`.
- `i2_pi_config`: `CANDIDATE_A_MODEL_ID`/`CANDIDATE_B_MODEL_ID` constants are
  REMOVED (use `qualification.records.CANDIDATE_MODEL_IDS` instead).
- `i2_route.RouteCheckOutcome`: the `failure: str | None` field is REMOVED
  and replaced by `failure_code: RouteFailureCode | None`.
- `i2_credentials.PreflightGateResult`: the `detail: str` field is REMOVED
  and replaced by `failure_code: str | None`, validated against
  `PREFLIGHT_FAILURE_CODES`.
- `i2_credentials.InfrastructureRefusal.__init__`: `detail: str = ""` is
  REPLACED by a required `failure_code: str` argument, validated the same
  way.

Every removal narrows an unsafe API surface; none of them reduces test
coverage of any previously-accepted behavior.

## What this does NOT establish (unchanged)

- At the time this phase was accepted, no zero-prompt live gate had run, and
  no candidate model had run. (One zero-prompt live gate attempt has since
  occurred -- see the TOP-LEVEL CORRECTION at the head of this document. No
  candidate model has run, then or now.) No PASS/FAIL, no ranking and no
  qualification verdict exists for Candidate A or Candidate B.
- 5F3B-Q1/Q2 remain **NOT authorized**.
- Redaction/scrubbing remain **backstops, not guarantees**.

---

# 5F3B-I2-FU2 -- Authority + Trusted-Value Closure

> **AS OF THIS PHASE'S ACCEPTANCE: STILL OFFLINE ONLY. NO ZERO-PROMPT LIVE
> GATE HAD RUN. NO CANDIDATE MODEL HAD RUN. Q1/Q2 REMAINED UNAUTHORIZED.**
> (One zero-prompt live attempt has since occurred -- see the TOP-LEVEL
> CORRECTION at the head of this document. No candidate model has run, then
> or now.)

FU1 closed repr/PATH/config-carrier/raw-diagnostic/InfrastructureRefusal/
base-URL-validator gaps. Independent review of the RESULT found one further
class of gap, twice: **a safe factory exists, but the public value object
it returns can still be forged directly**, and **a destructive cleanup API
trusted an arbitrary caller-supplied path with no proof AIDO created it**.
FU2 closes exactly these, and nothing else. No FU1 fix, no I1 invariant, no
I2A architecture decision is reopened.

## A. Generated-config cleanup now requires creation-time authority

Independent review reproduced `scrub_generated_qualification_config`
recursively deleting an arbitrary, caller-supplied directory -- a synthetic
victim directory and its unrelated file were both destroyed.

`write_qualification_pi_config` now writes a fixed, non-secret authority
marker (`.aido_i2_disposable_config`, content
`pi-implementer-qualification-i2-config.v1`) FIRST, before
`settings.json`/`models.json`. `GeneratedQualificationConfig` is now valid
by construction: `__post_init__` calls
`i2_pi_config.verify_generated_config_authority`, which resolves
`config_dir`, requires `settings_path`/`models_path` to be EXACT structural
children (`config_dir/settings.json`, `config_dir/models.json`), and
requires the marker to exist with the exact expected content -- so the
object cannot be built pointing at an arbitrary directory at all.
`scrub_generated_qualification_config` now accepts ONLY that typed object
(never a raw path string) and RE-VERIFIES the same authority immediately
before deleting anything, in case the marker was removed or altered after
construction. Any authority failure raises `CleanupAuthorityError` -- a
bounded reason code only (`MARKER_MISSING`, `MARKER_CONTENT_MISMATCH`,
`SETTINGS_PATH_NOT_STRUCTURAL_CHILD`, `MODELS_PATH_NOT_STRUCTURAL_CHILD`,
`CONFIG_DIR_NOT_A_DIRECTORY`) -- and never echoes the path (a
workspace-absolute path is itself sensitive content).

Proven: an arbitrary victim directory + `important.txt` cannot even be
wrapped in a `GeneratedQualificationConfig` (refused at construction,
victim untouched, byte-identical file content); the SAME victim, reached
via an `object.__new__` bypass of `__post_init__`, is independently refused
at `scrub_generated_qualification_config`'s own re-verification; a parent
experiment root passed in place of the real child config directory is
refused (nothing deleted, both directories remain intact); a marker removed
or tampered with AFTER a valid object was constructed is refused at cleanup
time, before any delete; a genuine generated config cleans up successfully;
and a partially-generated config (marker present, `settings.json`/
`models.json` never written -- an interrupted-write simulation) still
cleans up successfully, because authority depends on the marker, not on
every file existing.

## B. `ConnectionValues` is valid by construction

Independent review demonstrated `ConnectionValues(base_url="not-a-url",
api_key="")` could be constructed directly, and
`resolve_connection_after_preflight` would trust and return it.
`__post_init__` now calls `validate_b300_base_url(base_url)` and requires a
non-blank `api_key` -- direct construction with either invalid value is
now impossible. `resolve_connection_after_preflight` is unchanged in
behavior (it already caught `ConnectionValueError`/`InvalidBaseUrlError`
from `read_connection()`; those now fire at `ConnectionValues.__init__`
time instead of only inside `read_connection_values`'s own pre-checks).
Repr safety (`field(repr=False)` + custom `__repr__`) is unchanged and
re-proven. Proven: a malformed URL and a blank key are each rejected at
direct construction; a valid direct construction succeeds; an injected
`read_connection` callback that TRIES to fabricate an invalid
`ConnectionValues` cannot bypass policy, because the fabrication itself
raises.

## C. `RouteDescriptor` is valid by construction AND revalidated at use

Independent review demonstrated a directly-forged `RouteDescriptor`
(arbitrary `model_id`/`provider_id`/`backend_gateway_class`/
`credential_mechanism`/`credential_env_var_name`, including
`backend_gateway_class="direct_vllm"`) reached `run_offline_route_check`
and could return `passed=True`. A single shared validator,
`_validate_route_descriptor_fields`, is now called from TWO places: (1)
`RouteDescriptor.__post_init__`, so direct construction with any forged
field is impossible; and (2) `run_offline_route_check`, which revalidates
the descriptor at the consumption boundary BEFORE the checker is ever
invoked -- a second, independent defense for a descriptor that reached the
function through any path other than its own constructor.

Proven: each of model id, provider id, `backend_gateway_class` (including
the exact `"direct_vllm"` counterexample), credential mechanism, credential
carrier, and a reversed A/B pairing is individually rejected at
construction; a fully-forged descriptor cannot even be built (checker call
count stays `0`); and a descriptor that bypasses `__post_init__` entirely
(via `object.__new__` + `object.__setattr__`, simulating a path other than
the constructor) is still refused at `run_offline_route_check`'s own
revalidation, before the checker runs (checker call count stays `0` there
too).

## D. `QualificationRouteSecretContext` is valid by construction; factory narrowed

Independent review demonstrated direct construction with `base_url=
"not-a-url"`, `endpoint_host="<unparsed>"`, or a forged
`credential_env_var_name`/`provider_id`/`model_id` bypassed
`build_secret_context` entirely. `__post_init__` now enforces all of:
`validate_b300_base_url(base_url)`; non-blank `api_key`; `endpoint_host ==
extract_endpoint_host(base_url)` (closing the exact `"<unparsed>"`
counterexample); `credential_env_var_name == CREDENTIAL_ENV_VAR_NAME`;
`provider_id == PROVIDER_ID`; `model_id in CANDIDATE_MODEL_IDS.values()`.
`build_secret_context` is narrowed to `(*, base_url, api_key, model_id)` --
`provider_id`/`credential_env_var_name` are no longer parameters at all,
mirroring FU1's identical narrowing of the config generator. Repr safety is
unchanged and re-proven. Proven: each of a malformed base URL, the exact
`"<unparsed>"` endpoint-host forgery, a mismatched endpoint host, a blank
API key, a forged credential carrier, a forged provider id, and an
unauthorized model id is individually rejected at direct construction; the
narrowed factory signature is proven by introspection to contain no route
identity parameter.

## E. The config generator uses the ONE shared base-URL validator

Independent review demonstrated `write_qualification_pi_config(base_url=
"not-a-url")` reached the generated `models.json` unchanged -- the
generator previously only checked for a blank string. It now calls
`i2_secret_context.validate_b300_base_url(base_url)` before any directory
or file is created -- the identical rule set the connection contract and
secret context already enforce, never a second, independently-drifting URL
rule set. Proven: a no-scheme URL, an embedded-username/password URL, a
query string, and a fragment are each rejected with NO directory created
(`os.listdir(root) == []`); valid `http://`/`https://` B300 shapes are
still accepted; the error never echoes the offending URL, host, or embedded
credential text.

## F. `PreflightGateResult` cannot express an impossible state

`passed=True` with a non-`None` `failure_code`, and `passed=False` with
`failure_code=None`, both now raise at construction. Because a failing
gate's `failure_code` is therefore guaranteed present,
`resolve_connection_after_preflight`'s `result.failure_code or
"CHECK_FAILED"` fallback -- a silently-invented code FU1 left in place --
is removed; the function now consumes only a fully coherent result.
Proven: both impossible combinations are rejected; a valid pass and a
valid fail are each accepted, and a valid fail reaches the expected bounded
`InfrastructureRefusal`; every declared code in `PREFLIGHT_FAILURE_CODES`
is individually usable for a failing result.

## G. Unexpected route-check exceptions are bounded

FU1 removed `RouteCheckOutcome.failure` (the checker's own returned
string). Independent review noted a checker that RAISES instead of
returning could still leak arbitrary prose through the exception boundary.
`run_offline_route_check` now wraps ONLY the `checker(...)` call in
`try`/`except Exception`, reducing any raised exception to the new bounded
`RouteFailureCode.ROUTE_CHECK_ERROR` -- never `str(exc)`, `repr(exc)`, or
traceback text. Proven: an injected `RuntimeError("https://host
Authorization: Bearer sk-synthetic-secret")` (the exact counterexample
text) leaves none of that text -- nor the exception type name -- anywhere
in the outcome, `repr(outcome)`, or `str(outcome)`; the same holds for
`ValueError`/`ConnectionError`/`TimeoutError` with distinct hostile
messages; and the descriptor's own `model_id` is still exactly what is
passed to the checker even when it raises (no fallback model).

## Offline suite result (FU2)

```text
400 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(353 at the end of FU1. FU2 adds 47 new regression tests across the six
existing `test_i2_*.py` modules -- no new test file was needed, and no
existing I1/FU1/FU2 test was modified, weakened, or removed except where
this closure intentionally narrowed an unsafe API: `test_blank_base_url_rejected`
in `test_i2_pi_config.py` and `test_i2_secret_context.py` now expect
`InvalidBaseUrlError` in place of the previously-separate blank-string
check, and every `test_i2_cleanup.py` call site was updated to pass the
typed `GeneratedQualificationConfig` object rather than a raw path string.)

The frozen `experiments/pi_external_runtime_ar2/tests` suite was re-run,
unmodified: **290 passed, 0 failed**, no `ar2/` file touched.

## API signature changes (intentional; call sites updated, semantics not weakened)

- `i2_cleanup.scrub_generated_qualification_config`: now takes a
  `GeneratedQualificationConfig` (was: a raw `config_dir: str`).
- `i2_pi_config.write_qualification_pi_config`: `base_url` is now validated
  by `validate_b300_base_url` (was: a bare non-blank check) -- a malformed
  URL now raises `InvalidBaseUrlError`, not `QualificationPiConfigError`.
- `i2_secret_context.build_secret_context`: `provider_id` and
  `credential_env_var_name` parameters are REMOVED; the function now takes
  only `base_url`, `api_key`, `model_id`.
- `i2_environment.PROVIDER_ID`: moved here from `i2_pi_config` (still
  importable from `i2_pi_config` too, via re-export) so `i2_pi_config` and
  `i2_secret_context` can share the base-URL validator without an import
  cycle.
- `i2_credentials.PreflightGateResult`: construction now enforces
  `passed`/`failure_code` coherence (was: only `failure_code` membership,
  when present).
- `i2_credentials.resolve_connection_after_preflight`: no longer
  substitutes `"CHECK_FAILED"` for a missing `failure_code` (impossible by
  construction as of item F).

Every change narrows an unsafe API surface or closes a validation gap;
none of them reduces test coverage of any previously-accepted behavior.

## What this does NOT establish (unchanged)

- At the time this phase was accepted, no zero-prompt live gate had run, and
  no candidate model had run. (One zero-prompt live gate attempt has since
  occurred -- see the TOP-LEVEL CORRECTION at the head of this document. No
  candidate model has run, then or now.) No PASS/FAIL, no ranking and no
  qualification verdict exists for Candidate A or Candidate B.
- 5F3B-Q1/Q2 remain **NOT authorized**.
- Redaction/scrubbing remain **backstops, not guarantees**. The authority
  marker and the trusted-value-object checks in this closure are
  correctness/integrity controls against accidental misuse and forged call
  sites -- not an OS sandbox, and not a guarantee against a determined
  same-process adversary willing to bypass Python's own object model
  (e.g. `object.__new__`/`ctypes`). Every such bypass this closure could
  identify and test is proven refused at the consumption boundary too, but
  no claim of exhaustive adversarial coverage is made.

---

# 5F3B-I2-FU3 -- Run Authority and Cross-Boundary Binding Closure

> **AS OF THIS PHASE'S ACCEPTANCE: STILL OFFLINE ONLY. NO ZERO-PROMPT LIVE
> GATE HAD RUN. NO CANDIDATE MODEL HAD RUN. Q1/Q2 REMAINED UNAUTHORIZED.**
> (One zero-prompt live attempt has since occurred -- see the TOP-LEVEL
> CORRECTION at the head of this document. No candidate model has run, then
> or now.)

FU1/FU2 made every I2 value object valid by construction and closed the
directory-deletion boundary against an arbitrary raw path. Independent
review found FU2's own authority mechanism was itself forgeable (a fixed,
PUBLIC marker string -- copy it into any directory and cleanup would accept
it), and found two remaining boundaries where a caller could still supply a
raw, uncorrelated value instead of a trusted object: the Pi child's config
directory, and its credential. FU3 closes exactly these five things, and
nothing else. No FU1/FU2 fix, no I1 invariant, no I2A architecture decision
is reopened.

## 1. Real per-run authority replaces the public fixed marker

The FU2 marker's authority was ONLY "does this exact fixed string exist in
this file" -- independent review proved this forgeable: create a victim
directory, write the public string into it, and
`GeneratedQualificationConfig` accepted it. Authority is now a fresh,
unpredictable, per-run 128-bit token (`secrets.token_hex(16)`), generated
ONLY by `write_qualification_pi_config`, held on
`GeneratedQualificationConfig.authority_token` as `field(repr=False)` --
never written to disk, never shown in any repr/diagnostic/evidence. The
on-disk marker (schema `pi-implementer-qualification-i2-config.v2`) carries
only a SHA-256 keyed binding of `(token, resolved config_dir)`, computed by
`verify_generated_config_authority`, which every consumption boundary
(`GeneratedQualificationConfig.__post_init__`,
`scrub_generated_qualification_config`, `describe_generated_config`,
`build_child_environment`, `verify_i2_identity_binding`) calls to
independently re-verify authority. Because the binding is keyed on the
directory path too, a marker copied to a DIFFERENT directory recomputes to
a different expected value there and is refused, even with the (never
persisted) genuine token in hand.

Proven: an arbitrary victim directory with no marker, with the OLD FU2
public marker text, or with the correct v2 schema but a fabricated
binding, is refused in all three cases with the victim directory and its
file byte-identical afterward; a marker COPIED verbatim from a genuine
config into a different directory does not authorize that directory (the
required "path-bound authority" regression); a parent-experiment-root
mix-up is refused; a marker removed or tampered with after construction is
refused at cleanup, before any delete; a genuine config -- including a
deliberately partial one (marker present, `settings.json`/`models.json`
never written) -- still cleans up successfully; and the bypass-`__post_init__`
double-check (`object.__new__`) proves `scrub_generated_qualification_config`
itself independently re-verifies, not merely trusting a once-checked object.

## 2. The generator cleans up its own partial failure

If any internal write fails after `mkdir` succeeds (an injected
`OSError` on `settings.json` or `models.json` in the offline tests), a
best-effort verified delete is attempted using the SAME authority the call
just established, before the original exception is re-raised -- so no
caller can be left holding an endpoint-bearing partial config with no
usable cleanup capability. If that verified delete cannot itself be
confirmed (a second, independently-injected `shutil.rmtree` failure),
`QualificationPiConfigCleanupError` is raised instead (chained from the
original failure, bounded reason code only, never echoing the path or the
base URL). Proven for both write-failure injection points and for the
double-failure (cleanup-also-fails) case.

## 3. `PI_CODING_AGENT_DIR` has exactly one source

Independent review passed an arbitrary, global-style path directly as the
former `pi_config_dir: str` parameter and it was accepted unchanged.
`build_child_environment` no longer has that parameter at all -- it
consumes `generated_config: GeneratedQualificationConfig`, re-verifies its
authority at this consumption boundary before trusting it, and sets
`PI_CODING_AGENT_DIR = generated_config.config_dir`. Proven: the parameter
is gone from the signature (introspection); supplying one raises
`TypeError`; `PI_CODING_AGENT_DIR` always equals the bound config's own
directory; and a config whose marker is removed after construction is
refused here too (authority re-verified, not merely trusted).

## 4. The child credential comes from the SAME run-scoped secret context

Independent review proved a caller could hold `SecretContext.api_key =
KEY_A` and pass `credential_value=KEY_B` to the (former)
`build_child_environment` API -- the child would receive `KEY_B` while
`ArtifactSafetyContext` (built from the SAME secret context) would only
ever scrub for `KEY_A`. The `credential_value` parameter is REMOVED; the
carrier's value is sourced only from `secret_context.api_key`. Proven:
`credential_value`/`api_key` do not exist as parameters (introspection);
the child environment always carries exactly the secret context's own key;
and a second, different key never appears anywhere in the built
environment.

## 5. `LaunchEnvironment` is immutable and self-validating

Independent review did `launch.environment["OPENAI_API_KEY"] = "oops"` on
the supposedly-`frozen=True` dataclass and it succeeded, because
`frozen=True` blocks attribute REASSIGNMENT only, not mutation of a
mutable object a field already references. The raw dict is now a private
field (`_raw_environment`, `field(repr=False)`); `environment` is a
read-only `MappingProxyType` property -- assignment or deletion through it
now raises `TypeError`. A genuinely mutable, independent snapshot for an
eventual subprocess-launch boundary is available only via
`as_launch_snapshot()`, which returns a FRESH `dict` copy every call;
mutating a snapshot never affects the retained object or any other
snapshot. `__post_init__` additionally re-validates internal coherence:
`path_narrowed is True` (identity check, so a non-bool stand-in is also
rejected); `included_names` agrees exactly with the environment's own
keys; `PI_CODING_AGENT_DIR` equals the bound `pi_config_dir`; the
credential carrier is present and non-blank; and no forbidden
ambient/vendor/AIDO name is present except the exact carrier. Proven
directly-constructed for each of these five invariants individually.

## 6. Exact `bool` typing for `PreflightGateResult.passed`

Independent review reproduced `PreflightGateResult(passed="false")` being
accepted and treated as truthy by Python's own truthiness rules --
precisely the shape a credential-read authorization gate must never permit.
`__post_init__` now requires `type(passed) is bool` exactly, checked BEFORE
the `if self.passed:` branch, so `"false"`, `"true"`, `1`, `0`, and `None`
are all rejected outright. Proven individually for each, plus that the
existing pass/fail coherence rule (a valid `True` carries no code; a valid
`False` requires one) is unchanged, and that a `"false"`-valued gate
propagated through `resolve_connection_after_preflight` raises rather than
silently authorizing anything.

## 7. The route-check input is a trusted object, with no second URL validator

Independent review passed `base_url="not-a-url"` straight into
`run_offline_route_check` and a synthetic checker could still return
`passed=True`. The function no longer takes a raw `base_url: str` -- it
consumes an already-valid `QualificationRouteSecretContext` (its `base_url`
already validated by the SAME `validate_b300_base_url` at construction),
with one defensive re-check of that same function at the consumption
boundary (never a second validator: a source-identity test proves
`i2_route.validate_b300_base_url is i2_secret_context.validate_b300_base_url`).
Proven: a malformed URL cannot even reach `run_offline_route_check` because
it cannot survive `QualificationRouteSecretContext` construction; and a
secret context that bypasses `__post_init__` (`object.__new__`) is still
refused before the checker runs (checker call count `0` in both cases).

## 8. Exact `bool` typing for the route checker's result, and `RouteCheckOutcome` coherence

Independent review reproduced `result.reachable = "false"` /
`result.configured_model_served = "false"` being coerced by a bare
`bool(...)` call into `True`/`True` and an overall PASS. Both fields are
now required to be `type(...) is bool` exactly; anything else (a string,
`1`/`0`, a missing attribute) fails closed as the new
`RouteFailureCode.ROUTE_CHECK_INVALID_RESULT`, and the raw non-bool value
is never read into, or retained by, the outcome. `RouteCheckOutcome` itself
gained a `__post_init__`: all three boolean fields must be exact `bool`;
`passed=True` requires `reachable=configured_model_served=True` with no
`failure_code`; `passed=False` always requires a declared `failure_code`.
Proven: `"false"`/`"false"`, `1`/`0`, one-field-only-non-bool, and a
missing-attribute result all fail closed (never PASS); a genuine
`True`/`True` result still passes; and each of the five ways to directly
construct an incoherent `RouteCheckOutcome` is individually rejected.

## 9. Config/secret/route identity binding

A new, narrow module, `qualification.i2_composition`
(`verify_i2_identity_binding`), is the ONE shared composition check that
three independently-valid-by-construction objects -- a
`GeneratedQualificationConfig`, a `QualificationRouteSecretContext`, and a
`RouteDescriptor` -- agree with EACH OTHER once composed for one run: it
re-verifies the generated config's own authority first, then requires
`secret_context.model_id`/`generated_config.model_id` ==
`route_descriptor.model_id`, `secret_context.provider_id`/
`generated_config.provider_id` == `route_descriptor.provider_id`, and the
generated config's own recorded `baseUrl` == `secret_context.base_url`
(compared in memory only, never rendered). Deliberately not a generic
runtime/integration framework -- one function, one job; a regression test
confirms no `AgentRuntime`/`RuntimeAdapter`/`GenericRuntime` name exists in
the module. Proven: a matching triple for each candidate is accepted; each
of a secret-context model mismatch, a generated-config model mismatch, and
a generated-config base-URL mismatch is individually rejected before any
live-capable action, with no base URL or credential echoed in the error;
and a tampered generated config's authority failure is what actually fires
first (re-verification happens before any identity comparison).

## 10. `ArtifactSafetyContext` population is now fully explicit

`QualificationRouteSecretContext.to_safety_context`'s four run-sensitive
parameters (`broker_token`, `pipe_name`, `capability_id`,
`workspace_absolute_path`) LOSE their `= None` defaults -- every caller
must now state each field explicitly, passing `None` for a genuinely
offline/no-broker case rather than silently omitting it. This mirrors the
discipline `ArtifactSafetyContext.none_declared()` already established for
I1. Proven: calling with zero or partial arguments raises `TypeError`;
calling with all four explicit (including `None`) succeeds and behaves
identically to the old default-driven call.

## 11. `describe_generated_config` takes the typed object only

The former `settings_path`/`models_path` string parameters could point at
ANY JSON document, letting a caller manufacture evidence-ish
provider/model/env-var-name fields from an arbitrary file.
`describe_generated_config` now takes only `generated:
GeneratedQualificationConfig`, re-verifies its authority before reading
anything, and reports the same secret-free structural facts as before
(never the base URL, host, or resolved apiKey value). Proven: the
signature accepts only `generated` (introspection); a forged capability
object pointed at an attacker-authored JSON pair is refused
(`CleanupAuthorityError`) before any of that JSON is ever parsed.

## Import layering note

A new leaf module, `qualification.i2_identity`, now holds
`CREDENTIAL_ENV_VAR_NAME`/`PROVIDER_ID` (unchanged in value; moved from
`i2_environment`, which still re-exports both for backward compatibility).
This exists solely so `i2_environment` can import
`i2_pi_config.GeneratedQualificationConfig` and
`i2_secret_context.QualificationRouteSecretContext` (items 3/4) without an
import cycle, since both of those modules also need the same fixed
identity constants. No behavior changed; every constant's VALUE is
unchanged from I2A/FU1/FU2.

## Offline suite result (FU3)

```text
462 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(400 at the end of FU2. FU3 adds 62 new regression tests: one new file,
`test_i2_composition.py`, for item 9's composition validator, plus
additions to every one of the six existing `test_i2_*.py` modules for the
closure it corresponds to. No existing I1/FU1/FU2 test was weakened or
removed except where this closure intentionally narrowed an unsafe API --
every such removal is listed below, and every affected test call site was
updated to the new, safer shape rather than deleted.)

The frozen `experiments/pi_external_runtime_ar2/tests` suite was re-run,
unmodified: **290 passed, 0 failed**, no `ar2/` file touched.

## API signature changes (intentional; call sites updated, semantics not weakened)

- `i2_pi_config.GeneratedQualificationConfig`: gained `provider_id`,
  `model_id`, and `authority_token` (`field(repr=False)`) fields; the
  authority marker's on-disk shape changed from FU2's fixed public text to
  FU3's JSON `{schema, binding}` document (`AUTHORITY_MARKER_CONTENT` is
  REMOVED; `AUTHORITY_MARKER_SCHEMA` replaces it).
- `i2_pi_config.verify_generated_config_authority`: gained a required
  `authority_token` keyword argument.
- `i2_pi_config.describe_generated_config`: now takes `generated:
  GeneratedQualificationConfig` (was: `settings_path`/`models_path` raw
  strings).
- `i2_environment.build_child_environment`: `pi_config_dir`/
  `credential_value` string parameters are REMOVED; replaced by
  `generated_config: GeneratedQualificationConfig` and `secret_context:
  QualificationRouteSecretContext`.
- `i2_environment.LaunchEnvironment`: the `environment` dataclass field is
  RENAMED to the private `_raw_environment`; `environment` is now a
  read-only property. Gained a `pi_config_dir` field and an
  `as_launch_snapshot()` method.
- `i2_secret_context.QualificationRouteSecretContext.to_safety_context`:
  all four parameters LOSE their `= None` defaults.
- `i2_route.run_offline_route_check`: `base_url: str` is REMOVED; replaced
  by `secret_context: QualificationRouteSecretContext`.
- `i2_route.RouteCheckOutcome`: gained a `__post_init__` coherence gate;
  gained `RouteFailureCode.ROUTE_CHECK_INVALID_RESULT`.
- `i2_environment.PROVIDER_ID` / `i2_pi_config.PROVIDER_ID`: unchanged
  value, moved to the new `i2_identity` leaf module (both re-export it, so
  existing import sites are unaffected).

Every change narrows an unsafe API surface or closes a validation gap;
none of them reduces test coverage of any previously-accepted behavior.

## What this does NOT establish (unchanged, as of FU3)

- At the time this phase was accepted, no zero-prompt live gate had run, and
  no candidate model had run. (One zero-prompt live gate attempt has since
  occurred -- see the TOP-LEVEL CORRECTION at the head of this document. No
  candidate model has run, then or now.) No PASS/FAIL, no ranking and no
  qualification verdict exists for Candidate A or Candidate B.
- 5F3B-Q1/Q2 remain **NOT authorized**.
- Redaction/scrubbing, and every trusted-value-object check in this
  closure, remain correctness/integrity controls -- not an OS sandbox, and
  not a guarantee against a determined same-process adversary willing to
  bypass Python's own object model.

## 5F3B-I2-FU3A -- issuance authority, content integrity, mandatory binding

FU3's authority scheme still had a gap: the marker is
`SHA256(caller-supplied token + canonical path)`, and nothing ever required
that token to be one I2 itself generated. Independent review reproduced this
exactly: mint an arbitrary token, hand-compute the same public formula, write
a marker into an arbitrary victim directory alongside a hand-authored
`settings.json`/`models.json` -- `GeneratedQualificationConfig` construction
(and therefore cleanup) accepted it. Independent review also reproduced a
second gap: `verify_i2_identity_binding` and `build_child_environment` /
`run_offline_route_check` trusted a `GeneratedQualificationConfig`'s
`provider_id`/`model_id` FIELDS at face value, so a genuine token/path pair
could be relabeled to a different candidate's identity, and a mismatched
generated-config/secret-context/route-descriptor triple could reach a
launch-capable consumption boundary without ever going through the (merely
optional) composition helper. FU3A closes all of this without adding a fixer,
a live gate, or any new architecture.

### 1. A genuine, process-local I2 issuance fact (item A)

A new leaf module, `qualification.i2_issuance`, holds a plain,
**process-local, in-memory-only** registry (`dict[(token, resolved_path),
IssuanceRecord]`) -- never persisted, never an evidence artifact, no claim of
surviving a process restart. `write_qualification_pi_config` now calls
`i2_issuance.register_issuance(token, config_dir, provider_id, model_id)`
immediately after `mkdir`, before the marker is even written, and
`i2_issuance.finalize_issuance(token, config_dir, settings_sha256,
models_sha256)` only once both files are successfully on disk.
`i2_pi_config.verify_cleanup_authority` (renamed from FU3's
`verify_generated_config_authority`) now requires, in addition to every FU3
marker/path check: the token is currently present in the registry for that
EXACT resolved directory (`NOT_ISSUED_BY_I2` otherwise), and the registered
`provider_id`/`model_id` agree with what the caller claims
(`ISSUED_METADATA_MISMATCH` otherwise). A self-forged token with a
correctly-computed marker but no registry entry now fails closed at
construction, before anything is ever deleted -- proven by
`test_self_forged_token_with_hand_built_marker_but_no_issuance_is_refused`
and its cleanup-boundary counterpart in `test_i2_cleanup.py`, and by
`test_self_forged_token_with_hand_built_marker_refused_via_public_api` in
`test_i2_pi_config.py`. The victim directory and its unrelated file are
byte-identical afterward in every case.

### 2. Cleanup authority vs. complete content integrity (item B)

`i2_pi_config` now exposes two distinct checks:

- `verify_cleanup_authority` -- marker/path binding + genuine registry
  presence + issued-metadata agreement. Enough to authorize a DELETE. Used
  by `GeneratedQualificationConfig.__post_init__` and by
  `i2_cleanup.scrub_generated_qualification_config`. Deliberately does
  **not** require the issuance record to be finalized, so a partially
  generated (marker-only) config -- exactly the shape the generator's own
  self-cleanup-on-failure path produces -- remains cleanable.
- `verify_generated_config_integrity` -- calls `verify_cleanup_authority`
  first, then additionally requires the record to be FINALIZED and the
  CURRENT on-disk SHA-256 of both `settings.json`/`models.json` to still
  match the digests recorded at finalization time. Used by every
  launch-capable consumption path: `i2_environment.build_child_environment`,
  `i2_pi_config.describe_generated_config`, and
  `i2_composition.verify_i2_identity_binding`.

### 3. Finalized config is content-bound (item C)

After both files are written successfully, their exact on-disk SHA-256
digests (computed from the bytes actually read back from disk -- not from
the pre-write in-memory string, because `Path.write_text`'s universal-newline
translation means those can differ on Windows) are recorded via
`finalize_issuance`. Six new regression tests in `test_i2_pi_config.py` each
tamper ONE thing after a successful generation -- the `apiKey` literal, the
model id, an added `maxTokens`, the `baseUrl`, and the `settings.json` retry/
trust policy -- and each is refused by `verify_generated_config_integrity`
(`SETTINGS_CONTENT_MISMATCH` / `MODELS_CONTENT_MISMATCH`), by
`build_child_environment`, and by `describe_generated_config`.
`test_tampered_config_can_still_be_cleaned_up` proves the SAME tampered
object remains cleanable via `verify_cleanup_authority`, so a tampered but
genuinely-issued config is never stranded.

### 4. Metadata is bound to the issued config (item D)

`GeneratedQualificationConfig.__post_init__`'s call to
`verify_cleanup_authority` (item A's metadata-agreement check) means a
genuine token/path pair can no longer be paired with a relabeled
`provider_id`/`model_id` at construction time at all
(`test_genuine_config_cannot_be_relabeled_to_a_different_model_id`,
`..._provider_id`), and `verify_i2_identity_binding` refuses it again,
independently, for an object that bypassed `__post_init__`
(`test_relabeled_generated_config_bypassing_post_init_still_refused_at_composition`).

### 5. Composition checks the actual finalized config (item E)

`verify_i2_identity_binding` now calls `verify_generated_config_integrity`
FIRST (not the old marker-only re-check), so a config whose `models.json` was
edited on disk after generation -- even with the genuine token, even with
consistent dataclass fields -- is refused before any field comparison is
trusted (`test_binding_refuses_content_tampered_generated_config`). Base URLs
are still never rendered in any failure.

### 6. Mandatory binding at consumption boundaries (item F)

`build_child_environment` and `run_offline_route_check` each now perform
their own local `provider_id`/`model_id` (and, for the environment builder,
`baseUrl`) agreement check against the run's secret context, BEFORE doing
anything else -- so a caller who skips `verify_i2_identity_binding` entirely
can no longer build a Candidate-A environment against a Candidate-B secret
context, or run a Candidate-A route check against a Candidate-B secret
context. Required regressions:
`test_build_child_environment_refuses_mismatched_generated_and_secret_context`
(environment builder raises `EnvironmentPolicyError`) and
`test_run_offline_route_check_refuses_mismatched_descriptor_and_secret_context`
(checker call count remains `0`). `verify_i2_identity_binding` remains the
one full triple check, still available for a caller doing all three
comparisons at once.

### 7. `LaunchEnvironment` breaks external mutable aliases (item G)

Independent review did `LaunchEnvironment(_raw_environment=raw, ...)`, then
`raw["OPENAI_API_KEY"] = "evil"` on the CALLER's own dict, and the mutation
was visible through `launch.environment` -- `frozen=True` only blocks
attribute reassignment, never mutation of an object a field already points
at, and the constructor had never copied it. `__post_init__` now replaces
`self._raw_environment` with a fresh `dict` copy of whatever was passed in,
as its very first action, before any validation runs. Proven:
`test_constructor_dict_mutation_after_construction_does_not_affect_launch_environment`
mutates the original dict after construction and asserts no effect; existing
`environment[...] = ...` (`TypeError`) and `as_launch_snapshot()`
independence tests are re-run unchanged and still pass.

### 8. Generator failure before the marker leaves nothing (item H)

The fresh authority token is now generated BEFORE `mkdir`, so the one
failure-prone step that can fail before ANY authority exists leaves nothing
on disk to clean up. `test_token_generation_failure_leaves_no_directory_at_all`
monkeypatches `secrets.token_hex` to raise and asserts the experiment root
stays completely empty.

### 9. Safe description requires complete integrity (item I)

`describe_generated_config` now calls `verify_generated_config_integrity`
(not the old cleanup-only check), so a tampered or merely partial config can
never have its bytes parsed and reported as though they were still what I2
wrote (`test_describe_generated_config_refuses_tampered_content`).

### Offline suite result (FU3A)

```text
496 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(462 at the end of FU3. FU3A adds 34 new regression tests: one new file,
`test_i2_issuance.py` (10 tests) for the registry's own contract, plus
additions to `test_i2_pi_config.py`, `test_i2_cleanup.py`,
`test_i2_composition.py`, `test_i2_environment.py`, and `test_i2_route.py`
for the closure each corresponds to. No existing test's assertion was
weakened; the one existing test whose SETUP had become indistinguishable
from the attack scenario this closure fixes
(`test_partially_generated_config_with_valid_marker_can_still_be_cleaned`)
was updated to also perform genuine issuance registration, so it continues
to test "a legitimately partial config is still cleanable" rather than "a
self-forged token is accepted".)

The frozen `experiments/pi_external_runtime_ar2/tests` suite was re-run,
unmodified: **290 passed, 0 failed**, no `ar2/` file touched.

### API signature changes (intentional; call sites updated, semantics not weakened)

- `i2_pi_config.verify_generated_config_authority` is RENAMED to
  `verify_cleanup_authority` and gains required `provider_id`/`model_id`
  keyword arguments; it now returns the matched `IssuanceRecord` (previously
  returned `None`). No test imported the old name directly.
- `i2_pi_config` gains `verify_generated_config_integrity` (new function).
- New module `qualification.i2_issuance` (leaf; register/finalize/lookup/
  discard + `IssuanceRecord`/`IssuanceError`).
- `i2_environment.LaunchEnvironment.__post_init__` now copies
  `_raw_environment` before validating (previously validated the caller's
  own dict reference directly).

Every change narrows an unsafe API surface or closes a validation gap; none
of them reduces test coverage of any previously-accepted behavior.

### What this does NOT establish (unchanged)

- At the time this phase was accepted, no zero-prompt live gate had run, and
  no candidate model had run. (One zero-prompt live gate attempt has since
  occurred -- see the TOP-LEVEL CORRECTION at the head of this document. No
  candidate model has run, then or now.) No PASS/FAIL, no ranking and no
  qualification verdict exists for Candidate A or Candidate B.
- 5F3B-Q1/Q2 remain **NOT authorized**.
- The `i2_issuance` registry is an in-process authority fact, not evidence,
  and not a security boundary against a same-process adversary willing to
  use `object.__new__`/`object.__setattr__` or to import and call this
  package's own underscored internals to bypass Python's own object model --
  exactly the same boundary every other FU2/FU3/FU3A trusted-value-object
  check already accepted. The objective throughout is a robust
  orchestration boundary against supported-API misuse and filesystem
  tampering, not an in-process security sandbox.
- Redaction/scrubbing, and every trusted-value-object check in this
  closure, remain correctness/integrity controls -- not an OS sandbox.

## 5F3B-I2-FU3B -- issuance registry encapsulation closure

FU3A's registry closed the "self-forged token" gap, but its own mutation
functions -- `register_issuance`, `finalize_issuance`, `discard_issuance` --
were PUBLIC module-level functions. Independent review reproduced two
distinct attacks against that public surface, using ONLY it (no
`object.__new__`, no private-global mutation, no live activity):

1. **Self-issuance.** Call the public `register_issuance` directly, for an
   arbitrary caller-chosen token, an arbitrary victim directory, and
   arbitrary provider/model metadata. Every downstream check (marker
   binding, registry presence, metadata agreement) then passes normally,
   because the registry only ever proved "someone called
   `register_issuance`", never "I2's own generator issued this". The victim
   directory and its unrelated `important.txt` were both deleted.
2. **Re-finalization.** After a genuine config was finalized and then
   tampered on disk (so `verify_generated_config_integrity` correctly
   returned `MODELS_CONTENT_MISMATCH`), calling the public
   `finalize_issuance` a second time, with the tampered file's own digest,
   silently overwrote the trusted digest and made
   `verify_generated_config_integrity` pass again.

Two smaller findings rode along: `lookup_issuance` returned the actual
mutable registry object, so `record.models_sha256 = <tampered>` changed the
registry directly; and `IssuanceRecord`'s default repr rendered both the
token and the canonical absolute path, contradicting FU3A's own "the token
is never rendered" claim.

### 1. Public issuance mutation API removed (item A)

`qualification/i2_issuance.py` now exposes only `_register_issuance`,
`_finalize_issuance`, `_lookup_issuance`, `_discard_issuance` -- all
underscore-prefixed. `i2_pi_config.py` and `i2_cleanup.py` are its only
callers (both updated to the new names; no other production code imported
the old ones). Per the FU3A/FU3B threat boundary, this is explicitly NOT a
defense against a caller that deliberately imports underscored internals --
that stays out of scope -- it is the removal of a PUBLIC, SUPPORTED
capability a well-behaved caller could misuse without any such bypass.
`test_no_public_register_finalize_discard_or_lookup_api` /
`test_no_public_issuance_mutation_api_exists` prove the old names are gone
structurally (`not hasattr(...)`).

### 2. `IssuanceRecord` is immutable (item B)

`IssuanceRecord` is now `@dataclass(frozen=True)`. `_finalize_issuance`
replaces the registry's entry with a freshly constructed record
(`dataclasses.replace`) rather than mutating fields on an existing instance;
a record a caller obtained from an earlier `_lookup_issuance` call before
finalization is provably unaffected by a later finalization
(`test_finalize_replaces_the_registry_entry_not_the_old_returned_object`).
Attempting `record.models_sha256 = ...` on a returned record now raises
`dataclasses.FrozenInstanceError`
(`test_issuance_record_is_a_frozen_dataclass`,
`test_mutating_a_returned_record_cannot_change_the_registry`).

### 3. Finalization is one-shot (item C)

`_finalize_issuance` now checks `record.is_finalized` before replacing
anything: a second finalization for an already-finalized token raises
`IssuanceError("ISSUANCE_ALREADY_FINALIZED")` and changes nothing.
`test_second_finalization_of_the_same_token_is_refused` and
`test_second_finalization_never_replaces_the_trusted_digests` prove this at
the registry level; `test_tamper_then_reattempted_finalization_cannot_restore_integrity_pass`
(in `test_i2_pi_config.py`) reproduces the EXACT independent-review attack
end to end: generate a genuine config, tamper `models.json`, confirm
`verify_generated_config_integrity` fails, attempt re-finalization with the
tampered file's own digest, confirm that is refused
(`ISSUANCE_ALREADY_FINALIZED`), confirm integrity is STILL refused
afterward (`MODELS_CONTENT_MISMATCH`, unchanged), and confirm the tampered-
but-genuinely-issued config remains cleanable.

### 4. Token uniqueness (item D)

The registry is now keyed by **token alone**
(`dict[str, IssuanceRecord]`, was `dict[(token, path), IssuanceRecord]`) --
one authority token represents exactly one issued config. A token already
registered for ANY path (the same path or a different one) is refused
(`ISSUANCE_ALREADY_REGISTERED`) -- internal capability coherence, not an
authorization/version gate, exactly as specified. `_lookup_issuance`,
`_finalize_issuance`, and `_discard_issuance` each still check that the
SUPPLIED path agrees with the record's own canonical path, so a genuine
token used against the wrong directory still resolves to "no issuance here"
rather than leaking cross-directory authority.

### 5. Repr safety (item E)

`IssuanceRecord.token` and `.canonical_config_dir` are `field(repr=False)`
*and* the class defines its own bounded `__repr__` -- two independent
reasons neither can ever render. The acceptable shape from the design is
matched exactly:
`IssuanceRecord(provider_id='...', model_id='...', finalized=True)`.
`test_issuance_record_repr_never_contains_token_or_path` and
`test_issuance_record_repr_shows_only_provider_model_and_finalized` prove
this, including for a token deliberately shaped to look like a leaked
secret.

### 6. Public-surface regression (item F)

Both `test_i2_issuance.py` (`test_no_public_register_finalize_discard_or_lookup_api`)
and `test_i2_pi_config.py` (`test_no_public_issuance_mutation_api_exists`)
assert `not hasattr(i2_issuance, name)` for all four old public names.
`_lookup_issuance` was made private too, per the design's "if lookup is not
needed outside package internals, make it private" -- it is needed only by
`i2_pi_config`, within the same package.

### 7. Self-issuance victim attack, using only the public API (item G)

`test_self_issued_victim_attack_refused_using_only_public_api` is the
decisive regression: it first asserts `register_issuance` does not exist on
the module at all, then builds an arbitrary victim directory + `important.txt`
+ a caller-chosen token + a marker whose binding is computed with the exact
documented public formula (`_compute_authority_binding`, itself not a
secret -- the FORMULA was always public; only the *registration fact* is
now unreachable), and attempts `GeneratedQualificationConfig` construction
through the ordinary public constructor. Refused `NOT_ISSUED_BY_I2`; the
victim directory, `important.txt`, and its two placeholder JSON files are
byte-identical afterward.

### 8/9. Genuine generation still works (items H)

`test_genuine_generation_still_passes_integrity_builds_and_describes`
exercises a real `write_qualification_pi_config` run end to end through
`verify_generated_config_integrity`, `build_child_environment`, and
`describe_generated_config` -- all still pass unchanged. Every pre-existing
FU1-FU3A test that exercises the generator, cleanup, environment, route, or
composition paths was re-run unmodified and still passes (see suite result
below), proving the encapsulation closure is a pure internal refactor of
`i2_issuance`'s access surface, not a behavior change for any legitimate
caller.

### 10. Cleanup discards issuance (item 10)

`test_successful_cleanup_discards_issuance_and_deauthorizes_the_object`:
after `scrub_generated_qualification_config` verifies removal, the exact
same `GeneratedQualificationConfig` object can no longer pass
`verify_cleanup_authority` (the directory itself is gone), and a white-box
`_lookup_issuance` confirms the registry entry itself was discarded, not
merely orphaned.

### 11. Package status docstring corrected (item I)

`qualification/__init__.py`'s top docstring previously said B300 routing,
credentials, and a Pi provider config were "not implemented here". That was
stale as of 5F3B-I2A. It now states plainly that 5F3B-I2's offline
route/credential machinery (I2-1 through I2-6, hardened through
FU1/FU2/FU3/FU3A/FU3B) is implemented, fully offline, and separately states
that the live zero-prompt gate, Category-B, and Q1/Q2 remain NOT
implemented/NOT authorized, and that no candidate model has ever been run.
No package constant (`PACKAGE_ID`, `RECORD_VERSION`, etc.) was changed.

### Offline suite result (FU3B)

```text
514 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(496 at the end of FU3A. FU3B adds 18 new regression tests: 13 new/rewritten
in `test_i2_issuance.py` beyond FU3A's original 10 -- the FU3A suite's
`test_i2_issuance.py` was fully rewritten to white-box the now-private
internals, since none of its old public-API calls compile anymore -- plus 5
new tests in `test_i2_pi_config.py` for the public-surface, self-issuance,
re-finalization, genuine-generation, and cleanup-discard regressions. One
existing FU3A test, `test_partially_generated_config_with_valid_marker_can_still_be_cleaned`,
already called the (then-public) `register_issuance` directly as a
legitimate white-box setup step for simulating a partial write; it now calls
`_register_issuance` -- a rename only, not a behavior or assertion change.
No existing test's assertion was weakened.)

The frozen `experiments/pi_external_runtime_ar2/tests` suite was re-run,
unmodified: **290 passed, 0 failed**, no `ar2/` file touched.

### API signature changes (intentional; call sites updated, semantics not weakened)

- `i2_issuance.register_issuance` / `finalize_issuance` / `discard_issuance`
  / `lookup_issuance` are REMOVED from the public surface, replaced by
  `_register_issuance` / `_finalize_issuance` / `_discard_issuance` /
  `_lookup_issuance`. `i2_pi_config.py` and `i2_cleanup.py` (this package's
  only two legitimate callers) were updated to the new names.
- `i2_issuance.IssuanceRecord` is now `@dataclass(frozen=True)` (was a
  plain mutable `@dataclass`) and defines its own `__repr__` (was the
  default dataclass repr).
- `i2_issuance`'s internal registry key changed from `(token, canonical
  path)` to `token` alone; every public-facing behavior (a wrong token, or
  a genuine token used against the wrong path, both resolve to "no
  issuance") is unchanged, because `_lookup_issuance`/`_finalize_issuance`/
  `_discard_issuance` still check path agreement explicitly.
- New `IssuanceError` reason codes: `ISSUANCE_ALREADY_FINALIZED`,
  `PATH_MISMATCH` (both new to `_finalize_issuance`).

Every change narrows an unsafe API surface or closes a validation gap; none
of them reduces test coverage of any previously-accepted behavior, and none
of it reopens the accepted I2A/FU1/FU2/FU3/FU3A architecture (marker/digest
scheme, cleanup design, environment/config/route/composition designs, token
policy all unchanged).

### What this does NOT establish (unchanged)

- At the time this phase was accepted, no zero-prompt live gate had run, and
  no candidate model had run. (One zero-prompt live gate attempt has since
  occurred -- see the TOP-LEVEL CORRECTION at the head of this document. No
  candidate model has run, then or now.) No PASS/FAIL, no ranking and no
  qualification verdict exists for Candidate A or Candidate B.
- 5F3B-Q1/Q2 remain **NOT authorized**.
- The threat boundary is unchanged from FU3A: this closes PUBLIC-API misuse
  (the two attacks independent review actually reproduced), not a defense
  against a same-process adversary willing to import this package's own
  underscored internals, mutate private module globals, or use
  `object.__new__`/`object.__setattr__` to bypass Python's own object
  model. The objective remains a robust orchestration boundary, not an
  in-process security sandbox.
- Redaction/scrubbing, and every trusted-value-object check in this
  closure, remain correctness/integrity controls -- not an OS sandbox.

---

# 5F3B-I2B / I2B-FU1 -- Category-B Runtime Authority + Lifecycle Closure (Offline Only)

> **AS OF THIS PHASE'S ACCEPTANCE: I2B CONTROLLER WIRED OFFLINE. CATEGORY-B
> LIVE EXECUTION NOT YET RUN. NO CANDIDATE MODEL RUN. Q1/Q2 NO-GO.** (One
> zero-prompt Category-B live attempt has since occurred -- see the TOP-LEVEL
> CORRECTION at the head of this document. No candidate model has run, then
> or now.)

I2-1 through I2-6 (hardened through FU1/FU2/FU3/FU3A/FU3B) built the offline
objects a future live qualification run would need. I2B assembles them into
the orchestration SHAPE for the Category-B zero-prompt gates (I2A design
Sec. 15) -- and only that shape. **5F3B-I2B-FU1 rebuilt that shape against
the frozen AR2/O1 runtime lifecycle**, because the initial I2B controller
could not mechanically prove several things it appeared to claim. This
section records the corrected slice; the initial controller's API is
superseded and was not preserved for compatibility.

## Pre-coding adversarial findings against the initial I2B controller

Every one of these was reproduced against the initial controller's source
before any new code was written.

1. **The terminal outcome ignored lifecycle closure.** `outcome` was decided
   solely from `gate_statuses["broker_ready"] == "PASSED"`, computed BEFORE
   teardown, cleanup and the evidence scrub ran. A run whose teardown failed,
   whose config cleanup was unverified, or whose evidence was refused still
   returned `CATEGORY_B_GATE_PASSED`, and its evidence still recorded
   `compatibility_gate_passed: true`.
2. **The broker was confirmed LAST, contradicting frozen O1.** `broker_ready`
   sat after the route check, at the end of the sequence. Frozen O1's
   `run_o1.phase_handshake`/`phase_case` mint `BrokerBinding`, start
   `BrokerServer`, observe `STATE_READY`, and only THEN call
   `launch_and_handshake(..., pipe_name=server.pipe_name,
   capability_id=binding.capability_id, token=binding.token)` -- the launch
   writes that binding into the disposable extension. Broker readiness is a
   PRECONDITION of the launch, not a postcondition of the run. I2A Sec. 15's
   numbered list is a checklist, not a dependency graph; the frozen runtime
   fact wins.
3. **No resource authority existed at all.** `h1_check()`, `get_commands()`,
   `get_state()`, `broker_ready()` and `teardown()` were unrelated
   NO-ARGUMENT callbacks. Two individually valid observations could describe
   two different runtime instances; a caller could supply runtime A's
   launcher and runtime B's teardown; and nothing was structurally
   detectable.
4. **H1 and the tool registry came from two unrelated observations.** Frozen
   AR2 proves H1 FROM the `get_commands` response --
   `ar2.handshakes.evaluate_extension_identity(commands,
   extension_entry=...)` takes that response's command list as its argument.
   Modelling H1 as its own callback was never faithful to the seam.
5. **A passing run with no observable Pi version passed.**
   `RpcLaunchOutcome.observed_pi_version` was `str | None` and influenced
   nothing; `None` (or a blank string) still passed.
6. **Four independently required facts were collapsed into one caller
   boolean.** I2A Sec. 15 items 1-4 (Pi installed/version, RPC launch shape,
   required flags accepted, LF JSONL correlation) were all folded into
   `RpcLaunchOutcome.gate.passed`, so AIDO could not prove which fact was
   observed.
7. **I2A gate 8 was never established.** `PROTOCOL_OR_EXTENSION_ERROR` was a
   declared failure code that no code path could ever produce.
8. **The tool registry comparison collapsed duplicates.**
   `frozenset(observed) == AUTHORIZED_TOOL_NAMES` accepted
   `("aido_read", "aido_read", "aido_edit")`, and could not distinguish a
   duplicate from a genuine pair.
9. **The result and the evidence were mutable after validation.**
   `gate_statuses` was typed `Mapping[str, str]` but held a real `dict`, so
   `result.gate_statuses["broker_ready"] = "PASSED"` silently rewrote a
   validated result. `CategoryBEvidenceResult.evidence` was the very dict
   that had been scrub-checked, handed out by reference, and `scrub` was a
   mutable dict whose `clean` key could be flipped.
10. **The safety context was silently truncated.**
    `secret_context.to_safety_context(broker_token=None, pipe_name=None,
    capability_id=None, workspace_absolute_path=None)` was hard-coded, so a
    live run's real broker binding and workspace path would never be
    declared as scrub needles -- exactly how a binding survives into a
    retained artifact. The README's "full `ArtifactSafetyContext`" claim was
    therefore not established.
11. **A partial launch could strand a resource with no authority to close
    it,** and there was no broker teardown anywhere in the controller.
12. **An adapter returning `None` crashed the controller.** `_safe_call`
    conflated "raised" with "returned an unexpected value"; an adapter that
    simply returned `None` recorded no failure at all, left `failed_gate`
    unset, and then raised an unbounded `ValueError` from
    `CategoryBControllerResult.__post_init__`. That is a fail-open into a
    crash, not a refusal.

## What was built

Two modules and one test module:

- `qualification/i2b_session.py` -- the narrow, I2B-owned run-scoped
  authority and bounded observation value objects. Deliberately **not** a
  generic `AgentRuntime`/`RuntimeAdapter` framework: no registry, no plugin
  system, no lifecycle base class, no capability negotiation, no reusable
  transport, and no interface a second runtime could be registered against.
  A LEAF module -- it imports no other `qualification` module.
- `qualification/i2b_controller.py` -- the state machine, the terminal
  rule, the closure sequence and the evidence gate.
- `tests/test_i2b_controller.py` -- 124 offline tests.

No frozen I1/I2/AR2/O1 module, test, or public API was modified.

## Final resource / lifecycle architecture

```text
AIDO-supplied argument validation                (BEFORE any credential read)
  -> non-secret preflight        (reused i2_credentials, unmodified)
  -> connection-value read       (reused i2_credentials, unmodified)
  -> route descriptor            (i2_route)
  -> run-scoped secret context   (i2_secret_context)
  -> disposable Pi config        (i2_pi_config)          [RESOURCE 1]
  -> config/secret/route binding (i2_composition)
  -> positive-allowlist child env(i2_environment)
  -> broker session created      (injected)              [RESOURCE 2]
  -> broker reached READY        (from that same session)
  -> runtime launched WITH the binding (injected)        [RESOURCE 3]
  -> [4 facts from ONE launch observation]
  -> [3 facts from ONE get_commands observation]
  -> [2 facts from ONE get_state observation]
  -> protocol/extension integrity (injected, session-bound)
  -> exact model served           (reused i2_route, unmodified)
  == compatibility facts end ==
  -> runtime teardown             (frozen O1 order: runtime FIRST)
  -> broker shutdown              (frozen O1 order: broker SECOND)
  -> generated-config cleanup     (reused i2_cleanup, unmodified)
  -> retained-evidence safety gate(reused qualification.safety, unmodified)
```

## Broker / runtime authority binding

The binding is MECHANICAL, not conventional:

- the controller mints one per-run `run_id` nonce that no adapter supplies;
  a `BrokerSession` that does not carry it is refused as
  `BROKER_SESSION_MISMATCH` **before any launch-capable continuation**;
- `RuntimeLaunchRequest` is CONSTRUCTED BY THE CONTROLLER and is
  **unconstructible** from a broker session that belongs to a different run
  or has not `reached_ready`. Frozen O1's ordering is therefore enforced by
  the type, not by call order alone;
- the launch request carries the broker's `pipe_name`/`capability_id`/
  `broker_token` -- the binding the launch actually needs;
- every post-launch adapter takes the run's `RuntimeSession` and returns an
  observation carrying the `runtime_session_id` it was produced from; the
  controller compares it against the session the launch returned. A
  mismatched `get_commands`, `get_state`, protocol observation, runtime
  shutdown or broker shutdown is refused;
- teardown targets exactly those session objects. A session AIDO could not
  tie to its own run is still shut down (abandoning it would strand a
  resource) but **never reports closure satisfied**;
- a failed launch must EITHER hand back a `RuntimeSession` OR declare
  `partial_resource_cleaned_internally=True`; the third, stranding state is
  unconstructible. A launch adapter that RAISES leaves AIDO no authority,
  reported as `RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE`, which can never
  pass.

**Honest scope of the nonce:** `run_id` is a CORRELATION control, not an
authentication control. It catches a stale, leftover or foreign session
object. It does not authenticate the adapter, which necessarily receives the
nonce in order to echo it, and which is AIDO's own future live code inside
the trust boundary.

## H1 / get_commands and H2 / get_state observation binding

One `GetCommandsObservation` yields THREE distinct gate facts -- the call
and response shape (`GET_COMMANDS`), H1 exact extension identity
(`H1_EXTENSION_IDENTITY`), and the exact authorized registry
(`TOOL_REGISTRY`). They remain distinct facts, but cannot refer to two
unrelated runtime snapshots. One `GetStateObservation` likewise yields
`GET_STATE` and `H2_PROVIDER_MODEL_IDENTITY`. There is no `h1_check` adapter
and no `broker_ready` adapter left in the controller signature at all.

The registry comparison is over the **sorted observed name sequence**, never
a set, so a duplicate cannot collapse into a match. `ObservedCommand.source`
is recorded but is deliberately NOT part of the registry rule: I2A Sec. 15
item 6 defines that gate over the registered command SET, and extension
provenance is H1's job, proven separately from the same response.

## The thirteen individually established compatibility facts

`CompatibilityFacts`, one exact-`bool` field each: `pi_version_observed`,
`rpc_launch_shape_valid`, `required_launch_flags_accepted`,
`lf_jsonl_correlation_succeeded`, `get_commands_response_shape_understood`,
`h1_extension_identity_matched`, `authorized_tool_registry_exact`,
`get_state_response_shape_understood`, `h2_provider_model_identity_matched`,
`no_protocol_violation_observed`, `no_extension_error_observed`,
`exact_candidate_model_served`, `broker_reached_required_ready_state`.

`pi_version_observed` is **provenance only** -- nothing anywhere compares an
observed version against a pinned value, proven by a test in which a run
with `99.0.0-rc1` passes identically. A run with no observable version fails
closed as `PI_VERSION_NOT_OBSERVED`; a blank or unbounded version string is
refused at construction.

## Terminal-pass rule

```text
CATEGORY_B_GATE_PASSED  iff  every compatibility fact established
                        AND  semantic_prompts_sent == 0
                        AND  every required teardown closed truthfully
                        AND  generated-config cleanup VERIFIED
                        AND  evidence retention-ready (scrub clean)
```

Anything else is `INFRASTRUCTURE_REFUSAL` with `semantic_prompts_sent = 0`.
The single boolean the evidence records as `compatibility_gate_passed` is
computed only after compatibility AND closure are both resolved, so it can
never be `true` alongside a failed teardown, an unclosed broker or an
unverified cleanup. `CategoryBControllerResult.__post_init__` refuses to
construct a pass that violates any of these, so the rule holds even for a
directly-constructed result.

**Correction (5F3B-I2B-FU2A).** The claim above was FALSE as first written.
Independent review found `__post_init__` read
`runtime_teardown.closure_satisfied`/`broker_shutdown.closure_satisfied`/
`cleanup.closure_satisfied`/`evidence.retention_ready` via bare attribute
access with **no type check on those three fields at all**, and checked
`facts`/`evidence` with `isinstance` rather than exact type -- so an
unrelated object merely exposing `closure_satisfied = True` as a bare class
attribute, or a subclass overriding any of these five read-only properties,
constructed a `CATEGORY_B_GATE_PASSED` result directly. See the FU2A section
below for the concrete counterexamples, the fix (every nested authority
value is now checked by `type(x) is ExactType`, never `isinstance`), and the
regression tests. The claim is accurate again as of FU2A.

## Teardown / broker-shutdown behaviour, stated truthfully

Runtime first, then broker -- frozen O1's order. Each is attempted exactly
once, on the failure path and the passing path alike, for whatever resources
may exist. `RuntimeTeardownStatus.succeeded` means AIDO's own shutdown call
returned AND reported that **AIDO's own DIRECT child** exited;
`BrokerShutdownStatus.reached_closed` is the broker lifecycle's own terminal
state. Neither is, and neither may be read as, a claim that a descendant
process was terminated, that Pi/provider inference stopped, or that GPU work
stopped. The evidence records
`backend_inference_lifetime_after_teardown: "not observed"` and
`descendant_process_lifetime_after_teardown: "not observed"`, and its
`claim_scope` states the negation explicitly.

## Config-cleanup behaviour

Reuses `i2_cleanup.scrub_generated_qualification_config` and, on any failure
or unverified result, `classify_cleanup_failure(semantic_prompts_sent=0)` --
the only value this module can ever supply. A `stat`-verified removal is
required for closure; an unverified one forces `INFRASTRUCTURE_REFUSAL`.
Proven under filesystem tampering: a test removes the disposable config's
authority marker mid-run, cleanup can then no longer be authorized, and the
run refuses rather than reporting a pass.

## The FULL artifact safety context

`build_run_safety_context` populates every field I1's `ArtifactSafetyContext`
declares, from the run's real value when that value exists: `endpoint_host`
and `api_key` from the secret context; `broker_token`, `pipe_name` and
`capability_id` from the live broker session; `workspace_absolute_path` from
the controller's required `workspace_root` argument. `bearer_token` is
`None` as a **derived, proven absence** -- I2A's frozen credential mechanism
for this route is `models_json_env_interpolation`, which mints no separate
bearer value; a descriptor reporting any other mechanism raises
`CategoryBSafetyContextError` rather than guessing. A run that failed before
a secret context existed still declares whatever it does have rather than
falling back to `none_declared()`. The evidence records
`safety_context_declared_needle_codes` -- the metadata CODES only, never a
value -- and a test asserts all six available codes are present on a passing
run.

## Result / evidence integrity

`gate_statuses` is a `MappingProxyType` over a throwaway dict; assigning
through it raises `TypeError`, and a copy taken from it is independent.
`CategoryBEvidence` holds one canonical, already-scrub-checked JSON string;
each `as_dict()` returns a freshly deserialized copy, so mutating a returned
dict -- including the nested `gate_statuses` and `compatibility_facts` --
cannot rewrite the evidence or a later reader's view. The scrub result is an
immutable `tuple` of bounded finding codes plus a `bool`. A refused evidence
body is not retained in any form (`as_dict() == {}`, `as_json() == ""`), and
`CategoryBEvidence.__post_init__` refuses to hold one.

## Second adversarial self-review of the shipped code

Five further defects were found by probing the finished implementation, and
all five are fixed with regression tests:

1. **A failed compatibility fact did not stop further LIVE calls.** With
   `observed_pi_version = None`, the `PI_VERSION_OBSERVED` gate failed but
   the stage gate below it tested only the LAST launch fact, so
   `get_commands`, `get_state`, `observe_protocol` and the route check all
   still ran. Stage gating now uses `_all_passed(...)` over every fact
   established so far. Facts still derivable from an observation already in
   hand are recorded anyway -- H1 and the registry both come from one
   response, and neither costs an extra live call.
2. **A subclass of an observation type passed the adapter boundary.** A
   subclass could re-declare a validated field as a property returning a
   different value per read, defeating both the exact-`bool` rule and the
   session-id comparisons. The boundary now requires `type(value) is
   expected`, not `isinstance`.
3. **A "clean" scrub result could carry findings.** `CategoryBEvidence` now
   requires `scrub_clean == (not scrub_findings)`.
4. **A teardown/broker status could claim closure for a resource that never
   existed.** `closed_by_creator` without a launch reported
   `closure_satisfied = True`; a broker shutdown could be reported with
   `creation_attempted = False`. Both are now unconstructible.
5. **A blank `workspace_root` caused a credential read for a run that could
   never be safe.** It ran the whole preflight/credential/config sequence
   and only failed at broker creation -- yet the workspace needle it would
   have declared was empty, so the run could never have produced provably
   safe evidence. AIDO's own arguments are now validated FIRST, raising
   `CategoryBControllerInputError` before any gate runs.

A bounded reported-command cap (256) was also added, so an unbounded
runtime-supplied command list is refused rather than held.

## Additional adversarial tests derived beyond the required regressions

Beyond the ten regressions the prompt required: launch bound to a foreign
broker session; a protocol observation for an unrelated runtime; a runtime
teardown or broker shutdown returning a foreign session id; every live
adapter proven to receive the SAME `RuntimeSession` object; a stale broker
session replayed from a previous invocation; re-running the controller
against the same `experiment_root` after cleanup; a subclassed observation
type; a launch adapter that raises leaving no teardown authority; a broker
adapter that raises leaving no shutdown authority; an unbounded command
list; an unexpected credential mechanism refusing rather than guessing;
teardown/shutdown proven attempted exactly once; `source`-only variation
proven not to change the registry verdict; and a shutdown call that returned
but reported no direct-child exit proven NOT to be closure.

## Offline suite result

```text
638 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(514 = I1 plus I2 through FU3B, unchanged and unmodified; I2B-FU1
contributes 124.) No network call, socket, model call, Pi/Node process, or
credential lookup occurred anywhere in the run.

Frozen sibling suites re-run unmodified, since I2B reuses their lifecycle
and interface facts:

```text
experiments/pi_external_runtime_ar2/tests        290 passed, 0 failed
experiments/pi_external_runtime_ar2_o1/tests      89 passed, 0 failed
```

No file under `ar2/`, `o1/`, or `src/` was touched.

## Zero-prompt proof

`SEMANTIC_PROMPTS_SENT` is a module constant `0`, and nothing binds another
value to the run's prompt count. Neither I2B module defines any function
that accepts, sends or forwards a prompt. An AST-based source regression
test asserts that no NAME in either module (identifier, attribute,
parameter, function or class) contains `prompt`, `message`, `chat`,
`completion`, `inference`, `agent_start` or `instruction`, apart from the
zero-valued counter itself -- checked against names, never against prose, so
the modules stay free to DOCUMENT what they refuse to do. A second test
asserts neither module imports `subprocess`, `socket`, `ssl`, `http`,
`urllib`, `requests`, `httpx`, `asyncio`, `multiprocessing`, `threading`,
`shutil`, `litellm` or `openai`, and that their code (docstrings stripped)
contains no `os.environ`, `getenv`, `Popen`, `urlopen` or `open(`. A third
asserts no candidate-scoring machinery is reachable, and that
`CategoryBOutcome` has exactly two members. Every Category-B failure is a
pre-prompt infrastructure refusal: there is no candidate classification, no
hard bar, no ranking, and no `AUTONOMOUS_PASS`/`AUTONOMOUS_FAIL`.

## What this does NOT establish

- At the time this phase was accepted, no zero-prompt live gate had run: no
  Pi/Node process had been launched, no RPC call made, no broker created, no
  socket opened, no `/models` request issued, and no real credential read.
  Every live boundary was an injected adapter this package supplied no real
  implementation for, and **no real live adapter was added by this phase**.
  (5F3B-I2B-L1 later added real live adapters and ran one zero-prompt
  attempt -- see the TOP-LEVEL CORRECTION at the head of this document.)
- No candidate model has ever run. No PASS/FAIL, no ranking and no
  qualification verdict exists for Candidate A or Candidate B, and this
  module cannot produce one.
- **Not** "every possible failure maps to `INFRASTRUCTURE_REFUSAL`." Every
  bounded adapter/gate failure does. A caller-programming error in AIDO's
  own arguments raises `CategoryBControllerInputError` before any gate runs,
  deliberately -- that is not a Category-B outcome at all. The earlier,
  stronger README claim has been corrected.
- The `run_id` nonce is a correlation control, not authentication against a
  hostile adapter.
- Redaction/scrubbing remain **backstops, not guarantees**, exactly as every
  earlier I1/I2 closure states.
- 5F3B-Q1/Q2 (the first live candidate sweeps) remain **NOT authorized** and
  cannot execute until a future, separately authorized phase supplies real
  implementations for the injected adapters and receives its own explicit
  go-ahead.

---

# 5F3B-I2B-FU2 -- Offline Category-B Controller Correction (Offline Only)

> **AS OF THIS PHASE'S ACCEPTANCE: OFFLINE IMPLEMENTATION ONLY. CATEGORY-B
> LIVE EXECUTION NOT YET RUN. NO CANDIDATE MODEL RUN. NO REAL WORKSPACE.
> Q1/Q2 NO-GO.** (One zero-prompt Category-B live attempt has since occurred
> -- see the TOP-LEVEL CORRECTION at the head of this document. No candidate
> model has run, then or now.)

The `5F3B-I2A` design family -- including `DESIGN-FU3`, `FU3A`, `FU3B` and
`FU3C` -- is **frozen**. The I2B-FU1 implementation slice was **never
accepted**, and the frozen design names six defects in it. This phase brings
the unfrozen I2B slice into exact conformance with that design. **No frozen
AR1/AR2/O1/I1/I2 contract or code was modified**, nothing under `src/`,
root `tests/` or `projects/` was touched, and `CLAUDE.md` was not modified.

## Pre-coding adversarial analysis

Answered for every authority-bearing object before any code was written.

| Object | Who creates it | Who may mutate it | What proves provenance | Bypassable through a supported path? |
|---|---|---|---|---|
| `QualificationRunWorkspace` | **only** `mint_qualification_run_workspace()`, which CREATES the root | nobody (frozen; both paths `repr=False` behind a bounded `__repr__`) | a process-local mint record keyed by a fresh 128-bit nonce, plus the frozen AR2 on-disk marker re-read at every consumption boundary | **No** -- there is no function taking a path, `__post_init__` refuses an unregistered nonce or a path that disagrees with the mint record, and every check is EXACT-type (a subclass is refused) |
| `BrokerCreationRequest` / `RuntimeLaunchRequest` | the controller only | nobody (frozen) | constructed from the run's own `run_id` plus the claimed, re-verified workspace | **No** -- re-verifies the workspace against the filesystem and requires the single-use claim to name exactly this `run_id` |
| `BrokerCreationObservation` / `RuntimeLaunchObservation` | the injected creator adapter | nobody (frozen) | the correlated `session`, or three orthogonal creator-reported facts | Fails closed: `_invoke` requires `type(v) is expected` (a subclass is refused), and every malformed/incoherent combination raises at construction |
| `BrokerSession` / `RuntimeSession` | the creator adapter | nobody (frozen) | `run_id` (and `broker_session_id`) equality against this invocation's own nonce, **and** being the direct return value of this invocation's own creation call | Value equality is a CORRELATION control, not authentication -- stated, not overclaimed |
| `GetCommandsObservation` (H1 + namespace) | the `get_commands` adapter | nobody (frozen) | five frozen-evaluator components AIDO recomputes; AIDO's own declared sentinel name and expected origin kind | An adapter fabricating all five components is out of scope by the design's own Sec. 6.3(e) -- stated as a residual, never claimed closed |
| `RuntimeShutdownObservation` / `BrokerShutdownObservation` | the shutdown adapters | nobody (frozen) | session-id equality with the exact session this run created | Never called at all for a session this run cannot prove is its own |
| generated Pi config | frozen `i2_pi_config` (unmodified) | its own internal-only issuance registry | unchanged from I2-FU3A/FU3B | Unchanged |
| evidence / safety context | the controller | nobody (canonical JSON string; fresh copy per read) | scrub gate over an explicitly declared needle set | Mutating a returned dict cannot rewrite the object |

Findings that changed the implementation, before coding:

1. **The `TOOL_REGISTRY` gate was unprovable AND unsatisfiable.** Confirmed
   mechanically in-repo: `ar2/extension/index.ts` registers `aido_read` and
   `aido_edit` with `pi.registerTool` and the sentinel with
   `pi.registerCommand`, and `get_commands` reports commands. The old gate
   could never pass on a correct run.
2. **The top-level `source` cannot discriminate.** Both AIDO's sentinel and
   Pi's own inline `llama` report `source == "extension"`; the real
   discriminator is `sourceInfo.source`. So `ObservedCommand` had to gain
   bounded PROVENANCE fields, and malformed `sourceInfo` had to be
   *representable* (so the gate can fail with the specific
   `EXTENSION_COMMAND_PROVENANCE_UNKNOWN` code) rather than refused at
   construction into a generic malformed-adapter bucket.
3. **A single H1 boolean cannot be audited.** Decomposition into the frozen
   evaluator's five components plus an AIDO-owned conjunction was required,
   with a differential conformance corpus proving the projection matches the
   frozen rule.
4. **`route_descriptor_for_candidate` was called AFTER the credential read.**
   It is fully deterministic and non-secret, so it had to move ahead of the
   boundary, along with the workspace claim and the correlation-id mint.
5. **`experiment_root`/`workspace_root` were arbitrary strings feeding a
   `mkdir`.** Both parameters had to be removed, not validated harder.
6. **`RuntimeLaunchObservation` made a physically real state
   unconstructible**, and its `partial_resource_cleaned_internally` flag was a
   creator-supplied verdict.
7. **`_close_runtime`/`_close_broker` called the shutdown adapter for a
   foreign session** and merely withheld `closure_satisfied`.
8. **`secrets.token_hex(16)` was unguarded**, so an entropy failure would
   escape a controller whose entire design is bounded refusal.
9. **A pre-existing FU1 truthfulness defect, found during this analysis and
   corrected here:** `RuntimeLaunchObservation` refused
   `session is None and launch_shape_valid is True`. A process can genuinely
   start with a valid launch shape and then fail before an RPC-correlated
   session id exists; forcing `launch_shape_valid=False` there would
   overwrite an independently observed creation fact with a lie, which is
   exactly what FU3 Sec. 9.3 forbids ("the resource kind's own independent
   creation-failure facts... are never overwritten or masked by the cleanup
   outcome"). The coupling was removed. No pass leaks: a `None` session
   fails the `RUNTIME_LAUNCH` gate, and the four launch facts are only gated
   after it passes.

## What was implemented

- **`qualification/i2b_workspace.py` (new).** One minting function taking no
  argument at all; `verify_run_workspace` delegating THE PROOF to the frozen
  `ar2.capability` root-authority verification (reused, never forked) and
  adding an existence/canonicity check for the repository child; a
  single-use `claim_run_workspace(workspace, run_id=...)`; and a
  removal/discard pair for fixture teardown. There is deliberately no
  function anywhere that converts an existing path into authority.
- **`qualification/i2b_session.py`.** `ObservedCommand` gained bounded
  provenance; `GetCommandsObservation` carries H1 COMPONENTS plus AIDO's own
  `h1_identity_established`, AIDO's declared sentinel name and expected
  origin kind, and an `extension_command_partition()` over SORTED sequences;
  `h1_components_from_frozen_evaluation` and
  `observed_command_from_reported_entry` are the fixed adapter projections;
  the new `BrokerCreationObservation` and the corrected
  `RuntimeLaunchObservation` share ONE validator for the four-row creator
  contract, and both expose `cleanup_verified_success` as a read-only
  AIDO-derived property; both run-scoped requests take the workspace object
  and re-verify it.
- **`qualification/i2b_controller.py`.** New `RUN_CORRELATION` and
  `WORKSPACE_AUTHORITY` gates ahead of `ROUTE_DESCRIPTOR`, which itself moved
  ahead of the credential boundary; `TOOL_REGISTRY` replaced by
  `EXTENSION_COMMAND_NAMESPACE`; closure modelled as one
  `ResourceClosureState` enum with DERIVED `attempted`/
  `authority_available`/`closure_satisfied`, so a contradictory combination
  is unrepresentable rather than merely rejected; the shutdown adapters are
  never called for an untrusted session; and the evidence gained
  `active_tool_registry_observation_available: false` plus AR2D Sec. 2.2's
  three-way distinction.

**One deliberate, documented deviation from "verbatim".** AR2D Sec. 2.2's
second line reads `observed live tool calls : aido_read x2, aido_edit x1, no
other observed` -- AR2's own live run's counts. A Category-B run sends zero
semantic prompts and therefore observes NO tool call at all; reproducing
those counts would fabricate an observation this run never made. That one
line is scoped to this run; the structure and every other line, including the
load-bearing `NOT established` statement, are AR2D's.

## Bypasses found during post-implementation self-review

Both were found by constructing supported/public counterexamples against the
implemented code, and both were fixed with a regression test **before**
completion was reported.

1. **The sentinel command name was adapter-supplied.** `sentinel_command_name`
   arrived on the observation. An adapter could nominate Pi's OWN `llama` as
   "the sentinel", mark it `"cli"`, and have BOTH H1 and the namespace
   partition evaluated against that nomination -- a fabricated identity
   dressed as an observation. **Fixed:** the name is now AIDO's own declared
   constant `CATEGORY_B_SENTINEL_COMMAND_NAME` (duplicated as a VALUE from
   `ar2.pi_config.SENTINEL_COMMAND_NAME`, with a test asserting they agree),
   and any observation naming a different sentinel is refused at
   construction. Regression:
   `test_the_sentinel_name_is_aidos_own_bytes_not_an_adapter_nomination`.
2. **Subclass substitution was unproven for the new types.** The exact-type
   discipline was implemented, but nothing tested it for
   `QualificationRunWorkspace`, `BrokerCreationObservation`, `RuntimeSession`
   or `BrokerSession` -- and a subclass can override a validated field with a
   property that returns a different value on each read. **Regressions added:**
   `test_a_subclass_of_the_workspace_type_is_refused_everywhere`,
   `test_a_subclass_of_the_broker_creation_observation_is_refused`,
   `test_a_subclass_of_a_session_type_is_refused_inside_an_observation`.

Two further supported counterexamples were constructed and found already
closed, and now carry regressions:
`test_discarding_a_workspace_cannot_resurrect_or_relaunder_authority` (the
public `discard_run_workspace` removes the MINT record, not merely the claim,
so a discarded workspace cannot be re-claimed, re-constructed or re-run) and
`test_h1_components_that_disagree_with_the_reported_list_fail_closed`.

## Adversarial coverage in the offline suite

The frozen design's named minimum, all present: the genuine
sentinel(`cli`) + `llama`(`inline`) passing regression, proven against the
real observed shape rather than a synthetic double; a second `cli` entry
refused; four distinct malformed/unrecognized provenance refusals plus a
sentinel whose own provenance is unreadable; a sixteen-row H1 differential
conformance corpus against the frozen evaluator; zero credential reads proven
for an unknown candidate, an unverifiable workspace, a foreign-claimed
workspace, cross-run reuse, a failing non-secret gate and a correlation-id
failure; workspace substitution/forgery/relocation/marker-tampering, plus
tampering INSERTED between the authority gate and the config-write
consumption boundary; all four creator partial-lifecycle states for BOTH
resource kinds; direct-child `False` vs `True`; `STATE_TEARDOWN_INCOMPLETE`
vs `STATE_CLOSED`; every malformed cleanup-observation typing combination
(non-bool, attempted-with-`None`, not-attempted-with-non-`None`,
cleanup-without-creation, session-plus-self-close); foreign broker session,
foreign runtime `run_id` and foreign runtime `broker_session_id` each with
shutdown call count **0**; a same-run positive control tearing down exactly
once in frozen-O1 order; teardown, broker-shutdown, cleanup and evidence-scrub
failures each proven unable to produce a terminal PASS; the pass decision
proven to consume already-resolved closure facts; result/evidence/facts/
workspace immutability and post-validation mutation attempts; and
duplicate/multiplicity cases proven not to collapse.

## Offline suite result

```text
718 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(514 = I1 plus I2 through FU3B, unchanged and unmodified; I2B-FU2
contributes 204, replacing I2B-FU1's 124.) No network call, socket, model
call, Pi/Node process, or credential lookup occurred anywhere in the run.

Frozen suites re-run unmodified, to prove no accepted behavior regressed:

```text
experiments/pi_external_runtime_ar1/tests         96 passed, 0 failed
experiments/pi_external_runtime_ar2/tests        290 passed, 0 failed
experiments/pi_external_runtime_ar2_o1/tests      89 passed, 0 failed
tests/  (the production suite)                  3504 passed, 0 failed
```

No file under `ar1/`, `ar2/`, `o1/`, `src/`, root `tests/` or `projects/` was
touched.

## What this does NOT establish

- **At the time this phase was accepted, no zero-prompt live gate had run.**
  No Pi/Node process had been launched, no RPC call made, no broker created,
  no socket opened, no `/models` request issued, and no real credential read.
  (One zero-prompt attempt has since occurred -- see the TOP-LEVEL CORRECTION
  at the head of this document.)
- **`get_commands` still proves NOTHING about the active tool registry.** The
  corrected gate proves the extension COMMAND PROVENANCE PARTITION is exactly
  what AIDO intended. Pi exposes no zero-prompt observation of the registry's
  contents, and the evidence records that as an explicit non-observation.
- **The adapter trust boundary is unchanged.** The component/verdict split
  for H1 and for cleanup is a correctness control against a projection defect
  or a future refactor -- **not** a defense against an adapter that
  deliberately fabricates every component. In particular, nothing forces an
  adapter's H1 components and its reported command list to have come from the
  same response; that remains the design's own stated Sec. 6.3(e) residual.
- **The synthetic workspace authority is not real-workspace authority**, and
  is not a step toward one. It makes a real workspace structurally unnameable
  from this path. It is not a defense against a same-user adversary, who
  could forge a marker trivially and does not need this code path at all.
- **No claim about descendants, inference or GPU work.** Neither the
  creator's observed postcondition nor AIDO's derived
  `cleanup_verified_success` nor an ordinary teardown result is ever a claim
  that a descendant process was terminated, that Pi/provider inference
  stopped, or that GPU work stopped.
- **Redaction/scrubbing remain backstops, not guarantees.**
- **5F3B-Q1/Q2 remain NOT authorized**, Category-B live execution remains
  **NO-GO**, and real-workspace authority remains **NO-GO**.

---

# 5F3B-I2B-FU2A -- Terminal Result + Evidence Integrity Closure (Offline Only)

> **OFFLINE ONLY. NO LIVE ACTIVITY OF ANY KIND.** No Pi/Node process, no
> socket, no model call, no credential read, no semantic prompt, no real
> workspace access. Category-B live execution remains **NO-GO**, Q1/Q2
> remain **NO-GO**, real-workspace authority remains **NO-GO**. The I2A/FU3
> design family is unchanged and was not reopened. No frozen AR1/AR2/O1
> code or contract was modified.

Independent source review of the accepted-in-direction 5F3B-I2B-FU2
architecture found three concrete, exploitable defects, all in
`qualification/i2b_controller.py`, none in `i2b_session.py` or
`i2b_workspace.py`. Each is closed below with a proven-before/proven-after
counterexample and a regression test.

## Public counterexamples that worked BEFORE this fix

Each was reproduced against the actual pre-fix code before any edit was made.

**1. `CleanupStatus` truthiness fail-open.**

```python
CleanupStatus(attempted=True, scrub_verified="false", classification=None)
# constructed successfully:
#   .closure_satisfied  -> True
#   .status_text        -> "VERIFIED_REMOVED"
```

`scrub_verified` was typed `bool | None` but never checked for exact `bool`;
`closure_satisfied` returned `bool(self.scrub_verified)`, and a non-empty
string is truthy in Python. `_attempt_cleanup()` separately re-introduced the
same coercion at the frozen `i2_cleanup` consumption boundary
(`verified = bool(result.scrub_verified)`).

**2. `CategoryBControllerResult` was not valid by construction.**

```python
class FakeClosure:
    closure_satisfied = True

CategoryBControllerResult(
    ..., outcome=CategoryBOutcome.CATEGORY_B_GATE_PASSED,
    runtime_teardown=FakeClosure(), broker_shutdown=FakeClosure(), cleanup=FakeClosure(),
    ...
)
# constructed successfully: .outcome is CATEGORY_B_GATE_PASSED
```

`runtime_teardown`/`broker_shutdown`/`cleanup` were consumed via bare
attribute access (`.closure_satisfied`) with **no type check at all** --
not even `isinstance`. `facts`/`evidence` used `isinstance`, which a
subclass overriding `all_established`/`retention_ready` as a read-only
property satisfies while lying about its own state; reproduced identically
with `FakeFacts(CompatibilityFacts)` overriding `all_established` and
`FakeTeardown(RuntimeTeardownStatus)`/`FakeBroker(BrokerShutdownStatus)`
overriding `closure_satisfied`, all four accepted into a genuine
`CATEGORY_B_GATE_PASSED` result.

**3. `CategoryBEvidence` could self-declare scrub-clean.**

```python
CategoryBEvidence(
    retention_ready=True, scrub_clean=True, scrub_findings=(),
    _serialized='{"api_key":"raw-secret"}',
)
# constructed successfully: .retention_ready -> True, .as_json() -> the raw secret string
```

No scrub provenance was established by the constructor at all --
`retention_ready` was a bare caller-supplied boolean the object trusted.

## Pre-coding adversarial analysis

The ten required counterexamples were constructed against the pre-fix code
before any edit, to determine which actually succeeded:

| # | Case | Result against pre-fix code |
|---|---|---|
| 1 | `scrub_verified="false"` | **Succeeded** -- blocker 1 |
| 2 | `scrub_verified=1` | Succeeded (same class) |
| 3 | truthy custom object as `scrub_verified` | Succeeded (same class) |
| 4 | subclass of `CleanupStatus` overriding `closure_satisfied` | Succeeded once accepted into a result (no type check on `cleanup` at all) |
| 5 | custom non-`CleanupStatus` object exposing `closure_satisfied=True` | **Succeeded** -- blocker 2 |
| 6 | subclass of `RuntimeTeardownStatus`/`BrokerShutdownStatus` overriding the derived property | **Succeeded** -- blocker 2 |
| 7 | subclass of `CompatibilityFacts` overriding `all_established` | **Succeeded** -- blocker 2 (`isinstance` accepted it) |
| 8 | subclass of `CategoryBEvidence` overriding `retention_ready` | Constructible via the OLD public constructor (no protection at all before this fix) |
| 9 | direct `CategoryBEvidence` creation with an unsafe `_serialized` body | **Succeeded** -- blocker 3 |
| 10 | a `CATEGORY_B_GATE_PASSED` result whose `_gate_status_pairs` contain a `FAILED:...`/`NOT_REACHED` entry | Succeeded -- `_gate_status_pairs` was never validated at all |

## Mechanical closure chosen

**1. `CleanupStatus` (blocker 1).** `scrub_verified` now goes through
`i2b_session.require_exact_bool` (reused, not reimplemented) when
`attempted=True`; `closure_satisfied` returns the already-proven-exact-bool
field directly, with **no** `bool(...)` call anywhere in the property.
`_attempt_cleanup()` consumes the frozen `i2_cleanup.CleanupResult`'s own
`scrub_verified` fail-closed: `verified = raw_verified is True` -- anything
that is not exactly `True`, including a value that is not exactly a `bool`
at all, is treated as unverified. `CleanupStatus`'s own exact-bool
requirement is what actually enforces the type; the consumption site never
coerces on its own.

**2. `CategoryBControllerResult` (blocker 2).** Every nested authority value
is now checked by **exact type** (`type(x) is ExactType`), never
`isinstance`: `facts` must be exactly `CompatibilityFacts`, `evidence`
exactly `CategoryBEvidence`, `runtime_teardown` exactly
`RuntimeTeardownStatus`, `broker_shutdown` exactly `BrokerShutdownStatus`,
`cleanup` exactly `CleanupStatus`. `outcome`/`failed_gate`/`failure_code`
are checked to be exactly their declared enum type (not merely
non-`None`); `pi_config_created`/`broker_created`/
`runtime_session_established` go through `require_exact_bool`;
`semantic_prompts_sent` is checked `type(x) is int` **before** the
value-equality check, because `False == 0` is `True` in Python and the old
bare `!=` comparison alone would have silently accepted
`semantic_prompts_sent=False`. `_gate_status_pairs` -- previously
unvalidated in any way -- is now checked by a new
`_validate_gate_status_pairs` helper against the bounded, declared
vocabulary of gate names (`CategoryBGateName`) and status texts this module
ever actually produces (`PASSED`/`NOT_REQUIRED`/`SUCCEEDED`/`CLOSED`/
`VERIFIED_REMOVED`/`CLOSED_BY_CREATOR_VERIFIED`/`NOT_REACHED`/
`FAILED:<known code>`), requires every declared gate exactly once, and --
only for a claimed `CATEGORY_B_GATE_PASSED` -- refuses any `NOT_REACHED` or
`FAILED:...` entry for **any** gate.

**3. `CategoryBEvidence` (blocker 3).** Every field is now `field(init=False,
...)`: the public, auto-generated constructor takes **no arguments at all**
and always yields the safe, inert `retention_ready=False` default -- there
is no supported way to pass `retention_ready=True` (or any other field) to
it. The only way to obtain a populated instance is through two
package-internal classmethods, both of which **derive** every field rather
than accepting it: `_build_from_payload(payload, safety)` runs the frozen,
unmodified `qualification.safety.qualification_scrub_check` on the payload
itself, inside this class, and the boolean/serialized body are a direct
function of that one real call -- never of a caller's say-so; `_refused(...)`
is for the one caller with no payload to check at all, and can only ever
produce the unconditionally-`False`, unconditionally body-less shape. The
scrub check that used to live in `_build_evidence` moved into the classmethod
itself, so there is exactly one call site for it. `payload` is a local
parameter only, never stored on the returned instance, so no raw
(possibly secret-bearing) diagnostic can be read back off any evidence
object, retained or refused.

## Bypasses found during post-implementation self-review

**Subclassing `CategoryBEvidence` was still exploitable after the `init=False`
fix, via a mechanism distinct from every other value object in this module.**
For a dataclass field with `init=False` **and a plain (non-factory)
default**, Python's generated `__init__` does not call
`object.__setattr__` for that field at all -- it relies on the class-level
default attribute, since the value already equals its default. A subclass
overriding `retention_ready` as a read-only property therefore constructed
successfully via the bare `cls()` call (no `AttributeError`, unlike
assigning to an ordinary frozen field with an `init=True` parameter) and
immediately reported `retention_ready is True` with **nothing ever
scrub-checked**:

```python
class _Sneaky(CategoryBEvidence):
    @property
    def retention_ready(self):
        return True

_Sneaky()  # constructed successfully before this fix; .retention_ready -> True
```

The exact-type check already added to `CategoryBControllerResult` (item 2
above) closes the only production path that could turn this into an
authorized PASS, but the object itself made a false claim about its own
state under a bare, no-argument, fully "supported" call. **Closed by
refusing subclassing outright**: `_check_invariants()` (called from
`__post_init__` and, explicitly, again after each classmethod's mutation)
now requires `type(self) is CategoryBEvidence` exactly, as its first check
-- so even a subclass that overrides nothing at all is refused the moment
`__init__` runs, including inside `_build_from_payload`/`_refused` when
called on a subclass. Regression:
`test_a_subclass_of_categorybevidence_cannot_override_retention_ready`,
`test_evidence_subclassing_is_refused_outright_even_via_the_classmethods`.

A broader sweep for the same class of bug (`isinstance` where exact-type
authority is intended; the `init=False`-plain-default `object.__setattr__`
skip specifically) across `i2b_controller.py`, `i2b_session.py` and
`i2b_workspace.py` found `CategoryBEvidence` was the **only** class in any
of the three modules using `field(init=False, default=<plain value>)` at
all -- confirmed by grep, not merely inspection. Every other `isinstance`
use in the package (`BrokerSession` inside `RuntimeLaunchRequest`,
`ResourceClosureState` membership, `Mapping`/`tuple`/`str` content checks)
was checked directly: each guards a value whose relevant fields are ordinary
`init=True` dataclass fields, which -- confirmed with an isolated
repro -- **are** always explicitly assigned via `object.__setattr__` in the
generated `__init__` regardless of default, so a subclass overriding one of
those as a property raises `AttributeError` at construction, before
`__post_init__` even runs. None of those needed a change, and
`i2b_session.py`/`i2b_workspace.py` were not touched by this follow-up.

## Regression tests added

All in `tests/test_i2b_controller.py`:

- `test_cleanup_status_scrub_verified_string_false_is_refused` -- the exact
  counterexample from the brief;
- `test_cleanup_status_rejects_every_non_bool_scrub_verified` -- `1`, `0`,
  `"true"`, `""`, `object()`, `1.0`, `[]`, `{}`;
- `test_cleanup_status_attempted_true_requires_a_scrub_verified_value`;
- `test_the_frozen_cleanup_helpers_own_return_is_consumed_fail_closed` --
  an end-to-end run through a monkeypatched `scrub_generated_qualification_config`
  returning a truthy non-`bool` `scrub_verified`, proving the real controller
  pipeline reports `attempted=True, scrub_verified=False, closure_satisfied=False`;
- `test_a_bare_object_exposing_closure_satisfied_cannot_authorize_a_pass` --
  the exact counterexample from the brief, for `runtime_teardown`/
  `broker_shutdown`/`cleanup`;
- `test_a_subclass_overriding_closure_satisfied_cannot_authorize_a_pass`;
- `test_a_subclass_of_cleanup_status_overriding_closure_satisfied_is_refused`;
- `test_a_subclass_of_compatibility_facts_overriding_all_established_is_refused`;
- `test_a_subclass_of_categorybevidence_cannot_override_retention_ready`;
- `test_evidence_subclassing_is_refused_outright_even_via_the_classmethods`;
- `test_a_duck_typed_object_cannot_stand_in_for_evidence_at_the_result_boundary`;
- `test_result_scalar_fields_are_checked_by_exact_type` -- eleven malformed
  scalar cases, including `semantic_prompts_sent=False`;
- `test_the_false_semantic_prompts_sent_counterexample_is_refused`;
- `test_result_enum_fields_are_checked_by_exact_type`;
- `test_a_failed_or_not_reached_gate_status_cannot_coexist_with_a_pass` --
  item 10's exact counterexample;
- `test_gate_status_pairs_must_name_every_declared_gate_exactly_once`,
  `test_gate_status_pairs_rejects_an_unrecognized_status_text`,
  `test_gate_status_pairs_shape_is_checked_structurally`,
  `test_a_refusal_result_still_validates_its_gate_status_pairs`;
- `test_the_public_evidence_constructor_cannot_assert_any_field_at_all` --
  the exact `CategoryBEvidence` counterexample from the brief;
- `test_retention_ready_true_is_only_reachable_by_actually_scrubbing_the_payload`;
- `test_a_malformed_scrub_check_result_is_refused_never_coerced`;
- `test_refused_requires_at_least_one_bounded_finding_code`;
- `test_the_full_pipeline_result_actually_satisfies_the_hardened_invariants`
  -- a real, end-to-end controller PASS still constructs cleanly under every
  new invariant.

## Offline suite result

```text
757 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(514 unchanged I1/I2 through FU3B; 243 in `test_i2b_controller.py`, up from
FU2's 204 -- 39 new/rewritten tests for this follow-up.)

Frozen suites re-run unmodified:

```text
experiments/pi_external_runtime_ar1/tests         96 passed, 0 failed
experiments/pi_external_runtime_ar2/tests        290 passed, 0 failed
experiments/pi_external_runtime_ar2_o1/tests      89 passed, 0 failed
tests/  (the production suite)                  3504 passed, 0 failed
```

No file under `ar1/`, `ar2/`, `o1/`, `src/`, root `tests/` or `projects/` was
touched. `i2b_session.py` and `i2b_workspace.py` were not modified --  the
self-review sweep found no instance of any of the three blockers' defect
classes in either module.

## Corrected claims

The "Terminal-pass rule" section above previously stated the terminal rule
"holds even for a directly-constructed result" -- **false at the time it was
written**, for the reason item 2 documents. The passage is corrected in
place, with a pointer to this section; it is accurate as of FU2A.

## What this does NOT establish

Unchanged from FU2's own closing section: no zero-prompt live gate has ever
run; `get_commands` still proves nothing about the active tool registry; the
adapter trust boundary is unchanged (an adapter that deliberately fabricates
every component of an observation remains out of this design's stated
scope); the synthetic workspace authority is not real-workspace authority
and is not a step toward one; no claim about descendants, inference, or GPU
work; redaction/scrubbing remain backstops, not guarantees.

**Additionally, narrowly, from this follow-up:** the exact-type checks added
to `CategoryBControllerResult` and the classmethod-only construction added
to `CategoryBEvidence` are, like every other component/verdict split in this
design, a correctness/integrity control against a caller (including a
future refactor) inside the trust boundary -- never a defense against a
caller willing to import and call a package-internal (single-underscore)
classmethod directly with fabricated inputs it controls end-to-end. That
residual is inherent to Python and is stated, not hidden.

---

# 5F3B-I2B-FU2B -- Terminal Cross-Field + Evidence Binding Closure (Offline Only)

> **OFFLINE ONLY. NO LIVE ACTIVITY OF ANY KIND.** No Pi/Node process, no
> socket, no model call, no credential read, no semantic prompt, no real
> workspace access. Category-B live execution remains **NO-GO**, Q1/Q2
> remain **NO-GO**, real-workspace authority remains **NO-GO**. The I2A/FU3
> design family is unchanged and was not reopened. No frozen AR1/AR2/O1/I1/I2
> code or contract was modified. `i2b_session.py`/`i2b_workspace.py` were not
> touched -- no reproduced defect required it.

FU2A hardened individual field TYPES (exact-type checks, no bare Python
truthiness) but left `CategoryBControllerResult` semantically incoherent:
fields could individually be well-typed while collectively describing an
impossible run. **The FU2A test helper's own default kwargs were themselves
the exact contradiction** this phase closes -- `pi_config_created=True`
alongside `cleanup.attempted=False`; `broker_created`/
`runtime_session_established=True` alongside `runtime_teardown`/
`broker_shutdown` left at `NOT_REQUIRED`; a single GLOBAL vocabulary of
gate-status strings that let ANY gate use ANY other gate's text; and a
retention-ready `CategoryBEvidence` scrub-built from `{"ok": True}`, with no
relationship to the result consuming it, accepted unconditionally. Roughly
twenty FU2A tests reused that contradictory default and were, without
anyone intending it, no longer isolating what they claimed to test -- the
FIRST cross-field check the constructor happened to run caught them all,
regardless of which field each test actually overrode.

## Mandatory counterexamples: which succeeded before the fix

All ten reproduced against the actual pre-fix code, isolated to ONE field
each (not merely via the already-contradictory shared default):

| # | Case | Result |
|---|---|---|
| 1 | `pi_config_created=True` + `cleanup.attempted=False` | **Succeeded** |
| 2 | `runtime_session_established=True` + `runtime_teardown.state=NOT_REQUIRED` | **Succeeded** |
| 3 | `broker_created=True` + `broker_shutdown.state=NOT_REQUIRED` | **Succeeded** |
| 4 | typed `runtime_teardown=NOT_REQUIRED` but `gate_statuses['runtime_teardown']=="PASSED"` | **Succeeded** |
| 5 | `gate_statuses['route_check']=="NOT_REQUIRED"` on an otherwise-passing result | **Succeeded** |
| 6 | retention-ready evidence scrub-built from `{"ok": True}` | **Succeeded** |
| 7 | `candidate="not-a-frozen-candidate"` on a PASS | **Succeeded** |
| 8 | `facts.pi_version_observed=True` + `observed_pi_version=None` | **Succeeded** |
| 9 | scrub helper returning a non-string finding entry | **Succeeded** (the entry's `str()` was called and RETAINED) |
| 10 | refusal whose `failed_gate`/`failure_code` disagree with that gate's own `_gate_status_pairs` entry | **Succeeded** |

## Exact cross-field invariants added

All in `CategoryBControllerResult.__post_init__`, unless noted:

1. **Universal (every outcome):** `pi_config_created == cleanup.attempted`.
   Both are, in the real controller, literally the SAME
   `generated_config is not None` fact -- `_attempt_cleanup(None)` iff no
   config was ever created, always attempted otherwise. Mechanically certain
   from source inspection, not invented.
2. **Universal:** `facts.pi_version_observed == (observed_pi_version is not
   None)`. Both come from the SAME `RuntimeLaunchObservation`, assigned at
   the SAME call site.
3. **Universal:** each of the other ELEVEN `CompatibilityFacts` fields must
   agree with its own compatibility gate's `PASSED`/not-`PASSED` status --
   **except when that gate was never reached (`NOT_REACHED`)**, an
   intentional, narrow exception for the four LAUNCH facts
   (`pi_version_observed`/`rpc_launch_shape_valid`/
   `required_launch_flags_accepted`/`lf_jsonl_correlation_succeeded`), which
   are recorded from the launch observation BEFORE the controller knows
   whether `RUNTIME_LAUNCH` itself will pass -- a session mismatch can still
   fail `RUNTIME_LAUNCH` AFTER a fact already reads `True`, and the four
   launch-fact gates are only evaluated in a LATER block gated behind
   `RUNTIME_LAUNCH` having passed. This asymmetry was discovered live, mid-
   implementation, when the first (unconditional) version of this check
   broke FOUR genuinely-passing offline tests exercising the real
   controller pipeline -- not a synthetic counterexample. Once a gate IS
   reached, the equivalence holds exactly, for all thirteen facts uniformly
   (the two `PROTOCOL_INTEGRITY` facts checked by conjunction, since ONE
   gate is jointly gated by both).
4. **PASS-only:** `candidate` must be a member of the frozen
   `qualification.records.CANDIDATE_MODEL_IDS` -- imported directly, never
   re-declared.
5. **PASS-only:** `pi_config_created`/`broker_created`/
   `runtime_session_established` all `True`.
6. **PASS-only:** `runtime_teardown.state is CLOSED_BY_ORCHESTRATOR` and
   `broker_shutdown.state is CLOSED_BY_ORCHESTRATOR` -- **not merely
   `closure_satisfied`**, which `NOT_REQUIRED` also satisfies and cannot be
   true of a resource the result itself says was created.
7. **PASS-only:** `cleanup.attempted and cleanup.scrub_verified`.
8. **PASS-only:** `observed_pi_version is not None` (redundant with
   `facts.all_established` + invariant 2 above, by design -- explicit per
   this phase's own brief, kept as defense in depth).

## Per-gate status validation rule

Replaces FU2A's single global vocabulary:

- **The three typed-object-bound closure gates**
  (`RUNTIME_TEARDOWN`/`BROKER_SHUTDOWN`/`GENERATED_CONFIG_CLEANUP`) are
  bound by **direct equality** to the already-validated typed object's own
  `status_text` property -- no separate vocabulary at all, no possibility of
  drift between the typed object and its string projection, for EVERY
  outcome.
- **`EVIDENCE_SAFETY`** is bound to `evidence.retention_ready`: `PASSED`
  exactly iff retention-ready; otherwise a `FAILED:<code>` naming one of the
  three codes this gate's own producer ever assigns
  (`SAFETY_CONTEXT_UNPROVABLE`/`EVIDENCE_SCRUB_REFUSED`/
  `MALFORMED_ADAPTER_RESULT`).
- **Each of the 21 COMPATIBILITY gates** gets its OWN bounded set of
  failure codes, read directly off that gate's own `_fail(...)` call
  site(s) in `run_category_b_controller` (`_COMPATIBILITY_GATE_ALLOWED_FAILURE_CODE_VALUES`,
  asserted at import time to cover `COMPATIBILITY_GATES` exactly). A status
  text valid on one gate (`"CLOSED"`, a broker-only text; or
  `BROKER_NOT_READY`, `BROKER_READY`'s own code) is refused on any other.
- **On a terminal PASS**, every compatibility gate must be **exactly**
  `"PASSED"` -- not merely "a text that gate's own producer could have
  emitted", which would still accept a stray `FAILED:.../NOT_REACHED` entry
  sitting alongside an otherwise-passing result. This is a SEPARATE check
  from the per-gate vocabulary rule above (needed because that rule alone
  does not distinguish PASS from REFUSAL) -- found missing during this
  phase's OWN implementation, when a mandatory counterexample regression
  (`route_check` `NOT_REACHED`/`FAILED:...`) failed against the first draft.
- `failed_gate`/`failure_code`, when set, must agree EXACTLY with that
  gate's own `_gate_status_pairs` entry (`f"FAILED:{failure_code.value}"`).

## Evidence-binding mechanism chosen

**Smallest mechanically sound shape, per the brief's own framing (option
"validate the retained canonical body against the result's own
projection").** No new digest/token/registry mechanism, and
`CategoryBControllerResult` was NOT converted into a factory-controlled
type (both were offered as options; neither was needed).

`_require_evidence_describes_this_result` runs whenever
`evidence.retention_ready` is `True` (for EVERY outcome, not only PASS) and
compares the retained body, key by key, against the RESULT's OWN
already-validated fields -- never a caller-supplied duplicate boolean:
`candidate`, `semantic_prompts_sent`, `compatibility_gate_passed` (derived
from `outcome`), `compatibility_facts` (`facts.as_dict()`),
`observed_pi_version`, `gate_statuses` (minus `EVIDENCE_SAFETY`, matching
the existing accepted `_build_evidence` exclusion), and the three closure
status-text strings. Any mismatch on any covered key is refused.

**Honest scope, stated per the brief's own "where available" framing.** The
frozen route/model/provider facts (`model_id`/`provider_id`/
`gateway_class`) and the safety-context needle codes are part of the
canonical evidence body but are **not** typed fields on
`CategoryBControllerResult` at all (they live only as local variables inside
`run_category_b_controller`) -- so they are not, and cannot yet be, bound by
this mechanism. This is recorded as an explicit residual, not a silent gap.

**Stated residual, matching every other component/verdict split in this
design:** this binds the result to whatever payload `_build_from_payload`
was actually called with -- it is not a defense against a caller willing to
import that package-internal classmethod directly and hand-craft a payload
whose keys happen to match a target result's fields; such a caller already
controls both sides of the comparison.

## Same-class bypasses found during the second adversarial review

Two, both fixed with a regression before completion was reported.

**1. A genuine PRODUCTION bug, surfaced end to end by the new closure-gate
equality binding, not a synthetic construction.**
`CleanupStatus.status_text`'s FAILED branch returned
`f"FAILED:{self.classification.autonomous_classification.value}"` --
embedding an `AutonomousClassification` member (a DIFFERENT enum than
`CategoryBFailureCode`). The controller's own closure loop separately calls
`_fail(GENERATED_CONFIG_CLEANUP, CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED)`
for an unverified cleanup (`CleanupStatus` carries no `failure_code`
attribute for the loop's `getattr(status, "failure_code", None) or
default_code` to find, so the fallback always fires) -- and `_fail`
OVERWRITES `gate_statuses['generated_config_cleanup']` with that fixed code
immediately afterward. The typed object's own property and what the
controller actually recorded for the SAME gate therefore DISAGREED, and the
SAME evidence body carried BOTH strings under two different keys
(`gate_statuses['generated_config_cleanup']` and
`orchestrator_generated_config_cleanup_status`). Reproduced through TWO
pre-existing FU2/FU2A offline tests that call the real
`run_category_b_controller` (`test_all_gates_pass_but_config_cleanup_fails_is_an_infrastructure_refusal`,
`test_the_frozen_cleanup_helpers_own_return_is_consumed_fail_closed`), both
of which started failing the moment the new equality binding was added,
before any test-suite change was made to accommodate it. **Fixed** by
changing `status_text`'s FAILED branch to the fixed
`CategoryBFailureCode.GENERATED_CONFIG_CLEANUP_UNVERIFIED` code, matching
exactly what `_fail()` always produces for this gate.
`classification` remains a real, validated, retained diagnostic fact on the
object -- it is simply no longer the STATUS TEXT's source. Regression:
`test_cleanup_status_text_agrees_with_what_fail_actually_records`,
`test_cleanup_status_classification_is_a_real_diagnostic_still_carried`.

**2. `CompatibilityFacts` fields were not bound to their own compatibility
gate's status at all.** Found during this phase's OWN post-implementation
adversarial review (not the mandatory pre-coding list). A hand-built
REFUSAL result could claim `facts.h1_extension_identity_matched=True` while
`gate_statuses['h1_extension_identity']` read `FAILED:...` -- two
individually-typed, individually-valid objects disagreeing about the same
underlying fact, exactly the "individually valid objects that contradict
one another" class the post-implementation review brief named. **Fixed**
via `_SINGLE_FACT_TO_GATE` (eleven of the thirteen facts map 1:1 to their
own gate; the two `PROTOCOL_INTEGRITY` facts are checked by conjunction),
enforced only when the gate was actually reached (see cross-field
invariant 3 above for the launch-facts exception this required). Sweep
regression: `test_every_single_mapped_fact_is_checked_against_its_own_gate`
(all eleven, independently); `test_protocol_integrity_conjunction_is_checked`;
positive controls proving the exception is neither too broad
(`test_the_launch_facts_are_still_checked_once_their_gate_is_reached`) nor
too narrow (`test_the_launch_facts_may_legitimately_be_true_while_not_reached`).

## New regression tests

All in `tests/test_i2b_controller.py`, under the new
`# FU2B -- terminal cross-field + per-gate status + evidence-binding
closure` section: ten `test_counterexample_N_*` tests (one per mandatory
counterexample, isolated to exactly one field via a corrected, genuinely
self-consistent `_build_result`/`_passing_gate_status_pairs` baseline --
every override now isolates the SPECIFIC check it names, verified directly
against the implementation before being trusted); the PASS-shape tests
(`test_pass_requires_*`, four); per-gate vocabulary tests
(`test_a_closure_only_status_text_is_refused_on_a_compatibility_gate`,
`test_a_failure_code_valid_on_one_gate_is_refused_on_another`,
`test_every_compatibility_gate_has_its_own_declared_allowed_codes`,
`test_evidence_safety_gate_is_bound_to_retention_ready`); evidence-binding
tests (a nine-way parametrized per-key mismatch sweep, plus a REFUSAL-outcome
positive/negative pair); malformed-finding tests (non-string entries never
stringified, out-of-pattern codes, the `_refused` path, and a positive
sweep proving every REAL finding code this package's frozen scrub layer
produces satisfies the new bounded pattern); the nearby-sweep tests
(`_ResourceClosureStatus.failure_code`/`CleanupStatus.classification` exact-
type, both previously blowing up LATER with an unrelated `AttributeError`
instead of refusing at construction); the two same-class-bypass regressions
above; `test_dataclasses_replace_cannot_break_a_genuine_passing_result`;
and `test_every_real_refusal_path_satisfies_the_new_binding_invariants`,
which drives the REAL controller through four distinct refusal gates and
re-asserts the headline bindings explicitly on each.

**The FU2A helper's isolation defect was verified directly, not assumed
fixed.** Before adding new tests, every existing FU2A test using
`_build_result` was re-run against a small standalone script constructing
each scenario in isolation (flipping exactly the ONE field each test names,
against an otherwise-valid baseline) and printing the actual raised
message -- confirming each now fails for the SPECIFIC reason it claims,
not merely "some ValueError, possibly the wrong one." Two isolation bugs
surfaced this way in the NEW tests themselves during this process (an
`observed_pi_version` cross-check firing before the intended check in two
places; a misplaced `@pytest.mark.parametrize` decorator left attached to
the wrong function after a naive text-insertion patch) and were corrected
before this report.

## Offline suite result

```text
823 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(514 unchanged I1/I2 through FU3B; 309 in `test_i2b_controller.py`, up from
FU2A's 243 -- 66 new/rewritten tests for this follow-up.)

Frozen suites re-run unmodified:

```text
experiments/pi_external_runtime_ar1/tests         96 passed, 0 failed
experiments/pi_external_runtime_ar2/tests        290 passed, 0 failed
experiments/pi_external_runtime_ar2_o1/tests      89 passed, 0 failed
tests/  (the production suite)                  3504 passed, 0 failed
```

No file under `ar1/`, `ar2/`, `o1/`, `src/`, root `tests/` or `projects/` was
touched. `i2b_session.py`/`i2b_workspace.py` were not modified -- no
reproduced defect required it.

## Corrected claims

FU2A's own closing README/FINDINGS text described
`CategoryBControllerResult` as "valid by construction" without
qualification. That was accurate for individual field TYPES and
subclass/duck-type substitution, but overstated for CROSS-FIELD coherence --
the FU2A test helper's own default kwargs were themselves the counterexample.
README.md's I2B closing block is corrected in place, with a pointer to this
section.

## What this does NOT establish

Unchanged from FU2/FU2A's own closing sections: no zero-prompt live gate has
ever run; `get_commands` still proves nothing about the active tool
registry; the adapter trust boundary is unchanged; the synthetic workspace
authority is not real-workspace authority; no claim about descendants,
inference, or GPU work; redaction/scrubbing remain backstops, not
guarantees.

**Additionally, narrowly, from this follow-up:** the evidence-binding check
covers exactly the canonical-evidence fields already represented as typed
`CategoryBControllerResult` fields -- `model_id`/`provider_id`/
`gateway_class`/the safety-needle codes are NOT independently re-verified
against the result, because the result carries no typed field for them at
all. And, as with every component/verdict split in this design, none of
these checks defend against a caller willing to import a package-internal
classmethod directly and fabricate both sides of a comparison it fully
controls.

# 5F3B-I2B-FU2C -- Refusal Evidence Semantic Closure (Offline Only)

> **OFFLINE ONLY. NO LIVE ACTIVITY OF ANY KIND.** No Pi/Node process, no
> socket, no model call, no credential read, no semantic prompt, no real
> workspace access. Category-B live execution remains **NO-GO**, Q1/Q2
> remain **NO-GO**, real-workspace authority remains **NO-GO**. The I2A/FU3
> design family is unchanged and was not reopened; H1/command provenance,
> credential ordering, partial-cleanup ownership, evidence-binding
> architecture and candidate-qualification design were not reopened. No
> frozen AR1/AR2/O1/I1/I2 code or contract was modified.
> `i2b_session.py`/`i2b_workspace.py` were not touched -- no reproduced
> defect required either.

FU2B's structural checks (cross-field invariants, per-gate status
vocabulary, evidence binding) were accepted, but independent source review
found FU2B stopped one layer too shallow in three places -- each checked
that a nested value carried the right EXACT TYPE, but not that its
CONTENTS were an actually-reachable combination:

1. `_ResourceClosureStatus.__post_init__` validated `failure_code` by being
   exactly a `CategoryBFailureCode` -- **any** member, on **any**
   `ResourceClosureState`, on **either** resource kind. Nothing constrained
   `failure_code` by the RESOURCE the status describes or by the STATE it is
   attached to.
2. `CategoryBControllerResult.__post_init__` checked that `failed_gate`,
   when set, agreed with THAT gate's own `gate_statuses` entry -- but never
   verified `failed_gate` was the FIRST failed gate the controller's own
   `_fail()` would have recorded. The real controller's `_fail()` sets
   `failed_gate`/`failure_code` only on its OWN first call
   (`if failed_gate is None: failed_gate = gate; failure_code = code`); every
   later `_fail()` call updates only that gate's own `gate_statuses` entry.
   So the true result semantics are `failed_gate = the first failed gate
   this controller run encountered` -- a fact nothing checked.
3. `CleanupStatus.__post_init__` validated `classification`'s exact type
   (`CleanupFailureClassification`) but never its four FIELDS. The frozen
   `i2_cleanup.CleanupFailureClassification` dataclass (deliberately not
   modified here) performs no validation of its own.

## Mandatory pre-coding counterexamples: which succeeded before the fix

All ten reproduced against the actual pre-fix code before any change was
written:

| # | Case | Result |
|---|---|---|
| 1 | `RuntimeTeardownStatus(state=SHUTDOWN_FAILED, failure_code=BROKER_SHUTDOWN_INCOMPLETE)` | **Succeeded** |
| 2 | `RuntimeTeardownStatus(state=SHUTDOWN_REFUSED_FOREIGN_SESSION, failure_code=RUNTIME_TEARDOWN_FAILED)` (instead of the foreign-session-specific code) | **Succeeded** |
| 3 | `BrokerShutdownStatus(state=SHUTDOWN_FAILED, failure_code=RUNTIME_TEARDOWN_FAILED)` | **Succeeded** |
| 4 | `CLOSED_BY_CREATOR_UNVERIFIED` carrying the OTHER resource kind's authority-unavailable code | **Succeeded** (both directions) |
| 5 | a hand-built refusal with two FAILED gates (an earlier compatibility gate and a later closure gate, and separately H1 + the later namespace gate) where `failed_gate` names the LATER one | **Succeeded** (both variants) |
| 6 | `failed_gate` naming a gate whose OWN `gate_statuses` text correctly matches `failure_code`, while an EARLIER gate is independently also `FAILED:...` | **Succeeded** (same construction as #5 -- the per-gate agreement check alone cannot see gate POSITION) |
| 7 | `CleanupFailureClassification(semantic_prompts_sent=1, ...)` alongside the pre-prompt `autonomous_classification` | **Succeeded** |
| 8 | `CleanupFailureClassification(..., scoring_eligible=True)` | **Succeeded** |
| 9 | `CleanupFailureClassification(..., autonomous_classification=None)` (a shape only the post-prompt branch approaches, and even that branch never leaves it bare) | **Succeeded** |
| 10 | genuine runtime/broker/cleanup refusal shapes (positive controls) | Already constructed correctly -- confirmed unaffected by the fix |

## Exact resource/state failure-code domains added

`_ResourceClosureStatus` gained one `ClassVar` table,
`_ALLOWED_FAILURE_CODES_BY_STATE: Mapping[ResourceClosureState,
frozenset[CategoryBFailureCode]]`, deliberately left empty on the (never
instantiated) base class and overridden once per concrete subclass. Every
entry was read directly off that subclass's own `_close_runtime`/
`_close_broker` producer function -- confirmed by grepping every
`RuntimeTeardownStatus(...)`/`BrokerShutdownStatus(...)` construction site
in `i2b_controller.py` and finding all of them inside those two functions,
none elsewhere:

**`RuntimeTeardownStatus`** (from `_close_runtime`):

| State | Allowed code(s) |
|---|---|
| `SHUTDOWN_AUTHORITY_UNAVAILABLE` | `RUNTIME_TEARDOWN_AUTHORITY_UNAVAILABLE` |
| `SHUTDOWN_REFUSED_FOREIGN_SESSION` | `RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION` |
| `SHUTDOWN_FAILED` | `RUNTIME_TEARDOWN_FAILED`, `RUNTIME_SESSION_MISMATCH` |
| `CLOSED_BY_CREATOR_UNVERIFIED` | `CLOSED_BY_CREATOR_UNVERIFIED` |
| `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` | `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` |

**`BrokerShutdownStatus`** (from `_close_broker`, the exact mirror):

| State | Allowed code(s) |
|---|---|
| `SHUTDOWN_AUTHORITY_UNAVAILABLE` | `BROKER_SHUTDOWN_AUTHORITY_UNAVAILABLE` |
| `SHUTDOWN_REFUSED_FOREIGN_SESSION` | `BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION` |
| `SHUTDOWN_FAILED` | `BROKER_SHUTDOWN_INCOMPLETE`, `BROKER_SESSION_MISMATCH` |
| `CLOSED_BY_CREATOR_UNVERIFIED` | `CLOSED_BY_CREATOR_UNVERIFIED` |
| `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` | `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` |

The two creator-retained-ownership rows are the SAME two codes on both
tables, deliberately -- `_RUNTIME_CLOSURE_FAILURE_CODES` and
`_BROKER_CLOSURE_FAILURE_CODES` are already, in the source, the identical
`MappingProxyType` object (`_BROKER_CLOSURE_FAILURE_CODES =
_RUNTIME_CLOSURE_FAILURE_CODES`), so `_creator_retained_ownership_state`
genuinely returns the same code regardless of resource kind. No generic
global closure-code set was introduced; every other row is resource-kind-
specific and refused on the other kind
(`test_fu2c_a_code_valid_for_runtime_is_not_automatically_valid_for_broker`).
`NOT_REQUIRED`/`CLOSED_BY_ORCHESTRATOR`/`CLOSED_BY_CREATOR_VERIFIED` carry no
table entry at all -- they are satisfied closures and are refused a
`failure_code` by the existing (unchanged) satisfied/unsatisfied branch
before the new table is ever consulted. A module-import-time assertion
(`test_fu2c_resource_closure_tables_cover_every_unsatisfied_state` mirrors
it in the test suite) proves both tables' key sets equal exactly
`set(ResourceClosureState) - {NOT_REQUIRED, CLOSED_BY_ORCHESTRATOR,
CLOSED_BY_CREATOR_VERIFIED}` -- five states, never a subset, a superset, or
one table forgetting a state the other has.

`test_fu2c_every_state_failure_code_pairing_is_exhaustively_swept` is the
strongest available proof of exactness: for both classes, for every one of
the five unsatisfied states, for every one of the 43 declared
`CategoryBFailureCode` members -- the allowed codes construct cleanly and
every other code is refused. 430 individual constructions per run.

## First-failure attribution mechanism

`CategoryBControllerResult.__post_init__` now scans `gate_statuses` in
`CategoryBGateName`'s own declaration order (confirmed, not merely assumed,
to be the controller's real evaluation order: the 23 `COMPATIBILITY_GATES`
in that exact order, followed by the four `CLOSURE_GATES` --
`RUNTIME_TEARDOWN -> BROKER_SHUTDOWN -> GENERATED_CONFIG_CLEANUP ->
EVIDENCE_SAFETY` -- in that exact order, both matching the real
`run_category_b_controller` source sequence read top to bottom) and:

- for `INFRASTRUCTURE_REFUSAL`: finds the FIRST `"FAILED:..."` entry, requires
  one to exist, and requires `failed_gate` to be exactly that gate (not
  merely "a gate whose own text matches its own `failure_code`", which the
  pre-existing agreement check already covered and which is silent about
  POSITION);
- for `CATEGORY_B_GATE_PASSED`: requires no gate at all to read `"FAILED:..."`
  (a narrower, explicit restatement of what invariants 5/6/7 in the FU2B
  section already implied together, made direct so the intent cannot be
  missed by a future reader of either check alone).

This is deliberately NOT a new generic workflow/state-machine validator --
it is the one first-failure-attribution invariant the controller's own
`_fail()` closure already implements operationally
(`if failed_gate is None: failed_gate = gate; failure_code = code`), made
externally checkable.

## CleanupFailureClassification coherence rule

`CleanupStatus.__post_init__` now calls a new
`_require_category_b_cleanup_failure_shape` helper whenever `classification`
is not `None` (i.e. on the already-existing failed/unverified path only).
The helper compares the given classification field-by-field against a
FRESHLY minted reference from the frozen, reused
`classify_cleanup_failure(semantic_prompts_sent=SEMANTIC_PROMPTS_SENT)` --
never against hand-declared literal field values:

- `semantic_prompts_sent`: exact `int` type, then `!=` against the
  reference's value (always `0`) -- catches a wrong value AND the
  `semantic_prompts_sent=False` truthiness bypass (`False == 0` in Python)
  the same way this design already guards `CategoryBControllerResult`'s own
  field of the same name.
- `autonomous_classification`: identity (`is not`) against the reference's
  member -- an enum-shaped singleton comparison, never `==`, so a
  duck-typed/foreign "equal-by-value" stand-in cannot pass.
- `run_validity`: `is not None` -- a pre-prompt refusal carries no
  `run_validity` at all, so ANY non-`None` value (regardless of its own
  type) is wrong.
- `scoring_eligible`: `require_exact_bool` (the same helper `CleanupStatus`
  already uses for its own `attempted`/`scrub_verified` fields), then an
  explicit `False` check.

**This never imports or names `AutonomousClassification` inside
`i2b_controller.py`.** `test_no_candidate_scoring_machinery_is_reachable`
(zero-prompt-authority suite, unchanged) already forbids that exact token in
this module's code -- reusing the frozen function's own RETURN VALUE for the
identity comparison, rather than re-declaring the correct enum member by
importing the enum, satisfies the field-level check without ever writing
the forbidden name. `test_fu2c_no_i2b_module_names_autonomous_classification`
pins this down directly, and the full zero-prompt-authority sweep
(`test_no_i2b_module_has_a_prompt_shaped_name_anywhere`,
`test_no_i2b_module_imports_a_live_io_primitive`,
`test_no_candidate_scoring_machinery_is_reachable`) still passes unmodified.

`i2_cleanup.py` (frozen) was **not** modified -- `CleanupFailureClassification`
still performs no validation of its own; the new check lives entirely on
the CONSUMING side, in `i2b_controller.py`.

## Same-class bypasses found during the second adversarial review

None found beyond the three named blockers themselves. The review checked,
specifically:

- **Per-resource failure-code drift** -- closed by exhaustively sweeping
  both classes' tables against all 43 `CategoryBFailureCode` members
  (`test_fu2c_every_state_failure_code_pairing_is_exhaustively_swept`) and
  grep-auditing every construction site of both classes in
  `i2b_controller.py`, confirming all of them live inside `_close_runtime`/
  `_close_broker` and nowhere else -- so the tables cannot have missed a
  reachable code the real source can emit.
- **State/failure-code disagreement** -- same sweep; every combination
  outside each state's declared set is mechanically refused.
- **`failed_gate` not being the first failure** -- checked against seven
  distinct REAL controller refusal shapes, including one where the
  compatibility failure and the closure failure both occur in the SAME run
  (`test_fu2c_real_pipeline_earlier_compat_failure_stays_failed_gate_despite_later_cleanup_failure`)
  and two where a real double-gate failure occurs from one observation
  (the `h1_components={"malformed_source_metadata": True}` case inside
  `test_fu2c_real_refusals_failed_gate_is_always_the_first_failed_gate_in_declared_order`)
  or where only a closure gate fails and every compatibility gate genuinely
  passed (`runtime_child_exited=False`/`broker_reached_closed=False`).
- **Typed diagnostic objects whose internal fields remain annotation-only
  trust** -- `CleanupFailureClassification` was exactly this shape before
  this phase (exact-type checked, fields untouched); now closed. No other
  typed diagnostic object consumed by `CategoryBControllerResult`/
  `CleanupStatus`/`_ResourceClosureStatus` was found in the same shape
  during this pass (`CompatibilityFacts`, `CategoryBEvidence` and the two
  closure-status classes already had FU2A/FU2B/this-phase field-level
  checks; the observation types in `i2b_session.py` already validate their
  own fields in `__post_init__` and were not touched).
- **New bool/truthiness coercion** -- every new comparison is by exact type
  then `!=`/`is`/`is not`, or (for `scoring_eligible`) `require_exact_bool`
  followed by a plain `if` on an already-type-proven `bool` (the same
  pattern the surrounding, already-accepted `CleanupStatus` code uses for
  `attempted`/`scrub_verified`) -- never a bare `if x:` on an unproven value.
- **Any gate/status/evidence field that can now contradict another
  individually valid field** -- none found; the full 344-test
  `test_i2b_controller.py` suite (was 309) and the full 858-test package
  suite (was 823) both pass with no test weakened, only two corrected (see
  "Corrected claims" below), proving every existing accepted invariant still
  holds simultaneously with the three new ones.

## New regression tests

35 new tests in `tests/test_i2b_controller.py`, under a new `# FU2C --
resource/state failure-code domains + first-failure attribution +
cleanup-classification coherence` section:

- **Blocker 1 (9 tests, one parametrized ×2, one parametrized ×2):**
  `test_fu2c_counterexample_1/2/3` (the three single-resource pre-coding
  reproductions), `test_fu2c_counterexample_4_creator_unverified_carrying_unrelated_resource_code`
  (parametrized, both directions), `test_fu2c_every_state_failure_code_pairing_is_exhaustively_swept`
  (parametrized ×2, the 430-combination sweep),
  `test_fu2c_a_code_valid_for_runtime_is_not_automatically_valid_for_broker`,
  `test_fu2c_the_shared_creator_retained_codes_really_are_shared`,
  `test_fu2c_resource_closure_tables_cover_every_unsatisfied_state`,
  `test_fu2c_real_controller_creator_retained_broker_state_still_constructs`
  (a genuine end-to-end `_close_broker` creator-retained-ownership
  reproduction, not merely a synthetic one).
- **Blocker 2 (7 tests, one parametrized ×7):**
  `test_fu2c_counterexample_5_earlier_compat_failure_later_closure_failure_wrong_failed_gate`,
  `test_fu2c_counterexample_6_h1_and_namespace_both_failed_wrong_failed_gate_is_later`,
  `test_fu2c_evidence_safety_alone_failing_may_be_failed_gate` (positive
  control), `test_fu2c_real_pipeline_earlier_compat_failure_stays_failed_gate_despite_later_cleanup_failure`
  (real end-to-end, both a compatibility AND a closure failure in one run),
  `test_fu2c_real_refusals_failed_gate_is_always_the_first_failed_gate_in_declared_order`
  (parametrized over seven real refusal shapes, stated as a GENERAL
  property rather than one scenario at a time),
  `test_fu2c_a_genuine_pass_still_constructs_with_no_failed_gate_check_active`
  (positive control).
- **Blocker 3 (10 tests, one parametrized ×4):**
  `test_fu2c_pre_coding_check_7/8/9` (the three named pre-coding shapes),
  `test_fu2c_cleanup_classification_run_validity_set_is_refused`,
  `test_fu2c_cleanup_classification_semantic_prompts_sent_false_is_refused`
  (the `False == 0` bypass, named explicitly per this design's existing
  convention), `test_fu2c_cleanup_classification_scoring_eligible_non_bool_is_refused`
  (parametrized ×4: `1`, `0`, `"false"`, `None`),
  `test_fu2c_pre_coding_check_10_genuine_cleanup_classification_still_constructs`
  (positive control), `test_fu2c_real_pipeline_cleanup_failure_still_constructs_under_the_new_check`
  (real end-to-end, via the same monkeypatched-`scrub_generated_qualification_config`
  reproduction FU2B's own regression already used),
  `test_fu2c_no_i2b_module_names_autonomous_classification` (the residual
  proof for why the fix does not need to violate the existing
  zero-prompt-authority sweep).

**Two pre-existing FU2B tests were corrected, not weakened, by the new
checks -- exactly the same class of "the fix surfaces a defect in an
existing test" event FU2B itself reported for
`CleanupStatus.status_text`.**
`test_every_unsatisfied_closure_state_reports_no_orchestrator_attempt` had
constructed all four of `SHUTDOWN_REFUSED_FOREIGN_SESSION`/
`SHUTDOWN_AUTHORITY_UNAVAILABLE`/`CLOSED_BY_CREATOR_UNVERIFIED`/
`PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` with the SAME bare
`RUNTIME_TEARDOWN_FAILED` code -- a combination the new table correctly
refuses for three of the four states. It now supplies each state's own
correct code. `test_pass_requires_runtime_teardown_and_broker_shutdown_closed_by_orchestrator`
asserted a specific error-message substring
(`"CLOSED_BY_ORCHESTRATOR"`) for a `SHUTDOWN_REFUSED_FOREIGN_SESSION`
`runtime_teardown` sitting inside an otherwise-PASS result; that
construction now correctly trips the NEW, earlier "a PASS may have no
FAILED gate" check first (a `FAILED:...` runtime_teardown status text is,
after all, a FAILED gate) -- the test's `match` pattern was broadened to
accept either message, since both are correct refusals of the same
underlying contradiction.

## Offline suite result

```text
858 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(514 unchanged I1/I2 through FU3B; 344 in `test_i2b_controller.py`, up from
FU2B's 309 -- 35 new tests, 2 corrected, for this follow-up.)

Frozen suites re-run unmodified:

```text
experiments/pi_external_runtime_ar1/tests         96 passed, 0 failed
experiments/pi_external_runtime_ar2/tests        290 passed, 0 failed
experiments/pi_external_runtime_ar2_o1/tests      89 passed, 0 failed
tests/  (the production suite)                  3504 passed, 0 failed
```

No file under `ar1/`, `ar2/`, `o1/`, `src/`, root `tests/` or `projects/` was
touched. `i2b_session.py`/`i2b_workspace.py`/`i2_cleanup.py` were not
modified -- no reproduced defect required any of them.

## Corrected claims

FU2B's own closing text did not claim more than it had closed, so nothing
in its prose is corrected here. What is corrected is narrower: two of
FU2B's OWN regression tests (named above) had encoded assumptions --
"any bare `RUNTIME_TEARDOWN_FAILED` demonstrates the derived-boolean
properties", "a `CLOSED_BY_ORCHESTRATOR` requirement is the only thing a
PASS-shaped invariant can fail on" -- that were true under FU2B's own
(looser) validation and are no longer the most specific true statement
under FU2C's. Neither test's INTENT changed; both still prove exactly what
their names say.

## What this does NOT establish

Unchanged from FU2/FU2A/FU2B's own closing sections, and true as of this
phase's acceptance: no zero-prompt live gate had run (one has since occurred
-- see the TOP-LEVEL CORRECTION at the head of this document);
`get_commands` still proves nothing about the active
tool registry; the adapter trust boundary is unchanged; the synthetic
workspace authority is not real-workspace authority; no claim about
descendants, inference, or GPU work; redaction/scrubbing remain backstops,
not guarantees; the evidence-binding check still covers only the
canonical-evidence fields already represented as typed
`CategoryBControllerResult` fields.

**Additionally, narrowly, from this follow-up:** every new check in this
phase is, like every other component/verdict split in this design, a
correctness/integrity control against a caller (including a future
refactor) INSIDE the trust boundary -- none of it defends against a caller
willing to import a package-internal construction path directly and
hand-craft both sides of a comparison it fully controls (e.g. calling
`classify_cleanup_failure` itself with a value other than `0`, which
remains a legitimate call for OTHER, non-Category-B callers of that shared
frozen function, and is not something this module can or should prevent).
The first-failure-attribution check proves `failed_gate` agrees with
`gate_statuses` POSITIONALLY; it does not, and cannot, prove
`gate_statuses` itself reflects any real controller run, which is what the
pre-existing per-gate vocabulary and typed-object-equality checks (FU2A/
FU2B, unchanged) are for.

# 5F3B-I2B-FU2D -- Refusal Trace + Resource-Existence Coherence (Offline Only)

> **OFFLINE ONLY. NO LIVE ACTIVITY OF ANY KIND.** No Pi/Node process, no
> socket, no model call, no credential read, no semantic prompt, no real
> workspace access. Category-B live execution remains **NO-GO**, Q1/Q2
> remain **NO-GO**, real-workspace authority remains **NO-GO**. Nothing in
> the frozen I2A/FU3 design family, H1/`get_commands` semantics, workspace
> authority, credential ordering, partial-resource ownership,
> foreign-session authority rules, the evidence-binding architecture, the
> FU2C failure-code domains, or the FU2C cleanup classification was
> reopened. `i2b_session.py`/`i2b_workspace.py` were not touched -- no
> reproduced defect required either.

FU2C's three fixes were accepted in substance. The remaining defect was one
layer up, and narrower:

> **Individually valid resource and gate objects could still describe an
> EXECUTION TRACE the real controller could never have produced.**

The suite's own `test_the_launch_facts_may_legitimately_be_true_while_not_
reached` "positive control" WAS such a trace, and was the brief's primary
counterexample. It asserted as legitimate a result with
`PI_CONFIG_GENERATION = PASSED` alongside `pi_config_created=False` and a
`NOT_REQUIRED` cleanup, and `RUNTIME_LAUNCH = FAILED:RUNTIME_SESSION_MISMATCH`
alongside `runtime_session_established=False`. Both are impossible: the
controller assigns `generated_config` exactly on that gate's success path,
and a session-mismatch refusal is reached only AFTER
`launch_observation.session` was returned and assigned. **Refusing to shut a
foreign session down is not the same fact as no session having been
returned.**

## Mandatory pre-coding counterexamples: which succeeded before the fix

All 13 negative cases reproduced against the actual pre-fix (FU2C) code
before any change was written; both positive controls were confirmed
constructible:

| # | Case | Result |
|---|---|---|
| 1 | the existing suite's own launch-facts "positive control" (the composite above) | **Constructed** |
| 2 | `pi_config_created=False` + `PI_CONFIG_GENERATION=PASSED` | **Constructed** |
| 3 | `pi_config_created=True` + `PI_CONFIG_GENERATION=NOT_REACHED` | **Constructed** |
| 4 | `runtime_session_established=False` + `runtime_teardown=CLOSED_BY_ORCHESTRATOR` | **Constructed** |
| 5 | `runtime_session_established=False` + `runtime_teardown=SHUTDOWN_REFUSED_FOREIGN_SESSION` | **Constructed** |
| 6 | `runtime_session_established=True` + `runtime_teardown=SHUTDOWN_AUTHORITY_UNAVAILABLE` | **Constructed** |
| 7 | `broker_created=False` + `broker_shutdown=CLOSED_BY_ORCHESTRATOR` | **Constructed** |
| 8 | `broker_created=False` + `broker_shutdown=SHUTDOWN_REFUSED_FOREIGN_SESSION` | **Constructed** |
| 9 | `broker_created=True` + `broker_shutdown=SHUTDOWN_AUTHORITY_UNAVAILABLE` | **Constructed** |
| 10 | `WORKSPACE_AUTHORITY=NOT_REACHED` + `ROUTE_DESCRIPTOR=FAILED` | **Constructed** |
| 11 | early compatibility failure + later `ROUTE_CHECK=PASSED` | **Constructed** |
| 12 | `GET_COMMANDS=FAILED` + `H1`/namespace reporting a verdict | **Constructed** |
| 13 | `RUNTIME_LAUNCH=FAILED` + a launch-fact gate reporting a verdict | **Constructed** |
| 14 | POSITIVE: `H1` and namespace both FAILED from one good `get_commands` | Constructed (must remain) |
| 15 | POSITIVE: launch FACTS True while their own GATES `NOT_REACHED` | Constructed (must remain) |

## Exact resource/session-existence invariants added

All derived from the controller's own terminal field expressions --
`pi_config_created = generated_config is not None`,
`broker_created = broker_session is not None`,
`runtime_session_established = runtime_session is not None` -- combined with
where each of those three locals is actually assigned. Every rule is a
biconditional, in `_require_resource_existence_coherence`:

1. **`pi_config_created == (gate_statuses['pi_config_generation'] ==
   'PASSED')`.** `generated_config` is assigned only inside that gate's own
   success path. Combined with the already-enforced FU2B
   `pi_config_created == cleanup.attempted`, this is what makes a
   config-generation PASS incompatible with a `NOT_REQUIRED` cleanup.
2. **Each existence boolean equals "the creation adapter returned a full
   session"**, which that gate's own status determines exactly: `PASSED` or
   that gate's own session-mismatch refusal, and no other status. A
   non-`None` session survives into exactly the mismatch-refusal branch or
   the success branch, because the branch immediately below the assignment
   refuses a `None` session with its own distinct code.
3. **The typed closure state must be one THAT EXACT gate status can
   produce** (`_RUNTIME_LAUNCH_STATUS_TO_CLOSURE_STATES` /
   `_BROKER_SESSION_STATUS_TO_CLOSURE_STATES`), transcribed from each
   resource's creation block and `_close_*` function together. This is
   strictly stronger than a session-bearing/non-session-bearing split, which
   it implies -- see the second-review finding below for why the weaker form
   was not enough. An import-time assertion requires each map's keys to be
   exactly `NOT_REACHED`, `PASSED`, and one entry per failure code that
   gate's FU2B vocabulary allows, so a code added to one table without the
   other cannot fall through unconstrained.

**The distinction the fix deliberately PRESERVES.** "A physical partial
resource may exist" and "a full session object crossed the boundary" are two
different facts, and only the second is what these booleans report. A
creator-retained partial broker (`resource_created=True`, `session=None`)
yields `broker_created=False` -- correctly, since no `BrokerSession` was ever
handed over -- while a FOREIGN full session yields `broker_created=True`
even though this run refused to act on it. Neither is collapsed into the
other; both directions are covered by tests, the second end-to-end through
the real controller.

## Exact gate reachability rules added

`_GATE_PREREQUISITES` transcribes, one-for-one, the `if` condition guarding
each compatibility gate's block in `run_category_b_controller` -- the
sequential pre-launch prefix, then the four-launch-fact group, the
`get_commands` group (H1 + namespace from ONE response), the `get_state`
group (H2 from ONE response), then protocol integrity and the route check.
`_require_reachable_gate_trace` walks the gates once and requires

```text
(status != NOT_REACHED)  ==  (every prerequisite is PASSED)
```

a **biconditional**, so both directions close: a gate reporting a verdict
its prerequisite never authorized is refused, and so is a gate claiming
`NOT_REACHED` when its prerequisite DID pass (the controller's launch-fact
loop sets all four gates together, so three `NOT_REACHED` beside one verdict
never happened either). `RUN_CORRELATION` has an empty prerequisite tuple --
the controller always attempts it, so `NOT_REACHED` is not a state it can
report.

Each block, once entered, records a status on every path through it
(verified branch by branch), which is what makes the biconditional sound
rather than merely an implication. An import-time assertion requires every
prerequisite to be a strictly EARLIER compatibility gate, which makes the
validator a single forward pass and rules out a cyclic table by
construction.

**This is deliberately not a generic workflow engine**, per the brief's stop
condition: one table transcribed from one function's `if` conditions, plus
one forward pass. It says nothing about WHICH status a reached gate holds --
the FU2B per-gate vocabulary and the FU2C first-failure rule already own
that. The four closure gates and `EVIDENCE_SAFETY` are deliberately absent
from the table: they are resolved on EVERY controller path, so their
coherence is proven against resource existence instead.

## Existing tests that encoded impossible traces, and how they were corrected

Nine tests failed the moment the new validators were added. Every one was
encoding a trace the controller cannot produce; none was weakened.

1. **`test_the_launch_facts_may_legitimately_be_true_while_not_reached`** --
   the brief's primary counterexample, described above. Rebuilt on the
   genuine reachable shape, and it now asserts the accepted asymmetry
   EXPLICITLY (the four launch FACTS read True while their own GATES stay
   `NOT_REACHED`) plus the resource trace that actually accompanies it
   (`runtime_session_established=True`, teardown
   `SHUTDOWN_REFUSED_FOREIGN_SESSION`, `pi_config_created=True`, cleanup
   attempted).
2. **`test_evidence_binding_applies_to_refusals_too_not_only_pass`** -- its
   comment claimed *"NOTHING was created before BROKER_READY failed"*, which
   is false for this lifecycle: frozen-O1 mints the generated config and the
   broker session BEFORE `BROKER_READY` is checked. Rebuilt on a derived
   trace; a new companion test
   (`test_fu2d_a_broker_ready_failure_reports_the_resources_that_already_exist`)
   asserts the positive half directly.
3. **`test_a_fact_claiming_true_while_its_own_gate_is_failed_is_refused`**,
   **`test_every_single_mapped_fact_is_checked_against_its_own_gate`**,
   **`test_protocol_integrity_conjunction_is_checked`**,
   **`test_the_launch_facts_are_still_checked_once_their_gate_is_reached`**,
   **`test_fu2c_counterexample_6_h1_and_namespace_both_failed_wrong_failed_gate_is_later`**
   -- all built on the old `_all_not_reached_pairs` helper, whose premise
   ("every gate `NOT_REACHED` except the ones a test names") was itself an
   impossible-trace generator. Rebuilt on `_reachable_refusal`.
4. **`test_pass_requires_pi_config_created_broker_created_runtime_session_established`**
   and
   **`test_pass_requires_runtime_teardown_and_broker_shutdown_closed_by_orchestrator`**
   -- both now trip a stricter, more specific FU2D rule before reaching the
   PASS-shape rule they named. The PASS-shape "all be True" check is
   consequently **defence in depth** rather than the first line of defence
   (the same stance FU2B already documented for the deliberately redundant
   `observed_pi_version is not None` PASS-only check); the tests accept
   either refusal and say so.

**The old helper was replaced, not patched.** `_all_not_reached_pairs` is
gone; `_reachable_compatibility_pairs` walks the SAME `_GATE_PREREQUISITES`
table the controller declares (imported, never re-declared, so the helper
cannot drift from the source), and `_closure_objects_for_trace` /
`_facts_for_trace` / `_reachable_refusal` DERIVE every remaining field from
that trace. A test overriding exactly one thing now isolates exactly that
one thing. `observed_pi_version` is derived from the resulting facts for the
same reason.

## Additional same-class bypass found in the second adversarial review

**One, fixed with a regression before completion was reported.** An
exhaustive (closure state x existence boolean) sweep over three reachable
traces found that binding the closure state only to *"was a session
returned"* was not tight enough: on a trace where `BROKER_SESSION` failed --
so the runtime launch adapter was **never called**, `launch_attempted` is
False, and `_close_runtime` can only return `NOT_REQUIRED` -- the
creator-retained (`CLOSED_BY_CREATOR_VERIFIED`/`UNVERIFIED`,
`PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`) and
`SHUTDOWN_AUTHORITY_UNAVAILABLE` runtime states all still constructed. Fixed
by replacing the coarse session-bearing split with the per-status
closure-state maps described above. Regression:
`test_fu2d_second_review_bypass_creator_states_need_the_adapter_to_have_been_called`.

**And one over-refusal in this phase's own first draft of that map**, caught
immediately by the real-controller trace sweep rather than by reasoning:
`_creator_retained_ownership_state` returns `NOT_REQUIRED` whenever the
creator reports `resource_created=False`, so a `RUNTIME_LAUNCH_FAILED` trace
legitimately admits FOUR closure states, not three. Regression:
`test_fu2d_not_required_is_reachable_from_a_launch_that_created_nothing`.

The remaining second-review items produced no finding: individually-valid
resource states whose existence booleans disagree (closed by invariants 2/3),
foreign full sessions vs creator-retained partial resources (both directions
tested, one end-to-end), gates reached after an earlier stage made them
unreachable (closed by the trace validator), the two intentional multi-fact
observation groups (positive controls, both still representable), and
`dataclasses.replace` on genuine controller refusals (swept).

## New regression tests

**56 new tests** in `tests/test_i2b_controller.py`, under a new `# FU2D --
refusal-trace + resource-existence coherence closure` section, plus the nine
corrections above. Highlights:

- the 13 negative counterexamples, each isolated to the one rule it names;
- both positive controls stated explicitly
  (`test_fu2d_counterexample_14_h1_and_namespace_may_both_fail_from_one_observation`,
  `test_fu2d_one_launch_fact_may_fail_while_its_three_siblings_pass`);
- `test_fu2d_a_foreign_session_is_still_a_returned_session` and
  `test_fu2d_a_creator_retained_partial_resource_is_not_a_returned_session`
  (the latter driving the REAL controller), pinning both halves of the
  distinction the brief insists on;
- `test_fu2d_a_reached_prerequisite_makes_not_reached_impossible_too` and
  `test_fu2d_run_correlation_may_never_be_not_reached`, closing the second
  direction of the biconditional;
- structural tests that the prerequisite table and both status->state maps
  match their sources
  (`test_fu2d_the_prerequisite_table_matches_the_controllers_own_stage_order`,
  `test_fu2d_status_to_closure_state_maps_cover_their_whole_vocabulary`);
- **`test_fu2d_every_real_controller_trace_is_accepted_by_the_new_validators`**,
  the decisive check that these rules are DERIVED and not merely plausible:
  **29 distinct real controller runs** -- every creation, observation,
  identity and teardown failure mode the offline harness can drive, plus the
  full pass -- each constructing its result cleanly. A rule that over-refuses
  shows up here immediately, and one did (above).

## Offline suite result

```text
914 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(514 unchanged I1/I2 through FU3B; 400 in `test_i2b_controller.py`, up from
FU2C's 344 -- 56 new tests, 9 corrected, for this follow-up.)

Frozen suites re-run unmodified:

```text
experiments/pi_external_runtime_ar1/tests         96 passed, 0 failed
experiments/pi_external_runtime_ar2/tests        290 passed, 0 failed
experiments/pi_external_runtime_ar2_o1/tests      89 passed, 0 failed
tests/  (the production suite)                  3504 passed, 0 failed
```

No file under `ar1/`, `ar2/`, `o1/`, `src/`, root `tests/` or `projects/` was
touched. `i2b_session.py`, `i2b_workspace.py` and `i2_cleanup.py` were not
modified.

## Corrected claims

**FU2C's closing verdict of "READY FOR INDEPENDENT REVIEW" was premature**,
and is corrected here. FU2C closed which failure code a resource/gate may
carry and which gate may be nominated as `failed_gate`, but its own
regression suite still contained a "positive control" asserting an
unreachable execution trace as legitimate -- so the suite was, in that one
place, defending the wrong thing. README.md's I2B status block is corrected
in place with a pointer to this section.

## What this does NOT establish

Unchanged from FU2/FU2A/FU2B/FU2C, and true as of this phase's acceptance:
no zero-prompt live gate had run (one has since occurred -- see the
TOP-LEVEL CORRECTION at the head of this document);
`get_commands` still proves nothing about the active tool registry; the
adapter trust boundary is unchanged; the synthetic workspace authority is not
real-workspace authority; no claim about descendants, inference, or GPU work;
redaction/scrubbing remain backstops, not guarantees; the evidence-binding
check still covers only the canonical-evidence fields represented as typed
result fields.

**Additionally, narrowly, from this follow-up:** these validators prove that
an accepted result describes a trace the controller COULD have produced --
not that it describes a trace that DID occur. They are a coherence control
against a caller or a future refactor inside the trust boundary, not
provenance: nothing here (and nothing that could reasonably be added here)
distinguishes a hand-built result that happens to be perfectly coherent from
one a real run emitted. The rules are also transcriptions of the CURRENT
controller's control flow; a future change to `run_category_b_controller`'s
stage conditions must update `_GATE_PREREQUISITES` and both status->state
maps in the same commit, and the 29-trace real-controller test is what would
catch a divergence.

# 5F3B-I2B-FU2E -- Observation-Fact Availability + Terminal Evidence State Closure (Offline Only)

> **OFFLINE ONLY. NO LIVE ACTIVITY OF ANY KIND.** No Pi/Node process, no
> socket, no model call, no credential read, no semantic prompt, no real
> workspace access. Category-B live execution remains **NO-GO**, Q1/Q2
> remain **NO-GO**, real-workspace authority remains **NO-GO**. Nothing in
> the frozen I2A/FU3 design family, gate reachability/prerequisite coherence,
> resource/session-existence coherence, the FU2B/FU2C status->closure-state
> maps, the foreign-session/creator-retained-partial-resource distinction,
> first-failure attribution, the FU2B/FU2C resource/state failure-code
> domains, workspace authority, credential ordering, H1/`get_commands`
> observability design, partial-cleanup ownership, or the evidence-scrub
> architecture was reopened. `i2b_session.py`/`i2b_workspace.py` were not
> touched -- no reproduced blocker required either.

FU2D's own "READY FOR FINAL FREEZE REVIEW" verdict was premature. FU2D
proved a gate TRACE is reachable exactly when the controller's own `if`
conditions would have reached it -- but a trace being reachable says nothing
about whether the `CompatibilityFacts` recorded alongside it are honest. The
gap was narrower and one layer up:

> **A gate trace can be reachable while `CompatibilityFacts` still claims an
> observation the controller never performed.**

Two independent forms of the same gap, plus one adjacent terminal-state gap:

1. **Blocker 1.** The fact-vs-gate loop's `NOT_REACHED` exception
   (`if gate_status == _STATUS_NOT_REACHED: continue`) applied uniformly to
   all eleven single-mapped facts. It is correct ONLY for the four LAUNCH
   facts; for the other seven, the fact and its own gate's `_pass`/`_fail`
   are set together, unconditionally, in the SAME block on every path
   through it -- "gate reached", "observation available" and "fact observed"
   are the same fact for them, so `NOT_REACHED` should have pinned the fact
   `False`, not left it unchecked.
2. **Blocker 2.** The four launch facts genuinely ARE the one place those
   three notions diverge, but the exception needed to be bound to
   `RUNTIME_LAUNCH`'s own status -- specifically to whether a valid
   `RuntimeLaunchObservation` was actually consumed -- not to "this fact's
   own gate is `NOT_REACHED`" taken as a free pass on its own.
3. **Blocker 3.** The `PROTOCOL_INTEGRITY` conjunction check
   (`(no_pv and no_ee) == protocol_gate_passed`) proved only that the two
   facts agreed with pass/fail, never *which* failure interpretation of the
   SAME observation they were consistent with -- it could not tell
   `FAILED:PROTOCOL_VIOLATION_OBSERVED` apart from
   `FAILED:EXTENSION_ERROR_OBSERVED`, each of which pins a DIFFERENT exact
   pair of fact values in the real controller.
4. **Terminal evidence state.** `CategoryBEvidence()`'s bare, no-argument
   constructor produces a safe INTERMEDIATE placeholder
   (`scrub_findings == ("evidence_not_yet_built",)`) -- legitimate to
   construct in isolation, but never a shape `run_category_b_controller`
   itself returns (every real path calls either `_refused` or
   `_build_from_payload`). Nothing previously refused a terminal
   `CategoryBControllerResult` carrying it.

## Mandatory pre-coding counterexamples: which succeeded before the fix

All 14 reproduced against a scratch, line-for-line reconstruction of the
pre-fix (FU2D-accepted) module, built by mechanically reverse-applying this
phase's own three edits to a throwaway sibling module
(`qualification/_i2b_controller_prefu2e.py`, deleted before this phase's
tests were finalized -- it is not part of the shipped package) and importing
it side-by-side with the real, fixed `qualification.i2b_controller`. Every
negative case constructed cleanly pre-fix and is refused post-fix; both
positive controls construct on BOTH:

| # | Case | Pre-fix | Post-fix |
|---|---|---|---|
| 1 | `RUN_CORRELATION` fails, `get_commands_response_shape_understood=True` | **Constructed** | Refused |
| 2 | same, `h1_extension_identity_matched=True` | **Constructed** | Refused |
| 3 | same, `exact_candidate_model_served=True` | **Constructed** | Refused |
| 4 | `BROKER_SESSION` fails / `BROKER_READY` `NOT_REACHED`, `broker_reached_required_ready_state=True` | **Constructed** | Refused |
| 5 | `GET_STATE` `NOT_REACHED`, `get_state_response_shape_understood=True` + `h2_provider_model_identity_matched=True` | **Constructed** | Refused |
| 6 | `PROTOCOL_INTEGRITY` `NOT_REACHED`, either protocol fact `True` | **Constructed** | Refused |
| 7 | `RUNTIME_LAUNCH` `NOT_REACHED`, all four launch facts `True` | **Constructed** | Refused |
| 8 | `RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE`, launch facts `True` | **Constructed** | Refused |
| 9 | `RUNTIME_LAUNCH` `ADAPTER_RAISED`, launch facts `True` | **Constructed*** | Refused (same underlying reason on both, see note) |
| 10 | POSITIVE: `RUNTIME_LAUNCH_FAILED` from a VALID observation, `session=None`, launch facts `True` | **Constructed (must remain)** | Constructed (must remain) |
| 11 | POSITIVE: `RUNTIME_SESSION_MISMATCH`, launch facts `True` | **Constructed (must remain)** | Constructed (must remain) |
| 12 | `FAILED:PROTOCOL_VIOLATION_OBSERVED` with `no_protocol_violation_observed=True`, `no_extension_error_observed=False` | **Constructed** | Refused |
| 13 | `FAILED:EXTENSION_ERROR_OBSERVED` with `no_protocol_violation_observed=False`, `no_extension_error_observed=True` | **Constructed** | Refused |
| 14 | terminal refusal carrying bare `CategoryBEvidence()` (`evidence_not_yet_built`) | **Constructed** | Refused |

`MALFORMED_ADAPTER_RESULT` (the `RUNTIME_LAUNCH` sibling of case 9) was swept
the same way with the same result. \* Case 9's scratch-diagnostic script used
a simplified closure-object builder that does not special-case every
failure code the way the real test suite's `_reachable_refusal` does, so it
was ALREADY refused pre-fix by the unrelated, already-accepted FU2D
resource-existence check (`ADAPTER_RAISED`/`MALFORMED_ADAPTER_RESULT` require
a `SHUTDOWN_AUTHORITY_UNAVAILABLE` runtime-teardown state, not the default
`NOT_REQUIRED`) -- not by anything this phase touches. The permanent
regression test for this case (below) supplies the correct
`SHUTDOWN_AUTHORITY_UNAVAILABLE` teardown explicitly so it isolates the
FU2E rule rather than riding on that earlier, unrelated check.

## Exact observation-availability rule added (blocker 1)

The old single loop over `_SINGLE_FACT_TO_GATE` is now:

```text
for each single-mapped fact:
    if its own gate status != NOT_REACHED:
        fact must equal (gate status == PASSED)      # unchanged from FU2D
    elif the fact is one of the four LAUNCH facts:
        see the launch-fact exception below
    else:
        fact must be False                            # NEW
```

For the seven non-launch single-mapped facts
(`get_commands_response_shape_understood`, `h1_extension_identity_matched`,
`no_unexpected_extension_command_observed`, `get_state_response_shape_understood`,
`h2_provider_model_identity_matched`, `exact_candidate_model_served`,
`broker_reached_required_ready_state`), `NOT_REACHED` on their own gate now
means the producing observation was never made, so the fact must be at its
`False` default -- confirmed field-by-field against each fact's own
assignment site in `run_category_b_controller` (e.g.
`fact_values["get_commands_response_shape_understood"] = True` sits in the
SAME `else` block as `_pass(GET_COMMANDS)`, on every path through the
`if _all_passed(<four launch gates>): ...` block).

## Exact launch-fact exception (blocker 2)

Read directly off the real controller's `RUNTIME_LAUNCH` block: all four
`fact_values[...]` assignments happen immediately after `_invoke(launch_runtime,
...)` returns a non-`None` `RuntimeLaunchObservation`, strictly BEFORE the
`runtime_session is None` / session-mismatch checks that can still fail
`RUNTIME_LAUNCH` itself. So the exception is now keyed off `RUNTIME_LAUNCH`'s
own recorded status, not off the fact's own (always-`NOT_REACHED`-in-this-
branch) gate:

```text
RUNTIME_LAUNCH status                                  four launch facts
---------------------------------------------------     ------------------
NOT_REACHED                                              must be False
FAILED:RUNTIME_LAUNCH_REQUEST_UNCONSTRUCTIBLE            must be False
FAILED:ADAPTER_RAISED                                    must be False
FAILED:MALFORMED_ADAPTER_RESULT                          must be False
FAILED:RUNTIME_LAUNCH_FAILED     (session=None)           may be True or False (each independently)
FAILED:RUNTIME_SESSION_MISMATCH  (foreign session)         may be True or False (each independently)
PASSED                                                    own gates ARE reached; falls through to the
                                                           ordinary per-own-gate check above
```

`PASSED` is deliberately absent from the "valid observation but own gate
unreached" set: when `RUNTIME_LAUNCH` passes, the four launch-fact gates are
themselves reached (their sole prerequisite IS `RUNTIME_LAUNCH`, enforced by
FU2D's own `_GATE_PREREQUISITES`/`_require_reachable_gate_trace`), so they
never need the exception at all. The existing accepted positive control for
`RUNTIME_SESSION_MISMATCH` (`test_the_launch_facts_may_legitimately_be_true_
while_not_reached`) was preserved verbatim -- not weakened -- and a new,
symmetric positive control for `RUNTIME_LAUNCH_FAILED`
(`test_fu2e_blocker2_positive_control_runtime_launch_failed_with_valid_no_
session_observation`) was added, proving the exception holds on BOTH of its
two reachable statuses, not just the one the suite happened to already cover.

## Exact protocol failure-code/fact mapping (blocker 3)

Read directly off the real controller's `PROTOCOL_INTEGRITY` block: both
`fact_values["no_protocol_violation_observed"]`/`["no_extension_error_
observed"]` are set from the raw observation booleans BEFORE the `if`/`elif`
that classifies the failure, so `PROTOCOL_VIOLATION_OBSERVED` (checked FIRST)
has precedence when both were observed:

```text
protocol_integrity status              no_protocol_violation_observed   no_extension_error_observed
--------------------------------------  --------------------------------  -----------------------------
PASSED                                  True                              True
FAILED:PROTOCOL_VIOLATION_OBSERVED      False                             either (violation has precedence)
FAILED:EXTENSION_ERROR_OBSERVED         True                              False
FAILED:RUNTIME_SESSION_MISMATCH         False                             False   (no valid observation consumed)
FAILED:ADAPTER_RAISED                   False                             False   (no valid observation consumed)
FAILED:MALFORMED_ADAPTER_RESULT         False                             False   (no valid observation consumed)
NOT_REACHED                             False                             False
```

The three "no valid observation consumed" rows share one code path in the
new validator (a single `else` bucket after the `PASSED`/
`PROTOCOL_VIOLATION_OBSERVED`/`EXTENSION_ERROR_OBSERVED` branches): both
facts are only ever populated inside the real controller's own `else` branch
that follows a matched `runtime_session_id`, so every failure reached BEFORE
that point -- a session mismatch or an adapter fault -- leaves both at their
`False` default, exactly like `NOT_REACHED`.

## Terminal evidence-state rule

One module-level constant,
`_EVIDENCE_NOT_YET_BUILT_SENTINEL = CategoryBEvidence().scrub_findings`
(derived from a fresh default instance rather than a duplicated literal, so
it can never drift from the dataclass field default it names), and one new
check in `CategoryBControllerResult.__post_init__`:

```python
if not self.evidence.retention_ready and self.evidence.scrub_findings == _EVIDENCE_NOT_YET_BUILT_SENTINEL:
    raise ValueError(...)
```

Deliberately narrow, per the brief's own stop condition: no second scrub-
finding taxonomy, no change to what `_refused`/`_build_from_payload` accept,
no change to `CategoryBEvidence`'s own invariants (a bare `CategoryBEvidence()`
remains constructible in isolation -- it is a legitimate, safe intermediate
value; only a TERMINAL `CategoryBControllerResult` carrying it is refused).

## Same-class bypasses found during the second adversarial review

The mandated sweep (every `CompatibilityFacts` field against its own gate
PASSED/FAILED/NOT_REACHED, whether the producing adapter was actually
called, and whether a valid observation was actually accepted) surfaced no
NEW bypass beyond the three blockers and the terminal-evidence gap already
closed. Specifically checked and found already correctly handled by the
fix's own structure (a single `else`/generic branch covering each), without
requiring a fourth blocker:

- `GET_COMMANDS`/`GET_STATE`/`PROTOCOL_INTEGRITY` can each independently fail
  with `RUNTIME_SESSION_MISMATCH` (a session-id mismatch on THAT call, not on
  `RUNTIME_LAUNCH`). For `GET_COMMANDS`/`GET_STATE`, the relevant fact is
  never populated on that branch (it sits in the `else` clause the mismatch
  check precedes), so the fact's own gate is FAILED, not NOT_REACHED, and the
  ORDINARY per-own-gate equality check (unchanged from FU2D) already binds it
  correctly -- no blocker-1 exception applies here at all. For
  `PROTOCOL_INTEGRITY`, this is exactly the same "no valid observation
  consumed" bucket blocker 3 already closes, and is now covered by a
  dedicated regression
  (`test_fu2e_blocker3_session_mismatch_pins_both_protocol_facts_false`).
- Downstream facts of a session-mismatched `GET_COMMANDS`/`GET_STATE`
  (`H1`/namespace/`H2`) correctly stay `NOT_REACHED` (their prerequisite gate
  did not pass), which is the ordinary blocker-1 non-launch case -- already
  covered generically by the sweep (the exact upstream cause of `NOT_REACHED`
  is irrelevant to the rule, only the status is).
- The four launch facts remain genuinely INDEPENDENT even inside the one
  "valid observation, own gate unreached" exception (e.g.
  `pi_version_observed=True` while `rpc_launch_shape_valid=False`, both on a
  `RUNTIME_LAUNCH_FAILED` trace) -- unchanged and still representable, matching
  I2A Sec. 15's "four independent facts from one observation" design.
- A retention-ready evidence body (`scrub_clean=True`) can never carry the
  sentinel tuple in the first place -- `CategoryBEvidence`'s own existing
  invariant (`scrub_clean == (not scrub_findings)`) already forces
  `scrub_findings == ()` whenever `retention_ready` is `True`, so the new
  terminal check's `not self.evidence.retention_ready` guard cannot be
  bypassed by a "clean but sentinel-carrying" evidence object -- there is no
  such reachable object.

## New/corrected tests

**28 new tests**, all under a new `# 5F3B-I2B-FU2E` section in
`tests/test_i2b_controller.py`; zero existing tests were weakened or
deleted, and the pre-existing 400/914 both remain green unmodified:

- **Blocker 1**: a parametrized sweep over all seven non-launch
  single-mapped facts
  (`test_fu2e_blocker1_a_non_launch_fact_may_not_float_true_while_never_
  reached`), plus a structural test that the sweep covers the whole set with
  no silent hand-picked subset
  (`test_fu2e_blocker1_every_non_launch_single_mapped_fact_is_swept`).
- **Blocker 2**: a parametrized sweep over the four no-valid-observation
  `RUNTIME_LAUNCH` statuses (mandatory counterexamples 4/7/8/9,
  `test_fu2e_blocker2_launch_facts_may_not_float_true_without_a_valid_
  observation`), plus the new `RUNTIME_LAUNCH_FAILED` positive control
  (counterexample 10) described above.
- **Blocker 3**: `NOT_REACHED` (counterexample 6) and
  `RUNTIME_SESSION_MISMATCH` both pinning both facts False; counterexamples
  12 and 13 exactly; a positive control proving `PROTOCOL_VIOLATION_OBSERVED`
  precedence leaves the OTHER fact free
  (`test_fu2e_blocker3_protocol_violation_precedence_leaves_the_other_fact_
  free`); and the unchanged `PASSED`-requires-both-True case re-expressed
  under the new branch structure.
- **Terminal evidence**: counterexample 14 directly on
  `CategoryBControllerResult`; an end-to-end proof that a genuine controller
  refusal's evidence is never the sentinel
  (`test_fu2e_a_real_refusal_still_carries_a_real_evidence_body_never_the_
  sentinel`); and a `dataclasses.replace` mutation of a genuine PASS onto the
  bare sentinel, refused.
- **Not-over-refused, end to end**: a parametrized sweep of six REAL
  controller refusal traces through the actual harness/`_run` path
  (`broker_ready=False`, `launch_returns_no_session=True`, a launch
  session-id mismatch, `protocol_violation=True`, `extension_error=True`,
  `pi_version=None`) -- the decisive proof that the tighter rules do not
  over-refuse a genuine run, exactly mirroring FU2D's own 29-trace
  real-controller test for this phase's own two blockers.

## Offline suite result

```text
942 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(514 unchanged I1/I2 through FU3B; 428 in `test_i2b_controller.py`, up from
FU2D's 400 -- 28 new tests, 0 corrected, for this follow-up.)

Frozen suites re-run unmodified:

```text
experiments/pi_external_runtime_ar1/tests         96 passed, 0 failed
experiments/pi_external_runtime_ar2/tests        290 passed, 0 failed
experiments/pi_external_runtime_ar2_o1/tests      89 passed, 0 failed
```

No file under `ar1/`, `ar2/`, `o1/`, `src/`, root `tests/` or `projects/` was
touched. `i2b_session.py`, `i2b_workspace.py`, `i2_cleanup.py` and every
other reused I2 module were not modified.

## No-live/no-network/no-model/no-credential confirmation

Unchanged from every prior FU2* closure: this follow-up touches only
`qualification/i2b_controller.py`'s terminal-result validator and
`tests/test_i2b_controller.py`. No new import of `subprocess`/`socket`/
`http`/`urllib`/`os.environ` was added (the module's own source-level
regression test enforces this mechanically and still passes); no test opens
a socket, launches a process, or reads an environment variable for a
credential; the scratch pre-fix reconstruction used to verify the mandatory
counterexamples was a diagnostic-only, throwaway Python module (never
imported by the shipped package or by any test) and was deleted before this
phase's own tests were finalized. Category-B live execution, Q1/Q2, and
real-workspace authority all remain **NO-GO**.

## Corrected claims

**FU2D's closing verdict of "READY FOR FINAL FREEZE REVIEW" was premature**,
and is corrected here. FU2D closed whether a gate TRACE is reachable, but its
own regression suite still let a reachable trace carry a `CompatibilityFacts`
field the controller's own source could never have set to `True` on that
trace (seven non-launch facts) or an execution-consistent but wrong pair of
values (the two protocol facts) -- so the suite was, in those places,
defending trace shape without defending the facts riding on it. README.md's
I2B status block is corrected in place with a pointer to this section.

## What this does NOT establish

Unchanged from FU2/FU2A/FU2B/FU2C/FU2D: no zero-prompt live gate has ever
run; `get_commands` still proves nothing about the active tool registry; the
adapter trust boundary is unchanged; the synthetic workspace authority is not
real-workspace authority; no claim about descendants, inference, or GPU work;
redaction/scrubbing remain backstops, not guarantees; the evidence-binding
check still covers only the canonical-evidence fields represented as typed
result fields; and, as FU2D itself already stated, these validators prove a
result describes a trace the controller COULD have produced, never that it
describes a trace that DID occur.

**Additionally, narrowly, from this follow-up:** the observation-availability
rules and the protocol failure-code mapping are, like FU2D's own rules,
transcriptions of the CURRENT controller's control flow at the exact call
sites named above. A future change to where `run_category_b_controller`
assigns `fact_values[...]` (particularly inside the `RUNTIME_LAUNCH` or
`PROTOCOL_INTEGRITY` blocks) must update `_LAUNCH_FACT_NAMES`/
`_RUNTIME_LAUNCH_STATUSES_WITH_VALID_OBSERVATION_BUT_OWN_GATE_UNREACHED`/the
protocol branch in the same commit, and the real-controller-trace regression
sweep is what would catch a divergence.

# 5F3B-I2B-FU2F -- Evidence-Safety Failure Attribution Closure (Offline Only)

> **OFFLINE ONLY. NO LIVE ACTIVITY OF ANY KIND.** No Pi/Node process, no
> socket, no model call, no credential read, no semantic prompt, no real
> workspace access. Category-B live execution remains **NO-GO**, Q1/Q2
> remain **NO-GO**, real-workspace authority remains **NO-GO**. Nothing in
> the frozen I2A/FU3 design family, non-launch `NOT_REACHED` fact
> availability, the exact `RuntimeLaunchObservation` exception, the protocol
> failure-code/fact mapping, or the terminal `evidence_not_yet_built`
> exclusion (all FU2E-accepted) was reopened. `i2b_session.py`/
> `i2b_workspace.py` were not touched -- no reproduced blocker required
> either.

FU2E's own "READY FOR FINAL INDEPENDENT FREEZE REVIEW" verdict was
premature, for exactly one narrow residual named by independent review:

> **`EVIDENCE_SAFETY` failure_code is not mechanically bound to the evidence
> refusal state that actually produced it.**

The CURRENT test suite itself still accepted:

```text
gate_statuses[EVIDENCE_SAFETY] = FAILED:EVIDENCE_SCRUB_REFUSED
failed_gate                    = EVIDENCE_SAFETY
failure_code                   = EVIDENCE_SCRUB_REFUSED
evidence                       = CategoryBEvidence._refused(
                                      ("safety_context_unprovable",)
                                  )
```

-- not a trace `run_category_b_controller` can produce. The real controller
has exactly TWO reachable evidence-refusal paths, and they are mutually
exclusive: (A) `safety is None` -> `evidence = CategoryBEvidence._refused(...)`
-> `EVIDENCE_SAFETY = FAILED:SAFETY_CONTEXT_UNPROVABLE`; (B) safety exists but
the canonical payload fails the real scrub -> `evidence =
CategoryBEvidence._build_from_payload(...)` -> `evidence.retention_ready =
False` -> `EVIDENCE_SAFETY = FAILED:EVIDENCE_SCRUB_REFUSED`. The old check
bound `EVIDENCE_SAFETY`'s code only to `evidence.retention_ready` (a single
boolean, shared by BOTH paths) and a flat three-code allowed set, so it could
not tell which path actually ran.

## Exact evidence-origin binding chosen

Of the three directions the brief offered, this phase chose **a narrow
internal evidence-origin marker set only by the two builder classmethods**:

- `CategoryBEvidence` gained one new `init=False` field, `_origin: str`,
  defaulting to `"unbuilt"` (the bare constructor's untouched value).
  `_refused` stamps `"refused"`; `_build_from_payload` stamps `"built"` --
  each inside the SAME classmethod that already derives every other field,
  never accepted as a constructor argument, and validated in
  `_check_invariants` against the exact three-member set `_EVIDENCE_ORIGINS`.
- `CategoryBControllerResult.__post_init__`'s `EVIDENCE_SAFETY` block now
  branches on `evidence._origin` (not `evidence.retention_ready` alone):
  `retention_ready=True` still requires `PASSED`; `_origin == "refused"`
  requires EXACTLY `FAILED:SAFETY_CONTEXT_UNPROVABLE` **and**
  `evidence.scrub_findings == _SAFETY_CONTEXT_UNPROVABLE_REFUSAL` (the one
  finding-code shape the real `_refused` call site ever passes -- a new
  module constant, reused at BOTH that real call site and the validator, so
  they cannot drift apart); `_origin == "built"` requires EXACTLY
  `FAILED:EVIDENCE_SCRUB_REFUSED`; `_origin == "unbuilt"` is left
  UNCONSTRAINED at this checkpoint -- FU2E's own, unchanged terminal
  `evidence_not_yet_built` sentinel check is what refuses it, regardless of
  what `gate_statuses['evidence_safety']` text accompanies it.

**Deliberately not a finding-code taxonomy.** `_origin` records WHICH
classmethod ran, never WHAT the scrub layer found -- the brief's own
"do not create an exhaustive second taxonomy" instruction is honored by
tracking exactly two builder identities plus the untouched default, nothing
about scrub-finding content. `_EVIDENCE_SAFETY_ALLOWED_FAILURE_CODE_VALUES`
(the old flat three-code set) was removed entirely rather than kept
alongside the new binding -- it is now provably redundant, and a document
comment at its former location explains why (see the `MALFORMED_ADAPTER_RESULT`
section below).

## Treatment of EVIDENCE_SAFETY MALFORMED_ADAPTER_RESULT

Inspected, not guessed. `run_category_b_controller` has a THIRD
`_fail(EVIDENCE_SAFETY, MALFORMED_ADAPTER_RESULT)` call site, guarding
`outcome is INFRASTRUCTURE_REFUSAL and failed_gate is None`. Traced against
the controller's own invariants:

- `EVIDENCE_SAFETY` is unconditionally resolved -- to `PASSED`, or via one of
  the two real `_fail` calls immediately above -- on EVERY path through the
  safety/evidence block, before the defensive guard's line ever runs;
- `provisional_pass = compatibility_established and closure_established`
  being `False` always traces back to a genuine, earlier `_fail` call:
  `compatibility_established=False` requires some compatibility gate not
  `PASSED`, and by induction along `_GATE_PREREQUISITES` (base case
  `RUN_CORRELATION`, which is ALWAYS resolved via its own bounded try/except
  -- never `NOT_REACHED`) that chain bottoms out at a genuinely FAILED gate,
  never at a `NOT_REACHED` one with no `_fail` behind it;
  `closure_established=False` means the closure loop already `_fail`-ed
  `RUNTIME_TEARDOWN`/`BROKER_SHUTDOWN`/`GENERATED_CONFIG_CLEANUP`
  unconditionally for the unsatisfied one(s);
- therefore `failed_gate` can never still be `None` when the guard's
  condition is evaluated. **The branch is PROVABLY UNREACHABLE** under the
  controller's own current invariants.

Per the brief's own instruction for the unreachable case: `MALFORMED_ADAPTER_
RESULT` is now **removed from `EVIDENCE_SAFETY`'s accepted terminal
vocabulary** -- neither `_origin` branch above accepts it, so a hand-built
`CategoryBControllerResult` claiming it is refused
(`test_fu2f_malformed_adapter_result_is_no_longer_an_accepted_evidence_
safety_code`). The dead defensive `_fail(...)` call site itself is KEPT in
the controller (a legitimate belt-and-suspenders invariant guard, not a
reachable branch) with an updated comment stating the unreachability
argument and the new consequence explicitly: if a future regression ever
does reach it, the `CategoryBControllerResult` constructed immediately after
will now itself raise -- loudly, at construction -- rather than silently
accepting a code the current source can never actually produce.
`MALFORMED_ADAPTER_RESULT` remains untouched and fully valid for every OTHER
gate that already used it (`RUNTIME_LAUNCH`/`BROKER_SESSION`/`GET_COMMANDS`/
`GET_STATE`/`PROTOCOL_INTEGRITY`) -- this is a per-gate vocabulary removal,
never a change to the shared `CategoryBFailureCode` enum or to any other
gate's own table.

## Mandatory pre-coding counterexamples

Reproduced against the REAL pre-fix predicate (the exact
`evidence.retention_ready`-only logic, extracted verbatim as it read
immediately before this phase's edit -- not a guess, not a reconstructed
whole module) alongside the real, current post-fix module, using the exact
real evidence shapes (`_refused(("safety_context_unprovable",))`, and a
genuinely dirty `_build_from_payload` body built the same way
`test_retention_ready_true_is_only_reachable_by_actually_scrubbing_the_
payload` already does -- `ArtifactSafetyContext(api_key="sk-should-be-
caught")` plus that literal in the payload, never a monkeypatch for this
part):

| # | Case | Pre-fix | Post-fix |
|---|---|---|---|
| 1 | `EVIDENCE_SCRUB_REFUSED` + `_refused(("safety_context_unprovable",))` | **Constructed** | Refused |
| 2 | `SAFETY_CONTEXT_UNPROVABLE` + a real dirty `_build_from_payload(...)` body | **Constructed** (the SYMMETRIC, previously-undetected twin of #1) | Refused |
| 3 | `EVIDENCE_SCRUB_REFUSED` + bare `CategoryBEvidence()` | Constructed | **Still refused** (by FU2E's unchanged sentinel check, unaffected by this phase) |
| 4 | POSITIVE: real controller safety-context-unprovable path, end to end | Constructed (must remain) | Constructed (must remain), now also carrying `_origin == "refused"` |
| 5 | POSITIVE: real controller scrub-refusal path (`qualification_scrub_check` forced dirty via a safe synthetic finding, `"synthetic_finding"`, never a real secret/endpoint), end to end | Constructed (must remain) | Constructed (must remain), now also carrying `_origin == "built"` |

Counterexample 2 answers the brief's own open question ("Determine whether
it currently constructs") directly: **yes** -- the old `retention_ready`-only
check accepted BOTH the reproduced counterexample and its unnamed symmetric
twin, and this phase closes both on the same footing.

## Corrected existing test

**`test_fu2c_evidence_safety_alone_failing_may_be_failed_gate`.** Its intent
(EVIDENCE_SAFETY may legitimately be the sole/first failed gate) was never in
question and is UNCHANGED -- the assertion `result.failed_gate is
CategoryBGateName.EVIDENCE_SAFETY` still holds. Its evidence object was
wrong for the failure code under test: it paired `EVIDENCE_SCRUB_REFUSED`
with `CategoryBEvidence._refused(("safety_context_unprovable",))`, exactly
this phase's own reproduced counterexample. It now builds a GENUINE scrub
refusal via the real `_build_from_payload` -> `qualification_scrub_check`
path (the same technique
`test_retention_ready_true_is_only_reachable_by_actually_scrubbing_the_
payload` already established), asserting `evidence.retention_ready is False`
and `evidence._origin == _EVIDENCE_ORIGIN_BUILT` before use. No other
existing test required correction; the full pre-existing 439/953 both remain
green.

Two other existing call sites needed a SMALL, mechanical follow-on change,
not a correction of a wrong assertion: `_reachable_refusal`'s helper (used by
dozens of other, unrelated tests) previously derived `EVIDENCE_SAFETY`'s
status from `evidence.retention_ready` alone; it now derives it from
`evidence._origin` too, so a future test supplying a genuine BUILT-but-dirty
body (not just the helper's default REFUSED one) is not tripped by this
phase's own new binding instead of the check it is exercising. Its default
behavior (a `_refused(...)`-built evidence, mapping to
`SAFETY_CONTEXT_UNPROVABLE`) is byte-for-byte unchanged.

## Second-adversarial-review result

The mandated sweep (`evidence.retention_ready`, evidence construction
origin, `evidence.scrub_findings`, `EVIDENCE_SAFETY` status, `failed_gate`/
`failure_code` against each other) was run as an EXHAUSTIVE cross-swap: every
individually-valid non-retention-ready evidence shape
(`_refused(...)`-origin, real dirty `_build_from_payload`-origin, bare
`CategoryBEvidence()`) against every one of the four EVIDENCE_SAFETY status
texts the old vocabulary allowed (`PASSED`,
`FAILED:SAFETY_CONTEXT_UNPROVABLE`, `FAILED:EVIDENCE_SCRUB_REFUSED`,
`FAILED:MALFORMED_ADAPTER_RESULT`) -- 12 pairings total. Exactly the two
reachable pairings construct; the other ten are refused. (The retention-ready
`PASSED` shape is swept separately, end to end, through the real controller
-- see counterexamples 4/5 above and `test_fu2d_a_genuine_pass_still_
constructs` -- rather than hand-built into this matrix, because a genuinely
retention-ready evidence body must ALSO describe the exact result consuming
it (`_require_evidence_describes_this_result`, FU2B, unrelated to and
unchanged by this phase); a hand-built `PASSED` case in the matrix would trip
THAT binding instead of the one under test.)

No bypass beyond the two named blockers (the reproduced counterexample and
its symmetric twin) and the `MALFORMED_ADAPTER_RESULT` unreachability finding
was found. `dataclasses.replace` on a genuine controller REFUSAL (swapping
its evidence for either wrong-origin real shape) and on a genuine controller
PASS (swapping its retention-ready evidence for either non-retention-ready
real shape) were both re-run and both refuse in every direction.

## New regression tests

**11 new tests** in `tests/test_i2b_controller.py`, under a new
`# 5F3B-I2B-FU2F` section:

- the reproduced counterexample and its symmetric twin, each isolated to the
  one origin/code pairing it names;
- counterexample 3 (bare evidence remains refused, via FU2E's own unchanged
  check);
- counterexamples 4 and 5, end to end through the real controller, each now
  additionally asserting the correct `_origin`;
- the `MALFORMED_ADAPTER_RESULT` unreachability closure, plus a scope check
  that the code remains valid for every OTHER gate that already used it;
- the exhaustive cross-swap sweep;
- two `dataclasses.replace` sweeps (a genuine refusal's evidence swapped to
  each wrong origin; a genuine pass's evidence swapped to each non-retention-
  ready origin -- split into two test functions after the first combined
  draft reused one `run_workspace` fixture instance across two `_run()`
  calls, which the workspace's own single-use claim authority correctly
  refused on the second call; the second scenario now uses the existing
  `second_run_workspace` fixture instead);
- a structural test that `_origin`'s three values are never mistaken for a
  fourth scrub-finding-code taxonomy entry.

## Offline suite result

```text
953 passed, 0 failed
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(514 unchanged I1/I2 through FU3B; 439 in `test_i2b_controller.py`, up from
FU2E's 428 -- 11 new tests, 1 corrected, for this follow-up.)

Frozen suites re-run unmodified (each run separately -- running all three
`ar1`/`ar2`/`ar2_o1` suites in one combined `pytest` invocation collides on
their identically-named `conftest` modules, a pre-existing pytest collection
artifact unrelated to this phase, confirmed by running them individually):

```text
experiments/pi_external_runtime_ar1/tests          96 passed, 0 failed
experiments/pi_external_runtime_ar2/tests         290 passed, 0 failed
experiments/pi_external_runtime_ar2_o1/tests       89 passed, 0 failed
```

No file under `ar1/`, `ar2/`, `o1/`, `src/`, root `tests/` or `projects/` was
touched. `i2b_session.py`, `i2b_workspace.py` and every other reused I2
module were not modified.

## No-live/no-network/no-model/no-credential confirmation

Unchanged from every prior FU2* closure: this follow-up touches only
`qualification/i2b_controller.py`'s `CategoryBEvidence`/
`CategoryBControllerResult` and `tests/test_i2b_controller.py`. No new
import of `subprocess`/`socket`/`http`/`urllib`/`os.environ` was added (the
module's own source-level regression test enforces this mechanically and
still passes); no test opens a socket, launches a process, or reads an
environment variable for a credential; the one "synthetic needle" used to
force a real dirty scrub result (`"synthetic_finding"`) and the one synthetic
API-key-shaped string used to prove a real scrub catch (`"sk-should-be-
caught"`, already an established pattern from
`test_retention_ready_true_is_only_reachable_by_actually_scrubbing_the_
payload`) are both fabricated test literals, never real credentials. A
scratch, throwaway diagnostic script used to confirm the pre-fix/post-fix
predicate difference during this phase's own investigation was never part of
the shipped package or the test suite, and was deleted before this phase's
tests were finalized. Category-B live execution, Q1/Q2, and real-workspace
authority all remain **NO-GO**.

## Corrected claims

**FU2E's closing verdict of "READY FOR FINAL INDEPENDENT FREEZE REVIEW" was
premature**, for exactly the one narrow residual independent review named.
FU2E closed the fact-vs-gate and protocol-fact-vs-code bindings, but its own
regression suite still let `EVIDENCE_SAFETY`'s failure code disagree with the
evidence object actually attached to the same result -- so the suite was, in
that one place, defending a code/state pairing the real controller can never
produce. README.md's I2B status block is corrected in place with a pointer
to this section.

## What this does NOT establish

Unchanged from FU2/FU2A/FU2B/FU2C/FU2D/FU2E, and true as of this phase's
acceptance: no zero-prompt live gate had run (one has since occurred -- see
the TOP-LEVEL CORRECTION at the head of this document);
`get_commands` still proves nothing about the active tool
registry; the adapter trust boundary is unchanged; the synthetic workspace
authority is not real-workspace authority; no claim about descendants,
inference, or GPU work; redaction/scrubbing remain backstops, not
guarantees; the evidence-binding check still covers only the
canonical-evidence fields represented as typed result fields; these
validators prove a result describes a trace the controller COULD have
produced, never that it describes a trace that DID occur.

**Additionally, narrowly, from this follow-up:** the evidence-origin binding
is, like every other FU2* rule, a transcription of the CURRENT controller's
exact call sites (`_refused`'s one production call site; `_build_from_payload`'s
one production call site inside `_build_evidence`). A future change that adds
a THIRD production call site for either classmethod, or that changes which
finding-code tuple the safety-context-unprovable branch passes to `_refused`,
must update `_SAFETY_CONTEXT_UNPROVABLE_REFUSAL` and the `_origin`-keyed
branch in the same commit -- the regression suite's real-controller-path
counterexamples (4 and 5) are what would catch a divergence. The
`MALFORMED_ADAPTER_RESULT` unreachability argument is likewise a proof about
the CURRENT source's control flow, not a structural guarantee independent of
it; a future change to how `provisional_pass`/`failed_gate` are computed
could reopen that branch's reachability, and would need to be re-audited
against this section's argument before being trusted again.

---

# 5F3B-I2B-L1-LF1 — Live Finding 1

**Required-flag observation correction + Pi 0.84.4 protocol-drift
attribution.** Everything in this section is OFFLINE. No live attempt was
made, Candidate A was not re-run, no prompt was sent, no real credential was
read, no broker was opened, no Node/Pi process was launched, and `/models`
was not called.

## 0. The first live record

The one and only Candidate-A Category-B live attempt is retained verbatim at
`results/i2b_live_A_20260831T192543Z.json`. **It has not been edited,
rewritten, or retroactively reclassified**, and it is not reclassified here:
its `outcome`, `failed_gate`, `failure_code` and every gate status stand as
historical evidence of what the frozen controller received from the live
adapter.

What is corrected is the FAILURE ATTRIBUTION — a statement *about* that
record — and the adapter producer that generated the false fact it
faithfully reported.

## 1. Did the first live refusal prove that unknown flags were rejected?

**No. It proved nothing about CLI flags at all.**

The retained record shows `rpc_launch_shape_valid: true`,
`lf_jsonl_correlation_succeeded: true`, `required_launch_flags_accepted:
false`. Under the pre-LF1 producer the third value was:

```
required_flags_accepted =
    launch_shape_valid AND lf_jsonl_correlation_succeeded AND NOT protocol_violation_observed
```

with

```
raw = stdout_state()["protocol_violation"]
protocol_violation_observed = type(raw) is not bool or raw is True
```

**That expression is UNSATISFIABLE against the frozen AR2 contract.**
`ar2.protocol.RecordStreamReader.protocol_violation` is declared
`str | None`, initialised to `None`, and only ever assigned a violation
MESSAGE string (`protocol.py:286`, `:350`, `:357`);
`PiRpcSupervisor.stdout_state()` republishes that value verbatim
(`supervisor.py:465`). It is never a `bool`. So `type(None) is not bool` is
`True`, and `protocol_violation_observed` was `True` on **every** real
launch, clean or not — which forced `required_flags_accepted` to `False` on
every real launch, whatever the runtime actually did.

The live refusal is therefore fully explained without any protocol violation
and without any unknown flag. Two further lines of evidence — one merely
suggestive, one conclusive — point the same way:

* **From the retained artifact — SUGGESTIVE, not conclusive.**
  `lf_jsonl_correlation_succeeded: true` means `await_response` returned
  `RUNTIME_RESPONSE_RECEIVED`, and `PiRpcSupervisor._wait` has exactly two
  paths that return it. On the **ordinary loop path**,
  `_terminal_stream_outcome()` is evaluated and must return `None` in the
  *same iteration*, immediately before `satisfied()` produces that outcome —
  and it returns `RUNTIME_PROTOCOL_VIOLATION` for any truthy
  `protocol_violation` — so that path does establish that no violation had
  been detected at that instant. On the **child-already-exited branch**,
  however, `satisfied()` is checked BEFORE the terminal check, so that path
  does **not** exclude a violation. The retained artifact does not record
  which path was taken, and a violation arriving between `await_response`
  returning and the adapter's later `stdout_state()` call is not excluded
  either. **This line of evidence is therefore stated as suggestive only.**
  It is not load-bearing: the next one is.
* **Mechanically, from the Pi 0.84.4 source — CONCLUSIVE, and independent
  of the above.** An unknown-flag rejection cannot coexist with a correlated
  RPC response at all, on any path: Pi calls `process.exit(1)` before
  `runRpcMode` is entered, so it never attaches its JSONL stdin reader, never
  reads AIDO's `get_commands` frame, and never writes a response record —
  `satisfied()` cannot become true in either `_wait` branch (§3). So the one
  fact the artifact does record unambiguously, a correlated response, already
  rules an unknown-flag rejection out.

The retained artifact did **not** keep the raw offending record, so it cannot
by itself distinguish the two hypotheses. That is exactly the gap Objective 6
closes.

> **Stated precisely.** The live run was a VALID FAIL-CLOSED RUN: it refused,
> it sent zero semantic prompts, it tore down, it cleaned up, and it
> verified. Its failure was misATTRIBUTED, by the adapter, to
> `REQUIRED_LAUNCH_FLAGS_REJECTED`. **The frozen controller behaved exactly
> as designed** — it mapped a `False` adapter fact to that gate's code — and
> is not reopened.

## 2. Pre-fix reproduction (Objective 1)

Written and run BEFORE any code change, against the unmodified adapter, with
**no unknown-flag observation present in either synthetic input** (in both,
the synthetic runtime accepted the exact argv, entered RPC command
processing, consumed AIDO's one `get_commands` frame, and returned a
correlated response):

```
tests/test_lf1_prefix_reproduction.py ...                         [100%]
3 passed in 0.40s
```

1. `launch_shape_valid=True`, LF correlation `True`, `protocol_violation=None`
   (a wholly CLEAN run, in the real `str | None` contract)
   → pre-fix `required_flags_accepted=False`. **This is the live run.**
2. `launch_shape_valid=True`, LF correlation `True`, `protocol_violation=<a
   real violation message>` → pre-fix `required_flags_accepted=False`.
   (The reviewer's hypothesised misattribution — also real, but not what the
   live run needed.)
3. Source pin: the frozen reader declares `str | None`.

That temporary module was removed once the fix landed, because it asserted
the defective behaviour. Its content survives as permanent regressions:
`test_lf1_prefix_defect_reproduction_old_projection_was_unsatisfiable`
evaluates the exact pre-LF1 expression over the frozen contract's real value
domain and proves it can never be `False`; the two behavioural cases became
`test_lf1_clean_run_real_supervisor_contract_accepts_required_flags` and
`test_lf1_launch_window_protocol_violation_does_not_deny_required_flags`.

**Why the offline suite never caught this.** The suite's supervisor double
published `protocol_violation` as a `bool` (`self._protocol_violation =
False`). The DOUBLE, not the adapter, disagreed with the real class, so an
adapter check that was unsatisfiable against real state passed here for
free. The double now defaults to `None` and models an observed violation
with a message STRING, exactly as `RecordStreamReader` does.

## 3. Pi 0.84.4 required-flag source inspection (Objective 2)

Offline inspection of the installed package
(`@earendil-works/pi-coding-agent`, `package.json` version `0.84.4`). No
launch, no network, no version gate.

**(a) Are all of AIDO's required argv flags still recognized?** Yes — all
fourteen, each with its own explicit `else if` branch in
`dist/cli/args.js` `parseArgs`:

| flag | recognized | takes a value |
|---|---|---|
| `--mode rpc` | yes (`text`/`json`/`rpc` accepted) | yes |
| `--no-session` | yes | no |
| `--no-extensions` | yes (`-ne`) | no |
| `--extension <path>` | yes (`-e`) | yes |
| `--tools <list>` | yes (`-t`) | yes |
| `--no-builtin-tools` | yes (`-nbt`) | no |
| `--no-skills` | yes (`-ns`) | no |
| `--no-prompt-templates` | yes (`-np`) | no |
| `--no-themes` | yes | no |
| `--no-context-files` | yes (`-nc`) | no |
| `--no-approve` | yes (`-na`) | no |
| `--offline` | yes | no |
| `--provider <name>` | yes | yes |
| `--model <pattern>` | yes | yes |

**(b) What code path does an unknown option take?**

* An unrecognized `--flag` does **not** error in `parseArgs`. It falls
  through to the `arg.startsWith("--")` catch-all and is stored in
  `result.unknownFlags` (this is Pi's extension-registered-flag mechanism).
  Later, `dist/core/agent-session-services.js` `applyExtensionFlagValues`
  compares each name against the flags the LOADED extensions registered; any
  name with no registration becomes
  `{type: "error", message: "Unknown option: --<name>"}` in the runtime's
  diagnostics.
* An unrecognized single-dash token (`-x`) pushes
  `{type: "error", message: "Unknown option: -x"}` straight into
  `result.diagnostics` during `parseArgs`.

**(c) Does unknown-option handling exit before RPC request processing?**
**Yes, in both paths, unconditionally.** In `dist/main.js`: a `parseArgs`
error diagnostic is printed and `process.exit(1)` runs immediately after
parsing; a runtime error diagnostic sets `hasRuntimeErrors`, is reported, and
also calls `process.exit(1)`. Both exits are strictly above the
`if (appMode === "rpc") { printTimings(); await runRpcMode(runtime); }`
block, so `runRpcMode` — the only place Pi attaches its JSONL stdin reader —
is never entered.

**(d) Which channel is the error emitted on?** **stderr.**
`reportDiagnostics` and the `parseArgs` diagnostic loop both use
`console.error`; the `parseArgs` path additionally exits before
`runRpcMode`'s `takeOverStdout()` could redirect anything. Nothing about the
message is written to stdout. There is no structured diagnostic channel.

**(e) Is there a stable machine-observable outcome AR2's supervisor already
exposes?** **Yes: the direct child terminates without answering.**
`PiRpcSupervisor._wait` polls `self.process.poll()`; a child that exited
without producing the awaited response yields `RUNTIME_EXITED_EARLY`. That is
a declared AR2 constant, already produced by the frozen supervisor, requiring
no stderr parsing at all.

**The smallest truthful live observation** that establishes *no "unknown
flag" startup rejection* is therefore: **AIDO's own argv contains only
source-established options, AND the exact argv was launched and the runtime
went on to answer AIDO's one correlated JSONL RPC command.** No semantic
prompt, no second candidate, no network call, no second runtime, no raw
secret retention, no version pin. No human stderr prose is parsed.

## 4. Every supervisor protocol-violation trigger condition (Objective 3)

`stdout_state()["protocol_violation"]` is set in exactly **five** places, all
in `ar2.protocol`'s stdout framing/decoding path, and all assign a message
STRING:

1. `RecordStreamReader._run` — a blank framed record (`raw.strip()` empty);
2. `decode_record` — an empty/whitespace-only record;
3. `decode_record` — a record that is not valid UTF-8;
4. `decode_record` — a record that is not strict JSON;
5. `decode_record` — a record that is JSON but not an OBJECT.

Enumerated and exercised offline in
`test_lf1_every_protocol_violation_trigger_condition_is_enumerated`, which
also proves the field is monotonic (the reader assigns once and returns) and
that a clean stream leaves it at exactly `None`.

**None of the five is a CLI-flag observation**, which is the structural
reason the same bit must never serve both `required_launch_flags` and
`protocol_integrity`.

### Source-level Pi 0.84.4 protocol drift found: NONE

* RPC-mode stdout is written through exactly one function,
  `dist/modes/rpc/jsonl.js` `serializeJsonLine` —
  ``return `${JSON.stringify(value)}\n`;`` — one JSON value, LF-only
  framing, one record per line. Its header states the same LF-only rule
  (and the same U+2028/U+2029 caveat) that `ar2.protocol` implements. Every
  RPC emission (`output(...)`, responses, events, `extension_ui_request`)
  goes through it, so no top-level non-object and no non-JSON record can be
  produced by that path.
* `runRpcMode` calls `takeOverStdout()` as its **first** statement
  (`dist/core/output-guard.js`), which replaces `process.stdout.write` with a
  writer that redirects to **stderr** and routes protocol output through the
  retained raw handle. For the whole RPC lifetime, any stray
  `console.log`/`process.stdout.write` lands on stderr, not on the protocol
  channel.
* The only unguarded stdout writers in the package are on paths AIDO's argv
  does not reach: `--version`, `--export`, `printHelp`, the auth/list-models/
  session-picker/config commands, interactive/TUI mode, and the session-
  resume prompts (AIDO passes `--no-session` and neither `--continue` nor
  `--resume`). `printTimings` writes to stderr and is inert unless
  `PI_TIMING=1`. `core/model-resolver.js` `restoreModelFromSession` contains
  three `console.log` calls but has **no caller anywhere in `dist/`** — dead
  code in this build.
* The AR2 disposable extension AIDO writes contains no `console.*` and no
  `process.stdout` write at all.

`test_lf1_pi_rpc_output_shape_is_accepted_by_the_frozen_parser` models Pi's
exact `serializeJsonLine` shape for the record kinds a zero-prompt run can
see — including a payload carrying real U+2028/U+2029 — and proves the frozen
parser accepts every one with `protocol_violation is None`.

> **Source-supported possible causes vs. actual observed cause.** The five
> conditions above are the complete set of *source-supported possible*
> causes. The **actual observed cause** of the live run's
> `required_flags_accepted=False` is the unsatisfiable type check in §1 — a
> defect that fires with or without any of them. **No claim is made that the
> live run hit any specific protocol-violation condition**; the retained
> artifact did not keep the raw offending record, and no source-level drift
> in Pi 0.84.4 that could produce one for AIDO's argv was found.

## 5. The corrected `required_flags_accepted` producer (Objective 4)

```
required_flags_accepted =
    argv_options_are_source_established(argv)      # AIDO's OWN argv
    AND lf_jsonl_correlation_succeeded             # the runtime answered
```

with the proof chain stated in full at the definition site:

```
exact argv AIDO constructed            (every option token source-established)
+ Pi CLI parser behaviour from current package source
      (unknown flag -> error diagnostic -> stderr -> process.exit(1),
       strictly BEFORE runRpcMode is entered)
+ exact observed runtime behaviour
      (the child consumed AIDO's one JSONL command and returned a
       correlated response, so runRpcMode ran)
=> no "unknown flag" startup rejection
```

This is the same evidence shape frozen AR2/O1 already accepted for its own
`required_launch_flags_accepted` (`run_o1.py`: the `build_pi_argv` argv was
accepted because the process reached H1/H2 without an early exit), and O1
likewise kept `no_protocol_violation_during_handshake` as a **separate**
fact.

**It is deliberately NOT a rename of "no protocol violation", and it is
deliberately NOT a collapse into LF correlation.** The argv half is checked
against AIDO's own argv before any runtime behaviour is consulted and fails
closed on its own: `test_lf1_unestablished_argv_option_denies_required_flags_
accepted` shows a correlated RPC response is *not* sufficient when the argv
carries an option whose recognition was never source-established.
`test_lf1_required_flags_producer_reads_no_protocol_violation_bit` pins, at
source level, that `protocol_violation` appears nowhere in the assignment.

**One further misattribution corrected alongside it.**
`RUNTIME_EXITED_EARLY` was missing from
`_RECOGNIZED_AWAIT_RESPONSE_OUTCOMES`, so a genuine early exit — exactly the
unknown-flag rejection shape — made `launch_shape_valid` `False` and failed
the *earlier* `rpc_launch_shape` gate. The Node-direct `--mode rpc` launch
shape was in fact constructed and launched correctly in that case; what
failed was flag acceptance. The tuple is now the exact, complete reachable
return domain of `PiRpcSupervisor._wait` (`RUNTIME_SETTLED` and
`RUNTIME_LAUNCH_FAILED` remain out, because `await_response` cannot produce
them).

The four launch facts remain four distinct facts: `observed_pi_version`,
`launch_shape_valid`, `required_flags_accepted`,
`lf_jsonl_correlation_succeeded`.

## 6. Independence of required flags and protocol integrity (Objectives 5, 6)

`observe_protocol` already read the supervisor's **cumulative** state, and
still does: `RecordStreamReader.protocol_violation` is assigned exactly once
(the reader thread then returns), nothing clears it, and `stdout_state()`
republishes that same live field on every call. Correcting
`required_flags_accepted` therefore cannot make a launch-window violation
disappear — only its type projection needed fixing, which it got
(`_protocol_violation_observed`, shared by both call sites).

Proven end to end, in both directions:

* `test_lf1_launch_window_protocol_violation_survives_to_protocol_observation`
  — one real observation set yields `required_flags_accepted=True` **and**
  `protocol_violation_observed=True`.
* `test_lf1_required_flags_pass_while_protocol_integrity_fails` (frozen
  controller) — `required_launch_flags = PASSED` alongside
  `protocol_integrity = FAILED:PROTOCOL_VIOLATION_OBSERVED`.
* `test_lf1_required_flags_fail_while_protocol_integrity_is_clean` (frozen
  controller) — an unknown-flag rejection attributes to
  `required_launch_flags`, leaves `rpc_launch_shape` PASSED, and leaves
  `protocol_integrity` `NOT_REACHED`.

### The bounded live diagnostic

Three declared codes per run, recorded at the **L1 harness/live-run level
only**. The frozen `RuntimeLaunchObservation` and the frozen
`CategoryBEvidence` schema are untouched, so frozen I2B is not reopened; the
harness attaches it as a SIBLING of `evidence`, never inside it.

```
launch_diagnostics: {
  "<run_id>": {
    "argv_options":           argv_options_all_source_established
                            | argv_option_not_source_established
    "launch_correlation":     correlated_rpc_response_received
                            | no_response_runtime_exited_early
                            | no_response_deadline_expired
                            | no_response_protocol_violation
                            | no_response_output_cap_exceeded
                            | no_response_event_cap_exceeded
                            | no_response_read_error
                            | no_response_unrecognized_outcome
    "launch_window_protocol": launch_window_protocol_violation_observed
                            | launch_window_protocol_violation_not_observed
  }
}
```

Raw observations are reduced to these literals at the moment of observation
and the raw values are dropped. A future zero-prompt refusal reads as
`no_response_runtime_exited_early` for an unknown-flag rejection and as
`launch_window_protocol_violation_observed` for a launch-window protocol
violation — no raw log needed. Retained: nothing else. **Never** raw stdout,
raw stderr, a raw RPC object, an endpoint, an API key, a broker token, a pipe
name, a capability id, an absolute workspace path, an argv token, or a
violation message —
`test_lf1_launch_diagnostic_values_are_declared_codes_only` and
`test_lf1_live_harness_diagnostic_passes_the_qualification_scrub` prove it,
the latter through the package's own `qualification_scrub_check` under a
context declaring the run's real broker token, pipe name, capability id,
endpoint host, API key and absolute workspace path as needles.

## 7. Pi version 0.84.4 (Objective 7)

**No authorization rule changed. Pi version remains PROVENANCE ONLY.** Both
facts stand and neither supersedes the other:

```
historical source-inspection baseline : 0.84.3
first L1 live observation             : 0.84.4   (Candidate A, first
                                                  Category-B attempt)
```

The LF1 source inspection in §3 was performed against the **installed
0.84.4** package. `test_lf1_pi_version_mismatch_alone_never_rejects` proves
0.84.3, 0.84.4 and an unreleased version all produce identical launch facts,
and `test_lf1_no_version_string_is_consulted_by_the_corrected_producer`
proves no version literal appears in the corrected machinery. No
exact-version authorization gate was introduced.

## 8. Files changed

| file | change |
|---|---|
| `qualification/i2b_live_adapters.py` | corrected `required_flags_accepted` producer + its proof chain; new `_argv_options_are_source_established`, `_protocol_violation_observed`, `LaunchDiagnostic`/`_launch_diagnostic`/`launch_diagnostics()`; `RUNTIME_EXITED_EARLY` added to the recognized outcome domain; `observe_protocol` type projection fixed; module docstring |
| `run_i2b_live.py` | attaches `launch_diagnostics` to the run summary, beside (never inside) the frozen evidence |
| `tests/test_i2b_live_adapters.py` | supervisor double's `protocol_violation` contract corrected to `str \| None`; two superseded misattribution tests replaced; LF1 regressions added |
| `tests/test_i2b_controller.py` | two frozen-controller gate-independence regressions (no controller source change) |
| `FINDINGS.md` | this section |

**Not changed:** the frozen I2B controller source, `qualification/
i2b_session.py`, `qualification/i2b_workspace.py`, anything under `ar2/`,
anything under `o1/`, `src/`, `CLAUDE.md`, and the retained live result
artifact.

## 9. Offline regression counts

| suite | before LF1 | after LF1 |
|---|---|---|
| `pi_implementer_qualification` | 1165 passed | 1187 passed |
| `pi_external_runtime_ar2` | 298 passed | 298 passed |
| `pi_external_runtime_ar1` | 96 passed | 96 passed |
| `pi_external_runtime_ar2_o1` | 89 passed | 89 passed |
| root production `tests/` | 3504 passed | 3504 passed |

Net **+22** in the qualification suite = **24 new LF1 regressions**
(`pytest -k lf1` collects exactly 24: 22 in `test_i2b_live_adapters.py`,
counting the 3 parametrizations of the version test as 3, plus 2 in
`test_i2b_controller.py`) **minus the 2 superseded misattribution tests they
replace** (`test_launch_runtime_protocol_violation_denies_required_flags_
accepted` and `test_launch_runtime_malformed_protocol_violation_type_fails_
closed`, both of which asserted exactly the behaviour LF1 corrects).

The four other suites are unchanged in count and content: LF1 touched no
file under `ar2/`, `o1/` or `src/`.

## 10. No-live confirmation

**No live attempt was made during LF1, and none is authorized.** Candidate A
was not re-run and must not be. Candidate B: **NO-GO**. Q1/Q2: **NO-GO**.
Real-workspace authority: **NO-GO**. Zero prompts were sent; no `/models`
call was made; no real credential, broker, pipe, Node process or Pi process
was created. The Pi 0.84.4 inspection was pure filesystem reading of the
installed package — the runtime was never launched, not even for
`--version`. Every regression above uses the established synthetic
doubles under pytest `tmp_path`, with no socket, no subprocess and no
environment credential.

## 11. What LF1 does NOT establish

* It does **not** establish that the live run's runtime was Category-B
  compatible. `required_launch_flags` is one gate of many, and the live run
  never reached `get_commands`, `h1`, `get_state`, `h2`,
  `protocol_integrity` or `route_check`. **Candidate A remains NOT YET
  QUALIFIED.**
* It does **not** establish what would happen on a corrected live run. The
  corrected producer is proven against synthetic doubles only; whether the
  real runtime returns a correlated response is precisely what a future,
  separately authorized live attempt would observe.
* It does **not** prove the live run had no protocol violation. What it
  proves is narrower: an unknown-flag rejection is ruled out conclusively
  (§1), the pre-LF1 producer would have reported `required_flags_accepted=
  False` with or without a violation, no source-level Pi 0.84.4 cause for one
  was found (§4), and — only if `_wait`'s ordinary loop path was the one
  taken, which the artifact does not record — none had been detected up to
  the moment the correlated response was accepted. A violation is neither
  established nor excluded by the retained evidence, and this section does
  not claim otherwise.
* The argv self-check is a fact about AIDO's OWN argv vocabulary against the
  CURRENTLY installed Pi source. It is not a guarantee about a future Pi
  build, and a future `build_pi_argv` change must re-establish the added
  option's recognition in the same commit — the check fails closed until it
  does, which is the intended behaviour, not a defect.
* Nothing here weakens any standing scope claim: no fixer, no
  model-backed implementer, no second candidate, no semantic prompt path,
  no agent loop, no descendant/inference/GPU claim, and redaction/scrubbing
  remain backstops, not guarantees.

---

# 5F3B-I2B-L1-LF1-FU1 — Required-Flag / LF-Correlation Independence Closure

**Everything in this section is OFFLINE. No live attempt was made, no
Node/Pi process was launched, no broker or named pipe was opened, no
`/models` request was issued, no real credential was read, and no semantic
prompt exists anywhere in this work.** Candidate A was not re-run and
Candidate B was not run. The one retained live artifact
(`results/i2b_live_A_20260831T192543Z.json`) is unedited.

## 1. The blocker

LF1's corrected producer still computed the required-flag fact as a
conjunction with the LF-correlation fact:

```text
required_flags_accepted = argv_options_source_established
                          and lf_jsonl_correlation_succeeded
```

The implication that expression rests on is sound in ONE direction:

```text
correlated RPC response  =>  Pi entered runRpcMode
                         =>  no unknown-option startup rejection occurred
```

The reverse is not:

```text
no correlated response   =/=>  an unknown CLI flag was rejected
```

The frozen controller evaluates

```text
RPC_LAUNCH_SHAPE -> REQUIRED_LAUNCH_FLAGS -> LF_JSONL_CORRELATION -> ...
                 -> PROTOCOL_INTEGRITY
```

and reads `required_flags_accepted=False` on a trusted session as
`REQUIRED_LAUNCH_FLAGS_REJECTED`. So every correlation failure was
attributed FIRST as an unknown-flag rejection. The four launch facts existed
as four fields, but `LF correlation false => required flags false` was a hard
producer invariant, so two of them were not observationally independent.

## 2. Pre-fix reproduction (six outcomes)

Reproduced offline against the synthetic supervisor double, with AIDO's own
argv source-established and no unknown-option observation in any case. Each
row is the `RuntimeLaunchObservation` the LF1 producer actually returned,
followed by what the **unmodified** frozen controller then reported when
driven end to end over the real live adapters:

| `await_response` outcome     | argv src-est. | session | `launch_shape_valid` | `lf_..._succeeded` | `required_flags_accepted` | controller first failure |
|------------------------------|---------------|---------|----------------------|--------------------|---------------------------|--------------------------|
| `RUNTIME_DEADLINE_EXPIRED`   | True          | yes     | True                 | False              | **False**                 | `required_launch_flags` / `REQUIRED_LAUNCH_FLAGS_REJECTED` |
| `RUNTIME_PROTOCOL_VIOLATION` | True          | yes     | True                 | False              | **False**                 | `required_launch_flags` / `REQUIRED_LAUNCH_FLAGS_REJECTED` |
| `RUNTIME_OUTPUT_CAP_EXCEEDED`| True          | yes     | True                 | False              | **False**                 | `required_launch_flags` / `REQUIRED_LAUNCH_FLAGS_REJECTED` |
| `RUNTIME_EVENT_CAP_EXCEEDED` | True          | yes     | True                 | False              | **False**                 | `required_launch_flags` / `REQUIRED_LAUNCH_FLAGS_REJECTED` |
| `RUNTIME_READ_ERROR`         | True          | yes     | True                 | False              | **False**                 | `required_launch_flags` / `REQUIRED_LAUNCH_FLAGS_REJECTED` |
| `RUNTIME_EXITED_EARLY`       | True          | no cause| True                 | False              | **False**                 | `required_launch_flags` / `REQUIRED_LAUNCH_FLAGS_REJECTED` |

All six were misattributed. None of them mechanically proves an
unknown-option startup rejection; `RUNTIME_EXITED_EARLY` is *compatible* with
one but is equally produced by any other pre-RPC child exit.

No frozen controller source was edited to obtain this. The controller behaved
exactly as designed — it mapped a FALSE adapter fact to that failure code —
and the defect was, again, in the producer of the fact.

## 3. The corrected evidence rules (three states)

Required-flag evidence is now classified internally into three states
(`qualification/i2b_live_adapters.py`,
`_classify_required_flag_evidence`). The frozen
`RuntimeLaunchObservation` and the frozen controller are unchanged — neither
gained a third state.

**ACCEPTED** — decided FIRST, and it is LF1's positive proof, unchanged:

```text
actual argv is source-established
  AND the exact runtime returned a correlated RPC response
=> Pi entered runRpcMode
=> no unknown-option startup rejection occurred
```

Both unknown-option exits (`dist/cli/args.js` `parseArgs` → an error
diagnostic → `process.exit(1)`; `dist/core/agent-session-services.js`
`applyExtensionFlagValues` → a runtime error diagnostic →
`reportDiagnostics` → `process.exit(1)`) run strictly before the
`appMode === "rpc"` branch that awaits `runRpcMode`, so a rejected option
cannot answer an RPC command. The actual-argv check was NOT removed.

**REJECTED** — only when a bounded startup diagnostic specifically
establishes that Pi rejected an option **present in AIDO's own argv**. It is
never inferred from a process exit, a missing response, a deadline, a
protocol violation, an output/event cap, or a read error.

**INDETERMINATE** — everything else, including: a deadline; a protocol
violation without a correlated response; an output cap; an event cap; a read
error; a generic early exit with no unknown-option observation; an
unreadable, truncated or ambiguous diagnostic; and an argv whose options are
not source-established **even when a correlated response did arrive** (that
case is a fail-closed refusal about AIDO's own argv vocabulary, and is
emphatically not a claim that Pi rejected anything).

`_classify_required_flag_evidence` reads **no supervisor outcome constant at
all**, so no outcome can become a proxy for flag rejection by drift.

## 4. How INDETERMINATE maps into the frozen controller without lying

The frozen `RuntimeLaunchObservation` carries one `bool`. For an
indeterminate launch, `True` would fabricate a proof that was never obtained
and `False` would invent a cause more specific than what was observed. There
is therefore **no truthful session-bearing observation** for that state.

So an indeterminate launch fails **earlier**, at the adapter's own
runtime-launch boundary, through the existing creator-retained cleanup
contract:

```text
INDETERMINATE
  -> _retain_and_close_partial_runtime(...)      (exactly ONE bounded self-close)
  -> RuntimeLaunchObservation(session=None, ...)
  -> frozen controller: RUNTIME_LAUNCH = FAILED:RUNTIME_LAUNCH_FAILED
  -> RPC_LAUNCH_SHAPE / REQUIRED_LAUNCH_FLAGS / LF_JSONL_CORRELATION
     / PI_VERSION_OBSERVED  = NOT_REACHED
```

`RUNTIME_LAUNCH_FAILED` is the honest statement "this launch produced no
trustworthy runtime session", and `REQUIRED_LAUNCH_FLAGS` is never told a
rejection happened.

Two things make this truthful rather than merely convenient:

1. **The frozen controller already sanctions exactly this shape.** Its
   `_RUNTIME_LAUNCH_STATUSES_WITH_VALID_OBSERVATION_BUT_OWN_GATE_UNREACHED`
   names `RUNTIME_LAUNCH_FAILED` as one of the two statuses at which a
   genuinely-consumed observation's four launch facts may each stand
   independently while their own gates read `NOT_REACHED`. Nothing was added
   to the controller to accommodate FU1; this is pinned by three new
   regressions in `tests/test_i2b_controller.py` (controller **source**
   unmodified).
2. **The facts the launch DID establish are carried through, not flattened.**
   `_retain_and_close_partial_runtime` gained three optional parameters
   (`launch_shape_valid`, `lf_jsonl_correlation_succeeded`,
   `observed_pi_version`), all defaulting to the conservative values every
   pre-existing caller genuinely observed. So an indeterminate launch reports
   a valid launch shape, the observed Pi version, and — in the
   argv-not-source-established case — an LF correlation that genuinely DID
   succeed. `required_flags_accepted` is always `False` there and is
   deliberately **not** a parameter: with no session there is no gate to
   interpret it, so it means "not established by this launch", never
   "rejected".

`resource_created`, `cleanup_attempted` and `direct_child_reported_exit` are
preserved truthfully, exactly one self-close is performed, and a self-close
that itself raises is reported as an unverified postcondition rather than
erasing the primary failure (BLOCKER 3 still holds on the new path).

This mapping was **not** chosen to make `LF_JSONL_CORRELATION` reachable — it
makes that gate *unreachable* for these outcomes. It was chosen because
failing closed is truthful and inventing a more specific cause is not.

## 5. Was `stderr_snapshot` needed, and what is its bounded reduction

**Yes.** Without a mechanism to establish a rejection, `REJECTED` would be
unreachable and `REQUIRED_LAUNCH_FLAGS_REJECTED` could never be produced from
a real observation at all. The existing **public**
`PiRpcSupervisor.stderr_snapshot()` surface is used, in exactly one place
(`_unknown_option_rejection_established`), reached only when the positive
acceptance proof did not hold — so the ordinary passing path never reads raw
stderr at all.

The unknown-option emission path was established from the **currently
installed** package source, offline:

* `dist/cli/args.js` `parseArgs` pushes `{type: "error", message: "Unknown
  option: <arg>"}` for a single-dash token matching no branch, and records
  unrecognized long options in `unknownFlags`;
* `dist/core/agent-session-services.js` `applyExtensionFlagValues` turns any
  `unknownFlags` name no loaded extension registered into
  `{type: "error", message: "Unknown option: --<name>"}` — or
  `"Unknown options: --<a>, --<b>"` for more than one;
* `dist/main.js` prints both through `chalk` to **stderr** with an
  `"Error: "` prefix and calls `process.exit(1)`, in both cases strictly
  before the `appMode === "rpc"` branch.

The matched shape is therefore the smallest one that is mechanically
justified: an `Error: `-prefixed line (only error diagnostics reach
`process.exit(1)`; a `Warning:` line is refused) whose message is exactly
`Unknown option: …` / `Unknown options: …`, with `chalk`'s SGR wrapper
stripped, and with **every** named token required to be an option token
present in AIDO's own argv. `_argv_option_tokens` walks AIDO's argv the way
`parseArgs` walks it (value-taking options consume the next token;
`--name=value` carries its own; an unrecognized long option consumes a
following token only when it starts with neither `-` nor `@`) and collects
**option tokens only** — never a value, so no absolute extension path can be
collected.

It fails closed on: a non-mapping snapshot; `captured` not exactly `True`;
`read_error is not None`; `cap_exceeded` not exactly `False`;
`bytes_seen != bytes_retained`; `bytes_retained` above the frozen
4000-character `text_tail` bound (so a sliced tail is never read as
complete); a non-`str` `text_tail`; a `stderr_snapshot()` call that raises;
no matching line; and a matching line naming any option not in AIDO's argv.

`eof` is deliberately **not** required, and the reason is stated rather than
assumed: stream completeness matters only for an ABSENCE proof, and this
function never makes one — it accepts only the POSITIVE presence of a
diagnostic, and the checks above already prove nothing was dropped from what
the reader saw. Requiring `eof` would add a race in which a genuine rejection
reads as indeterminate because the reader thread had not yet seen
end-of-stream.

**The reduction is immediate and total.** The tail is scanned transiently and
the function returns one `bool`. What is retained is one declared literal —
`required_flags_accepted`, `required_flags_rejected_unknown_option`, or
`required_flags_indeterminate` — added as the fourth field of the existing
bounded `LaunchDiagnostic`. No stderr line, message, option name, byte count
or fragment reaches a `RuntimeLaunchObservation`, a `CategoryBEvidence`, the
launch diagnostics, the result JSON, or any exception text. The reducer
refuses an undeclared classification outright, and its refusal message names
no runtime value.

## 6. `RUNTIME_EXITED_EARLY` is not proof

`RUNTIME_EXITED_EARLY` remains in `_RECOGNIZED_AWAIT_RESPONSE_OUTCOMES` —
that LF1 correction stands. Its prose is corrected:

```text
an unknown-option startup rejection is ONE source-supported cause of
RUNTIME_EXITED_EARLY
```

not

```text
RUNTIME_EXITED_EARLY itself proves unknown-option rejection.
```

Proved two ways. Behaviourally: `RUNTIME_EXITED_EARLY` with no unknown-option
observation classifies INDETERMINATE, identically to the other five
outcomes, and hands over no session. At source level: no supervisor outcome
constant appears in the **code** of `_classify_required_flag_evidence`,
`_unknown_option_rejection_established` or `_argv_option_tokens` (the check
strips docstrings, so the explanatory prose cannot satisfy or defeat it).

## 7. Required flags vs LF correlation — independence

| # | Claim | How proved |
|---|-------|-----------|
| 1 | ACCEPTED + LF PASS constructible | real launch, correlated response → `required_flags_accepted=True`, diagnostic `required_flags_accepted` |
| 2 | ACCEPTED + LF FAIL | **not constructible, deliberately** — see below |
| 4 | LF failure does not decide the flag fact | ONE fixed outcome (`RUNTIME_EXITED_EARLY`), TWO classifications: with the diagnostic → REJECTED (session handed over); without it → INDETERMINATE (no session) |
| 5 | an established rejection maps to `required_flags_accepted=False` | driven end to end: frozen controller reports `required_launch_flags` / `REQUIRED_LAUNCH_FLAGS_REJECTED` |
| 6 | generic early exit is not a rejection | INDETERMINATE, plus the source-level outcome-constant check |
| 7 | deadline is not a rejection | INDETERMINATE |
| 8 | protocol violation before a correlated response is not a rejection | INDETERMINATE |
| 9 | output cap / event cap / read error are not rejections | INDETERMINATE |
| 10 | indeterminate paths keep truthful creator ownership | `resource_created=True`, `cleanup_attempted=True`, one `shutdown()` call, truthful `direct_child_reported_exit` including the unverified and raising cases; no runtime record registered |
| 11 | no raw stderr escapes | a stderr tail carrying an unknown-option line, a key-shaped string and a base URL is driven through the frozen controller; the serialized diagnostics + result contain none of it, and the only new exception names no runtime value |
| 12 | no semantic prompt path | no new function names a prompt; the module still sends only `get_commands`/`get_state` |

**On item 2, stated exactly.** ACCEPTED means "mechanical evidence
establishes that no unknown-option startup rejection occurred". The only such
evidence available in this phase is LF1's positive proof, whose runtime half
*is* the correlated RPC response. So ACCEPTED alongside a failed LF
correlation is **not constructible**, and that is the honest answer to the
brief's "if and only if": no other mechanically-justified proof of acceptance
exists here, and inventing one would be the fabrication FU1 exists to remove.

That is not the coupling the blocker named. The defect was the *reverse*
direction — LF correlation false FORCING required flags false — and that
direction is now broken in both of its outcomes (rows 4–9).

## 8. Required flags vs protocol integrity — independence

* **Behaviourally.** A launch-window protocol violation changes nothing about
  the flag classification: with a correlated response it is still ACCEPTED
  (and the violation still survives to `observe_protocol`, so one real
  observation set produces `required_launch_flags = PASSED` alongside
  `protocol_integrity = FAILED:PROTOCOL_VIOLATION_OBSERVED`); without one it
  is INDETERMINATE for exactly the reason it would have been with no
  violation at all.
* **At source level.** Neither `_protocol_violation_observed` nor
  `stdout_state` appears anywhere in the classification chain, and
  `required_flags_accepted` is now assigned from one thing only:
  `required_flag_state == REQUIRED_FLAGS_ACCEPTED`.

## 9. Second adversarial review — what was attacked, and the result

| Attack | Result |
|--------|--------|
| deadline called an unknown flag | refused — INDETERMINATE |
| protocol violation called an unknown flag | refused — INDETERMINATE |
| output cap called an unknown flag | refused — INDETERMINATE |
| event cap called an unknown flag | refused — INDETERMINATE |
| read error called an unknown flag | refused — INDETERMINATE |
| generic early exit called an unknown flag | refused — INDETERMINATE |
| truncated stderr accepted as proof | refused — `cap_exceeded`, `bytes_seen != bytes_retained`, and `bytes_retained > 4000` each fail closed |
| stderr read error accepted as proof | refused — `read_error is not None` fails closed |
| `stderr_snapshot()` raising | refused — INDETERMINATE, never REJECTED |
| `captured`/`cap_exceeded` reported by truthiness | refused — identity against the exact singletons |
| unknown-option diagnostic for an option NOT in AIDO's argv | refused — including a message that also names a real AIDO option |
| a `Warning:` unknown-option line | refused — only `Error:` reaches `process.exit(1)` |
| the message shape embedded mid-line | refused — the diagnostic shape is anchored |
| raw diagnostic leakage | refused — declared literals only, pinned by a whole-result JSON scan |
| required-flags and LF-correlation re-coupled | refused — one outcome, two classifications |
| required-flags and protocol-integrity re-coupled | refused — behavioural and source-level checks |

**One further defect was found and fixed during this sweep**, in the tests
rather than the module, and it is the same class of defect as LF1's own root
cause: the synthetic supervisor double had no `stderr_snapshot` at all. It is
now present **and pinned to the frozen AR2 source** — same keys, same
declared value types, `read_error` typed `str | None` exactly as
`BoundedStreamState.error` is, never a bool — so the double cannot silently
disagree with the real class the way LF1's `protocol_violation` double did.
The 4000-character `text_tail` bound is likewise asserted against
`PiRpcSupervisor.stderr_snapshot`'s own source.

## 10. Files changed

| File | Change |
|------|--------|
| `qualification/i2b_live_adapters.py` | three-state classification, the bounded startup diagnostic, the argv option-token walk, the fourth `LaunchDiagnostic` field, the INDETERMINATE launch-boundary mapping, three optional parameters on `_retain_and_close_partial_runtime`, corrected `RUNTIME_EXITED_EARLY` prose |
| `tests/test_i2b_live_adapters.py` | the FU1 section (pre-fix reproduction as a regression, independence tests 1–12, the adversarial sweep, the double/real conformance pin) plus the six existing tests whose expectations the correction changes |
| `tests/test_i2b_controller.py` | three regressions pinning the frozen shape FU1 maps onto — **controller source unmodified** |
| `run_i2b_live.py` | comment only: the stale claim that an unknown-flag rejection "reads `launch_correlation: no_response_runtime_exited_early`" is corrected, and the new `required_launch_flags` diagnostic field is described |
| `FINDINGS.md` | this section, plus explicit time scope on historical present-perfect status claims |
| `README.md` | explicit time scope on historical present-perfect status claims, plus the FU1 pointer |

Not modified: `qualification/i2b_controller.py`, `qualification/i2b_session.py`,
`qualification/i2b_workspace.py`, AR1, AR2, D1, O1, `src/`, `projects/`,
`CLAUDE.md`, the first live result artifact.

## 11. Offline validation

```text
experiments/pi_implementer_qualification    1258 passed, 0 failed
experiments/pi_external_runtime_ar2           298 passed, 0 failed
experiments/pi_external_runtime_ar1            96 passed, 0 failed
experiments/pi_external_runtime_ar2_o1         89 passed, 0 failed
root production tests (tests/)               3504 passed, 0 failed
```

Run separately, offline. No Candidate-A retry, no Candidate-B run, no real
Node/Pi launch, no broker or named pipe, no `/models` call, no credential
read, no semantic prompt, no real project workspace, no commit/push/PR.

## 12. What this does NOT establish

* It does **not** establish that any launch fact of the one retained live
  attempt was different from what that artifact records. That artifact is
  unedited, and FU1 re-ran nothing.
* It does **not** prove that a future indeterminate launch had no
  unknown-option rejection. INDETERMINATE means exactly what it says: the
  evidence did not establish acceptance **or** rejection. The bounded
  diagnostic makes no absence proof and none is claimed.
* It does **not** make `LF_JSONL_CORRELATION` or `PROTOCOL_INTEGRITY`
  reachable for a correlation-failing launch — it makes them unreachable,
  because no trustworthy session exists to observe them through. That is the
  intended fail-closed behaviour.
* The stderr diagnostic is a fact about the **currently installed** Pi
  source. It is not a guarantee about a future Pi build, and it introduces no
  version gate: the observed version remains provenance only, nothing in the
  new machinery reads or compares it.
* Nothing here weakens any standing scope claim: no fixer, no model-backed
  implementer, no second candidate, no semantic prompt path, no agent loop,
  no descendant/inference/GPU claim, no real-workspace authority, and
  redaction/scrubbing remain backstops, not guarantees.


---

# 5F3B-I2B-L1-LF2 — Credentialed B300 Route Observation + Route Failure Attribution Closure

**No live activity was performed in this phase.** Candidate A was not rerun,
Candidate B was not run, no real `/models` request was made, no real
credential was read, no Node/Pi process was launched, no broker was opened, no
semantic prompt was sent, no real project workspace was used, and neither
Candidate-A live result artifact was edited.

## 0. The live record LF2 is about

`results/i2b_live_A_20260831T224840Z.json` — Candidate A's second real
zero-prompt Category-B attempt — passed every runtime-side compatibility gate
(`broker_ready`, `runtime_launch`, `rpc_launch_shape`, `required_launch_flags`,
`lf_jsonl_correlation`, `get_commands`, `h1_extension_identity`,
`extension_command_namespace`, `get_state`, `h2_provider_model_identity`,
`protocol_integrity`, `pi_version_observed`) and then failed exactly one:

```text
failed_gate  = route_check
failure_code = ROUTE_CHECK_FAILED
exact_candidate_model_served = false
semantic_prompts_sent        = 0
```

All runtime teardown, broker shutdown, generated-config cleanup, outer cleanup
and evidence scrub verified. **The gate-level refusal is accepted:** the route
gate did not establish success, and refusing was correct.

## 1. Why that record cannot distinguish 401, transport failure, malformed listing and true absence

The live adapter passed the frozen AR2 checker directly:

```python
route_checker = ar2.route_check.check_route_serves_model
```

That function performs `GET <base_url>/models` through
`httpx.Client(trust_env=False)` and **sends no `Authorization` header**. Its
signature is exactly `(base_url, *, model_id)` — proven mechanically in
`test_lf2_the_frozen_ar2_checker_accepts_no_credential_parameter` — so it
**cannot express a credential at all**, and `run_offline_route_check` passes it
exactly two values, neither of them a credential
(`test_lf2_run_offline_route_check_cannot_forward_a_credential_to_a_checker`).

Its single `configured_model_served=False` is therefore produced identically by
seven distinct source facts, of which only one is about the model:

| Shape | Source fact | Actually about |
|---|---|---|
| A | transport unreachable | the network |
| B | HTTP 401 | **authentication** |
| C | HTTP 403 | **authorization** |
| D | another non-200 | the gateway |
| E | HTTP 200, malformed body | the response shape |
| F | HTTP 200, valid listing, candidate absent | **the model** |
| G | malformed checker result | the checker |

The frozen controller then reduces every one of them to a single
`ROUTE_CHECK_FAILED` with `exact_candidate_model_served=false`, retaining
nothing that says which. **Fail-closed and correct as a verdict; too coarse to
be read as an attribution.**

Consequently:

> `qwen3-coder-next` being absent from B300 is **NOT** established by the
> retained evidence. Candidate-A live #2 is a **VALID FAIL-CLOSED RUN** whose
> **route failure cause is UNDERDETERMINED**.

### 1.1 The reproduction (Objective 1)

`tests/test_i2_route.py` now drives the **real, unmodified**
`ar2.route_check.check_route_serves_model` through the **exact**
`run_offline_route_check` wiring the frozen controller uses, for shapes A–F,
and a synthetic non-conforming result for shape G. Still no network: the frozen
module's own module-level `httpx` reference is monkeypatched, for the duration
of one test, to a namespace whose `Client` is backed by an
`httpx.MockTransport`. The frozen module's source is never touched and the
attribute is restored afterwards.

Every shape yields `passed=False, configured_model_served=False`. A 401 and a
genuine absence agree even on the wiring's own bounded
`RouteFailureCode.MODEL_NOT_SERVED`, so not even that distinguishes them. The
mechanical cause is observed rather than asserted: the request the frozen
checker issues carries no `authorization` header.

This reproduction is deliberately **kept**, not deleted once the authenticated
checker exists — it is the proof of what the retained live artifact can and
cannot mean.

## 2. The credential/header contract (Objective 2), established offline

Established mechanically from two independent in-repository sources. No live
traffic, no credential read, no endpoint contacted.

1. **What credential Pi receives.** `qualification/i2_pi_config.py` writes
   `providers.b300_pi_qualification.apiKey = "$PI_QUALIFICATION_B300_ROUTE_KEY"`
   — `$ENV` interpolation, never a literal, never `!shell` — and the child
   environment carries that variable, whose value is the `AIDO_LITELLM_API_KEY`
   resolved by `qualification.i2_credentials.read_connection_values` alongside
   `AIDO_LITELLM_BASE_URL`.
2. **What header shape it produces.** The provider is declared
   `api: "openai-completions"`. I2A §5's provider table records that this api
   type **already sends** `Authorization: Bearer <key>` — precisely why
   `authHeader: true` is documented as unnecessary for it and is not emitted.
3. **Whether AIDO's existing B300 integration already uses that shape.**
   **Yes.** `src/ai_dev_orchestrator/llm/client.py` builds
   `{"Authorization": f"Bearer {api_key}"}` from `AIDO_LITELLM_API_KEY`, loaded
   beside `AIDO_LITELLM_BASE_URL` by `llm/config.py`. Same two variables, same
   value, same header.
4. **Whether `/models` uses the same authenticated route identity.** It is a
   path on the same OpenAI-compatible route named by `AIDO_LITELLM_BASE_URL`,
   reached under the same provider identity Pi is configured with. Observing it
   anonymously asks a *different* question than the one the run depends on.

**This is an expectation about which identity the request is made under. It is
NOT a claim that the endpoint enforces it.** I2A §24 item 1 — does the B300
proxy validate `Authorization` for this route — remains **unresolved**. LF2
does not answer it. A differential probe (one call with a good credential, one
with a bad one) would, and is **not authorized**: not designed, not
implemented, not performed.

## 3. Exact design text superseded (Objective 3)

A narrow superseding correction now exists at
`docs/PHASE_5F3B_I2B_L1_LF2_ROUTE_BOUNDARY_CORRECTION.md`. Historical I2A is
**not** rewritten. Two clauses are superseded, and nothing else:

* **I2A §15 item 9** ("…via the **unmodified**
  `ar2.route_check.check_route_serves_model` non-inference `/models` GET …
  reused exactly as 5F3B §15.2 specifies") is superseded by:

  > AR2's original route checker remains frozen and unmodified for AR2.
  > Category-B B300 qualification may not reuse it as the live checker when the
  > selected route is credential-bearing and the checker cannot express that
  > credential.

  The gate's *meaning* is unchanged: one non-inference `GET /models`, no
  prompt, no generation, no inference, never one of the four semantic prompts,
  exact case-sensitive matching, nothing substituted or auto-selected, and a
  failure means zero prompts.

* **I2A §23 slice I2-4**'s "wiring reuse of the unmodified
  `check_route_serves_model`" is superseded the same way. The
  credential-read-ordering half of that slice is **unchanged and still
  binding**.

Explicitly **not** superseded: I2A §16's two-path failure attribution, §8's
credential read ordering, §24 item 1's honesty, and the frozen controller's
`ROUTE_CHECK_FAILED` verdict code, gate ordering and `CategoryBEvidence`.

## 4. The authenticated checker, and its authority binding (Objectives 4, 6)

`qualification/i2_b300_route_observation.py` is new, qualification-owned, and
imports **nothing** from `ar2` — asserted by parsing its own AST, not its prose
(`test_this_module_does_not_reuse_the_frozen_ar2_checker`).
`experiments/pi_external_runtime_ar2/ar2/route_check.py` is **unmodified**, and
a test asserts it still sends no `Authorization` header and still accepts no
credential parameter.

`observe_b300_route_serves_model` performs **exactly one** non-inference
`GET <base_url>/models`, with `trust_env=False`, `follow_redirects=False`, a
bounded 20 s timeout, an `Authorization: Bearer <key>` header, no retry, no
fallback endpoint, no fallback model, strict bounded response-shape validation,
and exact case-sensitive `==` matching written as an explicit per-entry
equality loop (never set membership, never truthiness).

**Authority is not its arguments.** The live checker is
`qualification.i2b_live_adapters.AuthenticatedB300RouteObserver`, built by
`build_authenticated_route_checker(candidate=…, adapters=…)`:

| Value | Derived from |
|---|---|
| base URL | the `ConnectionValues` the frozen controller consumed via `adapters.read_connection()` **on this run** |
| credential | the same `ConnectionValues` |
| model id | `route_descriptor_for_candidate(candidate).model_id` — the frozen I1 pairing |
| provider | not a parameter anywhere |

There is **no** `base_url`, `api_key`, `endpoint`, `provider`, `provider_id`,
`model`, `model_id`, `secret_context` or `connection_values` parameter on
either the observer's constructor or its factory — asserted by signature
inspection. The arguments the frozen controller passes are treated as **claims
to be checked**:

* base URL not byte-identical to the consumed one → refused;
* model id not exactly the frozen pairing's id for this candidate → refused
  (this is what closes "Candidate B's route during a Candidate A run");
* case-folded model id → refused;
* non-string base URL or model id → refused;
* no consumed connection values yet → refused (ordering preserved);
* a second call → refused, so one run issues exactly one GET;
* anything that is not the real `LiveCategoryBAdapters` (including a
  `SimpleNamespace` forging `consumed_connection_values`) → refused at
  construction;
* an unknown candidate → refused at construction by the frozen descriptor.

Every refusal happens **before** any HTTP request (the recorder sees zero
requests in each case), records `route_authority_refused`, and is reduced by the
unmodified `run_offline_route_check` to its existing bounded
`ROUTE_CHECK_ERROR`.

`read_connection` additionally refuses a repeat read that resolves to
**different** values, so the recorded route authority cannot be quietly replaced
mid-run.

`qualification/i2b_live_adapters.py` no longer imports
`ar2.route_check.check_route_serves_model` **at all** — the import is deleted
rather than left unused, and the former `route_checker` module attribute is
gone, so there is no symbol a future edit could pass to the controller's
`route_checker` parameter again. Asserted by AST.

## 5. Bounded route diagnostic vocabulary (Objective 5)

Declared literals only, in `qualification/i2_b300_route_observation.py`:

```text
route_model_served            HTTP 200 + valid bounded listing + exact id present
route_transport_unreachable   no HTTP response at all
route_auth_rejected           HTTP 401 or 403 — an AUTH fact, never a model fact
route_http_rejected           any other non-200, including an unfollowed 3xx
route_listing_malformed       HTTP 200, body not a strict bounded listing
route_model_not_listed        HTTP 200 + valid bounded listing + exact id ABSENT
route_result_malformed        a checker RESULT object that did not conform
route_authority_refused       same-run authority failed; NO request was issued
route_not_observed            the route stage was never reached (the default)
```

`exact_candidate_model_served = true` requires **all three** of HTTP 200, a
valid bounded listing shape, and the exact case-sensitive candidate id. Success
is never inferred from HTTP 200 alone — the observation type refuses to
construct any other combination.

The harness records it as `route_diagnostics`, **alongside** the frozen
controller's result and never inside `CategoryBEvidence` — exactly the LF1
`launch_diagnostics` precedent. It is **attribution, not verdict authority**:
the frozen controller keeps a single `ROUTE_CHECK_FAILED` for every failure
shape, and gained no new failure code (asserted:
`{c for c in CategoryBFailureCode if c.value.startswith("ROUTE_CHECK")} ==
{ROUTE_CHECK_FAILED}`). No diagnostic code is a `CompatibilityFacts` field.

## 6. Redirect policy

**Redirects are disabled**, explicitly (`follow_redirects=False`), not inherited
from an httpx default a future version could change.

A credential-bearing request must never be moved to an authority this run never
approved: httpx re-sends the `Authorization` header across a same-origin
redirect, and a cross-origin redirect would either leak the credential or
silently change which endpoint answered the question. **No redirect target is
"proven to remain within the authorized origin", because none is followed at
all.** A 3xx is simply a non-200 and classifies as `route_http_rejected`;
tested for 301, 302, 303, 307 and 308, each issuing exactly one request whose
URL is the approved one. Nothing upgrades, rewrites, or tunnels the URL.

`trust_env=False` is likewise explicit — asserted mechanically on the real
client object (`client.trust_env is False`, `client.follow_redirects is False`),
not read out of a docstring.

## 7. Secret-retention proof

A finished observation carries **two exact bools and one declared code**.
`as_dict()` contains no `status_code`, no `served_model_ids`, no `failure`
prose, no host, no scheme, no base URL and no credential — and declares
`status_code_recorded`, `served_model_ids_recorded`, `response_body_recorded`,
`endpoint_host_recorded`, `base_url_recorded`, `credential_recorded` and
`redirects_followed` all `false`. AR2's checker retains a status code and the
served ids; this one deliberately does not, because this request carries a
credential.

Proven, not asserted:

* across served / absent / 401 / 500 / malformed / transport-failure paths,
  neither the synthetic key, `"Bearer"`, the synthetic host nor the synthetic
  base URL appears in `repr(observation)`, `as_dict()`, or the JSON-serialized
  record;
* a response body that deliberately embeds
  `Authorization: Bearer <synthetic key>` never reaches the observation;
* a transport exception whose **message** deliberately embeds the base URL and
  the credential never reaches the observation — the handler is `except
  Exception:` with no `as exc`, so no message, type name, or traceback is
  retained on that path;
* the observer's own refusal messages echo neither URL nor credential;
* `route_diagnostics()` output plus `repr(observer)` contain none of the
  needles;
* `ConnectionValues.__repr__` still redacts both fields, and the adapter's repr
  carries neither.

## 8. Route failure matrix

| Response / condition | Diagnostic | `configured_model_served` | Controller verdict |
|---|---|---|---|
| 200, listing contains exact id | `route_model_served` | `true` | **PASSED** |
| 200, listing lacks exact id | `route_model_not_listed` | `false` | `ROUTE_CHECK_FAILED` |
| 200, case-mismatched id | `route_model_not_listed` | `false` | `ROUTE_CHECK_FAILED` |
| 200, prefix/suffix/namespaced id | `route_model_not_listed` | `false` | `ROUTE_CHECK_FAILED` |
| 401 | `route_auth_rejected` | `false` | `ROUTE_CHECK_FAILED` |
| 403 | `route_auth_rejected` | `false` | `ROUTE_CHECK_FAILED` |
| 400/404/429/500/502/503 | `route_http_rejected` | `false` | `ROUTE_CHECK_FAILED` |
| 301/302/303/307/308 (not followed) | `route_http_rejected` | `false` | `ROUTE_CHECK_FAILED` |
| 200, unparseable JSON | `route_listing_malformed` | `false` | `ROUTE_CHECK_FAILED` |
| 200, non-object payload | `route_listing_malformed` | `false` | `ROUTE_CHECK_FAILED` |
| 200, `data` not a list | `route_listing_malformed` | `false` | `ROUTE_CHECK_FAILED` |
| 200, any malformed entry | `route_listing_malformed` | `false` | `ROUTE_CHECK_FAILED` |
| 200, over-size / over-count / over-long id | `route_listing_malformed` | `false` | `ROUTE_CHECK_FAILED` |
| transport exception / timeout | `route_transport_unreachable` | `false` | `ROUTE_CHECK_FAILED` |
| substituted base URL / model / candidate | `route_authority_refused` | — (no request) | `ROUTE_CHECK_FAILED` |
| observation before credential read | `route_authority_refused` | — (no request) | `ROUTE_CHECK_FAILED` |
| second observation attempt | `route_authority_refused` | — (no request) | `ROUTE_CHECK_FAILED` |
| non-conforming checker result | `route_result_malformed` | `false` | `ROUTE_CHECK_FAILED` |
| route stage never reached | `route_not_observed` | `false` | (an earlier gate's code) |

A 401 and a genuine absence still refuse **identically** at the controller —
which is correct — and are now **distinguishable afterwards**.

## 9. Second adversarial review

| Attack | Result |
|---|---|
| unauthenticated checker accidentally used in live wiring | **Closed.** Import deleted, module attribute gone, asserted by AST. |
| 401 interpreted as "model absent" | **Closed.** Distinct declared code; a 401 never parses a body. |
| malformed listing interpreted as "model absent" | **Closed.** Distinct declared code. |
| wrong-route successful listing accepted | **Closed.** Base URL must equal the consumed one; refused before any request. |
| wrong candidate id accepted | **Closed.** Must equal the frozen pairing's id for this candidate. |
| credential appears in repr/exception/result | **Closed.** No `as exc` anywhere; needle scans across every path. |
| ambient proxy influences the request | **Closed.** `trust_env=False`, asserted on the client object. |
| redirect changes route authority | **Closed.** `follow_redirects=False`; every 3xx refused, one request only. |
| automatic HTTP retry | **Closed.** Exactly one request on every path, asserted per shape. |
| response body retained | **Closed.** Body is parsed and discarded; ids never retained. |
| model-id case folding | **Closed.** Explicit `==` loop; four case variants tested. |
| success inferred merely from HTTP 200 | **Closed.** The observation type refuses `configured_model_served=True` without the `route_model_served` code. |
| forged secret/adapter object supplying authority | **Closed.** Only a real `LiveCategoryBAdapters` is accepted. |
| duplicate ids as a set-membership authority issue | **Closed.** Per-entry equality; duplicates harmless either way. |
| malformed entry manufacturing a match | **Closed.** Any malformed entry invalidates the whole listing. |

## 10. Files changed

```text
NEW  qualification/i2_b300_route_observation.py    the authenticated, bounded route observation
NEW  tests/test_i2_b300_route_observation.py       offline matrix items 1-19 (MockTransport only)
NEW  docs/PHASE_5F3B_I2B_L1_LF2_ROUTE_BOUNDARY_CORRECTION.md
                                                   the narrow superseding design correction
MOD  qualification/i2b_live_adapters.py            ar2.route_check import + route_checker attribute
                                                   REMOVED; read_connection records the consumed
                                                   values; AuthenticatedB300RouteObserver +
                                                   build_authenticated_route_checker added
MOD  run_i2b_live.py                               builds the bound observer; records the bounded
                                                   route_diagnostics alongside the result
MOD  tests/test_i2_route.py                        Objective 1 attribution-collapse reproduction
MOD  tests/test_i2b_live_adapters.py               observer authority/substitution/retention matrix;
                                                   the old "route_checker is the AR2 function" test
                                                   inverted
MOD  tests/test_i2b_controller.py                  tests-only route_checker override on _run;
                                                   matrix items 20-22
MOD  FINDINGS.md, README.md                        this record
```

**Not modified:** `ar2/route_check.py`, `i2b_controller.py`, `i2b_session.py`,
`i2b_workspace.py`, D1, AR1, AR2, O1, `src/`, `projects/`, `CLAUDE.md`, and
**either Candidate-A live result artifact**.

## 11. Offline regression counts

```text
experiments/pi_implementer_qualification    1420 passed, 0 failed   (was 1258)
experiments/pi_external_runtime_ar2           298 passed, 0 failed
experiments/pi_external_runtime_ar1            96 passed, 0 failed
experiments/pi_external_runtime_ar2_o1         89 passed, 0 failed
root production tests (tests/)               3504 passed, 0 failed
```

Run separately, offline.

## 12. No-live confirmation

No Candidate-A rerun, no Candidate-B run, no real `/models` request, no real
credential read, no Node/Pi launch, no broker or named pipe, no semantic
prompt, no Q1/Q2, no real project workspace, no commit/push/PR, no CLAUDE.md
edit. Every HTTP interaction in the suite is served by `httpx.MockTransport`;
no socket is opened and no API key is needed to run it.

## 13. What LF2 does NOT establish

* It does **not** establish that `qwen3-coder-next` is served by B300, or that
  it is not. LF2 makes the question *answerable next time*; it does not answer
  it retroactively.
* It does **not** establish that the B300 proxy validates the `Authorization`
  header. That remains I2A §24 item 1, open.
* It does **not** reinterpret the retained live artifact. That artifact is
  unedited, LF2 re-ran nothing, and its `ROUTE_CHECK_FAILED` continues to mean
  exactly what it meant: **the route gate did not establish success**.
* Recording `route_auth_rejected` says what AIDO **observed**, never why the
  server chose it — a proxy may answer 401 for reasons unrelated to the key.
* It does **not** qualify Candidate A, authorize a further live attempt,
  authorize Candidate B, authorize Q1/Q2, or grant real-workspace authority.
* Nothing here weakens any standing scope claim: no fixer, no model-backed
  implementer, no second reviewer, no agent loop, no fallback endpoint or
  model, no provider registry, no retry, no differential auth probe, and no
  descendant/inference/GPU claim. Redaction and scrubbing remain backstops,
  not guarantees.


---

# 5F3B-I2B-L1-LF2-FU1 — Independent Review: Public-Authority Blockers Closed

**No live activity was performed in this phase.** This is a documentation
record of an independent review completed outside this repository's own
tooling. No real `/models` request was made, no real credential was read, no
Node/Pi process was launched, no broker was opened, no semantic prompt was
sent, no real project workspace was used, and neither Candidate-A live result
artifact was edited. No implementation code changed as part of recording this
review.

## 0. What was reviewed

LF2's own "READY FOR FINAL FREEZE REVIEW" state (see the "5F3B-I2B-L1-LF2"
section above) against two public-authority blockers on the live route
checker introduced by that phase, `AuthenticatedB300RouteObserver` and its
factory `build_authenticated_route_checker` (`qualification/
i2b_live_adapters.py`).

## 1. Blocker 1 — transport/client/request injection surface

**Finding, now closed:** `AuthenticatedB300RouteObserver.__init__` and
`build_authenticated_route_checker` accept exactly two keyword parameters,
`candidate` and `adapters`. There is no `transport=`, `client=`, or
request-injection parameter anywhere on the class's public surface. A
caller cannot construct a genuine same-run observer while substituting an
`httpx.MockTransport` (or any other fabricated transport) that would
manufacture `HTTP 200` / model-present evidence without ever contacting
B300. Any `httpx.MockTransport` injection used by the offline test suite
exists strictly below this boundary — inside
`qualification.i2_b300_route_observation.observe_b300_route_serves_model`'s
own test doubles, never reachable from the live adapter's own constructor.

## 2. Blocker 2 — forged/subclassed authority object

**Finding, now closed:** `AuthenticatedB300RouteObserver.__init__` requires
`type(adapters) is LiveCategoryBAdapters` exactly — not `isinstance`. A
forged subclass of `LiveCategoryBAdapters` supplying attacker-controlled
`consumed_connection_values()` (or any other overridden method) is refused
before its authority or HTTP mechanism is ever consulted, because the type
check runs first and raises `LiveAdapterError` immediately.

## 3. What remains accepted, unchanged by this review

Strict malformed-listing handling, authenticated `Bearer` `/models`
observation, the bounded route diagnostic vocabulary (§5 of the LF2
section above), no redirects (`follow_redirects=False`), `trust_env=False`,
exactly one request per run with no retry and no fallback endpoint or model,
the frozen and unmodified `ar2.route_check` checker (still not reused for
Category-B), and the frozen `i2b_controller` state machine. None of these
were reopened or modified by this review.

## 4. Standing facts this review does not change

The retained live artifact `results/i2b_live_A_20260831T224840Z.json` is
unedited and its verdict is unchanged:

```text
VALID FAIL-CLOSED RUN / ROUTE FAILURE CAUSE UNDERDETERMINED
```

**Candidate A: NOT YET QUALIFIED.** This review does not qualify Candidate A,
does not authorize Candidate B, does not authorize Q1/Q2, and does not grant
real-workspace authority. It authorizes exactly what §5 below states, and
nothing more.

## 5. Verdict

```text
5F3B-I2B-L1-LF2-FU1: ACCEPT
5F3B-I2B-L1-LF2:     ACCEPT / FREEZE
```

Independent review authorizes exactly **one** further Candidate-A
Category-B zero-prompt live attempt (attempt #3), and only once this
documentation state is committed by the operator. It does not authorize
Candidate B, Q1/Q2, a differential auth probe, a second `/models` request per
attempt, any semantic prompt, or any real project workspace. Nothing here
weakens any standing scope claim: no fixer, no model-backed implementer, no
second reviewer, no agent loop, no fallback endpoint or model, no provider
registry, no retry beyond the one already-frozen single-request discipline,
and no descendant/inference/GPU claim. Redaction and scrubbing remain
backstops, not guarantees.


---

# 5F3B-I2B-L1 — Candidate A Category-B Live Attempt #3: ACCEPT / VALID PASS

**Exactly one live activity occurred in this phase: the single authorized
Candidate-A Category-B zero-prompt live attempt itself.** No Candidate B run,
no Q1/Q2 activity, no differential auth probe, no second `/models` request,
and no real project workspace. No implementation code changed as part of
this attempt or as part of recording this review.

## 0. The accepted live artifact

```text
results/i2b_live_A_20260901T174244Z.json
```

Retained unedited. This is Candidate A's third real zero-prompt Category-B
attempt, run under the authority `5F3B-I2B-L1-LF2-FU1` established (the
authenticated, same-run-bound B300 route observer with no public
transport-injection surface and an exact-type adapter check).

## 1. What the run established

```text
controller outcome            = CATEGORY_B_GATE_PASSED
failed_gate                   = null
failure_code                  = null
route_observation             = route_model_served
observation_requests_issued   = 1
observed_pi_version           = 0.84.4  (provenance only, never a gate)
semantic_prompts_sent         = 0
runtime_teardown_status       = SUCCEEDED
broker_shutdown_status        = CLOSED
generated_config_cleanup      = VERIFIED_REMOVED
outer_cleanup_verified        = true
evidence_retention_ready      = true
evidence_scrub_findings       = []
```

All 13 Category-B compatibility facts are `true`:
`broker_reached_required_ready_state`, `exact_candidate_model_served`,
`get_commands_response_shape_understood`,
`get_state_response_shape_understood`, `h1_extension_identity_matched`,
`h2_provider_model_identity_matched`, `lf_jsonl_correlation_succeeded`,
`no_extension_error_observed`, `no_protocol_violation_observed`,
`no_unexpected_extension_command_observed`, `pi_version_observed`,
`required_launch_flags_accepted`, `rpc_launch_shape_valid`.

Every gate in `gate_statuses` is `PASSED` (or its own terminal-success
literal: `broker_shutdown: CLOSED`, `generated_config_cleanup:
VERIFIED_REMOVED`, `runtime_teardown: SUCCEEDED`). No gate failed.

The route observation is the credential-bearing, same-run-bound observer
LF2/LF2-FU1 established (never the frozen, unauthenticated AR2 checker):
exactly one non-inference `GET /models`, HTTP 200, a valid bounded listing,
and the exact candidate id present — `route_model_served`, the only code in
the declared vocabulary (§5 of the LF2 section above) that permits
`exact_candidate_model_served = true`.

## 2. Verdict

```text
Candidate A Category-B live attempt #3:              ACCEPT / VALID PASS
Candidate A Category-B compatibility:                QUALIFIED / FROZEN
5F3B-I2B-L1 live compatibility path (Candidate A):    ACCEPT / FROZEN
```

## 3. Frozen claim scope — what this PASS does and does NOT establish

**This PASS qualifies Candidate A only for the Category-B runtime/route
compatibility boundary** — that a real Node/Pi process launches with AIDO's
argv, speaks the frozen RPC/LF-JSONL protocol correctly, presents the
expected extension and provider/model identity, and that the authenticated
B300 route serves the exact candidate model id. It is a compatibility result,
not a capability result.

It does **NOT** constitute:

* semantic implementer qualification (zero semantic prompts were sent; no
  candidate task was attempted, scored, or even offered);
* model-quality scoring of any kind;
* Q1/Q2 qualification (the first live candidate sweeps remain a wholly
  separate, unauthorized activity);
* an active-tool-registry observation (`get_commands` enumerates slash
  commands and proves extension identity/command provenance only — Pi
  exposes no RPC command that enumerates the active tool registry, and none
  was queried);
* real-workspace authority of any kind.

**Candidate A implementer qualification: remains NOT YET QUALIFIED.**
**Candidate B Category-B: remains NOT YET RUN.**
**Q1/Q2: remain NO-GO.**
**Real-workspace authority: remains NO-GO.**

Nothing here weakens any standing scope claim: no fixer, no model-backed
implementer, no second reviewer, no agent loop, no fallback endpoint or
model, no provider registry, no retry, no differential auth probe, and no
descendant/inference/GPU claim. Redaction and scrubbing remain backstops,
not guarantees.


---

# 5F3B-I2B-L2 — Candidate B Category-B Live Authorization (attempt not yet run)

**Paper-trail update only. No live activity of any kind occurred in this
phase.** No Candidate B run, no Candidate A rerun, no Q1/Q2 activity, no
differential auth probe, no real project workspace, no live network call, no
Pi/Node process, no broker, no credential read, and no `/models` request.
No implementation code changed.

## 0. What this records

Independent review of Candidate A Category-B live attempt #3
(`5F3B-I2B-L1`, §"Candidate A Category-B Live Attempt #3" above) is
complete, and that attempt's `ACCEPT / VALID PASS` verdict stands unchanged.
The existing offline controller and the live CLI already prove candidate
symmetry: Candidate A and Candidate B execute the identical
`run_one_category_b_live_attempt` controller path and the identical
Category-B compatibility policy, differing only by the frozen
candidate/model identity —

```text
Candidate A -> qwen3-coder-next
Candidate B -> minimax-m2.7
```

Independent review now authorizes **exactly one** future Candidate B
Category-B zero-prompt live attempt. This authorization is for Candidate B
(`minimax-m2.7`) only.

## 1. What is authorized

```text
Candidate B Category-B live attempt #1:   AUTHORIZED, exactly once, zero-prompt
```

## 2. What is explicitly NOT authorized

* a Candidate A rerun (Candidate A Category-B stays `QUALIFIED / FROZEN`,
  established by live attempt #3; no further Candidate A live attempt is
  authorized);
* a second Candidate B attempt (this authorization is for exactly one
  attempt);
* any semantic prompt (the authorized attempt remains zero-prompt, exactly
  as every prior Category-B attempt has been);
* 5F3B-Q1 / Q2 (the first live candidate sweeps remain a wholly separate,
  unauthorized activity);
* model scoring of any kind;
* real project workspace of any kind;
* a fallback model, provider, endpoint, or runtime;
* differential auth probing;
* code changes of any kind;
* automatic repair;
* commit, push, or PR.

## 3. Current state as of this authorization

```text
Candidate A Category-B compatibility:        QUALIFIED / FROZEN
Candidate A implementer qualification:       NOT YET QUALIFIED
Candidate B Category-B:                      NOT YET RUN (attempt #1 AUTHORIZED)
Candidate B implementer qualification:       NOT YET QUALIFIED
Q1/Q2:                                       NO-GO
Real-workspace authority:                    NO-GO
```

Nothing here weakens any standing scope claim: no fixer, no model-backed
implementer, no second reviewer, no agent loop, no fallback endpoint or
model, no provider registry, no retry beyond the one already-frozen
single-request discipline, no differential auth probe, and no
descendant/inference/GPU claim. Redaction and scrubbing remain backstops,
not guarantees.


---

# 5F3B-I2B-L1 — Candidate B Category-B Live Attempt #1: ACCEPT / VALID PASS

**Exactly one live activity occurred in this phase: the single authorized
Candidate-B Category-B zero-prompt live attempt itself.** No Candidate A
rerun, no second Candidate B attempt, no Q1/Q2 activity, no differential
auth probe, no extra `/models` request beyond the one frozen route
observation owned by the attempt, and no real project workspace. No
implementation code changed as part of this attempt or as part of recording
this review.

## 0. The accepted live artifact

```text
results/i2b_live_B_20260901T180415Z.json
```

Retained unedited. This is Candidate B's first, and only authorized,
zero-prompt Category-B attempt, run under the same identical
`run_one_category_b_live_attempt` controller path and authenticated route
observer that qualified Candidate A (`5F3B-I2B-L1-LF2-FU1`), differing only
by the frozen candidate/model identity (`minimax-m2.7`).

## 1. What the run established

```text
exact command                 = /c/dev/ai_dev_orchestrator/.venv/Scripts/python.exe \
                                     run_i2b_live.py --candidate B --run-category-b-live-gate
git HEAD (pre-run)             = 2e7c1cef562a57ab6e0c8a43b55a8dc167aa27ac
offline qualification result   = 1429 passed, 0 failed
live exit code                 = 0
controller outcome             = CATEGORY_B_GATE_PASSED
failed_gate                    = null
failure_code                   = null
route_observation              = route_model_served
observation_requests_issued    = 1
observed_pi_version             = 0.84.4  (provenance only, never a gate)
semantic_prompts_sent          = 0
runtime_teardown_status        = SUCCEEDED
broker_shutdown_status         = CLOSED
generated_config_cleanup       = VERIFIED_REMOVED
outer_cleanup_verified         = true
evidence_retention_ready       = true
evidence_scrub_findings        = []
```

All 13 Category-B compatibility facts are `true`:
`broker_reached_required_ready_state`, `exact_candidate_model_served`,
`get_commands_response_shape_understood`,
`get_state_response_shape_understood`, `h1_extension_identity_matched`,
`h2_provider_model_identity_matched`, `lf_jsonl_correlation_succeeded`,
`no_extension_error_observed`, `no_protocol_violation_observed`,
`no_unexpected_extension_command_observed`, `pi_version_observed`,
`required_launch_flags_accepted`, `rpc_launch_shape_valid`.

Every gate in `gate_statuses` is `PASSED` (or its own terminal-success
literal: `broker_shutdown: CLOSED`, `generated_config_cleanup:
VERIFIED_REMOVED`, `runtime_teardown: SUCCEEDED`). No gate failed.

The route observation is the credential-bearing, same-run-bound observer
LF2/LF2-FU1 established (never the frozen, unauthenticated AR2 checker):
exactly one non-inference `GET /models`, HTTP 200, a valid bounded listing,
and the exact candidate id (`minimax-m2.7`) present — `route_model_served`,
the only code in the declared vocabulary that permits
`exact_candidate_model_served = true`.

The run's own `claim_scope` text reiterates the standing bounds explicitly:
this is not a claim that a descendant process was terminated, that
Pi/provider inference stopped, or that GPU work stopped; `get_commands`
proves extension identity and command provenance only, never an active
tool-registry observation; and no semantic prompt was sent, so no candidate
model was scored.

## 2. Verdict

```text
Candidate B Category-B live attempt #1:               ACCEPT / VALID PASS
Candidate B Category-B compatibility:                 QUALIFIED / FROZEN
Candidate A Category-B compatibility:                 remains QUALIFIED / FROZEN
5F3B-I2B-L1 Category-B compatibility workstream:       COMPLETE / FROZEN for both first-round candidates
```

## 3. Frozen claim scope — what this PASS does and does NOT establish

**This PASS qualifies Candidate B only for the Category-B runtime/route
compatibility boundary** — that a real Node/Pi process launches with AIDO's
argv, speaks the frozen RPC/LF-JSONL protocol correctly, presents the
expected extension and provider/model identity, and that the authenticated
B300 route serves the exact candidate model id. It is a compatibility
result, not a capability result.

It does **NOT** constitute:

* semantic implementer qualification (zero semantic prompts were sent; no
  candidate task was attempted, scored, or even offered);
* model-quality scoring of any kind;
* Q1/Q2 qualification (the first live candidate sweeps remain a wholly
  separate, unauthorized activity);
* an active-tool-registry observation (`get_commands` enumerates slash
  commands and proves extension identity/command provenance only — Pi
  exposes no RPC command that enumerates the active tool registry, and none
  was queried);
* real-workspace authority of any kind.

## 4. Current state after this review

```text
Candidate A Category-B:                   QUALIFIED / FROZEN
Candidate B Category-B:                   QUALIFIED / FROZEN
Candidate A implementer qualification:    NOT YET QUALIFIED
Candidate B implementer qualification:    NOT YET QUALIFIED
Q1/Q2:                                    NOT YET EXECUTED
Real-workspace authority:                 NO-GO
```

Nothing here weakens any standing scope claim: no fixer, no model-backed
implementer, no second reviewer, no agent loop, no fallback endpoint or
model, no provider registry, no retry, no differential auth probe, and no
descendant/inference/GPU claim. Redaction and scrubbing remain backstops,
not guarantees. No further Category-B live attempt is authorized for either
candidate; this workstream is now COMPLETE / FROZEN.

---

# 5F3B-Q1-PRE1-DESIGN-FU1 — Semantic Dispatch Authority + Indeterminate Evidence Contract

**DESIGN / SOURCE INSPECTION ONLY. No code was written or modified in this
phase, and no live activity of any kind occurred** — no semantic prompt, no
Pi/Node launch, no credential read, no socket, no B300 contact, no Q1/Q2 run,
no candidate run, no commit/push/PR.

Full design: [`docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md`](../../docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md).

## 0. Why this exists

Independent review put `5F3B-Q1-PRE1` and `5F3B-Q1-PRE1-FU1` on **HOLD**. FU1's
three-state dispatch fact (`CONFIRMED_SENT` / `CONFIRMED_NOT_SENT` /
`SEND_STATE_INDETERMINATE`) was the right correction, but implementation had
crossed a boundary that was supposed to stop for review, and two properties of
it were never established against the real Pi seam.

## 1. The seam, established from Pi 0.84.4 source

The semantic task turn starts with exactly one RPC command,
`{"id": ..., "type": "prompt", "message": ...}`, written as one LF-terminated
JSON line. It **does** have an ordinary correlated response —
`{type:"response", command:"prompt", id, success:true|false}` — and
`dist/modes/rpc/rpc-mode.js` emits it from a `preflightResult` callback
**after** Pi accepts the prompt and **strictly before** `agent_start` and before
any provider inference. `agent_settled` has exactly one emission site
(`_runAgentPrompt`'s `finally`), and `agent_start` is emitted by both
`runAgentLoop` **and** `runAgentLoopContinue`, so it is not a prompt count.

A successful JSONL write/flush proves **local transport issuance only** — Pi
exposes no receipt between "AIDO flushed the bytes" and "Pi emitted a response",
and that gap is a real property of the seam, not a modelling gap to paper over.

## 2. Blocker 1 — dispatch authority is not separable in the FU1 architecture

FU1 embeds `SemanticPromptDispatchObservation` inside `SemanticTurnObservation`
and drives both from one adapter, so the send fact only exists if the whole turn
adapter returns normally. But `SemanticTurnObservation` admits only two terminal
shapes for a `CONFIRMED_SENT` dispatch (`agent_settled` xor `deadline_reached`),
while `PiRpcSupervisor._wait` genuinely returns `RUNTIME_PROTOCOL_VIOLATION`,
`RUNTIME_OUTPUT_CAP_EXCEEDED`, `RUNTIME_EVENT_CAP_EXCEEDED`,
`RUNTIME_READ_ERROR` and `RUNTIME_EXITED_EARLY` **after** a correlated
acknowledgement. A live adapter in that state must either fabricate
`deadline_reached` or raise — and raising reaches `_DispatchIndeterminate`,
which **erases an already-established `CONFIRMED_SENT` back to
`SEND_STATE_INDETERMINATE`**. The same erasure applies to a post-send teardown
or broker-shutdown failure.

The correction is a two-phase contract with a durable dispatch observation
recorded before the turn wait begins, a third turn outcome
(`OBSERVATION_FAILED`), a closed `dispatch_evidence_code` vocabulary, and a
write-once `semantic_prompts_sent`. Merely calling the dispatch function still
establishes nothing.

## 3. Blocker 2 — an indeterminate attempt currently leaves NO evidence

`run_semantic_task_attempt` sets `qualification_record = None` for an
indeterminate dispatch and writes **no file at all**. The one outcome in which
AIDO cannot prove whether the candidate's single authorized prompt was spent is
the one outcome that retains nothing.

Decisions: the frozen `pi-implementer-qualification.v1` schema is **not**
widened (`_validate_run_shape` admits only `semantic_prompts_sent in (0, 1)`,
and both shapes would be false statements). A separate attempt-level artifact,
`pi-implementer-qualification-attempt.v1`, is emitted through the **same**
`emit_evidence_or_refuse` choke point, omitting `semantic_prompts_sent`
entirely rather than encoding a sentinel. The artifact-emission-refusal record
must **not** be reused — it asserts a scrub failure that did not occur — and
lineage cannot link the attempt today, because `_require_run_record_shape`
demands a real run record; a narrow, separately-authorized lineage extension
(reason `indeterminate_semantic_dispatch`) is specified but not implemented.

An indeterminate send **consumes** the one-shot attempt (it is not a proven
zero), **no automatic retry is ever allowed**, replacement is operator-only
under §15.1, and the sweep **stops immediately** rather than spending further
one-shot attempts against uncharacterised infrastructure. A second counter,
`semantic_dispatch_attempts`, is required so the per-candidate budget cannot
permit a possible fourth prompt.

## 4. Counts kept distinct

`semantic_prompts_sent`, Pi provider inference requests, RPC command count and
model HTTP request count remain four different things. Frozen I2A §7.1/§19's
invariant — one semantic prompt may cause one or many provider requests, and
AIDO has no authoritative numeric observer for them — is preserved unchanged.

## 5. Verdicts

```text
5F3B-Q1-PRE1-DESIGN-FU1        HOLD  (pending FU1A review; was READY FOR INDEPENDENT REVIEW)
5F3B-Q1-PRE1-FU1               HOLD
5F3B-Q1-PRE1                   HOLD
Q1 / Q2                        NO-GO
Real-workspace authority       NO-GO
```

**`5F3B-Q1-PRE1-DESIGN-FU1A`** (design documentation only, not implemented)
found four gaps between the above and the actual `semantic_workspace.py` /
`semantic_controller.py` / `semantic_sweep.py` / `safety.py` /
`i2_secret_context.py` / `i2b_workspace.py` source: no semantic workspace
removal on any closure path (the frozen `i2b_workspace.remove_run_workspace`
exists but "the controller never calls it," verbatim from its own
docstring); an artifact-safety-context builder whose field-independence is
currently a fact about gate *order*, not a proven invariant of the function
itself; a final-report-collection failure that today routes through the same
gate-failure machinery as verification/repository observation and wrongly
drives an otherwise-valid, fully-closed run to `ATTRIBUTION_UNDETERMINED`
and unscorable; and mutable `dict`/`list` fields on
`SemanticTaskAttemptResult.gate_statuses`/`qualification_record` and
`PrimarySweepResult.task_results` that nothing prevents a caller from
mutating after validation, including after hard-bar evaluation. All four are
frozen as closure contracts in
[`docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md`](../../docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md)'s
§9, with an adversarial check in §10. Verdict: `5F3B-Q1-PRE1-DESIGN-FU1A:
READY FOR INDEPENDENT REVIEW`; `5F3B-Q1-PRE1-DESIGN-FU1: HOLD pending FU1A
review`. No live activity of any kind occurred in this turn either.

---

# 5F3B-Q1-PRE1-FU2 — Semantic Executor Design-Conformance Closure

**OFFLINE IMPLEMENTATION ONLY.** No candidate was run, no semantic prompt was
sent, no Pi/Node process was launched, no credential was read, no socket or
named pipe was opened, B300 was not contacted, Q1/Q2 were not run, no real
project workspace was used, and nothing was committed, pushed, or opened as a
PR. `CLAUDE.md` was not modified. No frozen I1/I2/I2B/AR1/AR2/O1 module was
modified — every frozen contract this phase needed was consumed through its
existing public surface.

This turn implemented the now-frozen
[`docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md`](../../docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md)
(DESIGN-FU1 + FU1A). None of its contracts was redesigned.

## 1. Two-phase semantic dispatch (§2)

`send_semantic_prompt(SemanticPromptRequest) -> SemanticTurnObservation` is
gone. In its place:

```text
PHASE 1  dispatch_semantic_prompt(SemanticPromptRequest)
           -> SemanticPromptDispatchObservation
                CONFIRMED_NOT_SENT | CONFIRMED_SENT | SEND_STATE_INDETERMINATE
                + a bounded SemanticDispatchEvidenceCode
              |
              v   semantic_prompts_sent fixed HERE, once, write-once
PHASE 2  observe_semantic_turn(SemanticTurnRequest)
           -> SemanticTurnObservation
                SETTLED | DEADLINE_REACHED | OBSERVATION_FAILED
                + the independent agent_end_observed fact
```

`SemanticTurnObservation` no longer carries a dispatch object or a
`call_succeeded` flag: there is no field through which a phase-2 outcome
could rewrite a phase-1 truth. `SemanticTurnRequest` refuses construction
from a non-`CONFIRMED_SENT` dispatch, so phase 2 is unreachable without the
send fact both structurally and by control flow.

`OBSERVATION_FAILED` is the third terminal state FU1's two-boolean shape
denied. Every reachable post-acknowledgement failure — protocol violation,
output cap, event cap, read error, early child exit, a raised or wrong-typed
or foreign phase-2 result — now lands there, and `semantic_prompts_sent`
stays `1`. Under FU1 those shapes could only fabricate `deadline_reached` or
raise, and raising reached `_DispatchIndeterminate`, converting a **known
spent** prompt into an **unknown** one.

`_DispatchIndeterminate` is now raised from inside the phase-1 block and
nowhere else — the mechanical half of invariant I-1.

The ten `SemanticDispatchEvidenceCode` members map to exactly one dispatch
state each through one read-only `DISPATCH_EVIDENCE_CODE_STATES` proxy, and a
forged pairing is refused at construction. The code is audit-only; nothing
branches on it.

## 2. The indeterminate-attempt artifact (§3)

`pi-implementer-qualification.v1` is **not widened**. A new sibling module,
`qualification/semantic_attempt.py`, builds
`pi-implementer-qualification-attempt.v1` and emits it through the same
`safety.emit_evidence_or_refuse` choke point. It **omits
`semantic_prompts_sent` entirely** — proved recursively before the payload is
returned — and carries `semantic_prompts_sent_established: false`,
`attempt_consumed: true`, the bounded evidence code, the identity/compatibility
facts, the raw closure facts (including workspace removal), the explicit
scoped negatives, and a fixed `claim_scope`.

The artifact-emission-refusal record's *meaning* is not reused; the shared
choke point is. If the attempt artifact itself fails the scrub, the existing
bounded refusal record stands in its place, exactly as for a primary record.

Rule now enforced: **every invoked attempt leaves exactly one immutable
retained artifact — never zero, never both.**

The separately-deferred lineage extension (§3.I) was **not** implemented.

## 3. Sweep stop policy and count ownership (§3.J, §4)

The primary sweep stops immediately on the first indeterminate dispatch.
Later tasks are never invoked — `build_adapters` is not even called for them —
and appear in `not_attempted_task_ids` with no artifact. The two counts are
distinct and both validated:

- `confirmed_semantic_prompts_sent` (FU1's `total_semantic_prompts_sent`,
  **renamed, not aliased**, because the old name reads as though the actual
  number of accepted prompts were known);
- `semantic_dispatch_attempts` — how many times phase 1 was entered. **This
  is the budget the sweep enforces.**

## 4. Semantic workspace ownership and verified removal (§9.1)

The frozen closure order is now declared by `CLOSURE_GATES` and executed in
that order: runtime teardown → broker shutdown → generated-config cleanup →
**semantic workspace removal + verification** → evidence construction / scrub
/ emission. `remove_run_workspace` is called exactly once on every terminal
path after a successful mint; before FU2 the controller never called it at
all, so every attempt left its disposable Git fixture tree on disk
indefinitely.

Acceptance is the strict frozen predicate `run_i2b_live._workspace_removal_succeeded`
already applies — identity `is True`, `type(x) is int`, `== 0`, no
truthiness, no absence-of-exception shortcut. A raised removal is
`attempted=True, verified=False`, reported and never allowed to skip evidence
construction. An unverified removal folds into `closure_established` exactly
as teardown/shutdown/config-cleanup already do, and under an indeterminate
dispatch it records the same honest unavailable-classification reason rather
than a fabricated 0/1 classification.

## 5. Full artifact safety context (§9.2)

`build_run_safety_context` is now field-independent: the workspace needle is
declared whenever a workspace exists, the broker needles whenever a broker
session exists, and the endpoint/key whenever a secret context exists — no
field's absence gates another field's source object. The previously-unused
`route_descriptor` parameter now has its job: the credential mechanism is
asserted, and an unexpected one **refuses** construction rather than silently
defaulting `bearer_token`. `none_declared()` is returned only for the true
all-absent case. One context per attempt protects the primary record, the
attempt artifact and the refusal fallback alike.

## 6. The final assistant report is optional and untrusted (§9.3)

`FINAL_REPORT_CLAIMS` no longer routes through `_GateFailure`. It produces a
closed `ReportAvailability` (`AVAILABLE` / `UNAVAILABLE` / `MALFORMED`, or
`None` when collection was never reached), which cannot set `failed_gate`,
cannot reach `attribute_protocol_anomaly`, and therefore can no longer turn a
fully-verified, fully-closed run into `ATTRIBUTION_UNDETERMINED`. The bounded
failure code `FINAL_REPORT_CLAIMS_COLLECTION_FAILED` was **removed**, so the
seam it would be re-wired through no longer exists. An available report is
still compared conservatively; a contradiction remains a report-accuracy
finding only. No retry is triggered by a bad or missing report.

## 7. Deep immutability (§9.4)

`SemanticTaskAttemptResult.gate_statuses`, both record projections, and
`PrimarySweepResult.task_results` are read-only proxies over private,
recursively-immutable **copies** — copy before wrapping, since a proxy over a
caller-held dict stays a live view of it. Nested `findings` lists become
tuples. A new narrow frozen `EvidenceEmission` is what the hard bar's
`artifact_scrub_passed` reads, and the result cross-checks it against the
projection it describes. `report_accuracy_comparisons` is type-checked as a
tuple of `ClaimComparison`.

## 8. Verdicts

```text
5F3B-Q1-PRE1-FU2               COMPLETE (offline; awaiting independent review)
5F3B-Q1-PRE1                   HOLD pending independent FU2 review
Q1                             NO-GO
Q2                             NO-GO
Real-workspace authority       NO-GO
```

**NO SEMANTIC PROMPT HAS EVER BEEN SENT.** No candidate implementer PASS/FAIL
exists. Candidate A and Candidate B remain Category-B **compatibility**
qualified/frozen only.

## 9. One stale statement left deliberately uncorrected

`qualification/i2b_workspace.remove_run_workspace`'s docstring still says
*"This is a fixture/teardown convenience for the offline suite; the
controller never calls it."* As of FU2 the controller **does** call it. The
module is frozen and this phase is instructed not to modify frozen modules,
and DESIGN-FU1 §9.1.1 quotes that exact sentence as the gap it closes, so it
was left byte-identical. It is flagged here so independent review can
authorize the one-line correction.

## 10. Offline validation

Run separately, offline. No live run followed.

```text
pi_implementer_qualification   1628 passed   (1526 before FU2; +102 new cases)
pi_external_runtime_ar2         298 passed
pi_external_runtime_ar1          96 passed
pi_external_runtime_ar2_o1       89 passed
root production tests          3504 passed
```

New regression cases, by file:

```text
tests/test_semantic_fu2.py         93   (new file)
tests/test_semantic_session.py     +5   (13 -> 18)
tests/test_semantic_sweep.py       +4   (12 -> 16)
tests/test_semantic_controller.py  +-0  (68 -> 68; several rewritten in place)
                                  ----
                                   102
```

---

# 5F3B-Q1-PRE1 — ACCEPT / FREEZE

**Status record only. No live activity.** Independent review **ACCEPTED and
FROZE `5F3B-Q1-PRE1`**, superseding the `HOLD` verdicts recorded above.

Final offline validation as recorded at acceptance (superseding the FU2-turn
counts above):

```text
pi_implementer_qualification   1751 passed
pi_external_runtime_ar1           96 passed
pi_external_runtime_ar2          298 passed
pi_external_runtime_ar2_o1        89 passed

root tests                      3503 passed
                                   1 known environment-specific failure
```

The single root failure is
`tests/test_writer_execution_isolation.py::test_no_project_verification_command_runs_after_the_refactor`,
on a machine where Git resolves under `C:\Program Files\Git\cmd\git.exe`. It is
unrelated to this package and is **not** fixed by the acceptance turn or the
roadmap turn that recorded it. **The root suite is not fully passing and must
not be described as such.**

## Standing authority after acceptance

```text
5F3B-Q1-PRE1                ACCEPTED / FROZEN
Q1                          NO-GO   (until separately authorized)
Q2                          NO-GO   (until separately authorized)
Real-workspace authority    NO-GO
```

Acceptance authorizes the **infrastructure** for a live semantic attempt; it
does **not** authorize the attempt. **NO SEMANTIC PROMPT HAS EVER BEEN SENT.**
No candidate implementer PASS/FAIL exists. Candidate A and Candidate B remain
Category-B **compatibility** qualified/frozen only.

## Where this sits in AIDO's sequencing

Recorded in
[`docs/AIDO_RUNTIME_HARNESS_ROADMAP.md`](../../docs/AIDO_RUNTIME_HARNESS_ROADMAP.md):
the four independent axes (role / harness / model / backend), the qualification
identity tuple `(harness, harness_version, model, backend,
qualification_policy_revision)`, Pi's status as AIDO's **first** implementer
harness candidate and **not** a permanent architectural dependency, the M1–M11
multi-harness sequence (PRE1 is **M2**, complete/frozen; live Q1/Q2 is **M3**),
and the AIDO v1 / v2 product milestones. PRE1, Q1 and Q2 stay **Pi-specific**;
the generic harness contract is extracted only after real Q1/Q2 experience
(**M7**), and neither M7 nor a second harness (**M8**) is a prerequisite for
AIDO v1. That document is roadmap documentation and authorizes nothing.
