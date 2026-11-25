"""P0-MODEL-1 — explicit model choice: SUP-M3 implementer and an M3 reviewer.

Everything here is offline. Workspaces are synthetic Git repositories under
pytest ``tmp_path``; every "model" is an ``httpx.MockTransport`` behind AIDO's
own shipped wrappers. No socket, no real model, no real key.

What is proved:

- the supervised registry is append-only: ``SUP-D`` = ``qwen3.8-27b`` is
  unchanged, and ``SUP-M3`` = ``minimax-m3`` is a separately named entry;
- a project selects ``SUP-M3`` only by naming that exact pair; every mixed,
  case-variant or neighbouring identity (``minimax-m3-thinking``) is refused;
- the selected pair is bound at H2 and is the model the one request carries;
- every strict record (authorization, offline and live provenance) refuses a
  mixed pair even when each value is individually permitted;
- an authorization prepared for one candidate never sends for another, and a
  server naming a different model in its reply substitutes nothing;
- the reviewer can be explicitly configured as ``minimax-m3`` with the strict
  review parser unchanged, while ``gpt-oss-20b`` configurations still work;
- end to end, the coordinator runs SUP-M3 + gpt-oss-20b and SUP-D + minimax-m3
  with exactly one implementer and one reviewer request, and no automatic
  retry, substitution, write or approval.

SUP-D byte-identity (default request and default project-config digests) is
proved by the existing pinned golden tests, which this change leaves untouched.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys

import httpx
import pytest
from review_fixtures import assert_preserved_verification_only
import yaml
from pydantic import ValidationError

import test_supervised_implementer as off
import test_supervised_implementer_live as lv
from test_cli_l2_review_approved_file_edit import (
    CHANGES_REQUESTED_JSON,
    ENDPOINT_LINES,
    VALID_REVIEW_JSON,
    _env as _review_env,
    _run as _review_run,
    _setup as _review_setup,
    _stdout_json,
)
from test_task_approve import CONSENT, _ok, _ok_approve, _plan_approved
from test_task_coordinator import (
    APPLY,
    IMPLEMENT,
    PREPARE,
    PROPOSED,
    VALID_REVIEW,
    Env as TaskEnv,
    Server,
    _continue,
    _stage,
)

from ai_dev_orchestrator import supervised_implementer as sup
from ai_dev_orchestrator.supervised_implementer import identity
from ai_dev_orchestrator.supervised_implementer import live
from ai_dev_orchestrator.supervised_implementer import live_authorization as la
from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerProvenance
from ai_dev_orchestrator.task import run as task_run

_windows_git = [
    pytest.mark.skipif(sys.platform != "win32", reason="the live path and 5F2C writer are Windows-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
]

M3_CANDIDATE = "SUP-M3"
M3_MODEL = "minimax-m3"
QWEN_MODEL = "qwen3.8-27b"
GPT_OSS_MODEL = "gpt-oss-20b"
DELIMITED = "delimited_file"


def _m3_completion(content_text: str = lv.PROPOSED, *, model: str = M3_MODEL, content=None) -> dict:
    return lv._completion(content_text, content=content, model=model)


def _m3_server(**kwargs) -> lv.FakeServer:
    return lv.FakeServer(lambda request: httpx.Response(200, json=_m3_completion(**kwargs)))


# -- 1. the registry -------------------------------------------------------------------


def test_the_registry_is_append_only_and_sup_d_is_unchanged():
    assert identity.SUPERVISED_CANDIDATE_ID == "SUP-D"
    assert identity.SUPERVISED_CANDIDATE_MODEL_IDS["SUP-D"] == QWEN_MODEL
    assert identity.SUPERVISED_CANDIDATE_M3_ID == M3_CANDIDATE
    assert identity.SUPERVISED_CANDIDATE_MODEL_IDS[M3_CANDIDATE] == M3_MODEL
    assert list(identity.SUPERVISED_CANDIDATE_MODEL_IDS) == ["SUP-D", M3_CANDIDATE]
    assert sup.SUPERVISED_CANDIDATE_M3_ID == M3_CANDIDATE
    with pytest.raises(TypeError):
        identity.SUPERVISED_CANDIDATE_MODEL_IDS["SUP-M3"] = QWEN_MODEL  # type: ignore[index]


@pytest.mark.parametrize(
    "candidate, model",
    [("SUP-D", QWEN_MODEL), (M3_CANDIDATE, M3_MODEL)],
)
def test_exact_registry_pairs_are_accepted(candidate, model):
    identity.require_registered_candidate_pair(candidate, model)


@pytest.mark.parametrize(
    "candidate, model",
    [
        ("SUP-D", M3_MODEL),
        (M3_CANDIDATE, QWEN_MODEL),
        (M3_CANDIDATE, "minimax-m3-thinking"),
        (M3_CANDIDATE, "MiniMax-M3"),
        ("sup-m3", M3_MODEL),
        ("SUP-M3 ", M3_MODEL),
        (M3_CANDIDATE, None),
        (None, M3_MODEL),
    ],
)
def test_mixed_or_variant_pairs_are_refused(candidate, model):
    with pytest.raises(ValueError):
        identity.require_registered_candidate_pair(candidate, model)


def test_the_frozen_autonomous_registry_still_excludes_every_supervised_candidate():
    frozen = off._frozen_candidate_registry()
    assert M3_MODEL not in frozen.values() and M3_CANDIDATE not in frozen


# -- 2. the gate (offline library path) ------------------------------------------------


@pytest.mark.parametrize(
    "overrides, category",
    [
        ({"candidate": M3_CANDIDATE, "model": QWEN_MODEL}, "candidate_model_mismatch"),
        ({"candidate": "SUP-D", "model": M3_MODEL}, "candidate_model_mismatch"),
        ({"candidate": M3_CANDIDATE, "model": "minimax-m3-thinking"}, "candidate_model_mismatch"),
        ({"candidate": M3_CANDIDATE, "model": "MiniMax-M3"}, "candidate_model_mismatch"),
        ({"candidate": M3_CANDIDATE, "model": None}, "candidate_model_mismatch"),
        ({"candidate": "sup-m3", "model": M3_MODEL}, "unknown_candidate"),
        ({"candidate": "M3", "model": M3_MODEL}, "unknown_candidate"),
        ({"candidate": "SUP-M", "model": M3_MODEL}, "unknown_candidate"),
    ],
)
def test_the_gate_refuses_any_m3_substitution_before_reading(tmp_path, overrides, category):
    root = off._make_workspace(tmp_path)
    off._refused(tmp_path, category, project=off._project(root, **overrides))


def test_offline_sup_m3_request_and_provenance_name_the_selected_pair(tmp_path):
    root = off._make_workspace(tmp_path)
    project = off._project(root, candidate=M3_CANDIDATE, model=M3_MODEL)
    fake = off.FakeModel(json_body=off._completion(json.dumps({"content_text": off.PROPOSED}), model=M3_MODEL))
    notices: list = []
    result, _ = off._run(tmp_path, fake, project=project, notices=notices)
    assert len(fake.requests) == 1 and fake.requests[0]["model"] == M3_MODEL
    assert notices[0].candidate == M3_CANDIDATE and notices[0].model == M3_MODEL
    prov = result.provenance
    assert (prov.candidate, prov.model) == (M3_CANDIDATE, M3_MODEL)
    assert prov.qualification_credit == "none"
    assert prov.orchestrator_approval_created is False
    assert "SUP-M3 (model minimax-m3)" in result.diff_proposal.changes[0].rationale


def test_offline_provenance_refuses_a_mixed_pair(tmp_path):
    result, _ = off._run(tmp_path)
    data = result.provenance.model_dump(mode="json")
    SupervisedImplementerProvenance.model_validate(data)  # the SUP-D record is valid as is
    for candidate, model in (("SUP-D", M3_MODEL), (M3_CANDIDATE, QWEN_MODEL)):
        mixed = dict(data, candidate=candidate, model=model)
        with pytest.raises(ValidationError):
            SupervisedImplementerProvenance.model_validate(mixed)
    SupervisedImplementerProvenance.model_validate(dict(data, candidate=M3_CANDIDATE, model=M3_MODEL))


# -- 3. the live P1B path ----------------------------------------------------------------


class TestLive:
    pytestmark = _windows_git

    def _m3_env(self, tmp_path, **overrides):
        return lv.Env(tmp_path, candidate=M3_CANDIDATE, model=M3_MODEL, **overrides)

    def test_sup_m3_is_bound_at_h2_and_carried_by_the_one_request(self, tmp_path, capsys):
        env = self._m3_env(tmp_path)
        before = lv._workspace_state(env.repo)
        document = lv._consented(env, capsys)
        bound = document["bound"]
        assert (bound["candidate"], bound["model"], bound["provider"]) == (M3_CANDIDATE, M3_MODEL, "litellm")
        la.AuthorizationBound.model_validate(bound)

        code, out, err, server = lv._run(capsys, env, _m3_server())
        assert code == 0, err
        assert len(server.requests) == 1 and server.factory_calls == 1
        body = json.loads(server.requests[0].content)
        assert body["model"] == M3_MODEL
        assert "max_tokens" not in body and "response_format" not in body and "stream" not in body
        assert "candidate:     SUP-M3 / model minimax-m3" in err

        provenance = json.loads(out)
        assert (provenance["candidate"], provenance["model"]) == (M3_CANDIDATE, M3_MODEL)
        assert provenance["aido_requested"]["model"] == M3_MODEL
        assert provenance["aido_requested"]["client_max_retries"] == 0
        assert provenance["orchestrator_retries_issued"] == 0
        assert provenance["orchestrator_approval_created"] is False
        assert provenance["qualification_credit"] == "none"
        (run_dir,) = lv._run_dirs(env)
        request_bytes = (run_dir / "request-messages.json").read_bytes()
        assert hashlib.sha256(request_bytes).hexdigest() == bound["request_sha256"]
        assert lv._workspace_state(env.repo) == before  # nothing written

    def test_sup_m3_with_the_delimited_envelope(self, tmp_path, capsys):
        from test_supervised_implementer_delimited import _delim

        env = self._m3_env(tmp_path, output_envelope=DELIMITED)
        lv._consented(env, capsys)
        code, out, err, server = lv._run(capsys, env, _m3_server(content=_delim(lv.PROPOSED)))
        assert code == 0, err
        assert json.loads(server.requests[0].content)["model"] == M3_MODEL
        provenance = json.loads(out)
        assert provenance["aido_requested"]["output_envelope"] == DELIMITED
        assert provenance["aido_derived"]["proposed_content_sha256"] == hashlib.sha256(
            lv.PROPOSED.encode()
        ).hexdigest()

    @pytest.mark.parametrize(
        "overrides",
        [
            {"candidate": M3_CANDIDATE, "model": QWEN_MODEL},
            {"candidate": "SUP-D", "model": M3_MODEL},
            {"candidate": M3_CANDIDATE, "model": "minimax-m3-thinking"},
        ],
    )
    def test_prepare_refuses_a_mixed_pair_and_issues_nothing(self, tmp_path, capsys, overrides):
        env = lv.Env(tmp_path, **overrides)
        code, _, err = lv._prepare(capsys, env)
        assert code == 1 and "candidate_model_mismatch" in err
        assert not env.draft.exists() and lv._ledger_names(env) == []

    def test_an_authorization_for_sup_d_never_sends_for_sup_m3(self, tmp_path, capsys):
        env = lv.Env(tmp_path)
        lv._consented(env, capsys)
        env.write_config(candidate=M3_CANDIDATE, model=M3_MODEL)
        code, _, err, server = lv._run(capsys, env, _m3_server(), read_env=lv._never_read_env)
        assert code == 1 and "authorization_mismatch" in err
        assert "candidate" in err and "model" in err
        assert server.requests == [] and lv._run_dirs(env) == []

    def test_an_authorization_for_sup_m3_never_sends_for_sup_d(self, tmp_path, capsys):
        env = self._m3_env(tmp_path)
        lv._consented(env, capsys)
        env.write_config()
        code, _, err, server = lv._run(capsys, env, read_env=lv._never_read_env)
        assert code == 1 and "authorization_mismatch" in err
        assert server.requests == [] and lv._run_dirs(env) == []

    @pytest.mark.parametrize(
        "candidate, model",
        [(M3_CANDIDATE, QWEN_MODEL), ("SUP-D", M3_MODEL), (M3_CANDIDATE, M3_MODEL)],
    )
    def test_an_edited_bound_identity_is_refused_unsent(self, tmp_path, capsys, candidate, model):
        env = lv.Env(tmp_path)

        def edit(bound):
            bound["candidate"], bound["model"] = candidate, model

        lv._consented(env, capsys, bound_edit=edit)
        code, _, err, server = lv._run(capsys, env, read_env=lv._never_read_env)
        assert code == 1 and "authorization_invalid" in err
        assert server.requests == [] and lv._run_dirs(env) == []

    def test_the_authorization_record_refuses_a_mixed_pair_even_with_a_recomputed_binding(self, tmp_path, capsys):
        env = lv.Env(tmp_path)
        bound = lv._consented(env, capsys)["bound"]
        for candidate, model in ((M3_CANDIDATE, QWEN_MODEL), ("SUP-D", M3_MODEL)):
            forged = dict(bound, candidate=candidate, model=model)
            forged["binding_sha256"] = la.compute_binding_sha256(forged)
            with pytest.raises(ValidationError):
                la.AuthorizationBound.model_validate(forged)

    def test_live_provenance_refuses_mixed_or_disagreeing_models(self, tmp_path, capsys):
        env = self._m3_env(tmp_path)
        lv._consented(env, capsys)
        code, out, err, _ = lv._run(capsys, env, _m3_server())
        assert code == 0, err
        data = json.loads(out)
        live.SupervisedImplementerLiveProvenance.model_validate(data)
        with pytest.raises(ValidationError):
            live.SupervisedImplementerLiveProvenance.model_validate(dict(data, candidate="SUP-D"))
        with pytest.raises(ValidationError):
            live.SupervisedImplementerLiveProvenance.model_validate(
                dict(data, candidate="SUP-D", model=QWEN_MODEL)  # aido_requested still says M3
            )

    @pytest.mark.parametrize("served", [QWEN_MODEL, "minimax-m3-thinking"])
    def test_a_reply_naming_another_model_is_rejected_as_substitution(self, tmp_path, capsys, served):
        env = self._m3_env(tmp_path)
        before = lv._workspace_state(env.repo)
        lv._consented(env, capsys)
        code, out, err, server = lv._run(capsys, env, _m3_server(model=served))
        assert code == 4, err
        assert out == "" and "model_substitution" in err
        assert len(server.requests) == 1  # rejected once, never retried or re-routed
        (run_dir,) = lv._run_dirs(env)
        outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
        assert outcome["state"] == "output_rejected"
        assert outcome["failure_category"] == "model_substitution"
        assert outcome["orchestrator_retries_issued"] == 0
        assert not (run_dir / "diff-proposal.json").exists()
        assert lv._workspace_state(env.repo) == before

    def test_a_think_prefixed_json_reply_is_rejected_not_repaired(self, tmp_path, capsys):
        """A reasoning model that inlines its thinking fails the strict parser once."""
        env = self._m3_env(tmp_path)
        before = lv._workspace_state(env.repo)
        lv._consented(env, capsys)
        content = "<think>plan</think>" + json.dumps({"content_text": lv.PROPOSED})
        code, _, err, server = lv._run(capsys, env, _m3_server(content=content))
        assert code == 4, err
        assert len(server.requests) == 1
        (run_dir,) = lv._run_dirs(env)
        outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
        assert outcome["state"] == "output_rejected"
        assert outcome["orchestrator_retries_issued"] == 0
        assert not (run_dir / "diff-proposal.json").exists()
        assert lv._workspace_state(env.repo) == before


# -- 4. the reviewer -----------------------------------------------------------------------


def _review_block(model: str) -> str:
    return f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{model}"
{ENDPOINT_LINES}"""


def _reviewer_transport(model: str, content: str, seen: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "model": model,
                "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 321, "completion_tokens": 64, "total_tokens": 385},
            },
        )

    return lambda: httpx.MockTransport(handler)


class TestReviewer:
    pytestmark = _windows_git

    @pytest.mark.parametrize("model", [M3_MODEL, GPT_OSS_MODEL])
    def test_the_configured_reviewer_model_is_the_one_requested_and_recorded(self, tmp_path, capsys, model):
        _, config, artifact = _review_setup(tmp_path, review_block=_review_block(model))
        seen: list[dict] = []
        # The environment default names the OTHER model; it must not win.
        other = GPT_OSS_MODEL if model == M3_MODEL else M3_MODEL
        code = _review_run(
            config,
            artifact,
            read_env=lambda _provider: _review_env(AIDO_LITELLM_DEFAULT_MODEL=other),
            client_factory=_reviewer_transport(model, VALID_REVIEW_JSON, seen),
        )
        assert code == 0
        assert len(seen) == 1 and seen[0]["model"] == model
        packet = _stdout_json(capsys)
        assert packet["schema_version"] == "review-packet.v5"
        assert packet["reviewer"]["model"] == model
        assert packet["reviewer"]["model_source"] == "project_config.controlled_review.model"
        assert packet["reviewer"]["semantic_requests"] == 1

    def test_an_m3_changes_requested_verdict_is_preserved_and_ends_at_a_human(self, tmp_path, capsys):
        _, config, artifact = _review_setup(tmp_path, review_block=_review_block(M3_MODEL))
        seen: list[dict] = []
        code = _review_run(
            config,
            artifact,
            read_env=lambda _provider: _review_env(),
            client_factory=_reviewer_transport(M3_MODEL, CHANGES_REQUESTED_JSON, seen),
        )
        assert code == 0 and len(seen) == 1
        packet = _stdout_json(capsys)
        assert packet["review"]["verdict"] == "changes_requested"
        assert packet["review"]["findings"] == json.loads(CHANGES_REQUESTED_JSON)["findings"]

    @pytest.mark.parametrize(
        "content",
        [
            "```json\n" + VALID_REVIEW_JSON + "\n```",
            "<think>the diff looks fine</think>" + VALID_REVIEW_JSON,
            "<think>the diff looks fine</think>\n\n" + VALID_REVIEW_JSON,
        ],
    )
    def test_an_m3_envelope_violation_is_rejected_with_no_second_request(self, tmp_path, capsys, content):
        """No compact retry is configured here, so a rejected reply is terminal."""
        _, config, artifact = _review_setup(tmp_path, review_block=_review_block(M3_MODEL))
        seen: list[dict] = []
        code = _review_run(
            config,
            artifact,
            read_env=lambda _provider: _review_env(),
            client_factory=_reviewer_transport(M3_MODEL, content, seen),
        )
        assert code == 4
        assert len(seen) == 1 and seen[0]["model"] == M3_MODEL
        # FU-A: exit 4 keeps the verified report on stdout; still no packet.
        assert_preserved_verification_only(capsys.readouterr().out)


# -- 5. the task coordinator, end to end, with role pairings --------------------------------


def _task_env(tmp_path, *, candidate: str, implementer_model: str, reviewer_model: str) -> TaskEnv:
    env = TaskEnv(tmp_path)
    document = yaml.safe_load(env.config.read_text(encoding="utf-8"))
    document["supervised_implementer"]["candidate"] = candidate
    document["supervised_implementer"]["model"] = implementer_model
    document["controlled_review"]["model"] = reviewer_model
    env.config.write_text(yaml.safe_dump(document), encoding="utf-8")
    env.implementer = Server(
        lambda request: httpx.Response(200, json=lv._completion(PROPOSED, model=implementer_model))
    )
    env.reviewer = Server(
        lambda request: httpx.Response(
            200,
            json={
                "model": reviewer_model,
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps(VALID_REVIEW)}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 321, "completion_tokens": 64, "total_tokens": 385},
            },
        )
    )
    return env


@pytest.mark.parametrize(
    "candidate, implementer_model, reviewer_model",
    [
        (M3_CANDIDATE, M3_MODEL, GPT_OSS_MODEL),  # acceptance plan run 1
        ("SUP-D", QWEN_MODEL, M3_MODEL),  # acceptance plan run 2
    ],
)
class TestCoordinatorPairings:
    pytestmark = _windows_git

    def test_one_task_end_to_end(self, tmp_path, capsys, candidate, implementer_model, reviewer_model):
        env = _task_env(
            tmp_path, candidate=candidate, implementer_model=implementer_model, reviewer_model=reviewer_model
        )
        _plan_approved(capsys, env)
        _ok(_continue(capsys, env, PREPARE))
        assert _stage(env) == "implementer_consent"

        out, _ = _ok_approve(capsys, env, CONSENT)
        assert f"provider litellm, model {implementer_model} (supervised implementer {candidate})" in out
        assert env.implementer.requests == [] and env.reviewer.requests == []

        _ok(_continue(capsys, env, IMPLEMENT))
        assert len(env.implementer.requests) == 1
        assert json.loads(env.implementer.requests[0].content)["model"] == implementer_model
        consented = (env.run_dir / "20-authorization-1.consented.json").read_bytes()
        bound = la.parse_authorization(consented).bound
        assert (bound.candidate, bound.model) == (candidate, implementer_model)
        assert _stage(env) == "diff_approval"
        assert env.reviewer.requests == []  # no write, review or approval happened by itself

        _ok_approve(capsys, env, ["approve"])
        _ok(_continue(capsys, env, APPLY))
        assert _stage(env) == "awaiting_human_decision"
        assert len(env.implementer.requests) == 1  # never re-sent
        assert len(env.reviewer.requests) == 1
        assert json.loads(env.reviewer.requests[0].content)["model"] == reviewer_model
        packets = sorted((env.run_dir / task_run.STEPS_DIR).glob("*review*.stdout"))
        packet = json.loads(packets[-1].read_text(encoding="utf-8"))
        assert packet["reviewer"]["model"] == reviewer_model
        assert packet["review"]["verdict"] == "approve"
