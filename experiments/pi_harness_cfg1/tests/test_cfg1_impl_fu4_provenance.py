"""CFG1-IMPL-FU4 -- generated-config ISSUANCE PROVENANCE, not content equality.

The defect this file regresses, stated exactly. Every authority object L9 uses
was already unforgeable *individually*: a pin, an exclusive child and a
parentage proof each carry a registry-backed nonce, and
``register_config_issuance`` already refused a fabricated one. What was missing
was **origin**. ``win_config_authority``'s minting entry points are ordinary
module-level callables, so a caller holding a genuine ``Cfg1RunWorkspace``
could:

    derive the expected config location (no path parameter needed -- it is a
    pure function of the workspace) -> create the directory -> acquire a
    GENUINE root pin and a GENUINE config pin -> create the two GENUINE
    exclusive children -> obtain a GENUINE parentage proof -> write
    caller-selected bytes through the proven descriptors ->
    register_config_issuance(...) -> a GENUINE, ACTIVE issuance token

without ever calling ``write_cfg1_pi_config``. Every object presented was
real; the sequence was not L9. The token that came out was indistinguishable
from a legitimate one at every consumption boundary.

**The correction is a provenance stamp, not a content check.** Each pin, child
and proof records the
:class:`~pi_harness_cfg1.win_config_authority.GenerationInterval` that minted
it, an interval can be opened only from the bound generator's own CODE OBJECT,
and the issuance boundary refuses anything whose proof and children were not
minted inside ONE interval that is still open. So the rule these tests hold the
implementation to is:

    bytes are not provenance; names are not provenance; identities are not
    provenance; a genuine workspace is not provenance. Only having run is.

Pure Python, ``tmp_path``/``ar2``-root scoped, no live Pi/network/model/
credential activity.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import os
import shutil
import sys
from pathlib import Path

import pytest

from pi_harness_cfg1 import cfg1_pi_config, config_issuance, run_workspace
from pi_harness_cfg1 import win_config_authority as win
from pi_harness_cfg1.cfg1_pi_config import (
    CFG1_CONFIG_DIR_NAME,
    Cfg1PiConfigError,
    models_document,
    serialize_config_document,
    settings_document,
    write_cfg1_pi_config,
)
from pi_harness_cfg1.identity import CFG1_MODEL_ID, PROVIDER_ID

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "the provenance carrier is bound to Sec. 37.2's Win32 mint; a skip "
        "HERE on the target platform would hide exactly what FU4 closes"
    ),
)

SYNTHETIC_BASE_URL = "https://cfg1-fu4.invalid/v1"

#: Byte-for-byte what L9 itself would write for arm Q at this endpoint. Used to
#: prove that producing the RIGHT content by hand confers nothing.
LEGITIMATE_SETTINGS_TEXT = serialize_config_document(settings_document())
LEGITIMATE_MODELS_TEXT = serialize_config_document(
    models_document(arm_id="Q", base_url=SYNTHETIC_BASE_URL, model_id=CFG1_MODEL_ID)
)

#: Syntactically valid, caller-selected, and nothing to do with CFG1.
ALTERNATE_SETTINGS_TEXT = '{\n  "chosenByTheCaller": true\n}\n'
ALTERNATE_MODELS_TEXT = '{\n  "baseUrl": "https://caller.invalid/v1"\n}\n'

#: The genuine production callables, captured at import.
#:
#: Several rows below monkeypatch ``win.prove_config_parentage`` to borrow L9's
#: own in-flight authority objects. The ATTACKER must not be routed through
#: that scaffolding -- it calls the real functions, exactly as an unaided
#: caller would -- so the attack helper binds them here rather than resolving
#: them through the module attribute at call time.
_REAL_ACQUIRE_ROOT_PIN = win.acquire_root_pin
_REAL_ACQUIRE_CONFIG_PIN = win.acquire_config_pin
_REAL_CREATE_EXCLUSIVE_CHILD = win.create_exclusive_child
_REAL_PROVE_CONFIG_PARENTAGE = win.prove_config_parentage
_REAL_WRITE_CHILD_TEXT = win.write_child_text


@pytest.fixture()
def workspace(git_executable):
    """One genuine, freshly minted disposable run workspace, torn down hard."""
    handle, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    root = handle.experiment_root
    try:
        yield handle
    finally:
        run_workspace.discard_cfg1_run_workspace(handle)
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# The attack itself, expressed ONCE, through supported callables only
# ---------------------------------------------------------------------------


class CallerAssembledAuthority:
    """Everything a supported caller CAN still obtain, and nothing more.

    Deliberately built from public, module-level callables with no monkey-
    patching and no private-registry manipulation: if this class can be
    constructed, the Win32 half of the mechanism is genuinely reachable (which
    it must stay -- the FU15 suite depends on it). What FU4 proves is that
    everything in it is worthless at the issuance boundary.
    """

    def __init__(self, handle, *, config_dir: str):
        self.config_dir = config_dir
        self.root_pin = _REAL_ACQUIRE_ROOT_PIN(
            handle.experiment_root,
            expected_identity=win.directory_identity_of_path(handle.experiment_root),
        )
        self.config_pin = _REAL_ACQUIRE_CONFIG_PIN(config_dir)
        win.prove_child_directory_entry(
            self.root_pin,
            name=Path(config_dir).name,
            identity=win.pin_identity(self.config_pin),
        )
        self.settings_child = _REAL_CREATE_EXCLUSIVE_CHILD(
            config_dir=config_dir, name="settings.json"
        )
        self.models_child = _REAL_CREATE_EXCLUSIVE_CHILD(
            config_dir=config_dir, name="models.json"
        )
        self.proven = _REAL_PROVE_CONFIG_PARENTAGE(
            self.config_pin, children=(self.settings_child, self.models_child)
        )

    def write(self, settings_text: str, models_text: str) -> None:
        _REAL_WRITE_CHILD_TEXT(self.settings_child, settings_text)
        _REAL_WRITE_CHILD_TEXT(self.models_child, models_text)

    def attempt_issuance(self, handle, *, arm_id: str = "Q"):
        return config_issuance.register_config_issuance(
            workspace=handle,
            arm_id=arm_id,
            provider_id=PROVIDER_ID,
            model_id=CFG1_MODEL_ID,
            proven=self.proven,
            settings_child=self.settings_child,
            models_child=self.models_child,
        )

    def release(self) -> None:
        win.discard_parentage_proof(self.proven)
        win.close_child_quietly(self.settings_child)
        win.close_child_quietly(self.models_child)
        win.release_pin_quietly(self.config_pin)
        win.release_pin_quietly(self.root_pin)


def _expected_config_dir(handle) -> str:
    config_dir, _settings, _models = config_issuance.derive_cfg1_config_paths(handle)
    return config_dir


# ---------------------------------------------------------------------------
# FU4-1 -- the reviewer's bypass, run against the corrected code
# ---------------------------------------------------------------------------


def test_fu4_1_the_reviewer_bypass_reaches_the_boundary_and_is_refused_there(
    workspace,
):
    """The exact reported chain, with GENUINE production authority objects.

    Every step before the last one still SUCCEEDS, and that is deliberate: the
    refusal must come from the missing provenance, not from an unrelated
    failure earlier in the chain that would mask a future regression. So this
    asserts the pins, the children and the parentage proof were all really
    obtained, and only then that the issuance is refused -- with its own closed
    code, and with no token minted.
    """
    config_dir = _expected_config_dir(workspace)
    Path(config_dir).mkdir(parents=False, exist_ok=False)

    tokens_before = config_issuance.issued_token_count()
    assembled = CallerAssembledAuthority(workspace, config_dir=config_dir)
    try:
        # The chain really did get this far: these are genuine mint-backed
        # objects, not stand-ins.
        assert type(assembled.root_pin) is win.PinnedDirectory
        assert type(assembled.config_pin) is win.PinnedDirectory
        assert type(assembled.settings_child) is win.ExclusiveChild
        assert type(assembled.proven) is win.ProvenConfigChildren
        win.require_proven_children(
            assembled.proven, (assembled.settings_child, assembled.models_child)
        )

        assembled.write(LEGITIMATE_SETTINGS_TEXT, LEGITIMATE_MODELS_TEXT)

        with pytest.raises(config_issuance.ConfigIssuanceError) as excinfo:
            assembled.attempt_issuance(workspace)
        assert excinfo.value.reason_code == "ISSUANCE_PROVENANCE_NOT_PROVEN"
    finally:
        assembled.release()

    assert config_issuance.issued_token_count() == tokens_before
    assert win.held_interval_count() == 0


def test_fu4_1_the_underlying_provenance_predicate_names_the_missing_origin(
    workspace,
):
    """One layer down: the refusal is about ORIGIN, and says so.

    ``NOT_GENERATION_PROVENANCE`` rather than a child, name, identity or
    content code -- so a future change that started accepting caller-assembled
    authority could not be mistaken for a change in one of those other rules.
    """
    config_dir = _expected_config_dir(workspace)
    Path(config_dir).mkdir(parents=False, exist_ok=False)
    assembled = CallerAssembledAuthority(workspace, config_dir=config_dir)
    try:
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.require_production_issuance_provenance(
                assembled.proven, (assembled.settings_child, assembled.models_child)
            )
        assert excinfo.value.reason_code == "NOT_GENERATION_PROVENANCE"
    finally:
        assembled.release()


# ---------------------------------------------------------------------------
# FU4-2 -- exhaustive callable-surface closure
# ---------------------------------------------------------------------------


def _module_level_callables(module):
    """Every module-level callable, INCLUDING underscore-prefixed names.

    ``__all__`` is not consulted and a leading underscore is not a filter:
    FU16 invariant 8 says so explicitly, so the sweep must not honour either.
    Only names this module did not itself define are skipped, because an
    imported symbol is another module's surface, not this one's.
    """
    found = []
    for name, value in vars(module).items():
        if not callable(value):
            continue
        if getattr(value, "__module__", None) != module.__name__:
            continue
        found.append((name, value))
    return sorted(found)


def _argument_pool(handle, config_dir: str, assembled: CallerAssembledAuthority):
    """Ordinary values a supported caller genuinely has, keyed by parameter name.

    Each entry is a LIST of candidates, and the sweep calls each callable with
    every combination, so this is a real product over the caller's own
    vocabulary -- not one hand-picked invocation per function.
    """
    settings_path = str(Path(config_dir) / "settings.json")
    root_identity = win.directory_identity_of_path(handle.experiment_root)
    return {
        "path": [config_dir, settings_path, handle.experiment_root],
        "config_dir": [config_dir],
        "name": ["settings.json", CFG1_CONFIG_DIR_NAME],
        "expected_identity": [root_identity, win.pin_identity(assembled.config_pin)],
        "identity": [root_identity, win.pin_identity(assembled.config_pin)],
        "interval": [None],
        "pin": [assembled.root_pin, assembled.config_pin],
        "root_pin": [assembled.root_pin],
        "config_pin": [assembled.config_pin],
        "child": [assembled.settings_child, assembled.models_child],
        "settings_child": [assembled.settings_child],
        "models_child": [assembled.models_child],
        "children": [(assembled.settings_child, assembled.models_child)],
        "proven": [assembled.proven],
        "handle": [0, 1],
        "text": [LEGITIMATE_SETTINGS_TEXT, ALTERNATE_SETTINGS_TEXT],
        "workspace": [handle],
        "arm_id": ["Q", "R"],
        "provider_id": [PROVIDER_ID],
        "model_id": [CFG1_MODEL_ID],
        "base_url": [SYNTHETIC_BASE_URL],
        "token": ["", "0" * 32],
        "document": [settings_document()],
        "value": [LEGITIMATE_SETTINGS_TEXT],
    }


def _invocations(signature, pool):
    """Every argument combination this callable's own parameters admit."""
    combinations: list[dict] = [{}]
    for parameter in signature.parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        candidates = pool.get(parameter.name)
        if candidates is None:
            if parameter.default is parameter.empty:
                return []  # no supported value exists for this parameter at all
            continue
        combinations = [
            {**existing, parameter.name: candidate}
            for existing in combinations
            for candidate in candidates
        ]
    return combinations


def test_fu4_2_no_supported_callable_sequence_mints_a_generation_interval(workspace):
    """The sweep FU16 requirement B asks for, over the whole CFG1 surface.

    Every module-level callable of the issuance-relevant modules is invoked
    with every combination its own signature admits, drawn from a pool of
    values a caller holding a genuine workspace really has -- including genuine
    caller-assembled pins, children and a genuine parentage proof, rebuilt
    fresh for every callable so an earlier destructive call cannot make a later
    one vacuous. The claim proven is narrow and mechanical: nothing that comes
    back is a :class:`GenerationInterval`, nothing that comes back is a
    registered issuance token, and no interval is left open afterwards.
    """
    from pi_harness_cfg1 import environment as cfg1_environment

    modules = (cfg1_pi_config, win, config_issuance, cfg1_environment)
    swept: list[str] = []
    invoked: set[str] = set()
    returned_intervals: list[str] = []
    returned_tokens: list[str] = []

    for module in modules:
        for name, function in _module_level_callables(module):
            if not inspect.isfunction(function):
                continue
            config_dir = _expected_config_dir(workspace)
            shutil.rmtree(config_dir, ignore_errors=True)
            Path(config_dir).mkdir(parents=False, exist_ok=False)
            assembled = CallerAssembledAuthority(workspace, config_dir=config_dir)
            assembled.write(LEGITIMATE_SETTINGS_TEXT, LEGITIMATE_MODELS_TEXT)
            pins_before = set(win._PINS)
            children_before = set(win._CHILDREN)
            try:
                pool = _argument_pool(workspace, config_dir, assembled)
                calls = _invocations(inspect.signature(function), pool)
                swept.append(f"{module.__name__}.{name}")
                if calls:
                    invoked.add(f"{module.__name__}.{name}")
                for keywords in calls:
                    try:
                        result = function(**keywords)
                    except Exception:  # noqa: BLE001 - a refusal is the good case
                        continue
                    if type(result) is win.GenerationInterval:
                        returned_intervals.append(f"{module.__name__}.{name}")
                    if type(result) is str and result in config_issuance._ISSUED:
                        returned_tokens.append(f"{module.__name__}.{name}")
            finally:
                # A swept callable may legitimately mint a pin or a child of
                # its own; the sweep owns those and must not leave them held.
                # ``_register_pin`` accepts a raw handle, and the pool feeds it
                # the integers 0 and 1 -- closing THOSE would count a real
                # close failure the suite's hygiene fixture would rightly flag,
                # so a pin over a pool integer is retired without a close.
                for nonce in set(win._PINS) - pins_before:
                    if win._PINS[nonce][0] in (0, 1):
                        win._PINS.pop(nonce)
                        continue
                    win.release_pin_quietly(win.PinnedDirectory(nonce))
                for nonce in set(win._CHILDREN) - children_before:
                    win.close_child_quietly(win.ExclusiveChild(nonce))
                assembled.release()
                for token in list(config_issuance._ISSUED):
                    config_issuance.discard_config_issuance(token)

    # The sweep really covered the surface, rather than silently covering none.
    assert len(swept) >= 50, swept

    # Every callable that mints, stamps, or consumes authority was ACTUALLY
    # INVOKED, not merely enumerated. Without this the sweep could pass by
    # quietly skipping the only functions that matter.
    for critical in (
        "pi_harness_cfg1.win_config_authority.open_generation_interval",
        "pi_harness_cfg1.win_config_authority.bind_config_generator_authority",
        "pi_harness_cfg1.win_config_authority._register_pin",
        "pi_harness_cfg1.win_config_authority.acquire_root_pin",
        "pi_harness_cfg1.win_config_authority.acquire_config_pin",
        "pi_harness_cfg1.win_config_authority.create_exclusive_child",
        "pi_harness_cfg1.win_config_authority.prove_config_parentage",
        "pi_harness_cfg1.win_config_authority.require_production_issuance_provenance",
        "pi_harness_cfg1.config_issuance.register_config_issuance",
        "pi_harness_cfg1.config_issuance.verify_config_issuance",
        "pi_harness_cfg1.cfg1_pi_config.write_cfg1_pi_config",
    ):
        assert critical in invoked, critical

    # The remainder went uninvoked only because a caller has no supported value
    # for one of their REQUIRED parameters -- a Win32 access mask, an ambient
    # environment, a node executable, a credential. Pinned as a literal set so
    # a future signature change cannot quietly move a minting function into it.
    assert set(swept) - invoked == {
        "pi_harness_cfg1.win_config_authority._create_file",
        "pi_harness_cfg1.environment._narrowed_path",
        "pi_harness_cfg1.environment.audit_withheld_names",
        "pi_harness_cfg1.environment.build_cfg1_child_environment",
    }, sorted(set(swept) - invoked)

    assert returned_intervals == [], returned_intervals
    assert returned_tokens == [], returned_tokens
    assert win.held_interval_count() == 0


def test_fu4_2_opening_an_interval_is_gated_on_the_generator_code_object(workspace):
    """Not a name, not an underscore, not ``__all__`` -- the code object itself.

    The three things a caller can try are all refused for the same mechanical
    reason, and the generator's own code object being public knowledge does not
    help: what is checked is which code is EXECUTING, not which code is named.
    """
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.open_generation_interval()
    assert excinfo.value.reason_code == "NOT_THE_CONFIG_GENERATOR"

    # Calling it through an indirection does not change whose frame calls it.
    caller = win.open_generation_interval
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        caller()
    assert excinfo.value.reason_code == "NOT_THE_CONFIG_GENERATOR"

    # Nor does calling it from inside something that merely LOOKS like L9.
    def write_cfg1_pi_config():  # the same NAME, a different code object
        return win.open_generation_interval()

    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        write_cfg1_pi_config()
    assert excinfo.value.reason_code == "NOT_THE_CONFIG_GENERATOR"
    assert win.held_interval_count() == 0


def test_fu4_2_the_generator_binding_is_one_shot_and_self_derived():
    """Rebinding is refused, and the binding takes no argument to steer.

    A caller cannot nominate its own code object, cannot replace the bound one,
    and gains nothing by rebinding the generator module's ATTRIBUTE afterwards:
    what is bound is the code object captured at that module's import.
    """
    assert inspect.signature(win.bind_config_generator_authority).parameters == {}
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.bind_config_generator_authority()
    assert excinfo.value.reason_code == "GENERATOR_AUTHORITY_ALREADY_BOUND"
    assert win._GENERATOR_CODE is write_cfg1_pi_config.__code__


def test_fu4_2_a_generation_interval_cannot_be_constructed_or_guessed():
    """Direct construction of the authority-shaped object, and a guessed nonce."""
    for candidate in ("", "0" * 32, "not-a-nonce", None, 7):
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.GenerationInterval(candidate)
        assert excinfo.value.reason_code == "NOT_AN_OPEN_GENERATION_INTERVAL"

    # Subclassing inherits the registry, and therefore inherits the refusal:
    # the authority is the registry ENTRY, so a new class name adds nothing.
    for base, code in (
        (win.GenerationInterval, "NOT_AN_OPEN_GENERATION_INTERVAL"),
        (win.ProvenConfigChildren, "PARENTAGE_NOT_PROVEN"),
        (win.ExclusiveChild, "CHILD_NOT_HELD"),
        (win.PinnedDirectory, "PIN_NOT_HELD"),
    ):
        subclass = type("Forged", (base,), {"__slots__": ()})
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            subclass("0" * 32)
        assert excinfo.value.reason_code == code


def test_fu4_2_a_failed_generations_traceback_hands_back_only_retired_authority(
    workspace,
):
    """Reading ``exc.__traceback__`` is ordinary Python, so it is in scope.

    A caller that catches L9's refusal really CAN walk the traceback's frames
    and pull out the live-at-the-time :class:`GenerationInterval` and parentage
    proof -- there is no hiding a local from a traceback. What makes that
    harmless is ordering, not concealment: L9's ``finally`` retires both before
    the exception leaves the routine, so what the caller harvests is already
    inert. This row exists because a future change that retired the interval
    AFTER raising would silently reopen the bypass.
    """
    harvested: dict[str, object] = {}
    monkey = win.write_child_text

    def _boom(child, text):
        raise win.Cfg1DirectoryAuthorityError("CONFIG_FILES_NOT_WRITTEN")

    win.write_child_text = _boom
    try:
        with pytest.raises(Cfg1PiConfigError) as excinfo:
            write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    finally:
        win.write_child_text = monkey

    traceback = excinfo.value.__traceback__
    while traceback is not None:
        for value in traceback.tb_frame.f_locals.values():
            if type(value) is win.GenerationInterval:
                harvested["interval"] = value
            if type(value) is win.ProvenConfigChildren:
                harvested["proof"] = value
        traceback = traceback.tb_next

    # The premise: the harvest really did find them. A future refactor that
    # stopped exposing them would make this row vacuous rather than stronger,
    # so it is asserted rather than assumed.
    assert sorted(harvested) == ["interval", "proof"]

    assert win.held_interval_count() == 0
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.acquire_config_pin(
            workspace.experiment_root, interval=harvested["interval"]
        )
    assert excinfo.value.reason_code == "NOT_AN_OPEN_GENERATION_INTERVAL"
    with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
        win.require_production_issuance_provenance(harvested["proof"], ())
    assert excinfo.value.reason_code == "PARENTAGE_NOT_PROVEN"


def test_fu4_2_the_successful_generator_returns_no_authority_object_at_all(
    workspace,
):
    """L9's return value carries no pin, child, proof or interval to reuse."""
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        authority_types = (
            win.GenerationInterval,
            win.ProvenConfigChildren,
            win.PinnedDirectory,
            win.ExclusiveChild,
        )
        for slot in cfg1_pi_config.GeneratedCfg1Config.__slots__:
            assert type(getattr(generated, slot)) not in authority_types
        assert "interval" not in repr(generated)
    finally:
        config_issuance.discard_config_issuance(generated.issuance_token)


# ---------------------------------------------------------------------------
# FU4-3 / FU4-4 -- content is not provenance, whichever bytes are chosen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("settings_text", "models_text", "label"),
    [
        (LEGITIMATE_SETTINGS_TEXT, LEGITIMATE_MODELS_TEXT, "byte-identical"),
        (ALTERNATE_SETTINGS_TEXT, ALTERNATE_MODELS_TEXT, "caller-selected"),
    ],
)
@pytest.mark.parametrize("route", ["proven_descriptor", "pathname_write"])
def test_fu4_3_and_4_no_content_and_no_write_route_confers_issuance_provenance(
    workspace, settings_text, models_text, label, route
):
    """FU4-3 and FU4-4 together, over every production-authority write route.

    ``proven_descriptor`` is the strongest form of the attack: the bytes go in
    through descriptors that really did pass the real parentage gate, at the
    real derived path, under the real names. ``pathname_write`` is the naive
    form. Content equality is not origin, so both are refused -- the
    ``byte-identical`` case in particular must never be allowed to look "close
    enough".
    """
    config_dir = _expected_config_dir(workspace)
    Path(config_dir).mkdir(parents=False, exist_ok=False)
    tokens_before = config_issuance.issued_token_count()

    if route == "pathname_write":
        Path(config_dir, "settings.json").write_text(settings_text, encoding="utf-8")
        Path(config_dir, "models.json").write_text(models_text, encoding="utf-8")
        # The caller has files with exactly the right names and bytes, and a
        # genuine workspace -- and no proof object at all to present.
        with pytest.raises(config_issuance.ConfigIssuanceError) as excinfo:
            config_issuance.register_config_issuance(
                workspace=workspace,
                arm_id="Q",
                provider_id=PROVIDER_ID,
                model_id=CFG1_MODEL_ID,
                proven=object(),
                settings_child=object(),
                models_child=object(),
            )
        assert excinfo.value.reason_code == "PARENTAGE_NOT_PROVEN"
    else:
        assembled = CallerAssembledAuthority(workspace, config_dir=config_dir)
        try:
            assembled.write(settings_text, models_text)
            if label == "byte-identical":
                # Prove the premise: these really ARE the legitimate bytes.
                assert win.read_child_bytes(assembled.settings_child) == (
                    settings_text.replace("\n", os.linesep).encode("utf-8")
                )
            with pytest.raises(config_issuance.ConfigIssuanceError) as excinfo:
                assembled.attempt_issuance(workspace)
            assert excinfo.value.reason_code == "ISSUANCE_PROVENANCE_NOT_PROVEN"
        finally:
            assembled.release()

    assert config_issuance.issued_token_count() == tokens_before


# ---------------------------------------------------------------------------
# FU4-5 -- the production path still works, end to end
# ---------------------------------------------------------------------------


def test_fu4_5_the_genuine_generator_still_produces_one_consumable_issuance(
    workspace,
):
    """The positive control. Everything FU4 refuses elsewhere must still happen
    here, and the issuance must remain usable by both of its consumers.
    """
    tokens_before = config_issuance.issued_token_count()
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        assert config_issuance.issued_token_count() == tokens_before + 1
        # The interval was a local of L9 and did not outlive it.
        assert win.held_interval_count() == 0
        assert win.held_pin_count() == 0
        assert win.held_child_count() == 0

        record = config_issuance.verify_config_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        assert record.run_workspace_nonce == workspace.run_workspace_nonce
        assert (record.arm_id, record.provider_id, record.model_id) == (
            "Q",
            PROVIDER_ID,
            CFG1_MODEL_ID,
        )
        assert record.config_dir == _expected_config_dir(workspace)
        # Identities were established for the directory and both children.
        assert record.config_dir_identity != (-1, -1)
        assert record.settings_identity != (-1, -1)
        assert record.models_identity != (-1, -1)
        assert len({record.settings_identity, record.models_identity}) == 2
        # Digests are the FINALIZED on-disk bytes, read back through L9's own
        # descriptors -- so they agree with what a fresh read sees.
        assert (
            hashlib.sha256(Path(record.settings_path).read_bytes()).hexdigest()
            == record.settings_sha256
        )
        assert (
            hashlib.sha256(Path(record.models_path).read_bytes()).hexdigest()
            == record.models_sha256
        )

        # L12 still consumes it.
        from pi_harness_cfg1.environment import build_cfg1_child_environment

        built = build_cfg1_child_environment(
            ambient_environ={"SystemRoot": r"C:\Windows"},
            node_executable=r"C:\Program Files\nodejs\node.exe",
            generated_config=generated,
            workspace=workspace,
            credential_value="cfg1-synthetic-key",
        )
        assert built.pi_config_dir == record.config_dir

        # L24 still consumes it: the identity-bound scrub removes exactly the
        # endpoint-bearing file it issued, and nothing else.
        assert win.identity_bound_unlink(
            record.models_path, expected_identity=record.models_identity
        )
        assert not os.path.lexists(record.models_path)
        assert Path(record.settings_path).exists()
    finally:
        config_issuance.discard_config_issuance(generated.issuance_token)


# ---------------------------------------------------------------------------
# FU4-6 -- cross-generation and cross-interval object mixing
# ---------------------------------------------------------------------------


def _capture_live_generation(monkeypatch, sink: dict):
    """Capture L9's own live authority objects at the gate, and the interval.

    This is test-harness memory manipulation (Sec. 16.3.4), used deliberately:
    a supported caller cannot reach these at all, so the only way to prove the
    mixing rules hold for GENUINE in-interval objects is to borrow them from
    inside a real generation.
    """
    real_prove = win.prove_config_parentage

    def _prove(config_pin, *, children, **kwargs):
        proof = real_prove(config_pin, children=children, **kwargs)
        sink["interval"] = kwargs.get("interval")
        sink["config_pin"] = config_pin
        sink["children"] = children
        sink["proof"] = proof
        return proof

    monkeypatch.setattr(win, "prove_config_parentage", _prove)


def test_fu4_6_authority_from_one_interval_cannot_be_mixed_with_another(
    workspace, monkeypatch
):
    """Individually genuine objects from different origins never combine.

    Three mixes, all refused: a completed generation's proof with
    caller-assembled children; its retired interval used to stamp a caller's
    own pin; and that interval handed to the parentage gate.
    """
    live: dict[str, object] = {}
    _capture_live_generation(monkeypatch, live)

    foreign_dir = Path(workspace.experiment_root) / "caller_owned"
    foreign_dir.mkdir()
    assembled = CallerAssembledAuthority(workspace, config_dir=str(foreign_dir))
    try:
        assembled.write(LEGITIMATE_SETTINGS_TEXT, LEGITIMATE_MODELS_TEXT)

        generated = write_cfg1_pi_config(
            workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL
        )
        config_issuance.discard_config_issuance(generated.issuance_token)

        # (1) proof A + children B. L9 retires its proof on the way out, so the
        # combination is refused one step earlier still: the proof is not even
        # re-presentable, let alone pairable with another generation's children.
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.require_production_issuance_provenance(
                live["proof"], (assembled.settings_child, assembled.models_child)
            )
        assert excinfo.value.reason_code == "PARENTAGE_NOT_PROVEN"

        # (2) the retired interval object cannot stamp anything new.
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.acquire_config_pin(str(foreign_dir), interval=live["interval"])
        assert excinfo.value.reason_code == "NOT_AN_OPEN_GENERATION_INTERVAL"

        # (3) nor can it be handed to the gate.
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.prove_config_parentage(
                assembled.config_pin,
                children=(assembled.settings_child, assembled.models_child),
                interval=live["interval"],
            )
        assert excinfo.value.reason_code == "NOT_AN_OPEN_GENERATION_INTERVAL"
    finally:
        assembled.release()
    assert win.held_interval_count() == 0


def test_fu4_6_a_live_interval_refuses_to_absorb_caller_assembled_authority(
    workspace, monkeypatch
):
    """The mix attempted WHILE the production interval is genuinely open.

    The previous row's interval was already retired, which is a second reason
    it failed. This one runs the mixes from inside L9's own gate call, so the
    interval really is open and the ONLY thing wrong is that the caller's
    objects were not minted in it.
    """
    outcomes: dict[str, str] = {}
    foreign_dir = Path(workspace.experiment_root) / "caller_owned"
    foreign_dir.mkdir()

    real_prove = win.prove_config_parentage

    def _prove(config_pin, *, children, **kwargs):
        interval = kwargs.get("interval")
        assert type(interval) is win.GenerationInterval
        assert win.held_interval_count() == 1

        # A subclass instance over the OPEN interval's own nonce constructs --
        # the registry entry really is there -- and is still refused, because
        # every consumption gate asks for the exact type, not for something
        # that inherits from it.
        forged = type("Forged", (win.GenerationInterval,), {"__slots__": ()})(
            interval.nonce
        )
        try:
            win.acquire_config_pin(str(foreign_dir), interval=forged)
            outcomes["subclassed_interval"] = "PINNED (BAD)"
        except win.Cfg1DirectoryAuthorityError as exc:
            outcomes["subclassed_interval"] = exc.reason_code

        assembled = CallerAssembledAuthority(workspace, config_dir=str(foreign_dir))
        try:
            assembled.write(LEGITIMATE_SETTINGS_TEXT, LEGITIMATE_MODELS_TEXT)
            # A caller's pin cannot be folded into the open interval's proof.
            try:
                _REAL_PROVE_CONFIG_PARENTAGE(
                    assembled.config_pin,
                    children=(assembled.settings_child, assembled.models_child),
                    interval=interval,
                )
                outcomes["foreign_pin"] = "PROVED (BAD)"
            except win.Cfg1DirectoryAuthorityError as exc:
                outcomes["foreign_pin"] = exc.reason_code
            # Nor can a caller's children ride in on the production proof.
            proof = real_prove(config_pin, children=children, **kwargs)
            try:
                win.require_production_issuance_provenance(
                    proof, (assembled.settings_child, assembled.models_child)
                )
                outcomes["foreign_children"] = "ACCEPTED (BAD)"
            except win.Cfg1DirectoryAuthorityError as exc:
                outcomes["foreign_children"] = exc.reason_code
            # And a caller's children cannot be registered under it either.
            try:
                config_issuance.register_config_issuance(
                    workspace=workspace,
                    arm_id="Q",
                    provider_id=PROVIDER_ID,
                    model_id=CFG1_MODEL_ID,
                    proven=proof,
                    settings_child=assembled.settings_child,
                    models_child=assembled.models_child,
                )
                outcomes["registered"] = "REGISTERED (BAD)"
            except config_issuance.ConfigIssuanceError as exc:
                outcomes["registered"] = exc.reason_code
        finally:
            assembled.release()
        return proof

    monkeypatch.setattr(win, "prove_config_parentage", _prove)
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    config_issuance.discard_config_issuance(generated.issuance_token)

    assert outcomes == {
        "subclassed_interval": "NOT_AN_OPEN_GENERATION_INTERVAL",
        "foreign_pin": "GENERATION_PROVENANCE_MISMATCH",
        "foreign_children": "GENERATION_PROVENANCE_MISMATCH",
        "registered": "ISSUANCE_PROVENANCE_NOT_PROVEN",
    }


# ---------------------------------------------------------------------------
# FU4-7 -- post-validation mutation and rebinding
# ---------------------------------------------------------------------------


def test_fu4_7_mutating_or_rebinding_an_authority_object_adds_no_authority(
    workspace, monkeypatch
):
    """``object.__setattr__``, ``dataclasses.replace``, and a copied nonce.

    A nonce is the NAME of a registry fact, never the fact itself, so pairing a
    genuine one with substituted fields buys nothing -- and a production nonce
    copied out of a completed generation buys nothing either, because its
    interval is gone.
    """
    live: dict[str, object] = {}
    _capture_live_generation(monkeypatch, live)
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    record = None
    try:
        stolen_interval_nonce = live["interval"].nonce
        assert stolen_interval_nonce not in win._INTERVALS

        # A copied, genuine, but RETIRED interval nonce cannot be revived.
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.GenerationInterval(stolen_interval_nonce)
        assert excinfo.value.reason_code == "NOT_AN_OPEN_GENERATION_INTERVAL"

        # The mint-backed objects refuse ordinary mutation outright.
        for authority in (live["interval"], live["proof"], live["config_pin"]):
            with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
                authority.nonce = stolen_interval_nonce
            assert excinfo.value.reason_code == "AUTHORITY_IS_IMMUTABLE"
            with pytest.raises(win.Cfg1DirectoryAuthorityError):
                del authority.nonce

        # ``object.__setattr__`` reaches the slot, and still buys nothing: the
        # authority is the registry entry, and there is no entry to point at.
        config_dir = _expected_config_dir(workspace)
        forged = live["interval"]
        object.__setattr__(forged, "nonce", stolen_interval_nonce)
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.acquire_config_pin(config_dir, interval=forged)
        assert excinfo.value.reason_code == "NOT_AN_OPEN_GENERATION_INTERVAL"

        # The issuance record itself is frozen, and a replaced copy is not a
        # registry fact -- it cannot be presented anywhere.
        record = config_issuance.verify_config_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.arm_id = "R"  # type: ignore[misc]
        replaced = dataclasses.replace(record, arm_id="R")
        assert replaced not in config_issuance._ISSUED.values()

        # A genuine workspace paired with a guessed token is refused.
        with pytest.raises(config_issuance.ConfigIssuanceError) as excinfo:
            config_issuance.verify_config_issuance(token="0" * 32, workspace=workspace)
        assert excinfo.value.reason_code == "UNKNOWN_ISSUANCE_TOKEN"
    finally:
        config_issuance.discard_config_issuance(generated.issuance_token)
    assert record is not None


def test_fu4_7_a_completed_generation_cannot_be_issued_against_twice(
    workspace, monkeypatch
):
    """Repeated issuance, from objects retained past L9's own exit path.

    Even holding L9's real proof and real children, registration after the
    interval closed is refused -- so "register once more" is not a way to mint
    a second, differently-bound token for the same run.
    """
    live: dict[str, object] = {}
    _capture_live_generation(monkeypatch, live)
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        settings_child, models_child = live["children"]
        with pytest.raises(config_issuance.ConfigIssuanceError) as excinfo:
            config_issuance.register_config_issuance(
                workspace=workspace,
                arm_id="Q",
                provider_id=PROVIDER_ID,
                model_id=CFG1_MODEL_ID,
                proven=live["proof"],
                settings_child=settings_child,
                models_child=models_child,
            )
        assert excinfo.value.reason_code == "ISSUANCE_PROVENANCE_NOT_PROVEN"
        assert config_issuance.issued_token_count() == 1
    finally:
        config_issuance.discard_config_issuance(generated.issuance_token)


# ---------------------------------------------------------------------------
# FU4-8 -- partial failure leaves no reusable issuance authority
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "injection",
    [
        "before_parentage",
        "after_parentage_before_content",
        "between_the_two_content_writes",
        "after_both_writes_before_issuance",
        "during_provenance_establishment",
        "during_child_and_pin_release",
    ],
)
def test_fu4_8_no_partial_failure_leaves_reusable_issuance_authority(
    workspace, monkeypatch, injection
):
    """Every enumerated failure point, proven to strand nothing usable.

    **CFG1-IMPL-FU4-FU1.** What must be true after each one -- INCLUDING
    ``during_child_and_pin_release``, the one failure point that lands AFTER a
    genuine registration -- is now uniform: no issuance token exists, no
    generation interval is open, no pin is held, and the objects that DID
    exist during the attempt cannot be presented afterwards to mint or
    resurrect an issuance. A generation that registers an issuance and then
    fails during its own release cleanup must retire that registration ITSELF
    before the exception leaves L9; the assertion below holds because
    production code performed that retirement, not because this test reached
    into the registry to repair or conceal a record that was still live.
    T-152's frozen lifecycle state is unchanged: a refusal after the directory
    exists still leaves the residue INSIDE the owned root for L27, and CFG1
    still never removes it itself.
    """
    live: dict[str, object] = {}
    failure = win.Cfg1DirectoryAuthorityError
    real_prove = win.prove_config_parentage
    real_write = win.write_child_text

    if injection == "before_parentage":
        monkeypatch.setattr(
            win,
            "prove_config_parentage",
            lambda *a, **k: (_ for _ in ()).throw(
                failure("CONFIG_FILES_NOT_IN_PINNED_DIRECTORY")
            ),
        )
    elif injection == "after_parentage_before_content":

        def _prove(config_pin, *, children, **kwargs):
            live["proof"] = real_prove(config_pin, children=children, **kwargs)
            live["children"] = children
            live["interval"] = kwargs.get("interval")
            raise failure("CONFIG_FILES_NOT_WRITTEN")

        monkeypatch.setattr(win, "prove_config_parentage", _prove)
    elif injection == "between_the_two_content_writes":
        calls: list[int] = []

        def _write(child, text):
            calls.append(1)
            if len(calls) == 2:
                raise failure("CONFIG_FILES_NOT_WRITTEN")
            return real_write(child, text)

        monkeypatch.setattr(win, "write_child_text", _write)
    elif injection == "after_both_writes_before_issuance":
        monkeypatch.setattr(
            config_issuance,
            "register_config_issuance",
            lambda **k: (_ for _ in ()).throw(
                config_issuance.ConfigIssuanceError("INJECTED")
            ),
        )
    elif injection == "during_provenance_establishment":
        monkeypatch.setattr(
            win,
            "require_production_issuance_provenance",
            lambda *a, **k: (_ for _ in ()).throw(failure("INJECTED")),
        )
    else:

        def _prove_and_keep(config_pin, *, children, **kwargs):
            live["proof"] = real_prove(config_pin, children=children, **kwargs)
            live["children"] = children
            live["interval"] = kwargs.get("interval")
            return live["proof"]

        monkeypatch.setattr(win, "prove_config_parentage", _prove_and_keep)
        monkeypatch.setattr(win, "close_child_quietly", lambda child: False)

    tokens_before = config_issuance.issued_token_count()
    with pytest.raises(Cfg1PiConfigError):
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)

    # Uniform across every injection point, INCLUDING the one that lands after
    # a genuine registration: L9's own `finally` retires that registration
    # before raising (CFG1-IMPL-FU4-FU1), so there is nothing here for this
    # test to repair or hide. See the dedicated FU4-FU1 regressions below for
    # the release-failure-by-release-failure breakdown of this same property.
    assert config_issuance.issued_token_count() == tokens_before

    # Nothing held, nothing open.
    assert win.held_interval_count() == 0
    assert win.held_pin_count() == 0

    # T-152's frozen lifecycle state: whatever was created stayed INSIDE the
    # owned root, and L9 removed none of it.
    config_dir = Path(workspace.experiment_root) / CFG1_CONFIG_DIR_NAME
    if config_dir.exists():
        assert config_dir.parent == Path(workspace.experiment_root)

    # Anything the attempt did produce is inert afterwards.
    if "proof" in live:
        with pytest.raises(win.Cfg1DirectoryAuthorityError):
            win.require_production_issuance_provenance(live["proof"], live["children"])
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.acquire_config_pin(str(config_dir), interval=live["interval"])
        assert excinfo.value.reason_code == "NOT_AN_OPEN_GENERATION_INTERVAL"

    if injection == "during_child_and_pin_release":
        # The suite must not carry the deliberately un-closed descriptors into
        # a later test; close them with the real function.
        for child in live.get("children", ()):
            try:
                win.close_child(child)
            except win.Cfg1DirectoryAuthorityError:  # pragma: no cover
                pass
    assert win.held_child_count() == 0


# ---------------------------------------------------------------------------
# CFG1-IMPL-FU4-FU1 -- a post-registration release failure retires its own
# issuance, exactly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "which",
    ["child_release", "config_pin_release", "root_pin_release"],
)
def test_fu4_fu1_1_a_post_registration_release_failure_leaves_zero_active_issuance(
    workspace, monkeypatch, which
):
    """FU4-FU1-1. Each of step 11's three release calls, failing in isolation.

    Every injection here happens strictly AFTER a genuine registration: the
    generation itself is never disturbed, only ONE of its three release calls
    is made to report failure, and the other two run for real. What must be
    true afterward is ``issued_token_count() == tokens_before`` -- production
    code retired its own registration -- and this test does not create that
    invariant itself: it only reclaims the real OS handle/descriptor the
    injected failure left genuinely open, a housekeeping obligation distinct
    from (and performed strictly after) the registry assertion above it.
    """
    roles: dict[str, str] = {}
    real_root = win.acquire_root_pin
    real_config = win.acquire_config_pin
    real_release_pin = win.release_pin_quietly
    real_close_child = win.close_child_quietly
    stranded_pins: list[object] = []
    stranded_children: list[object] = []

    def _root(*args, **kwargs):
        pin = real_root(*args, **kwargs)
        roles[pin.nonce] = "root"
        return pin

    def _config(*args, **kwargs):
        pin = real_config(*args, **kwargs)
        roles[pin.nonce] = "config"
        return pin

    def _release_pin(pin):
        role = roles.get(pin.nonce)
        if (which == "config_pin_release" and role == "config") or (
            which == "root_pin_release" and role == "root"
        ):
            stranded_pins.append(pin)
            return False
        return real_release_pin(pin)

    def _close_child(child):
        if which == "child_release":
            stranded_children.append(child)
            return False
        return real_close_child(child)

    monkeypatch.setattr(win, "acquire_root_pin", _root)
    monkeypatch.setattr(win, "acquire_config_pin", _config)
    monkeypatch.setattr(win, "release_pin_quietly", _release_pin)
    monkeypatch.setattr(win, "close_child_quietly", _close_child)

    expected_code = {
        "child_release": "CONFIG_FILE_NOT_CLOSED",
        "config_pin_release": "CONFIG_DIR_PIN_NOT_RELEASED",
        "root_pin_release": "WORKSPACE_ROOT_PIN_NOT_RELEASED",
    }[which]

    tokens_before = config_issuance.issued_token_count()
    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == expected_code

    # The one property this test exists to prove -- and this test does not
    # repair it; production code already did.
    assert config_issuance.issued_token_count() == tokens_before

    # Reclaim whatever the injected failure genuinely left open, so the
    # hygiene fixture's held-pin/held-child assertions are this test's own
    # responsibility rather than a residue for a later test to trip over.
    for pin in stranded_pins:
        real_release_pin(pin)
    for child in stranded_children:
        real_close_child(child)


def test_fu4_fu1_2_a_traceback_harvested_provisional_token_is_unusable(
    workspace, monkeypatch
):
    """FU4-FU1-2. Reading ``exc.__traceback__`` is ordinary Python -- FU4-2
    already treats it as in scope -- so this proves the stronger property
    directly, rather than relying on the token being hard to find.

    Registration is instrumented so the test knows the EXACT provisional
    token L9 minted, before a post-registration release failure is injected.
    The local variable holding it is deliberately left alone (never reset to
    ``None``) so the harvest below is a genuine reflection of what L9's frame
    actually holds when it raises, matching the discipline the existing
    FU4-2 traceback regression already established for the interval and the
    parentage proof. Whether or not the walk actually finds it, presenting
    the exact provisionally-created token to ``verify_config_issuance`` after
    L9 has raised is refused as UNKNOWN -- because it was already retired by
    L9's own ``finally``, never because it happens to be inconvenient to
    locate.
    """
    real_register = config_issuance.register_config_issuance
    real_close_child = win.close_child_quietly
    captured: dict[str, object] = {}
    stranded_children: list[object] = []

    def _register(**kwargs):
        token = real_register(**kwargs)
        captured["token"] = token
        captured["children"] = (kwargs["settings_child"], kwargs["models_child"])
        return token

    def _fake_close(child):
        stranded_children.append(child)
        return False

    monkeypatch.setattr(config_issuance, "register_config_issuance", _register)
    monkeypatch.setattr(win, "close_child_quietly", _fake_close)

    tokens_before = config_issuance.issued_token_count()
    try:
        with pytest.raises(Cfg1PiConfigError) as excinfo:
            write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        assert excinfo.value.reason_code == "CONFIG_FILE_NOT_CLOSED"
        assert "token" in captured
        assert config_issuance.issued_token_count() == tokens_before

        harvested_from_traceback = None
        traceback = excinfo.value.__traceback__
        while traceback is not None:
            for value in traceback.tb_frame.f_locals.values():
                if value == captured["token"]:
                    harvested_from_traceback = value
            traceback = traceback.tb_next

        # The stronger property, proven regardless of the harvest's outcome:
        # the exact provisionally-created token grants no authority after L9
        # raised.
        with pytest.raises(config_issuance.ConfigIssuanceError) as verify_excinfo:
            config_issuance.verify_config_issuance(
                token=captured["token"], workspace=workspace
            )
        assert verify_excinfo.value.reason_code == "UNKNOWN_ISSUANCE_TOKEN"

        if harvested_from_traceback is not None:
            # It really was discoverable from a frame local -- so the refusal
            # above is proof of RETIREMENT, never proof of concealment.
            assert harvested_from_traceback == captured["token"]
    finally:
        for child in stranded_children:
            real_close_child(child)


def test_fu4_fu1_3_a_successful_generation_still_leaves_exactly_one_active_issuance(
    workspace,
):
    """FU4-FU1-3. Positive control: the correction fires only when L9 is about
    to raise, never on the ordinary success path. Proven directly here (a
    smaller, dedicated check), in addition to FU4-5's broader end-to-end
    coverage of the same success path.
    """
    tokens_before = config_issuance.issued_token_count()
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        assert config_issuance.issued_token_count() == tokens_before + 1
        record = config_issuance.verify_config_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        assert record.arm_id == "Q"

        from pi_harness_cfg1.environment import build_cfg1_child_environment

        built = build_cfg1_child_environment(
            ambient_environ={"SystemRoot": r"C:\Windows"},
            node_executable=r"C:\Program Files\nodejs\node.exe",
            generated_config=generated,
            workspace=workspace,
            credential_value="cfg1-synthetic-key",
        )
        assert built.pi_config_dir == record.config_dir
    finally:
        config_issuance.discard_config_issuance(generated.issuance_token)


def test_fu4_fu1_4_rollback_retires_exactly_the_failed_issuance(
    workspace, monkeypatch, git_executable
):
    """FU4-FU1-4. A second, unrelated, genuine issuance A survives a failed
    generation B's rollback untouched -- retirement is PER-TOKEN, never "clear
    the registry", which the design explicitly forbids as a rollback strategy.
    """
    handle_a, _built_a = run_workspace.mint_cfg1_run_workspace(
        git_executable=git_executable
    )
    try:
        generated_a = write_cfg1_pi_config(
            handle_a, arm_id="Q", base_url=SYNTHETIC_BASE_URL
        )
        tokens_before = config_issuance.issued_token_count()
        assert tokens_before >= 1

        real_close_child = win.close_child_quietly
        stranded_children: list[object] = []

        def _fake_close(child):
            stranded_children.append(child)
            return False

        monkeypatch.setattr(win, "close_child_quietly", _fake_close)
        try:
            with pytest.raises(Cfg1PiConfigError) as excinfo:
                write_cfg1_pi_config(
                    workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL
                )
            assert excinfo.value.reason_code == "CONFIG_FILE_NOT_CLOSED"

            # B's own registration is gone; A's is untouched and still usable.
            assert config_issuance.issued_token_count() == tokens_before
            record_a = config_issuance.verify_config_issuance(
                token=generated_a.issuance_token, workspace=handle_a
            )
            expected_dir, _settings, _models = config_issuance.derive_cfg1_config_paths(
                handle_a
            )
            assert record_a.config_dir == expected_dir
        finally:
            for child in stranded_children:
                real_close_child(child)
    finally:
        config_issuance.discard_config_issuance(generated_a.issuance_token)
        run_workspace.discard_cfg1_run_workspace(handle_a)
        shutil.rmtree(handle_a.experiment_root, ignore_errors=True)


def test_fu4_fu2_1_discard_config_issuance_is_the_exact_local_idempotent_retirement_primitive(
    workspace, git_executable, filesystem_spy
):
    """FU4-FU2. Pin the retirement primitive's actual boundary MECHANICALLY,
    from its real behavior and its real source -- never by monkeypatching it
    into a throwing stand-in and treating that mutation as a production
    fault, which was FU4-FU1-5's now-superseded premise. The frozen FU4
    threat model already excludes arbitrary interpreter/private-registry
    manipulation, and replacing the one function that owns ``_ISSUED.pop``
    with a throwing stand-in is exactly that class of manipulation, not a
    supported runtime failure L9 must defend against.

    Proves, from the real :func:`config_issuance.discard_config_issuance`,
    never a stand-in: it accepts the exact genuine token; it removes ONLY
    that token, never an unrelated one; repeated retirement is harmless; a
    guessed or malformed token mutates nothing; and its actual source is
    nothing but the type guard and the one dict pop its own docstring already
    promises -- so there is no filesystem, network, subprocess, model or
    handle call inside it that could ever fail in the first place. This
    suite's autouse ``_offline_only`` fixture already refuses any real socket
    for every test, so a hypothetical network call inside it would fail THIS
    test outright rather than merely go unasserted; ``filesystem_spy`` proves
    the filesystem half the same mechanical way.
    """
    # The exact, complete source: a type guard and one dict pop, nothing
    # else -- no import, no I/O call, no branch this test has not accounted
    # for. Whitespace-normalized so reformatting alone cannot break it, but
    # any ADDED statement, call, or dependency changes this string.
    source = inspect.getsource(config_issuance.discard_config_issuance)
    normalized = " ".join(source.split())
    assert normalized == (
        'def discard_config_issuance(token: str) -> None: '
        '"""Forget one issuance record. Idempotent, no I/O.""" '
        'if type(token) is not str: return _ISSUED.pop(token, None)'
    )

    generated_a = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    handle_b, _built_b = run_workspace.mint_cfg1_run_workspace(
        git_executable=git_executable
    )
    try:
        generated_b = write_cfg1_pi_config(
            handle_b, arm_id="Q", base_url=SYNTHETIC_BASE_URL
        )
        tokens_before = config_issuance.issued_token_count()
        assert tokens_before >= 2

        def _discard_touches_no_filesystem(token):
            before = (
                len(filesystem_spy.mkdir_calls),
                len(filesystem_spy.open_calls),
                len(filesystem_spy.lstat_calls),
                len(filesystem_spy.unlink_calls),
                len(filesystem_spy.rename_calls),
                len(filesystem_spy.truncate_calls),
            )
            config_issuance.discard_config_issuance(token)
            after = (
                len(filesystem_spy.mkdir_calls),
                len(filesystem_spy.open_calls),
                len(filesystem_spy.lstat_calls),
                len(filesystem_spy.unlink_calls),
                len(filesystem_spy.rename_calls),
                len(filesystem_spy.truncate_calls),
            )
            assert after == before, "discard_config_issuance touched the filesystem"

        # It accepts the exact genuine token, and removes ONLY it.
        _discard_touches_no_filesystem(generated_a.issuance_token)
        assert config_issuance.issued_token_count() == tokens_before - 1
        with pytest.raises(config_issuance.ConfigIssuanceError) as excinfo:
            config_issuance.verify_config_issuance(
                token=generated_a.issuance_token, workspace=workspace
            )
        assert excinfo.value.reason_code == "UNKNOWN_ISSUANCE_TOKEN"

        # B is untouched and still verifiable -- retirement is per-token, and
        # this test does not merely assume that, it checks a genuine second
        # record.
        record_b = config_issuance.verify_config_issuance(
            token=generated_b.issuance_token, workspace=handle_b
        )
        assert record_b.run_workspace_nonce == handle_b.run_workspace_nonce

        # Repeated retirement of the SAME already-gone token is harmless.
        _discard_touches_no_filesystem(generated_a.issuance_token)
        assert config_issuance.issued_token_count() == tokens_before - 1

        # A guessed token mutates nothing.
        _discard_touches_no_filesystem("0" * 32)
        assert config_issuance.issued_token_count() == tokens_before - 1

        # Malformed non-str input mutates nothing either -- refused by the
        # type guard before `_ISSUED.pop` is ever reached.
        for malformed in (None, 7, b"not-a-token", ["not", "a", "token"]):
            _discard_touches_no_filesystem(malformed)
            assert config_issuance.issued_token_count() == tokens_before - 1

        # B is still exactly as it was, after every one of the above.
        record_b_again = config_issuance.verify_config_issuance(
            token=generated_b.issuance_token, workspace=handle_b
        )
        assert record_b_again.settings_sha256 == record_b.settings_sha256
    finally:
        config_issuance.discard_config_issuance(generated_b.issuance_token)
        run_workspace.discard_cfg1_run_workspace(handle_b)
        shutil.rmtree(handle_b.experiment_root, ignore_errors=True)


# ---------------------------------------------------------------------------
# FU4-9 -- no raw authority diagnostics anywhere
# ---------------------------------------------------------------------------


def test_fu4_9_no_provenance_refusal_carries_a_path_handle_or_nonce(
    workspace, monkeypatch
):
    """Bounded closed codes only: no path, no handle, no nonce, no Win32 text."""
    live: dict[str, object] = {}
    _capture_live_generation(monkeypatch, live)
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    config_issuance.discard_config_issuance(generated.issuance_token)

    config_dir = _expected_config_dir(workspace)
    shutil.rmtree(config_dir, ignore_errors=True)
    Path(config_dir).mkdir()
    assembled = CallerAssembledAuthority(workspace, config_dir=config_dir)
    messages: list[str] = []
    try:
        assembled.write(LEGITIMATE_SETTINGS_TEXT, LEGITIMATE_MODELS_TEXT)
        for attempt in (
            lambda: assembled.attempt_issuance(workspace),
            lambda: win.require_production_issuance_provenance(
                assembled.proven, (assembled.settings_child, assembled.models_child)
            ),
            lambda: win.open_generation_interval(),
            lambda: win.acquire_config_pin(config_dir, interval=live["interval"]),
            lambda: win.GenerationInterval("0" * 32),
            lambda: win.bind_config_generator_authority(),
        ):
            try:
                attempt()
            except Exception as exc:  # noqa: BLE001 - the message is the subject
                messages.append(str(exc))
                messages.append(repr(exc))
    finally:
        assembled.release()

    assert len(messages) == 12
    forbidden = (
        workspace.experiment_root,
        workspace.workspace_root,
        config_dir,
        workspace.run_workspace_nonce,
        assembled.proven.nonce,
        assembled.settings_child.nonce,
        live["interval"].nonce,
        SYNTHETIC_BASE_URL,
        "cfg1-fu4.invalid",
    )
    for message in messages:
        for secret in forbidden:
            assert secret not in message, message
        assert "\\" not in message, message
        assert "0x" not in message, message

    # The authority objects themselves never render a handle or a nonce either.
    for authority in (assembled.proven, assembled.config_pin, live["interval"]):
        assert repr(authority) == f"{type(authority).__name__}(<bound>)"
        assert authority.nonce not in repr(authority)


# ---------------------------------------------------------------------------
# The frozen contract this correction did NOT widen
# ---------------------------------------------------------------------------


def test_fu4_the_issuance_boundary_still_asks_only_what_it_claims_to_ask(
    workspace,
):
    """An observation, recorded rather than silently "fixed".

    ``verify_config_issuance`` re-proves DIGESTS, not object identity, and it
    says so. The identity binding the record carries is L24's authority
    (Sec. 37.3.2a), exercised by :func:`identity_bound_unlink` -- so a
    byte-identical same-name replacement planted after issuance still verifies
    at L12's boundary and is still refused at L24's. That split is the frozen
    design's, and this row exists so a future change to either half is a
    deliberate decision rather than an accident.
    """
    generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    try:
        record = config_issuance.verify_config_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        original_bytes = Path(record.models_path).read_bytes()
        original_identity = record.models_identity

        # A byte-identical replacement: same name, same bytes, NEW object.
        os.unlink(record.models_path)
        Path(record.models_path).write_bytes(original_bytes)
        replacement = os.stat(record.models_path)
        assert (replacement.st_dev, replacement.st_ino) != original_identity

        # Digest-based re-verification still passes -- the documented contract.
        again = config_issuance.verify_config_issuance(
            token=generated.issuance_token, workspace=workspace
        )
        assert again.models_sha256 == record.models_sha256

        # L24's identity-bound authority refuses it, and deletes nothing.
        assert not win.identity_bound_unlink(
            record.models_path, expected_identity=original_identity
        )
        assert Path(record.models_path).exists()
    finally:
        config_issuance.discard_config_issuance(generated.issuance_token)
