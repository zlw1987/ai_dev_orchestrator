"""I2B -- run-scoped Category-B resource authority and bounded live observations.

**OFFLINE ONLY. This module launches nothing, opens nothing, and reads
nothing.** It contains no ``subprocess``, ``socket``, ``http``, ``urllib``,
or any other I/O primitive; it is pure value objects plus their
valid-by-construction rules. A source-level regression test in this
package's offline suite enforces that mechanically.

Why this module exists (5F3B-I2B-FU1)
-------------------------------------

The first I2B controller represented every future live operation as an
UNRELATED no-argument callback -- ``h1_check()``, ``get_state()``,
``broker_ready()``, ``teardown()``. Each could return a perfectly valid
result, and nothing anywhere established that those four results described
**the same runtime**. Two individually valid observations could refer to two
different runtime instances; a caller could hand the controller runtime A's
launcher and runtime B's teardown; and a partially-created resource had no
authority object through which it could ever be closed.

This module supplies the narrow, I2B-OWNED authority shape that closes
that. It is deliberately **not** a generic ``AgentRuntime`` /
``RuntimeAdapter`` framework: there is no registry, no plugin system, no
lifecycle base class, no capability negotiation, no reusable transport, and
no interface a second runtime could be registered against. It is exactly
the value objects one Category-B run needs, and nothing else.

The binding is MECHANICAL, not conventional
-------------------------------------------

1. The controller mints one per-run ``run_id`` nonce that no adapter
   supplies. :class:`BrokerSession` must carry that exact value back, or the
   broker is refused before any launch-capable continuation.
2. :class:`RuntimeLaunchRequest` can only be CONSTRUCTED from a
   :class:`BrokerSession` that already carries the matching ``run_id`` and
   has ``reached_ready is True``. Frozen O1's observed lifecycle
   (``run_o1.phase_handshake``/``phase_case``) starts the broker and reaches
   ``READY`` *before* Pi is launched, because the launch writes the broker
   ``pipe_name``/``capability_id``/``token`` into the disposable extension.
   That ordering is therefore not a convention here -- a launch request for
   a not-ready or foreign broker is unconstructible.
3. Every post-launch observation carries the ``runtime_session_id`` it was
   produced from. The controller compares it against the session the launch
   actually returned, so an observation belonging to a different runtime is
   refused rather than silently accepted.
4. A failed launch must EITHER hand back a :class:`RuntimeSession` (so AIDO
   retains enough authority to close it) OR declare that it closed its own
   partial resource internally. :class:`RuntimeLaunchObservation` cannot be
   constructed in the third, stranding state.

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
model id, a command name -- is charset- and length-bounded at construction,
so raw stdout, stderr, an RPC body, a traceback, an endpoint URL, or a
provider exception message cannot be smuggled into a retained observation
in the first place. Rejection raises :class:`ObservationError`; the
controller reduces that to one bounded failure code and never reads the
exception's text.

Truthful claim scope
--------------------

:class:`RuntimeShutdownObservation` reports only what AIDO's own shutdown
call returned and whether AIDO's own DIRECT child was reported to have
exited. Nothing here may ever be read as a claim that a descendant process
stopped, that backend inference stopped, or that GPU work stopped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class ObservationError(ValueError):
    """A run-authority or live-observation value object is invalid. Fails closed.

    Deliberately a ``ValueError`` subclass so a caller that already treats
    an invalid value object as a construction error keeps doing so. The
    controller catches it and reduces it to one bounded failure code --
    ``str()``/``repr()`` of this exception is never retained in evidence.
    """


#: An AIDO- or adapter-minted correlation identifier. Bounded so an id can
#: never carry a URL, a path, a credential, or a diagnostic sentence.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

#: A runtime-reported command name. Bounded for the same reason.
_COMMAND_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

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
#: may report. The authorized registry has exactly two members, so any real
#: response is tiny; this only refuses an unbounded runtime-supplied list
#: rather than holding it in memory to compare it.
_MAX_REPORTED_COMMANDS = 256


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


def _require_non_blank_path(field_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ObservationError(f"{field_name} must be a str; got {type(value).__name__}")
    if not value or not value.strip():
        raise ObservationError(f"{field_name} must be non-blank")
    return value


# -- broker authority ---------------------------------------------------------


@dataclass(frozen=True)
class BrokerCreationRequest:
    """What AIDO hands its broker-creation adapter. AIDO-authored only.

    Carries the per-run ``run_id`` nonce the returned :class:`BrokerSession`
    must echo back, plus the canonical workspace root the broker's
    capability is scoped to. There is no adapter-chosen field here at all.
    """

    run_id: str
    workspace_root: str = field(repr=False)

    def __post_init__(self) -> None:
        _require_pattern("BrokerCreationRequest.run_id", self.run_id, _ID_PATTERN)
        _require_non_blank_path("BrokerCreationRequest.workspace_root", self.workspace_root)

    def __repr__(self) -> str:  # noqa: D105 - workspace path is never rendered
        return f"{type(self).__name__}(run_id={self.run_id!r}, workspace_root=<bound>)"


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
class BrokerShutdownObservation:
    """What AIDO's own broker-shutdown call reported, for ONE broker session.

    ``reached_closed`` is the broker lifecycle's own terminal state, exactly
    as frozen AR2's ``BrokerServer.shutdown()`` reports it. This object
    never claims a runtime process, a descendant, or backend inference
    stopped.
    """

    session_id: str
    reached_closed: bool

    def __post_init__(self) -> None:
        _require_pattern("BrokerShutdownObservation.session_id", self.session_id, _ID_PATTERN)
        require_exact_bool("BrokerShutdownObservation.reached_closed", self.reached_closed)


# -- runtime authority --------------------------------------------------------


@dataclass(frozen=True)
class RuntimeSession:
    """The handle proving WHICH runtime instance an observation belongs to.

    Every field is a correlation identifier -- there is no process handle,
    no pipe, no file descriptor and no callable here. ``broker_session_id``
    is what makes a runtime session inseparable from the broker it was
    launched against.
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
    ``broker_session.run_id == run_id`` and ``broker_session.reached_ready
    is True``. Frozen O1's observed lifecycle reaches broker ``READY``
    before Pi is launched; here that ordering is enforced by the type, so a
    controller (or a future live adapter) cannot express "launch first,
    broker ready later" at all.

    ``launch_environment`` is the already-accepted, immutable I2-1
    ``LaunchEnvironment``; ``model_id``/``provider_id`` come from the run's
    already-validated route descriptor. There is no raw ``api_key``,
    ``base_url``, ``config_dir`` or argv parameter here -- the credential
    reaches the child only through the accepted child-environment carrier.
    """

    run_id: str
    broker_session: BrokerSession
    launch_environment: Any
    workspace_root: str = field(repr=False)
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
        # Checked structurally rather than by isinstance: this module is a
        # LEAF that imports no other qualification module, so it can never
        # create an import cycle with i2_environment.
        if not hasattr(self.launch_environment, "as_launch_snapshot"):
            raise ObservationError(
                "RuntimeLaunchRequest.launch_environment must be the accepted I2 "
                "LaunchEnvironment (no as_launch_snapshot boundary found)"
            )
        _require_non_blank_path("RuntimeLaunchRequest.workspace_root", self.workspace_root)
        _require_pattern("RuntimeLaunchRequest.provider_id", self.provider_id, _IDENTITY_PATTERN)
        _require_pattern("RuntimeLaunchRequest.model_id", self.model_id, _IDENTITY_PATTERN)

    def __repr__(self) -> str:  # noqa: D105 - workspace path is never rendered
        return (
            f"{type(self).__name__}(run_id={self.run_id!r}, "
            f"broker_session_id={self.broker_session.session_id!r}, "
            f"provider_id={self.provider_id!r}, model_id={self.model_id!r}, "
            "workspace_root=<bound>)"
        )


@dataclass(frozen=True)
class RuntimeLaunchObservation:
    """The bounded, DECOMPOSED result of the future Node-direct RPC launch.

    Category-B requires four independently-established launch facts (I2A
    Sec. 15 items 1-4), so this object carries four independent fields
    rather than one caller-supplied ``passed`` boolean:

    - ``observed_pi_version`` -- Pi is installed and its version is
      OBSERVABLE. Provenance only: nothing anywhere compares it against a
      pinned value. ``None``/malformed means "not observed", and a run with
      no observable Pi version cannot pass;
    - ``launch_shape_valid`` -- the Node-direct ``--mode rpc`` launch shape;
    - ``required_flags_accepted`` -- no "unknown flag" startup rejection;
    - ``lf_jsonl_correlation_succeeded`` -- LF-framed JSONL request/response
      correlation.

    **Partial-resource accounting.** ``session`` is the authority every
    later observation and the teardown are bound to. If the launch failed
    without producing a session, the adapter MUST declare
    ``partial_resource_cleaned_internally=True`` -- otherwise this object
    cannot be constructed at all, because the third state ("failed, no
    authority handed back, nothing cleaned") is exactly the stranding case
    Category-B may not silently accept. Conversely a successful launch that
    returned a session may not also claim it cleaned itself up.
    """

    session: RuntimeSession | None
    launch_shape_valid: bool
    required_flags_accepted: bool
    lf_jsonl_correlation_succeeded: bool
    observed_pi_version: str | None
    partial_resource_cleaned_internally: bool = False

    def __post_init__(self) -> None:
        if self.session is not None and not isinstance(self.session, RuntimeSession):
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
            "RuntimeLaunchObservation.partial_resource_cleaned_internally",
            self.partial_resource_cleaned_internally,
        )
        if self.observed_pi_version is not None:
            _require_pattern(
                "RuntimeLaunchObservation.observed_pi_version",
                self.observed_pi_version,
                _VERSION_PATTERN,
            )
        if self.session is None:
            if self.launch_shape_valid:
                raise ObservationError(
                    "RuntimeLaunchObservation: a valid launch shape must hand back a "
                    "RuntimeSession"
                )
            if not self.partial_resource_cleaned_internally:
                raise ObservationError(
                    "RuntimeLaunchObservation: a failed launch must either return a "
                    "RuntimeSession (so AIDO retains authority to close it) or declare "
                    "partial_resource_cleaned_internally=True; a stranded partial "
                    "resource is refused"
                )
        elif self.partial_resource_cleaned_internally:
            raise ObservationError(
                "RuntimeLaunchObservation: a session was returned, so the creator "
                "cannot also claim it cleaned its partial resource internally"
            )

    @property
    def pi_version_observed(self) -> bool:
        """Whether a usable Pi version was actually observed for THIS run."""
        return self.observed_pi_version is not None


@dataclass(frozen=True)
class ObservedCommand:
    """One command entry as reported by ``get_commands``. Bounded, never raw.

    ``name`` and ``source`` are charset/length bounded, so a malformed
    entry -- including one carrying a path, a URL or a diagnostic sentence
    -- is refused at construction rather than compared, counted, or
    retained.

    **``source`` is recorded, but is deliberately NOT part of the tool
    registry rule.** I2A Sec. 15 item 6 defines that gate over the
    REGISTERED COMMAND SET (exactly ``aido_read``/``aido_edit``, nothing
    else), and AR2's own ``--allowed-tools`` allowlist carries names only.
    Extension provenance is proven separately, by H1, against the sentinel
    command's own ``source``/``sourceInfo``. Adding a source condition to
    the registry gate here would be a NEW rule this slice is not
    authorized to invent.
    """

    name: str
    source: str

    def __post_init__(self) -> None:
        _require_pattern("ObservedCommand.name", self.name, _COMMAND_NAME_PATTERN)
        _require_pattern("ObservedCommand.source", self.source, _COMMAND_NAME_PATTERN)


@dataclass(frozen=True)
class GetCommandsObservation:
    """ONE correlated ``get_commands`` observation, from ONE runtime session.

    Frozen AR2 proves H1 FROM the ``get_commands`` response -- its own
    ``ar2.handshakes.evaluate_extension_identity(commands,
    extension_entry=...)`` takes that response's command list as its
    argument. So H1 (exact extension identity) and the exact authorized
    tool registry are two DISTINCT gate facts derived from ONE response,
    and this object is what makes it structurally impossible for them to
    come from two unrelated runtime snapshots.

    ``extension_identity_matched`` is the adapter's evaluation of that
    frozen H1 rule against THIS response. ``commands`` is the same
    response's command list, bounded. The controller derives the registry
    gate itself and never delegates it.
    """

    runtime_session_id: str
    call_succeeded: bool
    response_shape_understood: bool
    extension_identity_matched: bool
    commands: tuple[ObservedCommand, ...] = ()

    def __post_init__(self) -> None:
        _require_pattern(
            "GetCommandsObservation.runtime_session_id", self.runtime_session_id, _ID_PATTERN
        )
        require_exact_bool("GetCommandsObservation.call_succeeded", self.call_succeeded)
        require_exact_bool(
            "GetCommandsObservation.response_shape_understood", self.response_shape_understood
        )
        require_exact_bool(
            "GetCommandsObservation.extension_identity_matched",
            self.extension_identity_matched,
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
        if not self.call_succeeded and (
            self.response_shape_understood or self.extension_identity_matched or self.commands
        ):
            raise ObservationError(
                "GetCommandsObservation: a failed call cannot also report an understood "
                "response, a matched extension identity, or commands"
            )
        if not self.response_shape_understood and (
            self.extension_identity_matched or self.commands
        ):
            raise ObservationError(
                "GetCommandsObservation: an ununderstood response cannot also report a "
                "matched extension identity or a command list"
            )

    def command_names_in_report_order(self) -> tuple[str, ...]:
        """Every reported name, IN ORDER, with duplicates preserved.

        Deliberately never a ``set``/``frozenset``: collapsing duplicates is
        exactly how a runtime reporting ``aido_read`` twice (and
        ``aido_edit`` never) could have compared equal to the authorized
        registry.
        """
        return tuple(entry.name for entry in self.commands)


@dataclass(frozen=True)
class GetStateObservation:
    """ONE correlated ``get_state`` observation, from ONE runtime session.

    H2 (exact provider/model identity) and "the ``get_state`` response
    shape is understood" are two distinct gate facts derived from THIS one
    response -- the same one-observation discipline
    :class:`GetCommandsObservation` applies to H1 and the tool registry.
    ``reported_provider``/``reported_model`` are bounded identity strings,
    never a raw response body, base URL, host, or error message.
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

    **Claim scope, exactly.** ``shutdown_call_returned`` means AIDO's own
    call returned rather than raising. ``orchestrator_direct_child_reported_exit``
    means AIDO's OWN DIRECT child was reported to have exited. Neither is,
    and neither may ever be read as, a claim that a descendant process was
    terminated, that Pi/provider inference stopped, or that GPU work
    stopped -- those are outside this phase's observation boundary entirely.
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
