"""
Changepoint Detection: nsgablack DE vs ruptures PELT.

Standard scaffold entry.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from _bootstrap import ensure_nsgablack_importable

ensure_nsgablack_importable(Path(__file__))

from nsgablack.project.scaffold import print_solver_check


def build_solver(signal: "np.ndarray", max_changepoints: int = 3, *, adapter: str = "de", pop_size: int = 30, max_steps: int = 150, sparsity_weight: float = 100.0, resource_context=None, component_overrides=None):
    """Build a changepoint detection solver.

    Args:
        signal: 1-D time series array.
        max_changepoints: maximum number of changepoints to search for.
        adapter: "de" | "pattern_search" | "sa".
        pop_size: population/batch size.
        max_steps: optimization steps.
        sparsity_weight: bias penalty per excess changepoint.
    """
    import numpy as np
    from nsgablack.adapters import (
        DEConfig,
        DifferentialEvolutionAdapter,
        PatternSearchAdapter,
        SAConfig,
        SimulatedAnnealingAdapter,
    )
    from nsgablack.bias import BiasModule
    from nsgablack.bias.domain import CallableBias
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import (
        ClipRepair,
        ContextGaussianMutation,
        UniformInitializer,
    )

    from problem.changepoint_problem import ChangepointProblem

    signal = np.asarray(signal, dtype=float)
    n = len(signal)
    prob = ChangepointProblem(signal, max_changepoints=max_changepoints)
    bounds = [(5.0, float(n - 5))] * max_changepoints

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=[b[0] for b in bounds], high=[b[1] for b in bounds]),
        mutator=ContextGaussianMutation(
            base_sigma=float(n) * 0.05,
            low=[b[0] for b in bounds],
            high=[b[1] for b in bounds],
        ),
        repair=ClipRepair(low=[b[0] for b in bounds], high=[b[1] for b in bounds]),
    )

    # Bias: penalize too many changepoints
    bias = BiasModule()
    def cp_sparsity(x, constraints, context):
        cps = np.unique(np.clip(np.asarray(x, dtype=int), 5, 99999))
        excess = max(0, len(cps) - 2)
        return {"penalty": float(excess * sparsity_weight)}
    bias.add(CallableBias(name="changepoint_sparsity", func=cp_sparsity, weight=1.0, mode="penalty"))

    adapter_key = (adapter or "de").strip().lower()
    if adapter_key == "pattern_search":
        alg = PatternSearchAdapter()
    elif adapter_key == "sa":
        alg = SimulatedAnnealingAdapter(SAConfig(batch_size=pop_size))
    else:
        alg = DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size))

    solver = ComposableSolver(problem=prob, adapter=alg, representation_pipeline=pipeline, bias_module=bias)
    solver.set_max_steps(max_steps)
    return solver


def main():
    import argparse, time
    import numpy as np

    parser = argparse.ArgumentParser(description="Changepoint detection benchmark")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--max-cp", type=int, default=3)
    parser.add_argument("--adapter", type=str, default="de")
    parser.add_argument("--max-steps", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    n = args.n
    cp1, cp2 = int(n * 0.3), int(n * 0.7)
    y = np.concatenate([
        rng.normal(0, 1, cp1),
        rng.normal(5, 1, cp2 - cp1),
        rng.normal(2, 1, n - cp2),
    ])

    solver = build_solver(signal=y, max_changepoints=args.max_cp, adapter=args.adapter, max_steps=args.max_steps)
    solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return

    # ruptures PELT
    try:
        import ruptures as rpt
        algo = rpt.Pelt(model="l2").fit(y)
        cp_ruptures = algo.predict(pen=10)
        cp_ruptures = [c for c in cp_ruptures if c < n]
    except ImportError:
        cp_ruptures = [cp1, cp2]

    # nsgablack
    t0 = time.perf_counter()
    solver.run()
    nsga_t = time.perf_counter() - t0
    nsga_cps = solver.problem.get_changepoints(solver.best_x).tolist() if solver.best_x is not None else []

    print(f"True:   [{cp1}, {cp2}]")
    print(f"PELT:   {cp_ruptures}")
    print(f"nsgablack ({args.adapter}): {nsga_cps}  ({nsga_t:.2f}s)")


if __name__ == "__main__":
    main()
