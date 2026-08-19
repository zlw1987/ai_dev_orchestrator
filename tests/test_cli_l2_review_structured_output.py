"""Phase 5F2E-V2 tests: structured vLLM reviewer output.

This slice adds **one** thing: a direct-vLLM reviewer request may carry the
``ModelReviewResult`` JSON Schema in the OpenAI-compatible
``response_format``/``json_schema`` field, so the **server constrains
generation**. It exists because of observed evidence, not a theory:

- a controlled trial against a direct vLLM endpoint returned HTTP 200 with
  ``finish_reason="stop"`` and a review that correctly identified a seeded
  semantic bug — wrapped in a ```` ```json ```` markdown fence, which the strict
  parser rejected, correctly;
- the **identical** prompt, model, temperature and token cap, with only a
  JSON-Schema ``response_format`` added, produced one bare JSON object the
  *unmodified* parser accepted.

So the failure was the **envelope**, not the reasoning, and the fix belongs on
the generation side. Most of this file exists to prove what did **not** change:

1. **The parser** — unchanged and final. A fenced reply is still rejected, a
   bare object is still accepted, no repair helper was added, and a
   schema-valid reply that violates an AIDO-only Pydantic validator is still
   rejected.
2. **Serialization** — ``response_format`` is omitted entirely from every
   request that does not ask for it: planning, the real smoke test, a LiteLLM
   controlled review, and a vLLM review with the opt-in off.
3. **RS1** — transport retries forced to zero, one HTTP request per semantic
   attempt, a terminal stall, at most two semantic requests, and — the new
   rule — **no structured → unstructured fallback**.
4. **The packet** — ``review-packet.v4``, with ``v1``/``v2``/``v3`` meanings
   preserved and explicitly not claiming structured-output provenance.

**Every repository here is a synthetic Git repository created under pytest's own
``tmp_path``, and every verification program is a small synthetic Python script
written under ``tmp_path``.** No real target project is used, read, written, or
executed. **Every reviewer call goes through ``httpx.MockTransport``**: no socket
is opened, no real endpoint is contacted, and no API key is needed.
"""

from __future__ import annotations

import inspect
import json

import httpx
import pytest
from pydantic import ValidationError

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.llm.client import LLMClient
from ai_dev_orchestrator.llm.models import (
    LLMClientConfig,
    LLMJSONSchemaResponseFormat,
    LLMMessage,
    LLMRequest,
)
from ai_dev_orchestrator.models import ControlledReviewConfig, ProjectConfig
from ai_dev_orchestrator.review import (
    COMPACT_RETRY_MAX_FINDINGS,
    MAX_SEMANTIC_REVIEW_ATTEMPTS,
    REVIEWER_TRANSPORT_MAX_RETRIES,
    REVIEW_PACKET_SCHEMA_VERSION,
    REVIEW_PACKET_SCHEMA_VERSION_HISTORY,
    REVIEW_PACKET_SCHEMA_VERSION_V1,
    REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS,
    REVIEW_PACKET_SCHEMA_VERSION_V2,
    REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS,
    REVIEW_PACKET_SCHEMA_VERSION_V3,
    REVIEW_PACKET_SCHEMA_VERSION_V3_SEMANTICS,
    REVIEW_RESPONSE_FORMAT_NAME,
    REVIEW_RESPONSE_SCHEMA_SOURCE,
    STRUCTURED_OUTPUT_MODE_JSON_SCHEMA,
    STRUCTURED_OUTPUT_MODE_NONE,
    STRUCTURED_OUTPUT_MODES,
    STRUCTURED_OUTPUT_PARSER_AUTHORITY_NOTE,
    ModelReviewResult,
    ReviewPacket,
    ReviewRefusedError,
    ReviewValidationError,
    build_compact_model_review_request,
    build_model_review_request,
    build_review_context,
    build_review_response_format,
    check_controlled_review_gate,
    parse_model_review_response,
)
from ai_dev_orchestrator.review import request as review_request_module
from ai_dev_orchestrator.review import models as review_models_module

from review_fixtures import approved_diff_artifact, verification_report
from test_cli_l2_review_approved_file_edit import (
    FAKE_API_KEY,
    FAKE_BASE_URL,
    REVIEWER_MODEL,
    VALID_REVIEW_JSON,
    _env,
    _mock_client_factory,
    _run,
    _setup,
    _stdout_json,
    git_required,
    windows_only,
)
from test_cli_l2_review_vllm_provider import (
    VLLM_ENV_BASE_URL,
    VLLM_HTTPS_BASE_URL,
    VLLM_HTTPS_HOST,
    VLLM_REVIEWER_MODEL,
    _recording_factory,
    _vllm_env,
)

# The exact fenced reply the observed trial produced: correct review, wrong
# envelope. Reproduced in shape only — the content is this suite's own fixture.
FENCED_REVIEW_JSON = f"```json\n{VALID_REVIEW_JSON}\n```"


def _structured_vllm_block(
    *,
    model: str = VLLM_REVIEWER_MODEL,
    provider: str = "vllm",
    structured: bool | None = True,
    compact_retry: bool = False,
) -> str:
    """A ``controlled_review`` block with the V2 opt-in spelled explicitly."""
    lines = [
        "controlled_review:",
        "  enabled: true",
        f'  provider: "{provider}"',
        f'  model: "{model}"',
        f"  compact_retry_on_unusable_output: {str(compact_retry).lower()}",
    ]
    if structured is not None:
        lines.append(f"  vllm_structured_output: {str(structured).lower()}")
    return "\n".join(lines) + "\n"


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


# =============================================================================
# 1. Config
# =============================================================================


def test_an_existing_v1_config_loads_unchanged():
    """Requirement 1: no accepted Phase 5F2E-V1 config needs a new field."""
    settings = ControlledReviewConfig(enabled=True, model=REVIEWER_MODEL)

    assert settings.provider == "litellm"
    # Every accepted default is untouched by V2.
    assert settings.vllm_allow_insecure_http is False
    assert settings.attempt_timeout_seconds == 90.0
    assert settings.max_output_tokens == 2048
    assert settings.compact_retry_on_unusable_output is False


def test_vllm_structured_output_defaults_false():
    """Requirement 2: the opt-in ships off, so accepted behavior is preserved."""
    assert ControlledReviewConfig().vllm_structured_output is False
    assert (
        ControlledReviewConfig(
            enabled=True, provider="vllm", model=VLLM_REVIEWER_MODEL
        ).vllm_structured_output
        is False
    )


def test_vllm_plus_structured_true_is_accepted_by_the_gate():
    """Requirement 3."""
    authority = check_controlled_review_gate(
        _project(
            enabled=True,
            provider="vllm",
            model=VLLM_REVIEWER_MODEL,
            vllm_structured_output=True,
        )
    )

    assert authority.provider == "vllm"
    assert authority.model == VLLM_REVIEWER_MODEL
    assert authority.structured_output_mode == STRUCTURED_OUTPUT_MODE_JSON_SCHEMA


def test_litellm_plus_structured_true_is_refused_at_the_gate():
    """Requirement 4: refused, never silently ignored for LiteLLM."""
    with pytest.raises(ReviewRefusedError) as excinfo:
        check_controlled_review_gate(
            _project(
                enabled=True,
                provider="litellm",
                model=REVIEWER_MODEL,
                vllm_structured_output=True,
            )
        )

    message = str(excinfo.value)
    assert "structured output error" in message
    assert "'litellm'" in message
    assert "refused rather than ignored" in message
    assert "Nothing was contacted." in message


def test_the_gate_reports_none_for_every_unstructured_combination():
    """The other three cells of the two-by-two, all mode 'none'."""
    for provider, model in (("litellm", REVIEWER_MODEL), ("vllm", VLLM_REVIEWER_MODEL)):
        authority = check_controlled_review_gate(
            _project(enabled=True, provider=provider, model=model)
        )
        assert authority.structured_output_mode == STRUCTURED_OUTPUT_MODE_NONE

    explicit_off = check_controlled_review_gate(
        _project(
            enabled=True,
            provider="vllm",
            model=VLLM_REVIEWER_MODEL,
            vllm_structured_output=False,
        )
    )
    assert explicit_off.structured_output_mode == STRUCTURED_OUTPUT_MODE_NONE


def test_arbitrary_structured_output_config_is_rejected():
    """Requirement 5: one narrow boolean, not a structured-output framework."""
    for extra in (
        {"response_format": {"type": "json_schema"}},
        {"json_schema": {"name": "x"}},
        {"schema": "{}"},
        {"schema_path": "C:/schema.json"},
        {"schema_file": "schema.json"},
        {"guided_json": "{}"},
        {"guided_grammar": "root ::= object"},
        {"guided_regex": ".*"},
        {"grammar": "root ::= object"},
        {"regex": ".*"},
        {"structured_output": True},
        {"structured_output_mode": "json_schema"},
        {"vllm_structured_output_mode": "json_schema"},
        {"extra_body": {"guided_json": {}}},
        {"provider_capabilities": ["json_schema"]},
    ):
        with pytest.raises(ValidationError):
            ControlledReviewConfig(
                enabled=True, provider="vllm", model=VLLM_REVIEWER_MODEL, **extra
            )


def test_the_structured_opt_in_is_a_plain_bool_not_a_mode_string():
    """No arbitrary mode may be smuggled through the one field that exists."""
    for bad in ("json_schema", "guided_json", "grammar", 2, [], {}):
        with pytest.raises(ValidationError):
            ControlledReviewConfig(
                enabled=True,
                provider="vllm",
                model=VLLM_REVIEWER_MODEL,
                vllm_structured_output=bad,
            )


# =============================================================================
# 2. Schema source
# =============================================================================


def test_the_schema_is_generated_from_the_shipped_model():
    """Requirement 6: generated, never a hand-maintained duplicate."""
    response_format = build_review_response_format()

    assert response_format.type == "json_schema"
    assert response_format.name == REVIEW_RESPONSE_FORMAT_NAME == "aido_controlled_review"
    # Byte-for-byte the CURRENT generated schema, so the two cannot drift.
    assert response_format.json_schema == ModelReviewResult.model_json_schema()
    assert (
        REVIEW_RESPONSE_SCHEMA_SOURCE
        == "ai_dev_orchestrator.review.models.ModelReviewResult"
    )


def test_no_hand_written_duplicate_schema_exists_in_the_source():
    """Requirement 6, the negative half: exactly one generating call site."""
    source = inspect.getsource(review_request_module)

    assert source.count("model_json_schema()") == 1
    # No literal JSON-Schema keywords were typed out by hand anywhere in the
    # module that builds the response format.
    for keyword in ('"$defs"', '"additionalProperties"', '"properties"', '"$ref"'):
        assert keyword not in source


def test_the_generated_schema_retains_every_structural_constraint():
    """Requirement 7: nothing is simplified, weakened, or post-processed."""
    schema = build_review_response_format().json_schema

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == sorted(
        ["verdict", "summary", "findings", "residual_risks", "human_notes"]
    )
    assert schema["properties"]["verdict"]["enum"] == [
        "approve",
        "changes_requested",
        "needs_human_review",
    ]

    finding = schema["$defs"]["ReviewFinding"]
    assert finding["additionalProperties"] is False
    assert finding["properties"]["severity"]["enum"] == [
        "blocker",
        "major",
        "minor",
        "nit",
    ]
    assert finding["properties"]["category"]["enum"] == [
        "correctness",
        "security",
        "testing",
        "scope",
        "maintainability",
        "other",
    ]
    # The nullable line shape survives exactly as generated.
    assert finding["properties"]["line"]["anyOf"] == [
        {"type": "integer"},
        {"type": "null"},
    ]
    assert sorted(finding["required"]) == sorted(
        ["severity", "category", "message", "suggested_action"]
    )
    # The finding list is a $ref into the same generated definition.
    assert schema["properties"]["findings"]["items"] == {
        "$ref": "#/$defs/ReviewFinding"
    }


def test_the_schema_does_not_and_cannot_express_the_pydantic_validators():
    """Requirement 8: the boundary is real, documented, and asserted."""
    schema = build_review_response_format().json_schema
    rendered = json.dumps(schema)

    # None of AIDO's model-level rules appear in the generated schema: the
    # string length caps, the positive-line rule, the list bounds, or the
    # verdict/finding consistency rules.
    for absent in ("maxLength", "maxItems", "exclusiveMinimum", "minimum"):
        assert absent not in rendered

    note = STRUCTURED_OUTPUT_PARSER_AUTHORITY_NOTE
    assert "constrains GENERATION" in note
    assert "does not replace the strict parser" in note
    assert "FINAL authority" in note
    assert "rejects rather than repairs" in note


# =============================================================================
# 3. Request serialization
# =============================================================================


def test_an_ordinary_request_serializes_without_response_format():
    """Requirement 9."""
    request = LLMRequest(
        model="fake-model", messages=[LLMMessage(role="user", content="hello")]
    )

    assert request.response_format is None
    assert "response_format" not in _payload(request)


def test_the_planner_and_smoke_callers_send_no_response_format():
    """Requirement 10: no existing caller's payload changed."""
    from ai_dev_orchestrator.github.issue_parser import parse_issue_body
    from ai_dev_orchestrator.github.models import GitHubIssue
    from ai_dev_orchestrator.plan.model_planner import build_model_l1_plan_request

    issue = GitHubIssue(
        number=42,
        title="Round invoice totals",
        body="Totals should be rounded to two places.",
        state="open",
        html_url="https://example.invalid/issues/42",
    )
    request = build_model_l1_plan_request(
        issue, parse_issue_body(issue.body), _project(), model="fake-planner-model"
    )

    assert request.response_format is None
    assert "response_format" not in _payload(request)

    # The two CLI-built requests (dry-run smoke and real smoke) never name the
    # field at all, so neither can acquire one by accident.
    for function in (cli.llm_smoke_test, cli._run_real_llm_smoke_test):
        assert "response_format" not in inspect.getsource(function)


@windows_only
@git_required
def test_a_litellm_controlled_review_sends_no_response_format(tmp_path):
    """Requirement 11: LiteLLM is untouched by this feature."""
    _, config, artifact = _setup(tmp_path)

    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _env(),
        client_factory=_mock_client_factory(seen),
    )

    assert code == 0
    assert len(seen) == 1
    assert "response_format" not in seen[0]


@windows_only
@git_required
@pytest.mark.parametrize("structured", [None, False])
def test_a_vllm_review_without_the_opt_in_sends_no_response_format(
    tmp_path, structured
):
    """Requirement 12: accepted V1 behavior is preserved exactly."""
    _, config, artifact = _setup(
        tmp_path, review_block=_structured_vllm_block(structured=structured)
    )

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
    assert "response_format" not in seen[0]


@windows_only
@git_required
def test_a_structured_vllm_full_attempt_sends_the_generated_schema(tmp_path):
    """Requirement 13."""
    _, config, artifact = _setup(
        tmp_path, review_block=_structured_vllm_block(structured=True)
    )

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

    response_format = seen[0]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "aido_controlled_review"
    assert (
        response_format["json_schema"]["schema"]
        == ModelReviewResult.model_json_schema()
    )


@windows_only
@git_required
def test_a_structured_compact_retry_sends_the_same_schema(tmp_path):
    """Requirement 14: no smaller second schema for the compact attempt."""
    _, config, artifact = _setup(
        tmp_path,
        review_block=_structured_vllm_block(structured=True, compact_retry=True),
    )

    configs: list = []
    seen: list[dict] = []
    replies = iter([FENCED_REVIEW_JSON, VALID_REVIEW_JSON])

    def action(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": VLLM_REVIEWER_MODEL,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": next(replies)},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen, action=action),
    )

    assert code == 0
    assert len(seen) == MAX_SEMANTIC_REVIEW_ATTEMPTS == 2
    # Byte-identical response_format on both attempts.
    assert seen[0]["response_format"] == seen[1]["response_format"]
    assert (
        seen[1]["response_format"]["json_schema"]["schema"]
        == ModelReviewResult.model_json_schema()
    )
    # The prompts still differ — the retry is a smaller review, not a repair.
    assert seen[0]["messages"] != seen[1]["messages"]


def test_structured_output_changes_no_other_payload_field():
    """Requirement 15: the ONLY delta is the added key."""
    context = _context()
    plain = _payload(
        build_model_review_request(
            context, model=VLLM_REVIEWER_MODEL, max_output_tokens=2048
        )
    )
    structured = _payload(
        build_model_review_request(
            context,
            model=VLLM_REVIEWER_MODEL,
            max_output_tokens=2048,
            response_format=build_review_response_format(),
        )
    )

    assert set(structured) - set(plain) == {"response_format"}
    assert set(plain) - set(structured) == set()
    for key in plain:
        assert structured[key] == plain[key], key

    # The same holds for the compact request.
    compact_plain = _payload(
        build_compact_model_review_request(
            context, model=VLLM_REVIEWER_MODEL, max_output_tokens=2048
        )
    )
    compact_structured = _payload(
        build_compact_model_review_request(
            context,
            model=VLLM_REVIEWER_MODEL,
            max_output_tokens=2048,
            response_format=build_review_response_format(),
        )
    )
    assert set(compact_structured) - set(compact_plain) == {"response_format"}
    for key in compact_plain:
        assert compact_structured[key] == compact_plain[key], key


def test_the_typed_response_format_expresses_only_the_json_schema_shape():
    """No generic extra_body, kwargs, or provider body dictionary exists."""
    assert set(LLMJSONSchemaResponseFormat.model_fields) == {
        "type",
        "name",
        "json_schema",
    }
    # `type` is a closed literal: no json_object, grammar, or regex mode.
    with pytest.raises(ValidationError):
        LLMJSONSchemaResponseFormat(
            type="json_object", name="x", json_schema={"type": "object"}
        )
    with pytest.raises(ValidationError):
        LLMJSONSchemaResponseFormat(name="   ", json_schema={"type": "object"})
    with pytest.raises(ValidationError):
        LLMJSONSchemaResponseFormat(name="x", json_schema={})

    for forbidden in ("extra_body", "guided_json", "grammar", "regex", "tools"):
        assert forbidden not in LLMRequest.model_fields
        assert forbidden not in LLMJSONSchemaResponseFormat.model_fields


# =============================================================================
# 4. Strict parser
# =============================================================================


def test_fenced_json_remains_rejected():
    """Requirement 16: the observed failure is still a failure."""
    with pytest.raises(Exception) as excinfo:
        parse_model_review_response(FENCED_REVIEW_JSON)

    assert "markdown" in str(excinfo.value)


def test_bare_valid_json_remains_accepted():
    """Requirement 17: the observed fix is still accepted, unmodified."""
    review = parse_model_review_response(VALID_REVIEW_JSON)

    assert review.verdict == "approve"
    assert len(review.findings) == 1


def _executable_source(module) -> list[str]:
    """The module's executable tokens, with comments and string literals gone.

    The parser module uses the words "repair", "fence" and "coercion" often — in
    prose, explaining that it performs none of them. Searching the raw text
    would therefore prove nothing, so docstrings and comments are stripped and
    only the tokens that actually run are inspected.
    """
    import io
    import tokenize

    source = inspect.getsource(module)
    return [
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type not in (tokenize.COMMENT, tokenize.STRING)
    ]


def test_no_production_fence_strip_or_repair_helper_was_added():
    """Requirement 18: the parser module gained no repair machinery."""
    tokens = set(_executable_source(review_models_module))

    for forbidden in (
        "strip_fence",
        "extract_json",
        "find_json",
        "repair",
        "normalize",
        "coerce",
        "fallback",
        "removeprefix",
        "removesuffix",
        "partition",
        "splitlines",
        "replace",
        "re",
        "regex",
        "textwrap",
    ):
        assert forbidden not in tokens, forbidden

    # The whole review package still exposes no repair-shaped callable.
    import ai_dev_orchestrator.review as review_package

    for name in dir(review_package):
        lowered = name.lower()
        for forbidden in ("repair", "fence", "extract", "normalize", "salvage"):
            assert forbidden not in lowered, name




def _conforms_to_generated_schema(payload: dict) -> bool:
    """Check a payload against the *expressible* parts of the generated schema.

    Deliberately hand-rolled rather than pulling in a JSON-Schema validator: it
    checks exactly the constraints the generated document actually states — the
    closed key set, the required fields, the scalar types, the two enums, and
    the nullable ``line`` — and nothing else. That is the point of the tests
    below: a payload can satisfy all of it and still be rejected by AIDO.
    """
    schema = build_review_response_format().json_schema
    if set(payload) != set(schema["required"]):
        return False
    if payload["verdict"] not in schema["properties"]["verdict"]["enum"]:
        return False
    if not isinstance(payload["summary"], str):
        return False
    for key in ("residual_risks", "human_notes"):
        if not isinstance(payload[key], list) or not all(
            isinstance(item, str) for item in payload[key]
        ):
            return False
    finding_schema = schema["$defs"]["ReviewFinding"]
    if not isinstance(payload["findings"], list):
        return False
    for finding in payload["findings"]:
        if not isinstance(finding, dict):
            return False
        if not set(finding) <= set(finding_schema["properties"]):
            return False
        if not set(finding_schema["required"]) <= set(finding):
            return False
        if finding["severity"] not in finding_schema["properties"]["severity"]["enum"]:
            return False
        if finding["category"] not in finding_schema["properties"]["category"]["enum"]:
            return False
        if not isinstance(finding["message"], str):
            return False
        if not isinstance(finding["suggested_action"], str):
            return False
        line = finding.get("line")
        if line is not None and not isinstance(line, int):
            return False
    return True


@pytest.mark.parametrize(
    "payload, reason",
    [
        (
            {
                "verdict": "changes_requested",
                "summary": "Something small.",
                "findings": [
                    {
                        "severity": "nit",
                        "category": "maintainability",
                        "line": 2,
                        "message": "A nit.",
                        "suggested_action": "Consider renaming.",
                    }
                ],
                "residual_risks": [],
                "human_notes": [],
            },
            "changes_requested with no blocking finding",
        ),
        (
            {
                "verdict": "approve",
                "summary": "Looks fine.",
                "findings": [
                    {
                        "severity": "blocker",
                        "category": "correctness",
                        "line": 2,
                        "message": "The boundary is inclusive and should not be.",
                        "suggested_action": "Make the boundary exclusive.",
                    }
                ],
                "residual_risks": [],
                "human_notes": [],
            },
            "approve carrying a blocker",
        ),
        (
            {
                "verdict": "needs_human_review",
                "summary": "Unclear.",
                "findings": [
                    {
                        "severity": "minor",
                        "category": "other",
                        "line": 0,
                        "message": "Line zero is not a line.",
                        "suggested_action": "Nothing.",
                    }
                ],
                "residual_risks": [],
                "human_notes": [],
            },
            "line must be a positive line number",
        ),
        (
            {
                "verdict": "needs_human_review",
                "summary": "x" * 4_001,
                "findings": [],
                "residual_risks": [],
                "human_notes": [],
            },
            "summary exceeds the AIDO length cap",
        ),
        (
            {
                "verdict": "needs_human_review",
                "summary": "   ",
                "findings": [],
                "residual_risks": [],
                "human_notes": [],
            },
            "summary is whitespace-only",
        ),
    ],
)
def test_a_schema_valid_reply_violating_an_aido_validator_is_still_rejected(
    payload, reason
):
    """Requirement 19: the server assists generation; AIDO still validates.

    Each payload satisfies everything the **generated JSON Schema** can state —
    the closed key set, the required fields, the types, and both enums — and is
    still rejected, because the rule it breaks is a Pydantic model validator no
    JSON Schema expresses. Structured output is a generation aid, never AIDO's
    final validation authority.
    """
    assert _conforms_to_generated_schema(payload), reason

    with pytest.raises(ReviewValidationError):
        parse_model_review_response(json.dumps(payload))


@windows_only
@git_required
def test_a_structured_run_still_rejects_an_aido_invalid_reply(tmp_path, capsys):
    """The end-to-end half of requirement 19: exit 4, one request, no repair."""
    _, config, artifact = _setup(
        tmp_path, review_block=_structured_vllm_block(structured=True)
    )

    # Schema-valid, AIDO-invalid: an `approve` verdict carrying a blocker.
    content = json.dumps(
        {
            "verdict": "approve",
            "summary": "The boundary is inclusive.",
            "findings": [
                {
                    "severity": "blocker",
                    "category": "correctness",
                    "line": 2,
                    "message": "The comparison is inclusive and should be exclusive.",
                    "suggested_action": "Use a strict comparison.",
                }
            ],
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

    assert code == 4
    # One request: the compact retry was not enabled, and nothing was repaired.
    assert len(seen) == 1
    assert "response_format" in seen[0]
    assert capsys.readouterr().out == ""


# =============================================================================
# 5. Failure behavior — and no structured to unstructured fallback
# =============================================================================


def _status_factory(configs: list, seen: list[dict], status: int):
    def action(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "structured output rejected"})

    return _recording_factory(configs, seen, action=action)


@windows_only
@git_required
@pytest.mark.parametrize("status", [400, 422])
def test_a_structured_output_4xx_is_terminal_with_no_unstructured_retry(
    tmp_path, capsys, status
):
    """Requirement 20: one HTTP request, reviewer-stage failure, no fallback."""
    _, config, artifact = _setup(
        tmp_path,
        # Even with the compact retry ENABLED, a non-retryable 4xx is terminal.
        review_block=_structured_vllm_block(structured=True, compact_retry=True),
    )

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_status_factory(configs, seen, status),
    )

    assert code == 4
    assert len(seen) == 1
    # The one request carried the schema, and NOTHING re-issued it without one.
    assert "response_format" in seen[0]
    assert all("response_format" in body for body in seen)
    assert capsys.readouterr().out == ""


@windows_only
@git_required
def test_a_structured_decoding_5xx_is_terminal_with_no_unstructured_retry(
    tmp_path, capsys
):
    """Requirement 21: transport retries are zero, so a 5xx is one request."""
    _, config, artifact = _setup(
        tmp_path,
        review_block=_structured_vllm_block(structured=True, compact_retry=True),
    )

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_status_factory(configs, seen, 503),
    )

    assert code == 4
    assert len(seen) == 1
    assert "response_format" in seen[0]
    assert configs[0].max_retries == REVIEWER_TRANSPORT_MAX_RETRIES == 0
    assert capsys.readouterr().out == ""


@windows_only
@git_required
def test_an_unusable_structured_reply_gets_no_retry_unless_the_project_enabled_it(
    tmp_path, capsys
):
    """Requirement 22, the disabled half: the accepted opt-in still governs."""
    _, config, artifact = _setup(
        tmp_path,
        review_block=_structured_vllm_block(structured=True, compact_retry=False),
    )

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen, content=FENCED_REVIEW_JSON),
    )

    assert code == 4
    assert len(seen) == 1
    assert capsys.readouterr().out == ""


@windows_only
@git_required
def test_an_unusable_structured_reply_may_use_the_one_compact_retry(tmp_path, capsys):
    """Requirements 22 and 23: same model, same schema, and never a third."""
    _, config, artifact = _setup(
        tmp_path,
        review_block=_structured_vllm_block(structured=True, compact_retry=True),
    )

    replies = iter([FENCED_REVIEW_JSON, VALID_REVIEW_JSON])

    def action(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": VLLM_REVIEWER_MODEL,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": next(replies)},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen, action=action),
    )

    assert code == 0
    # Exactly two: no third request exists, structured or otherwise.
    assert len(seen) == 2
    # Same configured model on both.
    assert seen[0]["model"] == seen[1]["model"] == VLLM_REVIEWER_MODEL
    # Same structured schema on both.
    assert seen[0]["response_format"] == seen[1]["response_format"]

    packet = ReviewPacket.model_validate(_stdout_json(capsys))
    assert packet.reviewer.semantic_requests == 2
    assert packet.reviewer.structured_output_mode == STRUCTURED_OUTPUT_MODE_JSON_SCHEMA
    assert packet.reviewer_supervision.compact_retry_used is True
    assert packet.reviewer_supervision.compact_retry_finding_cap == (
        COMPACT_RETRY_MAX_FINDINGS
    )


@windows_only
@git_required
def test_a_structured_timeout_remains_terminal_at_one_request(tmp_path, capsys):
    """Requirement 24: RS1's terminal-stall rule is provider- and mode-neutral."""
    _, config, artifact = _setup(
        tmp_path,
        review_block=_structured_vllm_block(structured=True, compact_retry=True),
    )

    def action(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated reviewer stall", request=request)

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen, action=action),
    )

    assert code == 4
    assert len(seen) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "REVIEW STALLED" in captured.err
    # A stall never says a compact retry was authorized.
    assert "compact retry authorized" not in captured.err


# =============================================================================
# 6. Packet v4
# =============================================================================


def test_the_current_schema_version_is_v4():
    """Requirement 25."""
    assert REVIEW_PACKET_SCHEMA_VERSION == "review-packet.v4"


def test_v1_v2_and_v3_histories_remain_present_and_truthful():
    """Requirement 26."""
    assert REVIEW_PACKET_SCHEMA_VERSION_V1 == "review-packet.v1"
    assert REVIEW_PACKET_SCHEMA_VERSION_V2 == "review-packet.v2"
    assert REVIEW_PACKET_SCHEMA_VERSION_V3 == "review-packet.v3"

    # v1 and v2 keep exactly the meanings they were given.
    assert "exactly ONE semantic reviewer" in REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS
    assert "LiteLLM-SPECIFIC" in REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS

    history = REVIEW_PACKET_SCHEMA_VERSION_HISTORY
    for version in (
        "review-packet.v1",
        "review-packet.v2",
        "review-packet.v3",
        "review-packet.v4",
    ):
        assert version in history


def test_archived_v1_v2_and_v3_claim_no_structured_output_provenance():
    """Requirement 27: no earlier packet may be read as recording the fact."""
    assert "structured-generation" in REVIEW_PACKET_SCHEMA_VERSION_V3_SEMANTICS
    assert "must NOT be read as proving" in REVIEW_PACKET_SCHEMA_VERSION_V3_SEMANTICS
    assert "structured_output_mode" in REVIEW_PACKET_SCHEMA_VERSION_V3_SEMANTICS

    assert "NO structured-generation provenance" in (
        REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS
    )
    assert "none of them carried that fact" in REVIEW_PACKET_SCHEMA_VERSION_HISTORY
    assert "none about structured generation" in (
        REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS
    )


@windows_only
@git_required
def test_a_structured_vllm_packet_records_the_mode_and_schema_source(tmp_path, capsys):
    """Requirement 28."""
    _, config, artifact = _setup(
        tmp_path, review_block=_structured_vllm_block(structured=True)
    )

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen),
    )

    assert code == 0
    packet = ReviewPacket.model_validate(_stdout_json(capsys))

    assert packet.schema_version == "review-packet.v4"
    assert packet.reviewer.provider == "vllm"
    assert packet.reviewer.model == VLLM_REVIEWER_MODEL
    assert packet.reviewer.endpoint_host == VLLM_HTTPS_HOST
    assert packet.reviewer.structured_output_mode == "json_schema"
    assert packet.reviewer.structured_output_schema_source == (
        "ai_dev_orchestrator.review.models.ModelReviewResult"
    )
    # The boundary is stated in the artifact itself.
    assert (
        "does not replace the strict parser"
        in packet.reviewer.structured_output_note
    )

    # The schema DOCUMENT, the request JSON, the prompt, the raw reply, the base
    # URL and the credential are all absent from the packet.
    rendered = packet.model_dump_json()
    for absent in ("$defs", "additionalProperties", VLLM_HTTPS_BASE_URL, "Authorization"):
        assert absent not in rendered, absent

    # No packet FIELD carries the request body, the schema document, or the
    # provider's separate reasoning channel. ("response_format" and "reasoning"
    # each appear once in prose — the parser-authority note and RS1's
    # observability note — explaining boundaries, not transporting values.)
    def _keys(node) -> set[str]:
        if isinstance(node, dict):
            found = set(node)
            for value in node.values():
                found |= _keys(value)
            return found
        if isinstance(node, list):
            found: set[str] = set()
            for item in node:
                found |= _keys(item)
            return found
        return set()

    all_keys = _keys(packet.model_dump(mode="json"))
    for absent in ("response_format", "json_schema", "reasoning", "schema", "prompt"):
        assert absent not in all_keys, absent


@windows_only
@git_required
def test_an_ordinary_litellm_packet_reports_mode_none(tmp_path, capsys):
    """Requirement 29."""
    _, config, artifact = _setup(tmp_path)

    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _env(),
        client_factory=_mock_client_factory(),
    )

    assert code == 0
    packet = ReviewPacket.model_validate(_stdout_json(capsys))

    assert packet.schema_version == "review-packet.v4"
    assert packet.reviewer.provider == "litellm"
    assert packet.reviewer.structured_output_mode == "none"
    assert packet.reviewer.structured_output_schema_source is None


@windows_only
@git_required
def test_an_unstructured_vllm_packet_reports_mode_none(tmp_path, capsys):
    """Requirement 30: accepted V1 behavior, reported truthfully."""
    _, config, artifact = _setup(
        tmp_path, review_block=_structured_vllm_block(structured=False)
    )

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen),
    )

    assert code == 0
    packet = ReviewPacket.model_validate(_stdout_json(capsys))

    assert packet.reviewer.provider == "vllm"
    assert packet.reviewer.structured_output_mode == "none"
    assert packet.reviewer.structured_output_schema_source is None


def test_the_model_cannot_forge_structured_output_provenance():
    """Requirement 31, the schema half."""
    for field in (
        "structured_output_mode",
        "structured_output_schema_source",
        "structured_output_note",
        "response_format",
        "json_schema",
    ):
        assert field not in ModelReviewResult.model_fields

        forged = json.loads(VALID_REVIEW_JSON)
        forged[field] = "json_schema"
        with pytest.raises(ReviewValidationError):
            parse_model_review_response(json.dumps(forged))


@windows_only
@git_required
def test_a_reply_claiming_structured_output_does_not_change_the_packet(
    tmp_path, capsys
):
    """Requirement 31, end to end: provenance is orchestrator-owned."""
    _, config, artifact = _setup(
        tmp_path, review_block=_structured_vllm_block(structured=False)
    )

    # A well-formed review whose PROSE claims the run was schema-constrained.
    content = json.dumps(
        {
            "verdict": "approve",
            "summary": "structured_output_mode: json_schema - schema enforced.",
            "findings": [],
            "residual_risks": [],
            "human_notes": ["response_format: json_schema"],
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

    # The prose is preserved verbatim inside `review`, and changes nothing.
    assert "json_schema" in packet.review.summary
    assert packet.reviewer.structured_output_mode == "none"
    assert packet.reviewer.structured_output_schema_source is None
    assert "response_format" not in seen[0]


def test_the_two_structured_output_modes_are_a_closed_set():
    assert STRUCTURED_OUTPUT_MODES == ("none", "json_schema")
    assert STRUCTURED_OUTPUT_MODE_NONE == "none"
    assert STRUCTURED_OUTPUT_MODE_JSON_SCHEMA == "json_schema"


# =============================================================================
# 7. Human notice
# =============================================================================


@windows_only
@git_required
@pytest.mark.parametrize(
    "structured, expected", [(True, "json_schema"), (False, "none")]
)
def test_the_pre_call_banner_names_the_mode_but_never_the_schema(
    tmp_path, capsys, structured, expected
):
    """One safe line: the mode token, never the schema body."""
    _, config, artifact = _setup(
        tmp_path, review_block=_structured_vllm_block(structured=structured)
    )

    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=lambda _provider: _vllm_env(),
        client_factory=_recording_factory(configs, seen),
    )

    assert code == 0
    err = capsys.readouterr().err
    assert f"Structured output: {expected}" in err
    for absent in ("$defs", "additionalProperties", VLLM_HTTPS_BASE_URL):
        assert absent not in err


# =============================================================================
# 8. Scope — nothing else was added
# =============================================================================


def test_the_review_command_gained_no_option():
    """Requirement 39: authority stays project-config only."""
    command = next(
        info
        for info in cli.app.registered_commands
        if info.name == "l2-review-approved-file-edit"
    )
    parameters = set(inspect.signature(command.callback).parameters)

    # Exactly the accepted Phase 5F2E option set, unchanged by V2.
    assert parameters == {
        "project_config",
        "approved_diff_proposal",
        "verify_approved_file_edit_flag",
        "real_reviewer",
        "output_format",
    }

    # And no V2-shaped option name reaches the parser through any of them.
    declared = {
        option
        for parameter in inspect.signature(command.callback).parameters.values()
        for option in getattr(parameter.default, "param_decls", None) or ()
    }
    for flag in (
        "--structured-output",
        "--response-format",
        "--json-schema",
        "--guided-json",
        "--schema",
        "--provider",
        "--model",
        "--base-url",
        "--api-key",
        "--endpoint",
    ):
        assert flag not in declared, flag


def test_no_new_command_was_added():
    names = {info.name for info in cli.app.registered_commands}

    assert "l2-review-approved-file-edit" in names
    for forbidden in (
        "l2-review-structured",
        "l2-structured-review",
        "l2-implement",
        "l2-fix",
        "l2-apply-review-findings",
    ):
        assert forbidden not in names


def test_no_reasoning_field_is_captured_anywhere():
    """Requirement 38: `message.reasoning` is not read, stored, or exposed."""
    from ai_dev_orchestrator.llm import client as llm_client_module
    from ai_dev_orchestrator.llm import models as llm_models_module
    from ai_dev_orchestrator.llm.models import LLMResponse
    from ai_dev_orchestrator.review import packet as packet_module
    from ai_dev_orchestrator.review import reviewer as reviewer_module
    from ai_dev_orchestrator.review import supervision as supervision_module

    for module in (
        llm_client_module,
        llm_models_module,
        packet_module,
        reviewer_module,
        supervision_module,
        review_request_module,
        review_models_module,
    ):
        source = inspect.getsource(module)
        assert '"reasoning"' not in source, module.__name__
        assert "reasoning_content" not in source, module.__name__

    assert "reasoning" not in LLMResponse.model_fields
    assert "reasoning" not in ModelReviewResult.model_fields


def test_no_pi_implementer_fixer_failover_or_cancellation_was_added():
    """Requirements 32-37 and 40, as a source-level scope check."""
    from ai_dev_orchestrator.review import reviewer as reviewer_module
    from ai_dev_orchestrator.review import supervision as supervision_module

    for module in (reviewer_module, supervision_module, review_request_module):
        source = inspect.getsource(module)
        for forbidden in (
            "fallback_model",
            "secondary_model",
            "reviewer_chain",
            "failover",
            "def run_fixer",
            "def apply_fix",
            "cancel_request",
            "def cancel",
            "git commit",
            "git push",
            "create_pull_request",
        ):
            assert forbidden not in source, f"{module.__name__}: {forbidden}"

    # The bounded attempt policy is exactly as RS1 accepted it.
    assert MAX_SEMANTIC_REVIEW_ATTEMPTS == 2
    assert REVIEWER_TRANSPORT_MAX_RETRIES == 0


def test_every_reviewer_call_in_this_suite_is_mock_backed():
    """No socket, no real endpoint, and no real credential anywhere here."""
    assert "MockTransport" in inspect.getsource(_recording_factory)
    assert "MockTransport" in inspect.getsource(_mock_client_factory)
    assert ".invalid" in VLLM_HTTPS_BASE_URL
    assert ".invalid" in FAKE_BASE_URL
    assert "not-a-real-secret" in FAKE_API_KEY
    assert VLLM_ENV_BASE_URL == "AIDO_VLLM_BASE_URL"
