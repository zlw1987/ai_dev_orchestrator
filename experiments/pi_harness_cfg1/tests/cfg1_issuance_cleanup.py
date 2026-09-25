"""TEST-ONLY issuance cleanup (FU1-AUTH-2). Never imported by production code.

Production has no token-only retirement: a token is a lookup key, not
authority. Tests that generate an issuance directly and never run L24 still
must not strand the retained handle, so this helper reaches into the private
registries -- exactly the private-registry manipulation the threat model
excludes for callers, and lives here, outside the package, for that reason.
"""

from __future__ import annotations

from pi_harness_cfg1 import config_issuance, extension_issuance
from pi_harness_cfg1 import win_config_authority as win


def discard_config_for_test(token: object) -> bool:
    if type(token) is not str:
        return False
    record = config_issuance._ISSUED.pop(token, None)
    return record is not None and win.scrub_retire_retained(record.retained)


def discard_extension_for_test(token: object) -> bool:
    if type(token) is not str:
        return False
    record = extension_issuance._ISSUED_EXTENSIONS.pop(token, None)
    return record is not None and win.scrub_retire_retained(record.retained)
