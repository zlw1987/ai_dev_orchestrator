# Phase 5F3B-I1 -- Pi Implementer Qualification Corpus + Offline Harness

> **OFFLINE QUALIFICATION HARNESS ONLY.**
> **NO MODEL QUALIFICATION HAS OCCURRED.**
> **NO CANDIDATE PASS/FAIL EXISTS YET.**
> **5F3B-I2 / Q1 / Q2 ARE NOT AUTHORIZED.**

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

## What is explicitly NOT here

Per the design's Section 24 roadmap and Section 23:

- B300 routing, a Pi provider config, or a live Pi compatibility handshake.
- Any credential of any kind.
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

## Running the offline suite

```bash
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(Use the project's own virtual environment's `python`/`pytest` if `pydantic`
and friends are not on the ambient interpreter's path.)

## Status

Corpus, classifier, hard-bar and ranking machinery are ready offline. Per
the design's Section 26 verdict: 5F3B-I2 (route integration, which touches
credential handling) requires its own separate approval, and 5F3B-Q1/Q2
(the first live candidate sweeps) cannot execute until I2 ships. Neither is
authorized by this package.
