"""可选的等价向量化 Provider；使用同一问题公式，不调用 Problem.evaluate。"""
import numpy as np

from ..problem import RecipeProblem, recipe_cost


class RecipeProvider:
    name = "recipe_vectorized"
    semantic_mode = "equivalent"
    priority = 50
    allow_inner = False

    def can_handle_population(self, solver, population, context):
        return isinstance(solver.problem, RecipeProblem)

    def evaluate_population(self, solver, population, context):
        values = np.asarray(population, dtype=float)
        return recipe_cost(values).reshape(-1, 1), np.maximum(
            solver.problem.evaluate_constraints(values), 0.).sum(axis=1)

    def can_handle_individual(self, solver, x, context):
        return isinstance(solver.problem, RecipeProblem)

    def evaluate_individual(self, solver, x, context, individual_id=None):
        objectives, violations = self.evaluate_population(solver, np.asarray(x).reshape(1, -1), context)
        return objectives[0], float(violations[0])
