"""I2-4 -- credential read ordering and the connection contract (I2A Sec. 8/16.A).

**OFFLINE ONLY. NO REAL ENVIRONMENT READ.** Every function here takes the
environment reader as an INJECTED callback. There is no function anywhere in
this module with a default that silently reads ``os.environ`` -- a future
authorized live controller supplies the real reader explicitly, after this
phase's own offline gates.

Ordering (I2A Sec. 8/16, restated as the wiring shape this module enforces):

    non-secret gates
        |
        v  ONLY IF THEY ALL PASS
    read/resolve B300 connection values (AIDO_LITELLM_BASE_URL / _API_KEY)
        |
        v
    construct child env / config (I2-1 / I2-2)
        |
        v
    future zero-prompt route gate (I2-3, still offline in THIS phase)

A missing or blank connection value is a pre-prompt infrastructure refusal
condition (``semantic_prompts_sent = 0``), never a silent placeholder.
Failure text names the ENV VARIABLE NAME only -- never a value, a host, or
any header text.

**5F3B-I2-FU1 hardening**, closing two gaps independent review found:

1. ``resolve_connection_after_preflight`` now catches a connection-value
   failure (missing/blank ``AIDO_LITELLM_BASE_URL``/``_API_KEY``, or a
   malformed base URL) raised while resolving the connection, and
   translates it into the SAME bounded, zero-prompt
   :class:`InfrastructureRefusal` shape every other pre-prompt gate uses --
   it no longer escapes as an uncategorized low-level error.
2. ``PreflightGateResult.detail`` (arbitrary caller-authored prose) is
   REPLACED by ``failure_code``, one of a small declared set
   (:data:`PREFLIGHT_FAILURE_CODES`). A caller cannot embed a credential,
   endpoint, or path in a gate failure, because nothing but one of these
   fixed codes is ever accepted.

**5F3B-I2-FU2 hardening**, closing two more gaps independent review found:

3. ``ConnectionValues`` is now valid by construction: ``__post_init__``
   enforces ``validate_b300_base_url(base_url)`` and a non-blank
   ``api_key``, so ``ConnectionValues(base_url="not-a-url", api_key="")``
   is impossible to construct at all -- not merely something
   :func:`resolve_connection_after_preflight` happens to reject afterward.
4. ``PreflightGateResult`` can no longer express an impossible state:
   ``passed=True`` with a non-``None`` ``failure_code``, or ``passed=False``
   with ``failure_code=None``, both now raise at construction.
   :func:`resolve_connection_after_preflight` therefore never needs to
   invent a fallback code -- the ``or "CHECK_FAILED"`` substitution FU1 left
   in place is removed; a failing gate's ``failure_code`` is guaranteed
   present by construction.

**5F3B-I2-FU3.** Independent review reproduced ``PreflightGateResult(name=
"x", passed="false")`` being accepted and treated as truthy (Python's own
truthiness, not this module's coercion, but the effect is identical: a
non-bool "false"-shaped value silently authorizing the ``passed=True``
branch). This is a credential-read authorization gate -- no bool coercion
is acceptable. ``__post_init__`` now requires ``type(passed) is bool``
exactly, checked BEFORE the ``if self.passed:`` branch, so ``"false"``,
``1``, and ``0`` are all rejected outright rather than silently coerced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Sequence

from .i2_secret_context import InvalidBaseUrlError, validate_b300_base_url

#: The two required B300 connection variable NAMES (I2A Sec. 8/16.A). Names
#: only; no value is ever read, stored, or recorded by this constant.
CONNECTION_ENV_VAR_NAMES: tuple[str, str] = (
    "AIDO_LITELLM_BASE_URL",
    "AIDO_LITELLM_API_KEY",
)

#: Bounded, declared preflight/connection failure codes (5F3B-I2-FU1).
#: NEVER free-form prose -- a caller may only select one of these.
PREFLIGHT_FAILURE_CODES: frozenset[str] = frozenset(
    {
        "CHECK_FAILED",
        "NOT_INSTALLED",
        "SCHEMA_INVALID",
        "FORBIDDEN_VALUE_DETECTED",
        "NOT_READY",
        "VERIFICATION_FAILED",
        "CONNECTION_VALUE_MISSING_OR_BLANK",
        "CONNECTION_VALUE_INVALID",
    }
)

#: A short, lowercase_with_underscores identifier -- never diagnostic prose.
_GATE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _validate_gate_name(gate_name: str) -> None:
    if not _GATE_NAME_PATTERN.fullmatch(gate_name):
        raise ValueError(
            "gate_name must be a short lowercase_with_underscores identifier "
            "(letters, digits, underscores; max 64 chars); arbitrary "
            "diagnostic prose is refused"
        )


def _validate_failure_code(failure_code: str) -> None:
    if failure_code not in PREFLIGHT_FAILURE_CODES:
        raise ValueError(
            f"unknown preflight failure_code {failure_code!r}; declared: "
            f"{sorted(PREFLIGHT_FAILURE_CODES)}"
        )


class ConnectionValueError(Exception):
    """A required B300 connection value is missing, blank, or malformed.

    The message names the environment VARIABLE NAME, or a fixed generic
    phrase, only. It must never contain a base URL, a host, a key, or any
    header text. Internal to this module's connection-resolution step --
    :func:`resolve_connection_after_preflight` catches it and translates it
    into the bounded :class:`InfrastructureRefusal` shape.
    """


class InfrastructureRefusal(Exception):
    """A non-secret preflight gate (or connection resolution) failed pre-prompt.

    Pre-prompt (I2A Sec. 16.A): ``semantic_prompts_sent`` for the task this
    refusal belongs to remains ``0``. Both ``gate_name`` and
    ``failure_code`` are bounded/validated -- there is no free-text field
    anywhere on this exception, so it structurally cannot echo a
    credential, endpoint, or path.
    """

    def __init__(self, gate_name: str, failure_code: str) -> None:
        _validate_gate_name(gate_name)
        _validate_failure_code(failure_code)
        super().__init__(f"pre-prompt infrastructure gate failed: {gate_name}: {failure_code}")
        self.gate_name = gate_name
        self.failure_code = failure_code


@dataclass(frozen=True)
class ConnectionValues:
    """The resolved B300 connection values. Held only as long as the run needs them.

    **5F3B-I2-FU1.** Both fields are ``field(repr=False)`` *and* this class
    defines its own bounded ``__repr__`` -- two independent reasons the
    default dataclass repr can never print the base URL or the API key.

    **5F3B-I2-FU2: valid by construction.** ``__post_init__`` enforces
    ``validate_b300_base_url(base_url)`` and a non-blank ``api_key`` --
    direct construction with an invalid value is impossible, so an injected
    ``read_connection`` callback cannot bypass policy by fabricating one.
    """

    base_url: str = field(repr=False)
    api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        validate_b300_base_url(self.base_url)
        if not self.api_key or not self.api_key.strip():
            raise ConnectionValueError("api_key must be non-blank")

    def __repr__(self) -> str:  # noqa: D105 - see class docstring
        return f"{type(self).__name__}(base_url=<redacted>, api_key=<redacted>)"


@dataclass(frozen=True)
class PreflightGateResult:
    """One non-secret gate's outcome.

    **5F3B-I2-FU1.** The former free-text ``detail`` field is REMOVED and
    replaced by ``failure_code``, one of :data:`PREFLIGHT_FAILURE_CODES` --
    validated at construction, so an impossible/arbitrary code can never be
    built in the first place.

    **5F3B-I2-FU2: state coherence.** ``passed=True`` MUST carry
    ``failure_code=None``; ``passed=False`` MUST carry a declared
    ``failure_code``. Neither impossible combination can be constructed.
    """

    name: str
    passed: bool
    failure_code: str | None = None

    def __post_init__(self) -> None:
        _validate_gate_name(self.name)
        if type(self.passed) is not bool:
            raise ValueError(
                "PreflightGateResult: passed must be exactly a bool (no "
                f"truthy/falsy coercion); got {type(self.passed).__name__}"
            )
        if self.passed:
            if self.failure_code is not None:
                raise ValueError(
                    "PreflightGateResult: passed=True must not carry a failure_code"
                )
        else:
            if self.failure_code is None:
                raise ValueError(
                    "PreflightGateResult: passed=False requires a declared failure_code"
                )
            _validate_failure_code(self.failure_code)


def read_connection_values(reader: Callable[[str], str | None]) -> ConnectionValues:
    """Resolve the B300 connection values via an INJECTED reader callback.

    ``reader`` is a required, positional argument -- there is no default
    that reads a real environment. A missing/blank value raises
    :class:`ConnectionValueError` naming only the variable name. A
    non-blank but structurally malformed base URL raises
    :class:`~qualification.i2_secret_context.InvalidBaseUrlError` (I2A/FU1
    Sec. 7) -- neither ever echoes the offending value.
    """
    base_url = reader("AIDO_LITELLM_BASE_URL")
    if not base_url or not base_url.strip():
        raise ConnectionValueError(
            "AIDO_LITELLM_BASE_URL is unset or blank in the connection reader"
        )
    validate_b300_base_url(base_url)

    api_key = reader("AIDO_LITELLM_API_KEY")
    if not api_key or not api_key.strip():
        raise ConnectionValueError(
            "AIDO_LITELLM_API_KEY is unset or blank in the connection reader"
        )
    return ConnectionValues(base_url=base_url, api_key=api_key)


def resolve_connection_after_preflight(
    *,
    non_secret_gates: Sequence[Callable[[], PreflightGateResult]],
    read_connection: Callable[[], ConnectionValues],
) -> ConnectionValues:
    """I2A Sec. 8/16's ordering, made mechanically testable.

    Every gate in ``non_secret_gates`` is evaluated, IN ORDER; the first
    failing gate raises :class:`InfrastructureRefusal` immediately, and
    ``read_connection`` is never called. Only when every gate reports
    ``passed=True`` is ``read_connection`` invoked -- exactly once.

    **5F3B-I2-FU1: connection-value failures are now a TRUE pre-prompt
    infrastructure refusal.** A missing/blank/malformed connection value
    (``ConnectionValueError`` or ``InvalidBaseUrlError`` raised by
    ``read_connection``) is caught here and re-raised as the SAME bounded
    :class:`InfrastructureRefusal` shape every other pre-prompt gate uses --
    it no longer escapes this function as an uncategorized low-level error.

    The offline suite proves both ordering properties with a call-counting
    double wrapped around ``read_connection``; this function never reads a
    real environment itself.

    **5F3B-I2-FU2.** ``result.failure_code`` is never substituted with a
    silently-invented fallback: ``PreflightGateResult.__post_init__``
    already guarantees a failing gate carries a declared code, so
    ``resolve_connection_after_preflight`` only ever consumes a fully
    coherent result.
    """
    for gate in non_secret_gates:
        result = gate()
        if not result.passed:
            raise InfrastructureRefusal(result.name, result.failure_code)

    try:
        return read_connection()
    except ConnectionValueError as exc:
        raise InfrastructureRefusal(
            "connection_values", "CONNECTION_VALUE_MISSING_OR_BLANK"
        ) from exc
    except InvalidBaseUrlError as exc:
        raise InfrastructureRefusal("connection_values", "CONNECTION_VALUE_INVALID") from exc
