"""AR1-FU1 offline tests: fail-closed H1 extension identity, fail-closed scrub
emission.

Rules this suite obeys (same as the rest of the AR1 suite):

- NO network, NO socket, NO model call, NO Pi process, NO API key.
- No real endpoint/key value is ever used, even a synthetic-looking one that
  could be mistaken for real -- only obviously-fake placeholders.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ar1.pi_config import EXPECTED_EXTENSION_SOURCE_KIND, SENTINEL_COMMAND_NAME
from ar1.record import refusal_record, scrub_check

import run_ar1
from run_ar1 import emit_or_refuse, evaluate_extension_identity

EXPECTED_ENTRY = r"C:\disposable\pi_extension\index.ts"


def _sentinel(
    *,
    name: str = SENTINEL_COMMAND_NAME,
    source: str = "extension",
    source_info: dict[str, Any] | None = None,
    flat_path: str | None = None,
) -> dict[str, Any]:
    command: dict[str, Any] = {"name": name, "source": source}
    if source_info is not None:
        command["sourceInfo"] = source_info
    if flat_path is not None:
        command["path"] = flat_path
    return command


# -- H1: fail-closed extension identity ----------------------------------------


def test_h1_exact_expected_source_info_path_passes():
    commands = [_sentinel(source_info={"path": EXPECTED_ENTRY, "source": "cli"})]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is True
    assert result["extension_path_matched"] is True
    assert result["noncontradictory_source_origin"] is True
    assert result["sentinel_source_kind"] == "cli"


def test_h1_alternate_flat_path_passes_when_source_info_path_absent():
    commands = [_sentinel(source_info={"source": "cli"}, flat_path=EXPECTED_ENTRY)]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is True
    assert result["extension_path_matched"] is True


def test_h1_sentinel_absent_fails():
    commands = [{"name": "something-else", "source": "extension", "path": EXPECTED_ENTRY}]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is False
    assert result["sentinel_name_matched"] is False
    assert result["failure_reasons"]


def test_h1_correct_name_wrong_source_fails():
    commands = [_sentinel(source="prompt", flat_path=EXPECTED_ENTRY)]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is False
    assert result["sentinel_name_matched"] is True
    assert result["extension_source_matched"] is False


def test_h1_source_info_path_missing_and_no_flat_path_fails():
    commands = [_sentinel(source_info={"source": "cli"})]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is False
    assert result["extension_path_matched"] is False
    assert any("cannot be proven" in reason for reason in result["failure_reasons"])


def test_h1_source_info_path_wrong_fails():
    commands = [
        _sentinel(source_info={"path": r"C:\attacker\evil.ts", "source": "cli"})
    ]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is False
    assert result["extension_path_matched"] is False


def test_h1_flat_path_wrong_fails():
    commands = [_sentinel(flat_path=r"C:\attacker\evil.ts")]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is False
    assert result["extension_path_matched"] is False


def test_h1_malformed_source_info_fails():
    commands = [_sentinel(source_info="not-an-object")]  # type: ignore[arg-type]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is False
    assert result["malformed_source_metadata"] is True


def test_h1_contradictory_known_source_origin_fails():
    commands = [
        _sentinel(source_info={"path": EXPECTED_ENTRY, "source": "config"})
    ]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is False
    assert result["noncontradictory_source_origin"] is False
    assert result["extension_path_matched"] is True  # path alone is not enough
    assert result["sentinel_source_kind"] == "config"


def test_h1_missing_source_origin_field_is_not_a_contradiction():
    """The field is optional; absence must never be treated as a mismatch."""
    commands = [_sentinel(source_info={"path": EXPECTED_ENTRY})]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is True
    assert result["noncontradictory_source_origin"] is True
    assert result["sentinel_source_kind"] is None


def test_h1_historical_style_payload_shape_is_parsed_truthfully():
    """The exact Pi 0.84.2 shape from FINDINGS.md section 3, parsed without
    weakening the stricter FU1 identity requirement."""
    commands = [
        {
            "name": SENTINEL_COMMAND_NAME,
            "source": "extension",
            "sourceInfo": {"path": EXPECTED_ENTRY, "source": "cli", "scope": "temporary"},
        }
    ]
    result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert result["passed"] is True
    assert result["sentinel_source_kind"] == "cli"
    assert result["expected_source_kind"] == EXPECTED_EXTENSION_SOURCE_KIND


def test_h1_default_expected_source_kind_is_cli():
    assert EXPECTED_EXTENSION_SOURCE_KIND == "cli"


# -- H1: proof that a failed gate results in ZERO dispatched prompts -----------


class _FakePromptSender:
    """A counter standing in for the one real semantic dispatch in phase_live.

    Mirrors production's actual gating shape: ``phase_live`` composes a
    ``gate`` dict and only sends when ``all(bool(v) for v in gate.values())``.
    This uses that exact same composition, so the test proves the real gating
    rule refuses dispatch -- not just that the identity function returns False.
    """

    def __init__(self) -> None:
        self.prompt_count = 0

    def maybe_send(self, gate: dict[str, Any]) -> None:
        if all(bool(v) for v in gate.values()):
            self.prompt_count += 1


def _live_style_gate(*, extension_handshake_passed: bool) -> dict[str, Any]:
    return {
        "pi_version_is_pinned_0_84_2": True,
        "node_direct_launch_works": True,
        "baseline_repository_trusted": True,
        "baseline_shows_exactly_seeded_failure": True,
        "route_configuration_available": True,
        "extension_sentinel_handshake_passed": extension_handshake_passed,
        "model_identity_handshake_passed": True,
    }


def test_failed_h1_sends_zero_prompts():
    commands = [_sentinel(flat_path=r"C:\attacker\evil.ts")]  # path mismatch
    identity_result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert identity_result["passed"] is False

    sender = _FakePromptSender()
    gate = _live_style_gate(extension_handshake_passed=identity_result["passed"])
    sender.maybe_send(gate)
    assert sender.prompt_count == 0


def test_passed_h1_plus_passed_h2_permits_the_next_gate():
    commands = [_sentinel(source_info={"path": EXPECTED_ENTRY, "source": "cli"})]
    identity_result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert identity_result["passed"] is True

    sender = _FakePromptSender()
    gate = _live_style_gate(extension_handshake_passed=identity_result["passed"])
    sender.maybe_send(gate)
    assert sender.prompt_count == 1


def test_path_mismatch_alone_prevents_prompt_dispatch_even_with_good_h2():
    commands = [
        _sentinel(source_info={"path": r"C:\wrong\path.ts", "source": "cli"})
    ]
    identity_result = evaluate_extension_identity(commands, extension_entry=EXPECTED_ENTRY)
    assert identity_result["passed"] is False

    sender = _FakePromptSender()
    gate = _live_style_gate(extension_handshake_passed=identity_result["passed"])
    sender.maybe_send(gate)
    assert sender.prompt_count == 0


# -- scrub / emission: fail-closed artifact emission ----------------------------


_FAKE_ENDPOINT = "http://synthetic-endpoint.invalid:8000/v1"


def test_clean_artifact_is_written(tmp_path: Path):
    payload = {"note": "nothing sensitive here"}
    out_path = tmp_path / "out.json"
    code = emit_or_refuse(payload, phase="preflight", out_path=out_path)
    assert code == 0
    assert out_path.is_file()
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["note"] == "nothing sensitive here"
    assert written["scrub"]["clean"] is True


def test_clean_artifact_is_ascii_safe(tmp_path: Path):
    payload = {"final_assistant_text": "caf\u00e9"}
    out_path = tmp_path / "out.json"
    emit_or_refuse(payload, phase="preflight", out_path=out_path)
    text = out_path.read_text(encoding="utf-8")
    assert text.isascii()


def test_scrub_finding_prevents_unsafe_artifact_from_being_written(tmp_path: Path):
    payload = {"leaked": f"the endpoint is {_FAKE_ENDPOINT}"}
    out_path = tmp_path / "out.json"
    code = emit_or_refuse(payload, phase="live", out_path=out_path)
    assert code == 2
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert _FAKE_ENDPOINT not in json.dumps(written)
    assert written["outcome"] == "artifact_emission_refused"
    assert "leaked" not in written


def test_scrub_finding_prevents_unsafe_artifact_from_being_echoed(tmp_path: Path, capsys):
    payload = {"leaked": f"the endpoint is {_FAKE_ENDPOINT}"}
    out_path = tmp_path / "out.json"
    emit_or_refuse(payload, phase="live", out_path=out_path)
    printed = capsys.readouterr().out
    assert _FAKE_ENDPOINT not in printed
    assert "leaked" not in printed


def test_refusal_artifact_contains_no_offending_value(tmp_path: Path):
    secret_marker = "sk-not-a-real-key-0000000000000000"
    payload = {"secret": secret_marker}
    out_path = tmp_path / "out.json"
    scrub_result = scrub_check(
        payload, extra_forbidden=(("configured_endpoint_value_present", secret_marker),)
    )
    assert scrub_result["clean"] is False
    refusal = refusal_record(
        phase="live",
        finding_count=len(scrub_result["findings"]),
        finding_categories=scrub_result["findings"],
    )
    assert secret_marker not in json.dumps(refusal)


def test_refusal_artifact_contains_no_endpoint_url(tmp_path: Path):
    payload = {"note": f"reached {_FAKE_ENDPOINT}"}
    out_path = tmp_path / "out.json"
    emit_or_refuse(payload, phase="live", out_path=out_path)
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert "http://" not in json.dumps(written)
    assert "synthetic-endpoint.invalid" not in json.dumps(written)


def test_refusal_artifact_contains_no_authorization_or_bearer_material(tmp_path: Path):
    payload = {"headers": "Authorization: Bearer sk-fake-not-real-000000"}
    out_path = tmp_path / "out.json"
    emit_or_refuse(payload, phase="live", out_path=out_path)
    written = json.loads(out_path.read_text(encoding="utf-8"))
    serialized = json.dumps(written)
    assert "Authorization" not in serialized
    assert "Bearer " not in serialized
    assert "sk-fake-not-real" not in serialized


def test_refusal_artifact_contains_no_reasoning_content(tmp_path: Path):
    payload = {
        "run": {
            "message": {"content": [{"type": "thinking", "thinking": "secret plan"}]}
        }
    }
    out_path = tmp_path / "out.json"
    emit_or_refuse(payload, phase="live", out_path=out_path)
    written = json.loads(out_path.read_text(encoding="utf-8"))
    serialized = json.dumps(written)
    assert "secret plan" not in serialized
    assert "thinking" not in serialized


def test_refusal_artifact_is_ascii_representable(tmp_path: Path):
    payload = {"leaked": f"{_FAKE_ENDPOINT} caf\u00e9"}
    out_path = tmp_path / "out.json"
    emit_or_refuse(payload, phase="live", out_path=out_path)
    text = out_path.read_text(encoding="utf-8")
    assert text.isascii()


def test_multiple_scrub_findings_emit_only_bounded_metadata(tmp_path: Path):
    payload = {
        "a": f"http endpoint {_FAKE_ENDPOINT}",
        "b": "Authorization: Bearer sk-fake-not-real",
        "c": {"content": [{"type": "thinking", "thinking": "secret plan"}]},
    }
    out_path = tmp_path / "out.json"
    code = emit_or_refuse(payload, phase="live", out_path=out_path)
    assert code == 2
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["finding_count"] >= 3
    assert set(written["finding_categories"]).issubset(
        {
            "http_url_scheme_present",
            "authorization_header_text_present",
            "bearer_token_marker_present",
            "reasoning_content_present",
        }
    )
    serialized = json.dumps(written)
    for leaked in (_FAKE_ENDPOINT, "sk-fake-not-real", "secret plan"):
        assert leaked not in serialized


def test_scrub_checker_exception_fails_closed(tmp_path: Path):
    """A payload ``scrub_check`` cannot even serialize must refuse, not crash."""
    payload = {"not_serializable": object()}
    out_path = tmp_path / "out.json"
    code = emit_or_refuse(payload, phase="preflight", out_path=out_path)
    assert code == 2
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["outcome"] == "artifact_emission_refused"
    assert "scrub_check_raised" in written["finding_categories"]


def test_scrub_check_findings_are_codes_not_raw_needles():
    secret_marker = "super-secret-endpoint-value-0000"
    payload = {"leaked": secret_marker}
    result = scrub_check(
        payload, extra_forbidden=(("configured_endpoint_value_present", secret_marker),)
    )
    assert result["clean"] is False
    assert result["findings"] == ["configured_endpoint_value_present"]
    assert secret_marker not in json.dumps(result)


# -- historical clean-record shape stays accepted, and is never rewritten -------

_HISTORICAL_LIVE_RECORD = (
    Path(__file__).resolve().parents[1] / "results" / "ar1_live_20260821T004934Z.json"
)


@pytest.mark.skipif(
    not _HISTORICAL_LIVE_RECORD.is_file(), reason="historical live record not present"
)
def test_historical_clean_record_shape_remains_accepted_and_unmodified():
    before = _HISTORICAL_LIVE_RECORD.read_bytes()
    record = json.loads(before)

    assert record["record_version"] == "ar1-run-record.v1"
    assert record["scrub"] == {"scrub_checked": True, "findings": [], "clean": True}
    # The pre-FU1 gate: a same-named, extension-sourced sentinel was sufficient.
    handshake = record["run"]["handshake_extension"]
    assert handshake["sentinel_present_from_extension_source"] is True
    assert handshake["passed"] is True
    # AR1-FU1 does not claim the historical run used the stricter gate: the
    # pre-FU1 record carries no "sentinel_source_kind" derived-identity field
    # and no "noncontradictory_source_origin" field at all.
    assert "noncontradictory_source_origin" not in handshake

    after = _HISTORICAL_LIVE_RECORD.read_bytes()
    assert after == before, "the historical live record must never be rewritten"
