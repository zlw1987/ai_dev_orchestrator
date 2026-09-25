"""CFG1-owned independent pins for the L11 extension inputs (FU1 AM-14).

Design ``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` (R6) Sec. 9.2c-D.
Every value here is a LITERAL recorded from the reviewed bytes -- reviewer-
confirmed against frozen commit ``bfae384370246e0ab4073a28a6b6df0558153864``
(``lf`` line endings, each ``HEAD`` blob hashing to the same value). None of it
is derived at run time from the sources it pins, from the frozen AR2 writer, or
from CFG1's own serializer: an expected value computed from the thing under
test would be tautological agreement, which is exactly what B16 rejected.

**What these pins prove.** At L11 each static source is read ONCE; only bytes
whose exact length and SHA-256 equal the pin below are buffered, and only the
buffer is ever written (never the source pathname re-opened). The generated
``ar2_config.ts`` is produced from a template whose UTF-8 encoding matches
:data:`GENERATED_CONFIG_TEMPLATE_SHA256` and whose structure has exactly one
``%s`` and no other ``%``. They do NOT prove the reviewed bytes are the right
bytes (review does), that Pi loads only these files (OC-2), or anything about a
transient swap after the writer's own read-back.

This module is part of the audited source lineage: ``run_executor`` imports
it at module import, so the launcher's G4 import of the executor loads it and
G5 audits its origin with every other CFG1 module (Test Z asserts that).
"""

from __future__ import annotations

#: The strict four-name static-source set, in the fixed read/write order --
#: exactly the frozen ``ar2.pi_config.EXTENSION_SOURCE_FILES``. Never a
#: directory listing, a glob, or an extra name.
EXTENSION_SOURCE_NAMES: tuple[str, ...] = ("ipc.ts", "tools.ts", "index.ts", "package.json")

#: name -> (exact byte size, SHA-256 of the reviewed bytes).
PINNED_EXTENSION_SOURCES: dict[str, tuple[int, str]] = {
    "ipc.ts": (8589, "789831482abf353254aa2ff5af20d90634f2caad1fa7366bfe7776c4a35c2024"),
    "tools.ts": (5896, "c03de727ae73d58babef459c753852a7b53439ddd1c0db571a2f0443abe9f5b4"),
    "index.ts": (2182, "ffc2dee8198d51f0f914a67a2370e1149040e0616f8789526b9253f53bcfcb3c"),
    "package.json": (295, "4571c0f2552eefaadd40a99885f4d73930bfb540fe9ece4f23fed6a4a05058fc"),
}

#: The frozen ``_GENERATED_CONFIG_HEADER``: its UTF-8 encoding is exactly this
#: many bytes with this SHA-256, containing exactly one ``%s`` and no other
#: ``%`` (the structure rule).
GENERATED_CONFIG_TEMPLATE_BYTES = 748
GENERATED_CONFIG_TEMPLATE_SHA256 = (
    "819f1f1d7909020a701d9527f37138ecaab08494d3ad06923863bf407043094f"
)

#: The name of the one token-bearing generated file.
GENERATED_CONFIG_NAME = "ar2_config.ts"

#: The experiment literal the generated binding carries (unchanged from the
#: frozen CFG1 binding).
EXTENSION_EXPERIMENT_ID = "pi_harness_cfg1"

# ---------------------------------------------------------------------------
# The FROZEN golden output vector (R6/B18) -- design literals, not selections.
# The inputs are synthetic and non-secret; the real experiment id is
# deliberately not used. The pipe name is 27 characters: two backslashes,
# ".", a backslash, "pipe", a backslash, "golden_vector_pipe".
# ---------------------------------------------------------------------------

GOLDEN_VECTOR_EXPERIMENT_ID = "golden_vector_experiment"
GOLDEN_VECTOR_PIPE_NAME = "\\\\.\\pipe\\golden_vector_pipe"
GOLDEN_VECTOR_CAPABILITY_ID = "golden-capability-0001"
GOLDEN_VECTOR_TOKEN = "golden-vector-token-not-a-secret-0000"

#: SHA-256 of the 962 on-disk (CRLF) bytes -- the frozen literal.
GOLDEN_VECTOR_ON_DISK_SHA256 = (
    "e7916cd3c878626369684cde06e0919d15affaea80f9700871024999ee163715"
)
GOLDEN_VECTOR_ON_DISK_BYTES = 962
