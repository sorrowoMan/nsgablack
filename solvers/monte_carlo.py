"""蒙特卡洛优化模块

核心思想：
- 可组合的MC框架，支持嵌套调用任意优化器
- 处理随机变量、不确定性量化、鲁棒优化
- 与代理模型、遗传算法无缝集成

典型用法：
1. MC + GA嵌套：对每个MC样本调用GA求解
2. MC + Surrogate + GA：先用少量MC样本训练代理，再用MC+代理+GA求解
3. 鲁棒优化：最小化目标函数的期望+方差加权和
"""
import numpy as np
from typing import Callable, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
try:
    # 当作为包导入时使用相对导入
    from ..core.base import BlackBoxProblem
except ImportError:
    # 当作为脚本运行时使用绝对导入
    try:
        from nsgablack.core.base import BlackBoxProblem
    except ImportError:
        # 如果nsgablack不在sys.path，尝试直接从core导入
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        core_dir = os.path.join(parent_dir, 'core')
        if core_dir not in sys.path:
            sys.path.insert(0, core_dir)
        from base import BlackBoxProblem


@dataclass
class DistributionSpec:
    """随机变量分布规范"""
    type: str  # 'normal', 'uniform', 'lognormal', 'triangular'
    params: Dict  # 分布参数，如 {'mean': 0, 'std': 1}

    def sample(self, size=1, seed=None):
        """从分布中采样"""
        rng = np.random.default_rng(seed)
        if self.type == 'normal':
            return rng.normal(self.params['mean'], self.params['std'], size)
        elif self.type == 'uniform':
            return rng.uniform(self.params['low'], self.params['high'], size)
        elif self.type == 'lognormal':
            return rng.lognormal(self.params['mean'], self.params['sigma'], size)
        elif self.type == 'triangular':
            return rng.triangular(self.params['left'], self.params['mode'], self.params['right'], size)
        else:
            raise ValueError(f"Unknown distribution type: {self.type}")


class StochasticProblem(BlackBoxProblem):
    """随机黑箱问题：目标函数或约束包含随机变量

    用户需要实现：
    - evaluate_stochastic(x, random_params): 接受决策变量x和随机参数
    - get_random_distributions(): 返回随机参数的分布字典
    """

    def __init__(self, name="随机黑箱问题", dimension=2, bounds=None):
        super().__init__(name, dimension, bounds)

    def evaluate_stochastic(self, x, random_params: Dict) -> Union[float, np.ndarray]:
        """评估随机目标函数（子类必须实现）

        参数：
            x: 决策变量
            random_params: 随机参数字典，如 {'noise': 0.1, 'demand': 100}
        """
        raise NotImplementedError

    def get_random_distributions(self) -> Dict[str, DistributionSpec]:
        """返回随机参数的分布（子类必须实现）

        返回：
            字典，键为参数名，值为DistributionSpec
        """
        raise NotImplementedError

    def evaluate(self, x):
        """默认评估：单次采样（用于兼容确定性优化器）"""
        dists = self.get_random_distributions()
        random_params = {k: v.sample(1)[0] for k, v in dists.items()}
        return self.evaluate_stochastic(x, random_params)


class MonteCarloEvaluator:
    """蒙特卡洛评估器：量化不确定性、评估期望/方差/分位数"""

    def __init__(self, n_samples: int = 100, seed: Optional[int] = None):
        self.n_samples = n_samples
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def evaluate_expectation(self, problem: StochasticProblem, x: np.ndarray) -> Union[float, np.ndarray]:
        """评估目标函数的期望值"""
        dists = problem.get_random_distributions()
        samples = []
        for _ in range(self.n_samples):
            random_params = {k: v.sample(1, seed=self.rng.integers(0, 1e9))[0] for k, v in dists.items()}
            result = problem.evaluate_stochastic(x, random_params)
            samples.append(result)
        return np.mean(samples, axis=0)

    def evaluate_statistics(self, problem: StochasticProblem, x: np.ndarray) -> Dict:
        """评估完整统计量：期望、标准差、分位数"""
        dists = problem.get_random_distributions()
        samples = []
        for _ in range(self.n_samples):
            random_params = {k: v.sample(1, seed=self.rng.integers(0, 1e9))[0] for k, v in dists.items()}
            result = problem.evaluate_stochastic(x, random_params)
            samples.append(result)
        samples = np.array(samples)
        return {
            'mean': np.mean(samples, axis=0),
            'std': np.std(samples, axis=0),
            'min': np.min(samples, axis=0),
            'max': np.max(samples, axis=0),
            'q25': np.percentile(samples, 25, axis=0),
            'q50': np.percentile(samples, 50, axis=0),
            'q75': np.percentile(samples, 75, axis=0),
            'samples': samples
        }

    def evaluate_cvar(self, problem: StochasticProblem, x: np.ndarray, alpha: float = 0.95) -> float:
        """评估条件风险价值 (CVaR)：最坏alpha分位数的期望"""
        stats = self.evaluate_statistics(problem, x)
        samples = stats['samples'].flatten()
        var = np.percentile(samples, alpha * 100)
        cvar = np.mean(samples[samples >= var])
        return float(cvar)


class MonteCarloOptimizer:
    """蒙特卡洛优化器：可嵌套调用任意优化器的MC框架

    支持三种模式：
    1. 期望优化：min E[f(x, ξ)]
    2. 鲁棒优化：min E[f] + λ*Std[f]
    3. CVaR优化：min CVaR_α[f]
    """

    def __init__(self,
                 stochastic_problem: StochasticProblem,
                 inner_optimizer_factory: Callable,
                 mc_samples: int = 100,
                 mode: str = 'expectation',
                 robust_lambda: float = 0.5,
                 cvar_alpha: float = 0.95,
                 seed: Optional[int] = None):
        """
        参数：
            stochastic_problem: 随机问题实例
            inner_optimizer_factory: 内层优化器工厂函数，接受problem返回solver
                例如：lambda prob: BlackBoxSolverNSGAII(prob)
            mc_samples: MC采样数
            mode: 'expectation' | 'robust' | 'cvar'
            robust_lambda: 鲁棒优化的方差权重
            cvar_alpha: CVaR的置信水平
        """
        self.stochastic_problem = stochastic_problem
        self.inner_optimizer_factory = inner_optimizer_factory
        self.mc_samples = mc_samples
        self.mode = mode
        self.robust_lambda = robust_lambda
        self.cvar_alpha = cvar_alpha
        self.evaluator = MonteCarloEvaluator(mc_samples, seed)
        self.evaluation_count = 0
        self.best_x = None
        self.best_f = None

    def _create_deterministic_problem(self) -> BlackBoxProblem:
        """创建确定性代理问题：将随机问题转换为确定性优化"""
        stoch_prob = self.stochastic_problem
        evaluator = self.evaluator
        mode = self.mode
        robust_lambda = self.robust_lambda
        cvar_alpha = self.cvar_alpha

        class DeterministicProxy(BlackBoxProblem):
            def __init__(self):
                super().__init__(
                    name=f"MC_{mode}_{stoch_prob.name}",
                    dimension=stoch_prob.dimension,
                    bounds=stoch_prob.bounds
                )

            def evaluate(self, x):
                if mode == 'expectation':
                    return evaluator.evaluate_expectation(stoch_prob, x)
                elif mode == 'robust':
                    stats = evaluator.evaluate_statistics(stoch_prob, x)
                    return stats['mean'] + robust_lambda * stats['std']
                elif mode == 'cvar':
                    return evaluator.evaluate_cvar(stoch_prob, x, cvar_alpha)
                else:
                    raise ValueError(f"Unknown mode: {mode}")

            def get_num_objectives(self):
                return stoch_prob.get_num_objectives()

        return DeterministicProxy()

    def optimize(self, **solver_kwargs) -> Dict:
        """运行MC优化

        返回：
            包含 best_x, best_f, solver, statistics 的字典
        """
        # 创建确定性代理问题
        det_problem = self._create_deterministic_problem()

        # 创建内层优化器
        solver = self.inner_optimizer_factory(det_problem)

        # 应用用户传入的求解器参数
        for key, value in solver_kwargs.items():
            if hasattr(solver, key):
                setattr(solver, key, value)

        # 运行优化
        result = solver.run()

        # 提取最优解
        if hasattr(solver, 'pareto_solutions') and solver.pareto_solutions is not None:
            pareto = solver.pareto_solutions
            if len(pareto['individuals']) > 0:
                # 多目标：取第一个Pareto解
                self.best_x = pareto['individuals'][0]
                self.best_f = pareto['objectives'][0]
            else:
                self.best_x = None
                self.best_f = None
        else:
            # 单目标
            if solver.objectives is not None and len(solver.objectives) > 0:
                best_idx = np.argmin(solver.objectives[:, 0])
                self.best_x = solver.population[best_idx]
                self.best_f = solver.objectives[best_idx, 0]

        # 评估最优解的完整统计量
        final_stats = None
        if self.best_x is not None:
            final_stats = self.evaluator.evaluate_statistics(self.stochastic_problem, self.best_x)

        return {
            'best_x': self.best_x,
            'best_f': self.best_f,
            'solver': solver,
            'result': result,
            'statistics': final_stats,
            'mode': self.mode
        }


class SurrogateMonteCarloOptimizer:
    """代理模型 + 蒙特卡洛 + 遗传算法的三层架构

    流程：
    1. 用少量MC样本训练代理模型
    2. 用代理模型快速评估MC期望
    3. 选择高价值点进行真实MC评估
    4. 迭代更新代理模型
    """

    def __init__(self,
                 stochastic_problem: StochasticProblem,
                 inner_optimizer_factory: Callable,
                 mc_samples: int = 50,
                 surrogate_type: str = 'gp',
                 initial_samples: int = 20,
                 max_iterations: int = 10,
                 samples_per_iter: int = 5,
                 mode: str = 'expectation',
                 seed: Optional[int] = None):
        """
        参数：
            stochastic_problem: 随机问题
            inner_optimizer_factory: 优化器工厂
            mc_samples: 每次MC评估的样本数
            surrogate_type: 代理模型类型 ('gp', 'rf', 'rbf')
            initial_samples: 初始训练样本数
            max_iterations: 最大迭代次数
            samples_per_iter: 每次迭代新增样本数
            mode: MC模式
        """
        self.stochastic_problem = stochastic_problem
        self.inner_optimizer_factory = inner_optimizer_factory
        self.mc_samples = mc_samples
        self.surrogate_type = surrogate_type
        self.initial_samples = initial_samples
        self.max_iterations = max_iterations
        self.samples_per_iter = samples_per_iter
        self.mode = mode
        self.evaluator = MonteCarloEvaluator(mc_samples, seed)

        # 训练数据
        self.X_train = []
        self.y_train = []
        self.surrogate = None
        self.best_x = None
        self.best_f = None

    def _init_surrogate(self):
        """初始化代理模型"""
        if self.surrogate_type == 'gp':
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import RBF, ConstantKernel
            kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)
            return GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=3, alpha=1e-6, normalize_y=True)
        elif self.surrogate_type == 'rf':
            from sklearn.ensemble import RandomForestRegressor
            return RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
        elif self.surrogate_type == 'rbf':
            from sklearn.kernel_approximation import RBFSampler
            from sklearn.linear_model import Ridge
            from sklearn.pipeline import Pipeline
            return Pipeline([('rbf', RBFSampler(gamma=1.0, n_components=50)), ('ridge', Ridge(alpha=1.0))])
        else:
            raise ValueError(f"Unknown surrogate type: {self.surrogate_type}")

    def _evaluate_mc(self, x: np.ndarray) -> float:
        """真实MC评估"""
        if self.mode == 'expectation':
            return float(self.evaluator.evaluate_expectation(self.stochastic_problem, x))
        elif self.mode == 'robust':
            stats = self.evaluator.evaluate_statistics(self.stochastic_problem, x)
            return float(stats['mean'] + 0.5 * stats['std'])
        elif self.mode == 'cvar':
            return self.evaluator.evaluate_cvar(self.stochastic_problem, x, 0.95)

    def _initial_sampling(self):
        """初始LHS采样"""
        from scipy.stats import qmc
        bounds = self.stochastic_problem.bounds
        lows = np.array([bounds[v][0] for v in self.stochastic_problem.variables])
        highs = np.array([bounds[v][1] for v in self.stochastic_problem.variables])

        sampler = qmc.LatinHypercube(d=self.stochastic_problem.dimension, seed=42)
        samples = sampler.random(n=self.initial_samples)
        X = qmc.scale(samples, lows, highs)

        y = np.array([self._evaluate_mc(x) for x in X])
        self.X_train = X.tolist()
        self.y_train = y.tolist()

    def _train_surrogate(self):
        """训练代理模型"""
        if len(self.X_train) < 3:
            return
        X = np.array(self.X_train)
        y = np.array(self.y_train)
        self.surrogate = self._init_surrogate()
        self.surrogate.fit(X, y)

    def optimize(self, **solver_kwargs) -> Dict:
        """运行代理+MC优化"""
        # 1. 初始采样
        print(f"[Surrogate-MC] 初始采样 {self.initial_samples} 个点...")
        self._initial_sampling()
        self._train_surrogate()

        # 2. 迭代优化
        for iter_idx in range(self.max_iterations):
            print(f"[Surrogate-MC] 迭代 {iter_idx+1}/{self.max_iterations}")

            # 创建代理问题
            surrogate = self.surrogate
            stoch_prob = self.stochastic_problem

            class SurrogateProxy(BlackBoxProblem):
                def __init__(self):
                    super().__init__(
                        name=f"Surrogate_{stoch_prob.name}",
                        dimension=stoch_prob.dimension,
                        bounds=stoch_prob.bounds
                    )

                def evaluate(self, x):
                    return float(surrogate.predict(x.reshape(1, -1))[0])

            # 用代理模型优化
            proxy_problem = SurrogateProxy()
            solver = self.inner_optimizer_factory(proxy_problem)
            for key, value in solver_kwargs.items():
                if hasattr(solver, key):
                    setattr(solver, key, value)

            solver.run()

            # 选择新样本点（从Pareto前沿或最优解）
            if hasattr(solver, 'pareto_solutions') and solver.pareto_solutions is not None:
                candidates = solver.pareto_solutions['individuals'][:self.samples_per_iter]
            else:
                sorted_idx = np.argsort(solver.objectives[:, 0])
                candidates = solver.population[sorted_idx[:self.samples_per_iter]]

            # 真实MC评估新样本
            for x in candidates:
                y = self._evaluate_mc(x)
                self.X_train.append(x)
                self.y_train.append(y)

            # 更新代理模型
            self._train_surrogate()

        # 3. 返回最优解
        best_idx = np.argmin(self.y_train)
        self.best_x = self.X_train[best_idx]
        self.best_f = self.y_train[best_idx]

        final_stats = self.evaluator.evaluate_statistics(self.stochastic_problem, self.best_x)

        return {
            'best_x': self.best_x,
            'best_f': self.best_f,
            'X_train': np.array(self.X_train),
            'y_train': np.array(self.y_train),
            'statistics': final_stats,
            'surrogate': self.surrogate
        }


# 便捷函数
def optimize_with_monte_carlo(stochastic_problem: StochasticProblem,
                              inner_optimizer_factory: Callable,
                              mc_samples: int = 100,
                              mode: str = 'expectation',
                              **solver_kwargs) -> Dict:
    """便捷函数：MC优化"""
    optimizer = MonteCarloOptimizer(stochastic_problem, inner_optimizer_factory, mc_samples, mode)
    return optimizer.optimize(**solver_kwargs)


def optimize_with_surrogate_mc(stochastic_problem: StochasticProblem,
                               inner_optimizer_factory: Callable,
                               mc_samples: int = 50,
                               surrogate_type: str = 'gp',
                               initial_samples: int = 20,
                               max_iterations: int = 10,
                               **solver_kwargs) -> Dict:
    """便捷函数：代理+MC优化"""
    optimizer = SurrogateMonteCarloOptimizer(
        stochastic_problem, inner_optimizer_factory, mc_samples,
        surrogate_type, initial_samples, max_iterations
    )
    return optimizer.optimize(**solver_kwargs)
