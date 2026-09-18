"""The one bounded runtime capability observation (CFG1-L16-FU2). Pi-specific.

This module is NOT an observer framework, and it must not become one. It holds
exactly:

- the fixed probe command type (``get_state``) -- a module constant, never a
  parameter;
- the one raw classification of the one fixed path ``data.model.reasoning``,
  which is subjected to the two identity tests ``is True`` / ``is False`` and
  to nothing else (design Sec. 5.4 (c), Sec. 6.2 I-6/I-7);
- the single definitions of the Sec. 8.2 compat-shape and thinking-level
  classifications (R-AR2-4). CFG1 imports them from here; they are never
  duplicated and never passed in at runtime;
- the probe slot: supervisor-private, scalar-only state (Sec. 5.3, I-8).

Nothing here accepts a path, key, command type, extractor, predicate,
classifier or callback. Nothing here returns a mapping, a record, a subtree or
an id. The raw reasoning value is never stringified, formatted, hashed,
length-inspected, compared with ``==``, truth-tested, copied or retained.

What the observation proves and does not prove (Sec. 5.7): the four facts come
from the one correlated response to a ``get_state`` AIDO authored, on this
supervisor's own reader, reduced before publication. They remain
``runtime_reported_*`` UNTRUSTED CLAIMS: correlation does not make Pi's report
true.
"""

from __future__ import annotations

from typing import Any

from .handshakes import evaluate_model_identity

#: The probe's command type. A constant; no code path lets a caller choose it.
PROBE_COMMAND_TYPE = "get_state"

# -- closed literals ----------------------------------------------------------

REASONING_TRUE = "TRUE"
REASONING_FALSE = "FALSE"
REASONING_OTHER = "OTHER"
NOT_OBSERVED = "NOT_OBSERVED"

MODEL_REASONING_LITERALS: frozenset[str] = frozenset(
    {REASONING_TRUE, REASONING_FALSE, REASONING_OTHER, NOT_OBSERVED}
)

COMPAT_ABSENT = "ABSENT"
COMPAT_DEVELOPER_ROLE_FALSE_ONLY = "DEVELOPER_ROLE_FALSE_ONLY"
COMPAT_REASONING_EFFORT_FALSE_ONLY = "REASONING_EFFORT_FALSE_ONLY"
COMPAT_BOTH_FALSE_ONLY = "BOTH_FALSE_ONLY"
COMPAT_OTHER = "OTHER"

COMPAT_SHAPE_LITERALS: frozenset[str] = frozenset(
    {
        COMPAT_ABSENT,
        COMPAT_DEVELOPER_ROLE_FALSE_ONLY,
        COMPAT_REASONING_EFFORT_FALSE_ONLY,
        COMPAT_BOTH_FALSE_ONLY,
        COMPAT_OTHER,
        NOT_OBSERVED,
    }
)

#: Pi's own thinking-level vocabulary.
PI_THINKING_LEVELS: tuple[str, ...] = (
    "off",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)
THINKING_OTHER = "OTHER"

THINKING_LEVEL_LITERALS: frozenset[str] = frozenset(PI_THINKING_LEVELS) | frozenset(
    {THINKING_OTHER, NOT_OBSERVED}
)

#: The facts returned when no correlated response was observed (Sec. 8).
UNOBSERVED_FACTS: tuple[bool, str, str, str] = (
    False,
    NOT_OBSERVED,
    NOT_OBSERVED,
    NOT_OBSERVED,
)


# -- the raw, pre-drop classification (Sec. 5.4 (c)) -------------------------


def classify_raw_model_reasoning(model: dict) -> str:
    """Classify ``model["reasoning"]`` by identity ONLY. ``model`` is an exact dict.

    The value is subjected to exactly the key-membership test and the two
    identity tests below (I-6). It is never stringified, formatted, hashed,
    length-inspected, compared with ``==``, truth-tested, typed, copied or
    retained (I-7): ``1 == True`` in Python, so ``==`` would accept ``1``.
    The result is one of three constants that carry nothing about any other
    value.
    """
    if "reasoning" not in model:
        return REASONING_OTHER
    if model["reasoning"] is True:
        return REASONING_TRUE
    if model["reasoning"] is False:
        return REASONING_FALSE
    return REASONING_OTHER


def classify_correlated_raw_record(record: dict) -> tuple[bool, bool, str] | None:
    """Steps (b) and (c) on the one id-matched raw record, BEFORE ``ingest_record``.

    Returns ``(success_ok, data_is_dict, reasoning_literal)``, or ``None`` when
    the correlation itself is invalid (a wrong, missing or non-``str``
    ``command``), which poisons the slot. Only exact ``dict`` objects are
    descended into; a decoded JSON object always is one.
    """
    command = record.get("command")
    if type(command) is not str or command != PROBE_COMMAND_TYPE:
        return None
    success_ok = record.get("success") is True
    if not success_ok:
        return False, False, NOT_OBSERVED
    data = record.get("data")
    if type(data) is not dict:
        return True, False, NOT_OBSERVED
    model = data.get("model")
    if type(model) is not dict:
        return True, True, REASONING_OTHER
    return True, True, classify_raw_model_reasoning(model)


# -- the Sec. 8.2 classifications: the single definitions (R-AR2-4) -----------


def classify_compat_object(compat: object) -> str:
    """Exactly the four declared shapes, or ``OTHER``. Never a partial match.

    A key set outside the four, or a value that is not exact JSON ``false``,
    is ``OTHER`` -- the check never demands an explicit ``true`` for an absent
    field, and never accepts a truthy stand-in for ``false``.
    """
    if not isinstance(compat, dict):
        return COMPAT_OTHER
    if any(value is not False for value in compat.values()):
        return COMPAT_OTHER
    keys = frozenset(compat)
    if keys == frozenset({"supportsDeveloperRole"}):
        return COMPAT_DEVELOPER_ROLE_FALSE_ONLY
    if keys == frozenset({"supportsReasoningEffort"}):
        return COMPAT_REASONING_EFFORT_FALSE_ONLY
    if keys == frozenset({"supportsDeveloperRole", "supportsReasoningEffort"}):
        return COMPAT_BOTH_FALSE_ONLY
    return COMPAT_OTHER


def classify_compat_shape(state: dict) -> str:
    """Sec. 8.2 compat shape of a SANITIZED ``get_state`` ``data`` object.

    ``get_state`` serializes the COMPOSED model object, so what is observable
    is the arm's DECLARED shape -- never the effective ``true``/``false``
    values, which stay source-derived offline facts.
    """
    model = state.get("model")
    if not isinstance(model, dict):
        return COMPAT_OTHER
    if "compat" not in model:
        return COMPAT_ABSENT
    return classify_compat_object(model.get("compat"))


def classify_thinking_level(state: dict) -> str:
    """Sec. 8.2 thinking level of a SANITIZED ``get_state`` ``data`` object."""
    if "thinkingLevel" not in state:
        return NOT_OBSERVED
    level = state.get("thinkingLevel")
    if isinstance(level, str):
        for known in PI_THINKING_LEVELS:
            if level == known:
                # This module's own constant, never the runtime's object.
                return known
    return THINKING_OTHER


# -- step (e): reduce the sanitized record to bounded facts ------------------


def reduce_sanitized_get_state(
    sanitized: dict,
    *,
    success_ok: bool,
    data_is_dict: bool,
    expected_provider: str,
    expected_model: str,
) -> tuple[bool, str, str]:
    """H2 and the two Sec. 8.2 facts, from the SAME reader-local sanitized record.

    Called by the reader thread before the record is published, so no other
    thread can yet hold a reference to ``sanitized`` (Sec. 5.5). The frozen H2
    handshake is called unchanged; its diagnostic dict is discarded at once and
    only the exact ``passed is True`` survives.
    """
    if not success_ok or not data_is_dict:
        return False, NOT_OBSERVED, NOT_OBSERVED
    data = sanitized.get("data")
    if type(data) is not dict:
        return False, NOT_OBSERVED, NOT_OBSERVED
    h2 = (
        evaluate_model_identity(
            sanitized,
            expected_provider=expected_provider,
            expected_model=expected_model,
        ).get("passed")
        is True
    )
    return h2, classify_compat_shape(data), classify_thinking_level(data)


# -- the probe slot (Sec. 5.3, Sec. 5.4, I-8) ---------------------------------

SLOT_UNARMED = "UNARMED"
SLOT_ARMED = "ARMED"
SLOT_RESOLVED = "RESOLVED"
SLOT_POISONED = "POISONED"
SLOT_CONSUMED = "CONSUMED"
SLOT_RETIRED = "RETIRED"

_TERMINAL_SLOT_STATES = (SLOT_CONSUMED, SLOT_RETIRED)

#: Fixed poison reasons. Never an exception's text.
POISON_COMMAND_INVALID = "CORRELATED_COMMAND_INVALID"
POISON_DUPLICATE_RESPONSE = "DUPLICATE_CORRELATED_RESPONSE"
POISON_CLASSIFICATION_RAISED = "CLASSIFICATION_RAISED"
POISON_REASONS: frozenset[str] = frozenset(
    {POISON_COMMAND_INVALID, POISON_DUPLICATE_RESPONSE, POISON_CLASSIFICATION_RAISED}
)


class ProbeSlot:
    """Supervisor-private probe state. Immutable scalars only; ``__slots__``.

    ``__slots__`` is deliberate: an instance ``__dict__`` would itself be a
    container referenced by the slot (R-17). Every field is a ``str``, a
    ``bool`` or ``None``. Mutation happens only under the owning reader's lock
    once the slot is bound to a reader (and under the supervisor's lifecycle
    serialization before that); this class enforces the state machine's
    forward-only transitions but is not itself a lock.
    """

    __slots__ = (
        "state",
        "expected_id",
        "expected_provider",
        "expected_model",
        "h2",
        "capability_flag",
        "compat",
        "thinking_level",
        "poison_reason",
    )

    def __init__(self) -> None:
        self.state: str = SLOT_UNARMED
        self.expected_id: str | None = None
        self.expected_provider: str | None = None
        self.expected_model: str | None = None
        self.h2: bool | None = None
        self.capability_flag: str | None = None
        self.compat: str | None = None
        self.thinking_level: str | None = None
        self.poison_reason: str | None = None

    def arm(self, probe_id: str, expected_provider: str, expected_model: str) -> None:
        if self.state != SLOT_UNARMED:
            raise RuntimeError("probe slot is not unarmed")
        self.expected_id = probe_id
        self.expected_provider = expected_provider
        self.expected_model = expected_model
        self.state = SLOT_ARMED

    def resolve(self, h2: bool, capability_flag: str, compat: str, thinking_level: str) -> None:
        if self.state != SLOT_ARMED:
            return
        self.h2 = h2
        self.capability_flag = capability_flag
        self.compat = compat
        self.thinking_level = thinking_level
        self.state = SLOT_RESOLVED

    def poison(self, reason: str) -> None:
        """ARMED or RESOLVED -> POISONED; stored facts are discarded.

        ``reason`` is always one of the fixed ``POISON_*`` literals -- never an
        exception's text, which could carry a raw value.
        """
        if self.state not in (SLOT_ARMED, SLOT_RESOLVED):
            return
        if reason not in POISON_REASONS:
            reason = POISON_CLASSIFICATION_RAISED
        self._discard_facts()
        self.poison_reason = reason
        self.state = SLOT_POISONED

    def consume(self) -> tuple[bool, str, str, str] | None:
        """RESOLVED -> facts; ARMED -> unobserved facts; POISONED -> ``None``.

        Always leaves the slot ``CONSUMED``. Any other state raises.
        """
        state = self.state
        if state == SLOT_RESOLVED:
            facts = (self.h2, self.capability_flag, self.compat, self.thinking_level)
            self._discard_facts()
            self.expected_id = None
            self.state = SLOT_CONSUMED
            return facts  # type: ignore[return-value]
        if state == SLOT_ARMED:
            self.expected_id = None
            self.state = SLOT_CONSUMED
            return UNOBSERVED_FACTS
        if state == SLOT_POISONED:
            self.expected_id = None
            self.state = SLOT_CONSUMED
            return None
        raise RuntimeError("probe slot is not consumable")

    def retire(self) -> None:
        """Any state except CONSUMED -> RETIRED. Idempotent and monotonic."""
        if self.state in _TERMINAL_SLOT_STATES:
            return
        self._discard_facts()
        # The expected id is kept only from arming until CONSUMED or RETIRED.
        self.expected_id = None
        self.state = SLOT_RETIRED

    def _discard_facts(self) -> None:
        self.h2 = None
        self.capability_flag = None
        self.compat = None
        self.thinking_level = None


def is_correlated_response(record: dict, expected_id: Any) -> bool:
    """Step (a)'s match: exact ``type == "response"`` and exact ``id``.

    ``expected_id`` is the AIDO-minted ``str``; the record's ``id`` must be an
    exact ``str`` equal to it -- no case folding, trimming or normalization.
    """
    kind = record.get("type")
    if type(kind) is not str or kind != "response":
        return False
    identifier = record.get("id")
    if type(identifier) is not str or type(expected_id) is not str:
        return False
    return identifier == expected_id
