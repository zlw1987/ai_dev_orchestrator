"""Shared scaffolding for the PE-2c (CFG1 profile-aware integration) suite.

Every policy here is SYNTHETIC: a canonical committed chain written under a
fresh temporary directory, loaded by the GENUINE PE-2b strict loader
(``_load_policy_directory``), and installed by rebinding the loader module's
``_GENUINE_POLICY_LOAD`` / ``SEALED_POLICY_SNAPSHOT`` globals -- test-harness
memory manipulation, the same accepted seam the PE-2b suite uses. Nothing
here touches the genuine policy directory, an installed Pi, Node, npm, a
socket, a credential or an endpoint.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from pe2b_support import Chain, Payload, PolicyWorld, approval, retirement, seam_evidence

from pi_harness_cfg1 import pi_profile_policy_loader as loader

#: The approval class every synthetic profile here is approved under. It is
#: admissible above every C3 floor, needs no PMD and no reuse entry.
SYNTHETIC_APPROVAL_CLASS = "C3_SEAM_CHANGED"

_LOAD_CACHE: dict[tuple, object] = {}


def payload_for(files: dict[str, bytes], empty_dirs=()) -> Payload:
    """The PE-2b synthetic payload (facts + committed file bytes) for a file map."""
    return Payload(dict(files), tuple(empty_dirs))


def build_chain(revisions: list[dict]) -> Chain:
    """A synthetic append-only chain.

    Each item of ``revisions`` is ``{"approve": [Payload, ...], "retire":
    [profile_id, ...], "seam_evidence": [digests, ...]}`` (all optional).
    Every approved profile enters with exactly one ``C3_SEAM_CHANGED``
    approval in the revision that introduces it.
    """
    chain = Chain()
    for item in revisions:
        approve = list(item.get("approve", ()))
        chain.revision(
            seam_evidence=[seam_evidence(digests) for digests in item.get("seam_evidence", ())],
            profiles=[payload.profile() for payload in approve],
            approvals=[approval(payload.profile_id, SYNTHETIC_APPROVAL_CLASS) for payload in approve],
            retirements=[retirement(profile_id) for profile_id in item.get("retire", ())],
            payloads=approve,
        )
    return chain


def load_chain(chain: Chain):
    """Load a chain through the GENUINE strict loader, from a temporary tree."""
    base = Path(tempfile.mkdtemp(prefix="cfg1_pe2c_policy_"))
    try:
        world = PolicyWorld(base)
        world.write_chain(chain)
        return world.load()
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _cache_key(revisions: list[dict]) -> tuple:
    return tuple(
        (
            tuple(payload.fingerprint for payload in item.get("approve", ())),
            tuple(item.get("retire", ())),
            tuple(tuple(sorted(digests.items())) for digests in item.get("seam_evidence", ())),
        )
        for item in revisions
    )


def synthetic_policy_load(revisions: list[dict]):
    """A cached genuine ``_PolicyLoad`` of a synthetic chain (immutable)."""
    key = _cache_key(revisions)
    load = _LOAD_CACHE.get(key)
    if load is None:
        load = load_chain(build_chain(revisions))
        _LOAD_CACHE[key] = load
    return load


def install_policy_load(monkeypatch, load) -> object:
    """Install one genuine load as THE module-level sealed policy."""
    monkeypatch.setattr(loader, "_GENUINE_POLICY_LOAD", load)
    monkeypatch.setattr(loader, "SEALED_POLICY_SNAPSHOT", load.snapshot)
    return load


def install_synthetic_policy(monkeypatch, *approved: Payload, retire=()) -> object:
    """Approve ``approved`` in revision 1 (and retire ``retire`` in revision 2)."""
    revisions: list[dict] = [{"approve": list(approved)}]
    if retire:
        revisions.append({"retire": list(retire)})
    return install_policy_load(monkeypatch, synthetic_policy_load(revisions))


def install_empty_policy(monkeypatch) -> object:
    """A synthetic genesis-shaped chain: one seam evidence, ZERO profiles."""
    from pi_harness_cfg1.preflight import PINNED_PI_SEAM_DIGESTS

    load = synthetic_policy_load([{"seam_evidence": [dict(PINNED_PI_SEAM_DIGESTS)]}])
    return install_policy_load(monkeypatch, load)
