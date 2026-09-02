"""Phase 5F3B-I1 -- Pi implementer qualification corpus + offline harness.

**OFFLINE ONLY.** Nothing in this package launches Pi, calls a model, opens a
socket, or reads a credential. Every fixture is a synthetic, disposable Git
repository built under a fresh AIDO-created root (reusing
``experiments/pi_external_runtime_ar2/ar2/fixtures.py`` unmodified); every
"model run" the offline test suite exercises is a plain Python data
structure describing externally-observed facts, fed directly to a pure
policy function.

This package implements the slice authorized by
``docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`` Section 24,
5F3B-I1: the frozen IQ-1/IQ-2/IQ-3 corpus, baseline contract validation, the
autonomous outcome classifier, the run-validity model, refusal attribution
and scope metrics, a conservative report-accuracy comparator, the hard
qualification bar, categorical ranking, a versioned record schema with a
fail-closed safe-emission choke point, and immutable invalidation/
replacement lineage evidence -- PLUS 5F3B-I2's offline B300 route/credential
machinery (``docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md``,
slices I2-1 through I2-6, hardened through FU1/FU2/FU3/FU3A/FU3B): the
positive-allowlist child-environment builder, the run-scoped secret context,
the disposable Pi ``settings.json``/``models.json`` generator with genuine,
process-local issuance authority, route descriptors and offline route-check
wiring, credential-read ordering, generated-config cleanup with cleanup-
authority/complete-content-integrity separation, and config/secret/route
cross-object identity binding enforced at every consumption boundary. Every
one of these is fully offline -- no Pi/Node process, no HTTP/socket call, no
real credential read, anywhere in this package.

**Not implemented here, and not authorized by this package:** any live
Pi/Node process launch, a live compatibility handshake, a live zero-prompt
qualification gate or executor (5F3B-Q1/Q2 remain **NOT authorized**), any
model comparison result, a reviewer, real workspace authority, automatic
continuation, or a production stall circuit breaker. No candidate model has
ever been run. No PASS/FAIL verdict exists for Candidate A or Candidate B.

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

#: 5F3B-Q1-PRE1-FU2 (DESIGN-FU1 Sec. 3.B) -- the SIBLING attempt-level
#: artifact kind for a task attempt whose semantic dispatch send state could
#: not be mechanically established. It is deliberately NOT a widening of
#: :data:`RECORD_VERSION`: the frozen primary schema admits exactly
#: ``semantic_prompts_sent in (0, 1)``, and an unestablished send fact has no
#: truthful slot there. This artifact OMITS ``semantic_prompts_sent``
#: entirely rather than encoding the gap as ``null``, ``0``, or a sentinel.
ATTEMPT_RECORD_VERSION = "pi-implementer-qualification-attempt.v1"
