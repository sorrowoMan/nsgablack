"""GMM: nsgablack StrategyChain DE→VNS vs sklearn GaussianMixture (EM)."""
from __future__ import annotations
import sys, time, argparse
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path: sys.path.insert(0, str(_THIS_DIR))
from _bootstrap import ensure_nsgablack_importable; ensure_nsgablack_importable(Path(__file__))

import numpy as np
from nsgablack.adapters import (
    DifferentialEvolutionAdapter, DEConfig,
    VNSAdapter,
    StrategyChainAdapter, SerialPhaseSpec,
)
from nsgablack.bias import BiasModule
from nsgablack.bias.specialized.local_search import NelderMeadBias
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
from nsgablack.core.composable_solver import ComposableSolver
from problem.gmm_problem import GMMProblem


class WarmStartVNSAdapter(VNSAdapter):
    def setup(self, solver: Any) -> None:
        super().setup(solver)
        best_x = getattr(solver, "best_x", None)
        if best_x is not None:
            self.current_x = np.asarray(best_x, dtype=float).copy()
            self.current_score = None


class NelderMeadBiasBridge(NelderMeadBias):
    def compute(self, x, context):
        try:
            problem_data = getattr(context, 'problem_data', {}) or {}
            eval_func = problem_data.get('eval_func')
        except Exception:
            eval_func = None
        if eval_func is None:
            return 0.0
        try:
            return self.apply(np.asarray(x, dtype=float), eval_func, context)
        except Exception:
            return 0.0


def build_solver(data, k=3, *, pop_size=30, max_steps=300):
    prob = GMMProblem(data, k=k)
    low = np.array([b[0] for b in prob.bounds], dtype=float)
    high = np.array([b[1] for b in prob.bounds], dtype=float)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=low, high=high),
        mutator=ContextGaussianMutation(base_sigma=0.25, low=low, high=high),
        repair=ClipRepair(low=low, high=high))

    de_steps = max(1, max_steps * 80 // 100)
    vns_steps = max_steps - de_steps
    de_phase = SerialPhaseSpec(
        name="global_explore",
        adapter=DifferentialEvolutionAdapter(DEConfig(batch_size=pop_size)),
        steps=de_steps,
    )
    vns_phase = SerialPhaseSpec(
        name="local_refine",
        adapter=WarmStartVNSAdapter(batch_size=pop_size),
        steps=vns_steps,
    )
    chain = StrategyChainAdapter(phases=[de_phase, vns_phase])

    bias = BiasModule()
    bias.add(NelderMeadBiasBridge())

    solver = ComposableSolver(
        problem=prob,
        adapter=chain,
        representation_pipeline=pipeline,
        bias_module=bias,
    )
    solver.set_max_steps(max_steps)
    return solver


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--pop-size", type=int, default=30)
    p.add_argument("--max-steps", type=int, default=300)
    p.add_argument("--n-samples", type=int, default=300)
    p.add_argument("--n-features", type=int, default=2)
    args = p.parse_args()

    from sklearn.datasets import make_blobs
    from sklearn.mixture import GaussianMixture

    X, y_true = make_blobs(n_samples=args.n_samples, n_features=args.n_features,
                           centers=args.k, cluster_std=1.0, random_state=args.seed)

    t0 = time.perf_counter()
    sk_gmm = GaussianMixture(n_components=args.k, covariance_type="diag",
                             random_state=args.seed, n_init=3).fit(X)
    sk_time = time.perf_counter() - t0
    sk_nll = -sk_gmm.score(X) * X.shape[0]

    solver = build_solver(X, k=args.k, pop_size=args.pop_size, max_steps=args.max_steps)
    solver.set_random_seed(args.seed)
    t0 = time.perf_counter()
    solver.run()
    nsga_time = time.perf_counter() - t0
    nsga_nll = float(solver.best_objective) if solver.best_objective is not None else float("inf")

    print(f"GMM  k={args.k}  n={X.shape[0]}  d={X.shape[1]}  dimension={solver.problem.dimension}")
    print(f"sklearn EM       NLL={sk_nll:.3f}  time={sk_time:.3f}s")
    print(f"nsgablack DE→VNS  NLL={nsga_nll:.3f}  time={nsga_time:.2f}s")
    if nsga_nll < float("inf") and sk_nll < float("inf"):
        ratio = nsga_nll / max(sk_nll, 1e-10)
        print(f"ratio (DE→VNS/EM) = {ratio:.4f}")


if __name__ == "__main__":
    main()
