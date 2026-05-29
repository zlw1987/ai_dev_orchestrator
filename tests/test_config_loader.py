"""Phase 1 tests: typed project-config loading."""

from pathlib import Path

import pytest

from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
from ai_dev_orchestrator.models import ExternalIntegrationConfig

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
    assert cfg.providers["litellm_local"].base_url_env == "LITELLM_BASE_URL"


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
