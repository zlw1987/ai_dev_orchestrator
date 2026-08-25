"""Phase 5F3B-I1 -- Pi implementer qualification corpus + offline harness.

**OFFLINE ONLY.** Nothing in this package launches Pi, calls a model, opens a
socket, or reads a credential. Every fixture is a synthetic, disposable Git
repository built under a fresh AIDO-created root (reusing
``experiments/pi_external_runtime_ar2/ar2/fixtures.py`` unmodified); every
"model run" the offline test suite exercises is a plain Python data
structure describing externally-observed facts, fed directly to a pure
policy function.

This package implements exactly the slice authorized by
``docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`` Section 24,
5F3B-I1: the frozen IQ-1/IQ-2/IQ-3 corpus, baseline contract validation, the
autonomous outcome classifier, the run-validity model, refusal attribution
and scope metrics, a conservative report-accuracy comparator, the hard
qualification bar, categorical ranking, a versioned record schema with a
fail-closed safe-emission choke point, and immutable invalidation/
replacement lineage evidence.

**Not implemented here, and not authorized by this package:** B300 routing,
credentials, a Pi provider config, a live compatibility handshake, a live
qualification executor, any model comparison result, a reviewer, real
workspace authority, automatic continuation, or a production stall circuit
breaker. No candidate has been run. No PASS/FAIL verdict exists.

Reused, unmodified, from the sibling frozen experiments:

    experiments/pi_external_runtime_ar2/ar2/fixtures.py       CaseFixture,
        build_case_repository, remove_disposable_tree,
        create_disposable_experiment_root (disposable-root authority)
    experiments/pi_external_runtime_ar2/ar2/verification.py   VerificationOutcome,
        run_verification, baseline_matches_case_contract, parse_pytest_summary
    experiments/pi_external_runtime_ar2/ar2/record.py         scrub_check
        (the generic, parameterized secret/reasoning/ASCII scrub)
    src/ai_dev_orchestrator/workspace/git_adapter.py           the fixed,
        read-only Git operation set (status/ls-files observation)

Nothing under ``ar2/`` or ``src/`` is modified by anything in this package.
No ``AgentRuntime`` / generic multi-runtime abstraction is introduced here;
that abstraction stays deferred per the design.
"""

from __future__ import annotations

PACKAGE_ID = "pi_implementer_qualification"
RECORD_VERSION = "pi-implementer-qualification.v1"
FIXTURE_SCHEMA_VERSION = "pi-implementer-qualification-fixture.v1"
LINEAGE_RECORD_VERSION = "pi-implementer-qualification-lineage.v1"
REFUSAL_RECORD_VERSION = "pi-implementer-qualification-refusal.v1"
