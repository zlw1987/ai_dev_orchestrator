"""5F3B-I2-FU3 item 9 -- config/secret/route identity binding.

**OFFLINE ONLY.** No live route call, no credential read; every object here
is built from synthetic values under ``tmp_path``.
"""

from __future__ import annotations

import pytest

from qualification.i2_composition import (
    I2IdentityBindingError,
    verify_i2_identity_binding,
)
from qualification.i2_pi_config import (
    GeneratedQualificationConfig,
    write_qualification_pi_config,
)
from qualification.i2_route import route_descriptor_for_candidate
from qualification.i2_secret_context import build_secret_context

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
OTHER_SYNTHETIC_BASE_URL = "https://b300-other.example.invalid:8443/v1"
SYNTHETIC_API_KEY = "sk-synthetic-composition-key-0001"


def _generated(tmp_path, *, suffix="a", model_id="qwen3-coder-next", base_url=SYNTHETIC_BASE_URL):
    root = tmp_path / f"root_{suffix}"
    root.mkdir()
    return write_qualification_pi_config(str(root), model_id=model_id, base_url=base_url)


def _secret(*, model_id="qwen3-coder-next", base_url=SYNTHETIC_BASE_URL, api_key=SYNTHETIC_API_KEY):
    return build_secret_context(base_url=base_url, api_key=api_key, model_id=model_id)


# -- required regression 11: identity mismatch rejected before any live-capable
# action ------------------------------------------------------------------


def test_matching_triple_for_candidate_a_is_accepted(tmp_path):
    generated = _generated(tmp_path, suffix="match_a", model_id="qwen3-coder-next")
    secret = _secret(model_id="qwen3-coder-next")
    descriptor = route_descriptor_for_candidate("A")
    verify_i2_identity_binding(
        generated_config=generated, secret_context=secret, route_descriptor=descriptor
    )  # must not raise


def test_matching_triple_for_candidate_b_is_accepted(tmp_path):
    generated = _generated(tmp_path, suffix="match_b", model_id="minimax-m2.7")
    secret = _secret(model_id="minimax-m2.7")
    descriptor = route_descriptor_for_candidate("B")
    verify_i2_identity_binding(
        generated_config=generated, secret_context=secret, route_descriptor=descriptor
    )  # must not raise


def test_secret_context_model_id_mismatch_rejected(tmp_path):
    # secret context built for Candidate B's model, route descriptor for A.
    generated = _generated(tmp_path, suffix="mismatch1", model_id="qwen3-coder-next")
    secret = _secret(model_id="minimax-m2.7")
    descriptor = route_descriptor_for_candidate("A")
    with pytest.raises(I2IdentityBindingError) as excinfo:
        verify_i2_identity_binding(
            generated_config=generated, secret_context=secret, route_descriptor=descriptor
        )
    assert excinfo.value.reason_code == "SECRET_CONTEXT_MODEL_ID_MISMATCH"


def test_generated_config_model_id_mismatch_rejected(tmp_path):
    # generated config built for Candidate B's model, everything else for A.
    generated = _generated(tmp_path, suffix="mismatch2", model_id="minimax-m2.7")
    secret = _secret(model_id="qwen3-coder-next")
    descriptor = route_descriptor_for_candidate("A")
    with pytest.raises(I2IdentityBindingError) as excinfo:
        verify_i2_identity_binding(
            generated_config=generated, secret_context=secret, route_descriptor=descriptor
        )
    # secret_context vs route_descriptor is checked first and already
    # agrees here (both "qwen3-coder-next"), so the generated-config check
    # is what actually fires.
    assert excinfo.value.reason_code == "GENERATED_CONFIG_MODEL_ID_MISMATCH"


def test_generated_config_base_url_mismatch_rejected(tmp_path):
    generated = _generated(
        tmp_path, suffix="url_mismatch", model_id="qwen3-coder-next", base_url=SYNTHETIC_BASE_URL
    )
    secret = _secret(model_id="qwen3-coder-next", base_url=OTHER_SYNTHETIC_BASE_URL)
    descriptor = route_descriptor_for_candidate("A")
    with pytest.raises(I2IdentityBindingError) as excinfo:
        verify_i2_identity_binding(
            generated_config=generated, secret_context=secret, route_descriptor=descriptor
        )
    assert excinfo.value.reason_code == "GENERATED_CONFIG_BASE_URL_MISMATCH"


def test_binding_error_never_echoes_base_url_or_credential(tmp_path):
    generated = _generated(
        tmp_path, suffix="no_echo", model_id="qwen3-coder-next", base_url=SYNTHETIC_BASE_URL
    )
    secret = _secret(model_id="qwen3-coder-next", base_url=OTHER_SYNTHETIC_BASE_URL)
    descriptor = route_descriptor_for_candidate("A")
    with pytest.raises(I2IdentityBindingError) as excinfo:
        verify_i2_identity_binding(
            generated_config=generated, secret_context=secret, route_descriptor=descriptor
        )
    message = str(excinfo.value)
    assert SYNTHETIC_BASE_URL not in message
    assert OTHER_SYNTHETIC_BASE_URL not in message
    assert SYNTHETIC_API_KEY not in message


def test_binding_reverifies_generated_config_authority_first(tmp_path):
    import os

    from qualification.i2_pi_config import CleanupAuthorityError

    generated = _generated(tmp_path, suffix="tampered", model_id="qwen3-coder-next")
    marker_path = os.path.join(generated.config_dir, ".aido_i2_disposable_config")
    os.remove(marker_path)

    secret = _secret(model_id="qwen3-coder-next")
    descriptor = route_descriptor_for_candidate("A")
    with pytest.raises(CleanupAuthorityError):
        verify_i2_identity_binding(
            generated_config=generated, secret_context=secret, route_descriptor=descriptor
        )


# -- 5F3B-I2-FU3A item D/E: a genuine A config cannot be relabeled B ----------


def test_relabeled_generated_config_cannot_pass_composition_via_construction(tmp_path):
    # The metadata check now fires at GeneratedQualificationConfig
    # construction itself (i2_pi_config), so this never even reaches
    # verify_i2_identity_binding -- proving the closure holds at the
    # earliest possible point, not only inside the composition helper.
    from qualification.i2_pi_config import CleanupAuthorityError

    generated_a = _generated(tmp_path, suffix="relabel_compose", model_id="qwen3-coder-next")
    with pytest.raises(CleanupAuthorityError) as excinfo:
        GeneratedQualificationConfig(
            config_dir=generated_a.config_dir,
            settings_path=generated_a.settings_path,
            models_path=generated_a.models_path,
            provider_id=generated_a.provider_id,
            model_id="minimax-m2.7",  # relabeled from the genuine qwen3-coder-next
            authority_token=generated_a.authority_token,
        )
    assert excinfo.value.reason_code == "ISSUED_METADATA_MISMATCH"


def test_relabeled_generated_config_bypassing_post_init_still_refused_at_composition(tmp_path):
    # Defense in depth: a relabeled object that bypassed __post_init__ (so
    # construction-time refusal cannot be what stopped it) is still refused
    # by verify_i2_identity_binding's own complete-integrity re-check.
    from qualification.i2_pi_config import CleanupAuthorityError

    generated_a = _generated(tmp_path, suffix="relabel_bypass", model_id="qwen3-coder-next")
    forged = object.__new__(GeneratedQualificationConfig)
    object.__setattr__(forged, "config_dir", generated_a.config_dir)
    object.__setattr__(forged, "settings_path", generated_a.settings_path)
    object.__setattr__(forged, "models_path", generated_a.models_path)
    object.__setattr__(forged, "provider_id", generated_a.provider_id)
    object.__setattr__(forged, "model_id", "minimax-m2.7")  # relabeled
    object.__setattr__(forged, "authority_token", generated_a.authority_token)

    secret_b = _secret(model_id="minimax-m2.7")
    descriptor_b = route_descriptor_for_candidate("B")
    with pytest.raises(CleanupAuthorityError) as excinfo:
        verify_i2_identity_binding(
            generated_config=forged, secret_context=secret_b, route_descriptor=descriptor_b
        )
    assert excinfo.value.reason_code == "ISSUED_METADATA_MISMATCH"


def test_binding_refuses_content_tampered_generated_config(tmp_path):
    # Item E: composition checks the ACTUAL finalized/on-disk config, not
    # merely the dataclass fields -- a config whose models.json was edited
    # after generation (e.g. actual disk model swapped to Candidate B's id)
    # fails complete integrity before any field comparison is trusted.
    import json
    from pathlib import Path

    from qualification.i2_pi_config import CleanupAuthorityError, PROVIDER_ID

    generated_a = _generated(tmp_path, suffix="tampered_compose", model_id="qwen3-coder-next")
    raw = json.loads(Path(generated_a.models_path).read_text(encoding="utf-8"))
    raw["providers"][PROVIDER_ID]["models"][0]["id"] = "minimax-m2.7"
    Path(generated_a.models_path).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    secret = _secret(model_id="qwen3-coder-next")
    descriptor = route_descriptor_for_candidate("A")
    with pytest.raises(CleanupAuthorityError) as excinfo:
        verify_i2_identity_binding(
            generated_config=generated_a, secret_context=secret, route_descriptor=descriptor
        )
    assert excinfo.value.reason_code == "MODELS_CONTENT_MISMATCH"


def test_no_generic_runtime_abstraction_was_introduced():
    import qualification.i2_composition as mod

    for forbidden_name in ("AgentRuntime", "RuntimeAdapter", "GenericRuntime"):
        assert not hasattr(mod, forbidden_name)
