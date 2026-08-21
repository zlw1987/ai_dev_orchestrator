"""Drive one case's Latin-square-ordered set of real reviewer invocations.

Usage: python -B run_case.py <case_key>

For the given case:
  1. resets the sandbox to that case's approved dirty state,
  2. proves pre-state (git status/diff/log) and runs the plain verifier once
     to prove verification passes before any reviewer call,
  3. for each model in that case's Latin-square execution order, runs the REAL
     `l2-review-approved-file-edit` CLI (--verify-approved-file-edit
     --real-reviewer) exactly once, captures stdout/stderr/exit code/duration,
     and re-proves the sandbox still contains exactly the one approved
     modification afterward,
  4. writes one evidence JSON + the raw stdout packet (if any) per model into
     <case>/evidence/.

No API keys, base URLs, or hostnames are printed. Nothing here mutates
projects/mis_project.yaml or CLAUDE.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from case_defs import CASES_BY_KEY, EXECUTION_ORDER, EXPERIMENT_ROOT, SANDBOX_ROOT

AIDO_PYTHON = str(EXPERIMENT_ROOT.parent.parent / ".venv" / "Scripts" / "python.exe")
CLI_MODULE = "ai_dev_orchestrator.cli"


def git(cwd, *args):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, shell=False
    )
    return result.returncode, result.stdout, result.stderr


def prove_sandbox_state(label: str) -> dict:
    rc1, head, _ = git(str(SANDBOX_ROOT), "rev-parse", "HEAD")
    rc2, status, _ = git(str(SANDBOX_ROOT), "status", "--short")
    rc3, diff, _ = git(str(SANDBOX_ROOT), "diff")
    dirty_lines = [ln for ln in status.strip().splitlines() if ln.strip()]
    proof = {
        "label": label,
        "head": head.strip(),
        "status_short": status.strip(),
        "dirty_path_count": len(dirty_lines),
        "diff_sha256_len": len(diff),
    }
    return proof, diff


def run_cli(args, cwd, timeout_s=200):
    env = dict(os.environ)
    # Force UTF-8 stdout/stderr so a reviewer reply containing non-ASCII
    # characters (arrows, smart quotes, etc.) doesn't crash typer.echo()
    # under this shell's cp1252 console codepage. This is a harness-only
    # environment fix; it changes no AIDO source.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    start = time.monotonic()
    result = subprocess.run(
        [AIDO_PYTHON, "-B", "-m", CLI_MODULE, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        shell=False,
        timeout=timeout_s,
        env=env,
    )
    duration = time.monotonic() - start
    return result.returncode, result.stdout, result.stderr, duration


def main() -> None:
    case_key = sys.argv[1]
    case = CASES_BY_KEY[case_key]
    order = EXECUTION_ORDER[case_key]

    case_dir = EXPERIMENT_ROOT / case_key
    evidence_dir = case_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = case_dir / "artifacts" / "approved-diff-proposal.json"

    print(f"=== resetting sandbox for {case_key} ===")
    rc, out, err = None, None, None
    reset_rc = subprocess.run(
        [AIDO_PYTHON, "-B", "reset_sandbox.py", case_key],
        cwd=str(EXPERIMENT_ROOT),
        capture_output=True,
        text=True,
    )
    print(reset_rc.stdout)
    if reset_rc.returncode != 0:
        print(reset_rc.stderr, file=sys.stderr)
        sys.exit(1)

    pre_proof, pre_diff = prove_sandbox_state("pre-reviewer-baseline")
    (evidence_dir / "pre_state.json").write_text(
        json.dumps(pre_proof, indent=2), encoding="utf-8"
    )
    (evidence_dir / "approved.diff").write_text(pre_diff, encoding="utf-8")
    print(f"pre-state proof: {pre_proof}")
    assert pre_proof["dirty_path_count"] == 1, "expected exactly one dirty path"

    # Prove verification passes BEFORE any reviewer call, using the first
    # model's config (controlled_verification block is identical across all
    # 4 configs in this case).
    first_model = order[0]
    first_cfg = EXPERIMENT_ROOT / "configs" / f"{case_key}_{first_model.replace('.', '_')}.yaml"
    vrc, vout, verr, vdur = run_cli(
        [
            "l2-verify-approved-file-edit",
            "--project-config", str(first_cfg),
            "--approved-diff-proposal", str(artifact_path),
            "--apply-approved-plan",
            "--verify-approved-file-edit",
        ],
        cwd=str(EXPERIMENT_ROOT),
    )
    (evidence_dir / "preflight_verify_stdout.json").write_text(vout, encoding="utf-8")
    (evidence_dir / "preflight_verify_stderr.txt").write_text(verr, encoding="utf-8")
    print(f"preflight verify exit={vrc} duration={vdur:.2f}s")
    if vrc != 0:
        print("PREFLIGHT VERIFICATION DID NOT PASS -- aborting case", file=sys.stderr)
        sys.exit(2)

    # Re-check sandbox state unaffected by verification.
    post_verify_proof, _ = prove_sandbox_state("post-preflight-verify")
    assert post_verify_proof["head"] == pre_proof["head"]
    assert post_verify_proof["dirty_path_count"] == 1

    results = []
    for ordinal, model in enumerate(order, start=1):
        safe_model = model.replace(".", "_")
        cfg_path = EXPERIMENT_ROOT / "configs" / f"{case_key}_{safe_model}.yaml"
        print(f"--- [{case_key}] ordinal {ordinal}: {model} ---")

        rc, out, err, dur = run_cli(
            [
                "l2-review-approved-file-edit",
                "--project-config", str(cfg_path),
                "--approved-diff-proposal", str(artifact_path),
                "--verify-approved-file-edit",
                "--real-reviewer",
            ],
            cwd=str(EXPERIMENT_ROOT),
        )
        print(f"exit={rc} duration={dur:.2f}s")

        stdout_path = evidence_dir / f"{ordinal:02d}_{safe_model}_stdout.json"
        stderr_path = evidence_dir / f"{ordinal:02d}_{safe_model}_stderr.txt"
        stdout_path.write_text(out, encoding="utf-8")
        stderr_path.write_text(err, encoding="utf-8")

        post_proof, post_diff = prove_sandbox_state(f"post-review-{safe_model}")
        sandbox_unchanged = (
            post_proof["head"] == pre_proof["head"]
            and post_proof["dirty_path_count"] == 1
            and post_diff == pre_diff
        )

        record = {
            "case": case_key,
            "model": model,
            "execution_ordinal": ordinal,
            "provider": "litellm",
            "exit_code": rc,
            "wall_clock_seconds": round(dur, 3),
            "stdout_path": str(stdout_path.relative_to(EXPERIMENT_ROOT)),
            "stderr_path": str(stderr_path.relative_to(EXPERIMENT_ROOT)),
            "sandbox_unchanged_after_run": sandbox_unchanged,
            "post_run_head": post_proof["head"],
            "post_run_dirty_path_count": post_proof["dirty_path_count"],
        }
        results.append(record)
        (evidence_dir / f"{ordinal:02d}_{safe_model}_record.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        print(json.dumps(record, indent=2))

        if not sandbox_unchanged:
            print(
                f"SANDBOX STATE DRIFTED after {model} run -- aborting remaining "
                f"models in {case_key}",
                file=sys.stderr,
            )
            break

    summary = {
        "case": case_key,
        "execution_order": order,
        "results": results,
    }
    (evidence_dir / "_case_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"=== {case_key} complete ===")


if __name__ == "__main__":
    main()
