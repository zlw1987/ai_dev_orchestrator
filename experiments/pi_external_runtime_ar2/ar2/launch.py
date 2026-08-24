"""Pinned Node + Pi launch identity for AR2.

AR0 unknown U-1: prefer ``<absolute node.exe> <absolute pi dist/cli.js>`` over
running ``pi.cmd`` through ``cmd.exe``. AR0-FU1 section 2 sharpened it: two Node
installations exist on this machine (Program Files and an nvm shim), so "which
node" is ambiguous unless it is pinned.

If Node-direct launch does not work, this module reports it. It does not
silently fall back to a different launch architecture.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # noqa: S404 - pinned absolute argv, shell=False
from dataclasses import dataclass

PINNED_PI_VERSION = "0.84.2"
PI_PACKAGE_NAME = "@earendil-works/pi-coding-agent"


class LaunchIdentityError(Exception):
    """The runtime could not be pinned to the exact expected identity."""


@dataclass(frozen=True)
class RuntimeIdentity:
    """The exact, pinned executables AR2 will launch."""

    node_executable: str
    pi_cli_js: str
    pi_package_root: str
    reported_version: str
    launch_shape: str  # always "node_direct" when this object exists


def _resolve_node_executable() -> str:
    candidate = shutil.which("node")
    if not candidate:
        raise LaunchIdentityError("launch error: 'node' was not found on PATH")
    resolved = os.path.realpath(candidate)
    if not os.path.isabs(resolved) or not os.path.isfile(resolved):
        raise LaunchIdentityError(
            "launch error: the resolved node executable is not an existing regular file"
        )
    return resolved


def _resolve_pi_package_root() -> str:
    """Find the installed Pi package root from the npm bin shim's location."""
    shim = shutil.which("pi")
    if not shim:
        raise LaunchIdentityError("launch error: 'pi' was not found on PATH")
    npm_bin = os.path.dirname(os.path.realpath(shim))
    candidates = [
        os.path.join(npm_bin, "node_modules", *PI_PACKAGE_NAME.split("/")),
        os.path.join(npm_bin, "..", "node_modules", *PI_PACKAGE_NAME.split("/")),
    ]
    for candidate in candidates:
        normalized = os.path.realpath(candidate)
        if os.path.isfile(os.path.join(normalized, "package.json")):
            return normalized
    raise LaunchIdentityError(
        "launch error: the installed Pi package root could not be located next to the 'pi' shim"
    )


def resolve_runtime_identity(*, expected_version: str = PINNED_PI_VERSION) -> RuntimeIdentity:
    """Pin Node and Pi, prove the version, and prove Node-direct launch works.

    The version is read by launching **the pinned pair** -- not by running
    ``pi.cmd`` -- so a passing check simultaneously answers AR0 U-1 (does
    Node-direct launch work?) and AR0-FU1 risk N6 (is this the reviewed Pi?).

    A mismatch is terminal. No prompt is ever sent afterwards.
    """
    node_executable = _resolve_node_executable()
    package_root = _resolve_pi_package_root()
    cli_js = os.path.realpath(os.path.join(package_root, "dist", "cli.js"))
    if not os.path.isfile(cli_js):
        raise LaunchIdentityError("launch error: the pinned Pi dist/cli.js does not exist")

    try:
        completed = subprocess.run(  # noqa: S603 - pinned absolute argv, shell=False
            [node_executable, cli_js, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except OSError as exc:
        raise LaunchIdentityError(
            f"launch error: Node-direct Pi launch failed to start: {exc}"
        ) from exc

    if completed.returncode != 0:
        raise LaunchIdentityError(
            "launch error: Node-direct Pi launch exited "
            f"{completed.returncode}; no fallback launch architecture is attempted"
        )

    reported = completed.stdout.decode("utf-8", "replace").strip()
    if reported != expected_version:
        raise LaunchIdentityError(
            "launch error: Pi version mismatch. This experiment is pinned to "
            f"{expected_version!r} and the runtime reported {reported!r}. "
            "Terminal: no prompt is sent."
        )

    return RuntimeIdentity(
        node_executable=node_executable,
        pi_cli_js=cli_js,
        pi_package_root=package_root,
        reported_version=reported,
        launch_shape="node_direct",
    )


def build_pi_argv(
    identity: RuntimeIdentity,
    *,
    extension_entry: str,
    tool_allowlist: tuple[str, ...],
    provider: str,
    model: str,
) -> tuple[str, ...]:
    """The exact argv for the one supervised Pi run.

    Every flag here was confirmed present in ``pi --help`` for 0.84.2. No flag
    is passed that this version does not support.

    ``--tools`` is the SECURITY CONTROL: it filters the tool *registry*, so no
    built-in filesystem tool remains callable. ``--no-builtin-tools`` is passed
    as belt-and-braces only; AR0-FU1 4.1f proved it does not filter the registry
    and must not be relied on.
    """
    if not tool_allowlist:
        raise LaunchIdentityError("launch error: the tool allowlist must not be empty")
    return (
        identity.node_executable,
        identity.pi_cli_js,
        "--mode",
        "rpc",
        "--no-session",
        "--no-extensions",
        "--extension",
        extension_entry,
        "--tools",
        ",".join(tool_allowlist),
        "--no-builtin-tools",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--no-approve",
        "--offline",
        "--provider",
        provider,
        "--model",
        model,
    )
