"""CFG1-L16-FU2 -- the bounded runtime capability observation (R-rows).

Every receive-path row drives the REAL ``PiRpcSupervisor`` +
``RecordStreamReader`` + ``ingest_record`` over a REAL pipe to a synthetic peer
under ``tmp_path``. No row substitutes a hand-built dict for the wire.

Rows here: R-01..R-07c, R-09, R-11..R-25, R-30, R-32..R-34, R-38, R-39.
(R-08, R-10, R-31, R-35..R-37, R-40 exercise CFG1 and live in its suite.)
"""

from __future__ import annotations

import ast
import gc
import inspect
import json
import re
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from ar2 import protocol as protocol_module
from ar2 import runtime_probe
from ar2 import supervisor as supervisor_module
from ar2.protocol import REASONING_KEYS, RecordStreamReader, contains_reasoning
from ar2.runtime_probe import (
    POISON_CLASSIFICATION_RAISED,
    POISON_COMMAND_INVALID,
    POISON_DUPLICATE_RESPONSE,
    PROBE_COMMAND_TYPE,
    UNOBSERVED_FACTS,
)
from ar2.supervisor import PROBE_FAILED, PROBE_REFUSED, PiRpcSupervisor, PiSupervisorError, RunBounds

from probe_support import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    FAST_BOUNDS,
    ID_PLACEHOLDER,
    SYNTHETIC_BASE_URL,
    SYNTHETIC_SESSION_FILE,
    OwnerTrackingLock,
    close,
    count_reasoning_keys,
    frame,
    get_state_frame,
    leak_check,
    make_peer,
    make_supervisor,
    respond_config,
    run_in_thread,
    state_data,
)

_EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
_AR1_DIR = _EXPERIMENT_DIR.parent / "pi_external_runtime_ar1"

SENTINEL = "x-sentinel-7f3a91"


def _probe_once(tmp_path, frames, *, name="peer", bounds=FAST_BOUNDS, **peer_extra):
    """Launch, probe once, shut down. Returns (facts_or_exception, supervisor, peer)."""
    peer = make_peer(tmp_path, name, **respond_config(frames, **peer_extra))
    supervisor = make_supervisor(peer, bounds=bounds)
    supervisor.launch()
    try:
        try:
            outcome = supervisor.probe_runtime_capabilities()
        except PiSupervisorError as exc:
            outcome = exc
    finally:
        close(supervisor)
    return outcome, supervisor, peer


def _published_get_state(supervisor):
    return [
        record
        for record in supervisor.sanitized_events()
        if record.get("type") == "response" and record.get("command") == "get_state"
    ]


# ---------------------------------------------------------------------------
# 11.1 minimum rows
# ---------------------------------------------------------------------------


def test_r01_correlated_true_returns_the_four_exact_facts(tmp_path):
    facts, supervisor, peer = _probe_once(tmp_path, [get_state_frame()])
    assert facts == (True, "TRUE", "ABSENT", "medium")
    assert [type(value) for value in facts] == [bool, str, str, str]
    (command,) = peer.captured_commands()
    assert set(command) == {"id", "type"} and command["type"] == "get_state"
    assert re.fullmatch(r"[0-9a-f]{32}", command["id"])
    assert supervisor.commands_sent == ["get_state"]


def test_r02_the_published_record_has_no_reasoning_and_the_facts_no_container(tmp_path):
    facts, supervisor, _peer = _probe_once(tmp_path, [get_state_frame()])
    published = _published_get_state(supervisor)
    assert len(published) == 1
    assert "reasoning" not in published[0]["data"]["model"]
    assert type(facts) is tuple and len(facts) == 4
    for value in facts:
        assert not isinstance(value, (dict, list, set, tuple, bytes, bytearray))


def test_r03_containment_and_drop_statistics_are_exact(tmp_path):
    data = state_data()
    data["model"]["reasoning_content"] = SENTINEL
    data["thinking"] = {"nested": {"reasoningDetails": [SENTINEL]}}
    raw_frame = get_state_frame(data)
    expected_dropped = count_reasoning_keys(json.loads(raw_frame))
    assert expected_dropped == 3
    facts, supervisor, _peer = _probe_once(tmp_path, [raw_frame])
    assert facts == (True, "TRUE", "ABSENT", "medium")
    for record in supervisor.sanitized_events():
        assert contains_reasoning(record) is False
    assert supervisor.reasoning_stats.reasoning_keys_dropped == expected_dropped
    leak_check(supervisor, facts, [SENTINEL])


def test_r04_raw_false_is_false(tmp_path):
    facts, _s, _p = _probe_once(tmp_path, [get_state_frame(state_data(reasoning=False))])
    assert facts == (True, "FALSE", "ABSENT", "medium")


@pytest.mark.parametrize(
    "value",
    ["true", SENTINEL, {"k": SENTINEL}, [SENTINEL], None, 1, 0, 1.0, 0.0],
    ids=["str-true", "str-sentinel", "dict", "list", "null", "one", "zero", "one-float", "zero-float"],
)
def test_r05_every_non_boolean_value_is_other_and_leaks_nothing(tmp_path, value):
    facts, supervisor, _peer = _probe_once(
        tmp_path, [get_state_frame(state_data(reasoning=value))]
    )
    assert facts[1] == "OTHER"
    assert facts[0] is True  # H2 is judged independently of the capability flag
    leak_check(supervisor, facts, [SENTINEL])


def test_r06_unrelated_records_carrying_reasoning_never_feed_the_facts(tmp_path):
    decoy_state = state_data(reasoning=True)
    frames = [
        get_state_frame(decoy_state, response_id="unrelated-before"),
        frame({"type": "response", "id": "other", "command": "prompt", "success": True,
               "data": {"model": {"reasoning": True}}, "reasoning": SENTINEL}),
        get_state_frame(state_data(reasoning=False)),
        get_state_frame(decoy_state, response_id="unrelated-after"),
    ]
    peer = make_peer(
        tmp_path,
        startup_frames=[
            frame({"type": "response", "id": "startup", "command": "get_commands",
                   "success": True, "data": {"model": {"reasoning": True}}}),
        ],
        responses={
            "get_state": frames,
            "get_commands": [
                frame({"type": "response", "id": ID_PLACEHOLDER, "command": "get_commands",
                       "success": True, "data": {"reasoning_content": SENTINEL, "commands": []}})
            ],
        },
    )
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        supervisor.send_command({"id": "caller-h1", "type": "get_commands"})
        assert supervisor.await_response("caller-h1", timeout_seconds=4)[1] is not None
        facts = supervisor.probe_runtime_capabilities()
        time.sleep(0.2)
    finally:
        close(supervisor)
    assert facts == (True, "FALSE", "ABSENT", "medium")
    for record in supervisor.sanitized_events():
        assert contains_reasoning(record) is False
    leak_check(supervisor, facts, [SENTINEL])


def test_r07a_only_a_wrong_id_response_gives_unobserved_facts(tmp_path):
    bounds = RunBounds(startup_deadline_seconds=1.0, shutdown_deadline_seconds=3.0,
                       direct_child_reap_grace_seconds=1.0)
    facts, supervisor, _peer = _probe_once(
        tmp_path, [get_state_frame(response_id="not-the-probe-id")], bounds=bounds
    )
    assert facts == UNOBSERVED_FACTS
    assert supervisor._probe_slot.state == "CONSUMED"


def test_r07b_an_id_from_an_earlier_supervisor_has_no_effect(tmp_path):
    first, earlier, _ = _probe_once(tmp_path, [get_state_frame()], name="earlier")
    assert first == (True, "TRUE", "ABSENT", "medium")
    (earlier_id,) = [key for key in earlier.activity.responses]
    bounds = RunBounds(startup_deadline_seconds=1.0, shutdown_deadline_seconds=3.0,
                       direct_child_reap_grace_seconds=1.0)
    facts, later, _ = _probe_once(
        tmp_path, [get_state_frame(response_id=earlier_id)], name="later", bounds=bounds
    )
    assert facts == UNOBSERVED_FACTS
    assert earlier_id in later.activity.responses  # published, never classified


def test_r07c_a_callers_own_get_state_never_feeds_the_probe(tmp_path, monkeypatch):
    calls = []
    real = protocol_module.classify_correlated_raw_record
    monkeypatch.setattr(
        protocol_module, "classify_correlated_raw_record",
        lambda record: calls.append(1) or real(record),
    )
    peer = make_peer(tmp_path, **respond_config([get_state_frame()]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        supervisor.send_command({"id": "caller-x", "type": "get_state"})
        assert supervisor.await_response("caller-x", timeout_seconds=4)[1] is not None
        assert calls == []  # UNARMED: no matching at all
        facts = supervisor.probe_runtime_capabilities()
    finally:
        close(supervisor)
    assert facts == (True, "TRUE", "ABSENT", "medium")
    assert calls == [1]
    ids = [command["id"] for command in peer.captured_commands()]
    assert ids[0] == "caller-x" and ids[1] != "caller-x"


# ---------------------------------------------------------------------------
# R-09 / R-24 -- the existing drop is unchanged, with and without a probe
# ---------------------------------------------------------------------------

_REASONING_FRAMES = [
    frame({"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": SENTINEL},
           "usage": {"input": 1}}),
    frame({"type": "message_end", "message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": SENTINEL},
        {"type": "text", "text": "visible"},
        {"type": "redacted_thinking", "data": SENTINEL}],
        "reasoning_content": SENTINEL, "thinking_blocks": [SENTINEL]}}),
    frame({"type": "turn_end", "deep": {"a": [{"reasoningDetails": SENTINEL}, {"b": {"thinkingSignature": SENTINEL}}]}}),
    frame({"type": "response", "id": "u1", "command": "get_state", "success": True,
           "data": {"model": {"reasoning": True, "redactedThinking": SENTINEL}}}),
]


def _oracle_ar1_reader(payload: bytes):
    """The PRE-CHANGE reader: AR1's copy is byte-identical to shipped AR2's."""
    import io

    if str(_AR1_DIR) not in sys.path:
        sys.path.insert(0, str(_AR1_DIR))
    from ar1.protocol import ReasoningDropStats as Ar1Stats
    from ar1.protocol import RecordStreamReader as Ar1Reader

    stats = Ar1Stats()
    reader = Ar1Reader(io.BytesIO(payload), max_bytes=10_000_000, max_records=10_000, stats=stats)
    reader.start()
    reader._thread.join(10)
    return reader.all_records(), stats.as_dict()


def _new_reader(payload: bytes):
    import io

    stats = protocol_module.ReasoningDropStats()
    reader = RecordStreamReader(io.BytesIO(payload), max_bytes=10_000_000, max_records=10_000, stats=stats)
    reader.start()
    reader._thread.join(10)
    return reader.all_records(), stats.as_dict()


def test_r24_stream_parity_with_the_pre_change_reader():
    payload = ("\n".join(_REASONING_FRAMES * 3) + "\n").encode("utf-8")
    assert _new_reader(payload) == _oracle_ar1_reader(payload)


def test_r09_reasoning_stripping_is_unchanged_with_and_without_a_probe(tmp_path):
    expected_records, expected_stats = _oracle_ar1_reader(
        ("\n".join(_REASONING_FRAMES) + "\n").encode("utf-8")
    )
    # (1) no probe in flight
    peer = make_peer(tmp_path, "noprobe", startup_frames=_REASONING_FRAMES)
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        deadline = time.monotonic() + 4
        while supervisor._stdout.record_count() < len(_REASONING_FRAMES) and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        close(supervisor)
    assert supervisor.sanitized_events() == expected_records
    assert supervisor.reasoning_stats.as_dict() == expected_stats

    # (2) the same frames while a probe is ARMED on the same stream
    correlated = get_state_frame()
    facts, probed, _ = _probe_once(tmp_path, [*_REASONING_FRAMES, correlated], name="probe")
    assert facts == (True, "TRUE", "ABSENT", "medium")
    events = probed.sanitized_events()
    assert events[: len(_REASONING_FRAMES)] == expected_records
    correlated_dropped = count_reasoning_keys(json.loads(correlated))
    stats = probed.reasoning_stats.as_dict()
    assert stats["reasoning_keys_dropped"] == expected_stats["reasoning_keys_dropped"] + correlated_dropped
    assert stats["reasoning_delta_records_dropped"] == expected_stats["reasoning_delta_records_dropped"]
    assert stats["reasoning_blocks_dropped"] == expected_stats["reasoning_blocks_dropped"]
    leak_check(probed, facts, [SENTINEL])


# ---------------------------------------------------------------------------
# 11.2 same-response and mutation rows
# ---------------------------------------------------------------------------


def _install_publish_hook(monkeypatch, hook):
    real = RecordStreamReader._publish_locked

    def _wrapped(self, record):
        if record.get("type") == "response" and record.get("command") == "get_state":
            hook(self, record)
        return real(self, record)

    monkeypatch.setattr(RecordStreamReader, "_publish_locked", _wrapped)


def test_r11_r12_reduction_happens_before_publication(tmp_path, monkeypatch):
    seen = {}

    def _hook(reader, record):
        slot = reader._probe_slot
        seen["state"] = slot.state
        seen["facts"] = (slot.h2, slot.capability_flag, slot.compat, slot.thinking_level)
        seen["field_types"] = {type(getattr(slot, name)) for name in type(slot).__slots__}
        # Mutate the correlated sanitized record before it is published.
        record["data"]["model"]["id"] = "wrong-model"
        record["data"]["model"]["provider"] = "wrong-provider"
        record["data"]["thinkingLevel"] = "off"
        record["data"]["model"]["compat"] = {"x": 1}
        del record["data"]["model"]

    _install_publish_hook(monkeypatch, _hook)
    facts, supervisor, _peer = _probe_once(tmp_path, [get_state_frame()])
    assert facts == (True, "TRUE", "ABSENT", "medium")
    assert seen["state"] == "RESOLVED"  # R-12
    assert seen["facts"] == (True, "TRUE", "ABSENT", "medium")
    assert seen["field_types"] <= {str, bool, type(None)}
    assert "model" not in _published_get_state(supervisor)[0]["data"]


def test_r13_post_return_mutation_changes_nothing(tmp_path):
    facts, supervisor, _peer = _probe_once(tmp_path, [get_state_frame()])
    snapshot = tuple(facts)
    for record in supervisor.activity.responses.values():
        record["data"]["model"]["id"] = "mutated"
        record["data"]["thinkingLevel"] = "off"
    for record in supervisor.sanitized_events():
        record.clear()
    with pytest.raises(TypeError):
        facts[0] = False  # type: ignore[index]
    with pytest.raises(AttributeError):
        facts.h2 = False  # type: ignore[attr-defined]
    assert facts == snapshot == (True, "TRUE", "ABSENT", "medium")


def _instrument_counts(monkeypatch):
    counts = {"raw": 0, "reduce": 0}
    real_raw = protocol_module.classify_correlated_raw_record
    real_reduce = protocol_module.reduce_sanitized_get_state

    def _raw(record):
        counts["raw"] += 1
        return real_raw(record)

    def _reduce(*args, **kwargs):
        counts["reduce"] += 1
        return real_reduce(*args, **kwargs)

    monkeypatch.setattr(protocol_module, "classify_correlated_raw_record", _raw)
    monkeypatch.setattr(protocol_module, "reduce_sanitized_get_state", _reduce)
    return counts


def _probe_after_n_get_state_frames(supervisor, n):
    """Test-only: hold consumption until the reader has handled ``n`` get_state frames."""

    def _published_enough(reader):
        with reader._condition:
            return len(reader._records) >= n

    supervisor._probe_wait_over = _published_enough  # instance attribute, test-only
    return supervisor.probe_runtime_capabilities()


_GOOD = get_state_frame()
_BAD_H2 = get_state_frame(state_data(provider="someone-else"))


@pytest.mark.parametrize(
    "second",
    [
        _BAD_H2,
        _GOOD,
        frame({"type": "response", "id": ID_PLACEHOLDER, "command": "prompt", "success": True}),
        frame({"type": "response", "id": ID_PLACEHOLDER, "command": "get_state", "success": True, "data": "x"}),
    ],
    ids=["second-fails-h2", "second-identical", "second-other-command", "second-malformed-data"],
)
@pytest.mark.parametrize("first", [_GOOD, _BAD_H2], ids=["first-passes", "first-fails"])
def test_r14_a_duplicate_before_consumption_poisons_without_reclassifying(
    tmp_path, monkeypatch, first, second
):
    counts = _instrument_counts(monkeypatch)
    states = []
    real_match = RecordStreamReader._probe_match

    def _match(self, decoded):
        before = self._probe_slot.state if self._probe_slot is not None else None
        result = real_match(self, decoded)
        states.append((before, self._probe_slot.state if self._probe_slot is not None else None))
        return result

    monkeypatch.setattr(RecordStreamReader, "_probe_match", _match)
    third = _GOOD
    marker = frame({"type": "probe_done", "probe_marker": "done"})
    peer = make_peer(tmp_path, **respond_config([first, second, third, marker]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        with pytest.raises(PiSupervisorError) as raised:
            _probe_after_n_get_state_frames(supervisor, 4)
    finally:
        close(supervisor)
    assert str(raised.value) == PROBE_FAILED
    # frame 1: ARMED -> RESOLVED with one classification and one reduction
    assert states[0] == ("ARMED", "ARMED")  # (a) itself does not resolve
    assert counts == {"raw": 1, "reduce": 1}
    # frame 2: RESOLVED -> POISONED in (a), zero further classification
    assert states[1] == ("RESOLVED", "POISONED")
    # frame 3 (after poisoning): no matching, no change
    assert states[2] == ("POISONED", "POISONED")
    assert supervisor._probe_slot.state == "CONSUMED"
    # every frame was still sanitized and published normally
    assert len(_published_get_state(supervisor)) == 3 - (1 if "prompt" in second else 0)


def test_r14_poison_reason_is_fixed(tmp_path, monkeypatch):
    reasons = []
    real_consume = runtime_probe.ProbeSlot.consume

    def _consume(self):
        reasons.append(self.poison_reason)
        return real_consume(self)

    monkeypatch.setattr(runtime_probe.ProbeSlot, "consume", _consume)
    peer = make_peer(tmp_path, **respond_config([_GOOD, _GOOD, frame({"type": "x", "probe_marker": "done"})]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        with pytest.raises(PiSupervisorError):
            _probe_after_n_get_state_frames(supervisor, 3)
    finally:
        close(supervisor)
    assert reasons == [POISON_DUPLICATE_RESPONSE]


def test_r15_no_matching_while_unarmed_consumed_or_retired(tmp_path, monkeypatch):
    counts = _instrument_counts(monkeypatch)

    # UNARMED, with an id forced into the slot by test-side instrumentation only.
    peer = make_peer(
        tmp_path, "unarmed",
        startup_frames=[{"sleep": 0.6}, get_state_frame(response_id="forced-id")],
    )
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        supervisor._probe_slot.expected_id = "forced-id"
        time.sleep(1.2)
        assert supervisor._probe_slot.state == "UNARMED"
    finally:
        close(supervisor)
    assert counts == {"raw": 0, "reduce": 0}
    assert len(_published_get_state(supervisor)) == 1

    # CONSUMED: a matching frame arriving after the probe returned.
    peer = make_peer(
        tmp_path, "consumed",
        **respond_config([_GOOD, {"sleep": 0.8}, _BAD_H2], respond_async=True),
    )
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        facts = supervisor.probe_runtime_capabilities()
        time.sleep(1.4)
        assert len(_published_get_state(supervisor)) == 2
    finally:
        close(supervisor)
    assert facts == (True, "TRUE", "ABSENT", "medium")
    assert counts == {"raw": 1, "reduce": 1}
    assert supervisor._probe_slot.state == "CONSUMED"

    # RETIRED: retirement first, then the correlated frame arrives.
    peer = make_peer(
        tmp_path, "retired",
        **respond_config([{"sleep": 0.8}, _GOOD], respond_async=True, linger_after_eof=1.5),
    )
    supervisor = make_supervisor(peer)
    supervisor.launch()
    thread, box = run_in_thread(supervisor.probe_runtime_capabilities)
    try:
        deadline = time.monotonic() + 3
        while supervisor._probe_slot.state != "ARMED" and time.monotonic() < deadline:
            time.sleep(0.01)
        record = supervisor.shutdown()
        thread.join(5)
    finally:
        close(supervisor)
    assert isinstance(box.get("error"), PiSupervisorError)
    assert record["exit_status_observed"] is not None
    assert supervisor._probe_slot.state == "RETIRED"
    assert len(_published_get_state(supervisor)) == 1
    assert counts == {"raw": 1, "reduce": 1}  # unchanged from the CONSUMED case


def test_r16_the_returned_facts_and_the_spent_slot_carry_nothing_else(tmp_path):
    data = state_data(reasoning=SENTINEL)
    facts, supervisor, _peer = _probe_once(tmp_path, [get_state_frame(data)])
    assert len(facts) == 4
    assert [type(value) for value in facts] == [bool, str, str, str]
    (probe_id,) = list(supervisor.activity.responses)
    slot = supervisor._probe_slot
    for rendered in (repr(facts), repr([getattr(slot, name) for name in type(slot).__slots__])):
        for forbidden in (probe_id, "data", "model", SYNTHETIC_BASE_URL, SYNTHETIC_SESSION_FILE,
                          "baseUrl", SENTINEL):
            assert forbidden not in rendered, forbidden


def test_r17_the_slot_holds_only_scalars_and_references_no_container(tmp_path, monkeypatch):
    during = {}

    def _hook(reader, record):
        slot = reader._probe_slot
        during["types"] = {type(getattr(slot, name)) for name in type(slot).__slots__}
        during["referents"] = [type(ref) for ref in gc.get_referents(slot)]

    _install_publish_hook(monkeypatch, _hook)
    _facts, supervisor, _peer = _probe_once(tmp_path, [get_state_frame()])
    slot = supervisor._probe_slot
    after_types = {type(getattr(slot, name)) for name in type(slot).__slots__}
    after_referents = [type(ref) for ref in gc.get_referents(slot)]
    for types in (during["types"], after_types):
        assert types <= {str, bool, type(None)}
    for referents in (during["referents"], after_referents):
        assert not any(issubclass(kind, (dict, list, set, tuple)) for kind in referents)
    assert not hasattr(slot, "__dict__")


# ---------------------------------------------------------------------------
# 11.4 correlation and malformed-input rows
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_frame",
    [
        get_state_frame(include_command=False),
        get_state_frame(command="get_commands"),
        get_state_frame(command=5),
        get_state_frame(command=["get_state"]),
    ],
    ids=["missing", "get_commands", "int", "list"],
)
def test_r18_a_correlated_frame_with_a_bad_command_poisons(tmp_path, monkeypatch, bad_frame):
    reasons = []
    real_consume = runtime_probe.ProbeSlot.consume
    monkeypatch.setattr(
        runtime_probe.ProbeSlot, "consume",
        lambda self: reasons.append(self.poison_reason) or real_consume(self),
    )
    outcome, _supervisor, _peer = _probe_once(tmp_path, [bad_frame])
    assert isinstance(outcome, PiSupervisorError)
    assert str(outcome) == PROBE_FAILED
    assert reasons == [POISON_COMMAND_INVALID]


@pytest.mark.parametrize(
    "success_kwargs",
    [{"success": False}, {"include_success": False}, {"success": 1}, {"success": "true"}],
    ids=["false", "missing", "one", "str-true"],
)
def test_r19_success_not_exactly_true_is_unobserved(tmp_path, success_kwargs):
    facts, _s, _p = _probe_once(tmp_path, [get_state_frame(**success_kwargs)])
    assert facts == UNOBSERVED_FACTS


@pytest.mark.parametrize(
    "data, expected",
    [
        ("not-a-dict", UNOBSERVED_FACTS),
        ([1, 2], UNOBSERVED_FACTS),
        (None, None),  # data key present but null
        ({"model": "not-a-dict", "thinkingLevel": "medium"}, (False, "OTHER", "OTHER", "medium")),
        ({"model": [1], "thinkingLevel": "bogus"}, (False, "OTHER", "OTHER", "OTHER")),
        (state_data(include_reasoning=False), (True, "OTHER", "ABSENT", "medium")),
        (state_data(include_thinking=False), (True, "TRUE", "ABSENT", "NOT_OBSERVED")),
    ],
    ids=["data-str", "data-list", "data-null", "model-str", "model-list", "no-reasoning-key", "no-thinking"],
)
def test_r20_malformed_state_shapes_follow_the_sec8_table(tmp_path, data, expected):
    if data is None:
        raw = frame({"type": "response", "id": ID_PLACEHOLDER, "command": "get_state",
                     "success": True, "data": None})
        expected = UNOBSERVED_FACTS
    else:
        raw = get_state_frame(data)
    facts, _s, _p = _probe_once(tmp_path, [raw])
    assert facts == expected


def test_r20_compat_shapes_are_the_frozen_mapping(tmp_path):
    cases = [
        ({"supportsDeveloperRole": False}, "DEVELOPER_ROLE_FALSE_ONLY"),
        ({"supportsReasoningEffort": False}, "REASONING_EFFORT_FALSE_ONLY"),
        ({"supportsDeveloperRole": False, "supportsReasoningEffort": False}, "BOTH_FALSE_ONLY"),
        ({}, "OTHER"),
        ({"supportsDeveloperRole": 0}, "OTHER"),
        ({"supportsDeveloperRole": False, "x": False}, "OTHER"),
        ("str", "OTHER"),
        (None, "OTHER"),
    ]
    frames = [get_state_frame(state_data(compat=compat, include_compat=True)) for compat, _ in cases]
    for index, (raw, (_compat, expected)) in enumerate(zip(frames, cases)):
        facts, _s, _p = _probe_once(tmp_path, [raw], name=f"compat{index}")
        assert facts == (True, "TRUE", expected, "medium"), expected


def test_r21_arming_precedes_the_write(tmp_path, monkeypatch):
    observed = []
    real_write = supervisor_module._write_frame

    def _write(stream, payload):
        observed.append(supervisor._probe_slot.state)
        return real_write(stream, payload)

    monkeypatch.setattr(supervisor_module, "_write_frame", _write)
    peer = make_peer(tmp_path, **respond_config([get_state_frame()]))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        assert supervisor.probe_runtime_capabilities()[0] is True
    finally:
        close(supervisor)
    assert observed == ["ARMED"]


class _Hostile:
    """A raw value whose every dunder records and raises (R-22)."""

    calls: list = []

    def _record(name):  # noqa: N805 - class-body helper
        def _dunder(self, *args, **kwargs):
            _Hostile.calls.append(name)
            raise RuntimeError(SENTINEL)

        return _dunder

    __eq__ = _record("__eq__")
    __ne__ = _record("__ne__")
    __bool__ = _record("__bool__")
    __repr__ = _record("__repr__")
    __str__ = _record("__str__")
    __hash__ = _record("__hash__")
    __len__ = _record("__len__")
    __format__ = _record("__format__")
    __iter__ = _record("__iter__")
    __getitem__ = _record("__getitem__")
    __copy__ = _record("__copy__")
    __deepcopy__ = _record("__deepcopy__")


def test_r22_no_dunder_on_the_raw_reasoning_value_is_ever_invoked(tmp_path, monkeypatch):
    _Hostile.calls = []
    real_decode = protocol_module.decode_record

    def _decode(raw):
        record = real_decode(raw)
        data = record.get("data")
        if record.get("command") == "get_state" and isinstance(data, dict):
            data["model"]["reasoning"] = _Hostile()
        return record

    monkeypatch.setattr(protocol_module, "decode_record", _decode)
    facts, supervisor, _peer = _probe_once(tmp_path, [get_state_frame()])
    assert _Hostile.calls == []
    assert facts == (True, "OTHER", "ABSENT", "medium")
    assert supervisor._stdout.read_error is None
    leak_check(supervisor, facts, [SENTINEL])


@pytest.mark.parametrize("target", ["classify_correlated_raw_record", "reduce_sanitized_get_state", "is_correlated_response"])
def test_r22_forced_classifier_exceptions_poison_with_a_fixed_reason(tmp_path, monkeypatch, target):
    def _raise(*args, **kwargs):
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(protocol_module, target, _raise)
    reasons = []
    real_consume = runtime_probe.ProbeSlot.consume
    monkeypatch.setattr(
        runtime_probe.ProbeSlot, "consume",
        lambda self: reasons.append(self.poison_reason) or real_consume(self),
    )
    outcome, supervisor, _peer = _probe_once(tmp_path, [get_state_frame()])
    assert isinstance(outcome, PiSupervisorError)
    assert SENTINEL not in str(outcome) and str(outcome) == PROBE_FAILED
    assert outcome.__cause__ is None
    assert reasons == [POISON_CLASSIFICATION_RAISED]
    assert supervisor._stdout.read_error is None
    assert len(_published_get_state(supervisor)) == 1  # still published normally
    leak_check(supervisor, (), [SENTINEL])


@pytest.mark.parametrize("violation", ["protocol", "byte_cap", "record_cap"])
def test_r23_stream_terminal_conditions_before_resolution_are_unobserved(
    tmp_path, monkeypatch, violation
):
    counts = _instrument_counts(monkeypatch)
    bounds = FAST_BOUNDS
    frames = [get_state_frame()]
    if violation == "protocol":
        frames = ["this is not json", *frames]
    elif violation == "byte_cap":
        bounds = RunBounds(startup_deadline_seconds=2.0, shutdown_deadline_seconds=3.0,
                           direct_child_reap_grace_seconds=1.0, max_stdout_bytes=4000)
        frames = [frame({"type": "filler", "pad": "x" * 5000}), *frames]
    else:
        bounds = RunBounds(startup_deadline_seconds=2.0, shutdown_deadline_seconds=3.0,
                           direct_child_reap_grace_seconds=1.0, max_events=2)
        frames = [frame({"type": "a"}), frame({"type": "b"}), *frames]
    facts, _supervisor, _peer = _probe_once(tmp_path, frames, bounds=bounds)
    assert facts == UNOBSERVED_FACTS
    assert counts == {"raw": 0, "reduce": 0}


def test_r25_mismatching_expectations_fail_h2_only(tmp_path):
    peer = make_peer(tmp_path, **respond_config([get_state_frame()]))
    supervisor = make_supervisor(peer, provider="another-provider")
    supervisor.launch()
    try:
        facts = supervisor.probe_runtime_capabilities()
    finally:
        close(supervisor)
    assert facts == (False, "TRUE", "ABSENT", "medium")


# ---------------------------------------------------------------------------
# 11.5 no-generic-capability rows
# ---------------------------------------------------------------------------

_FORBIDDEN_PARAMETER_FRAGMENTS = (
    "path", "key", "command_type", "extractor", "predicate", "classifier", "hook", "callback",
    "selector", "observer", "registry",
)


def test_r30_no_generic_parameter_anywhere_on_the_public_surface():
    assert list(inspect.signature(PiRpcSupervisor.probe_runtime_capabilities).parameters) == ["self"]
    assert list(inspect.signature(PiRpcSupervisor.launch).parameters) == ["self"]
    for cls in (PiRpcSupervisor, RecordStreamReader):
        for name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name.startswith("_") and name != "__init__":
                continue
            for parameter in inspect.signature(member).parameters:
                for fragment in _FORBIDDEN_PARAMETER_FRAGMENTS:
                    assert fragment not in parameter.lower(), (cls.__name__, name, parameter)
    assert "probe" not in "".join(inspect.signature(RecordStreamReader.__init__).parameters)


def test_r32_the_probe_command_type_is_a_fixed_module_constant():
    assert PROBE_COMMAND_TYPE == "get_state"
    tree = ast.parse(textwrap.dedent(inspect.getsource(PiRpcSupervisor.probe_runtime_capabilities)))
    type_values = [
        node.values[node.keys.index(key)]
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for key in node.keys
        if isinstance(key, ast.Constant) and key.value == "type"
    ]
    assert len(type_values) == 1
    assert isinstance(type_values[0], ast.Name) and type_values[0].id == "PROBE_COMMAND_TYPE"


def test_r33_the_raw_value_is_touched_only_by_two_identity_tests():
    tree = ast.parse(inspect.getsource(runtime_probe.classify_raw_model_reasoning))
    function = tree.body[0]

    def _is_raw_value(node):
        return (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "model"
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "reasoning"
        )

    uses = [node for node in ast.walk(function) if _is_raw_value(node)]
    assert len(uses) == 2
    parents = {
        child: parent for parent in ast.walk(function) for child in ast.iter_child_nodes(parent)
    }
    for use in uses:
        compare = parents[use]
        assert isinstance(compare, ast.Compare)
        assert compare.left is use
        assert len(compare.ops) == 1 and isinstance(compare.ops[0], ast.Is)
        assert isinstance(compare.comparators[0], ast.Constant)
        assert compare.comparators[0].value in (True, False)
    # nothing else in the function calls anything or binds the value
    assert not [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    assert not [node for node in ast.walk(function) if isinstance(node, (ast.Assign, ast.NamedExpr))]
    for node in ast.walk(function):
        if isinstance(node, ast.Compare):
            assert not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)


class _StrSubclass(str):
    pass


@pytest.mark.parametrize(
    "provider, model",
    [
        (None, "m"), ("p", None), ("", "m"), ("p", ""), (b"p", "m"), ("p", b"m"),
        (5, "m"), (_StrSubclass("p"), "m"), ("p", _StrSubclass("m")), (["p"], "m"),
    ],
)
def test_r34_constructor_expectations_must_be_exact_nonempty_str(provider, model):
    with pytest.raises(PiSupervisorError):
        PiRpcSupervisor(
            argv=("x",), cwd=".", environment={}, bounds=FAST_BOUNDS,
            expected_provider=provider, expected_model=model,
        )
    # both absent is the unchanged AR2 / O1 / qualification construction
    PiRpcSupervisor(argv=("x",), cwd=".", environment={}, bounds=FAST_BOUNDS)


def test_r38_publication_under_the_reader_lock_never_self_deadlocks(tmp_path, monkeypatch):
    log: list = []
    entered_publish_while_owned = []

    class _Reader(RecordStreamReader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._lock = OwnerTrackingLock("reader", log)
            self._condition = threading.Condition(self._lock)

        def _publish(self, record):
            entered_publish_while_owned.append(self._lock.held_by_current_thread())
            return super()._publish(record)

    monkeypatch.setattr(supervisor_module, "RecordStreamReader", _Reader)
    frames = [frame({"type": "before"}), get_state_frame(), frame({"type": "after"})]
    peer = make_peer(tmp_path, **respond_config(frames))
    supervisor = make_supervisor(peer)
    supervisor.launch()
    try:
        thread, box = run_in_thread(supervisor.probe_runtime_capabilities)
        thread.join(8)
        assert not thread.is_alive(), "the probe self-deadlocked"
        deadline = time.monotonic() + 3
        while supervisor._stdout.record_count() < 3 and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        close(supervisor)
    assert box["result"] == (True, "TRUE", "ABSENT", "medium")
    assert entered_publish_while_owned and not any(entered_publish_while_owned)
    types = [record.get("type") for record in supervisor.sanitized_events()]
    assert types == ["before", "response", "after"]


def test_r39_the_expectation_binding_cannot_be_changed_through_the_supported_api(tmp_path):
    public_names = [name for name in dir(PiRpcSupervisor) if not name.startswith("_")]
    assert not [name for name in public_names if "expect" in name or "provider" in name]
    for name, member in inspect.getmembers(PiRpcSupervisor, predicate=inspect.isfunction):
        if name == "__init__" or name.startswith("_"):
            continue
        parameters = set(inspect.signature(member).parameters)
        assert not parameters & {"expected_provider", "expected_model", "provider", "model"}, name

    peer = make_peer(tmp_path, "same", **respond_config([get_state_frame()]))
    supervisor = make_supervisor(peer)
    for name in ("expected_provider", "expected_model", "provider", "model", "expectations"):
        setattr(supervisor, name, "attacker-value")  # creates an unrelated attribute
        delattr(supervisor, name)
    supervisor.expected_provider = "attacker-provider"
    supervisor.launch()
    try:
        facts = supervisor.probe_runtime_capabilities()
    finally:
        close(supervisor)
    assert facts[0] is True
    assert supervisor._probe_slot.expected_provider == EXPECTED_PROVIDER
    assert supervisor._probe_slot.expected_model == EXPECTED_MODEL

    other = make_peer(
        tmp_path, "different",
        **respond_config([get_state_frame(state_data(provider="attacker-provider"))]),
    )
    supervisor = make_supervisor(other)
    supervisor.expected_provider = "attacker-provider"
    supervisor.launch()
    try:
        facts = supervisor.probe_runtime_capabilities()
    finally:
        close(supervisor)
    assert facts[0] is False
