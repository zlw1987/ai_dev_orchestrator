"""I2-5 -- cleanup, phase-aware failure classification, and the pre-persistence
raw-diagnostic safety boundary (I2A Sec. 11/16/17/18).

Every test uses a synthetic, disposable directory under ``tmp_path``. No real
Pi process, config, or credential is ever involved.

**5F3B-I2-FU2 item A / 5F3B-I2-FU3 item 1.**
``scrub_generated_qualification_config`` takes ONLY a
``GeneratedQualificationConfig`` capability object -- never a raw path --
and that object is itself valid-by-construction against a REAL, fresh,
per-run 128-bit token (FU3: not FU2's fixed, forgeable public marker text).
These tests reproduce every independent-review counterexample: an arbitrary
victim directory with no marker, with the OLD FU2 public marker text, or
with a copied-schema-but-wrong-binding marker; a parent-root mix-up; a
missing/tampered marker; and a marker COPIED from a genuine config into a
different directory (path-bound authority) -- all refused with nothing
deleted. A genuine (including partially-generated-but-marked) config still
cleans up successfully.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil

import pytest

from qualification.i2_cleanup import (
    CleanupClassificationError,
    classify_cleanup_failure,
    prepare_diagnostic_text_for_retention,
    scrub_generated_qualification_config,
)
from qualification.i2_pi_config import (
    AUTHORITY_MARKER_FILENAME,
    AUTHORITY_MARKER_SCHEMA,
    CleanupAuthorityError,
    GeneratedQualificationConfig,
    write_qualification_pi_config,
)
from qualification.outcomes import AutonomousClassification
from qualification.safety import ArtifactSafetyContext
from qualification.validity import RunValidity

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
CREDENTIAL_ENV_VAR_NAME = "PI_QUALIFICATION_B300_ROUTE_KEY"
SYNTHETIC_CREDENTIAL_VALUE = "sk-synthetic-should-never-appear-in-models-json"

#: A placeholder identity triple for forgery-attempt tests where the
#: outcome is refusal regardless of these values (no marker exists, or the
#: path/marker checks fail before any binding comparison is even reached).
_PLACEHOLDER_PROVIDER_ID = "b300_pi_qualification"
_PLACEHOLDER_MODEL_ID = "qwen3-coder-next"
_PLACEHOLDER_TOKEN = "attacker-supplied-placeholder-token-0001"


# -- cleanup verification -------------------------------------------------


def test_successful_deletion_is_verified(tmp_path):
    root = tmp_path / "run_ok"
    root.mkdir()
    generated = write_qualification_pi_config(
        str(root),
        model_id="qwen3-coder-next",
        base_url=SYNTHETIC_BASE_URL,
    )

    # Before cleanup: the generated config exists, carries the synthetic
    # endpoint and the $ENV reference, and never the credential value.
    raw_models = open(generated.models_path, encoding="utf-8").read()
    assert SYNTHETIC_BASE_URL in raw_models
    assert f"${CREDENTIAL_ENV_VAR_NAME}" in raw_models
    assert SYNTHETIC_CREDENTIAL_VALUE not in raw_models

    result = scrub_generated_qualification_config(generated)
    assert result.existed is True
    assert result.removed is True
    assert result.verified_by_stat is True
    assert result.scrub_verified is True

    # After cleanup: directory absent, and absence is independently checkable.
    assert not os.path.exists(generated.config_dir)
    assert not os.path.exists(generated.models_path)


def test_failed_deletion_is_truthfully_reported(tmp_path, monkeypatch):
    root = tmp_path / "run_fail"
    root.mkdir()
    generated = write_qualification_pi_config(
        str(root),
        model_id="minimax-m2.7",
        base_url=SYNTHETIC_BASE_URL,
    )

    import qualification.i2_cleanup as mod

    def _fail_rmtree(path, ignore_errors=False):
        # Simulate a teardown that cannot actually remove the directory.
        return None

    monkeypatch.setattr(mod.shutil, "rmtree", _fail_rmtree)

    result = scrub_generated_qualification_config(generated)
    assert result.existed is True
    assert result.removed is False
    assert result.scrub_verified is False


# -- 5F3B-I2-FU2/FU3 item A: creation-time authority, required regressions --


def _forged_generated_config(
    *, config_dir, settings_path, models_path, token=_PLACEHOLDER_TOKEN
):
    return GeneratedQualificationConfig(
        config_dir=str(config_dir),
        settings_path=str(settings_path),
        models_path=str(models_path),
        provider_id=_PLACEHOLDER_PROVIDER_ID,
        model_id=_PLACEHOLDER_MODEL_ID,
        authority_token=token,
    )


def test_arbitrary_victim_directory_with_no_marker_cannot_be_constructed(tmp_path):
    victim_dir = tmp_path / "victim"
    victim_dir.mkdir()
    victim_file = victim_dir / "important.txt"
    victim_file.write_text("do not delete me", encoding="utf-8")

    with pytest.raises(CleanupAuthorityError) as excinfo:
        _forged_generated_config(
            config_dir=victim_dir,
            settings_path=victim_dir / "settings.json",
            models_path=victim_dir / "models.json",
        )
    assert excinfo.value.reason_code == "MARKER_MISSING"

    assert victim_dir.exists()
    assert victim_file.exists()
    assert victim_file.read_text(encoding="utf-8") == "do not delete me"


def test_arbitrary_victim_directory_with_old_public_marker_text_refused(tmp_path):
    # 5F3B-I2-FU2's fixed, public marker text -- the exact thing FU3 exists
    # to stop being sufficient authority on its own.
    victim_dir = tmp_path / "victim_old_marker"
    victim_dir.mkdir()
    victim_file = victim_dir / "important.txt"
    victim_file.write_text("do not delete me", encoding="utf-8")
    (victim_dir / AUTHORITY_MARKER_FILENAME).write_text(
        "pi-implementer-qualification-i2-config.v1\n", encoding="utf-8"
    )

    with pytest.raises(CleanupAuthorityError) as excinfo:
        _forged_generated_config(
            config_dir=victim_dir,
            settings_path=victim_dir / "settings.json",
            models_path=victim_dir / "models.json",
        )
    assert excinfo.value.reason_code == "MARKER_MALFORMED"

    assert victim_dir.exists()
    assert victim_file.exists()
    assert victim_file.read_text(encoding="utf-8") == "do not delete me"


def test_arbitrary_victim_directory_with_copied_schema_but_no_genuine_token_refused(tmp_path):
    # The attacker knows the PUBLIC schema string but has no genuine run
    # token, so they cannot compute a binding that will ever validate.
    victim_dir = tmp_path / "victim_fake_schema"
    victim_dir.mkdir()
    victim_file = victim_dir / "important.txt"
    victim_file.write_text("do not delete me", encoding="utf-8")
    fabricated_binding = hashlib.sha256(b"guessed-token:guessed-path").hexdigest()
    (victim_dir / AUTHORITY_MARKER_FILENAME).write_text(
        json.dumps({"schema": AUTHORITY_MARKER_SCHEMA, "binding": fabricated_binding}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CleanupAuthorityError) as excinfo:
        _forged_generated_config(
            config_dir=victim_dir,
            settings_path=victim_dir / "settings.json",
            models_path=victim_dir / "models.json",
        )
    assert excinfo.value.reason_code == "MARKER_BINDING_MISMATCH"

    assert victim_dir.exists()
    assert victim_file.exists()
    assert victim_file.read_text(encoding="utf-8") == "do not delete me"


def test_arbitrary_victim_directory_refused_at_cleanup_boundary_too(tmp_path):
    # Defense in depth: even if a GeneratedQualificationConfig-shaped object
    # reached scrub_generated_qualification_config through some path other
    # than normal construction, the function's OWN re-verification refuses
    # it independently. Simulated here by bypassing __post_init__ via
    # object.__new__, exactly the kind of bypass construction-time checking
    # alone cannot prevent.
    victim_dir = tmp_path / "victim2"
    victim_dir.mkdir()
    victim_file = victim_dir / "important.txt"
    victim_file.write_text("still here", encoding="utf-8")

    forged = object.__new__(GeneratedQualificationConfig)
    object.__setattr__(forged, "config_dir", str(victim_dir))
    object.__setattr__(forged, "settings_path", str(victim_dir / "settings.json"))
    object.__setattr__(forged, "models_path", str(victim_dir / "models.json"))
    object.__setattr__(forged, "provider_id", _PLACEHOLDER_PROVIDER_ID)
    object.__setattr__(forged, "model_id", _PLACEHOLDER_MODEL_ID)
    object.__setattr__(forged, "authority_token", _PLACEHOLDER_TOKEN)

    with pytest.raises(CleanupAuthorityError):
        scrub_generated_qualification_config(forged)

    assert victim_dir.exists()
    assert victim_file.exists()
    assert victim_file.read_text(encoding="utf-8") == "still here"


def test_marker_copied_from_genuine_config_does_not_authorize_another_directory(tmp_path):
    # Required regression 2 / item D: path-bound authority. Even with the
    # GENUINE token (known here only because this is a white-box test), a
    # marker copied verbatim to a different directory does not validate,
    # because its binding was computed for the ORIGINAL directory's path.
    root = tmp_path / "run_genuine_for_copy"
    root.mkdir()
    generated = write_qualification_pi_config(
        str(root), model_id="qwen3-coder-next", base_url=SYNTHETIC_BASE_URL
    )
    marker_src = os.path.join(generated.config_dir, AUTHORITY_MARKER_FILENAME)

    victim_dir = tmp_path / "victim_copy_target"
    victim_dir.mkdir()
    victim_file = victim_dir / "important.txt"
    victim_file.write_text("do not delete me either", encoding="utf-8")
    shutil.copyfile(marker_src, os.path.join(victim_dir, AUTHORITY_MARKER_FILENAME))

    with pytest.raises(CleanupAuthorityError) as excinfo:
        GeneratedQualificationConfig(
            config_dir=str(victim_dir),
            settings_path=str(victim_dir / "settings.json"),
            models_path=str(victim_dir / "models.json"),
            provider_id=generated.provider_id,
            model_id=generated.model_id,
            authority_token=generated.authority_token,
        )
    assert excinfo.value.reason_code == "MARKER_BINDING_MISMATCH"

    # Neither directory was touched: the original config is untouched too.
    assert victim_dir.exists()
    assert victim_file.exists()
    assert victim_file.read_text(encoding="utf-8") == "do not delete me either"
    assert os.path.isdir(generated.config_dir)
    assert os.path.isfile(generated.settings_path)


def test_self_forged_token_with_hand_built_marker_but_no_issuance_is_refused(tmp_path):
    # 5F3B-I2-FU3A's required authority regression: a caller mints its OWN
    # token, hand-computes the exact SAME public binding formula the real
    # marker uses, writes a syntactically-perfect marker into an arbitrary
    # victim directory, and drops settings.json/models.json alongside it --
    # but NEVER goes through write_qualification_pi_config, so this token
    # was never registered in the process-local i2_issuance registry.
    from qualification.i2_pi_config import (
        AUTHORITY_MARKER_FILENAME,
        AUTHORITY_MARKER_SCHEMA,
        _compute_authority_binding,
    )

    victim_dir = tmp_path / "victim_self_forged"
    victim_dir.mkdir()
    victim_file = victim_dir / "important.txt"
    victim_file.write_text("do not delete me", encoding="utf-8")
    (victim_dir / "settings.json").write_text("{}", encoding="utf-8")
    (victim_dir / "models.json").write_text("{}", encoding="utf-8")

    attacker_chosen_token = "attacker-picks-this-token-entirely-on-their-own"
    resolved_dir = victim_dir.resolve()
    correct_binding = _compute_authority_binding(token=attacker_chosen_token, config_dir=resolved_dir)
    (victim_dir / AUTHORITY_MARKER_FILENAME).write_text(
        json.dumps({"schema": AUTHORITY_MARKER_SCHEMA, "binding": correct_binding}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CleanupAuthorityError) as excinfo:
        _forged_generated_config(
            config_dir=victim_dir,
            settings_path=victim_dir / "settings.json",
            models_path=victim_dir / "models.json",
            token=attacker_chosen_token,
        )
    assert excinfo.value.reason_code == "NOT_ISSUED_BY_I2"

    # The correctly-computed marker alone was never sufficient authority --
    # construction failed, so cleanup was never even attempted.
    assert victim_dir.exists()
    assert victim_file.exists()
    assert victim_file.read_text(encoding="utf-8") == "do not delete me"
    assert (victim_dir / "settings.json").exists()
    assert (victim_dir / "models.json").exists()


def test_self_forged_token_also_refused_directly_at_cleanup_boundary(tmp_path):
    # Defense in depth, mirroring test_arbitrary_victim_directory_refused_at_
    # cleanup_boundary_too: even a GeneratedQualificationConfig-shaped object
    # that bypassed __post_init__ (so construction-time refusal cannot be
    # what stopped it) is refused again by scrub_generated_qualification_config
    # itself, because NOT_ISSUED_BY_I2 is re-checked there too.
    from qualification.i2_pi_config import (
        AUTHORITY_MARKER_FILENAME,
        AUTHORITY_MARKER_SCHEMA,
        _compute_authority_binding,
    )

    victim_dir = tmp_path / "victim_self_forged_bypass"
    victim_dir.mkdir()
    victim_file = victim_dir / "important.txt"
    victim_file.write_text("still here too", encoding="utf-8")

    attacker_chosen_token = "another-attacker-chosen-token-0002"
    resolved_dir = victim_dir.resolve()
    correct_binding = _compute_authority_binding(token=attacker_chosen_token, config_dir=resolved_dir)
    (victim_dir / AUTHORITY_MARKER_FILENAME).write_text(
        json.dumps({"schema": AUTHORITY_MARKER_SCHEMA, "binding": correct_binding}) + "\n",
        encoding="utf-8",
    )

    forged = object.__new__(GeneratedQualificationConfig)
    object.__setattr__(forged, "config_dir", str(victim_dir))
    object.__setattr__(forged, "settings_path", str(victim_dir / "settings.json"))
    object.__setattr__(forged, "models_path", str(victim_dir / "models.json"))
    object.__setattr__(forged, "provider_id", _PLACEHOLDER_PROVIDER_ID)
    object.__setattr__(forged, "model_id", _PLACEHOLDER_MODEL_ID)
    object.__setattr__(forged, "authority_token", attacker_chosen_token)

    with pytest.raises(CleanupAuthorityError) as excinfo:
        scrub_generated_qualification_config(forged)
    assert excinfo.value.reason_code == "NOT_ISSUED_BY_I2"

    assert victim_dir.exists()
    assert victim_file.exists()
    assert victim_file.read_text(encoding="utf-8") == "still here too"


def test_parent_experiment_root_passed_accidentally_is_refused(tmp_path):
    root = tmp_path / "run_parent_mixup"
    root.mkdir()
    generated = write_qualification_pi_config(
        str(root), model_id="qwen3-coder-next", base_url=SYNTHETIC_BASE_URL
    )
    marker_before = os.path.join(generated.config_dir, AUTHORITY_MARKER_FILENAME)
    assert os.path.isfile(marker_before)

    # Someone accidentally supplies the PARENT experiment root as config_dir,
    # while settings/models paths still point at the real child subdirectory.
    with pytest.raises(CleanupAuthorityError):
        GeneratedQualificationConfig(
            config_dir=str(root),
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
            authority_token=generated.authority_token,
        )

    # Nothing was deleted: neither the parent nor the genuine child survived
    # only by luck -- both are still fully intact.
    assert root.exists()
    assert os.path.isfile(marker_before)
    assert os.path.isfile(generated.settings_path)
    assert os.path.isfile(generated.models_path)


def test_marker_missing_after_construction_is_refused_at_cleanup(tmp_path):
    root = tmp_path / "run_marker_missing"
    root.mkdir()
    generated = write_qualification_pi_config(
        str(root), model_id="qwen3-coder-next", base_url=SYNTHETIC_BASE_URL
    )
    marker_path = os.path.join(generated.config_dir, AUTHORITY_MARKER_FILENAME)
    os.remove(marker_path)

    with pytest.raises(CleanupAuthorityError):
        scrub_generated_qualification_config(generated)

    # Refused BEFORE any delete: the directory and its real files remain.
    assert os.path.isdir(generated.config_dir)
    assert os.path.isfile(generated.settings_path)
    assert os.path.isfile(generated.models_path)


def test_marker_wrong_content_after_construction_is_refused_at_cleanup(tmp_path):
    root = tmp_path / "run_marker_wrong"
    root.mkdir()
    generated = write_qualification_pi_config(
        str(root), model_id="minimax-m2.7", base_url=SYNTHETIC_BASE_URL
    )
    marker_path = os.path.join(generated.config_dir, AUTHORITY_MARKER_FILENAME)
    with open(marker_path, "w", encoding="utf-8") as handle:
        handle.write("tampered-marker-content")

    with pytest.raises(CleanupAuthorityError):
        scrub_generated_qualification_config(generated)

    assert os.path.isdir(generated.config_dir)
    assert os.path.isfile(generated.settings_path)


def test_genuine_generated_config_cleanup_succeeds(tmp_path):
    root = tmp_path / "run_genuine"
    root.mkdir()
    generated = write_qualification_pi_config(
        str(root), model_id="qwen3-coder-next", base_url=SYNTHETIC_BASE_URL
    )
    result = scrub_generated_qualification_config(generated)
    assert result.scrub_verified is True
    assert not os.path.exists(generated.config_dir)


def test_partially_generated_config_with_valid_marker_can_still_be_cleaned(tmp_path):
    # Simulate an interrupted write: only the marker exists (settings.json /
    # models.json were never written), but the marker itself is GENUINE --
    # produced with the real per-run token/binding scheme AND a genuine
    # 5F3B-I2-FU3A issuance registration, not merely hand-faked. This is
    # what write_qualification_pi_config's own self-cleanup path deals with
    # internally; a caller reconstructing the same shape must go through the
    # same two steps (register, then mark) to be genuinely authorized.
    import secrets

    from qualification import i2_issuance
    from qualification.i2_pi_config import _write_authority_marker

    root = tmp_path / "run_partial"
    root.mkdir()
    config_dir = root / "i2_pi_config"
    config_dir.mkdir()
    token = secrets.token_hex(16)
    i2_issuance._register_issuance(
        token=token,
        config_dir=config_dir,
        provider_id=_PLACEHOLDER_PROVIDER_ID,
        model_id=_PLACEHOLDER_MODEL_ID,
    )
    _write_authority_marker(config_dir=config_dir, token=token)

    partial = GeneratedQualificationConfig(
        config_dir=str(config_dir),
        settings_path=str(config_dir / "settings.json"),
        models_path=str(config_dir / "models.json"),
        provider_id=_PLACEHOLDER_PROVIDER_ID,
        model_id=_PLACEHOLDER_MODEL_ID,
        authority_token=token,
    )
    result = scrub_generated_qualification_config(partial)
    assert result.existed is True
    assert result.scrub_verified is True
    assert not config_dir.exists()


def test_cleanup_authority_error_never_echoes_the_path(tmp_path):
    victim_dir = tmp_path / "victim3"
    victim_dir.mkdir()
    with pytest.raises(CleanupAuthorityError) as excinfo:
        _forged_generated_config(
            config_dir=victim_dir,
            settings_path=victim_dir / "settings.json",
            models_path=victim_dir / "models.json",
        )
    message = str(excinfo.value)
    assert str(victim_dir) not in message
    assert excinfo.value.reason_code == "MARKER_MISSING"


# -- phase-aware cleanup failure classification --------------------------


def test_cleanup_failure_with_zero_prompts_is_infrastructure_refusal():
    classification = classify_cleanup_failure(semantic_prompts_sent=0)
    assert classification.semantic_prompts_sent == 0
    assert (
        classification.autonomous_classification
        == AutonomousClassification.INFRASTRUCTURE_REFUSAL
    )
    assert classification.run_validity is None
    assert classification.scoring_eligible is False


def test_cleanup_failure_with_one_prompt_is_infrastructure_contaminated():
    classification = classify_cleanup_failure(semantic_prompts_sent=1)
    assert classification.semantic_prompts_sent == 1
    assert classification.autonomous_classification is None
    assert classification.run_validity == RunValidity.INFRASTRUCTURE_CONTAMINATED
    assert classification.scoring_eligible is False


def test_prompt_count_is_never_rewritten_by_classification():
    zero = classify_cleanup_failure(semantic_prompts_sent=0)
    one = classify_cleanup_failure(semantic_prompts_sent=1)
    assert zero.semantic_prompts_sent == 0
    assert one.semantic_prompts_sent == 1


def test_invalid_prompt_count_is_refused():
    with pytest.raises(CleanupClassificationError):
        classify_cleanup_failure(semantic_prompts_sent=2)
    with pytest.raises(CleanupClassificationError):
        classify_cleanup_failure(semantic_prompts_sent=-1)


# -- pre-persistence raw-diagnostic safety boundary -----------------------


SYNTHETIC_API_KEY = "sk-synthetic-diagnostic-needle-0001"
SYNTHETIC_ENDPOINT_HOST = "b300-proxy.example.invalid"
SYNTHETIC_WORKSPACE_PATH = r"C:\fake\workspace\qualification_run_0001"
SYNTHETIC_PIPE_NAME = r"\\.\pipe\synthetic-qualification-pipe"
SYNTHETIC_CAPABILITY_ID = "synthetic-capability-id-0001"

FULL_SAFETY = ArtifactSafetyContext(
    endpoint_host=SYNTHETIC_ENDPOINT_HOST,
    api_key=SYNTHETIC_API_KEY,
    bearer_token=None,
    broker_token=None,
    pipe_name=SYNTHETIC_PIPE_NAME,
    capability_id=SYNTHETIC_CAPABILITY_ID,
    workspace_absolute_path=SYNTHETIC_WORKSPACE_PATH,
)


def test_synthetic_api_key_text_refused():
    result = prepare_diagnostic_text_for_retention(
        f"the request failed with key {SYNTHETIC_API_KEY}", safety=FULL_SAFETY
    )
    assert result.retention_ready is False
    assert result.text is None
    assert "api_key_value_present" in result.scrub["findings"]


def test_endpoint_host_text_refused():
    result = prepare_diagnostic_text_for_retention(
        f"connection reached {SYNTHETIC_ENDPOINT_HOST}", safety=FULL_SAFETY
    )
    assert result.retention_ready is False
    assert result.text is None
    assert "endpoint_host_value_present" in result.scrub["findings"]


def test_absolute_workspace_path_text_refused():
    result = prepare_diagnostic_text_for_retention(
        f"wrote to {SYNTHETIC_WORKSPACE_PATH}", safety=FULL_SAFETY
    )
    assert result.retention_ready is False
    assert result.text is None
    assert "workspace_absolute_path_present" in result.scrub["findings"]


def test_pipe_name_text_refused():
    result = prepare_diagnostic_text_for_retention(
        f"pipe was {SYNTHETIC_PIPE_NAME}", safety=FULL_SAFETY
    )
    assert result.retention_ready is False
    assert result.text is None


def test_capability_id_text_refused():
    result = prepare_diagnostic_text_for_retention(
        f"capability {SYNTHETIC_CAPABILITY_ID} bound", safety=FULL_SAFETY
    )
    assert result.retention_ready is False
    assert result.text is None


def test_reasoning_needle_refused():
    result = prepare_diagnostic_text_for_retention(
        "the model privately reasoned about the fix before answering",
        safety=ArtifactSafetyContext.none_declared(),
        field="reasoning",
    )
    assert result.retention_ready is False
    assert result.text is None
    assert "reasoning_content_present" in result.scrub["findings"]


def test_safe_text_is_retention_ready():
    result = prepare_diagnostic_text_for_retention(
        "verification completed: 6 passed, 0 failed",
        safety=ArtifactSafetyContext.none_declared(),
    )
    assert result.retention_ready is True
    assert result.text == "verification completed: 6 passed, 0 failed"
    assert result.scrub["clean"] is True


def test_safe_text_under_full_safety_context_still_eligible():
    result = prepare_diagnostic_text_for_retention(
        "verification completed: 6 passed, 0 failed", safety=FULL_SAFETY
    )
    assert result.retention_ready is True
    assert result.text is not None


def test_refused_result_never_carries_the_raw_unsafe_text():
    raw = f"leak attempt {SYNTHETIC_API_KEY} and more"
    result = prepare_diagnostic_text_for_retention(raw, safety=FULL_SAFETY)
    serialized = json.dumps(
        {"retention_ready": result.retention_ready, "text": result.text}
    )
    assert SYNTHETIC_API_KEY not in serialized


# -- 5F3B-I2-FU1 item 8: the diagnostic-scrub boundary is preserved, and is
# the ONLY path by which route/preflight/provider raw text can become
# retention-ready. No second scanner is added anywhere -- every test below
# calls the SAME `prepare_diagnostic_text_for_retention` / `qualification_scrub_check`
# I1 already shipped. -------------------------------------------------------


def test_route_raw_error_text_cannot_become_retention_ready_without_the_scrub_path():
    # A route-check style raw error, carrying an endpoint and an API key --
    # exactly the shape 5F3B-I2-FU1 item 4 removed from RouteCheckOutcome.
    raw_route_error = (
        f"route check failed: GET {SYNTHETIC_ENDPOINT_HOST}/models returned 401 "
        f"for key {SYNTHETIC_API_KEY}"
    )
    result = prepare_diagnostic_text_for_retention(raw_route_error, safety=FULL_SAFETY)
    assert result.retention_ready is False
    assert result.text is None
    assert result.scrub["clean"] is False


def test_preflight_raw_error_text_cannot_become_retention_ready_without_the_scrub_path():
    # A preflight-gate style raw error naming a workspace path and a pipe --
    # exactly the shape 5F3B-I2-FU1 item 6 removed from PreflightGateResult.
    raw_preflight_error = (
        f"generated config at {SYNTHETIC_WORKSPACE_PATH} could not bind pipe "
        f"{SYNTHETIC_PIPE_NAME}"
    )
    result = prepare_diagnostic_text_for_retention(raw_preflight_error, safety=FULL_SAFETY)
    assert result.retention_ready is False
    assert result.text is None


def test_synthetic_provider_error_cannot_become_retention_ready_without_the_scrub_path():
    # A synthetic B300/LiteLLM-shaped provider error, carrying an
    # Authorization header and the endpoint.
    raw_provider_error = (
        f"POST {SYNTHETIC_ENDPOINT_HOST}/chat/completions failed: "
        f"Authorization: Bearer {SYNTHETIC_API_KEY}"
    )
    result = prepare_diagnostic_text_for_retention(raw_provider_error, safety=FULL_SAFETY)
    assert result.retention_ready is False
    assert result.text is None


def test_route_preflight_and_provider_safe_summaries_remain_retention_ready():
    # The boundary is a backstop against UNSAFE text, not a blanket refusal --
    # a genuinely safe, bounded summary of the same three scenarios must
    # still be retention-ready through the identical scrub path.
    for safe_text in (
        "route check failed: HTTP 401",
        "generated config cleanup verification failed",
        "provider request failed: HTTP 401",
    ):
        result = prepare_diagnostic_text_for_retention(
            safe_text, safety=ArtifactSafetyContext.none_declared()
        )
        assert result.retention_ready is True
        assert result.text == safe_text


def test_no_second_scanner_module_exists():
    # I1's qualification_scrub_check remains the ONE scanner. Confirm
    # i2_cleanup imports it rather than reimplementing scrub logic.
    import qualification.i2_cleanup as mod
    from qualification.safety import qualification_scrub_check as i1_scrub

    assert mod.qualification_scrub_check is i1_scrub
