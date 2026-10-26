"""DL-4B S2 — versioned records of the integration store (``store.v4``).

DL-4B binds a step's one permitted workspace effect to the plan activation a
human signs, instead of reopening the frozen Step Contract (FD-10, C-5). This
module holds the pure records and digests that binding needs, and the closed
vocabularies of the store.v4 records later slices write:

```text
WriteScopeV1                     write-scope.v1: one repo-relative file, modify only,
                                 its pre-image, the detached base HEAD, the config digest
plan_activation_subject_v2_sha256  what a human signs to activate a plan in store.v4:
                                 v1's fields + write scopes + project config + identity
                                 boundary (FD-10, AMEND1)
ALPHA_EXECUTION_POLICY           the only policy store.v4 activates (FD-8a)
```

Nothing here is authority by construction. The integration store recomputes
every digest from its own rows at every proof, and refuses a scope, a policy or
a subject that does not match what was signed.

The claim and observation vocabularies below exist so the store can fix them
in its schema now. **S2 has no writer for any of those records.** Execution
claims (FD-15) are bytes received from the execution identity, never
authority; authority observations are the authority identity's own reads
(FD-18). Their recorders are minted only into the S3–S5 adapters.

This module is pure: it imports nothing outside ``control_plane`` and the DL-1
allowed set.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from ai_dev_orchestrator.control_plane.authority import ExecutionPolicy
from ai_dev_orchestrator.control_plane.models import _slug, canonical_json_bytes, model_sha256

WRITE_SCOPE_SCHEMA_VERSION = "write-scope.v1"
PLAN_ACTIVATION_SUBJECT_V2_SCHEMA_VERSION = "plan-activation-subject.v2"
EXECUTION_HANDOFF_SCHEMA_VERSION = "execution-handoff.v1"
EXECUTION_CLAIM_SCHEMA_VERSION = "execution-claim.v1"
AUTHORITY_OBSERVATION_SCHEMA_VERSION = "authority-observation.v1"
WRITE_INTENT_SCHEMA_VERSION = "write-intent.v1"

#: FD-15. The only provenance label an execution claim, or any evidence row
#: derived from one, may carry. A claim is never relabeled as authority.
EXECUTION_CLAIM_PROVENANCE = "execution_claim"
#: FD-18. The label of the authority identity's own observations.
AUTHORITY_OBSERVATION_PROVENANCE = "authority_observation"
#: §8 ``execution-claim.v1``: the shapes S3/S4 classify stdout into.
CLAIM_SHAPES = ("write-result", "review-packet", "verification-failed", "workspace-untrusted")
#: FD-18 observation kinds.
OBSERVATION_KINDS = ("m0", "m1", "m2")
#: §8 ``write-intent.v1`` states.
WRITE_INTENT_STATES = ("pending", "completed", "refused", "indeterminate")

#: FD-8a. Review and human acceptance required, one attempt. store.v4 activates
#: no other policy, so "a human accepts every Alpha step" is a store refusal.
ALPHA_EXECUTION_POLICY = ExecutionPolicy(
    schema_version="execution-policy.v1",
    review_required=True,
    human_acceptance_required=True,
    max_attempts=1,
)

MAX_SCOPE_PATH_CHARS = 1024
MAX_SCOPE_COMPONENT_CHARS = 255
_HEX64 = re.compile(r"[0-9a-f]{64}")
#: A Git object id: SHA-1 (40) or SHA-256 (64) repositories, lowercase.
_OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
#: Printable ASCII only. A non-ASCII name can have several Unicode spellings
#: for one file, and this module may not import a normalizer to compare them.
_COMPONENT_FORBIDDEN = frozenset('\\:*?"<>|')
_SHORT_NAME = re.compile(r"~[0-9]")
_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{base}{n}" for base in ("COM", "LPT") for n in "123456789"}
)


def _repo_path(value: str) -> str:
    """One repo-relative POSIX path in its only spelling, or a refusal.

    Refused: empty, absolute or drive paths, backslashes, any ``:`` (drive
    forms and alternate streams), empty, ``.`` and ``..`` components, a ``.git``
    component in any case, components ending in a dot or a space, 8.3
    short-name forms, reserved device names, and any character outside
    printable ASCII. A path either names exactly one file unambiguously or is
    refused; nothing is normalized.
    """
    if not value or len(value) > MAX_SCOPE_PATH_CHARS:
        raise ValueError(f"path must be 1-{MAX_SCOPE_PATH_CHARS} characters.")
    if any(not " " <= char <= "~" for char in value):
        raise ValueError("path must be printable ASCII.")
    if value.startswith("/") or value.endswith("/"):
        raise ValueError("path must be relative and name a file.")
    for part in value.split("/"):
        if not part or part in (".", ".."):
            raise ValueError("path must not contain empty, '.' or '..' components.")
        if len(part) > MAX_SCOPE_COMPONENT_CHARS:
            raise ValueError("a path component is too long.")
        if part[-1] in ". ":
            raise ValueError("a path component must not end with a dot or a space.")
        if any(char in _COMPONENT_FORBIDDEN for char in part):
            raise ValueError("a path component contains a character Windows reserves.")
        if part.casefold() == ".git":
            raise ValueError("a write scope never names Git's own directory.")
        if _SHORT_NAME.search(part):
            raise ValueError("a path component looks like an 8.3 short name.")
        if part.split(".")[0].rstrip(" ").upper() in _RESERVED_NAMES:
            raise ValueError("a path component is a reserved device name.")
    return value


class WriteScopeV1(BaseModel):
    """``write-scope.v1``: the one workspace effect a step may have (FD-10).

    Approved inside the plan activation, keyed by ``step_id``. It names one
    existing file to ``modify``, the SHA-256 of the bytes it must hold before
    the write, the detached HEAD the clone must be at, and the digest of the
    project config whose bytes the execution identity receives.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["write-scope.v1"]
    step_id: str
    path: str
    change_type: Literal["modify"]
    pre_image_sha256: str
    base_head_oid: str
    project_config_sha256: str

    @field_validator("step_id")
    @classmethod
    def _step_id(cls, value: str) -> str:
        return _slug(value, "step_id")

    @field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        return _repo_path(value)

    @field_validator("pre_image_sha256", "project_config_sha256")
    @classmethod
    def _digest(cls, value: str, info) -> str:
        if _HEX64.fullmatch(value) is None:
            raise ValueError(f"{info.field_name} must be 64 lowercase hexadecimal characters.")
        return value

    @field_validator("base_head_oid")
    @classmethod
    def _oid(cls, value: str) -> str:
        if _OID.fullmatch(value) is None:
            raise ValueError("base_head_oid must be a lowercase 40- or 64-character Git object id.")
        return value

    @property
    def sha256(self) -> str:
        return model_sha256(self)


def is_alpha_policy(policy: ExecutionPolicy) -> bool:
    """``policy`` is exactly the FD-8a Alpha profile."""
    return (
        type(policy) is ExecutionPolicy
        and policy.sha256 == ALPHA_EXECUTION_POLICY.sha256
        and (policy.review_required, policy.human_acceptance_required, policy.max_attempts)
        == (True, True, 1)
    )


def write_scopes_sha256(scopes: tuple[WriteScopeV1, ...]) -> str:
    """The digest of a plan's write scopes, in ``step_id`` order."""
    return hashlib.sha256(canonical_json_bytes({
        "schema_version": WRITE_SCOPE_SCHEMA_VERSION,
        "scopes": [scope.sha256 for scope in sorted(scopes, key=lambda scope: scope.step_id)],
    })).hexdigest()


EXACT_DIFF_APPROVAL_SUBJECT_SCHEMA_VERSION = "exact-diff-approval-subject.v1"
#: DL-4B S3. The fixed summary of the one ImplementationReport the write
#: handoff adapter returns. It states what AIDO observed, never what the
#: execution identity claimed, and the store accepts no other report.
WRITE_HANDOFF_REPORT_SUMMARY = (
    "AIDO observed exactly the approved single-file change (authority observations "
    "M0 and M1); the 5F2C write report is an execution claim."
)


def exact_diff_approval_subject_v1_sha256(
    *,
    plan_activation_subject_sha256: str,
    execution_plan_sha256: str,
    step_id: str,
    write_scope_sha256: str,
    approved_diff_artifact_sha256: str,
) -> str:
    """``exact-diff-approval-subject.v1``: what a human signs to approve the
    exact ``approved-diff-proposal.v2`` bytes (by digest) for one activated
    step's write scope. The activation is named by its own signed v2 subject,
    so the approval cannot be carried to another activation, plan, step,
    scope, workspace, config or identity boundary."""
    return hashlib.sha256(canonical_json_bytes({
        "schema_version": EXACT_DIFF_APPROVAL_SUBJECT_SCHEMA_VERSION,
        "kind": "exact_diff_approval",
        "plan_activation_subject_sha256": plan_activation_subject_sha256,
        "execution_plan_sha256": execution_plan_sha256,
        "step_id": step_id,
        "write_scope_sha256": write_scope_sha256,
        "approved_diff_artifact_sha256": approved_diff_artifact_sha256,
    })).hexdigest()


def plan_activation_subject_v2_sha256(
    *,
    project_contract_sha256: str,
    execution_plan_sha256: str,
    execution_policy_sha256: str,
    target_workspace_sha256: str,
    write_scopes_sha256: str,
    project_config_sha256: str,
    identity_boundary_sha256: str,
) -> str:
    """``plan-activation-subject.v2``: the digest a human signs to activate a
    plan in store.v4. Its ``schema_version`` key keeps it apart from every v1
    subject, which carries none."""
    return hashlib.sha256(canonical_json_bytes({
        "schema_version": PLAN_ACTIVATION_SUBJECT_V2_SCHEMA_VERSION,
        "kind": "plan_activation",
        "project_contract_sha256": project_contract_sha256,
        "execution_plan_sha256": execution_plan_sha256,
        "execution_policy_sha256": execution_policy_sha256,
        "target_workspace_sha256": target_workspace_sha256,
        "write_scopes_sha256": write_scopes_sha256,
        "project_config_sha256": project_config_sha256,
        "identity_boundary_sha256": identity_boundary_sha256,
    })).hexdigest()
