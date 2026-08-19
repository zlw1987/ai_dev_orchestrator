"""AIDO's operator token policy: model output-token limits are UNLIMITED BY DEFAULT.

The correction this suite locks came from real deployment evidence, and the
evidence matters because it explains why the default was wrong rather than merely
small. A reviewer benchmark inherited ``controlled_review.max_output_tokens:
2048`` from the shipped default. The reviewer model completed its request, the
provider reported a length finish condition, AIDO classified the attempt
``review_output_budget_exhausted``, and no packet was produced — a ceiling the
operator never intended to impose, silently applied to every request.

So the policy is stated exactly, and "unlimited" means exactly one thing on the
wire:

    AIDO sends NO OpenAI-compatible ``max_tokens`` field.

It does **not** mean a large substituted number, 32000, 131072, a model's context
size, a per-model constant, or anything inferred from a model name — AIDO has no
basis to invent any of those. The provider/model/backend still has its own native
context and output limits; those are **backend capability limits**, never an
AIDO-requested cap, and this suite proves AIDO does not describe them as one.

The optional interface survives: a positive integer is an explicit
operator-requested cap, sent verbatim on **both** possible semantic attempts.

What this correction did **not** touch, and what several tests here exist to
prove: RS1's request-issuance and wait supervision (transport retries forced to
zero, at most two semantic requests, one HTTP request per attempt, a terminal
stall, AIDO's own monotonic deadline), the strict review parser, provider
environment isolation, the absence of any fallback model or provider, the
verification-before-credential-read ordering, and the real smoke test's
deliberate 512-token connectivity probe.

**Every repository here is a synthetic Git repository created under pytest's own
``tmp_path``, and every verification program is a small synthetic Python script
written under ``tmp_path``.** No real target project is used, read, written, or
executed. **Every model call goes through ``httpx.MockTransport``**: no socket is
opened, no real endpoint is contacted, and no API key is needed.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.config_loader import load_project_config
from ai_dev_orchestrator.llm import client as llm_client_module
from ai_dev_orchestrator.llm.client import LLMClient
from ai_dev_orchestrator.llm.models import LLMClientConfig, LLMRequest
from ai_dev_orchestrator.models import (
    AIRoleConfig,
    ControlledReviewConfig,
    ProjectConfig,
)
from ai_dev_orchestrator.review import (
    ATTEMPT_OUTCOME_LABELS,
    ReviewPacket,
    attempt_outcome_label,
    build_compact_model_review_request,
    build_model_review_request,
    build_review_context,
    build_review_response_format,
    parse_model_review_response,
)
from ai_dev_orchestrator.review import packet as packet_module
from ai_dev_orchestrator.review import reviewer as reviewer_module
from ai_dev_orchestrator.review import supervision as supervision_module
from ai_dev_orchestrator.review.models import ReviewError
from ai_dev_orchestrator.review.reviewer import reviewer_env_names_for_provider

from review_fixtures import approved_diff_artifact, verification_report
from test_cli_l2_review_approved_file_edit import (
    REVIEWER_MODEL,
    VALID_REVIEW_JSON,
    _env,
    _run,
    _setup,
    _stdout_json,
    git_required,
    windows_only,
)
from test_cli_l2_review_supervision import (
    MALFORMED,
    TRUNCATED,
    _ok,
    _raises,
    _scripted_factory,
    _sent_text,
)
from test_cli_l2_review_vllm_provider import (
    VLLM_REVIEWER_MODEL,
    _recording_factory,
    _vllm_env,
)

# A configured finite cap, kept deliberately unround so an assertion cannot pass
# against some other constant by coincidence.
EXPLICIT_CAP = 4321


# -- reviewer blocks ----------------------------------------------------------
#
# The unlimited blocks OMIT the field entirely, which is the shipped operator
# policy. The finite block sets it, because an explicitly configured cap remains
# supported and is valuable coverage — it simply is not the default.

UNLIMITED_LITELLM_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
  attempt_timeout_seconds: 30
  compact_retry_on_unusable_output: true
"""

FINITE_LITELLM_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
  attempt_timeout_seconds: 30
  max_output_tokens: {EXPLICIT_CAP}
  compact_retry_on_unusable_output: true
"""

NULL_LITELLM_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
  attempt_timeout_seconds: 30
  max_output_tokens: null
  compact_retry_on_unusable_output: true
"""

UNLIMITED_FAST_DEADLINE_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
  attempt_timeout_seconds: 0.3
  compact_retry_on_unusable_output: true
"""

STRUCTURED_VLLM_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "vllm"
  model: "{VLLM_REVIEWER_MODEL}"
  attempt_timeout_seconds: 30
  vllm_structured_output: true
"""

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _context():
    """One synthetic redacted transmission copy, built offline."""
    return build_review_context(
        approved_diff=approved_diff_artifact(),
        verification=verification_report(),
    )


def _payload(request: LLMRequest) -> dict:
    """Serialize a request exactly as the shipped client would."""
    config = LLMClientConfig(
        base_url="http://fake.invalid/v1", api_key="fake", default_model="fake"
    )
    return LLMClient(config)._build_payload(request)


def _retry_env(_provider: str) -> dict[str, str]:
    """An environment that would give the generic client TWO transport retries."""
    return _env(AIDO_LITELLM_MAX_RETRIES="2")


def _review(tmp_path, script: list, *, block: str):
    repo, config, artifact = _setup(tmp_path, review_block=block)
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=_retry_env,
        client_factory=_scripted_factory(script, seen),
    )
    return code, seen, repo


# =============================================================================
# 1. Config — the optional interface and its default
# =============================================================================


def test_the_shipped_default_is_no_aido_output_token_cap():
    """Requirement 1: the default is None, not 2048 and not any other number."""
    assert ControlledReviewConfig().max_output_tokens is None
    assert (
        ControlledReviewConfig(enabled=True, model=REVIEWER_MODEL).max_output_tokens
        is None
    )
    assert ControlledReviewConfig.model_fields["max_output_tokens"].default is None


def test_yaml_with_the_block_enabled_and_no_cap_loads_as_no_cap():
    """Requirement 2: an enabled reviewer block need not mention the field."""
    project = _project(enabled=True, model=REVIEWER_MODEL)
    assert project.controlled_review.enabled is True
    assert project.controlled_review.max_output_tokens is None


def test_an_explicit_yaml_null_loads_as_no_cap(tmp_path):
    """Requirement 3, through the real YAML loader rather than a dict."""
    config = tmp_path / "project.yaml"
    config.write_text(
        "project_id: demo\n"
        "display_name: Demo\n"
        "repo:\n"
        '  workspace_path: "C:/never/touched"\n'
        '  github_repo: "demo/widgets"\n'
        '  branch_prefix: "ai/demo"\n'
        "controlled_review:\n"
        "  enabled: true\n"
        f'  model: "{REVIEWER_MODEL}"\n'
        "  max_output_tokens: null\n",
        encoding="utf-8",
    )

    assert load_project_config(config).controlled_review.max_output_tokens is None


@pytest.mark.parametrize("value", [1, 512, EXPLICIT_CAP, 32_001, 131_072])
def test_a_positive_configured_cap_is_accepted_exactly(value):
    """Requirement 4, and requirement 6: no arbitrary ceiling survives.

    The old ``le=32_000`` bound was an AIDO policy artifact and expressed no
    provider-independent truth — a backend's real limit belongs to the backend,
    and AIDO has no basis to guess it — so values above it now load unchanged.
    """
    settings = ControlledReviewConfig(
        enabled=True, model=REVIEWER_MODEL, max_output_tokens=value
    )
    assert settings.max_output_tokens == value


@pytest.mark.parametrize("value", [0, -1, -2048])
def test_zero_and_negative_caps_are_rejected(value):
    """Requirement 5. Neither is a way to spell "unlimited" — omit the field."""
    with pytest.raises(ValidationError):
        ControlledReviewConfig(
            enabled=True, model=REVIEWER_MODEL, max_output_tokens=value
        )


@pytest.mark.parametrize("value", [True, False])
def test_a_boolean_cap_is_rejected_rather_than_coerced(value):
    """Pydantic would otherwise turn ``true`` into a ONE-token ceiling."""
    with pytest.raises(ValidationError):
        ControlledReviewConfig(
            enabled=True, model=REVIEWER_MODEL, max_output_tokens=value
        )


def test_no_numeric_default_or_upper_ceiling_remains_in_the_field_schema():
    """Requirement 6, stated against the field metadata itself."""
    field = ControlledReviewConfig.model_fields["max_output_tokens"]
    assert field.default is None
    rendered = repr(field.metadata) + repr(field.annotation)
    for artifact in ("2048", "32000", "32_000", "le=", "Le("):
        assert artifact not in rendered


def test_the_shipped_project_configs_request_no_cap():
    """The real project config no longer inherits the 2048 ceiling."""
    for name in ("mis_project.yaml", "mis_project.yaml.example"):
        project = load_project_config(REPO_ROOT / "projects" / name)
        assert project.controlled_review.max_output_tokens is None, name
        # Every non-token reviewer setting is preserved, including the example's
        # deliberately disabled gate and the live project's enabled one.
        assert project.controlled_review.provider == "litellm", name
        assert project.controlled_review.attempt_timeout_seconds == 90.0, name
        assert (
            project.controlled_review.compact_retry_on_unusable_output is False
        ), name
        assert project.controlled_review.vllm_allow_insecure_http is False, name
        assert project.controlled_review.vllm_structured_output is False, name

    live = load_project_config(REPO_ROOT / "projects" / "mis_project.yaml")
    assert live.controlled_review.enabled is True
    assert live.controlled_review.model == "nemotron-3-super"


# =============================================================================
# 2. Wire payload — what is and is not serialized
# =============================================================================


def test_the_litellm_full_request_omits_max_tokens_when_no_cap_is_configured():
    """Requirement 7. "Unlimited" is an ABSENT key, never a substituted number."""
    payload = _payload(build_model_review_request(_context(), model=REVIEWER_MODEL))

    assert "max_tokens" not in payload
    assert payload["model"] == REVIEWER_MODEL


def test_the_litellm_compact_request_omits_max_tokens_when_no_cap_is_configured():
    """Requirement 8."""
    payload = _payload(
        build_compact_model_review_request(_context(), model=REVIEWER_MODEL)
    )

    assert "max_tokens" not in payload


def test_a_configured_cap_appears_exactly_in_both_litellm_requests():
    """Requirement 9. The compact retry shares the cap deliberately.

    "Compact" is about the INPUT context and the finding count. It is not a
    smaller output budget, so there is no second, smaller number here.
    """
    context = _context()
    full = _payload(
        build_model_review_request(
            context, model=REVIEWER_MODEL, max_output_tokens=EXPLICIT_CAP
        )
    )
    compact = _payload(
        build_compact_model_review_request(
            context, model=REVIEWER_MODEL, max_output_tokens=EXPLICIT_CAP
        )
    )

    assert full["max_tokens"] == EXPLICIT_CAP
    assert compact["max_tokens"] == EXPLICIT_CAP


def test_an_unstructured_vllm_review_omits_max_tokens_when_no_cap_is_configured():
    """Requirement 10. Provider parity: the vLLM path has no separate default."""
    payload = _payload(
        build_model_review_request(_context(), model=VLLM_REVIEWER_MODEL)
    )

    assert "max_tokens" not in payload
    assert "response_format" not in payload


def test_a_structured_vllm_review_sends_the_schema_and_no_max_tokens():
    """Requirement 11. The two are independent: a schema is not a token cap."""
    context = _context()
    response_format = build_review_response_format()
    for request in (
        build_model_review_request(
            context, model=VLLM_REVIEWER_MODEL, response_format=response_format
        ),
        build_compact_model_review_request(
            context, model=VLLM_REVIEWER_MODEL, response_format=response_format
        ),
    ):
        payload = _payload(request)
        assert "max_tokens" not in payload
        assert payload["response_format"]["type"] == "json_schema"
        assert "schema" in payload["response_format"]["json_schema"]


def test_a_finite_structured_vllm_review_sends_both_the_schema_and_the_cap():
    """Requirement 12."""
    context = _context()
    response_format = build_review_response_format()
    for request in (
        build_model_review_request(
            context,
            model=VLLM_REVIEWER_MODEL,
            max_output_tokens=EXPLICIT_CAP,
            response_format=response_format,
        ),
        build_compact_model_review_request(
            context,
            model=VLLM_REVIEWER_MODEL,
            max_output_tokens=EXPLICIT_CAP,
            response_format=response_format,
        ),
    ):
        payload = _payload(request)
        assert payload["max_tokens"] == EXPLICIT_CAP
        assert payload["response_format"]["type"] == "json_schema"


# =============================================================================
# 3. Supervision and packet provenance
# =============================================================================


@windows_only
@git_required
def test_an_unlimited_review_records_null_at_every_provenance_location(
    tmp_path, capsys
):
    """Requirement 13, end to end through the real command.

    Null must be null: not 0, not -1, not a sentinel integer, and not the string
    "unlimited". It means exactly "AIDO did not request max_tokens".
    """
    code, seen, _ = _review(
        tmp_path, [_ok(VALID_REVIEW_JSON)], block=UNLIMITED_LITELLM_BLOCK
    )

    assert code == 0
    assert len(seen) == 1
    assert "max_tokens" not in seen[0]

    packet = _stdout_json(capsys)
    supervision = packet["reviewer_supervision"]

    assert supervision["requested_max_output_tokens"] is None
    assert [
        attempt["requested_max_output_tokens"] for attempt in supervision["attempts"]
    ] == [None]

    # The serialized JSON says `null`, and never a stand-in for a number.
    raw = json.dumps(supervision)
    assert '"requested_max_output_tokens": null' in raw
    for sentinel in ('"requested_max_output_tokens": 0', '"unlimited"', '": -1'):
        assert sentinel not in raw

    # The packet is still a valid packet under the unchanged schema version.
    ReviewPacket.model_validate(packet)


@windows_only
@git_required
def test_a_null_configured_cap_behaves_exactly_like_an_omitted_one(tmp_path, capsys):
    code, seen, _ = _review(
        tmp_path, [_ok(VALID_REVIEW_JSON)], block=NULL_LITELLM_BLOCK
    )

    assert code == 0
    assert "max_tokens" not in seen[0]
    assert (
        _stdout_json(capsys)["reviewer_supervision"]["requested_max_output_tokens"]
        is None
    )


@windows_only
@git_required
def test_a_finite_review_records_the_exact_integer_everywhere(tmp_path, capsys):
    """Requirement 14, on both attempts of a compact retry."""
    code, seen, _ = _review(
        tmp_path,
        [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)],
        block=FINITE_LITELLM_BLOCK,
    )

    assert code == 0
    assert [payload["max_tokens"] for payload in seen] == [EXPLICIT_CAP, EXPLICIT_CAP]

    supervision = _stdout_json(capsys)["reviewer_supervision"]
    assert supervision["requested_max_output_tokens"] == EXPLICIT_CAP
    assert [
        attempt["requested_max_output_tokens"] for attempt in supervision["attempts"]
    ] == [EXPLICIT_CAP, EXPLICIT_CAP]


@windows_only
@git_required
def test_a_length_finish_reason_without_an_aido_cap_is_classified_truthfully(
    tmp_path, capsys
):
    """Requirement 15 — the wording rule this whole correction turns on.

    A provider may report a length finish condition even when AIDO requested no
    cap: the backend has its own native output limit. The classification token is
    retained for artifact compatibility, but nothing human-facing may claim an
    AIDO-requested budget was exhausted, and AIDO must not invent knowledge about
    which native limit was reached.
    """
    code, seen, _ = _review(
        tmp_path,
        [_ok(TRUNCATED, finish_reason="length"), _ok(VALID_REVIEW_JSON)],
        block=UNLIMITED_LITELLM_BLOCK,
    )

    assert code == 0
    assert len(seen) == 2
    assert all("max_tokens" not in payload for payload in seen)

    captured = capsys.readouterr()
    supervision = json.loads(captured.out)["reviewer_supervision"]
    assert supervision["first_attempt_outcome"] == "review_output_budget_exhausted"
    assert supervision["attempts"][0]["finish_reason"] == "length"
    assert supervision["attempts"][0]["requested_max_output_tokens"] is None

    err = captured.err
    assert "REVIEW UNUSABLE" in err
    # The human is told whose limit it was...
    assert "AIDO requested NO output-token cap" in err
    assert "own native output limit" in err
    # ...and AIDO never claims to know which native limit that was.
    assert "does not claim to know which native limit" in err


def test_the_outcome_label_distinguishes_the_two_length_cases():
    """The same rule at the unit level, both directions."""
    no_cap = attempt_outcome_label("review_output_budget_exhausted", None)
    finite = attempt_outcome_label("review_output_budget_exhausted", EXPLICIT_CAP)

    assert "AIDO requested NO output-token cap" in no_cap
    assert f"AIDO requested max_tokens={EXPLICIT_CAP}" in finite
    assert "AIDO requested NO output-token cap" not in finite

    # Every other outcome reads identically either way.
    for outcome in ATTEMPT_OUTCOME_LABELS:
        if outcome == "review_output_budget_exhausted":
            continue
        assert attempt_outcome_label(outcome, None) == ATTEMPT_OUTCOME_LABELS[outcome]
        assert (
            attempt_outcome_label(outcome, EXPLICIT_CAP)
            == ATTEMPT_OUTCOME_LABELS[outcome]
        )


def test_the_packet_output_cap_note_explains_both_states():
    note = supervision_module.SUPERVISION_OUTPUT_CAP_NOTE

    assert "NO model output-token ceiling by default" in note
    assert "null" in note
    assert "never means zero" in note
    assert "backend capability limits, not an AIDO-requested cap" in note


# =============================================================================
# 4. RS1 supervision is unchanged
# =============================================================================


@windows_only
@git_required
def test_the_compact_retry_still_costs_exactly_two_requests_without_a_cap(
    tmp_path, capsys
):
    """Requirements 16 and 18, on the unlimited default.

    ``AIDO_LITELLM_MAX_RETRIES=2`` is in the environment, so without RS1's forced
    ``max_retries=0`` this would be far more than two requests.
    """
    code, seen, _ = _review(
        tmp_path,
        [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)],
        block=UNLIMITED_LITELLM_BLOCK,
    )

    assert code == 0
    assert len(seen) == 2
    assert all("max_tokens" not in payload for payload in seen)

    supervision = _stdout_json(capsys)["reviewer_supervision"]
    assert supervision["semantic_attempts_used"] == 2
    assert supervision["compact_retry_used"] is True
    assert supervision["max_semantic_attempts"] == 2
    assert supervision["transport_retries_per_attempt"] == 0
    assert supervision["transport_requests_per_attempt"] == 1
    assert supervision["same_model_used_for_every_attempt"] is True
    assert supervision["fallback_reviewer_model_available"] is False

    # The compact retry really is a smaller INPUT, not a smaller output budget.
    # Compared on the user message specifically: the system prompt's wording
    # length is not the signal (Issue-1 rewording made it slightly longer while
    # dropping the false "length budget" claim), the transmitted CONTEXT is.
    full_user = seen[0]["messages"][1]["content"]
    compact_user = seen[1]["messages"][1]["content"]
    assert len(compact_user) < len(full_user)


@windows_only
@git_required
def test_the_compact_retry_still_costs_exactly_two_requests_with_a_cap(tmp_path):
    """Requirement 16, on the finite-cap path."""
    code, seen, _ = _review(
        tmp_path,
        [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)],
        block=FINITE_LITELLM_BLOCK,
    )

    assert code == 0
    assert len(seen) == 2


@windows_only
@git_required
def test_a_timeout_is_still_terminal_with_no_aido_cap(tmp_path, capsys):
    """Requirement 17. The wait bound is not a token bound, and never became one."""
    code, seen, _ = _review(
        tmp_path,
        [_raises(httpx.ReadTimeout("synthetic"))],
        block=UNLIMITED_LITELLM_BLOCK,
    )

    assert code == 4
    assert len(seen) == 1

    err = capsys.readouterr().err
    assert "=== REVIEW STALLED ===" in err
    assert "compact retry authorized" not in err
    assert "Attempts used:    1 of at most 2" in err


@windows_only
@git_required
def test_an_aido_deadline_is_still_terminal_with_no_aido_cap(tmp_path, capsys):
    """The FU2 supervisor deadline, unchanged by the token-policy correction."""
    import time

    def _slow(request: httpx.Request) -> httpx.Response:
        time.sleep(3.0)
        return httpx.Response(200, json={"choices": []})

    code, seen, _ = _review(tmp_path, [_slow], block=UNLIMITED_FAST_DEADLINE_BLOCK)

    assert code == 4
    assert len(seen) == 1
    assert "=== REVIEW STALLED ===" in capsys.readouterr().err


def test_the_supervisor_still_takes_no_configurable_attempt_count():
    """No token-policy field grew into an attempt or retry knob."""
    assert supervision_module.MAX_SEMANTIC_REVIEW_ATTEMPTS == 2
    assert supervision_module.REVIEWER_TRANSPORT_MAX_RETRIES == 0
    assert supervision_module.TRANSPORT_REQUESTS_PER_ATTEMPT == 1
    assert supervision_module.RETRY_ELIGIBLE_OUTCOMES == (
        "review_output_budget_exhausted",
        "review_unusable_output",
    )
    for field in (
        "max_attempts",
        "max_semantic_attempts",
        "retry_on_timeout",
        "fallback_model",
        "reviewer_chain",
        "secondary_model",
    ):
        assert field not in ControlledReviewConfig.model_fields


# =============================================================================
# 5. Safety — what this change must not have touched
# =============================================================================


def test_the_strict_review_parser_is_unchanged():
    """Requirement 19. Rejected, never repaired — no fence stripping appeared."""
    assert parse_model_review_response(VALID_REVIEW_JSON).verdict in {
        "approve",
        "changes_requested",
        "needs_human_review",
    }
    with pytest.raises(ReviewError):
        parse_model_review_response("```json\n" + VALID_REVIEW_JSON + "\n```")
    with pytest.raises(ReviewError):
        parse_model_review_response(MALFORMED)

    source = inspect.getsource(parse_model_review_response)
    for repair in ("```", "strip_fence", "extract", "regex", "re."):
        assert repair not in source


def test_no_reasoning_field_is_read_or_reported():
    """Requirement 20."""
    for module in (supervision_module, packet_module, llm_client_module):
        source = inspect.getsource(module)
        for field in ("reasoning_content", "thinking_blocks", '"reasoning"'):
            assert field not in source, module.__name__

    assert "reasoning" not in supervision_module.ReviewAttemptRecord.model_fields


def test_provider_environment_isolation_is_unchanged():
    """Requirement 21: the reader still resolves ONE family before reading."""
    litellm = reviewer_env_names_for_provider("litellm")
    vllm = reviewer_env_names_for_provider("vllm")

    assert all("LITELLM" in name for name in litellm)
    assert all("VLLM" in name for name in vllm)
    assert not set(litellm) & set(vllm)
    # And there is still no union constant to regress to.
    assert not hasattr(reviewer_module, "REVIEWER_ENV_NAMES")


@windows_only
@git_required
def test_no_fallback_model_or_provider_was_introduced(tmp_path, capsys):
    """Requirement 22."""
    code, seen, _ = _review(
        tmp_path, [_ok(VALID_REVIEW_JSON)], block=UNLIMITED_LITELLM_BLOCK
    )

    assert code == 0
    assert seen[0]["model"] == REVIEWER_MODEL

    packet = _stdout_json(capsys)
    assert packet["reviewer"]["model"] == REVIEWER_MODEL
    assert packet["reviewer"]["fallback_model_used"] is False
    assert (
        packet["reviewer_supervision"]["fallback_reviewer_model_available"] is False
    )


@windows_only
@git_required
def test_verification_still_runs_before_any_reviewer_environment_read(tmp_path):
    """Requirement 23: a failing verification contacts no model at all.

    The client factory below would fail the test loudly if it were ever called,
    and the environment reader raises if consulted — so a model request could not
    happen silently.
    """
    failing = "import sys\nsys.exit(1)\n"
    repo, config, artifact = _setup(
        tmp_path, body=failing, review_block=UNLIMITED_LITELLM_BLOCK
    )

    def _forbidden_env(_provider: str):
        raise AssertionError(
            "reviewer environment was read before verification passed"
        )

    def _forbidden_factory(_config):
        raise AssertionError("a reviewer client was built before verification passed")

    code = _run(
        config, artifact, read_env=_forbidden_env, client_factory=_forbidden_factory
    )
    assert code == 2


@windows_only
@git_required
def test_the_vllm_path_has_no_separate_token_default_end_to_end(tmp_path, capsys):
    """Provider parity, through the command, over the direct vLLM provider."""
    repo, config, artifact = _setup(tmp_path, review_block=STRUCTURED_VLLM_BLOCK)
    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen),
    )

    assert code == 0
    assert len(seen) == 1
    assert "max_tokens" not in seen[0]
    assert seen[0]["response_format"]["type"] == "json_schema"

    packet = _stdout_json(capsys)
    assert packet["reviewer_supervision"]["requested_max_output_tokens"] is None
    assert packet["reviewer"]["provider"] == "vllm"
    # No AIDO_VLLM_DEFAULT_MODEL exists, and the model still comes from config.
    assert packet["reviewer"]["model"] == VLLM_REVIEWER_MODEL


# =============================================================================
# 6. The dormant ai_roles shape
# =============================================================================


def test_ai_role_max_tokens_defaults_to_no_cap():
    """Requirement 25. The dormant shape must not smuggle a future 8192 ceiling."""
    role = AIRoleConfig(provider="litellm_local", model="some-model")
    assert role.max_tokens is None
    assert AIRoleConfig.model_fields["max_tokens"].default is None


def test_an_explicit_positive_ai_role_max_tokens_still_validates():
    """Requirement 26: the optional interface exists here too."""
    role = AIRoleConfig(
        provider="litellm_local", model="some-model", max_tokens=EXPLICIT_CAP
    )
    assert role.max_tokens == EXPLICIT_CAP


@pytest.mark.parametrize("value", [0, -1, True])
def test_a_nonpositive_or_boolean_ai_role_max_tokens_is_rejected(value):
    with pytest.raises(ValidationError):
        AIRoleConfig(provider="litellm_local", model="some-model", max_tokens=value)


def test_ai_roles_is_still_not_controlled_review_authority():
    """Requirement 27. The reviewer reads ``controlled_review`` and nothing else."""
    source = inspect.getsource(reviewer_module)
    assert "ai_roles" not in source
    assert "AIRoleConfig" not in source

    # An ai_roles block naming a different model changes nothing about the gate.
    assert _project(enabled=True, model=REVIEWER_MODEL).ai_roles == {}
    with_roles = ProjectConfig.model_validate(
        {
            "project_id": "demo_project",
            "display_name": "Demo",
            "repo": {
                "workspace_path": "C:/never/touched",
                "github_repo": "demo/widgets",
                "branch_prefix": "ai/demo",
            },
            "ai_roles": {
                "reviewer": {
                    "provider": "litellm_local",
                    "model": "a-completely-different-model",
                    "max_tokens": 128,
                }
            },
            "controlled_review": {"enabled": True, "model": REVIEWER_MODEL},
        }
    )
    assert with_roles.controlled_review.model == REVIEWER_MODEL
    assert with_roles.controlled_review.max_output_tokens is None


# =============================================================================
# 7. The smoke probe is deliberately exempt
# =============================================================================


def test_the_real_smoke_probe_still_sends_its_fixed_512_token_bound():
    """Requirement 28. A bounded connectivity probe, not the ordinary policy."""
    assert cli._REAL_SMOKE_MAX_TOKENS == 512

    source = inspect.getsource(cli)
    assert "max_tokens=_REAL_SMOKE_MAX_TOKENS," in source


def test_the_fake_smoke_request_still_sends_no_max_tokens():
    """Requirement 29: the dry-run path was already unlimited and stays so."""
    source = inspect.getsource(cli.llm_smoke_test)
    assert "max_tokens" not in source


# =============================================================================
# 8. Follow-up: the compact prompt no longer claims a length budget
# =============================================================================


def test_the_compact_system_message_does_not_claim_a_length_budget():
    """The compact retry's own wording must match the accepted token policy.

    Under unlimited-by-default token semantics, the compact retry is bounded by
    reduced INPUT context and a five-finding cap — never, by default, by an
    AIDO-requested output-token/length budget. The prompt must not claim
    otherwise, regardless of what ``max_output_tokens`` happens to be configured
    to for a given project: the prompt text is fixed and deterministic and does
    not branch on it.
    """
    from ai_dev_orchestrator.review.request import _build_compact_system_message

    system = _build_compact_system_message()
    lowered = system.lower()

    assert "length budget" not in lowered
    assert "strict length" not in lowered

    # States the real constraints instead.
    assert "reduced context" in lowered
    assert "at most five" in lowered or "at most 5" in lowered
    assert "no third attempt" in lowered


# =============================================================================
# 9. Follow-up: the full first-attempt prompt no longer forecloses a retry
# =============================================================================


def test_the_full_system_message_does_not_falsely_foreclose_a_second_attempt():
    """The full first-attempt prompt must not contradict accepted RS1 semantics.

    A project may enable ONE compact second semantic attempt after a completed
    but unusable first response (RS1, ``compact_retry_on_unusable_output``). The
    fixed first-attempt prompt must therefore not claim that no second attempt
    can ever exist — while still making clear that THIS reply is final: never
    repaired, merged, or quoted into whatever retry may follow. The prompt is
    fixed and deterministic; it must not promise a retry will happen and must
    not branch on the project's retry setting.
    """
    from ai_dev_orchestrator.review.request import _build_system_message

    system = _build_system_message()
    # Normalize wrapped whitespace so a wrapped line doesn't break a phrase
    # match: the prompt text wraps for readability, not for meaning.
    lowered = " ".join(system.lower().split())

    # The old false claim is gone.
    assert "there is no second attempt" not in lowered
    assert "no follow-up prompt" not in lowered

    # This reply is still final from the model's own point of view: never
    # repaired, merged, or treated as something a follow-up will fix.
    assert "never repaired" in lowered
    assert "merged" in lowered

    # A possible second attempt is acknowledged as project-conditional and as a
    # NEW attempt, not a repair channel for this one.
    assert "new, independent semantic review attempt" in lowered
    assert "never a repair of this one" in lowered
    assert "do not assume a second attempt will happen" in lowered

    # Deterministic: identical output on repeated calls, and no branching on the
    # project's retry opt-in ever reaches this function (it takes no arguments).
    assert _build_system_message() == system
    import inspect

    assert "compact_retry_on_unusable_output" not in inspect.signature(
        _build_system_message
    ).parameters
