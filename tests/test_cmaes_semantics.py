"""CMA semantic checks: formulas, full cohorts, rollback and real checkpoint files."""
from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from blackbase.types import CandidateBatch, UnknownState

from nsgablack.adapters.cmaes import CMAESAdapter, CMAParameters, GaussianCohortSampler, StableObjectiveRanking
from nsgablack.adapters.proposal_repair import ProposalRepair
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.representation import RepresentationPipeline


PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/algorithm_semantics"


class Quadratic(BlackBoxProblem):
    def __init__(self, dimension=1):
        super().__init__(dimension=dimension, objectives=["min"], bounds=[(-100, 100)] * dimension)
        self.calls = []

    def evaluate(self, candidate):
        values = np.asarray(candidate, dtype=float)
        self.calls.append(values.copy())
        target = [1.] if len(values) == 1 else [.2, -.1]
        return [float(np.sum((values - target) ** 2))]


def scalar_adapter(**options):
    return CMAESAdapter([0.], sigma=1.,
        parameters=CMAParameters(weights=(.5, .5), cc=.5, cs=.5, c1=.25, cmu=.25, damping=1.),
        sampler=GaussianCohortSampler(19, fixed_batches=([[[-1.], [0.], [1.], [2.]]])), **options)


def normalized(adapter):
    return json.loads(json.dumps(adapter.get_state(), default=lambda item: item.tolist()))


def test_scalar_exact_distribution_and_four_observations_two_parents():
    a = scalar_adapter()
    s = ComposableSolver(Quadratic(), adapter=a)
    s.setup()
    assert a.algorithm_unit is None
    assert s.step().committed
    u = a.algorithm_unit
    assert len(s.problem.calls) == s.evaluation_count == 4
    assert len(u.last_cohort["refs"]) == 4
    assert u.last_cohort["selected_indices"] == (2, 1)
    np.testing.assert_allclose(u.mean, [.5], rtol=0, atol=1e-14)
    np.testing.assert_allclose(u.path_c, [math.sqrt(6)/4], rtol=0, atol=1e-14)
    np.testing.assert_allclose(u.path_sigma, u.path_c, rtol=0, atol=1e-14)
    np.testing.assert_allclose(u.covariance, [[23/32]], rtol=0, atol=1e-14)
    assert u.sigma == pytest.approx(math.exp(.5 * ((math.sqrt(6)/4)/math.sqrt(2/math.pi) - 1)))
    assert u.last_cohort["h_sigma"] == 1 and u.iteration == 1
    np.testing.assert_array_equal(a.get_current_candidates()[0], [1.])
    assert not np.array_equal(a.get_current_candidates()[0], u.mean)
    assert len(s.solution_pool.read(tuple(a.get_solution_pool_roots(s))).semantic_states) == 4


def test_two_dimensional_covariance_update_has_independent_matrix_expectation():
    a = CMAESAdapter([0., 0.], sigma=.5,
        sampler=GaussianCohortSampler(3, fixed_batches=([[[-1., 0.], [0., 1.], [1., 0.], [0., -1.]]])))
    s = ComposableSolver(Quadratic(2), adapter=a)
    s.setup()
    assert s.step().committed
    u = a.algorithm_unit
    np.testing.assert_array_equal(u.last_cohort["ranking"], [2, 3, 1, 0])
    w = np.log([2.5, 1.25]); w /= w.sum()
    eff, n = 1/np.sum(w*w), 2
    cc = (4+eff/n)/(n+4+2*eff/n)
    cs = (eff+2)/(n+eff+5)
    c1 = 2/((n+1.3)**2+eff)
    cmu = min(1-c1, 2*(eff-2+1/eff)/((n+2)**2+eff))
    yw = np.array([w[0], -w[1]])
    ps = np.sqrt(cs*(2-cs)*eff)*yw
    pc = np.sqrt(cc*(2-cc)*eff)*yw
    expected = (1-c1-cmu)*np.eye(2) + c1*np.outer(pc, pc) + cmu*np.diag(w)
    np.testing.assert_allclose(u.mean, .5*yw, atol=1e-14)
    np.testing.assert_allclose(u.path_sigma, ps, atol=1e-14)
    np.testing.assert_allclose(u.path_c, pc, atol=1e-14)
    np.testing.assert_allclose(u.covariance, expected, atol=1e-14)
    damping = 1 + 2*max(0, np.sqrt((eff-1)/(n+1))-1)+cs
    assert u.sigma == pytest.approx(.5*np.exp(cs/damping*(np.linalg.norm(ps)/np.sqrt(np.pi/2)-1)))
    assert abs(u.covariance[0, 1]) > 1e-4
    assert np.min(np.linalg.eigvalsh(u.covariance)) > 0


def test_sampling_uses_full_nondiagonal_covariance():
    c = np.array([[2., .5], [.5, 1.]])
    z = np.array([[-1., 0.], [0., 1.], [1., 0.], [0., -1.]])
    a = CMAESAdapter([.1, -.2], sigma=.4, covariance=c,
        sampler=GaussianCohortSampler(3, fixed_batches=(z,)))
    s = ComposableSolver(Quadratic(2), adapter=a)
    s.setup()
    assert s.step().committed
    # Closed 2x2 SPD square root, independent of the implementation's eigensolver.
    determinant_root = np.sqrt(np.linalg.det(c))
    root = (c + determinant_root*np.eye(2))/np.sqrt(np.trace(c)+2*determinant_root)
    expected = np.array([.1, -.2]) + .4*(z @ root.T)
    np.testing.assert_allclose(s.problem.calls, expected, atol=1e-14)
    np.testing.assert_allclose(a.algorithm_unit.last_cohort["offsets"], z @ root.T, atol=1e-14)
    np.testing.assert_array_equal(a.algorithm_unit.last_cohort["source_distribution"]["covariance"], c)


def test_assembly_and_inspection_do_not_construct_a_unit(monkeypatch):
    from nsgablack.units.cmaes import CMAUnit
    def forbidden(*args, **kwargs):
        raise AssertionError("inspection created a runtime Unit")
    monkeypatch.setattr(CMAUnit, "__init__", forbidden)
    a = scalar_adapter()
    assert a.algorithm_unit is None
    assert a.get_state()["algorithm_unit"] is None
    assert a.get_unit_alignment()["primary"]["requires"]["name"] == "nsgablack.cma_distribution"


class ShiftRepair:
    def repair(self, candidate, context=None):
        return np.asarray(candidate) + .1


def test_changed_repair_rejected_before_problem_and_restores_rng_absent_unit():
    a = scalar_adapter()
    s = ComposableSolver(Quadratic(), adapter=a, representation_pipeline=RepresentationPipeline(repair=ShiftRepair()))
    s.setup()
    before = normalized(a)
    with pytest.raises(ValueError, match="changed repair"):
        s.step()
    assert not s.problem.calls and s.evaluation_count == 0
    assert normalized(a) == before and a.algorithm_unit is None


def test_metadata_only_repair_is_rejected():
    a = scalar_adapter()
    a.propose(None, {})
    before = CandidateBatch.from_candidates([UnknownState([0.], {"domain": "a"})], candidate_tokens=("token",))
    after = CandidateBatch.from_candidates([UnknownState([0.], {"domain": "b"})], candidate_tokens=("token",))
    with pytest.raises(ValueError, match="changed repair"):
        a.on_proposal_repair(None, ProposalRepair(4, (0,), before, after), {})


@pytest.mark.parametrize("mode,count", [("budget", 3), ("admission", 4)])
def test_partial_cohort_rejects_without_changing_lambda_and_retains_real_cost(mode, count):
    a = scalar_adapter()
    s = ComposableSolver(Quadratic(), adapter=a)
    if mode == "budget":
        s.register_controller(BudgetController(max_evaluations=3))
    else:
        class AcceptTwo:
            policy_id = "test.accept.two"
            def select(self, candidates, feedback, context):
                return BatchDisposition(4, (0, 2))
        s.set_evaluation_acceptance_policy(AcceptTwo())
    s.setup()
    before = normalized(a)
    with pytest.raises(ValueError, match="incomplete cohort"):
        s.step()
    assert len(s.problem.calls) == s.evaluation_count == count
    assert normalized(a) == before and a.algorithm_unit is None
    assert a.parameters.population_size == 4
    assert s.get_population_authority_identity() is None
    assert s.evaluation_evidence_journal.list_records()


def test_failure_after_computed_update_rolls_distribution_rng_pool_and_authority_back():
    class FailingCMA(CMAESAdapter):
        def update(self, *args, **kwargs):
            super().update(*args, **kwargs)
            raise RuntimeError("injected after distribution update")
    base = scalar_adapter()
    a = FailingCMA([0.], sigma=1., parameters=base.parameters, sampler=base.sampler)
    s = ComposableSolver(Quadratic(), adapter=a)
    s.setup()
    before = normalized(a)
    with pytest.raises(RuntimeError, match="injected after distribution"):
        s.step()
    assert normalized(a) == before
    assert s.evaluation_count == len(s.problem.calls) == 4
    assert s.get_population_authority_identity() is None
    assert s.solution_pool.publication_ref() is None


def test_failure_preserves_already_published_distribution_and_pool(monkeypatch):
    a = scalar_adapter()
    s = ComposableSolver(Quadratic(), adapter=a)
    s.setup()
    assert s.step().committed
    state, authority, publication = normalized(a), s.get_population_authority_identity(), s.solution_pool.publication_ref()
    population = s.population.copy()
    update = a.update
    def fail_after_update(*args, **kwargs):
        update(*args, **kwargs)
        raise RuntimeError("fault before authority publication")
    monkeypatch.setattr(a, "update", fail_after_update)
    with pytest.raises(RuntimeError, match="fault before authority"):
        s.step()
    assert normalized(a) == state
    assert s.get_population_authority_identity() == authority
    assert s.solution_pool.publication_ref() == publication
    np.testing.assert_array_equal(s.population, population)
    assert s.evaluation_count == len(s.problem.calls) == 8
    assert len(a.algorithm_unit.last_cohort["refs"]) == 4


def test_stateful_ranking_requires_and_uses_explicit_component_codec():
    class CountingRanking(StableObjectiveRanking):
        stateless = False
        checkpoint_identity = {"schema": "test.counting_raw_rank/v1"}
        def __init__(self):
            self.reset()
        def reset(self):
            self.calls = 0
        def rank(self, feedback):
            self.calls += 1
            return super().rank(feedback)
        def get_state(self):
            return {"calls": self.calls}
        def set_state(self, state):
            self.calls = state["calls"]
    ranking = CountingRanking()
    a = scalar_adapter(ranking=ranking)
    s = ComposableSolver(Quadratic(), adapter=a)
    s.setup()
    assert s.step().committed and ranking.calls == 1
    saved = a.get_state()
    target_rank = CountingRanking()
    target = scalar_adapter(ranking=target_rank)
    target.set_state(saved)
    assert target_rank.calls == 1
    assert normalized(target) == normalized(a)
    class NoCodec:
        checkpoint_identity = {"schema": "test.unowned_rank/v1"}
        rank = ranking.rank
    with pytest.raises(TypeError, match="Stateful CMA components"):
        scalar_adapter(ranking=NoCodec())


def test_two_cma_instances_cannot_share_a_stateful_sampler():
    from nsgablack.adapters.algorithm_adapter import CompositeAdapter
    shared = GaussianCohortSampler(19)
    a = CMAESAdapter([0.], sampler=shared, name="left")
    b = CMAESAdapter([0.], sampler=shared, name="right")
    s = ComposableSolver(Quadratic(), adapter=CompositeAdapter([a, b]))
    before = shared.get_state()
    with pytest.raises(ValueError, match="multiple Adapter owners"):
        s.setup()
    assert shared.get_state() == before
    assert a.algorithm_unit is b.algorithm_unit is None
    assert not s.problem.calls


def test_independent_cma_samplers_can_share_stateless_ranking():
    from nsgablack.adapters.algorithm_adapter import CompositeAdapter
    shared = StableObjectiveRanking()
    a = CMAESAdapter([0.], ranking=shared, name="left")
    b = CMAESAdapter([0.], ranking=shared, name="right")
    s = ComposableSolver(Quadratic(), adapter=CompositeAdapter([a, b]))
    s.setup()
    assert a.ranking is b.ranking
    assert a.sampler is not b.sampler
    assert a.algorithm_unit is b.algorithm_unit is None


def test_absent_unit_checkpoint_stays_absent_and_configuration_change_is_rejected():
    source = scalar_adapter()
    saved = source.get_state()
    target = scalar_adapter()
    target.set_state(saved)
    assert target.algorithm_unit is None
    other = CMAESAdapter([0.], sigma=.25)
    with pytest.raises(ValueError, match="configuration"):
        other.set_state(saved)
    assert other.algorithm_unit is None


@pytest.fixture
def grant():
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1), owner_id="cma_semantics", scope="optimization")
    try:
        yield ResourceContext.from_mapping(lease.resource_context(namespace="algorithm_semantics"))
    finally:
        allocator.release(lease)


def assemble(grant, output, **config):
    return build_case(load_case_builder(PROJECT, "cmaes_distribution"), resource_context=grant,
        component_overrides={"config": {"output_dir": str(output), **config}})


def test_standard_case_runs_real_random_sampler_and_publishes_summary(tmp_path, grant):
    s = assemble(grant, tmp_path)
    assert s.adapter.algorithm_unit is None
    run_case(s)
    report = json.loads((tmp_path/"summary.json").read_text(encoding="utf-8"))
    assert report["evaluations"] == report["problem_calls"] == 12
    assert report["logical_steps"] == report["iteration"] == 3
    assert report["cohort_count"] == 4 and len(report["selected_indices"]) == 2
    assert s.resource_binding_audit["current"]
    assert list((tmp_path/"checkpoints").glob("*.pkl"))


def test_public_checkpoint_file_resume_matches_full_distribution_and_next_samples(tmp_path, grant):
    source = assemble(grant, tmp_path)
    run_case(source)
    checkpoint, = (tmp_path/"checkpoints").glob("*_g000000_*.pkl")
    target = assemble(grant, tmp_path)
    assert target.get_plugin("checkpoint_resume").resume(str(checkpoint))
    run_case(target)
    a, b = source.adapter.algorithm_unit, target.adapter.algorithm_unit
    assert target.evaluation_count == source.evaluation_count == 12
    assert len(target.problem.calls) == 8
    for field in ("mean", "covariance", "path_c", "path_sigma"):
        np.testing.assert_array_equal(getattr(a, field), getattr(b, field))
    assert a.sigma == b.sigma and a.iteration == b.iteration
    np.testing.assert_array_equal(a.last_cohort["candidates"], b.last_cohort["candidates"])
    assert source.adapter.sampler.get_state() == target.adapter.sampler.get_state()
