"""
测试核心求解器（Core Solver）

测试EvolutionSolver的基本功能。
"""
import pytest
import numpy as np
import sys
from pathlib import Path

# 添加项目根目录到路径

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver


class SimpleSphere(BlackBoxProblem):
    """简单的Sphere测试问题。"""

    def __init__(self, dimension=2):
        super().__init__(
            dimension=dimension,
            objectives=["minimize"],
            bounds=[(-10, 10)] * dimension
        )

    def evaluate(self, x):
        """Sphere函数：f(x) = sum(x^2)。"""
        return np.sum(x**2)


class SimpleRastrigin(BlackBoxProblem):
    """简单的Rastrigin测试问题。"""

    def __init__(self, dimension=2):
        super().__init__(
            dimension=dimension,
            objectives=["minimize"],
            bounds=[(-5.12, 5.12)] * dimension
        )

    def evaluate(self, x):
        """Rastrigin函数。"""
        A = 10
        return A * len(x) + np.sum(x**2 - A * np.cos(2 * np.pi * x))


class TestBlackBoxProblem:
    """测试BlackBoxProblem基类。"""

    def test_problem_initialization(self):
        """测试问题初始化。"""
        problem = SimpleSphere(dimension=3)

        assert problem.dimension == 3
        assert problem.get_num_objectives() == 1
        assert len(problem.bounds) == 3

    def test_bounds_checking(self):
        """测试边界检查。"""
        problem = SimpleSphere()

        # 有效点
        x_valid = np.array([5.0, 3.0])
        assert problem.is_valid(x_valid)

        # 无效点（超出边界）
        x_invalid = np.array([15.0, 3.0])
        assert not problem.is_valid(x_invalid)

    def test_evaluate(self):
        """测试评估函数。"""
        problem = SimpleSphere()

        x = np.array([1.0, 2.0])
        f = problem.evaluate(x)

        # 1^2 + 2^2 = 5
        assert np.isclose(f, 5.0)


class TestSolverInitialization:
    """测试求解器初始化。"""

    def test_solver_creation(self, sample_problem):
        """测试求解器创建。"""
        solver = EvolutionSolver(sample_problem)

        assert solver.problem == sample_problem
        assert solver.dimension == sample_problem.dimension
        assert solver.num_objectives == 1

    def test_solver_default_params(self, sample_problem):
        """测试求解器默认参数。"""
        solver = EvolutionSolver(sample_problem)

        # 检查默认参数
        assert hasattr(solver, 'pop_size')
        assert hasattr(solver, 'max_generations')


@pytest.mark.unit
class TestSolverBasicOperations:
    """测试求解器基本操作。"""

    def test_initialize_population(self, sample_problem):
        """测试种群初始化。"""
        solver = EvolutionSolver(sample_problem)
        solver.initialize_population()

        # 检查种群大小
        assert len(solver.population) == solver.pop_size

        # 检查个体维度
        for individual in solver.population:
            assert len(individual) == solver.dimension

        # 检查边界
        for individual in solver.population:
            assert sample_problem.is_valid(individual)

    def test_evaluate_population(self, sample_problem):
        """测试种群评估。"""
        solver = EvolutionSolver(sample_problem)
        solver.initialize_population()

        # 评估种群
        for individual in solver.population:
            f = sample_problem.evaluate(individual)
            assert f >= 0  # Sphere函数非负


@pytest.mark.slow
class TestSolverOptimization:
    """测试求解器优化过程（慢速测试）。"""

    def test_simple_optimization(self):
        """测试简单优化问题。"""
        problem = SimpleSphere(dimension=2)
        solver = EvolutionSolver(problem)
        solver.max_generations = 10
        solver.pop_size = 20

        # 运行优化
        best_x, best_f = solver.run()

        # 检查结果
        assert best_x is not None
        assert best_f is not None
        assert len(best_x) == 2
        assert best_f < 100.0  # 应该能找到相对好的解
        assert problem.is_valid(best_x)

    def test_rastrigin_optimization(self):
        """测试Rastrigin优化问题。"""
        problem = SimpleRastrigin(dimension=2)
        solver = EvolutionSolver(problem)
        solver.max_generations = 20
        solver.pop_size = 50

        # 运行优化
        best_x, best_f = solver.run()

        # 检查结果
        assert best_x is not None
        assert best_f is not None
        assert len(best_x) == 2
        assert best_f < 50.0  # Rastrigin函数的全局最优是0
        assert problem.is_valid(best_x)


class TestSolverWithBias:
    """测试带偏置的求解器。"""

    def test_solver_with_penalty_bias(self, sample_problem):
        """测试带罚函数偏置的求解器。"""
        from nsgablack.bias import BiasModule
        from nsgablack.bias.domain import CallableBias

        # 创建偏置：惩罚远离原点的解
        bias = BiasModule()

        def far_from_origin_penalty(x, constraints, context):
            distance = np.linalg.norm(x)
            return {"penalty": max(0, distance - 5)}

        bias.add(CallableBias(name="far_from_origin", func=far_from_origin_penalty, weight=2.0, mode="penalty"))

        # 创建求解器
        solver = EvolutionSolver(sample_problem)
        solver.max_generations = 10

        # 运行优化
        best_x, best_f = solver.run()

        # 检查结果
        assert best_x is not None
        # 解应该在原点附近（因为Sphere函数本身就趋向原点）
        assert np.linalg.norm(best_x) < 10.0

    @pytest.mark.slow
    def test_solver_with_convergence_bias(self):
        """测试带收敛加速偏置的求解器。"""
        from nsgablack.bias import BiasModule
        from nsgablack.bias.algorithmic.convergence import ConvergenceBias

        problem = SimpleSphere(dimension=5)
        bias = BiasModule()
        conv_bias = ConvergenceBias()

        bias.add(conv_bias, weight=0.5)

        solver = EvolutionSolver(problem)
        solver.max_generations = 15

        best_x, best_f = solver.run()

        assert best_x is not None
        assert best_f < 50.0


class TestSolverReproducibility:
    """测试求解器可重复性。"""

    def test_fixed_seed_reproducibility(self):
        """测试固定种子的可重复性。"""
        problem = SimpleSphere(dimension=2)

        # 第一次运行
        np.random.seed(42)
        solver1 = EvolutionSolver(problem)
        solver1.max_generations = 5
        best_x1, best_f1 = solver1.run()

        # 第二次运行（相同种子）
        np.random.seed(42)
        solver2 = EvolutionSolver(problem)
        solver2.max_generations = 5
        best_x2, best_f2 = solver2.run()

        # 结果应该相同
        assert np.allclose(best_x1, best_x2)
        assert np.isclose(best_f1, best_f2)


@pytest.mark.integration
class TestSolverIntegration:
    """测试求解器集成场景。"""

    def test_multi_start_optimization(self):
        """测试多次启动优化。"""
        problem = SimpleSphere(dimension=2)

        results = []
        for i in range(3):
            np.random.seed(i)
            solver = EvolutionSolver(problem)
            solver.max_generations = 10
            best_x, best_f = solver.run()
            results.append((best_x, best_f))

        # 所有运行都应该找到解
        for best_x, best_f in results:
            assert best_x is not None
            assert best_f < 100.0
            assert problem.is_valid(best_x)

    def test_high_dimensional_optimization(self):
        """测试高维优化。"""
        dimension = 10
        problem = SimpleSphere(dimension=dimension)

        solver = EvolutionSolver(problem)
        solver.max_generations = 20
        solver.pop_size = 100

        best_x, best_f = solver.run()

        assert best_x is not None
        assert len(best_x) == dimension
        assert best_f < 500.0  # 高维问题允许较大的目标值
        assert problem.is_valid(best_x)
