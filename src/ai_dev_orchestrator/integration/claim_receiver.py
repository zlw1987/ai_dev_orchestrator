"""DL-4B S3 — receiving one execution claim from a per-ticket outbox (FD-17).

The human runs an existing command as the execution identity X, redirects its
stdout to ``<outbox>\\stdout.json`` in X's own shell, and only after the
command exits creates an empty ``<outbox>\\complete``. A then:

```text
1  waits for `complete` to a FIXED code-constant bound (not config, not a CLI
   option); on expiry nothing is read and the dispatch fails
2  requires the outbox to hold EXACTLY stdout.json and complete
3  requires each to be a regular file, not a reparse point, with one link,
   owned by X's SID, at the path it was opened by; `complete` empty; stdout.json
   non-empty and within a fixed size cap
4  reads stdout.json ONCE, from one handle that denies write and delete
   sharing, and hashes those bytes; a sharing violation refuses
```

What this establishes is a **receipt**: these bytes arrived in the outbox A
created for this ticket. It is never evidence that a frozen harness ran, or
that what the bytes say is true (FD-15). Classification and binding are the
caller's, against A's own observations.

The receiver reads only the one outbox path it is handed, which the store
derives from the ticket it created the outbox for; it has no path, bytes or
claim parameter of any other kind.
"""

from __future__ import annotations

import hashlib
import ntpath
import time
from dataclasses import dataclass
from typing import Protocol

from ai_dev_orchestrator.integration.authority_files import AuthorityFiles
from ai_dev_orchestrator.integration.boundary_facts import ObjectFacts
from ai_dev_orchestrator.integration.security_descriptor import DescriptorError, parse_security_descriptor

#: FD-17 fixed bounds. Code constants; AUTH-PILOT records their values.
CLAIM_WAIT_SECONDS = 2 * 60 * 60
CLAIM_POLL_SECONDS = 2.0
STDOUT_NAME = "stdout.json"
COMPLETE_NAME = "complete"
_ERROR_SHARING_VIOLATION = 32


class Waiter(Protocol):
    """How A waits: a monotonic clock and a sleep."""

    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemWaiter:
    """The production waiter: ``time.monotonic`` and ``time.sleep``."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class ClaimProtocolError(Exception):
    """The outbox did not deliver exactly one well-formed claim. Nothing was
    recorded as a claim. ``category`` names the deviation."""

    def __init__(self, category: str, detail: str) -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"claim_refused:{category}: {detail}")


@dataclass(frozen=True)
class ReceivedClaim:
    """Bytes A read once from an outbox. A receipt, never a fact."""

    data: bytes
    sha256: str


def _call(what: str, method, *args):
    try:
        return method(*args)
    except ClaimProtocolError:
        raise
    except Exception as exc:  # noqa: BLE001 - an unreadable outbox delivers nothing
        code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
        if code == _ERROR_SHARING_VIOLATION or "error 32)" in str(exc):
            raise ClaimProtocolError("sharing_violation", f"{what} is open for writing elsewhere.") from None
        raise ClaimProtocolError(
            "read_failed", f"{what} could not be read ({type(exc).__name__}{f' {code}' if code else ''})."
        ) from None


def await_completion(files: AuthorityFiles, outbox: str, waiter: Waiter, deadline: float) -> None:
    """Return once ``complete`` is listed in ``outbox``; refuse at ``deadline``.

    Only the listing is consulted while waiting; no file is opened.
    """
    while True:
        entries = _call("the outbox listing", files.list_directory, outbox)
        if type(entries) is not tuple:
            raise ClaimProtocolError("read_failed", "the outbox listing is malformed.")
        if any(getattr(entry, "name", None) == COMPLETE_NAME for entry in entries):
            return
        remaining = deadline - waiter.monotonic()
        if remaining <= 0:
            raise ClaimProtocolError(
                "deadline_expired", f"no completion marker arrived within {CLAIM_WAIT_SECONDS} seconds."
            )
        waiter.sleep(min(CLAIM_POLL_SECONDS, remaining))


def _check_entry(facts: object, path: str, execution_sid: str, what: str) -> None:
    if (
        type(facts) is not ObjectFacts
        or type(facts.is_directory) is not bool
        or type(facts.is_reparse_point) is not bool
        or type(facts.link_count) is not int
        or type(facts.security_descriptor) is not bytes
    ):
        raise ClaimProtocolError("read_failed", f"the facts of {what} are malformed.")
    if facts.is_reparse_point:
        raise ClaimProtocolError("reparse_point", f"{what} is a reparse point.")
    if facts.is_directory:
        raise ClaimProtocolError("not_regular_file", f"{what} is a directory.")
    if facts.link_count != 1:
        raise ClaimProtocolError("hard_link", f"{what} has more than one link.")
    if facts.final_path is None or ntpath.normcase(facts.final_path) != ntpath.normcase(path):
        raise ClaimProtocolError("path_mismatch", f"{what} is not at the path it was opened by.")
    try:
        owner = parse_security_descriptor(facts.security_descriptor).owner
    except DescriptorError:
        raise ClaimProtocolError("read_failed", f"the owner of {what} cannot be read.") from None
    if owner != execution_sid:
        raise ClaimProtocolError("wrong_owner", f"{what} is not owned by the execution identity.")


def read_claim(files: AuthorityFiles, outbox: str, execution_sid: str, limit: int) -> ReceivedClaim:
    """Read the one claim in a completed outbox, exactly once, or refuse."""
    entries = _call("the outbox listing", files.list_directory, outbox)
    if type(entries) is not tuple:
        raise ClaimProtocolError("read_failed", "the outbox listing is malformed.")
    names = sorted(getattr(entry, "name", None) for entry in entries)
    if names != sorted([STDOUT_NAME, COMPLETE_NAME]):
        category = "missing_entry" if set(names) < {STDOUT_NAME, COMPLETE_NAME} else "unexpected_entry"
        raise ClaimProtocolError(category, "the outbox does not hold exactly stdout.json and complete.")
    for entry in entries:
        if entry.is_reparse_point:
            raise ClaimProtocolError("reparse_point", f"outbox/{entry.name} is a reparse point.")
        if entry.is_directory:
            raise ClaimProtocolError("not_regular_file", f"outbox/{entry.name} is a directory.")

    marker_path = ntpath.join(outbox, COMPLETE_NAME)
    marker = _call("outbox/complete", files.read_file, marker_path, 0)
    if marker is None:
        raise ClaimProtocolError("missing_entry", "outbox/complete vanished.")
    _check_entry(marker[0], marker_path, execution_sid, "outbox/complete")
    if marker[1] != b"":
        raise ClaimProtocolError("marker_not_empty", "outbox/complete is not empty.")

    stdout_path = ntpath.join(outbox, STDOUT_NAME)
    read = _call("outbox/stdout.json", files.read_file, stdout_path, limit)
    if read is None:
        raise ClaimProtocolError("missing_entry", "outbox/stdout.json vanished.")
    facts, data = read
    _check_entry(facts, stdout_path, execution_sid, "outbox/stdout.json")
    if type(data) is not bytes:
        raise ClaimProtocolError("read_failed", "outbox/stdout.json did not read as bytes.")
    if not data:
        raise ClaimProtocolError("empty", "outbox/stdout.json is empty.")
    if len(data) > limit:
        raise ClaimProtocolError("oversize", "outbox/stdout.json exceeds the claim size cap.")
    return ReceivedClaim(data=data, sha256=hashlib.sha256(data).hexdigest())
