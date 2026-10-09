"""F5A -- regression tests for the U126 approved-byte verifier and its report.

Offline. No socket (the suite conftest's ``_offline_only`` refuses every socket), no registry
contact, no Node/Pi/npm. Tarballs are SYNTHETIC and built in memory; the only
real inputs are the committed amendment/inventory/APS text and the committed
report, which are read, never written.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import io
import json
import shutil
import tarfile
import urllib.error
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _REPO_ROOT / "experiments" / "pi_harness_cfg1" / "evidence"
_VERIFIER_PATH = _EVIDENCE / "verify_f5a_u126_approved_bytes.py"
_REPORT_PATH = _EVIDENCE / "f5a_u126_verification_report.json"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_f5a_u126_approved_bytes", _VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v = _load_verifier()


# ---------------------------------------------------------------------------
# synthetic tarballs / registry
# ---------------------------------------------------------------------------


def make_tgz(members) -> bytes:
    """``members``: list of ``(name, data_or_None, kind)``; kind in file|dir|sym|hard|fifo."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            elif kind == "dir":
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            elif kind == "sym":
                info.type = tarfile.SYMTYPE
                info.linkname = "elsewhere"
                archive.addfile(info)
            elif kind == "hard":
                info.type = tarfile.LNKTYPE
                info.linkname = "package/other"
                archive.addfile(info)
            elif kind == "fifo":
                info.type = tarfile.FIFOTYPE
                archive.addfile(info)
            else:  # pragma: no cover
                raise AssertionError(kind)
    return buffer.getvalue()


def _inv(files: dict[str, bytes]) -> dict:
    return {path: (len(data), hashlib.sha256(data).hexdigest()) for path, data in files.items()}


def test_read_tarball_accepts_a_clean_archive_and_prefixes_the_payload_path():
    data = b"hello"
    inventory = _inv({"node_modules/@earendil-works/pi-ai/dist/a.js": data})
    records = v.read_tarball(
        "@earendil-works/pi-ai", "node_modules/@earendil-works/pi-ai",
        make_tgz([("package/dist/a.js", data, "file")]), inventory,
    )
    assert [(r["path"], r["equals_inventory"]) for r in records] == [
        ("node_modules/@earendil-works/pi-ai/dist/a.js", True)
    ]


_UNSAFE = [
    ("traversal", [("package/../escape.js", b"x", "file")], "PATH_MALFORMED"),
    ("traversal_inner", [("package/dist/../../escape.js", b"x", "file")], "PATH_MALFORMED"),
    ("absolute", [("/abs.js", b"x", "file")], "ARCHIVE_UNSAFE_MEMBER"),
    ("absolute_under_prefix", [("package//abs.js", b"x", "file")], "PATH_MALFORMED"),
    ("backslash", [("package/dist\\a.js", b"x", "file")], "PATH_MALFORMED"),
    ("drive_or_stream_colon", [("package/a.js:stream", b"x", "file")], "PATH_MALFORMED"),
    ("trailing_dot", [("package/a.js.", b"x", "file")], "PATH_MALFORMED"),
    ("control_char", [("package/a\x01.js", b"x", "file")], "PATH_MALFORMED"),
    ("symlink", [("package/a.js", None, "sym")], "ARCHIVE_UNSAFE_MEMBER"),
    ("hardlink", [("package/a.js", None, "hard")], "ARCHIVE_UNSAFE_MEMBER"),
    ("directory_member", [("package/dist", None, "dir")], "ARCHIVE_UNSAFE_MEMBER"),
    ("fifo", [("package/a.js", None, "fifo")], "ARCHIVE_UNSAFE_MEMBER"),
    ("outside_package_prefix", [("other/a.js", b"x", "file")], "ARCHIVE_UNSAFE_MEMBER"),
    ("duplicate", [("package/a.js", b"x", "file"), ("package/a.js", b"x", "file")], "ARCHIVE_DUPLICATE_PATH"),
    ("case_collision", [("package/a.js", b"x", "file"), ("package/A.js", b"x", "file")], "ARCHIVE_CASE_COLLISION"),
    ("not_in_inventory", [("package/unlisted.js", b"x", "file")], "ARCHIVE_MEMBER_NOT_IN_INVENTORY"),
]


@pytest.mark.parametrize("label,members,code", _UNSAFE, ids=[u[0] for u in _UNSAFE])
def test_read_tarball_refuses_every_unsafe_member_kind(label, members, code):
    inventory = _inv({"a.js": b"x", "A.js": b"x", "dist/a.js": b"x"})
    with pytest.raises(v.VerificationFailure) as excinfo:
        v.read_tarball("pkg", "", make_tgz(members), inventory)
    assert excinfo.value.code == code, excinfo.value


def test_read_tarball_reports_digest_mismatches_without_raising():
    inventory = _inv({"a.js": b"approved", "b.js": b"approved"})
    records = v.read_tarball(
        "pkg", "",
        make_tgz([("package/a.js", b"approveX", "file"), ("package/b.js", b"approved", "file")]),
        inventory,
    )
    assert {r["path"]: (r["equals_inventory"], r["problem"]) for r in records} == {
        "a.js": (False, "MEMBER_DIGEST_MISMATCH"), "b.js": (True, None)
    }


def test_read_tarball_refuses_a_wrong_size_member_at_once_and_does_not_skip_its_body():
    inventory = _inv({"a.js": b"approved", "b.js": b"approved"})
    declared_huge = io.BytesIO()
    with tarfile.open(fileobj=declared_huge, mode="w:gz") as archive:
        info = tarfile.TarInfo("package/a.js")
        info.size = 1_000_000
        archive.addfile(info, io.BytesIO(bytes(1_000_000)))
    with pytest.raises(v.VerificationFailure) as excinfo:
        v.read_tarball("pkg", "", declared_huge.getvalue(), inventory)
    assert excinfo.value.code == "MEMBER_SIZE_MISMATCH"
    shorter = make_tgz([("package/a.js", b"short", "file")])
    with pytest.raises(v.VerificationFailure) as excinfo:
        v.read_tarball("pkg", "", shorter, inventory)
    assert excinfo.value.code == "MEMBER_SIZE_MISMATCH"


@pytest.mark.parametrize(
    "tarball",
    [b"", b"not a gzip stream", gzip.compress(b"not a tar archive" * 50), gzip.compress(b"")],
    ids=["empty", "not_gzip", "gzip_not_tar", "empty_tar"],
)
def test_read_tarball_refuses_unreadable_or_empty_archives(tarball):
    with pytest.raises(v.VerificationFailure) as excinfo:
        v.read_tarball("pkg", "", tarball, _inv({"a.js": b"x"}))
    assert excinfo.value.code == "ARCHIVE_UNREADABLE"


def test_read_tarball_refuses_a_truncated_archive():
    full = make_tgz([("package/a.js", b"x" * 100_000, "file")])
    with pytest.raises(v.VerificationFailure) as excinfo:
        v.read_tarball("pkg", "", full[: len(full) // 2], _inv({"a.js": b"x" * 100_000}))
    assert excinfo.value.code == "ARCHIVE_UNREADABLE"


# ---------------------------------------------------------------------------
# registry metadata and integrity
# ---------------------------------------------------------------------------


def _dist(body: bytes, **overrides) -> dict:
    dist = {
        "tarball": "https://registry.npmjs.org/p/-/p-1.0.3.tgz",
        "integrity": "sha512-" + base64.b64encode(hashlib.sha512(body).digest()).decode(),
        "shasum": hashlib.sha1(body).hexdigest(),
    }
    dist.update(overrides)
    return dist


def test_integrity_verified_when_supplied_and_recorded_as_such():
    body = b"tarball bytes"
    assert v.verify_integrity("p", _dist(body), body) == {"integrity": "verified:sha512", "shasum": "verified:sha1"}


def test_integrity_not_supplied_is_recorded_not_passed():
    body = b"tarball bytes"
    dist = {"tarball": "https://registry.npmjs.org/p/-/p-1.0.3.tgz"}
    assert v.verify_integrity("p", dist, body) == {"integrity": "not_supplied", "shasum": "not_supplied"}


@pytest.mark.parametrize(
    "override,code",
    [
        ({"integrity": "sha512-" + base64.b64encode(b"\0" * 64).decode()}, "INTEGRITY_MISMATCH"),
        ({"integrity": "sha512-%%%not base64%%%"}, "INTEGRITY_UNUSABLE"),
        ({"integrity": "md5-AAAA"}, "INTEGRITY_UNUSABLE"),
        ({"integrity": ""}, "INTEGRITY_UNUSABLE"),
        ({"integrity": 5}, "INTEGRITY_UNUSABLE"),
        ({"shasum": "0" * 40}, "INTEGRITY_MISMATCH"),
        ({"shasum": "xyz"}, "INTEGRITY_UNUSABLE"),
    ],
)
def test_integrity_supplied_but_wrong_or_unusable_is_refused(override, code):
    body = b"tarball bytes"
    with pytest.raises(v.VerificationFailure) as excinfo:
        v.verify_integrity("p", _dist(body, **override), body)
    assert excinfo.value.code == code


@pytest.mark.parametrize(
    "mutation",
    [
        {"name": "@earendil-works/other"},
        {"version": "1.0.4"},
        {"dist": None},
        {"dist": {"tarball": "http://registry.npmjs.org/p.tgz"}},
        {"dist": {"tarball": "https://evil.example/p.tgz"}},
        {"dist": {"tarball": "https://registry.npmjs.org/p.tgz?token=1"}},
        {"dist": {"tarball": "https://user:pw@registry.npmjs.org/p.tgz"}},
        {"dist": {"tarball": "https://registry.npmjs.org/p.zip"}},
        {"dist": {}},
    ],
)
def test_registry_metadata_that_disagrees_or_points_elsewhere_is_refused(mutation):
    metadata = {"name": "p", "version": v.PACKAGE_VERSION,
                "dist": {"tarball": "https://registry.npmjs.org/p/-/p-1.0.3.tgz"}}
    metadata.update(mutation)
    with pytest.raises(v.VerificationFailure) as excinfo:
        v._check_registry_metadata("p", json.dumps(metadata).encode())
    assert excinfo.value.code == "REGISTRY_METADATA_INVALID"


def test_registry_metadata_that_is_not_json_is_refused():
    for raw in (b"\xff\xfe", b"[]", b"{not json"):
        with pytest.raises(v.VerificationFailure):
            v._check_registry_metadata("p", raw)


def test_registry_client_refuses_non_registry_urls_before_any_socket():
    client = v.RegistryClient()
    for url in (
        "http://registry.npmjs.org/x.tgz",
        "https://example.com/x.tgz",
        "https://user:pw@registry.npmjs.org/x.tgz",
        "file:///etc/passwd",
    ):
        with pytest.raises(v.VerificationFailure) as excinfo:
            client._get(url, 10, "application/json")
        assert excinfo.value.code == "DOWNLOAD_REFUSED"


def test_registry_client_refuses_redirects_off_the_registry():
    handler = v._RestrictedRedirects()
    request = v.urllib.request.Request("https://registry.npmjs.org/a")
    for target in ("http://registry.npmjs.org/b", "https://elsewhere.example/b"):
        with pytest.raises(urllib.error.URLError):
            handler.redirect_request(request, None, 302, "Found", {}, target)


def test_registry_client_ignores_environment_proxies_and_carries_no_auth_machinery(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://user:pw@proxy.invalid:3128")
    monkeypatch.setenv("HTTP_PROXY", "http://user:pw@proxy.invalid:3128")
    # POSITIVE CONTROL: a default urllib opener WOULD pick that proxy up.
    default_names = {type(h).__name__ for h in v.urllib.request.build_opener().handlers}
    assert "ProxyHandler" in default_names
    client = v.RegistryClient()
    names = {type(h).__name__ for h in client._opener.handlers}
    assert "ProxyHandler" not in names
    for auth in ("HTTPCookieProcessor", "HTTPBasicAuthHandler", "HTTPDigestAuthHandler", "ProxyBasicAuthHandler"):
        assert auth not in names, auth


# ---------------------------------------------------------------------------
# committed inputs (read-only) and the path-set digest convention
# ---------------------------------------------------------------------------


def test_path_set_digest_convention_is_lf_joined_sorted_utf8_without_trailing_newline():
    assert v.path_set_digest(["b", "a"]) == hashlib.sha256(b"a\nb").hexdigest()
    assert v.path_set_digest(["a", "b"]) == v.path_set_digest(["b", "a"])


def test_committed_amendment_parses_to_the_frozen_sets():
    text = (_REPO_ROOT / v.AMENDMENT_RELATIVE).read_bytes().decode("utf-8")
    parsed = v.parse_amendment(text)
    counts = {basis: len(paths) for basis, paths in parsed["by_basis"].items()}
    assert counts == {"A": 54, "B": 15, "B/R": 5, "C/R": 42, "D/R": 10, "UNPROVEN": 0}
    review = sorted(p for b in v.REVIEW_BASES for p in parsed["by_basis"][b])
    assert len(review) == 57
    assert v.path_set_digest(review) == parsed["historic_57_digest"]
    assert sorted(parsed["table_105_paths"]) == review
    assert v.path_set_digest(parsed["by_basis"]["B/R"]) == parsed["stated"]["B/R"][1]
    assert v.path_set_digest(parsed["by_basis"]["C/R"]) == parsed["stated"]["C/R"][1]
    assert v.path_set_digest(parsed["by_basis"]["D/R"]) == parsed["stated"]["D/R"][1]


def test_committed_inventory_is_bound_by_aps_and_well_formed():
    inventory = v.load_inventory(_REPO_ROOT)
    assert inventory["file_count"] == 15046
    assert inventory["directory_count"] == 1436
    assert inventory["file_count"] + inventory["directory_count"] == inventory["entry_count"]


def test_amendment_stated_numbers_are_present_in_the_amendment_text():
    text = (_REPO_ROOT / v.AMENDMENT_RELATIVE).read_bytes().decode("utf-8")
    spaced = lambda n: f"{n:,}".replace(",", " ")  # noqa: E731 - the amendment writes 2 367
    assert spaced(v.AMENDMENT_STATED["tarball_member_count"]) in text
    assert spaced(v.AMENDMENT_STATED["approved_file_count"]) in text
    assert spaced(v.AMENDMENT_STATED["approved_files_not_in_tarballs"]) in text
    assert f"{v.AMENDMENT_STATED['review_files_recovered']} / {v.AMENDMENT_STATED['review_files_recovered']}" in text
    assert f"Of the other 69 files of `U126`, {v.AMENDMENT_STATED['other_u126_recovered']} were incidentally recovered" in text
    assert f"{v.AMENDMENT_STATED['other_u126_not_in_packages']} are not in the five packages fetched" in text


# ---------------------------------------------------------------------------
# end to end over a SYNTHETIC repo and a fake registry
# ---------------------------------------------------------------------------

_SCOPED = (
    ("@earendil-works/pi-agent-core", "node_modules/@earendil-works/pi-agent-core"),
    ("@earendil-works/pi-ai", "node_modules/@earendil-works/pi-ai"),
    ("@earendil-works/pi-mcp", "node_modules/@earendil-works/pi-mcp"),
    ("@earendil-works/pi-tui", "node_modules/@earendil-works/pi-tui"),
)
#: the seven U126 files the real five packages do not contain
_NOT_IN_PACKAGES = (
    "node_modules/@babel/runtime/",
    "node_modules/@earendil-works/pi-codemode/",
)


def _synthetic_bytes(path: str) -> bytes:
    return f"// synthetic bytes for {path}\n".encode()


def _package_of(path: str) -> tuple[str, str]:
    for package, prefix in _SCOPED:
        if path.startswith(prefix + "/"):
            return package, path[len(prefix) + 1:]
    return "@earendil-works/pi-coding-agent", path


class FakeRegistry:
    def __init__(self, tarballs: dict[str, bytes], dist_overrides: dict[str, dict] | None = None):
        self.tarballs = tarballs
        self.dist_overrides = dist_overrides or {}
        self.requests: list[str] = []

    def _url(self, package: str) -> str:
        return f"https://registry.npmjs.org/{package}/-/{package.split('/')[1]}-1.0.3.tgz"

    def get_version_metadata(self, package, version):
        self.requests.append(package)
        body = self.tarballs[package]
        dist = _dist(body, tarball=self._url(package))
        dist.update(self.dist_overrides.get(package, {}))
        return json.dumps({"name": package, "version": version, "dist": dist}).encode()

    def get_tarball(self, url):
        for package, body in self.tarballs.items():
            if url == self._url(package):
                return body
        raise AssertionError(f"HARNESS: unknown url {url}")


@pytest.fixture()
def synthetic(tmp_path):
    """A synthetic repo root: the REAL amendment text, a synthetic inventory that
    lists the 126 U126 paths with synthetic bytes, and an APS stub binding it."""
    real = v.parse_amendment((_REPO_ROOT / v.AMENDMENT_RELATIVE).read_bytes().decode("utf-8"))
    paths = sorted(p for plist in real["by_basis"].values() for p in plist)
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    shutil.copyfile(_REPO_ROOT / v.AMENDMENT_RELATIVE, root / v.AMENDMENT_RELATIVE)
    entries = [
        {"kind": "file", "path": p, "size": len(_synthetic_bytes(p)), "sha256": hashlib.sha256(_synthetic_bytes(p)).hexdigest()}
        for p in paths
    ]
    entries.append({"kind": "dir", "path": "dist"})
    inventory = {"record_kind": "aido-pi-payload-inventory.v1", "payload_contract": "PI-PC1", "entries": entries}
    inventory_dir = root / v.INVENTORY_DIR_RELATIVE
    inventory_dir.mkdir(parents=True)
    (inventory_dir / f"{v.PAYLOAD_FINGERPRINT}.json").write_text(json.dumps(inventory), encoding="utf-8")
    aps = {"profiles": [{"profile_id": v.PROFILE_ID, "payload_fingerprint": v.PAYLOAD_FINGERPRINT,
                         "declared": {"package_version": v.PACKAGE_VERSION}}]}
    (root / v.APS_RELATIVE).parent.mkdir(parents=True)
    (root / v.APS_RELATIVE).write_text(json.dumps(aps), encoding="utf-8")

    per_package: dict[str, list] = {p: [] for p, _ in v.PACKAGES}
    for path in paths:
        if path.startswith(_NOT_IN_PACKAGES):
            continue
        package, member = _package_of(path)
        per_package[package].append((f"package/{member}", _synthetic_bytes(path), "file"))
    return root, paths, per_package


def _registry(per_package, **kwargs):
    return FakeRegistry({p: make_tgz(m) for p, m in per_package.items()}, **kwargs)


def test_end_to_end_pass_over_synthetic_bytes(synthetic):
    root, paths, per_package = synthetic
    report, status = v.run(root, _registry(per_package))
    assert status == 0 and report["verdict"] == "PASS", report
    measured = report["measured_facts"]
    assert measured["review_set"]["count"] == 57
    assert measured["review_set"]["recovered_and_exactly_equal"] == 57
    assert measured["members_vs_inventory"]["members"] == 119
    assert measured["other_u126_files_not_re_reviewed"]["not_in_the_five_packages"] == 7
    assert all(item["equal"] for item in measured["path_set_digests_recomputed_from_amendment_rows"]["sets"].values())
    # the synthetic world is NOT the real world: the measured totals must say so
    agreement = measured["agreement_with_amendment_stated_numbers"]
    assert agreement["tarball_member_count"]["agree"] is False
    assert agreement["review_files_recovered"]["agree"] is True
    assert report["author_semantic_analysis"]["status"] == "AUTHOR_CLAIM_NOT_VERIFIED_BY_THIS_PROGRAM"


def test_end_to_end_report_is_deterministic(synthetic):
    root, _paths, per_package = synthetic
    first = v.render(v.run(root, _registry(per_package))[0])
    second = v.render(v.run(root, _registry(per_package))[0])
    assert first == second and first.endswith(b"\n") and b"\r" not in first


def _review_member(per_package, path):
    package, member = _package_of(path)
    return package, f"package/{member}"


def _a_review_path(synthetic):
    root, _paths, _pp = synthetic
    real = v.parse_amendment((root / v.AMENDMENT_RELATIVE).read_bytes().decode("utf-8"))
    return sorted(real["by_basis"]["C/R"])[0]


def test_failure_missing_review_file(synthetic):
    root, _paths, per_package = synthetic
    package, name = _review_member(per_package, _a_review_path(synthetic))
    per_package[package] = [m for m in per_package[package] if m[0] != name]
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["verdict"] == "FAIL"
    assert report["failures"][0]["code"] == "REVIEW_FILE_MISSING"
    assert "measured_facts" not in report  # a failed run makes no measured claim


def test_failure_flipped_byte_in_a_review_file(synthetic):
    root, _paths, per_package = synthetic
    package, name = _review_member(per_package, _a_review_path(synthetic))
    per_package[package] = [
        (n, d[:-2] + b"X\n" if n == name else d, k) for n, d, k in per_package[package]
    ]
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] == "MEMBER_MISMATCH"


def test_failure_wrong_size_member(synthetic):
    root, _paths, per_package = synthetic
    package, name = _review_member(per_package, _a_review_path(synthetic))
    per_package[package] = [(n, d + b"extra" if n == name else d, k) for n, d, k in per_package[package]]
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] == "MEMBER_SIZE_MISMATCH"


def test_failure_unexpected_member(synthetic):
    root, _paths, per_package = synthetic
    per_package["@earendil-works/pi-tui"].append(("package/surprise.js", b"x", "file"))
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] == "ARCHIVE_MEMBER_NOT_IN_INVENTORY"


def test_failure_unsafe_member_in_any_tarball(synthetic):
    root, _paths, per_package = synthetic
    per_package["@earendil-works/pi-ai"].append(("package/link.js", None, "sym"))
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] == "ARCHIVE_UNSAFE_MEMBER"


def test_failure_same_payload_path_claimed_by_two_tarballs(synthetic):
    root, _paths, per_package = synthetic
    path = next(p for p in synthetic[1] if p.startswith("node_modules/@earendil-works/pi-ai/") and not p.startswith(_NOT_IN_PACKAGES))
    inner = path[len("node_modules/@earendil-works/pi-ai/"):]
    per_package["@earendil-works/pi-coding-agent"].append(
        (f"package/{path}", _synthetic_bytes(path), "file")
    )
    assert inner  # the same payload path now appears in two tarballs
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] == "ARCHIVE_DUPLICATE_PATH"


def test_failure_registry_integrity_mismatch(synthetic):
    root, _paths, per_package = synthetic
    registry = _registry(per_package, dist_overrides={
        "@earendil-works/pi-mcp": {"integrity": "sha512-" + base64.b64encode(b"\0" * 64).decode()}
    })
    report, status = v.run(root, registry)
    assert status == 1 and report["failures"][0]["code"] == "INTEGRITY_MISMATCH"


def test_failure_when_an_integrity_field_is_supplied_but_unusable(synthetic):
    root, _paths, per_package = synthetic
    report, status = v.run(root, _registry(per_package, dist_overrides={
        "@earendil-works/pi-mcp": {"integrity": "garbage"}}))
    assert status == 1 and report["failures"][0]["code"] == "INTEGRITY_UNUSABLE"


def test_pass_is_not_claimed_for_a_package_with_no_integrity_but_it_is_recorded(synthetic):
    root, _paths, per_package = synthetic
    registry = _registry(per_package, dist_overrides={"@earendil-works/pi-mcp": {"integrity": None, "shasum": None}})
    report, status = v.run(root, registry)
    assert status == 0
    pi_mcp = next(p for p in report["measured_facts"]["packages"] if p["package"].endswith("pi-mcp"))
    assert pi_mcp["registry_integrity_check"] == {"integrity": "not_supplied", "shasum": "not_supplied"}


def _tamper_amendment(root, old, new):
    path = root / v.AMENDMENT_RELATIVE
    text = path.read_bytes().decode("utf-8")
    assert text.count(old) == 1, old
    path.write_bytes(text.replace(old, new).encode("utf-8"))


def test_failure_amendment_row_basis_differs_from_the_per_path_table(synthetic):
    root, _paths, per_package = synthetic
    _tamper_amendment(root, "C/R       dist/cli/args.js", "D/R       dist/cli/args.js")
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] in {"AMENDMENT_INCONSISTENT", "SET_DIGEST_MISMATCH"}


def test_failure_amendment_path_set_digest_differs(synthetic):
    root, _paths, per_package = synthetic
    path = root / v.AMENDMENT_RELATIVE
    text = path.read_bytes().decode("utf-8")
    assert text.count(old) == 1, old
    path.write_bytes(text.replace(old, new).encode("utf-8"))


def test_failure_amendment_row_basis_differs_from_the_per_path_table(synthetic):
    root, _paths, per_package = synthetic
    _tamper_amendment(root, "C/R       dist/cli/args.js", "D/R       dist/cli/args.js")
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] in {"AMENDMENT_INCONSISTENT", "SET_DIGEST_MISMATCH"}


def test_failure_amendment_path_set_digest_differs(synthetic):
    root, _paths, per_package = synthetic
    _tamper_amendment(root, "7f47a89245f670553fe7bbaf4dd7338af46771b2af090415a32df007eaccd121   ".strip()[:0] + "C (R)", "C (R)")  # no-op guard
    path = root / v.AMENDMENT_RELATIVE
    text = path.read_bytes().decode("utf-8")
    path.write_bytes(text.replace("e55241b9a056a27d5ea4a10905edba4149c02bfc7d362b42bbef59e36369033a",
                                  "0" * 64).encode("utf-8"))
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] == "SET_DIGEST_MISMATCH"


def test_failure_amendment_with_an_unproven_row(synthetic):
    root, _paths, per_package = synthetic
    _tamper_amendment(root, "C/R       dist/cli/args.js", "UNPROVEN  dist/cli/args.js")
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] in {"AMENDMENT_INCONSISTENT", "SET_DIGEST_MISMATCH"}


def test_failure_review_path_missing_from_the_inventory(synthetic):
    root, _paths, per_package = synthetic
    inventory_path = root / v.INVENTORY_DIR_RELATIVE / f"{v.PAYLOAD_FINGERPRINT}.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    target = _a_review_path(synthetic)
    inventory["entries"] = [e for e in inventory["entries"] if e["path"] != target]
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] == "AMENDMENT_INCONSISTENT"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda inv: inv["entries"].append({"kind": "file", "path": "dist", "size": 0, "sha256": "0" * 64}),
        lambda inv: inv["entries"].append({"kind": "file", "path": "../x", "size": 0, "sha256": "0" * 64}),
        lambda inv: inv["entries"].append({"kind": "file", "path": "q.js", "size": -1, "sha256": "0" * 64}),
        lambda inv: inv["entries"].append({"kind": "file", "path": "q.js", "size": 1, "sha256": "ABC"}),
        lambda inv: inv["entries"].append({"kind": "link", "path": "q.js"}),
        lambda inv: inv["entries"].append({"kind": "file", "path": "q.js", "size": True, "sha256": "0" * 64}),
        lambda inv: inv["entries"].append({"kind": "dir", "path": "Dist"}),
        lambda inv: inv["entries"].append("not an object"),
        lambda inv: inv.update(entries=[]),
        lambda inv: inv.update(record_kind="other"),
    ],
)
def test_failure_malformed_inventory(synthetic, mutate):
    root, _paths, per_package = synthetic
    inventory_path = root / v.INVENTORY_DIR_RELATIVE / f"{v.PAYLOAD_FINGERPRINT}.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    mutate(inventory)
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] in {"INPUT_MALFORMED", "PATH_MALFORMED"}


def test_failure_aps_not_binding_the_inventory(synthetic):
    root, _paths, per_package = synthetic
    (root / v.APS_RELATIVE).write_text(json.dumps({"profiles": []}), encoding="utf-8")
    report, status = v.run(root, _registry(per_package))
    assert status == 1 and report["failures"][0]["code"] == "INPUT_MALFORMED"


def test_failure_missing_inputs(tmp_path):
    report, status = v.run(tmp_path, FakeRegistry({}))
    assert status == 1 and report["failures"][0]["code"] == "INPUT_UNREADABLE"


def test_failure_download_error_is_fail_closed(synthetic):
    root, _paths, per_package = synthetic

    class Broken(FakeRegistry):
        def get_tarball(self, url):
            raise v.VerificationFailure("DOWNLOAD_FAILED", "URLError")

    report, status = v.run(root, Broken({p: make_tgz(m) for p, m in per_package.items()}))
    assert status == 1 and report["failures"][0]["code"] == "DOWNLOAD_FAILED"


# ---------------------------------------------------------------------------
# the committed report
# ---------------------------------------------------------------------------


def _committed_report():
    return json.loads(_REPORT_PATH.read_bytes())


def test_committed_report_is_a_passing_deterministic_rendering():
    raw = _REPORT_PATH.read_bytes().replace(b"\r\n", b"\n")  # tolerate an autocrlf checkout
    report = json.loads(raw)
    assert report["record_kind"] == v.RECORD_KIND
    assert report["verdict"] == "PASS" and report["failures"] == []
    assert v.render(report) == raw  # exactly the serialization the program emits


def test_committed_report_is_bound_to_the_current_inputs():
    report = _committed_report()
    inputs = report["inputs"]
    amendment = (_REPO_ROOT / inputs["amendment"]["repo_path"]).read_bytes().replace(b"\r\n", b"\n")
    inventory = (_REPO_ROOT / inputs["approved_inventory"]["repo_path"]).read_bytes()
    aps = (_REPO_ROOT / inputs["approved_inventory"]["bound_by_aps"]["repo_path"]).read_bytes()
    assert hashlib.sha256(amendment).hexdigest() == inputs["amendment"]["sha256_after_crlf_to_lf"]
    assert hashlib.sha256(inventory).hexdigest() == inputs["approved_inventory"]["sha256"]
    assert hashlib.sha256(aps).hexdigest() == inputs["approved_inventory"]["bound_by_aps"]["sha256"]


def test_committed_report_review_files_equal_the_committed_inventory_entries():
    report = _committed_report()
    inventory = v.load_inventory(_REPO_ROOT)["files"]
    files = report["measured_facts"]["review_set"]["files"]
    assert len(files) == 57 and len({f["path"] for f in files}) == 57
    for item in files:
        assert inventory[item["path"]] == (item["size"], item["sha256"]), item["path"]
    assert v.path_set_digest([f["path"] for f in files]) == report["measured_facts"]["review_set"]["sorted_path_sha256"]
    assert report["measured_facts"]["review_set"]["sorted_path_sha256"] == (
        "e55241b9a056a27d5ea4a10905edba4149c02bfc7d362b42bbef59e36369033a"
    )


def test_committed_report_separates_measured_facts_from_the_authors_analysis():
    report = _committed_report()
    assert set(report) >= {"measured_facts", "author_semantic_analysis", "not_established", "scope_declaration"}
    analysis = report["author_semantic_analysis"]
    assert analysis["status"] == "AUTHOR_CLAIM_NOT_VERIFIED_BY_THIS_PROGRAM"
    flattened = json.dumps(report["measured_facts"])
    for forbidden in ("classification_correct", "read_relocation_proven", "harmless"):
        assert forbidden not in flattened
    assert any("classification" in item for item in report["not_established"])
    assert report["scope_declaration"]["downloaded_bytes_persisted"] is False
    for package in report["measured_facts"]["packages"]:
        assert package["registry_integrity_check"]["integrity"].startswith("verified:")
    for key, item in report["measured_facts"]["agreement_with_amendment_stated_numbers"].items():
        assert item["agree"] is True, key


def test_committed_report_is_credential_free_and_has_no_third_party_source():
    raw = _REPORT_PATH.read_text(encoding="ascii")
    lowered = raw.lower()
    for marker in ("bearer ", "api_key", "apikey", "password", "_authtoken", "secret"):
        assert marker not in lowered, marker
    import re

    assert not re.search(r"npm_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}", raw)
    assert "function " not in raw and "import " not in raw  # no JavaScript text
    assert len(raw) < 100_000


def test_verifier_module_imports_only_the_standard_library():
    import ast

    tree = ast.parse(_VERIFIER_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    import sys

    assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)
    source = _VERIFIER_PATH.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system", "importlib", "exec(", "eval(", "extractall", "extract("):
        assert forbidden not in source, forbidden
