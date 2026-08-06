"""Typed plan models for the AI Dev Orchestrator.

Phase 4B: pure data models only. ``L1Plan`` (and the optional
``L1PlanSource`` helper) describe the structured shape of the plan-only
artifact a future L1 planner (Phase 4C+) will produce. Importing this
package performs no file reads, no workspace path checks, no command
execution, no GitHub writes, and no model or network calls.
"""

from ai_dev_orchestrator.plan.models import L1Plan, L1PlanSource

__all__ = [
    "L1Plan",
    "L1PlanSource",
]
