"""B300 V2 recovery round: replay ONLY infrastructure-invalidated observations.

Authorized set (exact, do not extend):
  case_b_fail_closed: minimax-m2.7-thinking, minimax-m2.7
      (original: reviewer call completed, strict parser accepted,
       verdict=changes_requested, then the CLI crashed serializing the
       packet to a cp1252 console -- recovering the full packet + validating
       the accepted Windows Unicode-safe stdout fix)
  case_d_clean_control: minimax-m2.7, nemotron-3-super, minimax-m2.7-thinking,
                         qwen3-coder-next
      (original: all four failed uniformly at reviewer_response_error before
       any usable semantic review was captured)

Reuses the EXACT same V2 case fixtures/configs (same sandbox reset logic,
same approved-diff-proposal.json, same verify script, same project config
files) -- nothing about the case semantics is rebuilt.

Deliberately does NOT set PYTHONIOENCODING/PYTHONUTF8: this run is also the
validation that the accepted production Unicode-safe stdout fix works on its
own, without a workaround.
"""
from __future__ import annotations

import json
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
from case_defs import CASES_BY_KEY  # noqa: E402

RECOVERY_PLAN = {
    "case_b_fail_closed": ["minimax-m2.7-thinking", "minimax-m2.7"],
    "case_d_clean_control": [
        "minimax-m2.7",
        "nemotron-3-super",
        "minimax-m2.7-thinking",
        "qwen3-coder-next",
    ],
}

ORIGINAL_OBSERVATION = {
    ("case_b_fail_closed", "minimax-m2.7-thinking"): (
        "reviewer call completed; strict parser accepted; "
        "verdict=changes_requested; CLI then crashed serializing the packet "
        "to stdout under a cp1252 console (UnicodeEncodeError on U+2192); "
        "packet lost, exit_code=1"
    ),
    ("case_b_fail_closed", "minimax-m2.7"): (
        "reviewer call completed; strict parser accepted; "
        "verdict=changes_requested; CLI then crashed serializing the packet "
        "to stdout under a cp1252 console (UnicodeEncodeError on U+2192); "
        "packet lost, exit_code=1"
    ),
    ("case_d_clean_control", "minimax-m2.7"): (
        "reviewer_response_error (endpoint returned an error status or a "
        "malformed body); 0 usable semantic review captured; exit_code=4"
    ),
    ("case_d_clean_control", "nemotron-3-super"): (
        "reviewer_response_error (endpoint returned an error status or a "
        "malformed body); 0 usable semantic review captured; exit_code=4"
    ),
    ("case_d_clean_control", "minimax-m2.7-thinking"): (
        "reviewer_response_error (endpoint returned an error status or a "
        "malformed body); 0 usable semantic review captured; exit_code=4"
    ),
    ("case_d_clean_control", "qwen3-coder-next"): (
        "reviewer_response_error (endpoint returned an error status or a "
        "malformed body); 0 usable semantic review captured; exit_code=4"
    ),
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
    # Deliberately: no env override. This validates the production Unicode
    # fix under whatever console encoding this shell already has, with no
    # PYTHONIOENCODING / PYTHONUTF8 workaround applied.
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
    import os

    print(
        "Ambient PYTHONIOENCODING:",
        repr(os.environ.get("PYTHONIOENCODING")),
    )
    print("Ambient PYTHONUTF8:", repr(os.environ.get("PYTHONUTF8")))

    all_records = []
    for case_key, models in RECOVERY_PLAN.items():
        case = CASES_BY_KEY[case_key]
        evidence_dir = RECOVERY_ROOT / "b300_recovery" / (
            "case_b" if case_key == "case_b_fail_closed" else "case_d"
        )
        evidence_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = V2_ROOT / case.key / "artifacts" / "approved-diff-proposal.json"

        print(f"=== resetting sandbox for {case_key} (recovery) ===")
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

        pre_proof, pre_diff = prove_sandbox_state("pre-recovery-baseline")
        (evidence_dir / "pre_state.json").write_text(
            json.dumps(pre_proof, indent=2), encoding="utf-8"
        )
        assert pre_proof["dirty_path_count"] == 1

        first_model = models[0]
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
            print("PREFLIGHT VERIFICATION DID NOT PASS -- aborting", file=sys.stderr)
            sys.exit(2)

        for ordinal, model in enumerate(models, start=1):
            safe_model = model.replace(".", "_")
            cfg_path = V2_ROOT / "configs" / f"{case_key}_{safe_model}.yaml"
            print(f"--- [RECOVERY {case_key}] {model} ---")

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

            post_proof, post_diff = prove_sandbox_state(f"post-recovery-{safe_model}")
            sandbox_unchanged = (
                post_proof["head"] == pre_proof["head"]
                and post_proof["dirty_path_count"] == 1
                and post_diff == pre_diff
            )

            ascii_safe = None
            unicode_escape_present = None
            if rc == 0 and out.strip():
                try:
                    out.encode("ascii")
                    ascii_safe = True
                except UnicodeEncodeError:
                    ascii_safe = False
                unicode_escape_present = "\\u" in out

            record = {
                "recovery": True,
                "case": case_key,
                "model": model,
                "provider": "litellm",
                "original_v2_observation": ORIGINAL_OBSERVATION[(case_key, model)],
                "recovery_reason": "infrastructure/output-serialization failure invalidated the original observation",
                "exit_code": rc,
                "wall_clock_seconds": round(dur, 3),
                "stdout_ascii_safe": ascii_safe,
                "stdout_contains_unicode_escape": unicode_escape_present,
                "sandbox_unchanged_after_run": sandbox_unchanged,
                "stdout_path": str(stdout_path.relative_to(RECOVERY_ROOT)),
                "stderr_path": str(stderr_path.relative_to(RECOVERY_ROOT)),
            }
            all_records.append(record)
            (evidence_dir / f"{ordinal:02d}_{safe_model}_record.json").write_text(
                json.dumps(record, indent=2), encoding="utf-8"
            )
            print(json.dumps(record, indent=2))

            if not sandbox_unchanged:
                print(
                    f"SANDBOX DRIFTED after {model} in {case_key} -- aborting remaining",
                    file=sys.stderr,
                )
                break

    (RECOVERY_ROOT / "summary" / "b300_recovery_index.json").write_text(
        json.dumps(all_records, indent=2), encoding="utf-8"
    )
    print("=== B300 recovery complete ===")


if __name__ == "__main__":
    main()
