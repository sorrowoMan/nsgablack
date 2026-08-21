"""GMM: nsgablack StrategyChain DE→VNS vs sklearn GaussianMixture (EM)."""
from __future__ import annotations
from typing import Any

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
    def setup(self, control: Any) -> None:
        super().setup(control)
        best_x = getattr(control, "best_x", None)
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


def build_solver(
    *,
    pop_size: int = 30,
    max_steps: int = 300,
    resource_context=None,
    component_overrides=None,
):
    """Canonical scaffold entry: assemble GMM solver (DE→VNS).

    Uses synthetic 3-cluster blobs data by default.
    Override the problem via component_overrides={"problem": my_problem}.
    """
    overrides = dict(component_overrides or {})
    config = dict(overrides.pop("config", {}) or {})
    pop_size = int(config.pop("pop_size", pop_size))
    max_steps = int(config.pop("max_steps", max_steps))
    k = int(config.pop("k", 3))
    n_samples = int(config.pop("n_samples", 300))
    n_features = int(config.pop("n_features", 2))
    random_seed = int(config.pop("random_seed", 42))
    if config:
        raise ValueError("unsupported gmm_em_vs_de config overrides: " + str(sorted(config)))

    problem = overrides.pop("problem", None)
    if problem is None:
        from sklearn.datasets import make_blobs
        X, _y_true = make_blobs(
            n_samples=n_samples,
            n_features=n_features,
            centers=k,
            cluster_std=1.0,
            random_state=random_seed,
        )
        problem = GMMProblem(X, k=k)

    low = np.array([b[0] for b in problem.bounds], dtype=float)
    high = np.array([b[1] for b in problem.bounds], dtype=float)
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
        problem=problem,
        adapter=chain,
        representation_pipeline=pipeline,
        bias_module=bias,
    )
    solver.set_max_steps(max_steps)
    from nsgablack.project import apply_solver_component_overrides

    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
