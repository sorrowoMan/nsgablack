"""Production cooperation must hand exact candidates through the shared runtime."""
from __future__ import annotations

import copy
from types import SimpleNamespace

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline
from examples.cases.production_scheduling.cases.production_scheduling.adapter.directional import (
    build_directional_adapter,
)
from tests.test_search_plan_pool_tasks import task_wrappers


class FourAxisProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["quantity", "stability", "fullness", "continuity"],
                         bounds=[(0.0, 20.0)])
        self.calls = []
        self.fail_next = False

    def get_num_objectives(self):
        return 4

    def evaluate(self, candidate):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("evaluation interruption")
        value = float(candidate[0])
        self.calls.append(value)
        return [100000.0 * value ** 2, value ** 2, value / 10.0, value / 20.0]


class HalfStep:
    context_requires = ("vns_k",)

    def initialize(self, problem, context):
        return np.array([10.25])

    def mutate(self, candidate, context):
        return candidate - 0.65

    def repair(self, candidate, context):
        # Proposals really change before evaluation, including VNS neighbors.
        return np.maximum(0.0, np.floor(candidate * 2.0) / 2.0)


class KeepFirst:
    def select(self, candidates, feedback, context):
        return BatchDisposition(len(candidates.semantic_states), (0,))


def parameters(**changes):
    values = dict(quality_cycles=2, explore_steps=1, refine_steps=2, refine_directions=0,
                  objective_output_scale=100000.0, pop_size=8, moead_pop_size=4,
                  moead_neighborhood=2, moead_delta=0.9, moead_nr=2,
                  vns_batch_size=2, vns_k_max=2, vns_base_sigma=0.2, seed=42)
    values.update(changes)
    return SimpleNamespace(**values)


def build(**options):
    problem = FourAxisProblem()
    plan = build_directional_adapter(problem, parameters(**options))
    operator = HalfStep()
    solver = ComposableSolver(problem, adapter=plan,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator, repair=operator))
    solver.set_random_seed(42)
    solver.setup()
    return solver, plan


def test_every_direction_gets_a_repaired_seed_and_returns_once_per_round():
    solver, plan = build()
    tasks = task_wrappers(plan)
    moead, local = tasks["moead"].inner, tasks["local"].inner
    assert solver.step().committed
    unit = moead.algorithm_unit
    requests = set()
    returns = []
    for _ in range(30):
        if plan.cursor.completed:
            break
        assert solver.step().committed
        assert moead.algorithm_unit is unit
        if tasks["local"].task_status["request"]:
            requests.add(tasks["local"].task_status["request"])
        if tasks["moead"].task_status["status"] == "done":
            item = (tasks["moead"].task_status["request"], tasks["moead"].task_status["count"])
            if item not in returns:
                returns.append(item)
    assert plan.cursor.completed
    assert len(requests) == len(returns) == 2
    assert [count for _request, count in returns] == [4, 4]
    assert local.cfg.restart_on_stagnation is False
    assert moead.pop_F.shape == (4, 4)
    for candidate, recorded in zip(moead.pop_X, moead.pop_F, strict=True):
        np.testing.assert_allclose(recorded, solver.problem.evaluate(candidate))
    # Scalar direction feedback never overwrites the source four objectives.
    refs = moead.get_population_solution_refs(solver)
    raw, violations = solver.solution_pool.read_raw_feedback(refs)
    np.testing.assert_allclose(raw, moead.pop_F)
    assert np.all(violations == 0)
    assert all(float(value * 2).is_integer() for value in solver.problem.calls)


def test_failed_refinement_restores_task_and_partial_admission_keeps_alignment():
    solver, plan = build(quality_cycles=1)
    assert solver.step().committed  # Full initial MOEA/D population.
    assert solver.step().committed  # First direction's seed baseline.
    tasks = task_wrappers(plan)
    before = copy.deepcopy(tasks["local"].task_status)
    adapter_before = copy.deepcopy(plan.get_state())
    accepted = solver.solution_pool.select(stage="accepted")
    steps = solver.run_progress_steps
    solver.problem.fail_next = True
    with pytest.raises(RuntimeError, match="evaluation interruption"):
        solver.step()
    assert tasks["local"].task_status == before
    np.testing.assert_equal(plan.get_state(), adapter_before)
    assert solver.solution_pool.select(stage="accepted") == accepted
    assert solver.run_progress_steps == steps
    solver.set_evaluation_acceptance_policy(KeepFirst())
    for _ in range(20):
        if plan.cursor.completed:
            break
        assert solver.step().committed
    assert plan.cursor.completed
    assert len(tasks["local"].get_pool_task_results(solver)) == 4
    assert tasks["moead"].task_status["count"] == 4
    assert tasks["moead"].inner.pop_F.shape == (4, 4)


def test_checkpoint_resumes_the_frozen_direction_request_without_reinitialization():
    source, source_plan = build(quality_cycles=1)
    assert source.step().committed
    assert source.step().committed
    before = copy.deepcopy(task_wrappers(source_plan)["local"].task_status)
    historical = source.solution_pool.select()
    target, target_plan = build(quality_cycles=1)
    assert not target.problem.calls
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.cfg.strict = reader.cfg.strict = True
    writer.attach(source)
    reader.attach(target)
    reader._restore_payload(solver=target,
        payload=writer._build_payload(solver=source, reason="production-direction-task"))
    restored = task_wrappers(target_plan)["local"]
    assert restored.task_status == before
    assert target.solution_pool.select() == historical
    assert not target.problem.calls
    while not target_plan.cursor.completed:
        assert target.step().committed
    assert restored.task_status["request"] == before["request"]
    assert task_wrappers(target_plan)["moead"].task_status["count"] == 4
    assert len(restored.get_pool_task_results(target)) == 4
