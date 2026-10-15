"""Supervised implementer (ALPHA-P1A, DEC-SUP): offline, library-only.

One approved file's current text goes in. One model's proposed final text
comes back as **untrusted proposed content**, and AIDO turns it into a Phase 5E2
diff proposal with the unchanged deterministic generator. Then it **stops**:
a human must approve the exact diff (Phase 5F0) before the unchanged 5F2C
writer may do anything.

- Candidate ``SUP-D`` = ``qwen3.8-27b``. It is not in ``CANDIDATE_MODEL_IDS``
  and carries no qualification credit.
- Offline only: the runner accepts exactly ``httpx.MockTransport`` and rejects
  any other transport type, a guard against accidental live use, not a sandbox
  (a mock handler is arbitrary trusted caller code). No CLI command exists, so
  there is no authorized live invocation entry point.
- One request, zero retries, no fallback, a strict parser, no repair.

See ``docs/PHASE_ALPHA_P1A_SUPERVISED_IMPLEMENTER_OFFLINE.md``.
"""

from ai_dev_orchestrator.supervised_implementer.identity import (
    QUALIFICATION_CREDIT,
    SUPERVISED_CANDIDATE_ID,
    SUPERVISED_CANDIDATE_MODEL_IDS,
    SUPERVISED_IMPLEMENTER_ROLE,
)
from ai_dev_orchestrator.supervised_implementer.implementer import (
    check_supervised_implementer_endpoint,
    check_supervised_implementer_gate,
    run_supervised_implementer_offline,
)
from ai_dev_orchestrator.supervised_implementer.models import (
    SourceTransmissionNotice,
    SupervisedImplementerError,
    SupervisedImplementerOutput,
    SupervisedImplementerOutputRejected,
    SupervisedImplementerProvenance,
    SupervisedImplementerRefused,
    SupervisedImplementerResult,
    SupervisedImplementerTransportFailed,
    parse_supervised_implementer_output,
    revalidate_supervised_implementer_result,
)
from ai_dev_orchestrator.supervised_implementer.request import (
    build_supervised_implementer_request,
)

__all__ = [
    "QUALIFICATION_CREDIT",
    "SUPERVISED_CANDIDATE_ID",
    "SUPERVISED_CANDIDATE_MODEL_IDS",
    "SUPERVISED_IMPLEMENTER_ROLE",
    "SourceTransmissionNotice",
    "SupervisedImplementerError",
    "SupervisedImplementerOutput",
    "SupervisedImplementerOutputRejected",
    "SupervisedImplementerProvenance",
    "SupervisedImplementerRefused",
    "SupervisedImplementerResult",
    "SupervisedImplementerTransportFailed",
    "build_supervised_implementer_request",
    "check_supervised_implementer_endpoint",
    "check_supervised_implementer_gate",
    "parse_supervised_implementer_output",
    "revalidate_supervised_implementer_result",
    "run_supervised_implementer_offline",
]
