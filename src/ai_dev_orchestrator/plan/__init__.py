"""Typed plan models, planner engines, prompt building, and model-output parsing.

Phase 4B added ``L1Plan`` (and the optional ``L1PlanSource`` helper),
pure data models describing the structured shape of the plan-only artifact
an L1 planner produces. Phase 4C adds ``FakeL1Planner``, a deterministic,
offline transformation from an already-fetched issue/config into an
``L1Plan``. Phase 4F adds the typed model-planner error hierarchy and
``parse_model_l1_plan_response``, a pure strict-JSON output parser. Phase 4G
adds the pure prompt builder ``build_model_l1_plan_request`` and
``ModelBackedL1Planner``, which wires prompt builder → an **injected** chat
client → parser → ``L1Plan``; the planner never constructs a client, so with a
mock-transport-backed client injected it reaches no real model. Importing this
package performs no file reads, no workspace path checks, no command execution,
no GitHub writes, and no model or network calls.
"""

from ai_dev_orchestrator.plan.fake_planner import FakeL1Planner
from ai_dev_orchestrator.plan.model_planner import (
    ModelBackedL1Planner,
    ModelPlannerError,
    ModelPlannerParseError,
    ModelPlannerPolicyError,
    ModelPlannerValidationError,
    build_model_l1_plan_request,
    parse_model_l1_plan_response,
)
from ai_dev_orchestrator.plan.models import L1Plan, L1PlanSource

__all__ = [
    "FakeL1Planner",
    "L1Plan",
    "L1PlanSource",
    "ModelBackedL1Planner",
    "ModelPlannerError",
    "ModelPlannerParseError",
    "ModelPlannerPolicyError",
    "ModelPlannerValidationError",
    "build_model_l1_plan_request",
    "parse_model_l1_plan_response",
]
