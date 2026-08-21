"""Phase 5F3A-AR1 - Pi external runtime synthetic PoC (EXPERIMENT ONLY).

This package is not production code. It adds no ``ProjectConfig`` field, no CLI
command, and no production Pi support. It lives outside ``src/`` deliberately
(AR0-FU1 section 10), and it may be deleted wholesale.
"""

EXPERIMENT_ID = "5F3A-AR1"
# v2 (AR1-FU1): fail-closed H1 extension-identity gate; scrub-check findings are
# bounded codes, never raw needles; a scrub failure emits a refusal record
# instead of the candidate. The accepted historical v1 live record is
# unmodified and keeps its v1 meaning; see FINDINGS.md.
EXPERIMENT_RECORD_VERSION = "ar1-run-record.v2"
