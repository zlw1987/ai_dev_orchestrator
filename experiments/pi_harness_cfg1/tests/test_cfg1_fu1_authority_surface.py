"""5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-AUTHORITY-SURFACE-FU1 regressions.

FU1-AUTH-1: no verification return exposes retained authority.
FU1-AUTH-2: the public issuance token alone is never scrub/release authority.

Every test drives only SUPPORTED callables, from the position of a caller that
holds a generated result and (where stated) a genuine workspace.
"""

from __future__ import annotations

import dataclasses
import inspect
import shutil

import pytest
from cfg1_issuance_cleanup import discard_config_for_test, discard_extension_for_test
from test_cfg1_fu1_y6_retained_scrub import (
    SYNTHETIC_BASE_URL,
    _Target,
    _write_extension,
)

from pi_harness_cfg1 import config_issuance, extension_issuance, run_workspace
from pi_harness_cfg1 import win_config_authority as win
from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config

pytestmark = pytest.mark.skipif(not win.PLATFORM_SUPPORTED, reason="Win32 only")


def _mint(git_executable):
    handle, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    return handle


@pytest.fixture()
def workspace(git_executable):
    handle = _mint(git_executable)
    root = handle.experiment_root
    try:
        yield handle
    finally:
        run_workspace.discard_cfg1_run_workspace(handle)
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def other_workspace(git_executable):
    handle = _mint(git_executable)
    root = handle.experiment_root
    try:
        yield handle
    finally:
        run_workspace.discard_cfg1_run_workspace(handle)
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(params=["models.json", "ar2_config.ts"])
def target(request, workspace):
    return _Target(request.param, workspace)


def _generate(target):
    if target.config:
        return write_cfg1_pi_config(target.workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    return _write_extension(target.workspace)


def _verify(target, generated, workspace=None):
    fn = (
        config_issuance.verify_config_issuance
        if target.config
        else extension_issuance.verify_extension_issuance
    )
    return fn(token=generated.issuance_token, workspace=workspace or target.workspace)


def _scrub_fn(target):
    return (
        config_issuance.scrub_config_issuance
        if target.config
        else extension_issuance.scrub_extension_issuance
    )


def _reclaim_fn(target):
    return (
        config_issuance.reclaim_config_issuance
        if target.config
        else extension_issuance.reclaim_extension_issuance
    )


def _cleanup(target, token):
    (discard_config_for_test if target.config else discard_extension_for_test)(token)


def _registry(target):
    return config_issuance._ISSUED if target.config else extension_issuance._ISSUED_EXTENSIONS


def _private_retained(target, token):
    return _registry(target)[token].retained


def _graph(obj, seen=None):
    """Every object reachable through attributes, slots, tuples, lists, dicts."""
    seen = set() if seen is None else seen
    if id(obj) in seen:
        return
    seen.add(id(obj))
    yield obj
    children = []
    if isinstance(obj, (tuple, list, set, frozenset)):
        children += list(obj)
    elif isinstance(obj, dict):
        children += list(obj.keys()) + list(obj.values())
    else:
        children += list(getattr(obj, "__dict__", {}).values())
        for klass in type(obj).__mro__:
            for name in getattr(klass, "__slots__", ()):
                if hasattr(obj, name):
                    children.append(getattr(obj, name))
    for child in children:
        yield from _graph(child, seen)


def _assert_no_authority(obj, retained, raw_handle):
    nonce = retained.nonce
    for node in _graph(obj):
        assert type(node) is not win.RetainedAuthority
        assert node is not retained
        assert not (type(node) is str and node == nonce)
        assert not (type(node) is int and node == raw_handle and raw_handle > 0)
    text = repr(obj) + str(obj)
    assert nonce not in text and "RetainedAuthority" not in text
    assert not hasattr(obj, "retained")
    assert "retained" not in {f.name for f in dataclasses.fields(obj)}


def _spy_reopens(monkeypatch):
    reopens: list[int] = []
    real = win._reopen_file
    monkeypatch.setattr(win, "_reopen_file", lambda *a: (reopens.append(1), real(*a))[1])
    return reopens


# ---------------------------------------------------------------- A / B / C / D


def test_a_b_verify_returns_a_safe_view_carrying_no_retained_authority(target):
    generated = _generate(target)
    token = generated.issuance_token
    try:
        retained = _private_retained(target, token)
        raw_handle = win._RETAINED[retained.nonce][0]
        view = _verify(target, generated)
        assert type(view) not in (
            config_issuance._IssuanceRecord,
            extension_issuance._ExtensionIssuanceRecord,
        )
        assert view is not _registry(target)[token]
        _assert_no_authority(view, retained, raw_handle)
        _assert_no_authority(_verify(target, generated), retained, raw_handle)
    finally:
        _cleanup(target, token)


def test_c_d_genuine_token_and_workspace_cannot_extract_retained_authority(target):
    generated = _generate(target)
    token = generated.issuance_token
    try:
        retained = _private_retained(target, token)
        view = _verify(target, generated)
        with pytest.raises(dataclasses.FrozenInstanceError):
            view.retained = retained
        with pytest.raises(dataclasses.FrozenInstanceError):
            view.run_workspace_nonce = "x"
        # The view is not accepted anywhere retained authority is required.
        assert win.scrub_retire_retained(view) is False
        assert win.release_retained(view) is False
        with pytest.raises(win.Cfg1DirectoryAuthorityError):
            win.retained_identity(view)
        assert _reclaim_fn(target)(view) is False
        assert token in _registry(target)
        assert all(retained.nonce != v for v in vars(view).values())
    finally:
        _cleanup(target, token)


def test_j_generated_result_is_token_only(target):
    generated = _generate(target)
    try:
        retained = _private_retained(target, generated.issuance_token)
        raw_handle = win._RETAINED[retained.nonce][0]
        assert type(generated.issuance_token) is str
        for node in _graph(generated):
            assert type(node) is not win.RetainedAuthority
            assert not (type(node) is int and node == raw_handle and raw_handle > 0)
        assert retained.nonce not in repr(generated)
        assert not hasattr(generated, "retained")
    finally:
        _cleanup(target, generated.issuance_token)


# ------------------------------------------------------------------------ E / F


def test_e_no_public_production_callable_retires_on_a_token_alone(target, monkeypatch):
    # Structural sweep: the token-only cleanup surface no longer exists, and any
    # public callable that accepts a token also demands a workspace.
    for module in (config_issuance, extension_issuance):
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("_") or fn.__module__ != module.__name__:
                continue
            assert not name.startswith("discard_"), name
            if "token" in inspect.signature(fn).parameters:
                assert "workspace" in inspect.signature(fn).parameters, name
    assert not hasattr(config_issuance, "discard_config_issuance")
    assert not hasattr(extension_issuance, "discard_extension_issuance")

    generated = _generate(target)
    token = generated.issuance_token
    try:
        counters = {"scrub": 0, "release": 0}
        real_scrub, real_release = win.scrub_retire_retained, win.release_retained

        def _scrub(r):
            counters["scrub"] += 1
            return real_scrub(r)

        def _release(r):
            counters["release"] += 1
            return real_release(r)

        monkeypatch.setattr(win, "scrub_retire_retained", _scrub)
        monkeypatch.setattr(win, "release_retained", _release)
        reopens = _spy_reopens(monkeypatch)
        before = (dict(_registry(target)), len(win._RETAINED))
        for bad_workspace in (None, object(), "", 0, generated):
            assert _scrub_fn(target)(token=token, workspace=bad_workspace) is False
        _verify(target, generated)
        assert (dict(_registry(target)), len(win._RETAINED)) == before
        assert counters == {"scrub": 0, "release": 0}
        assert reopens == []
        assert target.path.stat().st_size > 0
    finally:
        _cleanup(target, token)


def test_f_another_runs_workspace_cannot_retire_this_runs_issuance(
    target, other_workspace, monkeypatch
):
    generated = _generate(target)
    token = generated.issuance_token
    try:
        reopens = _spy_reopens(monkeypatch)
        before = (dict(_registry(target)), len(win._RETAINED))
        assert _scrub_fn(target)(token=token, workspace=other_workspace) is False
        assert (dict(_registry(target)), len(win._RETAINED)) == before
        assert reopens == []
        assert target.path.stat().st_size > 0
        with pytest.raises(
            (config_issuance.ConfigIssuanceError, extension_issuance.ExtensionIssuanceError)
        ):
            _verify(target, generated, workspace=other_workspace)
    finally:
        _cleanup(target, token)


# ------------------------------------------------------------------- G / H / I


def test_g_i_genuine_l24_path_succeeds_exactly_once_then_fails_closed(target, monkeypatch):
    generated = _generate(target)
    token = generated.issuance_token
    assert _scrub_fn(target)(token=token, workspace=target.workspace) is True
    assert token not in _registry(target)
    assert target.path.stat().st_size == 0
    reopens = _spy_reopens(monkeypatch)
    assert _scrub_fn(target)(token=token, workspace=target.workspace) is False
    assert reopens == []


def test_h_writer_reclaim_needs_no_public_token(target):
    generated = _generate(target)
    token = generated.issuance_token
    retained = _private_retained(target, token)
    try:
        assert _reclaim_fn(target)(retained) is True
        assert token not in _registry(target)
        assert _reclaim_fn(target)(retained) is False
    finally:
        # The writer, having reclaimed, owns scrub-retirement of the authority.
        assert win.scrub_retire_retained(retained) is True
