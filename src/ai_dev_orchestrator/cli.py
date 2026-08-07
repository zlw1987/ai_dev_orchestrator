"""Command-line interface for the AI Dev Orchestrator.

Commands: a `version` command, `inspect-issue` (read-only GitHub issue
inspection), `llm-smoke-test` (a fake-provider dry-run of the Phase 3C LLM
client — no real model call), `generate-plan` (an offline fake/deterministic L1
plan generator — Phase 4D, no GitHub fetch, no model call), and the **two**
commands that may open a real socket, each only after every gate precondition
passes: `real-llm-smoke-test` (Phase 4K) and `generate-model-plan` (Phase 4L).

`real-llm-smoke-test` is a **connectivity check, not a planner**: it sends a
fixed, harmless prompt, never issue text, and produces no plan.
`generate-model-plan` is the planner: it transmits the issue title and the body
text of the local file explicitly named on the command line, and nothing else —
no source files, no workspace contents, no directory listings, no git history.
Both require an explicit `--real-model` flag plus a project config that opts in
and allowlists the model.

Every other command remains offline. No GitHub fetch happens in either gated
command, and no agent logic, role wiring, file editing, command execution, or
GitHub writes are wired up anywhere.
"""

from __future__ import annotations

import enum
import json
import os
from pathlib import Path

import typer

from ai_dev_orchestrator import __version__

app = typer.Typer(
    name="ai-dev-orchestrator",
    help="Controlled AI software development pipeline orchestrator.",
    no_args_is_help=True,
    add_completion=False,
)


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
_REAL_SMOKE_MAX_TOKENS = 32

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

    **This is the only command that can contact a real model.** It requires the
    explicit ``--real-model`` flag *and* a project config whose
    ``real_model_planning`` block enables real model use and allowlists
    ``--model``; either alone is not enough, and every precondition is checked
    before the environment is read or a client is built.

    It is a **connectivity check, not a planner**: it sends a fixed, harmless
    prompt and never issue text, never file or workspace contents, and never
    project data. It fetches nothing from GitHub, writes nothing to GitHub,
    generates no plan, edits no file, runs no command, and writes no audit file.

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


if __name__ == "__main__":
    app()
