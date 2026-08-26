"""I2-1 -- the qualification-owned child-environment builder (I2A design Sec. 9).

Every test here uses a SYNTHETIC ``ambient_environ`` mapping. No real
``os.environ`` value is ever read by the module under test or by these
tests.

**5F3B-I2-FU3.** ``build_child_environment`` no longer accepts a raw
``pi_config_dir``/``credential_value`` string -- it consumes an
authority-verified ``GeneratedQualificationConfig`` and a
``QualificationRouteSecretContext`` instead, and the returned
``LaunchEnvironment`` is immutable and self-validating.
"""

from __future__ import annotations

import dataclasses
import inspect
import os

import pytest

from qualification.i2_environment import (
    CREDENTIAL_ENV_VAR_NAME,
    FORBIDDEN_NAME_FRAGMENTS,
    EnvironmentPolicyError,
    WITHHELD_PROFILE_NAMES,
    audit_withheld_names,
    build_child_environment,
)
from qualification.i2_pi_config import write_qualification_pi_config
from qualification.i2_secret_context import build_secret_context

HOSTILE_AMBIENT_ENVIRON = {
    "SystemRoot": r"C:\Windows",
    "SystemDrive": "C:",
    "windir": r"C:\Windows",
    "ComSpec": r"C:\Windows\System32\cmd.exe",
    "PATHEXT": ".COM;.EXE;.BAT",
    "NUMBER_OF_PROCESSORS": "8",
    "PROCESSOR_ARCHITECTURE": "AMD64",
    "TEMP": r"C:\Users\synthetic\AppData\Local\Temp",
    "TMP": r"C:\Users\synthetic\AppData\Local\Temp",
    "PATH": r"C:\Windows\System32",
    # Hostile decoys -- none of these may reach the built environment.
    "OPENAI_API_KEY": "sk-synthetic-openai-decoy",
    "MINIMAX_API_KEY": "synthetic-minimax-decoy",
    "QWEN_TOKEN_PLAN_API_KEY": "synthetic-qwen-decoy",
    "AIDO_LITELLM_API_KEY": "synthetic-aido-litellm-decoy",
    "AIDO_LITELLM_BASE_URL": "https://litellm.example.invalid",
    "AIDO_VLLM_API_KEY": "synthetic-aido-vllm-decoy",
    "AIDO_VLLM_BASE_URL": "https://vllm.example.invalid",
    "HOME": r"C:\Users\synthetic",
    "APPDATA": r"C:\Users\synthetic\AppData\Roaming",
    "USERPROFILE": r"C:\Users\synthetic",
    "GITHUB_TOKEN": "synthetic-github-decoy",
    "ANTHROPIC_API_KEY": "synthetic-anthropic-decoy",
    "AWS_SECRET_ACCESS_KEY": "synthetic-aws-decoy",
}

CREDENTIAL_VALUE = "synthetic-b300-route-credential-001"
SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"


def _make_generated_config(tmp_path, *, suffix="a", model_id="qwen3-coder-next"):
    root = tmp_path / f"cfgroot_{suffix}"
    root.mkdir()
    return write_qualification_pi_config(str(root), model_id=model_id, base_url=SYNTHETIC_BASE_URL)


def _make_secret_context(*, api_key=CREDENTIAL_VALUE, model_id="qwen3-coder-next"):
    return build_secret_context(base_url=SYNTHETIC_BASE_URL, api_key=api_key, model_id=model_id)


def _build(tmp_path, **overrides):
    generated_config = overrides.pop("generated_config", None)
    if generated_config is None:
        generated_config = _make_generated_config(tmp_path)
    secret_context = overrides.pop("secret_context", None)
    if secret_context is None:
        secret_context = _make_secret_context()
    kwargs = dict(
        ambient_environ=HOSTILE_AMBIENT_ENVIRON,
        node_executable=r"C:\fake\node\node.exe",
        generated_config=generated_config,
        secret_context=secret_context,
    )
    kwargs.update(overrides)
    return build_child_environment(**kwargs)


# -- hostile names never propagate -------------------------------------------


def test_hostile_ambient_names_do_not_propagate(tmp_path):
    result = _build(tmp_path)
    for hostile_name in (
        "OPENAI_API_KEY",
        "MINIMAX_API_KEY",
        "QWEN_TOKEN_PLAN_API_KEY",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_BASE_URL",
        "AIDO_VLLM_API_KEY",
        "AIDO_VLLM_BASE_URL",
        "GITHUB_TOKEN",
        "ANTHROPIC_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
    ):
        assert hostile_name not in result.environment


def test_profile_names_never_forwarded(tmp_path):
    result = _build(tmp_path)
    for profile_name in WITHHELD_PROFILE_NAMES:
        assert profile_name in HOSTILE_AMBIENT_ENVIRON  # decoy actually present
        assert profile_name not in result.environment


def test_no_hostile_or_decoy_value_appears_anywhere_in_built_environment(tmp_path):
    result = _build(tmp_path)
    forbidden_values = {
        "sk-synthetic-openai-decoy",
        "synthetic-minimax-decoy",
        "synthetic-qwen-decoy",
        "synthetic-aido-litellm-decoy",
        "synthetic-aido-vllm-decoy",
        "synthetic-github-decoy",
        "synthetic-anthropic-decoy",
        "synthetic-aws-decoy",
    }
    assert not (forbidden_values & set(result.environment.values()))


# -- only the explicit allowlist propagates ----------------------------------


def test_only_baseline_pi_and_carrier_names_are_included(tmp_path):
    result = _build(tmp_path)
    expected = {
        "SystemRoot",
        "SystemDrive",
        "windir",
        "ComSpec",
        "PATHEXT",
        "NUMBER_OF_PROCESSORS",
        "PROCESSOR_ARCHITECTURE",
        "TEMP",
        "TMP",
        "PATH",
        "PI_CODING_AGENT_DIR",
        "PI_OFFLINE",
        "PI_SKIP_VERSION_CHECK",
        "PI_TELEMETRY",
        CREDENTIAL_ENV_VAR_NAME,
    }
    assert set(result.environment) == expected


def test_pi_owned_names_have_exact_values(tmp_path):
    generated = _make_generated_config(tmp_path)
    result = _build(tmp_path, generated_config=generated)
    assert result.environment["PI_CODING_AGENT_DIR"] == generated.config_dir
    assert result.environment["PI_OFFLINE"] == "1"
    assert result.environment["PI_SKIP_VERSION_CHECK"] == "1"
    assert result.environment["PI_TELEMETRY"] == "0"


# -- credential translation ---------------------------------------------------


def test_credential_value_translated_only_to_the_one_carrier(tmp_path):
    result = _build(tmp_path)
    assert result.environment[CREDENTIAL_ENV_VAR_NAME] == CREDENTIAL_VALUE
    other_values = [
        v for k, v in result.environment.items() if k != CREDENTIAL_ENV_VAR_NAME
    ]
    assert CREDENTIAL_VALUE not in other_values


def test_no_keyless_placeholder_path_exists():
    # There is no module-level placeholder constant to fall back to.
    import qualification.i2_environment as mod

    assert not hasattr(mod, "ROUTE_PLACEHOLDER_ENV_NAME")
    assert not hasattr(mod, "ROUTE_PLACEHOLDER_VALUE")


# -- candidate symmetry --------------------------------------------------------


def test_candidate_a_and_b_environment_policy_is_identical(tmp_path):
    # The builder takes no candidate parameter at all. Each run legitimately
    # gets its OWN disposable config directory (PI_CODING_AGENT_DIR), so
    # that is the one key allowed to differ; every other key/value,
    # including the credential carrier's value (same api_key used for
    # both), must be identical -- proving no hidden candidate-specific
    # branch anywhere in the builder.
    generated_a = _make_generated_config(tmp_path, suffix="cand_a", model_id="qwen3-coder-next")
    generated_b = _make_generated_config(tmp_path, suffix="cand_b", model_id="minimax-m2.7")
    secret_a = _make_secret_context(model_id="qwen3-coder-next")
    secret_b = _make_secret_context(model_id="minimax-m2.7")

    first = _build(tmp_path, generated_config=generated_a, secret_context=secret_a)
    second = _build(tmp_path, generated_config=generated_b, secret_context=secret_b)

    assert first.included_names == second.included_names
    env_a = dict(first.environment)
    env_b = dict(second.environment)
    differing_keys = {k for k in env_a if env_a[k] != env_b.get(k)}
    assert differing_keys == {"PI_CODING_AGENT_DIR"}


# -- audit --------------------------------------------------------------------


def test_audit_reports_zero_forwarded_sensitive_names(tmp_path):
    result = _build(tmp_path)
    audit = audit_withheld_names(
        ambient_environ=HOSTILE_AMBIENT_ENVIRON, built_environment=result.environment
    )
    assert audit["sensitive_names_forwarded_count"] == 0
    assert audit["sensitive_names_forwarded_to_child"] == []
    assert audit["profile_names_forwarded_to_child"] == []
    assert audit["sensitive_ambient_names_detected_count"] > 0


def test_credential_carrier_name_itself_contains_no_forbidden_fragment():
    upper = CREDENTIAL_ENV_VAR_NAME.upper()
    assert not any(fragment in upper for fragment in FORBIDDEN_NAME_FRAGMENTS)


# -- 5F3B-I2-FU1: the narrowed-PATH bypass is removed (required regression D) --


def test_build_child_environment_has_no_narrow_path_parameter():
    signature = inspect.signature(build_child_environment)
    assert "narrow_path" not in signature.parameters
    assert "inherit_path" not in signature.parameters
    assert "unsafe_path" not in signature.parameters


def test_hostile_ambient_path_is_not_forwarded_verbatim(tmp_path):
    hostile_path_environ = dict(HOSTILE_AMBIENT_ENVIRON)
    hostile_path_environ["PATH"] = os.pathsep.join(
        [
            r"C:\Windows\System32",
            r"C:\evil\credential-stealer",
            r"C:\Users\synthetic\.secret-tools",
            r"C:\malicious\payload",
        ]
    )
    result = _build(tmp_path, ambient_environ=hostile_path_environ)
    built_path = result.environment["PATH"]
    assert built_path != hostile_path_environ["PATH"]
    for hostile_entry in (
        r"C:\evil\credential-stealer",
        r"C:\Users\synthetic\.secret-tools",
        r"C:\malicious\payload",
    ):
        assert hostile_entry not in built_path


def test_narrowed_path_only_contains_approved_components(tmp_path):
    result = _build(tmp_path)
    entries = [p for p in result.environment["PATH"].split(os.pathsep) if p]
    approved = {r"C:\fake\node", r"C:\Windows\System32", r"C:\Windows"}
    assert set(entries) <= approved
    assert result.path_narrowed is True


# -- 5F3B-I2-FU1: LaunchEnvironment repr safety (required regression B) -------


def test_repr_of_launch_environment_does_not_leak_carrier_credential(tmp_path):
    result = _build(tmp_path)
    rendered = repr(result)
    assert CREDENTIAL_VALUE not in rendered
    for decoy_value in (
        "sk-synthetic-openai-decoy",
        "synthetic-minimax-decoy",
        "synthetic-aido-litellm-decoy",
    ):
        assert decoy_value not in rendered
    # Names are fine to show; the carrier NAME itself is not a secret.
    assert CREDENTIAL_ENV_VAR_NAME in rendered


def test_str_of_launch_environment_also_does_not_leak(tmp_path):
    result = _build(tmp_path)
    rendered = str(result)
    assert CREDENTIAL_VALUE not in rendered


def test_repr_of_launch_environment_does_not_leak_pi_config_dir(tmp_path):
    generated = _make_generated_config(tmp_path)
    result = _build(tmp_path, generated_config=generated)
    rendered = repr(result)
    assert generated.config_dir not in rendered


def test_launch_environment_raw_environment_field_is_repr_false(tmp_path):
    result = _build(tmp_path)
    field_by_name = {f.name: f for f in dataclasses.fields(result)}
    assert field_by_name["_raw_environment"].repr is False
    assert field_by_name["pi_config_dir"].repr is False
    assert "environment" not in field_by_name  # renamed; exposed only via the property


# -- 5F3B-I2-FU3 item 5: LaunchEnvironment is immutable (required regression 3)


def test_launch_environment_environment_cannot_be_mutated(tmp_path):
    result = _build(tmp_path)
    with pytest.raises(TypeError):
        result.environment["OPENAI_API_KEY"] = "oops"


def test_launch_environment_environment_cannot_be_mutated_for_existing_key(tmp_path):
    result = _build(tmp_path)
    with pytest.raises(TypeError):
        result.environment[CREDENTIAL_ENV_VAR_NAME] = "oops"


def test_launch_environment_environment_del_also_refused(tmp_path):
    result = _build(tmp_path)
    with pytest.raises(TypeError):
        del result.environment["PI_OFFLINE"]


def test_launch_environment_has_no_public_mutable_dict_attribute(tmp_path):
    result = _build(tmp_path)
    assert not hasattr(result, "_environment")
    # The only way to get a real, mutable dict is the explicit snapshot API.
    snapshot = result.as_launch_snapshot()
    assert isinstance(snapshot, dict)
    snapshot["OPENAI_API_KEY"] = "oops"
    # Mutating the snapshot never affects the retained object.
    assert "OPENAI_API_KEY" not in result.environment


def test_as_launch_snapshot_returns_a_fresh_independent_copy_each_time(tmp_path):
    result = _build(tmp_path)
    first_snapshot = result.as_launch_snapshot()
    second_snapshot = result.as_launch_snapshot()
    assert first_snapshot == second_snapshot
    assert first_snapshot is not second_snapshot
    first_snapshot["PI_OFFLINE"] = "mutated"
    assert second_snapshot["PI_OFFLINE"] == "1"
    assert result.environment["PI_OFFLINE"] == "1"


# -- 5F3B-I2-FU3 item 5: LaunchEnvironment self-validation --------------------


def test_launch_environment_rejects_path_narrowed_not_true(tmp_path):
    generated = _make_generated_config(tmp_path)
    with pytest.raises(EnvironmentPolicyError):
        _construct_launch_environment_directly(
            generated_config=generated, path_narrowed=False
        )
    with pytest.raises(EnvironmentPolicyError):
        _construct_launch_environment_directly(
            generated_config=generated, path_narrowed="true"
        )


def test_launch_environment_rejects_included_names_disagreement(tmp_path):
    generated = _make_generated_config(tmp_path)
    with pytest.raises(EnvironmentPolicyError):
        _construct_launch_environment_directly(
            generated_config=generated, included_names_override=("SOMETHING_ELSE",)
        )


def test_launch_environment_rejects_pi_config_dir_disagreement(tmp_path):
    generated = _make_generated_config(tmp_path)
    with pytest.raises(EnvironmentPolicyError):
        _construct_launch_environment_directly(
            generated_config=generated, pi_config_dir_override=r"C:\some\other\dir"
        )


def test_launch_environment_rejects_blank_credential_carrier(tmp_path):
    generated = _make_generated_config(tmp_path)
    with pytest.raises(EnvironmentPolicyError):
        _construct_launch_environment_directly(
            generated_config=generated, carrier_value_override=""
        )


def test_launch_environment_rejects_forbidden_name_present(tmp_path):
    generated = _make_generated_config(tmp_path)
    with pytest.raises(EnvironmentPolicyError):
        _construct_launch_environment_directly(
            generated_config=generated, inject_forbidden_name=True
        )


def _construct_launch_environment_directly(
    *,
    generated_config,
    path_narrowed=True,
    included_names_override=None,
    pi_config_dir_override=None,
    carrier_value_override=CREDENTIAL_VALUE,
    inject_forbidden_name=False,
):
    from qualification.i2_environment import LaunchEnvironment

    raw_environment = {
        "SystemRoot": r"C:\Windows",
        "PATH": r"C:\fake\node",
        "PI_CODING_AGENT_DIR": generated_config.config_dir,
        "PI_OFFLINE": "1",
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_TELEMETRY": "0",
        CREDENTIAL_ENV_VAR_NAME: carrier_value_override,
    }
    if inject_forbidden_name:
        raw_environment["OPENAI_API_KEY"] = "sk-synthetic-should-be-refused"
    included_names = (
        included_names_override
        if included_names_override is not None
        else tuple(sorted(raw_environment))
    )
    pi_config_dir = (
        pi_config_dir_override if pi_config_dir_override is not None else generated_config.config_dir
    )
    return LaunchEnvironment(
        _raw_environment=raw_environment,
        included_names=included_names,
        path_narrowed=path_narrowed,
        path_entry_count=1,
        pi_config_dir=pi_config_dir,
    )


# -- 5F3B-I2-FU3 item 3: generated config is the only PI_CODING_AGENT_DIR source
# (required regression 4) -----------------------------------------------------


def test_build_child_environment_has_no_raw_pi_config_dir_parameter():
    signature = inspect.signature(build_child_environment)
    assert "pi_config_dir" not in signature.parameters
    assert "credential_value" not in signature.parameters
    assert set(signature.parameters) == {
        "ambient_environ",
        "node_executable",
        "generated_config",
        "secret_context",
        "git_executable",
    }


def test_arbitrary_global_pi_config_dir_is_impossible_through_the_api(tmp_path):
    with pytest.raises(TypeError):
        build_child_environment(  # type: ignore[call-arg]
            ambient_environ=HOSTILE_AMBIENT_ENVIRON,
            node_executable=r"C:\fake\node\node.exe",
            pi_config_dir=r"C:\Users\synthetic\.pi\agent",
            secret_context=_make_secret_context(),
        )


def test_pi_coding_agent_dir_always_equals_the_generated_config_directory(tmp_path):
    generated = _make_generated_config(tmp_path, suffix="dirbind")
    result = _build(tmp_path, generated_config=generated)
    assert result.environment["PI_CODING_AGENT_DIR"] == generated.config_dir
    assert result.pi_config_dir == generated.config_dir


def test_generated_config_authority_is_reverified_at_consumption_boundary(tmp_path):
    from qualification.i2_pi_config import CleanupAuthorityError

    generated = _make_generated_config(tmp_path, suffix="tamper")
    marker_path = os.path.join(generated.config_dir, ".aido_i2_disposable_config")
    os.remove(marker_path)

    with pytest.raises(CleanupAuthorityError):
        _build(tmp_path, generated_config=generated)


# -- 5F3B-I2-FU3 item 4: child credential is sourced ONLY from secret_context
# (required regression 5) -----------------------------------------------------


def test_child_credential_cannot_differ_from_secret_context_api_key(tmp_path):
    key_a = "sk-synthetic-key-a-0001"
    secret_context = _make_secret_context(api_key=key_a)
    result = _build(tmp_path, secret_context=secret_context)
    assert result.environment[CREDENTIAL_ENV_VAR_NAME] == key_a

    key_b = "sk-synthetic-key-b-0002"
    assert key_b not in result.environment.values()


def test_build_child_environment_has_no_independent_credential_parameter():
    signature = inspect.signature(build_child_environment)
    assert "credential_value" not in signature.parameters
    assert "api_key" not in signature.parameters


# -- 5F3B-I2-FU3A item F: mandatory cross-object binding at build_child_environment
# (required regression: A generated + B secret -> environment builder refuses) --


def test_build_child_environment_refuses_mismatched_generated_and_secret_context(tmp_path):
    generated_a = _make_generated_config(tmp_path, suffix="cross_a", model_id="qwen3-coder-next")
    secret_b = _make_secret_context(model_id="minimax-m2.7")
    with pytest.raises(EnvironmentPolicyError):
        _build(tmp_path, generated_config=generated_a, secret_context=secret_b)


def test_build_child_environment_refuses_mismatched_base_url(tmp_path):
    from qualification.i2_secret_context import build_secret_context

    generated_a = _make_generated_config(tmp_path, suffix="cross_url", model_id="qwen3-coder-next")
    other_secret = build_secret_context(
        base_url="https://b300-other.example.invalid:8443/v1",
        api_key=CREDENTIAL_VALUE,
        model_id="qwen3-coder-next",
    )
    with pytest.raises(EnvironmentPolicyError):
        _build(tmp_path, generated_config=generated_a, secret_context=other_secret)


def test_build_child_environment_still_calls_the_stricter_integrity_check(tmp_path):
    # A tampered (post-generation-edited) config must also be refused HERE,
    # not just by describe_generated_config/verify_i2_identity_binding.
    import json

    from qualification.i2_environment import CREDENTIAL_ENV_VAR_NAME as CARRIER
    from qualification.i2_pi_config import PROVIDER_ID, CleanupAuthorityError

    generated = _make_generated_config(tmp_path, suffix="cross_tamper")
    raw = json.loads(open(generated.models_path, encoding="utf-8").read())
    raw["providers"][PROVIDER_ID]["baseUrl"] = "https://attacker.example.invalid/v1"
    with open(generated.models_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(raw, indent=2) + "\n")

    with pytest.raises(CleanupAuthorityError):
        _build(tmp_path, generated_config=generated)


def test_blank_secret_context_api_key_is_impossible_to_construct():
    # QualificationRouteSecretContext itself refuses a blank api_key
    # (I2A/FU2), so build_child_environment can never receive one -- the
    # defensive check inside it is unreachable in practice, and this test
    # proves WHY: the object cannot exist in that state at all.
    from qualification.i2_secret_context import SecretContextError

    with pytest.raises(SecretContextError):
        build_secret_context(base_url=SYNTHETIC_BASE_URL, api_key="   ", model_id="qwen3-coder-next")


# -- 5F3B-I2-FU3A item G: LaunchEnvironment breaks external mutable aliases ---


def test_constructor_dict_mutation_after_construction_does_not_affect_launch_environment(
    tmp_path,
):
    generated = _make_generated_config(tmp_path, suffix="alias_ctor")
    raw = {
        "SystemRoot": r"C:\Windows",
        "PATH": r"C:\fake\node",
        "PI_CODING_AGENT_DIR": generated.config_dir,
        "PI_OFFLINE": "1",
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_TELEMETRY": "0",
        CREDENTIAL_ENV_VAR_NAME: CREDENTIAL_VALUE,
    }
    from qualification.i2_environment import LaunchEnvironment

    launch = LaunchEnvironment(
        _raw_environment=raw,
        included_names=tuple(sorted(raw)),
        path_narrowed=True,
        path_entry_count=1,
        pi_config_dir=generated.config_dir,
    )

    # Mutate the CALLER's own dict reference after construction -- exactly
    # the independent-review reproduction.
    raw["OPENAI_API_KEY"] = "evil"
    assert "OPENAI_API_KEY" not in launch.environment
    assert set(launch.environment) == set(raw) - {"OPENAI_API_KEY"}


def test_launch_environment_environment_assignment_still_raises_typeerror_after_alias_fix(
    tmp_path,
):
    result = _build(tmp_path)
    with pytest.raises(TypeError):
        result.environment["OPENAI_API_KEY"] = "oops"


def test_as_launch_snapshot_mutation_never_affects_launch_environment(tmp_path):
    result = _build(tmp_path)
    snapshot = result.as_launch_snapshot()
    snapshot[CREDENTIAL_ENV_VAR_NAME] = "mutated-in-snapshot"
    snapshot["NEW_INJECTED_NAME"] = "evil"
    assert result.environment[CREDENTIAL_ENV_VAR_NAME] == CREDENTIAL_VALUE
    assert "NEW_INJECTED_NAME" not in result.environment
