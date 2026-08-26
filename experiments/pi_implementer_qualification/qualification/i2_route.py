"""I2-3 -- route descriptors, and the offline route-check wiring shape (I2A Sec. 15/19/20).

**OFFLINE ONLY.** This module never calls a real route. The one non-inference
gate this route depends on -- ``ar2.route_check.check_route_serves_model``,
reused UNMODIFIED per the design -- is wired here only via dependency
injection: :func:`run_offline_route_check` accepts a ``checker`` callable
with that function's exact signature shape, and every offline test supplies
a synthetic double. A real, live call is a future, separately authorized
step.

Candidate identity agrees EXACTLY with the accepted I1 pairing
(``qualification.records.CANDIDATE_MODEL_IDS``) -- imported here, never
re-declared, so the two mappings cannot silently drift apart.

**5F3B-I2-FU2: RouteDescriptor is a trusted value object.** Independent
review demonstrated a directly-forged ``RouteDescriptor`` (arbitrary
``model_id``/``provider_id``/``backend_gateway_class``/
``credential_mechanism``/``credential_env_var_name``) reached
:func:`run_offline_route_check` and could return ``passed=True``. Every
field is now mechanically enforced, twice: once at construction
(``__post_init__``), and again at the ``run_offline_route_check``
consumption boundary, immediately before the checker is ever invoked.

**5F3B-I2-FU3, three further closures:**

1. **The route input is a trusted object, not a raw string.**
   ``run_offline_route_check`` no longer takes a raw ``base_url: str`` --
   independent review passed ``base_url="not-a-url"`` straight through to
   a synthetic checker. It now consumes an already-valid
   ``i2_secret_context.QualificationRouteSecretContext``, whose ``base_url``
   was already validated by ``validate_b300_base_url`` in its own
   ``__post_init__`` -- reused, not duplicated, by a defensive re-check
   here too (no second validator is added).
2. **Exact bool types for the checker's result.** Independent review had
   ``result.reachable = "false"`` / ``result.configured_model_served =
   "false"`` coerce, via bare ``bool(...)``, into ``True``/``True`` and a
   PASS. Both fields are now required to be ``type(...) is bool`` exactly;
   anything else fails closed as ``RouteFailureCode.ROUTE_CHECK_INVALID_RESULT``,
   never PASS, and the raw (non-bool) value is never read into, or
   retained by, the outcome.
3. **``RouteCheckOutcome`` cannot express an impossible state.** Its own
   ``__post_init__`` now enforces exact-bool typing on all three boolean
   fields and requires ``passed=True`` to imply
   ``reachable=configured_model_served=True`` with no ``failure_code``, and
   ``passed=False`` to always carry a declared ``failure_code``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from .i2_identity import CREDENTIAL_ENV_VAR_NAME, PROVIDER_ID
from .i2_secret_context import QualificationRouteSecretContext, validate_b300_base_url
from .records import CANDIDATE_MODEL_IDS

#: I2A Sec. 6/19: this route is always the LiteLLM-proxied B300 backend,
#: never direct vLLM, never the built-in Qwen/MiniMax cloud catalogs.
BACKEND_GATEWAY_CLASS = "b300_litellm_proxy"

#: I2A Sec. 7/19: the chosen credential mechanism.
CREDENTIAL_MECHANISM = "models_json_env_interpolation"


class RouteDescriptorError(Exception):
    """An unknown or malformed candidate/model route request. Fails closed."""


def validate_candidate_model_pairing(candidate: str, model_id: str) -> None:
    """Refuse any candidate/model pairing other than the frozen I1 mapping.

    Catches both an unknown candidate and a REVERSED pairing (e.g. candidate
    ``"A"`` proposed with Candidate B's model id).
    """
    if candidate not in CANDIDATE_MODEL_IDS:
        raise RouteDescriptorError(
            f"unknown candidate {candidate!r}; declared: {sorted(CANDIDATE_MODEL_IDS)}"
        )
    expected = CANDIDATE_MODEL_IDS[candidate]
    if model_id != expected:
        raise RouteDescriptorError(
            f"candidate {candidate!r} is bound to model id {expected!r}, but "
            f"{model_id!r} was proposed; a reversed or mismatched pairing is refused"
        )


def _validate_route_descriptor_fields(
    *,
    candidate: str,
    model_id: str,
    provider_id: str,
    backend_gateway_class: str,
    credential_mechanism: str,
    credential_env_var_name: str,
) -> None:
    """The ONE shared field-level validator (5F3B-I2-FU2), used both by
    ``RouteDescriptor.__post_init__`` and by ``run_offline_route_check``'s
    consumption-boundary revalidation -- one rule set, checked twice.
    """
    validate_candidate_model_pairing(candidate, model_id)
    if provider_id != PROVIDER_ID:
        raise RouteDescriptorError(
            "route descriptor error: provider_id does not match the fixed "
            "qualification provider id"
        )
    if backend_gateway_class != BACKEND_GATEWAY_CLASS:
        raise RouteDescriptorError(
            "route descriptor error: backend_gateway_class does not match the "
            "fixed B300 LiteLLM proxy class (never direct vLLM)"
        )
    if credential_mechanism != CREDENTIAL_MECHANISM:
        raise RouteDescriptorError(
            "route descriptor error: credential_mechanism does not match the "
            "fixed qualification mechanism"
        )
    if credential_env_var_name != CREDENTIAL_ENV_VAR_NAME:
        raise RouteDescriptorError(
            "route descriptor error: credential_env_var_name does not match the "
            "fixed qualification credential carrier"
        )


@dataclass(frozen=True)
class RouteDescriptor:
    """One candidate's fixed route identity. Only ``candidate``/``model_id`` differ.

    **Valid by construction (5F3B-I2-FU2).** ``__post_init__`` calls
    :func:`_validate_route_descriptor_fields` -- every field is mechanically
    checked against the frozen identity, not merely the candidate/model
    pairing.
    """

    candidate: str
    model_id: str
    provider_id: str
    backend_gateway_class: str
    credential_mechanism: str
    credential_env_var_name: str

    def __post_init__(self) -> None:
        _validate_route_descriptor_fields(
            candidate=self.candidate,
            model_id=self.model_id,
            provider_id=self.provider_id,
            backend_gateway_class=self.backend_gateway_class,
            credential_mechanism=self.credential_mechanism,
            credential_env_var_name=self.credential_env_var_name,
        )


def route_descriptor_for_candidate(candidate: str) -> RouteDescriptor:
    """Build the frozen route descriptor for one candidate.

    Identical child-env builder, generator, compatibility gate, token
    policy, and credential mechanism for both candidates (I2A Sec. 20) --
    this function has no candidate-specific branch beyond selecting the
    model id from the frozen I1 pairing.
    """
    if candidate not in CANDIDATE_MODEL_IDS:
        raise RouteDescriptorError(
            f"unknown candidate {candidate!r}; declared: {sorted(CANDIDATE_MODEL_IDS)}"
        )
    model_id = CANDIDATE_MODEL_IDS[candidate]
    return RouteDescriptor(
        candidate=candidate,
        model_id=model_id,
        provider_id=PROVIDER_ID,
        backend_gateway_class=BACKEND_GATEWAY_CLASS,
        credential_mechanism=CREDENTIAL_MECHANISM,
        credential_env_var_name=CREDENTIAL_ENV_VAR_NAME,
    )


class RouteFailureCode(str, Enum):
    """Bounded, declared route-check failure codes (5F3B-I2-FU1, extended FU2).

    NEVER free-form prose. A raw ``checker.failure`` string may contain a
    full endpoint, ``Authorization``/``Bearer`` text, or a credential --
    independent review demonstrated exactly that. This outcome carries only
    one of these fixed codes, mechanically derived from
    ``reachable``/``configured_model_served`` (or from the checker raising,
    see ``ROUTE_CHECK_ERROR``); the checker's own ``failure`` attribute,
    whatever it contains, is never read, and an exception the checker
    raises is never retained as ``str(exc)``/``repr(exc)``/traceback text.
    """

    ROUTE_UNREACHABLE = "ROUTE_UNREACHABLE"
    MODEL_NOT_SERVED = "MODEL_NOT_SERVED"
    ROUTE_CHECK_ERROR = "ROUTE_CHECK_ERROR"
    ROUTE_CHECK_INVALID_RESULT = "ROUTE_CHECK_INVALID_RESULT"


@dataclass(frozen=True)
class RouteCheckOutcome:
    """The offline-wired result of the future zero-prompt route-check gate.

    Carries only bounded, mechanically-derived fields. There is no field
    here that could ever hold arbitrary checker/provider prose -- see
    :class:`RouteFailureCode`.

    **Valid by construction (5F3B-I2-FU3).** ``__post_init__`` requires
    ``passed``/``reachable``/``configured_model_served`` to be exactly
    ``bool`` (no ``"false"``/``1``/``0`` coercion survives to this point --
    they are already rejected earlier, in :func:`run_offline_route_check`,
    but this object refuses to describe an impossible state regardless of
    how it was built), and enforces the same
    ``passed`` <-> ``reachable``/``configured_model_served``/``failure_code``
    coherence :class:`~qualification.i2_credentials.PreflightGateResult`
    enforces for its own boolean.
    """

    passed: bool
    reachable: bool
    configured_model_served: bool
    failure_code: RouteFailureCode | None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("passed", self.passed),
            ("reachable", self.reachable),
            ("configured_model_served", self.configured_model_served),
        ):
            if type(value) is not bool:
                raise ValueError(
                    f"RouteCheckOutcome: {field_name} must be exactly a bool, got "
                    f"{type(value).__name__}"
                )
        if self.passed:
            if not (self.reachable and self.configured_model_served):
                raise ValueError(
                    "RouteCheckOutcome: passed=True requires reachable=True and "
                    "configured_model_served=True"
                )
            if self.failure_code is not None:
                raise ValueError(
                    "RouteCheckOutcome: passed=True must not carry a failure_code"
                )
        elif self.failure_code is None:
            raise ValueError(
                "RouteCheckOutcome: passed=False requires a declared failure_code"
            )


def run_offline_route_check(
    *,
    descriptor: RouteDescriptor,
    secret_context: QualificationRouteSecretContext,
    checker: Callable[..., Any],
) -> RouteCheckOutcome:
    """Wire the future zero-prompt route-check gate, via dependency injection.

    ``checker`` must accept the exact ``ar2.route_check.check_route_serves_model``
    call shape -- ``checker(base_url, model_id=...)`` -- so a real,
    unmodified call can be substituted later without changing this function.
    **This phase NEVER supplies a real checker**; every offline test injects
    a synthetic one.

    The descriptor's OWN ``model_id`` is always what is passed -- there is
    no fallback, no substitution, and no alternate model ever supplied on a
    mismatch. Both an unreachable result and a reachable-but-wrong-model
    result fail closed (``passed=False``).

    **5F3B-I2-FU1: the checker's ``failure`` attribute is never read.** An
    earlier revision copied it verbatim into the outcome, which could
    retain a raw endpoint/credential/``Authorization`` string a live
    checker might produce. The failure reason is now derived ONLY from the
    two booleans this function already inspects.

    **5F3B-I2-FU2:**

    1. **Consumption-boundary revalidation.** ``descriptor`` is
       revalidated field-by-field, via the SAME shared validator
       ``RouteDescriptor.__post_init__`` uses, BEFORE the checker is ever
       invoked -- a second, independent defense beyond construction-time
       validation, for a descriptor that reached this function through any
       path other than its own constructor (e.g. deserialization, or a
       future caller bypassing ``__init__``). A forged/invalid descriptor
       never reaches ``checker`` at all.
    2. **Bounded exception handling.** If ``checker`` itself RAISES (not
       merely returns an unreachable/wrong-model result), the exception is
       caught and reduced to the bounded ``RouteFailureCode.ROUTE_CHECK_ERROR``
       -- never ``str(exc)``, ``repr(exc)``, or traceback text.

    **5F3B-I2-FU3:**

    3. **Route input is a trusted object.** ``secret_context`` (not a raw
       ``base_url: str``) supplies the URL, already validated by its own
       ``__post_init__``; this function additionally re-runs
       ``validate_b300_base_url`` on it defensively (the SAME shared
       validator -- never a second one) before the checker is invoked.
    4. **Exact-bool result typing.** ``result.reachable`` /
       ``result.configured_model_served`` must be ``type(...) is bool``
       exactly -- a truthy non-bool stand-in (``"false"``, ``1``, ``0``)
       fails closed as ``ROUTE_CHECK_INVALID_RESULT`` rather than being
       coerced by a bare ``bool(...)`` call.

    **5F3B-I2-FU3A: mandatory cross-object binding, enforced HERE.** Before
    the descriptor's own field revalidation even runs, this function now
    ALSO refuses (``RouteDescriptorError``) if ``descriptor.provider_id`` or
    ``descriptor.model_id`` disagrees with ``secret_context.provider_id`` /
    ``secret_context.model_id`` -- so a caller who skips
    ``i2_composition.verify_i2_identity_binding`` can no longer run a route
    check for a Candidate-A descriptor against a Candidate-B secret context
    (or vice versa). The checker is never invoked in that case.
    """
    if descriptor.provider_id != secret_context.provider_id:
        raise RouteDescriptorError(
            "route descriptor error: descriptor provider_id does not match "
            "the run's secret context"
        )
    if descriptor.model_id != secret_context.model_id:
        raise RouteDescriptorError(
            "route descriptor error: descriptor model_id does not match "
            "the run's secret context"
        )

    _validate_route_descriptor_fields(
        candidate=descriptor.candidate,
        model_id=descriptor.model_id,
        provider_id=descriptor.provider_id,
        backend_gateway_class=descriptor.backend_gateway_class,
        credential_mechanism=descriptor.credential_mechanism,
        credential_env_var_name=descriptor.credential_env_var_name,
    )
    # Defensive re-check of the ALREADY-valid secret context's base_url --
    # the same shared validator secret_context.__post_init__ already ran,
    # not a second one.
    validate_b300_base_url(secret_context.base_url)

    try:
        result = checker(secret_context.base_url, model_id=descriptor.model_id)
    except Exception:
        return RouteCheckOutcome(
            passed=False,
            reachable=False,
            configured_model_served=False,
            failure_code=RouteFailureCode.ROUTE_CHECK_ERROR,
        )

    raw_reachable = getattr(result, "reachable", None)
    raw_served = getattr(result, "configured_model_served", None)
    if type(raw_reachable) is not bool or type(raw_served) is not bool:
        return RouteCheckOutcome(
            passed=False,
            reachable=False,
            configured_model_served=False,
            failure_code=RouteFailureCode.ROUTE_CHECK_INVALID_RESULT,
        )

    reachable = raw_reachable
    served = raw_served
    passed = reachable and served
    if passed:
        failure_code = None
    elif not reachable:
        failure_code = RouteFailureCode.ROUTE_UNREACHABLE
    else:
        failure_code = RouteFailureCode.MODEL_NOT_SERVED
    return RouteCheckOutcome(
        passed=passed,
        reachable=reachable,
        configured_model_served=served,
        failure_code=failure_code,
    )
