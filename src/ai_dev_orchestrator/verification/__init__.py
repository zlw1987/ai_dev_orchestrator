"""Controlled verification package (Phase 5F2D).

The first separately authorized capability in this repository to execute
**repository-controlled code**. Phase 5F2C writes one approved file; this phase
asks the project's own configured verification process whether that change holds
up, once, under bounded conditions, with the workspace state pinned on both
sides of the run.

Two modules, and the split is the design:

- :mod:`~ai_dev_orchestrator.verification.runner` owns the one execution. It
  validates the configured executable, assembles the exact argv, and launches it
  with ``shell=False``, a minimal environment, a bound on **AIDO's wait** and an
  output bound enforced during capture. It is **not** a general process utility
  and **not** a process-tree manager: there is no public "run this command" entry
  point, no retry, no fallback executable, no PATH search, and no command string
  anywhere.
- :mod:`~ai_dev_orchestrator.verification.verifier` owns the state binding and
  the result. It proves the workspace is exactly the approved post-image, on a
  pinned HEAD commit, with exactly one Git-visible dirty path before anything is
  launched, and proves all of it again afterwards.

**Controlled invocation is not sandboxed execution.** The launched process may
import project modules, run ``conftest.py``, create files, open sockets and spawn
children, and its descendants may still be running after the run returns. AIDO
does not confine it, does not track its descendants, and the result report says
so instead of claiming inertness it cannot establish. Every AIDO-owned negative
claim in that report is explicitly scoped with an ``orchestrator_`` prefix, so no
field can be misread as a statement about the child.

The L1 plan's ``required_verification`` is never command authority here. It is
planner-controlled prose, possibly model-written; it is never split, parsed, run,
or turned into argv. Execution authority is the project config's
``controlled_verification`` block plus explicit CLI consent, and nothing else.

Importing this package launches nothing, reads no workspace, and runs no command.
"""

from ai_dev_orchestrator.verification.runner import (
    CONFIGURED_ARGS_TRUST_NOTE,
    DIRECT_CHILD_REAP_GRACE_SECONDS,
    ENVIRONMENT_FORWARDING_POLICY,
    FORBIDDEN_ENV_NAME_FRAGMENTS,
    INHERITED_ENV_NAMES,
    WAIT_BOUND_POLICY,
    VerificationExecutableError,
    VerificationExecution,
    VerificationLaunchError,
    build_verification_argv,
    build_verification_environment,
    decode_verification_output,
    run_configured_verification,
    validate_verification_executable,
)
from ai_dev_orchestrator.verification.verifier import (
    POST_EXECUTION_DETECTION_LIMITS,
    VERIFICATION_GIT_OPERATIONS,
    VERIFICATION_MODE,
    VERIFICATION_SCHEMA_VERSION,
    VERIFICATION_SINGLE_ACTOR_CONTRACT,
    VerificationCapabilityBoundaries,
    VerificationCommandBlock,
    VerificationError,
    VerificationExecutionBlock,
    VerificationOutputBlock,
    VerificationRefusedError,
    VerificationResultReport,
    VerificationTargetBlock,
    VerificationWorkspacePostconditionBlock,
    VerificationWorkspacePreconditionBlock,
    verify_approved_file_edit,
)

__all__ = [
    "CONFIGURED_ARGS_TRUST_NOTE",
    "DIRECT_CHILD_REAP_GRACE_SECONDS",
    "ENVIRONMENT_FORWARDING_POLICY",
    "FORBIDDEN_ENV_NAME_FRAGMENTS",
    "INHERITED_ENV_NAMES",
    "WAIT_BOUND_POLICY",
    "POST_EXECUTION_DETECTION_LIMITS",
    "VERIFICATION_GIT_OPERATIONS",
    "VERIFICATION_MODE",
    "VERIFICATION_SCHEMA_VERSION",
    "VERIFICATION_SINGLE_ACTOR_CONTRACT",
    "VerificationCapabilityBoundaries",
    "VerificationCommandBlock",
    "VerificationError",
    "VerificationExecutableError",
    "VerificationExecution",
    "VerificationExecutionBlock",
    "VerificationLaunchError",
    "VerificationOutputBlock",
    "VerificationRefusedError",
    "VerificationResultReport",
    "VerificationTargetBlock",
    "VerificationWorkspacePostconditionBlock",
    "VerificationWorkspacePreconditionBlock",
    "build_verification_argv",
    "build_verification_environment",
    "decode_verification_output",
    "run_configured_verification",
    "validate_verification_executable",
    "verify_approved_file_edit",
]
