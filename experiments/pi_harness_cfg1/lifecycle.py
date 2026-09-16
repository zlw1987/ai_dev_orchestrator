"""Lifecycle step vocabulary and the Sec. 17 closure predicates.

Design Sec. 16.2 (the L0-L30 step names), Sec. 17 (per-resource "closed iff"
predicates), and Sec. 22.3's requirement that ``lifecycle_all_closed`` equal
the conjunction of its component bools -- with "not created" counting as
closed -- and that ``lifecycle_failure_steps`` be empty iff it is true.

**Closure is proven, never assumed.** Every predicate below is a conjunction
of facts AIDO itself observed about a resource IT created and holds a handle
to. None of them is ever satisfied by a name, a PID, a path string, or a file
on disk. And none of them claims anything about descendants: a closed runtime
means AIDO observed the DIRECT child's exit status and both reader EOFs --
never that inference stopped, that GPU work stopped, or that any descendant
died.
"""

from __future__ import annotations

from typing import Mapping

#: Every lifecycle step, in order. Used for ``refused_at_step`` and for
#: ``lifecycle_failure_steps``, so a record can never name a step this design
#: does not define.
LIFECYCLE_STEPS: tuple[str, ...] = tuple(f"L{index}" for index in range(0, 31))

#: The steps at which a run may be REFUSED PRE-DISPATCH (Sec. 16.2). L0 is
#: admission (a stage-level decision, never a run refusal) and L19 onward are
#: all post-dispatch, so the refusal window is exactly L1..L18.
REFUSAL_STEPS: frozenset[str] = frozenset(f"L{index}" for index in range(1, 19))

#: The steps that may appear in ``lifecycle_failure_steps``. Each names the
#: step that OWNS the closure fact which failed, never the step that first
#: noticed it -- which is why an L2 partial workspace mint surfaces here as
#: ``L27`` (workspace closure unproven), not as ``L2``. Exactly the set
#: :func:`compute_lifecycle_closure` can derive, so a record carrying any other
#: step name fails the validator's independent recomputation.
LIFECYCLE_FAILURE_STEPS: frozenset[str] = frozenset(
    {"L21", "L23", "L24", "L26", "L27"}
)


def compute_lifecycle_closure(facts: Mapping[str, object]) -> tuple[bool, tuple[str, ...]]:
    """Sec. 17's closure predicates, as one conjunction plus its failure steps.

    Returns ``(lifecycle_all_closed, sorted_failure_steps)``. Recomputed
    independently by the run-record validator from the record's own fields, so
    an assembled value that disagrees with its own components is refused rather
    than trusted (Sec. 22.1 item 7).

    "Not created counting as closed" is applied exactly where Sec. 17's own
    partial-creation column allows it: a runtime that was never launched has no
    exit status to observe, and a broker whose resource was never created has
    nothing to close. Scrub and workspace facts carry their own "or nothing was
    written / nothing was minted" meaning in the executor that sets them.
    """
    failures: set[str] = set()

    runtime_created = facts["runtime_created"] is True
    if runtime_created:
        if facts["runtime_exit_observed"] is not True:
            failures.add("L21")
        if facts["runtime_transport_eof_observed"] is not True:
            failures.add("L21")

    broker_created = facts["broker_resource_created"] is True
    if broker_created:
        if facts["broker_state_closed"] is not True:
            failures.add("L23")
        if facts["broker_pending_unreaped_zero"] is not True:
            failures.add("L23")
        if facts["broker_worker_terminated_or_absent"] is not True:
            failures.add("L23")

    if facts["generated_config_scrub_verified"] is not True:
        failures.add("L24")
    if facts["extension_binding_scrub_verified"] is not True:
        failures.add("L24")

    if facts["verification_child_reaped_or_not_started"] is not True:
        failures.add("L26")

    if facts["workspace_authority_reproved"] is not True:
        failures.add("L27")
    if facts["workspace_removed_verified"] is not True:
        failures.add("L27")
    residual = facts["workspace_residual_file_count"]
    if type(residual) is not int or residual != 0:
        failures.add("L27")

    return (not failures), tuple(sorted(failures))
