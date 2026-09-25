"""L11 -- the CFG1-owned transactional extension writer (FU1 AM-9, AM-10, AM-14).

Design ``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` (R6) Sec. 9.2a
(E-1 .. E11) and Sec. 9.2c-B/D. For CFG1 only, this replaces the frozen
``ar2.pi_config.write_disposable_extension``: that function copies whatever
the live source directory holds, writes the token-bearing ``ar2_config.ts``
with ``Path.write_text``, and has no ``finally``, no registry and no
identity. Neither it nor the frozen pathname scrubber is edited; CFG1 simply
stops calling them.

::

    E-1  pinned single read of the 4 sources + the template     EXTENSION_SOURCE_UNPINNED
         -- BEFORE anything exists; only verified bytes buffered  EXTENSION_TEMPLATE_UNPINNED
    E0   open THIS writer's extension-typed provenance interval
    E1-2 root pin, by the workspace's registered root identity
    E3   CreateDirectoryW pi_extension (R-WINDOW-E opens)
    E4-5 pin it (share-read, no-follow), prove it is the root's child by id
    E6   five exclusive children, CREATE_NEW, share 0, ZERO bytes
    E7   THE GATE: handle-relative parentage of every child
    E8   the verified buffers verbatim, then the token-bearing file LAST
    E9   read-back through the same descriptors vs. buffers AND pins
    E9a  RETAIN from the TOKEN child's creating handle only (AMEND2)
    E10  extension issuance, owning the retained authority -- the registry
         insert is registration's last statement; the public result is built
         (E10c) BEFORE any release
    E11  release; on a failure KNOWN before release: RECLAIM, SCRUB the token
         object through its creating handle, THEN close (AMEND2 K); a release
         failure after registration reclaims and scrubs through the retained
         handle before raising (S')

**What a caller gets.** Only an issuance token (:class:`GeneratedCfg1Extension`)
-- never a bare path. L14 and L15 take the extension entry from a fresh
``verify_extension_issuance``; L24 scrubs the CONTENT of the exact
``ar2_config.ts`` object through the issuance's retained handle (AMEND2). It
removes no name.

**Exception contract.** Every anticipated failure raises exactly one
:class:`Cfg1ExtensionError` carrying one closed code and one exact bool,
``token_material_outstanding = token_write_attempted AND NOT (scrubbed AND
token_closed AND (NOT retained_acquired OR retained_released))``: a successful
content scrub of the exact token object AND a successful close of the token
child's creating handle (and of any retained handle) are needed for "not
outstanding". A delete disposition is namespace cleanup and is not an input. An
unanticipated raise inside the writer is released the same way but
propagates UNTYPED, so the executor conservatively assumes token material
remains. No path, token or exception text crosses this boundary.

**R-WINDOW-E (accepted, R6).** Between E3 and E4 a same-user actor may
substitute another ORDINARY directory at ``pi_extension``; whichever object
wins is proven non-reparse and contained by file id in the identity-proven
root, and receives zero bytes before the gate. Nothing here claims CFG1
necessarily created that directory, and the writer never deletes it -- only
L27's independently re-proven whole-root teardown may.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import extension_issuance
from . import win_config_authority as win
from .extension_issuance import (
    CFG1_EXTENSION_DIR_NAME,
    EXTENSION_CHILD_NAMES,
    ExtensionIssuanceError,
)
from .extension_pins import (
    EXTENSION_EXPERIMENT_ID,
    EXTENSION_SOURCE_NAMES,
    GENERATED_CONFIG_TEMPLATE_BYTES,
    GENERATED_CONFIG_TEMPLATE_SHA256,
    PINNED_EXTENSION_SOURCES,
)


class Cfg1ExtensionError(Exception):
    """L11 refused. One closed code, one exact bool, nothing else."""

    def __init__(self, reason_code: str, token_material_outstanding: bool) -> None:
        super().__init__(f"cfg1 extension refused: {reason_code}")
        self.reason_code = reason_code
        self.token_material_outstanding = token_material_outstanding


class GeneratedCfg1Extension:
    """The ONE thing L11 returns: the extension issuance token.

    Carries no path, no broker value and no token material, and renders none.
    Its token is authority only while the registry holds it and only for the
    workspace it was issued against.
    """

    __slots__ = ("issuance_token",)

    def __init__(self, issuance_token: str) -> None:
        object.__setattr__(self, "issuance_token", issuance_token)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("GeneratedCfg1Extension is immutable")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}(issuance_token=<bound>)"


class _ExtensionRefusal(Exception):
    """Internal control flow: one anticipated closed code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------------------
# E-1 leaves -- the only places a source or the template is ever read
# ---------------------------------------------------------------------------


def _extension_source_directory() -> str:
    """The single, parameterless derivation of the frozen source directory.

    The ``extension`` directory beside the frozen ``ar2`` package. The
    LOCATION is deliberately not authority -- the pins are: any directory
    whose bytes match is the reviewed extension, and none that differs passes.
    """
    import ar2

    return str(Path(ar2.__file__).resolve().parent.parent / "extension")


def _read_source_once(path: str, max_bytes: int) -> bytes:
    """ONE no-follow open of one source; at most ``max_bytes + 1`` bytes."""
    return win.read_regular_file_once(path, max_bytes=max_bytes)


def _read_template_once() -> object:
    """Read the frozen ``_GENERATED_CONFIG_HEADER`` attribute exactly once."""
    from ar2 import pi_config as frozen_pi_config

    return frozen_pi_config._GENERATED_CONFIG_HEADER


def _pinned_inputs() -> tuple[dict[str, bytes], str]:
    """E-1. Read, verify and buffer every input BEFORE anything is created.

    Each source is opened once, and only bytes whose exact length and SHA-256
    equal the CFG1-owned pin are kept; the source pathname is never opened
    again. The template is read once into a local and verified against its
    pin and structure rule; that local -- never the module attribute again --
    is what E8 formats.
    """
    source_dir = _extension_source_directory()
    buffers: dict[str, bytes] = {}
    for name in EXTENSION_SOURCE_NAMES:
        size, digest = PINNED_EXTENSION_SOURCES[name]
        try:
            data = _read_source_once(os.path.join(source_dir, name), size)
        except win.Cfg1DirectoryAuthorityError:
            raise _ExtensionRefusal("EXTENSION_SOURCE_UNPINNED") from None
        if (
            type(data) is not bytes
            or len(data) != size
            or hashlib.sha256(data).hexdigest() != digest
        ):
            raise _ExtensionRefusal("EXTENSION_SOURCE_UNPINNED")
        buffers[name] = data

    template = _read_template_once()
    if type(template) is not str:
        raise _ExtensionRefusal("EXTENSION_TEMPLATE_UNPINNED")
    try:
        encoded = template.encode("utf-8")
    except UnicodeEncodeError:
        raise _ExtensionRefusal("EXTENSION_TEMPLATE_UNPINNED") from None
    if (
        len(encoded) != GENERATED_CONFIG_TEMPLATE_BYTES
        or hashlib.sha256(encoded).hexdigest() != GENERATED_CONFIG_TEMPLATE_SHA256
        or template.count("%s") != 1
        or template.count("%") != 1
    ):
        raise _ExtensionRefusal("EXTENSION_TEMPLATE_UNPINNED")
    return buffers, template


def render_generated_config(
    template: str, *, experiment_id: str, pipe_name: str, capability_id: str, token: str
) -> str:
    """The ``ar2_config.ts`` text from an ALREADY-VERIFIED template.

    The frozen key order and serializer: ``experiment``, ``pipeName``,
    ``capabilityId``, ``token``, ``json.dumps(..., indent=2,
    ensure_ascii=True)``. The golden vector (R6 Sec. 9.2c-D) pins its output.
    """
    config = {
        "experiment": experiment_id,
        "pipeName": pipe_name,
        "capabilityId": capability_id,
        "token": token,
    }
    return template % json.dumps(config, indent=2, ensure_ascii=True)


def _dispose_quietly(child: object) -> bool:
    """Namespace cleanup only (AMEND2): never an input to the outstanding bool."""
    try:
        return win.dispose_child_by_handle(child) is True
    except Exception:  # noqa: BLE001 - an unknown disposition is simply not proven
        return False


def _scrub_child_quietly(child: object) -> bool:
    """SCRUB-C through the still-held creating handle. Any failure is ``False``."""
    try:
        return win.scrub_child_through_creating_handle(child) is True
    except Exception:  # noqa: BLE001 - an unknown scrub is never proven
        return False


_RETAINED_ACQUIRED_CODES = frozenset(
    {"RETAINED_IDENTITY_MISMATCH", "RETAINED_INHERITABLE", "RETAINED_NOT_RELEASED"}
)


# ---------------------------------------------------------------------------
# The writer
# ---------------------------------------------------------------------------


def write_cfg1_extension(
    workspace, *, pipe_name: str, capability_id: str, token: str
) -> GeneratedCfg1Extension:
    """L11 -- write one run's disposable extension, transactionally.

    ``workspace`` is a genuine, ACTIVE ``Cfg1RunWorkspace`` -- never a path.
    ``pipe_name``/``capability_id``/``token`` are the broker binding, held in
    memory only and written to disk exactly once, into the token-bearing
    ``ar2_config.ts`` that is created LAST.
    """
    from .run_workspace import Cfg1RunWorkspace, registered_root_identity

    if not win.PLATFORM_SUPPORTED:
        raise Cfg1ExtensionError("EXTENSION_AUTHORITY_UNSUPPORTED_PLATFORM", False)
    if type(workspace) is not Cfg1RunWorkspace:
        raise Cfg1ExtensionError("NOT_A_CFG1_RUN_WORKSPACE", False)
    for value in (pipe_name, capability_id, token):
        if type(value) is not str or not value:
            raise Cfg1ExtensionError("MALFORMED_BROKER_BINDING", False)

    # -- E-1: pinned inputs, before ANY object exists ----------------------
    try:
        buffers, template = _pinned_inputs()
    except _ExtensionRefusal as refusal:
        raise Cfg1ExtensionError(refusal.code, False) from None

    generated = render_generated_config(
        template,
        experiment_id=EXTENSION_EXPERIMENT_ID,
        pipe_name=pipe_name,
        capability_id=capability_id,
        token=token,
    )
    # The declared newline translation of the text-mode write (``\n`` ->
    # ``os.linesep``), so E9 and E10 compare the exact on-disk bytes.
    expected_config_bytes = generated.replace("\n", os.linesep).encode("utf-8")
    expected_config_sha256 = hashlib.sha256(expected_config_bytes).hexdigest()

    try:
        extension_dir, _child_paths = extension_issuance.derive_cfg1_extension_paths(
            workspace
        )
        root_identity = registered_root_identity(workspace)
    except Exception:  # noqa: BLE001 - bounded; nothing has been created
        raise Cfg1ExtensionError("WORKSPACE_AUTHORITY_UNVERIFIED", False) from None

    interval = None
    root_pin = None
    extension_pin = None
    children: list = []
    proven = None
    issuance = None
    result = None
    retained = None
    retained_acquired = False
    retained_released = False
    token_write_attempted = False
    failure_code: str | None = None
    unexpected: BaseException | None = None
    try:
        # -- E0 ------------------------------------------------------------
        interval = win.open_generation_interval()
        # -- E1-E2 ----------------------------------------------------------
        root_pin = win.acquire_root_pin(
            workspace.experiment_root, expected_identity=root_identity, interval=interval
        )
        # -- E3: R-WINDOW-E opens here, closes at E4 -------------------------
        try:
            Path(extension_dir).mkdir(parents=False, exist_ok=False)
        except OSError:
            raise _ExtensionRefusal("EXTENSION_DIR_NOT_CREATED") from None
        # -- E4-E5 ----------------------------------------------------------
        extension_pin = win.acquire_config_pin(extension_dir, interval=interval)
        win.prove_child_directory_entry(
            root_pin,
            name=CFG1_EXTENSION_DIR_NAME,
            identity=win.pin_identity(extension_pin),
        )
        # -- E6: every child exclusive and EMPTY; the token file last --------
        for name in EXTENSION_CHILD_NAMES:
            children.append(
                win.create_exclusive_child(
                    config_dir=extension_dir, name=name, interval=interval
                )
            )
        # -- E7: THE GATE ---------------------------------------------------
        proven = win.prove_config_parentage(
            extension_pin, children=tuple(children), interval=interval
        )
        # -- E8: verified buffers verbatim, then the token LAST ---------------
        for name, child in zip(EXTENSION_SOURCE_NAMES, children):
            win.write_child_bytes(child, buffers[name])
        token_write_attempted = True
        win.write_child_text(children[-1], generated)
        # -- E9: read-back vs. buffers AND pins -----------------------------
        for name, child in zip(EXTENSION_SOURCE_NAMES, children):
            back = win.read_child_bytes(child)
            if (
                back != buffers[name]
                or hashlib.sha256(back).hexdigest() != PINNED_EXTENSION_SOURCES[name][1]
            ):
                raise _ExtensionRefusal("EXTENSION_READBACK_MISMATCH")
        if win.read_child_bytes(children[-1]) != expected_config_bytes:
            raise _ExtensionRefusal("EXTENSION_READBACK_MISMATCH")
        # -- E9a/E9b (AMEND2): RETAIN from the TOKEN child's creating handle
        # only, while it is still held. Static children get no retained handle.
        try:
            retained = win.retain_child(
                children[-1],
                kind=win.RETAINED_KIND_EXTENSION_TOKEN,
                interval=interval,
            )
        except win.Cfg1DirectoryAuthorityError as exc:
            retained_acquired = exc.reason_code in _RETAINED_ACQUIRED_CODES
            retained_released = exc.reason_code != "RETAINED_NOT_RELEASED"
            raise _ExtensionRefusal("EXTENSION_RETAINED_AUTHORITY_REFUSED") from None
        retained_acquired = True
        # -- E10: issuance. Every check runs through the held handles; the
        # registry insert, which takes ownership of ``retained``, is LAST. -----
        try:
            issuance = extension_issuance.register_extension_issuance(
                workspace=workspace,
                proven=proven,
                children=tuple(children),
                expected_config_sha256=expected_config_sha256,
                retained=retained,
            )
        except ExtensionIssuanceError:
            raise _ExtensionRefusal("EXTENSION_ISSUANCE_NOT_REGISTERED") from None
        # -- E10c: the public result is built BEFORE any release. --------------
        result = GeneratedCfg1Extension(issuance)
    except _ExtensionRefusal as refusal:
        failure_code = refusal.code
    except win.Cfg1DirectoryAuthorityError as exc:
        failure_code = exc.reason_code
    except BaseException as exc:  # noqa: BLE001 - released below, then re-raised untyped
        unexpected = exc

    failure_known = failure_code is not None or unexpected is not None

    # -- E11: release. The interval is retired FIRST, unconditionally. -------
    win.close_generation_interval(interval)
    token_child = children[-1] if token_write_attempted else None
    scrubbed = False
    if failure_known:
        # K -- a failure known BEFORE release: RECLAIM (no I/O), SCRUB the token
        # object through its still-held creating handle strictly before any
        # close, then dispositions (namespace cleanup only, best effort).
        if retained is not None:
            extension_issuance.reclaim_extension_issuance(retained)
        if token_child is not None:
            scrubbed = _scrub_child_quietly(token_child)
        for child in children:
            _dispose_quietly(child)
    token_closed = False
    child_close_failed = False
    for child in children:
        closed = win.close_child_quietly(child)
        if not closed:
            child_close_failed = True
        if child is token_child:
            token_closed = closed
    if failure_known and retained is not None:
        retained_released = win.release_retained(retained)
    win.discard_parentage_proof(proven)
    extension_pin_failed = extension_pin is not None and not win.release_pin_quietly(
        extension_pin
    )
    root_pin_failed = root_pin is not None and not win.release_pin_quietly(root_pin)
    release_failed = extension_pin_failed or root_pin_failed or child_close_failed

    if not failure_known and release_failed and retained is not None:
        # S' -- a release failure after a successful registration: RECLAIM the
        # entry and scrub through the retained handle before raising, so a raise
        # never leaves this invocation's issuance ACTIVE (the FU4-FU1 rule).
        extension_issuance.reclaim_extension_issuance(retained)
        scrubbed = win.scrub_retire_retained(retained) is True
        retained_released = scrubbed

    token_material_outstanding = token_write_attempted and not (
        scrubbed and token_closed and (not retained_acquired or retained_released)
    )

    if unexpected is not None:
        # Released exactly as a known failure, but NOT credited: the executor
        # assumes token material remains for any untyped raise (R6 Sec. 9.2a).
        raise unexpected
    if not failure_known and not release_failed:
        return result
    reason = failure_code
    if extension_pin_failed:
        reason = "EXTENSION_DIR_PIN_NOT_RELEASED"
    elif root_pin_failed:
        reason = "WORKSPACE_ROOT_PIN_NOT_RELEASED"
    elif child_close_failed:
        reason = "EXTENSION_FILE_NOT_CLOSED"
    raise Cfg1ExtensionError(reason, token_material_outstanding) from None


#: FU1 AM-10. Bind THE one extension-writer code object, at import, from this
#: module's own genuine writer.
win.bind_extension_writer_authority()
