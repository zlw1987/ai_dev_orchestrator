"""Alpha-0 operator helper -- Python standard library only.

Used by docs/ALPHA0_CMD_RUNBOOK.md. It is an OPERATOR tool, not AIDO code:
nothing in ai_dev_orchestrator imports it, and it imports nothing from
ai_dev_orchestrator. It is copied into the run directory, hashed, and run from
there, so it always lives outside the target workspace.

What it does: preflight checks, SHA-256 hashing, strict JSON checks, artifact
assembly, and a ledger of exit codes, hashes, HEAD and Git status.

What it never does:
- write, stage, restore, commit or push anything in the target workspace. Its
  only Git use is read-only inspection, run with the same hardened global
  options and minimal environment AIDO's own Git adapter uses;
- run a verification command, a test, a shell, or any project program;
- read, set or print a reviewer credential or endpoint value (it checks
  environment variable NAMES only);
- create, fill in, or "repair" a human approval. Drafts carry an approval stub
  with four EMPTY strings; a human types every value. approval-check only
  compares and reports.

The shipped AIDO commands remain the authority for every artifact. These checks
exist so a mismatch is caught before a human is asked to approve something that
a later AIDO gate would refuse.

Exit status: 0 = the check passed / record written; 1 = STOP (the printed
"A0 RESULT:" line says why); 2 = bad helper usage.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys

# ---------------------------------------------------------------------------
# Constants mirrored from the shipped source at 39d81bac799d. The shipped
# command re-checks every one of these authoritatively; a drift here can only
# make this helper stricter or looser than AIDO, never let AIDO skip a gate.
# ---------------------------------------------------------------------------

VERIFIED_AIDO_COMMIT = "39d81bac799d33cba66c38e09fb6588122d39fb6"

PLAN_APPROVAL_TEXT ="I approve this L1 plan for L2 implementation"  # handoff/models.py
DIFF_APPROVAL_TEXT = "I approve this diff proposal for workspace file editing"  # file_editing/models.py

L1_PLAN_FIELDS = (  # plan/models.py L1Plan
    "issue_number", "repo", "title", "summary", "scope_summary", "non_goals",
    "proposed_steps", "files_likely_to_change", "files_forbidden_or_out_of_scope",
    "required_verification", "risks", "open_questions", "automation_level",
    "requires_human_approval",
)

PROPOSED_CONTENT_KEYS = {  # diff_proposal/generator.py ProposedContentInput
    "schema_version", "mode", "changes", "assumptions", "risks",
    "open_questions", "requires_human_review", "next_authorization_required",
}
PROPOSED_CHANGE_KEYS = {
    "path", "change_type", "content_text", "rationale", "risks",
    "requires_human_review",
}

# workspace/git_adapter.py -- global options, minimal environment, config gate.
GIT_GLOBAL_ARGS = (
    "--no-pager", "--no-optional-locks",
    "-c", "core.pager=cat", "-c", "core.fsmonitor=false",
    "-c", "core.untrackedCache=false", "-c", "core.quotepath=false",
    "-c", "diff.external=",
)
GIT_INHERITED_ENV = (
    "PATH", "SystemRoot", "SYSTEMROOT", "SystemDrive", "ComSpec", "COMSPEC",
    "windir", "TEMP", "TMP", "PATHEXT",
)
GIT_FIXED_ENV = {
    "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": "",
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1",
    "GIT_PAGER": "cat", "PAGER": "cat", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C",
}
UNSUPPORTED_EXACT_KEYS = frozenset({
    "include.path", "core.fsmonitor", "core.fsmonitorhookversion",
    "core.hookspath", "core.pager", "core.editor", "core.sshcommand",
    "core.gitproxy", "core.askpass", "core.alternaterefscommand",
    "core.attributesfile", "core.excludesfile", "diff.external", "gpg.program",
    "sequence.editor", "uploadpack.packobjectshook",
})
UNSUPPORTED_PREFIXES = (
    "filter.", "includeif.", "extensions.", "difftool.", "mergetool.",
    "credential.", "pager.", "alias.", "protocol.", "ssh.",
)
UNSUPPORTED_SUFFIXES = (
    ("diff.", ".command"), ("diff.", ".textconv"), ("merge.", ".driver"),
    ("gpg.", ".program"), ("remote.", ".uploadpack"), ("remote.", ".receivepack"),
    ("remote.", ".proxy"), ("remote.", ".vcs"),
)
ORDINARY_BLOB_MODES = ("100644", "100755")  # file_editing/writer.py

# file_editing/windows_write.py: ARCHIVE | NORMAL | NOT_CONTENT_INDEXED.
SUPPORTED_FILE_ATTRIBUTE_MASK = 0x00000020 | 0x00000080 | 0x00002000

# Reviewer environment NAMES (review/reviewer.py). Checked for presence only.
REVIEWER_ENV_PREFIXES = ("AIDO_LITELLM_", "AIDO_VLLM_")

# Characters str.splitlines() treats as line boundaries in addition to \r and
# \n. The diff generator splits with splitlines(); the writer splits on the
# file's one line ending. A file containing any of these produces a diff the
# writer cannot apply, so it is out of the Alpha-0 domain.
EXTRA_SPLITLINES_CHARS = ("\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", " ", " ")

# Alpha-0 target path shape: what FakeL1Planner's Scope extraction can produce
# as one token, and what the artifact path validators accept.
TARGET_PATH_RE = re.compile(r"^[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)*$")
SHORT_NAME_RE = re.compile(r"^[^/\\.]{1,8}~[0-9]{1,3}(\.[^/\\.]{1,3})?$")

WORKSPACE_PATH_LINE_RE = re.compile(
    r"""^(\s+)workspace_path:\s*(?:"([^"]+)"|'([^']+)'|([^\s#"']+))\s*(?:#.*)?$""",
    re.MULTILINE,
)

STATE_NAME = os.path.join("state", "a0_state.json")
LEDGER_NAME = os.path.join("logs", "a0_ledger.jsonl")


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

class Stop(Exception):
    """A check failed. The message is printed as the STOP reason."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return sha256_bytes(handle.read())


def norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def same_or_under(candidate: str, root: str) -> bool:
    c, r = norm(candidate), norm(root)
    return c == r or c.startswith(r.rstrip(os.sep) + os.sep)


def now_local() -> str:
    # A ledger timestamp, never an approval timestamp.
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_strict_json_object(path: str, label: str) -> dict:
    """Read one strict JSON object the way AIDO's parsers do -- reject, never repair."""
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise Stop(
            f"{label} starts with a UTF-8 byte-order mark. AIDO's strict parsers "
            "reject it. Re-save the file as 'UTF-8' (not 'UTF-8 with BOM')."
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Stop(f"{label} is not valid UTF-8: {exc}") from exc
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise Stop(f"{label} is not exactly one JSON object (nothing may surround it).")
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise Stop(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise Stop(f"{label} is not a JSON object.")
    return value


def write_json(path: str, value: object) -> None:
    """UTF-8, no BOM, LF newlines, ASCII-escaped like AIDO's own output.

    Internal use only, for paths this helper builds itself (preflight and
    inventory). Any path that came from the command line goes through
    write_confined() instead."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.exists(path):
        raise Stop(f"refusing to overwrite an existing file: {path}")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=True))
        handle.write("\n")


def authorize_output(state: dict, path: str, subdir: str, label: str) -> str:
    """Return the absolute path of a helper-created file, or raise Stop.

    The caller does not get to choose where the helper writes. The file must be a
    NEW file placed DIRECTLY inside <run_dir>\\<subdir> -- the runbook's own
    layout -- and that directory must already exist, be the run directory's real
    child (no link or junction on the way), and lie outside the target workspace.
    Called immediately before each write, so authority is checked where the write
    happens and not where the command line was assembled."""
    run_dir, workspace = state["run_dir"], state["workspace"]
    if not isinstance(path, str) or not path.strip() or "\0" in path:
        raise Stop(f"{label}: the output path is blank or malformed.")
    if not os.path.isabs(path):
        raise Stop(f"{label}: the output path must be absolute.")
    allowed = os.path.join(run_dir, subdir)
    if not os.path.isdir(allowed):
        raise Stop(f"{label}: the run directory has no '{subdir}' folder.")
    real_allowed = norm(os.path.realpath(allowed))
    if real_allowed != norm(os.path.join(os.path.realpath(run_dir), subdir)):
        raise Stop(f"{label}: '{subdir}' is (or passes through) a link or junction.")
    parent, name = os.path.split(os.path.abspath(path))
    if not name or name in (".", ".."):
        raise Stop(f"{label}: the output path names no file.")
    if norm(os.path.realpath(parent)) != real_allowed:
        raise Stop(
            f"{label}: output must be a new file directly inside {allowed}; "
            f"{path} is elsewhere."
        )
    if ":" in name or name.endswith((".", " ")):
        raise Stop(f"{label}: the output file name is not an ordinary file name.")
    final = os.path.join(real_allowed, name)
    if same_or_under(final, workspace) or same_or_under(final, os.path.realpath(workspace)):
        raise Stop(f"{label}: the output path is inside the target workspace.")
    if os.path.lexists(final):
        raise Stop(f"{label}: refusing to overwrite an existing file: {final}")
    return os.path.join(allowed, name)


def write_confined(state: dict, path: str, subdir: str, label: str, text: str) -> str:
    """Create ONE new file after re-authorizing its path. Exclusive create."""
    target = authorize_output(state, path, subdir, label)
    with open(target, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return target


def json_text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True) + "\n"


def state_path(run_dir: str) -> str:
    return os.path.join(run_dir, STATE_NAME)


def inventory_path(run_dir: str) -> str:
    return os.path.join(run_dir, "logs", "99_inventory.json")


def is_closed(run_dir: str) -> bool:
    """The inventory is the final record: once it exists the run is closed."""
    return os.path.exists(inventory_path(run_dir))


def load_state(run_dir: str, allow_halted: bool = False) -> dict:
    path = state_path(run_dir)
    if not os.path.exists(path):
        raise Stop("no state file yet: run 'preflight' first.")
    with open(path, "r", encoding="utf-8") as handle:
        state = json.load(handle)
    if norm(state.get("run_dir", "")) != norm(run_dir):
        raise Stop("the state file does not belong to this run directory.")
    if is_closed(run_dir):
        raise Stop("this run is closed (the inventory exists); nothing more can be recorded.")
    if state.get("halted") and not allow_halted:
        h = state["halted"]
        raise Stop(
            f"this run is halted: step {h.get('step')} recorded an UNPROVEN workspace state. "
            "No further workflow step is authorized; only 'inventory' can close the run."
        )
    return state


def save_state(run_dir: str, state: dict) -> None:
    path = state_path(run_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def ledger(run_dir: str, record: dict) -> None:
    path = os.path.join(run_dir, LEDGER_NAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record = {"at": now_local(), **record}
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


IMMUTABLE_PINS = ("config", "helper")  # fixed at preflight; a change needs a new run directory


def pin(state: dict, label: str, path: str) -> str:
    if label in IMMUTABLE_PINS and label in state.get("pinned", {}):
        raise Stop(f"the '{label}' pin is fixed for this run; a changed {label} needs a new run directory.")
    digest = sha256_file(path)
    state.setdefault("pinned", {})[label] = {"path": os.path.abspath(path), "sha256": digest}
    return digest


def check_pins(state: dict) -> list[str]:
    problems = []
    for label, entry in sorted(state.get("pinned", {}).items()):
        path = entry["path"]
        if not os.path.exists(path):
            problems.append(f"pinned file '{label}' is missing: {path}")
            continue
        if sha256_file(path) != entry["sha256"]:
            problems.append(f"pinned file '{label}' changed since it was pinned: {path}")
    return problems


# ---------------------------------------------------------------------------
# Read-only Git, hardened exactly like AIDO's adapter
# ---------------------------------------------------------------------------

def git_environment() -> dict:
    env = {name: os.environ[name] for name in GIT_INHERITED_ENV if name in os.environ}
    env.update(GIT_FIXED_ENV)
    return env


def resolve_git(workspace: str) -> str:
    candidate = shutil.which("git")
    if not candidate:
        raise Stop("no 'git' executable on PATH.")
    resolved = os.path.abspath(candidate)
    if not os.path.isfile(resolved):
        raise Stop("the resolved git path is not a regular file.")
    if same_or_under(resolved, workspace):
        raise Stop("the resolved git executable lives inside the target workspace.")
    return resolved


def git(git_exe: str, workspace: str, *args: str, ok=(0,)) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [git_exe, *GIT_GLOBAL_ARGS, *args],
        cwd=workspace,
        env=git_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
        shell=False,
    )
    if proc.returncode not in ok:
        raise Stop(f"git {args[0]} exited {proc.returncode}.")
    return proc


def git_text(git_exe: str, workspace: str, *args: str, ok=(0,)) -> str:
    return git(git_exe, workspace, *args, ok=ok).stdout.decode("utf-8", "surrogateescape")


def unsupported_config_keys(keys) -> list[str]:
    found = set()
    for key in keys:
        lowered = key.lower()
        if lowered in UNSUPPORTED_EXACT_KEYS:
            found.add(lowered)
        elif any(lowered.startswith(p) for p in UNSUPPORTED_PREFIXES):
            found.add(lowered)
        elif any(lowered.startswith(p) and lowered.endswith(s) for p, s in UNSUPPORTED_SUFFIXES):
            found.add(lowered)
    return sorted(found)


def scoped_keys(stdout: str) -> list[str]:
    fields = stdout.split("\0")
    keys, index = [], 0
    while index < len(fields):
        scope = fields[index]
        if not scope:
            index += 1
            continue
        if index + 1 >= len(fields):
            raise Stop("git config --show-scope produced a scope with no key.")
        key = fields[index + 1]
        index += 2
        if scope == "command":
            continue  # the hardening -c flags above
        if scope not in {"system", "global", "local", "worktree", "submodule"}:
            raise Stop("git config --show-scope reported an unrecognized scope.")
        if key:
            keys.append(key)
    return keys


def status_records(stdout: str) -> list[str]:
    records, fields, index = [], stdout.split("\0"), 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        records.append(field)
        if field[:1] in ("R", "C"):
            index += 1  # skip the rename/copy source path
    return records


def head_of(git_exe: str, workspace: str) -> str | None:
    proc = git(git_exe, workspace, "rev-parse", "--verify", "--quiet", "HEAD", ok=(0, 1))
    value = proc.stdout.decode("ascii", "replace").strip()
    return value if proc.returncode == 0 and value else None


def workspace_status(git_exe: str, workspace: str) -> list[str]:
    return status_records(git_text(
        git_exe, workspace, "status", "--porcelain=v1", "-z",
        "--untracked-files=all", "--ignore-submodules=none",
    ))


# ---------------------------------------------------------------------------
# Text-domain checks shared by preflight and proposed-content
# ---------------------------------------------------------------------------

def line_ending_of(text: str) -> str:
    crlf = text.count("\r\n")
    lone_lf = text.count("\n") - crlf
    lone_cr = text.count("\r") - crlf
    if lone_cr:
        raise Stop("text contains a bare carriage return (only uniform LF or CRLF is supported).")
    if crlf and lone_lf:
        raise Stop("text mixes CRLF and LF line endings.")
    if crlf:
        return "crlf"
    if lone_lf:
        return "lf"
    raise Stop("text has no line terminator at all.")


def check_text_domain(text: str, label: str) -> str:
    if "\x00" in text:
        raise Stop(f"{label} contains a NUL character.")
    for char in EXTRA_SPLITLINES_CHARS:
        if char in text:
            raise Stop(
                f"{label} contains U+{ord(char):04X}, which the diff generator treats as "
                "a line break and the writer does not. Out of the Alpha-0 domain."
            )
    ending = line_ending_of(text)
    terminator = "\r\n" if ending == "crlf" else "\n"
    if not text.endswith(terminator):
        raise Stop(f"{label} does not end with its line terminator.")
    return ending


def check_target_path(target: str) -> None:
    if not TARGET_PATH_RE.match(target):
        raise Stop(
            "target path must be repo-relative, use forward slashes, and contain only "
            "letters, digits, '_', '-', '.' and '/'."
        )
    for component in target.split("/"):
        if component in (".", "..") or component.endswith("."):
            raise Stop("target path has a '.'/'..' component or one ending in a dot.")
        if SHORT_NAME_RE.match(component):
            raise Stop("target path has a component that looks like an 8.3 short name.")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_preflight(a) -> None:
    run_dir, ws, target = a.run_dir, a.workspace, a.target
    checks: list[dict] = []
    record: dict = {}

    def ok(name, detail=""):
        checks.append({"check": name, "pass": True, "detail": detail})

    if os.path.exists(state_path(run_dir)):
        raise Stop("a state file already exists in this run directory; use a fresh run directory.")
    if sys.platform != "win32":
        raise Stop("Alpha-0 runs on Windows only (the writer is Windows-only).")
    ok("platform", sys.platform)

    for label, path in (("workspace", ws), ("run_dir", run_dir), ("config", a.config), ("aido_repo", a.aido_repo)):
        if not os.path.isabs(path):
            raise Stop(f"{label} must be an absolute path.")
    if not os.path.isdir(ws):
        raise Stop("workspace is not an existing directory.")
    if norm(os.path.realpath(ws)) != norm(ws):
        raise Stop("workspace path is (or passes through) a link/junction; use its real path.")
    for label, path in (("run_dir", run_dir), ("config", a.config), ("aido_repo", a.aido_repo)):
        if same_or_under(path, ws):
            raise Stop(f"{label} is inside the target workspace.")
    if same_or_under(ws, run_dir) or same_or_under(ws, a.aido_repo):
        raise Stop("the target workspace is inside the run directory or the AIDO repository.")
    ok("locations", "workspace, run dir, config and AIDO repo are separate")

    # The config's repo.workspace_path must name exactly the workspace being
    # preflighted. Line-oriented extraction (no YAML library in the stdlib),
    # matching the runbook's template; anything else is refused.
    with open(a.config, "r", encoding="utf-8") as handle:
        found = WORKSPACE_PATH_LINE_RE.findall(handle.read())
    if len(found) != 1:
        raise Stop("the config must contain exactly one 'workspace_path:' line (use the runbook template).")
    configured = found[0][1] or found[0][2] or found[0][3]
    if norm(os.path.realpath(configured.strip())) != norm(os.path.realpath(ws)):
        raise Stop("config repo.workspace_path is not exactly the workspace being preflighted.")
    ok("config_workspace_path", "repo.workspace_path names this workspace")

    present = sorted(n for n in os.environ if n.upper().startswith(REVIEWER_ENV_PREFIXES))
    if present:
        raise Stop(
            "reviewer variables are set in this window (names: " + ", ".join(present)
            + "). Steps 0-8 run in a window without them; set them only in the step-9 window."
        )
    ok("reviewer_env_absent", "no AIDO_LITELLM_* / AIDO_VLLM_* names set")

    check_target_path(target)
    ok("target_path_shape", target)

    git_exe = resolve_git(ws)
    ok("git_executable", git_exe)
    record["git_executable"] = git_exe

    toplevel = git_text(git_exe, ws, "rev-parse", "--show-toplevel").strip()
    if not toplevel or norm(os.path.realpath(toplevel)) != norm(os.path.realpath(ws)):
        raise Stop("the Git working-tree top level is not exactly the workspace root.")
    ok("git_toplevel_is_workspace")

    head = head_of(git_exe, ws)
    if not head:
        raise Stop("the repository has no valid HEAD.")
    ok("git_head", head)
    record["baseline_head"] = head

    local_keys = [k for k in git_text(git_exe, ws, "config", "--list", "--local", "-z", "--no-includes", "--name-only").split("\0") if k]
    bad = unsupported_config_keys(local_keys)
    if bad:
        raise Stop("unsupported LOCAL git config keys (AIDO refuses): " + ", ".join(bad))
    bad = unsupported_config_keys(scoped_keys(git_text(git_exe, ws, "config", "--list", "-z", "--show-scope", "--name-only")))
    if bad:
        raise Stop("unsupported git config keys visible to AIDO's Git environment: " + ", ".join(bad))
    ok("git_config_gate", "no execution-capable or indirection keys")

    entries = []
    for rec in git_text(git_exe, ws, "ls-files", "-z", "--stage").split("\0"):
        if not rec:
            continue
        meta, _, path = rec.partition("\t")
        mode, _blob, stage_text = meta.split(" ")
        entries.append((mode, stage_text, path))
    if any(mode == "160000" for mode, _, _ in entries):
        raise Stop("the index contains a submodule (gitlink).")
    if any(stage_text != "0" for _, stage_text, _ in entries):
        raise Stop("the index contains an unmerged entry.")
    matching = [e for e in entries if e[2] == target]
    if len(matching) != 1:
        raise Stop("the target is not tracked as exactly one index entry.")
    if matching[0][0] not in ORDINARY_BLOB_MODES:
        raise Stop(f"the target's index mode {matching[0][0]} is not an ordinary file.")
    ok("git_index", f"{len(entries)} entries, target mode {matching[0][0]}")

    for rec in git_text(git_exe, ws, "ls-files", "-z", "-v").split("\0"):
        if rec and rec[:1] != "H":
            raise Stop("the index has an assume-unchanged, skip-worktree or other non-'H' entry.")
    ok("git_index_tags", "all entries 'H'")

    status = workspace_status(git_exe, ws)
    if status:
        raise Stop(f"the repository is not clean ({len(status)} status records, untracked included).")
    ok("git_clean", "no staged, unstaged or untracked changes")

    full = os.path.join(ws, *target.split("/"))
    info = os.lstat(full)
    if not stat.S_ISREG(info.st_mode):
        raise Stop("the target is not a regular file (or is a symlink).")
    attributes = getattr(info, "st_file_attributes", 0)
    if attributes & ~SUPPORTED_FILE_ATTRIBUTE_MASK:
        raise Stop(f"the target has unsupported Windows attributes (0x{attributes:08x}).")
    if info.st_nlink != 1:
        raise Stop("the target's hard-link count is not 1.")
    if info.st_size > a.max_bytes:
        raise Stop(f"the target is {info.st_size} bytes, above the {a.max_bytes}-byte Alpha-0 cap.")
    ok("target_file", f"{info.st_size} bytes, attributes 0x{attributes:08x}, nlink 1")

    with open(full, "rb") as handle:
        data = handle.read()
    if data.startswith(b"\xef\xbb\xbf"):
        raise Stop("the target starts with a UTF-8 BOM; out of the Alpha-0 domain.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Stop("the target is not valid UTF-8.") from exc
    ending = check_text_domain(text, "the target")
    ok("target_text", f"utf-8, uniform {ending}, terminal newline")

    aido_src = git_text(git_exe, a.aido_repo, "status", "--porcelain=v1", "-z", "--", "src", "pyproject.toml")
    if status_records(aido_src):
        raise Stop("the AIDO repository has uncommitted changes under src/ or pyproject.toml.")
    aido_head = head_of(git_exe, a.aido_repo)
    changed = git(git_exe, a.aido_repo, "diff", "--no-ext-diff", "--no-textconv", "--quiet",
                  a.verified_commit, "HEAD", "--", "src", "pyproject.toml", ok=(0, 1)).returncode
    if changed:
        raise Stop(
            f"AIDO src/ or pyproject.toml differs from {a.verified_commit[:12]}, the commit this "
            "runbook was verified against. Re-verify the runbook before running it."
        )
    ok("aido_source_clean", f"AIDO HEAD {aido_head}; src identical to {a.verified_commit[:12]}")

    state = {
        "run_dir": os.path.abspath(run_dir),
        "workspace": os.path.abspath(ws),
        "target": target,
        "baseline_head": head,
        "pre_image_sha256": sha256_bytes(data),
        "pre_image_bytes": len(data),
        "line_ending": ending,
        "aido_head": aido_head,
        "git_executable": git_exe,
    }
    pin(state, "config", a.config)
    pin(state, "helper", os.path.abspath(__file__))
    save_state(run_dir, state)
    out = {"result": "PASS", "checks": checks, **record,
           "pre_image_sha256": state["pre_image_sha256"], "aido_head": aido_head,
           "config_sha256": state["pinned"]["config"]["sha256"]}
    write_json(os.path.join(run_dir, "logs", "00_preflight.json"), out)
    ledger(run_dir, {"step": "00-preflight", "result": "PASS", "baseline_head": head,
                     "pre_image_sha256": state["pre_image_sha256"],
                     "config_sha256": state["pinned"]["config"]["sha256"], "aido_head": aido_head})
    for c in checks:
        print(f"  PASS  {c['check']:<22} {c['detail']}")
    print(f"A0 RESULT: PREFLIGHT_PASS  HEAD={head}  target_sha256={state['pre_image_sha256']}")


def cmd_snapshot(a) -> None:
    state = load_state(a.run_dir, allow_halted=True)
    if state.get("halted") and a.expect != "none":
        raise Stop(
            f"this run is halted at step {state['halted'].get('step')} (workspace state UNPROVEN); "
            "a later snapshot cannot clear that. Inspect by hand."
        )
    ws, target = state["workspace"], state["target"]
    git_exe = resolve_git(ws)
    if git_exe != state["git_executable"]:
        raise Stop("the git executable on PATH changed since preflight.")
    head = head_of(git_exe, ws)
    status = workspace_status(git_exe, ws)
    full = os.path.join(ws, *target.split("/"))
    target_sha = sha256_file(full) if os.path.isfile(full) else None
    problems = check_pins(state)

    pre, post = state["pre_image_sha256"], state.get("approved_post_image_sha256")
    expect = a.expect
    if expect in ("baseline", "restored"):
        if head != state["baseline_head"]:
            problems.append("HEAD is not the baseline HEAD.")
        if status:
            problems.append(f"working tree is not clean: {status}")
        if target_sha != pre:
            problems.append("target bytes do not match the approved pre-image.")
    elif expect == "written":
        if post is None:
            problems.append("no approved post-image recorded (approval-check --kind diff not run).")
        if head != state["baseline_head"]:
            problems.append("HEAD is not the baseline HEAD.")
        if status != [" M " + target]:
            problems.append(f"Git status is not exactly one unstaged modification of the target: {status}")
        if target_sha != post:
            problems.append("target bytes do not match the approved post-image.")
    elif expect == "committed":
        if post is None:
            problems.append("no approved post-image recorded.")
        if status:
            problems.append(f"working tree is not clean: {status}")
        if head == state["baseline_head"]:
            problems.append("HEAD did not move; no commit was made.")
        parents = git_text(git_exe, ws, "rev-list", "--parents", "-n", "1", "HEAD").split()
        if parents[1:] != [state["baseline_head"]]:
            problems.append("the new commit's only parent is not the baseline HEAD.")
        names = [n for n in git_text(git_exe, ws, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--no-renames", "HEAD").split("\0") if n]
        if names != [target]:
            problems.append(f"the commit does not change exactly the target: {names}")
        blob = git(git_exe, ws, "cat-file", "blob", f"HEAD:{target}").stdout
        if sha256_bytes(blob) != post:
            problems.append("the committed blob does not match the approved post-image.")
        if target_sha != post:
            problems.append("the working-tree target does not match the approved post-image.")

    if expect == "none":
        # Observation only. Nothing was compared with anything, so nothing is
        # proven, and this can never be reported as a success. It also halts the
        # run: no later snapshot may report success after it.
        result = "STOP_STATE_UNPROVEN"
        state["halted"] = {"step": a.step, "rc": a.rc, "at": now_local()}
        save_state(a.run_dir, state)
    else:
        result = "SNAPSHOT_OK" if not problems else "STOP_STATE_MISMATCH"
    state["last_snapshot"] = {"step": a.step, "expect": expect, "result": result}
    save_state(a.run_dir, state)
    ledger(a.run_dir, {"step": a.step, "rc": a.rc, "expect": expect, "result": result,
                       "head": head, "status": status, "target_sha256": target_sha,
                       "problems": problems})
    print(f"  HEAD          {head}")
    print(f"  status        {status if status else 'clean'}")
    print(f"  target sha256 {target_sha}")
    print(f"  rc recorded   {a.rc}")
    for p in problems:
        print(f"  PROBLEM       {p}")
    if expect == "none":
        print("  OBSERVATION ONLY: the values above were recorded, not compared with any expected state.")
        print("  The workspace state is UNPROVEN. This run is halted; inspect the clone by hand.")
        print("  No further workflow step is authorized by this helper.")
    print(f"A0 RESULT: {result}  step={a.step} expect={expect}")
    if problems or expect == "none":
        sys.exit(1)


def cmd_plan_draft(a) -> None:
    state = load_state(a.run_dir)
    generated = read_strict_json_object(a.generated, "generated plan")
    notice = generated.pop("notice", None)
    if not isinstance(notice, str):
        raise Stop("generated plan has no 'notice' string; was it produced by generate-plan?")
    extra = sorted(set(generated) - set(L1_PLAN_FIELDS))
    if extra:
        raise Stop("generated plan has fields L1Plan does not declare: " + ", ".join(extra))
    if generated.get("automation_level") != "L1" or generated.get("requires_human_approval") is not True:
        raise Stop("generated plan is not an unescalated L1 plan.")
    target = state["target"]
    if generated.get("files_likely_to_change") != [target]:
        raise Stop(
            "plan.files_likely_to_change is not exactly [target]. Edit the Scope section of "
            "the issue body so it names only the target path, then regenerate."
        )
    if target in generated.get("files_forbidden_or_out_of_scope", []):
        raise Stop("the target is listed in files_forbidden_or_out_of_scope.")
    draft = {
        # The approval stub is EMPTY. A human types all four values.
        "approval": {"approved_by": "", "approved_at": "", "approval_text": "", "source": ""},
        "plan_provenance": {
            "engine": "deterministic",
            "operation": "generate-plan",
            "real_call": False,
            "model": None,
            "endpoint_host": None,
            "generated_at": None,
            "project_id": a.project_id,
            "repo": generated["repo"],
            "issue_number": generated["issue_number"],
            "title": generated["title"],
        },
        "plan": generated,
        "project_id": a.project_id,
        "repo": generated["repo"],
        "issue_number": generated["issue_number"],
    }
    out = write_confined(state, a.out, "artifacts", "plan-draft --out", json_text(draft))
    digest = sha256_file(out)
    ledger(a.run_dir, {"step": "02-plan-draft", "file": out, "sha256": digest})
    print(f"  draft written {out}")
    print(f"  sha256        {digest}")
    print("A0 RESULT: PLAN_DRAFT_READY (approval stub is empty; a human must fill it)")


def cmd_approval_check(a) -> None:
    state = load_state(a.run_dir)
    required = PLAN_APPROVAL_TEXT if a.kind == "plan" else DIFF_APPROVAL_TEXT
    draft = read_strict_json_object(a.draft, "draft")
    approved = read_strict_json_object(a.approved, "approved artifact")
    if norm(a.draft) == norm(a.approved):
        raise Stop("the approved artifact must be a separate file from the draft.")
    approval = approved.get("approval")
    if not isinstance(approval, dict) or set(approval) != {"approved_by", "approved_at", "approval_text", "source"}:
        raise Stop("approval block must have exactly approved_by, approved_at, approval_text, source.")
    for key in ("approved_by", "approved_at", "approval_text", "source"):
        if not isinstance(approval[key], str) or not approval[key].strip():
            raise Stop(f"approval.{key} is empty; a human must type it.")
    if approval["approval_text"] != required:
        raise Stop("approval.approval_text is not the exact required sentence for this approval.")
    if approval["source"] != "manual":
        raise Stop("approval.source must be exactly 'manual'.")
    try:
        _dt.datetime.fromisoformat(approval["approved_at"])
    except ValueError as exc:
        raise Stop("approval.approved_at is not an ISO-8601 timestamp.") from exc
    rest_draft = {k: v for k, v in draft.items() if k != "approval"}
    rest_approved = {k: v for k, v in approved.items() if k != "approval"}
    if rest_draft != rest_approved:
        raise Stop("the approved file differs from the draft outside the approval block.")
    label = "approved_plan" if a.kind == "plan" else "approved_diff"
    digest = pin(state, label, a.approved)
    if a.kind == "diff":
        changes = approved["diff_proposal"]["changes"]
        post = changes[0]["post_image_sha256"]
        if post != state.get("expected_post_image_sha256"):
            raise Stop("approved post_image_sha256 differs from the proposed content's SHA-256.")
        state["approved_post_image_sha256"] = post
    save_state(a.run_dir, state)
    ledger(a.run_dir, {"step": f"approval-check-{a.kind}", "file": os.path.abspath(a.approved),
                       "sha256": digest, "approved_by": approval["approved_by"],
                       "approved_at": approval["approved_at"]})
    print(f"  approved file {a.approved}")
    print(f"  sha256        {digest}  (pinned)")
    print(f"A0 RESULT: APPROVAL_CONSISTENT kind={a.kind}")


def cmd_packet_check(a) -> None:
    state = load_state(a.run_dir)
    packet = read_strict_json_object(a.packet, "workspace-content packet")
    if packet.get("mode") != "l2-read-workspace-files":
        raise Stop("packet mode is not l2-read-workspace-files.")
    items = packet.get("workspace_content", {}).get("items", [])
    if len(items) != 1:
        raise Stop(f"packet has {len(items)} items; Alpha-0 requires exactly 1.")
    item = items[0]
    expected = {"original_plan_path": state["target"], "canonical_relative_path": state["target"],
                "status": "read", "kind": "file", "encoding": "utf-8", "redacted": False}
    for key, value in expected.items():
        if item.get(key) != value:
            raise Stop(f"packet item {key} is {item.get(key)!r}, expected {value!r}.")
    content = item.get("content_text")
    if not isinstance(content, str) or sha256_bytes(content.encode("utf-8")) != state["pre_image_sha256"]:
        raise Stop("packet content does not hash to the preflight pre-image.")
    digest = pin(state, "workspace_packet", a.packet)
    save_state(a.run_dir, state)
    ledger(a.run_dir, {"step": "03-packet-check", "file": os.path.abspath(a.packet), "sha256": digest})
    print(f"A0 RESULT: PACKET_OK  content matches pre-image {state['pre_image_sha256']}")


def cmd_proposed_assemble(a) -> None:
    state = load_state(a.run_dir)
    for path in (a.final_file, a.rationale_file):
        if same_or_under(path, state["workspace"]):
            raise Stop(f"{path} is inside the target workspace.")
    authorize_output(state, a.out, "inputs", "proposed-assemble --out")  # early refusal; re-checked at write
    with open(a.final_file, "rb") as handle:
        raw = handle.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise Stop("the final-content file starts with a UTF-8 BOM.")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Stop("the final-content file is not valid UTF-8.") from exc
    with open(a.rationale_file, "r", encoding="utf-8-sig") as handle:
        rationale = handle.read().strip()
    if not rationale:
        raise Stop("the rationale file is empty.")
    proposed = {
        "schema_version": "proposed-content.v1",
        "mode": "proposal-only",
        "changes": [{
            "path": state["target"],
            "change_type": "modify",
            "content_text": content,
            "rationale": rationale,
            "risks": [],
            "requires_human_review": True,
        }],
        "assumptions": [],
        "risks": [],
        "open_questions": [],
        "requires_human_review": True,
        "next_authorization_required": "Human approval of the generated diff proposal is required before any write.",
    }
    out = write_confined(state, a.out, "inputs", "proposed-assemble --out", json_text(proposed))
    ledger(a.run_dir, {"step": "04-proposed-assemble", "file": out,
                       "sha256": sha256_file(out), "final_file_sha256": sha256_bytes(raw)})
    print(f"A0 RESULT: PROPOSED_CONTENT_ASSEMBLED {out} (run 'proposed-check' next)")


def cmd_proposed_check(a) -> None:
    state = load_state(a.run_dir)
    if same_or_under(a.proposed, state["workspace"]):
        raise Stop("the proposed-content file is inside the target workspace.")
    doc = read_strict_json_object(a.proposed, "proposed-content")
    if set(doc) - PROPOSED_CONTENT_KEYS:
        raise Stop("proposed-content has unknown keys: " + ", ".join(sorted(set(doc) - PROPOSED_CONTENT_KEYS)))
    if doc.get("schema_version") != "proposed-content.v1" or doc.get("mode") != "proposal-only":
        raise Stop("proposed-content schema_version/mode is not proposed-content.v1 / proposal-only.")
    if doc.get("requires_human_review") is not True:
        raise Stop("proposed-content requires_human_review must be true.")
    nar = doc.get("next_authorization_required")
    if not isinstance(nar, str) or not nar.strip():
        raise Stop("proposed-content next_authorization_required must be a non-blank string.")
    changes = doc.get("changes")
    if not isinstance(changes, list) or len(changes) != 1:
        raise Stop("proposed-content must carry exactly one change for Alpha-0.")
    change = changes[0]
    if set(change) - PROPOSED_CHANGE_KEYS:
        raise Stop("proposed change has unknown keys: " + ", ".join(sorted(set(change) - PROPOSED_CHANGE_KEYS)))
    if change.get("path") != state["target"] or change.get("change_type") != "modify":
        raise Stop("the change must be a 'modify' of exactly the target path.")
    if change.get("requires_human_review") is not True:
        raise Stop("the change's requires_human_review must be true.")
    if not isinstance(change.get("rationale"), str) or not change["rationale"].strip():
        raise Stop("the change's rationale must be non-blank.")
    content = change.get("content_text")
    if not isinstance(content, str):
        raise Stop("content_text must be a string.")
    ending = check_text_domain(content, "proposed content_text")
    if ending != state["line_ending"]:
        raise Stop(f"proposed content uses {ending} but the target uses {state['line_ending']}; the writer would refuse.")
    post = sha256_bytes(content.encode("utf-8"))
    if post == state["pre_image_sha256"]:
        raise Stop("proposed content is identical to the current file; there is nothing to change.")
    if len(content.encode("utf-8")) > a.max_bytes:
        raise Stop(f"proposed content exceeds the {a.max_bytes}-byte Alpha-0 cap.")
    state["expected_post_image_sha256"] = post
    digest = pin(state, "proposed_content", a.proposed)
    save_state(a.run_dir, state)
    ledger(a.run_dir, {"step": "04-proposed-check", "file": os.path.abspath(a.proposed),
                       "sha256": digest, "expected_post_image_sha256": post})
    print(f"A0 RESULT: PROPOSED_CONTENT_OK  expected post-image sha256 {post}")


def cmd_diff_draft(a) -> None:
    state = load_state(a.run_dir)
    proposal = read_strict_json_object(a.proposal, "diff proposal")
    if proposal.get("schema_version") != "diff-proposal.v2":
        raise Stop("diff proposal schema_version is not diff-proposal.v2.")
    changes = proposal.get("changes", [])
    if len(changes) != 1 or proposal.get("omitted_paths"):
        raise Stop("the diff proposal must carry exactly one change and no omitted paths.")
    change = changes[0]
    if change.get("path") != state["target"] or change.get("change_type") != "modify":
        raise Stop("the diff proposal's change is not a 'modify' of the target.")
    if change.get("pre_image_sha256") != state["pre_image_sha256"]:
        raise Stop("the diff's pre_image_sha256 is not the preflight pre-image.")
    if change.get("post_image_sha256") != state.get("expected_post_image_sha256"):
        raise Stop("the diff's post_image_sha256 is not the proposed content's SHA-256.")
    provenance = proposal["provenance"]
    # Both outputs are authorized before either is written, so a refusal of the
    # second cannot leave the first behind.
    authorize_output(state, a.diff_out, "review", "diff-draft --diff-out")
    authorize_output(state, a.out, "artifacts", "diff-draft --out")
    if norm(a.diff_out) == norm(a.out):
        raise Stop("diff-draft --diff-out and --out are the same file.")
    pin(state, "diff_proposal", a.proposal)
    diff_out = write_confined(state, a.diff_out, "review", "diff-draft --diff-out",
                              change["unified_diff"] + "\n")
    draft = {
        # The approval stub is EMPTY. A human types all four values.
        "approval": {"approved_by": "", "approved_at": "", "approval_text": "", "source": ""},
        "schema_version": "approved-diff-proposal.v2",
        "mode": "file-edit-approval-only",
        "diff_proposal": proposal,
        "project_id": provenance["project_id"],
        "repo": provenance["repo"],
        "issue_number": provenance["issue_number"],
        "title": provenance["title"],
        "next_authorization_required": (
            "l2-apply-approved-file-edit with explicit --apply-approved-plan and "
            "--write-approved-file flags, then l2-verify-approved-file-edit and "
            "l2-review-approved-file-edit, each separately invoked by a human."
        ),
    }
    out = write_confined(state, a.out, "artifacts", "diff-draft --out", json_text(draft))
    save_state(a.run_dir, state)
    ledger(a.run_dir, {"step": "05-diff-draft", "file": out,
                       "sha256": sha256_file(out), "diff_file": diff_out,
                       "pre_image_sha256": change["pre_image_sha256"],
                       "post_image_sha256": change["post_image_sha256"]})
    print(f"  diff for human review  {diff_out}")
    print(f"  pre_image_sha256       {change['pre_image_sha256']}")
    print(f"  post_image_sha256      {change['post_image_sha256']}")
    print("A0 RESULT: DIFF_DRAFT_READY (approval stub is empty; a human must fill it)")


def _load_stdout_json(path: str):
    with open(path, "rb") as handle:
        raw = handle.read()
    if not raw.strip():
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "unparseable"
    return value if isinstance(value, dict) else "unparseable"


def cmd_report(a) -> None:
    state = load_state(a.run_dir)
    target = state["target"]
    out = _load_stdout_json(a.stdout)
    with open(a.stderr, "rb") as handle:
        err = handle.read().decode("utf-8", "replace")
    rc, kind = a.rc, a.kind
    usage = out is None and rc == 2 and ("Usage:" in err or "No such option" in err or "Missing option" in err or "Invalid value" in err)
    cls, detail = "UNEXPECTED_STOP", ""

    if usage:
        cls = "USAGE_ERROR"
    elif kind == "generic":
        cls = "OK" if rc == 0 and isinstance(out, dict) else "FAILED_STOP"
    elif kind == "write":
        if rc == 0 and isinstance(out, dict):
            good = (out.get("schema_version") == "workspace-write-result.v1"
                    and out.get("outcome") == "written-and-verified"
                    and out.get("files_edited") == 1
                    and out.get("target", {}).get("path") == target
                    and out.get("git", {}).get("dirty_paths_after_write") == [target])
            cls = "WRITTEN" if good else "UNEXPECTED_STOP"
        elif rc == 1 and out is None:
            cls = "WRITE_REFUSED"
        elif rc == 3:
            cls = "WRITE_INDETERMINATE_STOP"
    elif kind in ("verify", "review"):
        report = out
        if kind == "review" and rc == 0 and isinstance(out, dict):
            good = (out.get("schema_version") == "review-packet.v4"
                    and out.get("verification", {}).get("outcome") == "verified"
                    and out.get("target", {}).get("path") == target
                    and out.get("human_decision_required") is True)
            verdict = out.get("review", {}).get("verdict")
            cls, detail = ("REVIEWED", f"verdict={verdict}") if good else ("UNEXPECTED_STOP", "")
        elif kind == "verify" and rc == 0 and isinstance(out, dict):
            post = out.get("workspace_postcondition", {})
            good = (out.get("outcome") == "verified" and out.get("target", {}).get("path") == target
                    and post.get("head_unchanged") is True
                    and post.get("only_approved_target_git_dirty") is True)
            cls = "VERIFIED" if good else "UNEXPECTED_STOP"
        elif rc == 2 and isinstance(report, dict) and report.get("outcome") == "verification-failed":
            cls = "VERIFICATION_FAILED"
        elif rc == 3 and isinstance(report, dict) and report.get("outcome") == "workspace-state-untrusted":
            cls = "WORKSPACE_UNTRUSTED_STOP"
        elif rc == 1 and out is None:
            cls = "REFUSED_BEFORE_EXECUTION"
        elif kind == "review" and rc == 4 and out is None:
            cls = "REVIEWER_STAGE_FAILED"

    ledger(a.run_dir, {"step": a.step, "kind": kind, "rc": rc, "class": cls, "detail": detail,
                       "stdout_file": os.path.abspath(a.stdout),
                       "stdout_sha256": sha256_file(a.stdout), "stderr_file": os.path.abspath(a.stderr)})
    print(f"A0 RESULT: {cls}  step={a.step} rc={rc} {detail}".rstrip())
    if cls in ("OK", "WRITTEN", "VERIFIED", "REVIEWED"):
        return
    sys.exit(1)


def _hash_run_tree(run_dir: str, exclude: str) -> dict:
    files = {}
    for root, _dirs, names in os.walk(run_dir):
        for name in sorted(names):
            path = os.path.join(root, name)
            if norm(path) == norm(exclude):
                continue
            files[os.path.relpath(path, run_dir).replace(os.sep, "/")] = sha256_file(path)
    return dict(sorted(files.items()))


def cmd_inventory(a) -> None:
    """Close the run. The closing ledger event is appended FIRST and nothing is
    appended after the hashing, so the ledger hash recorded here is the ledger's
    final hash. The inventory's existence closes the run: every other command
    (and the STOP handler) refuses to touch the ledger or state afterwards."""
    state = load_state(a.run_dir, allow_halted=True)
    out_path = inventory_path(a.run_dir)
    last = state.get("last_snapshot") or {}
    # A description of the last snapshot, not a proof about the present: the
    # operator reads which step and expectation it was.
    final_state = "UNPROVEN_HALTED" if state.get("halted") else (
        "LAST_SNAPSHOT_OK" if last.get("result") == "SNAPSHOT_OK" else "LAST_SNAPSHOT_NOT_OK_OR_ABSENT")
    ledger(a.run_dir, {"step": "99-inventory", "result": "CLOSING", "final_state": final_state,
                       "last_snapshot": last})
    files = _hash_run_tree(a.run_dir, out_path)
    write_json(out_path, {"generated_at": now_local(), "final_state": final_state,
                          "last_snapshot": last, "files": files})
    if _hash_run_tree(a.run_dir, out_path) != files:  # a file changed while it was being hashed
        raise Stop("a run-directory file changed while the inventory was written; the inventory "
                   f"{out_path} does not describe the final files and must not be relied on.")
    print(f"  final workspace state  {final_state}")
    print(f"A0 RESULT: INVENTORY_WRITTEN {out_path} ({len(files)} files; the run is now closed)")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="a0_helper", description="Alpha-0 operator helper (stdlib only).")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("preflight")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--workspace", required=True)
    s.add_argument("--target", required=True)
    s.add_argument("--config", required=True)
    s.add_argument("--aido-repo", required=True)
    s.add_argument("--max-bytes", type=int, default=50000)
    s.add_argument("--verified-commit", default=VERIFIED_AIDO_COMMIT)
    s.set_defaults(func=cmd_preflight)

    s = sub.add_parser("snapshot")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--step", required=True)
    s.add_argument("--rc", required=True)
    s.add_argument("--expect", required=True, choices=("none", "baseline", "written", "committed", "restored"))
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("plan-draft")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--generated", required=True)
    s.add_argument("--project-id", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_plan_draft)

    s = sub.add_parser("approval-check")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--kind", required=True, choices=("plan", "diff"))
    s.add_argument("--draft", required=True)
    s.add_argument("--approved", required=True)
    s.set_defaults(func=cmd_approval_check)

    s = sub.add_parser("packet-check")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--packet", required=True)
    s.set_defaults(func=cmd_packet_check)

    s = sub.add_parser("proposed-assemble")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--final-file", required=True)
    s.add_argument("--rationale-file", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_proposed_assemble)

    s = sub.add_parser("proposed-check")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--proposed", required=True)
    s.add_argument("--max-bytes", type=int, default=50000)
    s.set_defaults(func=cmd_proposed_check)

    s = sub.add_parser("diff-draft")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--proposal", required=True)
    s.add_argument("--diff-out", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_diff_draft)

    s = sub.add_parser("report")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--step", required=True)
    s.add_argument("--kind", required=True, choices=("generic", "write", "verify", "review"))
    s.add_argument("--rc", required=True, type=int)
    s.add_argument("--stdout", required=True)
    s.add_argument("--stderr", required=True)
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("inventory")
    s.add_argument("--run-dir", required=True)
    s.set_defaults(func=cmd_inventory)

    args = p.parse_args(argv)
    try:
        try:
            args.func(args)
        except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.TimeoutExpired) as exc:
            raise Stop(f"{type(exc).__name__}: {exc}") from exc
    except Stop as exc:
        print(f"A0 RESULT: STOP  {exc}")
        try:
            if os.path.isdir(os.path.join(args.run_dir, "logs")) and not is_closed(args.run_dir):
                ledger(args.run_dir, {"step": getattr(args, "step", args.cmd), "result": "STOP", "reason": str(exc)})
        except OSError:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
