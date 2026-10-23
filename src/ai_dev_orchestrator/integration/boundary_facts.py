"""DL-4B S0 — the Windows security facts the identity-boundary proof consumes.

The proof (:mod:`.identity_boundary`) never calls Windows itself. It asks a
:class:`SecurityFacts` source for plain, immutable facts and decides everything
from them. Two sources exist:

- the production source in :mod:`.windows_security`, which reads the facts
  from the running process's own token and from the objects named by the
  identity boundary, with read-only Win32 calls; and
- any other object implementing :class:`SecurityFacts`, which is how the
  offline tests present synthetic descriptors and synthetic SIDs.

A proof records which kind of source produced it (``facts_origin``), and only
the production entry point can produce ``"windows"``. A supported caller that
implements this protocol can therefore never obtain a production proof.

Facts are re-validated where the proof consumes them (exact types, parseable
descriptors, canonical SIDs); a source is never trusted to have validated them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai_dev_orchestrator.integration.security_descriptor import ObjectKind, Principal


@dataclass(frozen=True)
class ObjectFacts:
    """One file-system object, read from a single handle opened without
    following a reparse point.

    ``final_path`` is the path Windows reports for that handle (``None`` when
    the source did not resolve it); the proof compares it with the declared
    path to refuse short names, case tricks and redirected components.
    """

    final_path: str | None
    is_directory: bool
    is_reparse_point: bool
    link_count: int
    security_descriptor: bytes


@dataclass(frozen=True)
class DirectoryEntry:
    """One entry as the directory listing reports it, without opening it."""

    name: str
    is_directory: bool
    #: ``FILE_ATTRIBUTE_REPARSE_POINT`` from the listing itself, so a
    #: subdirectory that a standard user cannot open is still classified.
    is_reparse_point: bool


@dataclass(frozen=True)
class TokenFacts:
    """The running process's primary token."""

    user_sid: str
    #: ``(sid, SE_GROUP_* attributes)`` for every group, including deny-only,
    #: logon and integrity entries.
    groups: tuple[tuple[str, int], ...]
    #: Every privilege present in the token, enabled or not: a disabled
    #: privilege can be enabled by the process itself.
    privileges: tuple[str, ...]
    elevated: bool
    #: ``TOKEN_ELEVATION_TYPE``: 1 default, 2 full, 3 limited (a filtered admin).
    elevation_type: int
    integrity_rid: int
    #: The token's default DACL (applied to threads and objects it creates),
    #: as a bare ACL.
    default_dacl: bytes
    #: The logon session's LUID (``TOKEN_STATISTICS.AuthenticationId``) as one
    #: unsigned 64-bit number, high part first. A non-interactive window
    #: station created for a logon session is named after it.
    authentication_id: int


@dataclass(frozen=True)
class PrincipalFacts:
    """One account, as the OS computes it from its SID alone (AuthZ)."""

    sid: str
    #: ``DOMAIN\\name`` as ``LookupAccountSid`` reports it.
    account_name: str
    #: ``SID_NAME_USE``; 1 is ``SidTypeUser``.
    sid_type: int
    #: The account's domain is this computer (a local account).
    is_local_account: bool
    groups: tuple[tuple[str, int], ...]
    privileges: tuple[str, ...]


@dataclass(frozen=True)
class SessionFacts:
    window_station: str
    window_station_visible: bool
    window_station_sid: str | None
    desktop: str
    desktop_sid: str | None
    #: Self-relative descriptors (owner and DACL) of the process's window
    #: station and of its thread's desktop: who else may open and use them.
    window_station_descriptor: bytes
    desktop_descriptor: bytes


@dataclass(frozen=True)
class ProcessFacts:
    """Security descriptors of the running process, its current thread and
    its primary token (each self-relative bytes)."""

    process_descriptor: bytes
    thread_descriptor: bytes
    token_descriptor: bytes


@dataclass(frozen=True)
class CodeLoadFacts:
    """Where the running interpreter loads code and searches for executables."""

    executables: tuple[str, ...]
    prefixes: tuple[str, ...]
    import_paths: tuple[str, ...]
    search_paths: tuple[str, ...]
    working_directory: str
    package_directory: str
    profile_directories: tuple[str, ...]
    #: The interpreter ignores ``PYTHON*`` variables, has no user site and puts
    #: no script or working directory on ``sys.path`` (``-I``, or ``-E -s -P``).
    isolated_interpreter: bool


class SecurityFacts(Protocol):
    """A source of Windows security facts. Every method may raise; the proof
    turns any exception into a ``security_fact_unavailable`` refusal."""

    def is_windows(self) -> bool: ...

    def environment_names(self) -> tuple[str, ...]: ...

    def current_token(self) -> TokenFacts: ...

    def program_data_directory(self) -> str: ...

    def read_file(self, path: str, limit: int) -> tuple[ObjectFacts, bytes] | None:
        """One file's facts and at most ``limit + 1`` bytes of it, from one
        handle that denies write sharing; ``None`` if it does not exist."""
        ...

    def object_facts(self, path: str) -> ObjectFacts | None:
        """``None`` if nothing exists at ``path``."""
        ...

    def list_directory(self, path: str) -> tuple[DirectoryEntry, ...]: ...

    def principal(self, sid: str) -> PrincipalFacts: ...

    def session(self) -> SessionFacts: ...

    def process(self) -> ProcessFacts: ...

    def code_load(self) -> CodeLoadFacts: ...

    def independent_rights(self, descriptor: bytes, principal: Principal, kind: ObjectKind) -> int | None:
        """An upper bound computed by an evaluator independent of
        :func:`~.security_descriptor.upper_bound_rights` (AuthZ in production),
        over the already-transformed ``descriptor`` and ``principal.allow_sids``;
        ``None`` if this source has no such evaluator."""
        ...
