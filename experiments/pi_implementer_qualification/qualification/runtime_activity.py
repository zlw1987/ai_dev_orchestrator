"""5F3B-HARNESS-OBS1 -- the durable runtime-activity COMPANION artifact.

**OFFLINE ONLY. This module launches nothing, opens no socket, calls no
model, and reads no credential.** It reads exactly two kinds of thing: an
already-absorbed, in-memory ``ar2.supervisor.RuntimeActivity`` projection
(bounded ints/bools only), and the bytes of an artifact THIS SAME attempt
already wrote, opened read-only.

Authority: ``docs/PHASE_5F3B_HARNESS_OBS1_RUNTIME_ACTIVITY_COMPANION_DESIGN.md``
(FU1/FU2/FU3/FU4) and ``docs/PHASE_5F3B_HARNESS_OBS1_CONTRACT_A1_PHASE2_OBSERVATION_AMENDMENT.md``.

**This artifact has NO authority of any kind.**

```text
PRIMARY (or ATTEMPT, or REFUSAL) ARTIFACT
    authority: scoring, hard bar, run validity, classification, Git truth
    knows nothing about the companion            <-- one-directional, no cycle
          ^
          | bound by: emitted-bytes SHA-256 + filename + identity tuple
          |
COMPANION ARTIFACT
    authority: NONE. observational provenance only.
```

The primary qualification record stays ``pi-implementer-qualification.v2``,
byte-identical in meaning and shape; there is no ``.v3`` and no lineage
change (design Sec. 2). The companion is a SEPARATE lineage,
:data:`~qualification.ACTIVITY_RECORD_VERSION`, whose ``record_kind`` is
deliberately unequal to all three known primary kinds, so
``lineage._require_run_record_shape`` already refuses a companion handed
where a run record was claimed -- with no edit to ``lineage.py``.

**Absence of a companion is NEVER evidence that no tool call occurred.**
Every ``UNAVAILABLE_*``/``REFUSED_*`` disposition means exactly "runtime
activity evidence unavailable" and nothing else (design Sec. 12.4).

**The three exception types here are narrow and SINGLE-ORIGIN by design**
(design Sec. 12.2/12.3, FU4). :class:`PrimaryArtifactUnavailableError` is
raised at the primary-read operation and NOWHERE else, so a structurally
identical ``OSError`` raised LATER by the companion's own write can never be
misclassified as "the primary is missing" merely by sharing a Python
superclass. There is no ``except OSError:`` and no ``except FileNotFoundError:``
anywhere in :func:`_attempt_runtime_activity_companion`'s except chain, and
exactly ONE generic ``except Exception:`` clause exists in this whole module
-- inside that one containment boundary. ``BaseException`` subclasses
(``KeyboardInterrupt``, ``SystemExit``, ``GeneratorExit``) are never caught
and always propagate.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from ar2.supervisor import RunBounds

from . import ACTIVITY_RECORD_VERSION, PACKAGE_ID, QUALIFICATION_POLICY_REVISION
from .records import CANDIDATE_MODEL_IDS, RECORD_KIND, TRUST_NAMESPACES
from .safety import (
    ArtifactSafetyContext,
    EvidencePathCollisionError,
    emit_evidence_or_refuse,
)

__all__ = (
    "ACTIVITY_RECORD_KIND",
    "ACTIVITY_TOOL_CATEGORIES",
    "ATTEMPT_RECORD_KIND",
    "ActivityRecordInvariantError",
    "AttemptIdentity",
    "MAX_ACTIVITY_TOOL_COUNT",
    "PrimaryArtifactUnavailableError",
    "RuntimeActivityCompanionDisposition",
    "RuntimeToolActivitySnapshot",
    "REFUSAL_RECORD_KIND",
    "TOOL_ALLOWLIST",
    "UnboundPrimaryError",
    "build_activity_companion_record",
    "emit_activity_companion_or_refuse",
    "project_runtime_tool_activity",
    "verify_activity_companion_binding",
)


#: The companion's own ``record_kind``. Deliberately UNEQUAL to
#: ``records.RECORD_KIND``, to ``semantic_attempt.ATTEMPT_RECORD_KIND`` and to
#: the refusal kind, so every existing consumer that pins one of those already
#: refuses a companion handed in its place.
ACTIVITY_RECORD_KIND = "qualification runtime activity companion"

#: ``qualification.semantic_attempt.ATTEMPT_RECORD_KIND`` and
#: ``qualification.safety.build_refusal_record``'s own ``record_kind`` literal,
#: each duplicated as a VALUE -- never imported -- per this package's
#: established precedent (see ``i2b_live_adapters.TOOL_ALLOWLIST``'s own
#: declaration note). Duplication here is not a style preference: this module
#: is imported by ``semantic_session``, which ``semantic_attempt`` itself
#: imports, so importing either symbol would create a genuine circular import.
#: Neither ``semantic_attempt.py`` nor ``safety.py`` is touched by OBS1, and
#: offline tests assert every duplicate agrees with its declaration site.
ATTEMPT_RECORD_KIND = "qualification attempt (indeterminate semantic dispatch)"
REFUSAL_RECORD_KIND = "artifact emission refusal"

#: The exactly three retained-artifact kinds a companion may ever bind to.
_KNOWN_PRIMARY_RECORD_KINDS: frozenset[str] = frozenset(
    {RECORD_KIND, ATTEMPT_RECORD_KIND, REFUSAL_RECORD_KIND}
)

#: The two kinds that carry this attempt's own identity, and can therefore be
#: cross-checked against it. The refusal record deliberately carries none
#: (``safety.build_refusal_record`` takes no payload), so no identity is ever
#: invented from it (design Sec. 10.5).
_IDENTITY_BEARING_RECORD_KINDS: frozenset[str] = frozenset(
    {RECORD_KIND, ATTEMPT_RECORD_KIND}
)

#: AR2's own tool allowlist, duplicated as a VALUE -- never imported -- per the
#: same precedent. Matched EXACTLY and CASE-SENSITIVELY: no alias table, no
#: normalization, no case folding (design Sec. 7). An offline test asserts this
#: agrees with ``i2b_live_adapters.TOOL_ALLOWLIST`` and AR2's own.
TOOL_ALLOWLIST: tuple[str, ...] = ("aido_read", "aido_edit")

#: The closed category vocabulary a projected tool call may fall into. A
#: literal tool name outside the allowlist collapses to ``unexpected_tool`` and
#: the literal itself is NEVER retained (design Sec. 7).
ACTIVITY_TOOL_CATEGORIES: tuple[str, ...] = ("aido_read", "aido_edit", "unexpected_tool")

#: Design Sec. 9.2. NOT a new invented policy number: ``RunBounds.max_events``
#: is the run's own existing, frozen, already-enforced cap on total absorbed
#: stream records, and ``tool_execution_*`` events are a strict subset of those.
#: The proven property is the inequality only -- a valid bounded run cannot
#: EXCEED this bound without triggering the existing ``RUNTIME_EVENT_CAP_EXCEEDED``
#: failure. Exceeding it here REFUSES the companion outright, never clamps.
MAX_ACTIVITY_TOOL_COUNT: int = RunBounds().max_events

#: ``qualification.semantic_session``'s own frozen broker caps, duplicated as
#: VALUES per Sec. 9.1 (its constants are module-private). An offline test
#: asserts the two agree.
_MAX_READ_OPERATIONS = 32
_MAX_EDIT_OPERATIONS = 16
_MAX_REFUSAL_EVENTS = 256

#: Design Sec. 5.3. Which completeness basis applied at the instant the
#: snapshot was taken -- populated from the turn outcome itself, never guessed
#: afterward.
CAPTURE_BASIS_AGENT_SETTLED = "agent_settled"
CAPTURE_BASIS_WAIT_ENDED_BEFORE_SETTLED = "wait_ended_before_settled"
_CAPTURE_BASES: frozenset[str] = frozenset(
    {CAPTURE_BASIS_AGENT_SETTLED, CAPTURE_BASIS_WAIT_ENDED_BEFORE_SETTLED}
)

#: The two record-stream event kinds whose per-dispatch DELTA this companion
#: retains (design Sec. 5.1). Both are already members of
#: ``semantic_live_adapters._AGENT_LOOP_EVENT_TYPES``, so the pre-dispatch
#: baseline already snapshots them.
_TOOL_EXECUTION_EVENT_TYPES: tuple[str, ...] = (
    "tool_execution_start",
    "tool_execution_end",
)

#: The fixed, literal scope statement every companion carries (design Sec. 8).
#: Contains no endpoint, host, dotted quad, URL scheme, path, or credential.
ACTIVITY_CLAIM_SCOPE = (
    "This artifact is OBSERVATIONAL PROVENANCE ONLY. It carries no scoring "
    "authority, no hard-bar input, no run-validity input, and no classification "
    "input. A tool call observed here is a request the runtime reported; it is "
    "NOT evidence that a file changed. Repository truth is Git-observed and "
    "lives only in the bound primary artifact. Tool-call counts are the "
    "runtime's own account of itself. When "
    "runtime_reported_tool_activity_capture_basis is "
    "'wait_ended_before_settled', these counts are best-effort only and may "
    "understate this turn's true tool activity. When "
    "runtime_reported_unidentified_tool_call_id_seen is true, the per-category "
    "breakdown may undercount distinct calls and misattribute the category of "
    "the collapsed entry. Absence of this artifact is NOT evidence that no tool "
    "call occurred. Controlled invocation is not sandboxed execution."
)


class ActivityRecordInvariantError(ValueError):
    """The companion's own bounded invariant-gate refusal.

    Raised for a closed-key violation (Sec. 10.2), a canonicalization failure,
    an identity mismatch, a malformed/overflowing count, a Sec. 6 cross-field
    violation, a non-derivable companion path, or a Sec. 10.4 binding
    mismatch. Every message is a FIXED sentence naming no runtime value -- no
    path, no digest, no count, no identity, no raw exception text -- in the
    exact lineage of ``records.RecordInvariantError``.
    """


class UnboundPrimaryError(ValueError):
    """The bound file WAS read successfully, and its CONTENT disqualifies it.

    Raised only at the primary-content classification step (Sec. 10.3 steps
    (4)-(5)): the bytes do not parse as a JSON object, or the declared
    ``record_kind`` is none of the three known literals. Deliberately a
    DIFFERENT type from :class:`PrimaryArtifactUnavailableError`, so "the file
    is not there / not readable" is never merged with "the file is there and
    readable, but is not a bindable primary".
    """


class PrimaryArtifactUnavailableError(Exception):
    """The bound primary artifact could not be OPENED or READ.

    Raised ONLY at the exact primary-read operation (Sec. 10.3 steps (2)-(3)),
    wrapping any ``OSError`` encountered there, and nowhere else in this
    module. That single origin is the entire point: a structurally identical
    ``OSError`` raised LATER, by the companion's OWN write, has no
    type-specific clause to be misattributed into (Sec. 12.3, FU4). The fixed
    message names no path, errno, or raw OS diagnostic.
    """


class RuntimeActivityCompanionDisposition(str, Enum):
    """The closed, eight-value companion-disposition vocabulary (Sec. 12).

    Never a free-form string. Never an input to scoring, ranking, the hard
    bar, run validity, classification, or the fingerprint.
    """

    #: The artifact exists at the derived companion path and is bound.
    EMITTED = "EMITTED"
    #: ``turn_observation`` was ``None`` -- an indeterminate dispatch or a
    #: pre-prompt refusal, where phase 2 was never entered (Sec. 5.4).
    UNAVAILABLE_NO_TURN_OBSERVATION = "UNAVAILABLE_NO_TURN_OBSERVATION"
    #: The retained primary could not be OPENED/READ at the primary-read
    #: boundary. (Never "unreadable content" -- that is the next value.)
    UNAVAILABLE_NO_PRIMARY = "UNAVAILABLE_NO_PRIMARY"
    #: The file WAS read successfully, but its content was not a valid,
    #: bindable retained artifact.
    UNAVAILABLE_UNBOUND_PRIMARY = "UNAVAILABLE_UNBOUND_PRIMARY"
    #: The companion payload failed its own gate. Never clamped or repaired.
    REFUSED_INVARIANT = "REFUSED_INVARIANT"
    #: The shared safety choke point substituted a bounded refusal record.
    REFUSED_SCRUB = "REFUSED_SCRUB"
    #: A file already existed at the derived companion path.
    REFUSED_PATH_COLLISION = "REFUSED_PATH_COLLISION"
    #: A genuinely unexpected ordinary ``Exception`` was contained at the
    #: companion boundary. No exception text, repr, traceback or path is ever
    #: retained -- only this bounded name.
    UNAVAILABLE_INTERNAL_ERROR = "UNAVAILABLE_INTERNAL_ERROR"


@dataclass(frozen=True)
class AttemptIdentity:
    """This attempt's OWN trusted identity tuple, from the controller's locals.

    Not new authority: exactly the ``candidate``/``model_id``/``task.task_id``/
    ``task.task_revision`` values ``run_semantic_task_attempt`` already used to
    build the primary record, moved from "used to compute claims before the
    call" to "passed into the call, so the call can compute the claims itself"
    (design Sec. 10.1/10.6).
    """

    candidate: str
    model_id: str
    task_id: str
    task_revision: str

    def __post_init__(self) -> None:
        from .corpus import TASKS_BY_ID

        for name in ("candidate", "model_id", "task_id", "task_revision"):
            if type(getattr(self, name)) is not str:
                raise ActivityRecordInvariantError(
                    "AttemptIdentity fields must be ordinary str values; a str "
                    "subclass that merely compares equal is refused, never coerced"
                )
        if self.candidate not in CANDIDATE_MODEL_IDS:
            raise ActivityRecordInvariantError(
                "AttemptIdentity.candidate is not one of the frozen declared "
                "candidates"
            )
        if self.model_id != CANDIDATE_MODEL_IDS[self.candidate]:
            raise ActivityRecordInvariantError(
                "AttemptIdentity.model_id does not match its candidate's frozen "
                "pairing -- a cross-candidate relabelling is refused"
            )
        task = TASKS_BY_ID.get(self.task_id)
        if task is None:
            raise ActivityRecordInvariantError(
                "AttemptIdentity.task_id is not one of the frozen corpus tasks"
            )
        if self.task_revision != task.task_revision:
            raise ActivityRecordInvariantError(
                "AttemptIdentity.task_revision does not equal that task's own "
                "frozen revision -- a revision that merely shares the task's id "
                "prefix is refused"
            )


def _require_exact_count(field_name: str, value: object, *, maximum: int) -> int:
    """Exact ``int``, never ``bool``, never truthiness, in ``[0, maximum]``.

    ``True``/``False`` are ``int`` subclasses and would otherwise pass every
    ordinary numeric check while meaning something else entirely; a float that
    happens to be integral is likewise refused rather than coerced.
    """
    if type(value) is not int or isinstance(value, bool):
        raise ActivityRecordInvariantError(
            f"{field_name} must be exactly an int -- a bool, a float, or any "
            "other lookalike is refused, never coerced. Nothing was written."
        )
    if value < 0 or value > maximum:
        raise ActivityRecordInvariantError(
            f"{field_name} is outside its declared bound -- refused outright, "
            "never clamped. Nothing was written."
        )
    return value


def _require_exact_bool(field_name: str, value: object) -> bool:
    if type(value) is not bool:
        raise ActivityRecordInvariantError(
            f"{field_name} must be exactly a bool -- a truthy non-bool is "
            "refused, never coerced. Nothing was written."
        )
    return value


def _is_exact_declared_str(value: Any, expected: str) -> bool:
    """``value`` is an ORDINARY ``str`` carrying exactly ``expected``.

    ``type(...) is str``, never ``isinstance``: a ``str`` subclass may define
    ``__eq__`` that compares equal to anything while its actual serialized
    content is something else entirely (the identical rule
    ``records._is_exact_declared_str`` already establishes).
    """
    return type(value) is str and value == expected


@dataclass(frozen=True)
class RuntimeToolActivitySnapshot:
    """ONE immutable, per-dispatch projection of the runtime's OWN tool-call
    account, taken inside ``observe_semantic_turn`` before it even returns.

    Bounded primitives only -- exact ``int``s, exact ``bool``s, and one closed
    two-value capture-basis literal. **No nested mutable container, and no
    reference to ``activity``, ``tool_calls``, or any live adapter object**, so
    mutating the supervisor's underlying dicts after construction cannot alter
    an already-constructed snapshot: there is no live reference inside it for
    such a mutation to reach (CONTRACT-A1 Sec. 6).

    Every field is a DELTA or a PROJECTION correlated to ONE dispatch (design
    Sec. 5.1/5.2), never a process-lifetime absolute count.

    ``*_call_ids`` deliberately avoids the word "start": an entry created only
    by an end event is indistinguishable, in the frozen representation, from
    one that also had a start, so no start-specific count is claimed
    (Sec. 6.2).
    """

    capture_basis: str
    tool_execution_start_events: int
    tool_execution_end_events: int
    distinct_tool_call_ids: int
    unidentified_tool_call_id_seen: bool
    aido_read_call_ids: int
    aido_read_end_observed: int
    aido_read_error_results: int
    aido_edit_call_ids: int
    aido_edit_end_observed: int
    aido_edit_error_results: int
    unexpected_tool_call_ids: int
    unexpected_tool_end_observed: int
    unexpected_tool_error_results: int

    def __post_init__(self) -> None:
        if not _is_exact_declared_str(
            self.capture_basis, CAPTURE_BASIS_AGENT_SETTLED
        ) and not _is_exact_declared_str(
            self.capture_basis, CAPTURE_BASIS_WAIT_ENDED_BEFORE_SETTLED
        ):
            raise ActivityRecordInvariantError(
                "RuntimeToolActivitySnapshot.capture_basis must be exactly one of "
                "the two declared capture-basis literals"
            )
        _require_exact_bool(
            "RuntimeToolActivitySnapshot.unidentified_tool_call_id_seen",
            self.unidentified_tool_call_id_seen,
        )
        for name in (
            "tool_execution_start_events",
            "tool_execution_end_events",
            "distinct_tool_call_ids",
            "aido_read_call_ids",
            "aido_read_end_observed",
            "aido_read_error_results",
            "aido_edit_call_ids",
            "aido_edit_end_observed",
            "aido_edit_error_results",
            "unexpected_tool_call_ids",
            "unexpected_tool_end_observed",
            "unexpected_tool_error_results",
        ):
            _require_exact_count(
                f"RuntimeToolActivitySnapshot.{name}",
                getattr(self, name),
                maximum=MAX_ACTIVITY_TOOL_COUNT,
            )
        _require_runtime_cross_field_invariants(
            tool_execution_start_events=self.tool_execution_start_events,
            tool_execution_end_events=self.tool_execution_end_events,
            distinct_tool_call_ids=self.distinct_tool_call_ids,
            aido_read_call_ids=self.aido_read_call_ids,
            aido_read_end_observed=self.aido_read_end_observed,
            aido_read_error_results=self.aido_read_error_results,
            aido_edit_call_ids=self.aido_edit_call_ids,
            aido_edit_end_observed=self.aido_edit_end_observed,
            aido_edit_error_results=self.aido_edit_error_results,
            unexpected_tool_call_ids=self.unexpected_tool_call_ids,
            unexpected_tool_end_observed=self.unexpected_tool_end_observed,
            unexpected_tool_error_results=self.unexpected_tool_error_results,
            context="RuntimeToolActivitySnapshot",
        )


def _require_runtime_cross_field_invariants(
    *,
    tool_execution_start_events: int,
    tool_execution_end_events: int,
    distinct_tool_call_ids: int,
    aido_read_call_ids: int,
    aido_read_end_observed: int,
    aido_read_error_results: int,
    aido_edit_call_ids: int,
    aido_edit_end_observed: int,
    aido_edit_error_results: int,
    unexpected_tool_call_ids: int,
    unexpected_tool_end_observed: int,
    unexpected_tool_error_results: int,
    context: str,
) -> None:
    """Design Sec. 6.2/6.3/6.4, re-derived (never inherited) at every gate.

    Only relationships SOURCE PROVES are checked here. Sec. 6.4 explicitly
    DECLINES ``distinct_tool_call_ids`` vs. ``tool_execution_start_events``
    alone, and no fixed ratio across id-less collapses is asserted.
    """
    # Sec. 6.2 -- per-category partition subset ordering.
    for ends, calls, error_results, category in (
        (aido_read_end_observed, aido_read_call_ids, aido_read_error_results, "aido_read"),
        (aido_edit_end_observed, aido_edit_call_ids, aido_edit_error_results, "aido_edit"),
        (
            unexpected_tool_end_observed,
            unexpected_tool_call_ids,
            unexpected_tool_error_results,
            "unexpected_tool",
        ),
    ):
        if ends > calls:
            raise ActivityRecordInvariantError(
                f"{context}: a category's observed ends can never exceed its own "
                "distinct call ids. Nothing was written."
            )
        if error_results > ends:
            raise ActivityRecordInvariantError(
                f"{context}: a category's error results can never exceed its own "
                "observed ends. Nothing was written."
            )
        del category
    # Sec. 6.3 -- the exact partition identity, re-derived by literally summing.
    if (
        aido_read_call_ids + aido_edit_call_ids + unexpected_tool_call_ids
        != distinct_tool_call_ids
    ):
        raise ActivityRecordInvariantError(
            f"{context}: the three tool categories must partition the distinct "
            "tool-call ids exactly. Nothing was written."
        )
    # Sec. 6.4 -- the collapse bound. Every distinct key was created by at
    # least one absorbed start or end record.
    if distinct_tool_call_ids > tool_execution_start_events + tool_execution_end_events:
        raise ActivityRecordInvariantError(
            f"{context}: distinct tool-call ids can never exceed the absorbed "
            "tool-execution start+end event total. Nothing was written."
        )
    # 5F3B-HARNESS-OBS1-IMPL-FU1 -- the TOTAL event-count bound. Sec. 9.2
    # derives MAX_ACTIVITY_TOOL_COUNT from RunBounds.max_events, the run's own
    # frozen cap on the TOTAL population of absorbed stream records for the
    # whole run. tool_execution_start and tool_execution_end are two DISJOINT
    # event kinds inside that SAME bounded population, so a truthful bounded
    # snapshot's two per-kind counts can never SUM to more than that one
    # shared ceiling -- even though each was already individually bounded by
    # it. No new cap is invented and nothing is clamped: an impossible sum is
    # refused outright, exactly like every other cross-field invariant here.
    if tool_execution_start_events + tool_execution_end_events > MAX_ACTIVITY_TOOL_COUNT:
        raise ActivityRecordInvariantError(
            f"{context}: tool-execution start+end events together can never "
            "exceed the frozen total run event-count bound. Nothing was "
            "written."
        )


def _tool_category(entry: object) -> str:
    """Collapse one ``tool_calls`` entry to the bounded category vocabulary.

    EXACT, CASE-SENSITIVE match against :data:`TOOL_ALLOWLIST`. A ``str``
    subclass that merely compares equal, a non-``str``, ``None``, a
    case-variant, a leading-space variant and a suffixed variant ALL collapse
    to ``unexpected_tool`` -- and the literal name is never retained anywhere
    (design Sec. 7).
    """
    if not isinstance(entry, Mapping):
        return "unexpected_tool"
    name = entry.get("toolName")
    if type(name) is not str:
        return "unexpected_tool"
    if name == TOOL_ALLOWLIST[0]:
        return TOOL_ALLOWLIST[0]
    if name == TOOL_ALLOWLIST[1]:
        return TOOL_ALLOWLIST[1]
    return "unexpected_tool"


def _correlated_event_delta(activity: object, baseline: object, kind: str) -> int:
    """``post_dispatch_count - frozen pre-dispatch baseline count`` (Sec. 5.1).

    A process-lifetime absolute count is NEVER persisted as a current-attempt
    fact. A negative delta is structurally impossible for the frozen AR2
    supervisor (``event_type_counts`` only ever increments, and the baseline is
    captured strictly before the one write), so it is refused rather than
    clamped if it somehow occurs.
    """
    counts = getattr(activity, "event_type_counts", None)
    if not isinstance(counts, Mapping):
        raise ActivityRecordInvariantError(
            "runtime activity projection requires the supervisor's own event-type "
            "count mapping"
        )
    baseline_counts = getattr(baseline, "agent_loop_event_counts", None)
    if not isinstance(baseline_counts, Mapping):
        raise ActivityRecordInvariantError(
            "runtime activity projection requires this dispatch's own frozen "
            "pre-dispatch baseline counts"
        )
    post = counts.get(kind, 0)
    pre = baseline_counts.get(kind, 0)
    if type(post) is not int or isinstance(post, bool):
        raise ActivityRecordInvariantError(
            "an observed event-type count must be exactly an int"
        )
    if type(pre) is not int or isinstance(pre, bool):
        raise ActivityRecordInvariantError(
            "a pre-dispatch baseline event-type count must be exactly an int"
        )
    delta = post - pre
    if delta < 0:
        raise ActivityRecordInvariantError(
            "a per-dispatch event delta can never be negative -- refused, never "
            "clamped"
        )
    return delta


def project_runtime_tool_activity(
    activity: object, baseline: object, *, turn_outcome: object
) -> RuntimeToolActivitySnapshot:
    """The ONLY place ``tool_calls`` and ``event_type_counts`` are ever read.

    Pure; retains no reference to ``activity``, ``baseline`` or any entry.
    Applies the per-dispatch baseline projection (Sec. 5.2) and the
    settled/non-settled capture-basis distinction (Sec. 5.3).

    Tool-call entries are projected ONLY from call ids ABSENT from
    ``baseline.pre_dispatch_tool_call_ids``. This is a real mechanical
    exclusion, not an assumed-empty baseline.

    **5F3B-HARNESS-OBS1-IMPL-FU1.** ``turn_outcome`` is typed ``object`` at
    this boundary because it is this exported helper's OWN caller-facing
    contract, not because any value is acceptable: before any capture basis
    is derived, ``type(turn_outcome) is SemanticTurnOutcome`` is mechanically
    established. A string, a bool, ``None``, a foreign ``Enum``, or an
    equality-forging lookalike is refused outright -- it must NEVER silently
    become the durable, plausible-looking ``wait_ended_before_settled`` fact
    the previous ``else`` branch produced for anything that was not exactly
    ``SETTLED``.
    """
    from .semantic_session import SemanticTurnOutcome

    if type(turn_outcome) is not SemanticTurnOutcome:
        raise ActivityRecordInvariantError(
            "runtime activity projection requires turn_outcome to be exactly a "
            "SemanticTurnOutcome member -- a lookalike is refused, never mapped "
            "to a capture basis. Nothing was written."
        )

    start_events = _correlated_event_delta(activity, baseline, _TOOL_EXECUTION_EVENT_TYPES[0])
    end_events = _correlated_event_delta(activity, baseline, _TOOL_EXECUTION_EVENT_TYPES[1])

    tool_calls = getattr(activity, "tool_calls", None)
    if not isinstance(tool_calls, Mapping):
        raise ActivityRecordInvariantError(
            "runtime activity projection requires the supervisor's own tool-call "
            "mapping"
        )
    pre_dispatch_ids = getattr(baseline, "pre_dispatch_tool_call_ids", None)
    if not isinstance(pre_dispatch_ids, frozenset):
        raise ActivityRecordInvariantError(
            "runtime activity projection requires this dispatch's own frozen "
            "pre-dispatch tool-call id snapshot"
        )

    tallies: dict[str, dict[str, int]] = {
        category: {"call_ids": 0, "end_observed": 0, "error_results": 0}
        for category in ACTIVITY_TOOL_CATEGORIES
    }
    distinct = 0
    unidentified_seen = False
    for call_id, entry in tool_calls.items():
        if call_id in pre_dispatch_ids:
            continue
        distinct += 1
        if call_id == "":
            unidentified_seen = True
        bucket = tallies[_tool_category(entry)]
        bucket["call_ids"] += 1
        if isinstance(entry, Mapping) and "isError" in entry:
            bucket["end_observed"] += 1
            if entry.get("isError") is True:
                bucket["error_results"] += 1

    basis = (
        CAPTURE_BASIS_AGENT_SETTLED
        if turn_outcome is SemanticTurnOutcome.SETTLED
        else CAPTURE_BASIS_WAIT_ENDED_BEFORE_SETTLED
    )
    return RuntimeToolActivitySnapshot(
        capture_basis=basis,
        tool_execution_start_events=start_events,
        tool_execution_end_events=end_events,
        distinct_tool_call_ids=distinct,
        unidentified_tool_call_id_seen=unidentified_seen,
        aido_read_call_ids=tallies["aido_read"]["call_ids"],
        aido_read_end_observed=tallies["aido_read"]["end_observed"],
        aido_read_error_results=tallies["aido_read"]["error_results"],
        aido_edit_call_ids=tallies["aido_edit"]["call_ids"],
        aido_edit_end_observed=tallies["aido_edit"]["end_observed"],
        aido_edit_error_results=tallies["aido_edit"]["error_results"],
        unexpected_tool_call_ids=tallies["unexpected_tool"]["call_ids"],
        unexpected_tool_end_observed=tallies["unexpected_tool"]["end_observed"],
        unexpected_tool_error_results=tallies["unexpected_tool"]["error_results"],
    )


#: The ENTIRE allowed input namespace for ``proposed_facts`` (design Sec. 10.2,
#: FU3). Nothing else may ever appear as a key, whether RESERVED (Sec. 8's
#: header/identity/binding fields -- the emitter owns and stamps every one of
#: those itself) or simply UNKNOWN (a typo, a future field added to the wrong
#: namespace). Checked by EXACT SET EQUALITY, which is the only shape that
#: catches an unknown non-reserved key with the same bounded refusal.
_ALLOWED_PROPOSED_FACTS_KEYS: frozenset[str] = frozenset(
    {
        "runtime_reported_tool_activity_available",
        "runtime_reported_tool_activity_capture_basis",
        "runtime_reported_tool_execution_start_events",
        "runtime_reported_tool_execution_end_events",
        "runtime_reported_distinct_tool_call_ids",
        "runtime_reported_unidentified_tool_call_id_seen",
        "runtime_reported_aido_read_call_ids",
        "runtime_reported_aido_read_end_observed",
        "runtime_reported_aido_read_error_results",
        "runtime_reported_aido_edit_call_ids",
        "runtime_reported_aido_edit_end_observed",
        "runtime_reported_aido_edit_error_results",
        "runtime_reported_unexpected_tool_call_ids",
        "runtime_reported_unexpected_tool_end_observed",
        "runtime_reported_unexpected_tool_error_results",
        "broker_recorded_activity_available",
        "broker_recorded_read_operation_count",
        "broker_recorded_edit_operation_count",
        "broker_recorded_edited_path_count",
        "broker_recorded_refusal_count",
    }
)

#: The header/identity/binding keys the EMITTER owns and stamps itself.
_ACTIVITY_HEADER_KEYS: frozenset[str] = frozenset(
    {
        "experiment",
        "record_version",
        "record_kind",
        "qualification_policy_revision",
        "is_review_packet",
        "reviewer_invoked",
        "scoring_authority",
        "claim_scope",
        "trust_namespaces",
        "candidate",
        "model_id",
        "task_id",
        "task_revision",
        "bound_primary_filename",
        "bound_primary_sha256",
        "bound_primary_record_kind",
        "bound_primary_identity_cross_check_performed",
    }
)

#: The FULL companion payload key set -- a strictly wider set than
#: ``_ALLOWED_PROPOSED_FACTS_KEYS`` (Sec. 10.4).
_REQUIRED_ACTIVITY_RECORD_TOP_LEVEL_KEYS: frozenset[str] = (
    _ACTIVITY_HEADER_KEYS | _ALLOWED_PROPOSED_FACTS_KEYS
)

#: The zeroed shape every ``*_available == false`` family must carry
#: (Sec. 6.1), independently re-derived at the companion's own gate rather
#: than inherited by reference from any port's validation.
_RUNTIME_ZERO_FACTS: dict[str, Any] = {
    "runtime_reported_tool_activity_capture_basis": None,
    "runtime_reported_tool_execution_start_events": 0,
    "runtime_reported_tool_execution_end_events": 0,
    "runtime_reported_distinct_tool_call_ids": 0,
    "runtime_reported_unidentified_tool_call_id_seen": False,
    "runtime_reported_aido_read_call_ids": 0,
    "runtime_reported_aido_read_end_observed": 0,
    "runtime_reported_aido_read_error_results": 0,
    "runtime_reported_aido_edit_call_ids": 0,
    "runtime_reported_aido_edit_end_observed": 0,
    "runtime_reported_aido_edit_error_results": 0,
    "runtime_reported_unexpected_tool_call_ids": 0,
    "runtime_reported_unexpected_tool_end_observed": 0,
    "runtime_reported_unexpected_tool_error_results": 0,
}

_BROKER_ZERO_FACTS: dict[str, Any] = {
    "broker_recorded_read_operation_count": 0,
    "broker_recorded_edit_operation_count": 0,
    "broker_recorded_edited_path_count": 0,
    "broker_recorded_refusal_count": 0,
}

_BROKER_COUNT_CAPS: dict[str, int] = {
    "broker_recorded_read_operation_count": _MAX_READ_OPERATIONS,
    "broker_recorded_edit_operation_count": _MAX_EDIT_OPERATIONS,
    "broker_recorded_edited_path_count": _MAX_EDIT_OPERATIONS,
    "broker_recorded_refusal_count": _MAX_REFUSAL_EVENTS,
}


def _enumerate_keys_or_refuse(proposed_facts: object, *, context: str) -> set:
    """``set(proposed_facts)``, with a BOUNDED refusal for anything hostile.

    POST-CODE ADVERSARIAL FIX. A ``proposed_facts`` that is not iterable at
    all would otherwise let an UNCONTROLLED Python ``TypeError`` out of the
    emission boundary -- the same class of defect FU3's Finding 1 identified
    for the duplicate-keyword ``TypeError``, arriving one step earlier, and
    indistinguishable from it to a reader of the traceback.

    Deliberately ``except TypeError`` and nothing wider: this module keeps
    EXACTLY ONE generic ``except Exception:`` clause, inside the containment
    boundary (design Sec. 17 item 66). A caller whose ``__iter__`` raises
    something else entirely is not an input-shape error -- it is precisely
    the "genuinely unexpected ordinary Exception" the catch-all exists for,
    and it lands on ``UNAVAILABLE_INTERNAL_ERROR`` truthfully.
    """
    try:
        return set(proposed_facts)  # type: ignore[call-overload]
    except TypeError:
        raise ActivityRecordInvariantError(
            f"{context} must be an ordinary mapping whose keys can be "
            "enumerated. Nothing was written."
        ) from None


def _require_closed_facts_keys(keys: "set[str] | frozenset[str]", *, context: str) -> None:
    """The ONE key-set check, called TWICE with two different meanings.

    Sec. 10.2 steps 1 and 3: preliminary (on ``set(proposed_facts)``, a cheap
    fail-fast that proves NOTHING and is never treated as authority) and
    AUTHORITATIVE (on ``set(facts)``, the canonical snapshot). Factored into
    one function so the two call sites can never drift into checking two
    different key sets.
    """
    if keys != _ALLOWED_PROPOSED_FACTS_KEYS:
        raise ActivityRecordInvariantError(
            f"{context} must carry EXACTLY the declared observational fact keys "
            "-- no header, identity, binding, or path field may be supplied by "
            "the caller; the emitter owns and stamps every one of those itself. "
            "Nothing was written."
        )


def _canonicalize_or_refuse(payload: object, *, context: str) -> dict[str, Any]:
    """Collapse ``payload`` through the WRITER'S OWN serialization, once.

    ``json.loads(json.dumps(..., ensure_ascii=True, sort_keys=True))`` can only
    ever produce ordinary ``dict``/``list``/``str``/``int``/``float``/``bool``/
    ``None`` objects. No ``Mapping``/``dict``/``str`` subclass survives the
    round trip: whatever ``json.dumps`` chose to walk is exactly what comes
    back, and exactly what a genuine write would have persisted.

    An unserializable or pathological shape raises the SAME bounded
    :class:`ActivityRecordInvariantError` every other gate raises -- never a
    raw ``TypeError``/``ValueError``/``RecursionError``, and never any text
    describing what made the value unserializable (``from None``, deliberately).
    """
    try:
        snapshot = json.loads(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    except (TypeError, ValueError, RecursionError):
        raise ActivityRecordInvariantError(
            f"{context} must be JSON-serializable -- by the SAME serialization "
            "configuration the writer uses -- to ever be durably emitted; refused "
            "before any check trusted its reported shape, and before any file was "
            "created. Nothing was written."
        ) from None
    if type(snapshot) is not dict:
        raise ActivityRecordInvariantError(
            f"{context} must serialize to a JSON object. Nothing was written."
        )
    return snapshot


def _canonicalize_activity_facts_or_refuse(proposed_facts: object) -> dict[str, Any]:
    """Sec. 10.3 step (9a). Produces THE canonical snapshot every later step
    consumes. After this returns, the ORIGINAL ``proposed_facts`` object is
    never read again, by this module or anything it calls."""
    return _canonicalize_or_refuse(proposed_facts, context="proposed_facts")


def _canonicalize_activity_payload_or_refuse(payload: object) -> dict[str, Any]:
    """Sec. 10.4. A DISTINCT helper from
    :func:`_canonicalize_activity_facts_or_refuse` -- one canonicalizes
    ``proposed_facts`` alone, the other the full, already-assembled payload --
    and neither is ever substituted for the other."""
    return _canonicalize_or_refuse(payload, context="the companion payload")


def _read_primary_bytes(bound_primary_path: str) -> bytes:
    """THE primary-read operation (Sec. 10.3 steps (2)-(3)).

    Opened ``"rb"`` -- read-only. Nothing reachable from this module ever opens
    the primary in a write, append, or exclusive-create mode. Every ``OSError``
    here, and ONLY here, is normalized into
    :class:`PrimaryArtifactUnavailableError`, so a later companion-WRITE
    ``OSError`` cannot be misattributed to the primary being missing.
    """
    try:
        with open(bound_primary_path, "rb") as handle:
            return handle.read()
    except OSError:
        raise PrimaryArtifactUnavailableError(
            "the bound primary artifact could not be read"
        ) from None


def _parse_json_object_or_raise(primary_bytes: bytes) -> dict[str, Any]:
    """Sec. 10.3 step (4). The file WAS read; its CONTENT is judged here."""
    try:
        parsed = json.loads(primary_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise UnboundPrimaryError(
            "the bound artifact is not a parseable JSON document"
        ) from None
    if type(parsed) is not dict:
        raise UnboundPrimaryError("the bound artifact is not a JSON object")
    return parsed


def _require_known_kind_or_raise(bound_record: Mapping[str, Any]) -> str:
    """Sec. 10.3 step (5). One of exactly the three accepted kinds."""
    kind = bound_record.get("record_kind")
    if type(kind) is not str or kind not in _KNOWN_PRIMARY_RECORD_KINDS:
        raise UnboundPrimaryError(
            "the bound artifact's record kind is none of the three known retained "
            "qualification artifact kinds"
        )
    return kind


def _require_identity_matches(
    bound_record: Mapping[str, Any], identity: AttemptIdentity
) -> None:
    """Sec. 10.3 step (6). Compared against THIS attempt's trusted identity
    only -- ``proposed_facts`` structurally cannot claim an identity at all."""
    for field_name in ("candidate", "model_id", "task_id", "task_revision"):
        declared = bound_record.get(field_name)
        if type(declared) is not str or declared != getattr(identity, field_name):
            raise ActivityRecordInvariantError(
                "the bound primary artifact's own declared identity disagrees with "
                "this attempt's trusted identity -- refused, never reconciled. "
                "Nothing was written."
            )


#: The one fixed companion-path suffix rule (Sec. 11.1). No timestamp, no
#: sequence suffix, no caller override.
_PRIMARY_PATH_EXTENSION = ".json"
_ACTIVITY_PATH_SUFFIX = ".activity.json"
_ACTIVITY_PATH_STEM_SUFFIX = ".activity"


def _derive_activity_path(bound_primary_path: str) -> str:
    """A PURE function of ``bound_primary_path`` alone.

    **ACCEPTED IMPLEMENTATION ERRATUM.** The design document illustrates this
    rule with ``assert ext == ".json"``. A bare ``assert`` is NOT used here:
    ``python -O`` strips it, which would silently remove the path-shape
    invariant. Explicit fail-closed validation raising the companion's own
    bounded exception is used instead, so the invariant holds under every
    interpreter optimization level.

    Also refuses a path that is ALREADY a companion (``*.activity.json``), so a
    companion can never be bound as though it were a primary and produce a
    ``*.activity.activity.json`` sibling.

    **5F3B-HARNESS-OBS1-IMPL-FU3.** This is the SHARED path-shape gate every
    primary filesystem access is derived through, so it is also where an
    embedded NUL byte is refused. The ``open`` builtin eventually raises its
    own ``ValueError: embedded null byte`` for such a string, but that is
    never relied on as the invariant here: a bounded, fixed-message
    :class:`ActivityRecordInvariantError` is raised BEFORE any filesystem
    operation is attempted, exactly like every other malformed-shape case
    this function already refuses.
    """
    if type(bound_primary_path) is not str or not bound_primary_path.strip():
        raise ActivityRecordInvariantError(
            "the bound primary artifact path must be a non-blank ordinary str. "
            "Nothing was written."
        )
    if "\x00" in bound_primary_path:
        raise ActivityRecordInvariantError(
            "the bound primary artifact path must not contain an embedded NUL "
            "byte. Nothing was written."
        )
    root, ext = os.path.splitext(bound_primary_path)
    if (
        ext != _PRIMARY_PATH_EXTENSION
        or not os.path.basename(root)
        or root.endswith(_ACTIVITY_PATH_STEM_SUFFIX)
    ):
        raise ActivityRecordInvariantError(
            "the bound primary artifact path is not the fixed retained-evidence "
            "'<name>.json' shape this companion's own destination is derived "
            "from, or is itself already a companion path. Nothing was written."
        )
    return root + _ACTIVITY_PATH_SUFFIX


def build_activity_companion_record(
    *,
    bound_primary_path: str,
    candidate: str,
    model_id: str,
    task_id: str,
    task_revision: str,
    bound_primary_filename: str,
    bound_primary_sha256: str,
    bound_primary_record_kind: str,
    bound_primary_identity_cross_check_performed: bool,
    **facts: Any,
) -> dict[str, Any]:
    """The invariant gate, builder half. NEVER itself the trust boundary.

    ``emit_activity_companion_or_refuse`` is this module's actual consumption/
    trust boundary; this function assembles a payload from facts that boundary
    has ALREADY twice-verified, plus binding fields that boundary computed
    itself, and then submits the assembled payload to the SAME independent
    re-derivation gate the boundary re-runs afterwards.
    """
    payload: dict[str, Any] = {
        "experiment": PACKAGE_ID,
        "record_version": ACTIVITY_RECORD_VERSION,
        "record_kind": ACTIVITY_RECORD_KIND,
        "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
        "is_review_packet": False,
        "reviewer_invoked": False,
        "scoring_authority": False,
        "claim_scope": ACTIVITY_CLAIM_SCOPE,
        "trust_namespaces": dict(TRUST_NAMESPACES),
        "candidate": candidate,
        "model_id": model_id,
        "task_id": task_id,
        "task_revision": task_revision,
        "bound_primary_filename": bound_primary_filename,
        "bound_primary_sha256": bound_primary_sha256,
        "bound_primary_record_kind": bound_primary_record_kind,
        "bound_primary_identity_cross_check_performed": (
            bound_primary_identity_cross_check_performed
        ),
        **facts,
    }
    return _require_valid_activity_payload(payload, bound_primary_path=bound_primary_path)


def _require_valid_activity_payload(
    payload: Mapping[str, Any], *, bound_primary_path: str
) -> dict[str, Any]:
    """The INDEPENDENT re-derivation gate over the FULLY ASSEMBLED payload.

    Called both at :func:`build_activity_companion_record`'s tail and,
    independently, at the emission boundary's own step (10) -- the identical
    two-call discipline ``records._require_valid_primary_payload`` already
    establishes for the primary artifact.

    **This is where a hand-built payload whose declared binding fields are
    internally self-consistent but disagree with the actual bytes at
    ``bound_primary_path`` is refused.** Nothing declared is trusted: the
    digest, the filename, the record kind and the identity cross-check flag are
    all RE-DERIVED here, by re-reading the file, and compared.

    Returns THE CANONICAL payload -- the ordinary ``dict`` the round trip
    produced -- so its caller writes exactly the object this gate inspected,
    never a caller-owned object that could still change shape afterwards.
    """
    record = _canonicalize_activity_payload_or_refuse(payload)

    keys = set(record)
    if keys != _REQUIRED_ACTIVITY_RECORD_TOP_LEVEL_KEYS:
        raise ActivityRecordInvariantError(
            "a runtime-activity companion payload must carry EXACTLY the declared "
            "top-level key set -- a missing, unknown or extra key is refused, "
            "never ignored. Nothing was written."
        )

    # -- fixed AIDO header metadata, re-derived from the declaration sites ----
    for key, expected in (
        ("experiment", PACKAGE_ID),
        ("record_version", ACTIVITY_RECORD_VERSION),
        ("record_kind", ACTIVITY_RECORD_KIND),
        ("qualification_policy_revision", QUALIFICATION_POLICY_REVISION),
        ("claim_scope", ACTIVITY_CLAIM_SCOPE),
    ):
        if not _is_exact_declared_str(record.get(key), expected):
            raise ActivityRecordInvariantError(
                "a runtime-activity companion's fixed header metadata must carry "
                "exactly the values AIDO declares. Nothing was written."
            )
    for key in ("is_review_packet", "reviewer_invoked", "scoring_authority"):
        if _require_exact_bool(f"the companion's {key}", record.get(key)) is not False:
            raise ActivityRecordInvariantError(
                "a runtime-activity companion never claims review-packet, "
                "reviewer-invoked or scoring authority. Nothing was written."
            )
    if json.dumps(record.get("trust_namespaces"), sort_keys=True) != json.dumps(
        dict(TRUST_NAMESPACES), sort_keys=True
    ):
        raise ActivityRecordInvariantError(
            "a runtime-activity companion must declare exactly the package's own "
            "trust namespaces. Nothing was written."
        )

    # -- identity: re-validated from the frozen declaration sites ------------
    identity = AttemptIdentity(
        candidate=record.get("candidate"),
        model_id=record.get("model_id"),
        task_id=record.get("task_id"),
        task_revision=record.get("task_revision"),
    )

    # -- cross-artifact binding: RE-DERIVED from the actual retained bytes ----
    expected_activity_path = _derive_activity_path(bound_primary_path)
    del expected_activity_path  # derived here only to refuse a non-derivable path
    primary_bytes = _read_primary_bytes(bound_primary_path)
    actual_sha256 = hashlib.sha256(primary_bytes).hexdigest()
    actual_filename = os.path.basename(bound_primary_path)
    bound_record = _parse_json_object_or_raise(primary_bytes)
    actual_kind = _require_known_kind_or_raise(bound_record)
    actual_cross_check = actual_kind in _IDENTITY_BEARING_RECORD_KINDS

    if not _is_exact_declared_str(record.get("bound_primary_sha256"), actual_sha256):
        raise ActivityRecordInvariantError(
            "the companion's declared bound-primary digest disagrees with the "
            "digest of the actual retained bytes -- refused, never corrected. "
            "Nothing was written."
        )
    if not _is_exact_declared_str(record.get("bound_primary_filename"), actual_filename):
        raise ActivityRecordInvariantError(
            "the companion's declared bound-primary filename disagrees with the "
            "actual retained artifact's own basename. Nothing was written."
        )
    if not _is_exact_declared_str(record.get("bound_primary_record_kind"), actual_kind):
        raise ActivityRecordInvariantError(
            "the companion's declared bound-primary record kind disagrees with the "
            "kind the actual retained artifact declares. Nothing was written."
        )
    if (
        _require_exact_bool(
            "the companion's bound_primary_identity_cross_check_performed",
            record.get("bound_primary_identity_cross_check_performed"),
        )
        is not actual_cross_check
    ):
        raise ActivityRecordInvariantError(
            "the companion's identity-cross-check claim disagrees with whether the "
            "bound artifact actually carries an identity to check. Nothing was "
            "written."
        )
    if actual_cross_check:
        _require_identity_matches(bound_record, identity)

    _require_valid_activity_facts(record)
    return record


def _require_valid_activity_facts(record: Mapping[str, Any]) -> None:
    """Sec. 6 -- availability implications, caps, and cross-field invariants,
    re-derived from the payload's OWN declared facts."""
    runtime_available = _require_exact_bool(
        "runtime_reported_tool_activity_available",
        record.get("runtime_reported_tool_activity_available"),
    )
    broker_available = _require_exact_bool(
        "broker_recorded_activity_available",
        record.get("broker_recorded_activity_available"),
    )

    if not runtime_available:
        for key, expected in _RUNTIME_ZERO_FACTS.items():
            actual = record.get(key)
            if expected is None:
                if actual is not None:
                    raise ActivityRecordInvariantError(
                        "an unavailable runtime tool-activity family must carry a "
                        "null capture basis. Nothing was written."
                    )
                continue
            if type(actual) is not type(expected) or actual != expected:
                raise ActivityRecordInvariantError(
                    "an unavailable runtime tool-activity family must carry exactly "
                    "zero/false for every one of its counts and flags. Nothing was "
                    "written."
                )
    else:
        basis = record.get("runtime_reported_tool_activity_capture_basis")
        if type(basis) is not str or basis not in _CAPTURE_BASES:
            raise ActivityRecordInvariantError(
                "an available runtime tool-activity family must declare exactly one "
                "of the two declared capture bases. Nothing was written."
            )
        _require_exact_bool(
            "runtime_reported_unidentified_tool_call_id_seen",
            record.get("runtime_reported_unidentified_tool_call_id_seen"),
        )
        for key in _RUNTIME_ZERO_FACTS:
            if key in (
                "runtime_reported_tool_activity_capture_basis",
                "runtime_reported_unidentified_tool_call_id_seen",
            ):
                continue
            _require_exact_count(key, record.get(key), maximum=MAX_ACTIVITY_TOOL_COUNT)
        _require_runtime_cross_field_invariants(
            tool_execution_start_events=record["runtime_reported_tool_execution_start_events"],
            tool_execution_end_events=record["runtime_reported_tool_execution_end_events"],
            distinct_tool_call_ids=record["runtime_reported_distinct_tool_call_ids"],
            aido_read_call_ids=record["runtime_reported_aido_read_call_ids"],
            aido_read_end_observed=record["runtime_reported_aido_read_end_observed"],
            aido_read_error_results=record["runtime_reported_aido_read_error_results"],
            aido_edit_call_ids=record["runtime_reported_aido_edit_call_ids"],
            aido_edit_end_observed=record["runtime_reported_aido_edit_end_observed"],
            aido_edit_error_results=record["runtime_reported_aido_edit_error_results"],
            unexpected_tool_call_ids=record["runtime_reported_unexpected_tool_call_ids"],
            unexpected_tool_end_observed=record[
                "runtime_reported_unexpected_tool_end_observed"
            ],
            unexpected_tool_error_results=record[
                "runtime_reported_unexpected_tool_error_results"
            ],
            context="the companion payload",
        )

    if not broker_available:
        for key, expected in _BROKER_ZERO_FACTS.items():
            actual = record.get(key)
            if type(actual) is not int or isinstance(actual, bool) or actual != expected:
                raise ActivityRecordInvariantError(
                    "an unavailable broker-activity family must carry exactly zero "
                    "for every one of its counts. Nothing was written."
                )
    else:
        for key, cap in _BROKER_COUNT_CAPS.items():
            _require_exact_count(key, record.get(key), maximum=cap)
        # Sec. 6.5 -- proven from ar2.capability's own accepted-edit path.
        if (
            record["broker_recorded_edited_path_count"]
            > record["broker_recorded_edit_operation_count"]
        ):
            raise ActivityRecordInvariantError(
                "the broker's distinct edited-path count can never exceed its own "
                "accepted edit-operation count. Nothing was written."
            )


def emit_activity_companion_or_refuse(
    proposed_facts: Mapping[str, Any],
    *,
    bound_primary_path: str,
    identity: AttemptIdentity,
    safety: ArtifactSafetyContext,
) -> dict[str, Any]:
    """THE consumption/trust boundary (design Sec. 10.3, FU2/FU3/FU4).

    ``proposed_facts`` carries the companion's OWN observed facts and nothing
    else. It is NEVER a trusted source for ``bound_primary_*`` or for an output
    path -- those keys cannot even be EXPRESSED through it (Sec. 10.2), which is
    a strictly stronger property than "expressible but rejected".

    There is deliberately **no** ``record``, ``path`` or ``activity_path``
    parameter: the companion's destination is a pure function of
    ``bound_primary_path``, computed by this callee, every time.
    """
    # (1) PRELIMINARY, NON-AUTHORITATIVE closed-key check on the RAW,
    # caller-supplied Mapping -- before bound_primary_path is even opened,
    # before any dict expansion, before any builder call. Passing this proves
    # NOTHING about what canonicalization will later produce from a hostile
    # Mapping; it is a cheap fail-fast for the ordinary-dict case.
    _require_closed_facts_keys(
        _enumerate_keys_or_refuse(proposed_facts, context="proposed_facts"),
        context="proposed_facts",
    )

    if type(identity) is not AttemptIdentity:
        raise ActivityRecordInvariantError(
            "the companion emission boundary requires this attempt's own trusted "
            "AttemptIdentity -- a lookalike is refused. Nothing was written."
        )
    if type(safety) is not ArtifactSafetyContext:
        raise ActivityRecordInvariantError(
            "the companion emission boundary requires an explicit "
            "ArtifactSafetyContext. Nothing was written."
        )

    # (2) 5F3B-HARNESS-OBS1-IMPL-FU3 -- DERIVE this companion's own
    # destination from `bound_primary_path` FIRST, strictly BEFORE any
    # primary filesystem access. `_derive_activity_path` is a PURE function
    # of `bound_primary_path` alone (Sec. 11.1); it does not need the primary
    # bytes, so there is no reason for it to run after the read that
    # `_read_primary_bytes` performs below. Running it first is what makes a
    # malformed `bound_primary_path` -- wrong type, blank, an embedded NUL
    # byte, or the wrong `<name>.json` shape -- refused before the `open`
    # builtin is ever reached: an integer here (the builtin accepts an `int`
    # as an ALREADY-OPEN file descriptor and takes ownership of it) is
    # refused without ever being consumed, read from, or closed.
    activity_path = _derive_activity_path(bound_primary_path)

    # (3)-(4) RE-READ the actual emitted file and compute its digest ITSELF.
    # The read is wrapped HERE, at the exact primary-read operation, and
    # normalized into ONE dedicated, bounded exception.
    primary_bytes = _read_primary_bytes(bound_primary_path)
    primary_sha256 = hashlib.sha256(primary_bytes).hexdigest()

    # (5)-(6) parse, and require one of exactly the three accepted kinds.
    bound_record = _parse_json_object_or_raise(primary_bytes)
    bound_kind = _require_known_kind_or_raise(bound_record)

    # (7) cross-check identity ONLY where the bound kind carries one.
    identity_cross_check_performed = bound_kind in _IDENTITY_BEARING_RECORD_KINDS
    if identity_cross_check_performed:
        _require_identity_matches(bound_record, identity)

    # (8) derive the sibling filename from the ACTUAL trusted path -- never
    # from proposed_facts (which cannot carry it) and never from
    # bound_record. `activity_path` was already derived at step (2) above and
    # is NOT re-derived here -- there is exactly one derivation per call.
    bound_primary_filename = os.path.basename(bound_primary_path)

    # (9a) CANONICALIZE. FROM THIS LINE ON, `proposed_facts` -- the ORIGINAL
    # parameter -- IS NEVER READ AGAIN, by this function or by anything it
    # calls. Every remaining step below reads ONLY `facts`.
    facts = _canonicalize_activity_facts_or_refuse(proposed_facts)

    # (9b) THE AUTHORITY CHECK -- re-validated on the CANONICAL SNAPSHOT
    # itself, not on the live Mapping a hostile caller controls. A reserved or
    # unknown key surviving canonicalization is refused HERE, as a bounded
    # ActivityRecordInvariantError, never as a Python duplicate-keyword
    # TypeError from the expansion three lines below.
    _require_closed_facts_keys(
        set(facts), context="the canonical proposed_facts snapshot"
    )

    payload = build_activity_companion_record(
        bound_primary_path=bound_primary_path,
        candidate=identity.candidate,
        model_id=identity.model_id,
        task_id=identity.task_id,
        task_revision=identity.task_revision,
        bound_primary_filename=bound_primary_filename,
        bound_primary_sha256=primary_sha256,
        bound_primary_record_kind=bound_kind,
        bound_primary_identity_cross_check_performed=identity_cross_check_performed,
        **facts,
    )

    # (10) an independent re-derivation gate over the FULLY ASSEMBLED payload
    # -- defense in depth against a payload that reached this point some other
    # way than through this function's own steps above. Its CANONICAL return
    # value is what is written, so nothing can change shape between this gate
    # and the writer.
    payload = _require_valid_activity_payload(payload, bound_primary_path=bound_primary_path)

    # (11)-(12) scrub, then exclusive-create -- the SAME shared choke point,
    # UNMODIFIED. Any OSError raised BY THIS CALL is a LATER, companion-write-
    # only failure, deliberately NOT wrapped into PrimaryArtifactUnavailableError.
    return emit_evidence_or_refuse(
        payload, path=activity_path, safety=safety, record_kind=ACTIVITY_RECORD_KIND
    )


def verify_activity_companion_binding(companion_path: str, primary_path: str) -> bool:
    """Whether the object at ``companion_path`` is a CURRENTLY VALID OBS1
    activity companion whose FULL retained binding still validates against
    the object at ``primary_path``.

    **5F3B-HARNESS-OBS1-IMPL-FU1.** The original implementation compared only
    two declared fields (``bound_primary_sha256``, ``bound_primary_filename``)
    against the current primary -- a companion whose identity, schema header,
    or `bound_primary_record_kind`/`bound_primary_identity_cross_check_performed`
    claims had been tampered with, while those two fields happened to remain
    byte-identical, still verified ``True``. That was a FALSE POSITIVE: it
    proved binding to a file, never validity of the companion itself.

    **The fix reuses the SAME shared full-payload re-derivation gate the
    emission boundary itself uses** --
    :func:`_require_valid_activity_payload` -- rather than inventing a second,
    weaker validation contract. That gate independently re-derives EVERY
    binding fact (digest, filename, record kind, identity-cross-check flag,
    and -- for a run/attempt primary -- the full candidate/model_id/task_id/
    task_revision identity match) from the ACTUAL bytes at ``primary_path``,
    and re-checks every fixed header field, the closed top-level key set, and
    every Sec. 6 cross-field invariant on the companion's own declared facts.
    For a refusal-bound companion, the identity-bearing check is correctly
    SKIPPED (a refusal carries no identity to check), exactly mirroring what
    the emission boundary itself does -- this function never fabricates a
    check the bound bytes cannot support.

    RE-READS and RE-PARSES the companion, and (via the shared gate) RE-READS
    and RE-HASHES the primary, at call time -- nothing stored is ever treated
    as self-certifying. Read-only: nothing here writes, mutates, or deletes
    either file. Returns ``False`` -- never raises, never leaks a path or raw
    exception/JSON text -- for any unreadable, unparseable, malformed, or
    tampered input on either side.

    **5F3B-HARNESS-OBS1-IMPL-FU2 -- the parameter TYPE gate.** Both
    parameters are mechanically required to be exactly ``str`` --
    ``type(...) is str``, never ``isinstance`` -- BEFORE any filesystem
    operation is attempted and before either name is ever handed to the
    ``open`` builtin. This is not merely a cosmetic input check:

    * The ``open`` builtin accepts an ``int`` as an ALREADY-OPEN file
      descriptor and takes ownership of it (closing it on exit from a
      ``with`` block, by default). A caller who -- by accident or by
      construction -- passes an integer here must never have this PURPORTED
      PATH VERIFIER consume, read from, or close a file descriptor it does
      not own. Only an exact ``str`` can ever reach that builtin here.
    * The ``open`` builtin raises a bare ``TypeError`` for ``None``,
      ``object()``, or any other non-path-shaped value. **5F3B-HARNESS-OBS1-
      IMPL-FU3 correction:** the ``open`` builtin itself ACCEPTS
      ``os.PathLike`` objects, including a ``pathlib.Path`` -- it does not
      raise for one. ``os.PathLike`` is deliberately NOT accepted HERE
      regardless: this function's own documented contract is an ordinary
      ``str`` path, not "anything the builtin accepts", so a ``pathlib.Path``
      is refused by THIS function's own exact-``str`` type gate, before
      ``open`` is ever reached -- never because the builtin would have
      rejected it. ``TypeError`` (raised by ``open`` for ``None``/``object()``)
      was not previously in this function's read-side ``except`` clause, so a
      malformed CALLER input could escape this "never raises" boolean
      function as an uncontrolled exception.
    * A ``str`` SUBCLASS is refused too, by the same ``type(...) is str``
      exact-type discipline this package already applies everywhere else
      (``_is_exact_declared_str``, ``AttemptIdentity.__post_init__``): what a
      lookalike reports and what it resolves to as a filesystem path need not
      agree.

    No coercion (``str(...)``), no ``os.PathLike`` acceptance, no truthiness.
    A malformed type returns ``False`` immediately -- zero ``open``/``read``
    calls are ever attempted for either parameter in that case.
    """
    if type(companion_path) is not str or type(primary_path) is not str:
        return False
    try:
        with open(companion_path, "rb") as handle:
            companion = json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError, RecursionError):
        return False
    if type(companion) is not dict:
        return False
    try:
        _require_valid_activity_payload(companion, bound_primary_path=primary_path)
    except (
        ActivityRecordInvariantError,
        UnboundPrimaryError,
        PrimaryArtifactUnavailableError,
    ):
        return False
    return True


def _build_proposed_facts(
    turn_observation: object, broker_activity: object
) -> dict[str, Any]:
    """Project this attempt's own observations onto the twenty declared
    observational fact keys -- and nothing else.

    Carries COUNTS ONLY from the broker: never an edited path, never a refusal
    reason, never a Git changed-path list.
    """
    from .semantic_session import BrokerActivityObservation, SemanticTurnObservation

    if type(turn_observation) is not SemanticTurnObservation:
        raise ActivityRecordInvariantError(
            "a companion's runtime facts come only from this attempt's own exact "
            "SemanticTurnObservation. Nothing was written."
        )
    snapshot = turn_observation.tool_activity
    facts: dict[str, Any] = {}
    if snapshot is None:
        facts["runtime_reported_tool_activity_available"] = False
        facts.update(_RUNTIME_ZERO_FACTS)
    else:
        if type(snapshot) is not RuntimeToolActivitySnapshot:
            raise ActivityRecordInvariantError(
                "a companion's runtime facts come only from an exact "
                "RuntimeToolActivitySnapshot. Nothing was written."
            )
        facts["runtime_reported_tool_activity_available"] = True
        facts["runtime_reported_tool_activity_capture_basis"] = snapshot.capture_basis
        facts["runtime_reported_unidentified_tool_call_id_seen"] = (
            snapshot.unidentified_tool_call_id_seen
        )
        for suffix in (
            "tool_execution_start_events",
            "tool_execution_end_events",
            "distinct_tool_call_ids",
            "aido_read_call_ids",
            "aido_read_end_observed",
            "aido_read_error_results",
            "aido_edit_call_ids",
            "aido_edit_end_observed",
            "aido_edit_error_results",
            "unexpected_tool_call_ids",
            "unexpected_tool_end_observed",
            "unexpected_tool_error_results",
        ):
            facts[f"runtime_reported_{suffix}"] = getattr(snapshot, suffix)

    if broker_activity is not None and type(broker_activity) is not BrokerActivityObservation:
        # Exact type, matching the runtime half above: a lookalike is REFUSED,
        # never quietly recorded as "no broker activity to report" -- that
        # would be a claim AIDO did not establish.
        raise ActivityRecordInvariantError(
            "a companion's broker facts come only from this attempt's own exact "
            "BrokerActivityObservation. Nothing was written."
        )
    if broker_activity is None or not broker_activity.call_succeeded:
        facts["broker_recorded_activity_available"] = False
        facts.update(_BROKER_ZERO_FACTS)
    else:
        facts["broker_recorded_activity_available"] = True
        facts["broker_recorded_read_operation_count"] = broker_activity.read_operation_count
        facts["broker_recorded_edit_operation_count"] = broker_activity.edit_operation_count
        facts["broker_recorded_edited_path_count"] = len(broker_activity.edited_paths)
        facts["broker_recorded_refusal_count"] = len(broker_activity.refusals)
    return facts


def _attempt_runtime_activity_companion(
    *,
    turn_observation: object,
    broker_activity: object,
    bound_primary_path: str,
    candidate: str,
    model_id: str,
    task_id: str,
    task_revision: str,
    safety: ArtifactSafetyContext,
) -> RuntimeActivityCompanionDisposition:
    """THE failure-containment boundary (design Sec. 12.2/12.3).

    Called exactly once, strictly AFTER ``EVIDENCE_SAFETY`` has sealed the
    primary/attempt/refusal artifact and strictly BEFORE the one genuine
    ``SemanticTaskAttemptResult(...)`` call. Every qualification-facing fact
    its caller will pass into that constructor is ALREADY fixed before this
    function is entered -- nothing in this body can reach back and change one.

    The ``except`` chain names ONLY this module's own narrow, single-origin
    exception types. There is deliberately **no** ``except OSError:`` and no
    ``except FileNotFoundError:`` here: classification is driven by WHICH
    OPERATION raised, never by which Python built-in superclass it happens to
    share with an unrelated operation.

    **This takes the four identity STRINGS, not a pre-built
    :class:`AttemptIdentity`**, and mints the identity INSIDE its own ``try``.
    The design's Sec. 12.2 pseudocode shows a pre-built ``identity``
    parameter, which the same section explicitly leaves to "implementation
    discretion" for this helper's internal decomposition; minting it here is
    strictly stronger, because ``AttemptIdentity.__post_init__`` can itself
    refuse, and a refusal raised in the CALLER's scope would propagate past
    the one genuine construction -- exactly the failure mode this boundary
    exists to prevent. Sec. 10.1's emission-boundary signature is unchanged:
    :func:`emit_activity_companion_or_refuse` still receives a genuine
    ``AttemptIdentity``.
    """
    if turn_observation is None:
        return RuntimeActivityCompanionDisposition.UNAVAILABLE_NO_TURN_OBSERVATION
    try:
        identity = AttemptIdentity(
            candidate=candidate,
            model_id=model_id,
            task_id=task_id,
            task_revision=task_revision,
        )
        proposed_facts = _build_proposed_facts(turn_observation, broker_activity)
        emission = emit_activity_companion_or_refuse(
            proposed_facts,
            bound_primary_path=bound_primary_path,
            identity=identity,
            safety=safety,
        )
    except PrimaryArtifactUnavailableError:
        # RAISED ONLY at the exact primary-read operation. A later, unrelated
        # OSError from the companion's OWN write cannot reach this clause.
        return RuntimeActivityCompanionDisposition.UNAVAILABLE_NO_PRIMARY
    except UnboundPrimaryError:
        # The file WAS read successfully; its CONTENT is what disqualifies it.
        return RuntimeActivityCompanionDisposition.UNAVAILABLE_UNBOUND_PRIMARY
    except ActivityRecordInvariantError:
        return RuntimeActivityCompanionDisposition.REFUSED_INVARIANT
    except EvidencePathCollisionError:
        # Raised ONLY by the shared safety writer's own FileExistsError
        # normalization, for the companion's OWN destination.
        return RuntimeActivityCompanionDisposition.REFUSED_PATH_COLLISION
    except Exception:
        # ANY other ordinary Exception -- most notably an OSError raised by the
        # COMPANION'S OWN WRITE (permission denied, out of space, the
        # destination's parent directory disappearing), which is deliberately
        # NOT given its own except clause: it is a LATER failure than the
        # primary read, about a DIFFERENT file, and attributing it to "the
        # primary is unavailable" would be a false claim. The exception object
        # is discarded HERE -- never stringified, never logged, never attached
        # to the disposition, never re-raised. This is the ONLY generic
        # `except Exception:` in this module.
        #
        # BaseException subclasses (KeyboardInterrupt, SystemExit,
        # GeneratorExit) are NOT listed in any clause above and therefore
        # propagate unmodified.
        return RuntimeActivityCompanionDisposition.UNAVAILABLE_INTERNAL_ERROR

    if emission["refused"]:
        return RuntimeActivityCompanionDisposition.REFUSED_SCRUB
    return RuntimeActivityCompanionDisposition.EMITTED
