"""Phase 5F2E-RS1 tests: bounded reviewer runtime supervision.

Unit-level and fully offline. Nothing here touches a workspace, launches a
process, opens a socket, or contacts a model: every reviewer call goes through
``httpx.MockTransport``, and no API key is needed to run any of it.

The properties under test are the ones that make a *local* reviewer affordable to
supervise:

1. **retry ownership** — the controlled reviewer forces transport
   ``max_retries=0``, so one semantic attempt is exactly one HTTP request, and
   the generic client's behavior is untouched for every other caller;
2. **a hard ceiling of two semantic requests AIDO may issue**, with a narrow,
   named list of conditions that buy the second one;
3. **a timeout is terminal** — the FU1 correction. AIDO stops waiting but cannot
   observe whether the backend released its inference slot, so a second request
   could put two concurrent inference jobs on the same local model. Only a
   **completed but unusable** response buys the compact retry;
4. **the compact retry is a smaller review, not a repair** — same model, a strict
   subset of the already-accepted transmission boundary, no merging, no parser
   repair;
5. **honest accounting** — usage that a provider did not supply is recorded as
   unknown rather than zero, and nothing claims a signal this architecture cannot
   observe, including any bound on backend inference lifetime.
"""

from __future__ import annotations

import json
import threading
import time

import httpx
import pytest
from pydantic import ValidationError

from ai_dev_orchestrator.llm.client import LLMClient
from ai_dev_orchestrator.llm.models import LLMClientConfig, LLMResponse
from ai_dev_orchestrator.models import ControlledReviewConfig, ProjectConfig
from ai_dev_orchestrator.review import (
    COMPACT_RETRY_MAX_FINDINGS,
    MAX_SEMANTIC_REVIEW_ATTEMPTS,
    REVIEWER_TRANSPORT_MAX_RETRIES,
    RETRY_ELIGIBLE_OUTCOMES,
    UNTRUSTED_BEGIN,
    UNTRUSTED_END,
    ReviewerAttemptExhaustedError,
    ReviewSupervisionBlock,
    build_compact_model_review_request,
    build_model_review_request,
    build_review_context,
    build_review_packet,
    build_reviewer_client_config,
    run_one_review_attempt,
    run_supervised_review,
)
from review_fixtures import (
    DIFF_MARKER,
    NON_GOALS_MARKER,
    OPEN_QUESTION_MARKER,
    PROJECT_ID,
    REPO,
    RISK_MARKER,
    SCOPE_MARKER,
    STEP_MARKER,
    SUMMARY_MARKER,
    TARGET,
    TITLE,
    UNCHANGED_MARKER,
    UNRELATED_MARKER,
    VERIFICATION_OUTPUT_MARKER,
    approved_diff_artifact,
    verification_report,
)

REVIEWER_MODEL = "fake-reviewer-model"
FAKE_BASE_URL = "http://fake-litellm.invalid/v1"
FAKE_HOST = "fake-litellm.invalid"
FAKE_API_KEY = "fake-key-not-a-real-secret"

VALID_REVIEW = {
    "verdict": "approve",
    "summary": "The rounding change is small, tested, and in scope.",
    "findings": [],
    "residual_risks": [],
    "human_notes": [],
}


def _finding(index: int) -> dict:
    return {
        "severity": "nit",
        "category": "maintainability",
        "line": index + 1,
        "message": f"Observation number {index}.",
        "suggested_action": "Consider naming the precision.",
    }


def _review_with_findings(count: int) -> str:
    payload = dict(VALID_REVIEW)
    payload["findings"] = [_finding(index) for index in range(count)]
    return json.dumps(payload)


VALID_REVIEW_JSON = json.dumps(VALID_REVIEW)


def _context():
    return build_review_context(
        approved_diff=approved_diff_artifact(),
        verification=verification_report(),
    )


def _env(**overrides) -> dict[str, str]:
    """A literal environment mapping. Never read from the real environment."""
    values = {
        "AIDO_LITELLM_BASE_URL": FAKE_BASE_URL,
        "AIDO_LITELLM_API_KEY": FAKE_API_KEY,
        "AIDO_LITELLM_DEFAULT_MODEL": "fake-env-default-model",
        "AIDO_LITELLM_TIMEOUT_SECONDS": "5",
        "AIDO_LITELLM_MAX_RETRIES": "2",
    }
    for key, value in overrides.items():
        if value is None:
            values.pop(key, None)
        else:
            values[key] = value
    return values


# -- A scripted, request-counting mock transport --------------------------------


def _ok(content: str, *, finish_reason: str = "stop", usage: dict | None = None):
    body: dict = {
        "model": REVIEWER_MODEL,
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
    }
    if usage is not None:
        body["usage"] = usage
    return lambda request: httpx.Response(200, json=body)


def _raises(exc: Exception):
    def action(request: httpx.Request):
        raise exc

    return action


def _status(code: int):
    return lambda request: httpx.Response(code, json={"error": "synthetic"})


def _client(script: list, seen: list[dict]) -> LLMClient:
    """A client whose transport follows ``script`` and records every request.

    An unscripted request is an assertion failure rather than a silent extra
    call — the point of these tests is that no hidden request exists.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        if len(seen) > len(script):
            raise AssertionError(
                f"request {len(seen)} was made but only {len(script)} were "
                "authorized by the script"
            )
        return script[len(seen) - 1](request)

    return LLMClient(
        LLMClientConfig(
            base_url=FAKE_BASE_URL,
            api_key=FAKE_API_KEY,
            default_model=REVIEWER_MODEL,
            timeout_seconds=5.0,
            max_retries=REVIEWER_TRANSPORT_MAX_RETRIES,
        ),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )


def _supervise(script: list, *, compact: bool = True, events: list | None = None):
    seen: list[dict] = []
    clock = iter([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
    outcome = run_supervised_review(
        _context(),
        client=_client(script, seen),
        model=REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
        max_output_tokens=2048,
        compact_retry_on_unusable_output=compact,
        on_event=None if events is None else events.append,
        monotonic=lambda: next(clock),
    )
    return outcome, seen


# =============================================================================
# 1. The project-config block
# =============================================================================


def test_an_existing_5f2e_config_without_the_new_fields_still_loads():
    """Every RS1 field has a safe default, so no existing config breaks."""
    settings = ControlledReviewConfig(enabled=True, model=REVIEWER_MODEL)

    assert settings.attempt_timeout_seconds == 90.0
    # AIDO imposes NO output-token ceiling by default: the field is optional and
    # unset, so no `max_tokens` is sent at all. It is deliberately NOT a number.
    assert settings.max_output_tokens is None
    # Defaults to OFF: an existing Phase 5F2E project keeps exactly one semantic
    # attempt until it explicitly opts into the compact retry.
    assert settings.compact_retry_on_unusable_output is False


def test_a_project_config_yaml_without_the_block_still_loads():
    project = ProjectConfig.model_validate(
        {
            "project_id": "demo_project",
            "display_name": "Demo",
            "repo": {
                "workspace_path": "C:/never/touched",
                "github_repo": "demo/widgets",
                "branch_prefix": "ai/demo",
            },
        }
    )

    assert project.controlled_review.attempt_timeout_seconds == 90.0
    assert project.controlled_review.max_output_tokens is None
    assert project.controlled_review.compact_retry_on_unusable_output is False


def test_the_unaccepted_draft_field_name_is_rejected_rather_than_aliased():
    """FU1 renamed the field; a stale draft config must fail loudly.

    ``compact_retry_on_stall`` would be actively misleading now that a timeout is
    terminal, so it is **not** retained as an alias. ``extra="forbid"`` rejects
    it, and an old draft config cannot silently keep the wrong semantics.
    """
    with pytest.raises(ValidationError):
        ControlledReviewConfig(
            enabled=True, model=REVIEWER_MODEL, compact_retry_on_stall=True
        )


@pytest.mark.parametrize(
    "field",
    [
        "compact_retry_on_stall",
        "retry_on_timeout",
        "compact_retry_on_timeout",
        "retry_enabled",
        "retry_on_stall",
    ],
)
def test_no_timeout_retry_or_generic_retry_field_exists(field):
    assert field not in ControlledReviewConfig.model_fields
    with pytest.raises(ValidationError):
        ControlledReviewConfig(enabled=True, model=REVIEWER_MODEL, **{field: True})


@pytest.mark.parametrize(
    "value", [0, 0.0, -1, -0.5, float("inf"), float("-inf"), float("nan"), 3601]
)
def test_a_nonpositive_or_nonfinite_attempt_timeout_is_rejected(value):
    with pytest.raises(ValidationError):
        ControlledReviewConfig(
            enabled=True, model=REVIEWER_MODEL, attempt_timeout_seconds=value
        )


@pytest.mark.parametrize("value", [0, -1, -2048, True, False])
def test_a_nonpositive_or_boolean_max_output_tokens_is_rejected(value):
    """Zero and negatives are not a way to spell "unlimited"; omit the field.

    Booleans are rejected explicitly because Pydantic would otherwise coerce
    ``true`` into ``1`` and silently impose a ONE-token ceiling.
    """
    with pytest.raises(ValidationError):
        ControlledReviewConfig(
            enabled=True, model=REVIEWER_MODEL, max_output_tokens=value
        )


@pytest.mark.parametrize("value", [1, 512, 2048, 32_001, 131_072, 1_000_000])
def test_any_positive_max_output_tokens_is_accepted_exactly(value):
    """The old artificial ``le=32_000`` ceiling was an AIDO policy artifact only.

    It expressed no provider-independent truth — a backend's real output limit is
    the backend's, and AIDO has no basis to guess it — so it is gone. A configured
    cap is stored exactly as written.
    """
    settings = ControlledReviewConfig(
        enabled=True, model=REVIEWER_MODEL, max_output_tokens=value
    )
    assert settings.max_output_tokens == value


def test_an_explicit_null_max_output_tokens_loads_as_no_cap():
    """YAML ``max_output_tokens: null`` is the same as omitting it."""
    project = ProjectConfig.model_validate(
        {
            "project_id": "demo_project",
            "display_name": "Demo",
            "repo": {
                "workspace_path": "C:/never/touched",
                "github_repo": "demo/widgets",
                "branch_prefix": "ai/demo",
            },
            "controlled_review": {
                "enabled": True,
                "model": REVIEWER_MODEL,
                "max_output_tokens": None,
            },
        }
    )

    assert project.controlled_review.max_output_tokens is None


def test_no_arbitrary_upper_ceiling_survives_in_the_field_schema():
    """Nothing in the field metadata still caps a configured value."""
    field = ControlledReviewConfig.model_fields["max_output_tokens"]
    assert field.default is None
    rendered = repr(field.metadata) + repr(field.annotation)
    for artifact in ("32000", "32_000", "le=", "Le("):
        assert artifact not in rendered


def test_the_block_still_has_no_fallback_model_or_reviewer_list():
    """RS2 (explicit reviewer failover) is documented, not implemented."""
    for extra in (
        {"fallback_model": "some-other-model"},
        {"reviewer_chain": ["a", "b"]},
        {"reviewers": ["a", "b"]},
        {"secondary_model": "some-other-model"},
        {"max_attempts": 5},
        {"max_semantic_attempts": 5},
        {"retry_prompt": "try harder"},
        {"max_retries": 2},
    ):
        with pytest.raises(ValidationError):
            ControlledReviewConfig(enabled=True, model=REVIEWER_MODEL, **extra)


# =============================================================================
# 2. Retry ownership — the load-bearing rule
# =============================================================================


def test_the_reviewer_client_config_forces_transport_retries_to_zero():
    """Even when the environment asks for two, the reviewer gets none."""
    config = build_reviewer_client_config(
        _env(AIDO_LITELLM_MAX_RETRIES="2"),
        model=REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
    )

    assert config.max_retries == 0
    assert REVIEWER_TRANSPORT_MAX_RETRIES == 0


def test_the_reviewer_client_config_uses_the_configured_attempt_timeout():
    """The project's reviewer budget wins over the generic env timeout."""
    config = build_reviewer_client_config(
        _env(AIDO_LITELLM_TIMEOUT_SECONDS="5"),
        model=REVIEWER_MODEL,
        attempt_timeout_seconds=120.0,
    )

    assert config.timeout_seconds == 120.0
    assert config.default_model == REVIEWER_MODEL


def test_the_generic_client_retry_behavior_is_not_globally_changed():
    """The generic path keeps its shipped default and honors the environment.

    RS1 narrows the *reviewer*, not the client. A planner or smoke-test caller
    loading the same environment still gets the retry budget it always did.
    """
    from ai_dev_orchestrator.llm.config import load_llm_client_config_from_env

    assert LLMClientConfig.model_fields["max_retries"].default == 2

    generic = load_llm_client_config_from_env(_env(AIDO_LITELLM_MAX_RETRIES="2"))
    assert generic.max_retries == 2

    reviewer = build_reviewer_client_config(
        _env(AIDO_LITELLM_MAX_RETRIES="2"),
        model=REVIEWER_MODEL,
        attempt_timeout_seconds=90.0,
    )
    assert reviewer.max_retries == 0


def test_a_generic_client_with_retries_really_does_retry():
    """The counterfactual: without RS1's override, one call is three requests.

    This is why hidden transport retries were the wrong owner for a supervised
    local reviewer — a single stalled semantic review would have cost three full
    inference requests.
    """
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        raise httpx.ReadTimeout("synthetic timeout")

    generic = LLMClient(
        LLMClientConfig(
            base_url=FAKE_BASE_URL,
            api_key=FAKE_API_KEY,
            default_model=REVIEWER_MODEL,
            max_retries=2,
        ),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    from ai_dev_orchestrator.llm.client import LLMTimeoutError

    with pytest.raises(LLMTimeoutError):
        generic.chat(build_model_review_request(_context(), model=REVIEWER_MODEL))

    assert len(seen) == 3


# =============================================================================
# 3. The output-token budget
# =============================================================================


def test_the_full_request_carries_the_exact_configured_max_tokens():
    request = build_model_review_request(
        _context(), model=REVIEWER_MODEL, max_output_tokens=1234
    )

    assert request.max_tokens == 1234


def test_the_compact_request_carries_the_exact_configured_max_tokens():
    request = build_compact_model_review_request(
        _context(), model=REVIEWER_MODEL, max_output_tokens=1234
    )

    assert request.max_tokens == 1234


def test_both_requests_serialize_max_tokens_through_the_existing_client():
    """No second transport abstraction: the existing LLMRequest field is used."""
    _, seen = _supervise([_ok("not json"), _ok(VALID_REVIEW_JSON)])

    assert [payload["max_tokens"] for payload in seen] == [2048, 2048]


# =============================================================================
# 4. The compact retry request — same model, strictly less context
# =============================================================================


def test_the_compact_request_uses_the_same_configured_model():
    full = build_model_review_request(_context(), model=REVIEWER_MODEL)
    compact = build_compact_model_review_request(_context(), model=REVIEWER_MODEL)

    assert compact.model == full.model == REVIEWER_MODEL


def test_the_compact_request_is_pure_and_deterministic():
    first = build_compact_model_review_request(_context(), model="m")
    second = build_compact_model_review_request(_context(), model="m")

    assert first.model_dump() == second.model_dump()


def _compact_text() -> str:
    request = build_compact_model_review_request(_context(), model=REVIEWER_MODEL)
    return "\n".join(message.content for message in request.messages)


def test_the_compact_request_keeps_the_diff_scope_non_goals_and_verification():
    text = _compact_text()

    for present in (
        DIFF_MARKER,
        SCOPE_MARKER,
        NON_GOALS_MARKER,
        VERIFICATION_OUTPUT_MARKER,
        TARGET,
    ):
        assert present in text


def test_the_compact_request_drops_the_nonessential_plan_prose():
    text = _compact_text()

    for absent in (STEP_MARKER, RISK_MARKER, OPEN_QUESTION_MARKER, SUMMARY_MARKER):
        assert absent not in text


def test_the_compact_request_sends_no_new_source_or_credential():
    """A strict subset: the retry can never widen the transmission boundary."""
    text = _compact_text()

    for absent in (
        UNCHANGED_MARKER,
        UNRELATED_MARKER,
        FAKE_API_KEY,
        FAKE_BASE_URL,
        "C:\\",
        "I approve this diff proposal for workspace file editing",
    ):
        assert absent not in text


def test_the_compact_request_keeps_free_form_values_inside_the_delimiters():
    request = build_compact_model_review_request(_context(), model=REVIEWER_MODEL)
    user = request.messages[1].content

    for value in (PROJECT_ID, REPO, TITLE, TARGET, DIFF_MARKER, SCOPE_MARKER):
        index = user.index(value)
        before = user[:index]
        # The most recent delimiter before the value must be an opening one.
        assert before.rfind(UNTRUSTED_BEGIN) > before.rfind(UNTRUSTED_END)


def test_the_compact_request_asks_for_at_most_five_findings():
    text = _compact_text()

    assert str(COMPACT_RETRY_MAX_FINDINGS) in text
    assert "needs_human_review" in text
    assert "checklist" in text.lower()


def test_the_compact_system_message_carries_no_project_data():
    system = (
        build_compact_model_review_request(_context(), model="m").messages[0].content
    )

    for marker in (DIFF_MARKER, SCOPE_MARKER, VERIFICATION_OUTPUT_MARKER, TARGET, REPO):
        assert marker not in system


# =============================================================================
# 5. Supervised attempt policy
# =============================================================================


def test_a_valid_first_attempt_makes_exactly_one_request():
    outcome, seen = _supervise([_ok(VALID_REVIEW_JSON)])

    assert len(seen) == 1
    assert outcome.supervision.semantic_attempts_used == 1
    assert outcome.supervision.compact_retry_used is False
    assert outcome.supervision.first_attempt_outcome == "valid_review"
    assert outcome.supervision.final_attempt_outcome == "valid_review"


@pytest.mark.parametrize(
    "verdict_json",
    [
        json.dumps(
            {
                "verdict": "changes_requested",
                "summary": "A real problem.",
                "findings": [
                    {
                        "severity": "major",
                        "category": "correctness",
                        "line": 2,
                        "message": "Non-numeric input raises deep inside.",
                        "suggested_action": "Validate before formatting.",
                    }
                ],
                "residual_risks": [],
                "human_notes": [],
            }
        ),
        json.dumps(
            {
                "verdict": "needs_human_review",
                "summary": "The diff alone is not enough.",
                "findings": [],
                "residual_risks": [],
                "human_notes": [],
            }
        ),
    ],
)
def test_a_valid_non_approve_verdict_never_triggers_a_retry(verdict_json):
    """A verdict AIDO dislikes is still a successful review, not a stall."""
    outcome, seen = _supervise([_ok(verdict_json)])

    assert len(seen) == 1
    assert outcome.supervision.compact_retry_used is False


def test_a_timeout_buys_no_second_request_even_with_the_compact_option_on():
    """The FU1 blocker, at the supervisor level.

    A client timeout is **not** evidence that the backend released its inference
    slot. Issuing a second request could give the same local model two concurrent
    inference jobs — increasing exactly the GPU, concurrency and context pressure
    this phase exists to contain. So the timeout is terminal, and the script
    below authorizes only one request: a second would fail the test loudly.
    """
    events: list = []
    with pytest.raises(ReviewerAttemptExhaustedError) as excinfo:
        _supervise([_raises(httpx.ReadTimeout("synthetic"))], events=events)

    message = str(excinfo.value)
    assert "review_stalled" in message
    assert "1 of at most 2" in message
    # The terminal stall notice, then the terminal unavailable notice — and the
    # attempt count stays at the one request that was actually issued.
    assert [event.kind for event in events] == ["stalled", "unavailable"]
    assert all(event.attempts_used == 1 for event in events)


def test_a_timeout_is_terminal_with_the_compact_option_off_too():
    events: list = []
    with pytest.raises(ReviewerAttemptExhaustedError):
        _supervise([_raises(httpx.ReadTimeout("t"))], compact=False, events=events)

    assert [event.kind for event in events] == ["stalled", "unavailable"]
    assert events[-1].attempts_used == 1


def test_a_timeout_on_the_compact_retry_is_also_terminal():
    """Attempt 1 completed-but-unusable, attempt 2 timed out: no third request."""
    events: list = []
    with pytest.raises(ReviewerAttemptExhaustedError) as excinfo:
        _supervise([_ok("not json"), _raises(httpx.ReadTimeout("t"))], events=events)

    assert "review_stalled" in str(excinfo.value)
    assert [event.kind for event in events] == ["unusable", "stalled", "unavailable"]
    assert events[-1].attempts_used == 2


def test_a_rejected_reply_buys_a_retry_announced_as_unusable_not_stalled():
    events: list = []
    outcome, seen = _supervise(
        [_ok("not json at all"), _ok(VALID_REVIEW_JSON)], events=events
    )

    assert len(seen) == 2
    assert outcome.supervision.first_attempt_outcome == "review_unusable_output"
    # A parse error is never called a stall.
    assert [event.kind for event in events] == ["unusable"]


def test_a_length_finish_reason_is_classified_as_output_budget_exhausted():
    outcome, seen = _supervise(
        [
            _ok('{"verdict": "appro', finish_reason="length"),
            _ok(VALID_REVIEW_JSON),
        ]
    )

    assert len(seen) == 2
    assert (
        outcome.supervision.first_attempt_outcome == "review_output_budget_exhausted"
    )


def test_the_compact_retry_is_a_new_request_not_a_repair_of_the_first():
    """Attempt 1's reply is discarded whole — never quoted into attempt 2."""
    leaky = "SENTINEL_FIRST_ATTEMPT_GARBAGE {{{ not json"
    outcome, seen = _supervise([_ok(leaky), _ok(VALID_REVIEW_JSON)])

    second_text = "\n".join(message["content"] for message in seen[1]["messages"])
    assert "SENTINEL_FIRST_ATTEMPT_GARBAGE" not in second_text
    assert seen[1]["model"] == seen[0]["model"] == REVIEWER_MODEL


def test_a_second_failure_exhausts_the_budget_with_no_third_request():
    events: list = []
    with pytest.raises(ReviewerAttemptExhaustedError) as excinfo:
        _supervise([_ok("not json"), _ok("still not json")], events=events)

    message = str(excinfo.value)
    assert "review_unusable_output" in message
    assert "2 of at most 2" in message
    assert [event.kind for event in events] == ["unusable", "unavailable"]
    assert events[-1].attempts_used == 2


def test_a_compact_retry_with_more_than_five_findings_is_unusable():
    with pytest.raises(ReviewerAttemptExhaustedError) as excinfo:
        _supervise(
            [
                _ok("not json"),
                _ok(_review_with_findings(COMPACT_RETRY_MAX_FINDINGS + 1)),
            ]
        )

    assert "review_retry_finding_cap_exceeded" in str(excinfo.value)


def test_a_compact_retry_at_exactly_five_findings_is_accepted():
    outcome, seen = _supervise(
        [_ok("not json"), _ok(_review_with_findings(COMPACT_RETRY_MAX_FINDINGS))]
    )

    assert len(seen) == 2
    assert len(outcome.review.findings) == COMPACT_RETRY_MAX_FINDINGS


def test_the_finding_cap_applies_only_to_the_retry():
    """A full first attempt keeps the accepted Phase 5F2E bound of 20."""
    outcome, seen = _supervise(
        [_ok(_review_with_findings(COMPACT_RETRY_MAX_FINDINGS + 3))]
    )

    assert len(seen) == 1
    assert len(outcome.review.findings) == COMPACT_RETRY_MAX_FINDINGS + 3


@pytest.mark.parametrize(
    "action, expected",
    [
        (_status(401), "reviewer_auth_failed"),
        (_status(403), "reviewer_auth_failed"),
        (_status(400), "reviewer_response_error"),
        (_status(404), "reviewer_response_error"),
        (_status(429), "reviewer_response_error"),
        (_status(500), "reviewer_response_error"),
        (_status(503), "reviewer_response_error"),
        (_raises(httpx.ConnectError("refused")), "reviewer_transport_failed"),
    ],
)
def test_service_failures_get_no_compact_retry(action, expected):
    """A shorter prompt does not plausibly solve any of these, so none retries.

    Because reviewer transport retries are zero, each of them also costs exactly
    one HTTP request rather than three.
    """
    events: list = []
    with pytest.raises(ReviewerAttemptExhaustedError) as excinfo:
        _supervise([action], events=events)

    assert expected in str(excinfo.value)
    assert [event.kind for event in events] == ["unavailable"]
    assert events[0].attempts_used == 1


def test_a_disabled_compact_retry_stops_after_one_attempt():
    events: list = []
    with pytest.raises(ReviewerAttemptExhaustedError):
        _supervise([_ok("not json")], compact=False, events=events)

    assert [event.kind for event in events] == ["unavailable"]
    assert events[0].attempts_used == 1


def test_the_retry_eligible_set_is_exactly_the_two_completed_response_conditions():
    """Both share the property that a response actually came back to AIDO.

    ``review_stalled`` is deliberately absent: after a timeout the first request
    is an unknown that may still be occupying the backend.
    """
    assert set(RETRY_ELIGIBLE_OUTCOMES) == {
        "review_output_budget_exhausted",
        "review_unusable_output",
    }
    assert "review_stalled" not in RETRY_ELIGIBLE_OUTCOMES
    assert MAX_SEMANTIC_REVIEW_ATTEMPTS == 2


def test_no_event_carries_a_prompt_diff_completion_or_credential():
    events: list = []
    with pytest.raises(ReviewerAttemptExhaustedError):
        _supervise(
            [_ok("SENTINEL_RAW_REPLY not json"), _ok("SENTINEL_RAW_REPLY_2 not json")],
            events=events,
        )

    for event in events:
        rendered = " ".join(
            str(getattr(event, name)) for name in type(event).__slots__
        )
        for forbidden in (
            "SENTINEL_RAW_REPLY",
            DIFF_MARKER,
            FAKE_API_KEY,
            FAKE_BASE_URL,
            "C:\\",
        ):
            assert forbidden not in rendered


# =============================================================================
# 5b. The AIDO-owned wall-clock deadline (Phase 5F2E-RS1-FU2)
# =============================================================================
#
# These are the FU2 regressions, and their whole point is that they must hold
# **without** httpx ever raising a timeout. The blocking client below is a plain
# fake whose `chat()` waits on a `threading.Event`: no transport, no socket, no
# timeout machinery of any kind. If AIDO's own deadline were not doing the work,
# these tests would hang rather than fail.
#
# Every test releases its blocked worker in a `finally`, so pytest never exits
# with a synthetic worker still parked on an Event.


class _BlockingClient:
    """A fake client whose ``chat`` blocks until the test releases it.

    Deliberately not an ``LLMClient`` with a slow transport: an httpx-based fake
    could always be accused of having tripped httpx's own timeout. This one has
    no networking at all, so a stall here can only have come from AIDO's
    supervisor deadline.
    """

    def __init__(self, release: threading.Event, *, response=None):
        self.release = release
        self.response = response
        self.calls = 0
        self.entered = threading.Event()

    def chat(self, request):
        self.calls += 1
        self.entered.set()
        # Bounded so a mistake in the test cannot wedge the suite; the assertions
        # all complete long before this expires.
        self.release.wait(timeout=30)
        if self.response is None:
            raise AssertionError("blocked worker was released without a response")
        return self.response


def _blocking(**kwargs):
    """Build a blocking client plus the event that frees its worker."""
    release = threading.Event()
    return _BlockingClient(release, **kwargs), release


def test_the_supervisor_deadline_ends_the_wait_without_any_httpx_timeout():
    """The FU2 blocker: AIDO's own deadline is what bounds the wait.

    The fake client never raises ``LLMTimeoutError`` — it has no transport to
    raise one. It simply does not return. AIDO must stop waiting anyway.
    """
    client, release = _blocking()
    try:
        started = time.monotonic()
        result = run_one_review_attempt(
            build_model_review_request(_context(), model=REVIEWER_MODEL),
            client=client,
            attempt=1,
            kind="full",
            requested_max_output_tokens=2048,
            attempt_timeout_seconds=0.2,
        )
        waited = time.monotonic() - started

        assert client.entered.wait(timeout=5), "the worker never started the call"
        assert result.review is None
        assert result.record.outcome == "review_stalled"
        # The distinguishing fact: AIDO's deadline won, not a client timeout.
        assert result.record.stall_source == "supervisor_deadline"
        # Exactly one call began, and AIDO did not sit on the blocked worker.
        assert client.calls == 1
        assert waited < 10, waited
    finally:
        release.set()


def test_a_deadline_stall_is_terminal_even_with_the_compact_retry_enabled():
    """No second request is issued while the first may still be in flight."""
    client, release = _blocking()
    events: list = []
    try:
        with pytest.raises(ReviewerAttemptExhaustedError) as excinfo:
            run_supervised_review(
                _context(),
                client=client,
                model=REVIEWER_MODEL,
                attempt_timeout_seconds=0.2,
                max_output_tokens=2048,
                compact_retry_on_unusable_output=True,
                on_event=events.append,
            )

        # One call began; the deadline did not create a second one.
        assert client.calls == 1
        assert "review_stalled" in str(excinfo.value)
        assert "ABANDONED" in str(excinfo.value)
        assert [event.kind for event in events] == ["stalled", "unavailable"]
        assert all(event.attempts_used == 1 for event in events)
    finally:
        release.set()


def test_a_slow_but_active_call_still_ends_at_the_supervisor_deadline():
    """The 'slow progress' discriminator.

    A call that stays *active* past the configured value — never idle long enough
    for any network-inactivity timeout to fire — is exactly the case httpx's
    timeout cannot bound. AIDO's deadline bounds it anyway.
    """
    client, release = _blocking()

    # A second thread keeps the operation demonstrably alive and progressing,
    # standing in for a peer that keeps trickling bytes.
    progress = []
    stop = threading.Event()

    def keep_active():
        while not stop.wait(0.02):
            progress.append(1)

    ticker = threading.Thread(target=keep_active, daemon=True)
    ticker.start()
    try:
        result = run_one_review_attempt(
            build_model_review_request(_context(), model=REVIEWER_MODEL),
            client=client,
            attempt=1,
            kind="full",
            requested_max_output_tokens=2048,
            attempt_timeout_seconds=0.2,
        )

        assert result.record.outcome == "review_stalled"
        assert result.record.stall_source == "supervisor_deadline"
        # The operation really was still progressing when AIDO stopped waiting.
        assert len(progress) > 0
        assert client.calls == 1
    finally:
        stop.set()
        release.set()


def test_a_compact_attempt_that_exceeds_the_deadline_is_terminal():
    """Attempt 1 completed-but-unusable, attempt 2 hit the deadline: no third."""

    class _ThenBlocking:
        """Returns one unusable response, then blocks forever on the retry."""

        def __init__(self, release):
            self.release = release
            self.calls = 0

        def chat(self, request):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    model=REVIEWER_MODEL, content="not json", finish_reason="stop"
                )
            self.release.wait(timeout=30)
            raise AssertionError("the blocked retry worker was released")

    release = threading.Event()
    client = _ThenBlocking(release)
    events: list = []
    try:
        with pytest.raises(ReviewerAttemptExhaustedError) as excinfo:
            run_supervised_review(
                _context(),
                client=client,
                model=REVIEWER_MODEL,
                attempt_timeout_seconds=0.2,
                max_output_tokens=2048,
                compact_retry_on_unusable_output=True,
                on_event=events.append,
            )

        assert client.calls == 2, "exactly two requests, never a third"
        assert "review_stalled" in str(excinfo.value)
        assert [event.kind for event in events] == [
            "unusable",
            "stalled",
            "unavailable",
        ]
        assert events[-1].attempts_used == 2
    finally:
        release.set()


def test_a_client_timeout_before_the_deadline_is_recorded_as_a_client_timeout():
    """Both stall sources exist; only the deadline one abandons a worker."""
    outcome_or_error: list = []
    with pytest.raises(ReviewerAttemptExhaustedError):
        outcome_or_error.append(
            _supervise([_raises(httpx.ReadTimeout("synthetic"))])
        )

    # Re-run at attempt level to inspect the record itself.
    seen: list[dict] = []
    result = run_one_review_attempt(
        build_model_review_request(_context(), model=REVIEWER_MODEL),
        client=_client([_raises(httpx.ReadTimeout("synthetic"))], seen),
        attempt=1,
        kind="full",
        requested_max_output_tokens=2048,
        attempt_timeout_seconds=30.0,
    )

    assert result.record.outcome == "review_stalled"
    assert result.record.stall_source == "client_timeout"
    assert len(seen) == 1


def test_a_response_that_arrives_before_the_deadline_behaves_exactly_as_before():
    """The deadline is invisible on the normal path."""
    outcome, seen = _supervise([_ok(VALID_REVIEW_JSON)])

    assert len(seen) == 1
    assert outcome.review.verdict == "approve"
    assert outcome.supervision.attempts[0].outcome == "valid_review"
    assert outcome.supervision.attempts[0].stall_source is None


def _called_attribute_names(module) -> set[str]:
    """Every ``x.name(...)`` attribute actually *called* in a module's code.

    Parsed with ``ast`` rather than grepped, because this module's own prose
    disclaims several of the things under test — "no executor, no asyncio, no
    join" — and a substring search would flag the disclaimer as the violation.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def test_the_attempt_worker_is_a_daemon_thread_that_is_never_joined():
    """Nothing may keep a CLI alive, and nothing may block on the worker."""
    import ast
    import inspect

    from ai_dev_orchestrator.review import supervision as supervision_module

    tree = ast.parse(inspect.getsource(supervision_module))

    # The worker is created daemon=True.
    daemon_kwargs = [
        keyword
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "daemon"
    ]
    assert daemon_kwargs, "no daemon= argument found"
    assert all(
        isinstance(keyword.value, ast.Constant) and keyword.value.value is True
        for keyword in daemon_kwargs
    )

    called = _called_attribute_names(supervision_module)
    # No join at all — bounded or otherwise — and nothing that kills a thread or
    # closes a socket from the supervisor.
    assert "join" not in called
    assert "close" not in called
    assert "shutdown" not in called
    assert "cancel" not in called

    # No executor, pool, registry, process, or asyncio machinery is imported.
    namespace = set(vars(supervision_module))
    for forbidden in (
        "asyncio",
        "concurrent",
        "futures",
        "ThreadPoolExecutor",
        "multiprocessing",
        "psutil",
        "signal",
    ):
        assert forbidden not in namespace, forbidden


def test_no_backend_cancellation_is_attempted_anywhere_in_the_review_package():
    from ai_dev_orchestrator.review import (
        packet as packet_module,
        reviewer as reviewer_module,
        supervision as supervision_module,
    )

    called: set[str] = set()
    for module in (supervision_module, reviewer_module, packet_module):
        called |= _called_attribute_names(module)

    for forbidden in ("cancel", "abort", "terminate", "kill", "close"):
        assert forbidden not in called, forbidden


# =============================================================================
# 6. Attempt accounting
# =============================================================================


def test_reported_usage_is_recorded_and_missing_usage_stays_unknown():
    outcome, _ = _supervise(
        [
            _ok("not json", usage={"prompt_tokens": 10, "completion_tokens": 2,
                                   "total_tokens": 12}),
            _ok(VALID_REVIEW_JSON),
        ]
    )

    first, second = outcome.supervision.attempts
    assert first.usage_reported is True
    assert first.usage.total_tokens == 12
    # The provider supplied none on the second response: unknown, NOT zero.
    assert second.usage_reported is False
    assert second.usage is None


def test_each_attempt_records_one_transport_request_and_the_requested_cap():
    outcome, _ = _supervise([_ok("not json"), _ok(VALID_REVIEW_JSON)])

    for record in outcome.supervision.attempts:
        assert record.transport_requests == 1
        assert record.requested_max_output_tokens == 2048
    assert [record.kind for record in outcome.supervision.attempts] == [
        "full",
        "compact",
    ]
    assert [record.attempt for record in outcome.supervision.attempts] == [1, 2]


def test_elapsed_time_comes_from_the_injected_monotonic_clock():
    outcome, _ = _supervise([_ok(VALID_REVIEW_JSON)])

    # The stub clock advances 0.0 -> 0.5 across the single attempt.
    assert outcome.supervision.attempts[0].elapsed_seconds == 0.5


def test_the_supervision_block_reports_no_unobservable_signal():
    outcome, _ = _supervise([_ok(VALID_REVIEW_JSON)])
    names = set(outcome.supervision.model_dump())
    names.update(outcome.supervision.attempts[0].model_dump())

    for forbidden in (
        "reasoning",
        "reasoning_tokens",
        "time_to_first_token",
        "time_to_first_finding",
        "tool_calls",
        "files_inspected",
        "tests_executed",
        "similarity",
        "chain_of_thought",
    ):
        assert forbidden not in names


def test_the_supervision_notes_state_their_limits_rather_than_reassure():
    outcome, _ = _supervise([_ok(VALID_REVIEW_JSON)])
    supervision = outcome.supervision

    assert "not" in supervision.timeout_semantics_note.lower()
    assert "backend" in supervision.timeout_semantics_note.lower()
    assert "requested" in supervision.output_cap_note.lower()
    assert "unknown rather than zero" in supervision.output_cap_note
    assert "not observe" in supervision.observability_note.lower()
    assert "max_retries=0" in supervision.retry_ownership_note

    # Backend cancellation is explicitly DISCLAIMED, not asserted. The phrase
    # appears only in its negated form, and the note says the boundary out loud —
    # including the FU1 consequence that a timeout ends the review.
    lowered = supervision.timeout_semantics_note.lower()
    assert "does not observe or claim that the backend stopped inference" in lowered
    assert "outside this phase's observation boundary" in lowered
    assert "not a process-style hard wall-clock kill" in lowered
    assert "terminal" in lowered
    assert "no compact retry is issued after a timeout" in lowered


def test_no_note_claims_gpu_or_backend_time_is_bounded():
    """The FU1 wording correction: RS1 bounds AIDO's issuance and wait only."""
    outcome, _ = _supervise([_ok(VALID_REVIEW_JSON)])
    text = outcome.supervision.model_dump_json().lower()

    for overclaim in (
        "gpu time is bounded",
        "total gpu time is bounded",
        "backend inference is bounded",
        "inference lifetime is bounded",
        "resource envelope is bounded",
        "gpu occupancy is bounded",
    ):
        assert overclaim not in text

    scope = outcome.supervision.supervision_scope_note
    assert "request issuance" in scope.lower()
    assert "wait budget" in scope.lower()


# =============================================================================
# 7. The v2 packet
# =============================================================================


def _packet(script: list, *, compact: bool = True):
    verification = verification_report()
    context = _context()
    outcome, _ = _supervise(script, compact=compact)
    return build_review_packet(
        verification=verification,
        context=context,
        review=outcome.review,
        provider="litellm",
        model=REVIEWER_MODEL,
        endpoint_host=FAKE_HOST,
        endpoint_scheme="http",
        # Phase 5F2E-V2: LiteLLM never carries the generation constraint.
        structured_output_mode="none",
        usage=outcome.usage,
        supervision=outcome.supervision,
    )


def test_the_packet_is_v4_and_preserves_v1_v2_and_v3_meaning_as_history():
    """RS1 supervision is unchanged by V1 and V2; only the version moved."""
    from ai_dev_orchestrator.review import (
        REVIEW_PACKET_SCHEMA_VERSION,
        REVIEW_PACKET_SCHEMA_VERSION_V1,
        REVIEW_PACKET_SCHEMA_VERSION_V2,
        REVIEW_PACKET_SCHEMA_VERSION_V3,
    )

    packet = _packet([_ok(VALID_REVIEW_JSON)])

    assert REVIEW_PACKET_SCHEMA_VERSION == "review-packet.v4"
    assert REVIEW_PACKET_SCHEMA_VERSION_V1 == "review-packet.v1"
    assert REVIEW_PACKET_SCHEMA_VERSION_V2 == "review-packet.v2"
    assert REVIEW_PACKET_SCHEMA_VERSION_V3 == "review-packet.v3"
    assert packet.schema_version == "review-packet.v4"
    assert "review-packet.v1" in packet.superseded_schema_version_note
    assert "review-packet.v2" in packet.superseded_schema_version_note
    assert "review-packet.v3" in packet.superseded_schema_version_note


def test_the_packet_preserves_every_accepted_v1_block():
    packet = _packet([_ok(VALID_REVIEW_JSON)])
    payload = packet.model_dump()

    for block in (
        "project_id",
        "repo",
        "issue_number",
        "title",
        "approved_by",
        "approved_at",
        "target",
        "verification",
        "reviewer",
        "review",
        "transmission_boundary",
        "capability_boundaries",
        "human_decision_required",
        "next_step",
    ):
        assert block in payload
    assert payload["verification"]["outcome"] == "verified"


def test_the_packet_records_a_single_attempt_run():
    packet = _packet([_ok(VALID_REVIEW_JSON)])

    assert packet.reviewer.semantic_requests == 1
    assert packet.reviewer.max_semantic_requests == 2
    assert packet.reviewer.transport_retries_per_semantic_request == 0
    assert packet.reviewer_supervision.semantic_attempts_used == 1
    assert packet.reviewer_supervision.compact_retry_used is False
    assert packet.capability_boundaries.orchestrator_bounded_compact_retry_used is False


def test_the_packet_records_a_compact_retry_run():
    packet = _packet([_ok("not json"), _ok(VALID_REVIEW_JSON)])

    assert packet.reviewer.semantic_requests == 2
    assert packet.reviewer_supervision.semantic_attempts_used == 2
    assert packet.reviewer_supervision.compact_retry_used is True
    assert packet.reviewer_supervision.first_attempt_outcome == "review_unusable_output"
    assert packet.reviewer_supervision.final_attempt_outcome == "valid_review"
    # The honest positive: this really did happen, so it is not a fixed false.
    assert packet.capability_boundaries.orchestrator_bounded_compact_retry_used is True


def test_the_packet_states_the_timeout_and_scope_limits():
    """The two claims FU1 made load-bearing, as fields rather than only prose."""
    packet = _packet([_ok(VALID_REVIEW_JSON)])
    supervision = packet.reviewer_supervision

    assert supervision.timeout_attempt_is_terminal is True
    assert "not observed" in supervision.backend_inference_lifetime_if_stalled
    assert supervision.supervision_scope == (
        "orchestrator_request_issuance_and_wait_budget"
    )
    assert "does NOT prove" in supervision.supervision_scope_note
    assert "NOT bounded by" in supervision.supervision_scope_note
    assert "COMPLETED but unusable" in supervision.compact_retry_policy_note
    assert "never issued after a timeout" in supervision.compact_retry_policy_note


@pytest.mark.parametrize(
    "script, expected_attempts",
    [
        pytest.param([_ok(VALID_REVIEW_JSON)], 1, id="first-attempt-success"),
        pytest.param(
            [_ok("not json"), _ok(VALID_REVIEW_JSON)], 2, id="compact-retry-success"
        ),
    ],
)
def test_a_successful_packet_never_describes_a_stall_or_an_abandoned_worker(
    script, expected_attempts
):
    """The invariant that makes the conditional fields honest.

    A stall is terminal: it raises ``ReviewerAttemptExhaustedError`` and the
    command exits 4 with **no packet**. So every packet that exists — on either
    success path — was produced by a run in which nothing stalled and no worker
    was abandoned. The residual-limit fields must therefore read as conditional
    policy, never as a record of this run.
    """
    packet = _packet(script)
    supervision = packet.reviewer_supervision

    assert supervision.semantic_attempts_used == expected_attempts
    assert len(supervision.attempts) == expected_attempts

    # Nothing stalled, and no attempt has a stall source.
    assert supervision.first_attempt_outcome != "review_stalled"
    assert supervision.final_attempt_outcome == "valid_review"
    for record in supervision.attempts:
        assert record.outcome != "review_stalled"
        assert record.stall_source is None

    # The two residual-limit fields are conditional policy: each opens from an
    # explicit condition and disclaims being a record of this run.
    for value in (
        supervision.backend_inference_lifetime_if_stalled,
        supervision.abandoned_worker_lifetime_if_supervisor_deadline_expires,
    ):
        assert value.startswith("Conditional policy, not a record of this run:")
        assert " IF " in value
        assert "never asserts that it happened" in value


@pytest.mark.parametrize(
    "script",
    [
        pytest.param([_ok(VALID_REVIEW_JSON)], id="first-attempt-success"),
        pytest.param(
            [_ok("not json"), _ok(VALID_REVIEW_JSON)], id="compact-retry-success"
        ),
    ],
)
def test_a_successful_packet_makes_no_bare_abandoned_worker_claim(script):
    """No field name or value may read as "a worker was abandoned here"."""
    packet = _packet(script)
    payload = packet.reviewer_supervision.model_dump()

    # The superseded unconditional names are gone entirely.
    assert "backend_inference_lifetime_after_timeout" not in payload
    assert "abandoned_worker_lifetime_after_deadline" not in payload

    # And no value asserts an abandonment as fact.
    text = packet.reviewer_supervision.model_dump_json()
    for forbidden in (
        "the worker thread is abandoned rather than stopped",
        "a worker was abandoned",
        "the worker was abandoned",
        "an abandoned worker exists",
    ):
        assert forbidden not in text


def test_the_packet_denies_a_third_attempt_a_repair_and_a_fallback_model():
    packet = _packet([_ok("not json"), _ok(VALID_REVIEW_JSON)])
    boundaries = packet.capability_boundaries

    assert boundaries.orchestrator_third_semantic_attempt_made is False
    assert boundaries.orchestrator_parser_repair_attempted is False
    assert boundaries.orchestrator_partial_findings_merged_across_attempts is False
    assert boundaries.orchestrator_fallback_reviewer_model_used is False
    assert packet.reviewer.fallback_model_configured is False
    assert packet.reviewer.fallback_model_used is False
    assert packet.reviewer_supervision.fallback_reviewer_model_available is False
    assert packet.reviewer_supervision.same_model_used_for_every_attempt is True


def test_every_false_capability_boundary_is_still_orchestrator_scoped():
    packet = _packet([_ok(VALID_REVIEW_JSON)])

    for name, value in packet.capability_boundaries.model_dump().items():
        if isinstance(value, bool) and value is False:
            assert name.startswith("orchestrator_"), name


def test_the_packet_carries_no_prompt_completion_or_credential():
    packet = _packet([_ok("not json"), _ok(VALID_REVIEW_JSON)])
    text = packet.model_dump_json()

    for absent in (DIFF_MARKER, "not json", FAKE_API_KEY, FAKE_BASE_URL, "http://"):
        assert absent not in text


def test_the_supervision_block_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ReviewSupervisionBlock.model_validate(
            {"supervision_enabled": True, "fallback_model": "other"}
        )
