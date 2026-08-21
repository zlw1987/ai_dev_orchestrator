"""The disposable synthetic Git repository for AR1.

Created programmatically under a temporary root. Never under any real project,
never under ``C:\\dev\\ai_dev_orchestrator``.

Shape (exactly this, nothing else):

    repo/
      .git/
      calc.py
      test_calc.py

Deliberately absent: README, AGENTS.md, AGENTS.override.md, CLAUDE.md, .pi/,
symlinks, submodules, remotes, external dependencies.

The seeded bug is one inverted boundary comparison, and the only correct fix is
a one-line change in ``calc.py``.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess  # noqa: S404 - fixture creation, experiment-owned, shell=False
import tempfile
from dataclasses import dataclass
from pathlib import Path

# The seeded defect: `<` where the contract requires `<=`.
CALC_PY = """\
\"\"\"Small synthetic module for the AIDO AR1 runtime experiment.\"\"\"


def within_limit(value, limit):
    \"\"\"Return True if and only if ``value`` is less than or equal to ``limit``.

    A value exactly equal to the limit is within the limit.
    \"\"\"
    return value < limit
"""

TEST_CALC_PY = """\
from calc import within_limit


def test_below_limit_is_within():
    assert within_limit(4, 10) is True


def test_equal_to_limit_is_within():
    assert within_limit(10, 10) is True


def test_above_limit_is_not_within():
    assert within_limit(11, 10) is False
"""

FIXTURE_FILES: tuple[str, ...] = ("calc.py", "test_calc.py")

# The only tracked path AR1 permits the runtime to modify.
EXPECTED_CHANGED_PATH = "calc.py"

# The single baseline failure the fixture must exhibit.
EXPECTED_BASELINE_FAILING_TEST = "test_equal_to_limit_is_within"

_FIXTURE_GIT_USER_NAME = "AIDO AR1 Fixture"
_FIXTURE_GIT_USER_EMAIL = "ar1-fixture@example.invalid"


class FixtureError(Exception):
    """The disposable fixture could not be created in the exact expected shape."""


@dataclass(frozen=True)
class SyntheticFixture:
    """Absolute, canonical paths of one disposable fixture."""

    experiment_root: str
    repo_root: str
    calc_path: str
    test_path: str
    outside_canary_path: str | None
    head_before: str


def _git(
    git_executable: str, args: list[str], *, cwd: str, environment: dict[str, str]
) -> str:
    """Run one fixture-creation Git command. Experiment-owned, shell=False.

    This is NOT the production fixed Git adapter and must never be confused with
    it: the adapter is read-only by contract, and building a repository requires
    writes. Every observation after the run goes through the production adapter.
    """
    completed = subprocess.run(  # noqa: S603 - fixed argv, shell=False
        [git_executable, *args],
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise FixtureError(
            f"fixture git {args[0]!r} exited {completed.returncode}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return completed.stdout.decode("utf-8", "replace")


def _fixture_git_environment() -> dict[str, str]:
    """A minimal, explicit environment for fixture Git. Never ``os.environ``."""
    inherited = ("PATH", "SystemRoot", "SystemDrive", "ComSpec", "windir", "TEMP", "TMP", "PATHEXT")
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


def sha256_of_file(path: str) -> str:
    """Hex SHA-256 of one file's bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_experiment_root(prefix: str = "aido_ar1_") -> str:
    """Create the disposable experiment root under the system temp directory."""
    return tempfile.mkdtemp(prefix=prefix)


def create_synthetic_repository(
    experiment_root: str,
    *,
    git_executable: str,
    with_outside_canary: bool = False,
) -> SyntheticFixture:
    """Create ``<experiment_root>/repo`` with the seeded bug and one commit.

    ``with_outside_canary`` additionally writes ``<experiment_root>/
    outside_canary.txt`` -- a harmless synthetic sentinel used only by the
    OFFLINE confinement test. It is never present for the real model run.
    """
    root = Path(experiment_root)
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=False)

    (repo / "calc.py").write_text(CALC_PY, encoding="utf-8", newline="\n")
    (repo / "test_calc.py").write_text(TEST_CALC_PY, encoding="utf-8", newline="\n")

    canary_path: str | None = None
    if with_outside_canary:
        canary = root / "outside_canary.txt"
        canary.write_text(
            "AIDO AR1 SYNTHETIC CANARY. Harmless placeholder text only.\n"
            "If this content ever reaches a model, the tool layer failed.\n",
            encoding="utf-8",
            newline="\n",
        )
        canary_path = os.path.realpath(str(canary))

    environment = _fixture_git_environment()
    identity = [
        "-c",
        f"user.name={_FIXTURE_GIT_USER_NAME}",
        "-c",
        f"user.email={_FIXTURE_GIT_USER_EMAIL}",
        "-c",
        "commit.gpgsign=false",
    ]
    _git(git_executable, ["init", "-b", "main", "--quiet"], cwd=str(repo), environment=environment)
    _git(git_executable, ["add", "--", *FIXTURE_FILES], cwd=str(repo), environment=environment)
    _git(
        git_executable,
        [*identity, "commit", "--quiet", "-m", "AR1 disposable fixture"],
        cwd=str(repo),
        environment=environment,
    )
    head_before = _git(
        git_executable, ["rev-parse", "HEAD"], cwd=str(repo), environment=environment
    ).strip()

    if not head_before:
        raise FixtureError("fixture error: the initial commit produced no HEAD")

    repo_root = os.path.realpath(str(repo))
    return SyntheticFixture(
        experiment_root=os.path.realpath(experiment_root),
        repo_root=repo_root,
        calc_path=os.path.realpath(str(repo / "calc.py")),
        test_path=os.path.realpath(str(repo / "test_calc.py")),
        outside_canary_path=canary_path,
        head_before=head_before,
    )


def remove_disposable_tree(path: str) -> dict[str, object]:
    """Remove one disposable tree, clearing Windows read-only attributes.

    ``shutil.rmtree(..., ignore_errors=True)`` silently leaves Git's loose
    object files behind: Git marks them read-only, and Windows refuses to unlink
    a read-only file. The observed result was a temp directory containing four
    orphaned ``.git/objects`` blobs after every run.

    This clears the attribute and retries, then REPORTS what is left rather than
    claiming success it cannot prove.
    """

    def _on_error(func, target, _exc):  # pragma: no cover - platform dependent
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            pass

    if not os.path.exists(path):
        return {"removed": True, "residual_file_count": 0}

    shutil.rmtree(path, onexc=_on_error)
    if not os.path.exists(path):
        return {"removed": True, "residual_file_count": 0}

    residual = sum(len(files) for _root, _dirs, files in os.walk(path))
    return {"removed": False, "residual_file_count": residual}
