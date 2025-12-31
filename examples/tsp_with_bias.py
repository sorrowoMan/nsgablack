"""
TSP问题 - 使用连续编码+偏置系统的旅行商问题实现

这个实现展示了如何使用连续编码和偏置系统来解决经典的组合优化问题。
核心思想：
1. 使用连续向量编码城市访问顺序
2. 通过偏置系统引导搜索向有效的TSP解
3. 保持NSGA-II在连续空间中优化
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Any
import math

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .core.base import BlackBoxProblem
    from .solvers.nsga2 import BlackBoxSolverNSGAII
    from .bias.bias_v2 import UniversalBiasManager, DomainBias, OptimizationContext
    from .bias.bias_library_algorithmic import DiversityBias, ExplorationBias
except ImportError as e:
    print(f"Import error: {e}")
    print("请确保在项目根目录运行，或安装nsgablack包")
    sys.exit(1)


class TSPContinuousEncoding:
    """TSP问题的连续编码方案

    使用随机键编码：每个城市对应一个随机数，按照随机数大小确定访问顺序
    """

    def __init__(self, n_cities: int):
        self.n_cities = n_cities

    def decode_to_tour(self, continuous_vector: np.ndarray) -> List[int]:
        """将连续向量解码为城市访问顺序"""
        if len(continuous_vector) != self.n_cities:
            raise ValueError(f"向量长度{len(continuous_vector)}不等于城市数量{self.n_cities}")

        # 根据连续值的大小确定访问顺序
        sorted_indices = np.argsort(continuous_vector)
        return sorted_indices.tolist()

    def encode_from_tour(self, tour: List[int]) -> np.ndarray:
        """从城市访问顺序编码为连续向量（用于初始化）"""
        # 生成随机键，保持指定的顺序
        random_keys = np.random.exponential(1.0, self.n_cities)
        sorted_keys = np.zeros(self.n_cities)
        for i, city in enumerate(tour):
            sorted_keys[city] = random_keys[i]
        return sorted_keys

    def vector_bounds(self) -> List[Tuple[float, float]]:
        """返回连续变量的边界"""
        return [(0.0, 1.0)] * self.n_cities


class TSPBias(DomainBias):
    """TSP专用偏置：引导连续编码向有效的TSP解收敛"""

    def __init__(self, cities: np.ndarray, weight: float = 10.0):
        super().__init__("tsp_bias", weight)
        self.cities = cities
        self.n_cities = len(cities)
        self.distance_matrix = self._compute_distance_matrix()

        # 偏置参数
        self.distance_weight = 1.0      # 距离权重
        self.validity_weight = 5.0      # 有效性权重
        self.diversity_weight = 0.1     # 多样性权重

    def _compute_distance_matrix(self) -> np.ndarray:
        """计算城市间距离矩阵"""
        n = self.n_cities
        dist_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                dist_matrix[i, j] = np.linalg.norm(self.cities[i] - self.cities[j])
        return dist_matrix

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算TSP偏置值"""
        tour = self._decode_tour(x)
        if not tour:
            return 1000.0  # 无效解码，给予大惩罚

        # 1. 计算总距离（目标）
        total_distance = self._calculate_tour_distance(tour)

        # 2. 计算有效性惩罚
        validity_penalty = self._compute_validity_penalty(tour)

        # 3. 计算多样性奖励（避免所有解收敛到同一个tour）
        diversity_bonus = self._compute_diversity_bonus(tour, context)

        # 总偏置：距离最小化 + 有效性最大化 + 多样性
        bias_value = (self.distance_weight * total_distance / 1000.0 +  # 归一化
                     self.validity_weight * validity_penalty +
                     self.diversity_weight * diversity_bonus)

        return -bias_value  # 负值，因为优化器最小化目标

    def _decode_tour(self, x: np.ndarray) -> List[int]:
        """解码连续向量为城市访问顺序"""
        try:
            encoder = TSPContinuousEncoding(self.n_cities)
            tour = encoder.decode_to_tour(x)

            # 验证tour的有效性
            if len(set(tour)) == self.n_cities and set(tour) == set(range(self.n_cities)):
                return tour
            else:
                return []
        except:
            return []

    def _calculate_tour_distance(self, tour: List[int]) -> float:
        """计算tour的总距离"""
        if len(tour) != self.n_cities:
            return float('inf')

        total = 0.0
        for i in range(self.n_cities):
            current_city = tour[i]
            next_city = tour[(i + 1) % self.n_cities]
            total += self.distance_matrix[current_city, next_city]

        return total

    def _compute_validity_penalty(self, tour: List[int]) -> float:
        """计算tour的有效性惩罚"""
        if not tour:
            return 10.0  # 空tour，大惩罚

        penalty = 0.0

        # 检查城市覆盖
        visited_cities = set(tour)
        if len(visited_cities) != self.n_cities:
            missing_cities = set(range(self.n_cities)) - visited_cities
            penalty += len(missing_cities) * 2.0

        # 检查重复访问
        if len(tour) != len(set(tour)):
            duplicates = len(tour) - len(set(tour))
            penalty += duplicates * 3.0

        return penalty

    def _compute_diversity_bonus(self, tour: List[int], context: OptimizationContext) -> float:
        """计算多样性奖励，鼓励探索不同的解"""
        if not context.population or len(context.population) < 2:
            return 0.0

        # 计算当前tour与种群中其他解的相似度
        similarity_scores = []
        current_tuple = tuple(tour)

        for other_individual in context.population:
            other_tour = self._decode_tour(other_individual)
            if other_tour:
                # 计算相似度（使用边重叠度）
                similarity = self._tour_similarity(current_tuple, tuple(other_tour))
                similarity_scores.append(similarity)

        if similarity_scores:
            # 与其他解越不相似，奖励越大
            avg_similarity = np.mean(similarity_scores)
            diversity_bonus = 1.0 - avg_similarity
            return diversity_bonus

        return 0.0

    def _tour_similarity(self, tour1: tuple, tour2: tuple) -> float:
        """计算两个tour的相似度（基于边重叠）"""
        edges1 = set()
        edges2 = set()

        for i in range(len(tour1)):
            edge1 = tuple(sorted([tour1[i], tour1[(i + 1) % len(tour1)]]))
            edges1.add(edge1)

        for i in range(len(tour2)):
            edge2 = tuple(sorted([tour2[i], tour2[(i + 1) % len(tour2)]]))
            edges2.add(edge2)

        if len(edges1) == 0:
            return 0.0

        overlap = len(edges1.intersection(edges2))
        return overlap / len(edges1)


class TSPProblem(BlackBoxProblem):
    """TSP问题包装器，集成连续编码和偏置系统"""

    def __init__(self, cities: np.ndarray, enable_bias: bool = True):
        self.cities = cities
        self.n_cities = len(cities)
        self.encoder = TSPContinuousEncoding(self.n_cities)

        # 创建变量边界
        bounds = {f"x{i}": [0.0, 1.0] for i in range(self.n_cities)}

        super().__init__(name=f"TSP_{self.n_cities}_cities",
                        dimension=self.n_cities,
                        bounds=bounds)

        self.enable_bias = enable_bias
        self.tsp_bias = TSPBias(cities, weight=10.0)

        # 统计信息
        self.evaluation_count = 0
        self.best_tour = None
        self.best_distance = float('inf')

    def evaluate(self, x: np.ndarray):
        """评估TSP解的适应度"""
        self.evaluation_count += 1

        # 解码为tour
        tour = self.encoder.decode_to_tour(x)

        if not tour:
            return [10000.0]  # 无效解，返回大值

        # 计算tour距离
        distance = self._calculate_total_distance(tour)

        # 更新最佳解
        if distance < self.best_distance:
            self.best_distance = distance
            self.best_tour = tour

        # 如果启用偏置，则应用偏置
        if self.enable_bias:
            # 创建优化上下文
            context = OptimizationContext(
                generation=0,  # 这里需要从外部传入
                individual=x,
                population=[]
            )

            # 计算偏置值
            bias_value = self.tsp_bias.compute(x, context)

            # 总目标 = 距离 + 偏置引导
            total_fitness = distance + bias_value * 0.1  # 偏置权重较小
        else:
            total_fitness = distance

        return [total_fitness]

    def _calculate_total_distance(self, tour: List[int]) -> float:
        """计算tour的总距离"""
        total = 0.0
        for i in range(self.n_cities):
            current_city = tour[i]
            next_city = tour[(i + 1) % self.n_cities]
            total += np.linalg.norm(self.cities[current_city] - self.cities[next_city])
        return total


def create_tsp_bias_manager(cities: np.ndarray) -> UniversalBiasManager:
    """创建TSP专用的偏置管理器"""
    manager = UniversalBiasManager()

    # 添加TSP偏置
    tsp_bias = TSPBias(cities, weight=10.0)
    manager.domain_manager.add_bias(tsp_bias)

    # 添加算法偏置（增强探索能力）
    diversity_bias = DiversityBias(weight=0.2)
    exploration_bias = ExplorationBias(weight=0.15)

    manager.algorithmic_manager.add_bias(diversity_bias)
    manager.algorithmic_manager.add_bias(exploration_bias)

    # 调整权重：业务偏置更重要
    manager.set_bias_weights(algorithmic_weight=0.3, domain_weight=0.7)

    return manager


def generate_random_cities(n_cities: int, seed: int = None) -> np.ndarray:
    """生成随机城市坐标"""
    if seed:
        np.random.seed(seed)

    # 生成随机城市分布
    cities = np.random.uniform(0, 100, (n_cities, 2))

    # 确保城市间有合理距离
    min_distance = 5.0
    max_attempts = 1000

    for attempt in range(max_attempts):
        conflicts = False
        for i in range(n_cities):
            for j in range(i + 1, n_cities):
                if np.linalg.norm(cities[i] - cities[j]) < min_distance:
                    cities[j] = np.random.uniform(0, 100, 2)
                    conflicts = True
                    break
            if conflicts:
                break

        if not conflicts:
            break

    return cities


def visualize_tsp_solution(cities: np.ndarray, tour: List[int], title: str = "TSP Solution"):
    """可视化TSP解"""
    try:
        plt.figure(figsize=(10, 8))

        # 绘制城市
        plt.scatter(cities[:, 0], cities[:, 1], c='red', s=100, zorder=5, alpha=0.8)

        # 绘制路线
        tour_cities = cities[tour + [tour[0]]]  # 回到起点
        plt.plot(tour_cities[:, 0], tour_cities[:, 1], 'b-', alpha=0.6, linewidth=2)

        # 标注城市编号
        for i, city in enumerate(cities):
            plt.annotate(f'{i}', (city[0], city[1]), xytext=(5, 5),
                        textcoords='offset points', fontsize=12)

        plt.xlabel('X Coordinate')
        plt.ylabel('Y Coordinate')
        plt.title(f'{title} - Total Distance: {calculate_tour_distance(cities, tour):.2f}')
        plt.grid(True, alpha=0.3)
        plt.show()
    except Exception as e:
        print(f"可视化失败: {e}")
        print(f"Tour: {tour}")
        print(f"Total Distance: {calculate_tour_distance(cities, tour):.2f}")


def calculate_tour_distance(cities: np.ndarray, tour: List[int]) -> float:
    """计算tour的总距离"""
    total = 0.0
    n = len(tour)
    for i in range(n):
        current_city = tour[i]
        next_city = tour[(i + 1) % n]
        total += np.linalg.norm(cities[current_city] - cities[next_city])
    return total


def simple_tsp_solver(tsp_problem: TSPProblem, pop_size: int, max_generations: int) -> Dict[str, Any]:
    """简单的随机搜索求解器，作为NSGA-II的回退"""
    print("使用简单随机搜索求解器...")

    best_solution = None
    best_distance = float('inf')

    for generation in range(max_generations):
        # 生成随机解
        for _ in range(pop_size):
            random_vector = np.random.uniform(0, 1, tsp_problem.n_cities)
            tour = tsp_problem.encoder.decode_to_tour(random_vector)

            if tour:
                distance = tsp_problem._calculate_total_distance(tour)
                if distance < best_distance:
                    best_distance = distance
                    best_solution = tour

        if generation % 50 == 0:
            print(f"  第{generation}代，最佳距离: {best_distance:.2f}")

    return {
        'best_tour': best_solution,
        'best_distance': best_distance,
        'evaluation_count': pop_size * max_generations,
        'generations': max_generations,
        'problem': tsp_problem,
        'solver': None
    }


def solve_tsp_with_bias(cities: np.ndarray,
                       pop_size: int = 100,
                       max_generations: int = 200,
                       enable_bias: bool = True,
                       enable_visualization: bool = True) -> Dict[str, Any]:
    """使用偏置系统解决TSP问题"""

    print(f"解决 {len(cities)} 城市TSP问题...")
    print(f"使用偏置系统: {enable_bias}")

    # 创建TSP问题
    tsp_problem = TSPProblem(cities, enable_bias=enable_bias)

    # 创建求解器
    try:
        solver = BlackBoxSolverNSGAII(tsp_problem)
        solver.pop_size = pop_size
        solver.max_generations = max_generations
        solver.enable_bias = enable_bias
        solver.enable_progress_log = True
        solver.report_interval = 50

        # 如果启用偏置，设置偏置管理器
        if enable_bias:
            bias_manager = create_tsp_bias_manager(cities)
            solver.bias_module = bias_manager
    except Exception as e:
        print(f"创建求解器时出错: {e}")
        # 回退到简单评估
        return simple_tsp_solver(tsp_problem, pop_size, max_generations)

    # 运行优化
    print("开始优化...")
    result = solver.run(return_experiment=True)

    # 获取最佳解
    if result.pareto_solutions is not None and len(result.pareto_solutions['individuals']) > 0:
        best_individual = result.pareto_solutions['individuals'][0]
        best_tour = tsp_problem.encoder.decode_to_tour(best_individual)
        best_distance = tsp_problem._calculate_total_distance(best_tour)
    else:
        # 使用问题中记录的最佳解
        best_tour = tsp_problem.best_tour
        best_distance = tsp_problem.best_distance

    # 可视化结果
    if enable_visualization and best_tour:
        visualize_tsp_solution(cities, best_tour,
                             f"TSP Solution with Bias: {enable_bias}")

    print(f"\n优化完成!")
    print(f"最佳距离: {best_distance:.2f}")
    print(f"最佳tour: {best_tour}")
    print(f"评估次数: {tsp_problem.evaluation_count}")
    print(f"运行代数: {result.generation}")

    return {
        'best_tour': best_tour,
        'best_distance': best_distance,
        'evaluation_count': tsp_problem.evaluation_count,
        'generations': result.generation,
        'problem': tsp_problem,
        'solver': solver
    }


# 示例使用
if __name__ == "__main__":
    # 生成测试数据
    n_cities = 15
    cities = generate_random_cities(n_cities, seed=42)

    print("=" * 50)
    print("旅行商问题（TSP） - 连续编码+偏置系统")
    print("=" * 50)

    # 1. 使用偏置系统
    print("\n1. 使用偏置系统求解:")
    result_with_bias = solve_tsp_with_bias(
        cities,
        pop_size=150,
        max_generations=300,
        enable_bias=True,
        enable_visualization=True
    )

    # 2. 不使用偏置系统（对比）
    print("\n2. 不使用偏置系统求解:")
    result_without_bias = solve_tsp_with_bias(
        cities,
        pop_size=150,
        max_generations=300,
        enable_bias=False,
        enable_visualization=True
    )

    # 3. 比较结果
    print("\n" + "=" * 50)
    print("结果比较:")
    print("=" * 50)
    print(f"使用偏置:")
    print(f"  最佳距离: {result_with_bias['best_distance']:.2f}")
    print(f"  评估次数: {result_with_bias['evaluation_count']}")
    print(f"  收敛代数: {result_with_bias['generations']}")

    print(f"\n不使用偏置:")
    print(f"  最佳距离: {result_without_bias['best_distance']:.2f}")
    print(f"  评估次数: {result_without_bias['evaluation_count']}")
    print(f"  收敛代数: {result_without_bias['generations']}")

    improvement = ((result_without_bias['best_distance'] - result_with_bias['best_distance']) /
                  result_without_bias['best_distance']) * 100
    print(f"\n偏置系统改进: {improvement:.1f}%")