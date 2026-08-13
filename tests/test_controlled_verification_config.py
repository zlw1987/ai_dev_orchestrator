"""Phase 5F2D tests: the ``controlled_verification`` project config block.

This block is the **only** place a verification command may come from, so the
tests here are as much about what the block cannot express as about what it can:
no shell string, no PATH lookup, no default executable, no working-directory
override, no interpolation, no secret forwarding, and no second command profile.

Nothing in this file touches a workspace, launches a process, or reads an
environment variable.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
from ai_dev_orchestrator.models import ControlledVerificationConfig, ProjectConfig

BASE_CONFIG = """\
project_id: demo_project
display_name: Demo Project
repo:
  workspace_path: C:\\\\synthetic\\\\workspace
  github_repo: demo/widgets
  branch_prefix: ai/demo
allowed_paths:
  - "src/**"
"""


def _load(tmp_path, extra: str = "") -> ProjectConfig:
    path = tmp_path / "project.yaml"
    path.write_text(BASE_CONFIG + extra, encoding="utf-8")
    return load_project_config(path)


# -- Fails closed --------------------------------------------------------------


def test_an_absent_block_is_identical_to_an_explicitly_disabled_one(tmp_path):
    absent = _load(tmp_path)
    present = _load(
        tmp_path, "controlled_verification:\n  enabled: false\n"
    )

    assert absent.controlled_verification.enabled is False
    assert present.controlled_verification.enabled is False
    assert (
        absent.controlled_verification.model_dump()
        == present.controlled_verification.model_dump()
    )


def test_enabled_defaults_to_false():
    assert ControlledVerificationConfig().enabled is False


def test_there_is_no_executable_default():
    """No default, so there is nothing to silently fall back to."""
    assert ControlledVerificationConfig().executable is None
    assert ControlledVerificationConfig().args == []


def test_bounds_have_finite_defaults():
    settings = ControlledVerificationConfig()

    assert settings.timeout_seconds == 120
    assert settings.max_output_bytes == 200_000


# -- The shape it accepts ------------------------------------------------------


def test_an_enabled_block_carries_exactly_one_executable_and_an_exact_argv(tmp_path):
    project = _load(
        tmp_path,
        "controlled_verification:\n"
        "  enabled: true\n"
        '  executable: "C:\\\\tools\\\\python\\\\python.exe"\n'
        "  args:\n"
        '    - "-m"\n'
        '    - "pytest"\n'
        '    - "tests/test_targeted.py"\n'
        '    - "-q"\n'
        "  timeout_seconds: 90\n"
        "  max_output_bytes: 50000\n",
    )

    settings = project.controlled_verification
    assert settings.enabled is True
    assert settings.executable == "C:\\tools\\python\\python.exe"
    assert settings.args == ["-m", "pytest", "tests/test_targeted.py", "-q"]
    assert settings.timeout_seconds == 90
    assert settings.max_output_bytes == 50_000


def test_args_are_kept_verbatim_and_nothing_is_split_or_expanded(tmp_path):
    """An arg containing spaces, quotes and shell metacharacters stays ONE arg."""
    project = _load(
        tmp_path,
        "controlled_verification:\n"
        "  enabled: true\n"
        '  executable: "C:\\\\tools\\\\python.exe"\n'
        "  args:\n"
        '    - "-k"\n'
        '    - "one and two && three | four > five ${HOME} {path}"\n',
    )

    args = project.controlled_verification.args
    assert len(args) == 2
    assert args[1] == "one and two && three | four > five ${HOME} {path}"


# -- The shape it refuses ------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        # A shell command line, in any of the spellings someone might reach for.
        "command",
        "command_line",
        "shell",
        "shell_command",
        "script",
        # A working-directory override.
        "cwd",
        "working_directory",
        # Environment and secret forwarding.
        "env",
        "environment",
        "forward_env",
        "secrets",
        "api_key_env",
        # Command profiles, ids, hooks, and retries.
        "commands",
        "profiles",
        "command_id",
        "before",
        "after",
        "retries",
        "install",
        # Sourcing the command from the plan.
        "use_required_verification",
        "from_plan",
    ],
)
def test_no_field_exists_for_any_capability_this_phase_refuses(tmp_path, field):
    with pytest.raises(ConfigError):
        _load(
            tmp_path,
            "controlled_verification:\n  enabled: true\n  %s: something\n" % field,
        )


def test_a_nul_byte_in_the_executable_is_refused():
    with pytest.raises(ValidationError):
        ControlledVerificationConfig(executable="C:\\tools\\py\x00thon.exe")


def test_a_nul_byte_in_an_arg_is_refused():
    with pytest.raises(ValidationError):
        ControlledVerificationConfig(args=["-m", "pyt\x00est"])


def test_a_blank_executable_is_refused():
    with pytest.raises(ValidationError):
        ControlledVerificationConfig(executable="   ")


def test_a_non_string_arg_is_refused():
    with pytest.raises(ValidationError):
        ControlledVerificationConfig(args=["-m", 7])


@pytest.mark.parametrize("value", [0, -1, 100_000])
def test_the_timeout_must_be_positive_and_bounded(value):
    with pytest.raises(ValidationError):
        ControlledVerificationConfig(timeout_seconds=value)


@pytest.mark.parametrize("value", [0, -1, 50_000_000])
def test_the_output_cap_must_be_positive_and_bounded(value):
    with pytest.raises(ValidationError):
        ControlledVerificationConfig(max_output_bytes=value)


# -- No credential lives here --------------------------------------------------


def test_the_block_has_no_credential_or_model_field():
    fields = set(ControlledVerificationConfig.model_fields)

    assert fields == {
        "enabled",
        "executable",
        "args",
        "timeout_seconds",
        "max_output_bytes",
    }
    for forbidden in ("api_key", "token", "base_url", "endpoint", "model", "provider"):
        assert not any(forbidden in name for name in fields), forbidden
