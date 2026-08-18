"""RT1 SYNTHETIC TRIAL SCRATCH — persistent env-var NAME presence check.

Reports ONLY whether the required reviewer variable NAMES exist in the current
process environment and in the persistent user/machine environment scopes.
It never prints, logs, or returns any value.
"""

import os
import winreg

NAMES = (
    "AIDO_LITELLM_BASE_URL",
    "AIDO_LITELLM_API_KEY",
    "AIDO_LITELLM_DEFAULT_MODEL",
)

SCOPES = (
    ("user", winreg.HKEY_CURRENT_USER, r"Environment"),
    (
        "machine",
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
    ),
)


def names_in(root, subkey):
    found = set()
    try:
        with winreg.OpenKey(root, subkey) as key:
            index = 0
            while True:
                try:
                    name, _value, _kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                found.add(name.upper())
                index += 1
    except OSError:
        return None
    return found


scope_names = {label: names_in(root, sub) for label, root, sub in SCOPES}

for name in NAMES:
    parts = [f"process={'yes' if os.environ.get(name, '').strip() else 'no'}"]
    for label, found in scope_names.items():
        if found is None:
            parts.append(f"{label}=unreadable")
        else:
            parts.append(f"{label}={'yes' if name.upper() in found else 'no'}")
    print(f"{name}: " + " ".join(parts))
