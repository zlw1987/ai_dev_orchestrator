"""Reset the authorized synthetic sandbox to one case's approved dirty state.

Usage: python -B reset_sandbox.py <case_key>

Rebuilds C:\\dev\\aido_rs1_rt1_sandbox as a clean Git repo containing only
that case's package files at HEAD (the ORIGINAL/correct text), then edits the
target file in the working tree to the seeded (approved-diff) text, leaving
exactly one path as an unstaged modification. Never touches any path outside
the sandbox other than reading case_defs.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from case_defs import CASES_BY_KEY, SANDBOX_ROOT


def run(cmd, cwd):
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, shell=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed: {cmd}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result.stdout


def main() -> None:
    case_key = sys.argv[1]
    case = CASES_BY_KEY[case_key]

    src_dir = SANDBOX_ROOT / "src"
    if src_dir.exists():
        shutil.rmtree(src_dir)
    src_dir.mkdir(parents=True)

    for rel_path, content in case.package_files.items():
        full = SANDBOX_ROOT / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8", newline="")

    target_full = SANDBOX_ROOT / case.target_rel_path
    target_full.write_text(case.original_text, encoding="utf-8", newline="")

    if not (SANDBOX_ROOT / ".git").exists():
        run(["git", "init"], cwd=str(SANDBOX_ROOT))
        run(["git", "config", "user.name", "RT1 Operator"], cwd=str(SANDBOX_ROOT))
        run(
            ["git", "config", "user.email", "rt1-operator@example.invalid"],
            cwd=str(SANDBOX_ROOT),
        )

    run(["git", "add", "-A"], cwd=str(SANDBOX_ROOT))
    run(
        ["git", "commit", "-m", f"RT1 synthetic baseline: {case.key}", "--allow-empty"],
        cwd=str(SANDBOX_ROOT),
    )

    target_full.write_text(case.proposed_text, encoding="utf-8", newline="")

    status = run(["git", "status", "--short"], cwd=str(SANDBOX_ROOT))
    print(f"reset sandbox for {case_key}; git status --short:\n{status}")


if __name__ == "__main__":
    main()
