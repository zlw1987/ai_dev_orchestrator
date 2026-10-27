"""DL-4B S6 — ``AlphaPlannerRule``, the deterministic Alpha planner (FD-8).

DL-2's planner dispatch at ACCEPTANCE is answered in an integration session by
this rule and nothing else. It calls no model, runs nothing, waits for nothing
and records nothing. It asks the store for the decision the store derives
from its own re-proven records:

```text
RECOMMEND_STEP_ACCEPT   iff the attempt's approved write is proven (M0, M1), M2 holds,
                        the recorded verification claim's outcome is 'verified' and
                        the recorded review evidence's verdict is 'approve'
HUMAN_REQUIRED          otherwise
```

Neither the outcome nor the verdict is read from the cached ``step_runs``
fields, or from the ``step_run`` DL-2 hands the port (S5's R5-8): both come
from ``verification_evidence_v2`` and ``review_evidence``, re-derived from the
stored claim bytes. The store refuses any planner output that is not exactly
this decision, whoever presents it, so the rule's origin is not what makes it
authority (R-3 stands: it never is). A ``RECOMMEND_STEP_ACCEPT`` is only ever
held for a signed human acceptance; it never completes a step by itself.
"""

from __future__ import annotations

from typing import Any

from ai_dev_orchestrator.control_plane.authority import BoundRoleOutput, DispatchTicket, bind_role_output
from ai_dev_orchestrator.control_plane.models import StepContract, StepRun

_RULE_TOKEN = object()


class AlphaPlannerRule:
    """DL-2's ``BoundPlannerPort`` in an integration session."""

    __slots__ = ("_store",)

    def __init__(self, store: Any, *, _token: object = None) -> None:
        if _token is not _RULE_TOKEN:
            raise TypeError("the Alpha planner rule is minted only by open_integration_session().")
        object.__setattr__(self, "_store", store)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("AlphaPlannerRule cannot be subclassed.")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("the Alpha planner rule is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("the Alpha planner rule is immutable.")

    def __reduce__(self) -> Any:
        raise TypeError("the Alpha planner rule cannot be copied or pickled.")

    def __copy__(self) -> Any:
        raise TypeError("the Alpha planner rule cannot be copied or pickled.")

    def __deepcopy__(self, memo: Any) -> Any:
        raise TypeError("the Alpha planner rule cannot be copied or pickled.")

    def decide_step(self, *, step_contract: StepContract, step_run: StepRun,
                    dispatch: DispatchTicket) -> BoundRoleOutput:
        """The rule's decision for the ``dispatch`` ticket. ``step_run`` is
        cross-checked for identity only; none of its state fields is read."""
        if type(dispatch) is not DispatchTicket:
            raise TypeError("dispatch must be exactly a DispatchTicket.")
        ticket = DispatchTicket.model_validate_json(dispatch.model_dump_json())
        if type(step_contract) is not StepContract or step_contract.sha256 != ticket.step_contract_sha256:
            raise ValueError("the step contract is not the dispatched contract.")
        if type(step_run) is not StepRun or step_run.step_run_id != ticket.step_run_id:
            raise ValueError("the step run is not the dispatched step run.")
        return bind_role_output(ticket, self._store._alpha_planner_decision(ticket))


def mint_alpha_planner_rule(store: Any) -> AlphaPlannerRule:
    """For :mod:`.integration_session` only."""
    return AlphaPlannerRule(store, _token=_RULE_TOKEN)
