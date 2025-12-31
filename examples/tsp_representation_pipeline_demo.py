"""
TSP demo using the representation pipeline (random-keys encoding).
"""

import os
import sys
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from utils.representation import RepresentationPipeline
from utils.representation.continuous import ClipRepair
from utils.representation.permutation import (
    RandomKeyInitializer,
    RandomKeyMutation,
    RandomKeyPermutationDecoder,
)


class TSPRandomKeysProblem(BlackBoxProblem):
    def __init__(self, cities: np.ndarray):
        self.cities = np.array(cities, dtype=float)
        self.decoder = RandomKeyPermutationDecoder()
        n = self.cities.shape[0]
        bounds = {f"x{i}": [0.0, 1.0] for i in range(n)}
        super().__init__(name="TSPRandomKeys", dimension=n, bounds=bounds)

    def evaluate(self, x):
        tour = self.decoder.decode(np.asarray(x, dtype=float))
        total = 0.0
        for i in range(len(tour)):
            j = (i + 1) % len(tour)
            total += np.linalg.norm(self.cities[tour[i]] - self.cities[tour[j]])
        return [total]


def main():
    rng = np.random.default_rng(42)
    n_cities = 12
    cities = rng.uniform(0.0, 100.0, size=(n_cities, 2))

    problem = TSPRandomKeysProblem(cities)

    pipeline = RepresentationPipeline(
        initializer=RandomKeyInitializer(0.0, 1.0),
        repair=ClipRepair(0.0, 1.0),
        mutator=RandomKeyMutation(sigma=0.08, low=0.0, high=1.0),
        encoder=problem.decoder,
    )

    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 80
    solver.max_generations = 120
    solver.set_representation_pipeline(pipeline)

    result = solver.run()
    pareto = result.get("pareto_solutions") or {}
    objectives = pareto.get("objectives")
    individuals = pareto.get("individuals")

    if objectives is None or len(objectives) == 0:
        print("No solutions returned.")
        return

    best_idx = int(np.argmin(objectives[:, 0]))
    best_x = individuals[best_idx]
    best_tour = problem.decoder.decode(best_x)
    best_distance = float(objectives[best_idx, 0])

    print(f"Best distance: {best_distance:.4f}")
    print(f"Best tour: {best_tour.tolist()}")


if __name__ == "__main__":
    main()
