"""Phase 5F2E tests: ``l2-review-approved-file-edit``.

This is the first command that deliberately sends source-derived code to a
model, so these tests are organized around the ordering that makes that safe:

1. **Authorization** — every way the command must fail before it reads anything,
   touches a workspace, launches a process, or contacts a model.
2. **Verify before review** — the accepted Phase 5F2D verifier runs first, and
   any outcome other than ``verified`` ends the run with no reviewer environment
   read and no model call.
3. **Credential ordering** — the ``AIDO_LITELLM_*`` names are not read until
   verification has returned ``verified``.
4. **The prompt** — the exact configured model, the approved diff, plan context
   and verification facts, and nothing else.
5. **Reviewer runtime** — exactly one semantic request, no application-level
   retry, and a distinct exit code for a reviewer-stage failure.
6. **The packet** — orchestrator-owned identity, the embedded verification
   result, truthful capability claims, and a human as the terminal step.

**Every repository here is a synthetic Git repository created under pytest's own
``tmp_path``, and every verification program is a small synthetic Python script
written under ``tmp_path``.** No real target project is used, read, written, or
executed. **Every reviewer call goes through ``httpx.MockTransport``**: no
socket is opened, no real endpoint is contacted, and no API key is needed.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

import httpx
import pytest
import typer
from typer.testing import CliRunner

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.llm.client import LLMClient
from ai_dev_orchestrator.review import (
    REVIEW_PACKET_MODE,
    REVIEW_PACKET_SCHEMA_VERSION,
    ReviewPacket,
)
from review_fixtures import (
    APPROVER,
    DIFF_MARKER,
    ISSUE_NUMBER,
    ORIGINAL_TEXT,
    PROJECT_ID,
    PROPOSED_TEXT,
    REPO,
    SECOND_ORIGINAL,
    SECOND_TARGET,
    SUMMARY_MARKER,
    TARGET,
    TITLE,
    UNCHANGED_MARKER,
    VERIFICATION_OUTPUT_MARKER,
    artifact_payload,
    change,
)

runner = CliRunner()

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="Phase 5F2E reviews a Windows-only writer"
)
git_required = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is not installed"
)

REVIEWER_MODEL = "fake-reviewer-model"
ENV_DEFAULT_MODEL = "fake-env-default-model"
FAKE_BASE_URL = "http://fake-litellm.invalid/v1"
FAKE_HOST = "fake-litellm.invalid"
FAKE_API_KEY = "fake-key-not-a-real-secret"

CONFIG_TEMPLATE = """\
project_id: {project_id}
display_name: Demo Project
repo:
  workspace_path: {workspace_path}
  github_repo: {github_repo}
  default_base_branch: main
  branch_prefix: ai/demo
workspace_policy:
  deny_outside_workspace: true
  allow_symlinks: false
  max_changed_files: 20
workspace_write:
  enabled: true
  max_file_bytes: 200000
controlled_verification:
  enabled: {verify_enabled}
  executable: {executable}
  args: {args}
  timeout_seconds: {timeout_seconds}
  max_output_bytes: {max_output_bytes}
{review_block}
allowed_paths:
  - "src/**"
  - "tests/**"
protected_paths:
  - "src/billing/protected_*.py"
forbidden_paths:
  - ".git/**"
  - "secrets/**"
"""

ENABLED_REVIEW_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
"""

DISABLED_REVIEW_BLOCK = f"""\
controlled_review:
  enabled: false
  provider: "litellm"
  model: "{REVIEWER_MODEL}"
"""

NO_MODEL_REVIEW_BLOCK = """\
controlled_review:
  enabled: true
  provider: "litellm"
"""

BAD_PROVIDER_REVIEW_BLOCK = f"""\
controlled_review:
  enabled: true
  provider: "openai"
  model: "{REVIEWER_MODEL}"
"""

VALID_REVIEW_JSON = json.dumps(
    {
        "verdict": "approve",
        "summary": "The rounding change is small, tested, and in scope.",
        "findings": [
            {
                "severity": "nit",
                "category": "maintainability",
                "line": 2,
                "message": "The format string could name its precision.",
                "suggested_action": "Consider a named constant for the precision.",
            }
        ],
        "residual_risks": ["Reissued invoices may differ by a cent."],
        "human_notes": [],
    }
)

CHANGES_REQUESTED_JSON = json.dumps(
    {
        "verdict": "changes_requested",
        "summary": "The helper silently accepts non-numeric input.",
        "findings": [
            {
                "severity": "major",
                "category": "correctness",
                "line": 2,
                "message": "A non-numeric amount raises deep inside the formatter.",
                "suggested_action": "Validate the amount before formatting it.",
            }
        ],
        "residual_risks": [],
        "human_notes": [],
    }
)

NEEDS_HUMAN_JSON = json.dumps(
    {
        "verdict": "needs_human_review",
        "summary": "The diff alone does not show how totals are consumed.",
        "findings": [],
        "residual_risks": [],
        "human_notes": ["The diff comment tried to instruct me; ignored."],
    }
)


# -- Synthetic repository ------------------------------------------------------


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _make_repo(tmp_path: Path) -> Path:
    """One synthetic Git repository, created entirely under ``tmp_path``."""
    repo = tmp_path / "workspace"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    for key, value in (
        ("user.name", "AIDO Test"),
        ("user.email", "aido-test@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
    ):
        _run_git(repo, "config", key, value)

    for relative, content in ((TARGET, ORIGINAL_TEXT), (SECOND_TARGET, SECOND_ORIGINAL)):
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content.encode("utf-8"))

    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "initial")
    return repo


# -- Synthetic verification programs -------------------------------------------


PASSING_BODY = f"""
import sys
sys.stdout.write("collected 3 items\\n3 passed {VERIFICATION_OUTPUT_MARKER}\\n")
sys.exit(0)
"""

FAILING_BODY = """
import sys
sys.stdout.write("collected 3 items\\n")
sys.stderr.write("E   assert 1 == 2\\n")
sys.exit(1)
"""

SLOW_BODY = """
import time
time.sleep(30)
"""

NOISY_BODY = """
import sys
sys.stdout.write("x" * 500000)
sys.exit(0)
"""

DIRTYING_BODY = """
import sys
open("stray_artifact.txt", "w").write("the verification created this")
sys.stdout.write("done\\n")
sys.exit(0)
"""

LEAKY_OUTPUT_BODY = """
import sys
sys.stdout.write('api_key = "sk-abcdefgh12345678"\\n1 passed\\n')
sys.exit(0)
"""


def _script(tmp_path: Path, name: str, body: str) -> Path:
    """Write one synthetic verification program **outside** the repository."""
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    path = scripts / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


# -- Harness -------------------------------------------------------------------


def _write_config(
    directory: Path,
    workspace: Path,
    *,
    executable: str | None,
    args: list[str],
    verify_enabled: bool = True,
    timeout_seconds: int = 60,
    max_output_bytes: int = 200_000,
    review_block: str = ENABLED_REVIEW_BLOCK,
    project_id: str = PROJECT_ID,
    github_repo: str = REPO,
    name: str = "project.yaml",
) -> Path:
    path = directory / name
    path.write_text(
        CONFIG_TEMPLATE.format(
            project_id=project_id,
            workspace_path=json.dumps(str(workspace)),
            github_repo=github_repo,
            verify_enabled=str(verify_enabled).lower(),
            executable=json.dumps(executable) if executable else "null",
            args=json.dumps(args),
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            review_block=review_block,
        ),
        encoding="utf-8",
    )
    return path


def _setup(
    tmp_path: Path,
    *,
    body: str = PASSING_BODY,
    apply_change: bool = True,
    artifact: dict | None = None,
    **config_kwargs,
):
    """One synthetic repo, one applied approved change, one synthetic verifier."""
    repo = _make_repo(tmp_path)
    if apply_change:
        (repo / TARGET).write_bytes(PROPOSED_TEXT.encode("utf-8"))

    inputs = tmp_path / "inputs"
    inputs.mkdir(exist_ok=True)

    script = _script(tmp_path, "verify.py", body)
    config_kwargs.setdefault("executable", sys.executable)
    config_kwargs.setdefault("args", [str(script)])

    config = _write_config(inputs, repo, **config_kwargs)
    artifact_path = inputs / "approved.json"
    artifact_path.write_text(
        json.dumps(artifact if artifact is not None else artifact_payload()),
        encoding="utf-8",
    )
    return repo, config, artifact_path


def _env(**overrides) -> dict[str, str]:
    """A literal environment mapping. Never read from the real environment."""
    values = {
        "AIDO_LITELLM_BASE_URL": FAKE_BASE_URL,
        "AIDO_LITELLM_API_KEY": FAKE_API_KEY,
        # Deliberately different from the project-configured reviewer model.
        "AIDO_LITELLM_DEFAULT_MODEL": ENV_DEFAULT_MODEL,
        "AIDO_LITELLM_TIMEOUT_SECONDS": "5",
        "AIDO_LITELLM_MAX_RETRIES": "0",
    }
    for key, value in overrides.items():
        if value is None:
            values.pop(key, None)
        else:
            values[key] = value
    return values


def _mock_client_factory(
    seen: list[dict] | None = None,
    content: str = VALID_REVIEW_JSON,
    *,
    raise_transport: bool = False,
):
    """Build a client factory returning a MockTransport-backed client."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(request.content.decode("utf-8")))
        if raise_transport:
            raise httpx.ConnectError("simulated connection failure")
        return httpx.Response(
            200,
            json={
                "model": REVIEWER_MODEL,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 321,
                    "completion_tokens": 64,
                    "total_tokens": 385,
                },
            },
        )

    def factory(config):
        return LLMClient(
            config, transport=httpx.MockTransport(handler), sleep=lambda _: None
        )

    return factory


def _forbidden_env():
    def read_env():
        raise AssertionError(
            "reviewer environment was read before verification succeeded"
        )

    return read_env


def _forbidden_client():
    def factory(config):
        raise AssertionError("a reviewer client was built when it must not be")

    return factory


def _run(
    config: Path,
    artifact: Path,
    *,
    read_env=None,
    client_factory=None,
    verify_flag: bool = True,
    real_reviewer: bool = True,
) -> int:
    """Call the extracted helper with injected env/client; return the exit code."""
    try:
        cli._run_l2_review_approved_file_edit(
            project_config=config,
            approved_diff_proposal=artifact,
            verify_approved_file_edit_flag=verify_flag,
            real_reviewer=real_reviewer,
            read_env=read_env if read_env is not None else _forbidden_env(),
            client_factory=(
                client_factory if client_factory is not None else _forbidden_client()
            ),
        )
    except typer.Exit as exc:
        return exc.exit_code
    return 0


def _stdout_json(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


# =============================================================================
# 1. CLI / authorization
# =============================================================================


@pytest.mark.parametrize(
    "flags",
    [[], ["--verify-approved-file-edit"], ["--real-reviewer"]],
)
def test_a_missing_action_flag_reads_nothing_and_contacts_nothing(
    tmp_path, monkeypatch, flags
):
    """Both flags gate every read: no file, no process, no environment, no model."""
    repo, config, artifact = _setup(tmp_path) if shutil.which("git") else (
        None,
        tmp_path / "project.yaml",
        tmp_path / "approved.json",
    )
    if repo is None:
        pytest.skip("git is not installed")

    reads: list[str] = []
    original_read_text = Path.read_text

    def tracking(self, *args, **kwargs):
        reads.append(str(self))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("a process was started without both action flags")
        ),
    )
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("a socket was opened without both action flags")
        ),
    )

    result = runner.invoke(
        app,
        [
            "l2-review-approved-file-edit",
            "--project-config",
            str(config),
            "--approved-diff-proposal",
            str(artifact),
            *flags,
        ],
    )

    assert result.exit_code == 1
    assert reads == []


@git_required
def test_missing_verify_flag_message_names_the_flag(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    assert _run(config, artifact, verify_flag=False) == 1
    assert "--verify-approved-file-edit" in capsys.readouterr().err


@git_required
def test_missing_real_reviewer_flag_message_names_the_flag(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    assert _run(config, artifact, real_reviewer=False) == 1
    assert "--real-reviewer" in capsys.readouterr().err


@git_required
def test_an_absent_controlled_review_block_is_refused_before_the_workspace(
    tmp_path, monkeypatch, capsys
):
    repo = _make_repo(tmp_path)
    (repo / TARGET).write_bytes(PROPOSED_TEXT.encode("utf-8"))
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = inputs / "project.yaml"
    config.write_text(
        "project_id: %s\n"
        "display_name: Demo\n"
        "repo:\n"
        "  workspace_path: %s\n"
        "  github_repo: %s\n"
        "  branch_prefix: ai/demo\n"
        'allowed_paths: ["src/**"]\n' % (PROJECT_ID, json.dumps(str(repo)), REPO),
        encoding="utf-8",
    )
    artifact = inputs / "approved.json"
    artifact.write_text(json.dumps(artifact_payload()), encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("a process was started while review was unauthorized")
        ),
    )

    assert _run(config, artifact) == 1
    assert "opt-in error" in capsys.readouterr().err


@git_required
@pytest.mark.parametrize(
    "block, expected",
    [
        (DISABLED_REVIEW_BLOCK, "opt-in error"),
        (NO_MODEL_REVIEW_BLOCK, "model error"),
        (BAD_PROVIDER_REVIEW_BLOCK, "provider error"),
    ],
)
def test_review_gate_failures_refuse_before_anything_runs(
    tmp_path, monkeypatch, capsys, block, expected
):
    repo, config, artifact = _setup(tmp_path, review_block=block)

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("a process was started while review was unauthorized")
        ),
    )

    assert _run(config, artifact) == 1
    assert expected in capsys.readouterr().err


@git_required
def test_a_blank_reviewer_model_is_refused(tmp_path, capsys):
    repo, config, artifact = _setup(
        tmp_path,
        review_block='controlled_review:\n  enabled: true\n  model: "   "\n',
    )

    assert _run(config, artifact) == 1
    assert "controlled_review.model" in capsys.readouterr().err


@git_required
def test_disabled_controlled_verification_is_refused_before_the_artifact(
    tmp_path, capsys
):
    repo, config, artifact = _setup(tmp_path, verify_enabled=False)

    assert _run(config, artifact) == 1
    assert "controlled_verification" in capsys.readouterr().err


@git_required
def test_an_artifact_inside_the_workspace_is_refused_before_it_is_read(
    tmp_path, monkeypatch, capsys
):
    repo, config, _ = _setup(tmp_path)
    inside = repo / "approved.json"
    inside.write_text(json.dumps(artifact_payload()), encoding="utf-8")

    original_read_text = Path.read_text

    def tracking(self, *args, **kwargs):
        assert "approved.json" not in str(self), "the in-workspace artifact was read"
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking)

    assert _run(config, inside) == 1
    assert "workspace_path" in capsys.readouterr().err


def test_the_command_exposes_no_model_prompt_fixer_or_git_options():
    result = runner.invoke(app, ["l2-review-approved-file-edit", "--help"])
    text = result.output

    for forbidden in (
        "--model",
        "--provider",
        "--prompt",
        "--message",
        "--command",
        "--shell",
        "--fix",
        "--repair",
        "--retry",
        "--commit",
        "--branch",
        "--push",
        "--pr ",
        "--github",
        "--fetch",
        "--apply",
        "--verification-result",
    ):
        assert f"\n{forbidden}" not in text.replace("|", "\n")


def test_the_command_exposes_exactly_the_five_intended_options():
    """Introspect the declared options rather than trusting the help layout."""
    import inspect

    signature = inspect.signature(cli.l2_review_approved_file_edit)
    declared: set[str] = set()
    for parameter in signature.parameters.values():
        default = parameter.default
        assert isinstance(default, typer.models.OptionInfo), parameter.name
        declared.update(
            decl for decl in (default.param_decls or ()) if decl.startswith("--")
        )

    assert declared == {
        "--project-config",
        "--approved-diff-proposal",
        "--verify-approved-file-edit",
        "--real-reviewer",
        "--format",
    }


# =============================================================================
# 2. Verify before review — ordering, proved by what did NOT happen
# =============================================================================


@windows_only
@git_required
def test_a_missing_applied_change_refuses_with_no_reviewer_env_read(tmp_path, capsys):
    """5F2D refuses; the reviewer environment is never read and no model is called."""
    repo, config, artifact = _setup(tmp_path, apply_change=False)

    assert _run(config, artifact) == 1
    assert "post_image_sha256" in capsys.readouterr().err


@windows_only
@git_required
def test_a_wrong_applied_change_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path, apply_change=False)
    (repo / TARGET).write_bytes(b"something else entirely\n")

    assert _run(config, artifact) == 1


@windows_only
@git_required
def test_a_failing_verification_exits_two_and_contacts_no_model(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path, body=FAILING_BODY)

    assert _run(config, artifact) == 2

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["outcome"] == "verification-failed"
    assert report["schema_version"] == "verification-result.v1"
    assert "no reviewer was contacted" in captured.err


@windows_only
@git_required
def test_the_exit_two_message_scopes_every_claim(tmp_path, capsys):
    """Exit 2 arrives after the unsandboxed child has already run.

    So it may say what the returned 5F2D report establishes and what AIDO did
    not do — and nothing about commits, pushes, or Git state at large.
    """
    repo, config, artifact = _setup(tmp_path, body=FAILING_BODY)

    assert _run(config, artifact) == 2

    lowered = capsys.readouterr().err.lower()

    assert "no reviewer was contacted" in lowered
    assert "no reviewer environment value was read" in lowered
    assert "the report above is what establishes the workspace state" in lowered
    assert "aido performed no retry" in lowered
    assert "not sandboxed" in lowered
    assert "detection boundary" in lowered

    for forbidden in (
        "nothing committed",
        "nothing was committed",
        "or committed",
        "no push happened",
        "no git state was changed",
        "no branch, commit, push or pr happened",
        "the workspace is still exactly the approved change",
    ):
        assert forbidden not in lowered, forbidden


@windows_only
@git_required
def test_the_exit_three_message_scopes_every_claim(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path, body=DIRTYING_BODY)

    assert _run(config, artifact) == 3

    lowered = capsys.readouterr().err.lower()

    assert "no reviewer was contacted" in lowered
    assert "aido repaired nothing" in lowered
    assert "not sandboxed" in lowered

    for forbidden in (
        "nothing committed",
        "nothing was committed",
        "no push happened",
        "no git state was changed",
    ):
        assert forbidden not in lowered, forbidden


@windows_only
@git_required
def test_a_timed_out_verification_exits_two_and_contacts_no_model(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path, body=SLOW_BODY, timeout_seconds=1)

    assert _run(config, artifact) == 2

    report = json.loads(capsys.readouterr().out)
    assert report["execution"]["timed_out"] is True
    assert report["outcome"] == "verification-failed"


@windows_only
@git_required
def test_an_output_overflow_exits_two_and_contacts_no_model(tmp_path, capsys):
    repo, config, artifact = _setup(
        tmp_path, body=NOISY_BODY, max_output_bytes=5_000, timeout_seconds=30
    )

    assert _run(config, artifact) == 2

    report = json.loads(capsys.readouterr().out)
    assert report["execution"]["output_limit_exceeded"] is True


@windows_only
@git_required
def test_a_dirtying_verification_exits_three_and_contacts_no_model(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path, body=DIRTYING_BODY)

    assert _run(config, artifact) == 3

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["outcome"] == "workspace-state-untrusted"
    assert "No reviewer was contacted" in captured.err


@windows_only
@git_required
def test_a_verification_that_moves_head_exits_three(tmp_path, capsys):
    """A committing verification leaves the bytes intact but moves the baseline."""
    repo, config, artifact = _setup(tmp_path)
    committing = _script(
        tmp_path,
        "commit.py",
        """
        import subprocess, sys
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "moved"],
                       cwd=r"{repo}", capture_output=True)
        sys.exit(0)
        """.replace("{repo}", str(repo)),
    )
    config = _write_config(
        config.parent,
        repo,
        executable=sys.executable,
        args=[str(committing)],
        name="project_commit.yaml",
    )

    assert _run(config, artifact) == 3

    report = json.loads(capsys.readouterr().out)
    assert report["workspace_postcondition"]["head_unchanged"] is False


@windows_only
@git_required
def test_a_successful_verification_lets_the_reviewer_proceed(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)
    seen: list[dict] = []

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(seen),
        )
        == 0
    )
    assert len(seen) == 1


# =============================================================================
# 3. Reviewer credential ordering
# =============================================================================


@windows_only
@git_required
@pytest.mark.parametrize(
    "body, expected", [(FAILING_BODY, 2), (DIRTYING_BODY, 3)]
)
def test_reviewer_env_is_not_read_when_verification_does_not_succeed(
    tmp_path, body, expected
):
    """``read_env`` raises if called — reaching it at all fails the test."""
    repo, config, artifact = _setup(tmp_path, body=body)

    assert _run(config, artifact, read_env=_forbidden_env()) == expected


@windows_only
@git_required
def test_reviewer_env_names_are_not_touched_before_verification_succeeds(
    tmp_path, monkeypatch
):
    """Prove ordering directly: the env read is recorded against the process run."""
    repo, config, artifact = _setup(tmp_path)

    events: list[str] = []
    real_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        events.append("process")
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", recording_popen)

    def read_env():
        events.append("env")
        return _env()

    assert (
        _run(config, artifact, read_env=read_env, client_factory=_mock_client_factory())
        == 0
    )
    assert events.index("process") < events.index("env")
    assert events.count("env") == 1


@windows_only
@git_required
def test_after_a_verified_state_the_environment_configuration_is_loaded(
    tmp_path, capsys
):
    repo, config, artifact = _setup(tmp_path)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(),
        )
        == 0
    )

    packet = _stdout_json(capsys)
    assert packet["reviewer"]["endpoint_host"] == FAKE_HOST


@windows_only
@git_required
def test_a_missing_reviewer_environment_fails_the_reviewer_stage_only(
    tmp_path, capsys
):
    repo, config, artifact = _setup(tmp_path)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(AIDO_LITELLM_API_KEY=None),
            client_factory=_forbidden_client(),
        )
        == 4
    )

    captured = capsys.readouterr()
    assert "AIDO_LITELLM_API_KEY" in captured.err
    assert "verification had already passed" in captured.err
    # The approved change is left exactly as the writer and verifier left it.
    assert (repo / TARGET).read_bytes() == PROPOSED_TEXT.encode("utf-8")


@windows_only
@git_required
def test_the_environment_default_model_cannot_override_the_configured_model(
    tmp_path, capsys
):
    repo, config, artifact = _setup(tmp_path)
    seen: list[dict] = []

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(seen),
        )
        == 0
    )

    assert seen[0]["model"] == REVIEWER_MODEL
    assert seen[0]["model"] != ENV_DEFAULT_MODEL
    assert _stdout_json(capsys)["reviewer"]["model"] == REVIEWER_MODEL


# =============================================================================
# 4. What actually goes over the wire
# =============================================================================


def _sent_text(seen: list[dict]) -> str:
    return "\n".join(message["content"] for message in seen[0]["messages"])


@windows_only
@git_required
def test_the_transmitted_prompt_carries_the_diff_plan_and_verification_output(
    tmp_path,
):
    repo, config, artifact = _setup(tmp_path)
    seen: list[dict] = []

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(seen),
        )
        == 0
    )

    text = _sent_text(seen)
    assert DIFF_MARKER in text
    assert SUMMARY_MARKER in text
    assert VERIFICATION_OUTPUT_MARKER in text
    assert TARGET in text


@windows_only
@git_required
def test_the_transmitted_prompt_carries_no_absolute_path_or_credential(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    seen: list[dict] = []

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(seen),
    )

    text = _sent_text(seen)
    for absent in (
        str(repo),
        str(repo).replace("\\", "/"),
        sys.executable,
        FAKE_API_KEY,
        FAKE_BASE_URL,
        UNCHANGED_MARKER,
        "I approve this diff proposal for workspace file editing",
    ):
        assert absent not in text


@windows_only
@git_required
def test_secret_like_verification_output_is_redacted_before_transmission(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path, body=LEAKY_OUTPUT_BODY)
    seen: list[dict] = []

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(seen),
        )
        == 0
    )

    assert "sk-abcdefgh12345678" not in _sent_text(seen)
    boundary = _stdout_json(capsys)["transmission_boundary"]
    assert boundary["review_context_redacted_before_transmission"] is True
    assert boundary["redaction_count"] >= 1


# =============================================================================
# 5. Reviewer runtime
# =============================================================================


@windows_only
@git_required
def test_exactly_one_semantic_reviewer_request_is_made(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)
    seen: list[dict] = []

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(seen),
    )

    assert len(seen) == 1
    assert _stdout_json(capsys)["reviewer"]["semantic_requests"] == 1


@windows_only
@git_required
@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        "```json\n" + VALID_REVIEW_JSON + "\n```",
        json.dumps({"verdict": "approve", "summary": "ok"}),
        json.dumps(
            {
                "verdict": "approve",
                "summary": "ok",
                "findings": [],
                "residual_risks": [],
                "human_notes": [],
                "project_id": "someone/else",
            }
        ),
    ],
)
def test_a_bad_reviewer_reply_exits_four_without_a_second_request(
    tmp_path, capsys, content
):
    repo, config, artifact = _setup(tmp_path)
    seen: list[dict] = []

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(seen, content=content),
        )
        == 4
    )

    # No re-prompt, no re-review: exactly one semantic request was ever made.
    assert len(seen) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "reviewer" in captured.err.lower()


@windows_only
@git_required
def test_a_transport_failure_exits_four(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(raise_transport=True),
        )
        == 4
    )

    assert "transport" in capsys.readouterr().err.lower()


@windows_only
@git_required
def test_a_reviewer_failure_leaks_neither_the_reply_nor_the_credentials(
    tmp_path, capsys
):
    leaky = "SENTINEL_RAW_MODEL_REPLY_TEXT that must never be echoed"
    repo, config, artifact = _setup(tmp_path)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(content=leaky),
        )
        == 4
    )

    captured = capsys.readouterr()
    assert "SENTINEL_RAW_MODEL_REPLY_TEXT" not in captured.err
    assert FAKE_API_KEY not in captured.err
    assert FAKE_BASE_URL not in captured.err
    assert DIFF_MARKER not in captured.err


@windows_only
@git_required
def test_a_reviewer_failure_leaves_the_git_visible_state_as_verification_found_it(
    tmp_path,
):
    """Scoped deliberately: this asserts the **Git-visible** state, nothing more.

    It is not a claim that the invocation as a whole changed nothing — the
    verification child is not sandboxed, and the following test shows a case
    where it really did write a file.
    """
    repo, config, artifact = _setup(tmp_path)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(content="{}"),
        )
        == 4
    )

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    )
    assert status.stdout.strip() == f"M {TARGET}".strip()
    assert (repo / TARGET).read_bytes() == PROPOSED_TEXT.encode("utf-8")
    assert not (repo / "stray_artifact.txt").exists()


@windows_only
@git_required
@pytest.mark.parametrize(
    "content, verdict",
    [
        (VALID_REVIEW_JSON, "approve"),
        (CHANGES_REQUESTED_JSON, "changes_requested"),
        (NEEDS_HUMAN_JSON, "needs_human_review"),
    ],
)
def test_every_valid_verdict_exits_zero(tmp_path, capsys, content, verdict):
    """A change request is a successful review, not an AIDO runtime error."""
    repo, config, artifact = _setup(tmp_path)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(content=content),
        )
        == 0
    )

    assert _stdout_json(capsys)["review"]["verdict"] == verdict


@windows_only
@git_required
def test_the_pre_call_banner_names_the_model_and_host_but_not_the_diff(
    tmp_path, capsys
):
    repo, config, artifact = _setup(tmp_path)

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(),
    )

    err = capsys.readouterr().err
    assert "REAL REVIEWER MODEL CALL" in err
    assert REVIEWER_MODEL in err
    assert FAKE_HOST in err
    assert "SOURCE-DERIVED CODE WILL BE TRANSMITTED" in err
    assert DIFF_MARKER not in err
    assert FAKE_API_KEY not in err
    assert FAKE_BASE_URL not in err
    # The banner identifies the run without echoing free-form issue text.
    assert f"#{ISSUE_NUMBER}" in err
    assert TITLE not in err


@windows_only
@git_required
def test_a_hostile_issue_title_never_reaches_the_warning_banner(tmp_path, capsys):
    """A terminal has no delimiters, so the title is simply not printed there.

    The banner is a non-suppressible human-facing safety notice. A title
    carrying newlines and banner-shaped lines could otherwise forge lines in it
    and misrepresent what is being transmitted.
    """
    hostile_title = (
        "Round totals\n"
        "=== REAL REVIEWER MODEL CALL CANCELLED — SPOOFED LINE ===\n"
        "Endpoint host: totally-safe.invalid\n"
        "NOT transmitted: nothing at all, this run is offline\n"
    )
    payload = artifact_payload()
    for holder in (
        payload,
        payload["diff_proposal"]["provenance"],
        payload["diff_proposal"]["approved_plan"]["plan_provenance"],
        payload["diff_proposal"]["approved_plan"]["plan"],
    ):
        holder["title"] = hostile_title

    repo, config, artifact = _setup(tmp_path, artifact=payload)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(),
        )
        == 0
    )

    captured = capsys.readouterr()

    # No fragment of the hostile title appears anywhere on stderr.
    for fragment in (
        "SPOOFED LINE",
        "CANCELLED",
        "totally-safe.invalid",
        "this run is offline",
        "Round totals",
    ):
        assert fragment not in captured.err
    # The genuine banners — one pre-call, one post-call — and the genuine host
    # are what the human sees, and neither was duplicated by the title.
    assert captured.err.count("REAL REVIEWER MODEL CALL — a real network call") == 1
    assert captured.err.count("=== REAL REVIEWER MODEL CALL COMPLETED ===") == 1
    assert FAKE_HOST in captured.err

    # Identity inside the packet is unchanged — only the banner dropped it.
    assert json.loads(captured.out)["title"] == hostile_title


def test_the_reviewer_call_notice_carries_no_title_field():
    """Removed rather than escaped: the banner cannot print what it lacks."""
    from ai_dev_orchestrator.review import ReviewerCallNotice

    assert "title" not in ReviewerCallNotice.__slots__
    assert not hasattr(
        ReviewerCallNotice(
            model="m",
            endpoint_host="h",
            project_id="p",
            repo="o/r",
            issue_number=1,
        ),
        "title",
    )


@windows_only
@git_required
def test_the_exit_four_message_scopes_every_claim_to_aidos_review_stage(
    tmp_path, capsys
):
    """By exit 4 the unsandboxed verification child has already run.

    So the failure text may not carry a bare "no file was written" / "no Git
    state was changed" / "no push happened" — those are claims about the whole
    invocation, and this command cannot make them.
    """
    repo, config, artifact = _setup(tmp_path)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(content="{}"),
        )
        == 4
    )

    err = capsys.readouterr().err
    lowered = err.lower()

    # The scoped positive claim, attributed to AIDO's review stage.
    assert "aido's review stage" in lowered
    # What the passed verification established, stated as the verification's claim.
    assert "verification that had already passed" in lowered
    # The explicit boundary, and the admission that the child was not sandboxed.
    assert "not sandboxed" in lowered
    assert "detection boundary" in lowered

    # None of the unscoped global denials.
    for forbidden in (
        "no file was written",
        "no git state was changed",
        "no branch, commit, push or pr happened",
        "nothing was written",
        "no push happened",
        "no network activity",
    ):
        assert forbidden not in lowered, forbidden


@windows_only
@git_required
def test_exit_four_wording_holds_when_the_child_really_did_write_a_file(
    tmp_path, capsys
):
    """A concrete case where an unscoped claim would have been false.

    The synthetic verification program writes a **Git-ignored** file. That is a
    real filesystem effect inside the workspace, it is invisible to the
    post-execution Git check by design, and Phase 5F2D does not observe it. The
    reviewer stage then fails — and the failure text must still not claim that
    no file was written.

    No child-effect detection, branch scanning, or Git supervision is added to
    make this point: the test simply looks at the file the child left behind.
    """
    repo = _make_repo(tmp_path)
    (repo / TARGET).write_bytes(PROPOSED_TEXT.encode("utf-8"))
    (repo / ".gitignore").write_text("child_scratch.txt\n", encoding="utf-8")
    _run_git(repo, "add", ".gitignore")
    _run_git(repo, "commit", "-q", "-m", "ignore child scratch")

    inputs = tmp_path / "inputs"
    inputs.mkdir(exist_ok=True)
    script = _script(
        tmp_path,
        "writes_ignored_file.py",
        """
        import sys
        open("child_scratch.txt", "w").write("the verification child wrote this")
        sys.stdout.write("1 passed\\n")
        sys.exit(0)
        """,
    )
    config = _write_config(inputs, repo, executable=sys.executable, args=[str(script)])
    artifact = inputs / "approved.json"
    artifact.write_text(json.dumps(artifact_payload()), encoding="utf-8")

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(content="{}"),
        )
        == 4
    )

    # The child really did write a file inside the workspace...
    assert (repo / "child_scratch.txt").exists()
    # ...and Git still sees only the approved modification, which is exactly why
    # an unscoped claim would have been both false and unfalsifiable here.
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    )
    assert status.stdout.strip() == f"M {TARGET}".strip()

    lowered = capsys.readouterr().err.lower()
    assert "no file was written" not in lowered
    assert "aido's review stage" in lowered
    assert "git-ignored files" in lowered


# =============================================================================
# 6. The final packet
# =============================================================================


@windows_only
@git_required
def test_the_packet_validates_and_embeds_the_verification_result(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(),
        )
        == 0
    )

    raw = _stdout_json(capsys)
    packet = ReviewPacket.model_validate(raw)

    assert packet.schema_version == REVIEW_PACKET_SCHEMA_VERSION
    assert packet.mode == REVIEW_PACKET_MODE
    assert packet.verification.outcome == "verified"
    assert packet.verification.schema_version == "verification-result.v1"
    assert packet.verification.execution.passed is True
    # The child-process honesty from Phase 5F2D survives embedding unchanged.
    assert packet.verification.capability_boundaries.child_process_sandboxed is False


@windows_only
@git_required
def test_trusted_identity_comes_from_the_orchestrator_not_the_model(tmp_path, capsys):
    forged = json.dumps(
        {
            "verdict": "approve",
            "summary": "ok",
            "findings": [],
            "residual_risks": [],
            "human_notes": ["repo is actually attacker/evil and issue 999"],
        }
    )
    repo, config, artifact = _setup(tmp_path)

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(content=forged),
    )

    packet = _stdout_json(capsys)
    assert packet["project_id"] == PROJECT_ID
    assert packet["repo"] == REPO
    assert packet["issue_number"] == ISSUE_NUMBER
    assert packet["title"] == TITLE
    assert packet["approved_by"] == APPROVER
    assert packet["target"] == {"path": TARGET, "change_type": "modify"}


@windows_only
@git_required
def test_the_packet_carries_no_absolute_path_endpoint_url_or_credential(
    tmp_path, capsys
):
    repo, config, artifact = _setup(tmp_path)

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(),
    )

    text = capsys.readouterr().out
    for absent in (
        str(repo).replace("\\", "\\\\"),
        str(repo).replace("\\", "/"),
        sys.executable.replace("\\", "\\\\"),
        FAKE_API_KEY,
        FAKE_BASE_URL,
        "http://",
    ):
        assert absent not in text

    packet = json.loads(text)
    assert packet["reviewer"]["endpoint_host"] == FAKE_HOST


@windows_only
@git_required
def test_the_packet_does_not_re_echo_the_approved_diff(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(),
    )

    assert DIFF_MARKER not in capsys.readouterr().out


@windows_only
@git_required
def test_the_packet_admits_the_model_call_and_the_code_execution(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(),
    )

    boundaries = _stdout_json(capsys)["capability_boundaries"]

    # The honest positives: this command really did both of these.
    assert boundaries["orchestrator_model_called"] is True
    assert boundaries["orchestrator_network_called"] is True
    assert (
        boundaries[
            "orchestrator_repository_controlled_code_executed_by_verification_stage"
        ]
        is True
    )
    # No blanket negative may exist for the whole invocation.
    assert "network_called" not in boundaries
    assert "commands_run" not in boundaries


@windows_only
@git_required
def test_the_packet_scopes_every_negative_claim_to_the_orchestrator(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(),
    )

    boundaries = _stdout_json(capsys)["capability_boundaries"]

    for field in (
        "orchestrator_fixer_invoked",
        "orchestrator_second_reviewer_invoked",
        # Phase 5F2E-RS1 replaced the hard-coded
        # `orchestrator_review_retry_or_reprompt_attempted: false` — which would
        # have been a lie whenever the bounded compact retry ran — with a real
        # boolean plus these fixed negatives. This run made one attempt, so the
        # compact-retry flag is false here too.
        "orchestrator_bounded_compact_retry_used",
        "orchestrator_third_semantic_attempt_made",
        "orchestrator_parser_repair_attempted",
        "orchestrator_partial_findings_merged_across_attempts",
        "orchestrator_fallback_reviewer_model_used",
        "orchestrator_patch_generated_from_findings",
        "orchestrator_file_edit_from_findings",
        "orchestrator_automatic_repair_attempted",
        "orchestrator_rollback_or_restore_performed",
        "orchestrator_verification_rerun_after_review",
        "orchestrator_files_written_by_review_stage",
        "orchestrator_branch_created",
        "orchestrator_committed",
        "orchestrator_pushed",
        "orchestrator_pr_created",
        "orchestrator_github_accessed",
    ):
        assert boundaries[field] is False

    for name, value in boundaries.items():
        if isinstance(value, bool) and value is False:
            assert name.startswith("orchestrator_"), name


@windows_only
@git_required
def test_the_packet_states_the_transmission_boundary(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(),
    )

    boundary = _stdout_json(capsys)["transmission_boundary"]

    assert boundary["approved_diff_sent_to_reviewer"] is True
    assert boundary["verification_output_sent_redacted"] is True
    assert boundary["full_target_file_sent_to_reviewer"] is False
    assert boundary["unrelated_source_sent_to_reviewer"] is False
    assert boundary["workspace_absolute_path_sent_to_reviewer"] is False
    assert boundary["api_key_sent_to_reviewer"] is False
    assert "best-effort" in boundary["redaction_note"]
    # Redaction is never claimed as a guarantee.
    assert "secret-free" in boundary["redaction_note"]


@windows_only
@git_required
def test_the_packet_records_safe_reviewer_provenance(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(),
    )

    reviewer = _stdout_json(capsys)["reviewer"]

    assert reviewer["provider"] == "litellm"
    assert reviewer["model"] == REVIEWER_MODEL
    assert reviewer["model_source"] == "project_config.controlled_review.model"
    assert reviewer["operation"] == "code-review"
    assert reviewer["real_call"] is True
    assert reviewer["usage"]["total_tokens"] == 385
    assert "base_url" not in reviewer
    assert "api_key" not in reviewer
    assert "headers" not in reviewer


@windows_only
@git_required
def test_the_human_decision_is_the_terminal_step(tmp_path, capsys):
    repo, config, artifact = _setup(tmp_path)

    _run(
        config,
        artifact,
        read_env=lambda: _env(),
        client_factory=_mock_client_factory(content=CHANGES_REQUESTED_JSON),
    )

    captured = capsys.readouterr()
    packet = json.loads(captured.out)

    assert packet["human_decision_required"] is True
    assert "human" in packet["next_step"].lower()
    assert "advisory" in packet["next_step"].lower()
    assert "advisory" in captured.err


@windows_only
@git_required
def test_no_git_state_changes_across_a_successful_review(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(),
        )
        == 0
    )

    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    branches = subprocess.run(
        ["git", "branch", "--list"], cwd=repo, capture_output=True, text=True
    ).stdout

    assert head_after == head_before
    assert status == f"M {TARGET}".strip()
    assert branches.count("\n") <= 1


# =============================================================================
# 7. The review module itself has no fixer/writer/git surface
# =============================================================================


def test_the_review_package_has_no_fixer_writer_or_git_surface():
    import ai_dev_orchestrator.review as review_package

    names = " ".join(dir(review_package)).lower()
    for forbidden in (
        "fixer",
        "commit",
        "push",
        "branch",
        "pull_request",
        "apply_",
        "write_file",
        "subprocess",
        "shell",
        "github",
    ):
        assert forbidden not in names


def test_the_review_package_imports_no_transport_or_subprocess():
    import ai_dev_orchestrator.review.models as models_module
    import ai_dev_orchestrator.review.packet as packet_module
    import ai_dev_orchestrator.review.request as request_module
    import ai_dev_orchestrator.review.reviewer as reviewer_module

    for module in (models_module, request_module, packet_module, reviewer_module):
        source_names = set(vars(module))
        assert "httpx" not in source_names
        assert "subprocess" not in source_names
        assert "os" not in source_names


@windows_only
@git_required
def test_the_writer_is_never_invoked_by_the_review_command(tmp_path, monkeypatch):
    """5F2E starts from an applied change; it must not apply one itself."""
    import ai_dev_orchestrator.file_editing.writer as writer_module

    monkeypatch.setattr(
        writer_module,
        "apply_approved_file_edit",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("the review command invoked the writer")
        ),
    )
    repo, config, artifact = _setup(tmp_path)

    assert (
        _run(
            config,
            artifact,
            read_env=lambda: _env(),
            client_factory=_mock_client_factory(),
        )
        == 0
    )
