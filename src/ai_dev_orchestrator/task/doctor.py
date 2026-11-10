"""``task-doctor``: a read-only preflight for one project config (ALPHA-2A-T1).

It reports, for one project config, whether each gate a task needs is open
(including, since ALPHA-2A-T3, the ``read_only_workspace_content`` opt-in that
the implementer's prepare step reads the target through), and derives the
reviewer endpoint AUTHORIZATION block from the environment's base URL so a
human can paste it into the config **once per machine** (D-1).

The derivation never authorizes anything by itself: ALPHA-1A-FU1 keeps the
endpoint authorization in project config and requires the environment to match
it on every review. Deriving it per run would only compare the environment with
itself, so this command prints the block and a human decides.

What it reads: the project config; for the configured reviewer provider,
**exactly one** environment value, the base URL name
(``AIDO_LITELLM_BASE_URL`` or ``AIDO_VLLM_BASE_URL``); the presence (never the
value) of the API key name; and, only when a target path is given, the
workspace through the 5F2C writer's fixed read-only Git preflight. It runs no
verification, builds no client, contacts nothing and writes nothing. It prints
the endpoint's scheme, host, port and base path, because the human must paste
them; it never prints a userinfo, query, fragment or API key.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import ValidationError

from ai_dev_orchestrator.models import ControlledReviewEndpointConfig, ProjectConfig


@dataclass(frozen=True)
class DoctorLine:
    ok: bool
    text: str


class EndpointDerivationError(Exception):
    """The base URL does not map to an endpoint authorization. Never echoes it."""


def derive_endpoint(base_url: str) -> ControlledReviewEndpointConfig:
    """The ``controlled_review.endpoint`` block that authorizes ``base_url``.

    Parsed by httpx exactly as the reviewer's request will be
    (:func:`~ai_dev_orchestrator.review.egress.reviewer_request_url`), then
    checked with the accepted egress check against itself, so a block this
    returns is one the review gate would accept for that environment value.
    """
    from ai_dev_orchestrator.review.egress import (
        CHAT_COMPLETIONS_SUFFIX,
        ReviewerEndpointAuthority,
        check_reviewer_destination,
        effective_port,
        reviewer_request_url,
    )
    from ai_dev_orchestrator.review.models import ReviewerEgressRefused

    if type(base_url) is not str or not base_url.strip():
        raise EndpointDerivationError("the base URL is empty.")
    try:
        url = reviewer_request_url(base_url)
    except ReviewerEgressRefused:
        raise EndpointDerivationError("the base URL cannot be parsed.") from None
    if url.userinfo or url.query or url.fragment:
        raise EndpointDerivationError(
            "the base URL carries a userinfo, query or fragment, which no endpoint "
            "authorization can express."
        )
    raw_path = url.raw_path.decode("ascii", "replace")
    if not raw_path.endswith(CHAT_COMPLETIONS_SUFFIX):  # pragma: no cover - appended above
        raise EndpointDerivationError("the base URL's path is not supported.")
    try:
        endpoint = ControlledReviewEndpointConfig.model_validate(
            {
                "scheme": url.scheme,
                "host": url.raw_host.decode("ascii", "replace"),
                "port": effective_port(url),
                "base_path": raw_path[: -len(CHAT_COMPLETIONS_SUFFIX)],
            }
        )
    except ValidationError as exc:
        fields = sorted({str(error["loc"][0]) for error in exc.errors() if error["loc"]})
        raise EndpointDerivationError(
            "the base URL does not map to a valid endpoint authorization (field "
            + ", ".join(fields or ["?"])
            + ")."
        ) from None
    try:
        check_reviewer_destination(url, ReviewerEndpointAuthority.from_config(endpoint))
    except ReviewerEgressRefused:
        raise EndpointDerivationError("the derived endpoint does not match its own base URL.") from None
    return endpoint


def endpoint_block_yaml(endpoint: ControlledReviewEndpointConfig) -> str:
    return (
        "controlled_review:\n"
        "  endpoint:\n"
        f'    scheme: "{endpoint.scheme}"\n'
        f'    host: "{endpoint.host}"\n'
        f"    port: {endpoint.port}\n"
        f'    base_path: "{endpoint.base_path}"\n'
    )


READ_ONLY_CONTENT_REQUIREMENT = (
    "read_only_workspace_content.enabled must be true: the implementer's "
    "prepare step reads the target through the bounded read-only content read"
)


def read_only_content_enabled(project: ProjectConfig) -> bool:
    """Whether the 5D2 opt-in that prepare's source read needs is open (ALPHA-2A-T3).

    It is the same predicate the 5D2 reader enforces
    (``content_read.read_approved_plan_workspace_contents``), checked here only
    so that ``task-doctor`` reports it and ``task-start`` refuses before a run
    directory exists, instead of after a human has approved a plan. Prepare
    itself still enforces it; this grants nothing.
    """
    return project.read_only_workspace_content.enabled is True


_BASE_URL_NAME = {"litellm": "AIDO_LITELLM_BASE_URL", "vllm": "AIDO_VLLM_BASE_URL"}
_KEY_NAME = {"litellm": "AIDO_LITELLM_API_KEY", "vllm": "AIDO_VLLM_API_KEY"}


def run_doctor(
    project: ProjectConfig,
    *,
    environ: Mapping[str, str],
    target_path: str | None = None,
) -> tuple[list[DoctorLine], ControlledReviewEndpointConfig | None]:
    """Check every gate a task needs. Returns the report lines and the derived endpoint.

    ``environ`` is looked up for at most one value (the configured provider's
    base URL name) and one presence test (its API key name).
    """
    from ai_dev_orchestrator.review import check_controlled_review_gate
    from ai_dev_orchestrator.review.models import ReviewRefusedError
    from ai_dev_orchestrator.supervised_implementer.live import check_supervised_implementer_live_gate
    from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerError

    lines: list[DoctorLine] = []

    if read_only_content_enabled(project):
        lines.append(DoctorLine(True, "read_only_workspace_content.enabled"))
    else:
        lines.append(DoctorLine(False, READ_ONLY_CONTENT_REQUIREMENT))
    lines.append(DoctorLine(project.workspace_write.enabled, "workspace_write.enabled"))

    verification = project.controlled_verification
    executable = verification.executable
    verification_ok = (
        verification.enabled is True
        and type(executable) is str
        and os.path.isabs(executable)
        and os.path.isfile(executable)
    )
    lines.append(
        DoctorLine(
            verification_ok,
            "controlled_verification enabled with an existing absolute executable",
        )
    )

    try:
        check_supervised_implementer_live_gate(project.supervised_implementer)
        ledger = project.supervised_implementer.authorization_ledger_dir
        implementer_ok, implementer_text = os.path.isdir(ledger), "supervised_implementer live gate; ledger directory exists"
    except SupervisedImplementerError as exc:
        implementer_ok, implementer_text = False, f"supervised_implementer live gate: {exc}"
    lines.append(DoctorLine(implementer_ok, implementer_text))

    review = project.controlled_review
    try:
        check_controlled_review_gate(project)
        lines.append(DoctorLine(True, f"controlled_review gate ({review.provider}, model {review.model})"))
    except ReviewRefusedError as exc:
        lines.append(DoctorLine(False, f"controlled_review gate: {exc}"))

    derived: ControlledReviewEndpointConfig | None = None
    provider = review.provider
    base_name = _BASE_URL_NAME.get(provider)
    if base_name is None:
        lines.append(DoctorLine(False, "reviewer provider is not one AIDO supports"))
    else:
        base_url = environ.get(base_name)
        if not base_url:
            lines.append(DoctorLine(False, f"{base_name} is not set"))
        else:
            try:
                derived = derive_endpoint(base_url)
            except EndpointDerivationError as exc:
                lines.append(DoctorLine(False, f"{base_name}: {exc}"))
            else:
                configured = review.endpoint
                if configured is None:
                    lines.append(
                        DoctorLine(False, "controlled_review.endpoint is absent: paste the block below")
                    )
                elif configured == derived:
                    lines.append(DoctorLine(True, f"controlled_review.endpoint MATCHES {base_name}"))
                else:
                    lines.append(
                        DoctorLine(
                            False,
                            f"controlled_review.endpoint does NOT match {base_name}: "
                            "the block below is what the environment would need",
                        )
                    )
        key_name = _KEY_NAME[provider]
        key_present = key_name in environ
        lines.append(
            DoctorLine(
                key_present or provider == "vllm",
                f"{key_name} is {'set' if key_present else 'not set'} (its value is never read here)",
            )
        )

    if target_path is not None:
        lines.append(_workspace_line(project, target_path))
    return lines, derived


def _workspace_line(project: ProjectConfig, target_path: str) -> DoctorLine:
    from ai_dev_orchestrator.supervised_implementer.live_workspace import observe_clean_workspace_head
    from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerError

    try:
        head = observe_clean_workspace_head(project, target_path)
    except SupervisedImplementerError as exc:
        return DoctorLine(False, f"workspace: {exc}")
    return DoctorLine(True, f"workspace is wholly clean at HEAD {head}; {target_path!r} is tracked")
