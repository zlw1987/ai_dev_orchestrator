"""The qualification-owned retained-evidence safety and emission choke point.

Phase 5F3B-I1-FU1. Every qualification evidence artifact -- a run record, an
artifact-emission refusal, and lineage/invalidation evidence alike -- is
written through :func:`emit_evidence_or_refuse` and nowhere else. Two
integrity properties are enforced here, structurally, rather than left to
each caller's discipline:

**1. An explicit safety context is MANDATORY.**
:class:`ArtifactSafetyContext` carries the run's known runtime-sensitive
values. The emission API takes it as a REQUIRED argument, with no default,
because a defaulted "nothing to check" argument is exactly how a bare
endpoint host survives into a retained artifact: the caller who forgets it
gets the same silent success as the caller who correctly has nothing to
declare. An offline caller with genuinely nothing to declare says so
explicitly via ``ArtifactSafetyContext.none_declared()``.

**2. Emission is EXCLUSIVE-CREATE.**
Emitted artifacts are immutable after emission (design Sec. 26). A writer
opened in ``"w"`` mode silently truncates whatever was already at that
pathname, which would let a later refusal artifact destroy an earlier valid
historical record merely because the same output path was supplied. Every
write here uses ``"x"`` (``O_CREAT | O_EXCL``): the first write to a fresh
pathname succeeds, and any second write to the same pathname fails closed
with :class:`EvidencePathCollisionError`, leaving the first file byte-for-
byte unchanged.

Scrubbing reuses ``ar2.record.scrub_check`` UNMODIFIED (it is already
generic over ``(record, extra_forbidden)``), and adds one structural rule
this package owns: a bare IPv4 literal. AR2's own R1-b run established that
a bare host or IP can reach an artifact by a route the base-URL needle does
not cover; a needle only catches a value the caller knew to declare, so an
undeclared dotted quad is caught structurally instead. A false positive
refuses a legitimate record, which is the intended fail-closed direction.

**Redaction and scrubbing are BACKSTOPS, not guarantees.** Nothing here
claims a retained artifact is provably secret-free.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ar2.record import scrub_check

from . import PACKAGE_ID, REFUSAL_RECORD_VERSION


class EvidencePathCollisionError(Exception):
    """An evidence pathname already exists. Emitted artifacts are immutable."""


@dataclass(frozen=True)
class ArtifactSafetyContext:
    """The run's known runtime-sensitive values, declared explicitly.

    Every field is optional individually, but the CONTEXT ITSELF is not:
    :func:`emit_evidence_or_refuse` requires one. An all-``None`` context is
    a legitimate, explicit declaration that this caller has no
    qualification-specific sensitive values to check -- which is the correct
    state for I1's offline suite, where no endpoint, credential, broker
    binding or live workspace exists at all.

    I1 defines this contract; it does NOT implement 5F3B-I2's credential
    handling. No field here is ever read from the environment, and no value
    placed in one is ever transmitted anywhere -- these values exist only to
    be searched for and refused.
    """

    endpoint_host: str | None = None
    api_key: str | None = None
    bearer_token: str | None = None
    broker_token: str | None = None
    pipe_name: str | None = None
    capability_id: str | None = None
    workspace_absolute_path: str | None = None

    @classmethod
    def none_declared(cls) -> "ArtifactSafetyContext":
        """An explicit "this caller has no sensitive values to declare" context.

        Deliberately a named constructor rather than a default argument: the
        caller states the fact, instead of inheriting it by omission.
        """
        return cls()

    def forbidden_needles(self) -> tuple[tuple[str, str], ...]:
        """``(finding_code, needle)`` pairs for ``ar2.record.scrub_check``.

        Findings carry the CODE only, never the needle -- a finding that
        echoed the offending value back would turn detection into a leak.
        """
        declared: tuple[tuple[str, str | None], ...] = (
            ("endpoint_host_value_present", self.endpoint_host),
            ("api_key_value_present", self.api_key),
            ("bearer_token_value_present", self.bearer_token),
            ("broker_token_present", self.broker_token),
            ("broker_pipe_name_present", self.pipe_name),
            ("broker_capability_id_present", self.capability_id),
            ("workspace_absolute_path_present", self.workspace_absolute_path),
        )
        return tuple((code, value) for code, value in declared if value)


# A dotted quad not embedded in a longer digit/dot run. Version strings such
# as "0.84.2" have three components and never match; a four-component match
# is additionally range-checked so "1.2.3.999" is not reported as an address.
_IPV4_LITERAL = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")


def _structural_findings(serialized: str) -> list[str]:
    """Package-owned structural rules layered on top of ``scrub_check``."""
    for match in _IPV4_LITERAL.finditer(serialized):
        if all(0 <= int(octet) <= 255 for octet in match.groups()):
            return ["ipv4_literal_present"]
    return []


def qualification_scrub_check(
    payload: dict[str, Any], safety: ArtifactSafetyContext
) -> dict[str, Any]:
    """``ar2.record.scrub_check`` plus this package's structural rules.

    Findings are bounded metadata codes, never the offending value, so this
    function's own output stays safe to persist even when the payload it
    checked was not.
    """
    check = scrub_check(payload, extra_forbidden=safety.forbidden_needles())
    findings = list(check["findings"])
    findings.extend(_structural_findings(json.dumps(payload, ensure_ascii=True)))
    return {"scrub_checked": True, "findings": findings, "clean": not findings}


def build_refusal_record(
    *, refused_record_kind: str, finding_count: int, finding_categories: list[str]
) -> dict[str, Any]:
    """A SAFE placeholder emitted INSTEAD of an artifact that failed scrub.

    Carries only fixed metadata -- experiment identity, what kind of artifact
    was refused, and the finding COUNT and CODES. Never the offending value,
    the unsafe candidate body, an endpoint, a credential, reasoning content,
    or any copied snippet that triggered a rule.
    """
    return {
        "experiment": PACKAGE_ID,
        "record_version": REFUSAL_RECORD_VERSION,
        "record_kind": "artifact emission refusal",
        "refused_record_kind": refused_record_kind,
        "is_review_packet": False,
        "reviewer_invoked": False,
        "outcome": "artifact_emission_refused",
        "scrub_checked": True,
        "candidate_artifact_not_emitted": True,
        "finding_count": finding_count,
        "finding_categories": sorted(set(finding_categories)),
    }


def write_evidence_exclusively(path: str, payload: dict[str, Any]) -> None:
    """Write one evidence artifact with ``O_CREAT | O_EXCL``, or fail closed.

    There is deliberately no overwrite, append, force, or replace variant of
    this function anywhere in the package.
    """
    try:
        handle = open(path, "x", encoding="utf-8", newline="\n")  # noqa: SIM115
    except FileExistsError as exc:
        raise EvidencePathCollisionError(
            "qualification evidence refused: an artifact already exists at this "
            "pathname, and emitted artifacts are immutable. Nothing was written, "
            "and the existing artifact is unchanged."
        ) from exc
    with handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True, sort_keys=True)
        handle.write("\n")


def emit_evidence_or_refuse(
    payload: dict[str, Any],
    *,
    path: str,
    safety: ArtifactSafetyContext,
    record_kind: str,
) -> dict[str, Any]:
    """THE emission choke point for every qualification evidence artifact.

    Fail-closed in both directions: an unsafe payload is never written (a
    bounded, independently scrub-checked refusal record is written in its
    place), and an already-occupied pathname is never overwritten by either
    the payload or the refusal.
    """
    check = qualification_scrub_check(payload, safety)
    if check["clean"]:
        write_evidence_exclusively(path, payload)
        return {"emitted": True, "refused": False, "path": path, "scrub": check}

    refusal = build_refusal_record(
        refused_record_kind=record_kind,
        finding_count=len(check["findings"]),
        finding_categories=list(check["findings"]),
    )
    refusal_check = qualification_scrub_check(refusal, safety)
    if not refusal_check["clean"]:  # pragma: no cover - the refusal shape is fixed and safe
        raise RuntimeError(
            "the qualification refusal record itself failed its own scrub check: "
            f"{refusal_check['findings']!r}"
        )
    write_evidence_exclusively(path, refusal)
    return {"emitted": True, "refused": True, "path": path, "scrub": check}
