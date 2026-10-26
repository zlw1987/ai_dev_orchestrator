"""DL-4B S2 — the one way to hold an integration store (FD-6, FD-16).

:func:`open_integration_session` is the production composition root. It takes
the state root and **nothing else**: the identity boundary prover is S0's
``prove_identity_boundary`` (live Windows facts, the code-constant boundary),
the attestation verifier is S1's ``RegistryHumanAttestationVerifier()`` (the
code-constant registry), and the clock is the system's. There is no parameter,
flag, configuration key or environment variable that supplies a proof, a facts
source, a verifier, a digest or a clock, and no same-account mode.

:func:`open_integration_session_from_facts` runs the identical store over a
caller's synthetic facts and clock, for offline tests and library composition.
Its proofs and verifier records are always ``injected``, its store is marked
``injected`` on creation, and a production session refuses to open that store
(and the reverse), so synthetic authority can never be consumed as production
authority.

Neither session exposes a recorder or any evidence-writing API. S3 mints the
write handoff's recorder (FD-6: it records execution claims and A's own
observations, never a harness call) straight into the session's
:class:`~.write_handoff.WriteHandoffAdapter`, which the session exposes as
``implementer``; the recorder itself is reachable from neither the session nor
the store. A library session reads the real files through the default
:class:`~.authority_files.WindowsAuthorityFiles` unless the caller supplies
``files``, and waits with a caller-supplied ``waiter`` (tests); it is never
production either way.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any

from ai_dev_orchestrator.control_plane.containment import AidoStateRoot
from ai_dev_orchestrator.integration.attestation_verifier import RegistryHumanAttestationVerifier
from ai_dev_orchestrator.integration.authority_files import AuthorityFiles, WindowsAuthorityFiles
from ai_dev_orchestrator.integration.boundary_facts import SecurityFacts
from ai_dev_orchestrator.integration.claim_receiver import SystemWaiter, Waiter
from ai_dev_orchestrator.integration.identity_boundary import (
    prove_identity_boundary,
    prove_identity_boundary_from_facts,
)
from ai_dev_orchestrator.integration.integration_store import IntegrationStore
from ai_dev_orchestrator.integration.write_handoff import WriteHandoffAdapter, mint_write_handoff_adapter

_SESSION_TOKEN = object()
_SESSION_FIELDS = ("_state_root", "_store", "_implementer")


class IntegrationSession:
    """An open integration store and nothing more.

    It exposes the state root, the store and the bound implementer port. It
    has no recorder, no verifier and no prover attribute, cannot be subclassed
    and is immutable.
    """

    __slots__ = _SESSION_FIELDS

    def __init__(self, state_root: AidoStateRoot, store: IntegrationStore, implementer: WriteHandoffAdapter,
                 *, _token: object = None) -> None:
        if _token is not _SESSION_TOKEN:
            raise TypeError("an integration session is opened only by open_integration_session().")
        object.__setattr__(self, "_state_root", state_root)
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "_implementer", implementer)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("IntegrationSession cannot be subclassed.")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("an integration session is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("an integration session is immutable.")

    def __reduce__(self) -> Any:
        raise TypeError("an integration session cannot be copied or pickled.")

    def __copy__(self) -> Any:
        raise TypeError("an integration session cannot be copied or pickled.")

    def __deepcopy__(self, memo: Any) -> Any:
        raise TypeError("an integration session cannot be copied or pickled.")

    @property
    def state_root(self) -> AidoStateRoot:
        return self._state_root

    @property
    def store(self) -> IntegrationStore:
        return self._store

    @property
    def implementer(self) -> WriteHandoffAdapter:
        """DL-2's implementer port: the write handoff adapter (FD-8)."""
        return self._implementer

    @property
    def boundary_sha256(self) -> str:
        """The identity boundary digest this session is pinned to."""
        return self._store.boundary_sha256

    @property
    def is_production(self) -> bool:
        return self._store.is_production

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> IntegrationSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def open_integration_session(state_root: AidoStateRoot) -> IntegrationSession:
    """Prove the FD-16 identity boundary for this process, then open the
    integration store of ``state_root``, which must be the boundary's declared
    state root. Nothing is created or opened if the proof fails."""
    key = object()
    store = IntegrationStore._open_integration(
        state_root,
        prove=prove_identity_boundary,
        verifier=RegistryHumanAttestationVerifier(),
        clock=None,
        files=WindowsAuthorityFiles,
        waiter=SystemWaiter(),
        write_key=key,
    )
    return IntegrationSession(state_root, store, mint_write_handoff_adapter(store, key), _token=_SESSION_TOKEN)


def open_integration_session_from_facts(
    state_root: AidoStateRoot,
    facts: SecurityFacts,
    *,
    clock: Callable[[], datetime],
    files: AuthorityFiles | None = None,
    waiter: Waiter | None = None,
) -> IntegrationSession:
    """The same session over ``facts``, ``clock`` and, when given, ``files``
    and ``waiter``. Never production: every proof and record is ``injected``,
    and so is the store it creates."""
    if not callable(clock):
        raise TypeError("clock must be callable.")
    key = object()
    store = IntegrationStore._open_integration(
        state_root,
        prove=partial(prove_identity_boundary_from_facts, facts, clock=clock),
        verifier=RegistryHumanAttestationVerifier.from_facts(facts, clock=clock),
        clock=clock,
        files=WindowsAuthorityFiles if files is None else (lambda: files),
        waiter=waiter,
        write_key=key,
    )
    return IntegrationSession(state_root, store, mint_write_handoff_adapter(store, key), _token=_SESSION_TOKEN)
