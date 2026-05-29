"""Load a project config YAML into a typed :class:`ProjectConfig`.

Phase 1 constraints (deliberate):

- Reads ONLY the config file path explicitly passed in.
- Does NOT scan the ``projects/`` directory.
- Does NOT check that the configured ``workspace_path`` exists or touch it.
- Does NOT read environment variables, resolve credentials, or call any service.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from ai_dev_orchestrator.models import ProjectConfig


class ConfigError(Exception):
    """Raised when a project config file cannot be read or parsed."""


def load_project_config(config_path: str | Path) -> ProjectConfig:
    """Load and validate a single project config YAML file.

    Args:
        config_path: Path to the YAML config file to load. Only this path is read.

    Returns:
        A validated :class:`ProjectConfig`.

    Raises:
        ConfigError: If the file is missing, is not valid YAML, is not a mapping,
            or fails schema validation.
    """
    path = Path(config_path)

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read config file {path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(
            f"Config in {path} must be a YAML mapping at the top level."
        )

    try:
        return ProjectConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Config in {path} failed validation:\n{exc}") from exc
