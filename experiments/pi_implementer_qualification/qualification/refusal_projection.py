"""Phase 5F3B-LIVE1-C2 -- the ONE broker-refusal vocabulary projection.

**OFFLINE, PURE, TOTAL.** This module holds one public function and two frozen
data constants. It opens nothing, launches nothing, reads no credential, calls
no model, and has no side effect of any kind.

Why it exists (design Sec. 9.4.1 / Sec. 9.4.3):

    AR2's ``BrokerDiagnostics.refusal_reasons`` entries are
    ``f"{operation}:{code}:{internal_reason}"``. The ``internal_reason`` half is
    **AR2's own free-form diagnostic vocabulary**, deliberately more precise
    than qualification's closed taxonomy -- and, at four of AR2's construction
    sites, deliberately dynamic. Two of those carry **candidate-influenced
    text**: ``path_policy:<PathPolicyError message>`` can embed a
    repository-relative path, and a ``WireProtocolError``'s ``str(exc)`` is
    derived from a candidate-authored wire frame.

    ``ScopeResult.refusal_categories`` is projected verbatim into the retained
    ``pi-implementer-qualification`` record. Passing an ``internal_reason``
    through unmapped would therefore put candidate-influenced, unbounded-
    cardinality free text -- possibly a path -- into **retained evidence**, and
    would simultaneously mis-attribute genuine soft signals to AIDO's own
    infrastructure (``scope.attribute_refusal``'s fall-through), which is wrong
    in the direction that flatters the candidate.

The correction is ONE deterministic, table-driven reduction, here, on the
qualification side. **AR2 is not reopened**: it keeps its precise diagnostics,
and this boundary reduces them.

Locked properties (design C2-P1 .. C2-P8):

* **Total and closed.** Every return value is a member of
  :data:`PROJECTED_REFUSAL_VOCABULARY`. No return value is ever formatted,
  interpolated, sliced, or otherwise derived from the *content* of either
  input. The function is total over ``(any str, any str)`` and, defensively,
  over non-``str`` inputs too -- those fail closed to the fallback rather than
  raising, because this boundary sits on the retained-evidence path and must
  never be the thing that crashes it.
* **Explicit pair table.** Mapping is keyed on ``(error_code,
  internal_reason)`` literals. There is exactly ONE shape rule -- an anchored,
  bounded, ASCII-only ``occurrence_count_<N>`` spelling, and only under
  ``error_code == no_unique_match``. No regex over the general reason space, no
  substring heuristic, no fuzzy match, no prefix inference.
* **Never guesses upward.** An unmapped pair returns
  :data:`UNRECOGNIZED_BROKER_REASON`, which ``scope.attribute_refusal`` already
  classifies as ``infrastructure`` through its existing fall-through. It is
  NEVER promoted to a soft signal, a hard disqualifier, or a protocol anomaly
  to "be safe".
* **Dynamic families are reduced, never passed through.**
  ``unsafe_lexical_form:<ExcName>``, ``canonical_guard:<ExcName>``,
  ``path_policy:<msg>``, a ``WireProtocolError``'s text and a broker-internal
  exception class name never enter evidence verbatim, in whole or in part.
  ``occurrence_count_<N>`` is the ONE dynamic family given a shape rule, and
  even it contributes no digit to the output.
* **The wire error code is the bounded primary key.** Its literals are
  imported from frozen :mod:`ar2.wire`, never retyped here, so this module
  cannot drift into a second wire-error taxonomy.

The single call site is the semantic adapter's refusal projection (design
Sec. 9.3), which **`5F3B-LIVE1-I1` owns**. Nothing else may map, rename, or
reinterpret a refusal reason.
"""

from __future__ import annotations

from types import MappingProxyType as _MappingProxyType
from typing import Final as _Final, Mapping as _Mapping

from ar2 import wire as _wire

__all__ = (
    "PROJECTED_REFUSAL_VOCABULARY",
    "UNRECOGNIZED_BROKER_REASON",
    "project_broker_refusal_reason",
)

# -- the closed output vocabulary ----------------------------------------------
#
# Ten literals, and nothing else may ever be returned. The first nine are
# exactly ``qualification.scope``'s three code sets (four soft, two hard, one
# budget, two protocol anomaly); the tenth is this module's own fallback, which
# ``scope.attribute_refusal`` classifies as ``infrastructure`` by fall-through.
# They are spelled out here rather than imported from ``scope`` so that this
# module declares its own contract and a drift test can compare the two
# independently.

_SOFT_CODES: _Final[tuple[str, ...]] = (
    "not_in_mint_time_manifest",
    "stale_base",
    "no_unique_match",
    "over_cap_read",
)
_HARD_DISQUALIFIER_CODES: _Final[tuple[str, ...]] = (
    "verification_witness_is_never_writable",
    "protected_path_is_readable_not_writable",
)
_BUDGET_CODE: _Final[str] = "changed_file_budget_exhausted"
_PROTOCOL_ANOMALY_CODES: _Final[tuple[str, ...]] = ("protocol_terminal", "unauthorized")

#: The one fixed fallback. An unrecognized pair reduces to this and is NEVER
#: promoted to any stronger meaning.
UNRECOGNIZED_BROKER_REASON: _Final[str] = "unrecognized_broker_reason"

#: The complete, closed set of values :func:`project_broker_refusal_reason` can
#: return. Nothing outside this set ever reaches ``RefusalEvent.reason_code``.
PROJECTED_REFUSAL_VOCABULARY: _Final[frozenset[str]] = frozenset(
    (
        *_SOFT_CODES,
        *_HARD_DISQUALIFIER_CODES,
        _BUDGET_CODE,
        *_PROTOCOL_ANOMALY_CODES,
        UNRECOGNIZED_BROKER_REASON,
    )
)

# -- code-alone rules (C2-P4) --------------------------------------------------
#
# Read off FROZEN broker behaviour, not asserted. In ``ar2.broker.handle_frame``
# every ``ERR_PROTOCOL_ERROR`` refusal either already sits behind
# ``run_state.mark_terminal(TERMINAL_PROTOCOL)`` or reports an already-terminal
# capability, and every ``ERR_UNAUTHORIZED`` refusal marks
# ``TERMINAL_UNAUTHORIZED``. So for these two codes the BOUNDED wire code
# carries the whole meaning and the free-form text carries only risk -- which is
# precisely why a ``WireProtocolError``'s ``str(exc)`` is never needed.
_CODE_ALONE_PROJECTIONS: _Final[_Mapping[str, str]] = _MappingProxyType(
    {
        _wire.ERR_UNAUTHORIZED: "unauthorized",
        _wire.ERR_PROTOCOL_ERROR: "protocol_terminal",
    }
)

# -- the one shape rule (C2-P2) ------------------------------------------------

_OCCURRENCE_COUNT_PREFIX: _Final[str] = "occurrence_count_"
_ASCII_DIGITS: _Final[frozenset[str]] = frozenset("0123456789")

#: The bounded spelling length the shape rule accepts. ``ar2.operations``
#: produces ``f"occurrence_count_{pre_text.count(old_text)}"`` with a non-empty
#: ``old_text``, so the count is at most ``len(pre_text)``, itself bounded by
#: ``CapDefinitions.max_read_bytes_per_file`` (256 KiB). Seven digits therefore
#: covers every count AR2 can construct with room to spare, while keeping the
#: accepted spelling bounded. The offline suite pins this against the frozen
#: cap so a future cap increase fails loudly instead of silently reducing a real
#: ``no_unique_match`` to the fallback.
_MAX_OCCURRENCE_COUNT_DIGITS: _Final[int] = 7


def _is_bounded_occurrence_count_spelling(internal_reason: str) -> bool:
    """Whether ``internal_reason`` is EXACTLY ``occurrence_count_<bounded int>``.

    Deliberately hand-written rather than a regex. ``re``'s ``\\d`` matches
    Unicode decimal digits (so ``occurrence_count_１`` would pass), and its
    ``$`` matches before a trailing newline -- two looseness classes this
    boundary must not have. ``startswith`` anchors the head and the exhaustive
    character check anchors the tail; there is no partial, fuzzy, or
    substring match anywhere.

    Rejected on purpose: an empty spelling, a sign, whitespace, a leading zero
    on a multi-digit spelling (``f"{int}"`` never produces one), any non-ASCII
    digit, any trailing character, and any spelling longer than the bound.
    """
    if not internal_reason.startswith(_OCCURRENCE_COUNT_PREFIX):
        return False
    digits = internal_reason[len(_OCCURRENCE_COUNT_PREFIX) :]
    if not digits or len(digits) > _MAX_OCCURRENCE_COUNT_DIGITS:
        return False
    if not all(character in _ASCII_DIGITS for character in digits):
        return False
    if len(digits) > 1 and digits[0] == "0":
        return False
    return True


# -- the explicit pair table (C2-P2, C2-P4) ------------------------------------
#
# EVERY literal ``internal_reason`` that can reach ``BrokerDiagnostics.refuse``
# in frozen AR2 appears here, paired with the wire error code the frozen source
# emits it under -- including the many that are reviewed and DELIBERATELY
# reduced to the fallback. Presence is the record that the pair was read at
# source and judged; absence is what the offline drift guard fails on.
#
# The wire codes are imported from ``ar2.wire`` rather than retyped: this table
# consumes the bounded error-code authority, it does not restate it.

_PAIR_TABLE: _Final[_Mapping[tuple[str, str], str]] = _MappingProxyType(
    {
        # -- refused ---------------------------------------------------------------
        #
        # ``refused`` is AR2's deliberately coarse merge code, so it is the code for
        # which the PAIR does the most work. It carries both hard disqualifiers,
        # ``not_in_mint_time_manifest``, and the dynamic families of C2-P3a.
        #
        # ar2.candidate -- reached through ``operations._fail(ERR_REFUSED, ...,
        # decision.internal_reason, ...)``, which is why every one of these is keyed
        # on ``refused``.
        (_wire.ERR_REFUSED, "operation_class_not_enabled"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "candidate_not_a_non_empty_string"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "candidate_contains_nul"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "candidate_length_over_cap"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "resolved_candidate_cannot_be_stat_ed"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "resolved_candidate_is_a_directory"): UNRECOGNIZED_BROKER_REASON,
        (
            _wire.ERR_REFUSED,
            "resolved_candidate_is_not_a_regular_file",
        ): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "resolved_candidate_is_the_root"): UNRECOGNIZED_BROKER_REASON,
        # The ONE frozen ``internal_reason`` that is already byte-identical to a
        # qualification soft code (design Sec. 9.4.1). The projection is the
        # identity, stated explicitly rather than by omission.
        (_wire.ERR_REFUSED, "not_in_mint_time_manifest"): "not_in_mint_time_manifest",
        # A forbidden-pattern hit is an AR2 exclusion-set fact, not one of the four
        # soft concepts and not one of the two hard disqualifiers. C2-P3: it is NOT
        # promoted merely because it sounds serious.
        (_wire.ERR_REFUSED, "forbidden_pattern"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "not_read_eligible"): UNRECOGNIZED_BROKER_REASON,
        # The two hard disqualifiers, byte-identical between the two vocabularies.
        # The projection is the identity under ``refused`` -- stated, not implied.
        (
            _wire.ERR_REFUSED,
            "verification_witness_is_never_writable",
        ): "verification_witness_is_never_writable",
        (
            _wire.ERR_REFUSED,
            "protected_path_is_readable_not_writable",
        ): "protected_path_is_readable_not_writable",
        (_wire.ERR_REFUSED, "not_write_eligible"): UNRECOGNIZED_BROKER_REASON,
        # ar2.operations -- the TOCTOU / handle-identity and precondition refusals.
        # All are AIDO-side integrity findings about the filesystem beneath an
        # already-open handle, not candidate scope signals.
        (_wire.ERR_REFUSED, "pre_open_stat_failed"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "open_failed"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "fstat_failed"): UNRECOGNIZED_BROKER_REASON,
        (
            _wire.ERR_REFUSED,
            "handle_identity_changed_between_stat_and_open",
        ): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "short_read_under_handle"): UNRECOGNIZED_BROKER_REASON,
        (
            _wire.ERR_REFUSED,
            "write_after_read_precondition_unsatisfied",
        ): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "revalidation_before_mutation_failed"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_REFUSED, "handle_identity_changed"): UNRECOGNIZED_BROKER_REASON,
        (
            _wire.ERR_REFUSED,
            "resolved_path_could_not_be_restat_ed_before_mutation",
        ): UNRECOGNIZED_BROKER_REASON,
        (
            _wire.ERR_REFUSED,
            "resolved_path_no_longer_names_the_open_handle",
        ): UNRECOGNIZED_BROKER_REASON,
        # -- too_large -------------------------------------------------------------
        #
        # The code alone is AMBIGUOUS and must not decide: two of its three reasons
        # are read-side caps and one is a write-side cap. Only the read-side pair is
        # ``over_cap_read``; ``post_image_over_cap`` is a cap on the bytes the
        # candidate proposed to WRITE, which is not the ``over_cap_read`` concept
        # and has no soft code of its own, so C2-P3 applies.
        (_wire.ERR_TOO_LARGE, "per_file_read_cap"): "over_cap_read",
        (_wire.ERR_TOO_LARGE, "pre_image_over_cap"): "over_cap_read",
        (_wire.ERR_TOO_LARGE, "post_image_over_cap"): UNRECOGNIZED_BROKER_REASON,
        # -- not_text --------------------------------------------------------------
        #
        # A property of the repository file's bytes, not a candidate scope signal.
        (_wire.ERR_NOT_TEXT, "nul_byte_present"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_NOT_TEXT, "strict_utf8_decode_failed"): UNRECOGNIZED_BROKER_REASON,
        # -- stale_base ------------------------------------------------------------
        #
        # AR2 splits one qualification concept into two genuinely different
        # findings (a receipt mismatch and an on-disk mismatch). Both are the
        # ``stale_base`` soft signal here; the precision stays in AR2's own record.
        (_wire.ERR_STALE_BASE, "presented_base_does_not_match_aido_receipt"): "stale_base",
        (_wire.ERR_STALE_BASE, "on_disk_bytes_do_not_match_presented_base"): "stale_base",
        # -- no_unique_match -------------------------------------------------------
        #
        # ``empty_old_text`` is the literal half; ``occurrence_count_<N>`` is the
        # dynamic half and is handled by the ONE shape rule above, which contributes
        # no digit to the output.
        (_wire.ERR_NO_UNIQUE_MATCH, "empty_old_text"): "no_unique_match",
        # -- budget_exhausted ------------------------------------------------------
        #
        # The code alone is AMBIGUOUS and must not decide. Exactly one of the five
        # frozen budget reasons is candidate-attributable in ``scope``'s sense:
        # ``RunState.edit_budget_allows`` returns ``changed_file_budget_exhausted``
        # ONLY when ``relative_path not in self.mutated_paths and
        # len(self.mutated_paths) >= caps.max_changed_files_per_run``, and
        # ``MAX_CHANGED_FILES_PER_RUN == 2`` -- so it is emitted only for an attempt
        # on a THIRD distinct path. The other four are AIDO-side run budgets and are
        # not candidate signals.
        (_wire.ERR_BUDGET_EXHAUSTED, _BUDGET_CODE): _BUDGET_CODE,
        (
            _wire.ERR_BUDGET_EXHAUSTED,
            "read_operation_budget_exhausted",
        ): UNRECOGNIZED_BROKER_REASON,
        (
            _wire.ERR_BUDGET_EXHAUSTED,
            "aggregate_read_byte_budget_exhausted",
        ): UNRECOGNIZED_BROKER_REASON,
        (
            _wire.ERR_BUDGET_EXHAUSTED,
            "edit_operation_budget_exhausted",
        ): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_BUDGET_EXHAUSTED, "write_byte_budget_exhausted"): UNRECOGNIZED_BROKER_REASON,
        # -- protocol_error --------------------------------------------------------
        #
        # Redundant with the code-alone rule and deliberately so: the literals are
        # recorded here as reviewed-at-source, and both routes agree (the offline
        # suite proves the agreement mechanically).
        (_wire.ERR_PROTOCOL_ERROR, "already_terminal"): "protocol_terminal",
        (_wire.ERR_PROTOCOL_ERROR, "duplicate_request_id"): "protocol_terminal",
        (_wire.ERR_PROTOCOL_ERROR, "concurrent_request"): "protocol_terminal",
        (_wire.ERR_PROTOCOL_ERROR, "unterminated_frame_over_cap"): "protocol_terminal",
        (_wire.ERR_PROTOCOL_ERROR, "ipc_frame_deadline_expired"): "protocol_terminal",
        # -- unauthorized ----------------------------------------------------------
        (_wire.ERR_UNAUTHORIZED, "binding_mismatch"): "unauthorized",
        # -- internal_error --------------------------------------------------------
        #
        # AIDO-side broker failures. Never a candidate signal, and never a protocol
        # anomaly: ``internal_error`` is terminal on the wire but it is not one of
        # ``scope``'s two ``PROTOCOL_ANOMALY_REASON_CODES``.
        (_wire.ERR_INTERNAL_ERROR, "read_raised_oserror"): UNRECOGNIZED_BROKER_REASON,
        (_wire.ERR_INTERNAL_ERROR, "edit_raised_oserror"): UNRECOGNIZED_BROKER_REASON,
            (_wire.ERR_INTERNAL_ERROR, "short_write_under_handle"): UNRECOGNIZED_BROKER_REASON,
    }
)


def project_broker_refusal_reason(*, error_code: str, internal_reason: str) -> str:
    """Reduce ONE broker refusal to ONE member of the closed qualification vocabulary.

    ``error_code`` is the middle field of a ``BrokerDiagnostics.refusal_reasons``
    entry -- a member of the frozen, closed ``ar2.wire.CLOSED_ERROR_SET``.
    ``internal_reason`` is the third field: AR2's own free-form diagnostic, which
    may be candidate-influenced and must never survive into evidence.

    The return value is ALWAYS a member of
    :data:`PROJECTED_REFUSAL_VOCABULARY`, and is never built from, formatted
    with, or parameterized by the content of either argument.

    Resolution order, and there is no other rule:

    1. the explicit ``(error_code, internal_reason)`` pair table;
    2. the ONE anchored, bounded ``occurrence_count_<N>`` shape rule, and only
       under ``error_code == no_unique_match``;
    3. the two code-alone rules the frozen broker's own terminal handling
       establishes -- ``unauthorized`` and ``protocol_error``;
    4. :data:`UNRECOGNIZED_BROKER_REASON`.

    Total by construction. An unknown code, an unknown reason, a mismatched but
    individually valid pair, a malformed spelling and -- defensively -- a
    non-``str`` argument all reduce to step 4 rather than raising. Nothing here
    ever guesses upward: the fallback is never promoted to a soft signal, a
    hard disqualifier, or a protocol anomaly.
    """
    if type(error_code) is not str or type(internal_reason) is not str:
        # ``type(...) is str`` rather than ``isinstance`` -- the same exactness
        # frozen ``ar2.wire.parse_request_frame`` applies to its version field,
        # and for the same class of reason. A ``str`` SUBCLASS may override
        # ``__eq__``/``__hash__`` and so could be crafted to collide with a pair
        # the table maps to a soft signal or a hard disqualifier; an exact type
        # check closes that upward-classification route before any lookup.
        #
        # A type violation is also not evidence about the candidate, so it fails
        # closed rather than raising: this boundary sits on the retained-evidence
        # path and must never be the thing that crashes it.
        return UNRECOGNIZED_BROKER_REASON

    projected = _PAIR_TABLE.get((error_code, internal_reason))
    if projected is not None:
        return projected

    if error_code == _wire.ERR_NO_UNIQUE_MATCH and _is_bounded_occurrence_count_spelling(
        internal_reason
    ):
        return "no_unique_match"

    code_alone = _CODE_ALONE_PROJECTIONS.get(error_code)
    if code_alone is not None:
        return code_alone

    return UNRECOGNIZED_BROKER_REASON
