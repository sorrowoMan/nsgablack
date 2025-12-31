"""
梯度下降偏置实现模块

该模块实现梯度下降（Gradient Descent）算法思想的偏置化，将 GD 概念注入到任何优化算法中：
- 梯度方向转换为偏置值
- GD 的快速收敛能力注入
- 算法无关性的 GD 特性注入
- 与其他偏置的无缝组合

通过偏置系统，任何算法（GA、PSO、NSGA-II等）都可以获得 GD 的快速收敛能力。

GD 核心思想：x_new = x_old - learning_rate * gradient
转换为偏置：鼓励沿负梯度方向移动
"""

import numpy as np
from typing import List, Dict, Any, Optional, Callable
from ..core.base import AlgorithmicBias, OptimizationContext


class GradientDescentBias(AlgorithmicBias):
    """
    梯度下降偏置 - 将 GD 的梯度方向思想注入到任何算法

    核心思想是将梯度下降的负梯度方向转换为可计算的偏置值：
    - 沿负梯度方向移动（函数值下降最快的方向）
    - 适合快速局部收敛
    - 基于有限差分近似梯度

    通过这种转换，任何优化算法都能获得 GD 的快速收敛能力。
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        learning_rate: float = 0.1,     # 学习率
        epsilon: float = 1e-5,          # 有限差分步长
        gradient_method: str = "forward", # 梯度计算方法
        adaptive_lr: bool = False       # 自适应学习率
    ):
        """
        初始化梯度下降偏置

        Args:
            initial_weight: 初始偏置权重
            learning_rate: 学习率（步长大小）
                - 太大：可能震荡
                - 太小：收敛慢
            epsilon: 有限差分步长（用于数值计算梯度）
            gradient_method: 梯度计算方法
                - 'forward': 前向差分
                - 'central': 中心差分（更精确）
            adaptive_lr: 是否自适应调整学习率
        """
        super().__init__("gradient_descent", initial_weight, adaptive=True)

        # GD 核心参数
        self.learning_rate = learning_rate              # 学习率
        self.initial_learning_rate = learning_rate      # 初始学习率
        self.epsilon = epsilon                          # 有限差分步长
        self.gradient_method = gradient_method          # 梯度计算方法
        self.adaptive_lr = adaptive_lr                  # 自适应学习率

        # 历史记录
        self.gradient_history = []                      # 梯度历史
        self.gradient_magnitude_history = []            # 梯度大小历史
        self.step_size_history = []                     # 步长历史

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算梯度下降偏置值

        核心算法：
        1. 计算当前点的近似梯度（有限差分）
        2. 获取个体移动方向
        3. 计算沿负梯度方向的投影
        4. 转换为偏置值（鼓励沿负梯度方向移动）

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            GD 偏置值（负值表示奖励，正值表示惩罚）

        Note:
            上下文需要提供：
            - context.evaluate: 目标函数（用于计算梯度）
            - context.population: 当前种群
        """
        # 检查是否有评估函数
        if not hasattr(context, 'evaluate') or context.evaluate is None:
            # 无法计算梯度，回退到基于种群的近似
            return self._compute_population_based_bias(x, context)

        # ========== 计算梯度 ==========
        gradient = self._compute_gradient(x, context)

        # 记录历史
        self.gradient_history.append(gradient)
        gradient_magnitude = np.linalg.norm(gradient)
        self.gradient_magnitude_history.append(gradient_magnitude)

        # 如果梯度接近零，已经到达局部最优
        if gradient_magnitude < 1e-10:
            return 0.0

        # ========== 计算偏置值 ==========
        # 负梯度方向（下降方向）
        negative_gradient = -gradient

        # 个体移动方向（相对于种群中心）
        population = context.population
        population_center = np.mean(population, axis=0)
        move_direction = x - population_center

        # 如果在中心附近，无法判断方向
        if np.linalg.norm(move_direction) < 1e-10:
            return 0.0

        # 计算沿负梯度方向的投影
        # 归一化负梯度方向
        normalized_descent = negative_gradient / gradient_magnitude

        # 计算投影
        projection = np.dot(move_direction, normalized_descent)

        # 偏置值：
        # 正投影 → 沿下降方向移动 → 负偏置（奖励）
        # 负投影 → 沿上升方向移动 → 正偏置（惩罚）
        bias_value = -projection * 0.1

        # 自适应调整学习率
        if self.adaptive_lr:
            self._adapt_learning_rate(gradient_magnitude, context)

        return bias_value

    def _compute_gradient(self, x: np.ndarray, context: OptimizationContext) -> np.ndarray:
        """
        计算梯度（使用有限差分）

        Args:
            x: 当前点
            context: 优化上下文

        Returns:
            梯度向量
        """
        evaluate_func = context.evaluate

        # 计算当前点的函数值
        f_x = evaluate_func(x)

        gradient = np.zeros_like(x)

        if self.gradient_method == "forward":
            # 前向差分
            for i in range(len(x)):
                x_plus = x.copy()
                x_plus[i] += self.epsilon
                f_x_plus = evaluate_func(x_plus)
                gradient[i] = (f_x_plus - f_x) / self.epsilon

        elif self.gradient_method == "central":
            # 中心差分（更精确）
            for i in range(len(x)):
                x_plus = x.copy()
                x_plus[i] += self.epsilon
                f_x_plus = evaluate_func(x_plus)

                x_minus = x.copy()
                x_minus[i] -= self.epsilon
                f_x_minus = evaluate_func(x_minus)

                gradient[i] = (f_x_plus - f_x_minus) / (2 * self.epsilon)

        return gradient

    def _compute_population_based_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        基于种群的近似偏置（当无法计算梯度时）

        使用种群中最好的解的方向作为近似下降方向。

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            近似偏置值
        """
        population = context.population

        # 如果没有适应度信息，无法计算
        if context.fitness is None:
            return 0.0

        # 找到最优个体
        best_idx = np.argmin(context.fitness)
        best_point = population[best_idx]

        # 计算到最优点的方向
        direction_to_best = best_point - x

        # 如果已经在最优解附近，给予奖励
        distance = np.linalg.norm(direction_to_best)

        if distance < self.learning_rate:
            # 在最优解附近
            return -0.2
        else:
            # 远离最优解，给予惩罚
            return 0.1 * distance

    def _adapt_learning_rate(self, gradient_magnitude: float, context: OptimizationContext):
        """
        自适应调整学习率

        策略：
        - 梯度大：可能离最优解远，保持或增大学习率
        - 梯度小：可能接近最优解，减小学习率
        """
        if not self.gradient_magnitude_history:
            return

        # 梯度变化率
        if len(self.gradient_magnitude_history) > 1:
            gradient_change = (
                self.gradient_magnitude_history[-1] -
                self.gradient_magnitude_history[-2]
            )
        else:
            gradient_change = 0

        if gradient_magnitude < 0.01:
            # 接近最优解，减小学习率
            self.learning_rate = max(self.learning_rate * 0.95, 1e-6)
        elif gradient_magnitude > 1.0 and gradient_change > 0:
            # 梯度增大，可能需要更大步长
            self.learning_rate = min(self.learning_rate * 1.05, 1.0)

    def get_descent_direction(
        self,
        x: np.ndarray,
        context: OptimizationContext
    ) -> np.ndarray:
        """
        获取下降方向（辅助方法）

        这个方法可以直接用于生成新的候选解。

        Args:
            x: 当前点
            context: 优化上下文

        Returns:
            下降方向向量
        """
        gradient = self._compute_gradient(x, context)
        return -gradient / (np.linalg.norm(gradient) + 1e-10)

    def generate_descent_point(
        self,
        x: np.ndarray,
        context: OptimizationContext
    ) -> np.ndarray:
        """
        生成下降点（辅助方法）

        完全模拟 GD 的行为：x_new = x - learning_rate * gradient

        Args:
            x: 当前点
            context: 优化上下文

        Returns:
            新的候选解
        """
        gradient = self._compute_gradient(x, context)
        new_point = x - self.learning_rate * gradient
        return new_point

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取 GD 偏置统计信息

        Returns:
            包含各种统计指标的字典
        """
        if not self.gradient_magnitude_history:
            return {
                'current_learning_rate': self.learning_rate,
                'initial_learning_rate': self.initial_learning_rate,
                'avg_gradient_magnitude': 0,
                'gradient_method': self.gradient_method
            }

        return {
            'current_learning_rate': self.learning_rate,                    # 当前学习率
            'initial_learning_rate': self.initial_learning_rate,            # 初始学习率
            'avg_gradient_magnitude': np.mean(self.gradient_magnitude_history),  # 平均梯度大小
            'last_gradient_magnitude': self.gradient_magnitude_history[-1],      # 最近梯度大小
            'gradient_method': self.gradient_method,                        # 梯度计算方法
            'gradient_history': [g.tolist() for g in self.gradient_history[-5:]]  # 最近5次梯度
        }


class MomentumGradientDescentBias(GradientDescentBias):
    """
    动量梯度下降偏置

    在标准 GD 偏置基础上增加动量项：
    - 加速收敛
    - 减少震荡
    - 更好地穿越平坦区域
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        learning_rate: float = 0.1,
        epsilon: float = 1e-5,
        momentum: float = 0.9          # 动量系数
    ):
        """
        初始化动量 GD 偏置

        Args:
            initial_weight: 初始权重
            learning_rate: 学习率
            epsilon: 有限差分步长
            momentum: 动量系数 [0, 1]
        """
        super().__init__(initial_weight, learning_rate, epsilon)

        self.momentum = momentum                    # 动量系数
        self.velocity = None                        # 速度向量

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算动量 GD 偏置值

        在标准 GD 计算基础上增加动量项。
        """
        # 计算梯度
        gradient = self._compute_gradient(x, context)

        # 初始化速度
        if self.velocity is None:
            self.velocity = np.zeros_like(gradient)

        # 更新速度（包含动量）
        self.velocity = self.momentum * self.velocity - self.learning_rate * gradient

        # 记录梯度
        self.gradient_history.append(gradient)
        self.gradient_magnitude_history.append(np.linalg.norm(gradient))

        # 计算偏置（基于动量方向）
        population = context.population
        population_center = np.mean(population, axis=0)
        move_direction = x - population_center

        # 使用速度方向而不是纯梯度方向
        if np.linalg.norm(self.velocity) > 1e-10:
            normalized_velocity = self.velocity / np.linalg.norm(self.velocity)
            projection = np.dot(move_direction, normalized_velocity)
            bias_value = -projection * 0.1
        else:
            bias_value = 0.0

        return bias_value


class AdaptiveGradientDescentBias(GradientDescentBias):
    """
    自适应梯度下降偏置（类似 Adagrad）

    在标准 GD 偏置基础上增加自适应学习率：
    - 每个维度有自己的学习率
    - 梯度大的维度学习率减小更快
    - 梯度小的维度学习率保持较大
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        learning_rate: float = 0.1,
        epsilon: float = 1e-5,
        adagrad_epsilon: float = 1e-8
    ):
        """
        初始化自适应 GD 偏置

        Args:
            initial_weight: 初始权重
            learning_rate: 全局学习率
            epsilon: 有限差分步长
            adagrad_epsilon: Adagrad 平滑项
        """
        super().__init__(initial_weight, learning_rate, epsilon)

        self.adagrad_epsilon = adagrad_epsilon            # Adagrad 平滑项
        self.gradient_squared_sum = None                 # 梯度平方和

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算自适应 GD 偏置值

        使用 Adagrad 风格的自适应学习率。
        """
        # 计算梯度
        gradient = self._compute_gradient(x, context)

        # 初始化梯度平方和
        if self.gradient_squared_sum is None:
            self.gradient_squared_sum = np.zeros_like(gradient)

        # 累积梯度平方
        self.gradient_squared_sum += gradient ** 2

        # 记录梯度
        self.gradient_history.append(gradient)
        self.gradient_magnitude_history.append(np.linalg.norm(gradient))

        # 计算偏置（使用自适应学习率）
        population = context.population
        population_center = np.mean(population, axis=0)
        move_direction = x - population_center

        # 自适应学习率：每个维度不同
        adaptive_lr = self.learning_rate / (
            np.sqrt(self.gradient_squared_sum) + self.adagrad_epsilon
        )

        # 加权梯度方向
        weighted_gradient = gradient * adaptive_lr

        if np.linalg.norm(weighted_gradient) > 1e-10:
            normalized_weighted = -weighted_gradient / np.linalg.norm(weighted_gradient)
            projection = np.dot(move_direction, normalized_weighted)
            bias_value = -projection * 0.1
        else:
            bias_value = 0.0

        return bias_value


class AdamGradientBias(GradientDescentBias):
    """
    Adam（Adaptive Moment Estimation）偏置

    结合动量和自适应学习率的优点：
    - 动量项（一阶矩）
    - 自适应学习率（二阶矩）
    - 偏差修正
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        learning_rate: float = 0.01,      # Adam 通常用较小的学习率
        beta1: float = 0.9,               # 一阶矩衰减率
        beta2: float = 0.999,             # 二阶矩衰减率
        epsilon: float = 1e-8
    ):
        """
        初始化 Adam 偏置

        Args:
            initial_weight: 初始权重
            learning_rate: 学习率
            beta1: 一阶矩（动量）衰减率
            beta2: 二阶矩（未中心方差）衰减率
            epsilon: 平滑项
        """
        # Adam 的 epsilon 是用于梯度计算的，不是有限差分
        super().__init__(initial_weight, learning_rate, epsilon=1e-5)

        self.beta1 = beta1
        self.beta2 = beta2
        self.adam_epsilon = epsilon

        self.m = None        # 一阶矩（动量）
        self.v = None        # 二阶矩（未中心方差）
        self.t = 0           # 时间步

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算 Adam 偏置值

        使用 Adam 算法的自适应学习方法。
        """
        self.t += 1

        # 计算梯度
        gradient = self._compute_gradient(x, context)

        # 初始化矩
        if self.m is None:
            self.m = np.zeros_like(gradient)
            self.v = np.zeros_like(gradient)

        # 更新一阶矩（动量）
        self.m = self.beta1 * self.m + (1 - self.beta1) * gradient

        # 更新二阶矩
        self.v = self.beta2 * self.v + (1 - self.beta2) * (gradient ** 2)

        # 偏差修正
        m_hat = self.m / (1 - self.beta1 ** self.t)
        v_hat = self.v / (1 - self.beta2 ** self.t)

        # 记录梯度
        self.gradient_history.append(gradient)
        self.gradient_magnitude_history.append(np.linalg.norm(gradient))

        # 计算偏置（使用 Adam 更新方向）
        population = context.population
        population_center = np.mean(population, axis=0)
        move_direction = x - population_center

        # Adam 更新方向
        adam_direction = -m_hat / (np.sqrt(v_hat) + self.adam_epsilon)

        if np.linalg.norm(adam_direction) > 1e-10:
            normalized_adam = adam_direction / np.linalg.norm(adam_direction)
            projection = np.dot(move_direction, normalized_adam)
            bias_value = -projection * 0.1
        else:
            bias_value = 0.0

        return bias_value


# ========== 工具函数 ==========

def generate_gradient_descent_point(
    x: np.ndarray,
    evaluate_func: Callable,
    learning_rate: float = 0.1,
    epsilon: float = 1e-5
) -> np.ndarray:
    """
    生成梯度下降点的便捷函数

    Args:
        x: 当前点
        evaluate_func: 目标函数
        learning_rate: 学习率
        epsilon: 有限差分步长

    Returns:
        梯度下降后的新点
    """
    gradient = np.zeros_like(x)
    f_x = evaluate_func(x)

    # 前向差分
    for i in range(len(x)):
        x_plus = x.copy()
        x_plus[i] += epsilon
        f_x_plus = evaluate_func(x_plus)
        gradient[i] = (f_x_plus - f_x) / epsilon

    # 梯度下降
    new_point = x - learning_rate * gradient
    return new_point
