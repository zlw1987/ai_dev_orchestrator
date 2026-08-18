"""Phase 5F2E-V1 tests: the direct vLLM reviewer provider.

This slice adds **one** thing: ``controlled_review.provider`` may now be
``"vllm"`` — a direct OpenAI-compatible vLLM endpoint — as well as the existing
``"litellm"`` internal path. Everything that made Phase 5F2E and Phase 5F2E-RS1
safe is unchanged, and most of this file exists to prove that it is unchanged:

1. **Authority** — the provider is exact and case-sensitive, and it is
   established from trusted project config before anything is read, executed, or
   contacted.
2. **Environment** — a vLLM reviewer needs ``AIDO_VLLM_BASE_URL`` and nothing
   else; no ``AIDO_LITELLM_*`` value substitutes for it, there is no
   ``AIDO_VLLM_DEFAULT_MODEL``, and the model still comes only from project
   config.
3. **Transport security** — plaintext HTTP to a direct vLLM endpoint is refused
   before any model request unless the project explicitly opted in, and the
   opt-in is never described as making the transport secure.
4. **Ordering** — for *both* providers, no reviewer environment value is read
   until the accepted Phase 5F2D verification returned ``verified``.
5. **RS1 invariants** — transport retries forced to zero, one HTTP request per
   semantic attempt, a terminal stall, at most two semantic requests, and no
   fallback model, all applied identically to the vLLM path.
6. **The packet** — ``review-packet.v3``, with truthful provider and transport
   provenance, and ``v1``/``v2`` semantics preserved as history.

**Every repository here is a synthetic Git repository created under pytest's own
``tmp_path``, and every verification program is a small synthetic Python script
written under ``tmp_path``.** No real target project is used, read, written, or
executed. **Every reviewer call goes through ``httpx.MockTransport``**: no socket
is opened, no real endpoint is contacted, no API key is needed, and no real vLLM
endpoint — the operator's included — appears anywhere in this suite.
"""

from __future__ import annotations

import json
import socket

import httpx
import pytest
from pydantic import ValidationError

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.llm.client import LLMClient
from ai_dev_orchestrator.models import ControlledReviewConfig, ProjectConfig
from ai_dev_orchestrator.review import (
    MAX_SEMANTIC_REVIEW_ATTEMPTS,
    REVIEW_PACKET_SCHEMA_VERSION,
    REVIEW_PACKET_SCHEMA_VERSION_HISTORY,
    REVIEW_PACKET_SCHEMA_VERSION_V1,
    REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS,
    REVIEW_PACKET_SCHEMA_VERSION_V2,
    REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS,
    REVIEW_PROVIDER_LITELLM,
    REVIEW_PROVIDER_VLLM,
    LITELLM_REVIEWER_ENV_NAMES,
    RETRY_ELIGIBLE_OUTCOMES,
    SUPPORTED_REVIEW_PROVIDERS,
    VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY,
    VLLM_ENV_API_KEY,
    VLLM_ENV_BASE_URL,
    ReviewPacket,
    ReviewRefusedError,
    build_reviewer_client_config,
    check_controlled_review_gate,
    reviewer_env_names_for_provider,
)
from review_fixtures import DIFF_MARKER
from test_cli_l2_review_approved_file_edit import (
    DIRTYING_BODY,
    FAILING_BODY,
    FAKE_API_KEY,
    FAKE_BASE_URL,
    REVIEWER_MODEL,
    VALID_REVIEW_JSON,
    _env,
    _forbidden_client,
    _forbidden_env,
    _run,
    _setup,
    _stdout_json,
    git_required,
    windows_only,
)

# Synthetic, non-resolvable endpoints. The ``.invalid`` TLD is reserved by
# RFC 2606 precisely so it can never name a real host, and no real vLLM
# deployment, address or port appears in this file.
VLLM_HTTPS_BASE_URL = "https://fake-vllm.invalid/v1"
VLLM_HTTPS_HOST = "fake-vllm.invalid"
VLLM_HTTP_BASE_URL = "http://fake-vllm.invalid:8000/v1"
VLLM_HTTP_HOST = "fake-vllm.invalid:8000"
VLLM_API_KEY = "fake-vllm-key-not-a-real-secret"

# The exact model a project configures. Deliberately shaped like a real served
# model name so the "config, not environment, names the model" property is
# visible, but it is invented and matched only against itself.
VLLM_REVIEWER_MODEL = "fake-vllm-reviewer-27b"


def _vllm_block(
    *,
    model: str = VLLM_REVIEWER_MODEL,
    allow_insecure_http: bool | None = None,
    compact_retry: bool = False,
    attempt_timeout_seconds: float | None = None,
    provider: str = "vllm",
) -> str:
    lines = [
        "controlled_review:",
        "  enabled: true",
        f'  provider: "{provider}"',
        f'  model: "{model}"',
        f"  compact_retry_on_unusable_output: {str(compact_retry).lower()}",
    ]
    if attempt_timeout_seconds is not None:
        lines.append(f"  attempt_timeout_seconds: {attempt_timeout_seconds}")
    if allow_insecure_http is not None:
        lines.append(
            f"  vllm_allow_insecure_http: {str(allow_insecure_http).lower()}"
        )
    return "\n".join(lines) + "\n"


def _vllm_env(**overrides) -> dict[str, str]:
    """A literal environment mapping. Never read from the real environment."""
    values = {VLLM_ENV_BASE_URL: VLLM_HTTPS_BASE_URL}
    for key, value in overrides.items():
        if value is None:
            values.pop(key, None)
        else:
            values[key] = value
    return values


def _recording_factory(
    configs: list,
    seen: list[dict],
    *,
    content: str = VALID_REVIEW_JSON,
    action=None,
):
    """A MockTransport-backed factory that records configs and counts requests."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        if action is not None:
            return action(request)
        return httpx.Response(
            200,
            json={
                "model": VLLM_REVIEWER_MODEL,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 300,
                    "completion_tokens": 40,
                    "total_tokens": 340,
                },
            },
        )

    def factory(config):
        configs.append(config)
        return LLMClient(
            config, transport=httpx.MockTransport(handler), sleep=lambda _: None
        )

    return factory


def _project(**review) -> ProjectConfig:
    payload = {
        "project_id": "demo_project",
        "display_name": "Demo",
        "repo": {
            "workspace_path": "C:/never/touched",
            "github_repo": "demo/widgets",
            "branch_prefix": "ai/demo",
        },
    }
    if review:
        payload["controlled_review"] = review
    return ProjectConfig.model_validate(payload)


# =============================================================================
# 1. Provider authority — config shape and the gate
# =============================================================================


def test_an_existing_5f2e_config_loads_unchanged_with_safe_defaults():
    """Requirement 1: no existing project config needs a new field."""
    settings = ControlledReviewConfig(enabled=True, model=REVIEWER_MODEL)

    assert settings.provider == "litellm"
    assert settings.vllm_allow_insecure_http is False
    # The accepted RS1 defaults are untouched.
    assert settings.attempt_timeout_seconds == 90.0
    assert settings.max_output_tokens == 2048
    assert settings.compact_retry_on_unusable_output is False


def test_the_vllm_provider_is_accepted_by_the_gate():
    """Requirement 7."""
    authority = check_controlled_review_gate(
        _project(enabled=True, provider="vllm", model=VLLM_REVIEWER_MODEL)
    )

    assert authority.provider == "vllm"
    assert authority.model == VLLM_REVIEWER_MODEL


def test_exactly_two_providers_are_supported():
    assert SUPPORTED_REVIEW_PROVIDERS == ("litellm", "vllm")
    assert REVIEW_PROVIDER_LITELLM == "litellm"
    assert REVIEW_PROVIDER_VLLM == "vllm"


@pytest.mark.parametrize(
    "provider",
    ["VLLM", "vLLM", "Vllm", "vllm ", " vllm", "LiteLLM", "LITELLM"],
)
def test_provider_spelling_is_exact_and_case_sensitive(provider):
    """Requirement 8: no alias, no case folding, no trimming, no glob."""
    with pytest.raises(ReviewRefusedError) as excinfo:
        check_controlled_review_gate(
            _project(enabled=True, provider=provider, model=VLLM_REVIEWER_MODEL)
        )

    assert "provider error" in str(excinfo.value)


@pytest.mark.parametrize(
    "provider",
    [
        "openai",
        "openai_compatible",
        "openai-compatible",
        "vllm_openai",
        "anthropic",
        "ollama",
        "pi",
        "*",
    ],
)
def test_arbitrary_and_generic_providers_are_refused(provider):
    """Requirement 9: two named backends, not a compatible family."""
    with pytest.raises(ReviewRefusedError) as excinfo:
        check_controlled_review_gate(
            _project(enabled=True, provider=provider, model=VLLM_REVIEWER_MODEL)
        )

    message = str(excinfo.value)
    assert "provider error" in message
    assert "case-sensitive" in message


def test_the_block_still_rejects_every_forbidden_reviewer_field():
    """Requirements 33/41: no fallback, chain, second reviewer, or overrides."""
    for extra in (
        {"fallback_model": "another-model"},
        {"secondary_model": "another-model"},
        {"reviewer_chain": ["a", "b"]},
        {"reviewers": ["a", "b"]},
        {"provider_priority": ["vllm", "litellm"]},
        {"providers": ["vllm", "litellm"]},
        {"provider_list": ["vllm"]},
        {"models": ["a", "b"]},
        {"base_url": VLLM_HTTPS_BASE_URL},
        {"endpoint": VLLM_HTTPS_BASE_URL},
        {"api_key": "sk-not-a-real-key"},
        {"api_key_env": VLLM_ENV_API_KEY},
        {"headers": {"X": "y"}},
        {"max_retries": 3},
        {"vllm_base_url": VLLM_HTTPS_BASE_URL},
        {"allow_insecure_http": True},
    ):
        with pytest.raises(ValidationError):
            ControlledReviewConfig(
                enabled=True, provider="vllm", model=VLLM_REVIEWER_MODEL, **extra
            )


# =============================================================================
# 2. The vLLM environment contract
# =============================================================================


def test_each_provider_resolves_to_its_own_exact_env_names():
    """The read authority is per-provider, and there is no union (V1-FU1)."""
    assert reviewer_env_names_for_provider("litellm") == (
        "AIDO_LITELLM_BASE_URL",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_DEFAULT_MODEL",
        "AIDO_LITELLM_TIMEOUT_SECONDS",
        "AIDO_LITELLM_MAX_RETRIES",
    )
    assert reviewer_env_names_for_provider("vllm") == (
        "AIDO_VLLM_BASE_URL",
        "AIDO_VLLM_API_KEY",
    )
    assert reviewer_env_names_for_provider("litellm") == LITELLM_REVIEWER_ENV_NAMES

    # The two families are disjoint, so neither can ever stand in for the other.
    assert not set(reviewer_env_names_for_provider("litellm")) & set(
        reviewer_env_names_for_provider("vllm")
    )
    # Requirement 11: there is no vLLM default-model variable to read.
    assert not any(
        name.startswith("AIDO_VLLM_DEFAULT")
        for name in reviewer_env_names_for_provider("vllm")
    )


def test_an_unsupported_provider_resolves_to_no_env_names_at_all():
    """Fail-closed, and before any name — let alone any value — is resolved."""
    for provider in ("openai", "openai_compatible", "VLLM", "vllm ", ""):
        with pytest.raises(Exception) as excinfo:
            reviewer_env_names_for_provider(provider)
        assert "no reviewer environment contract" in str(excinfo.value)


def test_vllm_requires_no_litellm_variable_at_all():
    """Requirement 10."""
    config = build_reviewer_client_config(
        {VLLM_ENV_BASE_URL: VLLM_HTTPS_BASE_URL},
        model=VLLM_REVIEWER_MODEL,
        attempt_timeout_seconds=45.0,
        provider="vllm",
    )

    assert config.base_url == VLLM_HTTPS_BASE_URL
    assert config.default_model == VLLM_REVIEWER_MODEL
    assert config.timeout_seconds == 45.0


def test_the_project_configured_model_becomes_the_client_default_model():
    """Requirement 12: authority is project config, never the environment."""
    config = build_reviewer_client_config(
        _vllm_env(),
        model=VLLM_REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="vllm",
    )

    assert config.default_model == VLLM_REVIEWER_MODEL


@pytest.mark.parametrize("base_url", [None, "", "   "])
def test_a_missing_or_blank_vllm_base_url_is_refused(base_url):
    """Requirement 13, at the library boundary."""
    env = {} if base_url is None else {VLLM_ENV_BASE_URL: base_url}

    with pytest.raises(Exception) as excinfo:
        build_reviewer_client_config(
            env,
            model=VLLM_REVIEWER_MODEL,
            attempt_timeout_seconds=90.0,
            provider="vllm",
        )

    message = str(excinfo.value)
    assert VLLM_ENV_BASE_URL in message
    assert "AIDO_LITELLM" not in message.replace("AIDO_LITELLM_*", "")


@pytest.mark.parametrize("api_key", [None, "", "   "])
def test_an_absent_or_blank_vllm_api_key_uses_the_compatibility_placeholder(api_key):
    """Requirement 14. The placeholder is not a credential."""
    env = _vllm_env(**{VLLM_ENV_API_KEY: api_key})
    config = build_reviewer_client_config(
        env,
        model=VLLM_REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="vllm",
    )

    assert config.api_key == VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY
    assert VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY == "no_api_key"


def test_a_supplied_vllm_api_key_reaches_only_the_client_config():
    """Requirement 15 (library half)."""
    config = build_reviewer_client_config(
        _vllm_env(**{VLLM_ENV_API_KEY: VLLM_API_KEY}),
        model=VLLM_REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="vllm",
    )

    assert config.api_key == VLLM_API_KEY
    # The key is excluded from repr, exactly as the shipped model intends.
    assert VLLM_API_KEY not in repr(config)


def test_the_generic_llm_client_config_still_requires_an_api_key():
    """Requirement 4/keyless design: the generic model was NOT weakened.

    The vLLM path substitutes a fixed placeholder rather than making ``api_key``
    optional for every caller, so this constraint must still hold.
    """
    from ai_dev_orchestrator.llm.models import LLMClientConfig

    with pytest.raises(ValidationError):
        LLMClientConfig(
            base_url=VLLM_HTTPS_BASE_URL, api_key="", default_model="m"
        )


def test_litellm_environment_values_cannot_supply_a_vllm_reviewer():
    """Requirement 16: the two name families never substitute for each other.

    Asserted against the loaders themselves, so it holds even if a caller hands
    over a mapping wider than the provider's names. (The real reader never does —
    see ``test_cli_l2_review_provider_env_isolation.py``, which proves the
    unconfigured family is never read from the process environment at all.)
    """
    mixed = {
        **_env(),  # every AIDO_LITELLM_* name, with a different default model
        VLLM_ENV_BASE_URL: VLLM_HTTPS_BASE_URL,
        VLLM_ENV_API_KEY: VLLM_API_KEY,
    }

    vllm = build_reviewer_client_config(
        mixed,
        model=VLLM_REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="vllm",
    )
    assert vllm.base_url == VLLM_HTTPS_BASE_URL
    assert vllm.api_key == VLLM_API_KEY
    assert vllm.default_model == VLLM_REVIEWER_MODEL

    # And the reverse: a vLLM value can never supply the LiteLLM path.
    litellm = build_reviewer_client_config(
        mixed,
        model=REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="litellm",
    )
    assert litellm.base_url == FAKE_BASE_URL
    assert litellm.api_key == FAKE_API_KEY
    assert litellm.default_model == REVIEWER_MODEL


def test_the_existing_litellm_environment_contract_is_unchanged():
    """Requirements 2 and 3."""
    config = build_reviewer_client_config(
        _env(),
        model=REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
    )

    assert config.base_url == FAKE_BASE_URL
    assert config.api_key == FAKE_API_KEY
    # The project-configured model beats AIDO_LITELLM_DEFAULT_MODEL.
    assert config.default_model == REVIEWER_MODEL
    assert config.max_retries == 0


def test_both_providers_force_reviewer_transport_retries_to_zero():
    """Requirements 4 and 27."""
    litellm = build_reviewer_client_config(
        _env(AIDO_LITELLM_MAX_RETRIES="2"),
        model=REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
    )
    vllm = build_reviewer_client_config(
        _vllm_env(),
        model=VLLM_REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="vllm",
    )

    assert litellm.max_retries == 0
    assert vllm.max_retries == 0


# =============================================================================
# 3. Direct vLLM transport security
# =============================================================================


def test_https_works_with_the_default_insecure_http_opt_out():
    """Requirement 17."""
    config = build_reviewer_client_config(
        _vllm_env(),
        model=VLLM_REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="vllm",
        allow_insecure_http=False,
    )

    assert config.base_url.startswith("https://")


def test_plaintext_http_is_refused_by_default_and_echoes_no_url_or_credential():
    """Requirement 18, plus the "never echo the base URL" rule."""
    with pytest.raises(Exception) as excinfo:
        build_reviewer_client_config(
            _vllm_env(
                **{
                    VLLM_ENV_BASE_URL: VLLM_HTTP_BASE_URL,
                    VLLM_ENV_API_KEY: VLLM_API_KEY,
                }
            ),
            model=VLLM_REVIEWER_MODEL,
            attempt_timeout_seconds=90.0,
            provider="vllm",
            allow_insecure_http=False,
        )

    message = str(excinfo.value)
    assert "PLAINTEXT HTTP" in message
    assert "vllm_allow_insecure_http" in message
    # Never the URL, never the key.
    assert VLLM_HTTP_BASE_URL not in message
    assert VLLM_API_KEY not in message
    # And the opt-in is never described as a security property.
    lowered = message.lower()
    for claim in (
        "is secure",
        "is encrypted",
        "is private",
        "is authenticated",
        "company-approved",
        "safe for secrets",
    ):
        assert f"transport {claim}" not in lowered


def test_plaintext_http_may_proceed_with_the_explicit_project_opt_in():
    """Requirement 19."""
    config = build_reviewer_client_config(
        _vllm_env(**{VLLM_ENV_BASE_URL: VLLM_HTTP_BASE_URL}),
        model=VLLM_REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="vllm",
        allow_insecure_http=True,
    )

    assert config.base_url == VLLM_HTTP_BASE_URL


def test_the_insecure_http_rule_is_not_applied_to_the_litellm_provider():
    """V1 must not retroactively break an accepted LiteLLM deployment."""
    config = build_reviewer_client_config(
        _env(),  # FAKE_BASE_URL is http://
        model=REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="litellm",
        allow_insecure_http=False,
    )

    assert config.base_url.startswith("http://")


@pytest.mark.parametrize(
    "base_url",
    ["ftp://fake-vllm.invalid/v1", "file:///tmp/nope", "fake-vllm.invalid/v1"],
)
def test_an_unsupported_endpoint_scheme_is_refused(base_url):
    with pytest.raises(Exception) as excinfo:
        build_reviewer_client_config(
            {VLLM_ENV_BASE_URL: base_url},
            model=VLLM_REVIEWER_MODEL,
            attempt_timeout_seconds=90.0,
            provider="vllm",
            allow_insecure_http=True,
        )

    assert base_url not in str(excinfo.value)


# =============================================================================
# 4. Ordering — for BOTH providers
# =============================================================================


DISABLED_VLLM_BLOCK = (
    'controlled_review:\n  enabled: false\n  provider: "vllm"\n'
    f'  model: "{VLLM_REVIEWER_MODEL}"\n'
)
DISABLED_LITELLM_BLOCK = (
    'controlled_review:\n  enabled: false\n  provider: "litellm"\n'
    f'  model: "{REVIEWER_MODEL}"\n'
)
UNSUPPORTED_PROVIDER_BLOCK = _vllm_block(provider="openai_compatible")


@windows_only
@git_required
@pytest.mark.parametrize(
    ("review_block", "verify_flag", "real_reviewer"),
    [
        (_vllm_block(), False, False),
        (_vllm_block(), True, False),
        (_vllm_block(), False, True),
        (None, False, False),
        (None, True, False),
        (DISABLED_VLLM_BLOCK, True, True),
        (DISABLED_LITELLM_BLOCK, True, True),
        (UNSUPPORTED_PROVIDER_BLOCK, True, True),
    ],
    ids=[
        "vllm-no-flags",
        "vllm-missing-real-reviewer",
        "vllm-missing-verify",
        "litellm-no-flags",
        "litellm-missing-real-reviewer",
        "vllm-review-disabled",
        "litellm-review-disabled",
        "unsupported-provider",
    ],
)
def test_no_reviewer_environment_is_read_when_the_command_refuses(
    tmp_path, review_block, verify_flag, real_reviewer
):
    """Requirement 24, for both providers and every refusal shape.

    A refusal must cost nothing: no reviewer environment value is read and no
    client is built, whichever provider the project named.
    """
    kwargs = {} if review_block is None else {"review_block": review_block}
    _, config, artifact = _setup(tmp_path, **kwargs)

    code = _run(
        config,
        artifact,
        read_env=_forbidden_env(),
        client_factory=_forbidden_client(),
        verify_flag=verify_flag,
        real_reviewer=real_reviewer,
    )

    assert code == 1


@windows_only
@git_required
@pytest.mark.parametrize(
    ("body", "expected_code"),
    [(FAILING_BODY, 2), (DIRTYING_BODY, 3)],
    ids=["verification-failed", "workspace-untrusted"],
)
@pytest.mark.parametrize(
    "review_block",
    [_vllm_block(), None],
    ids=["vllm", "litellm"],
)
def test_a_non_verified_outcome_reads_no_reviewer_environment(
    tmp_path, body, expected_code, review_block, capsys
):
    """Requirement 25, for both providers."""
    kwargs = {} if review_block is None else {"review_block": review_block}
    _, config, artifact = _setup(tmp_path, body=body, **kwargs)

    code = _run(
        config,
        artifact,
        read_env=_forbidden_env(),
        client_factory=_forbidden_client(),
    )

    assert code == expected_code
    err = capsys.readouterr().err
    assert "no reviewer environment value was read" in err.lower()


@windows_only
@git_required
def test_the_reader_is_called_once_after_verified_and_is_told_the_provider(tmp_path):
    """Requirement 26, and the V1-FU1 contract: the reader receives the provider.

    The provider argument is what makes provider-specific reading possible at
    all — the reader resolves it to exact names *before* touching any
    environment. That the real reader honours it is proved against the process
    environment in ``test_cli_l2_review_provider_env_isolation.py``.
    """
    _, config, artifact = _setup(tmp_path, review_block=_vllm_block())

    calls: list[str] = []

    def read_env(provider):
        calls.append(provider)
        return _vllm_env(**{VLLM_ENV_API_KEY: VLLM_API_KEY})

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=read_env,
        client_factory=_recording_factory(configs, seen),
    )

    assert code == 0
    # Exactly once, after `verified`, with the configured provider.
    assert calls == ["vllm"]
    assert configs[0].base_url == VLLM_HTTPS_BASE_URL
    assert configs[0].api_key == VLLM_API_KEY
    assert configs[0].default_model == VLLM_REVIEWER_MODEL


# =============================================================================
# 5. End-to-end vLLM reviews, and the v3 packet
# =============================================================================


@windows_only
@git_required
def test_an_https_vllm_review_succeeds_and_records_tls_truthfully(tmp_path, capsys):
    """Requirements 21, 28 and the transmission boundary, end to end."""
    _, config, artifact = _setup(tmp_path, review_block=_vllm_block())

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen),
    )

    assert code == 0
    # Requirement 28: first-attempt success is exactly one request.
    assert len(seen) == 1

    packet = ReviewPacket.model_validate(_stdout_json(capsys))
    assert packet.schema_version == "review-packet.v3"
    assert packet.reviewer.provider == "vllm"
    assert packet.reviewer.model == VLLM_REVIEWER_MODEL
    assert packet.reviewer.endpoint_host == VLLM_HTTPS_HOST
    assert packet.reviewer.endpoint_scheme == "https"
    assert packet.reviewer.transport_tls is True
    assert packet.reviewer.semantic_requests == 1
    assert packet.reviewer.transport_retries_per_semantic_request == 0
    assert packet.reviewer.fallback_model_configured is False
    assert packet.reviewer.fallback_model_used is False
    assert packet.reviewer.model_source == "project_config.controlled_review.model"
    assert packet.reviewer.environment_default_model_used is False
    assert packet.reviewer.cli_model_override_available is False

    # The approved diff really was the thing reviewed.
    assert DIFF_MARKER in json.dumps(seen[0])
    # The request named the project-configured model, not an environment one.
    assert seen[0]["model"] == VLLM_REVIEWER_MODEL


@windows_only
@git_required
def test_an_authorized_http_vllm_review_records_no_tls_and_warns_unmistakably(
    tmp_path, capsys
):
    """Requirements 20, 22 and 23."""
    _, config, artifact = _setup(
        tmp_path, review_block=_vllm_block(allow_insecure_http=True)
    )

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(
            **{
                VLLM_ENV_BASE_URL: VLLM_HTTP_BASE_URL,
                VLLM_ENV_API_KEY: VLLM_API_KEY,
            }
        ),
        client_factory=_recording_factory(configs, seen),
    )

    assert code == 0
    captured = capsys.readouterr()

    packet = ReviewPacket.model_validate(json.loads(captured.out))
    assert packet.reviewer.provider == "vllm"
    assert packet.reviewer.endpoint_scheme == "http"
    assert packet.reviewer.transport_tls is False
    assert packet.reviewer.endpoint_host == VLLM_HTTP_HOST

    err = captured.err
    # Requirement 22: unmistakable.
    assert "NOT TLS-ENCRYPTED" in err
    assert "UNENCRYPTED" in err
    assert "Provider:      vllm" in err
    # Requirement 23: never the base URL, never the credential, never the prompt.
    assert VLLM_HTTP_BASE_URL not in err
    assert VLLM_API_KEY not in err
    assert VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY not in err
    assert DIFF_MARKER not in err
    # The host alone is allowed, under the same rule the accepted banner uses.
    assert VLLM_HTTP_HOST in err
    # Being internal or colleague-hosted is explicitly not a privacy claim.
    assert "does NOT make it private" in err


@windows_only
@git_required
def test_an_unauthorized_http_vllm_endpoint_fails_after_verification_and_before_contact(
    tmp_path, capsys
):
    """Requirement 18, end to end: verification passed, no model request issued."""
    _, config, artifact = _setup(tmp_path, review_block=_vllm_block())

    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(**{VLLM_ENV_BASE_URL: VLLM_HTTP_BASE_URL}),
        client_factory=_forbidden_client(),
    )

    assert code == 4
    err = capsys.readouterr().err
    assert "PLAINTEXT HTTP" in err
    assert VLLM_HTTP_BASE_URL not in err


@windows_only
@git_required
def test_a_missing_vllm_base_url_fails_after_verification_and_before_contact(
    tmp_path, capsys
):
    """Requirement 13, end to end."""
    _, config, artifact = _setup(tmp_path, review_block=_vllm_block())

    code = _run(
        config,
        artifact,
        read_env=lambda _provider: {},
        client_factory=_forbidden_client(),
    )

    assert code == 4
    err = capsys.readouterr().err
    assert VLLM_ENV_BASE_URL in err


@windows_only
@git_required
def test_a_supplied_vllm_key_never_appears_in_output(tmp_path, capsys):
    """Requirement 15, end to end."""
    _, config, artifact = _setup(tmp_path, review_block=_vllm_block())

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(**{VLLM_ENV_API_KEY: VLLM_API_KEY}),
        client_factory=_recording_factory(configs, seen),
    )

    assert code == 0
    captured = capsys.readouterr()
    assert configs[0].api_key == VLLM_API_KEY
    assert VLLM_API_KEY not in captured.out
    assert VLLM_API_KEY not in captured.err
    assert VLLM_API_KEY not in json.dumps(seen)


@windows_only
@git_required
def test_a_litellm_review_now_records_provider_and_scheme_truthfully(
    tmp_path, capsys
):
    """Requirement 6: the accepted LiteLLM path emits a v3 packet.

    The synthetic ``FAKE_BASE_URL`` is ``http://``, so the packet must say so.
    That is test provenance being reported honestly, not a security approval.
    """
    _, config, artifact = _setup(tmp_path)

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _env(),
        client_factory=_recording_factory(configs, seen, content=VALID_REVIEW_JSON),
    )

    assert code == 0
    packet = ReviewPacket.model_validate(_stdout_json(capsys))
    assert packet.schema_version == "review-packet.v3"
    assert packet.reviewer.provider == "litellm"
    assert packet.reviewer.model == REVIEWER_MODEL
    assert packet.reviewer.endpoint_scheme == "http"
    assert packet.reviewer.transport_tls is False


# =============================================================================
# 6. RS1 invariants, applied identically to the vLLM path
# =============================================================================


@windows_only
@git_required
def test_a_vllm_client_timeout_is_terminal_and_costs_exactly_one_request(
    tmp_path, capsys
):
    """Requirement 29. Compact retry ENABLED, and still one request."""
    _, config, artifact = _setup(
        tmp_path, review_block=_vllm_block(compact_retry=True)
    )

    configs: list = []
    seen: list[dict] = []

    def action(request):
        raise httpx.ReadTimeout("synthetic")

    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen, action=action),
    )

    assert code == 4
    assert len(seen) == 1, seen

    err = capsys.readouterr().err
    assert "=== REVIEW STALLED ===" in err
    assert "compact retry authorized" not in err
    assert "REVIEW UNUSABLE" not in err
    assert "Attempts used:    1 of at most 2" in err


@windows_only
@git_required
def test_a_vllm_supervisor_deadline_is_terminal_and_costs_exactly_one_request(
    tmp_path, capsys
):
    """Requirement 30: AIDO's own monotonic deadline, compact retry enabled."""
    import threading
    import time

    release = threading.Event()
    _, config, artifact = _setup(
        tmp_path,
        review_block=_vllm_block(compact_retry=True, attempt_timeout_seconds=0.3),
    )

    configs: list = []
    seen: list[dict] = []

    def action(request):
        # Outlive AIDO's deadline without ever timing out a socket read, which
        # is precisely the FU2 case the supervisor deadline exists for.
        release.wait(5.0)
        return httpx.Response(
            200,
            json={
                "model": VLLM_REVIEWER_MODEL,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": VALID_REVIEW_JSON},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    try:
        started = time.monotonic()
        code = _run(
            config,
            artifact,
            read_env=lambda _provider: _vllm_env(),
            client_factory=_recording_factory(configs, seen, action=action),
        )
        elapsed = time.monotonic() - started
    finally:
        release.set()

    assert code == 4
    assert len(seen) == 1, seen
    # AIDO stopped waiting well before the worker would have returned.
    assert elapsed < 4.0

    err = capsys.readouterr().err
    assert "=== REVIEW STALLED ===" in err
    assert "compact retry authorized" not in err


@windows_only
@git_required
def test_a_completed_unusable_vllm_response_retries_only_when_enabled(tmp_path):
    """Requirements 31 and 32: at most two, and only with the project opt-in."""
    for compact, expected_requests in ((False, 1), (True, 2)):
        case = tmp_path / f"case-{compact}"
        case.mkdir()
        _, config, artifact = _setup(
            case, review_block=_vllm_block(compact_retry=compact)
        )
        configs: list = []
        seen: list[dict] = []

        code = _run(
            config,
            artifact,
            read_env=lambda _provider: _vllm_env(),
            client_factory=_recording_factory(
                configs, seen, content="not json at all"
            ),
        )

        assert code == 4
        assert len(seen) == expected_requests, (compact, seen)
        # Requirement 32/33: never a third request, never a second model.
        assert len(seen) <= MAX_SEMANTIC_REVIEW_ATTEMPTS
        assert {payload["model"] for payload in seen} == {VLLM_REVIEWER_MODEL}


def test_the_rs1_retry_policy_itself_is_unchanged():
    """Requirements 5 and 33: the accepted classifications did not move."""
    assert RETRY_ELIGIBLE_OUTCOMES == (
        "review_output_budget_exhausted",
        "review_unusable_output",
    )
    assert MAX_SEMANTIC_REVIEW_ATTEMPTS == 2


# =============================================================================
# 7. Packet history
# =============================================================================


def test_the_current_schema_version_is_v3():
    """Requirement 34."""
    assert REVIEW_PACKET_SCHEMA_VERSION == "review-packet.v3"


def test_v1_and_v2_semantics_remain_present_and_truthful():
    """Requirements 35 and 36."""
    assert REVIEW_PACKET_SCHEMA_VERSION_V1 == "review-packet.v1"
    assert REVIEW_PACKET_SCHEMA_VERSION_V2 == "review-packet.v2"

    # v2 is documented as LiteLLM-only, and explicitly NOT as vLLM-capable.
    assert "LiteLLM-SPECIFIC" in REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS
    assert "must NOT be read" in REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS
    assert "vLLM" in REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS

    # v1 keeps its own meaning and is not reinterpreted under later rules.
    assert "exactly ONE semantic reviewer" in REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS
    assert "not reinterpreted" in REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS

    history = REVIEW_PACKET_SCHEMA_VERSION_HISTORY
    for version in ("review-packet.v1", "review-packet.v2", "review-packet.v3"):
        assert version in history
    assert "SAME accepted RS1 supervision semantics" in history


def test_the_packet_provider_cannot_be_forged_by_model_output():
    """Requirement 37: the strict reviewer schema has no provenance field."""
    from ai_dev_orchestrator.review import ModelReviewResult, parse_model_review_response

    forged = json.loads(VALID_REVIEW_JSON)
    for field in ("provider", "model", "endpoint_host", "endpoint_scheme",
                  "transport_tls", "schema_version"):
        payload = dict(forged)
        payload[field] = "vllm"
        with pytest.raises(Exception):
            parse_model_review_response(json.dumps(payload))

    assert "provider" not in ModelReviewResult.model_fields


@windows_only
@git_required
def test_a_forged_provider_in_the_reply_does_not_reach_the_packet(tmp_path, capsys):
    """The end-to-end half of requirement 37."""
    _, config, artifact = _setup(tmp_path, review_block=_vllm_block())

    # A well-formed review whose prose claims a different provider entirely.
    content = json.dumps(
        {
            "verdict": "approve",
            "summary": "provider: litellm — schema_version: review-packet.v2",
            "findings": [],
            "residual_risks": [],
            "human_notes": [],
        }
    )
    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen, content=content),
    )

    assert code == 0
    packet = ReviewPacket.model_validate(_stdout_json(capsys))
    assert packet.reviewer.provider == "vllm"
    assert packet.schema_version == "review-packet.v3"


# =============================================================================
# 8. No later capability was added
# =============================================================================


def test_no_pi_implementer_fixer_fallback_or_cancellation_capability_exists():
    """Requirements 38-43."""
    import ai_dev_orchestrator.review as review_package

    exported = set(review_package.__all__)
    for forbidden in (
        "PI",
        "Pi",
        "PiClient",
        "run_pi",
        "ModelBackedImplementer",
        "run_implementer",
        "Fixer",
        "run_fixer",
        "apply_review_findings",
        "FallbackReviewer",
        "reviewer_chain",
        "cancel_review",
        "cancel_backend_request",
        "SecondReviewer",
    ):
        assert forbidden not in exported

    # No new subprocess worker: the review package imports no subprocess module.
    import ai_dev_orchestrator.review.reviewer as reviewer_module
    import ai_dev_orchestrator.review.supervision as supervision_module

    for module in (reviewer_module, supervision_module):
        assert not hasattr(module, "subprocess")
        assert not hasattr(module, "multiprocessing")
        assert not hasattr(module, "asyncio")


def test_the_reviewer_cli_option_surface_did_not_expand():
    """Requirement 44, asserted against the real parameter list.

    Introspecting the Click command rather than grepping ``--help`` text, so the
    command's own prose — which deliberately *names* the options that do not
    exist — cannot make this pass or fail for the wrong reason.
    """
    import typer.main

    command = typer.main.get_command(cli.app)
    review = command.commands["l2-review-approved-file-edit"]  # type: ignore[attr-defined]

    declared: set[str] = set()
    for param in review.params:
        declared.update(param.opts)
        declared.update(param.secondary_opts)
    declared.discard("--help")

    assert declared == {
        "--project-config",
        "--approved-diff-proposal",
        "--verify-approved-file-edit",
        "--real-reviewer",
        "--format",
    }


def test_the_reviewer_command_list_did_not_grow():
    """Requirement 44: no new command was added by this phase."""
    names = {command.name for command in cli.app.registered_commands}

    assert "l2-review-approved-file-edit" in names
    for forbidden in (
        "l2-review-approved-file-edit-vllm",
        "l2-review-vllm",
        "l2-fix-approved-file-edit",
        "l2-implement",
        "pi-review",
    ):
        assert forbidden not in names


def test_the_suite_opens_no_socket(monkeypatch):
    """Belt and braces: every reviewer call here is MockTransport-backed."""

    def boom(*args, **kwargs):
        raise AssertionError("a real socket was opened by the reviewer tests")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)

    config = build_reviewer_client_config(
        _vllm_env(),
        model=VLLM_REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        provider="vllm",
    )
    # Building settings is inert; nothing here connects.
    assert config.base_url == VLLM_HTTPS_BASE_URL
