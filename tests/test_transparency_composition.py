"""组合透明性：真实调度、池交接与主动精英替换的行为证据。"""
import numpy as np
import pytest

from benchmarks.transparency_composition import (
    COMPOSITION_NAMES, CompositionReference, EliteReference, PoolSearchReference, PoolTaskReference,
    make_composition_adapter, make_elite_adapter, make_pool_search_adapter, make_pool_task_adapter,
    project_composition, project_elite, project_pool_search, project_pool_task,
)
from benchmarks.transparency_trajectory import make_trajectory_problem
from nsgablack.core import ComposableSolver


def fixture(kind, seed):
    evaluate = lambda row: (np.asarray([np.sum(np.asarray(row) ** 2)]), 0.0)
    if kind in COMPOSITION_NAMES:
        return (make_composition_adapter(seed, kind=kind), CompositionReference(kind, seed, evaluate),
                lambda solver: project_composition(solver, kind=kind),
                {"search_plan_serial": 4, "search_plan_multi": 3}.get(kind, 6))
    if kind == "elite_retention":
        return make_elite_adapter(seed), EliteReference(seed, evaluate), project_elite, 6
    if kind == "pool_task":
        return make_pool_task_adapter(seed), PoolTaskReference(seed, evaluate), project_pool_task, 4
    return make_pool_search_adapter(seed), PoolSearchReference(seed, evaluate), project_pool_search, 7


def assert_state_equal(actual, expected):
    if isinstance(actual, dict):
        assert actual.keys() == expected.keys()
        for key in actual:
            assert_state_equal(actual[key], expected[key])
    elif isinstance(actual, list):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            assert_state_equal(a, b)
    elif isinstance(actual, (float, np.floating)):
        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-14)
    else:
        assert actual == expected


@pytest.mark.parametrize("kind", [*COMPOSITION_NAMES, "elite_retention", "pool_task", "pool_search"])
@pytest.mark.parametrize("seed", [3, 17])
def test_composition_matches_bare_children_and_scheduler_after_every_commit(kind, seed):
    adapter, bare, project, steps = fixture(kind, seed)
    solver = ComposableSolver(make_trajectory_problem("sa"), adapter=adapter)
    solver.set_random_seed(seed)
    solver.setup()
    evaluation_count = 0
    for _ in range(steps):
        assert solver.step().committed
        reference = bare.step()
        evaluation_count += len(reference["candidates"])
        assert_state_equal(project(solver), reference["state"])
        assert solver.problem.evaluation_count == evaluation_count
    if kind == "pool_task":
        result = project(solver)
        assert result["accepted_history_count"] == 9
        assert len(result["selected_results"]) == 1
        assert result["scheduler"]["completed"]
    elif kind == "pool_search":
        result = project(solver)
        assert result["scheduler"]["phase"] == "search"
        assert result["scheduler"]["recovery_count"] == 2
        assert len(result["children"]["search"]["population"]) == 10


def test_search_plan_nested_reuses_children_and_waits_for_each_parallel_branch():
    _, reference, _, _ = fixture("search_plan_nested", 13)
    states = [reference.step()["state"] for _ in range(6)]
    assert states[0]["scheduler"]["active"] == [
        {"name": "sa", "label": "joint_sa", "count": 1, "steps": 2}]
    assert states[1]["scheduler"]["active"][0]["label"] == "solo_sample"
    assert states[2]["scheduler"]["active"][0]["count"] == 0
    assert states[-1]["scheduler"]["completed"]
    # SA receives four updates across two repeat cycles; it is not reinitialized.
    assert states[-1]["children"]["sa"]["temperature"] == pytest.approx(0.7 * 0.8 ** 3)


def test_bare_composition_and_wrappers_do_not_call_framework_composers(monkeypatch):
    from nsgablack.adapters import CompositeAdapter
    from nsgablack.adapters.multi_strategy import StrategyRouterAdapter
    from nsgablack.adapters.serial_strategy import StrategyChainAdapter
    from nsgablack.adapters.role_adapters import RoleAdapter, RoleRouterAdapter
    from nsgablack.adapters.search_plan import SearchPlanAdapter
    from nsgablack.adapters.pool_tasks import PoolTaskAdapter
    from nsgablack.adapters.pool_search import PoolSearchAdapter
    from nsgablack.adapters.elite_retention import EliteRetentionAdapter

    # Instantiate only the independent engines before disabling every framework
    # orchestration surface. Numeric leaf kernels have no framework references.
    evaluate = lambda row: (np.asarray([np.sum(np.asarray(row) ** 2)]), 0.0)
    references = [CompositionReference(kind, 7, evaluate) for kind in COMPOSITION_NAMES]
    references.extend([EliteReference(7, evaluate), PoolTaskReference(7, evaluate), PoolSearchReference(7, evaluate)])

    def forbidden(*args, **kwargs):
        raise AssertionError("bare orchestration called framework composer")

    for cls in (CompositeAdapter, StrategyRouterAdapter, StrategyChainAdapter, RoleAdapter,
                RoleRouterAdapter, SearchPlanAdapter, PoolTaskAdapter, PoolSearchAdapter, EliteRetentionAdapter):
        for method in ("propose", "update", "get_state", "set_state"):
            monkeypatch.setattr(cls, method, forbidden)
    for reference in references:
        for _ in range(3):
            assert reference.step()["candidates"]
