"""Typed planner errors and a strict output parser for model-backed L1 planning.

Phase 4F: exception classes plus one **pure** function. This module implements
the "output parser" box of
[PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md](../../../docs/PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md)
§3.4/§6 and nothing else. It makes **no** model call, constructs **no**
``LLMClient``, imports **no** transport (`httpx`), makes **no** network call,
reads **no** environment variable, performs **no** file IO, and performs **no**
workspace path resolution/stat/normalization. Path-like values are handled as
plain strings only, exactly as in Phase 4B/4C.

The parser is deliberately strict and **rejects rather than repairs** (design
§3.5): the completion must be exactly one JSON object — no markdown fences, no
prose before or after, no arrays or scalars, no extra top-level keys, no missing
required keys. The caller-controlled ("trusted") fields ``issue_number``,
``repo``, ``title``, ``automation_level`` and ``requires_human_approval`` are
never read from model output; they are supplied by the caller, and a response
that tries to set them is rejected so prompt-injection attempts surface instead
of being silently dropped.

The policy guard (:data:`_POLICY_RULES`) is a small, deterministic, deliberately
**conservative** phrase check for obvious forbidden proposals — command
execution, direct file edits, branch creation, PRs, GitHub writes, workspace
file reads, automation escalation, or skipping human approval. It is not
security NLP, and it does not interpret negation: a response that merely
*mentions* one of those actions, even to disclaim it, is rejected. That
trade-off is intentional — a rejected plan is reviewed by a human, never
sanitized and passed on.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from ai_dev_orchestrator.plan.models import L1Plan


class ModelPlannerError(Exception):
    """Base class for all model-backed planner errors.

    Messages never include an API key, and never echo the full prompt or the
    full completion.
    """


class ModelPlannerParseError(ModelPlannerError):
    """The completion was not exactly one strict JSON object."""


class ModelPlannerValidationError(ModelPlannerError):
    """The decoded object had the wrong keys, wrong types, or failed ``L1Plan``."""


class ModelPlannerPolicyError(ModelPlannerError):
    """The completion parsed cleanly but proposed forbidden (non-L1) behavior."""


# Fields the caller owns. They are never read from model output, and their
# presence in a response is treated as an injection attempt (design §3.4/§4.5).
_TRUSTED_FIELDS = (
    "issue_number",
    "repo",
    "title",
    "automation_level",
    "requires_human_approval",
)

# Fields the model must supply, exactly — no more, no less.
_REQUIRED_STRING_FIELDS = (
    "summary",
    "scope_summary",
)
_REQUIRED_LIST_FIELDS = (
    "non_goals",
    "proposed_steps",
    "files_likely_to_change",
    "files_forbidden_or_out_of_scope",
    "required_verification",
    "risks",
    "open_questions",
)
_REQUIRED_MODEL_FIELDS = _REQUIRED_STRING_FIELDS + _REQUIRED_LIST_FIELDS

# (compiled pattern, human-readable reason). Matched case-insensitively against
# each model-controlled string. Conservative by design; see the module docstring.
_POLICY_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), reason)
    for pattern, reason in (
        # Automation escalation above L1.
        (
            r"automation[ _-]*level[^.\n]{0,40}\bl[234]\b",
            "proposes an automation level above L1",
        ),
        (r"\bl[234]\b[^.\n]{0,40}\bautomation\b", "proposes L2+ automation"),
        (
            r"\b(?:escalat|upgrad|promot|elevat)\w*\b[^.\n]{0,40}\bl[234]\b",
            "proposes escalating the automation level",
        ),
        (r"\bl[234]\s+(?:automation|mode|level)\b", "proposes L2+ automation"),
        # Human approval removal.
        (
            r"requires?[ _-]*human[ _-]*approval[^.\n]{0,20}(?:false|no\b|not\b)",
            "proposes marking the plan as not requiring human approval",
        ),
        (
            r"\b(?:without|no|skip|skipping|bypass|bypassing|waive|waiving)\b"
            r"[^.\n]{0,20}human[ _-]*(?:approval|review|sign[ -]?off)",
            "proposes proceeding without human approval",
        ),
        (
            r"human[ _-]*(?:approval|review)[^.\n]{0,20}(?:is |are )?"
            r"not (?:required|needed|necessary)",
            "proposes that human approval is not required",
        ),
        (
            r"\bauto[ -]?(?:approve|approved|approval|merge|merged)\b",
            "proposes auto-approval or auto-merge",
        ),
        # Command execution.
        (
            r"\b(?:run|runs|running|execute|executes|executing|invoke|invoking|"
            r"launch|launching|spawn|spawning)\b[^.\n]{0,30}\b(?:command|commands|"
            r"shell|bash|powershell|cmd\.exe|terminal|cli|script|scripts)\b",
            "proposes executing a shell/CLI command",
        ),
        (
            r"\b(?:shell|bash|powershell|terminal|cli)\s+command",
            "proposes a shell/CLI command",
        ),
        (
            r"\b(?:os\.system|subprocess\.(?:run|popen|call|check_output))\b",
            "proposes executing a process",
        ),
        # Direct file editing.
        (
            r"\b(?:edit|edits|editing|modify|modifies|modifying|patch|patching|"
            r"rewrite|rewriting|overwrite|overwriting|write|writing|delete|"
            r"deleting)\b[^.\n]{0,25}\bfiles?\b[^.\n]{0,25}"
            r"\b(?:directly|myself|automatically|for you|on your behalf)\b",
            "proposes editing files directly",
        ),
        (
            r"\bapply\b[^.\n]{0,25}\b(?:patch|diff|changes?|edits?)\b",
            "proposes applying edits directly",
        ),
        (
            r"\bi\s+(?:will|can|have|already|am going to)\s+"
            r"(?:edit|modify|write|patch|change|update|create|delete)\b",
            "proposes performing the change itself",
        ),
        # Branch creation.
        (
            r"\b(?:create|creating|make|making|cut|cutting|check\s?out|switch)\b"
            r"[^.\n]{0,25}\bbranch\b",
            "proposes creating a branch",
        ),
        (r"\bnew\s+branch\b", "proposes creating a branch"),
        (r"\bgit\s+(?:checkout|switch|branch|commit|push)\b", "proposes a git write"),
        # Pull requests.
        (
            r"\b(?:open|opens|opening|create|creates|creating|submit|submitting|"
            r"raise|raising|merge|merging)\b[^.\n]{0,25}"
            r"\b(?:pull[ -]request|merge[ -]request|prs?)\b",
            "proposes opening or merging a pull request",
        ),
        (r"\bgh\s+pr\b", "proposes a GitHub pull-request write"),
        # GitHub comments / labels / issue writes.
        (
            r"\b(?:post|posts|posting|add|adds|adding|leave|leaving|write|writes|"
            r"writing|create|creating)\b[^.\n]{0,20}\bcomments?\b",
            "proposes writing a GitHub comment",
        ),
        (r"\bcomment\s+on\s+(?:the\s+)?issue\b", "proposes writing a GitHub comment"),
        (
            r"\b(?:add|adds|adding|apply|applies|applying|set|sets|setting|remove|"
            r"removes|removing)\b[^.\n]{0,20}\blabels?\b[^.\n]{0,20}\bissue\b",
            "proposes writing GitHub labels",
        ),
        (r"\blabel\s+the\s+issue\b", "proposes writing GitHub labels"),
        (
            r"\b(?:close|closes|closing|reopen|reopens|reopening|edit|edits|editing|"
            r"update|updates|updating)\s+(?:the\s+)?issue\b",
            "proposes writing to the GitHub issue",
        ),
        (
            r"\bgithub\b[^.\n]{0,30}\b(?:write|writes|writing|post|posting|"
            r"comment|label)\b",
            "proposes a GitHub write",
        ),
        # Target workspace reads.
        (
            r"\b(?:read|reads|reading|open|opens|opening|list|lists|listing|scan|"
            r"scans|scanning|inspect|inspects|inspecting|browse|browsing|traverse|"
            r"traversing)\b[^.\n]{0,30}\b(?:workspace|working\s+directory|"
            r"file\s+tree|directory\s+tree|repository\s+tree|source\s+files?|"
            r"file\s+contents?)\b",
            "proposes reading target workspace files",
        ),
        (
            r"\b(?:read|reads|reading)\b[^.\n]{0,30}\b(?:repo|repository)\s+files?\b",
            "proposes reading target workspace files",
        ),
    )
)


def _decode_strict_json_object(text: str) -> dict:
    """Decode exactly one strict JSON object, or raise :class:`ModelPlannerParseError`."""
    if not isinstance(text, str):
        raise ModelPlannerParseError("model output must be a string.")

    # Only surrounding whitespace is tolerated. Markdown fences, prose before or
    # after the object, and trailing content all fail here or in ``json.loads``.
    stripped = text.strip()
    if not stripped:
        raise ModelPlannerParseError("model output was empty.")
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise ModelPlannerParseError(
            "model output must be exactly one JSON object with no markdown "
            "fences, prose, or other content around it."
        )

    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ModelPlannerParseError(f"model output is not valid JSON: {exc}") from exc

    if not isinstance(decoded, dict):
        raise ModelPlannerParseError(
            "model output must be a JSON object, not an array, string, number, "
            "boolean, or null."
        )
    return decoded


def _check_keys(decoded: dict) -> None:
    """Enforce the strict key set: no trusted fields, no extras, nothing missing."""
    keys = set(decoded)

    trusted_present = [name for name in _TRUSTED_FIELDS if name in keys]
    if trusted_present:
        raise ModelPlannerValidationError(
            "model output must not supply caller-controlled field(s): "
            + ", ".join(trusted_present)
            + "."
        )

    unexpected = sorted(keys - set(_REQUIRED_MODEL_FIELDS))
    if unexpected:
        raise ModelPlannerValidationError(
            "model output has unexpected top-level key(s): " + ", ".join(unexpected) + "."
        )

    missing = [name for name in _REQUIRED_MODEL_FIELDS if name not in keys]
    if missing:
        raise ModelPlannerValidationError(
            "model output is missing required field(s): " + ", ".join(missing) + "."
        )


def _check_types(decoded: dict) -> None:
    """Enforce the coarse JSON types before the values are scanned or validated."""
    for name in _REQUIRED_STRING_FIELDS:
        if not isinstance(decoded[name], str):
            raise ModelPlannerValidationError(f"{name} must be a JSON string.")

    for name in _REQUIRED_LIST_FIELDS:
        value = decoded[name]
        if not isinstance(value, list):
            raise ModelPlannerValidationError(f"{name} must be a JSON array.")
        if not all(isinstance(item, str) for item in value):
            raise ModelPlannerValidationError(f"{name} items must be JSON strings.")


def _check_policy(decoded: dict) -> None:
    """Reject obvious proposals of forbidden, non-L1 behavior.

    Only model-controlled values are scanned; caller-supplied forbidden paths are
    merged in afterwards and are never scanned.
    """
    for name in _REQUIRED_MODEL_FIELDS:
        value = decoded[name]
        items = [value] if isinstance(value, str) else value
        for item in items:
            for pattern, reason in _POLICY_RULES:
                if pattern.search(item):
                    raise ModelPlannerPolicyError(
                        f"model output rejected by planner policy: {name} {reason}. "
                        "An L1 plan is descriptive text only."
                    )


def _merge_forbidden_paths(
    project_forbidden_paths: list[str] | None,
    model_forbidden_paths: list[str],
) -> list[str]:
    """Merge caller and model forbidden paths verbatim, order-preserving, deduplicated.

    The strings are copied as-is: never resolved, ``stat``'d, globbed, or
    normalized (Phase 4B/4C rule).
    """
    merged: list[str] = []
    for path in list(project_forbidden_paths or []) + list(model_forbidden_paths):
        if path not in merged:
            merged.append(path)
    return merged


def parse_model_l1_plan_response(
    text: str,
    *,
    issue_number: int,
    repo: str,
    title: str,
    project_forbidden_paths: list[str] | None = None,
) -> L1Plan:
    """Parse a strict-JSON model completion into a validated :class:`L1Plan`.

    Pure function: no file IO, no environment reads, no network, no model client,
    and no workspace path operations.

    ``issue_number``, ``repo`` and ``title`` are taken from the arguments;
    ``automation_level`` is always ``"L1"`` and ``requires_human_approval`` is
    always ``True``. None of those five are ever read from ``text``.

    Raises:
        ModelPlannerParseError: ``text`` is not exactly one strict JSON object.
        ModelPlannerValidationError: wrong keys/types, or the final ``L1Plan``
            fails validation.
        ModelPlannerPolicyError: the response proposes forbidden, non-L1 behavior.
    """
    decoded = _decode_strict_json_object(text)
    _check_keys(decoded)
    _check_types(decoded)
    _check_policy(decoded)

    files_forbidden_or_out_of_scope = _merge_forbidden_paths(
        project_forbidden_paths,
        decoded["files_forbidden_or_out_of_scope"],
    )

    try:
        return L1Plan(
            issue_number=issue_number,
            repo=repo,
            title=title,
            summary=decoded["summary"],
            scope_summary=decoded["scope_summary"],
            non_goals=list(decoded["non_goals"]),
            proposed_steps=list(decoded["proposed_steps"]),
            files_likely_to_change=list(decoded["files_likely_to_change"]),
            files_forbidden_or_out_of_scope=files_forbidden_or_out_of_scope,
            required_verification=list(decoded["required_verification"]),
            risks=list(decoded["risks"]),
            open_questions=list(decoded["open_questions"]),
            automation_level="L1",
            requires_human_approval=True,
        )
    except ValidationError as exc:
        raise ModelPlannerValidationError(
            f"model output failed L1Plan validation: {exc}"
        ) from exc
