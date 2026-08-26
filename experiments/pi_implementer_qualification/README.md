# Phase 5F3B-I1 / I2 -- Pi Implementer Qualification Corpus + Offline Harness

> **OFFLINE QUALIFICATION HARNESS ONLY.**
> **NO MODEL QUALIFICATION HAS OCCURRED.**
> **NO CANDIDATE PASS/FAIL EXISTS YET.**
> **NO ZERO-PROMPT LIVE GATE HAS RUN.**
> **5F3B-Q1 / Q2 ARE NOT AUTHORIZED.**

**5F3B-I2 (route/credential offline machinery, slices I2-1 through I2-5) is
now implemented, fully offline, per
[`docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md`](../../docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md).**
This establishes that the future live qualification route CAN be constructed
safely -- it does NOT authorize using it. No Pi/Node process has ever been
launched from this package, no HTTP/socket call has ever been made, no real
`AIDO_LITELLM_*` value has ever been read, and no candidate model has ever
been run.

**EXPERIMENT ONLY.** Not production code. Not a CLI command. Lives outside
`src/`, adds no `ProjectConfig` field, and this whole directory may be
deleted as one unit without touching anything else in the repository.

## What this is

The binding design is
[`docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`](../../docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md).
This package implements exactly its Section 24 slice **5F3B-I1**: the frozen
IQ-1/IQ-2/IQ-3 synthetic task corpus, baseline contract validation, the
autonomous outcome classifier, the run-validity model, refusal attribution
and scope metrics, a conservative report-accuracy comparator, the hard
qualification bar, categorical ranking, a versioned record schema with a
fail-closed safe-emission choke point, and immutable invalidation/
replacement lineage evidence.

**This is fully offline.** No Pi process is launched, no model is called, no
socket or HTTP request is opened, no credential is read, and no B300/vLLM/
LiteLLM route is touched. Every "model run" the test suite classifies is a
plain Python fact structure (`RunFacts`, `RefusalEvent`, `ReportClaims`, ...)
fed directly to a pure policy function. The only subprocess activity is
local: `git` (fixture construction/inspection) and `python -m pytest`
(running each fixture's own fixed verification command against itself).

## Why this exists

5F3B-I1 makes the future Q1/Q2 one-shot live evidence *interpretable before
either candidate model is run*: a green offline suite here means a live
`AUTONOMOUS_FAIL` in a later round is a **model fact**, not a harness
defect. Building the corpus and the classifier first, and proving them
correct against synthetic evidence, is exactly what the accepted O1
offline-suite-before-live-run precedent already established.

## What I2 adds (offline only)

Per `docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md` Section
23's slices I2-1 through I2-5:

- **I2-1** (`qualification/i2_environment.py`) -- the qualification-owned
  positive-allowlist child-environment builder: Windows baseline names,
  narrowed `PATH`, Pi-owned `PI_*` variables, and exactly ONE credential
  carrier (`PI_QUALIFICATION_B300_ROUTE_KEY`). No profile names, no keyless
  placeholder. Also `qualification/i2_secret_context.py`, the run-scoped
  secret context whose secret-bearing fields cannot leak through `repr()`.
- **I2-2** (`qualification/i2_pi_config.py`) -- the disposable
  `settings.json` (`maxRetries: 0`) + `models.json` (`apiKey:
  "$PI_QUALIFICATION_B300_ROUTE_KEY"`, `maxTokens` omitted) generator.
  **Since 5F3B-I2-FU1, `write_qualification_pi_config` takes only
  `model_id`/`base_url`** -- the provider id and the credential carrier are
  fixed internal constants, not caller-supplied parameters, so an arbitrary
  provider (`"openai"`) or credential carrier (`OPENAI_API_KEY`) cannot be
  requested through this API at all, and `model_id` is validated against
  the frozen candidate pairing before any file is written.
- **I2-3** (`qualification/i2_route.py`) -- route descriptors for Candidate A
  (`qwen3-coder-next`) / Candidate B (`minimax-m2.7`), always
  `b300_litellm_proxy`, never direct vLLM, plus the offline-only,
  dependency-injected wiring shape for the future `check_route_serves_model`
  zero-prompt gate.
- **I2-4** (`qualification/i2_credentials.py`) -- the credential-read-ordering
  contract: non-secret gates must ALL pass before the injected connection
  reader is ever called, proven with a call-counting double, never a real
  environment read.
- **I2-5** (`qualification/i2_cleanup.py`) -- generated-config teardown
  verified by `stat`, the phase-aware cleanup-failure classification
  (`semantic_prompts_sent == 0` -> `INFRASTRUCTURE_REFUSAL`;
  `== 1` -> `INFRASTRUCTURE_CONTAMINATED` / `scoring_eligible = False`), and
  the pre-persistence raw-diagnostic safety boundary that reuses I1's
  existing scrub primitive rather than a second secret scanner.
- **I2-6** (`qualification/i2_issuance.py`, 5F3B-I2-FU3A, encapsulated in
  FU3B) -- the process-local, in-memory-only registry that proves a
  disposable config's authority token was genuinely issued by this package,
  for that exact directory, in this process -- closing the gap where a
  caller-forged token with a correctly-computed FU3 marker could still
  authorize construction/cleanup. Also backs the cleanup-authority-vs-
  complete-content-integrity split
  (`i2_pi_config.verify_cleanup_authority` / `verify_generated_config_integrity`)
  that every launch-capable consumption path (`build_child_environment`,
  `describe_generated_config`, `verify_i2_identity_binding`) now requires.
  **Since 5F3B-I2-FU3B, every registry function is package-internal
  (underscore-prefixed)** -- only `i2_pi_config`/`i2_cleanup` call it; there
  is no public `register_issuance`/`finalize_issuance`/`discard_issuance`/
  `lookup_issuance` anywhere. Its `IssuanceRecord` is frozen and repr-safe,
  and finalization is one-shot (a second finalization for an already-
  finalized token is refused, never silently overwriting a trusted digest).

## What I2B adds (offline wiring only)

**I2B CONTROLLER WIRED OFFLINE. CATEGORY-B LIVE EXECUTION NOT RUN. NO
CANDIDATE MODEL RUN. Q1/Q2 NO-GO.**

`qualification/i2b_controller.py` implements the state-machine / orchestration
SHAPE for the future Category-B zero-prompt live gates (I2A Sec. 15) -- it
does not run any of them. Every future live boundary (Node-direct RPC launch,
H1, `get_commands`, `get_state`, the B300 `/models` route check, broker
`READY`, teardown) is represented ONLY as an injected callable; every offline
test supplies a synthetic double for each, never a real subprocess, socket,
or model call. The controller:

- consumes I2's already-accepted, frozen offline objects
  (`ConnectionValues`, `QualificationRouteSecretContext`,
  `GeneratedQualificationConfig`, `RouteDescriptor`, `LaunchEnvironment`) and
  their cross-object binding (`i2_composition.verify_i2_identity_binding`)
  UNCHANGED -- no new raw `api_key`/config-path/provider-id/model-id
  parameter is introduced anywhere;
- reuses `i2_credentials.resolve_connection_after_preflight` unmodified for
  the credential-read-ordering proof: the injected connection reader is
  never called until every non-secret gate has passed;
- reuses `i2_route.run_offline_route_check` unmodified for the future
  `/models` exact-model-served gate;
- reuses `i2_cleanup.scrub_generated_qualification_config` and
  `classify_cleanup_failure(semantic_prompts_sent=0)` unmodified for
  generated-config teardown -- the only prompt count this controller can
  ever supply, since Category-B never sends one;
- attributes every possible failure to a bounded `INFRASTRUCTURE_REFUSAL`
  with `semantic_prompts_sent == 0` -- never `AUTONOMOUS_FAIL`, never a
  candidate classification, never a scoring result. It imports no
  candidate-scoring machinery (`outcomes`, `hard_bar`, `ranking`, or
  `records`'s record builder) at all;
- always attempts teardown once a live resource creation was attempted, and
  always attempts generated-config cleanup once the disposable config was
  created, on every path -- a later failure or the fully-passed case alike;
- builds a bounded, credential-free Category-B evidence shape (candidate,
  model/provider/gateway identity, `observed_pi_version` as provenance only,
  per-gate statuses, the fixed token-policy fields, teardown/cleanup status)
  and scrub-checks it through the existing `safety.qualification_scrub_check`
  with an explicit `ArtifactSafetyContext` before calling it retention-ready
  -- it does not write anything to disk.

Candidate A and Candidate B run through the identical controller function,
differing only in the `candidate` argument. 32 new, fully offline tests
(`tests/test_i2b_controller.py`) prove gate ordering, the credential-read
boundary, every individual gate refusal (H1, H2, tool registry, route
unavailable, wrong served model, broker-not-ready, protocol/extension error,
an unexpected exception), teardown/cleanup truthful attribution, evidence
safety, and -- by source-level regression test -- that no semantic-prompt API
and no live/network/process primitive exists anywhere in this module.

## What is explicitly NOT here

Per the design's Section 24/23 roadmaps:

- Any live Pi/Node process launch, RPC broker, or compatibility handshake --
  including via `i2b_controller.py`, whose every live boundary is an
  injected callable this package never supplies a real implementation for.
- Any real credential value read, anywhere, at any point.
- A live qualification executor -- nothing here can run a candidate model.
- Any model comparison result. The Section 26 comparison table in the design
  document is deliberately unfilled, and nothing in this package fills it.
- A reviewer, real workspace authority, automatic continuation, or a
  production stall circuit breaker.
- A generic `AgentRuntime` / multi-runtime abstraction (stays deferred).

## Package layout

```text
experiments/pi_implementer_qualification/
    README.md                  this file
    FINDINGS.md                offline harness facts only; no candidate results
    .gitignore
    qualification/
        __init__.py            package identity, version constants
        corpus.py               IQ-1 / IQ-2 / IQ-3 frozen fixtures + task contracts
        fixtures.py              build/teardown + baseline contract validation
        outcomes.py              Sec. 8 / Sec. 11 autonomous outcome classifier
        validity.py              Sec. 17.3 run-validity / scoring-eligibility model
        scope.py                 Sec. 17 refusal attribution + QD-2 scope metrics
        report_accuracy.py       QD-4 conservative report-accuracy comparator
        hard_bar.py              Sec. 16 hard qualification bar (H-1..H-14)
        ranking.py               Sec. 18 categorical ranking (R-1..R-4)
        safety.py                THE evidence safety + exclusive-create emission choke point
        records.py               pi-implementer-qualification.v1 schema + invariant gate
        lineage.py               Sec. 13/26 immutable invalidation/replacement evidence
        i2_environment.py        I2-1 child-environment builder (offline)
        i2_secret_context.py     I2-1 run-scoped secret context (repr-safe, no evidence helper)
        i2_pi_config.py          I2-2 disposable settings.json/models.json generator (offline)
        i2_route.py              I2-3 route descriptors + offline route-check wiring
        i2_credentials.py        I2-4 credential read ordering + connection contract (offline)
        i2_cleanup.py            I2-5 cleanup, phase-aware failure classification, diagnostic safety
        i2_identity.py           5F3B-I2-FU3: the leaf module for CREDENTIAL_ENV_VAR_NAME/PROVIDER_ID
        i2_composition.py        5F3B-I2-FU3: config/secret/route identity binding
        i2_issuance.py           5F3B-I2-FU3A/FU3B: the leaf module for the process-local issuance registry (internal-only API)
        i2b_controller.py        5F3B-I2B: the Category-B zero-prompt live-gate controller (offline wiring only)
    tests/
        conftest.py              sys.path wiring, git_executable fixture, thread-leak check
        test_iq1_fixture.py      IQ-1 fixture, baseline, correct-repair proof
        test_iq2_fixture.py      IQ-2 fixture, two-file necessity proof
        test_iq3_fixture.py      IQ-3 fixture, no-change proof
        test_baselines.py        baseline contract validation, synthetic outcomes
        test_task_revision.py    frozen task-revision identity (incl. baseline contract)
        test_outcomes.py         autonomous outcome classifier
        test_run_validity.py     run-validity / scoring-eligibility
        test_scope.py            refusal attribution + scope metrics
        test_report_accuracy.py  QD-4 comparator
        test_hard_bar.py         hard qualification bar
        test_ranking.py          categorical ranking
        test_records.py          record invariant gate + safe/exclusive-create emission
        test_lineage.py          immutable invalidation/replacement lineage
        test_i2_environment.py   I2-1 child-environment builder
        test_i2_secret_context.py I2-1 run-scoped secret context safety
        test_i2_pi_config.py     I2-2 disposable config generator
        test_i2_route.py         I2-3 route descriptors + offline route-check wiring
        test_i2_credentials.py   I2-4 credential read ordering
        test_i2_cleanup.py       I2-5 cleanup, classification, diagnostic safety
        test_safety_repr.py      5F3B-I2-FU1: ArtifactSafetyContext repr-safety proof
        test_i2_composition.py   5F3B-I2-FU3: config/secret/route identity binding
        test_i2_issuance.py      5F3B-I2-FU3A/FU3B: process-local issuance registry contract (white-boxes internal-only API)
        test_i2b_controller.py   5F3B-I2B: Category-B controller state-machine/gate-ordering/teardown/evidence (offline doubles only)
```

**All qualification evidence is written by exactly one function**
(`safety.write_evidence_exclusively`, `O_CREAT | O_EXCL`), through one
fail-closed choke point that requires an explicit `ArtifactSafetyContext`.
There is deliberately no overwrite, append, or force variant anywhere in the
package, and two source-level regression tests enforce that.

## Reuse, not duplication

This package deliberately does **not** copy the AR2/O1 harness. It reuses,
unmodified, exactly the pieces that are generic and safe:

| Reused from (frozen, unmodified)                         | What                                             |
|------------------------------------------------------------|---------------------------------------------------|
| `experiments/pi_external_runtime_ar2/ar2/fixtures.py`       | `CaseFixture`, `build_case_repository`, `remove_disposable_tree`, the disposable-root authority origin |
| `experiments/pi_external_runtime_ar2/ar2/verification.py`   | `VerificationOutcome`, `run_verification`, `baseline_matches_case_contract` |
| `experiments/pi_external_runtime_ar2/ar2/record.py`         | `scrub_check` (generic secret/reasoning/ASCII scrub) |
| `src/ai_dev_orchestrator/workspace/git_adapter.py`          | the fixed, read-only Git operation set (status/ls-files observation) |

Nothing under `ar2/` or `src/` is modified. This package imports **none** of
AR2's live-runtime machinery (`broker`, `supervisor`, `launch`, `handshakes`,
`route_check`, `pi_config`, `environment`, `wire`, `winpipe`, `candidate`,
`operations`, `observation`) -- there is no live runtime to integrate with
here at all.

**I2's own `i2_environment.py` / `i2_pi_config.py` / `i2_route.py` are
structurally modeled on** `ar2/environment.py`, `ar2/pi_config.py`, and
`ar2/route_check.py` (I2A design Sec. 9/10/15) -- the accepted VALUES
(Windows baseline names, forbidden-fragment list, generated-config shape,
the `check_route_serves_model` call shape) are duplicated as new I2-owned
data and wiring, never imported as a dependency. `i2_route.py`'s offline
route-check wiring is exercised only against an INJECTED synthetic checker;
the real, unmodified `ar2.route_check.check_route_serves_model` function is
never imported or called by anything in this package.

## Running the offline suite

```bash
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(Use the project's own virtual environment's `python`/`pytest` if `pydantic`
and friends are not on the ambient interpreter's path.)

## Status

Corpus, classifier, hard-bar and ranking machinery (I1) are ready offline.
**I2's offline machinery (slices I2-1 through I2-5) is implemented and
green** -- the child-environment builder, the run-scoped secret context, the
disposable Pi config generator, the route descriptors, the credential
read-ordering contract, and the phase-aware cleanup-failure classification.

**5F3B-I2-FU1 (Credential/Route Boundary Integrity Closure) closed seven
implementation gaps** an independent review found in I2's source: every
secret-bearing object (`ConnectionValues`, `LaunchEnvironment`, and the
narrowly-authorized `ArtifactSafetyContext`) is now repr-safe; the
`narrow_path` PATH-inheritance bypass is removed; the config generator no
longer accepts a caller-supplied `provider_id`/`credential_env_var_name`;
raw route-check failure text is no longer retained; a missing/blank/
malformed connection value is now a true bounded `InfrastructureRefusal`;
preflight failure detail is a bounded code, not free prose; and the B300
base URL is structurally validated before it can become safety-context
data. See `FINDINGS.md`'s `5F3B-I2-FU1` section for the full closure record.
None of it reopens the accepted I2A architecture.

**5F3B-I2-FU2 (Authority + Trusted-Value Closure) closed a further class of
gaps**: a safe factory existed, but its public value object could still be
forged by direct construction, or a destructive API trusted an unproven
path. `GeneratedQualificationConfig` required creation-time authority
before it could even be constructed, and `scrub_generated_qualification_config`
took that typed object -- never a raw path -- re-verifying the same
authority immediately before deleting anything.
`ConnectionValues`/`RouteDescriptor`/`QualificationRouteSecretContext` became
valid by construction (`__post_init__` enforces every field), with
`run_offline_route_check` additionally revalidating the descriptor at the
consumption boundary; the config generator's `base_url` went through the
one shared validator; `PreflightGateResult` could no longer express an
impossible `passed`/`failure_code` combination; and an exception a route
checker raises was reduced to a bounded `RouteFailureCode.ROUTE_CHECK_ERROR`,
never retaining `str(exc)`/`repr(exc)`/traceback text. See `FINDINGS.md`'s
`5F3B-I2-FU2` section for the full closure record.

**5F3B-I2-FU3 (Run Authority and Cross-Boundary Binding Closure) closed the
next class of gaps**, mainly in FU2's own authority mechanism and in two
remaining "raw value instead of trusted object" boundaries. FU2's
directory-deletion authority was a FIXED, PUBLIC marker string -- forgeable
by copying it into any directory. It is now a fresh, unpredictable, per-run
128-bit token (`secrets.token_hex(16)`), held only in memory
(`field(repr=False)`, never written to disk), with the on-disk marker
carrying only a path-keyed SHA-256 binding -- copying the marker to a
different directory no longer authorizes it. The generator now cleans up
its own partial failure (an injected internal write failure triggers a
verified delete using the authority it just established, never leaving an
endpoint-bearing partial config behind). `build_child_environment` no
longer accepts a raw `pi_config_dir`/`credential_value` string -- it
consumes an authority-reverified `GeneratedQualificationConfig` and a
`QualificationRouteSecretContext`, so the child's `PI_CODING_AGENT_DIR` and
credential can never disagree with the run's own trusted objects.
`LaunchEnvironment.environment` is now a read-only `MappingProxyType` view
(assignment raises `TypeError`); a fresh mutable copy is available only via
`as_launch_snapshot()`. `PreflightGateResult.passed` and the route
checker's `reachable`/`configured_model_served` now require `type(...) is
bool` exactly -- `"false"`/`1`/`0` no longer coerce through Python's own
truthiness. A new `i2_composition.verify_i2_identity_binding` binds
config/secret/route identity so the three cannot silently disagree once
composed for one run. See `FINDINGS.md`'s `5F3B-I2-FU3` section for the
full closure record. None of FU1/FU2/FU3 reopens the accepted I2A
architecture.

**5F3B-I2-FU3A (Issuance Authority, Content Integrity, Mandatory Binding
Closure) is the final offline-only closure.** FU3's marker still never
required the token itself to be genuinely I2-issued -- a caller could mint
its own token, hand-compute the same public binding formula, and forge a
marker into an arbitrary directory. A new process-local, in-memory-only
registry (`qualification/i2_issuance.py`) now records every token I2 itself
issues, for the exact directory it issued it for, and authority requires
BOTH the marker binding AND registry presence
(`i2_pi_config.verify_cleanup_authority`). A stricter
`verify_generated_config_integrity` additionally requires the issuance to be
FINALIZED and the on-disk `settings.json`/`models.json` bytes to still match
the SHA-256 digests recorded when I2 wrote them -- used by every
launch-capable consumption path, so a config edited after generation (a
relabeled model id, a substituted literal secret, an added `maxTokens`, a
changed `baseUrl`, a retry/trust policy edit) is refused, while cleanup of a
tampered-but-genuinely-issued config remains possible. `build_child_environment`
and `run_offline_route_check` now each independently refuse a
generated-config/secret-context or route-descriptor/secret-context identity
mismatch themselves, rather than relying on a caller remembering to call
`verify_i2_identity_binding` first. `LaunchEnvironment.__post_init__` now
copies its input dict before validating, closing an external-mutable-alias
gap independent review reproduced. See `FINDINGS.md`'s `5F3B-I2-FU3A`
section for the full closure record.

**5F3B-I2-FU3B (Issuance Registry Encapsulation Closure) is the final
offline-only correction.** FU3A's own registry mutation functions
(`register_issuance`/`finalize_issuance`/`discard_issuance`) were PUBLIC.
Independent review used ONLY that public surface -- no `object.__new__`, no
private-global mutation, no live activity -- to self-issue authority for an
arbitrary victim directory (call `register_issuance` for its own chosen
token/path/identity, then satisfy every other check normally), and
separately to overwrite an already-trusted digest with a tampered one by
calling `finalize_issuance` a second time. `qualification/i2_issuance.py`
now exposes only underscore-prefixed functions
(`_register_issuance`/`_finalize_issuance`/`_lookup_issuance`/
`_discard_issuance`); `i2_pi_config`/`i2_cleanup` remain its only callers.
`IssuanceRecord` is now `@dataclass(frozen=True)` with a bounded custom
`__repr__` (never the token or the canonical path), the registry is keyed by
token alone (one token = one issued config; a token already registered for
any path is refused), and finalization is one-shot -- a second finalization
for an already-finalized token is refused
(`ISSUANCE_ALREADY_FINALIZED`), never silently replacing trusted digests.
See `FINDINGS.md`'s `5F3B-I2-FU3B` section for the full closure record.
This closes the accepted 5F3B-I2 scope; no further FU is anticipated absent
a new independent-review finding.

**5F3B-I2B (Category-B Zero-Prompt Live-Gate Controller) is offline wiring
only.** `qualification/i2b_controller.py` implements the state-machine shape
that will LATER execute the accepted Category-B gates -- gate ordering, the
credential-read boundary, failure attribution, teardown/cleanup discipline,
and evidence safety -- entirely through injected callables and synthetic
offline doubles. **I2B CONTROLLER WIRED OFFLINE. CATEGORY-B LIVE EXECUTION
NOT RUN. NO CANDIDATE MODEL RUN. Q1/Q2 NO-GO.** See the "What I2B adds"
section above for the full closure record.

**This is still an offline-only implementation.** No zero-prompt live gate
(I2A Sec. 15) has run, no candidate model has run, and 5F3B-Q1/Q2 (the first
live candidate sweeps) remain **NOT authorized** and cannot execute until a
future, separately authorized phase runs the Category B live gates on top of
this machinery.
