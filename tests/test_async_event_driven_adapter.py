import numpy as np


def _build_pipeline():
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer

    return RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.4, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
    )


def test_async_event_driven_adapter_runs(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        AsyncEventDrivenAdapter,
        AsyncEventDrivenConfig,
        EventStrategySpec,
        SAConfig,
        SimulatedAnnealingAdapter,
        VNSAdapter,
        VNSConfig,
    )

    np.random.seed(3)
    adapter = AsyncEventDrivenAdapter(
        strategies=[
            EventStrategySpec(
                adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=1, initial_temperature=6.0)),
                name="sa",
                weight=0.8,
            ),
            EventStrategySpec(
                adapter=VNSAdapter(VNSConfig(batch_size=2, k_max=3, base_sigma=0.25)),
                name="vns",
                weight=1.2,
            ),
        ],
        config=AsyncEventDrivenConfig(total_batch_size=10, target_queue_size=24),
    )

    solver = ComposableSolver(problem=sample_problem, adapter=adapter, representation_pipeline=_build_pipeline())
    solver.max_steps = 10
    solver.run()

    assert solver.best_objective is not None
    ctx = solver.get_context()
    state = ctx.get("event_shared", {}) or {}
    assert "queue_size" in state
    assert "stats" in state
    assert len(adapter.event_history) > 0
    assert len(adapter.archive) > 0


def test_attach_async_event_suite_wires_plugins(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import EventStrategySpec, SAConfig, SimulatedAnnealingAdapter
    from nsgablack.utils.suites import attach_async_event_driven

    solver = ComposableSolver(problem=sample_problem, representation_pipeline=_build_pipeline())
    adapter = attach_async_event_driven(
        solver,
        strategies=[
            EventStrategySpec(
                adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=1)),
                name="sa",
            )
        ],
        attach_async_hub=True,
        attach_pareto_archive=True,
    )

    assert solver.adapter is adapter
    assert solver.get_plugin("async_event_hub") is not None
    assert solver.get_plugin("pareto_archive") is not None
