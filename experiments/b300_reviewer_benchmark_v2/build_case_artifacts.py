"""Generator for B300 V2 fixed, non-sandbox artifacts.

For each case, writes:
  - <case>/scripts/verify_case_*.py     (verification program, lives outside sandbox)
  - <case>/artifacts/approved-diff-proposal.json  (approved-diff-proposal.v2)
  - configs/<case>_<model>.yaml          (4 configs per case, identical except
                                           controlled_review.model)

Experiment-only. Does not touch AIDO production code/tests/CLAUDE.md or
projects/mis_project.yaml, and never writes into the sandbox itself.
"""
from __future__ import annotations

import difflib
import json
import sys

from case_defs import (
    ALL_CASES,
    APPROVED_DIFF_PROPOSAL_MODE,
    APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
    APPROVER,
    DIFF_PROPOSAL_MODE,
    DIFF_PROPOSAL_SCHEMA_VERSION,
    EXPERIMENT_ROOT,
    MODELS,
    REPO,
    REQUIRED_APPROVAL_TEXT,
    REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    SANDBOX_ROOT,
    CaseDef,
    sha256_text,
)


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


def build_artifact(case: CaseDef, issue_number: int) -> dict:
    diff = _unified_diff(case.target_rel_path, case.original_text, case.proposed_text)
    change = {
        "path": case.target_rel_path,
        "change_type": "modify",
        "unified_diff": diff,
        "pre_image_sha256": sha256_text(case.original_text),
        "post_image_sha256": sha256_text(case.proposed_text),
        "rationale": case.diff_rationale,
        "risks": case.diff_risks,
        "requires_human_review": True,
    }
    plan = {
        "issue_number": issue_number,
        "repo": REPO,
        "title": case.title,
        "summary": case.plan_summary,
        "scope_summary": case.scope_summary,
        "non_goals": case.non_goals,
        "proposed_steps": case.proposed_steps,
        "files_likely_to_change": [case.target_rel_path],
        "files_forbidden_or_out_of_scope": [],
        "required_verification": case.required_verification,
        "risks": case.plan_risks,
        "open_questions": [],
        "automation_level": "L1",
        "requires_human_approval": True,
    }
    approved_plan = {
        "approval": {
            "approved_by": APPROVER,
            "approved_at": "2026-08-19T17:30:00+00:00",
            "approval_text": REQUIRED_APPROVAL_TEXT,
            "source": "manual",
        },
        "plan_provenance": {
            "engine": "deterministic",
            "operation": "l1-plan",
            "real_call": False,
            "model": None,
            "endpoint_host": None,
            "generated_at": "2026-08-19T17:00:00+00:00",
            "project_id": case.project_id,
            "repo": REPO,
            "issue_number": issue_number,
            "title": case.title,
        },
        "plan": plan,
        "project_id": case.project_id,
        "repo": REPO,
        "issue_number": issue_number,
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
            "project_id": case.project_id,
            "repo": REPO,
            "issue_number": issue_number,
            "title": case.title,
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
            "approved_at": "2026-08-19T17:35:00+00:00",
            "approval_text": REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
            "source": "manual",
        },
        "diff_proposal": proposal,
        "project_id": case.project_id,
        "repo": REPO,
        "issue_number": issue_number,
        "title": case.title,
        "next_authorization_required": "Reviewer integration remains unauthorized.",
    }
    return payload


CONFIG_TEMPLATE = """\
# EXPERIMENT-ONLY project config for the B300 reviewer benchmark V2.
# NOT production config. Do not commit. Targets the synthetic sandbox at
# C:/dev/aido_rs1_rt1_sandbox, never a real project workspace.
project_id: {project_id}
display_name: B300 V2 {case_label} ({model})

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
  compact_retry_on_unusable_output: false
  vllm_allow_insecure_http: false
  vllm_structured_output: false

run_limits:
  max_model_calls_per_issue: 20
  max_review_loops: 3
  max_ci_fix_loops: 2
  max_total_runtime_minutes: 60
"""


def build_config(case: CaseDef, model: str, python_exe: str) -> str:
    verify_script = str(
        EXPERIMENT_ROOT / case.key / "scripts" / case.verify_script_name
    ).replace("\\", "/")
    python_exe_fwd = python_exe.replace("\\", "/")
    return CONFIG_TEMPLATE.format(
        project_id=case.project_id,
        case_label=case.key,
        model=model,
        python_exe=python_exe_fwd,
        verify_script=verify_script,
    )


def main() -> None:
    python_exe = sys.argv[1] if len(sys.argv) > 1 else sys.executable

    configs_dir = EXPERIMENT_ROOT / "configs"
    configs_dir.mkdir(exist_ok=True)

    for issue_number, case in enumerate(ALL_CASES, start=1):
        case_dir = EXPERIMENT_ROOT / case.key
        scripts_dir = case_dir / "scripts"
        artifacts_dir = case_dir / "artifacts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        verify_path = scripts_dir / case.verify_script_name
        verify_path.write_text(case.verify_script_text, encoding="utf-8", newline="")
        print(f"wrote {verify_path}")

        artifact = build_artifact(case, issue_number)
        artifact_path = artifacts_dir / "approved-diff-proposal.json"
        artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        print(f"wrote {artifact_path}")

        for model in MODELS:
            cfg = build_config(case, model, python_exe)
            safe_model = model.replace(".", "_")
            cfg_path = configs_dir / f"{case.key}_{safe_model}.yaml"
            cfg_path.write_text(cfg, encoding="utf-8")
            print(f"wrote {cfg_path}")


if __name__ == "__main__":
    main()
