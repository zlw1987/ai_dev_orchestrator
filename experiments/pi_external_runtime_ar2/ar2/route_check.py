"""A non-inference check that the route actually serves the configured model.

Why this exists, recorded because AR2's R1 discovered it the expensive way:

    H2 (``get_state``) proves what **Pi thinks** it is configured to use. It
    compares Pi's reported provider/model against AIDO's own configured values,
    which agree by construction. It does **NOT** prove that the backend serves
    that model id.

R1's prompt was therefore sent to a route whose served model id had changed
underneath the experiment. Pi asked for a model the server did not have, the turn
ended in 0.382 s with no tool call, no usage and empty assistant content, and one
irreplaceable case attempt was consumed by an infrastructure mismatch that a
mechanically evaluated gate should have caught first.

This check closes that gap. It is:

- **not an inference call.** One HTTP ``GET`` of the OpenAI-compatible
  ``/models`` listing. No prompt, no completion, no tokens generated, and it is
  never counted as one of the four semantic prompts;
- **exact.** The configured model id must appear in the served list, matched
  exactly and case-sensitively. No prefix match, no family match, no fuzzy
  match, and nothing is auto-selected or substituted;
- **silent about the endpoint.** The base URL is never returned, recorded,
  printed, or logged, and **neither is the host**. Only the scheme, the TLS fact
  and the served model ids are reported, and an unencrypted transport is named
  unmistakably. An internal endpoint's host or IP is exactly the value the
  experiment retention policy says must not reach a committed artifact, so it is
  carried in memory for the gate decision and never rendered.
- **not dependent on ambient proxy or certificate configuration (FU-C).** A
  default ``httpx.Client`` honors ``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``ALL_PROXY``
  and other ambient environment state, which would make this gate's result
  depend on whatever happens to be set in the operator's shell -- silently
  routing the "does the route serve this model" question through a proxy this
  design never named or reasoned about. The listing request is made with
  ``trust_env=False`` explicitly, so this gate's behavior is determined ONLY by
  the ``base_url`` argument it was given, never by ambient process state. No
  credential is added by this.

It does **not** authorize anything, does not choose a model, and does not widen
the capability. A failure means that case sends **zero prompts**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

ROUTE_CHECK_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class RouteModelCheck:
    """What the non-inference listing actually reported."""

    reachable: bool
    status_code: int | None
    configured_model_served: bool
    served_model_ids: tuple[str, ...]
    endpoint_host: str
    endpoint_scheme: str
    transport_tls: bool
    failure: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": "non_inference_model_listing",
            "is_a_semantic_prompt": False,
            "tokens_generated": 0,
            "reachable": self.reachable,
            "status_code": self.status_code,
            "configured_model_served": self.configured_model_served,
            "served_model_ids": list(self.served_model_ids),
            "endpoint_host_recorded": False,
            "endpoint_scheme": self.endpoint_scheme,
            "transport_tls": self.transport_tls,
            "transport_note": (
                "NOT TLS-ENCRYPTED" if not self.transport_tls else "TLS"
            ),
            "base_url_recorded": False,
            "failure": self.failure,
            "matching": "exact and case-sensitive; nothing is substituted or auto-selected",
        }


def check_route_serves_model(base_url: str, *, model_id: str) -> RouteModelCheck:
    """One ``GET /models``. Fails closed, and never surfaces the base URL."""
    parsed = urlparse(base_url)
    host = parsed.hostname or "<unparsed>"
    scheme = (parsed.scheme or "").lower()
    tls = scheme == "https"
    listing_url = base_url.rstrip("/") + "/models"

    try:
        # trust_env=False (FU-C): this gate's result must depend ONLY on the
        # base_url it was given, never on ambient HTTP_PROXY / HTTPS_PROXY /
        # ALL_PROXY or other environment-derived transport configuration.
        with httpx.Client(trust_env=False) as client:
            response = client.get(listing_url, timeout=ROUTE_CHECK_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - any transport failure fails closed
        return RouteModelCheck(
            reachable=False,
            status_code=None,
            configured_model_served=False,
            served_model_ids=(),
            endpoint_host=host,
            endpoint_scheme=scheme,
            transport_tls=tls,
            failure=f"route unreachable: {type(exc).__name__}",
        )

    if response.status_code != 200:
        return RouteModelCheck(
            reachable=True,
            status_code=response.status_code,
            configured_model_served=False,
            served_model_ids=(),
            endpoint_host=host,
            endpoint_scheme=scheme,
            transport_tls=tls,
            failure=f"the model listing returned HTTP {response.status_code}",
        )

    try:
        payload = response.json()
        served = tuple(
            str(entry.get("id"))
            for entry in payload.get("data", [])
            if isinstance(entry, dict) and entry.get("id")
        )
    except Exception as exc:  # noqa: BLE001 - an unparseable listing fails closed
        return RouteModelCheck(
            reachable=True,
            status_code=response.status_code,
            configured_model_served=False,
            served_model_ids=(),
            endpoint_host=host,
            endpoint_scheme=scheme,
            transport_tls=tls,
            failure=f"the model listing could not be parsed: {type(exc).__name__}",
        )

    matched = model_id in served
    return RouteModelCheck(
        reachable=True,
        status_code=response.status_code,
        configured_model_served=matched,
        served_model_ids=served,
        endpoint_host=host,
        endpoint_scheme=scheme,
        transport_tls=tls,
        failure=(
            None
            if matched
            else "the configured model id is not among the ids this route serves"
        ),
    )
