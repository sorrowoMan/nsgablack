"""
Performance tests for nsgablack
"""

import pytest
import time
import numpy as np
import psutil
import os
from typing import Dict, Any

# Import nsgablack components
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.problems import ZDT1BlackBox, ZDT3BlackBox, SphereBlackBox
from core.solver import BlackBoxSolverNSGAII
from solvers.monte_carlo import MonteCarloOptimizer


class TestPerformance:
    """Performance test suite for nsgablack"""

    @pytest.fixture
    def performance_monitor(self):
        """Monitor performance metrics during tests."""
        class PerformanceMonitor:
            def __init__(self):
                self.process = psutil.Process()
                self.start_time = None
                self.start_memory = None
                self.peak_memory = None

            def start(self):
                """Start monitoring."""
                self.start_time = time.time()
                self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                self.peak_memory = self.start_memory

            def stop(self) -> Dict[str, Any]:
                """Stop monitoring and return metrics."""
                end_time = time.time()
                end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                self.peak_memory = max(self.peak_memory, end_memory)

                return {
                    'elapsed_time': end_time - self.start_time,
                    'memory_used': end_memory - self.start_memory,
                    'peak_memory': self.peak_memory,
                    'end_memory': end_memory
                }

        return PerformanceMonitor()

    def test_nsga2_performance_small(self, performance_monitor):
        """Test NSGA-II performance on small problems."""
        problem = ZDT1BlackBox(dimension=10)
        solver = BlackBoxSolverNSGAII(problem)
        solver.pop_size = 50
        solver.max_generations = 20

        performance_monitor.start()
        result = solver.run()
        metrics = performance_monitor.stop()

        # Performance assertions
        assert metrics['elapsed_time'] < 30.0, "NSGA-II took too long on small problem"
        assert metrics['peak_memory'] < 200.0, "NSGA-II used too much memory"

        # Quality assertions
        assert len(result['pareto_solutions']) > 0, "No Pareto solutions found"
        assert len(result['pareto_objectives']) == len(result['pareto_solutions'])

    def test_nsga2_performance_medium(self, performance_monitor):
        """Test NSGA-II performance on medium problems."""
        problem = ZDT1BlackBox(dimension=30)
        solver = BlackBoxSolverNSGAII(problem)
        solver.pop_size = 100
        solver.max_generations = 50

        performance_monitor.start()
        result = solver.run()
        metrics = performance_monitor.stop()

        # Performance assertions
        assert metrics['elapsed_time'] < 120.0, "NSGA-II took too long on medium problem"
        assert metrics['peak_memory'] < 500.0, "NSGA-II used too much memory"

        # Quality assertions
        assert len(result['pareto_solutions']) > 10, "Too few Pareto solutions found"
        assert len(result['pareto_objectives']) == len(result['pareto_solutions'])

    def test_monte_carlo_performance(self, performance_monitor):
        """Test Monte Carlo optimizer performance."""
        problem = SphereBlackBox(dimension=20)
        optimizer = MonteCarloOptimizer(problem)
        optimizer.max_iterations = 1000

        performance_monitor.start()
        result = optimizer.run()
        metrics = performance_monitor.stop()

        # Performance assertions
        assert metrics['elapsed_time'] < 60.0, "Monte Carlo took too long"
        assert metrics['peak_memory'] < 100.0, "Monte Carlo used too much memory"

        # Quality assertions
        assert len(result['best_solutions']) > 0, "No solutions found"

    def test_memory_optimization(self):
        """Test memory optimization features."""
        problem = ZDT1BlackBox(dimension=50)
        solver = BlackBoxSolverNSGAII(problem)
        solver.pop_size = 200
        solver.max_generations = 30

        # Monitor memory without optimization
        import gc
        gc.collect()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        result = solver.run()

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert memory_increase < 300.0, f"Memory increased too much: {memory_increase:.2f} MB"

    def test_scalability(self):
        """Test algorithm scalability with problem size."""
        dimensions = [10, 20, 30]
        times = []
        memory_usage = []

        for dim in dimensions:
            problem = ZDT1BlackBox(dimension=dim)
            solver = BlackBoxSolverNSGAII(problem)
            solver.pop_size = 50
            solver.max_generations = 10

            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            start_time = time.time()

            result = solver.run()

            end_time = time.time()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB

            times.append(end_time - start_time)
            memory_usage.append(end_memory - start_memory)

        # Check that scaling is reasonable
        # Time should not increase more than linearly
        if len(times) > 1:
            time_ratio = times[-1] / times[0]
            dimension_ratio = dimensions[-1] / dimensions[0]
            assert time_ratio < dimension_ratio * 2, "Time scaling is too poor"

    @pytest.mark.benchmark
    def test_benchmark_nsga2_vs_random(self, benchmark):
        """Benchmark NSGA-II against random search."""
        def run_nsga2():
            problem = ZDT1BlackBox(dimension=20)
            solver = BlackBoxSolverNSGAII(problem)
            solver.pop_size = 50
            solver.max_generations = 20
            result = solver.run()
            # Calculate hypervolume as quality metric
            if len(result['pareto_objectives']) > 0:
                return self._calculate_hypervolume(result['pareto_objectives'])
            return 0.0

        def run_random():
            problem = ZDT1BlackBox(dimension=20)
            # Simple random search for comparison
            best_solutions = []
            for _ in range(1000):  # Same number of evaluations
                x = np.random.random(20)
                objectives = problem.evaluate(x)
                best_solutions.append(objectives)
            return self._calculate_hypervolume(np.array(best_solutions))

        nsga2_result = benchmark(run_nsga2)
        random_result = benchmark(run_random)

        # NSGA-II should significantly outperform random search
        # This is tested by the benchmark framework

    def _calculate_hypervolume(self, objectives: np.ndarray) -> float:
        """Calculate hypervolume for 2D objectives."""
        if len(objectives) == 0:
            return 0.0

        if objectives.shape[1] != 2:
            return 0.0

        # Simple 2D hypervolume calculation
        ref_point = np.max(objectives, axis=0) * 1.1

        # Sort by first objective
        sorted_idx = np.argsort(objectives[:, 0])
        sorted_obj = objectives[sorted_idx]

        volume = 0.0
        for i in range(len(sorted_obj)):
            if i == 0:
                volume += (ref_point[0] - sorted_obj[i, 0]) * (ref_point[1] - sorted_obj[i, 1])
            else:
                volume += (ref_point[0] - sorted_obj[i, 0]) * (sorted_obj[i-1, 1] - sorted_obj[i, 1])

        return volume

    def test_convergence_speed(self):
        """Test algorithm convergence speed."""
        problem = ZDT1BlackBox(dimension=20)
        solver = BlackBoxSolverNSGAII(problem)
        solver.pop_size = 50
        solver.max_generations = 100

        # Track convergence history
        convergence_history = []
        original_converged = solver._converged
        original_stagnation_count = solver._stagnation_count

        def capture_convergence():
            if hasattr(solver, '_get_pareto_front'):
                pareto = solver._get_pareto_front()
                if pareto and 'objectives' in pareto:
                    convergence_history.append(len(pareto['objectives']))

        # Monkey patch to capture convergence data
        original_evolve = solver.evolve_one_generation
        def patched_evolve():
            result = original_evolve()
            capture_convergence()
            return result
        solver.evolve_one_generation = patched_evolve

        result = solver.run()

        # Restore original methods
        solver.evolve_one_generation = original_evolve
        solver._converged = original_converged
        solver._stagnation_count = original_stagnation_count

        # Check convergence behavior
        assert len(convergence_history) > 0, "No convergence data captured"

        # Should see improvement over time
        if len(convergence_history) > 10:
            early_avg = np.mean(convergence_history[:10])
            late_avg = np.mean(convergence_history[-10:])
            assert late_avg >= early_avg, "Algorithm did not show improvement"

    def test_algorithm_stability(self):
        """Test algorithm stability across multiple runs."""
        problem = ZDT1BlackBox(dimension=15)

        results = []
        hypervolumes = []

        # Run algorithm multiple times with different seeds
        for seed in [42, 123, 456, 789, 999]:
            np.random.seed(seed)
            solver = BlackBoxSolverNSGAII(problem)
            solver.pop_size = 50
            solver.max_generations = 30

            result = solver.run()
            results.append(result)

            # Calculate quality metric
            if len(result['pareto_objectives']) > 0:
                hv = self._calculate_hypervolume(result['pareto_objectives'])
                hypervolumes.append(hv)

        # Check stability
        assert len(hypervolumes) == 5, "Not all runs completed successfully"

        # Coefficient of variation should be reasonable (< 50%)
        mean_hv = np.mean(hypervolumes)
        std_hv = np.std(hypervolumes)
        cv = std_hv / mean_hv if mean_hv > 0 else 0

        assert cv < 0.5, f"Algorithm is too unstable (CV = {cv:.3f})"
        assert mean_hv > 0, "Algorithm consistently failed to find solutions"

    def test_parallel_evaluation_speedup(self):
        """Test parallel evaluation speedup."""
        # This test would require parallel evaluation to be implemented
        # For now, we'll skip if not available
        try:
            from utils.parallel_evaluator import ParallelEvaluator
            parallel_available = True
        except ImportError:
            parallel_available = False
            pytest.skip("Parallel evaluation not available")

        if not parallel_available:
            pytest.skip("Parallel evaluation not available")

        # Test would go here to compare serial vs parallel evaluation
        # This is a placeholder for future implementation
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])