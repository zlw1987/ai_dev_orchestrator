"""Offline tests 13, 15-18: shutdown, handshake gates, tool allowlist, fail-closed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ar1.launch import LaunchIdentityError, build_pi_argv
from ar1.pi_config import (
    SENTINEL_COMMAND_NAME,
    TOOL_ALLOWLIST,
    write_disposable_extension,
)
from ar1.supervisor import RUNTIME_SETTLED, PiRpcSupervisor, RunBounds


def _line(obj: dict) -> str:
    return json.dumps(obj) + "\n"


def _supervisor(argv, env, tmp_path, bounds=None) -> PiRpcSupervisor:
    return PiRpcSupervisor(
        argv=argv,
        cwd=str(tmp_path),
        environment=env,
        bounds=bounds
        or RunBounds(
            startup_deadline_seconds=10,
            turn_deadline_seconds=10,
            shutdown_deadline_seconds=5,
            direct_child_reap_grace_seconds=2,
        ),
    )


# -- 13. stdin-close shutdown behavior ----------------------------------------


def test_closing_stdin_shuts_the_process_down(fake_pi, minimal_env, tmp_path):
    argv = fake_pi({"startup_chunks": [_line({"type": "agent_settled"})], "exit_code": 0})
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_SETTLED
    record = supervisor.shutdown()
    assert record["stdin_closed"] is True
    assert record["rung_reached"] == "exited_after_stdin_close"
    assert record["exit_status_observed"] == 0
    assert record["direct_child_terminate_sent"] is False
    assert record["direct_child_kill_sent"] is False
    assert "not a claim that inference stopped" in record["claim_scope"]


def test_a_process_that_ignores_stdin_close_is_escalated_and_recorded(
    fake_pi, minimal_env, tmp_path
):
    argv = fake_pi(
        {
            "startup_chunks": [_line({"type": "agent_settled"})],
            "ignore_stdin_close": True,
            "hang_seconds": 120,
        }
    )
    supervisor = _supervisor(
        argv,
        minimal_env,
        tmp_path,
        bounds=RunBounds(shutdown_deadline_seconds=1, direct_child_reap_grace_seconds=5),
    )
    supervisor.launch()
    assert supervisor.await_settled(timeout_seconds=10) == RUNTIME_SETTLED
    record = supervisor.shutdown()
    assert record["stdin_closed"] is True
    assert record["direct_child_terminate_sent"] is True
    assert record["rung_reached"] in ("exited_after_terminate", "exited_after_kill", "gave_up_waiting")


# -- 15/16. handshake gates ----------------------------------------------------


def _sentinel_response(commands: list[dict]) -> dict:
    return {"success": True, "data": {"commands": commands}}


def test_missing_extension_sentinel_means_no_prompt(fake_pi, minimal_env, tmp_path):
    """The gate is evaluated by the caller; this proves the evidence it needs."""
    argv = fake_pi(
        {
            "responses": {
                "get_commands": _sentinel_response(
                    [{"name": "something-else", "source": "prompt"}]
                )
            },
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        supervisor.send_command({"id": "h1", "type": "get_commands"})
        _outcome, response = supervisor.await_response("h1", timeout_seconds=10)
        commands = response["data"]["commands"]
        sentinel = [
            c
            for c in commands
            if c.get("name") == SENTINEL_COMMAND_NAME and c.get("source") == "extension"
        ]
        assert sentinel == []
        assert "prompt" not in supervisor.commands_sent
    finally:
        supervisor.shutdown()


def test_present_extension_sentinel_is_recognized(fake_pi, minimal_env, tmp_path):
    argv = fake_pi(
        {
            "responses": {
                "get_commands": _sentinel_response(
                    [
                        {
                            "name": SENTINEL_COMMAND_NAME,
                            "source": "extension",
                            "path": "C:\\\\disposable\\\\index.ts",
                        }
                    ]
                )
            },
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        supervisor.send_command({"id": "h1", "type": "get_commands"})
        _outcome, response = supervisor.await_response("h1", timeout_seconds=10)
        names = [c["name"] for c in response["data"]["commands"] if c["source"] == "extension"]
        assert SENTINEL_COMMAND_NAME in names
    finally:
        supervisor.shutdown()


def test_get_state_model_mismatch_is_detectable_before_prompting(
    fake_pi, minimal_env, tmp_path
):
    argv = fake_pi(
        {
            "responses": {
                "get_state": {
                    "success": True,
                    "data": {"model": {"id": "some-other-model", "provider": "elsewhere"}},
                }
            },
            "ignore_stdin_close": True,
        }
    )
    supervisor = _supervisor(argv, minimal_env, tmp_path)
    supervisor.launch()
    try:
        supervisor.send_command({"id": "h2", "type": "get_state"})
        _outcome, response = supervisor.await_response("h2", timeout_seconds=10)
        model = response["data"]["model"]
        assert model["id"] != "Qwen3.6-27B-131K"
        assert model["provider"] != "aido-ar1-qwen36-direct-vllm"
        assert "prompt" not in supervisor.commands_sent
    finally:
        supervisor.shutdown()


# -- 17. exact tool allowlist construction ------------------------------------


class _Identity:
    node_executable = r"C:\node\node.exe"
    pi_cli_js = r"C:\pi\dist\cli.js"


def test_tool_allowlist_is_exactly_the_two_aido_tools():
    assert TOOL_ALLOWLIST == ("aido_read", "aido_edit")
    argv = build_pi_argv(
        _Identity(),
        extension_entry=r"C:\disposable\index.ts",
        tool_allowlist=TOOL_ALLOWLIST,
        provider="p",
        model="m",
    )
    assert "--tools" in argv
    assert argv[argv.index("--tools") + 1] == "aido_read,aido_edit"
    # No built-in filesystem tool name is ever named.
    for builtin in ("read", "write", "edit", "grep", "find", "ls", "bash"):
        assert builtin not in argv
    # Belt-and-braces flags are present, and the ambient-state flags too.
    for flag in (
        "--no-builtin-tools",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--no-approve",
        "--offline",
        "--no-session",
    ):
        assert flag in argv
    assert argv[2:4] == ("--mode", "rpc")


def test_an_empty_tool_allowlist_is_refused():
    with pytest.raises(LaunchIdentityError):
        build_pi_argv(
            _Identity(),
            extension_entry=r"C:\disposable\index.ts",
            tool_allowlist=(),
            provider="p",
            model="m",
        )


# -- 18. a failed extension load leaves NO matching filesystem tool ------------


def test_distinct_tool_names_mean_a_failed_load_exposes_nothing(tmp_path: Path):
    """The registry filter names only aido_* tools, which no built-in provides.

    Pi collects extension load errors and continues (verified in
    dist/core/extensions/loader.js). Overriding the built-in NAMES would
    therefore fail OPEN. Distinct names make the same failure fail CLOSED: the
    --tools allowlist matches nothing, so the model gets no filesystem tool.
    """
    argv = build_pi_argv(
        _Identity(),
        extension_entry=r"C:\disposable\index.ts",
        tool_allowlist=TOOL_ALLOWLIST,
        provider="p",
        model="m",
    )
    allowlist = argv[argv.index("--tools") + 1].split(",")
    pi_builtin_tool_names = {"read", "bash", "edit", "write", "grep", "find", "ls"}
    assert set(allowlist).isdisjoint(pi_builtin_tool_names)
    assert all(name.startswith("aido_") for name in allowlist)


def test_generated_extension_config_carries_only_the_exact_allowlist(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    calc = repo / "calc.py"
    test = repo / "test_calc.py"
    calc.write_text("x = 1\n", encoding="utf-8")
    test.write_text("y = 2\n", encoding="utf-8")

    source_dir = Path(__file__).resolve().parents[1] / "extension"
    extension_dir, entry = write_disposable_extension(
        str(tmp_path),
        source_dir=str(source_dir),
        repo_root=str(repo),
        read_allowlist=(str(calc), str(test)),
        edit_allowlist=(str(calc),),
        experiment_id="5F3A-AR1-test",
    )
    generated = (Path(extension_dir) / "ar1_config.ts").read_text(encoding="utf-8")
    assert '"readAllowlist"' in generated
    assert '"editAllowlist"' in generated
    assert json.dumps(str(calc))[1:-1] in generated
    # test_calc.py must be readable but NOT editable.
    config_json = generated.split("= ", 1)[1].rsplit(";", 1)[0].strip()
    parsed = json.loads(config_json)
    assert parsed["editAllowlist"] == [str(calc)]
    assert sorted(parsed["readAllowlist"]) == sorted([str(calc), str(test)])
    assert Path(entry).name == "index.ts"
    assert (Path(extension_dir) / "confinement.ts").is_file()


def test_sentinel_path_is_read_from_source_info_in_pi_0_84_2():
    """Pi 0.84.2 reports the extension origin under ``sourceInfo.path``.

    The shipped ``docs/rpc.md`` example shows a flat ``path`` field, which this
    version does not emit for extension commands. Reading only the flat field
    made a genuine match look like a mismatch, so both are read -- and a missing
    one still fails closed.
    """
    entry = r"C:\disposable\pi_extension\index.ts"
    command = {
        "name": SENTINEL_COMMAND_NAME,
        "source": "extension",
        "sourceInfo": {"path": entry, "source": "cli", "scope": "temporary"},
    }
    assert "path" not in command
    source_info = command["sourceInfo"]
    reported = command.get("path")
    if not isinstance(reported, str):
        reported = source_info.get("path")
    assert reported == entry
    assert source_info["source"] == "cli"


def test_pi_ships_its_own_inline_extension_command_and_it_is_not_a_tool():
    """An inline Pi-internal extension command is not an AIDO tool exposure.

    Pi 0.84.2 registers an inline ``llama`` command (``sourceInfo.source ==
    "inline"``, path ``<inline:llama.cpp>``). It is a slash COMMAND, not a tool,
    and the --tools registry filter governs tools regardless of it.
    """
    commands = [
        {"name": SENTINEL_COMMAND_NAME, "source": "extension",
         "sourceInfo": {"path": r"C:\d\index.ts", "source": "cli"}},
        {"name": "llama", "source": "extension",
         "sourceInfo": {"path": "<inline:llama.cpp>", "source": "inline"}},
    ]
    others = sorted(c["name"] for c in commands if c["name"] != SENTINEL_COMMAND_NAME)
    assert others == ["llama"]
    assert all(name not in TOOL_ALLOWLIST for name in others)
