"""5F3B-Q1-PRE1-FU2A-FU1A-FU1 -- Attempt-bound authority replay closure.

**No real network connection, credential, Node/Pi process, named pipe, or
model call is ever made here.** Every live-facing adapter is a synthetic
double, exactly as in the rest of this suite.

Independent review accepted FU2A-FU1A's direct-construction closure but
found THREE remaining SUPPORTED (no ``object.__new__``, no private-global
mutation, no live activity) replay bypasses:

    1. A genuine SUCCESSFUL ``EvidenceEmission``, minted for one attempt, was
       reusable as H-14 authority for a DIFFERENT result, by attaching it to
       a forged ``qualification_record`` projection whose ``path``/
       ``refused`` fields were edited to match it. Neither object needed to
       be forged -- both are genuine, just borrowed from another attempt.
    2. A genuine ``_AttemptIdentityProvenance``, minted for one result, was
       reusable as identity proof for a DIFFERENT result (another run of the
       same candidate/task, another task, or another candidate), by
       relabelling that result's own outer candidate/model_id/task_id/
       task_revision (and its projection) to match the borrowed provenance's
       value tuple.
    3. ``closure.semantic_workspace_removal.facts`` accepted ANY Mapping, so
       a scrub-clean unknown nested claim (e.g. ``backend_inference_stopped``)
       rode along unexamined, widening the attempt.v1 artifact's frozen claim
       scope.

The fix for (1)/(2): ``run_semantic_task_attempt`` mints ONE fresh, random,
per-attempt ``attempt_authority_token`` and threads it into BOTH
``identity_provenance`` and ``evidence_emission`` for that SAME call.
``SemanticTaskAttemptResult.__post_init__`` requires the two tokens to agree
exactly whenever an evidence emission is present. A replayed genuine object
from any OTHER call carries a DIFFERENT, independently-random token, so the
pairing disagrees even though every other field-level check already in place
(path/refused agreement, the candidate/model/task/revision value tuple) is
satisfied.

The fix for (3): ``closure.semantic_workspace_removal.facts`` is now a
CLOSED, typed 4-key shape read off
``qualification.semantic_controller._bounded_removal_facts``'s own exact
projection domain, plus a coherence check against the sibling ``verified``
field.

This module reproduces each as a failing-before-fix regression and proves it
is refused after the fix, plus positive controls proving genuine
controller-produced objects, and every shape ``_bounded_removal_facts`` can
actually produce, are unaffected.

**5F3B-Q1-PRE1-FU2A-FU1A-FU1-FU1** (appended below): independent review
reproduced ONE remaining supported replay the pairwise
``attempt_authority_token`` equality check above could not catch --
``qualification_record``/``identity_provenance``/``evidence_emission`` ALL
replaced together, from the SAME different genuine attempt of the SAME
candidate/task. All three borrowed objects share ONE mutually valid foreign
token, so their pairwise agreement is trivially satisfied. The fix binds
each token, in a process-local issuance registry (mirroring
``qualification.i2_issuance``'s own register/lookup precedent), to a SHA-256
fingerprint of the facts OUTSIDE the borrowed bundle itself (gate
chronology, dispatch outcome, run validity, scoring eligibility,
classification, verification) -- re-derived from the result's OWN current
facts at ``__post_init__`` time and required to match. It also closes the
last ``_bounded_removal_facts`` projection-domain gap: a
``result_shape_recognized: False`` bounded-removal projection can never
legitimately carry all three of ``removed``/``residual_file_count``/
``verified`` as non-``None``, because a key that made recognition fail is
always ``None`` in the projection.

**5F3B-Q1-PRE1-FINAL-CLOSURE** (appended below): independent review
reproduced a STRONGER replay even the facts-fingerprint check above could
not catch -- the fingerprint is derived entirely from caller-replaceable
``SemanticTaskAttemptResult`` fields, so ``replace()`` copying the foreign
attempt's ``gate_statuses`` ALONGSIDE the borrowed bundle reconstructs a
matching fingerprint too. The fix makes ``SemanticTaskAttemptResult``
construction consume a ONE-SHOT issuance: ``run_semantic_task_attempt``
registers ONE pending ``(token, fingerprint)`` pair immediately before its
own genuine construction, and ``__post_init__`` atomically
requires-and-consumes it -- deleting the entry regardless of whether the
match succeeds. A token can therefore back AT MOST ONE
``SemanticTaskAttemptResult`` construction, ever. This necessarily also
means every OTHERWISE-HARMLESS ``dataclasses.replace()`` of a genuine
result -- even one that touches only an unrelated field -- now fails too;
that is intentional (``SemanticTaskAttemptResult`` is a valid-by-
construction authority object, not a freely reconstructible DTO), and every
test in this module (and the sibling modules it shares helpers with) that
previously required a plain ``replace()`` to succeed has been updated to
assert the new one-shot refusal instead, with any genuinely independent
intent (e.g. ``freeze_mapping`` copy-before-wrap semantics) preserved
through a direct, ``SemanticTaskAttemptResult``-independent helper test.
"""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path

import pytest

from qualification.corpus import IQ1_TASK, IQ2_TASK, TASKS_BY_ID
from qualification.records import CANDIDATE_MODEL_IDS
from qualification.semantic_attempt import (
    AttemptRecordInvariantError,
    build_attempt_record,
    _REMOVAL_FACTS_VERIFIED_SHAPE,
    _require_valid_removal_facts,
)
from qualification.semantic_session import SemanticDispatchEvidenceCode

from test_semantic_controller import Harness, _iq1_correct_repair
from test_semantic_fu2a import _genuine_indeterminate_attempt_kwargs, _indeterminate


def _iq2_correct_repair(h: Harness) -> None:
    """Mirrors ``test_semantic_controller.test_iq2_full_autonomous_pass``'s
    inline correct repair -- there is no shared named helper for IQ-2, so
    this reproduces it locally rather than depending on that test's body.
    """
    parse_correct = (
        "\"\"\"Parse a raw sensor reading string into (value, unit).\"\"\"\n\n\n"
        "def parse_reading(reading):\n"
        "    text = reading.strip()\n"
        "    unit = text[-1]\n"
        "    number_text = text[:-1]\n"
        "    return float(number_text), unit\n"
    )
    convert_correct = (
        "\"\"\"Convert Celsius to Fahrenheit, rounded to one decimal.\"\"\"\n\n\n"
        "def to_fahrenheit(celsius):\n"
        "    return round(celsius * 9.0 / 5.0 + 32.0, 1)\n"
    )
    h.repair_files = {
        "units/parse.py": parse_correct,
        "units/convert.py": convert_correct,
    }
    h.edited_paths = frozenset({"units/parse.py", "units/convert.py"})
    h.claimed_changed_paths = h.edited_paths
    h.claimed_no_change = False


def _run_genuine_success(candidate: str, task, git_executable: str, path: Path):
    h = Harness(candidate, git_executable)
    if task is IQ1_TASK:
        _iq1_correct_repair(h)
    elif task is IQ2_TASK:
        _iq2_correct_repair(h)
    else:  # pragma: no cover - not exercised by this module
        raise AssertionError(f"no repair helper wired for {task!r}")
    result = h.run(task, str(path))
    assert result.evidence_emission is not None
    assert result.evidence_emission.refused is False
    return result


def _run_genuine_scrub_refusal(candidate: str, task, git_executable: str, path: Path):
    """Scoped to a private ``pytest.MonkeyPatch`` context, undone before this
    function returns -- unlike the shared per-test ``monkeypatch`` fixture,
    which stays active for the REST of the test, and would otherwise also
    dirty a later genuine-success run in the same test function.
    """
    import qualification.safety as safety_module

    h = Harness(candidate, git_executable)
    if task is IQ1_TASK:
        _iq1_correct_repair(h)
    elif task is IQ2_TASK:
        _iq2_correct_repair(h)
    else:  # pragma: no cover - not exercised by this module
        raise AssertionError(f"no repair helper wired for {task!r}")
    real_scrub_check = safety_module.qualification_scrub_check

    def _dirty_scrub(payload, safety):
        if payload.get("record_kind") == "artifact emission refusal":
            return real_scrub_check(payload, safety)
        return {"scrub_checked": True, "findings": ["needle_present"], "clean": False}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(safety_module, "qualification_scrub_check", _dirty_scrub)
        result = h.run(task, str(path))
    assert result.evidence_emission is not None
    assert result.evidence_emission.refused is True
    return result


# ===========================================================================
# 1. GENUINE EVIDENCE AUTHORITY IS REPLAYABLE ACROSS ATTEMPTS
# ===========================================================================


def test_h14_success_from_another_run_of_same_candidate_task_cannot_upgrade_refusal(
    git_executable: str, tmp_path: Path
) -> None:
    failed = _run_genuine_scrub_refusal(
        "A", IQ1_TASK, git_executable, tmp_path / "failed.json"
    )
    success = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "success.json")

    forged_projection = dict(failed.qualification_record)
    forged_projection["refused"] = False
    forged_projection["path"] = success.evidence_emission.path

    with pytest.raises(ValueError):
        replace(
            failed,
            qualification_record=forged_projection,
            evidence_emission=success.evidence_emission,
        )


def test_h14_success_from_another_candidate_cannot_be_replayed(
    git_executable: str, tmp_path: Path
) -> None:
    failed = _run_genuine_scrub_refusal(
        "A", IQ1_TASK, git_executable, tmp_path / "failed.json"
    )
    success = _run_genuine_success("B", IQ1_TASK, git_executable, tmp_path / "success.json")

    forged_projection = dict(failed.qualification_record)
    forged_projection["refused"] = False
    forged_projection["path"] = success.evidence_emission.path

    with pytest.raises(ValueError):
        replace(
            failed,
            qualification_record=forged_projection,
            evidence_emission=success.evidence_emission,
        )


def test_h14_success_from_another_task_cannot_be_replayed(
    git_executable: str, tmp_path: Path
) -> None:
    failed = _run_genuine_scrub_refusal(
        "A", IQ1_TASK, git_executable, tmp_path / "failed.json"
    )
    success = _run_genuine_success("A", IQ2_TASK, git_executable, tmp_path / "success.json")

    forged_projection = dict(failed.qualification_record)
    forged_projection["refused"] = False
    forged_projection["path"] = success.evidence_emission.path

    with pytest.raises(ValueError):
        replace(
            failed,
            qualification_record=forged_projection,
            evidence_emission=success.evidence_emission,
        )


def test_own_genuine_successful_emission_still_yields_h14_success(
    git_executable: str, tmp_path: Path
) -> None:
    """Positive control: this result's OWN genuine successful emission
    produces H-14 success.

    5F3B-Q1-PRE1-FINAL-CLOSURE: replaying the exact same pairing (both
    objects, unchanged) onto a SECOND ``SemanticTaskAttemptResult``
    construction no longer succeeds either -- ``SemanticTaskAttemptResult``
    is now a one-shot authority object, and the genuine construction below
    already consumed the only issuance this ``evidence_emission`` will ever
    back.
    """
    result = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "ok.json")
    assert result.evidence_emission.refused is False
    with pytest.raises(ValueError):
        replace(result, evidence_emission=result.evidence_emission)


# ===========================================================================
# 2. GENUINE IDENTITY PROVENANCE IS REPLAYABLE ACROSS RESULTS
# ===========================================================================


def test_a_facts_with_genuine_b_provenance_replay_refused(
    git_executable: str, tmp_path: Path
) -> None:
    a = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "a.json")
    b = _run_genuine_success("B", IQ1_TASK, git_executable, tmp_path / "b.json")

    projection = dict(a.qualification_record)
    projection["candidate"] = "B"
    projection["model_id"] = CANDIDATE_MODEL_IDS["B"]

    with pytest.raises(ValueError):
        replace(
            a,
            candidate="B",
            model_id=CANDIDATE_MODEL_IDS["B"],
            qualification_record=projection,
            identity_provenance=b.identity_provenance,
        )


def test_iq1_facts_with_genuine_iq2_provenance_replay_refused(
    git_executable: str, tmp_path: Path
) -> None:
    a = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "a.json")
    c = _run_genuine_success("A", IQ2_TASK, git_executable, tmp_path / "c.json")

    projection = dict(a.qualification_record)
    projection["task_id"] = "IQ-2"
    projection["task_revision"] = TASKS_BY_ID["IQ-2"].task_revision

    with pytest.raises(ValueError):
        replace(
            a,
            task_id="IQ-2",
            task_revision=TASKS_BY_ID["IQ-2"].task_revision,
            qualification_record=projection,
            identity_provenance=c.identity_provenance,
        )


def test_same_candidate_task_provenance_from_another_run_cannot_replace_this_attempts(
    git_executable: str, tmp_path: Path
) -> None:
    """Two SEPARATE genuine runs of the SAME candidate/task pair mint
    _AttemptIdentityProvenance instances with EQUAL field values (same
    candidate/model/task/revision) but are minted by different calls. The
    second run's provenance must not be usable to back the first run's own
    retained evidence, even though nothing about the outer
    candidate/model_id/task_id/task_revision needs to change to attempt it.
    """
    b1 = _run_genuine_success("B", IQ1_TASK, git_executable, tmp_path / "b1.json")
    b2 = _run_genuine_success("B", IQ1_TASK, git_executable, tmp_path / "b2.json")
    assert (
        b1.identity_provenance.candidate,
        b1.identity_provenance.task_id,
    ) == (
        b2.identity_provenance.candidate,
        b2.identity_provenance.task_id,
    )

    with pytest.raises(ValueError):
        replace(b1, identity_provenance=b2.identity_provenance)


def test_genuine_result_replace_of_an_unrelated_field_no_longer_works(
    git_executable: str, tmp_path: Path
) -> None:
    """5F3B-Q1-PRE1-FINAL-CLOSURE: ``SemanticTaskAttemptResult`` is now a
    one-shot, valid-by-construction authority object, not a freely
    reconstructible DTO -- so a plain ``replace()`` that doesn't touch
    identity or evidence at all no longer works either. The genuine
    construction below already consumed the ONLY issuance ``result``'s
    ``identity_provenance``/``evidence_emission`` will ever have; a SECOND
    construction attempt, for ANY reason, finds nothing pending.
    """
    result = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "ok.json")
    assert result.candidate == "A"
    with pytest.raises(ValueError):
        replace(result, observed_pi_version=result.observed_pi_version)


# ===========================================================================
# 3. ATTEMPT.V1 NESTED WORKSPACE-REMOVAL FACTS ARE NOW CLOSED
# ===========================================================================


def test_removal_facts_rejects_an_unknown_extra_key() -> None:
    facts = {
        "result_shape_recognized": True,
        "removed": True,
        "residual_file_count": 0,
        "verified": True,
        "backend_inference_stopped": True,
    }
    with pytest.raises(AttemptRecordInvariantError):
        _require_valid_removal_facts(facts)


def test_removal_facts_rejects_a_missing_key() -> None:
    facts = {"result_shape_recognized": True, "removed": True, "verified": True}
    with pytest.raises(AttemptRecordInvariantError):
        _require_valid_removal_facts(facts)


def test_removal_facts_rejects_a_bool_residual_file_count() -> None:
    facts = {
        "result_shape_recognized": True,
        "removed": True,
        # `True` is a `bool`, not an `int` here -- `_bounded_removal_facts`'
        # own `_exact_int` excludes it too.
        "residual_file_count": True,
        "verified": True,
    }
    with pytest.raises(AttemptRecordInvariantError):
        _require_valid_removal_facts(facts)


def test_removal_facts_rejects_a_non_bool_result_shape_recognized() -> None:
    facts = {
        "result_shape_recognized": 1,
        "removed": True,
        "residual_file_count": 0,
        "verified": True,
    }
    with pytest.raises(AttemptRecordInvariantError):
        _require_valid_removal_facts(facts)


@pytest.mark.parametrize(
    "facts",
    [
        # genuine successful projection
        {
            "result_shape_recognized": True,
            "removed": True,
            "residual_file_count": 0,
            "verified": True,
        },
        # genuine residual (unverified but shape-recognized) projection
        {
            "result_shape_recognized": True,
            "removed": False,
            "residual_file_count": 2,
            "verified": True,
        },
        # genuine malformed-result projection: a partial dict recognized as
        # not matching the frozen shape, with only SOME fields still typed
        {
            "result_shape_recognized": False,
            "removed": True,
            "residual_file_count": None,
            "verified": None,
        },
        # genuine removal-exception / non-dict-result projection
        {
            "result_shape_recognized": False,
            "removed": None,
            "residual_file_count": None,
            "verified": None,
        },
    ],
)
def test_removal_facts_every_actually_producible_shape_is_accepted(facts: dict) -> None:
    """Positive control: every shape `_bounded_removal_facts` can actually
    produce -- successful, residual, malformed-result, and removal-exception
    -- is still accepted.
    """
    _require_valid_removal_facts(facts)


def test_genuine_indeterminate_attempt_with_verified_removal_still_builds(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    record = build_attempt_record(**kwargs)
    assert record["closure"]["semantic_workspace_removal"]["facts"] == dict(
        _REMOVAL_FACTS_VERIFIED_SHAPE
    )


def test_genuine_indeterminate_attempt_with_residual_removal_still_builds(
    git_executable: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive control: a genuine FAILED (residual) removal under an
    indeterminate dispatch still round-trips as a valid attempt.v1 artifact.
    """
    import json

    import qualification.semantic_controller as mod

    def _residual(workspace):
        return {"removed": False, "residual_file_count": 3, "verified": True}

    monkeypatch.setattr(mod, "remove_run_workspace", _residual)
    h = Harness("A", git_executable)
    _indeterminate(h)
    evidence_path = str(tmp_path / "genuine_residual.json")
    result = h.run(IQ1_TASK, evidence_path)
    assert result.workspace_removal.verified is False
    payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    facts = payload["closure"]["semantic_workspace_removal"]["facts"]
    assert facts == {
        "result_shape_recognized": True,
        "removed": False,
        "residual_file_count": 3,
        "verified": True,
    }
    # And it re-validates cleanly through the builder's own kwarg shape too.
    kwargs = dict(
        candidate=payload["candidate"],
        model_id=payload["model_id"],
        task_id=payload["task_id"],
        task_revision=payload["task_revision"],
        dispatch_evidence_code=SemanticDispatchEvidenceCode(payload["dispatch_evidence_code"]),
        gate_statuses=dict(payload["gate_statuses"]),
        observed_pi_version=payload["pi_runtime"]["observed_version"],
        compatibility_facts=dict(payload["pi_runtime"]["compatibility_facts"]),
        compatibility_gate_passed=payload["pi_runtime"]["compatibility_gate_passed"],
        route_provenance=dict(payload["route_provenance"]),
        closure=json.loads(json.dumps(payload["closure"])),
    )
    build_attempt_record(**kwargs)


def test_attempt_builder_rejects_verified_true_with_non_success_facts(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    closure = dict(kwargs["closure"])
    removal = dict(closure["semantic_workspace_removal"])
    removal["verified"] = True
    removal["facts"] = {
        "result_shape_recognized": True,
        "removed": False,
        "residual_file_count": 1,
        "verified": True,
    }
    closure["semantic_workspace_removal"] = removal
    kwargs["closure"] = closure
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


def test_attempt_builder_rejects_success_facts_with_verified_false(
    git_executable: str, tmp_path: Path
) -> None:
    kwargs = _genuine_indeterminate_attempt_kwargs(git_executable, tmp_path)
    closure = dict(kwargs["closure"])
    gate_statuses = dict(kwargs["gate_statuses"])
    gate_statuses["semantic_workspace_removal"] = (
        "FAILED:SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED_INDETERMINATE_DISPATCH"
    )
    kwargs["gate_statuses"] = gate_statuses
    removal = dict(closure["semantic_workspace_removal"])
    removal["verified"] = False
    # facts still exactly the success shape -- internally incoherent
    removal["facts"] = dict(_REMOVAL_FACTS_VERIFIED_SHAPE)
    closure["semantic_workspace_removal"] = removal
    closure["closure_established"] = False
    kwargs["closure"] = closure
    with pytest.raises(AttemptRecordInvariantError):
        build_attempt_record(**kwargs)


# ===========================================================================
# 4. FU1A-FU1: THE WHOLE AUTHORITY BUNDLE, REPLAYED TOGETHER, FROM ONE
#    FOREIGN GENUINE ATTEMPT OF THE SAME CANDIDATE/TASK
# ===========================================================================


def test_whole_authority_bundle_replayed_together_from_a_foreign_attempt_refused(
    git_executable: str, tmp_path: Path
) -> None:
    """The exact remaining bypass: ``qualification_record``,
    ``identity_provenance`` AND ``evidence_emission`` are ALL borrowed
    together from a DIFFERENT genuine successful A/IQ-1 attempt. The
    pairwise ``attempt_authority_token`` equality check alone is satisfied
    (all three share ONE mutually valid foreign token), so only the
    facts-fingerprint registry check can catch this.
    """
    failed = _run_genuine_scrub_refusal("A", IQ1_TASK, git_executable, tmp_path / "failed.json")
    success = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "success.json")

    # The trio is internally self-consistent -- it is success's own genuine
    # record/identity/emission, unmodified.
    with pytest.raises(ValueError):
        replace(
            failed,
            qualification_record=success.qualification_record,
            identity_provenance=success.identity_provenance,
            evidence_emission=success.evidence_emission,
        )


def test_whole_authority_bundle_replay_in_the_other_direction_also_refused(
    git_executable: str, tmp_path: Path
) -> None:
    """The reverse graft: attach the SCRUB-REFUSED attempt's own genuine
    bundle onto the SUCCESSFUL attempt's other facts. Still refused -- the
    fingerprint registered for the refused attempt's token was built from
    its OWN (refused) gate chronology, which the successful attempt's
    current facts do not match.
    """
    failed = _run_genuine_scrub_refusal("A", IQ1_TASK, git_executable, tmp_path / "failed.json")
    success = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "success.json")

    with pytest.raises(ValueError):
        replace(
            success,
            qualification_record=failed.qualification_record,
            identity_provenance=failed.identity_provenance,
            evidence_emission=failed.evidence_emission,
        )


def test_own_whole_bundle_replayed_onto_itself_no_longer_succeeds(
    git_executable: str, tmp_path: Path
) -> None:
    """5F3B-Q1-PRE1-FINAL-CLOSURE (required regression 3): reusing a genuine
    result's OWN ``identity_provenance``/``evidence_emission``/
    ``qualification_record`` to construct a SECOND
    ``SemanticTaskAttemptResult`` is refused, because the issuance was
    already consumed by the FIRST (the genuine) construction -- even though
    every bundle field is byte-for-byte identical to what it was originally
    minted for, and even though nothing about candidate/task/other facts
    changed at all.
    """
    result = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "ok.json")
    assert result.evidence_emission.refused is False
    with pytest.raises(ValueError):
        replace(
            result,
            qualification_record=result.qualification_record,
            identity_provenance=result.identity_provenance,
            evidence_emission=result.evidence_emission,
        )


# ===========================================================================
# 5. FU1A-FU1: THE LAST _bounded_removal_facts PROJECTION-DOMAIN GAP
# ===========================================================================


def test_removal_facts_rejects_recognized_false_with_all_three_fields_non_none() -> None:
    """``result_shape_recognized: False`` can only happen because at least
    one of the three required keys was absent from the underlying removal
    result -- and that key's own projected field is always None.
    ``_bounded_removal_facts`` can never produce all three non-None while
    also reporting recognition failure.
    """
    facts = {
        "result_shape_recognized": False,
        "removed": True,
        "residual_file_count": 0,
        "verified": True,
    }
    with pytest.raises(AttemptRecordInvariantError):
        _require_valid_removal_facts(facts)


# ===========================================================================
# 6. FINAL-CLOSURE: ONE-SHOT RESULT AUTHORITY ISSUANCE
# ===========================================================================


def test_stronger_replay_with_copied_gate_statuses_is_still_refused(
    git_executable: str, tmp_path: Path
) -> None:
    """Required regression 1 -- the exact stronger replay: for two
    otherwise-identical correct A/IQ-1 attempts, the remaining fingerprinted
    fields (``dispatch_state``, ``run_validity``, ``scoring_eligible``,
    ``autonomous_classification``, ``diagnostic_subclassification``,
    ``verification_passed``, ``semantic_prompts_sent``) are equal; copying
    the foreign attempt's OWN ``gate_statuses`` (its
    ``EVIDENCE_SAFETY`` entry included) alongside the borrowed bundle makes
    the re-derived fingerprint match the foreign token's registered one too.
    The one-shot issuance still refuses it: ``success``'s token was already
    consumed by ``success``'s OWN genuine construction, so it is not even
    pending here.
    """
    failed = _run_genuine_scrub_refusal("A", IQ1_TASK, git_executable, tmp_path / "failed.json")
    success = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "success.json")

    with pytest.raises(ValueError):
        replace(
            failed,
            qualification_record=success.qualification_record,
            identity_provenance=success.identity_provenance,
            evidence_emission=success.evidence_emission,
            gate_statuses=success.gate_statuses,
        )


def test_entire_foreign_result_field_set_cannot_reuse_its_consumed_issuance(
    git_executable: str, tmp_path: Path
) -> None:
    """Required regression 2: reconstructing a SECOND
    ``SemanticTaskAttemptResult`` from the ENTIRE caller-visible field set of
    a DIFFERENT genuine result -- not just the authority bundle, EVERY
    field -- still fails, because ``success``'s issuance was already
    consumed by ``success``'s own original construction. There is no field
    combination that can revive it.
    """
    failed = _run_genuine_scrub_refusal("A", IQ1_TASK, git_executable, tmp_path / "failed.json")
    success = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "success.json")

    every_field_of_success = {f.name: getattr(success, f.name) for f in fields(success)}
    with pytest.raises(ValueError):
        replace(failed, **every_field_of_success)


def test_normal_controller_produced_result_still_constructs_successfully(
    git_executable: str, tmp_path: Path
) -> None:
    """Required regression 4: a normal, genuine, controller-produced
    construction -- the ONE construction `run_semantic_task_attempt` itself
    performs -- still succeeds without exception, for both a successful and
    a scrub-refused attempt.
    """
    success = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "success.json")
    assert success.evidence_emission.refused is False
    failed = _run_genuine_scrub_refusal("A", IQ1_TASK, git_executable, tmp_path / "failed.json")
    assert failed.evidence_emission.refused is True


def test_genuine_run_consumes_exactly_one_pending_issuance_and_leaves_none_behind(
    git_executable: str, tmp_path: Path
) -> None:
    """Required regressions 5 and 7: every genuine run registers and then
    consumes EXACTLY one pending issuance -- after
    ``run_semantic_task_attempt`` returns, its own token is no longer
    present in the pending-issuance registry at all, so no entry remains as
    reusable construction authority.
    """
    import qualification.semantic_controller as mod

    before = dict(mod._PENDING_ATTEMPT_AUTHORITY)
    result = _run_genuine_success("A", IQ1_TASK, git_executable, tmp_path / "ok.json")
    after = dict(mod._PENDING_ATTEMPT_AUTHORITY)
    # No NEW pending entry was left behind by this run -- the one it
    # registered was consumed by its own construction before returning.
    assert after == before
    assert result.identity_provenance.attempt_authority_token not in after


def test_mismatched_consumption_permanently_burns_the_token(
    git_executable: str, tmp_path: Path
) -> None:
    """Required regression 6: a failed/mismatched consumption attempt cannot
    turn a pending issuance back into reusable authority for a LATER,
    correctly-matching attempt -- the entry is deleted as part of the SAME
    atomic step regardless of whether the match succeeds, so once ANY
    consumption attempt (successful or not) has run against a token, no
    subsequent attempt -- even one with the exact fingerprint the token was
    genuinely registered under -- can ever consume it again.

    Exercises the registry's own two package-internal functions directly
    (mirroring how this suite already tests other package-internal
    invariant helpers, e.g. ``_require_valid_removal_facts``), since normal
    ``run_semantic_task_attempt`` flow never leaves a window between
    registration and its own genuine consumption for an external mismatched
    attempt to land in between.
    """
    import qualification.semantic_controller as mod

    token = f"final-closure-test-token-{id(object())}"
    fingerprint = "genuinely-expected-fingerprint"
    mod._register_attempt_authority(token, fingerprint)

    with pytest.raises(ValueError):
        mod._consume_pending_attempt_authority(token, "wrong-fingerprint")

    # The token is now permanently burned -- even the ORIGINALLY correct
    # fingerprint can no longer consume it.
    with pytest.raises(ValueError):
        mod._consume_pending_attempt_authority(token, fingerprint)
    assert token not in mod._PENDING_ATTEMPT_AUTHORITY
