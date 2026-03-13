"""Template: portfolio optimization (Pareto: risk vs return) with simplex repair."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import MOEADAdapter, MOEADConfig
    from nsgablack.plugins import ParetoArchivePlugin
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation
    from nsgablack.utils.wiring import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import MOEADAdapter, MOEADConfig
    from nsgablack.plugins import ParetoArchivePlugin
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation
    from nsgablack.utils.wiring import attach_benchmark_harness, attach_module_report


class SimplexRepair:
    """Project weights onto simplex (sum=1, all >=0)."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Simplex projection is local; no context I/O.",)

    def repair(self, x, context=None):
        w = np.maximum(0.0, np.asarray(x, dtype=float))
        s = float(np.sum(w))
        if s <= 0:
            w[:] = 1.0 / len(w)
        else:
            w = w / s
        return w


class PortfolioProblem(BlackBoxProblem):
    def __init__(self, mu: np.ndarray, cov: np.ndarray):
        n = len(mu)
        super().__init__(
            name="PortfolioPareto",
            dimension=n,
            bounds={f"x{i}": (0.0, 1.0) for i in range(n)},
        )
        self.mu = np.asarray(mu, dtype=float)
        self.cov = np.asarray(cov, dtype=float)

    def evaluate(self, x):
        w = np.asarray(x, dtype=float)
        ret = float(np.dot(w, self.mu))
        risk = float(w @ self.cov @ w)
        # minimize risk, maximize return -> minimize (-return)
        return np.array([risk, -ret], dtype=float)


def build_solver():
    rng = np.random.default_rng(3)
    n_assets = 8
    mu = rng.uniform(0.01, 0.2, size=n_assets)
    A = rng.normal(0.0, 0.1, size=(n_assets, n_assets))
    cov = A.T @ A

    problem = PortfolioProblem(mu, cov)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=0.0, high=1.0),
        mutator=ContextGaussianMutation(base_sigma=0.2, low=0.0, high=1.0),
        repair=SimplexRepair(),
    )

    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    solver.set_max_steps(80)

    solver.set_adapter(MOEADAdapter(MOEADConfig(pop_size=40, n_neighbors=10)))
    solver.add_plugin(ParetoArchivePlugin())
    attach_benchmark_harness(solver, output_dir="runs", run_id="template_portfolio", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="template_portfolio", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("pareto_size:", len(getattr(solver, "pareto_objectives", []) or []))
