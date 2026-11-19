"""P0-RECOVERY-T2 — the opt-in ``delimited_file`` reply envelope, tested offline.

Every test is offline. Workspaces are synthetic directories or synthetic Git
repositories under pytest ``tmp_path``; every model is an ``httpx.MockTransport``
handler behind AIDO's own clients and wrappers. No socket, no real model, no real
target project and no real key is involved.

What is proven:

1. the default ``json_content_text`` mode is byte-compatible: the JSON-mode
   instruction constants, the golden Alpha 2A request digests, the default
   project-config serialization and the P1B config digest are unchanged (the
   config digest is pinned to the value the baseline ``c6e992c4`` produces);
2. the strict delimited parser extracts the exact file text for LF and CRLF
   files (quote-heavy Python, backslashes, f-strings, terminal newlines) and
   rejects, never repairs, every malformed envelope;
3. the request builder selects the delimited instruction for round 1 and for
   the correction round, keeps the user message identical, and refuses before
   sending when a marker is already in the input;
4. the real offline runner, the real live P1B path and the real task
   coordinator (round 1 and round 2) parse delimited replies through the
   unchanged diff generator and reachability proof, record the envelope, and
   reject invalid replies with exactly one request, no retry, no workspace
   write and no approval created.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys

import httpx
import pytest
import yaml
from pydantic import ValidationError

import test_supervised_implementer as off
import test_supervised_implementer_live as lv
from test_task_correction_round import (
    BEGIN,
    CORRECTED,
    GOLDEN_MESSAGES_SHA256,
    GOLDEN_PAYLOAD_SHA256,
    GOLDEN_SYSTEM_SHA256,
    _consent2,
    _golden_plan,
    _restore,
    _round1_to_offer,
    _sequence,
    _stage,
)
from test_task_approve import _shown_before_first_answer, _to_consent
from test_task_coordinator import (
    IMPLEMENT,
    IMPLEMENTER_MODEL,
    PREPARE,
    PROPOSED,
    Env as TaskEnv,
    _continue,
    _reviewer_reply,
    _workspace,
)

from ai_dev_orchestrator import supervised_implementer as sup
from ai_dev_orchestrator.models import ProjectConfig, SupervisedImplementerConfig
from ai_dev_orchestrator.supervised_implementer import correction as sic
from ai_dev_orchestrator.supervised_implementer import live
from ai_dev_orchestrator.supervised_implementer import request as sir
from ai_dev_orchestrator.supervised_implementer.live_authorization import (
    canonical_json_bytes,
    sha256_hex,
)
from ai_dev_orchestrator.task import run as task_run
from ai_dev_orchestrator.supervised_implementer.models import (
    DELIMITED_BEGIN_MARKER as BEGIN_M,
    DELIMITED_END_MARKER as END_M,
    SupervisedImplementerOutputRejected,
    SupervisedImplementerRefused,
    parse_supervised_implementer_delimited_output as parse_delimited,
    parse_supervised_implementer_output as parse_json,
)

_windows_git = [
    pytest.mark.skipif(sys.platform != "win32", reason="the live path and 5F2C writer are Windows-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
]

DELIMITED = "delimited_file"

# Captured from this change's builder; pinned so any later edit is deliberate.
GOLDEN_DELIMITED_SYSTEM_SHA256 = "d1ccc3a37a050b77e18231162f15aad0e4e07acf2eebba219fb006a78cf2ebdf"
GOLDEN_DELIMITED_CORRECTION_SYSTEM_SHA256 = (
    "4fd60b5071a1ae4c68f93230a5d7994b449af2dc18e431850a04bc11354bd8b1"
)
# The accepted correction instruction, unchanged since ALPHA-2B-T1 (equal at c6e992c4).
GOLDEN_CORRECTION_SYSTEM_SHA256 = "66cc61b67c01dff946bd4b78ad430e272584a58af2c28bbac00ad417fc2559af"
# The P1B canonical-JSON project-config digest of _BASELINE_CONFIG, computed by
# the UNCHANGED baseline c6e992c4 source. Equality proves a default-mode config
# still binds the same digest, so every authorization binding is unchanged.
GOLDEN_BASELINE_CONFIG_DIGEST = "c9c1fe634c05a672f1896fa19ba6a13841f18a94711b58a6250c5a544f09aa83"
_BASELINE_CONFIG = {
    "project_id": "p", "display_name": "D",
    "repo": {"workspace_path": "C:/synthetic/ws", "github_repo": "o/r", "branch_prefix": "ai/p"},
    "allowed_paths": ["src/**"], "protected_paths": [], "forbidden_paths": [".git/**"],
    "read_only_workspace_content": {"enabled": True},
    "supervised_implementer": {
        "enabled": True, "live_transmission_enabled": True, "candidate": "SUP-D",
        "provider": "litellm", "model": "qwen3.8-27b", "allow_insecure_http": True,
        "structured_output": False, "attempt_timeout_seconds": 30.0,
        "authorization_ledger_dir": "C:/synthetic/ledger",
    },
}

# Quote-heavy Python: f-strings, nested quotes, triple quotes, raw strings,
# backslash escapes, a regex, non-ASCII text and a trailing blank line before the
# final newline. Under the JSON envelope every one of these must be escaped.
QUOTE_HEAVY = (
    '"""Formatting helpers with \'quotes\' and "double quotes"."""\n'
    "import re\n"
    "\n"
    'PATTERN = re.compile(r"^(\\d+):(\\d{2})$")\n'
    "WINDOWS = 'C:\\\\Users\\\\demo\\\\file.txt'\n"
    "\n"
    "\n"
    "def fmt(hours: int, minutes: int, seconds: int) -> str:\n"
    '    """Return \\"H:MM:SS\\" — or MM:SS under an hour."""\n'
    "    if hours:\n"
    '        return f"{hours}:{minutes:02d}:{seconds:02d}"\n'
    "    return f\"{minutes:02d}:{seconds:02d}\"\n"
    "\n"
    "\n"
    "def quote(text: str) -> str:\n"
    "    return f'\"{text}\"' + \"\\n\" + 'tab\\there' + \"\\\\\"\n"
    "\n"
)


def _delim(text: str, ending: str = "\n", *, before: str = "", after: str = "\n") -> str:
    return f"{before}{BEGIN_M}{ending}{text}{END_M}{after}"


def _sha(text: str) -> str:
    # Compared with the PINNED digests, never with the module constants, so a
    # builder that silently ignored the envelope could not pass by aliasing.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _category(text: str, ending: str = "\n") -> str:
    with pytest.raises(SupervisedImplementerOutputRejected) as info:
        parse_delimited(text, line_ending=ending)
    assert info.value.transmission_attempted is True
    return info.value.category


# -- 1. the default JSON mode is byte-compatible ----------------------------------


def test_quote_heavy_fixture_is_valid_python():
    compile(QUOTE_HEAVY, "fmt.py", "exec")


@pytest.mark.parametrize("explicit", [False, True])
def test_the_default_request_is_byte_identical_to_alpha_2a(explicit):
    kwargs = {"output_envelope": "json_content_text"} if explicit else {}
    request = sir.build_supervised_implementer_request(
        approved_plan=_golden_plan(), target_path="src/mod.py", current_text=off.ORIGINAL,
        model="qwen3.8-27b", max_output_tokens=None, structured_output=False, **kwargs,
    )
    assert sir.request_messages_sha256(request) == GOLDEN_MESSAGES_SHA256
    assert live.request_payload_sha256(request) == GOLDEN_PAYLOAD_SHA256
    assert _sha(request.messages[0].content) == GOLDEN_SYSTEM_SHA256


def test_the_json_mode_instruction_constants_are_unchanged():
    assert hashlib.sha256(sir.SYSTEM_INSTRUCTION.encode()).hexdigest() == GOLDEN_SYSTEM_SHA256
    assert (
        hashlib.sha256(sir.CORRECTION_SYSTEM_INSTRUCTION.encode()).hexdigest()
        == GOLDEN_CORRECTION_SYSTEM_SHA256
    )


def test_the_delimited_instructions_are_pinned_and_distinct():
    assert (
        hashlib.sha256(sir.DELIMITED_SYSTEM_INSTRUCTION.encode()).hexdigest()
        == GOLDEN_DELIMITED_SYSTEM_SHA256
    )
    assert (
        hashlib.sha256(sir.DELIMITED_CORRECTION_SYSTEM_INSTRUCTION.encode()).hexdigest()
        == GOLDEN_DELIMITED_CORRECTION_SYSTEM_SHA256
    )
    for text in (sir.DELIMITED_SYSTEM_INSTRUCTION, sir.DELIMITED_CORRECTION_SYSTEM_INSTRUCTION):
        assert f"\n{BEGIN_M}\n" in text and f"\n{END_M}\n" in text
        assert "content_text" not in text
    for text in (sir.SYSTEM_INSTRUCTION, sir.CORRECTION_SYSTEM_INSTRUCTION):
        assert BEGIN_M not in text and END_M not in text


def test_a_default_config_serializes_and_digests_exactly_as_the_baseline():
    project = ProjectConfig.model_validate(_BASELINE_CONFIG)
    dumped = project.model_dump(mode="json")
    assert "output_envelope" not in dumped["supervised_implementer"]
    assert sha256_hex(canonical_json_bytes(dumped)) == GOLDEN_BASELINE_CONFIG_DIGEST
    # Spelling the default out explicitly is the same config.
    explicit = json.loads(json.dumps(_BASELINE_CONFIG))
    explicit["supervised_implementer"]["output_envelope"] = "json_content_text"
    assert ProjectConfig.model_validate(explicit).model_dump(mode="json") == dumped


def test_a_delimited_config_serializes_the_envelope_and_round_trips():
    document = json.loads(json.dumps(_BASELINE_CONFIG))
    document["supervised_implementer"]["output_envelope"] = DELIMITED
    project = ProjectConfig.model_validate(document)
    dumped = project.model_dump(mode="json")
    assert dumped["supervised_implementer"]["output_envelope"] == DELIMITED
    assert sha256_hex(canonical_json_bytes(dumped)) != GOLDEN_BASELINE_CONFIG_DIGEST
    again = ProjectConfig.model_validate_json(project.model_dump_json())
    assert again.supervised_implementer.output_envelope == DELIMITED


@pytest.mark.parametrize("value", ["Delimited_File", "delimited", "json", "", 1, None, True])
def test_the_envelope_field_is_exact_and_strict(value):
    with pytest.raises(ValidationError):
        SupervisedImplementerConfig(output_envelope=value)


# -- 2. the strict delimited parser -----------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "x = 1\n",
        QUOTE_HEAVY,
        "\n\nleading blank lines\n",
        "trailing spaces   \n\t\n",
        "ünïcödé = '✓'\n",
        "a = 1\n\n\n",
    ],
    ids=["minimal", "quote-heavy", "leading-blanks", "trailing-whitespace", "non-ascii", "blank-tail"],
)
@pytest.mark.parametrize(
    "before,after",
    [("", ""), ("", "\n"), ("\n\n", "\n"), ("  \n", "  \n\n")],
    ids=["bare", "final-newline", "qwen-leading-newlines", "surrounding-whitespace"],
)
def test_lf_text_is_extracted_exactly(text, before, after):
    output = parse_delimited(_delim(text, before=before, after=after), line_ending="\n")
    assert output.content_text == text


@pytest.mark.parametrize("text", ["x = 1\r\n", QUOTE_HEAVY.replace("\n", "\r\n")])
def test_crlf_text_is_extracted_exactly(text):
    output = parse_delimited(_delim(text, "\r\n", after="\r\n"), line_ending="\r\n")
    assert output.content_text == text


@pytest.mark.parametrize(
    "reply,category",
    [
        (f"x = 1\n{END_M}\n", "delimited_begin_marker_missing"),
        (f"{BEGIN_M}\nx = 1\n", "delimited_end_marker_missing"),
        (f"{BEGIN_M}\n{BEGIN_M}\nx = 1\n{END_M}\n", "delimited_marker_repeated"),
        (f"{BEGIN_M}\nx = 1\n{END_M}\n{END_M}\n", "delimited_marker_repeated"),
        (f"{BEGIN_M}\ns = '{END_M}'\n{END_M}\n", "delimited_marker_repeated"),
        (f"{END_M}\nx = 1\n{BEGIN_M}\n", "delimited_markers_out_of_order"),
        (f"```python\n{BEGIN_M}\nx = 1\n{END_M}\n```\n", "delimited_text_outside_markers"),
        (f"Here is the file:\n{BEGIN_M}\nx = 1\n{END_M}\n", "delimited_text_outside_markers"),
        (f"{BEGIN_M}\nx = 1\n{END_M}\nDone.\n", "delimited_text_outside_markers"),
        (f"{BEGIN_M} x = 1\n{END_M}\n", "delimited_begin_marker_line_invalid"),
        (f"{BEGIN_M}x = 1\n{END_M}\n", "delimited_begin_marker_line_invalid"),
        (f"{BEGIN_M}\r\nx = 1\n{END_M}\n", "delimited_begin_marker_line_invalid"),
        (f"{BEGIN_M}\n{END_M}\n", "delimited_content_empty"),
        (f"{BEGIN_M}\nx = 1{END_M}\n", "delimited_end_marker_not_on_own_line"),
        (f"{BEGIN_M}\nx = 1\ny = 2   {END_M}\n", "delimited_end_marker_not_on_own_line"),
        (f"{BEGIN_M}\nx = 1\r\n{END_M}\n", "delimited_line_ending_mismatch"),
        (f"{BEGIN_M}\na = 1\r\nb = 2\n{END_M}\n", "delimited_line_ending_mismatch"),
        (f"{BEGIN_M}\na = 1\rb = 2\n{END_M}\n", "delimited_line_ending_mismatch"),
        (json.dumps({"content_text": "x = 1\n"}), "delimited_begin_marker_missing"),
        ("", "output_empty"),
        ("  \n\t\n", "output_empty"),
        (f"{BEGIN_M}\nx = '\x00'\n{END_M}\n", "output_schema_violation"),
        (f"{BEGIN_M}\nx = '\ud800'\n{END_M}\n", "output_schema_violation"),
    ],
    ids=[
        "no-begin", "no-end", "repeated-begin", "repeated-end", "marker-inside-text",
        "out-of-order", "markdown-fence", "prose-before", "prose-after",
        "begin-then-text", "begin-glued-to-text", "begin-crlf-in-lf-file", "empty",
        "end-glued-to-last-line", "end-after-trailing-spaces", "crlf-text-in-lf-file",
        "mixed-endings", "bare-cr", "json-envelope", "empty-reply", "whitespace-reply",
        "nul", "lone-surrogate",
    ],
)
def test_malformed_lf_replies_are_rejected_never_repaired(reply, category):
    assert _category(reply) == category


@pytest.mark.parametrize(
    "reply,category",
    [
        (f"{BEGIN_M}\nx = 1\r\n{END_M}\r\n", "delimited_begin_marker_line_invalid"),
        (f"{BEGIN_M}\r\nx = 1\n{END_M}\r\n", "delimited_line_ending_mismatch"),
        (f"{BEGIN_M}\r\na = 1\r\nb = 2\n{END_M}\r\n", "delimited_line_ending_mismatch"),
        (f"{BEGIN_M}\r\nx = 1{END_M}\r\n", "delimited_end_marker_not_on_own_line"),
    ],
    ids=["begin-lf-in-crlf-file", "lf-text-in-crlf-file", "mixed", "end-glued"],
)
def test_malformed_crlf_replies_are_rejected(reply, category):
    assert _category(reply, "\r\n") == category


def test_the_parser_appends_nothing_a_dropped_final_newline_is_refused():
    # The A1/A2 failure class: the file's last line terminator is not optional.
    assert _category(f"{BEGIN_M}\nreturn f\"{{x}}\"{END_M}") == "delimited_end_marker_not_on_own_line"


def test_non_text_and_an_invalid_line_ending_argument_are_refused():
    assert _category(None) == "output_not_text"  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parse_delimited(_delim("x = 1\n"), line_ending="\r")


def test_the_two_parsers_never_accept_each_others_envelope():
    with pytest.raises(SupervisedImplementerOutputRejected) as info:
        parse_json(_delim("x = 1\n"))
    assert info.value.category == "output_not_bare_json_object"
    assert _category(json.dumps({"content_text": "x = 1\n"})) == "delimited_begin_marker_missing"


# -- 3. the request builder ---------------------------------------------------------


def _build(**kwargs):
    values = {
        "approved_plan": _golden_plan(), "target_path": "src/mod.py", "current_text": off.ORIGINAL,
        "model": "qwen3.8-27b", "max_output_tokens": None, "structured_output": False,
    }
    values.update(kwargs)
    return sir.build_supervised_implementer_request(**values)


def _correction(**review_overrides) -> sic.CorrectionInput:
    review = {
        "verdict": "changes_requested", "summary": "Mark the rounding.",
        "findings": [{"severity": "major", "category": "correctness", "line": 2,
                      "message": "No marker.", "suggested_action": "Add one."}],
    }
    review.update(review_overrides)
    return sic.build_correction_input(
        reason="reviewer_changes_requested",
        baseline=sic.CorrectionBaseline(
            target_path="src/mod.py",
            source_sha256=hashlib.sha256(off.ORIGINAL.encode()).hexdigest(),
            source_bytes=len(off.ORIGINAL.encode()),
            workspace_head_object_id="a" * 40,
        ),
        previous_approved_diff="--- a/src/mod.py\n+++ b/src/mod.py\n@@ -1,2 +1,2 @@\n-x\n+y\n",
        verification={"outcome": "verified", "return_code": 0, "passed": True, "timed_out": False,
                      "output_limit_exceeded": False, "output_complete": True, "output_text": "1 passed\n"},
        review=review,
        workspace_path="C:/synthetic/ws",
    )


def test_a_delimited_round1_request_changes_only_the_system_instruction():
    json_request = _build()
    delimited = _build(output_envelope=DELIMITED)
    assert _sha(delimited.messages[0].content) == GOLDEN_DELIMITED_SYSTEM_SHA256
    assert delimited.messages[1].content == json_request.messages[1].content
    assert delimited.max_tokens is None and delimited.response_format is None
    assert live.request_payload_sha256(delimited) != GOLDEN_PAYLOAD_SHA256


def test_a_delimited_correction_request_uses_the_delimited_correction_instruction():
    correction = _correction()
    json_request = _build(correction=correction)
    delimited = _build(correction=correction, output_envelope=DELIMITED)
    assert _sha(json_request.messages[0].content) == GOLDEN_CORRECTION_SYSTEM_SHA256
    assert _sha(delimited.messages[0].content) == GOLDEN_DELIMITED_CORRECTION_SYSTEM_SHA256
    assert delimited.messages[1].content == json_request.messages[1].content
    assert '"correction"' in delimited.messages[1].content


@pytest.mark.parametrize(
    "kwargs",
    [
        {"current_text": f"# {BEGIN_M}\nx = 1\n"},
        {"current_text": f"s = '{END_M}'\n"},
        {"correction": "marker-in-finding"},
    ],
    ids=["begin-in-source", "end-in-source", "end-in-reviewer-finding"],
)
def test_a_marker_already_in_the_input_refuses_before_sending(kwargs):
    if kwargs.get("correction") == "marker-in-finding":
        kwargs = {"correction": _correction(summary=f"quote {END_M} here")}
    with pytest.raises(SupervisedImplementerRefused) as info:
        _build(output_envelope=DELIMITED, **kwargs)
    assert info.value.category == "delimited_marker_in_request"
    assert info.value.transmission_attempted is False
    _build(**kwargs)  # the JSON envelope is unaffected


@pytest.mark.parametrize(
    "kwargs",
    [{"output_envelope": "xml"}, {"output_envelope": None}, {"output_envelope": DELIMITED, "structured_output": True}],
    ids=["unknown", "none", "with-structured-output"],
)
def test_the_builder_refuses_an_unsupported_envelope(kwargs):
    with pytest.raises(ValueError):
        _build(**kwargs)


# -- 4. the offline runner: real parse, diff and reachability paths ------------------


def _offline(tmp_path, reply, *, original: str | None = None, **block):
    root = off._make_workspace(tmp_path)
    if original is not None:
        (root / "src" / "mod.py").write_bytes(original.encode("utf-8"))
    project = off._project(root, output_envelope=DELIMITED, **block)
    return root, project, off.FakeModel(reply)


def test_offline_quote_heavy_delimited_reply_is_proposed_exactly(tmp_path):
    root, project, fake = _offline(tmp_path, _delim(QUOTE_HEAVY, before="\n\n"))
    before = off._snapshot(root)
    notices: list = []
    result, _ = off._run(tmp_path, fake, project=project, notices=notices)
    assert result.provenance.outcome == "diff_proposed"
    assert result.diff_proposal.changes[0].post_image_sha256 == hashlib.sha256(QUOTE_HEAVY.encode()).hexdigest()
    assert result.provenance.proposed_content_sha256 == hashlib.sha256(QUOTE_HEAVY.encode()).hexdigest()
    assert result.provenance.output_envelope == DELIMITED
    assert json.loads(result.provenance.model_dump_json())["output_envelope"] == DELIMITED
    assert len(fake.requests) == 1 and len(notices) == 1
    assert _sha(fake.requests[0]["messages"][0]["content"]) == GOLDEN_DELIMITED_SYSTEM_SHA256
    assert "response_format" not in fake.requests[0]
    assert off._snapshot(root) == before  # nothing written
    assert result.provenance.orchestrator_approval_created is False
    assert result.provenance.next_step == "human_exact_diff_approval_required"


def test_offline_default_provenance_carries_no_envelope_field(tmp_path):
    result, fake = off._run(tmp_path)
    assert result.provenance.output_envelope == "json_content_text"
    assert "output_envelope" not in json.loads(result.provenance.model_dump_json())
    assert _sha(fake.requests[0]["messages"][0]["content"]) == GOLDEN_SYSTEM_SHA256


def test_offline_unchanged_delimited_reply_is_no_change(tmp_path):
    _, project, fake = _offline(tmp_path, _delim(off.ORIGINAL))
    result, _ = off._run(tmp_path, fake, project=project)
    assert result.provenance.outcome == "no_change_proposed"


def test_offline_crlf_file_with_a_crlf_delimited_reply_round_trips(tmp_path):
    original = off.ORIGINAL.replace("\n", "\r\n")
    proposed = off.PROPOSED.replace("\n", "\r\n")
    _, project, fake = _offline(tmp_path, _delim(proposed, "\r\n", after="\r\n"), original=original)
    result, _ = off._run(tmp_path, fake, project=project)
    assert result.provenance.outcome == "diff_proposed"
    assert result.diff_proposal.changes[0].post_image_sha256 == hashlib.sha256(proposed.encode()).hexdigest()


@pytest.mark.parametrize(
    "reply,original,category",
    [
        (f"{BEGIN_M}\n{off.PROPOSED.rstrip()}{END_M}\n", None, "delimited_end_marker_not_on_own_line"),
        (_delim(off.PROPOSED.replace("\n", "\r\n")), None, "delimited_line_ending_mismatch"),
        (_delim(off.PROPOSED.replace("\n", "\r\n"), "\r\n"), None, "delimited_begin_marker_line_invalid"),
        (_delim(off.PROPOSED, "\r\n"), off.ORIGINAL.replace("\n", "\r\n"), "delimited_line_ending_mismatch"),
        (f"```\n{_delim(off.PROPOSED)}```\n", None, "delimited_text_outside_markers"),
        (json.dumps({"content_text": off.PROPOSED}), None, "delimited_begin_marker_missing"),
    ],
    ids=["dropped-final-newline", "crlf-in-lf-file", "crlf-markers-in-lf-file",
         "lf-in-crlf-file", "fenced", "json-envelope"],
)
def test_offline_invalid_delimited_replies_are_rejected_once_without_writes(tmp_path, reply, original, category):
    root, project, fake = _offline(tmp_path, reply, original=original)
    before = off._snapshot(root)
    off._rejected(tmp_path, category, fake, project=project)
    assert off._snapshot(root) == before


def test_offline_default_mode_rejects_a_delimited_reply(tmp_path):
    off._make_workspace(tmp_path)
    off._rejected(tmp_path, "output_not_bare_json_object", off.FakeModel(_delim(off.PROPOSED)))


def test_offline_delimited_with_structured_output_is_refused_before_any_read(tmp_path):
    root = off._make_workspace(tmp_path)
    project = off._project(root, output_envelope=DELIMITED, structured_output=True)
    off._refused(tmp_path, "output_envelope_conflicts_with_structured_output", project=project)


def test_offline_a_forged_envelope_is_refused_by_the_gate(tmp_path):
    root = off._make_workspace(tmp_path)
    project = off._project(root)
    forged = project.supervised_implementer.model_copy(update={"output_envelope": "xml"})
    with pytest.raises(SupervisedImplementerRefused) as info:
        sup.check_supervised_implementer_gate(forged)
    assert info.value.category == "unsupported_output_envelope"


def test_offline_a_marker_in_the_source_is_refused_before_any_request(tmp_path):
    root = off._make_workspace(tmp_path)
    (root / "src" / "mod.py").write_bytes(f"# {BEGIN_M}\nx = 1\n".encode())
    project = off._project(root, output_envelope=DELIMITED)
    off._refused(tmp_path, "delimited_marker_in_request", project=project)


# -- 5. the live P1B path, with MockTransport behind AIDO's real wrappers --------------


def _live_reply(content: str) -> lv.FakeServer:
    return lv.FakeServer(lambda request: httpx.Response(200, json=lv._completion(content=content)))


class TestLive:
    pytestmark = _windows_git

    def test_delimited_happy_path_records_the_envelope_and_stops(self, tmp_path, capsys):
        env = lv.Env(tmp_path, output_envelope=DELIMITED)
        before = lv._workspace_state(env.repo)
        lv._consented(env, capsys)
        code, out, err, server = lv._run(capsys, env, _live_reply(_delim(QUOTE_HEAVY, before="\n\n")))
        assert code == 0, err
        assert len(server.requests) == 1
        body = json.loads(server.requests[0].content)
        assert _sha(body["messages"][0]["content"]) == GOLDEN_DELIMITED_SYSTEM_SHA256
        assert "response_format" not in body and "max_tokens" not in body
        provenance = json.loads(out)
        assert provenance["schema_version"] == "supervised-implementer-provenance.v2"
        assert provenance["aido_requested"]["output_envelope"] == DELIMITED
        assert provenance["aido_derived"]["proposed_content_sha256"] == hashlib.sha256(
            QUOTE_HEAVY.encode()
        ).hexdigest()
        assert "reply format:  delimited_file" in err
        (run_dir,) = lv._run_dirs(env)
        bound = json.loads(env.authorization.read_text(encoding="utf-8"))["bound"]
        request_bytes = (run_dir / "request-messages.json").read_bytes()
        assert hashlib.sha256(request_bytes).hexdigest() == bound["request_sha256"]
        assert lv._workspace_state(env.repo) == before

    def test_default_live_provenance_and_banner_are_unchanged(self, tmp_path, capsys):
        env = lv.Env(tmp_path)
        lv._consented(env, capsys)
        code, out, err, _ = lv._run(capsys, env)
        assert code == 0, err
        assert "output_envelope" not in json.loads(out)["aido_requested"]
        assert "reply format:" not in err

    def test_an_invalid_delimited_reply_is_rejected_once_and_writes_nothing(self, tmp_path, capsys):
        env = lv.Env(tmp_path, output_envelope=DELIMITED)
        before = lv._workspace_state(env.repo)
        lv._consented(env, capsys)
        reply = f"{BEGIN_M}\n{lv.PROPOSED.rstrip()}{END_M}\n"
        code, _, err, server = lv._run(capsys, env, _live_reply(reply))
        assert code == 4, err
        assert len(server.requests) == 1
        (run_dir,) = lv._run_dirs(env)
        outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
        assert outcome["state"] == "output_rejected"
        assert outcome["failure_category"] == "delimited_end_marker_not_on_own_line"
        assert outcome["orchestrator_retries_issued"] == 0
        assert outcome["orchestrator_approval_created"] is False
        assert outcome["orchestrator_workspace_written"] is False
        assert not (run_dir / "diff-proposal.json").exists()
        assert lv._workspace_state(env.repo) == before
        # The authorization is spent: a second run sends nothing.
        code, _, _, again = lv._run(capsys, env, _live_reply(_delim(lv.PROPOSED)))
        assert code != 0 and again.requests == []

    def test_switching_the_envelope_after_prepare_is_refused_unsent(self, tmp_path, capsys):
        env = lv.Env(tmp_path)
        lv._consented(env, capsys)
        env.write_config(output_envelope=DELIMITED)
        code, _, err, server = lv._run(capsys, env, read_env=lv._never_read_env)
        assert code == 1
        assert "authorization_mismatch" in err and "project_config_sha256" in err
        assert server.requests == []

    def test_a_marker_in_the_source_refuses_prepare_before_issuance(self, tmp_path, capsys):
        env = lv.Env(tmp_path, output_envelope=DELIMITED)
        (env.repo / "src" / "mod.py").write_bytes(f"# {END_M}\nx = 1\n".encode())
        lv._git(env.repo, "commit", "-q", "-am", "marker")
        code, _, err = lv._prepare(capsys, env)
        assert code == 1 and "delimited_marker_in_request" in err
        assert lv._ledger_names(env) == []
        assert not env.draft.exists()


# -- 6. the task coordinator: round 1, H2 display and the correction round ------------


def _delimited_task_env(tmp_path, *, proposals=(PROPOSED, CORRECTED), reviews=None) -> TaskEnv:
    from test_task_correction_round import CHANGES_REQUESTED
    from test_task_coordinator import VALID_REVIEW

    env = TaskEnv(tmp_path)
    document = yaml.safe_load(env.config.read_text(encoding="utf-8"))
    document["supervised_implementer"]["output_envelope"] = DELIMITED
    env.config.write_text(yaml.safe_dump(document), encoding="utf-8")
    env.implementer.respond = _sequence(*[_task_reply(_delim(text)) for text in proposals])
    env.reviewer.respond = _sequence(
        *[_reviewer_reply(review) for review in (reviews or (CHANGES_REQUESTED, VALID_REVIEW))]
    )
    return env


def _task_reply(content: str) -> dict:
    return {
        "id": "cmpl-impl",
        "model": IMPLEMENTER_MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


class TestTaskCoordinator:
    pytestmark = _windows_git

    def test_h2_names_the_delimited_envelope_and_the_default_display_does_not(self, tmp_path, capsys):
        (tmp_path / "d").mkdir()
        (tmp_path / "j").mkdir()
        delimited = _delimited_task_env(tmp_path / "d")
        _to_consent(capsys, delimited)
        assert "reply format: delimited_file" in _shown_before_first_answer(capsys, delimited)
        default = TaskEnv(tmp_path / "j")
        _to_consent(capsys, default)
        assert "reply format" not in _shown_before_first_answer(capsys, default)

    def test_round1_and_round2_use_the_selected_envelope(self, tmp_path, capsys):
        env = _delimited_task_env(tmp_path)
        _round1_to_offer(capsys, env)
        assert len(env.implementer.requests) == 1
        first = json.loads(env.implementer.requests[0].content)
        assert _sha(first["messages"][0]["content"]) == GOLDEN_DELIMITED_SYSTEM_SHA256
        assert _workspace(env.repo)[2] == PROPOSED.encode("utf-8")  # applied after human H3

        code, _, err = _continue(capsys, env, BEGIN)
        assert code == 0, err
        _restore(env)
        code, _, err = _continue(capsys, env, PREPARE)
        assert code == 0, err
        _consent2(env)
        code, _, err = _continue(capsys, env, IMPLEMENT)
        assert code == 0, err
        assert _stage(env) == "round2_diff_approval"
        assert len(env.implementer.requests) == 2
        second = json.loads(env.implementer.requests[1].content)
        assert _sha(second["messages"][0]["content"]) == GOLDEN_DELIMITED_CORRECTION_SYSTEM_SHA256
        assert '"correction"' in second["messages"][1]["content"]
        stderr = sorted((env.run_dir / "steps").glob("*-implementer-run-r2.exit-0.stderr"))[0]
        banner = stderr.read_text(encoding="utf-8")
        assert "reply format:  delimited_file" in banner and "ROUND 2" in banner
        draft = (env.run_dir / task_run.ROUND_2.diff_draft_file).read_text(encoding="utf-8")
        assert hashlib.sha256(CORRECTED.encode()).hexdigest() in draft
        # Round 2 stops at its own human diff approval: the workspace holds the baseline.
        assert _workspace(env.repo)[2] != CORRECTED.encode("utf-8")

    def test_an_invalid_round1_delimited_reply_ends_the_task_without_a_write(self, tmp_path, capsys):
        from test_task_coordinator import _approve_plan, _consent, _start

        env = _delimited_task_env(tmp_path)
        env.implementer.respond = _sequence(_task_reply(f"{BEGIN_M}\n{PROPOSED.rstrip()}{END_M}\n"))
        before = _workspace(env.repo)
        code, _, err = _start(capsys, env)
        assert code == 0, err
        _approve_plan(env)
        assert _continue(capsys, env, PREPARE)[0] == 0
        _consent(env)
        code, _, _ = _continue(capsys, env, IMPLEMENT)
        assert code == 4
        assert _stage(env) == "implementer_failed"
        assert len(env.implementer.requests) == 1 and env.reviewer.requests == []
        assert _workspace(env.repo) == before
