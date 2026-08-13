"""Phase 5F2C / 5F2C-FU1 tests: the fixed Git inspection adapter.

The adapter is the one place in this repository that starts a process, so the
tests here are mostly about what it **cannot** do: it cannot run a program other
than the one absolute ``git`` executable resolved up front, cannot run a Git
subcommand outside a closed set, cannot be handed a flag or a shell fragment by
a model, a user, a config file, or an artifact, and cannot mutate a repository,
reach a network, or leak this process's environment into the child.

Phase 5F2C-FU1 added three properties worth stating separately, because the
original phase asserted the first two and had neither:

- the executable handed to ``subprocess`` is **absolute**, resolved once, and
  never the ambient string ``"git"``;
- the repository's own Git configuration cannot cause a **filter or helper
  program** to run — a repository that could is refused;
- stdout is bounded **during** capture rather than measured after it.

Every repository used by an integration test is a synthetic Git repository
created under pytest's own ``tmp_path``. No real project workspace is used
anywhere.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ai_dev_orchestrator.workspace import git_adapter
from ai_dev_orchestrator.workspace.git_adapter import (
    CONTENT_READING_OPERATIONS,
    FIXED_GIT_OPERATIONS,
    GitAdapterError,
    GitExecutableError,
    GitOperationNotAllowedError,
    build_git_argv,
    find_unsupported_config_keys,
    ordered_preflight_operations,
    parse_config_name_only,
    parse_config_scoped_name_only,
    parse_ls_files_stage,
    parse_ls_files_verbose,
    parse_status_porcelain,
    resolve_git_executable,
    run_fixed_git_operation,
    status_record_path,
)

git_required = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is not installed"
)

# A stand-in absolute path for the pure-argv tests, so they never depend on
# where git happens to live on the machine running them.
FAKE_GIT = os.path.join(os.sep + "opt", "aido-fake", "git.exe")
if os.name == "nt":
    FAKE_GIT = "C:\\aido-fake\\git.exe"


def _real_git() -> str:
    return resolve_git_executable(workspace_root="")


def _init_repo(tmp_path: Path, name: str = "repo") -> Path:
    """Create one synthetic Git repository under ``tmp_path``. Never a real project."""
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    for key, value in (
        ("user.name", "AIDO Test"),
        ("user.email", "aido-test@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
    ):
        subprocess.run(
            ["git", "config", key, value], cwd=repo, check=True, capture_output=True
        )
    (repo / "src").mkdir()
    (repo / "src" / "totals.py").write_bytes(b"a\nb\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


# -- 1. The closed operation set ----------------------------------------------


def test_the_fixed_operation_set_is_exactly_these_eight():
    assert set(FIXED_GIT_OPERATIONS) == {
        "rev_parse_show_toplevel",
        "rev_parse_head",
        "config_list_local",
        "config_list_scoped",
        "ls_files_stage",
        "ls_files_verbose",
        "status_porcelain",
        "diff_one_path",
    }


def test_every_fixed_operation_is_read_only():
    """No mutating subcommand exists in the set, and none can be added at runtime."""
    mutating = {
        "add", "commit", "checkout", "switch", "restore", "reset", "stash",
        "clean", "branch", "tag", "merge", "rebase", "cherry-pick", "revert",
        "apply", "am", "mv", "rm", "fetch", "pull", "push", "clone", "remote",
        "submodule", "hook", "filter-branch", "gc", "update-index",
        "update-ref", "write-tree", "hash-object",
    }
    for operation, template in FIXED_GIT_OPERATIONS.items():
        assert template[0] not in mutating, (operation, template[0])


def test_the_config_operations_only_read_and_only_names():
    """The config probe can neither set a value nor read one."""
    for operation in ("config_list_local", "config_list_scoped"):
        template = FIXED_GIT_OPERATIONS[operation]
        assert template[0] == "config"
        assert "--list" in template
        # --name-only is what keeps configuration *values* out of this process.
        assert "--name-only" in template
        for absent in ("--replace-all", "--add", "--unset", "--edit", "--get"):
            assert absent not in template


def test_the_local_config_probe_does_not_follow_includes():
    """The decision about indirection must not be made by following it."""
    template = FIXED_GIT_OPERATIONS["config_list_local"]
    assert "--local" in template
    assert "--no-includes" in template


def test_every_argv_starts_with_the_absolute_executable_and_safe_global_flags():
    for operation, template in FIXED_GIT_OPERATIONS.items():
        path = "src/totals.py" if None in template else None
        argv = build_git_argv(
            operation, git_executable=FAKE_GIT, repo_relative_path=path
        )
        assert argv[0] == FAKE_GIT
        assert os.path.isabs(argv[0])
        for flag in ("--no-pager", "--no-optional-locks"):
            assert flag in argv, (operation, flag)
        joined = " ".join(argv)
        assert "core.pager=cat" in joined
        assert "core.fsmonitor=false" in joined
        assert "diff.external=" in joined


def test_the_only_variable_component_is_one_path_after_a_double_dash():
    argv = build_git_argv(
        "diff_one_path", git_executable=FAKE_GIT, repo_relative_path="src/totals.py"
    )

    assert argv[-1] == "src/totals.py"
    assert argv[-2] == "--"
    template_and_flags = (
        set(git_adapter._GIT_GLOBAL_ARGS)
        | {item for item in FIXED_GIT_OPERATIONS["diff_one_path"] if item is not None}
        | {FAKE_GIT}
    )
    variable = [item for item in argv if item not in template_and_flags]
    assert variable == ["src/totals.py"]


@pytest.mark.parametrize(
    "operation",
    ["commit", "push", "apply", "git", "status", "rev-parse", "", "STATUS_PORCELAIN"],
)
def test_an_operation_outside_the_fixed_set_is_refused(operation):
    with pytest.raises(GitOperationNotAllowedError):
        build_git_argv(operation, git_executable=FAKE_GIT)


def test_a_path_may_not_be_supplied_to_an_operation_that_takes_none():
    with pytest.raises(GitOperationNotAllowedError):
        build_git_argv(
            "status_porcelain", git_executable=FAKE_GIT, repo_relative_path="src/a.py"
        )


def test_a_path_is_required_by_the_operation_that_takes_one():
    with pytest.raises(GitOperationNotAllowedError):
        build_git_argv("diff_one_path", git_executable=FAKE_GIT)


@pytest.mark.parametrize("path", ["", "--upload-pack=evil", "-c", "src/a\x00b.py"])
def test_an_option_like_or_nul_bearing_path_is_refused(path):
    with pytest.raises(GitOperationNotAllowedError):
        build_git_argv(
            "diff_one_path", git_executable=FAKE_GIT, repo_relative_path=path
        )


# -- 2. Executable resolution (Phase 5F2C-FU1, finding 4) ----------------------


@pytest.mark.parametrize("unqualified", ["git", "git.exe", "", None, "./git"])
def test_an_unqualified_executable_is_never_accepted(unqualified):
    with pytest.raises(GitExecutableError):
        build_git_argv("rev_parse_head", git_executable=unqualified)


def test_build_git_argv_has_no_executable_default():
    """There is no way to fall back to the ambient literal 'git' by omission."""
    import inspect

    signature = inspect.signature(build_git_argv)
    parameter = signature.parameters["git_executable"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    signature = inspect.signature(run_fixed_git_operation)
    parameter = signature.parameters["git_executable"]
    assert parameter.default is inspect.Parameter.empty


@git_required
def test_the_resolved_executable_is_absolute_and_a_real_file():
    resolved = resolve_git_executable(workspace_root="")

    assert os.path.isabs(resolved)
    assert os.path.isfile(resolved)


@git_required
def test_a_git_executable_inside_the_target_workspace_is_refused(tmp_path):
    """The repository being edited may not supply the program that inspects it."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    real = resolve_git_executable(workspace_root="")
    planted = workspace / "tools"
    planted.mkdir()
    shutil.copyfile(real, planted / ("git.exe" if os.name == "nt" else "git"))

    monkeypatched_path = str(planted) + os.pathsep + os.environ.get("PATH", "")
    original = os.environ.get("PATH", "")
    try:
        os.environ["PATH"] = monkeypatched_path
        with pytest.raises(GitExecutableError) as excinfo:
            resolve_git_executable(workspace_root=str(workspace))
        assert "inside the target workspace" in str(excinfo.value)
    finally:
        os.environ["PATH"] = original


def test_no_git_on_the_path_fails_closed(monkeypatch):
    monkeypatch.setattr(git_adapter.shutil, "which", lambda name: None)

    with pytest.raises(GitExecutableError):
        resolve_git_executable(workspace_root="")


def test_a_resolved_path_that_is_not_a_regular_file_fails_closed(
    monkeypatch, tmp_path
):
    directory = tmp_path / "not-a-file"
    directory.mkdir()
    monkeypatch.setattr(git_adapter.shutil, "which", lambda name: str(directory))

    with pytest.raises(GitExecutableError):
        resolve_git_executable(workspace_root="")


def test_the_module_no_longer_exposes_a_bare_git_constant():
    assert not hasattr(git_adapter, "GIT_EXECUTABLE")


# -- 3. How the process is started --------------------------------------------


class _FakePopen:
    """A minimal Popen stand-in for the bounded-capture tests."""

    def __init__(self, chunks: list[bytes], returncode: int = 0):
        import io

        self.stdout = io.BytesIO(b"".join(chunks))
        self._returncode = returncode
        self.killed = False
        # Recorded before the adapter closes the stream, so a test can assert
        # how much was ever pulled into memory.
        self.bytes_consumed = 0
        real_read = self.stdout.read

        def counting_read(size=-1):
            chunk = real_read(size)
            self.bytes_consumed += len(chunk)
            return chunk

        self.stdout.read = counting_read  # type: ignore[method-assign]

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self._returncode


def test_no_shell_is_ever_used_and_the_environment_is_minimal(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return _FakePopen([b""])

    monkeypatch.setenv("AIDO_LITELLM_API_KEY", "SENTINEL_SECRET_KEY")
    monkeypatch.setenv("GITHUB_TOKEN", "SENTINEL_GITHUB_TOKEN")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere" / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "elsewhere"))
    monkeypatch.setattr(git_adapter.subprocess, "Popen", fake_popen)

    run_fixed_git_operation(
        "status_porcelain", git_executable=FAKE_GIT, workspace_root=str(tmp_path)
    )

    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["cwd"] == str(tmp_path)
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL
    # stderr is discarded, which is what leaves exactly one pipe to read.
    assert captured["kwargs"]["stderr"] is subprocess.DEVNULL

    environment = captured["kwargs"]["env"]
    for absent in (
        "AIDO_LITELLM_API_KEY",
        "GITHUB_TOKEN",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
    ):
        assert absent not in environment
    assert "SENTINEL_SECRET_KEY" not in str(environment)
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_OPTIONAL_LOCKS"] == "0"


def test_only_the_fixed_argv_shapes_can_ever_reach_the_child(monkeypatch, tmp_path):
    seen: list[tuple] = []

    def fake_popen(argv, **kwargs):
        seen.append(tuple(argv))
        return _FakePopen([b""])

    monkeypatch.setattr(git_adapter.subprocess, "Popen", fake_popen)

    for operation, template in FIXED_GIT_OPERATIONS.items():
        path = "src/totals.py" if None in template else None
        run_fixed_git_operation(
            operation,
            git_executable=FAKE_GIT,
            workspace_root=str(tmp_path),
            repo_relative_path=path,
        )

    allowed = {
        build_git_argv(
            operation,
            git_executable=FAKE_GIT,
            repo_relative_path="src/totals.py" if None in template else None,
        )
        for operation, template in FIXED_GIT_OPERATIONS.items()
    }
    assert set(seen) == allowed
    for argv in seen:
        assert os.path.isabs(argv[0])


def test_output_is_bounded_during_capture_and_kills_the_child(monkeypatch, tmp_path):
    """The cap is enforced by the read loop, not measured afterwards."""
    oversized = b"x" * (git_adapter.MAX_GIT_OUTPUT_BYTES + git_adapter._READ_CHUNK_BYTES)
    fake = _FakePopen([oversized])
    monkeypatch.setattr(git_adapter.subprocess, "Popen", lambda *a, **k: fake)

    with pytest.raises(GitAdapterError) as excinfo:
        run_fixed_git_operation(
            "status_porcelain", git_executable=FAKE_GIT, workspace_root=str(tmp_path)
        )

    assert "killed mid-stream" in str(excinfo.value)
    assert fake.killed, "the child must be killed once the cap is passed"
    # At most one chunk beyond the cap is ever pulled into memory — the whole
    # oversized stream is never read.
    assert fake.bytes_consumed <= (
        git_adapter.MAX_GIT_OUTPUT_BYTES + git_adapter._READ_CHUNK_BYTES
    )
    assert fake.bytes_consumed < len(oversized) + git_adapter._READ_CHUNK_BYTES


def test_a_timeout_kills_the_child_and_fails_closed(monkeypatch, tmp_path):
    class _HangingPopen(_FakePopen):
        def __init__(self):
            super().__init__([b""])

    fake = _HangingPopen()
    monkeypatch.setattr(git_adapter.subprocess, "Popen", lambda *a, **k: fake)

    # Fire the watchdog immediately rather than waiting 30 real seconds.
    monkeypatch.setattr(git_adapter, "GIT_TIMEOUT_SECONDS", 0.0)

    with pytest.raises(GitAdapterError) as excinfo:
        run_fixed_git_operation(
            "status_porcelain", git_executable=FAKE_GIT, workspace_root=str(tmp_path)
        )
    assert "exceeded" in str(excinfo.value)


def test_a_missing_git_executable_fails_closed(monkeypatch, tmp_path):
    def fake_popen(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(git_adapter.subprocess, "Popen", fake_popen)
    with pytest.raises(GitExecutableError):
        run_fixed_git_operation(
            "status_porcelain", git_executable=FAKE_GIT, workspace_root=str(tmp_path)
        )


def test_a_nonzero_return_code_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(
        git_adapter.subprocess, "Popen", lambda *a, **k: _FakePopen([b""], returncode=128)
    )
    with pytest.raises(GitAdapterError):
        run_fixed_git_operation(
            "status_porcelain", git_executable=FAKE_GIT, workspace_root=str(tmp_path)
        )


def test_non_utf8_output_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(
        git_adapter.subprocess, "Popen", lambda *a, **k: _FakePopen([b"\xff\xfe bad"])
    )
    with pytest.raises(GitAdapterError) as excinfo:
        run_fixed_git_operation(
            "ls_files_stage", git_executable=FAKE_GIT, workspace_root=str(tmp_path)
        )
    assert "not valid UTF-8" in str(excinfo.value)


def test_the_result_carries_no_stderr_field():
    """stderr goes to DEVNULL; there is no field that could carry repo content."""
    assert "stderr" not in git_adapter.GitResult.__dataclass_fields__


# -- 4. The configuration gate (Phase 5F2C-FU1, finding 3) ---------------------


def test_the_preflight_order_puts_every_content_reading_operation_last():
    order = ordered_preflight_operations()

    assert set(order) <= set(FIXED_GIT_OPERATIONS)
    gates = [name for name in order if name not in CONTENT_READING_OPERATIONS]
    content = [name for name in order if name in CONTENT_READING_OPERATIONS]
    assert content, "the order must actually contain a content-reading operation"
    last_gate = max(order.index(name) for name in gates)
    first_content = min(order.index(name) for name in content)
    assert last_gate < first_content


def test_the_config_gate_runs_before_the_index_gate_and_both_before_status():
    order = list(ordered_preflight_operations())

    assert order.index("config_list_local") < order.index("config_list_scoped")
    assert order.index("config_list_scoped") < order.index("ls_files_stage")
    assert order.index("ls_files_stage") < order.index("status_porcelain")


@pytest.mark.parametrize(
    "key",
    [
        "filter.evil.clean",
        "filter.evil.smudge",
        "filter.evil.process",
        "filter.evil.required",
        "filter.lfs.clean",
        "FILTER.Evil.Clean",
        "include.path",
        "includeIf.gitdir:/x.path",
        "core.fsmonitor",
        "core.hooksPath",
        "core.pager",
        "core.editor",
        "core.sshCommand",
        "core.gitProxy",
        "core.askpass",
        "core.attributesFile",
        "core.excludesFile",
        "core.alternateRefsCommand",
        "diff.external",
        "diff.mine.command",
        "diff.mine.textconv",
        "merge.mine.driver",
        "difftool.x.cmd",
        "mergetool.x.cmd",
        "credential.helper",
        "pager.log",
        "alias.st",
        "gpg.program",
        "gpg.x509.program",
        "sequence.editor",
        "uploadpack.packObjectsHook",
        "protocol.ext.allow",
        "extensions.worktreeConfig",
        "ssh.variant",
        "remote.origin.uploadpack",
        "remote.origin.proxy",
    ],
)
def test_execution_and_indirection_capable_keys_are_refused(key):
    assert find_unsupported_config_keys((key,)) == (key.lower(),)


@pytest.mark.parametrize(
    "key",
    [
        "core.repositoryformatversion",
        "core.filemode",
        "core.bare",
        "core.autocrlf",
        "core.ignorecase",
        "core.symlinks",
        "core.logallrefupdates",
        "user.name",
        "user.email",
        "commit.gpgsign",
        "branch.main.remote",
        "remote.origin.url",
        "remote.origin.fetch",
        "push.default",
        "color.ui",
        "diff.renames",
        "merge.conflictstyle",
    ],
)
def test_ordinary_keys_are_not_refused(key):
    assert find_unsupported_config_keys((key,)) == ()


def test_unsupported_keys_are_deduplicated_and_sorted():
    keys = ("filter.b.clean", "filter.a.clean", "FILTER.A.CLEAN", "user.name")

    assert find_unsupported_config_keys(keys) == ("filter.a.clean", "filter.b.clean")


def test_config_name_only_output_is_parsed_into_key_names():
    assert parse_config_name_only("user.name\x00filter.evil.clean\x00") == (
        "user.name",
        "filter.evil.clean",
    )


def test_scoped_config_excludes_this_modules_own_command_scope_flags():
    stdout = (
        "command\x00core.pager\x00"
        "local\x00user.name\x00"
        "global\x00filter.lfs.clean\x00"
    )

    assert parse_config_scoped_name_only(stdout) == ("user.name", "filter.lfs.clean")


def test_an_unrecognized_config_scope_fails_closed():
    with pytest.raises(GitAdapterError):
        parse_config_scoped_name_only("mystery\x00user.name\x00")


def test_a_scope_with_no_key_fails_closed():
    with pytest.raises(GitAdapterError):
        parse_config_scoped_name_only("local")


# -- 5. Parsers ----------------------------------------------------------------


def test_ls_files_stage_is_parsed_into_entries():
    stdout = "100644 abc123 0\tsrc/a.py\x00160000 def456 0\tvendor/sub\x00"
    entries = parse_ls_files_stage(stdout)

    assert [(e.mode, e.stage, e.path) for e in entries] == [
        ("100644", 0, "src/a.py"),
        ("160000", 0, "vendor/sub"),
    ]


@pytest.mark.parametrize(
    "stdout",
    [
        "100644 abc123 0 src/a.py\x00",
        "100644 abc123\tsrc/a.py\x00",
        "100644 abc x\tsrc/a.py\x00",
    ],
)
def test_a_malformed_index_record_is_refused_rather_than_skipped(stdout):
    with pytest.raises(GitAdapterError):
        parse_ls_files_stage(stdout)


def test_ls_files_verbose_is_parsed_into_tag_path_pairs():
    stdout = "H src/a.py\x00S src/b.py\x00h src/c.py\x00"
    assert parse_ls_files_verbose(stdout) == (
        ("H", "src/a.py"),
        ("S", "src/b.py"),
        ("h", "src/c.py"),
    )


def test_a_malformed_verbose_record_is_refused():
    with pytest.raises(GitAdapterError):
        parse_ls_files_verbose("Hsrc/a.py\x00")


def test_status_porcelain_consumes_the_second_field_of_a_rename():
    stdout = "R  new.py\x00old.py\x00 M other.py\x00"
    records = parse_status_porcelain(stdout)

    assert records == ("R  new.py", " M other.py")
    assert status_record_path(" M other.py") == "other.py"


def test_a_malformed_status_record_is_refused():
    with pytest.raises(GitAdapterError):
        status_record_path("XY")


# -- 6. Integration against synthetic repositories -----------------------------


@git_required
def test_a_clean_synthetic_repository_reports_clean(tmp_path):
    repo = _init_repo(tmp_path)
    git = _real_git()

    toplevel = run_fixed_git_operation(
        "rev_parse_show_toplevel", git_executable=git, workspace_root=str(repo)
    ).stdout.strip()
    assert os.path.normcase(os.path.realpath(toplevel)) == os.path.normcase(
        os.path.realpath(str(repo))
    )

    run_fixed_git_operation(
        "rev_parse_head", git_executable=git, workspace_root=str(repo)
    )
    assert (
        parse_status_porcelain(
            run_fixed_git_operation(
                "status_porcelain", git_executable=git, workspace_root=str(repo)
            ).stdout
        )
        == ()
    )

    entries = parse_ls_files_stage(
        run_fixed_git_operation(
            "ls_files_stage", git_executable=git, workspace_root=str(repo)
        ).stdout
    )
    assert [(e.mode, e.stage, e.path) for e in entries] == [
        ("100644", 0, "src/totals.py")
    ]


@git_required
def test_a_clean_repositorys_config_is_supported(tmp_path):
    """The gate must not refuse an ordinary repository."""
    repo = _init_repo(tmp_path)
    git = _real_git()

    keys = parse_config_name_only(
        run_fixed_git_operation(
            "config_list_local",
            git_executable=git,
            workspace_root=str(repo),
            allowed_returncodes=(0, 1),
        ).stdout
    )
    assert keys, "an initialized repository always has some local config"
    assert find_unsupported_config_keys(keys) == ()


@git_required
def test_a_configured_clean_filter_is_visible_to_the_gate(tmp_path):
    repo = _init_repo(tmp_path)
    git = _real_git()
    subprocess.run(
        ["git", "config", "filter.evil.clean", "cmd /c echo x"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    keys = parse_config_name_only(
        run_fixed_git_operation(
            "config_list_local",
            git_executable=git,
            workspace_root=str(repo),
            allowed_returncodes=(0, 1),
        ).stdout
    )
    assert find_unsupported_config_keys(keys) == ("filter.evil.clean",)


@git_required
def test_an_include_directive_is_seen_without_being_followed(tmp_path):
    """The local probe must report include.path rather than resolving it."""
    repo = _init_repo(tmp_path)
    git = _real_git()
    included = tmp_path / "extra.cfg"
    included.write_text("[filter \"hidden\"]\n\tclean = cmd /c echo x\n", encoding="utf-8")
    subprocess.run(
        ["git", "config", "include.path", str(included).replace("\\", "/")],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    keys = parse_config_name_only(
        run_fixed_git_operation(
            "config_list_local",
            git_executable=git,
            workspace_root=str(repo),
            allowed_returncodes=(0, 1),
        ).stdout
    )

    assert "include.path" in keys
    # --no-includes means the hidden filter was NOT pulled in by this probe.
    assert "filter.hidden.clean" not in keys
    assert "include.path" in find_unsupported_config_keys(keys)


@git_required
def test_an_unstaged_modification_shows_up(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "src" / "totals.py").write_bytes(b"a\nCHANGED\n")

    records = parse_status_porcelain(
        run_fixed_git_operation(
            "status_porcelain", git_executable=_real_git(), workspace_root=str(repo)
        ).stdout
    )
    assert [status_record_path(record) for record in records] == ["src/totals.py"]


@git_required
def test_an_untracked_file_shows_up(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "stray.txt").write_bytes(b"x\n")

    records = parse_status_porcelain(
        run_fixed_git_operation(
            "status_porcelain", git_executable=_real_git(), workspace_root=str(repo)
        ).stdout
    )
    assert [status_record_path(record) for record in records] == ["stray.txt"]


@git_required
def test_a_repository_with_no_commit_has_no_head(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)

    with pytest.raises(GitAdapterError):
        run_fixed_git_operation(
            "rev_parse_head", git_executable=_real_git(), workspace_root=str(repo)
        )


@git_required
def test_the_one_path_diff_is_bounded_to_that_path(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "src" / "totals.py").write_bytes(b"a\nCHANGED\n")
    (repo / "src" / "other.py").write_bytes(b"SENTINEL_OTHER_FILE\n")
    subprocess.run(
        ["git", "add", "src/other.py"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "other"], cwd=repo, check=True, capture_output=True
    )
    (repo / "src" / "other.py").write_bytes(b"SENTINEL_OTHER_FILE_CHANGED\n")

    diff = run_fixed_git_operation(
        "diff_one_path",
        git_executable=_real_git(),
        workspace_root=str(repo),
        repo_relative_path="src/totals.py",
    ).stdout

    assert "src/totals.py" in diff
    assert "SENTINEL_OTHER_FILE_CHANGED" not in diff
    assert "other.py" not in diff


# -- 7. Nothing else is reachable ---------------------------------------------


def test_the_module_imports_no_client_no_socket_and_no_shell_helper():
    source = Path(git_adapter.__file__).read_text(encoding="utf-8")
    for absent in (
        "import socket",
        "import httpx",
        "import requests",
        "os.system",
        "shell=True",
        "LLMClient",
        "GitHubClient",
    ):
        assert absent not in source, absent
    assert "shell=False" in source


def test_no_network_git_operation_exists():
    joined = " ".join(
        " ".join(str(item) for item in template)
        for template in FIXED_GIT_OPERATIONS.values()
    )
    for absent in ("fetch", "pull", "push", "clone", "remote", "ls-remote"):
        assert absent not in joined, absent


def test_the_unsupported_replacefile_flag_is_not_referenced_here():
    source = Path(git_adapter.__file__).read_text(encoding="utf-8")
    assert "REPLACEFILE" not in source
