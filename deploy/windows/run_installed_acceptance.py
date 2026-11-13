"""Run AIDO's offline workflow and boundary tests AGAINST AN INSTALLED AIDO (PORTABLE-T1).

Stdlib only. Run it from the checkout that was installed::

    py -3.14 -I deploy\\windows\\run_installed_acceptance.py --venv <installed env> ^
        --pytest-site <a site-packages directory that provides pytest>

``install_aido.py check`` proves the installed environment is intact and that
its offline commands start. This script answers a different question: does the
INSTALLED package -- not the development checkout -- still carry out the
accepted ALPHA-2A task and ALPHA-2B correction round, and still enforce the
frozen boundaries? It runs the repository's own existing tests with the
installed environment's interpreter:

* ``workflow``: ``tests/test_installed_task_workflow.py`` (the installed
  console script, from the shipped template), ``tests/test_task_coordinator.py``
  and ``tests/test_task_correction_round.py``;
* ``all`` (default): ``workflow`` plus the writer, verifier, reviewer,
  supervised-implementer, egress, redaction and path-policy test files listed in
  ``BOUNDARY_TESTS``.

Every model in those tests is an ``httpx.MockTransport`` handler. Nothing here
contacts a model, reads a credential value, or touches a real repository.

How the installed package is kept honest:

* the installed environment must carry an ``install_aido.py`` receipt whose
  commit is this checkout's ``HEAD``. The test files and ``deploy/windows``
  must be clean, so the tests that run are the installed commit's own tests;
* ``install_aido.py check`` (without its smoke) must report nothing to fix;
* the interpreter runs isolated (``-I``: no ``PYTHONPATH``, no user site, no
  script or working directory on ``sys.path``) from a neutral temporary
  directory, with credential-named variables removed;
* pytest comes from ``--pytest-site``, which is APPENDED to ``sys.path`` after
  the installed site-packages, so it can only supply what the installed
  environment does not have. That directory's ``.pth`` files are not processed,
  so an editable install of AIDO there is inert;
* a guard plugin fails the run if, after collection or at the end, any
  ``ai_dev_orchestrator`` module was loaded from anywhere but the installed
  site-packages, or if any module that the installed environment provides was
  loaded from ``--pytest-site`` or from the checkout's ``src``.

It does not install pytest. ``--pytest-site`` names a directory you already
have (for example a development environment's ``Lib\\site-packages``); pytest is
a test tool and is deliberately not part of the runtime lock.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

WORKFLOW_TESTS = (
    "test_installed_task_workflow.py",
    "test_task_coordinator.py",
    "test_task_correction_round.py",
)
#: Frozen authority, source-transmission, model-role, evidence and retry boundaries.
BOUNDARY_TESTS = (
    # the one-file writer and its target guard
    "test_cli_l2_apply_approved_file_edit.py",
    "test_strict_diff_apply.py",
    "test_workspace_write_target_guard.py",
    "test_workspace_canonical_path_guard.py",
    "test_writer_execution_isolation.py",
    "test_path_policy.py",
    # the controlled verification
    "test_cli_l2_verify_approved_file_edit.py",
    "test_verification_runner.py",
    "test_controlled_verification_config.py",
    # the reviewer: transmission boundary, egress authority, env isolation, RS1 retry/stall policy
    "test_cli_l2_review_approved_file_edit.py",
    "test_review_egress.py",
    "test_cli_l2_review_provider_env_isolation.py",
    "test_review_supervision.py",
    "test_cli_l2_review_supervision.py",
    "test_cli_l2_review_structured_output.py",
    "test_cli_l2_review_vllm_provider.py",
    "test_review_request_builder.py",
    "test_review_output_models.py",
    "test_controlled_review_config.py",
    "test_optional_model_output_token_cap.py",
    "test_redaction.py",
    # the supervised, proposal-only implementer and its single-use ledger
    "test_supervised_implementer.py",
    "test_supervised_implementer_live.py",
)
SUITES = {"workflow": WORKFLOW_TESTS, "all": WORKFLOW_TESTS + BOUNDARY_TESTS}
RUN_TIMEOUT_SECONDS = 3600

#: Executed by the INSTALLED environment's python with -I. argv: venv, pytest
#: site, checkout root, JSON list of pytest arguments.
BOOTSTRAP = r"""
import json, os, sys, sysconfig
venv, tools, root, args = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4])

def norm(path):
    return os.path.normcase(os.path.realpath(path))

def under(path, base):
    p, b = norm(path), norm(base)
    return p == b or p.startswith(b.rstrip("\\/") + os.sep)

site = sysconfig.get_paths()["purelib"]
if not (under(sys.prefix, venv) and under(site, venv)):
    sys.exit("BOOTSTRAP: this interpreter is not the installed environment's")
provided = set()
for name in os.listdir(site):
    if name.endswith((".dist-info", ".pth", ".egg-info")) or name == "__pycache__":
        continue
    provided.add(name.split(".", 1)[0])
src = os.path.join(root, "src")

# pytest may supply only what the installed environment lacks. The checkout
# root goes last, for 'from tests.<module> import'; it is a src layout, so it
# holds no importable ai_dev_orchestrator.
sys.path.append(tools)
sys.path.append(root)

def violations():
    found = []
    for name, module in sorted(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if not path:
            continue
        top = name.split(".", 1)[0]
        if top == "ai_dev_orchestrator" and not under(path, site):
            found.append(f"{name} from {path}")
        elif top in provided and (under(path, tools) or under(path, src)):
            found.append(f"{name} from {path} (the installed environment provides {top})")
        elif under(path, src):
            found.append(f"{name} from the checkout source {path}")
    return found

import ai_dev_orchestrator, httpx, pydantic, pydantic_core, yaml, typer, cryptography
import pytest
early = violations()
if early:
    sys.exit("BOOTSTRAP: wrong import origin:\n  " + "\n  ".join(early))
print("INSTALLED-PACKAGE TEST RUN")
print(f"  interpreter   {sys.executable} ({sys.version.split()[0]})")
print(f"  site-packages {site}")
for module in (ai_dev_orchestrator, httpx, pydantic, pydantic_core, yaml, typer, cryptography, pytest):
    print(f"  {module.__name__:<20} {getattr(module, '__version__', '?'):<10} {module.__file__}")

class InstalledOriginGuard:
    def __init__(self):
        self.found = []

    def pytest_collection_finish(self, session):
        self.found.extend(violations())

    def pytest_sessionfinish(self, session, exitstatus):
        self.found.extend(violations())
        if self.found:
            session.exitstatus = 1

    def pytest_terminal_summary(self, terminalreporter):
        if self.found:
            terminalreporter.write_sep("=", "INSTALLED-ORIGIN GUARD FAILED", red=True)
            for line in sorted(set(self.found)):
                terminalreporter.write_line("  " + line)
        else:
            terminalreporter.write_sep(
                "=", "installed-origin guard: every ai_dev_orchestrator module came from " + site, green=True
            )

guard = InstalledOriginGuard()
code = int(pytest.main(args, plugins=[guard]))
sys.exit(1 if guard.found and code == 0 else code)
"""


def _load_installer():
    spec = importlib.util.spec_from_file_location("aido_install_for_acceptance", os.path.join(HERE, "install_aido.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


inst = _load_installer()


def preflight(venv_dir: str, *, root: str, pytest_site: str, runner=inst.run, which=shutil.which) -> list:
    """Refuse unless the installed environment, the checkout and the tools site line up."""
    receipt = inst.read_receipt(venv_dir)
    if receipt is None or not os.path.isfile(inst.venv_python(venv_dir)):
        raise inst.InstallError(f"{venv_dir!r} is not an environment made by install_aido.py install.")
    git = inst.find_git(which)
    code, head = inst.git_text(git, root, ["rev-parse", "--verify", "HEAD^{commit}"], runner)
    if code != 0 or head != receipt["source_commit"]:
        raise inst.InstallError(
            f"the environment holds commit {receipt['source_commit']}, but this checkout is at "
            f"{head or 'an unreadable HEAD'}. Run this from a checkout of the installed commit, so "
            "that the tests are the installed code's own tests."
        )
    code, dirty = inst.git_text(
        git, root, ["status", "--porcelain", "--untracked-files=all", "--", "tests", "deploy/windows"], runner
    )
    if code != 0 or dirty:
        raise inst.InstallError(
            "tests/ or deploy/windows/ differ from the installed commit; the run would not test "
            "what was installed. Commit, stash or discard them first."
        )
    tools = os.path.abspath(pytest_site)
    if not os.path.isdir(os.path.join(tools, "pytest")) and not os.path.isdir(os.path.join(tools, "_pytest")):
        raise inst.InstallError(f"--pytest-site {tools!r} does not contain pytest.")
    if inst.is_same_or_under(tools, venv_dir):
        raise inst.InstallError("--pytest-site must not be inside the installed environment.")
    if os.path.isdir(os.path.join(tools, inst.MODULE_NAME)):
        raise inst.InstallError(
            f"--pytest-site holds a regular copy of {inst.MODULE_NAME}; use a directory without one."
        )
    lines = inst.check(venv_dir, root=root, runner=runner, which=which, smoke=False)
    fixes = [line for line in lines if line.status == "FIX"]
    if fixes:
        raise inst.InstallError(
            "install_aido.py check reports problems:\n" + "\n".join(line.render() for line in fixes)
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    # Keep our lines in order with the child's, which writes to the inherited stream.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(prog="run_installed_acceptance.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--venv", required=True, help="the installed AIDO environment directory")
    parser.add_argument("--pytest-site", required=True, help="a site-packages directory that provides pytest")
    parser.add_argument("--suite", choices=sorted(SUITES), default="all")
    parser.add_argument("pytest_args", nargs="*", help="extra pytest arguments, after '--'")
    args = parser.parse_args(argv)

    root = inst.checkout_root()
    venv_dir = os.path.abspath(args.venv)
    try:
        lines = preflight(venv_dir, root=root, pytest_site=args.pytest_site)
    except inst.InstallError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    for line in lines:
        print(line.render())

    tests_dir = os.path.join(root, "tests")
    files = [os.path.join(tests_dir, name) for name in SUITES[args.suite]]
    missing = [path for path in files if not os.path.isfile(path)]
    if missing:
        print("REFUSED: missing test files: " + ", ".join(missing), file=sys.stderr)
        return 1
    pytest_args = ["-p", "no:cacheprovider", "--rootdir", root, "-q", *files, *args.pytest_args]
    env = dict(inst.scrubbed_env(os.environ), PYTHONIOENCODING="utf-8")
    neutral = tempfile.mkdtemp(prefix="aido-acceptance-")
    try:
        result = inst.run(
            [inst.venv_python(venv_dir), "-I", "-B", "-c", BOOTSTRAP, venv_dir, os.path.abspath(args.pytest_site),
             root, json.dumps(pytest_args)],
            cwd=neutral, env=env, capture=False, timeout=RUN_TIMEOUT_SECONDS,
        )
    except inst.InstallError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(neutral, ignore_errors=True)
    print(f"RESULT: pytest exit {result.returncode} against the installed package in {venv_dir}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
