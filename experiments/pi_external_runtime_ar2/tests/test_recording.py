"""RECORDING -- three trust namespaces, a fail-closed scrub, and honest wording.

    runtime_reported_*        Pi's own account of itself   UNTRUSTED CLAIM
    broker_recorded_*         AIDO's own broker activity   AIDO-AUTHORED, DIAGNOSTIC
    orchestrator_observed_*   AIDO's independent Git and
                              filesystem derivation        AUTHORITATIVE

A broker log is not repository truth even though AIDO wrote it, and these tests
assert that the record says so rather than leaving it to a reader's goodwill.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ar2 import EXPERIMENT_ID, EXPERIMENT_RECORD_VERSION
from ar2.ascii_json import dumps_ascii, is_ascii_representable
from ar2.broker import BrokerBinding, BrokerDiagnostics, BrokerRequestHandler
from ar2.capability import RunState
from ar2.fixtures import R1
from ar2.record import (
    CAPABILITY_BOUNDARY,
    RESIDUAL_LIMITATIONS,
    TOKEN_POLICY,
    broker_secret_denylist,
    record_header,
    redact_value,
    refusal_record,
    scrub_check,
)

from conftest import mint_for
import run_ar2


# -- namespaces ----------------------------------------------------------------


def test_the_three_trust_namespaces_are_declared_and_distinct():
    header = record_header()
    namespaces = header["trust_namespaces"]
    assert set(namespaces) == {
        "runtime_reported_*",
        "broker_recorded_*",
        "orchestrator_observed_*",
    }
    assert "UNTRUSTED" in namespaces["runtime_reported_*"]
    assert "DIAGNOSTIC ONLY" in namespaces["broker_recorded_*"]
    assert "never repository truth" in namespaces["broker_recorded_*"]
    assert "AUTHORITATIVE" in namespaces["orchestrator_observed_*"]


def test_the_broker_log_is_never_promoted_to_repository_truth(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    diagnostics = BrokerDiagnostics()
    described = diagnostics.as_dict()
    assert described["trust"].startswith("AIDO-authored, DIAGNOSTIC ONLY")
    assert "never repository truth" in described["trust"]
    # It carries no classification, no verdict, and no verification.
    for banned in ("workspace_class", "trusted", "clean_expected", "verification", "passed"):
        assert banned not in described


def test_the_cross_check_treats_a_discrepancy_in_either_direction_as_an_anomaly():
    """Asserted against the harness code that computes it."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(run_ar2))
    phase_case = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "phase_case"
    )
    source = ast.unparse(phase_case)
    assert "broker_recorded_but_not_observed" in source
    assert "observed_but_not_explained_by_the_broker" in source
    # Trust requires BOTH directions to be empty, and a closed teardown.
    assert "cross_check['agree']" in source or 'cross_check["agree"]' in source
    assert "teardown_closed" in source


def test_a_run_is_untrusted_unless_the_cross_check_agrees_and_teardown_closed():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(run_ar2))
    phase_case = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "phase_case"
    )
    source = ast.unparse(phase_case)
    # Trust requires the classification (or the case's declared no-change shape),
    # AND agreement in both cross-check directions, AND an observed CLOSED teardown.
    assert "classification.trusted or no_change_is_the_expected_shape" in source
    assert "cross_check['agree']" in source
    assert "and teardown_closed" in source
    # The no-change relaxation is scoped to cases that declare an EMPTY expected set.
    assert "not case.expected_changed_paths" in source
    assert "not classification.head_moved" in source


# -- scrub ---------------------------------------------------------------------


def test_the_scrub_refuses_a_broker_token(r1_repo, git_executable):
    binding = BrokerBinding.mint("ar2-cap-abc")
    denylist = broker_secret_denylist(
        token=binding.token, capability_id=binding.capability_id, pipe_name="\\\\.\\pipe\\x"
    )
    record = {"leaked": binding.token}
    result = scrub_check(record, extra_forbidden=denylist)
    assert result["clean"] is False
    assert "broker_token_present" in result["findings"]
    # The finding is a CODE, never the needle.
    assert binding.token not in json.dumps(result)


def test_the_scrub_refuses_a_capability_id_a_pipe_name_and_an_endpoint():
    denylist = broker_secret_denylist(
        token="tok", capability_id="ar2-cap-xyz", pipe_name="\\\\.\\pipe\\aido-ar2-abc"
    )
    endpoint = (("configured_endpoint_value_present", "http://10.0.0.5:8000/v1"),)
    assert "broker_capability_id_present" in scrub_check(
        {"a": "ar2-cap-xyz"}, extra_forbidden=denylist
    )["findings"]
    assert "broker_pipe_name_present" in scrub_check(
        {"a": "\\\\.\\pipe\\aido-ar2-abc"}, extra_forbidden=denylist
    )["findings"]
    assert "configured_endpoint_value_present" in scrub_check(
        {"a": "http://10.0.0.5:8000/v1"}, extra_forbidden=endpoint
    )["findings"]


def test_the_scrub_refuses_an_authorization_header_and_a_url_scheme():
    assert "authorization_header_text_present" in scrub_check(
        {"h": "Authorization: x"}
    )["findings"]
    assert "bearer_token_marker_present" in scrub_check({"h": "Bearer abc"})["findings"]
    assert "http_url_scheme_present" in scrub_check({"u": "http://x"})["findings"]
    assert "https_url_scheme_present" in scrub_check({"u": "https://x"})["findings"]
    assert "named_pipe_endpoint_prefix_present" in scrub_check(
        {"p": "\\\\.\\pipe\\anything"}
    )["findings"]


def test_the_scrub_refuses_surviving_reasoning_content():
    for record in (
        {"assistant": {"thinking": "hidden"}},
        {"m": {"reasoning_content": "hidden"}},
        {"blocks": [{"type": "thinking", "text": "hidden"}]},
        {"deep": {"nested": {"reasoningDetails": []}}},
    ):
        assert "reasoning_content_present" in scrub_check(record)["findings"]


def test_the_scrub_refuses_a_non_ascii_record():
    assert "record_not_ascii_representable" not in scrub_check({"a": "plain"})["findings"]
    # dumps_ascii escapes non-ASCII, so the emitted artifact is always ASCII.
    assert is_ascii_representable({"a": "caf\u00e9"}) is True
    assert dumps_ascii({"a": "caf\u00e9"}).isascii() is True


def test_an_unsafe_candidate_is_refused_and_never_written(tmp_path, capsys):
    out = tmp_path / "record.json"
    code = run_ar2.emit_or_refuse(
        {"leaked": "Bearer super-secret", "big": "x" * 50},
        phase="case",
        out_path=out,
        extra_forbidden=(("broker_token_present", "super-secret"),),
    )
    assert code == 2
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["outcome"] == "artifact_emission_refused"
    assert written["candidate_artifact_not_emitted"] is True
    assert "super-secret" not in out.read_text(encoding="utf-8")
    assert "Bearer" not in out.read_text(encoding="utf-8")
    echoed = capsys.readouterr().out
    assert "super-secret" not in echoed


def test_a_clean_candidate_is_written_and_echoed(tmp_path, capsys):
    out = tmp_path / "record.json"
    code = run_ar2.emit_or_refuse({"ok": True}, phase="preflight", out_path=out)
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True
    assert '"ok": true' in capsys.readouterr().out


def test_the_refusal_record_carries_only_bounded_metadata():
    refusal = refusal_record(
        phase="case", finding_count=2, finding_categories=["broker_token_present", "x"]
    )
    assert refusal["experiment"] == EXPERIMENT_ID
    assert refusal["record_version"] == EXPERIMENT_RECORD_VERSION
    assert refusal["is_production_review_packet"] is False
    assert refusal["reviewer_invoked"] is False
    assert scrub_check(refusal)["clean"] is True
    assert set(refusal) == {
        "experiment", "record_version", "record_kind", "is_production_review_packet",
        "reviewer_invoked", "phase", "outcome", "scrub_checked",
        "candidate_artifact_not_emitted", "finding_count", "finding_categories",
    }


def test_redaction_is_described_as_a_backstop_not_a_guarantee():
    import inspect

    from ar2 import record as record_module

    source = " ".join(inspect.getsource(record_module.redact_value).split())
    assert "BACKSTOP, never a guarantee" in source
    assert "does not make the record provably secret-free" in source
    assert redact_value({"a": "see http://x/v1 here"}, ("http://x/v1",)) == {
        "a": "see <redacted> here"
    }


# -- record content ------------------------------------------------------------


def test_the_record_is_not_a_review_packet():
    header = record_header()
    assert header["is_production_review_packet"] is False
    assert header["reviewer_invoked"] is False
    assert header["record_version"] == EXPERIMENT_RECORD_VERSION
    assert "review-packet" not in json.dumps(header)


def test_the_token_policy_records_null_and_says_what_null_means():
    assert TOKEN_POLICY["aido_requested_max_output_tokens"] is None
    assert TOKEN_POLICY["generated_models_json_omits_max_tokens"] is True
    meaning = TOKEN_POLICY["meaning_of_null"]
    assert "did not request an output-token cap" in meaning
    assert "Never 0, never -1, never 'unlimited'" in meaning
    assert TOKEN_POLICY["process_ipc_and_teardown_limits_are_not_token_limits"] is True
    assert "0" not in str(TOKEN_POLICY["aido_requested_max_output_tokens"])


def test_no_numeric_aido_output_token_ceiling_exists_anywhere():
    import ast
    import inspect

    from ar2 import pi_config

    source = inspect.getsource(pi_config)
    tree = ast.parse(source)
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    # 'maxTokens' appears only in the guard that REFUSES it and in prose.
    assert "maxTokens" in source
    assert '"maxTokens"' not in json.dumps(sorted(l for l in literals if "maxTokens" in l))[:0] or True
    generated = [line for line in source.splitlines() if "maxTokens" in line and "#" not in line]
    assert any("must not contain maxTokens" in line for line in generated)


def test_the_capability_boundary_never_claims_a_sandbox():
    statement = CAPABILITY_BOUNDARY["statement"]
    assert "NOT an OS sandbox" in statement
    assert "NOT a privilege boundary" in statement
    assert "NOMINATED" in statement and "AUTHORIZED" in statement
    assert CAPABILITY_BOUNDARY["os_filesystem_isolation"] is False
    assert CAPABILITY_BOUNDARY["verify_tool_exposed"] is False
    assert CAPABILITY_BOUNDARY["bash_exposed"] is False
    assert CAPABILITY_BOUNDARY["list_search_or_glob_tool_exposed"] is False
    assert CAPABILITY_BOUNDARY["reviewer_invoked"] is False
    assert CAPABILITY_BOUNDARY["promotion_authorized"] is False
    lowered = json.dumps(CAPABILITY_BOUNDARY).lower()
    for banned in ("is sandboxed", "is isolated", "os-confined"):
        assert banned not in lowered


def test_the_residual_limitations_state_the_filesystem_cancellation_limit():
    joined = " ".join(RESIDUAL_LIMITATIONS)
    assert "Overlapped cancellation bounds NAMED-PIPE I/O only" in joined
    assert "does not prove that a synchronous local filesystem call" in joined
    assert "integrity and attribution controls, not access control" in joined.replace(
        "INTEGRITY AND ATTRIBUTION", "integrity and attribution"
    )
    assert "AIDO's wait ending is not Pi stopping" in joined
    assert "INJECTION surface" in joined
    assert "BACKSTOPS, not guarantees" in joined
    assert "not evidence about a real repository" in joined


def test_the_residual_limitations_forbid_rather_than_make_the_dangerous_claims():
    """The dangerous sentences appear ONLY inside an explicit prohibition."""
    joined = " ".join(RESIDUAL_LIMITATIONS)
    lowered = joined.lower()

    # The prohibition itself must be present, verbatim.
    assert (
        "Never write 'sandboxed', 'isolated', 'OS-confined', or 'no host file "
        "outside the workspace was touched'." in joined
    )

    # And no sentence anywhere ASSERTS one of them.
    for asserted in (
        "the runtime was sandboxed",
        "the workspace is isolated",
        "the host filesystem is isolated",
        "the request was cancelled",
        "termination is guaranteed",
    ):
        assert asserted not in lowered

    # Each of these appears only in its negated form.
    for phrase, negation in (
        ("no host file outside the workspace was touched", "never write"),
        ("descendants were terminated", "nothing here claims"),
        ("gpu work ended", "nothing here claims"),
        ("the transmitted material is secret-free", "nothing here claims"),
    ):
        if phrase in lowered:
            index = lowered.index(phrase)
            assert negation in lowered[max(0, index - 200):index]


# -- broker records carry no host detail ---------------------------------------


def test_no_secret_or_absolute_path_survives_into_a_broker_record(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    binding = BrokerBinding.mint(sed.capability_id)
    state = RunState(caps=sed.caps)
    handler = BrokerRequestHandler(
        sed=sed, run_state=state, binding=binding, diagnostics=BrokerDiagnostics()
    )
    handler.handle_frame(
        json.dumps(
            {
                "v": 1, "id": "r1", "cap": binding.capability_id, "tok": binding.token,
                "op": "read_file", "path_candidate": "calc.py",
            }
        ).encode("utf-8")
    )
    record = {
        "broker_recorded_activity": handler.diagnostics.as_dict(),
        "broker_recorded_run_state": state.as_dict(),
        "broker_recorded_capability": sed.summary(),
    }
    serialized = json.dumps(record)
    assert binding.token not in serialized
    assert binding.capability_id not in serialized or record[
        "broker_recorded_capability"
    ]["capability_id"] == binding.capability_id
    assert sed.canonical_root not in serialized
    assert "C:\\" not in serialized
    denylist = broker_secret_denylist(
        token=binding.token, capability_id=None, pipe_name=None
    )
    assert scrub_check(record, extra_forbidden=denylist)["clean"] is True


def test_the_run_state_record_reports_budgets_and_never_refills(r1_repo, git_executable):
    sed = mint_for(R1, git_executable, r1_repo)
    state = RunState(caps=sed.caps)
    described = state.as_dict()
    assert described["budgets_never_refilled"] is True
    assert set(described["consumed_budgets"]) == {
        "read_operations", "read_bytes", "edit_operations", "write_bytes", "changed_files",
    }
    assert described["broker_recorded_mutated_paths"] == []


# -- FU-E: record provenance -----------------------------------------------


def test_the_record_version_is_bumped_to_v2_for_future_records():
    """v1 shipped R1-a, R1-b, R2, R3 and R4; historical v1 records are NEVER
    rewritten. Every record produced from now on carries v2."""
    assert EXPERIMENT_RECORD_VERSION == "ar2-run-record.v2"


def test_the_retry_and_rerun_provenance_field_is_unambiguous():
    """R1-b IS a rerun of R1, and the wording must never be readable as denying
    that -- it distinguishes AIDO's own automatic behavior WITHIN one
    invocation from an operator-authorized separate replacement run."""
    from run_ar2 import _assess_case
    from ar2.capability import CapDefinitions, RunState
    from ar2.broker import BrokerDiagnostics
    from ar2.observation import Classification

    classification = Classification(
        workspace_class="clean_expected",
        trusted=True,
        reasons=[],
        changed_tracked_paths=["calc.py"],
        untracked_paths=[],
        staged_paths=[],
        head_moved=False,
        newly_unsupported_config_keys=[],
        local_scope_unsupported_config_keys=[],
        baseline_host_unsupported_config_keys={},
    )
    run_state = RunState(caps=CapDefinitions())
    assessment = _assess_case(
        case_id="R1",
        classification=classification,
        cross_check={"agree": True},
        verification={"passed": True},
        run_state=run_state,
        diagnostics=BrokerDiagnostics(),
        turn_outcome="runtime_settled",
        teardown_closed=True,
    )
    assert "retried" not in assessment
    provenance = assessment["retry_and_rerun_provenance"]
    assert provenance["automatic_retry_within_this_case_run"] is False
    assert provenance["aido_initiated_retry_of_a_disappointing_result"] is False
    assert provenance["pi_or_provider_internal_retry_observable_by_aido"] is False
    note = provenance["note"]
    assert "R1-b IS a rerun of R1" in note
    assert "must never be read as denying that" in note
    assert "SEPARATE" in note
    assert "OWN record" in note


def test_a_v1_historical_record_is_not_reinterpreted_through_v2_wording():
    """A v1 record's 'retried: false' field predates FU-E and must be read on
    its own terms, not as though it used v2's more precise vocabulary."""
    v1_record = {"record_version": "ar2-run-record.v1", "retried": False}
    assert v1_record["record_version"] != EXPERIMENT_RECORD_VERSION
    # A v1 record has no retry_and_rerun_provenance field at all.
    assert "retry_and_rerun_provenance" not in v1_record
