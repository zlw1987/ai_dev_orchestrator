"""The **one** controlled verification execution (Phase 5F2D).

This module exists to hold a distinction that Phase 5F2C was careful never to
cross, and that Phase 5F2D crosses deliberately, once, in a named place:

    :mod:`ai_dev_orchestrator.workspace.git_adapter` runs a fixed, AIDO-owned,
    read-only inspection set. It is part of the writer's own correctness
    contract, and no repository content selects what it runs.

    **This module launches a project's own program.** That program is chosen by
    trusted project configuration, and what it does once running is *not*
    constrained by AIDO.

Because that second sentence is true, this module refuses to describe itself in
the language of the first. A configured verification process — pytest, typically
— can import arbitrary project modules, execute ``conftest.py``, create and
delete files, open sockets, spawn children, and read whatever environment it is
given. AIDO does not sandbox it, cannot detect most of what it does, and says so.

What is actually controlled here, and it is worth being precise because these are
the only claims the report is allowed to make:

- **Which program.** One absolute path from project config. No ``PATH`` search,
  no default, no fallback, no second candidate, and nothing derived from a model,
  an artifact, a plan, or the CLI.
- **Which arguments.** The exact configured list, used verbatim. Nothing is
  split, quoted, unquoted, expanded, templated, or interpreted.
- **No shell.** ``shell=False``, always. There is no command string anywhere in
  this phase, so there is nothing for a shell to parse: no chaining, no pipeline,
  no redirection, no globbing, no variable expansion.
- **Which directory.** The canonical configured repository root, passed in by the
  caller. There is no working-directory override anywhere in the config.
- **Which environment.** A fixed minimal allowlist, never ``os.environ``. No
  ``AIDO_LITELLM_*``, no ``GITHUB_TOKEN``, no API key, no database or cloud
  credential, and **no project-configurable environment forwarding** — a project
  whose tests need credentials is outside this first supported domain and may
  simply fail. That claim is about the *environment*; the configured ``args`` are
  trusted configuration data used verbatim, and nothing here proves they contain
  no sensitive literal (see :data:`CONFIGURED_ARGS_TRUST_NOTE`).
- **For how long AIDO waits.** A hard wall-clock bound on *this process's* wait,
  corrected in Phase 5F2D-FU1 to be real. At the deadline the direct child is
  killed, whatever was captured is taken, and this function **returns** — it does
  not wait for a descendant that inherited the output pipe. Stated exactly (Phase
  5F2D-FU2): the configured timeout bounds the execution/capture wait, and after
  it AIDO may spend at most :data:`DIRECT_CHILD_REAP_GRACE_SECONDS` reaping the
  direct child's handle. This is a bound on AIDO, **not** a guarantee that the
  verification stopped: descendants are not enumerated, signalled, or tracked,
  and may still be running afterwards.
- **How much output.** A hard byte cap enforced **during** capture; the direct
  child is killed the moment it is passed — genuinely at that moment since Phase
  5F2D-FU2, which replaced a fixed-size buffered read that could sit waiting for
  a buffer to fill long after the cap had been exceeded. The result is marked
  incomplete rather than quietly truncated, and the over-limit bytes are dropped
  rather than retained.
- **How many times.** Exactly once. No retry, no re-run, no second attempt with
  different arguments, and no repair.

Not here, deliberately: no multi-command sequence, no before/after hooks, no
generic ``run(argv)`` helper, no environment forwarding switch, no output
streaming API, and no public entry point that would let a caller name its own
program. The single public function takes an executable and an argv tail that the
caller has already proved came from project config.
"""

from __future__ import annotations

import os
import stat as stat_module
import subprocess
import threading
import time
from dataclasses import dataclass

# The only environment variable *names* copied from this process, and the reason
# each is here: a Windows child needs a system root and a system drive to
# initialize at all, an interpreter needs a temp directory and ``PATHEXT``, and a
# test runner that launches tools needs ``PATH``. Everything else is absent.
#
# Not forwarded, and there is no configuration field that could add them:
# ``AIDO_LITELLM_BASE_URL``, ``AIDO_LITELLM_API_KEY`` and every other ``AIDO_*``
# value; ``GITHUB_TOKEN``; any ``*_API_KEY``, ``*_SECRET``, ``*_TOKEN`` or
# ``*_PASSWORD``; database and cloud credentials; and ``GIT_DIR`` /
# ``GIT_WORK_TREE`` / ``GIT_INDEX_FILE`` / ``GIT_CONFIG``.
INHERITED_ENV_NAMES: tuple[str, ...] = (
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
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
)

# Environment variable name fragments that must never reach the child, asserted
# against the built environment as a belt-and-braces check on the allowlist
# above. If a future edit widens ``INHERITED_ENV_NAMES`` carelessly, this fails
# loudly instead of leaking.
FORBIDDEN_ENV_NAME_FRAGMENTS: tuple[str, ...] = (
    "AIDO_",
    "GITHUB_TOKEN",
    "API_KEY",
    "APIKEY",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "CREDENTIAL",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_CONFIG",
)

# How the environment forwarding policy is described in the result report. It is
# a fixed string because it is a fixed property: no project can change it.
#
# Phase 5F2D-FU1 narrowed this claim. It is a statement about the **environment**
# only: there is no mechanism by which a project config can forward an
# environment variable or a credential to the child. It is deliberately no longer
# phrased as "no secret forwarding exists", because that would also be read as a
# claim about argv — see :data:`CONFIGURED_ARGS_TRUST_NOTE`.
ENVIRONMENT_FORWARDING_POLICY = (
    "minimal fixed allowlist of OS/runtime variables only; there is no "
    "project-configurable environment-variable or credential forwarding "
    "mechanism in this phase"
)

# What is, and is not, established about the configured argument list.
#
# The argv is the configured one used verbatim, which means a project config
# could in principle place a literal credential in `args`. The project-wide rule
# is that secrets live in environment variables and never in files, and args are
# trusted configuration data written by a human — but Phase 5F2D does not *prove*
# that an arbitrary argument string contains no sensitive literal, and it does
# not pretend to. No heuristic argv secret scanner was added, and the configured
# args are never echoed into the report.
CONFIGURED_ARGS_TRUST_NOTE = (
    "The configured args are trusted project-configuration data and are used "
    "verbatim. AIDO does not inspect them and does not prove that an arbitrary "
    "argument string contains no sensitive literal. They are never echoed into "
    "this report."
)

# The largest single read this module will request. It bounds the allocation per
# read; it is deliberately **not** a fixed chunk that must fill before the reader
# can act. See :class:`_BoundedOutputReader` for why that distinction is the
# whole of Phase 5F2D-FU2.
_MAX_READ_REQUEST_BYTES = 64 * 1024


class VerificationExecutableError(Exception):
    """The configured verification executable is not one that may be launched.

    Raised before any child process exists, so a caller that sees this knows
    nothing was started. Messages name the failure category; they never echo an
    environment value or a credential.
    """


class VerificationLaunchError(Exception):
    """The configured verification process could not be started at all.

    Distinct from "it started and failed": a launch failure is an AIDO-side
    refusal, not a verification outcome.
    """


@dataclass(frozen=True)
class VerificationExecution:
    """The bounded outcome of the one verification invocation. Data only.

    ``return_code`` is ``None`` whenever the run did not finish on its own terms
    — a timeout kill or an output-cap kill — because the exit status of a killed
    process is not a verification answer and must not be reported as one.

    ``output_bytes`` may be shorter than what the child would have produced, and
    ``output_complete`` is the field that says so. Nothing downstream is
    permitted to present incomplete output as complete.

    ``direct_child_killed`` means: **AIDO sent at least one kill to the direct
    verification child during this invocation.** Either bound can be the cause —
    the timeout kill happens on the main thread, the output-cap kill happens on
    the reader thread — and both are consulted, so an ordinary overflow run no
    longer reports ``false`` while having killed the child. A child that had
    already exited was not killed, and that stays ``False``.

    It is deliberately **not** named or described as "the verification was
    terminated", because descendants are not tracked, are never signalled, and
    may still be running. See :func:`run_configured_verification`.
    """

    argv: tuple[str, ...]
    started: bool
    completed: bool
    timed_out: bool
    output_limit_exceeded: bool
    return_code: int | None
    output_bytes: bytes
    output_complete: bool
    direct_child_killed: bool = False

    @property
    def passed(self) -> bool:
        """A verification passes only by finishing, in time, in bounds, at zero."""
        return (
            self.completed
            and not self.timed_out
            and not self.output_limit_exceeded
            and self.return_code == 0
        )


# How long the direct child may take to be reaped after a kill, so that the kill
# itself cannot become a second unbounded wait.
#
# Phase 5F2D-FU2 made this public and named it, because it is the difference
# between the configured timeout and the function's true worst-case wait. It is
# a fixed constant: it is not configurable, it is not a second timeout a project
# can set, and it applies only to the **direct** child's process handle.
DIRECT_CHILD_REAP_GRACE_SECONDS = 5.0

# The exact timing contract, carried in the result so it travels with it.
#
# The earlier phrasing — "the function returns at the configured deadline" — was
# not literally true in the worst case, because of the reap grace above. Rather
# than add process management to remove the grace, the claim is made precise.
WAIT_BOUND_POLICY = (
    "The configured timeout bounds the execution and output-capture wait. After "
    "that deadline AIDO sends one kill to the direct child and may spend at most "
    "the fixed direct-child reap grace waiting for that one process handle. It "
    "never waits for descendants, and it never waits for the abandoned output "
    "reader. Worst-case AIDO wait is therefore the configured timeout plus the "
    "reap grace, and nothing else."
)


def _kill_quietly(process: subprocess.Popen) -> bool:
    """Send one kill to the **direct** child. Returns whether one was sent.

    Descendants are not enumerated, signalled, or tracked. Phase 5F2D does not
    manage a process tree and does not claim to.
    """
    try:
        if process.poll() is None:
            process.kill()
            return True
    except OSError:
        pass
    return False


class _BoundedOutputReader:
    """Read one pipe under a byte cap, on a thread that may be **abandoned**.

    Phase 5F2D-FU1 exists because of this class's absence. The original code read
    the pipe on the main thread and relied on a ``threading.Timer`` that killed
    the direct child at the deadline::

        threading.Timer(timeout_seconds, process.kill)   # main thread in read()

    That is not a bound on AIDO's invocation, and a synthetic repository proves
    it. The direct child is explicitly permitted to spawn descendants, and a
    descendant launched with inherited standard handles holds the **write end**
    of the same pipe. Killing or exiting the direct parent does not close the
    handle the descendant owns, so the main thread stays blocked in ``read()``
    until the descendant closes it. Measured against the old algorithm: a 0.5s
    configured timeout with a ~4s descendant returned after ~4s.

    The fix is deliberately narrow. The blocking read moves to a daemon thread,
    and the main thread waits on an :class:`threading.Event` with a deadline. If
    the deadline expires the main thread kills the direct child, takes whatever
    the reader has accumulated so far, and **returns** — leaving the reader
    thread blocked on the inherited pipe rather than waiting for it.

    Two consequences, both stated rather than hidden:

    - **The abandoned reader's own lifetime is not bounded** (corrected in Phase
      5F2D-FU2). Abandoning the daemon reader stops it from extending the *AIDO
      invocation*, which is the property FU1 added — but the thread and the
      pipe's read end may themselves stay alive for as long as a descendant
      retains the inherited write handle, which may be indefinitely. An earlier
      draft of this docstring called that "a bounded, known cost", which
      conflated the two. It is a **documented residual limitation**, and closing
      it would require exactly the process-tree management this phase is not
      authorized to add.
    - **This does not terminate descendants**, and nothing here claims it does.
      The guarantee added by FU1 is only that a descendant cannot keep AIDO's
      reader blocked past the configured deadline.

    Phase 5F2D-FU2: the output cap was not enforced when it was passed
    -----------------------------------------------------------------

    The reader called ``stream.read(64 * 1024)`` and only tested the cap after
    that call returned. ``BufferedReader.read(n)`` blocks until it has ``n``
    bytes or reaches EOF, so a child that emitted *more than the cap* and then
    stopped writing was not detected: the read sat waiting for a 64 KiB buffer
    that would never fill. The documented contract — "the direct child is killed
    the moment the cap is passed" — was therefore false. Measured against a real
    Windows pipe with a child that wrote 5001 bytes and slept 30s::

        read(65536)  -> returned after 30.1 s   (only when the child exited)
        read1(5001)  -> returned after  0.078 s

    The fix is a read *strategy*, not a framework. Each iteration asks for
    ``min(remaining_allowance + 1, 64 KiB)`` bytes via ``read1``, which performs
    **one** underlying read and returns as soon as any data is available rather
    than waiting for the request to be filled. Once fewer than 64 KiB of
    allowance remain the request is exactly ``remaining + 1``, so the arrival of
    that one extra byte is itself the proof of overflow. No asyncio, no
    selectors, no polling loop, no non-blocking mode.

    The excess is **dropped, not stored**: what the result carries is at most the
    configured cap, exactly.

    This is not a general process supervisor: it is private, it reads exactly one
    stream for exactly one invocation, and it has no public entry point.
    """

    def __init__(self, process: subprocess.Popen, *, max_output_bytes: int) -> None:
        self._process = process
        self._max_output_bytes = max_output_bytes
        self._lock = threading.Lock()
        self._chunks: list[bytes] = []
        self._total = 0
        self._overflowed = False
        # Whether *this* thread's overflow path actually sent a kill. The main
        # thread has its own timeout-path answer; the two are combined so the
        # reported field means "AIDO sent at least one kill during this
        # invocation", not "the timeout branch sent one".
        self._killed = False
        self.finished = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        try:
            stream = self._process.stdout
            if stream is None:  # pragma: no cover - stdout is always a pipe here
                return
            while True:
                with self._lock:
                    remaining = self._max_output_bytes - self._total
                # Ask for at most one byte beyond what may be kept. Receiving
                # that byte *is* the proof that the cap was passed, so overflow
                # is detected on the read that carries it rather than on some
                # later read that may never come. The request is additionally
                # capped so a large configured limit does not mean a large
                # allocation per read; that cap is only ever the smaller of the
                # two while overflow is still impossible.
                request = min(remaining + 1, _MAX_READ_REQUEST_BYTES)
                chunk = stream.read1(request)
                if not chunk:
                    break
                overflowed = False
                with self._lock:
                    keep = min(len(chunk), self._max_output_bytes - self._total)
                    if keep:
                        self._chunks.append(chunk[:keep])
                        self._total += keep
                    if len(chunk) > keep:
                        # The over-limit byte(s) are never retained: what is kept
                        # is exactly the configured cap, and the excess is
                        # dropped here.
                        self._overflowed = True
                        overflowed = True
                        # The kill and the record of it happen **inside the same
                        # lock that guards** :meth:`snapshot`, so the two can
                        # never be observed separately. Previously the kill ran
                        # outside the lock and published ``_killed`` afterwards,
                        # which left a real window: the reader could send the
                        # kill, the main thread could then time out, its own kill
                        # would find the child already dead and return False, and
                        # a ``snapshot`` taken before the reader published would
                        # report ``direct_child_killed: false`` for an invocation
                        # in which AIDO really did kill the child.
                        #
                        # Holding the lock across ``process.kill()`` is safe:
                        # nothing in the kill path ever acquires this lock, so
                        # there is no ordering cycle, and the critical section is
                        # one non-blocking system call.
                        killed = _kill_quietly(self._process)
                        self._killed = self._killed or killed
                if overflowed:
                    break
        except (OSError, ValueError):
            # The pipe went away underneath the read. Nothing more to capture,
            # and this is not itself a verification outcome.
            pass
        finally:
            # Reached only when this thread actually finishes. An abandoned
            # reader never gets here, which is exactly why the pipe can stay
            # open after a timeout.
            try:
                if self._process.stdout is not None:
                    self._process.stdout.close()
            except OSError:
                pass
            self.finished.set()

    def snapshot(self) -> tuple[bytes, bool, bool]:
        """Take what has been captured so far, safely, from another thread.

        Returns ``(output_bytes, overflowed, killed_by_this_reader)``. The third
        element exists because the overflow kill happens **here**, on the reader
        thread, while the timeout kill happens on the main thread — reporting
        only the latter made an ordinary overflow run claim no kill was sent when
        one had been.

        The overflow path performs its kill while holding this same lock, so a
        caller can never observe ``overflowed`` without the matching ``killed``.
        """
        with self._lock:
            return b"".join(self._chunks), self._overflowed, self._killed


def build_verification_environment() -> dict[str, str]:
    """Build the minimal child environment. Never a copy of ``os.environ``.

    The allowlist is applied first, and then the result is re-checked against
    :data:`FORBIDDEN_ENV_NAME_FRAGMENTS`, so a name that both lists somehow cover
    is dropped rather than forwarded. Nothing here reads a value in order to
    decide — only names are examined.
    """
    environment = {
        name: os.environ[name] for name in INHERITED_ENV_NAMES if name in os.environ
    }
    return {
        name: value
        for name, value in environment.items()
        if not any(
            fragment in name.upper() for fragment in FORBIDDEN_ENV_NAME_FRAGMENTS
        )
    }


def _is_inside(candidate: str, root: str) -> bool:
    """Whether ``candidate`` sits at or under ``root``, by canonical comparison.

    An error while comparing returns ``True`` — "cannot prove separation" is
    treated as "not separate", because the caller refuses on ``True``.
    """
    try:
        candidate_key = os.path.normcase(os.path.realpath(candidate))
        root_key = os.path.normcase(os.path.realpath(root))
    except OSError:
        return True
    if candidate_key == root_key:
        return True
    return candidate_key.startswith(root_key.rstrip("\\/") + os.sep)


def validate_verification_executable(
    executable: str | None, *, workspace_root: str
) -> str:
    """Prove the configured executable is one this phase may launch, or refuse.

    Four requirements, and the last one is the interesting one:

    1. **Configured.** There is no default, so an absent value is a refusal, not
       a fallback to ``python`` or anything else.
    2. **Absolute.** A bare name would be resolved by the OS against a search
       order this project does not control, which is precisely the ambient
       selection Phase 5F2C-FU1 removed from the Git adapter.
    3. **An existing regular file.** A missing path, a directory, or anything
       that is not a regular file is refused rather than handed to the OS.
    4. **Outside the target workspace.** The repository under verification may
       not supply the program that verifies it. Without this, an ignored
       ``.venv`` or a project-shipped binary becomes a second mutable executable
       target inside the very tree whose state this phase is trying to pin down —
       and the whole point of the pre/post state binding is that the executable's
       identity does not move underneath it. The verified project's **code** is
       still executed from the workspace; that is the capability being
       authorized. The **launcher** comes from outside it.

    Requirement 4 may be revisited if real projects prove that workspace-local
    virtual environments are necessary. It is not solved here.
    """
    if executable is None or not executable.strip():
        raise VerificationExecutableError(
            "verification config error: controlled_verification.executable is "
            "not set. There is no default executable and no PATH lookup, so "
            "nothing was launched."
        )
    if "\x00" in executable:
        raise VerificationExecutableError(
            "verification config error: controlled_verification.executable "
            "contains a NUL byte. Nothing was launched."
        )
    if not os.path.isabs(executable):
        raise VerificationExecutableError(
            "verification config error: controlled_verification.executable must "
            "be an absolute path. A bare name would be resolved by the operating "
            "system against a search order this project does not control. "
            "Nothing was launched."
        )

    try:
        info = os.stat(executable)
    except OSError as exc:
        raise VerificationExecutableError(
            "verification config error: the configured verification executable "
            "does not exist or could not be examined. Nothing was launched."
        ) from exc
    if not stat_module.S_ISREG(info.st_mode):
        raise VerificationExecutableError(
            "verification config error: the configured verification executable "
            "is not a regular file. Nothing was launched."
        )

    if _is_inside(executable, workspace_root):
        raise VerificationExecutableError(
            "verification config error: the configured verification executable "
            "resolves inside the target workspace. The repository being verified "
            "may not supply the program that launches its own verification, "
            "because that would make the executable's identity part of the very "
            "state this phase is pinning down. Nothing was launched."
        )

    return os.path.abspath(executable)


def build_verification_argv(executable: str, args: list[str]) -> tuple[str, ...]:
    """Assemble the exact argv: ``[executable, *args]`` and nothing else.

    Separated from execution so a test can assert the complete shape of what this
    phase can ever launch without launching it. There is no place in this
    function where a plan, a model, an artifact, or a CLI option could contribute
    a token: the two inputs come from validated project config and are used
    verbatim.
    """
    for arg in args:
        if not isinstance(arg, str):
            raise VerificationExecutableError(
                "verification config error: controlled_verification.args must "
                "contain strings only. Nothing was launched."
            )
        if "\x00" in arg:
            raise VerificationExecutableError(
                "verification config error: a controlled_verification.args entry "
                "contains a NUL byte. Nothing was launched."
            )
    return (executable, *args)


def run_configured_verification(
    *,
    executable: str,
    args: list[str],
    cwd: str,
    timeout_seconds: int,
    max_output_bytes: int,
) -> VerificationExecution:
    """Launch the configured verification process **once**, bounded.

    ``executable`` must already have passed
    :func:`validate_verification_executable`, and ``cwd`` must already be the
    canonical workspace root the caller proved. This function canonicalizes
    nothing, searches nothing, and chooses nothing.

    Capture is deliberately a single stream. ``stderr`` is merged into ``stdout``
    so exactly **one** pipe exists, which is what makes a single-threaded bounded
    read loop deadlock-free without building a multi-stream process framework.
    Merging also means a verification's diagnostics are not silently dropped:
    unlike the Git adapter, where stderr was never used for a decision, a test
    runner's failure text is the very thing a human needs to read.

    ``stdin`` is ``DEVNULL``, so a process that prompts gets EOF instead of
    hanging on a terminal that is not there.

    **The timeout bounds AIDO's wait, not the child's life** (Phase 5F2D-FU1).
    The blocking read happens on a daemon thread; this function waits on that
    thread's completion event with a monotonic deadline. When the deadline
    expires it kills the **direct** child, takes whatever was captured, and
    returns — it does not wait for a descendant that inherited the pipe. See
    :class:`_BoundedOutputReader` for why the previous timer-plus-blocking-read
    arrangement did not actually bound anything.

    A run whose pipe is still held open at the deadline is reported as
    ``timed_out`` with incomplete output, even if the direct child had already
    exited. That is the honest answer: AIDO stopped waiting, so it does not have
    the whole output and does not have an exit status it may report.

    Returns a :class:`VerificationExecution` describing what happened. A non-zero
    exit is a **valid verification outcome**, not an error, and is returned
    normally rather than raised.

    Raises:
        VerificationLaunchError: the child could not be started at all.
    """
    argv = build_verification_argv(executable, args)
    environment = build_verification_environment()

    try:
        process = subprocess.Popen(  # noqa: S603 - fixed config argv, shell=False
            argv,
            cwd=cwd,
            shell=False,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        raise VerificationLaunchError(
            "verification launch error: the configured verification process "
            "could not be started. No verification was performed."
        ) from exc

    reader = _BoundedOutputReader(process, max_output_bytes=max_output_bytes)
    reader.start()

    deadline = time.monotonic() + timeout_seconds
    timed_out = not reader.finished.wait(max(0.0, deadline - time.monotonic()))

    return_code: int | None = None
    if not timed_out:
        # The stream is closed, so the direct child is normally already gone.
        # Reaping it is still bounded by the same deadline, so a child that
        # closed its output and then lingered cannot extend the invocation.
        try:
            return_code = process.wait(
                timeout=max(0.0, deadline - time.monotonic())
            )
        except subprocess.TimeoutExpired:
            timed_out = True

    killed_on_timeout = False
    if timed_out:
        killed_on_timeout = _kill_quietly(process)
        try:
            process.wait(timeout=DIRECT_CHILD_REAP_GRACE_SECONDS)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            pass
        return_code = None

    output_bytes, overflowed, killed_on_overflow = reader.snapshot()
    if overflowed:
        # The exit status of a process we killed is not a verification answer.
        return_code = None

    # Either branch may have sent the kill: the timeout kill happens here on the
    # main thread, the overflow kill happens on the reader thread. The reported
    # field means "AIDO sent at least one kill to the direct child during this
    # invocation" — so both are consulted. A child that had already exited was
    # not killed, and that stays honestly False.
    direct_child_killed = killed_on_timeout or killed_on_overflow

    killed_or_abandoned = timed_out or overflowed
    return VerificationExecution(
        argv=argv,
        started=True,
        completed=not killed_or_abandoned,
        timed_out=timed_out,
        output_limit_exceeded=overflowed,
        return_code=return_code,
        output_bytes=output_bytes,
        # A timeout means the stream was abandoned mid-flight, so the captured
        # text is a prefix in that case too — not just on overflow.
        output_complete=not killed_or_abandoned,
        direct_child_killed=direct_child_killed,
    )


def decode_verification_output(data: bytes) -> tuple[str, bool]:
    """Decode captured output for human reading, never for a decision.

    ``errors="replace"`` rather than a refusal: this text is reported to a person
    and nothing branches on it, so a test runner that emits one stray byte in a
    non-UTF-8 encoding should not turn into an orchestrator failure. Whether
    replacement happened is returned so the report can state it.
    """
    text = data.decode("utf-8", errors="replace")
    return text, "�" in text
