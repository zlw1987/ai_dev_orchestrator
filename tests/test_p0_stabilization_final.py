"""P0-STABILIZATION-FINAL — FU-A and FU-B, tested offline.

FU-A: once verification has passed, its report survives a reviewer-stage
failure. ``l2-review-approved-file-edit`` exit 4 now prints the verifier's own
``verified`` report on stdout (exactly as exit 2 and 3 already print theirs),
and the task coordinator reports whether an exit-4 step record holds a report
attributable to that round's approved diff and write.

FU-B: the round-2 correction's transmission copy also replaces the directories
of the configured verification executable and of absolute verification
arguments (the external test script), plus the user-profile root
(``X:\\Users\\<account>``) of those paths, in the spellings observed.

Every workspace is a synthetic Git repository under pytest ``tmp_path``; every
verification program is a synthetic script under ``tmp_path``; every model is an
``httpx.MockTransport``. No socket, no real model and no real key.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

import httpx
import pytest

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.config_loader import load_project_config
from ai_dev_orchestrator.file_editing import parse_approved_diff_proposal_artifact
from ai_dev_orchestrator.review import ReviewPacket
from ai_dev_orchestrator.review import reviewer as reviewer_module
from ai_dev_orchestrator.supervised_implementer import correction as sic
from ai_dev_orchestrator.supervised_implementer import live
from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused
from ai_dev_orchestrator.task import correction as task_correction
from ai_dev_orchestrator.task import run as task_run
from ai_dev_orchestrator.verification import VerificationResultReport

import test_cli_l2_review_approved_file_edit as review_cli
from review_fixtures import assert_preserved_verification_only
from test_task_correction_round import (
    APPLY,
    BEGIN,
    CORRECTED,
    PREPARE,
    PROPOSED,
    REVIEW,
    TARGET,
    VALID_REVIEW,
    IMPLEMENT,
    _approve_diff,
    _approve_diff2,
    _consent2,
    _continue,
    _env,
    _library_inputs,
    _ok,
    _restore,
    _round1_records,
    _stage,
    _task,
    _to_diff_approval,
    _to_round2_diff_approval,
    _user_payload,
)

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="the 5F2C writer is Windows-only"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
]


def _stall(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("synthetic reviewer stall", request=request)


def _transport(handler):
    def factory():
        return httpx.MockTransport(handler)

    return factory


def _serialized(model) -> str:
    """Exactly what the CLI's ``_echo_json_model`` writes (plus typer's newline)."""
    return json.dumps(model.model_dump(mode="json"), indent=2) + "\n"


# =============================================================================
# FU-A, at the review command
# =============================================================================


def _spy_on_passed_verification(monkeypatch) -> list:
    """Record the report object the review library hands the CLI."""
    import ai_dev_orchestrator.review as review_package

    real = review_package.run_controlled_review
    handed: list = []

    def spy(**kwargs):
        callback = kwargs["on_verification_passed"]

        def record(report):
            handed.append(report)
            callback(report)

        kwargs["on_verification_passed"] = record
        return real(**kwargs)

    monkeypatch.setattr(review_package, "run_controlled_review", spy)
    return handed


def test_fu_a_a_verified_review_still_prints_only_the_packet(tmp_path, capsys, monkeypatch):
    handed = _spy_on_passed_verification(monkeypatch)
    _, config, artifact = review_cli._setup(tmp_path)
    seen: list[dict] = []
    code = review_cli._run(
        config, artifact, read_env=lambda _p: review_cli._env(),
        client_factory=review_cli._mock_client_factory(seen),
    )
    assert code == 0
    captured = capsys.readouterr()
    packet = ReviewPacket.model_validate_json(captured.out)
    assert packet.review.verdict == "approve"
    # The packet embeds the very report handed over before the reviewer ran.
    assert len(handed) == 1
    assert packet.verification == handed[0]
    assert "VERIFICATION EVIDENCE PRESERVED" not in captured.err


def test_fu_a_a_reviewer_timeout_keeps_the_original_verification_report(tmp_path, capsys, monkeypatch):
    handed = _spy_on_passed_verification(monkeypatch)
    _, config, artifact = review_cli._setup(tmp_path)
    code = review_cli._run(
        config, artifact, read_env=lambda _p: review_cli._env(), client_factory=_transport(_stall)
    )
    assert code == 4
    captured = capsys.readouterr()
    assert "REVIEW STALLED" in captured.err
    assert "VERIFICATION EVIDENCE PRESERVED" in captured.err
    assert "NOT a review packet" in captured.err
    document = assert_preserved_verification_only(captured.out)
    # Byte-for-byte the serialization of the verifier's own object: not rebuilt.
    assert len(handed) == 1
    assert captured.out == _serialized(handed[0])
    assert document["target"]["path"] == review_cli.TARGET
    assert review_cli.VERIFICATION_OUTPUT_MARKER in document["output"]["combined_text"]


@pytest.mark.parametrize("content", ["not json at all", "```json\n{}\n```"])
def test_fu_a_a_malformed_reply_keeps_the_original_verification_report(tmp_path, capsys, monkeypatch, content):
    handed = _spy_on_passed_verification(monkeypatch)
    _, config, artifact = review_cli._setup(tmp_path)
    seen: list[dict] = []
    code = review_cli._run(
        config, artifact, read_env=lambda _p: review_cli._env(),
        client_factory=review_cli._mock_client_factory(seen, content=content),
    )
    assert code == 4
    assert len(seen) == 1  # no repair, no second request (compact retry is off)
    captured = capsys.readouterr()
    assert_preserved_verification_only(captured.out)
    assert captured.out == _serialized(handed[0])


def test_fu_a_a_transport_error_keeps_the_original_verification_report(tmp_path, capsys):
    _, config, artifact = review_cli._setup(tmp_path)
    code = review_cli._run(
        config, artifact, read_env=lambda _p: review_cli._env(),
        client_factory=review_cli._mock_client_factory(raise_transport=True),
    )
    assert code == 4
    assert_preserved_verification_only(capsys.readouterr().out)


def test_fu_a_a_failed_verification_never_reaches_the_reviewer(tmp_path, capsys, monkeypatch):
    handed = _spy_on_passed_verification(monkeypatch)
    _, config, artifact = review_cli._setup(tmp_path, body=review_cli.FAILING_BODY)
    code = review_cli._run(
        config, artifact, read_env=review_cli._forbidden_env(),
        client_factory=review_cli._forbidden_client(),
    )
    assert code == 2
    report = VerificationResultReport.model_validate_json(capsys.readouterr().out)
    assert report.outcome == "verification-failed"
    assert handed == []  # the callback is for a passed verification only


def test_fu_a_an_unexpected_error_after_verification_propagates_with_the_report(
    tmp_path, capsys, monkeypatch
):
    _, config, artifact = review_cli._setup(tmp_path)

    def explode(*args, **kwargs):
        raise RuntimeError("synthetic internal failure")

    monkeypatch.setattr(reviewer_module, "run_supervised_review", explode)
    with pytest.raises(RuntimeError):
        review_cli._run(
            config, artifact, read_env=lambda _p: review_cli._env(),
            client_factory=review_cli._mock_client_factory(),
        )
    assert_preserved_verification_only(capsys.readouterr().out)


def test_fu_a_the_library_hands_over_the_report_before_any_credential_is_read(tmp_path):
    _, config, artifact_path = review_cli._setup(tmp_path)
    project = load_project_config(config)
    artifact = parse_approved_diff_proposal_artifact(artifact_path.read_text(encoding="utf-8"))
    events: list = []

    def read_env(provider):
        events.append(("read_env", provider))
        return review_cli._env()

    outcome = reviewer_module.run_controlled_review(
        approved_diff=artifact,
        project=project,
        read_env=read_env,
        network_transport_factory=review_cli._mock_client_factory(),
        on_verification_passed=lambda report: events.append(("verified", report)),
    )
    assert [kind for kind, _ in events] == ["verified", "read_env"]
    assert events[0][1] is outcome.verification
    assert outcome.packet is not None and outcome.packet.verification == outcome.verification


# =============================================================================
# FU-A, in the task coordinator: attributable to the attempt, semantics unchanged
# =============================================================================


def _exit4_records(env, step: str) -> list[Path]:
    return sorted((env.run_dir / "steps").glob(f"*-{step}.exit-4.stdout"))


def test_fu_a_a_round1_stall_preserves_attributable_evidence_and_stays_retryable(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,), reviews=(VALID_REVIEW,))
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    env.reviewer.respond = _stall
    assert _continue(capsys, env, APPLY)[0] == 4
    stage = task_run.derive_stage(_task(env))
    # Exit semantics and correction eligibility are unchanged: a retry, no correction.
    assert stage.name == "review_pending" and not stage.terminal
    assert set(stage.actions) == {task_run.REVIEW_FLAGS}
    [record] = _exit4_records(env, "review")
    assert f"preserved unchanged in {record.name}" in stage.message
    assert "It is NOT a review" in stage.message
    evidence = record.read_bytes()
    report = VerificationResultReport.model_validate_json(evidence)
    assert report.outcome == "verified"

    env.reviewer.respond = lambda request: httpx.Response(200, json=_reviewer_ok())
    _ok(_continue(capsys, env, REVIEW))
    assert _stage(env) == "awaiting_human_decision"
    assert record.read_bytes() == evidence  # the earlier attempt's record is untouched


def _reviewer_ok() -> dict:
    from test_task_coordinator import _reviewer_reply

    return _reviewer_reply(VALID_REVIEW)


def test_fu_a_a_round2_stall_is_terminal_with_attributable_evidence(tmp_path, capsys):
    env = _env(tmp_path)
    _to_round2_diff_approval(capsys, env)
    _approve_diff2(env)
    env.reviewer.respond = _stall
    assert _continue(capsys, env, APPLY)[0] == 4
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_review_failed" and stage.terminal and stage.actions == {}
    assert "NO valid round-2 review" in stage.message
    [record] = _exit4_records(env, "review-r2")
    assert f"preserved unchanged in {record.name}" in stage.message
    # Round-1 evidence is still exactly what began the correction.
    evidence, _first = task_run.round2_context(_task(env))
    assert evidence.reason == "reviewer_changes_requested"
    # Tampering is detected by the round-2 integrity record and named.
    record.write_bytes(record.read_bytes().replace(b'"verified"', b'"verifiedX"', 1))
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_review_failed"
    assert "holds no verification report attributable" in stage.message
    assert "integrity record" in stage.message


def test_fu_a_an_exit4_record_naming_another_approval_or_empty_is_not_attributed(tmp_path, capsys):
    env = _env(tmp_path, proposals=(PROPOSED,), reviews=(VALID_REVIEW,))
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    env.reviewer.respond = _stall
    assert _continue(capsys, env, APPLY)[0] == 4
    [record] = _exit4_records(env, "review")
    document = json.loads(record.read_text(encoding="utf-8"))
    document["approved_by"] = "someone-else@example.invalid"
    record.write_text(json.dumps(document, indent=2), encoding="utf-8")
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "review_pending"
    assert "does not name 31-diff.approved.json" in stage.message
    # A pre-FU-A record (empty stdout) is reported as such, never as evidence.
    record.write_bytes(b"")
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "review_pending" and set(stage.actions) == {task_run.REVIEW_FLAGS}
    assert "before FU-A" in stage.message


# =============================================================================
# FU-B, unit level: what is replaced, and what is kept
# =============================================================================

ALICE_WS = "C:\\Users\\Alice-Q\\AIDO-area\\repo"
ALICE_EXE = "C:\\Users\\Alice-Q\\AppData\\Local\\AIDO\\venv\\Scripts\\python.exe"
ALICE_SCRIPT = "C:\\Users\\Alice-Q\\AIDO-area\\suite\\test_semver.py"


def _facts(output_text: str, outcome: str = "verification-failed") -> dict:
    return {
        "outcome": outcome, "return_code": 1, "passed": False, "timed_out": False,
        "output_limit_exceeded": False, "output_complete": True, "output_text": output_text,
    }


def _build(output_text: str, *, args=(ALICE_SCRIPT,), executable=ALICE_EXE, workspace=ALICE_WS):
    return sic.build_correction_input(
        reason="verification_failed",
        baseline=sic.CorrectionBaseline(
            target_path="semver_utils.py", source_sha256="a" * 64, source_bytes=10,
            workspace_head_object_id="b" * 40,
        ),
        previous_approved_diff="--- a/semver_utils.py\n+++ b/semver_utils.py\n@@ -1 +1 @@\n-x\n+y\n",
        verification=_facts(output_text),
        review=None,
        workspace_path=workspace,
        verification_executable=executable,
        verification_args=tuple(args),
    )


def _observed_traceback(times: int = 13) -> str:
    frames = "".join(
        f'Traceback (most recent call last):\n  File "{ALICE_SCRIPT}", line {40 + n}, in '
        f"test_prerelease_accepts_dot\nValueError: invalid pre-release identifier '1.0.{n}-rc.1'\n"
        for n in range(times)
    )
    return (
        frames
        + f'  File "{ALICE_WS}\\semver_utils.py", line 7, in parse\n'
        + f"python: {ALICE_EXE}\n"
        + "site: C:/Users/Alice-Q/AppData/Local/Programs/Python/Python312/Lib/unittest/case.py\n"
        + "repr: " + repr(ALICE_SCRIPT) + "\n"
        + "upper: " + ALICE_SCRIPT.upper() + "\n"
        + "13 failed\n"
    )


def test_fu_b_the_observed_script_path_disclosure_is_removed_and_details_kept():
    text = _observed_traceback()
    assert text.count(ALICE_SCRIPT) == 13  # the 13 traceback frames observed
    correction = _build(text)
    sent = correction.transmitted()["aido_observed_verification_facts"]["output_text"]
    for gone in ("Alice-Q", "alice-q", "AIDO-area\\suite", "Scripts\\python"):
        assert gone.casefold() not in sent.casefold(), gone
    # Debugging detail survives: test name, input, exception, file name, line.
    assert sent.count('File "<verification-arg-dir>\\test_semver.py", line 4') == 10
    assert "test_prerelease_accepts_dot" in sent
    assert "ValueError: invalid pre-release identifier '1.0.12-rc.1'" in sent
    assert '<workspace>\\semver_utils.py", line 7, in parse' in sent
    assert "python: <verification-executable-dir>\\python.exe" in sent
    assert "site: <user-profile>/AppData/Local/Programs/Python/Python312/Lib/unittest/case.py" in sent
    assert "repr: '<verification-arg-dir>\\\\test_semver.py'" in sent
    assert "upper: <verification-arg-dir>\\TEST_SEMVER.PY" in sent
    assert correction.local_path_replacements >= 17
    assert correction.workspace_path_replacements == 1
    note = correction.transmitted()["redaction_note"]
    assert "other configured local path" in note and "backstop, not a guarantee" in note
    assert "secret-free" not in note


def test_fu_b_paths_the_configuration_does_not_name_pass_through_unchanged():
    text = "D:\\elsewhere\\x.py\nC:\\Program Files\\Python\\python.exe\nC:\\Users\\Bob\\y.py\n"
    sent = _build(text).verification.output_text
    # Not under a configured directory or profile root: a backstop, not DLP.
    assert sent == text


def test_fu_b_drive_roots_and_the_users_directory_are_never_replaced():
    table = dict(
        (spelling.casefold(), placeholder)
        for spelling, placeholder in sic.local_path_redaction_table(
            ALICE_WS, "C:\\python.exe", ("C:\\Users\\top.py", "D:\\t.py")
        )
    )
    assert "c:" not in table and "c:\\users" not in table and "d:" not in table
    assert "c:\\users\\top.py".casefold() not in table


def test_fu_b_an_argument_inside_the_workspace_keeps_its_relative_path():
    script = ALICE_WS + "\\tests\\test_x.py"
    sent = _build(f'File "{script}", line 3\n', args=(script,)).verification.output_text
    assert sent == 'File "<workspace>\\tests\\test_x.py", line 3\n'


def test_fu_b_an_option_value_path_is_covered():
    sent = _build(
        "rootdir=C:\\Users\\Alice-Q\\suites\\semver\nok\n",
        args=("--rootdir=C:\\Users\\Alice-Q\\suites\\semver\\conftest.py",),
    ).verification.output_text
    assert sent == "rootdir=<verification-arg-dir>\nok\n"


def test_fu_b_derivation_is_deterministic():
    text = _observed_traceback()
    assert _build(text).transmitted() == _build(text).transmitted()


def test_fu_b_original_strings_are_never_mutated():
    text = _observed_traceback()
    facts = _facts(text)
    sic.build_correction_input(
        reason="verification_failed",
        baseline=sic.CorrectionBaseline(
            target_path="semver_utils.py", source_sha256="a" * 64, source_bytes=10,
            workspace_head_object_id="b" * 40,
        ),
        previous_approved_diff="--- a/x\n+++ b/x\n@@ -1 +1 @@\n-x\n+y\n",
        verification=facts, review=None, workspace_path=ALICE_WS,
        verification_executable=ALICE_EXE, verification_args=(ALICE_SCRIPT,),
    )
    assert facts["output_text"] == text


# =============================================================================
# FU-B, end to end: the actual serialized outbound round-2 request
# =============================================================================

# Fails until the target carries the CORRECTED marker, printing a traceback of
# its own absolute path 13 times (the P0-M3-LIVE-1 round-2 shape), plus the
# executable path and other spellings of the script path.
FUB_SCRIPT = """\
import os
import sys
import traceback

text = open(os.path.join("src", "mod.py"), encoding="utf-8").read()
print("rootdir: " + os.getcwd())
print("python: " + sys.executable)
if "CORRECTED" in text:
    print("13 passed")
    sys.exit(0)
failed = 0
for n in range(13):
    case = "1.0." + str(n) + "-rc.1"
    try:
        raise ValueError("invalid pre-release identifier " + repr(case))
    except ValueError:
        failed += 1
        print("FAIL: test_prerelease_accepts_dot[" + case + "]")
        sys.stdout.write(traceback.format_exc())
print("script repr: " + repr(__file__))
print("script posix: " + __file__.replace(os.sep, "/"))
print("script upper: " + __file__.upper())
print(str(failed) + " failed")
sys.exit(1)
"""


def _spellings(path: str) -> list[str]:
    base = os.path.abspath(path).rstrip("\\/")
    return [base, base.replace("\\", "/"), base.replace("\\", "\\\\")]


def _all_strings(value) -> list[str]:
    if isinstance(value, str):
        found = [value]
        try:
            found += _all_strings(json.loads(value))
        except ValueError:
            pass
        return found
    if isinstance(value, dict):
        return [s for item in value.values() for s in _all_strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in _all_strings(item)]
    return []


def _profile_root(path: Path) -> str | None:
    parts = Path(os.path.abspath(path)).parts
    if len(parts) >= 3 and parts[1].casefold() == "users":
        return str(Path(*parts[:3]))
    return None


def _round1_failed_then_begun(capsys, env) -> dict:
    _to_diff_approval(capsys, env)
    _approve_diff(env)
    assert _continue(capsys, env, APPLY)[0] == 2
    assert _stage(env) == "correction_offered"
    _ok(_continue(capsys, env, BEGIN))
    _restore(env)
    return _round1_records(env)


def test_fu_b_the_outbound_correction_request_carries_no_configured_local_path(tmp_path, capsys):
    env = _env(tmp_path, reviews=(VALID_REVIEW,), script=FUB_SCRIPT, proposals=(PROPOSED, CORRECTED))
    round1 = _round1_failed_then_begun(capsys, env)
    [record] = sorted((env.run_dir / "steps").glob("*-review.exit-2.stdout"))
    original = record.read_text(encoding="utf-8")
    script_json = json.dumps(str(env.script))[1:-1]
    # The observed disclosure, reproduced in the ORIGINAL local evidence.
    assert original.count(script_json) >= 13

    _ok(_continue(capsys, env, PREPARE))
    _consent2(env)
    _ok(_continue(capsys, env, IMPLEMENT))  # the run re-derived the same digest
    request = env.implementer.requests[1]
    body = json.loads(request.content)
    strings = _all_strings(body)
    forbidden = _spellings(str(env.script.parent)) + _spellings(os.path.dirname(sys.executable))
    forbidden += _spellings(str(env.repo))
    profile = _profile_root(tmp_path)
    if profile is not None:
        forbidden += _spellings(profile)
    raw = request.content.decode("utf-8").casefold()
    for spelling in forbidden:
        assert spelling.casefold() not in raw, spelling
        assert not any(spelling.casefold() in s.casefold() for s in strings), spelling
    if profile is not None and len(Path(profile).name) >= 4:
        # The account-name-bearing path component is gone from every path form.
        account = Path(profile).name.casefold()
        assert not re.search(r"users[\\/]+" + re.escape(account), raw)

    correction = _user_payload(request)["correction"]
    sent = correction["aido_observed_verification_facts"]["output_text"]
    assert sent.count('File "<verification-arg-dir>\\verify.py", line ') == 13
    assert "FAIL: test_prerelease_accepts_dot[1.0.12-rc.1]" in sent
    assert "ValueError: invalid pre-release identifier '1.0.12-rc.1'" in sent
    assert "python: <verification-executable-dir>\\" in sent
    assert "rootdir: <workspace>" in sent
    assert "13 failed" in sent
    assert "other configured local path" in correction["redaction_note"]

    # What was sent is exactly the deterministic derivation from the evidence.
    evidence, _ = task_run.round2_context(_task(env))
    rebuilt = task_correction.correction_input(evidence, env.project())
    assert correction == rebuilt.transmitted()
    assert task_correction.correction_input(evidence, env.project()).transmitted() == correction
    # The local evidence is byte-unchanged.
    assert record.read_text(encoding="utf-8") == original
    after = _round1_records(env)
    assert {name: after.get(name) for name in round1} == round1

    _approve_diff2(env)
    _ok(_continue(capsys, env, APPLY))
    assert _stage(env) == "round2_awaiting_human_decision"


def _legacy_table(workspace_path, *_args, **_kwargs):
    """The pre-FU-B derivation: the workspace path only."""
    return tuple((spelling, sic.WORKSPACE_PLACEHOLDER) for spelling in sic.workspace_path_variants(workspace_path))


def test_fu_b_an_authorization_prepared_under_the_old_derivation_is_refused(tmp_path, capsys, monkeypatch):
    env = _env(tmp_path, reviews=(VALID_REVIEW,), script=FUB_SCRIPT, proposals=(PROPOSED, CORRECTED))
    _round1_failed_then_begun(capsys, env)
    with monkeypatch.context() as patch:
        patch.setattr(sic, "local_path_redaction_table", _legacy_table)
        _ok(_continue(capsys, env, PREPARE))
    _consent2(env)
    sent_before = len(env.implementer.requests)
    code, _out, err = _continue(capsys, env, IMPLEMENT)
    assert code == 1
    assert "authorization_mismatch" in err
    assert len(env.implementer.requests) == sent_before  # nothing was sent
    stage = task_run.derive_stage(_task(env))
    assert stage.name == "round2_implementer_consent"
    # Re-preparation is offered; the stale draft could only be refused again.
    assert task_run.PREPARE_FLAGS in stage.actions
    assert _continue(capsys, env, IMPLEMENT)[0] == 1
    assert len(env.implementer.requests) == sent_before
    # A fresh preparation and consent under the new derivation then succeeds.
    _ok(_continue(capsys, env, PREPARE))
    _consent2(env)
    _ok(_continue(capsys, env, IMPLEMENT))
    assert len(env.implementer.requests) == sent_before + 1


def test_fu_b_the_live_boundary_refuses_a_copy_that_still_names_a_local_path(tmp_path, capsys):
    env = _env(tmp_path, reviews=(VALID_REVIEW,), script=FUB_SCRIPT, proposals=(PROPOSED, CORRECTED))
    _round1_failed_then_begun(capsys, env)
    project, plan = _library_inputs(env)
    evidence, _ = task_run.round2_context(_task(env))
    correction = task_correction.correction_input(evidence, project)
    leaky_facts = correction.verification.model_copy(
        update={"output_text": "see " + str(env.script).replace("\\", "/").upper()}
    )
    leaky = correction.model_copy(update={"verification": leaky_facts})
    with pytest.raises(SupervisedImplementerRefused) as caught:
        live.prepare_supervised_implementation(
            project=project, approved_plan=plan, target_path=TARGET,
            evidence_dir=str(env.run_dir / task_run.EVIDENCE_DIR), correction=leaky,
        )
    assert caught.value.category == "correction_contains_local_path"


# =============================================================================
# The recommended pilot configuration is valid in this version (nothing defaulted)
# =============================================================================


def test_the_recommended_pilot_configuration_passes_both_gates(tmp_path):
    from ai_dev_orchestrator.models import ProjectConfig, SupervisedImplementerConfig
    from ai_dev_orchestrator.review import check_controlled_review_gate
    from test_task_coordinator import _config

    document = _config(tmp_path / "repo", tmp_path, tmp_path / "verify.py")
    document["controlled_review"].update(
        {"provider": "litellm", "model": "gpt-oss-20b", "attempt_timeout_seconds": 300}
    )
    document["supervised_implementer"].update(
        {
            "candidate": "SUP-M3",
            "model": "minimax-m3",
            "provider": "litellm",
            "output_envelope": "delimited_file",
            "endpoint": {"scheme": "http", "host": "litellm.example.invalid", "port": 8080, "base_path": "/v1"},
        }
    )
    project = ProjectConfig.model_validate(document)
    authority = check_controlled_review_gate(project)
    assert (authority.provider, authority.model) == ("litellm", "gpt-oss-20b")
    settings = live.check_supervised_implementer_live_gate(project.supervised_implementer)
    assert settings.base.model == "minimax-m3"
    assert settings.base.output_envelope == "delimited_file"
    # SUP-D keeps its exact identity, and no default names the pilot models.
    default = SupervisedImplementerConfig()
    assert default.candidate is None and default.model is None
    assert default.output_envelope == "json_content_text"
    sup_d = dict(document["supervised_implementer"], candidate="SUP-D", model="qwen3.8-27b",
                 output_envelope="json_content_text")
    assert live.check_supervised_implementer_live_gate(
        SupervisedImplementerConfig.model_validate(sup_d)
    ).base.model == "qwen3.8-27b"


def test_fu_a_an_egress_refusal_keeps_the_report_with_no_transport_built(tmp_path, capsys):
    """The smoke plan's zero-request FU-A check: verification runs, nothing is sent."""
    _, config, artifact = review_cli._setup(tmp_path)
    code = review_cli._run(
        config, artifact,
        read_env=lambda _p: review_cli._env(AIDO_LITELLM_BASE_URL="http://not-the-pin.invalid:9/v1"),
        client_factory=review_cli._forbidden_client(),
    )
    assert code == 4
    captured = capsys.readouterr()
    assert_preserved_verification_only(captured.out)
    assert "VERIFICATION EVIDENCE PRESERVED" in captured.err
