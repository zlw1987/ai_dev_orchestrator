"""FINAL round of the AIDO controlled-reviewer benchmark.

Part 0: gpt-oss-20b gated connectivity precheck (real-llm-smoke-test).
Part 1: B300 case_d_clean_control recovery replay (4 models), reusing the
        EXACT v2 configs/artifacts/scripts unchanged.
Part 2: gpt-oss-20b full reviewer qualification across case_a..case_d, using
        newly authored configs in ./configs/ that are byte-identical to the
        existing v2 per-case qwen3-coder-next templates except project_id,
        display_name, and controlled_review.model.

Does not modify any file under b300_reviewer_benchmark/, b300_reviewer_benchmark_v2/,
or b300_reviewer_benchmark_v2_recovery/ -- those are read-only historical evidence.
All new output lives under this directory.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V2_ROOT = ROOT.parent / "b300_reviewer_benchmark_v2"
AIDO_ROOT = ROOT.parent.parent
AIDO_PYTHON = str(AIDO_ROOT / ".venv" / "Scripts" / "python.exe")
SANDBOX_ROOT = Path(r"C:\dev\aido_rs1_rt1_sandbox")
CONFIGS = ROOT / "configs"
EVIDENCE = ROOT / "evidence"
SUMMARY = ROOT / "summary"

CASE_D_RECOVERY_MODELS = [
    "nemotron-3-super",
    "minimax-m2.7",
    "minimax-m2.7-thinking",
    "qwen3-coder-next",
]

GPT_OSS_CASES = [
    "case_a_boundary",
    "case_b_fail_closed",
    "case_c_order_preservation",
    "case_d_clean_control",
]

VERIFY_SCRIPT_NAME = {
    "case_a_boundary": "verify_case_a.py",
    "case_b_fail_closed": "verify_case_b.py",
    "case_c_order_preservation": "verify_case_c.py",
    "case_d_clean_control": "verify_case_d.py",
}


def git(cwd, *args):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, shell=False
    )
    return result.returncode, result.stdout, result.stderr


def prove_sandbox_state(label: str):
    _, head, _ = git(str(SANDBOX_ROOT), "rev-parse", "HEAD")
    _, status, _ = git(str(SANDBOX_ROOT), "status", "--short")
    _, diff, _ = git(str(SANDBOX_ROOT), "diff")
    dirty_lines = [ln for ln in status.strip().splitlines() if ln.strip()]
    return {
        "label": label,
        "head": head.strip(),
        "status_short": status.strip(),
        "dirty_path_count": len(dirty_lines),
    }, diff


def run_cli(args, cwd, timeout_s=200):
    start = time.monotonic()
    try:
        result = subprocess.run(
            [AIDO_PYTHON, "-B", "-m", "ai_dev_orchestrator.cli", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout_s,
        )
        return result.returncode, result.stdout, result.stderr, time.monotonic() - start
    except subprocess.TimeoutExpired as exc:
        return (
            None,
            exc.stdout or "",
            (exc.stderr or "") + "\n[harness-level subprocess timeout]",
            time.monotonic() - start,
        )


def part0_smoke_test():
    print("=== PART 0: gpt-oss-20b connectivity precheck ===")
    cfg = CONFIGS / "smoke_gpt-oss-20b.yaml"
    rc, out, err, dur = run_cli(
        [
            "real-llm-smoke-test",
            "--project-config", str(cfg),
            "--model", "gpt-oss-20b",
            "--real-model",
        ],
        cwd=str(ROOT),
        timeout_s=120,
    )
    (EVIDENCE / "part0_smoke_stdout.json").write_text(out, encoding="utf-8")
    (EVIDENCE / "part0_smoke_stderr.txt").write_text(err, encoding="utf-8")
    print(f"smoke exit={rc} duration={dur:.2f}s")

    usable = False
    parsed = None
    if rc == 0 and out.strip():
        try:
            parsed = json.loads(out)
            # usable if it looks like a real completed result, not just a
            # bare socket-open confirmation
            usable = bool(parsed) and isinstance(parsed, dict)
        except json.JSONDecodeError:
            usable = False

    record = {
        "part": 0,
        "purpose": "gpt-oss-20b connectivity precheck (not a benchmark score)",
        "exit_code": rc,
        "wall_clock_seconds": round(dur, 3),
        "usable_result": usable,
        "stdout_path": "evidence/part0_smoke_stdout.json",
        "stderr_path": "evidence/part0_smoke_stderr.txt",
    }
    (EVIDENCE / "part0_smoke_record.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    print(json.dumps(record, indent=2))
    return record


def part1_case_d_recovery():
    print("=== PART 1: B300 case_d_clean_control recovery replay ===")
    case_key = "case_d_clean_control"
    artifact_path = V2_ROOT / case_key / "artifacts" / "approved-diff-proposal.json"
    evidence_dir = EVIDENCE / "part1_case_d"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    print(f"--- resetting sandbox for {case_key} ---")
    reset_rc = subprocess.run(
        [AIDO_PYTHON, "-B", "reset_sandbox.py", case_key],
        cwd=str(V2_ROOT),
        capture_output=True,
        text=True,
    )
    print(reset_rc.stdout)
    if reset_rc.returncode != 0:
        print(reset_rc.stderr, file=sys.stderr)
        sys.exit(1)

    pre_proof, pre_diff = prove_sandbox_state("pre-part1-baseline")
    (evidence_dir / "pre_state.json").write_text(
        json.dumps(pre_proof, indent=2), encoding="utf-8"
    )
    assert pre_proof["dirty_path_count"] == 1, pre_proof

    first_model = CASE_D_RECOVERY_MODELS[0]
    first_cfg = V2_ROOT / "configs" / f"{case_key}_{first_model.replace('.', '_')}.yaml"
    vrc, vout, verr, vdur = run_cli(
        [
            "l2-verify-approved-file-edit",
            "--project-config", str(first_cfg),
            "--approved-diff-proposal", str(artifact_path),
            "--apply-approved-plan",
            "--verify-approved-file-edit",
        ],
        cwd=str(V2_ROOT),
    )
    (evidence_dir / "preflight_verify_stdout.json").write_text(vout, encoding="utf-8")
    (evidence_dir / "preflight_verify_stderr.txt").write_text(verr, encoding="utf-8")
    print(f"preflight verify exit={vrc} duration={vdur:.2f}s")
    if vrc != 0:
        print("PREFLIGHT VERIFICATION DID NOT PASS -- aborting part 1", file=sys.stderr)
        sys.exit(2)

    records = []
    for ordinal, model in enumerate(CASE_D_RECOVERY_MODELS, start=1):
        safe_model = model.replace(".", "_")
        cfg_path = V2_ROOT / "configs" / f"{case_key}_{safe_model}.yaml"
        print(f"--- [PART1 {case_key}] {model} ({ordinal}/4) ---")

        rc, out, err, dur = run_cli(
            [
                "l2-review-approved-file-edit",
                "--project-config", str(cfg_path),
                "--approved-diff-proposal", str(artifact_path),
                "--verify-approved-file-edit",
                "--real-reviewer",
            ],
            cwd=str(V2_ROOT),
        )
        print(f"exit={rc} duration={dur:.2f}s")

        stdout_path = evidence_dir / f"{ordinal:02d}_{safe_model}_stdout.json"
        stderr_path = evidence_dir / f"{ordinal:02d}_{safe_model}_stderr.txt"
        stdout_path.write_text(out, encoding="utf-8")
        stderr_path.write_text(err, encoding="utf-8")

        post_proof, post_diff = prove_sandbox_state(f"post-part1-{safe_model}")
        sandbox_unchanged = (
            post_proof["head"] == pre_proof["head"]
            and post_proof["dirty_path_count"] == 1
            and post_diff == pre_diff
        )

        guardrail_signature_reappeared = "reviewer_response_error" in (out + err)

        parsed = None
        verdict = None
        attempts_line = None
        if out.strip():
            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                parsed = None
        if isinstance(parsed, dict):
            verdict = (
                parsed.get("review", {}).get("verdict")
                if isinstance(parsed.get("review"), dict)
                else parsed.get("verdict")
            )
        for line in (err or "").splitlines():
            if "Attempts used" in line:
                attempts_line = line.strip()

        record = {
            "part": 1,
            "case": case_key,
            "model": model,
            "provider": "litellm",
            "prior_recovery_observation": "reviewer_response_error; exit_code=4 (guardrail false-positive on benign strip() diff)",
            "exit_code": rc,
            "wall_clock_seconds": round(dur, 3),
            "reviewer_response_error_reappeared": guardrail_signature_reappeared,
            "strict_parser_accepted_reply": parsed is not None and rc == 0,
            "verdict": verdict,
            "attempts_line": attempts_line,
            "expected_verdict": "approve",
            "semantic_false_positive": bool(
                verdict and verdict != "approve"
            ),
            "sandbox_unchanged_after_run": sandbox_unchanged,
            "stdout_path": str(stdout_path.relative_to(ROOT)),
            "stderr_path": str(stderr_path.relative_to(ROOT)),
        }
        records.append(record)
        (evidence_dir / f"{ordinal:02d}_{safe_model}_record.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        print(json.dumps(record, indent=2))

        if not sandbox_unchanged:
            print(
                f"SANDBOX DRIFTED after {model} in {case_key} -- aborting remaining part 1 runs",
                file=sys.stderr,
            )
            break

    return records


def part2_gpt_oss(part0_record):
    print("=== PART 2: gpt-oss-20b full reviewer qualification (A-D) ===")
    if not part0_record.get("usable_result"):
        print("Part 0 did not produce a usable result -- skipping Part 2 entirely.")
        return []

    records = []
    for case_key in GPT_OSS_CASES:
        evidence_dir = EVIDENCE / "part2_gpt_oss" / case_key
        evidence_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = V2_ROOT / case_key / "artifacts" / "approved-diff-proposal.json"
        cfg_path = CONFIGS / f"{case_key}_gpt-oss-20b.yaml"

        print(f"--- resetting sandbox for {case_key} ---")
        reset_rc = subprocess.run(
            [AIDO_PYTHON, "-B", "reset_sandbox.py", case_key],
            cwd=str(V2_ROOT),
            capture_output=True,
            text=True,
        )
        print(reset_rc.stdout)
        if reset_rc.returncode != 0:
            print(reset_rc.stderr, file=sys.stderr)
            sys.exit(1)

        pre_proof, pre_diff = prove_sandbox_state(f"pre-part2-{case_key}")
        (evidence_dir / "pre_state.json").write_text(
            json.dumps(pre_proof, indent=2), encoding="utf-8"
        )
        assert pre_proof["dirty_path_count"] == 1, pre_proof

        vrc, vout, verr, vdur = run_cli(
            [
                "l2-verify-approved-file-edit",
                "--project-config", str(cfg_path),
                "--approved-diff-proposal", str(artifact_path),
                "--apply-approved-plan",
                "--verify-approved-file-edit",
            ],
            cwd=str(V2_ROOT),
        )
        (evidence_dir / "preflight_verify_stdout.json").write_text(vout, encoding="utf-8")
        (evidence_dir / "preflight_verify_stderr.txt").write_text(verr, encoding="utf-8")
        print(f"preflight verify exit={vrc} duration={vdur:.2f}s")
        if vrc != 0:
            print(f"PREFLIGHT VERIFICATION DID NOT PASS for {case_key} -- skipping this case", file=sys.stderr)
            continue

        print(f"--- [PART2 {case_key}] gpt-oss-20b ---")
        rc, out, err, dur = run_cli(
            [
                "l2-review-approved-file-edit",
                "--project-config", str(cfg_path),
                "--approved-diff-proposal", str(artifact_path),
                "--verify-approved-file-edit",
                "--real-reviewer",
            ],
            cwd=str(V2_ROOT),
        )
        print(f"exit={rc} duration={dur:.2f}s")

        stdout_path = evidence_dir / "stdout.json"
        stderr_path = evidence_dir / "stderr.txt"
        stdout_path.write_text(out, encoding="utf-8")
        stderr_path.write_text(err, encoding="utf-8")

        post_proof, post_diff = prove_sandbox_state(f"post-part2-{case_key}")
        sandbox_unchanged = (
            post_proof["head"] == pre_proof["head"]
            and post_proof["dirty_path_count"] == 1
            and post_diff == pre_diff
        )

        parsed = None
        verdict = None
        findings = None
        attempts_line = None
        stall_terminal = "REVIEW STALLED" in (err or "")
        compact_retry_authorized = "compact retry authorized" in (err or "")
        if out.strip():
            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                parsed = None
        if isinstance(parsed, dict):
            review = parsed.get("review") if isinstance(parsed.get("review"), dict) else parsed
            if isinstance(review, dict):
                verdict = review.get("verdict")
                f = review.get("findings")
                findings = len(f) if isinstance(f, list) else None
        for line in (err or "").splitlines():
            if "Attempts used" in line:
                attempts_line = line.strip()

        expected = {
            "case_a_boundary": "changes_requested",
            "case_b_fail_closed": "changes_requested",
            "case_c_order_preservation": "changes_requested",
            "case_d_clean_control": "approve",
        }[case_key]

        record = {
            "part": 2,
            "case": case_key,
            "model": "gpt-oss-20b",
            "provider": "litellm",
            "exit_code": rc,
            "wall_clock_seconds": round(dur, 3),
            "strict_parser_accepted_reply": parsed is not None and rc == 0,
            "verdict": verdict,
            "finding_count": findings,
            "expected_verdict": expected,
            "matches_expected": verdict == expected,
            "attempts_line": attempts_line,
            "stall_terminal_reported": stall_terminal,
            "compact_retry_authorized_reported": compact_retry_authorized,
            "sandbox_unchanged_after_run": sandbox_unchanged,
            "stdout_path": str(stdout_path.relative_to(ROOT)),
            "stderr_path": str(stderr_path.relative_to(ROOT)),
        }
        records.append(record)
        (evidence_dir / "record.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        print(json.dumps(record, indent=2))

        if not sandbox_unchanged:
            print(
                f"SANDBOX DRIFTED after gpt-oss-20b in {case_key} -- aborting remaining part 2 runs",
                file=sys.stderr,
            )
            break

    return records


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    SUMMARY.mkdir(parents=True, exist_ok=True)

    part0_record = part0_smoke_test()
    part1_records = part1_case_d_recovery()
    part2_records = part2_gpt_oss(part0_record)

    index = {
        "part0_smoke": part0_record,
        "part1_case_d_recovery": part1_records,
        "part2_gpt_oss": part2_records,
    }
    (SUMMARY / "final_extension_index.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    print("=== FINAL EXTENSION RUN COMPLETE ===")


if __name__ == "__main__":
    main()
