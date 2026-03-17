import numpy as np


def test_multi_strategy_controller_runs_and_broadcasts_shared_state(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        StrategySpec,
        MultiStrategyConfig,
        StrategyRouterAdapter,
        VNSAdapter,
        VNSConfig,
        SimulatedAnnealingAdapter,
        SAConfig,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair

    np.random.seed(1)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.5, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    strategies = [
        StrategySpec(adapter=VNSAdapter(VNSConfig(batch_size=8, k_max=3)), name="vns", weight=0.6),
        StrategySpec(adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=4)), name="sa", weight=0.4),
    ]
    cfg = MultiStrategyConfig(total_batch_size=12, adapt_weights=True, stagnation_window=5)
    controller = StrategyRouterAdapter(strategies=strategies, config=cfg)

    solver = ComposableSolver(problem=sample_problem, adapter=controller, representation_pipeline=pipeline)
    solver.max_steps = 30
    solver.run()

    assert solver.best_objective is not None
    ctx = solver.get_context()
    shared = ctx.get("shared", {}) or {}
    assert shared.get("best_score") is not None
    assert isinstance(shared.get("strategies"), dict)
    assert "vns" in shared["strategies"]
    assert "sa" in shared["strategies"]


def test_multi_strategy_direct_wiring_smoke(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        StrategyRouterAdapter,
        StrategySpec,
        VNSAdapter,
        VNSConfig,
        SimulatedAnnealingAdapter,
        SAConfig,
    )
    from nsgablack.plugins import ParetoArchivePlugin
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.5, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    solver = ComposableSolver(problem=sample_problem, representation_pipeline=pipeline)
    solver.set_adapter(
        StrategyRouterAdapter(
        strategies=[
            StrategySpec(adapter=VNSAdapter(VNSConfig(batch_size=4, k_max=2)), name="vns", weight=0.5),
            StrategySpec(adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=2)), name="sa", weight=0.5),
        ],
        )
    )
    solver.add_plugin(ParetoArchivePlugin())
    solver.max_steps = 3
    solver.run()
    assert solver.adapter is not None


def test_multi_strategy_controller_supports_multi_units_per_role(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        RoleSpec,
        MultiStrategyConfig,
        StrategyRouterAdapter,
        VNSAdapter,
        VNSConfig,
        SimulatedAnnealingAdapter,
        SAConfig,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.5, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    roles = [
        RoleSpec(
            name="vns",
            adapter=lambda uid: VNSAdapter(VNSConfig(batch_size=4, k_max=2)),
            n_units=3,
            weight=0.6,
        ),
        RoleSpec(
            name="sa",
            adapter=lambda uid: SimulatedAnnealingAdapter(SAConfig(batch_size=2)),
            n_units=2,
            weight=0.4,
        ),
    ]
    cfg = MultiStrategyConfig(total_batch_size=10, adapt_weights=True, stagnation_window=5)
    controller = StrategyRouterAdapter(roles=roles, config=cfg)

    solver = ComposableSolver(problem=sample_problem, adapter=controller, representation_pipeline=pipeline)
    solver.max_steps = 10
    solver.run()

    assert solver.best_objective is not None
    ctx = solver.get_context()
    units = ctx.get("candidate_units")
    assert isinstance(units, list)
    assert len(set(units)) > 1
    ctx = solver.get_context()
    shared = ctx.get("shared", {}) or {}
    assert "units" in shared


def test_multi_strategy_phase_and_region_tasks_are_dispatched(sample_problem):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import RoleSpec, MultiStrategyConfig, StrategyRouterAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    import numpy as np

    class RecorderAdapter:
        def __init__(self, name: str):
            from nsgablack.adapters import AlgorithmAdapter

            class _A(AlgorithmAdapter):
                def __init__(self, outer, nm):
                    super().__init__(name=nm)
                    self.outer = outer

                def propose(self, solver, context):
                    task = context.get("task", {})
                    self.outer.last_tasks.append(task)
                    # simple proposals using pipeline helpers
                    k = int(task.get("budget", 1))
                    out = []
                    for _ in range(max(1, k)):
                        x = solver.init_candidate(context)
                        out.append(solver.mutate_candidate(x, context))
                    return out

            self.adapter = _A(self, name)
            self.last_tasks = []

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.5, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    rec1 = RecorderAdapter("explorer")
    rec2 = RecorderAdapter("exploiter")

    roles = [
        RoleSpec(name="explorer", adapter=lambda uid: rec1.adapter, n_units=1, weight=1.0),
        RoleSpec(name="exploiter", adapter=lambda uid: rec2.adapter, n_units=1, weight=1.0),
    ]
    cfg = MultiStrategyConfig(
        total_batch_size=6,
        enable_regions=True,
        n_regions=4,
        phase_schedule=(("explore", 2), ("exploit", -1)),
        phase_roles={"explore": ["explorer"], "exploit": ["exploiter"]},
        seeds_per_task=1,
        seeds_source="best",
    )
    controller = StrategyRouterAdapter(roles=roles, config=cfg)

    solver = ComposableSolver(problem=sample_problem, adapter=controller, representation_pipeline=pipeline)
    solver.max_steps = 5
    solver.run()

    ctx = solver.get_context()
    shared = ctx.get("shared", {}) or {}
    assert shared.get("phase") in {"explore", "exploit"}
    assert isinstance(shared.get("regions"), list)
    assert len(shared["regions"]) == 4
    ctx = solver.get_context()
    unit_tasks = ctx.get("unit_tasks")
    assert isinstance(unit_tasks, dict)
    # verify some task contains phase/region/seeds keys
    any_task = None
    for _k, task in unit_tasks.items():
        any_task = task
        break
    assert any_task is not None
    assert "phase" in any_task and "region_id" in any_task and "seeds" in any_task

