"""Supervised-implementer role and candidate identity (DEC-SUP, ALPHA-P1A, P0-MODEL-1).

This registry is **separate from, and never merged into**, the frozen
autonomous-implementer qualification registry ``CANDIDATE_MODEL_IDS``
(``experiments/pi_implementer_qualification/qualification/records.py``). That
registry holds candidates A, B and C and is not touched by this phase.

Every entry is a *supervised* candidate: its output is untrusted proposed
content that a human approves as an exact diff before anything is written. It
carries **no qualification credit** in either direction. ``SUP-D`` is not
Candidate D's autonomous qualification, a supervised result is never hard-bar
evidence, and no entry grants reviewer authority.

The registry is **append-only** (P0-MODEL-1, policy §13). ``SUP-D`` =
``qwen3.8-27b`` is unchanged. ``SUP-M3`` = ``minimax-m3`` is a separately
identified candidate, never an alias, substitute or fallback for ``SUP-D``. A
project selects exactly one candidate, by id **and** model, in its own config;
H2 binds that pair, and the request carries that model. Nothing selects,
substitutes or fails over between candidates.

The mapping is read-only, so importing code cannot add, replace or rebind a
candidate at runtime.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Literal

#: The role this package implements. Distinct from the autonomous (Pi)
#: implementer role, the reviewer role, and the (unauthorized) fixer role.
SUPERVISED_IMPLEMENTER_ROLE: Final = "supervised_implementer"

#: The first supervised candidate DEC-SUP authorized.
SUPERVISED_CANDIDATE_ID: Final = "SUP-D"

#: P0-MODEL-1. A separately identified supervised candidate.
SUPERVISED_CANDIDATE_M3_ID: Final = "SUP-M3"

#: Read-only candidate -> exact served model id. Matched with ``==`` only:
#: no glob, prefix, alias or case folding. Append-only.
SUPERVISED_CANDIDATE_MODEL_IDS: Final = MappingProxyType(
    {
        SUPERVISED_CANDIDATE_ID: "qwen3.8-27b",
        SUPERVISED_CANDIDATE_M3_ID: "minimax-m3",
    }
)

#: What a supervised result is worth toward any qualification: nothing.
QUALIFICATION_CREDIT: Final = "none"

SupervisedCandidateId = Literal["SUP-D", "SUP-M3"]
SupervisedModelId = Literal["qwen3.8-27b", "minimax-m3"]


def require_registered_candidate_pair(candidate: object, model: object) -> None:
    """Refuse unless ``(candidate, model)`` is exactly one registry entry.

    Every record that carries both fields calls this, so a record pairing
    ``SUP-D`` with ``minimax-m3`` (or ``SUP-M3`` with ``qwen3.8-27b``) is
    invalid even though each value is individually a permitted literal.
    """
    if (
        type(candidate) is not str
        or type(model) is not str
        or SUPERVISED_CANDIDATE_MODEL_IDS.get(candidate) != model
    ):
        raise ValueError(
            "candidate and model must be exactly one supervised registry pair "
            f"({dict(SUPERVISED_CANDIDATE_MODEL_IDS)}); a different model is a "
            "different candidate, never a substitute."
        )
