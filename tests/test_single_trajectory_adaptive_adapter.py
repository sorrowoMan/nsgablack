import numpy as np


def _pipeline():
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer

    return RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.35, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
    )


def test_single_trajectory_adapter_runs(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SingleTrajectoryAdaptiveAdapter, SingleTrajectoryAdaptiveConfig

    np.random.seed(13)
    adapter = SingleTrajectoryAdaptiveAdapter(
        SingleTrajectoryAdaptiveConfig(batch_size=6, initial_sigma=0.4, restart_patience=8)
    )
    solver = ComposableSolver(problem=sample_problem, adapter=adapter, representation_pipeline=_pipeline())
    solver.max_steps = 12
    solver.run()

    assert solver.best_objective is not None
    assert getattr(solver, "sta_sigma", None) is not None
    assert getattr(solver, "sta_best_x", None) is not None


def test_attach_single_trajectory_suite(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SingleTrajectoryAdaptiveConfig
    from nsgablack.utils.suites import attach_single_trajectory_adaptive

    solver = ComposableSolver(problem=sample_problem, representation_pipeline=_pipeline())
    adapter = attach_single_trajectory_adaptive(
        solver,
        config=SingleTrajectoryAdaptiveConfig(batch_size=4, initial_sigma=0.3),
    )
    solver.max_steps = 5
    solver.run()

    assert solver.adapter is adapter
    assert solver.best_objective is not None
