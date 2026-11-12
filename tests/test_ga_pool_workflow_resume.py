"""Formal checkpoints resume GA batch changes, Pool choice and member plans."""
from __future__ import annotations

import copy

import numpy as np

from nsgablack.adapters import ChangeResult, NSGA2Adapter
from nsgablack.adapters.change_batch import ChangeBatchResult
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.plugins.base import Plugin
from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer


class ResumeSphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-20., 20.)])
        self.calls = []

    def evaluate(self, candidate):
        values = np.array(candidate, dtype=float, copy=True)
        self.calls.append(values)
        return [float(np.dot(values, values))]


def crossover_pair(request, *, rng):
    """One calculation shares its perturbation between two independent children."""
    a, b = request.parents[:2]
    noise = rng.normal(0., .02, a.shape)
    return ChangeBatchResult((
        ChangeResult(.75 * a + .25 * b - .25 + noise, source_refs=request.source_refs),
        ChangeResult(.25 * a + .75 * b - .35 - noise, source_refs=request.source_refs),
    ))


def choose_four(pool):
    return pool.sort(lambda rows: rows.objectives[:, 0]).take(range(4))


def elite_score(pool):
    objectives, violations = pool.raw_feedback()
    return np.column_stack((violations > 0., np.maximum(violations, 0.), objectives[:, 0]))


def keep_current_elite(request, *, rng):
    del rng
    kept = request.pool.subpool("elite").merge(request.accepted).top(2, key=elite_score)
    return (request.pool.replace_members("elite", kept.refs),)


def capture(solver):
    adapter, pool = solver.adapter, solver.solution_pool
    return {
        "evaluations": solver.evaluation_count,
        "pool_refs": pool.select(stage=None),
        "initial_refs": pool.select(stage="initial"),
        "elite_refs": pool.subpool_refs("elite"),
        "elite_descriptor": pool.subpool_descriptor("elite"),
        "adapter_state": copy.deepcopy(adapter.get_state()),
        "bindings": copy.deepcopy(adapter.operator_bindings_state()),
        "rng": copy.deepcopy(adapter._rng.bit_generator.state),
        "unit_id": adapter.get_unit_id(),
    }


class EliteFixtureAndProbe(Plugin):
    """Create only the test collection; observe the post-restore public state."""

    def __init__(self):
        super().__init__("ga_resume_probe")
        self.created = 0
        self.at_init = None
        self.committed = []

    def on_solver_init(self, solver):
        if not solver.solution_pool.has_subpool("elite"):
            solver.solution_pool.create_subpool("elite")
            self.created += 1
        self.at_init = capture(solver)

    def on_generation_committed(self, generation, outcome):
        self.committed.append(capture(self.solver))


def make_solver(config):
    adapter = NSGA2Adapter(population_size=4, offspring_size=4,
        change=crossover_pair, selector=choose_four, pool_maintenance=keep_current_elite)
    solver = ComposableSolver(ResumeSphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(
            initializer=UniformInitializer(low=4., high=5.), repair=ClipRepair(low=-20., high=20.)))
    solver.set_random_seed(173)
    probe = EliteFixtureAndProbe()
    solver.add_plugin(probe)
    checkpoint = CheckpointResumePlugin(config=config)
    solver.add_plugin(checkpoint)
    return solver, probe, checkpoint


def test_formal_ga_pool_workflow_resume_keeps_saved_identity_and_deterministic_continuation(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "ga-pool-workflow-resume-test")
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_every=2,
                                  save_on_finish=False, strict=True)
    source, source_probe, _ = make_solver(config)
    initializations = []
    initializer = source.representation_pipeline.initializer
    initialize = initializer.initialize

    def track_initialize(problem, context=None):
        value = initialize(problem, context)
        initializations.append(np.array(value, copy=True))
        return value

    monkeypatch.setattr(initializer, "initialize", track_initialize)
    source.run(max_steps=3)
    assert source.run_progress_steps == 3
    assert len(initializations) == 4
    assert source_probe.created == 1
    assert len(source_probe.committed) == 3
    saved = source_probe.committed[1]
    assert saved["evaluations"] == 8
    assert len(saved["elite_refs"]) == 2
    assert set(saved["bindings"]) == {"change", "selector", "pool_maintenance"}
    checkpoint, = tuple(tmp_path.glob("*_g000001_*.pkl"))

    restored, restored_probe, reader = make_solver(config)
    assert restored.adapter is not source.adapter

    def do_not_initialize_again(*args, **kwargs):
        raise AssertionError("checkpoint continuation must not initialize GA seeds again")

    monkeypatch.setattr(restored.representation_pipeline.initializer,
                        "initialize", do_not_initialize_again)
    assert reader.resume(str(checkpoint))
    restored.run(max_steps=3)

    # Ordinary init hooks run after the restore envelope. Every pre-existing
    # version and the complete Unit/binding/RNG state must already be restored.
    assert restored_probe.created == 0
    assert restored_probe.at_init == saved
    assert len(restored_probe.committed) == 1
    assert restored.run_session.run_id == source.run_session.run_id
    assert restored.run_progress_steps == source.run_progress_steps == 3
    assert restored.evaluation_count == source.evaluation_count == 12
    np.testing.assert_array_equal(restored.problem.calls, source.problem.calls[saved["evaluations"]:])
    assert restored.solution_pool.select(stage="initial") == source.solution_pool.select(stage="initial")
    final_refs = restored.solution_pool.select(stage=None)
    assert final_refs[:len(saved["pool_refs"])] == saved["pool_refs"]
    assert restored.adapter.get_unit_id() == source.adapter.get_unit_id()
    assert restored.adapter.operator_bindings_state() == source.adapter.operator_bindings_state()
    assert restored.adapter._rng.bit_generator.state == source.adapter._rng.bit_generator.state
    np.testing.assert_array_equal(restored.adapter.population, source.adapter.population)
    np.testing.assert_array_equal(restored.adapter.objectives, source.adapter.objectives)
    np.testing.assert_array_equal(restored.adapter.violations, source.adapter.violations)

    # Independent continuations derive fresh proposal IDs. Their selected
    # values, raw feedback and stable collection identity must still coincide.
    actual = restored.solution_pool.subpool_refs("elite")
    expected = source.solution_pool.subpool_refs("elite")
    np.testing.assert_array_equal(restored.read_solutions(actual).numeric_matrix,
                                  source.read_solutions(expected).numeric_matrix)
    for left, right in zip(restored.solution_pool.read_raw_feedback(actual),
                           source.solution_pool.read_raw_feedback(expected), strict=True):
        np.testing.assert_array_equal(left, right)
    assert restored.solution_pool.subpool_descriptor("elite") == source.solution_pool.subpool_descriptor("elite")
    actual_population_refs = restored.adapter.get_population_solution_refs(restored)
    expected_population_refs = source.adapter.get_population_solution_refs(source)
    np.testing.assert_array_equal(restored.read_solutions(actual_population_refs).numeric_matrix,
                                  source.read_solutions(expected_population_refs).numeric_matrix)
    assert len({ref.candidate_token for ref in actual_population_refs}) == 4
