"""Typed plan models and fake planner engine for the AI Dev Orchestrator.

Phase 4B added ``L1Plan`` (and the optional ``L1PlanSource`` helper),
pure data models describing the structured shape of the plan-only artifact
an L1 planner produces. Phase 4C adds ``FakeL1Planner``, a deterministic,
offline transformation from an already-fetched issue/config into an
``L1Plan``. Importing this package performs no file reads, no workspace path
checks, no command execution, no GitHub writes, and no model or network
calls.
"""

from ai_dev_orchestrator.plan.fake_planner import FakeL1Planner
from ai_dev_orchestrator.plan.models import L1Plan, L1PlanSource

__all__ = [
    "FakeL1Planner",
    "L1Plan",
    "L1PlanSource",
]
