"""Interactive human decisions for the task coordinator (P0-UX1, D-2′).

``task-approve`` lets a human decide H1 (the plan), H2 (the implementer
consent) and H3 (the exact diff), and their round-2 equivalents, on the local
terminal instead of by editing JSON. Each decision is about ONE exact
presented artifact:

```text
12-plan.decision.json                  H1
20-authorization-<n>.decision.json     H2 (round 2: 50-authorization-<n>.decision.json)
20-authorization-<n>.consented.json    H2, the serialized consent (task-continue writes it)
32-diff.decision.json                  H3 (round 2: 62-diff.decision.json)
```

**What AIDO generates, and when.** Only after the human typed ``approve`` (and,
for H2, typed the endpoint they expect and confirmed transmission), AIDO
records a write-once decision. The decision is bound to the run, the project
config, the round, the stage and the exact draft bytes that were displayed. The
approval or consent block the accepted strict parser requires is serialized
from that record, with the stage's fixed phrase, AIDO's clock and the observed
local account name, only inside the stage's own ``task-continue`` invocation,
after the record is re-validated. ``reject`` is recorded the same way and ends
the task (or the correction round). A cancel records nothing.

**Single-approval H2 (P0-UX-H2-SIMPLE).** When the run's pinned project config
pins ``supervised_implementer.endpoint``, H2 is one informed decision instead:
AIDO checks the environment's base URL against the pinned destination by P1B's
rules, shows the complete destination (scheme, host, explicit port, base path),
its TLS state with a ``NOT TLS-ENCRYPTED`` banner for http, and everything the
one request carries, and the human types ``approve`` (or ``reject``) once. The
record says so (``confirmation: "single_approval"``) and holds the exact screen
shown; it claims no separately typed ``transmit`` or ``plaintext``. The mode is
the pinned config's, never the record's, so an existing run keeps its typed
contract.

**What this module never does.** It sends nothing, calls no model, runs no
process, writes nothing to the workspace and runs no verification. The only
environment value it reads is the implementer's base URL, for H2, to compare
it with the endpoint the human typed using P1B's own endpoint rules; it never
reads a key and never displays the URL. What each decision leads to (the
configured workspace, the verification command, the reviewer's configured
identity and destination) is displayed from the run's pinned project config,
which grants nothing by being shown. The account name is an observation,
not an authenticated identity, and a TTY check is not proof that a human is
present (A-19): the human remains the trust root, as with a file edit.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr, ValidationError

from ai_dev_orchestrator.task import run as task_run
from ai_dev_orchestrator.task.run import (
    PLAN_APPROVED_FILE,
    PLAN_DECISION_FILE,
    PLAN_DRAFT_FILE,
    ROUND_1,
    Round,
    Stage,
    TaskRecord,
    TaskRefused,
    _canonical,
    _json_bytes,
    _read_bytes,
    _strict_json_object,
    consent_decision_path,
    consented_path,
    sha256_bytes,
)

DECISION_SCHEMA_VERSION = "aido-task-decision.v1"
INTERFACE = "terminal"

KIND_PLAN = "plan_approval"
KIND_CONSENT = "implementer_consent"
KIND_DIFF = "diff_approval"

APPROVE = "approve"
REJECT = "reject"
TRANSMIT_WORD = "transmit"
PLAINTEXT_WORD = "plaintext"

#: How far a decision's ``recorded_at`` may sit in the future of AIDO's clock.
CLOCK_SKEW = timedelta(minutes=5)
MAX_ACCOUNT_CHARS = 200

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_AUTHORITY = re.compile(r"^(http|https)://([^/\s@?#\\]+):([0-9]{1,5})$")

#: Characters a terminal could use to hide, reorder or overwrite text. Shown as
#: visible escapes; ``\n`` and ``\t`` are kept.
_ZERO_WIDTH_AND_SEPARATORS = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x2028, 0x2029}
_BIDI = {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


class Cancelled(Exception):
    """The human cancelled. Nothing was recorded."""


# -- the decision record ---------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Presented(_Strict):
    file: StrictStr
    sha256: StrictStr
    size: StrictInt


class PlanBinding(_Strict):
    target_path: StrictStr


class ConsentBinding(_Strict):
    authorization_file: StrictStr
    p1b_run_id: StrictStr
    binding_sha256: StrictStr
    request_sha256: StrictStr
    prepared_at: StrictStr
    expires_at: StrictStr
    provider: StrictStr
    model: StrictStr
    target_path: StrictStr
    source_sha256: StrictStr
    source_bytes: StrictInt
    endpoint_scheme: Literal["http", "https"] | None
    endpoint_host: StrictStr | None
    endpoint_port: StrictInt | None
    endpoint_matched_environment: StrictBool
    transmission_confirmed: StrictBool
    plaintext_confirmed: StrictBool


class SingleApprovalConsentBinding(_Strict):
    """P0-UX-H2-SIMPLE: an H2 decided by ONE typed answer on a full disclosure.

    Used only when the run's pinned project config pins
    ``supervised_implementer.endpoint``. The destination fields come from that
    config, never from the human or the environment; the record says how the
    decision was made (``confirmation``), that the environment matched before
    it was recorded, and exactly what screen the human was shown. It records
    no ``transmit`` or ``plaintext`` answer, because none was typed.
    """

    authorization_file: StrictStr
    p1b_run_id: StrictStr
    binding_sha256: StrictStr
    request_sha256: StrictStr
    prepared_at: StrictStr
    expires_at: StrictStr
    provider: StrictStr
    candidate: StrictStr
    model: StrictStr
    target_path: StrictStr
    source_sha256: StrictStr
    source_bytes: StrictInt
    confirmation: Literal["single_approval"]
    endpoint_source: Literal["project_config.supervised_implementer.endpoint"]
    endpoint_scheme: Literal["http", "https"]
    endpoint_host: StrictStr
    endpoint_port: StrictInt
    endpoint_base_path: StrictStr
    transport_tls: StrictBool
    endpoint_matched_environment: StrictBool
    presented_screen_sha256: StrictStr
    presented_screen: StrictStr


class DiffBinding(_Strict):
    diff_text_file: StrictStr
    diff_text_sha256: StrictStr
    diff_proposal_sha256: StrictStr
    p1b_run_id: StrictStr
    target_path: StrictStr
    pre_image_sha256: StrictStr
    post_image_sha256: StrictStr


_BINDINGS = {KIND_PLAN: PlanBinding, KIND_CONSENT: ConsentBinding, KIND_DIFF: DiffBinding}

#: P0-UX-H2-SIMPLE. The one value of ``confirmation`` a single-approval H2 binds.
SINGLE_APPROVAL = "single_approval"
PINNED_ENDPOINT_SOURCE = "project_config.supervised_implementer.endpoint"

#: The binding fields the human's answers set, for H2; every other binding
#: field is recomputed from the run directory at consumption and must match.
_CONSENT_ANSWER_FIELDS = (
    "endpoint_scheme",
    "endpoint_host",
    "endpoint_port",
    "endpoint_matched_environment",
    "transmission_confirmed",
    "plaintext_confirmed",
)
#: The same, for a single-approval H2: the destination is recomputed from the
#: pinned config, so only the observation and the presented screen are answers.
_SINGLE_ANSWER_FIELDS = (
    "endpoint_matched_environment",
    "presented_screen_sha256",
    "presented_screen",
)


def _binding_model(kind: str, binding: object) -> type[_Strict]:
    if kind == KIND_CONSENT and isinstance(binding, dict) and "confirmation" in binding:
        return SingleApprovalConsentBinding
    return _BINDINGS[kind]


def is_single_approval(subject: "Subject") -> bool:
    """Whether ``subject`` is an H2 the run's pinned config decides by one approval."""
    return subject.kind == KIND_CONSENT and subject.binding.get("confirmation") == SINGLE_APPROVAL


class Decision(_Strict):
    schema_version: Literal["aido-task-decision.v1"]
    decision_id: StrictStr
    run_id: StrictStr
    project_config_sha256: StrictStr
    round: Literal[1, 2]
    stage: StrictStr
    kind: Literal["plan_approval", "implementer_consent", "diff_approval"]
    decision: Literal["approve", "reject"]
    interface: Literal["terminal"]
    recorded_at: StrictStr
    account: StrictStr
    presented: Presented
    binding: dict


def stage_name(kind: str, rnd: Round) -> str:
    """The one stage a decision of ``kind`` in ``rnd`` is made at."""
    return rnd.stage_prefix + kind


def _aware(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value) if type(value) is str else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TaskRefused(f"{label} is not an ISO-8601 timestamp with an offset.")
    return parsed


def _check_account(account: object) -> str:
    if (
        type(account) is not str
        or not account.strip()
        or len(account) > MAX_ACCOUNT_CHARS
        or any(ord(char) < 32 or ord(char) == 127 for char in account)
    ):
        raise TaskRefused("the local account name is blank, too long or holds a control character.")
    return account


def observed_account() -> str:
    """The local account name. An observation, never an authenticated identity."""
    try:
        return _check_account(getpass.getuser())
    except TaskRefused:
        raise
    except Exception:  # noqa: BLE001 - getpass raises several types.
        raise TaskRefused("the local account name could not be observed. Nothing was recorded.") from None


def parse_decision(data: bytes, label: str) -> Decision:
    """Strictly parse one decision record. Rejects, never repairs."""
    document = _strict_json_object(data, label)
    try:
        decision = Decision.model_validate(document)
        _binding_model(decision.kind, decision.binding).model_validate(decision.binding)
    except ValidationError:
        raise TaskRefused(f"{label} is not a valid {DECISION_SCHEMA_VERSION} record.") from None
    _aware(decision.recorded_at, f"{label} recorded_at")
    _check_account(decision.account)
    digests = [decision.project_config_sha256, decision.presented.sha256]
    if "presented_screen_sha256" in decision.binding:
        digests.append(decision.binding["presented_screen_sha256"])
    for value in digests:
        if not _HEX64.fullmatch(value):
            raise TaskRefused(f"{label} carries a malformed digest.")
    return decision


def read_decision(path: str) -> Decision:
    return parse_decision(_read_bytes(path, os.path.basename(path)), os.path.basename(path))


def create_atomic_exclusive(path: str, data: bytes) -> None:
    """Create ``path`` whole or not at all; never overwrite.

    The bytes go to a private temporary file first, which is then hard-linked
    to ``path`` (the link fails if ``path`` exists), so an interruption never
    leaves a partial decision or serialized approval at ``path``.
    """
    temporary = f"{path}.{secrets.token_hex(8)}.tmp"
    task_run.create_exclusive(temporary, data)
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise TaskRefused(
                f"{os.path.basename(path)} already exists. A decision is recorded once "
                "and never replaced. Nothing new was recorded."
            ) from None
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


# -- what each decision is about ----------------------------------------------------


@dataclass(frozen=True)
class Subject:
    """One decision's exact subject, recomputed from the run directory."""

    kind: str
    rnd: Round
    decision_path: str
    draft_path: str
    draft_bytes: bytes
    draft: dict
    binding: dict
    evidence_run_dir: str | None = None


def _presented(subject: Subject) -> dict:
    return {
        "file": os.path.basename(subject.draft_path),
        "sha256": sha256_bytes(subject.draft_bytes),
        "size": len(subject.draft_bytes),
    }


def _require_untouched(subject: Subject, expected: dict) -> None:
    if _canonical(subject.draft) != _canonical(expected):
        raise TaskRefused(
            f"{os.path.basename(subject.draft_path)} is not AIDO's untouched draft: it was "
            "edited by hand. A decision is either a hand edit or an interactive one, "
            "never both. Nothing was recorded."
        )


def plan_subject(task: TaskRecord) -> Subject:
    path = task.path(PLAN_DRAFT_FILE)
    data = _read_bytes(path, PLAN_DRAFT_FILE)
    subject = Subject(
        KIND_PLAN,
        ROUND_1,
        task.path(PLAN_DECISION_FILE),
        path,
        data,
        _strict_json_object(data, PLAN_DRAFT_FILE),
        {"target_path": task.target_path},
    )
    _require_untouched(subject, task_run.build_plan_draft(task))
    return subject


def diff_subject(task: TaskRecord, rnd: Round, evidence_run_dir: str) -> Subject:
    from ai_dev_orchestrator.supervised_implementer.live import DIFF_FILE

    path = task.path(rnd.diff_draft_file)
    data = _read_bytes(path, rnd.diff_draft_file)
    proposal_bytes = _read_bytes(os.path.join(evidence_run_dir, DIFF_FILE), DIFF_FILE)
    proposal = _strict_json_object(proposal_bytes, DIFF_FILE)
    expected = task_run.build_diff_draft(task, proposal)
    diff_text = _read_bytes(task.path(rnd.diff_text_file), rnd.diff_text_file)
    change = proposal["changes"][0]
    if diff_text != (str(change.get("unified_diff")) + "\n").encode("utf-8"):
        raise TaskRefused(f"{rnd.diff_text_file} is not the implementer's proposed diff. Nothing was recorded.")
    binding = {
        "diff_text_file": rnd.diff_text_file,
        "diff_text_sha256": sha256_bytes(diff_text),
        "diff_proposal_sha256": sha256_bytes(proposal_bytes),
        "p1b_run_id": os.path.basename(evidence_run_dir),
        "target_path": task.target_path,
        "pre_image_sha256": str(change.get("pre_image_sha256")),
        "post_image_sha256": str(change.get("post_image_sha256")),
    }
    subject = Subject(
        KIND_DIFF,
        rnd,
        task.path(rnd.diff_decision_file),
        path,
        data,
        _strict_json_object(data, rnd.diff_draft_file),
        binding,
        evidence_run_dir,
    )
    _require_untouched(subject, expected)
    return subject


def consent_subject(task: TaskRecord, rnd: Round, authorization_path: str) -> Subject:
    from ai_dev_orchestrator.supervised_implementer.live_authorization import (
        DRAFT_CONSENT_TEMPLATE,
        AuthorizationBound,
    )

    name = os.path.basename(authorization_path)
    data = _read_bytes(authorization_path, name)
    document = _strict_json_object(data, name)
    if set(document) != {"bound", "consent"} or not isinstance(document.get("bound"), dict):
        raise TaskRefused(f"{name} is not an authorization draft. Nothing was recorded.")
    try:
        bound = AuthorizationBound.model_validate(document["bound"])
    except ValidationError:
        raise TaskRefused(f"{name}'s bound section is invalid or was edited. Nothing was recorded.") from None
    if _canonical(document["consent"]) != _canonical(DRAFT_CONSENT_TEMPLATE):
        raise TaskRefused(
            f"{name}'s consent block was edited by hand. A consent is either a hand edit "
            "or an interactive one, never both. Nothing was recorded."
        )
    binding = {
        "authorization_file": name,
        "p1b_run_id": bound.run_id,
        "binding_sha256": bound.binding_sha256,
        "request_sha256": bound.request_sha256,
        "prepared_at": bound.prepared_at,
        "expires_at": bound.expires_at,
        "provider": bound.provider,
        "model": bound.model,
        "target_path": bound.target_path,
        "source_sha256": bound.source_sha256,
        "source_bytes": bound.source_bytes,
    }
    # P0-UX-H2-SIMPLE: the mode and the destination come from the run's pinned
    # project config (checked against task.json's digest), never from a record.
    pinned = pinned_project(task).supervised_implementer.endpoint
    if pinned is not None:
        binding = {
            **binding,
            "candidate": bound.candidate,
            "confirmation": SINGLE_APPROVAL,
            "endpoint_source": PINNED_ENDPOINT_SOURCE,
            "endpoint_scheme": pinned.scheme,
            "endpoint_host": pinned.host,
            "endpoint_port": pinned.port,
            "endpoint_base_path": pinned.base_path,
            "transport_tls": pinned.scheme == "https",
        }
    return Subject(
        KIND_CONSENT,
        rnd,
        consent_decision_path(authorization_path),
        authorization_path,
        data,
        document,
        binding,
    )


def _build_record(task: TaskRecord, subject: Subject, decision: str, now: datetime, account: str, answers: dict) -> dict:
    return {
        "schema_version": DECISION_SCHEMA_VERSION,
        "decision_id": secrets.token_hex(16),
        "run_id": os.path.basename(task.run_dir),
        "project_config_sha256": task.project_config_sha256,
        "round": subject.rnd.number,
        "stage": stage_name(subject.kind, subject.rnd),
        "kind": subject.kind,
        "decision": decision,
        "interface": INTERFACE,
        "recorded_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "account": _check_account(account),
        "presented": _presented(subject),
        "binding": {**subject.binding, **answers},
    }


def record_decision(task: TaskRecord, subject: Subject, decision: str, *, now: datetime, account: str, answers: dict | None = None) -> str:
    """Write the one decision record for ``subject``. Write-once."""
    answers = dict(answers or {})
    if is_single_approval(subject) and not answers:
        raise TaskRefused(
            "a single-approval H2 decision needs the environment check and the presented "
            "screen. Nothing was recorded."
        )
    if subject.kind == KIND_CONSENT and not answers:
        answers = {
            "endpoint_scheme": None,
            "endpoint_host": None,
            "endpoint_port": None,
            "endpoint_matched_environment": False,
            "transmission_confirmed": False,
            "plaintext_confirmed": False,
        }
    record = _build_record(task, subject, decision, now, account, answers)
    data = _json_bytes(record)
    checked = parse_decision(data, os.path.basename(subject.decision_path))
    _check_consistent(task, subject, checked, now)
    create_atomic_exclusive(subject.decision_path, data)
    return subject.decision_path


def _check_consistent(task: TaskRecord, subject: Subject, decision: Decision, now: datetime) -> None:
    """The decision is about exactly this subject, and its answers are coherent."""
    label = os.path.basename(subject.decision_path)
    expected = {
        "run_id": os.path.basename(task.run_dir),
        "project_config_sha256": task.project_config_sha256,
        "round": subject.rnd.number,
        "stage": stage_name(subject.kind, subject.rnd),
        "kind": subject.kind,
    }
    actual = {name: getattr(decision, name) for name in expected}
    if actual != expected:
        raise TaskRefused(f"{label} is for another run, config, round, stage or kind. It is refused.")
    if decision.presented.model_dump() != _presented(subject):
        raise TaskRefused(
            f"{label} was made for different bytes of {os.path.basename(subject.draft_path)} "
            "than the file holds now. The decision is stale and is refused."
        )
    binding = dict(decision.binding)
    single = is_single_approval(subject)
    answer_fields = _SINGLE_ANSWER_FIELDS if single else _CONSENT_ANSWER_FIELDS
    answers = {name: binding.pop(name) for name in answer_fields if name in binding}
    if _canonical(binding) != _canonical(subject.binding):
        raise TaskRefused(f"{label} binds different data than this run now holds. It is refused.")
    recorded = _aware(decision.recorded_at, f"{label} recorded_at")
    if recorded > now + CLOCK_SKEW:
        raise TaskRefused(f"{label} is dated in the future of AIDO's clock. It is refused.")
    if subject.kind != KIND_CONSENT:
        return
    prepared = _aware(subject.binding["prepared_at"], "prepared_at")
    expires = _aware(subject.binding["expires_at"], "expires_at")
    if not prepared <= recorded <= expires:
        raise TaskRefused(f"{label} was not recorded while its authorization was valid. It is refused.")
    if single:
        # One typed answer, approve or reject, on a screen that showed the pinned
        # destination after the environment matched it. Nothing else is claimed.
        screen = answers.get("presented_screen")
        if (
            set(answers) != set(_SINGLE_ANSWER_FIELDS)
            or answers["endpoint_matched_environment"] is not True
            or type(screen) is not str
            or not screen
            or answers["presented_screen_sha256"] != sha256_bytes(screen.encode("utf-8"))
        ):
            raise TaskRefused(
                f"{label} lacks the environment match or its presented screen does not match "
                "its digest. It is refused."
            )
        return
    if decision.decision == REJECT:
        if any(answers[name] not in (None, False) for name in _CONSENT_ANSWER_FIELDS):
            raise TaskRefused(f"{label} is a rejection that carries consent answers. It is refused.")
        return
    scheme = answers["endpoint_scheme"]
    if (
        scheme is None
        or type(answers["endpoint_host"]) is not str
        or type(answers["endpoint_port"]) is not int
        or answers["endpoint_matched_environment"] is not True
        or answers["transmission_confirmed"] is not True
        or answers["plaintext_confirmed"] is not (scheme == "http")
    ):
        raise TaskRefused(
            f"{label} lacks the typed endpoint, the environment match, the transmission "
            "confirmation or the plaintext confirmation its scheme requires. It is refused."
        )


def validated_decision(task: TaskRecord, subject: Subject, *, now: datetime) -> Decision:
    """Read and fully re-validate the decision for ``subject``, at consumption."""
    decision = read_decision(subject.decision_path)
    _check_consistent(task, subject, decision, now)
    return decision


# -- serialization (task-continue only) -----------------------------------------------


def _approval_block(kind: str, decision: Decision) -> dict:
    from ai_dev_orchestrator.file_editing.models import REQUIRED_DIFF_EDIT_APPROVAL_TEXT
    from ai_dev_orchestrator.handoff.models import REQUIRED_APPROVAL_TEXT

    return {
        "approved_by": decision.account,
        "approved_at": decision.recorded_at,
        "approval_text": REQUIRED_APPROVAL_TEXT if kind == KIND_PLAN else REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
        "source": "manual",
    }


def approved_bytes(task: TaskRecord, subject: Subject, *, now: datetime) -> bytes:
    """The frozen plan or diff approval serialized from an APPROVE decision."""
    decision = validated_decision(task, subject, now=now)
    if decision.decision != APPROVE:
        raise TaskRefused(f"{os.path.basename(subject.decision_path)} records a rejection. Nothing runs.")
    document = dict(subject.draft)
    document["approval"] = _approval_block(subject.kind, decision)
    return _json_bytes(document)


def consent_bytes(task: TaskRecord, subject: Subject, *, now: datetime) -> bytes:
    """The consented authorization serialized from an APPROVE decision."""
    from ai_dev_orchestrator.supervised_implementer.live_authorization import (
        CONSENT_TEXT,
        PLAINTEXT_ACKNOWLEDGEMENT,
        parse_authorization,
    )
    from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused

    decision = validated_decision(task, subject, now=now)
    if decision.decision != APPROVE:
        raise TaskRefused(f"{os.path.basename(subject.decision_path)} records a rejection. Nothing is sent.")
    binding = decision.binding
    if is_single_approval(subject):
        # P0-UX-H2-SIMPLE: P1B's consent schema is unchanged, so the one approval
        # is serialized into its fixed fields: the pinned destination (from the
        # validated binding, i.e. the pinned config) and, for http, the fixed
        # acknowledgement phrase of the NOT TLS-ENCRYPTED risk the screen showed.
        # The decision record, not this block, says that ONE answer was typed.
        plaintext = binding["endpoint_scheme"] == "http"
    else:
        plaintext = binding["plaintext_confirmed"]
    consent = {
        "consented_by": decision.account,
        "consented_at": decision.recorded_at,
        "source": "manual",
        "binding_sha256": subject.binding["binding_sha256"],
        "endpoint_scheme": binding["endpoint_scheme"],
        "endpoint_host": binding["endpoint_host"],
        "endpoint_port": binding["endpoint_port"],
        "consent_text": CONSENT_TEXT,
        "plaintext_acknowledgement": PLAINTEXT_ACKNOWLEDGEMENT if plaintext else None,
    }
    data = (
        json.dumps({"bound": subject.draft["bound"], "consent": consent}, ensure_ascii=True, indent=2) + "\n"
    ).encode("ascii")
    try:
        parse_authorization(data)  # the unchanged P1B parser decides
    except SupervisedImplementerRefused as exc:
        raise TaskRefused(f"the serialized consent was refused by the accepted parser: {exc}") from None
    return data


def write_or_match(path: str, data: bytes) -> None:
    """Create ``path`` with ``data``, or require the existing file to be exactly ``data``."""
    if os.path.lexists(path):
        if _read_bytes(path, os.path.basename(path)) != data:
            raise TaskRefused(
                f"{os.path.basename(path)} exists but is not what the recorded decision "
                "serializes to. It is refused, never replaced."
            )
        return
    create_atomic_exclusive(path, data)


def authorization_for_run(task: TaskRecord, rnd: Round, *, now: datetime) -> str:
    """The authorization file the P1B run consumes: the consented copy, or the hand-edited draft."""
    problem = authorization_records_problem(task, rnd)
    if problem is not None:
        raise TaskRefused(f"{problem} Nothing was sent.")
    latest = task_run.authorization_paths(task, rnd)[-1]
    decided = consent_decision_path(latest)
    serialized = consented_path(latest)
    if not os.path.lexists(decided):
        if os.path.lexists(serialized):
            raise TaskRefused(
                f"{os.path.basename(serialized)} exists without its decision record. Nothing was sent."
            )
        return latest  # the manual path, unchanged
    subject = consent_subject(task, rnd, latest)
    write_or_match(serialized, consent_bytes(task, subject, now=now))
    return serialized


# -- rejections, in stage derivation ------------------------------------------------------

#: ``create_atomic_exclusive``'s private temporary name; it never carries a decision.
_TEMPORARY = re.compile(r"\.[0-9a-f]{16}\.tmp$")
_NUMBER = re.compile(r"[1-9][0-9]*")
#: Checked in this order: ``.json`` also ends the two longer suffixes.
_AUTHORIZATION_SUFFIXES = (".decision.json", ".consented.json", ".json")


def authorization_records_problem(task: TaskRecord, rnd: Round) -> str | None:
    """Why ``rnd``'s authorization records cannot be accounted for, or ``None``.

    Every file named like one of the round's authorization records is examined
    by its OWN name, not reached through a draft (P0-UX1-T1-FU1), so a decision
    or consent whose draft is gone is still seen. It fails closed when:

    - a name is not a draft, decision or consent name AIDO writes;
    - the drafts are not numbered exactly 1..n;
    - a decision has no draft, or a consent has no decision;
    - more prepare steps succeeded than drafts exist (a draft was removed
      together with its decision).

    A rejection therefore cannot be hidden by removing its draft, and an
    earlier approved authorization cannot become the latest one again.
    """
    prefix = rnd.authorization_name.split("{n}")[0]
    found: dict[str, dict[int, str]] = {suffix: {} for suffix in _AUTHORIZATION_SUFFIXES}
    for name in sorted(os.listdir(task.run_dir)):
        if not name.startswith(prefix) or _TEMPORARY.search(name):
            continue
        rest = name[len(prefix) :]
        suffix = next((candidate for candidate in _AUTHORIZATION_SUFFIXES if rest.endswith(candidate)), None)
        number = rest[: -len(suffix)] if suffix is not None else ""
        if not _NUMBER.fullmatch(number):
            return f"{name} is not an authorization draft, decision or consent name AIDO writes."
        found[suffix][int(number)] = name
    decisions, consented, drafts = (found[suffix] for suffix in _AUTHORIZATION_SUFFIXES)
    if sorted(drafts) != list(range(1, len(drafts) + 1)):
        return (
            f"the authorization drafts are not numbered 1..{len(drafts)} "
            f"({', '.join(drafts[n] for n in sorted(drafts))}): a draft is missing."
        )
    for number in sorted(set(decisions) - set(drafts)):
        return (
            f"{decisions[number]} records a decision, but its authorization draft "
            f"{rnd.authorization_name.format(n=number)} is missing, so it cannot be accounted for."
        )
    for number in sorted(set(consented) - set(decisions)):
        return f"{consented[number]} exists without its decision record."
    prepared = sum(
        1 for record in task_run.step_records(task) if record.step == rnd.step_prepare and record.exit_code == 0
    )
    if prepared > len(drafts):
        return (
            f"{prepared} successful {rnd.step_prepare} step(s) are recorded, but only "
            f"{len(drafts)} authorization draft(s) exist: a draft is missing."
        )
    return None


def _decision_paths(task: TaskRecord, rnd: Round) -> list[str]:
    paths = [task.path(PLAN_DECISION_FILE)] if rnd.number == 1 else []
    paths += [consent_decision_path(path) for path in task_run.authorization_paths(task, rnd)]
    paths.append(task.path(rnd.diff_decision_file))
    return [path for path in paths if os.path.lexists(path)]


def _invalid(message: str, rnd: Round) -> Stage:
    return Stage(
        rnd.stage_prefix + "decision_record_invalid",
        True,
        message + " A decision record is never repaired or replaced. HUMAN INSPECTION "
        "OF THE RUN DIRECTORY IS REQUIRED. Nothing more will run.",
        round_number=rnd.number,
    )


def rejection_stage(task: TaskRecord, rnd: Round) -> Stage | None:
    """A terminal stage if one of ``rnd``'s decisions is a rejection or is unreadable.

    A rejection ends the task (round 1) or the correction round (round 2). A
    rejection that later records contradict, an unreadable record, or an
    authorization record that cannot be accounted for, fails closed.
    """
    problem = authorization_records_problem(task, rnd)
    if problem is not None:
        return _invalid(problem[0].upper() + problem[1:], rnd)
    rejected = None
    for path in _decision_paths(task, rnd):
        name = os.path.basename(path)
        try:
            decision = read_decision(path)
        except TaskRefused as exc:
            return _invalid(str(exc), rnd)
        if (
            decision.run_id != os.path.basename(task.run_dir)
            or decision.kind != _decision_kind(name, rnd)
            or decision.round != rnd.number
            or decision.stage != stage_name(decision.kind, rnd)
            or decision.presented.file != _decision_subject_file(name, rnd)
        ):
            return _invalid(f"{name} names another run, round, stage or file.", rnd)
        if decision.decision == REJECT and rejected is None:
            rejected = (path, decision)
    if rejected is None:
        return None
    path, decision = rejected
    progress = _progress_after(task, rnd, decision)
    if progress is not None:
        return _invalid(f"{os.path.basename(path)} records a rejection, but {progress}.", rnd)
    what = {KIND_PLAN: "the plan", KIND_CONSENT: "the implementer consent", KIND_DIFF: "the diff"}[decision.kind]
    ending = (
        "The task has ended at your decision. Start a new task to try again."
        if rnd.number == 1
        else "The correction round has ended at your decision; no further round exists. "
        "Round 1's evidence is preserved."
    )
    return Stage(
        rnd.stage_prefix + "rejected",
        True,
        f"You rejected {what} ({os.path.basename(path)}). {ending} Nothing was sent or "
        "written after the rejection. AIDO committed nothing.",
        round_number=rnd.number,
    )


def _decision_kind(decision_name: str, rnd: Round) -> str:
    if decision_name == PLAN_DECISION_FILE:
        return KIND_PLAN
    if decision_name == rnd.diff_decision_file:
        return KIND_DIFF
    return KIND_CONSENT


def _decision_subject_file(decision_name: str, rnd: Round) -> str:
    if decision_name == PLAN_DECISION_FILE:
        return PLAN_DRAFT_FILE
    if decision_name == rnd.diff_decision_file:
        return rnd.diff_draft_file
    return decision_name[: -len(".decision.json")] + ".json"


def _progress_after(task: TaskRecord, rnd: Round, decision: Decision) -> str | None:
    if decision.kind == KIND_PLAN:
        if os.path.lexists(task.path(PLAN_APPROVED_FILE)) or task_run.authorization_paths(task, rnd):
            return "the plan was frozen or an authorization was prepared afterwards"
        return None
    if decision.kind == KIND_CONSENT:
        if task_run.consumed_authorization(task, rnd) is not None:
            return "an implementer authorization of this round was consumed"
        drafts = [os.path.basename(path) for path in task_run.authorization_paths(task, rnd)]
        if drafts[-1:] != [decision.binding["authorization_file"]]:
            return "another authorization was prepared afterwards"
        return None
    if os.path.lexists(task.path(rnd.diff_approved_file)) or any(
        record.step in (rnd.step_apply, rnd.step_review) for record in task_run.step_records(task)
    ):
        return "the diff was frozen or a write/review step ran afterwards"
    return None


# -- the terminal presentation ---------------------------------------------------------------


def escape_terminal_text(text: str, encoding: str | None = None) -> tuple[str, int]:
    """Make ``text`` safe to print: hidden, reordering or overwriting characters
    become visible escapes. Returns the text and how many characters were escaped.

    ``\\n`` and ``\\t`` are kept. Every other C0 control (including ``\\r``),
    DEL, C1, bidi controls, zero-width characters and line separators are
    escaped, as is any character the console encoding cannot show (never
    dropped).
    """
    parts: list[str] = []
    escaped = 0
    for char in text:
        code = ord(char)
        hidden = (
            (code < 32 and char not in "\n\t")
            or code == 127
            or 0x80 <= code <= 0x9F
            or code in _BIDI
            or code in _ZERO_WIDTH_AND_SEPARATORS
        )
        if not hidden and encoding:
            try:
                char.encode(encoding)
            except (UnicodeEncodeError, LookupError):
                hidden = True
        if hidden:
            escaped += 1
            parts.append(f"\\x{code:02x}" if code < 0x100 else (f"\\u{code:04x}" if code < 0x10000 else f"\\U{code:08x}"))
        else:
            parts.append(char)
    return "".join(parts), escaped


class Display:
    """Collects escaped lines and counts what had to be escaped."""

    def __init__(self, encoding: str | None) -> None:
        self.encoding = encoding
        self.lines: list[str] = []
        self.escaped = 0

    def add(self, text: str = "") -> None:
        safe, count = escape_terminal_text(text, self.encoding)
        self.escaped += count
        self.lines.extend(safe.split("\n"))

    def text(self) -> str:
        lines = list(self.lines)
        if self.escaped:
            lines.append(
                f"NOTE: {self.escaped} control, bidi, zero-width or undisplayable "
                "character(s) above are shown as visible \\x.. / \\u.... escapes."
            )
        return "\n".join(lines)


def pinned_project(task: TaskRecord):
    """The run's project config, from bytes that match the run's pinned digest.

    Read once and checked against ``task.json``'s SHA-256 before parsing, so
    what is displayed is exactly the config every later step is pinned to. It
    is display input only: it grants nothing, and no environment value is read.
    """
    import yaml

    from ai_dev_orchestrator.models import ProjectConfig

    data = _read_bytes(task.project_config, "the project config")
    if sha256_bytes(data) != task.project_config_sha256:
        raise TaskRefused(
            "the project config changed after this task started. A run uses one config "
            "from start to end; start a new task. Nothing was recorded."
        )
    try:
        document = yaml.safe_load(data.decode("utf-8"))
        return ProjectConfig.model_validate(document)
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError):
        raise TaskRefused("the pinned project config could not be parsed. Nothing was recorded.") from None


def _on_disk(workspace: str, target_path: str) -> str:
    return os.path.join(workspace, *target_path.split("/"))


def _add_scope(display: Display, task: TaskRecord, project) -> None:
    """The configured workspace, repository and target, exactly as configured."""
    workspace = project.repo.workspace_path
    display.add(f"project:    {project.project_id} ({project.display_name})")
    display.add(f"workspace:  {workspace}   (configured Windows workspace root)")
    display.add(f"repository: {project.repo.github_repo}, issue {task.issue_number}")
    display.add(f"target:     {task.target_path}")
    display.add(f"  on disk:  {_on_disk(workspace, task.target_path)}")


def _add_verification(display: Display, project) -> None:
    verification = project.controlled_verification
    display.add("  2. VERIFY: run the project's configured verification ONCE. It is repository-")
    display.add("     controlled code and is NOT sandboxed (its effects and children are not confined).")
    if not verification.enabled or verification.executable is None:
        display.add("     controlled_verification is NOT ENABLED: the step will be refused.")
        return
    display.add(f"     executable: {verification.executable}")
    display.add(f"     arguments:  {len(verification.args)}, each passed verbatim as one argv entry" + (":" if verification.args else ""))
    for index, argument in enumerate(verification.args, start=1):
        display.add(f"       [{index}] {argument}")
    display.add(
        f"     cwd: the workspace root; no shell; stdin closed. AIDO's wait is bounded by "
        f"{verification.timeout_seconds} s (plus a fixed reap grace); captured output is capped "
        f"at {verification.max_output_bytes} bytes. This bounds AIDO's wait, not the process's life."
    )


def _add_reviewer(display: Display, project) -> None:
    review = project.controlled_review
    requests = (
        "in at most two requests (a second only if the first completes with no usable review)"
        if review.compact_retry_on_unusable_output
        else "in exactly one request"
    )
    display.add(f"  3. REVIEW, only if verification passes: SEND to the reviewer model, {requests}:")
    display.add(f"     provider {review.provider}, model {review.model}")
    endpoint = review.endpoint
    if not review.enabled or endpoint is None:
        display.add("     controlled_review is NOT ENABLED or has no endpoint: the review will be refused.")
    else:
        tls = "TLS (https)" if endpoint.scheme == "https" else "NOT TLS-ENCRYPTED (plaintext http)"
        display.add(
            f"     destination (authorized by the project config): {endpoint.scheme} host "
            f"{endpoint.host} port {endpoint.port}, transport {tls}."
        )
        display.add(
            "     The environment's reviewer base URL must match this scheme, host and port and the "
            "configured base path exactly, or nothing is sent to the reviewer (verification will "
            "already have run)."
        )
    display.add(
        "     What is sent: selected approved-plan prose, this exact diff, and the fresh "
        "verification facts with their bounded, redacted output. Never the full target file, "
        "other source, a file listing or git history. Redaction is a backstop, not a "
        "guarantee that nothing sensitive is sent."
    )


def _render_value(display: Display, label: str, value: object) -> None:
    if isinstance(value, list):
        display.add(f"{label}:" + ("" if value else " (none)"))
        for item in value:
            display.add(f"  - {item}")
    else:
        display.add(f"{label}: {value}")


def render_plan(task: TaskRecord, subject: Subject, encoding: str | None, project) -> str:
    display = Display(encoding)
    display.add(f"H1 PLAN APPROVAL — run {os.path.basename(task.run_dir)}, round 1")
    _add_scope(display, task, project)
    display.add(f"task:       {task.title}")
    display.add(f"draft {PLAN_DRAFT_FILE} sha256 {sha256_bytes(subject.draft_bytes)}")
    display.add("")
    display.add("----- the complete plan (its scope is exactly the one target above) -----")
    for key, value in subject.draft["plan"].items():
        _render_value(display, key, value)
    display.add("----- end of plan -----")
    display.add("")
    display.add(
        "Approving records this decision only. It runs nothing. The next step, typed "
        "separately on task-continue, prepares the implementer authorization offline: it "
        f"reads the complete content of {task.target_path} in the workspace above and "
        "sends nothing. Sending it needs a separate implementer consent (H2)."
    )
    return display.text()


def render_diff(task: TaskRecord, subject: Subject, encoding: str | None, project) -> str:
    binding = subject.binding
    workspace = project.repo.workspace_path
    display = Display(encoding)
    display.add(
        f"H3 EXACT-DIFF APPROVAL — run {os.path.basename(task.run_dir)}, round {subject.rnd.number}"
    )
    display.add(f"workspace:  {workspace}   (configured Windows workspace root)")
    display.add(f"target {binding['target_path']}")
    display.add(f"  on disk:  {_on_disk(workspace, binding['target_path'])}")
    display.add(f"pre-image sha256  {binding['pre_image_sha256']}")
    display.add(f"post-image sha256 {binding['post_image_sha256']}")
    display.add(f"diff {binding['diff_text_file']} sha256 {binding['diff_text_sha256']}")
    if subject.rnd.number == 2:
        display.add("This diff is against the ORIGINAL baseline; round 1's approval does not carry over.")
    display.add("----- the complete proposed diff (model-generated) -----")
    text = _read_bytes(task.path(binding["diff_text_file"]), binding["diff_text_file"]).decode("utf-8", "replace")
    display.add(text.rstrip("\n"))
    display.add("----- end of diff -----")
    display.add(
        "Approving records this decision only. It runs nothing. The next step, typed "
        "separately on task-continue (--apply-approved-plan --write-approved-file "
        "--verify-approved-file-edit --real-reviewer), does ALL of the following:"
    )
    display.add(
        f"  1. WRITE: apply exactly this diff to {_on_disk(workspace, binding['target_path'])} "
        "(one file, modify only, pre- and post-image pinned by the digests above)."
    )
    _add_verification(display, project)
    _add_reviewer(display, project)
    display.add("AIDO commits, pushes and restores nothing; the review verdict is advisory and ends at you.")
    return display.text()


def render_consent(task: TaskRecord, subject: Subject, encoding: str | None, now: datetime, project) -> str:
    binding = subject.binding
    bound = subject.draft["bound"]
    workspace = project.repo.workspace_path
    remaining = int((_aware(binding["expires_at"], "expires_at") - now).total_seconds() // 60)
    display = Display(encoding)
    display.add(
        f"H2 IMPLEMENTER CONSENT — run {os.path.basename(task.run_dir)}, round {subject.rnd.number}, "
        f"{binding['authorization_file']}"
    )
    display.add(f"workspace:  {workspace}   (configured Windows workspace root)")
    display.add(
        f"source scope: exactly ONE file, {binding['target_path']} — on disk "
        f"{_on_disk(workspace, binding['target_path'])}. No other file, listing, tree or git "
        "history is sent."
    )
    display.add(f"provider {binding['provider']}, model {binding['model']} (supervised implementer {bound['candidate']})")
    display.add(
        f"WHAT WILL BE SENT, in exactly one model request with zero transport retries "
        f"(wait bound {bound['attempt_timeout_seconds']} s):"
    )
    display.add(
        f"  - the COMPLETE current content of exactly one file: {binding['target_path']} "
        f"({binding['source_bytes']} bytes, sha256 {binding['source_sha256']}) at HEAD "
        f"{bound['workspace_head_object_id']}"
    )
    display.add("  - the approved plan's prose and AIDO's fixed implementer instructions")
    if project.supervised_implementer.output_envelope == "delimited_file":
        # P0-RECOVERY-T2: the opt-in envelope is named at H2; the default
        # display is unchanged. The request sha256 below binds the instruction.
        display.add(
            "  - reply format: delimited_file — the model is asked for the complete file "
            "as plain text between AIDO marker lines (opt-in; not the default JSON envelope)"
        )
    if subject.rnd.number == 2:
        display.add(
            "  - the correction data: the previous approved diff, AIDO-observed "
            "verification facts and any reviewer findings (redacted, as untrusted data)"
        )
    display.add(f"request sha256 {binding['request_sha256']}")
    display.add(
        f"authorization {binding['p1b_run_id']}, prepared {binding['prepared_at']}, expires "
        f"{binding['expires_at']} ({remaining} min left), single use"
    )
    if is_single_approval(subject):
        _add_pinned_destination(display, binding)
        return display.text()
    if bound["allow_insecure_http"]:
        display.add(
            "This project permits plaintext HTTP. If the endpoint is http, the source will "
            "be sent NOT TLS-ENCRYPTED, and you will be asked to confirm that separately."
        )
    display.add(
        "The endpoint is NOT shown here. If you approve, you type the endpoint you expect "
        "(scheme://host:port); AIDO compares it with the environment using P1B's rules."
    )
    display.add(
        "Approving records this decision only. It sends nothing. The transmission itself "
        "happens only when you run task-continue with its own flags."
    )
    return display.text()


def pinned_destination_url(binding: dict) -> str:
    """The pinned destination as ``scheme://host:port<base_path>``, from config values only."""
    return f"{binding['endpoint_scheme']}://{binding['endpoint_host']}:{binding['endpoint_port']}{binding['endpoint_base_path']}"


def _add_pinned_destination(display: Display, binding: dict) -> None:
    """P0-UX-H2-SIMPLE: the complete destination, its environment match, the TLS state."""
    from ai_dev_orchestrator.llm.config import ENV_BASE_URL

    url = pinned_destination_url(binding)
    display.add("")
    display.add(f"DESTINATION (pinned by the project config, {PINNED_ENDPOINT_SOURCE}):")
    display.add(f"  {url}")
    display.add(
        f"  scheme {binding['endpoint_scheme']}, host {binding['endpoint_host']}, port "
        f"{binding['endpoint_port']}, base path {binding['endpoint_base_path'] or '(none)'}"
    )
    display.add(f"  the one request goes to exactly {url}/chat/completions")
    display.add(
        f"  environment: {ENV_BASE_URL} matches this destination exactly (scheme, host, "
        "effective port and path; checked just now, again before your answer is recorded, "
        "and again by task-continue immediately before sending)"
    )
    if binding["transport_tls"]:
        display.add("  transport: TLS (https)")
    else:
        display.add("  transport: NOT TLS-ENCRYPTED (plaintext http)")
        display.add("!" * 72)
        display.add("!!  PLAINTEXT HTTP: this source will be sent NOT TLS-ENCRYPTED.        !!")
        display.add("!!  Anyone on the network path can read it. This is not secure.        !!")
        display.add("!" * 72)
    risk = ", including sending it NOT TLS-ENCRYPTED" if not binding["transport_tls"] else ""
    display.add("")
    display.add(
        f"Typing 'approve' consents to this ENTIRE transmission as shown above{risk}. It is "
        "the only confirmation. It records the decision only and sends nothing: the "
        "transmission happens only when you run task-continue --transmit-approved-source "
        "--real-implementer, within the authorization's validity."
    )


def check_pinned_environment(subject: Subject, read_base_url: Callable[[], object]) -> None:
    """P0-UX-H2-SIMPLE: the environment must resolve to the pinned destination.

    Reads exactly one environment value, the implementer base URL (never a key),
    and applies P1B's own rules: ``check_live_endpoint`` and the full pinned
    comparison ``check_pinned_endpoint``, which the run repeats before sending.
    The authority is the pinned config, never the value being checked. The URL
    is never displayed.
    """
    from ai_dev_orchestrator.models import ControlledReviewEndpointConfig
    from ai_dev_orchestrator.supervised_implementer.live import check_live_endpoint, check_pinned_endpoint
    from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused

    binding = subject.binding
    pinned = ControlledReviewEndpointConfig(
        scheme=binding["endpoint_scheme"],
        host=binding["endpoint_host"],
        port=binding["endpoint_port"],
        base_path=binding["endpoint_base_path"],
    )
    base_url = read_base_url()
    if base_url is None:
        raise TaskRefused("the implementer base URL is not set in the environment. Nothing was recorded.")
    try:
        check_live_endpoint(base_url, allow_insecure_http=subject.draft["bound"]["allow_insecure_http"])
        check_pinned_endpoint(base_url, pinned)
    except SupervisedImplementerRefused as exc:
        raise TaskRefused(
            f"the environment does not resolve to the pinned implementer destination: {exc} "
            "Fix the environment, or the project config in a new task. Nothing was recorded."
        ) from None


def single_approval_answers(subject: Subject, screen: str) -> dict:
    """The answer fields of a single-approval H2: the observation and what was shown."""
    return {
        "endpoint_matched_environment": True,
        "presented_screen_sha256": sha256_bytes(screen.encode("utf-8")),
        "presented_screen": screen,
    }


# -- the interaction ----------------------------------------------------------------------------


def _ask(prompt: Callable[[str], str], text: str) -> str:
    try:
        answer = prompt(text)
    except (EOFError, KeyboardInterrupt):
        raise Cancelled() from None
    if type(answer) is not str:
        raise Cancelled()
    return answer.strip()


def ask_decision(prompt: Callable[[str], str], what: str) -> str:
    """``approve`` or ``reject``; anything else (an empty line, EOF, Ctrl-C) cancels."""
    answer = _ask(prompt, f"Type 'approve' to approve {what}, 'reject' to reject it, anything else to cancel: ")
    if answer in (APPROVE, REJECT):
        return answer
    raise Cancelled()


def parse_typed_authority(text: str) -> tuple[str, str, int]:
    """``scheme://host:port`` as the human typed it, with an explicit effective port."""
    from ai_dev_orchestrator.supervised_implementer.live_authorization import _HOST

    match = _AUTHORITY.fullmatch(text)
    if match is None or not _HOST.fullmatch(match.group(2)):
        raise TaskRefused(
            "the endpoint must be typed as scheme://host:port with an explicit port "
            "(for example 443 for https), and nothing else. Nothing was recorded."
        )
    port = int(match.group(3))
    if not 1 <= port <= 65535:
        raise TaskRefused("the port must be between 1 and 65535. Nothing was recorded.")
    return match.group(1), match.group(2), port


def consent_answers(
    subject: Subject,
    *,
    prompt: Callable[[str], str],
    echo: Callable[[str], None],
    read_base_url: Callable[[], object],
) -> dict:
    """H2 after ``approve``: the typed endpoint, its match, then the transmission confirmations."""
    from ai_dev_orchestrator.supervised_implementer.live import check_live_endpoint
    from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerRefused

    typed = _ask(prompt, "Type the endpoint you expect the source to be sent to (scheme://host:port): ")
    if not typed:
        raise Cancelled()
    scheme, host, port = parse_typed_authority(typed)
    base_url = read_base_url()
    if base_url is None:
        raise TaskRefused("the implementer base URL is not set in the environment. Nothing was recorded.")
    try:
        endpoint = check_live_endpoint(base_url, allow_insecure_http=subject.draft["bound"]["allow_insecure_http"])
    except SupervisedImplementerRefused as exc:
        raise TaskRefused(f"the environment's endpoint is refused by P1B's rules: {exc} Nothing was recorded.") from None
    if (endpoint.scheme, endpoint.host, endpoint.port) != (scheme, host.lower(), port):
        raise TaskRefused(
            "the endpoint you typed does not match the endpoint the environment resolves "
            "to (scheme, host and effective port). It is not shown. Nothing was recorded."
        )
    tls = "TLS (https)" if scheme == "https" else "NOT TLS-ENCRYPTED (plaintext http)"
    echo(
        f"Destination confirmed: provider {subject.binding['provider']}, model "
        f"{subject.binding['model']}, {scheme} host {endpoint.host} port {endpoint.port}, transport {tls}."
    )
    echo(
        f"Sending: the complete content of {subject.binding['target_path']} "
        f"({subject.binding['source_bytes']} bytes) in one request, when you run task-continue."
    )
    if _ask(prompt, f"Type '{TRANSMIT_WORD}' to confirm this transmission, anything else to cancel: ") != TRANSMIT_WORD:
        raise Cancelled()
    plaintext = scheme == "http"
    if plaintext:
        echo("!" * 72)
        echo("!!  PLAINTEXT HTTP: this source will be sent NOT TLS-ENCRYPTED.        !!")
        echo("!!  Anyone on the network path can read it. This is not secure.        !!")
        echo("!" * 72)
        if _ask(prompt, f"Type '{PLAINTEXT_WORD}' to confirm sending it unencrypted, anything else to cancel: ") != PLAINTEXT_WORD:
            raise Cancelled()
    return {
        "endpoint_scheme": scheme,
        "endpoint_host": host,
        "endpoint_port": port,
        "endpoint_matched_environment": True,
        "transmission_confirmed": True,
        "plaintext_confirmed": plaintext,
    }


def default_read_base_url() -> object:
    """Exactly one environment value: the implementer's base URL. Never a key."""
    from ai_dev_orchestrator.llm.config import ENV_BASE_URL

    return os.environ.get(ENV_BASE_URL)


def default_encoding() -> str:
    return getattr(sys.stdout, "encoding", None) or "utf-8"
