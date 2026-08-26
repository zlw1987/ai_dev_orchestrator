"""I2-2 -- the I2-owned disposable Pi config generator for the B300 route (I2A Sec. 10).

**OFFLINE ONLY.** This module never launches Pi, never reads a real
credential, and never opens a socket. It only writes small JSON/text files
into a fresh, caller-supplied directory.

Structurally identical in shape to AR2's generator
(``experiments/pi_external_runtime_ar2/ar2/pi_config.py:84-153``), but new,
I2-owned code -- it does not import or modify that frozen module.

Hard rules, enforced here exactly like AR2 enforces its own:

1. **``maxTokens`` is never emitted.** AIDO imposes no model output-token
   ceiling by default; a value AIDO writes into a file AIDO generates is
   AIDO-configured whatever field it lands in.
2. **``apiKey`` uses ``$ENV`` interpolation only**, and the credential
   carrier is a fixed, internal variable NAME -- never a value, and never a
   caller-supplied parameter at all.
3. **Exactly one candidate model per generated config.** Candidate A and
   Candidate B are produced by calling the SAME function twice with only
   ``model_id`` varying -- no candidate-specific branch exists in this
   module at all.
4. **Route identity is not a caller-supplied parameter (5F3B-I2-FU1).**
   ``provider_id``/``credential_env_var_name`` are fixed internal
   constants; ``model_id`` is validated against the frozen first-round
   pairing before any file is created.
5. **``base_url`` is validated with the ONE shared qualification URL
   validator (5F3B-I2-FU2).** ``i2_secret_context.validate_b300_base_url``,
   BEFORE any directory or file is created -- never a second, drifting URL
   rule set.
6. **Cleanup requires REAL creation-time authority, not a public marker
   (5F3B-I2-FU3).** Independent review proved the FU2 fixed, public marker
   text was forgeable: copy the public string into an arbitrary directory
   and ``GeneratedQualificationConfig`` would accept it. Authority is now a
   fresh, unpredictable, per-run 128-bit token, generated only here, held
   by :class:`GeneratedQualificationConfig` with ``repr=False`` (never
   written to disk, never shown in any repr/diagnostic/evidence), and
   PATH-BOUND: the on-disk marker carries only a SHA-256 keyed binding of
   ``(token, resolved config_dir)`` -- copying the marker file to a
   DIFFERENT directory recomputes to a different expected binding and is
   refused, even if the (never-persisted) token were somehow also known.
7. **A generation failure after the directory exists cleans itself up
   (5F3B-I2-FU3).** If any internal write fails after ``mkdir`` succeeds, a
   best-effort verified delete is attempted using the authority this
   function itself just established, so no caller can be left holding an
   endpoint-bearing partial config with no usable cleanup capability. If
   that verified delete cannot be confirmed, :class:`QualificationPiConfigCleanupError`
   is raised (bounded, never echoing path/endpoint/credential) instead of
   silently leaving the partial directory behind.
8. **Authority requires a genuine I2 issuance fact, not just a marker
   (5F3B-I2-FU3A).** Independent review of rule 6 found the FU3 marker --
   ``SHA256(token, resolved config_dir)`` -- never actually required the
   token to be one I2 generated: a caller could mint its own token, compute
   the same public formula by hand, write a marker into an arbitrary
   directory, and both ``GeneratedQualificationConfig`` construction and
   cleanup would accept it. :func:`verify_cleanup_authority` (renamed from
   FU3's ``verify_generated_config_authority``) now ALSO requires the
   supplied token to be present, for the exact resolved ``config_dir``, in
   the process-local, in-memory-only :mod:`qualification.i2_issuance`
   registry -- populated ONLY by this module's own
   :func:`write_qualification_pi_config`. A self-forged token with a
   correctly hand-computed marker but no registry entry now fails closed as
   ``NOT_ISSUED_BY_I2``, before anything is ever deleted. The registry is
   never evidence, never persisted, and makes no claim of surviving past
   this process.
9. **Cleanup authority and complete content integrity are two different
   questions (5F3B-I2-FU3A).** A partially generated (marker written,
   ``settings.json``/``models.json`` not yet both written) config must
   still be cleanable -- it is exactly the shape a self-cleanup-on-failure
   run produces. But a CALLER consuming a config (building a child
   environment, describing it, or composing it with a secret/route) must
   never trust one whose on-disk bytes have drifted from what I2 itself
   wrote, or whose ``provider_id``/``model_id`` metadata has been relabeled
   after the fact. :func:`verify_cleanup_authority` proves only "this token
   may authorize deleting this directory, and its claimed
   provider/model identity matches what I2 issued"; the stricter
   :func:`verify_generated_config_integrity` additionally requires the
   issuance record to be FINALIZED (both files were successfully written)
   and requires the CURRENT on-disk SHA-256 of both files to still match
   the digests recorded at finalization time. Every launch-capable
   consumption path (``i2_environment.build_child_environment``,
   ``describe_generated_config``, ``i2_composition.verify_i2_identity_binding``)
   uses the stricter check; only cleanup uses the permissive one.
10. **Issuance registry mutation is package-internal only (5F3B-I2-FU3B).**
    FU3A's registry functions were public, so independent review
    self-issued authority for an arbitrary victim directory through the
    supported API alone (no private-internal bypass needed), and separately
    used a public re-finalization call to overwrite an already-trusted
    digest with a tampered one. :mod:`qualification.i2_issuance` now
    exposes only underscore-prefixed functions
    (``_register_issuance``/``_finalize_issuance``/``_lookup_issuance``/
    ``_discard_issuance``); this module and ``i2_cleanup`` are its only
    callers. Its ``IssuanceRecord`` is frozen and repr-safe, and
    finalization is one-shot -- a second finalization for an already-
    finalized token is refused (``ISSUANCE_ALREADY_FINALIZED``), never
    silently replacing trusted digests.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import i2_issuance
from .i2_identity import CREDENTIAL_ENV_VAR_NAME, PROVIDER_ID
from .i2_secret_context import validate_b300_base_url
from .records import CANDIDATE_MODEL_IDS

#: The fixed, non-secret authority marker FILENAME and SCHEMA (5F3B-I2-FU3).
#: The schema string alone is public and NOT the authority -- see rule 6.
AUTHORITY_MARKER_FILENAME = ".aido_i2_disposable_config"
AUTHORITY_MARKER_SCHEMA = "pi-implementer-qualification-i2-config.v2"

#: 128 bits, per-run, generated only by :func:`write_qualification_pi_config`.
_AUTHORITY_TOKEN_BYTES = 16


class QualificationPiConfigError(Exception):
    """The disposable Pi qualification config could not be generated safely."""


class QualificationPiConfigCleanupError(Exception):
    """Generation failed internally AND the resulting partial config could
    not be verified-deleted afterward.

    Never a forensic-erasure claim, and never echoes endpoint, path, or
    credential content -- only a fixed, bounded reason code.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(
            f"config generation failed and cleanup could not be verified: {reason_code}"
        )
        self.reason_code = reason_code


class CleanupAuthorityError(Exception):
    """Creation-time authority for a disposable I2 config directory could not
    be established.

    **Never echoes the caller-supplied path.** Only a fixed, bounded reason
    code -- a workspace-absolute path is itself sensitive content (see
    ``qualification.safety.ArtifactSafetyContext.workspace_absolute_path``),
    so it must never appear in an exception message raised on a refusal
    path that fires precisely because authority/trust could not be proven.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cleanup authority refused: {reason_code}")
        self.reason_code = reason_code


def _compute_authority_binding(*, token: str, config_dir: Path) -> str:
    """A per-run keyed binding of ``token`` to the RESOLVED config directory.

    SHA-256 over ``"{token}:{resolved_config_dir}"``. Deliberately one-way:
    the binding alone never reveals the token, and the binding computed for
    one directory does not validate for any other directory -- copying a
    marker file (which carries only this binding, never the token) to a
    different path recomputes to a different expected value there.
    """
    material = f"{token}:{config_dir}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _write_authority_marker(*, config_dir: Path, token: str) -> None:
    """Write the marker FIRST, before any other file (5F3B-I2-FU2/FU3).

    The marker never contains the token itself, an endpoint, a credential,
    model output, or a workspace path -- only the fixed public schema
    string and the one-way keyed binding.
    """
    binding = _compute_authority_binding(token=token, config_dir=config_dir)
    marker_document = {"schema": AUTHORITY_MARKER_SCHEMA, "binding": binding}
    marker_path = config_dir / AUTHORITY_MARKER_FILENAME
    marker_path.write_text(json.dumps(marker_document) + "\n", encoding="utf-8")


def verify_cleanup_authority(
    *,
    config_dir: str,
    settings_path: str,
    models_path: str,
    authority_token: str,
    provider_id: str,
    model_id: str,
) -> i2_issuance.IssuanceRecord:
    """Verify enough to authorize DELETING ``config_dir`` -- and nothing more.

    Performs NO filesystem mutation, ever -- this is the check that
    authorizes a subsequent recursive delete elsewhere
    (``qualification.i2_cleanup.scrub_generated_qualification_config``,
    and this module's own :class:`GeneratedQualificationConfig`
    construction), and it never deletes anything itself. Required, in
    order:

    1. ``config_dir`` resolves to an existing directory.
    2. ``settings_path``/``models_path`` resolve to EXACTLY
       ``config_dir/settings.json`` / ``config_dir/models.json`` -- direct
       structural children, not merely "somewhere underneath".
    3. The fixed authority marker exists directly inside ``config_dir``,
       parses as the expected JSON shape, carries EXACTLY the expected
       schema string, and its stored ``binding`` matches the binding
       recomputed from ``(authority_token, resolved config_dir)`` --
       proven with a constant-time comparison
       (:func:`secrets.compare_digest`).
    4. **(5F3B-I2-FU3A)** ``authority_token`` is currently present in the
       process-local :mod:`qualification.i2_issuance` registry for this
       EXACT resolved ``config_dir`` -- i.e. this token was genuinely
       issued by :func:`write_qualification_pi_config`, in this process,
       for this directory. A caller-chosen token that happens to satisfy
       steps 1-3 (by hand-computing the public binding formula) but was
       never registered fails here as ``NOT_ISSUED_BY_I2``.
    5. **(5F3B-I2-FU3A)** The registered issuance record's own
       ``provider_id``/``model_id`` match the ``provider_id``/``model_id``
       supplied here -- i.e. the caller's claimed identity for this config
       agrees with what I2 itself issued. A genuinely-authorized token
       cannot be reused to authorize a RELABELED identity.

    A caller who does not hold the genuine, in-memory ``authority_token``
    (i.e. anyone other than the code that legitimately received it from
    :func:`write_qualification_pi_config` via a
    :class:`GeneratedQualificationConfig`) cannot pass step 3, even if they
    can read or copy the on-disk marker file, because the marker never
    contains the token and the binding is path-bound. And even a caller who
    somehow reused a genuine token cannot pass step 4/5 for a directory or
    identity I2 did not itself issue that token for.

    Raises :class:`CleanupAuthorityError` (never echoing the path) on any
    failure; returns the matched :class:`~qualification.i2_issuance.IssuanceRecord`
    on success.
    """
    resolved_dir = Path(config_dir).resolve()
    if not resolved_dir.is_dir():
        raise CleanupAuthorityError("CONFIG_DIR_NOT_A_DIRECTORY")

    expected_settings = resolved_dir / "settings.json"
    expected_models = resolved_dir / "models.json"
    try:
        resolved_settings = Path(settings_path).resolve()
        resolved_models = Path(models_path).resolve()
    except OSError as exc:  # pragma: no cover - defensive; Path.resolve rarely raises
        raise CleanupAuthorityError("PATH_UNRESOLVABLE") from exc
    if resolved_settings != expected_settings:
        raise CleanupAuthorityError("SETTINGS_PATH_NOT_STRUCTURAL_CHILD")
    if resolved_models != expected_models:
        raise CleanupAuthorityError("MODELS_PATH_NOT_STRUCTURAL_CHILD")

    marker_path = resolved_dir / AUTHORITY_MARKER_FILENAME
    if not marker_path.is_file():
        raise CleanupAuthorityError("MARKER_MISSING")
    try:
        raw_marker = marker_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CleanupAuthorityError("MARKER_UNREADABLE") from exc

    try:
        marker_document = json.loads(raw_marker)
    except ValueError as exc:
        raise CleanupAuthorityError("MARKER_MALFORMED") from exc
    if not isinstance(marker_document, dict):
        raise CleanupAuthorityError("MARKER_MALFORMED")
    if marker_document.get("schema") != AUTHORITY_MARKER_SCHEMA:
        raise CleanupAuthorityError("MARKER_SCHEMA_MISMATCH")

    stored_binding = marker_document.get("binding")
    if not isinstance(stored_binding, str) or not stored_binding:
        raise CleanupAuthorityError("MARKER_BINDING_MISSING")
    expected_binding = _compute_authority_binding(token=authority_token, config_dir=resolved_dir)
    if not secrets.compare_digest(stored_binding, expected_binding):
        raise CleanupAuthorityError("MARKER_BINDING_MISMATCH")

    record = i2_issuance._lookup_issuance(token=authority_token, config_dir=resolved_dir)
    if record is None:
        raise CleanupAuthorityError("NOT_ISSUED_BY_I2")
    if record.provider_id != provider_id or record.model_id != model_id:
        raise CleanupAuthorityError("ISSUED_METADATA_MISMATCH")
    return record


def verify_generated_config_integrity(
    *,
    config_dir: str,
    settings_path: str,
    models_path: str,
    authority_token: str,
    provider_id: str,
    model_id: str,
) -> i2_issuance.IssuanceRecord:
    """Verify enough to trust ``config_dir`` for a LAUNCH-CAPABLE consumption.

    Strictly stronger than :func:`verify_cleanup_authority`, which it calls
    first (so every cleanup-authority failure mode applies here too, with
    the same reason codes). On top of that:

    1. The matched issuance record must be FINALIZED
       (``record.is_finalized``) -- both ``settings.json`` and
       ``models.json`` were successfully written and their digests
       recorded. An issued-but-not-yet-finalized (partial) config fails
       here as ``CONFIG_NOT_FINALIZED``, even though it remains cleanable.
    2. The CURRENT on-disk SHA-256 of ``settings_path`` exactly matches the
       digest recorded at finalization time (``SETTINGS_CONTENT_MISMATCH``
       otherwise).
    3. The CURRENT on-disk SHA-256 of ``models_path`` exactly matches the
       digest recorded at finalization time (``MODELS_CONTENT_MISMATCH``
       otherwise).

    Any post-generation edit to either file -- a relabeled model id, an
    added ``maxTokens``, a changed ``baseUrl``, a substituted literal
    secret in place of the ``$ENV`` reference, a retry/tool/trust policy
    edit in ``settings.json`` -- changes that file's bytes and therefore
    its digest, so it is caught here, unconditionally, without needing a
    field-by-field diff.

    Raises :class:`CleanupAuthorityError` (never echoing the path or file
    contents) on any failure; returns the matched, finalized
    :class:`~qualification.i2_issuance.IssuanceRecord` on success.
    """
    record = verify_cleanup_authority(
        config_dir=config_dir,
        settings_path=settings_path,
        models_path=models_path,
        authority_token=authority_token,
        provider_id=provider_id,
        model_id=model_id,
    )
    if not record.is_finalized:
        raise CleanupAuthorityError("CONFIG_NOT_FINALIZED")

    try:
        settings_bytes = Path(settings_path).read_bytes()
        models_bytes = Path(models_path).read_bytes()
    except OSError as exc:
        raise CleanupAuthorityError("CONFIG_FILE_UNREADABLE") from exc

    if hashlib.sha256(settings_bytes).hexdigest() != record.settings_sha256:
        raise CleanupAuthorityError("SETTINGS_CONTENT_MISMATCH")
    if hashlib.sha256(models_bytes).hexdigest() != record.models_sha256:
        raise CleanupAuthorityError("MODELS_CONTENT_MISMATCH")
    return record


@dataclass(frozen=True)
class GeneratedQualificationConfig:
    """Where the disposable config landed. Never carries the credential value.

    **Valid by construction (5F3B-I2-FU2, tokenized in FU3, issuance-bound in
    FU3A).** ``__post_init__`` calls :func:`verify_cleanup_authority` with
    ``self.authority_token``/``self.provider_id``/``self.model_id``, so this
    object cannot be forged to describe an arbitrary directory OR relabeled
    identity: constructing one against a directory lacking a marker whose
    binding matches the SUPPLIED token raises :class:`CleanupAuthorityError`
    immediately (before the object exists at all), as does supplying a
    genuine token/path pair together with a ``provider_id``/``model_id``
    that disagrees with what I2 itself issued for that token. The one
    function that legitimately produces a
    register-then-marker-then-object sequence is
    :func:`write_qualification_pi_config`.

    ``authority_token`` is ``field(repr=False)`` and is never written to
    disk, logged, or included in any evidence -- see module docstring rule
    6. ``provider_id``/``model_id`` are NOT secrets and are shown normally;
    they exist so config/secret/route identity can be cross-checked
    (``qualification.i2_composition``) without re-parsing JSON.
    """

    config_dir: str
    settings_path: str
    models_path: str
    provider_id: str
    model_id: str
    authority_token: str = field(repr=False)

    def __post_init__(self) -> None:
        verify_cleanup_authority(
            config_dir=self.config_dir,
            settings_path=self.settings_path,
            models_path=self.models_path,
            authority_token=self.authority_token,
            provider_id=self.provider_id,
            model_id=self.model_id,
        )


def _settings_document() -> dict[str, object]:
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
        # Pi's OWN provider-transport retry, disabled: one semantic attempt's
        # individual failed provider request is not auto-retried. This says
        # nothing about, and does not bound, how many separate provider
        # requests Pi's agent loop may issue across one semantic prompt's
        # turn (I2A Sec. 7.1/10).
        "retry": {
            "enabled": True,
            "maxRetries": 3,
            "baseDelayMs": 2000,
            "provider": {"maxRetries": 0},
        },
    }


def _best_effort_verified_cleanup(config_dir: Path) -> bool:
    """Delete ``config_dir`` if present, and VERIFY absence afterward.

    Internal to this module's own self-cleanup-on-failure path (rule 7) --
    never claims forensic erasure, and swallows an ``OSError`` from the
    delete attempt itself so the CALLER's verification (not this helper's
    exception) is what decides pass/fail.
    """
    try:
        if config_dir.exists():
            shutil.rmtree(config_dir, ignore_errors=True)
    except OSError:
        pass
    return not config_dir.exists()


def write_qualification_pi_config(
    experiment_root: str,
    *,
    model_id: str,
    base_url: str,
) -> GeneratedQualificationConfig:
    """Write ``settings.json`` + ``models.json`` for one B300 qualification run.

    ``base_url`` is written into the disposable ``models.json`` and is
    NEVER recorded, printed, or echoed anywhere else by this function.

    **Route identity is fixed, not caller-supplied (5F3B-I2-FU1).** There
    is no ``provider_id`` or ``credential_env_var_name`` parameter.
    ``model_id`` must be exactly one of the frozen first-round candidate
    model ids; ``base_url`` must pass the ONE shared qualification URL
    validator (5F3B-I2-FU2). Every identity/URL check below runs BEFORE any
    directory or file is created, so a validation failure leaves nothing on
    disk.

    **5F3B-I2-FU3: self-cleanup on internal failure.** Once the directory
    exists, any internal failure (including one an injected test double
    forces) triggers a best-effort verified delete using the authority this
    call just established, before the original exception is re-raised. If
    that delete cannot be verified, :class:`QualificationPiConfigCleanupError`
    is raised instead (chained from the original failure).

    **5F3B-I2-FU3A: token generated before ``mkdir``; issuance registered
    and finalized around the writes.** The fresh authority token is now
    generated BEFORE the directory is created at all, so the one
    filesystem-mutating call that can fail before any authority exists
    (``mkdir`` itself) leaves nothing to clean up and nothing registered.
    Once the directory exists, the run is registered with
    :mod:`qualification.i2_issuance` (rule 8) before the marker is written,
    and finalized with both files' SHA-256 digests (rule 9) only after both
    have been written successfully. Any failure anywhere in that sequence
    both attempts the existing verified filesystem cleanup AND discards the
    (possibly partial) issuance record, so no orphaned registry entry can
    outlive a failed run.
    """
    validate_b300_base_url(base_url)
    if not model_id or not model_id.strip():
        raise QualificationPiConfigError("config error: model_id must be non-blank")
    if model_id not in CANDIDATE_MODEL_IDS.values():
        raise QualificationPiConfigError(
            f"config error: {model_id!r} is not one of the frozen first-round "
            f"candidate model ids {sorted(CANDIDATE_MODEL_IDS.values())!r}"
        )

    provider_id = PROVIDER_ID
    credential_env_var_name = CREDENTIAL_ENV_VAR_NAME

    # Generated BEFORE mkdir (5F3B-I2-FU3A item H): if this somehow failed,
    # no directory would exist yet and nothing would need cleanup.
    token = secrets.token_hex(_AUTHORITY_TOKEN_BYTES)

    config_dir = Path(experiment_root) / "i2_pi_config"
    config_dir.mkdir(parents=True, exist_ok=False)

    try:
        # Registered BEFORE the marker is written, so verify_cleanup_authority's
        # registry check (rule 8) is satisfiable the instant the marker exists.
        i2_issuance._register_issuance(
            token=token, config_dir=config_dir, provider_id=provider_id, model_id=model_id
        )

        # The authority marker is written next, before any other file, so
        # a config directory's mere existence up to this point is never
        # mistaken for genuine I2 authority.
        _write_authority_marker(config_dir=config_dir, token=token)

        settings = _settings_document()
        settings_text = json.dumps(settings, indent=2) + "\n"
        settings_path = config_dir / "settings.json"
        settings_path.write_text(settings_text, encoding="utf-8")

        api_key_expression = f"${credential_env_var_name}"
        models: dict[str, object] = {
            "providers": {
                provider_id: {
                    "baseUrl": base_url,
                    "api": "openai-completions",
                    "apiKey": api_key_expression,
                    "models": [
                        {
                            "id": model_id,
                            "reasoning": True,
                            # NOTE: maxTokens is deliberately ABSENT. See rule 1.
                        }
                    ],
                }
            }
        }

        provider_doc = models["providers"][provider_id]  # type: ignore[index]
        resolved_api_key = provider_doc["apiKey"]  # type: ignore[index]
        if not resolved_api_key.startswith("$") or resolved_api_key.startswith("$$"):
            raise QualificationPiConfigError(
                "config error: apiKey must use exact '$ENV_NAME' interpolation"
            )
        if "!" in resolved_api_key:
            raise QualificationPiConfigError(
                "config error: apiKey must never use '!shell' resolution"
            )
        if resolved_api_key != api_key_expression:
            raise QualificationPiConfigError(
                "config error: apiKey does not match the expected $ENV reference form"
            )

        models_text = json.dumps(models, indent=2) + "\n"
        if "maxTokens" in models_text:
            raise QualificationPiConfigError(
                "config error: the generated models.json must not contain maxTokens"
            )

        models_path = config_dir / "models.json"
        models_path.write_text(models_text, encoding="utf-8")

        # Finalized ONLY once both files are successfully on disk (rule 9):
        # from this point on, verify_generated_config_integrity can prove
        # the exact bytes I2 itself wrote. Digests are computed from the
        # bytes actually READ BACK from disk -- not from the in-memory text
        # re-encoded -- because Path.write_text's universal-newline
        # translation (``\n`` -> ``os.linesep``, i.e. ``\r\n`` on Windows)
        # means the on-disk bytes can differ from ``text.encode("utf-8")``.
        i2_issuance._finalize_issuance(
            token=token,
            config_dir=config_dir,
            settings_sha256=hashlib.sha256(settings_path.read_bytes()).hexdigest(),
            models_sha256=hashlib.sha256(models_path.read_bytes()).hexdigest(),
        )

        return GeneratedQualificationConfig(
            config_dir=str(config_dir),
            settings_path=str(settings_path),
            models_path=str(models_path),
            provider_id=provider_id,
            model_id=model_id,
            authority_token=token,
        )
    except Exception as original_exc:
        cleanup_verified = _best_effort_verified_cleanup(config_dir)
        i2_issuance._discard_issuance(token=token, config_dir=config_dir)
        if not cleanup_verified:
            raise QualificationPiConfigCleanupError(
                "PARTIAL_CONFIG_CLEANUP_UNVERIFIED"
            ) from original_exc
        raise


def describe_generated_config(generated: GeneratedQualificationConfig) -> dict[str, object]:
    """A recordable, secret-free description of one genuinely I2-generated config.

    **5F3B-I2-FU3: no arbitrary path strings.** Takes ONLY the typed
    :class:`GeneratedQualificationConfig` capability object -- never
    caller-supplied ``settings_path``/``models_path`` strings that could
    point at an arbitrary JSON document and manufacture evidence-ish
    provider/model/env-var-name fields.

    **5F3B-I2-FU3A: requires COMPLETE integrity, not just cleanup
    authority.** Re-verifies :func:`verify_generated_config_integrity`
    before reading anything, so a tampered (post-generation-edited) or
    merely partial (not-yet-finalized) config can never have its bytes
    parsed and reported as though they were still what I2 wrote.

    Reports only structural facts, never the base URL, the resolved apiKey
    value, or any host -- mirrors the reporting discipline of AR2's own
    ``describe_generated_config``.
    """
    verify_generated_config_integrity(
        config_dir=generated.config_dir,
        settings_path=generated.settings_path,
        models_path=generated.models_path,
        authority_token=generated.authority_token,
        provider_id=generated.provider_id,
        model_id=generated.model_id,
    )
    settings = json.loads(Path(generated.settings_path).read_text(encoding="utf-8"))
    models = json.loads(Path(generated.models_path).read_text(encoding="utf-8"))
    provider_ids = sorted(models.get("providers", {}))
    provider = models["providers"][provider_ids[0]] if provider_ids else {}
    model_entries = provider.get("models", [])
    api_key_expression = provider.get("apiKey", "")
    return {
        "settings_keys": sorted(settings),
        "settings_ambient_sources_emptied": all(
            settings.get(key) == []
            for key in ("packages", "extensions", "skills", "prompts", "themes")
        ),
        "settings_default_project_trust": settings.get("defaultProjectTrust"),
        "settings_provider_max_retries": settings.get("retry", {})
        .get("provider", {})
        .get("maxRetries"),
        "models_provider_ids": provider_ids,
        "models_provider_api": provider.get("api"),
        "models_model_ids": [entry.get("id") for entry in model_entries],
        "models_json_contains_max_tokens": any("maxTokens" in e for e in model_entries)
        or "maxTokens" in provider,
        "api_key_resolution": (
            "env_interpolation"
            if api_key_expression.startswith("$") and not api_key_expression.startswith("$$")
            else "other"
        ),
        "api_key_uses_shell_command_resolution": api_key_expression.startswith("!"),
        "api_key_env_variable_name": (
            api_key_expression.lstrip("$") if api_key_expression.startswith("$") else None
        ),
        "base_url_recorded": False,
    }
