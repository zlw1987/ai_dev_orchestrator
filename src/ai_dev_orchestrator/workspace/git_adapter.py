"""**Fixed** Git inspection adapter (Phase 5F2C, corrected by 5F2C-FU1).

Phase 5F2A's §26.1 resolved the dirty-tree requirement by proposing a
non-subprocess Git-state reader in its own phase, precisely so that "the writer
needs to know whether the tree is clean" would not become "the orchestrator may
run programs". The post-5F2B roadmap review (§27) kept the *goal* and changed
the *mechanism*: a hand-written ``.git`` parser reimplements subtle logic that
Git already implements correctly, and getting it subtly wrong is itself a safety
problem. So Phase 5F2C ships this instead — an AIDO-owned adapter that runs a
**closed, hard-coded set of Git inspection commands** and nothing else.

The distinction this module exists to hold is worth stating plainly:

    Fixed, AIDO-owned Git plumbing is part of the **writer's own correctness
    contract**. Repository-configured verification (``required_verification``,
    pytest, npm, make) is a **separate executable capability**, and Phase 5F2C
    does not have it.

Phase 5F2C-FU1: the assumption that a fixed argv was sufficient
---------------------------------------------------------------

The original Phase 5F2C reasoning was::

    literal "git" + fixed argv + shell=False  =  no repository-controlled
                                                 command execution

**That reasoning was wrong, and a synthetic repository proves it.** Git clean,
smudge and process *filters* are commands configured through ``filter.<driver>.*``
and selected by ``.gitattributes``. They are run by Git itself, from inside a
perfectly fixed argv. Reproduced against a real ``git`` binary in a temporary
repository, a repository-configured ``filter.evil.clean`` executes during:

- ``git diff -- <path>``; and
- ``git status --porcelain`` — **including on a wholly clean tree**, whenever a
  tracked path's cached stat data is stale (a mere ``touch`` is enough), because
  Git must re-hash the file to prove it is unchanged, and hashing a filtered
  path means running the filter.

That second case is the dangerous one: it fires during the writer's very first
preflight, against a repository the writer would otherwise consider clean.

Two corrections follow, and neither is "reimplement Git":

1. **A configuration gate runs before anything reads working-tree content.** A
   repository whose effective Git configuration can cause filter or helper
   execution — or can *indirect* to configuration that could — is **refused**.
   Phase 5F2C prefers a smaller supported domain over a bigger implementation.
2. **The gate order was changed** so that content-reading operations come last.
   See :func:`ordered_preflight_operations`.

What makes this not an arbitrary command executor
--------------------------------------------------

- The executable is a **fully-qualified absolute path**, resolved once per run
  by :func:`resolve_git_executable` and pinned for every subsequent invocation.
  There is no project config field for it, no model/user/artifact input, and a
  candidate located inside the target workspace is refused.
- Every argv is assembled here from constants. :data:`FIXED_GIT_OPERATIONS`
  enumerates the complete set, and :func:`run_fixed_git_operation` refuses an
  operation name that is not in it.
- **No model, user, config file, or artifact supplies a subcommand, a flag, or a
  shell fragment.** The one variable component in the entire module is a single
  repo-relative path, which reaches Git only after ``--`` (so it can never be
  read as an option) and only after the caller has proved it through the lexical
  write policy and the Phase 5F2B canonical guard.
- ``shell=False`` always. No shell is spawned.
- The environment is a **minimal allowlist**, not a copy of the process
  environment: no ``AIDO_LITELLM_*`` value, no ``GITHUB_TOKEN``, and no
  inherited ``GIT_DIR``/``GIT_WORK_TREE``/``GIT_INDEX_FILE`` can reach the child.
- stdout is **bounded during capture** (see :func:`run_fixed_git_operation`),
  stderr is discarded to ``DEVNULL``, and a watchdog kills the child at the
  timeout. Neither the pager, nor terminal prompting, nor external diff, nor
  textconv, nor fsmonitor is permitted to run — **and none of that is relied on
  to neutralize filters**, which is what the configuration gate is for.

Nothing here writes to a repository. There is no ``add``, ``commit``,
``checkout``, ``restore``, ``reset``, ``stash``, ``clean``, ``branch``,
``fetch``, ``push`` or ``apply`` in the fixed set, and no network operation of
any kind — remote divergence is deliberately **not** a first-writer correctness
prerequisite, so nothing is fetched and nothing is compared against a remote.
"""

from __future__ import annotations

import os
import shutil
import stat as stat_module
import subprocess
import threading
from dataclasses import dataclass

# Top-level Git options applied to every invocation, before the subcommand.
#
# These remain because each is correct on its own terms. **They are not what
# stops a repository-configured filter from running** — that is
# :func:`find_unsupported_config_keys`'s job, and Phase 5F2C-FU1 exists because
# the original code leaned on this list for a guarantee it never provided.
#
# - ``--no-pager`` / ``core.pager=cat``: never hand output to a pager, which
#   would be a second program chosen by repository or user configuration.
# - ``--no-optional-locks``: inspection must not take index locks it does not
#   need, so a read cannot disturb a repository or fight a concurrent process.
# - ``core.fsmonitor=false``: a repository may configure fsmonitor to a *hook
#   program*. Disabling it keeps repository configuration from selecting a
#   process for us.
# - ``diff.external=`` and ``core.quotepath=false``: no externally configured
#   diff program, and raw (unescaped) path bytes so paths are compared as
#   themselves rather than as C-style escapes.
# - ``core.untrackedCache=false``: deterministic untracked-file reporting rather
#   than a cached one.
_GIT_GLOBAL_ARGS: tuple[str, ...] = (
    "--no-pager",
    "--no-optional-locks",
    "-c",
    "core.pager=cat",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.untrackedCache=false",
    "-c",
    "core.quotepath=false",
    "-c",
    "diff.external=",
)

# The complete set of Git operations this project may perform. Each value is the
# exact argv **after** the executable and the global options above. An operation
# whose tuple contains ``None`` takes exactly one repo-relative path,
# substituted after the ``--`` separator and nowhere else.
#
# Every entry is read-only. Adding a mutating one would be a separately
# authorized change, not a configuration tweak.
FIXED_GIT_OPERATIONS: dict[str, tuple[str | None, ...]] = {
    # -- Safe metadata: no working-tree content is read, so no filter can run --
    #
    # Where Git thinks the working tree root is. Compared against the
    # configured workspace root, which must be exactly it.
    "rev_parse_show_toplevel": ("rev-parse", "--show-toplevel"),
    # Whether a valid HEAD exists at all. A repository with no commit has no
    # baseline to recover to, so it is refused.
    "rev_parse_head": ("rev-parse", "--verify", "--quiet", "HEAD"),
    # -- The configuration gate (Phase 5F2C-FU1) ---------------------------
    #
    # The repository's own config file, with ``include.path`` /
    # ``includeIf.*.path`` directives **deliberately not followed**: the
    # decision about whether indirection is permitted must not itself follow
    # the indirection. ``--local`` makes ``--no-includes`` the effective
    # default, and it is passed explicitly so the behavior is visible rather
    # than inherited.
    "config_list_local": (
        "config",
        "--list",
        "--local",
        "-z",
        "--no-includes",
        "--name-only",
    ),
    # Every scope Git would actually apply, so that an execution-capable key
    # inherited from a user's global config (git-lfs's ``filter.lfs.*``, for
    # instance) is caught too. Run only *after* the local scan proved there is
    # no include directive to follow. ``--show-scope`` lets the caller ignore
    # the ``command`` scope, which is this module's own ``-c`` flags.
    "config_list_scoped": ("config", "--list", "-z", "--show-scope", "--name-only"),
    # -- Index inspection: still no working-tree content -------------------
    #
    # The index as stage/mode/blob rows: proves the target is one ordinary
    # stage-0 blob, and reveals gitlink and symlink index modes anywhere.
    "ls_files_stage": ("ls-files", "-z", "--stage"),
    # The index as status tags: the only way to see assume-unchanged (a
    # lowercase tag) and skip-worktree (``S``), both of which make Git's answer
    # about a file stop meaning what it usually means.
    "ls_files_verbose": ("ls-files", "-z", "-v"),
    # -- Working-tree content: MUST run only after the gates above ----------
    #
    # The whole-repository cleanliness question, in one NUL-delimited answer:
    # staged, unstaged, untracked, deleted, renamed, unmerged and dirty
    # submodule state all appear here. This operation re-hashes tracked files
    # whose cached stat data is stale, so it can run a clean filter.
    "status_porcelain": (
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=none",
    ),
    # A human-facing diff for exactly one path, with every configurable
    # transformation disabled. Also reads working-tree content.
    "diff_one_path": (
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--unified=3",
        "--",
        None,
    ),
}

# Operations that may cause Git to read and hash working-tree content, and
# therefore may run a repository-configured clean filter. They are named here so
# the ordering rule is machine-checkable rather than a comment.
CONTENT_READING_OPERATIONS: frozenset[str] = frozenset(
    {"status_porcelain", "diff_one_path"}
)


def ordered_preflight_operations() -> tuple[str, ...]:
    """The mandatory order the writer's Git gates run in (Phase 5F2C-FU1).

    Exposed as data so a test can assert the property rather than trusting a
    comment: **every content-reading operation comes after every gate**, so a
    repository whose configuration can execute a filter, or whose index carries
    a gitlink, is refused before Git is ever asked to look at a working file.

    In particular ``status --ignore-submodules=none`` must not run before the
    index has been proved free of gitlinks, so that the status walk has no
    submodule to descend into.
    """
    return (
        "rev_parse_show_toplevel",
        "rev_parse_head",
        "config_list_local",
        "config_list_scoped",
        "ls_files_stage",
        "ls_files_verbose",
        "status_porcelain",
    )


# -- The Git configuration gate ------------------------------------------------

# Configuration keys whose mere presence makes a repository unsupported.
#
# Two kinds, and the distinction matters:
#
# **Execution-capable** — the value is, or names, a program Git will run:
# ``filter.*`` (clean/smudge/process — the escape this follow-up exists to
# close), external and textconv diff drivers, merge drivers, difftool/mergetool
# commands, hook paths, credential and askpass helpers, SSH and GPG programs,
# pagers, editors, fsmonitor, proxies, and ``uploadpack.packObjectsHook``.
#
# **Indirection-capable** — the value points somewhere else that could carry any
# of the above: ``include.path``, ``includeIf.*.path``, ``core.attributesFile``,
# ``core.excludesFile`` (which can also hide untracked files from the clean
# check), and ``extensions.*`` (``worktreeConfig`` in particular introduces a
# whole additional config file).
#
# Matching is on the **key name only**. No configuration *value* is ever read,
# compared, or reported — a refusal names the key and nothing else.
_UNSUPPORTED_EXACT_KEYS: frozenset[str] = frozenset(
    {
        "include.path",
        "core.fsmonitor",
        "core.fsmonitorhookversion",
        "core.hookspath",
        "core.pager",
        "core.editor",
        "core.sshcommand",
        "core.gitproxy",
        "core.askpass",
        "core.alternaterefscommand",
        "core.attributesfile",
        "core.excludesfile",
        "diff.external",
        "gpg.program",
        "sequence.editor",
        "uploadpack.packobjectshook",
    }
)

_UNSUPPORTED_PREFIXES: tuple[str, ...] = (
    # The filter escape itself: clean, smudge, process, required.
    "filter.",
    # Config indirection.
    "includeif.",
    "extensions.",
    # Program-naming helpers.
    "difftool.",
    "mergetool.",
    "credential.",
    "pager.",
    "alias.",
    "protocol.",
    "ssh.",
)

# Keys matched by shape rather than by a fixed prefix, because the interesting
# part is the *suffix* under an arbitrary subsection name.
_UNSUPPORTED_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("diff.", ".command"),
    ("diff.", ".textconv"),
    ("merge.", ".driver"),
    ("gpg.", ".program"),
    ("remote.", ".uploadpack"),
    ("remote.", ".receivepack"),
    ("remote.", ".proxy"),
    ("remote.", ".vcs"),
)


def find_unsupported_config_keys(keys: tuple[str, ...]) -> tuple[str, ...]:
    """Return the configuration key names that make a repository unsupported.

    Pure function over key **names**. It never sees a configuration value, so it
    cannot leak one, and it makes no judgement about whether a particular value
    would have been harmless: ``filter.lfs.clean`` set to something benign is
    still refused, because deciding *which* command is safe to run is exactly
    the judgement this phase declines to make.

    Duplicates are collapsed and the result is sorted, so a refusal message is
    deterministic.
    """
    unsupported: set[str] = set()
    for key in keys:
        lowered = key.lower()
        if lowered in _UNSUPPORTED_EXACT_KEYS:
            unsupported.add(lowered)
            continue
        if any(lowered.startswith(prefix) for prefix in _UNSUPPORTED_PREFIXES):
            unsupported.add(lowered)
            continue
        for prefix, suffix in _UNSUPPORTED_SUFFIXES:
            if lowered.startswith(prefix) and lowered.endswith(suffix):
                unsupported.add(lowered)
                break
    return tuple(sorted(unsupported))


# How long any one inspection may take before the child is killed. Generous for
# a local repository, and finite so a hung Git cannot hang the writer.
GIT_TIMEOUT_SECONDS = 30

# How much stdout any one inspection may produce. Enforced **during** capture:
# the read loop stops and kills the child once the cap is passed, so an
# unbounded amount of output is never accumulated in memory. A repository whose
# index or status does not fit is refused rather than truncated, because a
# truncated cleanliness answer is worse than no answer.
MAX_GIT_OUTPUT_BYTES = 8 * 1024 * 1024

_READ_CHUNK_BYTES = 64 * 1024

# The only environment variable *names* copied from this process. Git on Windows
# needs a path and a system root to run at all; everything else is either
# supplied fixed below or deliberately absent. In particular ``GIT_DIR``,
# ``GIT_WORK_TREE``, ``GIT_INDEX_FILE``, ``GIT_CONFIG``, ``GIT_SSH*``,
# ``GITHUB_TOKEN`` and every ``AIDO_LITELLM_*`` value are **not** forwarded.
_INHERITED_ENV_NAMES: tuple[str, ...] = (
    "PATH",
    "SystemRoot",
    "SYSTEMROOT",
    "SystemDrive",
    "ComSpec",
    "COMSPEC",
    "windir",
    "TEMP",
    "TMP",
    "PATHEXT",
)

# Fixed environment for every invocation. These suppress the remaining ways a
# repository, a user config, or an interactive terminal could inject behavior.
_FIXED_ENV: dict[str, str] = {
    # Never prompt for credentials, and never run an askpass helper.
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS": "",
    # Never read system-wide config or attributes.
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_ATTR_NOSYSTEM": "1",
    # Never page.
    "GIT_PAGER": "cat",
    "PAGER": "cat",
    # Never take optional locks (belt and braces with --no-optional-locks).
    "GIT_OPTIONAL_LOCKS": "0",
    # Stable, locale-independent messages.
    "LC_ALL": "C",
}


class GitAdapterError(Exception):
    """A fixed Git inspection could not be performed, or its answer was unusable.

    Messages name the *category* of failure and the operation. They never echo
    repository file contents or configuration **values**, and they never carry
    environment values, model data, or credentials.
    """


class GitOperationNotAllowedError(GitAdapterError):
    """An operation name is not in :data:`FIXED_GIT_OPERATIONS`.

    This is the guard that keeps the module from becoming a command executor. It
    is a programming error rather than a user-reachable condition, because no
    caller-supplied string ever reaches it — and it is raised anyway, so that
    the property is testable rather than merely intended.
    """


class GitExecutableError(GitAdapterError):
    """No trusted absolute ``git`` executable could be established.

    Phase 5F2C-FU1. Raised when Git is not on the path at all, when the resolved
    candidate is not an absolute path to an existing regular file, or when it
    lives **inside the target workspace** — which would let the repository under
    edit supply the program that inspects it.
    """


@dataclass(frozen=True)
class GitResult:
    """The bounded outcome of one fixed Git inspection. Data only.

    There is no ``stderr`` field. The child's stderr is sent to ``DEVNULL``:
    it was never used to make a decision, discarding it removes the second pipe
    (which is what makes a single-threaded bounded read of stdout deadlock-free),
    and Git's stderr can contain paths and content that this project's
    no-echo policy would have to strip anyway.
    """

    operation: str
    argv: tuple[str, ...]
    returncode: int
    stdout: str


# -- Executable resolution (Phase 5F2C-FU1) ------------------------------------


def _is_inside(candidate: str, root: str) -> bool:
    """Whether ``candidate`` sits at or under ``root``, by canonical comparison."""
    try:
        candidate_key = os.path.normcase(os.path.realpath(candidate))
        root_key = os.path.normcase(os.path.realpath(root))
    except OSError:
        # Unable to compare means unable to prove separation.
        return True
    if candidate_key == root_key:
        return True
    return candidate_key.startswith(root_key.rstrip("\\/") + os.sep)


def resolve_git_executable(*, workspace_root: str) -> str:
    """Resolve ``git`` to one absolute path, once, before any workspace use.

    Python's own documentation recommends passing a fully-qualified executable
    path for maximum reliability, and the original Phase 5F2C code passed the
    bare string ``"git"`` — which on Windows is resolved by the child-creation
    machinery against a search order this project does not control. For a
    component described as *AIDO-owned fixed Git plumbing*, that is not good
    enough.

    The resolution is deliberately the smallest deterministic one:
    :func:`shutil.which` over this process's own ``PATH``, followed by three
    checks. There is **no** project config field, **no** model/user/artifact
    input, and **no** search of the target workspace.

    Args:
        workspace_root: The target workspace. Used **only** to refuse a
            candidate that lives inside it; it is never searched.

    Returns:
        An absolute path to an existing regular file.

    Raises:
        GitExecutableError: Git was not found, the candidate is not an absolute
            path to a regular file, or it lives inside the target workspace.
    """
    candidate = shutil.which("git")
    if not candidate:
        raise GitExecutableError(
            "git executable error: no 'git' executable could be found. Phase "
            "5F2C requires a local Git working tree and refuses rather than "
            "proceeding without one."
        )

    resolved = os.path.abspath(candidate)
    if not os.path.isabs(resolved):
        raise GitExecutableError(
            "git executable error: the resolved git path is not absolute."
        )
    try:
        info = os.stat(resolved)
    except OSError as exc:
        raise GitExecutableError(
            "git executable error: the resolved git path could not be examined."
        ) from exc
    if not stat_module.S_ISREG(info.st_mode):
        raise GitExecutableError(
            "git executable error: the resolved git path is not a regular file."
        )

    if workspace_root and _is_inside(resolved, workspace_root):
        raise GitExecutableError(
            "git executable error: the resolved git executable is inside the "
            "target workspace. The repository being edited may not supply the "
            "program that inspects it."
        )

    return resolved


def _build_environment() -> dict[str, str]:
    """Build the minimal child environment. Never a copy of ``os.environ``."""
    environment = {
        name: os.environ[name] for name in _INHERITED_ENV_NAMES if name in os.environ
    }
    environment.update(_FIXED_ENV)
    return environment


def build_git_argv(
    operation: str,
    *,
    git_executable: str,
    repo_relative_path: str | None = None,
) -> tuple[str, ...]:
    """Assemble the exact argv for one fixed operation, or refuse.

    Exposed separately from :func:`run_fixed_git_operation` so that tests can
    assert the complete set of command shapes this project can ever produce
    without running anything.

    ``git_executable`` is required and must be absolute — there is no default,
    so no caller can accidentally fall back to the ambient literal ``"git"``.

    Raises:
        GitExecutableError: ``git_executable`` is missing or not absolute.
        GitOperationNotAllowedError: ``operation`` is not a fixed operation, or
            a path was supplied for an operation that takes none (or omitted for
            one that requires it).
    """
    if not git_executable or not os.path.isabs(git_executable):
        raise GitExecutableError(
            "git executable error: a fixed Git operation requires an absolute "
            "git executable path; an unqualified name is never handed to "
            "subprocess."
        )

    template = FIXED_GIT_OPERATIONS.get(operation)
    if template is None:
        raise GitOperationNotAllowedError(
            f"git error: {operation!r} is not one of this project's fixed Git "
            "operations. There is no mechanism for running an arbitrary Git "
            "command."
        )

    takes_path = None in template
    if takes_path and repo_relative_path is None:
        raise GitOperationNotAllowedError(
            f"git error: fixed Git operation {operation!r} requires exactly one "
            "repo-relative path and none was supplied."
        )
    if not takes_path and repo_relative_path is not None:
        raise GitOperationNotAllowedError(
            f"git error: fixed Git operation {operation!r} takes no path "
            "argument, so one may not be supplied."
        )
    if repo_relative_path is not None and (
        not repo_relative_path
        or repo_relative_path.startswith("-")
        or "\x00" in repo_relative_path
    ):
        raise GitOperationNotAllowedError(
            "git error: the repo-relative path supplied to a fixed Git operation "
            "is empty, option-like, or contains a NUL byte."
        )

    argv = [git_executable, *_GIT_GLOBAL_ARGS]
    for item in template:
        argv.append(repo_relative_path if item is None else item)
    return tuple(argv)


def _capture_bounded(
    argv: tuple[str, ...], *, cwd: str, environment: dict[str, str]
) -> tuple[bytes, int, bool, bool]:
    """Run one child and read stdout under a hard byte cap and a watchdog.

    This is the smallest thing that makes the bound real rather than advisory,
    and it is deliberately not a general process framework:

    - stderr goes to ``DEVNULL``, leaving exactly **one** pipe, which is what
      makes a single-threaded read loop deadlock-free;
    - the read loop stops and **kills the child** the moment the cap is passed,
      so at most one chunk beyond the cap is ever held in memory;
    - a ``threading.Timer`` kills the child at the timeout, so the mandatory
      time bound holds even for a child that neither writes nor exits.

    Returns ``(stdout_bytes, returncode, timed_out, overflowed)``.
    """
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed argv, shell=False, no user input
            argv,
            cwd=cwd,
            shell=False,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise GitExecutableError(
            "git executable error: the resolved git executable could not be run."
        ) from exc
    except OSError as exc:
        raise GitAdapterError("git error: the Git child could not be started.") from exc

    timed_out = threading.Event()

    def _kill_on_timeout() -> None:
        timed_out.set()
        try:
            process.kill()
        except OSError:
            pass

    watchdog = threading.Timer(GIT_TIMEOUT_SECONDS, _kill_on_timeout)
    watchdog.daemon = True
    watchdog.start()

    chunks: list[bytes] = []
    total = 0
    overflowed = False
    try:
        stream = process.stdout
        assert stream is not None
        while True:
            chunk = stream.read(_READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_GIT_OUTPUT_BYTES:
                overflowed = True
                try:
                    process.kill()
                except OSError:
                    pass
                break
            chunks.append(chunk)
    finally:
        watchdog.cancel()
        if process.stdout is not None:
            try:
                process.stdout.close()
            except OSError:
                pass
        returncode = process.wait()

    return b"".join(chunks), returncode, timed_out.is_set(), overflowed


def run_fixed_git_operation(
    operation: str,
    *,
    git_executable: str,
    workspace_root: str,
    repo_relative_path: str | None = None,
    allowed_returncodes: tuple[int, ...] = (0,),
) -> GitResult:
    """Run exactly one fixed Git inspection in ``workspace_root``.

    ``git_executable`` must be the absolute path
    :func:`resolve_git_executable` returned, and the caller is expected to reuse
    the same one for the whole run. ``workspace_root`` must already be the
    canonical workspace root the caller proved; this function does not
    canonicalize, and it never chooses a directory of its own.

    No shell is spawned, the environment is the minimal fixed one, **stdout is
    bounded during capture**, stderr is discarded, and a watchdog enforces the
    timeout. Nothing is written, staged, committed, fetched, or pushed by any
    operation in the fixed set.

    Raises:
        GitExecutableError: the executable is unqualified, missing, or unrunnable.
        GitOperationNotAllowedError: the operation is not in the fixed set.
        GitAdapterError: the call timed out, the output exceeded the cap, the
            output was not decodable, or the return code was not one the caller
            declared acceptable.
    """
    argv = build_git_argv(
        operation,
        git_executable=git_executable,
        repo_relative_path=repo_relative_path,
    )

    stdout_bytes, returncode, timed_out, overflowed = _capture_bounded(
        argv, cwd=workspace_root, environment=_build_environment()
    )

    if timed_out:
        raise GitAdapterError(
            f"git error: fixed Git operation {operation!r} exceeded "
            f"{GIT_TIMEOUT_SECONDS}s and the child was killed. Nothing was "
            "written."
        )
    if overflowed:
        raise GitAdapterError(
            f"git error: fixed Git operation {operation!r} exceeded "
            f"{MAX_GIT_OUTPUT_BYTES} bytes of output and the child was killed "
            "mid-stream. It is refused rather than truncated: a truncated "
            "answer about repository state is worse than no answer."
        )

    try:
        stdout = stdout_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GitAdapterError(
            f"git error: the output of fixed Git operation {operation!r} is not "
            "valid UTF-8, so this repository contains names this writer cannot "
            "reason about. Refused."
        ) from exc

    if returncode not in allowed_returncodes:
        raise GitAdapterError(
            f"git error: fixed Git operation {operation!r} exited "
            f"{returncode}. Repository state could not be established, "
            "so nothing was written."
        )

    return GitResult(
        operation=operation,
        argv=argv,
        returncode=returncode,
        stdout=stdout,
    )


# -- Parsed views over the fixed operations ------------------------------------


@dataclass(frozen=True)
class GitIndexEntry:
    """One stage-0-or-not row of ``git ls-files --stage``."""

    mode: str
    blob: str
    stage: int
    path: str


def parse_ls_files_stage(stdout: str) -> tuple[GitIndexEntry, ...]:
    """Parse NUL-delimited ``ls-files --stage`` output, or refuse.

    Each record is ``<mode> <object> <stage>\\t<path>``. A record that does not
    have that shape fails closed rather than being skipped: an index this
    project cannot fully account for is an index it must not write against.
    """
    entries: list[GitIndexEntry] = []
    for record in stdout.split("\0"):
        if not record:
            continue
        meta, separator, path = record.partition("\t")
        if not separator:
            raise GitAdapterError(
                "git error: an index record from 'ls-files --stage' has no path "
                "separator. Refused rather than guessed at."
            )
        parts = meta.split(" ")
        if len(parts) != 3:
            raise GitAdapterError(
                "git error: an index record from 'ls-files --stage' does not have "
                "a mode, an object and a stage. Refused rather than guessed at."
            )
        mode, blob, stage_text = parts
        if not stage_text.isdigit():
            raise GitAdapterError(
                "git error: an index record from 'ls-files --stage' has a "
                "non-numeric stage. Refused rather than guessed at."
            )
        entries.append(
            GitIndexEntry(mode=mode, blob=blob, stage=int(stage_text), path=path)
        )
    return tuple(entries)


def parse_ls_files_verbose(stdout: str) -> tuple[tuple[str, str], ...]:
    """Parse NUL-delimited ``ls-files -v`` output into ``(tag, path)`` pairs.

    The tag is the character Git uses to describe the entry. ``H`` is an
    ordinary cached file; **anything else matters**: ``S`` is skip-worktree,
    ``M`` is unmerged, ``R``/``C``/``K`` describe removal or modification
    states, and a **lowercase** tag means assume-unchanged, which tells Git to
    stop noticing that a file changed. Phase 5F2C refuses every one of them.
    """
    pairs: list[tuple[str, str]] = []
    for record in stdout.split("\0"):
        if not record:
            continue
        if len(record) < 3 or record[1] != " ":
            raise GitAdapterError(
                "git error: an index record from 'ls-files -v' does not begin "
                "with a tag and a space. Refused rather than guessed at."
            )
        pairs.append((record[0], record[2:]))
    return tuple(pairs)


def parse_config_name_only(stdout: str) -> tuple[str, ...]:
    """Parse NUL-delimited ``config --list --name-only`` output into key names.

    ``--name-only`` means **no configuration value is ever read into this
    process**, which is why a refusal can name a key without any risk of
    reporting a secret, a path, or a command line.
    """
    return tuple(record for record in stdout.split("\0") if record)


def parse_config_scoped_name_only(stdout: str) -> tuple[str, ...]:
    """Parse ``config --list --show-scope --name-only -z`` into key names.

    Each record is ``<scope>\\0<key>``, so the fields alternate. Entries in the
    ``command`` scope are **excluded**: those are this module's own ``-c`` flags
    from :data:`_GIT_GLOBAL_ARGS`, and refusing the repository because of them
    would be refusing it for our own hardening.

    A record whose scope is unrecognized fails closed, because a scope this
    project cannot account for might be one it should have refused.
    """
    fields = [record for record in stdout.split("\0")]
    known_scopes = {"system", "global", "local", "worktree", "command", "submodule"}
    keys: list[str] = []
    index = 0
    while index < len(fields):
        scope = fields[index]
        if not scope:
            index += 1
            continue
        if scope not in known_scopes:
            raise GitAdapterError(
                "git error: 'config --list --show-scope' reported an "
                "unrecognized configuration scope. Refused rather than guessed "
                "at."
            )
        if index + 1 >= len(fields):
            raise GitAdapterError(
                "git error: 'config --list --show-scope' produced a scope with "
                "no key. Refused rather than guessed at."
            )
        key = fields[index + 1]
        index += 2
        if scope == "command":
            # This module's own -c hardening flags.
            continue
        if key:
            keys.append(key)
    return tuple(keys)


def parse_status_porcelain(stdout: str) -> tuple[str, ...]:
    """Parse NUL-delimited ``status --porcelain=v1 -z`` into raw records.

    Records are returned as Git wrote them, minus the extra NUL-separated
    "original path" field a rename record carries. Phase 5F2C does not interpret
    the two status characters beyond "there is a record here, so the tree is not
    clean" — for a rename, an unmerged entry, or a dirty submodule, the specific
    letters change nothing about the answer.
    """
    records: list[str] = []
    fields = stdout.split("\0")
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        records.append(field)
        # A rename or copy record is followed by a second NUL-terminated field
        # holding the original path. Consume it so it is not counted twice.
        if len(field) >= 2 and ("R" in field[:2] or "C" in field[:2]):
            index += 1
    return tuple(records)


def status_record_path(record: str) -> str:
    """Return the path from one porcelain-v1 record (``XY <path>``)."""
    if len(record) < 4 or record[2] != " ":
        raise GitAdapterError(
            "git error: a 'status --porcelain=v1 -z' record does not have the "
            "expected 'XY <path>' shape. Refused rather than guessed at."
        )
    return record[3:]
