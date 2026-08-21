"""
Changepoint Detection: nsgablack DE vs ruptures PELT.

Standard scaffold entry.
"""

from __future__ import annotations

def build_solver(signal: "np.ndarray | None" = None, max_changepoints: int = 3, *, adapter: str = "de", pop_size: int = 30, max_steps: int = 150, sparsity_weight: float = 100.0, resource_context=None, component_overrides=None):
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

    overrides = dict(component_overrides or {})
    config = dict(overrides.pop("config", {}) or {})
    max_changepoints = int(config.pop("max_changepoints", max_changepoints))
    adapter = str(config.pop("adapter", adapter))
    pop_size = int(config.pop("pop_size", pop_size))
    max_steps = int(config.pop("max_steps", max_steps))
    sparsity_weight = float(config.pop("sparsity_weight", sparsity_weight))
    if config:
        raise ValueError("unsupported changepoint config overrides: " + str(sorted(config)))
    signal = overrides.pop("signal", signal)
    if signal is None:
        signal = np.concatenate(
            [np.zeros(30, dtype=float), np.ones(30, dtype=float), np.full(30, 0.25)]
        )
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
    from nsgablack.project import apply_solver_component_overrides
    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
