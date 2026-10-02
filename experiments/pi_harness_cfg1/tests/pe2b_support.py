"""Shared scaffolding for the PE-2b policy-authority regressions. Test-only.

Every policy chain here is SYNTHETIC: canonical policy files written under
pytest ``tmp_path`` from synthetic PE-2a payloads (inert bytes and JSON
manifests, never an installed Pi). Nothing here runs Node, Pi or npm, opens a
socket, reads a credential, or touches the genuine policy directory.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pe2a_support import (
    PI_AGENT_CORE,
    PI_AI,
    facts_for,
    manifest_bytes,
    root_manifest,
    synthetic_payload_files,
)

from pi_harness_cfg1 import pi_profile_policy_loader as loader
from pi_harness_cfg1.pi_payload import canonical_json_bytes
from pi_harness_cfg1.pi_profile_floor import compute_pmd_deltas, policy_file_bytes

SYNTHETIC_REF = {"repo_path": "docs/review/pe2b_synthetic_review.md", "sha256": "ab" * 32}
ACCEPTANCE = "AIDO-PE2B-SYNTHETIC-ACCEPTANCE-0001"
APS_LISTS = ("seam_evidence", "profiles", "approvals", "retirements")


def refs(count: int = 1) -> list[dict]:
    return [
        {"repo_path": f"docs/review/pe2b_ref_{index}.md", "sha256": f"{index:02x}" * 32}
        for index in range(count)
    ]


def with_id(record: dict, field: str) -> dict:
    """``record`` with ``field`` (re)computed as SHA-256 of the rest, appended last."""
    body = {name: value for name, value in record.items() if name != field}
    result = dict(body)
    result[field] = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    return result


# ---------------------------------------------------------------------------
# Synthetic payloads
# ---------------------------------------------------------------------------


class Payload:
    """One synthetic payload's PE-2a facts and its committed policy file bytes."""

    def __init__(self, files: dict[str, bytes], empty_dirs=()) -> None:
        self.files = dict(files)
        self.facts = facts_for(self.files, empty_dirs)
        assert self.facts.c5_reason is None, self.facts.c5_reason
        self.fingerprint = self.facts.payload_fingerprint
        self.profile_id = self.facts.profile_id
        self.inventory_bytes = policy_file_bytes(self.facts.inventory.to_record())
        self.bundle_bytes = policy_file_bytes(self.facts.bundle.to_record())

    def profile(self, **overrides) -> dict:
        record = profile_record(self.facts)
        record.update(overrides)
        return record


def files_with(**changes: bytes) -> tuple[dict[str, bytes], tuple[str, ...]]:
    files, empty_dirs = synthetic_payload_files()
    for key, data in changes.items():
        files[key.replace("__", "/")] = data
    return files, empty_dirs


def base_payload() -> Payload:
    return Payload(*synthetic_payload_files())


def payload_with(path: str, data: bytes) -> Payload:
    files, empty_dirs = synthetic_payload_files()
    files[path] = data
    return Payload(files, empty_dirs)


def root_manifest_payload(*, indent: int | None = 2, **overrides) -> Payload:
    return payload_with("package.json", manifest_bytes(root_manifest(**overrides), indent=indent))


def version_bump_payload(version: str = "1.0.1") -> Payload:
    return root_manifest_payload(version=version)


def internal_range_payload() -> Payload:
    return root_manifest_payload(
        dependencies={PI_AI: "^1.0.1", PI_AGENT_CORE: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    )


def presence_change_payload() -> Payload:
    return root_manifest_payload(dependencies={PI_AI: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"})


def key_reorder_payload() -> Payload:
    return root_manifest_payload(
        dependencies={PI_AGENT_CORE: "^1.0.0", PI_AI: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    )


def whitespace_payload() -> Payload:
    return root_manifest_payload(indent=4)


def non_seam_payload() -> Payload:
    """Counterexample 1: the 20 seams unchanged, ``dist/cli/setup.js`` changed."""
    return payload_with("dist/cli/setup.js", b"export const setup = 99;\n")


def seam_change_payload(path: str = "dist/main.js") -> Payload:
    return payload_with(path, b"synthetic pe2b changed seam: " + path.encode("ascii") + b"\n")


def exposed_payload() -> Payload:
    return root_manifest_payload(
        dependencies={
            PI_AI: "^1.0.0",
            PI_AGENT_CORE: "^1.0.0",
            "left-pad": "1.3.0",
            "@scope/util": "2.0.0",
            "missing-dep": "1.0.0",
            "@ghost/pkg": "2.0.0",
        }
    )


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def seam_evidence(digests: dict[str, str], evidence: list | None = None) -> dict:
    from pi_harness_cfg1.pi_payload import compute_seam_fingerprint

    record = {
        "record_kind": loader.SEAM_EVIDENCE_RECORD_KIND,
        "seam_contract": "PI-SC1",
        "seam_digests": dict(digests),
        "seam_fingerprint": compute_seam_fingerprint(dict(digests)),
        "evidence": [dict(SYNTHETIC_REF)] if evidence is None else evidence,
    }
    return with_id(record, "evidence_id")


def profile_record(facts) -> dict:
    return {
        "record_kind": loader.PROFILE_RECORD_KIND,
        "payload_contract": "PI-PC1",
        "payload_fingerprint": facts.payload_fingerprint,
        "resolution_exposures": list(facts.resolution_exposures),
        "profile_id": facts.profile_id,
        "seam_contract": "PI-SC1",
        "seam_digests": facts.seam_digests_dict(),
        "seam_fingerprint": facts.seam_fingerprint,
        "declared": facts.declared_dict(),
        "discovery": {"aido_commit": "0" * 40, "discovery_tool_revision": "PE-2a"},
    }


def seam_files_scope(paths) -> dict:
    return {"kind": "SEAM_FILES", "paths": sorted(paths)}


def payload_scope() -> dict:
    return {"kind": "PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS"}


def reuse(kind: str, source_id: str, scope: dict, ref_list: list | None = None) -> dict:
    return {
        "evidence_kind": kind,
        "source_id": source_id,
        "premise_scope": scope,
        "refs": [dict(SYNTHETIC_REF)] if ref_list is None else ref_list,
    }


def _finding(finding: str, count: int) -> dict:
    return {"finding": finding, "refs": refs(count)}


def pmd_for(candidate: Payload, reference: Payload, *, reuse_count: int = 0, cfg1: str = "NOT_AFFECTED") -> dict:
    """A structurally complete PMD over the RECOMPUTED delta list.

    Every category ``NOT_REACHED`` unless ``cfg1 == "AFFECTED"``, in which case
    ``REQUEST_SHAPE`` is ``AFFECTS`` (rule 6 consistency).
    """
    deltas = []
    for item in compute_pmd_deltas(candidate.facts, reference.facts):
        raw = item["delta"] == "RAW_BYTES"
        categories = {name: _finding("NOT_REACHED", 0) for name in sorted(loader.PMD_CATEGORIES)}
        if cfg1 == "AFFECTED":
            categories["REQUEST_SHAPE"] = _finding("AFFECTS", 1)
        deltas.append(
            {
                "delta": item["delta"],
                "manifest_path": item["manifest_path"],
                "old": item["old"],
                "new": item["new"],
                "read_as_parsed_field": _finding("NOT_APPLICABLE", 0) if raw else _finding("NOT_READ", 1),
                "read_as_raw_manifest": _finding("NOT_READ", 1),
                "categories": categories,
                "cfg1_cc1_effect": cfg1,
                "evidence_effect": {str(index): "NOT_AFFECTED" for index in range(reuse_count)},
            }
        )
    return {
        "reference_profile_id": reference.profile_id,
        "deltas": deltas,
        "conclusion_refs": [dict(SYNTHETIC_REF)],
    }


def approval(
    profile_id: str,
    qualification_class: str,
    *,
    reused: list | None = None,
    pmd: dict | None = None,
    evidence: list | None = None,
    acceptance: str = ACCEPTANCE,
) -> dict:
    record = {
        "record_kind": loader.APPROVAL_RECORD_KIND,
        "profile_id": profile_id,
        "consumer_contract": "CFG1-CC1",
        "policy_revision": "HPP-1",
        "qualification_class": qualification_class,
        "reused_evidence": [] if reused is None else reused,
        "pmd": pmd,
        "evidence": [dict(SYNTHETIC_REF)] if evidence is None else evidence,
        "acceptance_reference": acceptance,
    }
    return with_id(record, "approval_id")


def retirement(profile_id: str, reason: str = "OPERATOR_WITHDRAWN") -> dict:
    record = {
        "record_kind": loader.RETIREMENT_RECORD_KIND,
        "profile_id": profile_id,
        "consumer_contract": "CFG1-CC1",
        "reason_code": reason,
        "evidence": [dict(SYNTHETIC_REF)],
    }
    return with_id(record, "retirement_id")


# ---------------------------------------------------------------------------
# Chains and on-disk policy trees
# ---------------------------------------------------------------------------


class Chain:
    """An append-only APS chain built revision by revision (cumulative lists)."""

    def __init__(self) -> None:
        self.lists: dict[str, list] = {name: [] for name in APS_LISTS}
        self.records: list[dict] = []
        self.payloads: dict[str, Payload] = {}

    def revision(self, *, seam_evidence=(), profiles=(), approvals=(), retirements=(), payloads=()) -> dict:
        for payload in payloads:
            self.payloads[payload.fingerprint] = payload
        self.lists["seam_evidence"].extend(seam_evidence)
        self.lists["profiles"].extend(profiles)
        self.lists["approvals"].extend(approvals)
        self.lists["retirements"].extend(retirements)
        previous = None
        if self.records:
            previous = hashlib.sha256(policy_file_bytes(self.records[-1])).hexdigest()
        record = {
            "record_kind": loader.APS_RECORD_KIND,
            "consumer_contract": "CFG1-CC1",
            "policy_revision": "HPP-1",
            "payload_contract": "PI-PC1",
            "seam_contract": "PI-SC1",
            "revision": len(self.records) + 1,
            "previous_revision_sha256": previous,
            "seam_evidence": list(self.lists["seam_evidence"]),
            "profiles": list(self.lists["profiles"]),
            "approvals": list(self.lists["approvals"]),
            "retirements": list(self.lists["retirements"]),
        }
        self.records.append(record)
        return record

    def file_bytes(self) -> list[bytes]:
        return [policy_file_bytes(record) for record in self.records]


def rechain(records: list[dict]) -> list[bytes]:
    """Re-derive every ``previous_revision_sha256`` after an edit; return bytes."""
    out: list[bytes] = []
    for index, record in enumerate(records):
        record = dict(record)
        record["previous_revision_sha256"] = None if index == 0 else hashlib.sha256(out[-1]).hexdigest()
        out.append(policy_file_bytes(record))
    return out


class PolicyWorld:
    """A synthetic ``pi_profile_policy`` directory under ``tmp_path``."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.dir = base / "pi_profile_policy"

    @property
    def aps(self) -> Path:
        return self.dir / "aps"

    @property
    def inventories(self) -> Path:
        return self.dir / "inventories"

    @property
    def bundles(self) -> Path:
        return self.dir / "manifest_bundles"

    def write_revisions(self, revision_bytes: list[bytes]) -> None:
        self.aps.mkdir(parents=True, exist_ok=True)
        for index, data in enumerate(revision_bytes, start=1):
            (self.aps / f"aps.r{index:04d}.json").write_bytes(data)

    def write_payload(self, payload: Payload) -> None:
        self.inventories.mkdir(parents=True, exist_ok=True)
        self.bundles.mkdir(parents=True, exist_ok=True)
        (self.inventories / (payload.fingerprint + ".json")).write_bytes(payload.inventory_bytes)
        (self.bundles / (payload.fingerprint + ".json")).write_bytes(payload.bundle_bytes)

    def write_chain(self, chain: Chain, revision_bytes: list[bytes] | None = None) -> None:
        self.write_revisions(chain.file_bytes() if revision_bytes is None else revision_bytes)
        for payload in chain.payloads.values():
            self.write_payload(payload)

    def load(self, **leaves):
        return loader._load_policy_directory(str(self.dir), **leaves)


def genesis_like_chain() -> Chain:
    """One synthetic seam evidence record, zero profiles (the r0001 shape)."""
    chain = Chain()
    chain.revision(seam_evidence=[seam_evidence(base_payload().facts.seam_digests_dict())])
    return chain


def two_profile_chain() -> tuple[Chain, Payload, Payload]:
    """r1: seam evidence + A (C3_SEAM_EQUAL, E1 reuse); r2: A' version bump (C2)."""
    a = base_payload()
    b = version_bump_payload()
    chain = Chain()
    evidence = seam_evidence(a.facts.seam_digests_dict())
    chain.revision(
        seam_evidence=[evidence],
        profiles=[a.profile()],
        approvals=[
            approval(
                a.profile_id,
                "C3_SEAM_EQUAL",
                reused=[reuse("E1", evidence["evidence_id"], seam_files_scope(["dist/cli.js", "dist/main.js"]))],
            )
        ],
        payloads=[a],
    )
    chain.revision(
        profiles=[b.profile()],
        approvals=[approval(b.profile_id, "C2_MANIFEST_ONLY", pmd=pmd_for(b, a))],
        payloads=[b],
    )
    return chain, a, b
