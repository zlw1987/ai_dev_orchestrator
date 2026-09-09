"""5F3B-LIVE1-C4 -- qualification-record policy binding.

**OFFLINE ONLY.** No semantic prompt, no Pi/Node launch, no model call, no
socket, no credential read, no real workspace. Every repository these tests
touch is a synthetic one built under pytest ``tmp_path`` by the existing
offline harness.

What C4 changed, and therefore what this module proves
------------------------------------------------------

C4 gives every durable per-result implementer qualification artifact a
self-describing binding to the qualification policy under which its verdicts
were produced (design ``PHASE_5F3B_LIVE1_PI_SEMANTIC_LIVE_LAYER_DESIGN.md``
Sec. 10A.2b / Sec. 10A.2c, Sec. 18.2/18.3/18.5)::

    QUALIFICATION_POLICY_REVISION     ONE declaration site, qualification/__init__.py
        -> pi-implementer-qualification.v2           carries it
        -> pi-implementer-qualification-attempt.v2   carries it
        -> pi-implementer-qualification-refusal.v2   carries it as FIXED METADATA

This is **policy provenance, not ranking**: no run validity, scoring
eligibility, classification, hard bar, refusal attribution, R-1..R-4 rule or
comparison semantic changed. C4 itself does not implement C3's ranking
mechanics.

The adversarial question this module answers mechanically
----------------------------------------------------------

    Can a SUPPORTED caller make a retained primary, attempt, or refusal
    artifact claim a policy revision that AIDO did not declare?

The answer must be NO, and it is proven three independent ways for the two
``**extra``-accepting header builders (caller-key refusal, dict-merge stamp
order, emission-boundary re-derivation) and structurally for the refusal
record, whose signature admits no payload at all.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from qualification import (
    ATTEMPT_RECORD_VERSION,
    FIXTURE_SCHEMA_VERSION,
    LINEAGE_RECORD_VERSION,
    QUALIFICATION_POLICY_REVISION,
    RECORD_VERSION,
    REFUSAL_RECORD_VERSION,
)
from qualification import records as records_module
from qualification import semantic_attempt as semantic_attempt_module
from qualification.corpus import IQ1_TASK
from qualification.lineage import (
    FIXTURE_OR_PROMPT_DEFECT,
    build_invalidation_evidence,
    write_invalidation_evidence,
)
from qualification.records import (
    RECORD_KIND,
    RecordInvariantError,
    build_qualification_record,
    emit_or_refuse,
    record_header,
)
from qualification.safety import (
    ArtifactSafetyContext,
    build_refusal_record,
    emit_evidence_or_refuse,
    qualification_scrub_check,
)
from qualification.semantic_attempt import (
    ATTEMPT_RECORD_KIND,
    AttemptRecordInvariantError,
    _EXPECTED_ATTEMPT_RECORD_TOP_LEVEL_KEYS,
    attempt_record_header,
    build_attempt_record,
    emit_attempt_or_refuse,
)
from qualification.semantic_session import (
    SemanticDispatchEvidenceCode,
    SemanticPromptDispatchState,
)

from test_semantic_controller import Harness

NO_SECRETS = ArtifactSafetyContext.none_declared()

_QUALIFICATION_DIR = Path(records_module.__file__).resolve().parent
_EXPERIMENTS_DIR = _QUALIFICATION_DIR.parents[1]
_REPO_ROOT = _EXPERIMENTS_DIR.parent
_SRC_DIR = _REPO_ROOT / "src"

#: The FOUR production modules C4 is authorized to touch.
_C4_AUTHORIZED_MODULES: frozenset[str] = frozenset(
    {"__init__.py", "records.py", "semantic_attempt.py", "safety.py"}
)

#: The pre-C4 refusal-record key set, written out by hand so the "gained
#: EXACTLY one field" claim is a comparison against a recorded fact rather
#: than against whatever the current builder happens to produce.
_PRE_C4_REFUSAL_KEYS: frozenset[str] = frozenset(
    {
        "experiment",
        "record_version",
        "record_kind",
        "refused_record_kind",
        "is_review_packet",
        "reviewer_invoked",
        "outcome",
        "scrub_checked",
        "candidate_artifact_not_emitted",
        "finding_count",
        "finding_categories",
    }
)

#: The pre-C4 attempt-artifact closed top-level key set, likewise recorded by
#: hand: 8 fixed header keys + 24 ``build_attempt_record`` extras.
_PRE_C4_ATTEMPT_KEYS: frozenset[str] = frozenset(
    {
        "experiment",
        "record_version",
        "fixture_schema_version",
        "record_kind",
        "is_review_packet",
        "reviewer_invoked",
        "external_prior_not_scored",
        "trust_namespaces",
        "candidate",
        "model_id",
        "task_id",
        "task_revision",
        "semantic_dispatch_state",
        "dispatch_evidence_code",
        "semantic_prompts_sent_established",
        "attempt_consumed",
        "qualification_record_emitted",
        "scoring_eligible",
        "run_validity",
        "autonomous_classification",
        "diagnostic_subclassification",
        "hard_bar_evaluable",
        "operator_continuation",
        "automatic_semantic_retry",
        "pi_runtime",
        "route_provenance",
        "gate_statuses",
        "closure",
        "cleanup_classification_unavailable_reason",
        "workspace_removal_classification_unavailable_reason",
        "token_policy",
        "claim_scope",
    }
)

_FORGED = "forged-policy-revision-that-aido-never-declared"


def _production_qualification_sources() -> list[Path]:
    return sorted(p for p in _QUALIFICATION_DIR.glob("*.py"))


def _minimal_primary_record(**overrides) -> dict:
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
        route_provenance={"model_id": "qwen3-coder-next"},
        verification={"passed": True},
        scope_result={"hard_refusal_count": 0},
        report_accuracy={"bucket": "ACCURATE"},
    )
    base.update(overrides)
    return build_qualification_record(**base)


def _genuine_attempt_record(git_executable: str, tmp_path: Path) -> dict:
    """One REAL indeterminate-dispatch attempt artifact, produced by the
    frozen controller against a synthetic repository under ``tmp_path``.

    No Pi process, no network, no model: the harness's dispatch adapter is a
    synthetic double that raises, exactly as the existing offline suite does.
    """
    harness = Harness("A", git_executable)
    harness.dispatch_semantic_prompt = lambda request: (_ for _ in ()).throw(
        ConnectionResetError("wire dropped after (maybe) writing the request")
    )
    evidence_path = str(tmp_path / "genuine_attempt.json")
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    return json.loads(Path(evidence_path).read_text(encoding="utf-8"))


# ===========================================================================
# A. DECLARATION SITE AND VERSION CONSTANTS  (C4-1, C4-2)
# ===========================================================================


def test_exactly_one_policy_revision_declaration_site_in_production_code():
    """C4-1 / counterexamples 5, 6, 12: one authority, never two literals.

    Two declaration sites is exactly how the primary record, the attempt
    record and the refusal record could come to disagree about the policy
    they were produced under, and how C3 could later rank against a revision
    no artifact carries.
    """
    sites: list[tuple[str, ast.AST]] = []
    for source_path in _production_qualification_sources():
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            else:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "QUALIFICATION_POLICY_REVISION":
                    sites.append((source_path.name, value))

    assert len(sites) == 1, f"expected exactly one declaration site, found: {sites}"
    assert sites[0][0] == "__init__.py"


def test_the_policy_revision_is_a_plain_declared_string_literal():
    """C4-1 / counterexample 12: declared, never computed.

    A computed identifier (a source hash, a Git SHA, a date) changes on every
    refactor and silently stops meaning "the policy changed".
    """
    tree = ast.parse(
        (_QUALIFICATION_DIR / "__init__.py").read_text(encoding="utf-8"),
        filename="__init__.py",
    )
    values = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "QUALIFICATION_POLICY_REVISION"
    ]
    assert len(values) == 1
    value = values[0]
    assert isinstance(value, ast.Constant), f"not a literal: {ast.dump(value)}"
    assert isinstance(value.value, str)
    assert value.value == QUALIFICATION_POLICY_REVISION
    assert value.value.strip() == value.value
    assert value.value.isascii()
    assert value.value


def test_the_declaration_module_computes_nothing_at_all():
    """C4-1: independent of environment, filesystem, Git, clock and digests.

    Proven structurally rather than by inspecting the value: the declaration
    module contains NO call, NO attribute access, NO subscript, NO name read
    and NO import other than ``from __future__``. There is therefore no
    expression in it through which ``os.environ``, ``subprocess``,
    ``datetime``, ``hashlib`` or a file read could reach any constant.
    """
    tree = ast.parse(
        (_QUALIFICATION_DIR / "__init__.py").read_text(encoding="utf-8"),
        filename="__init__.py",
    )
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.Call, ast.Attribute, ast.Subscript)), ast.dump(node)
        assert not isinstance(node, ast.Import), ast.dump(node)
        if isinstance(node, ast.ImportFrom):
            assert node.module == "__future__", ast.dump(node)


def test_the_three_per_result_versions_are_bumped_to_v2():
    """C4-2, and counterexample 8: the field never ships under a ``.v1``."""
    assert RECORD_VERSION == "pi-implementer-qualification.v2"
    assert ATTEMPT_RECORD_VERSION == "pi-implementer-qualification-attempt.v2"
    assert REFUSAL_RECORD_VERSION == "pi-implementer-qualification-refusal.v2"


def test_the_fixture_and_lineage_versions_are_not_bumped():
    """C4-2: exactly three lineages move; no other schema/version is created."""
    assert FIXTURE_SCHEMA_VERSION == "pi-implementer-qualification-fixture.v1"
    assert LINEAGE_RECORD_VERSION == "pi-implementer-qualification-lineage.v1"


def test_the_policy_revision_is_not_a_schema_version():
    """C4-2: ``record_version`` answers "what SHAPE"; this answers "what POLICY".

    They sit side by side in every emitted artifact, so a spelling either one
    could be mistaken for is a defect. Neither may substitute for the other.
    """
    schema_versions = {
        RECORD_VERSION,
        ATTEMPT_RECORD_VERSION,
        REFUSAL_RECORD_VERSION,
        FIXTURE_SCHEMA_VERSION,
        LINEAGE_RECORD_VERSION,
    }
    assert QUALIFICATION_POLICY_REVISION not in schema_versions
    assert not QUALIFICATION_POLICY_REVISION.endswith(".v1")
    assert not QUALIFICATION_POLICY_REVISION.endswith(".v2")


# ===========================================================================
# B. PRIMARY RECORD HEADER  (C4-3)
# ===========================================================================


def test_record_header_carries_the_declared_policy_revision():
    header = record_header()
    assert header["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert header["record_version"] == RECORD_VERSION


def test_a_built_primary_record_carries_both_the_v2_version_and_the_revision():
    """Counterexamples 7 and 8: never a ``.v2`` without the field, and never
    the field without the ``.v2``."""
    record = _minimal_primary_record()
    assert record["record_version"] == "pi-implementer-qualification.v2"
    assert record["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION


def test_record_header_refuses_a_caller_supplied_policy_revision():
    """Counterexample 1: forged header extra, primary record. Layer 1."""
    with pytest.raises(RecordInvariantError):
        record_header(qualification_policy_revision=_FORGED)


def test_build_qualification_record_cannot_be_handed_a_policy_revision():
    """The builder's own signature has no such parameter, so the only route in
    would be ``record_header``'s ``**extra`` -- already refused above."""
    parameters = inspect.signature(build_qualification_record).parameters
    assert "qualification_policy_revision" not in parameters
    assert not any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )


def test_record_header_stamps_the_constant_after_extras_even_if_the_guard_is_removed(
    monkeypatch,
):
    """Counterexample 13, primary: the SECOND, independent defence.

    The guard above is layer 1. Layer 2 is dict-merge order: the
    authoritative constant is written AFTER ``**extra`` in the header
    literal, so the last write -- AIDO's -- wins. Neutralising the guard
    proves layer 2 holds on its own rather than being decorative.
    """
    monkeypatch.setattr(
        records_module, "_reject_caller_supplied_fixed_metadata", lambda extra: None
    )
    header = records_module.record_header(qualification_policy_revision=_FORGED)
    assert header["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert _FORGED not in json.dumps(header)


# ===========================================================================
# C. ATTEMPT RECORD HEADER  (C4-4)
# ===========================================================================


def test_attempt_record_header_carries_the_same_declared_policy_revision():
    """Counterexample 5: the two builders read ONE constant, not two literals."""
    header = attempt_record_header()
    assert header["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert header["qualification_policy_revision"] == (
        record_header()["qualification_policy_revision"]
    )
    assert header["record_version"] == "pi-implementer-qualification-attempt.v2"


def test_attempt_record_header_refuses_a_caller_supplied_policy_revision():
    """Counterexample 2: forged header extra, attempt record. Layer 1."""
    with pytest.raises(AttemptRecordInvariantError):
        attempt_record_header(qualification_policy_revision=_FORGED)


def test_attempt_record_header_stamps_the_constant_after_extras_even_if_guard_removed(
    monkeypatch,
):
    """Counterexample 13, attempt: the SECOND, independent defence."""
    monkeypatch.setattr(
        semantic_attempt_module, "_reject_caller_supplied_fixed_metadata", lambda extra: None
    )
    header = semantic_attempt_module.attempt_record_header(
        qualification_policy_revision=_FORGED
    )
    assert header["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert _FORGED not in json.dumps(header)


def test_the_two_header_builders_protect_the_same_key_set():
    """Counterexample 14: one protected-key set, imported, never re-listed.

    (The set's exact membership -- widened by C4-FU1 to the ``.v2`` metadata
    PAIR -- is pinned in section I.)
    """
    assert (
        semantic_attempt_module._CALLER_FORBIDDEN_HEADER_KEYS
        is records_module._CALLER_FORBIDDEN_HEADER_KEYS
    )
    assert "qualification_policy_revision" in records_module._CALLER_FORBIDDEN_HEADER_KEYS


def test_attempt_closed_key_set_admits_exactly_the_one_new_field():
    """C4-4 / counterexample 9: an enumeration of one more permitted field,
    never a relaxation of the closed-shape rule."""
    assert _EXPECTED_ATTEMPT_RECORD_TOP_LEVEL_KEYS == (
        _PRE_C4_ATTEMPT_KEYS | {"qualification_policy_revision"}
    )
    assert len(_EXPECTED_ATTEMPT_RECORD_TOP_LEVEL_KEYS) == len(_PRE_C4_ATTEMPT_KEYS) + 1


def test_a_genuine_attempt_artifact_carries_the_revision_and_the_v2_version(
    git_executable: str, tmp_path: Path
):
    payload = _genuine_attempt_record(git_executable, tmp_path)
    assert payload["record_version"] == "pi-implementer-qualification-attempt.v2"
    assert payload["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert set(payload) == _EXPECTED_ATTEMPT_RECORD_TOP_LEVEL_KEYS


def test_the_attempt_artifact_still_cannot_carry_semantic_prompts_sent(
    git_executable: str, tmp_path: Path
):
    """C4-4: every frozen semantic-attempt invariant survives the bump.

    The frozen rule is about the KEY, at any depth -- ``semantic_prompts_sent``
    must be ABSENT, never ``null``, ``0`` or a sentinel. (A substring check
    would be wrong here: ``semantic_prompts_sent_established`` legitimately
    contains it.)
    """
    payload = _genuine_attempt_record(git_executable, tmp_path)
    assert not semantic_attempt_module._contains_key(payload, "semantic_prompts_sent")
    assert payload["semantic_prompts_sent_established"] is False


def test_the_attempt_closed_key_set_is_still_exact_and_closed(
    git_executable: str, tmp_path: Path
):
    """C4-4 / counterexample 9: not weakened. An unknown extra key is still
    refused, and a missing key is still refused."""
    payload = _genuine_attempt_record(git_executable, tmp_path)

    widened = dict(payload)
    widened["semantic_prompt_definitely_sent"] = True
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            widened, path=str(tmp_path / "widened.json"), safety=NO_SECRETS
        )

    narrowed = dict(payload)
    del narrowed["qualification_policy_revision"]
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(
            narrowed, path=str(tmp_path / "narrowed.json"), safety=NO_SECRETS
        )

    assert not (tmp_path / "widened.json").exists()
    assert not (tmp_path / "narrowed.json").exists()


def test_emit_attempt_refuses_a_hand_tampered_policy_revision(
    git_executable: str, tmp_path: Path
):
    """Counterexamples 13 and 14: the THIRD, independent defence.

    A hand-built dict handed straight to ``emit_attempt_or_refuse`` never met
    ``attempt_record_header``'s guard at all. The emission boundary
    re-derives the fixed value from the declaration site and refuses.
    """
    payload = _genuine_attempt_record(git_executable, tmp_path)
    tampered = dict(payload)
    tampered["qualification_policy_revision"] = _FORGED
    target = tmp_path / "tampered_revision.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(tampered, path=str(target), safety=NO_SECRETS)
    assert not target.exists()


def test_build_attempt_record_cannot_be_handed_a_policy_revision():
    parameters = inspect.signature(build_attempt_record).parameters
    assert "qualification_policy_revision" not in parameters
    assert not any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )


# ===========================================================================
# D. SAFETY-REFUSAL ARTIFACT  (C4-5)
# ===========================================================================


def _sample_refusal() -> dict:
    return build_refusal_record(
        refused_record_kind=RECORD_KIND,
        finding_count=1,
        finding_categories=["ipv4_literal_present"],
    )


def test_refusal_record_is_v2_and_carries_the_declared_policy_revision():
    refusal = _sample_refusal()
    assert refusal["record_version"] == "pi-implementer-qualification-refusal.v2"
    assert refusal["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION


def test_refusal_record_key_set_is_the_old_set_plus_exactly_one_field():
    """C4-5 / counterexample 10: the refusal artifact's closed shape."""
    assert set(_sample_refusal()) == _PRE_C4_REFUSAL_KEYS | {"qualification_policy_revision"}
    assert len(_sample_refusal()) == len(_PRE_C4_REFUSAL_KEYS) + 1


def test_refusal_record_gained_no_candidate_model_task_path_or_runtime_field():
    """C4-5: named explicitly, so a later widening cannot slip in beside the
    one authorized field."""
    refusal = _sample_refusal()
    for forbidden in (
        "candidate",
        "model_id",
        "task_id",
        "task_revision",
        "path",
        "workspace_root",
        "workspace_absolute_path",
        "prompt",
        "endpoint",
        "endpoint_host",
        "base_url",
        "api_key",
        "exception",
        "error",
        "traceback",
        "pi_runtime",
        "route_provenance",
        "closure",
        "gate_statuses",
    ):
        assert forbidden not in refusal


def test_build_refusal_record_has_no_parameter_through_which_a_payload_arrives():
    """Counterexamples 3 and 4, closed STRUCTURALLY.

    The builder's signature admits a kind string, a count and finding CODES
    -- and nothing else. There is no parameter through which the unsafe
    candidate's body, or a fake policy revision sitting inside it, could
    reach the retained refusal artifact.
    """
    parameters = inspect.signature(build_refusal_record).parameters
    assert set(parameters) == {
        "refused_record_kind",
        "finding_count",
        "finding_categories",
    }
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters.values()
    )


def test_refusal_record_passes_its_own_independent_scrub():
    """C4-5: the added literal is scrub-safe by construction."""
    check = qualification_scrub_check(_sample_refusal(), NO_SECRETS)
    assert check["clean"] is True
    assert check["findings"] == []


def test_the_declared_revision_survives_a_hostile_safety_context():
    """The revision is a fixed literal, so it is never itself a declared
    secret needle; a caller cannot make the refusal artifact unemittable by
    declaring the revision as sensitive."""
    check = qualification_scrub_check(
        _sample_refusal(), ArtifactSafetyContext(endpoint_host="synthetic-host.invalid")
    )
    assert check["clean"] is True


# ===========================================================================
# E. EMISSION PATH  (C4-5, C4-6)
# ===========================================================================


def test_a_scrub_clean_primary_record_emits_normally_with_the_revision(tmp_path: Path):
    target = tmp_path / "primary.json"
    result = emit_or_refuse(_minimal_primary_record(), path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["record_version"] == "pi-implementer-qualification.v2"
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION


def test_a_scrub_clean_attempt_record_emits_normally_with_the_revision(
    git_executable: str, tmp_path: Path
):
    payload = _genuine_attempt_record(git_executable, tmp_path)
    target = tmp_path / "attempt_reemitted.json"
    result = emit_attempt_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION


def test_emit_or_refuse_refuses_a_hand_built_primary_record_with_a_forged_revision(
    tmp_path: Path,
):
    """SELF-REVIEW FINDING (counterexamples 13/14, primary path).

    Found by probing the shipped API rather than by re-reading the checklist:
    ``records.emit_or_refuse`` accepted an arbitrary scrub-clean dict and
    persisted it verbatim. A hand-built payload that never passed through
    ``record_header`` -- and so never met its protected-key guard -- could
    therefore be retained claiming ``"FORGED-BY-CALLER"``, even though the
    attempt path had refused exactly this since FU2A.

    The primary emission boundary now re-derives the declared constant. This
    is the regression.
    """
    forged = {
        "experiment": "pi_implementer_qualification",
        "record_version": RECORD_VERSION,
        "record_kind": RECORD_KIND,
        "candidate": "A",
        "qualification_policy_revision": _FORGED,
    }
    target = tmp_path / "forged_primary.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    assert not target.exists()


def test_emit_or_refuse_refuses_a_v2_primary_record_carrying_no_revision_at_all(
    tmp_path: Path,
):
    """Counterexample 7: ``.v2`` present, policy revision absent.

    The same emission-boundary check closes this too -- a record cannot claim
    the schema revision that MEANS "carries a policy binding" while carrying
    none.
    """
    unbound = _minimal_primary_record()
    del unbound["qualification_policy_revision"]
    target = tmp_path / "unbound_primary.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(unbound, path=str(target), safety=NO_SECRETS)
    assert not target.exists()


def test_emit_or_refuse_refuses_the_declared_revision_paired_with_a_stale_v1(
    tmp_path: Path,
):
    """Counterexample 8: the revision present, the version still ``.v1``.

    ``.v1``'s frozen meaning is *a record carrying no policy-revision
    binding*, so the two may not be emitted in disagreement. The bump and the
    field are one fact.
    """
    stale = _minimal_primary_record()
    stale["record_version"] = "pi-implementer-qualification.v1"
    target = tmp_path / "stale_v1.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(stale, path=str(target), safety=NO_SECRETS)
    assert not target.exists()


def test_emit_or_refuse_refuses_an_equality_coercing_revision_lookalike(
    tmp_path: Path,
):
    """Counterexample 13: a Python truthiness/coercion path.

    An equality-only check can be satisfied by a ``str`` subclass with a
    custom ``__eq__`` -- the same class of bypass an equality-only bool check
    has with ``0``/``1``. The emission boundary type-checks as well.
    """

    class AlwaysEqual(str):
        def __eq__(self, other):  # noqa: D105 - the bypass under test
            return True

        def __ne__(self, other):
            return False

        def __hash__(self):
            return hash(str(self))

    lookalike = _minimal_primary_record()
    lookalike["qualification_policy_revision"] = AlwaysEqual(_FORGED)
    target = tmp_path / "lookalike.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(lookalike, path=str(target), safety=NO_SECRETS)
    assert not target.exists()


def test_a_scrub_rejected_payload_yields_a_refusal_carrying_the_DECLARED_revision(
    tmp_path: Path,
):
    """Counterexamples 3 and 4, closed BEHAVIOURALLY.

    The unsafe payload deliberately carries an attacker-authored
    ``qualification_policy_revision`` of its own, plus a real scrub trigger.
    The retained refusal must carry only AIDO's declared constant, and the
    forged value must not appear on disk anywhere.
    """
    unsafe = {
        "record_kind": RECORD_KIND,
        "qualification_policy_revision": _FORGED,
        "leak": "the reviewer endpoint is at 203.0.113.7 and must never be retained",
    }
    target = tmp_path / "refused.json"
    result = emit_evidence_or_refuse(
        unsafe, path=str(target), safety=NO_SECRETS, record_kind=RECORD_KIND
    )
    assert result["refused"] is True
    assert "ipv4_literal_present" in result["scrub"]["findings"]

    on_disk = target.read_text(encoding="utf-8")
    written = json.loads(on_disk)

    # The refusal artifact is what was retained -- never the unsafe payload.
    assert written["record_version"] == "pi-implementer-qualification-refusal.v2"
    assert written["outcome"] == "artifact_emission_refused"
    assert written["candidate_artifact_not_emitted"] is True
    assert "leak" not in written
    assert "203.0.113.7" not in on_disk

    # ...and it carries AIDO's DECLARED revision, not the payload's.
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert _FORGED not in on_disk

    # The retained refusal is itself scrub-clean.
    assert qualification_scrub_check(written, NO_SECRETS)["clean"] is True


def test_a_scrub_rejected_attempt_payload_yields_the_same_bound_refusal(tmp_path: Path):
    unsafe = {
        "record_kind": ATTEMPT_RECORD_KIND,
        "qualification_policy_revision": _FORGED,
        "leak": "host 198.51.100.22",
    }
    target = tmp_path / "attempt_refused.json"
    result = emit_evidence_or_refuse(
        unsafe, path=str(target), safety=NO_SECRETS, record_kind=ATTEMPT_RECORD_KIND
    )
    assert result["refused"] is True
    on_disk = target.read_text(encoding="utf-8")
    written = json.loads(on_disk)
    assert written["refused_record_kind"] == ATTEMPT_RECORD_KIND
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert _FORGED not in on_disk


def test_emission_remains_exclusive_create_after_the_bump(tmp_path: Path):
    """C4-6: the choke point's frozen behaviour is untouched -- no overwrite,
    no append, no second output path."""
    from qualification.safety import EvidencePathCollisionError

    target = tmp_path / "once.json"
    emit_or_refuse(_minimal_primary_record(), path=str(target), safety=NO_SECRETS)
    first_bytes = target.read_bytes()
    with pytest.raises(EvidencePathCollisionError):
        emit_or_refuse(
            _minimal_primary_record(task_id="IQ-2", task_revision="IQ-2@aaaaaaaaaaaaaaaa"),
            path=str(target),
            safety=NO_SECRETS,
        )
    assert target.read_bytes() == first_bytes


# ===========================================================================
# F. ALL THREE ARTIFACT KINDS AGREE  (counterexample 14)
# ===========================================================================


def test_all_three_durable_artifact_kinds_carry_one_identical_revision(
    git_executable: str, tmp_path: Path
):
    primary = _minimal_primary_record()
    attempt = _genuine_attempt_record(git_executable, tmp_path)
    refusal = _sample_refusal()
    revisions = {
        primary["qualification_policy_revision"],
        attempt["qualification_policy_revision"],
        refusal["qualification_policy_revision"],
    }
    assert revisions == {QUALIFICATION_POLICY_REVISION}


# ===========================================================================
# G. LINEAGE IS UNTOUCHED AND STILL BINDS  (C4-7)
# ===========================================================================


def test_lineage_binds_a_genuine_v2_primary_record_without_any_lineage_edit(
    tmp_path: Path,
):
    """C4-7 / counterexample 11: no shim, no relaxation, no lineage edit."""
    old_path = str(tmp_path / "iq2_original.json")
    old_record = _minimal_primary_record(
        task_id="IQ-2", task_revision="IQ-2@original00000000"
    )
    assert old_record["record_version"] == "pi-implementer-qualification.v2"
    emit_or_refuse(old_record, path=old_path, safety=NO_SECRETS)

    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-2@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        corrected_task_revision="IQ-2@corrected0000000",
    )
    write_invalidation_evidence(
        evidence, path=str(tmp_path / "iq2_lineage.json"), safety=NO_SECRETS
    )
    assert evidence["invalidated_task_revision"] == "IQ-2@original00000000"


def test_the_lineage_artifact_does_not_carry_the_policy_revision(tmp_path: Path):
    """C4-7: the field is added to the three per-result lineages and nowhere
    else. Lineage binds records by content digest and can read the revision
    from the record it binds."""
    old_path = str(tmp_path / "iq3_original.json")
    emit_or_refuse(
        _minimal_primary_record(task_id="IQ-3", task_revision="IQ-3@original00000000"),
        path=old_path,
        safety=NO_SECRETS,
    )
    evidence = build_invalidation_evidence(
        invalidated_record_path=old_path,
        invalidated_task_revision="IQ-3@original00000000",
        invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
        corrected_task_revision="IQ-3@corrected0000000",
    )
    assert "qualification_policy_revision" not in evidence
    assert evidence["record_version"] == LINEAGE_RECORD_VERSION


def test_lineage_reads_the_record_version_symbol_rather_than_a_stale_literal():
    """C4-7: proven from source. ``lineage.py`` contains NO
    ``pi-implementer-qualification*`` literal at all, so it cannot have been
    left pinned to ``.v1`` -- it follows whatever ``records.RECORD_VERSION``
    currently is, which is why it needed no edit."""
    source = (_QUALIFICATION_DIR / "lineage.py").read_text(encoding="utf-8")
    assert "pi-implementer-qualification" not in source
    assert "from .records import RECORD_KIND, RECORD_VERSION" in source


def test_lineage_still_refuses_a_record_at_the_superseded_v1_version(tmp_path: Path):
    """C4-2 / counterexample 8: ``.v1`` keeps its ORIGINAL meaning -- *a record
    with no durable qualification-policy-revision binding* -- and there is no
    compatibility shim that would silently read one as belonging to the new
    policy."""
    from qualification.lineage import LineageBindingError

    forged_v1 = _minimal_primary_record(
        task_id="IQ-2", task_revision="IQ-2@original00000000"
    )
    forged_v1["record_version"] = "pi-implementer-qualification.v1"
    forged_v1.pop("qualification_policy_revision")
    path = str(tmp_path / "hand_made_v1.json")
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(forged_v1, handle)

    with pytest.raises(LineageBindingError):
        build_invalidation_evidence(
            invalidated_record_path=path,
            invalidated_task_revision="IQ-2@original00000000",
            invalidation_reason=FIXTURE_OR_PROMPT_DEFECT,
            corrected_task_revision="IQ-2@corrected0000000",
        )


# ===========================================================================
# H. SCOPE  (C4-6, C4-7, C4-8, and the prohibited-work list)
# ===========================================================================


def test_the_policy_revision_appears_only_in_the_authorized_modules():
    """Mechanical scope proof, independent of VCS state.

    If a production qualification module outside this set had been edited to
    mention the revision -- ``lineage.py`` for a shim,
    ``semantic_controller.py`` for a projection -- this fails.

    **Updated when 5F3B-LIVE1-C3 landed.** ``ranking.py`` now legitimately
    CONSUMES the constant at the ranking boundary (design Sec. 10A.3 C3-PR-1/2),
    which is exactly the ordering C4 was built for: C4 declares it and writes it
    into retained artifacts; C3 imports it and refuses across revisions. It is
    listed separately from ``_C4_AUTHORIZED_MODULES`` so this test still proves
    C4's own scope, and
    :func:`test_exactly_one_policy_revision_declaration_site_in_production_code`
    (unchanged) still proves ranking declares no second literal.
    """
    mentioning = {
        source_path.name
        for source_path in _production_qualification_sources()
        if "qualification_policy_revision" in source_path.read_text(encoding="utf-8").lower()
    }
    assert mentioning == _C4_AUTHORIZED_MODULES | {"ranking.py"}


def test_c4_did_not_implement_c3s_ranking_mechanics():
    """Prohibited work for C4: C3 owns the ranking-policy mechanics.

    Originally written as ``test_c3_is_not_implemented_here``, asserting
    ``ranking.py`` mentioned the revision nowhere. C3 has since landed and does
    consume it, so that spelling would now assert C3's absence rather than C4's
    restraint. The property C4 actually owns is preserved and still checked
    here: **none of C4's four authorized modules contains ranking mechanics** --
    no R-2 derivation, no R-3 symmetry, no profile comparison.
    """
    for module_name in sorted(_C4_AUTHORIZED_MODULES):
        source = (_QUALIFICATION_DIR / module_name).read_text(encoding="utf-8")
        for token in (
            "from .ranking",
            "OperationBucket",
            "ReportAccuracyBucket",
            "CandidateRankingProfile",
            "RankingInput",
            "R2TaskEvidence",
            "resolve_r2_bucket",
            "compare_profiles",
            "build_profile",
            "R3_EVALUABLE",
        ):
            assert token not in source, f"{module_name} carries ranking mechanics: {token!r}"


def test_no_ar2_or_production_src_module_mentions_the_policy_revision():
    """The revision is this experiment's own policy identity. Nothing under
    ``ar2/`` or ``src/`` is touched by C4."""
    scanned = 0
    for root in (_EXPERIMENTS_DIR / "pi_external_runtime_ar2" / "ar2", _SRC_DIR):
        for source_path in root.rglob("*.py"):
            scanned += 1
            text = source_path.read_text(encoding="utf-8", errors="replace")
            assert "qualification_policy_revision" not in text.lower(), source_path
    assert scanned > 0


def test_no_new_artifact_kind_was_added():
    """Prohibited work: C4 is policy provenance on THREE EXISTING lineages --
    no new artifact kind, no sweep artifact, no candidate-level decision
    artifact."""
    package_source = (_QUALIFICATION_DIR / "__init__.py").read_text(encoding="utf-8")
    version_assignments = {
        target.id
        for node in ast.walk(ast.parse(package_source))
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id.endswith("_VERSION")
    }
    assert version_assignments == {
        "RECORD_VERSION",
        "FIXTURE_SCHEMA_VERSION",
        "LINEAGE_RECORD_VERSION",
        "REFUSAL_RECORD_VERSION",
        "ATTEMPT_RECORD_VERSION",
    }


def test_c4_changed_no_policy_behaviour(git_executable: str, tmp_path: Path):
    """C4-8: provenance/schema only.

    A genuine indeterminate attempt still classifies exactly as before --
    unestablished send state, attempt consumed, no scoring eligibility, no
    hard-bar evaluability, no classification, no retry authority.
    """
    payload = _genuine_attempt_record(git_executable, tmp_path)
    assert payload["semantic_dispatch_state"] == "SEND_STATE_INDETERMINATE"
    assert payload["semantic_prompts_sent_established"] is False
    assert payload["attempt_consumed"] is True
    assert payload["qualification_record_emitted"] is False
    assert payload["scoring_eligible"] is False
    assert payload["run_validity"] is None
    assert payload["autonomous_classification"] is None
    assert payload["diagnostic_subclassification"] is None
    assert payload["hard_bar_evaluable"] is False
    assert payload["operator_continuation"] is False
    assert payload["automatic_semantic_retry"] is False
    assert payload["token_policy"]["aido_requested_max_output_tokens"] is None
    assert (
        SemanticDispatchEvidenceCode(payload["dispatch_evidence_code"])
        in semantic_attempt_module.INDETERMINATE_EVIDENCE_CODES
    )


# ===========================================================================
# I. 5F3B-LIVE1-C4-FU1 -- DURABLE-RECORD CONSUMPTION-BOUNDARY CLOSURE
# ===========================================================================
# Independent review found three concrete authority bypasses in C4 as first
# implemented. Everything below is a regression against one of them:
#
#   Finding 1  attempt policy-revision type-confusion (a `str` subclass whose
#              underlying content is forged but whose equality pretends to
#              match the declared revision)
#   Finding 2  primary AND attempt schema-version type-confusion, plus the
#              two `**extra` header builders' fixed-metadata protection
#   Finding 3  the primary invariant gate was bypassable at persistence --
#              `emit_or_refuse` accepted an arbitrary scrub-clean hand-built
#              dict provided it carried the accepted revision and version,
#              bypassing `build_qualification_record` entirely
#
# The property the whole section establishes:
#
#   Any record accepted for primary or attempt durable emission mechanically
#   satisfies its artifact kind's own invariant contract, and carries a
#   version and a policy revision whose SERIALIZED value is AIDO's declared
#   one. Neither depends on a caller having invoked the right builder first.


class _ForgedEqualStr(str):
    """A ``str`` subclass that LIES about equality.

    Its underlying content -- the content ``json.dump`` writes into the
    immutable artifact -- is whatever it was constructed with, but it compares
    equal to everything and unequal to nothing. An equality-only check
    (``value != DECLARED``) is therefore satisfied by a forgery. This is the
    exact shape of findings 1 and 2.
    """

    def __eq__(self, other):  # noqa: D105 - the bypass under test
        return True

    def __ne__(self, other):
        return False

    def __hash__(self):
        return str.__hash__(self)


class _LyingDict(dict):
    """A ``dict`` subclass whose ``get`` reports AIDO's declared values while
    its real storage holds forged ones.

    ``json.dump`` serializes a dict subclass from that real storage, not
    through ``get`` -- proven inline in the tests below rather than asserted
    -- so a gate reading through ``get`` would approve one payload and then
    persist a different one.
    """

    def __init__(self, storage, reported):
        super().__init__(storage)
        self._reported = dict(reported)

    def get(self, key, default=None):
        if key in self._reported:
            return self._reported[key]
        return super().get(key, default)


class _Absent:
    def __repr__(self):  # pragma: no cover - debugging aid only
        return "<absent>"


_ABSENT = _Absent()

_STALE_PRIMARY_V1 = "pi-implementer-qualification.v1"
_STALE_ATTEMPT_V1 = "pi-implementer-qualification-attempt.v1"


def _assert_nothing_written(target: Path) -> None:
    assert not target.exists()


# -- Finding 1: attempt policy-revision type confusion -----------------------


def test_attempt_emission_refuses_an_equality_forging_policy_revision(
    git_executable: str, tmp_path: Path
):
    """FINDING 1. ``_require_valid_attempt_payload`` compared the retained
    policy revision with ordinary ``!=`` only, so a ``str`` subclass with an
    attacker-controlled ``__eq__``/``__ne__`` compared equal to the declared
    revision while serializing its forged underlying string.
    """
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged = dict(payload)
    forged["qualification_policy_revision"] = _ForgedEqualStr(_FORGED)

    # The bypass is real: the lookalike satisfies an equality-only check...
    assert forged["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert not (forged["qualification_policy_revision"] != QUALIFICATION_POLICY_REVISION)
    # ...while what would reach the immutable artifact is the forgery.
    assert _FORGED in json.dumps(forged)

    target = tmp_path / "attempt_forged_revision.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


@pytest.mark.parametrize(
    "impostor",
    [_ForgedEqualStr(""), None, 1, True, ("x",), 1.0],
    ids=["forged_empty_str_subclass", "none", "int", "bool", "tuple", "float"],
)
def test_attempt_emission_refuses_a_revision_of_any_non_str_type(
    git_executable: str, tmp_path: Path, impostor
):
    """The rule is EXACT ORDINARY ``str``, not "something that compares
    equal" -- no truthiness, no coercion, no ``str(value)``, no
    normalization."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged = dict(payload)
    forged["qualification_policy_revision"] = impostor
    target = tmp_path / "attempt_impostor.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


# -- Finding 2: schema-version type confusion, both artifact kinds -----------


def test_attempt_emission_refuses_an_equality_forging_stale_v1_version(
    git_executable: str, tmp_path: Path
):
    """FINDING 2, attempt. A retained artifact must not pair the new policy
    binding with a real underlying ``.v1`` value that merely compares equal
    to ``.v2``."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged = dict(payload)
    forged["record_version"] = _ForgedEqualStr(_STALE_ATTEMPT_V1)
    assert forged["record_version"] == ATTEMPT_RECORD_VERSION  # the bypass
    assert _STALE_ATTEMPT_V1 in json.dumps(forged)  # what would be persisted

    target = tmp_path / "attempt_forged_version.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_primary_emission_refuses_an_equality_forging_stale_v1_version(tmp_path: Path):
    """FINDING 2, primary. Same bypass, same closure."""
    forged = _minimal_primary_record()
    forged["record_version"] = _ForgedEqualStr(_STALE_PRIMARY_V1)
    assert forged["record_version"] == RECORD_VERSION  # the bypass
    assert _STALE_PRIMARY_V1 in json.dumps(forged)  # what would be persisted

    target = tmp_path / "primary_forged_version.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_primary_emission_refuses_an_equality_forging_policy_revision(tmp_path: Path):
    """FINDING 2, primary revision, against a subclass that forges ``__ne__``
    as well as ``__eq__``."""
    forged = _minimal_primary_record()
    forged["qualification_policy_revision"] = _ForgedEqualStr(_FORGED)
    assert _FORGED in json.dumps(forged)
    target = tmp_path / "primary_forged_revision.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


@pytest.mark.parametrize("key", ["experiment", "record_kind", "fixture_schema_version"])
def test_primary_emission_refuses_equality_forging_fixed_header_strings(
    tmp_path: Path, key: str
):
    """Every fixed header string is type-guarded, not just the C4 pair --
    otherwise the same trick simply moves one field sideways."""
    forged = _minimal_primary_record()
    forged[key] = _ForgedEqualStr("forged-" + key)
    target = tmp_path / "primary_forged_fixed.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


@pytest.mark.parametrize("key", ["candidate", "model_id", "task_id", "task_revision"])
def test_primary_emission_refuses_equality_forging_identity_strings(tmp_path: Path, key: str):
    """A lookalike must be refused BEFORE it can subvert the frozen contract's
    own comparisons (``model_id !=``, ``task_revision.startswith``)."""
    forged = _minimal_primary_record()
    forged[key] = _ForgedEqualStr("forged-" + key)
    target = tmp_path / "primary_forged_identity.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


@pytest.mark.parametrize("key", ["candidate", "model_id", "task_id", "task_revision"])
def test_attempt_emission_refuses_equality_forging_identity_strings(
    git_executable: str, tmp_path: Path, key: str
):
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged = dict(payload)
    forged[key] = _ForgedEqualStr("forged-" + key)
    target = tmp_path / "attempt_forged_identity.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


# -- Finding 2: the two `**extra` header builders ----------------------------


def test_the_two_header_builders_protect_the_c4_fixed_metadata_pair():
    """FINDING 2, header construction. ``record_version`` and
    ``qualification_policy_revision`` are both FIXED AIDO metadata of C4's
    ``.v2`` schemas, so a caller must not be able to manufacture an
    internally inconsistent header by supplying either through ``**extra``.

    The set is deliberately EXACTLY that pair: this is not a redesign of
    every historical fixed header key.
    """
    assert (
        semantic_attempt_module._CALLER_FORBIDDEN_HEADER_KEYS
        is records_module._CALLER_FORBIDDEN_HEADER_KEYS
    )
    assert records_module._CALLER_FORBIDDEN_HEADER_KEYS == frozenset(
        {"record_version", "qualification_policy_revision"}
    )


def test_record_header_refuses_a_caller_supplied_record_version():
    with pytest.raises(RecordInvariantError):
        record_header(record_version=_STALE_PRIMARY_V1)


def test_attempt_record_header_refuses_a_caller_supplied_record_version():
    with pytest.raises(AttemptRecordInvariantError):
        attempt_record_header(record_version=_STALE_ATTEMPT_V1)


def test_header_builders_restamp_the_version_after_extras_if_the_guard_is_removed(
    monkeypatch,
):
    """The SECOND, independent defence, for the version half of the pair: the
    fixed metadata is re-stamped after ``**extra`` is merged, so the last
    write -- AIDO's -- wins even with the guard neutralised.
    """
    monkeypatch.setattr(
        records_module, "_reject_caller_supplied_fixed_metadata", lambda extra: None
    )
    monkeypatch.setattr(
        semantic_attempt_module, "_reject_caller_supplied_fixed_metadata", lambda extra: None
    )
    primary = records_module.record_header(record_version=_STALE_PRIMARY_V1)
    attempt = semantic_attempt_module.attempt_record_header(record_version=_STALE_ATTEMPT_V1)
    assert primary["record_version"] == RECORD_VERSION
    assert attempt["record_version"] == ATTEMPT_RECORD_VERSION
    assert _STALE_PRIMARY_V1 not in json.dumps(primary)
    assert _STALE_ATTEMPT_V1 not in json.dumps(attempt)


def test_the_two_header_builders_stamp_their_OWN_version_not_each_others():
    """The protected key NAMES are shared; the version VALUES are not."""
    assert record_header()["record_version"] == RECORD_VERSION
    assert attempt_record_header()["record_version"] == ATTEMPT_RECORD_VERSION
    assert RECORD_VERSION != ATTEMPT_RECORD_VERSION


# -- Finding 3: the primary invariant gate at persistence --------------------


def test_emit_or_refuse_refuses_a_dict_carrying_only_the_c4_metadata(tmp_path: Path):
    """FINDING 3, the minimal case named by the review.

    A scrub-clean direct dict carrying nothing but the accepted revision and
    version was persisted verbatim, bypassing ``build_qualification_record``
    -- the module's declared invariant gate for this artifact -- entirely.
    The scrub says nothing about it, because a scrub checks SAFETY.
    """
    bypass = {
        "record_version": RECORD_VERSION,
        "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
    }
    assert qualification_scrub_check(bypass, NO_SECRETS)["clean"] is True
    target = tmp_path / "metadata_only.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(bypass, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def _primary_with(mutations: dict) -> dict:
    """A genuine builder record, mutated AFTERWARDS into a shape the builder
    itself would have refused.

    This is the supported-caller bypass in its strongest form: a dict that
    carries every correct fixed C4 header field and still violates the frozen
    primary-record contract.
    """
    record = _minimal_primary_record()
    for key, value in mutations.items():
        if value is _ABSENT:
            del record[key]
        else:
            record[key] = value
    return record


#: Every adversarial direct-dict shape the review named, plus the header and
#: closed-shape cases. Each carries the correct ``.v2`` version and declared
#: policy revision unless the case is specifically about removing one, so
#: ONLY a mechanical re-derivation of the frozen primary contract can refuse
#: it.
_ADVERSARIAL_PRIMARY_MUTATIONS: dict[str, dict] = {
    "candidate_model_mismatch": {"model_id": "minimax-m2.7"},
    "unknown_task_id": {"task_id": "IQ-9", "task_revision": "IQ-9@deadbeefdeadbeef"},
    "task_revision_of_another_task": {"task_revision": "IQ-2@deadbeefdeadbeef"},
    "semantic_prompts_sent_two": {"semantic_prompts_sent": 2},
    "semantic_prompts_sent_zero_post_prompt": {"semantic_prompts_sent": 0},
    "valid_with_scoring_eligible_false": {
        "scoring_eligible": False,
        "autonomous_classification": "AUTONOMOUS_FAIL",
        "diagnostic_subclassification": "COMPLETED_BUT_WRONG",
    },
    "non_valid_with_scoring_eligible_true": {"run_validity": "INFRASTRUCTURE_CONTAMINATED"},
    "unknown_run_validity": {"run_validity": "PROBABLY_FINE"},
    "autonomous_pass_with_automatic_retry": {"automatic_semantic_retry": True},
    "autonomous_pass_with_operator_continuation": {"operator_continuation": True},
    "autonomous_pass_with_a_fail_only_subclassification": {
        "diagnostic_subclassification": "PREMATURE_SETTLE"
    },
    "unknown_autonomous_classification": {"autonomous_classification": "AUTONOMOUS_MAYBE"},
    "invalid_supervised_recovery_pass": {"supervised_recovery": "PASS"},
    "invalid_supervised_recovery_fail": {"supervised_recovery": "FAIL"},
    "invalid_supervised_recovery_unknown": {"supervised_recovery": "PARTIAL"},
    "route_provenance_model_id_mismatch": {"route_provenance": {"model_id": "minimax-m2.7"}},
    "route_provenance_not_a_dict": {"route_provenance": "qwen3-coder-next"},
    "infrastructure_refusal_with_a_model_classification": {
        "infrastructure_refusal": True,
        "semantic_prompts_sent": 0,
        "run_validity": None,
        "scoring_eligible": False,
    },
    "wrong_fixed_experiment": {"experiment": "some-other-experiment"},
    "wrong_fixed_record_kind": {"record_kind": "qualification attempt"},
    "wrong_fixed_fixture_schema_version": {"fixture_schema_version": "made-up.v9"},
    "wrong_fixed_trust_namespaces": {"trust_namespaces": {}},
    "wrong_fixed_token_policy": {"token_policy": {"aido_requested_max_output_tokens": 4096}},
    "wrong_fixed_is_review_packet": {"is_review_packet": True},
    "wrong_fixed_reviewer_invoked": {"reviewer_invoked": True},
    "wrong_fixed_external_prior_not_scored": {"external_prior_not_scored": False},
    "missing_fixed_record_kind": {"record_kind": _ABSENT},
    "missing_fixed_trust_namespaces": {"trust_namespaces": _ABSENT},
    "missing_fixed_token_policy": {"token_policy": _ABSENT},
    "missing_policy_revision": {"qualification_policy_revision": _ABSENT},
    "missing_record_version": {"record_version": _ABSENT},
    "missing_run_validity": {"run_validity": _ABSENT},
    "missing_verification": {"verification": _ABSENT},
    "missing_supervised_recovery": {"supervised_recovery": _ABSENT},
    "unknown_top_level_field": {"provider_request_count": 3},
    "unknown_provenance_boolean": {"built_by_builder": True},
    "unknown_validated_boolean": {"validated": True},
    "supersedes_task_revision_of_another_task": {
        "supersedes_task_revision": "IQ-2@original00000000"
    },
    "non_bool_operator_continuation": {"operator_continuation": 0},
    "non_bool_scoring_eligible": {"scoring_eligible": 1},
    "non_int_semantic_prompts_sent": {"semantic_prompts_sent": True},
}


@pytest.mark.parametrize("case", sorted(_ADVERSARIAL_PRIMARY_MUTATIONS))
def test_emit_or_refuse_mechanically_re_derives_the_primary_contract(tmp_path: Path, case: str):
    """FINDING 3, the full matrix.

    Every payload here is a supported direct dictionary handed straight to
    the durable emission boundary, and the pre-FU1 boundary would have
    persisted each one. The boundary now re-derives the SAME contract
    ``build_qualification_record`` enforces, from the payload's own declared
    facts -- so a caller cannot bypass that contract by constructing a dict
    directly, and no provenance flag the payload might supply is consulted.
    """
    payload = _primary_with(_ADVERSARIAL_PRIMARY_MUTATIONS[case])
    target = tmp_path / "adversarial_primary.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_the_builder_refuses_every_adversarial_shape_it_can_express():
    """The boundary is not stricter than the builder in some arbitrary
    direction: for the mutations expressible as builder arguments, the
    builder refuses them too. The two enforce ONE contract."""
    builder_expressible = {
        "candidate_model_mismatch": {"model_id": "minimax-m2.7"},
        "unknown_task_id": {"task_id": "IQ-9", "task_revision": "IQ-9@deadbeefdeadbeef"},
        "task_revision_of_another_task": {"task_revision": "IQ-2@deadbeefdeadbeef"},
        "semantic_prompts_sent_two": {"semantic_prompts_sent": 2},
        "non_valid_with_scoring_eligible_true": {"run_validity": "INFRASTRUCTURE_CONTAMINATED"},
        "autonomous_pass_with_automatic_retry": {"automatic_semantic_retry": True},
        "autonomous_pass_with_operator_continuation": {"operator_continuation": True},
        "invalid_supervised_recovery_pass": {"supervised_recovery": "PASS"},
        "route_provenance_model_id_mismatch": {"route_provenance": {"model_id": "minimax-m2.7"}},
        "supersedes_task_revision_of_another_task": {
            "supersedes_task_revision": "IQ-2@original00000000"
        },
    }
    for overrides in builder_expressible.values():
        with pytest.raises(RecordInvariantError):
            _minimal_primary_record(**overrides)


def test_a_record_is_not_persistable_by_asserting_its_own_provenance(tmp_path: Path):
    """Named explicitly by the review: an extra provenance boolean inside the
    record is never trusted, and cannot rescue a payload. Here it does not
    even help an otherwise genuine one -- the closed shape refuses it."""
    payload = _minimal_primary_record()
    payload["built_by_builder"] = True
    payload["validated"] = True
    target = tmp_path / "self_asserted_provenance.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_emit_or_refuse_refuses_a_lying_dict_subclass(tmp_path: Path):
    """``json.dump`` serializes a dict subclass from its REAL storage, not
    through ``get`` -- proven inline -- so a payload whose ``get`` reports
    AIDO's declared values while its storage holds forged ones would
    otherwise be approved and then persisted as the forgery."""
    storage = _minimal_primary_record()
    storage["record_version"] = _STALE_PRIMARY_V1
    storage["qualification_policy_revision"] = _FORGED
    lying = _LyingDict(
        storage,
        {
            "record_version": RECORD_VERSION,
            "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
        },
    )
    # The bypass is real in both directions.
    assert lying.get("qualification_policy_revision") == QUALIFICATION_POLICY_REVISION
    assert lying.get("record_version") == RECORD_VERSION
    assert _FORGED in json.dumps(lying)
    assert _STALE_PRIMARY_V1 in json.dumps(lying)

    target = tmp_path / "lying_primary.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(lying, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_emit_attempt_or_refuse_refuses_a_lying_dict_subclass(
    git_executable: str, tmp_path: Path
):
    storage = _genuine_attempt_record(git_executable, tmp_path)
    storage["record_version"] = _STALE_ATTEMPT_V1
    storage["qualification_policy_revision"] = _FORGED
    lying = _LyingDict(
        storage,
        {
            "record_version": ATTEMPT_RECORD_VERSION,
            "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
        },
    )
    assert lying.get("qualification_policy_revision") == QUALIFICATION_POLICY_REVISION
    assert _FORGED in json.dumps(lying)

    target = tmp_path / "lying_attempt.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(lying, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_the_builder_and_the_boundary_call_ONE_contract_function():
    """Structural proof that the re-derivation is not a second, drifting copy
    of the rules: ``build_qualification_record`` and
    ``_require_valid_primary_payload`` both call the same
    ``_validate_primary_invariants``, and nothing else does."""
    tree = ast.parse(
        (_QUALIFICATION_DIR / "records.py").read_text(encoding="utf-8"), filename="records.py"
    )
    callers = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "_validate_primary_invariants"
            for inner in ast.walk(node)
        )
    }
    assert callers == {"build_qualification_record", "_require_valid_primary_payload"}


def test_the_primary_boundary_does_not_depend_on_the_builder_being_called(
    tmp_path: Path, monkeypatch
):
    """Why this is an authority invariant rather than a caller convention:
    with the builder made unusable, a previously built genuine record still
    emits, and a hand-built dict still does not. The boundary consults the
    payload, never the call history."""
    genuine = _minimal_primary_record()

    def _explode(*args, **kwargs):  # pragma: no cover - must never be reached
        raise AssertionError("emit_or_refuse must not call the builder")

    monkeypatch.setattr(records_module, "build_qualification_record", _explode)

    ok = tmp_path / "still_emits.json"
    result = emit_or_refuse(genuine, path=str(ok), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False

    bad = tmp_path / "still_refused.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(
            {
                "record_version": RECORD_VERSION,
                "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
            },
            path=str(bad),
            safety=NO_SECRETS,
        )
    _assert_nothing_written(bad)


# -- Positive controls -------------------------------------------------------


def test_positive_control_a_genuine_primary_record_still_emits(tmp_path: Path):
    target = tmp_path / "genuine_primary.json"
    result = emit_or_refuse(_minimal_primary_record(), path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["record_version"] == RECORD_VERSION
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION


def test_positive_control_the_conditional_supersedes_field_is_still_accepted(tmp_path: Path):
    """The one conditionally-present top-level key survives the closed-shape
    rule -- a real builder output must never be refused by its own
    boundary."""
    record = _minimal_primary_record(
        task_id="IQ-2",
        task_revision="IQ-2@corrected0000000",
        supersedes_task_revision="IQ-2@original00000000",
    )
    target = tmp_path / "supersedes.json"
    result = emit_or_refuse(record, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    assert json.loads(target.read_text(encoding="utf-8"))["supersedes_task_revision"] == (
        "IQ-2@original00000000"
    )


def test_positive_control_a_pre_prompt_infrastructure_refusal_record_still_emits(
    tmp_path: Path,
):
    """The other frozen primary shape: a pre-prompt gate outcome with no run
    to validate. The boundary must accept every shape the builder produces,
    not merely the post-prompt VALID one."""
    record = _minimal_primary_record(
        semantic_prompts_sent=0,
        infrastructure_refusal=True,
        run_validity=None,
        scoring_eligible=False,
        autonomous_classification="INFRASTRUCTURE_REFUSAL",
        diagnostic_subclassification="NONE",
    )
    target = tmp_path / "pre_prompt_refusal.json"
    result = emit_or_refuse(record, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False


def test_positive_control_a_genuine_attempt_record_still_emits(
    git_executable: str, tmp_path: Path
):
    payload = _genuine_attempt_record(git_executable, tmp_path)
    target = tmp_path / "genuine_attempt_reemitted.json"
    result = emit_attempt_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert written["record_version"] == ATTEMPT_RECORD_VERSION


def test_positive_control_a_scrub_rejected_genuine_primary_still_yields_the_v2_refusal(
    tmp_path: Path,
):
    """The new invariant gate runs BEFORE the scrub, so it must not preempt
    the refusal path for a payload that is invariant-valid but unsafe. The
    bounded ``.v2`` refusal, carrying the single declared policy revision, is
    still what gets retained."""
    unsafe = _minimal_primary_record(
        pi_runtime={"observed_version": "0.84.2-synthetic", "seen": "203.0.113.7"}
    )
    target = tmp_path / "scrub_refused_primary.json"
    result = emit_or_refuse(unsafe, path=str(target), safety=NO_SECRETS)
    assert result["refused"] is True
    on_disk = target.read_text(encoding="utf-8")
    written = json.loads(on_disk)
    assert written["record_version"] == REFUSAL_RECORD_VERSION
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert set(written) == _PRE_C4_REFUSAL_KEYS | {"qualification_policy_revision"}
    assert "203.0.113.7" not in on_disk


def test_positive_control_a_scrub_rejected_genuine_attempt_still_yields_the_v2_refusal(
    git_executable: str, tmp_path: Path
):
    unsafe = _genuine_attempt_record(git_executable, tmp_path)
    unsafe["pi_runtime"] = dict(unsafe["pi_runtime"])
    unsafe["pi_runtime"]["observed_version"] = "seen at 203.0.113.7"
    target = tmp_path / "scrub_refused_attempt.json"
    result = emit_attempt_or_refuse(unsafe, path=str(target), safety=NO_SECRETS)
    assert result["refused"] is True
    on_disk = target.read_text(encoding="utf-8")
    written = json.loads(on_disk)
    assert written["record_version"] == REFUSAL_RECORD_VERSION
    assert written["refused_record_kind"] == ATTEMPT_RECORD_KIND
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert set(written) == _PRE_C4_REFUSAL_KEYS | {"qualification_policy_revision"}
    assert "203.0.113.7" not in on_disk


def test_positive_control_exclusive_create_semantics_are_unchanged(tmp_path: Path):
    """FU1 added a gate, not a second write path: the first write to a fresh
    pathname succeeds and any second write fails closed, leaving the first
    artifact byte-for-byte unchanged."""
    from qualification.safety import EvidencePathCollisionError

    target = tmp_path / "once_fu1.json"
    emit_or_refuse(_minimal_primary_record(), path=str(target), safety=NO_SECRETS)
    first_bytes = target.read_bytes()
    with pytest.raises(EvidencePathCollisionError):
        emit_or_refuse(
            _minimal_primary_record(task_id="IQ-3", task_revision="IQ-3@aaaaaaaaaaaaaaaa"),
            path=str(target),
            safety=NO_SECRETS,
        )
    assert target.read_bytes() == first_bytes


# -- Additional bypasses found by the mandatory post-fix adversarial pass ----
# The first fix type-guarded the TOP-LEVEL fixed fields. Probing the shipped
# API afterwards showed the same trick simply moved one level down: a fixed
# AIDO mapping (`token_policy`, `trust_namespaces`, the attempt's frozen
# `route_provenance`) was compared with `==`, and `dict.__eq__` compares its
# VALUES with `==` too. The fixed mappings are now compared by SERIALIZED
# form -- what is compared is exactly what gets written.


def test_primary_emission_refuses_a_nested_forged_token_policy_claim(tmp_path: Path):
    """``token_policy`` is a fixed AIDO CLAIM (`AIDO requested no output-token
    cap`), so a nested equality-forging value inside it is a forged durable
    claim, not a cosmetic difference."""
    forged_policy = dict(records_module.TOKEN_POLICY)
    forged_policy["meaning_of_null"] = _ForgedEqualStr("AIDO capped output at 512 tokens")
    payload = _minimal_primary_record()
    payload["token_policy"] = forged_policy

    # The bypass is real: an ordinary mapping comparison is satisfied...
    assert forged_policy == records_module.TOKEN_POLICY
    # ...while the forged claim is what would be written.
    assert "AIDO capped output at 512 tokens" in json.dumps(payload)

    target = tmp_path / "forged_token_policy.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_primary_emission_refuses_a_nested_forged_trust_namespace_claim(tmp_path: Path):
    forged_namespaces = dict(records_module.TRUST_NAMESPACES)
    forged_namespaces["runtime_reported_*"] = _ForgedEqualStr("AUTHORITATIVE")
    payload = _minimal_primary_record()
    payload["trust_namespaces"] = forged_namespaces
    assert forged_namespaces == records_module.TRUST_NAMESPACES

    target = tmp_path / "forged_trust_namespaces.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_attempt_emission_refuses_a_nested_forged_token_policy_claim(
    git_executable: str, tmp_path: Path
):
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged_policy = dict(payload["token_policy"])
    forged_policy["meaning_of_null"] = _ForgedEqualStr("AIDO capped output at 512 tokens")
    payload["token_policy"] = forged_policy

    target = tmp_path / "attempt_forged_token_policy.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_attempt_emission_refuses_a_nested_forged_route_identity(
    git_executable: str, tmp_path: Path
):
    """The attempt's ``route_provenance`` is the FROZEN route identity for the
    candidate, so a nested lookalike is a cross-candidate/provider/backend
    route substitution."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged_route = dict(payload["route_provenance"])
    forged_route["model_id"] = _ForgedEqualStr("minimax-m2.7")
    payload["route_provenance"] = forged_route
    assert "minimax-m2.7" in json.dumps(payload)

    target = tmp_path / "attempt_forged_route.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_primary_emission_refuses_a_nested_forged_route_model_id(tmp_path: Path):
    """The primary contract's ``route_provenance.model_id`` check compared
    with ``!=`` only; qualification evidence belongs to a model x route
    tuple, so a lookalike there substitutes the model the evidence is about."""
    payload = _minimal_primary_record()
    payload["route_provenance"] = {"model_id": _ForgedEqualStr("minimax-m2.7")}
    assert payload["route_provenance"]["model_id"] == "qwen3-coder-next"  # the bypass
    assert "minimax-m2.7" in json.dumps(payload)

    target = tmp_path / "primary_forged_route.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_the_builder_also_refuses_a_forged_route_model_id():
    """The builder shares the contract, so it refuses the same lookalike --
    a forged record cannot be manufactured through the supported builder
    either."""
    with pytest.raises(RecordInvariantError):
        _minimal_primary_record(
            route_provenance={"model_id": _ForgedEqualStr("minimax-m2.7")}
        )


def test_a_fixed_mapping_of_the_right_value_but_the_wrong_type_is_refused(tmp_path: Path):
    """``type(...) is dict``: a Mapping subclass can report one thing and
    serialize another, exactly as at the top level."""
    payload = _minimal_primary_record()
    payload["token_policy"] = _LyingDict(
        {"forged": True}, dict(records_module.TOKEN_POLICY)
    )
    target = tmp_path / "mapping_subclass_token_policy.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


# ===========================================================================
# J. 5F3B-LIVE1-C4-FU2 -- NESTED DURABLE-CLAIM TYPE/CONTAINER CLOSURE
# ===========================================================================
# FU1 closed the TOP-LEVEL lying-container and lying-equality bypasses.
# Independent review found the identical trick still worked one level down:
#
#   Finding 1  the PRIMARY record's `route_provenance` container itself was
#              only `isinstance(..., dict)`-checked, so a `dict` subclass
#              could report the expected model id through `.get()` while its
#              real storage -- what `json.dump` actually serializes -- held
#              a different one. Reachable through both
#              `build_qualification_record` and `emit_or_refuse`, because
#              both call the same `_validate_route_provenance`.
#   Finding 2  the ATTEMPT record's nested Mapping containers (`pi_runtime`,
#              `compatibility_facts`, `gate_statuses`, `closure` and its own
#              nested fields) were `isinstance(..., Mapping)`-checked only,
#              the identical class of bypass one level deeper.
#   Finding 3  nested attempt STRINGS establishing gate chronology, dispatch
#              failure identity, `NOT_REACHED` status, runtime/broker closure
#              agreement, and the two cleanup/removal statuses were compared
#              with plain `!=`/`in`, forgeable by an equality-lying `str`
#              subclass exactly as the top-level fields were before FU1.
#
# The fix is ONE mechanism, not a special case per field:
# `_require_valid_attempt_payload` now canonicalizes the WHOLE payload
# through the SAME `json.dumps`/`json.loads` round trip the writer's
# `json.dump` call is equivalent to, before any other check runs, so every
# later check -- at any depth -- compares against the identical concrete
# value that would reach disk (`_canonicalize_or_refuse`). The primary
# record's `route_provenance` fix is narrower: `_validate_route_provenance`
# now requires an exact `dict`, matching the precedent FU1 already set for
# `token_policy`/`trust_namespaces`/the attempt's own `route_provenance`.
#
# The forbidden-key rule (`semantic_prompts_sent` absent at EVERY depth) is
# proven closed against a nested container that hides the key from every
# virtual Mapping operation (`get`, `__getitem__`, `__contains__`,
# `__iter__`, `values`) except `.items()` -- the one operation `json.dumps`
# actually uses for a non-exact dict, and therefore the one operation that,
# if it also hid the key, would mean the key never reaches persistence
# either. There is no way to hide from validation without also hiding from
# the writer.


class _HidingDict(dict):
    """A ``dict`` subclass that hides one key from every VIRTUAL Mapping
    operation -- ``get``, ``__getitem__``, ``__contains__``, ``__iter__``
    (and therefore ``set(...)``), ``values`` -- while leaving ``.items()``,
    and therefore ``json.dumps``, untouched. Proven inline: whatever
    ``.items()`` still reports is exactly what a real removal/cleanup/
    closure object's own real storage would also report, so this is the
    maximal adversary reachable without also hiding the key from
    persistence itself.
    """

    def __init__(self, storage: dict, hidden_key: str):
        super().__init__(storage)
        self._hidden_key = hidden_key

    def get(self, key, default=None):
        if key == self._hidden_key:
            return default
        return super().get(key, default)

    def __getitem__(self, key):
        if key == self._hidden_key:
            raise KeyError(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        if key == self._hidden_key:
            return False
        return super().__contains__(key)

    def __iter__(self):
        return iter(k for k in super().__iter__() if k != self._hidden_key)

    def values(self):
        return [v for k, v in super().items() if k != self._hidden_key]


# -- Finding 1: primary route_provenance container -----------------------


def test_the_builder_refuses_a_lying_route_provenance_container():
    """FINDING 1. The exact concrete example from the follow-up prompt: the
    validator observes ``model_id == qwen3-coder-next`` through ``.get()``,
    but the container's real storage -- what ``json.dump`` would serialize --
    holds ``minimax-m2.7``. ``build_qualification_record`` must refuse this
    just as readily as the emission boundary does; both call the same
    ``_validate_route_provenance``."""
    lying_route = _LyingDict(
        {"model_id": "minimax-m2.7"}, {"model_id": "qwen3-coder-next"}
    )
    # The bypass is real...
    assert lying_route.get("model_id") == "qwen3-coder-next"
    # ...while what would reach the immutable artifact is the other model.
    assert "minimax-m2.7" in json.dumps(lying_route)
    assert "qwen3-coder-next" not in json.dumps(lying_route)

    with pytest.raises(RecordInvariantError):
        _minimal_primary_record(route_provenance=lying_route)


def test_primary_emission_refuses_a_lying_route_provenance_container(tmp_path: Path):
    """FINDING 1, emission boundary. A hand-built payload that never passed
    through the builder must be refused identically, and nothing may be
    written."""
    lying_route = _LyingDict(
        {"model_id": "minimax-m2.7"}, {"model_id": "qwen3-coder-next"}
    )
    payload = _minimal_primary_record()
    payload["route_provenance"] = lying_route

    target = tmp_path / "primary_lying_route_container.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


# -- Finding 2: attempt nested Mapping containers ----------------------------


def test_attempt_emission_refuses_a_lying_pi_runtime_container(
    git_executable: str, tmp_path: Path
):
    """FINDING 2. The exact concrete example from the follow-up prompt:
    ``pi_runtime``'s real storage carries a FAILED compatibility gate and
    all-false compatibility facts, while its ``.get()`` reports a PASSED
    gate and all-true facts. The gate must refuse a payload it can only
    approve by trusting the lie."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    compat_names = sorted(semantic_attempt_module._COMPATIBILITY_FACT_NAMES)
    real_compat_facts = {name: False for name in compat_names}
    reported_compat_facts = {name: True for name in compat_names}
    lying_pi_runtime = _LyingDict(
        {
            "observed_version": payload["pi_runtime"]["observed_version"],
            "compatibility_facts": real_compat_facts,
            "compatibility_gate_passed": False,
        },
        {
            "compatibility_gate_passed": True,
            "compatibility_facts": reported_compat_facts,
        },
    )
    # The bypass is real: an equality/`.get()`-based check would be satisfied...
    assert lying_pi_runtime.get("compatibility_gate_passed") is True
    assert all(lying_pi_runtime.get("compatibility_facts").values())
    # ...while what would reach the immutable artifact is the opposite.
    canonical = json.loads(json.dumps(lying_pi_runtime))
    assert canonical["compatibility_gate_passed"] is False
    assert not any(canonical["compatibility_facts"].values())

    forged = dict(payload)
    forged["pi_runtime"] = lying_pi_runtime
    target = tmp_path / "attempt_lying_pi_runtime.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_attempt_emission_refuses_a_lying_gate_statuses_container(
    git_executable: str, tmp_path: Path
):
    """A ``gate_statuses`` container whose ``.get()`` reports the genuine
    PASSED chronology while its real storage records a failed pre-prompt
    gate -- the same class of bypass one field over from ``pi_runtime``."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    real_gate_statuses = dict(payload["gate_statuses"])
    real_gate_statuses["run_correlation"] = "FAILED:FORGED"
    lying_gate_statuses = _LyingDict(
        real_gate_statuses, {"run_correlation": "PASSED"}
    )
    assert lying_gate_statuses.get("run_correlation") == "PASSED"
    canonical = json.loads(json.dumps(lying_gate_statuses))
    assert canonical["run_correlation"] == "FAILED:FORGED"

    forged = dict(payload)
    forged["gate_statuses"] = lying_gate_statuses
    target = tmp_path / "attempt_lying_gate_statuses.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_attempt_emission_refuses_a_lying_removal_facts_container(
    git_executable: str, tmp_path: Path
):
    """``closure.semantic_workspace_removal.facts`` -- the deepest nested
    authority-bearing Mapping named by the follow-up prompt -- is subject to
    the identical bypass and the identical fix."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    real_facts = dict(payload["closure"]["semantic_workspace_removal"]["facts"])
    real_facts["verified"] = False
    real_facts["removed"] = False
    lying_facts = _LyingDict(real_facts, {"verified": True, "removed": True})
    assert lying_facts.get("verified") is True
    canonical = json.loads(json.dumps(lying_facts))
    assert canonical["verified"] is False

    removal = dict(payload["closure"]["semantic_workspace_removal"])
    removal["facts"] = lying_facts
    closure = dict(payload["closure"])
    closure["semantic_workspace_removal"] = removal
    forged = dict(payload)
    forged["closure"] = closure
    target = tmp_path / "attempt_lying_removal_facts.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


# -- Finding 3: attempt nested authority-bearing strings ---------------------


@pytest.mark.parametrize(
    "gate_name,forged_content",
    [
        ("run_correlation", "FAILED:FORGED"),  # pre-prompt gate status
        ("semantic_prompt_dispatch", "FAILED:FORGED"),  # dispatch failure identity
        ("turn_completion", "FAILED:FORGED"),  # post-dispatch NOT_REACHED
        ("generated_config_cleanup", "FAILED:FORGED"),  # cleanup gate status
        ("semantic_workspace_removal", "FAILED:FORGED"),  # removal gate status
    ],
)
def test_attempt_emission_refuses_a_forged_equality_gate_status(
    git_executable: str, tmp_path: Path, gate_name: str, forged_content: str
):
    """FINDING 3. Each of these is compared with plain ``!=``/``in``, so an
    equality-forging ``str`` subclass whose real content is a completely
    different status satisfies the comparison while persisting the forged
    text."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    genuine_status = payload["gate_statuses"][gate_name]
    forged_status = _ForgedEqualStr(forged_content)
    gate_statuses = dict(payload["gate_statuses"])
    gate_statuses[gate_name] = forged_status

    # The bypass is real...
    assert forged_status == genuine_status
    assert not (forged_status != genuine_status)
    # ...while what would reach the immutable artifact is the forged text.
    assert forged_content in json.dumps(gate_statuses)

    forged = dict(payload)
    forged["gate_statuses"] = gate_statuses
    target = tmp_path / f"attempt_forged_gate_{gate_name}.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


@pytest.mark.parametrize("closure_key", ["runtime_teardown", "broker_shutdown"])
def test_attempt_emission_refuses_a_forged_equality_closure_value(
    git_executable: str, tmp_path: Path, closure_key: str
):
    """The runtime/broker closure-agreement check
    (``closure[key] != gate_statuses[key]``) is equality-only. Here the
    ``gate_statuses`` side stays genuine and only the ``closure`` side is
    forged -- the exact regression the follow-up prompt names explicitly."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    genuine_status = payload["gate_statuses"][closure_key]
    forged_content = genuine_status + "-FORGED"
    forged_value = _ForgedEqualStr(forged_content)
    closure = dict(payload["closure"])
    closure[closure_key] = forged_value

    assert forged_value == genuine_status  # the bypass
    assert forged_content in json.dumps(closure)  # what would be persisted

    forged = dict(payload)
    forged["closure"] = closure
    target = tmp_path / f"attempt_forged_closure_{closure_key}.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


# -- Forbidden-key adversarial case: hidden at a nested container boundary --


def test_attempt_emission_refuses_semantic_prompts_sent_hidden_behind_a_lying_container(
    git_executable: str, tmp_path: Path
):
    """The frozen invariant is that ``semantic_prompts_sent`` is ABSENT at
    EVERY depth. Here it is hidden from ``__contains__``/``__getitem__``/
    ``get``/``__iter__``/``values`` -- everything ``_contains_key`` and
    ``set(...)`` could ever consult directly -- while ``.items()``, the
    operation ``json.dumps`` actually walks for a non-exact dict, still
    reports it. The emission boundary must still refuse it, because the
    fix is not "call ``_contains_key`` again": it is that every check now
    runs against the JSON round trip, which can only ever reflect what
    ``.items()`` (here, still honest) reports.
    """
    payload = _genuine_attempt_record(git_executable, tmp_path)
    hidden_cleanup = _HidingDict(
        dict(payload["closure"]["generated_config_cleanup"], semantic_prompts_sent=1),
        "semantic_prompts_sent",
    )
    # The hiding is real against every virtual Mapping operation...
    assert "semantic_prompts_sent" not in hidden_cleanup
    assert "semantic_prompts_sent" not in set(hidden_cleanup)
    assert hidden_cleanup.get("semantic_prompts_sent") is None
    with pytest.raises(KeyError):
        hidden_cleanup["semantic_prompts_sent"]  # noqa: B018 - the point is the raise
    # ...while `.items()` -- what `json.dumps` actually walks -- still has it.
    canonical = json.loads(json.dumps(hidden_cleanup))
    assert canonical["semantic_prompts_sent"] == 1

    closure = dict(payload["closure"])
    closure["generated_config_cleanup"] = hidden_cleanup
    forged = dict(payload)
    forged["closure"] = closure
    target = tmp_path / "attempt_hidden_forbidden_key.json"
    with pytest.raises(AttemptRecordInvariantError) as excinfo:
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    assert "semantic_prompts_sent" in str(excinfo.value)
    _assert_nothing_written(target)


def test_attempt_emission_accepts_the_shape_when_items_also_hides_the_key(
    git_executable: str, tmp_path: Path
):
    """The complementary case, proving there is no gap left at the OTHER
    edge: a container that hides the key from ``.items()`` too. This is NOT
    a bypass -- if ``.items()`` does not report the key, ``json.dumps``
    genuinely would not persist it either, and what remains is exactly the
    real, genuine 3-key ``generated_config_cleanup`` shape with nothing
    forged. So the correct outcome here is ACCEPTANCE, not refusal: refusing
    it would mean the gate is reacting to the wrapper object's identity
    rather than to any actual divergence between what it validates and what
    would be written -- and there is none once ``.items()`` itself is
    honest about what should reach disk."""

    class _ItemsAlsoHidingDict(_HidingDict):
        def items(self):
            return [(k, v) for k, v in dict.items(self) if k != self._hidden_key]

    payload = _genuine_attempt_record(git_executable, tmp_path)
    fully_hidden_cleanup = _ItemsAlsoHidingDict(
        dict(payload["closure"]["generated_config_cleanup"], semantic_prompts_sent=1),
        "semantic_prompts_sent",
    )
    canonical = json.loads(json.dumps(fully_hidden_cleanup))
    # Proof: when `.items()` also lies, the key genuinely never reaches the
    # serialized form -- there is no divergence for the validator to miss.
    assert "semantic_prompts_sent" not in canonical
    assert canonical == dict(payload["closure"]["generated_config_cleanup"])

    closure = dict(payload["closure"])
    closure["generated_config_cleanup"] = fully_hidden_cleanup
    forged = dict(payload)
    forged["closure"] = closure
    target = tmp_path / "attempt_items_hidden_key.json"
    result = emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert "semantic_prompts_sent" not in written["closure"]["generated_config_cleanup"]


# -- Positive controls: canonicalization must not disturb a genuine payload -


def test_positive_control_canonicalization_still_accepts_a_genuine_attempt_record(
    git_executable: str, tmp_path: Path
):
    """The FU2 fix must not turn correctness into a coincidence: an ordinary,
    honestly-built attempt payload -- plain dicts and ordinary strings all
    the way down, exactly what `build_attempt_record` produces -- still
    emits after being round-tripped through `json.dumps`/`json.loads`."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    target = tmp_path / "attempt_fu2_positive_control.json"
    result = emit_attempt_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["record_kind"] == ATTEMPT_RECORD_KIND


def test_positive_control_a_genuine_route_provenance_dict_still_emits(tmp_path: Path):
    """The FU2 route_provenance fix must not reject an ordinary dict."""
    record = _minimal_primary_record(route_provenance={"model_id": "qwen3-coder-next"})
    target = tmp_path / "genuine_route_provenance.json"
    result = emit_or_refuse(record, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    assert record["route_provenance"] == {"model_id": "qwen3-coder-next"}


# ===========================================================================
# K. 5F3B-LIVE1-C4-FU3 -- BIND DURABLE ATTEMPT EMISSION TO THE VALIDATED
#    SNAPSHOT
# ===========================================================================
# FU2 closed the primary `route_provenance` lying-container bypass, the
# attempt's nested Mapping/value confusion, and nested equality-forging
# string cases -- all found by comparing what a validator READ against what
# `json.dump` would WRITE for the SAME call. FU3 closes a different-shaped
# gap in the same family: `_require_valid_attempt_payload` canonicalized
# `record` -- rebinding it to `_canonicalize_or_refuse`'s output -- but that
# rebinding was LOCAL to the function. `build_attempt_record` and
# `emit_attempt_or_refuse` went on to use their OWN local variable
# (`record`, the caller's original object) for everything downstream: the
# scrub check and the exclusive-create write both re-consulted the ORIGINAL
# object a SECOND time, not the validated snapshot. A caller-owned object
# whose serialization changes between calls -- a stateful `dict` subclass,
# or a plain mutation performed between validation and persistence -- could
# therefore have a genuinely valid shape checked and a completely different,
# forged shape persisted.
#
# The fix: `_require_valid_attempt_payload` now RETURNS the exact canonical
# snapshot it validated, and both `build_attempt_record` and
# `emit_attempt_or_refuse` use ONLY that return value from that point on.
# The caller's original object is read exactly once (by
# `_canonicalize_or_refuse`, inside the ONE call to
# `_require_valid_attempt_payload`) and never consulted again.
#
# A second, independent gap closed here: `_canonicalize_or_refuse`'s probe
# `json.dumps` call did not use `sort_keys=True`, while
# `write_evidence_exclusively`'s `json.dump` call does. Independent review
# reproduced a payload for which the former succeeds and the latter raises
# `TypeError` -- AFTER the output file had already been exclusive-created,
# stranding a partial artifact. `_canonicalize_or_refuse` now probes with
# the SAME configuration the writer uses, so that failure surfaces as a
# clean refusal at validation time, before any file exists.
#
# A third, narrow schema gap closed here: `pi_runtime.observed_version` now
# mechanically enforces the real builder parameter's own declared domain,
# `str | None` -- never a Mapping, list, number, bool, or any other JSON
# shape the real builder could not have honestly produced.


class _StatefulItemsDict(dict):
    """A ``dict`` subclass whose ``.items()`` reports a genuine, valid
    attempt payload on its FIRST call, and a DIFFERENT, forged payload on
    every call after that.

    5F3B-LIVE1-C4-FU3's mandatory adversarial regression: "a `dict`
    subclass whose `.items()` changes behaviour by call count." Proven
    inline, before the supported API is ever invoked, that the two
    serializations genuinely disagree -- this is not an assumption about
    what ``json.dumps`` does internally, it is a fact established by calling
    it.
    """

    def __init__(self, genuine: dict, forged: dict):
        super().__init__(genuine)
        self._genuine_items = list(genuine.items())
        self._forged_items = list(forged.items())
        self.items_call_count = 0

    def items(self):
        self.items_call_count += 1
        if self.items_call_count == 1:
            return list(self._genuine_items)
        return list(self._forged_items)


def test_stateful_dict_items_cannot_forge_the_persisted_attempt_artifact(
    git_executable: str, tmp_path: Path
):
    """Mandatory adversarial regression: a stateful ``dict`` subclass whose
    ``.items()`` reports a genuinely valid attempt on the first call and an
    impossible one -- a forged ``qualification_policy_revision``, exactly
    one of the shapes the follow-up prompt names -- on every later call.

    Pre-FU3, ``_require_valid_attempt_payload`` validated call #1 and then
    discarded the canonical snapshot; ``emit_attempt_or_refuse`` went on to
    hand the ORIGINAL stateful object to the scrub and the writer, each of
    which would have triggered a FRESH call to ``.items()`` -- call #2,
    reporting the forgery. Post-FU3, the original object is read exactly
    once, ever.
    """
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged = dict(payload)
    forged["qualification_policy_revision"] = _FORGED

    stateful = _StatefulItemsDict(payload, forged)

    # -- Step 1: mechanically prove the adversary is real, BEFORE the
    # supported API is ever invoked. Two serializations of the SAME object
    # genuinely disagree.
    first_json = json.dumps(stateful, sort_keys=True)
    second_json = json.dumps(stateful, sort_keys=True)
    assert stateful.items_call_count == 2
    assert first_json != second_json
    assert json.loads(first_json) == payload
    assert QUALIFICATION_POLICY_REVISION in first_json
    assert _FORGED in second_json

    # Reset: the probe above is not part of the emission path under test.
    stateful.items_call_count = 0

    # -- Step 2: call the supported attempt durable-emission API.
    target = tmp_path / "stateful_items_attempt.json"
    result = emit_attempt_or_refuse(stateful, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False

    # -- Step 3: the ORIGINAL object's `.items()` was consulted EXACTLY
    # ONCE across the whole emission call -- never again after the
    # validated snapshot was produced.
    assert stateful.items_call_count == 1

    # -- Step 4: the retained artifact is EXACTLY the validated snapshot,
    # never the later (forged) serialization of the caller's object.
    on_disk = target.read_text(encoding="utf-8")
    written = json.loads(on_disk)
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert _FORGED not in on_disk


def test_stateful_nested_dict_items_cannot_forge_the_persisted_attempt_artifact(
    git_executable: str, tmp_path: Path
):
    """The same adversary, one level deeper: the TOP-LEVEL object is an
    ordinary dict, but the ``pi_runtime`` field nested inside it is the
    stateful adversary. Canonicalization walks the WHOLE payload in one
    ``json.dumps`` call, so the nested object's ``.items()`` is likewise
    consulted exactly once, ever.
    """
    payload = _genuine_attempt_record(git_executable, tmp_path)
    genuine_pi_runtime = dict(payload["pi_runtime"])
    forged_pi_runtime = dict(genuine_pi_runtime)
    forged_pi_runtime["compatibility_gate_passed"] = False

    stateful_pi_runtime = _StatefulItemsDict(genuine_pi_runtime, forged_pi_runtime)
    forged = dict(payload)
    forged["pi_runtime"] = stateful_pi_runtime

    first_json = json.dumps(stateful_pi_runtime, sort_keys=True)
    second_json = json.dumps(stateful_pi_runtime, sort_keys=True)
    assert first_json != second_json
    assert stateful_pi_runtime.items_call_count == 2
    stateful_pi_runtime.items_call_count = 0

    target = tmp_path / "stateful_nested_items_attempt.json"
    result = emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    assert stateful_pi_runtime.items_call_count == 1

    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["pi_runtime"]["compatibility_gate_passed"] is True


def test_post_snapshot_mutation_of_the_caller_object_cannot_reach_the_artifact(
    git_executable: str, tmp_path: Path
):
    """Mandatory adversarial regression: a mutation of the ORIGINAL
    caller-owned object performed AFTER the validated snapshot is taken.

    Drives ``_require_valid_attempt_payload`` and
    ``safety.emit_evidence_or_refuse`` directly -- exactly the two halves
    ``emit_attempt_or_refuse`` composes -- to open the window the follow-up
    prompt names explicitly ("post-snapshot mutation of the original caller
    object") and mutate inside it. The retained artifact must reflect only
    the pre-mutation validated snapshot.
    """
    payload = _genuine_attempt_record(git_executable, tmp_path)
    mutable = dict(payload)

    validated = semantic_attempt_module._require_valid_attempt_payload(mutable)

    # The mutation happens AFTER the snapshot was produced and validated.
    mutable["qualification_policy_revision"] = _FORGED
    mutable["semantic_dispatch_state"] = "SEND_STATE_DETERMINATE_SENT"
    mutable["closure"] = "mutated away entirely"
    mutable.clear()

    target = tmp_path / "post_snapshot_mutation.json"
    result = emit_evidence_or_refuse(
        validated, path=str(target), safety=NO_SECRETS, record_kind=ATTEMPT_RECORD_KIND
    )
    assert result["emitted"] is True and result["refused"] is False

    on_disk = target.read_text(encoding="utf-8")
    written = json.loads(on_disk)
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert written["semantic_dispatch_state"] == "SEND_STATE_INDETERMINATE"
    assert isinstance(written["closure"], dict)
    assert _FORGED not in on_disk


def test_mutating_the_caller_dict_after_full_emission_never_touches_the_written_file(
    git_executable: str, tmp_path: Path
):
    """The end-to-end, public-API counterpart: after ``emit_attempt_or_refuse``
    returns, mutating the caller's own dict must not be able to reach back
    into the artifact already retained on disk."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    mutable = dict(payload)
    target = tmp_path / "mutate_after_emit.json"
    result = emit_attempt_or_refuse(mutable, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    before = target.read_bytes()

    mutable["qualification_policy_revision"] = _FORGED
    mutable.clear()

    after = target.read_bytes()
    assert after == before


# -- Blocker 2: canonicalization must probe with the WRITER's own config ----


def test_canonicalization_uses_the_writers_exact_serialization_configuration():
    """Structural proof, from source: ``_canonicalize_or_refuse``'s probe
    ``json.dumps`` call passes ``sort_keys=True``, matching
    ``write_evidence_exclusively``'s ``json.dump`` call (``indent=2`` aside,
    which only affects whitespace)."""
    source = inspect.getsource(semantic_attempt_module._canonicalize_or_refuse)
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "dumps"
    ]
    assert len(calls) == 1
    kwarg_names = {kw.arg for kw in calls[0].keywords}
    assert {"ensure_ascii", "sort_keys"} <= kwarg_names


def test_a_payload_the_writer_configuration_cannot_serialize_is_refused_before_any_file_exists(
    tmp_path: Path,
):
    """Blocker 2, mechanically proven, independent of the stateful adversary
    above.

    ``sort_keys=True`` sorts a dict's ``.items()`` BEFORE any non-``str``
    key is coerced to text, so a dict with heterogeneous key TYPES (``str``
    and ``int`` keys mixed) can raise ``TypeError`` when compared. First,
    mechanically: ``json.dumps(hostile)`` succeeds while
    ``json.dumps(hostile, sort_keys=True)`` -- the writer's own
    configuration -- raises. Then: the supported API refuses the identical
    payload cleanly, and no file is ever created at the target path.
    """
    hostile_nested = {"a": 1, 1: "a"}

    # Step 1: mechanically prove the adversary is real.
    json.dumps(hostile_nested)  # succeeds -- no ordering is required
    with pytest.raises(TypeError):
        json.dumps(hostile_nested, sort_keys=True)  # the writer's own config

    payload = {"top_level": hostile_nested}
    json.dumps(payload)  # still succeeds without sort_keys
    with pytest.raises(TypeError):
        json.dumps(payload, sort_keys=True)

    # Step 2: the supported API refuses it, and refuses it BEFORE any file
    # is created -- never a bare TypeError escaping from inside the writer
    # after `open(path, "x")` already succeeded.
    target = tmp_path / "hostile_sort_keys.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_a_writer_incompatible_second_read_never_reaches_persistence(
    git_executable: str, tmp_path: Path
):
    """Blocker 1 and Blocker 2 combined, exactly as independent review
    reproduced them: a stateful object whose FIRST read is genuinely valid
    and whose SECOND read -- the one the pre-FU3 writer would have taken --
    contains heterogeneous dict key types that ``sort_keys=True`` cannot
    serialize. Pre-FU3 this would have raised a bare ``TypeError`` inside
    ``write_evidence_exclusively``, AFTER the output file had already been
    exclusive-created, stranding a partial artifact. Post-FU3 the original
    object is never read a second time, so the writer only ever sees the
    validated, writer-safe snapshot.
    """
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged = dict(payload)
    forged["closure"] = {"a": 1, 1: "a"}  # unserializable under sort_keys=True

    stateful = _StatefulItemsDict(payload, forged)
    # Step 1: mechanically prove the adversary is real -- call #1 (genuine)
    # serializes cleanly; call #2 (forged) is exactly what a pre-FU3 writer
    # re-reading the original object would have hit.
    first_json = json.dumps(stateful, sort_keys=True)
    assert json.loads(first_json)["closure"] == payload["closure"]
    with pytest.raises(TypeError):
        json.dumps(stateful, sort_keys=True)
    assert stateful.items_call_count == 2
    stateful.items_call_count = 0

    # Step 2: the supported API only ever takes the FIRST read.
    target = tmp_path / "writer_incompatible_second_read.json"
    result = emit_attempt_or_refuse(stateful, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    assert stateful.items_call_count == 1
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["closure"] == payload["closure"]


# -- pi_runtime.observed_version domain --------------------------------------


@pytest.mark.parametrize(
    "impostor",
    [
        {"observed": "0.84.2"},
        ["0.84.2"],
        84,
        84.2,
        True,
        False,
        {"nested": {"deeper": "0.84.2"}},
    ],
    ids=[
        "mapping",
        "list",
        "int",
        "float",
        "bool_true",
        "bool_false",
        "nested_json_object",
    ],
)
def test_attempt_emission_refuses_an_observed_version_outside_its_declared_domain(
    git_executable: str, tmp_path: Path, impostor
):
    """The real builder parameter is ``observed_pi_version: str | None`` --
    the ONE domain the real builder could ever honestly produce. A
    hand-built dict handed straight to ``emit_attempt_or_refuse`` must not
    be able to express any other shape there."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged = dict(payload)
    pi_runtime = dict(forged["pi_runtime"])
    pi_runtime["observed_version"] = impostor
    forged["pi_runtime"] = pi_runtime

    target = tmp_path / "attempt_observed_version_impostor.json"
    with pytest.raises(AttemptRecordInvariantError):
        emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


def test_attempt_emission_still_accepts_a_none_observed_version(
    git_executable: str, tmp_path: Path
):
    """Positive control: ``None`` is the OTHER half of the real domain, and
    must not be rejected by the new check."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    forged = dict(payload)
    pi_runtime = dict(forged["pi_runtime"])
    pi_runtime["observed_version"] = None
    forged["pi_runtime"] = pi_runtime

    target = tmp_path / "attempt_observed_version_none.json"
    result = emit_attempt_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["pi_runtime"]["observed_version"] is None


def test_attempt_emission_still_accepts_an_ordinary_str_observed_version(
    git_executable: str, tmp_path: Path
):
    """Positive control: a genuine attempt record's own observed version --
    already an ordinary str -- still emits."""
    payload = _genuine_attempt_record(git_executable, tmp_path)
    assert isinstance(payload["pi_runtime"]["observed_version"], str)
    target = tmp_path / "attempt_observed_version_genuine.json"
    result = emit_attempt_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False


# -- Structural proof: build_attempt_record returns the SAME validated -----
# -- object its own self-check produced, never a second local copy ---------


def test_build_attempt_record_returns_exactly_what_its_own_gate_validated(
    monkeypatch,
):
    """Structural proof that ``build_attempt_record`` cannot return one
    object while having validated another: monkeypatch
    ``_require_valid_attempt_payload`` to return a recognizable sentinel
    dict, and confirm that sentinel -- not the function's own locally built
    ``record`` -- is what comes back."""
    sentinel = {"sentinel": True}

    def _fake_gate(record):
        return sentinel

    monkeypatch.setattr(
        semantic_attempt_module, "_require_valid_attempt_payload", _fake_gate
    )
    result = semantic_attempt_module.build_attempt_record(
        candidate="A",
        model_id="qwen3-coder-next",
        task_id="IQ-1",
        task_revision=semantic_attempt_module.TASKS_BY_ID["IQ-1"].task_revision,
        dispatch_evidence_code=next(iter(semantic_attempt_module.INDETERMINATE_EVIDENCE_CODES)),
        gate_statuses={},
        observed_pi_version=None,
        compatibility_facts={},
        compatibility_gate_passed=True,
        route_provenance={},
        closure={},
    )
    assert result is sentinel


def test_emit_attempt_or_refuse_persists_exactly_what_its_own_gate_validated(
    monkeypatch, tmp_path: Path
):
    """The same structural proof for ``emit_attempt_or_refuse``: whatever
    ``_require_valid_attempt_payload`` returns is what is handed to
    ``emit_evidence_or_refuse`` for the scrub and the write -- never the
    original ``record`` parameter."""
    sentinel = {
        "record_kind": ATTEMPT_RECORD_KIND,
        "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
        "sentinel": True,
    }

    def _fake_gate(record):
        return sentinel

    monkeypatch.setattr(
        semantic_attempt_module, "_require_valid_attempt_payload", _fake_gate
    )
    target = tmp_path / "sentinel_attempt.json"
    original_record = {"this is": "the caller's own object, never persisted"}
    result = emit_attempt_or_refuse(original_record, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written == sentinel
    assert "this is" not in target.read_text(encoding="utf-8")


# -- Positive controls: the FU3 fix must not disturb a genuine payload ------


def test_positive_control_a_genuine_attempt_record_still_emits_after_fu3(
    git_executable: str, tmp_path: Path
):
    payload = _genuine_attempt_record(git_executable, tmp_path)
    target = tmp_path / "genuine_attempt_fu3.json"
    result = emit_attempt_or_refuse(payload, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["record_kind"] == ATTEMPT_RECORD_KIND
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION


def test_positive_control_build_attempt_record_still_round_trips_through_emission(
    tmp_path: Path,
):
    """The builder's OWN return value -- the validated snapshot, per the
    FU3 contract -- must still be directly emittable."""
    task = semantic_attempt_module.TASKS_BY_ID["IQ-1"]
    evidence_code = next(iter(semantic_attempt_module.INDETERMINATE_EVIDENCE_CODES))
    route = semantic_attempt_module.route_descriptor_for_candidate("A")
    compat_names = sorted(semantic_attempt_module._COMPATIBILITY_FACT_NAMES)
    gate_statuses = {
        **{name: "PASSED" for name in semantic_attempt_module._PRE_PROMPT_GATE_NAMES},
        semantic_attempt_module._SEMANTIC_PROMPT_DISPATCH_GATE_NAME: (
            semantic_attempt_module._INDETERMINATE_DISPATCH_GATE_STATUS
        ),
        **{
            name: "NOT_REACHED"
            for name in semantic_attempt_module._POST_DISPATCH_UNREACHED_GATE_NAMES
        },
        "runtime_teardown": "NOT_REQUIRED",
        "broker_shutdown": "NOT_REQUIRED",
        "generated_config_cleanup": (
            semantic_attempt_module._GENERATED_CONFIG_CLEANUP_VERIFIED_STATUS
        ),
        "semantic_workspace_removal": (
            semantic_attempt_module._SEMANTIC_WORKSPACE_REMOVAL_VERIFIED_STATUS
        ),
    }
    closure = {
        "runtime_teardown": "NOT_REQUIRED",
        "broker_shutdown": "NOT_REQUIRED",
        "generated_config_cleanup": {
            "attempted": True,
            "scrub_verified": True,
            "classification": None,
        },
        "semantic_workspace_removal": {
            "attempted": True,
            "verified": True,
            "facts": dict(semantic_attempt_module._REMOVAL_FACTS_VERIFIED_SHAPE),
        },
        "closure_established": True,
    }
    built = build_attempt_record(
        candidate="A",
        model_id="qwen3-coder-next",
        task_id=task.task_id,
        task_revision=task.task_revision,
        dispatch_evidence_code=evidence_code,
        gate_statuses=gate_statuses,
        observed_pi_version="0.84.2-synthetic",
        compatibility_facts={name: True for name in compat_names},
        compatibility_gate_passed=True,
        route_provenance={
            "model_id": route.model_id,
            "provider_route": route.provider_id,
            "backend_gateway_class": route.backend_gateway_class,
        },
        closure=closure,
    )
    target = tmp_path / "builder_round_trip.json"
    result = emit_attempt_or_refuse(built, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert written["record_kind"] == ATTEMPT_RECORD_KIND


# ===========================================================================
# L. 5F3B-LIVE1-C4-FU4 -- BIND PRIMARY VALIDATION, SCRUB, AND PERSISTENCE TO
#    ONE SNAPSHOT
# ===========================================================================
# FU3 closed the TOCTOU between validation and persistence for the ATTEMPT
# artifact by making `_require_valid_attempt_payload` canonicalize its input
# through one `json.dumps`/`json.loads` round trip and RETURN that snapshot,
# with `build_attempt_record` and `emit_attempt_or_refuse` binding every
# downstream consumer to that one return value.
#
# The identical invariant was still missing on the PRIMARY artifact path.
# `records._require_valid_primary_payload` type-guarded the top-level record
# and compared `route_provenance` by serialized form, but its own nested
# `pi_runtime`/`verification`/`scope_result`/`report_accuracy` values were
# caller-owned Mapping objects, consulted independently by three different
# call sites: the invariant gate (via canonicalization once this section's
# fix lands, but PRE-FU4 not at all), the safety scrub
# (`qualification_scrub_check` -> `scrub_check`/`json.dumps`), and the
# exclusive-create writer (`json.dump`). A nested `dict` subclass whose
# `.items()` disagreed between those calls could pass a genuinely safe
# validation and scrub, and still have a LATER, secret-bearing or
# evidence-altering representation reach the immutable artifact.
#
# The fix mirrors FU3 exactly: `_require_valid_primary_payload` now
# canonicalizes `record` FIRST, and every one of its own checks -- plus the
# nested `route_provenance` comparison, which no longer needs its own
# separate defence -- runs against that snapshot. `build_qualification_record`
# and `emit_or_refuse` both bind every downstream consumer (the safety scrub,
# the writer) to EXACTLY that snapshot, never to their own local `record`
# variable. The caller's original record, and every one of its original
# nested objects, is read exactly once, ever.


def _minimal_primary_record_kwargs(**overrides) -> dict:
    """The same fixed keyword bundle :func:`_minimal_primary_record` builds
    from, exposed separately so a test can substitute an adversarial object
    for exactly one nested field before calling
    :func:`build_qualification_record` itself (``_minimal_primary_record``
    only forwards ``**overrides`` into ``build_qualification_record``, which
    is sufficient for a top-level substitution but this makes the intent at
    each call site explicit for a nested-field adversary)."""
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
        route_provenance={"model_id": "qwen3-coder-next"},
        verification={"passed": True},
        scope_result={"hard_refusal_count": 0},
        report_accuracy={"bucket": "ACCURATE"},
    )
    base.update(overrides)
    return base


# -- Adversarial regression 1: stateful nested SECRET bypass -----------------


def test_stateful_nested_verification_secret_cannot_reach_the_persisted_primary_artifact(
    tmp_path: Path,
):
    """Mandatory adversarial regression #1. A stateful ``verification``
    object whose ``.items()`` reports a genuine, secret-free payload on its
    FIRST call and a secret-bearing payload on every call after that.

    Pre-FU4, ``build_qualification_record`` validated call #1 (inside
    ``_require_valid_primary_payload``) and then returned its own local
    ``record`` variable -- still holding a live reference to the stateful
    ``verification`` object. A caller's subsequent ``emit_or_refuse`` would
    re-consult it via the scrub and the writer, each triggering a fresh
    ``.items()`` call -- call #2, reporting the secret, which would reach
    the immutable artifact even though the safety context declares it.
    Post-FU4 the object is read exactly once, ever, and the FIRST
    (safe) snapshot is what is validated, scrubbed, and persisted.
    """
    genuine_verification = {"passed": True}
    forged_verification = {"passed": True, "leaked": "sk-synthetic-secret-0000"}
    stateful = _StatefulItemsDict(genuine_verification, forged_verification)

    # Step 1: mechanically prove the adversary is real, BEFORE the supported
    # API is ever invoked.
    first_json = json.dumps(stateful, sort_keys=True)
    second_json = json.dumps(stateful, sort_keys=True)
    assert stateful.items_call_count == 2
    assert first_json != second_json
    assert "leaked" not in first_json
    assert "sk-synthetic-secret-0000" in second_json
    stateful.items_call_count = 0

    # Step 2: the supported build path.
    built = build_qualification_record(
        **_minimal_primary_record_kwargs(verification=stateful)
    )
    assert stateful.items_call_count == 1

    # Step 3: the supported emission path, with the secret declared.
    safety = ArtifactSafetyContext(api_key="sk-synthetic-secret-0000")
    target = tmp_path / "stateful_verification_secret.json"
    result = emit_or_refuse(built, path=str(target), safety=safety)

    # The FIRST (secret-free) snapshot was what got validated and scrubbed,
    # so it emits normally -- the LATER, secret-bearing representation is
    # never consulted again.
    assert result["emitted"] is True and result["refused"] is False
    assert stateful.items_call_count == 1

    on_disk = target.read_text(encoding="utf-8")
    assert "sk-synthetic-secret-0000" not in on_disk
    written = json.loads(on_disk)
    assert written["verification"] == genuine_verification


def test_stateful_nested_verification_secret_on_the_first_call_is_refused_not_the_second(
    tmp_path: Path,
):
    """The complementary ordering named by the follow-up prompt: "if the
    snapshot is unsafe, emit the bounded refusal." Here the FIRST
    serialization is the secret-bearing one and the SECOND (which a
    pre-FU4 scrub or writer would have re-read) is clean -- proving the
    refusal decision is made on the snapshot actually validated, not on
    whatever a later, coincidentally-safe read would report.
    """
    forged_verification = {"passed": True, "leaked": "sk-synthetic-secret-1111"}
    genuine_verification = {"passed": True}
    stateful = _StatefulItemsDict(forged_verification, genuine_verification)

    built = build_qualification_record(
        **_minimal_primary_record_kwargs(verification=stateful)
    )
    assert stateful.items_call_count == 1

    safety = ArtifactSafetyContext(api_key="sk-synthetic-secret-1111")
    target = tmp_path / "stateful_verification_secret_first.json"
    result = emit_or_refuse(built, path=str(target), safety=safety)

    assert result["refused"] is True
    assert stateful.items_call_count == 1
    on_disk = target.read_text(encoding="utf-8")
    assert "sk-synthetic-secret-1111" not in on_disk
    written = json.loads(on_disk)
    assert written["record_kind"] == "artifact emission refusal"


# -- Adversarial regression 2: stateful nested EVIDENCE/PROVENANCE mutation --


def test_stateful_nested_report_accuracy_mutation_cannot_alter_the_persisted_artifact(
    tmp_path: Path,
):
    """Mandatory adversarial regression #2. A stateful ``report_accuracy``
    object that would change an evidence claim -- ``bucket`` -- on a later
    serialization, with no secret involved at all. The retained artifact
    must equal the FIRST (validated) snapshot, never the later claim.
    """
    genuine_report_accuracy = {"bucket": "ACCURATE"}
    later_report_accuracy = {"bucket": "INACCURATE"}
    stateful = _StatefulItemsDict(genuine_report_accuracy, later_report_accuracy)

    first_json = json.dumps(stateful, sort_keys=True)
    second_json = json.dumps(stateful, sort_keys=True)
    assert first_json != second_json
    assert stateful.items_call_count == 2
    stateful.items_call_count = 0

    built = build_qualification_record(
        **_minimal_primary_record_kwargs(report_accuracy=stateful)
    )
    assert stateful.items_call_count == 1

    target = tmp_path / "stateful_report_accuracy.json"
    result = emit_or_refuse(built, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    assert stateful.items_call_count == 1

    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["report_accuracy"] == genuine_report_accuracy


def test_lying_scope_result_container_persists_its_real_storage_not_its_reported_lie(
    tmp_path: Path,
):
    """The DICT-SUBCLASS shape of the same adversary (as opposed to the
    call-count-stateful shape above): ``scope_result.get()`` reports zero
    hard refusals while its real storage -- what ``json.dump`` actually
    walks -- records three. The persisted artifact must reflect the real
    storage, never the ``.get()``-reported account of it.
    """
    lying_scope_result = _LyingDict(
        {"hard_refusal_count": 3}, {"hard_refusal_count": 0}
    )
    assert lying_scope_result.get("hard_refusal_count") == 0
    canonical = json.loads(json.dumps(lying_scope_result, sort_keys=True))
    assert canonical["hard_refusal_count"] == 3

    built = build_qualification_record(
        **_minimal_primary_record_kwargs(scope_result=lying_scope_result)
    )
    target = tmp_path / "lying_scope_result.json"
    result = emit_or_refuse(built, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["scope_result"] == {"hard_refusal_count": 3}


def test_lying_pi_runtime_container_on_the_primary_path_persists_its_real_storage(
    tmp_path: Path,
):
    """The identical dict-subclass adversary against ``pi_runtime`` on the
    PRIMARY path (the attempt path's own ``pi_runtime`` closure is proven in
    section J; this is the primary record's counterpart, which had no
    field-specific defence at all before this section)."""
    lying_pi_runtime = _LyingDict(
        {"observed_version": "0.1.0-real"}, {"observed_version": "9.9.9-reported"}
    )
    assert lying_pi_runtime.get("observed_version") == "9.9.9-reported"
    canonical = json.loads(json.dumps(lying_pi_runtime, sort_keys=True))
    assert canonical["observed_version"] == "0.1.0-real"

    built = build_qualification_record(
        **_minimal_primary_record_kwargs(pi_runtime=lying_pi_runtime)
    )
    target = tmp_path / "lying_pi_runtime_primary.json"
    result = emit_or_refuse(built, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["pi_runtime"] == {"observed_version": "0.1.0-real"}


# -- Adversarial regression 3: post-snapshot mutation ------------------------


def test_post_snapshot_mutation_of_the_original_primary_record_cannot_reach_the_artifact(
    tmp_path: Path,
):
    """Mandatory adversarial regression #3. Drives
    ``records._require_valid_primary_payload`` and
    ``safety.emit_evidence_or_refuse`` directly -- exactly the two halves
    ``emit_or_refuse`` composes -- to open the window between snapshot
    creation and persistence, and mutates the ORIGINAL caller record (and
    one of its original nested mappings) inside it. The retained artifact
    must reflect only the pre-mutation validated snapshot.
    """
    payload = _minimal_primary_record()
    mutable = dict(payload)
    mutable["verification"] = dict(payload["verification"])

    validated = records_module._require_valid_primary_payload(mutable)

    # The mutation happens AFTER the snapshot was produced and validated --
    # both a top-level replacement and a mutation of a nested mapping the
    # caller still holds a reference to.
    mutable["qualification_policy_revision"] = _FORGED
    mutable["task_id"] = "IQ-2"
    mutable["verification"]["leaked"] = "sk-synthetic-post-snapshot-0000"
    mutable.clear()

    target = tmp_path / "primary_post_snapshot_mutation.json"
    result = emit_evidence_or_refuse(
        validated, path=str(target), safety=NO_SECRETS, record_kind=RECORD_KIND
    )
    assert result["emitted"] is True and result["refused"] is False

    on_disk = target.read_text(encoding="utf-8")
    written = json.loads(on_disk)
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert written["task_id"] == "IQ-1"
    assert written["verification"] == {"passed": True}
    assert _FORGED not in on_disk
    assert "sk-synthetic-post-snapshot-0000" not in on_disk


def test_mutating_the_caller_dict_after_full_primary_emission_never_touches_the_written_file(
    tmp_path: Path,
):
    """The end-to-end, public-API counterpart: after ``emit_or_refuse``
    returns, mutating the caller's own dict (and a nested mapping inside it)
    must not be able to reach back into the artifact already retained on
    disk."""
    payload = _minimal_primary_record()
    mutable = dict(payload)
    mutable["scope_result"] = dict(payload["scope_result"])
    target = tmp_path / "primary_mutate_after_emit.json"
    result = emit_or_refuse(mutable, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    before = target.read_bytes()

    mutable["qualification_policy_revision"] = _FORGED
    mutable["scope_result"]["hard_refusal_count"] = 999
    mutable.clear()

    after = target.read_bytes()
    assert after == before


# -- Adversarial regression 4: writer-incompatible second representation ----


def test_primary_writer_incompatible_second_read_never_reaches_persistence(
    tmp_path: Path,
):
    """Mandatory adversarial regression #4. A stateful ``scope_result``
    object whose FIRST read is a genuinely valid, writer-safe shape and
    whose SECOND read -- the one a pre-FU4 scrub-then-writer sequence would
    have taken -- carries heterogeneous dict key types that
    ``sort_keys=True`` cannot serialize. Pre-FU4 this would have raised a
    bare ``TypeError`` inside ``write_evidence_exclusively``, AFTER the
    output file had already been exclusive-created, stranding a partial
    artifact. Post-FU4 the original object is never read a second time, so
    the writer only ever sees the validated, writer-safe snapshot.
    """
    genuine_scope_result = {"hard_refusal_count": 0}
    unserializable_scope_result = {"a": 1, 1: "a"}
    stateful = _StatefulItemsDict(genuine_scope_result, unserializable_scope_result)

    # Step 1: mechanically prove the adversary is real.
    first_json = json.dumps(stateful, sort_keys=True)
    assert json.loads(first_json) == genuine_scope_result
    with pytest.raises(TypeError):
        json.dumps(stateful, sort_keys=True)
    assert stateful.items_call_count == 2
    stateful.items_call_count = 0

    # Step 2: the supported build+emit path only ever takes the FIRST read.
    built = build_qualification_record(
        **_minimal_primary_record_kwargs(scope_result=stateful)
    )
    assert stateful.items_call_count == 1

    target = tmp_path / "primary_writer_incompatible_second_read.json"
    result = emit_or_refuse(built, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    assert stateful.items_call_count == 1
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["scope_result"] == genuine_scope_result


def test_a_primary_payload_the_writer_cannot_serialize_is_refused_before_any_file_exists(
    tmp_path: Path,
):
    """The non-stateful mechanical proof, independent of the call-count
    adversary above: an ORDINARY (non-stateful) hostile nested mapping with
    heterogeneous key types is refused at validation time, before any file
    is created -- never a bare ``TypeError`` escaping from inside the
    writer after ``open(path, "x")`` already succeeded."""
    hostile = {"a": 1, 1: "a"}
    json.dumps(hostile)  # succeeds -- no ordering is required
    with pytest.raises(TypeError):
        json.dumps(hostile, sort_keys=True)  # the writer's own config

    payload = _minimal_primary_record()
    forged = dict(payload)
    forged["scope_result"] = hostile

    target = tmp_path / "primary_hostile_sort_keys.json"
    with pytest.raises(RecordInvariantError):
        emit_or_refuse(forged, path=str(target), safety=NO_SECRETS)
    _assert_nothing_written(target)


# -- Structural binding: validate object A, return/write object B -----------


def test_build_qualification_record_returns_exactly_the_gates_own_output(monkeypatch):
    """Mandatory adversarial self-review question: "Can the primary
    invariant validator ... return/write object B" while validating object
    A? Proven by substituting a distinguishable sentinel for the gate's
    return value and checking IDENTITY (``is``), not mere equality --
    ``build_qualification_record`` must return exactly that object, never a
    second, independently-constructed local variable that merely looks the
    same.
    """
    sentinel: dict[str, Any] = {"sentinel": "fu4-canonical-snapshot"}
    monkeypatch.setattr(
        records_module, "_require_valid_primary_payload", lambda record: sentinel
    )
    built = _minimal_primary_record()
    assert built is sentinel


def test_emit_or_refuse_hands_the_scrub_and_writer_exactly_the_gates_output(
    monkeypatch, tmp_path: Path
):
    """The emission-boundary half of the same structural proof:
    ``emit_or_refuse`` must call
    ``safety.emit_evidence_or_refuse`` with EXACTLY the object
    ``_require_valid_primary_payload`` returned -- never the original
    ``record`` argument, and never a second local reconstruction of it.
    """
    original = _minimal_primary_record()
    sentinel: dict[str, Any] = {"sentinel": "fu4-canonical-snapshot", "record_kind": RECORD_KIND}
    monkeypatch.setattr(
        records_module, "_require_valid_primary_payload", lambda record: sentinel
    )

    captured: dict[str, Any] = {}

    def fake_emit_evidence_or_refuse(payload, *, path, safety, record_kind):
        captured["payload"] = payload
        captured["is_original"] = payload is original
        captured["is_sentinel"] = payload is sentinel
        return {
            "emitted": True,
            "refused": False,
            "path": path,
            "scrub": {"scrub_checked": True, "findings": [], "clean": True},
        }

    monkeypatch.setattr(records_module, "emit_evidence_or_refuse", fake_emit_evidence_or_refuse)
    emit_or_refuse(original, path=str(tmp_path / "structural_emit.json"), safety=NO_SECRETS)
    assert captured["is_sentinel"] is True
    assert captured["is_original"] is False


# -- Positive controls: the FU4 fix must not disturb a genuine payload ------


def test_positive_control_a_genuine_primary_record_still_emits_after_fu4(tmp_path: Path):
    record = _minimal_primary_record()
    target = tmp_path / "genuine_primary_fu4.json"
    result = emit_or_refuse(record, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["record_kind"] == RECORD_KIND
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert written["verification"] == {"passed": True}
    assert written["scope_result"] == {"hard_refusal_count": 0}
    assert written["report_accuracy"] == {"bucket": "ACCURATE"}


def test_positive_control_build_qualification_record_snapshot_round_trips_through_emission(
    tmp_path: Path,
):
    """The builder's OWN return value -- the validated snapshot, per the
    FU4 contract -- must still be directly emittable, exactly as FU3
    established for the attempt artifact's builder."""
    built = build_qualification_record(**_minimal_primary_record_kwargs())
    target = tmp_path / "primary_builder_round_trip.json"
    result = emit_or_refuse(built, path=str(target), safety=NO_SECRETS)
    assert result["emitted"] is True and result["refused"] is False
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["qualification_policy_revision"] == QUALIFICATION_POLICY_REVISION
    assert written["record_kind"] == RECORD_KIND
