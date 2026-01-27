"""
Performance comparison between nsgablack and other optimization frameworks
"""

import time
import json
import numpy as np
import sys
import os
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.problems import ZDT1BlackBox, ZDT3BlackBox, SphereBlackBox
from core.solver import BlackBoxSolverNSGAII
from solvers.monte_carlo import MonteCarloOptimizer


class PerformanceComparison:
    """Compare nsgablack performance with other frameworks."""

    def __init__(self):
        self.results = {
            'nsgablack': {},
            'other_frameworks': {},
            'problems': {},
            'timestamp': time.time()
        }

    def run_nsgablack_tests(self) -> Dict[str, Any]:
        """Run performance tests with nsgablack."""
        print("Running nsgablack performance tests...")

        results = {}

        # Test problems
        problems = {
            'ZDT1_10D': ZDT1BlackBox(dimension=10),
            'ZDT1_30D': ZDT1BlackBox(dimension=30),
            'ZDT3_20D': ZDT3BlackBox(dimension=20),
            'Sphere_20D': SphereBlackBox(dimension=20),
        }

        for problem_name, problem in problems.items():
            print(f"  Testing {problem_name}...")

            # NSGA-II test
            solver = BlackBoxSolverNSGAII(problem)
            solver.pop_size = 50
            solver.max_generations = 50

            start_time = time.time()
            start_memory = self._get_memory_usage()

            result = solver.run()

            end_time = time.time()
            end_memory = self._get_memory_usage()

            performance = {
                'time': end_time - start_time,
                'memory_mb': end_memory - start_memory,
                'pareto_size': len(result['pareto_solutions']),
                'generations': result['generations'],
                'evaluations': result['evaluations'],
                'hypervolume': self._calculate_hypervolume(result['pareto_objectives']),
                'converged': result.get('converged', False)
            }

            results[problem_name] = performance

        return results

    def run_other_framework_tests(self) -> Dict[str, Any]:
        """Run tests with other frameworks if available."""
        print("Testing other frameworks...")

        results = {}

        # Try pymoo
        try:
            results['pymoo'] = self._test_pymoo()
        except ImportError:
            print("  pymoo not available")
        except Exception as e:
            print(f"  pymoo test failed: {e}")

        # Try DEAP
        try:
            results['deap'] = self._test_deap()
        except ImportError:
            print("  DEAP not available")
        except Exception as e:
            print(f"  DEAP test failed: {e}")

        return results

    def _test_pymoo(self) -> Dict[str, Any]:
        """Test pymoo framework."""
        import pymoo
        from pymoo.algorithms.moo.nsga2 import NSGA2
        from pymoo.factory import get_problem, get_sampling, get_crossover, get_mutation
        from pymoo.optimize import minimize

        results = {}

        # Test ZDT1 problem
        problem = get_problem("zdt1", n_var=30)
        algorithm = NSGA2(
            pop_size=50,
            sampling=get_sampling("real_random"),
            crossover=get_crossover("real_sbx", prob=0.9, eta=15),
            mutation=get_mutation("real_pm", eta=20),
            eliminate_duplicates=True
        )

        start_time = time.time()
        start_memory = self._get_memory_usage()

        res = minimize(problem,
                      algorithm,
                      termination=('n_gen', 50),
                      verbose=False)

        end_time = time.time()
        end_memory = self._get_memory_usage()

        results['ZDT1_30D'] = {
            'time': end_time - start_time,
            'memory_mb': end_memory - start_memory,
            'pareto_size': len(res.F),
            'hypervolume': self._calculate_hypervolume_pymoo(res.F)
        }

        return results

    def _test_deap(self) -> Dict[str, Any]:
        """Test DEAP framework."""
        import random
        from deap import base, creator, tools

        results = {}

        # Create types (only once)
        if not hasattr(creator, "FitnessMin"):
            creator.create("FitnessMin", base.Fitness, weights=(-1.0, -1.0))
            creator.create("Individual", list, fitness=creator.FitnessMin)

        # ZDT1 problem function
        def zdt1(individual):
            x = individual
            f1 = x[0]
            g = 1 + 9 * sum(x[1:]) / (len(x) - 1)
            f2 = g * (1 - np.sqrt(f1 / g))
            return f1, f2

        toolbox = base.Toolbox()
        toolbox.register("attr_float", random.random)
        toolbox.register("individual", tools.initRepeat, creator.Individual,
                        toolbox.attr_float, n=30)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register("evaluate", zdt1)
        toolbox.register("mate", tools.cxSBX)
        toolbox.register("mutate", tools.mutPolynomialBounded, low=0.0, up=1.0, eta=20.0, indpb=1.0/30)
        toolbox.register("select", tools.selNSGA2)

        # Create initial population
        pop = toolbox.population(n=50)

        # Evaluate initial population
        fitnesses = list(map(toolbox.evaluate, pop))
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit

        # Run algorithm
        start_time = time.time()
        start_memory = self._get_memory_usage()

        # This is a simplified NSGA-II implementation for testing
        for gen in range(50):
            # Select and evolve
            offspring = tools.selTournamentDCD(pop, len(pop))
            offspring = [toolbox.clone(ind) for ind in offspring]

            # Apply crossover and mutation
            for ind1, ind2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < 0.9:
                    toolbox.mate(ind1, ind2)
                    del ind1.fitness.values, ind2.fitness.values

            for ind in offspring:
                if random.random() < 0.1:
                    toolbox.mutate(ind)
                    del ind.fitness.values

            # Evaluate new individuals
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit

            # Select next generation
            pop = toolbox.select(pop + offspring, len(pop))

        end_time = time.time()
        end_memory = self._get_memory_usage()

        # Extract Pareto front
        pareto_front = tools.sortNondominated(pop)

        results['ZDT1_30D'] = {
            'time': end_time - start_time,
            'memory_mb': end_memory - start_memory,
            'pareto_size': len(pareto_front),
            'hypervolume': self._calculate_hypervolume_deap(pareto_front)
        }

        return results

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0

    def _calculate_hypervolume(self, objectives: np.ndarray) -> float:
        """Calculate hypervolume for nsgablack objectives."""
        if len(objectives) == 0 or objectives.shape[1] != 2:
            return 0.0

        ref_point = np.max(objectives, axis=0) * 1.1
        sorted_idx = np.argsort(objectives[:, 0])
        sorted_obj = objectives[sorted_idx]

        volume = 0.0
        for i in range(len(sorted_obj)):
            if i == 0:
                volume += (ref_point[0] - sorted_obj[i, 0]) * (ref_point[1] - sorted_obj[i, 1])
            else:
                volume += (ref_point[0] - sorted_obj[i, 0]) * (sorted_obj[i-1, 1] - sorted_obj[i, 1])

        return volume

    def _calculate_hypervolume_pymoo(self, objectives: np.ndarray) -> float:
        """Calculate hypervolume for pymoo objectives."""
        if len(objectives) == 0:
            return 0.0
        return self._calculate_hypervolume(objectives)

    def _calculate_hypervolume_deap(self, individuals: List) -> float:
        """Calculate hypervolume for DEAP individuals."""
        if len(individuals) == 0:
            return 0.0

        objectives = np.array([ind.fitness.values for ind in individuals])
        return self._calculate_hypervolume(objectives)

    def run_comparison(self) -> Dict[str, Any]:
        """Run complete performance comparison."""
        print("Starting performance comparison...")

        # Test nsgablack
        self.results['nsgablack'] = self.run_nsgablack_tests()

        # Test other frameworks
        self.results['other_frameworks'] = self.run_other_framework_tests()

        # Analyze results
        self._analyze_results()

        return self.results

    def _analyze_results(self):
        """Analyze and compare results."""
        print("\nAnalyzing results...")

        nsgablack_results = self.results['nsgablack']
        other_results = self.results['other_frameworks']

        # Compare with other frameworks
        if 'pymoo' in other_results:
            self._compare_with_framework('pymoo', other_results['pymoo'])

        if 'deap' in other_results:
            self._compare_with_framework('DEAP', other_results['deap'])

    def _compare_with_framework(self, framework_name: str, framework_results: Dict[str, Any]):
        """Compare nsgablack with a specific framework."""
        print(f"\n{framework_name} comparison:")

        nsgablack_results = self.results['nsgablack']

        for problem in ['ZDT1_10D', 'ZDT1_30D']:
            if problem in nsgablack_results and problem in framework_results:
                nsga_result = nsgablack_results[problem]
                other_result = framework_results[problem]

                print(f"  {problem}:")
                print(f"    Time: nsgablack={nsga_result['time']:.2f}s, {framework_name}={other_result['time']:.2f}s")
                print(f"    Memory: nsgablack={nsga_result['memory_mb']:.1f}MB, {framework_name}={other_result['memory_mb']:.1f}MB")
                print(f"    Pareto size: nsgablack={nsga_result['pareto_size']}, {framework_name}={other_result['pareto_size']}")

                if 'hypervolume' in nsga_result and 'hypervolume' in other_result:
                    print(f"    Hypervolume: nsgablack={nsga_result['hypervolume']:.4f}, {framework_name}={other_result['hypervolume']:.4f}")

    def save_results(self, filename: str = 'performance_results.json'):
        """Save results to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\nResults saved to {filename}")

    def print_summary(self):
        """Print a summary of the comparison."""
        print("\n" + "="*50)
        print("PERFORMANCE COMPARISON SUMMARY")
        print("="*50)

        nsgablack_results = self.results['nsgablack']

        print("\nnsgablack Performance:")
        for problem, result in nsgablack_results.items():
            print(f"  {problem}:")
            print(f"    Time: {result['time']:.2f}s")
            print(f"    Memory: {result['memory_mb']:.1f}MB")
            print(f"    Pareto size: {result['pareto_size']}")
            print(f"    Hypervolume: {result['hypervolume']:.4f}")

        print(f"\nTest completed at: {time.ctime(self.results['timestamp'])}")


if __name__ == '__main__':
    comparison = PerformanceComparison()
    results = comparison.run_comparison()
    comparison.save_results()
    comparison.print_summary()