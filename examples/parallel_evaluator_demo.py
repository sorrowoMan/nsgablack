"""ParallelEvaluator demo: evaluate a population in parallel."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.utils.parallel.evaluator import ParallelEvaluator
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.utils.parallel.evaluator import ParallelEvaluator


class Sphere(BlackBoxProblem):
    def __init__(self, dim=6, low=-5.0, high=5.0):
        super().__init__(name="Sphere", dimension=dim, bounds={f"x{i}": (low, high) for i in range(dim)})
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


def main():
    problem = Sphere()
    rng = np.random.default_rng(7)
    pop = rng.uniform(problem.low, problem.high, size=(16, problem.dimension))

    evaluator = ParallelEvaluator(backend="thread", max_workers=4, precheck=True)
    obj, vio, errors = evaluator.evaluate_population(
        pop,
        problem=problem,
        enable_bias=False,
        extra_context={"generation": 0},
    )

    print("objectives shape:", np.asarray(obj).shape)
    print("violations shape:", np.asarray(vio).shape)
    print("errors:", errors)


if __name__ == "__main__":
    main()
