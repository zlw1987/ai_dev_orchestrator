"""Run-scoped secret context safety (I2A Sec. 8/11): repr never leaks, no evidence helper.

**5F3B-I2-FU1** added the shared ``validate_b300_base_url`` structural
validator (item 7): a malformed base URL can no longer produce
``endpoint_host == "<unparsed>"``, which had defeated
``ArtifactSafetyContext``'s endpoint-host backstop.
"""

from __future__ import annotations

import dataclasses

import pytest

from qualification.i2_secret_context import (
    InvalidBaseUrlError,
    QualificationRouteSecretContext,
    SecretContextError,
    build_secret_context,
    extract_endpoint_host,
    validate_b300_base_url,
)
from qualification.safety import ArtifactSafetyContext

VALID_KWARGS = dict(
    base_url="https://b300-proxy.example.invalid:8443/v1",
    api_key="sk-synthetic-b300-route-key-0001",
    endpoint_host="b300-proxy.example.invalid",
    credential_env_var_name="PI_QUALIFICATION_B300_ROUTE_KEY",
    provider_id="b300_pi_qualification",
    model_id="qwen3-coder-next",
)

SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
SYNTHETIC_API_KEY = "sk-synthetic-b300-route-key-0001"


def _build(**overrides):
    # 5F3B-I2-FU2: build_secret_context no longer accepts provider_id /
    # credential_env_var_name at all -- both are fixed internally.
    kwargs = dict(
        base_url=SYNTHETIC_BASE_URL,
        api_key=SYNTHETIC_API_KEY,
        model_id="qwen3-coder-next",
    )
    kwargs.update(overrides)
    return build_secret_context(**kwargs)


def test_extract_endpoint_host():
    assert extract_endpoint_host(SYNTHETIC_BASE_URL) == "b300-proxy.example.invalid"


def test_repr_does_not_contain_the_synthetic_key_or_base_url():
    ctx = _build()
    rendered = repr(ctx)
    assert SYNTHETIC_API_KEY not in rendered
    assert SYNTHETIC_BASE_URL not in rendered
    assert "b300-proxy.example.invalid" not in rendered
    # Safe, non-secret identity fields are fine to show.
    assert "PI_QUALIFICATION_B300_ROUTE_KEY" in rendered
    assert "qwen3-coder-next" in rendered


def test_str_also_does_not_leak_via_default_dataclass_repr():
    ctx = _build()
    rendered = str(ctx)
    assert SYNTHETIC_API_KEY not in rendered
    assert SYNTHETIC_BASE_URL not in rendered


def test_dataclass_fields_bearing_secrets_are_repr_false():
    field_by_name = {f.name: f for f in dataclasses.fields(_build())}
    assert field_by_name["api_key"].repr is False
    assert field_by_name["base_url"].repr is False
    assert field_by_name["endpoint_host"].repr is False


def test_no_serialization_to_evidence_helper_exists():
    ctx = _build()
    for forbidden_attr in ("to_dict", "asdict", "model_dump", "as_dict", "to_json"):
        assert not hasattr(ctx, forbidden_attr)


def test_blank_base_url_rejected():
    with pytest.raises(InvalidBaseUrlError):
        _build(base_url="")


def test_blank_api_key_rejected():
    with pytest.raises(SecretContextError):
        _build(api_key="   ")


# -- 5F3B-I2-FU1: base-URL validation (required regression H) ----------------


def test_accepted_http_url_with_port_and_path():
    assert validate_b300_base_url("http://b300-internal.example.invalid:8080/v1") == (
        "http://b300-internal.example.invalid:8080/v1"
    )
    assert extract_endpoint_host("http://b300-internal.example.invalid:8080/v1") == (
        "b300-internal.example.invalid"
    )


def test_accepted_https_url():
    assert extract_endpoint_host("https://b300-proxy.example.invalid/v1") == (
        "b300-proxy.example.invalid"
    )


def test_no_scheme_url_rejected():
    with pytest.raises(InvalidBaseUrlError):
        validate_b300_base_url("b300-proxy.example.invalid/v1")


def test_unsupported_scheme_rejected():
    with pytest.raises(InvalidBaseUrlError):
        validate_b300_base_url("ftp://b300-proxy.example.invalid/v1")


def test_username_password_url_rejected():
    with pytest.raises(InvalidBaseUrlError):
        validate_b300_base_url("https://user:sk-synthetic-pw@b300-proxy.example.invalid/v1")


def test_blank_url_rejected():
    with pytest.raises(InvalidBaseUrlError):
        validate_b300_base_url("")
    with pytest.raises(InvalidBaseUrlError):
        validate_b300_base_url("   ")


def test_query_string_rejected():
    with pytest.raises(InvalidBaseUrlError):
        validate_b300_base_url("https://b300-proxy.example.invalid/v1?token=sk-synthetic")


def test_fragment_rejected():
    with pytest.raises(InvalidBaseUrlError):
        validate_b300_base_url("https://b300-proxy.example.invalid/v1#sk-synthetic")


def test_malformed_url_never_produces_unparsed_placeholder():
    # extract_endpoint_host must raise rather than ever return "<unparsed>".
    for bad_url in (
        "not-a-url",
        "",
        "ftp://b300-proxy.example.invalid/v1",
        "https://user:pw@b300-proxy.example.invalid/v1",
    ):
        with pytest.raises(InvalidBaseUrlError):
            extract_endpoint_host(bad_url)


def test_invalid_url_error_never_echoes_the_offending_value():
    hostile_url = "https://user:sk-synthetic-embedded-secret@b300-internal.example.invalid/v1"
    with pytest.raises(InvalidBaseUrlError) as excinfo:
        validate_b300_base_url(hostile_url)
    message = str(excinfo.value)
    assert hostile_url not in message
    assert "sk-synthetic-embedded-secret" not in message
    assert "b300-internal.example.invalid" not in message


def test_build_secret_context_rejects_malformed_base_url_before_storing():
    with pytest.raises(InvalidBaseUrlError):
        _build(base_url="not-a-url")


def test_to_safety_context_produces_the_existing_i1_context_type():
    ctx = _build()
    safety = ctx.to_safety_context(
        broker_token="synthetic-broker-token",
        pipe_name=r"\\.\pipe\synthetic-qualification-pipe",
        capability_id="synthetic-capability-id",
        workspace_absolute_path=r"C:\fake\workspace\root",
    )
    assert isinstance(safety, ArtifactSafetyContext)
    assert safety.api_key == SYNTHETIC_API_KEY
    assert safety.endpoint_host == "b300-proxy.example.invalid"
    assert safety.bearer_token is None
    assert safety.broker_token == "synthetic-broker-token"


def test_to_safety_context_forbidden_needles_catch_the_declared_secret():
    ctx = _build()
    safety = ctx.to_safety_context(
        broker_token=None, pipe_name=None, capability_id=None, workspace_absolute_path=None
    )
    needle_codes = dict(safety.forbidden_needles())
    assert needle_codes["api_key_value_present"] == SYNTHETIC_API_KEY
    assert needle_codes["endpoint_host_value_present"] == "b300-proxy.example.invalid"


# -- 5F3B-I2-FU3 item 10: to_safety_context has no silent defaults -----------


def test_to_safety_context_signature_has_no_defaults():
    import inspect

    signature = inspect.signature(QualificationRouteSecretContext.to_safety_context)
    for name in ("broker_token", "pipe_name", "capability_id", "workspace_absolute_path"):
        assert signature.parameters[name].default is inspect.Parameter.empty


def test_to_safety_context_requires_every_field_explicitly():
    ctx = _build()
    with pytest.raises(TypeError):
        ctx.to_safety_context()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        ctx.to_safety_context(broker_token=None)  # type: ignore[call-arg]


def test_to_safety_context_accepts_explicit_none_for_every_field():
    ctx = _build()
    safety = ctx.to_safety_context(
        broker_token=None, pipe_name=None, capability_id=None, workspace_absolute_path=None
    )
    assert isinstance(safety, ArtifactSafetyContext)
    assert safety.broker_token is None
    assert safety.pipe_name is None
    assert safety.capability_id is None
    assert safety.workspace_absolute_path is None


# -- 5F3B-I2-FU2 item D: QualificationRouteSecretContext valid by construction
# (required regression 5) -----------------------------------------------------


def test_valid_direct_construction_is_accepted():
    ctx = QualificationRouteSecretContext(**VALID_KWARGS)
    assert ctx.model_id == "qwen3-coder-next"


def test_direct_construction_with_malformed_base_url_rejected():
    kwargs = dict(VALID_KWARGS, base_url="not-a-url")
    with pytest.raises(InvalidBaseUrlError):
        QualificationRouteSecretContext(**kwargs)


def test_direct_construction_with_endpoint_host_placeholder_rejected():
    # The exact independent-review counterexample: endpoint_host="<unparsed>".
    kwargs = dict(VALID_KWARGS, endpoint_host="<unparsed>")
    with pytest.raises(SecretContextError):
        QualificationRouteSecretContext(**kwargs)


def test_direct_construction_with_mismatched_endpoint_host_rejected():
    kwargs = dict(VALID_KWARGS, endpoint_host="attacker-controlled.example.invalid")
    with pytest.raises(SecretContextError):
        QualificationRouteSecretContext(**kwargs)


def test_direct_construction_with_blank_api_key_rejected():
    kwargs = dict(VALID_KWARGS, api_key="")
    with pytest.raises(SecretContextError):
        QualificationRouteSecretContext(**kwargs)


def test_direct_construction_with_forged_credential_carrier_rejected():
    kwargs = dict(VALID_KWARGS, credential_env_var_name="OPENAI_API_KEY")
    with pytest.raises(SecretContextError):
        QualificationRouteSecretContext(**kwargs)


def test_direct_construction_with_forged_provider_id_rejected():
    kwargs = dict(VALID_KWARGS, provider_id="evil")
    with pytest.raises(SecretContextError):
        QualificationRouteSecretContext(**kwargs)


def test_direct_construction_with_unauthorized_model_id_rejected():
    kwargs = dict(VALID_KWARGS, model_id="evil-model")
    with pytest.raises(SecretContextError):
        QualificationRouteSecretContext(**kwargs)


def test_build_secret_context_signature_has_no_route_identity_parameters():
    import inspect

    signature = inspect.signature(build_secret_context)
    param_names = set(signature.parameters)
    assert "provider_id" not in param_names
    assert "credential_env_var_name" not in param_names
    assert param_names == {"base_url", "api_key", "model_id"}
