"""Phase 5F2E-RS1 tests: supervised reviewer runtime through the real command.

These exercise ``l2-review-approved-file-edit`` end to end — project config,
synthetic Git repository, real Phase 5F2D verification of a synthetic
verification program, reviewer client construction from an injected environment
mapping, and the bounded attempt policy — and they **count HTTP requests**.

That counting is the point, and there are two load-bearing regressions:

- an environment declaring ``AIDO_LITELLM_MAX_RETRIES=2`` still produces exactly
  **one** HTTP request per semantic attempt;
- a **timeout** produces exactly **one** HTTP request in total, even with the
  compact-retry option enabled. AIDO stops waiting but cannot observe whether the
  backend released its inference slot, so a second request could give the same
  local model two concurrent inference jobs — the opposite of what this phase is
  for. Only a **completed but unusable** response buys the one compact retry.

**Every repository here is a synthetic Git repository created under pytest's own
``tmp_path``, and every verification program is a small synthetic Python script
written under ``tmp_path``.** No real target project is used, read, written, or
executed. **Every reviewer call goes through ``httpx.MockTransport``**: no socket
is opened, no real endpoint is contacted, and no API key is needed.

The synthetic repository/config/artifact harness is imported from the accepted
Phase 5F2E command tests rather than duplicated, so the two suites cannot drift
apart about what a valid setup looks like.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time

import httpx
import pytest

from ai_dev_orchestrator.llm.client import LLMClient
from ai_dev_orchestrator.review import (
    COMPACT_RETRY_MAX_FINDINGS,
    MAX_SEMANTIC_REVIEW_ATTEMPTS,
    REVIEWER_ATTEMPT_THREAD_NAME,
    ReviewPacket,
)
from review_fixtures import DIFF_MARKER, TARGET, UNCHANGED_MARKER, UNRELATED_MARKER
from test_cli_l2_review_approved_file_edit import (
    CHANGES_REQUESTED_JSON,
    FAKE_API_KEY,
    FAKE_BASE_URL,
    NEEDS_HUMAN_JSON,
    REVIEWER_MODEL,
    VALID_REVIEW_JSON,
    _env,
    _run,
    _setup,
    _stdout_json,
    git_required,
    windows_only,
)

# The reviewer block used by these tests, with the RS1 fields spelled out. The
# generic environment below deliberately asks for two transport retries so the
# override is proved rather than assumed.
SUPERVISED_REVIEW_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
  attempt_timeout_seconds: 30
  max_output_tokens: 1536
  compact_retry_on_unusable_output: true
"""

NO_RETRY_REVIEW_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
  attempt_timeout_seconds: 30
  max_output_tokens: 1536
  compact_retry_on_unusable_output: false
"""

# A deliberately tiny AIDO-side deadline, with the compact retry ENABLED, so the
# FU2 tests prove the deadline is terminal rather than merely reachable.
FAST_DEADLINE_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
  attempt_timeout_seconds: 0.3
  max_output_tokens: 1536
  compact_retry_on_unusable_output: true
"""

# The unaccepted RS1 draft name. It must fail to load rather than silently
# retaining the old, now-wrong semantics.
STALE_FIELD_REVIEW_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
  compact_retry_on_stall: true
"""

MALFORMED = "SENTINEL_RAW_FIRST_REPLY — this is not JSON at all"
TRUNCATED = '{"verdict": "appro'


def _retry_env(_provider: str) -> dict[str, str]:
    """An environment that would give the generic client TWO transport retries."""
    return _env(AIDO_LITELLM_MAX_RETRIES="2")


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


def _scripted_factory(script: list, seen: list[dict]):
    """A client factory whose transport follows ``script`` and counts requests.

    An unscripted request fails the test loudly: these suites exist to prove that
    no hidden request is made.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        if len(seen) > len(script):
            raise AssertionError(
                f"request {len(seen)} was made but only {len(script)} were "
                "authorized by the script"
            )
        return script[len(seen) - 1](request)

    def factory(config):
        # The config the command built: this is where the forced max_retries=0
        # actually takes effect, so the count below is an end-to-end fact.
        assert config.max_retries == 0, config.max_retries
        return LLMClient(
            config, transport=httpx.MockTransport(handler), sleep=lambda _: None
        )

    return factory


def _review(tmp_path, script: list, *, block: str = SUPERVISED_REVIEW_BLOCK):
    repo, config, artifact = _setup(tmp_path, review_block=block)
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=_retry_env,
        client_factory=_scripted_factory(script, seen),
    )
    return code, seen, repo


def _sent_text(payload: dict) -> str:
    return "\n".join(message["content"] for message in payload["messages"])


# =============================================================================
# 1. Retry ownership — the load-bearing regression
# =============================================================================


@windows_only
@git_required
def test_a_timeout_costs_exactly_one_request_even_with_compact_retry_enabled(
    tmp_path, capsys
):
    """The FU1 blocker, end to end — and the retry-ownership proof in one test.

    The environment declares ``AIDO_LITELLM_MAX_RETRIES=2`` and the project
    **enables** the compact retry. Without RS1's transport override the
    ``ReadTimeout`` alone would have produced three HTTP requests; without FU1's
    terminal-timeout rule a compact retry would have added at least one more,
    potentially running concurrently with a backend job AIDO cannot see.

    Exactly one request is issued. The script authorizes only one, so a second
    would fail loudly rather than pass silently.
    """
    code, seen, _ = _review(tmp_path, [_raises(httpx.ReadTimeout("synthetic"))])

    assert code == 4
    assert len(seen) == 1, seen

    captured = capsys.readouterr()
    assert captured.out == ""

    err = captured.err
    assert "=== REVIEW STALLED ===" in err
    # Never announced as a retry, and never called unusable.
    assert "compact retry authorized" not in err
    assert "REVIEW UNUSABLE" not in err
    # The human is told the honest reason.
    assert "NOT observed" in err
    assert "NO compact retry is being issued" in err
    assert "REVIEWER UNAVAILABLE FOR THIS REVIEW" in err
    # Attempts used must read as 1 — this run did not use two.
    assert "Attempts used:    1 of at most 2" in err
    assert "review_stalled" in err


@windows_only
@git_required
def test_a_timeout_with_the_compact_retry_disabled_costs_exactly_one_request(
    tmp_path, capsys
):
    """Same terminal classification, with no hidden generic retry either."""
    code, seen, _ = _review(
        tmp_path,
        [_raises(httpx.ReadTimeout("synthetic"))],
        block=NO_RETRY_REVIEW_BLOCK,
    )

    assert code == 4
    assert len(seen) == 1

    err = capsys.readouterr().err
    assert "=== REVIEW STALLED ===" in err
    assert "REVIEWER UNAVAILABLE FOR THIS REVIEW" in err
    assert "review_stalled" in err
    assert "Attempts used:    1 of at most 2" in err


@windows_only
@git_required
def test_a_completed_but_unusable_response_costs_two_requests_not_four_or_six(
    tmp_path, capsys
):
    """The retry-ownership regression, on the path where a retry is allowed.

    The first response **came back**, so the first request is no longer an
    unknown in flight and one smaller request is safe. With
    ``AIDO_LITELLM_MAX_RETRIES=2`` and reviewer retries forced to zero, the whole
    supervised review costs exactly two HTTP requests.
    """
    code, seen, _ = _review(tmp_path, [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)])

    assert code == 0
    assert len(seen) == 2, seen
    assert len(seen) not in (4, 6)

    captured = capsys.readouterr()
    assert "REVIEW UNUSABLE — compact retry authorized" in captured.err
    assert "REVIEW STALLED" not in captured.err

    packet = json.loads(captured.out)
    assert packet["reviewer"]["semantic_requests"] == 2
    assert packet["reviewer"]["transport_retries_per_semantic_request"] == 0
    assert packet["reviewer_supervision"]["semantic_attempts_used"] == 2
    assert packet["reviewer_supervision"]["compact_retry_used"] is True


@windows_only
@git_required
def test_the_stale_draft_config_field_fails_to_load(tmp_path, capsys):
    """``compact_retry_on_stall`` is rejected, never silently honored."""
    code, seen, _ = _review(
        tmp_path, [_ok(VALID_REVIEW_JSON)], block=STALE_FIELD_REVIEW_BLOCK
    )

    assert code == 1
    assert len(seen) == 0
    assert "compact_retry_on_stall" in capsys.readouterr().err


@windows_only
@git_required
def test_the_command_builds_a_reviewer_client_with_zero_transport_retries(tmp_path):
    """Asserted inside the factory, against the config the command produced."""
    seen_configs: list = []

    repo, config, artifact = _setup(tmp_path, review_block=SUPERVISED_REVIEW_BLOCK)

    def factory(client_config):
        seen_configs.append(client_config)
        return LLMClient(
            client_config,
            transport=httpx.MockTransport(_ok(VALID_REVIEW_JSON)),
            sleep=lambda _: None,
        )

    assert _run(config, artifact, read_env=_retry_env, client_factory=factory) == 0

    assert len(seen_configs) == 1
    assert seen_configs[0].max_retries == 0
    # The project's reviewer budget, not the generic AIDO_LITELLM_TIMEOUT_SECONDS.
    assert seen_configs[0].timeout_seconds == 30.0
    assert seen_configs[0].default_model == REVIEWER_MODEL


# =============================================================================
# 2. The attempt matrix
# =============================================================================


@windows_only
@git_required
def test_a_first_attempt_success_makes_exactly_one_request(tmp_path, capsys):
    code, seen, _ = _review(tmp_path, [_ok(VALID_REVIEW_JSON)])

    assert code == 0
    assert len(seen) == 1
    assert _stdout_json(capsys)["reviewer_supervision"]["compact_retry_used"] is False


@windows_only
@git_required
@pytest.mark.parametrize(
    "content, verdict",
    [
        (CHANGES_REQUESTED_JSON, "changes_requested"),
        (NEEDS_HUMAN_JSON, "needs_human_review"),
    ],
)
def test_a_valid_non_approve_verdict_never_retries(tmp_path, capsys, content, verdict):
    """A verdict AIDO dislikes is a successful review, never a reason to retry."""
    code, seen, _ = _review(tmp_path, [_ok(content)])

    assert code == 0
    assert len(seen) == 1
    packet = _stdout_json(capsys)
    assert packet["review"]["verdict"] == verdict
    assert packet["reviewer_supervision"]["compact_retry_used"] is False


@windows_only
@git_required
def test_unusable_then_timeout_costs_two_requests_then_unavailable(tmp_path, capsys):
    """The compact retry may itself time out — and that is terminal too."""
    code, seen, _ = _review(
        tmp_path,
        [_ok(MALFORMED), _raises(httpx.ReadTimeout("b"))],
    )

    assert code == 4
    assert len(seen) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "REVIEW UNUSABLE — compact retry authorized" in captured.err
    assert "=== REVIEW STALLED ===" in captured.err
    assert "REVIEWER UNAVAILABLE FOR THIS REVIEW" in captured.err
    assert (
        f"{MAX_SEMANTIC_REVIEW_ATTEMPTS} semantic requests AIDO may issue"
        in captured.err
    )
    assert "review_stalled" in captured.err
    assert "Attempts used:    2 of at most 2" in captured.err


@windows_only
@git_required
def test_malformed_then_valid_costs_two_requests(tmp_path, capsys):
    code, seen, _ = _review(tmp_path, [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)])

    assert code == 0
    assert len(seen) == 2

    captured = capsys.readouterr()
    # A parse failure is announced truthfully — never as a stall.
    assert "REVIEW UNUSABLE" in captured.err
    assert "REVIEW STALLED" not in captured.err


@windows_only
@git_required
def test_malformed_then_malformed_costs_two_requests_then_unavailable(
    tmp_path, capsys
):
    code, seen, _ = _review(tmp_path, [_ok(MALFORMED), _ok("still not json")])

    assert code == 4
    assert len(seen) == 2
    assert "REVIEWER UNAVAILABLE FOR THIS REVIEW" in capsys.readouterr().err


@windows_only
@git_required
def test_a_length_finish_reason_then_valid_costs_two_requests(tmp_path, capsys):
    code, seen, _ = _review(
        tmp_path,
        [_ok(TRUNCATED, finish_reason="length"), _ok(VALID_REVIEW_JSON)],
    )

    assert code == 0
    assert len(seen) == 2

    captured = capsys.readouterr()
    assert "REVIEW UNUSABLE" in captured.err
    supervision = json.loads(captured.out)["reviewer_supervision"]
    assert supervision["first_attempt_outcome"] == "review_output_budget_exhausted"
    assert supervision["attempts"][0]["finish_reason"] == "length"


@windows_only
@git_required
def test_a_retry_with_more_than_five_findings_is_unusable_with_no_third_request(
    tmp_path, capsys
):
    oversized = json.dumps(
        {
            "verdict": "approve",
            "summary": "Many small observations.",
            "findings": [
                {
                    "severity": "nit",
                    "category": "maintainability",
                    "line": index + 1,
                    "message": f"Observation {index}.",
                    "suggested_action": "Consider a named constant.",
                }
                for index in range(COMPACT_RETRY_MAX_FINDINGS + 1)
            ],
            "residual_risks": [],
            "human_notes": [],
        }
    )
    code, seen, _ = _review(tmp_path, [_ok(MALFORMED), _ok(oversized)])

    assert code == 4
    assert len(seen) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "review_retry_finding_cap_exceeded" in captured.err


@windows_only
@git_required
@pytest.mark.parametrize("code_value", [401, 403])
def test_an_authentication_failure_costs_one_request_and_no_compact_retry(
    tmp_path, capsys, code_value
):
    code, seen, _ = _review(tmp_path, [_status(code_value)])

    assert code == 4
    assert len(seen) == 1

    err = capsys.readouterr().err
    assert "reviewer_auth_failed" in err
    assert "REVIEW STALLED" not in err
    assert "REVIEW UNUSABLE" not in err


@windows_only
@git_required
@pytest.mark.parametrize("code_value", [400, 404])
def test_a_non_retryable_4xx_costs_one_request_and_no_compact_retry(
    tmp_path, capsys, code_value
):
    code, seen, _ = _review(tmp_path, [_status(code_value)])

    assert code == 4
    assert len(seen) == 1
    assert "reviewer_response_error" in capsys.readouterr().err


@windows_only
@git_required
@pytest.mark.parametrize("code_value", [429, 500, 503])
def test_a_429_or_5xx_costs_one_request_with_no_transport_or_semantic_retry(
    tmp_path, capsys, code_value
):
    """Exactly the case the generic client WOULD have retried three times."""
    code, seen, _ = _review(tmp_path, [_status(code_value)])

    assert code == 4
    assert len(seen) == 1
    assert "REVIEWER UNAVAILABLE FOR THIS REVIEW" in capsys.readouterr().err


@windows_only
@git_required
def test_a_connection_error_costs_one_request_and_no_compact_retry(tmp_path, capsys):
    code, seen, _ = _review(
        tmp_path, [_raises(httpx.ConnectError("simulated connection failure"))]
    )

    assert code == 4
    assert len(seen) == 1
    assert "reviewer_transport_failed" in capsys.readouterr().err


# =============================================================================
# 3. What the retry sends
# =============================================================================


@windows_only
@git_required
def test_the_retry_uses_the_same_configured_model(tmp_path, capsys):
    code, seen, _ = _review(
        tmp_path, [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)]
    )

    assert code == 0
    assert [payload["model"] for payload in seen] == [REVIEWER_MODEL, REVIEWER_MODEL]

    packet = _stdout_json(capsys)
    assert packet["reviewer"]["model"] == REVIEWER_MODEL
    assert packet["reviewer"]["fallback_model_used"] is False
    assert (
        packet["reviewer_supervision"]["same_model_used_for_every_attempt"] is True
    )


@windows_only
@git_required
def test_both_attempts_carry_the_exact_configured_max_output_tokens(tmp_path, capsys):
    code, seen, _ = _review(
        tmp_path, [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)]
    )

    assert code == 0
    assert [payload["max_tokens"] for payload in seen] == [1536, 1536]
    assert (
        _stdout_json(capsys)["reviewer_supervision"]["requested_max_output_tokens"]
        == 1536
    )


@windows_only
@git_required
def test_the_retry_sends_no_full_file_unrelated_source_path_or_credential(tmp_path):
    code, seen, repo = _review(
        tmp_path, [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)]
    )

    assert code == 0
    retry_text = _sent_text(seen[1])

    # Present: the one approved diff and the target's repo-relative path.
    assert DIFF_MARKER in retry_text
    assert TARGET in retry_text

    for absent in (
        str(repo),
        str(repo).replace("\\", "/"),
        FAKE_API_KEY,
        FAKE_BASE_URL,
        UNCHANGED_MARKER,
        UNRELATED_MARKER,
        "I approve this diff proposal for workspace file editing",
    ):
        assert absent not in retry_text


@windows_only
@git_required
def test_the_retry_keeps_project_text_inside_the_untrusted_delimiters(tmp_path):
    from ai_dev_orchestrator.review import UNTRUSTED_BEGIN, UNTRUSTED_END

    code, seen, _ = _review(
        tmp_path, [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)]
    )

    assert code == 0
    user = seen[1]["messages"][1]["content"]
    for value in (DIFF_MARKER, TARGET):
        before = user[: user.index(value)]
        assert before.rfind(UNTRUSTED_BEGIN) > before.rfind(UNTRUSTED_END)


@windows_only
@git_required
def test_the_first_attempts_raw_reply_never_reaches_the_retry_stderr_or_packet(
    tmp_path, capsys
):
    """Discarded whole: not repaired, not quoted back, not echoed anywhere."""
    code, seen, _ = _review(tmp_path, [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)])

    assert code == 0
    captured = capsys.readouterr()

    assert "SENTINEL_RAW_FIRST_REPLY" not in _sent_text(seen[1])
    assert "SENTINEL_RAW_FIRST_REPLY" not in captured.err
    assert "SENTINEL_RAW_FIRST_REPLY" not in captured.out


@windows_only
@git_required
def test_a_failed_run_never_echoes_either_raw_reply(tmp_path, capsys):
    code, seen, _ = _review(
        tmp_path, [_ok(MALFORMED), _ok("SENTINEL_RAW_SECOND_REPLY not json")]
    )

    assert code == 4
    err = capsys.readouterr().err
    assert "SENTINEL_RAW_FIRST_REPLY" not in err
    assert "SENTINEL_RAW_SECOND_REPLY" not in err
    assert FAKE_API_KEY not in err
    assert FAKE_BASE_URL not in err
    assert DIFF_MARKER not in err


# =============================================================================
# 4. The v2 packet, end to end
# =============================================================================


@windows_only
@git_required
def test_the_packet_validates_as_v3_and_records_the_attempt_history(
    tmp_path, capsys
):
    code, seen, _ = _review(
        tmp_path,
        [
            _ok(MALFORMED, usage={"prompt_tokens": 800, "completion_tokens": 12,
                                  "total_tokens": 812}),
            _ok(
                VALID_REVIEW_JSON,
                usage={"prompt_tokens": 400, "completion_tokens": 60,
                       "total_tokens": 460},
            ),
        ],
    )

    assert code == 0
    raw = json.loads(capsys.readouterr().out)
    packet = ReviewPacket.model_validate(raw)

    # Phase 5F2E-V1 bumped the version for reviewer provenance only; the RS1
    # attempt history this test asserts is unchanged.
    assert packet.schema_version == "review-packet.v3"
    assert packet.reviewer.provider == "litellm"
    supervision = packet.reviewer_supervision

    assert supervision.supervision_enabled is True
    assert supervision.max_semantic_attempts == 2
    assert supervision.semantic_attempts_used == 2
    assert supervision.transport_retries_per_attempt == 0
    assert supervision.compact_retry_enabled is True
    assert supervision.compact_retry_used is True
    assert supervision.configured_attempt_timeout_seconds == 30.0
    assert supervision.requested_max_output_tokens == 1536
    assert supervision.first_attempt_outcome == "review_unusable_output"
    assert supervision.final_attempt_outcome == "valid_review"

    first, second = supervision.attempts
    assert (first.kind, second.kind) == ("full", "compact")
    assert first.usage.total_tokens == 812
    assert second.usage.total_tokens == 460
    assert packet.reviewer.usage.total_tokens == 460


@windows_only
@git_required
def test_missing_usage_is_recorded_as_unknown_not_zero(tmp_path, capsys):
    code, _, _ = _review(tmp_path, [_ok(VALID_REVIEW_JSON)])

    assert code == 0
    supervision = _stdout_json(capsys)["reviewer_supervision"]
    attempt = supervision["attempts"][0]

    assert attempt["usage_reported"] is False
    assert attempt["usage"] is None
    # Emphatically not an invented zero.
    assert attempt["usage"] != {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


@windows_only
@git_required
@pytest.mark.parametrize(
    "script",
    [
        pytest.param([_ok(VALID_REVIEW_JSON)], id="first-attempt-success"),
        pytest.param(
            [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)], id="compact-retry-success"
        ),
    ],
)
def test_a_printed_packet_never_implies_a_stall_or_an_abandoned_worker(
    tmp_path, capsys, script
):
    """The successful-packet invariant, against the JSON a human actually reads.

    A stall is terminal and exits 4 with no packet at all, so any packet on stdout
    came from a run in which nothing stalled. Its residual-limit fields must read
    as conditional policy — what would be known *if* a stall occurred — never as a
    record of one.
    """
    code, seen, _ = _review(tmp_path, script)

    assert code == 0
    supervision = json.loads(capsys.readouterr().out)["reviewer_supervision"]

    assert supervision["final_attempt_outcome"] == "valid_review"
    for record in supervision["attempts"]:
        assert record["outcome"] != "review_stalled"
        assert record["stall_source"] is None

    for key in (
        "backend_inference_lifetime_if_stalled",
        "abandoned_worker_lifetime_if_supervisor_deadline_expires",
    ):
        value = supervision[key]
        assert value.startswith("Conditional policy, not a record of this run:")
        assert " IF " in value

    # The superseded unconditional names and their fact-shaped wording are gone.
    assert "backend_inference_lifetime_after_timeout" not in supervision
    assert "abandoned_worker_lifetime_after_deadline" not in supervision
    assert (
        "the worker thread is abandoned rather than stopped"
        not in json.dumps(supervision)
    )


@windows_only
@git_required
def test_the_packet_reports_no_unobservable_runtime_progress(tmp_path, capsys):
    code, _, _ = _review(tmp_path, [_ok(VALID_REVIEW_JSON)])

    assert code == 0
    text = capsys.readouterr().out

    for forbidden in (
        "reasoning_tokens",
        "time_to_first_token",
        "time_to_first_finding",
        "tool_calls",
        "files_inspected",
        "tests_executed",
        "chain_of_thought",
        "reasoning_similarity",
    ):
        assert forbidden not in text


@windows_only
@git_required
def test_a_supervised_review_still_changes_no_git_state(tmp_path):
    """Two model attempts, still zero workspace or Git effects from AIDO."""
    repo, config, artifact = _setup(tmp_path, review_block=SUPERVISED_REVIEW_BLOCK)
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=_retry_env,
        client_factory=_scripted_factory(
            [_ok(MALFORMED), _ok(VALID_REVIEW_JSON)], seen
        ),
    )

    assert code == 0
    assert len(seen) == 2

    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    assert head_after == head_before
    assert status == f"M {TARGET}".strip()


# =============================================================================
# 4b. The AIDO-owned deadline, through the real command (Phase 5F2E-RS1-FU2)
# =============================================================================


@windows_only
@git_required
def test_the_command_stops_waiting_at_its_own_deadline_with_no_httpx_timeout(
    tmp_path, capsys
):
    """The FU2 blocker, end to end.

    The injected client never raises ``LLMTimeoutError`` — it has no transport at
    all. It simply does not return. The command must still stop waiting, classify
    the attempt ``review_stalled``, issue no compact retry even though the project
    enabled one, and exit 4 reporting **one** attempt used.

    The blocked worker is released in a ``finally`` so pytest leaves nothing
    parked, and the assertions all run long before that release.
    """
    release = threading.Event()
    entered = threading.Event()
    calls: list[int] = []

    class _BlockingClient:
        def chat(self, request):
            calls.append(1)
            entered.set()
            release.wait(timeout=30)
            raise AssertionError("the blocked worker was released mid-test")

    repo, config, artifact = _setup(tmp_path, review_block=FAST_DEADLINE_BLOCK)
    try:
        started = time.monotonic()
        code = _run(
            config,
            artifact,
            read_env=_retry_env,
            client_factory=lambda client_config: _BlockingClient(),
        )
        waited = time.monotonic() - started

        assert code == 4
        assert entered.wait(timeout=5), "the worker never started the call"
        # Exactly one call began; the deadline created no second request.
        assert len(calls) == 1
        # AIDO did not sit on the blocked worker for its full 30s wait.
        assert waited < 20, waited

        err = capsys.readouterr().err
        assert "=== REVIEW STALLED ===" in err
        assert "compact retry authorized" not in err
        assert "REVIEWER UNAVAILABLE FOR THIS REVIEW" in err
        assert "Attempts used:    1 of at most 2" in err
    finally:
        release.set()


@windows_only
@git_required
def test_the_abandoned_worker_does_not_keep_the_command_alive(tmp_path):
    """The worker is a daemon thread, and the command returns without it."""
    release = threading.Event()
    entered = threading.Event()

    class _BlockingClient:
        def chat(self, request):
            entered.set()
            release.wait(timeout=30)
            raise AssertionError("the blocked worker was released mid-test")

    repo, config, artifact = _setup(tmp_path, review_block=FAST_DEADLINE_BLOCK)
    try:
        assert (
            _run(
                config,
                artifact,
                read_env=_retry_env,
                client_factory=lambda client_config: _BlockingClient(),
            )
            == 4
        )

        assert entered.is_set()
        # The worker is still parked — abandoned, not stopped — and it is a
        # daemon, so it cannot hold a real process open at exit.
        workers = [
            thread
            for thread in threading.enumerate()
            if thread.name == REVIEWER_ATTEMPT_THREAD_NAME
        ]
        assert len(workers) == 1, "exactly one abandoned worker, never more"
        assert workers[0].daemon is True
        assert workers[0].is_alive()
    finally:
        release.set()


# =============================================================================
# 5. Nothing later was smuggled in
# =============================================================================


def test_no_fallback_model_option_or_config_field_exists():
    import inspect

    import typer

    from ai_dev_orchestrator import cli
    from ai_dev_orchestrator.models import ControlledReviewConfig

    declared: set[str] = set()
    for parameter in inspect.signature(
        cli.l2_review_approved_file_edit
    ).parameters.values():
        default = parameter.default
        assert isinstance(default, typer.models.OptionInfo), parameter.name
        declared.update(
            decl for decl in (default.param_decls or ()) if decl.startswith("--")
        )

    # RS1 added no CLI surface at all: still exactly the accepted five options.
    assert declared == {
        "--project-config",
        "--approved-diff-proposal",
        "--verify-approved-file-edit",
        "--real-reviewer",
        "--format",
    }

    fields = set(ControlledReviewConfig.model_fields)
    for forbidden in (
        "fallback_model",
        "reviewer_chain",
        "reviewers",
        "secondary_model",
        "max_attempts",
        "max_retries",
        "retry_prompt",
    ):
        assert forbidden not in fields


def test_no_fixer_or_later_capability_was_added_to_the_review_package():
    import ai_dev_orchestrator.review as review_package

    names = " ".join(dir(review_package)).lower()
    for forbidden in (
        "fixer",
        "commit",
        "push",
        "branch",
        "pull_request",
        "apply_",
        "write_file",
        "subprocess",
        "shell",
        "github",
        "fallback",
    ):
        assert forbidden not in names


def test_the_supervision_module_imports_no_transport_process_or_executor():
    """FU2 added `threading` deliberately — and nothing beyond it.

    One daemon worker per semantic attempt is the smallest mechanism that can
    establish an AIDO-owned wall-clock wait bound. It is **not** a licence for an
    executor, a pool, a process, or asyncio, and none of those is imported.
    """
    import ai_dev_orchestrator.review.supervision as supervision_module

    names = set(vars(supervision_module))
    assert "httpx" not in names
    assert "subprocess" not in names
    assert "os" not in names

    # The one intended addition.
    assert "threading" in names

    # And nothing else that would turn it into a task framework.
    for forbidden in (
        "multiprocessing",
        "asyncio",
        "concurrent",
        "futures",
        "ThreadPoolExecutor",
        "psutil",
        "signal",
        "queue",
    ):
        assert forbidden not in names, forbidden
