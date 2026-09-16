"""Post-hoc durable-artifact path binding -- read-only, offline, unauthorizing.

Design Sec. 22.5. Payload validation (Sec. 22.1-22.4) proves a record's own
declared fields agree with each other. It cannot distinguish a genuine
``results/S1-X1/S1_01_Q.json`` from a byte-for-byte copy of it sitting at
``results/S1-X2/S1_01_Q.json``: both payloads are internally self-consistent,
and only the ACTUAL filesystem location differs from what the payload claims.
That stronger claim lives here.

**One argument, and the artifact's own bytes.** An earlier signature took an
already-parsed record as a second argument, which never bound that record to
the CURRENT bytes at the path -- a caller could hold an old genuine ``dict``,
change the file, and still ask "would this old dict belong at this path",
which answers a different, useless question. There is no such parameter: the
verifier reads and parses the artifact itself, so ``True`` means exactly *the
bytes currently at this path form a valid CFG1 artifact, and those same bytes'
own identity fields match that artifact's current filesystem location*.

**Lexical checks run before ``resolve()``.** Resolving first destroys exactly
the evidence these checks exist to see: a symlink alias pointing AT a genuine
record, or an ordinary file under a redirected parent, would both resolve to
something perfectly innocent.

**Never called by the live stage runner, and grants nothing.** A durable record
is not filesystem authority and never recreates a stage-output authority --
nothing in ``results/`` authorizes anything, including a future write. These
functions exist for a human, an auditor, or an offline regression examining
archived evidence after the fact. They never rewrite, repair, or move anything;
``False`` is the entire output, with no exception text, repr or traceback ever
part of it.
"""

from __future__ import annotations

import json
import os
import stat as stat_module
from pathlib import Path

from ai_dev_orchestrator.workspace.canonical import _is_symlink_or_reparse_point

from . import MAX_CFG1_ARTIFACT_BYTES
from .records import (
    _dispatch_run_path_validator,
    _require_valid_cfg1_stage_closure_payload,
    _run_record_filename,
    _stage_closure_record_filename,
)
from .schedule import _schedule_arm_for
from .stage_output import _establish_results_root


def _lexical_resource_checks(actual_path: str) -> bool:
    """Step 1 -- on the ORIGINAL, unresolved path. ``resolve()`` is never called.

    A symlink ALIAS to a genuine record must return ``False``: it is not the
    record itself. A symlink or junction standing in for the execution
    directory must return ``False`` too, even though the artifact beneath it
    may be a perfectly ordinary file.
    """
    lexical = Path(actual_path)
    try:
        leaf = os.lstat(str(lexical))
    except OSError:
        return False
    if _is_symlink_or_reparse_point(leaf):
        return False
    if not stat_module.S_ISREG(leaf.st_mode):
        return False

    try:
        parent = os.lstat(str(lexical.parent))
    except OSError:
        return False
    if _is_symlink_or_reparse_point(parent):
        return False
    if not stat_module.S_ISDIR(parent.st_mode):
        return False
    return True


def _read_and_parse(actual_path: str):
    """Step 2 -- a bounded read of the artifact's OWN bytes. ``None`` on refusal.

    At most ``MAX_CFG1_ARTIFACT_BYTES + 1`` bytes are requested: receiving that
    many means the file exceeds the bound, and the verifier refuses without
    reading further and without parsing anything. The same constant the writer
    checks against, from the same declaration site, so a writer can never
    produce an artifact this read would truncate.
    """
    try:
        with open(actual_path, "rb") as handle:
            data = handle.read(MAX_CFG1_ARTIFACT_BYTES + 1)
    except OSError:
        return None
    if len(data) > MAX_CFG1_ARTIFACT_BYTES:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        parsed = json.loads(text)
    except Exception:  # noqa: BLE001 - malformed JSON is simply False
        return None
    if type(parsed) is not dict:
        return None
    return parsed


def _fresh_reparse_recheck(resolved: Path) -> bool:
    """Step 4 item 11 -- a FRESH ``lstat`` of the leaf and parent, taken again.

    Defense in depth beyond Step 1's earlier check: closes the window in which
    either was genuine at Step 1 and was replaced before this point.
    """
    for candidate in (resolved, resolved.parent):
        try:
            entry = os.lstat(str(candidate))
        except OSError:
            return False
        if _is_symlink_or_reparse_point(entry):
            return False
    return True


def _bind_to_actual_location(actual_path: str, parsed: dict, *, expected_filename: str) -> bool:
    """Step 4 -- every check against the actual, resolved path.

    The root-provenance proof is re-run FRESH here (Level A strictly before
    Level B), never cached and never assumed from the fact that a live stage
    once proved it.
    """
    try:
        results_root = _establish_results_root(create_if_absent=False)
    except Exception:  # noqa: BLE001 - any provenance failure is simply False
        return False

    try:
        resolved = Path(actual_path).resolve(strict=True)
    except OSError:
        return False

    if str(resolved.parent.parent) != results_root:
        return False
    if resolved.parent.name != parsed.get("stage_execution_id"):
        return False
    if resolved.name != expected_filename:
        return False
    return _fresh_reparse_recheck(resolved)


def verify_cfg1_run_artifact_binding(actual_path: str) -> bool:
    """Is the artifact currently at this RUN path valid and correctly located?

    A scheduled run path may genuinely hold exactly ONE OF TWO record kinds:
    the run record itself, or the bounded, non-recursive refusal record written
    at that same path when the primary record's own ``PRE_CREATE`` emission
    failed. Treating a valid refusal artifact as an invalid run-path artifact
    merely because it is not the run kind would be wrong -- it is one of two
    legitimate occupants, not a third, unrecognized one.

    An unknown, missing, mixed or contradictory discriminator pair dispatches
    to no validator at all, and returns ``False`` with zero validator calls.
    """
    # Step 0 -- the lexical input boundary, with ZERO filesystem calls for a
    # non-``str``. Not ``isinstance``, no ``PathLike`` acceptance, no
    # ``os.fspath()``, no ``str()`` coercion.
    if type(actual_path) is not str:
        return False
    if not _lexical_resource_checks(actual_path):
        return False

    parsed = _read_and_parse(actual_path)
    if parsed is None:
        return False

    validator = _dispatch_run_path_validator(parsed)
    if validator is None:
        return False
    try:
        validator(parsed)
    except Exception:  # noqa: BLE001 - any schema failure is simply False
        return False

    stage_id = parsed.get("stage_id")
    run_ordinal = parsed.get("run_ordinal")
    arm_id = parsed.get("arm_id")
    try:
        if arm_id != _schedule_arm_for(stage_id, run_ordinal):
            return False
        expected_filename = _run_record_filename(stage_id, run_ordinal, arm_id)
    except Exception:  # noqa: BLE001
        return False

    return _bind_to_actual_location(actual_path, parsed, expected_filename=expected_filename)


def verify_cfg1_stage_closure_binding(actual_path: str) -> bool:
    """Is the artifact currently at this STAGE-CLOSURE path valid and located?

    No dispatch: a stage-closure path never legitimately holds any kind other
    than ``pi-harness-cfg1-stage-closure.v1``, so a run or refusal record found
    there is simply malformed for that validator, with no branch to take.

    A ``True`` here proves the current bytes are a valid, correctly-bound CFG1
    artifact. It does NOT reconstruct the original, now-gone
    ``CFG1StageClosureDecision``, and it does NOT prove the live
    ``emit_cfg1_stage_closure`` invocation reached ``EMISSION_CONFIRMED``
    rather than merely leaving structurally valid post-create residue behind.
    """
    if type(actual_path) is not str:
        return False
    if not _lexical_resource_checks(actual_path):
        return False

    parsed = _read_and_parse(actual_path)
    if parsed is None:
        return False

    try:
        _require_valid_cfg1_stage_closure_payload(parsed)
    except Exception:  # noqa: BLE001
        return False

    try:
        expected_filename = _stage_closure_record_filename(parsed["stage_id"])
    except Exception:  # noqa: BLE001
        return False

    return _bind_to_actual_location(actual_path, parsed, expected_filename=expected_filename)
