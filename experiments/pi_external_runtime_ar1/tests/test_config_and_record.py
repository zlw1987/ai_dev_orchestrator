"""Offline tests 29-32: generated config, record hygiene, ASCII safety.

Also covers the environment policy, the token-policy record shape, and the
fixture/verification baseline contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ar1.ascii_json import dumps_ascii, is_ascii_representable
from ar1.environment import (
    EnvironmentPolicyError,
    FORBIDDEN_NAME_FRAGMENTS,
    ROUTE_PLACEHOLDER_ENV_NAME,
    ROUTE_PLACEHOLDER_VALUE,
    audit_withheld_names,
    build_launch_environment,
)
from ar1.pi_config import describe_generated_config, write_disposable_pi_config
from ar1.protocol import contains_reasoning
from ar1.record import (
    CAPABILITY_BOUNDARY,
    RESIDUAL_LIMITATIONS,
    TOKEN_POLICY,
    record_header,
    scrub_check,
)
from ar1.verification import baseline_matches_seeded_defect, parse_pytest_summary


# -- 29. the generated models.json contains NO maxTokens -----------------------


@pytest.fixture()
def generated(tmp_path: Path):
    config_dir, settings_path, models_path = write_disposable_pi_config(
        str(tmp_path),
        provider_id="aido-ar1-qwen36-direct-vllm",
        model_id="Qwen3.6-27B-131K",
        base_url="http://synthetic.invalid:8000/v1",
    )
    return Path(config_dir), Path(settings_path), Path(models_path)


def test_generated_models_json_omits_max_tokens(generated):
    _config_dir, _settings_path, models_path = generated
    text = models_path.read_text(encoding="utf-8")
    assert "maxTokens" not in text
    parsed = json.loads(text)
    provider = parsed["providers"]["aido-ar1-qwen36-direct-vllm"]
    assert "maxTokens" not in provider
    for model in provider["models"]:
        assert "maxTokens" not in model


def test_token_policy_record_is_truthful():
    assert TOKEN_POLICY["aido_requested_max_output_tokens"] is None
    assert TOKEN_POLICY["runtime_native_max_tokens"] == "pi_catalog_default"
    assert TOKEN_POLICY["generated_models_json_omits_max_tokens"] is True


# -- 30. no shell-executed credential resolver --------------------------------


def test_generated_config_never_uses_shell_credential_resolution(generated):
    _config_dir, settings_path, models_path = generated
    models = json.loads(models_path.read_text(encoding="utf-8"))
    provider = models["providers"]["aido-ar1-qwen36-direct-vllm"]
    assert provider["apiKey"] == f"${ROUTE_PLACEHOLDER_ENV_NAME}"
    assert not provider["apiKey"].startswith("!")

    described = describe_generated_config(
        settings_path=str(settings_path), models_path=str(models_path)
    )
    assert described["api_key_resolution"] == "env_interpolation"
    assert described["api_key_uses_shell_command_resolution"] is False
    assert described["models_json_contains_max_tokens"] is False
    assert described["base_url_recorded"] is False
    assert described["settings_ambient_sources_emptied"] is True
    assert described["settings_default_project_trust"] == "never"


def test_the_route_placeholder_is_not_a_credential():
    assert ROUTE_PLACEHOLDER_VALUE == "no_api_key"


# -- 31/32. record hygiene -----------------------------------------------------


def test_record_scrub_rejects_an_endpoint_or_reasoning_leak():
    leaky = record_header(run={"note": "endpoint http://10.0.0.1:8000/v1"})
    result = scrub_check(leaky)
    assert result["clean"] is False

    reasoning_leak = record_header(run={"message": {"content": [{"type": "thinking", "thinking": "x"}]}})
    assert scrub_check(reasoning_leak)["clean"] is False
    assert contains_reasoning(reasoning_leak)


def test_a_clean_record_passes_the_scrub_and_is_ascii():
    record = record_header(
        runtime={"name": "pi", "version": "0.84.2", "launch_mode": "rpc"},
        provider_route={"logical_route_name": "qwen36-direct-vllm", "endpoint_recorded": False},
        model={"id": "Qwen3.6-27B-131K"},
        token_policy=TOKEN_POLICY,
        capability_boundary=CAPABILITY_BOUNDARY,
        residual_limitations=RESIDUAL_LIMITATIONS,
        run={"runtime_reported": {"text": "done"}, "orchestrator_observed": {"head_after": "abc"}},
    )
    result = scrub_check(record)
    assert result["clean"] is True, result["findings"]
    assert is_ascii_representable(record)
    assert dumps_ascii(record).isascii()


def test_non_ascii_runtime_text_is_escaped_not_dropped():
    record = record_header(run={"final_assistant_text": "caf\u00e9 \u2014 \u4f60\u597d"})
    emitted = dumps_ascii(record)
    assert emitted.isascii()
    assert "\\u00e9" in emitted
    assert json.loads(emitted)["run"]["final_assistant_text"] == "caf\u00e9 \u2014 \u4f60\u597d"


def test_capability_boundary_never_claims_a_sandbox():
    assert CAPABILITY_BOUNDARY["os_filesystem_isolation"] is False
    assert CAPABILITY_BOUNDARY["bash_exposed"] is False
    assert CAPABILITY_BOUNDARY["built_in_filesystem_tools_exposed"] is False
    assert CAPABILITY_BOUNDARY["production_workspace_access_authorized"] is False
    assert CAPABILITY_BOUNDARY["promotion_authorized"] is False
    assert CAPABILITY_BOUNDARY["reviewer_invoked"] is False
    statement = CAPABILITY_BOUNDARY["statement"]
    assert "NOT an OS sandbox" in statement
    for forbidden in ("was sandboxed", "OS-isolated", "no host file outside"):
        assert forbidden not in statement.replace("does NOT prove that no host file outside", "")


# -- environment policy --------------------------------------------------------


def test_launch_environment_is_explicit_and_withholds_profile_names(tmp_path: Path):
    built = build_launch_environment(
        node_executable=r"C:\Program Files\nodejs\node.exe",
        pi_config_dir=str(tmp_path / "pi_config"),
        git_executable=r"C:\Program Files\Git\cmd\git.exe",
    )
    assert built.profile_names_included == ()
    assert set(built.profile_names_withheld) == {"USERPROFILE", "HOME", "APPDATA"}
    assert built.environment["PI_CODING_AGENT_DIR"] == str(tmp_path / "pi_config")
    assert built.environment["PI_OFFLINE"] == "1"
    assert built.environment["PI_SKIP_VERSION_CHECK"] == "1"
    assert built.environment["PI_TELEMETRY"] == "0"
    assert built.environment[ROUTE_PLACEHOLDER_ENV_NAME] == ROUTE_PLACEHOLDER_VALUE
    assert built.path_narrowed is True
    assert built.path_entry_count <= 4

    audit = audit_withheld_names(built.environment)
    assert audit["sensitive_names_forwarded_to_runtime"] == []
    for name in built.environment:
        if name == ROUTE_PLACEHOLDER_ENV_NAME:
            continue
        assert not any(f in name.upper() for f in FORBIDDEN_NAME_FRAGMENTS), name


def test_an_unknown_profile_name_is_refused(tmp_path: Path):
    with pytest.raises(EnvironmentPolicyError):
        build_launch_environment(
            node_executable=r"C:\node\node.exe",
            pi_config_dir=str(tmp_path),
            include_profile_names=("SOMETHING_ELSE",),
        )


# -- verification contract -----------------------------------------------------


def test_pytest_summary_parsing_and_baseline_contract():
    output = "..F\n=== short test summary info ===\nFAILED test_calc.py::test_equal_to_limit_is_within - assert\n1 failed, 2 passed in 0.05s\n"
    counts, failed = parse_pytest_summary(output)
    assert counts == {"failed": 1, "passed": 2}
    assert failed == ("test_calc.py::test_equal_to_limit_is_within",)

    class _Outcome:
        passed = False
        counts = {"failed": 1, "passed": 2}
        failed_node_ids = ("test_calc.py::test_equal_to_limit_is_within",)

    ok, why = baseline_matches_seeded_defect(
        _Outcome(), expected_failing_test="test_equal_to_limit_is_within"
    )
    assert ok is True, why


def test_a_baseline_that_passes_is_not_the_seeded_defect():
    class _Outcome:
        passed = True
        counts = {"passed": 3}
        failed_node_ids = ()

    ok, why = baseline_matches_seeded_defect(
        _Outcome(), expected_failing_test="test_equal_to_limit_is_within"
    )
    assert ok is False
    assert "seeded defect is absent" in why


def test_the_verification_command_is_fixed_by_the_experiment():
    from ar1.verification import VERIFICATION_ARGS

    assert VERIFICATION_ARGS[:4] == ("-B", "-m", "pytest", "-q")
    assert "no:cacheprovider" in VERIFICATION_ARGS
    assert VERIFICATION_ARGS[-1] == "test_calc.py"


# -- disposable-tree cleanup ---------------------------------------------------


def test_disposable_tree_removal_clears_read_only_git_objects(tmp_path, git_executable):
    """Git marks loose objects read-only, and Windows refuses to unlink those.

    ``shutil.rmtree(..., ignore_errors=True)`` therefore leaves ``.git/objects``
    blobs behind silently. This helper clears the attribute and reports residue
    rather than claiming a success it cannot prove.
    """
    from ar1.fixture import create_synthetic_repository, remove_disposable_tree

    fixture = create_synthetic_repository(str(tmp_path / "root"), git_executable=git_executable)
    assert Path(fixture.repo_root).is_dir()

    result = remove_disposable_tree(fixture.experiment_root)
    assert result["removed"] is True
    assert result["residual_file_count"] == 0
    assert not Path(fixture.experiment_root).exists()


def test_removing_an_absent_tree_is_a_no_op(tmp_path):
    from ar1.fixture import remove_disposable_tree

    assert remove_disposable_tree(str(tmp_path / "nope")) == {
        "removed": True,
        "residual_file_count": 0,
    }
