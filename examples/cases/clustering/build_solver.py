"""
Clustering benchmark: nsgablack SA/DE search vs sklearn KMeans (Lloyd).
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable

ensure_nsgablack_importable(Path(__file__))


def build_solver(
    data: "np.ndarray",
    k: int = 3,
    adapter: str = "sa",
    pop_size: int = 20,
    max_steps: int = 200,
):
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
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import (
        ClipRepair,
        ContextGaussianMutation,
        UniformInitializer,
    )

    from problem.clustering_problem import ClusteringProblem

    problem = ClusteringProblem(np.asarray(data, dtype=float), k=k)
    n_feat = problem.n_features

    # Representation: flat centroid vector with per-dimension bounds
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(
            low=[b[0] for b in problem.bounds], high=[b[1] for b in problem.bounds]
        ),
        mutator=ContextGaussianMutation(
            base_sigma=0.15,
            sigma_key="mutation_sigma",
            low=[b[0] for b in problem.bounds],
            high=[b[1] for b in problem.bounds],
        ),
        repair=ClipRepair(
            low=[b[0] for b in problem.bounds], high=[b[1] for b in problem.bounds]
        ),
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
    return solver


# ── Benchmark runner ────────────────────────────────────────────────────
def main():
    import argparse
    import time

    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.datasets import make_blobs

    parser = argparse.ArgumentParser(description="Clustering benchmark")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--n-samples", type=int, default=300)
    parser.add_argument("--n-features", type=int, default=2)
    parser.add_argument("--adapter", type=str, default="sa")
    parser.add_argument("--pop-size", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    data, true_labels = make_blobs(
        n_samples=args.n_samples,
        n_features=args.n_features,
        centers=args.k,
        cluster_std=1.5,
        random_state=args.seed,
    )

    print(f"Dataset: {args.n_samples} points, {args.n_features}D, k={args.k}")
    print(f"Adapter: {args.adapter}, pop={args.pop_size}, steps={args.max_steps}")
    print()

    # ── nsgablack ──
    solver = build_solver(
        data=data,
        k=args.k,
        adapter=args.adapter,
        pop_size=args.pop_size,
        max_steps=args.max_steps,
    )
    solver.set_random_seed(args.seed)

    t0 = time.perf_counter()
    result = solver.run()
    nsga_time = time.perf_counter() - t0

    best_x = getattr(solver, "best_x", None)
    nsga_sse = float(solver.problem.evaluate(best_x)) if best_x is not None else float("inf")
    nsga_centroids = solver.problem.get_centroids(best_x) if best_x is not None else None

    # ── sklearn KMeans (Lloyd) ──
    t0 = time.perf_counter()
    km = KMeans(n_clusters=args.k, n_init=10, random_state=args.seed)
    km.fit(data)
    sk_time = time.perf_counter() - t0
    sk_sse = float(km.inertia_)

    # ── Report ──
    print(f"{'':-^50}")
    print(f"{'Method':<20} {'SSE':>12} {'Time(s)':>10}")
    print(f"{'':-^50}")
    print(f"{'nsgablack (' + args.adapter + ')':<20} {nsga_sse:>12.4f} {nsga_time:>10.4f}")
    print(f"{'sklearn KMeans':<20} {sk_sse:>12.4f} {sk_time:>10.4f}")
    print(f"{'':-^50}")
    print(f"SSE ratio (nsga/sk): {nsga_sse / sk_sse:.4f}")
    print(f"Time ratio (nsga/sk): {nsga_time / sk_time:.2f}x")


if __name__ == "__main__":
    main()
