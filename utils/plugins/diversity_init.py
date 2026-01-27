"""
多样性初始化插件

提供多样性感知的种群初始化策略
"""

import numpy as np
from typing import Optional
from .base import Plugin


class DiversityInitPlugin(Plugin):
    is_algorithmic = True
    """
    多样性初始化插件

    功能：在初始化种群时保持个体间的多样性
    特点：
    - 拒绝过于相似的个体
    - 提高初始种群的覆盖范围

    推荐用于：
    - 多峰优化问题
    - 需要探索多个区域的问题
    """

    def __init__(self, similarity_threshold: float = 0.1, rejection_prob: float = 0.5):
        """
        初始化多样性插件

        Args:
            similarity_threshold: 相似度阈值（小于此值认为相似）
            rejection_prob: 拒绝概率（相似个体被拒绝的概率）
        """
        super().__init__("diversity_init")
        self.similarity_threshold = similarity_threshold
        self.rejection_prob = rejection_prob

    def on_solver_init(self, solver):
        """求解器初始化"""
        # 在初始化种群时使用多样性策略
        if hasattr(solver, 'use_diverse_init'):
            solver.use_diverse_init = True

    def on_population_init(self, population, objectives, violations):
        """种群初始化后可以评估多样性"""
        diversity_score = self._compute_diversity(population)
        print(f"[DiversityInit] 初始种群多样性: {diversity_score:.4f}")

    def on_generation_start(self, generation: int):
        """代开始"""
        pass

    def on_generation_end(self, generation: int):
        """代结束"""
        pass

    def on_solver_finish(self, result):
        """求解器结束"""
        pass

    def _compute_diversity(self, population) -> float:
        """计算种群多样性"""
        if len(population) < 2:
            return 0.0

        # 归一化
        pop_norm = (population - population.min(axis=0)) / (population.max(axis=0) - population.min(axis=0) + 1e-10)

        # 计算平均距离
        distances = []
        n_samples = min(30, len(pop_norm))
        indices = np.random.choice(len(pop_norm), n_samples, replace=False)
        samples = pop_norm[indices]

        for i in range(n_samples):
            for j in range(i + 1, n_samples):
                dist = np.linalg.norm(samples[i] - samples[j])
                distances.append(dist)

        return float(np.mean(distances)) if distances else 0.0

    def is_similar(self, individual: np.ndarray, existing_population: np.ndarray) -> bool:
        """
        判断个体是否与现有种群过于相似

        Args:
            individual: 待判断的个体
            existing_population: 现有种群

        Returns:
            True=相似, False=不相似
        """
        if len(existing_population) == 0:
            return False

        # 计算与所有现有个体的最小距离
        min_distance = float('inf')
        for existing in existing_population:
            dist = np.linalg.norm(individual - existing)
            if dist < min_distance:
                min_distance = dist

        return min_distance < self.similarity_threshold

    def should_accept(self, individual: np.ndarray, existing_population: np.ndarray) -> bool:
        """
        判断是否接受新个体

        Args:
            individual: 待判断的个体
            existing_population: 现有种群

        Returns:
            True=接受, False=拒绝
        """
        if not self.is_similar(individual, existing_population):
            return True

        # 如果相似，按概率拒绝
        return np.random.random() > self.rejection_prob
