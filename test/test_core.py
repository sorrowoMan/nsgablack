"""
Test core functionality
"""

import unittest
import sys
import os
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.problems import ZDT1BlackBox, ZDT3BlackBox
    from core.solver import BlackBoxSolverNSGAII
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure you're running tests from the nsgablack directory")
    sys.exit(1)


class TestCore(unittest.TestCase):
    """Test core NSGA-II functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.problem = ZDT1BlackBox(dimension=10)
        self.solver = BlackBoxSolverNSGAII(self.problem)

    def test_problem_initialization(self):
        """Test problem initialization"""
        self.assertEqual(self.problem.dimension, 10)
        self.assertEqual(len(self.problem.bounds), 10)
        self.assertEqual(self.problem.n_objectives, 2)

    def test_solver_initialization(self):
        """Test solver initialization"""
        self.assertIsNotNone(self.solver.problem)
        self.assertEqual(self.solver.pop_size, 100)  # default value
        self.assertEqual(self.solver.max_generations, 100)  # default value

    def test_evaluation(self):
        """Test objective evaluation"""
        x = np.random.random(10)
        objectives = self.problem.evaluate(x)
        self.assertEqual(len(objectives), 2)
        self.assertTrue(all(isinstance(obj, (int, float)) for obj in objectives))

    def test_nsga2_run_short(self):
        """Test NSGA-II algorithm with short run"""
        # Use small population and generations for quick test
        self.solver.pop_size = 20
        self.solver.max_generations = 5

        result = self.solver.run()

        # Check result structure
        self.assertIn('pareto_solutions', result)
        self.assertIn('pareto_objectives', result)
        self.assertIn('generations', result)
        self.assertIn('evaluations', result)

        # Check Pareto front
        pareto_solutions = result['pareto_solutions']
        pareto_objectives = result['pareto_objectives']

        self.assertGreater(len(pareto_solutions), 0)
        self.assertEqual(len(pareto_solutions), len(pareto_objectives))

        # Check objectives shape
        for obj in pareto_objectives:
            self.assertEqual(len(obj), 2)

    def test_population_initialization(self):
        """Test population initialization"""
        self.solver.initialize_population()

        self.assertEqual(len(self.solver.population), self.solver.pop_size)
        self.assertEqual(len(self.solver.objectives), self.solver.pop_size)

        # Check bounds
        for individual in self.solver.population:
            self.assertEqual(len(individual), self.problem.dimension)
            for i, val in enumerate(individual):
                bounds = self.problem.bounds[i]
                self.assertGreaterEqual(val, bounds[0])
                self.assertLessEqual(val, bounds[1])

    def test_fast_non_dominated_sort(self):
        """Test fast non-dominated sorting"""
        # Create a small test population
        test_objectives = np.array([
            [0.0, 1.0],
            [0.5, 0.5],
            [1.0, 0.0],
            [0.2, 0.8],
            [0.8, 0.2]
        ])

        fronts = self.solver.fast_non_dominated_sort(test_objectives)

        # Should have at least one front
        self.assertGreater(len(fronts), 0)

        # First front should contain non-dominated solutions
        self.assertIn(0, fronts[0])  # [0.0, 1.0] should be in first front
        self.assertIn(2, fronts[0])  # [1.0, 0.0] should be in first front
        self.assertIn(1, fronts[0])  # [0.5, 0.5] should be in first front

    def test_crowding_distance(self):
        """Test crowding distance calculation"""
        # Create test objectives
        test_objectives = np.array([
            [0.0, 1.0],
            [0.5, 0.5],
            [1.0, 0.0],
            [0.2, 0.8],
            [0.8, 0.2]
        ])

        # First front (indices of non-dominated solutions)
        first_front = [0, 1, 2]

        distances = self.solver.calculate_crowding_distance(test_objectives, first_front)

        self.assertEqual(len(distances), len(first_front))

        # Boundary solutions should have infinite distance
        # For 2-objective problem with minimization, [0.0, 1.0] and [1.0, 0.0] are boundaries
        self.assertTrue(np.isinf(distances[first_front.index(0)]) or
                       np.isinf(distances[first_front.index(2)]))

    def test_constraint_handling(self):
        """Test constraint handling"""
        class ConstrainedTestProblem(ZDT1BlackBox):
            def __init__(self):
                super().__init__(dimension=2)
                self.n_constraints = 1

            def evaluate_constraints(self, x):
                # Simple constraint: x[0] + x[1] <= 1.0
                return [max(0, x[0] + x[1] - 1.0)]

        constrained_problem = ConstrainedTestProblem()
        solver = BlackBoxSolverNSGAII(constrained_problem)

        # Test constraint evaluation
        x1 = np.array([0.3, 0.4])  # feasible: 0.3 + 0.4 = 0.7 <= 1.0
        x2 = np.array([0.6, 0.6])  # infeasible: 0.6 + 0.6 = 1.2 > 1.0

        constraints1 = constrained_problem.evaluate_constraints(x1)
        constraints2 = constrained_problem.evaluate_constraints(x2)

        self.assertEqual(constraints1[0], 0.0)  # feasible
        self.assertGreater(constraints2[0], 0.0)  # infeasible


class TestDifferentProblems(unittest.TestCase):
    """Test with different problem types"""

    def test_zdt3_problem(self):
        """Test ZDT3 problem"""
        problem = ZDT3BlackBox(dimension=10)
        solver = BlackBoxSolverNSGAII(problem)

        solver.pop_size = 20
        solver.max_generations = 5

        result = solver.run()

        self.assertGreater(len(result['pareto_solutions']), 0)
        self.assertEqual(len(result['pareto_objectives']), len(result['pareto_solutions']))

    def test_different_dimensions(self):
        """Test with different problem dimensions"""
        for dim in [5, 10, 20]:
            with self.subTest(dimension=dim):
                problem = ZDT1BlackBox(dimension=dim)
                solver = BlackBoxSolverNSGAII(problem)

                solver.pop_size = 10
                solver.max_generations = 3

                result = solver.run()

                self.assertGreater(len(result['pareto_solutions']), 0)
                # Check solution dimensions
                for sol in result['pareto_solutions']:
                    self.assertEqual(len(sol), dim)


if __name__ == '__main__':
    unittest.main()