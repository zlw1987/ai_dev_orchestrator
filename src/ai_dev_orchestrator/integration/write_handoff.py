"""DL-4B S3 — the write handoff adapter: the only implementer in store.v4 (FD-8).

:class:`WriteHandoffAdapter` answers DL-2's implementer dispatch. It does not
write, run, launch or call anything. It hands the store the dispatch ticket it
was given, through a capability (its **recorder**) that only the session that
opened the store holds, and the store performs the whole write handoff itself
from its own records (§5.5):

```text
M0 (A's own reads) → durable intent, approval spent → handoff-<ticket> + outbox-<ticket>
   → the HUMAN runs the existing `l2-apply-approved-file-edit` as X, stdout to the outbox
   → claim read once (FD-17) → M1 → effect decided by M0/M1 alone → settled intent
```

FD-6: the recorder is minted by :func:`~.integration_session.open_integration_session`
straight into this adapter and is not reachable from the session. The
recorder records claims and A's observations; it never records a harness
call, because no harness runs in A. What the adapter returns is a bound
:class:`~ai_dev_orchestrator.control_plane.models.ImplementationReport` in
AIDO's fixed words. The store accepts ``IMPLEMENTATION_RETURNED`` only for
the dispatch whose write it proved, whoever presents it.

The adapter takes no path, artifact, config, claim, observation, digest or
report from its caller: the contract and attempt it is handed are only
cross-checked against the ticket the store re-proves.
"""

from __future__ import annotations

from typing import Any

from ai_dev_orchestrator.control_plane.authority import BoundRoleOutput, DispatchTicket, bind_role_output
from ai_dev_orchestrator.control_plane.models import StepContract

_ADAPTER_TOKEN = object()


class _WriteRecorder:
    """The write handoff's recorder capability. Held only by its adapter."""

    __slots__ = ("_store", "_key")

    def __init__(self, store: Any, key: object) -> None:
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "_key", key)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("a recorder is immutable.")

    def __reduce__(self) -> Any:
        raise TypeError("a recorder cannot be copied or pickled.")

    def hand_off(self, ticket: DispatchTicket):
        return self._store._perform_write_handoff(self._key, ticket)


class WriteHandoffAdapter:
    """DL-2's ``BoundImplementerPort`` in an integration session."""

    __slots__ = ("_recorder",)

    def __init__(self, store: Any, key: object, *, _token: object = None) -> None:
        if _token is not _ADAPTER_TOKEN:
            raise TypeError("a write handoff adapter is minted only by open_integration_session().")
        object.__setattr__(self, "_recorder", _WriteRecorder(store, key))

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("WriteHandoffAdapter cannot be subclassed.")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("a write handoff adapter is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("a write handoff adapter is immutable.")

    def __reduce__(self) -> Any:
        raise TypeError("a write handoff adapter cannot be copied or pickled.")

    def __copy__(self) -> Any:
        raise TypeError("a write handoff adapter cannot be copied or pickled.")

    def __deepcopy__(self, memo: Any) -> Any:
        raise TypeError("a write handoff adapter cannot be copied or pickled.")

    def implement(self, *, step_contract: StepContract, attempt: int, dispatch: DispatchTicket) -> BoundRoleOutput:
        """Hand off the approved write for ``dispatch`` and wait for the human.

        Raises when the write is not proven exactly as approved; DL-2 then
        reduces the step to RECOVERY_REQUIRED. Nothing is retried.
        """
        if type(dispatch) is not DispatchTicket:
            raise TypeError("dispatch must be exactly a DispatchTicket.")
        ticket = DispatchTicket.model_validate_json(dispatch.model_dump_json())
        if type(step_contract) is not StepContract or step_contract.sha256 != ticket.step_contract_sha256:
            raise ValueError("the step contract is not the dispatched contract.")
        if type(attempt) is not int or attempt != ticket.attempt:
            raise ValueError("the attempt is not the dispatched attempt.")
        report = self._recorder.hand_off(ticket)
        return bind_role_output(ticket, report)


def mint_write_handoff_adapter(store: Any, key: object) -> WriteHandoffAdapter:
    """For :mod:`.integration_session` only: mint the adapter around ``key``."""
    return WriteHandoffAdapter(store, key, _token=_ADAPTER_TOKEN)
