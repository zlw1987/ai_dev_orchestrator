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
                           TRIGGER_AIDO_TEARDOWN, and (5F3B-I2B-L1-D1)
                           BrokerServer.pipe_resource_created -- the public,
                           monotonic partial-start fact this module's
                           broker-start failure path reads instead of
                           guessing conservatively
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

**``ar2.route_check`` is deliberately NOT imported here (5F3B-I2B-L1-LF2).**
It was, until Candidate-A's second live attempt proved the assumption behind
that reuse wrong. AR2's ``check_route_serves_model`` sends no
``Authorization`` header and accepts no credential parameter, so on a
credential-bearing route its single ``configured_model_served=False`` cannot
distinguish an auth rejection from a genuinely absent model. The live route
checker is now :class:`AuthenticatedB300RouteObserver`, built by
:func:`build_authenticated_route_checker` and bound to THIS run's consumed
connection values. The import is gone rather than merely unused, so the
unauthenticated checker cannot be reintroduced into live wiring by accident;
an offline test asserts this module has no reference to it. AR2's own module
stays frozen and unmodified for AR2.

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

**Corrected by 5F3B-LIVE1-C1, and stated rather than glossed.** The two
paragraphs above remain exactly true of the ORDINARY Category-B path -- the
one every caller of this module's plain constructor reaches, and the one
Candidate A / Candidate B were qualified under -- and the inert domain
remains this class's byte-identical default. They are no longer true of the
package as a whole: :mod:`qualification.i2b_workspace` now owns a narrow
semantic issuance boundary that DOES call the frozen, unmodified
``ar2.capability.mint_capability`` (and ``ar2.observation.observe_repository``
to derive the manifest) for a semantic task, and
:func:`build_semantic_task_live_adapters` below is the one construction path
through which ``create_broker`` consumes it. This module still imports
neither: it imports the opaque grant type and the issuance function, and it
still exposes no authority object, no domain parameter, and no capability
accessor. The "second unrelated disposable root" objection is unchanged and
still refused -- the issuance consumes the run's OWN mint record, never a
fresh one.

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
``lf_jsonl_correlation_succeeded`` (and, with the separate argv check, the
LF1-corrected ``required_flags_accepted``), and CACHES
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

5F3B-I2B-L1-LF1 -- required-flag observation vs. protocol integrity
--------------------------------------------------------------------

The first (and only) live Candidate-A Category-B attempt refused at
``required_launch_flags`` with ``REQUIRED_LAUNCH_FLAGS_REJECTED`` while
recording ``rpc_launch_shape_valid=True`` and
``lf_jsonl_correlation_succeeded=True``. Independent review found the frozen
controller had behaved exactly as designed -- it mapped a FALSE adapter fact
to that failure code -- and that the DEFECT was in this module's producer of
that fact.

Two separate defects were found here, both corrected below and both proved
offline:

1. ``_protocol_violation_observed`` -- the projection of
   ``PiRpcSupervisor.stdout_state()["protocol_violation"]`` asserted a
   ``bool`` contract, but the frozen AR2 value is ``str | None``. The old
   expression ``type(raw) is not bool or raw is True`` was therefore
   UNSATISFIABLE: ``None`` (no violation) reported a violation, so EVERY
   real launch reported one. The offline suite missed it because its
   supervisor double published a ``bool``.

2. ``required_flags_accepted`` was computed as ``launch_shape_valid and
   lf_jsonl_correlation_succeeded and not protocol_violation_observed``,
   which is not the frozen fact. Frozen I2A section 15 item 3 and
   ``RuntimeLaunchObservation.required_flags_accepted`` both define it as
   "no 'unknown flag' startup rejection", and ``protocol_integrity`` is a
   SEPARATE, later gate. The same bit must not serve two gates.

Together these made the two gates non-independent AND made the second one
unconditionally false. The corrected producer, its three-part proof chain
against the installed Pi CLI source, and the bounded declared-code launch
diagnostic added to diagnose a future zero-prompt refusal all live beside
:data:`_RECOGNIZED_AWAIT_RESPONSE_OUTCOMES` below.

5F3B-I2B-L1-LF1-FU1 -- required flags and LF correlation are INDEPENDENT
--------------------------------------------------------------------------

LF1 left one half of the coupling in place. Its producer computed
``required_flags_accepted = argv_options_source_established and
lf_jsonl_correlation_succeeded``, whose positive direction is sound (a
correlated RPC response can only come from inside ``runRpcMode``, which both
unknown-option exits are strictly earlier than) but whose reverse direction is
not: **no correlated response does not imply an unknown CLI flag was
rejected**. Because the frozen controller evaluates ``rpc_launch_shape``,
then ``required_launch_flags``, then ``lf_jsonl_correlation``, EVERY
correlation failure -- a deadline, a launch-window protocol violation, an
output cap, an event cap, a read error, and a generic early exit alike -- was
attributed FIRST as ``REQUIRED_LAUNCH_FLAGS_REJECTED``, a cause none of them
mechanically establishes.

FU1 replaces that single expression with a THREE-state classification
(:func:`_classify_required_flag_evidence`): ACCEPTED, from LF1's unchanged
positive proof; REJECTED, only from a bounded startup diagnostic that
specifically observes Pi rejecting an option present in AIDO's own argv; and
INDETERMINATE for everything else. Only the two definite states may reach the
frozen ``bool``. An INDETERMINATE launch fails earlier, at this module's own
runtime-launch boundary, through the existing creator-retained cleanup
contract -- so the frozen controller reports the honest
``RUNTIME_LAUNCH_FAILED`` and leaves ``required_launch_flags`` NOT_REACHED,
rather than being told a rejection occurred. Neither the frozen
``RuntimeLaunchObservation`` nor the frozen controller gained a third state;
the three states are visible only in this module and in its own L1-level
bounded launch diagnostic.

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

Runtime-identity provenance (5F3B-I2B-L1-FU3 BLOCKER 2)
--------------------------------------------------------

The ``RuntimeIdentity`` a live attempt runs on is ISSUED by this module's
own :func:`resolve_pi_identity` -- the same trusted operation that performs
the one provenance-only ``node cli.js --version`` probe -- and handed to
:class:`LiveCategoryBAdapters` as an opaque :class:`IssuedRuntimeIdentity`
that a caller cannot construct and cannot populate. A freely-built
``RuntimeIdentity``, even one carrying every trusted path, is refused at
construction, so ``RuntimeLaunchObservation.observed_pi_version`` can only
ever be a version THIS process observed. The observed version remains
provenance only -- it is never compared, pinned, or gated on, here or
anywhere else in this package.

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

5F3B-I2B-L1-LF1-FU1 added exactly ONE place that inspects raw child stderr:
:func:`_unknown_option_rejection_established`, through the existing PUBLIC
``PiRpcSupervisor.stderr_snapshot()`` surface. It is reached only when the
positive flag-acceptance proof did not hold, it scans the bounded text tail
TRANSIENTLY, and it reduces everything it saw to one ``bool`` before
returning. No stderr line, no diagnostic message, no option name and no byte
count survives that call: what is retained is one declared literal from
:data:`REQUIRED_FLAG_STATES`. Raw stderr never reaches a
``RuntimeLaunchObservation``, a ``CategoryBEvidence``, the launch diagnostic,
a result JSON, or any exception text.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
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
from ar2.supervisor import (
    RUNTIME_DEADLINE_EXPIRED,
    RUNTIME_EVENT_CAP_EXCEEDED,
    RUNTIME_EXITED_EARLY,
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
from .i2_b300_route_observation import (
    ROUTE_AUTHORITY_REFUSED,
    ROUTE_DIAGNOSTIC_CODES,
    ROUTE_NOT_OBSERVED,
    B300RouteObservation,
    observe_b300_route_serves_model,
)
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
from .i2b_workspace import (
    QUALIFICATION_EXPERIMENT_ID,
    SemanticCapabilityGrant,
    WorkspaceAuthorityError,
    issue_semantic_broker_capability,
)

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
#:
#: **5F3B-I2B-L1-LF1 added ``RUNTIME_EXITED_EARLY``.** Its absence was itself
#: a misattribution: ``PiRpcSupervisor._wait`` genuinely returns it whenever
#: the direct child terminated before the awaited response arrived. With it
#: excluded, such a launch made ``launch_shape_valid`` False, so the frozen
#: controller failed the EARLIER ``rpc_launch_shape`` gate -- though the
#: Node-direct ``--mode rpc`` launch shape had in fact been constructed and
#: launched correctly, and what had not been established belongs to a LATER
#: gate.
#:
#: **5F3B-I2B-L1-LF1-FU1 corrected this entry's own prose.** An unknown-CLI-
#: flag startup rejection is ONE source-supported CAUSE of
#: ``RUNTIME_EXITED_EARLY`` -- ``dist/main.js`` reports the diagnostic on
#: stderr and calls ``process.exit(1)`` before ``runRpcMode`` is ever entered
#: -- but ``RUNTIME_EXITED_EARLY`` does NOT itself prove one. Any other
#: pre-RPC child exit produces the identical outcome constant. Nothing in
#: this module branches on ``RUNTIME_EXITED_EARLY`` to establish flag
#: rejection; see :func:`_classify_required_flag_evidence`, which reads no
#: supervisor outcome constant at all.
#:
#: This tuple is now the exact, complete reachable return domain of
#: ``PiRpcSupervisor._wait``. ``RUNTIME_SETTLED`` (only ``await_settled``
#: maps to it) and ``RUNTIME_LAUNCH_FAILED`` (only ``launch()`` raises it)
#: are deliberately still absent, because ``await_response`` cannot produce
#: them.
_RECOGNIZED_AWAIT_RESPONSE_OUTCOMES = (
    RUNTIME_RESPONSE_RECEIVED,
    RUNTIME_DEADLINE_EXPIRED,
    RUNTIME_EXITED_EARLY,
    RUNTIME_PROTOCOL_VIOLATION,
    RUNTIME_OUTPUT_CAP_EXCEEDED,
    RUNTIME_EVENT_CAP_EXCEEDED,
    RUNTIME_READ_ERROR,
)


# -- 5F3B-I2B-L1-LF1: the required-CLI-flag OBSERVATION -----------------------
#
# Frozen I2A section 15 item 3, and the frozen
# ``RuntimeLaunchObservation.required_flags_accepted`` docstring, define this
# fact identically and narrowly:
#
#     required flags accepted  =  no "unknown flag" startup rejection
#
# It is NOT "no protocol violation" -- that is a separate, later, frozen gate
# (``protocol_integrity``), fed by the separate ``ProtocolObservation``. The
# two must never be served by the same bit under two gate names.
#
# THE PROOF CHAIN, stated exactly, in three mechanical parts:
#
#   1. THE EXACT ARGV AIDO CONSTRUCTED. Every option token in the argv the
#      frozen, unmodified ``ar2.launch.build_pi_argv`` produced is a member
#      of the source-established option set below. This half is checked
#      against AIDO'S OWN argv, before any runtime behaviour is consulted,
#      and it fails closed for any token whose recognition was never
#      source-established -- so a future argv change cannot ride silently on
#      the runtime-behaviour half.
#
#   2. PI'S CLI PARSER BEHAVIOUR, established from the CURRENT installed
#      package source by OFFLINE inspection (no launch, no version gate):
#
#        - ``dist/cli/args.js`` ``parseArgs``: every long option below has
#          its own explicit ``else if`` branch. An option matching no branch
#          falls through to the ``arg.startsWith("--")`` catch-all and is
#          recorded in ``result.unknownFlags``; a single-dash token matching
#          no branch pushes an ``{type: "error"}`` entry into
#          ``result.diagnostics``.
#        - ``dist/core/agent-session-services.js``
#          ``applyExtensionFlagValues``: any ``unknownFlags`` name not
#          registered by a loaded extension becomes an
#          ``{type: "error", message: "Unknown option: --<name>"}``
#          diagnostic in the runtime's diagnostics.
#        - ``dist/main.js``: a ``parseArgs`` error diagnostic is printed and
#          ``process.exit(1)`` runs immediately after parsing; a runtime
#          error diagnostic sets ``hasRuntimeErrors``, is reported through
#          ``console.error`` (STDERR, never stdout) and also calls
#          ``process.exit(1)``. BOTH exits are strictly BEFORE the
#          ``if (appMode === "rpc") { ... await runRpcMode(runtime); }``
#          block, so Pi cannot read, parse or answer a single JSONL RPC
#          command when any flag was rejected as unknown.
#
#   3. THE EXACT OBSERVED RUNTIME BEHAVIOUR. AIDO wrote its one
#      ``{"id": "h1", "type": "get_commands"}`` frame to the child's stdin
#      and the frozen supervisor returned ``RUNTIME_RESPONSE_RECEIVED``
#      correlated to id ``h1`` -- i.e. ``runRpcMode`` ran, consumed the
#      command and wrote a correlated response.
#
#   => No "unknown flag" startup rejection occurred.
#
# This is the same evidence shape frozen AR2/O1 already accepted for its own
# ``required_launch_flags_accepted`` check (``run_o1.py``: the argv from
# ``build_pi_argv`` was accepted because the process reached H1/H2 without an
# early exit), and O1 likewise kept ``no_protocol_violation_during_handshake``
# as a SEPARATE fact. Nothing here compares a Pi version: the version stays
# provenance only, and no exact-version authorization gate is introduced.

#: Long options AIDO's argv may contain, each with its own explicit
#: recognizing branch in the installed Pi ``dist/cli/args.js`` ``parseArgs``.
#: Split by whether ``parseArgs`` consumes a following value token, so this
#: module can walk AIDO's own argv the way Pi's parser does. This is a
#: recorded fact about AIDO's OWN argv vocabulary -- not an authorization
#: gate, not a version pin, and never applied to a runtime-reported value.
_PI_SOURCE_ESTABLISHED_LONG_OPTIONS_WITH_VALUE: frozenset[str] = frozenset(
    {"--mode", "--extension", "--tools", "--provider", "--model"}
)
_PI_SOURCE_ESTABLISHED_LONG_OPTIONS_WITHOUT_VALUE: frozenset[str] = frozenset(
    {
        "--no-session",
        "--no-extensions",
        "--no-builtin-tools",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--no-approve",
        "--offline",
    }
)
_PI_SOURCE_ESTABLISHED_LONG_OPTIONS: frozenset[str] = (
    _PI_SOURCE_ESTABLISHED_LONG_OPTIONS_WITH_VALUE
    | _PI_SOURCE_ESTABLISHED_LONG_OPTIONS_WITHOUT_VALUE
)


def _argv_options_are_source_established(argv: tuple[str, ...]) -> bool:
    """Whether every option token in AIDO'S OWN ``argv`` is source-established.

    ``argv[0]``/``argv[1]`` are the two pinned program paths (the Node
    executable and Pi's ``dist/cli.js``) and are skipped. The remainder is
    walked the way Pi's own ``parseArgs`` walks it: a value-taking option
    consumes the following token, a valueless option consumes nothing, and
    anything else -- an unrecognized option token, a value-taking option with
    no value left, or an unexpected positional (AIDO's argv contains none) --
    fails CLOSED.

    This launches nothing and retains nothing: it returns one bool, and no
    token from ``argv`` (which carries an absolute extension path) reaches a
    caller, an exception message, or any record.
    """
    if len(argv) < 2:
        return False
    index = 2
    while index < len(argv):
        token = argv[index]
        if token in _PI_SOURCE_ESTABLISHED_LONG_OPTIONS_WITH_VALUE:
            if index + 1 >= len(argv):
                return False
            index += 2
            continue
        if token in _PI_SOURCE_ESTABLISHED_LONG_OPTIONS_WITHOUT_VALUE:
            index += 1
            continue
        return False
    return True


# -- 5F3B-I2B-L1-LF1-FU1: required-flag evidence is THREE-STATE ---------------
#
# THE FU1 BLOCKER. LF1's producer computed
#
#     required_flags_accepted = argv_options_source_established
#                               and lf_jsonl_correlation_succeeded
#
# The POSITIVE implication that expression rests on is sound:
#
#     correlated RPC response  =>  Pi entered runRpcMode
#                              =>  no unknown-option startup rejection occurred
#
# The REVERSE implication is NOT:
#
#     no correlated response   =/=>  an unknown CLI flag was rejected
#
# Because the frozen controller evaluates RPC_LAUNCH_SHAPE, then
# REQUIRED_LAUNCH_FLAGS, then LF_JSONL_CORRELATION in that order, and reads
# ``required_flags_accepted=False`` as REQUIRED_LAUNCH_FLAGS_REJECTED, every
# one of these recognized ``await_response`` outcomes --
# ``RUNTIME_DEADLINE_EXPIRED``, ``RUNTIME_PROTOCOL_VIOLATION``,
# ``RUNTIME_OUTPUT_CAP_EXCEEDED``, ``RUNTIME_EVENT_CAP_EXCEEDED``,
# ``RUNTIME_READ_ERROR`` and a generic ``RUNTIME_EXITED_EARLY`` -- was
# attributed FIRST as an unknown-flag rejection, though none of them
# mechanically proves one. That is a truthful-attribution defect, and it also
# meant the four launch facts were not observationally independent: LF
# correlation false forced required flags false, unconditionally.
#
# The correction is to treat required-flag evidence as THREE conceptual
# states internally, and to map them into the frozen two-valued field only
# where the mapping is honest:
#
#     ACCEPTED       mechanical evidence establishes that NO unknown-option
#                    startup rejection occurred;
#     REJECTED       mechanical evidence specifically establishes that Pi
#                    rejected an argv option as unknown;
#     INDETERMINATE  neither can be established.
#
# Nothing is added to the frozen ``RuntimeLaunchObservation`` or to the frozen
# controller: the three states live here, in this module's own private
# classification and in its L1-level bounded launch diagnostic.

#: The three declared required-flag classification codes. These are also
#: :class:`LaunchDiagnostic` values -- see :data:`LAUNCH_DIAGNOSTIC_CODES`.
REQUIRED_FLAGS_ACCEPTED = "required_flags_accepted"
REQUIRED_FLAGS_REJECTED_UNKNOWN_OPTION = "required_flags_rejected_unknown_option"
REQUIRED_FLAGS_INDETERMINATE = "required_flags_indeterminate"

REQUIRED_FLAG_STATES: frozenset[str] = frozenset(
    {
        REQUIRED_FLAGS_ACCEPTED,
        REQUIRED_FLAGS_REJECTED_UNKNOWN_OPTION,
        REQUIRED_FLAGS_INDETERMINATE,
    }
)

#: The exact character bound ``PiRpcSupervisor.stderr_snapshot()`` applies to
#: its ``text_tail`` field (``text[-4000:]``). Because decoding N bytes can
#: only ever produce at most N characters, a snapshot whose ``bytes_retained``
#: does not exceed this bound carries its ENTIRE retained stderr in
#: ``text_tail``, with nothing sliced away. An offline test asserts this
#: constant still matches the frozen AR2 source.
_STDERR_TEXT_TAIL_CHAR_LIMIT = 4000

#: ``dist/main.js`` prints every diagnostic through ``chalk`` -- colourless
#: when stderr is a pipe (as it always is here), but the wrapper is part of
#: the emission path, so its SGR sequences are stripped before matching
#: rather than being allowed to silently defeat the match.
_ANSI_SGR_SEQUENCE = re.compile(r"\x1b\[[0-9;]*m")

#: The exact prefix ``dist/main.js`` prints for an ERROR diagnostic -- both at
#: the ``parseArgs`` site and in ``reportDiagnostics`` (``prefix = "Error: "``).
#: Only an ERROR diagnostic reaches ``process.exit(1)``, so only an ERROR line
#: is accepted as evidence of a rejection.
_PI_DIAGNOSTIC_ERROR_PREFIX = "Error: "

#: The exact unknown-option diagnostic MESSAGE shape the installed package
#: emits, established from its own source by OFFLINE inspection (no launch, no
#: version gate):
#:
#:   - ``dist/cli/args.js`` ``parseArgs`` pushes an error diagnostic whose
#:     message is "Unknown option: " followed by the offending single-dash
#:     token;
#:   - ``dist/core/agent-session-services.js`` ``applyExtensionFlagValues``
#:     pushes an error diagnostic whose message is "Unknown option: " (one
#:     flag) or "Unknown options: " (more than one) followed by the unknown
#:     long-flag names, each re-prefixed with "--" and joined with ", ".
#:
#: Both are printed to STDERR and both are strictly followed by
#: ``process.exit(1)`` BEFORE the ``appMode === "rpc"`` branch that awaits
#: ``runRpcMode``, so a rejected option can never answer an RPC command.
_UNKNOWN_OPTION_DIAGNOSTIC = re.compile(r"^Unknown options?:[ ](?P<names>\S.*)$")


def _argv_option_tokens(argv: tuple[str, ...]) -> frozenset[str]:
    """The OPTION tokens in AIDO's own ``argv``, walked Pi's parser's way.

    This is deliberately NOT :func:`_argv_options_are_source_established`:
    that function answers "is every option token one Pi's parser is
    source-established to recognize?" and fails closed on the first token it
    does not know. This one answers "which tokens did AIDO actually pass as
    options?", INCLUDING ones that are not source-established -- because those
    are exactly the tokens a genuine unknown-option diagnostic would name, and
    a finding must be tied to an option actually present in AIDO's own argv.

    ``argv[0]``/``argv[1]`` are the two pinned program paths and are skipped.
    Value consumption mirrors ``dist/cli/args.js`` ``parseArgs``: a
    source-established value-taking option consumes the following token; a
    ``--name=value`` token carries its own value; and an UNRECOGNIZED long
    option consumes the next token as its value only when that token starts
    with neither ``-`` nor ``@`` (``parseArgs``' own rule).

    Returns option tokens only -- never a value token, so no absolute
    extension path, model id or provider id is ever collected. The result is
    consumed inside :func:`_unknown_option_rejection_established` for one
    membership test and never reaches a caller, a record, or an exception.
    """
    if not isinstance(argv, tuple) or len(argv) < 2:
        return frozenset()
    tokens: set[str] = set()
    index = 2
    while index < len(argv):
        token = argv[index]
        if not isinstance(token, str):
            return frozenset()
        if token.startswith("--"):
            name_part, separator, _value_part = token.partition("=")
            tokens.add(name_part)
            if separator:
                index += 1
                continue
            if token in _PI_SOURCE_ESTABLISHED_LONG_OPTIONS_WITH_VALUE:
                index += 2
                continue
            if token in _PI_SOURCE_ESTABLISHED_LONG_OPTIONS_WITHOUT_VALUE:
                index += 1
                continue
            following = argv[index + 1] if index + 1 < len(argv) else None
            if (
                isinstance(following, str)
                and not following.startswith("-")
                and not following.startswith("@")
            ):
                index += 2
                continue
            index += 1
            continue
        if token.startswith("-"):
            tokens.add(token)
            index += 1
            continue
        index += 1
    return frozenset(tokens)


def _unknown_option_rejection_established(
    *, argv: tuple[str, ...], stderr_snapshot: Any
) -> bool:
    """Whether a bounded startup diagnostic MECHANICALLY establishes that Pi
    rejected an option in AIDO's own argv as unknown.

    This is the ONLY thing in this module that inspects raw stderr, and it
    does so TRANSIENTLY: the snapshot's ``text_tail`` is scanned here, reduced
    to one ``bool``, and dropped. No line, message, option name, byte count or
    fragment of it is returned, retained, logged, ``repr()``'d, placed in a
    record, or placed in an exception message.

    It fails CLOSED -- returning ``False``, i.e. "not established", which the
    caller resolves to INDETERMINATE and never to REJECTED -- whenever:

    - the snapshot is not the frozen mapping shape, or reports ``captured``
      anything other than exactly ``True``;
    - the stderr reader recorded a read error (``read_error is not None``);
    - the bounded reader dropped bytes (``cap_exceeded`` is anything other
      than exactly ``False``, or ``bytes_seen != bytes_retained``);
    - the retained stderr exceeds :data:`_STDERR_TEXT_TAIL_CHAR_LIMIT`, so
      ``text_tail`` may itself be a sliced tail rather than the whole of it;
    - ``text_tail`` is not a ``str``;
    - no line matches the exact ``Error: Unknown option(s): ...`` shape;
    - a matching line names ANY option token that is not present in AIDO's own
      argv (an ambiguous diagnostic proves nothing about AIDO's flags).

    ``eof`` is deliberately NOT required. Completeness of the stream matters
    only for an ABSENCE proof, and this function never makes one: it accepts
    only the POSITIVE presence of a diagnostic, and the checks above already
    prove nothing was dropped from what the reader did see. Requiring ``eof``
    would add a race in which a genuine rejection reads as indeterminate
    purely because the reader thread had not yet observed end-of-stream.
    """
    if not isinstance(stderr_snapshot, dict):
        return False
    if stderr_snapshot.get("captured") is not True:
        return False
    if stderr_snapshot.get("read_error") is not None:
        return False
    if stderr_snapshot.get("cap_exceeded") is not False:
        return False
    bytes_seen = stderr_snapshot.get("bytes_seen")
    bytes_retained = stderr_snapshot.get("bytes_retained")
    if type(bytes_seen) is not int or type(bytes_retained) is not int:
        return False
    if bytes_seen != bytes_retained or bytes_retained > _STDERR_TEXT_TAIL_CHAR_LIMIT:
        return False
    text_tail = stderr_snapshot.get("text_tail")
    if type(text_tail) is not str:
        return False
    option_tokens = _argv_option_tokens(argv)
    if not option_tokens:
        return False
    for raw_line in text_tail.splitlines():
        line = _ANSI_SGR_SEQUENCE.sub("", raw_line).strip()
        if not line.startswith(_PI_DIAGNOSTIC_ERROR_PREFIX):
            continue
        match = _UNKNOWN_OPTION_DIAGNOSTIC.match(line[len(_PI_DIAGNOSTIC_ERROR_PREFIX) :])
        if match is None:
            continue
        named = [part.strip() for part in match.group("names").split(",")]
        if any(not name for name in named):
            continue
        if all(name in option_tokens for name in named):
            return True
    return False


def _classify_required_flag_evidence(
    *,
    argv: tuple[str, ...],
    argv_options_source_established: bool,
    lf_jsonl_correlation_succeeded: bool,
    stderr_snapshot_reader: Any,
) -> str:
    """Classify required-flag evidence into exactly one of the three states.

    ACCEPTED is decided FIRST, and it is the LF1 positive proof, unchanged:
    the actual argv is source-established AND the exact runtime returned a
    correlated RPC response. That response can only have been produced from
    inside ``runRpcMode``, which both unknown-option exits are strictly
    earlier than, so it establishes that no unknown-option startup rejection
    occurred. Deciding it first also means the ordinary passing path never
    reads raw stderr at all.

    Only when that positive proof does NOT hold is a bounded startup
    diagnostic consulted, and only to establish the specifically-observed
    REJECTED state. Everything else -- a deadline, a protocol violation
    without a correlated response, an output cap, an event cap, a read error,
    a generic early exit with no unknown-option observation, and an
    unreadable, truncated or ambiguous diagnostic -- is INDETERMINATE.

    An argv whose options are NOT source-established is INDETERMINATE too,
    even when a correlated response DID come back. That case is a fail-closed
    refusal about AIDO's OWN argv vocabulary having drifted from the parser
    behaviour this module established from source -- it is emphatically NOT a
    claim that Pi rejected anything, which is precisely why it must not be
    reported as a rejection. The actual-argv check is kept (LF1 added it so a
    future argv change could not ride silently on the runtime-behaviour half);
    what FU1 changes is only where its failure is allowed to land.

    ``RUNTIME_EXITED_EARLY`` has NO special status here: no supervisor outcome
    constant is read by this function at all. An unknown-option startup
    rejection is ONE source-supported cause of an early exit, not the only
    one, so an early exit alone is never treated as proof of one.
    """
    if argv_options_source_established and lf_jsonl_correlation_succeeded:
        return REQUIRED_FLAGS_ACCEPTED
    try:
        snapshot = stderr_snapshot_reader()
    except Exception:  # noqa: BLE001 - an unreadable diagnostic proves nothing
        return REQUIRED_FLAGS_INDETERMINATE
    if _unknown_option_rejection_established(argv=argv, stderr_snapshot=snapshot):
        return REQUIRED_FLAGS_REJECTED_UNKNOWN_OPTION
    return REQUIRED_FLAGS_INDETERMINATE


def _protocol_violation_observed(stdout_state: dict[str, Any]) -> bool:
    """Project the frozen supervisor's ``protocol_violation`` fact, correctly.

    **5F3B-I2B-L1-LF1 root cause.** The frozen AR2 contract is
    ``str | None``, never ``bool``:
    ``ar2.protocol.RecordStreamReader.protocol_violation`` is initialised to
    ``None`` and is only ever assigned a violation MESSAGE string, and
    ``PiRpcSupervisor.stdout_state()`` republishes that value verbatim. The
    previous projection here was ``type(raw) is not bool or raw is True``,
    which is UNSATISFIABLE against that contract: ``type(None) is not bool``
    is ``True``, so a wholly clean run reported a violation on every real
    launch. The offline suite could not catch it, because its supervisor
    double published a ``bool`` -- the double, not the adapter, disagreed
    with the real class.

    The corrected projection still fails CLOSED, in the one direction that
    matters: ``None`` -- and only ``None`` -- means no violation; a ``str``
    is a violation message; anything else is outside the frozen contract and
    is treated as a violation rather than coerced by truthiness. A ``bool``
    is therefore itself an out-of-contract value and fails closed.

    A state mapping that does not carry the key at all is likewise outside
    the frozen contract (``PiRpcSupervisor.stdout_state()`` always publishes
    it) and fails closed.

    The message string is examined for its TYPE only. It is never retained,
    returned, logged, or placed in any record -- raw runtime content never
    leaves this function.
    """
    if "protocol_violation" not in stdout_state:
        return True
    return stdout_state["protocol_violation"] is not None


# -- 5F3B-I2B-L1-LF1 OBJECTIVE 6: the bounded live launch diagnostic ----------
#
# The first live Candidate-A refusal proved the retained evidence was too
# coarse to tell an unknown-flag rejection apart from a launch-window
# protocol violation without reading raw logs afterwards. This is the
# smallest bounded, scrub-safe diagnostic that separates them.
#
# It is DECLARED-ENUM ONLY. Raw runtime observations are reduced to these
# fixed literals at the moment of observation and the raw values are dropped
# immediately; no stdout, stderr, RPC object, endpoint, API key, broker
# token, pipe name, capability id, absolute workspace path, argv token or
# violation message can reach it. It lives at the L1 harness/live-run level
# ONLY -- neither the frozen ``RuntimeLaunchObservation`` nor the frozen
# ``CategoryBEvidence`` schema is touched, so frozen I2B is not reopened.

ARGV_OPTIONS_SOURCE_ESTABLISHED = "argv_options_all_source_established"
ARGV_OPTION_NOT_SOURCE_ESTABLISHED = "argv_option_not_source_established"

CORRELATION_RESPONSE_RECEIVED = "correlated_rpc_response_received"
CORRELATION_NONE_RUNTIME_EXITED_EARLY = "no_response_runtime_exited_early"
CORRELATION_NONE_DEADLINE_EXPIRED = "no_response_deadline_expired"
CORRELATION_NONE_PROTOCOL_VIOLATION = "no_response_protocol_violation"
CORRELATION_NONE_OUTPUT_CAP_EXCEEDED = "no_response_output_cap_exceeded"
CORRELATION_NONE_EVENT_CAP_EXCEEDED = "no_response_event_cap_exceeded"
CORRELATION_NONE_READ_ERROR = "no_response_read_error"
CORRELATION_NONE_UNRECOGNIZED_OUTCOME = "no_response_unrecognized_outcome"

LAUNCH_WINDOW_PROTOCOL_VIOLATION_OBSERVED = "launch_window_protocol_violation_observed"
LAUNCH_WINDOW_PROTOCOL_VIOLATION_NOT_OBSERVED = (
    "launch_window_protocol_violation_not_observed"
)

#: Every literal a :class:`LaunchDiagnostic` field may ever hold. An offline
#: test asserts the produced values are always drawn from this set.
LAUNCH_DIAGNOSTIC_CODES: frozenset[str] = frozenset(
    {
        ARGV_OPTIONS_SOURCE_ESTABLISHED,
        ARGV_OPTION_NOT_SOURCE_ESTABLISHED,
        CORRELATION_RESPONSE_RECEIVED,
        CORRELATION_NONE_RUNTIME_EXITED_EARLY,
        CORRELATION_NONE_DEADLINE_EXPIRED,
        CORRELATION_NONE_PROTOCOL_VIOLATION,
        CORRELATION_NONE_OUTPUT_CAP_EXCEEDED,
        CORRELATION_NONE_EVENT_CAP_EXCEEDED,
        CORRELATION_NONE_READ_ERROR,
        CORRELATION_NONE_UNRECOGNIZED_OUTCOME,
        LAUNCH_WINDOW_PROTOCOL_VIOLATION_OBSERVED,
        LAUNCH_WINDOW_PROTOCOL_VIOLATION_NOT_OBSERVED,
        # 5F3B-I2B-L1-LF1-FU1: the three-state required-flag classification,
        # the ONE place the INDETERMINATE state is visible at all. The frozen
        # ``RuntimeLaunchObservation`` still carries only the bool.
        REQUIRED_FLAGS_ACCEPTED,
        REQUIRED_FLAGS_REJECTED_UNKNOWN_OPTION,
        REQUIRED_FLAGS_INDETERMINATE,
    }
)
assert REQUIRED_FLAG_STATES <= LAUNCH_DIAGNOSTIC_CODES

#: The raw ``await_response`` outcome -> declared correlation code map. Every
#: member of :data:`_RECOGNIZED_AWAIT_RESPONSE_OUTCOMES` appears exactly once;
#: anything outside it reduces to
#: :data:`CORRELATION_NONE_UNRECOGNIZED_OUTCOME`, so no raw outcome string
#: from the supervisor is ever retained verbatim.
_CORRELATION_CODE_BY_OUTCOME: dict[str, str] = {
    RUNTIME_RESPONSE_RECEIVED: CORRELATION_RESPONSE_RECEIVED,
    RUNTIME_EXITED_EARLY: CORRELATION_NONE_RUNTIME_EXITED_EARLY,
    RUNTIME_DEADLINE_EXPIRED: CORRELATION_NONE_DEADLINE_EXPIRED,
    RUNTIME_PROTOCOL_VIOLATION: CORRELATION_NONE_PROTOCOL_VIOLATION,
    RUNTIME_OUTPUT_CAP_EXCEEDED: CORRELATION_NONE_OUTPUT_CAP_EXCEEDED,
    RUNTIME_EVENT_CAP_EXCEEDED: CORRELATION_NONE_EVENT_CAP_EXCEEDED,
    RUNTIME_READ_ERROR: CORRELATION_NONE_READ_ERROR,
}
assert set(_CORRELATION_CODE_BY_OUTCOME) == set(_RECOGNIZED_AWAIT_RESPONSE_OUTCOMES)


@dataclass(frozen=True)
class LaunchDiagnostic:
    """Four declared codes. Nothing raw, nothing secret, nothing unbounded.

    5F3B-I2B-L1-LF1-FU1 added ``required_flags_code``: the ONLY place the
    three-state required-flag classification is visible, and the only thing
    that distinguishes a mechanically-established unknown-option REJECTION
    from an INDETERMINATE launch. It is a declared literal from
    :data:`REQUIRED_FLAG_STATES`, never a stderr line, never an option name,
    and never an unknown-option message.
    """

    argv_code: str
    correlation_code: str
    launch_window_protocol_code: str
    required_flags_code: str

    def as_dict(self) -> dict[str, str]:
        return {
            "argv_options": self.argv_code,
            "launch_correlation": self.correlation_code,
            "launch_window_protocol": self.launch_window_protocol_code,
            "required_launch_flags": self.required_flags_code,
        }


def _launch_diagnostic(
    *,
    argv_ok: bool,
    wait_outcome: Any,
    protocol_violation_observed: bool,
    required_flags_code: str,
) -> LaunchDiagnostic:
    """Reduce the raw launch-window observations to declared codes at once.

    ``required_flags_code`` arrives ALREADY reduced -- it is produced by
    :func:`_classify_required_flag_evidence`, which is the only thing that
    ever sees a raw stderr snapshot and which returns one of exactly three
    declared literals.
    """
    if required_flags_code not in REQUIRED_FLAG_STATES:
        raise LiveAdapterError(
            "launch diagnostic refused: the required-flag classification is "
            "not one of the three declared states"
        )
    return LaunchDiagnostic(
        argv_code=(
            ARGV_OPTIONS_SOURCE_ESTABLISHED
            if argv_ok
            else ARGV_OPTION_NOT_SOURCE_ESTABLISHED
        ),
        correlation_code=_CORRELATION_CODE_BY_OUTCOME.get(
            wait_outcome if isinstance(wait_outcome, str) else "",
            CORRELATION_NONE_UNRECOGNIZED_OUTCOME,
        ),
        launch_window_protocol_code=(
            LAUNCH_WINDOW_PROTOCOL_VIOLATION_OBSERVED
            if protocol_violation_observed
            else LAUNCH_WINDOW_PROTOCOL_VIOLATION_NOT_OBSERVED
        ),
        required_flags_code=required_flags_code,
    )


# -- BLOCKER 2 (5F3B-I2B-L1-FU3): RuntimeIdentity ISSUANCE -------------------
#
# FU2 removed PATH substitution by comparing a caller-supplied
# ``RuntimeIdentity``'s executable paths against this machine's own trusted
# resolver. It did not remove caller AUTHORSHIP: ``RuntimeIdentity`` is a
# plain, freely-constructible frozen dataclass, so a supported caller could
# build one carrying the three trusted paths and an entirely fabricated
# ``reported_version``, and this module would later publish that fabricated
# string as ``RuntimeLaunchObservation.observed_pi_version``. That is an
# evidence-provenance defect, not an authorization defect -- the version is
# NOT, and never becomes, a gate (no comparison, no pin, no equality check
# anywhere; see ``_require_runtime_identity_matches_trusted_resolution``,
# which deliberately checks only that the string is non-empty).
#
# The fix is an ISSUANCE boundary, not a stronger inspection: the SAME
# trusted operation that runs the one provenance-only ``node cli.js
# --version`` probe (:func:`resolve_pi_identity`) is the only thing that can
# mint the object a live attempt consumes.
#
# What makes it unforgeable, mechanically:
#
#   * :class:`IssuedRuntimeIdentity` carries NO identity data of its own --
#     only an opaque, fresh 128-bit issuance token. Every identity fact is
#     read back out of this module's own process-local registry, so there is
#     literally no field on the object a caller could author. A fabricated
#     ``reported_version`` has nowhere to live.
#   * Its ``__init__`` refuses any caller that cannot present the
#     module-private issuer key object, so ``IssuedRuntimeIdentity(...)`` is
#     not a public construction path.
#   * An issuance is ONE-SHOT: the first ``LiveCategoryBAdapters``
#     construction claims it, and a second claim of the same issuance is
#     refused. One ``--version`` probe therefore authorizes exactly one live
#     attempt, and an issued identity can never be replayed into another run.
#
# Per this package's already-accepted FU3B threat boundary (see
# ``qualification.i2_issuance``'s own module docstring), this is NOT a
# defense against a caller that deliberately imports underscored internals
# or reaches through ``object.__new__``; it is the removal of a PUBLIC,
# SUPPORTED path by which a well-behaved caller could author the evidence.
# Deliberately NOT used: a caller-supplied ``trusted=True`` boolean, a
# caller-supplied version/hash accepted as proof, and a global mutable "last
# resolved identity" convention (which has no attempt binding at all).

#: The module-private capability object :class:`IssuedRuntimeIdentity`'s
#: constructor demands. Never exported, never a string, never derivable.
_IDENTITY_ISSUER_KEY = object()


@dataclass
class _IssuedRuntimeIdentityRecord:
    """One issuance. ``claimed`` makes the issuance one-shot (attempt binding)."""

    identity: RuntimeIdentity
    claimed: bool = False


#: Process-local, in-memory only -- never persisted, never an evidence
#: field, and carrying no claim of surviving a process restart. Keyed by
#: issuance token alone, exactly as ``qualification.i2_issuance``'s own
#: accepted registry is.
_ISSUED_RUNTIME_IDENTITIES: dict[str, _IssuedRuntimeIdentityRecord] = {}


class IssuedRuntimeIdentity:
    """An opaque proof that THIS module's own trusted probe produced one
    :class:`~ar2.launch.RuntimeIdentity`, for exactly one live attempt.

    Holds only an issuance token. Every identity fact -- including
    ``reported_version``, which stays provenance only -- lives in this
    module's registry, never on the object, so no caller-authored value can
    reach :class:`~qualification.i2b_session.RuntimeLaunchObservation`.
    ``repr()`` renders no path and no token.
    """

    __slots__ = ("_issuance_token",)

    def __init__(self, issuer_key: Any, *, issuance_token: str) -> None:
        if issuer_key is not _IDENTITY_ISSUER_KEY:
            raise LiveAdapterError(
                "runtime identity refused: IssuedRuntimeIdentity is minted "
                "only by this module's own qualification-owned issuance path"
            )
        self._issuance_token = issuance_token

    @property
    def node_executable(self) -> str:
        """The trusted Node executable, read from the REGISTRY -- the one
        identity fact the live entry point needs outside the adapter (the
        frozen controller's own child-environment PATH narrowing). Never a
        value stored on this object."""
        record = _ISSUED_RUNTIME_IDENTITIES.get(self._issuance_token)
        if record is None:
            raise LiveAdapterError(
                "runtime identity refused: this issued runtime identity is "
                "not present in this process's own issuance registry"
            )
        return record.identity.node_executable

    def __repr__(self) -> str:  # noqa: D105 - see class docstring
        return f"{type(self).__name__}(issued=True)"


def _issue_runtime_identity(identity: RuntimeIdentity) -> IssuedRuntimeIdentity:
    """Package-internal. The ONLY supported caller is
    :func:`resolve_pi_identity`, immediately after its one real
    ``--version`` probe."""
    if type(identity) is not RuntimeIdentity:
        raise LiveAdapterError(
            "runtime identity refused: only a RuntimeIdentity can be issued"
        )
    token = secrets.token_hex(16)
    if token in _ISSUED_RUNTIME_IDENTITIES:  # pragma: no cover - 128-bit collision
        raise LiveAdapterError("runtime identity refused: issuance token collision")
    _ISSUED_RUNTIME_IDENTITIES[token] = _IssuedRuntimeIdentityRecord(identity=identity)
    return IssuedRuntimeIdentity(_IDENTITY_ISSUER_KEY, issuance_token=token)


def _claim_issued_runtime_identity(issued: Any) -> RuntimeIdentity:
    """Consume one issuance for one live attempt, and return the TRUSTED
    identity the registry holds -- never anything read off ``issued``.

    Claiming happens BEFORE any further validation, so a construction that
    is subsequently refused still burns the issuance: a rejected attempt can
    never re-present the same probe's authority to a second construction.
    """
    if type(issued) is not IssuedRuntimeIdentity:
        raise LiveAdapterError(
            "LiveCategoryBAdapters requires a RuntimeIdentity ISSUED by this "
            "module's own resolve_pi_identity probe; a caller-constructed "
            "RuntimeIdentity can never authorize a live attempt"
        )
    token = issued._issuance_token
    record = _ISSUED_RUNTIME_IDENTITIES.get(token) if type(token) is str else None
    if record is None:
        raise LiveAdapterError(
            "runtime identity refused: this issued runtime identity is not "
            "present in this process's own issuance registry"
        )
    if record.claimed:
        raise LiveAdapterError(
            "runtime identity refused: this issued runtime identity was "
            "already consumed by one live attempt and is never reusable"
        )
    record.claimed = True
    return record.identity


def resolve_pi_identity() -> IssuedRuntimeIdentity:
    """Locate Node + Pi and OBSERVE Pi's version. Never gates on the value.

    **The trusted issuance boundary (FU3 BLOCKER 2).** This is the one
    operation authorized to run the single provenance-only ``node cli.js
    --version`` probe for a live attempt, and it is therefore the one
    operation that mints the :class:`IssuedRuntimeIdentity` a
    :class:`LiveCategoryBAdapters` will consume. The probe and the issuance
    are the SAME operation, so the identity handed to the adapter is
    mechanically tied to a version this process itself observed -- there is
    no supported path by which a caller can author ``reported_version``,
    and none by which an unissued ``RuntimeIdentity`` can reach a live
    launch. ``reported_version`` remains provenance ONLY: it is observed,
    required to be non-empty, recorded, and never compared to anything.

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
    return _issue_runtime_identity(
        RuntimeIdentity(
            node_executable=node_executable,
            pi_cli_js=cli_js,
            pi_package_root=package_root,
            reported_version=reported,
            launch_shape="node_direct",
        )
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


#: FU3 BLOCKER 3 / FU4 BLOCKER 1 -- generated-config RELEASE ownership for
#: the Category-A self-checks that actually generate a config.
#:
#: Three preflight producers below call
#: ``i2_pi_config.write_qualification_pi_config``
#: (``preflight_config_generator_self_check``,
#: ``preflight_child_environment_builder_self_check``, and
#: ``preflight_candidate_route_generator_symmetry``, which issues TWO). Every
#: other Category-A producer generates nothing and is untouched by this rule.
#:
#: FU2 routed only the SUCCESSFUL exits through the official cleanup path.
#: FU3 moved that official cleanup into a ``finally``, so it is attempted
#: exactly once per returned object on every exit. FU4 fixes what remained:
#: the throwaway parent's raw ``shutil.rmtree`` still ran UNCONDITIONALLY
#: afterwards.
#:
#: That mattered because the frozen cleanup primitive has a deliberate
#: invariant (``i2_cleanup.scrub_generated_qualification_config``):
#:
#:     removal VERIFIED      -> the process-local issuance is discarded
#:     removal NOT verified  -> the issuance is RETAINED, precisely because
#:                              the directory still exists and a future
#:                              authorized cleanup must remain possible
#:
#: So "official cleanup could not verify, then raw-delete the tree anyway"
#: destroyed the path while leaving the issuance live -- exactly the stale-
#: authority class FU3 set out to eliminate, reintroduced one line later.
#:
#: The rule enforced below, per GENERATED OBJECT (never one aggregate bool
#: across two objects):
#:
#:     A. official cleanup VERIFIED -- the issuance is gone and the config
#:        tree is verified absent, so the throwaway PARENT may be raw-deleted
#:        for hygiene. Gate unaffected.
#:     B. generation failed BEFORE returning an object -- no issuance exists
#:        and nothing was cleaned, so the throwaway PARENT may be
#:        raw-deleted. Gate unaffected by cleanup.
#:     C. official cleanup NOT VERIFIED, or it raised -- the frozen primitive
#:        intentionally RETAINED the issuance. The gate FAILS, and NOTHING
#:        beneath that retained issuance is raw-deleted. The synthetic temp
#:        tree may survive on disk in this failure-only path; that is
#:        strictly preferable to falsifying the issuance/path coupling.
#:
#: In case C this module never calls an ``i2_issuance`` discard function,
#: never mutates the registry, never retries the delete through an
#: unreviewed path, and never converts an unverified cleanup into success
#: because a later raw delete happened to remove the directory. The truthful
#: residual is reported as it stands: cleanup was attempted, cleanup was not
#: verified, the preflight failed. A live attempt aborts on that Category-A
#: failure -- before the version probe and before the credential boundary.


@dataclass(frozen=True)
class _GeneratedConfigRelease:
    """What releasing ONE generated self-check config actually achieved.

    Deliberately three recorded facts rather than a single bool, because
    "nothing was generated" and "generated and successfully released" are
    different histories that happen to permit the same follow-up action,
    and "generated but NOT released" must permit neither the gate to pass
    nor the parent to be deleted.
    """

    generated_object_existed: bool
    cleanup_attempted: bool
    cleanup_verified: bool

    @property
    def issuance_outstanding(self) -> bool:
        """The one derived predicate both decisions below read.

        True exactly while a generated object exists whose issuance the
        frozen cleanup primitive deliberately RETAINED. Identity against the
        ``True`` singleton is already enforced where ``cleanup_verified`` is
        set, never bare truthiness on a primitive's return value.
        """
        return self.generated_object_existed and not self.cleanup_verified

    @property
    def gate_ok(self) -> bool:
        """Whether this release lets the producing gate pass."""
        return not self.issuance_outstanding

    @property
    def throwaway_parent_may_be_removed(self) -> bool:
        """Whether the throwaway PARENT directory may now be raw-deleted."""
        return not self.issuance_outstanding


def _release_generated_self_check_config(
    generated: GeneratedQualificationConfig | None,
) -> _GeneratedConfigRelease:
    """Attempt the official qualification cleanup/discard for ONE generated
    self-check config, exactly once. Never a raw path delete.

    :func:`~qualification.i2_cleanup.scrub_generated_qualification_config`
    is the ONLY cleanup authority used -- it is what discards the
    process-local :mod:`qualification.i2_issuance` record, and only on a
    removal it verified. Any failure, including the cleanup primitive itself
    raising, is recorded as an unverified cleanup rather than escaping: a
    cleanup attempt must never erase the gate result it is cleaning up
    after, and must never be skipped by an exception on a neighbouring
    object.
    """
    if generated is None:
        return _GeneratedConfigRelease(
            generated_object_existed=False, cleanup_attempted=False, cleanup_verified=False
        )
    try:
        verified = scrub_generated_qualification_config(generated).scrub_verified is True
    except Exception:  # noqa: BLE001 - bounded: a cleanup failure is a gate failure, never a crash
        verified = False
    return _GeneratedConfigRelease(
        generated_object_existed=True, cleanup_attempted=True, cleanup_verified=verified
    )


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

    **L1-FU2 nearby fix, completed by L1-FU3 BLOCKER 3 and L1-FU4
    BLOCKER 1.** Cleanup goes through the ACCEPTED qualification cleanup
    path
    (:func:`~qualification.i2_cleanup.scrub_generated_qualification_config`,
    via :func:`_release_generated_self_check_config`) rather than a raw
    ``shutil.rmtree`` of the whole throwaway parent directory -- the raw
    delete bypassed :mod:`qualification.i2_issuance`'s own discard step,
    leaving a stale process-local issuance record behind even though the
    directory was gone. FU2 fixed only the SUCCESS exit; FU3 moved the
    official cleanup into a ``finally``, so it is attempted exactly once on
    EVERY exit after generation returned an object -- including the
    verification-failure branch below and an unexpected propagating
    exception. FU4 then made the throwaway parent's raw delete
    CONDITIONAL: it runs only once the release verified (or when no object
    was ever generated), never underneath an issuance the frozen primitive
    deliberately retained. A cleanup that cannot be verified FAILS this
    gate, rather than silently passing.
    """
    tmp_root = tempfile.mkdtemp(prefix="i2b-preflight-self-check-")
    generated: GeneratedQualificationConfig | None = None
    gate_failed = False
    try:
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
            gate_failed = True
    finally:
        release = _release_generated_self_check_config(generated)
        if release.throwaway_parent_may_be_removed:
            shutil.rmtree(tmp_root, ignore_errors=True)

    if gate_failed or not release.gate_ok:
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

    **FU3 BLOCKER 3 + FU4 BLOCKER 1.** The post-generation failure branch
    used to raw-delete the throwaway parent, leaving the process-local
    issuance record behind after a FAILED preflight. The official
    cleanup/discard now runs from a ``finally``, exactly once, on every exit
    where generation returned an object -- the secret-context,
    environment-builder and audit failures included -- and the raw parent
    delete happens only after it AND only when that release verified.
    """
    tmp_root = tempfile.mkdtemp(prefix="i2b-preflight-env-self-check-")
    generated: GeneratedQualificationConfig | None = None
    gate_failed = False
    try:
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
            if (
                audit["sensitive_names_forwarded_count"] != 0
                or audit["profile_names_forwarded_to_child"]
            ):
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
            gate_failed = True
    finally:
        release = _release_generated_self_check_config(generated)
        if release.throwaway_parent_may_be_removed:
            shutil.rmtree(tmp_root, ignore_errors=True)

    if gate_failed or not release.gate_ok:
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

    **FU3 BLOCKER 3 + FU4 BLOCKER 1.** This producer issues TWO configs, so
    the ownership rule applies to each independently: whichever generations
    returned an object get the official cleanup/discard exactly once, on
    every exit -- a validation failure after BOTH were issued cleans both,
    and a first generation that succeeded followed by a second that failed
    still cleans the first. Each throwaway parent's raw delete is then
    decided by ITS OWN release, never by one aggregate bool: a verified
    release for one config and an unverified release for the other removes
    only the released config's parent, leaving the other parent coupled to
    the issuance the frozen primitive retained. The earlier ``_cleanup``
    helper ran only where it was explicitly called and let a ``KeyError``
    from the document comparison reach the raw-delete branch with issuance
    records still live.
    """
    tmp_root_a = tempfile.mkdtemp(prefix="i2b-preflight-symmetry-a-")
    tmp_root_b = tempfile.mkdtemp(prefix="i2b-preflight-symmetry-b-")
    generated_a: GeneratedQualificationConfig | None = None
    generated_b: GeneratedQualificationConfig | None = None
    gate_failed = False

    try:
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
                k: v
                for k, v in models_a["providers"][generated_a.provider_id].items()
                if k != "models"
            }
            provider_b = {
                k: v
                for k, v in models_b["providers"][generated_b.provider_id].items()
                if k != "models"
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
        except (
            QualificationPiConfigError,
            QualificationPiConfigCleanupError,
            CleanupAuthorityError,
            KeyError,
        ):
            gate_failed = True
    finally:
        # BOTH issued objects, independently, exactly once each -- and each
        # throwaway parent's raw delete is decided by ITS OWN release, never
        # by one aggregate bool across the two (FU4 BLOCKER 1). A verified
        # release for A and an unverified release for B removes A's parent
        # and leaves B's parent coupled to B's retained issuance.
        release_a = _release_generated_self_check_config(generated_a)
        release_b = _release_generated_self_check_config(generated_b)
        if release_a.throwaway_parent_may_be_removed:
            shutil.rmtree(tmp_root_a, ignore_errors=True)
        if release_b.throwaway_parent_may_be_removed:
            shutil.rmtree(tmp_root_b, ignore_errors=True)

    if gate_failed or not (release_a.gate_ok and release_b.gate_ok):
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


def _broker_reports_pipe_resource_created(server: Any) -> bool:
    """FU3 BLOCKER 1: project AR2 D1's ``BrokerServer.pipe_resource_created``.

    This is the ONE public fact the partial-start branch is allowed to read
    (5F3B-I2B-L1-D1). It is monotonic and truthful by construction on the
    frozen dependency: ``True`` only immediately after
    ``winpipe.create_first_instance_pipe`` returned, never "creation was
    attempted", and never reset to ``False`` afterwards.

    Fail-closed in the direction that preserves cleanup: ONLY an exact
    ``False`` singleton reports "no broker resource ever existed". An
    unreadable attribute, or a value that is not exactly a ``bool`` --
    neither of which the frozen D1 surface can produce -- reports ``True``,
    so the one bounded supported cleanup is still attempted rather than
    skipped on the strength of a value this module could not verify.

    Nothing here reads ``server.state``, an exception, ``_pipe_handle``,
    ``_thread``, or any other private field.
    """
    try:
        raw = server.pipe_resource_created
    except Exception:  # noqa: BLE001 - an unreadable fact is never "nothing was created"
        return True
    if type(raw) is not bool:
        return True
    return raw


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


# -- 5F3B-LIVE1-C1-FU2: semantic authority STATE, not grant presence ----------
#
# BLOCKER. ``_semantic_capability_grant is None`` used to carry TWO different
# meanings at once: (1) an ordinary Category-B adapter, which must use the
# inert domain, and (2) a semantic adapter whose one grant was already
# consumed by a prior ``create_broker`` call, which must NEVER use the inert
# domain and must NEVER issue a second capability. ``create_broker`` could not
# tell those apart, because clearing the grant to ``None`` after consuming it
# was indistinguishable from never having had one.
#
# The correction adds a THIRD, explicit, mechanical state, private to this
# module, that a semantic instance moves through irreversibly:
#
#     CATEGORY_B_INERT       ordinary constructor only; every ``create_broker``
#                             call on this instance uses the inert domain.
#     SEMANTIC_GRANT_PENDING set ONLY by ``build_semantic_task_live_adapters``,
#                             after it has validated a genuine
#                             ``SemanticCapabilityGrant``; the ONE call in
#                             which issuance may be attempted.
#     SEMANTIC_GRANT_SPENT   set by ``create_broker`` itself, BEFORE it calls
#                             ``issue_semantic_broker_capability``, regardless
#                             of whether that call goes on to succeed, refuse
#                             expectedly, or raise unexpectedly. Every LATER
#                             ``create_broker`` call on the same instance
#                             refuses fail-closed from this state alone.
#
# There is still no caller-facing ``semantic=``/``semantic_mode=``/
# ``enable_writes=``/``use_real_capability=``/``capability_source=``/
# ``domain=`` parameter or public mode setter anywhere: this state is set only
# by ``build_semantic_task_live_adapters`` (PENDING) and by ``create_broker``
# itself (PENDING -> SPENT), never by a caller.

_CATEGORY_B_INERT = "category_b_inert"
_SEMANTIC_GRANT_PENDING = "semantic_grant_pending"
_SEMANTIC_GRANT_SPENT = "semantic_grant_spent"

#: Every literal :attr:`LiveCategoryBAdapters._semantic_authority_state` may
#: ever hold. An offline test asserts the field is always drawn from this set.
_SEMANTIC_AUTHORITY_STATES: frozenset[str] = frozenset(
    {_CATEGORY_B_INERT, _SEMANTIC_GRANT_PENDING, _SEMANTIC_GRANT_SPENT}
)


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
        runtime_identity: IssuedRuntimeIdentity,
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
        probe, never two (L1 brief, "SINGLE RUNTIME IDENTITY BINDING").

        **It must be an :class:`IssuedRuntimeIdentity`, never a bare
        ``RuntimeIdentity`` (FU3 BLOCKER 2).** A freely-constructed
        ``RuntimeIdentity`` -- even one carrying all three trusted paths --
        is refused here, because its ``reported_version`` would be
        caller-authored evidence. The issuance is claimed ONE-SHOT at this
        point, so one ``--version`` probe authorizes exactly one adapter
        instance and can never be replayed into a second run, and the
        identity this instance goes on to use is read from the issuance
        registry rather than off the presented object.

        The claimed identity is additionally bound, mechanically, to this
        machine's own trusted resolver path (L1-FU2 BLOCKER 1,
        RuntimeIdentity variant) -- that accepted check is unchanged and
        still runs, as defense in depth behind the issuance boundary.

        **There is no ``ar2_extension_source_dir`` parameter (L1-FU2
        BLOCKER 1).** The disposable extension's source is derived
        deterministically from this package's own reused ``ar2`` import and
        mechanically verified against a fixed, reviewed digest before this
        object exists -- no caller of this constructor can express a
        substitute.
        """
        identity = _claim_issued_runtime_identity(runtime_identity)
        _require_runtime_identity_matches_trusted_resolution(identity)
        self._environ_reader = environ_reader
        self._ar2_extension_source_dir = _require_authorized_extension_source()
        self._runtime_identity = identity
        self._experiment_id = experiment_id
        self._bounds = bounds or _DEFAULT_BOUNDS
        self._brokers: dict[str, _LiveBrokerRecord] = {}
        self._runtimes: dict[str, _LiveRuntimeRecord] = {}
        #: LF1 OBJECTIVE 6. Bounded, declared-code-only launch diagnostics,
        #: keyed by run id, recorded on exactly the ``launch_runtime`` path
        #: that reached the correlation window and therefore HAS a wait
        #: outcome to reduce. A creator-retained partial failure records
        #: none, deliberately: it has no correlation observation to describe,
        #: and the frozen controller already attributes it to its own
        #: RUNTIME_LAUNCH gate rather than to a launch-fact gate. Read by the
        #: L1 live entry point for the run artifact; never passed to, or
        #: observed by, the frozen controller.
        self._launch_diagnostics: dict[str, LaunchDiagnostic] = {}
        #: LF2 OBJECTIVE 6. The connection values the frozen controller
        #: ACTUALLY consumed on this run, recorded at the one credential
        #: boundary below so the authenticated route observer can derive its
        #: authority from the same object rather than from anything a caller
        #: hands it. ``None`` until the controller has read them, which is
        #: itself a refusal condition for the observer: a route observation
        #: can never precede the credential read it depends on.
        self._consumed_connection: ConnectionValues | None = None
        #: 5F3B-LIVE1-C1. ``None`` on the ORDINARY Category-B construction
        #: path -- which is every path reachable through this constructor --
        #: so ``create_broker`` below keeps today's inert domain as the
        #: DEFAULT, reached without the caller naming anything. It is set to
        #: an OPAQUE, module-external, one-shot
        #: :class:`~qualification.i2b_workspace.SemanticCapabilityGrant` by
        #: exactly one narrow construction path,
        #: :func:`build_semantic_task_live_adapters`, and by nothing else.
        #: There is deliberately no constructor parameter, no boolean, no
        #: setter and no public accessor for it: a caller cannot select
        #: broker capability authority, it can only present a grant that
        #: ``qualification.i2b_workspace`` alone can mint and that carries no
        #: authority fact of its own.
        #:
        #: **5F3B-LIVE1-C1-FU2:** this field alone is no longer what
        #: ``create_broker`` branches on -- clearing it to ``None`` after
        #: consumption proved indistinguishable from never having had a
        #: grant at all. It is retained only as the CARRIER of the opaque
        #: grant object between construction and consumption.
        #: :attr:`_semantic_authority_state` below is the sole authority
        #: ``create_broker`` reads.
        self._semantic_capability_grant: SemanticCapabilityGrant | None = None
        #: 5F3B-LIVE1-C1-FU2. The mechanical state distinguishing an ordinary
        #: Category-B instance from a semantic instance whose one grant is
        #: still pending, or already spent. Starts ``CATEGORY_B_INERT`` for
        #: every instance reachable through this constructor;
        #: :func:`build_semantic_task_live_adapters` alone may move a fresh
        #: instance to ``SEMANTIC_GRANT_PENDING``; ``create_broker`` itself
        #: alone may move ``SEMANTIC_GRANT_PENDING`` to
        #: ``SEMANTIC_GRANT_SPENT``, irreversibly, before it attempts
        #: issuance. No other transition exists, and no caller-facing
        #: parameter or setter can reach this field.
        self._semantic_authority_state: str = _CATEGORY_B_INERT

    # -- credential boundary -------------------------------------------------

    def read_connection(self) -> ConnectionValues:
        """The ONLY credential read in this module. Reused, unmodified.

        **5F3B-I2B-L1-LF2.** The resolved values are additionally RECORDED on
        this instance, so :class:`AuthenticatedB300RouteObserver` binds to the
        exact ``ConnectionValues`` the frozen controller consumed rather than
        to a base URL or credential supplied at the route boundary. The read
        itself is unchanged, and this is not a second read: a repeat call must
        resolve to identical values or the adapter refuses, so the recorded
        authority can never be quietly replaced mid-run.
        """
        values = read_connection_values(self._environ_reader)
        recorded = self._consumed_connection
        if recorded is not None and (
            recorded.base_url != values.base_url or recorded.api_key != values.api_key
        ):
            raise LiveAdapterError(
                "connection read refused: this run already consumed a different "
                "set of B300 connection values"
            )
        self._consumed_connection = values
        return values

    def consumed_connection_values(self) -> ConnectionValues | None:
        """The connection values this run actually consumed, or ``None``.

        Read only by :class:`AuthenticatedB300RouteObserver`. The returned
        object is the accepted, valid-by-construction
        :class:`~qualification.i2_credentials.ConnectionValues`, whose own
        ``__repr__`` redacts both fields.
        """
        return self._consumed_connection

    # -- broker authority ------------------------------------------------------

    def create_broker(self, request: BrokerCreationRequest) -> BrokerCreationObservation:
        """Create this run's broker. **The capability is the DEFAULT inert one.**

        5F3B-LIVE1-C1 adds exactly one alternative, and it is not reachable
        from this constructor: when -- and only when -- this instance was
        built by :func:`build_semantic_task_live_adapters`, the capability is
        the GENUINE one ``qualification.i2b_workspace`` issues for this exact
        (workspace nonce, ``run_id``, ``task_id``, ``task_revision``), from an
        AIDO-OBSERVED manifest and the frozen task contract. This call site is
        the design's EVENT 2 (capability issuance), and it is the first
        adapter call that carries both the run id and the exact workspace --
        which is why issuance happens here and not at ``read_connection``,
        whose frozen zero-argument shape is not widened.

        The state is transitioned to SPENT before it is consumed, so this
        instance can never present it twice; the issuance registry refuses a
        replay independently (defense in depth -- see the module-level
        ``_WORKSPACE_SEMANTIC_ISSUANCE`` note). A refused issuance **never**
        falls back to the inert domain: a semantic run in which every model
        operation was silently refused would read as candidate behaviour
        rather than as harness failure.

        **5F3B-LIVE1-C1-FU1: an EXPECTED issuance refusal is a truthful "no
        broker was ever attempted" observation, not an adapter exception.**
        The frozen design requires this failure to land at the controller's
        ``BROKER_SESSION`` gate as ``BROKER_CREATION_FAILED`` -- the same
        attribution an ordinary ``session=None`` broker-creation failure
        already gets -- rather than as ``ADAPTER_RAISED``. A bounded
        :class:`~qualification.i2b_workspace.WorkspaceAuthorityError` raised
        by :func:`issue_semantic_broker_capability` is therefore caught HERE,
        before any :class:`BrokerServer` is constructed or started, and
        projected into the frozen ``session=None`` / ``start_attempted=False``
        / ``resource_created=False`` shape -- truthful, because at that point
        no broker-start call has been reached and no resource exists. An
        UNEXPECTED exception (a programmer error, not a bounded refusal) is
        NOT caught here, and still reaches the frozen controller's
        ``ADAPTER_RAISED`` path -- the two failure classes stay distinct.

        **5F3B-LIVE1-C1-FU2: a semantic adapter may never fall back to
        Category-B inert mode.** ``_semantic_capability_grant is None`` used
        to mean BOTH "ordinary Category-B instance" and "semantic instance,
        grant already spent" -- indistinguishable, so a second call on a
        semantic instance fell through to the inert branch. This instance's
        :attr:`_semantic_authority_state` is now the sole authority this
        method branches on. It moves ``SEMANTIC_GRANT_PENDING`` ->
        ``SEMANTIC_GRANT_SPENT`` irreversibly, BEFORE the issuance attempt --
        so a genuine success, an expected refusal, and an unexpected
        exception all leave the instance permanently ``SPENT``. A LATER call
        on an already-``SPENT`` instance refuses fail-closed, using this same
        truthful "no broker was ever attempted" shape: it never builds an
        inert domain, never attempts a second issuance, and never constructs
        or starts a :class:`BrokerServer`.
        """
        state = self._semantic_authority_state
        if state not in _SEMANTIC_AUTHORITY_STATES:
            raise LiveAdapterError(
                "broker creation refused: this adapter's semantic authority "
                "state is not one of the declared states"
            )
        if state == _CATEGORY_B_INERT:
            sed = _build_inert_static_eligibility_domain(
                canonical_root=request.workspace.workspace_root
            )
        elif state == _SEMANTIC_GRANT_SPENT:
            # The one semantic grant this instance ever held was already
            # committed to one attempt (success, expected refusal, or
            # unexpected exception -- all three land here identically). Never
            # fall back to inert mode, never issue a second capability, never
            # construct or start a BrokerServer, never add a registry entry.
            return BrokerCreationObservation(
                session=None, start_attempted=False, resource_created=False
            )
        else:  # state == _SEMANTIC_GRANT_PENDING
            grant = self._semantic_capability_grant
            self._semantic_authority_state = _SEMANTIC_GRANT_SPENT
            self._semantic_capability_grant = None
            try:
                sed = issue_semantic_broker_capability(
                    grant, workspace=request.workspace, run_id=request.run_id
                )
            except WorkspaceAuthorityError:
                return BrokerCreationObservation(
                    session=None, start_attempted=False, resource_created=False
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
        """A ``BrokerServer.start()`` failure. See L1 BLOCKER 1, corrected by
        5F3B-I2B-L1-FU3 BLOCKER 1 once the AR2 D1 dependency landed.

        **The single fact this reads is D1's own public, monotonic
        ``BrokerServer.pipe_resource_created``** -- never ``server.state``,
        never the exception's type or text, and never a private field
        (``_pipe_handle``, ``_thread``, ``_worker_thread_started``). Before
        D1, the frozen public surface could not distinguish "nothing was
        created" from "a pipe exists but no worker owns it": ``state`` reads
        ``STATE_CREATED`` for every pre-READY failure point ``start()`` can
        raise from, so this method conservatively reported
        ``resource_created=True`` and attempted a cleanup for EVERY start
        failure, including one where the pipe creation itself raised. D1
        removed that ambiguity, so the conservative behaviour is no longer
        truthful and is no longer used.

        ``pipe_resource_created is False`` -- ``create_first_instance_pipe``
        raised before returning, or ``start()`` was never reached at all --
        means no broker OS resource ever existed. There is nothing to own
        and nothing to close, so this reports the frozen
        :class:`~qualification.i2b_session.BrokerCreationObservation`
        "nothing created" row exactly (``resource_created=False``,
        ``cleanup_attempted=False``) and calls ``shutdown()`` ZERO times. A
        fake cleanup call issued purely to make the two branches look
        uniform would be an untrue ``cleanup_attempted=True``, so it is not
        made.

        ``pipe_resource_created is True`` means an OS resource was created
        during this ``start()`` call and, because ``start()`` did not
        return, creator ownership never transferred anywhere. This performs
        exactly ONE supported ``server.shutdown(TRIGGER_AIDO_TEARDOWN)``
        -- D1's own no-worker branch closes only the handles
        ``BrokerServer`` itself created and can genuinely reach
        ``STATE_CLOSED``, and its worker-started branch runs the full
        teardown ladder -- and reports the postcondition it actually
        observed. A cleanup that itself raises is caught here so it can
        never erase the primary start failure (BLOCKER 3); it is reported
        as ``reached_closed=False``, an honestly unverified postcondition,
        never a fabricated success.

        The projection is fail-closed in the one direction that matters: a
        value that is not EXACTLY the ``False`` singleton (an unreadable
        attribute, or a non-``bool``, neither of which the frozen D1
        surface can produce) is treated as creator-owned, so the cleanup is
        still attempted rather than skipped.
        """
        if not _broker_reports_pipe_resource_created(server):
            return BrokerCreationObservation(
                session=None,
                start_attempted=True,
                resource_created=False,
                cleanup_attempted=False,
            )
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
        # LF1: projected against the FROZEN ``str | None`` contract, not a
        # bool. See ``_protocol_violation_observed``. This value does NOT
        # feed ``required_flags_accepted`` -- it belongs to the separate,
        # later ``protocol_integrity`` gate, which reads the supervisor's own
        # cumulative (monotonic) state again in ``observe_protocol``. It is
        # read here only to reduce it into the bounded launch diagnostic.
        protocol_violation_observed = _protocol_violation_observed(stdout_state)
        # LF1 OBJECTIVE 4: the corrected required-CLI-flag observation.
        #
        #     required flags accepted  =  no "unknown flag" startup rejection
        #
        # Both halves of the proof chain documented above
        # ``_argv_options_are_source_established`` are required, and neither
        # is a protocol-violation bit:
        #
        #   (a) every option token in the argv AIDO itself constructed is
        #       source-established as recognized by Pi's CLI parser, and
        #   (b) the exact argv was launched and the runtime went on to
        #       consume AIDO's one JSONL RPC command and return a correlated
        #       response -- which Pi cannot reach when any flag was rejected
        #       as unknown, because that path exits before ``runRpcMode``.
        #
        # A launch-window protocol violation alone therefore no longer denies
        # this fact.
        #
        # 5F3B-I2B-L1-LF1-FU1: and neither does a bare correlation failure.
        # The LF1 producer read "no correlated response" as an unknown-flag
        # rejection, which is the unsound REVERSE implication -- a deadline, a
        # launch-window protocol violation, an output cap, an event cap, a
        # read error, and a generic early exit all land there while proving
        # nothing at all about flag acceptance. The classification is now
        # THREE-state, and only its two DEFINITE states may reach the frozen
        # bool.
        argv_options_source_established = _argv_options_are_source_established(argv)
        required_flag_state = _classify_required_flag_evidence(
            argv=argv,
            argv_options_source_established=argv_options_source_established,
            lf_jsonl_correlation_succeeded=lf_jsonl_correlation_succeeded,
            # Deferred, so the ordinary ACCEPTED path never reads raw stderr
            # at all, and an unreadable surface can only ever mean
            # INDETERMINATE.
            stderr_snapshot_reader=lambda: supervisor.stderr_snapshot(),
        )
        required_flags_accepted = required_flag_state == REQUIRED_FLAGS_ACCEPTED
        launch_diagnostic = _launch_diagnostic(
            argv_ok=argv_options_source_established,
            wait_outcome=wait_outcome,
            protocol_violation_observed=protocol_violation_observed,
            required_flags_code=required_flag_state,
        )
        self._launch_diagnostics[request.run_id] = launch_diagnostic

        # -- LF1-FU1: how INDETERMINATE maps into the FROZEN controller -----
        #
        # The frozen ``RuntimeLaunchObservation`` carries one ``bool``, and the
        # frozen controller reads ``required_flags_accepted=False`` on a
        # TRUSTED session as REQUIRED_LAUNCH_FLAGS_REJECTED. There is
        # therefore no truthful session-bearing observation for a launch whose
        # flag evidence is indeterminate: ``True`` would fabricate a proof
        # that was never obtained, and ``False`` would invent a cause more
        # specific than what was observed.
        #
        # So an indeterminate launch fails EARLIER, at this adapter's own
        # runtime-launch boundary, through the existing creator-retained
        # cleanup contract: no session crosses the boundary, the frozen
        # controller fails RUNTIME_LAUNCH itself with RUNTIME_LAUNCH_FAILED
        # (the honest "no trustworthy runtime session was produced"), and
        # REQUIRED_LAUNCH_FLAGS is left NOT_REACHED rather than being told a
        # rejection happened. The frozen controller already sanctions exactly
        # this shape -- see its
        # ``_RUNTIME_LAUNCH_STATUSES_WITH_VALID_OBSERVATION_BUT_OWN_GATE_UNREACHED``,
        # under which a genuinely-consumed observation's four launch facts may
        # each independently be True or False while their own gates never ran.
        #
        # Because of that sanction, the two launch facts this run DID
        # establish are carried through truthfully rather than flattened to
        # False: the launch shape really was valid, and Pi's version really was
        # observed. Neither is read by any gate on this path.
        #
        # This is not chosen to make LF_JSONL_CORRELATION reachable -- it makes
        # it UNREACHABLE for these outcomes. It is chosen because failing
        # closed is truthful and inventing a more specific cause is not.
        if required_flag_state == REQUIRED_FLAGS_INDETERMINATE:
            return self._retain_and_close_partial_runtime(
                supervisor=supervisor,
                extension_dir=extension.extension_dir,
                launch_shape_valid=launch_shape_valid,
                lf_jsonl_correlation_succeeded=lf_jsonl_correlation_succeeded,
                observed_pi_version=identity.reported_version,
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

    def launch_diagnostics(self) -> dict[str, dict[str, str]]:
        """LF1 OBJECTIVE 6: the bounded per-run launch diagnostics.

        Declared codes only (:data:`LAUNCH_DIAGNOSTIC_CODES`). Never raw
        stdout, stderr, an RPC object, an endpoint, an API key, a broker
        token, a pipe name, a capability id, an argv token, an absolute
        workspace path, or a protocol-violation message.
        """
        return {
            run_id: diagnostic.as_dict()
            for run_id, diagnostic in self._launch_diagnostics.items()
        }

    def _retain_and_close_partial_runtime(
        self,
        *,
        supervisor: PiRpcSupervisor,
        extension_dir: str,
        launch_shape_valid: bool = False,
        lf_jsonl_correlation_succeeded: bool = False,
        observed_pi_version: str | None = None,
    ) -> RuntimeLaunchObservation:
        """A real process exists but no trustworthy session can be formed.

        Creator-retained ownership (FU3 Sec. 9.3): exactly one bounded
        self-close, the observed postcondition reported truthfully, and NO
        session handed to the controller. ``extension_dir`` is accepted only
        to keep the call site symmetric with ``o1.handshake``'s own pattern;
        this module does not scrub it here (see the module docstring --
        scrubbing/removal of the disposable tree is the live entry point's
        job, run unconditionally after every outcome).

        **5F3B-I2B-L1-LF1-FU1.** ``launch_shape_valid``,
        ``lf_jsonl_correlation_succeeded`` and ``observed_pi_version`` default
        to the conservative "nothing was established" values that every
        PRE-EXISTING caller of this method genuinely observed: those callers
        arrive from a raised ``launch()``, a raised send/await, or an
        unconstructible session, none of which ever obtained a recognized
        ``await_response`` outcome or reached a point where a version could be
        reported for this launch. The INDETERMINATE-flag caller added by FU1
        DID establish them and passes them through, so a fail-closed mapping
        never has to flatten a fact it actually observed -- notably, an
        indeterminate launch in which the LF-framed JSONL correlation really
        did succeed still reports that truthfully. None of them is read by any
        gate on this path: with no session, the frozen controller fails
        RUNTIME_LAUNCH itself and leaves all four launch-fact gates
        NOT_REACHED (its own
        ``_RUNTIME_LAUNCH_STATUSES_WITH_VALID_OBSERVATION_BUT_OWN_GATE_UNREACHED``
        is what sanctions each fact standing independently there).

        ``required_flags_accepted`` is ALWAYS ``False`` here and is
        deliberately NOT a parameter. With no session there is no gate to
        interpret it, so ``False`` means "not established by this launch" and
        never "rejected". The one state that does mean rejection keeps its
        session and is reported through the ordinary path above, where the
        frozen controller can name it exactly.
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
            launch_shape_valid=launch_shape_valid,
            required_flags_accepted=False,
            lf_jsonl_correlation_succeeded=lf_jsonl_correlation_succeeded,
            observed_pi_version=observed_pi_version,
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
        ``protocol_violation`` value outside the frozen ``str | None``
        contract, or an ``extension_errors`` collection that is not exactly a
        ``list``, fails CLOSED -- treated as an observed violation/error --
        rather than being coerced.

        **LF1 OBJECTIVE 5: a launch-window protocol violation must still be
        visible HERE.** Correcting ``required_flags_accepted`` must not make
        the violation disappear, and it does not: the frozen
        ``ar2.protocol.RecordStreamReader.protocol_violation`` field is
        MONOTONIC -- it is assigned exactly once, at the point of detection,
        and the reader thread then returns, so nothing ever clears it or
        overwrites it with ``None``. ``PiRpcSupervisor.stdout_state()``
        republishes that same live reader field on every call, so this method
        reads the supervisor's CUMULATIVE state, not a launch-window
        snapshot. A violation observed during the launch window is therefore
        still reported at ``protocol_integrity`` time, and a corrected run
        can truthfully produce ``required_launch_flags = PASSED`` alongside
        ``protocol_integrity = FAILED:PROTOCOL_VIOLATION_OBSERVED``.
        """
        record = self._require_runtime_record(session)
        stdout_state = record.supervisor.stdout_state()
        protocol_violation_observed = _protocol_violation_observed(stdout_state)
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


def build_semantic_task_live_adapters(
    *,
    environ_reader: Any,
    runtime_identity: IssuedRuntimeIdentity,
    capability_grant: Any,
) -> LiveCategoryBAdapters:
    """The ONE narrow construction path under which ``create_broker`` issues a
    genuine capability (5F3B-LIVE1-C1).

    Returns an object whose ``type(...) is LiveCategoryBAdapters`` -- exactly,
    not a subclass -- so the frozen
    :class:`AuthenticatedB300RouteObserver`'s exact-type route authority is
    unchanged and unweakened, and every accepted Category-B behaviour of the
    returned object is the accepted one.

    ``capability_grant`` must be an opaque
    :class:`~qualification.i2b_workspace.SemanticCapabilityGrant`, which only
    ``qualification.i2b_workspace`` can mint and only for a task that IS one
    of the frozen corpus singletons. It carries no manifest, no protected
    set, no witness set, no root, no capability id, no domain, and no
    callable -- every authority fact is derived at consumption, inside the
    issuing module, from AIDO's own observation of the verified workspace.

    **This is not an authority switch.** There is no ``semantic=True``, no
    ``real_capability=``, no ``enable_writes=``, no ``capability_source=`` and
    no domain parameter anywhere; the distinction is carried mechanically by
    an object a caller cannot construct. Category-B construction remains the
    plain :class:`LiveCategoryBAdapters` constructor, whose signature is
    unchanged and whose default capability is unchanged.
    """
    if type(capability_grant) is not SemanticCapabilityGrant:
        raise LiveAdapterError(
            "semantic broker capability refused: this construction path "
            "requires a grant minted by qualification.i2b_workspace's own "
            "issuance boundary; no caller-constructed value can authorize one"
        )
    adapters = LiveCategoryBAdapters(
        environ_reader=environ_reader, runtime_identity=runtime_identity
    )
    adapters._semantic_capability_grant = capability_grant
    # 5F3B-LIVE1-C1-FU2: the ONE place a fresh instance may enter
    # SEMANTIC_GRANT_PENDING -- after the grant above has already been
    # validated as a genuine SemanticCapabilityGrant. create_broker owns the
    # only further transition (PENDING -> SPENT), and it is irreversible.
    adapters._semantic_authority_state = _SEMANTIC_GRANT_PENDING
    return adapters


class AuthenticatedB300RouteObserver:
    """The live route checker (5F3B-I2B-L1-LF2). Same-run authority, or nothing.

    Replaces the unauthenticated ``ar2.route_check.check_route_serves_model``
    that frozen I2A Sec. 15 item 9 mandated. It presents the SAME call shape
    the frozen controller and
    :func:`qualification.i2_route.run_offline_route_check` already expect --
    ``checker(base_url, model_id=...)`` returning an object with exact-``bool``
    ``.reachable`` / ``.configured_model_served`` -- so neither of those is
    reopened, modified, or wrapped.

    **Its authority is not its arguments.** The base URL and the credential
    come from the ``ConnectionValues`` the frozen controller already consumed
    on this run, read back from the adapter instance; the model id comes from
    the frozen I1 candidate pairing for the candidate this observer was built
    for. The arguments it receives are treated as claims to be CHECKED against
    that authority, never as instructions:

    - a ``base_url`` that is not byte-identical to the consumed one is
      refused (substituted route);
    - a ``model_id`` that is not exactly the frozen pairing's id for this
      candidate is refused (substituted model, and specifically a Candidate-B
      model id offered during a Candidate-A run);
    - a call made before the controller's credential read is refused (there is
      no authority to derive yet);
    - a SECOND call is refused outright, so one Category-B run issues exactly
      one non-inference GET.

    There is deliberately no parameter anywhere on this class for a base URL,
    an API key, a provider id, an endpoint, or a model id. None can be
    supplied at the live adapter boundary at all.

    **LF2-FU1 BLOCKER 1: no transport/client/request-injection parameter
    either.** An earlier revision accepted a public ``transport=`` keyword
    "for offline testing" and forwarded it into
    :func:`observe_b300_route_serves_model`. That is a public substitution
    point for the live observation channel itself: a caller could construct a
    genuine same-run observer while injecting an ``httpx.MockTransport`` that
    fabricates ``HTTP 200`` / model-present evidence without ever contacting
    B300, and every logical authority check above would still pass. Calling
    the parameter "test-only" in a comment was never an enforcement of that.
    This constructor now accepts **exactly** ``candidate`` and ``adapters`` --
    no ``transport``, ``client``, ``requester``, ``sender``, ``session``,
    ``http_client`` or ``request_callback`` parameter under any name -- so the
    production observer always calls the real mechanism function with its
    normal live transport. Offline tests inject a synthetic transport at a
    PRIVATE substitution point instead: by monkeypatching the module-internal
    ``observe_b300_route_serves_model`` name this class calls, which is not
    reachable through this public constructor or through
    :func:`build_authenticated_route_checker`.

    **LF2-FU1 BLOCKER 2: the adapter authority check is exact-type, not
    ``isinstance``.** ``isinstance(adapters, LiveCategoryBAdapters)`` is true
    for any subclass, including one whose ``__init__`` never runs the real
    constructor and whose ``consumed_connection_values`` is overridden to
    return attacker-selected values -- deriving route authority from an
    object the frozen controller never actually consumed. The check below is
    ``type(adapters) is LiveCategoryBAdapters`` -- the exact live adapter
    type, and nothing a subclass can satisfy by inheritance alone.

    Every refusal raises :class:`LiveAdapterError`, which
    ``run_offline_route_check`` already reduces to its bounded
    ``ROUTE_CHECK_ERROR`` without reading the exception text -- and the
    observer records :data:`ROUTE_AUTHORITY_REFUSED` first, so the L1 harness
    can still attribute the refusal truthfully.
    """

    def __init__(
        self,
        *,
        candidate: str,
        adapters: LiveCategoryBAdapters,
    ) -> None:
        if type(adapters) is not LiveCategoryBAdapters:
            raise LiveAdapterError(
                "route observer refused: the live adapter instance for this run "
                "is required as the authority source"
            )
        # ``route_descriptor_for_candidate`` is the frozen, already-accepted
        # pairing: it refuses an unknown candidate and cannot be talked into
        # an arbitrary model id, provider id, gateway class, or credential
        # carrier. The observer derives the model id here rather than
        # accepting one.
        self._descriptor = route_descriptor_for_candidate(candidate)
        self._candidate = self._descriptor.candidate
        self._adapters = adapters
        self._diagnostic_code: str = ROUTE_NOT_OBSERVED
        self._observations = 0

    @property
    def candidate(self) -> str:
        """The candidate this observer is bound to. Read by the L1 harness."""
        return self._candidate

    def _refuse(self, message: str) -> LiveAdapterError:
        self._diagnostic_code = ROUTE_AUTHORITY_REFUSED
        return LiveAdapterError(message)

    def __call__(self, base_url: str, *, model_id: str) -> B300RouteObservation:
        if self._observations:
            raise self._refuse(
                "route observation refused: one Category-B run issues exactly "
                "one non-inference model-listing request"
            )

        values = self._adapters.consumed_connection_values()
        if values is None:
            raise self._refuse(
                "route observation refused: this run has not consumed its B300 "
                "connection values, so there is no route authority to derive"
            )
        if type(base_url) is not str or base_url != values.base_url:
            # Never echoes either URL.
            raise self._refuse(
                "route observation refused: the requested base URL is not the "
                "one this run consumed"
            )
        if type(model_id) is not str or model_id != self._descriptor.model_id:
            # Never echoes either model id.
            raise self._refuse(
                "route observation refused: the requested model id is not the "
                "frozen pairing's id for this run's candidate"
            )

        self._observations += 1
        # No ``transport=`` forwarded: this class no longer accepts one from
        # a caller at all (LF2-FU1 BLOCKER 1), so the real mechanism function
        # always opens its own live ``httpx`` transport here.
        observation = observe_b300_route_serves_model(
            base_url=values.base_url,
            api_key=values.api_key,
            model_id=self._descriptor.model_id,
        )
        self._diagnostic_code = observation.diagnostic_code
        return observation

    def route_diagnostics(self) -> dict[str, str]:
        """LF2 OBJECTIVE 5: the bounded route diagnostic, for the L1 artifact.

        Declared codes only (:data:`ROUTE_DIAGNOSTIC_CODES`). Never a status
        code, a served-model-id list, a response body, an endpoint, a host, a
        base URL, a credential, or exception text. Defaults to
        ``route_not_observed``, which is what an earlier gate failing first
        truthfully leaves behind.

        This is **attribution, not verdict authority**: the frozen controller
        still owns ``ROUTE_CHECK_FAILED`` and
        ``exact_candidate_model_served``, and this record never contradicts,
        overrides, or softens either.
        """
        if self._diagnostic_code not in ROUTE_DIAGNOSTIC_CODES:  # pragma: no cover
            raise LiveAdapterError(
                "route diagnostic refused: the recorded code is not a declared code"
            )
        return {
            "candidate": self._candidate,
            "route_observation": self._diagnostic_code,
            "observation_requests_issued": str(self._observations),
        }


def build_authenticated_route_checker(
    *,
    candidate: str,
    adapters: LiveCategoryBAdapters,
) -> AuthenticatedB300RouteObserver:
    """The ONE live route checker factory. No endpoint or credential parameter.

    The live entry point passes the result as ``run_category_b_controller``'s
    ``route_checker`` argument. ``candidate`` must be the same candidate that
    run is for; if it ever is not, the observer refuses at call time rather
    than observing the wrong route, because the model id the frozen controller
    passes will not match the frozen pairing this observer derived.
    """
    return AuthenticatedB300RouteObserver(candidate=candidate, adapters=adapters)
