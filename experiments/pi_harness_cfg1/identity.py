"""Every pinned CFG1 identity literal, declared exactly once.

Design Sec. 8.3 ("frozen across all arms and runs") and Sec. 22.3's
"``model_id``, ``provider_id``, ``backend_gateway_class``, ``fixture_task_id``,
``fixture_revision`` equal their pinned literals".

Nothing here is read from the environment, a CLI flag, a config file, or an
authorization document. The future ``LIVE-S1``/``LIVE-S2`` authorization
supplies exactly one value -- a ``stage_execution_id`` literal -- and nothing
else (Sec. 14.1).
"""

from __future__ import annotations

#: The one diagnostic subject for the whole stage (Sec. 9). CFG1 grants it no
#: qualification credit, no verdict change, no ranking and no hard-bar input.
CFG1_MODEL_ID = "qwen3-coder-next"

#: The frozen qualification provider id, reused so the route identity CFG1
#: exercises is the same one Q1/Q2/Q3 exercised (Sec. 8.3).
PROVIDER_ID = "b300_pi_qualification"

#: The route class CFG1 runs over. Recorded as a bounded class literal, never
#: as a URL, host, port, or scheme (Sec. 21.2).
BACKEND_GATEWAY_CLASS = "b300_litellm_proxy"

#: The ONE environment name the generated ``models.json`` references through
#: exact ``$ENV_NAME`` interpolation. Its VALUE is never written to disk,
#: never digested, and never placed in any record or console line.
CREDENTIAL_ENV_VAR_NAME = "PI_QUALIFICATION_B300_ROUTE_KEY"

#: The ONE environment name the base URL is read from, at L4 only, after every
#: non-secret gate has already passed (Sec. 16.2 L4).
BASE_URL_ENV_VAR_NAME = "AIDO_LITELLM_BASE_URL"

#: The exact Pi release this design's seam digests and source derivations were
#: taken against (Sec. 1.2, Sec. 14.2). A mismatch refuses BEFORE any
#: credential read, and means the derivation must be re-reviewed -- never that
#: Pi is incompatible.
PINNED_PI_VERSION = "0.85.1"

#: The tool allowlist, frozen across every arm and run (Sec. 8.3). An
#: unregistered name never reaches an extension or the broker at all
#: (``agent-loop.js`` returns "Tool ... not found" inside the agent loop), so
#: a hallucinated call proves nothing about the intended AIDO tool path --
#: which is exactly why Sec. 12.1 row 6 routes any unexpected call to
#: indeterminate BEFORE ``ACTIVE``.
TOOL_ALLOWLIST: tuple[str, ...] = ("aido_read", "aido_edit")
