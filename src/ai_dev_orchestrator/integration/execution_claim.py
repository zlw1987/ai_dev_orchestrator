"""DL-4B S4 — the execution claim adapter, VERIFYING half (FD-6, FD-8).

:class:`ExecutionClaimAdapter` answers DL-2's verifier dispatch. It does not
verify, run, launch or call anything. It hands the store the dispatch ticket
it was given, through a capability (its **recorder**) that only the session
that opened the store holds, and the store performs the whole review handoff
itself from its own records (§5.2, AMEND1):

```text
handoff-<verifier ticket> (the write intent's approved artifact + config bytes)
   → the HUMAN runs the existing `l2-review-approved-file-edit` as X, stdout to the outbox
   → claim read once (FD-17) and classified by its bytes alone
   → M2 (A's own reads) against M1 → verification_evidence_v2 iff claim binds and M2 holds
```

What the adapter returns is a bound
:class:`~ai_dev_orchestrator.control_plane.models.VerificationObservation`
built from the store's **receipt**: the outcome the claim's own facts support
and the claim's digest. It is never authority-plane evidence that the
verification executable behaved honestly (FD-15, D-2′); the store accepts
``VERIFICATION_OBSERVED`` only for the dispatch whose claim and M2 it bound,
whoever presents it.

S5's reviewer is answered from the same recorded claim. This module has no
``review`` method yet, and nothing here runs the review command again.

The adapter takes no path, artifact, config, claim, observation, digest or
report from its caller: the contract and attempt it is handed are only
cross-checked against the ticket the store re-proves.
"""

from __future__ import annotations

from typing import Any

from ai_dev_orchestrator.control_plane.authority import BoundRoleOutput, DispatchTicket, bind_role_output
from ai_dev_orchestrator.control_plane.models import StepContract

_ADAPTER_TOKEN = object()


class _ClaimRecorder:
    """The execution claim adapter's recorder capability. Held only by its adapter."""

    __slots__ = ("_store", "_key")

    def __init__(self, store: Any, key: object) -> None:
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "_key", key)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("a recorder is immutable.")

    def __reduce__(self) -> Any:
        raise TypeError("a recorder cannot be copied or pickled.")

    def hand_off_review(self, ticket: DispatchTicket):
        return self._store._perform_review_handoff(self._key, ticket)


class ExecutionClaimAdapter:
    """DL-2's ``BoundVerifierPort`` in an integration session."""

    __slots__ = ("_recorder",)

    def __init__(self, store: Any, key: object, *, _token: object = None) -> None:
        if _token is not _ADAPTER_TOKEN:
            raise TypeError("an execution claim adapter is minted only by open_integration_session().")
        object.__setattr__(self, "_recorder", _ClaimRecorder(store, key))

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("ExecutionClaimAdapter cannot be subclassed.")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("an execution claim adapter is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("an execution claim adapter is immutable.")

    def __reduce__(self) -> Any:
        raise TypeError("an execution claim adapter cannot be copied or pickled.")

    def __copy__(self) -> Any:
        raise TypeError("an execution claim adapter cannot be copied or pickled.")

    def __deepcopy__(self, memo: Any) -> Any:
        raise TypeError("an execution claim adapter cannot be copied or pickled.")

    def verify(self, *, step_contract: StepContract, attempt: int, dispatch: DispatchTicket) -> BoundRoleOutput:
        """Hand off the review command for ``dispatch`` and wait for the human.

        Raises when no claim binds with M2 holding; DL-2 then reduces the step
        to RECOVERY_REQUIRED. Nothing is retried and nothing runs twice.
        """
        if type(dispatch) is not DispatchTicket:
            raise TypeError("dispatch must be exactly a DispatchTicket.")
        ticket = DispatchTicket.model_validate_json(dispatch.model_dump_json())
        if type(step_contract) is not StepContract or step_contract.sha256 != ticket.step_contract_sha256:
            raise ValueError("the step contract is not the dispatched contract.")
        if type(attempt) is not int or attempt != ticket.attempt:
            raise ValueError("the attempt is not the dispatched attempt.")
        observation = self._recorder.hand_off_review(ticket)
        return bind_role_output(ticket, observation)


def mint_execution_claim_adapter(store: Any, key: object) -> ExecutionClaimAdapter:
    """For :mod:`.integration_session` only: mint the adapter around ``key``."""
    return ExecutionClaimAdapter(store, key, _token=_ADAPTER_TOKEN)
