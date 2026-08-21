"""Offline tests 1-12: JSONL framing, ingestion, correlation, bounds, deadlines."""

from __future__ import annotations

import json

from ar1.protocol import (
    ProtocolViolation,
    ReasoningDropStats,
    decode_record,
    drop_reasoning,
    ingest_record,
    contains_reasoning,
    split_records,
)
from ar1.supervisor import (
    RUNTIME_DEADLINE_EXPIRED,
    RUNTIME_EVENT_CAP_EXCEEDED,
    RUNTIME_EXITED_EARLY,
    RUNTIME_OUTPUT_CAP_EXCEEDED,
    RUNTIME_PROTOCOL_VIOLATION,
    RUNTIME_SETTLED,
    PiRpcSupervisor,
    RunBounds,
)

import pytest


def _line(obj: dict) -> str:
    return json.dumps(obj) + "\n"


def _supervisor(argv, env, tmp_path, bounds=None) -> PiRpcSupervisor:
    return PiRpcSupervisor(
        argv=argv,
        cwd=str(tmp_path),
        environment=env,
        bounds=bounds
        or RunBounds(
            startup_deadline_seconds=10,
            turn_deadline_seconds=10,
            shutdown_deadline_seconds=2,
            direct_child_reap_grace_seconds=2,
        ),
    )


# -- 1. LF-only framing --------------------------------------------------------


def test_records_split_on_lf_only():
    buffer = b'{"a":1}\n{"b":"x\xe2\x80\xa8y"}\n{"c":3}'
    records, remainder = split_records(buffer)
    assert len(records) == 2
    assert remainder == b'{"c":3}'
    # U+2028 inside a JSON string must NOT be treated as a delimiter.
    assert decode_record(records[1])["b"] == "x y"


def test_only_a_trailing_cr_is_stripped_never_an_embedded_one():
    assert decode_record(b'{"a":1}\r') == {"a": 1}
    # A CR inside a JSON string survives: nothing strips CR globally.
    assert decode_record(b'{"a":"line\\r"}')["a"] == "line\r"
    with pytest.raises(ProtocolViolation):
        decode_record(b"not json\r")


# -- 2/3. fragmentation and multiple records per read --------------------------


def test_fragmented_and_batched_records(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "startup_chunks": [
                '{"type":"agent_st',
                'art"}\n{"type":"turn_start"}\n{"type":"agent_settled"}\n',
            ],
            "chunk_delay_seconds": 0.05,
            "responses": {},
            "ignore_stdin_close": False,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_SETTLED
        assert supervisor.activity.event_type_counts["agent_start"] == 1
        assert supervisor.activity.event_type_counts["turn_start"] == 1
    finally:
        supervisor.shutdown()


# -- 4. malformed JSON is terminal --------------------------------------------


def test_malformed_stdout_record_is_terminal(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "startup_chunks": ['{"type":"agent_start"}\n', "this is not json\n"],
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_PROTOCOL_VIOLATION
        assert supervisor.stdout_state()["protocol_violation"]
    finally:
        supervisor.shutdown()


# -- 5. stderr is separate from stdout ----------------------------------------


def test_stderr_never_enters_the_protocol_stream(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "startup_chunks": ['{"type":"agent_settled"}\n'],
            "stderr_text": "a diagnostic line that is NOT json\n",
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_SETTLED
        supervisor.shutdown()
        stderr = supervisor.stderr_snapshot()
        assert "NOT json" in stderr["text_tail"]
        assert supervisor.stdout_state()["protocol_violation"] is None
    finally:
        pass


# -- 6. command/response id correlation ---------------------------------------


def test_response_correlates_by_rpc_id(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "responses": {
                "get_state": {"success": True, "data": {"model": {"id": "m", "provider": "p"}}}
            },
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        supervisor.send_command({"id": "h2", "type": "get_state"})
        outcome, response = supervisor.await_response("h2", timeout_seconds=10)
        assert outcome == "runtime_response_received"
        assert response is not None and response["id"] == "h2"
        assert response["data"]["model"]["id"] == "m"
    finally:
        supervisor.shutdown()


def test_response_with_a_different_id_does_not_satisfy_the_wait(
    fake_pi, minimal_env, tmp_path
):
    argv = fake_pi(
        {
            "responses": {"get_state": {"success": True, "data": {}}},
            "drop_response_id": True,
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        supervisor.send_command({"id": "h2", "type": "get_state"})
        outcome, response = supervisor.await_response("h2", timeout_seconds=2)
        assert outcome == RUNTIME_DEADLINE_EXPIRED
        assert response is None
    finally:
        supervisor.shutdown()


# -- 7/8. agent_end does not settle; agent_settled does ------------------------


def test_agent_end_with_will_retry_does_not_settle(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "startup_chunks": [
                _line({"type": "agent_start"}),
                _line({"type": "agent_end", "willRetry": True, "messages": []}),
            ],
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=2) == RUNTIME_DEADLINE_EXPIRED
        assert supervisor.activity.settled is False
        assert supervisor.activity.agent_end_count == 1
        assert supervisor.activity.agent_end_will_retry_count == 1
    finally:
        supervisor.shutdown()


def test_agent_settled_settles(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "startup_chunks": [
                _line({"type": "agent_end", "willRetry": False}),
                _line({"type": "agent_settled"}),
            ],
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_SETTLED
        assert supervisor.activity.settled is True
    finally:
        supervisor.shutdown()


# -- 9. reasoning is dropped at ingestion --------------------------------------


def test_reasoning_deltas_are_dropped_at_ingestion(fake_pi, minimal_env, tmp_path):
    secret = "SECRET_CHAIN_OF_THOUGHT_TEXT"
    argv = fake_pi(
        {
            "startup_chunks": [
                _line(
                    {
                        "type": "message_update",
                        "usage": {"input": 5, "output": 1, "totalTokens": 6},
                        "assistantMessageEvent": {
                            "type": "thinking_delta",
                            "delta": secret,
                        },
                    }
                ),
                _line(
                    {
                        "type": "message_end",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "thinking", "thinking": secret},
                                {"type": "text", "text": "visible answer"},
                            ],
                            "reasoning_content": secret,
                        },
                    }
                ),
                _line({"type": "agent_settled"}),
            ],
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_SETTLED
        events = supervisor.sanitized_events()
        serialized = json.dumps(events)
        assert secret not in serialized
        assert not contains_reasoning(events)
        assert supervisor.activity.final_assistant_text == "visible answer"
        # Non-reasoning usage metadata survives.
        assert supervisor.activity.last_usage["totalTokens"] == 6
        stats = supervisor.reasoning_stats
        assert stats.reasoning_delta_records_dropped == 1
        assert stats.reasoning_blocks_dropped == 1
        assert stats.reasoning_keys_dropped >= 1
    finally:
        supervisor.shutdown()


def test_drop_reasoning_is_recursive_and_structural():
    stats = ReasoningDropStats()
    value = {
        "a": {"reasoning": "x", "keep": 1},
        "b": [{"type": "thinking", "thinking": "y"}, {"type": "text", "text": "z"}],
    }
    cleaned = drop_reasoning(value, stats)
    assert cleaned == {"a": {"keep": 1}, "b": [{"type": "text", "text": "z"}]}
    assert not contains_reasoning(cleaned)


def test_ingest_record_keeps_usage_when_dropping_a_thinking_delta():
    stats = ReasoningDropStats()
    cleaned = ingest_record(
        {
            "type": "message_update",
            "usage": {"totalTokens": 11},
            "assistantMessageEvent": {"type": "thinking_start"},
        },
        stats,
    )
    assert cleaned["usage"]["totalTokens"] == 11
    assert cleaned["assistantMessageEvent"] == "reasoning_dropped_at_ingestion"


# -- 10. bounds ----------------------------------------------------------------


def test_event_cap_is_terminal(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "startup_chunks": ["".join(_line({"type": "turn_start"}) for _ in range(50))],
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(
        argv,
        minimal_env,
        tmp_path,
        bounds=RunBounds(
            max_events=5,
            startup_deadline_seconds=10,
            turn_deadline_seconds=10,
            shutdown_deadline_seconds=2,
            direct_child_reap_grace_seconds=2,
        ),
    )
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_EVENT_CAP_EXCEEDED
        assert supervisor.stdout_state()["event_cap_exceeded"] is True
    finally:
        supervisor.shutdown()


def test_stdout_byte_cap_is_terminal(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "startup_chunks": [_line({"type": "turn_start", "pad": "x" * 5000})],
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(
        argv,
        minimal_env,
        tmp_path,
        bounds=RunBounds(
            max_stdout_bytes=64,
            startup_deadline_seconds=10,
            turn_deadline_seconds=10,
            shutdown_deadline_seconds=2,
            direct_child_reap_grace_seconds=2,
        ),
    )
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_OUTPUT_CAP_EXCEEDED
    finally:
        supervisor.shutdown()


def test_stderr_cap_retains_only_the_bound(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "startup_chunks": [_line({"type": "agent_settled"})],
            "stderr_text": "e" * 10000,
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(
        argv,
        minimal_env,
        tmp_path,
        bounds=RunBounds(
            max_stderr_bytes=100,
            startup_deadline_seconds=10,
            turn_deadline_seconds=10,
            shutdown_deadline_seconds=2,
            direct_child_reap_grace_seconds=2,
        ),
    )
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_SETTLED
        supervisor.shutdown()
        stderr = supervisor.stderr_snapshot()
        assert stderr["bytes_retained"] <= 100
        assert stderr["cap_exceeded"] is True
    finally:
        pass


# -- 11/12. startup and turn deadlines -----------------------------------------


def test_startup_deadline_expires_without_a_response(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "responses": {"get_state": {"success": True, "data": {}}},
            "response_delay_seconds": 30,
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        supervisor.send_command({"id": "h2", "type": "get_state"})
        outcome, response = supervisor.await_response("h2", timeout_seconds=1.0)
        assert outcome == RUNTIME_DEADLINE_EXPIRED
        assert response is None
    finally:
        supervisor.shutdown()


def test_turn_deadline_expires_without_agent_settled(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "responses": {"prompt": {"success": True}},
            "prompt_chunks": [_line({"type": "agent_start"})],
            "settle_delay_seconds": 0,
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        supervisor.send_command({"id": "p1", "type": "prompt", "message": "hello"})
        outcome, response = supervisor.await_response("p1", timeout_seconds=10)
        assert outcome == "runtime_response_received"
        assert supervisor.await_settled(timeout_seconds=1.5) == RUNTIME_DEADLINE_EXPIRED
    finally:
        supervisor.shutdown()


# -- 14. early process exit ----------------------------------------------------


def test_early_process_exit_is_reported_as_such(fake_pi, minimal_env, tmp_path):
    argv = fake_pi({"exit_immediately": True, "exit_code": 3})
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_EXITED_EARLY
    finally:
        record = supervisor.shutdown()
        assert record["exit_status_observed"] == 3
