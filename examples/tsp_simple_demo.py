"""
TSP问题简化演示 - 连续编码+偏置系统的核心概念
这个版本专注于展示核心思想，避免复杂的依赖
"""

import numpy as np
import random
import math
from typing import List, Tuple, Dict, Any


class TSPContinuousEncoding:
    """TSP问题的连续编码方案 - 随机键编码"""

    def __init__(self, n_cities: int):
        self.n_cities = n_cities

    def decode_to_tour(self, continuous_vector: np.ndarray) -> List[int]:
        """将连续向量解码为城市访问顺序"""
        if len(continuous_vector) != self.n_cities:
            return []

        # 根据连续值的大小确定访问顺序
        sorted_indices = np.argsort(continuous_vector)
        return sorted_indices.tolist()


class SimpleTSPBias:
    """简化的TSP偏置系统"""

    def __init__(self, cities: np.ndarray, weight: float = 5.0):
        self.cities = cities
        self.n_cities = len(cities)
        self.weight = weight
        self.distance_matrix = self._compute_distance_matrix()

    def _compute_distance_matrix(self) -> np.ndarray:
        """计算城市间距离矩阵"""
        n = self.n_cities
        dist_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                dist_matrix[i, j] = np.linalg.norm(self.cities[i] - self.cities[j])
        return dist_matrix

    def compute_bias(self, x: np.ndarray, population: List[np.ndarray] = None) -> float:
        """计算偏置值，引导向更好的TSP解"""

        # 解码为tour
        encoder = TSPContinuousEncoding(self.n_cities)
        tour = encoder.decode_to_tour(x)

        if not tour:
            return 1000.0  # 无效解码，大惩罚

        # 1. 计算tour距离
        distance = self._calculate_tour_distance(tour)

        # 2. 有效性检查
        validity_penalty = 0.0
        if len(set(tour)) != self.n_cities:
            validity_penalty += 10.0  # 重复或缺失城市

        # 3. 多样性检查（可选）
        diversity_bonus = 0.0
        if population and len(population) > 1:
            # 计算与种群中其他解的相似度
            similarities = []
            for other in population:
                other_tour = encoder.decode_to_tour(other)
                if other_tour:
                    similarity = self._tour_similarity(tour, other_tour)
                    similarities.append(similarity)

            if similarities:
                avg_similarity = np.mean(similarities)
                diversity_bonus = 1.0 - avg_similarity

        # 总偏置：距离最小化 + 有效性 + 多样性
        bias_value = (distance / 100.0 + validity_penalty - 0.1 * diversity_bonus)

        # 返回负的偏置值（因为我们要最小化目标函数）
        return -self.weight * bias_value

    def _calculate_tour_distance(self, tour: List[int]) -> float:
        """计算tour的总距离"""
        total = 0.0
        for i in range(self.n_cities):
            current_city = tour[i]
            next_city = tour[(i + 1) % self.n_cities]
            total += self.distance_matrix[current_city, next_city]
        return total

    def _tour_similarity(self, tour1: List[int], tour2: List[int]) -> float:
        """计算两个tour的相似度"""
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


def evaluate_tsp_solution(x: np.ndarray, cities: np.ndarray,
                         enable_bias: bool = True,
                         population: List[np.ndarray] = None) -> float:
    """评估TSP解的适应度"""
    encoder = TSPContinuousEncoding(len(cities))

    # 解码为tour
    tour = encoder.decode_to_tour(x)

    if not tour:
        return 10000.0  # 无效解，返回大值

    # 计算距离
    distance = calculate_total_distance(cities, tour)

    # 如果启用偏置
    if enable_bias:
        bias = SimpleTSPBias(cities)
        bias_value = bias.compute_bias(x, population)
        return distance + bias_value * 0.1  # 偏置权重较小

    return distance


def calculate_total_distance(cities: np.ndarray, tour: List[int]) -> float:
    """计算tour的总距离"""
    total = 0.0
    n = len(tour)
    for i in range(n):
        current_city = tour[i]
        next_city = tour[(i + 1) % n]
        total += np.linalg.norm(cities[current_city] - cities[next_city])
    return total


def generate_random_cities(n_cities: int, seed: int = None) -> np.ndarray:
    """生成随机城市坐标"""
    if seed:
        np.random.seed(seed)
        random.seed(seed)

    return np.random.uniform(0, 100, (n_cities, 2))


def simple_genetic_algorithm(cities: np.ndarray,
                           pop_size: int = 50,
                           max_generations: int = 100,
                           enable_bias: bool = True) -> Dict[str, Any]:
    """简化的遗传算法解决TSP问题"""

    print(f"\n{'='*50}")
    print(f"TSP求解器 - 偏置系统: {enable_bias}")
    print(f"城市数量: {len(cities)}, 种群大小: {pop_size}, 最大代数: {max_generations}")
    print(f"{'='*50}")

    n_cities = len(cities)

    # 初始化种群（连续编码）
    population = []
    for _ in range(pop_size):
        individual = np.random.uniform(0, 1, n_cities)
        population.append(individual)

    # 评估初始种群
    fitness_scores = []
    for individual in population:
        fitness = evaluate_tsp_solution(individual, cities, enable_bias, population)
        fitness_scores.append(fitness)

    best_individual = None
    best_fitness = float('inf')
    best_tour = None
    best_distance = float('inf')

    # 进化循环
    for generation in range(max_generations):
        # 选择（锦标赛选择）
        new_population = []
        for _ in range(pop_size):
            # 选择3个随机个体
            tournament = random.sample(list(zip(population, fitness_scores)), 3)
            winner = min(tournament, key=lambda x: x[1])
            new_population.append(winner[0].copy())

        # 交叉和变异
        for i in range(0, pop_size, 2):
            if i + 1 < pop_size:
                parent1 = new_population[i]
                parent2 = new_population[i + 1]

                # 简单交叉
                if random.random() < 0.8:
                    crossover_point = random.randint(1, n_cities - 1)
                    child1 = np.concatenate([parent1[:crossover_point], parent2[crossover_point:]])
                    child2 = np.concatenate([parent2[:crossover_point], parent1[crossover_point:]])
                else:
                    child1 = parent1.copy()
                    child2 = parent2.copy()

                # 变异
                for child in [child1, child2]:
                    if random.random() < 0.2:
                        mutation_rate = 0.1
                        mutation = np.random.uniform(-mutation_rate, mutation_rate, n_cities)
                        child = child + mutation
                        # 确保在[0,1]范围内
                        child = np.clip(child, 0, 1)

                new_population[i] = child1
                new_population[i + 1] = child2

        population = new_population

        # 评估新种群
        fitness_scores = []
        for individual in population:
            fitness = evaluate_tsp_solution(individual, cities, enable_bias, population)
            fitness_scores.append(fitness)

        # 更新最佳解
        current_best_fitness = min(fitness_scores)
        current_best_idx = np.argmin(fitness_scores)
        current_best_individual = population[current_best_idx]

        encoder = TSPContinuousEncoding(n_cities)
        current_best_tour = encoder.decode_to_tour(current_best_individual)
        current_best_distance = calculate_total_distance(cities, current_best_tour)

        if current_best_distance < best_distance:
            best_distance = current_best_distance
            best_tour = current_best_tour
            best_individual = current_best_individual.copy()
            best_fitness = current_best_fitness

        # 进度报告
        if generation % 20 == 0:
            print(f"第{generation:3d}代 | 最佳距离: {best_distance:8.2f} | "
                  f"当前最佳: {current_best_distance:8.2f} | Tour: {current_best_tour}")

    return {
        'best_tour': best_tour,
        'best_distance': best_distance,
        'best_individual': best_individual,
        'generations': max_generations,
        'population': population
    }


def print_tour_comparison(result1: Dict, result2: Dict, label1: str, label2: str):
    """比较两个TSP求解结果"""
    print(f"\n{'='*60}")
    print("结果比较")
    print(f"{'='*60}")

    print(f"{label1}:")
    print(f"  最佳距离: {result1['best_distance']:.2f}")
    print(f"  最佳路线: {result1['best_tour']}")

    print(f"\n{label2}:")
    print(f"  最佳距离: {result2['best_distance']:.2f}")
    print(f"  最佳路线: {result2['best_tour']}")

    improvement = ((result2['best_distance'] - result1['best_distance']) /
                  result2['best_distance']) * 100
    print(f"\n{label1} 相对于 {label2} 的改进: {improvement:.1f}%")


def verify_tour_validity(tour: List[int], n_cities: int) -> bool:
    """验证tour的有效性"""
    if len(tour) != n_cities:
        return False
    if set(tour) != set(range(n_cities)):
        return False
    return True


def main():
    """主函数"""
    print("旅行商问题（TSP）- 连续编码+偏置系统演示")
    print("=" * 60)

    # 生成测试数据
    n_cities = 12
    cities = generate_random_cities(n_cities, seed=42)

    print(f"\n城市坐标:")
    for i, city in enumerate(cities):
        print(f"  城市 {i:2d}: ({city[0]:6.2f}, {city[1]:6.2f})")

    # 1. 使用偏置系统求解
    print(f"\n{'#'*60}")
    print("1. 使用偏置系统求解")
    print(f"{'#'*60}")

    result_with_bias = simple_genetic_algorithm(
        cities,
        pop_size=40,
        max_generations=80,
        enable_bias=True
    )

    # 2. 不使用偏置系统求解
    print(f"\n{'#'*60}")
    print("2. 不使用偏置系统求解")
    print(f"{'#'*60}")

    result_without_bias = simple_genetic_algorithm(
        cities,
        pop_size=40,
        max_generations=80,
        enable_bias=False
    )

    # 3. 比较结果
    print_tour_comparison(result_with_bias, result_without_bias,
                         "使用偏置", "不使用偏置")

    # 4. 验证解的有效性
    print(f"\n{'='*60}")
    print("解的有效性验证")
    print(f"{'='*60}")

    print(f"使用偏置的解有效性: {verify_tour_validity(result_with_bias['best_tour'], n_cities)}")
    print(f"不使用偏置的解有效性: {verify_tour_validity(result_without_bias['best_tour'], n_cities)}")

    # 5. 核心概念总结
    print(f"\n{'='*60}")
    print("核心概念总结")
    print(f"{'='*60}")
    print("1. 连续编码: 使用随机键编码，每个城市对应一个[0,1]的随机数")
    print("2. 解码方案: 按随机数大小排序确定访问顺序")
    print("3. 偏置系统: 引导搜索向有效、短路径的解收敛")
    print("   - 距离惩罚: 偏好短路径")
    print("   - 有效性检查: 确保每个城市只访问一次")
    print("   - 多样性保持: 避免过早收敛")
    print("4. 优势: 保持底层连续优化器的简单性，通过偏置处理复杂约束")


if __name__ == "__main__":
    main()