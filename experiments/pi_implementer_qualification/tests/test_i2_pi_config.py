"""I2-2 -- the disposable Pi config generator for the B300 route (I2A Sec. 10).

**5F3B-I2-FU1.** ``write_qualification_pi_config`` no longer accepts
``provider_id``/``credential_env_var_name`` at all -- route identity is
fixed internally.

**5F3B-I2-FU3.** Authority is now a real, fresh, per-run 128-bit token
(never the FU2 fixed public marker text), and a generation failure after
the directory exists cleans itself up. ``describe_generated_config`` now
takes the typed ``GeneratedQualificationConfig`` object, not raw path
strings.
"""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import pytest

from qualification.i2_environment import CREDENTIAL_ENV_VAR_NAME
from qualification.i2_pi_config import (
    AUTHORITY_MARKER_FILENAME,
    AUTHORITY_MARKER_SCHEMA,
    PROVIDER_ID,
    GeneratedQualificationConfig,
    QualificationPiConfigCleanupError,
    QualificationPiConfigError,
    describe_generated_config,
    write_qualification_pi_config,
)
from qualification.i2_secret_context import InvalidBaseUrlError
from qualification.records import CANDIDATE_MODEL_IDS

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
SYNTHETIC_CREDENTIAL_VALUE_THAT_MUST_NEVER_APPEAR = "sk-synthetic-should-never-appear"

CANDIDATE_A_MODEL_ID = CANDIDATE_MODEL_IDS["A"]
CANDIDATE_B_MODEL_ID = CANDIDATE_MODEL_IDS["B"]


def _write(tmp_path, *, model_id: str, suffix: str):
    root = tmp_path / f"root_{suffix}"
    root.mkdir()
    return write_qualification_pi_config(
        str(root),
        model_id=model_id,
        base_url=SYNTHETIC_BASE_URL,
    )


# -- settings shape ------------------------------------------------------------


def test_settings_shape_exact(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    settings = json.loads(open(generated.settings_path, encoding="utf-8").read())
    for key in ("packages", "extensions", "skills", "prompts", "themes"):
        assert settings[key] == []
    assert settings["defaultProjectTrust"] == "never"
    assert settings["enableInstallTelemetry"] is False
    assert settings["enableAnalytics"] is False


def test_max_retries_is_zero(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    settings = json.loads(open(generated.settings_path, encoding="utf-8").read())
    assert settings["retry"]["provider"]["maxRetries"] == 0


# -- models.json shape -----------------------------------------------------


def test_models_provider_id_exact(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    models = json.loads(open(generated.models_path, encoding="utf-8").read())
    assert list(models["providers"]) == [PROVIDER_ID]


def test_models_provider_api_is_openai_completions(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    models = json.loads(open(generated.models_path, encoding="utf-8").read())
    assert models["providers"][PROVIDER_ID]["api"] == "openai-completions"


def test_candidate_model_id_exact(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    models = json.loads(open(generated.models_path, encoding="utf-8").read())
    ids = [m["id"] for m in models["providers"][PROVIDER_ID]["models"]]
    assert ids == [CANDIDATE_A_MODEL_ID]


def test_exactly_one_model_entry(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_B_MODEL_ID, suffix="b")
    models = json.loads(open(generated.models_path, encoding="utf-8").read())
    assert len(models["providers"][PROVIDER_ID]["models"]) == 1


def test_api_key_is_exact_env_reference(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    models = json.loads(open(generated.models_path, encoding="utf-8").read())
    assert models["providers"][PROVIDER_ID]["apiKey"] == f"${CREDENTIAL_ENV_VAR_NAME}"


def test_credential_value_absent_from_generated_config(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    raw_settings = open(generated.settings_path, encoding="utf-8").read()
    raw_models = open(generated.models_path, encoding="utf-8").read()
    assert SYNTHETIC_CREDENTIAL_VALUE_THAT_MUST_NEVER_APPEAR not in raw_settings
    assert SYNTHETIC_CREDENTIAL_VALUE_THAT_MUST_NEVER_APPEAR not in raw_models


def test_max_tokens_key_absent(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    raw_models = open(generated.models_path, encoding="utf-8").read()
    assert "maxTokens" not in raw_models


def test_no_shell_command_apikey_form(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    models = json.loads(open(generated.models_path, encoding="utf-8").read())
    assert "!" not in models["providers"][PROVIDER_ID]["apiKey"]


def test_base_url_recorded_in_generated_file_but_not_elsewhere(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    raw_models = open(generated.models_path, encoding="utf-8").read()
    assert SYNTHETIC_BASE_URL in raw_models  # necessarily present, per design Sec. 10


# -- candidate A/B symmetry ---------------------------------------------------


def test_candidate_a_and_b_configs_differ_only_in_model_identity(tmp_path):
    a = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    b = _write(tmp_path, model_id=CANDIDATE_B_MODEL_ID, suffix="b")

    models_a = json.loads(open(a.models_path, encoding="utf-8").read())
    models_b = json.loads(open(b.models_path, encoding="utf-8").read())

    provider_a = models_a["providers"][PROVIDER_ID]
    provider_b = models_b["providers"][PROVIDER_ID]

    assert provider_a["baseUrl"] == provider_b["baseUrl"]
    assert provider_a["api"] == provider_b["api"]
    assert provider_a["apiKey"] == provider_b["apiKey"]
    assert len(provider_a["models"]) == len(provider_b["models"]) == 1
    assert provider_a["models"][0]["id"] != provider_b["models"][0]["id"]
    assert provider_a["models"][0]["reasoning"] == provider_b["models"][0]["reasoning"]

    settings_a = json.loads(open(a.settings_path, encoding="utf-8").read())
    settings_b = json.loads(open(b.settings_path, encoding="utf-8").read())
    assert settings_a == settings_b

    # Distinct per-run authority tokens even for structurally-identical configs.
    assert a.authority_token != b.authority_token


# -- 5F3B-I2-FU2: route identity is not a caller-supplied parameter -----------


def test_generator_signature_has_no_route_identity_parameters():
    signature = inspect.signature(write_qualification_pi_config)
    param_names = set(signature.parameters)
    forbidden = {
        "api_key",
        "apikey",
        "credential_value",
        "secret",
        "key_value",
        "credential",
        "credential_env_var_name",
        "provider_id",
    }
    assert not (param_names & forbidden)
    assert param_names == {"experiment_root", "model_id", "base_url"}


def test_arbitrary_provider_id_is_impossible_through_the_api():
    with pytest.raises(TypeError):
        write_qualification_pi_config(  # type: ignore[call-arg]
            "unused", model_id=CANDIDATE_A_MODEL_ID, base_url=SYNTHETIC_BASE_URL,
            provider_id="openai",
        )


def test_openai_api_key_carrier_is_impossible_through_the_api():
    with pytest.raises(TypeError):
        write_qualification_pi_config(  # type: ignore[call-arg]
            "unused", model_id=CANDIDATE_A_MODEL_ID, base_url=SYNTHETIC_BASE_URL,
            credential_env_var_name="OPENAI_API_KEY",
        )


def test_minimax_api_key_carrier_is_impossible_through_the_api():
    with pytest.raises(TypeError):
        write_qualification_pi_config(  # type: ignore[call-arg]
            "unused", model_id=CANDIDATE_A_MODEL_ID, base_url=SYNTHETIC_BASE_URL,
            credential_env_var_name="MINIMAX_API_KEY",
        )


def test_arbitrary_unauthorized_model_id_is_refused(tmp_path):
    root = tmp_path / "root_unauthorized_model"
    root.mkdir()
    with pytest.raises(QualificationPiConfigError):
        write_qualification_pi_config(
            str(root), model_id="some-unauthorized-model", base_url=SYNTHETIC_BASE_URL
        )


def test_no_partial_config_after_identity_validation_failure(tmp_path):
    root = tmp_path / "root_no_partial"
    root.mkdir()
    with pytest.raises(QualificationPiConfigError):
        write_qualification_pi_config(
            str(root), model_id="some-unauthorized-model", base_url=SYNTHETIC_BASE_URL
        )
    # Nothing was created under root at all -- validation ran before mkdir.
    assert os.listdir(root) == []


def test_generated_config_always_uses_the_fixed_provider_and_carrier(tmp_path):
    from qualification.i2_environment import CREDENTIAL_ENV_VAR_NAME as CARRIER

    for candidate, model_id in CANDIDATE_MODEL_IDS.items():
        generated = _write(tmp_path, model_id=model_id, suffix=candidate)
        models = json.loads(open(generated.models_path, encoding="utf-8").read())
        assert list(models["providers"]) == [PROVIDER_ID]
        assert models["providers"][PROVIDER_ID]["apiKey"] == f"${CARRIER}"
        assert generated.provider_id == PROVIDER_ID
        assert generated.model_id == model_id


def test_blank_base_url_rejected(tmp_path):
    root = tmp_path / "root_blank_url"
    root.mkdir()
    with pytest.raises(InvalidBaseUrlError):
        write_qualification_pi_config(
            str(root), model_id=CANDIDATE_A_MODEL_ID, base_url=""
        )


def test_malformed_base_url_rejected_and_nothing_created(tmp_path):
    root = tmp_path / "root_malformed_url"
    root.mkdir()
    with pytest.raises(InvalidBaseUrlError):
        write_qualification_pi_config(
            str(root), model_id=CANDIDATE_A_MODEL_ID, base_url="not-a-url"
        )
    assert os.listdir(root) == []


# -- 5F3B-I2-FU2 item E: shared base-URL validator, no second rule set -------


def test_no_scheme_url_rejected_and_nothing_created(tmp_path):
    root = tmp_path / "root_no_scheme"
    root.mkdir()
    with pytest.raises(InvalidBaseUrlError):
        write_qualification_pi_config(
            str(root), model_id=CANDIDATE_A_MODEL_ID, base_url="b300-proxy.example.invalid/v1"
        )
    assert os.listdir(root) == []


def test_embedded_username_password_url_rejected_and_nothing_created(tmp_path):
    root = tmp_path / "root_userinfo"
    root.mkdir()
    with pytest.raises(InvalidBaseUrlError):
        write_qualification_pi_config(
            str(root),
            model_id=CANDIDATE_A_MODEL_ID,
            base_url="https://user:sk-synthetic-pw@b300-proxy.example.invalid/v1",
        )
    assert os.listdir(root) == []


def test_query_string_url_rejected_and_nothing_created(tmp_path):
    root = tmp_path / "root_query"
    root.mkdir()
    with pytest.raises(InvalidBaseUrlError):
        write_qualification_pi_config(
            str(root),
            model_id=CANDIDATE_A_MODEL_ID,
            base_url="https://b300-proxy.example.invalid/v1?token=sk-synthetic",
        )
    assert os.listdir(root) == []


def test_fragment_url_rejected_and_nothing_created(tmp_path):
    root = tmp_path / "root_fragment"
    root.mkdir()
    with pytest.raises(InvalidBaseUrlError):
        write_qualification_pi_config(
            str(root),
            model_id=CANDIDATE_A_MODEL_ID,
            base_url="https://b300-proxy.example.invalid/v1#sk-synthetic",
        )
    assert os.listdir(root) == []


def test_valid_http_and_https_b300_shapes_still_accepted(tmp_path):
    for scheme_url, suffix in (
        ("http://b300-proxy.example.invalid:8080/v1", "http_ok"),
        ("https://b300-proxy.example.invalid/v1", "https_ok"),
    ):
        root = tmp_path / f"root_{suffix}"
        root.mkdir()
        generated = write_qualification_pi_config(
            str(root), model_id=CANDIDATE_A_MODEL_ID, base_url=scheme_url
        )
        assert os.path.isfile(generated.models_path)


def test_malformed_url_error_never_echoes_the_value(tmp_path):
    root = tmp_path / "root_no_echo"
    root.mkdir()
    hostile_url = "https://user:sk-synthetic-embedded-secret@b300-internal.example.invalid/v1"
    with pytest.raises(InvalidBaseUrlError) as excinfo:
        write_qualification_pi_config(str(root), model_id=CANDIDATE_A_MODEL_ID, base_url=hostile_url)
    message = str(excinfo.value)
    assert hostile_url not in message
    assert "sk-synthetic-embedded-secret" not in message
    assert "b300-internal.example.invalid" not in message


# -- 5F3B-I2-FU3 item 1: real per-run authority, not a public fixed marker ----


def test_authority_marker_is_json_with_schema_and_binding_not_the_token(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="marker")
    marker_path = os.path.join(generated.config_dir, AUTHORITY_MARKER_FILENAME)
    assert os.path.isfile(marker_path)
    with open(marker_path, encoding="utf-8") as handle:
        document = json.loads(handle.read())
    assert document["schema"] == AUTHORITY_MARKER_SCHEMA
    assert isinstance(document["binding"], str) and document["binding"]
    # The raw token is NEVER written to disk -- the marker text must not
    # contain the in-memory authority_token value.
    assert generated.authority_token not in json.dumps(document)


def test_authority_token_is_fresh_and_at_least_128_bits(tmp_path):
    a = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="tok_a")
    b = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="tok_b")
    assert a.authority_token != b.authority_token
    # secrets.token_hex(16) -> 32 hex chars -> 128 bits.
    assert len(a.authority_token) >= 32
    int(a.authority_token, 16)  # must be valid hex


def test_authority_marker_contains_no_credential_endpoint_or_workspace_content(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="marker_content")
    marker_path = os.path.join(generated.config_dir, AUTHORITY_MARKER_FILENAME)
    with open(marker_path, encoding="utf-8") as handle:
        content = handle.read()
    assert SYNTHETIC_BASE_URL not in content
    assert generated.config_dir not in content
    assert CREDENTIAL_ENV_VAR_NAME not in content


def test_generated_authority_token_field_is_repr_false(tmp_path):
    import dataclasses

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="repr")
    field_by_name = {f.name: f for f in dataclasses.fields(generated)}
    assert field_by_name["authority_token"].repr is False


def test_repr_of_generated_config_never_leaks_authority_token(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="repr2")
    rendered = repr(generated)
    assert generated.authority_token not in rendered


# -- 5F3B-I2-FU3 item 2: generator cleans its own partial failure ------------


def test_injected_write_failure_leaves_no_partial_config(tmp_path, monkeypatch):
    root = tmp_path / "run_injected_failure"
    root.mkdir()

    original_write_text = Path.write_text

    def _failing_write_text(self, *args, **kwargs):
        if self.name == "models.json":
            raise OSError("synthetic disk failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _failing_write_text)

    with pytest.raises(OSError):
        write_qualification_pi_config(
            str(root), model_id=CANDIDATE_A_MODEL_ID, base_url=SYNTHETIC_BASE_URL
        )

    assert not (root / "i2_pi_config").exists()


def test_injected_write_failure_on_settings_leaves_no_partial_config(tmp_path, monkeypatch):
    root = tmp_path / "run_injected_failure_settings"
    root.mkdir()

    original_write_text = Path.write_text

    def _failing_write_text(self, *args, **kwargs):
        if self.name == "settings.json":
            raise OSError("synthetic disk failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _failing_write_text)

    with pytest.raises(OSError):
        write_qualification_pi_config(
            str(root), model_id=CANDIDATE_A_MODEL_ID, base_url=SYNTHETIC_BASE_URL
        )

    assert not (root / "i2_pi_config").exists()


def test_injected_write_failure_when_cleanup_also_fails_raises_bounded_error(tmp_path, monkeypatch):
    root = tmp_path / "run_double_failure"
    root.mkdir()

    original_write_text = Path.write_text

    def _failing_write_text(self, *args, **kwargs):
        if self.name == "models.json":
            raise OSError("synthetic disk failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _failing_write_text)

    import qualification.i2_pi_config as mod

    def _noop_rmtree(path, ignore_errors=False):
        return None

    monkeypatch.setattr(mod.shutil, "rmtree", _noop_rmtree)

    with pytest.raises(QualificationPiConfigCleanupError) as excinfo:
        write_qualification_pi_config(
            str(root), model_id=CANDIDATE_A_MODEL_ID, base_url=SYNTHETIC_BASE_URL
        )
    message = str(excinfo.value)
    assert str(root) not in message
    assert SYNTHETIC_BASE_URL not in message
    assert excinfo.value.reason_code == "PARTIAL_CONFIG_CLEANUP_UNVERIFIED"
    # The partial (endpoint-bearing) config directory still exists in this
    # synthetic double-failure scenario -- but the caller is now correctly
    # informed via a bounded error rather than silently succeeding.
    assert (root / "i2_pi_config").exists()


# -- 5F3B-I2-FU3A item H: token-generation failure before mkdir leaves nothing


def test_token_generation_failure_leaves_no_directory_at_all(tmp_path, monkeypatch):
    root = tmp_path / "run_token_gen_failure"
    root.mkdir()

    import qualification.i2_pi_config as mod

    def _failing_token_hex(nbytes):
        raise OSError("synthetic entropy-source failure")

    monkeypatch.setattr(mod.secrets, "token_hex", _failing_token_hex)

    with pytest.raises(OSError):
        write_qualification_pi_config(
            str(root), model_id=CANDIDATE_A_MODEL_ID, base_url=SYNTHETIC_BASE_URL
        )

    # Token generation now happens BEFORE mkdir -- a failure there leaves
    # nothing on disk at all, not even an empty i2_pi_config directory.
    assert os.listdir(root) == []


# -- 5F3B-I2-FU3A item A: genuine issuance authority, not just a marker ------


def test_self_forged_token_with_hand_built_marker_refused_via_public_api(tmp_path):
    # The same required regression as test_i2_cleanup's, exercised through
    # GeneratedQualificationConfig construction directly: a caller-chosen
    # token with a correctly-computed marker, but no genuine I2 issuance,
    # can never construct a valid capability object.
    from qualification.i2_pi_config import (
        AUTHORITY_MARKER_FILENAME,
        _compute_authority_binding,
    )

    victim_dir = tmp_path / "victim_pi_config_self_forged"
    victim_dir.mkdir()
    victim_file = victim_dir / "important.txt"
    victim_file.write_text("do not delete me", encoding="utf-8")
    (victim_dir / "settings.json").write_text("{}", encoding="utf-8")
    (victim_dir / "models.json").write_text("{}", encoding="utf-8")

    attacker_token = "entirely-self-chosen-token-not-issued-by-i2"
    binding = _compute_authority_binding(token=attacker_token, config_dir=victim_dir.resolve())
    (victim_dir / AUTHORITY_MARKER_FILENAME).write_text(
        json.dumps({"schema": AUTHORITY_MARKER_SCHEMA, "binding": binding}) + "\n",
        encoding="utf-8",
    )

    from qualification.i2_pi_config import CleanupAuthorityError

    with pytest.raises(CleanupAuthorityError) as excinfo:
        GeneratedQualificationConfig(
            config_dir=str(victim_dir),
            settings_path=str(victim_dir / "settings.json"),
            models_path=str(victim_dir / "models.json"),
            provider_id=PROVIDER_ID,
            model_id=CANDIDATE_A_MODEL_ID,
            authority_token=attacker_token,
        )
    assert excinfo.value.reason_code == "NOT_ISSUED_BY_I2"
    assert victim_file.read_text(encoding="utf-8") == "do not delete me"


# -- 5F3B-I2-FU3A item D: a genuine config cannot be relabeled -----------------


def test_genuine_config_cannot_be_relabeled_to_a_different_model_id(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="relabel")
    from qualification.i2_pi_config import CleanupAuthorityError

    with pytest.raises(CleanupAuthorityError) as excinfo:
        GeneratedQualificationConfig(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            provider_id=generated.provider_id,
            model_id=CANDIDATE_B_MODEL_ID,  # relabeled, same genuine token/path
            authority_token=generated.authority_token,
        )
    assert excinfo.value.reason_code == "ISSUED_METADATA_MISMATCH"


def test_genuine_config_cannot_be_relabeled_to_a_different_provider_id(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="relabel_provider")
    from qualification.i2_pi_config import CleanupAuthorityError

    with pytest.raises(CleanupAuthorityError) as excinfo:
        GeneratedQualificationConfig(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            provider_id="some-other-provider",
            model_id=generated.model_id,
            authority_token=generated.authority_token,
        )
    assert excinfo.value.reason_code == "ISSUED_METADATA_MISMATCH"


# -- 5F3B-I2-FU3A item C: post-generation content tampering fails closed ------


def test_tampered_api_key_literal_fails_complete_integrity(tmp_path):
    from qualification.i2_pi_config import (
        CleanupAuthorityError,
        verify_generated_config_integrity,
    )

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="tamper_apikey")
    raw = json.loads(Path(generated.models_path).read_text(encoding="utf-8"))
    raw["providers"][PROVIDER_ID]["apiKey"] = "sk-literal-synthetic-secret-not-env-ref"
    Path(generated.models_path).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(CleanupAuthorityError) as excinfo:
        verify_generated_config_integrity(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            authority_token=generated.authority_token,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
        )
    assert excinfo.value.reason_code == "MODELS_CONTENT_MISMATCH"
    # Cleanup authority (not content integrity) is still available.
    from qualification.i2_pi_config import verify_cleanup_authority

    verify_cleanup_authority(
        config_dir=generated.config_dir,
        settings_path=generated.settings_path,
        models_path=generated.models_path,
        authority_token=generated.authority_token,
        provider_id=generated.provider_id,
        model_id=generated.model_id,
    )  # must not raise


def test_tampered_model_id_fails_complete_integrity(tmp_path):
    from qualification.i2_pi_config import (
        CleanupAuthorityError,
        verify_generated_config_integrity,
    )

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="tamper_model")
    raw = json.loads(Path(generated.models_path).read_text(encoding="utf-8"))
    raw["providers"][PROVIDER_ID]["models"][0]["id"] = CANDIDATE_B_MODEL_ID
    Path(generated.models_path).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(CleanupAuthorityError) as excinfo:
        verify_generated_config_integrity(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            authority_token=generated.authority_token,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
        )
    assert excinfo.value.reason_code == "MODELS_CONTENT_MISMATCH"


def test_tampered_max_tokens_addition_fails_complete_integrity(tmp_path):
    from qualification.i2_pi_config import (
        CleanupAuthorityError,
        verify_generated_config_integrity,
    )

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="tamper_maxtokens")
    raw = json.loads(Path(generated.models_path).read_text(encoding="utf-8"))
    raw["providers"][PROVIDER_ID]["models"][0]["maxTokens"] = 4096
    Path(generated.models_path).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(CleanupAuthorityError) as excinfo:
        verify_generated_config_integrity(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            authority_token=generated.authority_token,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
        )
    assert excinfo.value.reason_code == "MODELS_CONTENT_MISMATCH"


def test_tampered_base_url_fails_complete_integrity(tmp_path):
    from qualification.i2_pi_config import (
        CleanupAuthorityError,
        verify_generated_config_integrity,
    )

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="tamper_baseurl")
    raw = json.loads(Path(generated.models_path).read_text(encoding="utf-8"))
    raw["providers"][PROVIDER_ID]["baseUrl"] = "https://attacker.example.invalid/v1"
    Path(generated.models_path).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(CleanupAuthorityError) as excinfo:
        verify_generated_config_integrity(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            authority_token=generated.authority_token,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
        )
    assert excinfo.value.reason_code == "MODELS_CONTENT_MISMATCH"


def test_tampered_settings_retry_policy_fails_complete_integrity(tmp_path):
    from qualification.i2_pi_config import (
        CleanupAuthorityError,
        verify_generated_config_integrity,
    )

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="tamper_settings")
    raw = json.loads(Path(generated.settings_path).read_text(encoding="utf-8"))
    raw["retry"]["provider"]["maxRetries"] = 5
    raw["defaultProjectTrust"] = "always"
    Path(generated.settings_path).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(CleanupAuthorityError) as excinfo:
        verify_generated_config_integrity(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            authority_token=generated.authority_token,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
        )
    assert excinfo.value.reason_code == "SETTINGS_CONTENT_MISMATCH"


def test_tampered_config_can_still_be_cleaned_up(tmp_path):
    # Item C: content integrity is never required for cleanup of a
    # known-issued config -- a tampered config must not be strandable.
    from qualification.i2_cleanup import scrub_generated_qualification_config

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="tamper_then_clean")
    raw = json.loads(Path(generated.models_path).read_text(encoding="utf-8"))
    raw["providers"][PROVIDER_ID]["models"][0]["id"] = CANDIDATE_B_MODEL_ID
    Path(generated.models_path).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    result = scrub_generated_qualification_config(generated)
    assert result.scrub_verified is True
    assert not os.path.exists(generated.config_dir)


def test_describe_generated_config_refuses_tampered_content(tmp_path):
    from qualification.i2_pi_config import CleanupAuthorityError

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="tamper_describe")
    raw = json.loads(Path(generated.models_path).read_text(encoding="utf-8"))
    raw["providers"][PROVIDER_ID]["baseUrl"] = "https://attacker.example.invalid/v1"
    Path(generated.models_path).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(CleanupAuthorityError) as excinfo:
        describe_generated_config(generated)
    assert excinfo.value.reason_code == "MODELS_CONTENT_MISMATCH"


# -- 5F3B-I2-FU3B: issuance registry encapsulation ----------------------------


def test_no_public_issuance_mutation_api_exists():
    # Item F / required test 1: the supported module surface exposes no
    # public issuance mutation (or lookup) function at all.
    from qualification import i2_issuance

    for forbidden_name in (
        "register_issuance",
        "finalize_issuance",
        "discard_issuance",
        "lookup_issuance",
    ):
        assert not hasattr(i2_issuance, forbidden_name)


def test_self_issued_victim_attack_refused_using_only_public_api(tmp_path):
    # Item G, the decisive regression: an attacker using ONLY the supported
    # public API -- never i2_issuance's private internals -- constructs an
    # arbitrary victim directory, an important.txt, a caller-chosen token,
    # and a marker whose binding is computed with the EXACT documented
    # public formula. Under FU3A alone this was already refused because
    # nothing had called register_issuance for that token/path -- but FU3A's
    # register_issuance was ITSELF public, so a determined caller could have
    # called it directly to manufacture that missing fact. FU3B closes that:
    # there is now no supported way to manufacture it at all.
    from qualification import i2_issuance
    from qualification.i2_pi_config import (
        AUTHORITY_MARKER_FILENAME,
        AUTHORITY_MARKER_SCHEMA,
        CleanupAuthorityError,
        _compute_authority_binding,
    )

    # There is no public register_issuance to call, at all -- confirmed
    # structurally, not merely "we chose not to call it".
    assert not hasattr(i2_issuance, "register_issuance")

    victim_dir = tmp_path / "victim_fu3b_self_issue"
    victim_dir.mkdir()
    victim_file = victim_dir / "important.txt"
    victim_file.write_text("do not delete me", encoding="utf-8")
    (victim_dir / "settings.json").write_text("{}", encoding="utf-8")
    (victim_dir / "models.json").write_text("{}", encoding="utf-8")

    attacker_token = "fu3b-attacker-chosen-token-entirely-on-their-own"
    binding = _compute_authority_binding(token=attacker_token, config_dir=victim_dir.resolve())
    (victim_dir / AUTHORITY_MARKER_FILENAME).write_text(
        json.dumps({"schema": AUTHORITY_MARKER_SCHEMA, "binding": binding}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CleanupAuthorityError) as excinfo:
        GeneratedQualificationConfig(
            config_dir=str(victim_dir),
            settings_path=str(victim_dir / "settings.json"),
            models_path=str(victim_dir / "models.json"),
            provider_id=PROVIDER_ID,
            model_id=CANDIDATE_A_MODEL_ID,
            authority_token=attacker_token,
        )
    assert excinfo.value.reason_code == "NOT_ISSUED_BY_I2"

    assert victim_dir.exists()
    assert victim_file.exists()
    assert victim_file.read_text(encoding="utf-8") == "do not delete me"
    assert (victim_dir / "settings.json").read_text(encoding="utf-8") == "{}"
    assert (victim_dir / "models.json").read_text(encoding="utf-8") == "{}"


def test_tamper_then_reattempted_finalization_cannot_restore_integrity_pass(tmp_path):
    # Item 6 / the exact independent-review attack #2, at the full
    # integration level: generate a genuine config, tamper models.json (so
    # complete integrity now fails), then attempt to re-finalize with the
    # TAMPERED file's own digest -- the same digest verify_generated_config_integrity
    # would need to see recorded in order to pass. One-shot finalization
    # must refuse this, and integrity must remain failed afterward.
    import hashlib

    from qualification import i2_issuance
    from qualification.i2_pi_config import (
        CleanupAuthorityError,
        verify_generated_config_integrity,
    )

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="fu3b_refinalize")

    raw = json.loads(Path(generated.models_path).read_text(encoding="utf-8"))
    raw["providers"][PROVIDER_ID]["baseUrl"] = "https://attacker.example.invalid/v1"
    Path(generated.models_path).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(CleanupAuthorityError) as excinfo:
        verify_generated_config_integrity(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            authority_token=generated.authority_token,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
        )
    assert excinfo.value.reason_code == "MODELS_CONTENT_MISMATCH"

    tampered_models_digest = hashlib.sha256(
        Path(generated.models_path).read_bytes()
    ).hexdigest()
    settings_digest = hashlib.sha256(Path(generated.settings_path).read_bytes()).hexdigest()

    # White-box: this is exactly the call independent review used to
    # restore a PASS under FU3A. It is now package-internal AND one-shot.
    with pytest.raises(i2_issuance.IssuanceError) as issuance_excinfo:
        i2_issuance._finalize_issuance(
            token=generated.authority_token,
            config_dir=generated.config_dir,
            settings_sha256=settings_digest,
            models_sha256=tampered_models_digest,
        )
    assert issuance_excinfo.value.reason_code == "ISSUANCE_ALREADY_FINALIZED"

    # Integrity is STILL refused -- the re-finalization attempt changed
    # nothing.
    with pytest.raises(CleanupAuthorityError) as excinfo_again:
        verify_generated_config_integrity(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            authority_token=generated.authority_token,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
        )
    assert excinfo_again.value.reason_code == "MODELS_CONTENT_MISMATCH"

    # The tampered-but-genuinely-issued config remains cleanable.
    from qualification.i2_cleanup import scrub_generated_qualification_config

    result = scrub_generated_qualification_config(generated)
    assert result.scrub_verified is True


def test_genuine_generation_still_passes_integrity_builds_and_describes(tmp_path):
    # Items 8/H: a real write_qualification_pi_config run is unaffected by
    # the encapsulation closure -- it still issues, finalizes once, and
    # every launch-capable consumption path still succeeds.
    from qualification.i2_environment import build_child_environment
    from qualification.i2_pi_config import verify_generated_config_integrity
    from qualification.i2_secret_context import build_secret_context

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="fu3b_genuine")

    verify_generated_config_integrity(
        config_dir=generated.config_dir,
        settings_path=generated.settings_path,
        models_path=generated.models_path,
        authority_token=generated.authority_token,
        provider_id=generated.provider_id,
        model_id=generated.model_id,
    )  # must not raise

    secret_context = build_secret_context(
        base_url=SYNTHETIC_BASE_URL, api_key="sk-synthetic-fu3b-genuine", model_id=CANDIDATE_A_MODEL_ID
    )
    launch = build_child_environment(
        ambient_environ={"SystemRoot": r"C:\Windows"},
        node_executable=r"C:\fake\node\node.exe",
        generated_config=generated,
        secret_context=secret_context,
    )
    assert launch.environment["PI_CODING_AGENT_DIR"] == generated.config_dir

    description = describe_generated_config(generated)  # must not raise
    assert description["models_model_ids"] == [CANDIDATE_A_MODEL_ID]


def test_successful_cleanup_discards_issuance_and_deauthorizes_the_object(tmp_path):
    # Item 10: after a verified cleanup, the SAME GeneratedQualificationConfig
    # object is no longer authorized -- the underlying issuance entry was
    # discarded, so a repeat cleanup attempt (or any complete-integrity
    # re-check) now fails NOT_ISSUED_BY_I2 rather than silently no-opping.
    from qualification.i2_cleanup import scrub_generated_qualification_config
    from qualification.i2_pi_config import CleanupAuthorityError, verify_cleanup_authority

    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="fu3b_discard")
    result = scrub_generated_qualification_config(generated)
    assert result.scrub_verified is True

    with pytest.raises(CleanupAuthorityError) as excinfo:
        verify_cleanup_authority(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            authority_token=generated.authority_token,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
        )
    # The directory itself is gone (CONFIG_DIR_NOT_A_DIRECTORY fires before
    # the registry is even consulted) -- proving the object is unusable, and
    # a second, independent proof that the registry entry is really gone
    # follows below via the white-box lookup.
    assert excinfo.value.reason_code == "CONFIG_DIR_NOT_A_DIRECTORY"

    from qualification import i2_issuance

    assert (
        i2_issuance._lookup_issuance(
            token=generated.authority_token, config_dir=generated.config_dir
        )
        is None
    )


# -- describe_generated_config (5F3B-I2-FU3: typed object only) --------------


def test_describe_generated_config_takes_typed_object(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="describe")
    signature = inspect.signature(describe_generated_config)
    assert set(signature.parameters) == {"generated"}


def test_describe_generated_config_never_reports_base_url_or_key(tmp_path):
    generated = _write(tmp_path, model_id=CANDIDATE_A_MODEL_ID, suffix="a")
    description = describe_generated_config(generated)
    serialized = json.dumps(description)
    assert SYNTHETIC_BASE_URL not in serialized
    assert description["base_url_recorded"] is False
    assert description["api_key_resolution"] == "env_interpolation"
    assert description["api_key_env_variable_name"] == CREDENTIAL_ENV_VAR_NAME
    assert description["models_json_contains_max_tokens"] is False
    assert description["settings_provider_max_retries"] == 0


def test_describe_generated_config_cannot_read_an_arbitrary_json_document(tmp_path):
    victim_dir = tmp_path / "victim_describe"
    victim_dir.mkdir()
    (victim_dir / "settings.json").write_text("{}", encoding="utf-8")
    (victim_dir / "models.json").write_text(
        json.dumps({"providers": {"evil": {"apiKey": "$EVIL", "models": [{"id": "evil"}]}}}),
        encoding="utf-8",
    )
    from qualification.i2_pi_config import CleanupAuthorityError

    forged = object.__new__(GeneratedQualificationConfig)
    object.__setattr__(forged, "config_dir", str(victim_dir))
    object.__setattr__(forged, "settings_path", str(victim_dir / "settings.json"))
    object.__setattr__(forged, "models_path", str(victim_dir / "models.json"))
    object.__setattr__(forged, "provider_id", "evil")
    object.__setattr__(forged, "model_id", "evil")
    object.__setattr__(forged, "authority_token", "not-the-real-token")

    with pytest.raises(CleanupAuthorityError):
        describe_generated_config(forged)
