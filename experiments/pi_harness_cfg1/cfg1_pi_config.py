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
   ``json.dumps(..., indent=2) + newline`` shape and the same
   ``Path.write_text`` call, so the on-disk bytes -- including Windows
   newline translation -- agree exactly.
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


def write_cfg1_pi_config(
    workspace, *, arm_id: str, base_url: str, model_id: str = CFG1_MODEL_ID
) -> GeneratedCfg1Config:
    """Write one run's ``settings.json`` + ``models.json`` for one arm.

    ``workspace`` is a genuine, ACTIVE ``Cfg1RunWorkspace`` ownership handle --
    never a bare path. The directory is created with ``exist_ok=False`` at the
    location :func:`config_issuance.derive_cfg1_config_paths` derives from that
    handle's own re-verified ``experiment_root`` -- the ONE on-disk location of
    this run's endpoint value, verified-unlinked at L24 before any
    model-influenced code runs (Sec. 16.2). A caller cannot select a different
    location: there is no parameter through which one could be named
    (CFG1-IMPL-FU1 Finding 2).
    """
    from . import config_issuance
    from .run_workspace import Cfg1RunWorkspace

    if type(arm_id) is not str or arm_id not in ARM_COMPAT:
        raise Cfg1PiConfigError("UNKNOWN_ARM_ID")
    if type(workspace) is not Cfg1RunWorkspace:
        raise Cfg1PiConfigError("NOT_A_CFG1_RUN_WORKSPACE")

    try:
        config_dir_str, settings_path_str, models_path_str = (
            config_issuance.derive_cfg1_config_paths(workspace)
        )
    except config_issuance.ConfigIssuanceError as exc:
        raise Cfg1PiConfigError("WORKSPACE_AUTHORITY_UNVERIFIED") from exc

    config_dir = Path(config_dir_str)
    try:
        config_dir.mkdir(parents=False, exist_ok=False)
    except OSError as exc:
        raise Cfg1PiConfigError("CONFIG_DIR_NOT_CREATED") from exc

    settings_path = Path(settings_path_str)
    models_path = Path(models_path_str)
    try:
        settings_path.write_text(
            serialize_config_document(settings_document()), encoding="utf-8"
        )
        models_path.write_text(
            serialize_config_document(
                models_document(arm_id=arm_id, base_url=base_url, model_id=model_id)
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        raise Cfg1PiConfigError("CONFIG_FILES_NOT_WRITTEN") from exc

    token = config_issuance.register_config_issuance(
        workspace=workspace,
        arm_id=arm_id,
        provider_id=PROVIDER_ID,
        model_id=model_id,
    )
    return GeneratedCfg1Config(
        config_dir=config_dir_str,
        settings_path=settings_path_str,
        models_path=models_path_str,
        arm_id=arm_id,
        provider_id=PROVIDER_ID,
        model_id=model_id,
        settings_sha256=settings_digest(),
        models_redacted_sha256=redacted_models_digest(arm_id=arm_id, model_id=model_id),
        issuance_token=token,
    )
