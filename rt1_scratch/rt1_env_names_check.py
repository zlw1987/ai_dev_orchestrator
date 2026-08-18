"""RT1 SYNTHETIC TRIAL SCRATCH — env-var NAME presence check only.

Prints only variable NAMES and whether they are defined. Never prints a value.
"""

import os
import sys

NAMES = (
    "AIDO_LITELLM_BASE_URL",
    "AIDO_LITELLM_API_KEY",
    "AIDO_LITELLM_DEFAULT_MODEL",
    "AIDO_LITELLM_TIMEOUT_SECONDS",
    "AIDO_LITELLM_MAX_RETRIES",
)

missing = []
for name in NAMES:
    defined = bool(os.environ.get(name, "").strip())
    print(f"{name}: {'DEFINED' if defined else 'MISSING_OR_BLANK'}")
    if not defined:
        missing.append(name)

print(f"python_executable: {sys.executable}")
print(f"python_version: {sys.version.split()[0]}")
try:
    import ai_dev_orchestrator

    print(f"ai_dev_orchestrator: IMPORTABLE ({ai_dev_orchestrator.__file__})")
except Exception as exc:  # pragma: no cover - scratch script
    print(f"ai_dev_orchestrator: NOT IMPORTABLE ({type(exc).__name__})")

print("MISSING_REQUIRED: " + (",".join(m for m in missing if m in NAMES[:3]) or "none"))
