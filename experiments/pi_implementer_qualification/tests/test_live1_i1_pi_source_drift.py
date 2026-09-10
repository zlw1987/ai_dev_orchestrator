"""5F3B-LIVE1-I1-FU2 / **FU4B** / **FU4C** -- the REAL installed-Pi
source-level drift guard for FU4A/FU4B/FU4C Case 45.

**OFFLINE ONLY. No Pi process, no Node process, no ``--help``, no network.**
Every fact this module checks is established by a PLAIN FILE READ of the
already-installed Pi package on disk, located through the SAME
process-free, already-accepted resolver
:func:`qualification.i2b_live_adapters._ar2_resolve_pi_package_root` (the
one :func:`qualification.i2b_live_adapters.preflight_pi_installed_offline`
and :func:`qualification.i2b_live_adapters.resolve_pi_identity` already
compose from). No subprocess is ever launched to obtain any fact here.

Why this module exists, and how it differs from the synthetic wire test
--------------------------------------------------------------------------

``tests/test_semantic_live_adapters.py``'s
``test_case45_prompt_response_and_id_less_parse_arms_match_the_frozen_pi_seam``
proves an AIDO-side compatibility chain: *given* Pi-shaped bytes matching
the documented seam, the frozen AIDO decoder/absorber/LIVE1 classification
handle them correctly. It is unconditionally useful, and it is KEPT. But it
authors its own expected dictionaries -- it can never notice that the
INSTALLED Pi package itself no longer defines that shape, because it never
reads Pi's own source at all.

THIS module closes that gap: it reads the actually-installed package's own
``package.json``, ``dist/modes/rpc/rpc-types.d.ts``,
``dist/modes/rpc/rpc-mode.js`` and ``dist/modes/rpc/jsonl.js`` and asserts,
from that text, that the exact seam facts LIVE1's dispatch classification
depends on (design Sec. 2.1-2.3) are still true.

What FU4B strengthened, and why
--------------------------------------------------------------------------

The pre-FU4B checks were bounded regexes over the WHOLE file. They were
useful, but several were mechanically weaker than their own docstrings
claimed: a ``case "prompt":`` arm anywhere in the file satisfied the
"handleCommand acknowledges prompt" check; a ``success(id, "prompt")``
satisfied the "correlated" check even if ``id`` were an unrelated local; a
``catch (parseError)`` anywhere satisfied the parse-failure check; and the
union-arm checks did not care which ``export type`` declaration the arm
belonged to. FU4B binds every check to the declaration or function that
actually carries the authority:

* the ``RpcCommand`` prompt-request arm is located INSIDE the real
  ``export type RpcCommand = ...;`` declaration;
* the ``RpcResponse`` prompt-success arm and the shared
  ``success: false`` / ``error: string`` failure arm are located INSIDE the
  real ``export type RpcResponse = ...;`` declaration;
* the ``case "prompt":`` arm is located INSIDE the real ``handleCommand``
  arrow function, never merely somewhere in ``rpc-mode.js``;
* the acknowledgement's id is proved to DERIVE from this command's own
  correlation source -- ``const <name> = <handleCommand's own parameter>.id;``
  -- and the acknowledgement is then required to pass THAT SAME NAME, so a
  coincidentally-named local ``id`` cannot satisfy it;
* the id-less ``"parse"`` refusal is located inside a ``catch`` block of the
  real ``handleInputLine`` arrow function;
* ``serializeJsonLine``'s ``JSON.stringify`` consequence (an ``undefined``
  id VANISHES from the wire rather than becoming ``null``) is preserved
  unchanged, because it is still true.

Every one of those bindings carries a mutation regression below that MOVES
the satisfying text out of the authoritative declaration/function while
leaving it in the file. Each such test additionally asserts that the naive
whole-file regex would still have been satisfied -- which is what makes the
binding demonstrably load-bearing rather than decorative.

Each check remains a bounded, targeted scan over the semantically relevant
fragment -- never a full-file hash, and never a claim about unrelated
formatting or whitespace.

If ANY of these assertions fails against the currently-installed package,
this module fails LOUDLY. It never falls back to a test-authored shape and
never skips.

Provenance, stated honestly
------------------------------

``_FROZEN_SEAM_PROVENANCE_VERSION`` records the Pi version this repository's
accepted design (``docs/PHASE_5F3B_LIVE1_PI_SEMANTIC_LIVE_LAYER_DESIGN.md``
Sec. 1.1) was reviewed against. Consistent with this project's standing
"version is provenance only, never an authorization gate" policy (see
``resolve_pi_identity``'s own docstring), THIS module's version check is
exactly that: a provenance/drift observation, never something any runtime
authorization path reads. A version mismatch does not mean the shape
drifted -- the shape checks above are independent and may still pass -- but
it does mean the accepted design's own provenance claim is now stale and
must be re-reviewed. That is reported, not hidden.

**That is precisely what happened.** This guard, at frozen provenance
``0.84.4``, correctly discovered an installed ``0.85.1``. Phase
``5F3B-LIVE1-DESIGN-FU4B`` then re-performed the complete Sec. 2.1-2.5
source analysis against the actual 0.85.1 package and found every required
LIVE1 fact mechanically preserved, so the declared reviewed provenance is
advanced here to ``0.85.1``. The superseded value is retained in
``_HISTORICAL_SEAM_PROVENANCE_VERSIONS`` so the advance is a recorded
re-review, not a silently edited expectation.

**FU4C completed the outer package's own identity, and decoupled the two
packages' version constants.** Before FU4C, the outer-package test proved
only ``version``, never ``name`` -- so a same-versioned but DIFFERENT npm
package at the resolved path would have silently passed. It now proves both,
via ``_OUTER_PACKAGE_NAME`` alongside the existing
``_FROZEN_SEAM_PROVENANCE_VERSION``. FU4C also gave the nested core its own
independent version constant, ``_NESTED_CORE_REVIEWED_VERSION`` (previously
the nested-core test reused ``_FROZEN_SEAM_PROVENANCE_VERSION`` -- the outer
package's own constant -- which was correct only because the two versions
happened to coincide, and would have been silently wrong the moment they
diverged). The two packages' reviewed versions currently both read
``0.85.1``, and their historical versions both read ``0.84.4`` -- each
established independently, from that package's own ``package.json``, never
derived from the other's constant. Nothing about this split changes what is
checked against the installed source; it only removes an implicit coupling
between two independently-versioned npm packages that happened to agree by
coincidence.
"""

from __future__ import annotations

import json
import os
import re

import pytest

from qualification.i2b_live_adapters import _ar2_resolve_pi_package_root

#: The reviewed OUTER package's own name. Provenance only -- exactly like the
#: version below, NEVER an authorization gate -- see the module docstring.
#: **5F3B-LIVE1-DESIGN-FU4C** added this: before FU4C the outer-package test
#: proved only a version match, which a same-versioned but different npm
#: package at the resolved path would also have satisfied.
_OUTER_PACKAGE_NAME = "@earendil-works/pi-coding-agent"

#: The Pi OUTER package version the accepted design's Sec. 2.1-2.5 seam
#: analysis was reviewed against. NEVER an authorization gate -- see the
#: module docstring. Advanced from ``0.84.4`` to ``0.85.1`` by
#: ``5F3B-LIVE1-DESIGN-FU4B``, and only AFTER the complete re-review.
_FROZEN_SEAM_PROVENANCE_VERSION = "0.85.1"

#: Outer package versions this repository's design was reviewed against
#: BEFORE the current one, oldest first. Kept so that advancing the
#: expectation is an auditable event rather than an invisible edit.
_HISTORICAL_SEAM_PROVENANCE_VERSIONS: tuple[str, ...] = ("0.84.4",)

#: The nested agent-core package carrying the ``agent_start`` / ``agent_end``
#: emission sites design Sec. 2.2 reasons about. FU4B re-reviewed it too, so
#: its own name is recorded here for the same provenance-only reason.
_NESTED_CORE_PACKAGE_NAME = "@earendil-works/pi-agent-core"
_NESTED_CORE_RELATIVE_PARTS = ("node_modules", "@earendil-works", "pi-agent-core")

#: The nested core package version design Sec. 2.2's completion-authority
#: analysis was reviewed against. **5F3B-LIVE1-DESIGN-FU4C**: this is a
#: DELIBERATELY INDEPENDENT constant from ``_FROZEN_SEAM_PROVENANCE_VERSION``
#: above -- the outer and nested-core packages are versioned separately, and
#: nothing requires them to move together even though they happen to read the
#: same value today. A future re-review may advance one without the other.
_NESTED_CORE_REVIEWED_VERSION = "0.85.1"

#: Nested-core versions this repository's design was reviewed against BEFORE
#: the current one, oldest first, established independently from the nested
#: core's OWN ``package.json`` (design Sec. 1.1) -- never derived from the
#: outer package's historical version.
_NESTED_CORE_HISTORICAL_VERSIONS: tuple[str, ...] = ("0.84.4",)


def _installed_package_root() -> str:
    """The SAME process-free resolver seam ``preflight_pi_installed_offline``
    and ``resolve_pi_identity`` already use. No subprocess."""
    return _ar2_resolve_pi_package_root()


def _read_installed_source(*relative_parts: str) -> str:
    root = _installed_package_root()
    path = os.path.join(root, *relative_parts)
    if not os.path.isfile(path):
        pytest.fail(
            f"installed Pi package is missing an expected seam source file: "
            f"{os.path.join(*relative_parts)}"
        )
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


# ===========================================================================
# Bounded structural extractors.
#
# These are deliberately simple brace-depth scans. This is emitted JS /
# ``.d.ts`` text, not something ``ast`` can parse, and a regex alone cannot
# safely bound nested braces. They read STRUCTURE, never whitespace
# conventions.
# ===========================================================================


def _brace_block_at(source: str, open_index: int) -> str | None:
    """The ``{ ... }`` block whose opening brace is at ``open_index``."""
    if open_index < 0 or open_index >= len(source) or source[open_index] != "{":
        return None
    depth = 0
    index = open_index
    while index < len(source):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[open_index : index + 1]
        index += 1
    return None


def _extract_type_alias_declaration(source: str, *, alias_name: str) -> str | None:
    """The complete text of ONE ``export type <alias_name> = ... ;``
    declaration, bounded by the first ``;`` at brace depth zero.

    This is what turns an arm assertion into a claim about THAT UNION rather
    than about the file. ``export type RpcCommandType = RpcCommand["type"];``
    is not matched by ``alias_name="RpcCommand"``, because the pattern
    requires the alias name to be followed directly by ``=``.
    """
    match = re.search(rf"export\s+type\s+{re.escape(alias_name)}\s*=", source)
    if match is None:
        return None
    index = match.end()
    depth = 0
    while index < len(source):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == ";" and depth == 0:
            return source[match.start() : index + 1]
        index += 1
    return None


def _top_level_union_arms(declaration: str) -> list[str]:
    """Every ``{ ... }`` object member at the top level of a union type-alias
    declaration, in source order.

    The scan always jumps over a complete block, so every ``{`` it reaches is
    by construction a top-level one.
    """
    arms: list[str] = []
    index = 0
    while index < len(declaration):
        if declaration[index] == "{":
            block = _brace_block_at(declaration, index)
            if block is None:
                break
            arms.append(block)
            index += len(block)
            continue
        index += 1
    return arms


def _extract_arrow_function_body(source: str, *, name: str) -> tuple[str, str] | None:
    """``(parameter_name, body_text)`` for ``const <name> = async (<p>) => { ... }``.

    Returning the parameter name is the point: the correlation proof below
    must bind the acknowledgement's id to THIS function's own command
    argument, not to any identifier that merely happens to be spelled ``id``.
    """
    match = re.search(
        rf"const\s+{re.escape(name)}\s*=\s*async\s*\(\s*(\w+)\s*\)\s*=>\s*\{{",
        source,
    )
    if match is None:
        return None
    body = _brace_block_at(source, match.end() - 1)
    if body is None:
        return None
    return match.group(1), body


def _extract_switch_case_block(source: str, *, case_label: str) -> str | None:
    """The text of ONE ``case "<case_label>": { ... }`` block within
    ``source`` -- which callers pass as an ALREADY-BOUND function body, never
    as a whole file."""
    marker = f'case "{case_label}":'
    start = source.find(marker)
    if start == -1:
        return None
    return _brace_block_at(source, source.find("{", start))


def _extract_default_arm_block(source: str) -> str | None:
    """The ``default: { ... }`` arm within an already-bound function body."""
    match = re.search(r"default:\s*\{", source)
    if match is None:
        return None
    return _brace_block_at(source, match.end() - 1)


def _catch_blocks(source: str) -> list[str]:
    """Every ``catch (<name>) { ... }`` block within ``source`` -- again, an
    already-bound function body rather than a whole file."""
    blocks: list[str] = []
    for match in re.finditer(r"catch\s*\(\s*\w+\s*\)\s*\{", source):
        block = _brace_block_at(source, match.end() - 1)
        if block is not None:
            blocks.append(block)
    return blocks


def _command_correlation_identifier(source: str, *, function_name: str) -> str | None:
    """The name of the local that a function binds to ITS OWN command
    argument's ``id`` -- i.e. the ``<name>`` in
    ``const <name> = <parameter>.id;``.

    ``None`` when the function does not exist, or does not derive an id from
    its own command at all. Every acknowledgement/refusal assertion below
    requires this name specifically, which is what makes them a correlation
    proof rather than a spelling coincidence.
    """
    extracted = _extract_arrow_function_body(source, name=function_name)
    if extracted is None:
        return None
    parameter, body = extracted
    match = re.search(rf"const\s+(\w+)\s*=\s*{re.escape(parameter)}\s*\.\s*id\s*;", body)
    if match is None:
        return None
    return match.group(1)


# ===========================================================================
# Structural assertion functions -- over TEXT, never a live process.
#
# Each takes source text and returns a bool. Written this way (rather than
# reading the file internally) so the SAME function can be run against the
# REAL installed source AND against a deliberately-mutated copy, in the
# adversarial self-tests below -- proving each check actually discriminates
# rather than being vacuously true.
# ===========================================================================

#: The prompt REQUEST arm's identifying field pair (design Sec. 2.1).
_PROMPT_REQUEST_ARM_PATTERN = r'type:\s*"prompt"\s*;\s*message:\s*string\s*;'

#: The correlated prompt SUCCESS response arm (design Sec. 2.1).
_PROMPT_SUCCESS_ARM_PATTERN = (
    r'id\?:\s*string\s*;\s*type:\s*"response"\s*;\s*command:\s*"prompt"\s*;'
    r"\s*success:\s*true\s*;"
)

#: The shared failure arm every non-``"prompt"``-specific refusal (including a
#: same-command-id ``"prompt"`` refusal) is drawn from (design Sec. 2.1/2.3).
_SHARED_FAILURE_ARM_PATTERN = (
    r'id\?:\s*string\s*;\s*type:\s*"response"\s*;\s*command:\s*string\s*;'
    r"\s*success:\s*false\s*;\s*error:\s*string\s*;"
)


def _rpc_command_has_prompt_arm_with_string_message(rpc_types_source: str) -> bool:
    """The ``RpcCommand`` DECLARATION still carries a union member
    ``type: "prompt"; message: string;`` (design Sec. 2.1).

    Bound to the declaration: a prompt-shaped arm sitting in some other
    exported type does not satisfy this.
    """
    declaration = _extract_type_alias_declaration(rpc_types_source, alias_name="RpcCommand")
    if declaration is None:
        return False
    return re.search(_PROMPT_REQUEST_ARM_PATTERN, declaration) is not None


def _rpc_command_prompt_arm_keeps_optional_fields_optional(rpc_types_source: str) -> bool:
    """Within the ``RpcCommand`` declaration's OWN prompt arm, ``id``,
    ``images`` and ``streamingBehavior`` are all still OPTIONAL (design
    Sec. 2.1: "omitted optional fields remain optional").

    This is what keeps AIDO's exact three-field ``{id, type, message}``
    command a complete, accepted command rather than a truncated one.
    """
    declaration = _extract_type_alias_declaration(rpc_types_source, alias_name="RpcCommand")
    if declaration is None:
        return False
    for arm in _top_level_union_arms(declaration):
        if re.search(_PROMPT_REQUEST_ARM_PATTERN, arm) is None:
            continue
        # The three fields AIDO does NOT send must each carry `?`. (`message`,
        # the one text-bearing field AIDO does send, is required by the
        # pattern above, which has no `?`.)
        if re.search(r"\bid\?:\s*string\s*;", arm) is None:
            return False
        if re.search(r"\bimages\?:", arm) is None:
            return False
        if re.search(r"\bstreamingBehavior\?:", arm) is None:
            return False
        return True
    return False


def _rpc_response_has_prompt_success_arm(rpc_types_source: str) -> bool:
    """The ``RpcResponse`` DECLARATION still carries the correlated prompt
    success arm ``{id?: string; type: "response"; command: "prompt";
    success: true;}``."""
    declaration = _extract_type_alias_declaration(rpc_types_source, alias_name="RpcResponse")
    if declaration is None:
        return False
    return re.search(_PROMPT_SUCCESS_ARM_PATTERN, declaration) is not None


def _rpc_response_has_shared_failure_arm(rpc_types_source: str) -> bool:
    """The ``RpcResponse`` DECLARATION still carries the shared failure arm
    ``{id?: string; type: "response"; command: string; success: false;
    error: string;}``, which LIVE1's ``PROMPT_RESPONSE_REFUSED``
    classification depends on."""
    declaration = _extract_type_alias_declaration(rpc_types_source, alias_name="RpcResponse")
    if declaration is None:
        return False
    return re.search(_SHARED_FAILURE_ARM_PATTERN, declaration) is not None


def _handle_command_prompt_case_acknowledges_by_correlation_id(rpc_mode_source: str) -> bool:
    """``handleCommand`` still has a ``case "prompt":`` arm whose
    acknowledgement is tied to THIS command's own correlation id.

    The proof is a three-link chain, and every link is bound:

    1. locate the real ``const handleCommand = async (<param>) => {...}``
       and capture ``<param>``;
    2. inside THAT body, find ``const <name> = <param>.id;`` -- the
       command's own correlation source -- and capture ``<name>``;
    3. inside THAT body's ``case "prompt":`` block, require
       ``output(success(<name>, "prompt"))``.

    Merely observing ``success(id, "prompt")`` is NOT accepted: without
    link 2 the ``id`` could be any local, and without link 1 the case could
    belong to an unrelated switch.
    """
    identifier = _command_correlation_identifier(rpc_mode_source, function_name="handleCommand")
    if identifier is None:
        return False
    extracted = _extract_arrow_function_body(rpc_mode_source, name="handleCommand")
    assert extracted is not None  # guaranteed by the identifier lookup above
    block = _extract_switch_case_block(extracted[1], case_label="prompt")
    if block is None:
        return False
    return (
        re.search(
            rf'output\(\s*success\(\s*{re.escape(identifier)}\s*,\s*"prompt"\s*\)\s*\)',
            block,
        )
        is not None
    )


def _handle_command_prompt_case_refuses_by_correlation_id(rpc_mode_source: str) -> bool:
    """The SAME ``case "prompt":`` arm's failure path is correlated too:
    ``output(error(<name>, "prompt", ...))``.

    Design Sec. 2.1 -- a ``success: false`` prompt response is a genuine
    refusal of THIS command, before an accepted agent run, which is what
    makes LIVE1's ``CONFIRMED_NOT_SENT`` / ``PROMPT_RESPONSE_REFUSED``
    truthful rather than a guess.
    """
    identifier = _command_correlation_identifier(rpc_mode_source, function_name="handleCommand")
    if identifier is None:
        return False
    extracted = _extract_arrow_function_body(rpc_mode_source, name="handleCommand")
    assert extracted is not None
    block = _extract_switch_case_block(extracted[1], case_label="prompt")
    if block is None:
        return False
    return (
        re.search(
            rf'output\(\s*error\(\s*{re.escape(identifier)}\s*,\s*"prompt"\s*,', block
        )
        is not None
    )


def _handle_input_line_parse_failure_is_id_less_and_named_parse(rpc_mode_source: str) -> bool:
    """``handleInputLine``'s OWN ``catch`` block still calls the shared
    ``error`` helper with an ID-LESS first argument (the literal
    ``undefined``) and the literal command identity ``"parse"`` -- the fact
    ``_unparseable_refusal_established``'s U4 check depends on.

    Bound to ``handleInputLine``: a ``catch (parseError)`` anywhere else in
    ``rpc-mode.js`` does not satisfy this.
    """
    extracted = _extract_arrow_function_body(rpc_mode_source, name="handleInputLine")
    if extracted is None:
        return False
    return any(
        re.search(r'error\(\s*undefined\s*,\s*"parse"\s*,', block) is not None
        for block in _catch_blocks(extracted[1])
    )


def _handle_input_line_command_failure_is_correlated(rpc_mode_source: str) -> bool:
    """``handleInputLine``'s OTHER ``catch`` block -- the post-parse
    command-failure arm -- still propagates the parsed command's own id
    (``error(<name>.id, <name>.type, ...)``).

    This is the second half of design Sec. 2.3's id-less INVENTORY: given
    AIDO's own three-field dispatch (which always carries ``id: "s1"``),
    every successfully-parsed command's response is correlated, so the
    parse-failure arm remains the only id-less ``type: "response"`` record
    that dispatch can provoke.
    """
    extracted = _extract_arrow_function_body(rpc_mode_source, name="handleInputLine")
    if extracted is None:
        return False
    return any(
        re.search(r"error\(\s*(\w+)\s*\.\s*id\s*,\s*\1\s*\.\s*type\s*,", block) is not None
        for block in _catch_blocks(extracted[1])
    )


def _handle_command_default_arm_is_correlated(rpc_mode_source: str) -> bool:
    """``handleCommand``'s ``default:`` unknown-command arm still returns
    ``error(<name>, <unknown>.type, ...)`` -- correlated, NOT id-less
    (design Sec. 2.3).

    A Pi that did not know ``"prompt"`` would therefore return a CORRELATED
    ``command: "prompt", success: false``, which LIVE1 classifies truthfully
    as ``PROMPT_RESPONSE_REFUSED`` rather than as an unparseable command.
    """
    identifier = _command_correlation_identifier(rpc_mode_source, function_name="handleCommand")
    if identifier is None:
        return False
    extracted = _extract_arrow_function_body(rpc_mode_source, name="handleCommand")
    assert extracted is not None
    block = _extract_default_arm_block(extracted[1])
    if block is None:
        return False
    return (
        re.search(rf"error\(\s*{re.escape(identifier)}\s*,\s*\w+\s*\.\s*type\s*,", block)
        is not None
    )


def _serialize_json_line_uses_json_stringify(jsonl_source: str) -> bool:
    """``serializeJsonLine`` still serializes through ``JSON.stringify`` --
    the ECMAScript behaviour that DROPS an ``undefined``-valued key (such as
    a parse failure's ``id``) rather than emitting ``null``.

    Preserved verbatim from the pre-FU4B guard: it was already bound to the
    function's own declaration and its first statement, and it is still true
    at the re-reviewed provenance.
    """
    return re.search(
        r"function\s+serializeJsonLine\s*\([^)]*\)\s*\{\s*return\s*`\$\{JSON\.stringify\(",
        jsonl_source,
    ) is not None


# ===========================================================================
# Mutation helper -- used ONLY by the adversarial self-tests.
# ===========================================================================


def _move_union_arm_out_of_declaration(
    source: str, *, alias_name: str, arm_pattern: str, stray_alias: str
) -> str:
    """Delete the matching field sequence from ``alias_name``'s OWN
    declaration and re-attach it to a NEW, unrelated exported type at the end
    of the file.

    The mutated text therefore still contains the arm -- a whole-file regex
    is still satisfied -- but the authoritative declaration no longer
    declares it. That is exactly the drift a declaration-bound check must
    catch and a file-wide one cannot.
    """
    declaration = _extract_type_alias_declaration(source, alias_name=alias_name)
    assert declaration is not None, f"{alias_name} declaration not found"
    match = re.search(arm_pattern, declaration)
    assert match is not None, f"{alias_name} does not contain the arm to move"
    stripped = declaration[: match.start()] + declaration[match.end() :]
    stray = f"\nexport type {stray_alias} = {{\n    {match.group(0)}\n}};\n"
    return source.replace(declaration, stripped, 1) + stray


# ===========================================================================
# Provenance-identity checkers -- pure functions over a PARSED package.json
# dict, never a live process. Split out from the test bodies (matching this
# module's own established pattern for the structural checks above) so the
# SAME function can be run against the REAL installed document and against a
# deliberately-mutated one in the adversarial regressions below -- proving
# each check discriminates on NAME as well as VERSION, never version alone.
# ===========================================================================


def _outer_package_identity_matches_reviewed_provenance(package_document: dict) -> bool:
    """True iff a parsed outer ``package.json`` carries BOTH the reviewed
    outer package's own name and its reviewed version.

    A version match alone is not an identity match: two differently-named npm
    packages could coincidentally share a version string. **5F3B-LIVE1-DESIGN-FU4C**
    added the name half of this check; before FU4C only the version was
    compared.
    """
    return (
        package_document.get("name") == _OUTER_PACKAGE_NAME
        and package_document.get("version") == _FROZEN_SEAM_PROVENANCE_VERSION
    )


def _nested_core_identity_matches_reviewed_provenance(package_document: dict) -> bool:
    """True iff a parsed nested-core ``package.json`` carries BOTH the
    reviewed nested-core package's own name and its OWN INDEPENDENTLY
    reviewed version (``_NESTED_CORE_REVIEWED_VERSION`` -- never the outer
    package's ``_FROZEN_SEAM_PROVENANCE_VERSION``, even though the two
    currently coincide)."""
    return (
        package_document.get("name") == _NESTED_CORE_PACKAGE_NAME
        and package_document.get("version") == _NESTED_CORE_REVIEWED_VERSION
    )


# ===========================================================================
# The drift guard itself -- against the REAL installed package.
# ===========================================================================


def test_case45_installed_pi_outer_package_name_and_version_match_reviewed_provenance():
    """package.json's own ``name`` AND ``version`` fields, read by plain file
    read (the SAME mechanism
    :func:`~qualification.i2b_live_adapters.preflight_pi_installed_offline`
    already uses), must still equal the reviewed outer package identity.

    A failure here is a genuine, actionable finding -- either the installed
    package is no longer ``@earendil-works/pi-coding-agent`` at all (a name
    mismatch -- **5F3B-LIVE1-DESIGN-FU4C** added this half), or it has moved
    past the version this design's own seam analysis (Sec. 2.1-2.5) was
    performed against (a version mismatch, unchanged since FU4B). It is
    reported here, not silently accepted: this test is DELIBERATELY not
    weakened to tolerate an unreviewed name or version, and the expected
    values are advanced ONLY by a completed re-review.
    """
    root = _installed_package_root()
    with open(os.path.join(root, "package.json"), "r", encoding="utf-8") as handle:
        package_document = json.load(handle)
    installed_name = package_document.get("name")
    installed_version = package_document.get("version")
    assert isinstance(installed_version, str) and installed_version.strip(), (
        "installed Pi package.json has no observable version field"
    )
    assert installed_name == _OUTER_PACKAGE_NAME, (
        f"installed outer package name {installed_name!r} no longer matches "
        f"the reviewed outer package name {_OUTER_PACKAGE_NAME!r} -- this is "
        "not the package LIVE1's Sec. 2.1-2.5 seam analysis was performed "
        "against, regardless of what its version field says"
    )
    assert installed_version == _FROZEN_SEAM_PROVENANCE_VERSION, (
        f"installed Pi package version {installed_version!r} no longer matches "
        f"the frozen seam provenance {_FROZEN_SEAM_PROVENANCE_VERSION!r} this "
        "design was reviewed against -- the Sec. 2.1-2.5 seam analysis must be "
        "re-run against the installed version before LIVE1 is trusted further"
    )
    assert _outer_package_identity_matches_reviewed_provenance(package_document), (
        "sanity: the combined name+version checker must agree with the "
        "individual assertions above"
    )
    assert _FROZEN_SEAM_PROVENANCE_VERSION not in _HISTORICAL_SEAM_PROVENANCE_VERSIONS, (
        "the current provenance must not also be recorded as superseded"
    )


def test_case45_installed_nested_agent_core_name_and_version_match_reviewed_provenance():
    """The nested ``@earendil-works/pi-agent-core`` package carries the
    ``agent_start`` / ``agent_end`` emission sites design Sec. 2.2 reasons
    about, so FU4B records its provenance too -- and FU4C makes that
    provenance independent of the outer package's own version constant.

    Provenance only -- exactly like the outer identity, read by exactly the
    same plain file read. Nothing in any runtime authorization path reads it.
    """
    root = _installed_package_root()
    path = os.path.join(root, *_NESTED_CORE_RELATIVE_PARTS, "package.json")
    if not os.path.isfile(path):
        pytest.fail(
            "installed Pi package no longer nests "
            f"{_NESTED_CORE_PACKAGE_NAME} at the reviewed location"
        )
    with open(path, "r", encoding="utf-8") as handle:
        package_document = json.load(handle)
    installed_name = package_document.get("name")
    installed_version = package_document.get("version")
    assert installed_name == _NESTED_CORE_PACKAGE_NAME, (
        f"installed nested-core package name {installed_name!r} no longer "
        f"matches the reviewed nested-core package name "
        f"{_NESTED_CORE_PACKAGE_NAME!r}"
    )
    assert installed_version == _NESTED_CORE_REVIEWED_VERSION, (
        f"nested {_NESTED_CORE_PACKAGE_NAME} version {installed_version!r} no "
        "longer matches the reviewed nested-core provenance "
        f"{_NESTED_CORE_REVIEWED_VERSION!r} -- the Sec. 2.2 completion-authority "
        "analysis must be re-run against it"
    )
    assert _nested_core_identity_matches_reviewed_provenance(package_document), (
        "sanity: the combined name+version checker must agree with the "
        "individual assertions above"
    )
    assert _NESTED_CORE_REVIEWED_VERSION not in _NESTED_CORE_HISTORICAL_VERSIONS, (
        "the current nested-core provenance must not also be recorded as "
        "superseded"
    )


# ===========================================================================
# Adversarial regression (FU4C): the provenance guard must discriminate on
# NAME, not merely on version -- a differently-named package that happens to
# share the reviewed version string must still fail.
# ===========================================================================


def test_case45_adversarial_outer_provenance_fails_on_right_version_wrong_name():
    """The exact scenario the FU4C prompt names: 'a package with the right
    version but wrong outer package name fails the provenance guard.'

    A version match alone is not identity -- two different npm packages could
    coincidentally share a version string. The guard must require BOTH name
    and version, and this proves it actually does.
    """
    right_version_wrong_name = {
        "name": "@earendil-works/some-other-package",
        "version": _FROZEN_SEAM_PROVENANCE_VERSION,
    }
    assert not _outer_package_identity_matches_reviewed_provenance(
        right_version_wrong_name
    )

    # Sanity: an otherwise-identical document with the RIGHT name passes --
    # proving the failure above is caused by the name, not by document shape.
    right_version_right_name = {
        "name": _OUTER_PACKAGE_NAME,
        "version": _FROZEN_SEAM_PROVENANCE_VERSION,
    }
    assert _outer_package_identity_matches_reviewed_provenance(
        right_version_right_name
    )


def test_case45_adversarial_nested_core_provenance_fails_on_right_version_wrong_name():
    """The same discrimination, proved independently for the nested-core
    checker -- it must not be satisfied merely by reusing the OUTER package's
    reviewed version on a wrongly-named document."""
    right_version_wrong_name = {
        "name": "@earendil-works/some-other-core",
        "version": _NESTED_CORE_REVIEWED_VERSION,
    }
    assert not _nested_core_identity_matches_reviewed_provenance(
        right_version_wrong_name
    )

    right_version_right_name = {
        "name": _NESTED_CORE_PACKAGE_NAME,
        "version": _NESTED_CORE_REVIEWED_VERSION,
    }
    assert _nested_core_identity_matches_reviewed_provenance(
        right_version_right_name
    )


def test_case45_installed_pi_source_still_defines_the_prompt_request_arm():
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    assert _rpc_command_has_prompt_arm_with_string_message(rpc_types_source), (
        "installed Pi's RpcCommand union no longer carries a "
        '`type: "prompt"; message: string;` arm -- LIVE1\'s dispatch command '
        "shape assumption has drifted"
    )
    assert _rpc_command_prompt_arm_keeps_optional_fields_optional(rpc_types_source), (
        "installed Pi's RpcCommand prompt arm no longer leaves id, images and "
        "streamingBehavior optional -- AIDO's exact three-field {id, type, "
        "message} dispatch command may no longer be a complete command"
    )


def test_case45_installed_pi_source_still_defines_the_prompt_response_arm():
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    assert _rpc_response_has_prompt_success_arm(rpc_types_source), (
        "installed Pi's RpcResponse union no longer carries the correlated "
        'command: "prompt" / success: true arm'
    )
    assert _rpc_response_has_shared_failure_arm(rpc_types_source), (
        "installed Pi's RpcResponse union no longer carries the shared "
        "success: false / error: string failure arm LIVE1's "
        "PROMPT_RESPONSE_REFUSED classification depends on"
    )


def test_case45_installed_pi_source_handle_command_still_acknowledges_prompt_by_id():
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")
    assert _handle_command_prompt_case_acknowledges_by_correlation_id(rpc_mode_source), (
        'installed Pi\'s handleCommand no longer has a case "prompt": arm whose '
        "acknowledgement is tied to the command's own correlation id"
    )
    assert _handle_command_prompt_case_refuses_by_correlation_id(rpc_mode_source), (
        'installed Pi\'s handleCommand case "prompt": arm no longer emits a '
        "correlated failure response for this command's own id"
    )


def test_case45_installed_pi_source_parse_failure_still_id_less_and_named_parse():
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")
    assert _handle_input_line_parse_failure_is_id_less_and_named_parse(rpc_mode_source), (
        "installed Pi's handleInputLine parse-failure path no longer calls "
        'error(undefined, "parse", ...) -- either the id has become '
        'correlated, or the command identity is no longer "parse"'
    )


def test_case45_installed_pi_source_other_refusal_arms_stay_correlated():
    """Design Sec. 2.3's id-less inventory, re-established mechanically: the
    two adjacent refusal arms both carry a correlation id, so -- for AIDO's
    own always-id-bearing dispatch -- the parse-failure arm remains the only
    id-less ``type: "response"`` record that dispatch can provoke."""
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")
    assert _handle_command_default_arm_is_correlated(rpc_mode_source), (
        "installed Pi's handleCommand default: arm no longer returns a "
        "correlated error for an unknown command type"
    )
    assert _handle_input_line_command_failure_is_correlated(rpc_mode_source), (
        "installed Pi's handleInputLine command-failure catch no longer "
        "propagates the parsed command's own id and type"
    )


def test_case45_installed_pi_source_jsonl_serialization_still_drops_undefined_id():
    jsonl_source = _read_installed_source("dist", "modes", "rpc", "jsonl.js")
    assert _serialize_json_line_uses_json_stringify(jsonl_source), (
        "installed Pi's serializeJsonLine no longer serializes through "
        "JSON.stringify -- the id-less parse-failure wire shape assumption "
        "(an undefined id vanishes rather than becoming null) may no longer hold"
    )


# ===========================================================================
# Adversarial self-tests, group 1: each structural assertion function must
# actually DISCRIMINATE against a deliberately mutated copy of the REAL
# installed text -- not merely happen to pass against unmodified text.
# ===========================================================================


def test_case45_adversarial_prompt_arm_check_fails_if_prompt_is_renamed():
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    assert _rpc_command_has_prompt_arm_with_string_message(rpc_types_source)  # sanity
    mutated = re.sub(
        _PROMPT_REQUEST_ARM_PATTERN,
        'type: "chat"; message: string;',
        rpc_types_source,
        count=1,
    )
    assert mutated != rpc_types_source, "the mutation did not actually change anything"
    assert not _rpc_command_has_prompt_arm_with_string_message(mutated)


def test_case45_adversarial_prompt_arm_check_fails_if_message_stops_being_a_string():
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    mutated = re.sub(
        _PROMPT_REQUEST_ARM_PATTERN,
        'type: "prompt"; message: unknown;',
        rpc_types_source,
        count=1,
    )
    assert mutated != rpc_types_source
    assert not _rpc_command_has_prompt_arm_with_string_message(mutated)


def test_case45_adversarial_prompt_arm_check_fails_if_message_becomes_optional():
    """``message`` is the task-text-bearing field (design Sec. 2.1). If it
    became optional, AIDO's three-field command would no longer be provably
    the text-bearing shape it was reviewed as."""
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    mutated = re.sub(
        _PROMPT_REQUEST_ARM_PATTERN,
        'type: "prompt"; message?: string;',
        rpc_types_source,
        count=1,
    )
    assert mutated != rpc_types_source
    assert not _rpc_command_has_prompt_arm_with_string_message(mutated)


def test_case45_adversarial_optional_field_check_fails_if_images_becomes_required():
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    assert _rpc_command_prompt_arm_keeps_optional_fields_optional(rpc_types_source)  # sanity
    mutated = rpc_types_source.replace(
        "images?: ImageContent[];", "images: ImageContent[];", 1
    )
    assert mutated != rpc_types_source
    assert not _rpc_command_prompt_arm_keeps_optional_fields_optional(mutated)


def test_case45_adversarial_prompt_success_arm_check_fails_if_success_becomes_false():
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    assert _rpc_response_has_prompt_success_arm(rpc_types_source)  # sanity
    mutated = re.sub(
        _PROMPT_SUCCESS_ARM_PATTERN,
        'id?: string; type: "response"; command: "prompt"; success: false;',
        rpc_types_source,
        count=1,
    )
    assert mutated != rpc_types_source
    assert not _rpc_response_has_prompt_success_arm(mutated)


def test_case45_adversarial_shared_failure_arm_check_fails_if_error_field_removed():
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    assert _rpc_response_has_shared_failure_arm(rpc_types_source)  # sanity
    mutated = re.sub(
        _SHARED_FAILURE_ARM_PATTERN,
        'id?: string; type: "response"; command: string; success: false;',
        rpc_types_source,
        count=1,
    )
    assert mutated != rpc_types_source
    assert not _rpc_response_has_shared_failure_arm(mutated)


def test_case45_adversarial_prompt_ack_check_fails_if_ack_stops_using_correlation_id():
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")
    assert _handle_command_prompt_case_acknowledges_by_correlation_id(rpc_mode_source)  # sanity
    mutated = rpc_mode_source.replace(
        'output(success(id, "prompt"));', 'output(success(undefined, "prompt"));', 1
    )
    assert mutated != rpc_mode_source
    assert not _handle_command_prompt_case_acknowledges_by_correlation_id(mutated)


def test_case45_adversarial_parse_failure_check_fails_if_id_becomes_correlated():
    """The exact adversarial scenario the FU2 prompt names: 'rpc-mode changes
    parse error from undefined id to correlated id.'"""
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")
    assert _handle_input_line_parse_failure_is_id_less_and_named_parse(rpc_mode_source)  # sanity
    mutated = rpc_mode_source.replace(
        'error(undefined, "parse",', 'error(command?.id, "parse",', 1
    )
    assert mutated != rpc_mode_source
    assert not _handle_input_line_parse_failure_is_id_less_and_named_parse(mutated)


def test_case45_adversarial_parse_failure_check_fails_if_command_identity_renamed():
    """The exact adversarial scenario the FU2 prompt names: 'rpc-mode changes
    the parse command identity.'"""
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")
    mutated = rpc_mode_source.replace(
        'error(undefined, "parse",', 'error(undefined, "parseFailure",', 1
    )
    assert mutated != rpc_mode_source
    assert not _handle_input_line_parse_failure_is_id_less_and_named_parse(mutated)


def test_case45_adversarial_jsonl_check_fails_if_stringify_is_replaced():
    jsonl_source = _read_installed_source("dist", "modes", "rpc", "jsonl.js")
    assert _serialize_json_line_uses_json_stringify(jsonl_source)  # sanity
    mutated = jsonl_source.replace("JSON.stringify(value)", "customSerialize(value)", 1)
    assert mutated != jsonl_source
    assert not _serialize_json_line_uses_json_stringify(mutated)


def test_case45_adversarial_prompt_arm_removed_entirely():
    """The exact adversarial scenario the FU2 prompt names: 'rpc-types
    removes/renames prompt.'"""
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    mutated = re.sub(
        _PROMPT_REQUEST_ARM_PATTERN,
        'type: "prompt_v2"; text: string;',
        rpc_types_source,
        count=1,
    )
    assert mutated != rpc_types_source
    assert not _rpc_command_has_prompt_arm_with_string_message(mutated)


# ===========================================================================
# Adversarial self-tests, group 2 (FU4B): each BINDING must be load-bearing.
#
# Every test here MOVES satisfying text out of the authoritative declaration
# or function while leaving it in the file, then asserts BOTH that the bound
# check now fails AND that a naive whole-file regex would still have passed.
# The second assertion is what proves the binding earns its keep.
# ===========================================================================


def test_case45_binding_a_stray_prompt_request_arm_outside_rpccommand_is_not_enough():
    """A ``type: "prompt"; message: string;`` arm parked in some other
    exported type must not satisfy the RpcCommand assertion."""
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    mutated = _move_union_arm_out_of_declaration(
        rpc_types_source,
        alias_name="RpcCommand",
        arm_pattern=_PROMPT_REQUEST_ARM_PATTERN,
        stray_alias="RpcStrayCommandArm",
    )
    # The naive, pre-FU4B whole-file check would still be satisfied ...
    assert re.search(_PROMPT_REQUEST_ARM_PATTERN, mutated) is not None
    # ... but the declaration-bound check correctly refuses.
    assert not _rpc_command_has_prompt_arm_with_string_message(mutated)


def test_case45_binding_a_stray_prompt_response_arm_outside_rpcresponse_is_not_enough():
    """The exact scenario the FU4B prompt names: 'prompt response arms placed
    outside RpcResponse must not satisfy the guard.'"""
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    mutated = _move_union_arm_out_of_declaration(
        rpc_types_source,
        alias_name="RpcResponse",
        arm_pattern=_PROMPT_SUCCESS_ARM_PATTERN,
        stray_alias="RpcStrayResponseArm",
    )
    assert re.search(_PROMPT_SUCCESS_ARM_PATTERN, mutated) is not None
    assert not _rpc_response_has_prompt_success_arm(mutated)


def test_case45_binding_a_stray_shared_failure_arm_outside_rpcresponse_is_not_enough():
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    mutated = _move_union_arm_out_of_declaration(
        rpc_types_source,
        alias_name="RpcResponse",
        arm_pattern=_SHARED_FAILURE_ARM_PATTERN,
        stray_alias="RpcStrayFailureArm",
    )
    assert re.search(_SHARED_FAILURE_ARM_PATTERN, mutated) is not None
    assert not _rpc_response_has_shared_failure_arm(mutated)


def test_case45_binding_a_fake_prompt_case_outside_handlecommand_is_not_enough():
    """The exact scenario the FU4B prompt names: 'a fake unrelated
    ``case "prompt"`` elsewhere must not satisfy the guard.'

    The real arm is renamed inside ``handleCommand``, and a decoy switch --
    complete with its own ``const id = command.id;`` -- is appended outside
    it. A file-wide scan sees a perfectly convincing acknowledgement; the
    function-bound scan sees that ``handleCommand`` no longer has one.
    """
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")
    assert _handle_command_prompt_case_acknowledges_by_correlation_id(rpc_mode_source)  # sanity
    renamed = rpc_mode_source.replace('case "prompt": {', 'case "prompt_v2": {', 1)
    assert renamed != rpc_mode_source
    decoy = (
        "\nconst handleSomethingElse = async (command) => {\n"
        "    const id = command.id;\n"
        "    switch (command.type) {\n"
        '        case "prompt": {\n'
        '            output(success(id, "prompt"));\n'
        "            return undefined;\n"
        "        }\n"
        "    }\n"
        "};\n"
    )
    mutated = renamed + decoy
    # The naive, pre-FU4B whole-file check would still be satisfied ...
    assert re.search(r'success\(\s*id\s*,\s*"prompt"\s*\)', mutated) is not None
    # ... but the handleCommand-bound check correctly refuses.
    assert not _handle_command_prompt_case_acknowledges_by_correlation_id(mutated)


def test_case45_binding_a_local_id_not_derived_from_the_command_is_not_correlation():
    """The exact scenario the FU4B prompt names: 'a local unrelated variable
    named ``id`` must not satisfy correlation proof.'

    ``const id = command.id;`` is replaced by a freshly minted uuid. The
    acknowledgement still reads ``success(id, "prompt")`` verbatim, so the
    pre-FU4B check passed it -- yet the emitted id would be uncorrelated to
    AIDO's ``"s1"``, silently breaking the entire dispatch classification.
    """
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")
    mutated = rpc_mode_source.replace(
        "const id = command.id;", "const id = crypto.randomUUID();", 1
    )
    assert mutated != rpc_mode_source
    # The naive, pre-FU4B whole-file check would still be satisfied ...
    assert re.search(r'success\(\s*id\s*,\s*"prompt"\s*\)', mutated) is not None
    # ... but the derivation-bound checks correctly refuse.
    assert not _handle_command_prompt_case_acknowledges_by_correlation_id(mutated)
    assert not _handle_command_prompt_case_refuses_by_correlation_id(mutated)
    assert not _handle_command_default_arm_is_correlated(mutated)


def test_case45_binding_a_parse_catch_outside_handleinputline_is_not_enough():
    """The exact scenario the FU4B prompt names: 'a ``catch (parseError)``
    outside ``handleInputLine`` must not satisfy the guard.'"""
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")
    assert _handle_input_line_parse_failure_is_id_less_and_named_parse(rpc_mode_source)  # sanity
    renamed = rpc_mode_source.replace(
        'error(undefined, "parse",', 'error(undefined, "parse_v2",', 1
    )
    assert renamed != rpc_mode_source
    decoy = (
        "\nconst handleSomethingElseEntirely = async (line) => {\n"
        "    try {\n"
        "        JSON.parse(line);\n"
        "    }\n"
        "    catch (parseError) {\n"
        '        output(error(undefined, "parse", "decoy"));\n'
        "    }\n"
        "};\n"
    )
    mutated = renamed + decoy
    # The naive, pre-FU4B whole-file check would still be satisfied ...
    assert re.search(r'error\(\s*undefined\s*,\s*"parse"\s*,', mutated) is not None
    # ... but the handleInputLine-bound check correctly refuses.
    assert not _handle_input_line_parse_failure_is_id_less_and_named_parse(mutated)


def test_case45_binding_extractors_reject_a_renamed_authority():
    """If the authoritative declaration or function is renamed outright, every
    bound check must fail closed rather than silently fall back to a
    file-wide scan."""
    rpc_types_source = _read_installed_source("dist", "modes", "rpc", "rpc-types.d.ts")
    rpc_mode_source = _read_installed_source("dist", "modes", "rpc", "rpc-mode.js")

    assert _extract_type_alias_declaration(rpc_types_source, alias_name="RpcCommand")
    assert _extract_type_alias_declaration(rpc_types_source, alias_name="RpcResponse")
    assert _extract_type_alias_declaration(rpc_types_source, alias_name="NoSuchAlias") is None

    # `RpcCommandType = RpcCommand["type"]` must not be mistaken for, or
    # swept into, the RpcCommand declaration itself.
    assert '= RpcCommand["type"]' in rpc_types_source
    command_declaration = _extract_type_alias_declaration(
        rpc_types_source, alias_name="RpcCommand"
    )
    assert command_declaration is not None
    assert '= RpcCommand["type"]' not in command_declaration
    # ... and RpcResponse's declaration must not swallow RpcExtensionUIResponse.
    response_declaration = _extract_type_alias_declaration(
        rpc_types_source, alias_name="RpcResponse"
    )
    assert response_declaration is not None
    assert "RpcExtensionUIResponse" not in response_declaration

    assert _extract_arrow_function_body(rpc_mode_source, name="handleCommand")
    assert _extract_arrow_function_body(rpc_mode_source, name="handleInputLine")
    assert _extract_arrow_function_body(rpc_mode_source, name="noSuchFunction") is None

    renamed_types = rpc_types_source.replace(
        "export type RpcCommand =", "export type RpcCommandV2 =", 1
    )
    assert not _rpc_command_has_prompt_arm_with_string_message(renamed_types)

    renamed_mode = rpc_mode_source.replace(
        "const handleCommand = async (command) =>", "const dispatch = async (command) =>", 1
    )
    assert not _handle_command_prompt_case_acknowledges_by_correlation_id(renamed_mode)

    renamed_input = rpc_mode_source.replace(
        "const handleInputLine = async (line) =>", "const onLine = async (line) =>", 1
    )
    assert not _handle_input_line_parse_failure_is_id_less_and_named_parse(renamed_input)
