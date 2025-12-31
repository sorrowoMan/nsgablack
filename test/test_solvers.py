"""
Test different solvers
"""

import unittest
import sys
import os
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.problems import ZDT1BlackBox
    from solvers.nsga2 import BlackBoxSolverNSGAII
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure you're running tests from the nsgablack directory")
    sys.exit(1)


class TestNSGA2(unittest.TestCase):
    """Test NSGA-II solver"""

    def test_nsga2_basic_functionality(self):
        """Test basic NSGA-II functionality"""
        problem = ZDT1BlackBox(dimension=10)
        solver = BlackBoxSolverNSGAII(problem)

        # Configure for quick test
        solver.pop_size = 20
        solver.max_generations = 10

        result = solver.run()

        # Check result structure
        self.assertIn('pareto_solutions', result)
        self.assertIn('pareto_objectives', result)
        self.assertIn('generations', result)
        self.assertIn('evaluations', result)

        # Check Pareto front
        self.assertGreater(len(result['pareto_solutions']), 0)
        self.assertEqual(
            len(result['pareto_solutions']),
            len(result['pareto_objectives'])
        )

    def test_nsga2_parameters(self):
        """Test NSGA-II parameter settings"""
        problem = ZDT1BlackBox(dimension=5)
        solver = BlackBoxSolverNSGAII(problem)

        # Test parameter setting
        solver.pop_size = 50
        solver.max_generations = 20
        solver.crossover_rate = 0.8
        solver.mutation_rate = 0.1

        self.assertEqual(solver.pop_size, 50)
        self.assertEqual(solver.max_generations, 20)
        self.assertEqual(solver.crossover_rate, 0.8)
        self.assertEqual(solver.mutation_rate, 0.1)

    def test_nsga2_selection(self):
        """Test selection operators"""
        problem = ZDT1BlackBox(dimension=5)
        solver = BlackBoxSolverNSGAII(problem)

        # Initialize population
        solver.initialize_population()
        solver.evaluate_population()

        # Test selection
        selected = solver.selection()
        self.assertEqual(len(selected), solver.pop_size)
        self.assertEqual(len(selected[0]), problem.dimension)

    def test_nsga2_crossover(self):
        """Test crossover operators"""
        problem = ZDT1BlackBox(dimension=5)
        solver = BlackBoxSolverNSGAII(problem)

        parent1 = np.random.random(5)
        parent2 = np.random.random(5)

        child1, child2 = solver.crossover(parent1, parent2)

        self.assertEqual(len(child1), 5)
        self.assertEqual(len(child2), 5)

        # Check bounds
        for i in range(5):
            bounds = problem.bounds[i]
            self.assertGreaterEqual(child1[i], bounds[0])
            self.assertLessEqual(child1[i], bounds[1])
            self.assertGreaterEqual(child2[i], bounds[0])
            self.assertLessEqual(child2[i], bounds[1])

    def test_nsga2_mutation(self):
        """Test mutation operators"""
        problem = ZDT1BlackBox(dimension=5)
        solver = BlackBoxSolverNSGAII(problem)

        individual = np.random.random(5)
        mutated = solver.mutation(individual)

        self.assertEqual(len(mutated), 5)

        # Check bounds
        for i in range(5):
            bounds = problem.bounds[i]
            self.assertGreaterEqual(mutated[i], bounds[0])
            self.assertLessEqual(mutated[i], bounds[1])

    def test_nsga2_convergence(self):
        """Test NSGA-II convergence"""
        problem = ZDT1BlackBox(dimension=10)
        solver = BlackBoxSolverNSGAII(problem)

        # Run for more generations to test convergence
        solver.pop_size = 50
        solver.max_generations = 50

        result = solver.run()

        # For ZDT1 problem, check Pareto front properties
        pareto_objectives = np.array(result['pareto_objectives'])

        # Check if objectives are in reasonable range
        self.assertTrue(np.all(pareto_objectives >= 0))
        self.assertTrue(np.all(pareto_objectives[:, 0] <= 1.2))  # Some tolerance
        self.assertTrue(np.all(pareto_objectives[:, 1] <= 5.0))

        # Check diversity of solutions
        f1_values = pareto_objectives[:, 0]
        diversity = len(np.unique(np.round(f1_values, 2)))
        self.assertGreater(diversity, 3)  # Should have diverse solutions


class TestSolverIntegration(unittest.TestCase):
    """Test solver integration with other components"""

    def test_solver_with_custom_problem(self):
        """Test solver with custom problem definition"""
        class CustomProblem(ZDT1BlackBox):
            def __init__(self):
                super().__init__(dimension=3)
                self.n_constraints = 1

            def evaluate(self, x):
                f1 = x[0]**2
                f2 = (x[0] - 1)**2 + x[1]**2 + x[2]**2
                return [f1, f2]

            def evaluate_constraints(self, x):
                # Constraint: x[0] + x[1] + x[2] <= 2
                return [max(0, x[0] + x[1] + x[2] - 2)]

        problem = CustomProblem()
        solver = BlackBoxSolverNSGAII(problem)

        solver.pop_size = 30
        solver.max_generations = 20

        result = solver.run()

        self.assertGreater(len(result['pareto_solutions']), 0)

        # Check constraint satisfaction
        for sol in result['pareto_solutions']:
            self.assertLessEqual(sol[0] + sol[1] + sol[2], 2.1)  # Some tolerance

    def test_solver_reproducibility(self):
        """Test solver reproducibility with random seed"""
        problem = ZDT1BlackBox(dimension=10)

        # Run first time
        solver1 = BlackBoxSolverNSGAII(problem)
        solver1.pop_size = 20
        solver1.max_generations = 10
        solver1.random_seed = 42

        result1 = solver1.run()

        # Run second time with same seed
        solver2 = BlackBoxSolverNSGAII(problem)
        solver2.pop_size = 20
        solver2.max_generations = 10
        solver2.random_seed = 42

        result2 = solver2.run()

        # Results should be identical
        np.testing.assert_array_equal(
            np.array(result1['pareto_solutions']),
            np.array(result2['pareto_solutions'])
        )

    def test_solver_performance(self):
        """Test solver performance metrics"""
        problem = ZDT1BlackBox(dimension=10)
        solver = BlackBoxSolverNSGAII(problem)

        solver.pop_size = 50
        solver.max_generations = 30

        import time
        start_time = time.time()
        result = solver.run()
        end_time = time.time()

        elapsed_time = end_time - start_time

        # Performance checks
        self.assertLess(elapsed_time, 30.0)  # Should complete within 30 seconds
        self.assertEqual(result['generations'], 30)
        self.assertEqual(result['evaluations'], 30 * 50)  # generations * pop_size

        # Check memory usage (basic check)
        import sys
        pareto_size = sys.getsizeof(result['pareto_solutions'])
        self.assertLess(pareto_size, 1024 * 1024)  # Less than 1MB for solutions


if __name__ == '__main__':
    unittest.main()