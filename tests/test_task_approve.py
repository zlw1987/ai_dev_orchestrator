"""P0-UX1 (D-2′) — interactive human approval, tested entirely offline.

Same synthetic setup as the coordinator suite: a Git repository under pytest
``tmp_path``, a synthetic verification script, and ``httpx.MockTransport``
handlers for both models. No socket, no real model, no real project.

What is proven: ``task-approve`` records exactly one write-once decision and
runs nothing; ``task-continue`` remains the only executor and re-validates the
decision before any consequential action; approve, reject and cancel are
distinct; the H2 endpoint must be typed by the human and match the environment
by P1B's rules, with separate transmission and plaintext confirmations; stale,
tampered, replayed, concurrent and mixed decisions fail closed; round 2 needs
its own decisions; interrupted serialization is resumed or refused, never
repaired; terminal text is escaped; the manual path is unchanged.
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_task_coordinator import (
    APPLY,
    BASE_URL,
    FAKE_KEY,
    HOST,
    IMPLEMENT,
    IMPLEMENTER_MODEL,
    PREPARE,
    REPO,
    REVIEW,
    REVIEWER_MODEL,
    TARGET,
    Env,
    _approve_plan,
    _consent,
    _continue,
    _invoke,
    _reader,
    _stage,
    _start,
    _tree,
    _workspace,
)
from test_task_correction_round import (
    BEGIN,
    _env as _correction_env,
    _restore,
    _round1_to_offer,
)

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.file_editing import parse_approved_diff_proposal_artifact
from ai_dev_orchestrator.file_editing.models import REQUIRED_DIFF_EDIT_APPROVAL_TEXT
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.handoff.models import parse_approved_l1_plan_artifact
from ai_dev_orchestrator.supervised_implementer import live_authorization as la
from ai_dev_orchestrator.task import approve
from ai_dev_orchestrator.task import run as task_run

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="the 5F2C writer is Windows-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
]

ACCOUNT = "aido-operator"
AUTHORITY = f"http://{HOST}:8080"
CONSENT = ["approve", AUTHORITY, "transmit", "plaintext"]
RUNNERS = (
    "_run_l2_supervised_implementer_prepare",
    "_run_l2_supervised_implementer_run",
    "_run_l2_apply_approved_file_edit",
    "_run_l2_review_approved_file_edit",
)


class Prompter:
    """Answers prompts in order; EOF after the last one. Records every prompt."""

    def __init__(self, answers, on_prompt=None) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.on_prompt = on_prompt

    def __call__(self, text: str) -> str:
        self.prompts.append(text)
        if self.on_prompt is not None:
            self.on_prompt(len(self.prompts))
        if not self.answers:
            raise EOFError
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


class BaseUrl:
    def __init__(self, value=BASE_URL) -> None:
        self.value = value
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.value


def _approve(capsys, env: Env, answers, *, tty=True, clock=None, account=lambda: ACCOUNT, base_url=None, on_prompt=None, encoding="utf-8"):
    prompter = Prompter(answers, on_prompt)
    result = _invoke(
        capsys,
        cli._run_task_approve,
        run_dir=env.run_dir,
        prompt=prompter,
        is_tty=lambda: tty,
        clock=clock,
        account=account,
        read_base_url=base_url or BaseUrl(),
        encoding=encoding,
    )
    return result, prompter


def _ok(result):
    code, out, err = result
    assert code == 0, err
    return out, err


def _ok_approve(capsys, env, answers, **kw):
    (code, out, err), _ = _approve(capsys, env, answers, **kw)
    assert code == 0, err
    return out, err


def _forbid_runners(monkeypatch) -> list[str]:
    called: list[str] = []

    def make(name):
        def boom(**kwargs):
            called.append(name)
            raise AssertionError(f"{name} must not run")

        return boom

    for name in RUNNERS:
        monkeypatch.setattr(cli, name, make(name))
    return called


def _plan_approved(capsys, env) -> None:
    _ok(_start(capsys, env))
    _ok_approve(capsys, env, ["approve"])


def _to_consent(capsys, env) -> None:
    _plan_approved(capsys, env)
    _ok(_continue(capsys, env, PREPARE))
    assert _stage(env) == "implementer_consent"


def _to_diff(capsys, env) -> None:
    _to_consent(capsys, env)
    _ok_approve(capsys, env, CONSENT)
    _ok(_continue(capsys, env, IMPLEMENT))
    assert _stage(env) == "diff_approval"


def _auth(env, n=1, prefix="20") -> Path:
    return env.run_dir / f"{prefix}-authorization-{n}.json"


def _record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rewrite(path: Path, mutate) -> None:
    document = _record(path)
    mutate(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _ledger(env) -> list[str]:
    return sorted(p.name for p in (env.tmp / "ledger").iterdir())


# -- 1. the full interactive workflow ------------------------------------------------------


def test_a_task_runs_end_to_end_with_interactive_h1_h2_h3(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    moment = datetime.now(timezone.utc).replace(microsecond=0)

    _, err = _ok_approve(capsys, env, ["approve"], clock=lambda: moment)
    assert "APPROVED: recorded in 12-plan.decision.json" in err
    assert "--prepare-supervised-implementation" in err  # the next command, without memorizing it
    assert not (env.run_dir / task_run.PLAN_APPROVED_FILE).exists()
    assert _stage(env) == "plan_approval"
    _ok(_continue(capsys, env, PREPARE))
    frozen = (env.run_dir / task_run.PLAN_APPROVED_FILE).read_text(encoding="utf-8")
    parse_approved_l1_plan_artifact(frozen)
    assert json.loads(frozen)["approval"] == {
        "approved_by": ACCOUNT,
        "approved_at": moment.isoformat(timespec="seconds"),
        "approval_text": REQUIRED_APPROVAL_TEXT,
        "source": "manual",
    }

    draft_before = _auth(env).read_bytes()
    base_url = BaseUrl()
    out, err = _ok_approve(capsys, env, CONSENT, base_url=base_url)
    assert base_url.calls == 1
    assert "provider litellm, model qwen3.8-27b" in out and "src/mod.py" in out
    assert "NOT TLS-ENCRYPTED" in out and "--transmit-approved-source --real-implementer" in err
    assert env.implementer.requests == []
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 1
    assert _auth(env).read_bytes() == draft_before  # the draft is never rewritten
    consented = (env.run_dir / "20-authorization-1.consented.json").read_bytes()
    consent = la.parse_authorization(consented).consent
    assert consent.consented_by == ACCOUNT and consent.consent_text == la.CONSENT_TEXT
    assert consent.plaintext_acknowledgement == la.PLAINTEXT_ACKNOWLEDGEMENT
    assert (consent.endpoint_scheme, consent.endpoint_host, consent.endpoint_port) == ("http", HOST, 8080)
    evidence = env.run_dir / task_run.EVIDENCE_DIR / la.parse_authorization(consented).bound.run_id
    assert (evidence / "authorization.json").read_bytes() == consented

    out, err = _ok_approve(capsys, env, ["approve"])
    assert "@@" in out and "round(x, 2)" in out
    _ok(_continue(capsys, env, APPLY))
    assert _stage(env) == "awaiting_human_decision"
    diff = (env.run_dir / task_run.DIFF_APPROVED_FILE).read_text(encoding="utf-8")
    parse_approved_diff_proposal_artifact(diff)
    assert json.loads(diff)["approval"]["approval_text"] == REQUIRED_DIFF_EDIT_APPROVAL_TEXT
    assert len(env.reviewer.requests) == 1


# -- 2. recording runs nothing --------------------------------------------------------------


@pytest.mark.parametrize("stage", ["plan", "consent", "diff"])
def test_recording_a_decision_runs_nothing(tmp_path, capsys, monkeypatch, stage):
    env = Env(tmp_path)
    if stage == "plan":
        _ok(_start(capsys, env))
        answers, decision = ["approve"], task_run.PLAN_DECISION_FILE
    elif stage == "consent":
        _to_consent(capsys, env)
        answers, decision = CONSENT, "20-authorization-1.decision.json"
    else:
        _to_diff(capsys, env)
        answers, decision = ["approve"], task_run.ROUND_1.diff_decision_file
    called = _forbid_runners(monkeypatch)
    before_run, before_ws, before_ledger = _tree(env.run_dir), _workspace(env.repo), _ledger(env)
    requests = (len(env.implementer.requests), len(env.reviewer.requests))

    def unchanged_so_far(_n):
        assert _tree(env.run_dir) == before_run  # nothing before the confirmation

    (code, _, err), _ = _approve(capsys, env, answers, on_prompt=unchanged_so_far)
    assert code == 0, err
    after = _tree(env.run_dir)
    assert set(after) - set(before_run) == {decision}
    assert all(after[name] == data for name, data in before_run.items())
    assert called == [] and _workspace(env.repo) == before_ws and _ledger(env) == before_ledger
    assert (len(env.implementer.requests), len(env.reviewer.requests)) == requests


def test_a_decision_without_the_stage_flags_runs_nothing(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff(capsys, env)
    _ok_approve(capsys, env, ["approve"])
    before = _workspace(env.repo)
    for flags in ({}, REVIEW, IMPLEMENT, PREPARE):
        code, _, err = _continue(capsys, env, flags)
        assert code == 1 and "accepts exactly" in err
    assert _workspace(env.repo) == before and env.reviewer.requests == []


def test_task_approve_needs_a_terminal_and_shows_nothing_otherwise(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    before = _tree(env.run_dir)
    (code, out, err), prompter = _approve(capsys, env, ["approve"], tty=False)
    assert code == 1 and "interactive terminal" in err
    assert "Round totals" not in out and prompter.prompts == []
    assert _tree(env.run_dir) == before


# -- 3. approve, reject and cancel ------------------------------------------------------------


@pytest.mark.parametrize(
    "answers",
    [["cancel"], [""], [], [KeyboardInterrupt()], ["Approve"], ["yes"], [" reject it"]],
)
def test_cancel_records_nothing_and_changes_no_stage(tmp_path, capsys, answers):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    before = _tree(env.run_dir)
    (code, _, err), _ = _approve(capsys, env, answers)
    assert code == 1 and "No decision was recorded" in err
    assert _tree(env.run_dir) == before and _stage(env) == "plan_approval"
    _ok_approve(capsys, env, ["approve"])  # still decidable afterwards


@pytest.mark.parametrize(
    "answers",
    [
        ["approve", ""],
        ["approve", AUTHORITY, "no"],
        ["approve", AUTHORITY, "transmit"],
        ["approve", AUTHORITY, "transmit", "yes"],
    ],
)
def test_cancelling_any_consent_confirmation_records_nothing(tmp_path, capsys, answers):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    before = _tree(env.run_dir)
    (code, _, err), _ = _approve(capsys, env, answers)
    assert code == 1 and "No decision was recorded" in err
    assert _tree(env.run_dir) == before and _stage(env) == "implementer_consent"


@pytest.mark.parametrize("stage", ["plan", "consent", "diff"])
def test_reject_ends_the_task_and_cannot_be_bypassed(tmp_path, capsys, monkeypatch, stage):
    env = Env(tmp_path)
    if stage == "plan":
        _ok(_start(capsys, env))
    elif stage == "consent":
        _to_consent(capsys, env)
    else:
        _to_diff(capsys, env)
    base_url = BaseUrl()
    _, err = _ok_approve(capsys, env, ["reject"], base_url=base_url)
    assert "REJECTED" in err and base_url.calls == 0
    assert _stage(env) == "rejected"
    status = _invoke(capsys, cli._run_task_status, run_dir=env.run_dir)[1]
    assert "(terminal)" in status and "task-continue" not in status
    called = _forbid_runners(monkeypatch)
    before = _tree(env.run_dir), _workspace(env.repo), _ledger(env)
    for flags in (PREPARE, IMPLEMENT, APPLY, REVIEW, {}):
        code, _, err = _continue(capsys, env, flags)
        assert code == 1 and "finished" in err
    # A later hand edit cannot revive it either.
    if stage == "plan":
        _approve_plan(env)
    elif stage == "consent":
        _consent(env)
    assert _stage(env) == "rejected"
    assert _approve(capsys, env, ["approve"])[0][0] == 1
    assert called == []
    assert (_workspace(env.repo), _ledger(env)) == before[1:]


def test_a_rejection_contradicted_by_later_records_fails_closed(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    _ok_approve(capsys, env, ["reject"])
    (env.run_dir / task_run.PLAN_APPROVED_FILE).write_bytes(b"{}")
    assert _stage(env) == "decision_record_invalid"


# -- 4. the H2 endpoint -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    [
        f"http://wrong-host.invalid:8080",
        f"http://{HOST}:9090",
        f"https://{HOST}:8080",
        f"http://{HOST}",
        f"http://{HOST}:8080/v1",
        f"http://user@{HOST}:8080",
        f"{HOST}:8080",
    ],
)
def test_an_incorrect_typed_endpoint_records_nothing_and_reveals_nothing(tmp_path, capsys, typed):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    before = _tree(env.run_dir)
    (code, out, err), _ = _approve(capsys, env, ["approve", typed, "transmit", "plaintext"])
    assert code == 1 and "Nothing was recorded" in err
    assert _tree(env.run_dir) == before
    if HOST not in typed:
        assert HOST not in out + err


def test_the_endpoint_is_never_shown_before_it_is_typed(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    seen: list[str] = []
    _ok_approve(capsys, env, CONSENT, on_prompt=lambda n: seen.append(capsys.readouterr().out) if n <= 2 else None)
    assert HOST not in "".join(seen) and "8080" not in "".join(seen)


def test_a_missing_or_refused_environment_endpoint_records_nothing(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    before = _tree(env.run_dir)
    for value in (None, "http://user:pw@host.invalid:8080/v1", "ftp://host.invalid:21"):
        (code, _, err), _ = _approve(capsys, env, CONSENT, base_url=BaseUrl(value))
        assert code == 1 and "Nothing was recorded" in err
    assert _tree(env.run_dir) == before


def test_an_endpoint_changed_after_consent_is_refused_by_p1b_unconsumed(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, CONSENT)
    ledger = _ledger(env)

    def moved(provider):
        values = _reader()(provider)
        return {**values, "AIDO_LITELLM_BASE_URL": f"http://{HOST}:9090/v1"}

    code, _, err = _continue(capsys, env, IMPLEMENT, implementer_env=moved)
    assert code == 1 and "endpoint_not_consented" in err
    assert env.implementer.requests == [] and _ledger(env) == ledger


def test_a_tampered_consent_endpoint_is_still_refused_by_p1b(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, CONSENT)
    _rewrite(env.run_dir / "20-authorization-1.decision.json", lambda d: d["binding"].update(endpoint_port=9090))
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 1 and "endpoint_not_consented" in err
    assert env.implementer.requests == []


def test_an_expired_authorization_cannot_be_decided(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    late = lambda: datetime.now(timezone.utc) + timedelta(minutes=61)  # noqa: E731
    before = _tree(env.run_dir)
    (code, _, err), prompter = _approve(capsys, env, CONSENT, clock=late)
    assert code == 1 and "expired" in err and prompter.prompts == []
    assert _tree(env.run_dir) == before


def test_a_fresh_authorization_needs_its_own_consent_decision(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, CONSENT)
    _ok(_continue(capsys, env, PREPARE))  # re-issue before consumption
    assert _stage(env) == "implementer_consent"
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 1 and env.implementer.requests == []  # authorization 2 is undecided
    _ok_approve(capsys, env, CONSENT)
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 1


# -- 5. stale, tampered, replayed, concurrent and mixed decisions --------------------------------


def test_a_draft_changed_while_displayed_records_nothing(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    draft = env.run_dir / task_run.PLAN_DRAFT_FILE

    def touch(_n):
        draft.write_bytes(draft.read_bytes() + b"\n")  # same JSON, different bytes

    (code, _, err), _ = _approve(capsys, env, ["approve"], on_prompt=touch)
    assert code == 1 and "changed while it was displayed" in err
    assert not (env.run_dir / task_run.PLAN_DECISION_FILE).exists()


def test_a_second_decision_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    _ok_approve(capsys, env, ["approve"])
    first = (env.run_dir / task_run.PLAN_DECISION_FILE).read_bytes()
    (code, _, err), _ = _approve(capsys, env, ["reject"])
    assert code == 1 and "already records a decision" in err
    assert (env.run_dir / task_run.PLAN_DECISION_FILE).read_bytes() == first


def test_concurrent_decisions_record_exactly_one(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    task = task_run.load_task(str(env.run_dir))
    subject = approve.plan_subject(task)
    barrier = threading.Barrier(8)
    outcomes: list[str] = []

    def decide(choice):
        barrier.wait()
        try:
            approve.record_decision(task, subject, choice, now=datetime.now(timezone.utc), account=ACCOUNT)
            outcomes.append("ok")
        except task_run.TaskRefused:
            outcomes.append("refused")

    threads = [threading.Thread(target=decide, args=("approve" if i % 2 else "reject",)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["ok"] + ["refused"] * 7
    assert [p.name for p in env.run_dir.glob("12-plan.decision.json*")] == ["12-plan.decision.json"]


@pytest.mark.parametrize(
    "mutate,stage_after",
    [
        (lambda d: d["presented"].update(sha256="0" * 64), "plan_approval"),
        (lambda d: d["binding"].update(target_path="src/other.py"), "plan_approval"),
        (lambda d: d.update(recorded_at="2999-01-01T00:00:00+00:00"), "plan_approval"),
        (lambda d: d.update(project_config_sha256="0" * 64), "plan_approval"),
        (lambda d: d.update(stage="diff_approval"), "decision_record_invalid"),
        (lambda d: d.update(run_id="20990101T000000Z-deadbeef"), "decision_record_invalid"),
        (lambda d: d.update(extra=True), "decision_record_invalid"),
        (lambda d: d.update(decision="approved"), "decision_record_invalid"),
    ],
)
def test_a_tampered_plan_decision_runs_nothing(tmp_path, capsys, monkeypatch, mutate, stage_after):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    _ok_approve(capsys, env, ["approve"])
    _rewrite(env.run_dir / task_run.PLAN_DECISION_FILE, mutate)
    assert _stage(env) == stage_after
    called = _forbid_runners(monkeypatch)
    code, _, _ = _continue(capsys, env, PREPARE)
    assert code == 1 and called == []
    assert not (env.run_dir / task_run.PLAN_APPROVED_FILE).exists()


def test_a_duplicate_key_decision_fails_closed(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    _ok_approve(capsys, env, ["approve"])
    path = env.run_dir / task_run.PLAN_DECISION_FILE
    path.write_text(path.read_text(encoding="utf-8").replace('"decision": "approve"', '"decision": "reject", "decision": "approve"'), encoding="utf-8")
    assert _stage(env) == "decision_record_invalid"


def test_a_decision_replayed_from_another_run_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    _ok_approve(capsys, env, ["approve"])
    first = env.run_dir
    _ok(_start(capsys, env))
    env.run_dir = next(path for path in env.runs_root.iterdir() if path != first)
    assert env.run_dir != first
    shutil.copy(first / task_run.PLAN_DECISION_FILE, env.run_dir / task_run.PLAN_DECISION_FILE)
    assert _stage(env) == "decision_record_invalid"
    assert _continue(capsys, env, PREPARE)[0] == 1


@pytest.mark.parametrize("field,value", [("plaintext_confirmed", False), ("transmission_confirmed", False), ("endpoint_matched_environment", False)])
def test_a_consent_decision_missing_a_confirmation_sends_nothing(tmp_path, capsys, field, value):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, CONSENT)
    _rewrite(env.run_dir / "20-authorization-1.decision.json", lambda d: d["binding"].update({field: value}))
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 1 and env.implementer.requests == []
    assert not (env.run_dir / "20-authorization-1.consented.json").exists()


def test_hand_editing_after_an_interactive_decision_is_refused(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    _ok_approve(capsys, env, ["approve"])
    _approve_plan(env)  # a contradictory hand edit
    called = _forbid_runners(monkeypatch)
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 1 and "edited by hand" in err and called == []


def test_an_interactive_decision_after_a_hand_edit_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _consent(env)
    (code, _, err), _ = _approve(capsys, env, CONSENT)
    assert code == 1 and "edited by hand" in err
    assert not (env.run_dir / "20-authorization-1.decision.json").exists()


def test_a_control_character_account_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    (code, _, err), _ = _approve(capsys, env, ["approve"], account=lambda: "evil\x1b[2Kname")
    assert code == 1 and not (env.run_dir / task_run.PLAN_DECISION_FILE).exists()


# -- 6. interrupted serialization -------------------------------------------------------------


def test_an_interrupted_consent_serialization_resumes_once(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, CONSENT)
    task = task_run.load_task(str(env.run_dir))
    # As if task-continue stopped after serializing, before transmission.
    approve.authorization_for_run(task, task_run.ROUND_1, now=task_run.utc_now())
    (env.run_dir / "20-authorization-1.consented.json.0123456789abcdef.tmp").write_bytes(b"partial")
    assert env.implementer.requests == []
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 1
    assert _stage(env) == "diff_approval"


def test_a_mismatched_or_orphaned_consented_file_sends_nothing(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    consented = env.run_dir / "20-authorization-1.consented.json"
    consented.write_bytes(b"{}")
    code, _, err = _continue(capsys, env, IMPLEMENT)  # no decision: orphaned
    assert code == 1 and "without its decision" in err
    consented.unlink()
    _ok_approve(capsys, env, CONSENT)
    consented.write_bytes(b"{}")  # a partial or foreign serialization
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 1 and "never replaced" in err
    assert env.implementer.requests == [] and consented.read_bytes() == b"{}"


def test_an_interrupted_plan_freeze_resumes(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    _ok_approve(capsys, env, ["approve"])
    task_run.freeze_plan_approval(task_run.load_task(str(env.run_dir)))  # frozen, prepare not run
    _ok(_continue(capsys, env, PREPARE))
    assert _stage(env) == "implementer_consent"


# -- 7. round 2 ------------------------------------------------------------------------------------


def _to_round2_consent_interactive(capsys, env) -> None:
    _round1_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    _ok(_continue(capsys, env, PREPARE))
    assert _stage(env) == "round2_implementer_consent"


def test_round2_needs_its_own_decisions_and_reuses_nothing_from_round1(tmp_path, capsys):
    env = _correction_env(tmp_path)
    _round1_interactive_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    _ok(_continue(capsys, env, PREPARE))
    assert _stage(env) == "round2_implementer_consent"
    # Round 1's consent decision copied into round 2's place is refused.
    record = env.run_dir / "50-authorization-1.decision.json"
    shutil.copy(env.run_dir / "20-authorization-1.decision.json", record)
    assert _stage(env) == "round2_decision_record_invalid"
    assert _continue(capsys, env, IMPLEMENT)[0] == 1 and len(env.implementer.requests) == 1
    record.unlink()

    out, _ = _ok_approve(capsys, env, CONSENT)
    assert "correction data" in out
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 2 and _stage(env) == "round2_diff_approval"
    shutil.copy(env.run_dir / task_run.ROUND_1.diff_decision_file, env.run_dir / "62-diff.decision.json")
    assert _stage(env) == "round2_decision_record_invalid"
    (env.run_dir / "62-diff.decision.json").unlink()
    out, _ = _ok_approve(capsys, env, ["approve"])
    assert "ORIGINAL baseline" in out
    _ok(_continue(capsys, env, APPLY))
    assert _stage(env) == "round2_awaiting_human_decision"


def test_a_round2_rejection_ends_the_correction_round(tmp_path, capsys, monkeypatch):
    env = _correction_env(tmp_path)
    _to_round2_consent_interactive(capsys, env)
    _ok_approve(capsys, env, ["reject"])
    assert _stage(env) == "round2_rejected"
    called = _forbid_runners(monkeypatch)
    for flags in (IMPLEMENT, PREPARE):
        assert _continue(capsys, env, flags)[0] == 1
    assert called == [] and len(env.implementer.requests) == 1


def _round1_interactive_to_offer(capsys, env) -> None:
    _to_diff(capsys, env)
    _ok_approve(capsys, env, ["approve"])
    _continue(capsys, env, APPLY)
    assert _stage(env) == "correction_offered"


def test_round1_interactive_decisions_carry_into_a_correction_round(tmp_path, capsys):
    env = _correction_env(tmp_path)
    _round1_interactive_to_offer(capsys, env)
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    _ok(_continue(capsys, env, PREPARE))
    assert _stage(env) == "round2_implementer_consent"
    assert _continue(capsys, env, IMPLEMENT)[0] == 1  # round 2 is undecided


# -- 8. terminal text -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "char,shown",
    [
        ("\x1b", "\\x1b"),
        ("\r", "\\x0d"),
        ("\x7f", "\\x7f"),
        ("\x9b", "\\x9b"),
        ("‮", "\\u202e"),
        ("⁦", "\\u2066"),
        ("​", "\\u200b"),
        ("﻿", "\\ufeff"),
        (" ", "\\u2028"),
    ],
)
def test_hidden_characters_are_shown_as_escapes(char, shown):
    text, count = approve.escape_terminal_text(f"a{char}b\n\tc", "utf-8")
    assert text == f"a{shown}b\n\tc" and count == 1


def test_undisplayable_characters_are_escaped_not_dropped():
    assert approve.escape_terminal_text("café", "ascii") == ("caf\\xe9", 1)
    assert approve.escape_terminal_text("café", "utf-8") == ("café", 0)


def test_model_controlled_diff_text_is_escaped_on_screen(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff(capsys, env)
    diff_path = env.run_dir / task_run.DIFF_TEXT_FILE
    task = task_run.load_task(str(env.run_dir))
    subject = approve.diff_subject(task, task_run.ROUND_1, _stage_dir(env))
    hostile = diff_path.read_bytes().replace(b"round(x, 2)", "round(x, 2)\x1b[2K‮".encode("utf-8"))
    rendered = approve.render_diff(task, subject, "utf-8", env.project())
    assert "\x1b" not in rendered and "NOTE:" not in rendered
    # Rendering reads the bound diff text: a hostile one is shown escaped.
    diff_path.write_bytes(hostile)
    rendered = approve.render_diff(task, subject, "utf-8", env.project())
    assert "\\x1b[2K\\u202e" in rendered and "\x1b" not in rendered and "‮" not in rendered
    assert "NOTE: 2 control" in rendered


def test_plan_text_is_escaped_on_screen(tmp_path, capsys):
    env = Env(tmp_path)
    code, _, err = _start(capsys, env, description="Round the total‮ to two places.\x1b[31m")
    if code != 0:
        pytest.skip(f"task-start refuses such a description itself: {err}")
    (code, out, err), _ = _approve(capsys, env, ["cancel"])
    assert "‮" not in out and "\x1b" not in out and "\\u202e" in out


def _stage_dir(env) -> str:
    return task_run.derive_stage(task_run.load_task(str(env.run_dir))).evidence_run_dir


# -- 9. compatibility and hygiene -------------------------------------------------------------------


def test_the_manual_path_records_no_decision(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    _approve_plan(env)
    _ok(_continue(capsys, env, PREPARE))
    _consent(env)
    _ok(_continue(capsys, env, IMPLEMENT))
    assert not list(env.run_dir.glob("*.decision.json")) and not list(env.run_dir.glob("*.consented.json"))


def test_task_approve_refuses_at_a_stage_with_nothing_to_decide(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    _ok_approve(capsys, env, ["approve"])
    _ok(_continue(capsys, env, PREPARE))
    _ok_approve(capsys, env, CONSENT)
    (code, _, err), _ = _approve(capsys, env, CONSENT)
    assert code == 1 and "already records a decision" in err


def test_the_approve_module_imports_no_process_socket_or_client():
    source = Path(approve.__file__).read_text(encoding="utf-8")
    for forbidden in ("import subprocess", "import socket", "LLMClient(", "httpx.Client(", "os.system", "HTTPTransport("):
        assert forbidden not in source


# -- 10. P0-UX1-T1-FU1: every H2 decision is accounted for by its own name ----------------------


def _frozen(env) -> tuple:
    return _tree(env.run_dir), _workspace(env.repo), _ledger(env)


def _nothing_continues(capsys, env, monkeypatch, *, implementer_requests: int) -> None:
    """No task-continue action can prepare, consume, send or run another stage."""
    called = _forbid_runners(monkeypatch)
    before = _frozen(env)
    for flags in (PREPARE, IMPLEMENT, APPLY, REVIEW, BEGIN, {}):
        code, _, err = _continue(capsys, env, flags)
        assert code == 1 and "finished" in err
    (code, _, _), _ = _approve(capsys, env, CONSENT)
    assert code == 1
    assert called == []
    assert _frozen(env) == before
    assert len(env.implementer.requests) == implementer_requests


def test_an_orphaned_rejection_cannot_revive_an_earlier_approved_authorization(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, CONSENT)  # 1. authorization 1 prepared and APPROVED
    _ok(_continue(capsys, env, PREPARE))  # 2. authorization 2 prepared (fresh, legitimate)
    assert _stage(env) == "implementer_consent"
    _ok_approve(capsys, env, ["reject"])  # 3. authorization 2 REJECTED
    assert _stage(env) == "rejected"
    _auth(env, 2).unlink()  # 4. only authorization 2's draft is removed
    assert (env.run_dir / "20-authorization-2.decision.json").is_file()
    assert _stage(env) == "decision_record_invalid"
    status = _invoke(capsys, cli._run_task_status, run_dir=env.run_dir)[1]
    assert "20-authorization-2.decision.json" in status and "is missing" in status
    _nothing_continues(capsys, env, monkeypatch, implementer_requests=0)  # 5.
    assert env.reviewer.requests == []
    # The run-time boundary refuses on its own as well, before anything is serialized.
    task = task_run.load_task(str(env.run_dir))
    with pytest.raises(task_run.TaskRefused, match="Nothing was sent"):
        approve.authorization_for_run(task, task_run.ROUND_1, now=task_run.utc_now())
    assert not (env.run_dir / "20-authorization-1.consented.json").exists()


def test_removing_a_rejected_draft_and_its_decision_cannot_revive_authorization_1(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, CONSENT)
    _ok(_continue(capsys, env, PREPARE))
    _ok_approve(capsys, env, ["reject"])
    _auth(env, 2).unlink()
    (env.run_dir / "20-authorization-2.decision.json").unlink()
    # Two prepare steps succeeded, but one draft remains: still refused.
    assert _stage(env) == "decision_record_invalid"
    _nothing_continues(capsys, env, monkeypatch, implementer_requests=0)


def test_a_missing_middle_draft_or_an_orphaned_consent_fails_closed(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _ok(_continue(capsys, env, PREPARE))
    _ok(_continue(capsys, env, PREPARE))
    moved = env.tmp / "aside.json"
    shutil.move(_auth(env, 2), moved)
    assert _stage(env) == "decision_record_invalid"  # drafts are 1 and 3: not 1..n
    shutil.move(moved, _auth(env, 2))
    assert _stage(env) == "implementer_consent"
    consented = env.run_dir / "20-authorization-1.consented.json"
    consented.write_bytes(b"{}")  # a consent of an older draft, with no decision
    assert _stage(env) == "decision_record_invalid"
    consented.unlink()
    assert _stage(env) == "implementer_consent"


@pytest.mark.parametrize(
    "name",
    ["20-authorization-2.decision.json.bak", "20-authorization-02.decision.json", "20-authorization-x.json"],
)
def test_an_unrecognised_authorization_record_name_fails_closed(tmp_path, capsys, name):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    (env.run_dir / name).write_bytes(b"{}")
    assert _stage(env) == "decision_record_invalid"
    assert _continue(capsys, env, IMPLEMENT)[0] == 1 and env.implementer.requests == []


def test_a_round2_orphaned_rejection_cannot_revive_round2_authorization_1(tmp_path, capsys, monkeypatch):
    env = _correction_env(tmp_path)
    _to_round2_consent_interactive(capsys, env)
    _ok_approve(capsys, env, CONSENT)  # round-2 authorization 1 APPROVED
    _ok(_continue(capsys, env, PREPARE))  # round-2 authorization 2
    assert _stage(env) == "round2_implementer_consent"
    _ok_approve(capsys, env, ["reject"])
    assert _stage(env) == "round2_rejected"
    _auth(env, 2, prefix="50").unlink()
    assert (env.run_dir / "50-authorization-2.decision.json").is_file()
    assert _stage(env) == "round2_decision_record_invalid"
    _nothing_continues(capsys, env, monkeypatch, implementer_requests=1)  # round 1's only
    task = task_run.load_task(str(env.run_dir))
    with pytest.raises(task_run.TaskRefused, match="Nothing was sent"):
        approve.authorization_for_run(task, task_run.ROUND_2, now=task_run.utc_now())


def test_a_round2_decision_before_the_round_was_begun_fails_closed(tmp_path, capsys):
    env = _correction_env(tmp_path)
    _round1_interactive_to_offer(capsys, env)
    shutil.copy(env.run_dir / "20-authorization-1.decision.json", env.run_dir / "50-authorization-1.decision.json")
    assert _stage(env) == "correction_records_inconsistent"
    assert _continue(capsys, env, BEGIN)[0] == 1


def test_a_fresh_authorization_before_a_rejection_still_works(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, CONSENT)
    _ok(_continue(capsys, env, PREPARE))
    _ok_approve(capsys, env, CONSENT)  # authorization 2 decided on its own
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 1 and _stage(env) == "diff_approval"
    assert (env.run_dir / "20-authorization-2.consented.json").is_file()
    assert not (env.run_dir / "20-authorization-1.consented.json").exists()


# -- 11. P0-UX1-T1-FU1: what each approval leads to is disclosed before it is recorded ------------


def _shown_before_first_answer(capsys, env) -> str:
    seen: list[str] = []
    _approve(capsys, env, ["cancel"], on_prompt=lambda n: seen.append(capsys.readouterr().out) if n == 1 else None)
    return seen[0]


def _on_disk(env) -> str:
    return str(Path(env.repo, *TARGET.split("/")))


def test_h1_shows_the_workspace_repository_target_task_and_plan_scope(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    shown = _shown_before_first_answer(capsys, env)
    for expected in (str(env.repo), REPO, TARGET, _on_disk(env), "Round totals", "----- the complete plan"):
        assert expected in shown, expected
    assert "sends nothing" in shown and "H2" in shown


def test_h2_shows_the_workspace_and_source_scope_but_not_the_endpoint(tmp_path, capsys):
    env = Env(tmp_path)
    _to_consent(capsys, env)
    shown = _shown_before_first_answer(capsys, env)
    for expected in (str(env.repo), _on_disk(env), "exactly ONE file", IMPLEMENTER_MODEL):
        assert expected in shown, expected
    # The endpoint is still typed independently: no destination is shown.
    assert HOST not in shown and "8080" not in shown and "reviewer" not in shown.lower()
    assert FAKE_KEY not in shown


def test_h3_shows_the_write_verification_and_reviewer_consequences(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff(capsys, env)
    shown = _shown_before_first_answer(capsys, env)
    project = env.project()
    verification = project.controlled_verification
    for expected in (
        str(env.repo),
        _on_disk(env),
        "1. WRITE",
        "2. VERIFY",
        "NOT sandboxed",
        f"executable: {verification.executable}",
        *(f"[{i}] {arg}" for i, arg in enumerate(verification.args, start=1)),
        f"{verification.timeout_seconds} s",
        "3. REVIEW, only if verification passes",
        f"provider {project.controlled_review.provider}, model {REVIEWER_MODEL}",
        f"http host {HOST} port 8080",
        "NOT TLS-ENCRYPTED",
        "must match this scheme, host and port",
        "nothing is sent to the reviewer (verification will already have run)",
        "Never the full target file",
        "Redaction is a backstop",
        "----- the complete proposed diff",
    ):
        assert expected in shown, expected
    # Configuration is shown, never a credential or the environment's base URL.
    assert FAKE_KEY not in shown and BASE_URL not in shown


def test_h3_states_the_one_request_or_compact_retry_policy_from_config(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff(capsys, env)
    task = task_run.load_task(str(env.run_dir))
    subject = approve.diff_subject(task, task_run.ROUND_1, _stage_dir(env))
    project = env.project()
    review = project.controlled_review
    for retry, phrase in ((False, "in exactly one request"), (True, "in at most two requests")):
        changed = project.model_copy(
            update={"controlled_review": review.model_copy(update={"compact_retry_on_unusable_output": retry})}
        )
        assert phrase in approve.render_diff(task, subject, "utf-8", changed)


def test_hostile_configured_values_are_escaped_on_screen(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff(capsys, env)
    task = task_run.load_task(str(env.run_dir))
    subject = approve.diff_subject(task, task_run.ROUND_1, _stage_dir(env))
    project = env.project()
    hostile = project.model_copy(
        update={
            "controlled_verification": project.controlled_verification.model_copy(
                update={"args": ["--ok\x1b[2K‮"]}
            )
        }
    )
    rendered = approve.render_diff(task, subject, "utf-8", hostile)
    assert "\x1b" not in rendered and "‮" not in rendered
    assert "--ok\\x1b[2K\\u202e" in rendered and "NOTE: 2 control" in rendered


def test_the_disclosure_comes_only_from_the_pinned_config(tmp_path, capsys):
    env = Env(tmp_path)
    _ok(_start(capsys, env))
    task = task_run.load_task(str(env.run_dir))
    assert approve.pinned_project(task).repo.workspace_path == str(env.repo)
    env.config.write_text(env.config.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    with pytest.raises(task_run.TaskRefused, match="changed after this task started"):
        approve.pinned_project(task)
    before = _tree(env.run_dir)
    (code, out, _), prompter = _approve(capsys, env, ["approve"])
    assert code == 1 and prompter.prompts == [] and str(env.repo) not in out
    assert _tree(env.run_dir) == before
