"""The AR2 broker wire protocol. EXPERIMENT ONLY.

Exactly two operations, a closed error set, and strict LF-framed JSONL. There is
no third operation, and adding one is a protocol change rather than a detail:

    read_file, edit_file

and specifically NO ``verify``, ``stat``, ``list``, ``search``, ``execute``,
``shell``, ``create``, ``delete``, ``rename``, or cancellation verb.

**A response may never contain** an absolute path, a resolved path, a parent
directory, a volume or drive, the canonical root, an exclusion pattern, the
manifest, Win32 error text, an ``errno``, a stack trace, an environment value,
the token, or capability internals. ``path_candidate`` is **never echoed back**.

The error set is closed and deliberately coarse. ``refused`` merges
outside-root, not-in-manifest, forbidden, protected-write, wrong kind, reparse,
bad lexical form AND nonexistent, so the runtime cannot use error codes to probe
the repository. AIDO's own record keeps the full internal reason; the model may
not have it.

Note the evidence limit this protocol does NOT overcome: a broker that receives
only ``read_file`` and ``edit_file`` requests is evidence about **what was
requested through the broker**, never proof of what the active tool registry
contained (AR2D section 2.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1

OP_READ_FILE = "read_file"
OP_EDIT_FILE = "edit_file"
SUPPORTED_OPERATIONS: frozenset[str] = frozenset({OP_READ_FILE, OP_EDIT_FILE})

MAX_REQUEST_FRAME_BYTES = 256 * 1024
MAX_RESPONSE_FRAME_BYTES = 512 * 1024
MAX_REQUEST_ID_LENGTH = 64
MAX_EDIT_TEXT_BYTES = 128 * 1024

# -- the closed error set ------------------------------------------------------

ERR_REFUSED = "refused"
ERR_TOO_LARGE = "too_large"
ERR_NOT_TEXT = "not_text"
ERR_STALE_BASE = "stale_base"
ERR_NO_UNIQUE_MATCH = "no_unique_match"
ERR_BUDGET_EXHAUSTED = "budget_exhausted"
ERR_PROTOCOL_ERROR = "protocol_error"
ERR_UNAUTHORIZED = "unauthorized"
ERR_INTERNAL_ERROR = "internal_error"

CLOSED_ERROR_SET: frozenset[str] = frozenset(
    {
        ERR_REFUSED,
        ERR_TOO_LARGE,
        ERR_NOT_TEXT,
        ERR_STALE_BASE,
        ERR_NO_UNIQUE_MATCH,
        ERR_BUDGET_EXHAUSTED,
        ERR_PROTOCOL_ERROR,
        ERR_UNAUTHORIZED,
        ERR_INTERNAL_ERROR,
    }
)

# Errors that end the connection and the capability for the rest of the run.
TERMINAL_ERROR_CODES: frozenset[str] = frozenset(
    {ERR_PROTOCOL_ERROR, ERR_UNAUTHORIZED, ERR_INTERNAL_ERROR}
)

_READ_FIELDS: frozenset[str] = frozenset({"v", "id", "cap", "tok", "op", "path_candidate"})
_EDIT_FIELDS: frozenset[str] = frozenset(
    {"v", "id", "cap", "tok", "op", "path_candidate", "base_sha256", "old_text", "new_text"}
)

_HEX = frozenset("0123456789abcdefABCDEF")


class WireProtocolError(Exception):
    """A frame was malformed. ALWAYS terminal; never repaired, never guessed at."""


@dataclass(frozen=True)
class BrokerRequest:
    """One validated request. The candidate stays an opaque untrusted string."""

    request_id: str
    capability_id: str
    token: str
    operation: str
    path_candidate: str
    base_sha256: str | None = None
    old_text: str | None = None
    new_text: str | None = None


def parse_request_frame(raw: bytes) -> BrokerRequest:
    """Validate one LF-stripped request frame, or raise :class:`WireProtocolError`.

    Extra fields are **rejected, not ignored**; ``v`` must be exactly ``1``; the
    ``id`` is opaque, at most 64 characters, and its uniqueness is enforced by the
    caller against AIDO-owned run state.
    """
    if len(raw) > MAX_REQUEST_FRAME_BYTES:
        raise WireProtocolError("protocol error: the request frame exceeds the cap")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WireProtocolError("protocol error: the request frame is not valid UTF-8") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WireProtocolError("protocol error: the request frame is not strict JSON") from exc
    if not isinstance(value, dict):
        raise WireProtocolError("protocol error: the request frame is not a JSON object")

    # ``type(...) is int`` rather than ``isinstance``: in Python ``True == 1`` and
    # ``isinstance(True, int)`` is true, so a boolean version would otherwise slip
    # through. The version is matched exactly, never coerced.
    if type(value.get("v")) is not int or value["v"] != PROTOCOL_VERSION:
        raise WireProtocolError("protocol error: unsupported protocol version")

    operation = value.get("op")
    if operation not in SUPPORTED_OPERATIONS:
        raise WireProtocolError("protocol error: unsupported operation")

    allowed = _READ_FIELDS if operation == OP_READ_FILE else _EDIT_FIELDS
    extra = set(value) - allowed
    if extra:
        raise WireProtocolError("protocol error: the request carries unknown fields")
    missing = allowed - set(value)
    if missing:
        raise WireProtocolError("protocol error: the request is missing required fields")

    request_id = value["id"]
    if (
        not isinstance(request_id, str)
        or not request_id
        or len(request_id) > MAX_REQUEST_ID_LENGTH
    ):
        raise WireProtocolError("protocol error: the request id is absent or over-long")

    for name in ("cap", "tok", "path_candidate"):
        if not isinstance(value[name], str) or not value[name]:
            raise WireProtocolError(f"protocol error: {name} is absent or not a string")

    if operation == OP_READ_FILE:
        return BrokerRequest(
            request_id=request_id,
            capability_id=value["cap"],
            token=value["tok"],
            operation=operation,
            path_candidate=value["path_candidate"],
        )

    base = value["base_sha256"]
    if (
        not isinstance(base, str)
        or len(base) != 64
        or any(character not in _HEX for character in base)
    ):
        raise WireProtocolError("protocol error: base_sha256 is not a 64-character hex digest")
    old_text = value["old_text"]
    new_text = value["new_text"]
    if not isinstance(old_text, str) or not isinstance(new_text, str):
        raise WireProtocolError("protocol error: old_text and new_text must be strings")
    if len(old_text.encode("utf-8")) > MAX_EDIT_TEXT_BYTES or len(
        new_text.encode("utf-8")
    ) > MAX_EDIT_TEXT_BYTES:
        raise WireProtocolError("protocol error: an edit text field exceeds the cap")

    return BrokerRequest(
        request_id=request_id,
        capability_id=value["cap"],
        token=value["tok"],
        operation=operation,
        path_candidate=value["path_candidate"],
        base_sha256=base,
        old_text=old_text,
        new_text=new_text,
    )


def success_frame(request_id: str, result: dict[str, Any]) -> bytes:
    return _encode({"v": PROTOCOL_VERSION, "id": request_id, "ok": True, "result": result})


def error_frame(request_id: str, code: str, detail: str) -> bytes:
    if code not in CLOSED_ERROR_SET:
        raise WireProtocolError(
            "protocol error: an error code outside the closed set was constructed"
        )
    return _encode(
        {
            "v": PROTOCOL_VERSION,
            "id": request_id,
            "ok": False,
            "error": {"code": code, "detail": detail},
        }
    )


def _encode(payload: dict[str, Any]) -> bytes:
    frame = json.dumps(payload, ensure_ascii=True, sort_keys=False).encode("utf-8") + b"\n"
    if len(frame) > MAX_RESPONSE_FRAME_BYTES:
        raise WireProtocolError("protocol error: the response frame exceeds the cap")
    return frame


def response_is_host_safe(frame: bytes, *, forbidden_values: tuple[str, ...]) -> bool:
    """Whether a response frame is free of every host detail it must never carry.

    A self-check, used by the broker before a frame is written and asserted by
    the offline suite. It is a **backstop**, never a proof.
    """
    text = frame.decode("utf-8", "replace")
    lowered = text.lower()
    for value in forbidden_values:
        if value and value.lower() in lowered:
            return False
    for marker in ("c:\\", "c:/", "\\\\", "traceback", "winerror", "errno"):
        if marker in lowered:
            return False
    return True
