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
    """Configuration for one AI role (implementer / reviewer / fixer)."""

    provider: str = Field(description="Key into the providers map.")
    model: str = Field(description="Model name exposed by the provider.")
    temperature: float = Field(default=0.2, ge=0.0)
    max_tokens: int = Field(default=8192, gt=0)
    can_edit_files: bool = Field(default=False)


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
    """Per-project opt-in for a future **real** model-backed L1 planner.

    Phase 4I ships the typed shape only — see
    ``docs/PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md`` §4. Nothing reads this
    block yet: there is no gate function, no environment read, no client, no
    CLI command, and no model call. It fails closed by construction — an absent
    block is identical to an explicitly disabled one.

    It holds **no credentials**: no api key, no base URL, no endpoint. Those are
    named by environment-variable *name* on :class:`ProviderConfig`, per the
    Phase 1 rule, and unknown fields here are rejected.
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

    @property
    def path_rules(self) -> PathRulesConfig:
        """Group the flat path lists into a single rules object."""
        return PathRulesConfig(
            allowed_paths=self.allowed_paths,
            protected_paths=self.protected_paths,
            forbidden_paths=self.forbidden_paths,
        )
