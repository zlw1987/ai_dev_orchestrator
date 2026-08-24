"""Strict Pi-specific JSONL RPC framing, ingestion and reasoning drop.

This is deliberately Pi-specific. It is NOT a generic ``AgentRuntime``
abstraction, and it must not become one (AR0 section 17.3).

Framing rules, taken from Pi's shipped ``dist/modes/rpc/jsonl.js``:

- LF (``\\n``) is the ONLY record delimiter.
- At most one trailing ``\\r`` is stripped.
- Records are UTF-8 and are parsed with strict ``json.loads``.
- A non-JSON stdout record is a TERMINAL protocol violation, never skipped.
- Node ``readline`` semantics (splitting on U+2028/U+2029) are wrong here, so
  nothing in this module may use a generic line reader.

Reasoning rule (AR0 section 13.3, 5F2E-V2 precedent): reasoning-bearing content
is dropped AT INGESTION, before any record is stored, counted, hashed, or
written. AIDO builds no chain-of-thought observability.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, IO

# ``assistantMessageEvent.type`` values that carry model reasoning.
REASONING_DELTA_TYPES: frozenset[str] = frozenset(
    {"thinking_start", "thinking_delta", "thinking_end"}
)

# Object keys that carry reasoning, anywhere at any depth.
REASONING_KEYS: frozenset[str] = frozenset(
    {
        "thinking",
        "thinkingBlocks",
        "thinking_blocks",
        "reasoning",
        "reasoningContent",
        "reasoning_content",
        "reasoningDetails",
        "reasoning_details",
        "redactedThinking",
        "redacted_thinking",
        "thinkingSignature",
        "thinking_signature",
    }
)

# Content-block ``type`` values that carry reasoning.
REASONING_BLOCK_TYPES: frozenset[str] = frozenset(
    {"thinking", "reasoning", "redacted_thinking", "redactedThinking"}
)

_REASONING_DROPPED_MARKER = "reasoning_dropped_at_ingestion"


def _read_available(stream: IO[bytes], size: int) -> bytes:
    """Read what is available now, without waiting for a full buffer.

    ``BufferedReader.read(n)`` blocks until ``n`` bytes arrive or the stream
    ends, which would stall a live protocol stream until the process exits.
    ``read1`` returns as soon as any data is available, which is what a JSONL
    supervisor needs.
    """
    reader = getattr(stream, "read1", None)
    if reader is not None:
        return reader(size)
    return stream.read(size)


class ProtocolViolation(Exception):
    """A stdout record was not a strict, single-line JSON object. Terminal."""


def split_records(buffer: bytes) -> tuple[list[bytes], bytes]:
    """Split a byte buffer on ``b"\\n"`` only, returning records and the remainder."""
    if b"\n" not in buffer:
        return [], buffer
    parts = buffer.split(b"\n")
    return parts[:-1], parts[-1]


def decode_record(raw: bytes) -> dict[str, Any]:
    """Decode one framed record, or raise :class:`ProtocolViolation`."""
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    if not raw.strip():
        raise ProtocolViolation("protocol violation: an empty stdout record was framed")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolViolation(
            "protocol violation: a stdout record was not valid UTF-8"
        ) from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolViolation(
            "protocol violation: a stdout record was not strict JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ProtocolViolation(
            "protocol violation: a stdout record was JSON but not an object"
        )
    return value


@dataclass
class ReasoningDropStats:
    """How much reasoning was discarded. Counts only -- never content."""

    reasoning_delta_records_dropped: int = 0
    reasoning_keys_dropped: int = 0
    reasoning_blocks_dropped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "reasoning_delta_records_dropped": self.reasoning_delta_records_dropped,
            "reasoning_keys_dropped": self.reasoning_keys_dropped,
            "reasoning_blocks_dropped": self.reasoning_blocks_dropped,
        }


def drop_reasoning(value: Any, stats: ReasoningDropStats) -> Any:
    """Recursively remove every reasoning-bearing field and content block.

    Removal is structural: the key or block disappears entirely. Nothing is
    summarized, hashed, counted by length, or replaced by a redacted copy of
    itself -- only the fact that *something* was dropped is counted.
    """
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key in REASONING_KEYS:
                stats.reasoning_keys_dropped += 1
                continue
            result[key] = drop_reasoning(item, stats)
        return result
    if isinstance(value, list):
        kept: list[Any] = []
        for item in value:
            if isinstance(item, dict) and item.get("type") in REASONING_BLOCK_TYPES:
                stats.reasoning_blocks_dropped += 1
                continue
            kept.append(drop_reasoning(item, stats))
        return kept
    return value


def ingest_record(record: dict[str, Any], stats: ReasoningDropStats) -> dict[str, Any]:
    """Sanitize one decoded record at ingestion.

    A ``message_update`` whose ``assistantMessageEvent`` is a thinking delta has
    that event removed outright; the record is retained only as evidence that a
    reasoning delta arrived and was discarded, plus any non-reasoning usage
    metadata Pi attached to it.
    """
    delta = record.get("assistantMessageEvent")
    if isinstance(delta, dict) and delta.get("type") in REASONING_DELTA_TYPES:
        stats.reasoning_delta_records_dropped += 1
        sanitized = {
            key: value
            for key, value in record.items()
            if key != "assistantMessageEvent"
        }
        sanitized["assistantMessageEvent"] = _REASONING_DROPPED_MARKER
        return drop_reasoning(sanitized, stats)
    return drop_reasoning(record, stats)


def contains_reasoning(value: Any) -> bool:
    """Whether any reasoning-bearing key or block survives anywhere in ``value``."""
    if isinstance(value, dict):
        if any(key in REASONING_KEYS for key in value):
            return True
        if value.get("type") in REASONING_BLOCK_TYPES:
            return True
        return any(contains_reasoning(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_reasoning(item) for item in value)
    return False


@dataclass
class BoundedStreamState:
    """Observable state of one bounded reader. Data only."""

    bytes_seen: int = 0
    bytes_retained: int = 0
    cap_exceeded: bool = False
    eof: bool = False
    error: str | None = None
    chunks: list[bytes] = field(default_factory=list)


class BoundedStreamReader:
    """Read one binary stream on a daemon thread with the cap enforced during capture.

    The cap is enforced **at the moment it is passed**, not by waiting for a
    buffer to fill -- the accepted ``_BoundedOutputReader`` lesson. Reading
    continues past the cap so the writer is never blocked by a full pipe, but
    the over-limit bytes are discarded rather than retained.
    """

    def __init__(self, stream: IO[bytes], *, max_bytes: int, name: str) -> None:
        self._stream = stream
        self._max_bytes = max_bytes
        self.state = BoundedStreamState()
        self._lock = threading.Lock()
        self._finished = threading.Event()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)

    def start(self) -> None:
        self._thread.start()

    @property
    def finished(self) -> threading.Event:
        return self._finished

    def _run(self) -> None:
        try:
            while True:
                chunk = _read_available(self._stream, 65536)
                if not chunk:
                    with self._lock:
                        self.state.eof = True
                    break
                with self._lock:
                    self.state.bytes_seen += len(chunk)
                    remaining = self._max_bytes - self.state.bytes_retained
                    if remaining <= 0:
                        self.state.cap_exceeded = True
                        continue
                    if len(chunk) > remaining:
                        self.state.cap_exceeded = True
                        chunk = chunk[:remaining]
                    self.state.chunks.append(chunk)
                    self.state.bytes_retained += len(chunk)
        except Exception as exc:  # noqa: BLE001 - the reader must never raise upward
            with self._lock:
                self.state.error = f"{type(exc).__name__}: {exc}"
        finally:
            self._finished.set()

    def snapshot(self) -> tuple[bytes, BoundedStreamState]:
        with self._lock:
            data = b"".join(self.state.chunks)
            state = BoundedStreamState(
                bytes_seen=self.state.bytes_seen,
                bytes_retained=self.state.bytes_retained,
                cap_exceeded=self.state.cap_exceeded,
                eof=self.state.eof,
                error=self.state.error,
            )
        return data, state


class RecordStreamReader:
    """Bounded stdout reader that frames, decodes and sanitizes records live.

    stdout is the PROTOCOL channel and is never merged with stderr. Records are
    published to a list under a lock; reasoning is dropped before publication,
    so no reasoning-bearing value is ever stored by this process.
    """

    def __init__(
        self,
        stream: IO[bytes],
        *,
        max_bytes: int,
        max_records: int,
        stats: ReasoningDropStats,
    ) -> None:
        self._stream = stream
        self._max_bytes = max_bytes
        self._max_records = max_records
        self._stats = stats
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._records: list[dict[str, Any]] = []
        self._finished = threading.Event()
        self.bytes_seen = 0
        self.byte_cap_exceeded = False
        self.record_cap_exceeded = False
        self.protocol_violation: str | None = None
        self.eof = False
        self.read_error: str | None = None
        self._thread = threading.Thread(
            target=self._run, name="ar2-pi-stdout", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    @property
    def finished(self) -> threading.Event:
        return self._finished

    def wait_for_more(self, known_count: int, timeout: float) -> None:
        """Block until more than ``known_count`` records exist, or ``timeout``.

        The wait is always bounded by the caller's own monotonic deadline; this
        never waits indefinitely and never joins the reader thread.
        """
        if timeout <= 0:
            return
        with self._condition:
            self._condition.wait_for(
                lambda: len(self._records) > known_count or self._finished.is_set(),
                timeout=timeout,
            )

    def records_since(self, index: int) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._records[index:])

    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    def all_records(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._records)

    def _publish(self, record: dict[str, Any]) -> None:
        with self._condition:
            self._records.append(record)
            self._condition.notify_all()

    def _run(self) -> None:
        buffer = b""
        try:
            while True:
                chunk = _read_available(self._stream, 65536)
                if not chunk:
                    self.eof = True
                    break
                self.bytes_seen += len(chunk)
                if self.bytes_seen > self._max_bytes:
                    self.byte_cap_exceeded = True
                    break
                buffer += chunk
                framed, buffer = split_records(buffer)
                for raw in framed:
                    if not raw.strip():
                        # Pi writes exactly one LF per record; a blank line would
                        # be a framing anomaly, so it is refused rather than
                        # skipped.
                        self.protocol_violation = (
                            "protocol violation: a blank stdout record was framed"
                        )
                        return
                    try:
                        decoded = decode_record(raw)
                    except ProtocolViolation as exc:
                        self.protocol_violation = str(exc)
                        return
                    self._publish(ingest_record(decoded, self._stats))
                    if self.record_count() >= self._max_records:
                        self.record_cap_exceeded = True
                        return
        except Exception as exc:  # noqa: BLE001 - never raise out of the reader
            self.read_error = f"{type(exc).__name__}: {exc}"
        finally:
            self._finished.set()
            with self._condition:
                self._condition.notify_all()
