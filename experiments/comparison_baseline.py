"""
手工实现的SA-TS混合算法（Hybrid SATS Baseline）

这是用于对比的baseline，代表"传统手工实现"的混合算法。
经过精心设计和调优，代表混合算法的合理实现水平。
"""

import numpy as np
import random
import time
from typing import Callable, List, Tuple, Any
from abc import ABC, abstractmethod


class OptimizationProblem:
    """优化问题接口"""

    def __init__(self, name: str, dimension: int, bounds: List[Tuple[float, float]],
                 evaluate_func: Callable, seed: int = 42):
        self.name = name
        self.dimension = dimension
        self.bounds = bounds
        self.evaluate_func = evaluate_func
        self.seed = seed
        np.random.seed(seed)
        random.seed(seed)

    def evaluate(self, x: np.ndarray) -> float:
        """评估解的目标函数值"""
        return self.evaluate_func(x)

    def generate_random_solution(self) -> np.ndarray:
        """生成随机解"""
        return np.array([random.uniform(low, high)
                        for low, high in self.bounds])

    def generate_neighbors(self, x: np.ndarray, n_neighbors: int = 10) -> List[np.ndarray]:
        """生成邻域解"""
        neighbors = []
        for _ in range(n_neighbors):
            neighbor = x.copy()
            # 随机选择一个维度进行扰动
            dim = random.randint(0, self.dimension - 1)
            low, high = self.bounds[dim]
            # 高斯扰动
            neighbor[dim] += random.gauss(0, (high - low) * 0.1)
            neighbor[dim] = np.clip(neighbor[dim], low, high)
            neighbors.append(neighbor)
        return neighbors


class HybridSATS:
    """
    手工实现的模拟退火 + 禁忌搜索混合算法

    这是精心设计的baseline，包含：
    1. 自适应的SA/TS切换策略
    2. 动态温度调度
    3. 禁忌表管理
    4. 多样性保持机制
    """

    def __init__(
        self,
        initial_temperature: float = 100.0,
        cooling_rate: float = 0.99,
        tabu_size: int = 30,
        switch_generation: int = 100,  # SA/TS切换的代数
        diversification_interval: int = 50,  # 多样性保持间隔
        seed: int = 42
    ):
        # SA参数
        self.initial_temp = initial_temperature
        self.cooling_rate = cooling_rate
        self.current_temp = initial_temperature

        # TS参数
        self.tabu_list = []
        self.tabu_size = tabu_size

        # 切换策略
        self.switch_gen = switch_generation

        # 多样性保持
        self.diversification_interval = diversification_interval

        # 随机种子
        self.seed = seed
        np.random.seed(seed)
        random.seed(seed)

        # 运行时状态
        self.generation = 0
        self.best_solution = None
        self.best_fitness = float('inf')
        self.history = []

    def run(
        self,
        problem: OptimizationProblem,
        max_generations: int = 1000,
        verbose: bool = False
    ) -> dict:
        """
        运行混合算法

        Args:
            problem: 优化问题
            max_generations: 最大迭代次数
            verbose: 是否输出进度

        Returns:
            dict: 包含结果、历史记录等的字典
        """
        start_time = time.time()

        # 初始化
        current = problem.generate_random_solution()
        current_fitness = problem.evaluate(current)

        self.best_solution = current.copy()
        self.best_fitness = current_fitness
        self.history = [{
            'generation': 0,
            'best_fitness': current_fitness,
            'current_fitness': current_fitness,
            'temperature': self.current_temp
        }]

        # 主循环
        for gen in range(1, max_generations + 1):
            self.generation = gen

            # 温度衰减
            self.current_temp = self.initial_temp * (self.cooling_rate ** gen)

            # 生成邻域
            neighbors = problem.generate_neighbors(current, n_neighbors=10)

            # 过滤禁忌解
            valid_neighbors = [n for n in neighbors
                             if not self._is_tabu(n)]

            if not valid_neighbors:
                # 所有邻居都在禁忌表中，随机生成新解
                next_sol = problem.generate_random_solution()
            else:
                # 根据阶段选择策略
                if gen < self.switch_gen:
                    # SA阶段：Metropolis准则
                    next_sol = self._sa_select(current, valid_neighbors, problem)
                else:
                    # TS阶段：选择最优非禁忌
                    next_sol = self._ts_select(current, valid_neighbors, problem)

            # 评估新解
            next_fitness = problem.evaluate(next_sol)

            # 更新当前解
            current = next_sol
            current_fitness = next_fitness

            # 更新禁忌表
            self._update_tabu(current)

            # 更新最优解
            if current_fitness < self.best_fitness:
                self.best_solution = current.copy()
                self.best_fitness = current_fitness

            # 多样性保持：定期随机搜索
            if gen % self.diversification_interval == 0:
                random_sol = problem.generate_random_solution()
                random_fitness = problem.evaluate(random_sol)
                if random_fitness < self.best_fitness:
                    self.best_solution = random_sol
                    self.best_fitness = random_fitness

            # 记录历史
            self.history.append({
                'generation': gen,
                'best_fitness': self.best_fitness,
                'current_fitness': current_fitness,
                'temperature': self.current_temp,
                'tabu_size': len(self.tabu_list)
            })

            # 输出进度
            if verbose and gen % 100 == 0:
                print(f"Gen {gen}: Best={self.best_fitness:.6f}, "
                      f"Temp={self.current_temp:.2f}, Tabu={len(self.tabu_list)}")

        end_time = time.time()

        return {
            'best_solution': self.best_solution,
            'best_fitness': self.best_fitness,
            'history': self.history,
            'total_generations': max_generations,
            'time_elapsed': end_time - start_time
        }

    def _sa_select(
        self,
        current: np.ndarray,
        neighbors: List[np.ndarray],
        problem: OptimizationProblem
    ) -> np.ndarray:
        """SA选择策略：Metropolis准则"""
        current_fitness = problem.evaluate(current)

        for neighbor in neighbors:
            neighbor_fitness = problem.evaluate(neighbor)
            delta = neighbor_fitness - current_fitness

            # Metropolis准则
            if delta < 0:
                # 更好解，接受
                return neighbor
            else:
                # 更差解，概率接受
                prob = np.exp(-delta / (self.current_temp + 1e-10))
                if random.random() < prob:
                    return neighbor

        # 如果都没接受，返回当前解
        return current

    def _ts_select(
        self,
        current: np.ndarray,
        neighbors: List[np.ndarray],
        problem: OptimizationProblem
    ) -> np.ndarray:
        """TS选择策略：最优非禁忌"""
        # 评估所有邻居
        evaluated = [(n, problem.evaluate(n)) for n in neighbors]

        # 找最优的
        best_neighbor, best_fitness = min(evaluated, key=lambda x: x[1])

        # 如果比当前好，接受；否则返回当前
        current_fitness = problem.evaluate(current)
        if best_fitness < current_fitness:
            return best_neighbor
        else:
            return current

    def _is_tabu(self, solution: np.ndarray) -> bool:
        """检查解是否在禁忌表中"""
        threshold = 1e-6
        for tabu_sol in self.tabu_list:
            if np.linalg.norm(solution - tabu_sol) < threshold:
                return True
        return False

    def _update_tabu(self, solution: np.ndarray):
        """更新禁忌表"""
        # 添加当前解
        self.tabu_list.append(solution.copy())

        # 如果超过容量，移除最早的
        if len(self.tabu_list) > self.tabu_size:
            self.tabu_list.pop(0)


# ============ 测试问题定义 ============

def rosenbrock(x: np.ndarray) -> float:
    """Rosenbrock函数（经典测试函数，有狭窄的弯曲山谷）"""
    n = len(x)
    return sum(100 * (x[i+1] - x[i]**2)**2 + (1 - x[i])**2 for i in range(n-1))


def sphere(x: np.ndarray) -> float:
    """Sphere函数（简单测试）"""
    return np.sum(x ** 2)


def rastrigin(x: np.ndarray) -> float:
    """Rastrigin函数（多峰）"""
    n = len(x)
    return 10 * n + np.sum(x ** 2 - 10 * np.cos(2 * np.pi * x))


# ============ 便捷函数 ============

def run_hybrid_sats_on_problem(
    problem_name: str,
    dimension: int,
    evaluate_func: Callable,
    max_generations: int = 1000,
    seed: int = 42,
    verbose: bool = False
) -> dict:
    """
    在单个问题上运行HybridSATS

    Args:
        problem_name: 问题名称
        dimension: 问题维度
        evaluate_func: 目标函数
        max_generations: 最大迭代次数
        seed: 随机种子
        verbose: 是否输出进度

    Returns:
        运行结果字典
    """
    # 创建问题
    bounds = [(-5.0, 5.0) for _ in range(dimension)]
    problem = OptimizationProblem(
        name=problem_name,
        dimension=dimension,
        bounds=bounds,
        evaluate_func=evaluate_func,
        seed=seed
    )

    # 创建算法
    hybrid = HybridSATS(
        initial_temperature=100.0,
        cooling_rate=0.99,
        tabu_size=30,
        switch_generation=100,
        diversification_interval=50,
        seed=seed
    )

    # 运行
    result = hybrid.run(problem, max_generations, verbose)

    # 添加额外信息
    result['problem_name'] = problem_name
    result['dimension'] = dimension
    result['algorithm'] = 'HybridSATS'

    return result


if __name__ == "__main__":
    # 测试运行
    print("=" * 60)
    print("HybridSATS Baseline 测试")
    print("=" * 60)

    # 测试Sphere问题
    print("\n1. Sphere Problem (d=10)")
    result = run_hybrid_sats_on_problem(
        problem_name="Sphere",
        dimension=10,
        evaluate_func=sphere,
        max_generations=500,
        verbose=True
    )
    print(f"结果: {result['best_fitness']:.6f}")
    print(f"耗时: {result['time_elapsed']:.2f}秒")

    # 测试Rastrigin问题
    print("\n2. Rastrigin Problem (d=10)")
    result = run_hybrid_sats_on_problem(
        problem_name="Rastrigin",
        dimension=10,
        evaluate_func=rastrigin,
        max_generations=1000,
        verbose=True
    )
    print(f"结果: {result['best_fitness']:.6f}")
    print(f"耗时: {result['time_elapsed']:.2f}秒")

    print("\n" + "=" * 60)
    print("Baseline测试完成！")
    print("=" * 60)
