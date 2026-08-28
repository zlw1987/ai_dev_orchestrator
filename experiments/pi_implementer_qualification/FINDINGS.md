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

---

# 5F3B-I2B / I2B-FU1 -- Category-B Runtime Authority + Lifecycle Closure (Offline Only)

> **I2B CONTROLLER WIRED OFFLINE. CATEGORY-B LIVE EXECUTION NOT RUN. NO
> CANDIDATE MODEL RUN. Q1/Q2 NO-GO.**

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

- No zero-prompt live gate has ever run. No Pi/Node process was launched, no
  RPC call was made, no broker was created, no socket was opened, no
  `/models` request was issued, and no real credential was read. Every live
  boundary is an injected adapter this package supplies no real
  implementation for, and **no real live adapter was added by this phase**.
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

> **OFFLINE IMPLEMENTATION ONLY. CATEGORY-B LIVE EXECUTION NOT RUN. NO
> CANDIDATE MODEL RUN. NO REAL WORKSPACE. Q1/Q2 NO-GO.**

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

- **No zero-prompt live gate has ever run.** No Pi/Node process was launched,
  no RPC call was made, no broker was created, no socket was opened, no
  `/models` request was issued, and no real credential was read.
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

Unchanged from FU2/FU2A/FU2B's own closing sections: no zero-prompt live
gate has ever run; `get_commands` still proves nothing about the active
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

Unchanged from FU2/FU2A/FU2B/FU2C: no zero-prompt live gate has ever run;
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

Unchanged from FU2/FU2A/FU2B/FU2C/FU2D/FU2E: no zero-prompt live gate has
ever run; `get_commands` still proves nothing about the active tool
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
