"""DL-4B S3 — per-ticket handoff and outbox directories (FD-14, FD-17).

For one implementer dispatch A creates, in the exchange root the identity
boundary declares (owned by A, protected, X and O read-only — S0 proves it):

```text
<exchange>\\handoff-<ticket>\\   created EXCLUSIVELY with a protected DACL set at creation:
                                A full; X read and execute; SYSTEM, Administrators full;
                                O nothing. Holds exactly two files A writes once:
    approved-diff-proposal.json    the human-approved artifact bytes, verbatim
    project.yaml                   the project config bytes, verbatim
<exchange>\\outbox-<ticket>\\    created EXCLUSIVELY, protected: an OWNER RIGHTS ACE
                                limits its owner A to read; X may list and add files,
                                and read, write and delete the files it creates
                                (never re-permission them: OWNER RIGHTS is inherited);
                                O reads; SYSTEM, Administrators full
```

A directory that already exists is refused (never adopted), and after
creation each one is re-read: a directory at the path it was created by, not
a reparse point, owned by A, with exactly the protected DACL A specified. The
handoff must list exactly its two files, each a single-link regular file
holding exactly the bytes A wrote; the outbox must be empty. Identities
``(volume, file id)`` are returned for the store to record.

Nothing here deletes, renames or re-permissions anything, and nothing is
created in the clone.
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass

from ai_dev_orchestrator.integration.authority_files import AuthorityFiles
from ai_dev_orchestrator.integration.boundary_facts import ObjectFacts
from ai_dev_orchestrator.integration.security_descriptor import (
    ACCESS_ALLOWED_ACE_TYPE,
    ADMINISTRATORS,
    CONTAINER_INHERIT_ACE,
    DELETE,
    FILE_ADD_FILE,
    FILE_ALL_ACCESS,
    FILE_GENERIC_READ,
    FILE_GENERIC_WRITE,
    INHERIT_ONLY_ACE,
    LOCAL_SYSTEM,
    OBJECT_INHERIT_ACE,
    OWNER_RIGHTS,
    READ_ONLY,
    Ace,
    DescriptorError,
    build_security_descriptor,
    parse_security_descriptor,
)

HANDOFF_ARTIFACT_NAME = "approved-diff-proposal.json"
HANDOFF_CONFIG_NAME = "project.yaml"
_OICI = OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
_FILES_ONLY = OBJECT_INHERIT_ACE | INHERIT_ONLY_ACE
#: What X may do to a file it creates in its outbox.
OUTBOX_EXECUTION_FILE_RIGHTS = FILE_GENERIC_READ | FILE_GENERIC_WRITE | DELETE
#: What X may do in the outbox directory itself: list and add files.
OUTBOX_EXECUTION_DIRECTORY_RIGHTS = READ_ONLY | FILE_ADD_FILE


class ExchangeError(Exception):
    """A per-ticket directory could not be created or proven as required.
    ``category`` names why."""

    def __init__(self, category: str, detail: str) -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"exchange_refused:{category}: {detail}")


@dataclass(frozen=True)
class PublishedHandoff:
    handoff_identity: str
    outbox_identity: str


def _allow(sid: str, mask: int, flags: int) -> Ace:
    return Ace(ACCESS_ALLOWED_ACE_TYPE, flags, mask, sid)


def handoff_dacl(authority_sid: str, execution_sid: str) -> tuple[Ace, ...]:
    return (
        _allow(authority_sid, FILE_ALL_ACCESS, _OICI),
        _allow(execution_sid, READ_ONLY, _OICI),
        _allow(LOCAL_SYSTEM, FILE_ALL_ACCESS, _OICI),
        _allow(ADMINISTRATORS, FILE_ALL_ACCESS, _OICI),
    )


def outbox_dacl(authority_sid: str, execution_sid: str, operator_sid: str) -> tuple[Ace, ...]:
    return (
        _allow(OWNER_RIGHTS, READ_ONLY, _OICI),
        _allow(authority_sid, READ_ONLY, _OICI),
        _allow(execution_sid, OUTBOX_EXECUTION_DIRECTORY_RIGHTS, 0),
        _allow(execution_sid, OUTBOX_EXECUTION_FILE_RIGHTS, _FILES_ONLY),
        _allow(operator_sid, READ_ONLY, _OICI),
        _allow(LOCAL_SYSTEM, FILE_ALL_ACCESS, _OICI),
        _allow(ADMINISTRATORS, FILE_ALL_ACCESS, _OICI),
    )


def ticket_directories(exchange_root: str, ticket_id: str) -> tuple[str, str]:
    """The handoff and outbox paths of one ticket. The ticket id is AIDO's own
    32-hex identifier, so the names are fixed and unambiguous."""
    if len(ticket_id) != 32 or any(c not in "0123456789abcdef" for c in ticket_id):
        raise ExchangeError("ticket_invalid", "a ticket id is 32 lowercase hexadecimal characters.")
    return (ntpath.join(exchange_root, f"handoff-{ticket_id}"),
            ntpath.join(exchange_root, f"outbox-{ticket_id}"))


def _call(what: str, method, *args):
    try:
        return method(*args)
    except ExchangeError:
        raise
    except FileExistsError:
        raise ExchangeError("pre_existing", f"{what} already exists; it is never adopted.") from None
    except Exception as exc:  # noqa: BLE001 - a failed publication publishes nothing trusted
        raise ExchangeError("io_failed", f"{what} could not be created or read ({type(exc).__name__}).") from None


def _identity(files: AuthorityFiles, path: str, what: str) -> str:
    value = _call(f"the identity of {what}", files.file_identity, path)
    if (
        type(value) is not tuple or len(value) != 2
        or any(type(part) is not int or part < 0 for part in value)
    ):
        raise ExchangeError("io_failed", f"the identity of {what} is malformed.")
    return f"{value[0]}:{value[1]}"


def _checked(facts: object, path: str, what: str, *, directory: bool) -> ObjectFacts:
    if (
        type(facts) is not ObjectFacts
        or type(facts.is_directory) is not bool
        or type(facts.is_reparse_point) is not bool
        or type(facts.link_count) is not int
        or type(facts.security_descriptor) is not bytes
    ):
        raise ExchangeError("io_failed", f"the facts of {what} are malformed.")
    if facts.is_reparse_point:
        raise ExchangeError("substituted", f"{what} is a reparse point.")
    if facts.is_directory != directory:
        raise ExchangeError("substituted", f"{what} is not a {'directory' if directory else 'file'}.")
    if not directory and facts.link_count != 1:
        raise ExchangeError("substituted", f"{what} has more than one link.")
    if facts.final_path is None or ntpath.normcase(facts.final_path) != ntpath.normcase(path):
        raise ExchangeError("substituted", f"{what} is not at the path it was created by.")
    return facts


def verify_directory(files: AuthorityFiles, path: str, authority_sid: str,
                     dacl: tuple[Ace, ...], what: str) -> str:
    """``path`` is the directory A created: owned by A, protected, with
    exactly ``dacl``. Returns its identity."""
    facts = _checked(_call(f"the facts of {what}", files.object_facts, path), path, what, directory=True)
    try:
        descriptor = parse_security_descriptor(facts.security_descriptor)
    except DescriptorError:
        raise ExchangeError("io_failed", f"the security descriptor of {what} cannot be read.") from None
    if descriptor.owner != authority_sid:
        raise ExchangeError("substituted", f"{what} is not owned by the authority identity.")
    if not descriptor.protected or tuple(
        (ace.ace_type, ace.flags, ace.mask, ace.sid) for ace in descriptor.dacl
    ) != tuple((ace.ace_type, ace.flags, ace.mask, ace.sid) for ace in dacl):
        raise ExchangeError("dacl_mismatch", f"{what} does not carry exactly the protected DACL A set.")
    return _identity(files, path, what)


def publish_handoff(
    files: AuthorityFiles,
    *,
    exchange_root: str,
    ticket_id: str,
    authority_sid: str,
    execution_sid: str,
    operator_sid: str,
    artifact: bytes,
    config: bytes,
) -> PublishedHandoff:
    """Create and prove one ticket's handoff (with its two files) and outbox."""
    handoff, outbox = ticket_directories(exchange_root, ticket_id)
    for path, what in ((handoff, "the handoff directory"), (outbox, "the outbox directory")):
        if _call(f"the facts of {what}", files.object_facts, path) is not None:
            raise ExchangeError("pre_existing", f"{what} already exists; it is never adopted.")

    handoff_acl = handoff_dacl(authority_sid, execution_sid)
    _call("the handoff directory", files.create_directory, handoff,
          build_security_descriptor(authority_sid, handoff_acl, protected=True))
    verify_directory(files, handoff, authority_sid, handoff_acl, "the handoff directory")
    contents = {HANDOFF_ARTIFACT_NAME: artifact, HANDOFF_CONFIG_NAME: config}
    for name, content in contents.items():
        _call(f"handoff/{name}", files.create_file, ntpath.join(handoff, name), content)
    listing = _call("the handoff listing", files.list_directory, handoff)
    if type(listing) is not tuple or sorted(getattr(e, "name", None) for e in listing) != sorted(contents):
        raise ExchangeError("substituted", "the handoff does not hold exactly its two files.")
    for name, content in contents.items():
        path = ntpath.join(handoff, name)
        read = _call(f"handoff/{name}", files.read_file, path, len(content))
        if read is None:
            raise ExchangeError("substituted", f"handoff/{name} vanished.")
        _checked(read[0], path, f"handoff/{name}", directory=False)
        if read[1] != content:
            raise ExchangeError("substituted", f"handoff/{name} does not hold the bytes A wrote.")
    handoff_identity = verify_directory(files, handoff, authority_sid, handoff_acl, "the handoff directory")

    outbox_acl = outbox_dacl(authority_sid, execution_sid, operator_sid)
    _call("the outbox directory", files.create_directory, outbox,
          build_security_descriptor(authority_sid, outbox_acl, protected=True))
    outbox_identity = verify_directory(files, outbox, authority_sid, outbox_acl, "the outbox directory")
    if _call("the outbox listing", files.list_directory, outbox) != ():
        raise ExchangeError("substituted", "a new outbox is not empty.")
    return PublishedHandoff(handoff_identity=handoff_identity, outbox_identity=outbox_identity)


def outbox_still_published(files: AuthorityFiles, exchange_root: str, ticket_id: str, *,
                           authority_sid: str, execution_sid: str, operator_sid: str,
                           identity: str) -> str:
    """The outbox A created for ``ticket_id``, re-proven before its claim is
    read: same identity, still A's protected directory. Returns its path."""
    _, outbox = ticket_directories(exchange_root, ticket_id)
    current = verify_directory(files, outbox, authority_sid,
                               outbox_dacl(authority_sid, execution_sid, operator_sid), "the outbox directory")
    if current != identity:
        raise ExchangeError("substituted", "the outbox is not the directory A created for this ticket.")
    return outbox
