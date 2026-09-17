"""The CFG1-owned, per-arm Pi configuration generator.

Design Sec. 7.4 ("New, CFG1-owned"). The frozen qualification generator
(``qualification.i2_pi_config.write_qualification_pi_config``) cannot host
CFG1 -- it has no arm parameter, and the frozen controller calls it itself --
so CFG1 owns this one. It is NOT a fork of that module's authority, issuance,
marker or cleanup machinery: CFG1's own issuance registry lives in
:mod:`config_issuance`, and the run lifecycle owns cleanup (Sec. 17).

Two properties this module exists to guarantee:

1. **Arm Q is byte-identical** to the frozen generator's output for the same
   synthetic inputs (T-1). Both files are produced through the same
   ``json.dumps(..., indent=2) + newline`` shape, and although FU15 replaced
   ``Path.write_text`` with a write through a proven descriptor
   (:func:`win_config_authority.write_child_text`), the newline translation is
   the identical :mod:`io` translation, so the on-disk bytes -- including
   Windows newline translation -- still agree exactly (T-149).
2. **Every other arm differs from Q by exactly one provider-level ``compat``
   subtree** and nothing else (T-2), inserted between ``apiKey`` and
   ``models`` so the surrounding document's key ordering is untouched.

The base URL is written into the disposable ``models.json`` and is NEVER
recorded, returned, printed, digested un-redacted, or echoed anywhere else.
The credential is never written at all -- only the exact ``$ENV_NAME``
interpolation reference.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import win_config_authority as win
from .arms import ARM_COMPAT
from .identity import CFG1_MODEL_ID, CREDENTIAL_ENV_VAR_NAME, PROVIDER_ID


class Cfg1PiConfigError(Exception):
    """The disposable per-arm Pi configuration could not be produced."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 pi config refused: {reason_code}")
        self.reason_code = reason_code


#: The fixed placeholder substituted for the base URL before digesting.
#: A redacted digest is a DRIFT DETECTOR for the generated document's shape,
#: never a fingerprint of the endpoint -- two different endpoints produce the
#: same redacted digest by construction, which is exactly the point.
REDACTED_BASE_URL = "<REDACTED>"

#: The directory name CFG1 creates inside the run's own owned workspace root.
#: Deliberately NOT ``i2_pi_config``: a CFG1 directory must never be mistaken
#: for a qualification-issued one by a human reading a tree.
CFG1_CONFIG_DIR_NAME = "cfg1_pi_config"


def settings_document() -> dict[str, object]:
    """The emptied-ambient settings document, identical to the frozen one.

    The same content as ``qualification.i2_pi_config._settings_document`` --
    deliberately re-declared rather than imported, because importing a private
    name from a frozen module and then depending on its exact bytes would make
    that module's internals part of CFG1's own contract. T-1 proves the two
    agree, which is the correct direction: a drift becomes a test failure, not
    a silent inheritance.

    ``defaultThinkingLevel`` is deliberately ABSENT, so Pi's own ``medium``
    default applies unclamped (Sec. 3.3).
    """
    return {
        "packages": [],
        "extensions": [],
        "skills": [],
        "prompts": [],
        "themes": [],
        "defaultTools": [],
        "enableSkillCommands": False,
        "defaultProjectTrust": "never",
        "enableInstallTelemetry": False,
        "enableAnalytics": False,
        "quietStartup": True,
        "retry": {
            "enabled": True,
            "maxRetries": 3,
            "baseDelayMs": 2000,
            "provider": {"maxRetries": 0},
        },
    }


def models_document(
    *, arm_id: str, base_url: str, model_id: str = CFG1_MODEL_ID
) -> dict[str, object]:
    """The per-arm ``models.json`` document.

    Arm Q's provider key order is exactly ``baseUrl, api, apiKey, models``.
    Every other arm inserts ``compat`` between ``apiKey`` and ``models`` --
    one subtree, in one place, with nothing else moved, added, or removed.

    ``maxTokens`` is deliberately absent at every level: AIDO imposes no
    output-token ceiling here, so Pi's own default applies and is a
    Pi-defaulted fact, never an AIDO-requested cap.
    """
    if type(arm_id) is not str or arm_id not in ARM_COMPAT:
        raise Cfg1PiConfigError("UNKNOWN_ARM_ID")
    if type(base_url) is not str or not base_url.strip():
        raise Cfg1PiConfigError("MALFORMED_BASE_URL")
    if type(model_id) is not str or not model_id.strip():
        raise Cfg1PiConfigError("MALFORMED_MODEL_ID")

    provider: dict[str, object] = {
        "baseUrl": base_url,
        "api": "openai-completions",
        "apiKey": "$" + CREDENTIAL_ENV_VAR_NAME,
    }
    compat = ARM_COMPAT[arm_id]
    if compat is not None:
        # dict preserves insertion order, so this lands exactly between
        # `apiKey` and `models` -- the one structural delta between arms.
        provider["compat"] = dict(compat)
    provider["models"] = [{"id": model_id, "reasoning": True}]
    return {"providers": {PROVIDER_ID: provider}}


def serialize_config_document(document: object) -> str:
    """The one serialization shape both generated files use."""
    return json.dumps(document, indent=2) + "\n"


def redacted_models_digest(*, arm_id: str, model_id: str = CFG1_MODEL_ID) -> str:
    """SHA-256 of this arm's ``models.json`` with the base URL redacted.

    Computed from the in-memory document with :data:`REDACTED_BASE_URL`
    substituted, so no endpoint value ever reaches a digest, a record, or a
    console line. This is the value a run record's
    ``models_json_redacted_sha256`` field must equal (Sec. 22.3).
    """
    document = models_document(arm_id=arm_id, base_url=REDACTED_BASE_URL, model_id=model_id)
    return hashlib.sha256(serialize_config_document(document).encode("utf-8")).hexdigest()


def settings_digest() -> str:
    """SHA-256 of the settings document's canonical serialized text."""
    return hashlib.sha256(
        serialize_config_document(settings_document()).encode("utf-8")
    ).hexdigest()


class GeneratedCfg1Config:
    """Where one run's disposable per-arm configuration landed.

    Deliberately not a value object a caller can construct meaningfully: it is
    produced only by :func:`write_cfg1_pi_config`, and carries no credential,
    no base URL, and -- in any rendered form -- no absolute path and no
    issuance token.
    """

    __slots__ = (
        "config_dir",
        "settings_path",
        "models_path",
        "arm_id",
        "provider_id",
        "model_id",
        "settings_sha256",
        "models_redacted_sha256",
        "issuance_token",
    )

    def __init__(
        self,
        *,
        config_dir: str,
        settings_path: str,
        models_path: str,
        arm_id: str,
        provider_id: str,
        model_id: str,
        settings_sha256: str,
        models_redacted_sha256: str,
        issuance_token: str,
    ) -> None:
        self.config_dir = config_dir
        self.settings_path = settings_path
        self.models_path = models_path
        self.arm_id = arm_id
        self.provider_id = provider_id
        self.model_id = model_id
        self.settings_sha256 = settings_sha256
        self.models_redacted_sha256 = models_redacted_sha256
        self.issuance_token = issuance_token

    def __repr__(self) -> str:  # noqa: D105 - absolute paths are never rendered
        return (
            f"{type(self).__name__}(arm_id={self.arm_id!r}, "
            f"provider_id={self.provider_id!r}, model_id={self.model_id!r}, "
            "config_dir=<bound>, issuance_token=<bound>)"
        )


def _dispose_children_by_handle(children) -> None:
    """Sec. 37.3.2 rows 9-10 -- remove the zero-byte children, BY HANDLE ONLY.

    Reached only when the parentage gate refused, at which point every child is
    content-free. Disposition goes through the very descriptors that created
    them (W12), never through a pathname, so no pathname-resolved victim is
    reachable. A disposition that fails leaves the zero-byte file untouched and
    is never retried by name.
    """
    for child in children:
        win.dispose_child_by_handle(child)
        win.close_child_quietly(child)


def write_cfg1_pi_config(
    workspace, *, arm_id: str, base_url: str, model_id: str = CFG1_MODEL_ID
) -> GeneratedCfg1Config:
    """L9 -- write one run's ``settings.json`` + ``models.json`` for one arm.

    ``workspace`` is a genuine, ACTIVE ``Cfg1RunWorkspace`` ownership handle --
    never a bare path. The location is a pure function of that handle's own
    re-verified ``experiment_root``
    (:func:`config_issuance.derive_cfg1_config_paths` takes no path, prefix or
    parent parameter of any kind), so a caller cannot select a different one.

    **Sec. 37.3.1, in order, with the pins owned as locals of this routine.**
    Both pins are acquired here, consumed only by this routine's own proofs,
    and released here on EVERY exit path before control leaves L9. Neither is
    stored on :class:`GeneratedCfg1Config`, registered, returned, passed to a
    port, placed in a record, or rendered in any ``repr``: they are not
    capability objects and confer no authority outside this interval.

    ::

        1-2  root identity re-proved from a handle  WORKSPACE_ROOT_*
        3    CreateDirectoryW                       CONFIG_DIR_NOT_CREATED
        4    config pin, proven non-reparse         CONFIG_DIR_REDIRECTED
        5    containment by file id, no pathname    CONFIG_DIR_NOT_IN_OWNED_ROOT
        6    exclusive children, ZERO content bytes CONFIG_FILE_ALREADY_EXISTS
        7    THE GATE: handle-relative parentage    CONFIG_FILES_NOT_IN_PINNED_DIRECTORY
        8    content, through the proven descriptors
        9    finalization read-back, same descriptors
        10   issuance, bound to the proven identities
        11   release: children, config directory, then root

    **What this closes, and what it does not.** From step 4 onward the pinned
    NAME cannot be rebound (W2, W3, W5, W6) and, independently and with no
    pathname involved at all, step 7 proves the bytes go into the pinned
    OBJECT. The gate runs strictly before step 8, so a failed proof means no
    content byte is ever written -- not that a foreign write is detected
    afterwards. ``R-WINDOW`` (Sec. 37.3.6) remains open and is ACCEPTED as a
    documented, bounded residual (FU15-D1 resolved ``D-A`` = A1): between step
    3 and step 4 a same-user actor may substitute another ORDINARY directory
    object at the same child name, and L9 neither detects nor refuses that.
    Whichever object wins is still proven to be a genuine non-reparse
    directory contained by file id inside the identity-proven owned root, and
    still receives zero content bytes before the gate. This routine must never
    be described as proving the pinned object is the one ``CreateDirectoryW``
    returned, and the directory must never be called secure, isolated,
    tamper-proof or sandboxed -- it is pinned for a bounded interval, which is
    a statement about rename, delete and reparse conversion and nothing else.

    **CFG1-IMPL-FU2's own source comment is superseded.** It described the
    directory-level half of the config-generation TOCTOU as an open design
    question needing a Windows-specific directory-handle authority that "this
    design has never frozen". FU15/FU15-D1 froze exactly that authority, and
    this is it. The file-level half FU2 closed with ``open(path, "x")`` is
    re-closed here on stronger evidence: that idiom is NOT symlink-safe on
    win32 (see :func:`win_config_authority.create_exclusive_child`).
    """
    from . import config_issuance
    from .run_workspace import Cfg1RunWorkspace, registered_root_identity

    if type(arm_id) is not str or arm_id not in ARM_COMPAT:
        raise Cfg1PiConfigError("UNKNOWN_ARM_ID")
    if type(workspace) is not Cfg1RunWorkspace:
        raise Cfg1PiConfigError("NOT_A_CFG1_RUN_WORKSPACE")
    if not win.PLATFORM_SUPPORTED:
        # Every semantic Sec. 37.2 establishes is a Win32 semantic. A portable
        # substitute under the same name would reinstate precisely the window
        # the pins exist to close, which is the reasoning Sec. 37.2 already
        # applies to NtCreateFile's own fallback. So: fail closed.
        raise Cfg1PiConfigError("CONFIG_DIR_AUTHORITY_UNSUPPORTED_PLATFORM")

    # Serialize BOTH documents before anything is created, so a malformed arm
    # or endpoint refuses with nothing on disk, and so step 8 performs exactly
    # one serialization per document (Sec. 16.3.8.1's discipline).
    settings_text = serialize_config_document(settings_document())
    models_text = serialize_config_document(
        models_document(arm_id=arm_id, base_url=base_url, model_id=model_id)
    )

    try:
        config_dir_str, _settings_path, _models_path = (
            config_issuance.derive_cfg1_config_paths(workspace)
        )
        root_identity = registered_root_identity(workspace)
    except Exception as exc:  # noqa: BLE001 - bounded; no raw text retained
        raise Cfg1PiConfigError("WORKSPACE_AUTHORITY_UNVERIFIED") from exc

    root_pin = None
    config_pin = None
    children: list = []
    proven = None
    token = None
    try:
        # -- steps 1-2: the owned root, by IDENTITY, before anything exists --
        try:
            root_pin = win.acquire_root_pin(
                workspace.experiment_root, expected_identity=root_identity
            )
        except win.Cfg1DirectoryAuthorityError as exc:
            raise Cfg1PiConfigError(exc.reason_code) from None

        # -- step 3: CreateDirectoryW. R-WINDOW opens here, closes at step 4 --
        try:
            Path(config_dir_str).mkdir(parents=False, exist_ok=False)
        except OSError as exc:
            raise Cfg1PiConfigError("CONFIG_DIR_NOT_CREATED") from exc

        # -- steps 4-5: pin it, prove it is a plain, contained directory -----
        # A refusal from here on leaves the created directory UNTOUCHED: its
        # ownership is not mechanically proven, so CFG1 never removes it. Only
        # L27's root-namespace teardown may (Sec. 37.3.2a).
        try:
            config_pin = win.acquire_config_pin(config_dir_str)
            win.prove_child_directory_entry(
                root_pin,
                name=CFG1_CONFIG_DIR_NAME,
                identity=win.pin_identity(config_pin),
            )
        except win.Cfg1DirectoryAuthorityError as exc:
            raise Cfg1PiConfigError(exc.reason_code) from None

        # -- step 6: exclusive children, ZERO content bytes ------------------
        for name in ("settings.json", "models.json"):
            try:
                children.append(
                    win.create_exclusive_child(config_dir=config_dir_str, name=name)
                )
            except win.Cfg1DirectoryAuthorityError as exc:
                raise Cfg1PiConfigError(exc.reason_code) from None

        # -- step 7: THE GATE ------------------------------------------------
        try:
            proven = win.prove_config_parentage(config_pin, children=tuple(children))
        except win.Cfg1DirectoryAuthorityError as exc:
            _dispose_children_by_handle(children)
            children = []
            raise Cfg1PiConfigError(exc.reason_code) from None

        # -- steps 8-9: content, then finalization, through those descriptors -
        settings_child, models_child = children
        try:
            win.write_child_text(settings_child, settings_text)
            win.write_child_text(models_child, models_text)
        except win.Cfg1DirectoryAuthorityError as exc:
            raise Cfg1PiConfigError(exc.reason_code) from None

        # -- step 10: issuance, bound to the proven identities ---------------
        try:
            token = config_issuance.register_config_issuance(
                workspace=workspace,
                arm_id=arm_id,
                provider_id=PROVIDER_ID,
                model_id=model_id,
                proven=proven,
                settings_child=settings_child,
                models_child=models_child,
            )
        except config_issuance.ConfigIssuanceError as exc:
            raise Cfg1PiConfigError("CONFIG_ISSUANCE_NOT_REGISTERED") from exc
    finally:
        # Step 11, on EVERY exit path, before control leaves L9: children
        # first, then the config directory, then the root. EVERY handle gets
        # its own release attempted before any failure is raised, so one
        # failure cannot strand the rest, and there is no force-close, no
        # retry, and no re-derivation of a handle from a name anywhere here.
        #
        # A close failure is LIFECYCLE-SIGNIFICANT, not memory hygiene: a
        # leaked pin makes L27's removal fail by construction (W2, W6), so it
        # is raised rather than swallowed. Exactly one closed code is reported,
        # in a fixed precedence -- the config-directory pin first, because it
        # is the one whose leak stops L27 outright. Raising here REPLACES an
        # in-flight refusal (Python chains the original as ``__context__``);
        # nothing durable is lost, because the run executor reduces every L9
        # exception to the same ``CONFIG_GENERATION_FAILED`` code, and the
        # leaked pin is the more consequential of the two facts.
        child_close_failed = False
        for child in children:
            if not win.close_child_quietly(child):
                child_close_failed = True
        win.discard_parentage_proof(proven)
        config_pin_failed = config_pin is not None and not win.release_pin_quietly(
            config_pin
        )
        root_pin_failed = root_pin is not None and not win.release_pin_quietly(root_pin)

        if config_pin_failed:
            raise Cfg1PiConfigError("CONFIG_DIR_PIN_NOT_RELEASED")
        if root_pin_failed:
            raise Cfg1PiConfigError("WORKSPACE_ROOT_PIN_NOT_RELEASED")
        if child_close_failed:
            raise Cfg1PiConfigError("CONFIG_FILE_NOT_CLOSED")

    return GeneratedCfg1Config(
        config_dir=config_dir_str,
        settings_path=str(Path(config_dir_str) / "settings.json"),
        models_path=str(Path(config_dir_str) / "models.json"),
        arm_id=arm_id,
        provider_id=PROVIDER_ID,
        model_id=model_id,
        settings_sha256=settings_digest(),
        models_redacted_sha256=redacted_models_digest(arm_id=arm_id, model_id=model_id),
        issuance_token=token,
    )
