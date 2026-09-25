"""T-142 - T-155: FU15 Finding A -- the L9 Windows directory-pin authority.

Every row here depends on a Win32 semantic, so every row must ACTUALLY EXECUTE
on win32 (Sec. 37.6). A skipped Windows authority regression on the target
platform proves nothing and is explicitly not an acceptable LIVE-S1 input, so
these tests are marked ``skipif`` on the platform rather than guarded by a
``try``/``skip`` that could pass vacuously on Windows too.

Every row that asserts "the pin is what produced this refusal" carries its
matched **no-pin** and/or **pin-released** control, because a refusal that
would have happened anyway proves nothing -- that is the exact error
``mklink`` produced during the FU15 investigation itself.

**T-154 does not prove ``R-WINDOW`` was eliminated, and must never be changed
to.** It proves the residual's exact accepted boundary: the substitution wins,
the post-pin guarantees still hold against the substitute, and no sensitive
byte is written before the authority proof completes.

Pure Python, ``tmp_path``/``ar2``-root scoped, no live Pi/network/model/
credential activity.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest
from cfg1_issuance_cleanup import discard_config_for_test

from pi_harness_cfg1 import cfg1_pi_config, config_issuance, run_workspace
from pi_harness_cfg1 import win_config_authority as win
from pi_harness_cfg1.cfg1_pi_config import (
    CFG1_CONFIG_DIR_NAME,
    Cfg1PiConfigError,
    write_cfg1_pi_config,
)

import cfg1_win_probe as probe

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "Sec. 37.2's mechanism is Win32-only; a skip HERE on the target "
        "platform would itself be the failure this suite guards against"
    ),
)

SYNTHETIC_BASE_URL = "https://cfg1-fu15.invalid/v1"

#: Every literal that must never reach a file the authority has not proven.
_SENSITIVE_LITERALS = ("cfg1-fu15.invalid", "qwen3-coder-next", "b300_pi_qualification")


@pytest.fixture()
def workspace(git_executable):
    """One genuine, freshly minted disposable run workspace, torn down hard.

    Teardown does not go through ``remove_cfg1_run_workspace``: several rows
    here deliberately leave a planted junction or a foreign leaf inside the
    owned tree, and the frozen remover's own removal verification is not the
    thing under test.
    """
    handle, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    root = handle.experiment_root
    try:
        yield handle
    finally:
        run_workspace.discard_cfg1_run_workspace(handle)
        shutil.rmtree(root, ignore_errors=True)


def _config_dir(handle) -> str:
    return str(Path(handle.experiment_root) / CFG1_CONFIG_DIR_NAME)


def _plant_in_r_window(monkeypatch, plant):
    """Run ``plant(config_dir)`` in the mkdir -> first-pin window.

    This is the ONLY window the accepted residual occupies, and patching
    ``Path.mkdir`` is how the suite reaches it deterministically instead of
    racing a real thread against a sub-millisecond interval.
    """
    real_mkdir = Path.mkdir
    fired: list[bool] = []

    def _mkdir_then_plant(self, *args, **kwargs):
        result = real_mkdir(self, *args, **kwargs)
        if not fired and self.name == CFG1_CONFIG_DIR_NAME:
            fired.append(True)
            plant(self)
        return result

    monkeypatch.setattr(Path, "mkdir", _mkdir_then_plant)
    return fired


# ---------------------------------------------------------------------------
# T-142 -- the owned root is bound by IDENTITY, not by name
# ---------------------------------------------------------------------------


def test_t142_the_owned_root_is_bound_by_identity_before_anything_is_created(
    workspace, filesystem_spy
):
    """The genuine root is moved aside and an ordinary directory of the same
    name substituted, with the marker and the repository child moved into the
    substitute so every NAME-based check still passes. Only the identity
    recorded at L2 disagrees.
    """
    root = Path(workspace.experiment_root)
    genuine_identity = probe.file_identity(root)
    aside = root.parent / (root.name + "_moved_aside")

    os.rename(root, aside)
    os.mkdir(root)
    for entry in os.listdir(aside):
        os.rename(aside / entry, root / entry)
    os.rmdir(aside)

    substitute_identity = probe.file_identity(root)
    assert substitute_identity != genuine_identity, (
        "the substitution did not produce a different object; the test proves "
        "nothing unless the file id actually changed"
    )

    before_mkdirs = list(filesystem_spy.mkdir_calls)
    before_opens = len(filesystem_spy.open_calls)

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == "WORKSPACE_ROOT_IDENTITY_MISMATCH"

    # Refused BEFORE CreateDirectoryW: zero directory creations, and nothing
    # opened anywhere under the config location. The workspace re-proof's own
    # read of the frozen AR2 marker is expected and is deliberately not
    # counted -- it is a read of a file the frozen creator wrote, outside the
    # config directory, and asserting "zero opens of any kind" would make this
    # row fail for a reason that has nothing to do with the identity gate.
    assert filesystem_spy.mkdir_calls == before_mkdirs
    config_location = str(root / CFG1_CONFIG_DIR_NAME)
    for entry in filesystem_spy.open_calls[before_opens:]:
        assert not entry.startswith(config_location)
    assert not (root / CFG1_CONFIG_DIR_NAME).exists()
    # The substitute is left untouched -- CFG1 never removes what it cannot
    # prove it owns.
    assert probe.file_identity(root) == substitute_identity
    assert win.held_pin_count() == 0


def test_t142_matched_control_the_genuine_root_proceeds(workspace):
    """Without the substitution the same code path proceeds, so the refusal
    above is attributable to the identity check and not to an unrelated
    failure.
    """
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert Path(generated.models_path).exists()
    assert win.held_pin_count() == 0
    discard_config_for_test(generated.issuance_token)


# ---------------------------------------------------------------------------
# T-143 -- a reparse point at the config-directory name is refused
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_inside_root", [False, True])
def test_t143_a_reparse_point_at_the_config_name_is_refused_never_followed(
    workspace, monkeypatch, tmp_path, target_inside_root
):
    """Both halves of the redirect: a junction whose target is outside the
    owned root, and one whose target is lexically INSIDE it.

    The second is what proves the refusal comes from the handle's own
    ``FILE_ATTRIBUTE_REPARSE_POINT``/``ReparseTag`` evidence rather than from a
    lexical containment check -- a name-based check would happily accept it.
    """
    if target_inside_root:
        junction_target = Path(workspace.experiment_root) / "inside_target"
    else:
        junction_target = tmp_path / "outside_target"
    junction_target.mkdir()

    from conftest import make_directory_redirect

    def _plant(config_dir: Path) -> None:
        os.rmdir(config_dir)
        make_directory_redirect(config_dir, junction_target)

    fired = _plant_in_r_window(monkeypatch, _plant)

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert fired == [True]
    assert excinfo.value.reason_code == "CONFIG_DIR_REDIRECTED"

    # The junction target contains NO file of any name, of any length -- not
    # settings.json, not models.json, not a zero-byte anything.
    assert list(junction_target.iterdir()) == []
    assert win.held_pin_count() == 0


def test_t143_matched_positive_control_a_genuine_directory_reports_no_reparse(
    workspace,
):
    """FU15-D1's required positive control.

    Against a genuine, non-redirected ordinary directory at the identical
    name, the SAME handle-based check reports the reparse attribute absent and
    ``ReparseTag == 0``, and L9 proceeds past step 4 rather than refusing.
    Without this half, an L9 that refused every directory regardless of
    reparse status would pass the negative half alone.
    """
    config_dir = _config_dir(workspace)
    Path(config_dir).mkdir()
    pin = win.acquire_config_pin(config_dir)
    try:
        attributes, reparse_tag = win.pin_attributes(pin)
        assert attributes & win.FILE_ATTRIBUTE_DIRECTORY
        assert not attributes & win.FILE_ATTRIBUTE_REPARSE_POINT
        assert reparse_tag == 0
    finally:
        win.release_pin(pin)
    os.rmdir(config_dir)

    # And end to end: L9 gets past step 4 and completes.
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert Path(generated.settings_path).exists()
    discard_config_for_test(generated.issuance_token)


# ---------------------------------------------------------------------------
# T-144 -- the pin is what prevents in-place reparse conversion
# ---------------------------------------------------------------------------


def test_t144_in_place_reparse_conversion_succeeds_without_a_pin_and_fails_with_one(
    tmp_path,
):
    """Both halves are required; (b) alone does not satisfy this row.

    (a) proves the reviewer's "conversion without delete" counterexample is
    REAL on this platform -- an unpinned empty directory becomes a junction
    with no delete and no rename at all -- and therefore that ``mklink``'s
    refusal was an unsound oracle. (b) proves the pin is what stops it, at the
    adversary's own open, before the FSCTL is ever reached.
    """
    junction_target = tmp_path / "target"
    junction_target.mkdir()

    # (a) UNPINNED, empty: the conversion SUCCEEDS.
    unpinned = tmp_path / "unpinned_empty"
    unpinned.mkdir()
    outcome, error = probe.attempt_in_place_reparse_conversion(unpinned, junction_target)
    assert outcome == "converted" and error == 0, (
        "in-place conversion of an unpinned empty directory did not succeed on "
        "this platform; W4 -- and therefore the pin's whole purpose -- must be "
        "re-established before this row can be read as passing"
    )

    # (b) PINNED exactly as L9 pins it: the adversary's own open is refused.
    pinned = tmp_path / "pinned_empty"
    pinned.mkdir()
    pin = win.acquire_config_pin(str(pinned))
    try:
        outcome, error = probe.attempt_in_place_reparse_conversion(
            pinned, junction_target
        )
        assert outcome == "open_refused"
        assert error == probe.ERROR_SHARING_VIOLATION
    finally:
        win.release_pin(pin)

    # Matched pin-released control: the identical attack now succeeds, so the
    # refusal above is attributable to the pin and not to the directory.
    outcome, error = probe.attempt_in_place_reparse_conversion(pinned, junction_target)
    assert outcome == "converted" and error == 0


def test_t144_a_non_empty_directory_refuses_conversion_at_the_fsctl_not_the_open(
    tmp_path,
):
    """W5, kept distinct from W3 on purpose: a non-empty directory's refusal
    comes from the FSCTL with ``ERROR_DIRECTORY_NOT_EMPTY`` and happens pinned
    or not, so it must never be mistaken for evidence that a pin was doing the
    work.
    """
    junction_target = tmp_path / "target_ne"
    junction_target.mkdir()
    non_empty = tmp_path / "non_empty"
    non_empty.mkdir()
    (non_empty / "child.txt").write_text("x", encoding="utf-8")

    outcome, error = probe.attempt_in_place_reparse_conversion(
        non_empty, junction_target
    )
    assert outcome == "fsctl_refused"
    assert error == probe.ERROR_DIRECTORY_NOT_EMPTY


# ---------------------------------------------------------------------------
# T-145 -- rename/delete stability of the pinned directory and its ancestors
# ---------------------------------------------------------------------------


def test_t145_the_pinned_directory_and_every_ancestor_are_rename_delete_stable(
    tmp_path,
):
    """Three matched controls are mandatory, and all three are here: the same
    operations with NO pin held must succeed, and must succeed AGAIN after the
    pin is released. Without them a rename that failed for an unrelated reason
    would read as proof.
    """
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    pinned = deep / "cfg1_pi_config"
    pinned.mkdir()

    # -- control 1: with NO pin, every operation succeeds -------------------
    assert probe.attempt_rename(pinned, deep / "renamed_control") is None
    os.rename(deep / "renamed_control", pinned)
    assert probe.attempt_rename(tmp_path / "a", tmp_path / "a_control") is None
    os.rename(tmp_path / "a_control", tmp_path / "a")
    assert probe.attempt_rmdir(pinned) is None
    pinned.mkdir()

    # -- the pin, exactly as L9 acquires it --------------------------------
    pin = win.acquire_config_pin(str(pinned))
    try:
        assert probe.attempt_rename(pinned, deep / "renamed") is not None
        assert probe.attempt_rmdir(pinned) is not None
        # No ancestor at ANY depth can be renamed while a descendant handle is
        # open, and a non-empty ancestor can be neither removed nor converted.
        for ancestor in (deep, deep.parent, tmp_path / "a"):
            assert probe.attempt_rename(ancestor, ancestor.parent / "moved") is not None
            assert probe.attempt_rmdir(ancestor) is not None
    finally:
        win.release_pin(pin)

    # -- control 2: after release, the identical operations succeed again ---
    assert probe.attempt_rename(pinned, deep / "renamed_after") is None
    os.rename(deep / "renamed_after", pinned)
    assert probe.attempt_rename(tmp_path / "a", tmp_path / "a_after") is None
    os.rename(tmp_path / "a_after", tmp_path / "a")


# ---------------------------------------------------------------------------
# T-146 -- the parentage proof is a PRE-WRITE gate (the core of Finding A)
# ---------------------------------------------------------------------------


def _redirect_children_to(monkeypatch, foreign_dir: Path) -> None:
    """Force the two exclusive creates to land somewhere that is not the pin.

    This models the redirect at the PATHNAME layer that the whole gate exists
    to catch: the pin is genuine, the children are genuinely created, and the
    only thing wrong is that they are not entries of the pinned object.
    """
    real_create = win.create_exclusive_child

    def _create(*, config_dir: str, name: str, **kwargs):
        return real_create(config_dir=str(foreign_dir), name=name, **kwargs)

    monkeypatch.setattr(win, "create_exclusive_child", _create)


def test_t146_the_parentage_gate_refuses_before_any_content_byte(
    workspace, monkeypatch, tmp_path, filesystem_spy
):
    foreign = tmp_path / "foreign_config_dir"
    foreign.mkdir()
    _redirect_children_to(monkeypatch, foreign)

    before_unlinks = list(filesystem_spy.unlink_calls)

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == "CONFIG_FILES_NOT_IN_PINNED_DIRECTORY"

    # (2) The foreign models.json is EXACTLY zero bytes, asserted against the
    # actual bytes rather than a digest, and never held a sensitive literal.
    # (3) It is removed only by handle-based disposition: the delete-on-close
    # disposition means it is already gone, with ZERO pathname unlinks.
    assert filesystem_spy.unlink_calls == before_unlinks
    assert list(foreign.iterdir()) == []
    assert win.held_child_count() == 0
    assert win.held_pin_count() == 0


def test_t146_the_foreign_leaf_is_content_free_at_the_moment_of_refusal(
    workspace, monkeypatch, tmp_path
):
    """The bytes themselves -- asserted against actual bytes, not a digest.

    Two independent proofs, because either alone would be weaker. First, an
    ordering spy shows NO content write was attempted before the gate was
    entered. Second, with handle disposition disabled so the leaves survive
    the refusal, their bytes are read and proven to be exactly empty -- and
    since the code raises the instant the gate refuses, the post-refusal bytes
    ARE the at-gate bytes.

    The leaves cannot be read WHILE L9 holds them: step 6 opens them with
    ``dwShareMode = 0``, which denies another opener read, write and delete
    for the descriptors' lifetime. That refusal is itself part of what the
    mechanism buys.
    """
    foreign = tmp_path / "foreign_capture"
    foreign.mkdir()
    _redirect_children_to(monkeypatch, foreign)
    monkeypatch.setattr(win, "dispose_child_by_handle", lambda child: False)

    writes_before_gate: list[str] = []
    gate_entered: list[bool] = []
    denied_while_held: dict[str, object] = {}
    real_prove = win.prove_config_parentage
    real_write = win.write_child_text

    def _write(child, text):
        if not gate_entered:
            writes_before_gate.append(win.child_name(child))
        return real_write(child, text)

    def _prove(config_pin, *, children, **kwargs):
        gate_entered.append(True)
        try:
            (foreign / "models.json").read_bytes()
            denied_while_held["models.json"] = "READABLE"
        except OSError:
            denied_while_held["models.json"] = "DENIED"
        return real_prove(config_pin, children=children, **kwargs)

    monkeypatch.setattr(win, "prove_config_parentage", _prove)
    monkeypatch.setattr(win, "write_child_text", _write)

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == "CONFIG_FILES_NOT_IN_PINNED_DIRECTORY"

    assert gate_entered == [True]
    assert writes_before_gate == [], "a content write was attempted before the gate"
    assert denied_while_held["models.json"] == "DENIED"

    for name in ("settings.json", "models.json"):
        content = (foreign / name).read_bytes()
        assert content == b"", f"{name} carried content bytes outside the pinned object"
        for literal in _SENSITIVE_LITERALS:
            assert literal.encode() not in content


def test_t146_a_failing_handle_disposition_leaves_the_leaf_and_never_falls_back(
    workspace, monkeypatch, tmp_path, filesystem_spy
):
    """(4) When handle-based removal is made to fail, the zero-byte leaf is
    left untouched, the failure is reported, and NO pathname fallback of any
    kind is attempted.
    """
    foreign = tmp_path / "foreign_no_dispose"
    foreign.mkdir()
    _redirect_children_to(monkeypatch, foreign)
    monkeypatch.setattr(win, "dispose_child_by_handle", lambda child: False)

    before_unlinks = list(filesystem_spy.unlink_calls)

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == "CONFIG_FILES_NOT_IN_PINNED_DIRECTORY"

    assert filesystem_spy.unlink_calls == before_unlinks
    remaining = sorted(entry.name for entry in foreign.iterdir())
    assert remaining == ["models.json", "settings.json"]
    for name in remaining:
        assert (foreign / name).read_bytes() == b""


# ---------------------------------------------------------------------------
# T-147 -- exclusive child creation refuses an occupied name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("leaf", ["settings.json", "models.json"])
@pytest.mark.parametrize("occupant", ["file", "symlink"])
def test_t147_exclusive_creation_refuses_an_occupied_name_or_a_planted_link(
    workspace, monkeypatch, tmp_path, leaf, occupant
):
    """For each leaf INDEPENDENTLY, and for both occupant shapes.

    The symlink's target deliberately does NOT exist: that is the shape under
    which ``CREATE_NEW`` without ``FILE_FLAG_OPEN_REPARSE_POINT`` -- and
    Python's own ``open(path, "x")`` -- follow the link and create the target
    outside the owned root.
    """
    decoy_bytes = b'{"attacker": "controlled"}'
    symlink_target = tmp_path / f"symlink_target_{leaf}"

    def _plant(config_dir: Path) -> None:
        if occupant == "file":
            (config_dir / leaf).write_bytes(decoy_bytes)
        else:
            os.symlink(str(symlink_target), str(config_dir / leaf))

    if occupant == "symlink":
        try:
            probe_link = tmp_path / "symlink_capability_probe"
            os.symlink(str(tmp_path / "nowhere"), str(probe_link))
            os.unlink(probe_link)
        except (OSError, NotImplementedError):
            pytest.skip("this platform grants no unprivileged file-symlink creation")

    fired = _plant_in_r_window(monkeypatch, _plant)

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert fired == [True]
    assert excinfo.value.reason_code == "CONFIG_FILE_ALREADY_EXISTS"

    planted = Path(_config_dir(workspace)) / leaf
    if occupant == "file":
        assert planted.read_bytes() == decoy_bytes
    else:
        assert not symlink_target.exists(), (
            "the exclusive create followed a planted symlink and brought its "
            "target into existence outside the owned root"
        )
    assert win.held_pin_count() == 0
    assert win.held_child_count() == 0


# ---------------------------------------------------------------------------
# T-148 -- content bytes reach only the proven descriptors
# ---------------------------------------------------------------------------


def test_t148_no_pathname_open_of_either_config_path_occurs_inside_l9(
    workspace, filesystem_spy
):
    """After the gate passes, EVERY content byte and every finalization
    read-back goes through the two descriptors whose file ids the parentage
    proof matched. A pathname open of either config path anywhere inside L9
    would mean the digest is a statement about whatever the name resolves to,
    not about the proven object.
    """
    config_dir = _config_dir(workspace)
    before = len(filesystem_spy.open_calls)

    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        opened = filesystem_spy.open_calls[before:]
        for entry in opened:
            assert not entry.startswith(config_dir), (
                f"L9 opened a config path BY NAME: {entry!r}"
            )
        # The bytes really did land, so this is not vacuously true.
        assert Path(generated.settings_path).read_bytes()
        assert Path(generated.models_path).read_bytes()
    finally:
        discard_config_for_test(generated.issuance_token)


def test_t148_the_finalization_digest_comes_from_the_held_descriptor(workspace):
    """The registered digest equals the bytes actually on disk, and the
    read-back that produced it happened through the descriptor -- proven by
    the digest still matching after L9 released everything.
    """
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        import hashlib

        record = config_issuance.verify_config_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        on_disk = Path(generated.models_path).read_bytes()
        assert record.models_sha256 == hashlib.sha256(on_disk).hexdigest()
        assert record.models_identity == probe.file_identity(generated.models_path)
        assert record.settings_identity == probe.file_identity(generated.settings_path)
    finally:
        discard_config_for_test(generated.issuance_token)


# ---------------------------------------------------------------------------
# T-149 -- T-1's byte identity survives the handle-based writer
# ---------------------------------------------------------------------------


def test_t149_arm_q_bytes_are_unchanged_by_the_descriptor_writer(workspace, tmp_path):
    """A failure here BLOCKS FU15 rather than amending T-1.

    The frozen qualification generator still uses ``Path.write_text``; FU15's
    writer goes through a descriptor. Both perform the same :mod:`io` newline
    translation, so the on-disk bytes -- including the Windows ``\\r\\n`` --
    must still agree exactly.
    """
    from qualification import i2_issuance
    from qualification.i2_pi_config import write_qualification_pi_config

    from pi_harness_cfg1.identity import CFG1_MODEL_ID

    frozen_root = tmp_path / "frozen_t149"
    frozen_root.mkdir()
    frozen = write_qualification_pi_config(
        str(frozen_root), model_id=CFG1_MODEL_ID, base_url=SYNTHETIC_BASE_URL
    )
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        settings_bytes = Path(generated.settings_path).read_bytes()
        models_bytes = Path(generated.models_path).read_bytes()
        assert settings_bytes == Path(frozen.settings_path).read_bytes()
        assert models_bytes == Path(frozen.models_path).read_bytes()
        # And the translation really happened, so equality is not two
        # untranslated files agreeing.
        assert b"\r\n" in settings_bytes
    finally:
        i2_issuance._discard_issuance(
            token=frozen.authority_token, config_dir=frozen.config_dir
        )
        discard_config_for_test(generated.issuance_token)


# ---------------------------------------------------------------------------
# T-150 -- both pins released on every exit path, before L9 returns
# ---------------------------------------------------------------------------


def _release_order_spy(monkeypatch) -> list[str]:
    """Record which pin each release targets, by the role that acquired it."""
    order: list[str] = []
    roles: dict[str, str] = {}
    real_root = win.acquire_root_pin
    real_config = win.acquire_config_pin
    real_release = win.release_pin_quietly

    def _root(*args, **kwargs):
        pin = real_root(*args, **kwargs)
        roles[pin.nonce] = "root"
        return pin

    def _config(*args, **kwargs):
        pin = real_config(*args, **kwargs)
        roles[pin.nonce] = "config"
        return pin

    def _release(pin):
        order.append(roles.get(getattr(pin, "nonce", ""), "unknown"))
        return real_release(pin)

    monkeypatch.setattr(win, "acquire_root_pin", _root)
    monkeypatch.setattr(win, "acquire_config_pin", _config)
    monkeypatch.setattr(win, "release_pin_quietly", _release)
    return order


def test_t150_the_success_path_releases_both_pins_config_directory_first(
    workspace, monkeypatch
):
    order = _release_order_spy(monkeypatch)
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    discard_config_for_test(generated.issuance_token)
    assert order == ["config", "root"]
    assert win.held_pin_count() == 0
    assert win.held_child_count() == 0


@pytest.mark.parametrize(
    "injection",
    [
        "config_pin_failure",
        "containment_failure",
        "child_creation_failure",
        "parentage_failure",
        "content_write_failure",
        "issuance_failure",
    ],
)
def test_t150_every_refusal_and_injected_failure_path_releases_both_pins(
    workspace, monkeypatch, injection
):
    """Each enumerated Sec. 37.3.2 failure point, proven to leave zero held
    handles before control leaves L9.
    """
    order = _release_order_spy(monkeypatch)
    failure = win.Cfg1DirectoryAuthorityError

    if injection == "config_pin_failure":
        monkeypatch.setattr(
            win,
            "acquire_config_pin",
            lambda path, **k: (_ for _ in ()).throw(failure("CONFIG_DIR_NOT_PINNED")),
        )
    elif injection == "containment_failure":
        monkeypatch.setattr(
            win,
            "prove_child_directory_entry",
            lambda *a, **k: (_ for _ in ()).throw(failure("CONFIG_DIR_NOT_IN_OWNED_ROOT")),
        )
    elif injection == "child_creation_failure":
        real_create = win.create_exclusive_child
        calls: list[int] = []

        def _create(*, config_dir, name, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise failure("CONFIG_FILE_ALREADY_EXISTS")
            return real_create(config_dir=config_dir, name=name, **kwargs)

        monkeypatch.setattr(win, "create_exclusive_child", _create)
    elif injection == "parentage_failure":
        monkeypatch.setattr(
            win,
            "prove_config_parentage",
            lambda *a, **k: (_ for _ in ()).throw(
                failure("CONFIG_FILES_NOT_IN_PINNED_DIRECTORY")
            ),
        )
    elif injection == "content_write_failure":
        monkeypatch.setattr(
            win,
            "write_child_text",
            lambda *a, **k: (_ for _ in ()).throw(failure("CONFIG_FILES_NOT_WRITTEN")),
        )
    else:
        monkeypatch.setattr(
            config_issuance,
            "register_config_issuance",
            lambda **k: (_ for _ in ()).throw(
                config_issuance.ConfigIssuanceError("INJECTED")
            ),
        )

    with pytest.raises(Cfg1PiConfigError):
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)

    assert win.held_pin_count() == 0, "a pin outlived L9"
    assert win.held_child_count() == 0, "a child descriptor outlived L9"
    if injection == "config_pin_failure":
        assert order == ["root"]
    else:
        assert order == ["config", "root"]


def test_t150_a_leaked_pin_makes_l27_removal_fail_so_release_is_load_bearing(
    workspace,
):
    """Release is not hygiene: with a pin deliberately leaked, the frozen
    remover cannot remove the tree. A future regression in release is
    therefore guaranteed to surface as a lifecycle failure rather than
    silently.
    """
    from ar2.fixtures import remove_disposable_tree

    config_dir = _config_dir(workspace)
    Path(config_dir).mkdir()
    leaked = win.acquire_config_pin(config_dir)
    try:
        result = remove_disposable_tree(workspace.experiment_root)
        assert result.get("removed") is not True
    finally:
        win.release_pin(leaked)


# ---------------------------------------------------------------------------
# T-151 -- pin-release failure degrades L9 AND the lifecycle evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "which,expected",
    [("config", "CONFIG_DIR_PIN_NOT_RELEASED"), ("root", "WORKSPACE_ROOT_PIN_NOT_RELEASED")],
)
def test_t151_a_pin_release_failure_refuses_l9_with_its_own_closed_code(
    workspace, monkeypatch, which, expected
):
    roles: dict[str, str] = {}
    real_root = win.acquire_root_pin
    real_config = win.acquire_config_pin
    real_release = win.release_pin_quietly
    reopens: list[str] = []
    stranded: list[object] = []

    def _root(*args, **kwargs):
        pin = real_root(*args, **kwargs)
        roles[pin.nonce] = "root"
        return pin

    def _config(*args, **kwargs):
        pin = real_config(*args, **kwargs)
        roles[pin.nonce] = "config"
        return pin

    def _release(pin):
        if roles.get(pin.nonce) == which:
            stranded.append(pin)
            return False  # the close itself failed; the handle is still open
        return real_release(pin)

    def _no_reacquire(path, *args, **kwargs):
        reopens.append(str(path))
        raise AssertionError("L9 re-derived a pin from a NAME after a close failure")

    monkeypatch.setattr(win, "acquire_root_pin", _root)
    monkeypatch.setattr(win, "acquire_config_pin", _config)
    monkeypatch.setattr(win, "release_pin_quietly", _release)

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == expected

    # No force-close, no retry, no re-derivation of the handle from a name.
    assert reopens == []
    assert len(stranded) == 1
    # The suite must not leak the stranded handle into later tests.
    for pin in stranded:
        real_release(pin)
    config_issuance._ISSUED.clear()


def test_t151_a_leaked_pin_degrades_the_durable_lifecycle_evidence_end_to_end(
    git_executable, monkeypatch
):
    """(3) and (4): the run's own evidence carries
    ``workspace_removed_verified = false`` and ``lifecycle_all_closed =
    false``, it classifies ``INDETERMINATE_LIFECYCLE``, and the L27 failure is
    reported rather than suppressed.
    """
    from cfg1_doubles import build_doubled_ports, seam_digests_all_match
    from pi_harness_cfg1.classification import classify_cfg1_run
    from pi_harness_cfg1.lifecycle import compute_lifecycle_closure
    from pi_harness_cfg1.run_contract import Cfg1RunAdmission
    from pi_harness_cfg1.run_executor import execute_cfg1_run
    from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

    seam_digests_all_match(monkeypatch)

    leaked: list[object] = []
    real_config = win.acquire_config_pin
    real_release = win.release_pin_quietly

    def _config(path, **kwargs):
        pin = real_config(path, **kwargs)
        leaked.append(pin)
        return pin

    def _release(pin):
        if pin in leaked:
            return False
        return real_release(pin)

    monkeypatch.setattr(win, "acquire_config_pin", _config)
    monkeypatch.setattr(win, "release_pin_quietly", _release)

    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="a" * 32,
    )
    ports, made = build_doubled_ports(git_executable=git_executable)
    outcome = execute_cfg1_run(admission, ports=ports)
    try:
        observations = outcome.observations
        assert observations["workspace_removed_verified"] is False
        all_closed, failure_steps = compute_lifecycle_closure(observations)
        assert all_closed is False
        assert "L27" in failure_steps
        observations["lifecycle_all_closed"] = all_closed
        assert classify_cfg1_run(observations) == "INDETERMINATE_LIFECYCLE"
    finally:
        for pin in leaked:
            real_release(pin)
        handle = made.get("workspace")
        if handle is not None:
            run_workspace.discard_cfg1_run_workspace(handle)
            shutil.rmtree(handle.experiment_root, ignore_errors=True)


# ---------------------------------------------------------------------------
# T-152 -- the two post-creation partial-failure points
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("point", ["between_writes", "before_issuance"])
def test_t152_post_creation_partial_failures_mint_no_token_and_leave_residue_inside(
    git_executable, monkeypatch, point
):
    """Sec. 37.3.2 rows 7-8, mapped onto FU15's own frozen ordering.

    FU15 creates BOTH children at step 6 with zero content bytes and writes
    both at step 8, so "after settings.json is written but before models.json
    is created" is not a reachable state in the frozen sequence. Its exact
    analogue is a failure of the SECOND content write -- settings content on
    disk, models content not -- and that is what ``between_writes`` injects.
    ``before_issuance`` is row 8 verbatim.
    """
    from cfg1_doubles import build_doubled_ports, seam_digests_all_match
    from pi_harness_cfg1.run_contract import Cfg1RunAdmission
    from pi_harness_cfg1.run_executor import execute_cfg1_run
    from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

    seam_digests_all_match(monkeypatch)

    if point == "between_writes":
        real_write = win.write_child_text
        calls: list[int] = []

        def _write(child, text):
            calls.append(1)
            if len(calls) == 2:
                raise win.Cfg1DirectoryAuthorityError("CONFIG_FILES_NOT_WRITTEN")
            return real_write(child, text)

        monkeypatch.setattr(win, "write_child_text", _write)
    else:
        monkeypatch.setattr(
            config_issuance,
            "register_config_issuance",
            lambda **k: (_ for _ in ()).throw(
                config_issuance.ConfigIssuanceError("INJECTED")
            ),
        )

    tokens_before = config_issuance.issued_token_count()
    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="b" * 32,
    )
    ports, made = build_doubled_ports(git_executable=git_executable)

    # Prove the L24 scrub branch is not merely reported unentered but actually
    # never reached: its own re-verification is what the branch begins with.
    issuance_verifications: list[int] = []
    real_verify = config_issuance.verify_config_issuance

    def _verify(**kwargs):
        issuance_verifications.append(1)
        return real_verify(**kwargs)

    monkeypatch.setattr(config_issuance, "verify_config_issuance", _verify)

    residue: dict[str, object] = {}
    real_remove = run_workspace.remove_cfg1_run_workspace

    def _remove(handle):
        root = Path(handle.experiment_root)
        config_dir = root / CFG1_CONFIG_DIR_NAME
        residue["existed"] = config_dir.exists()
        residue["entries"] = (
            sorted(entry.name for entry in config_dir.iterdir())
            if config_dir.exists()
            else []
        )
        residue["inside_root"] = config_dir.exists() and (
            os.path.commonpath([os.path.realpath(config_dir), os.path.realpath(root)])
            == os.path.realpath(root)
        )
        return real_remove(handle)

    # ``run_executor.workspace_module`` IS this module object, so one
    # rebinding covers the executor's own call site too.
    monkeypatch.setattr(run_workspace, "remove_cfg1_run_workspace", _remove)

    outcome = execute_cfg1_run(admission, ports=ports)
    observations = outcome.observations

    assert observations["pre_dispatch_refusal_code"] == "CONFIG_GENERATION_FAILED"
    assert observations["refused_at_step"] == "L9"
    # No issuance token, so no consumer can claim a generated config exists.
    assert config_issuance.issued_token_count() == tokens_before
    # Both pins released; nothing left held.
    assert win.held_pin_count() == 0
    assert win.held_child_count() == 0
    # No model-influenced code ran while an endpoint-bearing file was on disk.
    assert observations["verification_attempted"] is False
    assert observations["verification_skip_reason"] == "PRE_DISPATCH_REFUSAL"
    # L24's scrub branch was NOT entered -- there is no issuance to prove
    # ownership with -- rather than entered and failed. The durable field
    # therefore keeps its "nothing was written, so nothing's scrub can be
    # unverified" default, which Sec. 37.3.2 row 8 states explicitly; what
    # proves the branch was skipped is that its own re-verification never ran.
    assert issuance_verifications == []
    assert observations["generated_config_scrub_verified"] is True
    # The residue stayed INSIDE the owned root and L27's removal is what took
    # it: after the run, the root is gone.
    assert residue["existed"] is True
    assert residue["inside_root"] is True
    # FU1 AM-13 (OC-11): both injection points fail AFTER the endpoint write
    # was attempted, so the writer's one failure-path release disposed BOTH
    # children through their own creating handles and then closed them --
    # which is exactly what licenses ``generated_config_scrub_verified`` above
    # (an exact ``endpoint_material_outstanding == False``). The directory
    # itself is still residue, left for L27 alone.
    assert residue["entries"] == []
    assert observations["workspace_removed_verified"] is True
    handle = made.get("workspace")
    assert handle is not None and not Path(handle.experiment_root).exists()


# ---------------------------------------------------------------------------
# T-153 -- pin-acquisition failure creates nothing and deletes nothing
# ---------------------------------------------------------------------------


def test_t153_root_pin_acquisition_failure_creates_nothing_at_all(
    workspace, monkeypatch, filesystem_spy
):
    monkeypatch.setattr(
        win,
        "acquire_root_pin",
        lambda path, *, expected_identity, **k: (_ for _ in ()).throw(
            win.Cfg1DirectoryAuthorityError("WORKSPACE_ROOT_NOT_PINNED")
        ),
    )
    before_mkdirs = list(filesystem_spy.mkdir_calls)

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == "WORKSPACE_ROOT_NOT_PINNED"

    assert filesystem_spy.mkdir_calls == before_mkdirs
    assert not Path(_config_dir(workspace)).exists()
    assert win.held_child_count() == 0


def test_t153_config_pin_failure_leaves_the_created_directory_in_place(
    workspace, monkeypatch, filesystem_spy, git_executable
):
    """CFG1 never removes a directory whose ownership it cannot prove, so the
    just-created empty directory is LEFT, and its removal happens only via
    L27's namespace teardown.
    """
    monkeypatch.setattr(
        win,
        "acquire_config_pin",
        lambda path, **k: (_ for _ in ()).throw(
            win.Cfg1DirectoryAuthorityError("CONFIG_DIR_NOT_PINNED")
        ),
    )
    before_unlinks = list(filesystem_spy.unlink_calls)

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == "CONFIG_DIR_NOT_PINNED"

    config_dir = Path(_config_dir(workspace))
    assert config_dir.is_dir(), "CFG1 removed a directory it could not prove it owned"
    assert list(config_dir.iterdir()) == [], "a child was created after the pin failed"
    assert filesystem_spy.unlink_calls == before_unlinks
    assert win.held_pin_count() == 0

    # L27 is what removes it, and it does.
    monkeypatch.undo()
    run_workspace.remove_cfg1_run_workspace(workspace)
    assert not config_dir.exists()


# ---------------------------------------------------------------------------
# T-154 -- R-WINDOW: the FROZEN acceptance test for the accepted residual
# ---------------------------------------------------------------------------


def test_t154_r_window_substitution_wins_and_l9_neither_detects_nor_refuses_it(
    workspace, monkeypatch, tmp_path, filesystem_spy
):
    """**This row must never be read, and no future change may make it read,
    as proving the window was eliminated.** It establishes the residual's
    exact, accepted three-part boundary.
    """
    identities: dict[str, tuple[int, int]] = {}

    def _plant(config_dir: Path) -> None:
        identities["original"] = probe.file_identity(config_dir)
        os.rmdir(config_dir)
        os.mkdir(config_dir)  # a DIFFERENT ordinary directory object
        identities["substitute"] = probe.file_identity(config_dir)

    fired = _plant_in_r_window(monkeypatch, _plant)

    pinned_identity: dict[str, tuple[int, int]] = {}
    attacks: dict[str, object] = {}
    writes_before_gate: list[str] = []
    real_prove = win.prove_config_parentage
    real_write = win.write_child_text
    gate_passed: list[bool] = []

    def _write(child, text):
        if not gate_passed:
            writes_before_gate.append(win.child_name(child))
        return real_write(child, text)

    def _prove(config_pin, *, children, **kwargs):
        # (2) Every escape/replacement/reparse attempt this design enumerates,
        # run against the SUBSTITUTE while the pin is held.
        pinned_identity["pinned"] = win.pin_identity(config_pin)
        config_dir = Path(_config_dir(workspace))
        attacks["rename"] = probe.attempt_rename(
            config_dir, config_dir.parent / "stolen"
        )
        attacks["rmdir"] = probe.attempt_rmdir(config_dir)
        attacks["reparse"] = probe.attempt_in_place_reparse_conversion(
            config_dir, tmp_path / "reparse_target"
        )
        attacks["ancestor_rename"] = probe.attempt_rename(
            config_dir.parent, config_dir.parent.parent / "stolen_ancestor"
        )
        try:
            win.create_exclusive_child(
                config_dir=str(config_dir), name="settings.json"
            )
            attacks["leaf_collision"] = "CREATED (BAD)"
        except win.Cfg1DirectoryAuthorityError as exc:
            attacks["leaf_collision"] = exc.reason_code
        result = real_prove(config_pin, children=children, **kwargs)
        gate_passed.append(True)
        return result

    (tmp_path / "reparse_target").mkdir()
    monkeypatch.setattr(win, "prove_config_parentage", _prove)
    monkeypatch.setattr(win, "write_child_text", _write)

    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        assert fired == [True]

        # (1) THE SUBSTITUTION WINS, and L9 does not detect it and does not
        # refuse. This is the accepted residual, stated positively.
        assert identities["original"] != identities["substitute"]
        assert pinned_identity["pinned"] == identities["substitute"], (
            "the object L9 pinned was not the substitute; this row no longer "
            "exercises R-WINDOW at all"
        )

        # (2) The post-pin guarantee is a property of the PIN, not of the
        # pinned object's provenance.
        assert attacks["rename"] is not None
        assert attacks["rmdir"] is not None
        assert attacks["reparse"] == ("open_refused", probe.ERROR_SHARING_VIOLATION)
        assert attacks["ancestor_rename"] is not None
        assert attacks["leaf_collision"] == "CONFIG_FILE_ALREADY_EXISTS"

        # (3) No sensitive byte before the post-pin authority proof completes.
        assert writes_before_gate == []

        # ...and the written models.json resolves INSIDE the identity-proven
        # owned root.
        root = os.path.realpath(workspace.experiment_root)
        resolved = os.path.realpath(generated.models_path)
        assert os.path.commonpath([resolved, root]) == root
        assert SYNTHETIC_BASE_URL.encode() in Path(generated.models_path).read_bytes()

        # L24's scrub reaches the exact issued object through the retained
        # handle (AMEND2, Y6): a handle-bound CONTENT scrub, no pathname and no
        # unlink. The object is left at length zero; L27 owns namespace cleanup.
        assert config_issuance.scrub_config_issuance(
            token=generated.issuance_token, workspace=workspace
        ) is True
        assert Path(generated.models_path).read_bytes() == b""
    finally:
        discard_config_for_test(generated.issuance_token)

    # And L27's removal reaches the substituted directory: root-namespace
    # teardown authority covers a descendant CFG1 did not itself create
    # (Sec. 37.3.2a), because it is mechanically contained in the owned root.
    monkeypatch.undo()
    result = run_workspace.remove_cfg1_run_workspace(workspace)
    assert result.get("removed") is True
    assert not Path(workspace.experiment_root).exists()


def test_t154_the_residual_is_never_described_as_eliminated(workspace):
    """A source-of-truth guard: nothing in the authority path may claim
    ``R-WINDOW`` is closed, and the ONE mechanism that would close it stays
    unauthorized.
    """
    import inspect

    for source in (
        inspect.getsource(win),
        inspect.getsource(cfg1_pi_config.write_cfg1_pi_config),
    ):
        lowered = source.lower()
        for claim in (
            "r-window is closed",
            "r-window eliminated",
            "closes r-window",
            "no longer a residual",
        ):
            assert claim not in lowered
    assert 'WinDLL("ntdll' not in inspect.getsource(win)


# ---------------------------------------------------------------------------
# T-155 -- L24's scrub is identity-bound and never deletes a non-matching object
# ---------------------------------------------------------------------------


def test_t155_the_issuance_record_binds_the_config_and_both_child_identities(
    workspace,
):
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        record = config_issuance.verify_config_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        assert record.config_dir_identity == probe.file_identity(generated.config_dir)
        assert record.settings_identity == probe.file_identity(generated.settings_path)
        assert record.models_identity == probe.file_identity(generated.models_path)
    finally:
        discard_config_for_test(generated.issuance_token)


def test_t155_a_same_name_same_bytes_replacement_is_untouched_and_never_unlinked(
    workspace, filesystem_spy
):
    """The replacement carries IDENTICAL BYTES on purpose.

    Under AMEND2 (Y6) L24 opens no pathname, so a same-name replacement -- even
    a byte-identical one -- cannot be reached by L24 at all: it is neither read,
    modified nor deleted. The ISSUED object (now unnamed, still held by the
    retained handle) is the one scrubbed.
    """
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    original_bytes = Path(generated.models_path).read_bytes()
    original_identity = probe.file_identity(generated.models_path)

    # Replace the object, keeping the name and the bytes exactly.
    os.unlink(generated.models_path)
    Path(generated.models_path).write_bytes(original_bytes)
    replacement_identity = probe.file_identity(generated.models_path)
    assert replacement_identity != original_identity

    before_unlinks = list(filesystem_spy.unlink_calls)
    assert config_issuance.scrub_config_issuance(
        token=generated.issuance_token, workspace=workspace
    ) is True
    # NO unlink of any kind occurs -- including no pathname unlink.
    assert filesystem_spy.unlink_calls == before_unlinks
    assert Path(generated.models_path).read_bytes() == original_bytes  # untouched
    assert probe.file_identity(generated.models_path) == replacement_identity


@pytest.mark.parametrize("variant", ["foreign_replacement", "failed_scrub"])
def test_t155_a_replacement_is_not_a_failure_but_a_failed_scrub_skips_l26(
    variant, git_executable, monkeypatch
):
    """End to end. A same-name replacement between issuance and L24 no longer
    fails L24 (L24 never consults the name); an ACTUAL scrub failure still sets
    ``generated_config_scrub_verified`` false, skips L26 with
    ``LIFECYCLE_UNPROVEN``, fails closure at L24, and classifies
    ``INDETERMINATE_LIFECYCLE`` -- Sec. 18 row 9's disposition.
    """
    from cfg1_doubles import build_doubled_ports, seam_digests_all_match
    from pi_harness_cfg1.classification import classify_cfg1_run
    from pi_harness_cfg1.lifecycle import compute_lifecycle_closure
    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)
    real_write_config = cfg1_pi_config.write_cfg1_pi_config

    def _write_config(handle, *, arm_id, base_url):
        generated = real_write_config(handle, arm_id=arm_id, base_url=base_url)
        if variant == "foreign_replacement":
            content = Path(generated.models_path).read_bytes()
            os.unlink(generated.models_path)
            Path(generated.models_path).write_bytes(content)
        return generated

    if variant == "failed_scrub":
        monkeypatch.setattr(win, "_truncate_handle", lambda handle: False)
    ports, made = build_doubled_ports(
        git_executable=git_executable,
        overrides={
            "write_config": lambda *, workspace, arm_id, base_url: _write_config(
                workspace, arm_id=arm_id, base_url=base_url
            )
        },
    )
    from cfg1_fu1_support import make_admission

    outcome = execute_cfg1_run(make_admission(), ports=ports)
    observations = outcome.observations
    all_closed, failure_steps = compute_lifecycle_closure(observations)
    if variant == "foreign_replacement":
        assert observations["generated_config_scrub_verified"] is True
        assert observations["verification_attempted"] is True
        assert "L24" not in failure_steps
    else:
        assert observations["generated_config_scrub_verified"] is False
        assert observations["verification_attempted"] is False
        assert observations["verification_skip_reason"] == "LIFECYCLE_UNPROVEN"
        assert all_closed is False
        assert "L24" in failure_steps
        observations["lifecycle_all_closed"] = all_closed
        assert classify_cfg1_run(observations) == "INDETERMINATE_LIFECYCLE"
    assert made.get("workspace") is not None


# ---------------------------------------------------------------------------
# Post-implementation adversarial review (CFG1-IMPL-FU3), folded into the
# rows whose invariants they defend. Each of these closed a REAL bypass found
# by attacking the implementation after it was green.
# ---------------------------------------------------------------------------


def test_t155_a_genuine_parentage_proof_cannot_be_paired_with_other_children(
    workspace, monkeypatch
):
    """The "copied proof plus substituted identities" attack, one layer below
    the one CFG1-IMPL-FU1 Finding 2 closed for ``GeneratedCfg1Config``.

    A parentage proof is a statement about SPECIFIC objects. Before this was
    closed, ``register_config_issuance`` accepted a genuine ``proven`` object
    alongside any two genuine-but-different ``ExclusiveChild`` handles, and
    would then bind THEIR identities into the issuance record -- which is what
    L24 later deletes by.
    """
    stolen: dict[str, object] = {}
    real_prove = win.prove_config_parentage

    def _prove(config_pin, *, children, **kwargs):
        proof = real_prove(config_pin, children=children, **kwargs)
        stolen["proof"] = proof
        return proof

    monkeypatch.setattr(win, "prove_config_parentage", _prove)
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    discard_config_for_test(generated.issuance_token)

    # The proof is retired with L9, so it is not even re-presentable.
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.require_proven_children(stolen["proof"], ())
    assert excinfo.value.reason_code == "PARENTAGE_NOT_PROVEN"

    # And while a proof IS live, it refuses any child set but its own.
    config_dir = Path(workspace.experiment_root) / "second_config"
    config_dir.mkdir()
    pin = win.acquire_config_pin(str(config_dir))
    genuine_children = tuple(
        win.create_exclusive_child(config_dir=str(config_dir), name=name)
        for name in ("settings.json", "models.json")
    )
    other = None
    try:
        proof = win.prove_config_parentage(pin, children=genuine_children)
        win.require_proven_children(proof, genuine_children)  # the positive control

        elsewhere = Path(workspace.experiment_root) / "elsewhere"
        elsewhere.mkdir()
        other = win.create_exclusive_child(
            config_dir=str(elsewhere), name="models.json"
        )
        for substituted in (
            (genuine_children[0], other),
            (other,),
            (),
            genuine_children + (other,),
        ):
            with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
                win.require_proven_children(proof, substituted)
            assert excinfo.value.reason_code in (
                "PARENTAGE_CHILD_MISMATCH",
                "NOT_AN_EXCLUSIVE_CHILD",
            )
        win.discard_parentage_proof(proof)
    finally:
        for child in genuine_children:
            win.close_child_quietly(child)
        win.close_child_quietly(other)
        win.release_pin_quietly(pin)


def test_t153_the_l2_baseline_refuses_to_record_a_redirected_root_identity(
    tmp_path,
):
    """Binding the run's root authority to the far end of a reparse point
    would make every later identity comparison agree about the wrong object.
    The one baseline reading therefore refuses a redirect outright.
    """
    from conftest import make_directory_redirect

    real = tmp_path / "real_root"
    real.mkdir()
    link = tmp_path / "redirected_root"
    try:
        make_directory_redirect(link, real)
    except OSError:
        pytest.skip("this platform grants no directory-redirect mechanism")

    assert win.directory_identity_of_path(str(real)) == probe.file_identity(real)
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.directory_identity_of_path(str(link))
    assert excinfo.value.reason_code == "ROOT_IDENTITY_REDIRECTED"


def test_t151_a_failed_close_is_counted_rather_than_hidden_by_registry_removal(
    tmp_path, monkeypatch
):
    """A nonce must stop being usable as authority whatever the close returned,
    so the registry entry is retired either way -- which would make
    ``held_pin_count()`` read zero after a LEAK. A leak must never be
    invisible, so it is counted separately.
    """
    directory = tmp_path / "close_failure"
    directory.mkdir()
    pin = win.acquire_config_pin(str(directory))

    before = win.close_failure_count()
    monkeypatch.setattr(win._K32, "CloseHandle", lambda handle: 0)
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.release_pin(pin)
    assert excinfo.value.reason_code == "PIN_NOT_RELEASED"
    monkeypatch.undo()

    assert win.held_pin_count() == 0, "the nonce must stop being authority"
    assert win.close_failure_count() == before + 1, "the leak was hidden"
    # The suite's own hygiene fixture asserts this counter is zero, so this
    # test accounts for the leak it deliberately injected.
    win._CLOSE_FAILURES.clear()
    assert win.release_pin_quietly(pin) is True  # already retired; idempotent


def test_t153_a_pin_cannot_be_minted_for_anything_that_is_not_a_win32_handle():
    """Found by T-124's own callable sweep during the FU3 adversarial review.

    ``_register_pin`` is the one place a ``PinnedDirectory`` comes into
    existence, so an ungated one would let any object be registered as a
    handle -- a forged pin whose later "release" closes an arbitrary integer.
    """
    for impostor in (None, "handle", object(), 1.0, True, [1]):
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win._register_pin(impostor)
        assert excinfo.value.reason_code == "NOT_A_WIN32_HANDLE"
    assert win.held_pin_count() == 0


def test_t146_a_foreign_file_planted_into_the_pinned_directory_fails_the_gate(
    tmp_path,
):
    """W11/C5 prove a directory pin does NOT protect its children: another
    actor can still create new entries inside the pinned directory. The gate's
    EXACT-SET requirement is what catches that, and it is why the proof is not
    merely "each of my two children is present".
    """
    directory = tmp_path / "pinned_with_intruder"
    directory.mkdir()
    pin = win.acquire_config_pin(str(directory))
    children = tuple(
        win.create_exclusive_child(config_dir=str(directory), name=name)
        for name in ("settings.json", "models.json")
    )
    try:
        (directory / "planted_by_someone_else.txt").write_text("x", encoding="utf-8")
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.prove_config_parentage(pin, children=children)
        assert excinfo.value.reason_code == "CONFIG_FILES_NOT_IN_PINNED_DIRECTORY"
    finally:
        for child in children:
            win.dispose_child_by_handle(child)
            win.close_child_quietly(child)
        win.release_pin(pin)


def test_t150_an_authority_object_is_immutable_and_unforgeable(tmp_path):
    """Python object immutability alone is NOT the authority here -- the
    registry entry is -- but a mutable field would still let a verified object
    be re-pointed after its own check, so both halves are proven.
    """
    directory = tmp_path / "immutable"
    directory.mkdir()
    pin = win.acquire_config_pin(str(directory))
    retired_nonce = pin.nonce
    try:
        for attempt in (
            lambda: setattr(pin, "nonce", "forged"),
            lambda: setattr(pin, "extra_field", 1),
            lambda: delattr(pin, "nonce"),
        ):
            with pytest.raises((win.Cfg1DirectoryAuthorityError, AttributeError)):
                attempt()
        assert pin.nonce == retired_nonce
    finally:
        win.release_pin(pin)

    # Forging by construction, and reusing a retired nonce, are both refused.
    for cls, code in (
        (win.PinnedDirectory, "PIN_NOT_HELD"),
        (win.ExclusiveChild, "CHILD_NOT_HELD"),
        (win.ProvenConfigChildren, "PARENTAGE_NOT_PROVEN"),
    ):
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            cls("deadbeef" * 4)
        assert excinfo.value.reason_code == code
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.PinnedDirectory(retired_nonce)
    assert excinfo.value.reason_code == "PIN_NOT_HELD"
    # A released pin is dead for every consumer, not merely for release.
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.pin_identity(pin)
    assert excinfo.value.reason_code == "PIN_ALREADY_RELEASED"


def test_t155_the_scrub_never_follows_a_redirect_and_refuses_malformed_authority(
    workspace, tmp_path
):
    """Two shapes L24 must never act on: a reparse point standing where the
    generated file was, and an authority the caller could not supply correctly.
    Neither may result in a write to, or a deletion of, anything foreign.
    """
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    victim = tmp_path / "victim_outside_the_root.json"
    victim.write_bytes(b"VICTIM")
    os.unlink(generated.models_path)
    try:
        os.symlink(str(victim), generated.models_path)
    except (OSError, NotImplementedError):
        discard_config_for_test(generated.issuance_token)
        pytest.skip("this platform grants no unprivileged file-symlink creation")

    # L24 never resolves the name, so the redirect is never followed: the
    # victim is untouched and the redirect itself is never removed.
    assert config_issuance.scrub_config_issuance(
        token=generated.issuance_token, workspace=workspace
    ) is True
    assert victim.exists() and victim.read_bytes() == b"VICTIM"
    assert os.path.lexists(generated.models_path)

    for malformed in (None, (1,), ("a", "b"), [1, 2], (True, 2), "id", 0, object()):
        assert win.scrub_retire_retained(malformed) is False
        assert win.release_retained(malformed) is False
    assert victim.read_bytes() == b"VICTIM"


def test_t143_no_refusal_message_carries_a_path_or_a_raw_win32_error(tmp_path):
    """Sec. 21.1's reduction rule at this boundary: a closed reason code and
    nothing else. A Win32 error NUMBER is an unbounded diagnostic here too --
    it is what an attacker's probe would read back out of a console line.
    """
    missing = tmp_path / "definitely_absent_directory_name"
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.acquire_config_pin(str(missing))
    text = str(excinfo.value)
    assert excinfo.value.reason_code == "CONFIG_DIR_NOT_PINNED"
    assert text == "cfg1 directory authority refused: CONFIG_DIR_NOT_PINNED"
    assert str(missing) not in text
    assert "definitely_absent_directory_name" not in text
    assert not hasattr(excinfo.value, "winerror")
