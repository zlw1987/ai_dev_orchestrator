"""Command-line interface for the AI Dev Orchestrator.

Commands: a `version` command, `inspect-issue` (read-only GitHub issue
inspection), `llm-smoke-test` (a fake-provider dry-run of the Phase 3C LLM
client — no real model call), `generate-plan` (an offline fake/deterministic L1
plan generator — Phase 4D, no GitHub fetch, no model call), `l2-dry-run` (an
offline validator that reports what a future L2 *would* have in scope — Phase
5C, no workspace access and no implementation), and the **three** commands that
may open a real socket, each only after every gate precondition passes:
`real-llm-smoke-test` (Phase 4K), `generate-model-plan` (Phase 4L) and
`l2-review-approved-file-edit` (Phase 5F2E).

`real-llm-smoke-test` is a **connectivity check, not a planner**: it sends a
fixed, harmless prompt, never issue text, and produces no plan.
`generate-model-plan` is the planner: it transmits the issue title and the body
text of the local file explicitly named on the command line, and nothing else —
no source files, no workspace contents, no directory listings, no git history.
Both require an explicit `--real-model` flag plus a project config that opts in
and allowlists the model. `l2-review-approved-file-edit` is the **reviewer**, and
the only one of the three that transmits source-derived text; it is gated by a
**separate** `controlled_review` project opt-in — `real_model_planning` does not
authorize it — plus two explicit flags, and it is described below.

Every other command remains offline in the sense that matters here: no GitHub
fetch happens in any gated command, and no model-backed implementer, fixer,
review/fix loop, GitHub write, branch, commit, push or PR is wired up anywhere.

**Three commands do act on explicitly approved artifacts**, and the older prose
claiming that nothing here edits a file or runs a command is history, not current
status. `l2-apply-approved-file-edit` (Phase 5F2C) writes one approved
modification to one tracked file, `l2-verify-approved-file-edit` (Phase 5F2D)
executes one project-configured verification process, and
`l2-review-approved-file-edit` (Phase 5F2E) runs that verification itself and
then sends the approved change to a project-configured reviewer model. All three
are described below. **L2 is still not complete**: there is no model-backed
implementer, no automatic fixer, and no branch, commit, push or PR.

`l2-dry-run` is the first command that reads an approved-plan artifact, and it
does exactly two file reads — the `--project-config` YAML and the
`--approved-plan` artifact, in that order — before printing the scope L2 *would*
be bounded by. `l2-dry-run` itself still takes **no** action: it inspects
nothing, proposes nothing, edits nothing, runs nothing, commits nothing.

`l2-inspect-workspace` (Phase 5D1) is the first command that may touch a
configured target workspace, and it touches it only as `stat`. It reads the
same two files, and then — behind `--apply-approved-plan`, `--inspect-workspace`,
a project-level `read_only_workspace_inspection` opt-in, artifact validation,
exact identity matching, candidate-count caps, the lexical Phase 1 path policy,
and the Phase 5D0 canonical guard — reports whether each path the plan names
exists, whether it is a file or a directory, and how big it is. **It reads no
file contents and lists no directory**, and it edits nothing, runs nothing, and
proposes nothing.

`generate-patch-proposal` (Phase 5E1) is the one command that produces a patch
**proposal** artifact. It reads the same two local files, generates the artifact
deterministically and offline from them, and prints it to stdout. **It is not a
diff and it is not file editing**: the artifact carries no unified diff, no
patch, no edit script, no file content, no command, and no command output — only
prose about paths the approved plan already named. It touches no workspace,
reads no file contents, calls no model, writes no file, and stamps no approval.

`l2-preview-file-edits` (Phase 5F1) is the first command that reads a Phase 5F0
**file-edit approval**, and it reads one only to describe a hypothetical. It
reads the same two local files, validates the approved diff proposal against the
project config and the lexical Phase 1 write policy, and prints what a future,
separately authorized write phase *would* be permitted to attempt — each
permitted path, its change type, and counts summarizing its diff. **It is not
file editing**: no diff is applied, whether a diff applies is never checked, no
command is run, and the configured target workspace is never read, listed,
stat'd, resolved, or canonicalized.

`l2-apply-approved-file-edit` (Phase 5F2C) is the one command that **writes** a
file, under the narrow contract of its own module.

`l2-verify-approved-file-edit` (Phase 5F2D) is the one command that **executes
repository-controlled code**. It launches the project's own configured
verification process — once, with an exact configured argv, in the canonical
workspace root, under an output bound and a bound on **AIDO's own wait** — but
only after proving the workspace still holds exactly the one approved
modification on a pinned HEAD commit, and it re-proves all of that afterwards.
Controlled invocation is **not** sandboxing: the project's own process is not
confined, its descendants are not tracked and may outlive the run, and the report
says so rather than claiming otherwise. Every AIDO-owned negative claim in that
report is scoped with an `orchestrator_` prefix, so no field can be misread as a
statement about the child. The command is separate from the writer on purpose,
and the L1 plan's `required_verification` is never command authority.

`l2-review-approved-file-edit` (Phase 5F2E) is the first command that
**deliberately sends source-derived code to a model**. It runs the Phase 5F2D
verification internally — there is no `--verification-result` input, and no saved
report is trusted as authority — and only after a `verified` outcome does it read
the **configured provider's** environment (the `AIDO_LITELLM_*` names, or the
`AIDO_VLLM_*` names, never both) and contact the project-configured reviewer. It
transmits one approved unified diff, selected approved-plan prose, and the
bounded, redacted verification output, all as delimited untrusted data; it never
transmits the full target file, unrelated source, a directory listing, git
history, an absolute path, or a credential. The reviewer's verdict is advisory:
`approve`, `changes_requested` and `needs_human_review` all end with a human, and
no fixer, re-review, patch, file edit, branch, commit, push or PR follows.

Phase 5F2E-V2 added one optional **generation constraint** to the direct-vLLM
path — `controlled_review.vllm_structured_output` sends the reviewer JSON Schema
in the OpenAI-compatible `response_format` field — because an observed trial
returned a semantically correct review wrapped in a markdown fence. The strict
parser is unchanged and still rejects rather than repairs, there is no fallback to
an unstructured request, and no CLI option was added for any of it.
"""

from __future__ import annotations

import enum
import json
import os
import sys
from pathlib import Path

import typer

from ai_dev_orchestrator import __version__
from ai_dev_orchestrator.redaction import (
    API_KEY_PLACEHOLDER,
    BEARER_TOKEN_RE,
    OPENAI_STYLE_KEY_RE,
    REDACTION_PLACEHOLDER,
    SECRET_ASSIGNMENT_RE,
    _replace_assignment_value as _shared_replace_assignment_value,
    redact_secret_like_text,
)

app = typer.Typer(
    name="ai-dev-orchestrator",
    help="Controlled AI software development pipeline orchestrator.",
    no_args_is_help=True,
    add_completion=False,
)


def _echo_json_model(model: object) -> None:
    """Echo a Pydantic model to stdout as ASCII-safe JSON.

    ``model.model_dump_json()`` emits raw Unicode by default, which crashes
    ``typer.echo`` under a non-UTF-8 Windows console codepage (e.g. cp1252)
    the moment reviewer-, model-, or subprocess-controlled text contains a
    character that codepage cannot represent. ``json.dumps`` defaults to
    ``ensure_ascii=True``, so every non-ASCII character is escaped
    (``\\u2192``) instead. The escaped text round-trips through
    ``json.loads`` to the exact original string, and remains valid
    ``review-packet``/report JSON.
    """
    typer.echo(json.dumps(model.model_dump(mode="json"), indent=2))


@app.callback()
def main() -> None:
    """Controlled AI software development pipeline orchestrator."""


@app.command()
def version() -> None:
    """Print the orchestrator version."""
    typer.echo(__version__)


@app.command("inspect-issue")
def inspect_issue(
    repo: str = typer.Option(..., "--repo", help="Repository as owner/repo."),
    issue: int = typer.Option(..., "--issue", help="Issue number to inspect."),
) -> None:
    """Read a GitHub issue (read-only) and report its parsed sections.

    Read-only: does not write to GitHub, call any model, or read/write any
    configured project workspace.
    """
    # Imported lazily so the rest of the CLI works without httpx installed.
    from ai_dev_orchestrator.github.client import GitHubClient, GitHubError
    from ai_dev_orchestrator.github.issue_parser import parse_issue_body

    client = GitHubClient()
    try:
        gh_issue = client.get_issue(repo, issue)
    except GitHubError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    parsed = parse_issue_body(gh_issue.body)

    labels = ", ".join(gh_issue.labels) if gh_issue.labels else "(none)"
    found = ", ".join(parsed.present_sections) if parsed.present_sections else "(none)"
    missing = (
        ", ".join(parsed.missing_required) if parsed.missing_required else "(none)"
    )

    typer.echo(f"Issue #{gh_issue.number}: {gh_issue.title}")
    typer.echo(f"State: {gh_issue.state}")
    if gh_issue.is_pull_request:
        typer.echo("Note: this issue is actually a pull request.")
    typer.echo(f"Labels: {labels}")
    typer.echo(f"Sections found: {found}")
    typer.echo(f"Missing required sections: {missing}")


_FAKE_BASE_URL = "http://fake-litellm.local/v1"
_FAKE_API_KEY = "fake-api-key-for-dry-run-only"
_DEFAULT_MODEL = "minimax-m2.7"


@app.command("llm-smoke-test")
def llm_smoke_test(
    model: str = typer.Option(
        _DEFAULT_MODEL, "--model", help="Fake model name to send in the request."
    ),
    message: str = typer.Option(
        "ping", "--message", help="User message content to send."
    ),
) -> None:
    """Dry-run smoke test of the Phase 3C LLMClient against a fake provider.

    This is a **dry-run / fake-provider smoke test only**: it never reads
    environment variables, never loads real LiteLLM config, and never makes a
    real network call. All HTTP is faked with an in-process
    ``httpx.MockTransport`` that returns a deterministic response.
    """
    # Imported lazily, matching the inspect-issue command's pattern.
    from ai_dev_orchestrator.llm.client import LLMClient
    from ai_dev_orchestrator.llm.models import LLMClientConfig, LLMMessage, LLMRequest

    import httpx

    def fake_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": model,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": f"[fake response] echo: {message}",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    config = LLMClientConfig(
        base_url=_FAKE_BASE_URL,
        api_key=_FAKE_API_KEY,
        default_model=model,
    )
    client = LLMClient(
        config,
        transport=httpx.MockTransport(fake_handler),
        sleep=lambda _seconds: None,
    )
    request = LLMRequest(
        model=model,
        messages=[LLMMessage(role="user", content=message)],
    )
    response = client.chat(request)

    typer.echo("=== LLM smoke test (dry-run / fake provider) ===")
    typer.echo("This is a dry-run using a fake provider. No real model was called.")
    typer.echo(f"Model: {response.model}")
    typer.echo(f"Response content: {response.content}")
    if response.usage is not None:
        typer.echo(
            "Token usage: prompt="
            f"{response.usage.prompt_tokens} completion="
            f"{response.usage.completion_tokens} total="
            f"{response.usage.total_tokens}"
        )


class GeneratePlanFormat(str, enum.Enum):
    """Supported output formats for `generate-plan`. Only JSON exists so far."""

    json = "json"


def _is_same_or_under(candidate: Path, root: str) -> bool:
    """Report whether ``candidate`` is ``root`` itself or sits beneath it.

    **String/path normalization only.** Both operands are treated as opaque
    strings: neither is read, listed, stat'd, resolved, or otherwise touched
    on disk. ``os.path.abspath`` only joins against the current working
    directory and normalizes separators — it performs no filesystem access.
    """
    normalized_candidate = os.path.normcase(os.path.abspath(str(candidate)))
    normalized_root = os.path.normcase(os.path.abspath(str(root)))
    if normalized_candidate == normalized_root:
        return True
    return normalized_candidate.startswith(normalized_root + os.sep)


@app.command("generate-plan")
def generate_plan(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to a project config YAML file inside this repo, "
        "e.g. projects/mis_project.yaml.example.",
    ),
    repo: str = typer.Option(
        ..., "--repo", help="Repository as owner/repo for the synthetic issue."
    ),
    issue: int = typer.Option(
        ..., "--issue", help="Issue number for the synthetic issue."
    ),
    title: str = typer.Option(
        ..., "--title", help="Issue title for the synthetic issue."
    ),
    body_file: Path = typer.Option(
        ...,
        "--body-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to a local markdown/text file containing the issue body.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Build an offline, fake/deterministic L1 plan from local files only.

    **Offline-only (Phase 4D)**: reads only the two local files explicitly
    given via ``--project-config`` and ``--body-file``. Does not fetch the
    issue from GitHub, does not call any model, does not read
    ``AIDO_LITELLM_*`` or any other environment variable, and does not read
    the project's configured ``repo.workspace_path``.

    A ``--body-file`` that is the configured ``repo.workspace_path`` itself,
    or sits under it, is rejected before the file is read — enforced with
    string/path normalization only, never by touching that path on disk.

    The printed JSON is an **L1 (plan-only) artifact**: it always carries
    ``automation_level: "L1"`` and ``requires_human_approval: true``, and its
    ``proposed_steps`` are descriptive review steps, not executable
    instructions.
    """
    # Imported lazily, matching the inspect-issue/llm-smoke-test pattern.
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.github.issue_parser import parse_issue_body
    from ai_dev_orchestrator.github.models import GitHubIssue
    from ai_dev_orchestrator.plan import FakeL1Planner

    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    # Refuse to read an issue body that lives inside the configured target
    # workspace. Checked BEFORE the body file is read, using string/path
    # normalization only — repo.workspace_path is never read, listed, stat'd,
    # resolved, or otherwise touched.
    if _is_same_or_under(body_file, project.repo.workspace_path):
        typer.echo(
            "Error: --body-file is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). "
            "generate-plan never reads target project workspaces; copy the "
            "issue body to a file outside that path and retry.",
            err=True,
        )
        raise typer.Exit(code=1)

    body_text = body_file.read_text(encoding="utf-8")

    synthetic_issue = GitHubIssue(
        number=issue,
        title=title,
        body=body_text,
        state="open",
        html_url=f"(offline synthetic issue, not fetched from GitHub) {repo}#{issue}",
    )
    parsed = parse_issue_body(synthetic_issue.body)

    plan = FakeL1Planner().create_plan(synthetic_issue, parsed, project)

    output = {
        "notice": (
            "L1 PLAN ONLY — generated offline by a fake/deterministic "
            "planner. This is not executable instructions. A human must "
            "review and approve before any implementation work proceeds."
        ),
        **plan.model_dump(),
    }
    typer.echo(json.dumps(output, indent=2))


# -- real model smoke test (Phase 4K) -----------------------------------------

# The ONLY environment variables this command may read (the Phase 3B names).
# Values are never printed, and the API key never reaches any output path.
_REAL_SMOKE_ENV_NAMES = (
    "AIDO_LITELLM_BASE_URL",
    "AIDO_LITELLM_API_KEY",
    "AIDO_LITELLM_DEFAULT_MODEL",
    "AIDO_LITELLM_TIMEOUT_SECONDS",
    "AIDO_LITELLM_MAX_RETRIES",
)

# A fixed, harmless connectivity prompt. It carries no issue text, no file
# contents, no workspace path, and no project data beyond nothing at all — the
# only variable part of the request is the model name.
_REAL_SMOKE_SYSTEM_PROMPT = (
    "You are responding to a connectivity smoke test for AI Dev Orchestrator. "
    "Do not include secrets. Reply briefly."
)
_REAL_SMOKE_USER_PROMPT = "Reply with exactly: AIDO_REAL_SMOKE_OK"
# 512, not 32: observed real deployment evidence showed reasoning-capable
# models (e.g. nemotron-3-super, minimax-m2.7, minimax-m2.7-thinking) consuming
# the entire 32-token budget on reasoning content before emitting any final
# assistant `content`, so the smoke test never saw usable output. This is a
# generation-room fix only; the smoke test still judges `content` alone.
_REAL_SMOKE_MAX_TOKENS = 512

_REAL_SMOKE_NOTICE = (
    "REAL MODEL SMOKE TEST ONLY — no issue text, planning, file edits, "
    "commands, GitHub writes, or workspace access."
)


def _read_real_llm_env() -> dict[str, str]:
    """Snapshot **only** the five ``AIDO_LITELLM_*`` names from the environment.

    This is the one place in the codebase that reads the real process
    environment, and the command calls it only after ``--real-model`` was given,
    the project config loaded, the project opted in, and the model passed the
    allowlist. No other variable is read, and no value is printed.
    """
    return {
        name: os.environ[name]
        for name in _REAL_SMOKE_ENV_NAMES
        if name in os.environ
    }


def _read_reviewer_env(provider: str) -> dict[str, str]:
    """Snapshot **only** the configured reviewer provider's environment names.

    Used by ``l2-review-approved-file-edit`` alone, and called only after the
    accepted Phase 5F2D verification returned ``verified``.

    **The ordering inside this function is the point** (Phase 5F2E-V1-FU1). The
    provider is resolved to an exact tuple of names *before* ``os.environ`` is
    touched at all, so:

    - a ``vllm`` review reads **only** ``AIDO_VLLM_BASE_URL`` and
      ``AIDO_VLLM_API_KEY``, and no ``AIDO_LITELLM_*`` name is ever looked up;
    - a ``litellm`` review reads **only** the five ``AIDO_LITELLM_*`` names, and
      no ``AIDO_VLLM_*`` name is ever looked up.

    Phase 5F2E-V1 shipped this reader as a *union* snapshot of both families,
    narrowed afterwards. That was wrong: reading a credential and then discarding
    it is still reading it, and it contradicted the contract V1 documented. There
    is deliberately no union constant left for this function to use.

    An unsupported provider raises before any name is resolved, so it cannot read
    an environment value either. No other variable is read, and no value is
    printed.

    ``_read_real_llm_env`` above is untouched: it still serves the planner and
    smoke-test commands with their own five ``AIDO_LITELLM_*`` names.
    """
    from ai_dev_orchestrator.review import reviewer_env_names_for_provider

    # Resolved from the provider alone — no environment access has happened yet.
    names = reviewer_env_names_for_provider(provider)
    return {name: os.environ[name] for name in names if name in os.environ}


def _build_real_llm_client(config):
    """Construct the real, socket-capable client. The only such call site."""
    from ai_dev_orchestrator.llm.client import LLMClient

    return LLMClient(config)


def _echo_real_smoke_banner(*, endpoint_host: str, model: str, project_id: str) -> None:
    """Print the non-suppressible pre-call warning block to stderr (design §3.3).

    Host only — never the full base URL (which may embed userinfo or a query
    string) and never the API key.
    """
    for line in (
        "=== REAL MODEL SMOKE TEST — a real network call is about to be made ===",
        f"Endpoint host: {endpoint_host}",
        f"Model:         {model}",
        f"Project:       {project_id}",
        "No issue text is sent: the prompt is a fixed connectivity check.",
        "No files, workspaces, or GitHub data are read or written.",
        "No plan is generated. The API key is never printed.",
        "=" * 71,
    ):
        typer.echo(line, err=True)


def _echo_real_smoke_result(
    *, endpoint_host: str, model: str, succeeded: bool, detail: str = ""
) -> None:
    """Print the matching post-call block to stderr.

    Printed only when a real call was actually attempted, so its presence in a
    scrollback means a request left the machine.
    """
    headline = (
        "=== REAL MODEL SMOKE TEST COMPLETED ==="
        if succeeded
        else "=== REAL MODEL SMOKE TEST FAILED (a real call was attempted) ==="
    )
    typer.echo(headline, err=True)
    typer.echo(f"Endpoint host: {endpoint_host}", err=True)
    typer.echo(f"Model:         {model}", err=True)
    if detail:
        typer.echo(f"Detail:        {detail}", err=True)


def _run_real_llm_smoke_test(
    *,
    project_config: Path,
    model: str,
    real_model: bool,
    read_env=_read_real_llm_env,
    client_factory=_build_real_llm_client,
) -> None:
    """Gate, then run one real chat completion. Extracted so tests can inject.

    ``read_env`` and ``client_factory`` are injection points: the CLI wrapper
    supplies the real environment reader and the real client builder, while
    tests supply a literal mapping and an ``httpx.MockTransport``-backed client,
    so the test suite never reads a real value or opens a real socket.

    Ordering is the safety property. In sequence: ``--real-model`` must be
    present, the project config must load, the project must opt in, and the
    model must be allowlisted — **all before** ``read_env`` is called — and only
    then may a client be built.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.llm.client import LLMClientError
    from ai_dev_orchestrator.llm.config import LLMConfigError
    from ai_dev_orchestrator.llm.models import LLMMessage, LLMRequest
    from ai_dev_orchestrator.plan import (
        RealModelPlanningGateError,
        check_real_model_planning_gate,
        endpoint_host_from_base_url,
    )

    # 1. Explicit confirmation. Checked first, so a plain invocation cannot read
    #    the environment, build a client, or reach the network.
    if not real_model:
        typer.echo(
            "Error: real-llm-smoke-test makes a REAL model call and requires "
            "the explicit --real-model flag. Nothing was read and no call was "
            "made.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 2. Project config: the only file this command reads. The configured
    #    repo.workspace_path is never read, listed, stat'd, or resolved.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    # 3. Probe the Phase 4J gate with an EMPTY mapping. The gate checks the
    #    project opt-in and the model allowlist before it looks at any
    #    environment value, so a project/model failure surfaces here — with the
    #    gate's own message — while the real environment is still untouched. A
    #    probe that gets as far as LLMConfigError has passed those checks, which
    #    is exactly the point at which reading the environment becomes allowed.
    try:
        check_real_model_planning_gate(
            project=project, requested_model=model, env={}
        )
    except RealModelPlanningGateError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "No environment variable was read, no client was built, and no "
            "network call was made.",
            err=True,
        )
        raise typer.Exit(code=1)
    except LLMConfigError:
        # Expected: the probe mapping deliberately carries no connection values.
        pass

    # 4. Now — and only now — read the five AIDO_LITELLM_* names and run the
    #    authoritative gate over them.
    env = read_env()
    try:
        config = check_real_model_planning_gate(
            project=project, requested_model=model, env=env
        )
        endpoint_host = endpoint_host_from_base_url(config.base_url)
    except (RealModelPlanningGateError, LLMConfigError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo("No client was built and no network call was made.", err=True)
        raise typer.Exit(code=1)

    # 5. Warn before the socket exists, not after.
    _echo_real_smoke_banner(
        endpoint_host=endpoint_host, model=model, project_id=project.project_id
    )

    # 6. The gate has passed: build the real client and send the fixed prompt.
    #    ``model`` is the explicit --model value; the environment's default
    #    model never selects what is sent.
    client = client_factory(config)
    request = LLMRequest(
        model=model,
        messages=[
            LLMMessage(role="system", content=_REAL_SMOKE_SYSTEM_PROMPT),
            LLMMessage(role="user", content=_REAL_SMOKE_USER_PROMPT),
        ],
        temperature=0.0,
        max_tokens=_REAL_SMOKE_MAX_TOKENS,
    )

    try:
        response = client.chat(request)
    except LLMClientError as exc:
        _echo_real_smoke_result(
            endpoint_host=endpoint_host,
            model=model,
            succeeded=False,
            detail=f"{type(exc).__name__}: {exc}",
        )
        raise typer.Exit(code=1)

    _echo_real_smoke_result(
        endpoint_host=endpoint_host, model=model, succeeded=True
    )

    output = {
        "notice": _REAL_SMOKE_NOTICE,
        "provenance": {
            "engine": "real-model",
            "operation": "smoke-test",
            "real_call": True,
            "model": model,
            "endpoint_host": endpoint_host,
            "project_id": project.project_id,
        },
        "response_content": response.content,
        "usage": response.usage.model_dump() if response.usage is not None else None,
    }
    typer.echo(json.dumps(output, indent=2))


@app.command("real-llm-smoke-test")
def real_llm_smoke_test(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to a project config YAML file whose real_model_planning "
        "block enables real model use.",
    ),
    model: str = typer.Option(
        ...,
        "--model",
        help="Exact model name to contact. Must be listed in the project's "
        "real_model_planning.allowed_models.",
    ),
    real_model: bool = typer.Option(
        False,
        "--real-model",
        help="Required explicit confirmation that a REAL model call may be "
        "made. Without it this command fails without reading anything.",
    ),
) -> None:
    """Gated REAL model connectivity smoke test (opens a real socket).

    One of several separately gated commands that may contact a real model —
    ``generate-model-plan`` and ``l2-review-approved-file-edit`` are the others,
    each with its own opt-in and its own model authority. **What is unique to
    this one is its scope**: it is a bounded **connectivity probe**, not a
    planner or a reviewer. It requires the explicit ``--real-model`` flag *and*
    a project config whose ``real_model_planning`` block enables real model use
    and allowlists ``--model``; either alone is not enough, and every
    precondition is checked before the environment is read or a client is
    built.

    It sends a **fixed, harmless prompt** and nothing else: never issue text,
    never file or workspace contents, and never project data. It fetches
    nothing from GitHub, writes nothing to GitHub, generates no plan, edits no
    file, runs no command, and writes no audit file.

    Only the five ``AIDO_LITELLM_*`` variables are read, and only after the gate
    passes. The API key is never printed; the endpoint is reported as a **host**
    only. A warning block is written to stderr before the call and a matching
    block after it, so a real call is impossible to miss in a scrollback, and
    the JSON result goes to stdout.
    """
    _run_real_llm_smoke_test(
        project_config=project_config,
        model=model,
        real_model=real_model,
        read_env=_read_real_llm_env,
        client_factory=_build_real_llm_client,
    )


# -- real model L1 plan (Phase 4L) --------------------------------------------

_MODEL_PLAN_NOTICE = (
    "REAL MODEL L1 PLAN ONLY — issue text was sent to a real model. This is "
    "not executable instructions. A human must review and approve before any "
    "implementation work proceeds."
)

# Human-readable categories for the Phase 4F planner errors. The category is
# printed instead of, or alongside, the exception message so the operator can
# tell "the model replied with garbage" from "the model proposed something
# forbidden" without the model's reply being echoed.
_PLANNER_FAILURE_CATEGORIES: dict[str, str] = {
    "ModelPlannerParseError": (
        "parser failure — the reply was not exactly one strict JSON object"
    ),
    "ModelPlannerValidationError": (
        "validation failure — the reply had missing, extra, or wrong-typed "
        "fields, supplied a caller-controlled field, or failed L1Plan validation"
    ),
    "ModelPlannerPolicyError": (
        "policy failure — the reply proposed forbidden, non-L1 behavior"
    ),
}

# A validation error's message can embed pydantic's echo of the offending input
# values, i.e. fragments of the completion. Those messages are withheld; the
# other two categories build their messages from fixed strings, field names, and
# JSON decoder positions only, so they are safe to show.
_PLANNER_ERRORS_WITH_UNSAFE_MESSAGES = frozenset({"ModelPlannerValidationError"})


def _utc_now_iso() -> str:
    """Return the current UTC time as a second-resolution ISO-8601 stamp."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _UsageRecordingClient:
    """Delegating chat client that remembers **only** the last reply's usage.

    The Phase 4G planner returns an ``L1Plan``, not the raw response, so token
    counts would otherwise be unavailable to the command. This wrapper keeps the
    counts and nothing else: the prompt and the completion are never stored,
    logged, or printed.
    """

    def __init__(self, client) -> None:
        self._client = client
        self.usage = None

    def chat(self, request):
        response = self._client.chat(request)
        self.usage = response.usage
        return response


def _echo_model_plan_banner(
    *,
    endpoint_host: str,
    model: str,
    project_id: str,
    repo: str,
    issue_number: int,
    title: str,
) -> None:
    """Print the non-suppressible pre-call warning block to stderr (design §3.3).

    Unlike the smoke test's banner, this one has to say plainly that issue text
    leaves the machine. Host only — never the full base URL (which may embed
    userinfo or a query string) and never the API key.
    """
    for line in (
        "=== REAL MODEL L1 PLAN — a real network call is about to be made ===",
        f"Endpoint host: {endpoint_host}",
        f"Model:         {model}",
        f"Project:       {project_id}",
        f"Repo:          {repo}",
        f"Issue:         #{issue_number} {title}",
        "The issue title and the text of the local body file WILL be "
        "transmitted to the model above.",
        "Nothing else is sent: no source files, no workspace contents, no "
        "directory listings, no git history, no GitHub token, no API key.",
        "Nothing is fetched from or written to GitHub. No file is edited and "
        "no command is run. No audit file is written.",
        "The result is an L1 plan only and still requires human approval.",
        "=" * 71,
    ):
        typer.echo(line, err=True)


def _echo_model_plan_result(
    *, endpoint_host: str, model: str, succeeded: bool, detail: str = ""
) -> None:
    """Print the matching post-call block to stderr.

    Printed only when a real call was actually attempted, so its presence in a
    scrollback means issue text left the machine.
    """
    typer.echo(
        "=== REAL MODEL L1 PLAN COMPLETED ==="
        if succeeded
        else "=== REAL MODEL L1 PLAN FAILED (a real call was attempted) ===",
        err=True,
    )
    typer.echo(f"Endpoint host: {endpoint_host}", err=True)
    typer.echo(f"Model:         {model}", err=True)
    if detail:
        typer.echo(f"Detail:        {detail}", err=True)


def _run_generate_model_plan(
    *,
    project_config: Path,
    issue: int,
    title: str,
    body_file: Path,
    model: str,
    real_model: bool,
    read_env=_read_real_llm_env,
    client_factory=_build_real_llm_client,
) -> None:
    """Gate, then produce one real model-backed L1 plan. Extracted for tests.

    ``read_env`` and ``client_factory`` are injection points: the CLI wrapper
    supplies the real environment reader and the real client builder, while tests
    supply a literal mapping and an ``httpx.MockTransport``-backed client, so the
    test suite never reads a real value or opens a real socket.

    Ordering is the safety property, and it is stricter than the smoke test's
    because this command transmits issue text. In sequence: ``--real-model`` must
    be present, the project config must load, ``--body-file`` must be outside the
    configured ``repo.workspace_path``, the project must opt in, and the model
    must be allowlisted — **all before** ``read_env`` is called — then the
    environment gate must pass, and only *then* is the body file read, the banner
    printed, and a client built.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.github.issue_parser import parse_issue_body
    from ai_dev_orchestrator.github.models import GitHubIssue
    from ai_dev_orchestrator.llm.client import LLMClientError
    from ai_dev_orchestrator.llm.config import LLMConfigError
    from ai_dev_orchestrator.plan import (
        ModelBackedL1Planner,
        ModelPlannerError,
        RealModelPlanningGateError,
        check_real_model_planning_gate,
        endpoint_host_from_base_url,
    )

    # 1. Explicit confirmation. Checked first, so a plain invocation reads no
    #    environment value, reads no issue body, builds no client, and reaches no
    #    network.
    if not real_model:
        typer.echo(
            "Error: generate-model-plan sends the issue text to a REAL model and "
            "requires the explicit --real-model flag. Nothing was read and no "
            "call was made.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 2. Project config: the only file read before gating. The configured
    #    repo.workspace_path is never read, listed, stat'd, or resolved.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    # 3. Refuse an issue body that lives inside the configured target workspace,
    #    BEFORE that file is read or stat'd — which is also why --body-file
    #    carries no Typer exists=/readable= check: those would touch the path
    #    before this guard could run. String/path normalization only; the
    #    workspace path itself is never read, listed, stat'd, or resolved.
    if _is_same_or_under(body_file, project.repo.workspace_path):
        typer.echo(
            "Error: --body-file is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). "
            "generate-model-plan never reads target project workspaces; copy "
            "the issue body to a file outside that path and retry.",
            err=True,
        )
        typer.echo(
            "The body file was not read, no environment variable was read, no "
            "client was built, and no network call was made.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 4. Probe the Phase 4J gate with an EMPTY mapping. The gate checks the
    #    project opt-in and the model allowlist before it looks at any
    #    environment value, so a project/model failure surfaces here — with the
    #    gate's own message — while the real environment and the issue body are
    #    both still untouched. A probe that gets as far as LLMConfigError has
    #    passed those checks, which is the point at which reading the environment
    #    becomes allowed.
    try:
        check_real_model_planning_gate(project=project, requested_model=model, env={})
    except RealModelPlanningGateError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The body file was not read, no environment variable was read, no "
            "client was built, and no network call was made.",
            err=True,
        )
        raise typer.Exit(code=1)
    except LLMConfigError:
        # Expected: the probe mapping deliberately carries no connection values.
        pass

    # 5. Now — and only now — read the five AIDO_LITELLM_* names and run the
    #    authoritative gate over them.
    env = read_env()
    try:
        config = check_real_model_planning_gate(
            project=project, requested_model=model, env=env
        )
        endpoint_host = endpoint_host_from_base_url(config.base_url)
    except (RealModelPlanningGateError, LLMConfigError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The body file was not read, no client was built, and no network "
            "call was made.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 6. Every gate has passed, so the issue body may finally be read. It is
    #    read from the local path given on the command line and nowhere else;
    #    GitHub is not contacted.
    try:
        body_text = body_file.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Error: could not read --body-file: {exc}", err=True)
        typer.echo("No client was built and no network call was made.", err=True)
        raise typer.Exit(code=1)

    synthetic_issue = GitHubIssue(
        number=issue,
        title=title,
        body=body_text,
        state="open",
        html_url=(
            "(local issue body, not fetched from GitHub) "
            f"{project.repo.github_repo}#{issue}"
        ),
    )
    parsed = parse_issue_body(synthetic_issue.body)

    # 7. Warn before the socket exists, not after.
    _echo_model_plan_banner(
        endpoint_host=endpoint_host,
        model=model,
        project_id=project.project_id,
        repo=project.repo.github_repo,
        issue_number=issue,
        title=title,
    )

    # 8. Build the real client and plan with it. ``model`` is the explicit
    #    --model value; the environment's default model never selects what is
    #    sent. Neither the prompt nor the completion is logged or written to disk.
    client = _UsageRecordingClient(client_factory(config))
    try:
        plan = ModelBackedL1Planner(client).create_plan(
            synthetic_issue, parsed, project, model=model
        )
    except LLMClientError as exc:
        _echo_model_plan_result(
            endpoint_host=endpoint_host,
            model=model,
            succeeded=False,
            detail=f"{type(exc).__name__}: {exc}",
        )
        raise typer.Exit(code=1)
    except ModelPlannerError as exc:
        name = type(exc).__name__
        category = _PLANNER_FAILURE_CATEGORIES.get(name, "planner failure")
        detail = f"{name}: {category}"
        if name not in _PLANNER_ERRORS_WITH_UNSAFE_MESSAGES:
            detail = f"{detail}. {exc}"
        _echo_model_plan_result(
            endpoint_host=endpoint_host,
            model=model,
            succeeded=False,
            detail=detail,
        )
        typer.echo(
            "The model reply is not echoed and no audit file was written.",
            err=True,
        )
        raise typer.Exit(code=1)

    _echo_model_plan_result(endpoint_host=endpoint_host, model=model, succeeded=True)

    output = {
        "notice": _MODEL_PLAN_NOTICE,
        "provenance": {
            "engine": "real-model",
            "operation": "l1-plan",
            "real_call": True,
            "model": model,
            "endpoint_host": endpoint_host,
            "project_id": project.project_id,
            "repo": project.repo.github_repo,
            "issue_number": issue,
            "title": title,
            "generated_at": _utc_now_iso(),
        },
        "plan": plan.model_dump(),
        "usage": client.usage.model_dump() if client.usage is not None else None,
    }
    typer.echo(json.dumps(output, indent=2))


@app.command("generate-model-plan")
def generate_model_plan(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to a project config YAML file whose real_model_planning "
        "block enables real model use.",
    ),
    issue: int = typer.Option(
        ..., "--issue", help="Issue number for the synthetic issue."
    ),
    title: str = typer.Option(
        ..., "--title", help="Issue title. It is sent to the model."
    ),
    body_file: Path = typer.Option(
        ...,
        "--body-file",
        # Deliberately no exists=/readable= check: Typer would stat the path
        # before the command body could reject one inside the configured
        # workspace. The guard runs first; the file is opened only afterwards.
        help="Path to a local markdown/text file containing the issue body. "
        "Its text is sent to the model. Must not be inside the project's "
        "configured workspace path.",
    ),
    model: str = typer.Option(
        ...,
        "--model",
        help="Exact model name to plan with. Must be listed in the project's "
        "real_model_planning.allowed_models.",
    ),
    real_model: bool = typer.Option(
        False,
        "--real-model",
        help="Required explicit confirmation that a REAL model call may be "
        "made. Without it this command fails without reading anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Gated REAL model L1 plan (opens a real socket, sends the issue text).

    **This command transmits issue text to a real model.** It requires the
    explicit ``--real-model`` flag *and* a project config whose
    ``real_model_planning`` block enables real model use and allowlists
    ``--model``; either alone is not enough, and every precondition is checked
    before the environment is read, the body file is opened, or a client is
    built.

    What is sent: the ``--title`` value, the text of the ``--body-file``, its
    parsed issue sections, and the project's allowed/protected/forbidden path
    **patterns** and policy flags. What is never sent: source files, workspace
    contents, directory listings, git history, the GitHub token, and the API key.

    A ``--body-file`` that is the configured ``repo.workspace_path`` itself, or
    sits under it, is rejected before the file is read or stat'd — enforced with
    string/path normalization only, never by touching that path on disk.

    Nothing is fetched from GitHub and nothing is written to GitHub: there is no
    option to reach it. No plan or command is executed, no file is edited, and no
    prompt/completion audit file is written.

    Only the five ``AIDO_LITELLM_*`` variables are read, and only after the gate
    passes. The API key is never printed; the endpoint is reported as a **host**
    only. A warning block goes to stderr before the call and a matching block
    after it, so a real call is impossible to miss in a scrollback, and the JSON
    result goes to stdout.

    The result is an **L1 (plan-only) artifact**: ``automation_level: "L1"`` and
    ``requires_human_approval: true`` are set by the orchestrator, never read
    from model output. No L2/L3 automation is authorized by this command.
    """
    _run_generate_model_plan(
        project_config=project_config,
        issue=issue,
        title=title,
        body_file=body_file,
        model=model,
        real_model=real_model,
        read_env=_read_real_llm_env,
        client_factory=_build_real_llm_client,
    )


# -- L2 dry run (Phase 5C) -----------------------------------------------------

_L2_DRY_RUN_NOTICE = (
    "L2 DRY RUN ONLY — no workspace was read, no files were edited, no "
    "commands were run, and no implementation occurred."
)

_L2_DRY_RUN_NEXT_AUTHORIZATION = (
    "Phase 5D or later must be explicitly authorized before any workspace "
    "inspection or implementation, and Phase 5D is additionally blocked on the "
    "path-canonicalization work in the Phase 5A design §6.4."
)

# Printed alongside the copied plan fields so the block cannot be mistaken for
# an instruction set. `required_verification` in particular tends to read like a
# list of commands to run; it is prose from the plan, and this command ran none
# of it.
_L2_INTENDED_SCOPE_NOTE = (
    "Plan text only, copied verbatim from the approved plan snapshot and never "
    "acted on. No path listed here was read, stat'd, resolved, globbed, or "
    "checked for existence, and every required_verification entry is plan text "
    "that this command did not execute."
)

# Human-readable categories for the Phase 5B handoff errors, following the Phase
# 4L precedent: name *what kind* of thing failed. The exception messages are
# safe to show — Phase 5B guarantees they name the failed field and category and
# never echo the artifact text, plan prose, or any supplied value.
_APPROVED_PLAN_FAILURE_CATEGORIES: dict[str, str] = {
    "ApprovedPlanParseError": (
        "parse failure — the artifact text was not exactly one strict JSON object"
    ),
    "ApprovedPlanValidationError": (
        "validation failure — the artifact had missing, extra, or wrong-typed "
        "fields, an absent or invalid approval block, an identity mismatch, or "
        "a plan that is not an unescalated L1 plan"
    ),
}


def _run_l2_dry_run(
    *,
    project_config: Path,
    approved_plan: Path,
    apply_approved_plan: bool,
) -> None:
    """Validate an approved plan and print the scope a future L2 would have.

    Extracted from the command body so tests can call it directly and track
    exactly which files are read, in which order.

    Ordering is the safety property, and it is the Phase 5A §4.3 gate as far as
    this phase is authorized to go. In sequence: ``--apply-approved-plan`` must
    be present, the project config must load, and ``--approved-plan`` must be
    outside the configured ``repo.workspace_path`` — **all before** the artifact
    is opened — then the artifact is read, parsed, and identity-matched against
    the config, and only then is anything printed.

    Step 3 of §4.3 (a project-level L2 opt-in block) is deliberately **not**
    implemented here: this command performs no L2 action, so there is nothing
    for a project to opt into yet. It belongs with the phase that first touches
    a workspace.

    Nothing here reads an environment variable, opens a socket, builds a client,
    contacts GitHub, executes a command, edits a file, or reads/lists/stats/
    resolves any target project workspace.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.handoff import (
        ApprovedPlanError,
        parse_approved_l1_plan_artifact,
    )

    # 1. Explicit confirmation. Checked first, so a plain invocation reads no
    #    file at all — not the config, and certainly not the artifact.
    if not apply_approved_plan:
        typer.echo(
            "Error: l2-dry-run acts on a human-approved plan artifact and "
            "requires the explicit --apply-approved-plan flag. Nothing was "
            "read.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 2. Project config: the first file read. The configured repo.workspace_path
    #    is never read, listed, stat'd, or resolved.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo("The approved plan artifact was not read.", err=True)
        raise typer.Exit(code=1)

    # 3. Refuse an artifact that lives inside the configured target workspace,
    #    BEFORE it is read or stat'd — which is also why --approved-plan carries
    #    no Typer exists=/readable= check: those would touch the path before this
    #    guard could run. String/path normalization only; the workspace path
    #    itself is never read, listed, stat'd, or resolved.
    if _is_same_or_under(approved_plan, project.repo.workspace_path):
        typer.echo(
            "Error: --approved-plan is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). "
            "l2-dry-run never reads target project workspaces; move the "
            "approved plan artifact outside that path and retry.",
            err=True,
        )
        typer.echo("The approved plan artifact was not read.", err=True)
        raise typer.Exit(code=1)

    # 4. The guard has passed, so the artifact may be read. It is the second and
    #    final file read by this command.
    try:
        artifact_text = approved_plan.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Error: could not read --approved-plan: {exc}", err=True)
        raise typer.Exit(code=1)

    # 5. Parse strictly (Phase 5B). Rejected, never repaired.
    try:
        artifact = parse_approved_l1_plan_artifact(artifact_text)
    except ApprovedPlanError as exc:
        name = type(exc).__name__
        category = _APPROVED_PLAN_FAILURE_CATEGORIES.get(name, "artifact failure")
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        typer.echo(
            "The artifact text and the plan prose are not echoed. No scope was "
            "printed and no L2 action was taken.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 6. The artifact and the config are independent inputs that can disagree.
    #    Exact string equality only — no normalization, no case folding, no
    #    prefix matching (design §3.5). The issue number comes from the artifact
    #    alone; GitHub is not contacted to confirm it.
    mismatches = [
        f"{label}: artifact has {artifact_value!r}, project config has "
        f"{config_value!r}"
        for label, artifact_value, config_value in (
            ("project_id", artifact.project_id, project.project_id),
            ("repo", artifact.repo, project.repo.github_repo),
            ("plan.repo", artifact.plan.repo, project.repo.github_repo),
            (
                "plan_provenance.repo",
                artifact.plan_provenance.repo,
                project.repo.github_repo,
            ),
        )
        if artifact_value != config_value
    ]
    if mismatches:
        typer.echo(
            "Error: the approved plan does not match this project config "
            "exactly. A plan approved for one project/repo grants nothing for "
            "another.",
            err=True,
        )
        for mismatch in mismatches:
            typer.echo(f"  Mismatch in {mismatch}", err=True)
        raise typer.Exit(code=1)

    approval = artifact.approval
    provenance = artifact.plan_provenance
    plan = artifact.plan

    # 7. Report. Deliberately absent: the raw artifact text, the raw prompt or
    #    completion, any API key or base URL, and the configured workspace path.
    #    `approval_text` is omitted too — it is required to equal a fixed phrase,
    #    so echoing it conveys nothing the `approved_by`/`approved_at` pair does
    #    not already carry.
    output = {
        "notice": _L2_DRY_RUN_NOTICE,
        "mode": "l2-dry-run",
        "project": {
            "project_id": project.project_id,
            "repo": project.repo.github_repo,
            "workspace_policy": {
                "deny_outside_workspace": (
                    project.workspace_policy.deny_outside_workspace
                ),
                "allow_symlinks": project.workspace_policy.allow_symlinks,
                "max_changed_files": project.workspace_policy.max_changed_files,
            },
        },
        "approved_plan": {
            "approved_by": approval.approved_by,
            "approved_at": approval.approved_at.isoformat(),
            "source": approval.source,
            "plan_engine": provenance.engine,
            "real_call": provenance.real_call,
            "model": provenance.model,
            "issue_number": artifact.issue_number,
            "title": plan.title,
        },
        "intended_scope": {
            "note": _L2_INTENDED_SCOPE_NOTE,
            "files_likely_to_change": list(plan.files_likely_to_change),
            "files_forbidden_or_out_of_scope": list(
                plan.files_forbidden_or_out_of_scope
            ),
            "required_verification": list(plan.required_verification),
            "proposed_steps": list(plan.proposed_steps),
            "risks": list(plan.risks),
            "open_questions": list(plan.open_questions),
        },
        "next_authorization_required": _L2_DRY_RUN_NEXT_AUTHORIZATION,
    }
    typer.echo(json.dumps(output, indent=2))


@app.command("l2-dry-run")
def l2_dry_run(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the project config YAML the approved plan must match.",
    ),
    approved_plan: Path = typer.Option(
        ...,
        "--approved-plan",
        # Deliberately no exists=/readable= check: Typer would stat the path
        # before the command body could reject one inside the configured
        # workspace. The guard runs first; the file is opened only afterwards.
        help="Path to a human-approved L1 plan artifact (Phase 5B shape). Must "
        "not be inside the project's configured workspace path.",
    ),
    apply_approved_plan: bool = typer.Option(
        False,
        "--apply-approved-plan",
        help="Required explicit confirmation that an approved plan may be "
        "acted on. Without it this command fails without reading anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Validate an approved L1 plan and print the scope a future L2 would have.

    **Dry run only, and L2 is still not built.** This command reads exactly two
    local files — the ``--project-config`` YAML and the ``--approved-plan``
    artifact, in that order — validates the artifact with the Phase 5B parser,
    checks it against the config, and prints what a future implementer *would*
    be bounded by. It inspects nothing, proposes nothing, and changes nothing.

    It does **not**: read, list, stat, or resolve the project's configured
    ``repo.workspace_path`` or any target workspace; check whether any file the
    plan names exists; run any ``required_verification`` entry or any other
    command; generate or apply a patch; edit a file; create a branch, commit, or
    PR; fetch from or write to GitHub; call a model; open a socket; or read
    ``AIDO_LITELLM_*`` or any other environment variable.

    It also never writes or stamps an approval: the approval block must already
    have been written by a human, and it must carry a non-blank ``approved_by``,
    a parseable ``approved_at``, ``source: "manual"``, and an ``approval_text``
    matching the required phrase exactly. An artifact merely existing, or merely
    parsing, is not approval.

    The gate fails closed in order: ``--apply-approved-plan`` first (without it
    nothing is read at all), then the config, then a string/path check rejecting
    an ``--approved-plan`` inside the configured workspace **before** it is read
    or stat'd, then the strict parse, then exact ``project_id``/``repo``
    matching against the config. Any failure exits non-zero with stderr only and
    nothing on stdout, and never echoes the artifact text or the plan prose.
    """
    _run_l2_dry_run(
        project_config=project_config,
        approved_plan=approved_plan,
        apply_approved_plan=apply_approved_plan,
    )


# -- L2 read-only workspace metadata inspection (Phase 5D1) --------------------

_L2_INSPECT_NOTICE = (
    "L2 WORKSPACE METADATA INSPECTION ONLY — workspace paths were canonicalized "
    "and stat'd, but no file contents were read, no files were edited, no "
    "commands were run, and no implementation occurred."
)

_L2_INSPECT_NEXT_AUTHORIZATION = (
    "Phase 5E or later must be explicitly authorized before any patch proposal, "
    "file edit, command execution, commit, push, or PR."
)

# Printed inside the inspection block so a reader knows exactly how far the
# command went: it proved paths exist and recorded their kind and size, and it
# stopped there.
_L2_INSPECT_ITEMS_NOTE = (
    "Metadata only. Each path was checked against the lexical path policy, "
    "canonicalized against the configured workspace root, and stat'd. No file "
    "was opened or read, no directory was listed, and nothing was executed."
)

_L2_INSPECT_EMPTY_NOTE = (
    "The approved plan named no files_likely_to_change, so there was nothing to "
    "inspect and the configured workspace was not touched at all."
)


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    """Drop exact duplicate strings, keeping the first occurrence's position."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _stat_kind_and_size(resolved_candidate: str) -> tuple[str, int | None]:
    """Classify an already-canonicalized path from its metadata alone.

    ``os.stat`` and nothing else: the path is never opened, never read, and
    never listed. A directory reports its kind and a ``None`` size — its
    entries are not enumerated.
    """
    import stat as stat_module

    result = os.stat(resolved_candidate)
    if stat_module.S_ISDIR(result.st_mode):
        return "directory", None
    if stat_module.S_ISREG(result.st_mode):
        return "file", result.st_size
    return "other", None


def _run_l2_inspect_workspace(
    *,
    project_config: Path,
    approved_plan: Path,
    apply_approved_plan: bool,
    inspect_workspace: bool,
) -> None:
    """Report metadata for the paths an approved plan names. Extracted for tests.

    This is the **first shipped code that may touch a configured target
    workspace**, and the ordering below is the whole safety argument. Every
    cheap, local, disk-free check runs first; the workspace is touched only
    after all of them pass, and then only through the Phase 5D0 canonical guard
    and :func:`os.stat`.

    In sequence: ``--apply-approved-plan``, then ``--inspect-workspace`` (both
    before any file is read), then the project config, then the project-level
    ``read_only_workspace_inspection`` opt-in, then a string/path check
    rejecting an ``--approved-plan`` inside the configured workspace, then the
    artifact read, the strict Phase 5B parse, exact identity matching, the
    candidate-count caps, and the lexical Phase 1 path policy for **every**
    candidate. Only after all of that does any path get canonicalized or stat'd.

    Nothing here reads file contents, lists a directory, globs, walks a tree,
    executes a command, edits a file, runs a ``required_verification`` entry,
    reads an environment variable, opens a socket, calls a model, or contacts
    GitHub.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.handoff import (
        ApprovedPlanError,
        parse_approved_l1_plan_artifact,
    )
    from ai_dev_orchestrator.workspace import (
        CanonicalPathError,
        CanonicalPathInputError,
        PathClassification,
        PathPolicy,
        canonicalize_existing_path_under_workspace,
    )

    # 1. Explicit confirmation that an approved plan may be acted on. Checked
    #    first, so a plain invocation reads no file at all.
    if not apply_approved_plan:
        typer.echo(
            "Error: l2-inspect-workspace acts on a human-approved plan artifact "
            "and requires the explicit --apply-approved-plan flag. Nothing was "
            "read and no workspace was touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 2. Explicit confirmation that the target workspace may be inspected. This
    #    is a second, separate consent: approving a plan is not the same act as
    #    permitting a workspace to be examined.
    if not inspect_workspace:
        typer.echo(
            "Error: l2-inspect-workspace reads path metadata from the project's "
            "configured workspace and requires the explicit --inspect-workspace "
            "flag. Nothing was read and no workspace was touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 3. Project config: the first file read. repo.workspace_path is still only
    #    a string at this point — it is not read, listed, stat'd, or resolved.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The approved plan artifact was not read and no workspace was "
            "touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 4. Project-level opt-in. An absent block is identical to a disabled one,
    #    and either fails before the artifact is opened.
    inspection = project.read_only_workspace_inspection
    if not inspection.enabled:
        typer.echo(
            "Error: this project does not enable read-only workspace "
            "inspection. Set read_only_workspace_inspection.enabled to true in "
            "the project config to permit path metadata inspection.",
            err=True,
        )
        typer.echo(
            "The approved plan artifact was not read and no workspace was "
            "touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 5. Refuse an artifact that lives inside the configured target workspace,
    #    BEFORE it is read or stat'd — which is why --approved-plan carries no
    #    Typer exists=/readable= check. String/path normalization only.
    if _is_same_or_under(approved_plan, project.repo.workspace_path):
        typer.echo(
            "Error: --approved-plan is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). The approved "
            "plan must live outside the workspace it authorizes; move it "
            "outside that path and retry.",
            err=True,
        )
        typer.echo(
            "The approved plan artifact was not read and no workspace was "
            "touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 6. The guard has passed, so the artifact may be read. It is the second and
    #    final file this command reads.
    try:
        artifact_text = approved_plan.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Error: could not read --approved-plan: {exc}", err=True)
        typer.echo("No workspace was touched.", err=True)
        raise typer.Exit(code=1)

    # 7. Parse strictly (Phase 5B). Rejected, never repaired.
    try:
        artifact = parse_approved_l1_plan_artifact(artifact_text)
    except ApprovedPlanError as exc:
        name = type(exc).__name__
        category = _APPROVED_PLAN_FAILURE_CATEGORIES.get(name, "artifact failure")
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        typer.echo(
            "The artifact text and the plan prose are not echoed. No workspace "
            "was touched and no path was inspected.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 8. Exact identity matching against the config (design §3.5). A plan
    #    approved for one project/repo grants nothing for another — and here
    #    that mistake would mean stat'ing another project's files.
    mismatches = [
        f"{label}: artifact has {artifact_value!r}, project config has "
        f"{config_value!r}"
        for label, artifact_value, config_value in (
            ("project_id", artifact.project_id, project.project_id),
            ("repo", artifact.repo, project.repo.github_repo),
            ("plan.repo", artifact.plan.repo, project.repo.github_repo),
            (
                "plan_provenance.repo",
                artifact.plan_provenance.repo,
                project.repo.github_repo,
            ),
        )
        if artifact_value != config_value
    ]
    if mismatches:
        typer.echo(
            "Error: the approved plan does not match this project config "
            "exactly. A plan approved for one project/repo grants nothing for "
            "another.",
            err=True,
        )
        for mismatch in mismatches:
            typer.echo(f"  Mismatch in {mismatch}", err=True)
        typer.echo("No workspace was touched.", err=True)
        raise typer.Exit(code=1)

    plan = artifact.plan

    # 9. Candidates come from files_likely_to_change and nowhere else.
    #    files_forbidden_or_out_of_scope is never inspected — naming a path as
    #    out of scope must not become a way to have it examined — and
    #    proposed_steps / required_verification / risks / open_questions are
    #    prose that is never treated as a path.
    candidates = _dedupe_preserving_order(list(plan.files_likely_to_change))

    if len(candidates) > inspection.max_inspected_files:
        typer.echo(
            f"Error: the approved plan names {len(candidates)} distinct paths, "
            "which exceeds read_only_workspace_inspection.max_inspected_files "
            f"({inspection.max_inspected_files}). No workspace was touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    if len(candidates) > project.workspace_policy.max_changed_files:
        typer.echo(
            f"Error: the approved plan names {len(candidates)} distinct paths, "
            "which exceeds workspace_policy.max_changed_files "
            f"({project.workspace_policy.max_changed_files}). No workspace was "
            "touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 10. The lexical Phase 1 policy runs for EVERY candidate before any of them
    #     is canonicalized or stat'd. A single failure stops the whole run: a
    #     plan that names one forbidden path does not get a partial inspection
    #     of its other paths.
    policy = PathPolicy.from_project_config(project)
    normalized: list[tuple[str, str]] = []
    refusals: list[str] = []
    for original in candidates:
        decision = policy.check_read(original)
        if decision.classification is PathClassification.PROTECTED:
            if not inspection.allow_protected_paths:
                refusals.append(
                    f"{original!r}: classified protected, and "
                    "read_only_workspace_inspection.allow_protected_paths is "
                    "false"
                )
                continue
        elif not decision.permitted:
            refusals.append(
                f"{original!r}: classified {decision.classification.value} "
                f"({decision.reason})"
            )
            continue
        normalized.append((original, decision.path))

    if refusals:
        typer.echo(
            "Error: the approved plan names paths the project's path policy "
            "refuses to read. The whole inspection is abandoned; no path was "
            "canonicalized, stat'd, or otherwise touched.",
            err=True,
        )
        for refusal in refusals:
            typer.echo(f"  Refused {refusal}", err=True)
        raise typer.Exit(code=1)

    # 11. Every candidate passed the lexical gate, so — and only so — the
    #     configured workspace may be touched. The root is canonicalized first,
    #     which proves it exists, is a directory, and satisfies the symlink
    #     policy before any candidate is resolved against it. With no candidates
    #     there is nothing to inspect and the workspace stays untouched.
    items: list[dict] = []
    allow_symlinks = project.workspace_policy.allow_symlinks

    if normalized:
        try:
            canonicalize_existing_path_under_workspace(
                project.repo.workspace_path,
                project.repo.workspace_path,
                allow_symlinks=allow_symlinks,
            )
        except CanonicalPathError as exc:
            typer.echo(
                "Error: the configured repo.workspace_path could not be "
                f"canonicalized. {type(exc).__name__}: {exc}",
                err=True,
            )
            typer.echo("No candidate path was inspected.", err=True)
            raise typer.Exit(code=1)

    for original, candidate in normalized:
        missing = {
            "original_plan_path": original,
            "canonical_relative_path": None,
            "status": "missing",
            "kind": None,
            "size_bytes": None,
            "symlinks_allowed": allow_symlinks,
        }
        try:
            resolved = canonicalize_existing_path_under_workspace(
                project.repo.workspace_path,
                candidate,
                allow_symlinks=allow_symlinks,
            )
        except CanonicalPathInputError:
            # The root was proven good above and the candidate is a non-blank
            # string that passed the lexical gate, so the only remaining input
            # failure is "this path does not exist". That is an ordinary,
            # reportable answer, not a boundary violation.
            items.append(missing)
            continue
        except CanonicalPathError as exc:
            # Containment, symlink, ambiguity, and resolution failures are
            # boundary violations. They stop the whole run.
            typer.echo(
                f"Error: {original!r} failed the canonical workspace path "
                f"guard. {type(exc).__name__}: {exc}",
                err=True,
            )
            typer.echo(
                "The inspection is abandoned; no result is printed.", err=True
            )
            raise typer.Exit(code=1)

        try:
            kind, size_bytes = _stat_kind_and_size(resolved.resolved_candidate)
        except FileNotFoundError:
            # Time-of-check/time-of-use: the path existed a moment ago and does
            # not now. Reported as missing rather than as a violation.
            items.append(missing)
            continue
        except OSError as exc:
            typer.echo(
                f"Error: metadata for {original!r} could not be read after "
                f"canonicalization. {type(exc).__name__}: {exc}",
                err=True,
            )
            typer.echo(
                "The inspection is abandoned; no result is printed.", err=True
            )
            raise typer.Exit(code=1)

        items.append(
            {
                "original_plan_path": original,
                "canonical_relative_path": resolved.relative_path.replace(
                    "\\", "/"
                ),
                "status": "exists",
                "kind": kind,
                "size_bytes": size_bytes,
                "symlinks_allowed": allow_symlinks,
            }
        )

    approval = artifact.approval
    provenance = artifact.plan_provenance

    # 12. Report. Deliberately absent: the configured workspace_path, any
    #     resolved absolute path, any file content, any directory listing, the
    #     raw artifact text, `approval_text`, any prompt or completion, and any
    #     API key or base URL. `required_verification` is absent too — this
    #     command did not run it, and reprinting it here would only invite
    #     someone to.
    output = {
        "notice": _L2_INSPECT_NOTICE,
        "mode": "l2-inspect-workspace",
        "project": {
            "project_id": project.project_id,
            "repo": project.repo.github_repo,
            "workspace_policy": {
                "deny_outside_workspace": (
                    project.workspace_policy.deny_outside_workspace
                ),
                "allow_symlinks": project.workspace_policy.allow_symlinks,
                "max_changed_files": project.workspace_policy.max_changed_files,
            },
            "inspection_policy": {
                "enabled": inspection.enabled,
                "max_inspected_files": inspection.max_inspected_files,
                "allow_protected_paths": inspection.allow_protected_paths,
            },
        },
        "approved_plan": {
            "approved_by": approval.approved_by,
            "approved_at": approval.approved_at.isoformat(),
            "source": approval.source,
            "plan_engine": provenance.engine,
            "real_call": provenance.real_call,
            "model": provenance.model,
            "issue_number": artifact.issue_number,
            "title": plan.title,
        },
        "workspace_inspection": {
            "note": _L2_INSPECT_ITEMS_NOTE if items else _L2_INSPECT_EMPTY_NOTE,
            "candidate_source": "approved_plan.files_likely_to_change",
            "file_contents_read": False,
            "directories_listed": False,
            "commands_run": False,
            "items": items,
        },
        "next_authorization_required": _L2_INSPECT_NEXT_AUTHORIZATION,
    }
    typer.echo(json.dumps(output, indent=2))


@app.command("l2-inspect-workspace")
def l2_inspect_workspace(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the project config YAML the approved plan must match. "
        "Its read_only_workspace_inspection block must enable inspection.",
    ),
    approved_plan: Path = typer.Option(
        ...,
        "--approved-plan",
        # Deliberately no exists=/readable= check: Typer would stat the path
        # before the command body could reject one inside the configured
        # workspace. The guard runs first; the file is opened only afterwards.
        help="Path to a human-approved L1 plan artifact (Phase 5B shape). Must "
        "not be inside the project's configured workspace path.",
    ),
    apply_approved_plan: bool = typer.Option(
        False,
        "--apply-approved-plan",
        help="Required explicit confirmation that an approved plan may be "
        "acted on. Without it this command fails without reading anything.",
    ),
    inspect_workspace: bool = typer.Option(
        False,
        "--inspect-workspace",
        help="Required explicit confirmation that the project's configured "
        "workspace may be inspected for path metadata. Without it this command "
        "fails without reading anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Report path metadata for an approved plan's files. **Read-only.**

    This is the first command permitted to touch a configured target workspace,
    and it makes the smallest possible touch: for each path the approved plan
    lists under ``files_likely_to_change``, it canonicalizes the path against
    the workspace root and calls ``stat``, reporting whether the path exists,
    whether it is a file or a directory, and how large a regular file is.

    It does **not**: read or open any file's contents; list, glob, or walk any
    directory (a candidate that *is* a directory is reported as one and its
    entries are not enumerated); inspect any path outside
    ``files_likely_to_change``, including ``files_forbidden_or_out_of_scope``;
    treat ``proposed_steps``, ``required_verification``, ``risks``, or
    ``open_questions`` as paths; run any ``required_verification`` entry or any
    other command; generate or apply a patch; edit or write any file; create a
    branch, commit, or PR; fetch from or write to GitHub; call a model; open a
    socket; or read ``AIDO_LITELLM_*`` or any other environment variable. It
    never writes or stamps an approval.

    Four things must all be true before the workspace is touched: both
    ``--apply-approved-plan`` and ``--inspect-workspace`` must be given, the
    project config's ``read_only_workspace_inspection.enabled`` must be true,
    and the approved plan must validate and match the config exactly. The gate
    then fails closed in order: the two flags first (without either, nothing is
    read at all), then the config, then the project opt-in, then a string/path
    check rejecting an ``--approved-plan`` inside the configured workspace
    **before** it is read or stat'd, then the strict Phase 5B parse, then exact
    ``project_id``/``repo`` matching, then the candidate-count caps from
    ``max_inspected_files`` and ``max_changed_files``, then the lexical Phase 1
    path policy for **every** candidate — forbidden, outside, and unlisted
    paths always refused, and protected paths refused unless
    ``allow_protected_paths`` is true.

    Only after all of that is any path canonicalized, through the Phase 5D0
    guard honoring ``workspace_policy.allow_symlinks``. A path that does not
    exist is reported as ``missing`` and the run continues; a containment,
    symlink, ambiguity, or resolution failure stops the whole run. Any failure
    exits non-zero with stderr only and nothing on stdout, and never echoes the
    artifact text, the plan prose, or any file content.
    """
    _run_l2_inspect_workspace(
        project_config=project_config,
        approved_plan=approved_plan,
        apply_approved_plan=apply_approved_plan,
        inspect_workspace=inspect_workspace,
    )


# -- deterministic patch proposal (Phase 5E1) ----------------------------------

# Human-readable category for the Phase 5E1 generator error, following the Phase
# 4L/5C precedent: name *what kind* of thing failed. The exception message is
# safe to show — Phase 5E1 guarantees it names the failed field and category and
# never echoes the artifact text, the plan prose, or any supplied value.
_PATCH_PROPOSAL_FAILURE_CATEGORY = (
    "generation failure — the approved plan did not match this project config, "
    "was not an unescalated L1 plan, contradicted itself, exceeded the changed-"
    "file cap, or produced an artifact that failed validation"
)


def _run_generate_patch_proposal(
    *,
    project_config: Path,
    approved_plan: Path,
    apply_approved_plan: bool,
    generate_proposal: bool,
) -> None:
    """Generate a patch proposal artifact and print it. Extracted for tests.

    Ordering is the safety property, and it is the same shape as `l2-dry-run`'s
    with one more explicit consent in front of it. In sequence: both
    ``--apply-approved-plan`` and ``--generate-proposal`` must be present — with
    **no file read at all** if either is missing — then the project config
    loads, then a string/path check rejects an ``--approved-plan`` inside the
    configured workspace **before** the artifact is opened, then the artifact is
    read and strictly parsed, then the deterministic generator runs, and only
    then is anything printed.

    The generator is pure and offline, so this command reads exactly two local
    files and touches nothing else. Nothing here reads file contents from a
    workspace, lists a directory, generates a diff, edits a file, executes a
    command, reads an environment variable, opens a socket, builds a client,
    contacts GitHub, writes an artifact file, or stamps an approval.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.handoff import (
        ApprovedPlanError,
        parse_approved_l1_plan_artifact,
    )
    from ai_dev_orchestrator.patch_proposal import (
        PatchProposalGenerationError,
        build_deterministic_patch_proposal,
    )

    # 1. Explicit confirmation that an approved plan may be acted on. Checked
    #    first, so a plain invocation reads no file at all.
    if not apply_approved_plan:
        typer.echo(
            "Error: generate-patch-proposal acts on a human-approved plan "
            "artifact and requires the explicit --apply-approved-plan flag. "
            "Nothing was read.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 2. Explicit confirmation that a proposal may be produced. A second,
    #    separate consent: approving a plan is not the same act as asking for
    #    work to be proposed against it.
    if not generate_proposal:
        typer.echo(
            "Error: generate-patch-proposal produces a patch proposal artifact "
            "and requires the explicit --generate-proposal flag. Nothing was "
            "read.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 3. Project config: the first file read. The configured repo.workspace_path
    #    is never read, listed, stat'd, or resolved.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The approved plan artifact was not read and no proposal was "
            "generated.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 4. Refuse an artifact that lives inside the configured target workspace,
    #    BEFORE it is read or stat'd — which is also why --approved-plan carries
    #    no Typer exists=/readable= check: those would touch the path before this
    #    guard could run. String/path normalization only; the workspace path
    #    itself is never read, listed, stat'd, or resolved.
    if _is_same_or_under(approved_plan, project.repo.workspace_path):
        typer.echo(
            "Error: --approved-plan is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). The approved "
            "plan must live outside the workspace it authorizes; move it "
            "outside that path and retry.",
            err=True,
        )
        typer.echo(
            "The approved plan artifact was not read and no proposal was "
            "generated.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 5. The guard has passed, so the artifact may be read. It is the second and
    #    final file this command reads.
    try:
        artifact_text = approved_plan.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Error: could not read --approved-plan: {exc}", err=True)
        typer.echo("No proposal was generated.", err=True)
        raise typer.Exit(code=1)

    # 6. Parse strictly (Phase 5B). Rejected, never repaired.
    try:
        artifact = parse_approved_l1_plan_artifact(artifact_text)
    except ApprovedPlanError as exc:
        name = type(exc).__name__
        category = _APPROVED_PLAN_FAILURE_CATEGORIES.get(name, "artifact failure")
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        typer.echo(
            "The artifact text and the plan prose are not echoed. No proposal "
            "was generated.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 7. Generate deterministically and offline. The generator performs the
    #    exact identity matching against the config, re-checks the L1
    #    invariants, and fails closed on a self-contradicting plan or a
    #    candidate count above workspace_policy.max_changed_files.
    try:
        proposal = build_deterministic_patch_proposal(
            approved_plan=artifact, project=project
        )
    except PatchProposalGenerationError as exc:
        typer.echo(
            "Error: PatchProposalGenerationError: "
            f"{_PATCH_PROPOSAL_FAILURE_CATEGORY}. {exc}",
            err=True,
        )
        typer.echo(
            "The artifact text and the plan prose are not echoed. No proposal "
            "was printed and no file was written.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 8. Print the artifact itself — nothing wrapped around it, so stdout parses
    #    with parse_patch_proposal_artifact. Deliberately absent, because the
    #    artifact has no field for any of them: the configured workspace_path,
    #    any resolved absolute path, any file content, any diff, any command or
    #    command output, the raw artifact text, any prompt or completion, and any
    #    API key or base URL. The approval travels only inside the embedded
    #    approved-plan snapshot, exactly as it was given.
    _echo_json_model(proposal)


@app.command("generate-patch-proposal")
def generate_patch_proposal(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the project config YAML the approved plan must match.",
    ),
    approved_plan: Path = typer.Option(
        ...,
        "--approved-plan",
        # Deliberately no exists=/readable= check: Typer would stat the path
        # before the command body could reject one inside the configured
        # workspace. The guard runs first; the file is opened only afterwards.
        help="Path to a human-approved L1 plan artifact (Phase 5B shape). Must "
        "not be inside the project's configured workspace path.",
    ),
    apply_approved_plan: bool = typer.Option(
        False,
        "--apply-approved-plan",
        help="Required explicit confirmation that an approved plan may be "
        "acted on. Without it this command fails without reading anything.",
    ),
    generate_proposal: bool = typer.Option(
        False,
        "--generate-proposal",
        help="Required explicit confirmation that a patch proposal artifact "
        "may be produced. Without it this command fails without reading "
        "anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Turn an approved L1 plan into a **proposal-only** patch proposal artifact.

    The proposal is generated **deterministically and offline** from two local
    files — the ``--project-config`` YAML and the ``--approved-plan`` artifact,
    in that order — and nothing else. For each path the approved plan lists
    under ``files_likely_to_change`` it emits one ``modify`` change carrying a
    rationale, prose review steps, and risks. The same inputs always produce a
    byte-identical artifact.

    **It is not a diff and it is not file editing.** The artifact has no field
    for a unified diff, a patch, a hunk, an edit script, before/after content,
    source file content, a command, or command output, so there is nothing in it
    that can be applied.

    It does **not**: read, list, stat, resolve, or glob the project's configured
    ``repo.workspace_path`` or any target workspace; read any file's contents
    beyond the two files named on the command line; check whether any path the
    plan names exists; generate or apply a patch; edit or write any file; write
    the proposal to a file (stdout only); run any ``required_verification`` entry
    or any other command; create a branch, commit, or PR; fetch from or write to
    GitHub; call a model; open a socket; or read ``AIDO_LITELLM_*`` or any other
    environment variable. It never writes or stamps an approval — the approval
    must already have been written by a human, and it is carried through
    unchanged inside the embedded plan snapshot.

    The gate fails closed in order: ``--apply-approved-plan`` and
    ``--generate-proposal`` first (without either, nothing is read at all), then
    the config, then a string/path check rejecting an ``--approved-plan`` inside
    the configured workspace **before** it is read or stat'd, then the strict
    Phase 5B parse, then the generator's own exact ``project_id``/``repo``
    matching, its L1 re-check, its refusal of a path listed as both likely and
    forbidden, and the ``workspace_policy.max_changed_files`` cap. Any failure
    exits non-zero with stderr only and nothing on stdout, and never echoes the
    artifact text or the plan prose.

    Stdout is the proposal artifact itself, with no wrapper, so it parses with
    ``parse_patch_proposal_artifact``.
    """
    _run_generate_patch_proposal(
        project_config=project_config,
        approved_plan=approved_plan,
        apply_approved_plan=apply_approved_plan,
        generate_proposal=generate_proposal,
    )


# -- L2 bounded read-only file-content inspection (Phase 5D2) ------------------

_L2_READ_NOTICE = (
    "L2 READ-ONLY FILE-CONTENT INSPECTION ONLY — bounded workspace file "
    "contents may have been read and redacted, but no files were edited, no "
    "diffs were generated, no commands were run, no model was called, and no "
    "implementation occurred."
)

_L2_READ_NEXT_AUTHORIZATION = (
    "Phase 5E2 or later must be explicitly authorized before generating diffs, "
    "editing files, running commands, committing, pushing, opening PRs, or "
    "sending source contents to a model."
)

# Printed inside the content block so a reader knows exactly how far the command
# went: it proved paths exist, bounded what it opened, redacted what it printed,
# and stopped there.
_L2_READ_ITEMS_NOTE = (
    "Bounded content only. Each path was checked against the lexical path "
    "policy, canonicalized against the configured workspace root, and stat'd; "
    "it was opened only if it is a regular file within the configured byte "
    "caps. Any text shown has been passed through basic secret-like "
    "redaction, which is best-effort and not a guarantee. No directory was "
    "listed, no diff was produced, no file was written, nothing was executed, "
    "and no content was sent to a model."
)

_L2_READ_EMPTY_NOTE = (
    "The approved plan named no files_likely_to_change, so there was nothing "
    "to read and the configured workspace was not touched at all."
)

# The redaction rules moved to `ai_dev_orchestrator.redaction` in Phase 5F2D,
# unchanged. Verification output needs exactly the same treatment as workspace
# file contents, and two independently maintained secret detectors would drift —
# so there is one implementation and these are aliases onto it, kept so that the
# Phase 5D2 call sites and their tests continue to name what they always named.
_REDACTION_PLACEHOLDER = REDACTION_PLACEHOLDER
_API_KEY_PLACEHOLDER = API_KEY_PLACEHOLDER
_SECRET_ASSIGNMENT_RE = SECRET_ASSIGNMENT_RE
_BEARER_TOKEN_RE = BEARER_TOKEN_RE
_OPENAI_STYLE_KEY_RE = OPENAI_STYLE_KEY_RE
_redact_secret_like_text = redact_secret_like_text
_replace_assignment_value = _shared_replace_assignment_value


def _read_bounded_bytes(resolved_candidate: str, *, limit: int) -> bytes | None:
    """Read at most ``limit`` bytes from an already-canonicalized regular file.

    Returns ``None`` when the file holds more than ``limit`` bytes. The cap is
    enforced at the read itself rather than only against the size a previous
    ``stat`` reported, so a file that grew in between is still refused instead
    of being slurped whole.
    """
    with open(resolved_candidate, "rb") as handle:
        chunk = handle.read(limit + 1)
    return None if len(chunk) > limit else chunk


def _decode_utf8_text(chunk: bytes) -> str | None:
    """Decode strictly as UTF-8, or return ``None`` for anything else.

    An embedded NUL is rejected up front: such a file is binary in every sense
    that matters here even in the cases where its bytes happen to decode.
    """
    if b"\x00" in chunk:
        return None
    try:
        return chunk.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _empty_content_item(original: str, status: str, **overrides) -> dict:
    """One result row for a candidate whose contents were deliberately not read.

    Every status shares one shape, so a consumer never has to branch on which
    keys are present — the not-read cases simply carry a null ``content_text``
    and a zero ``bytes_read``.
    """
    item = {
        "original_plan_path": original,
        "canonical_relative_path": None,
        "status": status,
        "kind": None,
        "size_bytes": None,
        "bytes_read": 0,
        "encoding": None,
        "redacted": False,
        "redaction_count": 0,
        "redaction_kinds": [],
        "content_text": None,
    }
    item.update(overrides)
    return item


def _run_l2_read_workspace_files(
    *,
    project_config: Path,
    approved_plan: Path,
    apply_approved_plan: bool,
    read_contents: bool,
) -> None:
    """Print bounded, redacted contents of an approved plan's files. For tests.

    This is the **first shipped code that may print target workspace file
    contents**, and the ordering below is the whole safety argument. It is
    Phase 5D1's ordering with one more consent flag and one more project opt-in
    in front of it: every cheap, local, disk-free check runs first, the
    workspace is touched only after all of them pass, and a file is opened only
    after the Phase 5D0 canonical guard and a ``stat`` have both agreed it is a
    regular file inside the configured byte caps.

    In sequence: ``--apply-approved-plan``, then ``--read-contents`` (both
    before any file is read), then the project config, then the project-level
    ``read_only_workspace_content`` opt-in, then a string/path check rejecting
    an ``--approved-plan`` inside the configured workspace, then the artifact
    read, the strict Phase 5B parse, exact identity matching, the
    candidate-count caps, and the lexical Phase 1 path policy for **every**
    candidate. Only after all of that does any path get canonicalized, stat'd,
    or opened.

    Nothing here lists a directory, globs, walks a tree, generates a diff,
    executes a command, edits a file, writes any file, runs a
    ``required_verification`` entry, reads an environment variable, opens a
    socket, calls a model, or contacts GitHub. No content read here is sent
    anywhere: it goes to stdout, redacted, and nowhere else.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.handoff import (
        ApprovedPlanError,
        parse_approved_l1_plan_artifact,
    )
    from ai_dev_orchestrator.workspace import (
        CanonicalPathError,
        CanonicalPathInputError,
        PathClassification,
        PathPolicy,
        canonicalize_existing_path_under_workspace,
    )

    # 1. Explicit confirmation that an approved plan may be acted on. Checked
    #    first, so a plain invocation reads no file at all.
    if not apply_approved_plan:
        typer.echo(
            "Error: l2-read-workspace-files acts on a human-approved plan "
            "artifact and requires the explicit --apply-approved-plan flag. "
            "Nothing was read and no workspace was touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 2. Explicit confirmation that file *contents* may be read. A third,
    #    separate consent: approving a plan is not permission to examine a
    #    workspace, and permission to examine one is not permission to print
    #    what its files say.
    if not read_contents:
        typer.echo(
            "Error: l2-read-workspace-files reads and prints bounded file "
            "contents from the project's configured workspace and requires the "
            "explicit --read-contents flag. Nothing was read and no workspace "
            "was touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 3. Project config: the first file read. repo.workspace_path is still only
    #    a string at this point — it is not read, listed, stat'd, or resolved.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The approved plan artifact was not read and no workspace was "
            "touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 4. Project-level opt-in, and a different one from Phase 5D1's: a project
    #    that permits path metadata inspection has not thereby permitted its
    #    source to be printed. An absent block is identical to a disabled one,
    #    and either fails before the artifact is opened.
    content_policy = project.read_only_workspace_content
    if not content_policy.enabled:
        typer.echo(
            "Error: this project does not enable read-only workspace content "
            "reads. Set read_only_workspace_content.enabled to true in the "
            "project config to permit bounded file-content inspection.",
            err=True,
        )
        typer.echo(
            "The approved plan artifact was not read and no workspace was "
            "touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 5. Refuse an artifact that lives inside the configured target workspace,
    #    BEFORE it is read or stat'd — which is why --approved-plan carries no
    #    Typer exists=/readable= check. String/path normalization only.
    if _is_same_or_under(approved_plan, project.repo.workspace_path):
        typer.echo(
            "Error: --approved-plan is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). The approved "
            "plan must live outside the workspace it authorizes; move it "
            "outside that path and retry.",
            err=True,
        )
        typer.echo(
            "The approved plan artifact was not read and no workspace was "
            "touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 6. The guard has passed, so the artifact may be read. It is the second
    #    file this command reads, and the last one outside the workspace.
    try:
        artifact_text = approved_plan.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Error: could not read --approved-plan: {exc}", err=True)
        typer.echo("No workspace was touched.", err=True)
        raise typer.Exit(code=1)

    # 7. Parse strictly (Phase 5B). Rejected, never repaired.
    try:
        artifact = parse_approved_l1_plan_artifact(artifact_text)
    except ApprovedPlanError as exc:
        name = type(exc).__name__
        category = _APPROVED_PLAN_FAILURE_CATEGORIES.get(name, "artifact failure")
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        typer.echo(
            "The artifact text and the plan prose are not echoed. No workspace "
            "was touched and no file was read.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 8. Exact identity matching against the config (design §3.5). A plan
    #    approved for one project/repo grants nothing for another — and here
    #    that mistake would mean printing another project's source.
    mismatches = [
        f"{label}: artifact has {artifact_value!r}, project config has "
        f"{config_value!r}"
        for label, artifact_value, config_value in (
            ("project_id", artifact.project_id, project.project_id),
            ("repo", artifact.repo, project.repo.github_repo),
            ("plan.repo", artifact.plan.repo, project.repo.github_repo),
            (
                "plan_provenance.repo",
                artifact.plan_provenance.repo,
                project.repo.github_repo,
            ),
        )
        if artifact_value != config_value
    ]
    if mismatches:
        typer.echo(
            "Error: the approved plan does not match this project config "
            "exactly. A plan approved for one project/repo grants nothing for "
            "another.",
            err=True,
        )
        for mismatch in mismatches:
            typer.echo(f"  Mismatch in {mismatch}", err=True)
        typer.echo("No workspace was touched.", err=True)
        raise typer.Exit(code=1)

    plan = artifact.plan

    # 9. Candidates come from files_likely_to_change and nowhere else.
    #    files_forbidden_or_out_of_scope is never read — naming a path as out of
    #    scope must not become a way to have it printed — and proposed_steps /
    #    required_verification / risks / open_questions are prose that is never
    #    treated as a path.
    candidates = _dedupe_preserving_order(list(plan.files_likely_to_change))

    if len(candidates) > content_policy.max_files:
        typer.echo(
            f"Error: the approved plan names {len(candidates)} distinct paths, "
            "which exceeds read_only_workspace_content.max_files "
            f"({content_policy.max_files}). No workspace was touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    if len(candidates) > project.workspace_policy.max_changed_files:
        typer.echo(
            f"Error: the approved plan names {len(candidates)} distinct paths, "
            "which exceeds workspace_policy.max_changed_files "
            f"({project.workspace_policy.max_changed_files}). No workspace was "
            "touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 10. The lexical Phase 1 policy runs for EVERY candidate before any of them
    #     is canonicalized, stat'd, or opened. A single failure stops the whole
    #     run: a plan that names one forbidden path does not get the contents of
    #     its other paths printed.
    policy = PathPolicy.from_project_config(project)
    normalized: list[tuple[str, str]] = []
    refusals: list[str] = []
    for original in candidates:
        decision = policy.check_read(original)
        if decision.classification is PathClassification.PROTECTED:
            if not content_policy.allow_protected_paths:
                refusals.append(
                    f"{original!r}: classified protected, and "
                    "read_only_workspace_content.allow_protected_paths is false"
                )
                continue
        elif not decision.permitted:
            refusals.append(
                f"{original!r}: classified {decision.classification.value} "
                f"({decision.reason})"
            )
            continue
        normalized.append((original, decision.path))

    if refusals:
        typer.echo(
            "Error: the approved plan names paths the project's path policy "
            "refuses to read. The whole run is abandoned; no path was "
            "canonicalized, stat'd, opened, or otherwise touched.",
            err=True,
        )
        for refusal in refusals:
            typer.echo(f"  Refused {refusal}", err=True)
        raise typer.Exit(code=1)

    # 11. Every candidate passed the lexical gate, so — and only so — the
    #     configured workspace may be touched. The root is canonicalized first,
    #     which proves it exists, is a directory, and satisfies the symlink
    #     policy before any candidate is resolved against it. With no candidates
    #     there is nothing to read and the workspace stays untouched.
    items: list[dict] = []
    total_bytes_read = 0
    allow_symlinks = project.workspace_policy.allow_symlinks

    if normalized:
        try:
            canonicalize_existing_path_under_workspace(
                project.repo.workspace_path,
                project.repo.workspace_path,
                allow_symlinks=allow_symlinks,
            )
        except CanonicalPathError as exc:
            typer.echo(
                "Error: the configured repo.workspace_path could not be "
                f"canonicalized. {type(exc).__name__}: {exc}",
                err=True,
            )
            typer.echo("No candidate path was read.", err=True)
            raise typer.Exit(code=1)

    for original, candidate in normalized:
        try:
            resolved = canonicalize_existing_path_under_workspace(
                project.repo.workspace_path,
                candidate,
                allow_symlinks=allow_symlinks,
            )
        except CanonicalPathInputError:
            # The root was proven good above and the candidate is a non-blank
            # string that passed the lexical gate, so the only remaining input
            # failure is "this path does not exist". That is an ordinary,
            # reportable answer, not a boundary violation.
            items.append(_empty_content_item(original, "missing"))
            continue
        except CanonicalPathError as exc:
            # Containment, symlink, ambiguity, and resolution failures are
            # boundary violations. They stop the whole run.
            typer.echo(
                f"Error: {original!r} failed the canonical workspace path "
                f"guard. {type(exc).__name__}: {exc}",
                err=True,
            )
            typer.echo("The run is abandoned; no result is printed.", err=True)
            raise typer.Exit(code=1)

        relative = resolved.relative_path.replace("\\", "/")

        try:
            kind, size_bytes = _stat_kind_and_size(resolved.resolved_candidate)
        except FileNotFoundError:
            # Time-of-check/time-of-use: the path existed a moment ago and does
            # not now. Reported as missing rather than as a violation.
            items.append(_empty_content_item(original, "missing"))
            continue
        except OSError as exc:
            typer.echo(
                f"Error: metadata for {original!r} could not be read after "
                f"canonicalization. {type(exc).__name__}: {exc}",
                err=True,
            )
            typer.echo("The run is abandoned; no result is printed.", err=True)
            raise typer.Exit(code=1)

        # A directory is reported as one and its entries are never enumerated;
        # anything that is neither a regular file nor a directory is reported
        # and left alone rather than guessed at.
        if kind != "file":
            items.append(
                _empty_content_item(
                    original,
                    "directory_no_content" if kind == "directory" else "other_no_content",
                    canonical_relative_path=relative,
                    kind=kind,
                )
            )
            continue

        if size_bytes > content_policy.max_file_bytes:
            items.append(
                _empty_content_item(
                    original,
                    "too_large",
                    canonical_relative_path=relative,
                    kind=kind,
                    size_bytes=size_bytes,
                )
            )
            continue

        if total_bytes_read + size_bytes > content_policy.max_total_bytes:
            items.append(
                _empty_content_item(
                    original,
                    "skipped_total_limit",
                    canonical_relative_path=relative,
                    kind=kind,
                    size_bytes=size_bytes,
                )
            )
            continue

        # 12. Only now is a file opened, and only up to the per-file cap.
        try:
            chunk = _read_bounded_bytes(
                resolved.resolved_candidate, limit=content_policy.max_file_bytes
            )
        except FileNotFoundError:
            items.append(_empty_content_item(original, "missing"))
            continue
        except OSError as exc:
            typer.echo(
                f"Error: {original!r} could not be read after it was stat'd. "
                f"{type(exc).__name__}: {exc}",
                err=True,
            )
            typer.echo("The run is abandoned; no result is printed.", err=True)
            raise typer.Exit(code=1)

        if chunk is None:
            # The file grew past the per-file cap between the stat and the read.
            items.append(
                _empty_content_item(
                    original,
                    "too_large",
                    canonical_relative_path=relative,
                    kind=kind,
                    size_bytes=size_bytes,
                )
            )
            continue

        text = _decode_utf8_text(chunk)
        if text is None:
            items.append(
                _empty_content_item(
                    original,
                    "binary_or_non_utf8",
                    canonical_relative_path=relative,
                    kind=kind,
                    size_bytes=size_bytes,
                )
            )
            continue

        content_text, redaction_kinds = _redact_secret_like_text(text)
        total_bytes_read += len(chunk)
        items.append(
            {
                "original_plan_path": original,
                "canonical_relative_path": relative,
                "status": "read",
                "kind": kind,
                "size_bytes": size_bytes,
                "bytes_read": len(chunk),
                "encoding": "utf-8",
                "redacted": bool(redaction_kinds),
                "redaction_count": len(redaction_kinds),
                "redaction_kinds": _dedupe_preserving_order(redaction_kinds),
                "content_text": content_text,
            }
        )

    approval = artifact.approval
    provenance = artifact.plan_provenance

    # 13. Report. File content appears in exactly one place — items[].content_text,
    #     after the byte caps and after redaction. Deliberately absent: the
    #     configured workspace_path, any resolved absolute path, any directory
    #     listing, any diff or before/after pair, any command or command output,
    #     the raw artifact text, `approval_text`, any prompt or completion, and
    #     any API key or base URL. `required_verification` is absent too — this
    #     command did not run it, and reprinting it here would only invite
    #     someone to.
    output = {
        "notice": _L2_READ_NOTICE,
        "mode": "l2-read-workspace-files",
        "project": {
            "project_id": project.project_id,
            "repo": project.repo.github_repo,
            "workspace_policy": {
                "deny_outside_workspace": (
                    project.workspace_policy.deny_outside_workspace
                ),
                "allow_symlinks": project.workspace_policy.allow_symlinks,
                "max_changed_files": project.workspace_policy.max_changed_files,
            },
            "content_policy": {
                "enabled": content_policy.enabled,
                "max_files": content_policy.max_files,
                "max_file_bytes": content_policy.max_file_bytes,
                "max_total_bytes": content_policy.max_total_bytes,
                "allow_protected_paths": content_policy.allow_protected_paths,
                "redaction": "mandatory_basic_secret_like_redaction",
            },
        },
        "approved_plan": {
            "approved_by": approval.approved_by,
            "approved_at": approval.approved_at.isoformat(),
            "source": approval.source,
            "plan_engine": provenance.engine,
            "real_call": provenance.real_call,
            "model": provenance.model,
            "issue_number": artifact.issue_number,
            "title": plan.title,
        },
        "workspace_content": {
            "note": _L2_READ_ITEMS_NOTE if items else _L2_READ_EMPTY_NOTE,
            "candidate_source": "approved_plan.files_likely_to_change",
            "file_contents_read": True,
            "directories_listed": False,
            "commands_run": False,
            "model_called": False,
            "diffs_generated": False,
            "files_edited": False,
            "total_bytes_read": total_bytes_read,
            "items": items,
        },
        "next_authorization_required": _L2_READ_NEXT_AUTHORIZATION,
    }
    typer.echo(json.dumps(output, indent=2))


@app.command("l2-read-workspace-files")
def l2_read_workspace_files(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the project config YAML the approved plan must match. "
        "Its read_only_workspace_content block must enable content reads.",
    ),
    approved_plan: Path = typer.Option(
        ...,
        "--approved-plan",
        # Deliberately no exists=/readable= check: Typer would stat the path
        # before the command body could reject one inside the configured
        # workspace. The guard runs first; the file is opened only afterwards.
        help="Path to a human-approved L1 plan artifact (Phase 5B shape). Must "
        "not be inside the project's configured workspace path.",
    ),
    apply_approved_plan: bool = typer.Option(
        False,
        "--apply-approved-plan",
        help="Required explicit confirmation that an approved plan may be "
        "acted on. Without it this command fails without reading anything.",
    ),
    read_contents: bool = typer.Option(
        False,
        "--read-contents",
        help="Required explicit confirmation that bounded file contents from "
        "the project's configured workspace may be read and printed. Without "
        "it this command fails without reading anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Print bounded, redacted contents of an approved plan's files. **Read-only.**

    Phase 5D1's ``l2-inspect-workspace`` answers "does this path exist and how
    big is it". This command answers the strictly larger question "what does it
    say", and is the first shipped command whose output may contain target
    workspace source. For each path the approved plan lists under
    ``files_likely_to_change`` it canonicalizes the path against the workspace
    root, stats it, and — only for a regular file within the configured byte
    caps — reads it, decodes it as UTF-8, redacts obvious secret-like text, and
    prints the result.

    It does **not**: list, glob, or walk any directory (a candidate that *is* a
    directory is reported as ``directory_no_content`` and its entries are not
    enumerated); read any path outside ``files_likely_to_change``, including
    ``files_forbidden_or_out_of_scope``; treat ``proposed_steps``,
    ``required_verification``, ``risks``, or ``open_questions`` as paths; run
    any ``required_verification`` entry or any other command; generate a diff
    or a patch; apply anything; edit or write any file; write an artifact file
    (stdout only); create a branch, commit, or PR; fetch from or write to
    GitHub; call a model or send any file content to one; open a socket; or
    read ``AIDO_LITELLM_*`` or any other environment variable. It never writes
    or stamps an approval.

    Four things must all be true before the workspace is touched: both
    ``--apply-approved-plan`` and ``--read-contents`` must be given, the
    project config's ``read_only_workspace_content.enabled`` must be true, and
    the approved plan must validate and match the config exactly. The gate then
    fails closed in order: the two flags first (without either, nothing is read
    at all), then the config, then the project opt-in, then a string/path check
    rejecting an ``--approved-plan`` inside the configured workspace **before**
    it is read or stat'd, then the strict Phase 5B parse, then exact
    ``project_id``/``repo`` matching, then the candidate-count caps from
    ``max_files`` and ``max_changed_files``, then the lexical Phase 1 path
    policy for **every** candidate — forbidden, outside, and unlisted paths
    always refused, and protected paths refused unless ``allow_protected_paths``
    is true.

    Only after all of that is any path canonicalized, through the Phase 5D0
    guard honoring ``workspace_policy.allow_symlinks``. A missing path, a
    directory, a file over ``max_file_bytes``, a file that would breach
    ``max_total_bytes``, and a binary or non-UTF-8 file are each reported with
    a null ``content_text`` and the run continues; a containment, symlink,
    ambiguity, or resolution failure stops the whole run. Redaction is
    mandatory, best-effort, and has no off switch. Any failure exits non-zero
    with stderr only and nothing on stdout, and never echoes the artifact text,
    the plan prose, or any file content.
    """
    _run_l2_read_workspace_files(
        project_config=project_config,
        approved_plan=approved_plan,
        apply_approved_plan=apply_approved_plan,
        read_contents=read_contents,
    )


# -- deterministic diff proposal (Phase 5E3) -----------------------------------

# Human-readable categories for the Phase 5E3 generator errors, following the
# Phase 4L/5C/5E1 precedent: name *what kind* of thing failed. The exception
# messages are safe to show — Phase 5E3 guarantees they name the failed field,
# category, or path and never echo the artifact text, the plan prose, the
# proposed content, any original file content, the generated diff, or any
# secret-like value.
_DIFF_PROPOSAL_INPUT_FAILURE_CATEGORIES = {
    "DiffProposalInputParseError": (
        "input parse failure — the file was not exactly one strict JSON object"
    ),
    "DiffProposalInputValidationError": (
        "input validation failure — the JSON object was not the expected shape"
    ),
}

_DIFF_PROPOSAL_FAILURE_CATEGORY = (
    "generation failure — the approved plan, the project config, and the "
    "workspace-content packet did not match exactly, a proposed path was out of "
    "scope or had no usable recorded content, or the generated diff was refused"
)


def _fail_diff_proposal(exc: Exception, what_was_not_done: str) -> None:
    """Report a Phase 5E3 failure by category and exit non-zero. Never returns.

    The exception message is safe to show; nothing else about the inputs is.
    Deliberately not echoed here or anywhere on the failure path: the raw input
    text, the plan prose, the proposed content, any original file content, any
    generated diff text, and any secret-like value.
    """
    name = type(exc).__name__
    category = _DIFF_PROPOSAL_INPUT_FAILURE_CATEGORIES.get(
        name, _DIFF_PROPOSAL_FAILURE_CATEGORY
    )
    typer.echo(f"Error: {name}: {category}. {exc}", err=True)
    typer.echo(
        f"No input text, file content, or diff text is echoed. {what_was_not_done}",
        err=True,
    )
    raise typer.Exit(code=1)


def _read_diff_proposal_input(path: Path, label: str) -> str:
    """Read one explicitly named local input file, or fail closed. For tests.

    Called only after the workspace guard has cleared **all three** input paths,
    so no read here can reach into the configured target workspace.
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Error: could not read {label}: {exc}", err=True)
        typer.echo("No diff proposal was generated.", err=True)
        raise typer.Exit(code=1)


def _run_generate_diff_proposal(
    *,
    project_config: Path,
    approved_plan: Path,
    workspace_content: Path,
    proposed_content: Path,
    apply_approved_plan: bool,
    generate_diff: bool,
) -> None:
    """Generate a diff proposal artifact and print it. Extracted for tests.

    Ordering is the safety property, and it is `generate-patch-proposal`'s with
    two more input files in the middle. In sequence: both
    ``--apply-approved-plan`` and ``--generate-diff`` must be present — with
    **no file read at all** if either is missing — then the project config
    loads, then a string/path check rejects **any** of the three inputs that
    sits inside the configured workspace *before* any of them is opened, then
    the approved plan is read and strictly parsed, then the Phase 5D2 packet,
    then the proposed content, then the deterministic generator runs, and only
    then is anything printed.

    The generator is pure and offline, so this command reads exactly four local
    files and touches nothing else. Original source text reaches it only as data
    inside the Phase 5D2 packet named on the command line. Nothing here reads
    the configured target workspace, lists a directory, applies a diff, checks
    whether a diff applies, edits a file, executes a command, reads an
    environment variable, opens a socket, builds a client, contacts GitHub,
    writes an artifact file, or stamps an approval.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.diff_proposal import (
        DiffProposalGenerationError,
        build_deterministic_diff_proposal,
        parse_proposed_content_input,
        parse_workspace_content_packet,
    )
    from ai_dev_orchestrator.handoff import (
        ApprovedPlanError,
        parse_approved_l1_plan_artifact,
    )

    # 1. Explicit confirmation that an approved plan may be acted on. Checked
    #    first, so a plain invocation reads no file at all.
    if not apply_approved_plan:
        typer.echo(
            "Error: generate-diff-proposal acts on a human-approved plan "
            "artifact and requires the explicit --apply-approved-plan flag. "
            "Nothing was read.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 2. Explicit confirmation that diff text may be produced. A second,
    #    separate consent: approving a plan is not the same act as asking for a
    #    diff to be written against it.
    if not generate_diff:
        typer.echo(
            "Error: generate-diff-proposal produces unified diff text and "
            "requires the explicit --generate-diff flag. Nothing was read.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 3. Project config: the first file read. The configured repo.workspace_path
    #    is never read, listed, stat'd, or resolved.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "No input was read and no diff proposal was generated.", err=True
        )
        raise typer.Exit(code=1)

    # 4. Refuse any input that lives inside the configured target workspace,
    #    BEFORE any of them is read or stat'd — which is also why none of the
    #    three carries a Typer exists=/readable= check: those would touch the
    #    path before this guard could run. All three are checked together, so a
    #    later input inside the workspace cannot be reached by an earlier read.
    #    String/path normalization only; the workspace path itself is never
    #    read, listed, stat'd, or resolved.
    for label, candidate in (
        ("--approved-plan", approved_plan),
        ("--workspace-content", workspace_content),
        ("--proposed-content", proposed_content),
    ):
        if _is_same_or_under(candidate, project.repo.workspace_path):
            typer.echo(
                f"Error: {label} is inside the project's configured "
                f"repo.workspace_path ({project.repo.workspace_path}). Every "
                "input must live outside the workspace it describes; move it "
                "outside that path and retry.",
                err=True,
            )
            typer.echo(
                "No input was read and no diff proposal was generated.", err=True
            )
            raise typer.Exit(code=1)

    # 5/6. The guard has passed, so the approved plan may be read and strictly
    #      parsed (Phase 5B). Rejected, never repaired.
    artifact_text = _read_diff_proposal_input(approved_plan, "--approved-plan")
    try:
        artifact = parse_approved_l1_plan_artifact(artifact_text)
    except ApprovedPlanError as exc:
        name = type(exc).__name__
        category = _APPROVED_PLAN_FAILURE_CATEGORIES.get(name, "artifact failure")
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        typer.echo(
            "The artifact text and the plan prose are not echoed. The remaining "
            "inputs were not read and no diff proposal was generated.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 7/8. The Phase 5D2 content packet — the only source of original file text,
    #      and a file, not a workspace. Parsed immediately, so an invalid packet
    #      fails before the proposed content is opened at all.
    packet_text = _read_diff_proposal_input(workspace_content, "--workspace-content")
    try:
        packet = parse_workspace_content_packet(packet_text)
    except DiffProposalGenerationError as exc:
        _fail_diff_proposal(
            exc,
            "The proposed content was not read and no diff proposal was "
            "generated.",
        )

    # 9/10. The proposed final content, read last.
    proposed_text = _read_diff_proposal_input(proposed_content, "--proposed-content")
    try:
        proposal_input = parse_proposed_content_input(proposed_text)
    except DiffProposalGenerationError as exc:
        _fail_diff_proposal(exc, "No diff proposal was generated.")

    # 11. Generate deterministically and offline. The generator performs the
    #     exact identity matching against the config and the packet, re-checks
    #     the L1 invariants, keeps every proposed path inside the approved
    #     scope, and fails closed on missing, redacted, or wrong-kind original
    #     content and on a secret-like generated diff.
    try:
        proposal = build_deterministic_diff_proposal(
            approved_plan=artifact,
            project=project,
            workspace_content=packet,
            proposed_content=proposal_input,
        )
    except DiffProposalGenerationError as exc:
        _fail_diff_proposal(
            exc, "No diff proposal was printed and no file was written."
        )

    # 12. Print the artifact itself — nothing wrapped around it, so stdout parses
    #     with parse_diff_proposal_artifact. Deliberately absent, because the
    #     artifact has no field for any of them: the configured workspace_path,
    #     any resolved absolute path, the raw text of any input, any command or
    #     command output, any apply result, any prompt or completion, and any API
    #     key or base URL. Source text appears only as diff context inside the
    #     generated unified diffs, and the approval only inside the embedded
    #     approved-plan snapshot, exactly as it was given.
    _echo_json_model(proposal)


@app.command("generate-diff-proposal")
def generate_diff_proposal(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the project config YAML the approved plan must match.",
    ),
    approved_plan: Path = typer.Option(
        ...,
        "--approved-plan",
        # Deliberately no exists=/readable= check on any of the three inputs:
        # Typer would stat the path before the command body could reject one
        # inside the configured workspace. The guard runs first; the files are
        # opened only afterwards.
        help="Path to a human-approved L1 plan artifact (Phase 5B shape). Must "
        "not be inside the project's configured workspace path.",
    ),
    workspace_content: Path = typer.Option(
        ...,
        "--workspace-content",
        help="Path to JSON previously printed by l2-read-workspace-files. It "
        "supplies the original text to diff against. Must not be inside the "
        "project's configured workspace path.",
    ),
    proposed_content: Path = typer.Option(
        ...,
        "--proposed-content",
        help="Path to a proposed-content JSON object giving each path's final "
        "text. Must not be inside the project's configured workspace path.",
    ),
    apply_approved_plan: bool = typer.Option(
        False,
        "--apply-approved-plan",
        help="Required explicit confirmation that an approved plan may be "
        "acted on. Without it this command fails without reading anything.",
    ),
    generate_diff: bool = typer.Option(
        False,
        "--generate-diff",
        help="Required explicit confirmation that unified diff text may be "
        "produced. Without it this command fails without reading anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Turn approved-plan, recorded-content, and proposed-content JSON into diffs.

    The proposal is generated **deterministically and offline** from four local
    files — the project config, the approved plan artifact, a Phase 5D2
    ``l2-read-workspace-files`` packet, and a proposed-content JSON object, in
    that order — and nothing else. For each proposed path it runs ``difflib``
    between the original text the packet recorded and the final text the input
    supplies, and emits one single-file unified diff. The same inputs always
    produce a byte-identical artifact.

    **It generates diff text and does nothing with it.** Nothing is applied,
    staged, or written, and whether a diff would apply is never checked —
    ``applies_cleanly_checked`` is false because the question was never asked.

    It does **not**: read, list, stat, resolve, or glob the project's configured
    ``repo.workspace_path`` or any target workspace; open any of the paths the
    approved plan names — their original text arrives inside the packet or the
    generation for that path fails; apply a patch; edit or write any file; write
    the proposal to a file (stdout only); run any verification entry or any
    other command; create a branch, commit, or PR; fetch from or write to
    GitHub; call a model; open a socket; or read ``AIDO_LITELLM_*`` or any other
    environment variable. It never writes or stamps an approval — the approval
    must already have been written by a human, and it is carried through
    unchanged inside the embedded plan snapshot.

    The gate fails closed in order: ``--apply-approved-plan`` and
    ``--generate-diff`` first (without either, nothing is read at all), then the
    config, then a string/path check rejecting **any** of the three inputs
    inside the configured workspace **before** any is read or stat'd, then the
    strict Phase 5B parse, then the packet, then the proposed content, then the
    generator's exact identity matching against both the config and the packet,
    its L1 re-check, and its scope containment. Generation also fails closed
    when a proposed path is absent from the packet, when a modify's recorded
    content is missing, redacted, or not a regular file's, when a create names a
    path that was actually read, and when a generated diff matches a
    secret-like pattern — refused rather than redacted, since a redacted diff
    could never apply. Any failure exits non-zero with stderr only and nothing
    on stdout, and never echoes the artifact text, the plan prose, the proposed
    content, any file content, or any diff text.

    Stdout is the diff proposal artifact itself, with no wrapper, so it parses
    with ``parse_diff_proposal_artifact``.
    """
    _run_generate_diff_proposal(
        project_config=project_config,
        approved_plan=approved_plan,
        workspace_content=workspace_content,
        proposed_content=proposed_content,
        apply_approved_plan=apply_approved_plan,
        generate_diff=generate_diff,
    )


# -- L2 dry-run file-edit preview (Phase 5F1) ----------------------------------

# Human-readable categories for the Phase 5F0 approval errors, following the
# Phase 4L/5C/5E3 precedent: name *what kind* of thing failed. The exception
# messages are safe to show — Phase 5F0 guarantees they name the failed field
# and category and never echo the artifact text, the diff, or the approval text.
_APPROVED_DIFF_FAILURE_CATEGORIES: dict[str, str] = {
    "FileEditingApprovalParseError": (
        "parse failure — the artifact text was not exactly one strict JSON object"
    ),
    "FileEditingApprovalValidationError": (
        "validation failure — the artifact had missing, extra, or wrong-typed "
        "fields, an absent, paraphrased, or non-manual file-edit approval, an "
        "identity mismatch, a duplicate or out-of-scope path, or a malformed "
        "diff proposal"
    ),
}

_FILE_EDIT_PREVIEW_FAILURE_CATEGORY = (
    "preview failure — the approved diff proposal and the project config did "
    "not match exactly, a path was duplicated or refused by the lexical write "
    "policy, or the change count exceeded workspace_policy.max_changed_files"
)


def _run_l2_preview_file_edits(
    *,
    project_config: Path,
    approved_diff_proposal: Path,
    apply_approved_plan: bool,
    preview_file_edits: bool,
) -> None:
    """Print a dry-run preview of the writes a future phase would be allowed.

    Extracted from the command body so tests can call it directly and track
    exactly which files are read, in which order.

    Ordering is the safety property, and it is `l2-dry-run`'s with a second
    consent flag in front. In sequence: both ``--apply-approved-plan`` and
    ``--preview-file-edits`` must be present — with **no file read at all** if
    either is missing — then the project config loads, then a string/path check
    rejects an ``--approved-diff-proposal`` that sits inside the configured
    workspace *before* it is opened or stat'd, then the artifact is read and
    strictly parsed with the Phase 5F0 parser, then the pure builder runs, and
    only then is anything printed.

    This command reads exactly two local files and touches nothing else. Nothing
    here reads, lists, stat's, globs, walks, resolves, or canonicalizes the
    configured target workspace; opens any path the approved diff names; applies
    a diff; checks whether a diff applies; edits a file; executes a command;
    reads an environment variable; opens a socket; builds a client; contacts
    GitHub; creates a branch, commit, or PR; writes an artifact file; or stamps
    an approval.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.file_editing import (
        FileEditingApprovalError,
        FileEditPreviewError,
        build_file_edit_preview,
        parse_approved_diff_proposal_artifact,
    )

    # 1. Explicit confirmation that an approved plan may be acted on. Checked
    #    first, so a plain invocation reads no file at all.
    if not apply_approved_plan:
        typer.echo(
            "Error: l2-preview-file-edits acts on a human-approved artifact "
            "and requires the explicit --apply-approved-plan flag. Nothing was "
            "read.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 2. Explicit confirmation that a file-edit preview may be produced. A
    #    second, separate consent: approving a plan is not the same act as
    #    asking what a future write phase would be allowed to attempt.
    if not preview_file_edits:
        typer.echo(
            "Error: l2-preview-file-edits describes writes a future phase "
            "would attempt and requires the explicit --preview-file-edits "
            "flag. Nothing was read.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 3. Project config: the first file read. The configured repo.workspace_path
    #    is never read, listed, stat'd, resolved, or canonicalized.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The approved diff proposal artifact was not read and no preview "
            "was printed.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 4. Refuse an artifact that lives inside the configured target workspace,
    #    BEFORE it is read or stat'd — which is also why
    #    --approved-diff-proposal carries no Typer exists=/readable= check:
    #    those would touch the path before this guard could run. String/path
    #    normalization only; the workspace path itself is never read, listed,
    #    stat'd, or resolved.
    if _is_same_or_under(approved_diff_proposal, project.repo.workspace_path):
        typer.echo(
            "Error: --approved-diff-proposal is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). "
            "l2-preview-file-edits never reads target project workspaces; move "
            "the artifact outside that path and retry.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read and no preview "
            "was printed.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 5. The guard has passed, so the artifact may be read. It is the second and
    #    final file read by this command.
    try:
        artifact_text = approved_diff_proposal.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(
            f"Error: could not read --approved-diff-proposal: {exc}", err=True
        )
        typer.echo("No preview was printed.", err=True)
        raise typer.Exit(code=1)

    # 6. Parse strictly (Phase 5F0). Rejected, never repaired. This is the only
    #    place the file-edit approval comes from: it is never inferred from the
    #    wrapped L1 plan approval, from the proposal parsing, from
    #    requires_human_review, or from this file simply existing.
    try:
        artifact = parse_approved_diff_proposal_artifact(artifact_text)
    except FileEditingApprovalError as exc:
        name = type(exc).__name__
        category = _APPROVED_DIFF_FAILURE_CATEGORIES.get(name, "artifact failure")
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        typer.echo(
            "The artifact text, the approval text, and the diffs are not "
            "echoed. No preview was printed and no file was touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 7. Build the preview. The builder is pure: it performs the exact identity
    #    matching against the config, re-checks path uniqueness, enforces
    #    workspace_policy.max_changed_files, and runs the lexical Phase 1 write
    #    policy over every path — failing the whole preview on any refusal.
    try:
        report = build_file_edit_preview(approved_diff=artifact, project=project)
    except FileEditPreviewError as exc:
        typer.echo(
            f"Error: FileEditPreviewError: {_FILE_EDIT_PREVIEW_FAILURE_CATEGORY}. "
            f"{exc}",
            err=True,
        )
        typer.echo(
            "No preview was printed, no file was edited, and no workspace was "
            "touched.",
            err=True,
        )
        raise typer.Exit(code=1)

    # 8. Print the report itself — nothing wrapped around it. Deliberately
    #    absent, because the report has no field for any of them: any unified
    #    diff, any source contents, the raw artifact text, the approval text,
    #    the configured workspace_path, any resolved absolute path, any command
    #    or command output, any apply result, any branch/commit/push/PR claim,
    #    and any API key or base URL.
    _echo_json_model(report)


@app.command("l2-preview-file-edits")
def l2_preview_file_edits(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the project config YAML the approved diff must match.",
    ),
    approved_diff_proposal: Path = typer.Option(
        ...,
        "--approved-diff-proposal",
        # Deliberately no exists=/readable= check: Typer would stat the path
        # before the command body could reject one inside the configured
        # workspace. The guard runs first; the file is opened only afterwards.
        help="Path to a human-approved diff proposal artifact (Phase 5F0 "
        "shape). Must not be inside the project's configured workspace path.",
    ),
    apply_approved_plan: bool = typer.Option(
        False,
        "--apply-approved-plan",
        help="Required explicit confirmation that a human-approved artifact "
        "may be acted on. Without it this command fails without reading "
        "anything.",
    ),
    preview_file_edits: bool = typer.Option(
        False,
        "--preview-file-edits",
        help="Required explicit confirmation that a dry-run file-edit preview "
        "may be produced. Without it this command fails without reading "
        "anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Print what a future file-editing phase would be allowed to attempt.

    **Dry-run preview only, and nothing here edits a file.** This command reads
    exactly two local files — the ``--project-config`` YAML and the
    ``--approved-diff-proposal`` artifact, in that order — validates the
    artifact with the Phase 5F0 parser, checks it against the config and the
    lexical Phase 1 write policy, and prints a JSON report describing the writes
    a future, separately authorized phase *would* be permitted to try.

    The report names each permitted path, its change type, and **counts** of its
    diff — bytes, lines, hunks, added, removed, context. It carries no unified
    diff text and no source contents.

    It does **not**: read, list, stat, glob, walk, resolve, or canonicalize the
    project's configured ``repo.workspace_path`` or any target workspace; open
    any path the approved diff names; check whether any of those paths exists or
    what it currently contains; apply a diff or check whether one would apply;
    edit or write any file; write the report to a file (stdout only); run any
    ``required_verification`` entry or any other command; create a branch,
    commit, or PR; fetch from or write to GitHub; call a model; open a socket;
    or read ``AIDO_LITELLM_*`` or any other environment variable.

    It also never writes or stamps an approval. The file-edit approval must
    already have been written by a human, in the exact Phase 5F0 wording, and it
    is never inferred from the wrapped L1 plan approval, from the diff proposal
    existing or parsing, from ``requires_human_review``, or from this file being
    present.

    The gate fails closed in order: ``--apply-approved-plan`` and
    ``--preview-file-edits`` first (without either, nothing is read at all),
    then the config, then a string/path check rejecting an
    ``--approved-diff-proposal`` inside the configured workspace **before** it
    is read or stat'd, then the strict Phase 5F0 parse, then exact identity
    matching against the config in all six places the artifact records it, then
    path uniqueness, the ``max_changed_files`` cap, and the lexical write policy
    — where a forbidden, unlisted, traversal-escaping, or **protected** path
    fails the whole preview rather than being reported as denied. Any failure
    exits non-zero with stderr only and nothing on stdout, and never echoes the
    artifact text, the approval text, any diff, or any file content.

    Stdout is the preview report itself, with no wrapper.
    """
    _run_l2_preview_file_edits(
        project_config=project_config,
        approved_diff_proposal=approved_diff_proposal,
        apply_approved_plan=apply_approved_plan,
        preview_file_edits=preview_file_edits,
    )


# -- L2 controlled single-file write (Phase 5F2C) ------------------------------

# Exit codes, kept distinct because conflating them is the failure mode §13 of
# the phase scope exists to prevent. 1 means "refused, and the target is
# unchanged"; 3 means "a write was attempted and its final state could not be
# proved" — never the same claim.
_WRITE_EXIT_REFUSED = 1
_WRITE_EXIT_INDETERMINATE = 3


def _run_l2_apply_approved_file_edit(
    *,
    project_config: Path,
    approved_diff_proposal: Path,
    apply_approved_plan: bool,
    write_approved_file: bool,
) -> None:
    """Apply one approved single-file modification, or refuse having done nothing.

    Extracted from the command body so tests can call it directly and track
    exactly which files are read, in which order.

    Ordering is the safety property. In sequence: both ``--apply-approved-plan``
    and ``--write-approved-file`` must be present — with **no file read at all**
    if either is missing — then the project config loads, then
    ``workspace_write.enabled`` must be true, then the platform must be Windows
    (all three before any target workspace is touched), then a string/path check
    rejects an ``--approved-diff-proposal`` that sits inside the configured
    workspace *before* it is opened or stat'd, then the artifact is read and
    strictly parsed, and only then does the writer begin its workspace and Git
    checks.

    This command runs **no** project verification command, no model-proposed
    command, and no shell. The only subprocess it can cause is the closed set of
    fixed Git inspection commands the writer's own correctness contract needs.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.file_editing import (
        FileEditingApprovalError,
        WorkspaceWriteIndeterminateError,
        WorkspaceWriteRefusedError,
        apply_approved_file_edit,
        parse_approved_diff_proposal_artifact,
    )

    # 1. Explicit confirmation that an approved plan may be acted on.
    if not apply_approved_plan:
        typer.echo(
            "Error: l2-apply-approved-file-edit acts on a human-approved "
            "artifact and requires the explicit --apply-approved-plan flag. "
            "Nothing was read and nothing was written.",
            err=True,
        )
        raise typer.Exit(code=_WRITE_EXIT_REFUSED)

    # 2. Explicit confirmation that a file may actually be written. A second,
    #    separate consent: approving a diff is not the same act as telling this
    #    tool to modify a real file on disk right now.
    if not write_approved_file:
        typer.echo(
            "Error: l2-apply-approved-file-edit writes one real file into a "
            "target workspace and requires the explicit --write-approved-file "
            "flag. Nothing was read and nothing was written.",
            err=True,
        )
        raise typer.Exit(code=_WRITE_EXIT_REFUSED)

    # 3. Project config: the first file read.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The approved diff proposal artifact was not read and nothing was "
            "written.",
            err=True,
        )
        raise typer.Exit(code=_WRITE_EXIT_REFUSED)

    # 4. The project-level write opt-in. Checked before the artifact is opened
    #    and long before the workspace is touched: a project that has not opted
    #    in is not one this command may look at, let alone write.
    if not project.workspace_write.enabled:
        typer.echo(
            "Error: this project's workspace_write block is absent or disabled, "
            "so no file may be written for it. Set workspace_write.enabled to "
            "true in the project config to permit it.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read and no target "
            "workspace was touched.",
            err=True,
        )
        raise typer.Exit(code=_WRITE_EXIT_REFUSED)

    # 5. Platform. The Phase 5F2C writer is explicitly Windows-only, and it
    #    refuses here — before any target workspace touch — rather than
    #    pretending to be portable.
    if sys.platform != "win32":
        typer.echo(
            "Error: the Phase 5F2C writer is Windows-only. It refuses on this "
            "platform rather than applying write and metadata semantics it has "
            "not reasoned about here.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read and no target "
            "workspace was touched.",
            err=True,
        )
        raise typer.Exit(code=_WRITE_EXIT_REFUSED)

    # 6. Refuse an artifact that lives inside the configured target workspace,
    #    BEFORE it is read or stat'd — the same lexical guard every earlier
    #    phase uses, and the reason --approved-diff-proposal carries no Typer
    #    exists=/readable= check.
    if _is_same_or_under(approved_diff_proposal, project.repo.workspace_path):
        typer.echo(
            "Error: --approved-diff-proposal is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). The approval "
            "must live outside the workspace it authorizes writing to; move the "
            "artifact and retry.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read and nothing was "
            "written.",
            err=True,
        )
        raise typer.Exit(code=_WRITE_EXIT_REFUSED)

    # 7. The artifact: the second and final file read by this command.
    try:
        artifact_text = approved_diff_proposal.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(
            f"Error: could not read --approved-diff-proposal: {exc}", err=True
        )
        typer.echo("Nothing was written.", err=True)
        raise typer.Exit(code=_WRITE_EXIT_REFUSED)

    # 8. Parse strictly. Rejected, never repaired. This is the only place the
    #    file-edit approval comes from, and it is never inferred from anything
    #    else.
    try:
        artifact = parse_approved_diff_proposal_artifact(artifact_text)
    except FileEditingApprovalError as exc:
        name = type(exc).__name__
        category = _APPROVED_DIFF_FAILURE_CATEGORIES.get(name, "artifact failure")
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        typer.echo(
            "The artifact text, the approval text, and the diffs are not "
            "echoed. Nothing was written and no target workspace was touched.",
            err=True,
        )
        raise typer.Exit(code=_WRITE_EXIT_REFUSED)

    # 9. The writer. Every remaining gate — identity, single-change, modify-only,
    #    lexical write policy, canonical write target, regular file, hard-link
    #    count, Windows attributes, clean Git baseline, simple index, tracked
    #    target, pre-image identity, strict diff application, post-image
    #    identity, final revalidation, the replacement, and post-write
    #    verification — lives there.
    try:
        report = apply_approved_file_edit(approved_diff=artifact, project=project)
    except WorkspaceWriteRefusedError as exc:
        typer.echo(f"Error: refused-before-write: {exc}", err=True)
        typer.echo(
            "The target file was NOT modified. No source, diff, approval text, "
            "or absolute path is echoed.",
            err=True,
        )
        raise typer.Exit(code=_WRITE_EXIT_REFUSED)
    except WorkspaceWriteIndeterminateError as exc:
        typer.echo(
            "Error: write-attempted-state-indeterminate: " + str(exc), err=True
        )
        typer.echo(
            "A file replacement was ATTEMPTED. This is not a claim that nothing "
            "changed. Nothing was retried, nothing was rolled back, and no git "
            "restore was run. HUMAN REPOSITORY INSPECTION IS REQUIRED: compare "
            "the working tree against the clean baseline this run proved before "
            "writing.",
            err=True,
        )
        raise typer.Exit(code=_WRITE_EXIT_INDETERMINATE)

    # 10. Print the report itself — nothing wrapped around it. Deliberately
    #     absent, because the report has no field for any of them: the
    #     configured workspace path, any absolute path, the raw artifact text,
    #     the approval text, the approved unified diff, any unrelated source
    #     file, any arbitrary command output, and any API key or base URL.
    _echo_json_model(report)


@app.command("l2-apply-approved-file-edit")
def l2_apply_approved_file_edit(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the project config YAML the approved diff must match. Its "
        "workspace_write block must be enabled.",
    ),
    approved_diff_proposal: Path = typer.Option(
        ...,
        "--approved-diff-proposal",
        # Deliberately no exists=/readable= check: Typer would stat the path
        # before the command body could reject one inside the configured
        # workspace. The guard runs first; the file is opened only afterwards.
        help="Path to a human-approved diff proposal artifact "
        "(approved-diff-proposal.v2). Must not be inside the project's "
        "configured workspace path.",
    ),
    apply_approved_plan: bool = typer.Option(
        False,
        "--apply-approved-plan",
        help="Required explicit confirmation that a human-approved artifact may "
        "be acted on. Without it this command fails without reading anything.",
    ),
    write_approved_file: bool = typer.Option(
        False,
        "--write-approved-file",
        help="Required explicit confirmation that one real file may be written "
        "into the target workspace. Without it this command fails without "
        "reading anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Apply ONE approved single-file modification to a target workspace.

    **This command writes a real file.** It is the first and only one in this
    repository that does. What it can write is deliberately one thing: an exact
    approved modification of one existing, Git-tracked, ordinary UTF-8 file
    inside one wholly clean Windows Git repository whose top level is exactly
    the configured workspace root.

    Everything else fails closed. There is no file creation, no delete, no
    rename, no second file, no protected path, no fuzzy patching, no force
    override, no protected-path override, and no rollback switch — because none
    of those capabilities exists here to be turned on.

    The transformation is bound at **both ends**: the approved artifact carries
    the pre-image and post-image SHA-256 of the whole file, the destination's
    current bytes must hash to the approved pre-image, the diff is applied
    **exactly** (no fuzz, no offset search, no nearest-match, no three-way
    merge, no repair), and the result must hash to the approved post-image
    before anything is written. Immediately before the replacement, the
    canonical target, the file's attributes, its hard-link count, its bytes and
    the clean Git baseline are all re-established from scratch.

    It does **not**: run ``required_verification``, pytest, npm, make, a build
    script, or any other project-configured or model-proposed command; invoke a
    shell; call a model; open a socket; contact GitHub; create a branch;
    commit; push; open a PR; or read ``AIDO_LITELLM_*`` or any other
    environment variable for credentials. The only subprocess it can cause is a
    closed set of fixed, read-only Git inspection commands that the writer's own
    correctness contract requires.

    The gate fails closed in order: ``--apply-approved-plan`` and
    ``--write-approved-file`` first (without either, nothing is read at all),
    then the config, then ``workspace_write.enabled``, then the Windows-only
    platform check, then a string/path check rejecting an
    ``--approved-diff-proposal`` inside the configured workspace **before** it
    is read or stat'd, then the strict parse, then every writer gate.

    Exit codes are distinct on purpose. **1** means refused before any write —
    the target is unchanged. **3** means a replacement was attempted and its
    final state could not be proved; that is never reported as "nothing
    changed", nothing is retried or rolled back, and a human must inspect the
    repository against the clean baseline.

    On success stdout is the result report itself, with no wrapper. The change
    is left **uncommitted** in the working tree for human review.
    """
    _run_l2_apply_approved_file_edit(
        project_config=project_config,
        approved_diff_proposal=approved_diff_proposal,
        apply_approved_plan=apply_approved_plan,
        write_approved_file=write_approved_file,
    )


# -- L2 controlled verification (Phase 5F2D) -----------------------------------

# Three exit categories, kept distinct because conflating any two of them is the
# failure mode this phase exists to avoid:
#
#   1  refused before any project process was started; the workspace is
#      untouched and stdout is empty.
#   2  a verification process ran and did not pass — a non-zero exit, a timeout,
#      or an output-cap kill. That is a legitimate answer about the code, not an
#      AIDO error, and the structured result is printed.
#   3  a verification process ran and afterwards the repository is not provably
#      the approved state. Never reported as merely "failed"; nothing is
#      repaired, restored, or retried, and a human must inspect the repository.
_VERIFY_EXIT_REFUSED = 1
_VERIFY_EXIT_NOT_PASSED = 2
_VERIFY_EXIT_WORKSPACE_UNTRUSTED = 3


def _run_l2_verify_approved_file_edit(
    *,
    project_config: Path,
    approved_diff_proposal: Path,
    apply_approved_plan: bool,
    verify_approved_file_edit_flag: bool,
) -> None:
    """Execute one configured verification process, or refuse having run nothing.

    Extracted from the command body so tests can call it directly and track
    exactly which files are read, in which order.

    Ordering is the safety property, and it is the writer's ordering with one
    substitution. In sequence: both ``--apply-approved-plan`` and
    ``--verify-approved-file-edit`` must be present — with **no file read at
    all** if either is missing — then the project config loads, then
    ``controlled_verification.enabled`` must be true, then the platform must be
    Windows (all three before any target workspace is touched), then a
    string/path check rejects an ``--approved-diff-proposal`` that sits inside
    the configured workspace *before* it is opened or stat'd, then the artifact
    is read and strictly parsed, and only then does the verifier begin its
    workspace, Git, and execution work.

    **The executable and its arguments come only from the project config.**
    There is no ``--command``, ``--executable``, ``--args``, ``--shell`` or
    ``--verification`` option, and the L1 plan's ``required_verification`` is
    never consulted for execution authority.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.file_editing import (
        FileEditingApprovalError,
        parse_approved_diff_proposal_artifact,
    )
    from ai_dev_orchestrator.verification import (
        VerificationRefusedError,
        verify_approved_file_edit,
    )

    # 1. Explicit confirmation that an approved plan may be acted on.
    if not apply_approved_plan:
        typer.echo(
            "Error: l2-verify-approved-file-edit acts on a human-approved "
            "artifact and requires the explicit --apply-approved-plan flag. "
            "Nothing was read and nothing was executed.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_REFUSED)

    # 2. Explicit confirmation that a project's own program may actually be run.
    #    A second, separate consent: approving a diff is not the same act as
    #    telling this tool to execute repository-controlled code right now.
    if not verify_approved_file_edit_flag:
        typer.echo(
            "Error: l2-verify-approved-file-edit executes the project's own "
            "configured verification process — repository-controlled code, in a "
            "process AIDO does not sandbox — and requires the explicit "
            "--verify-approved-file-edit flag. Nothing was read and nothing was "
            "executed.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_REFUSED)

    # 3. Project config: the first file read.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The approved diff proposal artifact was not read and nothing was "
            "executed.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_REFUSED)

    # 4. The project-level verification opt-in. Checked before the artifact is
    #    opened and long before the workspace is touched or anything is launched.
    if not project.controlled_verification.enabled:
        typer.echo(
            "Error: this project's controlled_verification block is absent or "
            "disabled, so no verification process may be executed for it. Set "
            "controlled_verification.enabled to true, and configure an absolute "
            "executable and its exact args, to permit it.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read, no target "
            "workspace was touched, and no process was launched.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_REFUSED)

    # 5. Platform. This phase verifies a Phase 5F2C write, and that writer is
    #    explicitly Windows-only.
    if sys.platform != "win32":
        typer.echo(
            "Error: Phase 5F2D verifies a Phase 5F2C write, and that writer is "
            "Windows-only. It refuses on this platform rather than reasoning "
            "about semantics it has not established here.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read, no target "
            "workspace was touched, and no process was launched.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_REFUSED)

    # 6. Refuse an artifact that lives inside the configured target workspace,
    #    BEFORE it is read or stat'd — the same lexical guard every earlier phase
    #    uses, and the reason --approved-diff-proposal carries no Typer exists=
    #    check.
    if _is_same_or_under(approved_diff_proposal, project.repo.workspace_path):
        typer.echo(
            "Error: --approved-diff-proposal is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). The approval "
            "must live outside the workspace it refers to; move the artifact and "
            "retry.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read and nothing was "
            "executed.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_REFUSED)

    # 7. The artifact: the second and final file read by this command.
    try:
        artifact_text = approved_diff_proposal.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(
            f"Error: could not read --approved-diff-proposal: {exc}", err=True
        )
        typer.echo("Nothing was executed.", err=True)
        raise typer.Exit(code=_VERIFY_EXIT_REFUSED)

    # 8. Parse strictly. Rejected, never repaired.
    try:
        artifact = parse_approved_diff_proposal_artifact(artifact_text)
    except FileEditingApprovalError as exc:
        name = type(exc).__name__
        category = _APPROVED_DIFF_FAILURE_CATEGORIES.get(name, "artifact failure")
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        typer.echo(
            "The artifact text, the approval text, and the diffs are not "
            "echoed. Nothing was executed and no target workspace was touched.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_REFUSED)

    # 9. The verifier. Every remaining gate — identity, single-change,
    #    modify-only, lexical write policy, canonical target, executable
    #    validation, the exact approved post-image, the Git baseline of exactly
    #    one approved dirty target, the single bounded execution, and the
    #    post-execution state proof — lives there.
    try:
        report = verify_approved_file_edit(approved_diff=artifact, project=project)
    except VerificationRefusedError as exc:
        typer.echo(f"Error: refused-before-execution: {exc}", err=True)
        typer.echo(
            "No verification process was started. No source, diff, approval "
            "text, absolute path, or environment value is echoed.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_REFUSED)

    # 10. Print the report itself — nothing wrapped around it — for every outcome
    #     in which a process actually ran. A failing verification and an
    #     untrusted workspace are both results a human needs to read, not errors
    #     to swallow.
    _echo_json_model(report)

    if report.outcome == "workspace-state-untrusted":
        typer.echo(
            "Error: workspace-state-untrusted: the verification process ran, and "
            "afterwards the repository is NOT provably the approved state. This "
            "is not a claim that verification merely failed. Nothing was "
            "repaired, nothing was restored, no git restore was run, and nothing "
            "was retried. HUMAN REPOSITORY INSPECTION IS REQUIRED.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_WORKSPACE_UNTRUSTED)

    if report.outcome == "verification-failed":
        typer.echo(
            "Verification did not pass. The workspace is still exactly the "
            "approved change; nothing was retried, repaired, restored, or "
            "committed.",
            err=True,
        )
        raise typer.Exit(code=_VERIFY_EXIT_NOT_PASSED)


@app.command("l2-verify-approved-file-edit")
def l2_verify_approved_file_edit(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the project config YAML the approved diff must match. Its "
        "controlled_verification block must be enabled and must name the exact "
        "absolute executable and args that may run.",
    ),
    approved_diff_proposal: Path = typer.Option(
        ...,
        "--approved-diff-proposal",
        # Deliberately no exists=/readable= check: Typer would stat the path
        # before the command body could reject one inside the configured
        # workspace. The guard runs first; the file is opened only afterwards.
        help="Path to the human-approved diff proposal artifact "
        "(approved-diff-proposal.v2) whose modification has already been "
        "applied. Must not be inside the project's configured workspace path.",
    ),
    apply_approved_plan: bool = typer.Option(
        False,
        "--apply-approved-plan",
        help="Required explicit confirmation that a human-approved artifact may "
        "be acted on. Without it this command fails without reading anything.",
    ),
    verify_approved_file_edit_flag: bool = typer.Option(
        False,
        "--verify-approved-file-edit",
        help="Required explicit confirmation that the project's own configured "
        "verification process may be executed. Without it this command fails "
        "without reading anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Execute ONE configured verification process against ONE applied edit.

    **This command runs repository-controlled code.** It is the first and only
    one in this repository that does. Phase 5F2C's writer runs a fixed,
    AIDO-owned, read-only Git inspection set as part of its own correctness
    contract; this command launches a program the *project* chose — typically a
    test runner — which may import arbitrary project modules, execute
    ``conftest.py``, create files, open network connections and spawn children.

    **Controlled invocation is not sandboxed execution.** AIDO controls which
    absolute executable is launched, with which exact arguments, in which
    directory, with which minimal environment, how long **AIDO waits**, and how
    much output it may produce. AIDO does **not** confine what that process then
    does, does **not** track its descendants — which may still be running after
    this command returns — and the result report says so rather than claiming the
    run touched nothing. Every AIDO-owned negative claim in the report carries an
    ``orchestrator_`` prefix precisely so that none of them can be read as a
    statement about the verification child.

    Command authority comes only from the project config's
    ``controlled_verification`` block: one absolute executable that must exist,
    be a regular file, and resolve **outside** the target workspace, plus an
    exact ordered argv list used verbatim. There is no shell, no command string,
    no PATH lookup, no default executable, no interpolation or templating, no
    working-directory override, no retry, and no CLI option through which a
    command, an executable, or an argument could be supplied — the executable
    and its arguments are project-config authority, never CLI authority, and
    never model, plan, or artifact authority. The L1 plan's
    ``required_verification`` is
    planner-controlled prose that may have been written by a model: it is
    **never** split, parsed, run, or turned into argv.

    Verification is bound to the exact already-applied approved change. Before
    anything is launched, the approved target must canonicalize inside the
    workspace, be a regular file, hash to the approved ``post_image_sha256``
    exactly, be tracked as one ordinary stage-0 blob, and be the **only**
    Git-visible dirty path — as a plain unstaged modification, with nothing
    staged, untracked, deleted, renamed, unmerged, or submodule-shaped anywhere.
    The exact ``HEAD`` object id is captured too, and all of it is re-proved
    after the process terminates: a verification that moves the baseline commit
    (``git commit --allow-empty``, say) is refused as an untrusted workspace even
    though the target's bytes and dirty status are untouched.

    Exit codes are distinct on purpose. **1** means refused before any process
    started. **2** means a process ran and verification did not pass — a non-zero
    exit, a timeout, or an output-cap kill — with the workspace still exactly the
    approved change. **3** means a process ran and the repository is no longer
    provably the approved state; that is never reported as "verification failed",
    nothing is repaired, restored, or retried, and a human must inspect the
    repository.

    Nothing here calls a model, contacts GitHub, creates a branch, commits,
    pushes, or opens a PR, and no reviewer or fixer runs.
    """
    _run_l2_verify_approved_file_edit(
        project_config=project_config,
        approved_diff_proposal=approved_diff_proposal,
        apply_approved_plan=apply_approved_plan,
        verify_approved_file_edit_flag=verify_approved_file_edit_flag,
    )


# -- L2 controlled reviewer integration (Phase 5F2E) ---------------------------

# Five exit categories. The first three are Phase 5F2D's, unchanged in meaning,
# because this command runs that verifier and must not reinterpret it:
#
#   1  refused before any project process was started.
#   2  a verification process ran and did not pass. No model was contacted.
#   3  a verification process ran and the repository is no longer provably the
#      approved state. No model was contacted.
#   4  verification PASSED and the reviewer stage failed — environment, client,
#      transport, strict JSON, or schema/consistency validation. The approved
#      change is untouched and the same command may be run again.
#   0  the reviewer produced a valid structured result. All three verdicts —
#      approve, changes_requested, needs_human_review — are successful reviewer
#      completions, not runtime errors.
_REVIEW_EXIT_REFUSED = 1
_REVIEW_EXIT_VERIFICATION_NOT_PASSED = 2
_REVIEW_EXIT_WORKSPACE_UNTRUSTED = 3
_REVIEW_EXIT_REVIEWER_FAILED = 4

# Human-readable categories for the reviewer-stage failures, following the Phase
# 4L precedent: name *what kind* of thing failed. None of these messages may carry
# the raw model response, the prompt, the approved diff, the API key, or the base
# URL — the review module's own messages are built from fixed strings and field
# names for exactly that reason.
_REVIEWER_FAILURE_CATEGORIES: dict[str, str] = {
    # Deliberately provider-neutral. Two reviewer providers exist, so naming one
    # family here would misdescribe a failure of the other — and "disallowed"
    # covers the case where the settings were present and well-formed but the
    # transport was refused, such as a direct vLLM endpoint on plaintext HTTP
    # without the project opt-in. The raised exception carries the specific,
    # safe detail (which environment variable NAME is required, or why the
    # transport was refused); this category never does.
    "ReviewerEnvironmentError": (
        "reviewer connection configuration failure — the configured reviewer "
        "connection settings were missing, invalid, or disallowed"
    ),
    "ReviewerTransportError": (
        "reviewer transport failure — the endpoint call failed under the LLM "
        "client's existing policy"
    ),
    "ReviewParseError": (
        "reviewer parse failure — the reply was not exactly one strict JSON object"
    ),
    "ReviewValidationError": (
        "reviewer validation failure — the reply had missing, extra, or "
        "wrong-typed fields, supplied an orchestrator-controlled field, exceeded "
        "a bound, or carried a verdict its findings contradict"
    ),
    "ReviewerAttemptExhaustedError": (
        "reviewer unavailable — the bounded supervised attempt budget produced "
        "no valid review"
    ),
}


def _echo_supervision_event(event) -> None:
    """Print one Phase 5F2E-RS1 circuit-breaker signal to stderr.

    Three kinds, and the wording distinguishes them because they are genuinely
    different failures:

    - ``stalled`` — AIDO stopped waiting, because the client reported a timeout
      or because AIDO's own attempt deadline expired first, and that is
      **terminal**. Announced as ``REVIEW STALLED``, and it must never say a
      compact retry was authorized: AIDO's wait ending is not the request ending,
      and it cannot observe whether the backend released its inference slot, so
      issuing a second request could put two concurrent inference jobs on the
      same model. An ``unavailable`` block always follows, and attempts used
      stays at what was actually issued;
    - ``unusable`` — a response **came back** and was rejected by the strict
      parser, or the provider reported an output length limit. Announced as
      ``REVIEW UNUSABLE``, because calling a parse error a stall would
      misdescribe it. This is the only notice that precedes a compact retry;
    - ``unavailable`` — the terminal notice, printed once no further request is
      authorized.

    The event object carries only a model name, attempt counters and a
    classification token, so this function **cannot** print the prompt, the diff,
    the completion, an API key, a base URL, or an absolute path — there is no
    field holding one.
    """
    if event.kind == "unavailable":
        lines = (
            "=== REVIEWER UNAVAILABLE FOR THIS REVIEW ===",
            f"Model:            {event.model}",
            f"Attempts used:    {event.attempts_used} of at most "
            f"{event.max_attempts} semantic requests AIDO may issue "
            "(one HTTP/model request each)",
            f"Final category:   {event.outcome} — {event.outcome_label}",
            "No fallback reviewer model was contacted, no further semantic "
            "request was made, and no transport retry was performed.",
            "A HUMAN DECISION IS REQUIRED. Nothing was fixed, patched, "
            "reverted, committed, or pushed by AIDO's review stage.",
            "=" * 74,
        )
    elif event.kind == "stalled":
        lines = (
            "=== REVIEW STALLED ===",
            f"Model:            {event.model}",
            f"Attempt:          {event.attempt} (semantic requests issued: "
            f"{event.attempts_used})",
            f"Classification:   {event.outcome} — {event.outcome_label}",
            "AIDO stopped waiting for this request when its own attempt deadline "
            "elapsed, or when the client reported a timeout.",
            "AIDO's WAIT ended. That is NOT the same as the request ending: the "
            "worker performing the call is ABANDONED, not stopped, and its HTTP "
            "request may still be active.",
            "Backend cancellation / inference termination is NOT observed: the "
            "model may still be generating on the server, holding its inference "
            "slot and context.",
            "NO compact retry is being issued. A second request could place a "
            "SECOND concurrent inference job on the same model, increasing the "
            "GPU, concurrency and context pressure this bound exists to contain.",
            "The reviewer is UNAVAILABLE for this review and a HUMAN DECISION "
            "IS REQUIRED.",
            "=" * 74,
        )
    else:
        lines = (
            "=== REVIEW UNUSABLE — compact retry authorized ===",
            f"Model:            {event.model}",
            f"Attempt:          {event.attempt} of {event.max_attempts}",
            f"Classification:   {event.outcome} — {event.outcome_label}",
            "A response WAS returned and was unusable, so the first request is "
            "no longer in flight and one smaller request is safe to issue.",
            "AIDO will now make EXACTLY ONE compact retry, with a reduced "
            "context and the SAME configured reviewer model.",
            "No fallback reviewer is being selected, no third request exists, "
            "and the first reply is discarded rather than repaired or merged.",
            "=" * 74,
        )

    for line in lines:
        typer.echo(line, err=True)


def _reviewer_transport_line(notice) -> str:
    """One unmistakable line about whether the transport is encrypted.

    Derived from the endpoint's URL **scheme** only — the one URL component that
    carries neither credential nor payload. The base URL itself, its userinfo,
    path and query are never printed, and there is no field here holding them.

    A plaintext endpoint says so in capitals. It is never softened by where the
    endpoint happens to sit: an internal, colleague-hosted, or same-network HTTP
    endpoint is not private, and this line must never imply that it is.
    """
    if notice.transport_tls:
        return f"{notice.endpoint_scheme.upper()} — TLS-encrypted"
    return (
        f"{notice.endpoint_scheme.upper()} — NOT TLS-ENCRYPTED. Source-derived "
        "code will be sent UNENCRYPTED over this network path. Being internal, "
        "colleague-hosted, or on a particular network does NOT make it private."
    )


def _echo_reviewer_banner(notice) -> None:
    """Print the non-suppressible pre-call warning block to stderr.

    Follows the Phase 4 real-model command pattern, and says the one thing those
    banners never had to: **source-derived code is about to leave the machine.**
    Host only — never the base URL (which may embed userinfo or a query string),
    never the API key, and never the diff itself.

    Phase 5F2E-V2 added one safe line: whether the request carries a JSON-Schema
    generation constraint. It prints the **mode token** (``none`` or
    ``json_schema``) and never the schema document itself.

    The issue **title** is deliberately absent. It is free-form third-party text
    that may contain newlines and banner-shaped lines, and this block is a
    non-suppressible human-facing safety notice: a hostile title could forge
    banner lines here and misrepresent what is being transmitted. The prompt
    contains that text inside untrusted-data delimiters, but a terminal has no
    such boundary. ``ReviewerCallNotice`` therefore has no ``title`` field at
    all, so this function cannot print one — no escaping or sanitization
    machinery was added for it. The issue number identifies the run; the title
    still appears in the review packet and the model request.
    """
    for line in (
        "=== REAL REVIEWER MODEL CALL — a real network call is about to be made ===",
        f"Provider:      {notice.provider}",
        f"Endpoint host: {notice.endpoint_host}",
        f"Transport:     {_reviewer_transport_line(notice)}",
        f"Model:         {notice.model}",
        # Phase 5F2E-V2. The MODE token only — never the schema document, the
        # response_format request JSON, the prompt, or the diff.
        f"Structured output: {notice.structured_output_mode}",
        f"Project:       {notice.project_id}",
        f"Repo:          {notice.repo}",
        f"Issue:         #{notice.issue_number}",
        "SOURCE-DERIVED CODE WILL BE TRANSMITTED to the model above:",
        "  - the ONE human-approved unified diff for the one approved file;",
        "  - selected approved-plan prose (summary, scope, non-goals, proposed "
        "steps, risks, open questions);",
        "  - the redacted output of the verification run that just passed.",
        "NOT transmitted: the full target file, any unrelated repository source, "
        "any directory listing, repository tree or git history, the workspace "
        "absolute path, the verification or git executable path, the approval "
        "text, the raw input artifact, any environment value, the GitHub token, "
        "the endpoint base URL, or the API key.",
        "Redaction was applied to project-controlled text before transmission. "
        "It is a best-effort backstop, NOT a guarantee that the material is "
        "secret-free.",
        "AIDO will issue at most TWO semantic requests to this same model, "
        "exactly one HTTP/model request each, each waited on to AIDO's own "
        "monotonic deadline. A stalled request is terminal and gets no retry. "
        "No fallback reviewer model exists. This bounds AIDO's request issuance "
        "and wait — NOT the request's own lifetime, and NOT backend inference "
        "time.",
        "The reviewer's verdict is advisory: no fixer, re-review of a completed "
        "verdict, patch, file edit, branch, commit, push, or PR follows it.",
        "=" * 74,
    ):
        typer.echo(line, err=True)


def _run_l2_review_approved_file_edit(
    *,
    project_config: Path,
    approved_diff_proposal: Path,
    verify_approved_file_edit_flag: bool,
    real_reviewer: bool,
    read_env=_read_reviewer_env,
    client_factory=_build_real_llm_client,
) -> None:
    """Verify one applied approved change, then review it. Extracted for tests.

    ``read_env`` and ``client_factory`` are injection points: the CLI wrapper
    supplies the real environment reader and the real client builder, while tests
    supply a literal mapping and an ``httpx.MockTransport``-backed client, so the
    test suite never reads a real value or opens a real socket. ``read_env`` is
    called as ``read_env(provider)``.

    Ordering is the safety property, and the credential ordering in particular is
    load-bearing. In sequence: both ``--verify-approved-file-edit`` and
    ``--real-reviewer`` must be present — with **no file read at all** if either
    is missing — then the project config loads, then ``controlled_review`` must
    authorize a reviewer (enabled, supported provider, exact non-blank model),
    then ``controlled_verification`` must be enabled and the platform must be
    Windows, then a string/path check rejects an ``--approved-diff-proposal``
    inside the configured workspace *before* it is opened, then the artifact is
    read and strictly parsed, then the **accepted Phase 5F2D verifier runs**, and
    only after it returns ``verified`` is ``read_env`` called — **once**, with the
    configured provider — and a client built.

    No reviewer credential is read on behalf of a run whose verification refused,
    failed, or left the workspace untrusted — for either provider. And on a run
    that *does* reach the reader, only the **configured** provider's names are
    read: the other family is never looked up at all, rather than looked up and
    discarded (Phase 5F2E-V1-FU1).

    Phase 5F2E-V1 changed nothing about that ordering. It widened one step: the
    gate now accepts ``provider: "litellm"`` or ``provider: "vllm"``, still
    exactly and case-sensitively, and an unsupported provider still refuses here
    before any workspace access, process launch, environment read, or model
    contact. There is no new flag and no new command; provider selection is
    project-config only and the endpoint is environment-only.
    """
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.file_editing import (
        FileEditingApprovalError,
        parse_approved_diff_proposal_artifact,
    )
    from ai_dev_orchestrator.review import (
        ReviewerStageError,
        ReviewRefusedError,
        check_controlled_review_gate,
        run_controlled_review,
    )
    from ai_dev_orchestrator.verification import VerificationRefusedError

    # 1. Explicit confirmation that the project's own verification process may be
    #    executed. This command runs it internally, so it demands the same
    #    consent the standalone verifier does.
    if not verify_approved_file_edit_flag:
        typer.echo(
            "Error: l2-review-approved-file-edit runs the project's own "
            "configured verification process — repository-controlled code, in a "
            "process AIDO does not sandbox — before it contacts a reviewer, and "
            "requires the explicit --verify-approved-file-edit flag. Nothing was "
            "read, nothing was executed, and no model was contacted.",
            err=True,
        )
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)

    # 2. Explicit confirmation that source-derived code may leave the machine. A
    #    second, separate consent: agreeing to run the tests is not agreeing to
    #    send the diff to a model.
    if not real_reviewer:
        typer.echo(
            "Error: l2-review-approved-file-edit transmits SOURCE-DERIVED CODE — "
            "the approved unified diff, selected plan prose, and redacted "
            "verification output — to a REAL reviewer model, and requires the "
            "explicit --real-reviewer flag. Nothing was read, nothing was "
            "executed, and no model was contacted.",
            err=True,
        )
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)

    # 3. Project config: the first file read.
    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The approved diff proposal artifact was not read, nothing was "
            "executed, and no model was contacted.",
            err=True,
        )
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)

    # 4. Reviewer authority, from trusted project config only. Checked before the
    #    artifact is opened and long before repository-controlled code could run
    #    on behalf of a project that may never be reviewed. `real_model_planning`
    #    is not consulted: planning authorization is not review authorization.
    try:
        check_controlled_review_gate(project)
    except ReviewRefusedError as exc:
        typer.echo(f"Error: {exc}", err=True)
        typer.echo(
            "The approved diff proposal artifact was not read, no target "
            "workspace was touched, no process was launched, no environment "
            "value was read, and no model was contacted.",
            err=True,
        )
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)

    # 5. The verification opt-in. The verifier re-checks this itself; it is
    #    checked here too so a project that cannot verify fails before its
    #    artifact is opened.
    if not project.controlled_verification.enabled:
        typer.echo(
            "Error: this project's controlled_verification block is absent or "
            "disabled. Phase 5F2E verifies before it reviews, so a project that "
            "cannot run its own verification cannot be reviewed here.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read, no process was "
            "launched, and no model was contacted.",
            err=True,
        )
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)

    # 6. Platform. This phase reviews a Phase 5F2C write, and that writer is
    #    explicitly Windows-only.
    if sys.platform != "win32":
        typer.echo(
            "Error: Phase 5F2E reviews a Phase 5F2C write verified by Phase "
            "5F2D, and that writer is Windows-only. It refuses on this platform "
            "rather than reasoning about semantics it has not established here.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read, no process was "
            "launched, and no model was contacted.",
            err=True,
        )
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)

    # 7. Refuse an artifact that lives inside the configured target workspace,
    #    BEFORE it is read or stat'd — the same lexical guard every earlier phase
    #    uses, and the reason --approved-diff-proposal carries no Typer exists=
    #    check.
    if _is_same_or_under(approved_diff_proposal, project.repo.workspace_path):
        typer.echo(
            "Error: --approved-diff-proposal is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). The approval "
            "must live outside the workspace it refers to; move the artifact and "
            "retry.",
            err=True,
        )
        typer.echo(
            "The approved diff proposal artifact was not read, nothing was "
            "executed, and no model was contacted.",
            err=True,
        )
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)

    # 8. The artifact: the second and final file read by this command.
    try:
        artifact_text = approved_diff_proposal.read_text(encoding="utf-8")
    except OSError as exc:
        typer.echo(
            f"Error: could not read --approved-diff-proposal: {exc}", err=True
        )
        typer.echo("Nothing was executed and no model was contacted.", err=True)
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)

    # 9. Parse strictly. Rejected, never repaired.
    try:
        artifact = parse_approved_diff_proposal_artifact(artifact_text)
    except FileEditingApprovalError as exc:
        name = type(exc).__name__
        category = _APPROVED_DIFF_FAILURE_CATEGORIES.get(name, "artifact failure")
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        typer.echo(
            "The artifact text, the approval text, and the diffs are not "
            "echoed. Nothing was executed, no target workspace was touched, and "
            "no model was contacted.",
            err=True,
        )
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)

    # 10. Verify first, review second. The composition lives in the review
    #     package; the accepted Phase 5F2D verifier is CALLED there, not copied,
    #     and `read_env` is invoked only after it returns `verified`.
    try:
        outcome = run_controlled_review(
            approved_diff=artifact,
            project=project,
            read_env=read_env,
            client_factory=client_factory,
            on_before_model_call=_echo_reviewer_banner,
            on_supervision_event=_echo_supervision_event,
        )
    except VerificationRefusedError as exc:
        typer.echo(f"Error: refused-before-execution: {exc}", err=True)
        typer.echo(
            "No verification process was started, no reviewer environment value "
            "was read, and no model was contacted. No source, diff, approval "
            "text, absolute path, or environment value is echoed.",
            err=True,
        )
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)
    except ReviewRefusedError as exc:  # pragma: no cover - gate ran at step 4
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=_REVIEW_EXIT_REFUSED)
    except ReviewerStageError as exc:
        name = type(exc).__name__
        category = _REVIEWER_FAILURE_CATEGORIES.get(name, "reviewer failure")
        typer.echo(
            "=== REAL REVIEWER MODEL CALL FAILED (verification had already "
            "passed) ===",
            err=True,
        )
        typer.echo(f"Error: {name}: {category}. {exc}", err=True)
        # Every claim below is scoped, because by this point the unsandboxed
        # Phase 5F2D verification child has already run. An unscoped "no file was
        # written / no Git state was changed / no push happened" would be a claim
        # about the whole invocation, and this command cannot make it: the child
        # may have written Git-ignored files, written outside the repository,
        # reached the network, pushed, created a ref that leaves HEAD and the
        # worktree untouched, or left descendants running. Phase 5F2D
        # deliberately does not observe those effects, and Phase 5F2E adds no
        # detection for them.
        for line in (
            "The raw model response is not echoed, and no API key, base URL, "
            "prompt, or approved diff appears in this message.",
            # "Retried nothing" would no longer be true when the project enabled
            # the Phase 5F2E-RS1 compact retry, so the claim is stated as the
            # bound that actually holds: at most two semantic attempts, each one
            # HTTP/model request, with no repair of a rejected reply. The exact
            # number used for this run is in the REVIEWER UNAVAILABLE block above.
            "AIDO's review stage: repaired nothing, restored nothing, wrote no "
            "file into the target workspace, performed no Git mutation, and "
            "created no branch, commit, push or PR.",
            "AIDO issued at most two semantic requests to the same configured "
            "model, exactly one HTTP/model request each (reviewer transport "
            "retries are forced to zero), with no request after a timeout, no "
            "third request, no fallback reviewer model, and no parser repair or "
            "merging of a rejected reply. That bounds AIDO's request issuance "
            "and wait, not backend inference time.",
            "The workspace state that IS established comes from the "
            "verification that had already passed: the approved target's exact "
            "bytes, a HEAD object id equal to the one the run started from, and "
            "a Git-visible dirty state of exactly that one unstaged path.",
            "Beyond that boundary nothing is claimed. The verification child was "
            "NOT sandboxed, and effects outside Phase 5F2D's documented "
            "detection boundary — Git-ignored files, anything outside this "
            "repository, network activity, remote operations such as a push, "
            "additional refs that leave HEAD and the worktree unchanged, and "
            "descendants still running — are not observed by AIDO.",
            "Correct the reviewer configuration and run this command again.",
        ):
            typer.echo(line, err=True)
        raise typer.Exit(code=_REVIEW_EXIT_REVIEWER_FAILED)

    # 11. Verification ran but did not produce a reviewable state. The Phase
    #     5F2D report is printed as-is and its exit semantics are preserved
    #     exactly; no model was contacted and no reviewer environment value was
    #     read.
    if outcome.packet is None:
        report = outcome.verification
        _echo_json_model(report)
        if report.outcome == "workspace-state-untrusted":
            typer.echo(
                "Error: workspace-state-untrusted: the verification process ran, "
                "and afterwards the repository is NOT provably the approved "
                "state. No reviewer was contacted and no reviewer environment "
                "value was read. AIDO repaired nothing, restored nothing, and "
                "retried nothing. The verification child was NOT sandboxed. "
                "HUMAN REPOSITORY INSPECTION IS REQUIRED.",
                err=True,
            )
            raise typer.Exit(code=_REVIEW_EXIT_WORKSPACE_UNTRUSTED)
        # Scoped for the same reason exit 4 is: the unsandboxed Phase 5F2D child
        # has already run by now, so "nothing was committed" would be a claim
        # about the whole invocation rather than about AIDO.
        for line in (
            "Verification did not pass, so no reviewer was contacted and no "
            "reviewer environment value was read.",
            "The report above is what establishes the workspace state: the "
            "approved target's exact bytes, a HEAD object id equal to the one "
            "the run started from, and the expected Git-visible dirty state.",
            "AIDO performed no retry, no repair, no restore, and no "
            "reviewer-stage action.",
            "The verification child was NOT sandboxed, and effects outside "
            "Phase 5F2D's documented detection boundary are not claimed here.",
        ):
            typer.echo(line, err=True)
        raise typer.Exit(code=_REVIEW_EXIT_VERIFICATION_NOT_PASSED)

    # 12. A structured reviewer result. Exit 0 for every verdict — a change
    #     request is a successful review, not an AIDO error — and the packet
    #     itself is stdout, with no wrapper.
    packet = outcome.packet
    typer.echo(
        "=== REAL REVIEWER MODEL CALL COMPLETED ===",
        err=True,
    )
    typer.echo(f"Provider:      {packet.reviewer.provider}", err=True)
    typer.echo(f"Endpoint host: {packet.reviewer.endpoint_host}", err=True)
    typer.echo(
        "Transport:     "
        + (
            f"{packet.reviewer.endpoint_scheme.upper()} — TLS-encrypted"
            if packet.reviewer.transport_tls
            else f"{packet.reviewer.endpoint_scheme.upper()} — NOT TLS-ENCRYPTED"
        ),
        err=True,
    )
    typer.echo(f"Model:         {packet.reviewer.model}", err=True)
    typer.echo(f"Verdict:       {packet.review.verdict}", err=True)
    typer.echo(
        f"Requests:      {packet.reviewer.semantic_requests} of at most "
        f"{packet.reviewer.max_semantic_requests} semantic requests AIDO may "
        "issue (one HTTP/model request each)",
        err=True,
    )
    typer.echo(
        "The verdict is advisory and ends here: a human decides what happens "
        "next. No fixer, re-review of this verdict, patch, file edit, branch, "
        "commit, push, or PR followed it.",
        err=True,
    )
    _echo_json_model(packet)


@app.command("l2-review-approved-file-edit")
def l2_review_approved_file_edit(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the project config YAML the approved diff must match. Its "
        "controlled_verification block must be enabled, and its "
        "controlled_review block must be enabled and name the exact reviewer "
        "model.",
    ),
    approved_diff_proposal: Path = typer.Option(
        ...,
        "--approved-diff-proposal",
        # Deliberately no exists=/readable= check: Typer would stat the path
        # before the command body could reject one inside the configured
        # workspace. The guard runs first; the file is opened only afterwards.
        help="Path to the human-approved diff proposal artifact "
        "(approved-diff-proposal.v2) whose modification has already been "
        "applied. Must not be inside the project's configured workspace path.",
    ),
    verify_approved_file_edit_flag: bool = typer.Option(
        False,
        "--verify-approved-file-edit",
        help="Required explicit confirmation that the project's own configured "
        "verification process may be executed. Without it this command fails "
        "without reading anything.",
    ),
    real_reviewer: bool = typer.Option(
        False,
        "--real-reviewer",
        help="Required explicit confirmation that source-derived code may be "
        "sent to a REAL reviewer model. Without it this command fails without "
        "reading anything.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Verify ONE applied approved edit, then have ONE reviewer model review it.

    **This is the first command that deliberately sends source-derived code to a
    model.** Every earlier model-facing command transmitted issue text; this one
    transmits a unified diff of the project's own source, selected approved-plan
    prose, and the redacted output of a verification run.

    It does **not** run the writer. It starts from the exact state
    ``l2-apply-approved-file-edit`` leaves behind and runs the **existing** Phase
    5F2D verification internally, so a verification result is never an input:
    there is no ``--verification-result`` option, and no saved report is trusted
    as authority. That keeps the verification fresh for the review it informs,
    keeps reviewer credentials out of the process while unsandboxed
    repository-controlled code runs, and makes the whole command re-runnable if
    the reviewer configuration turns out to be wrong.

    The reviewer model comes only from the project config's ``controlled_review``
    block. There is no ``--model``, ``--provider``, ``--prompt``, ``--message``,
    ``--command``, ``--shell``, ``--fix``, ``--repair``, ``--retry``,
    ``--commit``, ``--branch``, ``--push``, ``--pr``, ``--github``, ``--fetch``,
    or ``--apply`` option, and no environment variable of either provider ever
    selects the reviewer model.

    The reviewer **backend** likewise comes only from
    ``controlled_review.provider``, which is exactly ``"litellm"`` (the existing
    internal OpenAI-compatible LiteLLM path, connection details from the
    ``AIDO_LITELLM_*`` names) or ``"vllm"`` (a direct OpenAI-compatible vLLM
    endpoint, connection details from ``AIDO_VLLM_BASE_URL`` and the optional
    ``AIDO_VLLM_API_KEY``). Matching is exact and case-sensitive. A direct vLLM
    endpoint reached over plaintext ``http`` is refused before any model request
    unless the project set ``controlled_review.vllm_allow_insecure_http`` — an
    acknowledgement that unencrypted transport is accepted, **not** a claim that
    it is secure, private, or authenticated.

    What is transmitted: the one approved unified diff, the plan's summary, scope
    summary, non-goals, proposed steps, risks and open questions, and the
    verification outcome plus its bounded, redacted output. What is never
    transmitted: the full target file, any unrelated source, any directory
    listing, repository tree or git history, the configured workspace path, any
    absolute path, the approval text, the raw artifact, any environment value,
    the GitHub token, the endpoint base URL, or the API key. Project-controlled
    text is redacted before transmission — a best-effort backstop, not a
    guarantee — and is delimited as untrusted data that the reviewer is
    instructed to inspect, never to obey.

    The reviewer's reply must be exactly one strict JSON object matching the
    review schema. It is **rejected rather than repaired**: no parser repair, no
    "fix your JSON" round trip, and no merging of two replies.

    Reviewer request issuance is **supervised and bounded** (Phase 5F2E-RS1). The
    reviewer client is built with ``max_retries=0`` — overriding
    ``AIDO_LITELLM_MAX_RETRIES`` for this command only — so one semantic attempt
    is exactly one HTTP/model request. AIDO issues at most **two** semantic
    requests: the second exists only when the project set
    ``controlled_review.compact_retry_on_unusable_output`` **and** the first
    response was *completed but unusable* — the provider reported an output
    length limit, or the strict parser rejected it. A **timeout is terminal**: AIDO stops waiting
    but cannot observe whether the backend released its inference slot, so it
    never issues a second request that could run concurrently with the first. The
    retry uses the **same** configured model with a reduced context; there is no
    third request and no fallback reviewer.

    ``controlled_review.attempt_timeout_seconds`` bounds AIDO's *wait* on each
    request, established by AIDO's **own** monotonic deadline in the supervisor
    rather than by httpx timeout semantics (a network-inactivity timeout a busy
    peer can outlive). When that deadline wins, the worker performing the call is
    **abandoned, not stopped** — AIDO never claims the request was cancelled or
    that a backend stopped inference.

    ``controlled_review.max_output_tokens`` is **optional, and unset by
    default**: AIDO then imposes no output-token ceiling and sends no
    ``max_tokens`` field at all, so ``requested_max_output_tokens`` is recorded
    as ``null``. Setting it to a positive integer sends exactly that value on
    both possible attempts — still a *request*, never a guarantee. The
    provider/model/backend keeps its own native output and context limits in both
    cases, so a provider may report a length finish condition even when AIDO
    requested no cap; that is the backend's own limit, and AIDO does not claim to
    know which one. This bounds AIDO's request issuance and wait budget only; the abandoned worker's lifetime, backend inference
    lifetime and GPU occupancy after a stall are **not** bounded here.

    Exit codes are distinct on purpose. **1** refused before any process started.
    **2** verification ran and did not pass — no model was contacted. **3**
    verification ran and the repository is no longer provably the approved state
    — no model was contacted. **4** verification passed but the reviewer stage
    failed — AIDO's review stage wrote nothing, mutated no Git state and created
    no branch/commit/push/PR, the passed verification had established the
    approved bytes, an unchanged HEAD and the expected single dirty path, and
    nothing is claimed beyond Phase 5F2D's documented detection boundary; the
    command may be re-run. **0**
    the reviewer produced a valid result — for ``approve``,
    ``changes_requested`` *and* ``needs_human_review`` alike, because all three
    are successful reviews.

    A verdict is advisory and terminal: there is no fixer, no second reviewer, no
    retry after findings, no patch generation, no file edit, no revert or
    restore, no branch, no commit, no push, and no PR. The human decides.
    """
    _run_l2_review_approved_file_edit(
        project_config=project_config,
        approved_diff_proposal=approved_diff_proposal,
        verify_approved_file_edit_flag=verify_approved_file_edit_flag,
        real_reviewer=real_reviewer,
        read_env=_read_reviewer_env,
        client_factory=_build_real_llm_client,
    )


if __name__ == "__main__":
    app()
