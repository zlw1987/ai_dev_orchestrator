"""Fail-closed precondition gate for a **future** real model-backed L1 planner.

Phase 4J implements the §3.4 precondition table and the §10 failure taxonomy of
[PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md](../../../docs/PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md)
as a **library function only**. It is the layer that decides whether a real
model call *would* be permitted; it is not the layer that makes one, and it has
no way to make one.

What this module deliberately cannot do:

- **No `os.environ` read.** Environment values arrive as an **injected**
  ``Mapping``. :func:`load_llm_client_config_from_env` is called *only* with
  that mapping — never with its ``os.environ`` default, and calling the gate
  without a mapping is itself a gate error.
- **No client construction.** No ``LLMClient``, no ``httpx.Client``, no
  transport. ``httpx`` is not imported, and ``LLMClient`` appears only under
  ``TYPE_CHECKING``, so no code path here can build one. The client used for
  planning is always **injected** by the caller; in Phase 4J every caller
  injects an ``httpx.MockTransport``-backed fake.
- **No network call**, no DNS, no socket. :func:`endpoint_host_from_base_url`
  is pure string/URL parsing.
- **No filesystem access.** ``audit_dir`` is validated as a *flag* only — never
  created, read, stat'd, resolved, listed, or written. Audit-file writing is
  not implemented in this phase (design §7).
- **No CLI wiring, no GitHub fetch or write, no command execution, no file
  editing, no agent logic, and no target workspace access.**

The gate is **fail-closed** (design §3): every precondition must be
affirmatively satisfied, and absence or ambiguity is an error rather than a
permissive default. An absent ``real_model_planning`` block is identical to an
explicitly disabled one, and an empty ``allowed_models`` permits *no* model.

**Env default model handling (design §4.3).** ``AIDO_LITELLM_DEFAULT_MODEL`` is
required by the existing Phase 3B loader, so it must be present — but it can
never select the planning model. A default that differs from
``requested_model`` is *not* fatal; instead the returned
:class:`~ai_dev_orchestrator.llm.models.LLMClientConfig` has its
``default_model`` replaced by ``requested_model``, which has already passed the
project allowlist. The env therefore supplies *connection* details only, and the
project config supplies *permission* — a config returned by this gate cannot
fall back to the env default even if a later phase forgets to pass a model
explicitly.

Error messages never include the API key and never echo the base URL (which may
itself embed a credential in userinfo or a query string).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from ai_dev_orchestrator.github.issue_parser import ParsedIssue
from ai_dev_orchestrator.github.models import GitHubIssue
from ai_dev_orchestrator.llm.config import load_llm_client_config_from_env
from ai_dev_orchestrator.llm.models import LLMClientConfig
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.plan.model_planner import (
    ModelBackedL1Planner,
    ModelPlannerError,
)
from ai_dev_orchestrator.plan.models import L1Plan

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime.
    # Annotation-only. The gate is handed a client; it must never be able to
    # build one, so this import stays out of module globals.
    from ai_dev_orchestrator.llm.client import LLMClient


class RealModelPlanningGateError(ModelPlannerError):
    """A real-model planning **precondition** failed; no call may be made.

    Raised only for gate failures — project opt-in, model allowlist, audit-flag,
    and endpoint-shape checks. Parser failures keep their Phase 4F types
    (``ModelPlannerParseError`` / ``ModelPlannerValidationError`` /
    ``ModelPlannerPolicyError``), environment failures keep the Phase 3B
    ``LLMConfigError``, and transport failures keep the Phase 3C
    ``LLMClientError`` family. Subclassing ``ModelPlannerError`` lets a caller
    catch the whole planner family at once (design §10).
    """


def endpoint_host_from_base_url(base_url: str) -> str:
    """Reduce an endpoint base URL to ``host`` or ``host:port``.

    Pure string/URL parsing (design §5.3). No DNS lookup, no connection, no
    filesystem access.

    The result deliberately drops **everything** that could carry a credential
    or payload: userinfo (``user:key@``), path, query string, fragment, and
    scheme. Showing *where* data would go is a safety property; showing the
    credential is not.

    Raises:
        RealModelPlanningGateError: ``base_url`` is blank, unparseable, has an
            invalid port, or names no host. The message never echoes the URL.
    """
    if not isinstance(base_url, str) or not base_url.strip():
        raise RealModelPlanningGateError(
            "Endpoint base URL is missing or blank; refusing to derive a host."
        )

    try:
        split = urlsplit(base_url.strip())
        hostname = split.hostname
        port = split.port
    except ValueError as exc:
        # Raised for a malformed netloc or a non-numeric/out-of-range port. The
        # URL is never included in the message: it may embed a credential.
        raise RealModelPlanningGateError(
            "Endpoint base URL could not be parsed into a host."
        ) from exc

    if not hostname:
        raise RealModelPlanningGateError(
            "Endpoint base URL names no host (an absolute URL with a scheme is "
            "required)."
        )

    return f"{hostname}:{port}" if port is not None else hostname


def check_real_model_planning_gate(
    *,
    project: ProjectConfig,
    requested_model: str,
    env: Mapping[str, str],
    audit_dir: str | None = None,
) -> LLMClientConfig:
    """Check every real-model planning precondition and return connection settings.

    Checks run in fail-closed order — project opt-in, then the model allowlist,
    then the audit flag, then the environment — so a project that is not opted
    in fails **before** its environment is even parsed, and nothing is read on
    behalf of a project that may never be planned with a real model.

    Args:
        project: The project whose issue text would be transmitted. Its
            ``real_model_planning`` block is the per-project opt-in (design §4).
        requested_model: The model the caller explicitly named. It must match an
            ``allowed_models`` entry **exactly** — no globs, prefixes, or
            normalization (design §4.3).
        env: **Injected** environment mapping. Required: this function never
            falls back to ``os.environ``, and ``None`` is a gate error rather
            than a silent read of the real process environment.
        audit_dir: Optional audit directory, validated as a **flag only**. It is
            never created, read, stat'd, resolved, or listed, and Phase 4J
            writes no audit files.

    Returns:
        A validated :class:`LLMClientConfig` whose ``default_model`` is
        ``requested_model``, so the env default can never select the model. **No
        client is constructed from it here.**

    Raises:
        RealModelPlanningGateError: Any precondition failed. No call is made.
        LLMConfigError: A required ``AIDO_LITELLM_*`` value in ``env`` is
            missing, blank, or invalid — raised before any client is used.
    """
    settings = project.real_model_planning

    # 1. Per-project opt-in. An absent block defaults to a disabled one, so the
    #    missing and explicitly-false cases are indistinguishable (design §4.1).
    if not settings.enabled:
        raise RealModelPlanningGateError(
            f"Project {project.project_id!r} does not enable real model "
            "planning (real_model_planning.enabled is false or the block is "
            "absent). Real model planning is opt-in per project."
        )

    # 2. The model must be named explicitly; the env default never selects one.
    if not isinstance(requested_model, str) or not requested_model.strip():
        raise RealModelPlanningGateError(
            "A non-blank model name must be requested explicitly for real model "
            "planning."
        )

    # 3. An empty allowlist means "no model", never "any model" (design §4.3).
    allowed_models = list(settings.allowed_models)
    if not allowed_models:
        raise RealModelPlanningGateError(
            f"Project {project.project_id!r} enables real model planning but "
            "real_model_planning.allowed_models is empty, so no model is "
            "permitted."
        )

    # 4. Exact match only. Fuzzy matching is a silent route to an unintended
    #    (possibly external, possibly paid) model.
    if requested_model not in allowed_models:
        raise RealModelPlanningGateError(
            f"Model {requested_model!r} is not in real_model_planning."
            f"allowed_models for project {project.project_id!r}."
        )

    # 5. Audit files are doubly gated (design §4.4/§7.2). The path is treated as
    #    an opaque flag value: never created, read, stat'd, resolved, or listed.
    if audit_dir is not None:
        if not settings.allow_prompt_audit_files:
            raise RealModelPlanningGateError(
                f"Project {project.project_id!r} does not set "
                "real_model_planning.allow_prompt_audit_files, so prompt/"
                "completion audit files are not permitted."
            )
        if not isinstance(audit_dir, str) or not audit_dir.strip():
            raise RealModelPlanningGateError(
                "Audit directory must be a non-blank path when auditing is "
                "requested."
            )

    # 6. Environment. Injected only — never the real process environment.
    if env is None or not isinstance(env, Mapping):
        raise RealModelPlanningGateError(
            "An environment mapping must be injected explicitly; the real model "
            "planning gate never reads the process environment."
        )
    config = load_llm_client_config_from_env(env)

    # 7. The endpoint must reduce to a host. This validates the URL's shape
    #    before any client could be built, and never exposes the URL itself.
    endpoint_host_from_base_url(config.base_url)

    # 8. Pin the model to the allowlisted request. AIDO_LITELLM_DEFAULT_MODEL
    #    supplies connection defaults, never permission, so a differing env
    #    default is neutralized here rather than being fatal (design §4.3).
    return LLMClientConfig(
        base_url=config.base_url,
        api_key=config.api_key,
        default_model=requested_model,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.max_retries,
    )


def build_real_model_provenance(
    *,
    issue: GitHubIssue,
    project: ProjectConfig,
    requested_model: str,
    endpoint_host: str,
) -> dict[str, object]:
    """Build the wrapper provenance metadata for a real-model plan (design §9.2).

    Pure and deterministic: no clock, no environment, no filesystem, no network.
    ``generated_at`` is deliberately **absent** — clock use is not authorized in
    Phase 4J — so a later phase adds it alongside the command that emits this.

    Every value comes from the caller's own trusted inputs, never from model
    output. ``endpoint_host`` must already be host-only (see
    :func:`endpoint_host_from_base_url`); the API key never appears here.

    This helper is not wired into any command: Phase 4J adds no CLI behavior.
    """
    return {
        "engine": "real-model",
        "real_call": True,
        "model": requested_model,
        "endpoint_host": endpoint_host,
        "issue_number": issue.number,
        "repo": project.repo.github_repo,
        "title": issue.title,
        "project_id": project.project_id,
    }


def create_real_model_l1_plan_with_gate(
    *,
    issue: GitHubIssue,
    parsed: ParsedIssue,
    project: ProjectConfig,
    requested_model: str,
    env: Mapping[str, str],
    client: LLMClient,
    audit_dir: str | None = None,
) -> L1Plan:
    """Run the gate, then plan with the **injected** client.

    The gate runs to completion first, so a precondition failure means the
    client is never used. The validated config it returns is used for
    validation/provenance only — **no client is constructed from it**; the
    caller's ``client`` is the only one, and it is the only thing here that
    could reach a socket. With an ``httpx.MockTransport``-backed client injected
    (the only kind Phase 4J's tests use), no real model is contacted.

    ``requested_model`` — already checked against the project allowlist — is
    passed to the planner explicitly, so the environment's default model cannot
    select what is sent.

    Nothing is logged: no prompt, no completion, no banner, no audit file.

    Raises:
        RealModelPlanningGateError: A gate precondition failed; the client was
            not used.
        LLMConfigError: Required environment values were missing or invalid;
            the client was not used.
        ModelPlannerParseError, ModelPlannerValidationError,
            ModelPlannerPolicyError: Propagated unchanged from the Phase 4F
            parser.
        LLMClientError: Propagated unchanged from the injected client — never
            converted into a gate error, because "the gate refused" and "the
            endpoint failed" are different facts.
    """
    config = check_real_model_planning_gate(
        project=project,
        requested_model=requested_model,
        env=env,
        audit_dir=audit_dir,
    )

    # Defensive: the gate pins the config's model to the allowlisted request.
    # If that ever stops holding, fail closed rather than plan with a model that
    # was not checked.
    if config.default_model != requested_model:
        raise RealModelPlanningGateError(
            "Internal gate inconsistency: the validated configuration does not "
            "name the requested model."
        )

    return ModelBackedL1Planner(client).create_plan(
        issue, parsed, project, model=requested_model
    )
