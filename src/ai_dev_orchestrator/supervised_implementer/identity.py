"""Supervised-implementer role and candidate identity (DEC-SUP, ALPHA-P1A).

This registry is **separate from, and never merged into**, the frozen
autonomous-implementer qualification registry ``CANDIDATE_MODEL_IDS``
(``experiments/pi_implementer_qualification/qualification/records.py``). That
registry holds candidates A, B and C and is not touched by this phase.

``SUP-D`` is a *supervised* candidate: its output is untrusted proposed content
that a human approves as an exact diff before anything is written. It carries
**no qualification credit** in either direction. It is not Candidate D's
autonomous qualification, a supervised result is never hard-bar evidence, and
it grants no reviewer authority.

The mapping is read-only, so importing code cannot add, replace or rebind a
candidate at runtime.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Literal

#: The role this package implements. Distinct from the autonomous (Pi)
#: implementer role, the reviewer role, and the (unauthorized) fixer role.
SUPERVISED_IMPLEMENTER_ROLE: Final = "supervised_implementer"

#: The one supervised candidate DEC-SUP authorized.
SUPERVISED_CANDIDATE_ID: Final = "SUP-D"

#: Read-only candidate -> exact served model id. Matched with ``==`` only:
#: no glob, prefix, alias or case folding.
SUPERVISED_CANDIDATE_MODEL_IDS: Final = MappingProxyType(
    {SUPERVISED_CANDIDATE_ID: "qwen3.8-27b"}
)

#: What a supervised result is worth toward any qualification: nothing.
QUALIFICATION_CREDIT: Final = "none"

SupervisedCandidateId = Literal["SUP-D"]
SupervisedModelId = Literal["qwen3.8-27b"]
