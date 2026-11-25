"""ALPHA-2B-T1 — one human-supervised bounded correction round, tested offline.

Every workspace is a synthetic Git repository under pytest ``tmp_path``; the
verification program is a synthetic script under ``tmp_path``; both models are
``httpx.MockTransport`` handlers behind AIDO's own wrappers. No socket, no real
model, no real target project and no real key is involved. The test acts as the
human operator, including the ``git restore`` that AIDO never performs.

What is proven (ALPHA-2B-D1 §5): round-1 request byte compatibility; correction
eligibility and non-eligibility; refusal while the workspace is dirty;
preparation after a human restore; HEAD and source baseline mismatch;
authorization and identity mismatch; correction evidence provenance and
tampering; a fresh ledger authorization and replay refusal; a baseline-relative
complete round-2 diff; round-scoped stages, approvals and steps; the final
summary; interruption and partial failures; and the strict one-round limit.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import httpx
import pytest

from test_task_coordinator import (
    APPLY,
    APPROVER,
    FAKE_KEY,
    HOST,
    IMPLEMENT,
    ORIGINAL,
    PREPARE,
    PROPOSED,
    REVIEW,
    TARGET,
    VALID_REVIEW,
    Env,
    _approve_diff,
    _consent,
    _continue,
    _fill_approval,
    _git,
    _implementer_reply,
    _invoke,
    _reader,
    _reviewer_reply,
    _stage,
    _steps,
    _to_diff_approval,
    _tree,
    _workspace,
)

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.file_editing.models import REQUIRED_DIFF_EDIT_APPROVAL_TEXT
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.handoff.models import parse_approved_l1_plan_artifact
from ai_dev_orchestrator.supervised_implementer import correction as sic
from ai_dev_orchestrator.supervised_implementer import live
from ai_dev_orchestrator.supervised_implementer import live_authorization as la
from ai_dev_orchestrator.supervised_implementer import request as sir
from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused
from ai_dev_orchestrator.task import correction as task_correction
from ai_dev_orchestrator.task import run as task_run

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="the 5F2C writer is Windows-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
]

CORRECTED = "def total(x):\n    return round(x, 2)  # CORRECTED\n"
BEGIN = {"--begin-correction-round": True}
DECLINE = {"--decline-correction": True}

CHANGES_REQUESTED = {
    "verdict": "changes_requested",
    "summary": "The rounding is unmarked; mark it as corrected.",
    "findings": [
        {
            "severity": "major",
            "category": "correctness",
            "line": 2,
            "message": "FINDING-SENTINEL: the rounding line lacks the CORRECTED marker.",
            "suggested_action": "Append a CORRECTED comment to the return line.",
        }
    ],
    "residual_risks": [],
    "human_notes": [],
}
NEEDS_HUMAN = {**CHANGES_REQUESTED, "verdict": "needs_human_review", "findings": []}

# Fails until the target carries the CORRECTED marker. It also prints the
# workspace path, which must never reach the implementer.
CONTENT_SCRIPT = """\
import os
import sys
text = open(os.path.join("src", "mod.py"), encoding="utf-8").read()
sys.stdout.write("rootdir: " + os.getcwd() + "\\n")
if "CORRECTED" in text:
    sys.stdout.write("1 passed\\n")
    sys.exit(0)
sys.stdout.write("FAILED test_total: VERIFY-SENTINEL expected the corrected rounding\\n")
sys.exit(1)
"""

# Golden values of the Alpha 2A round-1 request, captured from the shipped
# builder at 0ebd9f65 before ALPHA-2B-T1 changed anything.
GOLDEN_MESSAGES_SHA256 = "5130397bd7c9c1cb7fd7f4faea913955b11cdfb2a07bf05740c0d87be91853e4"
GOLDEN_PAYLOAD_SHA256 = "018d5863f0b9792635b3fa4162a3d1ccd19e646e5b9b7bea896066d0842a8e69"
GOLDEN_SYSTEM_SHA256 = "ee4002c6c0f0aad7f69d7cf017c3beae447ae649b531b94fde5c5b3dfc773b68"


def _sequence(*bodies):
    """A respond() returning each body in turn, then refusing any extra request."""
    remaining = list(bodies)

    def respond(request):
        if not remaining:
            raise AssertionError("an unexpected extra model request")
        return httpx.Response(200, json=remaining.pop(0))

    return respond


def _env(tmp_path, *, reviews=(CHANGES_REQUESTED, VALID_REVIEW), proposals=(PROPOSED, CORRECTED), script=None) -> Env:
    env = Env(tmp_path)
    env.implementer.respond = _sequence(*[_implementer_reply(text) for text in proposals])
    env.reviewer.respond = _sequence(*[_reviewer_reply(review) for review in reviews])
    if script is not None:
        env.script.write_text(script, encoding="utf-8")
    return env


def _task(env):
    return task_run.load_task(str(env.run_dir))


def _ok(result):
    code, out, err = result
    assert code == 0, err
    return out, err


def _round1_to_offer(capsys, env) -> None:
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    _continue(capsys, env, APPLY)
    assert _stage(env) == "correction_offered"


def _restore(env) -> None:
    """The HUMAN's restore. AIDO never does this."""
    _git(env.repo, "restore", "--", TARGET)


def _r2_drafts(env) -> list[Path]:
    return sorted(env.run_dir.glob("50-authorization-*.json"))


def _consent2(env, path: Path | None = None) -> None:
    path = path or _r2_drafts(env)[-1]
    document = json.loads(path.read_text(encoding="utf-8"))
    document["consent"] = {
        "consented_by": APPROVER,
        "consented_at": la.utc_timestamp(la.parse_timestamp(document["bound"]["prepared_at"])),
        "source": "manual",
        "binding_sha256": document["bound"]["binding_sha256"],
        "endpoint_scheme": "http",
        "endpoint_host": HOST,
        "endpoint_port": 8080,
        "consent_text": la.CONSENT_TEXT,
        "plaintext_acknowledgement": la.PLAINTEXT_ACKNOWLEDGEMENT,
    }
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def _to_round2_consent(capsys, env) -> None:
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    _ok(_continue(capsys, env, PREPARE))
    assert _stage(env) == "round2_implementer_consent"


def _to_round2_diff_approval(capsys, env) -> None:
    _to_round2_consent(capsys, env)
    _consent2(env)
    _ok(_continue(capsys, env, IMPLEMENT))
    assert _stage(env) == "round2_diff_approval"


def _approve_diff2(env) -> None:
    _fill_approval(env.run_dir / task_run.ROUND_2.diff_draft_file, REQUIRED_DIFF_EDIT_APPROVAL_TEXT)


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def _user_payload(request: httpx.Request) -> dict:
    content = _body(request)["messages"][1]["content"]
    return json.loads(content.split("INPUT (JSON):\n", 1)[1])


def _round1_records(env) -> dict[str, bytes]:
    tree = _tree(env.run_dir)
    return {
        name: data
        for name, data in tree.items()
        if not (
            name.startswith(("40-", "50-", "60-", "61-", "summary-r2"))
            or "-r2." in name
        )
    }


def _first_bound(env) -> dict:
    return json.loads((env.run_dir / "20-authorization-1.json").read_text(encoding="utf-8"))["bound"]


def _ledger_names(env) -> list[str]:
    return sorted(os.listdir(env.tmp / "ledger"))


# -- 1. round-1 compatibility ------------------------------------------------------------------


def _golden_plan():
    document = {
        "approval": {
            "approved_by": "op@example.invalid",
            "approved_at": "2026-11-10T00:00:00+00:00",
            "approval_text": REQUIRED_APPROVAL_TEXT,
            "source": "manual",
        },
        "plan_provenance": {
            "engine": "aido-task", "operation": "task-start", "real_call": False, "model": None,
            "endpoint_host": None, "generated_at": "2026-11-10T00:00:00+00:00", "project_id": "p",
            "repo": "o/r", "issue_number": 7, "title": "T",
        },
        "plan": {
            "issue_number": 7, "repo": "o/r", "title": "T", "summary": "Round it.",
            "scope_summary": "Modify src/mod.py.", "non_goals": ["n"], "proposed_steps": ["s"],
            "files_likely_to_change": ["src/mod.py"], "files_forbidden_or_out_of_scope": [],
            "required_verification": ["v"], "risks": [], "open_questions": [],
            "automation_level": "L1", "requires_human_approval": True,
        },
        "project_id": "p", "repo": "o/r", "issue_number": 7,
    }
    return parse_approved_l1_plan_artifact(json.dumps(document))


@pytest.mark.parametrize("pass_none_explicitly", [False, True])
def test_a_round1_request_is_byte_identical_to_alpha_2a(pass_none_explicitly):
    kwargs = {"correction": None} if pass_none_explicitly else {}
    request = sir.build_supervised_implementer_request(
        approved_plan=_golden_plan(),
        target_path="src/mod.py",
        current_text=ORIGINAL,
        model="qwen3.8-27b",
        max_output_tokens=None,
        structured_output=False,
        **kwargs,
    )
    assert sir.request_messages_sha256(request) == GOLDEN_MESSAGES_SHA256
    assert live.request_payload_sha256(request) == GOLDEN_PAYLOAD_SHA256
    assert hashlib.sha256(sir.SYSTEM_INSTRUCTION.encode()).hexdigest() == GOLDEN_SYSTEM_SHA256
    assert request.messages[0].content == sir.SYSTEM_INSTRUCTION
    assert "correction" not in request.messages[1].content


def test_a_round1_live_run_sends_no_correction_and_the_2a_notice(tmp_path, capsys):
    env = _env(tmp_path)
    _to_diff_approval(capsys, env)
    body = _body(env.implementer.requests[0])
    assert body["messages"][0]["content"] == sir.SYSTEM_INSTRUCTION
    assert "correction" not in _user_payload(env.implementer.requests[0])
    stderr = next((env.run_dir / "steps").glob("02-implementer-run.exit-0.stderr")).read_text(encoding="utf-8")
    assert "correction:" not in stderr


def test_the_builder_refuses_a_correction_of_the_wrong_type():
    with pytest.raises(TypeError):
        sir.build_supervised_implementer_request(
            approved_plan=_golden_plan(), target_path="src/mod.py", current_text=ORIGINAL,
            model="qwen3.8-27b", max_output_tokens=None, structured_output=False,
            correction={"previous_approved_diff": "x"},
        )


# -- 2. the whole correction round, after changes_requested --------------------------------------


def test_a_changes_requested_round_is_corrected_from_the_baseline(tmp_path, capsys):
    env = _env(tmp_path)
    head = _git(env.repo, "rev-parse", "HEAD")
    _round1_to_offer(capsys, env)
    assert (env.run_dir / task_run.SUMMARY_FILE).exists()
    assert len(env.implementer.requests) == 1 and len(env.reviewer.requests) == 1
    round1 = _round1_records(env)

    # The offer: beginning records the decision only.
    out, err = _ok(_continue(capsys, env, BEGIN, implementer_env=_never, reviewer_env=_never))
    assert "git restore" in err and "DISCARDS" in err and "AIDO never restores" in err
    assert len(env.implementer.requests) == 1 and len(env.reviewer.requests) == 1
    assert _workspace(env.repo)[2] == PROPOSED.encode("utf-8")  # AIDO restored nothing
    record = json.loads((env.run_dir / task_run.CORRECTION_FILE).read_text(encoding="utf-8"))
    assert record["reason"] == "reviewer_changes_requested"
    assert record["human_restore_required"]["performed_by_aido"] is False
    assert record["baseline"]["workspace_head_object_id"] == head.strip()
    assert _stage(env) == "round2_restore_pending"

    # Prepare refuses while the round-1 candidate is still in the workspace.
    ledger_before = _ledger_names(env)
    code, _, err = _continue(capsys, env, PREPARE, implementer_env=_never, reviewer_env=_never)
    assert code == 1
    assert _r2_drafts(env) == []
    assert _ledger_names(env) == ledger_before
    assert _stage(env) == "round2_restore_pending"

    # After the human's restore, AIDO observes the baseline itself.
    _restore(env)
    _ok(_continue(capsys, env, PREPARE, implementer_env=_never, reviewer_env=_never))
    assert [path.name for path in _r2_drafts(env)] == ["50-authorization-1.json"]
    second = json.loads(_r2_drafts(env)[0].read_text(encoding="utf-8"))["bound"]
    first = _first_bound(env)
    for name in task_correction.BASELINE_FIELDS:
        assert second[name] == first[name], name
    for name in ("run_id", "issuance_sha256", "binding_sha256", "request_sha256"):
        assert second[name] != first[name], name
    assert second["workspace_head_object_id"] == head.strip()
    assert env.implementer.requests[1:] == []

    # The fresh consent and the one round-2 request.
    _consent2(env)
    calls: list[str] = []
    _ok(_continue(capsys, env, IMPLEMENT, implementer_env=_reader(calls), reviewer_env=_never))
    assert calls == ["litellm"]
    assert len(env.implementer.requests) == 2
    sent = env.implementer.requests[1]
    assert _body(sent)["messages"][0]["content"] == sir.CORRECTION_SYSTEM_INSTRUCTION
    payload = _user_payload(sent)
    assert payload["current_file_text"] == ORIGINAL
    assert payload["target_path"] == TARGET
    correction = payload["correction"]
    assert correction["reason"] == "reviewer_changes_requested"
    assert "UNTRUSTED" in correction["nature"]
    assert "+    return round(x, 2)" in correction["previous_approved_candidate_diff"]["unified_diff"]
    assert correction["aido_observed_verification_facts"]["outcome"] == "verified"
    findings = correction["untrusted_reviewer_findings"]
    assert findings["verdict"] == "changes_requested"
    assert "FINDING-SENTINEL" in findings["findings"][0]["message"]
    assert "baseline" not in correction  # the baseline identity is never transmitted
    request_text = sent.content.decode("utf-8")
    assert str(env.repo).casefold() not in request_text.casefold()
    assert FAKE_KEY not in request_text
    stderr = sorted((env.run_dir / "steps").glob("*-implementer-run-r2.exit-0.stderr"))[0].read_text(encoding="utf-8")
    assert "ROUND 2" in stderr

    # The round-2 diff is the complete change against the ORIGINAL baseline.
    diff2 = (env.run_dir / task_run.ROUND_2.diff_text_file).read_text(encoding="utf-8")
    assert "-    return x" in diff2
    assert "+    return round(x, 2)  # CORRECTED" in diff2
    assert "-    return round(x, 2)\n" not in diff2
    assert _stage(env) == "round2_diff_approval"

    # Its own approval, write, verification and review.
    _approve_diff2(env)
    _ok(_continue(capsys, env, APPLY))
    assert _stage(env) == "round2_awaiting_human_decision"
    head_after, status, target = _workspace(env.repo)
    assert head_after == head
    assert status == f" M {TARGET}\n"
    assert target == CORRECTED.encode("utf-8")
    assert len(env.reviewer.requests) == 2

    stdout_steps = [name.split(".")[0] for name in _steps(env) if name.endswith(".stdout")]
    assert stdout_steps == [
        "01-prepare", "02-implementer-run", "03-apply", "04-review",
        "05-prepare-r2", "06-prepare-r2", "07-implementer-run-r2", "08-apply-r2", "09-review-r2",
    ]
    # Round-1 evidence is preserved byte-exact, and both summaries exist.
    assert {name: data for name, data in _round1_records(env).items() if name in round1} == round1
    summary2 = (env.run_dir / task_run.ROUND_2.summary_file).read_text(encoding="utf-8")
    assert "FINAL" in summary2 and "NOT itself" in summary2
    assert "Round-2 reviewer model claims (NOT verified by AIDO)" in summary2
    assert "Final workspace state, as AIDO last observed it" in summary2
    assert f"Git-visible dirty paths:                     {TARGET}" in summary2
    assert "READY FOR YOUR DECISION" in summary2
    assert "This was the only correction round" in summary2

    # The strict limit: nothing continues, and no third round exists.
    for flags in (BEGIN, REVIEW, PREPARE, IMPLEMENT, APPLY, DECLINE):
        code, _, err = _continue(capsys, env, flags)
        assert code == 1 and "finished" in err
    assert len(env.implementer.requests) == 2


def _never(provider):
    raise AssertionError("no environment may be read on this path")


# -- 3. the correction round after a verification failure --------------------------------------


def test_a_verification_failure_is_corrected_with_redacted_observed_facts(tmp_path, capsys):
    env = _env(tmp_path, reviews=(VALID_REVIEW,), script=CONTENT_SCRIPT)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    code, _, _ = _continue(capsys, env, APPLY)
    assert code == 2
    assert env.reviewer.requests == []
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "correction_offered"
    assert set(stage.actions) == {
        task_run.REVIEW_FLAGS, task_run.BEGIN_CORRECTION_FLAGS, task_run.DECLINE_CORRECTION_FLAGS,
    }

    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    _ok(_continue(capsys, env, PREPARE))
    _consent2(env)
    _ok(_continue(capsys, env, IMPLEMENT))
    correction = _user_payload(env.implementer.requests[1])["correction"]
    assert correction["reason"] == "verification_failed"
    assert correction["untrusted_reviewer_findings"] is None
    facts = correction["aido_observed_verification_facts"]
    assert facts["outcome"] == "verification-failed" and facts["passed"] is False
    assert facts["return_code"] == 1
    assert "VERIFY-SENTINEL" in facts["output_text"]
    # The verification child printed the workspace path; it is replaced.
    assert sic.WORKSPACE_PLACEHOLDER in facts["output_text"]
    assert str(env.repo).casefold() not in env.implementer.requests[1].content.decode().casefold()
    # ...while the round-1 evidence keeps the original output byte-exact.
    review_record = next((env.run_dir / "steps").glob("04-review.exit-2.stdout")).read_text(encoding="utf-8")
    assert json.dumps(str(env.repo))[1:-1] in review_record

    _approve_diff2(env)
    _ok(_continue(capsys, env, APPLY))
    assert _stage(env) == "round2_awaiting_human_decision"
    assert (env.repo / TARGET).read_bytes() == CORRECTED.encode("utf-8")


def test_a_verification_failure_still_allows_the_2a_review_retry(tmp_path, capsys):
    env = _env(tmp_path, reviews=(VALID_REVIEW,), script=CONTENT_SCRIPT)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    assert _continue(capsys, env, APPLY)[0] == 2
    env.script.write_text("print('1 passed')\n", encoding="utf-8")
    _ok(_continue(capsys, env, REVIEW))
    # The latest round-1 result now is 'approve', so no correction is offered.
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "awaiting_human_decision" and stage.terminal
    assert "No correction round is offered" in stage.message


# -- 4. non-eligibility ------------------------------------------------------------------------


@pytest.mark.parametrize("review", [VALID_REVIEW, NEEDS_HUMAN], ids=["approve", "needs_human_review"])
def test_no_correction_is_offered_for_approve_or_needs_human_review(tmp_path, capsys, review):
    env = _env(tmp_path, reviews=(review,), proposals=(PROPOSED,))
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    _ok(_continue(capsys, env, APPLY))
    assert _stage(env) == "awaiting_human_decision"
    before = _tree(env.run_dir)
    for flags in (BEGIN, DECLINE):
        code, _, err = _continue(capsys, env, flags)
        assert code == 1 and "finished" in err
    assert _tree(env.run_dir) == before


def test_no_correction_is_offered_for_an_untrusted_workspace(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    env.script.write_text("open('stray_artifact.txt', 'w').write('x')\nprint('done')\n", encoding="utf-8")
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    assert _continue(capsys, env, APPLY)[0] == 3
    assert _stage(env) == "workspace_untrusted"
    code, _, err = _continue(capsys, env, BEGIN)
    assert code == 1 and "finished" in err
    assert not (env.run_dir / task_run.CORRECTION_FILE).exists()


def test_no_correction_is_offered_after_a_reviewer_failure(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    env.reviewer.respond = lambda request: httpx.Response(200, json=_reviewer_reply({"verdict": "maybe"}))
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    assert _continue(capsys, env, APPLY)[0] == 4
    assert _stage(env) == "review_pending"
    code, _, err = _continue(capsys, env, BEGIN)
    assert code == 1 and "accepts exactly" in err
    assert not (env.run_dir / task_run.CORRECTION_FILE).exists()


def test_a_malformed_review_record_offers_no_correction(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    record = next((env.run_dir / "steps").glob("04-review.exit-0.stdout"))
    record.write_bytes(record.read_bytes().replace(b'"changes_requested"', b'"approve"', 1)[:-40])
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "awaiting_human_decision" and stage.terminal
    assert "No correction round is offered" in stage.message
    code, _, _ = _continue(capsys, env, BEGIN)
    assert code == 1


def test_a_review_packet_for_another_approval_offers_no_correction(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    record = next((env.run_dir / "steps").glob("04-review.exit-0.stdout"))
    record.write_bytes(record.read_bytes().replace(APPROVER.encode(), b"someone-else@example.invalid"))
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "awaiting_human_decision"
    assert "does not name round 1's diff approval" in stage.message


# -- 5. the human's choice ----------------------------------------------------------------------


def test_declining_ends_the_task_without_any_call(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, DECLINE, implementer_env=_never, reviewer_env=_never))
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "awaiting_human_decision" and stage.terminal
    assert "declined" in stage.message
    assert (env.repo / TARGET).read_bytes() == PROPOSED.encode("utf-8")
    for flags in (BEGIN, DECLINE, PREPARE):
        code, _, err = _continue(capsys, env, flags)
        assert code == 1 and "finished" in err
    assert len(env.implementer.requests) == 1


def test_declining_after_a_verification_failure_points_at_the_record(tmp_path, capsys):
    env = _env(tmp_path, reviews=(), proposals=(PROPOSED,), script=CONTENT_SCRIPT)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    assert _continue(capsys, env, APPLY)[0] == 2
    _ok(_continue(capsys, env, DECLINE))
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "awaiting_human_decision" and stage.terminal
    assert "04-review.exit-2.stdout" in stage.message
    assert task_run.SUMMARY_FILE not in stage.message
    assert env.reviewer.requests == [] and len(env.implementer.requests) == 1


def test_beginning_twice_or_declining_after_beginning_is_refused(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    record = (env.run_dir / task_run.CORRECTION_FILE).read_bytes()
    for flags in (BEGIN, DECLINE):
        code, _, err = _continue(capsys, env, flags)
        assert code == 1 and "accepts exactly" in err
    assert (env.run_dir / task_run.CORRECTION_FILE).read_bytes() == record
    assert not (env.run_dir / task_run.CORRECTION_DECLINED_FILE).exists()


def test_both_begin_and_decline_records_fail_closed(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    (env.run_dir / task_run.CORRECTION_DECLINED_FILE).write_text("{}", encoding="utf-8")
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "correction_records_inconsistent" and stage.terminal


def test_a_correction_record_without_a_round1_result_fails_closed(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _to_diff_approval(capsys, env)
    (env.run_dir / task_run.CORRECTION_FILE).write_text("{}", encoding="utf-8")
    assert _stage(env) == "correction_records_inconsistent"


# -- 6. baseline binding ------------------------------------------------------------------------


def test_prepare_refuses_a_dirty_workspace_even_with_the_target_restored(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    (env.repo / "src" / "other.py").write_text("OTHER = 2\n", encoding="utf-8")
    code, _, _ = _continue(capsys, env, PREPARE)
    assert code == 1
    assert _r2_drafts(env) == [] and _stage(env) == "round2_restore_pending"


def test_prepare_refuses_a_moved_head(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    (env.repo / "src" / "other.py").write_text("OTHER = 2\n", encoding="utf-8")
    _git(env.repo, "commit", "-q", "-am", "moved")
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 1 and "correction_baseline_mismatch" in err and "workspace_head_object_id" in err
    assert _r2_drafts(env) == [] and _stage(env) == "round2_restore_pending"
    assert len(env.implementer.requests) == 1


def test_prepare_refuses_a_committed_candidate_as_the_baseline(tmp_path, capsys):
    # The human committed the round-1 candidate instead of restoring it: HEAD and
    # source both differ, and AIDO never silently re-baselines.
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _git(env.repo, "commit", "-q", "-am", "candidate")
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 1 and "correction_baseline_mismatch" in err
    assert "source_sha256" in err and "workspace_head_object_id" in err
    assert _r2_drafts(env) == []


def _library_inputs(env):
    project = env.project()
    plan = parse_approved_l1_plan_artifact((env.run_dir / task_run.PLAN_APPROVED_FILE).read_text(encoding="utf-8"))
    return project, plan


def _correction(env, **baseline_overrides):
    evidence, _ = task_run.round2_context(_task(env))
    correction = task_correction.correction_input(evidence, env.project())
    if baseline_overrides:
        baseline = correction.baseline.model_copy(update=baseline_overrides)
        correction = correction.model_copy(update={"baseline": baseline})
    return correction


def test_the_library_refuses_a_source_digest_that_is_not_the_baseline(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    project, plan = _library_inputs(env)
    ledger_before = _ledger_names(env)
    for override in ({"source_sha256": "0" * 64}, {"source_bytes": 1}, {"workspace_head_object_id": "0" * 40}):
        with pytest.raises(SupervisedImplementerRefused) as caught:
            live.prepare_supervised_implementation(
                project=project, approved_plan=plan, target_path=TARGET,
                evidence_dir=str(env.run_dir / task_run.EVIDENCE_DIR),
                correction=_correction(env, **override),
            )
        assert caught.value.category == "correction_baseline_mismatch"
        assert next(iter(override)) in str(caught.value)
    assert _ledger_names(env) == ledger_before  # refused before any issuance


def test_the_library_refuses_a_correction_that_still_names_the_workspace(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    project, plan = _library_inputs(env)
    correction = _correction(env)
    leaky = correction.model_copy(update={"previous_approved_diff": "see " + str(env.repo).upper()})
    with pytest.raises(SupervisedImplementerRefused) as caught:
        live.prepare_supervised_implementation(
            project=project, approved_plan=plan, target_path=TARGET,
            evidence_dir=str(env.run_dir / task_run.EVIDENCE_DIR), correction=leaky,
        )
    assert caught.value.category == "correction_contains_workspace_path"


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_head_object_id", "0" * 40),
        ("source_sha256", "0" * 64),
        ("source_bytes", 3),
        ("approved_plan_sha256", "1" * 64),
        ("project_config_sha256", "2" * 64),
        ("evidence_dir_sha256", "3" * 64),
        ("authorization_ledger_dir_sha256", "4" * 64),
        ("issue_number", 8),
        ("target_path", "src/other.py"),
    ],
)
def test_a_round2_authorization_that_differs_from_round1_is_never_offered(tmp_path, capsys, field, value):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _to_round2_consent(capsys, env)
    path = _r2_drafts(env)[0]
    document = json.loads(path.read_text(encoding="utf-8"))
    document["bound"][field] = value
    document["bound"]["binding_sha256"] = la.compute_binding_sha256(document["bound"])
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_correction_baseline_mismatch" and stage.terminal
    assert field in stage.message
    _consent2(env)
    code, _, _ = _continue(capsys, env, IMPLEMENT)
    assert code == 1
    assert len(env.implementer.requests) == 1


@pytest.mark.parametrize("field,value", [("model", "other-model"), ("provider", "vllm"), ("candidate", "SUP-X")])
def test_a_round2_authorization_with_another_model_identity_is_refused(tmp_path, capsys, field, value):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _to_round2_consent(capsys, env)
    path = _r2_drafts(env)[0]
    document = json.loads(path.read_text(encoding="utf-8"))
    document["bound"][field] = value
    document["bound"]["binding_sha256"] = la.compute_binding_sha256(document["bound"])
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    assert _stage(env) == "round2_correction_baseline_mismatch"
    assert task_correction.round2_binding_problem(str(path), _first_bound(env)) is not None


# -- 7. fresh authorization, single use and replay ---------------------------------------------


def test_round1s_consumed_authorization_cannot_stand_in_for_round2(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    shutil.copyfile(env.run_dir / "20-authorization-1.json", env.run_dir / "50-authorization-1.json")
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_evidence_inconsistent" and stage.terminal
    assert "round 1's implementer run" in stage.message
    code, _, _ = _continue(capsys, env, IMPLEMENT)
    assert code == 1
    # Even passed straight to P1B with the correction, the ledger refuses it.
    project, plan = _library_inputs(env)
    with pytest.raises(SupervisedImplementerRefused):
        live.run_supervised_implementation(
            project=project, approved_plan=plan,
            authorization_bytes=(env.run_dir / "20-authorization-1.json").read_bytes(),
            evidence_dir=str(env.run_dir / task_run.EVIDENCE_DIR),
            read_env=_reader(), announce=lambda notice: None, correction=_correction(env),
            _inner_transport_factory=env.implementer.factory,
        )
    assert len(env.implementer.requests) == 1


def test_an_unspent_round1_authorization_cannot_carry_a_correction(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    from test_task_coordinator import _approve_plan, _start

    _start(capsys, env)
    _approve_plan(env)
    _ok(_continue(capsys, env, PREPARE))
    _ok(_continue(capsys, env, PREPARE))  # 20-authorization-2.json is the one used
    spare = env.run_dir / "20-authorization-1.json"
    _consent(env)
    _ok(_continue(capsys, env, IMPLEMENT))
    _approve_diff(env)
    _continue(capsys, env, APPLY)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    _consent2(env, spare)  # still unspent in the ledger
    shutil.copyfile(spare, env.run_dir / "50-authorization-1.json")
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_correction_baseline_mismatch"
    assert "binds round 1's request" in stage.message
    project, plan = _library_inputs(env)
    with pytest.raises(SupervisedImplementerRefused) as caught:
        live.run_supervised_implementation(
            project=project, approved_plan=plan, authorization_bytes=spare.read_bytes(),
            evidence_dir=str(env.run_dir / task_run.EVIDENCE_DIR), read_env=_never,
            announce=lambda notice: None, correction=_correction(env),
            _inner_transport_factory=env.implementer.factory,
        )
    assert caught.value.category == "authorization_mismatch" and "request_sha256" in str(caught.value)
    assert len(env.implementer.requests) == 1


def test_a_round2_authorization_without_its_correction_is_refused_unconsumed(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_consent(capsys, env)
    _consent2(env)
    project, plan = _library_inputs(env)
    ledger_before = _ledger_names(env)
    for correction in (None, _correction(env).model_copy(update={"previous_approved_diff": "--- other\n"})):
        with pytest.raises(SupervisedImplementerRefused) as caught:
            live.run_supervised_implementation(
                project=project, approved_plan=plan,
                authorization_bytes=_r2_drafts(env)[0].read_bytes(),
                evidence_dir=str(env.run_dir / task_run.EVIDENCE_DIR), read_env=_never,
                announce=lambda notice: None, correction=correction,
                _inner_transport_factory=env.implementer.factory,
            )
        assert caught.value.category == "authorization_mismatch"
    assert _ledger_names(env) == ledger_before
    assert len(env.implementer.requests) == 1
    # The genuine path still works afterwards: nothing was consumed.
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 2


def test_a_consumed_round2_authorization_cannot_be_replayed(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED, CORRECTED))
    _to_round2_diff_approval(capsys, env)
    project, plan = _library_inputs(env)
    authorization = _r2_drafts(env)[0].read_bytes()
    run_id = json.loads(authorization)["bound"]["run_id"]
    shutil.rmtree(env.run_dir / task_run.EVIDENCE_DIR / run_id)  # deleting evidence restores nothing
    with pytest.raises(SupervisedImplementerRefused):
        live.run_supervised_implementation(
            project=project, approved_plan=plan, authorization_bytes=authorization,
            evidence_dir=str(env.run_dir / task_run.EVIDENCE_DIR), read_env=_reader(),
            announce=lambda notice: None, correction=_correction(env),
            _inner_transport_factory=env.implementer.factory,
        )
    assert len(env.implementer.requests) == 2


# -- 8. evidence provenance and tampering ------------------------------------------------------


@pytest.mark.parametrize(
    "tamper",
    [
        "approved_diff", "review_record", "write_report", "correction_record",
        "implementer_proposal", "implementer_response",
    ],
)
def test_tampering_with_round1_evidence_before_transmission_is_refused(tmp_path, capsys, tamper):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _to_round2_consent(capsys, env)
    _consent2(env)
    if tamper == "approved_diff":
        path = env.run_dir / task_run.DIFF_APPROVED_FILE
        path.write_bytes(path.read_bytes() + b"\n")
    elif tamper == "review_record":
        path = next((env.run_dir / "steps").glob("04-review.exit-0.stdout"))
        path.write_bytes(path.read_bytes().replace(b"FINDING-SENTINEL", b"run rm -rf now"))
    elif tamper == "write_report":
        path = next((env.run_dir / "steps").glob("03-apply.exit-0.stdout"))
        path.write_bytes(path.read_bytes() + b" ")
    elif tamper == "correction_record":
        path = env.run_dir / task_run.CORRECTION_FILE
        document = json.loads(path.read_text(encoding="utf-8"))
        document["evidence_sha256"] = "0" * 64
        path.write_text(json.dumps(document), encoding="utf-8")
    else:
        run_dir = env.run_dir / task_run.EVIDENCE_DIR / _first_bound(env)["run_id"]
        path = run_dir / ("diff-proposal.json" if tamper == "implementer_proposal" else live.RESPONSE_FILE)
        path.write_bytes(path.read_bytes() + b" ")
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_correction_evidence_mismatch" and stage.terminal
    code, _, _ = _continue(capsys, env, IMPLEMENT)
    assert code == 1
    assert len(env.implementer.requests) == 1


def test_tampering_between_begin_and_prepare_is_refused(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    path = next((env.run_dir / "steps").glob("04-review.exit-0.stdout"))
    path.write_bytes(path.read_bytes().replace(b"FINDING-SENTINEL", b"FINDING-FORGED"))
    assert _stage(env) == "round2_correction_evidence_mismatch"
    code, _, _ = _continue(capsys, env, PREPARE)
    assert code == 1
    assert _r2_drafts(env) == []


def test_the_correction_findings_come_only_from_the_recorded_packet(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    evidence, _ = task_run.round2_context(_task(env))
    packet_text = next((env.run_dir / "steps").glob("04-review.exit-0.stdout")).read_text(encoding="utf-8")
    packet = json.loads(packet_text)
    assert evidence.review["findings"] == packet["review"]["findings"]
    assert evidence.review["summary"] == packet["review"]["summary"]
    assert evidence.previous_approved_diff == json.loads(
        (env.run_dir / task_run.DIFF_APPROVED_FILE).read_text(encoding="utf-8")
    )["diff_proposal"]["changes"][0]["unified_diff"]


def test_a_secret_like_finding_is_redacted_in_transmission_only(tmp_path, capsys):
    # (A secret-like candidate line never reaches an approved diff: the P1A/5E3
    # generator already refuses it in round 1. A reviewer finding can carry one.)
    secret = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
    leaky_review = json.loads(json.dumps(CHANGES_REQUESTED))
    leaky_review["findings"][0]["suggested_action"] = f"Set api_key={secret} in the config."
    env = _env(tmp_path, reviews=(leaky_review, VALID_REVIEW))
    _to_round2_consent(capsys, env)
    _consent2(env)
    _ok(_continue(capsys, env, IMPLEMENT))
    sent = env.implementer.requests[1].content.decode("utf-8")
    assert secret not in sent
    correction = _user_payload(env.implementer.requests[1])["correction"]
    assert correction["redaction_note"].startswith("1 secret-like")
    # The recorded review packet keeps the original, byte-exact.
    assert secret in next((env.run_dir / "steps").glob("04-review.exit-0.stdout")).read_text(encoding="utf-8")


# -- 9. round-scoped approvals and records ------------------------------------------------------


def test_a_round1_approval_cannot_authorize_the_round2_write(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    shutil.copyfile(env.run_dir / task_run.DIFF_APPROVED_FILE, env.run_dir / task_run.ROUND_2.diff_approved_file)
    assert _stage(env) == "round2_apply_pending"
    before = _workspace(env.repo)
    code, _, err = _continue(capsys, env, APPLY)
    assert code == 1 and "outside its 'approval'" in err
    assert _workspace(env.repo) == before
    assert len(env.reviewer.requests) == 1


def test_round_scoped_records_never_cross(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    task = _task(env)
    first = task_run.consumed_implementer_run(task, task_run.ROUND_1)
    second = task_run.consumed_implementer_run(task, task_run.ROUND_2)
    assert first and second and first != second
    assert [os.path.basename(p) for p in task_run.authorization_paths(task, task_run.ROUND_1)] == ["20-authorization-1.json"]
    assert [os.path.basename(p) for p in task_run.authorization_paths(task, task_run.ROUND_2)] == ["50-authorization-1.json"]
    assert task_run._last(task, "review").step == "review"
    assert task_run._last(task, "review-r2") is None
    stage = task_run.derive_stage(task)
    assert stage.round_number == 2 and stage.evidence_run_dir == second


def test_the_round1_summary_does_not_block_the_final_summary(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    round1_summary = (env.run_dir / task_run.SUMMARY_FILE).read_bytes()
    _approve_diff2(env)
    _ok(_continue(capsys, env, APPLY))
    assert (env.run_dir / task_run.SUMMARY_FILE).read_bytes() == round1_summary
    assert (env.run_dir / task_run.ROUND_2.summary_file).exists()


# -- 10. interruption, partial failure and the strict limit ------------------------------------


def test_a_round2_implementer_failure_is_terminal_with_no_third_round(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _to_round2_consent(capsys, env)
    _consent2(env)
    env.implementer.respond = lambda request: httpx.Response(500, json={"error": "boom"})
    code, _, _ = _continue(capsys, env, IMPLEMENT)
    assert code == 4
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_implementer_failed" and stage.terminal
    assert "no further round" in stage.message
    for flags in (PREPARE, BEGIN, IMPLEMENT):
        assert _continue(capsys, env, flags)[0] == 1
    assert len(env.implementer.requests) == 2


def test_a_round2_no_change_reply_is_terminal(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED, ORIGINAL))
    _to_round2_consent(capsys, env)
    _consent2(env)
    _ok(_continue(capsys, env, IMPLEMENT))
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_no_change_proposed" and stage.terminal
    assert (env.repo / TARGET).read_bytes() == ORIGINAL.encode("utf-8")


def test_a_round2_changes_requested_verdict_is_terminal(tmp_path, capsys):
    env = _env(tmp_path, reviews=(CHANGES_REQUESTED, CHANGES_REQUESTED))
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    _ok(_continue(capsys, env, APPLY))
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_awaiting_human_decision" and stage.terminal
    summary = (env.run_dir / task_run.ROUND_2.summary_file).read_text(encoding="utf-8")
    assert "requested changes again" in summary
    code, _, err = _continue(capsys, env, BEGIN)
    assert code == 1 and "finished" in err
    assert len(env.implementer.requests) == 2


def test_a_round2_verification_failure_is_terminal_with_a_final_summary(tmp_path, capsys):
    env = _env(tmp_path, reviews=(VALID_REVIEW,), proposals=(PROPOSED, PROPOSED + "# still wrong\n"),
               script=CONTENT_SCRIPT)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    assert _continue(capsys, env, APPLY)[0] == 2
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    _ok(_continue(capsys, env, PREPARE))
    _consent2(env)
    _ok(_continue(capsys, env, IMPLEMENT))
    _approve_diff2(env)
    code, _, _ = _continue(capsys, env, APPLY)
    assert code == 2
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_verification_failed" and stage.terminal
    summary = (env.run_dir / task_run.ROUND_2.summary_file).read_text(encoding="utf-8")
    assert "NOT READY" in summary and "not contacted" in summary
    for flags in (REVIEW, BEGIN):
        assert _continue(capsys, env, flags)[0] == 1
    assert env.reviewer.requests == []


def test_a_round2_prewrite_refusal_can_be_retried(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    stray = env.repo / "src" / "stray.py"
    stray.write_text("STRAY = 1\n", encoding="utf-8")
    assert _continue(capsys, env, APPLY)[0] == 1
    assert _stage(env) == "round2_apply_pending"
    stray.unlink()
    _ok(_continue(capsys, env, APPLY))
    assert _stage(env) == "round2_awaiting_human_decision"


# -- 11. ALPHA-2B-T1-FU1: terminal reviewer failure and validated terminal evidence ---------------


def _r2_steps(env, kind: str, code=None):
    pattern = f"*-{kind}-r2.exit-{'*' if code is None else code}.stdout"
    return sorted((env.run_dir / "steps").glob(pattern))


def _r2_done(capsys, env):
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    _ok(_continue(capsys, env, APPLY))


def test_a_round1_reviewer_failure_is_still_retryable(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    env.reviewer.respond = lambda request: httpx.Response(200, json=_reviewer_reply({"verdict": "maybe"}))
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    assert _continue(capsys, env, APPLY)[0] == 4
    assert _stage(env) == "review_pending"
    env.reviewer.respond = lambda request: httpx.Response(200, json=_reviewer_reply(VALID_REVIEW))
    _ok(_continue(capsys, env, REVIEW))
    assert _stage(env) == "awaiting_human_decision"


def test_a_round2_reviewer_failure_is_terminal_and_never_retried(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    env.reviewer.respond = lambda request: httpx.Response(200, json=_reviewer_reply({"verdict": "maybe"}))
    before = len(env.reviewer.requests)
    assert _continue(capsys, env, APPLY)[0] == 4
    calls = len(env.reviewer.requests)
    assert calls > before
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_review_failed" and stage.terminal and stage.actions == {}
    assert "NO valid round-2 review" in stage.message
    env.reviewer.respond = lambda request: httpx.Response(200, json=_reviewer_reply(VALID_REVIEW))
    for flags in (REVIEW, APPLY, BEGIN, PREPARE):
        assert _continue(capsys, env, flags)[0] == 1
    assert len(env.reviewer.requests) == calls
    assert not (env.run_dir / task_run.ROUND_2.summary_file).exists()


def test_a_round2_reviewer_refusal_exit_1_is_terminal(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    env.reviewer.respond = lambda request: httpx.Response(200, json=_reviewer_reply({"verdict": "maybe"}))
    assert _continue(capsys, env, APPLY)[0] == 4
    for stream in ("stdout", "stderr"):
        old = next((env.run_dir / "steps").glob(f"*-review-r2.exit-4.{stream}"))
        old.rename(old.with_name(old.name.replace("exit-4", "exit-1")))
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_review_failed" and stage.terminal
    assert "refused" in stage.message


@pytest.mark.parametrize("review", [VALID_REVIEW, NEEDS_HUMAN, CHANGES_REQUESTED])
def test_valid_round2_verdicts_still_reach_the_terminal_state(tmp_path, capsys, review):
    env = _env(tmp_path, reviews=(CHANGES_REQUESTED, review))
    _r2_done(capsys, env)
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_awaiting_human_decision" and stage.terminal
    assert (env.run_dir / task_run.ROUND_2.summary_file).exists()


def test_a_malformed_round2_exit0_packet_is_not_a_completed_task(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    record = _r2_steps(env, "review", 0)[0]
    record.write_bytes(record.read_bytes()[:-40])
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_evidence_inconsistent" and stage.terminal
    assert "HUMAN INSPECTION" in stage.message


def test_a_round2_packet_for_another_approval_is_refused(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    record = _r2_steps(env, "review", 0)[0]
    record.write_bytes(record.read_bytes().replace(APPROVER.encode(), b"someone-else@example.invalid"))
    assert _stage(env) == "round2_evidence_inconsistent"


def test_a_round1_packet_cannot_stand_in_for_the_round2_review(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    round1 = next((env.run_dir / "steps").glob("*-review.exit-0.stdout"))
    _r2_steps(env, "review", 0)[0].write_bytes(round1.read_bytes())
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_evidence_inconsistent"


def test_a_mismatched_round2_write_report_is_refused(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    record = _r2_steps(env, "apply", 0)[0]
    record.write_bytes(record.read_bytes().replace(APPROVER.encode(), b"someone-else@example.invalid"))
    assert _stage(env) == "round2_evidence_inconsistent"


def test_a_round2_write_report_with_another_baseline_size_is_refused(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    record = _r2_steps(env, "apply", 0)[0]
    document = json.loads(record.read_text(encoding="utf-8"))
    document["target"]["pre_image_bytes"] += 1
    record.write_text(json.dumps(document), encoding="utf-8")
    assert _stage(env) == "round2_evidence_inconsistent"


def _r2_verification_failed(capsys, tmp_path):
    env = _env(tmp_path, reviews=(VALID_REVIEW,), proposals=(PROPOSED, PROPOSED + "# still wrong\n"),
               script=CONTENT_SCRIPT)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    assert _continue(capsys, env, APPLY)[0] == 2
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    _ok(_continue(capsys, env, PREPARE))
    _consent2(env)
    _ok(_continue(capsys, env, IMPLEMENT))
    _approve_diff2(env)
    assert _continue(capsys, env, APPLY)[0] == 2
    return env


def test_a_valid_round2_verification_failure_still_reaches_its_terminal_state(tmp_path, capsys):
    env = _r2_verification_failed(capsys, tmp_path)
    assert _stage(env) == "round2_verification_failed"


@pytest.mark.parametrize("tamper", ["malformed", "approval", "outcome", "untrusted"])
def test_an_invalid_round2_verification_report_is_refused(tmp_path, capsys, tamper):
    env = _r2_verification_failed(capsys, tmp_path)
    record = _r2_steps(env, "review", 2)[0]
    data = record.read_bytes()
    if tamper == "malformed":
        data = data[:-40]
    elif tamper == "approval":
        data = data.replace(APPROVER.encode(), b"someone-else@example.invalid")
    elif tamper == "outcome":
        data = data.replace(b'"verification-failed"', b'"verified"', 1)
    else:
        data = data.replace(b'"head_unchanged": true', b'"head_unchanged": false', 1)
    assert data != record.read_bytes()
    record.write_bytes(data)
    assert _stage(env) == "round2_evidence_inconsistent"


def test_tampering_after_the_final_summary_is_detected_on_the_next_status(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    assert (env.run_dir / task_run.ROUND_2.summary_file).exists()
    assert _stage(env) == "round2_awaiting_human_decision"
    record = _r2_steps(env, "review", 0)[0]
    record.write_bytes(record.read_bytes().replace(APPROVER.encode(), b"someone-else@example.invalid"))
    assert _stage(env) == "round2_evidence_inconsistent"
    _r2_steps(env, "apply", 0)[0].write_bytes(b"{}")
    assert _stage(env) == "round2_evidence_inconsistent"


def test_an_interrupted_round2_diff_draft_is_completed_or_refused(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    draft = env.run_dir / task_run.ROUND_2.diff_draft_file
    draft.unlink()  # as if interrupted after the diff text was written
    assert _stage(env) == "round2_diff_draft_pending"
    _ok(_continue(capsys, env, {}))
    assert draft.exists()
    draft.unlink()
    text = env.run_dir / task_run.ROUND_2.diff_text_file
    text.write_text(text.read_text(encoding="utf-8") + "+forged\n", encoding="utf-8")
    code, _, err = _continue(capsys, env, {})
    assert code == 1 and "not this round's proposed diff" in err
    assert not draft.exists()


def test_a_round2_runner_that_raises_needs_inspection(tmp_path, capsys, monkeypatch):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)

    def explode(**kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(cli, "_run_l2_apply_approved_file_edit", explode)
    assert _continue(capsys, env, APPLY)[0] == 1
    assert _stage(env) == "round2_write_needs_inspection"


def test_a_round2_step_without_a_begun_correction_fails_closed(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _round1_to_offer(capsys, env)
    steps = env.run_dir / "steps"
    (steps / "09-review-r2.exit-0.stdout").write_text("{}", encoding="utf-8")
    (steps / "09-review-r2.exit-0.stderr").write_text("", encoding="utf-8")
    assert _stage(env) == "correction_records_inconsistent"
    assert _continue(capsys, env, BEGIN)[0] == 1


def test_the_correction_modules_add_no_execution_surface():
    for module in (task_correction, sic):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "import subprocess", "import socket", "LLMClient(", "httpx", "os.system",
            "os.environ", "getenv", "git restore\"", "run_fixed_git_operation",
        ):
            assert forbidden not in source, (module.__name__, forbidden)
    # The coordinator never types a consent or approval value.
    source = Path(task_correction.__file__).read_text(encoding="utf-8")
    for phrase in ("I approve this", "consent_text", "CONSENT_TEXT", "PLAINTEXT_ACKNOWLEDGEMENT"):
        assert phrase not in source


def test_the_p1b_commands_gained_no_correction_option():
    import typer

    command = typer.main.get_command(cli.app)
    for name in ("l2-supervised-implementer-prepare", "l2-supervised-implementer-run"):
        declared = {opt for param in command.commands[name].params for opt in param.opts}
        assert not any("correction" in opt for opt in declared)


# -- 12. ALPHA-2B-T1-FU2: byte-exact integrity of the round-2 terminal records ------------------


def _integrity(env, kind: str, code=0) -> Path:
    stdout = _r2_steps(env, kind, code)[0]
    return stdout.with_name(stdout.name[: -len(".stdout")] + task_run.INTEGRITY_SUFFIX)


def _edit_keeping_everything_valid(record: Path, old: bytes, new: bytes, model) -> None:
    data = record.read_bytes()
    assert old in data
    edited = data.replace(old, new, 1)
    assert edited != data
    model.model_validate_json(edited)  # still schema-valid, identity untouched
    record.write_bytes(edited)


def test_round2_terminal_steps_carry_an_integrity_record_and_round1_does_not(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    for kind in ("apply", "review"):
        doc = json.loads(_integrity(env, kind).read_text(encoding="utf-8"))
        assert doc["schema_version"] == task_run.STEP_INTEGRITY_SCHEMA_VERSION
        assert doc["step"] == f"{kind}-r2"
    assert not list((env.run_dir / "steps").glob("*-review.exit-*.integrity.json"))
    assert not list((env.run_dir / "steps").glob("*-apply.exit-*.integrity.json"))
    assert _stage(env) == "round2_awaiting_human_decision"


def test_a_valid_different_round2_verdict_is_detected(tmp_path, capsys):
    from ai_dev_orchestrator.review import ReviewPacket

    env = _env(tmp_path, reviews=(CHANGES_REQUESTED, VALID_REVIEW))
    _r2_done(capsys, env)
    _edit_keeping_everything_valid(
        _r2_steps(env, "review", 0)[0],
        b'"verdict": "approve"',
        b'"verdict": "needs_human_review"',
        ReviewPacket,
    )
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_evidence_inconsistent" and "integrity record" in stage.message


@pytest.mark.parametrize(
    "old,new,reviews",
    [
        (b"FINDING-SENTINEL", b"FINDING-SENTINEM", (CHANGES_REQUESTED, CHANGES_REQUESTED)),
        (b"The rounding is unmarked", b"The rounding is unmarkEd", (CHANGES_REQUESTED, CHANGES_REQUESTED)),
    ],
    ids=["finding_text", "summary_text"],
)
def test_same_length_round2_reviewer_text_edits_are_detected(tmp_path, capsys, old, new, reviews):
    from ai_dev_orchestrator.review import ReviewPacket

    env = _env(tmp_path, reviews=reviews)
    _r2_done(capsys, env)
    record = _r2_steps(env, "review", 0)[0]
    size = record.stat().st_size
    _edit_keeping_everything_valid(record, old, new, ReviewPacket)
    assert record.stat().st_size == size
    assert _stage(env) == "round2_evidence_inconsistent"


def test_a_schema_valid_round2_write_report_edit_is_detected(tmp_path, capsys):
    from ai_dev_orchestrator.file_editing import WorkspaceWriteReport

    env = _env(tmp_path)
    _r2_done(capsys, env)
    _edit_keeping_everything_valid(
        _r2_steps(env, "apply", 0)[0], b'"line_ending": "lf"', b'"line_ending": "crlf"', WorkspaceWriteReport
    )
    assert _stage(env) == "round2_evidence_inconsistent"


def test_a_schema_valid_round2_verification_report_edit_is_detected(tmp_path, capsys):
    from ai_dev_orchestrator.verification import VerificationResultReport

    env = _r2_verification_failed(capsys, tmp_path)
    record = _r2_steps(env, "review", 2)[0]
    data = record.read_bytes()
    code = json.loads(data)["execution"]["return_code"]
    _edit_keeping_everything_valid(
        record, f'"return_code": {code}'.encode(), f'"return_code": {code + 5}'.encode(), VerificationResultReport
    )
    assert _stage(env) == "round2_evidence_inconsistent"


def test_a_rewritten_integrity_record_that_disagrees_is_detected(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    path = _integrity(env, "review")
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["stdout_sha256"] = "0" * 64
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert _stage(env) == "round2_evidence_inconsistent"


@pytest.mark.parametrize("kind", ["apply", "review"])
def test_an_incomplete_integrity_record_never_yields_a_completed_result(tmp_path, capsys, kind):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    _integrity(env, kind).unlink()  # as if interrupted before it was written
    assert _stage(env) == "round2_evidence_inconsistent"
    before = _workspace(env.repo)
    requests = (len(env.implementer.requests), len(env.reviewer.requests))
    for flags in (REVIEW, APPLY, BEGIN, PREPARE, IMPLEMENT):
        assert _continue(capsys, env, flags)[0] == 1
    assert _workspace(env.repo) == before
    assert (len(env.implementer.requests), len(env.reviewer.requests)) == requests


def test_an_unreadable_integrity_record_fails_closed(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    _integrity(env, "review").write_bytes(b"{")
    assert _stage(env) == "round2_evidence_inconsistent"


# -- 13. ALPHA-2B-T1-FU3: crash-safe round-2 attempt accounting ---------------------------------


class _Crash(BaseException):
    """A process death between a runner finishing and its record being complete."""


def _crash_on(monkeypatch, step: str, *, partial: bool = False):
    real = task_run.record_step

    def record(task, name, code, stdout, stderr):
        if name == step:
            if partial:  # the stdout stream lands, then the process dies
                base = os.path.join(task.path(task_run.STEPS_DIR), f"99-{name}.exit-{code}")
                Path(base + ".stdout").write_bytes(stdout.encode("utf-8"))
            raise _Crash()
        return real(task, name, code, stdout, stderr)

    monkeypatch.setattr(task_run, "record_step", record)
    return real


def _assert_nothing_more_can_run(capsys, env, stage_name="round2_attempt_incomplete"):
    stage = task_run.derive_stage(_task(env))
    assert stage.name == stage_name and stage.terminal and stage.actions == {}
    assert "HUMAN" in stage.message
    before = _workspace(env.repo)
    requests = (len(env.implementer.requests), len(env.reviewer.requests))
    records = _tree(env.run_dir)
    for flags in (REVIEW, APPLY, BEGIN, DECLINE, PREPARE, IMPLEMENT, {}):
        assert _continue(capsys, env, flags)[0] == 1
    assert _workspace(env.repo) == before  # nothing written and nothing restored
    assert (len(env.implementer.requests), len(env.reviewer.requests)) == requests
    assert _tree(env.run_dir) == records


def test_a_crash_after_the_round2_reviewer_but_before_any_record_blocks_a_second_review(
    tmp_path, capsys, monkeypatch
):
    env = _env(tmp_path, reviews=(CHANGES_REQUESTED, VALID_REVIEW, VALID_REVIEW))
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    _crash_on(monkeypatch, "review-r2")
    with pytest.raises(_Crash):
        _continue(capsys, env, APPLY)
    monkeypatch.undo()
    assert len(env.reviewer.requests) == 2  # round 1's + the one interrupted round-2 request
    assert not _r2_steps(env, "review")
    assert _r2_steps(env, "apply", 0)
    _assert_nothing_more_can_run(capsys, env)
    assert len(env.reviewer.requests) == 2


def test_a_round2_stdout_without_stderr_is_terminal_inconsistency(tmp_path, capsys):
    env = _env(tmp_path, reviews=(CHANGES_REQUESTED, VALID_REVIEW, VALID_REVIEW))
    _r2_done(capsys, env)
    stdout = _r2_steps(env, "review", 0)[0]
    stdout.with_name(stdout.name[: -len(".stdout")] + ".stderr").unlink()
    _integrity(env, "review").unlink()
    _assert_nothing_more_can_run(capsys, env)


def test_round2_streams_without_their_integrity_record_are_terminal(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    _integrity(env, "review").unlink()
    _assert_nothing_more_can_run(capsys, env, "round2_evidence_inconsistent")


def test_a_crash_while_recording_the_round2_write_authorizes_no_second_write_or_review(
    tmp_path, capsys, monkeypatch
):
    env = _env(tmp_path, reviews=(CHANGES_REQUESTED, VALID_REVIEW, VALID_REVIEW))
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    _crash_on(monkeypatch, "apply-r2", partial=True)
    with pytest.raises(_Crash):
        _continue(capsys, env, APPLY)
    monkeypatch.undo()
    assert (env.repo / TARGET).read_bytes() == CORRECTED.encode("utf-8")  # the write happened
    assert len(env.reviewer.requests) == 1  # only round 1's
    _assert_nothing_more_can_run(capsys, env)


def test_a_failed_attempt_marker_means_nothing_is_run(tmp_path, capsys, monkeypatch):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)

    def refuse(task, step):
        raise OSError("disk full")

    monkeypatch.setattr(task_run, "begin_attempt", refuse)
    monkeypatch.setattr(
        cli, "_run_l2_apply_approved_file_edit", lambda **kw: pytest.fail("the writer must not start")
    )
    before = _workspace(env.repo)
    code, _, err = _continue(capsys, env, APPLY)
    assert code == 1 and "Nothing was run" in err
    assert _workspace(env.repo) == before
    assert not _r2_steps(env, "apply")
    assert _stage(env) == "round2_apply_pending"


def test_each_round2_attempt_leaves_a_marker_and_round1_leaves_none(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    steps = sorted(os.listdir(env.run_dir / "steps"))
    assert [n for n in steps if ".begun-" in n] == ["apply-r2.begun-01", "review-r2.begun-01"]
    assert task_run.attempt_accounting_problem(_task(env)) is None
    assert _stage(env) == "round2_awaiting_human_decision"


def test_a_round2_record_without_a_begun_marker_is_refused(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    (env.run_dir / "steps" / "review-r2.begun-01").unlink()
    _assert_nothing_more_can_run(capsys, env)


def test_a_completed_round2_write_refusal_may_still_be_retried(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    stray = env.repo / "src" / "stray.py"
    stray.write_text("STRAY = 1\n", encoding="utf-8")
    assert _continue(capsys, env, APPLY)[0] == 1
    assert _stage(env) == "round2_apply_pending"
    assert task_run.attempt_accounting_problem(_task(env)) is None
    stray.unlink()
    _ok(_continue(capsys, env, APPLY))
    assert _stage(env) == "round2_awaiting_human_decision"


def test_a_round1_crash_still_leaves_the_accepted_alpha_2a_behavior(tmp_path, capsys, monkeypatch):
    env = _env(tmp_path, proposals=(PROPOSED,))
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    _ok(_continue(capsys, env, APPLY))
    assert not any(".begun-" in n for n in os.listdir(env.run_dir / "steps"))


# -- 14. ALPHA-2B-T1-FU3 closure: accounting is enforced BEFORE any nonterminal round-2 stage ----


def _interrupted_review_r2(tmp_path, capsys, monkeypatch):
    """A round-2 reviewer attempt that began and died before its record was complete."""
    env = _env(tmp_path, reviews=(CHANGES_REQUESTED, VALID_REVIEW, VALID_REVIEW))
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    _crash_on(monkeypatch, "review-r2")
    with pytest.raises(_Crash):
        _continue(capsys, env, APPLY)
    monkeypatch.undo()
    assert (env.run_dir / "steps" / "review-r2.begun-01").is_file()
    assert not _r2_steps(env, "review")
    return env


def _forget_tree(path: Path) -> None:
    import shutil
    import stat

    def writable(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=writable)


@pytest.mark.parametrize(
    "lost",
    [
        ("61-diff.approved.json",),
        ("60-diff.draft.json",),
        ("60-diff.draft.json", "61-diff.approved.json"),
    ],
    ids=["approved-diff", "draft-diff", "both-diffs"],
)
def test_an_interrupted_round2_review_stays_terminal_when_diff_evidence_is_lost(
    tmp_path, capsys, monkeypatch, lost
):
    env = _interrupted_review_r2(tmp_path, capsys, monkeypatch)
    for name in lost:
        (env.run_dir / name).unlink()
    # Previously this offered a diff-approval/draft action; no action may exist now.
    _assert_nothing_more_can_run(capsys, env)
    assert len(env.reviewer.requests) == 2  # round 1's + the interrupted round-2 request


def test_an_interrupted_round2_review_stays_terminal_when_the_authorization_is_lost(
    tmp_path, capsys, monkeypatch
):
    env = _interrupted_review_r2(tmp_path, capsys, monkeypatch)
    for path in task_run.authorization_paths(_task(env), task_run.ROUND_2):
        os.unlink(path)
    _assert_nothing_more_can_run(capsys, env)


def test_an_interrupted_round2_review_stays_terminal_when_its_implementer_evidence_is_lost(
    tmp_path, capsys, monkeypatch
):
    env = _interrupted_review_r2(tmp_path, capsys, monkeypatch)
    _, run_dir = task_run.consumed_authorization(_task(env), task_run.ROUND_2)
    _forget_tree(Path(run_dir))
    _assert_nothing_more_can_run(capsys, env)


def test_losing_both_the_authorization_and_the_diff_evidence_cannot_reopen_anything(
    tmp_path, capsys, monkeypatch
):
    env = _interrupted_review_r2(tmp_path, capsys, monkeypatch)
    for name in ("60-diff.draft.json", "61-diff.approved.json"):
        (env.run_dir / name).unlink()
    for path in task_run.authorization_paths(_task(env), task_run.ROUND_2):
        os.unlink(path)
    _assert_nothing_more_can_run(capsys, env)


def test_a_begun_round2_write_attempt_cannot_be_reopened_by_losing_the_approved_diff(
    tmp_path, capsys, monkeypatch
):
    env = _env(tmp_path, reviews=(CHANGES_REQUESTED, VALID_REVIEW, VALID_REVIEW))
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    _crash_on(monkeypatch, "apply-r2", partial=True)
    with pytest.raises(_Crash):
        _continue(capsys, env, APPLY)
    monkeypatch.undo()
    (env.run_dir / "61-diff.approved.json").unlink()
    _assert_nothing_more_can_run(capsys, env)


def test_losing_the_approved_diff_after_a_completed_round2_write_refusal_is_terminal(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    stray = env.repo / "src" / "stray.py"
    stray.write_text("STRAY = 1\n", encoding="utf-8")
    assert _continue(capsys, env, APPLY)[0] == 1
    assert _stage(env) == "round2_apply_pending"
    stray.unlink()
    (env.run_dir / "61-diff.approved.json").unlink()
    _assert_nothing_more_can_run(capsys, env)


def test_losing_the_approved_diff_after_a_finished_round2_is_terminal_not_reapprovable(tmp_path, capsys):
    env = _env(tmp_path)
    _r2_done(capsys, env)
    assert _stage(env) == "round2_awaiting_human_decision"
    (env.run_dir / "61-diff.approved.json").unlink()
    _assert_nothing_more_can_run(capsys, env)


def test_round2_pre_attempt_stages_are_unchanged_when_no_attempt_began(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    assert not any(".begun-" in n for n in os.listdir(env.run_dir / "steps"))
    (env.run_dir / "60-diff.draft.json").unlink()
    assert _stage(env) == "round2_diff_draft_pending"  # no attempt: drafts may still be recreated
