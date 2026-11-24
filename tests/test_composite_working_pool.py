"""Composite pool bindings keep nested search inputs local without copying values."""
from __future__ import annotations

import copy

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch

from nsgablack.adapters import (
    ChangeResult, MultiStrategyConfig, NSGA2Adapter, PoolTaskSpec, RoleSpec,
    SerialPhaseSpec, StrategyChainAdapter, StrategyRouterAdapter, VNSAdapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.context_keys import KEY_SOLUTION_WORKING_POOL
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.plugins.base import Plugin
from nsgablack.project.case_support.adapter_config import create_bindings
from nsgablack.representation import RepresentationPipeline
from tests.test_subpool_tasks import Operator


class CountedSphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-100., 100.)])
        self.calls = []

    def evaluate(self, candidate):
        row = np.array(candidate, dtype=float, copy=True)
        self.calls.append(row)
        return [float(row @ row)]


def build_solver(adapter):
    solver = ComposableSolver(CountedSphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator(1.)))
    solver.set_random_seed(310)
    solver.setup()
    return solver


def add_seeds(solver, values=(50., 60., 4., 5., 8., 9.)):
    return solver.store_solutions(CandidateBatch.from_candidates(
        [np.array([value]) for value in values],
        candidate_tokens=tuple(f"seed:{index}" for index in range(len(values)))), source="seed")


def router(*, working_pool=None, spec=None, leaf=None, name="group"):
    leaf = leaf or NSGA2Adapter(name="ga", population_size=2, offspring_size=2)
    adapter = StrategyRouterAdapter(name=name, working_pool=working_pool,
        roles=[RoleSpec("search", leaf, pool_task=spec or PoolTaskSpec(
            mode="initialize", shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
    return adapter, leaf


def seed_sources(solver, leaf):
    refs = leaf.get_population_solution_refs(solver)
    return tuple(item["metadata"]["solution_source_ref"]["candidate_token"]
                 for item in solver.solution_pool.read_provenance(refs))


def exact_first_two(control, context):
    del context
    return control.solution_pool.subpool_refs("explicit")


def working_initial_donor(request, *, rng):
    del rng
    source = request.pool.main(stage="initial")
    if len(source) != 2:
        raise AssertionError("the current working source escaped into the Solver root")
    return source.values[0] - .5


def archive_working_initials(request, *, rng):
    del rng
    source = request.pool.main(stage="initial")
    return (request.pool.replace_members("archive", source.refs, create=True),)


def replace_own_workspace(request, *, rng):
    del rng
    return ChangeResult(request.candidate - .5,
        edits=(request.pool.replace_members("workspace", ()),))


def test_unbound_composite_preserves_the_default_root_source():
    group, leaf = router()
    solver = build_solver(group)
    refs = add_seeds(solver)
    assert solver.step().committed
    assert seed_sources(solver, leaf) == tuple(ref.candidate_token for ref in refs[:2])
    assert solver.evaluation_count == len(solver.problem.calls) == 2


def test_router_uses_only_its_workspace_and_appends_exact_admitted_versions():
    group, leaf = router(working_pool="workspace")
    solver = build_solver(group)
    refs = add_seeds(solver)
    pool = solver.solution_pool
    pool.create_subpool("workspace", refs[2:4])
    before_descriptor = pool.subpool_descriptor("workspace")
    assert solver.step().committed
    assert solver.solution_pool is pool
    assert seed_sources(solver, leaf) == tuple(ref.candidate_token for ref in refs[2:4])
    accepted = pool.select(stage="accepted")
    assert pool.subpool_refs("workspace") == (*refs[2:4], *accepted)
    assert pool.subpool_descriptor("workspace")["view_id"] == before_descriptor["view_id"]
    assert not set(refs[:2]).intersection(pool.subpool_refs("workspace"))
    assert leaf.population.shape == (2, 1)  # Pool history is not Unit membership.


@pytest.mark.parametrize("outer_binding,inner_binding,expected", [
    ("outer", None, (2, 3)),
    ("outer", "inner", (4, 5)),
    (None, "inner", (4, 5)),
])
def test_serial_to_router_inherits_the_nearest_binding_without_filling_ancestors(
        outer_binding, inner_binding, expected):
    group, leaf = router(working_pool=inner_binding)
    chain = StrategyChainAdapter([SerialPhaseSpec("nested", group)], working_pool=outer_binding)
    solver = build_solver(chain)
    refs = add_seeds(solver)
    pool = solver.solution_pool
    pool.create_subpool("outer", refs[2:4])
    pool.create_subpool("inner", refs[4:6])
    assert solver.step().committed
    assert seed_sources(solver, leaf) == tuple(refs[index].candidate_token for index in expected)
    accepted = pool.select(stage="accepted")
    active = "inner" if inner_binding else "outer"
    original = refs[4:6] if active == "inner" else refs[2:4]
    assert pool.subpool_refs(active) == (*original, *accepted)
    other = "outer" if active == "inner" else "inner"
    assert pool.subpool_refs(other) == (refs[2:4] if other == "outer" else refs[4:6])
    assert len(set(pool.subpool_refs(active))) == len(pool.subpool_refs(active))


def test_nested_routers_inherit_one_binding_and_record_each_version_once():
    inner, leaf = router(name="inner")
    outer = StrategyRouterAdapter(name="outer", working_pool="workspace",
        roles=[RoleSpec("nested", inner)],
        config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
    solver = build_solver(outer)
    refs = add_seeds(solver)
    solver.solution_pool.create_subpool("workspace", refs[2:4])
    assert solver.step().committed
    assert seed_sources(solver, leaf) == tuple(ref.candidate_token for ref in refs[2:4])
    assert solver.solution_pool.subpool_refs("workspace") == (
        *refs[2:4], *solver.solution_pool.select(stage="accepted"))


@pytest.mark.parametrize("selection", ["selected", exact_first_two])
def test_explicit_task_source_overrides_default_workspace_without_rewriting_names(selection):
    group, leaf = router(working_pool="workspace", spec=PoolTaskSpec(
        selection, mode="initialize", shuffle=False))
    solver = build_solver(group)
    refs = add_seeds(solver)
    solver.solution_pool.create_subpool("workspace", refs[2:4])
    solver.solution_pool.create_subpool("group/selected", refs[:2])
    solver.solution_pool.create_subpool("explicit", refs[:2])
    assert solver.step().committed
    assert seed_sources(solver, leaf) == tuple(ref.candidate_token for ref in refs[:2])
    # Input selection does not append the offspring into the donor collection.
    assert solver.solution_pool.subpool_refs("group/selected") == refs[:2]
    assert solver.solution_pool.subpool_refs("explicit") == refs[:2]
    assert solver.solution_pool.subpool_refs("workspace") == (
        *refs[2:4], *solver.solution_pool.select(stage="accepted"))


@pytest.mark.parametrize("kind", ["missing", "algorithm-view"])
def test_workspace_must_exist_as_a_committed_ordinary_collection_before_evaluation(kind):
    group, _ = router(working_pool="workspace")
    solver = build_solver(group)
    refs = add_seeds(solver)
    if kind == "algorithm-view":
        solver.solution_pool.publish_subpool_view("workspace", refs[2:4], created_by=("owner",))
    with pytest.raises((KeyError, ValueError), match="workspace|ordinary|candidate_collection|view"):
        solver.step()
    assert solver.evaluation_count == len(solver.problem.calls) == 0
    if kind == "missing":
        assert not solver.solution_pool.has_subpool("workspace")


@pytest.mark.parametrize("allow_main", [False, True])
def test_change_main_reads_the_working_region_without_bypassing_task_permissions(allow_main):
    leaf = VNSAdapter(name="local", change=working_initial_donor, batch_size=1,
                      restart_on_stagnation=False)
    group, _ = router(leaf=leaf, working_pool="workspace", spec=PoolTaskSpec(
        steps=2, count=1, shuffle=False, change_allow_main=allow_main))
    solver = build_solver(group)
    refs = add_seeds(solver)
    solver.solution_pool.create_subpool("workspace", refs[2:4])
    assert solver.step().committed
    assert leaf.current_x[0] == 4.
    if allow_main:
        assert solver.step().committed
        assert leaf.current_x[0] == 3.5
        assert solver.evaluation_count == 2
    else:
        with pytest.raises(ValueError, match="mother pool|declared inputs"):
            solver.step()
        assert solver.evaluation_count == 1
        assert leaf.current_x[0] == 4.


def test_update_maintenance_receives_the_same_working_main_scope():
    leaf = NSGA2Adapter(population_size=2, offspring_size=2,
                        pool_maintenance=archive_working_initials)
    group, _ = router(leaf=leaf, working_pool="workspace", spec=PoolTaskSpec(
        mode="initialize", shuffle=False, change_sources=("archive",), change_allow_main=True))
    solver = build_solver(group)
    refs = add_seeds(solver)
    solver.solution_pool.create_subpool("workspace", refs[2:4])
    assert solver.step().committed
    assert solver.solution_pool.subpool_refs("archive") == refs[2:4]


class Admission:
    def __init__(self, selected):
        self.selected = selected

    def select(self, candidates, feedback, context):
        return BatchDisposition(len(candidates.semantic_states), self.selected)


@pytest.mark.parametrize("selected", [(), (1,)])
def test_only_hard_admitted_versions_join_the_workspace(selected):
    group, leaf = router(working_pool="workspace")
    solver = build_solver(group)
    refs = add_seeds(solver)
    pool = solver.solution_pool
    pool.create_subpool("workspace", refs[2:4])
    solver.set_evaluation_acceptance_policy(Admission(selected))
    outcome = solver.step()
    accepted = pool.select(stage="accepted")
    assert outcome.committed is bool(selected)
    assert len(accepted) == len(selected)
    assert pool.subpool_refs("workspace") == (*refs[2:4], *accepted)
    assert solver.evaluation_count == len(solver.problem.calls) == 2
    if selected:
        assert seed_sources(solver, leaf) == (refs[3].candidate_token,)
        task = group.units[0].adapter
        assert pool.input_remaining(task._local["input"]) == 1


def test_sibling_failure_rolls_back_workspace_and_allocations_but_keeps_real_cost(monkeypatch):
    first = NSGA2Adapter(name="first", population_size=2, offspring_size=2)
    second = NSGA2Adapter(name="second", population_size=2, offspring_size=2)
    group = StrategyRouterAdapter(working_pool="workspace", roles=[
        RoleSpec("first", first, pool_task=PoolTaskSpec(mode="initialize", shuffle=False)),
        RoleSpec("second", second, pool_task=PoolTaskSpec(mode="initialize", shuffle=False)),
    ], config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False))
    solver = build_solver(group)
    refs = add_seeds(solver)
    pool = solver.solution_pool
    pool.create_subpool("workspace", refs[2:4])
    original_descriptor = pool.subpool_descriptor("workspace")

    def fail(*args, **kwargs):
        raise RuntimeError("second child failed")

    monkeypatch.setattr(second, "update", fail)
    with pytest.raises(RuntimeError, match="second child failed"):
        solver.step()
    assert pool.subpool_refs("workspace") == refs[2:4]
    assert pool.subpool_descriptor("workspace") == original_descriptor
    assert not pool.select(stage="accepted")
    assert first.population is None and second.population is None
    assert all(unit.adapter.task_status["status"] is None for unit in group.units)
    assert solver.evaluation_count == len(solver.problem.calls) == 4


def test_explicit_replacement_of_auto_appended_workspace_is_a_transaction_conflict():
    leaf = VNSAdapter(name="local", change=replace_own_workspace, batch_size=1,
                      restart_on_stagnation=False)
    group, _ = router(leaf=leaf, working_pool="workspace", spec=PoolTaskSpec(
        count=1, steps=3, shuffle=False, change_sources=("workspace",)))
    solver = build_solver(group)
    refs = add_seeds(solver)
    pool = solver.solution_pool
    pool.create_subpool("workspace", refs[2:4])
    assert solver.step().committed
    before = pool.subpool_refs("workspace")
    descriptor = pool.subpool_descriptor("workspace")
    current = np.array(leaf.current_x, copy=True)
    with pytest.raises(ValueError, match="append|replace|conflict|workspace"):
        solver.step()
    assert pool.subpool_refs("workspace") == before
    assert pool.subpool_descriptor("workspace") == descriptor
    np.testing.assert_array_equal(leaf.current_x, current)
    assert solver.evaluation_count == len(solver.problem.calls) == 2


def test_failure_after_workspace_staging_restores_the_committed_area_and_authority(monkeypatch):
    group, leaf = router(working_pool="workspace")
    solver = build_solver(group)
    refs = add_seeds(solver)
    pool = solver.solution_pool
    pool.create_subpool("workspace", refs[2:4])
    assert solver.step().committed
    descriptor = pool.subpool_descriptor("workspace")
    members, manifest = pool.subpool_refs("workspace"), pool.publication_ref()
    adapter_state = copy.deepcopy(group.get_state())
    observed = []

    def fail_after_staging(*args, **kwargs):
        observed.append(pool.subpool_metadata("workspace")["published"])
        raise RuntimeError("publication failed after working area staging")

    monkeypatch.setattr(solver, "_update_best", fail_after_staging)
    with pytest.raises(RuntimeError, match="after working area staging"):
        solver.step()
    assert observed == [False]
    assert pool.subpool_descriptor("workspace") == descriptor
    assert pool.subpool_refs("workspace") == members
    assert pool.publication_ref() == manifest
    assert group.get_state() == adapter_state
    assert solver.evaluation_count == len(solver.problem.calls) == 4


def test_checkpoint_restores_binding_pool_members_and_next_search_without_replaying_evaluation():
    group, _ = router(working_pool="workspace")
    source = build_solver(group)
    refs = add_seeds(source)
    source.solution_pool.create_subpool("workspace", refs[2:4])
    assert source.step().committed
    resumed_group, resumed_leaf = router(working_pool="workspace")
    target = build_solver(resumed_group)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target, payload=writer._build_payload(solver=source, reason="working-pool"))
    assert not target.problem.calls
    assert target.solution_pool.subpool_refs("workspace") == source.solution_pool.subpool_refs("workspace")
    restored_refs = target.solution_pool.subpool_refs("workspace")
    assert source.step().committed and target.step().committed
    # Loaded historical identities survive transport exactly. Future evaluated
    # proposals are new identities in each fork, not replayed UUIDs.
    source_refs = source.solution_pool.subpool_refs("workspace")
    target_refs = target.solution_pool.subpool_refs("workspace")
    assert source_refs[:len(restored_refs)] == target_refs[:len(restored_refs)] == restored_refs
    assert len(source_refs) == len(target_refs) == len(restored_refs) + 2
    np.testing.assert_array_equal(source.solution_pool.read(source_refs).numeric_matrix,
                                  target.solution_pool.read(target_refs).numeric_matrix)
    np.testing.assert_array_equal(resumed_leaf.population, group.units[0].adapter.inner.population)
    assert target.evaluation_count == source.evaluation_count == 4
    assert len(target.problem.calls) == 2


def test_recreating_the_same_workspace_name_cannot_redirect_an_active_composite():
    group, _ = router(working_pool="workspace")
    solver = build_solver(group)
    refs = add_seeds(solver)
    pool = solver.solution_pool
    pool.create_subpool("workspace", refs[2:4])
    assert solver.step().committed
    before = pool.subpool_refs("workspace")
    descriptor = pool.subpool_descriptor("workspace")
    pool.drop_subpool("workspace")
    pool.create_subpool("workspace", before)
    replacement = pool.subpool_descriptor("workspace")
    assert replacement["view_id"] != descriptor["view_id"]
    with pytest.raises(ValueError, match="working.pool|identity|changed|binding"):
        solver.step()
    assert pool.subpool_refs("workspace") == before
    assert pool.subpool_descriptor("workspace") == replacement
    assert solver.evaluation_count == len(solver.problem.calls) == 2


@pytest.mark.parametrize("kind", ["router", "chain"])
def test_checkpoint_rejects_changed_explicit_working_pool_binding(kind):
    def build(binding):
        group, _ = router(working_pool=binding if kind == "router" else None)
        adapter = (group if kind == "router" else StrategyChainAdapter(
            [SerialPhaseSpec("nested", group)], working_pool=binding))
        return build_solver(adapter)

    source = build("workspace")
    refs = add_seeds(source)
    source.solution_pool.create_subpool("workspace", refs[2:4])
    assert source.step().committed
    state = copy.deepcopy(source.adapter.get_state())
    target = build("different")
    with pytest.raises(ValueError, match="working.pool|binding|configuration|identity"):
        target.adapter.set_state(state)


def test_explicit_setter_is_available_before_the_first_search_attempt():
    group, leaf = router()
    group.set_working_pool("workspace")
    solver = build_solver(group)
    refs = add_seeds(solver)
    solver.solution_pool.create_subpool("workspace", refs[2:4])
    assert solver.step().committed
    assert seed_sources(solver, leaf) == tuple(ref.candidate_token for ref in refs[2:4])


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_catalog_exposes_working_area_on_both_composite_surfaces(profile):
    from nsgablack.catalog import get_catalog
    catalog = get_catalog(profile=profile, refresh=True)
    for key, expected in (("adapter.multi_strategy", StrategyRouterAdapter),
                          ("adapter.serial_strategy", StrategyChainAdapter)):
        entry = catalog.get(key)
        assert entry.load() is expected
        assert "working_pool" in entry.config_keys


def test_inspection_validates_only_the_binding_declaration_without_starting_a_pool_or_unit():
    from nsgablack.utils.runtime_contracts import inspect_runtime_contracts
    group, leaf = router(working_pool="not_created_yet")
    solver = build_solver(group)
    assert leaf.algorithm_unit is None
    assert not solver.solution_pool.has_subpool("not_created_yet")
    issues = inspect_runtime_contracts(solver)
    assert not any(code == "solution-pool-working-binding-invalid" for code, _ in issues)
    assert leaf.algorithm_unit is None
    assert not solver.solution_pool.has_subpool("not_created_yet")
    group._working_pool = ""  # Corrupted declaration, without running its code.
    issues = inspect_runtime_contracts(solver)
    assert any(code == "solution-pool-working-binding-invalid" for code, _ in issues)
    assert leaf.algorithm_unit is None


@pytest.mark.parametrize("kind", ["multi", "serial"])
def test_scaffold_single_child_helpers_keep_an_explicit_workspace_binding(kind):
    bindings = create_bindings(ExampleAdapter=NSGA2Adapter)
    registry = bindings.AdapterRegistry()
    inner, leaf = router(name="inner")
    if kind == "multi":
        assert bindings.multi(registry, "unbound", [inner]) is inner
        outer = bindings.multi(registry, "bound", [inner], working_pool="workspace")
        assert isinstance(outer, StrategyRouterAdapter)
    else:
        phases = [bindings.phase("inner", inner)]
        assert bindings.serial(registry, "unbound", phases) is inner
        outer = bindings.serial(registry, "bound", phases, working_pool="workspace")
        assert isinstance(outer, StrategyChainAdapter)
    assert outer is not inner
    assert outer.working_pool == "workspace"
    solver = build_solver(outer)
    refs = add_seeds(solver)
    solver.solution_pool.create_subpool("workspace", refs[2:4])
    assert solver.step().committed
    assert seed_sources(solver, leaf) == tuple(ref.candidate_token for ref in refs[2:4])
    assert solver.solution_pool.subpool_refs("workspace") == (
        *refs[2:4], *solver.solution_pool.select(stage="accepted"))


class OtherWorkspaceObservation(Plugin):
    """A live global projection must not rebind an existing child request."""

    context_provides = (KEY_SOLUTION_WORKING_POOL,)

    def on_context_build(self, context):
        return {**context, KEY_SOLUTION_WORKING_POOL:
                self.solver.solution_pool.subpool_descriptor("observation")}


def test_original_child_workspace_survives_global_context_observation_through_all_hooks(monkeypatch):
    group, leaf = router(working_pool="workspace")
    solver = build_solver(group)
    refs = add_seeds(solver)
    solver.solution_pool.create_subpool("workspace", refs[2:4])
    solver.solution_pool.create_subpool("observation", refs[:2])
    solver.add_plugin(OtherWorkspaceObservation("other_workspace"))
    assert solver.build_context()[KEY_SOLUTION_WORKING_POOL]["name"] == "observation"
    seen = {}
    for hook in ("get_proposal_contexts", "on_proposal_repair", "on_proposal_disposition", "update"):
        original = getattr(leaf, hook)

        def record(*args, _hook=hook, _original=original, **kwargs):
            context = kwargs.get("context", args[-1] if args else None)
            seen.setdefault(_hook, []).append(context[KEY_SOLUTION_WORKING_POOL]["name"])
            return _original(*args, **kwargs)

        monkeypatch.setattr(leaf, hook, record)
    assert solver.step().committed
    assert set(seen) == {"get_proposal_contexts", "on_proposal_repair", "on_proposal_disposition", "update"}
    assert all(values and set(values) == {"workspace"} for values in seen.values())
    assert seed_sources(solver, leaf) == tuple(ref.candidate_token for ref in refs[2:4])
    assert solver.solution_pool.subpool_refs("observation") == refs[:2]
    assert solver.solution_pool.subpool_refs("workspace") == (
        *refs[2:4], *solver.solution_pool.select(stage="accepted"))
