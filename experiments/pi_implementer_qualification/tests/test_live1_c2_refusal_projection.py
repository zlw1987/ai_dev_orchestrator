"""5F3B-LIVE1-C2 -- the broker-refusal vocabulary projection, and its drift guard.

**OFFLINE ONLY, AND PURELY STATIC.** Nothing here launches Pi or Node, opens a
broker, a named pipe or a socket, contacts B300, reads a credential, calls a
model, sends a semantic prompt, or touches a real workspace. One local,
read-only ``git show`` subprocess is intentionally used to fetch the frozen
``bbd67e7`` baseline of ``qualification.scope`` for the executable-AST
comparison below; it performs no repository or workspace write. Apart from
that one call, every test calls one pure function or parses frozen AR2 source
with :mod:`ast`. There is no filesystem write at all. Q1 and Q2 remain
unauthorized and are not exercised.

What is proved here:

* the projection's output vocabulary is CLOSED, and the function is TOTAL --
  over arbitrary strings, mismatched pairs, malformed spellings, and even
  non-``str`` arguments;
* every mapping the design names is exact, and the two code-alone rules
  (``unauthorized`` / ``protocol_error``) agree with the explicit pair table;
* the ONE ``occurrence_count_<N>`` shape rule is as narrow as specified, and
  every other dynamic AR2 reason family reduces to the fallback;
* no candidate- or runtime-controlled substring -- a path, an exception
  message, wire text, an exception class name, or a count -- can reach the
  output;
* ``qualification.scope``'s executable behaviour is unchanged (C2 edited only
  its module docstring);
* the SOURCE-DRIFT GUARD: every literal refusal reason in frozen
  ``ar2.candidate`` / ``ar2.operations`` / ``ar2.broker`` (plus the
  ``ar2.capability`` budget literals they forward) is present in the pair
  table, and every DYNAMIC construction site equals an explicitly reviewed
  inventory -- so a newly added literal AND a newly added f-string /
  ``str(exc)`` / exception-derived reason both fail loudly;
* no second refusal mapping exists anywhere in the qualification package.

The guard READS frozen AR2 source and never edits it (C2-P7).
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

import qualification.refusal_projection as projection_module
import qualification.scope as scope_module
from ar2 import wire
from ar2.capability import MAX_READ_BYTES_PER_FILE, MAX_CHANGED_FILES_PER_RUN
from qualification.refusal_projection import (
    PROJECTED_REFUSAL_VOCABULARY,
    UNRECOGNIZED_BROKER_REASON,
    project_broker_refusal_reason,
)
from qualification.scope import (
    BUDGET_EXHAUSTED_REASON_CODE,
    HARD_DISQUALIFIER_REASON_CODES,
    PROTOCOL_ANOMALY_REASON_CODES,
    SOFT_REASON_CODES,
    RefusalEvent,
    attribute_refusal,
    build_scope_result,
)

_TESTS_DIR = Path(__file__).resolve().parent
_QUALIFICATION_PACKAGE = _TESTS_DIR.parent / "qualification"
_AR2_PACKAGE = _TESTS_DIR.parents[1] / "pi_external_runtime_ar2" / "ar2"

#: The commit at which C2 began. ``qualification.scope``'s executable AST is
#: pinned against it, so a behavioural edit to that frozen module -- by C2 or by
#: anything after it -- fails loudly rather than passing as "doc-only".
_C2_BASELINE_COMMIT = "bbd67e7ebf6683b677375a01371bca6fbdbad00d"


# =============================================================================
# static source helpers -- shared by the drift guard
# =============================================================================


def _ar2_source(module_name: str) -> ast.Module:
    """Parse ONE frozen AR2 module. Read-only; AR2 is never written by this suite."""
    return ast.parse((_AR2_PACKAGE / f"{module_name}.py").read_text(encoding="utf-8"))


def _shape(node: ast.AST | None) -> str:
    """A stable, version-independent structural descriptor for one expression.

    Deliberately NOT ``ast.unparse``: its output has changed between CPython
    releases (notably for f-strings), which would make the drift inventory fail
    on an interpreter upgrade rather than on an actual AR2 change. This
    descriptor names only node kinds, identifiers and literal segments.
    """
    if node is None:
        return "<absent>"
    if isinstance(node, ast.Constant):
        return f"Constant({node.value!r})"
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(f"lit={value.value!r}")
            elif isinstance(value, ast.FormattedValue):
                parts.append(f"expr[{_shape(value.value)}]")
            else:  # pragma: no cover - defensive
                parts.append(f"other[{type(value).__name__}]")
        return "JoinedStr(" + "+".join(parts) + ")"
    if isinstance(node, ast.Name):
        return f"Name({node.id})"
    if isinstance(node, ast.Attribute):
        return f"Attribute({_shape(node.value)}.{node.attr})"
    if isinstance(node, ast.Call):
        return "Call(" + _shape(node.func) + "(" + ",".join(_shape(a) for a in node.args) + "))"
    if isinstance(node, ast.BoolOp):
        return type(node.op).__name__ + "(" + ",".join(_shape(v) for v in node.values) + ")"
    if isinstance(node, ast.Tuple):
        return "Tuple(" + ",".join(_shape(element) for element in node.elts) + ")"
    return f"{type(node).__name__}(...)"


def _enclosing_function(tree: ast.Module) -> dict[int, str]:
    names: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                names.setdefault(id(child), node.name)
    return names


def _argument(call: ast.Call, index: int, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    if len(call.args) > index:
        return call.args[index]
    return None


def _static_error_code(node: ast.AST | None) -> str | None:
    """Resolve an error-code expression to a wire literal, or ``None`` if dynamic.

    The names are resolved against frozen :mod:`ar2.wire` itself, so the guard
    consumes the bounded error-code authority instead of restating it.
    """
    if isinstance(node, ast.Name):
        value = getattr(wire, node.id, None)
        if isinstance(value, str) and value in wire.CLOSED_ERROR_SET:
            return value
    if isinstance(node, ast.Constant) and node.value in wire.CLOSED_ERROR_SET:
        return str(node.value)
    return None


def _string_returns(tree: ast.Module, function_name: str) -> set[str]:
    """Every string constant returned by one named function."""
    enclosing = _enclosing_function(tree)
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or enclosing.get(id(node)) != function_name:
            continue
        for candidate in ast.walk(node):
            if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                found.add(candidate.value)
    return found


# -- the observed refusal-reason sites, extracted mechanically -----------------


def _candidate_sites() -> list[dict[str, object]]:
    """``ar2.candidate``'s refusal reasons.

    Every one reaches the broker under ``refused``: ``ar2.operations`` forwards
    ``decision.internal_reason`` through ``_fail(ERR_REFUSED, ...)`` only, which
    :func:`test_candidate_reasons_reach_diagnostics_only_under_refused` proves
    mechanically rather than assuming.
    """
    tree = _ar2_source("candidate")
    enclosing = _enclosing_function(tree)
    sites: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id == "_refuse":
            sites.append(
                {
                    "module": "ar2.candidate",
                    "function": enclosing.get(id(node), "<module>"),
                    "refusal": True,
                    "error_code": wire.ERR_REFUSED,
                    "reason": _argument(node, 2, "reason"),
                }
            )
        elif node.func.id == "DelegatedDecision":
            permitted = _argument(node, 0, "permitted")
            is_refusal = isinstance(permitted, ast.Constant) and permitted.value is False
            sites.append(
                {
                    "module": "ar2.candidate",
                    "function": enclosing.get(id(node), "<module>"),
                    "refusal": is_refusal,
                    "error_code": wire.ERR_REFUSED if is_refusal else None,
                    "reason": _argument(node, 3, "internal_reason"),
                }
            )
    return sites


def _operations_sites() -> list[dict[str, object]]:
    tree = _ar2_source("operations")
    enclosing = _enclosing_function(tree)
    sites: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id == "_fail":
            sites.append(
                {
                    "module": "ar2.operations",
                    "function": enclosing.get(id(node), "<module>"),
                    "refusal": True,
                    "error_code": _static_error_code(_argument(node, 0, "code")),
                    "reason": _argument(node, 2, "reason"),
                }
            )
        elif node.func.id == "_ok":
            sites.append(
                {
                    "module": "ar2.operations",
                    "function": enclosing.get(id(node), "<module>"),
                    "refusal": False,
                    "error_code": None,
                    "reason": _argument(node, 2, "reason"),
                }
            )
    return sites


def _broker_sites() -> list[dict[str, object]]:
    tree = _ar2_source("broker")
    enclosing = _enclosing_function(tree)
    sites: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "refuse":
            continue
        sites.append(
            {
                "module": "ar2.broker",
                "function": enclosing.get(id(node), "<module>"),
                "refusal": True,
                "error_code": _static_error_code(_argument(node, 1, "code")),
                "reason": _argument(node, 2, "reason"),
            }
        )
    return sites


def _all_sites() -> list[dict[str, object]]:
    return _candidate_sites() + _operations_sites() + _broker_sites()


def _literal_refusal_pairs() -> set[tuple[str | None, str]]:
    """Every ``(error_code, literal reason)`` pair observed at a refusal site."""
    pairs: set[tuple[str | None, str]] = set()
    for site in _all_sites():
        reason = site["reason"]
        if not site["refusal"]:
            continue
        if isinstance(reason, ast.Constant) and isinstance(reason.value, str):
            pairs.add((site["error_code"], reason.value))  # type: ignore[arg-type]
    return pairs


def _dynamic_sites() -> set[tuple[str, str, str | None, str]]:
    """Every DYNAMIC (non-``Constant``) refusal-reason construction/forwarding site.

    Keyed by (module, enclosing function, statically determinable error code,
    structural shape) -- never by line number, so reformatting frozen AR2 does
    not produce a false failure while a genuinely new site does.
    """
    observed: set[tuple[str, str, str | None, str]] = set()
    for site in _all_sites():
        if not site["refusal"]:
            continue
        reason = site["reason"]
        if isinstance(reason, ast.Constant) and isinstance(reason.value, str):
            continue
        observed.add(
            (
                str(site["module"]),
                str(site["function"]),
                site["error_code"],  # type: ignore[arg-type]
                _shape(reason),  # type: ignore[arg-type]
            )
        )
    return observed


# =============================================================================
# THE REVIEWED INVENTORIES -- design Sec. 9.4.3.1, read at source, not memory
# =============================================================================

#: Every dynamic refusal-reason site in frozen AR2, reviewed one by one.
#:
#: ``handling`` is the reviewed disposition:
#:   ``free_text``   -- candidate/runtime-influenced text. NEVER enters evidence,
#:                      in whole or in part; reduces to the fallback, except
#:                      where the BOUNDED wire code alone already carries the
#:                      meaning (C2-P4), which is noted per entry.
#:   ``shape_rule``  -- the ONE narrowly anchored ``occurrence_count_<N>`` family.
#:   ``forwarded``   -- not a construction site at all: it forwards a reason
#:                      built elsewhere. ``literal_source`` names the frozen
#:                      function whose string constants it can carry, and the
#:                      guard requires every one of those to be in the table.
_REVIEWED_DYNAMIC_SITES: dict[tuple[str, str, str | None, str], dict[str, str]] = {
    # -- Sec. 9.4.3.1 source 1: an exception CLASS NAME -----------------------
    (
        "ar2.candidate",
        "evaluate_delegated_candidate",
        wire.ERR_REFUSED,
        "JoinedStr(lit='unsafe_lexical_form:'"
        "+expr[Attribute(Call(Name(type)(Name(exc))).__name__)])",
    ): {"handling": "free_text", "note": "CanonicalPathError subclass name"},
    # -- Sec. 9.4.3.1 source 2: an exception CLASS NAME -----------------------
    (
        "ar2.candidate",
        "evaluate_delegated_candidate",
        wire.ERR_REFUSED,
        "JoinedStr(lit='canonical_guard:'"
        "+expr[Attribute(Call(Name(type)(Name(exc))).__name__)])",
    ): {"handling": "free_text", "note": "CanonicalPathError subclass name"},
    # -- Sec. 9.4.3.1 source 3: a PathPolicyError MESSAGE, which may embed a
    #    repository-relative PATH. The most dangerous of the six.
    (
        "ar2.candidate",
        "evaluate_delegated_candidate",
        wire.ERR_REFUSED,
        "JoinedStr(lit='path_policy:'+expr[Name(exc)])",
    ): {"handling": "free_text", "note": "PathPolicyError message; may embed a path"},
    # -- Sec. 9.4.3.1 source 4: the ONE family with a shape rule --------------
    (
        "ar2.operations",
        "perform_edit",
        wire.ERR_NO_UNIQUE_MATCH,
        "JoinedStr(lit='occurrence_count_'+expr[Name(occurrences)])",
    ): {"handling": "shape_rule", "note": "candidate-determined integer count"},
    # -- Sec. 9.4.3.1 source 5: a WireProtocolError's own text, derived from a
    #    CANDIDATE-AUTHORED wire frame. The bounded code carries the meaning.
    (
        "ar2.broker",
        "handle_frame",
        wire.ERR_PROTOCOL_ERROR,
        "Call(Name(str)(Name(exc)))",
    ): {
        "handling": "free_text",
        "note": "code-alone rule decides: protocol_error -> protocol_terminal",
    },
    # -- Sec. 9.4.3.1 source 6: a broker-internal exception CLASS NAME --------
    (
        "ar2.broker",
        "handle_frame",
        wire.ERR_INTERNAL_ERROR,
        "Attribute(Call(Name(type)(Name(exc))).__name__)",
    ): {"handling": "free_text", "note": "broker-internal exception class name"},
    # -- forwarding sites: NOT construction sites, but non-Constant and so
    #    inventoried, because a change here would re-route which literals reach
    #    the diagnostics and under which code.
    (
        "ar2.candidate",
        "_refuse",
        wire.ERR_REFUSED,
        "Name(reason)",
    ): {"handling": "forwarded", "literal_source": "candidate:_refuse_call_sites"},
    (
        "ar2.operations",
        "perform_read",
        wire.ERR_REFUSED,
        "Attribute(Name(decision).internal_reason)",
    ): {"handling": "forwarded", "literal_source": "candidate:_refuse_call_sites"},
    (
        "ar2.operations",
        "perform_edit",
        wire.ERR_REFUSED,
        "Attribute(Name(decision).internal_reason)",
    ): {"handling": "forwarded", "literal_source": "candidate:_refuse_call_sites"},
    (
        "ar2.operations",
        "perform_read",
        wire.ERR_REFUSED,
        "Name(failure)",
    ): {"handling": "forwarded", "literal_source": "operations:_open_verified"},
    (
        "ar2.operations",
        "perform_edit",
        wire.ERR_REFUSED,
        "Name(failure)",
    ): {"handling": "forwarded", "literal_source": "operations:_open_verified"},
    (
        "ar2.operations",
        "perform_read",
        wire.ERR_BUDGET_EXHAUSTED,
        "Name(budget_failure)",
    ): {"handling": "forwarded", "literal_source": "capability:read_budget_allows"},
    (
        "ar2.operations",
        "perform_edit",
        wire.ERR_BUDGET_EXHAUSTED,
        "Name(budget_failure)",
    ): {"handling": "forwarded", "literal_source": "capability:edit_budget_allows"},
    # The broker's own forward of an ``OperationOutcome``. Its error code is
    # ``outcome.code or ERR_INTERNAL_ERROR`` -- NOT statically determinable, which
    # is exactly why ``ar2.operations``' own ``_fail`` call sites are the
    # authority for those pairs and are extracted separately above.
    (
        "ar2.broker",
        "handle_frame",
        None,
        "Attribute(Name(outcome).internal_reason)",
    ): {"handling": "forwarded", "literal_source": "operations:_fail_call_sites"},
}

#: Every f-string in the three modules, refusal-carrying or not. Inventoried so
#: that a NEW f-string anywhere in them -- including one that turns a currently
#: accepted reason into a refused one, or one that changes the diagnostics
#: STORAGE FORMAT the Sec. 9.3 ``split(":", 2)`` contract depends on -- fails
#: loudly rather than silently.
_REVIEWED_FSTRING_SITES: dict[tuple[str, str, str], str] = {
    (
        "ar2.candidate",
        "evaluate_delegated_candidate",
        "JoinedStr(lit='unsafe_lexical_form:'"
        "+expr[Attribute(Call(Name(type)(Name(exc))).__name__)])",
    ): "refusal reason, dynamic source 1",
    (
        "ar2.candidate",
        "evaluate_delegated_candidate",
        "JoinedStr(lit='canonical_guard:'"
        "+expr[Attribute(Call(Name(type)(Name(exc))).__name__)])",
    ): "refusal reason, dynamic source 2",
    (
        "ar2.candidate",
        "evaluate_delegated_candidate",
        "JoinedStr(lit='path_policy:'+expr[Name(exc)])",
    ): "refusal reason, dynamic source 3",
    (
        "ar2.operations",
        "perform_edit",
        "JoinedStr(lit='occurrence_count_'+expr[Name(occurrences)])",
    ): "refusal reason, dynamic source 4",
    (
        "ar2.operations",
        "perform_edit",
        "JoinedStr(lit='edit applied at offset '+expr[Name(offset)]"
        "+lit='; receipt replaced with the post-image hash')",
    ): "ACCEPTED-operation reason; never reaches diagnostics.refuse",
    (
        "ar2.broker",
        "refuse",
        "JoinedStr(expr[Name(operation)]+lit=':'+expr[Name(code)])",
    ): "the refused-operation COUNTER key; not a reason",
    (
        "ar2.broker",
        "refuse",
        "JoinedStr(expr[Name(operation)]+lit=':'+expr[Name(code)]+lit=':'+expr[Name(reason)])",
    ): "the refusal_reasons ENTRY FORMAT the Sec. 9.3 split(':', 2) depends on",
    (
        "ar2.broker",
        "_serve",
        "JoinedStr(expr[Attribute(Call(Name(type)(Name(exc))).__name__)]+lit=': '+expr[Name(exc)])",
    ): "worker_error; never reaches diagnostics.refuse (design Sec. 9.4.3.1 note)",
}

#: The literal reasons at NON-refusal sites, inventoried for the same reason.
_REVIEWED_NON_REFUSAL_LITERALS: frozenset[str] = frozenset(
    {
        "read permitted: tracked, contained, ordinary, not excluded",
        "write permitted: statically eligible; preconditions checked separately",
        "read permitted and performed through an identity-verified handle",
    }
)


# =============================================================================
# 1. the closed vocabulary, totality, and the public surface
# =============================================================================


def test_the_output_vocabulary_is_exactly_the_ten_declared_codes():
    assert PROJECTED_REFUSAL_VOCABULARY == frozenset(
        {
            "not_in_mint_time_manifest",
            "stale_base",
            "no_unique_match",
            "over_cap_read",
            "verification_witness_is_never_writable",
            "protected_path_is_readable_not_writable",
            "changed_file_budget_exhausted",
            "protocol_terminal",
            "unauthorized",
            "unrecognized_broker_reason",
        }
    )


def test_the_vocabulary_is_scopes_own_code_sets_plus_exactly_one_fallback():
    frozen_scope_codes = (
        SOFT_REASON_CODES
        | HARD_DISQUALIFIER_REASON_CODES
        | PROTOCOL_ANOMALY_REASON_CODES
        | {BUDGET_EXHAUSTED_REASON_CODE}
    )
    assert PROJECTED_REFUSAL_VOCABULARY - frozen_scope_codes == {UNRECOGNIZED_BROKER_REASON}
    assert frozen_scope_codes - PROJECTED_REFUSAL_VOCABULARY == set()


def test_every_table_entry_and_rule_returns_a_vocabulary_member():
    for value in projection_module._PAIR_TABLE.values():
        assert value in PROJECTED_REFUSAL_VOCABULARY
    for value in projection_module._CODE_ALONE_PROJECTIONS.values():
        assert value in PROJECTED_REFUSAL_VOCABULARY


def test_the_table_uses_only_the_frozen_closed_wire_error_set():
    used = {code for code, _ in projection_module._PAIR_TABLE}
    used |= set(projection_module._CODE_ALONE_PROJECTIONS)
    assert used <= wire.CLOSED_ERROR_SET, used - wire.CLOSED_ERROR_SET


def test_the_public_surface_is_one_projection_function_and_two_constants():
    public = {
        name
        for name in vars(projection_module)
        if not name.startswith("_") and name != "annotations"
    }
    assert public == {
        "project_broker_refusal_reason",
        "PROJECTED_REFUSAL_VOCABULARY",
        "UNRECOGNIZED_BROKER_REASON",
    }
    assert set(projection_module.__all__) == public
    callables = {name for name in public if callable(getattr(projection_module, name))}
    assert callables == {"project_broker_refusal_reason"}


def test_the_projection_is_total_over_adversarial_string_pairs():
    codes = [
        *sorted(wire.CLOSED_ERROR_SET),
        "",
        " refused",
        "REFUSED",
        "refused\n",
        "unknown_code",
        "protocol_terminal",
        "over_cap_read",
        "\x00",
        "refused:refused",
        "占",
        "x" * 5000,
    ]
    reasons = [
        "",
        " ",
        "\n",
        "\x00",
        "not_in_mint_time_manifest",
        "NOT_IN_MINT_TIME_MANIFEST",
        " not_in_mint_time_manifest ",
        "path_policy:units/labels.py is protected",
        r"path_policy:C:\dev\secret\thing.py",
        "canonical_guard:CanonicalPathError",
        "unsafe_lexical_form:ValueError",
        "protocol error: the request frame is not strict JSON",
        "occurrence_count_0",
        "occurrence_count_",
        "occurrence_count_-1",
        "occurrence_count_x",
        "stale_base",
        "unrecognized_broker_reason",
        "y" * 20000,
        "🙂",
    ]
    for code in codes:
        for reason in reasons:
            result = project_broker_refusal_reason(error_code=code, internal_reason=reason)
            assert isinstance(result, str)
            assert result in PROJECTED_REFUSAL_VOCABULARY, (code, reason, result)


def test_the_projection_is_keyword_only():
    with pytest.raises(TypeError):
        project_broker_refusal_reason("refused", "not_in_mint_time_manifest")  # type: ignore[misc]


@pytest.mark.parametrize(
    "error_code, internal_reason",
    [
        (None, "not_in_mint_time_manifest"),
        ("refused", None),
        (True, True),
        (1, 1),
        (b"refused", b"not_in_mint_time_manifest"),
        (["refused"], ["not_in_mint_time_manifest"]),
        (wire.ERR_REFUSED, 0),
    ],
)
def test_non_string_arguments_fail_closed_instead_of_raising(error_code, internal_reason):
    """This boundary sits on the retained-evidence path; it must not raise into it."""
    assert (
        project_broker_refusal_reason(
            error_code=error_code, internal_reason=internal_reason
        )
        == UNRECOGNIZED_BROKER_REASON
    )


class _LyingStr(str):
    """A ``str`` subclass that claims to equal -- and hash as -- something else.

    Exactly the shape a caller would need to steer an exact-pair lookup onto an
    entry the real value does not name.
    """

    def __new__(cls, actual: str, pretends_to_be: str) -> "_LyingStr":
        instance = super().__new__(cls, actual)
        instance._pretends_to_be = pretends_to_be  # type: ignore[attr-defined]
        return instance

    def __eq__(self, other: object) -> bool:
        return other == self._pretends_to_be  # type: ignore[attr-defined]

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self._pretends_to_be)  # type: ignore[attr-defined]


def test_a_lying_str_subclass_cannot_reach_a_stronger_table_entry():
    """The exact ``type(...) is str`` gate, and why ``isinstance`` was not enough.

    Without it, the crafted pair below hashes and compares equal to
    ``("refused", "verification_witness_is_never_writable")`` and would be
    projected as a HARD DISQUALIFIER despite naming neither value.
    """
    forged_code = _LyingStr("attacker", "refused")
    forged_reason = _LyingStr("attacker", "verification_witness_is_never_writable")

    # The forgery really does hit the table when looked up directly ...
    assert (
        projection_module._PAIR_TABLE.get((forged_code, forged_reason))
        == "verification_witness_is_never_writable"
    )
    # ... and the projection still refuses it.
    projected = project_broker_refusal_reason(
        error_code=forged_code, internal_reason=forged_reason
    )
    assert projected == UNRECOGNIZED_BROKER_REASON
    assert attribute_refusal(RefusalEvent(reason_code=projected)).is_hard_disqualifier is False

    # The same forgery aimed at the soft codes and the code-alone rules.
    for pretend_code, pretend_reason in (
        ("stale_base", "presented_base_does_not_match_aido_receipt"),
        ("budget_exhausted", "changed_file_budget_exhausted"),
        ("unauthorized", "binding_mismatch"),
        ("protocol_error", "already_terminal"),
        ("no_unique_match", "occurrence_count_2"),
    ):
        assert (
            project_broker_refusal_reason(
                error_code=_LyingStr("x", pretend_code),
                internal_reason=_LyingStr("y", pretend_reason),
            )
            == UNRECOGNIZED_BROKER_REASON
        ), (pretend_code, pretend_reason)


def test_the_lookup_tables_are_immutable_at_runtime():
    """No later module can inject or re-point a mapping entry in place."""
    for table in (projection_module._PAIR_TABLE, projection_module._CODE_ALONE_PROJECTIONS):
        with pytest.raises(TypeError):
            table["injected"] = "verification_witness_is_never_writable"  # type: ignore[index]
        with pytest.raises((TypeError, AttributeError)):
            table.clear()  # type: ignore[attr-defined]


def test_bool_int_equivalence_cannot_reach_a_table_entry():
    # ``True == 1`` and ``hash(True) == hash(1)`` in Python; the table is keyed on
    # str pairs, and the isinstance gate closes the door before a lookup anyway.
    assert project_broker_refusal_reason(error_code=True, internal_reason=1) == (
        UNRECOGNIZED_BROKER_REASON
    )


# =============================================================================
# 2. explicit pair semantics
# =============================================================================


@pytest.mark.parametrize(
    "internal_reason",
    [
        "binding_mismatch",
        "",
        "anything at all",
        r"path_policy:units\labels.py",
        "protocol error: the request frame is not valid UTF-8",
    ],
)
def test_unauthorized_projects_to_unauthorized_from_the_bounded_code_alone(internal_reason):
    assert (
        project_broker_refusal_reason(
            error_code=wire.ERR_UNAUTHORIZED, internal_reason=internal_reason
        )
        == "unauthorized"
    )


@pytest.mark.parametrize(
    "internal_reason",
    [
        "already_terminal",
        "duplicate_request_id",
        "concurrent_request",
        "unterminated_frame_over_cap",
        "ipc_frame_deadline_expired",
        "protocol error: the request carries unknown fields",
        "protocol error: base_sha256 is not a 64-character hex digest",
        "",
        "occurrence_count_1",
        "not_in_mint_time_manifest",
    ],
)
def test_protocol_error_projects_to_protocol_terminal_from_the_bounded_code_alone(
    internal_reason,
):
    assert (
        project_broker_refusal_reason(
            error_code=wire.ERR_PROTOCOL_ERROR, internal_reason=internal_reason
        )
        == "protocol_terminal"
    )


def test_the_code_alone_rules_agree_with_every_explicit_table_entry():
    for (code, reason), projected in projection_module._PAIR_TABLE.items():
        expected = projection_module._CODE_ALONE_PROJECTIONS.get(code)
        if expected is not None:
            assert projected == expected, (code, reason, projected)


@pytest.mark.parametrize(
    "error_code, internal_reason, expected",
    [
        # the one already-identical soft literal
        (wire.ERR_REFUSED, "not_in_mint_time_manifest", "not_in_mint_time_manifest"),
        # stale_base -- AR2 splits one concept into two genuine findings
        (
            wire.ERR_STALE_BASE,
            "presented_base_does_not_match_aido_receipt",
            "stale_base",
        ),
        (
            wire.ERR_STALE_BASE,
            "on_disk_bytes_do_not_match_presented_base",
            "stale_base",
        ),
        # no_unique_match -- the literal half
        (wire.ERR_NO_UNIQUE_MATCH, "empty_old_text", "no_unique_match"),
        # too_large -- the read-side split
        (wire.ERR_TOO_LARGE, "per_file_read_cap", "over_cap_read"),
        (wire.ERR_TOO_LARGE, "pre_image_over_cap", "over_cap_read"),
        # too_large -- the WRITE-side cap is NOT a read, and gets no soft code
        (wire.ERR_TOO_LARGE, "post_image_over_cap", UNRECOGNIZED_BROKER_REASON),
        # the two hard disqualifiers, identity under refused
        (
            wire.ERR_REFUSED,
            "verification_witness_is_never_writable",
            "verification_witness_is_never_writable",
        ),
        (
            wire.ERR_REFUSED,
            "protected_path_is_readable_not_writable",
            "protected_path_is_readable_not_writable",
        ),
        # budget_exhausted -- exactly one candidate-attributable reason
        (
            wire.ERR_BUDGET_EXHAUSTED,
            "changed_file_budget_exhausted",
            "changed_file_budget_exhausted",
        ),
        (
            wire.ERR_BUDGET_EXHAUSTED,
            "read_operation_budget_exhausted",
            UNRECOGNIZED_BROKER_REASON,
        ),
        (
            wire.ERR_BUDGET_EXHAUSTED,
            "aggregate_read_byte_budget_exhausted",
            UNRECOGNIZED_BROKER_REASON,
        ),
        (
            wire.ERR_BUDGET_EXHAUSTED,
            "edit_operation_budget_exhausted",
            UNRECOGNIZED_BROKER_REASON,
        ),
        (
            wire.ERR_BUDGET_EXHAUSTED,
            "write_byte_budget_exhausted",
            UNRECOGNIZED_BROKER_REASON,
        ),
        # not one of the four soft concepts, and never promoted to look like one
        (wire.ERR_REFUSED, "forbidden_pattern", UNRECOGNIZED_BROKER_REASON),
        (wire.ERR_REFUSED, "not_read_eligible", UNRECOGNIZED_BROKER_REASON),
        (wire.ERR_REFUSED, "not_write_eligible", UNRECOGNIZED_BROKER_REASON),
        (wire.ERR_NOT_TEXT, "nul_byte_present", UNRECOGNIZED_BROKER_REASON),
        (wire.ERR_INTERNAL_ERROR, "read_raised_oserror", UNRECOGNIZED_BROKER_REASON),
    ],
)
def test_explicit_pair_semantics(error_code, internal_reason, expected):
    assert (
        project_broker_refusal_reason(
            error_code=error_code, internal_reason=internal_reason
        )
        == expected
    )


def test_mapping_is_driven_by_the_pair_not_by_the_reason_alone():
    """A valid reason under the WRONG code never inherits the right code's meaning."""
    wrong_pairs = [
        (wire.ERR_STALE_BASE, "not_in_mint_time_manifest"),
        (wire.ERR_REFUSED, "presented_base_does_not_match_aido_receipt"),
        (wire.ERR_REFUSED, "per_file_read_cap"),
        (wire.ERR_TOO_LARGE, "changed_file_budget_exhausted"),
        (wire.ERR_BUDGET_EXHAUSTED, "verification_witness_is_never_writable"),
        (wire.ERR_NOT_TEXT, "protected_path_is_readable_not_writable"),
        (wire.ERR_NO_UNIQUE_MATCH, "not_in_mint_time_manifest"),
        (wire.ERR_STALE_BASE, "empty_old_text"),
        (wire.ERR_TOO_LARGE, "on_disk_bytes_do_not_match_presented_base"),
        (wire.ERR_REFUSED, "post_image_over_cap"),
    ]
    for code, reason in wrong_pairs:
        assert (
            project_broker_refusal_reason(error_code=code, internal_reason=reason)
            == UNRECOGNIZED_BROKER_REASON
        ), (code, reason)


def test_an_unknown_error_code_never_borrows_a_known_reasons_meaning():
    for reason in (
        "not_in_mint_time_manifest",
        "changed_file_budget_exhausted",
        "verification_witness_is_never_writable",
        "presented_base_does_not_match_aido_receipt",
        "occurrence_count_1",
    ):
        for code in ("", "refuse", "refused ", "Refused", "no_unique_match2", "stale-base"):
            assert (
                project_broker_refusal_reason(error_code=code, internal_reason=reason)
                == UNRECOGNIZED_BROKER_REASON
            ), (code, reason)


def test_the_qualification_output_codes_are_not_accepted_as_inputs():
    """The projection is one-way: feeding it its own output does not round-trip."""
    for produced in sorted(PROJECTED_REFUSAL_VOCABULARY):
        for code in sorted(wire.CLOSED_ERROR_SET):
            result = project_broker_refusal_reason(
                error_code=code, internal_reason=produced
            )
            # Only the pairs the table genuinely contains may map to themselves.
            if (code, produced) in projection_module._PAIR_TABLE:
                continue
            if code in projection_module._CODE_ALONE_PROJECTIONS:
                assert result == projection_module._CODE_ALONE_PROJECTIONS[code]
            else:
                assert result == UNRECOGNIZED_BROKER_REASON, (code, produced, result)


# =============================================================================
# 3. the ONE shape rule
# =============================================================================


@pytest.mark.parametrize(
    "count", [0, 1, 2, 3, 7, 9, 10, 42, 99, 100, 1000, 65535, 262144, 9999999]
)
def test_occurrence_count_normalizes_for_every_count_ar2_can_construct(count):
    assert (
        project_broker_refusal_reason(
            error_code=wire.ERR_NO_UNIQUE_MATCH,
            internal_reason=f"occurrence_count_{count}",
        )
        == "no_unique_match"
    )


def test_the_accepted_occurrence_spelling_bound_covers_the_frozen_read_cap():
    """``occurrences <= len(pre_text) <= max_read_bytes_per_file``, so 7 digits suffice.

    If AR2 ever raises the per-file read cap past this bound, a genuine
    ``no_unique_match`` could silently reduce to the fallback -- so this fails
    loudly instead.
    """
    assert MAX_READ_BYTES_PER_FILE < 10**projection_module._MAX_OCCURRENCE_COUNT_DIGITS


@pytest.mark.parametrize(
    "spelling",
    [
        "occurrence_count_",
        "occurrence_count_-1",
        "occurrence_count_+1",
        "occurrence_count_ 1",
        "occurrence_count_1 ",
        "occurrence_count_1\n",
        "occurrence_count_1\t",
        "occurrence_count_01",
        "occurrence_count_007",
        "occurrence_count_1_",
        "occurrence_count_1.0",
        "occurrence_count_1e3",
        "occurrence_count_0x2",
        "occurrence_count_two",
        "occurrence_count_None",
        "occurrence_count_\u0661",  # ARABIC-INDIC DIGIT ONE -- str.isdigit() is True
        "occurrence_count_\uff11",  # FULLWIDTH DIGIT ONE -- re \d matches it
        "occurrence_count_\u00b2",  # SUPERSCRIPT TWO
        "occurrence_count_1\u0000",
        " occurrence_count_1",
        "\noccurrence_count_1",
        "xoccurrence_count_1",
        "prefix occurrence_count_1",
        "occurrence_count_1 occurrence_count_2",
        "occurrence_count_" + "9" * 8,
        "occurrence_count_" + "9" * 400,
        "occurrence_countx1",
        "occurrence_count1",
        "OCCURRENCE_COUNT_1",
        "Occurrence_Count_1",
    ],
)
def test_malformed_occurrence_spellings_reduce_to_the_fallback(spelling):
    assert (
        project_broker_refusal_reason(
            error_code=wire.ERR_NO_UNIQUE_MATCH, internal_reason=spelling
        )
        == UNRECOGNIZED_BROKER_REASON
    ), spelling


@pytest.mark.parametrize(
    "error_code",
    sorted(wire.CLOSED_ERROR_SET - {wire.ERR_NO_UNIQUE_MATCH}),
)
def test_the_shape_rule_applies_only_under_no_unique_match(error_code):
    result = project_broker_refusal_reason(
        error_code=error_code, internal_reason="occurrence_count_2"
    )
    assert result != "no_unique_match"
    # protocol_error / unauthorized still fall to their own code-alone rule.
    assert result == projection_module._CODE_ALONE_PROJECTIONS.get(
        error_code, UNRECOGNIZED_BROKER_REASON
    )


def test_the_shape_rule_never_leaks_the_count_into_the_output():
    for count in (0, 1, 2, 17, 4242, 987654):
        result = project_broker_refusal_reason(
            error_code=wire.ERR_NO_UNIQUE_MATCH,
            internal_reason=f"occurrence_count_{count}",
        )
        assert result == "no_unique_match"
        assert str(count) not in result or count in (0, 1, 2)  # "no_unique_match" has no digits
        assert not any(character.isdigit() for character in result)


def test_no_output_code_contains_a_digit_or_a_separator():
    """A structural proof that nothing in the vocabulary can carry a count or a path."""
    for code in PROJECTED_REFUSAL_VOCABULARY:
        assert not any(character.isdigit() for character in code)
        for forbidden in ("/", "\\", ":", " ", ".", "{", "}"):
            assert forbidden not in code


# =============================================================================
# 4. every dynamic family is REDUCED, and nothing leaks
# =============================================================================


_LEAKY_REASONS = [
    # source 3 -- a PathPolicyError message, which may embed a path
    "path_policy:units/labels.py is not writable",
    r"path_policy:C:\dev\ai_dev_orchestrator\secret.py refused",
    "path_policy:.git/config",
    "path_policy:",
    "path_policy:not_in_mint_time_manifest",
    "path_policy:changed_file_budget_exhausted",
    # sources 1, 2, 6 -- exception class names
    "unsafe_lexical_form:CanonicalPathError",
    "unsafe_lexical_form:OSError",
    "canonical_guard:CanonicalPathError",
    "canonical_guard:ValueError",
    "RuntimeError",
    "MemoryError",
    "KeyboardInterrupt",
    # source 5 -- WireProtocolError text derived from a candidate-authored frame
    "protocol error: the request frame is not strict JSON",
    "protocol error: cap is absent or not a string",
    "protocol error: unsupported operation",
]


@pytest.mark.parametrize("reason", _LEAKY_REASONS)
def test_dynamic_reason_families_reduce_and_never_pass_through(reason):
    for code in sorted(wire.CLOSED_ERROR_SET):
        result = project_broker_refusal_reason(error_code=code, internal_reason=reason)
        assert result in PROJECTED_REFUSAL_VOCABULARY
        if code == wire.ERR_UNAUTHORIZED:
            assert result == "unauthorized"
        elif code == wire.ERR_PROTOCOL_ERROR:
            assert result == "protocol_terminal"
        else:
            assert result == UNRECOGNIZED_BROKER_REASON, (code, reason, result)


@pytest.mark.parametrize("reason", _LEAKY_REASONS)
def test_no_candidate_or_runtime_controlled_fragment_survives_into_the_output(reason):
    """No token of the diagnostic -- path, message, class name -- reaches evidence.

    Fragments that are themselves substrings of a FIXED vocabulary literal are
    excluded, and deliberately so: ``"protocol"`` occurs inside
    ``protocol_terminal`` no matter what the input was, so its presence proves
    nothing about leakage. What must never happen is a fragment appearing in the
    output *because it was in the input* -- and for a vocabulary word appearing
    verbatim in the diagnostic (``path_policy:not_in_mint_time_manifest``) the
    stronger check applies: it must not be what was returned.
    """
    fragments = [
        piece
        for piece in reason.replace(":", " ").replace("/", " ").replace("\\", " ").split()
        if len(piece) >= 4
    ]
    inherent = {
        fragment
        for fragment in fragments
        if any(fragment in produced for produced in PROJECTED_REFUSAL_VOCABULARY)
    }
    for code in sorted(wire.CLOSED_ERROR_SET):
        result = project_broker_refusal_reason(error_code=code, internal_reason=reason)
        for fragment in fragments:
            if fragment in PROJECTED_REFUSAL_VOCABULARY:
                # e.g. "path_policy:not_in_mint_time_manifest" -- the fragment is
                # a vocabulary word, but it must NOT be what was returned.
                assert result != fragment, (code, reason, fragment)
                continue
            if fragment in inherent:
                continue
            assert fragment not in result, (code, reason, fragment)


def test_a_path_shaped_diagnostic_never_becomes_a_soft_or_hard_signal():
    for reason in (
        "path_policy:tests/test_money.py",
        "path_policy:verification_witness_is_never_writable",
        "canonical_guard:StaleBaseError",
    ):
        projected = project_broker_refusal_reason(
            error_code=wire.ERR_REFUSED, internal_reason=reason
        )
        attribution = attribute_refusal(RefusalEvent(reason_code=projected))
        assert projected == UNRECOGNIZED_BROKER_REASON
        assert attribution.category == "infrastructure"
        assert not attribution.is_hard_disqualifier
        assert not attribution.is_soft_signal


# =============================================================================
# 5. integration with the FROZEN scope module
# =============================================================================


def test_the_fallback_is_classified_as_infrastructure_by_frozen_scope():
    attribution = attribute_refusal(RefusalEvent(reason_code=UNRECOGNIZED_BROKER_REASON))
    assert attribution.category == "infrastructure"
    assert attribution.is_hard_disqualifier is False
    assert attribution.is_soft_signal is False


def test_a_run_of_only_unrecognized_reasons_produces_no_candidate_signal():
    result = build_scope_result(
        expected_changed_paths={"units/labels.py"},
        observed_changed_paths={"units/labels.py"},
        refusals=tuple(
            RefusalEvent(
                reason_code=project_broker_refusal_reason(
                    error_code=wire.ERR_REFUSED, internal_reason=reason
                )
            )
            for reason in _LEAKY_REASONS
        ),
    )
    assert result.hard_refusal_count == 0
    assert result.soft_refusal_count == 0
    assert result.protected_write_attempts == 0
    assert result.third_file_attempts == 0
    assert result.refusal_categories == (UNRECOGNIZED_BROKER_REASON,)


def test_every_projected_code_is_a_bounded_artifact_token():
    """``refusal_categories`` can only ever hold members of the closed vocabulary."""
    refusals = tuple(
        RefusalEvent(
            reason_code=project_broker_refusal_reason(
                error_code=code, internal_reason=reason
            )
        )
        for code in sorted(wire.CLOSED_ERROR_SET)
        for reason in (
            *sorted({literal for _, literal in _literal_refusal_pairs()}),
            *_LEAKY_REASONS,
            "occurrence_count_3",
        )
    )
    result = build_scope_result(
        expected_changed_paths=set(), observed_changed_paths=set(), refusals=refusals
    )
    assert set(result.refusal_categories) <= PROJECTED_REFUSAL_VOCABULARY


def test_the_soft_signals_the_projection_can_produce_are_attributed_to_the_candidate():
    produced_soft = {
        project_broker_refusal_reason(error_code=code, internal_reason=reason)
        for code, reason in (
            (wire.ERR_REFUSED, "not_in_mint_time_manifest"),
            (wire.ERR_STALE_BASE, "presented_base_does_not_match_aido_receipt"),
            (wire.ERR_STALE_BASE, "on_disk_bytes_do_not_match_presented_base"),
            (wire.ERR_NO_UNIQUE_MATCH, "empty_old_text"),
            (wire.ERR_NO_UNIQUE_MATCH, "occurrence_count_4"),
            (wire.ERR_TOO_LARGE, "per_file_read_cap"),
            (wire.ERR_TOO_LARGE, "pre_image_over_cap"),
        )
    }
    assert produced_soft == set(SOFT_REASON_CODES)
    for code in produced_soft:
        attribution = attribute_refusal(RefusalEvent(reason_code=code))
        assert attribution.category == "candidate"
        assert attribution.is_soft_signal
        assert not attribution.is_hard_disqualifier


def test_the_third_distinct_file_derivation_still_rests_on_a_cap_of_two():
    """Design Sec. 9.3: ``changed_file_budget_exhausted`` means a THIRD distinct path."""
    assert MAX_CHANGED_FILES_PER_RUN == 2


# -- scope's executable behaviour is unchanged (C2-P8) -------------------------


def test_scope_code_sets_are_byte_identical_to_the_frozen_declarations():
    assert HARD_DISQUALIFIER_REASON_CODES == frozenset(
        {
            "verification_witness_is_never_writable",
            "protected_path_is_readable_not_writable",
        }
    )
    assert BUDGET_EXHAUSTED_REASON_CODE == "changed_file_budget_exhausted"
    assert SOFT_REASON_CODES == frozenset(
        {"not_in_mint_time_manifest", "stale_base", "no_unique_match", "over_cap_read"}
    )
    assert PROTOCOL_ANOMALY_REASON_CODES == frozenset({"protocol_terminal", "unauthorized"})


def test_refusal_event_field_set_and_defaults_are_unchanged():
    fields = scope_module.RefusalEvent.__dataclass_fields__
    assert list(fields) == [
        "reason_code",
        "path",
        "is_third_distinct_implementation_file",
        "self_corrected",
    ]
    event = RefusalEvent(reason_code="x")
    assert event.path is None
    assert event.is_third_distinct_implementation_file is False
    assert event.self_corrected is False


def test_attribute_refusal_is_exhaustively_unchanged_over_the_whole_vocabulary():
    expected = {
        ("verification_witness_is_never_writable", False): ("candidate", True, False),
        ("verification_witness_is_never_writable", True): ("candidate", True, False),
        ("protected_path_is_readable_not_writable", False): ("candidate", True, False),
        ("protected_path_is_readable_not_writable", True): ("candidate", True, False),
        ("changed_file_budget_exhausted", False): ("candidate", False, False),
        ("changed_file_budget_exhausted", True): ("candidate", True, False),
        ("not_in_mint_time_manifest", False): ("candidate", False, True),
        ("not_in_mint_time_manifest", True): ("candidate", False, True),
        ("stale_base", False): ("candidate", False, True),
        ("stale_base", True): ("candidate", False, True),
        ("no_unique_match", False): ("candidate", False, True),
        ("no_unique_match", True): ("candidate", False, True),
        ("over_cap_read", False): ("candidate", False, True),
        ("over_cap_read", True): ("candidate", False, True),
        ("protocol_terminal", False): ("undetermined", False, False),
        ("protocol_terminal", True): ("undetermined", False, False),
        ("unauthorized", False): ("undetermined", False, False),
        ("unauthorized", True): ("undetermined", False, False),
        ("unrecognized_broker_reason", False): ("infrastructure", False, False),
        ("unrecognized_broker_reason", True): ("infrastructure", False, False),
    }
    assert {code for code, _ in expected} == set(PROJECTED_REFUSAL_VOCABULARY)
    for (code, third), (category, hard, soft) in expected.items():
        attribution = attribute_refusal(
            RefusalEvent(reason_code=code, is_third_distinct_implementation_file=third)
        )
        assert (attribution.category, attribution.is_hard_disqualifier,
                attribution.is_soft_signal) == (category, hard, soft), (code, third)


def test_scope_executable_ast_is_identical_to_the_c2_baseline_commit():
    """C2's ONLY edit to ``qualification.scope`` is its module docstring.

    Proved by comparing the docstring-stripped AST against the frozen baseline
    blob, so a behavioural edit cannot pass as documentation.
    """
    relative = "experiments/pi_implementer_qualification/qualification/scope.py"
    repository = _TESTS_DIR.parents[2]
    try:
        completed = subprocess.run(
            ["git", "show", f"{_C2_BASELINE_COMMIT}:{relative}"],
            cwd=repository,
            capture_output=True,
            check=False,
        )
    except OSError:  # pragma: no cover - environment dependent
        pytest.skip("git is not available")
    if completed.returncode != 0:  # pragma: no cover - environment dependent
        pytest.skip(f"the C2 baseline blob is not resolvable here: {_C2_BASELINE_COMMIT}")

    def _stripped(source: str) -> str:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
        return ast.dump(ast.fix_missing_locations(tree))

    baseline = completed.stdout.decode("utf-8")
    current = (_QUALIFICATION_PACKAGE / "scope.py").read_text(encoding="utf-8")
    assert _stripped(current) == _stripped(baseline)
    assert current != baseline, "the doc-only correction was not applied"


# =============================================================================
# 6. THE SOURCE-DRIFT GUARD over frozen AR2
# =============================================================================


def test_refusal_reason_construction_is_confined_to_the_three_reviewed_modules():
    """A new ``refuse`` / ``_fail`` / ``_refuse`` site in ANY other AR2 module fails here.

    Without this sweep the guard could be evaded simply by adding the new
    refusal somewhere the reviewed inventory does not look.
    """
    observed: dict[str, set[str]] = {}
    for path in sorted(_AR2_PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        markers: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in ("_fail", "_refuse"):
                markers.add(node.func.id)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "refuse":
                markers.add("refuse")
        if markers:
            observed[path.stem] = markers
    assert observed == {
        "candidate": {"_refuse"},
        "operations": {"_fail"},
        "broker": {"refuse"},
    }, observed


def test_candidate_reasons_reach_diagnostics_only_under_refused():
    """The static justification for keying every ``ar2.candidate`` literal on ``refused``.

    ``ar2.candidate`` names no wire code itself; ``ar2.operations`` supplies one
    when it forwards ``decision.internal_reason``. This reads that forwarding at
    source instead of assuming it.
    """
    forwards = [
        site
        for site in _operations_sites()
        if _shape(site["reason"]) == "Attribute(Name(decision).internal_reason)"  # type: ignore[arg-type]
    ]
    assert len(forwards) == 2
    assert {site["error_code"] for site in forwards} == {wire.ERR_REFUSED}


def test_budget_reasons_reach_diagnostics_only_under_budget_exhausted():
    forwards = [
        site
        for site in _operations_sites()
        if _shape(site["reason"]) == "Name(budget_failure)"  # type: ignore[arg-type]
    ]
    assert len(forwards) == 2
    assert {site["error_code"] for site in forwards} == {wire.ERR_BUDGET_EXHAUSTED}


def test_open_verified_failures_reach_diagnostics_only_under_refused():
    forwards = [
        site
        for site in _operations_sites()
        if _shape(site["reason"]) == "Name(failure)"  # type: ignore[arg-type]
    ]
    assert len(forwards) == 2
    assert {site["error_code"] for site in forwards} == {wire.ERR_REFUSED}


def test_every_literal_ar2_refusal_reason_is_present_in_the_pair_table():
    """(a) of C2-P6. A NEW literal reason in frozen AR2 fails loudly here."""
    table = projection_module._PAIR_TABLE
    missing = sorted(
        pair for pair in _literal_refusal_pairs() if pair not in table
    )
    assert not missing, f"AR2 literal refusal reasons absent from the C2 pair table: {missing}"


def test_every_forwarded_literal_source_is_present_in_the_pair_table():
    """The forwarding sites' literals are table-covered too, under the forwarded code."""
    table = projection_module._PAIR_TABLE
    operations_tree = _ar2_source("operations")
    capability_tree = _ar2_source("capability")

    resolved: dict[str, tuple[str, set[str]]] = {
        "candidate:_refuse_call_sites": (
            wire.ERR_REFUSED,
            {
                site["reason"].value  # type: ignore[union-attr]
                for site in _candidate_sites()
                if site["refusal"] and isinstance(site["reason"], ast.Constant)
            },
        ),
        "operations:_open_verified": (
            wire.ERR_REFUSED,
            _string_returns(operations_tree, "_open_verified"),
        ),
        "capability:read_budget_allows": (
            wire.ERR_BUDGET_EXHAUSTED,
            _string_returns(capability_tree, "read_budget_allows"),
        ),
        "capability:edit_budget_allows": (
            wire.ERR_BUDGET_EXHAUSTED,
            _string_returns(capability_tree, "edit_budget_allows"),
        ),
    }
    declared = {
        entry["literal_source"]
        for entry in _REVIEWED_DYNAMIC_SITES.values()
        if entry["handling"] == "forwarded"
    }
    assert declared - {"operations:_fail_call_sites"} == set(resolved)

    for name, (code, literals) in resolved.items():
        assert literals, f"no literals resolved for the forwarded source {name}"
        for literal in literals:
            assert (code, literal) in table, (name, code, literal)

    # ``operations:_fail_call_sites`` is the broker's forward of an
    # ``OperationOutcome``; its pairs are already covered by the direct literal
    # check above, which reads the very same ``_fail`` call sites.
    #
    # And no ``budget_exhausted`` reason is a DIRECT literal at any ``_fail``
    # site: every one of them arrives through the two forwarding sites resolved
    # above, which is why those must be resolved rather than assumed.
    assert not [pair for pair in _literal_refusal_pairs() if pair[0] == wire.ERR_BUDGET_EXHAUSTED]


def test_the_dynamic_construction_sites_equal_the_reviewed_inventory():
    """(b) of C2-P6, the part a literal-only guard would miss entirely.

    A newly added f-string, ``str(exc)``, exception-derived reason, or any
    other non-``Constant`` expression reaching a refusal reason fails here until
    it has been reviewed and given an explicit disposition.
    """
    observed = _dynamic_sites()
    reviewed = set(_REVIEWED_DYNAMIC_SITES)
    assert observed == reviewed, {
        "unreviewed new dynamic sites": sorted(observed - reviewed),
        "reviewed sites that vanished": sorted(reviewed - observed),
    }


def test_the_reviewed_inventory_covers_the_six_design_enumerated_dynamic_sources():
    constructing = {
        key: entry
        for key, entry in _REVIEWED_DYNAMIC_SITES.items()
        if entry["handling"] in ("free_text", "shape_rule")
    }
    assert len(constructing) == 6, sorted(constructing)
    shape_ruled = [key for key, entry in constructing.items() if entry["handling"] == "shape_rule"]
    assert len(shape_ruled) == 1
    assert "occurrence_count_" in shape_ruled[0][3]
    assert shape_ruled[0][2] == wire.ERR_NO_UNIQUE_MATCH


def test_every_fstring_in_the_three_modules_equals_the_reviewed_inventory():
    observed: dict[tuple[str, str, str], None] = {}
    for module_name in ("candidate", "operations", "broker"):
        tree = _ar2_source(module_name)
        enclosing = _enclosing_function(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                observed[
                    (f"ar2.{module_name}", enclosing.get(id(node), "<module>"), _shape(node))
                ] = None
    assert set(observed) == set(_REVIEWED_FSTRING_SITES), {
        "unreviewed new f-strings": sorted(set(observed) - set(_REVIEWED_FSTRING_SITES)),
        "reviewed f-strings that vanished": sorted(set(_REVIEWED_FSTRING_SITES) - set(observed)),
    }


def test_the_non_refusal_literal_reasons_are_still_non_refusal():
    observed = {
        site["reason"].value  # type: ignore[union-attr]
        for site in _all_sites()
        if not site["refusal"] and isinstance(site["reason"], ast.Constant)
    }
    assert observed == _REVIEWED_NON_REFUSAL_LITERALS, observed


def test_the_diagnostics_entry_format_the_projection_depends_on_is_unchanged():
    """Sec. 9.3's ``split(':', 2)`` contract, pinned at source."""
    tree = _ar2_source("broker")
    enclosing = _enclosing_function(tree)
    shapes = {
        _shape(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr) and enclosing.get(id(node)) == "refuse"
    }
    assert shapes == {
        "JoinedStr(expr[Name(operation)]+lit=':'+expr[Name(code)])",
        "JoinedStr(expr[Name(operation)]+lit=':'+expr[Name(code)]+lit=':'+expr[Name(reason)])",
    }


def test_the_pair_table_contains_no_entry_frozen_ar2_cannot_produce():
    """The table is a mirror of frozen AR2, not a wishlist."""
    producible = _literal_refusal_pairs()
    for name, (code, literals) in {
        "open_verified": (wire.ERR_REFUSED, _string_returns(_ar2_source("operations"), "_open_verified")),
        "read_budget": (
            wire.ERR_BUDGET_EXHAUSTED,
            _string_returns(_ar2_source("capability"), "read_budget_allows"),
        ),
        "edit_budget": (
            wire.ERR_BUDGET_EXHAUSTED,
            _string_returns(_ar2_source("capability"), "edit_budget_allows"),
        ),
    }.items():
        assert literals, f"no literals resolved for {name}"
        producible |= {(code, literal) for literal in literals}
    extra = sorted(set(projection_module._PAIR_TABLE) - producible)
    assert not extra, f"pair-table entries frozen AR2 cannot emit: {extra}"


def test_the_guard_never_writes_to_frozen_ar2():
    """A structural check that this suite only READS AR2 (C2-P7)."""
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in (
                "write_text",
                "write_bytes",
                "unlink",
                "rename",
                "mkdir",
                "touch",
            ), node.func.attr
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "open"


# =============================================================================
# 7. no duplicate mapping implementation exists
# =============================================================================


def test_only_one_module_defines_the_projection():
    definitions = []
    for path in sorted(_QUALIFICATION_PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "project_broker_refusal_reason"
            ):
                definitions.append(path.name)
    assert definitions == ["refusal_projection.py"]


def _non_docstring_string_constants(tree: ast.Module) -> set[str]:
    """Every string constant in EXECUTABLE position -- docstrings excluded.

    Prose that merely *names* an AR2 diagnostic while explaining behaviour is
    documentation, not a mapping. Only a string the module can actually compare
    against or return could constitute a second projection.
    """
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            docstrings.add(id(body[0].value))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    }


def test_no_other_qualification_module_carries_an_ar2_diagnostic_literal():
    """C2-P5: no second mapping table, and no partial re-spelling of one either."""
    ar2_only_literals = {
        literal
        for _, literal in _literal_refusal_pairs()
        if literal not in PROJECTED_REFUSAL_VOCABULARY
    }
    ar2_only_literals |= {"occurrence_count_", "path_policy:", "unsafe_lexical_form:",
                          "canonical_guard:"}
    assert len(ar2_only_literals) > 20

    offenders: dict[str, list[str]] = {}
    for path in sorted(_QUALIFICATION_PACKAGE.glob("*.py")):
        if path.name == "refusal_projection.py":
            continue
        executable = _non_docstring_string_constants(
            ast.parse(path.read_text(encoding="utf-8"))
        )
        hits = sorted(
            literal
            for literal in ar2_only_literals
            if any(literal in value for value in executable)
        )
        if hits:
            offenders[path.name] = hits
    assert offenders == {}, offenders


def test_the_projection_module_declares_no_second_lookup_structure():
    """Exactly one pair table, one code-alone table, and one shape rule."""
    tree = ast.parse((_QUALIFICATION_PACKAGE / "refusal_projection.py").read_text("utf-8"))
    # Any dict literal ANYWHERE in the assigned value counts -- including one
    # wrapped in ``MappingProxyType(...)`` -- so the check stays a real census of
    # lookup structures rather than a check on how they happen to be spelled.
    dict_names = [
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None
        for target in ([node.target] if isinstance(node, ast.AnnAssign) else node.targets)
        if isinstance(target, ast.Name)
        and any(
            isinstance(inner, (ast.Dict, ast.DictComp)) for inner in ast.walk(node.value)
        )
    ]
    assert dict_names == ["_CODE_ALONE_PROJECTIONS", "_PAIR_TABLE"]
    functions = [
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert functions == [
        "_is_bounded_occurrence_count_spelling",
        "project_broker_refusal_reason",
    ]


def test_the_projection_module_imports_no_runtime_or_network_surface():
    tree = ast.parse((_QUALIFICATION_PACKAGE / "refusal_projection.py").read_text("utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert imported == {"__future__", "types", "typing", "ar2"}
