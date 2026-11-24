"""Independent pymoo oracles for mathematical selection, not framework mirrors."""
from copy import deepcopy
import numpy as np
import pytest

pytest.importorskip("pymoo")

from nsgablack.adapters import NSGA2Adapter, NSGA3Adapter, MOEADAdapter
from nsgablack.utils.performance.fast_non_dominated_sort import FastNonDominatedSort


@pytest.mark.parametrize("case", ["random", "constant", "collinear", "scaled", "constrained"])
@pytest.mark.parametrize("seed", [3, 17, 29])
def test_nsga3_survival_and_persistent_normalization_match_independent_pymoo(case, seed):
    from pymoo.algorithms.moo.nsga3 import ReferenceDirectionSurvival
    from pymoo.core.population import Population
    from pymoo.core.problem import Problem
    from pymoo.util.ref_dirs import get_reference_directions
    refs = get_reference_directions("das-dennis", 3, n_partitions=3)
    oracle = ReferenceDirectionSurvival(refs)
    adapter = NSGA3Adapter(population_size=12, divisions=3)
    adapter.reference_points = refs.copy()
    adapter._rng = np.random.default_rng(seed)
    rng = np.random.default_rng(seed)
    data_rng = np.random.default_rng(seed+100)
    for generation in range(3):
        f = data_rng.random((40, 3))
        if case == "constant": f[:] = 1.
        if case == "collinear": f = np.tile(np.linspace(0., 1., 40)[:,None], (1,3))
        if case == "scaled": f *= [1., 1e3, 1e6]
        v = np.zeros(40)
        if case == "constrained": v[10:] = data_rng.uniform(.1, 2., 30)
        population = Population.new("F", f, "CV", v[:,None], "row_id", np.arange(len(f)))
        expected = oracle.do(Problem(n_obj=3,n_ieq_constr=1), population,n_survive=12,random_state=rng)
        actual = adapter._environmental_select(f,v,12)
        np.testing.assert_array_equal(actual, expected.get("row_id"))
        for name, value in (("ideal",oracle.norm.ideal_point),("worst",oracle.norm.worst_point),
                            ("extremes",oracle.norm.extreme_points),("nadir",oracle.norm.nadir_point)):
            np.testing.assert_allclose(adapter.normalization[name],value,rtol=1e-12,atol=1e-12)


def test_reference_association_uses_lines_not_endpoints():
    from nsgablack.adapters.nsga3.normalization import associate
    refs = np.array([[1.,0.],[.5,.5]])
    f = np.array([[100.,10.]])
    niche, distance = associate(f,refs,{"ideal":np.zeros(2),"nadir":np.ones(2)})
    assert niche.tolist() == [0]
    assert distance[0] == pytest.approx(10.)


@pytest.mark.parametrize("objectives",[5,8])
def test_nsga3_many_objective_survival_matches_reference(objectives):
    from pymoo.algorithms.moo.nsga3 import ReferenceDirectionSurvival
    from pymoo.core.population import Population
    from pymoo.core.problem import Problem
    from pymoo.util.ref_dirs import get_reference_directions
    refs=get_reference_directions("das-dennis",objectives,n_partitions=2)
    native=NSGA3Adapter(divisions=2)
    native.reference_points=refs.copy()
    native._rng=np.random.default_rng(71)
    external=ReferenceDirectionSurvival(refs)
    rng=np.random.default_rng(71)
    for index in range(3):
        f=np.random.default_rng(index).random((50,objectives))
        pop=Population.new("F",f,"CV",np.zeros((50,1)),"row_id",np.arange(50))
        expected=external.do(Problem(n_obj=objectives),pop,n_survive=16,random_state=rng)
        np.testing.assert_array_equal(native._environmental_select(f,np.zeros(50),16),expected.get("row_id"))


def test_all_infeasible_selection_does_not_invent_normalization_history():
    native=NSGA3Adapter()
    f=np.random.default_rng(1).random((10,3))
    v=np.arange(10,0,-1,dtype=float)
    np.testing.assert_array_equal(native._environmental_select(f,v,4),[9,8,7,6])
    assert not native.normalization


@pytest.mark.parametrize("seed",range(5))
def test_nsga2_fronts_and_crowding_survival_match_independent_implementation(seed):
    from pymoo.operators.survival.rank_and_crowding import RankAndCrowding
    from pymoo.core.population import Population
    from pymoo.core.problem import Problem
    f = np.random.default_rng(seed).random((70,3))
    actual = NSGA2Adapter()._environmental_select(f,np.zeros(70),30)
    pop = Population.new("F",f,"CV",np.zeros((70,1)),"row_id",np.arange(70))
    expected = RankAndCrowding().do(Problem(n_obj=3),pop,n_survive=30,random_state=np.random.default_rng(seed))
    # Infinite crowding ties can legitimately select different boundary rows.
    # Every choice must nevertheless have the oracle rank/crowding cutoff.
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
    from pymoo.operators.survival.rank_and_crowding.metrics import calc_crowding_distance
    fronts, rank = NonDominatedSorting().do(f, return_rank=True)
    crowding = np.zeros(len(f))
    for front in fronts:
        crowding[front] = calc_crowding_distance(f[front])
    cutoff_rank = rank[expected.get("row_id")].max()
    assert set(np.flatnonzero(rank < cutoff_rank)).issubset(set(actual))
    assert np.all(rank[actual] <= cutoff_rank)
    last = actual[rank[actual] == cutoff_rank]
    oracle_last = expected.get("row_id")[rank[expected.get("row_id")] == cutoff_rank]
    assert len(last) == len(oracle_last)
    assert np.all(crowding[last] >= np.min(crowding[oracle_last]) - 1e-12)


def test_moead_tchebycheff_and_neighborhood_replacement_match_independent_decomposition():
    from pymoo.decomposition.tchebicheff import Tchebicheff
    rng = np.random.default_rng(42)
    a = MOEADAdapter(population_size=20)
    a.ideal = np.array([-1., -2.])
    a.weights = rng.dirichlet(np.ones(2), size=20)
    a.pop_F = rng.random((20,2))
    a.pop_V = np.zeros(20)
    for child in rng.random((15,2)):
        expected_old = Tchebicheff().do(a.pop_F,weights=a.weights,ideal_point=a.ideal).reshape(-1)
        expected_child = Tchebicheff().do(child[None,:],weights=a.weights,ideal_point=a.ideal).reshape(-1)
        for j in range(20):
            assert a._is_better_for_subproblem(child,0.,j) == (expected_child[j] < expected_old[j])


def test_nsga3_normalization_is_unit_owned_and_rejects_legacy_binding():
    a = NSGA3Adapter(divisions=3)
    a._environmental_select(np.random.default_rng(17).random((40,3)),np.zeros(40),12)
    saved = a.get_state()
    clone = NSGA3Adapter(divisions=3)
    clone.set_state(deepcopy(saved))
    for key in a.normalization:
        np.testing.assert_array_equal(a.normalization[key],clone.normalization[key])
    assert a.normalization is a.algorithm_unit.normalization
    assert a.unit_schema.version == 2
    incompatible = deepcopy(saved)
    incompatible["unit_contract"]["schema"]["version"] = 1
    with pytest.raises(ValueError,match="binding/schema"):
        clone.set_state(incompatible)


@pytest.mark.parametrize("name",["nsga3_zdt1","nsga3_dtlz2"])
def test_nsga3_new_normalization_rolls_back_and_restores_durable_evidence(name,tmp_path):
    from benchmarks.transparency_registry import by_name
    from benchmarks.transparency_faults import run_fault_checks
    report = run_fault_checks(by_name(name),seed=11,work_dir=tmp_path)
    assert report["status"] == "passed", report
