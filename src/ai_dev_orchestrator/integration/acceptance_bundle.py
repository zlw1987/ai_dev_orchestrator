"""DL-4B S6 — the human-facing acceptance bundle and its publication (FD-7, AMEND1).

A held planner decision is the human's to accept or decline. What the human
reviews is a **bundle** the integration store builds from its own re-proven
records, never from a caller: the step contract and write scope, the approved
change, A's own observations M0/M1/M2, both execution claims with the claimed
outcome and verdict, the held planner envelope, and the exact
``step-acceptance-subject.v2`` the human signs. The bundle keeps the two
evidence classes apart (FD-15):

```text
aido_observed     what A observed or recorded itself: the clone's tree and .git
                  control state, the target digests, the approvals it verified,
                  the recorded lifecycle
execution_claims  what the execution identity printed: the write report, the
                  verification outcome and output, the review packet, the model's
                  verdict and findings. Repository code could have produced them
```

A publishes the bundle, and copies of every write-once blob it references,
into the boundary's ``published/`` directory, which A owns, O reads and X
cannot reach (FD-14; S0 re-proves it on every call). Every file is created
exclusively and re-read: a single-link regular file at its own path, owned by
A, holding exactly the bytes A wrote. A file already there is never replaced;
if its bytes differ, publication refuses. A reads ``published/`` only to
verify what it wrote; nothing in it is ever an authority input.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
from dataclasses import dataclass
from datetime import datetime

from ai_dev_orchestrator.control_plane.authority import BoundRoleOutput
from ai_dev_orchestrator.control_plane.integration_records import StepAcceptanceSubjectV2
from ai_dev_orchestrator.control_plane.models import canonical_json_bytes
from ai_dev_orchestrator.integration.authority_files import AuthorityFiles
from ai_dev_orchestrator.integration.boundary_facts import ObjectFacts
from ai_dev_orchestrator.integration.security_descriptor import DescriptorError, parse_security_descriptor

ACCEPTANCE_BUNDLE_SCHEMA_VERSION = "held-acceptance-bundle.v1"

#: Fixed AIDO text. The bundle states which facts A observed and which values
#: are execution claims (§5.3, AMEND1).
AIDO_OBSERVED_STATEMENT = (
    "Facts AIDO's authority identity observed or recorded itself: the clone's working tree and "
    ".git control state (M0 before the write, M1 after it, M2 after the review command), the "
    "target digests, the approvals it verified, and the step's recorded lifecycle. AIDO ran no "
    "Git, no harness and no model to obtain them."
)
EXECUTION_CLAIM_STATEMENT = (
    "Execution claims: bytes the execution identity printed. The write report, the verification "
    "outcome and output, the review packet, and the model's verdict and findings could all have "
    "been produced by repository code. A successful M2 shows only that the clone was as approved "
    "when AIDO looked; it does not authenticate the verifier or the reviewer."
)
PLANNER_STATEMENT = (
    "The held planner decision is AIDO's deterministic Alpha rule over the records above. It "
    "recommends; it never completes a step. Signing the acceptance subject accepts exactly these "
    "records, by digest."
)

#: The write-once blob kinds a bundle references, published as ``<kind>-<sha256>``.
BLOB_KINDS = ("approved-diff", "config", "claims", "observations")


class AcceptanceBundleError(Exception):
    """A bundle file could not be published, or ``published/`` does not hold
    exactly what A published."""


@dataclass(frozen=True)
class HeldAcceptanceDecision:
    """A planner decision held at ACCEPTANCE (FD-7), as the store re-proved it.
    ``duplicate`` marks the receipt of an identical repeated hold."""

    ticket_id: str
    step_run_id: str
    state_version: int
    envelope: BoundRoleOutput
    envelope_sha256: str
    held_at: datetime
    subject_sha256: str
    duplicate: bool = False


@dataclass(frozen=True)
class HeldAcceptanceBundle:
    """The human's review material for one held decision. ``document`` is the
    canonical JSON bundle; ``files`` are ``(published name, bytes)`` of the
    bundle's referenced blobs, then the bundle itself."""

    subject: StepAcceptanceSubjectV2
    name: str
    document: bytes
    files: tuple[tuple[str, bytes], ...]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.document).hexdigest()

    @property
    def content(self) -> dict:
        return json.loads(self.document)


@dataclass(frozen=True)
class PublishedAcceptanceBundle:
    """What A published: the bundle's name and digest, the subject it shows,
    and the names of every file A verified in ``published/``."""

    name: str
    sha256: str
    subject_sha256: str
    names: tuple[str, ...]


def bundle_name(subject_sha256: str) -> str:
    return f"acceptance-bundle-{subject_sha256}.json"


def blob_name(kind: str, sha256: str) -> str:
    if kind not in BLOB_KINDS:
        raise AcceptanceBundleError("no such blob kind.")
    return f"{kind}-{sha256}"


def bundle_bytes(content: dict) -> bytes:
    return canonical_json_bytes(content)


def _checked(read: object, path: str, name: str, authority_sid: str, data: bytes) -> None:
    if type(read) is not tuple or len(read) != 2:
        raise AcceptanceBundleError(f"published/{name} vanished after it was published.")
    facts, content = read
    if (
        type(facts) is not ObjectFacts or facts.is_directory is not False
        or facts.is_reparse_point is not False or facts.link_count != 1
        or facts.final_path is None or ntpath.normcase(facts.final_path) != ntpath.normcase(path)
    ):
        raise AcceptanceBundleError(f"published/{name} is not a single-link regular file at its own path.")
    try:
        owner = parse_security_descriptor(facts.security_descriptor).owner
    except DescriptorError:
        raise AcceptanceBundleError(f"the owner of published/{name} cannot be read.") from None
    if owner != authority_sid:
        raise AcceptanceBundleError(f"published/{name} is not owned by the authority identity.")
    if content != data:
        raise AcceptanceBundleError(f"published/{name} is not what AIDO published; it is never replaced.")


def publish(files: AuthorityFiles, published: str, authority_sid: str, bundle: HeldAcceptanceBundle,
            *, create: bool = True) -> PublishedAcceptanceBundle:
    """Publish (``create``) or only re-verify every file of ``bundle`` in
    ``published``: each exclusively created when absent, then re-read and
    compared byte for byte. Raises :class:`AcceptanceBundleError`."""
    names = []
    for name, data in bundle.files:
        path = ntpath.join(published, name)
        try:
            present = files.object_facts(path) is not None
            if not present:
                if not create:
                    raise AcceptanceBundleError(f"published/{name} is missing.")
                try:
                    files.create_file(path, data)
                except FileExistsError:
                    pass  # created meanwhile: verified below like any other file
            read = files.read_file(path, len(data))
        except AcceptanceBundleError:
            raise
        except Exception as exc:  # noqa: BLE001 - an unverifiable publication shows the human nothing
            raise AcceptanceBundleError(
                f"published/{name} could not be published or read ({type(exc).__name__})."
            ) from None
        _checked(read, path, name, authority_sid, data)
        names.append(name)
    return PublishedAcceptanceBundle(name=bundle.name, sha256=bundle.sha256,
                                     subject_sha256=bundle.subject.sha256, names=tuple(names))
