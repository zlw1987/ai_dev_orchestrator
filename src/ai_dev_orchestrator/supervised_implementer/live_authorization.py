"""The per-run live authorization artifact (ALPHA-P1B, DEC-SUP-LIVE).

``supervised-implementer-authorization.v1`` has two sections:

- ``bound`` is written by ``l2-supervised-implementer-prepare`` and never edited
  by the human. It binds, by value or by SHA-256, everything one live run may
  do: the approved plan, the project config, the one target, the exact source
  bytes, the Git HEAD the source was read at, the exact request payload, the
  model, provider and runtime limits, the one evidence directory its run
  evidence goes to, and (ALPHA-P1B-FU1) the one authorization ledger that
  issued it plus the digest of its issuance nonce, which only that ledger
  holds until consumption destroys it. ``binding_sha256`` is a digest over all
  of it.
- ``consent`` is written by the human. It echoes ``binding_sha256``, types the
  endpoint scheme, host and port the human expects, and carries an exact
  consent phrase (plus an exact plaintext acknowledgement iff the scheme is
  ``http``). A draft carries an empty, non-parsing consent.

**Exact types (refinement R-3).** Pydantic strict mode does not make
``Literal[1]`` or ``Literal[False]`` type-exact: JSON ``true`` validates as
``Literal[1]`` and JSON ``0`` as ``Literal[False]``. Every integer and boolean
here is therefore ``StrictInt`` / ``StrictBool`` with an exact-value check.

**What it does not defend against.** The artifact is unsigned. It guards
against stale, replayed, copied or mismatched consent by accident or
misconfiguration. It does not stop an operator who deliberately recomputes
``binding_sha256`` after editing ``bound``, and no library function is a
security boundary against other Python code in the same process (A-19). The
human is the trust root, as with the H2 plan approval and the H6 diff approval.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from ai_dev_orchestrator.diff_proposal.models import _summarize_validation_error
from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused

AUTHORIZATION_SCHEMA_VERSION = "supervised-implementer-authorization.v1"
AUTHORIZATION_STAGE = "propose_diff_stop_before_h6"

#: Fixed by D-7. A staleness guard, not a security property (A-22).
AUTH_TTL = timedelta(minutes=60)
#: How far ``consented_at`` may sit in the future of AIDO's clock.
CONSENT_CLOCK_SKEW = timedelta(minutes=5)

#: Fixed by D-8. A transport safety limit on buffered response bytes: never
#: sent to the server, never derived from or used as a token budget.
MAX_RESPONSE_BODY_BYTES = 16 * 1024 * 1024

#: The largest authorization file ``run`` will read.
MAX_AUTHORIZATION_FILE_BYTES = 64 * 1024

#: The exact per-run consent phrase. Distinct from the H2 plan sentence and the
#: H6 diff sentence; each of those is refused here.
CONSENT_TEXT = (
    "I consent to sending this one approved file to this model and endpoint "
    "for one supervised implementer request"
)
#: Required, exactly, iff the consented scheme is ``http``.
PLAINTEXT_ACKNOWLEDGEMENT = "I acknowledge this transmission is NOT TLS-ENCRYPTED"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_GIT_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_HOST = re.compile(r"^[A-Za-z0-9.\-:\[\]]{1,253}$")


def _hex64(value: str) -> str:
    if not _HEX64.fullmatch(value):
        raise ValueError("must be 64 lowercase hexadecimal characters.")
    return value


def _exactly(expected: object):
    def check(value: object) -> object:
        if value != expected:
            raise ValueError(f"must be exactly {expected!r}.")
        return value

    return check


def _must_be_false(value: bool) -> bool:
    if value is not False:
        raise ValueError("must be exactly false.")
    return value


def _number_not_bool(value: object) -> object:
    if type(value) not in (int, float):
        raise ValueError("must be a JSON number.")
    return value


def _aware_utc_iso(value: str) -> str:
    """An ISO-8601 timestamp that carries an explicit offset."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("must be an ISO-8601 timestamp.") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("must carry an explicit UTC offset.")
    return value


Hex64 = Annotated[StrictStr, AfterValidator(_hex64)]
ExactOne = Annotated[StrictInt, AfterValidator(_exactly(1))]
ExactZero = Annotated[StrictInt, AfterValidator(_exactly(0))]
StrictFalse = Annotated[StrictBool, AfterValidator(_must_be_false)]
AwareTimestamp = Annotated[StrictStr, AfterValidator(_aware_utc_iso)]
TimeoutSeconds = Annotated[
    float,
    BeforeValidator(_number_not_bool),
    Field(gt=0, le=3600, allow_inf_nan=False),
]


def parse_timestamp(value: str) -> datetime:
    """Parse a timestamp that already passed :data:`AwareTimestamp`."""
    return datetime.fromisoformat(value)


def utc_timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def canonical_json_bytes(value: object) -> bytes:
    """The one canonical serialization every P1B digest is computed over."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class AuthorizationBound(_Strict):
    """Everything one live run may do, written by ``prepare``. Never human-edited."""

    schema_version: Literal["supervised-implementer-authorization.v1"]
    run_id: StrictStr
    stage: Literal["propose_diff_stop_before_h6"]
    authorized_http_requests: ExactOne
    authorized_semantic_requests: ExactOne

    role: Literal["supervised_implementer"]
    candidate: Literal["SUP-D"]
    model: Literal["qwen3.8-27b"]
    provider: Literal["litellm"]

    project_id: StrictStr
    repo: StrictStr
    issue_number: StrictInt
    approved_plan_sha256: Hex64
    project_config_sha256: Hex64

    target_path: StrictStr
    change_type: Literal["modify"]
    source_sha256: Hex64
    source_bytes: StrictInt
    workspace_head_object_id: StrictStr
    workspace_git_state: Literal["clean_tree_at_head_target_tracked_ordinary_blob"]

    request_sha256: Hex64
    structured_output_mode: Literal["none"]
    requested_max_output_tokens: StrictInt | None
    attempt_timeout_seconds: TimeoutSeconds
    max_response_body_bytes: Annotated[StrictInt, AfterValidator(_exactly(MAX_RESPONSE_BODY_BYTES))]
    allow_insecure_http: StrictBool

    evidence_dir_sha256: Hex64
    authorization_ledger_dir_sha256: Hex64
    issuance_sha256: Hex64
    prepared_at: AwareTimestamp
    expires_at: AwareTimestamp
    aido_version: StrictStr

    binding_sha256: Hex64

    @field_validator("run_id")
    @classmethod
    def _run_id_shape(cls, value: str) -> str:
        if not _RUN_ID.fullmatch(value):
            raise ValueError("must be 32 lowercase hexadecimal characters.")
        return value

    @field_validator("workspace_head_object_id")
    @classmethod
    def _object_id_shape(cls, value: str) -> str:
        if not _GIT_OBJECT_ID.fullmatch(value):
            raise ValueError("must be a full lowercase Git object id.")
        return value

    @field_validator("issue_number")
    @classmethod
    def _positive_issue(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be positive.")
        return value

    @field_validator("source_bytes")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must not be negative.")
        return value

    @field_validator("requested_max_output_tokens")
    @classmethod
    def _positive_cap(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("must be null or a positive integer.")
        return value

    @model_validator(mode="after")
    def _binding_and_expiry_agree(self) -> AuthorizationBound:
        if parse_timestamp(self.expires_at) != parse_timestamp(self.prepared_at) + AUTH_TTL:
            raise ValueError("expires_at must be exactly prepared_at plus the fixed TTL.")
        if compute_binding_sha256(self) != self.binding_sha256:
            raise ValueError(
                "binding_sha256 does not match the bound section: it was edited "
                "after prepare wrote it."
            )
        return self


def compute_binding_sha256(bound: AuthorizationBound | dict) -> str:
    """SHA-256 over the canonical JSON of every bound field except the digest itself."""
    data = (
        bound.model_dump(mode="json", exclude={"binding_sha256"})
        if isinstance(bound, AuthorizationBound)
        else {key: value for key, value in bound.items() if key != "binding_sha256"}
    )
    return sha256_hex(canonical_json_bytes(data))


class AuthorizationConsent(_Strict):
    """The human's per-run consent. Never inferred from config or flags."""

    consented_by: StrictStr = Field(min_length=1, max_length=200)
    consented_at: AwareTimestamp
    source: Literal["manual"]
    binding_sha256: Hex64
    endpoint_scheme: Literal["http", "https"]
    endpoint_host: StrictStr
    endpoint_port: StrictInt
    consent_text: Literal[CONSENT_TEXT]  # type: ignore[valid-type]
    plaintext_acknowledgement: Literal[PLAINTEXT_ACKNOWLEDGEMENT] | None = None  # type: ignore[valid-type]

    @field_validator("consented_by")
    @classmethod
    def _plain_name(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("must be non-blank text without control characters.")
        return value

    @field_validator("endpoint_host")
    @classmethod
    def _host_shape(cls, value: str) -> str:
        if not _HOST.fullmatch(value):
            raise ValueError("must be a plain ASCII host name or address, without scheme or port.")
        return value

    @field_validator("endpoint_port")
    @classmethod
    def _port_range(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("must be between 1 and 65535.")
        return value

    @model_validator(mode="after")
    def _acknowledgement_iff_plaintext(self) -> AuthorizationConsent:
        if self.endpoint_scheme == "http" and self.plaintext_acknowledgement != PLAINTEXT_ACKNOWLEDGEMENT:
            raise ValueError(
                "an http endpoint requires the exact plaintext acknowledgement."
            )
        if self.endpoint_scheme == "https" and self.plaintext_acknowledgement is not None:
            raise ValueError(
                "a plaintext acknowledgement was given for an https endpoint; it "
                "is refused rather than ignored."
            )
        return self

    @property
    def normalized_host(self) -> str:
        """The one stated normalization: ASCII lowercase."""
        return self.endpoint_host.lower()


class SupervisedImplementerAuthorization(_Strict):
    """A complete, human-consented authorization for exactly one live run."""

    bound: AuthorizationBound
    consent: AuthorizationConsent

    @model_validator(mode="after")
    def _consent_echoes_binding(self) -> SupervisedImplementerAuthorization:
        if self.consent.binding_sha256 != self.bound.binding_sha256:
            raise ValueError("consent.binding_sha256 does not echo bound.binding_sha256.")
        return self


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def _refuse(category: str, message: str) -> SupervisedImplementerRefused:
    return SupervisedImplementerRefused(category, message)


def parse_authorization(data: bytes) -> SupervisedImplementerAuthorization:
    """Strictly parse a consented authorization. Rejects, never repairs.

    A draft (empty consent), an edited ``bound`` section, a wrong or reused
    phrase, an acknowledgement on ``https``, a missing one on ``http``, a naive
    timestamp, a duplicate key, or any extra or missing key is refused. Values
    are never echoed.
    """
    if type(data) is not bytes:
        raise _refuse("authorization_invalid", "the authorization must be read as bytes.")
    if len(data) > MAX_AUTHORIZATION_FILE_BYTES:
        raise _refuse("authorization_invalid", "the authorization file is too large.")
    try:
        text = data.decode("utf-8")
        decoded = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise _refuse(
            "authorization_invalid",
            "the authorization is not strict UTF-8 JSON, or repeats a key.",
        ) from None
    if not isinstance(decoded, dict):
        raise _refuse("authorization_invalid", "the authorization must be a JSON object.")
    try:
        return SupervisedImplementerAuthorization.model_validate(decoded)
    except ValidationError as exc:
        raise _refuse(
            "authorization_invalid",
            "the authorization is incomplete, edited, or malformed: "
            + _summarize_validation_error(exc),
        ) from None


#: The consent block a draft carries. Deliberately non-parsing: every field a
#: human must supply is empty, so a draft is never mistaken for consent.
DRAFT_CONSENT_TEMPLATE: dict[str, object] = {
    "consented_by": "",
    "consented_at": "",
    "source": "manual",
    "binding_sha256": "",
    "endpoint_scheme": "",
    "endpoint_host": "",
    "endpoint_port": 0,
    "consent_text": "",
    "plaintext_acknowledgement": None,
}


def render_authorization_draft(bound: AuthorizationBound) -> bytes:
    """The draft ``prepare`` writes: the bound section plus an empty consent."""
    document = {
        "bound": bound.model_dump(mode="json"),
        "consent": dict(DRAFT_CONSENT_TEMPLATE),
    }
    return (json.dumps(document, ensure_ascii=True, indent=2) + "\n").encode("ascii")
