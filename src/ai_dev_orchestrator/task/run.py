"""The task run directory, its drafts, and its stage (ALPHA-2A-T1).

One task is one run directory. Everything AIDO writes there is created
exclusively and never rewritten. A human edits exactly three files in place,
and only their approval or consent block:

```text
task.json                       AIDO   the task inputs and the pinned project config digest
10-plan.draft.json              AIDO   L1 plan + EMPTY approval      -> human fills "approval"
11-plan.approved.json           AIDO   byte-exact freeze of the human's approved file
20-authorization-<n>.json       AIDO   P1B prepare's draft          -> human fills "consent"
implementer-evidence/<run_id>/  AIDO   the P1B run evidence (diff-proposal.json, outcome.json, ...)
30-proposed.diff                AIDO   the proposed unified diff, for reading
30-diff.draft.json              AIDO   approved-diff-proposal.v2 + EMPTY approval -> human fills "approval"
31-diff.approved.json           AIDO   byte-exact freeze of the human's approved file
steps/NN-<step>.exit-<c>.stdout AIDO   exactly what each accepted command wrote to stdout
steps/NN-<step>.exit-<c>.stderr AIDO   exactly what it wrote to stderr
summary.txt                     AIDO   a DERIVED summary; not evidence
```

P0-UX1 (D-2′) adds an interactive alternative to the hand edit. ``task-approve``
records one write-once decision per approval or consent, bound to the exact
draft it displayed; the block is serialized from it only inside that stage's
own ``task-continue`` (see :mod:`ai_dev_orchestrator.task.approve`):

```text
12-plan.decision.json                AIDO   the human's H1 decision (approve or reject)
20-authorization-<n>.decision.json   AIDO   the human's H2 decision (round 2: 50-...)
20-authorization-<n>.consented.json  AIDO   the consent serialized from it, consumed by P1B
32-diff.decision.json                AIDO   the human's H3 decision (round 2: 62-diff.decision.json)
```

ALPHA-2B-T1 adds ONE optional, human-initiated correction round (PO-1/2/3).
Round 1 keeps every name above. Round 2 has its own, so no round-1 record can
ever be read as a round-2 one:

```text
40-correction.json              AIDO   the human started the correction round (+ evidence digests)
40-correction.declined.json     AIDO   the human declined it (terminal)
50-authorization-<n>.json       AIDO   round-2 P1B draft (fresh, single-use) -> human fills "consent"
60-proposed.diff                AIDO   the round-2 diff, against the ORIGINAL baseline
60-diff.draft.json              AIDO   round-2 approved-diff-proposal.v2 + EMPTY approval
61-diff.approved.json           AIDO   byte-exact freeze of the human's round-2 approval
steps/NN-<step>-r2.exit-...     AIDO   round-2 step records
summary-r2.txt                  AIDO   the DERIVED final summary; not evidence
```

Between the rounds a HUMAN restores the target (AIDO never does); round 2's
prepare and run then observe the clean tree, the round-1 HEAD and the round-1
source bytes themselves. There is never a third round.

**The stage is derived, every time, from these files.** There is no state
machine store and no caller-supplied stage. A file's presence says which step
ran; the accepted commands' own records say how it ended.

**Nothing here creates an approval or a consent.** Drafts carry empty approval
stubs. On the manual path a human types every value; freezing only checks that
the human changed nothing outside the approval block, then copies their bytes.
On the interactive path the block is serialized from the human's recorded
decision by :mod:`ai_dev_orchestrator.task.approve`, never invented here. Either
way the accepted strict parser decides whether the approval is valid. Nothing here reads an
environment variable, calls a model, runs a process or touches the workspace.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai_dev_orchestrator.handoff.models import (
    ApprovedPlanError,
    parse_approved_l1_plan_artifact,
)
from ai_dev_orchestrator.models import ProjectConfig

TASK_SCHEMA_VERSION = "aido-task.v1"

TASK_FILE = "task.json"
PLAN_DRAFT_FILE = "10-plan.draft.json"
PLAN_APPROVED_FILE = "11-plan.approved.json"
PLAN_DECISION_FILE = "12-plan.decision.json"
EVIDENCE_DIR = "implementer-evidence"
DIFF_TEXT_FILE = "30-proposed.diff"
DIFF_DRAFT_FILE = "30-diff.draft.json"
DIFF_APPROVED_FILE = "31-diff.approved.json"
STEPS_DIR = "steps"
SUMMARY_FILE = "summary.txt"

CORRECTION_FILE = "40-correction.json"
CORRECTION_DECLINED_FILE = "40-correction.declined.json"
CORRECTION_SCHEMA_VERSION = "aido-task-correction.v1"
CORRECTION_DECLINED_SCHEMA_VERSION = "aido-task-correction-declined.v1"

STEP_INTEGRITY_SCHEMA_VERSION = "aido-task-step-integrity.v1"
INTEGRITY_SUFFIX = ".integrity.json"
#: Round-2 terminal evidence steps (ALPHA-2B-T1-FU2). Round 1 gets no integrity record.
ROUND2_INTEGRITY_STEPS = ("apply-r2", "review-r2")
ATTEMPT_BEGUN_SCHEMA_VERSION = "aido-task-attempt-begun.v1"
BEGUN_INFIX = ".begun-"

_AUTHORIZATION_RE = re.compile(r"^20-authorization-([1-9][0-9]*)\.json$")
_STEP_RE = re.compile(
    r"^([0-9]{2,})-((?:prepare|implementer-run|apply|review)(?:-r2)?)"
    r"\.exit-([0-9]+|error)\.(stdout|stderr)$"
)


@dataclass(frozen=True)
class Round:
    """Every file and step name one round uses. Round 1 is exactly Alpha 2A's."""

    number: int
    authorization_re: re.Pattern
    authorization_name: str
    diff_text_file: str
    diff_draft_file: str
    diff_approved_file: str
    diff_decision_file: str
    step_prepare: str
    step_implementer: str
    step_apply: str
    step_review: str
    summary_file: str
    stage_prefix: str


ROUND_1 = Round(
    number=1,
    authorization_re=_AUTHORIZATION_RE,
    authorization_name="20-authorization-{n}.json",
    diff_text_file=DIFF_TEXT_FILE,
    diff_draft_file=DIFF_DRAFT_FILE,
    diff_approved_file=DIFF_APPROVED_FILE,
    diff_decision_file="32-diff.decision.json",
    step_prepare="prepare",
    step_implementer="implementer-run",
    step_apply="apply",
    step_review="review",
    summary_file=SUMMARY_FILE,
    stage_prefix="",
)
ROUND_2 = Round(
    number=2,
    authorization_re=re.compile(r"^50-authorization-([1-9][0-9]*)\.json$"),
    authorization_name="50-authorization-{n}.json",
    diff_text_file="60-proposed.diff",
    diff_draft_file="60-diff.draft.json",
    diff_approved_file="61-diff.approved.json",
    diff_decision_file="62-diff.decision.json",
    step_prepare="prepare-r2",
    step_implementer="implementer-run-r2",
    step_apply="apply-r2",
    step_review="review-r2",
    summary_file="summary-r2.txt",
    stage_prefix="round2_",
)
ROUNDS = {1: ROUND_1, 2: ROUND_2}

#: The plan and diff approval stubs: four EMPTY strings a human must type.
EMPTY_APPROVAL = {"approved_by": "", "approved_at": "", "approval_text": "", "source": ""}

MAX_DESCRIPTION_CHARS = 20_000
MAX_TITLE_CHARS = 300

# The per-stage confirmation flags, as the CLI option names. A human types them
# on ``task-continue``; the coordinator never supplies one itself.
PREPARE_FLAGS = ("--prepare-supervised-implementation",)
IMPLEMENTER_FLAGS = ("--transmit-approved-source", "--real-implementer")
APPLY_AND_REVIEW_FLAGS = (
    "--apply-approved-plan",
    "--write-approved-file",
    "--verify-approved-file-edit",
    "--real-reviewer",
)
REVIEW_FLAGS = ("--verify-approved-file-edit", "--real-reviewer")
#: ALPHA-2B-T1: the human's choice at a correction offer. Neither sends,
#: writes or approves anything; each only records the human's decision.
BEGIN_CORRECTION_FLAGS = ("--begin-correction-round",)
DECLINE_CORRECTION_FLAGS = ("--decline-correction",)
ALL_FLAGS = (
    PREPARE_FLAGS
    + IMPLEMENTER_FLAGS
    + APPLY_AND_REVIEW_FLAGS
    + BEGIN_CORRECTION_FLAGS
    + DECLINE_CORRECTION_FLAGS
)

DIFF_NEXT_AUTHORIZATION = (
    "task-continue with --apply-approved-plan, --write-approved-file, "
    "--verify-approved-file-edit and --real-reviewer, typed by a human: the "
    "accepted 5F2C writer applies this exact diff, then the accepted 5F2E "
    "reviewer runs the 5F2D verification and one review."
)


class TaskRefused(Exception):
    """The coordinator refused. Nothing was written unless the message says so."""


# -- small helpers --------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return sha256_bytes(handle.read())


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise TaskRefused(f"duplicate JSON key {key!r}; the file is refused, not repaired.")
        result[key] = value
    return result


def _strict_json_object(data: bytes, label: str) -> dict:
    try:
        decoded = json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TaskRefused(f"{label} is not valid UTF-8 JSON.") from None
    if not isinstance(decoded, dict):
        raise TaskRefused(f"{label} must be one JSON object.")
    return decoded


def _read_bytes(path: str, label: str) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        raise TaskRefused(f"{label} could not be read.") from None


def create_exclusive(path: str, data: bytes) -> None:
    """Create ``path`` exclusively and write it whole. Never overwrites."""
    from ai_dev_orchestrator.supervised_implementer.live import _create_exclusive

    _create_exclusive(path, data)


def _same_or_under(candidate: str, root: str) -> bool:
    candidate = os.path.normcase(candidate)
    root = os.path.normcase(root).rstrip("\\/")
    return candidate == root or candidate.startswith(root + os.sep)


def require_outside_workspace(path: str, workspace_path: str, label: str) -> None:
    """Refuse ``path`` inside the workspace, lexically and canonically."""
    lexical = os.path.abspath(path)
    if _same_or_under(lexical, os.path.abspath(workspace_path)) or _same_or_under(
        os.path.realpath(lexical), os.path.realpath(workspace_path)
    ):
        raise TaskRefused(
            f"the {label} is inside the project's configured workspace. Run "
            "artifacts must live outside the workspace they refer to."
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def consent_decision_path(authorization_path: str) -> str:
    """``20-authorization-<n>.json`` -> ``20-authorization-<n>.decision.json``."""
    return authorization_path[: -len(".json")] + ".decision.json"


def consented_path(authorization_path: str) -> str:
    """``20-authorization-<n>.json`` -> ``20-authorization-<n>.consented.json``."""
    return authorization_path[: -len(".json")] + ".consented.json"


# -- the task record --------------------------------------------------------------


@dataclass(frozen=True)
class TaskRecord:
    """``task.json``: the human's task inputs and the pinned project config."""

    run_dir: str
    created_at: str
    project_config: str
    project_config_sha256: str
    project_id: str
    repo: str
    issue_number: int
    title: str
    description: str
    target_path: str

    def path(self, name: str) -> str:
        return os.path.join(self.run_dir, name)


_TASK_FIELDS = (
    "created_at",
    "project_config",
    "project_config_sha256",
    "project_id",
    "repo",
    "issue_number",
    "title",
    "description",
    "target_path",
)


def _check_task_inputs(*, title: object, description: object, issue_number: object, target_path: object) -> None:
    if type(title) is not str or not title.strip() or len(title) > MAX_TITLE_CHARS:
        raise TaskRefused(f"the title must be non-blank text of at most {MAX_TITLE_CHARS} characters.")
    if "\n" in title or "\r" in title:
        raise TaskRefused("the title must be one line.")
    if type(description) is not str or not description.strip():
        raise TaskRefused("the task description must be non-blank text.")
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise TaskRefused(f"the task description is longer than {MAX_DESCRIPTION_CHARS} characters.")
    if type(issue_number) is not int or isinstance(issue_number, bool) or issue_number <= 0:
        raise TaskRefused("the issue number must be a positive integer.")
    if (
        type(target_path) is not str
        or not target_path
        or target_path != target_path.strip()
        or "\\" in target_path
        or target_path.startswith("/")
        or ":" in target_path
        or any(part in ("", ".", "..") for part in target_path.split("/"))
    ):
        raise TaskRefused(
            "the target path must be one repo-relative path with forward slashes, "
            "no '.', '..' or empty segment, no drive and no leading slash."
        )


def create_run(
    *,
    runs_root: str,
    project_config_path: str,
    project: ProjectConfig,
    title: str,
    description: str,
    issue_number: int,
    target_path: str,
    now: datetime | None = None,
) -> TaskRecord:
    """Create one run directory with ``task.json`` and the plan draft.

    ``runs_root`` is resolved to its canonical path (the P1B evidence directory
    under it must be named canonically) and must lie outside the workspace.
    """
    _check_task_inputs(
        title=title, description=description, issue_number=issue_number, target_path=target_path
    )
    workspace = project.repo.workspace_path
    root = os.path.realpath(os.path.abspath(runs_root))
    require_outside_workspace(root, workspace, "runs root")
    config_path = os.path.realpath(os.path.abspath(project_config_path))
    config_digest = sha256_file(config_path)
    os.makedirs(root, exist_ok=True)

    moment = (now or utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    name = moment.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    run_dir = os.path.join(root, name)
    os.mkdir(run_dir)
    os.mkdir(os.path.join(run_dir, EVIDENCE_DIR))
    os.mkdir(os.path.join(run_dir, STEPS_DIR))

    record = TaskRecord(
        run_dir=run_dir,
        created_at=moment.isoformat(),
        project_config=config_path,
        project_config_sha256=config_digest,
        project_id=project.project_id,
        repo=project.repo.github_repo,
        issue_number=issue_number,
        title=title,
        description=description,
        target_path=target_path,
    )
    document = {"schema_version": TASK_SCHEMA_VERSION}
    document.update({name: getattr(record, name) for name in _TASK_FIELDS})
    create_exclusive(record.path(TASK_FILE), _json_bytes(document))
    create_exclusive(record.path(PLAN_DRAFT_FILE), _json_bytes(build_plan_draft(record)))
    return record


def load_task(run_dir: str) -> TaskRecord:
    """Read ``task.json`` from a run directory, or refuse."""
    if type(run_dir) is not str or not run_dir:
        raise TaskRefused("a run directory is required.")
    canonical = os.path.realpath(os.path.abspath(run_dir))
    path = os.path.join(canonical, TASK_FILE)
    if not os.path.isfile(path):
        raise TaskRefused("the run directory holds no task.json; it is not an AIDO task run.")
    document = _strict_json_object(_read_bytes(path, "task.json"), "task.json")
    if document.get("schema_version") != TASK_SCHEMA_VERSION:
        raise TaskRefused(f"task.json is not {TASK_SCHEMA_VERSION}.")
    if set(document) != {"schema_version", *_TASK_FIELDS}:
        raise TaskRefused("task.json has missing or unexpected fields.")
    record = TaskRecord(run_dir=canonical, **{name: document[name] for name in _TASK_FIELDS})
    _check_task_inputs(
        title=record.title,
        description=record.description,
        issue_number=record.issue_number,
        target_path=record.target_path,
    )
    for name in ("created_at", "project_config", "project_config_sha256", "project_id", "repo"):
        if type(getattr(record, name)) is not str or not getattr(record, name):
            raise TaskRefused(f"task.json field {name!r} is invalid.")
    return record


def check_config_unchanged(task: TaskRecord) -> None:
    """A run uses ONE project config. A changed file refuses; start a new task."""
    try:
        digest = sha256_file(task.project_config)
    except OSError:
        raise TaskRefused("the project config this run was started with can no longer be read.") from None
    if digest != task.project_config_sha256:
        raise TaskRefused(
            "the project config changed after this task started. A run uses one "
            "config from start to end; start a new task (task-start) instead."
        )


# -- the plan draft ---------------------------------------------------------------


def build_plan_draft(task: TaskRecord) -> dict:
    """The L1 plan AIDO drafts from the human's task inputs. No model is involved.

    Every word of the plan except the title and the summary (the human's own
    description) is AIDO-fixed. ``required_verification`` is planner prose and
    never command authority: the verification that runs is the project's own
    ``controlled_verification``.
    """
    target = task.target_path
    plan = {
        "issue_number": task.issue_number,
        "repo": task.repo,
        "title": task.title,
        "summary": task.description.strip(),
        "scope_summary": f"Modify exactly one existing tracked file: {target}.",
        "non_goals": [
            f"No change to any file other than {target}.",
            "No new, deleted or renamed file.",
        ],
        "proposed_steps": [f"Change {target} as the summary describes."],
        "files_likely_to_change": [target],
        "files_forbidden_or_out_of_scope": [],
        "required_verification": [
            "The project's configured controlled verification (controlled_verification)."
        ],
        "risks": [],
        "open_questions": [],
        "automation_level": "L1",
        "requires_human_approval": True,
    }
    return {
        "approval": dict(EMPTY_APPROVAL),
        "plan_provenance": {
            "engine": "aido-task",
            "operation": "task-start",
            "real_call": False,
            "model": None,
            "endpoint_host": None,
            "generated_at": task.created_at,
            "project_id": task.project_id,
            "repo": task.repo,
            "issue_number": task.issue_number,
            "title": task.title,
        },
        "plan": plan,
        "project_id": task.project_id,
        "repo": task.repo,
        "issue_number": task.issue_number,
    }


def _freeze_approval(
    *, source_path: str, frozen_path: str, expected_draft: dict, label: str, parse
) -> bytes:
    """Check the human changed only ``approval``, strictly parse, then freeze.

    Returns the frozen bytes. The parse is the accepted parser's; this function
    decides nothing about whether an approval is valid.
    """
    data = _read_bytes(source_path, label)
    _check_only_approval_filled(data, expected_draft, label)
    parse(data.decode("utf-8"))
    create_exclusive(frozen_path, data)
    return data


def _check_only_approval_filled(data: bytes, expected_draft: dict, label: str) -> None:
    """The human changed nothing outside ``approval`` and typed every approval value."""
    document = _strict_json_object(data, label)
    if set(document) != set(expected_draft):
        raise TaskRefused(f"{label} has missing or unexpected top-level fields.")
    rest = {key: value for key, value in document.items() if key != "approval"}
    expected_rest = {key: value for key, value in expected_draft.items() if key != "approval"}
    if _canonical(rest) != _canonical(expected_rest):
        raise TaskRefused(
            f"{label} differs from the draft AIDO wrote outside its 'approval' "
            "block. Only the approval block may be edited. Nothing was recorded."
        )
    approval = document.get("approval")
    if not isinstance(approval, dict) or set(approval) != set(EMPTY_APPROVAL):
        raise TaskRefused(
            f"{label}: the approval block must hold exactly approved_by, "
            "approved_at, approval_text and source."
        )
    if any(type(approval[key]) is not str or not approval[key].strip() for key in EMPTY_APPROVAL):
        raise TaskRefused(
            f"{label}: the approval block is not filled in. A human must type "
            "every value. Nothing was recorded."
        )


def freeze_plan_approval(task: TaskRecord) -> str:
    """Freeze the human-approved plan. Returns the frozen path.

    With an interactive decision (``12-plan.decision.json``) the frozen bytes
    are serialized from it; otherwise they are the human's hand-edited bytes.
    An already-frozen file is re-checked either way.
    """
    frozen = task.path(PLAN_APPROVED_FILE)

    def parse(text: str) -> None:
        try:
            parse_approved_l1_plan_artifact(text)
        except ApprovedPlanError as exc:
            raise TaskRefused(f"the plan approval was refused by the accepted parser: {exc}") from None

    expected = build_plan_draft(task)
    if os.path.lexists(task.path(PLAN_DECISION_FILE)):
        from ai_dev_orchestrator.task import approve

        data = approve.approved_bytes(task, approve.plan_subject(task), now=utc_now())
        _check_only_approval_filled(data, expected, PLAN_APPROVED_FILE)
        parse(data.decode("utf-8"))
        approve.write_or_match(frozen, data)
        return frozen
    if os.path.lexists(frozen):
        data = _read_bytes(frozen, PLAN_APPROVED_FILE)
        _check_only_approval_filled(data, expected, PLAN_APPROVED_FILE)
        parse(data.decode("utf-8"))
        return frozen
    _freeze_approval(
        source_path=task.path(PLAN_DRAFT_FILE),
        frozen_path=frozen,
        expected_draft=expected,
        label=PLAN_DRAFT_FILE,
        parse=parse,
    )
    return frozen


# -- the implementer authorizations ---------------------------------------------------


def authorization_paths(task: TaskRecord, rnd: Round = ROUND_1) -> list[str]:
    """One round's authorization drafts, oldest first. Never another round's."""
    numbered = []
    for name in os.listdir(task.run_dir):
        match = rnd.authorization_re.match(name)
        if match:
            numbered.append((int(match.group(1)), os.path.join(task.run_dir, name)))
    return [path for _, path in sorted(numbered)]


def next_authorization_path(task: TaskRecord, rnd: Round = ROUND_1) -> str:
    return task.path(rnd.authorization_name.format(n=len(authorization_paths(task, rnd)) + 1))


def evidence_dir(task: TaskRecord) -> str:
    return task.path(EVIDENCE_DIR)


def authorization_run_id(path: str) -> str | None:
    """The P1B run id a draft names, or ``None`` if it cannot be read."""
    try:
        document = _strict_json_object(_read_bytes(path, "authorization"), "authorization")
    except TaskRefused:
        return None
    bound = document.get("bound")
    run_id = bound.get("run_id") if isinstance(bound, dict) else None
    if type(run_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", run_id):
        return None
    return run_id


def consumed_implementer_run(task: TaskRecord, rnd: Round = ROUND_1) -> str | None:
    """The P1B evidence directory of one round's consumed authorization, if any.

    Display only. Single use is decided by the P1B ledger, never by this.
    """
    found = consumed_authorization(task, rnd)
    return None if found is None else found[1]


def consumed_authorization(task: TaskRecord, rnd: Round = ROUND_1) -> tuple[str, str] | None:
    """``(consumed authorization path, evidence run dir)`` of one round's consumed run.

    The path is the file whose bytes P1B consumed: the hand-edited draft, or
    (D-2′) the ``.consented.json`` copy serialized from an interactive decision.
    """
    for path in authorization_paths(task, rnd):
        run_id = authorization_run_id(path)
        if run_id is None:
            continue
        candidate = os.path.join(evidence_dir(task), run_id)
        if os.path.isdir(candidate):
            consented = consented_path(path)
            return (consented if os.path.lexists(consented) else path), candidate
    return None


# -- the diff draft -----------------------------------------------------------------------


def read_implementer_diff_proposal(evidence_run_dir: str) -> dict:
    from ai_dev_orchestrator.supervised_implementer.live import DIFF_FILE

    path = os.path.join(evidence_run_dir, DIFF_FILE)
    return _strict_json_object(_read_bytes(path, "the implementer's diff proposal"), "diff-proposal.json")


def build_diff_draft(task: TaskRecord, proposal: dict) -> dict:
    """The approved-diff-proposal.v2 wrapper around the implementer's proposal."""
    from ai_dev_orchestrator.file_editing.models import (
        APPROVED_DIFF_PROPOSAL_MODE,
        APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
    )

    changes = proposal.get("changes")
    if (
        not isinstance(changes, list)
        or len(changes) != 1
        or not isinstance(changes[0], dict)
        or changes[0].get("path") != task.target_path
        or changes[0].get("change_type") != "modify"
        or proposal.get("omitted_paths")
    ):
        raise TaskRefused(
            "the implementer's diff proposal is not exactly one 'modify' of this "
            "task's target. Nothing was drafted."
        )
    return {
        "approval": dict(EMPTY_APPROVAL),
        "schema_version": APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": APPROVED_DIFF_PROPOSAL_MODE,
        "diff_proposal": proposal,
        "project_id": task.project_id,
        "repo": task.repo,
        "issue_number": task.issue_number,
        "title": task.title,
        "next_authorization_required": DIFF_NEXT_AUTHORIZATION,
    }


def write_diff_draft(task: TaskRecord, evidence_run_dir: str, rnd: Round = ROUND_1) -> None:
    """Write one round's diff text and diff draft, both exclusively."""
    proposal = read_implementer_diff_proposal(evidence_run_dir)
    draft = build_diff_draft(task, proposal)
    diff_text = proposal["changes"][0].get("unified_diff")
    if type(diff_text) is not str:
        raise TaskRefused("the implementer's diff proposal carries no unified diff.")
    expected_text = (diff_text + "\n").encode("utf-8")
    if not os.path.lexists(task.path(rnd.diff_text_file)):
        create_exclusive(task.path(rnd.diff_text_file), expected_text)
    elif rnd.number != 1 and _read_bytes(task.path(rnd.diff_text_file), rnd.diff_text_file) != expected_text:
        # An interrupted earlier attempt may have left the text; it must be THIS
        # round's diff, or the human would read one diff and approve another.
        raise TaskRefused(f"{rnd.diff_text_file} is not this round's proposed diff. Nothing was drafted.")
    create_exclusive(task.path(rnd.diff_draft_file), _json_bytes(draft))


def freeze_diff_approval(task: TaskRecord, evidence_run_dir: str, rnd: Round = ROUND_1) -> str:
    """Freeze one round's human-approved diff. Returns the frozen path.

    An already-frozen file is re-checked against THIS round's draft, so no
    other round's approval (or a copied file) can stand in for it.
    """
    from ai_dev_orchestrator.file_editing import (
        FileEditingApprovalError,
        parse_approved_diff_proposal_artifact,
    )

    def parse(text: str) -> None:
        try:
            parse_approved_diff_proposal_artifact(text)
        except FileEditingApprovalError as exc:
            raise TaskRefused(f"the diff approval was refused by the accepted parser: {exc}") from None

    frozen = task.path(rnd.diff_approved_file)
    expected = build_diff_draft(task, read_implementer_diff_proposal(evidence_run_dir))
    if os.path.lexists(task.path(rnd.diff_decision_file)):
        from ai_dev_orchestrator.task import approve

        data = approve.approved_bytes(task, approve.diff_subject(task, rnd, evidence_run_dir), now=utc_now())
        _check_only_approval_filled(data, expected, rnd.diff_approved_file)
        parse(data.decode("utf-8"))
        approve.write_or_match(frozen, data)
        return frozen
    if os.path.lexists(frozen):
        data = _read_bytes(frozen, rnd.diff_approved_file)
        _check_only_approval_filled(data, expected, rnd.diff_approved_file)
        parse(data.decode("utf-8"))
        return frozen

    _freeze_approval(
        source_path=task.path(rnd.diff_draft_file),
        frozen_path=frozen,
        expected_draft=expected,
        label=rnd.diff_draft_file,
        parse=parse,
    )
    return frozen


# -- step records ----------------------------------------------------------------------------


@dataclass(frozen=True)
class StepRecord:
    sequence: int
    step: str
    exit_code: int | None  # None: the command raised instead of exiting
    stdout_path: str
    stderr_path: str


def step_records(task: TaskRecord) -> list[StepRecord]:
    steps = task.path(STEPS_DIR)
    found: dict[tuple[int, str, str], dict[str, str]] = {}
    for name in os.listdir(steps):
        match = _STEP_RE.match(name)
        if match:
            key = (int(match.group(1)), match.group(2), match.group(3))
            found.setdefault(key, {})[match.group(4)] = os.path.join(steps, name)
    records = []
    for (sequence, step, code), streams in sorted(found.items()):
        if set(streams) != {"stdout", "stderr"}:
            continue
        records.append(
            StepRecord(
                sequence=sequence,
                step=step,
                exit_code=None if code == "error" else int(code),
                stdout_path=streams["stdout"],
                stderr_path=streams["stderr"],
            )
        )
    return records


def record_step(task: TaskRecord, step: str, exit_code: int | None, stdout: str, stderr: str) -> StepRecord:
    """Record one accepted command's exact output, exclusively."""
    sequence = 1 + max((record.sequence for record in step_records(task)), default=0)
    code = "error" if exit_code is None else str(exit_code)
    base = os.path.join(task.path(STEPS_DIR), f"{sequence:02d}-{step}.exit-{code}")
    out_bytes = stdout.encode("utf-8", "surrogatepass")
    err_bytes = stderr.encode("utf-8", "surrogatepass")
    create_exclusive(base + ".stdout", out_bytes)
    create_exclusive(base + ".stderr", err_bytes)
    if step in ROUND2_INTEGRITY_STEPS:
        # Written LAST: a crash before it leaves a round-2 record with no
        # integrity record, which terminal consumption refuses (fail closed).
        create_exclusive(
            base + INTEGRITY_SUFFIX,
            _json_bytes(
                {
                    "schema_version": STEP_INTEGRITY_SCHEMA_VERSION,
                    "step": step,
                    "sequence": sequence,
                    "exit_code": code,
                    "stdout_sha256": sha256_bytes(out_bytes),
                    "stdout_bytes": len(out_bytes),
                    "stderr_sha256": sha256_bytes(err_bytes),
                    "stderr_bytes": len(err_bytes),
                }
            ),
        )
    return StepRecord(sequence, step, exit_code, base + ".stdout", base + ".stderr")


def _begun_markers(task: TaskRecord, step: str) -> list[str]:
    prefix = f"{step}{BEGUN_INFIX}"
    return sorted(name for name in os.listdir(task.path(STEPS_DIR)) if name.startswith(prefix))


def begin_attempt(task: TaskRecord, step: str) -> None:
    """Durably record that a round-2 apply/review attempt is about to begin.

    Created exclusively and fsynced BEFORE the runner is invoked, so a crash
    anywhere afterwards (before any model request, mid-request, or before the
    step record is complete) still leaves proof that the attempt began. Raises
    on any failure, and the caller then invokes nothing.
    """
    if step not in ROUND2_INTEGRITY_STEPS:
        return
    ordinal = 1 + len(_begun_markers(task, step))
    create_exclusive(
        os.path.join(task.path(STEPS_DIR), f"{step}{BEGUN_INFIX}{ordinal:02d}"),
        _json_bytes({"schema_version": ATTEMPT_BEGUN_SCHEMA_VERSION, "step": step, "ordinal": ordinal}),
    )


def attempt_accounting_problem(task: TaskRecord) -> str | None:
    """Why round 2's begun attempts are not all accounted for by records, or None.

    Every begun attempt must have exactly one complete (stdout + stderr) step
    record, and no record may exist without a begun marker. Anything else means
    a runner may have run (and a reviewer may have been contacted) without a
    trustworthy outcome record; no further attempt may be authorized.
    """
    records = step_records(task)
    for step in ROUND2_INTEGRITY_STEPS:
        begun = len(_begun_markers(task, step))
        complete = sum(1 for record in records if record.step == step)
        if begun > complete:
            return (
                f"a {step} attempt began but has no complete step record "
                f"({begun} begun, {complete} recorded); AIDO cannot tell whether the "
                "runner, the workspace write or the reviewer model call happened."
            )
        if complete > begun:
            return f"{step} has {complete} step records but only {begun} begun-attempt markers."
    return None


def round2_attempt_exists(task: TaskRecord) -> bool:
    """True if ANY trace of a round-2 apply/review attempt exists.

    A begun marker or any step file (even a lone stdout/stderr) counts. This is
    deliberately broader than complete records: it decides whether the attempt
    gate applies, never whether an attempt succeeded.
    """
    for name in os.listdir(task.path(STEPS_DIR)):
        if any(name.startswith(f"{step}{BEGUN_INFIX}") for step in ROUND2_INTEGRITY_STEPS):
            return True
        match = _STEP_RE.match(name)
        if match and match.group(2) in ROUND2_INTEGRITY_STEPS:
            return True
    return False


def step_integrity_problem(record: StepRecord) -> str | None:
    """Why a round-2 step's bytes are not the ones AIDO recorded, or None.

    The integrity record sits in the same operator-controlled run directory as
    the bytes it covers. It detects partial recording and content edits that
    leave the record alone; it is NOT tamper-proof — whoever can rewrite the
    step files can rewrite this record too (no signature, no key, no ACL).
    """
    name = os.path.basename(record.stdout_path)
    path = record.stdout_path[: -len(".stdout")] + INTEGRITY_SUFFIX
    if not os.path.isfile(path):
        return f"{name} has no integrity record (an interrupted or incomplete recording)."
    try:
        doc = _strict_json_object(_read_bytes(path, "integrity record"), "integrity record")
        out_bytes = _read_bytes(record.stdout_path, name)
        err_bytes = _read_bytes(record.stderr_path, os.path.basename(record.stderr_path))
    except TaskRefused as exc:
        return str(exc)
    expected = {
        "schema_version": STEP_INTEGRITY_SCHEMA_VERSION,
        "step": record.step,
        "sequence": record.sequence,
        "exit_code": "error" if record.exit_code is None else str(record.exit_code),
        "stdout_sha256": sha256_bytes(out_bytes),
        "stdout_bytes": len(out_bytes),
        "stderr_sha256": sha256_bytes(err_bytes),
        "stderr_bytes": len(err_bytes),
    }
    if doc != expected:
        return f"{name} no longer matches the integrity record AIDO made when it recorded it."
    return None


def _last(task: TaskRecord, step: str) -> StepRecord | None:
    matching = [record for record in step_records(task) if record.step == step]
    return matching[-1] if matching else None


# -- the stage --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage:
    """Where a run stands. ``actions`` maps each accepted flag set to its action.

    ``round_number`` says which round's files and step names the actions use.
    """

    name: str
    terminal: bool
    message: str
    actions: dict[tuple[str, ...], str] = field(default_factory=dict)
    evidence_run_dir: str | None = None
    round_number: int = 1


# Action names the CLI dispatches on.
ACTION_PREPARE = "prepare"
ACTION_RUN_IMPLEMENTER = "run_implementer"
ACTION_WRITE_DIFF_DRAFT = "write_diff_draft"
ACTION_APPLY_AND_REVIEW = "apply_and_review"
ACTION_REVIEW = "review"
ACTION_BEGIN_CORRECTION = "begin_correction"
ACTION_DECLINE_CORRECTION = "decline_correction"


def _implementer_outcome(evidence_run_dir: str) -> dict | None:
    from ai_dev_orchestrator.supervised_implementer.live import OUTCOME_FILE

    path = os.path.join(evidence_run_dir, OUTCOME_FILE)
    if not os.path.isfile(path):
        return None
    try:
        return _strict_json_object(_read_bytes(path, "outcome.json"), "outcome.json")
    except TaskRefused:
        return None


@dataclass(frozen=True)
class _Reviewed:
    """One round whose review step ended with a reviewable result (exit 0 or 2)."""

    rnd: Round
    authorization_path: str
    evidence_run_dir: str
    apply_record: StepRecord
    review_record: StepRecord


def _stage(rnd: Round, name: str, terminal: bool, message: str, actions=None, evidence_run_dir=None) -> Stage:
    return Stage(
        rnd.stage_prefix + name, terminal, message, dict(actions or {}), evidence_run_dir, rnd.number
    )


def _review_pending(rnd: Round, review_record: StepRecord | None, run_dir: str, note: str = "") -> Stage:
    retry = (
        ""
        if review_record is None
        else f" The last review attempt exited {review_record.exit_code}; see "
        f"{os.path.basename(review_record.stderr_path)}. It may be run again."
    )
    return _stage(
        rnd,
        "review_pending",
        False,
        "The change is written. The next step runs the project's verification "
        "and, only if it passes, SENDS the diff to the reviewer model." + retry + note,
        {REVIEW_FLAGS: ACTION_REVIEW},
        run_dir,
    )


def _derive_round(task: TaskRecord, rnd: Round, consumed: tuple[str, str]) -> Stage | _Reviewed:
    """One round, from its consumed authorization to a finished review.

    Reads only that round's files and step records. Returns a :class:`Stage`
    for every point before a reviewable result, else a :class:`_Reviewed`.
    """
    authorization_path, run_dir = consumed
    final_round = rnd.number == 2
    restart = (
        " This was the one correction round; no further round exists."
        if final_round
        else " Start a new task to try again."
    )
    outcome = _implementer_outcome(run_dir)
    if outcome is None:
        return _stage(
            rnd,
            "implementer_evidence_incomplete",
            True,
            "The implementer authorization was consumed, but its outcome record is "
            "missing. Treat the source as sent. Inspect the implementer evidence. "
            + ("No further round exists." if final_round else "This task cannot continue; start a new task."),
            evidence_run_dir=run_dir,
        )
    state = outcome.get("state")
    if state == "no_change_proposed":
        return _stage(
            rnd,
            "no_change_proposed",
            True,
            "The implementer proposed no change. Nothing is left to approve or apply."
            + (" The workspace holds the restored original baseline." if final_round else ""),
            evidence_run_dir=run_dir,
        )
    if state != "diff_proposed":
        return _stage(
            rnd,
            "implementer_failed",
            True,
            f"The implementer run ended as {state!r} "
            f"({outcome.get('failure_category')!r}). The authorization is spent." + restart,
            evidence_run_dir=run_dir,
        )
    if final_round:
        # BEFORE any nonterminal stage: once a round-2 attempt has begun, no
        # missing or inconsistent preceding evidence may make another apply,
        # review, draft or approval action available again.
        unaccounted = attempt_accounting_problem(task)
        if unaccounted is None and round2_attempt_exists(task):
            missing = [
                name
                for name in (rnd.diff_draft_file, rnd.diff_approved_file)
                if not os.path.lexists(task.path(name))
            ]
            if missing:
                unaccounted = (
                    f"a round-2 apply/review attempt exists but {', '.join(missing)} is "
                    "missing, so what that attempt consumed can no longer be shown."
                )
        if unaccounted is not None:
            return _stage(
                rnd,
                "attempt_incomplete",
                True,
                f"{unaccounted[0].upper()}{unaccounted[1:]} Treat the change as possibly "
                "written and the diff as possibly sent to the reviewer. This was the one "
                "correction round: nothing more will run, and AIDO restores nothing. HUMAN "
                "REPOSITORY INSPECTION IS REQUIRED.",
                evidence_run_dir=run_dir,
            )

    if not os.path.lexists(task.path(rnd.diff_draft_file)):
        return _stage(
            rnd,
            "diff_draft_pending",
            False,
            "The implementer proposed a diff. The next step only writes the diff "
            "approval draft; it needs no flag.",
            {(): ACTION_WRITE_DIFF_DRAFT},
            run_dir,
        )
    if not os.path.lexists(task.path(rnd.diff_approved_file)):
        decided = _decided(task, rnd.diff_decision_file, "The diff decision")
        return _stage(
            rnd,
            "diff_approval",
            False,
            (
                decided
                or f"A human must read {rnd.diff_text_file} and, to approve it, fill in the "
                f"'approval' block of {rnd.diff_draft_file} (the exact file-edit "
                "approval_text), or decide interactively with task-approve. "
            )
            + "The next step WRITES the change into the workspace, "
            "runs the project's verification, and SENDS the diff to the reviewer model."
            + (
                " This diff is against the ORIGINAL baseline; round 1's approval "
                "does not carry over."
                if final_round
                else ""
            ),
            {APPLY_AND_REVIEW_FLAGS: ACTION_APPLY_AND_REVIEW},
            run_dir,
        )

    apply_record = _last(task, rnd.step_apply)
    if final_round and apply_record is not None and apply_record.exit_code == 1:
        broken = step_integrity_problem(apply_record)
        if broken is not None:
            return _stage(
                rnd,
                "evidence_inconsistent",
                True,
                f"The round-2 write record cannot be trusted: {broken} HUMAN INSPECTION IS "
                "REQUIRED. Nothing more will run.",
                evidence_run_dir=run_dir,
            )
    if apply_record is None or apply_record.exit_code == 1:
        retry ="" if apply_record is None else " The last write was refused before writing; fix what it named, then retry."
        return _stage(
            rnd,
            "apply_pending",
            False,
            "The diff is approved. The next step WRITES it, verifies, and reviews." + retry,
            {APPLY_AND_REVIEW_FLAGS: ACTION_APPLY_AND_REVIEW},
            run_dir,
        )
    if apply_record.exit_code != 0:
        return _stage(
            rnd,
            "write_needs_inspection",
            True,
            "The write ended in an indeterminate or unexpected state. HUMAN "
            "REPOSITORY INSPECTION IS REQUIRED. See "
            f"{os.path.basename(apply_record.stderr_path)}.",
            evidence_run_dir=run_dir,
        )

    review_record = _last(task, rnd.step_review)
    if final_round and review_record is not None and review_record.exit_code in (1, 4):
        # Round 2 is the last round: a completed reviewer invocation is never
        # repeated. No valid review exists; none is claimed.
        return _stage(
            rnd,
            "review_failed",
            True,
            f"The round-2 review step exited {review_record.exit_code} "
            f"({'refused' if review_record.exit_code == 1 else 'reviewer stage failed'}); see "
            f"{os.path.basename(review_record.stderr_path)}. NO valid round-2 review exists. "
            "This was the one correction round: AIDO will not run the reviewer again "
            "for it, and offers no retry or further round. The change is written and "
            "unreviewed. HUMAN INSPECTION IS REQUIRED. AIDO committed nothing.",
            evidence_run_dir=run_dir,
        )
    if review_record is None or review_record.exit_code in (1, 4):
        return _review_pending(rnd, review_record, run_dir)
    if review_record.exit_code == 3:
        return _stage(
            rnd,
            "workspace_untrusted",
            True,
            "Verification ran and the repository is no longer provably the "
            "approved state. HUMAN REPOSITORY INSPECTION IS REQUIRED.",
            evidence_run_dir=run_dir,
        )
    if review_record.exit_code not in (0, 2):
        return _stage(
            rnd,
            "review_needs_inspection",
            True,
            "The review step ended unexpectedly. See "
            f"{os.path.basename(review_record.stderr_path)}.",
            evidence_run_dir=run_dir,
        )
    return _Reviewed(rnd, authorization_path, run_dir, apply_record, review_record)


_AWAITING_DECISION = (
    f"AIDO is done. Read {SUMMARY_FILE} and the review packet, then decide. "
    "AIDO committed nothing and pushed nothing; if you accept the change, "
    "commit it yourself."
)


def _inconsistent(message: str, run_dir: str | None = None) -> Stage:
    return Stage(
        "correction_records_inconsistent",
        True,
        message + " HUMAN INSPECTION OF THE RUN DIRECTORY IS REQUIRED. Nothing more will run.",
        evidence_run_dir=run_dir,
    )


def _round2_files_exist(task: TaskRecord) -> bool:
    # Any round-2 authorization-named file counts, not only drafts: a round-2
    # decision or consent whose draft is gone is still a round-2 record.
    prefix = ROUND_2.authorization_name.split("{n}")[0]
    if any(name.startswith(prefix) for name in os.listdir(task.run_dir)):
        return True
    return round2_attempt_exists(task) or any(
        record.step.endswith("-r2") for record in step_records(task)
    ) or any(
        os.path.lexists(task.path(name))
        for name in (
            ROUND_2.diff_text_file,
            ROUND_2.diff_draft_file,
            ROUND_2.diff_approved_file,
            ROUND_2.diff_decision_file,
            ROUND_2.summary_file,
        )
    )


def _decided(task: TaskRecord, name: str, what: str) -> str | None:
    """A stage-message prefix when an interactive decision is already recorded."""
    if os.path.lexists(task.path(name)):
        return (
            f"{what} is recorded in {name} (task-approve). It runs nothing by itself; "
            "the next step validates it again first. "
        )
    return None


def derive_stage(task: TaskRecord) -> Stage:
    """Derive the run's stage from its files. Reads only the run directory."""
    from ai_dev_orchestrator.task import approve

    rejected = approve.rejection_stage(task, ROUND_1)
    if rejected is not None:
        return rejected
    if not os.path.lexists(task.path(PLAN_APPROVED_FILE)):
        decided = _decided(task, PLAN_DECISION_FILE, "The plan decision")
        return Stage(
            "plan_approval",
            False,
            (decided + "The next step prepares the implementer authorization; it is offline and sends nothing.")
            if decided
            else f"A human must approve the plan: fill in the 'approval' block of {PLAN_DRAFT_FILE} "
            "(approved_by, approved_at as ISO-8601 with offset, the exact approval_text, "
            "source \"manual\"), or decide interactively with task-approve. The next step "
            "then prepares the implementer authorization; it is offline and sends nothing.",
            {PREPARE_FLAGS: ACTION_PREPARE},
        )

    begun = os.path.lexists(task.path(CORRECTION_FILE))
    declined = os.path.lexists(task.path(CORRECTION_DECLINED_FILE))
    consumed = consumed_authorization(task, ROUND_1)
    if consumed is None:
        if begun or declined or _round2_files_exist(task):
            return _inconsistent("Correction-round records exist, but round 1 never ran.")
        if not authorization_paths(task):
            return Stage(
                "prepare_pending",
                False,
                "The plan is approved. The next step prepares the implementer "
                "authorization; it is offline and sends nothing.",
                {PREPARE_FLAGS: ACTION_PREPARE},
            )
        latest = os.path.basename(authorization_paths(task)[-1])
        decided = _decided(task, os.path.basename(consent_decision_path(latest)), "The consent decision")
        return Stage(
            "implementer_consent",
            False,
            (
                decided
                or f"A human must complete the 'consent' block of {latest} (it expires 60 "
                "minutes after it was prepared), or decide interactively with task-approve. "
            )
            + "The next step SENDS the one approved "
            "file to the supervised implementer model, once. To start over with a "
            "fresh authorization instead, pass --prepare-supervised-implementation.",
            {IMPLEMENTER_FLAGS: ACTION_RUN_IMPLEMENTER, PREPARE_FLAGS: ACTION_PREPARE},
        )

    first = _derive_round(task, ROUND_1, consumed)
    if isinstance(first, Stage):
        if begun or declined or _round2_files_exist(task):
            return _inconsistent(
                "Correction-round records exist, but round 1 has no reviewable result.",
                first.evidence_run_dir,
            )
        return first

    from ai_dev_orchestrator.task import correction as corr

    if begun and declined:
        return _inconsistent("The correction round was both begun and declined.", first.evidence_run_dir)
    if declined:
        if _round2_files_exist(task):
            return _inconsistent("The correction round was declined, but round-2 records exist.")
        try:
            corr.check_declined_record(task)
        except TaskRefused as exc:
            return _inconsistent(str(exc), first.evidence_run_dir)
        decided = (
            _AWAITING_DECISION
            if first.review_record.exit_code == 0
            else "Verification did not pass; read the review step's record "
            f"({os.path.basename(first.review_record.stdout_path)}), then decide. "
            "AIDO committed nothing and pushed nothing."
        )
        return Stage(
            "awaiting_human_decision",
            True,
            "You declined the correction round. " + decided,
            evidence_run_dir=first.evidence_run_dir,
        )
    if begun:
        rejected = approve.rejection_stage(task, ROUND_2)
        if rejected is not None:
            if round2_attempt_exists(task) and approve.authorization_records_problem(task, ROUND_2) is not None:
                # Both are terminal. Once a round-2 apply/review attempt has
                # begun, its own stage says more: the change may be written and
                # the diff may be sent (ALPHA-2B-T1-FU2).
                attempt = _derive_correction(task, first)
                if attempt.name == "round2_attempt_incomplete":
                    return attempt
            return rejected
        return _derive_correction(task, first)
    if _round2_files_exist(task):
        return _inconsistent("Round-2 records exist, but no correction round was begun.")

    evidence, why_not = corr.correction_eligibility(task, first)
    offer = (
        "A ONE-TIME correction round is available. To take it, pass "
        "--begin-correction-round: AIDO records your decision and tells you how to "
        "restore the target yourself; it sends, writes and approves nothing. Round "
        "2 then needs a fresh implementer consent and its own exact-diff approval, "
        "and it is the last round. To end the task at your own decision instead, "
        "pass --decline-correction."
    )
    if first.review_record.exit_code == 2:
        if evidence is None:
            return _review_pending(
                ROUND_1,
                first.review_record,
                first.evidence_run_dir,
                f" No correction round is offered: {why_not}",
            )
        return Stage(
            "correction_offered",
            False,
            "Verification ran and did not pass; the workspace is still provably the "
            "approved state. The review may be run again with "
            "--verify-approved-file-edit --real-reviewer. " + offer,
            {
                REVIEW_FLAGS: ACTION_REVIEW,
                BEGIN_CORRECTION_FLAGS: ACTION_BEGIN_CORRECTION,
                DECLINE_CORRECTION_FLAGS: ACTION_DECLINE_CORRECTION,
            },
            first.evidence_run_dir,
        )
    if evidence is None:
        return Stage(
            "awaiting_human_decision",
            True,
            _AWAITING_DECISION + f" No correction round is offered: {why_not}",
            evidence_run_dir=first.evidence_run_dir,
        )
    return Stage(
        "correction_offered",
        False,
        f"The reviewer requested changes (a model claim; read {SUMMARY_FILE}). " + offer,
        {
            BEGIN_CORRECTION_FLAGS: ACTION_BEGIN_CORRECTION,
            DECLINE_CORRECTION_FLAGS: ACTION_DECLINE_CORRECTION,
        },
        first.evidence_run_dir,
    )


def _derive_correction(task: TaskRecord, first: _Reviewed) -> Stage:
    """Round 2. Every step re-checks round 1's pinned evidence first."""
    from ai_dev_orchestrator.task import correction as corr

    try:
        evidence = corr.checked_correction_evidence(task, first)
    except TaskRefused as exc:
        return Stage(
            "round2_correction_evidence_mismatch",
            True,
            f"Round 2 cannot use round 1's evidence: {exc} HUMAN INSPECTION IS REQUIRED.",
            evidence_run_dir=first.evidence_run_dir,
            round_number=2,
        )
    first_bound = evidence.round1_bound
    consumed = consumed_authorization(task, ROUND_2)
    if consumed is None and round2_attempt_exists(task):
        # An attempt already began, so losing its consumed authorization or
        # evidence directory must never reopen restore/prepare/consent.
        return Stage(
            "round2_attempt_incomplete",
            True,
            "A round-2 apply/review attempt exists, but its consumed authorization or "
            "implementer evidence is missing, so what it consumed can no longer be shown. "
            "Treat the change as possibly written and the diff as possibly sent to the "
            "reviewer. This was the one correction round: nothing more will run, and AIDO "
            "restores nothing. HUMAN REPOSITORY INSPECTION IS REQUIRED.",
            round_number=2,
        )
    if consumed is None:
        drafts = authorization_paths(task, ROUND_2)
        if not drafts:
            return Stage(
                "round2_restore_pending",
                False,
                f"The correction round is begun. YOU must restore {task.target_path} to its "
                f"original baseline first: {corr.restore_instruction(task)} "
                f"WARNING: {corr.RESTORE_WARNING} AIDO never restores it. Then pass "
                "--prepare-supervised-implementation: AIDO observes the clean tree, the "
                "round-1 HEAD and the round-1 source bytes itself and refuses any "
                "difference. Preparing is offline and sends nothing.",
                {PREPARE_FLAGS: ACTION_PREPARE},
                round_number=2,
            )
        problem = corr.round2_binding_problem(drafts[-1], first_bound)
        if problem is not None:
            return Stage(
                "round2_correction_baseline_mismatch",
                True,
                f"{problem} No consent is offered and nothing will be sent.",
                round_number=2,
            )
        latest = os.path.basename(drafts[-1])
        decided = _decided(task, os.path.basename(consent_decision_path(latest)), "The round-2 consent decision")
        return Stage(
            "round2_implementer_consent",
            False,
            (
                decided
                or f"A human must complete the 'consent' block of {latest}, a FRESH single-use "
                "authorization (it expires 60 minutes after it was prepared; round 1's is "
                "spent and never reused), or decide interactively with task-approve. "
            )
            + "The next step SENDS the original file plus the "
            "correction data (the previous approved diff, AIDO-observed verification "
            "facts and any reviewer findings, as untrusted data) to the supervised "
            "implementer model, once. To issue another fresh authorization instead, "
            "pass --prepare-supervised-implementation.",
            {IMPLEMENTER_FLAGS: ACTION_RUN_IMPLEMENTER, PREPARE_FLAGS: ACTION_PREPARE},
            round_number=2,
        )
    authorization_path, run_dir = consumed
    problem = corr.round2_consumed_problem(authorization_path, run_dir, first_bound)
    if problem is not None:
        return Stage(
            "round2_evidence_inconsistent",
            True,
            f"{problem} HUMAN INSPECTION IS REQUIRED. Nothing more will run.",
            evidence_run_dir=run_dir,
            round_number=2,
        )
    second = _derive_round(task, ROUND_2, consumed)
    if isinstance(second, Stage):
        return second
    problem = corr.round2_terminal_problem(
        task, run_dir, first_bound, second.apply_record, second.review_record
    )
    if problem is not None:
        return Stage(
            "round2_evidence_inconsistent",
            True,
            f"The round-2 terminal records are not trustworthy: {problem} HUMAN "
            "INSPECTION IS REQUIRED. No result is claimed. Nothing more will run.",
            evidence_run_dir=run_dir,
            round_number=2,
        )
    if second.review_record.exit_code == 2:
        return Stage(
            "round2_verification_failed",
            True,
            f"Round-2 verification ran and did not pass. Read {ROUND_2.summary_file}. "
            "This was the one correction round; AIDO offers no further round and no "
            "retry. The decision is yours: AIDO committed nothing.",
            evidence_run_dir=run_dir,
            round_number=2,
        )
    return Stage(
        "round2_awaiting_human_decision",
        True,
        f"AIDO is done. Read {ROUND_2.summary_file} and the round-2 review packet, then "
        "decide. This was the one correction round; whatever the verdict, AIDO offers "
        "no further round. AIDO committed nothing and pushed nothing; if you accept "
        "the change, commit it yourself.",
        evidence_run_dir=run_dir,
        round_number=2,
    )


def round2_context(task: TaskRecord):
    """``(evidence, round-1 reviewed)`` for a begun correction, re-checked. For the CLI."""
    from ai_dev_orchestrator.task import correction as corr

    consumed = consumed_authorization(task, ROUND_1)
    if consumed is None:
        raise TaskRefused("round 1 never ran.")
    first = _derive_round(task, ROUND_1, consumed)
    if not isinstance(first, _Reviewed):
        raise TaskRefused("round 1 has no reviewable result.")
    return corr.checked_correction_evidence(task, first), first


def round1_reviewed(task: TaskRecord) -> _Reviewed:
    consumed = consumed_authorization(task, ROUND_1)
    first = None if consumed is None else _derive_round(task, ROUND_1, consumed)
    if not isinstance(first, _Reviewed):
        raise TaskRefused("round 1 has no reviewable result.")
    return first


# -- the derived summary ---------------------------------------------------------------------------


def _readiness(verification_outcome: str, verdict: str) -> str:
    if verification_outcome != "verified":
        return "NOT READY: verification did not pass."
    return {
        "approve": "READY FOR YOUR DECISION: verification passed and the reviewer returned 'approve'.",
        "changes_requested": "NOT RECOMMENDED AS IS: the reviewer requested changes.",
        "needs_human_review": "NEEDS YOUR REVIEW: the reviewer asked for human review.",
    }.get(verdict, "UNKNOWN VERDICT.")


def render_summary(task: TaskRecord, apply_record: StepRecord, review_record: StepRecord) -> str:
    """A derived, human-readable summary. It is NOT evidence and says so."""
    from ai_dev_orchestrator.review import ReviewPacket

    packet_text = _read_bytes(review_record.stdout_path, "the review packet").decode("utf-8")
    packet = ReviewPacket.model_validate_json(packet_text)
    write_report = _strict_json_object(_read_bytes(apply_record.stdout_path, "the write report"), "write report")
    target = write_report.get("target") if isinstance(write_report.get("target"), dict) else {}
    verification = packet.verification
    review = packet.review
    reviewer = packet.reviewer

    lines = [
        "AIDO TASK SUMMARY",
        "Derived by AIDO from the records in this run directory. It is NOT itself",
        "evidence: the authoritative records are the files it names.",
        "",
        f"Task:    {task.title} (issue {task.issue_number})",
        f"Project: {task.project_id} ({task.repo})",
        f"Target:  {task.target_path}",
        f"Diff:    {DIFF_TEXT_FILE}",
        "",
        "AIDO-observed facts",
        f"  write:        {write_report.get('outcome')!r}, "
        f"{target.get('pre_image_bytes')} -> {target.get('post_image_bytes')} bytes "
        f"[{os.path.basename(apply_record.stdout_path)}]",
        f"  verification: {verification.outcome!r}, return code "
        f"{verification.execution.return_code}, passed {verification.execution.passed} "
        "(embedded in the review packet)",
        f"  reviewer:     {reviewer.provider} / {reviewer.model} at {reviewer.endpoint_host} "
        f"({'TLS' if reviewer.transport_tls else 'NOT TLS-ENCRYPTED'}), "
        f"{reviewer.semantic_requests} of at most {reviewer.max_semantic_requests} semantic requests",
        "",
        "Reviewer model claims (NOT verified by AIDO)",
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
        "AIDO readiness (a fixed mapping of the two lines above, not a judgment)",
        f"  {_readiness(verification.outcome, review.verdict)}",
        "",
        "Records",
        f"  review packet, exactly as emitted: {os.path.basename(review_record.stdout_path)}",
        f"  write report, exactly as emitted:  {os.path.basename(apply_record.stdout_path)}",
        f"  implementer evidence:              {EVIDENCE_DIR}{os.sep}",
        "  The raw reviewer model response is not retained (5F2E design).",
        "",
        "Next: your decision. AIDO created no branch, commit, push or PR. If you",
        "accept the change, commit it yourself. If not, revert it with your own",
        "Git workflow.",
    ]
    return "\n".join(lines) + "\n"


def write_summary(task: TaskRecord) -> str | None:
    """Write ``summary.txt`` once for a reviewed run. Returns its text, or None."""
    apply_record = _last(task, "apply")
    review_record = _last(task, "review")
    if apply_record is None or review_record is None or review_record.exit_code != 0:
        return None
    text = render_summary(task, apply_record, review_record)
    if not os.path.lexists(task.path(SUMMARY_FILE)):
        create_exclusive(task.path(SUMMARY_FILE), text.encode("utf-8"))
    return text
