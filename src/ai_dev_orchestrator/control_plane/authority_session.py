"""DL-4A — the one way to open an authority store.

:func:`open_authority_session` is the composition root's entry point. It opens
the authority store of a verified :class:`AidoStateRoot`, wires the external
:class:`~ai_dev_orchestrator.control_plane.authority.HumanAttestationVerifier`
(by default one that approves nothing), and mints this session's single
:class:`VerificationEvidenceRecorder`. The recorder exists only on the returned
session: the store has no method that hands one out, so code that was not given
it cannot record verification evidence.

What the composition root must supply, and DL-4A cannot: a verifier whose
``True`` cannot be produced by the AIDO process itself, and a verification
adapter that records only bytes produced by the shipped 5F2D verification. See
``docs/DL4A_REAL_INTEGRATION_AUTHORITY.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ai_dev_orchestrator.control_plane.authority import (
    DispatchTicket,
    HumanAttestationVerifier,
    UnavailableHumanAttestationVerifier,
    VerificationEvidenceReceipt,
)
from ai_dev_orchestrator.control_plane.containment import AidoStateRoot
from ai_dev_orchestrator.control_plane.store import (
    ControlPlaneStore,
    StoreError,
    _AuthorityContext,
)

_RECORDER_TOKEN = object()


class VerificationEvidenceRecorder:
    """Records ``verification-result.v1`` bytes for one verifier dispatch.

    Give it only to the deterministic verification adapter. The store derives
    the outcome from the bytes and binds the record to the ticket's Project Run,
    Step Run, contract, attempt and version; the adapter names none of them.
    """

    def __init__(self, store: ControlPlaneStore, key: object, *, _token: object = None) -> None:
        if _token is not _RECORDER_TOKEN:
            raise StoreError("a verification recorder is minted only by open_authority_session().")
        self._store = store
        self._key = key

    def record(self, ticket: DispatchTicket, verification_result: bytes) -> VerificationEvidenceReceipt:
        return self._store._record_verification_evidence(self._key, ticket, verification_result)


class AuthoritySession:
    """An open authority store and the capabilities minted with it."""

    def __init__(
        self,
        state_root: AidoStateRoot,
        store: ControlPlaneStore,
        verification_recorder: VerificationEvidenceRecorder,
    ) -> None:
        self.state_root = state_root
        self.store = store
        self.verification_recorder = verification_recorder

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> AuthoritySession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def open_authority_session(
    state_root: AidoStateRoot,
    *,
    approval_verifier: HumanAttestationVerifier | None = None,
    clock: Callable[[], datetime] | None = None,
) -> AuthoritySession:
    """Open ``state_root``'s authority store (creating it if new).

    Without ``approval_verifier`` no human approval can ever be confirmed, so
    nothing can be approved, issued or run: that is the fail-closed default.
    """
    if type(state_root) is not AidoStateRoot:
        raise StoreError("an authority session needs an AidoStateRoot.")
    key = object()
    store = ControlPlaneStore._open_authority(
        _AuthorityContext(
            root=state_root,
            verifier=approval_verifier or UnavailableHumanAttestationVerifier(),
            recorder_key=key,
        ),
        clock,
    )
    recorder = VerificationEvidenceRecorder(store, key, _token=_RECORDER_TOKEN)
    return AuthoritySession(state_root, store, recorder)
