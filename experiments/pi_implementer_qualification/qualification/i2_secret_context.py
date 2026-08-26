"""Run-scoped secret/config context for the B300 qualification route (I2A Sec. 8/11).

This object is the one AIDO's own controller would hold, in memory, for the
duration of one qualification task run: the resolved connection values plus
enough identity to build both the Pi child environment (I2-1) and the
generated config (I2-2), and to populate the existing, unmodified
``qualification.safety.ArtifactSafetyContext`` for scrubbing every
retainable artifact (I2A Sec. 11/17).

**This object is RUNTIME-ONLY and is NEVER evidence.** There is deliberately
no ``to_dict``, no ``asdict``-for-evidence helper, and no ``model_dump``
anywhere on this class. Its only sanctioned downstream use is
:meth:`QualificationRouteSecretContext.to_safety_context`, which hands its
values to the ALREADY-accepted I1 scrub context -- a context designed to be
searched against and refused, never to be persisted directly.

Every secret- or endpoint-bearing field is declared ``repr=False`` *and* the
class defines its own bounded ``__repr__`` -- two independent reasons the
default dataclass repr can never print a credential value or a full base
URL, so removing either protection alone still leaves the other standing.

**5F3B-I2-FU2: valid by construction.** Independent review demonstrated
:class:`QualificationRouteSecretContext` could be instantiated directly
(bypassing :func:`build_secret_context` entirely) with a malformed
``base_url``, a mismatched ``endpoint_host``, or a forged
``provider_id``/``credential_env_var_name``/``model_id``. ``__post_init__``
now enforces every one of those rules itself, so the dataclass -- not just
its one sanctioned factory -- is a trusted value object. ``provider_id``
and ``credential_env_var_name`` were removed from
:func:`build_secret_context`'s own parameter list for the same reason FU1
narrowed the config generator: fixed route identity has no business being
a caller-supplied value anywhere in this package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from .i2_identity import CREDENTIAL_ENV_VAR_NAME, PROVIDER_ID
from .records import CANDIDATE_MODEL_IDS
from .safety import ArtifactSafetyContext


class SecretContextError(Exception):
    """The run-scoped secret context could not be constructed safely."""


class InvalidBaseUrlError(Exception):
    """The B300 route base URL failed the qualification URL validator.

    **Never echoes the invalid value.** The message may name only the
    variable name (``AIDO_LITELLM_BASE_URL``) or a fixed, generic phrase
    (``"invalid B300 route URL"``) plus which structural rule was violated
    -- never the URL text itself, which may itself carry an embedded
    credential or a malformed value an attacker chose.
    """


def validate_b300_base_url(base_url: str) -> str:
    """Structurally validate the B300 route base URL. Returns it unchanged if valid.

    **5F3B-I2-FU1.** Independent review found ``extract_endpoint_host``
    silently accepted a malformed URL and returned the placeholder string
    ``"<unparsed>"``, defeating ``ArtifactSafetyContext``'s endpoint-host
    backstop (a needle that is never populated can never be matched). This
    is the one qualification-owned validator, reused by both the connection
    contract (I2-4) and secret-context construction -- there is exactly one
    validation rule set, never a second drifting copy.

    Required: scheme is exactly ``http`` or ``https``; a hostname is
    present; no embedded username or password; no query string; no
    fragment. A bare path such as ``/v1`` is fine.
    """
    if not base_url or not base_url.strip():
        raise InvalidBaseUrlError(
            "invalid B300 route URL: AIDO_LITELLM_BASE_URL is unset or blank"
        )
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise InvalidBaseUrlError(
            "invalid B300 route URL: scheme must be exactly 'http' or 'https'"
        )
    if not parsed.hostname:
        raise InvalidBaseUrlError("invalid B300 route URL: hostname is missing")
    if parsed.username or parsed.password:
        raise InvalidBaseUrlError(
            "invalid B300 route URL: an embedded username/password is not allowed"
        )
    if parsed.query:
        raise InvalidBaseUrlError("invalid B300 route URL: a query string is not allowed")
    if parsed.fragment:
        raise InvalidBaseUrlError("invalid B300 route URL: a fragment is not allowed")
    return base_url


def extract_endpoint_host(base_url: str) -> str:
    """The host component only -- never the scheme, port, path, query, or full URL.

    **5F3B-I2-FU1.** Raises :class:`InvalidBaseUrlError` for a malformed
    URL rather than returning a placeholder. For every URL this function
    returns normally, the result is a real, non-empty hostname --
    ``"<unparsed>"`` can no longer be produced.
    """
    validate_b300_base_url(base_url)
    hostname = urlparse(base_url).hostname
    if not hostname:  # pragma: no cover - validate_b300_base_url already rejects this
        raise InvalidBaseUrlError("invalid B300 route URL: hostname is missing")
    return hostname


@dataclass(frozen=True)
class QualificationRouteSecretContext:
    """The run's resolved B300 connection values, held only as long as needed.

    Normally constructed via :func:`build_secret_context`, but
    ``__post_init__`` (5F3B-I2-FU2) makes DIRECT construction with invalid
    or forged values impossible too -- this is a trusted value object, not
    merely a factory-guarded one.
    """

    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    endpoint_host: str = field(repr=False)
    credential_env_var_name: str
    provider_id: str
    model_id: str

    def __post_init__(self) -> None:
        validate_b300_base_url(self.base_url)
        if not self.api_key or not self.api_key.strip():
            raise SecretContextError("secret context error: api_key must be non-blank")
        expected_host = extract_endpoint_host(self.base_url)
        if self.endpoint_host != expected_host:
            raise SecretContextError(
                "secret context error: endpoint_host does not match the base_url's own host"
            )
        if self.credential_env_var_name != CREDENTIAL_ENV_VAR_NAME:
            raise SecretContextError(
                "secret context error: credential_env_var_name does not match the "
                "fixed qualification credential carrier"
            )
        if self.provider_id != PROVIDER_ID:
            raise SecretContextError(
                "secret context error: provider_id does not match the fixed "
                "qualification provider id"
            )
        if self.model_id not in CANDIDATE_MODEL_IDS.values():
            raise SecretContextError(
                "secret context error: model_id is not one of the frozen "
                "first-round candidate model ids"
            )

    def __repr__(self) -> str:  # noqa: D105 - see module docstring
        return (
            f"{type(self).__name__}("
            f"credential_env_var_name={self.credential_env_var_name!r}, "
            f"provider_id={self.provider_id!r}, model_id={self.model_id!r})"
        )

    def to_safety_context(
        self,
        *,
        broker_token: str | None,
        pipe_name: str | None,
        capability_id: str | None,
        workspace_absolute_path: str | None,
    ) -> ArtifactSafetyContext:
        """Populate the existing, unmodified I1 ``ArtifactSafetyContext``.

        **5F3B-I2-FU3: no silent defaults.** Every run-sensitive field is a
        REQUIRED keyword argument -- there is no ``= None`` default a
        caller could omit and unknowingly leave unset. A genuinely
        offline/no-broker caller states ``None`` explicitly for each field
        it has nothing to declare, exactly as I1's own
        ``ArtifactSafetyContext.none_declared()`` requires an explicit
        statement rather than inheriting omission. The broker/workspace
        values themselves are per-run facts this offline phase does not
        itself generate (no live broker exists yet); callers supply them
        explicitly -- synthetic values in the offline suite, the real
        per-run values in a future live adapter.
        """
        return ArtifactSafetyContext(
            endpoint_host=self.endpoint_host,
            api_key=self.api_key,
            bearer_token=None,
            broker_token=broker_token,
            pipe_name=pipe_name,
            capability_id=capability_id,
            workspace_absolute_path=workspace_absolute_path,
        )


def build_secret_context(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
) -> QualificationRouteSecretContext:
    """Construct the run-scoped secret context.

    **5F3B-I2-FU2: narrowed signature.** There is no ``provider_id`` or
    ``credential_env_var_name`` parameter -- both are the fixed constants
    :data:`~qualification.i2_environment.PROVIDER_ID` and
    :data:`~qualification.i2_environment.CREDENTIAL_ENV_VAR_NAME`, so a
    caller cannot request an arbitrary provider or credential carrier
    through this factory at all. All validation (including ``base_url``)
    is enforced by :meth:`QualificationRouteSecretContext.__post_init__`
    itself, so this factory and direct construction obey identical rules.
    """
    return QualificationRouteSecretContext(
        base_url=base_url,
        api_key=api_key,
        endpoint_host=extract_endpoint_host(base_url),
        credential_env_var_name=CREDENTIAL_ENV_VAR_NAME,
        provider_id=PROVIDER_ID,
        model_id=model_id,
    )
