import numpy as np
import pytest


def baseline_solver():
    from nsgablack.adapters import SimulatedAnnealingAdapter
    from nsgablack.core import BlackBoxProblem, ComposableSolver
    from nsgablack.representation import RepresentationPipeline

    class Sphere(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=1, objectives=["minimize"], bounds=[(-20., 20.)])
            self.calls = []
        def evaluate(self, x):
            self.calls.append(float(x[0]))
            return [float(x[0] ** 2)]

    class Operator:
        mutations = 0
        def initialize(self, problem, context):
            return np.array([0.])
        def mutate(self, candidate, context):
            self.mutations += 1
            return candidate + 10.

    problem, operator = Sphere(), Operator()
    adapter = SimulatedAnnealingAdapter(batch_size=3, initial_temperature=1e-3, min_temperature=1e-6,
                                        cooling_rate=0.5, random_seed=1)
    solver = ComposableSolver(problem, adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.setup()
    return solver, operator


def test_initial_baseline_is_evaluated_before_neighbors_and_not_cooled():
    solver, operator = baseline_solver()
    assert solver.step().committed
    assert solver.problem.calls == [0.]
    assert operator.mutations == 0
    assert solver.adapter.current_score == 0.
    np.testing.assert_array_equal(solver.adapter.current_x, [0.])
    assert solver.adapter.temperature == 1e-3
    assert solver.step().committed
    assert solver.problem.calls == [0., 10., 10., 10.]
    assert operator.mutations == 3
    # A worse first neighbor must obey Metropolis instead of having delta=0.
    np.testing.assert_array_equal(solver.adapter.current_x, [0.])
    assert solver.adapter.current_score == 0.
    assert solver.adapter.temperature == 5e-4


def test_baseline_uses_repaired_candidate_and_admission_without_hidden_evaluation():
    from blackbase.contracts import BatchDisposition
    solver, operator = baseline_solver()
    class Repair:
        def repair(self, candidate, context):
            return np.array([1.])
    solver.representation_pipeline.set_repair(Repair())
    class Reject:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())
    solver.set_evaluation_acceptance_policy(Reject())
    outcome = solver.step()
    assert not outcome.committed
    assert solver.adapter.current_score is None
    assert operator.mutations == 0
    assert solver.adapter.temperature == 1e-3
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert operator.mutations == 0
    assert solver.adapter.current_score == solver.adapter.current_x[0] ** 2
    np.testing.assert_array_equal(solver.adapter.current_x, [1.])
    assert len(solver.problem.calls) == 2


def test_baseline_failure_rolls_back_score_but_keeps_evaluation_cost(monkeypatch):
    solver, operator = baseline_solver()
    monkeypatch.setattr(solver, "_update_best", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fail")))
    with pytest.raises(RuntimeError, match="fail"):
        solver.step()
    assert solver.adapter.current_x is None and solver.adapter.current_score is None
    assert solver.problem.calls == [0.]
    assert operator.mutations == 0


def test_baseline_checkpoint_restore_does_not_rescore_initial_state(tmp_path, monkeypatch):
    from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "sa-baseline-test-key")
    solver, _ = baseline_solver()
    assert solver.step().committed
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False)
    plugin = CheckpointResumePlugin(config=config)
    solver.add_plugin(plugin)
    path = plugin.save_checkpoint(reason="sa-baseline")
    restored, operator = baseline_solver()
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)
    assert reader.resume(str(path))
    restored.run(max_steps=0)
    assert restored.problem.calls == [] and operator.mutations == 0
    np.testing.assert_array_equal(restored.adapter.current_x, [0.])
    assert restored.adapter.current_score == 0.


def test_simulated_annealing_adapter_runs_and_cools(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.6, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    cfg = SAConfig(
        batch_size=2,
        initial_temperature=8.0,
        cooling_rate=0.95,
        min_temperature=1e-4,
        base_sigma=0.6,
        sigma_temperature_scale=1.0,
    )

    solver = ComposableSolver(problem=sample_problem, adapter=SimulatedAnnealingAdapter(cfg), representation_pipeline=pipeline)
    solver.set_random_seed(123)
    solver.max_steps = 60
    solver.run()

    assert solver.best_objective is not None
    # sphere objective is >=0; we only assert it improves to a reasonable range (avoid flakiness)
    assert solver.best_objective < 20.0
    ctx = solver.get_context()
    assert "temperature" in ctx
    assert float(ctx["temperature"]) < float(cfg.initial_temperature)


def test_sa_direct_wiring_smoke(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.6, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    solver = ComposableSolver(problem=sample_problem, representation_pipeline=pipeline)
    solver.set_adapter(
        SimulatedAnnealingAdapter(
            SAConfig(initial_temperature=5.0, cooling_rate=0.9),
        )
    )
    solver.max_steps = 3
    solver.run()

    assert solver.adapter is not None
