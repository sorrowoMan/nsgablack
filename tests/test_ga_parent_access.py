"""Exact parent references cannot bypass an enclosing PoolTask donor scope."""
import copy

import numpy as np
import pytest
from blackbase.types import CandidateBatch

from nsgablack.adapters import (MultiStrategyConfig, NSGA2Adapter, PoolTaskSpec,
                               RoleSpec, StrategyRouterAdapter)
from nsgablack.adapters.change_access import current_change_access, scoped_change_access
from nsgablack.adapters.parent_selection import MixedPoolParentSelector
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.representation import RepresentationPipeline, UniformInitializer


class ParentScopeProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-100., 100.)])
        self.calls = []

    def evaluate(self, candidate):
        self.calls.append(np.array(candidate, copy=True))
        return [float(candidate[0] ** 2)]


def seed_refs(control, context):
    return control.solution_pool.select(stage=None, source="seed")


def from_selected_parent(request, *, rng):
    del rng
    return request.candidate - 1.


def build_task(*, sources=(), allow_main=False, complete_change=True):
    inner = NSGA2Adapter(population_size=4, offspring_size=2,
        parent_selector=MixedPoolParentSelector("elite", 1.),
        change=from_selected_parent if complete_change else None)
    router = StrategyRouterAdapter(roles=[RoleSpec("ga", inner,
        pool_task=PoolTaskSpec(seed_refs, mode="initialize", count=4, shuffle=False,
            change_sources=sources, change_allow_main=allow_main))],
        config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False))
    solver = ComposableSolver(ParentScopeProblem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(low=4., high=4.)))
    solver.setup()
    solver.store_solutions(CandidateBatch.from_candidates([[4.], [5.], [6.], [7.]],
        candidate_tokens=("s0", "s1", "s2", "s3")), source="seed")
    refs = solver.store_solutions(CandidateBatch.from_candidates([[0.]], candidate_tokens=("elite",)),
                                  source="donor")
    solver.solution_pool.create_subpool("elite", refs)
    return solver, inner, refs


@pytest.mark.parametrize("complete_change", (True, False))
def test_task_parent_selector_cannot_import_an_undeclared_pool(complete_change):
    solver, inner, _ = build_task(complete_change=complete_change)
    assert solver.step().committed
    before = inner.get_population_solution_refs(solver)
    before_rng = copy.deepcopy(inner._rng.bit_generator.state)
    before_values = np.array(inner.population, copy=True)
    assert len(solver.problem.calls) == 4
    with pytest.raises(ValueError, match="declared inputs"):
        solver.step()
    assert len(solver.problem.calls) == 4
    assert inner.get_population_solution_refs(solver) == before
    np.testing.assert_array_equal(inner.population, before_values)
    assert inner._rng.bit_generator.state == before_rng
    assert current_change_access() is None


@pytest.mark.parametrize("complete_change", (True, False))
@pytest.mark.parametrize("permission", ("named", "main"))
def test_declared_named_or_main_scope_allows_exact_external_ga_parents(complete_change, permission):
    solver, _, refs = build_task(sources=("elite",) if permission == "named" else (),
        allow_main=permission == "main", complete_change=complete_change)
    assert solver.step().committed and solver.step().committed
    assert len(solver.problem.calls) == 6
    key = "change_source_refs" if complete_change else "parent_solution_refs"
    for provenance in solver._last_evaluated_event_provenance:
        exact = tuple(SolutionRef.from_dict(dict(value)) for value in provenance.metadata[key])
        assert exact == (refs[0], refs[0])
    assert current_change_access() is None


def test_nested_scope_cannot_reenable_named_ga_parent_donors():
    solver, inner, _ = build_task(sources=("elite",))
    assert solver.step().committed
    before = inner.get_population_solution_refs(solver)
    with scoped_change_access((), subpools=("other",)):
        with pytest.raises(ValueError, match="declared inputs"):
            solver.step()
    assert inner.get_population_solution_refs(solver) == before
    assert len(solver.problem.calls) == 4
    assert current_change_access() is None


@pytest.mark.parametrize("complete_change", (True, False))
def test_unused_declared_future_donor_does_not_block_existing_parent_sources(complete_change):
    solver, _, _ = build_task(sources=("elite", "not-yet-created"),
                              complete_change=complete_change)
    assert solver.step().committed and solver.step().committed
    assert len(solver.problem.calls) == 6
    assert not solver.solution_pool.has_subpool("not-yet-created")
