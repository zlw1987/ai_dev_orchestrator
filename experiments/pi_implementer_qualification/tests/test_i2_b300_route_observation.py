"""5F3B-I2B-L1-LF2 -- the authenticated, qualification-owned B300 route observation.

**NO REAL NETWORK.** Every request in this module is served by an
``httpx.MockTransport`` handler. No socket is opened, no DNS lookup is made,
no real credential is read, and no real endpoint is contacted. The
"credential" throughout is the synthetic literal :data:`SYNTHETIC_API_KEY`.

The offline matrix this module implements is LF2's own, items 1-19 (items
20-22, the controller-level shapes, live in ``test_i2b_controller.py``; the
attribution-collapse reproduction against the UNMODIFIED AR2 checker lives in
``test_i2_route.py``).
"""

from __future__ import annotations

import json

import httpx
import pytest

from qualification.i2_b300_route_observation import (
    B300_ROUTE_OBSERVATION_TIMEOUT_SECONDS,
    ROUTE_AUTH_REJECTED,
    ROUTE_DIAGNOSTIC_CODES,
    ROUTE_HTTP_REJECTED,
    ROUTE_LISTING_MALFORMED,
    ROUTE_MODEL_NOT_LISTED,
    ROUTE_MODEL_SERVED,
    ROUTE_NOT_OBSERVED,
    ROUTE_TRANSPORT_UNREACHABLE,
    B300RouteObservation,
    B300RouteObservationError,
    _listing_contains_exact_model,
    _open_route_client,
    _parse_bounded_model_listing,
    build_route_authorization_header,
    observe_b300_route_serves_model,
)

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
SYNTHETIC_API_KEY = "sk-synthetic-lf2-route-observation-key-0001"
CANDIDATE_A_MODEL = "qwen3-coder-next"
CANDIDATE_B_MODEL = "minimax-m2.7"


class _Recorder:
    """Captures every request an observation issues. Nothing is replayed."""

    def __init__(self, responder) -> None:
        self.requests: list[httpx.Request] = []
        self._responder = responder

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._responder(request)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def _listing(*model_ids: str) -> bytes:
    return json.dumps({"object": "list", "data": [{"id": mid} for mid in model_ids]}).encode()


def _json_response(status_code: int, body: bytes) -> httpx.Response:
    return httpx.Response(status_code, content=body, headers={"content-type": "application/json"})


def _observe(responder, *, model_id: str = CANDIDATE_A_MODEL, api_key: str = SYNTHETIC_API_KEY):
    recorder = _Recorder(responder)
    observation = observe_b300_route_serves_model(
        base_url=SYNTHETIC_BASE_URL,
        api_key=api_key,
        model_id=model_id,
        transport=recorder.transport,
    )
    return observation, recorder


# -- matrix 1: authenticated 200, exact model present -> PASS -----------------


def test_authenticated_200_with_exact_model_is_served() -> None:
    observation, recorder = _observe(
        lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL, CANDIDATE_B_MODEL))
    )
    assert observation.reachable is True
    assert observation.configured_model_served is True
    assert observation.diagnostic_code == ROUTE_MODEL_SERVED
    assert len(recorder.requests) == 1


def test_the_listing_path_is_models_under_the_given_base_url() -> None:
    _, recorder = _observe(lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)))
    assert str(recorder.requests[0].url) == "https://b300-proxy.example.invalid:8443/v1/models"
    assert recorder.requests[0].method == "GET"


def test_no_query_string_is_appended_to_the_listing_request() -> None:
    _, recorder = _observe(lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)))
    assert recorder.requests[0].url.query == b""


# -- matrix 2: authenticated 200, exact model absent -------------------------


def test_authenticated_200_without_the_exact_model_is_not_listed() -> None:
    observation, _ = _observe(lambda request: _json_response(200, _listing(CANDIDATE_B_MODEL)))
    assert observation.reachable is True
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_MODEL_NOT_LISTED


def test_an_empty_listing_is_not_listed_never_malformed() -> None:
    observation, _ = _observe(lambda request: _json_response(200, _listing()))
    assert observation.diagnostic_code == ROUTE_MODEL_NOT_LISTED


# -- matrix 3/4: 401 and 403 -> AUTH_REJECTED, never "model absent" ----------


@pytest.mark.parametrize("status_code", [401, 403])
def test_auth_status_is_classified_as_auth_rejection(status_code: int) -> None:
    observation, _ = _observe(lambda request: httpx.Response(status_code, content=b"denied"))
    assert observation.reachable is True
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_AUTH_REJECTED
    # THE POINT OF LF2: an auth rejection is never the "model absent" code.
    assert observation.diagnostic_code != ROUTE_MODEL_NOT_LISTED


@pytest.mark.parametrize("status_code", [401, 403])
def test_auth_rejection_even_when_the_body_lists_the_model(status_code: int) -> None:
    """A non-200 is never parsed, so a body cannot manufacture a match."""
    observation, _ = _observe(
        lambda request: _json_response(status_code, _listing(CANDIDATE_A_MODEL))
    )
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_AUTH_REJECTED


# -- matrix 5: another non-200 -> HTTP_REJECTED ------------------------------


@pytest.mark.parametrize("status_code", [400, 404, 429, 500, 502, 503])
def test_other_non_200_status_is_http_rejected(status_code: int) -> None:
    observation, _ = _observe(lambda request: httpx.Response(status_code, content=b"nope"))
    assert observation.reachable is True
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_HTTP_REJECTED


# -- matrix 6: transport exception -> TRANSPORT_UNREACHABLE ------------------


def _raise_connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("synthetic connect failure", request=request)


def test_transport_exception_is_unreachable() -> None:
    observation, _ = _observe(_raise_connect_error)
    assert observation.reachable is False
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_TRANSPORT_UNREACHABLE


def test_timeout_is_unreachable_not_model_absent() -> None:
    def _raise_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic read timeout", request=request)

    observation, _ = _observe(_raise_timeout)
    assert observation.diagnostic_code == ROUTE_TRANSPORT_UNREACHABLE
    assert observation.diagnostic_code != ROUTE_MODEL_NOT_LISTED


# -- matrix 7/8/9: malformed listings ----------------------------------------


def test_malformed_json_is_listing_malformed() -> None:
    observation, _ = _observe(lambda request: _json_response(200, b"{not json at all"))
    assert observation.reachable is True
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_LISTING_MALFORMED


@pytest.mark.parametrize("payload", [b"[]", b'"a string"', b"42", b"null", b"true"])
def test_non_object_payload_is_listing_malformed(payload: bytes) -> None:
    observation, _ = _observe(lambda request: _json_response(200, payload))
    assert observation.diagnostic_code == ROUTE_LISTING_MALFORMED


@pytest.mark.parametrize(
    "payload",
    [
        b'{"object": "list"}',
        b'{"data": null}',
        b'{"data": "qwen3-coder-next"}',
        b'{"data": {"id": "qwen3-coder-next"}}',
    ],
)
def test_data_not_a_list_is_listing_malformed(payload: bytes) -> None:
    observation, _ = _observe(lambda request: _json_response(200, payload))
    assert observation.diagnostic_code == ROUTE_LISTING_MALFORMED


def test_a_malformed_listing_is_never_reported_as_model_absent() -> None:
    observation, _ = _observe(lambda request: _json_response(200, b"<html>gateway</html>"))
    assert observation.diagnostic_code == ROUTE_LISTING_MALFORMED
    assert observation.diagnostic_code != ROUTE_MODEL_NOT_LISTED


# -- matrix 10: malformed entries cannot manufacture an exact match ----------


@pytest.mark.parametrize(
    "data",
    [
        [{"id": None}],
        [{"id": 1234}],
        [{"id": ["qwen3-coder-next"]}],
        [{"id": {"value": "qwen3-coder-next"}}],
        [{"name": "qwen3-coder-next"}],
        [{"id": ""}],
        ["qwen3-coder-next"],
        [None],
        [["qwen3-coder-next"]],
    ],
)
def test_malformed_entries_fail_closed_and_never_match(data: list) -> None:
    observation, _ = _observe(lambda request: _json_response(200, json.dumps({"data": data}).encode()))
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_LISTING_MALFORMED


def test_a_malformed_entry_beside_the_real_model_still_fails_closed() -> None:
    """Strict: an entry AIDO cannot understand invalidates the whole listing.

    A listing that cannot be fully understood must not be allowed to produce
    a match -- nor a confident non-match.
    """
    payload = json.dumps({"data": [{"id": CANDIDATE_A_MODEL}, {"id": 7}]}).encode()
    observation, _ = _observe(lambda request: _json_response(200, payload))
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_LISTING_MALFORMED


def test_an_object_shaped_like_a_match_cannot_stringify_into_one() -> None:
    """AR2's checker used ``str(entry.get("id"))``; this one requires a real str."""
    assert _parse_bounded_model_listing(json.dumps({"data": [{"id": 3}]}).encode()) is None


# -- matrix 11: case sensitivity ---------------------------------------------


@pytest.mark.parametrize(
    "served",
    ["QWEN3-CODER-NEXT", "Qwen3-Coder-Next", "qwen3-Coder-next", "QWEN3-coder-NEXT"],
)
def test_case_mismatch_never_matches(served: str) -> None:
    observation, _ = _observe(lambda request: _json_response(200, _listing(served)))
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_MODEL_NOT_LISTED


@pytest.mark.parametrize(
    "served",
    ["qwen3-coder-next-v2", "qwen3-coder", "b300/qwen3-coder-next", " qwen3-coder-next"],
)
def test_prefix_suffix_and_namespaced_ids_never_match(served: str) -> None:
    observation, _ = _observe(lambda request: _json_response(200, _listing(served)))
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_MODEL_NOT_LISTED


# -- matrix 12: duplicates are harmless, and matching is not set-based -------


def test_duplicate_model_ids_are_harmless_when_present() -> None:
    observation, _ = _observe(
        lambda request: _json_response(
            200, _listing(CANDIDATE_A_MODEL, CANDIDATE_A_MODEL, CANDIDATE_B_MODEL)
        )
    )
    assert observation.configured_model_served is True
    assert observation.diagnostic_code == ROUTE_MODEL_SERVED


def test_duplicate_model_ids_are_harmless_when_absent() -> None:
    observation, _ = _observe(
        lambda request: _json_response(200, _listing(CANDIDATE_B_MODEL, CANDIDATE_B_MODEL))
    )
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_MODEL_NOT_LISTED


def test_matching_is_equality_per_entry_not_set_membership() -> None:
    assert _listing_contains_exact_model((CANDIDATE_B_MODEL,) * 5, CANDIDATE_A_MODEL) is False
    assert _listing_contains_exact_model((CANDIDATE_A_MODEL,) * 5, CANDIDATE_A_MODEL) is True
    assert _listing_contains_exact_model((), CANDIDATE_A_MODEL) is False


# -- matrix 13: the Authorization header, exactly once -----------------------


def test_authorization_header_carries_the_synthetic_credential_exactly_once() -> None:
    _, recorder = _observe(lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)))
    assert len(recorder.requests) == 1
    assert recorder.requests[0].headers["Authorization"] == f"Bearer {SYNTHETIC_API_KEY}"


def test_the_header_shape_is_bearer() -> None:
    assert build_route_authorization_header(SYNTHETIC_API_KEY) == f"Bearer {SYNTHETIC_API_KEY}"


@pytest.mark.parametrize("bad", ["", "   ", None, 1234, b"bytes-key"])
def test_a_missing_or_blank_credential_is_refused_before_any_request(bad) -> None:
    recorder = _Recorder(lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)))
    with pytest.raises(B300RouteObservationError) as excinfo:
        observe_b300_route_serves_model(
            base_url=SYNTHETIC_BASE_URL,
            api_key=bad,
            model_id=CANDIDATE_A_MODEL,
            transport=recorder.transport,
        )
    assert recorder.requests == []
    assert str(bad) not in str(excinfo.value) or not str(bad).strip()


def test_the_request_carries_no_second_credential_bearing_header() -> None:
    _, recorder = _observe(lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)))
    header_names = {name.lower() for name in recorder.requests[0].headers}
    assert "cookie" not in header_names
    assert "proxy-authorization" not in header_names
    assert "x-api-key" not in header_names


# -- matrix 14: the credential never survives into anything retained ---------


_NEEDLES = (SYNTHETIC_API_KEY, "Bearer", "b300-proxy.example.invalid", SYNTHETIC_BASE_URL)


def _assert_no_needles(text: str) -> None:
    for needle in _NEEDLES:
        assert needle not in text, f"{needle!r} survived into: {text!r}"


@pytest.mark.parametrize(
    "responder",
    [
        lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)),
        lambda request: _json_response(200, _listing(CANDIDATE_B_MODEL)),
        lambda request: httpx.Response(401, content=b"denied"),
        lambda request: httpx.Response(500, content=b"boom"),
        lambda request: _json_response(200, b"{not json"),
        _raise_connect_error,
    ],
)
def test_no_credential_endpoint_or_body_survives_in_the_observation(responder) -> None:
    observation, _ = _observe(responder)
    _assert_no_needles(repr(observation))
    _assert_no_needles(json.dumps(observation.as_dict()))
    _assert_no_needles(str(observation.as_dict()))


def test_the_retained_record_omits_status_body_and_served_ids() -> None:
    observation, _ = _observe(lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)))
    record = observation.as_dict()
    assert record["status_code_recorded"] is False
    assert record["served_model_ids_recorded"] is False
    assert record["response_body_recorded"] is False
    assert record["endpoint_host_recorded"] is False
    assert record["base_url_recorded"] is False
    assert record["credential_recorded"] is False
    assert record["redirects_followed"] is False
    assert record["is_a_semantic_prompt"] is False
    assert record["tokens_generated"] == 0
    # No field anywhere holds a number that could be an HTTP status.
    assert "status_code" not in record
    assert "served_model_ids" not in record
    assert "failure" not in record


def test_a_secret_bearing_response_body_never_reaches_the_observation() -> None:
    leaky = json.dumps(
        {"data": [{"id": CANDIDATE_A_MODEL, "note": f"Authorization: Bearer {SYNTHETIC_API_KEY}"}]}
    ).encode()
    observation, _ = _observe(lambda request: _json_response(200, leaky))
    assert observation.configured_model_served is True
    _assert_no_needles(repr(observation))
    _assert_no_needles(json.dumps(observation.as_dict()))


def test_a_transport_exception_message_never_reaches_the_observation() -> None:
    def _leaky_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"failed connecting to {SYNTHETIC_BASE_URL} with Bearer {SYNTHETIC_API_KEY}",
            request=request,
        )

    observation, _ = _observe(_leaky_error)
    assert observation.diagnostic_code == ROUTE_TRANSPORT_UNREACHABLE
    _assert_no_needles(repr(observation))
    _assert_no_needles(json.dumps(observation.as_dict()))


# -- matrix 15/16/17/18: transport policy, no retry, no second endpoint ------


def test_trust_env_is_false_and_redirects_are_disabled() -> None:
    """Mechanically asserted on the real client object, not read from a docstring."""
    with _open_route_client() as client:
        assert client.trust_env is False
        assert client.follow_redirects is False
    with _open_route_client(httpx.MockTransport(lambda r: httpx.Response(200))) as client:
        assert client.trust_env is False
        assert client.follow_redirects is False


def test_a_redirect_is_refused_and_never_followed() -> None:
    """REDIRECT POLICY: a 3xx is a non-200, never a hop for a credentialed request."""
    responses = [
        httpx.Response(302, headers={"location": "https://elsewhere.example.invalid/v1/models"}),
        _json_response(200, _listing(CANDIDATE_A_MODEL)),
    ]

    def _redirecting(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    observation, recorder = _observe(_redirecting)
    assert observation.configured_model_served is False
    assert observation.diagnostic_code == ROUTE_HTTP_REJECTED
    # Exactly one request: the redirect target was never contacted, so the
    # credential never reached an authority this run did not approve.
    assert len(recorder.requests) == 1
    assert str(recorder.requests[0].url).startswith(SYNTHETIC_BASE_URL)


@pytest.mark.parametrize("status_code", [301, 302, 303, 307, 308])
def test_every_redirect_status_is_refused(status_code: int) -> None:
    observation, recorder = _observe(
        lambda request: httpx.Response(
            status_code, headers={"location": "https://elsewhere.example.invalid/v1/models"}
        )
    )
    assert observation.diagnostic_code == ROUTE_HTTP_REJECTED
    assert len(recorder.requests) == 1


@pytest.mark.parametrize(
    "responder",
    [
        _raise_connect_error,
        lambda request: httpx.Response(500),
        lambda request: httpx.Response(429),
        lambda request: httpx.Response(401),
        lambda request: _json_response(200, b"{not json"),
        lambda request: _json_response(200, _listing(CANDIDATE_B_MODEL)),
    ],
)
def test_no_retry_and_no_fallback_endpoint_on_any_failure(responder) -> None:
    """Exactly one request on every path -- no retry, no second endpoint."""
    recorder = _Recorder(responder)
    try:
        observe_b300_route_serves_model(
            base_url=SYNTHETIC_BASE_URL,
            api_key=SYNTHETIC_API_KEY,
            model_id=CANDIDATE_A_MODEL,
            transport=recorder.transport,
        )
    except B300RouteObservationError:  # pragma: no cover - none of these refuse
        pass
    assert len(recorder.requests) == 1


def test_no_fallback_model_is_ever_requested() -> None:
    """The absent-model path issues no second request for another model."""
    observation, recorder = _observe(lambda request: _json_response(200, _listing("some-other-id")))
    assert observation.diagnostic_code == ROUTE_MODEL_NOT_LISTED
    assert len(recorder.requests) == 1
    assert CANDIDATE_B_MODEL not in str(recorder.requests[0].url)


# -- matrix 19: nothing prompt-shaped ----------------------------------------


def test_the_request_is_a_bare_get_with_no_prompt_shaped_body() -> None:
    _, recorder = _observe(lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)))
    request = recorder.requests[0]
    assert request.method == "GET"
    assert request.content == b""
    assert not str(request.url).endswith("/chat/completions")
    assert "/completions" not in str(request.url)
    body_text = request.content.decode()
    for prompt_token in ("messages", "prompt", "model", "temperature", "max_tokens"):
        assert prompt_token not in body_text


def test_the_observation_declares_itself_a_non_semantic_check() -> None:
    observation, _ = _observe(lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)))
    record = observation.as_dict()
    assert record["check"] == "authenticated_non_inference_model_listing"
    assert record["is_a_semantic_prompt"] is False
    assert record["tokens_generated"] == 0
    assert record["requests_issued"] == 1


def test_the_wait_is_bounded() -> None:
    assert B300_ROUTE_OBSERVATION_TIMEOUT_SECONDS > 0
    assert B300_ROUTE_OBSERVATION_TIMEOUT_SECONDS <= 60


# -- the observation type cannot express an impossible state -----------------


def test_every_produced_diagnostic_is_a_declared_code() -> None:
    for responder in (
        lambda request: _json_response(200, _listing(CANDIDATE_A_MODEL)),
        lambda request: _json_response(200, _listing(CANDIDATE_B_MODEL)),
        lambda request: httpx.Response(401),
        lambda request: httpx.Response(403),
        lambda request: httpx.Response(500),
        lambda request: _json_response(200, b"{"),
        _raise_connect_error,
    ):
        observation, _ = _observe(responder)
        assert observation.diagnostic_code in ROUTE_DIAGNOSTIC_CODES


def test_success_requires_the_served_diagnostic() -> None:
    with pytest.raises(B300RouteObservationError):
        B300RouteObservation(
            reachable=True, configured_model_served=True, diagnostic_code=ROUTE_MODEL_NOT_LISTED
        )


def test_the_served_diagnostic_requires_success() -> None:
    with pytest.raises(B300RouteObservationError):
        B300RouteObservation(
            reachable=True, configured_model_served=False, diagnostic_code=ROUTE_MODEL_SERVED
        )


def test_success_requires_reachable() -> None:
    with pytest.raises(B300RouteObservationError):
        B300RouteObservation(
            reachable=False, configured_model_served=True, diagnostic_code=ROUTE_MODEL_SERVED
        )


@pytest.mark.parametrize("value", ["true", "false", 1, 0, None, [], "1"])
def test_non_bool_fields_are_refused(value) -> None:
    with pytest.raises(B300RouteObservationError):
        B300RouteObservation(
            reachable=value, configured_model_served=False, diagnostic_code=ROUTE_HTTP_REJECTED
        )
    with pytest.raises(B300RouteObservationError):
        B300RouteObservation(
            reachable=True, configured_model_served=value, diagnostic_code=ROUTE_HTTP_REJECTED
        )


def test_an_undeclared_diagnostic_code_is_refused() -> None:
    with pytest.raises(B300RouteObservationError):
        B300RouteObservation(
            reachable=True, configured_model_served=False, diagnostic_code="model_probably_missing"
        )


def test_route_not_observed_can_never_be_an_observation() -> None:
    """It describes the ABSENCE of an observation, so it cannot be one."""
    with pytest.raises(B300RouteObservationError):
        B300RouteObservation(
            reachable=False, configured_model_served=False, diagnostic_code=ROUTE_NOT_OBSERVED
        )


# -- bounded listing shape ----------------------------------------------------


def test_an_oversized_body_is_refused_as_malformed() -> None:
    from qualification.i2_b300_route_observation import _MAX_LISTING_BYTES

    assert _parse_bounded_model_listing(b"x" * (_MAX_LISTING_BYTES + 1)) is None


def test_too_many_entries_is_refused_as_malformed() -> None:
    from qualification.i2_b300_route_observation import _MAX_LISTING_ENTRIES

    data = [{"id": f"model-{index}"} for index in range(_MAX_LISTING_ENTRIES + 1)]
    assert _parse_bounded_model_listing(json.dumps({"data": data}).encode()) is None


def test_an_overlong_model_id_is_refused_as_malformed() -> None:
    from qualification.i2_b300_route_observation import _MAX_MODEL_ID_LENGTH

    data = [{"id": "m" * (_MAX_MODEL_ID_LENGTH + 1)}]
    assert _parse_bounded_model_listing(json.dumps({"data": data}).encode()) is None


def test_a_valid_bounded_listing_parses_to_its_exact_ids() -> None:
    parsed = _parse_bounded_model_listing(_listing(CANDIDATE_A_MODEL, CANDIDATE_B_MODEL))
    assert parsed == (CANDIDATE_A_MODEL, CANDIDATE_B_MODEL)


# -- this module never imports or reuses the frozen AR2 checker --------------


def test_this_module_does_not_reuse_the_frozen_ar2_checker() -> None:
    """Asserted against the parsed IMPORTS, not the prose.

    The module docstring names ``ar2.route_check`` deliberately, to record why
    it is not reused; what must be true is that no ``ar2`` symbol is actually
    imported or bound here.
    """
    import ast
    import inspect

    import qualification.i2_b300_route_observation as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(alias.name for alias in node.names)
    assert not any(name.startswith("ar2") for name in imported), imported
    assert "check_route_serves_model" not in imported
    assert not hasattr(module, "check_route_serves_model")
    assert not hasattr(module, "ar2")


def test_the_frozen_ar2_checker_still_sends_no_authorization_header() -> None:
    """The premise of LF2, asserted rather than assumed -- and AR2 stays frozen."""
    import inspect

    from ar2 import route_check

    source = inspect.getsource(route_check)
    assert "Authorization" not in source
    assert "api_key" not in source
    assert "headers=" not in source
