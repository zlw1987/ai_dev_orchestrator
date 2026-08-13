"""Phase 1 tests: typed project-config loading.

Phase 4I extends this with the typed ``real_model_planning`` block — config
shape only. No environment variable is read, no client is constructed, no
socket is opened, and no CLI behavior changes.
"""

import builtins
import os
import socket
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
from ai_dev_orchestrator.models import (
    ExternalIntegrationConfig,
    RealModelPlanningConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = REPO_ROOT / "projects" / "mis_project.yaml.example"

MINIMAL_VALID = """
project_id: demo
display_name: Demo
repo:
  workspace_path: "C:/dev/demo"
  github_repo: "owner/demo"
  branch_prefix: "ai/demo"
allowed_paths:
  - "src/**"
forbidden_paths:
  - ".env"
"""


def _write(tmp_path: Path, text: str) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(text, encoding="utf-8")
    return cfg


def test_loads_valid_minimal_config(tmp_path):
    cfg = load_project_config(_write(tmp_path, MINIMAL_VALID))
    assert cfg.project_id == "demo"
    assert cfg.repo.github_repo == "owner/demo"
    # Defaults applied.
    assert cfg.repo.default_base_branch == "main"
    assert cfg.workspace_policy.deny_outside_workspace is True


def test_loads_the_example_config():
    cfg = load_project_config(EXAMPLE_CONFIG)
    assert cfg.project_id == "mis_project"
    assert "minimax-m2.7" == cfg.ai_roles["implementer"].model
    assert cfg.providers["litellm_local"].base_url_env == "AIDO_LITELLM_BASE_URL"


# Old unprefixed env names; superseded by the canonical AIDO_-prefixed names.
_DEPRECATED_ENV_NAMES = {"LITELLM_BASE_URL", "LITELLM_API_KEY"}


def test_example_configs_use_canonical_env_names():
    """Checked-in example configs must not reference the old unprefixed names."""
    examples = sorted((REPO_ROOT / "projects").glob("*.yaml.example"))
    assert examples, "expected at least one example project config"
    for example in examples:
        cfg = load_project_config(example)
        for name, provider in cfg.providers.items():
            referenced = {provider.base_url_env, provider.api_key_env}
            stale = referenced & _DEPRECATED_ENV_NAMES
            assert not stale, f"{example.name} provider {name!r} uses stale env names: {stale}"


def test_missing_required_field_fails(tmp_path):
    # No 'repo' block -> required field missing.
    bad = "project_id: x\ndisplay_name: X\n"
    with pytest.raises(ConfigError):
        load_project_config(_write(tmp_path, bad))


def test_unknown_field_fails(tmp_path):
    bad = MINIMAL_VALID + "\nbogus_field: 123\n"
    with pytest.raises(ConfigError):
        load_project_config(_write(tmp_path, bad))


def test_missing_file_fails(tmp_path):
    with pytest.raises(ConfigError):
        load_project_config(tmp_path / "does_not_exist.yaml")


def test_external_integrations_disabled_by_default_in_example():
    cfg = load_project_config(EXAMPLE_CONFIG)
    assert cfg.external_integrations  # present
    for integration in cfg.external_integrations.values():
        assert integration.enabled is False


def test_external_integration_model_default_is_disabled():
    assert ExternalIntegrationConfig().enabled is False


# -- Phase 4I: typed real_model_planning block --------------------------------

_ENABLED_BLOCK = """
real_model_planning:
  enabled: true
  allowed_models:
    - minimax-m2.7
    - qwen3.6-27b
  allow_prompt_audit_files: false
"""


def test_missing_real_model_planning_block_defaults_to_disabled(tmp_path):
    cfg = load_project_config(_write(tmp_path, MINIMAL_VALID))

    assert cfg.real_model_planning.enabled is False
    assert cfg.real_model_planning.allowed_models == []
    assert cfg.real_model_planning.allow_prompt_audit_files is False


def test_explicit_disabled_block_loads(tmp_path):
    text = MINIMAL_VALID + """
real_model_planning:
  enabled: false
  allowed_models: []
  allow_prompt_audit_files: false
"""
    cfg = load_project_config(_write(tmp_path, text))

    assert cfg.real_model_planning == RealModelPlanningConfig()


def test_missing_block_is_indistinguishable_from_explicit_disabled(tmp_path):
    absent_dir = tmp_path / "absent"
    explicit_dir = tmp_path / "explicit"
    absent_dir.mkdir()
    explicit_dir.mkdir()

    absent = load_project_config(_write(absent_dir, MINIMAL_VALID))
    explicit = load_project_config(
        _write(explicit_dir, MINIMAL_VALID + "\nreal_model_planning:\n  enabled: false\n")
    )

    assert absent.real_model_planning == explicit.real_model_planning


def test_enabled_with_allowed_models_loads(tmp_path):
    cfg = load_project_config(_write(tmp_path, MINIMAL_VALID + _ENABLED_BLOCK))

    assert cfg.real_model_planning.enabled is True
    assert cfg.real_model_planning.allowed_models == ["minimax-m2.7", "qwen3.6-27b"]


def test_enabled_with_empty_allowed_models_is_valid_config(tmp_path):
    """Valid *config*; permitting no model is the gate's job in a later phase."""
    text = MINIMAL_VALID + "\nreal_model_planning:\n  enabled: true\n  allowed_models: []\n"
    cfg = load_project_config(_write(tmp_path, text))

    assert cfg.real_model_planning.enabled is True
    assert cfg.real_model_planning.allowed_models == []


@pytest.mark.parametrize("blank", ['""', '"   "', '"\\t"'])
def test_blank_model_name_rejected(tmp_path, blank):
    text = MINIMAL_VALID + f"\nreal_model_planning:\n  enabled: true\n  allowed_models:\n    - {blank}\n"
    with pytest.raises(ConfigError):
        load_project_config(_write(tmp_path, text))


def test_duplicate_model_names_rejected(tmp_path):
    text = (
        MINIMAL_VALID
        + "\nreal_model_planning:\n  enabled: true\n  allowed_models:\n"
        "    - minimax-m2.7\n    - minimax-m2.7\n"
    )
    with pytest.raises(ConfigError):
        load_project_config(_write(tmp_path, text))


def test_extra_field_under_real_model_planning_rejected(tmp_path):
    text = MINIMAL_VALID + "\nreal_model_planning:\n  enabled: false\n  bogus: 1\n"
    with pytest.raises(ConfigError):
        load_project_config(_write(tmp_path, text))


@pytest.mark.parametrize(
    "credential_field",
    ["api_key", "base_url", "endpoint", "api_key_env", "base_url_env", "token"],
)
def test_credential_like_fields_rejected_as_extras(tmp_path, credential_field):
    text = (
        MINIMAL_VALID
        + f"\nreal_model_planning:\n  enabled: false\n  {credential_field}: \"nope\"\n"
    )
    with pytest.raises(ConfigError):
        load_project_config(_write(tmp_path, text))


def test_real_model_planning_model_defaults():
    cfg = RealModelPlanningConfig()

    assert cfg.enabled is False
    assert cfg.allowed_models == []
    assert cfg.allow_prompt_audit_files is False


def test_real_model_planning_has_no_credential_fields():
    fields = set(RealModelPlanningConfig.model_fields)

    assert fields == {"enabled", "allowed_models", "allow_prompt_audit_files"}
    for forbidden in ("api_key", "base_url", "endpoint", "token", "api_key_env"):
        assert forbidden not in fields


def test_example_config_ships_real_model_planning_disabled():
    cfg = load_project_config(EXAMPLE_CONFIG)

    assert cfg.real_model_planning.enabled is False
    assert cfg.real_model_planning.allowed_models == []
    assert cfg.real_model_planning.allow_prompt_audit_files is False


def test_config_loading_reads_no_env_and_opens_no_socket(tmp_path, monkeypatch):
    cfg_path = _write(tmp_path, MINIMAL_VALID + _ENABLED_BLOCK)
    raw = cfg_path.read_text(encoding="utf-8")

    def _blocked(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("config loading must not read env or reach the network")

    monkeypatch.setattr(os, "getenv", _blocked)
    monkeypatch.setattr(os.environ, "get", _blocked)
    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)

    # Validate the already-read text directly, so `open` may be blocked too.
    monkeypatch.setattr(builtins, "open", _blocked)
    import yaml

    from ai_dev_orchestrator.models import ProjectConfig

    parsed = ProjectConfig.model_validate(yaml.safe_load(raw))
    assert parsed.real_model_planning.allowed_models == ["minimax-m2.7", "qwen3.6-27b"]


def test_models_module_cannot_construct_a_client():
    from ai_dev_orchestrator import models as models_module

    module_globals = vars(models_module)
    for name in (
        "httpx",
        "requests",
        "LLMClient",
        "LLMClientConfig",
        "load_llm_client_config_from_env",
    ):
        assert name not in module_globals


def test_no_cli_behavior_added():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("version", "inspect-issue", "llm-smoke-test", "generate-plan"):
        assert command in result.stdout
    # Phase 4I added no command of its own. (`generate-model-plan` arrived much
    # later, in the separately authorized Phase 4L.)
    for absent in ("plan-from-model", "real-generate-plan"):
        assert absent not in result.stdout


def test_generate_plan_still_has_no_real_or_model_option():
    result = CliRunner().invoke(app, ["generate-plan", "--help"])

    assert result.exit_code == 0
    for absent in ("--live", "--real", "--model", "--use-env", "--github", "--fetch"):
        assert absent not in result.stdout


# -- Phase 5F2C: the controlled single-file write opt-in -----------------------


def test_workspace_write_defaults_to_disabled():
    from ai_dev_orchestrator.models import WorkspaceWriteConfig

    config = WorkspaceWriteConfig()

    assert config.enabled is False
    assert config.max_file_bytes == 200_000


def test_an_absent_workspace_write_block_is_identical_to_a_disabled_one(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text(
        "project_id: p\n"
        "display_name: P\n"
        "repo:\n"
        '  workspace_path: "C:/nowhere/never/read"\n'
        '  github_repo: "owner/repo"\n'
        '  branch_prefix: "ai/p"\n',
        encoding="utf-8",
    )

    config = load_project_config(path)

    assert config.workspace_write.enabled is False


def test_workspace_write_can_be_enabled_with_a_cap(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text(
        "project_id: p\n"
        "display_name: P\n"
        "repo:\n"
        '  workspace_path: "C:/nowhere/never/read"\n'
        '  github_repo: "owner/repo"\n'
        '  branch_prefix: "ai/p"\n'
        "workspace_write:\n"
        "  enabled: true\n"
        "  max_file_bytes: 50000\n",
        encoding="utf-8",
    )

    config = load_project_config(path)

    assert config.workspace_write.enabled is True
    assert config.workspace_write.max_file_bytes == 50_000


@pytest.mark.parametrize(
    "block",
    [
        "  allow_protected_paths: true\n",
        "  allow_create: true\n",
        "  max_changed_files: 5\n",
        "  rollback: true\n",
        "  write_journal: /tmp/journal\n",
        "  api_key: sk-not-allowed\n",
        "  command: pytest -q\n",
        "  model: minimax-m2.7\n",
    ],
)
def test_workspace_write_rejects_every_widening_key(tmp_path, block):
    """The block carries an enable switch and a size ceiling. Nothing else."""
    path = tmp_path / "project.yaml"
    path.write_text(
        "project_id: p\n"
        "display_name: P\n"
        "repo:\n"
        '  workspace_path: "C:/nowhere/never/read"\n'
        '  github_repo: "owner/repo"\n'
        '  branch_prefix: "ai/p"\n'
        "workspace_write:\n"
        "  enabled: true\n" + block,
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_project_config(path)


@pytest.mark.parametrize("value", [0, -1, 1_000_001])
def test_max_file_bytes_is_bounded(tmp_path, value):
    path = tmp_path / "project.yaml"
    path.write_text(
        "project_id: p\n"
        "display_name: P\n"
        "repo:\n"
        '  workspace_path: "C:/nowhere/never/read"\n'
        '  github_repo: "owner/repo"\n'
        '  branch_prefix: "ai/p"\n'
        "workspace_write:\n"
        "  enabled: true\n"
        f"  max_file_bytes: {value}\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_project_config(path)


def test_the_example_config_ships_workspace_write_disabled():
    raw = Path("projects/mis_project.yaml.example").read_text(encoding="utf-8")

    import yaml

    from ai_dev_orchestrator.models import ProjectConfig

    parsed = ProjectConfig.model_validate(yaml.safe_load(raw))
    assert parsed.workspace_write.enabled is False
