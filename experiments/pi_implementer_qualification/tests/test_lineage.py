"""Immutable invalidation/replacement lineage evidence (Sec. 13, Sec. 26).

The binding rule under test: an emitted qualification record is NEVER
mutated. Invalidation is represented by separate, NEW, linked evidence that
references the old record by content digest -- never by editing it.

Phase 5F3B-I1-FU1 additionally proves that immutability is enforced by the
WRITER (exclusive-create), not merely by callers choosing fresh pathnames,
and that lineage evidence goes through the same scrub/safety choke point as
a run record.
"""

from __future__ import annotations

import json
import os

import pytest

from qualification.lineage import (
    FIXTURE_OR_PROMPT_DEFECT,
    INFRASTRUCTURE_CONTAMINATION,
    LineageBindingError,
    build_invalidation_evidence,
    sha256_of_file,
    verify_immutable,
    write_invalidation_evidence,
)
from qualification.records import build_qualification_record, emit_or_refuse
from qualification.safety import ArtifactSafetyContext, EvidencePathCollisionError

NO_SECRETS = ArtifactSafetyContext.none_declared()


def _sample_record(task_id: str, task_revision: str) -> dict:
    return build_qualification_record(
        candidate="A",
        model_id="qwen3-coder-next",
        task_id=task_id,
        task_revision=task_revision,
        semantic_prompts_sent=1,
        infrastructure_refusal=False,
        run_validity="VALID",
        scoring_eligible=True,
        autonomous_classification="AUTONOMOUS_PASS",
        diagnostic_subclassification="NONE",
        operator_continuation=False,
        automatic_semantic_retry=False,
        pi_runtime={"observed_version": "0.84.2-synthetic"},
        route_provenance={"model_id": "qwen3-coder-next"},
        verification={"passed": True},
        scope_result={"hard_refusal_count": 0},
        report_accuracy={"bucket": "ACCURATE"},
    )


def test_prior_record_remains_byte_for_byte_unchanged_after_invalidation(tmp_path):
    old_path = str(tmp_path / "iq2_original.json")
    emit_or_refuse(_sample_record("IQ-2", "IQ-2@original00000000"), path=old_path, safety=NO_SECRETS)

    with open(old_path, "rb") as handle:
        original_bytes = handle.read()
    original_sha = sha256_of_file(old_path)

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-2@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        corrected_task_revision="IQ-2@corrected0000000",
    )
    write_invalidation_evidence(
        evidence, path=str(tmp_path / "iq2_invalidation.json"), safety=NO_SECRETS
    )

    with open(old_path, "rb") as handle:
        after_bytes = handle.read()
    assert after_bytes == original_bytes
    assert verify_immutable(old_path, original_sha)


def test_replacement_record_links_to_exact_prior_record_and_revision(tmp_path):
    old_path = str(tmp_path / "iq2_original.json")
    emit_or_refuse(_sample_record("IQ-2", "IQ-2@original00000000"), path=old_path, safety=NO_SECRETS)
    old_sha = sha256_of_file(old_path)

    new_path = str(tmp_path / "iq2_replacement.json")
    replacement = _sample_record("IQ-2", "IQ-2@corrected0000000")
    replacement["supersedes_task_revision"] = "IQ-2@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-2@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        corrected_task_revision="IQ-2@corrected0000000",
        replacement_record_path=new_path,
    )

    assert evidence["invalidated_record_sha256"] == old_sha
    assert evidence["invalidated_task_revision"] == "IQ-2@original00000000"
    assert evidence["corrected_task_revision"] == "IQ-2@corrected0000000"
    assert evidence["replacement_record_filename"] == "iq2_replacement.json"

    with open(new_path, encoding="utf-8") as handle:
        replacement_on_disk = json.load(handle)
    assert replacement_on_disk["supersedes_task_revision"] == "IQ-2@original00000000"


def test_infrastructure_contamination_replacement_lineage(tmp_path):
    old_path = str(tmp_path / "iq3_contaminated.json")
    emit_or_refuse(
        _sample_record("IQ-3", "IQ-3@contaminated0000"), path=old_path, safety=NO_SECRETS
    )

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-3@contaminated0000",
        invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
    )
    assert evidence["invalidation_reason"] == INFRASTRUCTURE_CONTAMINATION
    assert evidence["scoring_eligible"] is False
    # No replacement issued yet is a legitimate, representable state.
    assert evidence["replacement_record_filename"] is None
    assert evidence["supersedes_relationship"] is None


def test_building_invalidation_evidence_never_opens_the_old_record_for_writing(tmp_path):
    old_path = str(tmp_path / "iq1_original.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)
    with open(old_path, "rb") as handle:
        before = handle.read()
    before_mtime = os.path.getmtime(old_path)

    build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
    )

    with open(old_path, "rb") as handle:
        after = handle.read()
    assert before == after
    assert os.path.getmtime(old_path) == before_mtime


def test_lineage_cannot_overwrite_an_existing_qualification_record(tmp_path):
    """The writer, not caller discipline, is what makes evidence immutable."""
    record_path = str(tmp_path / "record.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=record_path, safety=NO_SECRETS)
    with open(record_path, "rb") as handle:
        record_bytes = handle.read()

    evidence = build_invalidation_evidence(
        invalidated_record_path=record_path,
        invalidated_task_revision="IQ-1@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
    )
    with pytest.raises(EvidencePathCollisionError):
        write_invalidation_evidence(evidence, path=record_path, safety=NO_SECRETS)

    with open(record_path, "rb") as handle:
        assert handle.read() == record_bytes


def test_lineage_cannot_overwrite_earlier_lineage_evidence(tmp_path):
    record_path = str(tmp_path / "record.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=record_path, safety=NO_SECRETS)
    evidence = build_invalidation_evidence(
        invalidated_record_path=record_path,
        invalidated_task_revision="IQ-1@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
    )

    lineage_path = str(tmp_path / "lineage.json")
    write_invalidation_evidence(evidence, path=lineage_path, safety=NO_SECRETS)
    with open(lineage_path, "rb") as handle:
        first_bytes = handle.read()

    with pytest.raises(EvidencePathCollisionError):
        write_invalidation_evidence(evidence, path=lineage_path, safety=NO_SECRETS)

    with open(lineage_path, "rb") as handle:
        assert handle.read() == first_bytes


def test_lineage_emission_requires_an_explicit_safety_context(tmp_path):
    record_path = str(tmp_path / "record.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@x0000000000000"), path=record_path, safety=NO_SECRETS)
    evidence = build_invalidation_evidence(
        invalidated_record_path=record_path,
        invalidated_task_revision="IQ-1@x0000000000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
    )
    with pytest.raises(TypeError):
        write_invalidation_evidence(evidence, path=str(tmp_path / "lineage.json"))


def test_an_unsafe_lineage_field_never_reaches_disk(tmp_path):
    """Lineage carries operator-supplied reasons and identifiers, so it is
    scrub-checked exactly like a run record rather than trusted."""
    record_path = str(tmp_path / "record.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=record_path, safety=NO_SECRETS)
    evidence = build_invalidation_evidence(
        invalidated_record_path=record_path,
        invalidated_task_revision="IQ-1@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
    )
    needle = "synthetic-broker-token-lineage-0000"
    evidence["operator_note"] = f"route restored after rotating {needle}"

    lineage_path = str(tmp_path / "lineage.json")
    result = write_invalidation_evidence(
        evidence, path=lineage_path, safety=ArtifactSafetyContext(broker_token=needle)
    )

    assert result["refused"] is True
    with open(lineage_path, encoding="utf-8") as handle:
        on_disk_text = handle.read()
    assert needle not in on_disk_text
    # The refusal artifact names the finding CODE, never the offending value.
    on_disk = json.loads(on_disk_text)
    assert on_disk["record_kind"] == "artifact emission refusal"
    assert on_disk["refused_record_kind"] == "qualification lineage invalidation"
    assert "broker_token_present" in on_disk["finding_categories"]


def test_an_unsafe_bare_ip_in_lineage_never_reaches_disk(tmp_path):
    record_path = str(tmp_path / "record.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=record_path, safety=NO_SECRETS)
    evidence = build_invalidation_evidence(
        invalidated_record_path=record_path,
        invalidated_task_revision="IQ-1@original00000000",
        invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
    )
    evidence["operator_note"] = "route at 198.51.100.23 was restored"

    lineage_path = str(tmp_path / "lineage.json")
    result = write_invalidation_evidence(evidence, path=lineage_path, safety=NO_SECRETS)

    assert result["refused"] is True
    with open(lineage_path, encoding="utf-8") as handle:
        assert "198.51.100.23" not in handle.read()


def test_invalid_invalidation_reason_is_rejected(tmp_path):
    old_path = str(tmp_path / "record.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@x0000000000000"), path=old_path, safety=NO_SECRETS)
    with pytest.raises(ValueError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@x0000000000000",
            invalidation_reason="not_a_real_reason",
        )


# ===========================================================================
# FU2: lineage must verify the old and replacement records it references
# ===========================================================================


def test_caller_supplied_wrong_old_task_revision_is_rejected(tmp_path):
    """(E-1) The caller's claimed revision must match what the file itself
    declares -- it is no longer trusted independently of the file."""
    old_path = str(tmp_path / "record.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@actualactualactua"), path=old_path, safety=NO_SECRETS)
    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@wrongwrongwrongwr",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        )


def test_old_file_being_a_refusal_artifact_instead_of_a_run_record_is_rejected(tmp_path):
    """(E-2) A refusal record's record_kind is 'artifact emission refusal',
    never a real run record -- it must not be usable as invalidation evidence."""
    from qualification.records import build_refusal_record

    refusal_path = str(tmp_path / "refusal.json")
    refusal = build_refusal_record(
        refused_record_kind="qualification run record",
        finding_count=1,
        finding_categories=["reasoning_content_present"],
    )
    with open(refusal_path, "x", encoding="utf-8") as handle:
        json.dump(refusal, handle)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=refusal_path,
            invalidated_task_revision="IQ-1@doesnotmatterxxxxx",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        )


def test_malformed_old_record_json_is_rejected(tmp_path):
    """(E-3)"""
    bad_path = str(tmp_path / "bad.json")
    with open(bad_path, "x", encoding="utf-8") as handle:
        handle.write("{not valid json,,,")

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=bad_path,
            invalidated_task_revision="IQ-1@doesnotmatterxxxxx",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        )


def test_replacement_lacking_supersedes_task_revision_is_rejected(tmp_path):
    """(E-4) The replacement's OWN record must declare what it supersedes."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@corrected0000000")  # no supersedes_task_revision set
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
            corrected_task_revision="IQ-1@corrected0000000",
            replacement_record_path=new_path,
        )


def test_replacement_superseding_a_different_revision_is_rejected(tmp_path):
    """(E-5)"""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@corrected0000000")
    replacement["supersedes_task_revision"] = "IQ-1@someotherrevision"  # wrong
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
            corrected_task_revision="IQ-1@corrected0000000",
            replacement_record_path=new_path,
        )


def test_replacement_belonging_to_another_task_is_rejected(tmp_path):
    """(E-6)"""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-2", "IQ-2@corrected0000000")  # wrong task
    replacement["supersedes_task_revision"] = "IQ-1@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
            corrected_task_revision="IQ-2@corrected0000000",
            replacement_record_path=new_path,
        )


def test_replacement_belonging_to_another_candidate_is_rejected(tmp_path):
    """(E-7)"""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    new_path = str(tmp_path / "new.json")
    replacement = build_qualification_record(
        candidate="B",
        model_id="minimax-m2.7",
        task_id="IQ-1",
        task_revision="IQ-1@corrected0000000",
        semantic_prompts_sent=1,
        infrastructure_refusal=False,
        run_validity="VALID",
        scoring_eligible=True,
        autonomous_classification="AUTONOMOUS_PASS",
        diagnostic_subclassification="NONE",
        operator_continuation=False,
        automatic_semantic_retry=False,
        pi_runtime={"observed_version": "0.84.2-synthetic"},
        route_provenance={"model_id": "minimax-m2.7"},
        verification={"passed": True},
        scope_result={"hard_refusal_count": 0},
        report_accuracy={"bucket": "ACCURATE"},
    )
    replacement["supersedes_task_revision"] = "IQ-1@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
            corrected_task_revision="IQ-1@corrected0000000",
            replacement_record_path=new_path,
        )


def test_corrected_task_revision_disagreeing_with_replacement_revision_is_rejected(tmp_path):
    """(E-8)"""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@corrected0000000")
    replacement["supersedes_task_revision"] = "IQ-1@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
            corrected_task_revision="IQ-1@doesnotmatchxxxxx",  # disagrees with the file
            replacement_record_path=new_path,
        )


def test_fixture_defect_replacement_without_corrected_task_revision_is_rejected(tmp_path):
    """A fixture/prompt-defect replacement must state what it corrected to."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@corrected0000000")
    replacement["supersedes_task_revision"] = "IQ-1@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
            replacement_record_path=new_path,
            # corrected_task_revision omitted
        )


def test_valid_fixture_defect_replacement_lineage_is_fully_populated(tmp_path):
    """(E-9) The complete happy path: old SHA, exact old revision, replacement
    SHA, exact replacement revision, and a verified supersedes relationship."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)
    old_sha = sha256_of_file(old_path)

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@corrected0000000")
    replacement["supersedes_task_revision"] = "IQ-1@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)
    replacement_sha = sha256_of_file(new_path)

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        corrected_task_revision="IQ-1@corrected0000000",
        replacement_record_path=new_path,
    )

    assert evidence["invalidated_record_sha256"] == old_sha
    assert evidence["invalidated_task_revision"] == "IQ-1@original00000000"
    assert evidence["replacement_record_sha256"] == replacement_sha
    assert evidence["corrected_task_revision"] == "IQ-1@corrected0000000"
    assert evidence["replacement_record_filename"] == "new.json"
    assert evidence["supersedes_relationship"] == (
        "replacement_record supersedes invalidated_record"
    )


def test_infrastructure_contamination_lineage_without_replacement_is_representable(tmp_path):
    """(E-10)"""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(
        _sample_record("IQ-1", "IQ-1@contaminated0000"), path=old_path, safety=NO_SECRETS
    )

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@contaminated0000",
        invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
    )
    assert evidence["replacement_record_filename"] is None
    assert evidence["replacement_record_sha256"] is None
    assert evidence["corrected_task_revision"] is None


def test_infrastructure_replacement_with_same_task_revision_is_representable(tmp_path):
    """(E-11) The task/fixture itself did not change -- only the contaminated
    run did -- so the replacement may legitimately carry the SAME task
    revision as the run it replaces."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(
        _sample_record("IQ-1", "IQ-1@samerevision0000"), path=old_path, safety=NO_SECRETS
    )

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@samerevision0000")  # identical revision
    replacement["supersedes_task_revision"] = "IQ-1@samerevision0000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@samerevision0000",
        invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
        corrected_task_revision="IQ-1@samerevision0000",
        replacement_record_path=new_path,
    )
    assert evidence["corrected_task_revision"] == "IQ-1@samerevision0000"
    assert evidence["replacement_record_filename"] == "new.json"


def test_infrastructure_replacement_with_same_revision_and_no_corrected_revision_argument(tmp_path):
    """The same shape as E-11, but the caller does not separately restate
    corrected_task_revision -- infrastructure contamination does not require
    it, unlike a fixture/prompt defect."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(
        _sample_record("IQ-1", "IQ-1@samerevision0000"), path=old_path, safety=NO_SECRETS
    )

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@samerevision0000")
    replacement["supersedes_task_revision"] = "IQ-1@samerevision0000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@samerevision0000",
        invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
        replacement_record_path=new_path,
    )
    assert evidence["replacement_record_filename"] == "new.json"
    assert evidence["corrected_task_revision"] is None


def test_neither_old_nor_replacement_file_is_modified_by_lineage_construction(tmp_path):
    """(E-12)"""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)
    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@corrected0000000")
    replacement["supersedes_task_revision"] = "IQ-1@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    with open(old_path, "rb") as handle:
        old_before = handle.read()
    with open(new_path, "rb") as handle:
        new_before = handle.read()
    old_mtime_before = os.path.getmtime(old_path)
    new_mtime_before = os.path.getmtime(new_path)

    build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        corrected_task_revision="IQ-1@corrected0000000",
        replacement_record_path=new_path,
    )

    with open(old_path, "rb") as handle:
        assert handle.read() == old_before
    with open(new_path, "rb") as handle:
        assert handle.read() == new_before
    assert os.path.getmtime(old_path) == old_mtime_before
    assert os.path.getmtime(new_path) == new_mtime_before


# ===========================================================================
# FU2A: invalidation_reason must mechanically agree with the revision change
# ===========================================================================


def test_fixture_defect_corrected_revision_reusing_old_revision_is_rejected(tmp_path):
    """(FU2A-1) No replacement yet -- a fixture/prompt-defect lineage may
    legitimately exist before the replacement run happens, but a supplied
    corrected_task_revision must still differ from the old revision."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
            corrected_task_revision="IQ-1@original00000000",  # reuses the old revision
        )


def test_fixture_defect_replacement_reusing_old_revision_is_rejected(tmp_path):
    """(FU2A-2) A fixture/prompt-defect replacement must NOT reuse the old
    task_revision -- that would mean the frozen contract did not actually
    change, contradicting the declared reason."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@original00000000")  # same revision as old
    replacement["supersedes_task_revision"] = "IQ-1@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
            corrected_task_revision="IQ-1@original00000000",
            replacement_record_path=new_path,
        )


def test_infrastructure_contamination_replacement_with_different_revision_is_rejected(tmp_path):
    """(FU2A-3) Infrastructure contamination re-runs the SAME frozen task; a
    replacement carrying a different revision would mislabel an actual task
    change as a pure infrastructure re-run."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@differentrevisio")  # different revision
    replacement["supersedes_task_revision"] = "IQ-1@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
            replacement_record_path=new_path,
        )


def test_infrastructure_contamination_corrected_revision_differing_is_rejected(tmp_path):
    """(FU2A-4) Same rule, checked standalone against a caller-supplied
    corrected_task_revision even with no replacement record yet."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=old_path,
            invalidated_task_revision="IQ-1@original00000000",
            invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
            corrected_task_revision="IQ-1@differentrevisio",  # differs from old
        )


def test_fixture_defect_with_a_genuinely_differing_replacement_revision_is_accepted(tmp_path):
    """(FU2A-5, positive) The ordinary happy path: corrected revision differs
    from old, and the replacement's own revision equals the corrected one."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@original00000000"), path=old_path, safety=NO_SECRETS)

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@corrected0000000")
    replacement["supersedes_task_revision"] = "IQ-1@original00000000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        corrected_task_revision="IQ-1@corrected0000000",
        replacement_record_path=new_path,
    )
    assert evidence["corrected_task_revision"] == "IQ-1@corrected0000000"
    assert evidence["invalidated_task_revision"] == "IQ-1@original00000000"


def test_infrastructure_contamination_same_frozen_revision_replacement_is_accepted(tmp_path):
    """(FU2A-6, positive)"""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(
        _sample_record("IQ-1", "IQ-1@samerevision0000"), path=old_path, safety=NO_SECRETS
    )

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@samerevision0000")
    replacement["supersedes_task_revision"] = "IQ-1@samerevision0000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@samerevision0000",
        invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
        corrected_task_revision="IQ-1@samerevision0000",
        replacement_record_path=new_path,
    )
    assert evidence["replacement_record_filename"] == "new.json"
    assert evidence["corrected_task_revision"] == "IQ-1@samerevision0000"


def test_infrastructure_contamination_same_revision_replacement_without_corrected_revision_is_accepted(
    tmp_path,
):
    """(FU2A-7, positive) corrected_task_revision is optional for infrastructure
    contamination, unlike a fixture/prompt defect."""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(
        _sample_record("IQ-1", "IQ-1@samerevision0000"), path=old_path, safety=NO_SECRETS
    )

    new_path = str(tmp_path / "new.json")
    replacement = _sample_record("IQ-1", "IQ-1@samerevision0000")
    replacement["supersedes_task_revision"] = "IQ-1@samerevision0000"
    emit_or_refuse(replacement, path=new_path, safety=NO_SECRETS)

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@samerevision0000",
        invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
        replacement_record_path=new_path,
    )
    assert evidence["replacement_record_filename"] == "new.json"
    assert evidence["corrected_task_revision"] is None


def test_infrastructure_contamination_without_replacement_is_accepted(tmp_path):
    """(FU2A-8, positive)"""
    old_path = str(tmp_path / "old.json")
    emit_or_refuse(
        _sample_record("IQ-1", "IQ-1@contaminated0000"), path=old_path, safety=NO_SECRETS
    )

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@contaminated0000",
        invalidation_reason=INFRASTRUCTURE_CONTAMINATION,
    )
    assert evidence["replacement_record_filename"] is None
    assert evidence["corrected_task_revision"] is None


def test_invalidation_evidence_never_carries_an_absolute_path(tmp_path):
    old_path = str(tmp_path / "record.json")
    emit_or_refuse(_sample_record("IQ-1", "IQ-1@x0000000000000"), path=old_path, safety=NO_SECRETS)
    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-1@x0000000000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
    )
    assert str(tmp_path) not in json.dumps(evidence)
