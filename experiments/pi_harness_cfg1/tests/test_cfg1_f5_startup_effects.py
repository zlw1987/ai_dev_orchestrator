"""F-5: preservation regressions for Pi 1.0.3 startup effects (PE-4A F-5).

These pin ONLY facts that already hold in the shipped CFG1 launch boundary and
that the F-5 analysis depends on. They do NOT close F5-A (the out-of-tree
``.pi-native-quarantine`` delete) or F5-C (the OS-home credential-path
existence probe): both remain open live-launch blockers, and nothing here
claims otherwise.

* F5-B -- Pi's startup writes (``auth.json``, ``models-store.json``, the
  ``proper-lockfile`` ``*.lock`` directories) land under ``PI_CODING_AGENT_DIR``,
  whose ONLY source is the verified issuance record's config dir -- a direct
  child of the AIDO-minted experiment root -- and L27's recursive removal of
  that root takes them with it without following a reparse point planted
  inside it.
* Environment -- the child environment is a positive allowlist, so no ambient
  name can substitute Pi's package dir (``PI_PACKAGE_DIR``: the F5-A target
  stays a pure function of the proven package root), enable the managed-install
  staging delete (``PI_MANAGED_INSTALL_ROOT``), preload code (``NODE_OPTIONS``),
  or supply the Google project/location/credential names that would let the
  Vertex availability check succeed. That last point bounds what the probe can
  DECIDE; it does not redirect the probe's path, which is still derived from
  the OS-resolved home (F5-C, open).

Pure Python, synthetic workspaces only; no Node, Pi, network, model or real
credential is touched.
"""

from __future__ import annotations

import ntpath
import os
from pathlib import Path

import pytest
from cfg1_doubles import SYNTHETIC_BASE_URL, SYNTHETIC_CREDENTIAL
from cfg1_issuance_cleanup import discard_config_for_test
from conftest import make_directory_redirect

from pi_harness_cfg1 import config_issuance, run_workspace
from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config
from pi_harness_cfg1.environment import BASE_WINDOWS_NAMES, build_cfg1_child_environment
from pi_harness_cfg1.identity import CREDENTIAL_ENV_VAR_NAME

_NODE = r"C:\Program Files\nodejs\node.exe"

#: Ambient names whose presence in the CHILD would change an F-5 derivation.
_F5_DECOY_NAMES = (
    "PI_PACKAGE_DIR",
    "PI_MANAGED_INSTALL_ROOT",
    "PI_CODING_AGENT_SESSION_DIR",
    "NODE_OPTIONS",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_CLOUD_API_KEY",
    "GOOGLE_CLOUD_PROJECT",
    "GCLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "USERPROFILE",
    "HOME",
    "APPDATA",
    "LOCALAPPDATA",
    "HOMEDRIVE",
    "HOMEPATH",
)


def _inside_strictly(candidate: str, root: str) -> bool:
    candidate_n = ntpath.normcase(ntpath.normpath(candidate))
    root_n = ntpath.normcase(ntpath.normpath(root))
    return candidate_n != root_n and ntpath.commonpath([candidate_n, root_n]) == root_n


def test_f5b_pi_agent_dir_is_the_issued_config_dir_directly_under_the_owned_root(
    git_executable,
):
    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    config = None
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        built = build_cfg1_child_environment(
            ambient_environ={"SystemRoot": r"C:\Windows"},
            node_executable=_NODE,
            generated_config=config,
            workspace=workspace,
            credential_value=SYNTHETIC_CREDENTIAL,
        )
        agent_dir = built.environment["PI_CODING_AGENT_DIR"]
        derived_config_dir, _settings, _models = config_issuance.derive_cfg1_config_paths(
            workspace
        )
        assert agent_dir == derived_config_dir
        # A direct child of the root L27 removes -- never the root itself,
        # never Pi's cwd (the repo root), never anywhere else.
        assert ntpath.dirname(agent_dir) == workspace.experiment_root
        assert _inside_strictly(agent_dir, workspace.experiment_root)
        assert not _inside_strictly(agent_dir, workspace.workspace_root)
        # Pi derives every F5-B path as ``join(agentDir, <literal>)``.
        for pi_written in ("auth.json", "models-store.json", "auth.json.lock"):
            assert _inside_strictly(ntpath.join(agent_dir, pi_written), workspace.experiment_root)
    finally:
        if config is not None:
            discard_config_for_test(config.issuance_token)
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_f5b_l27_removes_pi_startup_extras_from_the_config_dir(git_executable):
    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    config = write_cfg1_pi_config(workspace, arm_id="R", base_url=SYNTHETIC_BASE_URL)
    config_dir, _settings, _models = config_issuance.derive_cfg1_config_paths(workspace)
    discard_config_for_test(config.issuance_token)

    # What Pi 1.0.3 startup leaves behind (AuthStorage, FileModelsStore,
    # proper-lockfile with realpath:false -> "<file>.lock" directories).
    with open(os.path.join(config_dir, "auth.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")
    with open(os.path.join(config_dir, "models-store.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")
    os.mkdir(os.path.join(config_dir, "auth.json.lock"))
    os.mkdir(os.path.join(config_dir, "settings.json.lock"))

    experiment_root = workspace.experiment_root
    result = run_workspace.remove_cfg1_run_workspace(workspace)

    assert result["removed"] is True
    assert result["residual_file_count"] == 0
    assert not os.path.exists(experiment_root)


def test_f5b_l27_does_not_follow_a_reparse_point_planted_in_the_config_dir(
    tmp_path, git_executable
):
    outside = tmp_path / "outside_target"
    outside.mkdir()
    sentinel = outside / "must_survive.txt"
    sentinel.write_text("not AIDO's", encoding="utf-8")

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    config = write_cfg1_pi_config(workspace, arm_id="E", base_url=SYNTHETIC_BASE_URL)
    config_dir, _settings, _models = config_issuance.derive_cfg1_config_paths(workspace)
    discard_config_for_test(config.issuance_token)
    try:
        make_directory_redirect(Path(config_dir) / "planted_redirect", outside)
    except OSError:
        run_workspace.remove_cfg1_run_workspace(workspace)
        pytest.skip("no directory-redirect mechanism on this platform")

    experiment_root = workspace.experiment_root
    result = run_workspace.remove_cfg1_run_workspace(workspace)

    assert result["removed"] is True
    assert not os.path.exists(experiment_root)
    assert sentinel.read_text(encoding="utf-8") == "not AIDO's"


def test_f5_launch_relevant_ambient_names_never_reach_the_child(git_executable):
    ambient = {"SystemRoot": r"C:\Windows", "PATH": r"C:\decoy"}
    for name in _F5_DECOY_NAMES:
        ambient[name] = r"C:\decoy\\" + name
    # An ambient PI_CODING_AGENT_DIR must be overridden, never forwarded.
    ambient["PI_CODING_AGENT_DIR"] = r"C:\Users\decoy\.pi\agent"

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    config = None
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        built = build_cfg1_child_environment(
            ambient_environ=ambient,
            node_executable=_NODE,
            generated_config=config,
            workspace=workspace,
            credential_value=SYNTHETIC_CREDENTIAL,
        )
        child = built.as_launch_snapshot()
        derived_config_dir = config_issuance.derive_cfg1_config_paths(workspace)[0]
    finally:
        if config is not None:
            discard_config_for_test(config.issuance_token)
        run_workspace.remove_cfg1_run_workspace(workspace)

    for name in _F5_DECOY_NAMES:
        assert name not in child, name
    assert child["PI_CODING_AGENT_DIR"] == derived_config_dir
    assert "decoy" not in child["PATH"].lower()
    expected = {
        name for name in BASE_WINDOWS_NAMES if name in ambient
    } | {
        "PATH",
        "PI_CODING_AGENT_DIR",
        "PI_OFFLINE",
        "PI_SKIP_VERSION_CHECK",
        "PI_TELEMETRY",
        CREDENTIAL_ENV_VAR_NAME,
    }
    assert set(child) == expected
