"""
贝叶斯优化器 - Bayesian Optimizer

基于高斯过程的全局优化方法，特别适合昂贵黑箱函数优化。

主要特性：
- 多种获取函数 (EI, UCB, PI)
- 多种核函数 (RBF, Matern)
- 支持并行评估
- 理论保证的收敛性
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from scipy.stats import norm
from typing import Callable, List, Tuple, Optional, Dict, Any
import warnings
warnings.filterwarnings('ignore')

try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import (
        RBF, Matern, ConstantKernel, WhiteKernel, DotProduct
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: sklearn not available. Using fallback implementation.")


class AcquisitionFunction:
    """获取函数基类"""

    def __init__(self, xi=0.01, kappa=2.576):
        self.xi = xi  # EI/PI参数
        self.kappa = kappa  # UCB参数

    def evaluate(self, x, gp, y_best):
        """评估获取函数值"""
        raise NotImplementedError


class ExpectedImprovement(AcquisitionFunction):
    """期望改进 (Expected Improvement)"""

    def evaluate(self, x, gp, y_best):
        # 确保 x 是 2D 数组
        if x.ndim == 1:
            x = x.reshape(1, -1)

        mu, sigma = gp.predict(x, return_std=True)
        mu = mu[0]  # 提取标量值
        sigma = sigma[0]  # 提取标量值

        with np.errstate(divide='warn'):
            imp = mu - y_best - self.xi
            Z = imp / sigma
            ei = imp * norm.cdf(Z) + sigma * norm.pdf(Z)

        return ei


class UpperConfidenceBound(AcquisitionFunction):
    """上置信界 (Upper Confidence Bound)"""

    def evaluate(self, x, gp, y_best):
        if x.ndim == 1:
            x = x.reshape(1, -1)
        mu, sigma = gp.predict(x, return_std=True)
        return mu[0] + self.kappa * sigma[0]


class ProbabilityOfImprovement(AcquisitionFunction):
    """改进概率 (Probability of Improvement)"""

    def evaluate(self, x, gp, y_best):
        if x.ndim == 1:
            x = x.reshape(1, -1)
        mu, sigma = gp.predict(x, return_std=True)
        Z = (mu[0] - y_best - self.xi) / sigma[0]
        return norm.cdf(Z)


class KnowledgeGradient(AcquisitionFunction):
    """知识梯度 (Knowledge Gradient)"""

    def evaluate(self, x, gp, y_best):
        # 简化的KG实现
        if x.ndim == 1:
            x = x.reshape(1, -1)
        mu, sigma = gp.predict(x, return_std=True)
        expected_future_best = mu[0] + 0.5 * sigma[0]
        return expected_future_best - y_best


class BayesianOptimizer:
    """
    贝叶斯优化器

    通过高斯过程模型和获取函数，高效地搜索昂贵函数的全局最优。
    """

    def __init__(self,
                 acquisition: str = 'ei',
                 kernel: str = 'rbf',
                 alpha: float = 1e-6,
                 n_restarts: int = 10,
                 normalize_y: bool = True,
                 random_state: Optional[int] = None):
        """
        初始化贝叶斯优化器

        Parameters:
        -----------
        acquisition : str
            获取函数类型 ('ei', 'ucb', 'pi', 'kg')
        kernel : str
            核函数类型 ('rbf', 'matern', 'matern52', 'rq')
        alpha : float
            高斯过程噪声参数
        n_restarts : int
            优化重启次数
        normalize_y : bool
            是否标准化目标值
        random_state : int
            随机种子
        """

        self.acquisition_name = acquisition.lower()
        self.kernel_name = kernel.lower()
        self.alpha = alpha
        self.n_restarts = n_restarts
        self.normalize_y = normalize_y
        self.random_state = random_state

        # 初始化组件
        self._setup_kernel()
        self._setup_acquisition()
        self._setup_gp_model()

        # 数据存储
        self.X_observed = []
        self.y_observed = []
        self.y_best = float('inf')
        self.x_best = None

        # 历史记录
        self.history = {
            'x': [],
            'y': [],
            'acquisition_values': []
        }

    def _setup_kernel(self):
        """设置核函数"""
        if SKLEARN_AVAILABLE:
            length_scale = 1.0

            if self.kernel_name == 'rbf':
                self.kernel = ConstantKernel(1.0) * RBF(length_scale=length_scale)
            elif self.kernel_name == 'matern':
                self.kernel = ConstantKernel(1.0) * Matern(length_scale=length_scale, nu=1.5)
            elif self.kernel_name == 'matern52':
                self.kernel = ConstantKernel(1.0) * Matern(length_scale=length_scale, nu=2.5)
            elif self.kernel_name == 'rq':
                # Rational Quadratic (需要自定义)
                from sklearn.gaussian_process.kernels import RationalQuadratic
                self.kernel = ConstantKernel(1.0) * RationalQuadratic(length_scale=length_scale, alpha=1.0)
            else:
                self.kernel = RBF(length_scale=length_scale)
        else:
            # 简单的后备实现
            self.kernel = None

    def _setup_acquisition(self):
        """设置获取函数"""
        if self.acquisition_name == 'ei':
            self.acquisition = ExpectedImprovement()
        elif self.acquisition_name == 'ucb':
            self.acquisition = UpperConfidenceBound()
        elif self.acquisition_name == 'pi':
            self.acquisition = ProbabilityOfImprovement()
        elif self.acquisition_name == 'kg':
            self.acquisition = KnowledgeGradient()
        else:
            self.acquisition = ExpectedImprovement()

    def _setup_gp_model(self):
        """设置高斯过程模型"""
        if SKLEARN_AVAILABLE:
            self.gp = GaussianProcessRegressor(
                kernel=self.kernel,
                alpha=self.alpha,
                normalize_y=self.normalize_y,
                n_restarts_optimizer=self.n_restarts,
                random_state=self.random_state
            )
        else:
            # 简单的后备实现
            self.gp = None

    def suggest_next(self, bounds: List[Tuple[float, float]],
                     n_candidates: int = 1000) -> np.ndarray:
        """
        建议下一个评估点

        Parameters:
        -----------
        bounds : List[Tuple[float, float]]
            每个变量的边界
        n_candidates : int
            随机候选点数量

        Returns:
        --------
        np.ndarray : 建议的下一个点
        """

        # 如果没有观察数据，返回随机点
        if len(self.X_observed) == 0:
            x_random = np.array([np.random.uniform(b[0], b[1]) for b in bounds])
            return x_random

        # 拟合高斯过程
        self._fit_gp()

        # 生成候选点
        candidates = self._generate_candidates(bounds, n_candidates)

        # 评估获取函数
        acquisition_values = []
        for candidate in candidates:
            val = self._evaluate_acquisition(candidate)
            acquisition_values.append(val)

        acquisition_values = np.array(acquisition_values)

        # 选择最佳候选点
        best_idx = np.argmax(acquisition_values)
        best_candidate = candidates[best_idx]

        # 局部优化
        if SKLEARN_AVAILABLE:
            best_candidate = self._local_optimize_acquisition(
                best_candidate, bounds
            )

        # 记录获取函数值
        self.history['acquisition_values'].append(acquisition_values[best_idx])

        return best_candidate

    def observe(self, x: np.ndarray, y: float):
        """
        观察新的数据点

        Parameters:
        -----------
        x : np.ndarray
            输入点
        y : float
            目标函数值
        """
        self.X_observed.append(x.copy())
        self.y_observed.append(y)

        # 更新最优解
        if y < self.y_best:
            self.y_best = y
            self.x_best = x.copy()

        # 记录历史
        self.history['x'].append(x.copy())
        self.history['y'].append(y)

    def optimize(self,
                 objective_func: Callable,
                 bounds: List[Tuple[float, float]],
                 budget: int = 100,
                 callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        执行完整的贝叶斯优化

        Parameters:
        -----------
        objective_func : Callable
            目标函数
        bounds : List[Tuple[float, float]]
            变量边界
        budget : int
            评估预算
        callback : Callable
            回调函数

        Returns:
        --------
        Dict : 优化结果
        """

        # 重置状态
        self.reset()

        # 优化循环
        for iteration in range(budget):
            # 建议下一个点
            x_next = self.suggest_next(bounds)

            # 评估目标函数
            y_next = objective_func(x_next)

            # 观察新数据
            self.observe(x_next, y_next)

            # 调用回调
            if callback is not None:
                callback(iteration, x_next, y_next, self.y_best)

        # 返回结果
        result = {
            'best_x': self.x_best,
            'best_y': self.y_best,
            'history': self.history,
            'n_evaluations': len(self.X_observed),
            'convergence': self._analyze_convergence()
        }

        return result

    def batch_suggest(self,
                      bounds: List[Tuple[float, float]],
                      batch_size: int = 5) -> List[np.ndarray]:
        """
        批量建议多个评估点（用于并行评估）

        Parameters:
        -----------
        bounds : List[Tuple[float, float]]
            变量边界
        batch_size : int
            批量大小

        Returns:
        --------
        List[np.ndarray] : 建议的批量点
        """
        batch_points = []

        for i in range(batch_size):
            # 暂时添加虚拟点以避免重复选择
            if len(self.X_observed) > 0:
                temp_X = self.X_observed + [np.random.uniform(
                    [b[0] for b in bounds],
                    [b[1] for b in bounds]
                )]
                temp_y = self.y_observed + [self.y_best]
                self._fit_gp_with_data(temp_X, temp_y)
            else:
                self._fit_gp()

            x_next = self.suggest_next(bounds)
            batch_points.append(x_next)

        return batch_points

    def _fit_gp(self):
        """拟合高斯过程模型"""
        if len(self.X_observed) > 0 and SKLEARN_AVAILABLE:
            X = np.array(self.X_observed)
            y = np.array(self.y_observed)
            self.gp.fit(X, y)

    def _fit_gp_with_data(self, X, y):
        """用指定数据拟合高斯过程"""
        if SKLEARN_AVAILABLE:
            self.gp.fit(np.array(X), np.array(y))

    def _generate_candidates(self, bounds, n_candidates):
        """生成候选点"""
        candidates = []
        for _ in range(n_candidates):
            x = np.array([np.random.uniform(b[0], b[1]) for b in bounds])
            candidates.append(x)
        return np.array(candidates)

    def _evaluate_acquisition(self, x):
        """评估获取函数"""
        if SKLEARN_AVAILABLE and len(self.X_observed) > 1:
            # 不需要在这里reshape，因为acquisition.evaluate会处理
            return self.acquisition.evaluate(x, self.gp, self.y_best)
        else:
            # 后备实现
            return 0.0

    def _local_optimize_acquisition(self, x_init, bounds):
        """局部优化获取函数"""
        def objective(x):
            return -self._evaluate_acquisition(x)

        result = minimize(
            objective,
            x_init,
            bounds=bounds,
            method='L-BFGS-B',
            options={'maxiter': 100}
        )

        return result.x

    def _analyze_convergence(self):
        """分析收敛情况"""
        if len(self.y_observed) < 10:
            return {}

        # 计算最近10次的改进
        recent_improvements = []
        y_array = np.array(self.y_observed)

        for i in range(len(y_array) - 1):
            improvement = y_array[i] - y_array[i + 1]
            recent_improvements.append(improvement)

        return {
            'best_improvement': max(recent_improvements),
            'average_improvement': np.mean(recent_improvements[-10:]),
            'stagnation_generations': len([x for x in recent_improvements[-20:] if x < 1e-6])
        }

    def reset(self):
        """重置优化器状态"""
        self.X_observed = []
        self.y_observed = []
        self.y_best = float('inf')
        self.x_best = None
        self.history = {
            'x': [],
            'y': [],
            'acquisition_values': []
        }

    def plot_optimization(self, save_path: Optional[str] = None):
        """绘制优化过程（仅适用于1D或2D问题）"""
        if len(self.y_observed) == 0:
            print("没有数据可绘制")
            return

        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        # 1. 收敛曲线
        axes[0, 0].plot(self.y_observed, 'b-', linewidth=2)
        axes[0, 0].set_xlabel('Iteration')
        axes[0, 0].set_ylabel('Objective Value')
        axes[0, 0].set_title('Convergence Curve')
        axes[0, 0].grid(True)

        # 2. 当前最优
        best_so_far = np.minimum.accumulate(self.y_observed)
        axes[0, 1].plot(best_so_far, 'r-', linewidth=2)
        axes[0, 1].set_xlabel('Iteration')
        axes[0, 1].set_ylabel('Best Objective')
        axes[0, 1].set_title('Best-so-far Curve')
        axes[0, 1].grid(True)

        # 3. 获取函数值
        if self.history['acquisition_values']:
            axes[1, 0].plot(self.history['acquisition_values'], 'g-', linewidth=2)
            axes[1, 0].set_xlabel('Iteration')
            axes[1, 0].set_ylabel('Acquisition Value')
            axes[1, 0].set_title('Acquisition Function Values')
            axes[1, 0].grid(True)

        # 4. 参数空间（仅适用于2D）
        if self.X_observed and len(self.X_observed[0]) == 2:
            X_array = np.array(self.X_observed)
            scatter = axes[1, 1].scatter(
                X_array[:, 0], X_array[:, 1],
                c=self.y_observed, cmap='viridis', s=50
            )
            axes[1, 1].set_xlabel('X[0]')
            axes[1, 1].set_ylabel('X[1]')
            axes[1, 1].set_title('Parameter Space')
            plt.colorbar(scatter, ax=axes[1, 1])
        else:
            axes[1, 1].text(0.5, 0.5, 'Parameter space plot\nonly available for 2D',
                          ha='center', va='center', transform=axes[1, 1].transAxes)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()


# 便捷函数
def bayesian_optimize(objective_func: Callable,
                      bounds: List[Tuple[float, float]],
                      budget: int = 100,
                      acquisition: str = 'ei',
                      kernel: str = 'rbf') -> Dict[str, Any]:
    """
    便捷的贝叶斯优化函数

    Parameters:
    -----------
    objective_func : Callable
        目标函数
    bounds : List[Tuple[float, float]]
        变量边界
    budget : int
        评估预算
    acquisition : str
        获取函数
    kernel : str
        核函数

    Returns:
    --------
    Dict : 优化结果
    """
    optimizer = BayesianOptimizer(
        acquisition=acquisition,
        kernel=kernel
    )

    return optimizer.optimize(objective_func, bounds, budget)