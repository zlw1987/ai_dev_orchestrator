"""The explicit minimal launch environment for the Pi process.

Why this is load-bearing rather than cosmetic (AR0 section 3.15, verified in
Pi's shipped ``harness/env/nodejs.js``)::

    function getShellEnv(baseEnv, extraEnv, inheritEnv = true) {
        if (!inheritEnv) return { ...extraEnv };
        return { ...process.env, ...baseEnv, ...extraEnv };
    }

Whatever environment AIDO gives Pi is the environment a model-authored shell
command would receive. AR2 exposes no ``bash`` tool at all, which removes that
particular path -- but the minimal environment stands anyway, because it is also
what a defective or future-widened tool would inherit.

NEVER a copy of ``os.environ``. Values are read only for allowlisted names, and
only NAMES are ever recorded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Windows process variables Node/Pi plausibly need. Probed empirically by the
# harness: the run starts from the strongest (smallest) set and only widens if
# Pi genuinely cannot start.
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

# The profile variables whose necessity is AR0 unknown U-4. Withholding them is
# the strong choice: on Windows Node's os.homedir() reads USERPROFILE, so
# withholding it is a second, independent barrier against ~/.pi/agent resolution
# even if PI_CODING_AGENT_DIR redirection were incomplete (U-3).
PROFILE_NAMES_UNDER_TEST: tuple[str, ...] = ("USERPROFILE", "HOME", "APPDATA")

# Names that must never reach the Pi process, checked by fragment after the
# allowlist is applied. Mirrors the accepted verification-runner discipline.
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

# The non-secret compatibility placeholder Pi's model catalog needs so a keyless
# server's model is considered "has auth configured" and becomes selectable.
#
# THIS IS NOT AUTHENTICATION AND NOT A CREDENTIAL. It is the same shape as the
# accepted 5F2E-V1 ``no_api_key`` rule, and the same wording discipline applies.
ROUTE_PLACEHOLDER_ENV_NAME = "AR2_ROUTE_PLACEHOLDER_KEY"
ROUTE_PLACEHOLDER_VALUE = "no_api_key"


class EnvironmentPolicyError(Exception):
    """The launch environment could not be built without violating the policy."""


@dataclass(frozen=True)
class LaunchEnvironment:
    """The explicit environment plus an audit of what was and was not included."""

    environment: dict[str, str]
    included_names: tuple[str, ...]
    profile_names_included: tuple[str, ...]
    profile_names_withheld: tuple[str, ...]
    path_narrowed: bool
    path_entry_count: int


def _narrowed_path(node_executable: str, git_executable: str | None) -> str:
    """A PATH holding only the Node directory, Git, and the system directory.

    AR0 unknown U-2. Started narrow deliberately; the harness widens only if
    startup genuinely fails, and records the minimum that worked.
    """
    system_root = os.environ.get("SystemRoot") or r"C:\Windows"
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


def build_launch_environment(
    *,
    node_executable: str,
    pi_config_dir: str,
    git_executable: str | None = None,
    include_profile_names: tuple[str, ...] = (),
    narrow_path: bool = True,
) -> LaunchEnvironment:
    """Build the explicit Pi launch environment.

    ``include_profile_names`` must be a subset of :data:`PROFILE_NAMES_UNDER_TEST`
    and starts empty. The harness adds the minimum required, one at a time, and
    records the fact.
    """
    for name in include_profile_names:
        if name not in PROFILE_NAMES_UNDER_TEST:
            raise EnvironmentPolicyError(
                f"environment error: {name!r} is not one of the profile names under test"
            )

    environment: dict[str, str] = {
        name: os.environ[name] for name in BASE_WINDOWS_NAMES if name in os.environ
    }
    for name in include_profile_names:
        if name in os.environ:
            environment[name] = os.environ[name]

    environment["PATH"] = (
        _narrowed_path(node_executable, git_executable)
        if narrow_path
        else os.environ.get("PATH", "")
    )

    # Pi-owned, deliberately set.
    environment["PI_CODING_AGENT_DIR"] = pi_config_dir
    environment["PI_OFFLINE"] = "1"
    environment["PI_SKIP_VERSION_CHECK"] = "1"
    environment["PI_TELEMETRY"] = "0"

    # The one route variable. Its value is the fixed non-secret placeholder, and
    # the endpoint is not an environment variable at all -- it is written into
    # the disposable models.json.
    environment[ROUTE_PLACEHOLDER_ENV_NAME] = ROUTE_PLACEHOLDER_VALUE

    violations = [
        name
        for name in environment
        if name != ROUTE_PLACEHOLDER_ENV_NAME
        and any(fragment in name.upper() for fragment in FORBIDDEN_NAME_FRAGMENTS)
    ]
    if violations:
        raise EnvironmentPolicyError(
            "environment error: the built environment contains withheld names: "
            + ", ".join(sorted(violations))
        )

    withheld = tuple(n for n in PROFILE_NAMES_UNDER_TEST if n not in include_profile_names)
    return LaunchEnvironment(
        environment=environment,
        included_names=tuple(sorted(environment)),
        profile_names_included=tuple(include_profile_names),
        profile_names_withheld=withheld,
        path_narrowed=narrow_path,
        path_entry_count=len([p for p in environment["PATH"].split(os.pathsep) if p]),
    )


def audit_withheld_names(environment: dict[str, str]) -> dict[str, object]:
    """Prove, by NAME only, that sensitive process variables were not forwarded.

    No value from ``os.environ`` is read here, and no value is recorded.
    """
    present_in_process = sorted(
        name
        for name in os.environ
        if any(fragment in name.upper() for fragment in FORBIDDEN_NAME_FRAGMENTS)
    )
    leaked = sorted(name for name in present_in_process if name in environment)
    return {
        "sensitive_process_env_names_detected_count": len(present_in_process),
        "sensitive_names_forwarded_to_runtime": leaked,
        "sensitive_names_forwarded_count": len(leaked),
        "note": (
            "Names only. No environment value was read, recorded, or printed. "
            "The single route variable carries a fixed non-secret placeholder, "
            "never a credential."
        ),
    }
