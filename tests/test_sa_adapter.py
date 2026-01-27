import numpy as np


def test_simulated_annealing_adapter_runs_and_cools(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair

    np.random.seed(123)

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
    solver.max_steps = 60
    solver.run()

    assert solver.best_objective is not None
    # sphere objective is >=0; we only assert it improves to a reasonable range (avoid flakiness)
    assert solver.best_objective < 20.0
    assert hasattr(solver, "sa_temperature")
    assert float(solver.sa_temperature) < float(cfg.initial_temperature)


def test_sa_suite_attach_smoke(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_simulated_annealing

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.6, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    solver = ComposableSolver(problem=sample_problem, representation_pipeline=pipeline)
    attach_simulated_annealing(solver, initial_temperature=5.0, cooling_rate=0.9)
    solver.max_steps = 3
    solver.run()

    assert solver.adapter is not None
