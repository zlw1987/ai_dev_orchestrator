"""Generate 4 experiment-only project configs for the Qwen3.6-27B-131K direct
vLLM reviewer extension (one per V2 case: A, B, C, D).

Reuses the EXACT SAME V2 case fixtures: same approved-diff-proposal.json,
same verify script, same controlled_verification executable/args as the
original V2 benchmark for that case. The ONLY difference from a V2 config is
the controlled_review block (provider/model/vLLM-specific fields).

No endpoint, base URL, or API key value is written into these configs --
AIDO_VLLM_BASE_URL / AIDO_VLLM_API_KEY are environment-only per the accepted
5F2E-V1 contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

RECOVERY_ROOT = Path(__file__).resolve().parent
V2_ROOT = RECOVERY_ROOT.parent / "b300_reviewer_benchmark_v2"
AIDO_ROOT = RECOVERY_ROOT.parent.parent

sys.path.insert(0, str(V2_ROOT))
from case_defs import ALL_CASES  # noqa: E402

QWEN36_MODEL = "Qwen3.6-27B-131K"

CONFIG_TEMPLATE = """\
# EXPERIMENT-ONLY project config for the B300 V2 recovery + Qwen3.6 extension.
# NOT production config. Do not commit. Targets the synthetic sandbox at
# C:/dev/aido_rs1_rt1_sandbox, never a real project workspace.
project_id: {project_id}
display_name: Qwen3.6 direct-vLLM reviewer extension ({case_label})

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
  provider: "vllm"
  model: "{model}"
  attempt_timeout_seconds: 90
  compact_retry_on_unusable_output: false
  vllm_allow_insecure_http: true
  vllm_structured_output: true

run_limits:
  max_model_calls_per_issue: 20
  max_review_loops: 3
  max_ci_fix_loops: 2
  max_total_runtime_minutes: 60
"""


def main() -> None:
    python_exe = (AIDO_ROOT / ".venv" / "Scripts" / "python.exe")
    python_exe_fwd = str(python_exe).replace("\\", "/")

    configs_dir = RECOVERY_ROOT / "configs"
    configs_dir.mkdir(exist_ok=True)

    for case in ALL_CASES:
        verify_script = str(
            V2_ROOT / case.key / "scripts" / case.verify_script_name
        ).replace("\\", "/")
        cfg = CONFIG_TEMPLATE.format(
            # Must match the artifact's embedded project_id exactly (identity
            # check in l2-verify/l2-review) -- reuse V2's own project_id
            # rather than minting a new one, since this reuses V2's artifact
            # unmodified.
            project_id=case.project_id,
            case_label=case.key,
            python_exe=python_exe_fwd,
            verify_script=verify_script,
            model=QWEN36_MODEL,
        )
        cfg_path = configs_dir / f"qwen36_{case.key}.yaml"
        cfg_path.write_text(cfg, encoding="utf-8", newline="")
        print(f"wrote {cfg_path}")


if __name__ == "__main__":
    main()
