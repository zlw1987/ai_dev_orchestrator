"""The coordinator's one pre-prepare workspace check (ALPHA-2A-T1).

AIDO never normalizes line endings: the 5F2C writer rejoins lines with the
file's own uniform ending, and the supervised implementer refuses a proposal
whose bytes the writer could not reproduce. A CRLF working-tree copy (Git's
``core.autocrlf=true`` Windows default) therefore cannot take an LF reply, so
the coordinator refuses it before anything is prepared or sent.

The check uses the implementer's own source read (the shipped 5D2 reader and
the writer's text-domain rules), so it cannot drift from what prepare reads.
It reads only; it never calls a model, a runner or a process.
"""

from __future__ import annotations

from ai_dev_orchestrator.handoff.models import ApprovedL1PlanArtifact
from ai_dev_orchestrator.models import ProjectConfig


def target_uses_crlf(project: ProjectConfig, approved_plan: ApprovedL1PlanArtifact, target_path: str) -> bool:
    """True when the target's working-tree copy is uniform CRLF text.

    Any refusal of the read itself returns ``False``: prepare re-reads the file
    and reports its own refusal.
    """
    from ai_dev_orchestrator.supervised_implementer.implementer import (
        _private_copies,
        _read_approved_source,
    )
    from ai_dev_orchestrator.supervised_implementer.models import SupervisedImplementerError

    try:
        source = _read_approved_source(*_private_copies(project, approved_plan), target_path)
    except SupervisedImplementerError:
        return False
    return source.ending == "\r\n"
