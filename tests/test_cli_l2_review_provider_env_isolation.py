"""Phase 5F2E-V1-FU1: the reviewer reads ONLY the configured provider's names.

Phase 5F2E-V1 shipped a reviewer environment reader that snapshotted **both**
provider families from ``os.environ`` and narrowed the result afterwards. The
documented contract said a vLLM review reads no ``AIDO_LITELLM_*`` value and a
LiteLLM review reads no ``AIDO_VLLM_*`` value — and that was not true. Reading a
credential and then discarding it is still reading it.

These tests exist to make that impossible to reintroduce, so they are deliberately
written to **fail against the old implementation**. They do not pass a pre-built
mapping and then check the filtering; they replace the process environment with a
tracking mapping and assert on which names the **real CLI reader** actually looked
up. A union snapshot touches all seven names and fails here immediately.

Four properties are proved:

1. a ``vllm`` review looks up only ``AIDO_VLLM_BASE_URL`` and
   ``AIDO_VLLM_API_KEY``;
2. a ``litellm`` review looks up only the five ``AIDO_LITELLM_*`` names;
3. a run whose verification did not return ``verified`` looks up **neither**
   family — the accepted verify-first / credential-second ordering is unchanged;
4. a refused run (disabled review, unsupported provider, missing action flag)
   looks up neither family either, and the reader is called exactly once on a run
   that does reach it.

**Every repository here is a synthetic Git repository created under pytest's own
``tmp_path``, and every verification program is a small synthetic Python script
written under ``tmp_path``.** No real target project is used, read, written, or
executed. **Every reviewer call goes through ``httpx.MockTransport``**: no socket
is opened, no real endpoint is contacted, and no API key is needed. The tracking
environment is seeded from a copy of the real one so the verification child still
gets its minimal inherited names, but **no real value is ever asserted on or
printed**.
"""

from __future__ import annotations

import json
import os

import pytest

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.review import (
    LITELLM_REVIEWER_ENV_NAMES,
    VLLM_ENV_API_KEY,
    VLLM_ENV_BASE_URL,
    VLLM_REVIEWER_ENV_NAMES,
)
from test_cli_l2_review_approved_file_edit import (
    DIRTYING_BODY,
    ENABLED_REVIEW_BLOCK,
    FAILING_BODY,
    _run,
    _setup,
    git_required,
    windows_only,
)
from test_cli_l2_review_vllm_provider import (
    VLLM_HTTPS_BASE_URL,
    VLLM_REVIEWER_MODEL,
    _recording_factory,
    _vllm_block,
)

# The seven names this suite watches. Any access to one of them is recorded, and
# any access to a *forbidden* one aborts the run loudly rather than being noted
# and forgiven.
WATCHED: tuple[str, ...] = LITELLM_REVIEWER_ENV_NAMES + VLLM_REVIEWER_ENV_NAMES

# Synthetic values, seeded into the tracking environment so a "successful" path
# has something to find. None of them is real.
FAKE_LITELLM_VALUES = {
    "AIDO_LITELLM_BASE_URL": "http://fake-litellm.invalid/v1",
    "AIDO_LITELLM_API_KEY": "fake-key-not-a-real-secret",
    "AIDO_LITELLM_DEFAULT_MODEL": "fake-env-default-model",
    "AIDO_LITELLM_TIMEOUT_SECONDS": "5",
    "AIDO_LITELLM_MAX_RETRIES": "0",
}
FAKE_VLLM_VALUES = {
    VLLM_ENV_BASE_URL: VLLM_HTTPS_BASE_URL,
    VLLM_ENV_API_KEY: "fake-vllm-key-not-a-real-secret",
}


class _TrackingEnviron(dict):
    """A ``dict`` that records — and can refuse — lookups of watched names.

    Seeded from a copy of the real environment so everything unrelated (the
    verification child's minimal inherited names, for instance) still resolves
    normally. Only the seven reviewer names are watched, and only synthetic
    values are ever added.

    ``__getitem__``, ``__contains__`` and ``get`` are all instrumented, because a
    reader can probe a variable through any of them and "did it read this name?"
    must not depend on which one it chose.
    """

    def __init__(self, extra: dict[str, str], forbidden: set[str]) -> None:
        base = dict(os.environ)
        # Watched names start absent, so nothing about the developer's real
        # machine can influence an assertion here.
        for name in WATCHED:
            base.pop(name, None)
        base.update(extra)
        super().__init__(base)
        self.seen: list[str] = []
        self._forbidden = set(forbidden)

    def _note(self, key: object) -> None:
        if key in WATCHED:
            if key in self._forbidden:
                raise AssertionError(
                    f"the reviewer read {key!r} from the process environment, "
                    "but the configured provider does not use that name. A "
                    "union snapshot that discards the other provider's values "
                    "afterwards is still reading them."
                )
            self.seen.append(str(key))

    def __getitem__(self, key):  # type: ignore[no-untyped-def]
        self._note(key)
        return super().__getitem__(key)

    def __contains__(self, key) -> bool:  # type: ignore[no-untyped-def]
        self._note(key)
        return super().__contains__(key)

    def get(self, key, default=None):  # type: ignore[no-untyped-def]
        self._note(key)
        return super().get(key, default)


def _install(monkeypatch, *, extra: dict[str, str], forbidden) -> _TrackingEnviron:
    tracking = _TrackingEnviron(extra, set(forbidden))
    monkeypatch.setattr(os, "environ", tracking)
    return tracking


def _spy(calls: list[str]):
    """Delegate to the REAL CLI reader, recording the provider it was given."""

    def read_env(provider: str):
        calls.append(provider)
        return cli._read_reviewer_env(provider)

    return read_env


# =============================================================================
# 1. The reader itself, in isolation
# =============================================================================


def test_the_real_reader_reads_only_the_vllm_names(monkeypatch):
    """Blocker 1, at the reader. Touching any AIDO_LITELLM_* name fails loudly."""
    tracking = _install(
        monkeypatch,
        extra={**FAKE_LITELLM_VALUES, **FAKE_VLLM_VALUES},
        forbidden=set(LITELLM_REVIEWER_ENV_NAMES),
    )

    result = cli._read_reviewer_env("vllm")

    assert set(result) == set(VLLM_REVIEWER_ENV_NAMES)
    assert set(tracking.seen) <= set(VLLM_REVIEWER_ENV_NAMES)
    assert not set(tracking.seen) & set(LITELLM_REVIEWER_ENV_NAMES)


def test_the_real_reader_reads_only_the_litellm_names(monkeypatch):
    """The mirror image. Touching any AIDO_VLLM_* name fails loudly."""
    tracking = _install(
        monkeypatch,
        extra={**FAKE_LITELLM_VALUES, **FAKE_VLLM_VALUES},
        forbidden=set(VLLM_REVIEWER_ENV_NAMES),
    )

    result = cli._read_reviewer_env("litellm")

    assert set(result) == set(LITELLM_REVIEWER_ENV_NAMES)
    assert set(tracking.seen) <= set(LITELLM_REVIEWER_ENV_NAMES)
    assert not set(tracking.seen) & set(VLLM_REVIEWER_ENV_NAMES)


def test_an_unsupported_provider_reads_no_environment_name_at_all(monkeypatch):
    """The provider is resolved to names first, so a bad one never gets that far."""
    tracking = _install(
        monkeypatch,
        extra={**FAKE_LITELLM_VALUES, **FAKE_VLLM_VALUES},
        forbidden=set(WATCHED),
    )

    for provider in ("openai", "openai_compatible", "VLLM", "vllm ", ""):
        with pytest.raises(Exception) as excinfo:
            cli._read_reviewer_env(provider)
        assert "no reviewer environment contract" in str(excinfo.value)

    assert tracking.seen == []


def test_a_missing_optional_vllm_key_is_simply_absent(monkeypatch):
    """Absent names are not invented, and no other family is consulted."""
    tracking = _install(
        monkeypatch,
        extra={VLLM_ENV_BASE_URL: VLLM_HTTPS_BASE_URL},
        forbidden=set(LITELLM_REVIEWER_ENV_NAMES),
    )

    result = cli._read_reviewer_env("vllm")

    assert set(result) == {VLLM_ENV_BASE_URL}
    assert not set(tracking.seen) & set(LITELLM_REVIEWER_ENV_NAMES)


# =============================================================================
# 2. End to end, through the real command
# =============================================================================


@windows_only
@git_required
def test_a_vllm_review_never_reads_a_litellm_variable_end_to_end(tmp_path, monkeypatch):
    """Blocker 1, through the whole command, with the REAL wired-in reader.

    ``read_env`` is deliberately **not** injected, so the default the CLI wires up
    is what runs. Under Phase 5F2E-V1 this test aborted inside the reader.
    """
    _, config, artifact = _setup(tmp_path, review_block=_vllm_block())
    tracking = _install(
        monkeypatch,
        extra={**FAKE_LITELLM_VALUES, **FAKE_VLLM_VALUES},
        forbidden=set(LITELLM_REVIEWER_ENV_NAMES),
    )

    configs: list = []
    seen: list[dict] = []
    code = cli._run_l2_review_approved_file_edit(
        project_config=config,
        approved_diff_proposal=artifact,
        verify_approved_file_edit_flag=True,
        real_reviewer=True,
        client_factory=_recording_factory(configs, seen),
    )

    assert code is None  # exit 0 raises nothing
    assert len(seen) == 1
    # Only vLLM names were looked up, and both of them were.
    assert set(tracking.seen) == set(VLLM_REVIEWER_ENV_NAMES)
    assert not set(tracking.seen) & set(LITELLM_REVIEWER_ENV_NAMES)
    # The endpoint really came from the vLLM variable.
    assert configs[0].base_url == VLLM_HTTPS_BASE_URL
    assert configs[0].default_model == VLLM_REVIEWER_MODEL


@windows_only
@git_required
def test_a_litellm_review_never_reads_a_vllm_variable_end_to_end(
    tmp_path, monkeypatch
):
    """The mirror image, also with the real wired-in reader."""
    _, config, artifact = _setup(tmp_path, review_block=ENABLED_REVIEW_BLOCK)
    tracking = _install(
        monkeypatch,
        extra={**FAKE_LITELLM_VALUES, **FAKE_VLLM_VALUES},
        forbidden=set(VLLM_REVIEWER_ENV_NAMES),
    )

    configs: list = []
    seen: list[dict] = []
    code = cli._run_l2_review_approved_file_edit(
        project_config=config,
        approved_diff_proposal=artifact,
        verify_approved_file_edit_flag=True,
        real_reviewer=True,
        client_factory=_recording_factory(configs, seen),
    )

    assert code is None
    assert len(seen) == 1
    assert set(tracking.seen) <= set(LITELLM_REVIEWER_ENV_NAMES)
    assert not set(tracking.seen) & set(VLLM_REVIEWER_ENV_NAMES)
    assert configs[0].base_url == FAKE_LITELLM_VALUES["AIDO_LITELLM_BASE_URL"]


@windows_only
@git_required
@pytest.mark.parametrize(
    ("body", "expected_code"),
    [(FAILING_BODY, 2), (DIRTYING_BODY, 3)],
    ids=["verification-failed", "workspace-untrusted"],
)
@pytest.mark.parametrize(
    "review_block",
    [_vllm_block(), ENABLED_REVIEW_BLOCK],
    ids=["vllm", "litellm"],
)
def test_a_non_verified_outcome_reads_neither_provider_family(
    tmp_path, monkeypatch, body, expected_code, review_block, capsys
):
    """The accepted verify-first / credential-second ordering, still exact.

    Every one of the seven names is forbidden here, so *any* environment access
    by either provider's path aborts the test.
    """
    _, config, artifact = _setup(tmp_path, body=body, review_block=review_block)
    tracking = _install(
        monkeypatch,
        extra={**FAKE_LITELLM_VALUES, **FAKE_VLLM_VALUES},
        forbidden=set(WATCHED),
    )

    calls: list[str] = []
    code = _run(config, artifact, read_env=_spy(calls))

    assert code == expected_code
    assert calls == []
    assert tracking.seen == []
    capsys.readouterr()


@windows_only
@git_required
@pytest.mark.parametrize(
    ("review_block", "verify_flag", "real_reviewer"),
    [
        (_vllm_block(), False, False),
        (_vllm_block(), True, False),
        (ENABLED_REVIEW_BLOCK, False, True),
        (_vllm_block(provider="openai_compatible"), True, True),
        (
            'controlled_review:\n  enabled: false\n  provider: "vllm"\n'
            f'  model: "{VLLM_REVIEWER_MODEL}"\n',
            True,
            True,
        ),
    ],
    ids=[
        "vllm-no-flags",
        "vllm-missing-real-reviewer",
        "litellm-missing-verify",
        "unsupported-provider",
        "review-disabled",
    ],
)
def test_a_refused_run_reads_neither_provider_family(
    tmp_path, monkeypatch, review_block, verify_flag, real_reviewer, capsys
):
    """A refusal must cost nothing — including no environment lookup."""
    _, config, artifact = _setup(tmp_path, review_block=review_block)
    tracking = _install(
        monkeypatch,
        extra={**FAKE_LITELLM_VALUES, **FAKE_VLLM_VALUES},
        forbidden=set(WATCHED),
    )

    calls: list[str] = []
    code = _run(
        config,
        artifact,
        read_env=_spy(calls),
        verify_flag=verify_flag,
        real_reviewer=real_reviewer,
    )

    assert code == 1
    assert calls == []
    assert tracking.seen == []
    capsys.readouterr()


@windows_only
@git_required
@pytest.mark.parametrize(
    ("review_block", "provider"),
    [(_vllm_block(), "vllm"), (ENABLED_REVIEW_BLOCK, "litellm")],
    ids=["vllm", "litellm"],
)
def test_the_reader_runs_exactly_once_with_the_configured_provider(
    tmp_path, monkeypatch, review_block, provider, capsys
):
    """Requirement 5: one call, after ``verified``, naming the configured backend."""
    _, config, artifact = _setup(tmp_path, review_block=review_block)
    _install(
        monkeypatch,
        extra={**FAKE_LITELLM_VALUES, **FAKE_VLLM_VALUES},
        forbidden=set(),
    )

    calls: list[str] = []
    configs: list = []
    seen: list[dict] = []
    code = _run(
        config,
        artifact,
        read_env=_spy(calls),
        client_factory=_recording_factory(configs, seen),
    )

    assert code == 0
    assert calls == [provider]
    capsys.readouterr()


# =============================================================================
# 3. The provider-neutral connection-failure category
# =============================================================================


@windows_only
@git_required
def test_a_missing_vllm_base_url_is_reported_without_blaming_litellm(
    tmp_path, monkeypatch, capsys
):
    """Truthfulness cleanup 2, end to end.

    The failure names the variable the operator must actually set, and never
    claims the ``AIDO_LITELLM_*`` settings were the problem — they are not even
    consulted for a vLLM reviewer.
    """
    _, config, artifact = _setup(tmp_path, review_block=_vllm_block())
    # Every LiteLLM name IS set, and every vLLM name is absent: under a
    # union-snapshot reader this is exactly the case that would have looked
    # healthy for the wrong reason.
    tracking = _install(
        monkeypatch,
        extra=dict(FAKE_LITELLM_VALUES),
        forbidden=set(LITELLM_REVIEWER_ENV_NAMES),
    )

    def forbidden_client(config):
        raise AssertionError("a client was built without a configured endpoint")

    calls: list[str] = []
    code = _run(
        config,
        artifact,
        read_env=_spy(calls),
        client_factory=forbidden_client,
    )

    assert code == 4
    assert calls == ["vllm"]
    assert not set(tracking.seen) & set(LITELLM_REVIEWER_ENV_NAMES)

    err = capsys.readouterr().err
    # It names the variable the operator must set.
    assert VLLM_ENV_BASE_URL in err
    # Provider-neutral category wording — no false LiteLLM blame.
    assert "reviewer connection configuration failure" in err
    assert "the AIDO_LITELLM_* connection settings" not in err
    # No endpoint, credential, or model value is echoed. (The two numeric
    # LiteLLM tuning values are excluded: "5" and "0" are not distinctive enough
    # to assert on against ordinary English prose.)
    for value in (
        FAKE_LITELLM_VALUES["AIDO_LITELLM_BASE_URL"],
        FAKE_LITELLM_VALUES["AIDO_LITELLM_API_KEY"],
        FAKE_LITELLM_VALUES["AIDO_LITELLM_DEFAULT_MODEL"],
        FAKE_VLLM_VALUES[VLLM_ENV_BASE_URL],
        FAKE_VLLM_VALUES[VLLM_ENV_API_KEY],
    ):
        assert value not in err


def test_the_reviewer_environment_failure_category_is_provider_neutral():
    """The fixed string itself: no family named, and no value interpolated."""
    category = cli._REVIEWER_FAILURE_CATEGORIES["ReviewerEnvironmentError"]

    assert category == (
        "reviewer connection configuration failure — the configured reviewer "
        "connection settings were missing, invalid, or disallowed"
    )
    assert "LITELLM" not in category.upper()
    assert "VLLM" not in category.upper()
    for token in ("http://", "https://", "sk-", "Bearer"):
        assert token not in category


@windows_only
@git_required
def test_an_unauthorized_http_vllm_endpoint_uses_the_same_neutral_category(
    tmp_path, monkeypatch, capsys
):
    """"disallowed" is in the wording because this case is not "missing/invalid"."""
    _, config, artifact = _setup(tmp_path, review_block=_vllm_block())
    _install(
        monkeypatch,
        extra={VLLM_ENV_BASE_URL: "http://fake-vllm.invalid:8000/v1"},
        forbidden=set(LITELLM_REVIEWER_ENV_NAMES),
    )

    def forbidden_client(config):
        raise AssertionError("a client was built for a refused transport")

    code = _run(
        config,
        artifact,
        read_env=_spy([]),
        client_factory=forbidden_client,
    )

    assert code == 4
    err = capsys.readouterr().err
    assert "reviewer connection configuration failure" in err
    assert "PLAINTEXT HTTP" in err
    assert "the AIDO_LITELLM_* connection settings" not in err
    assert "http://fake-vllm.invalid:8000/v1" not in err


# =============================================================================
# 4. There is no union read authority left to regress to
# =============================================================================


def test_no_union_environment_name_constant_is_exported():
    """The union constant was the defect's enabler; it is gone, not renamed."""
    import ai_dev_orchestrator.review as review_package
    import ai_dev_orchestrator.review.reviewer as reviewer_module

    assert "REVIEWER_ENV_NAMES" not in review_package.__all__
    assert not hasattr(review_package, "REVIEWER_ENV_NAMES")
    assert not hasattr(reviewer_module, "REVIEWER_ENV_NAMES")
    # The old narrow-afterwards helper is gone too, not left as a decoy.
    assert not hasattr(review_package, "select_reviewer_env")
    assert not hasattr(reviewer_module, "select_reviewer_env")


def test_the_cli_reader_requires_a_provider_argument():
    """A zero-argument reader is exactly the shape that could not be correct."""
    import inspect

    signature = inspect.signature(cli._read_reviewer_env)

    assert list(signature.parameters) == ["provider"]
    with pytest.raises(TypeError):
        cli._read_reviewer_env()  # type: ignore[call-arg]


def test_the_planner_and_smoke_test_reader_is_untouched():
    """FU1 narrowed the reviewer's reader only; the Phase 3B/4J one is unchanged."""
    import inspect

    assert list(inspect.signature(cli._read_real_llm_env).parameters) == []
    source = inspect.getsource(cli._read_real_llm_env)
    assert "AIDO_VLLM" not in source


def test_no_reviewer_test_here_touches_a_real_endpoint_or_socket():
    """Belt and braces: every value in this module is synthetic."""
    for value in {**FAKE_LITELLM_VALUES, **FAKE_VLLM_VALUES}.values():
        assert ".invalid" in value or not value.startswith("http")
    assert json.dumps(FAKE_VLLM_VALUES).count(".invalid") == 1
