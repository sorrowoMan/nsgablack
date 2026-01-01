import os
import sys
from typing import List

import numpy as np


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.base import BlackBoxProblem
from solvers.multi_agent import MultiAgentBlackBoxSolver
from bias.bias import BiasModule
from multi_agent.core.role import AgentRole


class BoxConstrainedBiObjective(BlackBoxProblem):
    def __init__(self):
        bounds = np.array([[0.0, 1.0], [0.0, 1.0]], dtype=float)
        super().__init__(name="BoxConstrainedBiObjective", dimension=2, bounds=bounds)

    def evaluate(self, x: np.ndarray) -> List[float]:
        f1 = x[0] ** 2 + x[1] ** 2
        f2 = (x[0] - 1.0) ** 2 + (x[1] - 1.0) ** 2
        return [f1, f2]

    def get_num_objectives(self):
        return 2


def constraint_penalty(x, constraints, context):
    violation = max(0.0, x[0] + x[1] - 1.0)
    return {"penalty": violation, "constraint": violation}


def score_bias(x, constraints, context):
    violation = float(context.get("constraint_violation", 0.0))
    score = 0.2 if violation == 0.0 else -0.2

    archives = context.get("archives") or {}
    diversity_archive = archives.get("diversity") or []
    if diversity_archive:
        sample = diversity_archive[: min(5, len(diversity_archive))]
        distances = [float(np.linalg.norm(x - item["x"])) for item in sample]
        score += 0.05 * min(distances)

    return {"score": score}


def main():
    np.random.seed(42)

    problem = BoxConstrainedBiObjective()

    bias = BiasModule()
    bias.add_penalty(constraint_penalty, weight=10.0, name="sum_limit")

    config = {
        "total_population": 80,
        "max_generations": 50,
        "communication_interval": 5,
        "adaptation_interval": 10,
        "archive_enabled": True,
        "archive_sizes": {"feasible": 160, "boundary": 80, "diversity": 160},
        "archive_share_k": 3,
        "global_score_biases": [score_bias],
        "role_score_biases": {
            AgentRole.EXPLORER: [score_bias],
            AgentRole.EXPLOITER: [score_bias],
        },
    }

    solver = MultiAgentBlackBoxSolver(problem, config)
    solver.bias_module = bias
    solver.enable_bias = True

    pareto_front = solver.run()
    print("pareto_size:", len(pareto_front))
    for idx, item in enumerate(pareto_front[:3]):
        print(f"{idx}: objectives={item['objectives']} constraints={item['constraints']}")


if __name__ == "__main__":
    main()
