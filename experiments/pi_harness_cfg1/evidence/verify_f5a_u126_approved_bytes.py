#!/usr/bin/env python3
"""F5-A R1-FU2 -- reproducible verification of the 57 recovered U126 review files.

Standard library only. This program is DATA-ONLY: it downloads five public npm
tarballs and hashes bytes. It never executes, imports, extracts to disk or
interprets any downloaded content, and it runs no Node, Pi, npm or lifecycle
script.

What it measures (directly, from bytes):

* the five ``@earendil-works/*@1.0.3`` tarballs downloaded intact (registry
  ``dist.integrity`` / ``dist.shasum`` when supplied);
* the archive is structurally safe (regular files only, no traversal, no links,
  no duplicate or case-colliding path, nothing outside the committed inventory);
* every tarball member equals its committed PE-5-approved inventory entry by
  exact payload-relative path, size and SHA-256;
* all 57 review files are present among those members and equal;
* the sorted-path SHA-256 of the original 57, and of the B/R, C/R, D/R sets
  (and the other Appendix sets), recomputed from the amendment's own rows equal
  the digests the amendment states.

What it does NOT establish: that any file was read, that any file is harmless,
or that the B / C / D read-relocation classification is correct. A matching
checksum proves the bytes are the approved bytes and nothing about what they do.
The classification is the author's static analysis (amendment 8.10.8) and is
recorded in the report as an unverified claim.

Nothing downloaded is written to disk: tarballs and members live only in
process memory. Only the JSON report is written, and only when asked.

Exit status: 0 verdict PASS, 1 verdict FAIL (a report is still produced).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RECORD_KIND = "aido-f5a-u126-approved-byte-verification.v1"

AMENDMENT_RELATIVE = "docs/PHASE_5F3B_CFG1_F5A_LIVE_LAUNCH_AUTHORITY_AMENDMENT.md"
APS_RELATIVE = "experiments/pi_harness_cfg1/pi_profile_policy/aps/aps.r0002.json"
INVENTORY_DIR_RELATIVE = "experiments/pi_harness_cfg1/pi_profile_policy/inventories"
DEFAULT_REPORT_RELATIVE = "experiments/pi_harness_cfg1/evidence/f5a_u126_verification_report.json"

PROFILE_ID = "56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67"
PAYLOAD_FINGERPRINT = "66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc"
PACKAGE_VERSION = "1.0.3"

#: (npm package name, payload-relative directory that package occupies).
PACKAGES = (
    ("@earendil-works/pi-coding-agent", ""),
    ("@earendil-works/pi-agent-core", "node_modules/@earendil-works/pi-agent-core"),
    ("@earendil-works/pi-ai", "node_modules/@earendil-works/pi-ai"),
    ("@earendil-works/pi-mcp", "node_modules/@earendil-works/pi-mcp"),
    ("@earendil-works/pi-tui", "node_modules/@earendil-works/pi-tui"),
)

REGISTRY_HOST = "registry.npmjs.org"
MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_TARBALL_BYTES = 128 * 1024 * 1024
MAX_MEMBER_COUNT = 20000
USER_AGENT = "aido-f5a-u126-verifier/1 (data-only)"

#: Values the amendment states in 8.10.8(3) and 8.10.8(11). They are
#: transcribed here ONLY so the report can say whether the measurement agrees;
#: the regression test asserts each string occurs in the amendment text.
AMENDMENT_STATED = {
    "tarball_member_count": 2367,
    "review_files_recovered": 57,
    "other_u126_recovered": 62,
    "other_u126_not_in_packages": 7,
    "approved_file_count": 15046,
    "approved_files_not_in_tarballs": 12679,
}

REVIEW_BASES = ("B/R", "C/R", "D/R")
ALL_BASES = ("A", "B", "B/R", "C/R", "D/R", "UNPROVEN")
#: label in the amendment's digest table -> basis key
DIGEST_TABLE_LABELS = {
    "A": "A",
    "B (F)": "B",
    "B (R)": "B/R",
    "C (R)": "C/R",
    "D (R)": "D/R",
    "UNPROVEN": "UNPROVEN",
    "U126": "U126",
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class VerificationFailure(Exception):
    """A closed-code, fail-closed refusal. ``detail`` never contains file bytes."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# small pure helpers
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def path_set_digest(paths) -> str:
    """The amendment's convention: SHA-256 of the sorted paths joined by LF, no
    trailing newline, UTF-8. (Measured: this reproduces every stated digest.)"""
    return sha256_hex("\n".join(sorted(paths)).encode("utf-8"))


def validate_relative_path(path: object, what: str) -> str:
    """Strict relative payload path grammar; anything else is refused."""
    if not isinstance(path, str) or not path:
        raise VerificationFailure("PATH_MALFORMED", f"{what}: not a non-empty string")
    if len(path) > 1024:
        raise VerificationFailure("PATH_MALFORMED", f"{what}: over-long path")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in path):
        raise VerificationFailure("PATH_MALFORMED", f"{what}: control character")
    if "\\" in path or ":" in path:
        raise VerificationFailure("PATH_MALFORMED", f"{what}: backslash or colon")
    if path.startswith("/"):
        raise VerificationFailure("PATH_MALFORMED", f"{what}: absolute path")
    for component in path.split("/"):
        if component in ("", ".", ".."):
            raise VerificationFailure("PATH_MALFORMED", f"{what}: empty, dot or dot-dot component")
        if component.endswith(".") or component.endswith(" "):
            raise VerificationFailure("PATH_MALFORMED", f"{what}: component ends in dot or space")
    return path


def _read_bytes(path: Path, what: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise VerificationFailure("INPUT_UNREADABLE", f"{what}: {type(exc).__name__}") from None


# ---------------------------------------------------------------------------
# committed inputs
# ---------------------------------------------------------------------------


def load_inventory(repo_root: Path) -> dict:
    """The committed PE-5-approved PI-PC1 inventory, plus the APS binding."""
    inventory_path = repo_root / INVENTORY_DIR_RELATIVE / f"{PAYLOAD_FINGERPRINT}.json"
    aps_path = repo_root / APS_RELATIVE
    inventory_bytes = _read_bytes(inventory_path, "inventory")
    aps_bytes = _read_bytes(aps_path, "aps")
    try:
        inventory = json.loads(inventory_bytes.decode("utf-8"))
        aps = json.loads(aps_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise VerificationFailure("INPUT_MALFORMED", "inventory or APS is not valid UTF-8 JSON") from None
    if not isinstance(inventory, dict) or inventory.get("record_kind") != "aido-pi-payload-inventory.v1":
        raise VerificationFailure("INPUT_MALFORMED", "inventory record_kind")
    if inventory.get("payload_contract") != "PI-PC1":
        raise VerificationFailure("INPUT_MALFORMED", "inventory payload_contract")
    entries = inventory.get("entries")
    if not isinstance(entries, list) or not entries:
        raise VerificationFailure("INPUT_MALFORMED", "inventory entries")

    # Binding: the APS revision-2 profile must name exactly this inventory.
    profiles = aps.get("profiles") if isinstance(aps, dict) else None
    bound = [
        p for p in (profiles or [])
        if isinstance(p, dict) and p.get("profile_id") == PROFILE_ID
    ]
    if len(bound) != 1 or bound[0].get("payload_fingerprint") != PAYLOAD_FINGERPRINT:
        raise VerificationFailure("INPUT_MALFORMED", "APS r0002 does not bind the profile to this inventory")
    declared = bound[0].get("declared")
    if not isinstance(declared, dict) or declared.get("package_version") != PACKAGE_VERSION:
        raise VerificationFailure("INPUT_MALFORMED", "APS declared package_version")

    files: dict[str, tuple[int, str]] = {}
    directories: set[str] = set()
    seen_casefold: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise VerificationFailure("INPUT_MALFORMED", f"inventory entry {index} is not an object")
        path = validate_relative_path(entry.get("path"), f"inventory entry {index}")
        folded = path.casefold()
        if folded in seen_casefold:
            raise VerificationFailure("INPUT_MALFORMED", f"inventory case collision at entry {index}")
        seen_casefold[folded] = path
        kind = entry.get("kind")
        if kind == "dir":
            if set(entry) != {"kind", "path"}:
                raise VerificationFailure("INPUT_MALFORMED", f"inventory dir entry {index} fields")
            directories.add(path)
        elif kind == "file":
            size, digest = entry.get("size"), entry.get("sha256")
            if set(entry) != {"kind", "path", "size", "sha256"}:
                raise VerificationFailure("INPUT_MALFORMED", f"inventory file entry {index} fields")
            if type(size) is not int or size < 0:
                raise VerificationFailure("INPUT_MALFORMED", f"inventory file entry {index} size")
            if not isinstance(digest, str) or not _HEX64.match(digest):
                raise VerificationFailure("INPUT_MALFORMED", f"inventory file entry {index} sha256")
            files[path] = (size, digest)
        else:
            raise VerificationFailure("INPUT_MALFORMED", f"inventory entry {index} kind")
    return {
        "files": files,
        "directory_count": len(directories),
        "file_count": len(files),
        "entry_count": len(entries),
        "inventory_sha256": sha256_hex(inventory_bytes),
        "aps_sha256": sha256_hex(aps_bytes),
    }


_APPENDIX_ROW = re.compile(r"^(A|B|B/R|C/R|D/R|UNPROVEN)[ \t]+(\S+)$")
_DIGEST_ROW = re.compile(r"^(A|B \(F\)|B \(R\)|C \(R\)|D \(R\)|UNPROVEN|U126)[ \t]+(\d+)[ \t]+([0-9a-f]{64}|\(empty\))")
_TABLE_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|")
_HISTORIC = re.compile(r"\(historic: the 57 as submitted: ([0-9a-f]{64})\)")
_SORTED_LINE = re.compile(r"Sorted-path SHA-256 of this set: `([0-9a-f]{64})`")


def _section(lines: list[str], start_marker: str, end_marker: str) -> list[str]:
    starts = [i for i, line in enumerate(lines) if line.startswith(start_marker)]
    if len(starts) != 1:
        raise VerificationFailure("INPUT_MALFORMED", f"amendment marker {start_marker!r} occurs {len(starts)} times")
    start = starts[0]
    for end in range(start + 1, len(lines)):
        if lines[end].startswith(end_marker):
            return lines[start + 1:end]
    raise VerificationFailure("INPUT_MALFORMED", f"amendment end marker {end_marker!r} not found")


def parse_amendment(text: str) -> dict:
    """Extract the Appendix U126 rows, its stated digests and the two per-path
    tables of 8.10, then cross-check them against each other."""
    lines = text.splitlines()

    appendix = _section(lines, "## Appendix U126", "## Status")
    rows: list[tuple[str, str]] = []
    stated: dict[str, tuple[int | None, str | None]] = {}
    historic = None
    for line in appendix:
        match = _APPENDIX_ROW.match(line)
        if match:
            rows.append((match.group(1), match.group(2)))
            continue
        digest = _DIGEST_ROW.match(line)
        if digest:
            label = DIGEST_TABLE_LABELS[digest.group(1)]
            stated[label] = (int(digest.group(2)), None if digest.group(3) == "(empty)" else digest.group(3))
            continue
        old = _HISTORIC.search(line)
        if old:
            historic = old.group(1)
    if not rows:
        raise VerificationFailure("INPUT_MALFORMED", "no Appendix U126 rows parsed")
    if historic is None:
        raise VerificationFailure("INPUT_MALFORMED", "historic 57-path digest not found")
    if set(stated) != set(DIGEST_TABLE_LABELS.values()):
        raise VerificationFailure("INPUT_MALFORMED", "Appendix digest table incomplete")

    by_basis: dict[str, list[str]] = {basis: [] for basis in ALL_BASES}
    seen: set[str] = set()
    for basis, path in rows:
        validate_relative_path(path, "Appendix row")
        if path in seen:
            raise VerificationFailure("INPUT_MALFORMED", "duplicate Appendix row")
        seen.add(path)
        by_basis[basis].append(path)

    # 8.10.5: the 57 as submitted.
    block_105 = _section(lines, "**8.10.5 `U126_READ_UNPROVEN`", "**What the frozen record says about the files")
    table_105: list[tuple[int, str]] = []
    sorted_line = None
    for line in block_105:
        match = _TABLE_ROW.match(line)
        if match:
            table_105.append((int(match.group(1)), match.group(2)))
        digest_match = _SORTED_LINE.search(line)
        if digest_match:
            sorted_line = digest_match.group(1)
    if sorted_line is None:
        raise VerificationFailure("INPUT_MALFORMED", "8.10.5 sorted-path digest not found")

    # 8.10.8(9): the per-path disposition table.
    block_9 = _section(lines, "*(9) Path-by-path disposition of the 57.*", "*(10) Result.*")
    table_9: list[tuple[int, str, str]] = []
    for line in block_9:
        match = _TABLE_ROW.match(line)
        if match:
            basis = re.match(r"\*\*([BCD])\*\*", match.group(3))
            if not basis:
                raise VerificationFailure("INPUT_MALFORMED", "8.10.8(9) row without a basis letter")
            table_9.append((int(match.group(1)), match.group(2), basis.group(1)))

    for what, numbers in (("8.10.5", [n for n, _ in table_105]), ("8.10.8(9)", [n for n, _, _ in table_9])):
        if numbers != list(range(1, len(numbers) + 1)):
            raise VerificationFailure("INPUT_MALFORMED", f"{what} row numbering is not 1..n")
    return {
        "by_basis": by_basis,
        "stated": stated,
        "historic_57_digest": historic,
        "table_105_paths": [p for _, p in table_105],
        "table_105_digest": sorted_line,
        "table_9": [(p, letter) for _, p, letter in table_9],
    }


# ---------------------------------------------------------------------------
# registry access (the only network surface; injectable for tests)
# ---------------------------------------------------------------------------


class _RestrictedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname != REGISTRY_HOST:
            raise urllib.error.URLError("redirect outside https://" + REGISTRY_HOST + " refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class RegistryClient:
    """Unauthenticated, read-only HTTPS GET against the public npm registry.

    Direct connection (environment proxies are NOT consulted, so no proxy
    credential can ride along); no cookies, no ``Authorization``; the response is
    read to a hard byte bound and treated as untrusted data.
    """

    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _RestrictedRedirects()
        )

    def _get(self, url: str, limit: int, accept: str) -> bytes:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != REGISTRY_HOST or parsed.username or parsed.password:
            raise VerificationFailure("DOWNLOAD_REFUSED", "URL is not a plain https://" + REGISTRY_HOST + " URL")
        request = urllib.request.Request(
            url, method="GET",
            headers={"Accept": accept, "Accept-Encoding": "identity", "User-Agent": USER_AGENT},
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                final = urllib.parse.urlsplit(response.geturl())
                if final.scheme != "https" or final.hostname != REGISTRY_HOST:
                    raise VerificationFailure("DOWNLOAD_REFUSED", "final URL left the registry host")
                data = response.read(limit + 1)
        except VerificationFailure:
            raise
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise VerificationFailure("DOWNLOAD_FAILED", type(exc).__name__) from None
        if len(data) > limit:
            raise VerificationFailure("DOWNLOAD_TOO_LARGE", f"over the {limit}-byte bound")
        return data

    def get_version_metadata(self, package: str, version: str) -> bytes:
        quoted = urllib.parse.quote(package, safe="@").replace("/", "%2F")
        return self._get(f"https://{REGISTRY_HOST}/{quoted}/{version}", MAX_METADATA_BYTES, "application/json")

    def get_tarball(self, url: str) -> bytes:
        return self._get(url, MAX_TARBALL_BYTES, "application/octet-stream")


# ---------------------------------------------------------------------------
# tarball verification
# ---------------------------------------------------------------------------


def _check_registry_metadata(package: str, raw: bytes) -> dict:
    try:
        metadata = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise VerificationFailure("REGISTRY_METADATA_INVALID", f"{package}: not UTF-8 JSON") from None
    if not isinstance(metadata, dict):
        raise VerificationFailure("REGISTRY_METADATA_INVALID", f"{package}: not an object")
    if metadata.get("name") != package or metadata.get("version") != PACKAGE_VERSION:
        raise VerificationFailure("REGISTRY_METADATA_INVALID", f"{package}: name or version differs")
    dist = metadata.get("dist")
    if not isinstance(dist, dict):
        raise VerificationFailure("REGISTRY_METADATA_INVALID", f"{package}: no dist object")
    tarball = dist.get("tarball")
    parsed = urllib.parse.urlsplit(tarball) if isinstance(tarball, str) else None
    if (
        parsed is None or parsed.scheme != "https" or parsed.hostname != REGISTRY_HOST
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or not parsed.path.endswith(".tgz")
    ):
        raise VerificationFailure("REGISTRY_METADATA_INVALID", f"{package}: dist.tarball is not a plain registry .tgz URL")
    return dist


_HASHES = {"sha512": hashlib.sha512, "sha384": hashlib.sha384, "sha256": hashlib.sha256, "sha1": hashlib.sha1}


def verify_integrity(package: str, dist: dict, tarball: bytes) -> dict:
    """Check ``dist.integrity`` (SRI) and ``dist.shasum`` when supplied.

    Supplied-but-unusable or mismatching metadata is a refusal. Neither field
    present is recorded as ``not_supplied`` (and is not an integrity PASS).
    """
    result = {"integrity": "not_supplied", "shasum": "not_supplied"}
    integrity = dist.get("integrity")
    if integrity is not None:
        if not isinstance(integrity, str) or not integrity.strip():
            raise VerificationFailure("INTEGRITY_UNUSABLE", f"{package}: dist.integrity is not a string")
        verified = []
        for token in integrity.split():
            algorithm, _, encoded = token.partition("-")
            if algorithm not in _HASHES or not encoded:
                raise VerificationFailure("INTEGRITY_UNUSABLE", f"{package}: unsupported integrity token")
            try:
                expected = base64.b64decode(encoded, validate=True)
            except ValueError:
                raise VerificationFailure("INTEGRITY_UNUSABLE", f"{package}: integrity is not base64") from None
            if _HASHES[algorithm](tarball).digest() != expected:
                raise VerificationFailure("INTEGRITY_MISMATCH", f"{package}: {algorithm} digest differs")
            verified.append(algorithm)
        result["integrity"] = "verified:" + "+".join(sorted(verified))
    shasum = dist.get("shasum")
    if shasum is not None:
        if not isinstance(shasum, str) or not re.fullmatch(r"[0-9a-f]{40}", shasum):
            raise VerificationFailure("INTEGRITY_UNUSABLE", f"{package}: dist.shasum is not 40 hex digits")
        if hashlib.sha1(tarball).hexdigest() != shasum:
            raise VerificationFailure("INTEGRITY_MISMATCH", f"{package}: sha1 shasum differs")
        result["shasum"] = "verified:sha1"
    return result


def read_tarball(package: str, prefix: str, tarball: bytes, inventory_files: dict) -> list[dict]:
    """Read every member of one tarball as untrusted data.

    Returns one record per member: ``path`` (payload-relative), ``size``,
    ``sha256``, ``equals_inventory``. Structural problems and size mismatches
    raise immediately; digest mismatches are returned so the caller can count
    all of them.
    """
    try:
        archive = tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz")
    except (tarfile.TarError, OSError, EOFError):
        raise VerificationFailure("ARCHIVE_UNREADABLE", f"{package}: not a readable gzip tar") from None
    records: list[dict] = []
    seen: set[str] = set()
    seen_folded: set[str] = set()
    try:
        with archive:
            while True:
                try:
                    member = archive.next()
                except (tarfile.TarError, OSError, EOFError):
                    raise VerificationFailure("ARCHIVE_UNREADABLE", f"{package}: corrupt member header") from None
                if member is None:
                    break
                if len(records) >= MAX_MEMBER_COUNT:
                    raise VerificationFailure("ARCHIVE_UNSAFE_MEMBER", f"{package}: member count bound exceeded")
                name = member.name
                if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or member.issparse():
                    raise VerificationFailure(
                        "ARCHIVE_UNSAFE_MEMBER", f"{package}: non-regular member (type {member.type!r})"
                    )
                if member.islnk() or member.issym() or member.linkname:
                    raise VerificationFailure("ARCHIVE_UNSAFE_MEMBER", f"{package}: link member")
                if not name.startswith("package/"):
                    raise VerificationFailure("ARCHIVE_UNSAFE_MEMBER", f"{package}: member outside the package/ prefix")
                relative = validate_relative_path(name[len("package/"):], f"{package} member")
                payload_path = f"{prefix}/{relative}" if prefix else relative
                if payload_path in seen:
                    raise VerificationFailure("ARCHIVE_DUPLICATE_PATH", f"{package}: duplicate member path")
                folded = payload_path.casefold()
                if folded in seen_folded:
                    raise VerificationFailure("ARCHIVE_CASE_COLLISION", f"{package}: case-colliding member path")
                seen.add(payload_path)
                seen_folded.add(folded)
                approved = inventory_files.get(payload_path)
                if approved is None:
                    raise VerificationFailure(
                        "ARCHIVE_MEMBER_NOT_IN_INVENTORY", f"{package}: member path absent from the approved inventory"
                    )
                size, digest = approved
                if member.size != size:
                    # Refuse at once: a body whose declared size is not the approved size is never read, and the
                    # archive is not advanced past it (skipping it would decompress an attacker-chosen length).
                    raise VerificationFailure("MEMBER_SIZE_MISMATCH", f"{package}: a member's declared size differs from its approved size")
                handle = archive.extractfile(member)
                if handle is None:
                    raise VerificationFailure("ARCHIVE_UNSAFE_MEMBER", f"{package}: member has no readable body")
                try:
                    body = handle.read(size + 1)
                except (tarfile.TarError, OSError, EOFError):
                    raise VerificationFailure("ARCHIVE_UNREADABLE", f"{package}: truncated member body") from None
                if len(body) != size:
                    raise VerificationFailure("MEMBER_SIZE_MISMATCH", f"{package}: a member's body length differs from its approved size")
                actual = sha256_hex(body)
                ok = actual == digest
                records.append({"path": payload_path, "size": size, "sha256": actual, "equals_inventory": ok,
                                "problem": None if ok else "MEMBER_DIGEST_MISMATCH", "package": package})
    except VerificationFailure:
        raise
    except (tarfile.TarError, OSError, EOFError):
        raise VerificationFailure("ARCHIVE_UNREADABLE", f"{package}: archive read error") from None
    if not records:
        raise VerificationFailure("ARCHIVE_UNREADABLE", f"{package}: archive has no members")
    return records


# ---------------------------------------------------------------------------
# the whole verification
# ---------------------------------------------------------------------------


def verify(repo_root: Path, client) -> dict:
    """Run the full verification and return the report dict (verdict PASS).

    Raises ``VerificationFailure`` on the first fail-closed condition.
    """
    amendment_path = repo_root / AMENDMENT_RELATIVE
    # The amendment is checked out with the platform's line endings (autocrlf); the input identity recorded in
    # the report is therefore taken over the LF-normalized bytes, so it does not depend on the checkout.
    amendment_bytes = _read_bytes(amendment_path, "amendment").replace(b"\r\n", b"\n")
    try:
        amendment_text = amendment_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise VerificationFailure("INPUT_MALFORMED", "amendment is not UTF-8") from None
    inventory = load_inventory(repo_root)
    files = inventory["files"]
    parsed = parse_amendment(amendment_text)
    by_basis = parsed["by_basis"]

    # ---- document-internal consistency (measured on the amendment's own text)
    if by_basis["UNPROVEN"]:
        raise VerificationFailure("AMENDMENT_INCONSISTENT", "Appendix still has UNPROVEN rows")
    review_paths = sorted(p for basis in REVIEW_BASES for p in by_basis[basis])
    all_126 = sorted(p for basis in ALL_BASES for p in by_basis[basis])
    if len(review_paths) != 57 or len(set(review_paths)) != 57:
        raise VerificationFailure("AMENDMENT_INCONSISTENT", f"review set has {len(review_paths)} rows, expected 57")
    if len(all_126) != 126:
        raise VerificationFailure("AMENDMENT_INCONSISTENT", f"Appendix has {len(all_126)} rows, expected 126")
    if sorted(parsed["table_105_paths"]) != review_paths:
        raise VerificationFailure("AMENDMENT_INCONSISTENT", "8.10.5 table differs from the Appendix R rows")
    if len(parsed["table_105_paths"]) != 57:
        raise VerificationFailure("AMENDMENT_INCONSISTENT", "8.10.5 table is not 57 rows")
    table_9 = dict(parsed["table_9"])
    if len(parsed["table_9"]) != 57 or set(table_9) != set(review_paths):
        raise VerificationFailure("AMENDMENT_INCONSISTENT", "8.10.8(9) table differs from the Appendix R rows")
    for basis in REVIEW_BASES:
        for path in by_basis[basis]:
            if table_9[path] != basis[0]:
                raise VerificationFailure("AMENDMENT_INCONSISTENT", "8.10.8(9) basis letter differs from the Appendix")
    missing_from_inventory = [p for p in all_126 if p not in files]
    if missing_from_inventory:
        raise VerificationFailure("AMENDMENT_INCONSISTENT", f"{len(missing_from_inventory)} U126 paths are not inventory files")

    set_digests = {}
    digest_inputs = {
        "original_57": (review_paths, parsed["historic_57_digest"]),
        "original_57_per_8.10.5": (parsed["table_105_paths"], parsed["table_105_digest"]),
        "A": (by_basis["A"], parsed["stated"]["A"][1]),
        "B_F": (by_basis["B"], parsed["stated"]["B"][1]),
        "B_R": (by_basis["B/R"], parsed["stated"]["B/R"][1]),
        "C_R": (by_basis["C/R"], parsed["stated"]["C/R"][1]),
        "D_R": (by_basis["D/R"], parsed["stated"]["D/R"][1]),
        "U126": (all_126, parsed["stated"]["U126"][1]),
    }
    stated_counts = {
        "A": parsed["stated"]["A"][0], "B_F": parsed["stated"]["B"][0], "B_R": parsed["stated"]["B/R"][0],
        "C_R": parsed["stated"]["C/R"][0], "D_R": parsed["stated"]["D/R"][0], "U126": parsed["stated"]["U126"][0],
        "original_57": 57, "original_57_per_8.10.5": 57,
    }
    for name, (paths, stated_digest) in sorted(digest_inputs.items()):
        computed = path_set_digest(paths)
        equal = computed == stated_digest
        count_equal = len(paths) == stated_counts[name]
        set_digests[name] = {
            "count": len(paths),
            "stated_count_equal": count_equal,
            "computed_sha256": computed,
            "stated_sha256": stated_digest,
            "equal": equal,
        }
        if not equal or not count_equal:
            raise VerificationFailure("SET_DIGEST_MISMATCH", f"path-set {name}: recomputed digest or count differs from the amendment")
    if parsed["stated"]["UNPROVEN"] != (0, None):
        raise VerificationFailure("AMENDMENT_INCONSISTENT", "UNPROVEN digest row is not 0 / (empty)")

    # ---- download + per-tarball verification
    package_reports = []
    all_records: list[dict] = []
    for package, prefix in PACKAGES:
        metadata_raw = client.get_version_metadata(package, PACKAGE_VERSION)
        dist = _check_registry_metadata(package, metadata_raw)
        tarball = client.get_tarball(dist["tarball"])
        integrity = verify_integrity(package, dist, tarball)
        records = read_tarball(package, prefix, tarball, files)
        package_reports.append({
            "package": package,
            "version": PACKAGE_VERSION,
            "payload_prefix": prefix,
            "tarball_url": dist["tarball"],
            "tarball_bytes": len(tarball),
            "tarball_sha256": sha256_hex(tarball),
            "registry_integrity_check": integrity,
            "member_count": len(records),
        })
        all_records.extend(records)

    # ---- cross-tarball structure
    seen: dict[str, str] = {}
    seen_folded: dict[str, str] = {}
    for record in all_records:
        path = record["path"]
        if path in seen:
            raise VerificationFailure("ARCHIVE_DUPLICATE_PATH", "a payload path is claimed by two tarballs")
        folded = path.casefold()
        if folded in seen_folded:
            raise VerificationFailure("ARCHIVE_CASE_COLLISION", "case-colliding payload paths across tarballs")
        seen[path] = record["package"]
        seen_folded[folded] = path

    problems = [r for r in all_records if not r["equals_inventory"]]
    if problems:
        sample = sorted(r["path"] for r in problems)[:10]
        raise VerificationFailure(
            "MEMBER_MISMATCH", f"{len(problems)} member(s) differ from the inventory (sha256); first: {sample}"
        )

    recovered = {r["path"]: r for r in all_records}
    missing_review = [p for p in review_paths if p not in recovered]
    if missing_review:
        raise VerificationFailure("REVIEW_FILE_MISSING", f"{len(missing_review)} review file(s) not in the tarballs: {missing_review[:10]}")
    review_files = []
    for path in review_paths:
        record = recovered[path]
        size, digest = files[path]
        if not (record["path"] == path and record["size"] == size and record["sha256"] == digest):
            raise VerificationFailure("REVIEW_FILE_MISMATCH", f"review file {path} differs from the inventory entry")
        review_files.append({"path": path, "size": size, "sha256": digest, "source_package": record["package"],
                             "basis_per_amendment": next(b for b in REVIEW_BASES if path in by_basis[b])})

    other_69 = sorted(by_basis["A"] + by_basis["B"])
    other_recovered = [p for p in other_69 if p in recovered]
    other_not_in_packages = [p for p in other_69 if p not in recovered]
    measured = {
        "tarball_member_count": len(all_records),
        "review_files_recovered": len(review_files),
        "other_u126_recovered": len(other_recovered),
        "other_u126_not_in_packages": len(other_not_in_packages),
        "approved_file_count": inventory["file_count"],
        "approved_files_not_in_tarballs": inventory["file_count"] - len(all_records),
    }
    agreement = {key: {"measured": measured[key], "amendment_states": AMENDMENT_STATED[key],
                       "agree": measured[key] == AMENDMENT_STATED[key]} for key in sorted(AMENDMENT_STATED)}

    return {
        "record_kind": RECORD_KIND,
        "verdict": "PASS",
        "failures": [],
        "subject": {
            "profile_id": PROFILE_ID,
            "payload_fingerprint": PAYLOAD_FINGERPRINT,
            "package_version": PACKAGE_VERSION,
        },
        "inputs": {
            "amendment": {"repo_path": AMENDMENT_RELATIVE, "sha256_after_crlf_to_lf": sha256_hex(amendment_bytes)},
            "approved_inventory": {
                "repo_path": f"{INVENTORY_DIR_RELATIVE}/{PAYLOAD_FINGERPRINT}.json",
                "sha256": inventory["inventory_sha256"],
                "entry_count": inventory["entry_count"],
                "file_count": inventory["file_count"],
                "directory_count": inventory["directory_count"],
                "bound_by_aps": {"repo_path": APS_RELATIVE, "sha256": inventory["aps_sha256"],
                                  "profile_id": PROFILE_ID},
            },
        },
        "measured_facts": {
            "statement": "Each item below was computed by this program from bytes or from the committed text; "
                         "none is an interpretation of what any file does.",
            "packages": package_reports,
            "archive_safety": {
                "rule": "regular-file members only, under package/, validated relative paths, no link, no duplicate, "
                        "no case collision, every member present in the approved inventory",
                "unsafe_or_rejected_members": 0,
                "members_not_in_inventory": 0,
            },
            "members_vs_inventory": {
                "members": len(all_records),
                "equal_by_path_size_sha256": len(all_records),
                "size_or_digest_mismatches": 0,
            },
            "review_set": {
                "count": len(review_files),
                "recovered_and_exactly_equal": len(review_files),
                "failed_or_unavailable": 0,
                "sorted_path_sha256": path_set_digest(review_paths),
                "files": review_files,
            },
            "path_set_digests_recomputed_from_amendment_rows": {
                "convention": "sha256 of the UTF-8 paths, sorted, joined by LF, no trailing newline",
                "sets": set_digests,
            },
            "amendment_internal_consistency": {
                "appendix_rows": len(all_126),
                "section_8_10_5_table_equals_appendix_R_rows": True,
                "section_8_10_8_9_table_equals_appendix_R_rows": True,
                "section_8_10_8_9_basis_letter_equals_appendix_suffix": True,
                "unproven_rows": 0,
                "all_u126_paths_are_approved_inventory_files": True,
            },
            "other_u126_files_not_re_reviewed": {
                "count": len(other_69),
                "incidentally_recovered_and_equal": len(other_recovered),
                "not_in_the_five_packages": len(other_not_in_packages),
                "not_in_the_five_packages_paths": other_not_in_packages,
            },
            "agreement_with_amendment_stated_numbers": agreement,
        },
        "author_semantic_analysis": {
            "status": "AUTHOR_CLAIM_NOT_VERIFIED_BY_THIS_PROGRAM",
            "source": "amendment section 8.10.8 (static review by the amendment's author; not independently reviewed)",
            "claimed_basis_counts": {"B": len(by_basis["B/R"]), "C": len(by_basis["C/R"]), "D": len(by_basis["D/R"]), "E": 0},
            "claimed_u126_read_unproven_count": 0,
            "note": "The counts above are READ FROM THE AMENDMENT'S OWN ROWS. This program did not read, search, "
                    "parse or execute the JavaScript and so measured no import.meta / path-derivation / filesystem-read "
                    "route. Matching checksums show only that the reviewed bytes were the approved bytes.",
        },
        "not_established": [
            "that the B / C / D read-relocation classification of any file is correct",
            "that any of the 57 files was read, or is harmless, or runs correctly from the relocated package",
            "that the recovered files form a complete approved installation",
            "anything about the other 69 U126 files beyond whether their bytes were incidentally present",
            "anything about Node, Pi, npm or any model; none was run",
        ],
        "scope_declaration": {
            "network": "five unauthenticated HTTPS GETs of version metadata and five of tarballs from "
                       + REGISTRY_HOST + "; no credential, cookie or authorization header; environment proxies not used",
            "execution": "none: no Node, Pi, npm, lifecycle script or downloaded code was executed or imported",
            "downloaded_bytes_persisted": False,
            "repository_files_written_by_verification": "report only, and only when --report is given",
        },
    }


def failure_report(failure: VerificationFailure) -> dict:
    return {
        "record_kind": RECORD_KIND,
        "verdict": "FAIL",
        "failures": [{"code": failure.code, "detail": failure.detail}],
        "subject": {"profile_id": PROFILE_ID, "payload_fingerprint": PAYLOAD_FINGERPRINT, "package_version": PACKAGE_VERSION},
        "not_established": ["everything: verification stopped at the first fail-closed condition"],
    }


def render(report: dict) -> bytes:
    """Deterministic serialization: sorted keys, 2-space indent, LF, trailing LF."""
    return (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def run(repo_root: Path, client) -> tuple[dict, int]:
    try:
        return verify(repo_root, client), 0
    except VerificationFailure as failure:
        return failure_report(failure), 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--report", help="write the deterministic JSON report to this path")
    parser.add_argument("--compare-with", help="exit 0 only if the regenerated report is byte-identical to this file "
                                               "(CRLF checkouts are compared after CRLF -> LF)")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    report, status = run(repo_root, RegistryClient())
    rendered = render(report)
    if args.report:
        Path(args.report).write_bytes(rendered)
    if args.compare_with:
        existing = _read_bytes(Path(args.compare_with), "comparison report").replace(b"\r\n", b"\n")
        identical = existing == rendered
        print(f"byte-identical to {args.compare_with}: {identical}")
        if not identical:
            status = status or 2
    print(f"verdict: {report['verdict']}")
    for failure in report.get("failures", []):
        print(f"  {failure['code']}: {failure['detail']}")
    return status


if __name__ == "__main__":
    sys.exit(main())
