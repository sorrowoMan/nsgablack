"""
贝叶斯优化偏置 - Bayesian Optimization Biases

将贝叶斯优化作为偏置策略，引导其他优化算法的搜索方向。

主要功能：
- 利用贝叶斯模型预测有潜力的区域
- 提供探索-利用平衡的偏置
- 自适应调整偏置强度
"""

import numpy as np
from typing import List, Dict, Any, Optional, Callable
from .bias_base import AlgorithmicBias, OptimizationContext
from ..solvers.bayesian_optimizer import BayesianOptimizer


class BayesianGuidanceBias(AlgorithmicBias):
    """
    贝叶斯引导偏置

    使用贝叶斯优化模型预测每个点的改进潜力，
    为其他优化算法（如NSGA-II）提供搜索指导。
    """

    def __init__(self,
                 weight: float = 0.2,
                 buffer_size: int = 50,
                 acquisition: str = 'ei',
                 kernel: str = 'rbf',
                 adaptive_weight: bool = True,
                 exploration_factor: float = 0.1):
        """
        初始化贝叶斯引导偏置

        Parameters:
        -----------
        weight : float
            偏置权重
        buffer_size : int
            历史数据缓冲区大小
        acquisition : str
            贝叶斯获取函数类型
        kernel : str
            核函数类型
        adaptive_weight : bool
            是否自适应调整权重
        exploration_factor : float
            探索因子（0-1）
        """
        super().__init__("bayesian_guidance", weight)
        self.buffer_size = buffer_size
        self.acquisition = acquisition
        self.kernel = kernel
        self.adaptive_weight = adaptive_weight
        self.exploration_factor = exploration_factor

        # 内部贝叶斯优化器
        self.local_bo = BayesianOptimizer(
            acquisition=acquisition,
            kernel=kernel
        )

        # 历史数据
        self.data_buffer = []
        self.last_update_gen = 0
        self.update_frequency = 5  # 每5代更新一次模型

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float],
              context: OptimizationContext) -> float:
        """应用贝叶斯引导偏置"""

        # 更新数据缓冲区
        self._update_buffer(context)

        # 如果数据不足，返回0
        if len(self.data_buffer) < 5:
            return 0.0

        # 定期更新贝叶斯模型
        if context.generation - self.last_update_gen >= self.update_frequency:
            self._update_model(eval_func)
            self.last_update_gen = context.generation

        # 预测改进潜力
        predicted_improvement = self._predict_improvement(x, context)

        # 自适应权重调整
        current_weight = self._adaptive_weight_adjustment(context)

        return current_weight * predicted_improvement

    def _update_buffer(self, context: OptimizationContext):
        """更新数据缓冲区"""
        if context.individual is not None and hasattr(context, 'individual_value'):
            # 添加新数据点
            self.data_buffer.append({
                'x': context.individual.copy(),
                'y': context.individual_value,
                'generation': context.generation
            })

            # 保持缓冲区大小
            if len(self.data_buffer) > self.buffer_size:
                self.data_buffer.pop(0)

    def _update_model(self, eval_func: Callable[[np.ndarray], float]):
        """更新贝叶斯模型"""
        if len(self.data_buffer) < 5:
            return

        # 提取数据
        X = np.array([item['x'] for item in self.data_buffer])
        y = np.array([item['y'] for item in self.data_buffer])

        # 重置并拟合模型
        self.local_bo.reset()
        for i in range(len(X)):
            self.local_bo.observe(X[i], y[i])

    def _predict_improvement(self, x: np.ndarray, context: OptimizationContext) -> float:
        """预测改进潜力"""
        if len(self.data_buffer) < 5:
            return 0.0

        try:
            # 获取当前最优值
            current_best = min([item['y'] for item in self.data_buffer])

            # 计算预测改进
            improvement_score = 0.0

            # 1. 基于获取函数的改进预测
            if hasattr(self.local_bo, 'gp') and self.local_bo.gp is not None:
                # 用贝叶斯模型预测
                mu, sigma = self.local_bo.gp.predict(x.reshape(1, -1), return_std=True)

                # 改进潜力（结合期望和不确定性）
                uncertainty_bonus = self.exploration_factor * sigma[0]
                expected_improvement = max(0, current_best - mu[0])

                improvement_score = expected_improvement + uncertainty_bonus

            # 2. 基于局部密度的调整
            if context.population:
                # 计算与最近邻的距离
                distances = [np.linalg.norm(x - ind) for ind in context.population]
                min_distance = min(distances)

                # 距离较小时给予奖励（鼓励探索）
                density_bonus = self.exploration_factor * min_distance
                improvement_score += density_bonus

            return max(0, improvement_score)

        except Exception as e:
            # 出错时返回0
            return 0.0

    def _adaptive_weight_adjustment(self, context: OptimizationContext) -> float:
        """自适应权重调整"""
        if not self.adaptive_weight:
            return self.weight

        # 根据收敛状态调整权重
        if hasattr(context, 'is_stuck') and context.is_stuck:
            # 陷入局部最优时增加权重
            return self.weight * 1.5
        elif context.generation > 50:
            # 后期逐渐减少权重，让算法收敛
            decay_factor = np.exp(-0.01 * (context.generation - 50))
            return self.weight * decay_factor
        else:
            return self.weight


class BayesianExplorationBias(AlgorithmicBias):
    """
    贝叶斯探索偏置

    专注于利用贝叶斯模型的不确定性信息，
    引导算法向高不确定性区域探索。
    """

    def __init__(self,
                 weight: float = 0.3,
                 uncertainty_threshold: float = 0.1,
                 decay_rate: float = 0.95):
        """
        初始化贝叶斯探索偏置

        Parameters:
        -----------
        weight : float
            偏置权重
        uncertainty_threshold : float
            不确定性阈值
        decay_rate : float
            权重衰减率
        """
        super().__init__("bayesian_exploration", weight)
        self.uncertainty_threshold = uncertainty_threshold
        self.decay_rate = decay_rate
        self.current_weight = weight

        # 贝叶斯模型
        self.bo = BayesianOptimizer(acquisition='ucb')
        self.exploration_history = []

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray]],
              context: OptimizationContext) -> float:
        """应用贝叶斯探索偏置"""

        # 收集数据
        if context.population and len(context.population) > 5:
            self._collect_data(context.population, eval_func)

        # 预测不确定性
        uncertainty = self._predict_uncertainty(x)

        # 基于不确定性计算偏置
        if uncertainty > self.uncertainty_threshold:
            # 高不确定性区域，给予奖励
            exploration_bonus = uncertainty * self.current_weight

            # 记录探索
            self.exploration_history.append({
                'x': x.copy(),
                'uncertainty': uncertainty,
                'generation': context.generation
            })

            # 衰减权重
            self.current_weight *= self.decay_rate

            return exploration_bonus

        return 0.0

    def _collect_data(self, population: List[np.ndarray], eval_func: Callable):
        """收集种群数据"""
        self.bo.reset()
        for ind in population:
            try:
                y = eval_func(ind)
                self.bo.observe(ind, y)
            except:
                pass

    def _predict_uncertainty(self, x: np.ndarray) -> float:
        """预测点的不确定性"""
        if len(self.bo.X_observed) < 5:
            return 0.0

        try:
            if hasattr(self.bo, 'gp') and self.bo.gp is not None:
                _, sigma = self.bo.gp.predict(x.reshape(1, -1), return_std=True)
                return sigma[0]
        except:
            pass

        return 0.0


class BayesianConvergenceBias(AlgorithmicBias):
    """
    贝叶斯收敛偏置

    利用贝叶斯模型的预测能力，
    在算法接近收敛时提供引导。
    """

    def __init__(self,
                 weight: float = 0.2,
                 convergence_threshold: float = 1e-4,
                 history_window: int = 20):
        """
        初始化贝叶斯收敛偏置

        Parameters:
        -----------
        weight : float
            偏置权重
        convergence_threshold : float
            收敛阈值
        history_window : int
            历史窗口大小
        """
        super().__init__("bayesian_convergence", weight)
        self.convergence_threshold = convergence_threshold
        self.history_window = history_window

        # 贝叶斯预测器
        self.predictor = BayesianOptimizer()
        self.convergence_history = []

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray]],
              context: OptimizationContext) -> float:
        """应用贝叶斯收敛偏置"""

        # 检查收敛状态
        is_converging = self._check_convergence(context)

        if is_converging:
            # 使用贝叶斯模型预测最优方向
            optimal_direction = self._predict_optimal_direction(x, eval_func)
            return self.weight * optimal_direction

        return 0.0

    def _check_convergence(self, context: OptimizationContext) -> bool:
        """检查是否在收敛"""
        if len(self.convergence_history) < self.history_window:
            return False

        # 计算最近改进
        recent_improvements = self.convergence_history[-self.history_window:]
        avg_improvement = np.mean(recent_improvements)

        return avg_improvement < self.convergence_threshold

    def _predict_optimal_direction(self, x: np.ndarray,
                                  eval_func: Callable[[np.ndarray]]) -> float:
        """预测最优方向"""
        if len(self.predictor.X_observed) < 10:
            return 0.0

        # 使用贝叶斯模型预测邻域
        epsilon = 1e-4
        direction_score = 0.0

        for i in range(len(x)):
            # 正方向
            x_plus = x.copy()
            x_plus[i] += epsilon
            try:
                y_plus = eval_func(x_plus)
            except:
                y_plus = float('inf')

            # 负方向
            x_minus = x.copy()
            x_minus[i] -= epsilon
            try:
                y_minus = eval_func(x_minus)
            except:
                y_minus = float('inf')

            # 计算方向梯度
            gradient_i = (y_plus - y_minus) / (2 * epsilon)
            direction_score -= abs(gradient_i)

        return max(0, direction_score)


# 便捷函数
def create_bayesian_guidance_bias(**kwargs) -> BayesianGuidanceBias:
    """创建贝叶斯引导偏置"""
    return BayesianGuidanceBias(**kwargs)


def create_bayesian_exploration_bias(**kwargs) -> BayesianExplorationBias:
    """创建贝叶斯探索偏置"""
    return BayesianExplorationBias(**kwargs)


def create_bayesian_convergence_bias(**kwargs) -> BayesianConvergenceBias:
    """创建贝叶斯收敛偏置"""
    return BayesianConvergenceBias(**kwargs)


def create_bayesian_suite() -> List[AlgorithmicBias]:
    """创建完整的贝叶斯偏置套件"""
    return [
        BayesianGuidanceBias(weight=0.2),
        BayesianExplorationBias(weight=0.15, uncertainty_threshold=0.1),
        BayesianConvergenceBias(weight=0.1, convergence_threshold=1e-4)
    ]


# 导出接口
__all__ = [
    'BayesianGuidanceBias',
    'BayesianExplorationBias',
    'BayesianConvergenceBias',
    'create_bayesian_guidance_bias',
    'create_bayesian_exploration_bias',
    'create_bayesian_convergence_bias',
    'create_bayesian_suite'
]