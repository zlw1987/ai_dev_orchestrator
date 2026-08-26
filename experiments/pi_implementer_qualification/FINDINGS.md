# 5F3B-I1 / I2 Findings

> **I1 + I2 OFFLINE MACHINERY ONLY. NO ZERO-PROMPT LIVE GATE HAS RUN. NO
> MODEL QUALIFICATION HAS OCCURRED. Q1/Q2 REMAIN UNAUTHORIZED.**

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

> **I2 OFFLINE IMPLEMENTATION ONLY. NO ZERO-PROMPT LIVE GATE HAS RUN. NO
> CANDIDATE MODEL HAS RUN. Q1/Q2 REMAIN UNAUTHORIZED.**

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

- No zero-prompt live gate (I2A Sec. 15: Node-direct launch, RPC broker
  reaching `READY`, H1/H2, `get_commands`/`get_state`, the real `/models`
  listing) has ever run.
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

> **STILL OFFLINE ONLY. NO ZERO-PROMPT LIVE GATE HAS RUN. NO CANDIDATE MODEL
> HAS RUN. Q1/Q2 REMAIN UNAUTHORIZED.**

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

- No zero-prompt live gate has ever run. No candidate model has ever run.
  No PASS/FAIL, no ranking, no qualification verdict exists for Candidate A
  or Candidate B.
- 5F3B-Q1/Q2 remain **NOT authorized**.
- Redaction/scrubbing remain **backstops, not guarantees**.

---

# 5F3B-I2-FU2 -- Authority + Trusted-Value Closure

> **STILL OFFLINE ONLY. NO ZERO-PROMPT LIVE GATE HAS RUN. NO CANDIDATE MODEL
> HAS RUN. Q1/Q2 REMAIN UNAUTHORIZED.**

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

- No zero-prompt live gate has ever run. No candidate model has ever run.
  No PASS/FAIL, no ranking, no qualification verdict exists for Candidate A
  or Candidate B.
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

> **STILL OFFLINE ONLY. NO ZERO-PROMPT LIVE GATE HAS RUN. NO CANDIDATE MODEL
> HAS RUN. Q1/Q2 REMAIN UNAUTHORIZED.**

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

- No zero-prompt live gate has ever run. No candidate model has ever run.
  No PASS/FAIL, no ranking, no qualification verdict exists for Candidate A
  or Candidate B.
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

- No zero-prompt live gate has ever run. No candidate model has ever run.
  No PASS/FAIL, no ranking, no qualification verdict exists for Candidate A
  or Candidate B.
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

- No zero-prompt live gate has ever run. No candidate model has ever run.
  No PASS/FAIL, no ranking, no qualification verdict exists for Candidate A
  or Candidate B.
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
