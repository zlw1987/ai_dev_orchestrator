"""PROTOCOL and BROKER BINDING.

The wire protocol is exactly two operations, a closed error set, strict LF-framed
JSONL, exact version, no extra fields, unique ids, and frame caps. The binding is
a per-run capability id plus a 256-bit token compared in constant time.

Both are driven here through :class:`ar2.broker.BrokerRequestHandler` directly --
the authority is separable from the pipe, which is exactly why this file opens no
pipe at all.
"""

from __future__ import annotations

import json
import os

import pytest

from ar2.broker import BrokerBinding, BrokerDiagnostics, BrokerRequestHandler
from ar2.capability import RunState
from ar2.fixtures import R1
from ar2.wire import (
    ERR_PROTOCOL_ERROR,
    ERR_UNAUTHORIZED,
    MAX_REQUEST_FRAME_BYTES,
    PROTOCOL_VERSION,
    WireProtocolError,
    error_frame,
    parse_request_frame,
    response_is_host_safe,
)

from conftest import mint_for


@pytest.fixture()
def handler(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    binding = BrokerBinding.mint(sed.capability_id)
    return BrokerRequestHandler(
        sed=sed,
        run_state=RunState(caps=sed.caps),
        binding=binding,
        diagnostics=BrokerDiagnostics(),
    )


def frame(handler_obj, **overrides) -> bytes:
    payload = {
        "v": PROTOCOL_VERSION,
        "id": "r1",
        "cap": handler_obj.binding.capability_id,
        "tok": handler_obj.binding.token,
        "op": "read_file",
        "path_candidate": "calc.py",
    }
    payload.update(overrides)
    for key in [k for k, v in payload.items() if v is None]:
        del payload[key]
    return json.dumps(payload).encode("utf-8")


def decode(response: bytes) -> dict:
    return json.loads(response.decode("utf-8"))


# -- version, shape, fields ----------------------------------------------------


def test_exactly_version_one_is_accepted(handler):
    assert decode(handler.handle_frame(frame(handler)).response)["ok"] is True


@pytest.mark.parametrize("version", [0, 2, "1", 1.0, None, True])
def test_any_other_version_is_a_terminal_protocol_error(handler, version):
    handled = handler.handle_frame(frame(handler, v=version))
    assert handled.terminal is True
    assert decode(handled.response)["error"]["code"] == ERR_PROTOCOL_ERROR


def test_unknown_fields_are_rejected_not_ignored(handler):
    handled = handler.handle_frame(frame(handler, extra_field="surprise"))
    assert handled.terminal is True
    assert decode(handled.response)["error"]["code"] == ERR_PROTOCOL_ERROR
    assert handler.run_state.terminal is True


def test_a_missing_required_field_is_a_protocol_error(handler):
    payload = json.loads(frame(handler).decode("utf-8"))
    del payload["path_candidate"]
    handled = handler.handle_frame(json.dumps(payload).encode("utf-8"))
    assert handled.terminal is True
    assert decode(handled.response)["error"]["code"] == ERR_PROTOCOL_ERROR


def test_a_third_operation_is_refused(handler):
    for operation in ("list_directory", "search_text", "verify", "run", "create_file",
                      "delete_file", "move_file", "stat_file", "shell", "cancel"):
        fresh = BrokerRequestHandler(
            sed=handler.sed,
            run_state=RunState(caps=handler.sed.caps),
            binding=handler.binding,
            diagnostics=BrokerDiagnostics(),
        )
        handled = fresh.handle_frame(frame(fresh, op=operation))
        assert handled.terminal is True
        assert decode(handled.response)["error"]["code"] == ERR_PROTOCOL_ERROR


def test_malformed_json_is_terminal(handler):
    handled = handler.handle_frame(b'{"v":1,"id":')
    assert handled.terminal is True
    assert decode(handled.response)["error"]["code"] == ERR_PROTOCOL_ERROR


def test_a_non_object_frame_is_terminal(handler):
    handled = handler.handle_frame(b'["v",1]')
    assert handled.terminal is True


def test_an_oversized_frame_is_terminal(handler):
    with pytest.raises(WireProtocolError, match="exceeds the cap"):
        parse_request_frame(b"x" * (MAX_REQUEST_FRAME_BYTES + 1))


def test_an_over_long_request_id_is_refused(handler):
    handled = handler.handle_frame(frame(handler, id="i" * 65))
    assert handled.terminal is True


def test_a_repeated_request_id_is_terminal(handler):
    first = handler.handle_frame(frame(handler, id="dup"))
    assert decode(first.response)["ok"] is True
    second = handler.handle_frame(frame(handler, id="dup", path_candidate="test_calc.py"))
    assert second.terminal is True
    assert decode(second.response)["error"]["code"] == ERR_PROTOCOL_ERROR


def test_a_bad_base_sha256_shape_is_a_protocol_error(handler):
    handled = handler.handle_frame(
        frame(
            handler,
            op="edit_file",
            base_sha256="not-a-digest",
            old_text="a",
            new_text="b",
        )
    )
    assert handled.terminal is True
    assert decode(handled.response)["error"]["code"] == ERR_PROTOCOL_ERROR


def test_after_a_terminal_frame_later_requests_are_refused(handler):
    handler.handle_frame(frame(handler, id="bad", extra_field="x"))
    later = handler.handle_frame(frame(handler, id="after"))
    assert later.terminal is True
    assert decode(later.response)["ok"] is False


# -- the closed error set ------------------------------------------------------


def test_error_codes_outside_the_closed_set_cannot_be_constructed():
    with pytest.raises(WireProtocolError, match="closed set"):
        error_frame("r1", "nonexistent_path", "detail")
    with pytest.raises(WireProtocolError, match="closed set"):
        error_frame("r1", "forbidden", "detail")
    with pytest.raises(WireProtocolError, match="closed set"):
        error_frame("r1", "outside_root", "detail")


def test_refusal_reasons_are_uniform_on_the_wire_and_detailed_in_the_record(handler):
    responses = []
    for index, candidate in enumerate(
        ["no_such_file.py", ".git/config", "..\\escape.py", "calc.py:stream"]
    ):
        handled = handler.handle_frame(
            frame(handler, id=f"u{index}", path_candidate=candidate)
        )
        responses.append(decode(handled.response))
    assert {r["error"]["code"] for r in responses} == {"refused"}
    assert {r["error"]["detail"] for r in responses} == {"operation_not_permitted"}
    # AIDO's diagnostic keeps what the wire deliberately does not.
    reasons = handler.diagnostics.refusal_reasons
    assert len(set(reasons)) >= 3


# -- responses never carry host detail or a secret ------------------------------


def test_a_response_never_contains_a_host_path_the_token_or_the_candidate(handler):
    handled = handler.handle_frame(frame(handler))
    text = handled.response.decode("utf-8")
    assert handler.binding.token not in text
    assert handler.binding.capability_id not in text
    assert handler.sed.canonical_root not in text
    assert "C:\\" not in text and "c:\\" not in text.lower()
    assert "path_candidate" not in text


def test_a_refusal_response_does_not_echo_the_candidate(handler):
    handled = handler.handle_frame(
        frame(handler, path_candidate="C:\\dev\\mis_project\\secret.py")
    )
    text = handled.response.decode("utf-8")
    assert "mis_project" not in text
    assert "C:" not in text


def test_response_host_safety_check_rejects_leaks():
    assert response_is_host_safe(b'{"ok":true}\n', forbidden_values=()) is True
    assert response_is_host_safe(b'{"p":"C:\\\\x"}\n', forbidden_values=()) is False
    assert response_is_host_safe(b'{"e":"WinError 2"}\n', forbidden_values=()) is False
    assert response_is_host_safe(b'{"t":"abc"}\n', forbidden_values=("abc",)) is False


def test_no_win32_error_text_errno_or_traceback_reaches_the_wire(handler):
    for candidate in ("NUL", "\\\\?\\C:\\x", "missing.py"):
        handled = handler.handle_frame(
            frame(handler, id=f"e{abs(hash(candidate)) % 1000}", path_candidate=candidate)
        )
        text = handled.response.decode("utf-8").lower()
        for marker in ("winerror", "errno", "traceback", "oserror"):
            assert marker not in text


# -- binding -------------------------------------------------------------------


def test_the_binding_is_per_run_and_256_bits():
    first = BrokerBinding.mint("cap-a")
    second = BrokerBinding.mint("cap-a")
    assert first.token != second.token
    # token_urlsafe(32) is 32 random bytes rendered base64url.
    assert len(first.token) >= 42


def test_a_wrong_token_is_terminal_and_anomalous(handler):
    handled = handler.handle_frame(frame(handler, tok="wrong-token-value"))
    assert handled.terminal is True
    assert decode(handled.response)["error"]["code"] == ERR_UNAUTHORIZED
    assert handler.run_state.terminal is True
    assert "unauthorized" in handler.run_state.terminal_flags
    assert handler.diagnostics.anomalies


def test_a_wrong_capability_id_is_terminal_and_anomalous(handler):
    handled = handler.handle_frame(frame(handler, cap="ar2-cap-deadbeef"))
    assert handled.terminal is True
    assert decode(handled.response)["error"]["code"] == ERR_UNAUTHORIZED
    assert handler.diagnostics.anomalies


def test_binding_comparison_uses_constant_time_comparison():
    """Both halves go through ``hmac.compare_digest``, and neither short-circuits."""
    import ast
    import inspect

    import ar2.broker as broker_module

    module_tree = ast.parse(inspect.getsource(broker_module))
    matches_node = next(
        node
        for node in ast.walk(module_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "matches"
    )
    tree = ast.Module(body=[matches_node], type_ignores=[])
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "compare_digest"
    ]
    assert len(calls) == 2, "both the capability id and the token must be compared"
    assert "hmac" in dir(broker_module)
    # No plain == comparison of the token anywhere in the method.
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Compare)]


def test_no_secret_is_persisted_in_a_normal_diagnostic_record(handler):
    handler.handle_frame(frame(handler))
    serialized = json.dumps(handler.diagnostics.as_dict())
    assert handler.binding.token not in serialized
    assert handler.binding.capability_id not in serialized


def test_the_capability_summary_carries_no_absolute_root(handler):
    serialized = json.dumps(handler.sed.summary())
    assert handler.sed.canonical_root not in serialized
    assert serialized.count("C:\\") == 0
    assert json.loads(serialized)["canonical_root_recorded"] is False


# -- single flight -------------------------------------------------------------


def test_a_reentrant_request_is_terminal(handler):
    handler.run_state.in_flight = True
    handled = handler.handle_frame(frame(handler, id="concurrent"))
    assert handled.terminal is True
    assert decode(handled.response)["error"]["code"] == ERR_PROTOCOL_ERROR


def test_the_in_flight_slot_is_released_after_every_request(handler):
    handler.handle_frame(frame(handler, id="a"))
    assert handler.run_state.in_flight is False
    handler.handle_frame(frame(handler, id="b", path_candidate="nope.py"))
    assert handler.run_state.in_flight is False
