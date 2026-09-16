"""The four CFG1 arms, and every pinned fact that is a pure function of one.

Design Sec. 7.2. **The only manipulated variable in this entire experiment is
the provider-level Pi ``compat`` object.** Arm Q adds nothing at all -- its
generated documents are byte-identical to the frozen qualification
generator's for the same inputs (T-1). Each other arm adds exactly one
provider-level ``compat`` object between ``apiKey`` and ``models``, and
nothing else (T-2).

The declared shape is what ``get_state`` can report (Sec. 2.5) -- Pi
serializes the COMPOSED model object, never the request-time ``getCompat``
result -- so the runtime manipulation check (Sec. 8.2) compares against the
DECLARED shape and never demands an explicit ``true`` for an absent field.
The effective values below are source-derived offline facts (Sec. 2.2-2.4),
asserted by T-3, never observed on the wire.
"""

from __future__ import annotations

#: Declared-shape vocabulary (Sec. 8.2). ``OTHER``/``NOT_OBSERVED`` are
#: RUNTIME-reported values only -- an arm never declares either.
SHAPE_ABSENT = "ABSENT"
SHAPE_DEVELOPER_ROLE_FALSE_ONLY = "DEVELOPER_ROLE_FALSE_ONLY"
SHAPE_REASONING_EFFORT_FALSE_ONLY = "REASONING_EFFORT_FALSE_ONLY"
SHAPE_BOTH_FALSE_ONLY = "BOTH_FALSE_ONLY"
SHAPE_OTHER = "OTHER"
SHAPE_NOT_OBSERVED = "NOT_OBSERVED"

DECLARED_COMPAT_SHAPES: frozenset[str] = frozenset(
    {
        SHAPE_ABSENT,
        SHAPE_DEVELOPER_ROLE_FALSE_ONLY,
        SHAPE_REASONING_EFFORT_FALSE_ONLY,
        SHAPE_BOTH_FALSE_ONLY,
    }
)

RUNTIME_COMPAT_SHAPES: frozenset[str] = DECLARED_COMPAT_SHAPES | frozenset(
    {SHAPE_OTHER, SHAPE_NOT_OBSERVED}
)

#: The provider-level ``compat`` subtree each arm adds. ``None`` means the key
#: is ABSENT from the generated document entirely -- never ``{}``, which would
#: be a present-but-empty object and a different declared shape.
ARM_COMPAT: dict[str, dict[str, bool] | None] = {
    "Q": None,
    "R": {"supportsDeveloperRole": False},
    "E": {"supportsReasoningEffort": False},
    "H": {"supportsDeveloperRole": False, "supportsReasoningEffort": False},
}

#: What ``get_state`` reports for each arm (Sec. 2.5), derived from
#: ``JSON.stringify`` dropping ``undefined`` and ``mergeCompat`` returning the
#: provider block unchanged when the model level declares none.
ARM_SHAPE: dict[str, str] = {
    "Q": SHAPE_ABSENT,
    "R": SHAPE_DEVELOPER_ROLE_FALSE_ONLY,
    "E": SHAPE_REASONING_EFFORT_FALSE_ONLY,
    "H": SHAPE_BOTH_FALSE_ONLY,
}

#: The four ``derived_*`` run-record fields, per arm. Source-derived from
#: ``getCompat``'s per-field ``??`` resolution against ``detectCompat``'s
#: ``true``/``true`` for a non-matching provider id and base URL (Sec. 2.2),
#: then ``convertMessages`` (Sec. 2.4) and ``buildParams`` (Sec. 2.4).
#:
#: ``derived_reasoning_effort_sent`` is ``"medium"`` when Pi emits
#: ``reasoning_effort``, and ``None`` when it omits the field entirely.
ARM_EFFECTIVE: dict[str, dict[str, object]] = {
    "Q": {
        "derived_effective_supports_developer_role": True,
        "derived_effective_supports_reasoning_effort": True,
        "derived_system_role": "developer",
        "derived_reasoning_effort_sent": "medium",
    },
    "R": {
        "derived_effective_supports_developer_role": False,
        "derived_effective_supports_reasoning_effort": True,
        "derived_system_role": "system",
        "derived_reasoning_effort_sent": "medium",
    },
    "E": {
        "derived_effective_supports_developer_role": True,
        "derived_effective_supports_reasoning_effort": False,
        "derived_system_role": "developer",
        "derived_reasoning_effort_sent": None,
    },
    "H": {
        "derived_effective_supports_developer_role": False,
        "derived_effective_supports_reasoning_effort": False,
        "derived_system_role": "system",
        "derived_reasoning_effort_sent": None,
    },
}

DERIVED_SYSTEM_ROLES: frozenset[str] = frozenset({"developer", "system"})

#: ``reasoning_effort``'s only non-null value under this design's frozen
#: thinking level (Sec. 3.3): no ``--thinking`` flag, no ``defaultThinkingLevel``,
#: no ``thinkingLevelMap``, so Pi's own ``"medium"`` default is unclamped.
DERIVED_REASONING_EFFORT_VALUES: frozenset[object] = frozenset({"medium", None})

#: Pi's own thinking-level vocabulary plus the two projection-only literals.
RUNTIME_THINKING_LEVELS: frozenset[str] = frozenset(
    {"off", "minimal", "low", "medium", "high", "xhigh", "max", "OTHER", "NOT_OBSERVED"}
)

RUNTIME_MODEL_REASONING_VALUES: frozenset[str] = frozenset(
    {"TRUE", "FALSE", "OTHER", "NOT_OBSERVED"}
)

#: The frozen thinking level every arm and every run shares (Sec. 8.3).
EXPECTED_THINKING_LEVEL = "medium"

#: SHA-256 of each arm's generated ``models.json`` with the base URL replaced
#: by the fixed redaction placeholder, for the pinned model id (Sec. 22.3's
#: ``ARM_REDACTED_DIGEST[arm_id]``).
#:
#: **Pinned literals, deliberately.** The run-record validator compares a
#: record's declared digest against THESE constants, and a separate regression
#: (T-2) compares these constants against what the generator actually produces.
#: Having the validator recompute from the generator instead would make the
#: check tautological -- any generator change would silently redefine what a
#: "correct" record is, and every archived record would retroactively become
#: wrong without anything failing.
ARM_REDACTED_DIGEST: dict[str, str] = {
    "Q": "882ca9f2845cb242f521fe289562ac1dece9d0bf16d0c62eecdf42186c48dc1b",
    "R": "efaf9c6fa92e71c6a0b2f97d93613b70155e9317e9bb45c94ad94b605f18c460",
    "E": "0ffa801cc3dc26a1b305a415b85cff8e75a3f0ce6dd8735e033f34ff50037952",
    "H": "3c13391664c82210a20f2d7b15451c74c2b407c642643f6d9ee5ce53f86ae911",
}

#: SHA-256 of the one settings document every arm and every run shares. Pinned
#: for the same reason, and checked the same way.
PINNED_SETTINGS_SHA256 = (
    "235a1e1fdf5a2ef41f86d0c27507d5f468b50022985033b0fb6c60baadad59ff"
)
