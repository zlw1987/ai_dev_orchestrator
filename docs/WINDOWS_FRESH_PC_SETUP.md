# AIDO on a fresh Windows PC — install, configure, self-check

Status: **PORTABLE-T1 — implemented; verified only in fresh virtual
environments on the original development PC.** Independent acceptance on a
separate clean Windows PC (PORTABLE-T2) has **not** been performed. Nothing in
this guide authorizes a live model call; live use of the task workflow stays
separately authorized (GitHub issue #2, PORTABLE-T3).

This is the one operator path from `git clone` to an offline-verified AIDO
installation and a project config that `task-doctor` accepts. It changes no
system-wide setting: no PATH edit, no system Python packages, no Git
configuration, no account or ACL change.

Commands are for **CMD**. Each block runs in one window.

---

## 1. What you need first (manual, once per PC)

| Prerequisite | Why | How to confirm |
|---|---|---|
| Windows 10/11, 64-bit | the writer and verifier are Windows-only | — |
| **Python 3.14, 64-bit**, from python.org (Python install manager or the classic installer, with the `py` launcher) | the locks are resolved and validated for CPython 3.14 x64 only; the installer refuses any other interpreter | `py -3.14 -VV` prints `3.14.x ... 64 bit (AMD64)` |
| **Git for Windows**, with "Git from the command line" on PATH | AIDO's writer resolves `git` from PATH and refuses without it; the installer pins code with `git archive` | `where git` |
| HTTPS access to the Python package index (or a mirror configured in your own `pip.ini`) | `install` downloads the locked wheels; every file is checked against its SHA-256, whichever index serves it | — |
| Access to `https://github.com/zlw1987/ai_dev_orchestrator` (public) | to clone AIDO | — |

Keep the base Python 3.14 installed: the AIDO environment points back at it.

### Supported interpreter

The **only** supported deployment interpreter is **64-bit CPython 3.14 on
Windows**. The locks are resolved for `cp314-win_amd64`, and the test suite
and the installed-package acceptance (§5) were run only on 3.14. The installer
refuses every other interpreter.

`pyproject.toml` declares `requires-python = ">=3.10"`. That is an older
packaging floor, **not a support statement**: no interpreter below 3.14 has been
locked or tested for this path, and the declaration has deliberately not been
widened or narrowed here. Do not install AIDO on another interpreter because the
metadata would allow it. `tests/test_windows_deploy.py` checks that 3.14 stays
inside the declared floor and that both locks name CPython 3.14.

## 2. Get AIDO

Use a clone, not a downloaded ZIP: the installer pins the exact commit.

```bat
git clone https://github.com/zlw1987/ai_dev_orchestrator.git "%LOCALAPPDATA%\AIDO\source"
```

To install a specific commit or release instead of the latest `main`:

```bat
git -C "%LOCALAPPDATA%\AIDO\source" checkout <COMMIT>
```

## 3. Install

```bat
py -3.14 -I "%LOCALAPPDATA%\AIDO\source\deploy\windows\install_aido.py" install
```

It installs into `%LOCALAPPDATA%\AIDO\venv` (`--venv <DIR>` to choose
another new directory). What it does, in order:

1. refuses unless it runs on base 64-bit CPython 3.14 on Windows, `git` is on
   PATH, the checkout is an AIDO Git clone, the target directory does not
   exist, and the installed paths (`pyproject.toml`, `README.md`, `src`,
   `deploy/windows`) have no uncommitted changes;
2. exports exactly the committed `HEAD` of those paths with `git archive`
   (untracked or modified files in the clone can never be installed);
3. builds the AIDO wheel in a throwaway build environment whose only package is
   the hash-locked `setuptools` (`requirements-build.lock`);
4. creates the runtime environment and installs `requirements-runtime.lock`
   with `--require-hashes --only-binary :all: --no-deps` (wheels only, nothing
   outside the lock), then the AIDO wheel with `--no-deps --no-index`, then runs
   `pip check`;
5. writes `aido-install.json` (commit, wheel SHA-256, Python version, time) into
   the environment, and runs the check of §5.

A failure prints `REFUSED: <what to do>` and exits 1. If it had already created
the environment, it removes that directory and nothing else. It never reuses or
overwrites an existing environment.

It does **not** enable any project gate, write a project config, read any
`AIDO_*` or `GITHUB_TOKEN` value, provision a credential, contact a model, or
touch a target repository.

| `REFUSED:` says | Fix |
|---|---|
| `this interpreter is Python 3.x` / `32-bit` | install 64-bit Python 3.14; run with `py -3.14` |
| `belongs to a virtual environment` | run with `py -3.14`, not a venv's `python.exe` |
| `no 'git' executable is on PATH` | install Git for Windows; open a new window |
| `is not the top of a Git checkout` | `git clone` AIDO (§2); run the script from that clone |
| `uncommitted changes to files the installer installs` | commit, stash or discard them, or check out the commit you want |
| `... already exists` | delete that directory yourself, or pass `--venv` with a new path |
| `... failed (pip exit N)` | read pip's message above it; usually network/proxy. Configure pip itself (`pip.ini`); the hashes still apply |

## 4. Run the CLI

Never edit PATH for this. In each AIDO window:

```bat
set "AIDO=%LOCALAPPDATA%\AIDO\venv\Scripts\ai-dev-orchestrator.exe"
"%AIDO%" version
```

Do **not** run `python -m ai_dev_orchestrator` from inside the source clone,
and never `pip install -e` into this environment: either would run the
checkout's files instead of the installed copy (the HB-1 shadowing hazard).

## 5. Offline self-check

```bat
py -3.14 -I "%LOCALAPPDATA%\AIDO\source\deploy\windows\install_aido.py" check
```

It prints `[OK]`, `[FIX]` or `[INFO]` lines and `RESULT: OK` or exits 1. It
contacts nothing and changes nothing outside a temporary directory it deletes.

- **Integrity:** the environment is isolated; `ai_dev_orchestrator` imports
  from this environment's `site-packages`, is not editable, and there are no
  `.pth` import hooks; installed packages equal the runtime lock exactly (only
  `pip` and AIDO besides); `pip check` passes; the installed commit equals the
  clone's `HEAD`; `ai-dev-orchestrator.exe` runs and lists the four `task-*`
  commands.
- **Your environment:** the same import probe in your current environment
  resolves to the same installed file. `PYTHONPATH` or `PYTHONHOME` set is a
  `[FIX]` (clear it: `set "PYTHONPATH="`). `AIDO_*` and `GITHUB_TOKEN` names are
  reported by presence only; their values are never read.
- **Offline smoke:** in a fresh temporary directory it creates a one-file Git
  repository (with system and global Git config disabled) and a throwaway
  project config whose reviewer endpoint is the reserved, unresolvable
  `aido-offline-smoke.invalid`. It then runs the installed `task-doctor` with
  the target (AIDO's own read-only Git preflight), `task-start` and
  `task-status`, and stops at the human plan-approval pause. It never fills an
  approval, never continues the task, writes nothing to that repository, and
  leaves its ledger empty. `--keep-smoke-dir` keeps the directory to inspect.

After `git pull` or `checkout`, the check reports a commit mismatch until you
reinstall (§10).

### Installed-package acceptance (optional, offline, needs pytest)

`check` proves that the environment is intact and that its offline commands
start. To prove that the **installed** package still runs the whole accepted
workflow, run the repository's own offline tests with the installed
environment's interpreter:

```bat
py -3.14 -I "%LOCALAPPDATA%\AIDO\source\deploy\windows\run_installed_acceptance.py" --venv "%LOCALAPPDATA%\AIDO\venv" --pytest-site "<DIR>\Lib\site-packages"
```

- **`--suite workflow`** runs:
  - `tests/test_installed_task_workflow.py`: the installed
    `ai-dev-orchestrator.exe` drives every offline step. That covers
    `task-doctor`, `task-start`, `task-status`, prepare, beginning the
    correction round, the round-2 prepare and the post-terminal refusals. The
    project config is built from `aido-project.template.yaml` with the
    `init-home` layout. The run covers the full ALPHA-2A task and the one
    ALPHA-2B correction round. It also checks that no round 3 is possible.
  - the coordinator and correction-round test files.
- **`--suite all`** (the default) adds the writer, verifier, reviewer, egress,
  redaction, path-policy and supervised-implementer test files.
- **Models:** every model is an `httpx.MockTransport`. Nothing contacts a
  model, reads a credential value, or touches a real repository.
- **Refusals:** it refuses unless the environment's receipt commit equals the
  clone's `HEAD`, `tests/` and `deploy/windows/` are clean, and `check`
  (without the smoke) is all `[OK]`.
- **Isolation:** the interpreter runs with `-I` from a neutral temporary
  directory, with credential-named variables removed. `--pytest-site` is
  *appended* after the installed site-packages, so it can supply only pytest
  and what the environment lacks. Its `.pth` files are not processed.
- **Guard:** a plugin fails the run if any `ai_dev_orchestrator` module, or
  any module the environment provides, was loaded from anywhere else. The
  output ends with `installed-origin guard: every ai_dev_orchestrator module
  came from <site-packages>`.

pytest is a test tool and is **not** in the runtime lock. `--pytest-site` must
name a directory you already have. On a development PC, that is the
development environment's `Lib\site-packages`. This is a maintainer and
acceptance step, not part of day-to-day use.

## 6. Per-machine directories (opt-in)

```bat
py -3.14 -I "%LOCALAPPDATA%\AIDO\source\deploy\windows\install_aido.py" init-home
```

It creates, only if missing and always empty, `%LOCALAPPDATA%\AIDO\config`,
`\runs` (task run directories, the `task-start` default) and `\ledger` (the
single-use authorization ledger). It never modifies an existing directory, and
it prints the canonical, forward-slash ledger path for the config as
`<LEDGER_DIR_FWD>`.

**Never copy a ledger, a runs directory or a project config holding
authorizations from another PC.** Every PC starts with an empty ledger. AIDO
refuses a missing ledger rather than treating it as empty.

## 7. The target repository: a dedicated LF clone

AIDO edits **one tracked file** of a **wholly clean** clone, never your working
copy. AIDO's own Git runs with system config disabled, so the clone must carry
its own `core.autocrlf=false`; otherwise your Git (Git for Windows defaults to
`true`) and AIDO's would disagree, and CRLF targets are refused.

```bat
git clone -c core.autocrlf=false --branch main "https://github.com/<OWNER>/<REPO>.git" "C:\work\<REPO>-aido"
git -C "C:\work\<REPO>-aido" config --local --get core.autocrlf
```

The last command must print `false`. The repository must not use Git LFS or
Git filters.

**The verification program** is the one program AIDO runs after a write. It
must be an absolute path **outside** the clone, and it runs unsandboxed with a
minimal environment (no `HOME`, `USERPROFILE` or `AIDO_*`). For a Python target
this is normally the target's own interpreter in an environment kept outside
the clone, for example:

```bat
py -3.14 -m venv "%LOCALAPPDATA%\AIDO\target-envs\<PROJECT_ID>"
```

…with its args such as `-B -m pytest -p no:cacheprovider -q` (no bytecode or
cache files may be left untracked in the clone). **Never use AIDO's own
environment's `python.exe`**: it would test the installed AIDO, not the target.
Choosing the program is your decision; this guide only gives an example.

## 8. The project config

```bat
copy "%LOCALAPPDATA%\AIDO\source\deploy\windows\aido-project.template.yaml" "%LOCALAPPDATA%\AIDO\config\<PROJECT_ID>.yaml"
notepad "%LOCALAPPDATA%\AIDO\config\<PROJECT_ID>.yaml"
```

Write every path with forward slashes. Replace each placeholder:

| Placeholder | Value |
|---|---|
| `<PROJECT_ID>`, `<DISPLAY_NAME>` | a short id and a name |
| `<TARGET_CLONE_FWD>` | the clone from §7, e.g. `C:/work/<REPO>-aido` |
| `<OWNER>`, `<REPO>` | the GitHub `owner/name` (identity only) |
| `<ALLOWED_GLOB>` | the repo-relative glob(s) a task may target; keep it narrow |
| `<VERIFY_EXECUTABLE_FWD>`, `<VERIFY_ARG_1>` | the verification program and its exact args (§7); add one list item per arg |
| `<REVIEW_MODEL>` | the exact reviewer model id |
| `<LEDGER_DIR_FWD>` | the ledger path `init-home` printed |

**Every authority ships disabled.** The six lines marked `# SWITCH` are separate
decisions. Edit each to `true` only after reading what its comment says it
permits: `read_only_workspace_content`, `workspace_write`,
`controlled_verification` (unsandboxed execution), `controlled_review`
(source-derived material leaves this PC), `supervised_implementer.enabled` and
`supervised_implementer.live_transmission_enabled`. The template sets no
output-token cap and holds no endpoint, URL or key.

The `controlled_review.endpoint` block is **not** typed by hand: `task-doctor`
prints it from your reviewer base URL (§9), and you paste it once per PC.

## 9. Provider environment variables, then `task-doctor`

Endpoint values and keys live **only** in environment variables, set in the
window that needs them. Never put them in a file in a repository, and prefer
per-window `set` over persistent `setx`, which every later window would inherit.
The names are listed in `.env.example`. For the LiteLLM reviewer and the
supervised implementer:

```bat
set "AIDO_LITELLM_BASE_URL=<your LiteLLM base URL>"
set /p "AIDO_LITELLM_API_KEY=API key (typed text is visible): "
set "AIDO_LITELLM_DEFAULT_MODEL=<required non-blank; the reviewer and implementer override it with the config's model>"
"%AIDO%" task-doctor --project-config "%LOCALAPPDATA%\AIDO\config\<PROJECT_ID>.yaml" --target-path <TARGET_FILE>
```

`task-doctor` is read-only and contacts nothing. It reads one value (the
configured provider's base URL) and the *presence* of the key name. It prints
one line per gate and the `endpoint:` block to paste under `controlled_review`.
Paste it, save, and run it again until every line is `[OK]`. A direct vLLM
reviewer uses `AIDO_VLLM_BASE_URL` (and optional `AIDO_VLLM_API_KEY`) instead;
see `CLAUDE.md` for its rules.

Doctor does not check that the ledger path is spelled canonically; use the exact
path `init-home` printed, or prepare refuses it later.

## 10. Upgrade or reinstall

The installed environment is disposable; config, runs and ledger are not in it.

```bat
git -C "%LOCALAPPDATA%\AIDO\source" pull --ff-only
rmdir /s /q "%LOCALAPPDATA%\AIDO\venv"
py -3.14 -I "%LOCALAPPDATA%\AIDO\source\deploy\windows\install_aido.py" install
```

`rmdir` deletes only the environment. Keep `config`, `runs` and `ledger`. A run
is pinned to its config's bytes, so start new tasks after changing a config.

## 11. Next: the task workflow

With `check` at `RESULT: OK` and `task-doctor` all `[OK]`, the four-pause task
workflow is `docs/ALPHA_2A_TASK_COORDINATOR.md` (`task-start`, `task-status`,
`task-continue`). Its implementer and reviewer stages contact real models and
its diff stage writes the clone: run them only when that use is authorized.

## 12. Maintainer: regenerating the locks

The locks are generated, never hand-edited. Regenerate them only together with
a dependency change validated by the test suite, on 64-bit CPython 3.14:

1. Install the candidate versions in a fresh 3.14 environment from a wheel of
   the commit (`pip install --only-binary :all: <wheel>`), run the suite, and
   `pip freeze --all` to get the exact closure (excluding `pip` and AIDO).
2. `pip download --only-binary :all: --no-deps -r <exact pins> -d <dir>` plus
   the chosen `setuptools` wheel.
3. Write one `name==version` line per wheel with
   `--hash=sha256:<sha256 of that file>` into `requirements-runtime.lock`
   (everything except setuptools) and `requirements-build.lock` (setuptools),
   in the existing format and header.
4. `tests/test_windows_deploy.py` checks that the locks still satisfy
   `pyproject.toml`, are closed under the installed requirements, and carry
   exactly one hash per exact pin.

## 13. Limits of this path

- **Verified:** fresh environments on the original development PC (installer,
  check, smoke, refusals, and the §5 installed-package acceptance). **Not
  verified:** a separate clean Windows PC (PORTABLE-T2), and any interpreter
  other than 64-bit CPython 3.14 (see "Supported interpreter" in §1).
- The installed-package acceptance exercises the model-contacting steps with
  fake models through AIDO's existing in-process test seams; the installed
  console script has no fake-model option, and none was added. A real model
  endpoint is never exercised here (PORTABLE-T3).
- Build reproducibility is bounded: the wheel is built from pinned inputs, but
  it is not byte-reproducible, and pip itself is whatever the base Python
  bundles.
- The check proves where `ai_dev_orchestrator` is imported from at check time.
  It is not tamper protection for an environment someone later edits.
- Redaction, the verification minimal environment and the egress check are
  AIDO's existing controls; nothing here adds a sandbox.
