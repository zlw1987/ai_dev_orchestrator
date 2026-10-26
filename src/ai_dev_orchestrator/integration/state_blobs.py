"""DL-4B S3 — write-once blobs of the integration store, in the state root.

store.v4 rows name bytes by SHA-256; the bytes live in the authority
identity's state root, which X cannot write, delete or re-permission (FD-14):

```text
<state root>\\evidence\\approved-diff\\<sha256>   the human-approved artifact, verbatim
<state root>\\evidence\\config\\<sha256>          the project config bytes X receives
<state root>\\evidence\\claims\\<sha256>          execution-claim stdout bytes, verbatim
<state root>\\evidence\\observations\\<sha256>    authority-observation.v1 manifests
```

Each is published with DL-4A's write-once primitive (exclusive staging file,
fsync, a hard link that never overwrites) **before** any row names it, and
re-hashed on every read. A differing file under an existing name is never
replaced; it makes the read refuse.
"""

from __future__ import annotations

import hashlib
import os
import re

from ai_dev_orchestrator.control_plane.containment import (
    AidoStateRoot,
    ContainmentError,
    _is_reparse,
    _read_regular_file,
    _write_once,
)

BLOB_KINDS = ("approved-diff", "config", "claims", "observations")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def _parts(kind: str) -> tuple[str, str]:
    if kind not in BLOB_KINDS:
        raise ContainmentError("no such blob kind.")
    return ("evidence", kind)


def write_blob(root: AidoStateRoot, kind: str, data: bytes) -> str:
    """Publish ``data`` write-once and return its SHA-256."""
    if type(data) is not bytes:
        raise ContainmentError("a blob is bytes.")
    parts = _parts(kind)
    root.verify()
    evidence = root.contained_directory(("evidence",))
    directory = os.path.join(evidence, kind)
    if not os.path.lexists(directory):
        os.mkdir(directory)
    if _is_reparse(directory) or not os.path.isdir(directory):
        raise ContainmentError("a state root blob directory was replaced.")
    sha256 = hashlib.sha256(data).hexdigest()
    _write_once(root, parts, sha256, data)
    return sha256


def read_blob(root: AidoStateRoot, kind: str, sha256: str, limit: int) -> bytes:
    """The bytes named ``sha256``, re-hashed, or a refusal."""
    if type(sha256) is not str or _HEX64.fullmatch(sha256) is None:
        raise ContainmentError("a blob name must be a SHA-256 digest.")
    directory = root.contained_directory(_parts(kind))
    data = _read_regular_file(os.path.join(directory, sha256), limit)
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ContainmentError("a stored blob no longer hashes to its name.")
    return data
