"""可拓展的优化偏向模块 (Bias Module)

核心思想：
- 罚函数（Penalty）：惩罚不良解，避免往更差的方向优化
- 奖函数（Reward）：奖励优质解，引导快速收敛到好的方向
- 方向引导：基于历史信息的智能偏向

设计原则：
- 奖函数权重（0.01-0.1）远小于罚函数（1.0-10.0）
- 避免过度引导导致早熟收敛
- 配合 VNS 等方法跳出局部最优
"""
import numpy as np
from typing import Callable, List, Dict, Any, Optional


class BiasModule:
    """可拓展的优化偏向模块

    统一管理罚函数和奖函数，影响遗传算法的搜索方向
    """

    def __init__(self):
        self.penalties: List[Dict[str, Any]] = []
        self.rewards: List[Dict[str, Any]] = []
        self.history_best_x: Optional[np.ndarray] = None
        self.history_best_f: float = float('inf')
        self.previous_f: Dict[int, float] = {}  # 记录个体上一次的目标值

    def add_penalty(self, func: Callable, weight: float = 1.0, name: str = ""):
        """添加罚函数

        参数：
            func: 罚函数，接受 x 返回惩罚值（>=0）
            weight: 权重（通常 1.0-10.0）
            name: 函数名称
        """
        self.penalties.append({'func': func, 'weight': weight, 'name': name})

    def add_reward(self, func: Callable, weight: float = 0.05, name: str = ""):
        """添加奖函数

        参数：
            func: 奖函数，接受 x 返回奖励值（>=0）
            weight: 权重（通常 0.01-0.1，远小于罚函数）
            name: 函数名称
        """
        self.rewards.append({'func': func, 'weight': weight, 'name': name})

    def compute_bias(self, x: np.ndarray, f_original: float,
                     individual_id: Optional[int] = None) -> float:
        """计算偏向后的目标值

        参数：
            x: 决策变量
            f_original: 原始目标值
            individual_id: 个体ID（用于跟踪改进）

        返回：
            偏向后的目标值
        """
        bias = 0.0

        # 罚函数：增加目标值（惩罚）
        for p in self.penalties:
            try:
                penalty_value = p['func'](x)
                bias += p['weight'] * max(0, penalty_value)
            except Exception:
                pass

        # 奖函数：减少目标值（奖励）
        for r in self.rewards:
            try:
                reward_value = r['func'](x)
                bias -= r['weight'] * max(0, reward_value)
            except Exception:
                pass

        # 更新历史
        if f_original < self.history_best_f:
            self.history_best_f = f_original
            self.history_best_x = x.copy()

        if individual_id is not None:
            self.previous_f[individual_id] = f_original

        return f_original + bias

    def update_history(self, x: np.ndarray, f: float):
        """手动更新历史最优解"""
        if f < self.history_best_f:
            self.history_best_f = f
            self.history_best_x = x.copy()

    def clear(self):
        """清空所有罚函数和奖函数"""
        self.penalties.clear()
        self.rewards.clear()


# ==================== 常用奖函数库 ====================

def proximity_reward(x: np.ndarray, best_x: np.ndarray,
                     scale: float = 1.0, normalize: bool = True) -> float:
    """接近历史最优解的奖励

    参数：
        x: 当前解
        best_x: 历史最优解
        scale: 缩放因子
        normalize: 是否归一化距离

    返回：
        奖励值（距离越近奖励越大）
    """
    if best_x is None:
        return 0.0

    distance = np.linalg.norm(x - best_x)
    if normalize:
        distance = distance / (np.sqrt(len(x)) + 1e-10)

    return scale * np.exp(-distance)


def improvement_reward(f_current: float, f_previous: float,
                       scale: float = 1.0) -> float:
    """目标改进速度奖励

    参数：
        f_current: 当前目标值
        f_previous: 上一次目标值
        scale: 缩放因子

    返回：
        奖励值（改进越大奖励越大）
    """
    improvement = max(0, f_previous - f_current)
    return scale * improvement


def feasibility_depth_reward(constraint_values: np.ndarray,
                             scale: float = 1.0) -> float:
    """深度可行性奖励

    不仅满足约束（g<=0），还奖励远离约束边界的解

    参数：
        constraint_values: 约束值数组（g<=0为可行）
        scale: 缩放因子

    返回：
        奖励值（越远离边界奖励越大）
    """
    if len(constraint_values) == 0:
        return 0.0

    # 计算可行性余量（负值越大越可行）
    margin = -np.sum(np.minimum(constraint_values, 0))
    return scale * margin


def diversity_reward(x: np.ndarray, population: np.ndarray,
                     scale: float = 1.0, k: int = 5) -> float:
    """多样性贡献奖励

    奖励与种群中其他个体距离较远的解

    参数：
        x: 当前解
        population: 种群
        scale: 缩放因子
        k: 考虑最近的k个邻居

    返回：
        奖励值（越独特奖励越大）
    """
    if len(population) == 0:
        return 0.0

    distances = np.linalg.norm(population - x, axis=1)
    k_nearest = np.partition(distances, min(k, len(distances)-1))[:k]
    avg_distance = np.mean(k_nearest)

    return scale * avg_distance


def gradient_alignment_reward(x: np.ndarray, gradient: np.ndarray,
                              direction: np.ndarray, scale: float = 1.0) -> float:
    """梯度对齐奖励

    奖励沿着梯度下降方向移动的解

    参数：
        x: 当前解
        gradient: 梯度向量
        direction: 移动方向
        scale: 缩放因子

    返回：
        奖励值（方向越对齐奖励越大）
    """
    if gradient is None or np.linalg.norm(gradient) < 1e-10:
        return 0.0

    # 计算方向与负梯度的余弦相似度
    grad_norm = gradient / (np.linalg.norm(gradient) + 1e-10)
    dir_norm = direction / (np.linalg.norm(direction) + 1e-10)
    alignment = -np.dot(grad_norm, dir_norm)  # 负梯度方向

    return scale * max(0, alignment)


# ==================== 常用罚函数库 ====================

def constraint_penalty(constraint_values: np.ndarray,
                      scale: float = 1.0) -> float:
    """标准约束罚函数

    参数：
        constraint_values: 约束值数组（g<=0为可行）
        scale: 缩放因子

    返回：
        惩罚值（违反约束越多惩罚越大）
    """
    if len(constraint_values) == 0:
        return 0.0

    violation = np.sum(np.maximum(constraint_values, 0))
    return scale * violation


def boundary_penalty(x: np.ndarray, bounds: List[tuple],
                    scale: float = 1.0) -> float:
    """边界惩罚

    惩罚超出变量边界的解

    参数：
        x: 决策变量
        bounds: 边界列表 [(min, max), ...]
        scale: 缩放因子

    返回：
        惩罚值
    """
    penalty = 0.0
    for i, (lb, ub) in enumerate(bounds):
        if x[i] < lb:
            penalty += (lb - x[i]) ** 2
        elif x[i] > ub:
            penalty += (x[i] - ub) ** 2

    return scale * penalty


def stagnation_penalty(generation: int, last_improvement_gen: int,
                      scale: float = 0.01) -> float:
    """停滞惩罚

    长时间未改进时增加惩罚，促进探索

    参数：
        generation: 当前代数
        last_improvement_gen: 上次改进的代数
        scale: 缩放因子

    返回：
        惩罚值
    """
    stagnation = generation - last_improvement_gen
    return scale * stagnation


# ==================== 便捷构造函数 ====================

def create_standard_bias(problem, reward_weight: float = 0.05,
                        penalty_weight: float = 1.0) -> BiasModule:
    """创建标准偏向模块

    包含：
    - 约束罚函数
    - 接近最优解奖励
    - 深度可行性奖励

    参数：
        problem: BlackBoxProblem 实例
        reward_weight: 奖励权重
        penalty_weight: 惩罚权重

    返回：
        配置好的 BiasModule
    """
    bias = BiasModule()

    # 添加约束罚函数
    def constraint_func(x):
        try:
            constraints = problem.evaluate_constraints(x)
            return constraint_penalty(np.asarray(constraints))
        except Exception:
            return 0.0

    bias.add_penalty(constraint_func, weight=penalty_weight, name="constraint")

    # 添加接近最优解奖励
    def proximity_func(x):
        if bias.history_best_x is None:
            return 0.0
        return proximity_reward(x, bias.history_best_x)

    bias.add_reward(proximity_func, weight=reward_weight, name="proximity")

    # 添加深度可行性奖励
    def feasibility_func(x):
        try:
            constraints = problem.evaluate_constraints(x)
            return feasibility_depth_reward(np.asarray(constraints))
        except Exception:
            return 0.0

    bias.add_reward(feasibility_func, weight=reward_weight * 0.5, name="feasibility")

    return bias
