"""PE-2b: eligibility, floor/class conservativeness, evidence-reuse premises,
PMD structural validation and the N-1 reference rules.

Acceptance rows B-5, B-6, B-7, B-8 and B-9 of
``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 26.2,
with PE-0 Sec. 14.3 counterexamples 1, 13, 15, 16, Sec. 14.4 scenarios 4-7
and the Sec. 14.5 loader B9 test. Every chain is SYNTHETIC under
``tmp_path``. A loaded PMD proves structural completeness and consistency
ONLY -- never that a finding is true (PE-1 Sec. 10.5).
"""

from __future__ import annotations

import copy

import pytest
from pe2b_support import (
    Chain,
    Payload,
    PolicyWorld,
    approval,
    base_payload,
    internal_range_payload,
    key_reorder_payload,
    non_seam_payload,
    payload_scope,
    pmd_for,
    presence_change_payload,
    retirement,
    reuse,
    seam_change_payload,
    seam_evidence,
    seam_files_scope,
    two_profile_chain,
    version_bump_payload,
    whitespace_payload,
)

from pi_harness_cfg1.pi_payload import PI_SC1_PATHS
from pi_harness_cfg1.pi_profile_floor import FLOOR_C2, FLOOR_C3_SEAM_EQUAL, ReferenceView, classify_floor
from pi_harness_cfg1.pi_profile_policy_loader import Cfg1PolicyError


def _load(tmp_path, chain: Chain):
    world = PolicyWorld(tmp_path)
    world.write_chain(chain)
    return world.load()


def _refuses(tmp_path, chain: Chain, code: str | None = None) -> str:
    with pytest.raises(Cfg1PolicyError) as caught:
        _load(tmp_path, chain)
    if code is not None:
        assert caught.value.reason_code == code
    return caught.value.reason_code


def _with_a(cls: str = "C3_SEAM_CHANGED") -> tuple[Chain, Payload]:
    """r1: A approved, no seam evidence."""
    a = base_payload()
    chain = Chain()
    chain.revision(profiles=[a.profile()], approvals=[approval(a.profile_id, cls)], payloads=[a])
    return chain, a


def _add(chain: Chain, payload: Payload, cls: str, **kwargs) -> None:
    chain.revision(profiles=[payload.profile()], approvals=[approval(payload.profile_id, cls, **kwargs)], payloads=[payload])


# ---------------------------------------------------------------------------
# B-5 -- coexistence and retirement
# ---------------------------------------------------------------------------


def test_b5_two_approved_profiles_coexist_and_each_has_its_own_view(tmp_path):
    chain, a, b = two_profile_chain()
    load = _load(tmp_path, chain)
    assert load.snapshot.eligible_profile_ids == frozenset({a.profile_id, b.profile_id})
    views = {view.profile_id: view for view in load.snapshot.eligible_profiles}
    assert views[a.profile_id].payload_fingerprint == a.fingerprint
    assert views[b.profile_id].payload_fingerprint == b.fingerprint
    assert a.fingerprint != b.fingerprint
    assert views[a.profile_id].declared_package_version == "1.0.0"
    assert views[b.profile_id].declared_package_version == "1.0.1"
    assert [entry[2] for entry in load.revisions] == [
        frozenset({a.profile_id}),
        frozenset({a.profile_id, b.profile_id}),
    ]


def test_b5_retirement_removes_eligibility_from_its_revision_on_only(tmp_path):
    chain, a, b = two_profile_chain()
    chain.revision(retirements=[retirement(a.profile_id, "SECURITY_ADVISORY")])
    load = _load(tmp_path / "full", chain)
    assert [entry[2] for entry in load.revisions] == [
        frozenset({a.profile_id}),
        frozenset({a.profile_id, b.profile_id}),
        frozenset({b.profile_id}),
    ]
    assert load.snapshot.eligible_profile_ids == frozenset({b.profile_id})
    # Earlier heads stay recomputable from the committed chain prefix.
    prefix = Chain()
    prefix.records = chain.records[:2]
    prefix.payloads = dict(chain.payloads)
    earlier = _load(tmp_path / "prefix", prefix)
    assert earlier.snapshot.eligible_profile_ids == frozenset({a.profile_id, b.profile_id})
    assert earlier.snapshot.aps_head_sha256 == load.revisions[1][1]


def test_b5_retirement_is_terminal_and_never_automatically_readmitted(tmp_path):
    chain, a, _b = two_profile_chain()
    chain.revision(retirements=[retirement(a.profile_id)])
    chain.revision(approvals=[approval(a.profile_id, "C3_SEAM_CHANGED", acceptance="READMIT")])
    _refuses(tmp_path, chain, "POLICY_DUPLICATE_APPROVAL_FOR_PROFILE")


def test_b5_a_retired_profile_re_entered_as_a_new_profile_record_refuses(tmp_path):
    chain, a, _b = two_profile_chain()
    chain.revision(retirements=[retirement(a.profile_id)])
    chain.revision(profiles=[a.profile()], approvals=[approval(a.profile_id, "C3_SEAM_CHANGED", acceptance="R2")])
    _refuses(tmp_path, chain, "POLICY_DUPLICATE_PAYLOAD_FINGERPRINT")


def test_b5_eligibility_is_exact_string_set_membership(tmp_path):
    chain, a, b = two_profile_chain()
    snapshot = _load(tmp_path, chain).snapshot
    assert type(snapshot.eligible_profile_ids) is frozenset
    assert all(type(item) is str for item in snapshot.eligible_profile_ids)
    assert a.profile_id.upper() not in snapshot.eligible_profile_ids
    assert a.profile_id[:63] not in snapshot.eligible_profile_ids


# ---------------------------------------------------------------------------
# B-6 -- floor / class conservativeness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", ["C2_MANIFEST_ONLY", "C2_MANIFEST_DELTA_REACQUIRED"])
def test_b6_counterexample_1_labelled_c2_refuses(tmp_path, cls):
    chain, a = _with_a()
    x = non_seam_payload()
    _add(chain, x, cls)
    _refuses(tmp_path / "no_pmd", chain, "POLICY_APPROVAL_CLASS_BELOW_FLOOR")
    chain, a = _with_a()
    _add(chain, x, cls, pmd=None)
    _refuses(tmp_path / "pmd", chain, "POLICY_APPROVAL_CLASS_BELOW_FLOOR")


def test_b6_counterexample_1_floor_is_c3_seam_equal_and_loads_at_that_class(tmp_path):
    chain, a = _with_a()
    x = non_seam_payload()
    view = ReferenceView(eligible=[a.facts], present_ineligible_profile_ids=(), seam_fingerprints=())
    assert classify_floor(x.facts, view) == FLOOR_C3_SEAM_EQUAL
    _add(chain, x, "C3_SEAM_EQUAL")
    assert _load(tmp_path, chain).snapshot.eligible_profile_ids == frozenset({a.profile_id, x.profile_id})


def test_b6_an_understated_seam_class_refuses(tmp_path):
    chain, _a = _with_a()
    x = seam_change_payload()
    _add(chain, x, "C3_SEAM_EQUAL")
    _refuses(tmp_path / "under", chain, "POLICY_APPROVAL_CLASS_BELOW_FLOOR")
    chain, _a = _with_a()
    _add(chain, x, "C3_SEAM_CHANGED")
    _load(tmp_path / "ok", chain)


def test_b6_a_first_profile_with_no_reference_is_at_least_c3_seam_changed(tmp_path):
    a = base_payload()
    for cls in ("C2_MANIFEST_ONLY", "C2_MANIFEST_DELTA_REACQUIRED", "C3_SEAM_EQUAL"):
        chain = Chain()
        chain.revision(profiles=[a.profile()], approvals=[approval(a.profile_id, cls)], payloads=[a])
        _refuses(tmp_path / cls, chain, "POLICY_APPROVAL_CLASS_BELOW_FLOOR")


def test_b6_seam_evidence_added_in_the_same_revision_counts_for_the_floor(tmp_path):
    a = base_payload()
    chain = Chain()
    chain.revision(
        seam_evidence=[seam_evidence(a.facts.seam_digests_dict())],
        profiles=[a.profile()],
        approvals=[approval(a.profile_id, "C3_SEAM_EQUAL")],
        payloads=[a],
    )
    _load(tmp_path, chain)


@pytest.mark.parametrize("cls", ["C4_CONTRACT_REVISED", "CC_REAPPROVAL"])
def test_b6_reserved_classes_refuse_under_cfg1_cc1(tmp_path, cls):
    chain, _a = _with_a(cls)
    _refuses(tmp_path, chain, "POLICY_QUALIFICATION_CLASS_RESERVED_FOR_FUTURE_CONTRACT")


@pytest.mark.parametrize("cls", ["C1", "C2", "C3", "c3_seam_changed", "C5", "APPROVED", "", None, 3])
def test_b6_unknown_classes_refuse(tmp_path, cls):
    chain, _a = _with_a(cls)
    _refuses(tmp_path, chain, "POLICY_QUALIFICATION_CLASS_UNKNOWN")


def test_b6_escalation_is_allowed_and_pmd_still_required_for_a_c2_floor(tmp_path):
    chain, a = _with_a()
    b = version_bump_payload()
    _add(chain, b, "C3_SEAM_CHANGED", pmd=pmd_for(b, a))
    _load(tmp_path / "ok", chain)
    chain, a = _with_a()
    _add(chain, b, "C3_SEAM_CHANGED")
    _refuses(tmp_path / "no_pmd", chain, "POLICY_PMD_REQUIRED")


def _manual_presence_pmd(candidate: Payload, reference: Payload) -> dict:
    """A PMD claiming an INTERNAL_DEPENDENCY delta for a key absent on one side."""
    template = pmd_for(version_bump_payload(), reference)
    raw = copy.deepcopy(template["deltas"][0])
    raw["old"] = reference.facts.inventory.entry("package.json")[2]
    raw["new"] = candidate.facts.inventory.entry("package.json")[2]
    dep = copy.deepcopy(template["deltas"][1])
    dep.update(delta="INTERNAL_DEPENDENCY:@earendil-works/pi-agent-core", old="^1.0.0", new="")
    return dict(template, deltas=[raw, dep])


@pytest.mark.parametrize("cls", ["C2_MANIFEST_ONLY", "C2_MANIFEST_DELTA_REACQUIRED"])
def test_b6_pe0_b9_loader_test_presence_change_labelled_c2_refuses(tmp_path, cls):
    chain, a = _with_a()
    x = presence_change_payload()
    _add(chain, x, cls, pmd=_manual_presence_pmd(x, a))
    _refuses(tmp_path, chain, "POLICY_APPROVAL_CLASS_BELOW_FLOOR")


def test_b6_pe0_b9_a_pmd_for_a_presence_change_never_matches(tmp_path):
    chain, a = _with_a()
    x = presence_change_payload()
    _add(chain, x, "C3_SEAM_CHANGED", pmd=_manual_presence_pmd(x, a))
    _refuses(tmp_path / "c3", chain, "POLICY_PMD_NOT_PERMITTED")
    chain, a = _with_a()
    _add(chain, x, "C3_SEAM_CHANGED", reused=[reuse("E3", a.profile_id, payload_scope())], pmd=_manual_presence_pmd(x, a))
    _refuses(tmp_path / "forced", chain, "POLICY_PMD_REFERENCE_NOT_C2")


def test_b6_a_key_reorder_labelled_c2_refuses(tmp_path):
    chain, a = _with_a()
    x = key_reorder_payload()
    _add(chain, x, "C2_MANIFEST_ONLY")
    _refuses(tmp_path, chain, "POLICY_APPROVAL_CLASS_BELOW_FLOOR")


def test_b6_version_strings_never_choose_the_class(tmp_path):
    """Same version text, non-manifest change: still C3; different version
    text, manifest-only change: C2. The version value decides nothing."""
    chain, a = _with_a()
    same_version_other_bytes = seam_change_payload("dist/core/sdk.js")
    assert same_version_other_bytes.facts.declared_dict() == a.facts.declared_dict()
    _add(chain, same_version_other_bytes, "C2_MANIFEST_ONLY")
    _refuses(tmp_path / "same_version", chain, "POLICY_APPROVAL_CLASS_BELOW_FLOOR")
    chain, a = _with_a()
    b = version_bump_payload("0.0.1-older")
    _add(chain, b, "C2_MANIFEST_ONLY", pmd=pmd_for(b, a))
    _load(tmp_path / "downgrade_text_is_still_c2", chain)


# ---------------------------------------------------------------------------
# B-7 -- evidence reuse premises
# ---------------------------------------------------------------------------


def test_b7_counterexample_13_seam_files_premise_verifies(tmp_path):
    chain, a = _with_a()
    x = non_seam_payload()
    assert x.facts.seam_fingerprint == a.facts.seam_fingerprint and x.profile_id != a.profile_id
    _add(chain, x, "C3_SEAM_EQUAL", reused=[reuse("E1", a.profile_id, seam_files_scope(PI_SC1_PATHS))])
    load = _load(tmp_path, chain)
    assert load.snapshot.eligible_profile_ids == frozenset({a.profile_id, x.profile_id})


def test_b7_counterexample_13_payload_premise_fails(tmp_path):
    chain, a = _with_a()
    x = non_seam_payload()
    _add(chain, x, "C3_SEAM_EQUAL", reused=[reuse("E3", a.profile_id, payload_scope())])
    _refuses(tmp_path / "no_pmd", chain, "POLICY_PMD_REQUIRED")
    chain, a = _with_a()
    forged_pmd = pmd_for(version_bump_payload(), a)
    _add(chain, x, "C3_SEAM_EQUAL", reused=[reuse("E3", a.profile_id, payload_scope())], pmd=forged_pmd)
    _refuses(tmp_path / "pmd", chain, "POLICY_PMD_REFERENCE_NOT_C2")


@pytest.mark.parametrize("kind", ["E3", "E4", "E5", "E6"])
def test_b7_counterexample_15_reuse_with_a_clean_complete_pmd_loads(tmp_path, kind):
    chain, a = _with_a()
    b = version_bump_payload()
    _add(chain, b, "C2_MANIFEST_ONLY", reused=[reuse(kind, a.profile_id, payload_scope())], pmd=pmd_for(b, a, reuse_count=1))
    load = _load(tmp_path, chain)
    assert load.snapshot.eligible_profile_ids == frozenset({a.profile_id, b.profile_id})


def test_b7_counterexample_15_reuse_without_or_with_incomplete_pmd_refuses(tmp_path):
    chain, a = _with_a()
    b = version_bump_payload()
    _add(chain, b, "C2_MANIFEST_ONLY", reused=[reuse("E6", a.profile_id, payload_scope())])
    _refuses(tmp_path / "absent", chain, "POLICY_PMD_REQUIRED")
    chain, a = _with_a()
    _add(chain, b, "C2_MANIFEST_ONLY", reused=[reuse("E6", a.profile_id, payload_scope())], pmd=pmd_for(b, a, reuse_count=0))
    _refuses(tmp_path / "incomplete", chain, "POLICY_PMD_EVIDENCE_EFFECT_KEYS")


def test_b7_counterexample_15_eligibility_never_arises_from_the_sources_approval(tmp_path):
    chain, a = _with_a()
    b = version_bump_payload()
    chain.revision(profiles=[b.profile()], payloads=[b])
    _refuses(tmp_path, chain, "POLICY_PROFILE_WITHOUT_APPROVAL")


@pytest.mark.parametrize(
    "path",
    [
        "node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js",
        "dist/core/agent-session.js",
    ],
)
def test_b7_counterexample_16_changed_harness_premise_is_not_reusable(tmp_path, path):
    chain, a = _with_a()
    x = seam_change_payload(path)
    _add(chain, x, "C3_SEAM_CHANGED", reused=[reuse("E6", a.profile_id, payload_scope())])
    _refuses(tmp_path / "no_pmd", chain, "POLICY_PMD_REQUIRED")
    chain, a = _with_a()
    _add(
        chain,
        x,
        "C3_SEAM_CHANGED",
        reused=[reuse("E6", a.profile_id, payload_scope())],
        pmd=pmd_for(version_bump_payload(), a, reuse_count=1),
    )
    _refuses(tmp_path / "pmd", chain, "POLICY_PMD_REFERENCE_NOT_C2")


def test_b7_seam_files_digest_mismatch_refuses_and_a_disjoint_subset_verifies(tmp_path):
    chain, a = _with_a()
    x = seam_change_payload("dist/main.js")
    _add(chain, x, "C3_SEAM_CHANGED", reused=[reuse("E1", a.profile_id, seam_files_scope(["dist/main.js"]))])
    _refuses(tmp_path / "bad", chain, "POLICY_REUSE_SEAM_PREMISE_FAILED")
    chain, a = _with_a()
    _add(chain, x, "C3_SEAM_CHANGED", reused=[reuse("E1", a.profile_id, seam_files_scope(["dist/cli.js", "dist/core/sdk.js"]))])
    _load(tmp_path / "ok", chain)


def test_b7_seam_files_reuse_from_genesis_style_seam_evidence(tmp_path):
    a = base_payload()
    evidence = seam_evidence(a.facts.seam_digests_dict())
    chain = Chain()
    chain.revision(seam_evidence=[evidence])
    _add(chain, a, "C3_SEAM_EQUAL", reused=[reuse("E1", evidence["evidence_id"], seam_files_scope(PI_SC1_PATHS))])
    _load(tmp_path / "ok", chain)
    other = dict(a.facts.seam_digests_dict())
    other["dist/cli.js"] = "99" * 32
    mismatched = seam_evidence(other)
    chain = Chain()
    chain.revision(seam_evidence=[mismatched])
    _add(chain, a, "C3_SEAM_CHANGED", reused=[reuse("E1", mismatched["evidence_id"], seam_files_scope(["dist/cli.js"]))])
    _refuses(tmp_path / "bad", chain, "POLICY_REUSE_SEAM_PREMISE_FAILED")


@pytest.mark.parametrize("kind", ["E3", "E4", "E5", "E6"])
def test_b7_non_e1_kinds_via_seam_files_refuse(tmp_path, kind):
    chain, a = _with_a()
    x = non_seam_payload()
    _add(chain, x, "C3_SEAM_EQUAL", reused=[reuse(kind, a.profile_id, seam_files_scope(["dist/cli.js"]))])
    _refuses(tmp_path, chain, "POLICY_REUSE_KIND_NOT_APPLICABLE_TO_PREMISE")


def test_b7_e1_via_payload_scope_refuses(tmp_path):
    chain, a = _with_a()
    b = version_bump_payload()
    _add(chain, b, "C2_MANIFEST_ONLY", reused=[reuse("E1", a.profile_id, payload_scope())], pmd=pmd_for(b, a, reuse_count=1))
    _refuses(tmp_path, chain, "POLICY_REUSE_KIND_NOT_APPLICABLE_TO_PREMISE")


@pytest.mark.parametrize("kind", ["E2", "E7", "E0", "E8", "e1", "PMD", "", None, 1])
def test_b7_unsupported_evidence_kinds_refuse(tmp_path, kind):
    chain, a = _with_a()
    x = non_seam_payload()
    _add(chain, x, "C3_SEAM_EQUAL", reused=[reuse(kind, a.profile_id, seam_files_scope(["dist/cli.js"]))])
    _refuses(tmp_path, chain, "POLICY_REUSE_EVIDENCE_KIND")


@pytest.mark.parametrize(
    "scope",
    [
        {"kind": "SEAM_FILES", "paths": []},
        {"kind": "SEAM_FILES", "paths": ["dist/main.js", "dist/cli.js"]},
        {"kind": "SEAM_FILES", "paths": ["dist/cli.js", "dist/cli.js"]},
        {"kind": "SEAM_FILES", "paths": ["dist/cli/setup.js"]},
        {"kind": "SEAM_FILES", "paths": ["DIST/CLI.JS"]},
        {"kind": "SEAM_FILES", "paths": "dist/cli.js"},
    ],
)
def test_b7_malformed_seam_files_paths_refuse(tmp_path, scope):
    chain, a = _with_a()
    x = non_seam_payload()
    _add(chain, x, "C3_SEAM_EQUAL", reused=[reuse("E1", a.profile_id, scope)])
    _refuses(tmp_path, chain, "POLICY_REUSE_SEAM_PATHS_MALFORMED")


@pytest.mark.parametrize(
    "scope",
    [
        {"kind": "SEAM_FILES"},
        {"kind": "PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS", "paths": ["dist/cli.js"]},
        {"kind": "SEAM_FILES:dist/cli.js"},
        {"kind": "ALL"},
        {},
        "SEAM_FILES",
    ],
)
def test_b7_malformed_premise_scopes_refuse(tmp_path, scope):
    chain, a = _with_a()
    x = non_seam_payload()
    _add(chain, x, "C3_SEAM_EQUAL", reused=[reuse("E1", a.profile_id, scope)])
    _refuses(tmp_path, chain, "POLICY_REUSE_PREMISE_MALFORMED")


def test_b7_a_retired_source_is_not_reusable(tmp_path):
    chain, a, b = two_profile_chain()
    chain.revision(retirements=[retirement(a.profile_id)])
    x = non_seam_payload()
    _add(chain, x, "C3_SEAM_EQUAL", reused=[reuse("E1", a.profile_id, seam_files_scope(["dist/cli.js"]))])
    _refuses(tmp_path, chain, "POLICY_REUSE_SOURCE_NOT_ELIGIBLE")


def test_b7_a_retired_pmd_reference_is_not_usable(tmp_path):
    chain, a = _with_a()
    chain.revision(retirements=[retirement(a.profile_id)])
    b = version_bump_payload()
    _add(chain, b, "C3_SEAM_CHANGED", reused=[reuse("E3", a.profile_id, payload_scope())], pmd=pmd_for(b, a, reuse_count=1))
    _refuses(tmp_path, chain, "POLICY_PMD_REFERENCE_NOT_ELIGIBLE")


def test_b7_an_unknown_or_ambiguous_source_refuses(tmp_path):
    chain, a = _with_a()
    x = non_seam_payload()
    _add(chain, x, "C3_SEAM_EQUAL", reused=[reuse("E1", "ab" * 32, seam_files_scope(["dist/cli.js"]))])
    _refuses(tmp_path, chain, "POLICY_REUSE_SOURCE_UNRESOLVED")


def test_b7_payload_reuse_from_a_seam_evidence_source_refuses(tmp_path):
    a = base_payload()
    evidence = seam_evidence(a.facts.seam_digests_dict())
    chain = Chain()
    chain.revision(seam_evidence=[evidence])
    _add(chain, a, "C3_SEAM_EQUAL")
    b = version_bump_payload()
    _add(
        chain,
        b,
        "C2_MANIFEST_ONLY",
        reused=[reuse("E3", evidence["evidence_id"], payload_scope())],
        pmd=pmd_for(b, a, reuse_count=1),
    )
    _refuses(tmp_path, chain, "POLICY_REUSE_SOURCE_NOT_A_PROFILE")


def test_b7_payload_reuse_whose_source_is_not_the_pmd_reference_refuses(tmp_path):
    """Rule 10: B (1.0.1) is C2 to both A (1.0.0) and A2 (1.0.2)."""
    chain, a = _with_a()
    a2 = version_bump_payload("1.0.2")
    _add(chain, a2, "C2_MANIFEST_ONLY", pmd=pmd_for(a2, a))
    b = version_bump_payload("1.0.1")
    _add(chain, b, "C2_MANIFEST_ONLY", reused=[reuse("E4", a2.profile_id, payload_scope())], pmd=pmd_for(b, a, reuse_count=1))
    _refuses(tmp_path / "mismatch", chain, "POLICY_REUSE_SOURCE_NOT_PMD_REFERENCE")
    chain, a = _with_a()
    _add(chain, a2, "C2_MANIFEST_ONLY", pmd=pmd_for(a2, a))
    _add(chain, b, "C2_MANIFEST_ONLY", reused=[reuse("E4", a2.profile_id, payload_scope())], pmd=pmd_for(b, a2, reuse_count=1))
    _load(tmp_path / "ok", chain)


def test_b7_conclusions_never_transfer_the_reused_source_stays_a_separate_profile(tmp_path):
    chain, a = _with_a()
    b = version_bump_payload()
    _add(chain, b, "C2_MANIFEST_ONLY", reused=[reuse("E6", a.profile_id, payload_scope())], pmd=pmd_for(b, a, reuse_count=1))
    chain.revision(retirements=[retirement(b.profile_id)])
    snapshot = _load(tmp_path, chain).snapshot
    assert snapshot.eligible_profile_ids == frozenset({a.profile_id})


# ---------------------------------------------------------------------------
# B-8 -- PMD completeness and consistency (Sec. 10.4 rules 1-10)
# ---------------------------------------------------------------------------


def _pmd_chain(candidate: Payload, pmd: dict, cls: str = "C2_MANIFEST_ONLY", reused=None) -> Chain:
    chain, _a = _with_a()
    _add(chain, candidate, cls, pmd=pmd, reused=reused)
    return chain


def _clean(candidate: Payload, **kwargs) -> dict:
    return pmd_for(candidate, base_payload(), **kwargs)


def test_b8_scenario_4_internal_range_change(tmp_path):
    x = internal_range_payload()
    pmd = _clean(x)
    labels = [delta["delta"] for delta in pmd["deltas"]]
    assert labels == ["RAW_BYTES", "INTERNAL_DEPENDENCY:@earendil-works/pi-ai"]
    _load(tmp_path / "ok", _pmd_chain(x, pmd))
    omitted = dict(pmd, deltas=pmd["deltas"][:1])
    _refuses(tmp_path / "omitted", _pmd_chain(x, omitted), "POLICY_PMD_DELTAS_MISMATCH")
    affected = _clean(x, cfg1="AFFECTED")
    _refuses(tmp_path / "only", _pmd_chain(x, affected, "C2_MANIFEST_ONLY"), "POLICY_PMD_CLASS_INADMISSIBLE")
    _load(tmp_path / "reacquired", _pmd_chain(x, affected, "C2_MANIFEST_DELTA_REACQUIRED"))
    _load(tmp_path / "escalated", _pmd_chain(x, affected, "C3_SEAM_CHANGED"))


def test_b8_scenario_5_version_change_without_raw_bytes_refuses(tmp_path):
    x = version_bump_payload()
    pmd = _clean(x)
    assert [delta["delta"] for delta in pmd["deltas"]] == ["RAW_BYTES", "VERSION"]
    _refuses(tmp_path, _pmd_chain(x, dict(pmd, deltas=pmd["deltas"][1:])), "POLICY_PMD_DELTAS_MISMATCH")


def test_b8_scenario_6_whitespace_only_is_c2_with_exactly_one_raw_bytes(tmp_path):
    x = whitespace_payload()
    pmd = _clean(x)
    assert [delta["delta"] for delta in pmd["deltas"]] == ["RAW_BYTES"]
    _load(tmp_path / "ok", _pmd_chain(x, pmd))
    _refuses(tmp_path / "empty", _pmd_chain(x, dict(pmd, deltas=[])), "POLICY_PMD_DELTAS_MISMATCH")


def test_b8_scenario_7_affected_reused_evidence_refuses(tmp_path):
    x = version_bump_payload()
    reused = [reuse("E6", base_payload().profile_id, payload_scope())]
    pmd = _clean(x, reuse_count=1)
    _load(tmp_path / "ok", _pmd_chain(x, pmd, reused=reused))
    bad = copy.deepcopy(pmd)
    bad["deltas"][0]["evidence_effect"]["0"] = "AFFECTED"
    bad["deltas"][0]["categories"]["RPC_BEHAVIOR"] = {"finding": "AFFECTS", "refs": [dict(pmd["conclusion_refs"][0])]}
    _refuses(tmp_path / "affected", _pmd_chain(x, bad, "C2_MANIFEST_DELTA_REACQUIRED", reused), "POLICY_PMD_REUSED_EVIDENCE_AFFECTED")
    inconsistent = copy.deepcopy(pmd)
    inconsistent["deltas"][1]["evidence_effect"]["0"] = "AFFECTED"
    _refuses(tmp_path / "inconsistent", _pmd_chain(x, inconsistent, reused=reused), "POLICY_PMD_CONSISTENCY_RULE")
    omitted = copy.deepcopy(pmd)
    del omitted["deltas"][0]["evidence_effect"]["0"]
    _refuses(tmp_path / "omitted", _pmd_chain(x, omitted, reused=reused), "POLICY_PMD_EVIDENCE_EFFECT_KEYS")


def _mutated(pmd: dict, mutate) -> dict:
    result = copy.deepcopy(pmd)
    mutate(result)
    return result


_REF = {"repo_path": "docs/review/x.md", "sha256": "ab" * 32}


@pytest.mark.parametrize(
    "mutate, code",
    [
        # Rule 1: exact list -- order, values, extras.
        (lambda p: p["deltas"].reverse(), "POLICY_PMD_DELTAS_MISMATCH"),
        (lambda p: p["deltas"].append(copy.deepcopy(p["deltas"][1])), "POLICY_PMD_DELTAS_MISMATCH"),
        (lambda p: p["deltas"][1].update(new="1.0.2"), "POLICY_PMD_DELTAS_MISMATCH"),
        (lambda p: p["deltas"][1].update(old="1.0.1", new="1.0.0"), "POLICY_PMD_DELTAS_MISMATCH"),
        (lambda p: p["deltas"][0].update(old="00" * 32), "POLICY_PMD_DELTAS_MISMATCH"),
        (lambda p: p["deltas"][0].update(manifest_path="node_modules/@earendil-works/pi-ai/package.json"), "POLICY_PMD_DELTAS_MISMATCH"),
        (lambda p: p["deltas"][1].update(delta="INTERNAL_DEPENDENCY:@earendil-works/pi-ai"), "POLICY_PMD_DELTAS_MISMATCH"),
        # Rule 2: parsed-field finding.
        (lambda p: p["deltas"][0].update(read_as_parsed_field={"finding": "NOT_READ", "refs": [_REF]}), "POLICY_PMD_PARSED_FIELD_RULE"),
        (lambda p: p["deltas"][0].update(read_as_parsed_field={"finding": "NOT_APPLICABLE", "refs": [_REF]}), "POLICY_PMD_PARSED_FIELD_RULE"),
        (lambda p: p["deltas"][1].update(read_as_parsed_field={"finding": "NOT_APPLICABLE", "refs": []}), "POLICY_PMD_PARSED_FIELD_RULE"),
        (lambda p: p["deltas"][1].update(read_as_parsed_field={"finding": "NOT_READ", "refs": []}), "POLICY_PMD_PARSED_FIELD_RULE"),
        (lambda p: p["deltas"][1].update(read_as_parsed_field={"finding": "READ", "refs": []}), "POLICY_PMD_PARSED_FIELD_RULE"),
        # Rule 3: raw-manifest search refs, same finding per manifest.
        (lambda p: p["deltas"][0].update(read_as_raw_manifest={"finding": "NOT_READ", "refs": []}), "POLICY_PMD_RAW_MANIFEST_RULE"),
        (lambda p: p["deltas"][1].update(read_as_raw_manifest={"finding": "READ", "refs": [_REF]}), "POLICY_PMD_RAW_MANIFEST_RULE"),
        (lambda p: p["deltas"][0].update(read_as_raw_manifest={"finding": "NOT_APPLICABLE", "refs": [_REF]}), "POLICY_PMD_FINDING_VALUE"),
        # Rule 4: every category present; refs empty iff NOT_REACHED.
        (lambda p: p["deltas"][0]["categories"].pop("NETWORK_BEHAVIOR"), "POLICY_PMD_CATEGORY_KEYS"),
        (lambda p: p["deltas"][0]["categories"].update(EXTRA_CATEGORY={"finding": "NOT_REACHED", "refs": []}), "POLICY_PMD_CATEGORY_KEYS"),
        (lambda p: p["deltas"][0]["categories"].update(FEATURE_GATES={"finding": "NOT_REACHED", "refs": [_REF]}), "POLICY_PMD_CATEGORY_RULE"),
        (lambda p: p["deltas"][0]["categories"].update(FEATURE_GATES={"finding": "REACHED_NO_EFFECT", "refs": []}), "POLICY_PMD_CATEGORY_RULE"),
        (lambda p: p["deltas"][0]["categories"].update(FEATURE_GATES={"finding": "MAYBE", "refs": [_REF]}), "POLICY_PMD_FINDING_VALUE"),
        # Rule 5: exactly one evidence_effect key per reused item.
        (lambda p: p["deltas"][0]["evidence_effect"].update({"0": "NOT_AFFECTED"}), "POLICY_PMD_EVIDENCE_EFFECT_KEYS"),
        (lambda p: p["deltas"][0].update(evidence_effect=[]), "POLICY_PMD_EVIDENCE_EFFECT_MALFORMED"),
        # Rule 6: AFFECTS <=> cfg1_cc1_effect AFFECTED (no reuse here).
        (lambda p: p["deltas"][0]["categories"].update(REQUEST_SHAPE={"finding": "AFFECTS", "refs": [_REF]}), "POLICY_PMD_CONSISTENCY_RULE"),
        (lambda p: p["deltas"][0].update(cfg1_cc1_effect="AFFECTED"), "POLICY_PMD_CONSISTENCY_RULE"),
        (lambda p: p["deltas"][0].update(cfg1_cc1_effect="UNKNOWN"), "POLICY_PMD_EFFECT_VALUE"),
        # Schema and conclusion refs.
        (lambda p: p.update(conclusion_refs=[]), "POLICY_REFS_EMPTY"),
        (lambda p: p.update(extra=True), "POLICY_PMD_KEYS"),
        (lambda p: p["deltas"][0].update(verdict="INERT"), "POLICY_PMD_DELTA_KEYS"),
        (lambda p: p["deltas"][0].update(delta="SCRIPTS"), "POLICY_PMD_DELTA_LABEL"),
        (lambda p: p.update(reference_profile_id="AB" * 32), "POLICY_PMD_REFERENCE_MALFORMED"),
    ],
)
def test_b8_every_rule_violated_in_turn_refuses(tmp_path, mutate, code):
    x = version_bump_payload()
    _refuses(tmp_path, _pmd_chain(x, _mutated(_clean(x), mutate)), code)


def test_b8_rule_6_and_8_consistent_affected_pmd_is_inadmissible_as_manifest_only(tmp_path):
    x = version_bump_payload()
    affected = _clean(x, cfg1="AFFECTED")
    _refuses(tmp_path / "only", _pmd_chain(x, affected, "C2_MANIFEST_ONLY"), "POLICY_PMD_CLASS_INADMISSIBLE")
    _load(tmp_path / "reacquired", _pmd_chain(x, affected, "C2_MANIFEST_DELTA_REACQUIRED"))


def test_b8_pmd_present_when_not_required_and_absent_when_required(tmp_path):
    chain, a = _with_a()
    x = non_seam_payload()
    _add(chain, x, "C3_SEAM_EQUAL", pmd=pmd_for(version_bump_payload(), a))
    _refuses(tmp_path / "present", chain, "POLICY_PMD_NOT_PERMITTED")
    x = version_bump_payload()
    _refuses(tmp_path / "absent", _pmd_chain(x, None), "POLICY_PMD_REQUIRED")


def test_b8_a_false_pmd_reference_refuses(tmp_path):
    """The reference must be eligible in N-1 AND C2-related to the candidate."""
    chain, a = _with_a()
    s = seam_change_payload()
    _add(chain, s, "C3_SEAM_CHANGED")
    b = version_bump_payload()
    pmd = pmd_for(b, a)
    pmd["reference_profile_id"] = s.profile_id
    _add(chain, b, "C2_MANIFEST_ONLY", pmd=pmd)
    _refuses(tmp_path / "not_c2", chain, "POLICY_PMD_REFERENCE_NOT_C2")
    chain, a = _with_a()
    pmd = pmd_for(b, a)
    pmd["reference_profile_id"] = "ab" * 32
    _add(chain, b, "C2_MANIFEST_ONLY", pmd=pmd)
    _refuses(tmp_path / "unknown", chain, "POLICY_PMD_REFERENCE_NOT_ELIGIBLE")


def test_b8_findings_are_never_proven_true_only_consistent(tmp_path):
    """A structurally complete PMD asserting NOT_READ everywhere loads: the
    loader cannot know whether that is true (Sec. 10.5, R-REVIEW)."""
    x = internal_range_payload()
    pmd = _clean(x)
    assert {delta["read_as_raw_manifest"]["finding"] for delta in pmd["deltas"]} == {"NOT_READ"}
    _load(tmp_path, _pmd_chain(x, pmd))


# ---------------------------------------------------------------------------
# B-9 -- references resolve against N-1; no self or sibling bootstrap
# ---------------------------------------------------------------------------


def test_b9_an_approval_citing_a_same_revision_profile_refuses(tmp_path):
    a = base_payload()
    b = version_bump_payload()
    chain = Chain()
    chain.revision(
        profiles=[a.profile(), b.profile()],
        approvals=[
            approval(a.profile_id, "C3_SEAM_CHANGED"),
            approval(b.profile_id, "C3_SEAM_CHANGED", reused=[reuse("E1", a.profile_id, seam_files_scope(["dist/cli.js"]))]),
        ],
        payloads=[a, b],
    )
    _refuses(tmp_path / "reuse", chain, "POLICY_REUSE_SOURCE_NOT_ELIGIBLE")
    chain = Chain()
    chain.revision(
        profiles=[a.profile(), b.profile()],
        approvals=[approval(a.profile_id, "C3_SEAM_CHANGED"), approval(b.profile_id, "C2_MANIFEST_ONLY", pmd=pmd_for(b, a))],
        payloads=[a, b],
    )
    _refuses(tmp_path / "floor", chain, "POLICY_APPROVAL_CLASS_BELOW_FLOOR")
    chain = Chain()
    chain.revision(
        profiles=[a.profile(), b.profile()],
        approvals=[approval(a.profile_id, "C3_SEAM_CHANGED"), approval(b.profile_id, "C3_SEAM_CHANGED", pmd=pmd_for(b, a))],
        payloads=[a, b],
    )
    _refuses(tmp_path / "pmd", chain, "POLICY_PMD_NOT_PERMITTED")


def test_b9_two_new_independent_profiles_in_one_revision_load(tmp_path):
    a = base_payload()
    s = seam_change_payload()
    chain = Chain()
    chain.revision(
        profiles=[a.profile(), s.profile()],
        approvals=[approval(s.profile_id, "C3_SEAM_CHANGED"), approval(a.profile_id, "C3_SEAM_CHANGED")],
        payloads=[a, s],
    )
    assert _load(tmp_path, chain).snapshot.eligible_profile_ids == frozenset({a.profile_id, s.profile_id})


def test_b9_self_reference_refuses(tmp_path):
    a = base_payload()
    chain = Chain()
    chain.revision(
        profiles=[a.profile()],
        approvals=[approval(a.profile_id, "C3_SEAM_CHANGED", reused=[reuse("E1", a.profile_id, seam_files_scope(["dist/cli.js"]))])],
        payloads=[a],
    )
    _refuses(tmp_path / "reuse", chain, "POLICY_REUSE_SOURCE_NOT_ELIGIBLE")


def test_b9_a_profile_without_its_approval_refuses(tmp_path):
    a = base_payload()
    chain = Chain()
    chain.revision(profiles=[a.profile()], payloads=[a])
    _refuses(tmp_path / "alone", chain, "POLICY_PROFILE_WITHOUT_APPROVAL")
    chain.revision(approvals=[approval(a.profile_id, "C3_SEAM_CHANGED")])
    _refuses(tmp_path / "late", chain, "POLICY_PROFILE_WITHOUT_APPROVAL")


def test_b9_an_approval_without_a_profile_refuses(tmp_path):
    chain = Chain()
    chain.revision(approvals=[approval("ab" * 32, "C3_SEAM_CHANGED")])
    _refuses(tmp_path, chain, "POLICY_APPROVAL_PROFILE_NOT_IN_REVISION")


def test_b9_a_second_approval_refuses_in_the_same_or_a_later_revision(tmp_path):
    a = base_payload()
    chain = Chain()
    chain.revision(
        profiles=[a.profile()],
        approvals=[approval(a.profile_id, "C3_SEAM_CHANGED"), approval(a.profile_id, "C3_SEAM_CHANGED", acceptance="TWICE")],
        payloads=[a],
    )
    _refuses(tmp_path / "same", chain, "POLICY_DUPLICATE_APPROVAL_FOR_PROFILE")
    chain, a = _with_a()
    chain.revision(approvals=[approval(a.profile_id, "C3_SEAM_CHANGED", acceptance="AGAIN")])
    _refuses(tmp_path / "later", chain, "POLICY_DUPLICATE_APPROVAL_FOR_PROFILE")
    chain = Chain()
    duplicate = approval(a.profile_id, "C3_SEAM_CHANGED")
    chain.revision(profiles=[a.profile()], approvals=[duplicate, duplicate], payloads=[a])
    _refuses(tmp_path / "identical", chain, "POLICY_DUPLICATE_APPROVAL_ID")


def test_b9_a_duplicate_profile_or_payload_fingerprint_refuses(tmp_path):
    a = base_payload()
    chain = Chain()
    chain.revision(
        profiles=[a.profile(), a.profile()],
        approvals=[approval(a.profile_id, "C3_SEAM_CHANGED")],
        payloads=[a],
    )
    _refuses(tmp_path / "same_revision", chain, "POLICY_DUPLICATE_PAYLOAD_FINGERPRINT")
    chain, a = _with_a()
    chain.revision(profiles=[a.profile()], approvals=[approval(a.profile_id, "C3_SEAM_CHANGED", acceptance="X")])
    _refuses(tmp_path / "later_revision", chain, "POLICY_DUPLICATE_PAYLOAD_FINGERPRINT")


def test_b9_retirement_of_a_never_eligible_profile_refuses(tmp_path):
    chain, _a = _with_a()
    chain.revision(retirements=[retirement("ab" * 32)])
    _refuses(tmp_path / "unknown", chain, "POLICY_RETIREMENT_TARGET_NOT_ELIGIBLE")
    a = base_payload()
    chain = Chain()
    chain.revision(
        profiles=[a.profile()],
        approvals=[approval(a.profile_id, "C3_SEAM_CHANGED")],
        retirements=[retirement(a.profile_id)],
        payloads=[a],
    )
    _refuses(tmp_path / "same_revision", chain, "POLICY_RETIREMENT_TARGET_NOT_ELIGIBLE")


def test_b9_retiring_twice_refuses(tmp_path):
    chain, a = _with_a()
    chain.revision(retirements=[retirement(a.profile_id)])
    chain.revision(retirements=[retirement(a.profile_id, "SUPERSEDED_BY_POLICY")])
    _refuses(tmp_path / "later", chain, "POLICY_DUPLICATE_RETIREMENT_FOR_PROFILE")
    chain, a = _with_a()
    chain.revision(retirements=[retirement(a.profile_id), retirement(a.profile_id, "DERIVATION_INVALIDATED")])
    _refuses(tmp_path / "same", chain, "POLICY_DUPLICATE_RETIREMENT_FOR_PROFILE")
    chain, a = _with_a()
    twice = retirement(a.profile_id)
    chain.revision(retirements=[twice, twice])
    _refuses(tmp_path / "identical", chain, "POLICY_DUPLICATE_RETIREMENT_ID")


@pytest.mark.parametrize("reason", ["EXPIRED", "operator_withdrawn", "", None])
def test_b9_retirement_reason_codes_are_closed(tmp_path, reason):
    chain, a = _with_a()
    chain.revision(retirements=[retirement(a.profile_id, reason)])
    _refuses(tmp_path, chain, "POLICY_RETIREMENT_REASON_CODE")


def test_b9_a_later_approval_never_changes_an_earlier_heads_eligible_set(tmp_path):
    chain, a, b = two_profile_chain()
    load = _load(tmp_path, chain)
    assert load.revisions[0][2] == frozenset({a.profile_id})
    assert load.revisions[0][1] != load.snapshot.aps_head_sha256
    assert FLOOR_C2 == "C2"  # the floor literal the second approval was verified at
