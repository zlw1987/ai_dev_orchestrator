"""5F3B-I2B-L1-LF2 -- the qualification-owned, credential-bearing B300 route observation.

**WHY THIS MODULE EXISTS AT ALL.**

Frozen I2A Sec. 15 item 9 mandated that the future Category-B zero-prompt
gate reuse the **unmodified** ``ar2.route_check.check_route_serves_model``
as its live route checker. Candidate-A's second real Category-B attempt
(``results/i2b_live_A_20260831T224840Z.json``) passed every runtime-side
compatibility gate and then failed exactly one:

.. code-block:: text

    route_check -> ROUTE_CHECK_FAILED
    exact_candidate_model_served = false

The refusal itself is correct and is not reopened here: **the route gate did
not establish success.** What the retained evidence does NOT establish is
*why*. The frozen AR2 checker issues its ``GET <base_url>/models`` through
``httpx.Client(trust_env=False)`` with **no Authorization header**, and
accepts no credential parameter at all, so its ``configured_model_served ==
False`` collapses at least these seven distinct facts into one
indistinguishable result:

.. code-block:: text

    A. transport unreachable
    B. HTTP 401                      <- an AUTH fact, not a model fact
    C. HTTP 403                      <- an AUTH fact, not a model fact
    D. another non-200 status
    E. HTTP 200, malformed body
    F. HTTP 200, valid listing, candidate absent
    G. a malformed checker result

Frozen I2A Sec. 24 item 1 recorded, honestly, that whether the B300 LiteLLM
proxy validates the ``Authorization`` header for this route was **unknown
from local source**. It nevertheless required the unmodified, unauthenticated
checker. Live evidence has now activated that open question, so the
assumption -- not the checker -- is what LF2 corrects.

**WHAT IS AND IS NOT CHANGED.**

- ``experiments/pi_external_runtime_ar2/ar2/route_check.py`` is **frozen and
  unmodified**, and remains AR2's own accepted checker for AR2's own route.
  Nothing here imports it, forks it, copies it, or wraps it.
- No credential is smuggled into a function whose accepted contract does not
  express one. This is a **new, qualification-owned** observation whose
  contract *does* express the credential, explicitly.
- This module performs exactly **one** non-inference ``GET``. It sends no
  prompt, requests no generation, and runs no inference. It is never counted
  as one of the four semantic prompts.

**WHAT THIS MODULE IS NOT.**

Not a provider registry, not a fallback endpoint, not a fallback model, not a
retry policy, not a differential auth probe (calling once with a good
credential and once with a bad one to *prove* something about auth is a
separate, unauthorized experiment), and not a generalized HTTP client. The
same-run authority binding that decides *which* route and *which* model may
ever be observed lives in :mod:`qualification.i2b_live_adapters`, not here --
this module is the mechanism, never the authority.

**RETENTION.** Nothing raw survives an observation. Not the response body,
not a served model-id list, not the HTTP status number, not the endpoint, not
the host, not the base URL, not the credential, and not an exception message
or traceback. A finished observation carries exactly two exact bools and one
declared code drawn from :data:`ROUTE_DIAGNOSTIC_CODES`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

# -- the bounded route diagnostic vocabulary (LF2 OBJECTIVE 5) ---------------
#
# Declared literals ONLY. These exist so a route refusal can be attributed
# TRUTHFULLY; they are never a verdict, and the frozen Category-B controller
# continues to reduce every failure shape to its own single
# ``ROUTE_CHECK_FAILED`` code without being reopened.

#: HTTP 200, a valid bounded listing, and the exact candidate model id present.
#: The ONLY code under which ``configured_model_served`` may be ``True``.
ROUTE_MODEL_SERVED = "route_model_served"

#: The request never produced an HTTP response (DNS, connect, TLS, read,
#: timeout, or any other transport-layer failure). Says NOTHING about the model.
ROUTE_TRANSPORT_UNREACHABLE = "route_transport_unreachable"

#: HTTP 401 or 403. An AUTHENTICATION/AUTHORIZATION fact about this request.
#: It is **not** evidence that the candidate model is absent from the route.
ROUTE_AUTH_REJECTED = "route_auth_rejected"

#: Any other non-200 status, including a 3xx the run refused to follow (see
#: the redirect policy below). Says NOTHING about the model.
ROUTE_HTTP_REJECTED = "route_http_rejected"

#: HTTP 200 whose body is not a bounded, strictly-shaped OpenAI-compatible
#: model listing. Says NOTHING about the model.
ROUTE_LISTING_MALFORMED = "route_listing_malformed"

#: HTTP 200, a valid bounded listing, and the exact candidate model id ABSENT.
#: This is the ONLY code that may ever be read as "this route did not list
#: this model", and only for the exact route and model this run was bound to.
ROUTE_MODEL_NOT_LISTED = "route_model_not_listed"

#: A route-check RESULT object did not conform (non-``bool`` fields, missing
#: attributes, or an observation that could not be built). Retained for the
#: L1 harness so a checker-shape failure is never read as a model fact.
ROUTE_RESULT_MALFORMED = "route_result_malformed"

#: The observation was REFUSED before any request was made, because the
#: same-run authority binding did not hold (a substituted base URL, a
#: substituted candidate model, a missing consumed credential, or a second
#: observation attempt). No HTTP request was issued.
ROUTE_AUTHORITY_REFUSED = "route_authority_refused"

#: The route stage was never reached -- an earlier Category-B gate failed
#: first, so no route observation exists. The default; never a failure of the
#: route itself.
ROUTE_NOT_OBSERVED = "route_not_observed"

#: Every literal a route diagnostic may ever hold. An offline test asserts
#: that every produced value is drawn from this set.
ROUTE_DIAGNOSTIC_CODES: frozenset[str] = frozenset(
    {
        ROUTE_MODEL_SERVED,
        ROUTE_TRANSPORT_UNREACHABLE,
        ROUTE_AUTH_REJECTED,
        ROUTE_HTTP_REJECTED,
        ROUTE_LISTING_MALFORMED,
        ROUTE_MODEL_NOT_LISTED,
        ROUTE_RESULT_MALFORMED,
        ROUTE_AUTHORITY_REFUSED,
        ROUTE_NOT_OBSERVED,
    }
)

#: The only code under which a successful route fact may be reported.
_SERVED_CODE = ROUTE_MODEL_SERVED

#: AIDO's own bound on this one request. No retry, so this is the whole budget.
B300_ROUTE_OBSERVATION_TIMEOUT_SECONDS = 20.0

#: Bounded listing shape. A listing larger than this, or with more entries
#: than this, is refused as malformed rather than parsed -- a route that
#: answers with an unbounded body must not become an unbounded read here.
_MAX_LISTING_BYTES = 1_048_576
_MAX_LISTING_ENTRIES = 4_096
_MAX_MODEL_ID_LENGTH = 512

#: **REDIRECT POLICY (LF2).** Redirects are DISABLED, explicitly, not
#: inherited from an httpx default that a future version could change. A
#: credential-bearing request must never be moved to an authority this run
#: never approved: httpx re-sends the ``Authorization`` header on a
#: same-origin redirect, and a cross-origin redirect would either leak the
#: credential or silently change which endpoint answered the "does this route
#: serve this model" question. With redirects disabled a 3xx is simply a
#: non-200 status and classifies as :data:`ROUTE_HTTP_REJECTED`. Nothing here
#: upgrades, rewrites, tunnels, or follows a URL.
_FOLLOW_REDIRECTS = False

#: **AMBIENT TRANSPORT POLICY.** Inherited unchanged from the reasoning AR2's
#: own FU-C recorded: a default ``httpx.Client`` honors ``HTTP_PROXY`` /
#: ``HTTPS_PROXY`` / ``ALL_PROXY`` and other ambient environment state, which
#: would make this observation depend on whatever happens to be set in the
#: operator's shell -- silently routing a CREDENTIAL-BEARING request through
#: a proxy this design never named. ``trust_env=False``, always.
_TRUST_ENV = False


class B300RouteObservationError(Exception):
    """A bounded refusal. Structurally incapable of carrying a secret.

    Every message this exception may ever carry is a fixed literal chosen in
    this module. No caller value -- base URL, host, credential, model id,
    status code, response body, or nested exception text -- is ever
    interpolated into it, and no ``from exc`` chain is preserved on a path
    that saw a real response.
    """


@dataclass(frozen=True)
class B300RouteObservation:
    """What ONE authenticated, non-inference model listing actually established.

    Deliberately shaped so that
    :func:`qualification.i2_route.run_offline_route_check` consumes it
    **unmodified**: it exposes exactly the ``reachable`` /
    ``configured_model_served`` attribute pair that function already requires
    to be ``type(...) is bool``. The added ``diagnostic_code`` is invisible to
    that function and to the frozen controller -- it exists only for the L1
    harness's bounded attribution record.

    Valid by construction, in the same style as
    :class:`qualification.i2_route.RouteCheckOutcome`: an impossible state
    cannot be built at all.
    """

    reachable: bool
    configured_model_served: bool
    diagnostic_code: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("reachable", self.reachable),
            ("configured_model_served", self.configured_model_served),
        ):
            if type(value) is not bool:
                raise B300RouteObservationError(
                    f"route observation: {field_name} must be exactly a bool"
                )
        if self.diagnostic_code not in ROUTE_DIAGNOSTIC_CODES:
            raise B300RouteObservationError(
                "route observation: diagnostic_code is not one of the declared codes"
            )
        if self.diagnostic_code == ROUTE_NOT_OBSERVED:
            raise B300RouteObservationError(
                "route observation: 'route_not_observed' describes the ABSENCE of "
                "an observation and can never be one"
            )
        if self.configured_model_served:
            # A successful route fact requires ALL THREE: HTTP 200, a valid
            # bounded listing shape, and the exact candidate model id present
            # -- which is exactly what _SERVED_CODE means and the only path
            # that produces it. Success is never inferred from HTTP 200 alone.
            if self.diagnostic_code != _SERVED_CODE:
                raise B300RouteObservationError(
                    "route observation: configured_model_served=True requires the "
                    "'route_model_served' diagnostic"
                )
            if not self.reachable:
                raise B300RouteObservationError(
                    "route observation: configured_model_served=True requires reachable=True"
                )
        elif self.diagnostic_code == _SERVED_CODE:
            raise B300RouteObservationError(
                "route observation: the 'route_model_served' diagnostic requires "
                "configured_model_served=True"
            )

    def as_dict(self) -> dict[str, Any]:
        """The retainable record. Two bools and one declared code -- nothing else.

        There is deliberately NO status code, NO served-model-id list, NO
        failure prose, NO host, NO scheme and NO base URL here. AR2's own
        checker reports a status code and the served ids; this one does not,
        because those are raw response content and this request carries a
        credential.
        """
        return {
            "check": "authenticated_non_inference_model_listing",
            "is_a_semantic_prompt": False,
            "tokens_generated": 0,
            "reachable": self.reachable,
            "configured_model_served": self.configured_model_served,
            "route_diagnostic": self.diagnostic_code,
            "status_code_recorded": False,
            "served_model_ids_recorded": False,
            "response_body_recorded": False,
            "endpoint_host_recorded": False,
            "base_url_recorded": False,
            "credential_recorded": False,
            "redirects_followed": False,
            "requests_issued": 1,
            "matching": "exact and case-sensitive; nothing is substituted or auto-selected",
        }


def _open_route_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """The ONE client factory. Both policy flags are set here, explicitly.

    ``transport`` exists so the offline suite can inject an
    ``httpx.MockTransport``; it is ``None`` on every live path, and it never
    relaxes ``trust_env`` or ``follow_redirects``. An offline test opens a
    client through this factory and asserts both attributes mechanically,
    rather than reading them out of this docstring.
    """
    if transport is None:
        return httpx.Client(trust_env=_TRUST_ENV, follow_redirects=_FOLLOW_REDIRECTS)
    return httpx.Client(
        trust_env=_TRUST_ENV, follow_redirects=_FOLLOW_REDIRECTS, transport=transport
    )


def build_route_authorization_header(api_key: str) -> str:
    """The mechanically-established B300 ``Authorization`` header VALUE.

    Established from two independent, in-repository sources, neither of them
    a guess about this endpoint:

    1. **Pi's own resolved-auth path.** The generated qualification
       ``models.json`` declares ``api: "openai-completions"`` with
       ``apiKey: "$PI_QUALIFICATION_B300_ROUTE_KEY"``
       (:mod:`qualification.i2_pi_config`). I2A Sec. 5's provider table
       records that the ``openai-completions`` api type "already sends"
       ``Authorization: Bearer <key>`` -- which is precisely why
       ``authHeader: true`` is documented as unnecessary for it and is not
       emitted.
    2. **AIDO's own shipped LiteLLM client**, which talks to this same route
       from the same two environment variables: ``src/ai_dev_orchestrator/
       llm/client.py`` builds ``{"Authorization": f"Bearer {api_key}"}`` from
       the ``AIDO_LITELLM_API_KEY`` loaded beside ``AIDO_LITELLM_BASE_URL``.

    So the credential Pi receives for this route, and the credential AIDO's
    production client already sends to it, are the same value in the same
    header shape. ``/models`` is part of that same OpenAI-compatible route
    identity, so the listing is observed under the same header rather than
    anonymously.

    The returned string is a live credential-bearing value. It is passed
    straight into one request's headers and is never logged, stored,
    repr'd, or returned to an artifact.
    """
    if type(api_key) is not str or not api_key.strip():
        raise B300RouteObservationError(
            "route observation refused: the route credential is missing or blank"
        )
    return f"Bearer {api_key}"


def _parse_bounded_model_listing(body: bytes) -> tuple[str, ...] | None:
    """Strictly validate a bounded OpenAI-compatible listing. ``None`` = malformed.

    Strict, and deliberately so: a listing AIDO cannot fully understand must
    never be allowed to produce -- or to deny -- an exact-model match. Every
    rejection below returns ``None`` and classifies as
    :data:`ROUTE_LISTING_MALFORMED`, which is explicitly NOT the same fact as
    "the model is absent".
    """
    if len(body) > _MAX_LISTING_BYTES:
        return None
    try:
        payload = json.loads(body)
    except Exception:  # noqa: BLE001 - an unparseable listing fails closed
        return None
    if type(payload) is not dict:
        return None
    data = payload.get("data")
    if type(data) is not list:
        return None
    if len(data) > _MAX_LISTING_ENTRIES:
        return None

    ids: list[str] = []
    for entry in data:
        # A malformed ENTRY makes the whole listing malformed. It can
        # therefore never contribute a match, and -- just as important --
        # never contribute a confident NON-match either.
        if type(entry) is not dict:
            return None
        entry_id = entry.get("id")
        if type(entry_id) is not str:
            return None
        if not entry_id or len(entry_id) > _MAX_MODEL_ID_LENGTH:
            return None
        ids.append(entry_id)
    return tuple(ids)


def _listing_contains_exact_model(served_ids: tuple[str, ...], model_id: str) -> bool:
    """Exact, case-sensitive ``==`` over the listed ids. Never set-based.

    Written as an explicit equality loop rather than ``model_id in set(ids)``
    so that the authority is unmistakably one string comparison per entry: no
    hashing, no normalization, no case folding, no prefix or family match, no
    substitution, and nothing auto-selected. Duplicate ids are therefore
    simply harmless -- the same comparison answers the same way twice.
    """
    for served_id in served_ids:
        if served_id == model_id:
            return True
    return False


def observe_b300_route_serves_model(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    transport: httpx.BaseTransport | None = None,
) -> B300RouteObservation:
    """ONE authenticated, non-inference ``GET <base_url>/models``. Fails closed.

    No retry, no fallback endpoint, no fallback model, no redirect, no second
    request of any kind. Exactly one HTTP request is issued per call, and the
    same-run authority that decides this call may happen at all is enforced by
    the caller in :mod:`qualification.i2b_live_adapters` -- this function is
    the mechanism, not the authority.

    The path is built exactly as AR2 built it (``base_url.rstrip("/") +
    "/models"``), so a ``base_url`` already ending in ``/v1`` yields
    ``/v1/models``. The qualification URL validator has already refused any
    query string or fragment, so no parameter is appended and none can be
    inherited.

    **Nothing raw is retained on any path.** A transport failure retains no
    exception text; a non-200 retains no status number and no body; a
    malformed 200 retains no body; a valid listing retains no served-id list.
    """
    authorization = build_route_authorization_header(api_key)
    listing_url = base_url.rstrip("/") + "/models"

    try:
        with _open_route_client(transport) as client:
            response = client.get(
                listing_url,
                headers={
                    "Authorization": authorization,
                    "Accept": "application/json",
                },
                timeout=B300_ROUTE_OBSERVATION_TIMEOUT_SECONDS,
            )
    except Exception:  # noqa: BLE001 - any transport failure fails closed
        # Deliberately no `as exc`: not the type name, not the message, not a
        # traceback. A transport failure is a transport failure.
        return B300RouteObservation(
            reachable=False,
            configured_model_served=False,
            diagnostic_code=ROUTE_TRANSPORT_UNREACHABLE,
        )

    status_code = response.status_code
    if status_code in (401, 403):
        # THE FACT LF2 EXISTS FOR. This is an auth fact about this request.
        # It is never reported, recorded, or read as "the model is absent".
        return B300RouteObservation(
            reachable=True,
            configured_model_served=False,
            diagnostic_code=ROUTE_AUTH_REJECTED,
        )
    if status_code != 200:
        # Includes every 3xx, because redirects are disabled: a redirect is a
        # refusal to move this credential-bearing request, never a hop.
        return B300RouteObservation(
            reachable=True,
            configured_model_served=False,
            diagnostic_code=ROUTE_HTTP_REJECTED,
        )

    try:
        body = response.content
    except Exception:  # noqa: BLE001 - an unreadable body fails closed
        return B300RouteObservation(
            reachable=True,
            configured_model_served=False,
            diagnostic_code=ROUTE_LISTING_MALFORMED,
        )

    served_ids = _parse_bounded_model_listing(body)
    if served_ids is None:
        return B300RouteObservation(
            reachable=True,
            configured_model_served=False,
            diagnostic_code=ROUTE_LISTING_MALFORMED,
        )

    if _listing_contains_exact_model(served_ids, model_id):
        return B300RouteObservation(
            reachable=True,
            configured_model_served=True,
            diagnostic_code=ROUTE_MODEL_SERVED,
        )
    return B300RouteObservation(
        reachable=True,
        configured_model_served=False,
        diagnostic_code=ROUTE_MODEL_NOT_LISTED,
    )
