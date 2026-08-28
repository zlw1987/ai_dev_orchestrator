"""I2B -- run-scoped Category-B resource authority and bounded live observations.

**OFFLINE ONLY. This module launches nothing, opens no socket, calls no
model, and reads no credential.** It contains no ``subprocess``, ``socket``,
``http``, ``urllib`` or ``os.environ`` primitive; it is value objects plus
their valid-by-construction rules. A source-level regression test in this
package's offline suite enforces that mechanically.

The one filesystem-touching exception is deliberate and required by design
FU3 Sec. 8.3: the two run-scoped REQUEST objects re-verify their
:class:`~qualification.i2b_workspace.QualificationRunWorkspace` against the
filesystem at construction, because a consumption boundary must re-prove
authority rather than trust a previous validation. That verification lives
in :mod:`qualification.i2b_workspace`; nothing here reads or writes a file
itself.

Why this module exists (5F3B-I2B-FU1)
-------------------------------------

The first I2B controller represented every future live operation as an
UNRELATED no-argument callback -- ``h1_check()``, ``get_state()``,
``broker_ready()``, ``teardown()``. Each could return a perfectly valid
result, and nothing anywhere established that those four results described
**the same runtime**. This module supplies the narrow, I2B-OWNED authority
shape that closes that. It is deliberately **not** a generic
``AgentRuntime`` / ``RuntimeAdapter`` framework: there is no registry, no
plugin system, no lifecycle base class, no capability negotiation, no
reusable transport, and no interface a second runtime could be registered
against.

What 5F3B-I2B-FU2 corrected here
--------------------------------

**1. H1 is no longer a caller-supplied verdict (design FU3 Sec. 6).**
``GetCommandsObservation.extension_identity_matched: bool`` was a single
boolean AIDO recorded without deriving anything -- nothing established that
it came from the frozen rule rather than from an adapter computing
something weaker (for instance the pre-AR1-FU1 gate that a same-named
command merely *existed*). The observation now carries the frozen
evaluator's own five COMPONENTS plus two bounded origin tokens, and AIDO
derives the verdict itself in :attr:`GetCommandsObservation.h1_identity_established`.
:func:`h1_components_from_frozen_evaluation` is the fixed projection a
future live adapter must use, and the offline suite proves it agrees with
the frozen, unmodified ``ar2.handshakes.evaluate_extension_identity`` over
an adversarial corpus.

**2. ``get_commands`` enumerates SLASH COMMANDS, not the tool registry
(design FU3 Sec. 5).** The old ``ObservedCommand`` recorded ``source`` while
documenting it as "deliberately NOT part of the rule", because I2A Sec. 15
item 6 defined a gate over "exactly ``aido_read``/``aido_edit``, nothing
else". That sentence is superseded: it is both unprovable (Pi exposes no
RPC command that enumerates the active tool registry) and unsatisfiable
(``aido_read``/``aido_edit`` are registered with ``pi.registerTool`` while
``get_commands`` reports ``pi.registerCommand`` slash commands, so those two
names can never appear in a response at all). ``ObservedCommand`` now
carries the reported PROVENANCE -- whether a ``sourceInfo`` object was
present, whether it was well formed, and its bounded origin kind -- so the
corrected gate can partition top-level-``"extension"``-sourced entries into
the one AIDO ``"cli"`` entry, Pi's own ``"inline"`` entries, and anything
else (which fails closed).

**3. The creator partial-failure contract (design FU3 Sec. 9.3, as
corrected by FU3A/FU3B/FU3C).** ``RuntimeLaunchObservation`` previously
carried one collapsed ``partial_resource_cleaned_internally`` flag and made
one physically real state -- a resource created and the creator failing
before it could even invoke its own cleanup -- unconstructible. Both
observations now carry three orthogonal facts (``resource_created``,
``cleanup_attempted``, and ONE resource-kind-specific observed
postcondition) and no generic verdict field at all. **The creator can never
supply ``cleanup_verified_success``**: it is a read-only property AIDO's own
code derives, identically for both kinds, as
``cleanup_attempted and (postcondition is True)`` -- never bare Python
truthiness, and never a "the close call did not raise" shortcut. No handle
of any kind crosses into the controller for a partial failure, so there is
no partial-handle provenance to forge and structurally only one possible
caller of a close primitive per branch.

**4. Workspace authority is an object minted by qualification machinery,
never a caller string (design FU3 Sec. 8).** ``BrokerCreationRequest`` and
``RuntimeLaunchRequest`` took ``workspace_root: str``, validated only as
non-blank. They now take the one
:class:`~qualification.i2b_workspace.QualificationRunWorkspace` the run
minted, re-verify it against the filesystem, and require it to be claimed by
exactly this run.

The binding is MECHANICAL, not conventional
-------------------------------------------

1. The controller mints one per-run ``run_id`` nonce that no adapter
   supplies. :class:`BrokerSession` must carry that exact value back, or the
   broker is refused before any launch-capable continuation.
2. :class:`RuntimeLaunchRequest` can only be CONSTRUCTED from a
   :class:`BrokerSession` that already carries the matching ``run_id`` and
   has ``reached_ready is True``. Frozen O1's observed lifecycle starts the
   broker and reaches ``READY`` *before* Pi is launched, because the launch
   writes the broker binding into the disposable extension. That ordering is
   therefore not a convention here -- a launch request for a not-ready or
   foreign broker is unconstructible.
3. Every post-launch observation carries the ``runtime_session_id`` it was
   produced from. The controller compares it against the session the launch
   actually returned, so an observation belonging to a different runtime is
   refused rather than silently accepted.
4. Both run-scoped requests re-verify the run's synthetic workspace and
   require it to be claimed by this exact ``run_id``.

**What the ``run_id`` nonce is, exactly.** It is a CORRELATION control, not
an authentication control. It proves that the broker session, the runtime
session and every observation the controller consumed belong to ONE
invocation -- catching a stale handle, a leftover session from a previous
run, or an object assembled for a different run. It does NOT authenticate
the adapter, which necessarily receives the nonce in order to echo it. An
adapter is AIDO's own future live code, inside the trust boundary; never
write that this nonce defends against a hostile adapter.

Bounded by construction
-----------------------

**No free-text field exists anywhere in this module.** Every string that
originates outside AIDO -- an observed Pi version, a reported provider or
model id, a command name, a reported origin kind -- is charset- and
length-bounded at construction, so raw stdout, stderr, an RPC body, a
traceback, an endpoint URL, an absolute path, or a provider exception
message cannot be smuggled into a retained observation in the first place.
Rejection raises :class:`ObservationError`; the controller reduces that to
one bounded failure code and never reads the exception's text.

Truthful claim scope
--------------------

:class:`RuntimeShutdownObservation` reports only what AIDO's own shutdown
call returned and whether AIDO's own DIRECT child was reported to have
exited; :class:`BrokerShutdownObservation` reports only the broker
lifecycle's own terminal state. The same scope applies identically to the
creator's own observed postcondition on the partial-failure path. Nothing
here is, or may ever be read as, a claim that a descendant process was
terminated, that Pi/provider inference stopped, or that GPU work stopped.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .i2b_workspace import (
    QualificationRunWorkspace,
    WorkspaceAuthorityError,
    run_workspace_is_claimed_by,
    verify_run_workspace,
)


class ObservationError(ValueError):
    """A run-authority or live-observation value object is invalid. Fails closed.

    Deliberately a ``ValueError`` subclass so a caller that already treats an
    invalid value object as a construction error keeps doing so. The
    controller catches it and reduces it to one bounded failure code --
    ``str()``/``repr()`` of this exception is never retained in evidence.
    """


#: An AIDO- or adapter-minted correlation identifier. Bounded so an id can
#: never carry a URL, a path, a credential, or a diagnostic sentence.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

#: A runtime-reported command name. Bounded for the same reason.
_COMMAND_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

#: A runtime-reported command SOURCE, or a ``sourceInfo.source`` origin kind.
#: Deliberately narrower than a command name: these are short origin tokens
#: (``"extension"``, ``"cli"``, ``"inline"``, a Pi built-in kind), never a
#: path and never a sentence.
_ORIGIN_KIND_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

#: A runtime-reported version string. Bounded and RETAINED as evidence
#: provenance, which is exactly why it may not be arbitrary runtime text.
_VERSION_PATTERN = re.compile(r"^[0-9][0-9A-Za-z.+_-]{0,31}$")

#: A provider/model identity string echoed back by the runtime.
_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9_.:/-]{1,128}$")

#: A broker binding secret (token/capability id/pipe name). Deliberately not
#: charset-bounded (a Windows pipe name is all backslashes), only
#: length-bounded and required non-blank. Never rendered, never retained.
_MAX_BINDING_LENGTH = 512

#: An upper bound on how many command entries one ``get_commands`` response
#: may report. A real response is tiny -- AR1's, AR2's and O1's real captured
#: live runs all reported exactly two commands -- so this only refuses an
#: unbounded runtime-supplied list rather than holding it in memory.
_MAX_REPORTED_COMMANDS = 256

#: The top-level ``source`` value that selects the extension-sourced subset
#: of a ``get_commands`` response. This is the SAME computation frozen AR2
#: and O1 already use for ``extension_command_count``
#: (``sum(1 for c in commands if c.get("source") == "extension")``) -- reused
#: as a VALUE, never imported, per this package's established precedent.
#:
#: **Both** AIDO's own sentinel and Pi's own inline ``llama`` command report
#: this same top-level value; it is therefore a SELECTOR, never a
#: discriminator. The discriminator is ``sourceInfo.source`` below.
EXTENSION_COMMAND_SOURCE = "extension"

#: ``sourceInfo.source`` for a command that came from an explicitly
#: CLI-loaded ``--extension`` extension -- AIDO's own. There must be exactly
#: one of these, and it must be the H1-validated sentinel.
CLI_EXTENSION_ORIGIN_KIND = "cli"

#: The sentinel COMMAND name AIDO's own extension registers with
#: ``pi.registerCommand``. Duplicated as a VALUE from
#: ``ar2.pi_config.SENTINEL_COMMAND_NAME`` -- never imported -- per this
#: package's established precedent; an offline test asserts the two agree.
#:
#: **This is AIDO's own bytes, not an observation.** Requiring
#: :attr:`GetCommandsObservation.sentinel_command_name` to equal it exactly
#: means an adapter cannot nominate some OTHER reported command as "the
#: sentinel" and have both H1 and the namespace partition evaluated against
#: that nomination -- exactly the way ``expected_source_kind`` is pinned.
CATEGORY_B_SENTINEL_COMMAND_NAME = "aido_ar2_broker_active"

#: ``sourceInfo.source`` for a command Pi ships itself (observed live:
#: ``llama``, path ``<inline:llama.cpp>``). Tolerated without further
#: constraint on name, path or count -- Pi's own catalog is not this gate's
#: business, and a Pi upgrade adding or removing one must not need the gate
#: to change.
INLINE_EXTENSION_ORIGIN_KIND = "inline"


def require_exact_bool(field_name: str, value: Any) -> bool:
    """Require exactly ``bool`` -- never a truthy/falsy stand-in.

    The same rule ``i2_credentials.PreflightGateResult`` and
    ``i2_route.RouteCheckOutcome`` already enforce: ``"false"``, ``1`` and
    ``0`` are refused outright rather than coerced.
    """
    if type(value) is not bool:
        raise ObservationError(
            f"{field_name} must be exactly a bool (no truthy/falsy coercion); "
            f"got {type(value).__name__}"
        )
    return value


def _require_pattern(field_name: str, value: Any, pattern: "re.Pattern[str]") -> str:
    if not isinstance(value, str):
        raise ObservationError(f"{field_name} must be a str; got {type(value).__name__}")
    if not pattern.fullmatch(value):
        raise ObservationError(
            f"{field_name} is not a bounded, well-formed value for this field; "
            "arbitrary runtime text is refused (the offending value is never echoed)"
        )
    return value


def _require_binding_secret(field_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ObservationError(f"{field_name} must be a str; got {type(value).__name__}")
    if not value or not value.strip():
        raise ObservationError(f"{field_name} must be non-blank")
    if len(value) > _MAX_BINDING_LENGTH:
        raise ObservationError(f"{field_name} exceeds the bounded binding length")
    return value


def _require_run_workspace(field_name: str, workspace: Any, *, run_id: str) -> None:
    """Re-verify the run's synthetic workspace AT THIS CONSUMPTION BOUNDARY.

    Design FU3 Sec. 8.3: authority is re-proved against the filesystem here,
    never inherited from an earlier validation, and the workspace must be
    claimed by exactly this ``run_id``. Relocation, marker tampering,
    substitution and cross-run reuse all fail closed.
    """
    if type(workspace) is not QualificationRunWorkspace:
        raise ObservationError(
            f"{field_name} must be a QualificationRunWorkspace minted by "
            "qualification.i2b_workspace; an arbitrary path is not authority"
        )
    try:
        verify_run_workspace(workspace)
    except WorkspaceAuthorityError as exc:
        raise ObservationError(
            f"{field_name} could not be re-verified at this consumption "
            f"boundary: {exc.reason_code}"
        ) from None
    if not run_workspace_is_claimed_by(workspace, run_id=run_id):
        raise ObservationError(
            f"{field_name} is not claimed by this run; a workspace belonging to "
            "another run (or to no run) is refused"
        )


# -- broker authority ---------------------------------------------------------


@dataclass(frozen=True)
class BrokerCreationRequest:
    """What AIDO hands its broker-creation adapter. AIDO-authored only.

    Carries the per-run ``run_id`` nonce the returned :class:`BrokerSession`
    must echo back, plus the run's ONE verified synthetic workspace, which
    the broker's capability is scoped to. There is no adapter-chosen field
    here at all, and no path string: the workspace is the object
    :mod:`qualification.i2b_workspace` minted by CREATING it, re-verified
    here rather than trusted.
    """

    run_id: str
    workspace: QualificationRunWorkspace = field(repr=False)

    def __post_init__(self) -> None:
        _require_pattern("BrokerCreationRequest.run_id", self.run_id, _ID_PATTERN)
        _require_run_workspace(
            "BrokerCreationRequest.workspace", self.workspace, run_id=self.run_id
        )

    @property
    def workspace_root(self) -> str:
        """The verified workspace root the broker capability is scoped to."""
        return self.workspace.workspace_root

    def __repr__(self) -> str:  # noqa: D105 - workspace path is never rendered
        return f"{type(self).__name__}(run_id={self.run_id!r}, workspace=<bound>)"


@dataclass(frozen=True)
class BrokerSession:
    """The run-scoped broker resource AIDO created, and its binding.

    ``pipe_name``/``capability_id``/``broker_token`` are the RUN-SENSITIVE
    values frozen AR2/O1 mint per run. They are held here for exactly two
    reasons, both mechanical:

    1. :class:`RuntimeLaunchRequest` consumes them -- the launch genuinely
       needs the binding, because frozen O1 writes it into the disposable
       extension before Pi starts;
    2. the controller declares all three to
       ``qualification.safety.ArtifactSafetyContext`` so the evidence scrub
       can refuse an artifact that leaked any of them. They are never
       rendered, never placed in evidence, and every one is
       ``field(repr=False)`` behind a bounded ``__repr__``.

    ``reached_ready`` is the adapter's OWN observation of the broker's
    ``READY`` state; the controller gates on it and never infers it.
    """

    run_id: str
    session_id: str
    pipe_name: str = field(repr=False)
    capability_id: str = field(repr=False)
    broker_token: str = field(repr=False)
    reached_ready: bool = False

    def __post_init__(self) -> None:
        _require_pattern("BrokerSession.run_id", self.run_id, _ID_PATTERN)
        _require_pattern("BrokerSession.session_id", self.session_id, _ID_PATTERN)
        _require_binding_secret("BrokerSession.pipe_name", self.pipe_name)
        _require_binding_secret("BrokerSession.capability_id", self.capability_id)
        _require_binding_secret("BrokerSession.broker_token", self.broker_token)
        require_exact_bool("BrokerSession.reached_ready", self.reached_ready)

    def __repr__(self) -> str:  # noqa: D105 - see class docstring
        return (
            f"{type(self).__name__}(run_id={self.run_id!r}, "
            f"session_id={self.session_id!r}, reached_ready={self.reached_ready!r}, "
            "pipe_name=<bound>, capability_id=<bound>, broker_token=<bound>)"
        )


@dataclass(frozen=True)
class BrokerCreationObservation:
    """The bounded result of ONE broker creation attempt (design FU3 Sec. 9.3).

    Replaces I2B-FU1's bare ``BrokerSession`` return type, which had no
    failure-carrying shape at all -- the broker side was missing the runtime
    side's partial-resource accounting entirely.

    **Exactly four constructible states, and no fifth:**

    ==============  =================  ==================  ================
    ``session``     ``resource_...``   ``cleanup_atte...`` ``reached_closed``
    ==============  =================  ==================  ================
    not ``None``    forced ``True``    forced ``False``    forced ``None``
    ``None``        ``False``          forced ``False``    forced ``None``
    ``None``        ``True``           ``True``            exact ``bool``
    ``None``        ``True``           ``False``           forced ``None``
    ==============  =================  ==================  ================

    Row 1 transfers ownership to the controller (its unchanged, Sec. 9.4-gated
    ``shutdown_broker`` applies later). Row 2 is "nothing created". Row 3 is
    "the creator retained ownership and attempted exactly one bounded
    self-close". Row 4 is ``PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`` --
    a resource created and the creator failing or being interrupted before it
    could invoke its own cleanup primitive. In rows 3 and 4 the controller has
    **no partial-close callable at all**, so a second close can never occur,
    and no repeat-close-safety assumption is ever required.

    ``start_attempted`` is the broker's own independent creation-failure fact
    -- whether the underlying start call was even reached -- mirroring the
    runtime side's existing granularity. It is recorded ALONGSIDE the cleanup
    facts and is never overwritten or masked by them.

    **``cleanup_verified_success`` is NOT a constructor field.** It is a
    read-only property AIDO derives; see the property's own docstring.
    """

    session: BrokerSession | None
    start_attempted: bool
    resource_created: bool
    cleanup_attempted: bool = False
    reached_closed: bool | None = None

    def __post_init__(self) -> None:
        if self.session is not None and type(self.session) is not BrokerSession:
            raise ObservationError(
                "BrokerCreationObservation.session must be a BrokerSession or None"
            )
        require_exact_bool("BrokerCreationObservation.start_attempted", self.start_attempted)
        require_exact_bool("BrokerCreationObservation.resource_created", self.resource_created)
        require_exact_bool("BrokerCreationObservation.cleanup_attempted", self.cleanup_attempted)
        _validate_creator_cleanup_facts(
            type_name="BrokerCreationObservation",
            postcondition_name="reached_closed",
            session_present=self.session is not None,
            resource_created=self.resource_created,
            cleanup_attempted=self.cleanup_attempted,
            postcondition=self.reached_closed,
        )
        if self.session is not None and not self.start_attempted:
            raise ObservationError(
                "BrokerCreationObservation: a returned broker session requires that "
                "the start call was attempted"
            )

    @property
    def cleanup_verified_success(self) -> bool:
        """AIDO's OWN derivation. Never a creator-supplied verdict (FU3C).

        ``cleanup_attempted and (reached_closed is True)`` -- identity
        against the ``True`` singleton, never bare Python truthiness and
        never a "the close call returned without raising" shortcut. The
        creator supplies only the narrow observed postcondition
        ``reached_closed``: the broker lifecycle reaching ``STATE_CLOSED``,
        exactly the same fact :class:`BrokerShutdownObservation` reports for
        an ordinary teardown. ``STATE_TEARDOWN_INCOMPLETE`` is not verified
        closure.
        """
        return self.cleanup_attempted and (self.reached_closed is True)


@dataclass(frozen=True)
class BrokerShutdownObservation:
    """What AIDO's own broker-shutdown call reported, for ONE broker session.

    ``reached_closed`` is the broker lifecycle's own terminal state, exactly
    as frozen AR2's ``BrokerServer.shutdown()`` reports it -- it reaches
    ``STATE_CLOSED`` only when worker termination was observed, and reports
    ``STATE_TEARDOWN_INCOMPLETE`` otherwise. This object never claims a
    runtime process, a descendant, or backend inference stopped.
    """

    session_id: str
    reached_closed: bool

    def __post_init__(self) -> None:
        _require_pattern("BrokerShutdownObservation.session_id", self.session_id, _ID_PATTERN)
        require_exact_bool("BrokerShutdownObservation.reached_closed", self.reached_closed)


def _validate_creator_cleanup_facts(
    *,
    type_name: str,
    postcondition_name: str,
    session_present: bool,
    resource_created: bool,
    cleanup_attempted: bool,
    postcondition: Any,
) -> None:
    """The ONE shared creator-cleanup rule, for both resource kinds.

    Written once so the runtime and broker contracts cannot silently diverge
    in what "attempted" and "verified" mean (design FU3 Sec. 9.3/9.3.1).
    """
    if session_present:
        if resource_created is not True:
            raise ObservationError(
                f"{type_name}: a returned session means a resource WAS created"
            )
        if cleanup_attempted is not False:
            raise ObservationError(
                f"{type_name}: a creator that hands back a live trusted session "
                "cannot also claim it attempted to close it"
            )
    elif cleanup_attempted and not resource_created:
        raise ObservationError(
            f"{type_name}: cleanup cannot have been attempted for a resource that "
            "was never created"
        )

    if cleanup_attempted:
        if type(postcondition) is not bool:
            raise ObservationError(
                f"{type_name}.{postcondition_name} must be exactly a bool when "
                "cleanup_attempted is True -- a creator that attempted its one "
                "bounded close must report a definite observed postcondition, "
                "never None and never a truthy/falsy stand-in"
            )
    elif postcondition is not None:
        raise ObservationError(
            f"{type_name}.{postcondition_name} must be None when cleanup_attempted "
            "is False -- no close was attempted, so no postcondition was observed"
        )


# -- runtime authority --------------------------------------------------------


@dataclass(frozen=True)
class RuntimeSession:
    """The handle proving WHICH runtime instance an observation belongs to.

    Every field is a correlation identifier -- there is no process handle, no
    pipe, no file descriptor and no callable here. ``broker_session_id`` is
    what makes a runtime session inseparable from the broker it was launched
    against.
    """

    run_id: str
    broker_session_id: str
    runtime_session_id: str

    def __post_init__(self) -> None:
        _require_pattern("RuntimeSession.run_id", self.run_id, _ID_PATTERN)
        _require_pattern("RuntimeSession.broker_session_id", self.broker_session_id, _ID_PATTERN)
        _require_pattern(
            "RuntimeSession.runtime_session_id", self.runtime_session_id, _ID_PATTERN
        )


@dataclass(frozen=True)
class RuntimeLaunchRequest:
    """Everything the future Node-direct RPC launch consumes, bound to ONE run.

    **Unconstructible for the wrong broker.** ``__post_init__`` requires
    ``broker_session.run_id == run_id`` and ``broker_session.reached_ready is
    True``. Frozen O1's observed lifecycle reaches broker ``READY`` before Pi
    is launched; here that ordering is enforced by the type, so a controller
    (or a future live adapter) cannot express "launch first, broker ready
    later" at all.

    **Unconstructible for the wrong workspace.** ``workspace`` is the run's
    ONE minted :class:`~qualification.i2b_workspace.QualificationRunWorkspace`,
    re-verified against the filesystem here and required to be claimed by
    this exact ``run_id`` -- the same object, verified the same way,
    :class:`BrokerCreationRequest` was constructed from.

    ``launch_environment`` is the already-accepted, immutable I2-1
    ``LaunchEnvironment``; ``model_id``/``provider_id`` come from the run's
    already-validated route descriptor. There is no raw ``api_key``,
    ``base_url``, ``config_dir`` or argv parameter here -- the credential
    reaches the child only through the accepted child-environment carrier.
    """

    run_id: str
    broker_session: BrokerSession
    launch_environment: Any
    workspace: QualificationRunWorkspace = field(repr=False)
    provider_id: str = ""
    model_id: str = ""

    def __post_init__(self) -> None:
        _require_pattern("RuntimeLaunchRequest.run_id", self.run_id, _ID_PATTERN)
        if not isinstance(self.broker_session, BrokerSession):
            raise ObservationError("RuntimeLaunchRequest.broker_session must be a BrokerSession")
        if self.broker_session.run_id != self.run_id:
            raise ObservationError(
                "RuntimeLaunchRequest: the broker session belongs to a different run"
            )
        if self.broker_session.reached_ready is not True:
            raise ObservationError(
                "RuntimeLaunchRequest: the broker session has not reached READY; "
                "frozen O1 requires broker readiness BEFORE the runtime launch"
            )
        # Checked structurally rather than by isinstance: importing
        # i2_environment here would create an import cycle. The workspace, by
        # contrast, is authority-bearing and is checked by EXACT TYPE.
        if not hasattr(self.launch_environment, "as_launch_snapshot"):
            raise ObservationError(
                "RuntimeLaunchRequest.launch_environment must be the accepted I2 "
                "LaunchEnvironment (no as_launch_snapshot boundary found)"
            )
        _require_run_workspace(
            "RuntimeLaunchRequest.workspace", self.workspace, run_id=self.run_id
        )
        _require_pattern("RuntimeLaunchRequest.provider_id", self.provider_id, _IDENTITY_PATTERN)
        _require_pattern("RuntimeLaunchRequest.model_id", self.model_id, _IDENTITY_PATTERN)

    @property
    def workspace_root(self) -> str:
        """The verified workspace root the runtime is launched against."""
        return self.workspace.workspace_root

    def __repr__(self) -> str:  # noqa: D105 - workspace path is never rendered
        return (
            f"{type(self).__name__}(run_id={self.run_id!r}, "
            f"broker_session_id={self.broker_session.session_id!r}, "
            f"provider_id={self.provider_id!r}, model_id={self.model_id!r}, "
            "workspace=<bound>)"
        )


@dataclass(frozen=True)
class RuntimeLaunchObservation:
    """The bounded, DECOMPOSED result of the future Node-direct RPC launch.

    Category-B requires four independently-established launch facts (I2A
    Sec. 15 items 1-4), so this object carries four independent fields rather
    than one caller-supplied ``passed`` boolean:

    - ``observed_pi_version`` -- Pi is installed and its version is
      OBSERVABLE. Provenance only: nothing anywhere compares it against a
      pinned value. ``None``/malformed means "not observed", and a run with
      no observable Pi version cannot pass;
    - ``launch_shape_valid`` -- the Node-direct ``--mode rpc`` launch shape;
    - ``required_flags_accepted`` -- no "unknown flag" startup rejection;
    - ``lf_jsonl_correlation_succeeded`` -- LF-framed JSONL request/response
      correlation.

    These four are the resource kind's own INDEPENDENT creation-failure
    facts. They are recorded alongside the cleanup facts below and are never
    overwritten or masked by them -- a creator whose self-close failed still
    reports truthfully what its launch did and did not achieve.

    **Partial-resource accounting (design FU3 Sec. 9.3, FU3A/FU3B/FU3C).**
    ``session`` is the authority every later observation and the teardown are
    bound to. The four constructible states are exactly those documented on
    :class:`BrokerCreationObservation`, with ``direct_child_reported_exit``
    as this kind's observed postcondition. No handle crosses the boundary for
    a partial failure: the creator retains ownership, performs at most one
    bounded internal close, and reports facts.
    """

    session: RuntimeSession | None
    launch_shape_valid: bool
    required_flags_accepted: bool
    lf_jsonl_correlation_succeeded: bool
    observed_pi_version: str | None
    resource_created: bool = False
    cleanup_attempted: bool = False
    direct_child_reported_exit: bool | None = None

    def __post_init__(self) -> None:
        if self.session is not None and type(self.session) is not RuntimeSession:
            raise ObservationError(
                "RuntimeLaunchObservation.session must be a RuntimeSession or None"
            )
        require_exact_bool(
            "RuntimeLaunchObservation.launch_shape_valid", self.launch_shape_valid
        )
        require_exact_bool(
            "RuntimeLaunchObservation.required_flags_accepted", self.required_flags_accepted
        )
        require_exact_bool(
            "RuntimeLaunchObservation.lf_jsonl_correlation_succeeded",
            self.lf_jsonl_correlation_succeeded,
        )
        require_exact_bool(
            "RuntimeLaunchObservation.resource_created", self.resource_created
        )
        require_exact_bool(
            "RuntimeLaunchObservation.cleanup_attempted", self.cleanup_attempted
        )
        if self.observed_pi_version is not None:
            _require_pattern(
                "RuntimeLaunchObservation.observed_pi_version",
                self.observed_pi_version,
                _VERSION_PATTERN,
            )
        _validate_creator_cleanup_facts(
            type_name="RuntimeLaunchObservation",
            postcondition_name="direct_child_reported_exit",
            session_present=self.session is not None,
            resource_created=self.resource_created,
            cleanup_attempted=self.cleanup_attempted,
            postcondition=self.direct_child_reported_exit,
        )

    @property
    def pi_version_observed(self) -> bool:
        """Whether a usable Pi version was actually observed for THIS run."""
        return self.observed_pi_version is not None

    @property
    def cleanup_verified_success(self) -> bool:
        """AIDO's OWN derivation. Never a creator-supplied verdict (FU3C).

        ``cleanup_attempted and (direct_child_reported_exit is True)`` --
        identity against the ``True`` singleton, never bare Python truthiness
        and never a "the close call returned without raising" shortcut. The
        creator supplies only the narrow observed postcondition
        ``direct_child_reported_exit``: AIDO's own DIRECT child reported
        exit, exactly the same fact
        :class:`RuntimeShutdownObservation` reports for an ordinary teardown.
        It is never a claim that a descendant process, provider inference or
        GPU work stopped.
        """
        return self.cleanup_attempted and (self.direct_child_reported_exit is True)


# -- get_commands: extension identity (H1) and command provenance -------------


@dataclass(frozen=True)
class ObservedCommand:
    """One command entry as reported by ``get_commands``. Bounded, never raw.

    ``name`` and ``source`` are charset/length bounded, so a malformed entry
    -- including one carrying a path, a URL or a diagnostic sentence -- is
    refused at construction rather than compared, counted, or retained.

    **``get_commands`` enumerates SLASH COMMANDS, not tools** (design FU3
    Sec. 3/Sec. 5). The provenance fields below exist because the top-level
    ``source`` cannot discriminate AIDO's own extension from Pi's: real
    captured live runs against Pi 0.84.2 and 0.84.3 both report exactly two
    top-level-``"extension"``-sourced commands, AIDO's sentinel and Pi's own
    inline ``llama``. The discriminator is ``sourceInfo.source``.

    - ``source_info_present`` -- a ``sourceInfo`` value was reported at all;
    - ``source_info_well_formed`` -- it was an object, and any ``source`` it
      carried was a bounded origin token. A ``sourceInfo`` that is present
      but not an object, or whose ``source`` is not a bounded token, is
      recorded as NOT well formed rather than refused, so the gate can fail
      closed with the precise ``EXTENSION_COMMAND_PROVENANCE_UNKNOWN`` code
      instead of collapsing into a generic malformed-adapter refusal;
    - ``source_info_source`` -- the bounded origin kind, or ``None``.

    **No path is retained.** ``sourceInfo.path`` is an input to the frozen H1
    evaluator, never a field here: the sentinel's path is an absolute path
    AIDO itself supplied, and Pi's inline path (``<inline:llama.cpp>``) is
    runtime text. Neither belongs in a retained observation.
    """

    name: str
    source: str
    source_info_present: bool = False
    source_info_well_formed: bool = False
    source_info_source: str | None = None

    def __post_init__(self) -> None:
        _require_pattern("ObservedCommand.name", self.name, _COMMAND_NAME_PATTERN)
        _require_pattern("ObservedCommand.source", self.source, _ORIGIN_KIND_PATTERN)
        require_exact_bool("ObservedCommand.source_info_present", self.source_info_present)
        require_exact_bool(
            "ObservedCommand.source_info_well_formed", self.source_info_well_formed
        )
        if self.source_info_well_formed and not self.source_info_present:
            raise ObservationError(
                "ObservedCommand: an absent sourceInfo cannot also be well formed"
            )
        if self.source_info_source is not None:
            if not self.source_info_well_formed:
                raise ObservationError(
                    "ObservedCommand: an origin kind cannot be reported from a "
                    "sourceInfo that is absent or not well formed"
                )
            _require_pattern(
                "ObservedCommand.source_info_source",
                self.source_info_source,
                _ORIGIN_KIND_PATTERN,
            )

    @property
    def is_extension_sourced(self) -> bool:
        """Whether the TOP-LEVEL ``source`` selects this entry into the gate.

        The identical computation frozen AR2/O1 already use for
        ``extension_command_count``. A SELECTOR only -- Pi's own inline
        commands share this value.
        """
        return self.source == EXTENSION_COMMAND_SOURCE

    @property
    def provenance_is_cli(self) -> bool:
        """A candidate AIDO-loaded-extension entry (``sourceInfo.source == "cli"``)."""
        return (
            self.source_info_present
            and self.source_info_well_formed
            and self.source_info_source == CLI_EXTENSION_ORIGIN_KIND
        )

    @property
    def provenance_is_inline(self) -> bool:
        """A mechanically-established Pi-owned entry (``sourceInfo.source == "inline"``)."""
        return (
            self.source_info_present
            and self.source_info_well_formed
            and self.source_info_source == INLINE_EXTENSION_ORIGIN_KIND
        )


def observed_command_from_reported_entry(entry: Any) -> ObservedCommand:
    """Project ONE raw ``get_commands`` entry onto a bounded :class:`ObservedCommand`.

    The fixed contract for a future live adapter, so provenance is derived
    from the reported response by ONE piece of AIDO-owned code rather than
    re-implemented per adapter. Malformed ``sourceInfo`` metadata is recorded
    as "not well formed" -- the gate's own ``EXTENSION_COMMAND_PROVENANCE_UNKNOWN``
    refusal -- while a malformed NAME or top-level SOURCE is refused
    outright, because those two are what the entry even is.
    """
    if not isinstance(entry, Mapping):
        raise ObservationError("a reported get_commands entry must be an object")
    raw_info = entry.get("sourceInfo")
    present = raw_info is not None
    well_formed = present and isinstance(raw_info, Mapping)
    origin: str | None = None
    if well_formed:
        raw_origin = raw_info.get("source")
        if raw_origin is None:
            origin = None
        elif isinstance(raw_origin, str) and _ORIGIN_KIND_PATTERN.fullmatch(raw_origin):
            origin = raw_origin
        else:
            # Present but not a bounded origin token: unrecognized provenance,
            # never coerced and never retained as raw text.
            well_formed = False
    return ObservedCommand(
        name=entry.get("name"),
        source=entry.get("source"),
        source_info_present=present,
        source_info_well_formed=well_formed,
        source_info_source=origin,
    )


#: The projection a future live adapter MUST apply to the frozen evaluator's
#: returned dict: ``(observation field, frozen evaluator key)``. The frozen
#: evaluator's only free-text field, ``failure_reasons``, is deliberately
#: absent -- it is never read, never projected, and never retained.
_H1_PROJECTION: tuple[tuple[str, str], ...] = (
    ("sentinel_command_name", "sentinel_command_name"),
    ("sentinel_name_matched", "sentinel_name_matched"),
    ("sentinel_source_is_extension", "extension_source_matched"),
    ("sentinel_path_resolves_to_expected_entry", "extension_path_matched"),
    ("noncontradictory_source_origin", "noncontradictory_source_origin"),
    ("malformed_source_metadata", "malformed_source_metadata"),
    ("expected_source_kind", "expected_source_kind"),
    ("reported_source_kind", "sentinel_source_kind"),
)

#: The five components AIDO's own conjunction consumes. Named here so the
#: offline differential-conformance test can assert the projection covers
#: exactly the frozen rule's own inputs.
H1_COMPONENT_FIELDS: tuple[str, ...] = (
    "sentinel_name_matched",
    "sentinel_source_is_extension",
    "sentinel_path_resolves_to_expected_entry",
    "noncontradictory_source_origin",
    "malformed_source_metadata",
)


def h1_components_from_frozen_evaluation(evaluation: Any) -> dict[str, Any]:
    """Project ``ar2.handshakes.evaluate_extension_identity``'s dict, field for field.

    **This is the adapter's fixed contract** (design FU3 Sec. 6.3(c)): obtain
    the raw ``get_commands`` command list, call the FROZEN, UNMODIFIED
    evaluator, and hand the result here. The returned mapping is exactly the
    keyword arguments :class:`GetCommandsObservation` takes for its H1
    components -- no verdict, no ``passed`` flag, no ``failure_reasons``, and
    no raw command list.

    The evaluator's ``passed`` key is deliberately NOT projected: AIDO
    recomputes the conjunction itself from the components, so an adapter that
    starts returning ``True`` for a weaker notion of "matched" cannot express
    that as a pass -- the field it would have to lie about is the specific
    one it did not check.

    A reported ``sourceInfo.source`` that is not a bounded origin token is
    refused here rather than retained or coerced. The frozen evaluator
    already computes ``passed=False`` for every such row (an origin that is
    not exactly ``"cli"`` contradicts the expected kind), so refusing cannot
    turn a frozen pass into a projection failure.
    """
    if not isinstance(evaluation, Mapping):
        raise ObservationError(
            "h1_components_from_frozen_evaluation expects the frozen evaluator's "
            "returned mapping"
        )
    projected: dict[str, Any] = {}
    for field_name, frozen_key in _H1_PROJECTION:
        if frozen_key not in evaluation:
            raise ObservationError(
                f"the frozen H1 evaluation is missing its {frozen_key!r} component"
            )
        projected[field_name] = evaluation[frozen_key]
    return projected


@dataclass(frozen=True)
class GetCommandsObservation:
    """ONE correlated ``get_commands`` observation, from ONE runtime session.

    Frozen AR2 proves H1 FROM the ``get_commands`` response -- its own
    ``ar2.handshakes.evaluate_extension_identity(commands, extension_entry=...)``
    takes that response's command list as its argument. So H1 (exact
    extension identity) and the extension COMMAND-NAMESPACE partition are two
    DISTINCT gate facts derived from ONE response, and this object is what
    makes it structurally impossible for them to come from two unrelated
    runtime snapshots.

    **H1 arrives as COMPONENTS, never as a verdict** (design FU3 Sec. 6.3).
    The five fields below are the frozen rule's own five components, projected
    field-for-field by :func:`h1_components_from_frozen_evaluation`; AIDO
    derives the verdict in :attr:`h1_identity_established`.

    **No raw text is retained.** The expected extension entry path is an
    absolute path AIDO itself supplied: it is an INPUT to the frozen
    evaluator, never an observation field, and never placed in evidence.
    """

    runtime_session_id: str
    call_succeeded: bool
    response_shape_understood: bool
    sentinel_command_name: str = CATEGORY_B_SENTINEL_COMMAND_NAME
    sentinel_name_matched: bool = False
    sentinel_source_is_extension: bool = False
    sentinel_path_resolves_to_expected_entry: bool = False
    noncontradictory_source_origin: bool = True
    malformed_source_metadata: bool = False
    expected_source_kind: str = CLI_EXTENSION_ORIGIN_KIND
    reported_source_kind: str | None = None
    commands: tuple[ObservedCommand, ...] = ()

    def __post_init__(self) -> None:
        _require_pattern(
            "GetCommandsObservation.runtime_session_id", self.runtime_session_id, _ID_PATTERN
        )
        _require_pattern(
            "GetCommandsObservation.sentinel_command_name",
            self.sentinel_command_name,
            _COMMAND_NAME_PATTERN,
        )
        if self.sentinel_command_name != CATEGORY_B_SENTINEL_COMMAND_NAME:
            raise ObservationError(
                "GetCommandsObservation: H1 and the extension command namespace are "
                "evaluated against AIDO's OWN declared sentinel command name; an "
                "evaluation nominating a different reported command as the sentinel "
                "is refused"
            )
        require_exact_bool("GetCommandsObservation.call_succeeded", self.call_succeeded)
        require_exact_bool(
            "GetCommandsObservation.response_shape_understood", self.response_shape_understood
        )
        for name in H1_COMPONENT_FIELDS:
            require_exact_bool(f"GetCommandsObservation.{name}", getattr(self, name))
        _require_pattern(
            "GetCommandsObservation.expected_source_kind",
            self.expected_source_kind,
            _ORIGIN_KIND_PATTERN,
        )
        if self.expected_source_kind != CLI_EXTENSION_ORIGIN_KIND:
            raise ObservationError(
                "GetCommandsObservation: H1 for AIDO's own CLI-loaded extension is "
                f"evaluated against {CLI_EXTENSION_ORIGIN_KIND!r}; an evaluation "
                "against a different expected origin kind is not this gate's rule"
            )
        if self.reported_source_kind is not None:
            _require_pattern(
                "GetCommandsObservation.reported_source_kind",
                self.reported_source_kind,
                _ORIGIN_KIND_PATTERN,
            )
        if not isinstance(self.commands, tuple) or not all(
            type(entry) is ObservedCommand for entry in self.commands
        ):
            raise ObservationError(
                "GetCommandsObservation.commands must be a tuple of ObservedCommand"
            )
        if len(self.commands) > _MAX_REPORTED_COMMANDS:
            raise ObservationError(
                "GetCommandsObservation.commands exceeds the bounded reported-command "
                "count; an unbounded runtime-supplied list is refused"
            )
        if not self.call_succeeded or not self.response_shape_understood:
            self._require_nothing_observed()

    def _require_nothing_observed(self) -> None:
        """A failed or ununderstood response observed NOTHING -- not even partly."""
        if not self.call_succeeded and self.response_shape_understood:
            raise ObservationError(
                "GetCommandsObservation: a failed call cannot also report an "
                "understood response"
            )
        if self.commands:
            raise ObservationError(
                "GetCommandsObservation: a failed or ununderstood response cannot "
                "also report a command list"
            )
        if (
            self.sentinel_name_matched
            or self.sentinel_source_is_extension
            or self.sentinel_path_resolves_to_expected_entry
            or self.malformed_source_metadata
            or self.noncontradictory_source_origin is not True
            or self.reported_source_kind is not None
        ):
            raise ObservationError(
                "GetCommandsObservation: a failed or ununderstood response cannot "
                "also report any observed H1 component"
            )

    @property
    def h1_identity_established(self) -> bool:
        """AIDO's OWN recomputation of the frozen H1 rule. Never adapter-supplied.

        ``1 and 2 and 3 and 4 and not 5`` over the frozen evaluator's own
        five components. No single adapter field can authorize H1.
        """
        return (
            self.sentinel_name_matched
            and self.sentinel_source_is_extension
            and self.sentinel_path_resolves_to_expected_entry
            and self.noncontradictory_source_origin
            and not self.malformed_source_metadata
        )

    def command_names_in_report_order(self) -> tuple[str, ...]:
        """Every reported name, IN ORDER, with duplicates preserved.

        Deliberately never a ``set``/``frozenset``: collapsing duplicates is
        exactly how a runtime reporting one command twice could compare equal
        to a smaller expected set.
        """
        return tuple(entry.name for entry in self.commands)

    def extension_command_partition(self) -> "ExtensionCommandPartition":
        """Partition the top-level-``"extension"``-sourced entries by provenance.

        This classification is NEW I2B-owned code, not the frozen evaluator
        reused: ``evaluate_extension_identity`` only ever examines the
        sentinel-named entry. It is built on this module's own bounded
        validation primitives rather than a second validation style.
        """
        cli: list[str] = []
        inline: list[str] = []
        unrecognized: list[str] = []
        for entry in self.commands:
            if not entry.is_extension_sourced:
                continue
            if entry.provenance_is_cli:
                cli.append(entry.name)
            elif entry.provenance_is_inline:
                inline.append(entry.name)
            else:
                unrecognized.append(entry.name)
        return ExtensionCommandPartition(
            cli_command_names=tuple(sorted(cli)),
            inline_command_names=tuple(sorted(inline)),
            unrecognized_command_names=tuple(sorted(unrecognized)),
        )


@dataclass(frozen=True)
class ExtensionCommandPartition:
    """How one ``get_commands`` response's extension entries classify.

    Every member is a SORTED SEQUENCE, never a set: multiplicity is
    load-bearing here, because "exactly one CLI-sourced entry" is precisely
    the fact a duplicate would otherwise collapse away.
    """

    cli_command_names: tuple[str, ...]
    inline_command_names: tuple[str, ...]
    unrecognized_command_names: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("cli_command_names", "inline_command_names", "unrecognized_command_names"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(
                isinstance(entry, str) for entry in value
            ):
                raise ObservationError(f"ExtensionCommandPartition.{name} must be a tuple of str")

    @property
    def cli_entry_count(self) -> int:
        return len(self.cli_command_names)

    @property
    def unrecognized_entry_count(self) -> int:
        return len(self.unrecognized_command_names)


@dataclass(frozen=True)
class GetStateObservation:
    """ONE correlated ``get_state`` observation, from ONE runtime session.

    H2 (exact provider/model identity) and "the ``get_state`` response shape
    is understood" are two distinct gate facts derived from THIS one response
    -- the same one-observation discipline
    :class:`GetCommandsObservation` applies to H1 and the command namespace.
    ``reported_provider``/``reported_model`` are bounded identity strings,
    never a raw response body, base URL, host, or error message.

    ``get_state`` returns model, thinking level, streaming/compaction flags,
    session identity and message counts -- **not tools**. Nothing here is, or
    may be read as, an observation of the active tool registry.
    """

    runtime_session_id: str
    call_succeeded: bool
    response_shape_understood: bool
    reported_provider: str | None = None
    reported_model: str | None = None

    def __post_init__(self) -> None:
        _require_pattern(
            "GetStateObservation.runtime_session_id", self.runtime_session_id, _ID_PATTERN
        )
        require_exact_bool("GetStateObservation.call_succeeded", self.call_succeeded)
        require_exact_bool(
            "GetStateObservation.response_shape_understood", self.response_shape_understood
        )
        for name, value in (
            ("reported_provider", self.reported_provider),
            ("reported_model", self.reported_model),
        ):
            if value is not None:
                _require_pattern(f"GetStateObservation.{name}", value, _IDENTITY_PATTERN)
        if not self.call_succeeded and (
            self.response_shape_understood
            or self.reported_provider is not None
            or self.reported_model is not None
        ):
            raise ObservationError(
                "GetStateObservation: a failed call cannot also report an understood "
                "response or an echoed identity"
            )
        if not self.response_shape_understood and (
            self.reported_provider is not None or self.reported_model is not None
        ):
            raise ObservationError(
                "GetStateObservation: an ununderstood response cannot also report an "
                "echoed provider/model identity"
            )


@dataclass(frozen=True)
class ProtocolObservation:
    """Whether ANY protocol violation or extension error was observed (I2A gate 8).

    Frozen AR2's supervisor already records both classes of event
    (``supervisor.activity.extension_errors``, and its own wire/protocol
    accounting). This object carries only the two BOOLEAN conclusions --
    never the offending frame, the error text, the stderr snapshot, or any
    other raw runtime output.
    """

    runtime_session_id: str
    protocol_violation_observed: bool
    extension_error_observed: bool

    def __post_init__(self) -> None:
        _require_pattern(
            "ProtocolObservation.runtime_session_id", self.runtime_session_id, _ID_PATTERN
        )
        require_exact_bool(
            "ProtocolObservation.protocol_violation_observed", self.protocol_violation_observed
        )
        require_exact_bool(
            "ProtocolObservation.extension_error_observed", self.extension_error_observed
        )


@dataclass(frozen=True)
class RuntimeShutdownObservation:
    """What AIDO's own runtime-shutdown call reported, for ONE runtime session.

    **Claim scope, exactly.** ``shutdown_call_returned`` means AIDO's own call
    returned rather than raising. ``orchestrator_direct_child_reported_exit``
    means AIDO's OWN DIRECT child was reported to have exited. Neither is, and
    neither may ever be read as, a claim that a descendant process was
    terminated, that Pi/provider inference stopped, or that GPU work stopped
    -- those are outside this phase's observation boundary entirely.
    """

    runtime_session_id: str
    shutdown_call_returned: bool
    orchestrator_direct_child_reported_exit: bool

    def __post_init__(self) -> None:
        _require_pattern(
            "RuntimeShutdownObservation.runtime_session_id",
            self.runtime_session_id,
            _ID_PATTERN,
        )
        require_exact_bool(
            "RuntimeShutdownObservation.shutdown_call_returned", self.shutdown_call_returned
        )
        require_exact_bool(
            "RuntimeShutdownObservation.orchestrator_direct_child_reported_exit",
            self.orchestrator_direct_child_reported_exit,
        )
