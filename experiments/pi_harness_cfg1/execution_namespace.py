"""The G9 bound execution-namespace absence PRECHECK primitive (PE-2c, C-27).

Implements ``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md``
Sec. 22.4 steps 1-3 as ONE audited primitive a future, separately authorized
PE-6 launcher calls with its single ``BOUND_STAGE_EXECUTION_ID`` constant. It
is **not** the launcher, is called by nothing in this package, and establishes
no authority of any kind.

**Waste avoidance only.** It answers one question -- "is
``RESULTS_ROOT\\<id>`` absent right now?" -- so a launcher can refuse BEFORE
the irreversible authorization-consumption call. It creates nothing, writes
nothing, never calls ``establish_stage_output_authority``, and grants nothing:
``establish_stage_output_authority`` remains independently fail-closed on an
existing execution directory (CFG1 Sec. 16.3.6). A namespace created by another
process AFTER this precheck and before establishment still makes establishment
refuse -- after consumption. That filesystem TOCTOU window is the accepted
residual R-NAMESPACE-RACE (PE-1 Sec. 27), stated and NOT solved here.

**The id is the only input.** The results root is never a parameter: it is
:mod:`stage_output`'s own audited derivation, re-proved here read-only (Level A
then Level B, ``create_if_absent=False``) exactly as every consumption-boundary
re-proof does. The candidate is formed by ``ntpath.join`` of that proven root
and an id that has already passed the frozen grammar, and is observed with the
no-follow inspection leaf -- a reparse point is reported as itself, never
followed.
"""

from __future__ import annotations

import ntpath

from . import pi_fs_leaves, stage_output
from .pi_fs_leaves import CLASSIFICATION_MISSING, CLASSIFICATIONS, NoFollowObservation

#: PE-1 Sec. 22.4 step 1 / Sec. 23.1a: execution ids that are burned and may
#: never name a fresh stage execution. ``CFG1-S1-A4`` is WITHDRAWN BEFORE
#: CONSUMPTION / HISTORICAL ONLY / MUST NOT EXECUTE.
BURNED_STAGE_EXECUTION_IDS: frozenset[str] = frozenset(
    {"CFG1-S1-A1", "CFG1-S1-A2", "CFG1-S1-A3", "CFG1-S1-A4"}
)

#: The ONE pass code: the bound namespace was observed absent.
G9_EXECUTION_NAMESPACE_ABSENT = "G9_EXECUTION_NAMESPACE_ABSENT"
#: The id is not an exact ``str`` in the frozen grammar, or is burned.
G9_BOUND_ID_INVALID = "G9_BOUND_ID_INVALID"
#: Something -- a directory, a file, a reparse point, anything -- occupies it.
G9_EXECUTION_NAMESPACE_OCCUPIED = "G9_EXECUTION_NAMESPACE_OCCUPIED"
#: The results root could not be re-proved, or the observation failed.
G9_EXECUTION_NAMESPACE_UNOBSERVABLE = "G9_EXECUTION_NAMESPACE_UNOBSERVABLE"

#: Exactly four closed codes. Console-only for the launcher; never a durable
#: record value, never consumed by any runtime step.
G9_PRECHECK_CODES: frozenset[str] = frozenset(
    {
        G9_EXECUTION_NAMESPACE_ABSENT,
        G9_BOUND_ID_INVALID,
        G9_EXECUTION_NAMESPACE_OCCUPIED,
        G9_EXECUTION_NAMESPACE_UNOBSERVABLE,
    }
)


def precheck_bound_execution_namespace(stage_execution_id: object, /) -> str:
    """G9 steps 1-3. Returns exactly one of :data:`G9_PRECHECK_CODES`. Total.

    1. ``type(id) is str``, ``fullmatch [A-Za-z0-9_-]{1,64}`` (the SAME
       pattern object establishment enforces), and not a burned id -- else
       ``G9_BOUND_ID_INVALID``, before any filesystem access;
    2. ``RESULTS_ROOT`` is :mod:`stage_output`'s own audited derivation,
       re-proved read-only -- any provenance failure (including an absent
       root) is ``G9_EXECUTION_NAMESPACE_UNOBSERVABLE``;
    3. ``ntpath.join(RESULTS_ROOT, id)`` observed no-follow: missing -> pass;
       directory / file / reparse point / other -> occupied; a malformed
       observation or a raise -> unobservable.

    Creates nothing, writes nothing, establishes nothing, and never calls
    ``establish_stage_output_authority``.
    """
    if (
        type(stage_execution_id) is not str
        or stage_output.STAGE_EXECUTION_ID_PATTERN.fullmatch(stage_execution_id) is None
        or stage_execution_id in BURNED_STAGE_EXECUTION_IDS
    ):
        return G9_BOUND_ID_INVALID
    try:
        results_root = stage_output._establish_results_root(create_if_absent=False)
    except Exception:  # noqa: BLE001 - an unprovable root is unobservable
        return G9_EXECUTION_NAMESPACE_UNOBSERVABLE
    if type(results_root) is not str:
        return G9_EXECUTION_NAMESPACE_UNOBSERVABLE
    candidate = ntpath.join(results_root, stage_execution_id)
    try:
        observation = pi_fs_leaves.inspect_no_follow(candidate)
    except Exception:  # noqa: BLE001 - an observation failure is unobservable
        return G9_EXECUTION_NAMESPACE_UNOBSERVABLE
    if type(observation) is not NoFollowObservation:
        return G9_EXECUTION_NAMESPACE_UNOBSERVABLE
    classification = observation.classification
    if type(classification) is not str or classification not in CLASSIFICATIONS:
        return G9_EXECUTION_NAMESPACE_UNOBSERVABLE
    if classification == CLASSIFICATION_MISSING:
        return G9_EXECUTION_NAMESPACE_ABSENT
    return G9_EXECUTION_NAMESPACE_OCCUPIED
