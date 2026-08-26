"""I2-1 -- the qualification-owned child-environment builder (I2A design Sec. 9).

**OFFLINE ONLY.** This module never reads ``os.environ`` itself. Every
ambient value it might use -- including the accepted Windows baseline names
-- is supplied by the caller as an explicit ``ambient_environ`` mapping, so
the whole builder is testable with synthetic decoy environments and never
touches, dumps, or prints a real process environment value.

Structurally modeled on ``experiments/pi_external_runtime_ar2/ar2/environment.py``
(I2A Sec. 9) but is new, I2-owned code -- it does not import or modify that
frozen module. The Windows baseline names and the forbidden-fragment list are
reused as VALUES (duplicated constants), never as an import dependency of
this production path.

**No keyless mode.** Unlike AR2's ``ROUTE_PLACEHOLDER_ENV_NAME`` /
``no_api_key`` placeholder, this B300 qualification route always carries a
real credential value under exactly one new, non-``AIDO_``-prefixed,
non-forbidden-fragment carrier name.

**5F3B-I2-FU3, two closures:**

1. **``PI_CODING_AGENT_DIR`` has exactly one source.** Independent review
   passed an arbitrary, real/global-style path directly as
   ``pi_config_dir`` and it was accepted unchanged.
   :func:`build_child_environment` no longer takes a raw ``pi_config_dir``
   string OR a raw ``credential_value`` string at all -- it consumes the
   typed ``i2_pi_config.GeneratedQualificationConfig`` (re-verified here,
   at the consumption boundary, before use) and
   ``i2_secret_context.QualificationRouteSecretContext`` objects instead,
   so neither the global ``~/.pi/agent`` directory, an arbitrary sibling
   config, nor a credential value disagreeing with the run's own secret
   context can reach the child environment through this API.
2. **``LaunchEnvironment`` is immutable and self-validating.** Independent
   review did ``launch.environment["OPENAI_API_KEY"] = "oops"`` on a
   supposedly-frozen dataclass and it worked, because ``frozen=True`` only
   blocks attribute REASSIGNMENT, not mutation of a mutable object a field
   already points at. The raw dict is now a private field
   (``field(repr=False)``) never exposed directly; ``environment`` is a
   read-only ``MappingProxyType`` view, and a fresh, independent
   ``dict[str, str]`` snapshot for an eventual subprocess-launch boundary
   is available only via :meth:`LaunchEnvironment.as_launch_snapshot`.
   ``__post_init__`` additionally re-checks internal coherence (narrowed
   PATH, ``included_names`` agreement, ``PI_CODING_AGENT_DIR`` binding, a
   non-blank credential carrier, no forbidden name) so the object cannot
   describe an impossible state even if built some other way.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .i2_identity import CREDENTIAL_ENV_VAR_NAME, PROVIDER_ID
from .i2_pi_config import GeneratedQualificationConfig, verify_generated_config_integrity
from .i2_secret_context import QualificationRouteSecretContext

#: Identical VALUES to AR2's ``BASE_WINDOWS_NAMES`` (environment.py:28-38),
#: duplicated here as I2-owned data -- not imported from AR2.
BASE_WINDOWS_NAMES: tuple[str, ...] = (
    "SystemRoot",
    "SystemDrive",
    "windir",
    "ComSpec",
    "PATHEXT",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "TEMP",
    "TMP",
)

#: Profile names this builder NEVER forwards, by construction (no code path
#: below ever copies one of these into the built environment). Kept here only
#: so tests can assert the withholding by name.
WITHHELD_PROFILE_NAMES: tuple[str, ...] = ("USERPROFILE", "HOME", "APPDATA")

#: Same style/content as AR2's ``FORBIDDEN_NAME_FRAGMENTS`` (environment.py:48-86),
#: duplicated as I2-owned data. Checked by NAME only, never by value.
FORBIDDEN_NAME_FRAGMENTS: tuple[str, ...] = (
    "API_KEY",
    "APIKEY",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "CREDENTIAL",
    "TOKEN",
    "AIDO_",
    "GITHUB",
    "ANTHROPIC",
    "OPENAI",
    "AZURE",
    "GEMINI",
    "GROQ",
    "XAI_",
    "OPENROUTER",
    "MISTRAL",
    "DEEPSEEK",
    "NVIDIA",
    "TOGETHER",
    "FIREWORKS",
    "CEREBRAS",
    "CLOUDFLARE",
    "MOONSHOT",
    "MINIMAX",
    "KIMI",
    "QWEN",
    "ZAI",
    "XIAOMI",
    "AWS_",
    "BEDROCK",
    "PROXY",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "EDITOR",
    "VISUAL",
)


class EnvironmentPolicyError(Exception):
    """The qualification child environment could not be built without violating policy."""


@dataclass(frozen=True)
class LaunchEnvironment:
    """The explicit environment plus an audit of what was and was not included.

    **Immutable (5F3B-I2-FU3).** The real environment mapping is a private
    field (``_raw_environment``, ``field(repr=False)``); it is exposed
    publicly only as a read-only :class:`types.MappingProxyType` via the
    :attr:`environment` property. There is no public attribute anywhere on
    this object holding the mutable dict, so ``launch.environment["X"] =
    "y"`` now raises ``TypeError`` (assignment through a
    ``MappingProxyType``), not a silent in-place mutation of a retained
    authority object.

    **Self-validating.** ``__post_init__`` re-checks: ``path_narrowed is
    True`` (identity check -- rejects any non-``bool`` truthy stand-in
    too); ``included_names`` agrees exactly with the environment's keys;
    ``PI_CODING_AGENT_DIR`` equals the bound ``pi_config_dir``; the
    credential carrier is present and non-blank; and no forbidden
    ambient/vendor/AIDO name is present except the exact carrier.

    **Alias-immune (5F3B-I2-FU3A).** Independent review did
    ``LaunchEnvironment(_raw_environment=raw, ...)`` and then
    ``raw["OPENAI_API_KEY"] = "evil"`` on the CALLER's own dict afterward,
    and the mutation was visible through ``launch.environment`` -- because
    ``frozen=True`` only blocks reassigning the ``_raw_environment``
    attribute, never mutation of whatever mutable object it already points
    at, and the constructor had never copied it. ``__post_init__`` now
    replaces ``self._raw_environment`` with a FRESH ``dict`` copy of
    whatever was passed in, before any validation runs and before control
    ever returns to the caller -- so no external reference the caller still
    holds can affect this object afterward, in either direction.
    """

    _raw_environment: dict[str, str] = field(repr=False)
    included_names: tuple[str, ...]
    path_narrowed: bool
    path_entry_count: int
    pi_config_dir: str = field(repr=False)

    def __post_init__(self) -> None:
        # Break any external alias FIRST (5F3B-I2-FU3A) -- everything below
        # then validates this object's OWN independent copy.
        object.__setattr__(self, "_raw_environment", dict(self._raw_environment))
        if self.path_narrowed is not True:
            raise EnvironmentPolicyError(
                "launch environment error: path_narrowed must be exactly True"
            )
        if set(self.included_names) != set(self._raw_environment):
            raise EnvironmentPolicyError(
                "launch environment error: included_names disagrees with the "
                "environment's own keys"
            )
        if self._raw_environment.get("PI_CODING_AGENT_DIR") != self.pi_config_dir:
            raise EnvironmentPolicyError(
                "launch environment error: PI_CODING_AGENT_DIR disagrees with the "
                "bound generated-config directory"
            )
        carrier_value = self._raw_environment.get(CREDENTIAL_ENV_VAR_NAME)
        if not carrier_value or not carrier_value.strip():
            raise EnvironmentPolicyError(
                "launch environment error: the credential carrier is missing or blank"
            )
        violations = [
            name
            for name in self._raw_environment
            if name != CREDENTIAL_ENV_VAR_NAME
            and any(fragment in name.upper() for fragment in FORBIDDEN_NAME_FRAGMENTS)
        ]
        if violations:
            raise EnvironmentPolicyError(
                "launch environment error: the built environment contains withheld "
                "names: " + ", ".join(sorted(violations))
            )

    @property
    def environment(self) -> Mapping[str, str]:
        """A read-only view. Assigning through this raises ``TypeError``."""
        return MappingProxyType(self._raw_environment)

    def as_launch_snapshot(self) -> dict[str, str]:
        """A FRESH, independent ``dict`` copy for a subprocess-launch boundary only.

        Never the retained authority object itself -- callers must not
        treat this snapshot as anything but a one-shot value; mutating it
        has no effect on this :class:`LaunchEnvironment` or on any other
        snapshot.
        """
        return dict(self._raw_environment)

    def __repr__(self) -> str:  # noqa: D105 - see class docstring
        return (
            f"{type(self).__name__}(included_names={self.included_names!r}, "
            f"path_narrowed={self.path_narrowed!r}, "
            f"path_entry_count={self.path_entry_count!r}, "
            f"pi_config_dir=<bound>)"
        )


def _narrowed_path(
    node_executable: str, git_executable: str | None, ambient_environ: Mapping[str, str]
) -> str:
    """A PATH holding only the Node directory, Git, and the system directory.

    Mirrors AR2's ``_narrowed_path`` construction exactly, but reads
    ``SystemRoot`` from the injected ``ambient_environ`` rather than
    ``os.environ``.
    """
    system_root = ambient_environ.get("SystemRoot") or r"C:\Windows"
    entries = [
        os.path.dirname(node_executable),
        os.path.join(system_root, "System32"),
        system_root,
    ]
    if git_executable:
        entries.insert(1, os.path.dirname(git_executable))
    seen: list[str] = []
    for entry in entries:
        if entry and entry not in seen:
            seen.append(entry)
    return os.pathsep.join(seen)


def build_child_environment(
    *,
    ambient_environ: Mapping[str, str],
    node_executable: str,
    generated_config: GeneratedQualificationConfig,
    secret_context: QualificationRouteSecretContext,
    git_executable: str | None = None,
) -> LaunchEnvironment:
    """Build the explicit, positive-allowlist Pi child environment.

    ``ambient_environ`` is REQUIRED and has no default -- there is
    deliberately no silent fallback to ``os.environ`` anywhere in this
    function. The offline suite passes synthetic mappings, including
    hostile decoy names, to prove none of them propagate.

    **5F3B-I2-FU3: no raw ``pi_config_dir``/``credential_value`` parameters.**
    ``PI_CODING_AGENT_DIR`` is set to ``generated_config.config_dir`` --
    ``generated_config``'s authority is RE-VERIFIED here, at this
    consumption boundary, before its ``config_dir`` is trusted, exactly
    like FU2's descriptor revalidation pattern. The child credential
    carrier's value comes ONLY from ``secret_context.api_key`` -- there is
    no independent ``credential_value`` argument through which a caller
    could send a value that disagrees with the SAME run-scoped secret
    context ``ArtifactSafetyContext`` will later scrub against.

    Identical for Candidate A and Candidate B -- this function takes no
    candidate parameter at all, so candidate symmetry is structural, not a
    policy this function could accidentally violate.

    **5F3B-I2-FU3A: complete integrity, plus mandatory cross-object binding,
    enforced HERE -- not only by the optional ``i2_composition`` helper.**
    ``generated_config`` is re-verified with
    :func:`~qualification.i2_pi_config.verify_generated_config_integrity`
    (genuine issuance, AND matching on-disk content digests -- stronger than
    FU3's marker-only re-check), and this function additionally REFUSES,
    before building anything, if ``generated_config`` and ``secret_context``
    disagree on ``provider_id``, ``model_id``, or the generated config's own
    recorded ``baseUrl``. A caller who skips
    ``i2_composition.verify_i2_identity_binding`` can no longer build a
    child environment for a config/secret pairing that does not agree with
    itself.
    """
    verify_generated_config_integrity(
        config_dir=generated_config.config_dir,
        settings_path=generated_config.settings_path,
        models_path=generated_config.models_path,
        authority_token=generated_config.authority_token,
        provider_id=generated_config.provider_id,
        model_id=generated_config.model_id,
    )

    if generated_config.provider_id != secret_context.provider_id:
        raise EnvironmentPolicyError(
            "environment error: generated config provider_id does not match "
            "the run's secret context"
        )
    if generated_config.model_id != secret_context.model_id:
        raise EnvironmentPolicyError(
            "environment error: generated config model_id does not match "
            "the run's secret context"
        )
    models_document = json.loads(Path(generated_config.models_path).read_text(encoding="utf-8"))
    provider_document = models_document.get("providers", {}).get(generated_config.provider_id, {})
    if provider_document.get("baseUrl") != secret_context.base_url:
        raise EnvironmentPolicyError(
            "environment error: generated config base URL does not match "
            "the run's secret context"
        )

    credential_value = secret_context.api_key
    if not credential_value or not credential_value.strip():
        # Defensive only: QualificationRouteSecretContext.__post_init__
        # already makes a blank api_key impossible to construct.
        raise EnvironmentPolicyError(
            "environment error: the run-scoped secret context's api_key is "
            "blank; this route has no keyless mode"
        )

    environment: dict[str, str] = {
        name: ambient_environ[name] for name in BASE_WINDOWS_NAMES if name in ambient_environ
    }

    environment["PATH"] = _narrowed_path(node_executable, git_executable, ambient_environ)

    # Pi-owned, deliberately set (I2A design Sec. 9 table). The ONE source
    # of PI_CODING_AGENT_DIR is the authority-verified generated config.
    environment["PI_CODING_AGENT_DIR"] = generated_config.config_dir
    environment["PI_OFFLINE"] = "1"
    environment["PI_SKIP_VERSION_CHECK"] = "1"
    environment["PI_TELEMETRY"] = "0"

    # The one credential carrier, sourced ONLY from secret_context.api_key.
    environment[CREDENTIAL_ENV_VAR_NAME] = credential_value

    violations = [
        name
        for name in environment
        if name != CREDENTIAL_ENV_VAR_NAME
        and any(fragment in name.upper() for fragment in FORBIDDEN_NAME_FRAGMENTS)
    ]
    if violations:
        raise EnvironmentPolicyError(
            "environment error: the built environment contains withheld names: "
            + ", ".join(sorted(violations))
        )

    return LaunchEnvironment(
        _raw_environment=environment,
        included_names=tuple(sorted(environment)),
        path_narrowed=True,
        path_entry_count=len([p for p in environment["PATH"].split(os.pathsep) if p]),
        pi_config_dir=generated_config.config_dir,
    )


def audit_withheld_names(
    *, ambient_environ: Mapping[str, str], built_environment: Mapping[str, str]
) -> dict[str, object]:
    """Prove, by NAME only, that sensitive ambient variables were not forwarded.

    Takes the ambient mapping as an explicit argument -- never reads
    ``os.environ`` -- so this audit itself is fully offline-testable against
    synthetic decoy environments. ``built_environment`` may be a plain
    ``dict`` or the read-only ``MappingProxyType`` view
    ``LaunchEnvironment.environment`` exposes -- both support the
    read-only operations this function performs.
    """
    present_in_ambient = sorted(
        name
        for name in ambient_environ
        if any(fragment in name.upper() for fragment in FORBIDDEN_NAME_FRAGMENTS)
    )
    leaked = sorted(name for name in present_in_ambient if name in built_environment)
    profile_leaked = sorted(
        name for name in WITHHELD_PROFILE_NAMES if name in built_environment
    )
    return {
        "sensitive_ambient_names_detected_count": len(present_in_ambient),
        "sensitive_names_forwarded_to_child": leaked,
        "sensitive_names_forwarded_count": len(leaked),
        "profile_names_forwarded_to_child": profile_leaked,
        "note": (
            "Names only. No environment value was read from a real process, "
            "recorded, or printed. The single credential carrier is excepted by "
            "exact identity and always carries the real B300 credential value, "
            "never a placeholder."
        ),
    }
