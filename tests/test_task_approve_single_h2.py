"""P0-UX-H2-SIMPLE — one-confirmation H2 consent, tested entirely offline.

Same synthetic setup as the coordinator and P0-UX1 suites: a Git repository
under pytest ``tmp_path``, a synthetic verification script, and
``httpx.MockTransport`` handlers for both models. No socket, no real model, no
real project, no real endpoint.

What is proven: a project that pins ``supervised_implementer.endpoint`` decides
H2 with exactly one typed ``approve``; the screen shows the complete pinned
destination, its environment match and the HTTP risk; the environment is
checked against the pinned destination (including ``/v1``) before display,
before recording and again by P1B before anything is consumed or sent;
mismatches, config changes, stale or altered drafts and records, expired
authorizations, cancels and rejects record or send nothing; approval alone
sends nothing; a decision never carries over to another run, authorization,
model, file or correction round; and a project without the pin keeps the
typed contract and its serialization byte-for-byte.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from test_task_approve import (
    ACCOUNT,
    CONSENT,
    BaseUrl,
    _approve,
    _auth,
    _forbid_runners,
    _ledger,
    _ok,
    _ok_approve,
    _plan_approved,
    _record,
    _rewrite,
)
from test_task_coordinator import (
    APPLY,
    BASE_URL,
    FAKE_KEY,
    HOST,
    IMPLEMENT,
    IMPLEMENTER_MODEL,
    PREPARE,
    TARGET,
    Env,
    _continue,
    _reader,
    _stage,
    _start,
    _tree,
    _workspace,
)
from test_task_correction_round import BEGIN, _env as _correction_env, _restore

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.models import ControlledReviewEndpointConfig, ProjectConfig
from ai_dev_orchestrator.supervised_implementer import live
from ai_dev_orchestrator.supervised_implementer import live_authorization as la
from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused
from ai_dev_orchestrator.task import approve
from ai_dev_orchestrator.task import run as task_run

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="the 5F2C writer is Windows-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
]

PINNED = {"scheme": "http", "host": HOST, "port": 8080, "base_path": "/v1"}
DECISION = "20-authorization-1.decision.json"
CONSENTED = "20-authorization-1.consented.json"


def _pin(env: Env, endpoint: dict | None = PINNED, **implementer) -> Env:
    """Rewrite the synthetic project config before the task starts."""
    document = yaml.safe_load(env.config.read_text(encoding="utf-8"))
    if endpoint is not None:
        document["supervised_implementer"]["endpoint"] = dict(endpoint)
    document["supervised_implementer"].update(implementer)
    env.config.write_text(yaml.safe_dump(document), encoding="utf-8")
    return env


def _pinned(tmp_path, **kw) -> Env:
    return _pin(Env(tmp_path), **kw)


def _to_consent(capsys, env) -> None:
    _plan_approved(capsys, env)
    _ok(_continue(capsys, env, PREPARE))
    assert _stage(env) == "implementer_consent"


def _to_diff(capsys, env) -> None:
    _to_consent(capsys, env)
    _ok_approve(capsys, env, ["approve"])
    _ok(_continue(capsys, env, IMPLEMENT))
    assert _stage(env) == "diff_approval"


def _env_with(base_url: str):
    def read(provider):
        return {**_reader()(provider), "AIDO_LITELLM_BASE_URL": base_url}

    return read


# -- 1. the one confirmation ---------------------------------------------------------------


def test_h2_takes_exactly_one_typed_approve_and_sends_only_at_task_continue(tmp_path, capsys, monkeypatch):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    draft_before = _auth(env).read_bytes()
    base_url = BaseUrl()
    called = _forbid_runners(monkeypatch)
    ledger = _ledger(env)

    (code, out, err), prompter = _approve(capsys, env, ["approve"], base_url=base_url)
    assert code == 0, err
    assert len(prompter.prompts) == 1  # one prompt, one typed answer
    assert "approve" in prompter.prompts[0] and "transmit" not in " ".join(prompter.prompts)
    assert base_url.calls == 2  # before the screen, and again before recording
    # Approval alone ran nothing, sent nothing, consumed nothing.
    assert called == [] and env.implementer.requests == [] and _ledger(env) == ledger
    assert not (env.run_dir / CONSENTED).exists()
    assert "APPROVED: recorded in " + DECISION in err

    record = _record(env.run_dir / DECISION)
    binding = record["binding"]
    assert record["decision"] == "approve" and record["account"] == ACCOUNT
    assert binding["confirmation"] == "single_approval"
    assert binding["endpoint_source"] == "project_config.supervised_implementer.endpoint"
    assert (binding["endpoint_scheme"], binding["endpoint_host"], binding["endpoint_port"], binding["endpoint_base_path"]) == (
        "http", HOST, 8080, "/v1"
    )
    assert binding["transport_tls"] is False and binding["endpoint_matched_environment"] is True
    # Truthful: no separately typed confirmations are claimed.
    assert "transmission_confirmed" not in binding and "plaintext_confirmed" not in binding
    # The record holds exactly the screen that was printed.
    assert binding["presented_screen"] in out
    assert binding["presented_screen_sha256"] == task_run.sha256_bytes(binding["presented_screen"].encode("utf-8"))

    monkeypatch.undo()
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 1
    assert str(env.implementer.requests[0].url) == f"{BASE_URL}/chat/completions"
    assert _auth(env).read_bytes() == draft_before
    consent = la.parse_authorization((env.run_dir / CONSENTED).read_bytes()).consent
    assert (consent.endpoint_scheme, consent.endpoint_host, consent.endpoint_port) == ("http", HOST, 8080)
    assert consent.consent_text == la.CONSENT_TEXT
    assert consent.plaintext_acknowledgement == la.PLAINTEXT_ACKNOWLEDGEMENT
    assert consent.consented_by == ACCOUNT and consent.consented_at == record["recorded_at"]
    assert _stage(env) == "diff_approval"

    # H3 stays its own separate decision.
    _ok_approve(capsys, env, ["approve"])
    _ok(_continue(capsys, env, APPLY))
    assert _stage(env) == "awaiting_human_decision"


def test_the_screen_discloses_the_destination_the_transmission_and_the_http_risk(tmp_path, capsys):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    bound = json.loads(_auth(env).read_text(encoding="utf-8"))["bound"]
    out, _ = _ok_approve(capsys, env, ["approve"])
    for expected in (
        f"http://{HOST}:8080/v1",
        f"scheme http, host {HOST}, port 8080, base path /v1",
        f"exactly http://{HOST}:8080/v1/chat/completions",
        "AIDO_LITELLM_BASE_URL matches this destination exactly",
        "NOT TLS-ENCRYPTED (plaintext http)",
        "PLAINTEXT HTTP: this source will be sent NOT TLS-ENCRYPTED",
        "including sending it NOT TLS-ENCRYPTED",
        "supervised implementer SUP-D",
        f"model {IMPLEMENTER_MODEL}",
        TARGET,
        bound["source_sha256"],
        f"request sha256 {bound['request_sha256']}",
        f"expires {bound['expires_at']}",
        "single use",
        "--transmit-approved-source --real-implementer",
    ):
        assert expected in out, expected
    assert "The endpoint is NOT shown here" not in out
    assert FAKE_KEY not in out  # never a key


def test_an_https_destination_is_shown_as_tls_and_needs_no_plaintext_acknowledgement(tmp_path, capsys):
    env = _pinned(tmp_path, endpoint={"scheme": "https", "host": HOST, "port": 443, "base_path": "/v1"})
    _to_consent(capsys, env)
    https = BaseUrl(f"https://{HOST}/v1")  # the default port is the explicit 443
    out, _ = _ok_approve(capsys, env, ["approve"], base_url=https)
    assert "transport: TLS (https)" in out and "PLAINTEXT HTTP" not in out
    assert _record(env.run_dir / DECISION)["binding"]["transport_tls"] is True
    _ok(_continue(capsys, env, IMPLEMENT, implementer_env=_env_with(f"https://{HOST}/v1")))
    assert len(env.implementer.requests) == 1
    consent = la.parse_authorization((env.run_dir / CONSENTED).read_bytes()).consent
    assert (consent.endpoint_scheme, consent.endpoint_port, consent.plaintext_acknowledgement) == ("https", 443, None)


# -- 2. cancel and reject ---------------------------------------------------------------------


@pytest.mark.parametrize("answers", [[""], [], [KeyboardInterrupt()], ["yes"], ["transmit"], ["Approve"], [f"http://{HOST}:8080"]])
def test_cancel_records_nothing(tmp_path, capsys, answers):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    before = _tree(env.run_dir)
    (code, _, err), prompter = _approve(capsys, env, answers)
    assert code == 1 and "No decision was recorded" in err
    assert len(prompter.prompts) == 1
    assert _tree(env.run_dir) == before and _stage(env) == "implementer_consent"
    assert env.implementer.requests == []


def test_reject_is_recorded_truthfully_and_ends_the_task(tmp_path, capsys, monkeypatch):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    _, err = _ok_approve(capsys, env, ["reject"])
    assert "REJECTED" in err and _stage(env) == "rejected"
    record = _record(env.run_dir / DECISION)
    assert record["decision"] == "reject" and record["binding"]["confirmation"] == "single_approval"
    called = _forbid_runners(monkeypatch)
    for flags in (IMPLEMENT, PREPARE, {}):
        assert _continue(capsys, env, flags)[0] == 1
    assert called == [] and env.implementer.requests == []
    assert not (env.run_dir / CONSENTED).exists()


# -- 3. the destination check --------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        None,
        f"http://{HOST}:8080",  # no /v1
        f"http://{HOST}:8080/v2",
        f"http://{HOST}:8080/v1/extra",
        f"http://{HOST}:9090/v1",
        f"http://{HOST}/v1",  # effective port 80
        f"https://{HOST}:8080/v1",
        f"http://other-gateway.invalid:8080/v1",
        f"http://user@{HOST}:8080/v1",
        f"http://{HOST}:8080/v1?x=1",
    ],
)
def test_an_environment_that_is_not_the_pinned_destination_shows_and_records_nothing(tmp_path, capsys, value):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    before = _tree(env.run_dir)
    (code, out, err), prompter = _approve(capsys, env, ["approve"], base_url=BaseUrl(value))
    assert code == 1 and "Nothing was recorded" in err
    assert prompter.prompts == [] and "DESTINATION" not in out  # refused before the screen
    assert _tree(env.run_dir) == before
    if value is not None:
        assert value not in out + err  # the environment's URL is never echoed


def test_an_environment_that_changes_while_displayed_records_nothing(tmp_path, capsys):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    before = _tree(env.run_dir)

    class Moving(BaseUrl):
        def __call__(self):
            self.calls += 1
            return BASE_URL if self.calls == 1 else f"http://{HOST}:8080/v2"

    (code, out, err), _ = _approve(capsys, env, ["approve"], base_url=Moving())
    assert code == 1 and "Nothing was recorded" in err and "DESTINATION" in out
    assert _tree(env.run_dir) == before


def test_a_trailing_slash_is_the_same_request_and_matches(tmp_path, capsys):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, ["approve"], base_url=BaseUrl(f"{BASE_URL}/"))


@pytest.mark.parametrize(
    "value, category",
    [
        (f"http://{HOST}:8080/v2", "endpoint_not_authorized"),  # same scheme, host and port
        (f"http://{HOST}:8080", "endpoint_not_authorized"),
        (f"http://{HOST}:9090/v1", "endpoint_not_authorized"),
    ],
)
def test_p1b_checks_the_pinned_destination_again_before_sending(tmp_path, capsys, value, category):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, ["approve"])
    ledger = _ledger(env)
    code, _, err = _continue(capsys, env, IMPLEMENT, implementer_env=_env_with(value))
    assert code == 1 and category in err and value not in err
    assert env.implementer.requests == [] and _ledger(env) == ledger  # unconsumed
    _ok(_continue(capsys, env, IMPLEMENT))  # the same consent still works with the right environment
    assert len(env.implementer.requests) == 1


def test_check_pinned_endpoint_compares_scheme_host_port_and_path():
    pinned = ControlledReviewEndpointConfig(**PINNED)
    for good in (BASE_URL, f"{BASE_URL}/"):
        live.check_pinned_endpoint(good, pinned)
    for bad in (
        f"http://{HOST}:8080",
        f"http://{HOST}:8080/V1",
        f"http://{HOST}:8080/v1/x",
        f"http://{HOST}:8081/v1",
        f"https://{HOST}:8080/v1",
        f"http://{HOST.upper()}x:8080/v1",
        f"http://u:p@{HOST}:8080/v1",
        f"http://{HOST}:8080/v1?q",
        12345,
    ):
        with pytest.raises(SupervisedImplementerRefused) as caught:
            live.check_pinned_endpoint(bad, pinned)
        assert caught.value.category in ("endpoint_not_authorized", "endpoint_invalid")
        assert str(bad) not in str(caught.value)


def test_a_pinned_http_destination_needs_allow_insecure_http(tmp_path, capsys):
    env = _pinned(tmp_path, allow_insecure_http=False)
    code, _, err = _start(capsys, env)  # task-start runs the live gate already
    assert code == 1 and "endpoint_plaintext_not_permitted" in err
    assert env.run_dir is None
    with pytest.raises(SupervisedImplementerRefused) as caught:
        live.check_supervised_implementer_live_gate(env.project().supervised_implementer)
    assert caught.value.category == "endpoint_plaintext_not_permitted"
    https = _pinned(tmp_path / "s", endpoint={**PINNED, "scheme": "https"}, allow_insecure_http=False)
    live.check_supervised_implementer_live_gate(https.project().supervised_implementer)


# -- 4. stale, altered, expired, changed -----------------------------------------------------------


def test_a_changed_config_refuses_approval_and_transmission(tmp_path, capsys):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    original = env.config.read_bytes()
    _pin(env, endpoint={**PINNED, "port": 9090})
    before = _tree(env.run_dir)
    (code, _, err), _ = _approve(capsys, env, ["approve"])
    assert code == 1 and _tree(env.run_dir) == before
    env.config.write_bytes(original)
    _ok_approve(capsys, env, ["approve"])
    _pin(env, endpoint={**PINNED, "base_path": "/v2"})
    assert _continue(capsys, env, IMPLEMENT)[0] == 1
    assert env.implementer.requests == []


def test_an_altered_draft_is_refused(tmp_path, capsys):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    _rewrite(_auth(env), lambda d: d["bound"].update(source_bytes=d["bound"]["source_bytes"] + 1))
    (code, _, err), prompter = _approve(capsys, env, ["approve"])
    assert code == 1 and prompter.prompts == [] and "Nothing was recorded" in err


def test_a_draft_changed_while_displayed_records_nothing(tmp_path, capsys):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    path = _auth(env)
    (code, _, err), _ = _approve(capsys, env, ["approve"], on_prompt=lambda n: path.write_bytes(path.read_bytes() + b"\n"))
    assert code == 1 and not (env.run_dir / DECISION).exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.update(endpoint_port=9090),
        lambda b: b.update(endpoint_base_path="/v2"),
        lambda b: b.update(endpoint_host="other.invalid"),
        lambda b: b.update(transport_tls=True),
        lambda b: b.update(model="minimax-m3", candidate="SUP-M3"),
        lambda b: b.update(target_path="src/other.py"),
        lambda b: b.update(presented_screen=b["presented_screen"] + " "),
        lambda b: b.update(endpoint_matched_environment=False),
        lambda b: b.pop("confirmation"),
        lambda b: b.update(transmission_confirmed=True),
    ],
)
def test_an_altered_decision_record_is_refused_and_sends_nothing(tmp_path, capsys, mutate):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, ["approve"])
    _rewrite(env.run_dir / DECISION, lambda d: mutate(d["binding"]))
    code, _, _ = _continue(capsys, env, IMPLEMENT)
    assert code == 1 and env.implementer.requests == []
    assert not (env.run_dir / CONSENTED).exists()


def test_an_expired_authorization_can_be_neither_decided_nor_sent(tmp_path, capsys, monkeypatch):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    late = lambda: datetime.now(timezone.utc) + timedelta(minutes=61)  # noqa: E731
    base_url = BaseUrl()
    (code, _, err), prompter = _approve(capsys, env, ["approve"], clock=late, base_url=base_url)
    assert code == 1 and "expired" in err and prompter.prompts == [] and base_url.calls == 0
    _ok_approve(capsys, env, ["approve"])
    monkeypatch.setattr(task_run, "utc_now", late)
    monkeypatch.setattr(live, "_utc_now", late)
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 1 and "expired" in err and env.implementer.requests == []


# -- 5. no carry-over -----------------------------------------------------------------------------


def test_a_decision_does_not_carry_over_to_a_fresh_authorization(tmp_path, capsys):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    _ok_approve(capsys, env, ["approve"])
    _ok(_continue(capsys, env, PREPARE))  # re-issued before consumption
    assert _continue(capsys, env, IMPLEMENT)[0] == 1 and env.implementer.requests == []
    _ok_approve(capsys, env, ["approve"])
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 1


def test_a_decision_does_not_carry_over_to_another_run(tmp_path, capsys):
    first = _pinned(tmp_path / "a")
    _to_consent(capsys, first)
    _ok_approve(capsys, first, ["approve"])
    second = _pinned(tmp_path / "b")
    _to_consent(capsys, second)
    shutil.copy(first.run_dir / DECISION, second.run_dir / DECISION)
    assert _stage(second) == "decision_record_invalid"
    assert _continue(capsys, second, IMPLEMENT)[0] == 1 and second.implementer.requests == []


def test_a_typed_record_from_the_old_contract_is_refused_in_a_pinned_run(tmp_path, capsys):
    typed = Env(tmp_path / "typed")
    _to_consent(capsys, typed)
    _ok_approve(capsys, typed, CONSENT)
    pinned = _pinned(tmp_path / "pinned")
    _to_consent(capsys, pinned)
    record = _record(typed.run_dir / DECISION)
    draft = _auth(pinned).read_bytes()
    bound = json.loads(draft)["bound"]
    # Re-aim the typed record at the pinned run so only its SHAPE differs.
    record.update(run_id=pinned.run_dir.name, project_config_sha256=task_run.load_task(str(pinned.run_dir)).project_config_sha256)
    record["recorded_at"] = bound["prepared_at"]
    record["presented"] = {"file": _auth(pinned).name, "sha256": task_run.sha256_bytes(draft), "size": len(draft)}
    record["binding"].update(
        p1b_run_id=bound["run_id"], binding_sha256=bound["binding_sha256"], request_sha256=bound["request_sha256"],
        prepared_at=bound["prepared_at"], expires_at=bound["expires_at"], source_sha256=bound["source_sha256"],
    )
    (pinned.run_dir / DECISION).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    assert _continue(capsys, pinned, IMPLEMENT)[0] == 1 and pinned.implementer.requests == []


def test_the_correction_round_uses_the_same_single_approval_and_its_own_decision(tmp_path, capsys):
    env = _pin(_correction_env(tmp_path))
    _to_diff(capsys, env)
    _ok_approve(capsys, env, ["approve"])
    _continue(capsys, env, APPLY)
    assert _stage(env) == "correction_offered"
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    _ok(_continue(capsys, env, PREPARE))
    assert _stage(env) == "round2_implementer_consent"
    # Round 1's decision copied into round 2's place is refused.
    copied = env.run_dir / "50-authorization-1.decision.json"
    shutil.copy(env.run_dir / DECISION, copied)
    assert _stage(env) == "round2_decision_record_invalid"
    assert _continue(capsys, env, IMPLEMENT)[0] == 1 and len(env.implementer.requests) == 1
    copied.unlink()

    (code, out, err), prompter = _approve(capsys, env, ["approve"])
    assert code == 0, err
    assert len(prompter.prompts) == 1 and "correction data" in out and f"http://{HOST}:8080/v1" in out
    record = _record(copied)
    assert record["round"] == 2 and record["binding"]["confirmation"] == "single_approval"
    assert record["binding"]["p1b_run_id"] != _record(env.run_dir / DECISION)["binding"]["p1b_run_id"]
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 2 and _stage(env) == "round2_diff_approval"


# -- 6. backward compatibility ------------------------------------------------------------------


def test_a_config_without_the_pin_serializes_byte_identically_and_keeps_the_typed_h2(tmp_path, capsys):
    env = Env(tmp_path)
    data = env.project().model_dump(mode="json")
    assert "endpoint" not in data["supervised_implementer"]
    reloaded = ProjectConfig.model_validate(data).model_dump(mode="json")
    assert la.canonical_json_bytes(reloaded) == la.canonical_json_bytes(data)
    pinned = _pin(Env(tmp_path / "p")).project().model_dump(mode="json")
    assert pinned["supervised_implementer"]["endpoint"] == PINNED  # a pin is always bound
    _to_consent(capsys, env)
    out, _ = _ok_approve(capsys, env, CONSENT)
    assert "The endpoint is NOT shown here" in out
    binding = _record(env.run_dir / DECISION)["binding"]
    assert "confirmation" not in binding and binding["transmission_confirmed"] is True
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == 1


def test_the_typed_answers_do_not_apply_in_a_pinned_run(tmp_path, capsys):
    env = _pinned(tmp_path)
    _to_consent(capsys, env)
    (code, _, err), prompter = _approve(capsys, env, CONSENT)
    assert code == 0, err
    assert len(prompter.prompts) == 1
    assert prompter.answers == CONSENT[1:]  # never asked
