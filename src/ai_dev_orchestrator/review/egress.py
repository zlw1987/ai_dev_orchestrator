"""Reviewer egress authority — the one destination reviewer requests may reach.

ALPHA-1A-FU1. Before this module, the reviewer's destination came only from the
environment, and the reviewer's ``httpx.Client`` honored inherited proxy
configuration (environment variables and, on Windows, the per-user registry
proxy). Nothing AIDO enforced tied source-derived material to a destination a
human had reviewed.

Three small pieces, and nothing else:

- :class:`ReviewerEndpointAuthority` — a frozen copy of the project-config
  ``controlled_review.endpoint`` block, captured once by the review gate
  **before verification runs**. Later changes to the config object, the client
  configuration, the environment or a URL cannot widen it.
- :func:`check_reviewer_destination` — a pure check on a URL **as httpx parsed
  it**. It compares the parse that will actually open the socket, never a
  separate ``urlsplit`` of a differently stripped string, so a parser
  differential (``\\@``, ``#@``, userinfo, a query or fragment swallowing
  ``/chat/completions``, dot segments) cannot widen the authority.
- :class:`ReviewerEgressTransport` — wraps the network transport and runs that
  check on **every** outbound ``httpx.Request`` before delegating. It adds no
  retry, no timeout, no count, and no response handling: RS1 owns those.

:func:`build_reviewer_network_transport` is the production inner transport:
``httpx.HTTPTransport(retries=0, trust_env=False)``. Because the reviewer's
``httpx.Client`` is then built with an explicit transport, httpx mounts **no**
inherited proxy at all (``allow_env_proxies = trust_env and transport is None``),
so neither environment proxies nor the Windows registry proxy apply, and
``trust_env=False`` also stops ``SSL_CERT_FILE``/``SSL_CERT_DIR`` from being
consulted. The connection is direct.

Stated limits (they are not hidden):

- **Name resolution is not observed.** The authority is the host as text. DNS
  answers, the hosts file and routing are outside it. Over ``https`` the server
  certificate is verified against that host with httpx's default trust store;
  over ``http`` nothing authenticates the server.
- **Not a sandbox against in-process code.** An injected inner transport is
  trusted caller code: it receives only requests that already passed the check,
  but nothing here stops arbitrary code in the same process from opening its own
  socket. The guarantee is that AIDO's reviewer path hands source-derived
  material only to the authorized destination.

Every refusal raises
:class:`~ai_dev_orchestrator.review.models.ReviewerEgressRefused`, whose fixed
message names only the mismatched component and never the URL.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from ai_dev_orchestrator.models import ControlledReviewEndpointConfig
from ai_dev_orchestrator.review.models import ReviewerEgressRefused

#: The one path suffix the OpenAI-compatible client appends to a base URL.
CHAT_COMPLETIONS_SUFFIX = "/chat/completions"

#: Where the authority comes from, recorded verbatim in the review packet.
ENDPOINT_AUTHORITY_SOURCE = "project_config.controlled_review.endpoint"

#: The reviewer transport's proxy mode, recorded verbatim in the review packet.
TRANSPORT_PROXY_MODE_DIRECT = "direct_no_inherited_proxy"

#: What the transport facts do and do not mean, stated once.
TRANSPORT_NOTE = (
    "Every reviewer request was checked, before it reached the network "
    "transport, against project_config.controlled_review.endpoint on scheme, "
    "host, effective port and path, with no userinfo, query or fragment. The "
    "reviewer transport is direct: no environment or platform (Windows "
    "registry) proxy is inherited, and SSL_CERT_FILE/SSL_CERT_DIR are not "
    "consulted. The host is authorized as TEXT: DNS resolution, the hosts file "
    "and routing are not observed. Over https the certificate is verified "
    "against that host; over http nothing authenticates the server and nothing "
    "is encrypted."
)

_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True)
class ReviewerEndpointAuthority:
    """A frozen copy of the authorized reviewer endpoint. See the module docstring."""

    scheme: str
    host: str
    port: int
    base_path: str

    @classmethod
    def from_config(
        cls, endpoint: ControlledReviewEndpointConfig
    ) -> "ReviewerEndpointAuthority":
        return cls(
            scheme=endpoint.scheme,
            host=endpoint.host,
            port=endpoint.port,
            base_path=endpoint.base_path,
        )

    @property
    def request_path(self) -> str:
        """The exact path AIDO may request: ``<base_path>/chat/completions``."""
        return self.base_path + CHAT_COMPLETIONS_SUFFIX


def effective_port(url: httpx.URL) -> int | None:
    """The port a connection to ``url`` uses. httpx drops a written default port."""
    if url.port is not None:
        return url.port
    return _DEFAULT_PORTS.get(url.scheme)


def check_reviewer_destination(
    url: httpx.URL, authority: ReviewerEndpointAuthority
) -> None:
    """Refuse ``url`` unless it is exactly the authorized request destination.

    Pure: no DNS, no connection, no environment. Compared on httpx's own parse:
    ``scheme``, ``raw_host`` (bytes, so IDNA is never decoded into a lookalike),
    the effective port, ``userinfo``, ``query``, ``fragment`` and ``raw_path``.

    Raises:
        ReviewerEgressRefused: naming the first mismatched component only.
    """
    if url.scheme != authority.scheme:
        raise ReviewerEgressRefused("scheme")
    if url.raw_host != authority.host.encode("ascii"):
        raise ReviewerEgressRefused("host")
    if effective_port(url) != authority.port:
        raise ReviewerEgressRefused("port")
    if url.userinfo != b"":
        raise ReviewerEgressRefused("userinfo")
    if url.query != b"":
        raise ReviewerEgressRefused("query")
    if url.fragment != "":
        raise ReviewerEgressRefused("fragment")
    if url.raw_path != authority.request_path.encode("ascii"):
        raise ReviewerEgressRefused("path")


def reviewer_request_url(base_url: str) -> httpx.URL:
    """The URL the LLM client will request for ``base_url``, parsed by httpx.

    This is exactly the expression
    :meth:`ai_dev_orchestrator.llm.client.LLMClient.chat` uses, so the
    pre-client gate checks the same string the client will send. The transport
    re-checks the real request regardless.

    Raises:
        ReviewerEgressRefused: httpx cannot parse it (component ``url``). The
            URL is never echoed.
    """
    try:
        return httpx.URL(f"{base_url.rstrip('/')}{CHAT_COMPLETIONS_SUFFIX}")
    except (httpx.InvalidURL, TypeError, ValueError):
        raise ReviewerEgressRefused("url") from None


class ReviewerEgressTransport(httpx.BaseTransport):
    """Checks every outbound reviewer request before the network transport sees it."""

    def __init__(
        self, inner: httpx.BaseTransport, *, authority: ReviewerEndpointAuthority
    ) -> None:
        if not isinstance(authority, ReviewerEndpointAuthority):
            raise TypeError("authority must be a ReviewerEndpointAuthority")
        self._inner = inner
        self._authority = authority

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "POST":
            raise ReviewerEgressRefused("method")
        check_reviewer_destination(request.url, self._authority)
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def build_reviewer_network_transport() -> httpx.BaseTransport:
    """The production reviewer network transport: direct, no inherited proxy.

    ``retries=0`` keeps RS1's one-HTTP-request-per-attempt property at the
    connection layer too, and ``trust_env=False`` stops environment TLS trust
    settings from being consulted. Constructing it opens no socket.
    """
    return httpx.HTTPTransport(retries=0, trust_env=False)
