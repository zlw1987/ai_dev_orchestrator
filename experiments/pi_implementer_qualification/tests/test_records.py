"""``pi-implementer-qualification.v1`` schema, invariant gate, and safe emission.

Phase 5F3B-I1-FU1 turned the builder from a formatter into a real gate and
the writer from an overwriting ``"w"`` into exclusive-create. These tests are
the proof of both.
"""

from __future__ import annotations

import json

import pytest

from qualification.records import (
    CANDIDATE_MODEL_IDS,
    RECORD_VERSION,
    RecordInvariantError,
    build_qualification_record,
    emit_or_refuse,
)
from qualification.safety import ArtifactSafetyContext, EvidencePathCollisionError

NO_SECRETS = ArtifactSafetyContext.none_declared()


def _minimal_record(**overrides) -> dict:
    base = dict(
        candidate="A",
        model_id="qwen3-coder-next",
        task_id="IQ-1",
        task_revision="IQ-1@deadbeefdeadbeef",
        semantic_prompts_sent=1,
        infrastructure_refusal=False,
        run_validity="VALID",
        scoring_eligible=True,
        autonomous_classification="AUTONOMOUS_PASS",
        diagnostic_subclassification="NONE",
        operator_continuation=False,
        automatic_semantic_retry=False,
        pi_runtime={"observed_version": "0.84.2-synthetic"},
        route_provenance={"model_id": "qwen3-coder-next", "provider_route": "synthetic"},
        verification={"passed": True},
        scope_result={"hard_refusal_count": 0},
        report_accuracy={"bucket": "ACCURATE"},
    )
    base.update(overrides)
    return build_qualification_record(**base)


# -- schema shape ------------------------------------------------------------


def test_record_carries_required_qualification_metadata():
    record = _minimal_record()
    assert record["record_version"] == RECORD_VERSION
    assert record["external_prior_not_scored"] is True
    assert record["reviewer_invoked"] is False
    assert record["is_review_packet"] is False
    assert record["token_policy"]["aido_requested_max_output_tokens"] is None


def test_supersedes_task_revision_only_present_when_given():
    plain = _minimal_record()
    assert "supersedes_task_revision" not in plain

    replacement = _minimal_record(supersedes_task_revision="IQ-1@oldoldoldoldoldo")
    assert replacement["supersedes_task_revision"] == "IQ-1@oldoldoldoldoldo"


# -- B: candidate <-> model identity ------------------------------------------


def test_frozen_candidate_model_pairing():
    assert CANDIDATE_MODEL_IDS == {"A": "qwen3-coder-next", "B": "minimax-m2.7"}


def test_candidate_b_with_its_own_model_is_accepted():
    record = _minimal_record(
        candidate="B",
        model_id="minimax-m2.7",
        route_provenance={"model_id": "minimax-m2.7"},
    )
    assert record["candidate"] == "B"


def test_reversed_candidate_model_pair_is_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            candidate="B", model_id="qwen3-coder-next", route_provenance={"model_id": "qwen3-coder-next"}
        )
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            candidate="A", model_id="minimax-m2.7", route_provenance={"model_id": "minimax-m2.7"}
        )


def test_unknown_candidate_is_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(candidate="C", model_id="qwen3-coder-next")


def test_route_provenance_model_id_must_agree_with_top_level_model_id():
    with pytest.raises(RecordInvariantError):
        _minimal_record(route_provenance={"model_id": "minimax-m2.7"})


def test_route_provenance_without_a_model_id_is_allowed():
    record = _minimal_record(route_provenance={"provider_route": "synthetic"})
    assert record["route_provenance"] == {"provider_route": "synthetic"}


# -- B: identity coherence ----------------------------------------------------


def test_unknown_task_id_is_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(task_id="IQ-9", task_revision="IQ-9@deadbeefdeadbeef")


def test_task_revision_must_belong_to_task_id():
    with pytest.raises(RecordInvariantError):
        _minimal_record(task_id="IQ-1", task_revision="IQ-2@deadbeefdeadbeef")


def test_supersedes_revision_must_belong_to_the_same_task():
    with pytest.raises(RecordInvariantError):
        _minimal_record(supersedes_task_revision="IQ-3@oldoldoldoldoldo")


# -- B: prompt/run shape ------------------------------------------------------


def test_pre_prompt_infrastructure_refusal_shape_is_accepted():
    record = _minimal_record(
        infrastructure_refusal=True,
        semantic_prompts_sent=0,
        run_validity=None,
        scoring_eligible=False,
        autonomous_classification="INFRASTRUCTURE_REFUSAL",
        diagnostic_subclassification="NONE",
    )
    assert record["semantic_prompts_sent"] == 0
    assert record["run_validity"] is None
    assert record["scoring_eligible"] is False


def test_infrastructure_refusal_with_a_prompt_sent_is_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            infrastructure_refusal=True,
            semantic_prompts_sent=1,
            run_validity=None,
            scoring_eligible=False,
            autonomous_classification="INFRASTRUCTURE_REFUSAL",
        )


def test_infrastructure_refusal_carrying_a_run_validity_is_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            infrastructure_refusal=True,
            semantic_prompts_sent=0,
            run_validity="VALID",
            scoring_eligible=True,
            autonomous_classification="INFRASTRUCTURE_REFUSAL",
        )


def test_infrastructure_refusal_cannot_carry_a_model_classification():
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            infrastructure_refusal=True,
            semantic_prompts_sent=0,
            run_validity=None,
            scoring_eligible=False,
            autonomous_classification="AUTONOMOUS_FAIL",
        )


def test_post_prompt_run_requires_exactly_one_prompt():
    for count in (0, 2):
        with pytest.raises(RecordInvariantError):
            _minimal_record(semantic_prompts_sent=count)


def test_post_prompt_run_requires_a_run_validity_value():
    with pytest.raises(RecordInvariantError):
        _minimal_record(run_validity=None, scoring_eligible=False)


def test_post_prompt_contaminated_run_keeps_prompt_count_one():
    record = _minimal_record(
        run_validity="INFRASTRUCTURE_CONTAMINATED",
        scoring_eligible=False,
        autonomous_classification="AUTONOMOUS_FAIL",
        diagnostic_subclassification="NONE",
    )
    assert record["semantic_prompts_sent"] == 1
    assert record["scoring_eligible"] is False


# -- B: validity coherence ----------------------------------------------------


@pytest.mark.parametrize(
    "run_validity",
    ["INFRASTRUCTURE_CONTAMINATED", "ATTRIBUTION_UNDETERMINED", "INVALIDATED_BY_FIXTURE_DEFECT"],
)
def test_non_valid_run_validity_cannot_be_scoring_eligible(run_validity):
    with pytest.raises(RecordInvariantError):
        _minimal_record(run_validity=run_validity, scoring_eligible=True)


def test_valid_run_validity_cannot_be_scoring_ineligible():
    with pytest.raises(RecordInvariantError):
        _minimal_record(run_validity="VALID", scoring_eligible=False)


def test_unknown_run_validity_is_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(run_validity="PROBABLY_FINE", scoring_eligible=False)


# -- B: classification coherence ----------------------------------------------


def test_unknown_autonomous_classification_is_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(autonomous_classification="MOSTLY_PASS")


def test_unknown_diagnostic_subclassification_is_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            autonomous_classification="AUTONOMOUS_FAIL", diagnostic_subclassification="SORT_OF"
        )


@pytest.mark.parametrize(
    "subclassification",
    [
        "PREMATURE_SETTLE",
        "RUNTIME_TIMEOUT",
        "RUNTIME_STALLED",
        "COMPLETED_BUT_WRONG",
        "UNTRUSTED_REPOSITORY_STATE",
    ],
)
def test_diagnostic_subclassification_requires_autonomous_fail(subclassification):
    """Sec. 8: these are subclassifications OF AUTONOMOUS_FAIL, never peers."""
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            autonomous_classification="AUTONOMOUS_PASS",
            diagnostic_subclassification=subclassification,
        )
    accepted = _minimal_record(
        autonomous_classification="AUTONOMOUS_FAIL",
        diagnostic_subclassification=subclassification,
        run_validity="VALID",
        scoring_eligible=True,
    )
    assert accepted["diagnostic_subclassification"] == subclassification


def test_invalid_supervised_recovery_value_is_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(supervised_recovery="MAYBE")


# -- FU2 A: the AUTONOMOUS_PASS cross-field bundle -----------------------------


def test_autonomous_pass_with_operator_continuation_is_rejected():
    """Sec. 9: 'No operator continuation inside the primary result.' A run
    with operator continuation is truthfully representable only as
    AUTONOMOUS_FAIL, never PASS."""
    with pytest.raises(RecordInvariantError):
        _minimal_record(autonomous_classification="AUTONOMOUS_PASS", operator_continuation=True)


def test_autonomous_pass_with_automatic_semantic_retry_is_rejected():
    """Sec. 9: 'No automatic semantic retry, for any reason.'"""
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            autonomous_classification="AUTONOMOUS_PASS", automatic_semantic_retry=True
        )


def test_operator_continuation_is_representable_as_autonomous_fail():
    record = _minimal_record(
        autonomous_classification="AUTONOMOUS_FAIL",
        diagnostic_subclassification="NONE",
        operator_continuation=True,
    )
    assert record["operator_continuation"] is True
    assert record["autonomous_classification"] == "AUTONOMOUS_FAIL"


def test_automatic_semantic_retry_is_representable_as_autonomous_fail():
    record = _minimal_record(
        autonomous_classification="AUTONOMOUS_FAIL",
        diagnostic_subclassification="NONE",
        automatic_semantic_retry=True,
    )
    assert record["automatic_semantic_retry"] is True
    assert record["autonomous_classification"] == "AUTONOMOUS_FAIL"


def test_autonomous_pass_requires_diagnostic_subclassification_none():
    """AUTONOMOUS_PASS + a non-NONE diagnostic subclassification (e.g. a
    stray RUNTIME_TIMEOUT tag) is incoherent: a genuine pass carries no
    failure diagnostic at all."""
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            autonomous_classification="AUTONOMOUS_PASS",
            diagnostic_subclassification="RUNTIME_TIMEOUT",
        )


def test_autonomous_pass_requires_semantic_prompts_sent_one():
    with pytest.raises(RecordInvariantError):
        _minimal_record(
            autonomous_classification="AUTONOMOUS_PASS",
            semantic_prompts_sent=0,
            infrastructure_refusal=True,
            run_validity=None,
            scoring_eligible=False,
        )


def test_valid_scoring_eligible_run_cannot_have_no_classification():
    with pytest.raises(RecordInvariantError):
        _minimal_record(autonomous_classification=None)


def test_valid_scoring_eligible_run_cannot_be_infrastructure_refusal():
    with pytest.raises(RecordInvariantError):
        _minimal_record(autonomous_classification="INFRASTRUCTURE_REFUSAL")


def test_valid_scoring_eligible_run_accepts_autonomous_fail():
    record = _minimal_record(
        autonomous_classification="AUTONOMOUS_FAIL", diagnostic_subclassification="NONE"
    )
    assert record["autonomous_classification"] == "AUTONOMOUS_FAIL"


# -- FU2 B: supervised recovery cannot be embedded in a primary record ---------


@pytest.mark.parametrize("recovery_value", ["PASS", "FAIL"])
def test_primary_record_rejects_embedded_supervised_recovery(recovery_value):
    """Sec. 10: recovery is a SEPARATE child evidence item created only AFTER
    the primary record is sealed. It must never be embedded in -- or upgrade
    -- the primary record itself."""
    with pytest.raises(RecordInvariantError):
        _minimal_record(supervised_recovery=recovery_value)


def test_primary_record_accepts_not_attempted():
    record = _minimal_record(supervised_recovery="NOT_ATTEMPTED")
    assert record["supervised_recovery"] == "NOT_ATTEMPTED"


def test_primary_record_default_supervised_recovery_is_not_attempted():
    record = _minimal_record()
    assert record["supervised_recovery"] == "NOT_ATTEMPTED"


def test_non_boolean_flags_are_rejected():
    with pytest.raises(RecordInvariantError):
        _minimal_record(operator_continuation="no")
    with pytest.raises(RecordInvariantError):
        _minimal_record(automatic_semantic_retry=1)


# -- C: exclusive-create emission ---------------------------------------------


def test_safe_record_writes(tmp_path):
    record = _minimal_record()
    path = str(tmp_path / "record.json")
    result = emit_or_refuse(record, path=path, safety=NO_SECRETS)
    assert result["emitted"] is True
    assert result["refused"] is False
    with open(path, encoding="utf-8") as handle:
        on_disk = json.load(handle)
    assert on_disk["task_id"] == "IQ-1"


def test_second_write_to_the_same_path_fails_closed(tmp_path):
    path = str(tmp_path / "record.json")
    emit_or_refuse(_minimal_record(), path=path, safety=NO_SECRETS)
    with open(path, "rb") as handle:
        first_bytes = handle.read()

    with pytest.raises(EvidencePathCollisionError):
        emit_or_refuse(
            _minimal_record(task_id="IQ-2", task_revision="IQ-2@feedfeedfeedfeed"),
            path=path,
            safety=NO_SECRETS,
        )

    with open(path, "rb") as handle:
        assert handle.read() == first_bytes


def test_an_unsafe_candidate_cannot_overwrite_an_earlier_valid_record(tmp_path):
    """The exact hazard: a later UNSAFE record must not be able to destroy an
    earlier valid historical record by writing its refusal artifact over it."""
    path = str(tmp_path / "record.json")
    emit_or_refuse(_minimal_record(), path=path, safety=NO_SECRETS)
    with open(path, "rb") as handle:
        first_bytes = handle.read()

    unsafe = _minimal_record(verification={"passed": True, "leaked": "https://example.invalid"})
    with pytest.raises(EvidencePathCollisionError):
        emit_or_refuse(unsafe, path=path, safety=NO_SECRETS)

    with open(path, "rb") as handle:
        assert handle.read() == first_bytes
    on_disk = json.loads(first_bytes.decode("utf-8"))
    assert on_disk["record_kind"] == "qualification run record"


# -- D: mandatory safety context and leak refusal ------------------------------


def test_emission_requires_an_explicit_safety_context(tmp_path):
    """There is deliberately no default that silently means "nothing to check"."""
    with pytest.raises(TypeError):
        emit_or_refuse(_minimal_record(), path=str(tmp_path / "r.json"))


@pytest.mark.parametrize(
    "needle_kwargs",
    [
        {"endpoint_host": "internal-b300.example.invalid"},
        {"api_key": "sk-synthetic-not-a-real-key-0000"},
        {"bearer_token": "Bearer synthetic-token-0000"},
        {"broker_token": "synthetic-broker-token-abc123"},
        {"pipe_name": r"\\.\pipe\aido-synthetic-pipe"},
        {"capability_id": "synthetic-capability-id-abc123"},
        {"workspace_absolute_path": r"C:\dev\ai_dev_orchestrator\experiments\synthetic"},
    ],
)
def test_declared_needle_values_are_refused_and_never_written(tmp_path, needle_kwargs):
    (needle_value,) = needle_kwargs.values()
    record = _minimal_record(verification={"passed": True, "leaked": needle_value})
    safety = ArtifactSafetyContext(**needle_kwargs)

    path = str(tmp_path / "record.json")
    result = emit_or_refuse(record, path=path, safety=safety)

    assert result["refused"] is True
    with open(path, encoding="utf-8") as handle:
        on_disk_text = handle.read()
    assert needle_value not in on_disk_text
    assert "task_revision" not in on_disk_text  # the unsafe candidate body was not written at all


def test_a_bare_undeclared_ipv4_endpoint_is_refused_structurally(tmp_path):
    """A needle only catches a value the caller knew to declare. A bare host or
    IP can reach an artifact by a route no declared needle covers (the AR2 R1-b
    lesson), so a dotted quad is refused structurally even under an all-None
    context."""
    record = _minimal_record(pi_runtime={"observed_version": "0.84.2", "seen": "203.0.113.7"})
    path = str(tmp_path / "record.json")
    result = emit_or_refuse(record, path=path, safety=NO_SECRETS)

    assert result["refused"] is True
    assert "ipv4_literal_present" in result["scrub"]["findings"]
    with open(path, encoding="utf-8") as handle:
        on_disk_text = handle.read()
    assert "203.0.113.7" not in on_disk_text


def test_an_ordinary_version_string_is_not_mistaken_for_an_ipv4_literal(tmp_path):
    record = _minimal_record(pi_runtime={"observed_version": "0.84.2"})
    result = emit_or_refuse(record, path=str(tmp_path / "record.json"), safety=NO_SECRETS)
    assert result["refused"] is False


def test_reasoning_content_is_refused_and_never_written(tmp_path):
    record = _minimal_record(
        verification={"passed": True, "reasoning": "chain-of-thought leaked into a field"}
    )
    path = str(tmp_path / "record.json")
    result = emit_or_refuse(record, path=path, safety=NO_SECRETS)
    assert result["refused"] is True
    with open(path, encoding="utf-8") as handle:
        on_disk_text = handle.read()
    assert "chain-of-thought" not in on_disk_text


# -- C: the writer property is structural, not a comment ----------------------

_TRUNCATING_OR_APPENDING_MODES = (
    '"w"', "'w'", '"a"', "'a'", '"w+"', "'w+'", '"a+"', "'a+'",
    '"r+"', "'r+'", '"wb"', "'wb'", '"ab"', "'ab'",
)


def _package_sources():
    import pathlib

    import qualification

    return sorted(pathlib.Path(qualification.__file__).parent.glob("*.py"))


def test_no_truncating_or_appending_open_exists_anywhere_in_the_package():
    """Immutability is enforced by the WRITER, so no module may quietly
    reintroduce a mode that can destroy an already-emitted artifact."""
    offenders = []
    for source_file in _package_sources():
        for lineno, line in enumerate(source_file.read_text(encoding="utf-8").splitlines(), 1):
            if "open(" not in line:
                continue
            if any(mode in line for mode in _TRUNCATING_OR_APPENDING_MODES):
                offenders.append(f"{source_file.name}:{lineno}")
    assert not offenders, f"truncating/appending open() found: {offenders}"


def test_exactly_one_evidence_writer_exists_and_it_uses_exclusive_create():
    writers = []
    for source_file in _package_sources():
        for lineno, line in enumerate(source_file.read_text(encoding="utf-8").splitlines(), 1):
            if "open(" in line and '"x"' in line:
                writers.append((source_file.name, lineno))
    assert len(writers) == 1, f"expected exactly one exclusive-create writer, found {writers}"
    assert writers[0][0] == "safety.py"


def test_refusal_record_itself_is_safe_and_bounded(tmp_path):
    record = _minimal_record(verification={"leaked": "http://internal.example.invalid/secret"})
    path = str(tmp_path / "record.json")
    result = emit_or_refuse(record, path=path, safety=NO_SECRETS)
    assert result["refused"] is True
    with open(path, encoding="utf-8") as handle:
        on_disk = json.load(handle)
    assert on_disk["record_kind"] == "artifact emission refusal"
    assert on_disk["refused_record_kind"] == "qualification run record"
    assert on_disk["candidate_artifact_not_emitted"] is True
    assert "http://" not in json.dumps(on_disk)
