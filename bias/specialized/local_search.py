"""
局部搜索偏置实现模块

该模块提供各种局部搜索偏置，用于：
- 基于梯度的精细局部优化
- 无梯度优化方法集成
- 局部收敛性增强
- 二阶导数信息利用

局部搜索偏置适用于优化后期需要精细调整的阶段，
能够显著提高解的精度和收敛速度。

主要偏置类型：
- 梯度下降偏置：动量梯度下降、自适应学习率
- 牛顿法偏置：二阶导数信息、阻尼牛顿法
- 线搜索偏置：Armijo准则、Wolfe条件
- 信赖域偏置：自适应搜索区域调整
- 单纯形法偏置：无导数优化方法
"""

import numpy as np
from typing import Callable, List, Optional, Dict, Any
from ..core.base import AlgorithmicBias, OptimizationContext


class GradientDescentBias(AlgorithmicBias):
    """
    梯度下降偏置 - 动量梯度下降优化引导

    实现高级梯度下降算法，包括：
    - 动量加速：累积历史梯度方向，加速收敛
    - Nesterov动量：前瞻性动量更新，改善收敛性
    - 自适应学习率：根据优化进展动态调整学习率
    - 方向对齐检查：评估梯度方向与最优解方向的一致性

    适用于光滑、可导的目标函数，在局部搜索阶段效果显著。
    """
    context_requires = ("problem_data",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: problem_data; outputs scalar bias only."



    def __init__(self, weight: float = 0.2, learning_rate: float = 0.01,
                 momentum: float = 0.9, adaptive_lr: bool = True,
                 nesterov: bool = False):
        """
        初始化梯度下降偏置

        Args:
            weight: 偏置权重
            learning_rate: 初始学习率
            momentum: 动量系数（0-1之间，越大惯性越强）
            adaptive_lr: 是否启用自适应学习率
            nesterov: 是否使用Nesterov加速梯度
        """
        super().__init__("gradient_descent", weight)
        self.learning_rate = learning_rate                        # 学习率
        self.momentum = momentum                                 # 动量系数
        self.adaptive_lr = adaptive_lr                           # 自适应学习率标志
        self.nesterov = nesterov                                 # Nesterov动量标志
        self.velocity = None                                     # 速度向量（动量）
        self.adaptive_factor = 1.0                              # 自适应调整因子
        self.improvement_history = []                           # 改进历史记录
        self.last_gradient = None                               # 上次计算的梯度

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算梯度下降偏置值

        算法流程：
        1. 计算当前点的数值梯度
        2. 更新动量向量
        3. 计算前瞻位置
        4. 评估改进潜力和方向对齐度

        Args:
            x: 当前个体位置
            context: 优化上下文，需要包含评估函数

        Returns:
            梯度下降偏置值（正值表示有改进潜力）
        """
        # 从上下文获取评估函数
        eval_func = context.problem_data.get('eval_func')
        if eval_func is None:
            return 0.0

        # 计算梯度
        gradient = self._compute_gradient(x, eval_func)
        self.last_gradient = gradient

        # 初始化速度
        if self.velocity is None:
            self.velocity = np.zeros_like(x)

        # 自适应学习率调整
        if self.adaptive_lr and len(self.improvement_history) > 5:
            recent_improvements = self.improvement_history[-5:]
            if np.mean(recent_improvements) < 0:
                self.adaptive_factor *= 0.95  # 改进不佳时减小学习率
            else:
                self.adaptive_factor *= 1.02  # 改进良好时稍微增大学习率
            self.adaptive_factor = np.clip(self.adaptive_factor, 0.1, 3.0)

        # 更新速度向量（含动量）
        if self.nesterov:
            # Nesterov动量：先更新到前瞻位置
            self.velocity = self.momentum * self.velocity - self.learning_rate * self.adaptive_factor * gradient
            lookahead = x + self.momentum * self.velocity
        else:
            # 标准动量更新
            self.velocity = self.momentum * self.velocity - self.learning_rate * self.adaptive_factor * gradient
            lookahead = x + self.velocity

        # 评估改进潜力和方向对齐度
        if context.problem_data.get('best_solution') is not None:
            best_solution = context.problem_data['best_solution']
            direction_to_best = best_solution - x

            if self.nesterov:
                actual_step = lookahead - x
            else:
                actual_step = self.velocity

            # 计算方向对齐度
            alignment = np.dot(actual_step, direction_to_best)

            # 记录实际改进
            current_value = eval_func(x)
            lookahead_value = eval_func(lookahead)
            improvement = current_value - lookahead_value
            self.improvement_history.append(improvement)

            # 限制历史记录长度
            if len(self.improvement_history) > 20:
                self.improvement_history.pop(0)

            return self.weight * max(0, alignment)
        else:
            # 无参考点时，返回梯度下降的改进潜力
            gradient_magnitude = np.linalg.norm(gradient)
            return self.weight * gradient_magnitude * self.learning_rate * self.adaptive_factor

    def _compute_gradient(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> np.ndarray:
        """
        计算数值梯度（中心差分法）

        使用中心差分公式计算梯度，比前向差分更精确：
        ∇f(x)_i ≈ [f(x + h*e_i) - f(x - h*e_i)] / (2h)

        Args:
            x: 当前点
            eval_func: 目标函数

        Returns:
            梯度向量
        """
        gradient = np.zeros_like(x)
        eps = 1e-6  # 数值微分步长

        for i in range(len(x)):
            x_plus = x.copy()
            x_minus = x.copy()
            x_plus[i] += eps
            x_minus[i] -= eps

            f_plus = eval_func(x_plus)
            f_minus = eval_func(x_minus)
            gradient[i] = (f_plus - f_minus) / (2 * eps)

        return gradient


class NewtonMethodBias(AlgorithmicBias):
    """牛顿法偏置 - 使用二阶导数信息"""
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def __init__(self, weight: float = 0.3, regularization: float = 1e-6,
                 damping: float = 0.1, use_damped_newton: bool = True,
                 use_bfgs_approx: bool = False):
        super().__init__("newton_method", weight)
        self.regularization = regularization
        self.damping = damping
        self.use_damped_newton = use_damped_newton
        self.use_bfgs_approx = use_bfgs_approx
        self.last_hessian = None
        self.approx_inverse_hessian = None

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float],
              context: OptimizationContext) -> float:
        """应用牛顿法偏置"""
        # 计算梯度和Hessian矩阵
        gradient = self._compute_gradient(x, eval_func)

        if self.use_bfgs_approx and self.approx_inverse_hessian is not None:
            # 使用BFGS近似的逆Hessian
            newton_step = self.approx_inverse_hessian @ gradient
        else:
            hessian = self._compute_hessian(x, eval_func)
            self.last_hessian = hessian

            # 正则化避免奇异性
            hessian += self.regularization * np.eye(len(x))

            try:
                # 计算牛顿步
                if self.use_damped_newton:
                    newton_step = self._damped_newton_step(gradient, hessian)
                else:
                    newton_step = np.linalg.solve(hessian, gradient)

                # 更新BFGS近似
                if self.use_bfgs_approx and self.approx_inverse_hessian is None:
                    self.approx_inverse_hessian = np.eye(len(x))

            except np.linalg.LinAlgError:
                # Hessian矩阵奇异时退化为梯度下降
                return -self.weight * np.linalg.norm(gradient) * 0.01

        # 评估改进潜力
        expected_improvement = -0.5 * np.dot(gradient, newton_step)

        # 更新BFGS近似
        if self.use_bfgs_approx and hasattr(self, 'last_x'):
            self._update_bfgs_approx(x, gradient)
        self.last_x = x.copy()
        self.last_gradient = gradient.copy()

        return self.weight * expected_improvement

    def _update_bfgs_approx(self, x_new: np.ndarray, grad_new: np.ndarray):
        """更新BFGS近似"""
        s = x_new - self.last_x
        y = grad_new - self.last_gradient

        sy = np.dot(s, y)
        if sy > 1e-10:  # 避免除零
            Hs = self.approx_inverse_hessian @ s
            self.approx_inverse_hessian += (
                np.outer(s, s) / sy - np.outer(Hs, Hs) / np.dot(s, Hs)
            )

    def _compute_gradient(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> np.ndarray:
        """计算梯度"""
        gradient = np.zeros_like(x)
        eps = 1e-6

        for i in range(len(x)):
            x_plus = x.copy()
            x_plus[i] += eps
            f_plus = eval_func(x_plus)
            f_current = eval_func(x)
            gradient[i] = (f_plus - f_current) / eps

        return gradient

    def _compute_hessian(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> np.ndarray:
        """计算Hessian矩阵（对角近似以提高效率）"""
        n = len(x)
        hessian = np.zeros((n, n))
        eps = 1e-5

        # 对角元素（二阶导数）
        for i in range(n):
            x_plus = x.copy()
            x_minus = x.copy()
            x_plus[i] += eps
            x_minus[i] -= eps

            f_plus = eval_func(x_plus)
            f_minus = eval_func(x_minus)
            f_current = eval_func(x)
            hessian[i, i] = (f_plus - 2 * f_current + f_minus) / (eps ** 2)

        # 可选：计算部分非对角元素（对于高维问题太慢）
        # 这里省略以提高计算效率

        return hessian

    def _damped_newton_step(self, gradient: np.ndarray, hessian: np.ndarray) -> np.ndarray:
        """阻尼牛顿步（Levenberg-Marquardt）"""
        I = np.eye(len(gradient))
        lambda_damping = self.damping

        # 迭代调整阻尼因子
        for _ in range(10):
            try:
                step = np.linalg.solve(hessian + lambda_damping * I, gradient)
                if np.linalg.norm(step) < 1.0:  # 步长合理
                    break
                lambda_damping *= 2
            except np.linalg.LinAlgError:
                lambda_damping *= 2

        return step


class LineSearchBias(AlgorithmicBias):
    """线搜索偏置 - 实现Armijo线搜索和Wolfe条件"""
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def __init__(self, weight: float = 0.15, method: str = 'armijo',
                 alpha: float = 0.5, beta: float = 0.8, max_iter: int = 20,
                 use_wolfe: bool = False, wolfe_c1: float = 1e-4, wolfe_c2: float = 0.9):
        super().__init__("line_search", weight)
        self.method = method
        self.alpha = alpha  # Armijo条件参数
        self.beta = beta    # 回缩因子
        self.max_iter = max_iter
        self.use_wolfe = use_wolfe
        self.wolfe_c1 = wolfe_c1  # Wolfe条件常数
        self.wolfe_c2 = wolfe_c2
        self.last_step_size = 1.0

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float],
              context: OptimizationContext) -> float:
        """应用线搜索偏置"""
        # 需要搜索方向
        if not hasattr(context, 'search_direction') or context.search_direction is None:
            # 如果没有搜索方向，使用负梯度方向
            gradient = self._compute_gradient(x, eval_func)
            context.search_direction = -gradient

        direction = context.search_direction
        f_current = eval_func(x)

        # 执行线搜索
        step_size = self._line_search(x, direction, eval_func, f_current)
        self.last_step_size = step_size

        # 返回步长作为偏置（表示找到的改进潜力）
        return self.weight * step_size

    def _line_search(self, x: np.ndarray, direction: np.ndarray,
                    eval_func: Callable[[np.ndarray], float],
                    f_current: float) -> float:
        """线搜索实现"""
        step_size = self.last_step_size if self.last_step_size > 0 else 1.0

        if self.use_wolfe:
            return self._wolfe_line_search(x, direction, eval_func, f_current, step_size)
        else:
            return self._armijo_line_search(x, direction, eval_func, f_current, step_size)

    def _armijo_line_search(self, x: np.ndarray, direction: np.ndarray,
                           eval_func: Callable[[np.ndarray], float],
                           f_current: float, step_size: float) -> float:
        """Armijo线搜索"""
        for _ in range(self.max_iter):
            x_new = x + step_size * direction
            f_new = eval_func(x_new)

            # Armijo条件检查
            if f_new <= f_current + self.alpha * step_size * np.dot(direction, direction):
                return step_size

            # 回缩步长
            step_size *= self.beta

            if step_size < 1e-10:
                break

        return max(step_size, 1e-10)

    def _wolfe_line_search(self, x: np.ndarray, direction: np.ndarray,
                          eval_func: Callable[[np.ndarray], float],
                          f_current: float, step_size: float) -> float:
        """强Wolfe条件线搜索（简化实现）"""
        gradient = self._compute_gradient(x, eval_func)
        dot_product = np.dot(gradient, direction)

        # 必须是下降方向
        if dot_product >= 0:
            return 1e-10

        for _ in range(self.max_iter):
            x_new = x + step_size * direction
            f_new = eval_func(x_new)

            # Armijo条件（充分下降）
            armijo_ok = f_new <= f_current + self.wolfe_c1 * step_size * dot_product

            if armijo_ok:
                # 检查曲率条件（简化版）
                new_gradient = self._compute_gradient(x_new, eval_func)
                curvature_ok = np.dot(new_gradient, direction) >= self.wolfe_c2 * dot_product

                if curvature_ok or step_size < 1e-6:
                    return step_size

            # 调整步长
            if f_new > f_current:
                step_size *= 0.5
            else:
                step_size *= 1.2

            if step_size > 2.0:
                step_size = 2.0

        return max(step_size, 1e-10)

    def _compute_gradient(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> np.ndarray:
        """计算梯度"""
        gradient = np.zeros_like(x)
        eps = 1e-6

        for i in range(len(x)):
            x_plus = x.copy()
            x_plus[i] += eps
            f_plus = eval_func(x_plus)
            f_current = eval_func(x)
            gradient[i] = (f_plus - f_current) / eps

        return gradient


class TrustRegionBias(AlgorithmicBias):
    """信赖域偏置 - 自适应调整搜索区域"""
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def __init__(self, weight: float = 0.25, initial_radius: float = 1.0,
                 eta1: float = 0.25, eta2: float = 0.75, gamma1: float = 0.5,
                 gamma2: float = 2.0, max_radius: float = 10.0, min_radius: float = 1e-6):
        super().__init__("trust_region", weight)
        self.radius = initial_radius
        self.eta1 = eta1  # 收缩阈值
        self.eta2 = eta2  # 扩展阈值
        self.gamma1 = gamma1  # 收缩因子
        self.gamma2 = gamma2  # 扩展因子
        self.max_radius = max_radius
        self.min_radius = min_radius
        self.last_successful = True

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float],
              context: OptimizationContext) -> float:
        """应用信赖域偏置"""
        # 建立局部二次模型
        gradient = self._compute_gradient(x, eval_func)
        hessian = self._compute_hessian(x, eval_func)

        # 解信赖域子问题（狗腿法）
        step = self._dogleg_step(gradient, hessian, self.radius)

        # 评估实际改进和预测改进
        f_current = eval_func(x)
        x_trial = x + step
        f_trial = eval_func(x_trial)

        actual_reduction = f_current - f_trial
        predicted_reduction = -np.dot(gradient, step) - 0.5 * np.dot(step, hessian @ step)

        # 计算比率
        if predicted_reduction > 0:
            ratio = actual_reduction / predicted_reduction
        else:
            ratio = 0

        # 更新信赖域半径
        if ratio < self.eta1:
            self.radius = max(self.gamma1 * self.radius, self.min_radius)
            self.last_successful = False
        elif ratio > self.eta2:
            self.radius = min(self.gamma2 * self.radius, self.max_radius)
            self.last_successful = True
        else:
            self.last_successful = True

        # 返回实际改进作为偏置
        return self.weight * actual_reduction

    def _compute_gradient(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> np.ndarray:
        """计算梯度"""
        gradient = np.zeros_like(x)
        eps = 1e-6

        for i in range(len(x)):
            x_plus = x.copy()
            x_plus[i] += eps
            f_plus = eval_func(x_plus)
            f_current = eval_func(x)
            gradient[i] = (f_plus - f_current) / eps

        return gradient

    def _compute_hessian(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> np.ndarray:
        """计算近似的Hessian矩阵（对角近似）"""
        n = len(x)
        hessian = np.zeros((n, n))
        eps = 1e-5

        for i in range(n):
            x_plus = x.copy()
            x_minus = x.copy()
            x_plus[i] += eps
            x_minus[i] -= eps

            f_plus = eval_func(x_plus)
            f_minus = eval_func(x_minus)
            f_current = eval_func(x)

            hessian[i, i] = (f_plus - 2 * f_current + f_minus) / (eps ** 2)

        return hessian

    def _dogleg_step(self, gradient: np.ndarray, hessian: np.ndarray,
                    radius: float) -> np.ndarray:
        """狗腿法求解信赖域子问题"""
        try:
            # Cauchy点（最速下降方向）
            gTg = np.dot(gradient, gradient)
            gTBg = np.dot(gradient, hessian @ gradient)

            if gTBg <= 0:
                cauchy_step = -radius * gradient / np.linalg.norm(gradient)
            else:
                cauchy_step = -(gTg / gTBg) * gradient

                if np.linalg.norm(cauchy_step) > radius:
                    cauchy_step = -radius * gradient / np.linalg.norm(gradient)

            # Newton步
            try:
                newton_step = np.linalg.solve(hessian, -gradient)
            except:
                return cauchy_step

            # 如果Newton步在信赖域内，使用Newton步
            if np.linalg.norm(newton_step) <= radius:
                return newton_step

            # 否则使用Cauchy点和Newton步的组合
            if np.linalg.norm(cauchy_step) >= radius:
                return cauchy_step

            # 求解组合点
            diff = newton_step - cauchy_step
            a = np.dot(diff, diff)
            b = 2 * np.dot(cauchy_step, diff)
            c = np.dot(cauchy_step, cauchy_step) - radius ** 2

            if a > 0:
                tau = (-b + np.sqrt(b ** 2 - 4 * a * c)) / (2 * a)
                tau = np.clip(tau, 0, 1)
            else:
                tau = 1

            return cauchy_step + tau * diff

        except:
            # 降级到最速下降
            return -radius * gradient / (np.linalg.norm(gradient) + 1e-10)


class NelderMeadBias(AlgorithmicBias):
    """Nelder-Mead单纯形法偏置"""
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def __init__(self, weight: float = 0.2, simplex_size: float = 0.1,
                 reflection: float = 1.0, expansion: float = 2.0,
                 contraction: float = 0.5, shrinkage: float = 0.5):
        super().__init__("nelder_mead", weight)
        self.simplex_size = simplex_size
        self.reflection = reflection
        self.expansion = expansion
        self.contraction = contraction
        self.shrinkage = shrinkage
        self.simplex = None
        self.simplex_values = None

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float],
              context: OptimizationContext) -> float:
        """应用Nelder-Mead偏置"""
        # 初始化单纯形
        if self.simplex is None:
            self._initialize_simplex(x, eval_func)

        # 执行一步Nelder-Mead迭代
        improvement = self._nelder_mead_step(eval_func)

        # 返回改进作为偏置
        return self.weight * improvement

    def _initialize_simplex(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]):
        """初始化单纯形"""
        n = len(x)
        self.simplex = [x.copy()]

        # 创建n个其他顶点
        for i in range(n):
            vertex = x.copy()
            vertex[i] += self.simplex_size
            self.simplex.append(vertex)

        # 计算所有顶点的函数值
        self.simplex_values = [eval_func(v) for v in self.simplex]

    def _nelder_mead_step(self, eval_func: Callable[[np.ndarray], float]) -> float:
        """执行一步Nelder-Mead迭代"""
        if self.simplex is None or len(self.simplex) < 2:
            return 0

        n = len(self.simplex) - 1

        # 排序：从好到坏
        indices = np.argsort(self.simplex_values)
        sorted_simplex = [self.simplex[i] for i in indices]
        sorted_values = [self.simplex_values[i] for i in indices]

        # 计算重心（排除最差点）
        centroid = np.mean(sorted_simplex[:-1], axis=0)
        worst_point = sorted_simplex[-1]
        worst_value = sorted_values[-1]

        # 反射
        reflected = centroid + self.reflection * (centroid - worst_point)
        reflected_value = eval_func(reflected)

        improvement = 0

        if reflected_value < sorted_values[-2]:
            if reflected_value < sorted_values[0]:
                # 扩展
                expanded = centroid + self.expansion * (reflected - centroid)
                expanded_value = eval_func(expanded)

                if expanded_value < reflected_value:
                    self.simplex[-1] = expanded
                    self.simplex_values[-1] = expanded_value
                    improvement = worst_value - expanded_value
                else:
                    self.simplex[-1] = reflected
                    self.simplex_values[-1] = reflected_value
                    improvement = worst_value - reflected_value
            else:
                self.simplex[-1] = reflected
                self.simplex_values[-1] = reflected_value
                improvement = worst_value - reflected_value
        else:
            # 收缩
            contracted = centroid + self.contraction * (worst_point - centroid)
            contracted_value = eval_func(contracted)

            if contracted_value < worst_value:
                self.simplex[-1] = contracted
                self.simplex_values[-1] = contracted_value
                improvement = worst_value - contracted_value
            else:
                # 收缩整个单纯形
                best_point = sorted_simplex[0]
                for i in range(1, n + 1):
                    self.simplex[i] = best_point + self.shrinkage * (self.simplex[i] - best_point)
                    self.simplex_values[i] = eval_func(self.simplex[i])

        return improvement


class QuasiNewtonBias(AlgorithmicBias):
    """拟牛顿法偏置 - BFGS和DFP"""
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def __init__(self, weight: float = 0.25, method: str = 'bfgs',
                 initial_scale: float = 1.0):
        super().__init__("quasi_newton", weight)
        self.method = method.lower()  # 'bfgs' or 'dfp'
        self.initial_scale = initial_scale
        self.approx_inverse_hessian = None
        self.last_x = None
        self.last_gradient = None

    def apply(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float],
              context: OptimizationContext) -> float:
        """应用拟牛顿法偏置"""
        # 计算当前梯度
        gradient = self._compute_gradient(x, eval_func)

        # 初始化逆Hessian近似
        if self.approx_inverse_hessian is None:
            self.approx_inverse_hessian = self.initial_scale * np.eye(len(x))

        # 计算搜索方向
        search_direction = -self.approx_inverse_hessian @ gradient

        # 更新上下文中的搜索方向
        if hasattr(context, 'search_direction'):
            context.search_direction = search_direction

        # 评估改进潜力
        if self.last_x is not None and self.last_gradient is not None:
            # 更新拟牛顿近似
            self._update_quasi_newton(x, gradient)

        # 记录当前点
        self.last_x = x.copy()
        self.last_gradient = gradient.copy()

        # 返回改进潜力
        return self.weight * np.linalg.norm(search_direction)

    def _update_quasi_newton(self, x_new: np.ndarray, grad_new: np.ndarray):
        """更新拟牛顿近似"""
        s = x_new - self.last_x
        y = grad_new - self.last_gradient

        sy = np.dot(s, y)
        if sy > 1e-10:  # 避免除零和数值问题
            Hs = self.approx_inverse_hessian @ s

            if self.method == 'bfgs':
                # BFGS更新
                self.approx_inverse_hessian += (
                    np.outer(s, s) / sy - np.outer(Hs, Hs) / np.dot(s, Hs)
                )
            else:  # dfp
                # DFP更新
                Hy = self.approx_inverse_hessian @ y
                self.approx_inverse_hessian += (
                    np.outer(Hs, Hs) / np.dot(Hs, y) - np.outer(Hy, Hy) / np.dot(y, Hy)
                )

    def _compute_gradient(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> np.ndarray:
        """计算梯度"""
        gradient = np.zeros_like(x)
        eps = 1e-6

        for i in range(len(x)):
            x_plus = x.copy()
            x_plus[i] += eps
            f_plus = eval_func(x_plus)
            f_current = eval_func(x)
            gradient[i] = (f_plus - f_current) / eps

        return gradient


# ==================== 便捷函数 ====================

def create_gradient_descent_suite(**kwargs) -> List[AlgorithmicBias]:
    """创建梯度下降套件"""
    return [
        GradientDescentBias(weight=0.2, **kwargs),
        LineSearchBias(weight=0.1, method='armijo')
    ]


def create_newton_suite(**kwargs) -> List[AlgorithmicBias]:
    """创建牛顿法套件"""
    return [
        NewtonMethodBias(weight=0.3, use_bfgs_approx=True, **kwargs),
        TrustRegionBias(weight=0.2, **kwargs)
    ]


def create_hybrid_local_suite(**kwargs) -> List[AlgorithmicBias]:
    """创建混合局部优化套件"""
    return [
        GradientDescentBias(weight=0.15, **kwargs),
        QuasiNewtonBias(weight=0.2, method='bfgs', **kwargs),
        LineSearchBias(weight=0.1, use_wolfe=True, **kwargs)
    ]


def create_derivative_free_suite(**kwargs) -> List[AlgorithmicBias]:
    """创建无导数优化套件"""
    return [
        NelderMeadBias(weight=0.25, **kwargs),
        TrustRegionBias(weight=0.15, **kwargs)
    ]


# ==================== 导出接口 ====================

__all__ = [
    # 局部优化偏置
    'GradientDescentBias',
    'NewtonMethodBias',
    'LineSearchBias',
    'TrustRegionBias',
    'NelderMeadBias',
    'QuasiNewtonBias',

    # 便捷函数
    'create_gradient_descent_suite',
    'create_newton_suite',
    'create_hybrid_local_suite',
    'create_derivative_free_suite',
]
