"""The one human-initiated correction round's evidence and records (ALPHA-2B-T1).

PO-1 permits exactly ONE correction round after an eligible round-1 result:

- a valid review packet whose verdict is ``changes_requested``; or
- verification exit 2 with a valid ``verification-failed`` report whose
  postconditions say the workspace is still provably the approved state.

Nothing here calls a model, runs a process, touches the workspace or reads an
environment variable. Everything is derived from the run directory's recorded
evidence, which is read and cross-checked every time:

- the round-1 consumed authorization (its evidence copy and the draft the human
  completed must be the same bytes) is the baseline: target path, source
  digest and size, workspace HEAD;
- the frozen round-1 diff approval must be THIS run's implementer proposal with
  only the approval filled in, and its pre-image digest must be the baseline's;
- the round-1 write report must name the same approval, target and baseline
  size;
- the round-1 review record must come after that write, and its packet or
  verification report must name the same approval, target and post-image size.

The verdict and findings come from the recorded packet, parsed by the accepted
``ReviewPacket`` model, never from text supplied anywhere else.
``40-correction.json`` records a digest of all of it when the human begins the
round; the round-2 prepare and run rebuild it and refuse any difference.

The transmission copy (:class:`~ai_dev_orchestrator.supervised_implementer.correction.CorrectionInput`)
is built from this evidence in memory. The original evidence files are never
modified, and a redacted copy never replaces them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from ai_dev_orchestrator.task.run import (
    CORRECTION_DECLINED_FILE,
    CORRECTION_DECLINED_SCHEMA_VERSION,
    CORRECTION_FILE,
    CORRECTION_SCHEMA_VERSION,
    PLAN_APPROVED_FILE,
    ROUND_1,
    ROUND_2,
    StepRecord,
    TaskRecord,
    TaskRefused,
    _canonical,
    _check_only_approval_filled,
    _json_bytes,
    _read_bytes,
    _Reviewed,
    _strict_json_object,
    build_diff_draft,
    create_exclusive,
    read_implementer_diff_proposal,
    sha256_bytes,
    step_integrity_problem,
    utc_now,
)

#: Round-1 authorization fields a round-2 authorization must repeat exactly.
#: ``run_id``, ``issuance_sha256``, ``binding_sha256``, ``request_sha256`` and
#: the timestamps must differ instead: it is a fresh, separately consented one.
BASELINE_FIELDS = (
    "role",
    "candidate",
    "model",
    "provider",
    "project_id",
    "repo",
    "issue_number",
    "approved_plan_sha256",
    "project_config_sha256",
    "target_path",
    "change_type",
    "source_sha256",
    "source_bytes",
    "workspace_head_object_id",
    "workspace_git_state",
    "evidence_dir_sha256",
    "authorization_ledger_dir_sha256",
)

RESTORE_WARNING = (
    "'git restore' DISCARDS every uncommitted change to that file in the "
    "workspace, including the round-1 candidate AIDO wrote. The candidate stays "
    "recorded in this run directory (the approved diff, the implementer "
    "evidence and the step records), which AIDO has checked and will not change."
)

_CORRECTION_RECORD_KEYS = {
    "schema_version",
    "round",
    "reason",
    "initiated_at",
    "initiated_by",
    "round1_implementer_run_id",
    "baseline",
    "evidence_sha256",
    "source_records",
    "round1_evidence_preserved",
    "human_restore_required",
    "grants",
}


@dataclass(frozen=True)
class CorrectionEvidence:
    """Round 1's facts, as recorded. ``digest()`` is what the record pins."""

    reason: str
    round1_run_id: str
    round1_bound: dict
    baseline: dict
    previous_approved_diff: str
    verification: dict
    review: dict | None
    review_verdict: str
    source_records: dict

    def pinned(self) -> dict:
        return {
            "reason": self.reason,
            "round1_run_id": self.round1_run_id,
            "baseline": self.baseline,
            "previous_approved_diff": self.previous_approved_diff,
            "verification": self.verification,
            "review": self.review,
            "source_records": self.source_records,
        }

    def digest(self) -> str:
        return sha256_bytes(_canonical(self.pinned()).encode("ascii"))


def _relname(task: TaskRecord, path: str) -> str:
    return os.path.relpath(path, task.run_dir).replace(os.sep, "/")


def _source_digest(task: TaskRecord, path: str) -> tuple[str, str]:
    return _relname(task, path), sha256_bytes(_read_bytes(path, os.path.basename(path)))


def _refuse(reason: str) -> TaskRefused:
    return TaskRefused(reason)


def round1_bound(authorization_draft_path: str, evidence_run_dir: str) -> dict:
    """The consumed round-1 authorization's bound section, cross-checked."""
    from ai_dev_orchestrator.supervised_implementer.live import AUTHORIZATION_FILE
    from ai_dev_orchestrator.supervised_implementer.live_authorization import parse_authorization
    from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerError

    recorded = _read_bytes(os.path.join(evidence_run_dir, AUTHORIZATION_FILE), "the consumed authorization")
    if recorded != _read_bytes(authorization_draft_path, "the authorization draft"):
        raise _refuse(
            "the consumed authorization recorded in the implementer evidence is "
            f"not the bytes of {os.path.basename(authorization_draft_path)}."
        )
    try:
        bound = parse_authorization(recorded).bound.model_dump(mode="json")
    except SupervisedImplementerError:
        raise _refuse("the consumed authorization no longer parses.") from None
    if bound["run_id"] != os.path.basename(evidence_run_dir):
        raise _refuse("the consumed authorization names a different implementer run.")
    return bound


def _same_approval(label: str, record, artifact) -> None:
    approval = artifact.approval
    pairs = (
        (record.approved_by, approval.approved_by),
        (record.approved_at, approval.approved_at),
        (record.project_id, artifact.project_id),
        (record.repo, artifact.repo),
        (record.issue_number, artifact.issue_number),
        (record.title, artifact.title),
    )
    if any(left != right for left, right in pairs):
        raise _refuse(f"the {label} does not name round 1's diff approval.")


def collect_correction_evidence(task: TaskRecord, reviewed: _Reviewed) -> CorrectionEvidence:
    """Round 1's correction evidence, from recorded files only, or refuse.

    Raises :class:`TaskRefused` with the reason no correction is available:
    an ineligible result (``approve``, ``needs_human_review``) or anything
    malformed, mismatched or untrusted.
    """
    from ai_dev_orchestrator.file_editing import (
        FileEditingApprovalError,
        WorkspaceWriteReport,
        parse_approved_diff_proposal_artifact,
    )
    from ai_dev_orchestrator.review import ReviewPacket
    from ai_dev_orchestrator.supervised_implementer.live import (
        AUTHORIZATION_FILE,
        DIFF_FILE,
        OUTCOME_FILE,
        RESPONSE_FILE,
    )
    from ai_dev_orchestrator.verification import VerificationResultReport
    from pydantic import ValidationError

    if reviewed.rnd is not ROUND_1:
        raise _refuse("only a round-1 result can be corrected; there is no third round.")
    apply_record, review_record = reviewed.apply_record, reviewed.review_record
    if apply_record.exit_code != 0 or review_record.sequence <= apply_record.sequence:
        raise _refuse("the round-1 review record does not follow the round-1 write.")
    if review_record.exit_code not in (0, 2):
        raise _refuse("the round-1 review did not end with a reviewable result.")

    bound = round1_bound(reviewed.authorization_path, reviewed.evidence_run_dir)
    if bound["target_path"] != task.target_path or bound["change_type"] != "modify":
        raise _refuse("the round-1 authorization is not for this task's target.")

    approved_path = task.path(ROUND_1.diff_approved_file)
    approved_bytes = _read_bytes(approved_path, ROUND_1.diff_approved_file)
    _check_only_approval_filled(
        approved_bytes,
        build_diff_draft(task, read_implementer_diff_proposal(reviewed.evidence_run_dir)),
        ROUND_1.diff_approved_file,
    )
    try:
        artifact = parse_approved_diff_proposal_artifact(approved_bytes.decode("utf-8"))
    except FileEditingApprovalError:
        raise _refuse("the frozen round-1 diff approval no longer parses.") from None
    change = artifact.diff_proposal.changes[0]
    if change.path != task.target_path or change.change_type != "modify":
        raise _refuse("the round-1 approved diff is not one 'modify' of this task's target.")
    if change.pre_image_sha256 != bound["source_sha256"]:
        raise _refuse("the round-1 approved diff is not against the round-1 baseline source.")

    try:
        write = WorkspaceWriteReport.model_validate_json(
            _read_bytes(apply_record.stdout_path, "the round-1 write report")
        )
    except ValidationError:
        raise _refuse("the round-1 write report is not a valid written-and-verified report.") from None
    _same_approval("round-1 write report", write, artifact)
    if write.target.path != task.target_path or write.target.pre_image_bytes != bound["source_bytes"]:
        raise _refuse("the round-1 write report does not match the round-1 baseline.")

    review_bytes = _read_bytes(review_record.stdout_path, "the round-1 review record")
    review_value = None
    verdict = "none"
    try:
        if review_record.exit_code == 0:
            packet = ReviewPacket.model_validate_json(review_bytes)
            report = packet.verification
            verdict = packet.review.verdict
        else:
            packet = None
            report = VerificationResultReport.model_validate_json(review_bytes)
    except ValidationError:
        raise _refuse("the round-1 review record is not a valid packet or verification report.") from None
    _same_approval("round-1 verification report", report, artifact)
    if packet is not None:
        _same_approval("round-1 review packet", packet, artifact)
        if packet.target.path != task.target_path:
            raise _refuse("the round-1 review packet is for a different target.")
    if report.target.path != task.target_path or report.target.post_image_bytes != write.target.post_image_bytes:
        raise _refuse("the round-1 verification report does not match the round-1 write.")
    post = report.workspace_postcondition
    if not all(
        (
            post.git_state_reestablished,
            post.exact_approved_target_still_present,
            post.exact_post_image_still_matches,
            post.head_unchanged,
            post.only_approved_target_git_dirty,
            post.no_additional_git_visible_changes,
        )
    ):
        raise _refuse("the round-1 verification does not establish a trusted workspace state.")

    if packet is not None:
        if report.outcome != "verified":
            raise _refuse("the round-1 review packet's verification did not pass.")
        if verdict != "changes_requested":
            raise _refuse(f"the reviewer returned {verdict!r}, not 'changes_requested'.")
        reason = "reviewer_changes_requested"
        review_value = {
            "verdict": packet.review.verdict,
            "summary": packet.review.summary,
            "findings": [
                {
                    "severity": finding.severity,
                    "category": finding.category,
                    "line": finding.line,
                    "message": finding.message,
                    "suggested_action": finding.suggested_action,
                }
                for finding in packet.review.findings
            ],
        }
    else:
        if report.outcome != "verification-failed":
            raise _refuse("the round-1 verification report is not 'verification-failed'.")
        reason = "verification_failed"

    sources = [
        reviewed.authorization_path,
        os.path.join(reviewed.evidence_run_dir, AUTHORIZATION_FILE),
        os.path.join(reviewed.evidence_run_dir, DIFF_FILE),
        os.path.join(reviewed.evidence_run_dir, OUTCOME_FILE),
        # The round-1 candidate's complete text, as the model returned it.
        os.path.join(reviewed.evidence_run_dir, RESPONSE_FILE),
        task.path(PLAN_APPROVED_FILE),
        approved_path,
        apply_record.stdout_path,
        review_record.stdout_path,
    ]
    return CorrectionEvidence(
        reason=reason,
        round1_run_id=bound["run_id"],
        round1_bound=bound,
        baseline={
            "target_path": bound["target_path"],
            "source_sha256": bound["source_sha256"],
            "source_bytes": bound["source_bytes"],
            "workspace_head_object_id": bound["workspace_head_object_id"],
        },
        previous_approved_diff=change.unified_diff,
        verification={
            "outcome": report.outcome,
            "return_code": report.execution.return_code,
            "passed": report.execution.passed,
            "timed_out": report.execution.timed_out,
            "output_limit_exceeded": report.execution.output_limit_exceeded,
            "output_complete": report.output.complete,
            "output_text": report.output.combined_text,
        },
        review=review_value,
        review_verdict=verdict,
        source_records=dict(_source_digest(task, path) for path in sources),
    )


def correction_eligibility(task: TaskRecord, reviewed: _Reviewed) -> tuple[CorrectionEvidence | None, str | None]:
    """``(evidence, None)`` when a correction may be offered, else ``(None, why not)``."""
    try:
        return collect_correction_evidence(task, reviewed), None
    except TaskRefused as exc:
        return None, str(exc)


# -- the human's records --------------------------------------------------------------


def restore_instruction(task: TaskRecord) -> str:
    return f'git restore -- "{task.target_path}"'


def begin_correction(task: TaskRecord, reviewed: _Reviewed, now: datetime | None = None) -> str:
    """Record that a human began the correction round. Sends, writes and grants nothing.

    The evidence is re-collected and checked first; its digests are recorded so
    that any later change to a round-1 record refuses round 2.
    """
    evidence = collect_correction_evidence(task, reviewed)
    moment = (now or utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    record = {
        "schema_version": CORRECTION_SCHEMA_VERSION,
        "round": 2,
        "reason": evidence.reason,
        "initiated_at": moment.isoformat(),
        "initiated_by": "a human, by typing --begin-correction-round on task-continue",
        "round1_implementer_run_id": evidence.round1_run_id,
        "baseline": evidence.baseline,
        "evidence_sha256": evidence.digest(),
        "source_records": evidence.source_records,
        "round1_evidence_preserved": (
            "Every round-1 record listed in source_records stays in this run "
            "directory, unchanged; round 2 refuses if any of them changes."
        ),
        "human_restore_required": {
            "path": task.target_path,
            "command": restore_instruction(task),
            "warning": RESTORE_WARNING,
            "performed_by_aido": False,
        },
        "grants": (
            "Nothing. No model call, no workspace write, no approval and no Git "
            "operation. Round 2 needs a fresh, separately consented, single-use "
            "implementer authorization and its own exact-diff approval."
        ),
    }
    create_exclusive(task.path(CORRECTION_FILE), _json_bytes(record))
    return evidence.reason


def decline_correction(task: TaskRecord, reviewed: _Reviewed, now: datetime | None = None) -> None:
    """Record that a human declined the correction round. Terminal."""
    evidence = collect_correction_evidence(task, reviewed)
    moment = (now or utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    create_exclusive(
        task.path(CORRECTION_DECLINED_FILE),
        _json_bytes(
            {
                "schema_version": CORRECTION_DECLINED_SCHEMA_VERSION,
                "declined_at": moment.isoformat(),
                "reason_offered": evidence.reason,
                "evidence_sha256": evidence.digest(),
                "meaning": "A human declined the one correction round. The task ends "
                "at the human's own decision; AIDO does nothing further.",
            }
        ),
    )


def check_declined_record(task: TaskRecord) -> None:
    document = _strict_json_object(
        _read_bytes(task.path(CORRECTION_DECLINED_FILE), CORRECTION_DECLINED_FILE),
        CORRECTION_DECLINED_FILE,
    )
    if document.get("schema_version") != CORRECTION_DECLINED_SCHEMA_VERSION:
        raise _refuse(f"{CORRECTION_DECLINED_FILE} is not {CORRECTION_DECLINED_SCHEMA_VERSION}.")


def checked_correction_evidence(task: TaskRecord, reviewed: _Reviewed) -> CorrectionEvidence:
    """Re-collect round 1's evidence and require it to equal what the record pinned."""
    document = _strict_json_object(_read_bytes(task.path(CORRECTION_FILE), CORRECTION_FILE), CORRECTION_FILE)
    if set(document) != _CORRECTION_RECORD_KEYS or document["schema_version"] != CORRECTION_SCHEMA_VERSION:
        raise _refuse(f"{CORRECTION_FILE} is not a valid {CORRECTION_SCHEMA_VERSION} record.")
    evidence = collect_correction_evidence(task, reviewed)
    if (
        document["round"] != 2
        or document["reason"] != evidence.reason
        or document["round1_implementer_run_id"] != evidence.round1_run_id
        or _canonical(document["baseline"]) != _canonical(evidence.baseline)
        or _canonical(document["source_records"]) != _canonical(evidence.source_records)
        or document["evidence_sha256"] != evidence.digest()
    ):
        raise _refuse(
            "a round-1 record changed after the correction round began; the "
            "correction would no longer be built from the evidence the human saw."
        )
    return evidence


def correction_input(evidence: CorrectionEvidence, workspace_path: str):
    """The in-memory transmission copy for round 2. Never written over evidence."""
    from pydantic import ValidationError

    from ai_dev_orchestrator.supervised_implementer.correction import (
        CorrectionBaseline,
        build_correction_input,
    )

    try:
        return build_correction_input(
            reason=evidence.reason,
            baseline=CorrectionBaseline.model_validate(evidence.baseline),
            previous_approved_diff=evidence.previous_approved_diff,
            verification=evidence.verification,
            review=evidence.review,
            workspace_path=workspace_path,
        )
    except ValidationError:
        raise _refuse("the round-1 evidence does not form a valid correction.") from None


# -- round-2 authorization binding ----------------------------------------------------------


def read_bound(path: str) -> dict:
    """A round's authorization draft (or consented copy): its checked bound section."""
    from pydantic import ValidationError

    from ai_dev_orchestrator.supervised_implementer.live_authorization import (
        AuthorizationBound,
        compute_binding_sha256,
    )

    document = _strict_json_object(_read_bytes(path, os.path.basename(path)), os.path.basename(path))
    bound = document.get("bound")
    if not isinstance(bound, dict):
        raise _refuse(f"{os.path.basename(path)} has no bound section.")
    try:
        AuthorizationBound.model_validate(bound)
    except ValidationError:
        raise _refuse(f"{os.path.basename(path)} has a malformed bound section.") from None
    if compute_binding_sha256(bound) != bound.get("binding_sha256"):
        raise _refuse(f"{os.path.basename(path)}'s bound section was edited.")
    return bound


def round2_binding_problem(path: str, first_bound: dict) -> str | None:
    """Why a round-2 authorization does not bind round 1's baseline, or None.

    Checked before consent is offered and again before the run, so a
    mismatched authorization is never offered for consent and never sent.
    """
    try:
        bound = read_bound(path)
    except TaskRefused as exc:
        return str(exc)
    mismatched = [
        name
        for name in BASELINE_FIELDS
        if type(bound.get(name)) is not type(first_bound.get(name)) or bound.get(name) != first_bound.get(name)
    ]
    if mismatched:
        return (
            f"{os.path.basename(path)} does not bind round 1's baseline; mismatched: "
            + ", ".join(mismatched)
            + ". The task is never silently re-baselined."
        )
    for name in ("run_id", "issuance_sha256", "binding_sha256"):
        if bound.get(name) == first_bound.get(name):
            return f"{os.path.basename(path)} reuses round 1's {name}; round 2 needs a fresh authorization."
    if bound.get("request_sha256") == first_bound.get("request_sha256"):
        return (
            f"{os.path.basename(path)} binds round 1's request, which carries no "
            "correction; it is not a round-2 authorization."
        )
    return None


def round2_consumed_problem(path: str, evidence_run_dir: str, first_bound: dict) -> str | None:
    """Why a consumed round-2 run is not this round's, or None."""
    from ai_dev_orchestrator.supervised_implementer.live import AUTHORIZATION_FILE

    if os.path.basename(evidence_run_dir) == first_bound["run_id"]:
        return "the round-2 authorization names round 1's implementer run."
    problem = round2_binding_problem(path, first_bound)
    if problem is not None:
        return problem
    try:
        recorded = _read_bytes(os.path.join(evidence_run_dir, AUTHORIZATION_FILE), "the consumed authorization")
        draft = _read_bytes(path, os.path.basename(path))
    except TaskRefused as exc:
        return str(exc)
    if recorded != draft:
        return (
            "the round-2 implementer evidence records a different authorization "
            f"than {os.path.basename(path)}."
        )
    return None


# -- round-2 terminal evidence (ALPHA-2B-T1-FU1) ----------------------------------------------


def round2_terminal_problem(
    task: TaskRecord,
    evidence_run_dir: str,
    first_bound: dict,
    apply_record: StepRecord,
    review_record: StepRecord,
) -> str | None:
    """Why round 2's recorded terminal evidence is not trustworthy, or None.

    Runs at the terminal consumption boundary on EVERY status read, from the
    recorded files only. The derived summary is never consulted: it is not
    evidence, and writing it must not be the only place evidence is checked.
    Mirrors the round-1 checks in :func:`collect_correction_evidence`, bound to
    round 2's own frozen approval, and reuses the same accepted parsers.
    """
    from ai_dev_orchestrator.file_editing import (
        FileEditingApprovalError,
        WorkspaceWriteReport,
        parse_approved_diff_proposal_artifact,
    )
    from ai_dev_orchestrator.review import ReviewPacket
    from ai_dev_orchestrator.verification import VerificationResultReport
    from pydantic import ValidationError

    try:
        if apply_record.exit_code != 0 or review_record.exit_code not in (0, 2):
            return "the round-2 write or review step did not end in a reviewable state."
        if review_record.sequence <= apply_record.sequence:
            return "the round-2 review record does not follow the round-2 write."
        for record in (apply_record, review_record):
            problem = step_integrity_problem(record)
            if problem is not None:
                return problem

        approved_bytes = _read_bytes(task.path(ROUND_2.diff_approved_file), ROUND_2.diff_approved_file)
        _check_only_approval_filled(
            approved_bytes,
            build_diff_draft(task, read_implementer_diff_proposal(evidence_run_dir)),
            ROUND_2.diff_approved_file,
        )
        if approved_bytes == _read_bytes(task.path(ROUND_1.diff_approved_file), ROUND_1.diff_approved_file):
            return "the round-2 diff approval is round 1's approval; round 2 needs its own."
        try:
            artifact = parse_approved_diff_proposal_artifact(approved_bytes.decode("utf-8"))
        except FileEditingApprovalError:
            return "the frozen round-2 diff approval no longer parses."
        change = artifact.diff_proposal.changes[0]
        if change.path != task.target_path or change.change_type != "modify":
            return "the round-2 approved diff is not one 'modify' of this task's target."
        if change.pre_image_sha256 != first_bound["source_sha256"]:
            return "the round-2 approved diff is not against the original baseline source."

        try:
            write = WorkspaceWriteReport.model_validate_json(
                _read_bytes(apply_record.stdout_path, "the round-2 write report")
            )
        except ValidationError:
            return "the round-2 write report is not a valid written-and-verified report."
        _same_approval("round-2 write report", write, artifact)
        if write.target.path != task.target_path or write.target.pre_image_bytes != first_bound["source_bytes"]:
            return "the round-2 write report does not match the original baseline."

        review_bytes = _read_bytes(review_record.stdout_path, "the round-2 review record")
        try:
            if review_record.exit_code == 0:
                packet = ReviewPacket.model_validate_json(review_bytes)
                report = packet.verification
            else:
                packet = None
                report = VerificationResultReport.model_validate_json(review_bytes)
        except ValidationError:
            return "the round-2 review record is not a valid review packet or verification report."
        _same_approval("round-2 verification report", report, artifact)
        if packet is not None:
            _same_approval("round-2 review packet", packet, artifact)
            if packet.target.path != task.target_path:
                return "the round-2 review packet is for a different target."
        if report.target.path != task.target_path or report.target.post_image_bytes != write.target.post_image_bytes:
            return "the round-2 verification report does not match the round-2 write."
        post = report.workspace_postcondition
        if not all(
            (
                post.git_state_reestablished,
                post.exact_approved_target_still_present,
                post.exact_post_image_still_matches,
                post.head_unchanged,
                post.only_approved_target_git_dirty,
                post.no_additional_git_visible_changes,
            )
        ):
            return "the round-2 verification does not establish a trusted workspace state."
        if packet is not None and report.outcome != "verified":
            return "the round-2 review packet's verification did not pass."
        if packet is None and report.outcome != "verification-failed":
            return "the round-2 verification report is not 'verification-failed'."
    except TaskRefused as exc:
        return str(exc)
    return None


# -- the final (round-2) summary -------------------------------------------------------------


def _readiness(verification_outcome: str, verdict: str | None) -> str:
    if verification_outcome != "verified":
        return "NOT READY: round-2 verification did not pass."
    return {
        "approve": "READY FOR YOUR DECISION: round-2 verification passed and the reviewer returned 'approve'.",
        "changes_requested": "NOT RECOMMENDED AS IS: the reviewer requested changes again. No further round exists.",
        "needs_human_review": "NEEDS YOUR REVIEW: the reviewer asked for human review.",
    }.get(verdict or "", "UNKNOWN VERDICT.")


def render_round2_summary(
    task: TaskRecord,
    evidence: CorrectionEvidence,
    second_bound: dict,
    apply_record: StepRecord,
    review_record: StepRecord,
) -> str:
    """The DERIVED final summary. Not evidence, and it says so."""
    from ai_dev_orchestrator.file_editing import WorkspaceWriteReport
    from ai_dev_orchestrator.review import ReviewPacket
    from ai_dev_orchestrator.verification import VerificationResultReport

    write = WorkspaceWriteReport.model_validate_json(_read_bytes(apply_record.stdout_path, "the write report"))
    review_bytes = _read_bytes(review_record.stdout_path, "the review record")
    packet = ReviewPacket.model_validate_json(review_bytes) if review_record.exit_code == 0 else None
    report = packet.verification if packet is not None else VerificationResultReport.model_validate_json(review_bytes)
    post = report.workspace_postcondition
    approved = _strict_json_object(
        _read_bytes(task.path(ROUND_2.diff_approved_file), ROUND_2.diff_approved_file),
        ROUND_2.diff_approved_file,
    )
    post_sha = approved["diff_proposal"]["changes"][0]["post_image_sha256"]

    round1_outcome = (
        f"verification passed; the reviewer returned {evidence.review_verdict!r}"
        if evidence.reason == "reviewer_changes_requested"
        else "verification did not pass (verification-failed)"
    )
    lines = [
        "AIDO TASK SUMMARY — FINAL (after the one correction round)",
        "Derived by AIDO from the records in this run directory. It is NOT itself",
        "evidence: the authoritative records are the files it names.",
        "",
        f"Task:    {task.title} (issue {task.issue_number})",
        f"Project: {task.project_id} ({task.repo})",
        f"Target:  {task.target_path}",
        "",
        "Round 1 (superseded; its records are kept unchanged)",
        f"  outcome:   {round1_outcome}",
        f"  diff:      {ROUND_1.diff_text_file} (approved as {ROUND_1.diff_approved_file})",
        f"  records:   {CORRECTION_FILE} pins their digests",
        "  The human then restored the target to its original baseline; AIDO restored nothing.",
        "",
        "Round 2 — AIDO-observed facts",
        f"  baseline:     the round-2 authorization bound HEAD {second_bound['workspace_head_object_id']}",
        f"                and source sha256 {second_bound['source_sha256']} ({second_bound['source_bytes']} bytes),",
        "                the same as round 1's, observed by AIDO on a clean tree",
        f"  diff:         {ROUND_2.diff_text_file}, against the ORIGINAL baseline",
        f"  write:        {write.outcome!r}, {write.target.pre_image_bytes} -> "
        f"{write.target.post_image_bytes} bytes [{os.path.basename(apply_record.stdout_path)}]",
        f"  verification: {report.outcome!r}, return code {report.execution.return_code}, "
        f"passed {report.execution.passed}",
    ]
    if packet is not None:
        reviewer = packet.reviewer
        lines.append(
            f"  reviewer:     {reviewer.provider} / {reviewer.model} at {reviewer.endpoint_host} "
            f"({'TLS' if reviewer.transport_tls else 'NOT TLS-ENCRYPTED'}), "
            f"{reviewer.semantic_requests} of at most {reviewer.max_semantic_requests} semantic requests"
        )
    else:
        lines.append("  reviewer:     not contacted (verification did not pass)")
    lines += [
        "",
        "Final workspace state, as AIDO last observed it (at the end of the round-2",
        "verification; AIDO has not looked since and changed nothing after it)",
        f"  target holds the round-2 approved post-image: {post.exact_post_image_still_matches} "
        f"(sha256 {post_sha}, {write.target.post_image_bytes} bytes)",
        f"  HEAD unchanged during verification:          {post.head_unchanged}",
        f"  Git-visible dirty paths:                     {', '.join(post.dirty_paths) or '(none)'}",
        "  Nothing is committed: AIDO created no branch, commit, push or PR.",
    ]
    if packet is not None:
        review = packet.review
        lines += [
            "",
            "Round-2 reviewer model claims (NOT verified by AIDO)",
            f"  verdict: {review.verdict}",
            f"  summary: {review.summary}",
            f"  findings: {len(review.findings)}",
        ]
        for finding in review.findings:
            where = f" line {finding.line}" if finding.line is not None else ""
            lines.append(f"    - [{finding.severity}/{finding.category}]{where}: {finding.message}")
            lines.append(f"      suggested: {finding.suggested_action}")
        lines.append(f"  residual risks: {len(review.residual_risks)}")
        lines.extend(f"    - {risk}" for risk in review.residual_risks)
        lines.append(f"  human notes: {len(review.human_notes)}")
        lines.extend(f"    - {note}" for note in review.human_notes)
    lines += [
        "",
        "AIDO readiness (a fixed mapping of the lines above, not a judgment)",
        f"  {_readiness(report.outcome, packet.review.verdict if packet is not None else None)}",
        "",
        "Records",
        f"  round-2 review record, exactly as emitted: {os.path.basename(review_record.stdout_path)}",
        f"  round-2 write report, exactly as emitted:  {os.path.basename(apply_record.stdout_path)}",
        f"  round-1 summary (if written):              {ROUND_1.summary_file}",
        "  The raw reviewer model response is not retained (5F2E design).",
        "",
        "Next: your decision. This was the only correction round; AIDO offers no",
        "other. A model proposing new code is not evidence that the correction",
        "succeeded. If you accept the change, commit it yourself; if not, revert",
        "it with your own Git workflow.",
    ]
    return "\n".join(lines) + "\n"


def write_round2_summary(
    task: TaskRecord,
    evidence: CorrectionEvidence,
    second_bound: dict,
    apply_record: StepRecord,
    review_record: StepRecord,
) -> str:
    text = render_round2_summary(task, evidence, second_bound, apply_record, review_record)
    if not os.path.lexists(task.path(ROUND_2.summary_file)):
        create_exclusive(task.path(ROUND_2.summary_file), text.encode("utf-8"))
    return text


__all__ = [
    "BASELINE_FIELDS",
    "CorrectionEvidence",
    "RESTORE_WARNING",
    "begin_correction",
    "check_declined_record",
    "checked_correction_evidence",
    "collect_correction_evidence",
    "correction_eligibility",
    "correction_input",
    "decline_correction",
    "read_bound",
    "restore_instruction",
    "round1_bound",
    "round2_binding_problem",
    "round2_consumed_problem",
    "round2_terminal_problem",
    "write_round2_summary",
]

