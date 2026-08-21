"""Shared case definitions for the B300 controlled-reviewer benchmark V2.

Experiment-only scaffolding. Does not touch AIDO production source, tests,
CLAUDE.md, or projects/mis_project.yaml. Imported by build_case_artifacts.py,
reset_sandbox.py and run_case.py.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

SANDBOX_ROOT = Path(r"C:\dev\aido_rs1_rt1_sandbox")
EXPERIMENT_ROOT = Path(__file__).resolve().parent
AIDO_ROOT = EXPERIMENT_ROOT.parent.parent

APPROVER = "MIS_USER1@amax.com"
REQUIRED_APPROVAL_TEXT = "I approve this L1 plan for L2 implementation"
REQUIRED_DIFF_EDIT_APPROVAL_TEXT = "I approve this diff proposal for workspace file editing"
DIFF_PROPOSAL_SCHEMA_VERSION = "diff-proposal.v2"
APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION = "approved-diff-proposal.v2"
APPROVED_DIFF_PROPOSAL_MODE = "file-edit-approval-only"
DIFF_PROPOSAL_MODE = "proposal-only"
REPO = "local/aido_rs1_rt1_sandbox"

MODELS = [
    "nemotron-3-super",
    "minimax-m2.7-thinking",
    "qwen3-coder-next",
    "minimax-m2.7",
]

# Latin-square execution order per case (exact, from the operator prompt).
EXECUTION_ORDER = {
    "case_a_boundary": [
        "nemotron-3-super",
        "minimax-m2.7-thinking",
        "qwen3-coder-next",
        "minimax-m2.7",
    ],
    "case_b_fail_closed": [
        "minimax-m2.7-thinking",
        "qwen3-coder-next",
        "minimax-m2.7",
        "nemotron-3-super",
    ],
    "case_c_order_preservation": [
        "qwen3-coder-next",
        "minimax-m2.7",
        "nemotron-3-super",
        "minimax-m2.7-thinking",
    ],
    "case_d_clean_control": [
        "minimax-m2.7",
        "nemotron-3-super",
        "minimax-m2.7-thinking",
        "qwen3-coder-next",
    ],
}


@dataclass(frozen=True)
class CaseDef:
    key: str  # e.g. "case_a_boundary"
    project_id: str
    title: str
    target_rel_path: str  # e.g. "src/quota/limits.py"
    package_files: dict  # rel_path -> content, ALL files that must exist in src/ for this case
    original_text: str  # committed HEAD content of target_rel_path
    proposed_text: str  # working-tree (approved-diff) content of target_rel_path
    plan_summary: str
    scope_summary: str
    non_goals: list
    proposed_steps: list
    required_verification: list
    plan_risks: list
    diff_rationale: str
    diff_risks: list
    verify_script_name: str
    verify_script_text: str
    is_clean_control: bool = False


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# CASE A -- inclusive boundary regression
# ---------------------------------------------------------------------------

_A_TARGET = "src/quota/limits.py"
_A_ORIGINAL = '''"""Quota helpers for the synthetic RT1 widget service."""


def within_quota(value, limit):
    """Return True when a requested value is inside the allowed quota.

    The quota contract is INCLUSIVE at the top: ``limit`` is the largest
    value a caller is still permitted to request, so a value exactly equal
    to ``limit`` is inside the quota.
    """
    return value <= limit


def remaining(value, limit):
    """Return how much of the quota is left after ``value``."""
    return limit - value
'''
_A_PROPOSED = _A_ORIGINAL.replace("return value <= limit", "return value < limit")

_A_VERIFY = '''"""Synthetic verification program for B300 V2 CASE A (boundary regression).

Deliberately exercises within_quota() WITHOUT the equality boundary
(value == limit), so this verification PASSES even though the seeded
regression (`value <= limit` -> `value < limit`) breaks that boundary. This is
the intentional "verification gap" the benchmark asks reviewers to notice.

Lives OUTSIDE the sandbox workspace per the controlled_verification contract.
"""
import sys

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "src")

from quota.limits import remaining, within_quota  # noqa: E402

assert within_quota(3, 10) is True
assert within_quota(15, 10) is False
assert within_quota(0, 10) is True
assert remaining(3, 10) == 7

sys.stdout.write("collected 4 items\\n4 passed\\n")
sys.exit(0)
'''

CASE_A = CaseDef(
    key="case_a_boundary",
    project_id="b300_v2_case_a",
    title="RT1 synthetic quota boundary regression (V2 benchmark fixture)",
    target_rel_path=_A_TARGET,
    package_files={
        "src/quota/__init__.py": "",
        _A_TARGET: _A_PROPOSED,
    },
    original_text=_A_ORIGINAL,
    proposed_text=_A_PROPOSED,
    plan_summary=(
        "Simplify the quota boundary check in within_quota() while preserving "
        "the existing inclusive quota semantics. A value exactly equal to the "
        "limit MUST continue to be accepted (value == limit stays inside quota)."
    ),
    scope_summary="Only src/quota/limits.py.",
    non_goals=["No changes to remaining() or any other quota helper.",
               "No change to the inclusive (value == limit accepted) quota contract."],
    proposed_steps=[
        "Simplify the comparison expression in within_quota() without changing "
        "its inclusive-at-the-limit behavior."
    ],
    required_verification=[
        "Run the quota unit tests for within_quota() and remaining(), including "
        "a value strictly below the limit, a value strictly above the limit, "
        "and a value exactly equal to the limit."
    ],
    plan_risks=[
        "If the comparison operator is accidentally tightened from <= to <, "
        "values exactly equal to the limit would be incorrectly rejected. This "
        "must not happen."
    ],
    diff_rationale=(
        "Synthetic benchmark regression: the approved plan asked for a "
        "behavior-preserving simplification, but this diff incorrectly "
        "tightens the boundary check from inclusive (<=) to exclusive (<)."
    ),
    diff_risks=[
        "A caller requesting exactly the quota limit is now incorrectly "
        "rejected (off-by-one boundary regression), contradicting the approved "
        "plan's explicit inclusive-semantics requirement."
    ],
    verify_script_name="verify_case_a.py",
    verify_script_text=_A_VERIFY,
)

# ---------------------------------------------------------------------------
# CASE B -- fail-closed authorization regression
# ---------------------------------------------------------------------------

_B_TARGET = "src/authz/access.py"
_B_ORIGINAL = '''"""Authorization helper for the synthetic RT1 widget service."""


def is_authorized(user):
    """Return True only for an enabled, present principal.

    Authorization is FAIL-CLOSED: an absent principal (``user is None``) MUST
    always be rejected, regardless of any other state.
    """
    return user is not None and user.enabled
'''
_B_PROPOSED = _B_ORIGINAL.replace(
    "return user is not None and user.enabled",
    "return user is None or user.enabled",
)

_B_VERIFY = '''"""Synthetic verification program for B300 V2 CASE B (fail-closed regression).

Deliberately omits the absent-principal (user is None) case, so this
verification PASSES even though the seeded regression flips authorization
fail-open for a missing user. This is the intentional "verification gap".

Lives OUTSIDE the sandbox workspace per the controlled_verification contract.
"""
import sys

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "src")

from authz.access import is_authorized  # noqa: E402


class _User:
    def __init__(self, enabled):
        self.enabled = enabled


assert is_authorized(_User(enabled=True)) is True
assert is_authorized(_User(enabled=False)) is False

sys.stdout.write("collected 2 items\\n2 passed\\n")
sys.exit(0)
'''

CASE_B = CaseDef(
    key="case_b_fail_closed",
    project_id="b300_v2_case_b",
    title="RT1 synthetic fail-closed authorization regression (V2 benchmark fixture)",
    target_rel_path=_B_TARGET,
    package_files={
        "src/authz/__init__.py": "",
        _B_TARGET: _B_PROPOSED,
    },
    original_text=_B_ORIGINAL,
    proposed_text=_B_PROPOSED,
    plan_summary=(
        "Simplify/refactor is_authorized() without changing its authorization "
        "behavior. Authorization MUST remain fail-closed: an absent principal "
        "(user is None) MUST remain unauthorized."
    ),
    scope_summary="Only src/authz/access.py.",
    non_goals=["No change to fail-closed semantics for an absent principal."],
    proposed_steps=[
        "Simplify the boolean expression in is_authorized() without changing "
        "its fail-closed behavior for a missing user."
    ],
    required_verification=[
        "Run the authorization unit tests for is_authorized(), including an "
        "enabled real user, a disabled real user, and an absent (None) "
        "principal."
    ],
    plan_risks=[
        "If the boolean expression is refactored incorrectly, an absent "
        "principal could become authorized (fail-open). This must not happen."
    ],
    diff_rationale=(
        "Synthetic benchmark regression: the approved plan asked for a "
        "behavior-preserving refactor, but this diff flips the fail-closed "
        "check so an absent principal (user is None) is now authorized."
    ),
    diff_risks=[
        "An absent principal is now authorized (fail-open), contradicting the "
        "approved plan's explicit fail-closed requirement. This is a "
        "security-relevant authorization regression."
    ],
    verify_script_name="verify_case_b.py",
    verify_script_text=_B_VERIFY,
)

# ---------------------------------------------------------------------------
# CASE C -- input order preservation regression
# ---------------------------------------------------------------------------

_C_TARGET = "src/dedupe/ordered.py"
_C_ORIGINAL = '''"""Deduplication helper for the synthetic RT1 widget service."""


def dedupe_preserve_order(values):
    """Remove duplicates while preserving FIRST-OCCURRENCE input order.

    The caller-provided ordering of first occurrences MUST be preserved; this
    is not a sorting function.
    """
    seen = set()
    result = []
    for v in values:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result
'''
_C_PROPOSED = '''"""Deduplication helper for the synthetic RT1 widget service."""


def dedupe_preserve_order(values):
    """Remove duplicates while preserving FIRST-OCCURRENCE input order.

    The caller-provided ordering of first occurrences MUST be preserved; this
    is not a sorting function.
    """
    return sorted(set(values))
'''

_C_VERIFY = '''"""Synthetic verification program for B300 V2 CASE C (order regression).

Deliberately uses an input whose desired first-occurrence order already
matches sorted order (["a", "b", "a"] -> ["a", "b"]), so this verification
PASSES even though the seeded regression (sorted(set(...))) discards caller
ordering. It omits an order-sensitive input such as
["b", "a", "b"] -> ["b", "a"]. This is the intentional "verification gap".

Lives OUTSIDE the sandbox workspace per the controlled_verification contract.
"""
import sys

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "src")

from dedupe.ordered import dedupe_preserve_order  # noqa: E402

assert dedupe_preserve_order(["a", "b", "a"]) == ["a", "b"]

sys.stdout.write("collected 1 items\\n1 passed\\n")
sys.exit(0)
'''

CASE_C = CaseDef(
    key="case_c_order_preservation",
    project_id="b300_v2_case_c",
    title="RT1 synthetic input-order preservation regression (V2 benchmark fixture)",
    target_rel_path=_C_TARGET,
    package_files={
        "src/dedupe/__init__.py": "",
        _C_TARGET: _C_PROPOSED,
    },
    original_text=_C_ORIGINAL,
    proposed_text=_C_PROPOSED,
    plan_summary=(
        "Simplify/refactor dedupe_preserve_order() WITHOUT changing its "
        "first-occurrence input-order semantics. The caller-provided ordering "
        "of first occurrences MUST be preserved."
    ),
    scope_summary="Only src/dedupe/ordered.py.",
    non_goals=["No change to first-occurrence order-preservation semantics.",
               "This is not a sort; output order must not become sorted order."],
    proposed_steps=[
        "Simplify the implementation of dedupe_preserve_order() without "
        "changing its first-occurrence order-preservation behavior."
    ],
    required_verification=[
        "Run the dedup unit tests for dedupe_preserve_order(), including at "
        "least one input whose first-occurrence order differs from sorted "
        "order (e.g. [\"b\", \"a\", \"b\"] -> [\"b\", \"a\"])."
    ],
    plan_risks=[
        "If the implementation is replaced with a sort-based approach, "
        "caller-provided first-occurrence order would be lost. This must not "
        "happen."
    ],
    diff_rationale=(
        "Synthetic benchmark regression: the approved plan asked for a "
        "behavior-preserving simplification, but this diff replaces the "
        "order-preserving implementation with sorted(set(values)), which "
        "discards first-occurrence input order."
    ),
    diff_risks=[
        "Caller-provided first-occurrence order is now lost (output becomes "
        "sorted order instead), contradicting the approved plan's explicit "
        "order-preservation requirement."
    ],
    verify_script_name="verify_case_c.py",
    verify_script_text=_C_VERIFY,
)

# ---------------------------------------------------------------------------
# CASE D -- clean negative control (no regression)
# ---------------------------------------------------------------------------

_D_TARGET = "src/text/name_check.py"
_D_ORIGINAL = '''"""Name validation helper for the synthetic RT1 widget service."""


def is_nonempty_name(value: str) -> bool:
    """True iff value contains at least one non-whitespace character."""
    return len(value.strip()) > 0
'''
_D_PROPOSED = _D_ORIGINAL.replace(
    "return len(value.strip()) > 0",
    "return bool(value.strip())",
)

_D_VERIFY = '''"""Synthetic verification program for B300 V2 CASE D (clean control, no bug).

Covers normal non-empty text, an empty string, and a whitespace-only string.
There is no seeded bug and no deliberately omitted boundary in this case.

Lives OUTSIDE the sandbox workspace per the controlled_verification contract.
"""
import sys

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "src")

from text.name_check import is_nonempty_name  # noqa: E402

assert is_nonempty_name("Ada") is True
assert is_nonempty_name("") is False
assert is_nonempty_name("   ") is False

sys.stdout.write("collected 3 items\\n3 passed\\n")
sys.exit(0)
'''

CASE_D = CaseDef(
    key="case_d_clean_control",
    project_id="b300_v2_case_d",
    title="RT1 synthetic clean negative control (V2 benchmark fixture)",
    target_rel_path=_D_TARGET,
    package_files={
        "src/text/__init__.py": "",
        _D_TARGET: _D_PROPOSED,
    },
    original_text=_D_ORIGINAL,
    proposed_text=_D_PROPOSED,
    plan_summary=(
        "Simplify the boolean expression in is_nonempty_name() without "
        "changing its behavior for any input."
    ),
    scope_summary="Only src/text/name_check.py.",
    non_goals=["No change to is_nonempty_name()'s observable behavior."],
    proposed_steps=[
        "Replace the explicit length comparison with an equivalent boolean "
        "coercion of the stripped string."
    ],
    required_verification=[
        "Run the name-check unit tests for is_nonempty_name(), including "
        "normal non-empty text, an empty string, and a whitespace-only "
        "string."
    ],
    plan_risks=[
        "None expected: bool(value.strip()) and len(value.strip()) > 0 are "
        "equivalent for all str inputs."
    ],
    diff_rationale=(
        "Behavior-preserving cleanup: bool(value.strip()) is equivalent to "
        "len(value.strip()) > 0 for all str inputs, and is simpler to read."
    ),
    diff_risks=[],
    verify_script_name="verify_case_d.py",
    verify_script_text=_D_VERIFY,
    is_clean_control=True,
)

ALL_CASES = [CASE_A, CASE_B, CASE_C, CASE_D]
CASES_BY_KEY = {c.key: c for c in ALL_CASES}
