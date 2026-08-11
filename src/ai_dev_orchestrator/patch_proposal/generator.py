"""Deterministic patch **proposal** generator (Phase 5E1).

Phase 5E0 typed the proposal artifact and shipped no producer. This module is
the producer, and it is deliberately the dullest one that could exist: a pure
function over two already-loaded objects — an ``ApprovedL1PlanArtifact`` and a
``ProjectConfig`` — that restates the plan's own
``files_likely_to_change`` list as one prose ``PatchProposalChange`` each.

**This is not patch generation in the interesting sense.** The artifact it
returns carries **no unified diff**, no patch, no hunk, no edit script, no
before/after content, no source file content, no command, and no command output
— because :class:`PatchProposalChange` has no field for any of those (Phase 5E0
design §19.2), and a payload carrying one is rejected as an extra. There is
nothing applyable here for a future bug or a confused operator to feed to a
patch tool.

What this module deliberately cannot do:

- **No file IO.** It is handed objects. It opens nothing, reads nothing, and
  writes nothing — not the workspace, not the config, not the artifact, and not
  an output file. Persisting a proposal is the caller's problem, and the Phase
  5E1 CLI command deliberately prints to stdout instead.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  globbed, walked, or resolved. Paths stay **strings**, are never joined to a
  workspace root, and are never canonicalized — the Phase 5D0 guard is not
  called from here.
- **No file-content read.** Nothing is opened, so ``change_type`` is always
  ``"modify"``: distinguishing "create" from "modify" would require workspace
  metadata this phase does not gather. That is recorded as an *assumption* in
  the artifact rather than guessed at.
- **No file editing, no command execution.** Nothing is applied, run, or
  written. ``required_verification`` is plan prose that this module never reads
  as a command and never executes.
- **No model call, no network call, no environment read.** ``httpx``,
  ``requests``, ``LLMClient``, ``LLMClientConfig``,
  ``load_llm_client_config_from_env`` and ``GitHubClient`` are not imported, so
  no code path here can construct one. The produced provenance says
  ``engine="deterministic"``, ``real_call=False``, ``model=None`` — and those
  are facts about this function, not claims copied from an input.
- **No clock.** ``generated_at`` is ``None``. A deterministic generator that
  stamped a timestamp would return a different artifact on every call for the
  same inputs, which would make the output impossible to diff or re-verify.
- **No GitHub fetch or write.** The issue number and title come from the
  approved plan snapshot; nothing is confirmed against GitHub.
- **No approval.** Nothing here stamps, writes, or infers an approval. The
  approval inside the wrapped :class:`ApprovedL1PlanArtifact` is carried
  through **unchanged** and re-validated, never created.

The generator **fails closed**. Identity between the approved plan and the
project config is matched with exact string equality — no normalization, no case
folding, no prefix matching (design §3.5) — and a plan that names a path both as
likely-to-change and as forbidden is refused outright rather than resolved in
the permissive direction. Scope only ever narrows: candidates come from
``files_likely_to_change`` and nowhere else, and
``files_forbidden_or_out_of_scope``, ``proposed_steps``,
``required_verification``, ``risks`` and ``open_questions`` are never treated as
candidate paths.

Producing a proposal never means anything may be *done*. Reading file contents
(Phase 5D2), carrying a real diff (Phase 5E2), editing files, running commands,
committing, pushing, and opening PRs all remain proposed and not authorized.
"""

from __future__ import annotations

from pydantic import ValidationError

from ai_dev_orchestrator.handoff.models import ApprovedL1PlanArtifact
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.patch_proposal.models import (
    PATCH_PROPOSAL_MODE,
    PATCH_PROPOSAL_SCHEMA_VERSION,
    PatchProposalArtifact,
    _summarize_validation_error,
)


class PatchProposalGenerationError(Exception):
    """A proposal could not be generated, and none was.

    Raised for an identity mismatch between the approved plan and the project
    config, a plan that contradicts itself, a candidate count above the
    project's ``max_changed_files`` cap, and any failure of the Phase 5E0
    artifact validation (an unsafe path in particular).

    Messages name the *category* of failure and the field that failed. They
    never echo the artifact text, plan prose, rationales, or any supplied value
    — a proposal carries text an operator may not want surfaced in a log.

    There is deliberately no apply error, edit error, or command error here,
    because there is no apply, no edit, and no command.
    """


# What each proposed change says. Fixed prose: the same inputs must always
# produce the same artifact, so nothing here is templated with a value that
# could vary between runs.
_CHANGE_RATIONALE = (
    "The approved L1 plan lists this path under files_likely_to_change. No "
    "file contents were read."
)

_CHANGE_STEPS = (
    "Review this path against the approved L1 plan.",
    "Prepare a human-reviewed change consistent with the approved scope.",
)

_CHANGE_RISKS = (
    "This proposal did not read file contents and does not prove the change "
    "is sufficient.",
)

# Stated plainly, because each one is a limit a human reading the proposal must
# know about before treating it as more than a restatement of the plan.
_ASSUMPTIONS = (
    "No workspace contents were read: this proposal was built from the "
    "approved plan artifact and the project config alone.",
    "No path's existence was checked by this generator, so a proposed path may "
    "not exist in the workspace at all.",
    "change_type is 'modify' for every path because this phase uses no "
    "workspace metadata and no file contents, and cannot tell an existing file "
    "from one that would have to be created.",
)

_EMPTY_ASSUMPTION = (
    "The approved plan proposed no file paths under files_likely_to_change, so "
    "this proposal contains no changes."
)

_RISKS = (
    "No diff was generated: this proposal carries prose only, and nothing in "
    "it can be applied.",
    "No file contents were read, so the proposal cannot show what the affected "
    "paths currently contain or prove the described work is complete.",
)

# What a human must authorize before anything beyond prose happens. Carried in
# the artifact itself so the boundary travels with it.
NEXT_AUTHORIZATION_REQUIRED = (
    "Phase 5D2/5E2 or later must be explicitly authorized before reading file "
    "contents, generating diffs, editing files, running commands, committing, "
    "pushing, or opening PRs."
)


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    """Drop exact duplicate strings, keeping the first occurrence's position.

    Exact string equality only. Two spellings of one file are two strings here,
    and nothing is normalized, case-folded, or resolved to find out otherwise.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _check_identity(
    approved_plan: ApprovedL1PlanArtifact, project: ProjectConfig
) -> None:
    """Refuse an approved plan that is not this project's, exactly (design §3.5).

    String equality only. A plan approved for one project/repo grants nothing
    for another, and the mismatch is reported by *field name* — the differing
    values are never echoed.
    """
    repo = project.repo.github_repo
    mismatched = [
        label
        for label, left, right in (
            ("project_id", approved_plan.project_id, project.project_id),
            ("repo", approved_plan.repo, repo),
            ("plan.repo", approved_plan.plan.repo, repo),
            ("plan_provenance.repo", approved_plan.plan_provenance.repo, repo),
        )
        if left != right
    ]
    if mismatched:
        raise PatchProposalGenerationError(
            "the approved plan does not match this project config exactly; "
            "mismatched fields: " + ", ".join(mismatched) + ". A plan approved "
            "for one project or repo grants nothing for another."
        )


def _check_plan_level(approved_plan: ApprovedL1PlanArtifact) -> None:
    """Re-check the L1 invariants rather than trusting an upstream guarantee.

    ``ApprovedL1PlanArtifact`` already enforces both, exactly as Phase 5E0's
    artifact re-checks them: a downstream guard must not depend on an upstream
    invariant staying true forever, and a plan claiming L2 is corrupt or forged
    — not more authorized.
    """
    plan = approved_plan.plan
    if plan.automation_level != "L1":
        raise PatchProposalGenerationError(
            "approved_plan.plan.automation_level must be exactly 'L1'; a plan "
            "claiming a higher level is corrupt or forged, not more authorized."
        )
    if plan.requires_human_approval is not True:
        raise PatchProposalGenerationError(
            "approved_plan.plan.requires_human_approval must be True."
        )


def _select_candidate_paths(
    approved_plan: ApprovedL1PlanArtifact, project: ProjectConfig
) -> list[str]:
    """Choose the paths to propose, from ``files_likely_to_change`` alone.

    ``files_forbidden_or_out_of_scope`` is **never** a candidate source: naming
    a path as out of scope must not become a way to have it proposed. Neither
    are ``proposed_steps``, ``required_verification``, ``risks`` or
    ``open_questions`` — those are prose, and prose is never read as a path.

    A path listed as both likely-to-change and forbidden is a **contradiction**,
    and the whole run is refused. Resolving it in the permissive direction would
    mean a plan could smuggle a forbidden path back into scope by also
    mentioning it as likely.
    """
    plan = approved_plan.plan
    candidates = _dedupe_preserving_order(list(plan.files_likely_to_change))

    forbidden = set(plan.files_forbidden_or_out_of_scope)
    contradictory = [path for path in candidates if path in forbidden]
    if contradictory:
        raise PatchProposalGenerationError(
            f"the approved plan lists {len(contradictory)} path(s) in both "
            "files_likely_to_change and files_forbidden_or_out_of_scope. A "
            "self-contradicting plan is refused, never resolved in the "
            "permissive direction."
        )

    max_changed_files = project.workspace_policy.max_changed_files
    if len(candidates) > max_changed_files:
        raise PatchProposalGenerationError(
            f"the approved plan names {len(candidates)} distinct paths, which "
            "exceeds workspace_policy.max_changed_files "
            f"({max_changed_files}). No proposal was generated."
        )

    return candidates


def build_deterministic_patch_proposal(
    *,
    approved_plan: ApprovedL1PlanArtifact,
    project: ProjectConfig,
) -> PatchProposalArtifact:
    """Build a Phase 5E0 proposal artifact from an approved plan. Pure function.

    It is handed two already-loaded objects and returns a third. It performs no
    file IO, touches no workspace, reads no environment variable, calls no
    model, opens no socket, runs no command, contacts GitHub not at all, reads
    no clock, edits nothing, generates no diff, and writes no artifact file. It
    prints nothing.

    The result is **deterministic**: the same inputs always produce an identical
    artifact, down to the byte. That is why ``generated_at`` is ``None`` and why
    every rationale, step, assumption and risk below is fixed prose.

    The proposal is a restatement, not a discovery. Each proposed change names a
    path the approved plan *already named* under ``files_likely_to_change`` and
    says, in prose, that a human should review it — nothing more. The wrapped
    :class:`ApprovedL1PlanArtifact` travels through **unchanged**, so the
    approval a human gave stays attached to the thing they approved and the
    proposal cannot restate its own authorization.

    Args:
        approved_plan: A validated, human-approved L1 plan snapshot.
        project: The project config the plan must match exactly.

    Returns:
        A validated :class:`PatchProposalArtifact` carrying one ``"modify"``
        change per deduplicated ``files_likely_to_change`` path. ``changes`` is
        **empty** when the plan named no paths — a well-formed statement about
        an approved plan, not a defect.

    Raises:
        PatchProposalGenerationError: identity mismatch against the project
            config, a plan that is not an unescalated L1 plan, a plan naming a
            path as both likely-to-change and forbidden, more distinct paths
            than ``workspace_policy.max_changed_files`` allows, or any Phase 5E0
            artifact validation failure (an unsafe path in particular). Nothing
            partial is returned and nothing is written.
    """
    _check_identity(approved_plan, project)
    _check_plan_level(approved_plan)
    candidates = _select_candidate_paths(approved_plan, project)

    plan = approved_plan.plan

    assumptions = list(_ASSUMPTIONS)
    if not candidates:
        assumptions.append(_EMPTY_ASSUMPTION)

    payload = {
        "schema_version": PATCH_PROPOSAL_SCHEMA_VERSION,
        "mode": PATCH_PROPOSAL_MODE,
        "provenance": {
            # Facts about *this function*, not values copied from an input: it
            # is deterministic, it called nothing, and it used no model.
            "engine": "deterministic",
            "operation": "patch-proposal",
            "real_call": False,
            "model": None,
            "generated_at": None,
            "project_id": approved_plan.project_id,
            "repo": approved_plan.repo,
            "issue_number": approved_plan.issue_number,
            "title": plan.title,
        },
        "approved_plan": approved_plan,
        "changes": [
            {
                "path": path,
                # Always "modify": see the module docstring. Nothing was stat'd
                # or read, so "create" cannot be established.
                "change_type": "modify",
                "rationale": _CHANGE_RATIONALE,
                "proposed_steps": list(_CHANGE_STEPS),
                "risks": list(_CHANGE_RISKS),
                "requires_human_review": True,
            }
            for path in candidates
        ],
        "omitted_paths": [],
        "assumptions": assumptions,
        "risks": list(_RISKS),
        # The plan's open questions are still open. Copied as prose, never
        # answered here and never treated as paths.
        "open_questions": list(plan.open_questions),
        "file_contents_read": False,
        "files_edited": False,
        "commands_run": False,
        "requires_human_review": True,
        "next_authorization_required": NEXT_AUTHORIZATION_REQUIRED,
    }

    # Deliberately validated through the Phase 5E0 model rather than
    # constructed field by field: an unsafe path, an out-of-scope path, a
    # duplicate, or an identity slip is caught by the same rules that guard a
    # proposal arriving from outside this repository. The generator gets no
    # privileged path around them.
    try:
        return PatchProposalArtifact.model_validate(payload)
    except ValidationError as exc:
        raise PatchProposalGenerationError(
            "the generated patch proposal failed Phase 5E0 artifact validation "
            "and was discarded: " + _summarize_validation_error(exc)
        ) from exc
