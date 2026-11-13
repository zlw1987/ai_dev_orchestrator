"""PORTABLE-T1: the Windows installer, its locks, its offline check and the template.

Offline only. Git is exercised only on synthetic repositories under ``tmp_path``;
no test creates a real environment, runs pip, or touches the network.
"""

from __future__ import annotations

import importlib.metadata as md
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

import pytest
from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

REPO = Path(__file__).resolve().parents[1]
DEPLOY = REPO / "deploy" / "windows"
GUIDE = REPO / "docs" / "WINDOWS_FRESH_PC_SETUP.md"
TEMPLATE = DEPLOY / "aido-project.template.yaml"


def _load_installer():
    spec = importlib.util.spec_from_file_location("aido_install_under_test", DEPLOY / "install_aido.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


inst = _load_installer()
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="the task workflow is Windows-only")

SENTINEL = "sentinel-value-that-must-never-appear-0f3c"


# -- helpers -------------------------------------------------------------------


def _git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("AIDO_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return env


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, env=_git_env(), capture_output=True, check=True,
    )
    return result.stdout.decode().strip()


def _synthetic_checkout(root: Path) -> str:
    """A tiny repository shaped like an AIDO checkout. Returns its HEAD."""
    root.mkdir()
    (root / "pyproject.toml").write_bytes(b'[project]\nname = "ai-dev-orchestrator"\nversion = "0.0.0"\n')
    (root / "README.md").write_bytes(b"synthetic\n")
    package = root / "src" / "ai_dev_orchestrator"
    package.mkdir(parents=True)
    (package / "__init__.py").write_bytes(b'__version__ = "0.0.0"\n')
    deploy = root / "deploy" / "windows"
    deploy.mkdir(parents=True)
    for name in ("requirements-runtime.lock", "requirements-build.lock"):
        (deploy / name).write_bytes((DEPLOY / name).read_bytes())
    _git(root.parent, "-c", "init.defaultBranch=main", "init", "-q", str(root))
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "baseline")
    return _git(root, "rev-parse", "HEAD")


def _probe(venv: Path, **overrides) -> dict:
    site = str(venv / "Lib" / "site-packages")
    lock = inst.read_lock(str(DEPLOY / "requirements-runtime.lock"))
    probe = {
        "version": [3, 14, 7],
        "x64": True,
        "prefix": str(venv),
        "base_prefix": "C:/Python314",
        "purelib": site,
        "platlib": site,
        "module_file": os.path.join(site, "ai_dev_orchestrator", "__init__.py"),
        "module_version": "0.0.0",
        "dists": [[name, version] for name, (version, _) in lock.items()]
        + [["pip", "26.2.1"], ["ai-dev-orchestrator", "0.0.0"]],
        "direct_url": json.dumps({"url": "file:///C:/x.whl", "archive_info": {}}),
        "pth_files": [],
    }
    probe.update(overrides)
    return probe


def _fixes(lines) -> list[str]:
    return [line.text for line in lines if line.status == "FIX"]


# -- locks: reproducibility and consistency with pyproject -----------------------


def test_runtime_lock_pins_every_declared_dependency_within_its_specifier():
    lock = inst.read_lock(str(DEPLOY / "requirements-runtime.lock"))
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    for raw in project["dependencies"]:
        requirement = Requirement(raw)
        name = inst.normalize_name(requirement.name)
        assert name in lock, f"{name} is declared but not locked"
        assert requirement.specifier.contains(lock[name][0]), f"{name} {lock[name][0]} violates {raw}"
    assert inst.PACKAGE_NAME not in lock


def test_build_lock_is_exactly_the_declared_build_backend():
    lock = inst.read_lock(str(DEPLOY / "requirements-build.lock"))
    build = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["build-system"]
    assert build["build-backend"] == "setuptools.build_meta"
    assert list(lock) == ["setuptools"]
    (requirement,) = [Requirement(raw) for raw in build["requires"]]
    assert requirement.specifier.contains(lock["setuptools"][0])


def test_runtime_lock_is_closed_under_installed_requirements():
    """Where this environment has the locked version, its requirements are locked too."""
    lock = inst.read_lock(str(DEPLOY / "requirements-runtime.lock"))
    env = {"sys_platform": "win32", "platform_system": "Windows", "python_version": "3.14",
           "python_full_version": "3.14.7", "implementation_name": "cpython",
           "platform_python_implementation": "CPython", "os_name": "nt", "extra": ""}
    checked = 0
    for name, (version, _) in lock.items():
        try:
            distribution = md.distribution(name)
        except md.PackageNotFoundError:
            continue
        if distribution.version != version:
            continue
        checked += 1
        for raw in distribution.requires or []:
            requirement = Requirement(raw)
            if requirement.marker is not None and not requirement.marker.evaluate(env):
                continue
            dep = inst.normalize_name(requirement.name)
            assert dep in lock, f"{name} requires {dep}, which is not locked"
            assert requirement.specifier.contains(lock[dep][0], prereleases=True)
    if checked == 0:
        pytest.skip("no locked version is installed in this test environment")


def test_every_lock_entry_has_exactly_one_sha256_and_an_exact_pin():
    for name in ("requirements-runtime.lock", "requirements-build.lock"):
        for package, (version, hashes) in inst.read_lock(str(DEPLOY / name)).items():
            assert len(hashes) == 1, package
            assert re.fullmatch(r"[0-9][0-9A-Za-z.]*", version), (package, version)


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("httpx>=0.27 --hash=sha256:" + "a" * 64 + "\n", "exact"),
        ("httpx==0.28.1\n", "no sha256"),
        ("httpx==0.28.1 --hash=md5:abc\n", "unsupported option"),
        ("httpx==0.28.1 --index-url=https://x --hash=sha256:" + "a" * 64 + "\n", "unsupported option"),
        ("a==1 --hash=sha256:" + "a" * 64 + "\nA==2 --hash=sha256:" + "b" * 64 + "\n", "twice"),
        ("# only comments\n", "pins nothing"),
    ],
)
def test_parse_lock_refuses_anything_but_hashed_exact_pins(text, fragment):
    with pytest.raises(inst.InstallError, match=fragment):
        inst.parse_lock(text)


def test_parse_lock_accepts_continuations_and_comments():
    pins = inst.parse_lock("Foo_Bar==1.2 \\\n    --hash=sha256:" + "c" * 64 + "\n    # foo.whl\n")
    assert pins == {"foo-bar": ("1.2", ("c" * 64,))}


# -- prerequisites -----------------------------------------------------------------


def _interp(**overrides):
    values = dict(version_info=(3, 14, 7), is_64bit=True, platform="win32", prefix="C:/Py", base_prefix="C:/Py")
    values.update(overrides)
    return inst.check_interpreter(**values)


def test_check_interpreter_accepts_base_64bit_314():
    _interp()


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"platform": "linux"}, "Windows-only"),
        ({"version_info": (3, 13, 2)}, r"Python 3\.13\.2"),
        ({"version_info": (3, 15, 0)}, r"Python 3\.15\.0"),
        ({"is_64bit": False}, "32-bit"),
        ({"prefix": "C:/venv"}, "virtual environment"),
    ],
)
def test_check_interpreter_refuses_with_an_actionable_message(overrides, fragment):
    with pytest.raises(inst.InstallError, match=fragment) as caught:
        _interp(**overrides)
    if "version_info" in overrides or "is_64bit" in overrides:
        assert "py -3.14 -I deploy\\windows\\install_aido.py install" in str(caught.value)


def test_find_git_refuses_missing_and_non_file(tmp_path):
    with pytest.raises(inst.InstallError, match="Git for Windows"):
        inst.find_git(lambda name: None)
    with pytest.raises(inst.InstallError, match="not a regular file"):
        inst.find_git(lambda name: str(tmp_path))
    exe = tmp_path / "git.exe"
    exe.write_bytes(b"")
    assert inst.find_git(lambda name: str(exe)) == str(exe)


# -- checkout handling (synthetic repositories only) --------------------------------


def test_read_checkout_returns_head_of_a_clean_checkout(tmp_path):
    root = tmp_path / "aido"
    head = _synthetic_checkout(root)
    (root / "src" / "ai_dev_orchestrator" / "untracked_shadow.py").write_bytes(b"x = 1\n")
    assert inst.read_checkout(str(root), inst.find_git(), inst.run) == head


def test_read_checkout_refuses_tracked_changes_to_installed_paths(tmp_path):
    root = tmp_path / "aido"
    _synthetic_checkout(root)
    (root / "src" / "ai_dev_orchestrator" / "__init__.py").write_bytes(b'__version__ = "9"\n')
    with pytest.raises(inst.InstallError, match=r"uncommitted changes.*src/ai_dev_orchestrator/__init__\.py"):
        inst.read_checkout(str(root), inst.find_git(), inst.run)


def test_read_checkout_refuses_a_non_aido_project_and_a_non_checkout(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "pyproject.toml").write_bytes(b'[project]\nname = "something-else"\n')
    with pytest.raises(inst.InstallError, match="not an AIDO checkout"):
        inst.read_checkout(str(other), inst.find_git(), inst.run)
    loose = tmp_path / "loose"
    loose.mkdir()
    (loose / "pyproject.toml").write_bytes(b'[project]\nname = "ai-dev-orchestrator"\n')
    with pytest.raises(inst.InstallError, match="not the top of a Git checkout"):
        inst.read_checkout(str(loose), inst.find_git(), inst.run)


def test_extract_archive_refuses_path_traversal(tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        member = tarfile.TarInfo("../escape.txt")
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(tarfile.TarError):
        inst.extract_archive(buffer.getvalue(), str(tmp_path / "stage"))
    assert not (tmp_path / "escape.txt").exists()


# -- install, with a fake launcher for everything but git ---------------------------


class FakeLauncher:
    """Runs git for real (synthetic repo); fakes every python/pip launch."""

    def __init__(self, fail_on: str | None = None):
        self.calls: list[tuple[list[str], dict | None]] = []
        self.fail_on = fail_on

    def __call__(self, argv, *, cwd=None, env=None, capture=True, timeout=None):
        # inst.run's own default for env=None is scrubbed_env(os.environ); record that.
        effective = dict(env) if env is not None else inst.scrubbed_env(os.environ)
        self.calls.append((list(argv), effective))
        if os.path.basename(argv[0]).lower().startswith("git"):
            return inst.run(argv, cwd=cwd, env=env)
        joined = " ".join(argv)
        if self.fail_on and self.fail_on in joined:
            return subprocess.CompletedProcess(argv, 1, b"", b"simulated failure")
        if argv[1:4] == ["-I", "-m", "venv"]:
            scripts = Path(argv[4]) / "Scripts"
            scripts.mkdir(parents=True)
            (scripts / "python.exe").write_bytes(b"")
        elif "wheel" in argv:
            wheel_dir = Path(argv[argv.index("-w") + 1])
            wheel_dir.mkdir(parents=True, exist_ok=True)
            (wheel_dir / "ai_dev_orchestrator-0.0.0-py3-none-any.whl").write_bytes(b"wheel")
        return subprocess.CompletedProcess(argv, 0, b"", b"")


def _environ_with_secrets():
    env = dict(os.environ)
    env.update(AIDO_LITELLM_API_KEY=SENTINEL, AIDO_VLLM_API_KEY=SENTINEL, GITHUB_TOKEN=SENTINEL)
    return env


def test_install_builds_from_head_with_locked_hashes_and_writes_a_receipt(tmp_path, monkeypatch):
    for name in ("AIDO_LITELLM_API_KEY", "AIDO_VLLM_API_KEY", "GITHUB_TOKEN"):
        monkeypatch.setenv(name, SENTINEL)
    root = tmp_path / "aido"
    head = _synthetic_checkout(root)
    venv = tmp_path / "home" / "venv"
    launcher = FakeLauncher()
    receipt = inst.install(str(venv), root=str(root), base_python=sys.executable, runner=launcher,
                           environ=_environ_with_secrets(), out=lambda text: None)

    assert receipt["source_commit"] == head
    assert json.loads((venv / inst.RECEIPT_NAME).read_text(encoding="utf-8")) == receipt
    argvs = [" ".join(argv) for argv, _ in launcher.calls]
    archive = next(a for a in argvs if " archive " in a)
    assert f"archive --format=tar {head} pyproject.toml README.md src deploy/windows" in archive
    assert "core.autocrlf=false" in archive
    pip_installs = [a for a in argvs if " -m pip install " in a and "--no-index" not in a]
    assert len(pip_installs) == 2
    for command in pip_installs:
        assert "--require-hashes --only-binary :all: --no-deps -r" in command
    assert any("requirements-build.lock" in a for a in pip_installs)
    assert any("requirements-runtime.lock" in a for a in pip_installs)
    wheel_install = next(a for a in argvs if " -m pip install " in a and "--no-index" in a)
    assert "--no-deps --no-index" in wheel_install and wheel_install.endswith(".whl")
    assert any(" -m pip wheel " in a and "--no-build-isolation --no-index" in a for a in argvs)
    # No child -- git, venv or pip -- ever received a credential-named variable.
    for argv, env in launcher.calls:
        assert not any(k.upper().startswith("AIDO_") or k.upper() == "GITHUB_TOKEN" for k in env), argv
        assert SENTINEL not in json.dumps(env)


def test_install_removes_the_environment_it_created_when_a_step_fails(tmp_path):
    root = tmp_path / "aido"
    _synthetic_checkout(root)
    venv = tmp_path / "venv"
    messages: list[str] = []
    with pytest.raises(inst.InstallError, match="locked runtime dependencies"):
        inst.install(str(venv), root=str(root), base_python=sys.executable,
                     runner=FakeLauncher(fail_on="requirements-runtime.lock"), out=messages.append)
    assert not venv.exists()
    assert any("Removed the partially created environment" in m for m in messages)


def test_install_never_reuses_or_overwrites_an_existing_environment(tmp_path):
    root = tmp_path / "aido"
    _synthetic_checkout(root)
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "keep.txt").write_bytes(b"mine")
    launcher = FakeLauncher()
    with pytest.raises(inst.InstallError, match="already exists"):
        inst.install(str(venv), root=str(root), base_python=sys.executable, runner=launcher, out=lambda t: None)
    assert (venv / "keep.txt").read_bytes() == b"mine"
    assert not any("venv" in argv for argv, _ in launcher.calls if "-m" in argv)


def test_install_refuses_a_dirty_checkout_before_launching_python(tmp_path):
    root = tmp_path / "aido"
    _synthetic_checkout(root)
    (root / "deploy" / "windows" / "requirements-runtime.lock").write_bytes(b"tampered\n")
    launcher = FakeLauncher()
    with pytest.raises(inst.InstallError, match="uncommitted changes"):
        inst.install(str(tmp_path / "venv"), root=str(root), base_python=sys.executable, runner=launcher,
                     out=lambda t: None)
    assert all(os.path.basename(argv[0]).lower().startswith("git") for argv, _ in launcher.calls)


# -- check: import origin, editable shadowing, lock drift ----------------------------


def test_evaluate_probe_accepts_a_locked_regular_install(tmp_path):
    lines = inst.evaluate_probe(_probe(tmp_path), str(tmp_path), inst.read_lock(str(DEPLOY / "requirements-runtime.lock")))
    assert _fixes(lines) == []


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"direct_url": json.dumps({"url": "file:///C:/dev/aido", "dir_info": {"editable": True}})}, "EDITABLE"),
        ({"module_file": "C:/dev/ai_dev_orchestrator/src/ai_dev_orchestrator/__init__.py"}, "outside this environment"),
        ({"import_error": "ModuleNotFoundError: No module named 'ai_dev_orchestrator'"}, "cannot be imported"),
        ({"pth_files": ["X/__editable__.ai_dev_orchestrator-0.0.0.pth"]}, r"unexpected \.pth"),
        ({"version": [3, 13, 1]}, "not 64-bit"),
        ({"prefix": "C:/elsewhere"}, "does not belong"),
    ],
)
def test_evaluate_probe_flags_shadowing_and_foreign_interpreters(tmp_path, overrides, fragment):
    lock = inst.read_lock(str(DEPLOY / "requirements-runtime.lock"))
    fixes = _fixes(inst.evaluate_probe(_probe(tmp_path, **overrides), str(tmp_path), lock))
    assert any(re.search(fragment, text) for text in fixes), fixes


def test_evaluate_probe_flags_every_kind_of_lock_drift(tmp_path):
    lock = inst.read_lock(str(DEPLOY / "requirements-runtime.lock"))
    dists = [[n, v] for n, (v, _) in lock.items() if n not in ("httpx", "rich")]
    dists += [["httpx", "0.27.0"], ["pytest", "9.1.1"], ["pip", "26.2.1"], ["PyYAML", lock["pyyaml"][0]]]
    (fix_text,) = [t for t in _fixes(inst.evaluate_probe(_probe(tmp_path, dists=dists), str(tmp_path), lock))]
    for fragment in ("httpx 0.27.0 (lock pins 0.28.1)", "pytest 9.1.1 is not in the lock",
                     "rich is missing", "pyyaml is installed 2 times", "ai-dev-orchestrator is missing"):
        assert fragment in fix_text


def test_check_reports_a_directory_that_is_not_an_installed_environment(tmp_path):
    lines = inst.check(str(tmp_path), root=str(REPO), runner=FakeLauncher(), smoke=False)
    assert [line.status for line in lines] == ["FIX"]
    assert "not an installed AIDO environment" in lines[0].text


def test_environment_lines_name_hazards_and_never_echo_values():
    environ = {"PYTHONPATH": SENTINEL, "AIDO_LITELLM_API_KEY": SENTINEL, "GITHUB_TOKEN": SENTINEL, "PATH": "x"}
    lines = inst.environment_lines(environ)
    rendered = "\n".join(line.render() for line in lines)
    assert "[FIX] PYTHONPATH is set" in rendered
    assert "AIDO_LITELLM_API_KEY" in rendered and "GITHUB_TOKEN" in rendered
    assert SENTINEL not in rendered


def test_scrubbed_env_drops_credential_and_import_names_by_name():
    env = inst.scrubbed_env({"PATH": "p", "aido_vllm_api_key": "k", "AIDO_ANYTHING": "k", "GITHUB_TOKEN": "k",
                             "PYTHONPATH": "k", "PYTHONHOME": "k", "TEMP": "t"})
    assert env == {"PATH": "p", "TEMP": "t"}


# -- template --------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"<[A-Z][A-Z0-9_]*>")


def _filled_template(tmp_path: Path, workspace: Path) -> str:
    verify = tmp_path / "verifier.exe"
    verify.write_bytes(b"")
    ledger = tmp_path / "ledger"
    ledger.mkdir(exist_ok=True)
    values = {
        "<PROJECT_ID>": "demo", "<DISPLAY_NAME>": "Demo", "<TARGET_CLONE_FWD>": workspace.as_posix(),
        "<OWNER>": "owner", "<REPO>": "repo", "<ALLOWED_GLOB>": "hello.txt",
        "<VERIFY_EXECUTABLE_FWD>": verify.as_posix(), "<VERIFY_ARG_1>": "-V",
        "<REVIEW_MODEL>": "reviewer-model", "<LEDGER_DIR_FWD>": ledger.as_posix(),
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    assert set(_PLACEHOLDER_RE.findall(text)) == set(values)
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def _load(text: str, tmp_path: Path, name: str):
    from ai_dev_orchestrator.config_loader import load_project_config

    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return load_project_config(path)


def test_template_as_shipped_enables_nothing(tmp_path):
    project = _load(_filled_template(tmp_path, tmp_path / "ws"), tmp_path, "shipped.yaml")
    assert project.read_only_workspace_content.enabled is False
    assert project.workspace_write.enabled is False
    assert project.controlled_verification.enabled is False
    assert project.controlled_review.enabled is False
    assert project.controlled_review.endpoint is None
    assert project.supervised_implementer.enabled is False
    assert project.supervised_implementer.live_transmission_enabled is False
    assert project.real_model_planning.enabled is False
    assert project.controlled_review.max_output_tokens is None
    assert project.supervised_implementer.max_output_tokens is None


def test_template_holds_no_secret_endpoint_or_token_cap():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "max_output_tokens" not in text and "max_tokens" not in text
    assert not re.search(r"https?://", text)
    assert not re.search(r"(?m)^\s*AIDO_[A-Z_]+\s*[:=]", text)
    assert text.count("# SWITCH") == 6


@windows_only
def test_template_with_its_six_switches_flipped_passes_every_task_gate(tmp_path):
    from ai_dev_orchestrator.task.doctor import endpoint_block_yaml, derive_endpoint, run_doctor

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "hello.txt").write_bytes(b"hello\n")
    _git(tmp_path, "-c", "init.defaultBranch=main", "init", "-q", str(workspace))
    _git(workspace, "config", "core.autocrlf", "false")
    _git(workspace, "add", "hello.txt")
    _git(workspace, "commit", "-q", "-m", "baseline")

    text = re.sub(r"(?m)^(\s*(?:enabled|live_transmission_enabled): )false(\s+# SWITCH)", r"\1true\2",
                  _filled_template(tmp_path, workspace))
    endpoint = derive_endpoint(inst.SMOKE_BASE_URL)
    block = endpoint_block_yaml(endpoint).split("\n", 1)[1]  # the indented 'endpoint:' lines
    text = text.replace("  # endpoint:  -> do NOT", block + "  # endpoint:  -> do NOT", 1)
    project = _load(text, tmp_path, "opened.yaml")
    lines, _ = run_doctor(
        project,
        environ={"AIDO_LITELLM_BASE_URL": inst.SMOKE_BASE_URL, "AIDO_LITELLM_API_KEY": SENTINEL},
        target_path="hello.txt",
    )
    assert [line.text for line in lines if not line.ok] == []


def test_guide_documents_every_template_placeholder_and_installer_command():
    guide = GUIDE.read_text(encoding="utf-8")
    for placeholder in set(_PLACEHOLDER_RE.findall(TEMPLATE.read_text(encoding="utf-8"))):
        assert placeholder in guide, placeholder
    for command in ("install", "check", "init-home"):
        assert re.search(r'install_aido\.py"? ' + command + r"\b", guide), command


# -- the offline smoke's expectations stay in sync with the real doctor ----------------


@windows_only
def test_smoke_config_reaches_exactly_the_expected_doctor_report(tmp_path):
    from ai_dev_orchestrator.models import ProjectConfig
    from ai_dev_orchestrator.task.doctor import run_doctor

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / inst.SMOKE_TARGET).write_bytes(inst.SMOKE_TARGET_BYTES)
    _git(tmp_path, "-c", "init.defaultBranch=main", "init", "-q", str(workspace))
    _git(workspace, "config", "core.autocrlf", "false")
    _git(workspace, "add", inst.SMOKE_TARGET)
    _git(workspace, "commit", "-q", "-m", "baseline")
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    config = inst.smoke_config(workspace=str(workspace), ledger=str(ledger), verification_executable=sys.executable)
    project = ProjectConfig.model_validate(json.loads(json.dumps(config)))
    lines, derived = run_doctor(project, environ={"AIDO_LITELLM_BASE_URL": inst.SMOKE_BASE_URL},
                                target_path=inst.SMOKE_TARGET)
    assert derived == project.controlled_review.endpoint
    stdout = "\n".join(f"[{'OK' if line.ok else 'FIX'}] {line.text}" for line in lines).encode()
    verdict = inst.evaluate_doctor_output(subprocess.CompletedProcess([], 1, stdout, b""))
    assert verdict.status == "OK", verdict.text


def test_evaluate_doctor_output_rejects_an_unexpected_fix():
    stdout = b"[OK] workspace_write.enabled\n[FIX] controlled_review gate: opt-in error\n"
    verdict = inst.evaluate_doctor_output(subprocess.CompletedProcess([], 1, stdout, b""))
    assert verdict.status == "FIX" and "controlled_review gate" in verdict.text


# -- init-home ------------------------------------------------------------------------


def test_init_home_creates_empty_dirs_and_never_touches_existing_ones(tmp_path):
    local = tmp_path / "Local"
    local.mkdir()
    lines = inst.init_home({"LOCALAPPDATA": str(local)})
    for name in ("config", "runs", "ledger"):
        assert (local / "AIDO" / name).is_dir()
        assert not any((local / "AIDO" / name).iterdir())
    assert sum(line.status == "OK" for line in lines) == 3
    assert any((local / "AIDO" / "ledger").as_posix() in line.text for line in lines)

    record = local / "AIDO" / "ledger" / "record"
    record.write_bytes(b"existing")
    again = inst.init_home({"LOCALAPPDATA": str(local)})
    assert record.read_bytes() == b"existing"
    assert all(line.status == "INFO" for line in again)
    assert any("kept existing" in line.text and "1 entry" in line.text for line in again)


def test_init_home_refuses_a_file_in_the_way_and_a_missing_localappdata(tmp_path):
    (tmp_path / "AIDO").mkdir()
    (tmp_path / "AIDO" / "ledger").write_bytes(b"")
    with pytest.raises(inst.InstallError, match="not a directory"):
        inst.init_home({"LOCALAPPDATA": str(tmp_path)})
    with pytest.raises(inst.InstallError, match="LOCALAPPDATA"):
        inst.init_home({})


# -- static guards on the installer itself --------------------------------------------


def test_installer_reads_no_credential_value_and_imports_no_client():
    import ast

    source = (DEPLOY / "install_aido.py").read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported.isdisjoint({"httpx", "requests", "urllib", "socket", "http", "ai_dev_orchestrator"}), imported
    assert not re.search(r"""environ(?:\.get)?\s*[\[(]\s*["'](?:AIDO_|GITHUB)""", source)
    assert "getenv" not in source
    assert "shell=True" not in source
    # The installed package is only ever imported in a child interpreter.
    assert source.count("import ai_dev_orchestrator") == 1


# -- the Python version policy ------------------------------------------------------------


def test_the_one_supported_interpreter_is_inside_the_declared_floor_and_documented():
    """3.14 x64 is the only deployment interpreter; pyproject's floor is not a support claim."""
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    supported = "%d.%d" % inst.SUPPORTED_PYTHON
    assert SpecifierSet(project["requires-python"]).contains(supported + ".0")
    for lock in ("requirements-runtime.lock", "requirements-build.lock"):
        assert f"CPython {supported}" in (DEPLOY / lock).read_text(encoding="ascii").splitlines()[0]
    guide = GUIDE.read_text(encoding="utf-8")
    assert "### Supported interpreter" in guide
    assert f"`requires-python = \"{project['requires-python']}\"`" in guide


# -- the installed-package acceptance runner -------------------------------------------------

ACCEPTANCE = DEPLOY / "run_installed_acceptance.py"


def _load_acceptance():
    spec = importlib.util.spec_from_file_location("aido_acceptance_under_test", ACCEPTANCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


acc = _load_acceptance()


def test_every_acceptance_test_file_exists_and_the_workflow_suite_is_included_in_all():
    names = acc.SUITES["all"]
    assert len(names) == len(set(names))
    assert set(acc.WORKFLOW_TESTS) <= set(names)
    for name in names:
        assert (REPO / "tests" / name).is_file(), name


def _fake_installed_env(tmp_path: Path, commit: str) -> Path:
    venv = tmp_path / "venv"
    (venv / "Scripts").mkdir(parents=True)
    (venv / "Scripts" / "python.exe").write_bytes(b"")
    (venv / inst.RECEIPT_NAME).write_text(json.dumps({"schema": inst.RECEIPT_SCHEMA, "source_commit": commit}))
    return venv


def _tools_site(tmp_path: Path) -> Path:
    tools = tmp_path / "tools"
    (tools / "pytest").mkdir(parents=True)
    return tools


@windows_only
def test_acceptance_preflight_refuses_what_would_not_test_the_installed_commit(tmp_path):
    checkout = tmp_path / "checkout"
    head = _synthetic_checkout(checkout)
    tools = _tools_site(tmp_path)

    with pytest.raises(acc.inst.InstallError, match="not an environment made by install_aido.py"):
        acc.preflight(str(tmp_path / "nothing"), root=str(checkout), pytest_site=str(tools))

    other = _fake_installed_env(tmp_path / "a", "0" * 40)
    with pytest.raises(acc.inst.InstallError, match="own tests"):
        acc.preflight(str(other), root=str(checkout), pytest_site=str(tools))

    venv = _fake_installed_env(tmp_path / "b", head)
    (checkout / "tests").mkdir()
    (checkout / "tests" / "test_new.py").write_bytes(b"")
    with pytest.raises(acc.inst.InstallError, match="differ from the installed commit"):
        acc.preflight(str(venv), root=str(checkout), pytest_site=str(tools))
    (checkout / "tests" / "test_new.py").unlink()

    with pytest.raises(acc.inst.InstallError, match="does not contain pytest"):
        acc.preflight(str(venv), root=str(checkout), pytest_site=str(tmp_path))
    with pytest.raises(acc.inst.InstallError, match="inside the installed environment"):
        (venv / "pytest").mkdir()
        acc.preflight(str(venv), root=str(checkout), pytest_site=str(venv))
    (tools / inst.MODULE_NAME).mkdir()
    with pytest.raises(acc.inst.InstallError, match="regular copy"):
        acc.preflight(str(venv), root=str(checkout), pytest_site=str(tools))


@windows_only
def test_acceptance_bootstrap_refuses_an_aido_imported_from_the_source_checkout(tmp_path):
    import ai_dev_orchestrator

    source = REPO / "src"
    if not Path(ai_dev_orchestrator.__file__).resolve().is_relative_to(source.resolve()):
        pytest.skip("this interpreter does not import AIDO from the checkout source")
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", acc.BOOTSTRAP, sys.prefix, str(tmp_path), str(REPO), "[]"],
        cwd=tmp_path, capture_output=True, timeout=120, check=False,
    )
    assert result.returncode != 0
    assert b"wrong import origin" in result.stderr
    assert b"INSTALLED-PACKAGE TEST RUN" not in result.stdout


def test_acceptance_runner_is_stdlib_offline_and_passes_no_credential():
    import ast

    source = ACCEPTANCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "argparse", "importlib", "json", "os", "shutil", "subprocess", "sys", "tempfile"}
    assert "scrubbed_env(os.environ)" in source and "shell=True" not in source
    assert not re.search(r"""environ(?:\.get)?\s*[\[(]\s*["'](?:AIDO_|GITHUB)""", source)
    assert '"-I", "-B", "-c", BOOTSTRAP' in source
