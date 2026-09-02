"""5F3B-Q1-PRE1 -- populate an I2B-minted workspace with ONE task's fixture content.

**OFFLINE ONLY.** The only subprocess activity here is local ``git`` (the
exact fixture-construction operation
``experiments/pi_external_runtime_ar2/ar2/fixtures.py`` already performs for
every other case in this repository). No Pi process, no socket, no HTTP
request, no credential.

Why this module exists
-----------------------

Two frozen origins already exist in this codebase, and neither can serve
this phase's need by itself:

- :func:`qualification.i2b_workspace.mint_qualification_run_workspace` is
  the **only** way to obtain a
  :class:`~qualification.i2b_workspace.QualificationRunWorkspace` -- the
  authority type :mod:`qualification.i2b_session`'s ``BrokerCreationRequest``
  / ``RuntimeLaunchRequest`` require by exact type. It takes **no**
  parameters and creates an **empty** directory, because Category-B sends
  zero prompts and therefore never needs file content in its workspace.
- :func:`ar2.fixtures.build_case_repository` (and its sibling
  :func:`ar2.fixtures.build_synthetic_repository`) is the only way to build a
  disposable Git repository populated with a
  :class:`~ar2.fixtures.CaseFixture`'s file content -- and by the deliberate
  5F3A-AR2-FU1A design, it **always** mints its OWN fresh root; "there is no
  way to point this at a pre-existing directory... that capability was
  removed in 5F3A-AR2-FU1A."

A semantic task run needs BOTH properties on the SAME directory at once: the
I2B-typed authority (so the broker/runtime request objects accept it) AND
task fixture content (so the model has something to read and edit, and so
AIDO's own baseline/final verification means anything). Neither frozen origin
can produce that by itself, and this is exactly the "frozen component cannot
truthfully represent a required semantic-run fact" case
``docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`` and this phase's
own prompt anticipate -- so this module adds the narrow bridge: mint the
authority-bearing EMPTY workspace via the frozen, unmodified
``mint_qualification_run_workspace()``, then populate that SAME, already
re-verified directory in place, using the identical mechanical steps
(``git init`` / ``git add`` / ``git commit``, with the identical fixed
fixture-git identity and minimal explicit environment) frozen AR2's own
``ar2.fixtures._build_repository_in_fresh_root`` already uses -- reproduced
here because that helper is module-private and therefore not importable, not
because the mechanics differ. The frozen fixture builders and this module's
population step are never invoked on the same repository at once, and this
module never creates or marks a root itself: it only writes into a directory
whose authority ``mint_qualification_run_workspace()`` already minted and
this module re-verifies again immediately before writing.

**A known, honest limitation.** ``mint_qualification_run_workspace()``
stamps every root's on-disk marker with
``qualification.i2b_workspace.QUALIFICATION_EXPERIMENT_ID ==
"5F3B-I2B-CATEGORY-B"`` unconditionally -- it has no parameter through which
a different experiment id could be supplied, by design (no path/parameter
surface at all, so a real workspace can never be named through it). A
semantic-sweep run is therefore minted under a marker whose experiment-id
label literally says "CATEGORY-B", even though this run goes on to send a
semantic prompt. This is a cosmetic provenance-label imprecision in an
in-memory, process-local, never-retained marker file (never surfaced in any
emitted evidence field), not a safety or authority defect: the marker's only
job is to let ``verify_run_workspace`` re-prove that AIDO itself created this
exact root, which it still does correctly. Re-declaring a parallel workspace-
minting mechanism purely to fix this label would duplicate a whole security
mechanism for a cosmetic string; this module does not do that, and instead
records the caveat here, honestly, exactly as this design's own "STOP and
report the incompatibility" instruction asks for a case that does not
justify forcing or duplicating a frozen invariant.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .corpus import QualificationTask
from .i2b_workspace import (
    QualificationRunWorkspace,
    WorkspaceAuthorityError,
    verify_run_workspace,
)

#: The identical fixed, non-secret Git author identity AR2's own fixture
#: builder uses (``ar2.fixtures._FIXTURE_GIT_USER_NAME`` /
#: ``_FIXTURE_GIT_USER_EMAIL``), reproduced as a VALUE because the AR2
#: constants are module-private. Never a real person, never configurable.
_FIXTURE_GIT_USER_NAME = "AIDO Qualification Semantic Fixture"
_FIXTURE_GIT_USER_EMAIL = "qualification-semantic-fixture@example.invalid"

#: Bounded git command timeout. Local, disposable-repo operations only.
_GIT_TIMEOUT_SECONDS = 60


class SemanticWorkspaceError(Exception):
    """A semantic task workspace could not be populated or proven. Fails closed.

    **Never echoes a path or raw git output.** Only a fixed reason code, the
    same discipline :class:`~qualification.i2b_workspace.WorkspaceAuthorityError`
    already applies.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"semantic task workspace refused: {reason_code}")
        self.reason_code = reason_code


def _fixture_git_environment() -> dict[str, str]:
    """A minimal, explicit environment for fixture Git. Never ``os.environ`` verbatim.

    Mirrors ``ar2.fixtures._fixture_git_environment`` exactly (same inherited
    name set, same fixed Git behavioral overrides) -- reproduced as new code
    because that helper is module-private, not because the policy differs.
    """
    inherited = (
        "PATH", "SystemRoot", "SystemDrive", "ComSpec", "windir", "TEMP", "TMP", "PATHEXT",
    )
    environment = {name: os.environ[name] for name in inherited if name in os.environ}
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
        }
    )
    return environment


def _git(git_executable: str, args: list[str], *, cwd: str, environment: dict[str, str]) -> str:
    """Run one fixture-population Git command. Fixed argv, ``shell=False``.

    Not the production fixed Git adapter (that is read-only by contract);
    this performs the writes fixture population genuinely requires, exactly
    the class of operation ``ar2.fixtures._git`` already performs.
    """
    completed = subprocess.run(  # noqa: S603 - fixed argv, shell=False
        [git_executable, *args],
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=_GIT_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        raise SemanticWorkspaceError("FIXTURE_GIT_COMMAND_FAILED")
    return completed.stdout.decode("utf-8", "replace")


@dataclass(frozen=True)
class SemanticTaskWorkspace:
    """One task's fixture content, populated into an I2B-authority-bearing workspace.

    ``workspace`` is the SAME :class:`~qualification.i2b_workspace.QualificationRunWorkspace`
    every broker/runtime request object in this package's compatibility layer
    requires; ``head_before``/``tracked_paths`` are exactly the facts
    :class:`~ar2.fixtures.BuiltFixture` records for every other fixture in
    this repository, so downstream Git observation/classification code can
    be handed the identical shape it already expects.
    """

    workspace: QualificationRunWorkspace = field(repr=False)
    task_id: str
    task_revision: str
    head_before: str
    tracked_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.workspace) is not QualificationRunWorkspace:
            raise SemanticWorkspaceError("NOT_A_QUALIFICATION_RUN_WORKSPACE")
        if not isinstance(self.task_id, str) or not self.task_id:
            raise SemanticWorkspaceError("MALFORMED_TASK_ID")
        if not isinstance(self.task_revision, str) or not self.task_revision:
            raise SemanticWorkspaceError("MALFORMED_TASK_REVISION")
        if not isinstance(self.head_before, str) or not self.head_before:
            raise SemanticWorkspaceError("MALFORMED_HEAD_BEFORE")
        if not isinstance(self.tracked_paths, tuple) or not all(
            isinstance(entry, str) for entry in self.tracked_paths
        ):
            raise SemanticWorkspaceError("MALFORMED_TRACKED_PATHS")

    @property
    def repo_root(self) -> str:
        """The verified repository root -- the ONE workspace identity this task has."""
        return self.workspace.workspace_root


def populate_semantic_task_workspace(
    workspace: QualificationRunWorkspace,
    task: QualificationTask,
    *,
    git_executable: str,
) -> SemanticTaskWorkspace:
    """Populate ``workspace`` (already minted, still empty) with ``task``'s fixture.

    Re-verifies workspace authority immediately before writing (never trusts
    a prior validation), requires the target directory to still be genuinely
    empty (the fresh-root invariant every other fixture builder in this
    codebase already relies on -- this function refuses to double-populate,
    or to populate a directory something else already wrote into), writes
    every ``task.case.files`` entry verbatim as UTF-8 text with LF newlines
    (the identical encoding rule ``ar2.fixtures`` uses for ``str`` bodies),
    and creates exactly one commit with the fixed, non-secret fixture
    identity.
    """
    try:
        verified_repo_root = verify_run_workspace(workspace)
    except WorkspaceAuthorityError as exc:
        raise SemanticWorkspaceError(f"WORKSPACE_UNVERIFIED:{exc.reason_code}") from None

    repo = Path(verified_repo_root)
    if any(repo.iterdir()):
        raise SemanticWorkspaceError("WORKSPACE_NOT_EMPTY")

    files = task.case.files
    for relative in sorted(files):
        body = files[relative]
        if not isinstance(body, str):
            raise SemanticWorkspaceError("FIXTURE_FILE_BODY_NOT_STR")
        target = repo / relative
        if repo not in target.resolve().parents and target.resolve() != repo:
            raise SemanticWorkspaceError("FIXTURE_FILE_PATH_ESCAPES_WORKSPACE")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8", newline="\n")

    environment = _fixture_git_environment()
    identity_flags = [
        "-c", f"user.name={_FIXTURE_GIT_USER_NAME}",
        "-c", f"user.email={_FIXTURE_GIT_USER_EMAIL}",
        "-c", "commit.gpgsign=false",
    ]
    _git(
        git_executable,
        ["init", "-b", "main", "--quiet"],
        cwd=str(repo),
        environment=environment,
    )
    _git(
        git_executable,
        ["add", "--", *sorted(files)],
        cwd=str(repo),
        environment=environment,
    )
    _git(
        git_executable,
        [
            *identity_flags,
            "commit",
            "--quiet",
            "-m",
            f"AIDO qualification semantic fixture {task.task_id}",
        ],
        cwd=str(repo),
        environment=environment,
    )
    head = _git(
        git_executable, ["rev-parse", "HEAD"], cwd=str(repo), environment=environment
    ).strip()
    if not head:
        raise SemanticWorkspaceError("FIXTURE_INITIAL_COMMIT_PRODUCED_NO_HEAD")

    return SemanticTaskWorkspace(
        workspace=workspace,
        task_id=task.task_id,
        task_revision=task.task_revision,
        head_before=head,
        tracked_paths=tuple(sorted(files)),
    )
