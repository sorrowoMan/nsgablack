"""Dynamic + Multi-Strategy showcase.

This example demonstrates:
- MultiStrategyControllerAdapter (cooperative strategies)
- DynamicSwitchPlugin (soft switching via signals)
- RepresentationPipeline with context-aware mutation
- BenchmarkHarness suite for reproducible outputs
"""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        MultiStrategyControllerAdapter,
        MultiStrategyConfig,
        StrategySpec,
        SimulatedAnnealingAdapter,
        SAConfig,
        VNSAdapter,
        VNSConfig,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.bias import BiasModule
    from nsgablack.bias.domain import DynamicPenaltyBias
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.plugins import DynamicSwitchPlugin, SensitivityAnalysisPlugin, SensitivityAnalysisConfig, SensitivityParam
    from nsgablack.utils.dynamic import SignalProviderBase
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover - convenience for direct script runs
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        MultiStrategyControllerAdapter,
        MultiStrategyConfig,
        StrategySpec,
        SimulatedAnnealingAdapter,
        SAConfig,
        VNSAdapter,
        VNSConfig,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.bias import BiasModule
    from nsgablack.bias.domain import DynamicPenaltyBias
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.plugins import DynamicSwitchPlugin, SensitivityAnalysisPlugin, SensitivityAnalysisConfig, SensitivityParam
    from nsgablack.utils.dynamic import SignalProviderBase
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report


class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension=8, low=-5.0, high=5.0):
        super().__init__(
            name="DynamicMultiStrategySphere",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x ** 2))


class AdaptiveSignalProvider(SignalProviderBase):
    """Signal based on recent improvement + population diversity."""

    def __init__(self, improve_tol=1e-3, diversity_tol=0.4, ema_alpha=0.2):
        self.improve_tol = float(improve_tol)
        self.diversity_tol = float(diversity_tol)
        self.ema_alpha = float(ema_alpha)
        self.last_best = None
        self.improve_ema = 0.0
        self.diversity_ema = 0.0
        self.mode = "explore"
        self.step = 0

    def update(self, best_value: float, diversity: float):
        if self.last_best is None:
            improve = 0.0
        else:
            improve = float(self.last_best - best_value)
        self.last_best = float(best_value)
        self.improve_ema = (1 - self.ema_alpha) * self.improve_ema + self.ema_alpha * improve
        self.diversity_ema = (1 - self.ema_alpha) * self.diversity_ema + self.ema_alpha * float(diversity)
        if self.improve_ema < self.improve_tol or self.diversity_ema < self.diversity_tol:
            self.mode = "explore"
        else:
            self.mode = "exploit"

    def read(self):
        self.step += 1
        return {
            "mode": self.mode,
            "tick": self.step,
            "improve_ema": self.improve_ema,
            "diversity_ema": self.diversity_ema,
        }


def build_solver():
    problem = SphereProblem()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    sa = SimulatedAnnealingAdapter(SAConfig(batch_size=2, initial_temperature=8.0, cooling_rate=0.97))
    vns = VNSAdapter(VNSConfig(batch_size=6, k_max=4, base_sigma=0.2, scale=1.5))

    adapter = MultiStrategyControllerAdapter(
        strategies=[
            StrategySpec(adapter=sa, name="sa", weight=0.6),
            StrategySpec(adapter=vns, name="vns", weight=1.0),
        ],
        config=MultiStrategyConfig(
            total_batch_size=24,
            adapt_weights=True,
            phase_schedule=(("explore", 20), ("exploit", -1)),
        ),
    )

    bias_module = BiasModule()
    def _soft_bounds_penalty(x, _context):
        x = np.asarray(x, dtype=float)
        return float(np.sum(np.maximum(0.0, np.abs(x) - 3.0)))

    bias_module.add(
        DynamicPenaltyBias(
            weight=0.2,
            penalty_func=_soft_bounds_penalty,
            schedule="linear",
            start_scale=0.2,
            end_scale=1.0,
        )
    )

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
        bias_module=bias_module,
    )
    solver.set_enable_bias(True)
    solver.set_max_steps(40)

    attach_benchmark_harness(
        solver,
        output_dir="runs",
        run_id="dynamic_multi_strategy",
        overwrite=True,
        log_every=1,
    )
    attach_module_report(
        solver,
        output_dir="runs",
        run_id="dynamic_multi_strategy",
        write_bias_markdown=True,
    )

    signal_provider = AdaptiveSignalProvider(improve_tol=1e-3, diversity_tol=0.35, ema_alpha=0.2)

    def should_switch(solver, context):
        # estimate diversity from population if available
        diversity = 0.0
        data = None
        reader = getattr(solver, "read_snapshot", None)
        if callable(reader):
            try:
                key = context.get("population_ref") or context.get("snapshot_key")
            except Exception:
                key = None
            try:
                data = reader(key) if key else reader()
            except Exception:
                data = None
        if data is None:
            data = {}
        pop = data.get("population")
        if pop is not None and len(pop) > 0:
            try:
                arr = np.asarray(pop, dtype=float)
                diversity = float(np.mean(np.std(arr, axis=0)))
            except Exception:
                diversity = 0.0
        best = getattr(solver, "best_objective", None)
        if best is not None:
            signal_provider.update(best, diversity)

        mode = (context.get("dynamic") or {}).get("mode")
        return mode is not None and mode != getattr(solver, "dynamic_mode", None)

    def soft_switch(solver, context):
        mode = (context.get("dynamic") or {}).get("mode")
        improve = float((context.get("dynamic") or {}).get("improve_ema", 0.0) or 0.0)
        diversity = float((context.get("dynamic") or {}).get("diversity_ema", 0.0) or 0.0)
        # continuous weights: explore when improvement/diversity low
        score = (diversity - 0.35) + (improve - 1e-3)
        explore_factor = 1.0 / (1.0 + np.exp(3.0 * score))
        sa_w = 0.6 + 0.8 * (1.0 - explore_factor)
        vns_w = 0.6 + 0.8 * explore_factor

        enabled_map = {}
        for spec in adapter.strategies:
            if spec.name == "sa":
                spec.weight = float(sa_w)
            elif spec.name == "vns":
                spec.weight = float(vns_w)
            enabled_map[spec.name] = bool(getattr(spec, "enabled", True))

        solver.dynamic_mode = mode
        msg = [f"sa={sa_w:.2f}" if enabled_map.get("sa", False) else "sa=off"]
        msg.append(f"vns={vns_w:.2f}" if enabled_map.get("vns", False) else "vns=off")
        print(f"[dynamic] switch -> {mode} ({', '.join(msg)})")

    solver.add_plugin(
        DynamicSwitchPlugin(
            should_switch_fn=should_switch,
            soft_switch_fn=soft_switch,
            signal_provider=signal_provider,
        )
    )

    # Optional: sensitivity sweep (example)
    solver.add_plugin(
        SensitivityAnalysisPlugin(
            config=SensitivityAnalysisConfig(
                params=[
                    SensitivityParam(
                        path="adapter.strategies[0].weight",
                        values=[0.4, 0.6, 0.8],
                        label="sa_weight",
                    ),
                ]
            )
        )
    )

    return solver


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="Launch Run Inspector UI before running.")
    args = parser.parse_args()

    from nsgablack.utils.viz import launch_from_builder, maybe_launch_ui

    if args.ui:
        launch_from_builder(build_solver, entry_label="examples/dynamic_multi_strategy_demo.py:build_solver")
    elif maybe_launch_ui(build_solver, entry_label="examples/dynamic_multi_strategy_demo.py:build_solver"):
        pass
    else:
        solver = build_solver()
        result = solver.run()
        print("运行状态:", result["status"], "steps:", result["steps"])
        if solver.best_x is not None:
            print("最优目标值:", f"{solver.best_objective:.6f}")
            print("最优解:", solver.best_x)

