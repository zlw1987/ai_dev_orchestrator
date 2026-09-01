"""I2-3 -- route descriptors and offline route-check wiring (I2A Sec. 15/19/20).

The route-check wiring is exercised ONLY through an injected synthetic
checker. No real ``ar2.route_check.check_route_serves_model`` call, no HTTP
request, and no socket is ever made by this test module.

**5F3B-I2-FU3.** ``run_offline_route_check`` no longer takes a raw
``base_url: str`` -- it consumes an already-valid
``QualificationRouteSecretContext``. The checker's result booleans must be
exact ``bool``; anything else (a string, an int) fails closed. An exception
the checker raises is bounded and never retained.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from qualification.i2_route import (
    BACKEND_GATEWAY_CLASS,
    CREDENTIAL_MECHANISM,
    RouteCheckOutcome,
    RouteDescriptor,
    RouteDescriptorError,
    RouteFailureCode,
    route_descriptor_for_candidate,
    run_offline_route_check,
    validate_candidate_model_pairing,
)
from qualification.i2_secret_context import build_secret_context
from qualification.records import CANDIDATE_MODEL_IDS

VALID_DESCRIPTOR_KWARGS = dict(
    candidate="A",
    model_id="qwen3-coder-next",
    provider_id="b300_pi_qualification",
    backend_gateway_class="b300_litellm_proxy",
    credential_mechanism="models_json_env_interpolation",
    credential_env_var_name="PI_QUALIFICATION_B300_ROUTE_KEY",
)

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
SYNTHETIC_API_KEY = "sk-synthetic-route-check-key-0001"


def _secret_context(model_id: str = "qwen3-coder-next"):
    return build_secret_context(
        base_url=SYNTHETIC_BASE_URL, api_key=SYNTHETIC_API_KEY, model_id=model_id
    )


# -- exact A/B mapping --------------------------------------------------------


def test_candidate_a_route_descriptor():
    descriptor = route_descriptor_for_candidate("A")
    assert descriptor.candidate == "A"
    assert descriptor.model_id == "qwen3-coder-next"
    assert descriptor.model_id == CANDIDATE_MODEL_IDS["A"]


def test_candidate_b_route_descriptor():
    descriptor = route_descriptor_for_candidate("B")
    assert descriptor.candidate == "B"
    assert descriptor.model_id == "minimax-m2.7"
    assert descriptor.model_id == CANDIDATE_MODEL_IDS["B"]


def test_unknown_candidate_refused():
    with pytest.raises(RouteDescriptorError):
        route_descriptor_for_candidate("C")


def test_reversed_model_candidate_pairing_refused():
    with pytest.raises(RouteDescriptorError):
        validate_candidate_model_pairing("A", "minimax-m2.7")
    with pytest.raises(RouteDescriptorError):
        validate_candidate_model_pairing("B", "qwen3-coder-next")


def test_correct_pairing_accepted():
    validate_candidate_model_pairing("A", "qwen3-coder-next")
    validate_candidate_model_pairing("B", "minimax-m2.7")


def test_unknown_candidate_pairing_refused():
    with pytest.raises(RouteDescriptorError):
        validate_candidate_model_pairing("Z", "qwen3-coder-next")


# -- never direct-vLLM; same policy for both candidates -----------------------


def test_backend_gateway_class_is_b300_litellm_proxy_never_direct_vllm():
    for candidate in ("A", "B"):
        descriptor = route_descriptor_for_candidate(candidate)
        assert descriptor.backend_gateway_class == BACKEND_GATEWAY_CLASS
        assert descriptor.backend_gateway_class == "b300_litellm_proxy"
        assert "vllm" not in descriptor.backend_gateway_class.lower()


def test_candidate_symmetry_beyond_model_identity():
    a = route_descriptor_for_candidate("A")
    b = route_descriptor_for_candidate("B")
    assert a.provider_id == b.provider_id
    assert a.backend_gateway_class == b.backend_gateway_class
    assert a.credential_mechanism == b.credential_mechanism
    assert a.credential_env_var_name == b.credential_env_var_name
    assert a.model_id != b.model_id
    assert a.credential_mechanism == CREDENTIAL_MECHANISM


# -- offline route-check wiring -----------------------------------------------


@dataclass(frozen=True)
class _FakeRouteModelCheck:
    reachable: object
    configured_model_served: object
    failure: str | None = None


def test_injected_checker_receives_exact_model_id_no_fallback():
    seen = {}

    def checker(base_url, *, model_id):
        seen["base_url"] = base_url
        seen["model_id"] = model_id
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    descriptor = route_descriptor_for_candidate("A")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=checker
    )
    assert seen["base_url"] == SYNTHETIC_BASE_URL
    assert seen["model_id"] == "qwen3-coder-next"
    assert outcome.passed is True


def test_unreachable_fails_closed():
    def checker(base_url, *, model_id):
        return _FakeRouteModelCheck(
            reachable=False, configured_model_served=False, failure="route unreachable"
        )

    descriptor = route_descriptor_for_candidate("A")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=checker
    )
    assert outcome.passed is False
    assert outcome.reachable is False
    assert outcome.failure_code == RouteFailureCode.ROUTE_UNREACHABLE


def test_reachable_but_wrong_model_fails_closed_no_fallback():
    def checker(base_url, *, model_id):
        # Reachable, but the served catalog does not include the configured id.
        return _FakeRouteModelCheck(
            reachable=True,
            configured_model_served=False,
            failure="the configured model id is not among the ids this route serves",
        )

    descriptor = route_descriptor_for_candidate("B")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context("minimax-m2.7"), checker=checker
    )
    assert outcome.passed is False
    assert outcome.reachable is True
    assert outcome.configured_model_served is False
    assert outcome.failure_code == RouteFailureCode.MODEL_NOT_SERVED


# -- 5F3B-I2-FU1: raw checker failure text is never read/retained (regression F)


SYNTHETIC_ENDPOINT_NEEDLE = "https://internal-b300.example.invalid:8443/v1"
SYNTHETIC_API_KEY_NEEDLE = "sk-synthetic-should-never-survive-route-check"
SYNTHETIC_AUTH_HEADER_NEEDLE = f"Authorization: Bearer {SYNTHETIC_API_KEY_NEEDLE}"


def test_raw_checker_failure_text_never_survives_in_outcome():
    hostile_failure_text = (
        f"connection to {SYNTHETIC_ENDPOINT_NEEDLE} failed; sent "
        f"'{SYNTHETIC_AUTH_HEADER_NEEDLE}'"
    )

    def checker(base_url, *, model_id):
        return _FakeRouteModelCheck(
            reachable=False, configured_model_served=False, failure=hostile_failure_text
        )

    descriptor = route_descriptor_for_candidate("A")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=checker
    )

    for needle in (
        hostile_failure_text,
        SYNTHETIC_ENDPOINT_NEEDLE,
        SYNTHETIC_API_KEY_NEEDLE,
        SYNTHETIC_AUTH_HEADER_NEEDLE,
        "Authorization",
        "Bearer",
    ):
        assert needle not in repr(outcome)
        assert needle not in str(outcome)
    assert not hasattr(outcome, "failure")
    assert outcome.failure_code == RouteFailureCode.ROUTE_UNREACHABLE


def test_raw_checker_failure_text_never_survives_for_wrong_model_case():
    hostile_failure_text = (
        f"model not served on {SYNTHETIC_ENDPOINT_NEEDLE} with key "
        f"{SYNTHETIC_API_KEY_NEEDLE}"
    )

    def checker(base_url, *, model_id):
        return _FakeRouteModelCheck(
            reachable=True, configured_model_served=False, failure=hostile_failure_text
        )

    descriptor = route_descriptor_for_candidate("B")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context("minimax-m2.7"), checker=checker
    )

    for needle in (hostile_failure_text, SYNTHETIC_ENDPOINT_NEEDLE, SYNTHETIC_API_KEY_NEEDLE):
        assert needle not in repr(outcome)
        assert needle not in str(outcome)
    assert outcome.failure_code == RouteFailureCode.MODEL_NOT_SERVED


def test_same_wiring_policy_for_both_candidates():
    def checker(base_url, *, model_id):
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    for candidate, model_id in (("A", "qwen3-coder-next"), ("B", "minimax-m2.7")):
        descriptor = route_descriptor_for_candidate(candidate)
        outcome = run_offline_route_check(
            descriptor=descriptor, secret_context=_secret_context(model_id), checker=checker
        )
        assert outcome.passed is True


# -- 5F3B-I2-FU2 item C: RouteDescriptor valid by construction, and at use
# (required regression 3) -----------------------------------------------------


def test_valid_direct_construction_is_accepted():
    descriptor = RouteDescriptor(**VALID_DESCRIPTOR_KWARGS)
    assert descriptor.model_id == "qwen3-coder-next"


def test_forged_model_id_rejected():
    kwargs = dict(VALID_DESCRIPTOR_KWARGS, model_id="evil-model")
    with pytest.raises(RouteDescriptorError):
        RouteDescriptor(**kwargs)


def test_forged_provider_id_rejected():
    kwargs = dict(VALID_DESCRIPTOR_KWARGS, provider_id="evil")
    with pytest.raises(RouteDescriptorError):
        RouteDescriptor(**kwargs)


def test_direct_vllm_backend_gateway_class_rejected():
    kwargs = dict(VALID_DESCRIPTOR_KWARGS, backend_gateway_class="direct_vllm")
    with pytest.raises(RouteDescriptorError):
        RouteDescriptor(**kwargs)


def test_forged_credential_mechanism_rejected():
    kwargs = dict(VALID_DESCRIPTOR_KWARGS, credential_mechanism="evil")
    with pytest.raises(RouteDescriptorError):
        RouteDescriptor(**kwargs)


def test_forged_credential_carrier_rejected():
    kwargs = dict(VALID_DESCRIPTOR_KWARGS, credential_env_var_name="OPENAI_API_KEY")
    with pytest.raises(RouteDescriptorError):
        RouteDescriptor(**kwargs)


def test_reversed_ab_pairing_rejected_at_construction():
    kwargs = dict(VALID_DESCRIPTOR_KWARGS, candidate="B")  # model_id still Candidate A's
    with pytest.raises(RouteDescriptorError):
        RouteDescriptor(**kwargs)


def test_forged_descriptor_never_reaches_checker_via_normal_construction():
    # The independent-review counterexample itself: this forged descriptor
    # can never even be built, so it never has a chance to reach the checker.
    checker_calls = {"count": 0}

    def checker(base_url, *, model_id):  # pragma: no cover - must not run
        checker_calls["count"] += 1
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    with pytest.raises(RouteDescriptorError):
        RouteDescriptor(
            candidate="A",
            model_id="evil-model",
            provider_id="evil",
            backend_gateway_class="direct_vllm",
            credential_mechanism="evil",
            credential_env_var_name="OPENAI_API_KEY",
        )
    assert checker_calls["count"] == 0


def test_forged_descriptor_bypassing_post_init_still_refused_at_consumption_boundary():
    # Defense in depth: a descriptor that reached this function through some
    # path OTHER than its own constructor (simulated here via object.__new__,
    # which skips __post_init__) must still be refused BEFORE the checker
    # runs -- proving run_offline_route_check's own revalidation, not just
    # RouteDescriptor.__post_init__, is what stops it.
    forged = object.__new__(RouteDescriptor)
    object.__setattr__(forged, "candidate", "A")
    object.__setattr__(forged, "model_id", "evil-model")
    object.__setattr__(forged, "provider_id", "evil")
    object.__setattr__(forged, "backend_gateway_class", "direct_vllm")
    object.__setattr__(forged, "credential_mechanism", "evil")
    object.__setattr__(forged, "credential_env_var_name", "OPENAI_API_KEY")

    checker_calls = {"count": 0}

    def checker(base_url, *, model_id):  # pragma: no cover - must not run
        checker_calls["count"] += 1
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    with pytest.raises(RouteDescriptorError):
        run_offline_route_check(
            descriptor=forged, secret_context=_secret_context(), checker=checker
        )
    assert checker_calls["count"] == 0


# -- 5F3B-I2-FU2 item G: unexpected route-check exceptions are bounded --------
# (required regression: route-check exception sanitization)


def test_checker_exception_is_bounded_and_needles_never_survive():
    hostile_exception_text = (
        "https://internal-b300.example.invalid Authorization: Bearer sk-synthetic-secret"
    )

    def raising_checker(base_url, *, model_id):
        raise RuntimeError(hostile_exception_text)

    descriptor = route_descriptor_for_candidate("A")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=raising_checker
    )

    assert outcome.passed is False
    assert outcome.failure_code == RouteFailureCode.ROUTE_CHECK_ERROR
    for needle in (
        hostile_exception_text,
        "internal-b300.example.invalid",
        "sk-synthetic-secret",
        "Authorization",
        "Bearer",
        "RuntimeError",
    ):
        assert needle not in repr(outcome)
        assert needle not in str(outcome)


def test_checker_exception_of_various_types_is_bounded():
    for exc_type, message in (
        (ValueError, "bad value at https://host/v1"),
        (ConnectionError, "connection reset by sk-synthetic-peer"),
        (TimeoutError, "timed out talking to endpoint.example.invalid"),
    ):

        def raising_checker(base_url, *, model_id, _exc=exc_type, _msg=message):
            raise _exc(_msg)

        descriptor = route_descriptor_for_candidate("B")
        outcome = run_offline_route_check(
            descriptor=descriptor,
            secret_context=_secret_context("minimax-m2.7"),
            checker=raising_checker,
        )
        assert outcome.passed is False
        assert outcome.failure_code == RouteFailureCode.ROUTE_CHECK_ERROR
        assert message not in repr(outcome)


def test_no_fallback_model_on_checker_exception():
    seen_model_ids = []

    def raising_checker(base_url, *, model_id):
        seen_model_ids.append(model_id)
        raise RuntimeError("boom")

    descriptor = route_descriptor_for_candidate("A")
    run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=raising_checker
    )
    assert seen_model_ids == ["qwen3-coder-next"]


# -- 5F3B-I2-FU3 item 7: route input is a trusted object (required regression 8)


def test_run_offline_route_check_has_no_raw_base_url_parameter():
    import inspect

    signature = inspect.signature(run_offline_route_check)
    assert "base_url" not in signature.parameters
    assert set(signature.parameters) == {"descriptor", "secret_context", "checker"}


def test_malformed_base_url_never_reaches_checker():
    # A QualificationRouteSecretContext can never hold "not-a-url" -- its
    # own __post_init__ already refuses it, so the checker is unreachable.
    from qualification.i2_secret_context import InvalidBaseUrlError

    checker_calls = {"count": 0}

    def checker(base_url, *, model_id):  # pragma: no cover - must not run
        checker_calls["count"] += 1
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    with pytest.raises(InvalidBaseUrlError):
        build_secret_context(base_url="not-a-url", api_key=SYNTHETIC_API_KEY, model_id="qwen3-coder-next")
    assert checker_calls["count"] == 0


def test_forged_secret_context_bypassing_post_init_still_refused_before_checker():
    from qualification.i2_secret_context import QualificationRouteSecretContext

    forged = object.__new__(QualificationRouteSecretContext)
    object.__setattr__(forged, "base_url", "not-a-url")
    object.__setattr__(forged, "api_key", SYNTHETIC_API_KEY)
    object.__setattr__(forged, "endpoint_host", "<unparsed>")
    object.__setattr__(forged, "credential_env_var_name", "PI_QUALIFICATION_B300_ROUTE_KEY")
    object.__setattr__(forged, "provider_id", "b300_pi_qualification")
    object.__setattr__(forged, "model_id", "qwen3-coder-next")

    checker_calls = {"count": 0}

    def checker(base_url, *, model_id):  # pragma: no cover - must not run
        checker_calls["count"] += 1
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    descriptor = route_descriptor_for_candidate("A")
    from qualification.i2_secret_context import InvalidBaseUrlError

    with pytest.raises(InvalidBaseUrlError):
        run_offline_route_check(descriptor=descriptor, secret_context=forged, checker=checker)
    assert checker_calls["count"] == 0


def test_no_second_url_validator_was_added():
    import qualification.i2_route as route_mod
    from qualification.i2_secret_context import validate_b300_base_url

    assert route_mod.validate_b300_base_url is validate_b300_base_url


# -- 5F3B-I2-FU3 item 8: exact-bool checker result typing (required regressions
# 9 and 10) --------------------------------------------------------------------


def test_string_false_reachable_and_served_fail_closed_never_pass():
    def checker(base_url, *, model_id):
        return _FakeRouteModelCheck(reachable="false", configured_model_served="false")

    descriptor = route_descriptor_for_candidate("A")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=checker
    )
    assert outcome.passed is False
    assert outcome.failure_code == RouteFailureCode.ROUTE_CHECK_INVALID_RESULT


def test_integer_1_0_reachable_and_served_fail_closed():
    def checker(base_url, *, model_id):
        return _FakeRouteModelCheck(reachable=1, configured_model_served=0)

    descriptor = route_descriptor_for_candidate("A")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=checker
    )
    assert outcome.passed is False
    assert outcome.failure_code == RouteFailureCode.ROUTE_CHECK_INVALID_RESULT


def test_only_one_field_non_bool_still_fails_closed():
    def checker(base_url, *, model_id):
        return _FakeRouteModelCheck(reachable=True, configured_model_served="true")

    descriptor = route_descriptor_for_candidate("A")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=checker
    )
    assert outcome.passed is False
    assert outcome.failure_code == RouteFailureCode.ROUTE_CHECK_INVALID_RESULT


def test_missing_result_attributes_fail_closed():
    class _Empty:
        pass

    def checker(base_url, *, model_id):
        return _Empty()

    descriptor = route_descriptor_for_candidate("A")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=checker
    )
    assert outcome.passed is False
    assert outcome.failure_code == RouteFailureCode.ROUTE_CHECK_INVALID_RESULT


def test_genuine_bool_true_true_still_passes():
    def checker(base_url, *, model_id):
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    descriptor = route_descriptor_for_candidate("A")
    outcome = run_offline_route_check(
        descriptor=descriptor, secret_context=_secret_context(), checker=checker
    )
    assert outcome.passed is True


# -- 5F3B-I2-FU3 item 8: RouteCheckOutcome cannot express an impossible state -


def test_route_check_outcome_rejects_non_bool_passed():
    with pytest.raises(ValueError):
        RouteCheckOutcome(
            passed="false", reachable=True, configured_model_served=True, failure_code=None
        )


def test_route_check_outcome_rejects_non_bool_reachable():
    with pytest.raises(ValueError):
        RouteCheckOutcome(
            passed=False,
            reachable=1,
            configured_model_served=False,
            failure_code=RouteFailureCode.ROUTE_UNREACHABLE,
        )


def test_route_check_outcome_rejects_passed_true_without_both_booleans_true():
    with pytest.raises(ValueError):
        RouteCheckOutcome(
            passed=True, reachable=True, configured_model_served=False, failure_code=None
        )


def test_route_check_outcome_rejects_passed_true_with_failure_code():
    with pytest.raises(ValueError):
        RouteCheckOutcome(
            passed=True,
            reachable=True,
            configured_model_served=True,
            failure_code=RouteFailureCode.ROUTE_UNREACHABLE,
        )


def test_route_check_outcome_rejects_passed_false_without_failure_code():
    with pytest.raises(ValueError):
        RouteCheckOutcome(
            passed=False, reachable=False, configured_model_served=False, failure_code=None
        )


# -- 5F3B-I2-FU3A item F: mandatory cross-object binding at run_offline_route_check
# (required regression: A descriptor + B secret -> checker call count remains 0)


def test_run_offline_route_check_refuses_mismatched_descriptor_and_secret_context(tmp_path=None):
    checker_calls = {"count": 0}

    def checker(base_url, *, model_id):  # pragma: no cover - must not run
        checker_calls["count"] += 1
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    descriptor_a = route_descriptor_for_candidate("A")
    secret_b = _secret_context("minimax-m2.7")
    with pytest.raises(RouteDescriptorError):
        run_offline_route_check(descriptor=descriptor_a, secret_context=secret_b, checker=checker)
    assert checker_calls["count"] == 0


def test_run_offline_route_check_refuses_mismatched_provider_id():
    checker_calls = {"count": 0}

    def checker(base_url, *, model_id):  # pragma: no cover - must not run
        checker_calls["count"] += 1
        return _FakeRouteModelCheck(reachable=True, configured_model_served=True)

    descriptor = route_descriptor_for_candidate("A")
    forged_secret = object.__new__(type(_secret_context()))
    genuine = _secret_context()
    for name in (
        "base_url",
        "api_key",
        "endpoint_host",
        "credential_env_var_name",
        "provider_id",
        "model_id",
    ):
        object.__setattr__(forged_secret, name, getattr(genuine, name))
    object.__setattr__(forged_secret, "provider_id", "some-other-provider")

    with pytest.raises(RouteDescriptorError):
        run_offline_route_check(descriptor=descriptor, secret_context=forged_secret, checker=checker)
    assert checker_calls["count"] == 0


def test_route_check_outcome_accepts_valid_pass_and_valid_fail():
    RouteCheckOutcome(
        passed=True, reachable=True, configured_model_served=True, failure_code=None
    )
    RouteCheckOutcome(
        passed=False,
        reachable=False,
        configured_model_served=False,
        failure_code=RouteFailureCode.ROUTE_UNREACHABLE,
    )


# =============================================================================
# 5F3B-I2B-L1-LF2 OBJECTIVE 1 -- reproducing the route ATTRIBUTION COLLAPSE
# =============================================================================
#
# These tests drive the REAL, UNMODIFIED ``ar2.route_check.
# check_route_serves_model`` -- the exact function frozen I2A Sec. 15 item 9
# mandated, and the exact function Candidate-A's second live attempt used --
# through the exact ``run_offline_route_check`` wiring the frozen Category-B
# controller uses, and prove that SEVEN distinct source facts all collapse
# into one indistinguishable result.
#
# **STILL NO NETWORK.** ``ar2.route_check``'s own module-level ``httpx``
# reference is replaced, for the duration of one test, by a namespace whose
# ``Client`` is backed by an ``httpx.MockTransport``. No socket is opened, no
# real endpoint is contacted, and the frozen module's SOURCE is never touched
# -- ``monkeypatch`` restores the attribute afterwards.
#
# This reproduction is the evidence for the LF2 design correction. It is
# deliberately NOT deleted once the authenticated checker exists: it is the
# proof of what the retained live artifact can, and cannot, mean.

import json as _json  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import httpx  # noqa: E402

from ar2 import route_check as _frozen_ar2_route_check  # noqa: E402


def _install_mock_ar2_transport(monkeypatch, handler) -> None:
    """Back the FROZEN checker's own ``httpx.Client`` with a mock transport."""

    def _client(**kwargs):
        # Every kwarg the frozen module passes (``trust_env=False``) is
        # forwarded verbatim -- its behavior is not altered, only its socket.
        return httpx.Client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(_frozen_ar2_route_check, "httpx", SimpleNamespace(Client=_client))


def _unauthenticated_outcome(monkeypatch, handler):
    """One ``run_offline_route_check`` through the UNMODIFIED AR2 checker."""
    _install_mock_ar2_transport(monkeypatch, handler)
    return run_offline_route_check(
        descriptor=route_descriptor_for_candidate("A"),
        secret_context=_secret_context(),
        checker=_frozen_ar2_route_check.check_route_serves_model,
    )


def _models_body(*model_ids: str) -> bytes:
    return _json.dumps({"object": "list", "data": [{"id": mid} for mid in model_ids]}).encode()


def _raise_transport_error(request):
    raise httpx.ConnectError("synthetic connect failure", request=request)


#: The six response-level source facts, and the ONE result each produces.
_COLLAPSE_SHAPES = {
    "A_transport_unreachable": _raise_transport_error,
    "B_http_401": lambda request: httpx.Response(401, content=b"unauthorized"),
    "C_http_403": lambda request: httpx.Response(403, content=b"forbidden"),
    "D_http_500": lambda request: httpx.Response(500, content=b"bad gateway"),
    "E_http_200_malformed_body": lambda request: httpx.Response(200, content=b"{not json"),
    "F_http_200_model_absent": lambda request: httpx.Response(
        200, content=_models_body("minimax-m2.7")
    ),
}


@pytest.mark.parametrize("shape", sorted(_COLLAPSE_SHAPES))
def test_lf2_every_unauthenticated_failure_shape_collapses_to_one_outcome(shape, monkeypatch):
    """A, B, C, D, E and F are indistinguishable at the wiring boundary."""
    outcome = _unauthenticated_outcome(monkeypatch, _COLLAPSE_SHAPES[shape])
    assert outcome.passed is False
    assert outcome.configured_model_served is False


def test_lf2_a_401_is_indistinguishable_from_a_genuinely_absent_model(monkeypatch):
    """THE FINDING. An AUTH fact and a MODEL fact produce the same outcome.

    Candidate-A live attempt #2 recorded exactly this outcome. It therefore
    cannot mean "B300 does not serve qwen3-coder-next".
    """
    auth = _unauthenticated_outcome(monkeypatch, _COLLAPSE_SHAPES["B_http_401"])
    monkeypatch.undo()
    absent = _unauthenticated_outcome(monkeypatch, _COLLAPSE_SHAPES["F_http_200_model_absent"])
    assert (auth.passed, auth.configured_model_served) == (False, False)
    assert (absent.passed, absent.configured_model_served) == (False, False)
    # They agree on the wiring's own bounded failure code too, so not even
    # that distinguishes them -- and the frozen controller reduces both to a
    # single ROUTE_CHECK_FAILED regardless.
    assert auth.failure_code == RouteFailureCode.MODEL_NOT_SERVED
    assert absent.failure_code == RouteFailureCode.MODEL_NOT_SERVED


def test_lf2_malformed_listing_is_indistinguishable_from_an_absent_model(monkeypatch):
    malformed = _unauthenticated_outcome(monkeypatch, _COLLAPSE_SHAPES["E_http_200_malformed_body"])
    monkeypatch.undo()
    absent = _unauthenticated_outcome(monkeypatch, _COLLAPSE_SHAPES["F_http_200_model_absent"])
    assert malformed.failure_code == absent.failure_code == RouteFailureCode.MODEL_NOT_SERVED
    assert malformed.configured_model_served is absent.configured_model_served is False


def test_lf2_shape_g_a_malformed_checker_result_also_collapses():
    """G. A non-conforming checker RESULT fails closed the same way."""

    class _NonBoolResult:
        reachable = "true"
        configured_model_served = "true"

    outcome = run_offline_route_check(
        descriptor=route_descriptor_for_candidate("A"),
        secret_context=_secret_context(),
        checker=lambda base_url, *, model_id: _NonBoolResult(),
    )
    assert outcome.passed is False
    assert outcome.configured_model_served is False


def test_lf2_the_unauthenticated_checker_sends_no_authorization_header(monkeypatch):
    """The mechanical cause of the collapse, observed rather than asserted."""
    seen = []

    def _handler(request):
        seen.append(request)
        return httpx.Response(200, content=_models_body("qwen3-coder-next"))

    outcome = _unauthenticated_outcome(monkeypatch, _handler)
    assert outcome.passed is True  # an unauthenticated route CAN pass, when it answers
    assert len(seen) == 1
    assert "authorization" not in {name.lower() for name in seen[0].headers}


def test_lf2_the_frozen_ar2_checker_accepts_no_credential_parameter():
    """It cannot express a credential, so it cannot be handed one."""
    import inspect

    parameters = set(
        inspect.signature(_frozen_ar2_route_check.check_route_serves_model).parameters
    )
    assert parameters == {"base_url", "model_id"}
    assert "api_key" not in parameters
    assert "headers" not in parameters


def test_lf2_run_offline_route_check_cannot_forward_a_credential_to_a_checker():
    """The wiring passes exactly two values; a credential is not one of them."""
    captured = {}

    class _Result:
        reachable = True
        configured_model_served = True

    def _checker(base_url, **kwargs):
        captured["base_url"] = base_url
        captured["kwargs"] = kwargs
        return _Result()

    run_offline_route_check(
        descriptor=route_descriptor_for_candidate("A"),
        secret_context=_secret_context(),
        checker=_checker,
    )
    assert captured["base_url"] == SYNTHETIC_BASE_URL
    assert set(captured["kwargs"]) == {"model_id"}
    assert SYNTHETIC_API_KEY not in str(captured)
