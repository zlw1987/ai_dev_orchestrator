"""The CFG1-owned Pi child-environment builder. Equal to I2's policy, by value.

Design Sec. 7.4 ("child-environment builder: equal to I2's policy for identical
inputs (T-4)"). The frozen I2 builder cannot be reused directly -- it accepts
only an I2-issued ``GeneratedQualificationConfig`` and an I2 secret context --
so CFG1 owns this one. Its POLICY is identical, and T-4 proves that by
comparing the built name set and every non-secret value.

**Never reads ``os.environ``.** Every ambient value is supplied by the caller as
an explicit mapping, so the whole builder is testable against synthetic decoy
environments and never touches, dumps, or prints a real process environment.

The allowlist is POSITIVE: a small Windows baseline, a narrowed PATH, four
Pi-owned variables, and exactly one credential carrier. Everything else --
including ``USERPROFILE``/``HOME``/``APPDATA`` and every name matching a
forbidden fragment -- is withheld by construction, and the result is re-audited
by NAME before it is returned.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .cfg1_pi_config import GeneratedCfg1Config
from .config_issuance import verify_config_issuance
from .identity import CREDENTIAL_ENV_VAR_NAME

#: Identical VALUES to AR2's and I2's own baseline, duplicated here as
#: CFG1-owned data -- never an import dependency on a frozen module's internals.
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

#: Profile names this builder NEVER forwards, by construction. Listed only so a
#: regression can assert the withholding by name.
WITHHELD_PROFILE_NAMES: tuple[str, ...] = ("USERPROFILE", "HOME", "APPDATA")

#: Checked by NAME only, never by value -- a policy that inspected values would
#: have to read them first.
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


class Cfg1EnvironmentPolicyError(Exception):
    """The child environment could not be built without violating policy."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 child environment refused: {reason_code}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class Cfg1LaunchEnvironment:
    """The built environment, exposed read-only, plus a by-name audit.

    ``frozen=True`` only blocks attribute REASSIGNMENT, never mutation of a
    mutable object a field already points at -- so the raw dict is private and
    the public view is a ``MappingProxyType``. A caller that genuinely needs a
    mutable mapping for a subprocess boundary takes an independent snapshot.
    """

    _raw_environment: dict[str, str] = field(repr=False)
    included_names: tuple[str, ...]
    path_entry_count: int
    pi_config_dir: str = field(repr=False)

    @property
    def environment(self) -> Mapping[str, str]:
        return MappingProxyType(self._raw_environment)

    def as_launch_snapshot(self) -> dict[str, str]:
        return dict(self._raw_environment)

    def __repr__(self) -> str:  # noqa: D105 - paths and values are never rendered
        return (
            f"{type(self).__name__}(included_names={self.included_names!r}, "
            f"path_entry_count={self.path_entry_count!r}, pi_config_dir=<bound>)"
        )


def _narrowed_path(
    node_executable: str, git_executable: str | None, ambient_environ: Mapping[str, str]
) -> str:
    """A PATH holding only the Node directory, Git, and the system directory."""
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


def build_cfg1_child_environment(
    *,
    ambient_environ: Mapping[str, str],
    node_executable: str,
    generated_config: GeneratedCfg1Config,
    workspace,
    credential_value: str,
    git_executable: str | None = None,
) -> Cfg1LaunchEnvironment:
    """Build the explicit, positive-allowlist Pi child environment for one run.

    ``PI_CODING_AGENT_DIR`` has exactly ONE source: the generated config's own
    directory, RE-VERIFIED here at this consumption boundary against CFG1's
    issuance registry -- bound to ``workspace``'s own ownership handle, never
    a bare path -- before it is trusted. Neither a global ``~/.pi/agent``
    directory nor an arbitrary sibling config can reach the child through this
    API, because there is no parameter through which one could be named, and a
    genuine config minted for a DIFFERENT workspace is refused here even when
    its recorded paths happen to match (CFG1-IMPL-FU1 Finding 2).

    This builder takes no arm parameter, so arm symmetry is structural: R, E
    and H differ from Q ONLY inside the generated ``models.json``, never in the
    environment the child is launched with.
    """
    verify_config_issuance(token=generated_config.issuance_token, workspace=workspace)
    if type(credential_value) is not str or not credential_value.strip():
        # Defensive: this route has no keyless mode, and a blank carrier would
        # look like a successful launch while authenticating nothing.
        raise Cfg1EnvironmentPolicyError("BLANK_CREDENTIAL_CARRIER")

    environment: dict[str, str] = {
        name: ambient_environ[name] for name in BASE_WINDOWS_NAMES if name in ambient_environ
    }
    environment["PATH"] = _narrowed_path(node_executable, git_executable, ambient_environ)
    environment["PI_CODING_AGENT_DIR"] = generated_config.config_dir
    environment["PI_OFFLINE"] = "1"
    environment["PI_SKIP_VERSION_CHECK"] = "1"
    environment["PI_TELEMETRY"] = "0"
    environment[CREDENTIAL_ENV_VAR_NAME] = credential_value

    violations = [
        name
        for name in environment
        if name != CREDENTIAL_ENV_VAR_NAME
        and any(fragment in name.upper() for fragment in FORBIDDEN_NAME_FRAGMENTS)
    ]
    if violations:
        raise Cfg1EnvironmentPolicyError("WITHHELD_NAME_PRESENT")

    return Cfg1LaunchEnvironment(
        _raw_environment=environment,
        included_names=tuple(sorted(environment)),
        path_entry_count=len([p for p in environment["PATH"].split(os.pathsep) if p]),
        pi_config_dir=generated_config.config_dir,
    )


def audit_withheld_names(
    *, ambient_environ: Mapping[str, str], built_environment: Mapping[str, str]
) -> dict[str, object]:
    """Prove, by NAME only, that sensitive ambient variables were not forwarded."""
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
            "recorded, or printed."
        ),
    }
