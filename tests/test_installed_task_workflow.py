"""PORTABLE-T1 — the ALPHA-2A task and the ALPHA-2B correction round through the
installed console script, from the shipped project template. Offline.

What this test covers that the coordinator and correction tests do not: it
drives the environment's own ``ai-dev-orchestrator.exe`` (the console-script
entry point that an installed AIDO runs) as a separate process for every step
that is offline by design. It does that from a project config made out of the
shipped ``deploy/windows/aido-project.template.yaml``, with the per-machine
layout the installer's ``init-home`` creates. The steps are ``task-doctor``,
``task-start``, ``task-status``, plan-stage ``task-continue`` (prepare),
``--begin-correction-round``, the round-2 prepare and the post-terminal refusals.

Only the two steps that contact a model are run in-process: the implementer
request and the write/verify/review step. They go through the same extracted
runner that the exe calls, with ``httpx.MockTransport`` in the existing seams.
An installed AIDO has no way to inject a fake model, and this test adds none.
No socket, no real model, no real target and no real key is involved.

The test runs against whatever AIDO the interpreter imports. Under
``deploy/windows/run_installed_acceptance.py`` that is the installed wheel, and
the runner proves it. Under the development ``.venv`` it is the editable source.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from test_task_coordinator import (
    APPLY,
    APPROVER,
    IMPLEMENT,
    ORIGINAL,
    PASSING_SCRIPT,
    PREPARE,
    PROPOSED,
    REVIEW,
    REVIEWER_MODEL,
    TARGET,
    VALID_REVIEW,
    Server,
    _fill_approval,
    _git,
    _implementer_reply,
    _make_repo,
    _reviewer_reply,
)
from test_task_correction_round import BEGIN, CHANGES_REQUESTED, CORRECTED, DECLINE, _sequence

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.file_editing.models import REQUIRED_DIFF_EDIT_APPROVAL_TEXT
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.review import ReviewPacket
from ai_dev_orchestrator.supervised_implementer import live_authorization as la
from ai_dev_orchestrator.task import run as task_run

CHECKOUT = Path(__file__).resolve().parents[1]
TEMPLATE = CHECKOUT / "deploy" / "windows" / "aido-project.template.yaml"
CLI_EXE = Path(sys.executable).with_name("ai-dev-orchestrator.exe")

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="the 5F2C writer is Windows-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
    pytest.mark.skipif(not CLI_EXE.is_file(), reason="this environment has no ai-dev-orchestrator.exe"),
    pytest.mark.skipif(not TEMPLATE.is_file(), reason="the checkout has no deploy/windows template"),
]

# TLS scheme, so the template's two insecure-http acknowledgements stay false.
BASE_URL = "https://fake-gateway.invalid:8443/v1"
KEY_SENTINEL = "sk-installed-workflow-SENTINEL-7f3e9a"
OFFLINE_ENV_SENTINEL = "offline-step-env-SENTINEL-c41d"


def _load_installer():
    path = CHECKOUT / "deploy" / "windows" / "install_aido.py"
    spec = importlib.util.spec_from_file_location("aido_install_for_workflow", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _exe_env() -> dict[str, str]:
    """The operator's window: no inherited AIDO_*/import-hazard name, plus sentinels.

    The key sentinel is present for EVERY exe step. Offline steps must never
    record it; the doctor reports only that the name is set.
    """
    drop = ("PYTHONPATH", "PYTHONHOME", "GITHUB_TOKEN")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("AIDO_") and k.upper() not in drop}
    env.update(
        PYTHONIOENCODING="utf-8",
        COLUMNS="200",
        AIDO_LITELLM_BASE_URL=BASE_URL,
        AIDO_LITELLM_API_KEY=KEY_SENTINEL,
        AIDO_LITELLM_DEFAULT_MODEL=OFFLINE_ENV_SENTINEL,
    )
    return env


def _exe(*args: str, cwd: Path, localappdata: Path) -> tuple[int, str, str]:
    result = subprocess.run(
        [str(CLI_EXE), *args], cwd=cwd, env=dict(_exe_env(), LOCALAPPDATA=str(localappdata)),
        stdin=subprocess.DEVNULL,
        capture_output=True, timeout=180, check=False,
    )
    # A Windows console script writes CRLF; the operator reads lines.
    return tuple([result.returncode] + [stream.decode("utf-8").replace("\r\n", "\n")
                                        for stream in (result.stdout, result.stderr)])


def _flags_argv(flags: dict) -> list[str]:
    return [name for name, value in flags.items() if value]


def _env_values(provider: str) -> dict[str, str]:
    assert provider == "litellm"
    return {
        "AIDO_LITELLM_BASE_URL": BASE_URL,
        "AIDO_LITELLM_API_KEY": KEY_SENTINEL,
        "AIDO_LITELLM_DEFAULT_MODEL": "env-default-model-must-not-be-used",
        "AIDO_LITELLM_MAX_RETRIES": "7",
        "AIDO_LITELLM_TIMEOUT_SECONDS": "999",
    }


def _never(provider: str):
    raise AssertionError("an in-process step read a provider environment it must not read")


def _filled_template(*, workspace: Path, verifier: Path, script: Path, ledger: Path) -> str:
    """The operator's §8 edits: every placeholder, then the six SWITCH lines."""
    values = {
        "<PROJECT_ID>": "demo_project", "<DISPLAY_NAME>": "Installed workflow demo",
        "<TARGET_CLONE_FWD>": workspace.as_posix(), "<OWNER>": "demo", "<REPO>": "widgets",
        "<ALLOWED_GLOB>": "src/**", "<VERIFY_EXECUTABLE_FWD>": verifier.as_posix(),
        "<VERIFY_ARG_1>": script.as_posix(), "<REVIEW_MODEL>": REVIEWER_MODEL,
        "<LEDGER_DIR_FWD>": ledger.as_posix(),
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    assert set(re.findall(r"<[A-Z][A-Z0-9_]*>", text)) == set(values)
    for key, value in values.items():
        text = text.replace(key, value)
    text, flipped = re.subn(
        r"(?m)^(\s*(?:enabled|live_transmission_enabled): )false(\s+# SWITCH)", r"\1true\2", text
    )
    assert flipped == 6
    return text


def _paste_endpoint_block(config_text: str, doctor_stdout: str) -> str:
    """Paste the block task-doctor printed, where the template says to."""
    match = re.search(r"(?m)^controlled_review:\n((?: {2,4}\S.*\n){5})", doctor_stdout)
    assert match, doctor_stdout
    block = match.group(1)
    assert block.startswith("  endpoint:\n")
    marker = "  # endpoint:  -> do NOT"
    assert config_text.count(marker) == 1
    return config_text.replace(marker, block + marker, 1)


def _consent(path: Path, doctor_stdout: str) -> None:
    """The human's consent, typed from the endpoint values task-doctor printed."""
    match = re.search(
        r"endpoint_scheme '(\w+)', endpoint_host '([^']+)', endpoint_port (\d+)\.", doctor_stdout
    )
    assert match, doctor_stdout
    document = json.loads(path.read_text(encoding="utf-8"))
    prepared = la.parse_timestamp(document["bound"]["prepared_at"])
    document["consent"] = {
        "consented_by": APPROVER,
        "consented_at": la.utc_timestamp(max(prepared, datetime.now(timezone.utc).replace(microsecond=0))),
        "source": "manual",
        "binding_sha256": document["bound"]["binding_sha256"],
        "endpoint_scheme": match.group(1),
        "endpoint_host": match.group(2),
        "endpoint_port": int(match.group(3)),
        "consent_text": la.CONSENT_TEXT,
        "plaintext_acknowledgement": None,
    }
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def _tree_text(directory: Path) -> str:
    return "\n".join(
        path.read_bytes().decode("utf-8", "replace") for path in sorted(directory.rglob("*")) if path.is_file()
    )


def test_the_installed_console_script_runs_the_2a_task_and_the_2b_round_from_the_template(tmp_path):
    installer = _load_installer()
    ops = tmp_path / "operator"
    ops.mkdir()

    # Per-machine layout exactly as 'install_aido.py init-home' creates it.
    home_lines = installer.init_home({"LOCALAPPDATA": str(tmp_path)}, out=lambda _text: None)
    assert not [line for line in home_lines if line.status == "FIX"]
    home = tmp_path / "AIDO"
    runs_root, ledger = home / "runs", home / "ledger"
    assert runs_root.is_dir() and ledger.is_dir() and not os.listdir(ledger)

    # A dedicated LF clone, and a verification program run by the BASE
    # interpreter (absolute, outside the workspace, not AIDO's own venv python).
    repo = _make_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD").strip()
    script = ops / "verify.py"
    script.write_text(textwrap.dedent(PASSING_SCRIPT), encoding="utf-8")
    verifier = Path(sys.base_prefix) / "python.exe"
    assert verifier.is_file() and verifier.is_absolute()
    assert os.path.normcase(str(verifier.parent)) != os.path.normcase(str(Path(sys.executable).parent))

    # §8: fill the template, flip the switches; §9: the doctor derives the endpoint block.
    config = home / "config" / "demo.yaml"
    text = _filled_template(workspace=repo, verifier=verifier, script=script, ledger=ledger)
    config.write_text(text, encoding="utf-8")
    doctor = ("task-doctor", "--project-config", str(config), "--target-path", TARGET)
    code, doctor_out, err = _exe(*doctor, cwd=ops, localappdata=tmp_path)
    assert code == 1, err
    fixes = [row for row in doctor_out.splitlines() if row.startswith("[FIX]")]
    assert len(fixes) == 2, doctor_out  # both say only: no endpoint authorization yet
    assert fixes[0].startswith("[FIX] controlled_review gate: endpoint authorization error")
    assert fixes[1] == "[FIX] controlled_review.endpoint is absent: paste the block below"
    config.write_text(_paste_endpoint_block(text, doctor_out), encoding="utf-8")
    code, doctor_out, err = _exe(*doctor, cwd=ops, localappdata=tmp_path)
    assert code == 0, doctor_out + err
    assert "[FIX]" not in doctor_out
    assert "[OK] workspace is wholly clean" in doctor_out
    assert KEY_SENTINEL not in doctor_out + err

    implementer = Server(_sequence(_implementer_reply(PROPOSED), _implementer_reply(CORRECTED)))
    reviewer = Server(_sequence(_reviewer_reply(CHANGES_REQUESTED), _reviewer_reply(VALID_REVIEW)))

    def in_process(run_dir: Path, flags: dict, *, implementer_env=_never, reviewer_env=_never) -> None:
        """A model-contacting step: the exe's own runner, models behind MockTransport."""
        import typer

        try:
            cli._run_task_continue(
                run_dir=run_dir, flags=dict(flags),
                read_implementer_env=implementer_env, read_reviewer_env=reviewer_env,
                reviewer_transport_factory=lambda: __import__("httpx").MockTransport(reviewer.handler),
                _implementer_transport_factory=lambda: __import__("httpx").MockTransport(implementer.handler),
            )
        except typer.Exit as exc:
            assert exc.code == 0, exc

    def status(run_dir: Path) -> str:
        code, out, err = _exe("task-status", "--run-dir", str(run_dir), cwd=ops, localappdata=tmp_path)
        assert code == 0, err
        stage = task_run.derive_stage(task_run.load_task(str(run_dir))).name
        assert stage in out + err
        return stage

    def offline(run_dir: Path, flags: dict) -> tuple[int, str, str]:
        return _exe("task-continue", "--run-dir", str(run_dir), *_flags_argv(flags), cwd=ops, localappdata=tmp_path)

    # -- ALPHA-2A: task creation and plan approval, through the exe ---------------------------
    # No --runs-root: the default is %LOCALAPPDATA%\AIDO\runs, the directory init-home made.
    code, _, err = _exe(
        "task-start", "--project-config", str(config), "--title", "Round totals", "--issue", "7",
        "--target-path", TARGET, "--description", "Round the total to two decimal places.",
        cwd=ops, localappdata=tmp_path,
    )
    assert code == 0, err
    (run_dir,) = sorted(runs_root.iterdir())
    assert status(run_dir) == "plan_approval"
    _fill_approval(run_dir / task_run.PLAN_DRAFT_FILE, REQUIRED_APPROVAL_TEXT)
    code, _, err = offline(run_dir, PREPARE)
    assert code == 0, err
    assert status(run_dir) == "implementer_consent"
    assert implementer.requests == [] and reviewer.requests == []

    # -- implementer proposal (fake model), human consent from the doctor's values -------------
    _consent(sorted(run_dir.glob("20-authorization-*.json"))[-1], doctor_out)
    in_process(run_dir, IMPLEMENT, implementer_env=_env_values)
    assert len(implementer.requests) == 1
    assert status(run_dir) == "diff_approval"
    assert (repo / TARGET).read_bytes() == ORIGINAL.encode("utf-8")

    # -- human diff approval, bounded single-file write, verification, review ------------------
    _fill_approval(run_dir / task_run.DIFF_DRAFT_FILE, REQUIRED_DIFF_EDIT_APPROVAL_TEXT)
    in_process(run_dir, APPLY, reviewer_env=_env_values)
    assert len(reviewer.requests) == 1
    assert (repo / TARGET).read_bytes() == PROPOSED.encode("utf-8")
    assert _git(repo, "status", "--porcelain") == f" M {TARGET}\n"
    packet = ReviewPacket.model_validate_json(
        (run_dir / task_run.STEPS_DIR / "04-review.exit-0.stdout").read_text(encoding="utf-8")
    )
    assert packet.verification.outcome == "verified"
    assert packet.review.verdict == "changes_requested"
    assert status(run_dir) == "correction_offered"

    # -- ALPHA-2B: human begins, human restores, fresh consent, one more write/review ----------
    code, _, err = offline(run_dir, BEGIN)
    assert code == 0, err
    assert "git restore" in err and "AIDO never restores" in err
    assert (repo / TARGET).read_bytes() == PROPOSED.encode("utf-8")  # AIDO restored nothing
    code, _, err = offline(run_dir, PREPARE)
    assert code == 1  # refused: the round-1 candidate is still in the workspace
    assert sorted(run_dir.glob("50-authorization-*.json")) == []
    _git(repo, "restore", "--", TARGET)  # the HUMAN's restore
    code, _, err = offline(run_dir, PREPARE)
    assert code == 0, err
    assert status(run_dir) == "round2_implementer_consent"
    (draft2,) = sorted(run_dir.glob("50-authorization-*.json"))
    first = json.loads((run_dir / "20-authorization-1.json").read_text(encoding="utf-8"))["bound"]
    second = json.loads(draft2.read_text(encoding="utf-8"))["bound"]
    assert second["workspace_head_object_id"] == first["workspace_head_object_id"] == head
    assert second["binding_sha256"] != first["binding_sha256"]

    _consent(draft2, doctor_out)
    in_process(run_dir, IMPLEMENT, implementer_env=_env_values)
    assert len(implementer.requests) == 2
    assert status(run_dir) == "round2_diff_approval"
    diff2 = (run_dir / task_run.ROUND_2.diff_text_file).read_text(encoding="utf-8")
    assert "-    return x" in diff2 and "+    return round(x, 2)  # CORRECTED" in diff2
    _fill_approval(run_dir / task_run.ROUND_2.diff_draft_file, REQUIRED_DIFF_EDIT_APPROVAL_TEXT)
    in_process(run_dir, APPLY, reviewer_env=_env_values)
    assert len(reviewer.requests) == 2
    assert status(run_dir) == "round2_awaiting_human_decision"

    # -- terminal: no third round, no further step of any kind, through the exe ----------------
    for flags in (BEGIN, DECLINE, PREPARE, IMPLEMENT, APPLY, REVIEW):
        code, _, err = offline(run_dir, flags)
        assert code == 1 and "finished" in err, (flags, err)
    assert len(implementer.requests) == 2 and len(reviewer.requests) == 2

    # The workspace: same HEAD, exactly the one file modified, nothing committed.
    assert _git(repo, "rev-parse", "HEAD").strip() == head
    assert _git(repo, "status", "--porcelain") == f" M {TARGET}\n"
    assert (repo / TARGET).read_bytes() == CORRECTED.encode("utf-8")

    # Ledger and evidence stay apart; two single-use authorizations were spent.
    evidence = run_dir / task_run.EVIDENCE_DIR
    assert evidence.is_dir() and ledger not in evidence.parents and evidence not in ledger.parents
    assert len(os.listdir(ledger)) >= 2
    summary2 = (run_dir / task_run.ROUND_2.summary_file).read_text(encoding="utf-8")
    assert "This was the only correction round" in summary2

    # Neither a key nor the offline-step environment reached any record.
    recorded = _tree_text(run_dir) + _tree_text(ledger)
    assert KEY_SENTINEL not in recorded
    assert OFFLINE_ENV_SENTINEL not in recorded
    assert BASE_URL not in recorded
