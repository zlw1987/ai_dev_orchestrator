"""Typed project-config models for the AI Dev Orchestrator.

Phase 1: pure data models only. These describe the SHAPE of a project config.
They make no network calls, read no environment variables, and never store
secrets — provider connection details are referenced by environment-variable
*name* (e.g. ``base_url_env``), never by value.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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

    @property
    def path_rules(self) -> PathRulesConfig:
        """Group the flat path lists into a single rules object."""
        return PathRulesConfig(
            allowed_paths=self.allowed_paths,
            protected_paths=self.protected_paths,
            forbidden_paths=self.forbidden_paths,
        )
