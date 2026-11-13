"""AIDO Windows installer and offline install check (PORTABLE-T1).

Stdlib only. Run it with the BASE CPython 3.14 interpreter in isolated mode::

    py -3.14 -I deploy\\windows\\install_aido.py install
    py -3.14 -I deploy\\windows\\install_aido.py check
    py -3.14 -I deploy\\windows\\install_aido.py init-home

Three subcommands, each doing exactly what it says and nothing else:

``install``
    Installs the checkout's committed ``HEAD`` into a NEW, project-isolated
    virtual environment (default ``%LOCALAPPDATA%\\AIDO\\venv``). The code comes
    from ``git archive HEAD`` -- never from the working tree, so an untracked or
    modified file in the checkout cannot be installed -- and the tracked install
    paths must be clean. The build backend and every runtime dependency come
    from the hash-pinned lock files in this directory, wheels only. The AIDO
    wheel is built in a throwaway build environment, so the runtime environment
    contains only the locked runtime packages, pip and AIDO itself. A failed
    install removes the environment it created; a pre-existing target is
    refused, never reused or overwritten. Afterwards it runs ``check``.

``check``
    Read-only integrity check of an installed environment, then an offline
    smoke rehearsal in a throwaway temporary directory (see ``offline_smoke``).
    It reports ``[OK]`` / ``[FIX]`` / ``[INFO]`` lines and exits 1 if anything
    needs fixing.

``init-home``
    Opt-in. Creates the empty per-machine directories ``%LOCALAPPDATA%\\AIDO``
    ``\\config``, ``\\runs`` and ``\\ledger`` if they are missing, never touches
    existing content, and prints the canonical paths to put in a project config.

What this script never does: enable any project gate, write or edit a project
config, read the VALUE of any ``AIDO_*`` or ``GITHUB_TOKEN`` variable (only the
presence of the names, for an informational line), provision a credential,
contact a model or any network host other than the package index pip is
configured for (``install`` only), touch a real target repository, modify
system-wide Python, Git, PATH, accounts or ACLs, or copy authorization or
ledger state from anywhere. The only programs it launches are ``git``, the base
interpreter (to create venvs), the venvs' own ``python.exe`` and pip, and the
installed ``ai-dev-orchestrator.exe`` with offline commands.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

# -- Fixed facts ---------------------------------------------------------------

#: The only interpreter the locks were resolved and the suite was validated on.
SUPPORTED_PYTHON = (3, 14)
PACKAGE_NAME = "ai-dev-orchestrator"
MODULE_NAME = "ai_dev_orchestrator"
CLI_EXE = "ai-dev-orchestrator.exe"
#: The only checkout paths ``git archive`` takes. The locks travel with the code.
ARCHIVED_PATHS = ("pyproject.toml", "README.md", "src", "deploy/windows")
RUNTIME_LOCK = "deploy/windows/requirements-runtime.lock"
BUILD_LOCK = "deploy/windows/requirements-build.lock"
RECEIPT_NAME = "aido-install.json"
RECEIPT_SCHEMA = "aido-install-receipt.v1"
#: Distributions allowed in the runtime venv besides the runtime lock.
UNLOCKED_ALLOWED = ("pip", PACKAGE_NAME)
TASK_COMMANDS = ("task-start", "task-status", "task-continue", "task-doctor")
#: Set in the user's environment, these redirect what the installed CLI imports.
IMPORT_HAZARD_VARS = ("PYTHONPATH", "PYTHONHOME")
#: Names reported by PRESENCE only. Their values are never read.
CREDENTIAL_NAMES = (
    "AIDO_LITELLM_BASE_URL",
    "AIDO_LITELLM_API_KEY",
    "AIDO_LITELLM_DEFAULT_MODEL",
    "AIDO_LITELLM_TIMEOUT_SECONDS",
    "AIDO_LITELLM_MAX_RETRIES",
    "AIDO_VLLM_BASE_URL",
    "AIDO_VLLM_API_KEY",
    "GITHUB_TOKEN",
)
#: A reserved, unresolvable name (RFC 6761). Only ever compared, never contacted.
SMOKE_BASE_URL = "https://aido-offline-smoke.invalid/v1"
SMOKE_TARGET = "hello.txt"
SMOKE_TARGET_BYTES = b"hello from the AIDO offline smoke\n"
PLAN_DRAFT_FILE = "10-plan.draft.json"
TASK_FILE = "task.json"
PIP_COMMON = ("--disable-pip-version-check", "--no-input")
COMMAND_TIMEOUT_SECONDS = 180
PIP_TIMEOUT_SECONDS = 1800


class InstallError(Exception):
    """A refusal or failure, with a message that says what to do."""


@dataclass(frozen=True)
class Line:
    status: str  # "OK" | "FIX" | "INFO"
    text: str

    def render(self) -> str:
        return f"[{self.status}] {self.text}"


def ok(text: str) -> Line:
    return Line("OK", text)


def fix(text: str) -> Line:
    return Line("FIX", text)


def info(text: str) -> Line:
    return Line("INFO", text)


# -- Small helpers -------------------------------------------------------------


def checkout_root() -> str:
    """The checkout this script belongs to: ``<root>/deploy/windows/install_aido.py``."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def is_same_or_under(path: str, root: str) -> bool:
    p = os.path.normcase(os.path.realpath(path))
    r = os.path.normcase(os.path.realpath(root))
    return p == r or p.startswith(r.rstrip("\\/") + os.sep)


def scrubbed_env(environ: Mapping[str, str]) -> dict[str, str]:
    """A child environment without credential names or import-redirecting names.

    Names are dropped by NAME; no value is inspected.
    """
    drop = {name.upper() for name in CREDENTIAL_NAMES + IMPORT_HAZARD_VARS}
    return {
        key: value
        for key, value in environ.items()
        if key.upper() not in drop and not key.upper().startswith("AIDO_")
    }


def default_aido_home(environ: Mapping[str, str]) -> str | None:
    base = environ.get("LOCALAPPDATA")
    return os.path.join(base, "AIDO") if base else None


def venv_python(venv_dir: str) -> str:
    return os.path.join(venv_dir, "Scripts", "python.exe")


def venv_cli(venv_dir: str) -> str:
    return os.path.join(venv_dir, "Scripts", CLI_EXE)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tail(text: str | bytes | None, lines: int = 15) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    return "\n".join(text.strip().splitlines()[-lines:])


Runner = Callable[..., subprocess.CompletedProcess]


def run(
    argv: list[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    capture: bool = True,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    """Launch one fixed argv, never through a shell. Output is bytes.

    Without an explicit ``env`` the child gets :func:`scrubbed_env`, so no
    credential-named variable reaches it. The one deliberate exception is the
    "your current environment" import probe in :func:`check`, which passes the
    caller's environment explicitly because that is what it measures.
    """
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=dict(env) if env is not None else scrubbed_env(os.environ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise InstallError(f"could not launch {os.path.basename(argv[0])!r}: it was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise InstallError(
            f"{os.path.basename(argv[0])!r} did not finish within {int(timeout)} seconds."
        ) from exc


# -- Prerequisites -------------------------------------------------------------


def check_interpreter(
    *,
    version_info: tuple[int, ...],
    is_64bit: bool,
    platform: str,
    prefix: str,
    base_prefix: str,
) -> None:
    """Refuse anything but a BASE 64-bit CPython 3.14 on Windows."""
    if platform != "win32":
        raise InstallError("AIDO's task workflow is Windows-only; this is not Windows.")
    found = ".".join(str(part) for part in version_info[:3])
    wanted = "%d.%d" % SUPPORTED_PYTHON
    if tuple(version_info[:2]) != SUPPORTED_PYTHON or not is_64bit:
        raise InstallError(
            f"this interpreter is Python {found} ({'64' if is_64bit else '32'}-bit). The "
            f"locked dependencies are resolved and validated for 64-bit CPython {wanted} "
            f"only. Install 64-bit Python {wanted} from python.org, then run: "
            f"py -{wanted} -I deploy\\windows\\install_aido.py install"
        )
    if os.path.normcase(os.path.abspath(prefix)) != os.path.normcase(os.path.abspath(base_prefix)):
        raise InstallError(
            "this interpreter belongs to a virtual environment. Run the installer with "
            f"the base interpreter instead: py -{wanted} -I deploy\\windows\\install_aido.py install"
        )


def find_git(which: Callable[[str], str | None] = shutil.which) -> str:
    """Resolve ``git`` as AIDO's writer does: ``PATH`` lookup, absolute regular file."""
    candidate = which("git")
    if not candidate:
        raise InstallError(
            "no 'git' executable is on PATH. Install Git for Windows (git-scm.com) with "
            "its default 'Git from the command line' PATH option, open a NEW window, "
            "and run this again."
        )
    resolved = os.path.abspath(candidate)
    try:
        mode = os.stat(resolved).st_mode
    except OSError as exc:
        raise InstallError("the 'git' found on PATH could not be examined.") from exc
    if not stat.S_ISREG(mode):
        raise InstallError("the 'git' found on PATH is not a regular file.")
    return resolved


def git_text(git: str, root: str, args: list[str], runner: Runner) -> tuple[int, str]:
    result = runner([git, "-C", root, *args])
    # rstrip only: a porcelain status row starts with a significant space.
    return result.returncode, (result.stdout or b"").decode("utf-8", "replace").rstrip()


def read_checkout(root: str, git: str, runner: Runner) -> str:
    """Prove ``root`` is an AIDO Git checkout with a clean install set; return HEAD."""
    pyproject = os.path.join(root, "pyproject.toml")
    try:
        with open(pyproject, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise InstallError(f"no readable pyproject.toml at the checkout root {root!r}.") from exc
    if not re.search(r'(?m)^name\s*=\s*"ai-dev-orchestrator"\s*$', text):
        raise InstallError(f"{root!r} is not an AIDO checkout (pyproject.toml names another project).")
    code, top = git_text(git, root, ["rev-parse", "--show-toplevel"], runner)
    if code != 0 or not top or not same_path(top, root):
        raise InstallError(
            f"{root!r} is not the top of a Git checkout. Obtain AIDO with 'git clone' "
            "(a downloaded ZIP has no commit to pin) and run the installer from that clone."
        )
    code, head = git_text(git, root, ["rev-parse", "--verify", "HEAD^{commit}"], runner)
    if code != 0 or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise InstallError("the checkout has no resolvable HEAD commit.")
    code, dirty = git_text(
        git, root, ["status", "--porcelain", "--untracked-files=no", "--", *ARCHIVED_PATHS], runner
    )
    if code != 0:
        raise InstallError("'git status' failed in the checkout.")
    if dirty:
        raise InstallError(
            "the checkout has uncommitted changes to files the installer installs ("
            + ", ".join(sorted({row[3:] for row in dirty.splitlines()}))
            + "). The installer installs the committed HEAD exactly, so it refuses rather "
            "than install something other than what you see. Commit, stash or discard "
            "them (or check out the commit you want), then run it again."
        )
    return head


# -- Lock files ----------------------------------------------------------------


_LOCK_LINE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)$")
_HASH_RE = re.compile(r"^--hash=sha256:([0-9a-f]{64})$")


def parse_lock(text: str) -> dict[str, tuple[str, tuple[str, ...]]]:
    """Parse a lock written by the maintainer procedure: ``name==ver`` plus sha256 hashes."""
    joined = re.sub(r"\\\r?\n", " ", text)
    pins: dict[str, tuple[str, tuple[str, ...]]] = {}
    for raw in joined.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        match = _LOCK_LINE_RE.match(tokens[0])
        if not match:
            raise InstallError(f"lock line is not an exact 'name==version' pin: {tokens[0]!r}")
        hashes = []
        for token in tokens[1:]:
            hash_match = _HASH_RE.match(token)
            if not hash_match:
                raise InstallError(f"lock entry {tokens[0]!r} has an unsupported option {token!r}")
            hashes.append(hash_match.group(1))
        if not hashes:
            raise InstallError(f"lock entry {tokens[0]!r} carries no sha256 hash")
        name = normalize_name(match.group(1))
        if name in pins:
            raise InstallError(f"lock pins {name!r} twice")
        pins[name] = (match.group(2), tuple(hashes))
    if not pins:
        raise InstallError("lock file pins nothing")
    return pins


def read_lock(path: str) -> dict[str, tuple[str, tuple[str, ...]]]:
    try:
        with open(path, encoding="ascii") as handle:
            return parse_lock(handle.read())
    except (OSError, UnicodeDecodeError) as exc:
        raise InstallError(f"could not read the lock file {path!r}.") from exc


# -- install -------------------------------------------------------------------


def extract_archive(tar_bytes: bytes, destination: str) -> None:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
        archive.extractall(destination, filter="data")


def _pip_or_fail(runner: Runner, argv: list[str], what: str, env: Mapping[str, str]) -> None:
    result = runner(argv, env=env, capture=False, timeout=PIP_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise InstallError(
            f"{what} failed (pip exit {result.returncode}); pip's own message is above. "
            "A network or proxy problem reaching the package index is the usual cause; "
            "pip's own configuration (pip.ini, PIP_INDEX_URL, proxy) is honored, and the "
            "lock's hashes are enforced whatever index serves the files."
        )


def install(
    venv_dir: str,
    *,
    root: str,
    base_python: str,
    runner: Runner = run,
    environ: Mapping[str, str] = os.environ,
    which: Callable[[str], str | None] = shutil.which,
    out: Callable[[str], None] = print,
    now: Callable[[], datetime.datetime] | None = None,
) -> dict:
    """Install ``root``'s HEAD into the new venv ``venv_dir``. Returns the receipt."""
    venv_dir = os.path.abspath(venv_dir)
    git = find_git(which)
    head = read_checkout(root, git, runner)
    if os.path.lexists(venv_dir) and not (os.path.isdir(venv_dir) and not os.listdir(venv_dir)):
        raise InstallError(
            f"{venv_dir!r} already exists. The installer never reuses or overwrites an "
            "environment. To reinstall, delete that directory yourself (it holds only the "
            "installed environment), or pass --venv with a new path."
        )
    child_env = scrubbed_env(environ)
    out(f"Installing AIDO commit {head} into {venv_dir}")
    created = False
    try:
        with tempfile.TemporaryDirectory(prefix="aido-install-", ignore_cleanup_errors=True) as tmp:
            stage = os.path.join(tmp, "source")
            os.mkdir(stage)
            archived = runner(
                [git, "-C", root, "-c", "core.autocrlf=false", "archive", "--format=tar", head, *ARCHIVED_PATHS]
            )
            if archived.returncode != 0:
                raise InstallError("'git archive' of the checkout's HEAD failed: " + tail(archived.stderr))
            extract_archive(archived.stdout, stage)
            runtime_lock = os.path.join(stage, *RUNTIME_LOCK.split("/"))
            build_lock = os.path.join(stage, *BUILD_LOCK.split("/"))
            read_lock(runtime_lock)
            read_lock(build_lock)

            out("[1/5] Building the AIDO wheel in a throwaway build environment")
            build_venv = os.path.join(tmp, "build-venv")
            result = runner([base_python, "-I", "-m", "venv", build_venv], env=child_env)
            if result.returncode != 0:
                raise InstallError("creating the build environment failed: " + tail(result.stderr))
            build_py = venv_python(build_venv)
            _pip_or_fail(
                runner,
                [build_py, "-I", "-m", "pip", "install", *PIP_COMMON, "--require-hashes",
                 "--only-binary", ":all:", "--no-deps", "-r", build_lock],
                "installing the locked build backend",
                child_env,
            )
            wheel_dir = os.path.join(tmp, "wheel")
            _pip_or_fail(
                runner,
                [build_py, "-I", "-m", "pip", "wheel", *PIP_COMMON, "--no-deps",
                 "--no-build-isolation", "--no-index", "-w", wheel_dir, stage],
                "building the AIDO wheel",
                child_env,
            )
            wheels = sorted(
                name for name in os.listdir(wheel_dir)
                if name.startswith(MODULE_NAME + "-") and name.endswith(".whl")
            )
            if len(wheels) != 1:
                raise InstallError(f"expected exactly one AIDO wheel, found {len(wheels)}.")
            wheel = os.path.join(wheel_dir, wheels[0])

            out("[2/5] Creating the runtime environment")
            os.makedirs(os.path.dirname(venv_dir), exist_ok=True)
            created = True
            result = runner([base_python, "-I", "-m", "venv", venv_dir], env=child_env)
            if result.returncode != 0:
                raise InstallError("creating the runtime environment failed: " + tail(result.stderr))
            runtime_py = venv_python(venv_dir)

            out("[3/5] Installing the hash-locked runtime dependencies (wheels only)")
            _pip_or_fail(
                runner,
                [runtime_py, "-I", "-m", "pip", "install", *PIP_COMMON, "--require-hashes",
                 "--only-binary", ":all:", "--no-deps", "-r", runtime_lock],
                "installing the locked runtime dependencies",
                child_env,
            )
            out("[4/5] Installing the AIDO wheel (no index, no dependency resolution)")
            _pip_or_fail(
                runner,
                [runtime_py, "-I", "-m", "pip", "install", *PIP_COMMON, "--no-deps", "--no-index", wheel],
                "installing the AIDO wheel",
                child_env,
            )
            out("[5/5] Checking dependency consistency")
            result = runner([runtime_py, "-I", "-m", "pip", "check", *PIP_COMMON], env=child_env)
            if result.returncode != 0:
                raise InstallError("'pip check' reports broken requirements: " + tail(result.stdout))

            moment = (now() if now is not None else datetime.datetime.now(datetime.timezone.utc))
            receipt = {
                "schema": RECEIPT_SCHEMA,
                "package": PACKAGE_NAME,
                "source_commit": head,
                "source_paths": list(ARCHIVED_PATHS),
                "wheel_file": wheels[0],
                "wheel_sha256": sha256_file(wheel),
                "python_version": ".".join(str(part) for part in sys.version_info[:3]),
                "installed_at": moment.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat(),
            }
            with open(os.path.join(venv_dir, RECEIPT_NAME), "x", encoding="utf-8", newline="\n") as handle:
                json.dump(receipt, handle, indent=2, sort_keys=True)
                handle.write("\n")
    except BaseException:
        if created and os.path.isdir(venv_dir):
            shutil.rmtree(venv_dir, ignore_errors=True)
            out(f"Removed the partially created environment {venv_dir}. Nothing else was changed.")
        raise
    return receipt


# -- check ---------------------------------------------------------------------

#: Executed by the venv's python. Imports AIDO's package (which reads no
#: environment value at import) and reports where everything came from.
PROBE = r"""
import json, os, sys, sysconfig
import importlib.metadata as md
paths = sysconfig.get_paths()
r = {"version": list(sys.version_info[:3]), "x64": sys.maxsize > 2**32,
     "prefix": sys.prefix, "base_prefix": sys.base_prefix,
     "purelib": paths["purelib"], "platlib": paths["platlib"]}
try:
    import ai_dev_orchestrator as m
    r["module_file"] = os.path.abspath(m.__file__)
    r["module_version"] = getattr(m, "__version__", None)
except Exception as e:
    r["import_error"] = type(e).__name__ + ": " + str(e)
r["dists"] = [[d.metadata["Name"], d.version] for d in md.distributions()]
try:
    r["direct_url"] = md.distribution("ai-dev-orchestrator").read_text("direct_url.json")
except Exception:
    r["direct_url"] = None
pth = set()
for root in (paths["purelib"], paths["platlib"]):
    try:
        pth.update(os.path.join(root, n) for n in os.listdir(root) if n.lower().endswith(".pth"))
    except OSError:
        pass
r["pth_files"] = sorted(pth)
print(json.dumps(r))
"""


def run_probe(python: str, *, isolated: bool, env: Mapping[str, str], cwd: str, runner: Runner) -> dict:
    argv = [python, "-I", "-c", PROBE] if isolated else [python, "-c", PROBE]
    result = runner(argv, env=env, cwd=cwd)
    if result.returncode != 0:
        raise InstallError("the environment's python could not run the import probe: " + tail(result.stderr))
    try:
        return json.loads((result.stdout or b"").decode("utf-8"))
    except ValueError as exc:
        raise InstallError("the import probe printed something that is not JSON.") from exc


def evaluate_probe(probe: Mapping, venv_dir: str, lock: Mapping[str, tuple[str, tuple[str, ...]]]) -> list[Line]:
    """Turn the isolated probe into report lines. Pure."""
    lines: list[Line] = []
    version = ".".join(str(part) for part in probe.get("version", []))
    if tuple(probe.get("version", [])[:2]) == SUPPORTED_PYTHON and probe.get("x64") is True:
        lines.append(ok(f"environment python is 64-bit CPython {version}"))
    else:
        lines.append(fix(f"environment python is {version or 'unknown'}, not 64-bit {'%d.%d' % SUPPORTED_PYTHON}: reinstall"))
    if not same_path(str(probe.get("prefix", "")), venv_dir):
        lines.append(fix("the environment's python does not belong to this environment directory"))

    site_dirs = [str(probe.get("purelib", "")), str(probe.get("platlib", ""))]
    module_file = probe.get("module_file")
    if probe.get("import_error"):
        lines.append(fix(f"{MODULE_NAME} cannot be imported: {probe['import_error']}"))
    elif not module_file or not any(
        is_same_or_under(module_file, site) and is_same_or_under(site, venv_dir) for site in site_dirs
    ):
        lines.append(fix(f"{MODULE_NAME} is imported from {module_file!r}, outside this environment's site-packages"))
    else:
        lines.append(ok(f"{MODULE_NAME} is imported from this environment's site-packages ({module_file})"))

    direct_url = probe.get("direct_url")
    editable = False
    if direct_url:
        try:
            editable = bool(json.loads(direct_url).get("dir_info", {}).get("editable"))
        except (ValueError, AttributeError):
            lines.append(fix("the AIDO distribution's direct_url.json is unreadable"))
    if editable:
        lines.append(fix(
            "AIDO is an EDITABLE install: it runs whatever is in the source checkout, not an "
            "installed copy (the HB-1 shadowing hazard). Install a fresh environment with "
            "install_aido.py install"
        ))
    else:
        lines.append(ok("AIDO is a regular (non-editable) install"))

    pth_files = list(probe.get("pth_files") or [])
    if pth_files:
        for path in pth_files:
            lines.append(fix(f"unexpected .pth file {path}: it can add import paths or run code at startup"))
    else:
        lines.append(ok("no .pth import hooks in site-packages"))

    installed: dict[str, list[str]] = {}
    for name, dist_version in probe.get("dists") or []:
        installed.setdefault(normalize_name(str(name)), []).append(str(dist_version))
    problems = []
    for name, versions in sorted(installed.items()):
        if len(versions) > 1:
            problems.append(f"{name} is installed {len(versions)} times")
        elif name in lock:
            if versions[0] != lock[name][0]:
                problems.append(f"{name} {versions[0]} (lock pins {lock[name][0]})")
        elif name not in UNLOCKED_ALLOWED:
            problems.append(f"{name} {versions[0]} is not in the lock")
    for name in sorted(set(lock) - set(installed)):
        problems.append(f"{name} is missing")
    if PACKAGE_NAME not in installed:
        problems.append(f"{PACKAGE_NAME} is missing")
    if problems:
        lines.append(fix("installed packages differ from the runtime lock: " + "; ".join(problems)))
    else:
        lines.append(ok(f"installed packages match the runtime lock exactly ({len(lock)} locked, plus pip and AIDO)"))
    return lines


def read_receipt(venv_dir: str) -> dict | None:
    try:
        with open(os.path.join(venv_dir, RECEIPT_NAME), encoding="utf-8") as handle:
            receipt = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(receipt, dict) or receipt.get("schema") != RECEIPT_SCHEMA:
        return None
    if not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("source_commit", ""))):
        return None
    return receipt


def environment_lines(environ: Mapping[str, str]) -> list[Line]:
    """Report hazards by NAME. No value is read, printed or compared."""
    upper = {key.upper() for key in environ}
    lines = []
    for name in IMPORT_HAZARD_VARS:
        if name in upper:
            lines.append(fix(
                f"{name} is set in this environment; it can make the installed CLI import code "
                f"from elsewhere. Clear it for AIDO windows (CMD: set \"{name}=\")"
            ))
    present = [name for name in CREDENTIAL_NAMES if name in upper]
    if present:
        lines.append(info(
            "set in this environment (values not read): " + ", ".join(present)
            + ". AIDO reads the reviewer/implementer names only inside the gated commands; "
            "this check and the installer never read them"
        ))
    else:
        lines.append(info("no AIDO_* provider variable and no GITHUB_TOKEN is set in this environment"))
    return lines


def check(
    venv_dir: str,
    *,
    root: str,
    runner: Runner = run,
    environ: Mapping[str, str] = os.environ,
    which: Callable[[str], str | None] = shutil.which,
    smoke: bool = True,
    keep_smoke_dir: bool = False,
) -> list[Line]:
    venv_dir = os.path.abspath(venv_dir)
    lines: list[Line] = []
    python = venv_python(venv_dir)
    cli = venv_cli(venv_dir)
    if not os.path.isfile(python) or not os.path.isfile(cli):
        return [fix(
            f"{venv_dir!r} is not an installed AIDO environment (no Scripts\\python.exe or "
            f"Scripts\\{CLI_EXE}). Run install_aido.py install"
        )]
    cfg = os.path.join(venv_dir, "pyvenv.cfg")
    try:
        with open(cfg, encoding="utf-8") as handle:
            cfg_text = handle.read()
    except OSError:
        cfg_text = ""
    if re.search(r"(?mi)^include-system-site-packages\s*=\s*false\s*$", cfg_text):
        lines.append(ok("the environment is isolated from the base interpreter's site-packages"))
    else:
        lines.append(fix("pyvenv.cfg does not say include-system-site-packages = false"))

    git: str | None
    try:
        git = find_git(which)
    except InstallError as exc:
        git = None
        lines.append(fix(str(exc)))
    else:
        result = runner([git, "--version"])
        version = (result.stdout or b"").decode("utf-8", "replace").strip()
        lines.append(ok(f"git on PATH: {git} ({version or 'version unknown'})")
                     if result.returncode == 0 else fix(f"'{git} --version' failed"))

    receipt = read_receipt(venv_dir)
    if receipt is None:
        lines.append(fix(
            f"no valid {RECEIPT_NAME} install receipt: this environment was not made by "
            "install_aido.py install"
        ))
    else:
        lines.append(ok(f"installed from AIDO commit {receipt['source_commit']} at {receipt.get('installed_at')}"))
        head = None
        if git is not None:
            code, text = git_text(git, root, ["rev-parse", "--verify", "HEAD^{commit}"], runner)
            head = text if code == 0 and re.fullmatch(r"[0-9a-f]{40}", text) else None
        if head is None:
            lines.append(info("the checkout's HEAD could not be read; installed commit not compared"))
        elif head != receipt["source_commit"]:
            lines.append(fix(
                f"this checkout is at {head}, but the environment holds {receipt['source_commit']}. "
                "Reinstall into a new directory (or check out the installed commit) so the "
                "documentation you follow matches the code you run"
            ))
        else:
            lines.append(ok("installed commit matches this checkout's HEAD"))

    try:
        lock = read_lock(os.path.join(root, *RUNTIME_LOCK.split("/")))
    except InstallError as exc:
        return lines + [fix(str(exc))]

    child_env = scrubbed_env(environ)
    neutral = tempfile.mkdtemp(prefix="aido-check-")
    try:
        try:
            isolated_probe = run_probe(python, isolated=True, env=child_env, cwd=neutral, runner=runner)
        except InstallError as exc:
            return lines + [fix(str(exc))]
        lines.extend(evaluate_probe(isolated_probe, venv_dir, lock))

        # The same probe in the caller's REAL environment (minus nothing), from a
        # neutral directory: what the installed CLI would actually import.
        try:
            user_probe = run_probe(python, isolated=False, env=dict(environ), cwd=neutral, runner=runner)
        except InstallError as exc:
            lines.append(fix(f"in your current environment: {exc}"))
        else:
            expected = isolated_probe.get("module_file")
            got = user_probe.get("module_file")
            if user_probe.get("import_error") or not got or not expected or not same_path(got, expected):
                lines.append(fix(
                    f"in your current environment {MODULE_NAME} resolves to {got!r} instead of "
                    f"{expected!r}; check PYTHONPATH / PYTHONHOME"
                ))
            else:
                lines.append(ok("your current environment imports the same installed package"))
        lines.extend(environment_lines(environ))

        result = runner([python, "-I", "-m", "pip", "check", *PIP_COMMON], env=child_env, cwd=neutral)
        lines.append(ok("pip check: no broken requirements") if result.returncode == 0
                     else fix("pip check reports broken requirements: " + tail(result.stdout)))

        cli_env = dict(child_env, PYTHONIOENCODING="utf-8", COLUMNS="200")
        result = runner([cli, "version"], env=cli_env, cwd=neutral)
        printed = (result.stdout or b"").decode("utf-8", "replace").strip()
        if result.returncode == 0 and printed and printed == isolated_probe.get("module_version"):
            lines.append(ok(f"{CLI_EXE} runs (version {printed})"))
        else:
            lines.append(fix(f"'{CLI_EXE} version' failed or printed {printed!r}: " + tail(result.stderr)))
        result = runner([cli, "--help"], env=cli_env, cwd=neutral)
        help_text = (result.stdout or b"").decode("utf-8", "replace")
        missing = [name for name in TASK_COMMANDS if name not in help_text]
        if result.returncode == 0 and not missing:
            lines.append(ok("the task coordinator commands are present: " + ", ".join(TASK_COMMANDS)))
        else:
            lines.append(fix("the CLI help does not list: " + ", ".join(missing or TASK_COMMANDS)))
    finally:
        shutil.rmtree(neutral, ignore_errors=True)

    home = default_aido_home(environ)
    if home:
        lines.append(info(f"default task runs root: {os.path.join(home, 'runs')} (task-start creates it)"))
    else:
        lines.append(info("LOCALAPPDATA is not set: pass --runs-root to task-start"))

    if smoke:
        if git is None:
            lines.append(fix("offline smoke skipped: it needs git"))
        else:
            lines.extend(offline_smoke(venv_dir, git=git, runner=runner, environ=environ, keep=keep_smoke_dir))
    return lines


# -- offline smoke ---------------------------------------------------------------


def smoke_config(*, workspace: str, ledger: str, verification_executable: str) -> dict:
    """A throwaway project config for the smoke's own disposable repository.

    Every task gate is open so that ``task-doctor`` and ``task-start`` reach their
    real checks; nothing in the smoke ever writes, verifies, reviews or transmits.
    The endpoint is a reserved ``.invalid`` name, so nothing could reach it.
    YAML is a superset of JSON, so this is written as JSON with the stdlib.
    """
    return {
        "project_id": "aido-offline-smoke",
        "display_name": "AIDO offline install smoke (disposable)",
        "repo": {
            "workspace_path": workspace,
            "github_repo": "aido-smoke/disposable",
            "default_base_branch": "main",
            "branch_prefix": "aido-smoke",
        },
        "workspace_policy": {"deny_outside_workspace": True, "allow_symlinks": False, "max_changed_files": 1},
        "allowed_paths": [SMOKE_TARGET],
        "protected_paths": [],
        "forbidden_paths": [".git", ".git/**"],
        "read_only_workspace_content": {
            "enabled": True, "max_files": 1, "max_file_bytes": 10000,
            "max_total_bytes": 10000, "allow_protected_paths": False,
        },
        "workspace_write": {"enabled": True, "max_file_bytes": 10000},
        "controlled_verification": {
            "enabled": True,
            "executable": verification_executable,
            "args": ["-I", "-c", "pass"],
            "timeout_seconds": 60,
            "max_output_bytes": 10000,
        },
        "controlled_review": {
            "enabled": True,
            "provider": "litellm",
            "model": "aido-offline-smoke-reviewer",
            "endpoint": {"scheme": "https", "host": "aido-offline-smoke.invalid", "port": 443, "base_path": "/v1"},
        },
        "supervised_implementer": {
            "enabled": True,
            "candidate": "SUP-D",
            "provider": "litellm",
            "model": "qwen3.8-27b",
            "live_transmission_enabled": True,
            "attempt_timeout_seconds": 60.0,
            "authorization_ledger_dir": ledger,
        },
    }


def _smoke_git_env(environ: Mapping[str, str]) -> dict[str, str]:
    env = scrubbed_env(environ)
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return env


def offline_smoke(
    venv_dir: str,
    *,
    git: str,
    runner: Runner = run,
    environ: Mapping[str, str] = os.environ,
    keep: bool = False,
) -> list[Line]:
    """Exercise the installed CLI against a disposable one-file repository.

    In one fresh temporary directory: ``git init`` a one-file repository (with
    system and global Git config disabled), write the throwaway config above,
    then run the installed CLI's offline commands -- ``task-doctor`` with the
    target (AIDO's own read-only Git preflight under AIDO's minimal Git
    environment), ``task-start`` (config gates, runs root, run directory, plan
    draft) and ``task-status``. It stops at the plan-approval pause: it never
    fills an approval, never continues a task, and never writes the target.
    The CLI runs with every credential name removed and only the fake
    ``.invalid`` reviewer base URL set, for the doctor to compare.
    """
    tmp = os.path.realpath(tempfile.mkdtemp(prefix="aido-smoke-"))
    lines: list[Line] = []
    try:
        workspace = os.path.join(tmp, "workspace")
        runs = os.path.join(tmp, "runs")
        ledger = os.path.join(tmp, "ledger")
        os.mkdir(ledger)
        git_env = _smoke_git_env(environ)

        def git_ok(*args: str, cwd: str | None = None) -> None:
            result = runner([git, *args], env=git_env, cwd=cwd)
            if result.returncode != 0:
                raise InstallError(f"smoke 'git {args[0]}' failed: " + tail(result.stderr))

        git_ok("-c", "init.defaultBranch=main", "init", "-q", workspace)
        git_ok("-C", workspace, "config", "core.autocrlf", "false")
        with open(os.path.join(workspace, SMOKE_TARGET), "wb") as handle:
            handle.write(SMOKE_TARGET_BYTES)
        git_ok("-C", workspace, "add", "--", SMOKE_TARGET)
        git_ok("-C", workspace, "-c", "user.name=AIDO smoke", "-c", "user.email=smoke@aido.invalid",
               "-c", "commit.gpgsign=false", "commit", "-q", "-m", "AIDO offline smoke baseline")

        config_path = os.path.join(tmp, "smoke-project.yaml")
        config = smoke_config(workspace=workspace, ledger=ledger, verification_executable=venv_python(venv_dir))
        with open(config_path, "x", encoding="utf-8", newline="\n") as handle:
            json.dump(config, handle, indent=2)

        cli = venv_cli(venv_dir)
        cli_env = dict(scrubbed_env(environ), PYTHONIOENCODING="utf-8", COLUMNS="200")
        doctor_env = dict(cli_env, AIDO_LITELLM_BASE_URL=SMOKE_BASE_URL)

        result = runner([cli, "task-doctor", "--project-config", config_path, "--target-path", SMOKE_TARGET],
                        env=doctor_env, cwd=tmp)
        lines.append(evaluate_doctor_output(result))

        result = runner(
            [cli, "task-start", "--project-config", config_path, "--title", "AIDO offline install smoke",
             "--issue", "1", "--target-path", SMOKE_TARGET, "--description",
             "Offline install smoke. Never approved and never continued.", "--runs-root", runs],
            env=cli_env, cwd=tmp,
        )
        run_dirs = sorted(os.listdir(runs)) if os.path.isdir(runs) else []
        if result.returncode != 0 or len(run_dirs) != 1:
            lines.append(fix(f"smoke task-start failed (exit {result.returncode}): " + tail(result.stderr)))
            return lines
        run_dir = os.path.join(runs, run_dirs[0])
        if not all(os.path.isfile(os.path.join(run_dir, name)) for name in (TASK_FILE, PLAN_DRAFT_FILE)):
            lines.append(fix(f"smoke task-start made a run directory without {TASK_FILE} and {PLAN_DRAFT_FILE}"))
            return lines
        lines.append(ok("smoke task-start: config gates, runs root, run directory and plan draft (offline)"))

        result = runner([cli, "task-status", "--run-dir", run_dir], env=cli_env, cwd=tmp)
        status = (result.stdout or b"").decode("utf-8", "replace")
        if result.returncode == 0 and "plan_approval" in status:
            lines.append(ok("smoke task-status: the task waits at the human plan-approval pause"))
        else:
            lines.append(fix(f"smoke task-status did not report plan_approval (exit {result.returncode})"))

        with open(os.path.join(workspace, SMOKE_TARGET), "rb") as handle:
            unchanged = handle.read() == SMOKE_TARGET_BYTES
        status_result = runner([git, "-C", workspace, "status", "--porcelain"], env=git_env)
        clean = status_result.returncode == 0 and not (status_result.stdout or b"").strip()
        if unchanged and clean and not os.listdir(ledger):
            lines.append(ok("smoke left its disposable repository unchanged and its ledger empty; no model was contacted"))
        else:
            lines.append(fix("smoke: the disposable repository or ledger changed, which must never happen"))
    except InstallError as exc:
        lines.append(fix(str(exc)))
    finally:
        if keep:
            lines.append(info(f"smoke directory kept for inspection: {tmp}"))
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    return lines


def evaluate_doctor_output(result: subprocess.CompletedProcess) -> Line:
    """The smoke doctor must report every gate OK except the absent API key name."""
    text = (result.stdout or b"").decode("utf-8", "replace")
    rows = [row.strip() for row in text.splitlines() if row.startswith("[")]
    fixes = [row for row in rows if row.startswith("[FIX]")]
    expected_fix = "[FIX] AIDO_LITELLM_API_KEY is not set"
    needed = (
        "[OK] read_only_workspace_content.enabled",
        "[OK] workspace_write.enabled",
        "[OK] controlled_verification enabled",
        "[OK] supervised_implementer live gate",
        "[OK] controlled_review gate",
        "[OK] controlled_review.endpoint MATCHES AIDO_LITELLM_BASE_URL",
        "[OK] workspace is wholly clean",
    )
    missing = [want for want in needed if not any(row.startswith(want) for row in rows)]
    if result.returncode == 1 and len(fixes) == 1 and fixes[0].startswith(expected_fix) and not missing:
        return ok("smoke task-doctor: every gate and AIDO's read-only Git preflight pass on a disposable repo")
    return fix(
        f"smoke task-doctor did not report the expected gates (exit {result.returncode}); "
        "unexpected or missing: " + "; ".join(missing + [row for row in fixes if not row.startswith(expected_fix)])
        + (" " + tail(result.stderr) if result.stderr else "")
    )


# -- init-home -------------------------------------------------------------------


def init_home(environ: Mapping[str, str], out: Callable[[str], None] = print) -> list[Line]:
    home = default_aido_home(environ)
    if not home:
        raise InstallError("LOCALAPPDATA is not set, so there is no per-user AIDO home to create.")
    home = os.path.abspath(home)
    existing = home
    while not os.path.exists(existing):
        existing = os.path.dirname(existing)
    if os.path.normcase(os.path.realpath(existing)) != os.path.normcase(existing):
        raise InstallError(
            f"{existing!r} passes through a link, junction or non-canonical spelling. AIDO's "
            "ledger must be named by its canonical path; choose directories yourself and put "
            "their canonical paths in the project config."
        )
    lines = []
    for name in ("config", "runs", "ledger"):
        path = os.path.join(home, name)
        if os.path.isdir(path):
            entries = len(os.listdir(path))
            lines.append(info(f"kept existing {path} ({entries} entr{'y' if entries == 1 else 'ies'}; never modified)"))
        elif os.path.lexists(path):
            raise InstallError(f"{path!r} exists and is not a directory; nothing was created.")
        else:
            os.makedirs(path)
            lines.append(ok(f"created empty {path}"))
    lines.append(info(
        "for the project config (forward slashes keep YAML quoting simple): "
        f"authorization_ledger_dir: \"{os.path.join(home, 'ledger').replace(os.sep, '/')}\""
    ))
    lines.append(info(f"put project configs in {os.path.join(home, 'config')}; task runs default to {os.path.join(home, 'runs')}"))
    return lines


# -- CLI -------------------------------------------------------------------------


def _print_lines(lines: Iterable[Line]) -> int:
    lines = list(lines)
    for line in lines:
        print(line.render())
    failed = any(line.status == "FIX" for line in lines)
    print("RESULT: " + ("NEEDS FIXING (see [FIX] lines)" if failed else "OK"))
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    # Line-buffer our own output so it stays in order with pip's, which writes
    # straight to the inherited console or file.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(prog="install_aido.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("install", "install HEAD into a new isolated environment, then check it"),
                       ("check", "offline integrity check and smoke of an installed environment")):
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("--venv", help="environment directory (default %%LOCALAPPDATA%%\\AIDO\\venv)")
        if name == "check":
            cmd.add_argument("--keep-smoke-dir", action="store_true", help="keep the smoke's temporary directory")
    sub.add_parser("init-home", help="create the empty per-user config, runs and ledger directories")
    args = parser.parse_args(argv)

    root = checkout_root()
    try:
        if args.command == "init-home":
            return _print_lines(init_home(os.environ))
        venv_dir = args.venv
        if venv_dir is None:
            home = default_aido_home(os.environ)
            if home is None:
                raise InstallError("LOCALAPPDATA is not set; pass --venv.")
            venv_dir = os.path.join(home, "venv")
        if args.command == "install":
            check_interpreter(
                version_info=tuple(sys.version_info),
                is_64bit=sys.maxsize > 2**32,
                platform=sys.platform,
                prefix=sys.prefix,
                base_prefix=sys.base_prefix,
            )
            install(venv_dir, root=root, base_python=sys.executable)
            print("Installed. Checking the new environment:")
        return _print_lines(check(venv_dir, root=root, keep_smoke_dir=getattr(args, "keep_smoke_dir", False)))
    except InstallError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
