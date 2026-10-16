"""The durable single-use authorization ledger (ALPHA-P1B-FU1).

P1B first spent an authorization by creating ``<evidence>/<run_id>``. That made
run evidence the only record of consumption, so deleting the run directory, or
rotating the evidence directory, made a spent authorization usable again (the
B-1 review finding). The ledger fixes that by inverting what proves an
authorization unused:

- **Unused is proven by a positive record, never by an absence.**
  ``prepare`` creates ``<ledger>/<run_id>.issued.json`` exclusively. It holds a
  fresh 256-bit issuance nonce, and the authorization's ``bound`` section binds
  the nonce's SHA-256 (``issuance_sha256``). A missing ledger, a missing record,
  or a record that does not match the authorization exactly is **refused**, so
  deleting, renaming or rotating anything can only ever remove authority.
- **Consumption is one exclusive create.** ``run`` creates the tombstone
  ``<ledger>/<run_id>.consumed.json`` with ``O_CREAT | O_EXCL`` (``CREATE_NEW``),
  which admits exactly one creator, so concurrent consumers are serialized
  there. A tombstone that exists in any form, even empty or partial, means
  spent. ``os.rename`` and ``os.remove`` are deliberately *not* the
  linearization point: on Windows, racing threads that each opened the same
  source before any of them finished have all been observed to report success
  for both, while ``O_EXCL`` produced exactly one winner every time.
- **Consumption destroys the nonce.** Only the tombstone's creator then
  re-checks the issuance record and deletes it. The nonce is stored nowhere
  else: never in the tombstone, the authorization, the evidence or any output.
  A spent authorization cannot be re-issued from anything left behind; only a
  copy of the ledger taken *before* consumption could restore it.
- **Transmission happens only from the settled spent state**: tombstone
  present, issuance record gone. Any failure on the way there is terminal and
  sends nothing. So under any pattern of deletion, at most one request is ever
  sent per authorization.

The ledger directory is named by ``supervised_implementer.authorization_ledger_dir``
in project config. It must exist, be absolute, canonical, outside the workspace
and disjoint from the evidence directory. Its canonical path is bound into the
authorization (``authorization_ledger_dir_sha256``) and, through the config, into
``project_config_sha256``, so pointing a run at another ledger is refused.

**What it does not defend against.** The ledger is ordinary files protected by
the OS account's permissions. Restoring a copy of the ledger taken before
consumption (a backup, a volume snapshot, a sync client's version history) and
removing the tombstone restores the authorization until it expires. That is a
deliberate rollback of AIDO's authority state, the same class as recomputing
``binding_sha256`` after editing ``bound``, and it is outside the threat model
(A-19): the human is the trust root. One narrower case has the same shape: if
the issuance record cannot be deleted after the tombstone exists (an OS
failure), the run ends ``authorization_ledger_settle_failed`` and sends
nothing, and a person who then deletes the tombstone (and the run directory,
if one was created) by hand makes that never-transmitted authorization usable
for its first and only request. Durability across power loss is not claimed: records
are fsynced, but Windows offers no directory fsync.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError, field_validator

from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused

ISSUANCE_SCHEMA_VERSION = "supervised-implementer-issuance.v1"
CONSUMPTION_SCHEMA_VERSION = "supervised-implementer-consumption.v1"
ISSUED_SUFFIX = ".issued.json"
CONSUMED_SUFFIX = ".consumed.json"

#: The largest ledger record ``run`` will read. Records are a few hundred bytes.
MAX_LEDGER_RECORD_BYTES = 4096

_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class LedgerSpentUnsettled(Exception):
    """The tombstone exists, but the ledger could not reach the settled spent state.

    The authorization is spent. Nothing may be sent. ``category`` and
    ``message`` are fixed text and never carry a path or exception detail.
    """

    def __init__(self, category: str, message: str) -> None:
        super().__init__(f"{category}: {message}")
        self.category = category
        self.message = message


def _refuse(category: str, message: str) -> SupervisedImplementerRefused:
    return SupervisedImplementerRefused(category, message)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _check_run_id(run_id: object) -> str:
    """A run id becomes a file name, so its shape is checked before any path is built."""
    if type(run_id) is not str or not _RUN_ID.fullmatch(run_id):
        raise _refuse("authorization_ledger_mismatch", "the run id is not 32 lowercase hex characters.")
    return run_id


def issued_path(ledger_dir: str, run_id: str) -> str:
    return os.path.join(ledger_dir, _check_run_id(run_id) + ISSUED_SUFFIX)


def consumed_path(ledger_dir: str, run_id: str) -> str:
    return os.path.join(ledger_dir, _check_run_id(run_id) + CONSUMED_SUFFIX)


def new_issuance_nonce() -> tuple[str, str]:
    """Return ``(nonce, issuance_sha256)``. Only the digest goes into the authorization."""
    nonce = secrets.token_hex(32)
    return nonce, _sha256_hex(nonce.encode("ascii"))


class _IssuanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["supervised-implementer-issuance.v1"]
    run_id: StrictStr
    binding_sha256: StrictStr
    issuance_nonce: StrictStr
    issued_at: StrictStr

    @field_validator("run_id")
    @classmethod
    def _run_id_shape(cls, value: str) -> str:
        if not _RUN_ID.fullmatch(value):
            raise ValueError("bad run id")
        return value

    @field_validator("binding_sha256", "issuance_nonce")
    @classmethod
    def _hex_shape(cls, value: str) -> str:
        if not _HEX64.fullmatch(value):
            raise ValueError("bad digest")
        return value


def _create_record_exclusive(path: str, data: bytes) -> None:
    """Exclusive create, whole write, fsync. Raises ``FileExistsError`` on a lost race.

    Split from the caller so a failure *after* the file exists is distinguishable
    from a failure to create it: see :func:`consume_issuance`.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def issue_authorization(
    ledger_dir: str, *, run_id: str, binding_sha256: str, nonce: str, issued_at: str
) -> None:
    """``prepare``: create the one issuance record. Never overwrites anything.

    Refuses if any record for this run id already exists. Only AIDO's
    ``prepare`` creates issuance records; nothing else in AIDO does.
    """
    if os.path.lexists(consumed_path(ledger_dir, run_id)) or os.path.lexists(
        issued_path(ledger_dir, run_id)
    ):
        raise _refuse(
            "authorization_ledger_conflict",
            "the ledger already holds a record for this run id. No draft was written.",
        )
    record = {
        "schema_version": ISSUANCE_SCHEMA_VERSION,
        "run_id": run_id,
        "binding_sha256": binding_sha256,
        "issuance_nonce": nonce,
        "issued_at": issued_at,
    }
    try:
        _create_record_exclusive(issued_path(ledger_dir, run_id), _canonical_json(record))
    except OSError:
        raise _refuse(
            "authorization_ledger_write_failed",
            "the issuance record could not be written to the authorization ledger. "
            "No draft was written.",
        ) from None


def _read_record(path: str) -> bytes:
    """Read one ledger record: a plain regular file, no link or reparse point, bounded.

    ``FileNotFoundError`` propagates; every other problem is a refusal.
    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise
    except OSError:
        raise _refuse(
            "authorization_ledger_corrupt", "the issuance record could not be inspected."
        ) from None
    if (
        not stat.S_ISREG(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
        or info.st_size > MAX_LEDGER_RECORD_BYTES
    ):
        raise _refuse(
            "authorization_ledger_corrupt",
            "the issuance record is not a plain, small regular file.",
        )
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_LEDGER_RECORD_BYTES + 1)
    except FileNotFoundError:
        raise
    except OSError:
        raise _refuse(
            "authorization_ledger_corrupt", "the issuance record could not be read."
        ) from None
    if len(data) > MAX_LEDGER_RECORD_BYTES:
        raise _refuse("authorization_ledger_corrupt", "the issuance record is too large.")
    return data


def _check_issuance_matches(
    data: bytes, *, run_id: str, binding_sha256: str, issuance_sha256: str
) -> None:
    """The record must belong to exactly this authorization: run id, binding, nonce."""
    try:
        record = _IssuanceRecord.model_validate(json.loads(data.decode("ascii")))
    except (UnicodeDecodeError, ValueError, ValidationError, RecursionError):
        raise _refuse(
            "authorization_ledger_corrupt",
            "the issuance record is malformed. Nothing was sent.",
        ) from None
    if (
        record.run_id != run_id
        or record.binding_sha256 != binding_sha256
        or _sha256_hex(record.issuance_nonce.encode("ascii")) != issuance_sha256
    ):
        raise _refuse(
            "authorization_ledger_mismatch",
            "the issuance record does not belong to this exact authorization. "
            "Nothing was sent.",
        )


def _already_consumed(message: str) -> SupervisedImplementerRefused:
    return _refuse("authorization_already_consumed", message)


def check_unspent(
    ledger_dir: str, *, run_id: str, binding_sha256: str, issuance_sha256: str
) -> None:
    """Refuse unless the ledger proves this exact authorization issued and unspent.

    Read-only. A tombstone, in any form, dominates and means spent. Then a
    positive issuance record must exist and match the authorization's run id,
    binding digest and nonce digest exactly. Absence is never "unused".
    """
    tombstone = consumed_path(ledger_dir, run_id)
    if os.path.lexists(tombstone):
        raise _already_consumed(
            "the authorization ledger records this authorization as consumed. A "
            "consumed authorization is never reusable; run prepare again. Nothing was sent."
        )
    try:
        data = _read_record(issued_path(ledger_dir, run_id))
    except FileNotFoundError:
        if os.path.lexists(tombstone):  # a racing invocation won meanwhile
            raise _already_consumed(
                "another invocation consumed this authorization. Nothing was sent."
            ) from None
        raise _refuse(
            "authorization_not_issued",
            "the authorization ledger holds no unspent issuance record for this "
            "authorization. A missing record is never treated as unused: it may "
            "have been consumed, deleted or rotated away. Run prepare again. "
            "Nothing was sent.",
        ) from None
    _check_issuance_matches(
        data, run_id=run_id, binding_sha256=binding_sha256, issuance_sha256=issuance_sha256
    )


def consume_issuance(
    ledger_dir: str,
    *,
    run_id: str,
    binding_sha256: str,
    issuance_sha256: str,
    consumed_at: str,
) -> None:
    """Spend the authorization. Returns only once the ledger is settled spent.

    Raises:
        SupervisedImplementerRefused: the ledger was not changed; the
            authorization is exactly as it was (unspent, or already spent by
            someone else).
        LedgerSpentUnsettled: the tombstone exists, so the authorization is
            spent, but the ledger did not reach the settled state. Nothing may
            be sent.
    """
    check_unspent(
        ledger_dir, run_id=run_id, binding_sha256=binding_sha256, issuance_sha256=issuance_sha256
    )
    tombstone = consumed_path(ledger_dir, run_id)
    try:
        _create_record_exclusive(
            tombstone,
            _canonical_json(
                {
                    "schema_version": CONSUMPTION_SCHEMA_VERSION,
                    "run_id": run_id,
                    "binding_sha256": binding_sha256,
                    "issuance_sha256": issuance_sha256,
                    "consumed_at": consumed_at,
                }
            ),
        )
    except FileExistsError:
        raise _already_consumed(
            "another invocation consumed this authorization first. Nothing was sent."
        ) from None
    except OSError:
        if not os.path.lexists(tombstone):
            raise _refuse(
                "authorization_ledger_write_failed",
                "the consumption record could not be created, so the authorization "
                "was not consumed. Nothing was sent.",
            ) from None
        raise LedgerSpentUnsettled(
            "authorization_ledger_write_failed",
            "the consumption record was created but could not be completed. The "
            "authorization is spent. Nothing was sent.",
        ) from None

    # The tombstone exists: every path from here is spent, and only this one
    # invocation can be here. The issuance bytes are checked again, so a record
    # swapped after the read-only check never transmits; then the nonce, whose
    # only copy is that record, is destroyed.
    issued = issued_path(ledger_dir, run_id)
    try:
        _check_issuance_matches(
            _read_record(issued),
            run_id=run_id,
            binding_sha256=binding_sha256,
            issuance_sha256=issuance_sha256,
        )
    except SupervisedImplementerRefused as exc:
        raise LedgerSpentUnsettled(
            exc.category,
            "the issuance record changed after it was checked. The authorization "
            "is spent. Nothing was sent.",
        ) from None
    except Exception:  # noqa: BLE001 - a fixed category; the path is never echoed.
        raise LedgerSpentUnsettled(
            "authorization_ledger_settle_failed",
            "the issuance record could not be re-read after consumption. The "
            "authorization is spent. Nothing was sent.",
        ) from None
    try:
        os.remove(issued)
    except Exception:  # noqa: BLE001 - a fixed category; the path is never echoed.
        raise LedgerSpentUnsettled(
            "authorization_ledger_settle_failed",
            "the authorization is spent, but its issuance record could not be "
            "removed. Nothing was sent.",
        ) from None
    if os.path.lexists(issued) or not os.path.lexists(tombstone):
        raise LedgerSpentUnsettled(
            "authorization_ledger_settle_failed",
            "the ledger is not in the settled spent state after consumption. "
            "Nothing was sent.",
        )
