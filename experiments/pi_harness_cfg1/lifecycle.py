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


# ---------------------------------------------------------------------------
# FU1 (R6 Sec. 8, AM-3) -- pi-harness-cfg1-run.v2 ONLY
# ---------------------------------------------------------------------------
#
# ``compute_lifecycle_closure`` above is the v1 predicate and stays exactly as
# shipped, so every archived v1 record keeps verifying exactly as it does
# today (A3's ``["L27"]`` included). The v2 predicate below is a separate
# function, used only for v2 records; it differs in the workspace conjunct
# alone, which is conditioned on the executor-owned, write-ahead workspace
# mint state W rather than on a path, a name, or ``refused_at_step``.

#: W, the workspace mint state (R6 Sec. 8). Closed.
WORKSPACE_MINT_NOT_ATTEMPTED = "NOT_ATTEMPTED"
WORKSPACE_MINT_ATTEMPTED_NO_AUTHORITY = "ATTEMPTED_NO_AUTHORITY"
WORKSPACE_MINT_AUTHORITY_RETURNED = "AUTHORITY_RETURNED"

WORKSPACE_MINT_STATES: frozenset[str] = frozenset(
    {
        WORKSPACE_MINT_NOT_ATTEMPTED,
        WORKSPACE_MINT_ATTEMPTED_NO_AUTHORITY,
        WORKSPACE_MINT_AUTHORITY_RETURNED,
    }
)


def compute_lifecycle_closure_v2(facts: Mapping[str, object]) -> tuple[bool, tuple[str, ...]]:
    """The v2 closure predicate: v1's, with the workspace conjunct per W.

    * ``NOT_ATTEMPTED`` -- the mint port was never called: nothing to close,
      the workspace conjunct holds;
    * ``ATTEMPTED_NO_AUTHORITY`` -- a tree may exist and no genuine authority
      reached the run: ALWAYS unproven (``L27``), and nothing is ever deleted;
    * ``AUTHORITY_RETURNED`` -- v1's unchanged predicate
      (``reproved AND removed AND residual == 0``);
    * anything else -- not a W value at all, so unproven (``L27``).

    Every other conjunct is identical to v1.
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

    mint_state = facts["workspace_mint_state"]
    if type(mint_state) is not str or mint_state not in WORKSPACE_MINT_STATES:
        failures.add("L27")
    elif mint_state == WORKSPACE_MINT_ATTEMPTED_NO_AUTHORITY:
        failures.add("L27")
    elif mint_state == WORKSPACE_MINT_AUTHORITY_RETURNED:
        if facts["workspace_authority_reproved"] is not True:
            failures.add("L27")
        if facts["workspace_removed_verified"] is not True:
            failures.add("L27")
        residual = facts["workspace_residual_file_count"]
        if type(residual) is not int or residual != 0:
            failures.add("L27")

    return (not failures), tuple(sorted(failures))
