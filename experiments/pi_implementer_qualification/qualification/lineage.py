"""Immutable invalidation/replacement lineage evidence (Sec. 13, Sec. 26).

**Binding interpretation, corrected from one ambiguous Sec. 13 sentence in
the design document** (see the wording fix applied to Sec. 13 itself): an
already-emitted qualification record is NEVER mutated. If a fixture/prompt
defect or an infrastructure-contamination finding is discovered after a
record was emitted:

    the old historical record stays byte-for-byte unchanged on disk
    a NEW, separate lineage/invalidation artifact is created, referencing
    the old record by its exact content digest and task revision
    a replacement record (if one exists yet) is linked back via
    ``supersedes_task_revision`` (see ``records.build_qualification_record``)

Three properties make that structural rather than merely intended:

1. **Lineage evidence goes through the SAME safety choke point as a run
   record** (Phase 5F3B-I1-FU1). It is scrub-checked against an explicit
   :class:`~qualification.safety.ArtifactSafetyContext` and refused if
   unsafe. Lineage fields carry operator-supplied reasons and identifiers,
   so exempting them from the retained-evidence policy would leave an
   obvious hole in exactly the artifact class that describes failures.
2. **Every write is exclusive-create** (FU1). Lineage can never overwrite an
   earlier qualification record or an earlier lineage artifact.
3. **The old and replacement records are READ AND VERIFIED, never merely
   named** (Phase 5F3B-I1-FU2). ``build_invalidation_evidence`` previously
   accepted ``invalidated_task_revision`` as an independent caller-supplied
   value with no check against the file it named -- a caller error (or a
   deliberately falsified argument) could produce lineage whose declared
   ``invalidated_record_sha256`` and ``invalidated_task_revision`` describe
   TWO DIFFERENT run states. This module now opens both records READ-ONLY,
   parses them, and REJECTS the evidence outright unless the files
   themselves prove the claimed relationship -- see
   :func:`_read_and_verify_old_record` and
   :func:`_read_and_verify_replacement_record`.
4. **``invalidation_reason`` must mechanically agree with whether the task
   revision actually changed** (Phase 5F3B-I1-FU2A). ``fixture_or_prompt_defect``
   means the frozen task/prompt/fixture contract itself changed, so any
   corrected/replacement revision that REUSES the old revision is refused.
   ``infrastructure_contamination`` means the task did NOT change, so any
   corrected/replacement revision that DIFFERS from the old revision is
   refused -- that shape would mislabel an actual task change as a pure
   infrastructure re-run. See :func:`_require_reason_matches_revision_change`.

Every record this module opens is opened in read-only (``"rb"``) mode. There
is no code path in this module that opens an existing record in any write
mode -- writing new evidence is exclusive-create only, via
:func:`write_invalidation_evidence`.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from . import LINEAGE_RECORD_VERSION, PACKAGE_ID
from .records import RECORD_KIND, RECORD_VERSION
from .safety import ArtifactSafetyContext, emit_evidence_or_refuse

LINEAGE_RECORD_KIND = "qualification lineage invalidation"

#: The two invalidation shapes Sec. 13 / Sec. 17.2 case 2 require support for.
FIXTURE_OR_PROMPT_DEFECT = "fixture_or_prompt_defect"
INFRASTRUCTURE_CONTAMINATION = "infrastructure_contamination"
_VALID_REASONS = frozenset({FIXTURE_OR_PROMPT_DEFECT, INFRASTRUCTURE_CONTAMINATION})


class LineageBindingError(ValueError):
    """The referenced old/replacement record does not prove the claimed relationship.

    Raised instead of emitting lineage that would assert a link the files
    themselves do not support -- a malformed record, a non-run-record
    artifact, or a caller-supplied identifier that disagrees with what the
    record actually contains.
    """


def sha256_of_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def _parse_record_json(raw_bytes: bytes, *, context: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LineageBindingError(f"{context} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LineageBindingError(f"{context} is not a JSON object")
    return parsed


def _require_run_record_shape(record: dict[str, Any], *, context: str) -> None:
    """The minimum shape Sec. C/D require of ANY record this module reads.

    Rejects, among other things, an artifact-emission refusal record
    supplied where a real run record was claimed: a refusal's
    ``record_kind`` is ``"artifact emission refusal"``, never
    ``RECORD_KIND``.
    """
    if record.get("record_kind") != RECORD_KIND:
        raise LineageBindingError(
            f"{context} does not have record_kind == {RECORD_KIND!r}; found "
            f"{record.get('record_kind')!r}"
        )
    if record.get("record_version") != RECORD_VERSION:
        raise LineageBindingError(
            f"{context} does not have record_version == {RECORD_VERSION!r}; found "
            f"{record.get('record_version')!r}"
        )
    if not record.get("task_id"):
        raise LineageBindingError(f"{context} has no declared task_id")
    if not record.get("task_revision"):
        raise LineageBindingError(f"{context} has no task_revision")


def _require_reason_matches_revision_change(
    *,
    invalidation_reason: str,
    old_task_revision: str,
    candidate_revision: str,
    label: str,
) -> None:
    """(FU2A) ``invalidation_reason`` <-> revision-change consistency.

    Called wherever a corrected/replacement revision is known -- once for a
    standalone ``corrected_task_revision`` (which may be supplied before any
    replacement record exists), and again for a supplied replacement
    record's own ``task_revision``, so the rule holds regardless of which of
    the two the caller provides first.
    """
    same_revision = candidate_revision == old_task_revision
    if invalidation_reason == FIXTURE_OR_PROMPT_DEFECT and same_revision:
        raise LineageBindingError(
            f"{label} {candidate_revision!r} reuses the invalidated record's own "
            "task_revision; a fixture/prompt-defect correction changes the frozen "
            "task/prompt/fixture contract and must therefore produce a DIFFERENT "
            "task_revision (Sec. 12.1's frozen-fixture identity)"
        )
    if invalidation_reason == INFRASTRUCTURE_CONTAMINATION and not same_revision:
        raise LineageBindingError(
            f"{label} {candidate_revision!r} differs from the invalidated record's "
            f"task_revision {old_task_revision!r}; infrastructure contamination "
            "re-runs the SAME frozen task, so a differing revision would mislabel "
            "an actual task change as a pure infrastructure replacement"
        )


@dataclass(frozen=True)
class _VerifiedOldRecord:
    sha256: str
    task_id: str
    task_revision: str
    candidate: str
    model_id: str


def _read_and_verify_old_record(
    path: str, *, invalidated_task_revision: str
) -> _VerifiedOldRecord:
    """Read the OLD record read-only and prove it matches the caller's claim.

    The caller-supplied ``invalidated_task_revision`` is no longer trusted
    independently of the file: it must equal the revision the record itself
    declares, or the evidence is refused before it is ever built.
    """
    raw_bytes = _read_bytes(path)
    record = _parse_record_json(raw_bytes, context="the invalidated record")
    _require_run_record_shape(record, context="the invalidated record")

    actual_revision = record["task_revision"]
    if actual_revision != invalidated_task_revision:
        raise LineageBindingError(
            f"invalidated_task_revision {invalidated_task_revision!r} disagrees with "
            f"the invalidated record's own task_revision {actual_revision!r}; lineage "
            "is refused rather than asserting a relationship the file does not prove"
        )
    if not record.get("candidate"):
        raise LineageBindingError("the invalidated record has no declared candidate")
    if not record.get("model_id"):
        raise LineageBindingError("the invalidated record has no declared model_id")

    return _VerifiedOldRecord(
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        task_id=record["task_id"],
        task_revision=actual_revision,
        candidate=record["candidate"],
        model_id=record["model_id"],
    )


def _read_and_verify_replacement_record(
    path: str,
    *,
    old: _VerifiedOldRecord,
    invalidation_reason: str,
    corrected_task_revision: str | None,
) -> tuple[str, str]:
    """Read the REPLACEMENT record read-only and prove it actually supersedes ``old``.

    Returns ``(sha256, task_revision)``. Rejects any mismatch rather than
    creating lineage that claims a relationship the files do not prove.
    """
    raw_bytes = _read_bytes(path)
    record = _parse_record_json(raw_bytes, context="the replacement record")
    _require_run_record_shape(record, context="the replacement record")

    if record.get("candidate") != old.candidate:
        raise LineageBindingError(
            f"the replacement record's candidate {record.get('candidate')!r} disagrees "
            f"with the invalidated record's candidate {old.candidate!r}"
        )
    if record.get("model_id") != old.model_id:
        raise LineageBindingError(
            f"the replacement record's model_id {record.get('model_id')!r} disagrees "
            f"with the invalidated record's model_id {old.model_id!r}"
        )
    if record.get("task_id") != old.task_id:
        raise LineageBindingError(
            f"the replacement record's task_id {record.get('task_id')!r} disagrees "
            f"with the invalidated record's task_id {old.task_id!r}"
        )

    supersedes = record.get("supersedes_task_revision")
    if supersedes != old.task_revision:
        raise LineageBindingError(
            f"the replacement record's supersedes_task_revision {supersedes!r} does not "
            f"equal the invalidated record's task_revision {old.task_revision!r}; a "
            "replacement must declare, in its OWN record, exactly what it supersedes"
        )

    replacement_revision = record["task_revision"]
    if corrected_task_revision is not None and corrected_task_revision != replacement_revision:
        raise LineageBindingError(
            f"corrected_task_revision {corrected_task_revision!r} disagrees with the "
            f"replacement record's own task_revision {replacement_revision!r}"
        )
    if invalidation_reason == FIXTURE_OR_PROMPT_DEFECT and corrected_task_revision is None:
        raise LineageBindingError(
            "a fixture/prompt-defect invalidation with a replacement record must supply "
            "corrected_task_revision, identifying the replacement record's revision -- "
            "the corrected fixture necessarily produces a different task_revision "
            "(Sec. 12.1's frozen-fixture identity), so leaving this unstated is refused"
        )
    # (FU2A) The reason must mechanically agree with whether the replacement
    # actually carries a different task revision than the run it replaces.
    _require_reason_matches_revision_change(
        invalidation_reason=invalidation_reason,
        old_task_revision=old.task_revision,
        candidate_revision=replacement_revision,
        label="the replacement record's task_revision",
    )

    return hashlib.sha256(raw_bytes).hexdigest(), replacement_revision


@dataclass(frozen=True)
class InvalidationEvidence:
    invalidated_record_filename: str
    invalidated_record_sha256: str
    invalidated_task_revision: str
    invalidation_reason: str
    corrected_task_revision: str | None
    replacement_record_filename: str | None
    replacement_record_sha256: str | None


def build_invalidation_evidence(
    *,
    invalidated_record_path: str,
    invalidated_task_revision: str,
    invalidation_reason: str,
    corrected_task_revision: str | None = None,
    replacement_record_path: str | None = None,
) -> dict[str, Any]:
    """Build NEW, linked invalidation evidence. Never opens any record for writing.

    Both ``invalidated_record_path`` and (if given) ``replacement_record_path``
    are opened READ-ONLY and their content is verified to actually support
    the claimed relationship (Phase 5F3B-I1-FU2) -- a caller-supplied
    revision, candidate, model id, or supersedes claim that disagrees with
    what the referenced file itself declares raises
    :class:`LineageBindingError` rather than being trusted and recorded.

    Paths are recorded by filename only (never an absolute workspace path),
    matching the retained-evidence safety rule.
    """
    if invalidation_reason not in _VALID_REASONS:
        raise ValueError(
            f"invalid invalidation_reason: {invalidation_reason!r}; declared: "
            f"{sorted(_VALID_REASONS)}"
        )

    old = _read_and_verify_old_record(
        invalidated_record_path, invalidated_task_revision=invalidated_task_revision
    )

    # (FU2A) A standalone corrected_task_revision is checked against the
    # reason immediately -- this holds even before any replacement record
    # exists (Sec. 13: a fixture/prompt-defect lineage may legitimately
    # exist temporarily with no replacement yet).
    if corrected_task_revision is not None:
        _require_reason_matches_revision_change(
            invalidation_reason=invalidation_reason,
            old_task_revision=old.task_revision,
            candidate_revision=corrected_task_revision,
            label="corrected_task_revision",
        )

    replacement_sha256: str | None = None
    replacement_filename: str | None = None
    if replacement_record_path is not None:
        replacement_sha256, _replacement_task_revision = _read_and_verify_replacement_record(
            replacement_record_path,
            old=old,
            invalidation_reason=invalidation_reason,
            corrected_task_revision=corrected_task_revision,
        )
        replacement_filename = os.path.basename(replacement_record_path)

    return {
        "experiment": PACKAGE_ID,
        "record_kind": LINEAGE_RECORD_KIND,
        "record_version": LINEAGE_RECORD_VERSION,
        "invalidated_record_filename": os.path.basename(invalidated_record_path),
        "invalidated_record_sha256": old.sha256,
        "invalidated_task_revision": old.task_revision,
        "invalidation_reason": invalidation_reason,
        "scoring_eligible": False,
        "corrected_task_revision": corrected_task_revision,
        "replacement_record_filename": replacement_filename,
        "replacement_record_sha256": replacement_sha256,
        "supersedes_relationship": (
            "replacement_record supersedes invalidated_record"
            if replacement_record_path
            else None
        ),
    }


def write_invalidation_evidence(
    evidence: dict[str, Any], *, path: str, safety: ArtifactSafetyContext
) -> dict[str, Any]:
    """Emit lineage evidence through the shared fail-closed choke point.

    ``safety`` is REQUIRED and has no default. The write is exclusive-create,
    so lineage can never overwrite an existing qualification record or an
    existing lineage artifact. If the evidence is unsafe, a bounded refusal
    record is written in its place and the unsafe evidence never reaches
    disk.
    """
    return emit_evidence_or_refuse(
        evidence, path=path, safety=safety, record_kind=LINEAGE_RECORD_KIND
    )


def verify_immutable(path: str, expected_sha256: str) -> bool:
    """True if the file at ``path`` still hashes to ``expected_sha256`` -- proves
    a prior record was never mutated after invalidation evidence was written."""
    return sha256_of_file(path) == expected_sha256
