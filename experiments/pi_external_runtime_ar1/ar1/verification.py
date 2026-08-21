"""Authoritative verification, using AIDO's accepted bounded RUNNER semantics.

Two deliberate choices, both required by the AR1 brief:

1. **The runner, not the state-bound verifier.** ``verification/verifier.py``
   binds to a pre-approved ``post_image_sha256`` and a human-approved diff. AR1's
   change is produced by a runtime and observed after the fact, so that binding
   is not merely inconvenient -- it would be false. The bounded *runner* carries
   the properties AR1 needs (fixed argv, ``shell=False``, no PATH search, minimal
   environment, AIDO-owned wait deadline, cap enforced during capture).

2. **The command is fixed by the experiment, never model-selected.** No model
   output may select a path, a command, an executable, or a file to change.

``-B`` and ``-p no:cacheprovider`` are passed so verification writes no
``__pycache__`` and no ``.pytest_cache`` into the fixture. That keeps the
post-run untracked set genuinely empty, so ``unexpected_untracked`` stays a sharp
signal instead of being blunted by a tolerated-cache allowlist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ai_dev_orchestrator.verification.runner import (
    VerificationExecutableError,
    VerificationLaunchError,
    decode_verification_output,
    run_configured_verification,
    validate_verification_executable,
)

VERIFICATION_TIMEOUT_SECONDS = 300
VERIFICATION_MAX_OUTPUT_BYTES = 1 * 1024 * 1024

# Fixed by the experiment. Not configurable by, or visible to, the model.
VERIFICATION_ARGS: tuple[str, ...] = (
    "-B",
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "-rf",
    "test_calc.py",
)

_SUMMARY_RE = re.compile(r"(?P<count>\d+)\s+(?P<word>passed|failed|error|errors)")
_FAILED_RE = re.compile(r"^FAILED\s+(?P<nodeid>\S+)", re.MULTILINE)


class VerificationError(Exception):
    """Verification could not be launched at all."""


@dataclass(frozen=True)
class VerificationOutcome:
    """What AIDO's own verification actually observed. Authoritative."""

    argv: tuple[str, ...]
    started: bool
    completed: bool
    timed_out: bool
    output_limit_exceeded: bool
    return_code: int | None
    passed: bool
    output_complete: bool
    direct_child_killed: bool
    output_text: str
    failed_node_ids: tuple[str, ...]
    counts: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "argv_tail": list(self.argv[1:]),
            "executable_recorded": False,
            "started": self.started,
            "completed": self.completed,
            "timed_out": self.timed_out,
            "output_limit_exceeded": self.output_limit_exceeded,
            "return_code": self.return_code,
            "passed": self.passed,
            "output_complete": self.output_complete,
            "orchestrator_direct_child_killed": self.direct_child_killed,
            "failed_node_ids": list(self.failed_node_ids),
            "counts": self.counts,
            "output_tail": self.output_text[-4000:],
            "claim_scope": (
                "This is a controlled invocation of repository-controlled code, "
                "not sandboxed execution. Descendants are not tracked and may "
                "still be running."
            ),
        }


def parse_pytest_summary(output: str) -> tuple[dict[str, int], tuple[str, ...]]:
    """Extract counts and failing node ids from ``pytest -q -rf`` output."""
    counts: dict[str, int] = {}
    tail = output.strip().splitlines()[-1] if output.strip() else ""
    for match in _SUMMARY_RE.finditer(tail):
        word = match.group("word")
        key = "error" if word.startswith("error") else word
        counts[key] = counts.get(key, 0) + int(match.group("count"))
    failed = tuple(match.group("nodeid") for match in _FAILED_RE.finditer(output))
    return counts, failed


def run_verification(
    *, python_executable: str, workspace_root: str
) -> VerificationOutcome:
    """Run the fixed verification command once, bounded."""
    try:
        executable = validate_verification_executable(
            python_executable, workspace_root=workspace_root
        )
    except VerificationExecutableError as exc:
        raise VerificationError(f"verification error: {exc}") from exc

    try:
        execution = run_configured_verification(
            executable=executable,
            args=list(VERIFICATION_ARGS),
            cwd=workspace_root,
            timeout_seconds=VERIFICATION_TIMEOUT_SECONDS,
            max_output_bytes=VERIFICATION_MAX_OUTPUT_BYTES,
        )
    except VerificationLaunchError as exc:
        raise VerificationError(f"verification error: {exc}") from exc

    text, _decoded_cleanly = decode_verification_output(execution.output_bytes)
    counts, failed = parse_pytest_summary(text)
    return VerificationOutcome(
        argv=execution.argv,
        started=execution.started,
        completed=execution.completed,
        timed_out=execution.timed_out,
        output_limit_exceeded=execution.output_limit_exceeded,
        return_code=execution.return_code,
        passed=execution.passed,
        output_complete=execution.output_complete,
        direct_child_killed=execution.direct_child_killed,
        output_text=text,
        failed_node_ids=failed,
        counts=counts,
    )


def baseline_matches_seeded_defect(
    outcome: VerificationOutcome, *, expected_failing_test: str
) -> tuple[bool, str]:
    """Whether the baseline shows exactly the one seeded equality failure."""
    if outcome.passed:
        return False, "baseline verification passed; the seeded defect is absent"
    if outcome.counts.get("failed") != 1:
        return False, f"baseline failure count was {outcome.counts.get('failed')!r}, expected exactly 1"
    if outcome.counts.get("passed") != 2:
        return False, f"baseline passing count was {outcome.counts.get('passed')!r}, expected exactly 2"
    if len(outcome.failed_node_ids) != 1:
        return False, "baseline reported a failing-node-id count other than 1"
    if expected_failing_test not in outcome.failed_node_ids[0]:
        return False, (
            f"baseline failing test was {outcome.failed_node_ids[0]!r}, "
            f"expected {expected_failing_test!r}"
        )
    return True, "baseline shows exactly the seeded equality failure"
