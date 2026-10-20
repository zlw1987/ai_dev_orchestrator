"""ALPHA-1A-FU1 tests: reviewer egress authority.

The reviewer may send source-derived material only to the destination its
human-reviewed project config authorizes (``controlled_review.endpoint``), and
its transport inherits no proxy. These tests prove, offline:

1. the destination check compares httpx's own parse of the request URL, so
   parser differentials, userinfo, query/fragment injection, path substitution
   and alternative ports are refused;
2. every refusal happens before any network transport is reached, after
   verification, with no URL in the output;
3. the transport re-checks every real request (post-validation mutation, a
   followed redirect, the compact retry);
4. the production transport is direct: no environment or registry proxy, no
   ``SSL_CERT_FILE`` trust, zero connection retries;
5. the library has no client injection point left, and the v5 packet and the
   banner record the authorized destination.

No test opens a socket or reads a real credential. Every endpoint is synthetic
(``.invalid`` or ``reviewer.example``) and no real endpoint appears here.
"""

from __future__ import annotations

import inspect
import json
import urllib.request
from pathlib import Path

import httpx
import pytest

from ai_dev_orchestrator.llm.client import LLMClient
from ai_dev_orchestrator.llm.models import LLMClientConfig
from ai_dev_orchestrator.models import ControlledReviewEndpointConfig
from ai_dev_orchestrator.review import (
    ENDPOINT_AUTHORITY_SOURCE,
    TRANSPORT_NOTE_DIRECT,
    TRANSPORT_NOTE_INJECTED_UNVERIFIED,
    TRANSPORT_PROXY_MODE_DIRECT,
    TRANSPORT_PROXY_MODE_INJECTED_UNVERIFIED,
    ReviewerDirectNetworkTransport,
    ReviewerEgressRefused,
    ReviewerEgressTransport,
    ReviewerEndpointAuthority,
    build_reviewer_network_transport,
    check_reviewer_destination,
    reviewer_request_url,
    run_controlled_review,
)
from ai_dev_orchestrator.review import egress as egress_module
from ai_dev_orchestrator.review import reviewer as reviewer_module
from test_cli_l2_review_approved_file_edit import (
    DIRTYING_BODY,
    ENABLED_REVIEW_BLOCK,
    FAKE_API_KEY,
    FAKE_BASE_URL,
    REVIEWER_MODEL,
    VALID_REVIEW_JSON,
    _env,
    _mock_client_factory,
    _run,
    _setup,
    _stdout_json,
    git_required,
    windows_only,
)
from test_cli_l2_review_supervision import _ok, _scripted_factory

AUTHORITY = ReviewerEndpointAuthority(
    scheme="http", host="reviewer.example", port=8000, base_path="/v1"
)


def _check(base_url: str, authority: ReviewerEndpointAuthority = AUTHORITY) -> None:
    check_reviewer_destination(reviewer_request_url(base_url), authority)


def _component(base_url: str, authority: ReviewerEndpointAuthority = AUTHORITY) -> str:
    with pytest.raises(ReviewerEgressRefused) as excinfo:
        _check(base_url, authority)
    return excinfo.value.component


# =============================================================================
# 1. The destination check, on httpx's own parse
# =============================================================================


@pytest.mark.parametrize(
    "base_url",
    [
        "http://reviewer.example:8000/v1",
        "http://reviewer.example:8000/v1/",
        "http://REVIEWER.example:8000/v1",
    ],
)
def test_equivalent_spellings_of_the_authorized_url_are_accepted(base_url):
    _check(base_url)


def test_an_authorized_default_port_matches_a_url_without_a_port():
    """Effective-port equality: httpx drops a written default port."""
    authority = ReviewerEndpointAuthority(
        scheme="http", host="reviewer.example", port=80, base_path="/v1"
    )
    _check("http://reviewer.example/v1", authority)
    _check("http://reviewer.example:80/v1", authority)


def test_an_empty_base_path_authorizes_exactly_chat_completions_at_the_root():
    authority = ReviewerEndpointAuthority(
        scheme="https", host="reviewer.example", port=443, base_path=""
    )
    _check("https://reviewer.example", authority)
    assert _component("https://reviewer.example/v1", authority) == "path"


def test_a_canonical_ipv4_authority_matches_only_that_literal():
    authority = ReviewerEndpointAuthority(
        scheme="http", host="127.0.0.1", port=8000, base_path="/v1"
    )
    _check("http://127.0.0.1:8000/v1", authority)
    # Resolver aliases of the same address are refused, not normalized.
    assert _component("http://127.1:8000/v1", authority) == "host"


@pytest.mark.parametrize(
    ("base_url", "component"),
    [
        ("https://reviewer.example:8000/v1", "scheme"),
        ("http://other.example:8000/v1", "host"),
        ("http://reviewer.example.:8000/v1", "host"),
        ("http://reviewer.example:8001/v1", "port"),
        ("http://reviewer.example/v1", "port"),
        ("http://reviewer.example:8000/v2", "path"),
        ("http://reviewer.example:8000/v1/../v1x", "path"),
        ("http://reviewer.example:8000//v1", "path"),
        ("http://reviewer.example:8000/v1%2f..", "path"),
        ("http://reviewer.example:8000/v1/extra", "path"),
        ("http://u:p@reviewer.example:8000/v1", "userinfo"),
        ("http://reviewer.example:8000/v1?x=1", "query"),
        ("http://reviewer.example:8000/v1#f", "fragment"),
        ("http://evil.example#@reviewer.example:8000/v1", "host"),
        ("http://reviewer.example:8000\\@evil.example/v1", "host"),
        (" http://reviewer.example:8000/v1", "scheme"),
        ("not a url", "scheme"),
    ],
)
def test_every_substitution_is_refused_naming_only_the_component(base_url, component):
    with pytest.raises(ReviewerEgressRefused) as excinfo:
        _check(base_url)

    assert excinfo.value.component == component
    message = str(excinfo.value)
    # Fixed text: never the URL, the observed host, or any userinfo.
    for fragment in ("evil.example", "other.example", "u:p", "x=1", base_url.strip()):
        assert fragment not in message


def test_an_unparseable_url_is_refused_as_url():
    assert _component("http://reviewer.example:99999/v1") in {"url", "port"}


# =============================================================================
# 2. The authority itself (config) — see also test_controlled_review_config.py
# =============================================================================


def test_the_authority_is_a_frozen_copy_of_the_config():
    endpoint = ControlledReviewEndpointConfig(
        scheme="http", host="reviewer.example", port=8000, base_path="/v1"
    )
    authority = ReviewerEndpointAuthority.from_config(endpoint)

    assert authority == AUTHORITY
    assert authority.request_path == "/v1/chat/completions"
    with pytest.raises(Exception):
        authority.host = "evil.example"  # type: ignore[misc]


# =============================================================================
# 3. The transport: every request is checked before the network transport
# =============================================================================


class _CountingInner(httpx.BaseTransport):
    def __init__(self, response: httpx.Response | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self._response = response

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._response or httpx.Response(200, json={"ok": True})


def test_the_transport_refuses_a_mismatched_request_before_the_inner_transport():
    inner = _CountingInner()
    transport = ReviewerEgressTransport(inner, authority=AUTHORITY)

    request = httpx.Request(
        "POST",
        "http://evil.example:8000/v1/chat/completions",
        headers={"Authorization": f"Bearer {FAKE_API_KEY}"},
        json={"model": "m"},
    )
    with pytest.raises(ReviewerEgressRefused) as excinfo:
        transport.handle_request(request)

    assert excinfo.value.component == "host"
    # The Authorization header never reached any network transport.
    assert inner.requests == []


def test_the_transport_refuses_a_non_post_method():
    inner = _CountingInner()
    transport = ReviewerEgressTransport(inner, authority=AUTHORITY)

    with pytest.raises(ReviewerEgressRefused) as excinfo:
        transport.handle_request(
            httpx.Request("GET", "http://reviewer.example:8000/v1/chat/completions")
        )

    assert excinfo.value.component == "method"
    assert inner.requests == []


def test_the_transport_forwards_exactly_the_authorized_request():
    inner = _CountingInner()
    transport = ReviewerEgressTransport(inner, authority=AUTHORITY)

    response = transport.handle_request(
        httpx.Request("POST", "http://reviewer.example:8000/v1/chat/completions")
    )

    assert response.status_code == 200
    assert len(inner.requests) == 1


def test_the_transport_requires_a_frozen_authority():
    with pytest.raises(TypeError):
        ReviewerEgressTransport(_CountingInner(), authority={"host": "x"})  # type: ignore[arg-type]


def test_a_forced_redirect_to_another_host_is_refused_at_the_transport():
    """Even a client that DID follow redirects could not leave the authority."""
    redirect = httpx.Response(
        307, headers={"Location": "http://evil.example:8000/v1/chat/completions"}
    )
    inner = _CountingInner(redirect)
    transport = ReviewerEgressTransport(inner, authority=AUTHORITY)

    with httpx.Client(transport=transport, follow_redirects=True) as client:
        with pytest.raises(ReviewerEgressRefused) as excinfo:
            client.post("http://reviewer.example:8000/v1/chat/completions", json={})

    assert excinfo.value.component == "host"
    assert len(inner.requests) == 1


def test_the_llm_client_does_not_follow_a_redirect_at_all():
    """The shipped client's own policy: one request, no second destination."""
    redirect = httpx.Response(
        307, headers={"Location": "http://evil.example:8000/v1/chat/completions"}
    )
    inner = _CountingInner(redirect)
    config = LLMClientConfig(
        base_url="http://reviewer.example:8000/v1",
        api_key=FAKE_API_KEY,
        default_model="m",
        max_retries=0,
    )
    client = LLMClient(config, transport=ReviewerEgressTransport(inner, authority=AUTHORITY))

    from ai_dev_orchestrator.llm.models import LLMMessage, LLMRequest

    with pytest.raises(Exception) as excinfo:
        client.chat(
            LLMRequest(model="m", messages=[LLMMessage(role="user", content="x")])
        )

    assert not isinstance(excinfo.value, ReviewerEgressRefused)
    assert len(inner.requests) == 1


# =============================================================================
# 4. Proxy isolation and the production transport
# =============================================================================


_PROXY_ENV = {
    "HTTP_PROXY": "http://proxy.invalid:3128",
    "HTTPS_PROXY": "http://proxy.invalid:3128",
    "ALL_PROXY": "http://proxy.invalid:3128",
}


def test_the_production_transport_is_direct_with_zero_retries():
    import httpcore

    transport = build_reviewer_network_transport()

    assert isinstance(transport, httpx.HTTPTransport)
    assert type(transport._pool) is httpcore.ConnectionPool  # not HTTPProxy
    assert transport._pool._retries == 0
    transport.close()


def test_the_production_transport_ignores_ssl_cert_file(monkeypatch, tmp_path):
    """``trust_env=False``: a bogus environment CA bundle is never loaded."""
    bogus = tmp_path / "bogus.pem"
    bogus.write_text("not a certificate\n", encoding="utf-8")
    monkeypatch.setenv("SSL_CERT_FILE", str(bogus))

    # Positive control: a transport that DID trust the environment fails here.
    with pytest.raises(Exception):
        httpx.HTTPTransport(trust_env=True)

    build_reviewer_network_transport().close()


def test_the_reviewer_client_mounts_no_inherited_proxy(monkeypatch):
    """Environment AND (simulated) Windows-registry proxies are both ignored."""
    for name, value in _PROXY_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    # Positive control: a default client really would mount these proxies.
    with httpx.Client() as default_client:
        assert default_client._mounts, "the proxy environment was not effective"

    config = LLMClientConfig(
        base_url="http://reviewer.example:8000/v1",
        api_key=FAKE_API_KEY,
        default_model="m",
        max_retries=0,
    )
    wrapper = ReviewerEgressTransport(
        build_reviewer_network_transport(), authority=AUTHORITY
    )
    client, owned = LLMClient(config, transport=wrapper)._acquire_client()
    try:
        assert owned is True
        assert client._mounts == {}
        assert client._transport is wrapper
    finally:
        client.close()


def test_a_registry_proxy_is_not_mounted_either(monkeypatch):
    """With no proxy variable set, urllib falls back to the registry on Windows."""
    for name in (*_PROXY_ENV, "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.setattr(
        urllib.request, "getproxies", lambda: {"http": "proxy.invalid:3128"}
    )
    import httpx._utils as httpx_utils

    monkeypatch.setattr(
        httpx_utils, "getproxies", lambda: {"http": "proxy.invalid:3128"}
    )

    with httpx.Client() as default_client:
        assert default_client._mounts, "the simulated registry proxy was not effective"

    config = LLMClientConfig(
        base_url="http://reviewer.example:8000/v1",
        api_key=FAKE_API_KEY,
        default_model="m",
        max_retries=0,
    )
    client, _ = LLMClient(
        config,
        transport=ReviewerEgressTransport(
            build_reviewer_network_transport(), authority=AUTHORITY
        ),
    )._acquire_client()
    try:
        assert client._mounts == {}
    finally:
        client.close()


# =============================================================================
# 5. The library entry point has no client injection left
# =============================================================================


def test_run_controlled_review_requires_a_network_transport_factory():
    parameters = inspect.signature(run_controlled_review).parameters

    assert "network_transport_factory" in parameters
    assert parameters["network_transport_factory"].default is inspect.Parameter.empty
    assert "client_factory" not in parameters
    assert "client" not in parameters

    with pytest.raises(TypeError):
        run_controlled_review(  # type: ignore[call-arg]
            approved_diff=None, project=None, read_env=lambda _p: {}
        )


def test_the_egress_module_imports_no_process_or_environment_access():
    names = set(vars(egress_module))
    for forbidden in ("subprocess", "os", "multiprocessing", "asyncio", "socket"):
        assert forbidden not in names


# =============================================================================
# 6. End to end, through the real command
# =============================================================================


MISMATCHED_BASE_URL = "http://other-host.invalid/v1"


@windows_only
@git_required
@pytest.mark.parametrize(
    "base_url",
    [
        MISMATCHED_BASE_URL,
        "http://fake-litellm.invalid:8080/v1",
        "http://fake-litellm.invalid/v2",
        "https://fake-litellm.invalid/v1",
        "http://fake-litellm.invalid/v1?x=1",
    ],
)
def test_a_mismatched_environment_url_is_refused_after_verification(
    tmp_path, capsys, base_url
):
    _, config, artifact = _setup(tmp_path)
    reads: list[str] = []
    built: list[int] = []

    def read_env(provider):
        reads.append(provider)
        return _env(AIDO_LITELLM_BASE_URL=base_url)

    def forbidden_transport():
        built.append(1)
        raise AssertionError("a network transport was built for a refused URL")

    code = _run(config, artifact, read_env=read_env, client_factory=forbidden_transport)

    assert code == 4
    # Verification passed first (the reader ran), exactly once, and nothing
    # network-capable was ever built.
    assert reads == ["litellm"]
    assert built == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "reviewer-egress-refused" in captured.err
    assert "refused before it reached any network transport" in captured.err
    assert base_url not in captured.err
    assert "REAL REVIEWER MODEL CALL — a real network call" not in captured.err


@windows_only
@git_required
def test_userinfo_in_the_environment_url_is_refused_and_never_echoed(tmp_path, capsys):
    _, config, artifact = _setup(tmp_path)
    secret_url = "http://leaky-user:leaky-pass@fake-litellm.invalid/v1"

    code = _run(
        config,
        artifact,
        read_env=lambda _p: _env(AIDO_LITELLM_BASE_URL=secret_url),
        client_factory=_mock_client_factory(),
    )

    assert code == 4
    captured = capsys.readouterr()
    assert "userinfo" in captured.err
    for fragment in ("leaky-user", "leaky-pass", secret_url):
        assert fragment not in captured.err
        assert fragment not in captured.out


@windows_only
@git_required
def test_a_missing_endpoint_refuses_before_verification_runs(tmp_path, capsys):
    marker = tmp_path / "verification-ran.txt"
    body = f"""
import pathlib, sys
pathlib.Path({str(marker)!r}).write_text("ran", encoding="utf-8")
sys.exit(0)
"""
    no_endpoint_block = (
        "controlled_review:\n"
        "  enabled: true\n"
        '  provider: "litellm"\n'
        f'  model: "{REVIEWER_MODEL}"\n'
    )
    _, config, artifact = _setup(tmp_path, body=body, review_block=no_endpoint_block)

    def forbidden_env(_provider):
        raise AssertionError("the environment was read without an endpoint authority")

    code = _run(config, artifact, read_env=forbidden_env)

    assert code == 1
    assert not marker.exists(), "the verification process was launched"
    assert "controlled_review.endpoint" in capsys.readouterr().err


@windows_only
@git_required
def test_a_post_validation_mutation_is_refused_at_the_transport(
    tmp_path, capsys, monkeypatch
):
    """The pre-client gate is bypassed; the transport still refuses.

    ``reviewer_request_url`` is patched to report the AUTHORIZED URL, so the
    pre-client check passes while the client actually sends to the
    environment's (unauthorized) URL — the shape of any post-validation change.
    """
    _, config, artifact = _setup(tmp_path)
    monkeypatch.setattr(
        reviewer_module,
        "reviewer_request_url",
        lambda _base: httpx.URL(FAKE_BASE_URL + "/chat/completions"),
    )
    inner_calls: list[httpx.Request] = []

    def handler(request):
        inner_calls.append(request)
        return httpx.Response(200, json={})

    code = _run(
        config,
        artifact,
        read_env=lambda _p: _env(AIDO_LITELLM_BASE_URL=MISMATCHED_BASE_URL),
        client_factory=lambda: httpx.MockTransport(handler),
    )

    assert code == 4
    assert inner_calls == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "reviewer-egress-refused" in captured.err
    assert MISMATCHED_BASE_URL not in captured.err


@windows_only
@git_required
def test_both_compact_retry_requests_pass_the_same_check(tmp_path):
    from test_cli_l2_review_approved_file_edit import ENDPOINT_LINES

    block = (
        "controlled_review:\n"
        "  enabled: true\n"
        '  provider: "litellm"\n'
        f'  model: "{REVIEWER_MODEL}"\n'
        "  compact_retry_on_unusable_output: true\n"
        f"{ENDPOINT_LINES}"
    )
    _, config, artifact = _setup(tmp_path, review_block=block)
    urls: list[str] = []

    def recording(action):
        def wrapped(request):
            urls.append(str(request.url))
            return action(request)

        return wrapped

    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _p: _env(),
        client_factory=_scripted_factory(
            [recording(_ok("not json at all")), recording(_ok(VALID_REVIEW_JSON))],
            seen,
        ),
    )

    assert code == 0
    assert urls == [FAKE_BASE_URL + "/chat/completions"] * 2


@windows_only
@git_required
def test_the_authorization_header_reaches_only_the_authorized_request(tmp_path):
    _, config, artifact = _setup(tmp_path)
    headers: list[str] = []

    def handler(request):
        headers.append(request.headers["authorization"])
        assert str(request.url) == FAKE_BASE_URL + "/chat/completions"
        return httpx.Response(
            200,
            json={
                "model": REVIEWER_MODEL,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": VALID_REVIEW_JSON},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    code = _run(
        config,
        artifact,
        read_env=lambda _p: _env(),
        client_factory=lambda: httpx.MockTransport(handler),
    )

    assert code == 0
    assert headers == [f"Bearer {FAKE_API_KEY}"]


@windows_only
@git_required
def test_the_v5_packet_and_banner_record_the_authorized_destination(tmp_path, capsys):
    _, config, artifact = _setup(tmp_path)

    code = _run(
        config, artifact, read_env=lambda _p: _env(), client_factory=_mock_client_factory()
    )

    assert code == 0
    captured = capsys.readouterr()
    packet = json.loads(captured.out)
    reviewer = packet["reviewer"]
    assert packet["schema_version"] == "review-packet.v5"
    assert reviewer["endpoint_port"] == 80
    assert reviewer["endpoint_base_path"] == "/v1"
    assert reviewer["endpoint_authority_source"] == ENDPOINT_AUTHORITY_SOURCE
    assert reviewer["endpoint_matched_authority_before_each_request"] is True
    # ALPHA-1A-FU2: _mock_client_factory injects an httpx.MockTransport, which
    # AIDO did not build, so no direct-transport claim may be made for it.
    assert reviewer["transport_proxy_mode"] == TRANSPORT_PROXY_MODE_INJECTED_UNVERIFIED
    assert reviewer["transport_note"] == TRANSPORT_NOTE_INJECTED_UNVERIFIED
    assert "not observed" in reviewer["transport_note"]
    # v4 meanings unchanged.
    assert reviewer["endpoint_host"] == "fake-litellm.invalid"
    assert reviewer["endpoint_scheme"] == "http"
    assert reviewer["transport_tls"] is False
    for absent in ("base_url", "api_key", "url"):
        assert absent not in reviewer

    assert (
        "Endpoint:      scheme http, port 80, base path /v1 — matches "
        "project-config authorization\n"
    ) in captured.err
    assert "Network path:  NOT ESTABLISHED — caller-supplied network transport" in (
        captured.err
    )
    assert "inherited proxies disabled" not in captured.err
    assert "no environment or platform proxy inherited" not in captured.err
    assert FAKE_BASE_URL not in captured.err
    assert FAKE_API_KEY not in captured.err
    assert FAKE_API_KEY not in captured.out


# =============================================================================
# 7. ALPHA-1A-FU2: transport provenance is derived, never asserted
# =============================================================================


def test_only_the_exact_production_transport_type_is_certified_direct():
    from ai_dev_orchestrator.review import transport_proxy_mode_of

    production = build_reviewer_network_transport()
    try:
        assert type(production) is ReviewerDirectNetworkTransport
        assert transport_proxy_mode_of(production) == TRANSPORT_PROXY_MODE_DIRECT
    finally:
        production.close()

    class _Lookalike(ReviewerDirectNetworkTransport):
        pass

    plain = httpx.HTTPTransport(retries=0, trust_env=False)
    proxied = httpx.HTTPTransport(proxy="http://proxy.invalid:3128")
    lookalike = _Lookalike()
    try:
        for other in (
            httpx.MockTransport(lambda _r: httpx.Response(200)),
            plain,  # even a correctly configured bare HTTPTransport
            proxied,
            lookalike,  # a subclass is not the type AIDO built
        ):
            assert (
                transport_proxy_mode_of(other)
                == TRANSPORT_PROXY_MODE_INJECTED_UNVERIFIED
            )
    finally:
        plain.close()
        proxied.close()
        lookalike.close()


def test_the_production_transport_class_takes_no_arguments():
    """No argument can reach it, so no proxy/trust_env/retries can be injected."""
    parameters = inspect.signature(ReviewerDirectNetworkTransport).parameters
    assert list(parameters) == []
    with pytest.raises(TypeError):
        ReviewerDirectNetworkTransport(proxy="http://proxy.invalid:3128")  # type: ignore[call-arg]


def test_the_two_notes_differ_and_the_injected_one_claims_no_transport_property():
    assert TRANSPORT_NOTE_DIRECT != TRANSPORT_NOTE_INJECTED_UNVERIFIED
    injected = TRANSPORT_NOTE_INJECTED_UNVERIFIED.lower()
    assert "did not establish" in injected
    # The injected note must not contain the production-only assertions.
    assert "certificate is verified" not in injected
    assert "which is direct" not in injected
    assert "are not consulted" not in injected
    assert "production reviewer transport" not in injected.replace(
        "not built by aido's production reviewer transport factory", ""
    )
    # Both keep the facts that hold for either transport.
    for note in (TRANSPORT_NOTE_DIRECT, TRANSPORT_NOTE_INJECTED_UNVERIFIED):
        assert "checked, before it reached the inner network transport" in note
        assert "not observed" in note


def test_the_packet_builder_requires_and_validates_the_proxy_mode():
    from ai_dev_orchestrator.review import build_review_packet

    parameters = inspect.signature(build_review_packet).parameters
    assert parameters["transport_proxy_mode"].default is inspect.Parameter.empty


@windows_only
@git_required
def test_the_production_cli_transport_records_the_direct_mode(
    tmp_path, capsys, monkeypatch
):
    """The CLI's default factory yields AIDO's transport; the facts say direct.

    The real class is used, so the exact-type derivation is what is exercised.
    Only ``handle_request`` is replaced, so no socket is opened.
    """
    from ai_dev_orchestrator import cli

    _, config, artifact = _setup(tmp_path)
    reached: list[httpx.Request] = []

    def canned(self, request):
        reached.append(request)
        return httpx.Response(
            200,
            json={
                "model": REVIEWER_MODEL,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": VALID_REVIEW_JSON},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    monkeypatch.setattr(ReviewerDirectNetworkTransport, "handle_request", canned)

    # No ``network_transport_factory``: the helper's default is the production one.
    cli._run_l2_review_approved_file_edit(
        project_config=config,
        approved_diff_proposal=artifact,
        verify_approved_file_edit_flag=True,
        real_reviewer=True,
        read_env=lambda _p: _env(),
    )

    captured = capsys.readouterr()
    reviewer = json.loads(captured.out)["reviewer"]
    assert len(reached) == 1
    assert reviewer["transport_proxy_mode"] == TRANSPORT_PROXY_MODE_DIRECT
    assert reviewer["transport_note"] == TRANSPORT_NOTE_DIRECT
    assert reviewer["endpoint_matched_authority_before_each_request"] is True
    assert (
        "Network path:  direct; no environment or platform proxy inherited"
        in captured.err
    )
    assert "NOT ESTABLISHED" not in captured.err


@windows_only
@git_required
def test_the_cli_default_transport_factory_builds_the_production_type():
    from ai_dev_orchestrator import cli

    transport = cli._build_reviewer_network_transport()
    try:
        assert type(transport) is ReviewerDirectNetworkTransport
    finally:
        transport.close()


@windows_only
@git_required
def test_an_https_injected_transport_is_not_announced_as_tls_verified(
    tmp_path, capsys
):
    """transport_tls stays scheme-derived, but the banner claims no more than that."""
    from ai_dev_orchestrator.review import ReviewerCallNotice
    from ai_dev_orchestrator import cli

    notice = ReviewerCallNotice(
        provider="litellm",
        model="m",
        endpoint_host="h.invalid",
        endpoint_scheme="https",
        transport_tls=True,
        endpoint_port=443,
        endpoint_base_path="/v1",
        transport_proxy_mode=TRANSPORT_PROXY_MODE_INJECTED_UNVERIFIED,
        project_id="p",
        repo="o/r",
        issue_number=1,
    )
    cli._echo_reviewer_banner(notice)
    err = capsys.readouterr().err
    assert "TLS/certificate verification NOT established" in err
    assert "— TLS-encrypted" not in err


def test_the_egress_refusal_messages_do_not_misdescribe_method_or_url():
    method = str(ReviewerEgressRefused("method"))
    url = str(ReviewerEgressRefused("url"))
    host = str(ReviewerEgressRefused("host"))

    assert "method is not POST" in method
    assert "does not match" not in method
    assert "could not be parsed" in url
    assert "does not match" not in url
    assert "host does not match project_config.controlled_review.endpoint" in host
    for message in (method, url, host):
        assert "No request was issued" not in message
        assert "refused before it reached any network transport" in message


@windows_only
@git_required
def test_a_dirtying_verification_still_stops_before_any_egress_check(tmp_path):
    """Ordering: an untrusted workspace reads no environment and builds nothing."""
    _, config, artifact = _setup(tmp_path, body=DIRTYING_BODY)

    def forbidden_env(_provider):
        raise AssertionError("environment read after an untrusted verification")

    assert _run(config, artifact, read_env=forbidden_env) == 3


def test_the_enabled_test_block_authorizes_the_test_url():
    """Guard for the fixtures themselves: the shared block matches FAKE_BASE_URL."""
    assert "fake-litellm.invalid" in ENABLED_REVIEW_BLOCK
    assert "port: 80" in ENABLED_REVIEW_BLOCK
    _check(
        FAKE_BASE_URL,
        ReviewerEndpointAuthority(
            scheme="http", host="fake-litellm.invalid", port=80, base_path="/v1"
        ),
    )
    assert Path(__file__).name == "test_review_egress.py"
