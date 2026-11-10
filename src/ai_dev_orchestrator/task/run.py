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

**The stage is derived, every time, from these files.** There is no state
machine store and no caller-supplied stage. A file's presence says which step
ran; the accepted commands' own records say how it ended.

**Nothing here creates an approval or a consent.** Drafts carry empty approval
stubs; a human types every value. Freezing only checks that the human changed
nothing outside the approval block, then copies their bytes; the accepted
strict parser decides whether the approval is valid. Nothing here reads an
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
EVIDENCE_DIR = "implementer-evidence"
DIFF_TEXT_FILE = "30-proposed.diff"
DIFF_DRAFT_FILE = "30-diff.draft.json"
DIFF_APPROVED_FILE = "31-diff.approved.json"
STEPS_DIR = "steps"
SUMMARY_FILE = "summary.txt"

_AUTHORIZATION_RE = re.compile(r"^20-authorization-([1-9][0-9]*)\.json$")
_STEP_RE = re.compile(
    r"^([0-9]{2,})-(prepare|implementer-run|apply|review)\.exit-([0-9]+|error)\.(stdout|stderr)$"
)

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
ALL_FLAGS = PREPARE_FLAGS + IMPLEMENTER_FLAGS + APPLY_AND_REVIEW_FLAGS

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
    parse(data.decode("utf-8"))
    create_exclusive(frozen_path, data)
    return data


def freeze_plan_approval(task: TaskRecord) -> str:
    """Freeze the human-approved plan. Returns the frozen path."""
    frozen = task.path(PLAN_APPROVED_FILE)
    if os.path.lexists(frozen):
        return frozen

    def parse(text: str) -> None:
        try:
            parse_approved_l1_plan_artifact(text)
        except ApprovedPlanError as exc:
            raise TaskRefused(f"the plan approval was refused by the accepted parser: {exc}") from None

    _freeze_approval(
        source_path=task.path(PLAN_DRAFT_FILE),
        frozen_path=frozen,
        expected_draft=build_plan_draft(task),
        label=PLAN_DRAFT_FILE,
        parse=parse,
    )
    return frozen


# -- the implementer authorizations ---------------------------------------------------


def authorization_paths(task: TaskRecord) -> list[str]:
    """The run's authorization drafts, oldest first."""
    numbered = []
    for name in os.listdir(task.run_dir):
        match = _AUTHORIZATION_RE.match(name)
        if match:
            numbered.append((int(match.group(1)), os.path.join(task.run_dir, name)))
    return [path for _, path in sorted(numbered)]


def next_authorization_path(task: TaskRecord) -> str:
    return task.path(f"20-authorization-{len(authorization_paths(task)) + 1}.json")


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


def consumed_implementer_run(task: TaskRecord) -> str | None:
    """The P1B evidence directory of a consumed authorization, if any.

    Display only. Single use is decided by the P1B ledger, never by this.
    """
    for path in authorization_paths(task):
        run_id = authorization_run_id(path)
        if run_id is None:
            continue
        candidate = os.path.join(evidence_dir(task), run_id)
        if os.path.isdir(candidate):
            return candidate
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


def write_diff_draft(task: TaskRecord, evidence_run_dir: str) -> None:
    """Write ``30-proposed.diff`` and ``30-diff.draft.json``, both exclusively."""
    proposal = read_implementer_diff_proposal(evidence_run_dir)
    draft = build_diff_draft(task, proposal)
    diff_text = proposal["changes"][0].get("unified_diff")
    if type(diff_text) is not str:
        raise TaskRefused("the implementer's diff proposal carries no unified diff.")
    if not os.path.lexists(task.path(DIFF_TEXT_FILE)):
        create_exclusive(task.path(DIFF_TEXT_FILE), (diff_text + "\n").encode("utf-8"))
    create_exclusive(task.path(DIFF_DRAFT_FILE), _json_bytes(draft))


def freeze_diff_approval(task: TaskRecord, evidence_run_dir: str) -> str:
    """Freeze the human-approved diff. Returns the frozen path."""
    from ai_dev_orchestrator.file_editing import (
        FileEditingApprovalError,
        parse_approved_diff_proposal_artifact,
    )

    frozen = task.path(DIFF_APPROVED_FILE)
    if os.path.lexists(frozen):
        return frozen

    def parse(text: str) -> None:
        try:
            parse_approved_diff_proposal_artifact(text)
        except FileEditingApprovalError as exc:
            raise TaskRefused(f"the diff approval was refused by the accepted parser: {exc}") from None

    _freeze_approval(
        source_path=task.path(DIFF_DRAFT_FILE),
        frozen_path=frozen,
        expected_draft=build_diff_draft(task, read_implementer_diff_proposal(evidence_run_dir)),
        label=DIFF_DRAFT_FILE,
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
    create_exclusive(base + ".stdout", stdout.encode("utf-8", "surrogatepass"))
    create_exclusive(base + ".stderr", stderr.encode("utf-8", "surrogatepass"))
    return StepRecord(sequence, step, exit_code, base + ".stdout", base + ".stderr")


def _last(task: TaskRecord, step: str) -> StepRecord | None:
    matching = [record for record in step_records(task) if record.step == step]
    return matching[-1] if matching else None


# -- the stage --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage:
    """Where a run stands. ``actions`` maps each accepted flag set to its action."""

    name: str
    terminal: bool
    message: str
    actions: dict[tuple[str, ...], str] = field(default_factory=dict)
    evidence_run_dir: str | None = None


# Action names the CLI dispatches on.
ACTION_PREPARE = "prepare"
ACTION_RUN_IMPLEMENTER = "run_implementer"
ACTION_WRITE_DIFF_DRAFT = "write_diff_draft"
ACTION_APPLY_AND_REVIEW = "apply_and_review"
ACTION_REVIEW = "review"


def _implementer_outcome(evidence_run_dir: str) -> dict | None:
    from ai_dev_orchestrator.supervised_implementer.live import OUTCOME_FILE

    path = os.path.join(evidence_run_dir, OUTCOME_FILE)
    if not os.path.isfile(path):
        return None
    try:
        return _strict_json_object(_read_bytes(path, "outcome.json"), "outcome.json")
    except TaskRefused:
        return None


def derive_stage(task: TaskRecord) -> Stage:
    """Derive the run's stage from its files. Reads only the run directory."""
    if not os.path.lexists(task.path(PLAN_APPROVED_FILE)):
        return Stage(
            "plan_approval",
            False,
            f"A human must approve the plan: fill in the 'approval' block of {PLAN_DRAFT_FILE} "
            "(approved_by, approved_at as ISO-8601 with offset, the exact approval_text, "
            "source \"manual\"). The next step then prepares the implementer authorization; "
            "it is offline and sends nothing.",
            {PREPARE_FLAGS: ACTION_PREPARE},
        )

    consumed = consumed_implementer_run(task)
    if consumed is None:
        if not authorization_paths(task):
            return Stage(
                "prepare_pending",
                False,
                "The plan is approved. The next step prepares the implementer "
                "authorization; it is offline and sends nothing.",
                {PREPARE_FLAGS: ACTION_PREPARE},
            )
        latest = os.path.basename(authorization_paths(task)[-1])
        return Stage(
            "implementer_consent",
            False,
            f"A human must complete the 'consent' block of {latest} (it expires 60 "
            "minutes after it was prepared). The next step SENDS the one approved "
            "file to the supervised implementer model, once. To start over with a "
            "fresh authorization instead, pass --prepare-supervised-implementation.",
            {IMPLEMENTER_FLAGS: ACTION_RUN_IMPLEMENTER, PREPARE_FLAGS: ACTION_PREPARE},
        )

    outcome = _implementer_outcome(consumed)
    if outcome is None:
        return Stage(
            "implementer_evidence_incomplete",
            True,
            "The implementer authorization was consumed, but its outcome record is "
            "missing. Treat the source as sent. Inspect the implementer evidence. "
            "This task cannot continue; start a new task.",
            evidence_run_dir=consumed,
        )
    state = outcome.get("state")
    if state == "no_change_proposed":
        return Stage(
            "no_change_proposed",
            True,
            "The implementer proposed no change. Nothing is left to approve or apply.",
            evidence_run_dir=consumed,
        )
    if state != "diff_proposed":
        return Stage(
            "implementer_failed",
            True,
            f"The implementer run ended as {state!r} "
            f"({outcome.get('failure_category')!r}). The authorization is spent. "
            "Start a new task to try again.",
            evidence_run_dir=consumed,
        )
    if not os.path.lexists(task.path(DIFF_DRAFT_FILE)):
        return Stage(
            "diff_draft_pending",
            False,
            "The implementer proposed a diff. The next step only writes the diff "
            "approval draft; it needs no flag.",
            {(): ACTION_WRITE_DIFF_DRAFT},
            evidence_run_dir=consumed,
        )
    if not os.path.lexists(task.path(DIFF_APPROVED_FILE)):
        return Stage(
            "diff_approval",
            False,
            f"A human must read {DIFF_TEXT_FILE} and, to approve it, fill in the "
            f"'approval' block of {DIFF_DRAFT_FILE} (the exact file-edit "
            "approval_text). The next step WRITES the change into the workspace, "
            "runs the project's verification, and SENDS the diff to the reviewer model.",
            {APPLY_AND_REVIEW_FLAGS: ACTION_APPLY_AND_REVIEW},
            evidence_run_dir=consumed,
        )

    apply_record = _last(task, "apply")
    if apply_record is None or apply_record.exit_code == 1:
        retry = "" if apply_record is None else " The last write was refused before writing; fix what it named, then retry."
        return Stage(
            "apply_pending",
            False,
            "The diff is approved. The next step WRITES it, verifies, and reviews." + retry,
            {APPLY_AND_REVIEW_FLAGS: ACTION_APPLY_AND_REVIEW},
            evidence_run_dir=consumed,
        )
    if apply_record.exit_code != 0:
        return Stage(
            "write_needs_inspection",
            True,
            "The write ended in an indeterminate or unexpected state. HUMAN "
            "REPOSITORY INSPECTION IS REQUIRED. See "
            f"{os.path.basename(apply_record.stderr_path)}.",
            evidence_run_dir=consumed,
        )

    review_record = _last(task, "review")
    if review_record is None or review_record.exit_code in (1, 2, 4):
        retry = (
            ""
            if review_record is None
            else f" The last review attempt exited {review_record.exit_code}; see "
            f"{os.path.basename(review_record.stderr_path)}. It may be run again."
        )
        return Stage(
            "review_pending",
            False,
            "The change is written. The next step runs the project's verification "
            "and, only if it passes, SENDS the diff to the reviewer model." + retry,
            {REVIEW_FLAGS: ACTION_REVIEW},
            evidence_run_dir=consumed,
        )
    if review_record.exit_code == 3:
        return Stage(
            "workspace_untrusted",
            True,
            "Verification ran and the repository is no longer provably the "
            "approved state. HUMAN REPOSITORY INSPECTION IS REQUIRED.",
            evidence_run_dir=consumed,
        )
    if review_record.exit_code != 0:
        return Stage(
            "review_needs_inspection",
            True,
            "The review step ended unexpectedly. See "
            f"{os.path.basename(review_record.stderr_path)}.",
            evidence_run_dir=consumed,
        )
    return Stage(
        "awaiting_human_decision",
        True,
        f"AIDO is done. Read {SUMMARY_FILE} and the review packet, then decide. "
        "AIDO committed nothing and pushed nothing; if you accept the change, "
        "commit it yourself.",
        evidence_run_dir=consumed,
    )


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
