"""
Clustering benchmark: nsgablack SA/DE search vs sklearn KMeans (Lloyd).
"""

from __future__ import annotations

def build_solver(data: "np.ndarray | None" = None, k: int = 3, adapter: str = "sa", pop_size: int = 20, max_steps: int = 200, *, resource_context=None, component_overrides=None):
    """Build a clustering solver for the given dataset.

    Args:
        data: (n_samples, n_features) array.
        k: number of clusters.
        adapter: "sa" | "de" | "vns".
        pop_size: population / batch size.
        max_steps: optimization steps / generations.
    """
    import numpy as np

    from nsgablack.adapters import (
        AlgorithmAdapter,
        CompositeAdapter,
        DEConfig,
        DifferentialEvolutionAdapter,
        SAConfig,
        SimulatedAnnealingAdapter,
    )
    from nsgablack.core.composable_solver import ComposableSolver
    from pipeline.main import build_pipeline
    from problem.clustering_problem import ClusteringProblem

    overrides = dict(component_overrides or {})
    config = dict(overrides.pop("config", {}) or {})
    k = int(config.pop("k", k))
    adapter = str(config.pop("adapter", adapter))
    pop_size = int(config.pop("pop_size", pop_size))
    max_steps = int(config.pop("max_steps", max_steps))
    if config:
        raise ValueError("unsupported clustering config overrides: " + str(sorted(config)))
    data = overrides.pop("data", data)
    if data is None:
        data = np.asarray(
            [[0.0, 0.0], [0.1, 0.0], [1.0, 1.0], [1.1, 1.0], [2.0, 0.0], [2.1, 0.0]],
            dtype=float,
        )
    problem = ClusteringProblem(np.asarray(data, dtype=float), k=k)
    pipeline = build_pipeline(
        problem,
        resource_context=resource_context,
        component_overrides=overrides,
    )

    adapter_key = (adapter or "sa").strip().lower()
    if adapter_key == "de":
        alg = DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size))
    elif adapter_key == "sa":
        alg = SimulatedAnnealingAdapter(SAConfig(batch_size=pop_size))
    else:
        alg = SimulatedAnnealingAdapter(SAConfig(batch_size=pop_size))

    solver = ComposableSolver(
        problem=problem,
        adapter=alg,
        representation_pipeline=pipeline,
    )
    solver.set_max_steps(max_steps)
    from nsgablack.project import apply_solver_component_overrides
    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver


# ── Benchmark runner ────────────────────────────────────────────────────
