"""DL-4B S7 — the operator's statement helper, run as the operator identity O.

O signs with the hardware authenticator, which AIDO never touches. This helper
only turns what A presented (a ``request-approval`` report, read from
``published/``) into the exact bytes O signs, and O's signature into the
``human-attestation.v2`` O places in the inbox:

```text
statement     report + approver id + key fingerprint + attested_at
              → attestation-statement.v1 canonical bytes on stdout
              (O redirects them to a file in O's own profile, byte for byte)
O             ssh-keygen -Y sign -f <sk key> -n aido-approval@v1 <statement file>
attestation   report + approver id + attested_at + the .sig file
              → human-attestation.v2 JSON on stdout (O redirects it into the inbox)
```

Nothing here is authority. The verifier rebuilds the statement from A's own
records and checks the signature against the registry (S1); a wrong helper
output can only fail verification. The helper opens no session, reads no
environment, launches nothing and writes no file: its only input files are the
report and the signature O names, and its only output is stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from ai_dev_orchestrator.control_plane.attestation_v2 import (
    ApprovalChallengeV2,
    AttestationStatementV1,
    HumanAttestationV2,
)
from ai_dev_orchestrator.control_plane.models import canonical_json_bytes

REPORT_SCHEMA_VERSION = "alpha-driver-report.v1"
#: Bounds on what O's helper reads. A report is a few kilobytes; an armored
#: security-key signature is a few hundred bytes.
MAX_REPORT_BYTES = 1024 * 1024
MAX_SIGNATURE_BYTES = 16 * 1024


class OperatorInputError(ValueError):
    """The presented report, an argument or the signature file is unusable."""


def presented_challenge(report: bytes) -> tuple[str, ApprovalChallengeV2]:
    """The state root id and the challenge of one ``request-approval``
    report: exactly one JSON object of the driver's report schema."""
    if type(report) is not bytes or len(report) > MAX_REPORT_BYTES:
        raise OperatorInputError("the report is not a bounded byte string.")
    try:
        document = json.loads(report.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OperatorInputError("the report is not exactly one UTF-8 JSON document.") from None
    if type(document) is not dict or document.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise OperatorInputError("the file is not an alpha-driver-report.v1.")
    if document.get("verb") != "request-approval" or document.get("refusal") is not None:
        raise OperatorInputError("only a successful request-approval report presents a challenge.")
    root, challenge = document.get("state_root_id"), document.get("challenge")
    if type(root) is not str or type(challenge) is not dict:
        raise OperatorInputError("the report names no state root or no challenge.")
    try:
        return root, ApprovalChallengeV2.model_validate_json(json.dumps(challenge))
    except ValueError:
        raise OperatorInputError("the presented challenge is not an approval-challenge.v2.") from None


def _attested(challenge: ApprovalChallengeV2, attested_at: datetime) -> datetime:
    if type(attested_at) is not datetime or attested_at.tzinfo is None:
        raise OperatorInputError("attested_at is an aware instant.")
    if not challenge.issued_at <= attested_at < challenge.expires_at:
        raise OperatorInputError("attested_at is outside the challenge's window.")
    return attested_at


def statement_bytes(report: bytes, *, approver_id: str, key_fingerprint_sha256: str,
                    attested_at: datetime) -> bytes:
    """The exact ``attestation-statement.v1`` bytes O signs."""
    root, challenge = presented_challenge(report)
    try:
        statement = AttestationStatementV1(
            schema_version="attestation-statement.v1", namespace="aido-approval@v1", state_root_id=root,
            challenge_id=challenge.challenge_id, subject_kind=challenge.subject_kind,
            subject_sha256=challenge.subject_sha256, approver_id=approver_id,
            key_fingerprint_sha256=key_fingerprint_sha256, attested_at=_attested(challenge, attested_at),
            expires_at=challenge.expires_at, approval_text=challenge.required_approval_text,
        )
    except ValueError as exc:
        raise OperatorInputError(f"the statement does not validate: {exc}") from None
    return statement.canonical_bytes()


def attestation_bytes(report: bytes, *, approver_id: str, attested_at: datetime, signature: str) -> bytes:
    """The ``human-attestation.v2`` O places in the inbox, carrying the
    armored signature verbatim (never repaired)."""
    _, challenge = presented_challenge(report)
    try:
        attestation = HumanAttestationV2(
            schema_version="human-attestation.v2", challenge_id=challenge.challenge_id,
            subject_kind=challenge.subject_kind, subject_sha256=challenge.subject_sha256,
            approver_id=approver_id, attested_at=_attested(challenge, attested_at),
            approval_text=challenge.required_approval_text, proof=signature,
        )
    except ValueError as exc:
        raise OperatorInputError(f"the attestation does not validate: {exc}") from None
    return canonical_json_bytes(attestation.model_dump(mode="json"))


def _read(path: str, limit: int, what: str) -> bytes:
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError as exc:
        raise OperatorInputError(f"the {what} could not be read ({type(exc).__name__}).") from None
    if len(data) > limit:
        raise OperatorInputError(f"the {what} exceeds its size bound.")
    return data


def _instant(text: str) -> datetime:
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("an RFC 3339 instant with an offset, e.g. 2026-10-27T18:05:00Z") from None
    if value.tzinfo is None:
        raise argparse.ArgumentTypeError("the instant needs an offset (Z or +hh:mm).")
    return value


def main(argv: list[str] | None = None) -> int:
    """``python -I -m ai_dev_orchestrator.integration.alpha_operator statement|attestation ...``"""
    parser = argparse.ArgumentParser(prog="alpha_operator", description="DL-4B S7 operator statement helper (O).")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("statement", "attestation"):
        command = commands.add_parser(name)
        command.add_argument("--report", required=True, help="the request-approval report A published")
        command.add_argument("--approver-id", required=True)
        command.add_argument("--attested-at", required=True, type=_instant)
        if name == "statement":
            command.add_argument("--key-fingerprint", required=True, help="SHA256:... of the registered key")
        else:
            command.add_argument("--signature", required=True, help="the .sig file ssh-keygen -Y sign wrote")
    args = parser.parse_args(argv)
    try:
        report = _read(args.report, MAX_REPORT_BYTES, "report")
        if args.command == "statement":
            output = statement_bytes(report, approver_id=args.approver_id,
                                     key_fingerprint_sha256=args.key_fingerprint, attested_at=args.attested_at)
        else:
            signature = _read(args.signature, MAX_SIGNATURE_BYTES, "signature file")
            try:
                text = signature.decode("ascii")
            except UnicodeDecodeError:
                raise OperatorInputError("the signature file is not ASCII armor.") from None
            output = attestation_bytes(report, approver_id=args.approver_id, attested_at=args.attested_at,
                                       signature=text)
    except OperatorInputError as exc:
        sys.stderr.write(f"refused: {exc}\n")
        return 1
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover - the operator's launch
    raise SystemExit(main())
