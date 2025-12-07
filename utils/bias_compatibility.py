"""
偏置模块兼容性层
确保旧版本代码可以继续使用新的偏置系统
"""

import numpy as np
from typing import Callable, List, Dict, Any, Optional
from .bias_v2 import (
    UniversalBiasManager, OptimizationContext,
    AlgorithmicBias, DomainBias, ConstraintBias, PreferenceBias,
    DiversityBias, ConvergenceBias, PrecisionBias
)


class BackwardCompatibleBiasModule:
    """向后兼容的偏置模块"""

    def __init__(self):
        self.penalties: List[Dict[str, Any]] = []
        self.rewards: List[Dict[str, Any]] = []
        self.history_best_x: Optional[np.ndarray] = None
        self.history_best_f: float = float('inf')
        self.previous_f: Dict[int, float] = {}

        # 新的偏置管理器
        self._bias_manager = UniversalBiasManager()
        self._generation = 0

    def add_penalty(self, func: Callable, weight: float = 1.0, name: str = ""):
        """添加惩罚函数（兼容旧接口）"""
        self.penalties.append({
            'func': func,
            'weight': weight,
            'name': name
        })

        # 同时添加到新系统
        constraint_bias = ConstraintBias(weight=weight)
        constraint_bias.add_hard_constraint(func)
        self._bias_manager.domain_manager.add_bias(constraint_bias)

    def add_reward(self, func: Callable, weight: float = 0.05, name: str = ""):
        """添加奖励函数（兼容旧接口）"""
        self.rewards.append({
            'func': func,
            'weight': weight,
            'name': name
        })

        # 同时添加到新系统
        preference_bias = PreferenceBias(weight=weight)
        # 这里需要根据具体情况设置偏好
        # 简化处理，实际可能需要更复杂的转换
        self._bias_manager.domain_manager.add_bias(preference_bias)

    def compute_bias(self, x: np.ndarray, f_original: float, individual_id: Optional[int] = None) -> float:
        """计算偏置值（兼容旧接口）"""

        # 使用新系统计算
        context = OptimizationContext(
            generation=self._generation,
            individual=x,
            population=[]
        )

        # 添加历史信息到上下文
        if hasattr(self, 'history') and self.history:
            context.history = self.history

        # 计算偏置
        total_bias = self._bias_manager.compute_total_bias(x, context)

        # 同时计算旧的偏置方式（为了完全兼容）
        legacy_bias = self._compute_legacy_bias(x, f_original, individual_id)

        # 可以选择使用新系统、旧系统或组合
        # 这里使用组合，给予旧系统更高权重以保持兼容性
        return 0.7 * legacy_bias + 0.3 * total_bias

    def _compute_legacy_bias(self, x: np.ndarray, f_original: float, individual_id: Optional[int] = None) -> float:
        """使用旧方式计算偏置"""
        bias = 0.0

        # 计算惩罚
        for penalty in self.penalties:
            penalty_value = penalty['func'](x)
            if penalty_value > 0:  # 只在违反约束时添加惩罚
                bias += penalty['weight'] * penalty_value

        # 计算奖励
        for reward in self.rewards:
            reward_value = reward['func'](x)
            bias -= reward['weight'] * reward_value  # 奖励是负偏置

        return bias

    def update_history(self, x: np.ndarray, f: float):
        """更新历史记录（兼容旧接口）"""
        if f < self.history_best_f:
            self.history_best_x = x.copy()
            self.history_best_f = f

    def set_generation(self, generation: int):
        """设置当前代数"""
        self._generation = generation

    def clear(self):
        """清空历史记录"""
        self.history_best_x = None
        self.history_best_f = float('inf')
        self.previous_f.clear()

    def get_bias_stats(self) -> Dict[str, Any]:
        """获取偏置统计信息"""
        return {
            'num_penalties': len(self.penalties),
            'num_rewards': len(self.rewards),
            'algorithmic_biases': len(self._bias_manager.algorithmic_manager.biases),
            'domain_biases': len(self._bias_manager.domain_manager.biases),
            'bias_weights': self._bias_manager.bias_weights
        }


def create_standard_bias(problem, reward_weight=0.05, penalty_weight=1.0):
    """创建标准偏置（完全兼容旧版本）"""

    # 使用新的偏置管理器，但保持旧接口
    bias_module = BackwardCompatibleBiasModule()

    # 如果问题有约束，添加约束惩罚
    if hasattr(problem, 'evaluate_constraints'):
        def constraint_penalty(x):
            try:
                violations = problem.evaluate_constraints(x)
                return max(0, np.max(violations)) if len(violations) > 0 else 0
            except:
                return 0

        bias_module.add_penalty(constraint_penalty, weight=penalty_weight, name="constraints")

    # 添加多样性奖励
    def diversity_reward(x):
        # 简化的多样性奖励
        return 0.1  # 固定奖励，实际应该基于种群多样性

    bias_module.add_reward(diversity_reward, weight=reward_weight, name="diversity")

    # 添加收敛奖励（接近历史最优）
    def convergence_reward(x):
        if bias_module.history_best_x is not None:
            distance = np.linalg.norm(x - bias_module.history_best_x)
            return np.exp(-distance)  # 距离越小，奖励越大
        return 0

    bias_module.add_reward(convergence_reward, weight=reward_weight * 0.5, name="convergence")

    return bias_module


# 内置奖励函数（保持向后兼容）
def proximity_reward(x, best_x, scale=1.0):
    """接近历史最优解的奖励"""
    distance = np.linalg.norm(x - best_x)
    return scale * np.exp(-distance)


def improvement_reward(f_current, f_previous, scale=1.0):
    """目标改进速度的奖励"""
    if f_previous is None:
        return 0
    improvement = f_previous - f_current
    return scale * max(0, improvement)


def feasibility_depth_reward(constraint_values, scale=1.0):
    """深度可行性奖励"""
    if len(constraint_values) == 0:
        return scale

    # 计算约束违反深度
    max_violation = np.max(constraint_values)
    if max_violation <= 0:
        return scale  # 完全可行
    else:
        return scale * (1.0 / (1.0 + max_violation))  # 部分可行


def diversity_reward(x, population, scale=1.0, k=5):
    """多样性贡献奖励"""
    if len(population) == 0:
        return 0

    distances = []
    for other in population[:k]:  # 考虑最近的k个个体
        if not np.array_equal(x, other):
            dist = np.linalg.norm(x - other)
            distances.append(dist)

    if not distances:
        return 0

    min_distance = min(distances)
    return scale * np.log(min_distance + 1.0)


# 内置罚函数（保持向后兼容）
def constraint_penalty(constraint_values, scale=1.0):
    """标准约束罚函数"""
    if len(constraint_values) == 0:
        return 0
    return scale * max(0, np.max(constraint_values))


def boundary_penalty(x, bounds, scale=1.0):
    """边界惩罚"""
    penalty = 0.0
    for i, (key, (low, high)) in enumerate(bounds.items()):
        if i < len(x):
            if x[i] < low:
                penalty += scale * (low - x[i])
            elif x[i] > high:
                penalty += scale * (x[i] - high)
    return penalty


def stagnation_penalty(generation, last_improvement_gen, scale=0.01):
    """停滞惩罚"""
    stagnation = generation - last_improvement_gen
    return scale * stagnation


# 导出主要接口，确保向后兼容
__all__ = [
    'BiasModule',  # 为了向后兼容，实际使用 BackwardCompatibleBiasModule
    'create_standard_bias',
    'BackwardCompatibleBiasModule',
    'proximity_reward',
    'improvement_reward',
    'feasibility_depth_reward',
    'diversity_reward',
    'constraint_penalty',
    'boundary_penalty',
    'stagnation_penalty'
]


# 创建别名以确保向后兼容
BiasModule = BackwardCompatibleBiasModule