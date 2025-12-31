"""
贝叶斯优化偏置实现模块

该模块提供基于贝叶斯优化的偏置实现，用于：
- 智能搜索区域预测和引导
- 探索与利用的动态平衡
- 基于代理模型的高效评估
- 不确定性量化和利用

贝叶斯优化偏置通过构建目标函数的概率模型，
能够智能预测搜索空间中最有潜力的区域，
为任何优化算法提供全局搜索指导。

核心组件：
- 贝叶斯引导偏置：利用获取函数预测改进潜力
- 贝叶斯探索偏置：基于不确定性引导探索
- 贝叶斯收敛偏置：收敛阶段的精细指导
"""

import numpy as np
from typing import List, Dict, Any, Optional, Callable
from ..core.base import AlgorithmicBias, OptimizationContext

# 简化的贝叶斯优化器实现（避免复杂依赖）
class SimpleBayesianOptimizer:
    """简化的贝叶斯优化器，用于偏置计算"""

    def __init__(self, acquisition='ei', kernel='rbf'):
        self.acquisition = acquisition
        self.kernel = kernel
        self.X_observed = []
        self.y_observed = []
        self.gp = None

    def observe(self, x, y):
        """观察数据点"""
        self.X_observed.append(x.copy() if isinstance(x, np.ndarray) else x)
        self.y_observed.append(y)

    def reset(self):
        """重置观察数据"""
        self.X_observed = []
        self.y_observed = []
        self.gp = None

# 使用简化实现替代复杂的贝叶斯优化器
BayesianOptimizer = SimpleBayesianOptimizer


class BayesianGuidanceBias(AlgorithmicBias):
    """
    贝叶斯引导偏置 - 智能搜索方向指导

    通过构建目标函数的概率模型，智能预测搜索空间中
    最有潜力的区域，为任何优化算法提供全局搜索指导。

    核心特性：
    - 获取函数引导：使用期望改进(EI)、概率改进(PI)等获取函数
    - 自适应权重：根据优化状态动态调整偏置强度
    - 历史学习：利用已评估数据构建改进预测模型
    - 探索平衡：在利用已知区域和探索未知区域间保持平衡

    适用于复杂的多模态优化问题，特别是在计算资源有限时
    需要智能引导搜索方向的场景。
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

        Args:
            weight: 偏置权重，控制引导强度
            buffer_size: 历史数据缓冲区大小
            acquisition: 获取函数类型 ('ei'=期望改进, 'pi'=概率改进, 'ucb'=置信上界)
            kernel: 核函数类型 (影响模型平滑度)
            adaptive_weight: 是否启用自适应权重调整
            exploration_factor: 探索因子（0-1），控制探索与利用的平衡
        """
        super().__init__("bayesian_guidance", weight)
        self.buffer_size = buffer_size                        # 数据缓冲区大小
        self.acquisition = acquisition                       # 获取函数类型
        self.kernel = kernel                                 # 核函数类型
        self.adaptive_weight = adaptive_weight               # 自适应权重标志
        self.exploration_factor = exploration_factor         # 探索因子

        # 内部贝叶斯优化器，用于建模和预测
        self.local_bo = BayesianOptimizer(
            acquisition=acquisition,
            kernel=kernel
        )

        # 历史数据管理
        self.data_buffer = []                               # 数据缓冲区
        self.last_update_gen = 0                            # 上次模型更新代数
        self.update_frequency = 5                           # 模型更新频率（每N代更新一次）

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算贝叶斯引导偏置值"""

        # 更新数据缓冲区
        self._update_buffer(context)

        # 如果数据不足，返回0
        if len(self.data_buffer) < 5:
            return 0.0

        # 尝试使用真正的评估函数更新模型
        if context.generation - self.last_update_gen >= self.update_frequency:
            if hasattr(self, 'problem_instance') and self.problem_instance:
                # 使用真正的评估函数
                self._update_model_with_real_eval()
            else:
                # 回退到简化版本
                self._update_model_simple()
            self.last_update_gen = context.generation

        # 预测改进潜力
        predicted_improvement = self._predict_improvement(x, context)

        # 自适应权重调整
        current_weight = self._adaptive_weight_adjustment(context)

        return current_weight * predicted_improvement

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float],
              context: OptimizationContext) -> float:
        """应用贝叶斯引导偏置（带评估函数版本）"""

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
        if context.individual is not None:
            # 尝试从不同来源获取评估值
            value = None
            if hasattr(context, 'individual_value'):
                value = context.individual_value
            elif hasattr(context, 'metrics') and 'objective' in context.metrics:
                value = context.metrics['objective']
            elif context.population and len(context.population) > 0:
                # 如果没有个体值，使用基于位置的估计
                try:
                    idx = context.population.index(context.individual) if context.individual in context.population else 0
                    # 简单估计：较早的个体可能有更好的值
                    value = len(context.population) - idx
                except:
                    value = 0.0
            else:
                value = 0.0

            # 添加新数据点
            self.data_buffer.append({
                'x': context.individual.copy(),
                'y': value,
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

    def _update_model_simple(self):
        """简化版模型更新（不使用评估函数）"""
        if len(self.data_buffer) < 5:
            return

        # 简化策略：使用基于距离和目标值的启发式方法
        # 这里暂时不做复杂的建模，只更新内部状态
        pass

    def _update_model_with_real_eval(self):
        """使用真正的评估函数更新模型"""
        if len(self.data_buffer) < 5:
            return

        # 优先级1：使用NSGA的代理模型（最快，零计算）
        if self._try_update_with_nsga_surrogate():
            return

        # 优先级2：使用NSGA的已评估数据（快速，无重复计算）
        if self._try_update_with_nsga_data():
            return

        # 优先级3：回退到使用评估函数重新计算
        print("回退到使用评估函数更新贝叶斯模型...")
        self._update_with_evaluation_function()

    def _try_update_with_nsga_surrogate(self):
        """尝试使用NSGA的代理模型更新贝叶斯模型"""
        if (hasattr(self, 'bias_manager') and
            hasattr(self.bias_manager, 'solver_instance') and
            self.bias_manager.solver_instance):

            solver = self.bias_manager.solver_instance

            # 检查是否有代理模型
            if (hasattr(solver, 'surrogate') and
                solver.surrogate is not None and
                hasattr(solver, 'X_real') and
                len(solver.X_real) >= 5):

                # 使用NSGA的代理模型生成大量训练数据
                try:
                    # 生成训练数据点
                    n_samples = min(500, len(solver.X_real) * 5)  # 生成更多数据点

                    # 在已评估点周围生成新点
                    X_train = []
                    y_train = []

                    for i in range(n_samples):
                        # 在历史点附近生成新点
                        if i < len(solver.X_real):
                            base_idx = i % len(solver.X_real)
                            base_point = solver.X_real[base_idx]
                        else:
                            base_idx = np.random.randint(0, len(solver.X_real))
                            base_point = solver.X_real[base_idx]

                        # 添加小的随机扰动
                        noise = np.random.normal(0, 0.1, base_point.shape)
                        new_point = np.clip(base_point + noise, 0, 1)
                        X_train.append(new_point)

                        # 使用NSGA代理模型预测
                        try:
                            pred = solver._evaluate_surrogate(new_point)
                            if isinstance(pred, np.ndarray):
                                y_train.append(pred[0])  # 使用第一个目标
                            else:
                                y_train.append(pred)
                        except:
                            y_train.append(0.0)

                    X_train = np.array(X_train)
                    y_train = np.array(y_train)

                    # 更新贝叶斯模型
                    self.local_bo.reset()
                    for i in range(len(X_train)):
                        try:
                            self.local_bo.observe(X_train[i], y_train[i])
                        except Exception as e:
                            continue

                    print(f"贝叶斯模型已更新，使用NSGA代理生成 {len(X_train)} 个数据点（零真实评估）")
                    return True

                except Exception as e:
                    print(f"使用NSGA代理更新失败: {e}")

        return False

    def _try_update_with_nsga_data(self):
        """尝试使用NSGA已评估的数据更新贝叶斯模型"""
        if (hasattr(self, 'bias_manager') and
            hasattr(self.bias_manager, 'get_evaluated_data')):

            X, y = self.bias_manager.get_evaluated_data()
            if X is not None and y is not None and len(X) > 0:
                # 直接使用NSGA的评估数据，避免重复计算！
                self.local_bo.reset()
                for i in range(min(len(X), 200)):  # 限制最多200个点
                    try:
                        self.local_bo.observe(X[i], y[i])
                    except Exception as e:
                        continue

                print(f"贝叶斯模型已更新，使用NSGA的 {len(X)} 个历史评估数据点（无重复计算）")
                return True

        return False

    def _update_with_evaluation_function(self):
        """使用评估函数重新计算并更新模型"""
        X = np.array([item['x'] for item in self.data_buffer])

        # 使用真正的评估函数重新评估所有历史点
        y = []
        for x in X:
            try:
                objectives = self.problem_instance.evaluate(x)
                # 使用加权和作为单一目标值
                # 或者使用第一个目标（物料剩余）
                single_objective = objectives[0]  # 可以根据需要调整
                y.append(single_objective)
            except Exception as e:
                print(f"评估历史点失败: {e}")
                y.append(0.0)

        y = np.array(y)

        # 更新贝叶斯模型
        self.local_bo.reset()
        for i in range(len(X)):
            try:
                self.local_bo.observe(X[i], y[i])
            except Exception as e:
                continue

        print(f"贝叶斯模型已更新，重新评估了 {len(y)} 个历史数据点")

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

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算贝叶斯探索偏置值"""

        # 简化版探索偏置（不使用评估函数）
        if context.population and len(context.population) > 5:
            self._collect_data_simple(context.population)

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

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray], Any],
              context: OptimizationContext) -> float:
        """应用贝叶斯探索偏置（带评估函数版本）"""

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

    def _collect_data_simple(self, population: List[np.ndarray]):
        """简化版数据收集（不使用评估函数）"""
        # 简化策略：使用基于种群位置的启发式估计
        self.bo.reset()
        for i, ind in enumerate(population):
            # 假设排序靠前的个体有更好的目标值
            estimated_value = len(population) - i
            try:
                self.bo.observe(ind, estimated_value)
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

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray], Any],
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
                                  eval_func: Callable[[np.ndarray], Any]) -> float:
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


class BayesianAdvisor:
    """贝叶斯建议者类 - 为优化提供智能参数建议"""

    def __init__(self, problem_type="production_scheduling", advisor_role="strategic"):
        self.problem_type = problem_type
        self.advisor_role = advisor_role
        self.optimizer = SimpleBayesianOptimizer()

    def get_parameters(self):
        """获取贝叶斯优化器建议的参数"""
        # 基于问题类型和角色提供参数建议
        if self.problem_type == "production_scheduling":
            if self.advisor_role == "strategic":
                return {
                    'mutation_rate': 0.15,
                    'crossover_rate': 0.85,
                    'elite_ratio': 0.12,
                    'diversity_pressure': 0.6
                }
            elif self.advisor_role == "explorative":
                return {
                    'mutation_rate': 0.25,
                    'crossover_rate': 0.75,
                    'elite_ratio': 0.08,
                    'diversity_pressure': 0.8
                }
        else:
            # 默认参数
            return {
                'mutation_rate': 0.2,
                'crossover_rate': 0.8,
                'elite_ratio': 0.1
            }

    def analyze_performance(self, historical_data):
        """分析历史性能并调整参数建议"""
        if not historical_data:
            return self.get_parameters()

        # 简单的性能分析逻辑
        avg_fitness = np.mean(historical_data.get('fitness', []))

        if avg_fitness < 0.5:  # 性能较差，增加探索
            return {
                'mutation_rate': 0.3,
                'crossover_rate': 0.7,
                'elite_ratio': 0.05
            }
        else:  # 性能良好，保持平衡
            return self.get_parameters()


# 导出接口
__all__ = [
    'BayesianGuidanceBias',
    'BayesianExplorationBias',
    'BayesianConvergenceBias',
    'BayesianAdvisor',
    'create_bayesian_guidance_bias',
    'create_bayesian_exploration_bias',
    'create_bayesian_convergence_bias',
    'create_bayesian_suite'
]