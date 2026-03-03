from __future__ import annotations

from nsgablack.utils.context.context_keys import KEY_BEST_OBJECTIVE, KEY_BEST_X


def test_composable_solver_exposes_best_context_keys(sample_problem) -> None:
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.2, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )
    solver = ComposableSolver(
        problem=sample_problem,
        adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=6)),
        representation_pipeline=pipeline,
    )
    solver.max_steps = 4
    solver.run()

    ctx = solver.get_context()
    assert KEY_BEST_X in ctx
    assert KEY_BEST_OBJECTIVE in ctx
    assert ctx[KEY_BEST_OBJECTIVE] is not None


def test_nsga2_solver_exposes_best_context_keys(sample_problem) -> None:
    from nsgablack.core.evolution_solver import EvolutionSolver

    solver = EvolutionSolver(sample_problem)
    solver.pop_size = 12
    solver.max_generations = 3
    solver.enable_progress_log = False
    solver.run(return_dict=True)

    ctx = solver.get_context()
    assert KEY_BEST_X in ctx
    assert KEY_BEST_OBJECTIVE in ctx
    assert ctx[KEY_BEST_OBJECTIVE] is not None
