"""Qwen3.6-27B-131K direct-vLLM reviewer extension: one run per V2 case (A-D).

Reuses the exact same V2 case fixtures (sandbox reset, approved-diff-proposal,
verify script, plan prose, source contract, ground truth) as the original V2
benchmark and the recovery round. Only the reviewer stack differs: direct
vLLM + generated JSON-Schema response_format + the unchanged strict parser.

Requires AIDO_VLLM_BASE_URL in the environment (never printed or stored).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

RECOVERY_ROOT = Path(__file__).resolve().parent
V2_ROOT = RECOVERY_ROOT.parent / "b300_reviewer_benchmark_v2"
AIDO_ROOT = RECOVERY_ROOT.parent.parent
AIDO_PYTHON = str(AIDO_ROOT / ".venv" / "Scripts" / "python.exe")
SANDBOX_ROOT = Path(r"C:\dev\aido_rs1_rt1_sandbox")

sys.path.insert(0, str(V2_ROOT))
from case_defs import ALL_CASES  # noqa: E402

CASE_TO_EVIDENCE_DIR = {
    "case_a_boundary": "case_a",
    "case_b_fail_closed": "case_b",
    "case_c_order_preservation": "case_c",
    "case_d_clean_control": "case_d",
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
    result = subprocess.run(
        [AIDO_PYTHON, "-B", "-m", "ai_dev_orchestrator.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        shell=False,
        timeout=timeout_s,
    )
    return result.returncode, result.stdout, result.stderr, time.monotonic() - start


def main() -> None:
    if not os.environ.get("AIDO_VLLM_BASE_URL"):
        print("AIDO_VLLM_BASE_URL is not set -- aborting.", file=sys.stderr)
        sys.exit(1)

    all_records = []
    for case in ALL_CASES:
        evidence_dir = (
            RECOVERY_ROOT / "qwen36_extension" / CASE_TO_EVIDENCE_DIR[case.key]
        )
        evidence_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = V2_ROOT / case.key / "artifacts" / "approved-diff-proposal.json"
        cfg_path = RECOVERY_ROOT / "configs" / f"qwen36_{case.key}.yaml"

        print(f"=== resetting sandbox for {case.key} (qwen3.6 extension) ===")
        reset_rc = subprocess.run(
            [AIDO_PYTHON, "-B", "reset_sandbox.py", case.key],
            cwd=str(V2_ROOT),
            capture_output=True,
            text=True,
        )
        print(reset_rc.stdout)
        if reset_rc.returncode != 0:
            print(reset_rc.stderr, file=sys.stderr)
            sys.exit(1)

        pre_proof, pre_diff = prove_sandbox_state("pre-qwen36-baseline")
        (evidence_dir / "pre_state.json").write_text(
            json.dumps(pre_proof, indent=2), encoding="utf-8"
        )
        assert pre_proof["dirty_path_count"] == 1

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
            print("PREFLIGHT VERIFICATION DID NOT PASS -- aborting", file=sys.stderr)
            sys.exit(2)

        print(f"--- [QWEN3.6 {case.key}] ---")
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

        post_proof, post_diff = prove_sandbox_state(f"post-qwen36-{case.key}")
        sandbox_unchanged = (
            post_proof["head"] == pre_proof["head"]
            and post_proof["dirty_path_count"] == 1
            and post_diff == pre_diff
        )

        record = {
            "extension": "qwen36_direct_vllm",
            "case": case.key,
            "model": "Qwen3.6-27B-131K",
            "provider": "vllm",
            "exit_code": rc,
            "wall_clock_seconds": round(dur, 3),
            "sandbox_unchanged_after_run": sandbox_unchanged,
            "stdout_path": str(stdout_path.relative_to(RECOVERY_ROOT)),
            "stderr_path": str(stderr_path.relative_to(RECOVERY_ROOT)),
        }
        all_records.append(record)
        (evidence_dir / "record.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        print(json.dumps(record, indent=2))

        if not sandbox_unchanged:
            print(f"SANDBOX DRIFTED after {case.key} -- aborting remaining", file=sys.stderr)
            break

    (RECOVERY_ROOT / "summary" / "qwen36_extension_index.json").write_text(
        json.dumps(all_records, indent=2), encoding="utf-8"
    )
    print("=== Qwen3.6 extension complete ===")


if __name__ == "__main__":
    main()
