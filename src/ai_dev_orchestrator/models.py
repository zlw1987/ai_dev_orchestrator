"""Typed project-config models for the AI Dev Orchestrator.

Phase 1: pure data models only. These describe the SHAPE of a project config.
They make no network calls, read no environment variables, and never store
secrets — provider connection details are referenced by environment-variable
*name* (e.g. ``base_url_env``), never by value.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so typos fail loudly."""

    model_config = ConfigDict(extra="forbid")


# -- The operator token policy, in one place ----------------------------------
#
# AIDO model output-token limits are UNLIMITED BY DEFAULT. For an ordinary model
# request that means exactly one thing on the wire: **no OpenAI-compatible
# ``max_tokens`` field is sent**. It does NOT mean a large substituted number, a
# model-context-derived value, or a per-model guess — none of which AIDO has any
# basis to invent.
#
# A provider/model/backend still has its own native context and output limits.
# Those are backend capability limits, NOT an AIDO-requested token limit, and
# must never be represented as one.
#
# The optional interface below exists so an operator can explicitly REQUEST a
# finite cap. Absent or null means no AIDO cap; a positive integer means exactly
# that integer. Zero, negatives and booleans are refused, the last because
# Pydantic would otherwise coerce ``true`` into ``1`` and silently impose a
# one-token ceiling.
def _validate_optional_output_token_cap(value: object, field: str) -> object:
    """Shape check for an optional operator-requested output-token cap."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(
            f"{field} must be omitted/null (no AIDO output-token cap) or a "
            "positive integer; a boolean is not a token count."
        )
    if isinstance(value, int) and value <= 0:
        raise ValueError(
            f"{field} must be a POSITIVE integer when set. Omit it (or set it to "
            "null) to request no AIDO output-token cap at all; 0 and negative "
            "values are not a way to say 'unlimited'."
        )
    return value


class RepoConfig(_Strict):
    """Where the project lives and how branches are named."""

    workspace_path: str = Field(
        description="Absolute root the orchestrator may operate within "
        "(documentation/config only; never read by Phase 1 code)."
    )
    github_repo: str = Field(description="owner/name of the GitHub repository.")
    default_base_branch: str = Field(default="main")
    branch_prefix: str = Field(
        description="Prefix for orchestrator-created branches, e.g. 'ai/mis'."
    )


class WorkspacePolicyConfig(_Strict):
    """Coarse safety switches for workspace behavior."""

    deny_outside_workspace: bool = Field(default=True)
    allow_symlinks: bool = Field(default=False)
    max_changed_files: int = Field(default=20, ge=0)


class PathRulesConfig(_Strict):
    """Allow / protect / forbid path rule lists (glob patterns).

    Precedence is enforced by the policy engine: forbidden > protected > allowed.
    """

    allowed_paths: list[str] = Field(default_factory=list)
    protected_paths: list[str] = Field(default_factory=list)
    forbidden_paths: list[str] = Field(default_factory=list)


class ProviderConfig(_Strict):
    """A model provider definition.

    Connection secrets are NOT stored here. ``base_url_env`` and ``api_key_env``
    name the environment variables that supply those values at run time.
    """

    type: str = Field(description="Provider type, e.g. 'openai_compatible'.")
    base_url_env: str = Field(description="Env var NAME holding the base URL.")
    api_key_env: str = Field(description="Env var NAME holding the API key.")
    timeout_seconds: int = Field(default=600, gt=0)
    default_headers: dict[str, str] = Field(default_factory=dict)


class AIRoleConfig(_Strict):
    """Configuration for one AI role (implementer / reviewer / fixer).

    **Dormant shape only.** No runtime reads this block: the controlled reviewer
    takes its model authority from ``controlled_review`` alone, and there is no
    model-backed implementer or fixer. The shape is kept truthful anyway, so a
    future phase that does read it cannot silently inherit a token ceiling AIDO's
    product policy never intended.

    ``max_tokens`` follows the same operator token policy as
    :attr:`ControlledReviewConfig.max_output_tokens`: absent/``None`` means AIDO
    requests **no** output-token cap, and a positive integer is an explicit
    operator-configured cap. There is no arbitrary numeric default.
    """

    provider: str = Field(description="Key into the providers map.")
    model: str = Field(description="Model name exposed by the provider.")
    temperature: float = Field(default=0.2, ge=0.0)
    max_tokens: int | None = Field(
        default=None,
        description="OPTIONAL requested model-output cap. Absent or null means "
        "AIDO imposes no output-token ceiling for this role; a positive integer "
        "is an explicit operator-requested cap. Provider/model/backend native "
        "limits still exist independently and are not an AIDO-requested cap.",
    )
    can_edit_files: bool = Field(default=False)

    @field_validator("max_tokens", mode="before")
    @classmethod
    def _check_max_tokens(cls, value: object) -> object:
        return _validate_optional_output_token_cap(value, "ai_roles.*.max_tokens")


class ExternalIntegrationConfig(_Strict):
    """An optional external integration. Disabled by default."""

    enabled: bool = Field(default=False)


class RunLimitsConfig(_Strict):
    """Hard caps on a single run (enforced in later phases)."""

    max_model_calls_per_issue: int = Field(default=20, ge=0)
    max_review_loops: int = Field(default=3, ge=0)
    max_ci_fix_loops: int = Field(default=2, ge=0)
    max_total_runtime_minutes: int = Field(default=60, ge=0)


class RealModelPlanningConfig(_Strict):
    """Per-project opt-in gating real model use for planning-adjacent commands.

    See ``docs/PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md`` §4 for the original
    design. This block is now **read**, by
    :func:`~ai_dev_orchestrator.plan.real_model_gate.check_real_model_planning_gate`,
    to gate the ``real-llm-smoke-test`` and ``generate-model-plan`` CLI commands:
    a real model call from either requires ``enabled: true`` **and** the exact
    requested model name to appear in ``allowed_models``. It fails closed by
    construction — an absent block is identical to an explicitly disabled one,
    and an empty ``allowed_models`` permits no model even when enabled.

    It holds **no credentials**: no api key, no base URL, no endpoint. Those are
    named by environment-variable *name* on :class:`ProviderConfig`, per the
    Phase 1 rule, and unknown fields here are rejected.

    This block is **not** authorization for the separate `controlled_review`
    capability (Phase 5F2E): the controlled reviewer takes its own opt-in, its
    own gate, and its model exclusively from ``controlled_review.model`` — never
    from here.
    """

    enabled: bool = Field(
        default=False,
        description="Whether this project may ever be planned with a real model.",
    )
    allowed_models: list[str] = Field(
        default_factory=list,
        description="Exact model names permitted for this project. Empty means "
        "no model is allowed, even when 'enabled' is true.",
    )
    allow_prompt_audit_files: bool = Field(
        default=False,
        description="Whether prompts/completions (i.e. issue text) may be "
        "written to disk by a future audited real path.",
    )

    @field_validator("allowed_models")
    @classmethod
    def _check_allowed_models(cls, models: list[str]) -> list[str]:
        seen: set[str] = set()
        for model in models:
            if not model.strip():
                raise ValueError("allowed_models entries must be non-blank strings")
            if model in seen:
                raise ValueError(f"duplicate model name in allowed_models: {model!r}")
            seen.add(model)
        return models


class ReadOnlyWorkspaceInspectionConfig(_Strict):
    """Per-project opt-in for **read-only workspace metadata inspection** (Phase 5D1).

    This is the first project-level block that can permit a command to touch the
    configured ``repo.workspace_path`` at all, and it permits the smallest
    possible touch: canonicalizing a path named by an approved plan and calling
    ``stat`` on it. It never authorizes reading file contents, listing a
    directory, running a command, editing a file, or calling a model.

    It fails closed by construction — an absent block is identical to an
    explicitly disabled one — and it holds **no credentials**: no API key, no
    base URL, no endpoint, no model name, and no environment-variable name.
    Unknown fields are rejected.
    """

    enabled: bool = Field(
        default=False,
        description="Whether this project's workspace may be inspected for "
        "path metadata at all. Absent or false means no workspace touch.",
    )
    max_inspected_files: int = Field(
        default=20,
        gt=0,
        le=100,
        description="Hard cap on how many approved-plan paths one invocation "
        "may canonicalize and stat. Exceeding it fails the whole run before "
        "the workspace is touched.",
    )
    allow_protected_paths: bool = Field(
        default=False,
        description="Whether a path classified PROTECTED by the Phase 1 path "
        "policy may be inspected. Forbidden and unlisted paths are refused "
        "regardless.",
    )


class ReadOnlyWorkspaceContentConfig(_Strict):
    """Per-project opt-in for **bounded read-only file-content reads** (Phase 5D2).

    Phase 5D1's :class:`ReadOnlyWorkspaceInspectionConfig` permits asking
    whether a path exists and how big it is. This block permits the strictly
    larger disclosure of asking *what the file says*, and it is deliberately a
    **separate** opt-in: a project that is willing to have its file names
    stat'd has not thereby agreed to have its source printed.

    Every field here is a ceiling, not a target. The caps bound how many files
    one invocation may open, how large any single file may be, and how many
    bytes may be emitted in total; redaction of obvious secret-like text is
    mandatory and has deliberately **no** off switch.

    It fails closed by construction — an absent block is identical to an
    explicitly disabled one — and it holds **no credentials**: no API key, no
    base URL, no endpoint, no model name, and no environment-variable name.
    Unknown fields are rejected.
    """

    enabled: bool = Field(
        default=False,
        description="Whether this project's workspace file contents may be "
        "read at all. Absent or false means no content read and no workspace "
        "touch.",
    )
    max_files: int = Field(
        default=10,
        gt=0,
        le=50,
        description="Hard cap on how many approved-plan paths one invocation "
        "may consider. Exceeding it fails the whole run before the workspace "
        "is touched.",
    )
    max_file_bytes: int = Field(
        default=50_000,
        gt=0,
        le=1_000_000,
        description="Hard cap on the size of any single file that may be "
        "read. A larger file is reported as too_large and never opened.",
    )
    max_total_bytes: int = Field(
        default=200_000,
        gt=0,
        le=5_000_000,
        description="Hard cap on the total bytes one invocation may read "
        "across all files. Once reaching it, later files are skipped unread.",
    )
    allow_protected_paths: bool = Field(
        default=False,
        description="Whether a path classified PROTECTED by the Phase 1 path "
        "policy may have its contents read. Forbidden and unlisted paths are "
        "refused regardless.",
    )


class WorkspaceWriteConfig(_Strict):
    """Per-project opt-in for the **controlled single-file writer** (Phase 5F2C).

    Phase 5D1's and 5D2's blocks permit *reading* a target workspace. This is the
    first block that can permit **writing** one, and it is deliberately the
    smallest opt-in that could carry that meaning: a switch and a size ceiling.

    It fails closed by construction — an absent block is identical to an
    explicitly disabled one — and while it is disabled the Phase 5F2C command
    refuses before the target workspace is touched at all.

    What it deliberately has **no field for**, each because granting it here
    would turn a per-invocation human decision into standing configuration, or
    would widen a capability this phase does not have:

    - no credential, API key, base URL, endpoint, or environment-variable name;
    - no model name and no model role;
    - no command, command allowlist, or verification entry;
    - no ``allow_protected_paths`` and no standing protected-write override —
      §26.6 rejects a project-config switch for protected writes, and Phase 5F2C
      refuses a protected destination outright;
    - no ``allow_create`` flag — Phase 5F2C refuses every ``create``;
    - no multi-file switch — Phase 5F2C requires exactly one change regardless
      of a larger configured ``workspace_policy.max_changed_files``;
    - no rollback, journal, backup, or retry setting — none of that machinery
      exists in this phase.

    ``workspace_policy.max_changed_files`` already exists and is **not**
    duplicated here. Phase 5F2C enforces both: the configured cap, and its own
    hard requirement of exactly one change. A ``max_changed_files`` of ``0``
    permits no write at all and is refused.
    """

    enabled: bool = Field(
        default=False,
        description="Whether this project's workspace may be written at all. "
        "Absent or false means no workspace touch and no write.",
    )
    max_file_bytes: int = Field(
        default=200_000,
        gt=0,
        le=1_000_000,
        description="Hard ceiling on the size of the file being edited, applied "
        "to both the pre-image read from disk and the post-image about to be "
        "written. A file outside it is refused, never truncated.",
    )


class ControlledVerificationConfig(_Strict):
    """Per-project opt-in for the **controlled verification slice** (Phase 5F2D).

    This is the first block in this repository that can authorize AIDO to execute
    **repository-controlled code**, and the distinction from everything before it
    matters more than its size suggests:

    - the Phase 5F2C Git adapter runs a fixed, AIDO-owned, read-only inspection
      set that is part of the writer's own correctness contract;
    - this block names a **project's own verification process** — a test runner,
      typically — which may import arbitrary project modules, execute
      ``conftest.py``, create files, reach the network, and spawn children.

    **Controlled invocation is not sandboxed execution.** AIDO controls *which*
    program is launched, with which exact arguments, in which directory, with
    which minimal environment, for how long, and how much output it may produce.
    It does **not** confine what that program then does. Phase 5F2D says so in
    its report rather than claiming otherwise.

    It fails closed by construction — an absent block is identical to an
    explicitly disabled one — and it deliberately has **no field** for any of:

    - a shell command string, a command line to split, or any shell syntax;
    - a working-directory override (cwd is always the canonical configured
      repository root);
    - a ``PATH`` lookup or an executable default (there is none: an absolute path
      must be given, and it is validated at run time);
    - interpolation, environment substitution, ``{path}`` templating, or any
      other place a model, an artifact, or a plan could inject a token;
    - environment or secret forwarding (the child environment is a fixed minimal
      allowlist, and no project may extend it);
    - multiple command profiles, command ids, or before/after hooks;
    - install, dependency, package-manager, Git or GitHub actions of any kind.

    In particular the L1 plan's ``required_verification`` is **not** wired here
    and never becomes command authority: it is planner-controlled prose, it may
    be produced by a model, and Phase 5F2D neither parses, splits, nor runs it.
    Execution authority comes only from this block plus explicit CLI consent.
    """

    enabled: bool = Field(
        default=False,
        description="Whether this project's configured verification process may "
        "be executed at all. Absent or false means nothing is launched.",
    )
    executable: str | None = Field(
        default=None,
        description="Absolute path to the one program that may be launched. "
        "There is no default and no PATH lookup; a relative name, a missing "
        "file, a directory, or a path inside the target workspace is refused at "
        "run time.",
    )
    args: list[str] = Field(
        default_factory=list,
        description="The exact ordered argv tail. Strings only, used verbatim: "
        "nothing is split, expanded, templated, or interpreted as shell syntax.",
    )
    timeout_seconds: int = Field(
        default=120,
        gt=0,
        le=3600,
        description="Hard wall-clock bound. The child is killed on expiry and "
        "the verification outcome is 'did not pass'.",
    )
    max_output_bytes: int = Field(
        default=200_000,
        gt=0,
        le=5_000_000,
        description="Hard ceiling on captured output, enforced DURING capture. "
        "Passing it kills the child and fails the verification; captured text is "
        "never presented as if it were the complete output.",
    )

    @field_validator("executable")
    @classmethod
    def _check_executable(cls, value: str | None) -> str | None:
        # Shape only. Absoluteness, existence, file-kind and workspace
        # separation are run-time properties and are checked at the gate, so a
        # disabled block can never make an unrelated command fail to load.
        if value is None:
            return None
        if not value.strip():
            raise ValueError(
                "controlled_verification.executable must be a non-blank absolute "
                "path, or absent"
            )
        if "\x00" in value:
            raise ValueError(
                "controlled_verification.executable must not contain a NUL byte"
            )
        return value

    @field_validator("args")
    @classmethod
    def _check_args(cls, values: list[str]) -> list[str]:
        for arg in values:
            if "\x00" in arg:
                raise ValueError(
                    "controlled_verification.args entries must not contain a NUL "
                    "byte"
                )
        return values


class ControlledReviewConfig(_Strict):
    """Per-project opt-in for the **controlled reviewer slice** (Phase 5F2E).

    This is the first block that can authorize AIDO to send **source-derived
    material** — one human-approved unified diff, selected approved-plan prose,
    and the redacted output of a verification run — to a model. Every earlier
    model-facing block carried issue text only; this one carries code.

    It is deliberately **not** :class:`RealModelPlanningConfig`. Planning
    authorization and review authorization are separate capabilities: a project
    that agreed its *issue text* may be planned by a model has not thereby agreed
    that its *source* may be reviewed by one, and neither block is ever consulted
    on the other's behalf.

    It fails closed by construction — an absent block is identical to an
    explicitly disabled one — and it deliberately has **no field** for any of:

    - an ``api_key``, ``base_url``, endpoint, credential, or
      environment-variable *name* — connection details come from the
      **configured provider's** environment names, and only after verification
      has passed: the five ``AIDO_LITELLM_*`` names for ``provider: "litellm"``,
      or ``AIDO_VLLM_BASE_URL`` plus the optional ``AIDO_VLLM_API_KEY`` for
      ``provider: "vllm"``. Only the configured provider's names are read;
    - a prompt template, system-prompt override, or arbitrary header;
    - a *transport* retry count — Phase 5F2E-RS1 forces the reviewer client's
      ``max_retries`` to ``0``, so one semantic attempt is exactly one
      HTTP/model request, and the number of semantic attempts is a fixed
      maximum of two rather than a configurable count;
    - a fixer, a second reviewer, a reviewer list, a ``fallback_model``, or any
      consensus/voting setting — this phase implements the reviewer role only,
      with exactly one model;
    - a full-file or repository-wide transmission switch.

    ``model`` is the **only** place a reviewer model may be named. There is no
    CLI ``--model`` override, no environment variable of either provider ever
    selects it — ``AIDO_LITELLM_DEFAULT_MODEL`` is overridden and there is no
    ``AIDO_VLLM_DEFAULT_MODEL`` at all — and matching is exact: no glob, prefix,
    or case folding.

    Phase 5F2E-V1 — two reviewer providers
    ---------------------------------------

    ``provider`` selects between the existing internal OpenAI-compatible LiteLLM
    path and a direct OpenAI-compatible vLLM endpoint, matched exactly and
    case-sensitively. ``vllm_allow_insecure_http`` is the only field it added; it
    applies to the vLLM provider only, ships ``false``, and is an
    acknowledgement of unencrypted transport rather than any claim that the
    transport is secure. There is still no provider list, provider priority,
    failover, registry, or endpoint field here.

    Phase 5F2E-V2 — structured vLLM reviewer output
    -----------------------------------------------

    ``vllm_structured_output`` is the only field V2 added. It applies to the
    vLLM provider only, ships ``false``, and asks the server to constrain
    **generation** to the ``ModelReviewResult`` JSON Schema. It exists because a
    controlled real-model trial produced a semantically correct review whose
    ``content`` was wrapped in a markdown fence — which the strict parser
    rejects, correctly — and the identical prompt with a JSON-Schema
    ``response_format`` produced one bare JSON object the *unmodified* parser
    accepted.

    Setting it with ``provider`` other than ``"vllm"`` is **refused at the
    review gate**, never silently ignored. There is deliberately no field for an
    arbitrary ``response_format``, a schema path, a schema string, a schema
    file, a structured-output *mode*, ``guided_json``, a grammar, or a regex,
    and no CLI flag reaches any of it.

    Phase 5F2E-RS1 — bounded reviewer runtime supervision
    -----------------------------------------------------

    Three narrow fields were added for **observable resource supervision** of a
    local reviewer model, whose cost is inference wall time, GPU occupancy,
    concurrent-request capacity and context occupancy rather than an API price.
    All three carry safe defaults, so every existing Phase 5F2E project config
    still loads unchanged and keeps exactly its previous behavior.

    They are deliberately **not** a generic resource-policy framework: there is
    no attempt count, no backoff curve, no per-role budget, no fallback model,
    no reviewer chain, and no CLI override for any of them.
    """

    enabled: bool = Field(
        default=False,
        description="Whether this project's approved change may be sent to a "
        "reviewer model at all. Absent or false means no model call.",
    )
    provider: str = Field(
        default="litellm",
        description="The reviewer provider. Exactly two values are supported, "
        "matched exactly and case-sensitively: 'litellm' (the existing internal "
        "OpenAI-compatible LiteLLM path) and 'vllm' (a direct OpenAI-compatible "
        "vLLM endpoint). Anything else — including 'openai', "
        "'openai_compatible', 'LiteLLM' or 'VLLM' — is refused at the review "
        "gate. There is no alias, no glob, no case folding, and no provider "
        "registry.",
    )
    model: str | None = Field(
        default=None,
        description="The exact reviewer model name. There is no default and no "
        "environment fallback; an enabled block without one is refused at the "
        "review gate.",
    )
    attempt_timeout_seconds: float = Field(
        default=90.0,
        gt=0,
        le=3600,
        allow_inf_nan=False,
        description="The maximum time AIDO WAITS for ONE reviewer HTTP/model "
        "call to complete, subject only to small local scheduling overhead. That "
        "bound is established by AIDO's own monotonic deadline in the reviewer "
        "supervisor, NOT by the client's timeout — an httpx timeout is a "
        "network-operation/inactivity timeout that a peer producing frequent "
        "activity can outlive. The reviewer's client also receives this value as "
        "a secondary network-inactivity timeout. It is NOT a process-style hard "
        "wall-clock kill: when the deadline wins, the worker performing the call "
        "is ABANDONED rather than stopped, and AIDO never claims that the "
        "request or the backend's inference stopped. Because neither release is "
        "observed, a stalled attempt is TERMINAL: no second request is issued.",
    )
    max_output_tokens: int | None = Field(
        default=None,
        description="OPTIONAL operator-requested model-output cap. Absent or "
        "null — the default — means AIDO imposes NO output-token ceiling: no "
        "OpenAI-compatible 'max_tokens' field is sent on either semantic "
        "reviewer attempt. A positive integer is an explicit operator-requested "
        "cap, sent verbatim as 'max_tokens' on BOTH attempts. Either way it is "
        "only a request: the provider/model/backend still has its own native "
        "context and output limits, which are backend capability limits rather "
        "than an AIDO-requested cap, and it says nothing about hidden reasoning "
        "or backend accounting. Zero and negative values are refused; they are "
        "not a way to spell 'unlimited'.",
    )
    compact_retry_on_unusable_output: bool = Field(
        default=False,
        description="Whether ONE bounded compact second semantic attempt may be "
        "made after a COMPLETED but unusable first response — that is, a "
        "response AIDO actually received, where either the provider reported an "
        "output-length limit or the strict parser rejected it. It deliberately "
        "does NOT cover a timeout: a client timeout is not evidence that the backend "
        "released its inference slot, so a second request could put a second "
        "concurrent job on the same model. Defaults to false, so a project "
        "keeps exactly one semantic attempt until it opts in. Even when true "
        "the hard maximum is TWO semantic attempts; there is no third, no "
        "configurable count, no retry-on-timeout switch, and no fallback model.",
    )

    vllm_allow_insecure_http: bool = Field(
        default=False,
        description="Whether this project explicitly permits source-derived "
        "reviewer material to be sent to a direct vLLM endpoint over PLAINTEXT "
        "HTTP. Applies to provider 'vllm' only; it is never consulted for the "
        "LiteLLM provider. Defaults to false, so an http:// vLLM endpoint is "
        "refused before any model request is issued. Setting it to true does "
        "NOT make the transport secure, encrypted, private, authenticated, "
        "company-approved, or safe for secrets — it records only that the "
        "project accepted an unencrypted reviewer transport.",
    )

    vllm_structured_output: bool = Field(
        default=False,
        description="Whether a direct-vLLM reviewer request carries the "
        "ModelReviewResult JSON Schema in the OpenAI-compatible "
        "response_format/json_schema field. Applies to provider 'vllm' only: "
        "setting it with any other provider is REFUSED at the review gate "
        "rather than silently ignored. Defaults to false, so every existing "
        "Phase 5F2E-V1 config and direct-vLLM deployment keeps exactly its "
        "accepted behavior. It constrains GENERATION only — the strict "
        "reviewer parser is unchanged and remains the final authority, and "
        "there is no fallback to an unstructured request if the server "
        "rejects the schema.",
    )

    @field_validator("provider")
    @classmethod
    def _check_provider(cls, value: str) -> str:
        # Shape only. Which providers are *supported* is enforced at the review
        # gate, so an unsupported value in a disabled block can never make an
        # unrelated command fail to load its config.
        if not value.strip():
            raise ValueError("controlled_review.provider must be a non-blank string")
        return value

    @field_validator("max_output_tokens", mode="before")
    @classmethod
    def _check_max_output_tokens(cls, value: object) -> object:
        return _validate_optional_output_token_cap(
            value, "controlled_review.max_output_tokens"
        )

    @field_validator("model")
    @classmethod
    def _check_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError(
                "controlled_review.model must be a non-blank exact model name, or "
                "absent"
            )
        return value


class ProjectConfig(_Strict):
    """Top-level typed project configuration."""

    project_id: str
    display_name: str
    repo: RepoConfig
    workspace_policy: WorkspacePolicyConfig = Field(
        default_factory=WorkspacePolicyConfig
    )

    allowed_paths: list[str] = Field(default_factory=list)
    protected_paths: list[str] = Field(default_factory=list)
    forbidden_paths: list[str] = Field(default_factory=list)

    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    ai_roles: dict[str, AIRoleConfig] = Field(default_factory=dict)
    external_integrations: dict[str, ExternalIntegrationConfig] = Field(
        default_factory=dict
    )
    run_limits: RunLimitsConfig = Field(default_factory=RunLimitsConfig)
    real_model_planning: RealModelPlanningConfig = Field(
        default_factory=RealModelPlanningConfig
    )
    read_only_workspace_inspection: ReadOnlyWorkspaceInspectionConfig = Field(
        default_factory=ReadOnlyWorkspaceInspectionConfig
    )
    read_only_workspace_content: ReadOnlyWorkspaceContentConfig = Field(
        default_factory=ReadOnlyWorkspaceContentConfig
    )
    workspace_write: WorkspaceWriteConfig = Field(
        default_factory=WorkspaceWriteConfig
    )
    controlled_verification: ControlledVerificationConfig = Field(
        default_factory=ControlledVerificationConfig
    )
    controlled_review: ControlledReviewConfig = Field(
        default_factory=ControlledReviewConfig
    )

    @property
    def path_rules(self) -> PathRulesConfig:
        """Group the flat path lists into a single rules object."""
        return PathRulesConfig(
            allowed_paths=self.allowed_paths,
            protected_paths=self.protected_paths,
            forbidden_paths=self.forbidden_paths,
        )
