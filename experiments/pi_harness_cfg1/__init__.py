"""Phase 5F3B-HARNESS-CFG1 -- the Pi launch-configuration isolation harness.

**Diagnostic lineage only. No qualification authority.** Nothing in this
package produces, amends, or feeds a qualification verdict, ranking, hard-bar
input, lineage record, or OBS1 companion artifact. It composes frozen modules
(``ar2``, ``qualification``, ``ai_dev_orchestrator.workspace.canonical``)
without modifying any of them.

Implements ``docs/PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md``
through ``5F3B-HARNESS-CFG1-DESIGN-FU14``, offline. The live Stage-1 and
Stage-2 experiments are **not** authorized by this package's existence; they
require ``5F3B-HARNESS-CFG1-LIVE-S1`` / ``-LIVE-S2`` (design Sec. 14.1).

This module deliberately declares only literals. Every mechanism lives in a
submodule, so importing the package name alone cannot pull in the live
runtime composition (``ar2.broker`` / ``ar2.supervisor``) as a side effect.
"""

from __future__ import annotations

#: The one experiment identifier every CFG1 durable record carries.
PACKAGE_ID = "pi_harness_cfg1"

#: The three durable record families (design Sec. 22.1 / 22.4.1 / 22.4.2).
#: Each is a CLOSED schema with its OWN independent validator -- never a
#: wrapper around another (Sec. 22.4.3).
RUN_RECORD_VERSION = "pi-harness-cfg1-run.v1"
REFUSAL_RECORD_VERSION = "pi-harness-cfg1-refusal.v1"
STAGE_CLOSURE_RECORD_VERSION = "pi-harness-cfg1-stage-closure.v1"

RUN_RECORD_KIND = "harness configuration diagnostic run"
REFUSAL_RECORD_KIND = "cfg1 artifact emission refusal"
STAGE_CLOSURE_RECORD_KIND = "cfg1 stage closure"

#: Design Sec. 16.3.8.1, Finding 4 (FU6): the EXACT integer, not "about 64 KiB".
#: Consumed at BOTH boundaries -- the writer's pre-create size check and the
#: post-hoc verifier's bounded read -- from this one declaration site.
MAX_CFG1_ARTIFACT_BYTES = 65536

#: The fixed ``claim_scope`` literal every CFG1 run record carries. States the
#: exact, narrow scope of what a CFG1 run can and cannot establish, so an
#: archived artifact is self-describing without this document.
CLAIM_SCOPE = (
    "CFG1 is a harness configuration diagnostic. It carries no qualification "
    "credit, no verdict, no ranking and no hard-bar input. Its only "
    "manipulated variable is the provider-level Pi compat object. Nothing here "
    "claims the request was observed on the wire, that the proxy forwarded it "
    "unchanged, that the backend honored the role or effort field, that "
    "backend inference stopped, or that any descendant process stopped. "
    "Verification is a controlled invocation of repository-controlled code, "
    "not sandboxed execution."
)

__all__ = [
    "PACKAGE_ID",
    "RUN_RECORD_VERSION",
    "REFUSAL_RECORD_VERSION",
    "STAGE_CLOSURE_RECORD_VERSION",
    "RUN_RECORD_KIND",
    "REFUSAL_RECORD_KIND",
    "STAGE_CLOSURE_RECORD_KIND",
    "MAX_CFG1_ARTIFACT_BYTES",
    "CLAIM_SCOPE",
]
