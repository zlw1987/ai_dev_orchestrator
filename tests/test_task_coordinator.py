"""ALPHA-2A-T1 — the single-file task coordinator, tested entirely offline.

Every workspace is a synthetic Git repository under pytest ``tmp_path``, and the
verification program is a synthetic script written under ``tmp_path``. Both
models are ``httpx.MockTransport`` handlers: the implementer through the P1B
private transport seam (AIDO still wraps it in its own bounded counting
transport), the reviewer through the 5F2E network-transport injection point
(AIDO still wraps it in its egress transport). No socket, no real model, no
real target project and no real API key is involved.

What is proven: the four human pauses, that each stage accepts exactly its own
flags, that nothing here fills an approval or a consent, that the human may
change only the approval or consent block, that each accepted command's output
is recorded byte-exact, that the P1B ledger (never the coordinator) decides
single use, retry semantics of the write and review stages, the CRLF refusal,
the pinned project config, and the doctor's endpoint derivation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import typer

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.file_editing.models import REQUIRED_DIFF_EDIT_APPROVAL_TEXT
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.review import ReviewPacket
from ai_dev_orchestrator.supervised_implementer import live_authorization as la
from ai_dev_orchestrator.task import doctor as task_doctor
from ai_dev_orchestrator.task import preflight as task_preflight
from ai_dev_orchestrator.task import run as task_run

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="the 5F2C writer is Windows-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
]

PROJECT_ID = "demo_project"
REPO = "demo/widgets"
TARGET = "src/mod.py"
ORIGINAL = "def total(x):\n    return x\n"
PROPOSED = "def total(x):\n    return round(x, 2)\n"
IMPLEMENTER_MODEL = "qwen3.8-27b"
REVIEWER_MODEL = "fake-reviewer-model"
HOST = "fake-gateway.invalid"
BASE_URL = f"http://{HOST}:8080/v1"
FAKE_KEY = "sk-task-sentinel-KEY-1a2b3c4d5e6f7a8b9c0d"
APPROVER = "operator@example.invalid"

VALID_REVIEW = {
    "verdict": "approve",
    "summary": "The rounding change is small and in scope.",
    "findings": [
        {
            "severity": "nit",
            "category": "maintainability",
            "line": 2,
            "message": "The precision could be a named constant.",
            "suggested_action": "Consider naming the precision.",
        }
    ],
    "residual_risks": ["Totals may differ by a cent."],
    "human_notes": [],
}

PASSING_SCRIPT = """
import sys
sys.stdout.write("collected 1 item\\n1 passed\\n")
sys.exit(0)
"""

FLAG_NAMES = task_run.ALL_FLAGS
PREPARE = {"--prepare-supervised-implementation": True}
IMPLEMENT = {"--transmit-approved-source": True, "--real-implementer": True}
APPLY = {
    "--apply-approved-plan": True,
    "--write-approved-file": True,
    "--verify-approved-file-edit": True,
    "--real-reviewer": True,
}
REVIEW = {"--verify-approved-file-edit": True, "--real-reviewer": True}


# -- synthetic setup ---------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _make_repo(tmp_path: Path, original: bytes = ORIGINAL.encode("utf-8")) -> Path:
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
    (repo / "src" / "mod.py").write_bytes(original)
    (repo / "src" / "other.py").write_bytes(b"OTHER = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


def _config(repo: Path, tmp_path: Path, script: Path, *, review_enabled: bool = True) -> dict:
    return {
        "project_id": PROJECT_ID,
        "display_name": "Demo",
        "repo": {
            "workspace_path": str(repo),
            "github_repo": REPO,
            "default_base_branch": "main",
            "branch_prefix": "ai/demo",
        },
        "allowed_paths": ["src/**"],
        "protected_paths": ["src/protected/**"],
        "forbidden_paths": [".git/**"],
        "read_only_workspace_content": {"enabled": True},
        "workspace_write": {"enabled": True, "max_file_bytes": 200000},
        "controlled_verification": {
            "enabled": True,
            "executable": sys.executable,
            "args": [str(script)],
            "timeout_seconds": 60,
            "max_output_bytes": 200000,
        },
        "controlled_review": {
            "enabled": review_enabled,
            "provider": "litellm",
            "model": REVIEWER_MODEL,
            "endpoint": {"scheme": "http", "host": HOST, "port": 8080, "base_path": "/v1"},
        },
        "supervised_implementer": {
            "enabled": True,
            "live_transmission_enabled": True,
            "candidate": "SUP-D",
            "provider": "litellm",
            "model": IMPLEMENTER_MODEL,
            "allow_insecure_http": True,
            "structured_output": False,
            "attempt_timeout_seconds": 30.0,
            "authorization_ledger_dir": str(tmp_path / "ledger"),
        },
    }


class Env:
    def __init__(self, tmp_path: Path, *, original: bytes = ORIGINAL.encode("utf-8"), **config_kw) -> None:
        import yaml

        self.tmp = tmp_path
        self.repo = _make_repo(tmp_path, original)
        (tmp_path / "ledger").mkdir()
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        self.script = scripts / "verify.py"
        self.script.write_text(textwrap.dedent(PASSING_SCRIPT), encoding="utf-8")
        self.ops = tmp_path / "operator"
        self.ops.mkdir()
        self.config = self.ops / "project.yaml"
        self.config.write_text(
            yaml.safe_dump(_config(self.repo, tmp_path, self.script, **config_kw)), encoding="utf-8"
        )
        self.runs_root = tmp_path / "runs"
        self.implementer = Server(lambda request: httpx.Response(200, json=_implementer_reply(PROPOSED)))
        self.reviewer = Server(lambda request: httpx.Response(200, json=_reviewer_reply(VALID_REVIEW)))
        self.run_dir: Path | None = None

    def project(self) -> ProjectConfig:
        import yaml

        return ProjectConfig.model_validate(yaml.safe_load(self.config.read_text(encoding="utf-8")))


class Server:
    def __init__(self, respond) -> None:
        self.respond = respond
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)

    def factory(self):
        return httpx.MockTransport(self.handler)


def _implementer_reply(content_text: str) -> dict:
    return {
        "id": "cmpl-impl",
        "model": IMPLEMENTER_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json.dumps({"content_text": content_text})},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


def _reviewer_reply(review: dict) -> dict:
    return {
        "model": REVIEWER_MODEL,
        "choices": [
            {"message": {"role": "assistant", "content": json.dumps(review)}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 321, "completion_tokens": 64, "total_tokens": 385},
    }


def _env_values() -> dict[str, str]:
    return {
        "AIDO_LITELLM_BASE_URL": BASE_URL,
        "AIDO_LITELLM_API_KEY": FAKE_KEY,
        "AIDO_LITELLM_DEFAULT_MODEL": "env-default-model-must-not-be-used",
        "AIDO_LITELLM_MAX_RETRIES": "7",
        "AIDO_LITELLM_TIMEOUT_SECONDS": "999",
    }


def _reader(calls: list[str] | None = None):
    def read(provider: str) -> dict[str, str]:
        if calls is not None:
            calls.append(provider)
        return _env_values()

    return read


def _never_read(provider: str):
    raise AssertionError("no environment may be read on this path")


def _invoke(capsys, function, **kwargs) -> tuple[int, str, str]:
    capsys.readouterr()
    code = 0
    try:
        function(**kwargs)
    except typer.Exit as exc:
        code = exc.exit_code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _start(capsys, env: Env, **overrides) -> tuple[int, str, str]:
    kwargs = {
        "project_config": env.config,
        "title": "Round totals",
        "issue": 7,
        "target_path": TARGET,
        "description": "Round the total to two decimal places.",
        "description_file": None,
        "runs_root": env.runs_root,
    }
    kwargs.update(overrides)
    result = _invoke(capsys, cli._run_task_start, **kwargs)
    runs = sorted(env.runs_root.iterdir()) if env.runs_root.is_dir() else []
    env.run_dir = runs[-1] if runs else None
    return result


def _continue(capsys, env: Env, flags: dict | None = None, *, implementer_env=None, reviewer_env=None):
    return _invoke(
        capsys,
        cli._run_task_continue,
        run_dir=env.run_dir,
        flags=dict(flags or {}),
        read_implementer_env=implementer_env or _reader(),
        read_reviewer_env=reviewer_env or _reader(),
        reviewer_transport_factory=env.reviewer.factory,
        _implementer_transport_factory=env.implementer.factory,
    )


def _status(capsys, env: Env) -> str:
    code, out, err = _invoke(capsys, cli._run_task_status, run_dir=env.run_dir)
    assert code == 0, err
    return out


def _stage(env: Env) -> str:
    return task_run.derive_stage(task_run.load_task(str(env.run_dir))).name


def _fill_approval(path: Path, text: str) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    document["approval"] = {
        "approved_by": APPROVER,
        "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "approval_text": text,
        "source": "manual",
    }
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def _approve_plan(env: Env) -> None:
    _fill_approval(env.run_dir / task_run.PLAN_DRAFT_FILE, REQUIRED_APPROVAL_TEXT)


def _consent(env: Env) -> None:
    path = sorted(env.run_dir.glob("20-authorization-*.json"))[-1]
    document = json.loads(path.read_text(encoding="utf-8"))
    document["consent"] = {
        "consented_by": APPROVER,
        "consented_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "manual",
        "binding_sha256": document["bound"]["binding_sha256"],
        "endpoint_scheme": "http",
        "endpoint_host": HOST,
        "endpoint_port": 8080,
        "consent_text": la.CONSENT_TEXT,
        "plaintext_acknowledgement": la.PLAINTEXT_ACKNOWLEDGEMENT,
    }
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def _approve_diff(env: Env) -> None:
    _fill_approval(env.run_dir / task_run.DIFF_DRAFT_FILE, REQUIRED_DIFF_EDIT_APPROVAL_TEXT)


def _to_diff_approval(capsys, env: Env) -> None:
    code, _, err = _start(capsys, env)
    assert code == 0, err
    _approve_plan(env)
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 0, err
    _consent(env)
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 0, err
    assert _stage(env) == "diff_approval"


def _workspace(repo: Path) -> tuple[str, str, bytes]:
    return _git(repo, "rev-parse", "HEAD"), _git(repo, "status", "--porcelain"), (repo / TARGET).read_bytes()


def _steps(env: Env) -> list[str]:
    return sorted(path.name for path in (env.run_dir / task_run.STEPS_DIR).iterdir())


def _tree(directory: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


# -- 1. the whole task, with its four human pauses ----------------------------------------


def test_one_task_runs_end_to_end_with_four_human_pauses(tmp_path, capsys):
    env = Env(tmp_path)
    head_before = _git(env.repo, "rev-parse", "HEAD")

    code, _, err = _start(capsys, env)
    assert code == 0, err
    assert "plan_approval" in err
    assert _stage(env) == "plan_approval"
    draft = json.loads((env.run_dir / task_run.PLAN_DRAFT_FILE).read_text(encoding="utf-8"))
    assert draft["approval"] == task_run.EMPTY_APPROVAL
    assert draft["plan"]["files_likely_to_change"] == [TARGET]
    assert draft["plan"]["summary"] == "Round the total to two decimal places."

    # Pause 1: the plan approval.
    _approve_plan(env)
    code, _, err = _continue(capsys, env, PREPARE, implementer_env=_never_read, reviewer_env=_never_read)
    assert code == 0, err
    assert _stage(env) == "implementer_consent"
    assert env.implementer.requests == []

    # Pause 2: the implementer consent.
    _consent(env)
    implementer_calls: list[str] = []
    code, out, err = _continue(
        capsys, env, IMPLEMENT, implementer_env=_reader(implementer_calls), reviewer_env=_never_read
    )
    assert code == 0, err
    assert implementer_calls == ["litellm"]
    assert len(env.implementer.requests) == 1
    assert _stage(env) == "diff_approval"
    diff_text = (env.run_dir / task_run.DIFF_TEXT_FILE).read_text(encoding="utf-8")
    assert "+    return round(x, 2)" in diff_text
    diff_draft = json.loads((env.run_dir / task_run.DIFF_DRAFT_FILE).read_text(encoding="utf-8"))
    assert diff_draft["approval"] == task_run.EMPTY_APPROVAL
    assert diff_draft["schema_version"] == "approved-diff-proposal.v2"
    assert _workspace(env.repo)[2] == ORIGINAL.encode("utf-8")

    # Pause 3: the exact-diff approval. Then write, verify, review.
    _approve_diff(env)
    reviewer_calls: list[str] = []
    code, out, err = _continue(capsys, env, APPLY, reviewer_env=_reader(reviewer_calls))
    assert code == 0, err
    assert reviewer_calls == ["litellm"]
    assert len(env.reviewer.requests) == 1
    assert len(env.implementer.requests) == 1

    # Pause 4: AIDO is done; the decision is the human's.
    assert _stage(env) == "awaiting_human_decision"
    head, status, target = _workspace(env.repo)
    assert head == head_before
    assert status == f" M {TARGET}\n"
    assert target == PROPOSED.encode("utf-8")

    steps = _steps(env)
    assert [name.split(".")[0] for name in steps if name.endswith(".stdout")] == [
        "01-prepare", "02-implementer-run", "03-apply", "04-review",
    ]
    review_stdout = env.run_dir / task_run.STEPS_DIR / "04-review.exit-0.stdout"
    packet_text = review_stdout.read_text(encoding="utf-8")
    packet = ReviewPacket.model_validate_json(packet_text)
    assert packet.review.verdict == "approve"
    assert packet.verification.outcome == "verified"
    # Byte-exact: the recorded packet is what the command printed.
    assert packet_text in out
    review_stderr = (env.run_dir / task_run.STEPS_DIR / "04-review.exit-0.stderr").read_text(encoding="utf-8")
    assert "REAL REVIEWER MODEL CALL COMPLETED" in review_stderr
    implementer_stdout = (env.run_dir / task_run.STEPS_DIR / "02-implementer-run.exit-0.stdout").read_text(
        encoding="utf-8"
    )
    assert json.loads(implementer_stdout)["schema_version"] == "supervised-implementer-provenance.v2"

    summary = (env.run_dir / task_run.SUMMARY_FILE).read_text(encoding="utf-8")
    assert "NOT itself" in summary and "evidence" in summary
    assert "Reviewer model claims (NOT verified by AIDO)" in summary
    assert "READY FOR YOUR DECISION" in summary

    # A finished run cannot be continued.
    code, _, err = _continue(capsys, env, REVIEW)
    assert code == 1 and "finished" in err


def test_no_credential_reaches_the_run_directory(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    code, _, err = _continue(capsys, env, APPLY)
    assert code == 0, err
    text = "\n".join(data.decode("utf-8", "replace") for data in _tree(env.run_dir).values())
    assert FAKE_KEY not in text
    assert BASE_URL not in text


# -- 2. each stage accepts exactly its own flags --------------------------------------------


@pytest.mark.parametrize(
    "flags",
    [
        {},
        IMPLEMENT,
        APPLY,
        REVIEW,
        {**PREPARE, **IMPLEMENT},
        {**PREPARE, "--real-reviewer": True},
    ],
)
def test_the_plan_stage_refuses_any_other_flag_set_and_does_nothing(tmp_path, capsys, flags):
    env = Env(tmp_path)
    _start(capsys, env)
    _approve_plan(env)
    before = _tree(env.run_dir)
    code, _, err = _continue(capsys, env, flags, implementer_env=_never_read, reviewer_env=_never_read)
    assert code == 1
    assert "accepts exactly" in err and "Nothing was done" in err
    assert _tree(env.run_dir) == before


def test_the_diff_stage_refuses_the_implementer_flags(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    before = _workspace(env.repo)
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 1 and "accepts exactly" in err
    assert len(env.implementer.requests) == 1
    assert _workspace(env.repo) == before
    assert not (env.run_dir / task_run.DIFF_APPROVED_FILE).exists()


def test_the_diff_stage_refuses_review_flags_alone(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    code, _, err = _continue(capsys, env, REVIEW)
    assert code == 1 and "accepts exactly" in err
    assert env.reviewer.requests == []


# -- 3. nothing here approves or consents -------------------------------------------------


def test_an_unfilled_plan_approval_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _start(capsys, env)
    code, _, err = _continue(capsys, env, PREPARE, implementer_env=_never_read)
    assert code == 1 and "not filled in" in err
    assert not (env.run_dir / task_run.PLAN_APPROVED_FILE).exists()
    assert task_run.authorization_paths(task_run.load_task(str(env.run_dir))) == []


def test_a_paraphrased_plan_approval_is_refused_by_the_accepted_parser(tmp_path, capsys):
    env = Env(tmp_path)
    _start(capsys, env)
    _fill_approval(env.run_dir / task_run.PLAN_DRAFT_FILE, "I approve this plan")
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 1 and "accepted parser" in err
    assert not (env.run_dir / task_run.PLAN_APPROVED_FILE).exists()


def test_an_unconsented_authorization_sends_nothing(tmp_path, capsys):
    env = Env(tmp_path)
    _start(capsys, env)
    _approve_plan(env)
    _continue(capsys, env, PREPARE)
    code, _, _ = _continue(capsys, env, IMPLEMENT)
    assert code == 1
    assert env.implementer.requests == []
    assert _stage(env) == "implementer_consent"


def test_an_unfilled_diff_approval_writes_nothing(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff_approval(capsys, env)
    before = _workspace(env.repo)
    code, _, err = _continue(capsys, env, APPLY)
    assert code == 1 and "not filled in" in err
    assert _workspace(env.repo) == before
    assert env.reviewer.requests == []


def test_the_coordinator_source_never_writes_an_approval_value():
    source = Path(task_run.__file__).read_text(encoding="utf-8")
    for phrase in ("I approve this", "consent_text", "CONSENT_TEXT", "PLAINTEXT_ACKNOWLEDGEMENT"):
        assert phrase not in source


# -- 4. only the approval block may change -----------------------------------------------------


def test_an_edited_plan_body_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _start(capsys, env)
    path = env.run_dir / task_run.PLAN_DRAFT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    document["plan"]["files_likely_to_change"] = [TARGET, "src/other.py"]
    path.write_text(json.dumps(document), encoding="utf-8")
    _approve_plan(env)
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 1 and "outside its 'approval'" in err
    assert not (env.run_dir / task_run.PLAN_APPROVED_FILE).exists()


def test_a_duplicate_key_in_the_plan_is_refused(tmp_path, capsys):
    env = Env(tmp_path)
    _start(capsys, env)
    _approve_plan(env)
    path = env.run_dir / task_run.PLAN_DRAFT_FILE
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"project_id"', '"project_id": "x", "project_id"', 1), encoding="utf-8")
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 1 and "duplicate JSON key" in err


def test_an_edited_diff_is_refused_and_nothing_is_written(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff_approval(capsys, env)
    path = env.run_dir / task_run.DIFF_DRAFT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    change = document["diff_proposal"]["changes"][0]
    change["unified_diff"] = change["unified_diff"].replace("round(x, 2)", "round(x, 3)")
    path.write_text(json.dumps(document), encoding="utf-8")
    _approve_diff(env)
    before = _workspace(env.repo)
    code, _, err = _continue(capsys, env, APPLY)
    assert code == 1 and "outside its 'approval'" in err
    assert _workspace(env.repo) == before
    assert env.reviewer.requests == []


def test_the_frozen_approval_is_the_exact_bytes_the_human_saved(tmp_path, capsys):
    env = Env(tmp_path)
    _start(capsys, env)
    _approve_plan(env)
    saved = (env.run_dir / task_run.PLAN_DRAFT_FILE).read_bytes()
    _continue(capsys, env, PREPARE)
    assert (env.run_dir / task_run.PLAN_APPROVED_FILE).read_bytes() == saved


# -- 5. the ledger, not the coordinator, decides single use -------------------------------------


def test_deleting_the_implementer_evidence_cannot_replay_the_authorization(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff_approval(capsys, env)
    shutil.rmtree(env.run_dir / task_run.EVIDENCE_DIR)
    (env.run_dir / task_run.EVIDENCE_DIR).mkdir()
    assert _stage(env) == "implementer_consent"
    code, _, _ = _continue(capsys, env, IMPLEMENT)
    assert code == 1
    assert len(env.implementer.requests) == 1


def test_a_fresh_authorization_can_be_issued_before_consumption(tmp_path, capsys):
    env = Env(tmp_path)
    _start(capsys, env)
    _approve_plan(env)
    _continue(capsys, env, PREPARE)
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 0, err
    task = task_run.load_task(str(env.run_dir))
    assert [os.path.basename(p) for p in task_run.authorization_paths(task)] == [
        "20-authorization-1.json", "20-authorization-2.json",
    ]
    _consent(env)
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 0, err
    assert _stage(env) == "diff_approval"


# -- 6. terminal implementer outcomes ---------------------------------------------------------


def test_a_no_change_reply_ends_the_task(tmp_path, capsys):
    env = Env(tmp_path)
    env.implementer.respond = lambda request: httpx.Response(200, json=_implementer_reply(ORIGINAL))
    _start(capsys, env)
    _approve_plan(env)
    _continue(capsys, env, PREPARE)
    _consent(env)
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 0, err
    assert _stage(env) == "no_change_proposed"
    assert not (env.run_dir / task_run.DIFF_DRAFT_FILE).exists()


def test_an_implementer_failure_is_terminal(tmp_path, capsys):
    env = Env(tmp_path)
    env.implementer.respond = lambda request: httpx.Response(500, json={"error": "boom"})
    _start(capsys, env)
    _approve_plan(env)
    _continue(capsys, env, PREPARE)
    _consent(env)
    code, _, _ = _continue(capsys, env, IMPLEMENT)
    assert code == 4
    assert _stage(env) == "implementer_failed"
    code, _, err = _continue(capsys, env, IMPLEMENT)
    assert code == 1 and "finished" in err
    assert len(env.implementer.requests) == 1


# -- 7. write and review retries ----------------------------------------------------------------


def test_a_refused_write_can_be_retried_after_the_human_fixes_the_workspace(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    stray = env.repo / "src" / "stray.py"
    stray.write_text("STRAY = 1\n", encoding="utf-8")
    code, _, _ = _continue(capsys, env, APPLY)
    assert code == 1
    assert _stage(env) == "apply_pending"
    assert (env.repo / TARGET).read_bytes() == ORIGINAL.encode("utf-8")
    assert env.reviewer.requests == []
    stray.unlink()
    code, _, err = _continue(capsys, env, APPLY)
    assert code == 0, err
    assert _stage(env) == "awaiting_human_decision"


def test_a_reviewer_failure_can_be_retried_with_the_review_flags(tmp_path, capsys):
    env = Env(tmp_path)
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    env.reviewer.respond = lambda request: httpx.Response(200, json=_reviewer_reply({"verdict": "maybe"}))
    code, _, _ = _continue(capsys, env, APPLY)
    assert code == 4
    assert _stage(env) == "review_pending"
    assert not (env.run_dir / task_run.SUMMARY_FILE).exists()
    env.reviewer.respond = lambda request: httpx.Response(200, json=_reviewer_reply(VALID_REVIEW))
    code, _, err = _continue(capsys, env, APPLY)
    assert code == 1 and "accepts exactly" in err
    code, _, err = _continue(capsys, env, REVIEW)
    assert code == 0, err
    assert _stage(env) == "awaiting_human_decision"
    assert [name for name in _steps(env) if name.endswith(".stdout")][-2:] == [
        "04-review.exit-4.stdout", "05-review.exit-0.stdout",
    ]


def test_a_verification_that_dirties_the_tree_is_terminal(tmp_path, capsys):
    env = Env(tmp_path)
    env.script.write_text(
        "open('stray_artifact.txt', 'w').write('x')\nprint('done')\n", encoding="utf-8"
    )
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    code, _, _ = _continue(capsys, env, APPLY)
    assert code == 3
    assert _stage(env) == "workspace_untrusted"
    assert env.reviewer.requests == []


def test_a_runner_that_raises_is_recorded_and_needs_inspection(tmp_path, capsys, monkeypatch):
    env = Env(tmp_path)
    _to_diff_approval(capsys, env)
    _approve_diff(env)

    def explode(**kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(cli, "_run_l2_apply_approved_file_edit", explode)
    code, _, _ = _continue(capsys, env, APPLY)
    assert code == 1
    assert "03-apply.exit-error.stderr" in _steps(env)
    assert _stage(env) == "write_needs_inspection"
    assert env.reviewer.requests == []


# -- 8. pinned config, CRLF, and start-time refusals ---------------------------------------------


def test_a_changed_project_config_refuses_every_later_step(tmp_path, capsys):
    env = Env(tmp_path)
    _start(capsys, env)
    _approve_plan(env)
    env.config.write_text(env.config.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 1 and "config changed" in err
    code, _, err = _invoke(capsys, cli._run_task_status, run_dir=env.run_dir)
    assert code == 1 and "config changed" in err


def test_a_crlf_target_is_refused_before_anything_is_prepared(tmp_path, capsys):
    env = Env(tmp_path, original=ORIGINAL.replace("\n", "\r\n").encode("utf-8"))
    _start(capsys, env)
    _approve_plan(env)
    code, _, err = _continue(capsys, env, PREPARE)
    assert code == 1 and "CRLF" in err
    assert (env.run_dir / task_run.PLAN_APPROVED_FILE).exists()
    assert task_run.authorization_paths(task_run.load_task(str(env.run_dir))) == []
    assert list((tmp_path / "ledger").iterdir()) == []


def test_start_refuses_a_closed_gate_and_writes_nothing(tmp_path, capsys):
    env = Env(tmp_path, review_enabled=False)
    code, _, err = _start(capsys, env)
    assert code == 1 and "controlled_review" in err
    assert not env.runs_root.exists()


# -- ALPHA-2A-T3: the read_only_workspace_content opt-in that prepare needs ----------------------

_READ_ONLY_STATES = ["missing", "disabled"]


def _set_read_only_content(env: Env, state: str) -> None:
    """Rewrite the config's read_only_workspace_content block: missing, disabled or enabled."""
    import yaml

    config = yaml.safe_load(env.config.read_text(encoding="utf-8"))
    if state == "missing":
        del config["read_only_workspace_content"]
    else:
        config["read_only_workspace_content"] = {"enabled": state == "enabled"}
    env.config.write_text(yaml.safe_dump(config), encoding="utf-8")


@pytest.mark.parametrize("state,expected", [("missing", False), ("disabled", False), ("enabled", True)])
def test_the_read_only_content_predicate_matches_the_5d2_opt_in(tmp_path, state, expected):
    env = Env(tmp_path)
    _set_read_only_content(env, state)
    assert task_doctor.read_only_content_enabled(env.project()) is expected


@pytest.mark.parametrize("state", _READ_ONLY_STATES)
def test_start_refuses_without_read_only_content_and_creates_no_run(tmp_path, capsys, state):
    env = Env(tmp_path)
    _set_read_only_content(env, state)
    code, _, err = _start(capsys, env)
    assert code == 1
    assert "read_only_workspace_content.enabled must be true" in err
    assert "Nothing was written" in err
    assert not env.runs_root.exists()
    assert list((tmp_path / "ledger").iterdir()) == []


def test_start_with_read_only_content_enabled_reaches_plan_approval(tmp_path, capsys):
    env = Env(tmp_path)
    _set_read_only_content(env, "enabled")
    code, _, err = _start(capsys, env)
    assert code == 0, err
    assert _stage(env) == "plan_approval"


@pytest.mark.parametrize("state", _READ_ONLY_STATES)
def test_the_doctor_reports_missing_or_disabled_read_only_content(tmp_path, capsys, state):
    env = Env(tmp_path)
    _set_read_only_content(env, state)
    environ = SpyEnviron(_env_values())
    code, out, _ = _invoke(capsys, cli._run_task_doctor, project_config=env.config, target_path=TARGET, environ=environ)
    assert code == 1
    assert "[FIX] read_only_workspace_content.enabled must be true" in out
    # Every other gate is still reported, and the read set is unchanged.
    assert "[OK] workspace_write.enabled" in out
    assert "MATCHES AIDO_LITELLM_BASE_URL" in out
    assert environ.looked_up == ["AIDO_LITELLM_BASE_URL"]
    assert not env.runs_root.exists()


def test_the_doctor_reports_enabled_read_only_content_ok(tmp_path, capsys):
    env = Env(tmp_path)
    _set_read_only_content(env, "enabled")
    code, out, _ = _invoke(capsys, cli._run_task_doctor, project_config=env.config, target_path=TARGET, environ=_env_values())
    assert code == 0, out
    assert "[OK] read_only_workspace_content.enabled" in out
    assert "[FIX]" not in out


def test_start_refuses_runs_root_inside_the_workspace(tmp_path, capsys):
    env = Env(tmp_path)
    code, _, err = _start(capsys, env, runs_root=env.repo / "runs")
    assert code == 1 and "inside the project's configured workspace" in err
    assert not (env.repo / "runs").exists()


def test_start_refuses_a_description_file_inside_the_workspace(tmp_path, capsys):
    env = Env(tmp_path)
    inside = env.repo / "notes.txt"
    code, _, err = _start(capsys, env, description=None, description_file=inside)
    assert code == 1 and "--description-file" in err


@pytest.mark.parametrize("target", ["../x.py", "/abs.py", "src\\mod.py", "C:/x.py", "src//mod.py", ""])
def test_start_refuses_a_malformed_target(tmp_path, capsys, target):
    env = Env(tmp_path)
    code, _, _ = _start(capsys, env, target_path=target)
    assert code == 1
    assert not env.runs_root.exists() or list(env.runs_root.iterdir()) == []


def test_status_is_read_only(tmp_path, capsys):
    env = Env(tmp_path)
    _start(capsys, env)
    before = _tree(env.run_dir)
    out = _status(capsys, env)
    assert "plan_approval" in out
    assert "--prepare-supervised-implementation" in out
    assert _tree(env.run_dir) == before


# -- 9. no new execution surface ------------------------------------------------------------------


@pytest.mark.parametrize("module", [task_run, task_doctor, task_preflight])
def test_the_task_modules_import_no_process_socket_or_client(module):
    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in ("import subprocess", "import socket", "LLMClient(", "httpx.Client(", "os.system"):
        assert forbidden not in source


# -- 10. the doctor ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("http://fake-gateway.invalid:8080/v1", ("http", "fake-gateway.invalid", 8080, "/v1")),
        ("http://fake-gateway.invalid:8080/v1/", ("http", "fake-gateway.invalid", 8080, "/v1")),
        ("https://fake-gateway.invalid/v1", ("https", "fake-gateway.invalid", 443, "/v1")),
        ("http://10.0.0.5", ("http", "10.0.0.5", 80, "")),
        # httpx resolves dot segments; the block shows the path actually requested.
        ("http://fake-gateway.invalid/v1/../x", ("http", "fake-gateway.invalid", 80, "/x")),
    ],
)
def test_the_endpoint_is_derived_with_the_reviewers_own_parse(base_url, expected):
    endpoint = task_doctor.derive_endpoint(base_url)
    assert (endpoint.scheme, endpoint.host, endpoint.port, endpoint.base_path) == expected


@pytest.mark.parametrize(
    "base_url",
    [
        "http://user:pw@fake-gateway.invalid/v1",
        "http://fake-gateway.invalid/v1?key=SECRETQUERY",
        "http://fake-gateway.invalid/v1#frag",
        "ftp://fake-gateway.invalid/v1",
        "",
    ],
)
def test_an_inexpressible_base_url_is_refused_unechoed(base_url):
    with pytest.raises(task_doctor.EndpointDerivationError) as info:
        task_doctor.derive_endpoint(base_url)
    assert "SECRETQUERY" not in str(info.value) and "pw" not in str(info.value)


class SpyEnviron(dict):
    """Records every name looked up; refuses to hand out an API key value."""

    def __init__(self, values):
        super().__init__(values)
        self.looked_up: list[str] = []

    def get(self, name, default=None):
        self.looked_up.append(name)
        if "API_KEY" in name:
            raise AssertionError("the doctor must never read a key value")
        return super().get(name, default)

    def __getitem__(self, name):
        self.looked_up.append(name)
        raise AssertionError("the doctor must never index the environment")


def test_the_doctor_matches_and_reads_only_the_base_url_value(tmp_path, capsys):
    env = Env(tmp_path)
    environ = SpyEnviron(_env_values())
    code, out, _ = _invoke(capsys, cli._run_task_doctor, project_config=env.config, target_path=TARGET, environ=environ)
    assert code == 0, out
    assert environ.looked_up == ["AIDO_LITELLM_BASE_URL"]
    assert "MATCHES AIDO_LITELLM_BASE_URL" in out
    assert 'host: "fake-gateway.invalid"' in out
    assert "wholly clean" in out
    assert FAKE_KEY not in out


def test_the_doctor_reports_a_mismatch_and_prints_the_block(tmp_path, capsys):
    env = Env(tmp_path)
    values = _env_values()
    values["AIDO_LITELLM_BASE_URL"] = "http://other-gateway.invalid:9000/v2"
    code, out, _ = _invoke(capsys, cli._run_task_doctor, project_config=env.config, target_path=None, environ=values)
    assert code == 1
    assert "does NOT match" in out
    assert 'host: "other-gateway.invalid"' in out and "port: 9000" in out and 'base_path: "/v2"' in out


def test_the_doctor_never_writes_the_config(tmp_path, capsys):
    env = Env(tmp_path)
    before = env.config.read_bytes()
    values = _env_values()
    values["AIDO_LITELLM_BASE_URL"] = "http://other-gateway.invalid:9000/v2"
    _invoke(capsys, cli._run_task_doctor, project_config=env.config, target_path=None, environ=values)
    assert env.config.read_bytes() == before


def test_the_doctor_prints_implementer_consent_values_only_for_a_litellm_reviewer(tmp_path, capsys):
    import yaml

    env = Env(tmp_path)
    _, out, _ = _invoke(capsys, cli._run_task_doctor, project_config=env.config, target_path=None, environ=_env_values())
    assert "Implementer consent values" in out

    config = yaml.safe_load(env.config.read_text(encoding="utf-8"))
    config["controlled_review"]["provider"] = "vllm"
    config["controlled_review"]["vllm_allow_insecure_http"] = True
    env.config.write_text(yaml.safe_dump(config), encoding="utf-8")
    values = {"AIDO_VLLM_BASE_URL": "http://fake-gateway.invalid:8080/v1"}
    _, out, _ = _invoke(capsys, cli._run_task_doctor, project_config=env.config, target_path=None, environ=values)
    assert "MATCHES AIDO_VLLM_BASE_URL" in out
    assert "Implementer consent values" not in out
