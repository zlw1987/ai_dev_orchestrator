"""One-shot generator for the B300 reviewer benchmark's fixed artifacts.

Builds, into experiments/b300_reviewer_benchmark/:
  - artifacts/approved-diff-proposal.json  (the ONE approved diff, shared by all 4 runs)
  - configs/mis_b300_<model>.yaml          (4 experiment-only project configs,
                                             identical except controlled_review.model)

This script is experiment-only scaffolding. It does not touch AIDO production
code, tests, or projects/mis_project.yaml.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import sys
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parent
AIDO_ROOT = EXPERIMENT_ROOT.parent.parent
SANDBOX_ROOT = Path(r"C:\dev\aido_rs1_rt1_sandbox")
VERIFY_SCRIPT = EXPERIMENT_ROOT / "scripts" / "verify_quota.py"

PROJECT_ID = "b300_reviewer_benchmark"
REPO = "local/aido_rs1_rt1_sandbox"
ISSUE_NUMBER = 1
TITLE = "RT1 synthetic quota boundary regression (benchmark fixture)"
APPROVER = "MIS_USER1@amax.com"
TARGET = "src/quota/limits.py"

ORIGINAL_TEXT = SANDBOX_ROOT.joinpath(TARGET).read_bytes().decode("utf-8")
# Reconstruct the pre-image (the committed original with `<=`) by inverting
# the one already-applied seeded edit, so pre/post hashes are exact.
PROPOSED_TEXT = ORIGINAL_TEXT
ORIGINAL_TEXT = ORIGINAL_TEXT.replace(
    "return value < limit", "return value <= limit"
)

REQUIRED_APPROVAL_TEXT = "I approve this L1 plan for L2 implementation"
REQUIRED_DIFF_EDIT_APPROVAL_TEXT = "I approve this diff proposal for workspace file editing"
DIFF_PROPOSAL_SCHEMA_VERSION = "diff-proposal.v2"
APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION = "approved-diff-proposal.v2"
APPROVED_DIFF_PROPOSAL_MODE = "file-edit-approval-only"
DIFF_PROPOSAL_MODE = "proposal-only"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unified_diff(path: str, original: str, proposed: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            proposed.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def build_artifact() -> dict:
    diff = _unified_diff(TARGET, ORIGINAL_TEXT, PROPOSED_TEXT)
    change = {
        "path": TARGET,
        "change_type": "modify",
        "unified_diff": diff,
        "pre_image_sha256": _sha(ORIGINAL_TEXT),
        "post_image_sha256": _sha(PROPOSED_TEXT),
        "rationale": (
            "Synthetic benchmark regression: tighten the quota boundary "
            "check from inclusive (<=) to exclusive (<)."
        ),
        "risks": [
            "A caller requesting exactly the quota limit is now incorrectly "
            "rejected (off-by-one boundary regression)."
        ],
        "requires_human_review": True,
    }
    plan = {
        "issue_number": ISSUE_NUMBER,
        "repo": REPO,
        "title": TITLE,
        "summary": "Adjust the quota boundary check in within_quota().",
        "scope_summary": "Only src/quota/limits.py.",
        "non_goals": ["No changes to remaining() or any other quota helper."],
        "proposed_steps": [
            "Change the comparison operator in within_quota() from <= to <."
        ],
        "files_likely_to_change": [TARGET],
        "files_forbidden_or_out_of_scope": [],
        "required_verification": [
            "Run the quota unit tests for within_quota() and remaining()."
        ],
        "risks": [
            "Values exactly equal to the limit may now be rejected "
            "unexpectedly."
        ],
        "open_questions": [],
        "automation_level": "L1",
        "requires_human_approval": True,
    }
    approved_plan = {
        "approval": {
            "approved_by": APPROVER,
            "approved_at": "2026-08-18T17:30:00+00:00",
            "approval_text": REQUIRED_APPROVAL_TEXT,
            "source": "manual",
        },
        "plan_provenance": {
            "engine": "deterministic",
            "operation": "l1-plan",
            "real_call": False,
            "model": None,
            "endpoint_host": None,
            "generated_at": "2026-08-18T17:00:00+00:00",
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
            "title": TITLE,
        },
        "plan": plan,
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
    }
    proposal = {
        "schema_version": DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": DIFF_PROPOSAL_MODE,
        "provenance": {
            "engine": "deterministic",
            "operation": "diff-proposal",
            "real_call": False,
            "model": None,
            "generated_at": None,
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
            "title": TITLE,
        },
        "approved_plan": approved_plan,
        "patch_proposal": None,
        "changes": [change],
        "omitted_paths": [],
        "assumptions": [],
        "risks": [],
        "open_questions": [],
        "source_contents_read": True,
        "diffs_generated": True,
        "files_edited": False,
        "commands_run": False,
        "applies_cleanly_checked": False,
        "requires_human_review": True,
        "next_authorization_required": "A writer must be authorized separately.",
    }
    payload = {
        "schema_version": APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": APPROVED_DIFF_PROPOSAL_MODE,
        "approval": {
            "approved_by": APPROVER,
            "approved_at": "2026-08-18T17:35:00+00:00",
            "approval_text": REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
            "source": "manual",
        },
        "diff_proposal": proposal,
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
        "title": TITLE,
        "next_authorization_required": "Reviewer integration remains unauthorized.",
    }
    return payload


CONFIG_TEMPLATE = """\
# EXPERIMENT-ONLY project config for the B300 reviewer benchmark.
# NOT production config. Do not commit. Targets the synthetic sandbox at
# C:/dev/aido_rs1_rt1_sandbox, never a real project workspace.
project_id: {project_id}
display_name: B300 Reviewer Benchmark ({model})

repo:
  workspace_path: "C:/dev/aido_rs1_rt1_sandbox"
  github_repo: "local/aido_rs1_rt1_sandbox"
  default_base_branch: "master"
  branch_prefix: "ai/bench"

workspace_policy:
  deny_outside_workspace: true
  allow_symlinks: false
  max_changed_files: 20

allowed_paths:
  - "src/**"

protected_paths: []

forbidden_paths:
  - ".git"
  - ".git/**"

providers:
  litellm_local:
    type: openai_compatible
    base_url_env: AIDO_LITELLM_BASE_URL
    api_key_env: AIDO_LITELLM_API_KEY
    timeout_seconds: 600

external_integrations:
  openai_api:
    enabled: false
  anthropic_api:
    enabled: false
  github_copilot_review:
    enabled: false
  codex_review:
    enabled: false

real_model_planning:
  enabled: false
  allowed_models: []
  allow_prompt_audit_files: false

read_only_workspace_inspection:
  enabled: false
  max_inspected_files: 20
  allow_protected_paths: false

read_only_workspace_content:
  enabled: false
  max_files: 10
  max_file_bytes: 50000
  max_total_bytes: 200000
  allow_protected_paths: false

workspace_write:
  enabled: false
  max_file_bytes: 200000

controlled_verification:
  enabled: true
  executable: "{python_exe}"
  args:
    - "-B"
    - "{verify_script}"
    - "src"
  timeout_seconds: 120
  max_output_bytes: 200000

controlled_review:
  enabled: true
  provider: "litellm"
  model: "{model}"
  attempt_timeout_seconds: 90
  max_output_tokens: 2048
  compact_retry_on_unusable_output: false
  vllm_allow_insecure_http: false
  vllm_structured_output: false

run_limits:
  max_model_calls_per_issue: 20
  max_review_loops: 3
  max_ci_fix_loops: 2
  max_total_runtime_minutes: 60
"""


def build_config(model: str, python_exe: str) -> str:
    # YAML scalars: forward slashes avoid backslash-escaping headaches.
    verify_script = str(VERIFY_SCRIPT).replace("\\", "/")
    python_exe_fwd = python_exe.replace("\\", "/")
    return CONFIG_TEMPLATE.format(
        project_id=PROJECT_ID,
        model=model,
        python_exe=python_exe_fwd,
        verify_script=verify_script,
    )


def main() -> None:
    python_exe = sys.argv[1] if len(sys.argv) > 1 else sys.executable

    artifacts_dir = EXPERIMENT_ROOT / "artifacts"
    configs_dir = EXPERIMENT_ROOT / "configs"
    artifacts_dir.mkdir(exist_ok=True)
    configs_dir.mkdir(exist_ok=True)

    artifact = build_artifact()
    artifact_path = artifacts_dir / "approved-diff-proposal.json"
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"wrote {artifact_path}")

    models = [
        "nemotron-3-super",
        "minimax-m2.7-thinking",
        "qwen3-coder-next",
        "minimax-m2.7",
    ]
    for model in models:
        cfg = build_config(model, python_exe)
        safe_name = model.replace(".", "_")
        cfg_path = configs_dir / f"mis_b300_{safe_name}.yaml"
        cfg_path.write_text(cfg, encoding="utf-8")
        print(f"wrote {cfg_path}")


if __name__ == "__main__":
    main()
