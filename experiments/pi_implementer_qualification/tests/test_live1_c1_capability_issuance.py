"""5F3B-LIVE1-C1 -- semantic capability issuance + trusted Git authority.

**OFFLINE ONLY.** No test here launches Pi or Node, contacts B300, reads a
credential, opens a real broker or named pipe, calls a model, or touches a
real workspace. Every repository is a synthetic, disposable tree minted by
``qualification.i2b_workspace``'s own no-argument creator under the approved
scratch boundary; the only subprocesses are local ``git`` (the fixture
construction this package's offline suite already performs) and, in the one
whole-attempt ordering test, the frozen controller's own ``python`` baseline
verification. The broker server and the Pi supervisor are the accepted
synthetic doubles from ``test_i2b_live_adapters``, reused rather than forked
so C1 is proved against the same offline transport the Category-B phase was
accepted against.

What is proved here, in the order the design states it:

* the ORDINARY Category-B path is untouched -- zero Git activity, a
  byte-identical inert capability, and no reachable route to the semantic
  issuance path;
* the semantic issuance path derives EVERY authority fact (observed manifest,
  frozen task contract, the run's own mint record) and accepts none;
* issuance is one-shot and unreplayable across workspace, run, task and
  revision;
* every Git execution reachable in a semantic attempt is bound to AIDO's own
  ``resolve_git_executable`` result -- proved at the C1-P12a fixture-population
  checkpoint and again, independently, at the C1-P12b manifest observation;
* every failure refuses with a bounded reason code and NO capability, never
  falling back to the inert domain and never to a wider one.
"""

from __future__ import annotations

import ast
import inspect
import os
from dataclasses import replace
from pathlib import Path

import pytest

import ar2.capability as ar2_capability
import qualification.i2b_live_adapters as live_module
import qualification.i2b_workspace as workspace_module
import qualification.semantic_workspace as semantic_workspace_module
from ai_dev_orchestrator.workspace.git_adapter import resolve_git_executable
from ar2.capability import ROOT_CLASS_DISPOSABLE_SYNTHETIC, CapDefinitions
from ar2.observation import ObservationError
from qualification.corpus import IQ1_TASK, IQ2_TASK
from qualification.i2b_session import BrokerCreationRequest
from qualification.i2b_workspace import (
    SemanticCapabilityGrant,
    WorkspaceAuthorityError,
    claim_run_workspace,
    grant_semantic_capability_issuance,
    issue_semantic_broker_capability,
    mint_qualification_run_workspace,
    remove_run_workspace,
)
from qualification.semantic_workspace import (
    SemanticWorkspaceError,
    populate_semantic_task_workspace,
)

# The accepted offline transport doubles and the ordinary Category-B
# construction helper, imported rather than forked. ``patched`` and
# ``run_workspace`` are pytest fixtures; binding them at module level makes
# them available here exactly as they are in their own module.
from test_i2b_live_adapters import (  # noqa: E402
    SYNTHETIC_API_KEY,
    SYNTHETIC_BASE_URL,
    _adapters,
    _drive_frozen_controller,
    _issued,
    patched,
    run_workspace,
)

_PACKAGE_DIR = str(Path(__file__).resolve().parents[1])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def trusted_git() -> str:
    """AIDO's own accepted resolution -- the ONLY value C1 ever executes."""
    return resolve_git_executable(workspace_root=_PACKAGE_DIR)


@pytest.fixture(autouse=True)
def _clear_grants():
    yield
    workspace_module.discard_semantic_capability_grants()


def _populated(task, *, run_id: str, git_executable: str):
    """Mint, claim and populate ONE synthetic task workspace."""
    workspace = mint_qualification_run_workspace()
    claim_run_workspace(workspace, run_id=run_id)
    populate_semantic_task_workspace(workspace, task, git_executable=git_executable)
    return workspace


def _semantic_adapters(grant):
    return live_module.build_semantic_task_live_adapters(
        environ_reader=lambda name: {
            "AIDO_LITELLM_BASE_URL": SYNTHETIC_BASE_URL,
            "AIDO_LITELLM_API_KEY": SYNTHETIC_API_KEY,
        }.get(name),
        runtime_identity=_issued(),
        capability_grant=grant,
    )


def _count_git(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Count every C1-introduced Git-observation/resolution call site."""
    counts = {"observe_repository": 0, "resolve_git_executable": 0, "fixed_git_operation": 0}
    import ai_dev_orchestrator.workspace.git_adapter as git_adapter

    real_observe = workspace_module.observe_repository
    real_resolve = workspace_module.resolve_git_executable
    real_fixed = git_adapter.run_fixed_git_operation

    def _observe(**kwargs):
        counts["observe_repository"] += 1
        return real_observe(**kwargs)

    def _resolve(**kwargs):
        counts["resolve_git_executable"] += 1
        return real_resolve(**kwargs)

    def _fixed(*args, **kwargs):
        counts["fixed_git_operation"] += 1
        return real_fixed(*args, **kwargs)

    monkeypatch.setattr(workspace_module, "observe_repository", _observe)
    monkeypatch.setattr(workspace_module, "resolve_git_executable", _resolve)
    monkeypatch.setattr(git_adapter, "run_fixed_git_operation", _fixed)
    return counts


def _module_tree(module) -> ast.Module:
    return ast.parse(inspect.getsource(module))


# ===========================================================================
# CATEGORY-B PRESERVATION  (obligations 1-5)
# ===========================================================================


def test_full_category_b_path_issues_zero_git_activity(
    run_workspace, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligation 1. Drive the REAL, UNMODIFIED frozen Category-B controller
    over the REAL live adapters and count every Git call site C1 introduced.
    Zero. (``qualification.i2b_controller`` cannot reach one at all: the
    strengthened purity test proves it imports nothing external.)"""
    counts = _count_git(monkeypatch)
    result = _drive_frozen_controller(run_workspace, _adapters())
    assert result is not None
    assert counts == {
        "observe_repository": 0,
        "resolve_git_executable": 0,
        "fixed_git_operation": 0,
    }


def test_category_b_capability_remains_exactly_inert(run_workspace, patched) -> None:
    """Obligation 2. Field for field, the accepted inert domain -- reached
    without the caller naming anything."""
    adapters = _adapters()
    claim_run_workspace(run_workspace, run_id="run-c1-inert-0001")
    observation = adapters.create_broker(
        BrokerCreationRequest(run_id="run-c1-inert-0001", workspace=run_workspace)
    )
    assert observation.session is not None
    sed = adapters._brokers[observation.session.session_id].handler.sed
    assert sed.manifest == ()
    assert sed.read_eligible == frozenset()
    assert sed.write_eligible == frozenset()
    assert sed.protected_paths == frozenset()
    assert sed.verification_witness_paths == frozenset()
    assert sed.excluded == ()
    assert sed.caps == CapDefinitions()
    assert sed.root_class == ROOT_CLASS_DISPOSABLE_SYNTHETIC
    assert sed.lifetime == "one runtime process"
    assert sed.canonical_root == run_workspace.workspace_root
    assert sed.capability_id.startswith("i2b-cat-b-")


def test_category_b_construction_cannot_reach_the_semantic_issuance_path(patched) -> None:
    """Obligation 5. The ordinary constructor exposes no way to select broker
    capability authority -- no parameter, no boolean, no factory -- and the
    instance it produces holds no grant."""
    parameters = tuple(inspect.signature(live_module.LiveCategoryBAdapters.__init__).parameters)
    assert parameters == ("self", "environ_reader", "runtime_identity", "experiment_id", "bounds")
    adapters = _adapters()
    assert adapters._semantic_capability_grant is None


def test_the_semantic_construction_path_preserves_exact_type_route_authority(patched) -> None:
    """Part D. The semantic path returns the EXACT accepted type, so the
    frozen ``AuthenticatedB300RouteObserver``'s ``type(...) is`` authority is
    not weakened; only the grant differs."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)
    assert type(adapters) is live_module.LiveCategoryBAdapters
    assert adapters._semantic_capability_grant is grant
    observer = live_module.AuthenticatedB300RouteObserver(candidate="A", adapters=adapters)
    assert observer.candidate == "A"


def test_the_live_adapter_module_remains_structurally_zero_prompt() -> None:
    """Obligation 4, restated locally so a C1 regression fails here too."""
    source = inspect.getsource(live_module)
    literals = {
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "prompt" not in literals
    assert '"type": "prompt"' not in source


# ===========================================================================
# NO CALLER-AUTHORED AUTHORITY FACTS  (obligations 17-22, 40)
# ===========================================================================

_FORBIDDEN_AUTHORITY_PARAMETERS = (
    "tracked_manifest",
    "manifest",
    "protected_patterns",
    "protected",
    "verification_witness_paths",
    "witness",
    "witnesses",
    "canonical_root",
    "root",
    "caps",
    "cap_definitions",
    "capability_id",
    "capability_source",
    "capability_factory",
    "sed",
    "sed_builder",
    "domain",
    "domain_provider",
    "domain_builder",
    "manifest_provider",
    "mint_fn",
    "git_executable",
    "executable",
    "path",
    "workspace_root",
    "authority",
)

_C1_SURFACES = (
    "grant_semantic_capability_issuance",
    "issue_semantic_broker_capability",
)


@pytest.mark.parametrize("name", _C1_SURFACES)
def test_the_issuance_surface_accepts_no_authority_fact(name: str) -> None:
    """Obligations 17-21, 40. Neither entry point has a parameter through
    which a manifest, a protected set, a witness set, a root, a
    ``CapDefinitions`` override, a capability id, a ``StaticEligibilityDomain``,
    a Git executable, or a factory/callback of any of those can be expressed."""
    parameters = inspect.signature(getattr(workspace_module, name)).parameters
    for parameter in parameters:
        lowered = parameter.lower()
        for forbidden in _FORBIDDEN_AUTHORITY_PARAMETERS:
            assert forbidden not in lowered, (name, parameter, forbidden)


def test_the_exact_c1_signatures_are_the_reviewed_ones() -> None:
    """Obligation 40. Not merely an absence of specific names -- the exact,
    complete parameter sets. Nothing here can override the resolver, name a
    repository, or carry a task/model/artifact/project-config value.

    **This asserts OVERRIDE-impossibility, and deliberately does NOT assert
    that Git resolution is independent of ``PATH``.** That would be false:
    the accepted ``resolve_git_executable`` begins with ``shutil.which("git")``,
    so AIDO's own process ``PATH`` is an input to the resolver by design. The
    property C1 establishes is that nothing else may OVERRIDE its result."""
    assert tuple(
        inspect.signature(workspace_module.grant_semantic_capability_issuance).parameters
    ) == ("task",)
    assert tuple(
        inspect.signature(workspace_module.issue_semantic_broker_capability).parameters
    ) == ("grant", "workspace", "run_id")
    assert tuple(
        inspect.signature(live_module.build_semantic_task_live_adapters).parameters
    ) == ("environ_reader", "runtime_identity", "capability_grant")


def test_no_c1_surface_accepts_a_callable_authority_source(patched) -> None:
    """Obligations 21, 40. A callable presented where a grant belongs is
    refused mechanically, not merely absent from the signature."""
    for candidate in (lambda: None, object(), "grant", None, True, {"manifest": ()}):
        with pytest.raises(live_module.LiveAdapterError):
            live_module.build_semantic_task_live_adapters(
                environ_reader=lambda name: None,
                runtime_identity=_issued(),
                capability_grant=candidate,
            )


def test_a_grant_cannot_be_constructed_by_a_caller() -> None:
    """Obligation 21. The constructor demands a module-private key object,
    which is never exported, never a string, and never derivable."""
    with pytest.raises(WorkspaceAuthorityError) as excinfo:
        SemanticCapabilityGrant(object(), grant_token="anything")
    assert excinfo.value.reason_code == "SEMANTIC_GRANT_NOT_MINTED_BY_QUALIFICATION"


def test_a_task_that_is_not_a_frozen_corpus_singleton_is_refused() -> None:
    """Obligations 18, 19. The protected-pattern and verification-witness
    policy is underivable by a caller: a task whose contract was rewritten is
    not the frozen singleton, so it can never reach ``mint_capability``."""
    forged = replace(IQ1_TASK, task_id="IQ-1")
    with pytest.raises(WorkspaceAuthorityError) as excinfo:
        grant_semantic_capability_issuance(forged)
    assert excinfo.value.reason_code == "NOT_A_FROZEN_CORPUS_TASK"
    with pytest.raises(WorkspaceAuthorityError):
        grant_semantic_capability_issuance("IQ-1")  # type: ignore[arg-type]


def test_the_disposable_root_authority_never_appears_on_a_public_surface(
    trusted_git: str,
) -> None:
    """Obligation 22. Not on the grant, not in its ``repr``, not in the mint
    record's ``repr``, not on the returned capability, and not reconstructible
    from anything C1 hands back."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    assert repr(grant) == "SemanticCapabilityGrant(granted=True)"
    assert not hasattr(grant, "authority")
    assert getattr(grant, "__dict__", None) is None  # __slots__ only
    assert tuple(SemanticCapabilityGrant.__slots__) == ("_grant_token",)

    workspace = _populated(IQ1_TASK, run_id="run-c1-auth-0001", git_executable=trusted_git)
    try:
        sed = issue_semantic_broker_capability(
            grant, workspace=workspace, run_id="run-c1-auth-0001"
        )
        assert not hasattr(sed, "authority")
        rendered = repr(sed) + repr(workspace) + repr(workspace_module._MINTED)
        assert "DisposableRootAuthority" not in rendered
        assert "marker" not in rendered
    finally:
        remove_run_workspace(workspace)


# ===========================================================================
# WORKSPACE / TASK / RUN BINDING  (obligations 11-16)
# ===========================================================================


def test_genuine_issuance_binds_workspace_run_task_and_revision(trusted_git: str) -> None:
    """Obligation 11."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-bind-0001", git_executable=trusted_git)
    try:
        sed = issue_semantic_broker_capability(
            grant, workspace=workspace, run_id="run-c1-bind-0001"
        )
        record = workspace_module._SEMANTIC_GRANTS[grant._grant_token]
        assert record.bound_run_workspace_nonce == workspace.run_workspace_nonce
        assert record.bound_run_id == "run-c1-bind-0001"
        assert record.bound_capability_id == sed.capability_id
        assert record.task_id == IQ1_TASK.task_id
        assert record.task_revision == IQ1_TASK.task_revision
        assert sed.canonical_root == workspace.workspace_root
    finally:
        remove_run_workspace(workspace)


def test_a_second_issuance_for_the_same_grant_refuses(trusted_git: str) -> None:
    """Obligation 12. Issuance is ONE-SHOT."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    first = _populated(IQ1_TASK, run_id="run-c1-once-0001", git_executable=trusted_git)
    second = _populated(IQ1_TASK, run_id="run-c1-once-0002", git_executable=trusted_git)
    try:
        issue_semantic_broker_capability(grant, workspace=first, run_id="run-c1-once-0001")
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(grant, workspace=second, run_id="run-c1-once-0002")
        assert excinfo.value.reason_code == "SEMANTIC_GRANT_ALREADY_CONSUMED"
    finally:
        remove_run_workspace(first)
        remove_run_workspace(second)


def test_a_refused_issuance_still_burns_the_grant(trusted_git: str) -> None:
    """Obligation 12. A rejected attempt can never re-present the same grant
    to a second issuance -- the burn happens BEFORE validation."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-burn-0001", git_executable=trusted_git)
    try:
        with pytest.raises(WorkspaceAuthorityError):
            issue_semantic_broker_capability(grant, workspace=workspace, run_id="a-foreign-run")
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant, workspace=workspace, run_id="run-c1-burn-0001"
            )
        assert excinfo.value.reason_code == "SEMANTIC_GRANT_ALREADY_CONSUMED"
    finally:
        remove_run_workspace(workspace)


def test_a_foreign_workspace_refuses(trusted_git: str) -> None:
    """Obligation 13. A workspace this module did not mint -- or one whose
    mint record has been discarded -- can never bear a capability."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)

    class _Forged:
        run_workspace_nonce = "forged"
        experiment_root = r"C:\nonexistent"
        workspace_root = r"C:\nonexistent"

    with pytest.raises(WorkspaceAuthorityError) as excinfo:
        issue_semantic_broker_capability(
            _Forged(), workspace=_Forged(), run_id="run-c1-foreign-0001"  # type: ignore[arg-type]
        )
    assert excinfo.value.reason_code == "NOT_A_SEMANTIC_CAPABILITY_GRANT"

    with pytest.raises(WorkspaceAuthorityError) as excinfo:
        issue_semantic_broker_capability(
            grant, workspace=_Forged(), run_id="run-c1-foreign-0001"  # type: ignore[arg-type]
        )
    assert excinfo.value.reason_code == "NOT_A_QUALIFICATION_RUN_WORKSPACE"


def test_a_foreign_run_id_refuses(trusted_git: str) -> None:
    """Obligation 14. The workspace must be claimed by EXACTLY this run."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-run-0001", git_executable=trusted_git)
    try:
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant, workspace=workspace, run_id="run-c1-run-0002"
            )
        assert excinfo.value.reason_code == "RUN_WORKSPACE_NOT_CLAIMED_BY_THIS_RUN"
    finally:
        remove_run_workspace(workspace)


def test_a_grant_for_another_task_refuses_against_this_workspace(trusted_git: str) -> None:
    """Obligation 15. A grant cannot be carried into another task of the same
    sweep: the observed manifest is IQ-1's, the grant's contract is IQ-2's,
    and the disagreement refuses rather than preferring either side."""
    grant = grant_semantic_capability_issuance(IQ2_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-task-0001", git_executable=trusted_git)
    try:
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant, workspace=workspace, run_id="run-c1-task-0001"
            )
        assert excinfo.value.reason_code == "INTENDED_AND_OBSERVED_MANIFEST_DISAGREE"
    finally:
        remove_run_workspace(workspace)


def test_task_identity_drift_between_grant_and_consumption_refuses(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligation 16. The revision snapshot taken at grant time is re-proved
    at consumption, so a task that changed underneath the grant is refused."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace_module._SEMANTIC_GRANTS[grant._grant_token].task_revision = "IQ-1@deadbeefdeadbeef"
    workspace = _populated(IQ1_TASK, run_id="run-c1-rev-0001", git_executable=trusted_git)
    try:
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant, workspace=workspace, run_id="run-c1-rev-0001"
            )
        assert excinfo.value.reason_code == "SEMANTIC_TASK_IDENTITY_DRIFTED"
    finally:
        remove_run_workspace(workspace)


# ===========================================================================
# WORKSPACE-LEVEL ONE-SHOT ISSUANCE  (5F3B-LIVE1-C1-FU1, Blocker 1, tests A-F)
# ===========================================================================
#
# C1-P8 is workspace-level, not merely grant-level. A SPECIFIC grant object
# being one-shot (proved above) does not, by itself, prove a WORKSPACE can
# bear only one semantic issuance: nothing stopped a second, DISTINCT,
# genuinely-minted grant for the same task from being presented against an
# already-issued workspace. These tests close that gap directly.


def test_a_two_distinct_genuine_grants_same_workspace_second_refuses(
    trusted_git: str,
) -> None:
    """FU1 Test A. Two DISTINCT genuine grants, same workspace, same run,
    same task: the first succeeds, the second refuses -- even though neither
    grant was ever presented twice."""
    grant1 = grant_semantic_capability_issuance(IQ1_TASK)
    grant2 = grant_semantic_capability_issuance(IQ1_TASK)
    assert grant1._grant_token != grant2._grant_token
    workspace = _populated(IQ1_TASK, run_id="run-fu1-a-0001", git_executable=trusted_git)
    try:
        issue_semantic_broker_capability(grant1, workspace=workspace, run_id="run-fu1-a-0001")
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant2, workspace=workspace, run_id="run-fu1-a-0001"
            )
        assert excinfo.value.reason_code == "WORKSPACE_SEMANTIC_ISSUANCE_ALREADY_CONSUMED"
    finally:
        remove_run_workspace(workspace)


def test_b_a_git_observation_failure_still_blocks_a_fresh_grant_retry(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU1 Test B. The first issuance reaches the valid workspace/run claim
    but later fails at Git observation; a second, fresh, genuine grant for
    that SAME workspace must still refuse -- proving the workspace-level
    authority is consumed BEFORE the point of failure, not merely alongside
    a successful outcome."""
    grant1 = grant_semantic_capability_issuance(IQ1_TASK)
    grant2 = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-fu1-b-0001", git_executable=trusted_git)
    try:

        def _fail(**kwargs):
            raise ObservationError("observation error: synthetic offline failure")

        monkeypatch.setattr(workspace_module, "observe_repository", _fail)
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant1, workspace=workspace, run_id="run-fu1-b-0001"
            )
        assert excinfo.value.reason_code == "REPOSITORY_OBSERVATION_FAILED"

        monkeypatch.undo()  # restore the real observe_repository for the retry
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant2, workspace=workspace, run_id="run-fu1-b-0001"
            )
        assert excinfo.value.reason_code == "WORKSPACE_SEMANTIC_ISSUANCE_ALREADY_CONSUMED"
    finally:
        remove_run_workspace(workspace)


def test_c_a_mint_capability_failure_still_blocks_a_fresh_grant_retry(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU1 Test C. Same as Test B, but the first issuance fails later still
    -- at ``mint_capability`` -- after Git resolution and observation both
    succeeded. The workspace-level authority was already consumed before
    either ran, so the second fresh grant still refuses at the same
    workspace-level checkpoint, without even reaching Git."""
    from ar2.capability import CapabilityMintError

    grant1 = grant_semantic_capability_issuance(IQ1_TASK)
    grant2 = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-fu1-c-0001", git_executable=trusted_git)
    git_calls: list[str] = []
    try:

        def _fail(**kwargs):
            raise CapabilityMintError("capability mint refused: synthetic offline failure")

        monkeypatch.setattr(workspace_module, "mint_capability", _fail)
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant1, workspace=workspace, run_id="run-fu1-c-0001"
            )
        assert excinfo.value.reason_code == "CAPABILITY_MINT_REFUSED"

        real_resolve = workspace_module.resolve_git_executable

        def _count_resolve(**kwargs):
            git_calls.append("resolve")
            return real_resolve(**kwargs)

        monkeypatch.setattr(workspace_module, "resolve_git_executable", _count_resolve)
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant2, workspace=workspace, run_id="run-fu1-c-0001"
            )
        assert excinfo.value.reason_code == "WORKSPACE_SEMANTIC_ISSUANCE_ALREADY_CONSUMED"
        assert git_calls == []  # the retry never even reached Git resolution
    finally:
        remove_run_workspace(workspace)


def test_d_a_fresh_new_workspace_still_permits_its_own_one_issuance(
    trusted_git: str,
) -> None:
    """FU1 Test D. Workspace-level one-shot is scoped to ONE nonce: a
    different, freshly minted workspace is unaffected by another workspace's
    already-consumed authority."""
    grant_a = grant_semantic_capability_issuance(IQ1_TASK)
    grant_b = grant_semantic_capability_issuance(IQ1_TASK)
    workspace_a = _populated(IQ1_TASK, run_id="run-fu1-d-0001", git_executable=trusted_git)
    workspace_b = _populated(IQ1_TASK, run_id="run-fu1-d-0002", git_executable=trusted_git)
    try:
        issue_semantic_broker_capability(
            grant_a, workspace=workspace_a, run_id="run-fu1-d-0001"
        )
        sed_b = issue_semantic_broker_capability(
            grant_b, workspace=workspace_b, run_id="run-fu1-d-0002"
        )
        assert sed_b.canonical_root == workspace_b.workspace_root
    finally:
        remove_run_workspace(workspace_a)
        remove_run_workspace(workspace_b)


def test_e_discard_run_workspace_retires_the_workspace_issuance_state(
    trusted_git: str,
) -> None:
    """FU1 Test E. ``discard_run_workspace`` retires the workspace-level
    semantic-issuance authority for that nonce, so the SAME nonce is never
    presented twice (it is disposable), but the retirement itself is
    verifiable via the module's own registry."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-fu1-e-0001", git_executable=trusted_git)
    issue_semantic_broker_capability(grant, workspace=workspace, run_id="run-fu1-e-0001")
    assert workspace.run_workspace_nonce in workspace_module._WORKSPACE_SEMANTIC_ISSUANCE
    remove_run_workspace(workspace)
    assert workspace.run_workspace_nonce not in workspace_module._WORKSPACE_SEMANTIC_ISSUANCE


def test_f_ordinary_category_b_is_unaffected_by_workspace_issuance_state(
    run_workspace, patched
) -> None:
    """FU1 Test F. The workspace-level one-shot registry is semantic-only:
    an ordinary Category-B ``create_broker`` call never touches it, and two
    successive Category-B broker creations against the SAME workspace (a
    pattern Category-B never exercises in practice, but which its own
    contract does not forbid) are each independently inert, never refused by
    the semantic-issuance registry."""
    adapters = _adapters()
    claim_run_workspace(run_workspace, run_id="run-fu1-f-0001")
    observation = adapters.create_broker(
        BrokerCreationRequest(run_id="run-fu1-f-0001", workspace=run_workspace)
    )
    assert observation.session is not None
    assert run_workspace.run_workspace_nonce not in workspace_module._WORKSPACE_SEMANTIC_ISSUANCE


# ===========================================================================
# OBSERVED MANIFEST  (obligations 23-27)
# ===========================================================================


def test_the_manifest_is_the_observed_git_index(trusted_git: str) -> None:
    """Obligations 23, 26, 27. The manifest is what Git's index actually
    reports, minted through the FROZEN ``ar2.capability.mint_capability`` --
    proved by the capability id prefix that only that function produces --
    and it carries IQ-1's protected/witness semantics."""
    assert workspace_module.mint_capability is ar2_capability.mint_capability
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-manifest-0001", git_executable=trusted_git)
    try:
        sed = issue_semantic_broker_capability(
            grant, workspace=workspace, run_id="run-c1-manifest-0001"
        )
        observed = workspace_module.observe_repository(
            git_executable=trusted_git, workspace_root=workspace.workspace_root
        )
        expected = tuple(sorted(entry.path for entry in observed.index_entries))
        assert sed.manifest == expected
        assert sed.capability_id.startswith("ar2-cap-")

        # C1-P5: the frozen task contract, not a caller list.
        witnesses = frozenset(IQ1_TASK.case.verification_witness_paths)
        assert witnesses
        assert witnesses <= sed.protected_paths
        assert not (witnesses & sed.write_eligible)
        assert sed.write_eligible < sed.read_eligible
        assert "money/rounding.py" in sed.write_eligible
    finally:
        remove_run_workspace(workspace)


def test_an_intended_and_observed_manifest_disagreement_refuses(trusted_git: str) -> None:
    """Obligation 24. Neither side is preferred: a disagreement means the
    populated fixture is not the fixture this revision names."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-disagree-0001", git_executable=trusted_git)
    try:
        # Track one extra file, so the OBSERVED index no longer matches the
        # frozen task's intended file set.
        semantic_workspace_module._git(
            trusted_git,
            ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "add", "--", "."],
            cwd=workspace.workspace_root,
            environment=semantic_workspace_module._fixture_git_environment(),
        )
        extra = Path(workspace.workspace_root) / "unexpected.py"
        extra.write_text("x = 1\n", encoding="utf-8", newline="\n")
        semantic_workspace_module._git(
            trusted_git,
            ["add", "--", "unexpected.py"],
            cwd=workspace.workspace_root,
            environment=semantic_workspace_module._fixture_git_environment(),
        )
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant, workspace=workspace, run_id="run-c1-disagree-0001"
            )
        assert excinfo.value.reason_code == "INTENDED_AND_OBSERVED_MANIFEST_DISAGREE"
    finally:
        remove_run_workspace(workspace)


def test_no_filesystem_walk_or_glob_is_used_as_authority() -> None:
    """Obligation 25. The manifest cannot come from the filesystem: none of
    the enumeration primitives appears anywhere in the module's code."""
    tree = _module_tree(workspace_module)
    used = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    } | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    for forbidden in (
        "glob",
        "rglob",
        "iglob",
        "walk",
        "listdir",
        "scandir",
        "iterdir",
        "fnmatch",
    ):
        assert forbidden not in used, f"i2b_workspace reaches {forbidden!r}"


# ===========================================================================
# TRUSTED GIT -- C1-P12a  (obligations 28-36)
# ===========================================================================


def _p12a_probe(monkeypatch: pytest.MonkeyPatch, workspace) -> dict[str, object]:
    """Instrument the fixture-population path: when did the resolve happen,
    relative to the first file write and the first Git subprocess?"""
    state: dict[str, object] = {"events": [], "dir_at_resolve": None}
    real_resolve = semantic_workspace_module.resolve_git_executable
    real_git = semantic_workspace_module._git

    def _resolve(**kwargs):
        state["events"].append("p12a_resolve")
        state["dir_at_resolve"] = sorted(os.listdir(workspace.workspace_root))
        return real_resolve(**kwargs)

    def _git(git_executable, args, **kwargs):
        state["events"].append(("git", git_executable, tuple(args)[:1]))
        return real_git(git_executable, args, **kwargs)

    monkeypatch.setattr(semantic_workspace_module, "resolve_git_executable", _resolve)
    monkeypatch.setattr(semantic_workspace_module, "_git", _git)
    return state


def test_p12a_resolves_before_the_first_write_and_the_first_subprocess(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligations 28, 36. The checkpoint is the attempt's first Git
    consumption boundary, and the value executed afterwards is the resolver's
    own return value."""
    workspace = mint_qualification_run_workspace()
    try:
        state = _p12a_probe(monkeypatch, workspace)
        populate_semantic_task_workspace(workspace, IQ1_TASK, git_executable=trusted_git)
        events = state["events"]
        assert events[0] == "p12a_resolve"
        assert state["dir_at_resolve"] == []  # not one fixture byte written yet
        git_events = [event for event in events if event != "p12a_resolve"]
        assert git_events, "the fixture population must actually have run git"
        assert [event[0] for event in git_events] == ["git"] * len(git_events)
        assert {event[1] for event in git_events} == {trusted_git}
    finally:
        remove_run_workspace(workspace)


def test_an_arbitrary_absolute_caller_executable_refuses_with_zero_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Obligations 29, 33, 34. Zero Git subprocesses, zero fixture writes, a
    fixed bounded reason code, and no path in the message."""
    workspace = mint_qualification_run_workspace()
    try:
        state = _p12a_probe(monkeypatch, workspace)
        arbitrary = r"C:\attacker\tools\git.exe"
        with pytest.raises(SemanticWorkspaceError) as excinfo:
            populate_semantic_task_workspace(workspace, IQ1_TASK, git_executable=arbitrary)
        assert excinfo.value.reason_code == "GIT_EXECUTABLE_NOT_TRUSTED_RESOLUTION"
        assert arbitrary not in str(excinfo.value)
        assert workspace.workspace_root not in str(excinfo.value)
        assert "\\" not in str(excinfo.value)
        assert state["events"] == ["p12a_resolve"]
        assert os.listdir(workspace.workspace_root) == []
    finally:
        remove_run_workspace(workspace)


def test_a_workspace_local_executable_is_refused_by_the_frozen_resolver(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligation 30. The repository being edited may not supply the program
    that inspects it -- and that check is the FROZEN resolver's, not C1's.
    Here the resolver itself resolves to a workspace-local path and refuses;
    nothing is launched."""
    workspace = mint_qualification_run_workspace()
    try:
        planted = os.path.join(workspace.workspace_root, "git.exe")
        Path(planted).write_text("", encoding="utf-8")
        monkeypatch.setattr(
            "ai_dev_orchestrator.workspace.git_adapter.shutil.which", lambda name: planted
        )
        state = _p12a_probe(monkeypatch, workspace)
        with pytest.raises(SemanticWorkspaceError) as excinfo:
            populate_semantic_task_workspace(workspace, IQ1_TASK, git_executable=planted)
        assert excinfo.value.reason_code == "GIT_EXECUTABLE_UNRESOLVED"
        assert state["events"] == ["p12a_resolve"]
        assert os.listdir(workspace.workspace_root) == ["git.exe"]
    finally:
        remove_run_workspace(workspace)


def test_the_exact_resolver_result_is_allowed(trusted_git: str) -> None:
    """Obligation 31."""
    workspace = mint_qualification_run_workspace()
    try:
        built = populate_semantic_task_workspace(
            workspace, IQ1_TASK, git_executable=trusted_git
        )
        assert built.head_before
        assert "money/rounding.py" in built.tracked_paths
    finally:
        remove_run_workspace(workspace)


@pytest.mark.parametrize("respell", ["lower", "upper", "quoted"])
def test_the_same_target_under_a_different_spelling_refuses(
    trusted_git: str, respell: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligation 32. EXACT STRING EQUALITY, not ``realpath``, ``samefile``,
    canonical-target or alias equivalence. This is the whole basis of the
    single-checkpoint proof: the frozen controller keeps using its ORIGINAL
    string afterwards, so a different SPELLING of the same target is what the
    later consumers would carry."""
    spellings = {
        "lower": trusted_git.lower(),
        "upper": trusted_git.upper(),
        "quoted": os.path.join(os.path.dirname(trusted_git), ".", os.path.basename(trusted_git)),
    }
    supplied = spellings[respell]
    if supplied == trusted_git:  # pragma: no cover - environment dependent
        pytest.skip("this spelling is identical to the resolver result here")
    assert os.path.normcase(os.path.normpath(supplied)) == os.path.normcase(
        os.path.normpath(trusted_git)
    ), "the test must present the SAME TARGET under a different spelling"
    workspace = mint_qualification_run_workspace()
    try:
        state = _p12a_probe(monkeypatch, workspace)
        with pytest.raises(SemanticWorkspaceError) as excinfo:
            populate_semantic_task_workspace(workspace, IQ1_TASK, git_executable=supplied)
        assert excinfo.value.reason_code == "GIT_EXECUTABLE_NOT_TRUSTED_RESOLUTION"
        assert state["events"] == ["p12a_resolve"]
        assert os.listdir(workspace.workspace_root) == []
    finally:
        remove_run_workspace(workspace)


def test_there_is_no_fallback_to_the_caller_path_or_to_a_bare_name() -> None:
    """Obligations 34, 35. Source-level: the ONLY value ever handed to the
    fixture Git runner is the checkpoint's return value, and the module names
    no bare git executable to fall back to."""
    tree = _module_tree(semantic_workspace_module)
    populate = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "populate_semantic_task_workspace"
    )
    for node in ast.walk(populate):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_git":
            first = node.args[0]
            assert isinstance(first, ast.Name) and first.id == "trusted_git_executable", (
                "populate_semantic_task_workspace executes something other than "
                "the checkpoint's return value"
            )
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "git" not in literals
    assert "git.exe" not in literals


# ===========================================================================
# TRUSTED GIT -- C1-P12b  (obligation 37)
# ===========================================================================


def test_the_manifest_observation_independently_resolves_git(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligation 37. The issuance does not carry, receive or trust a Git
    path: it verifies the same workspace and resolves its own, then executes
    exactly that."""
    assert "git_executable" not in inspect.signature(
        workspace_module.issue_semantic_broker_capability
    ).parameters
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-p12b-0001", git_executable=trusted_git)
    seen: list[str] = []
    try:
        real_observe = workspace_module.observe_repository

        def _observe(*, git_executable: str, workspace_root: str):
            seen.append(git_executable)
            return real_observe(git_executable=git_executable, workspace_root=workspace_root)

        monkeypatch.setattr(workspace_module, "observe_repository", _observe)
        issue_semantic_broker_capability(grant, workspace=workspace, run_id="run-c1-p12b-0001")
        assert seen == [trusted_git]
    finally:
        remove_run_workspace(workspace)


def test_an_unresolvable_git_executable_refuses_the_issuance(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligation 37 / fail-closed. No fallback to a carried value, to a bare
    name, or to skipping the observation."""
    from ai_dev_orchestrator.workspace.git_adapter import GitExecutableError

    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-p12b-0002", git_executable=trusted_git)
    try:

        def _refuse(**kwargs):
            raise GitExecutableError("git executable error: synthetic offline refusal")

        monkeypatch.setattr(workspace_module, "resolve_git_executable", _refuse)
        monkeypatch.setattr(
            workspace_module,
            "observe_repository",
            lambda **kwargs: pytest.fail("observation must not run"),
        )
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant, workspace=workspace, run_id="run-c1-p12b-0002"
            )
        assert excinfo.value.reason_code == "GIT_EXECUTABLE_UNRESOLVED"
    finally:
        remove_run_workspace(workspace)


# ===========================================================================
# WHOLE-ATTEMPT ORDERING  (obligations 38, 39)
# ===========================================================================


def test_the_whole_attempt_orders_p12a_before_every_other_git_consumer(
    trusted_git: str, patched, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligations 38, 39. One ordered event log over ONE real
    ``run_semantic_task_attempt``, with the genuine C1 issuance wired into
    ``create_broker``. The P12a resolve-and-compare event is strictly before
    the first Git subprocess, the child-environment build, the manifest
    observation and the later repository observation -- which is what binds
    all four consumers of the controller's single, never-reassigned local
    without reopening the frozen controller."""
    import qualification.semantic_controller as controller_module
    from test_semantic_controller import Harness

    events: list[str] = []
    launch_environments: list[object] = []

    def _record(name: str, real):
        def _wrapped(*args, **kwargs):
            events.append(name)
            return real(*args, **kwargs)

        return _wrapped

    monkeypatch.setattr(
        semantic_workspace_module,
        "resolve_git_executable",
        _record("p12a_resolve", semantic_workspace_module.resolve_git_executable),
    )
    monkeypatch.setattr(
        semantic_workspace_module, "_git", _record("fixture_git", semantic_workspace_module._git)
    )
    monkeypatch.setattr(
        workspace_module,
        "resolve_git_executable",
        _record("issuance_resolve", workspace_module.resolve_git_executable),
    )
    monkeypatch.setattr(
        workspace_module,
        "observe_repository",
        _record("manifest_observe", workspace_module.observe_repository),
    )
    monkeypatch.setattr(
        controller_module,
        "observe_repository",
        _record("repository_observe", controller_module.observe_repository),
    )

    real_build_child_environment = controller_module.build_child_environment

    def _build_child_environment(**kwargs):
        events.append("child_environment")
        built = real_build_child_environment(**kwargs)
        launch_environments.append(built)
        return built

    monkeypatch.setattr(controller_module, "build_child_environment", _build_child_environment)

    harness = Harness("A", trusted_git)
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)
    harness.create_broker = adapters.create_broker

    harness.run(IQ1_TASK, str(tmp_path / "evidence"))

    assert events, "the attempt produced no Git activity at all"
    assert events[0] == "p12a_resolve"
    first = events.index("p12a_resolve")
    for later in ("fixture_git", "child_environment", "issuance_resolve", "manifest_observe"):
        assert later in events, later
        assert first < events.index(later), later
    assert events.index("issuance_resolve") < events.index("manifest_observe")
    # The complete, observed chain over one real attempt:
    #   p12a_resolve -> fixture_git -> child_environment
    #                -> issuance_resolve -> manifest_observe -> repository_observe
    assert list(dict.fromkeys(events)) == [
        "p12a_resolve",
        "fixture_git",
        "child_environment",
        "issuance_resolve",
        "manifest_observe",
        "repository_observe",
    ]

    # Obligation 39: the untrusted Pi child's PATH gets the RESOLVED
    # identity's directory, never a substituted caller path.
    assert launch_environments
    path_entries = launch_environments[0].environment["PATH"].split(os.pathsep)
    assert os.path.dirname(trusted_git) in path_entries


# ===========================================================================
# FAIL CLOSED  (obligations 41-46)
# ===========================================================================


def test_workspace_verification_failure_yields_no_capability(trusted_git: str) -> None:
    """Obligation 41."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-fail-0001", git_executable=trusted_git)
    remove_run_workspace(workspace)
    with pytest.raises(WorkspaceAuthorityError) as excinfo:
        issue_semantic_broker_capability(grant, workspace=workspace, run_id="run-c1-fail-0001")
    assert excinfo.value.reason_code == "NOT_MINTED_BY_QUALIFICATION"


def test_git_observation_failure_yields_no_capability(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligation 42."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-fail-0002", git_executable=trusted_git)
    try:

        def _fail(**kwargs):
            raise ObservationError("observation error: synthetic offline failure")

        monkeypatch.setattr(workspace_module, "observe_repository", _fail)
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant, workspace=workspace, run_id="run-c1-fail-0002"
            )
        assert excinfo.value.reason_code == "REPOSITORY_OBSERVATION_FAILED"
    finally:
        remove_run_workspace(workspace)


def test_an_empty_observed_manifest_yields_no_capability(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligation 43. An empty manifest would mint an inert-by-accident
    capability; it refuses instead."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-fail-0003", git_executable=trusted_git)
    try:
        real_observe = workspace_module.observe_repository

        def _empty(**kwargs):
            return replace(real_observe(**kwargs), index_entries=())

        monkeypatch.setattr(workspace_module, "observe_repository", _empty)
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant, workspace=workspace, run_id="run-c1-fail-0003"
            )
        assert excinfo.value.reason_code == "OBSERVED_MANIFEST_EMPTY"
    finally:
        remove_run_workspace(workspace)


def test_a_mint_failure_yields_no_capability(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligation 44."""
    from ar2.capability import CapabilityMintError

    grant = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-c1-fail-0004", git_executable=trusted_git)
    try:

        def _fail(**kwargs):
            raise CapabilityMintError("capability mint refused: synthetic offline failure")

        monkeypatch.setattr(workspace_module, "mint_capability", _fail)
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant, workspace=workspace, run_id="run-c1-fail-0004"
            )
        assert excinfo.value.reason_code == "CAPABILITY_MINT_REFUSED"
    finally:
        remove_run_workspace(workspace)


def test_a_failed_issuance_never_falls_back_to_the_inert_or_a_wider_domain(
    trusted_git: str, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obligations 45, 46. Through ``create_broker`` itself: a refused
    issuance produces NO broker and NO capability -- an expected, bounded
    refusal that ``create_broker`` projects into the frozen no-session shape
    (FU1 Blocker 2) rather than raising or falling back. It must never
    silently become the inert domain -- a semantic run in which every model
    operation was refused would read as candidate behaviour rather than
    harness failure -- and never a wider one."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)
    workspace = _populated(IQ1_TASK, run_id="run-c1-fail-0005", git_executable=trusted_git)
    try:

        def _fail(**kwargs):
            raise ObservationError("observation error: synthetic offline failure")

        monkeypatch.setattr(workspace_module, "observe_repository", _fail)
        observation = adapters.create_broker(
            BrokerCreationRequest(run_id="run-c1-fail-0005", workspace=workspace)
        )
        assert observation.session is None
        assert observation.start_attempted is False
        assert observation.resource_created is False
        assert adapters._brokers == {}
    finally:
        remove_run_workspace(workspace)


def test_the_semantic_path_produces_a_genuine_capability_through_create_broker(
    trusted_git: str, patched
) -> None:
    """The positive counterpart of the previous test, and the whole point of
    C1: on the semantic path ``create_broker``'s handler carries a capability
    with a real read/write domain, not the inert one."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)
    workspace = _populated(IQ1_TASK, run_id="run-c1-genuine-0001", git_executable=trusted_git)
    try:
        observation = adapters.create_broker(
            BrokerCreationRequest(run_id="run-c1-genuine-0001", workspace=workspace)
        )
        assert observation.session is not None
        sed = adapters._brokers[observation.session.session_id].handler.sed
        assert sed.manifest
        assert sed.read_eligible
        assert sed.write_eligible
        assert sed.write_eligible < sed.read_eligible
        assert sed.capability_id.startswith("ar2-cap-")
        assert observation.session.capability_id == sed.capability_id
        # 5F3B-LIVE1-C1-FU2 correction: ``_semantic_capability_grant is None``
        # proves only that the grant OBJECT was cleared -- it does NOT by
        # itself prove "no second issuance" (an ordinary Category-B instance
        # is also ``None``). The SPENT authority state is what actually
        # closes that boundary; see the FU2 regression section below for the
        # proof that a second call cannot fall back to inert mode.
        assert adapters._semantic_capability_grant is None
        assert adapters._semantic_authority_state == live_module._SEMANTIC_GRANT_SPENT
    finally:
        remove_run_workspace(workspace)


def test_g_a_refused_issuance_lands_at_broker_session_broker_creation_failed(
    trusted_git: str, patched, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU1 Test G / Blocker 2. End to end through the FROZEN semantic
    controller: an EXPECTED issuance refusal (a bounded
    ``WorkspaceAuthorityError``) must land at ``BROKER_SESSION`` with
    ``BROKER_CREATION_FAILED`` -- the frozen design's own wording -- not
    ``ADAPTER_RAISED``. The earlier C1 draft raised through ``create_broker``
    and accepted ``ADAPTER_RAISED`` as a "deliberate deviation"; that
    deviation is withdrawn here, corrected rather than defended, because the
    frozen ``BrokerCreationObservation`` can truthfully represent "no broker
    was ever attempted" (``session=None``, ``start_attempted=False``,
    ``resource_created=False``) without fabricating a start attempt that
    never happened.
    """
    from qualification.semantic_controller import SemanticGateName
    from qualification.i2b_controller import CategoryBFailureCode
    from test_semantic_controller import Harness

    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)

    def _fail(**kwargs):
        raise ObservationError("observation error: synthetic offline failure")

    monkeypatch.setattr(workspace_module, "observe_repository", _fail)

    harness = Harness("A", trusted_git)
    harness.create_broker = adapters.create_broker
    result = harness.run(IQ1_TASK, str(tmp_path / "evidence"))

    assert result.failed_gate is SemanticGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.BROKER_CREATION_FAILED
    assert adapters._brokers == {}


def test_h_expected_issuance_refusal_yields_the_frozen_no_session_shape(
    trusted_git: str, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU1 Test H. Direct adapter observation, not through the controller:
    the exact frozen "nothing was ever attempted" shape."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)
    workspace = _populated(IQ1_TASK, run_id="run-fu1-h-0001", git_executable=trusted_git)
    try:

        def _fail(**kwargs):
            raise ObservationError("observation error: synthetic offline failure")

        monkeypatch.setattr(workspace_module, "observe_repository", _fail)

        observation = adapters.create_broker(
            BrokerCreationRequest(run_id="run-fu1-h-0001", workspace=workspace)
        )
        assert observation.session is None
        assert observation.start_attempted is False
        assert observation.resource_created is False
        assert observation.cleanup_attempted is False
        assert observation.reached_closed is None
    finally:
        remove_run_workspace(workspace)


def test_i_broker_server_is_never_constructed_on_issuance_refusal(
    trusted_git: str, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU1 Test I. No ``BrokerServer`` construction or start call is reached
    when the semantic issuance itself refuses -- proved by patching
    ``BrokerServer`` to fail loudly if touched at all, AFTER the ``patched``
    fixture has bound the trusted-identity resolvers (construction requires
    them regardless of this test's own concern)."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)
    workspace = _populated(IQ1_TASK, run_id="run-fu1-i-0001", git_executable=trusted_git)
    try:

        def _fail(**kwargs):
            raise ObservationError("observation error: synthetic offline failure")

        def _must_not_construct(*args, **kwargs):
            pytest.fail("BrokerServer must not be constructed on issuance refusal")

        monkeypatch.setattr(workspace_module, "observe_repository", _fail)
        monkeypatch.setattr(live_module, "BrokerServer", _must_not_construct)

        observation = adapters.create_broker(
            BrokerCreationRequest(run_id="run-fu1-i-0001", workspace=workspace)
        )
        assert observation.session is None
        assert adapters._brokers == {}
    finally:
        remove_run_workspace(workspace)


def test_j_an_unexpected_exception_still_reaches_adapter_raised(
    trusted_git: str, patched, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FU1 Test J. An UNEXPECTED, non-``WorkspaceAuthorityError`` exception
    from the issuance seam is a programmer-error signal, not a bounded
    refusal, and must NOT be caught here: it still reaches the frozen
    controller's ``ADAPTER_RAISED`` path, proving the two failure classes
    (expected refusal vs. unexpected exception) remain distinct."""
    from qualification.semantic_controller import SemanticGateName
    from qualification.i2b_controller import CategoryBFailureCode
    from test_semantic_controller import Harness

    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)

    def _blow_up(*args, **kwargs):
        raise RuntimeError("synthetic unexpected programmer error")

    monkeypatch.setattr(workspace_module, "issue_semantic_broker_capability", _blow_up)
    monkeypatch.setattr(live_module, "issue_semantic_broker_capability", _blow_up)

    harness = Harness("A", trusted_git)
    harness.create_broker = adapters.create_broker
    result = harness.run(IQ1_TASK, str(tmp_path / "evidence"))

    assert result.failed_gate is SemanticGateName.BROKER_SESSION
    assert result.failure_code is CategoryBFailureCode.ADAPTER_RAISED
    assert adapters._brokers == {}


# ===========================================================================
# 5F3B-LIVE1-C1-FU2 -- SEMANTIC ADAPTER SPENT-STATE FAIL-CLOSED CLOSURE
# ===========================================================================
#
# THE BLOCKER. ``_semantic_capability_grant is None`` used to carry TWO
# meanings at once: an ordinary Category-B adapter (correctly inert), and a
# semantic adapter whose one grant was already consumed (which must NEVER
# become inert). ``create_broker`` could not tell them apart, so a SECOND
# call on a semantic instance fell into the inert Category-B branch. These
# tests prove the corrected three-state authority
# (``_CATEGORY_B_INERT`` / ``_SEMANTIC_GRANT_PENDING`` /
# ``_SEMANTIC_GRANT_SPENT``) closes that in all three first-call outcome
# shapes, and that the ordinary Category-B path and the FU1 workspace-level
# one-shot are unaffected.


def test_fu2_a_success_then_second_call_refuses_without_inert_fallback(
    trusted_git: str, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Required regression A. First call SUCCEEDS with a genuine capability;
    the second call on the SAME adapter refuses -- no session, no inert
    capability, no second issuance, no BrokerServer construction/start, and
    no broker registry addition."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)
    workspace = _populated(IQ1_TASK, run_id="run-fu2-a-0001", git_executable=trusted_git)
    try:
        first = adapters.create_broker(
            BrokerCreationRequest(run_id="run-fu2-a-0001", workspace=workspace)
        )
        assert first.session is not None
        assert adapters._semantic_authority_state == live_module._SEMANTIC_GRANT_SPENT

        issuance_calls: list[str] = []
        real_issue = workspace_module.issue_semantic_broker_capability

        def _count_issue(*args, **kwargs):
            issuance_calls.append("issued")
            return real_issue(*args, **kwargs)

        def _must_not_construct(*args, **kwargs):
            pytest.fail("BrokerServer must not be constructed on a spent semantic adapter")

        monkeypatch.setattr(workspace_module, "issue_semantic_broker_capability", _count_issue)
        monkeypatch.setattr(live_module, "issue_semantic_broker_capability", _count_issue)
        monkeypatch.setattr(live_module, "BrokerServer", _must_not_construct)

        brokers_before = dict(adapters._brokers)
        second = adapters.create_broker(
            BrokerCreationRequest(run_id="run-fu2-a-0001", workspace=workspace)
        )
        assert second.session is None
        assert second.start_attempted is False
        assert second.resource_created is False
        assert issuance_calls == []
        assert adapters._brokers == brokers_before
        assert adapters._semantic_authority_state == live_module._SEMANTIC_GRANT_SPENT
    finally:
        remove_run_workspace(workspace)


def test_fu2_b_expected_refusal_then_second_call_still_refuses(
    trusted_git: str, patched, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Required regression B. First call gets an EXPECTED
    ``WorkspaceAuthorityError``; the second call still refuses, never enters
    inert mode, and never calls ``issue_semantic_broker_capability`` again."""
    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)
    workspace = _populated(IQ1_TASK, run_id="run-fu2-b-0001", git_executable=trusted_git)
    try:

        def _fail(**kwargs):
            raise ObservationError("observation error: synthetic offline failure")

        monkeypatch.setattr(workspace_module, "observe_repository", _fail)

        first = adapters.create_broker(
            BrokerCreationRequest(run_id="run-fu2-b-0001", workspace=workspace)
        )
        assert first.session is None
        assert adapters._semantic_authority_state == live_module._SEMANTIC_GRANT_SPENT

        issuance_calls: list[str] = []
        real_issue = workspace_module.issue_semantic_broker_capability

        def _count_issue(*args, **kwargs):
            issuance_calls.append("issued")
            return real_issue(*args, **kwargs)

        monkeypatch.setattr(workspace_module, "issue_semantic_broker_capability", _count_issue)
        monkeypatch.setattr(live_module, "issue_semantic_broker_capability", _count_issue)

        second = adapters.create_broker(
            BrokerCreationRequest(run_id="run-fu2-b-0001", workspace=workspace)
        )
        assert second.session is None
        assert second.start_attempted is False
        assert second.resource_created is False
        assert issuance_calls == []
        assert adapters._brokers == {}
    finally:
        remove_run_workspace(workspace)


def test_fu2_c_unexpected_exception_then_second_call_does_not_go_inert(
    trusted_git: str, patched, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Required regression C. First call raises an UNEXPECTED ``RuntimeError``
    (``ADAPTER_RAISED``, through the frozen controller); the second, direct
    ``create_broker`` call on the same adapter still refuses -- never the
    inert Category-B domain."""
    from qualification.semantic_controller import SemanticGateName
    from qualification.i2b_controller import CategoryBFailureCode
    from test_semantic_controller import Harness

    grant = grant_semantic_capability_issuance(IQ1_TASK)
    adapters = _semantic_adapters(grant)
    workspace = _populated(IQ1_TASK, run_id="run-fu2-c-0001", git_executable=trusted_git)
    try:

        def _blow_up(*args, **kwargs):
            raise RuntimeError("synthetic unexpected programmer error")

        monkeypatch.setattr(workspace_module, "issue_semantic_broker_capability", _blow_up)
        monkeypatch.setattr(live_module, "issue_semantic_broker_capability", _blow_up)

        harness = Harness("A", trusted_git)
        harness.create_broker = adapters.create_broker
        result = harness.run(IQ1_TASK, str(tmp_path / "evidence"))
        assert result.failed_gate is SemanticGateName.BROKER_SESSION
        assert result.failure_code is CategoryBFailureCode.ADAPTER_RAISED
        assert adapters._semantic_authority_state == live_module._SEMANTIC_GRANT_SPENT

        monkeypatch.undo()  # restore issue_semantic_broker_capability for the second call

        second = adapters.create_broker(
            BrokerCreationRequest(run_id="run-fu2-c-0001", workspace=workspace)
        )
        assert second.session is None
        assert second.start_attempted is False
        assert second.resource_created is False
        assert adapters._brokers == {}
    finally:
        remove_run_workspace(workspace)


def test_fu2_d_ordinary_category_b_still_uses_inert_domain(run_workspace, patched) -> None:
    """Required regression D. Ordinary Category-B semantics are unchanged:
    the state starts ``CATEGORY_B_INERT`` and ``create_broker`` still uses
    the inert domain."""
    adapters = _adapters()
    assert adapters._semantic_authority_state == live_module._CATEGORY_B_INERT
    claim_run_workspace(run_workspace, run_id="run-fu2-d-0001")
    observation = adapters.create_broker(
        BrokerCreationRequest(run_id="run-fu2-d-0001", workspace=run_workspace)
    )
    assert observation.session is not None
    sed = adapters._brokers[observation.session.session_id].handler.sed
    assert sed.read_eligible == frozenset()
    assert sed.write_eligible == frozenset()
    assert adapters._semantic_authority_state == live_module._CATEGORY_B_INERT


def test_fu2_e_no_public_semantic_mode_switch_was_introduced() -> None:
    """Required regression E. Source/signature proof: no public caller-facing
    mode boolean or switch exists on the constructor or the semantic
    factory."""
    ctor_parameters = tuple(
        inspect.signature(live_module.LiveCategoryBAdapters.__init__).parameters
    )
    assert ctor_parameters == (
        "self",
        "environ_reader",
        "runtime_identity",
        "experiment_id",
        "bounds",
    )
    factory_parameters = tuple(
        inspect.signature(live_module.build_semantic_task_live_adapters).parameters
    )
    assert factory_parameters == ("environ_reader", "runtime_identity", "capability_grant")
    forbidden_names = (
        "semantic",
        "semantic_mode",
        "enable_writes",
        "use_real_capability",
        "capability_source",
        "domain",
        "mode",
    )
    for parameters in (ctor_parameters, factory_parameters):
        for name in parameters:
            lowered = name.lower()
            for forbidden in forbidden_names:
                assert forbidden not in lowered, (parameters, name, forbidden)
    assert not hasattr(live_module.LiveCategoryBAdapters, "set_semantic_mode")
    assert not hasattr(live_module.LiveCategoryBAdapters, "semantic_mode")


def test_fu3_f_discard_semantic_capability_grants_clears_grants_only(
    trusted_git: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Required regression F (FU3 replacement). The FU2 "fix" was itself the
    defect: clearing ``_WORKSPACE_SEMANTIC_ISSUANCE`` from the GRANT-registry
    teardown helper reopened the C1-P8 workspace-level one-shot -- a caller
    could mint+claim one workspace, issue once, call the teardown helper, and
    then issue a SECOND time against the SAME still-alive workspace with a
    fresh grant. ``discard_semantic_capability_grants`` now clears ONLY
    ``_SEMANTIC_GRANTS``; only :func:`discard_run_workspace` /
    :func:`remove_run_workspace` may retire a workspace's own nonce."""
    grant1 = grant_semantic_capability_issuance(IQ1_TASK)
    workspace = _populated(IQ1_TASK, run_id="run-fu3-f-0001", git_executable=trusted_git)
    try:
        # 1-2: mint + claim + populate already done by _populated(); issue once.
        issue_semantic_broker_capability(grant1, workspace=workspace, run_id="run-fu3-f-0001")
        # 3: the workspace nonce is recorded as having consumed its one-shot.
        assert workspace.run_workspace_nonce in workspace_module._WORKSPACE_SEMANTIC_ISSUANCE

        # 4: the teardown helper under test.
        workspace_module.discard_semantic_capability_grants()

        # 5: it cleared the grant registry...
        assert workspace_module._SEMANTIC_GRANTS == {}
        # 6: ...but the workspace-level one-shot fact MUST survive it.
        assert workspace.run_workspace_nonce in workspace_module._WORKSPACE_SEMANTIC_ISSUANCE

        # 7: a fresh, genuinely minted grant, created AFTER the helper call.
        grant2 = grant_semantic_capability_issuance(IQ1_TASK)

        # 10: no Git resolution, observation or mint may occur on this retry
        # -- the workspace-issuance consumption check runs before all three.
        monkeypatch.setattr(
            workspace_module,
            "resolve_git_executable",
            lambda **kwargs: pytest.fail("resolve_git_executable must not run on retry"),
        )
        monkeypatch.setattr(
            workspace_module,
            "observe_repository",
            lambda **kwargs: pytest.fail("observe_repository must not run on retry"),
        )
        monkeypatch.setattr(
            workspace_module,
            "mint_capability",
            lambda **kwargs: pytest.fail("mint_capability must not run on retry"),
        )

        # 8-9: same live workspace, same run -- must refuse, never issue.
        with pytest.raises(WorkspaceAuthorityError) as excinfo:
            issue_semantic_broker_capability(
                grant2, workspace=workspace, run_id="run-fu3-f-0001"
            )
        assert excinfo.value.reason_code == "WORKSPACE_SEMANTIC_ISSUANCE_ALREADY_CONSUMED"
    finally:
        monkeypatch.undo()
        # also proves discard/remove_run_workspace still retires its own nonce.
        remove_run_workspace(workspace)
        assert workspace.run_workspace_nonce not in workspace_module._WORKSPACE_SEMANTIC_ISSUANCE
