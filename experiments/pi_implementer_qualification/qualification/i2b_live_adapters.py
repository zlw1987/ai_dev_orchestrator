"""5F3B-I2B-L1 -- the real live adapters for the frozen Category-B controller.

**THIS MODULE PERFORMS REAL, LIVE ACTIVITY.** Unlike every other module in
this package, it launches a real Node/Pi process, opens a real Windows named
pipe, and (via the injected connection reader) reads a real credential. It
sends **zero semantic prompts** -- :data:`qualification.i2b_controller.
SEMANTIC_PROMPTS_SENT` is never touched here, and no name in this module is
ever bound to a prompt string, a task, or an agent instruction. There is no
function here that accepts, sends, or forwards anything an agent could act
on; the only RPC command types this module ever sends are ``get_commands``
and ``get_state`` -- introspection calls, never ``prompt``.

Architectural rule (5F3B-I2B-L1 brief): **live adapters produce
observations; the frozen ``run_category_b_controller`` produces verdicts.**
Nothing here returns a bare ``passed``/``compatibility_ok`` boolean anywhere
-- every method below returns exactly the bounded, valid-by-construction
observation type :mod:`qualification.i2b_session` already declares, and gate
ordering, first-failure attribution, resource/session correlation, creator
partial-failure accounting, teardown/shutdown status, cleanup status,
evidence safety and the terminal PASS/REFUSAL decision all remain the frozen
controller's exclusive authority. This module is not a second controller and
does not duplicate the frozen lifecycle.

What is reused, unmodified, from frozen AR2 (composition, never copying):

    ar2.broker            BrokerBinding, BrokerRequestHandler, BrokerServer,
                           BrokerDiagnostics, STATE_READY, STATE_CLOSED,
                           TRIGGER_AIDO_TEARDOWN
    ar2.capability         StaticEligibilityDomain, RunState, CapDefinitions,
                           OPERATION_CLASSES, ROOT_CLASS_DISPOSABLE_SYNTHETIC
    ar2.launch             RuntimeIdentity, LaunchIdentityError,
                           build_pi_argv, and (composed, not the pinned
                           ``resolve_runtime_identity``) the SAME private
                           node/Pi-location helpers
                           ``experiments/pi_external_runtime_ar2_o1/
                           o1/pi_compat.py`` already reuses this way
    ar2.pi_config          write_disposable_extension, TOOL_ALLOWLIST (value,
                           duplicated below -- see the note at its
                           declaration), scrub_generated_extension_config
    ar2.handshakes         evaluate_extension_identity (H1 only -- H2 is a
                           direct field read, per the brief's "no
                           independent H2 callback" instruction)
    ar2.supervisor         PiRpcSupervisor, RunBounds, RUNTIME_RESPONSE_RECEIVED
    ar2.route_check        check_route_serves_model, passed to the frozen
                           controller's ``route_checker`` parameter DIRECTLY
                           (its call shape already matches
                           ``run_offline_route_check``'s expectation exactly
                           -- no wrapper is needed or added)

**Never reused, and never will be:** ``ar2.launch.resolve_runtime_identity``
(pins an EXACT Pi version as an authorization gate -- this package, like
``o1.pi_compat``, treats the observed version as provenance only, never
authorization); ``ar2.capability.mint_capability`` (see
:func:`_build_inert_static_eligibility_domain` for why); any AR2/O1
task-capability, candidate-repository, or prompt-manifest machinery
(``ar2.candidate``, ``ar2.manifest``, ``ar2.observation``,
``ar2.verification``, every ``o1.*`` module) -- Category-B has no candidate
task, sends no prompt, and diffs nothing.

Why the broker's capability is INERT (not scoped to the qualification
workspace's tracked-file manifest)
--------------------------------------------------------------------------

``ar2.capability.mint_capability`` requires a real
:class:`ar2.capability.DisposableRootAuthority`, obtainable only from
:func:`ar2.fixtures.create_disposable_experiment_root` -- and
:mod:`qualification.i2b_workspace` deliberately does not expose the one it
mints internally for the run's :class:`~qualification.i2b_workspace.
QualificationRunWorkspace` (by design: an exposed authority object is
exactly the kind of thing a future caller could misuse to mint an
independent, wider capability against the same disposable root). Minting a
SECOND, unrelated disposable root purely so ``mint_capability`` has
something to consume would create a directory tree with no relationship to
the run's actual workspace and no cleanup ownership story, for a capability
that a zero-prompt run structurally never uses (no prompt is ever sent, so
Pi never has a reason to invoke ``aido_read``/``aido_edit`` at all).

Instead, :func:`_build_inert_static_eligibility_domain` constructs a
:class:`~ar2.capability.StaticEligibilityDomain` DIRECTLY -- it is a plain
dataclass with no ``__post_init__`` invariant of its own; every eligibility
rule lives in ``mint_capability`` and in ``ar2.candidate.
evaluate_delegated_candidate``, never in the class itself. The constructed
SED names ``canonical_root=`` the run's own already-verified
``QualificationRunWorkspace.workspace_root`` (so it is at least an honest,
real, disposable directory) but with EMPTY ``read_eligible``/
``write_eligible`` -- which, read against ``evaluate_delegated_candidate``'s
own source (``ar2/candidate.py``), means every read/edit request is refused
as ``not_read_eligible``/``not_write_eligible`` unconditionally. This SED can
never authorize a single file operation, for any path, ever -- which is the
CORRECT, honest capability shape for a run with no candidate task.

Why one real ``get_commands`` round trip is shared between two adapter methods
-------------------------------------------------------------------------------

The frozen ``RuntimeLaunchObservation.lf_jsonl_correlation_succeeded`` fact
requires an actual LF-framed JSONL request/response round trip to establish
-- there is no lighter-weight RPC command in Pi's protocol (only
``get_commands``, ``get_state`` and ``prompt`` exist anywhere in this
codebase's live wiring; grep confirms it). Reusing ``get_state`` for this
would contaminate H2's own single-observation discipline; sending a SECOND,
distinct real ``get_commands`` frame later (once for launch correlation, once
again for the frozen ``get_commands`` adapter's own H1 observation) would
mean two live wire frames of the same RPC type for one run, which the L1
brief's own safety bookkeeping ("get_commands count <= 1") reads most
conservatively as forbidding.

So :meth:`LiveCategoryBAdapters.launch_runtime` sends the ONE real
``get_commands`` frame this run ever sends, uses it to establish
``lf_jsonl_correlation_succeeded``/``required_flags_accepted``, and CACHES
the raw response keyed by the minted ``runtime_session_id``.
:meth:`LiveCategoryBAdapters.get_commands` -- the frozen controller's own,
separate adapter call, invoked later against the returned
:class:`~qualification.i2b_session.RuntimeSession` -- never re-sends the
RPC; it re-projects that ONE cached real response through the SAME frozen
H1 machinery (:func:`~qualification.i2b_session.h1_components_from_frozen_
evaluation`) the offline suite already tests. There is still exactly ONE
real ``get_commands`` observation for this run; it is simply consumed by two
adapter methods rather than by one bundled call, matching the frozen
``i2b_session``/``i2b_controller`` contract's own separate-adapter shape.
``get_state`` has no such reuse: the frozen ``get_state`` adapter sends its
own single, fresh, real ``get_state`` frame, never shared with anything.

Session/ownership discipline (adversarial items 1-5, 7-10 of the L1 brief)
----------------------------------------------------------------------------

Every session this module hands to the frozen controller is looked up again,
by this module's OWN process-local registry, on every later call that
receives one back (``get_commands``/``get_state``/``observe_protocol``/
``shutdown_runtime``/``shutdown_broker``) -- never trusted merely because the
object's fields look well-formed. A session this module did not itself mint
and register is refused here, defense-in-depth on top of the frozen
controller's own ``run_id``/``broker_session_id``/``runtime_session_id``
correlation checks. A partial launch failure (the Pi process started but the
correlation probe could not establish a trustworthy session) is retained and
self-closed here, exactly once, bounded, per the frozen creator-partial-
failure contract -- never handed to the controller as a trusted session, and
never retried.

Credential/secret discipline
-----------------------------

:meth:`LiveCategoryBAdapters.read_connection` is the ONLY place this module
reads a credential, and it does so through the frozen, unmodified
``qualification.i2_credentials.read_connection_values`` -- there is no
second environment reader anywhere in this module. No credential value, base
URL, endpoint host, ``Authorization`` text, broker token, pipe name,
capability id, or absolute qualification workspace path is ever logged,
printed, ``repr()``'d, or placed in an exception message anywhere below;
every exception this module raises either propagates a frozen, already-safe
exception type (``ObservationError``, ``PiSupervisorError``,
``LaunchIdentityError``) or is a bounded, literal-string ``RuntimeError``
naming no runtime value.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import secrets
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ar2
from ar2.broker import (
    STATE_CLOSED,
    STATE_CREATED,
    STATE_READY,
    TRIGGER_AIDO_TEARDOWN,
    BrokerBinding,
    BrokerDiagnostics,
    BrokerRequestHandler,
    BrokerServer,
)
from ar2.capability import (
    OPERATION_CLASSES,
    ROOT_CLASS_DISPOSABLE_SYNTHETIC,
    CapDefinitions,
    RunState,
    StaticEligibilityDomain,
)
from ar2.handshakes import evaluate_extension_identity
from ar2.launch import (
    LaunchIdentityError,
    RuntimeIdentity,
    build_pi_argv,
)
from ar2.launch import (
    _resolve_node_executable as _ar2_resolve_node_executable,  # noqa: F401 -- deliberate reuse, matching o1.pi_compat's own precedent
)
from ar2.launch import (
    _resolve_pi_package_root as _ar2_resolve_pi_package_root,  # noqa: F401 -- deliberate reuse, matching o1.pi_compat's own precedent
)
from ar2.pi_config import (
    GeneratedExtension,
    write_disposable_extension,
)
from ar2.route_check import check_route_serves_model
from ar2.supervisor import (
    RUNTIME_DEADLINE_EXPIRED,
    RUNTIME_EVENT_CAP_EXCEEDED,
    RUNTIME_OUTPUT_CAP_EXCEEDED,
    RUNTIME_PROTOCOL_VIOLATION,
    RUNTIME_READ_ERROR,
    RUNTIME_RESPONSE_RECEIVED,
    PiRpcSupervisor,
    RunBounds,
)

from .i2_credentials import ConnectionValues, PreflightGateResult, read_connection_values
from .i2_environment import (
    FORBIDDEN_NAME_FRAGMENTS,
    WITHHELD_PROFILE_NAMES,
    EnvironmentPolicyError,
    audit_withheld_names,
    build_child_environment,
)
from .i2_identity import CREDENTIAL_ENV_VAR_NAME
from .i2_cleanup import scrub_generated_qualification_config
from .i2_pi_config import (
    CleanupAuthorityError,
    GeneratedQualificationConfig,
    QualificationPiConfigCleanupError,
    QualificationPiConfigError,
    describe_generated_config,
    verify_generated_config_integrity,
    write_qualification_pi_config,
)
from .i2_route import RouteDescriptorError, route_descriptor_for_candidate
from .i2_secret_context import InvalidBaseUrlError, SecretContextError, build_secret_context
from .records import CANDIDATE_MODEL_IDS as _CANDIDATE_MODEL_IDS
from .safety import ArtifactSafetyContext, qualification_scrub_check
from .i2b_session import (
    BrokerCreationObservation,
    BrokerCreationRequest,
    BrokerSession,
    BrokerShutdownObservation,
    GetCommandsObservation,
    GetStateObservation,
    ObservationError,
    ProtocolObservation,
    RuntimeLaunchObservation,
    RuntimeLaunchRequest,
    RuntimeSession,
    RuntimeShutdownObservation,
    h1_components_from_frozen_evaluation,
    observed_command_from_reported_entry,
)
from .i2b_workspace import QUALIFICATION_EXPERIMENT_ID

#: AR2's own tool allowlist, duplicated as a VALUE -- never imported -- per
#: this package's established precedent (see e.g.
#: ``qualification.i2b_session``'s own ``CATEGORY_B_SENTINEL_COMMAND_NAME``
#: docstring for the same reasoning). An offline test asserts the two agree.
TOOL_ALLOWLIST: tuple[str, ...] = ("aido_read", "aido_edit")

#: How long this module waits for the one real, launch-time correlation
#: probe (``get_commands``) and the later, separate ``get_state`` call.
#: Deliberately the SAME bound AR2/O1 already use for their own startup
#: handshakes -- not a new, unreviewed timeout policy.
_DEFAULT_BOUNDS = RunBounds()


class LiveAdapterError(RuntimeError):
    """A live adapter could not complete its call. Fails closed.

    Deliberately a bare, literal-string exception: every message here is a
    fixed sentence naming no runtime value (no path, no id, no credential,
    no raw RPC body). The frozen controller's own ``_invoke`` reduces any
    exception from an injected adapter to a bounded failure code and never
    reads this message; it exists only for a human reading a traceback
    during implementation/testing.
    """


# -- BLOCKER 1 (5F3B-I2B-L1-FU2): executable-source authority ----------------
#
# The disposable extension's SOURCE directory is derived deterministically
# from THIS package's own reused ``ar2`` import -- there is no constructor
# parameter, and no supported path anywhere in this module's public surface
# through which a caller can substitute an arbitrary extension source. Before
# that source is ever handed to ``write_disposable_extension`` (which copies
# it into a real Node/Pi-loaded location), its exact byte content is verified
# against a fixed, reviewed digest -- never a caller-supplied one.

#: ``ar2.__file__`` resolves to
#: ``experiments/pi_external_runtime_ar2/ar2/__init__.py``; its grandparent
#: directory is ``pi_external_runtime_ar2``, and ``extension/`` is that
#: directory's fixed sibling.
_AR2_EXPERIMENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(ar2.__file__)))
_FROZEN_AR2_EXTENSION_SOURCE_DIR = os.path.realpath(
    os.path.join(_AR2_EXPERIMENT_ROOT, "extension")
)

#: The frozen, reviewed SHA-256 of the EXACT AR2 extension source tree this
#: module is authorized to copy into a real Pi/Node-loaded location --
#: computed once over every file under ``_FROZEN_AR2_EXTENSION_SOURCE_DIR``
#: (sorted relative POSIX path, then content, null-byte separated; see
#: :func:`_hash_extension_source_tree`). This is a fixed literal in THIS
#: reviewed module -- never a caller-supplied digest, never derived from an
#: exception message, and never accepted merely because a path string looks
#: right. Changing the real extension source requires updating this constant
#: in the SAME reviewed change; a mismatch fails closed.
_FROZEN_AR2_EXTENSION_SHA256 = (
    "9233ea997702c7d16704c94d7de4b7bbec652689f41c71adb1bf172a722edbcb"
)


def _hash_extension_source_tree(root: str) -> str:
    """A deterministic content digest: sorted relative POSIX path + bytes,
    null-byte separated, over every regular file under ``root``."""
    digest = hashlib.sha256()
    root_path = Path(root)
    for path in sorted(p for p in root_path.rglob("*") if p.is_file()):
        rel = path.relative_to(root_path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()


def _require_authorized_extension_source() -> str:
    """Mechanically prove the source about to be copied into a real
    Node/Pi-loaded extension is the exact frozen, reviewed AR2 extension --
    BEFORE :func:`~ar2.pi_config.write_disposable_extension` ever reads a
    byte of it (L1-FU2 BLOCKER 1). Fails closed on a missing directory or a
    content mismatch; never reports "maybe authorized".
    """
    if not os.path.isdir(_FROZEN_AR2_EXTENSION_SOURCE_DIR):
        raise LiveAdapterError(
            "launch error: the frozen AR2 extension source directory does "
            "not exist"
        )
    observed = _hash_extension_source_tree(_FROZEN_AR2_EXTENSION_SOURCE_DIR)
    if observed != _FROZEN_AR2_EXTENSION_SHA256:
        raise LiveAdapterError(
            "launch error: the frozen AR2 extension source content does not "
            "match its authorized digest"
        )
    return _FROZEN_AR2_EXTENSION_SOURCE_DIR


def _require_runtime_identity_matches_trusted_resolution(identity: RuntimeIdentity) -> None:
    """BLOCKER 1 (RuntimeIdentity variant): a same-TYPE ``RuntimeIdentity``
    carrying substituted executable paths must never pass construction
    merely because ``type(...) is RuntimeIdentity`` -- bind it mechanically
    to THIS machine's own trusted resolver path, the SAME private resolvers
    :func:`resolve_pi_identity` itself composes from. This never re-runs the
    real ``--version`` subprocess probe -- that stays exactly once, inside
    :func:`resolve_pi_identity` -- and never gates on ``reported_version``,
    which remains provenance only (no exact-version pinning is restored).
    """
    if identity.launch_shape != "node_direct":
        raise LiveAdapterError(
            "LiveCategoryBAdapters requires a RuntimeIdentity with the "
            "frozen node_direct launch shape"
        )
    if not isinstance(identity.reported_version, str) or not identity.reported_version:
        raise LiveAdapterError(
            "LiveCategoryBAdapters requires a RuntimeIdentity with a "
            "non-empty observed reported_version"
        )
    try:
        expected_node = _ar2_resolve_node_executable()
        expected_package_root = _ar2_resolve_pi_package_root()
    except LaunchIdentityError:
        raise LiveAdapterError(
            "LiveCategoryBAdapters requires a RuntimeIdentity whose paths "
            "match this machine's own trusted resolver, which itself could "
            "not resolve"
        ) from None
    expected_cli_js = os.path.realpath(os.path.join(expected_package_root, "dist", "cli.js"))
    if (
        identity.node_executable != expected_node
        or identity.pi_package_root != expected_package_root
        or identity.pi_cli_js != expected_cli_js
    ):
        raise LiveAdapterError(
            "LiveCategoryBAdapters requires a RuntimeIdentity whose "
            "executable paths match this machine's own trusted resolver "
            "path exactly"
        )


#: BLOCKER 5 follow-up (L1-FU2, raw supervisor outcome domain): the exact,
#: positive set of ``PiRpcSupervisor.await_response`` outcomes this module
#: treats as a recognized (not necessarily SUCCESSFUL) launch-correlation
#: result. An unknown/malformed outcome -- one that is not a member of this
#: fixed set -- is never treated as valid merely because it happens not to
#: equal one of the two known-bad constants; it fails closed instead.
_RECOGNIZED_AWAIT_RESPONSE_OUTCOMES = (
    RUNTIME_RESPONSE_RECEIVED,
    RUNTIME_DEADLINE_EXPIRED,
    RUNTIME_PROTOCOL_VIOLATION,
    RUNTIME_OUTPUT_CAP_EXCEEDED,
    RUNTIME_EVENT_CAP_EXCEEDED,
    RUNTIME_READ_ERROR,
)


def resolve_pi_identity() -> RuntimeIdentity:
    """Locate Node + Pi and OBSERVE Pi's version. Never gates on the value.

    Structurally identical to ``experiments/pi_external_runtime_ar2_o1/
    o1/pi_compat.py``'s ``resolve_pi_identity_provenance_only`` -- composed
    from the SAME reused AR2 primitives (never
    ``ar2.launch.resolve_runtime_identity``, which pins an exact version as
    an authorization gate) -- written here as qualification-owned code
    rather than imported across an unrelated experiment package boundary,
    matching this package's own established precedent of never importing
    AR1/AR2/O1 experiment-specific (as opposed to library-shaped) code.
    """
    import subprocess

    node_executable = _ar2_resolve_node_executable()
    package_root = _ar2_resolve_pi_package_root()
    cli_js = os.path.realpath(os.path.join(package_root, "dist", "cli.js"))
    if not os.path.isfile(cli_js):
        raise LaunchIdentityError("launch error: the resolved Pi dist/cli.js does not exist")

    try:
        completed = subprocess.run(  # noqa: S603 - resolved absolute argv, shell=False
            [node_executable, cli_js, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except OSError as exc:
        raise LaunchIdentityError(
            f"launch error: Node-direct Pi launch failed to start: {type(exc).__name__}"
        ) from None

    if completed.returncode != 0:
        raise LaunchIdentityError(
            "launch error: Node-direct Pi launch exited non-zero; no fallback "
            "launch architecture is attempted"
        )
    reported = completed.stdout.decode("utf-8", "replace").strip()
    if not reported:
        raise LaunchIdentityError(
            "launch error: Pi reported an empty version string; a version must "
            "be observable even though it is never an authorization gate"
        )
    return RuntimeIdentity(
        node_executable=node_executable,
        pi_cli_js=cli_js,
        pi_package_root=package_root,
        reported_version=reported,
        launch_shape="node_direct",
    )


#: A fixed, never-real placeholder base URL used ONLY by
#: :func:`preflight_config_generator_self_check`. ``.invalid`` is the
#: RFC 2606 reserved TLD for a domain that must never resolve. This value
#: is never read from the environment, is never the real B300 endpoint,
#: and is never retained or echoed anywhere -- it exists only to satisfy
#: ``validate_b300_base_url``'s structural shape requirement so the
#: generator's own write/verify round trip can be exercised before any
#: credential is read.
_SELF_CHECK_BASE_URL = "https://pi-qualification-self-check.invalid/v1"

#: A fixed candidate model id used ONLY to exercise the generator's own
#: validation/write/verify round trip. Never tied to this run's actual
#: candidate, and never read from any live context.
_SELF_CHECK_MODEL_ID = _CANDIDATE_MODEL_IDS["A"]


def preflight_pi_installed_offline() -> PreflightGateResult:
    """I2A §14.1 -- REAL, OFFLINE (no subprocess): Node, the Pi package
    root, and ``dist/cli.js`` all resolve to existing files on disk, via the
    SAME private resolvers :func:`resolve_pi_identity` composes from
    (``ar2.launch._resolve_node_executable``/``_resolve_pi_package_root``),
    AND the package's own ``package.json`` ``version`` field is observed by
    a plain file read -- no process launch, exactly how §4 obtained
    ``0.84.3``.

    This establishes only that Pi is INSTALLED where AR2's own launch
    machinery expects to find it -- never that it runs, and never a
    version comparison (see the module docstring on why this package
    never imports ``ar2.launch.resolve_runtime_identity``). No credential
    is read and no process is launched.
    """
    try:
        package_root = _ar2_resolve_pi_package_root()
        _ar2_resolve_node_executable()
        cli_js = os.path.realpath(os.path.join(package_root, "dist", "cli.js"))
        if not os.path.isfile(cli_js):
            raise LaunchIdentityError(
                "launch error: the resolved Pi dist/cli.js does not exist"
            )
        package_json_path = os.path.join(package_root, "package.json")
        with open(package_json_path, "r", encoding="utf-8") as handle:
            package_document = json.load(handle)
        version_field = package_document.get("version") if isinstance(package_document, dict) else None
        if not isinstance(version_field, str) or not version_field.strip():
            raise LaunchIdentityError(
                "launch error: the resolved Pi package.json has no observable "
                "version field"
            )
    except (LaunchIdentityError, OSError, ValueError):
        return PreflightGateResult(
            name="pi_installed_offline", passed=False, failure_code="NOT_INSTALLED"
        )
    return PreflightGateResult(name="pi_installed_offline", passed=True)


def preflight_config_generator_self_check() -> PreflightGateResult:
    """I2A §14.2 -- REAL, credential-free self-test of the config-generator
    round trip.

    Writes a disposable ``settings.json``/``models.json`` pair under a
    throwaway ``tempfile.mkdtemp()`` directory (never the run's real
    workspace) using the fixed, never-real :data:`_SELF_CHECK_BASE_URL`
    and :data:`_SELF_CHECK_MODEL_ID` -- never the run's real base URL or
    candidate model -- then re-verifies the exact on-disk integrity the
    later launch path itself requires
    (``i2_pi_config.verify_generated_config_integrity``), and explicitly
    evaluates §14.2's own invariants (required keys present, ``apiKey``
    uses exact ``$ENV`` interpolation, no ``!`` shell-command form, no
    ``maxTokens``) via :func:`~qualification.i2_pi_config.describe_generated_config`
    -- never merely trusted because the generator did not raise. This
    proves the generator machinery this run will depend on is sound BEFORE
    any credential is read. It does NOT, and cannot, prove anything about
    the run's own eventual real generated config, which does not exist yet
    at preflight time.

    **L1-FU2 nearby fix.** Cleanup now goes through the ACCEPTED
    qualification cleanup path
    (:func:`~qualification.i2_cleanup.scrub_generated_qualification_config`)
    rather than a raw ``shutil.rmtree`` of the whole throwaway parent
    directory -- the earlier raw delete bypassed
    :mod:`qualification.i2_issuance`'s own discard step, leaving a stale
    process-local issuance record behind even though the directory was
    gone. A cleanup that cannot be verified now FAILS this gate, rather
    than silently passing.
    """
    tmp_root = tempfile.mkdtemp(prefix="i2b-preflight-self-check-")
    generated: GeneratedQualificationConfig | None = None
    try:
        generated = write_qualification_pi_config(
            tmp_root, model_id=_SELF_CHECK_MODEL_ID, base_url=_SELF_CHECK_BASE_URL
        )
        verify_generated_config_integrity(
            config_dir=generated.config_dir,
            settings_path=generated.settings_path,
            models_path=generated.models_path,
            authority_token=generated.authority_token,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
        )
        description = describe_generated_config(generated)
        if description["api_key_resolution"] != "env_interpolation":
            raise QualificationPiConfigError(
                "config error: apiKey does not use exact $ENV interpolation"
            )
        if description["api_key_uses_shell_command_resolution"]:
            raise QualificationPiConfigError(
                "config error: apiKey uses a shell-command '!' resolution form"
            )
        if description["models_json_contains_max_tokens"]:
            raise QualificationPiConfigError(
                "config error: the generated models.json contains maxTokens"
            )
        if not description["settings_keys"] or not description["models_provider_ids"]:
            raise QualificationPiConfigError(
                "config error: the generated config is missing a required key"
            )
    except (
        QualificationPiConfigError,
        QualificationPiConfigCleanupError,
        CleanupAuthorityError,
    ):
        shutil.rmtree(tmp_root, ignore_errors=True)
        return PreflightGateResult(
            name="config_generator_self_check",
            passed=False,
            failure_code="VERIFICATION_FAILED",
        )

    try:
        cleanup_verified = scrub_generated_qualification_config(generated).scrub_verified
    except CleanupAuthorityError:
        cleanup_verified = False
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    if not cleanup_verified:
        return PreflightGateResult(
            name="config_generator_self_check",
            passed=False,
            failure_code="VERIFICATION_FAILED",
        )
    return PreflightGateResult(name="config_generator_self_check", passed=True)


def preflight_environment_forbidden_fragment_audit(*, ambient_environ: Any) -> PreflightGateResult:
    """REAL, credential-free, NAMES-ONLY structural check.

    ``ambient_environ`` is REQUIRED and is never defaulted to a real
    ``os.environ`` read inside this module -- the live entry point supplies
    it explicitly, mirroring :meth:`LiveCategoryBAdapters.read_connection`'s
    own injected-value discipline. No environment VALUE is ever read here,
    only ``ambient_environ``'s own key names, and no name is retained or
    echoed in the returned result.

    What this establishes: (1) AIDO's own reserved credential-carrier name
    (``i2_identity.CREDENTIAL_ENV_VAR_NAME``) does not itself match
    ``i2_environment.FORBIDDEN_NAME_FRAGMENTS`` and does not collide with
    ``i2_environment.WITHHELD_PROFILE_NAMES`` -- a structural coherence
    fact about AIDO's own policy, checked before this run relies on it;
    (2) ``ambient_environ`` is usable (iterable by name) at all.

    What this does NOT establish: nothing here audits the run's own
    eventual BUILT child environment for a forbidden-fragment leak -- that
    structural check already runs, independently, inside
    ``i2_environment.build_child_environment`` itself at the later
    CHILD_ENVIRONMENT gate, against a real generated config and secret
    context that do not exist yet at preflight time. A forbidden-fragment
    NAME merely being present somewhere in the ambient environment (common
    on a developer machine) is not itself disqualifying, because the
    builder never blindly copies ambient names.
    """
    try:
        tuple(ambient_environ)
    except TypeError:
        return PreflightGateResult(
            name="environment_forbidden_fragment_audit",
            passed=False,
            failure_code="CHECK_FAILED",
        )
    if any(fragment in CREDENTIAL_ENV_VAR_NAME.upper() for fragment in FORBIDDEN_NAME_FRAGMENTS):
        return PreflightGateResult(
            name="environment_forbidden_fragment_audit",
            passed=False,
            failure_code="FORBIDDEN_VALUE_DETECTED",
        )
    if CREDENTIAL_ENV_VAR_NAME in WITHHELD_PROFILE_NAMES:
        return PreflightGateResult(
            name="environment_forbidden_fragment_audit",
            passed=False,
            failure_code="FORBIDDEN_VALUE_DETECTED",
        )
    return PreflightGateResult(name="environment_forbidden_fragment_audit", passed=True)


#: Self-check-only stand-ins for :func:`preflight_child_environment_builder_self_check`.
#: Never the run's real ambient environment, node path, or credential.
_SELF_CHECK_AMBIENT_ENVIRON: dict[str, str] = {"SystemRoot": r"C:\i2b-self-check-windows"}
_SELF_CHECK_NODE_EXECUTABLE = r"C:\i2b-self-check-windows\i2b-self-check-node.exe"
_SELF_CHECK_API_KEY = "i2b-preflight-self-check-api-key-not-a-credential"


def preflight_child_environment_builder_self_check() -> PreflightGateResult:
    """I2A §14.3 -- REAL, credential-free self-test proving the I2 child-
    environment BUILDER's OWN output passes its own forbidden-fragment
    audit, with the one exact credential-carrier name excepted -- exercised
    against a throwaway self-check config/secret pair, never the run's real
    ambient environment or credential (mirrors
    :func:`preflight_config_generator_self_check`'s own self-check
    discipline). Reuses the REAL, unmodified
    ``i2_environment.build_child_environment`` and
    ``i2_environment.audit_withheld_names`` -- never a second, drifting
    audit implementation.
    """
    tmp_root = tempfile.mkdtemp(prefix="i2b-preflight-env-self-check-")
    generated: GeneratedQualificationConfig | None = None
    try:
        generated = write_qualification_pi_config(
            tmp_root, model_id=_SELF_CHECK_MODEL_ID, base_url=_SELF_CHECK_BASE_URL
        )
        secret_context = build_secret_context(
            base_url=_SELF_CHECK_BASE_URL,
            api_key=_SELF_CHECK_API_KEY,
            model_id=_SELF_CHECK_MODEL_ID,
        )
        launch_environment = build_child_environment(
            ambient_environ=_SELF_CHECK_AMBIENT_ENVIRON,
            node_executable=_SELF_CHECK_NODE_EXECUTABLE,
            generated_config=generated,
            secret_context=secret_context,
        )
        audit = audit_withheld_names(
            ambient_environ=_SELF_CHECK_AMBIENT_ENVIRON,
            built_environment=launch_environment.environment,
        )
        if audit["sensitive_names_forwarded_count"] != 0 or audit["profile_names_forwarded_to_child"]:
            raise EnvironmentPolicyError(
                "environment error: the self-check builder output failed its "
                "own forbidden-fragment audit"
            )
    except (
        QualificationPiConfigError,
        QualificationPiConfigCleanupError,
        CleanupAuthorityError,
        SecretContextError,
        InvalidBaseUrlError,
        EnvironmentPolicyError,
    ):
        shutil.rmtree(tmp_root, ignore_errors=True)
        return PreflightGateResult(
            name="child_environment_builder_self_check",
            passed=False,
            failure_code="VERIFICATION_FAILED",
        )

    try:
        cleanup_verified = (
            generated is not None
            and scrub_generated_qualification_config(generated).scrub_verified
        )
    except CleanupAuthorityError:
        cleanup_verified = False
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    if not cleanup_verified:
        return PreflightGateResult(
            name="child_environment_builder_self_check",
            passed=False,
            failure_code="VERIFICATION_FAILED",
        )
    return PreflightGateResult(name="child_environment_builder_self_check", passed=True)


def preflight_candidate_route_generator_symmetry() -> PreflightGateResult:
    """I2A §14.4 -- REAL, credential-free proof that Candidate A and
    Candidate B configs come from calling the SAME generator function
    (:func:`~qualification.i2_pi_config.write_qualification_pi_config`)
    twice with only ``model_id`` varying: the two generated documents are
    compared field-by-field and must agree on everything except the one
    model entry's ``id``.
    """
    tmp_root_a = tempfile.mkdtemp(prefix="i2b-preflight-symmetry-a-")
    tmp_root_b = tempfile.mkdtemp(prefix="i2b-preflight-symmetry-b-")
    generated_a: GeneratedQualificationConfig | None = None
    generated_b: GeneratedQualificationConfig | None = None

    def _cleanup() -> bool:
        ok = True
        for generated, tmp_root in ((generated_a, tmp_root_a), (generated_b, tmp_root_b)):
            if generated is not None:
                try:
                    ok = scrub_generated_qualification_config(generated).scrub_verified and ok
                except CleanupAuthorityError:
                    ok = False
            shutil.rmtree(tmp_root, ignore_errors=True)
        return ok

    try:
        generated_a = write_qualification_pi_config(
            tmp_root_a, model_id=_CANDIDATE_MODEL_IDS["A"], base_url=_SELF_CHECK_BASE_URL
        )
        generated_b = write_qualification_pi_config(
            tmp_root_b, model_id=_CANDIDATE_MODEL_IDS["B"], base_url=_SELF_CHECK_BASE_URL
        )
        settings_a = json.loads(Path(generated_a.settings_path).read_text(encoding="utf-8"))
        settings_b = json.loads(Path(generated_b.settings_path).read_text(encoding="utf-8"))
        if settings_a != settings_b:
            raise QualificationPiConfigError(
                "config error: candidate A/B settings.json documents disagree"
            )
        models_a = json.loads(Path(generated_a.models_path).read_text(encoding="utf-8"))
        models_b = json.loads(Path(generated_b.models_path).read_text(encoding="utf-8"))
        entries_a = models_a["providers"][generated_a.provider_id]["models"]
        entries_b = models_b["providers"][generated_b.provider_id]["models"]
        if len(entries_a) != 1 or len(entries_b) != 1:
            raise QualificationPiConfigError(
                "config error: a candidate config does not carry exactly one "
                "model entry"
            )
        stripped_a = {k: v for k, v in entries_a[0].items() if k != "id"}
        stripped_b = {k: v for k, v in entries_b[0].items() if k != "id"}
        if stripped_a != stripped_b:
            raise QualificationPiConfigError(
                "config error: candidate A/B model entries disagree on a "
                "field other than id"
            )
        provider_a = {
            k: v for k, v in models_a["providers"][generated_a.provider_id].items() if k != "models"
        }
        provider_b = {
            k: v for k, v in models_b["providers"][generated_b.provider_id].items() if k != "models"
        }
        if provider_a != provider_b:
            raise QualificationPiConfigError(
                "config error: candidate A/B provider documents disagree on a "
                "field other than the model list"
            )
        if (
            entries_a[0]["id"] != _CANDIDATE_MODEL_IDS["A"]
            or entries_b[0]["id"] != _CANDIDATE_MODEL_IDS["B"]
        ):
            raise QualificationPiConfigError(
                "config error: a candidate config's model id does not match "
                "the frozen pairing"
            )
    except (QualificationPiConfigError, QualificationPiConfigCleanupError, CleanupAuthorityError, KeyError):
        _cleanup()
        return PreflightGateResult(
            name="candidate_route_generator_symmetry",
            passed=False,
            failure_code="VERIFICATION_FAILED",
        )

    if not _cleanup():
        return PreflightGateResult(
            name="candidate_route_generator_symmetry",
            passed=False,
            failure_code="VERIFICATION_FAILED",
        )
    return PreflightGateResult(name="candidate_route_generator_symmetry", passed=True)


#: A fixed, synthetic, never-real identity used ONLY by
#: :func:`preflight_planned_cli_argv_shape` to exercise
#: ``ar2.launch.build_pi_argv`` -- never the run's real resolved identity.
_SELF_CHECK_RUNTIME_IDENTITY = RuntimeIdentity(
    node_executable=r"C:\i2b-self-check-windows\i2b-self-check-node.exe",
    pi_cli_js=r"C:\i2b-self-check-windows\i2b-self-check-pi\dist\cli.js",
    pi_package_root=r"C:\i2b-self-check-windows\i2b-self-check-pi",
    reported_version="0.0.0-preflight-self-check",
    launch_shape="node_direct",
)

#: A fixed, synthetic, never-real extension entry path used ONLY by
#: :func:`preflight_planned_cli_argv_shape`.
_SELF_CHECK_EXTENSION_ENTRY = r"C:\i2b-self-check-workspace\pi_extension\index.ts"


def preflight_planned_cli_argv_shape() -> PreflightGateResult:
    """I2A §14.5 -- REAL, no-process proof that the planned CLI argv for
    EACH candidate matches, by exact tuple equality, the already-accepted
    AR2 shape (``ar2.launch.build_pi_argv`` /
    ``experiments/pi_external_runtime_ar2/ar2/launch.py:120-162``) with
    only ``--provider``/``--model`` substituted -- and specifically that no
    ``--api-key`` flag is ever introduced. Calls the REAL, unmodified
    ``build_pi_argv`` against a fixed synthetic identity/extension-entry;
    never a process, never a credential.
    """
    try:
        for candidate, expected_model_id in _CANDIDATE_MODEL_IDS.items():
            descriptor = route_descriptor_for_candidate(candidate)
            if descriptor.model_id != expected_model_id:
                raise RouteDescriptorError(
                    "route descriptor error: candidate/model pairing disagreement"
                )
            argv = build_pi_argv(
                _SELF_CHECK_RUNTIME_IDENTITY,
                extension_entry=_SELF_CHECK_EXTENSION_ENTRY,
                tool_allowlist=TOOL_ALLOWLIST,
                provider=descriptor.provider_id,
                model=descriptor.model_id,
            )
            expected_argv = (
                _SELF_CHECK_RUNTIME_IDENTITY.node_executable,
                _SELF_CHECK_RUNTIME_IDENTITY.pi_cli_js,
                "--mode",
                "rpc",
                "--no-session",
                "--no-extensions",
                "--extension",
                _SELF_CHECK_EXTENSION_ENTRY,
                "--tools",
                ",".join(TOOL_ALLOWLIST),
                "--no-builtin-tools",
                "--no-skills",
                "--no-prompt-templates",
                "--no-themes",
                "--no-context-files",
                "--no-approve",
                "--offline",
                "--provider",
                descriptor.provider_id,
                "--model",
                descriptor.model_id,
            )
            if argv != expected_argv:
                raise LaunchIdentityError(
                    "launch error: the planned CLI argv shape disagrees with "
                    "the accepted AR2 shape"
                )
            if "--api-key" in argv:
                raise LaunchIdentityError(
                    "launch error: the planned CLI argv must never carry "
                    "--api-key"
                )
    except (RouteDescriptorError, LaunchIdentityError):
        return PreflightGateResult(
            name="planned_cli_argv_shape", passed=False, failure_code="SCHEMA_INVALID"
        )
    return PreflightGateResult(name="planned_cli_argv_shape", passed=True)


#: Fixed, never-real stand-in values for every field
#: ``ArtifactSafetyContext`` declares -- used ONLY by
#: :func:`preflight_artifact_safety_scrub_self_check` to prove the scrub
#: backstop actually refuses a record carrying any of them. Never the run's
#: own real credential, endpoint, broker binding, or workspace path.
_SELF_CHECK_SAFETY_STAND_IN_VALUES: dict[str, str] = {
    "endpoint_host": "i2b-preflight-self-check-endpoint.invalid",
    "api_key": "i2b-preflight-self-check-api-key-0001",
    "bearer_token": "i2b-preflight-self-check-bearer-0001",
    "broker_token": "i2b-preflight-self-check-broker-token-0001",
    "pipe_name": r"\\.\pipe\i2b-preflight-self-check-0001",
    "capability_id": "i2b-preflight-self-check-capability-0001",
    "workspace_absolute_path": r"C:\i2b-preflight-self-check-workspace",
}


def preflight_artifact_safety_scrub_self_check() -> PreflightGateResult:
    """I2A §14.6 -- REAL, credential-free proof that
    ``ArtifactSafetyContext``'s scrub backstop actually refuses a record
    containing any of ``endpoint_host``, ``api_key``, ``bearer_token``,
    ``broker_token``, ``pipe_name``, ``capability_id``, or
    ``workspace_absolute_path`` -- exercised with fixed, never-real
    synthetic stand-in values, and cross-checked against a clean payload so
    the result is not merely "always refuses".
    """
    safety = ArtifactSafetyContext(**_SELF_CHECK_SAFETY_STAND_IN_VALUES)
    dirty_payload = {
        f"probe_{name}": value for name, value in _SELF_CHECK_SAFETY_STAND_IN_VALUES.items()
    }
    dirty_check = qualification_scrub_check(dirty_payload, safety)
    clean_payload = {"probe": "nothing sensitive declared in this payload"}
    clean_check = qualification_scrub_check(clean_payload, safety)
    if dirty_check["clean"] is not False or clean_check["clean"] is not True:
        return PreflightGateResult(
            name="artifact_safety_scrub_self_check",
            passed=False,
            failure_code="VERIFICATION_FAILED",
        )
    return PreflightGateResult(name="artifact_safety_scrub_self_check", passed=True)


def preflight_config_generator_no_credential_literal_path() -> PreflightGateResult:
    """I2A §14.7 -- REAL, no-process proof that
    ``write_qualification_pi_config``'s own signature has NO code path
    capable of accepting or embedding a literal (non-``$ENV``) credential
    value: the function's parameter names are inspected directly, and none
    of them may name a value carrier at all -- only a directory, a model
    id, and a base URL.
    """
    parameters = tuple(inspect.signature(write_qualification_pi_config).parameters)
    forbidden_fragments = ("key", "token", "secret", "credential", "password")
    offending = [
        name for name in parameters if any(fragment in name.lower() for fragment in forbidden_fragments)
    ]
    if offending or set(parameters) != {"experiment_root", "model_id", "base_url"}:
        return PreflightGateResult(
            name="config_generator_no_credential_literal_path",
            passed=False,
            failure_code="SCHEMA_INVALID",
        )
    return PreflightGateResult(name="config_generator_no_credential_literal_path", passed=True)


def _build_inert_static_eligibility_domain(*, canonical_root: str) -> StaticEligibilityDomain:
    """A real, valid, but STRUCTURALLY POWERLESS capability. See module docstring."""
    return StaticEligibilityDomain(
        capability_id="i2b-cat-b-" + secrets.token_hex(8),
        canonical_root=canonical_root,
        root_class=ROOT_CLASS_DISPOSABLE_SYNTHETIC,
        operation_classes=OPERATION_CLASSES,
        manifest=(),
        read_eligible=frozenset(),
        write_eligible=frozenset(),
        protected_paths=frozenset(),
        verification_witness_paths=frozenset(),
        excluded=(),
        caps=CapDefinitions(),
        lifetime="one runtime process",
    )


def _rpc_response_reports_exact_success(response: Any) -> bool:
    """BLOCKER 5: project an RPC response's ``success`` field FAIL-CLOSED.

    Requires ``response`` to be a ``dict`` carrying ``success`` as EXACTLY
    ``True`` -- ``type(value) is bool`` first, then identity against the
    ``True`` singleton. A malformed stand-in (``"false"``, ``1``, ``0``,
    ``[]``, an object-like value, a missing key, or a non-dict response)
    is never interpreted by Python truthiness as a protocol boolean; every
    such shape reports ``False`` here.
    """
    if not isinstance(response, dict):
        return False
    success = response.get("success")
    return type(success) is bool and success is True


# -- internal, process-local session registries --------------------------------


@dataclass
class _LiveBrokerRecord:
    server: BrokerServer
    handler: BrokerRequestHandler
    run_id: str
    #: The EXACT BrokerSession object this adapter minted and handed back.
    #: A future ``launch_runtime`` call is required to present a request
    #: whose ``broker_session`` agrees with every authority-bearing field
    #: here -- never merely the same ``session_id`` (Blocker 4).
    session: BrokerSession


@dataclass
class _LiveRuntimeRecord:
    supervisor: PiRpcSupervisor
    run_id: str
    broker_session_id: str
    extension_dir: str
    extension_entry: str
    cached_get_commands_response: dict[str, Any] | None = field(default=None)


class LiveCategoryBAdapters:
    """One run's worth of live adapter methods for ``run_category_b_controller``.

    **One instance per run.** Every method below is meant to be handed
    DIRECTLY to ``run_category_b_controller``'s matching keyword parameter
    (``read_connection=adapters.read_connection``, etc.) -- this class is not
    a controller and does not sequence anything itself; it only remembers,
    across calls, the broker/runtime resources IT created, so a later call
    (``get_commands``, ``shutdown_runtime``, ...) can look up the exact
    object it minted rather than trusting whatever session the frozen
    controller hands back.
    """

    def __init__(
        self,
        *,
        environ_reader: Any,
        runtime_identity: RuntimeIdentity,
        experiment_id: str = QUALIFICATION_EXPERIMENT_ID,
        bounds: RunBounds | None = None,
    ) -> None:
        """``environ_reader`` and ``runtime_identity`` are REQUIRED, keyword-only.

        The SAME injected-reader discipline
        ``qualification.i2_credentials.read_connection_values`` already
        enforces: there is no default that silently reads ``os.environ``.
        The live entry point passes ``os.environ.get`` explicitly.

        ``runtime_identity`` is the ONE ``resolve_pi_identity()`` probe the
        live entry point resolves for this whole attempt, BEFORE the
        credential boundary. ``launch_runtime`` below consumes this exact
        object rather than re-resolving Pi's identity a second time at
        launch -- one Category-B attempt performs exactly one version
        probe, never two (L1 brief, "SINGLE RUNTIME IDENTITY BINDING"). It
        is additionally bound, mechanically, to this machine's own trusted
        resolver path (L1-FU2 BLOCKER 1, RuntimeIdentity variant) -- a
        same-type object carrying substituted executable paths is refused
        here, at construction, never merely type-checked.

        **There is no ``ar2_extension_source_dir`` parameter (L1-FU2
        BLOCKER 1).** The disposable extension's source is derived
        deterministically from this package's own reused ``ar2`` import and
        mechanically verified against a fixed, reviewed digest before this
        object exists -- no caller of this constructor can express a
        substitute.
        """
        if type(runtime_identity) is not RuntimeIdentity:
            raise LiveAdapterError(
                "LiveCategoryBAdapters requires a single, already-resolved "
                "RuntimeIdentity"
            )
        _require_runtime_identity_matches_trusted_resolution(runtime_identity)
        self._environ_reader = environ_reader
        self._ar2_extension_source_dir = _require_authorized_extension_source()
        self._runtime_identity = runtime_identity
        self._experiment_id = experiment_id
        self._bounds = bounds or _DEFAULT_BOUNDS
        self._brokers: dict[str, _LiveBrokerRecord] = {}
        self._runtimes: dict[str, _LiveRuntimeRecord] = {}

    # -- credential boundary -------------------------------------------------

    def read_connection(self) -> ConnectionValues:
        """The ONLY credential read in this module. Reused, unmodified."""
        return read_connection_values(self._environ_reader)

    # -- broker authority ------------------------------------------------------

    def create_broker(self, request: BrokerCreationRequest) -> BrokerCreationObservation:
        sed = _build_inert_static_eligibility_domain(
            canonical_root=request.workspace.workspace_root
        )
        run_state = RunState(caps=sed.caps)
        binding = BrokerBinding.mint(sed.capability_id)
        handler = BrokerRequestHandler(
            sed=sed, run_state=run_state, binding=binding, diagnostics=BrokerDiagnostics()
        )
        server = BrokerServer(handler)
        try:
            server.start()
        except Exception:  # noqa: BLE001 - bounded; see _retain_and_close_partial_broker
            return self._retain_and_close_partial_broker(server)

        reached_ready = server.state == STATE_READY
        session = BrokerSession(
            run_id=request.run_id,
            session_id="i2b-brk-" + secrets.token_hex(12),
            pipe_name=server.pipe_name,
            capability_id=binding.capability_id,
            broker_token=binding.token,
            reached_ready=reached_ready,
        )
        self._brokers[session.session_id] = _LiveBrokerRecord(
            server=server, handler=handler, run_id=request.run_id, session=session
        )
        return BrokerCreationObservation(
            session=session, start_attempted=True, resource_created=True
        )

    def _retain_and_close_partial_broker(self, server: BrokerServer) -> BrokerCreationObservation:
        """A ``BrokerServer.start()`` failure. See L1 BLOCKER 1.

        The frozen ``BrokerServer``'s ``state`` reads ``STATE_CREATED`` for
        EVERY pre-READY failure point ``start()`` can raise from -- the
        worker only transitions to ``STATE_READY`` deep inside
        ``_serve_body``, after issuing its first overlapped
        ``ConnectNamedPipe``, which is strictly later than every exception
        ``start()`` itself can propagate (a pipe-creation failure, a
        shutdown-event-creation failure, a thread-construction/start
        failure, or the worker never signalling READY within its
        deadline). ``server.state == STATE_CREATED`` therefore CANNOT
        mechanically distinguish "nothing was created" from "a pipe (and
        possibly the shutdown event) was created but the worker thread was
        never started or never reached READY" -- there is no other public,
        supported signal on this class that can either (reaching into
        ``server._pipe_handle`` or ``server._thread`` would be exactly the
        private-internals workaround the L1 brief forbids).

        So this method NEVER infers ``resource_created=False`` from an
        exception here: it conservatively assumes a resource MAY have been
        created, and calls the ONE safe, always-callable, supported cleanup
        primitive the frozen class exposes for every such state --
        ``BrokerServer.shutdown()`` -- exactly once, guarded so a cleanup
        exception can never erase this primary start failure (BLOCKER 3).

        ``shutdown()`` itself is fully effective when the worker thread WAS
        started (a READY-deadline timeout): its own ``_thread is None``
        early-return branch is never taken, so the full teardown ladder
        runs and can genuinely reach ``STATE_CLOSED``. It is only
        INEFFECTIVE -- never unsafe, never raising -- for the narrower
        pre-thread-start failures, where its ``_thread is None`` branch
        returns immediately without closing a pipe handle that may exist;
        that case is reported exactly as designed: ``cleanup_attempted=
        True, reached_closed=False`` (cleanup was attempted; the
        postcondition is honestly unverified), never as a fabricated
        success and never as an erased primary failure.
        """
        try:
            lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)
            reached_closed = lifecycle["state_reached"] == STATE_CLOSED
        except Exception:  # noqa: BLE001 - the cleanup attempt itself must never escape
            reached_closed = False
        return BrokerCreationObservation(
            session=None,
            start_attempted=True,
            resource_created=True,
            cleanup_attempted=True,
            reached_closed=reached_closed,
        )

    def _require_exact_broker_session(self, broker_session: BrokerSession) -> _LiveBrokerRecord:
        """BLOCKER 4: refuse any broker-session-consuming call -- launch OR
        shutdown -- for a broker this instance did not itself mint, or whose
        authority-bearing fields disagree with what was minted -- a
        same-id object whose pipe/capability/token was substituted must
        refuse, never merely a session-id match.
        """
        record = self._brokers.get(broker_session.session_id)
        if record is None or record.run_id != broker_session.run_id:
            raise LiveAdapterError(
                "broker session refused: this session was not created by "
                "this adapter instance"
            )
        minted = record.session
        if (
            minted.run_id != broker_session.run_id
            or minted.session_id != broker_session.session_id
            or minted.pipe_name != broker_session.pipe_name
            or minted.capability_id != broker_session.capability_id
            or minted.broker_token != broker_session.broker_token
            or minted.reached_ready != broker_session.reached_ready
        ):
            raise LiveAdapterError(
                "broker session refused: the broker session does not match "
                "the exact authority this adapter instance minted for this run"
            )
        return record

    def shutdown_broker(self, session: BrokerSession) -> BrokerShutdownObservation:
        """BLOCKER 4 (L1-FU2): consume the SAME exact minted-authority check
        ``launch_runtime`` uses, not merely a ``session_id``/``run_id``
        lookup. A same-id session whose ``pipe_name``/``capability_id``/
        ``broker_token``/``reached_ready`` was substituted must trigger
        ZERO shutdown calls against the real registered server.
        """
        record = self._require_exact_broker_session(session)
        lifecycle = record.server.shutdown(TRIGGER_AIDO_TEARDOWN)
        return BrokerShutdownObservation(
            session_id=session.session_id,
            reached_closed=lifecycle["state_reached"] == STATE_CLOSED,
        )

    # -- runtime authority -------------------------------------------------

    def launch_runtime(self, request: RuntimeLaunchRequest) -> RuntimeLaunchObservation:
        # -- 0. BLOCKER 4: refuse BEFORE writing any extension file, ---------
        # -- building argv, constructing a supervisor, or launching any -----
        # -- process, unless request.broker_session is the EXACT broker -----
        # -- authority THIS adapter instance minted for this run. -----------
        self._require_exact_broker_session(request.broker_session)

        # -- 1. Pi's version. The ONE probe for this whole attempt, already -
        # -- resolved by the live entry point before the credential --------
        # -- boundary and handed to this instance at construction -- never -
        # -- re-resolved here (L1 brief, "SINGLE RUNTIME IDENTITY BINDING").-
        identity = self._runtime_identity

        # -- 2. write the disposable extension (the broker binding carrier)-
        extension: GeneratedExtension = write_disposable_extension(
            request.workspace.experiment_root,
            source_dir=self._ar2_extension_source_dir,
            experiment_id=self._experiment_id,
            pipe_name=request.broker_session.pipe_name,
            capability_id=request.broker_session.capability_id,
            token=request.broker_session.broker_token,
        )

        # -- 3. build argv and the supervisor. No process exists yet. ------
        argv = build_pi_argv(
            identity,
            extension_entry=extension.extension_entry,
            tool_allowlist=TOOL_ALLOWLIST,
            provider=request.provider_id,
            model=request.model_id,
        )
        supervisor = PiRpcSupervisor(
            argv=argv,
            cwd=request.workspace.workspace_root,
            environment=request.launch_environment.as_launch_snapshot(),
            bounds=self._bounds,
        )

        # -- 4. launch. BLOCKER 2: ``PiRpcSupervisor.launch()`` assigns -----
        # -- ``self.process = subprocess.Popen(...)`` FIRST and only THEN --
        # -- constructs/starts its stdout/stderr reader threads -- only ----
        # -- ``Popen``'s own ``OSError`` is wrapped locally, so an --------
        # -- exception from reader construction/start can escape ``launch``
        # -- with a REAL child already assigned to ``supervisor.process``. -
        # -- Distinguish mechanically, using ONLY that stable PUBLIC -------
        # -- attribute (never exception class/text, per the L1 brief): if -
        # -- ``supervisor.process`` is still ``None``, ``Popen`` itself ----
        # -- never succeeded and nothing exists to clean up, so the -------
        # -- original exception is re-raised unchanged; otherwise a real --
        # -- child exists and the creator retains ownership. ---------------
        try:
            supervisor.launch()
        except Exception:  # noqa: BLE001 - see above; re-raised below when nothing exists
            if supervisor.process is None:
                raise
            return self._retain_and_close_partial_runtime(
                supervisor=supervisor, extension_dir=extension.extension_dir
            )

        # -- 5. the ONE real correlation probe this run ever sends. See ----
        # -- the module docstring for why this is shared with the separate-
        # -- get_commands adapter rather than sent twice. ------------------
        try:
            supervisor.send_command({"id": "h1", "type": "get_commands"})
            wait_outcome, response = supervisor.await_response(
                "h1", timeout_seconds=self._bounds.startup_deadline_seconds
            )
        except Exception:  # noqa: BLE001 - a real process now exists; see below
            return self._retain_and_close_partial_runtime(
                supervisor=supervisor, extension_dir=extension.extension_dir
            )

        stdout_state = supervisor.stdout_state()
        lf_jsonl_correlation_succeeded = wait_outcome == RUNTIME_RESPONSE_RECEIVED
        # L1-FU2 (raw supervisor outcome domain): a POSITIVE allowlist of the
        # exact outcomes ``await_response`` can genuinely produce -- never a
        # negative check against the two known-bad constants. An
        # unknown/malformed outcome (which should never occur, but must never
        # be trusted merely because it isn't one of those two) fails closed.
        launch_shape_valid = wait_outcome in _RECOGNIZED_AWAIT_RESPONSE_OUTCOMES
        # BLOCKER 5: fail closed on a malformed/untyped protocol_violation
        # flag rather than applying bare truthiness to it -- a value that
        # is not exactly a bool is treated as a violation, never silently
        # coerced.
        raw_violation = stdout_state.get("protocol_violation")
        protocol_violation_observed = type(raw_violation) is not bool or raw_violation is True
        required_flags_accepted = (
            launch_shape_valid
            and lf_jsonl_correlation_succeeded
            and not protocol_violation_observed
        )

        try:
            run_id = request.run_id
            broker_session_id = request.broker_session.session_id
            session = RuntimeSession(
                run_id=run_id,
                broker_session_id=broker_session_id,
                runtime_session_id="i2b-rt-" + secrets.token_hex(12),
            )
        except ObservationError:
            return self._retain_and_close_partial_runtime(
                supervisor=supervisor, extension_dir=extension.extension_dir
            )

        self._runtimes[session.runtime_session_id] = _LiveRuntimeRecord(
            supervisor=supervisor,
            run_id=run_id,
            broker_session_id=broker_session_id,
            extension_dir=extension.extension_dir,
            extension_entry=extension.extension_entry,
            cached_get_commands_response=response if lf_jsonl_correlation_succeeded else None,
        )
        return RuntimeLaunchObservation(
            session=session,
            launch_shape_valid=launch_shape_valid,
            required_flags_accepted=required_flags_accepted,
            lf_jsonl_correlation_succeeded=lf_jsonl_correlation_succeeded,
            observed_pi_version=identity.reported_version,
            resource_created=True,
        )

    def _retain_and_close_partial_runtime(
        self, *, supervisor: PiRpcSupervisor, extension_dir: str
    ) -> RuntimeLaunchObservation:
        """A real process exists but no trustworthy session can be formed.

        Creator-retained ownership (FU3 Sec. 9.3): exactly one bounded
        self-close, the observed postcondition reported truthfully, and NO
        session handed to the controller. ``extension_dir`` is accepted only
        to keep the call site symmetric with ``o1.handshake``'s own pattern;
        this module does not scrub it here (see the module docstring --
        scrubbing/removal of the disposable tree is the live entry point's
        job, run unconditionally after every outcome).
        """
        del extension_dir
        try:
            termination = supervisor.shutdown()
            exit_observed = termination.get("exit_status_observed") is not None
        except Exception:  # noqa: BLE001 - BLOCKER 3: the cleanup attempt must never
            # erase the primary launch/correlation failure that brought us here.
            exit_observed = False
        return RuntimeLaunchObservation(
            session=None,
            launch_shape_valid=False,
            required_flags_accepted=False,
            lf_jsonl_correlation_succeeded=False,
            observed_pi_version=None,
            resource_created=True,
            cleanup_attempted=True,
            direct_child_reported_exit=exit_observed,
        )

    def _require_runtime_record(self, session: RuntimeSession) -> _LiveRuntimeRecord:
        record = self._runtimes.get(session.runtime_session_id)
        if (
            record is None
            or record.run_id != session.run_id
            or record.broker_session_id != session.broker_session_id
        ):
            # Defense in depth beyond the frozen controller's own foreign-
            # session refusal: this adapter never acts on a session it did
            # not itself mint and register.
            raise LiveAdapterError(
                "runtime adapter call refused: this session was not created by "
                "this adapter instance"
            )
        return record

    def get_commands(self, session: RuntimeSession) -> GetCommandsObservation:
        """Re-project the ONE cached real ``get_commands`` response. No new RPC."""
        record = self._require_runtime_record(session)
        response = record.cached_get_commands_response
        call_succeeded = _rpc_response_reports_exact_success(response)
        data = response.get("data") if call_succeeded else None
        response_shape_understood = call_succeeded and isinstance(data, dict) and isinstance(
            data.get("commands"), list
        )
        if not response_shape_understood:
            return GetCommandsObservation(
                runtime_session_id=session.runtime_session_id,
                call_succeeded=call_succeeded,
                response_shape_understood=False,
            )
        raw_commands = data["commands"]
        # BLOCKER 5: project EVERY reported entry, preserving multiplicity.
        # A malformed entry is never silently filtered out -- the frozen
        # command-namespace/H1 machinery must either see every entry or see
        # none; ``observed_command_from_reported_entry`` raises
        # ``ObservationError`` for any entry that is not a well-formed
        # object, and this fails the WHOLE response closed rather than
        # quietly reporting a smaller, "clean" command list.
        try:
            commands = tuple(
                observed_command_from_reported_entry(entry) for entry in raw_commands
            )
        except ObservationError:
            return GetCommandsObservation(
                runtime_session_id=session.runtime_session_id,
                call_succeeded=True,
                response_shape_understood=False,
            )
        evaluation = evaluate_extension_identity(
            list(raw_commands), extension_entry=record.extension_entry
        )
        h1 = h1_components_from_frozen_evaluation(evaluation)
        return GetCommandsObservation(
            runtime_session_id=session.runtime_session_id,
            call_succeeded=True,
            response_shape_understood=True,
            commands=commands,
            **h1,
        )

    def get_state(self, session: RuntimeSession) -> GetStateObservation:
        """The ONE real, fresh ``get_state`` round trip for this run."""
        record = self._require_runtime_record(session)
        supervisor = record.supervisor
        supervisor.send_command({"id": "h2", "type": "get_state"})
        outcome, response = supervisor.await_response(
            "h2", timeout_seconds=self._bounds.startup_deadline_seconds
        )
        # BLOCKER 5 ("GET_STATE RESPONSE OUTCOME"): a response body is
        # usable ONLY when the frozen supervisor reports the exact
        # successful wait outcome. A contradictory pair -- e.g. a deadline
        # expiry alongside a success-looking body -- must never produce a
        # successful observation, so the wait outcome gates the response
        # BEFORE the response's own ``success`` field is even consulted.
        call_succeeded = outcome == RUNTIME_RESPONSE_RECEIVED and _rpc_response_reports_exact_success(
            response
        )
        data = response.get("data") if call_succeeded else None
        model = data.get("model") if isinstance(data, dict) else None
        response_shape_understood = call_succeeded and isinstance(model, dict)
        if not response_shape_understood:
            return GetStateObservation(
                runtime_session_id=session.runtime_session_id,
                call_succeeded=call_succeeded,
                response_shape_understood=False,
            )
        reported_provider = model.get("provider")
        reported_model = model.get("id")
        return GetStateObservation(
            runtime_session_id=session.runtime_session_id,
            call_succeeded=True,
            response_shape_understood=True,
            reported_provider=reported_provider if isinstance(reported_provider, str) else None,
            reported_model=reported_model if isinstance(reported_model, str) else None,
        )

    def observe_protocol(self, session: RuntimeSession) -> ProtocolObservation:
        """The narrowest real observation: two booleans, nothing raw retained.

        BLOCKER 5: neither boolean is derived by applying bare Python
        truthiness to untrusted supervisor-reported state. A
        ``protocol_violation`` value that is not exactly a ``bool``, or an
        ``extension_errors`` collection that is not exactly a ``list``,
        fails CLOSED -- treated as an observed violation/error -- rather
        than being coerced.
        """
        record = self._require_runtime_record(session)
        stdout_state = record.supervisor.stdout_state()
        raw_violation = stdout_state.get("protocol_violation")
        protocol_violation_observed = type(raw_violation) is not bool or raw_violation is True
        raw_errors = record.supervisor.activity.extension_errors
        extension_error_observed = type(raw_errors) is not list or len(raw_errors) > 0
        return ProtocolObservation(
            runtime_session_id=session.runtime_session_id,
            protocol_violation_observed=protocol_violation_observed,
            extension_error_observed=extension_error_observed,
        )

    def shutdown_runtime(self, session: RuntimeSession) -> RuntimeShutdownObservation:
        record = self._require_runtime_record(session)
        termination = record.supervisor.shutdown()
        return RuntimeShutdownObservation(
            runtime_session_id=session.runtime_session_id,
            shutdown_call_returned=True,
            orchestrator_direct_child_reported_exit=termination.get("exit_status_observed")
            is not None,
        )


#: Passed DIRECTLY to ``run_category_b_controller``'s ``route_checker``
#: parameter. Its call shape (``checker(base_url, model_id=...)`` returning
#: an object with ``.reachable``/``.configured_model_served``) already
#: matches what ``qualification.i2_route.run_offline_route_check`` expects
#: exactly -- no wrapper is needed or added.
route_checker = check_route_serves_model
