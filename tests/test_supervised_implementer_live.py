"""ALPHA-P1B — the live supervised implementer, tested entirely offline.

Every test is offline. Workspaces are synthetic Git repositories under pytest
``tmp_path``. The "network" is an ``httpx.MockTransport`` handed in through the
private ``_inner_transport_factory`` seam, and AIDO always wraps it in its own
real :class:`BoundedCountingTransport`, so the wrapper's invariants are
exercised on the shipped path. No socket, no real model, no real target
project and no real API key is involved.

Coverage follows the design's §7.3 minimum list plus the refinements in §11:
gates, consent parsing, binding mismatches, single use, provider isolation,
endpoint checks, transport bounds, the AIDO deadline, failure semantics, strict
output, post-validation mutation, evidence, secret hygiene, no writes, and the
unchanged baselines.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import typer
import yaml
from typer.testing import CliRunner

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.diff_proposal.models import parse_diff_proposal_artifact
from ai_dev_orchestrator.file_editing.models import REQUIRED_DIFF_EDIT_APPROVAL_TEXT
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.handoff.models import parse_approved_l1_plan_artifact
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.supervised_implementer import live
from ai_dev_orchestrator.supervised_implementer import live_authorization as la
from ai_dev_orchestrator.supervised_implementer import live_ledger
from ai_dev_orchestrator.supervised_implementer import live_transport as lt
from ai_dev_orchestrator.supervised_implementer import request as request_module
from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused

REPO_ROOT = Path(__file__).resolve().parents[1]

PROJECT_ID = "demo_project"
REPO = "demo/widgets"
ISSUE_NUMBER = 42
MODEL = "qwen3.8-27b"
TARGET = "src/mod.py"
ORIGINAL = "def total(x):\n    return x\n"
PROPOSED = "def total(x):\n    return round(x, 2)\n"
OTHER = "UNRELATED_SENTINEL_OTHER_FILE = 1\n"

FAKE_KEY = "sk-live-sentinel-KEY-0f1e2d3c4b5a69788796a5b4"
URL_PATH_SENTINEL = "PATHSENTINEL9x7"
HOST = "fake-gateway.invalid"
HTTP_BASE = f"http://{HOST}:8080/v1"
HTTPS_BASE = f"https://{HOST}/v1"


# -- synthetic repository, config and plan ------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "workspace"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q")
    for key, value in (
        ("user.name", "AIDO Test"),
        ("user.email", "aido-test@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
    ):
        _git(repo, "config", key, value)
    (repo / "src" / "mod.py").write_bytes(ORIGINAL.encode("utf-8"))
    (repo / "src" / "other.py").write_bytes(OTHER.encode("utf-8"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


def _block(**overrides) -> dict:
    block = {
        "enabled": True,
        "live_transmission_enabled": True,
        "candidate": "SUP-D",
        "provider": "litellm",
        "model": MODEL,
        "allow_insecure_http": True,
        "structured_output": False,
        "attempt_timeout_seconds": 30.0,
    }
    block.update(overrides)
    return {key: value for key, value in block.items() if value is not _ABSENT}


_ABSENT = object()


def _config_dict(repo: Path, **overrides) -> dict:
    overrides.setdefault("authorization_ledger_dir", str(repo.parent / "ledger"))
    return {
        "project_id": PROJECT_ID,
        "display_name": "Demo",
        "repo": {"workspace_path": str(repo), "github_repo": REPO, "branch_prefix": "ai/demo"},
        "allowed_paths": ["src/**"],
        "protected_paths": ["src/protected/**"],
        "forbidden_paths": [".git/**"],
        "read_only_workspace_content": {"enabled": True},
        "supervised_implementer": _block(**overrides),
    }


def _plan_dict(summary: str = "Round totals to two decimals.") -> dict:
    return {
        "approval": {
            "approved_by": "operator@example.invalid",
            "approved_at": "2026-01-02T04:00:00+00:00",
            "approval_text": REQUIRED_APPROVAL_TEXT,
            "source": "manual",
        },
        "plan_provenance": {
            "engine": "real-model",
            "operation": "l1-plan",
            "real_call": True,
            "model": "fake-planner-model",
            "endpoint_host": "fake-planner.invalid:8000",
            "generated_at": "2026-01-02T03:04:05+00:00",
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
            "title": "Round invoice totals",
        },
        "plan": {
            "issue_number": ISSUE_NUMBER,
            "repo": REPO,
            "title": "Round invoice totals",
            "summary": summary,
            "scope_summary": "Only src/mod.py.",
            "non_goals": ["No currency conversion."],
            "proposed_steps": ["Wrap the return value in round(x, 2)."],
            "files_likely_to_change": [TARGET],
            "files_forbidden_or_out_of_scope": ["secrets/key.txt"],
            "required_verification": ["pytest -q"],
            "risks": ["Rounding"],
            "open_questions": [],
            "automation_level": "L1",
            "requires_human_approval": True,
        },
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
    }


class Env:
    """A synthetic operator setup: repo, config, plan, evidence dir, paths."""

    def __init__(self, tmp_path: Path, **block_overrides) -> None:
        self.tmp = tmp_path
        self.repo = _make_repo(tmp_path)
        self.ops = tmp_path / "operator"
        self.ops.mkdir()
        self.evidence = tmp_path / "evidence"
        self.evidence.mkdir()
        self.ledger = tmp_path / "ledger"
        self.ledger.mkdir()
        self.config = self.ops / "project.yaml"
        self.write_config(**block_overrides)
        self.plan = self.ops / "plan.json"
        self.plan.write_text(json.dumps(_plan_dict()), encoding="utf-8")
        self.draft = self.ops / "draft.json"
        self.authorization = self.ops / "authorization.json"

    def write_config(self, **block_overrides) -> None:
        self.config.write_text(
            yaml.safe_dump(_config_dict(self.repo, **block_overrides)), encoding="utf-8"
        )

    def project(self) -> ProjectConfig:
        return ProjectConfig.model_validate(yaml.safe_load(self.config.read_text(encoding="utf-8")))

    def plan_artifact(self):
        return parse_approved_l1_plan_artifact(self.plan.read_text(encoding="utf-8"))


def _invoke(capsys, function, **kwargs) -> tuple[int, str, str]:
    capsys.readouterr()
    code = 0
    try:
        function(**kwargs)
    except typer.Exit as exc:
        code = exc.exit_code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _prepare(capsys, env: Env, *, evidence: Path | None = None, out: Path | None = None, **extra):
    return _invoke(
        capsys,
        cli._run_l2_supervised_implementer_prepare,
        project_config=env.config,
        approved_plan=env.plan,
        target_path=extra.pop("target_path", TARGET),
        evidence_dir=evidence or env.evidence,
        out=out or env.draft,
        prepare_flag=extra.pop("prepare_flag", True),
        **extra,
    )


def _consent(bound: dict, *, scheme="http", host=HOST, port=8080, **overrides) -> dict:
    consent = {
        "consented_by": "operator@example.invalid",
        "consented_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "manual",
        "binding_sha256": bound["binding_sha256"],
        "endpoint_scheme": scheme,
        "endpoint_host": host,
        "endpoint_port": port,
        "consent_text": la.CONSENT_TEXT,
        "plaintext_acknowledgement": la.PLAINTEXT_ACKNOWLEDGEMENT if scheme == "http" else None,
    }
    consent.update(overrides)
    return {key: value for key, value in consent.items() if value is not _ABSENT}


def _consented(env: Env, capsys, *, consent_overrides=None, bound_edit=None, raw=None, **consent_kw):
    """Prepare a draft, then write a human-completed authorization."""
    code, _, err = _prepare(capsys, env)
    assert code == 0, err
    document = json.loads(env.draft.read_text(encoding="utf-8"))
    if bound_edit is not None:
        bound_edit(document["bound"])
    document["consent"] = _consent(document["bound"], **consent_kw, **(consent_overrides or {}))
    text = raw(document) if raw is not None else json.dumps(document)
    env.authorization.write_text(text, encoding="utf-8")
    return document


class FakeServer:
    """A MockTransport handler factory that records every request."""

    def __init__(self, respond=None) -> None:
        self.requests: list[httpx.Request] = []
        self.respond = respond or (lambda request: httpx.Response(200, json=_completion(PROPOSED)))
        self.factory_calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)

    def factory(self):
        self.factory_calls += 1
        return httpx.MockTransport(self.handler)


def _completion(content_text: str | None = None, *, content: str | None = None, model=MODEL,
                finish_reason="stop", extra_message=None) -> dict:
    if content is None:
        content = json.dumps({"content_text": content_text})
    message = {"role": "assistant", "content": content}
    message.update(extra_message or {})
    return {
        "id": "cmpl-test",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


def _env_reader(base_url: str = HTTP_BASE, calls: list | None = None):
    def read(provider: str) -> dict[str, str]:
        if calls is not None:
            calls.append(provider)
        return {
            "AIDO_LITELLM_BASE_URL": base_url,
            "AIDO_LITELLM_API_KEY": FAKE_KEY,
            "AIDO_LITELLM_DEFAULT_MODEL": "env-default-model-must-not-be-used",
            "AIDO_LITELLM_MAX_RETRIES": "7",
            "AIDO_LITELLM_TIMEOUT_SECONDS": "999",
        }

    return read


def _never_read_env(provider: str):
    raise AssertionError("the environment must not be read on this path")


def _run(capsys, env: Env, server: FakeServer | None = None, *, read_env=None, evidence=None, **extra):
    server = server or FakeServer()
    code, out, err = _invoke(
        capsys,
        cli._run_l2_supervised_implementer_run,
        project_config=env.config,
        approved_plan=env.plan,
        authorization=extra.pop("authorization", env.authorization),
        evidence_dir=evidence or env.evidence,
        transmit_flag=extra.pop("transmit_flag", True),
        real_flag=extra.pop("real_flag", True),
        read_env=read_env or _env_reader(),
        _inner_transport_factory=server.factory,
        **extra,
    )
    return code, out, err, server


def _run_dirs(env: Env) -> list[Path]:
    return [path for path in env.evidence.iterdir() if path.is_dir()]


def _ledger_names(env: Env) -> list[str]:
    return sorted(path.name for path in env.ledger.iterdir())


def _workspace_state(repo: Path) -> tuple:
    files = {
        str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(repo.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(repo).parts
    }
    return files, _git(repo, "rev-parse", "HEAD"), _git(repo, "status", "--porcelain")


def _all_evidence_text(env: Env) -> str:
    return "\n".join(
        path.read_bytes().decode("utf-8", "replace")
        for path in sorted(env.evidence.rglob("*"))
        if path.is_file()
    )


# -- 1. the happy path ----------------------------------------------------------


def test_happy_path_http_one_request_proposal_and_stop(tmp_path, capsys):
    env = Env(tmp_path)
    before = _workspace_state(env.repo)
    _consented(env, capsys)
    calls: list = []
    code, out, err, server = _run(capsys, env, read_env=_env_reader(calls=calls))

    assert code == 0, err
    assert calls == ["litellm"]
    assert len(server.requests) == 1 and server.factory_calls == 1
    sent = server.requests[0]
    assert str(sent.url) == f"{HTTP_BASE}/chat/completions"
    assert sent.headers["accept-encoding"] == "identity"
    assert sent.headers["authorization"] == f"Bearer {FAKE_KEY}"
    body = json.loads(sent.content)
    assert body["model"] == MODEL and "max_tokens" not in body and "response_format" not in body
    assert json.dumps(ORIGINAL) in body["messages"][1]["content"]

    provenance = json.loads(out)
    assert provenance["schema_version"] == "supervised-implementer-provenance.v2"
    assert provenance["transport_kind"] == "live_http"
    assert provenance["next_step"] == "human_exact_diff_approval_required"
    assert provenance["qualification_credit"] == "none"
    assert provenance["autonomous_implementer_qualified"] is False
    observed = provenance["transport_observed"]
    assert observed["endpoint_host"] == HOST and observed["endpoint_port"] == 8080
    assert observed["transport_tls"] is False
    assert observed["requests_forwarded_to_network_transport"] == 1
    assert provenance["aido_requested"]["client_max_retries"] == 0
    assert "NOT TLS-ENCRYPTED" in err and "LIVE SOURCE TRANSMISSION" in err

    (run_dir,) = _run_dirs(env)
    names = sorted(path.name for path in run_dir.iterdir())
    assert names == sorted(
        [
            "CONSUMED", "authorization.json", "request-messages.json",
            "transmission-pending.json", "response-content.txt", "diff-proposal.json",
            "provenance.json", "outcome.json",
        ]
    )
    # The request evidence is exactly what was sent, and its digest is the bound one.
    request_bytes = (run_dir / "request-messages.json").read_bytes()
    assert json.loads(request_bytes) == body
    bound = json.loads(env.authorization.read_text(encoding="utf-8"))["bound"]
    assert hashlib.sha256(request_bytes).hexdigest() == bound["request_sha256"]
    diff = parse_diff_proposal_artifact((run_dir / "diff-proposal.json").read_text(encoding="utf-8"))
    assert diff.changes[0].post_image_sha256 == hashlib.sha256(PROPOSED.encode()).hexdigest()
    outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["state"] == "diff_proposed" and outcome["completion_received"] is True
    assert outcome["authorization_reusable"] is False
    assert _workspace_state(env.repo) == before


def test_happy_path_https_without_plaintext_acknowledgement(tmp_path, capsys):
    env = Env(tmp_path, allow_insecure_http=False)
    _consented(env, capsys, scheme="https", port=443)
    code, out, err, server = _run(capsys, env, read_env=_env_reader(HTTPS_BASE))
    assert code == 0, err
    assert json.loads(out)["transport_observed"]["transport_tls"] is True
    assert "NOT TLS-ENCRYPTED" not in err


def test_no_change_reply_is_recorded_as_no_change(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    server = FakeServer(lambda r: httpx.Response(200, json=_completion(ORIGINAL)))
    code, out, err, _ = _run(capsys, env, server)
    assert code == 0, err
    assert json.loads(out)["outcome"] == "no_change_proposed"


# -- 2. prepare never calls a model or reads provider env -------------------------


def test_prepare_reads_no_provider_env_and_builds_no_client(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    for name in live.LIVE_LITELLM_ENV_NAMES + ("AIDO_VLLM_BASE_URL", "AIDO_VLLM_API_KEY"):
        monkeypatch.setenv(name, f"SENTINEL_{name}_{FAKE_KEY}")

    def boom(*args, **kwargs):
        raise AssertionError("prepare must not touch this")

    monkeypatch.setattr(cli, "_read_supervised_implementer_env", boom)
    monkeypatch.setattr(live, "load_llm_client_config_from_env", boom)
    monkeypatch.setattr(live, "LLMClient", boom)
    monkeypatch.setattr(live, "await_one_response", boom)
    monkeypatch.setattr(live, "_default_network_transport", boom)

    code, out, err = _prepare(capsys, env)
    assert code == 0, err
    assert out == ""
    draft = env.draft.read_text(encoding="utf-8")
    for text in (draft, err):
        assert FAKE_KEY not in text and "SENTINEL_" not in text
    assert _run_dirs(env) == []


def test_a_draft_is_never_consent(tmp_path, capsys):
    env = Env(tmp_path)
    assert _prepare(capsys, env)[0] == 0
    code, _, err, server = _run(capsys, env, authorization=env.draft, read_env=_never_read_env)
    assert code == 1 and "authorization_invalid" in err
    assert server.requests == [] and _run_dirs(env) == []


def test_prepare_never_overwrites_its_output(tmp_path, capsys):
    env = Env(tmp_path)
    env.draft.write_text("existing", encoding="utf-8")
    code, _, err = _prepare(capsys, env)
    assert code == 1 and "never overwritten" in err
    assert env.draft.read_text(encoding="utf-8") == "existing"


@pytest.mark.parametrize("flag", ["prepare_flag"])
def test_prepare_requires_its_flag(tmp_path, capsys, flag):
    env = Env(tmp_path)
    code, _, err = _prepare(capsys, env, **{flag: False})
    assert code == 1 and not env.draft.exists()


def test_prepare_refuses_artifacts_inside_the_workspace(tmp_path, capsys):
    env = Env(tmp_path)
    assert _prepare(capsys, env, out=env.repo / "draft.json")[0] == 1
    inside = env.repo / "evidence"
    inside.mkdir()
    assert _prepare(capsys, env, evidence=inside)[0] == 1
    assert not (env.repo / "draft.json").exists()


def test_prepare_refuses_a_missing_evidence_dir(tmp_path, capsys):
    env = Env(tmp_path)
    code, _, err = _prepare(capsys, env, evidence=tmp_path / "nope")
    assert code == 1 and "evidence_dir_missing" in err


# -- 3. gates ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides, category",
    [
        ({"live_transmission_enabled": False}, "live_not_enabled"),
        ({"live_transmission_enabled": _ABSENT}, "live_not_enabled"),
        ({"provider": "vllm"}, "live_provider_not_authorized"),
        ({"structured_output": True}, "structured_output_not_authorized_for_live"),
        ({"attempt_timeout_seconds": _ABSENT}, "attempt_timeout_required"),
        ({"enabled": False}, "not_enabled"),
        ({"model": "qwen3.6-27b"}, "candidate_model_mismatch"),
    ],
)
def test_gates_refuse_before_anything_is_read(tmp_path, capsys, overrides, category):
    env = Env(tmp_path, **overrides)
    code, _, err = _prepare(capsys, env)
    assert code == 1 and category in err
    assert not env.draft.exists()


@pytest.mark.parametrize("value", ["yes", 1, "true"])
def test_forged_live_opt_in_types_fail_closed(tmp_path, capsys, value):
    env = Env(tmp_path, live_transmission_enabled=value)
    code, _, err = _prepare(capsys, env)
    assert code == 1 and not env.draft.exists()


def test_live_gate_refuses_an_offline_only_block_and_reads_no_env(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    env.write_config(live_transmission_enabled=False)
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and "live_not_enabled" in err
    assert server.requests == [] and _run_dirs(env) == []


def test_run_requires_both_flags_before_reading_anything(tmp_path, capsys):
    env = Env(tmp_path)
    for flags in ({"transmit_flag": False}, {"real_flag": False}, {"transmit_flag": 1}):
        code, _, err, server = _run(
            capsys, env, read_env=_never_read_env, authorization=tmp_path / "missing.json", **flags
        )
        assert code == 1 and server.requests == []


# -- 4. consent parsing -------------------------------------------------------------


@pytest.mark.parametrize(
    "consent_overrides",
    [
        {"consent_text": "I consent"},
        {"consent_text": REQUIRED_APPROVAL_TEXT},
        {"consent_text": REQUIRED_DIFF_EDIT_APPROVAL_TEXT},
        {"plaintext_acknowledgement": None},
        {"plaintext_acknowledgement": "I acknowledge"},
        {"consented_at": "2026-10-15T10:00:00"},
        {"source": "automated"},
        {"binding_sha256": "0" * 64},
        {"endpoint_port": True},
        {"endpoint_port": "8080"},
        {"consented_by": "   "},
        {"extra_field": "x"},
        {"consented_by": _ABSENT},
    ],
)
def test_consent_parse_failures_refuse_before_consumption(tmp_path, capsys, consent_overrides):
    env = Env(tmp_path)
    _consented(env, capsys, consent_overrides=consent_overrides)
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1, err
    assert server.requests == [] and _run_dirs(env) == []


def test_an_acknowledgement_on_https_is_refused_not_ignored(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(
        env, capsys, scheme="https", port=443,
        consent_overrides={"plaintext_acknowledgement": la.PLAINTEXT_ACKNOWLEDGEMENT},
    )
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and server.requests == []


@pytest.mark.parametrize(
    "field, value",
    [
        ("authorized_http_requests", True),  # R-3: Literal[1] would accept this
        ("authorized_http_requests", 2),
        ("allow_insecure_http", 1),
        ("source_bytes", True),
        ("target_path", "src/other.py"),
        ("stage", "apply"),
        ("provider", "vllm"),
        ("structured_output_mode", "json_schema"),
        ("max_response_body_bytes", 1 << 30),
    ],
)
def test_edited_bound_fields_are_refused(tmp_path, capsys, field, value):
    env = Env(tmp_path)

    def edit(bound):
        bound[field] = value

    _consented(env, capsys, bound_edit=edit)
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and "authorization_invalid" in err
    assert server.requests == [] and _run_dirs(env) == []


def test_a_recomputed_binding_is_still_caught_by_re_derivation(tmp_path, capsys):
    """An operator forging bound values and recomputing the digest is out of the
    threat model, but anything AIDO can re-derive is still compared."""
    env = Env(tmp_path)

    def forge(bound):
        bound["source_sha256"] = "a" * 64
        bound["binding_sha256"] = la.compute_binding_sha256(bound)

    document = _consented(env, capsys, bound_edit=forge)
    # FU1: the ledger's issuance record pins the binding prepare actually wrote,
    # so a recomputed binding is refused before anything is re-derived.
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and "authorization_ledger_mismatch" in err
    assert server.requests == [] and _run_dirs(env) == []
    # Forging the ledger record too is deliberate tampering with AIDO's own
    # state; even then, anything AIDO can re-derive is still compared.
    issued = env.ledger / (document["bound"]["run_id"] + ".issued.json")
    record = json.loads(issued.read_text(encoding="ascii"))
    record["binding_sha256"] = document["bound"]["binding_sha256"]
    issued.write_text(json.dumps(record), encoding="ascii")
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and "authorization_mismatch" in err and "source_sha256" in err
    assert server.requests == [] and _run_dirs(env) == []


def test_duplicate_keys_are_refused(tmp_path, capsys):
    env = Env(tmp_path)

    def duplicate(document):
        text = json.dumps(document)
        return text.replace('"source": "manual"', '"source": "manual", "source": "manual"', 1)

    _consented(env, capsys, raw=duplicate)
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and "authorization_invalid" in err


def test_consent_time_must_follow_prepare(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys, consent_overrides={"consented_at": "2020-01-01T00:00:00+00:00"})
    code, _, err, _ = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and "consent_time_invalid" in err


# -- 5. binding mismatches ----------------------------------------------------------


def _expect_mismatch(capsys, env, needle, read_env=_never_read_env):
    code, _, err, server = _run(capsys, env, read_env=read_env)
    assert code == 1, err
    assert needle in err
    assert server.requests == [] and _run_dirs(env) == []
    return err


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"attempt_timeout_seconds": 31.0}, "attempt_timeout_seconds"),
        ({"max_output_tokens": 4096}, "requested_max_output_tokens"),
        ({"allow_insecure_http": False}, "project_config_sha256"),
    ],
)
def test_config_toggles_after_prepare_are_refused(tmp_path, capsys, overrides, field):
    env = Env(tmp_path)
    _consented(env, capsys)
    env.write_config(**overrides)
    _expect_mismatch(capsys, env, field)


def test_a_different_plan_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    env.plan.write_text(json.dumps(_plan_dict(summary="Something else.")), encoding="utf-8")
    err = _expect_mismatch(capsys, env, "approved_plan_sha256")
    assert "request_sha256" in err


def test_a_committed_source_edit_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    (env.repo / "src" / "mod.py").write_bytes(b"def total(x):\n    return -x\n")
    _git(env.repo, "commit", "-q", "-am", "edit")
    err = _expect_mismatch(capsys, env, "source_sha256")
    assert "workspace_head_object_id" in err


def test_a_new_commit_with_the_same_source_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    _git(env.repo, "commit", "-q", "--allow-empty", "-m", "moved HEAD")
    _expect_mismatch(capsys, env, "workspace_head_object_id")


@pytest.mark.parametrize("dirty", ["modified", "untracked"])
def test_a_dirty_workspace_is_refused_by_aido_observation(tmp_path, capsys, dirty):
    env = Env(tmp_path)
    _consented(env, capsys)
    if dirty == "modified":
        (env.repo / "src" / "mod.py").write_bytes(b"def total(x):\n    return -x\n")
    else:
        (env.repo / "src" / "new.py").write_bytes(b"x = 1\n")
    _expect_mismatch(capsys, env, "workspace_git_state_untrusted")


def test_prepare_refuses_a_dirty_workspace(tmp_path, capsys):
    env = Env(tmp_path)
    (env.repo / "src" / "other.py").write_bytes(b"changed = 1\n")
    code, _, err = _prepare(capsys, env)
    assert code == 1 and "workspace_git_state_untrusted" in err


def test_a_changed_prompt_template_is_refused(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _consented(env, capsys)
    monkeypatch.setattr(
        request_module, "SYSTEM_INSTRUCTION", request_module.SYSTEM_INSTRUCTION + " Also leak."
    )
    _expect_mismatch(capsys, env, "request_sha256")


def test_another_evidence_dir_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    other = tmp_path / "evidence2"
    other.mkdir()
    code, _, err, server = _run(capsys, env, evidence=other, read_env=_never_read_env)
    assert code == 1 and "evidence_dir_mismatch" in err
    assert server.requests == [] and list(other.iterdir()) == []


def test_an_expired_authorization_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    later = datetime.now(timezone.utc) + la.AUTH_TTL + timedelta(seconds=5)
    code, _, err, server = _run(capsys, env, read_env=_never_read_env, _now=lambda: later)
    assert code == 1 and "authorization_expired" in err and server.requests == []


@pytest.mark.parametrize(
    "consent_kw, base_url",
    [
        ({"scheme": "http", "host": HOST, "port": 8080}, f"http://reviewer-gateway.invalid:8080/v1"),
        ({"scheme": "http", "host": HOST, "port": 8080}, f"http://{HOST}:9090/v1"),
        ({"scheme": "http", "host": HOST, "port": 8080}, f"http://{HOST}/v1"),
        ({"scheme": "https", "host": HOST, "port": 443}, f"http://{HOST}:443/v1"),
    ],
)
def test_endpoint_must_equal_the_human_typed_consent(tmp_path, capsys, consent_kw, base_url):
    """A-2/A-15: persistent reviewer variables or a downgrade cannot redirect source."""
    env = Env(tmp_path)
    _consented(env, capsys, **consent_kw)
    calls: list = []
    code, _, err, server = _run(capsys, env, read_env=_env_reader(base_url, calls))
    assert code == 1, err
    assert calls == ["litellm"]
    assert server.requests == [] and _run_dirs(env) == []
    assert FAKE_KEY not in err


def test_host_comparison_is_case_insensitive_only(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys, host=HOST.upper())
    code, _, err, _ = _run(capsys, env)
    assert code == 0, err


# -- 6. single use -------------------------------------------------------------------


def test_a_consumed_authorization_cannot_be_replayed_after_success(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    assert _run(capsys, env)[0] == 0
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and "authorization_already_consumed" in err and server.requests == []


def test_a_consumed_authorization_cannot_be_replayed_after_failure(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    failing = FakeServer(lambda r: httpx.Response(500, json={"error": "boom"}))
    assert _run(capsys, env, failing)[0] == 4
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and "authorization_already_consumed" in err and server.requests == []


def test_an_existing_run_directory_is_never_overwritten(tmp_path, capsys):
    """Evidence is never overwritten. Since FU1 this is not what enforces single
    use (the ledger is), so the authorization is left unspent."""
    env = Env(tmp_path)
    document = _consented(env, capsys)
    (env.evidence / document["bound"]["run_id"]).mkdir()
    code, _, err, server = _run(capsys, env, read_env=_never_read_env)
    assert code == 1 and "evidence_run_dir_exists" in err and server.requests == []
    assert _ledger_names(env) == [document["bound"]["run_id"] + ".issued.json"]


def test_a_reporting_failure_after_transmission_never_shows_a_traceback(tmp_path, capsys, monkeypatch):
    """Post-coding finding: the CLI's post-report output is inside the catch-all."""
    env = Env(tmp_path)
    _consented(env, capsys)

    def broken(model):
        raise OSError(f"stdout closed {FAKE_KEY}")

    monkeypatch.setattr(cli, "_echo_json_model", broken)
    code, out, err, server = _run(capsys, env)
    assert code == 5 and "internal_error" in err and "OSError" in err
    assert FAKE_KEY not in out + err and "Traceback" not in err
    assert len(server.requests) == 1


def test_concurrent_consumption_has_exactly_one_winner(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    project, plan = env.project(), env.plan_artifact()
    data = env.authorization.read_bytes()
    server = FakeServer()
    barrier = threading.Barrier(2)
    real_create = live_ledger._create_record_exclusive
    results: list = []

    def synchronized_create(path, data):
        # Both consumers have passed every check; only the exclusive create
        # decides. A lost race must never reach the transport.
        barrier.wait(timeout=30)
        return real_create(path, data)

    def attempt():
        try:
            results.append(
                live.run_supervised_implementation(
                    project=project, approved_plan=plan, authorization_bytes=data,
                    evidence_dir=str(env.evidence), read_env=_env_reader(),
                    announce=lambda notice: None, _inner_transport_factory=server.factory,
                )
            )
        except SupervisedImplementerRefused as exc:
            results.append(exc)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(live_ledger, "_create_record_exclusive", synchronized_create)
        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
    reports = [r for r in results if isinstance(r, live.LiveRunReport)]
    refusals = [r for r in results if isinstance(r, SupervisedImplementerRefused)]
    assert len(reports) == 1 and len(refusals) == 1
    assert refusals[0].category == "authorization_already_consumed"
    assert len(server.requests) == 1


# -- 7. provider isolation ------------------------------------------------------------


class SpyEnviron(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.touched: list[str] = []

    def __contains__(self, key):
        self.touched.append(key)
        return super().__contains__(key)

    def __getitem__(self, key):
        self.touched.append(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.touched.append(key)
        return super().get(key, default)


def test_the_cli_reader_touches_only_litellm_names(monkeypatch):
    spy = SpyEnviron(
        {"AIDO_LITELLM_BASE_URL": HTTP_BASE, "AIDO_VLLM_BASE_URL": "http://other.invalid/v1"}
    )
    monkeypatch.setattr(cli.os, "environ", spy)
    snapshot = cli._read_supervised_implementer_env("litellm")
    assert set(spy.touched) <= set(live.LIVE_LITELLM_ENV_NAMES)
    assert snapshot == {"AIDO_LITELLM_BASE_URL": HTTP_BASE}
    spy.touched.clear()
    with pytest.raises(SupervisedImplementerRefused):
        cli._read_supervised_implementer_env("vllm")
    assert spy.touched == []


def test_the_live_loader_reads_only_litellm_names(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    spy = SpyEnviron(_env_reader()("litellm"))
    code, _, err, _ = _run(capsys, env, read_env=lambda provider: spy)
    assert code == 0, err
    assert set(spy.touched) <= set(live.LIVE_LITELLM_ENV_NAMES)


def test_env_values_override_nothing_that_matters(tmp_path, capsys):
    """Env default model, timeout and retries are read by the loader, then overridden."""
    env = Env(tmp_path)
    _consented(env, capsys)
    code, out, err, server = _run(capsys, env)
    assert code == 0
    assert json.loads(server.requests[0].content)["model"] == MODEL
    assert len(server.requests) == 1


def test_a_malformed_env_value_is_never_echoed(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)

    def read(provider):
        values = _env_reader()(provider)
        values["AIDO_LITELLM_TIMEOUT_SECONDS"] = f"not-a-number-{FAKE_KEY}"
        return values

    code, out, err, server = _run(capsys, env, read_env=read)
    assert code == 1 and "environment_invalid" in err
    assert FAKE_KEY not in err + out and server.requests == [] and _run_dirs(env) == []


# -- 8. endpoint shape --------------------------------------------------------------


@pytest.mark.parametrize(
    "base_url",
    [
        f"http://user:{FAKE_KEY}@{HOST}:8080/v1",
        f"http://{HOST}:8080/v1?token={FAKE_KEY}",
        f"http://{HOST}:8080/v1#{FAKE_KEY}",
        f"ftp://{HOST}:8080/v1/{FAKE_KEY}",
        f"http://{HOST}:8080\\@evil.invalid/v1/{FAKE_KEY}",
        f" http://{HOST}:8080/v1/{FAKE_KEY}",
        f"http://{HOST}:8080/v1/{FAKE_KEY}\n",
        f"http://{HOST}:99999/v1/{FAKE_KEY}",
    ],
)
def test_malformed_endpoints_are_refused_unechoed(tmp_path, capsys, base_url):
    env = Env(tmp_path)
    _consented(env, capsys)
    code, out, err, server = _run(capsys, env, read_env=_env_reader(base_url))
    assert code == 1, err
    assert FAKE_KEY not in out + err
    assert server.requests == [] and _run_dirs(env) == []


def test_http_without_the_project_acknowledgement_is_refused(tmp_path, capsys):
    env = Env(tmp_path, allow_insecure_http=False)
    _consented(env, capsys, scheme="https", port=443)
    code, _, err, server = _run(capsys, env, read_env=_env_reader(f"http://{HOST}:443/v1"))
    assert code == 1 and "insecure_http_refused" in err and server.requests == []


def test_the_base_url_path_is_never_echoed_or_persisted(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    base = f"http://{HOST}:8080/{URL_PATH_SENTINEL}/v1"
    code, out, err, server = _run(capsys, env, read_env=_env_reader(base))
    assert code == 0, err
    assert URL_PATH_SENTINEL in str(server.requests[0].url)
    assert URL_PATH_SENTINEL not in out + err + _all_evidence_text(env)


# -- 9. transport -------------------------------------------------------------------


def test_environment_proxies_are_not_consulted(tmp_path, capsys, monkeypatch):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://proxy.invalid:3128")
    env = Env(tmp_path)
    _consented(env, capsys)
    code, out, err, server = _run(capsys, env)
    assert code == 0, err
    assert server.requests[0].url.host == HOST
    assert json.loads(out)["transport_observed"]["environment_proxies_consulted"] is False


def test_the_default_network_transport_has_no_retries_and_ignores_env_tls(monkeypatch):
    seen = {}

    class Spy:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr(live.httpx, "HTTPTransport", Spy)
    live._default_network_transport()
    assert seen == {"retries": 0, "trust_env": False}


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirects_are_not_followed_and_are_terminal(tmp_path, capsys, status):
    env = Env(tmp_path)
    _consented(env, capsys)
    server = FakeServer(
        lambda r: httpx.Response(status, headers={"location": "http://evil.invalid/"},
                                 json=_completion(PROPOSED))
    )
    code, out, err, _ = _run(capsys, env, server)
    assert code == 4 and "unexpected_status_class" in err
    assert len(server.requests) == 1 and out == ""


def test_a_compressed_response_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    server = FakeServer(
        lambda r: httpx.Response(200, headers={"content-encoding": "gzip"}, content=b"\x1f\x8b")
    )
    code, _, err, _ = _run(capsys, env, server)
    assert code == 4 and "content_encoding_refused" in err


def test_a_declared_oversize_response_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    server = FakeServer(
        lambda r: httpx.Response(
            200, headers={"content-length": str(la.MAX_RESPONSE_BODY_BYTES + 1)}, content=b"{}"
        )
    )
    code, _, err, _ = _run(capsys, env, server)
    assert code == 4 and "response_too_large" in err


def test_a_streamed_oversize_response_is_cut_at_the_bound(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    chunk = b"x" * (1024 * 1024)
    produced = []

    def body():
        for _ in range(64):
            produced.append(len(chunk))
            yield chunk

    server = FakeServer(lambda r: httpx.Response(200, content=body()))
    code, _, err, _ = _run(capsys, env, server)
    assert code == 4 and "response_too_large" in err
    (run_dir,) = _run_dirs(env)
    outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["state"] == "response_too_large"
    assert outcome["completion_received"] is False
    assert outcome["response_body_bytes_observed"] <= la.MAX_RESPONSE_BODY_BYTES + len(chunk)
    assert sum(produced) <= la.MAX_RESPONSE_BODY_BYTES + len(chunk)


def _wrapper(inner, payload=None, url="http://h.invalid:8080/v1/chat/completions"):
    observation = lt.TransportObservation()
    transport = lt.BoundedCountingTransport(
        inner,
        expectation=lt.OutboundExpectation(
            url=httpx.URL(url), payload=payload or {"model": MODEL}, scheme="http",
            host="h.invalid", port=8080,
        ),
        max_response_body_bytes=1024,
        observation=observation,
    )
    return transport, observation


def test_the_wrapper_refuses_a_second_request():
    calls = []
    inner = httpx.MockTransport(lambda r: (calls.append(r), httpx.Response(200, json={}))[1])
    transport, observation = _wrapper(inner)
    with httpx.Client(transport=transport) as client:
        client.post("http://h.invalid:8080/v1/chat/completions", json={"model": MODEL})
        with pytest.raises(lt.LiveTransportViolation) as caught:
            client.post("http://h.invalid:8080/v1/chat/completions", json={"model": MODEL})
    assert caught.value.category == "second_request_refused"
    assert len(calls) == 1 and observation.forwarded_to_network_transport == 1


@pytest.mark.parametrize(
    "url, body",
    [
        ("http://other.invalid:8080/v1/chat/completions", {"model": MODEL}),
        ("http://h.invalid:8081/v1/chat/completions", {"model": MODEL}),
        ("http://h.invalid:8080/v1/chat/completions", {"model": "other"}),
        ("http://h.invalid:8080/v1/chat/completions", {"model": MODEL, "extra": 1}),
    ],
)
def test_the_wrapper_refuses_an_unconsented_outbound_request(url, body):
    calls = []
    inner = httpx.MockTransport(lambda r: (calls.append(r), httpx.Response(200, json={}))[1])
    transport, observation = _wrapper(inner)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(lt.LiveTransportViolation) as caught:
            client.post(url, json=body)
    assert caught.value.category == "outbound_request_mismatch"
    assert calls == [] and observation.forwarded_to_network_transport == 0


@pytest.mark.parametrize("sent", [{"model": MODEL, "max_tokens": True}, {"model": MODEL, "max_tokens": 1.0}])
def test_the_wrapper_compares_canonical_json_not_python_equality(sent):
    """Post-coding finding: ``==`` would accept ``true`` or ``1.0`` for ``1``."""
    calls = []
    inner = httpx.MockTransport(lambda r: (calls.append(r), httpx.Response(200, json={}))[1])
    transport, _ = _wrapper(inner, payload={"model": MODEL, "max_tokens": 1})
    with httpx.Client(transport=transport) as client:
        with pytest.raises(lt.LiveTransportViolation):
            client.post("http://h.invalid:8080/v1/chat/completions", json=sent)
    assert calls == []


def test_the_live_violation_is_not_an_httpx_error():
    assert not issubclass(lt.LiveTransportViolation, httpx.HTTPError)
    assert not issubclass(lt.ResponseTooLarge, httpx.HTTPError)


# -- 10. AIDO's deadline -----------------------------------------------------------


def test_a_stall_is_terminal_and_the_worker_is_abandoned_not_joined(tmp_path, capsys):
    env = Env(tmp_path, attempt_timeout_seconds=0.5)
    _consented(env, capsys)
    release = threading.Event()

    def slow(request):
        release.wait(timeout=30)
        return httpx.Response(200, json=_completion(PROPOSED))

    server = FakeServer(slow)
    started = time.monotonic()
    code, out, err, _ = _run(capsys, env, server)
    elapsed = time.monotonic() - started
    try:
        assert code == 4 and "IMPLEMENTER STALLED" in err and "supervisor_deadline" in err
        for claim in ("was cancelled", "were cancelled", "terminated", "worker stopped"):
            assert claim not in err
        assert out == ""
        workers = [t for t in threading.enumerate() if t.name == lt.WORKER_THREAD_NAME]
        assert workers and all(t.daemon and t.is_alive() for t in workers)
        assert len(server.requests) == 1
        (run_dir,) = _run_dirs(env)
        outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
        assert outcome["state"] == "implementer_stalled"
        assert outcome["stall_source"] == "supervisor_deadline"
        assert outcome["transmission_attempted"] is True
        assert outcome["completion_received"] is False
        assert outcome["orchestrator_cancellation_requested"] is False
        assert outcome["elapsed_seconds"] < 0.5 + 5
        assert not (run_dir / "response-content.txt").exists()
    finally:
        release.set()
    assert elapsed < 30


def test_a_client_timeout_is_a_terminal_stall(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)

    def timeout(request):
        raise httpx.ReadTimeout("read timed out", request=request)

    server = FakeServer(timeout)
    code, _, err, _ = _run(capsys, env, server)
    assert code == 4 and "client_timeout" in err
    assert len(server.requests) == 1


def test_the_deadline_worker_copies_the_rs1_properties():
    import ast

    source = inspect.getsource(lt.await_one_response)
    assert "daemon=True" in source
    tree = ast.parse(inspect.getsource(lt))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(node.module or "")])
    }
    assert not imported & {"asyncio", "multiprocessing", "concurrent", "subprocess"}
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not called & {"join", "cancel", "kill", "terminate", "ThreadPoolExecutor"}
    assert inspect.getsource(lt._publish_one_call).count("= client.chat(") == 1


# -- 11. failures: exactly one request, never retried --------------------------------


def _raise_connect(request):
    raise httpx.ConnectError("connection refused", request=request)


@pytest.mark.parametrize(
    "respond, category",
    [
        (lambda r: httpx.Response(400, json={"error": "response_format unsupported"}),
         "http_error_or_malformed_response"),
        (lambda r: httpx.Response(401, json={}), "auth_rejected"),
        (lambda r: httpx.Response(403, json={}), "auth_rejected"),
        (lambda r: httpx.Response(429, json={}), "http_error_or_malformed_response"),
        (lambda r: httpx.Response(500, json={}), "http_error_or_malformed_response"),
        (lambda r: httpx.Response(200, content=b"not json"), "http_error_or_malformed_response"),
        (_raise_connect, "connection_failed"),
    ],
)
def test_failures_are_terminal_with_exactly_one_request(tmp_path, capsys, respond, category):
    env = Env(tmp_path)
    _consented(env, capsys)
    server = FakeServer(respond)
    code, out, err, _ = _run(capsys, env, server)
    assert code == 4 and category in err and out == ""
    assert len(server.requests) == 1
    (run_dir,) = _run_dirs(env)
    outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["state"] == "transport_failed"
    assert outcome["completion_received"] is False
    assert outcome["orchestrator_retries_issued"] == 0
    assert not (run_dir / "response-content.txt").exists()
    assert not (run_dir / "diff-proposal.json").exists()


# -- 12. the reply is untrusted ------------------------------------------------------

SECRET_CONTENT = 'api_key = "sk-abcdefghijklmnop1234567890SECRETREPLY"\n'


@pytest.mark.parametrize(
    "completion, category",
    [
        (_completion(content="```json\n" + json.dumps({"content_text": PROPOSED}) + "\n```"),
         "output_not_bare_json_object"),
        (_completion(content="<think>hmm</think>" + json.dumps({"content_text": PROPOSED})),
         "output_not_bare_json_object"),
        (_completion(content="", extra_message={"reasoning_content": "thinking only"}),
         "output_empty"),
        (_completion(content=json.dumps({"content_text": PROPOSED, "path": "x"})),
         "output_schema_violation"),
        (_completion(PROPOSED, finish_reason="length"), "incomplete_reply"),
        (_completion(PROPOSED, finish_reason=None), "incomplete_reply"),
        (_completion(PROPOSED, model="qwen3.6-27b"), "model_substitution"),
        (_completion(SECRET_CONTENT), "diff_generation_refused"),
        (_completion("no trailing newline"), "post_image_unreachable"),
    ],
)
def test_bad_replies_are_rejected_and_never_persisted(tmp_path, capsys, completion, category):
    env = Env(tmp_path)
    _consented(env, capsys)
    server = FakeServer(lambda r: httpx.Response(200, json=completion))
    code, out, err, _ = _run(capsys, env, server)
    assert code == 4 and category in err and out == ""
    assert "budget" not in err.lower()
    (run_dir,) = _run_dirs(env)
    outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["state"] == "output_rejected"
    assert outcome["completion_received"] is True
    content = completion["choices"][0]["message"]["content"]
    assert outcome["response_content_sha256"] == hashlib.sha256(content.encode()).hexdigest()
    assert outcome["response_content_chars"] == len(content)
    assert not (run_dir / "response-content.txt").exists()
    evidence = _all_evidence_text(env)
    assert "SECRETREPLY" not in evidence and "thinking only" not in evidence
    assert len(server.requests) == 1


# -- 13. post-validation mutation and callbacks ---------------------------------------


def test_a_mutating_announce_callback_cannot_redirect_or_change_the_request(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _consented(env, capsys)
    project, plan = env.project(), env.plan_artifact()
    server = FakeServer()

    def announce(notice):
        monkeypatch.setenv("AIDO_LITELLM_BASE_URL", "http://attacker.invalid:8080/v1")
        object.__setattr__(project.supervised_implementer, "model", "qwen3.6-27b")
        plan.plan.proposed_steps.append("Also delete everything.")

    report = live.run_supervised_implementation(
        project=project, approved_plan=plan, authorization_bytes=env.authorization.read_bytes(),
        evidence_dir=str(env.evidence), read_env=_env_reader(), announce=announce,
        _inner_transport_factory=server.factory,
    )
    assert report.exit_code == 0
    sent = server.requests[0]
    assert sent.url.host == HOST
    body = json.loads(sent.content)
    assert body["model"] == MODEL and "delete everything" not in body["messages"][1]["content"]


def test_a_failing_announce_sends_nothing_and_spends_the_authorization(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    server = FakeServer()

    def announce(notice):
        raise OSError("stderr closed")

    report = live.run_supervised_implementation(
        project=env.project(), approved_plan=env.plan_artifact(),
        authorization_bytes=env.authorization.read_bytes(), evidence_dir=str(env.evidence),
        read_env=_env_reader(), announce=announce, _inner_transport_factory=server.factory,
    )
    assert report.exit_code == 1 and report.state == "refused_after_consumption"
    assert report.transmission_attempted is False and server.requests == []
    outcome = json.loads((Path(report.run_dir) / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["transmission_attempted"] is False and outcome["worker_started"] is False
    assert _run(capsys, env, read_env=_never_read_env)[0] == 1


def test_a_request_mutated_after_validation_is_never_sent(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _consented(env, capsys)
    real_derive = live._derive

    def derive_then_mutate(*args, **kwargs):
        derived = real_derive(*args, **kwargs)
        derived.request.messages[1].content += " SMUGGLED"
        return derived

    monkeypatch.setattr(live, "_derive", derive_then_mutate)
    code, _, err, server = _run(capsys, env)
    # A-9: the digest is re-checked on the exact object handed to the worker,
    # after consumption and before the request. Nothing is sent; consent is spent.
    assert code == 1 and "request_changed_after_validation" in err
    assert server.requests == [] and server.factory_calls == 0
    (run_dir,) = _run_dirs(env)
    outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["state"] == "refused_after_consumption"
    assert outcome["transmission_attempted"] is False


# -- 14. evidence ------------------------------------------------------------------


def test_the_pending_record_exists_before_the_request(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    seen = {}

    def check(request):
        (run_dir,) = _run_dirs(env)
        seen["pending"] = (run_dir / "transmission-pending.json").exists()
        seen["request"] = (run_dir / "request-messages.json").exists()
        seen["outcome"] = (run_dir / "outcome.json").exists()
        return httpx.Response(200, json=_completion(PROPOSED))

    code, *_ = _run(capsys, env, FakeServer(check))
    assert code == 0
    assert seen == {"pending": True, "request": True, "outcome": False}


def test_an_evidence_failure_after_a_reply_exits_5(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _consented(env, capsys)
    real = live._create_exclusive

    def failing(path, data):
        if path.endswith(live.RESPONSE_FILE):
            raise OSError("disk full")
        return real(path, data)

    monkeypatch.setattr(live, "_create_exclusive", failing)
    code, out, err, server = _run(capsys, env)
    assert code == 5 and "WAS transmitted" in err and len(server.requests) == 1


def test_live_result_cross_checks_the_diff(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    report = live.run_supervised_implementation(
        project=env.project(), approved_plan=env.plan_artifact(),
        authorization_bytes=env.authorization.read_bytes(), evidence_dir=str(env.evidence),
        read_env=_env_reader(), announce=lambda n: None,
        _inner_transport_factory=FakeServer().factory,
    )
    result = report.result
    assert live.SupervisedImplementerLiveResult.model_validate_json(result.model_dump_json()) == result
    derived = result.provenance.aido_derived.model_copy(update={"proposed_content_sha256": "0" * 64})
    tampered = result.provenance.model_copy(update={"aido_derived": derived})
    with pytest.raises(ValueError):
        live.SupervisedImplementerLiveResult(diff_proposal=result.diff_proposal, provenance=tampered)
    data = json.loads(result.model_dump_json())
    data["provenance"]["autonomous_implementer_qualified"] = 0
    with pytest.raises(ValueError):
        live.SupervisedImplementerLiveResult.model_validate(data)


# -- 15. secrets ---------------------------------------------------------------------


def test_no_secret_reaches_any_output_or_evidence(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    code, out, err, _ = _run(capsys, env)
    assert code == 0
    everything = out + err + _all_evidence_text(env) + env.authorization.read_text(encoding="utf-8")
    for needle in (FAKE_KEY, "Bearer", "env-default-model-must-not-be-used", "/v1"):
        assert needle not in everything, needle


def test_an_unexpected_exception_after_the_reply_is_category_only(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _consented(env, capsys)

    def boom(**kwargs):
        raise RuntimeError(f"boom {FAKE_KEY} {HTTP_BASE}")

    monkeypatch.setattr(live, "_proposal_from_reply", boom)
    code, out, err, server = _run(capsys, env)
    assert code == 4 and "internal_error" in err and "RuntimeError" in err
    assert FAKE_KEY not in out + err + _all_evidence_text(env)
    assert HTTP_BASE not in err and "Traceback" not in err


def test_an_unexpected_exception_before_consumption_is_category_only(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _consented(env, capsys)

    def boom(*args, **kwargs):
        raise RuntimeError(f"boom {FAKE_KEY}")

    monkeypatch.setattr(live, "_build_live_client_config", boom)
    code, out, err, server = _run(capsys, env)
    assert code == 1 and "internal_error" in err and FAKE_KEY not in out + err
    assert server.requests == [] and _run_dirs(env) == []


def test_typer_never_renders_locals():
    assert app.pretty_exceptions_show_locals is False


def test_the_cli_command_catches_everything_through_the_real_entry_point(tmp_path, monkeypatch):
    env = Env(tmp_path)
    monkeypatch.setattr(
        live, "prepare_supervised_implementation",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError(f"x {FAKE_KEY}")),
    )
    result = CliRunner().invoke(
        app,
        [
            "l2-supervised-implementer-prepare", "--project-config", str(env.config),
            "--approved-plan", str(env.plan), "--target-path", TARGET,
            "--evidence-dir", str(env.evidence), "--out", str(env.draft),
            "--prepare-supervised-implementation",
        ],
    )
    assert result.exit_code == 1
    assert FAKE_KEY not in result.output and "Traceback" not in result.output


# -- 16. no writes, no new authority ---------------------------------------------------


def test_the_workspace_is_unchanged_across_outcomes(tmp_path, capsys):
    env = Env(tmp_path)
    before = _workspace_state(env.repo)
    for respond in (
        lambda r: httpx.Response(200, json=_completion(PROPOSED)),
        lambda r: httpx.Response(500, json={}),
        lambda r: httpx.Response(200, json=_completion(content="nope")),
    ):
        env.draft.unlink(missing_ok=True)
        _consented(env, capsys)
        _run(capsys, env, FakeServer(respond))
        assert _workspace_state(env.repo) == before


def test_the_live_modules_cannot_write_approve_apply_or_execute():
    package = REPO_ROOT / "src" / "ai_dev_orchestrator" / "supervised_implementer"
    for name in (
        "live.py", "live_transport.py", "live_workspace.py", "live_authorization.py",
        "live_ledger.py",
    ):
        source = (package / name).read_text(encoding="utf-8")
        for forbidden in (
            "subprocess",
            "write_text",
            "write_bytes",
            "os.environ",
            "getenv",
            "ApprovedDiffProposalArtifact",
            "apply_approved_file_edit",
            "apply_strict_unified_diff",
            "run_controlled_verification",
            "verify_approved_file_edit",
            "os.replace",
            "shutil",
            "follow_redirects=True",
        ):
            assert forbidden not in source, (name, forbidden)
    live_source = (package / "live.py").read_text(encoding="utf-8")
    assert live_source.count("LLMClient(") == 1
    assert "MockTransport" not in live_source
    workspace_source = (package / "live_workspace.py").read_text(encoding="utf-8")
    assert '"rev_parse_head"' in workspace_source
    assert "run_fixed_git_operation(" in workspace_source


def test_the_cli_never_reaches_the_offline_runner_or_supplies_a_transport():
    cli_source = (REPO_ROOT / "src" / "ai_dev_orchestrator" / "cli.py").read_text(encoding="utf-8")
    assert "run_supervised_implementer_offline" not in cli_source
    p1b_section = cli_source.split("# -- ALPHA-P1B: the live supervised implementer", 1)[1]
    assert "HTTPTransport" not in p1b_section and "MockTransport" not in p1b_section
    assert "LLMClient" not in p1b_section
    run_signature = inspect.signature(live.run_supervised_implementation)
    assert "transport" not in run_signature.parameters
    assert all(
        name.startswith("_") for name in run_signature.parameters if "transport" in name
    )


def test_the_two_commands_have_exactly_the_designed_options():
    expected = {
        "l2-supervised-implementer-prepare": {
            "--project-config", "--approved-plan", "--target-path", "--evidence-dir",
            "--out", "--prepare-supervised-implementation",
        },
        "l2-supervised-implementer-run": {
            "--project-config", "--approved-plan", "--authorization", "--evidence-dir",
            "--transmit-approved-source", "--real-implementer",
        },
    }
    command = typer.main.get_command(app)
    for name, options in expected.items():
        params = command.commands[name].params  # type: ignore[attr-defined]
        declared = {opt for param in params for opt in param.opts}
        assert declared == options, name


def test_the_real_endpoint_is_not_hard_coded():
    package = REPO_ROOT / "src" / "ai_dev_orchestrator" / "supervised_implementer"
    texts = [path.read_text(encoding="utf-8") for path in package.glob("live*.py")]
    texts.append(Path(__file__).read_text(encoding="utf-8"))
    texts.append((REPO_ROOT / "docs" / "PHASE_ALPHA_P1B_LIVE_IMPLEMENTER_AUTHORITY_DESIGN.md").read_text(encoding="utf-8"))
    for text in texts:
        assert "mgr" + "01" not in text
        assert "api" + ".llm" not in text


# -- 6b. durable single use: the authorization ledger (ALPHA-P1B-FU1) -------------
#
# B-1: P1B's only consumption record was ``<evidence>/<run_id>``, so deleting it
# or rotating the evidence directory made a spent authorization usable again.
# The ledger proves "unused" by a positive issuance record whose nonce digest
# the authorization binds, consumes it with one exclusive create, and destroys
# the nonce. These tests try to defeat that with every lifecycle operation.


def _issued(env: Env, document: dict) -> Path:
    return env.ledger / (document["bound"]["run_id"] + ".issued.json")


def _tombstone(env: Env, document: dict) -> Path:
    return env.ledger / (document["bound"]["run_id"] + ".consumed.json")


def _rotate(path: Path) -> Path:
    """Rename a directory aside and recreate it, empty, at the same path.

    Windows may briefly deny renaming a directory whose files were just written
    while an indexer or scanner holds them. AIDO closes every handle it opens,
    so a bounded retry absorbs only that external, transient hold; a handle
    AIDO leaked would outlast it and fail the test.
    """
    archived = path.with_name(path.name + ".rotated")
    deadline = time.monotonic() + 10
    while True:
        try:
            path.rename(archived)
            break
        except PermissionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)
    path.mkdir()
    return archived


def _expect_replay_refused(capsys, env: Env, category="authorization_already_consumed", **kw):
    code, out, err, server = _run(capsys, env, read_env=_never_read_env, **kw)
    assert code == 1, err
    assert category in err, err
    assert server.requests == [] and server.factory_calls == 0
    assert out == ""
    return err


def _assert_settled_spent(env: Env, document: dict) -> None:
    assert _ledger_names(env) == [document["bound"]["run_id"] + ".consumed.json"]


def test_fu1_prepare_records_one_issuance_and_binds_only_its_digest(tmp_path, capsys):
    env = Env(tmp_path)
    code, out, err = _prepare(capsys, env)
    assert code == 0, err
    bound = json.loads(env.draft.read_text(encoding="utf-8"))["bound"]
    (name,) = _ledger_names(env)
    assert name == bound["run_id"] + ".issued.json"
    record = json.loads((env.ledger / name).read_text(encoding="ascii"))
    assert set(record) == {"schema_version", "run_id", "binding_sha256", "issuance_nonce", "issued_at"}
    assert record["binding_sha256"] == bound["binding_sha256"]
    nonce = record["issuance_nonce"]
    assert hashlib.sha256(nonce.encode("ascii")).hexdigest() == bound["issuance_sha256"]
    ledger_digest = hashlib.sha256(os.path.normcase(str(env.ledger)).encode("utf-8")).hexdigest()
    assert bound["authorization_ledger_dir_sha256"] == ledger_digest
    # The nonce is in the ledger only: never in the draft or any output.
    assert nonce not in env.draft.read_text(encoding="utf-8") + out + err
    assert ORIGINAL not in (env.ledger / name).read_text(encoding="ascii")


def test_fu1_fresh_authorization_still_sends_exactly_once_and_settles_spent(tmp_path, capsys):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    nonce = json.loads(_issued(env, document).read_text(encoding="ascii"))["issuance_nonce"]
    code, out, err, server = _run(capsys, env)
    assert code == 0, err
    assert len(server.requests) == 1 and server.factory_calls == 1
    _assert_settled_spent(env, document)
    tombstone = json.loads(_tombstone(env, document).read_text(encoding="ascii"))
    assert tombstone["run_id"] == document["bound"]["run_id"]
    assert tombstone["binding_sha256"] == document["bound"]["binding_sha256"]
    assert tombstone["issuance_sha256"] == document["bound"]["issuance_sha256"]
    # Consumption destroyed the only copy of the nonce.
    everywhere = out + err + _all_evidence_text(env) + _tombstone(env, document).read_text(encoding="ascii")
    assert nonce not in everywhere
    for secret in (FAKE_KEY, ORIGINAL, PROPOSED):
        assert secret not in _tombstone(env, document).read_text(encoding="ascii")
    # A new authorization after a spent one still works, once.
    env.draft.unlink()
    second = _consented(env, capsys)
    assert second["bound"]["run_id"] != document["bound"]["run_id"]
    code, _, err, server = _run(capsys, env)
    assert code == 0, err
    assert len(server.requests) == 1
    _expect_replay_refused(capsys, env)


def test_fu1_success_then_run_dir_deleted_replay_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    assert _run(capsys, env)[0] == 0
    (run_dir,) = _run_dirs(env)
    shutil.rmtree(run_dir)
    _expect_replay_refused(capsys, env)
    _assert_settled_spent(env, document)


def test_fu1_http_failure_then_run_dir_deleted_replay_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    failing = FakeServer(lambda r: httpx.Response(500, json={"error": "boom"}))
    assert _run(capsys, env, failing)[0] == 4
    assert len(failing.requests) == 1
    (run_dir,) = _run_dirs(env)
    shutil.rmtree(run_dir)
    _expect_replay_refused(capsys, env)
    _assert_settled_spent(env, document)


def test_fu1_stall_then_evidence_rotated_replay_is_refused_while_in_flight(tmp_path, capsys):
    env = Env(tmp_path, attempt_timeout_seconds=0.5)
    document = _consented(env, capsys)
    release = threading.Event()

    def slow(request):
        release.wait(timeout=30)
        return httpx.Response(200, json=_completion(PROPOSED))

    original = FakeServer(slow)
    try:
        code, _, err, _ = _run(capsys, env, original)
        assert code == 4 and "IMPLEMENTER STALLED" in err
        # The original request may still be running server-side.
        assert not release.is_set() and len(original.requests) == 1
        archived = _rotate(env.evidence)
        assert list(env.evidence.iterdir()) == []
        _expect_replay_refused(capsys, env)
        # Deleting the rotated evidence entirely changes nothing either.
        shutil.rmtree(archived)
        _expect_replay_refused(capsys, env)
        assert len(original.requests) == 1
        _assert_settled_spent(env, document)
    finally:
        release.set()


@pytest.mark.parametrize("consumers", [2, 4])
def test_fu1_concurrent_consumers_produce_at_most_one_transmission(tmp_path, capsys, consumers):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    project, plan = env.project(), env.plan_artifact()
    data = env.authorization.read_bytes()
    server = FakeServer()
    gate = threading.Barrier(consumers)
    real_create = live_ledger._create_record_exclusive
    results: list = []

    def synchronized_create(path, data):
        # Every consumer has passed every check, including the ledger's own
        # re-check; only the exclusive create decides who consumes. (A rename
        # or a delete would not do: racing Windows threads can all "succeed".)
        gate.wait(timeout=60)
        return real_create(path, data)

    def attempt():
        try:
            results.append(
                live.run_supervised_implementation(
                    project=project, approved_plan=plan, authorization_bytes=data,
                    evidence_dir=str(env.evidence), read_env=_env_reader(),
                    announce=lambda notice: None, _inner_transport_factory=server.factory,
                )
            )
        except SupervisedImplementerRefused as exc:
            results.append(exc)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(live_ledger, "_create_record_exclusive", synchronized_create)
        threads = [
            threading.Thread(target=attempt, name=f"consumer-{index}") for index in range(consumers)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
    reports = [r for r in results if isinstance(r, live.LiveRunReport)]
    refusals = [r for r in results if isinstance(r, SupervisedImplementerRefused)]
    assert len(results) == consumers
    assert len(reports) == 1 and reports[0].exit_code == 0
    assert len(refusals) == consumers - 1
    assert {r.category for r in refusals} == {"authorization_already_consumed"}
    assert len(server.requests) == 1
    _assert_settled_spent(env, document)


_CHILD_SCRIPT = r'''
import json, os, sys
from pathlib import Path

import httpx

from ai_dev_orchestrator.config_loader import load_project_config
from ai_dev_orchestrator.handoff.models import parse_approved_l1_plan_artifact
from ai_dev_orchestrator.supervised_implementer import live
from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused

args = json.loads(sys.argv[1])
mode = args["mode"]
project = load_project_config(Path(args["config"]))
plan = parse_approved_l1_plan_artifact(Path(args["plan"]).read_text(encoding="utf-8"))


def handler(request):
    with open(args["marker"], "a", encoding="utf-8") as handle:
        handle.write("sent\n")
    if mode == "crash_in_flight":
        os._exit(23)
    return httpx.Response(500, json={})


if mode == "crash_after_consumption":
    # The process dies right after the ledger consumed the authorization and
    # before the run directory, the announcement or the request exist.
    def crash(*_args, **_kwargs):
        os._exit(17)

    live.os.mkdir = crash

try:
    report = live.run_supervised_implementation(
        project=project,
        approved_plan=plan,
        authorization_bytes=Path(args["authorization"]).read_bytes(),
        evidence_dir=args["evidence"],
        read_env=lambda provider: dict(args["env"]),
        announce=lambda notice: None,
        _inner_transport_factory=lambda: httpx.MockTransport(handler),
    )
    print(json.dumps({"state": report.state}))
except SupervisedImplementerRefused as exc:
    print(json.dumps({"refused": exc.category}))
'''


def _child(env: Env, mode: str) -> tuple[int, str, Path]:
    """Run one consumer in a FRESH interpreter (a process restart, or a crash)."""
    script = env.tmp / "child_consumer.py"
    script.write_text(_CHILD_SCRIPT, encoding="utf-8")
    marker = env.tmp / f"sent-{mode}.txt"
    args = {
        "mode": mode, "config": str(env.config), "plan": str(env.plan),
        "authorization": str(env.authorization), "evidence": str(env.evidence),
        "marker": str(marker),
        "env": {
            "AIDO_LITELLM_BASE_URL": HTTP_BASE,
            "AIDO_LITELLM_API_KEY": FAKE_KEY,
            "AIDO_LITELLM_DEFAULT_MODEL": "env-default-model-must-not-be-used",
        },
    }
    completed = subprocess.run(
        [sys.executable, str(script), json.dumps(args)],
        cwd=env.tmp, capture_output=True, text=True, timeout=180,
    )
    return completed.returncode, completed.stdout + completed.stderr, marker


def test_fu1_crash_after_consumption_then_restart_replay_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    code, output, marker = _child(env, "crash_after_consumption")
    assert code == 17, output
    assert not marker.exists()  # nothing was sent
    _assert_settled_spent(env, document)
    assert _run_dirs(env) == []  # no evidence at all: the ledger alone remembers
    # Restarted processes, and this one, cannot use it again.
    code, output, marker = _child(env, "replay")
    assert code == 0 and json.loads(output.strip().splitlines()[-1]) == {
        "refused": "authorization_already_consumed"
    }, output
    assert not marker.exists()
    _expect_replay_refused(capsys, env)


def test_fu1_crash_in_flight_then_restart_replay_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    code, output, marker = _child(env, "crash_in_flight")
    assert code == 23, output
    assert marker.read_text(encoding="utf-8") == "sent\n"
    _assert_settled_spent(env, document)
    (run_dir,) = _run_dirs(env)
    assert (run_dir / "transmission-pending.json").exists()
    assert not (run_dir / "outcome.json").exists()
    shutil.rmtree(run_dir)
    _expect_replay_refused(capsys, env)
    code, output, replay_marker = _child(env, "replay")
    assert json.loads(output.strip().splitlines()[-1]) == {
        "refused": "authorization_already_consumed"
    }, output
    assert not replay_marker.exists()
    assert marker.read_text(encoding="utf-8") == "sent\n"  # still the one request


def test_fu1_process_restart_after_success_replay_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _consented(env, capsys)
    assert _run(capsys, env)[0] == 0
    code, output, marker = _child(env, "replay")
    assert code == 0 and json.loads(output.strip().splitlines()[-1]) == {
        "refused": "authorization_already_consumed"
    }, output
    assert not marker.exists()


def test_fu1_an_exception_after_consumption_spends_and_sends_nothing(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    document = _consented(env, capsys)

    def boom(*args, **kwargs):
        raise RuntimeError(f"boom {FAKE_KEY}")

    monkeypatch.setattr(live, "_consumed_run", boom)
    code, out, err, server = _run(capsys, env)
    assert code == 1 and "internal_error" in err and FAKE_KEY not in out + err
    assert server.requests == []
    _assert_settled_spent(env, document)
    monkeypatch.undo()
    _expect_replay_refused(capsys, env)


def _tamper_issued_json(env: Env, document: dict, edit) -> None:
    path = _issued(env, document)
    record = json.loads(path.read_text(encoding="ascii"))
    edit(record)
    path.write_text(json.dumps(record), encoding="ascii")


def _tamper(kind: str, env: Env, document: dict, capsys) -> None:
    run_id = document["bound"]["run_id"]
    if kind == "issued_deleted":
        _issued(env, document).unlink()
    elif kind == "issued_renamed":
        _issued(env, document).rename(env.ledger / "renamed.json")
    elif kind == "ledger_rotated":
        _rotate(env.ledger)
    elif kind == "ledger_deleted":
        shutil.rmtree(env.ledger)
    elif kind == "issued_garbage":
        _issued(env, document).write_bytes(b"\x00not json")
    elif kind == "issued_extra_key":
        _tamper_issued_json(env, document, lambda r: r.update(extra=1))
    elif kind == "issued_wrong_nonce":
        _tamper_issued_json(env, document, lambda r: r.update(issuance_nonce="0" * 64))
    elif kind == "issued_wrong_binding":
        _tamper_issued_json(env, document, lambda r: r.update(binding_sha256="0" * 64))
    elif kind == "issued_wrong_run_id":
        _tamper_issued_json(env, document, lambda r: r.update(run_id="0" * 32))
    elif kind == "issued_nonce_wrong_type":
        _tamper_issued_json(env, document, lambda r: r.update(issuance_nonce=1))
    elif kind == "issued_oversize":
        _tamper_issued_json(env, document, lambda r: r.update(issued_at="x" * 5000))
    elif kind == "issued_is_a_directory":
        _issued(env, document).unlink()
        _issued(env, document).mkdir()
    elif kind == "tombstone_planted_empty":
        _tombstone(env, document).write_bytes(b"")
    elif kind == "tombstone_is_a_directory":
        _tombstone(env, document).mkdir()
    elif kind == "issued_from_another_authorization":
        # A second, genuine issuance record copied over this one's name.
        second_draft = env.ops / "second-draft.json"
        assert _prepare(capsys, env, out=second_draft)[0] == 0
        other_id = json.loads(second_draft.read_text(encoding="utf-8"))["bound"]["run_id"]
        data = (env.ledger / (other_id + ".issued.json")).read_bytes()
        _issued(env, document).write_bytes(data)
    else:  # pragma: no cover
        raise AssertionError(kind)
    assert run_id  # keeps the id in scope for debugging


@pytest.mark.parametrize(
    "kind, category",
    [
        ("issued_deleted", "authorization_not_issued"),
        ("issued_renamed", "authorization_not_issued"),
        ("ledger_rotated", "authorization_not_issued"),
        ("ledger_deleted", "authorization_ledger_missing"),
        ("issued_garbage", "authorization_ledger_corrupt"),
        ("issued_extra_key", "authorization_ledger_corrupt"),
        ("issued_nonce_wrong_type", "authorization_ledger_corrupt"),
        ("issued_oversize", "authorization_ledger_corrupt"),
        ("issued_is_a_directory", "authorization_ledger_corrupt"),
        ("issued_wrong_nonce", "authorization_ledger_mismatch"),
        ("issued_wrong_binding", "authorization_ledger_mismatch"),
        ("issued_wrong_run_id", "authorization_ledger_mismatch"),
        ("issued_from_another_authorization", "authorization_ledger_mismatch"),
        ("tombstone_planted_empty", "authorization_already_consumed"),
        ("tombstone_is_a_directory", "authorization_already_consumed"),
    ],
)
def test_fu1_missing_corrupt_or_foreign_ledger_state_fails_closed(tmp_path, capsys, kind, category):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    _tamper(kind, env, document, capsys)
    err = _expect_replay_refused(capsys, env, category)
    assert _run_dirs(env) == []
    assert FAKE_KEY not in err and str(env.ledger) not in err


@pytest.mark.parametrize(
    "attack, category",
    [
        ("delete_tombstone", "authorization_not_issued"),
        ("rotate_ledger", "authorization_not_issued"),
        ("restore_issued_copy_keep_tombstone", "authorization_already_consumed"),
        ("rotate_ledger_and_evidence", "authorization_not_issued"),
    ],
)
def test_fu1_post_consumption_ledger_lifecycle_never_restores_authority(tmp_path, capsys, attack, category):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    copy = _issued(env, document).read_bytes()  # a copy taken before consumption
    assert _run(capsys, env)[0] == 0
    if attack == "delete_tombstone":
        _tombstone(env, document).unlink()
    elif attack == "rotate_ledger":
        _rotate(env.ledger)
    elif attack == "restore_issued_copy_keep_tombstone":
        _issued(env, document).write_bytes(copy)
    elif attack == "rotate_ledger_and_evidence":
        _rotate(env.ledger)
        _rotate(env.evidence)
    _expect_replay_refused(capsys, env, category)


def test_fu1_another_ledger_or_evidence_dir_cannot_regain_authority(tmp_path, capsys):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    # Before consumption: a copy of the ledger elsewhere is a different ledger.
    other_ledger = tmp_path / "ledger2"
    shutil.copytree(env.ledger, other_ledger)
    env.write_config(authorization_ledger_dir=str(other_ledger))
    _expect_replay_refused(capsys, env, "authorization_ledger_mismatch")
    env.write_config()
    assert _run(capsys, env)[0] == 0
    # After consumption: the pre-consumption copy in another ledger, another
    # evidence directory, or both, never reach a request.
    env.write_config(authorization_ledger_dir=str(other_ledger))
    _expect_replay_refused(capsys, env, "authorization_ledger_mismatch")
    other_evidence = tmp_path / "evidence2"
    other_evidence.mkdir()
    _expect_replay_refused(capsys, env, "evidence_dir_mismatch", evidence=other_evidence)
    env.write_config()
    _expect_replay_refused(capsys, env, "evidence_dir_mismatch", evidence=other_evidence)
    _assert_settled_spent(env, document)


def test_fu1_a_recomputed_issuance_digest_is_refused(tmp_path, capsys):
    env = Env(tmp_path)

    def forge(bound):
        bound["issuance_sha256"] = hashlib.sha256(b"0" * 64).hexdigest()
        bound["binding_sha256"] = la.compute_binding_sha256(bound)

    _consented(env, capsys, bound_edit=forge)
    _expect_replay_refused(capsys, env, "authorization_ledger_mismatch")


@pytest.mark.parametrize("field", ["issuance_sha256", "authorization_ledger_dir_sha256"])
def test_fu1_edited_ledger_bindings_are_refused(tmp_path, capsys, field):
    env = Env(tmp_path)

    def edit(bound):
        bound[field] = "0" * 64

    _consented(env, capsys, bound_edit=edit)
    _expect_replay_refused(capsys, env, "authorization_invalid")


def test_fu1_a_failed_consumption_create_sends_nothing_and_spends_nothing(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    document = _consented(env, capsys)

    def refuse_create(path, data):
        raise PermissionError("denied")

    monkeypatch.setattr(live_ledger, "_create_record_exclusive", refuse_create)
    code, _, err, server = _run(capsys, env)
    assert code == 1 and "authorization_ledger_write_failed" in err
    assert "consumed nothing" in err
    assert server.requests == [] and server.factory_calls == 0 and _run_dirs(env) == []
    assert _ledger_names(env) == [document["bound"]["run_id"] + ".issued.json"]
    monkeypatch.undo()
    # Nothing was written, so the authorization is exactly as unspent as before.
    code, _, err, server = _run(capsys, env)
    assert code == 0, err
    assert len(server.requests) == 1


def test_fu1_a_partial_consumption_record_spends_and_sends_nothing(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    document = _consented(env, capsys)

    def partial(path, data):
        Path(path).write_bytes(data[:5])
        raise OSError("disk full")

    monkeypatch.setattr(live_ledger, "_create_record_exclusive", partial)
    code, _, err, server = _run(capsys, env)
    assert code == 1 and "authorization_ledger_write_failed" in err
    assert server.requests == [] and server.factory_calls == 0
    (run_dir,) = _run_dirs(env)
    outcome = json.loads((run_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["state"] == "refused_after_consumption"
    assert outcome["transmission_attempted"] is False
    monkeypatch.undo()
    shutil.rmtree(run_dir)
    _expect_replay_refused(capsys, env)


def test_fu1_an_unremovable_issuance_record_spends_and_sends_nothing(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    document = _consented(env, capsys)

    def locked(path):
        raise PermissionError("in use")

    monkeypatch.setattr(live_ledger.os, "remove", locked)
    code, _, err, server = _run(capsys, env)
    monkeypatch.undo()
    assert code == 1 and "authorization_ledger_settle_failed" in err
    assert server.requests == [] and server.factory_calls == 0
    assert _tombstone(env, document).exists() and _issued(env, document).exists()
    # The tombstone dominates the surviving issuance record.
    _expect_replay_refused(capsys, env)
    # Deleting the surviving issuance record, or the run directory, never
    # restores authority either.
    shutil.rmtree(_run_dirs(env)[0])
    _expect_replay_refused(capsys, env)
    _issued(env, document).unlink()
    _expect_replay_refused(capsys, env)


def test_fu1_a_record_swapped_after_validation_spends_and_sends_nothing(tmp_path, capsys, monkeypatch):
    """The issuance bytes are re-checked by the tombstone's creator: a swap
    between the read-only check and consumption never transmits."""
    env = Env(tmp_path)
    document = _consented(env, capsys)
    real_create = live_ledger._create_record_exclusive

    def swap_then_create(path, data):
        issued = _issued(env, document)
        record = json.loads(issued.read_text(encoding="ascii"))
        record["issuance_nonce"] = "f" * 64
        issued.write_text(json.dumps(record), encoding="ascii")
        return real_create(path, data)

    monkeypatch.setattr(live_ledger, "_create_record_exclusive", swap_then_create)
    code, _, err, server = _run(capsys, env)
    monkeypatch.undo()
    assert code == 1 and "authorization_ledger_mismatch" in err
    assert "refused_after_consumption" in err
    assert server.requests == [] and server.factory_calls == 0
    _expect_replay_refused(capsys, env)


def test_fu1_a_run_dir_failure_after_consumption_spends_and_sends_nothing(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    document = _consented(env, capsys)
    real_mkdir = os.mkdir

    def failing_mkdir(path, *args, **kwargs):
        if os.path.normcase(os.path.dirname(str(path))) == os.path.normcase(str(env.evidence)):
            raise PermissionError("denied")
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(live.os, "mkdir", failing_mkdir)
    code, _, err, server = _run(capsys, env)
    monkeypatch.undo()
    assert code == 1 and "refused_after_consumption" in err and "evidence_write_failed" in err
    assert "Nothing was sent; the authorization ledger records the consumption." in err
    assert server.requests == [] and _run_dirs(env) == []
    _assert_settled_spent(env, document)
    _expect_replay_refused(capsys, env)


def test_fu1_an_issuance_write_failure_writes_no_draft(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)

    def refuse_create(path, data):
        raise PermissionError("denied")

    monkeypatch.setattr(live_ledger, "_create_record_exclusive", refuse_create)
    code, _, err = _prepare(capsys, env)
    assert code == 1 and "authorization_ledger_write_failed" in err
    assert not env.draft.exists() and _ledger_names(env) == []


def test_fu1_an_existing_out_writes_no_ledger_record(tmp_path, capsys):
    env = Env(tmp_path)
    env.draft.write_text("existing", encoding="utf-8")
    code, _, err = _prepare(capsys, env)
    assert code == 1 and "never overwritten" in err
    assert _ledger_names(env) == []


@pytest.mark.parametrize(
    "ledger, category",
    [
        (_ABSENT, "authorization_ledger_required"),
        (None, "authorization_ledger_required"),
        ("relative/ledger", "authorization_ledger_invalid"),
        ("MISSING", "authorization_ledger_missing"),
        ("WORKSPACE", "authorization_ledger_inside_workspace"),
        ("EVIDENCE", "authorization_ledger_not_independent"),
        ("UNDER_EVIDENCE", "authorization_ledger_not_independent"),
        ("ABOVE_EVIDENCE", "authorization_ledger_not_independent"),
    ],
)
def test_fu1_the_ledger_location_is_required_and_independent(tmp_path, capsys, ledger, category):
    env = Env(tmp_path)
    resolved = {
        "MISSING": str(tmp_path / "no-such-ledger"),
        "WORKSPACE": str(env.repo / "ledger"),
        "EVIDENCE": str(env.evidence),
        "UNDER_EVIDENCE": str(env.evidence / "ledger"),
        "ABOVE_EVIDENCE": str(tmp_path),
    }.get(ledger, ledger)
    for name in ("WORKSPACE", "UNDER_EVIDENCE"):
        if ledger == name:
            Path(resolved).mkdir()
    env.write_config(authorization_ledger_dir=resolved)
    code, _, err = _prepare(capsys, env)
    assert code == 1 and category in err, err
    assert not env.draft.exists()


@pytest.mark.parametrize("value", [1, True, ["x"]])
def test_fu1_a_forged_ledger_type_is_refused_at_load(tmp_path, capsys, value):
    env = Env(tmp_path)
    env.write_config(authorization_ledger_dir=value)
    code, _, err = _prepare(capsys, env)
    assert code == 1 and not env.draft.exists() and _ledger_names(env) == []


def test_fu1_the_ledger_is_not_part_of_p1a(tmp_path):
    """The offline P1A gate neither needs nor reads the ledger field."""
    from ai_dev_orchestrator.models import SupervisedImplementerConfig
    from ai_dev_orchestrator.supervised_implementer.implementer import (
        check_supervised_implementer_gate,
    )

    config = SupervisedImplementerConfig(enabled=True, candidate="SUP-D", model=MODEL)
    assert config.authorization_ledger_dir is None
    check_supervised_implementer_gate(config)
