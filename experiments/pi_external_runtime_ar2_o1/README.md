# Phase 5F3A-AR2-O1 -- Two-File Coordinated Implementation Case

**EXPERIMENT ONLY.** Not production code. Not a CLI command. Lives outside
`src/`, adds no `ProjectConfig` field, and this whole directory may be
deleted as one unit without touching anything else in the repository.

## What this is

A small, separate follow-up experiment built **on top of** the accepted,
frozen `experiments/pi_external_runtime_ar2/` architecture (AR2). AR2
established that a Pi runtime can nominate repository-relative path
candidates while AIDO's own Python broker authorizes every read/write, and
demonstrated four cases (R1 control, R2 discovery, R3 protected-write
refusal, R4 clean/no-change) -- each touching **at most one** implementation
file.

O1 asks the one remaining AR2D qualification question those four cases could
not: **can the same Pi + broker architecture complete ONE task that
genuinely requires coordinated changes to TWO implementation files**, under
the accepted, unmodified two-file changed-file cap
(`ar2.capability.MAX_CHANGED_FILES_PER_RUN == 2`)?

This is **not** model benchmarking and **not** production qualification.

## How it reuses AR2 without modifying it

Nothing under `experiments/pi_external_runtime_ar2/` is read-and-rewritten,
monkeypatched, or forked by copy-paste. `o1/__init__.py` documents exactly
which AR2 modules are imported and reused **unmodified** (broker,
capability, candidate, operations, observation, verification's bounded
runner, supervisor, launch, handshakes, route-check, pi-config, environment,
protocol, wire, winpipe, ascii_json) and which four small pieces O1 supplies
itself, because they are case-set-specific in AR2 and cannot fit O1's shape
without editing frozen code:

| AR2 (frozen, R1-R4 specific)                          | O1's own equivalent                    |
|---------------------------------------------------------|-----------------------------------------|
| `ar2.fixtures.CASES_BY_ID` (R1-R4 only)                  | `o1.fixture.O1_CASE` (same `CaseFixture` dataclass, one new value) |
| `ar2.verification.baseline_matches_case_contract` (exactly 1 failing test) | `o1.fixture.baseline_matches_o1_contract` (exactly 3: two independent behaviors + the integration test) |
| `run_ar2.py`'s `_assess_case` (dispatches on R1-R4)      | `o1.assessment.assess_o1`                |
| `ar2.record.record_header` / `refusal_record` (AR2's own experiment id/version) | `o1.record.record_header` / `refusal_record` (a NEW experiment id/version; everything else -- `scrub_check`, `redact_value`, `broker_secret_denylist`, `CAPABILITY_BOUNDARY`, `RESIDUAL_LIMITATIONS`, `TOKEN_POLICY` -- imported from `ar2.record` unchanged) |
| `ar2.launch.resolve_runtime_identity` (exact Pi version == `"0.84.2"` gate) | `o1.pi_compat.resolve_pi_identity_provenance_only` + a zero-prompt capability-compatibility gate (see below) |

`run_o1.py` mirrors `run_ar2.py`'s four phases (`preflight`, `broker`,
`handshake`, `case`) call-for-call, using AR2's real functions directly.

The model pin and logical route name are imported directly from `ar2`
(`PINNED_MODEL_ID`, `LOGICAL_ROUTE_NAME`) -- never redeclared -- so there is
exactly one place either experiment's model/route pin could drift from the
other's. **Pi's version is deliberately NOT imported from `ar2` at all** --
see the Pi compatibility policy below.

## Pi compatibility policy (corrected)

The first O1 invocation inherited AR2's exact-version gate unchanged
(`resolve_runtime_identity(expected_version="0.84.2")`), and stopped at
`preflight` with zero prompts sent when the operator-upgraded, installed Pi
reported `"0.84.3"`. That was a **harness-policy defect**, not a runtime
incompatibility -- nothing about the actual seam had been checked yet.

The corrected policy, for O1 only (AR2 itself, and its historical
`PINNED_PI_VERSION = "0.84.2"` and R1-R4 records, remain untouched and
truthful evidence of the Pi version AR2 actually used):

    Pi version = provenance / diagnostic evidence, always recorded truthfully
    Pi version = NEVER authorization by itself

There is no comparison against any pin anywhere in `o1/pi_compat.py` --
not an exact match, not a semver range. Instead, before any prompt, a
**zero-prompt compatibility gate** mechanically proves the exact runtime
seam O1 depends on: Node-direct launch, JSONL RPC request/response
correlation, RPC startup with zero inference, H1 exact extension identity,
H2 exact provider/model identity, the required CLI launch shape (AR2's own
`build_pi_argv`, unmodified), absence of any protocol violation or extension
error during that exchange, and the non-inference `/models` route check. If
ANY of those fails, O1 fails closed for that EXACT capability/behavior --
never generically as "version mismatch" -- and sends zero prompts. If every
check passes, a *different* Pi version is allowed to proceed; a version
difference is never by itself a reason to stop. See `FINDINGS.md` for the
actual `0.84.3` compatibility-gate result and the live case it then
authorized.

## The task: a new "enterprise" subscription tier

Fixture (`o1/fixture.py`), a synthetic Git repository:

```
subscription/__init__.py    (package docstring only)
subscription/normalize.py   (tier-name normalization -- knows "standard"/"pro" only)
subscription/rates.py       (per-seat rate lookup -- knows "standard"/"pro" only)
subscription/quote.py       (composes normalize + rate lookup -- ALREADY CORRECT)
subscription/labels.py      (invoice label rendering -- unrelated decoy)
tests/test_subscription.py  (verification witness -- protected, read-only)
NOTES.md
```

Six non-test tracked files (>= 5 required), one test witness. The task is
"add a third tier, `enterprise`, at 6000 cents/seat" -- and it **genuinely**
requires editing both `normalize.py` (so "enterprise" spellings normalize at
all) and `rates.py` (so the canonical name has a configured rate).
`quote.py` needs no change: it already calls both functions correctly, so a
one-file patch to it cannot supply either missing behavior. Three
independent tests enforce this as a verified property rather than an
intention: `test_normalize_enterprise_variants` and `test_rate_enterprise`
each fail on their own missing behavior, and `test_quote_enterprise` fails
whenever *either* underlying behavior is missing, so no single-file
workaround at the integration point can pass the full suite. See
`tests/test_o1_baseline.py` for the mechanically verified proof.

The model prompt (`o1.fixture.O1_CASE.prompt`) describes this behavior in
prose and **never names `normalize.py` or `rates.py`**
(`tests/test_o1_prompt_and_manifest.py` asserts this). The model receives
the task description plus AR2's own AIDO-computed, unmodified bounded
manifest of every readable/editable file -- it must discover both
implementation locations itself.

## Reused caps, unmodified

- `max_changed_files_per_run = 2` (AR2's default, not raised, not
  overridden). A successful O1 run consumes exactly both slots; a probed
  third distinct edit is refused by the same `RunState.edit_budget_allows`
  AR2 already ships (`tests/test_o1_budget_and_policy.py`).
- No `aido_verify`, no shell, no search/list/glob tool. Pi gets exactly
  `aido_read` and `aido_edit`, same as every AR2 case.
- No reviewer is invoked.
- `aido_requested_max_output_tokens: null` -- AIDO imposes no output-token
  ceiling. Never written into generated Pi model configuration.

## Running it

```bat
copy experiment_config.example.json experiment_config.json
:: edit python_executable if needed; provider_id/model_id/base_url_env_name
:: are pinned to the same accepted AR2 route and should not be changed.
```

`experiment_config.json` ships **absent** and is git-ignored; never commit
it. Endpoint and credential values come only from the environment variable
named in `base_url_env_name` (`AIDO_VLLM_BASE_URL`), never from config.

```bash
python run_o1.py --phase preflight
python run_o1.py --phase broker
python run_o1.py --phase handshake
python run_o1.py --phase case --run-pi-delegated-broker-experiment --send-one-real-model-prompt
```

`--phase case` requires **both** explicit flags and sends **at most one**
semantic prompt, ever, for the life of this harness. There is no retry, no
fallback model, and no fallback route for any reason.

**Operator prerequisite** (not attested by the harness): the offline suite
under `tests/` must be green before `--phase case` is ever run.

```bash
python -m pytest experiments/pi_external_runtime_ar2_o1/tests -q
```

See `FINDINGS.md` for the full history: the harness-policy defect that
blocked the first invocation, its correction, the zero-prompt compatibility
gate result against the actual installed `0.84.3` runtime, and the live O1
case result.
