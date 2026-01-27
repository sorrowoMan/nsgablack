"""
Test bias system functionality
"""

import unittest
import sys
import os
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from bias.bias_base import (
        BaseBias, AlgorithmicBias, DomainBias, OptimizationContext
    )
    from bias.bias_library_algorithmic import (
        DiversityBias, ConvergenceBias, ExplorationBias
    )
    from bias.bias_library_domain import (
        ConstraintBias, PreferenceBias, EngineeringDesignBias
    )
    from bias.bias import BiasModule
    # Note: UniversalBiasManager is in bias_v2.py which is not used anymore
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure you're running tests from the nsgablack directory")
    sys.exit(1)


class TestBiasBase(unittest.TestCase):
    """Test base bias classes"""

    def test_base_bias_initialization(self):
        """Test BaseBias initialization"""
        bias = BaseBias("test_bias", weight=1.0)
        self.assertEqual(bias.name, "test_bias")
        self.assertEqual(bias.weight, 1.0)
        self.assertTrue(bias.enabled)

    def test_algorithmic_bias(self):
        """Test AlgorithmicBias class"""
        bias = AlgorithmicBias("diversity", weight=0.5)
        self.assertEqual(bias.bias_type, "algorithmic")

    def test_domain_bias(self):
        """Test DomainBias class"""
        bias = DomainBias("constraint", weight=2.0)
        self.assertEqual(bias.bias_type, "domain")

    def test_optimization_context(self):
        """Test OptimizationContext"""
        population = np.random.random((50, 5))
        objectives = np.random.random((50, 2))
        constraints = np.random.random((50, 3))

        context = OptimizationContext(
            generation=100,
            population=population,
            objectives=objectives,
            constraints=constraints,
            best_objectives=[0.1, 0.2]
        )

        self.assertEqual(context.generation, 100)
        self.assertEqual(len(context.population), 50)
        self.assertEqual(context.population.shape[1], 5)
        self.assertEqual(len(context.best_objectives), 2)


class TestAlgorithmicBias(unittest.TestCase):
    """Test algorithmic bias implementations"""

    def test_diversity_bias(self):
        """Test DiversityBias"""
        bias = DiversityBias(weight=0.3)

        # Create test population
        population = np.array([
            [0.0, 0.0],
            [0.5, 0.5],
            [1.0, 1.0],
            [0.0, 1.0],
            [1.0, 0.0]
        ])

        context = OptimizationContext(
            generation=50,
            population=population,
            objectives=None,
            constraints=None
        )

        bias_values = bias.apply_bias(population, context)

        self.assertEqual(len(bias_values), len(population))
        self.assertTrue(all(isinstance(val, (int, float)) for val in bias_values))

    def test_convergence_bias(self):
        """Test ConvergenceBias"""
        bias = ConvergenceBias(weight=0.2)

        population = np.random.random((30, 3))
        objectives = np.random.random((30, 2))

        context = OptimizationContext(
            generation=50,
            population=population,
            objectives=objectives,
            constraints=None
        )

        bias_values = bias.apply_bias(population, context)
        self.assertEqual(len(bias_values), len(population))

    def test_exploration_bias(self):
        """Test ExplorationBias"""
        bias = ExplorationBias(weight=0.4)

        population = np.random.random((20, 4))
        context = OptimizationContext(
            generation=10,  # Early generation
            population=population,
            objectives=None,
            constraints=None
        )

        bias_values = bias.apply_bias(population, context)
        self.assertEqual(len(bias_values), len(population))


class TestDomainBias(unittest.TestCase):
    """Test domain bias implementations"""

    def test_constraint_bias(self):
        """Test ConstraintBias"""
        bias = ConstraintBias(weight=5.0)

        # Add a simple constraint
        bias.add_hard_constraint(lambda x: max(0, x[0] + x[1] - 1.0))

        # Test feasible and infeasible solutions
        feasible_x = np.array([0.2, 0.3])  # Sum = 0.5 <= 1.0
        infeasible_x = np.array([0.6, 0.6])  # Sum = 1.2 > 1.0

        feasible_pop = np.array([feasible_x, feasible_x])
        infeasible_pop = np.array([infeasible_x, infeasible_x])

        context = OptimizationContext(
            generation=1,
            population=None,
            objectives=None,
            constraints=None
        )

        feasible_bias = bias.apply_bias(feasible_pop, context)
        infeasible_bias = bias.apply_bias(infeasible_pop, context)

        # Infeasible solutions should have higher penalty
        self.assertGreater(np.mean(infeasible_bias), np.mean(feasible_bias))

    def test_preference_bias(self):
        """Test PreferenceBias"""
        bias = PreferenceBias(weight=0.5)

        # Add a soft preference (prefer smaller first dimension)
        bias.add_soft_constraint(lambda x: x[0])  # Minimize x[0]

        population = np.array([
            [0.1, 0.5],
            [0.5, 0.5],
            [0.9, 0.5]
        ])

        context = OptimizationContext(
            generation=1,
            population=population,
            objectives=None,
            constraints=None
        )

        bias_values = bias.apply_bias(population, context)

        # Solution with smallest x[0] should have lowest bias value
        self.assertEqual(bias_values[0], min(bias_values))

    def test_engineering_design_bias(self):
        """Test EngineeringDesignBias"""
        bias = EngineeringDesignBias(weight=1.0)

        # Add safety factors
        bias.add_safety_factor("stress_limit", 1.5)
        self.assertEqual(bias.safety_factors["stress_limit"], 1.5)


class TestBiasModule(unittest.TestCase):
    """Test BiasModule (replacement for UniversalBiasManager)"""

    def test_module_initialization(self):
        """Test BiasModule initialization"""
        bias_module = BiasModule()
        self.assertIsNotNone(bias_module)

    def test_bias_addition(self):
        """Test adding bias functions"""
        bias_module = BiasModule()

        # Add reward function
        bias_module.add_reward_function("test_reward", lambda x: x[0]**2)
        self.assertIn("test_reward", bias_module.reward_functions)

        # Add penalty function
        bias_module.add_penalty_function("test_penalty", lambda x: max(0, x[0] - 1.0))
        self.assertIn("test_penalty", bias_module.penalty_functions)

    def test_bias_application(self):
        """Test bias application to solutions"""
        bias_module = BiasModule()

        # Add simple penalty function
        bias_module.add_penalty_function("boundary", lambda x: max(0, x[0] - 0.5))

        # Test feasible and infeasible solutions
        feasible = np.array([0.3, 0.4])
        infeasible = np.array([0.7, 0.4])

        feasible_fitness = bias_module.apply_bias(feasible, np.array([1.0]))
        infeasible_fitness = bias_module.apply_bias(infeasible, np.array([1.0]))

        # Infeasible solution should have higher (worse) fitness
        self.assertGreater(infeasible_fitness, feasible_fitness)

    def test_multiple_biases(self):
        """Test multiple bias functions"""
        bias_module = BiasModule()

        # Add multiple bias functions
        bias_module.add_reward_function("minimize_x1", lambda x: -x[0])  # Reward small x[0]
        bias_module.add_penalty_function("boundary", lambda x: max(0, x[0] - 0.5))
        bias_module.add_penalty_function("boundary2", lambda x: max(0, -x[0] + 0.1))  # x[0] >= 0.1

        # Test solution
        x = np.array([0.3, 0.5])
        base_fitness = 1.0

        biased_fitness = bias_module.apply_bias(x, base_fitness)

        # Should be modified by biases
        self.assertNotEqual(biased_fitness, base_fitness)


class TestBiasIntegration(unittest.TestCase):
    """Test bias system integration with solver"""

    def test_solver_with_bias(self):
        """Test solver with bias system"""
        from core.problems import ZDT1BlackBox
        from core.solver import BlackBoxSolverNSGAII

        # Create problem and solver
        problem = ZDT1BlackBox(dimension=10)
        solver = BlackBoxSolverNSGAII(problem)

        # Create bias module
        bias_module = BiasModule()

        # Add simple penalty function
        bias_module.add_penalty_function(
            "x0_boundary",
            lambda x: max(0, x[0] - 0.8)  # Penalty if x[0] > 0.8
        )

        # Set bias module to solver
        solver.bias_module = bias_module
        solver.enable_bias = True

        # Run short test
        solver.pop_size = 20
        solver.max_generations = 5

        result = solver.run()

        self.assertGreater(len(result['pareto_solutions']), 0)

        # Test that bias module was used
        self.assertTrue(solver.enable_bias)


if __name__ == '__main__':
    unittest.main()