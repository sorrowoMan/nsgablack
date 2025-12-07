import numpy as np
from typing import Callable, List, Tuple, Dict, Any

try:
    # 当作为包导入时使用相对导入
    from ..core.base import BlackBoxProblem
    from ..solvers.nsga2 import BlackBoxSolverNSGAII
    from ..core.problems import BusinessPortfolioOptimization
    from .headless import run_headless_single_objective
    from .manifold_reduction import PCAReducer
except ImportError:
    # 当作为脚本运行时使用绝对导入
    from core.base import BlackBoxProblem
    from solvers.nsga2 import BlackBoxSolverNSGAII
    from core.problems import BusinessPortfolioOptimization
    from utils.headless import run_headless_single_objective
    from utils.manifold_reduction import PCAReducer


class ReducedMultiObjectiveProblem(BlackBoxProblem):
    """将已有多目标 BlackBoxProblem 通过解码器降维后的包装器。

    变量是降维后的 z，evaluate 先用 expand_to_full(z) 还原到原空间 x，再调用基问题的 evaluate(x)。
    """
    def __init__(self, base_problem: BlackBoxProblem,
                 reduced_bounds: List[Tuple[float, float]],
                 expand_to_full: Callable[[np.ndarray], np.ndarray],
                 name: str | None = None):
        name = name or f"降维-{base_problem.name}"
        super().__init__(name=name, dimension=len(reduced_bounds),
                         bounds={f"x{i}": [float(lo), float(hi)] for i, (lo, hi) in enumerate(reduced_bounds)})
        self._base = base_problem
        self._expand = expand_to_full
        self.num_objectives = self._base.get_num_objectives()

    def evaluate(self, z: np.ndarray):
        x = self._expand(np.asarray(z, dtype=float))
        return self._base.evaluate(x)

    def get_num_objectives(self):
        return self._base.get_num_objectives()


def build_pca_reduced_multiobjective_problem(base_problem: BlackBoxProblem,
                                             n_components: int = 3,
                                             initial_samples: int = 200,
                                             sampling_method: str = 'lhs',
                                             pad_ratio: float = 0.10,
                                             scale: bool = True) -> Dict[str, Any]:
    """利用 PCA 在自变量空间降维，构造多目标降维问题包装器（直接使用 PCAReducer，避免维度不一致）。

    返回字典：
    - problem: 降维后的 BlackBoxProblem（可直接交给 NSGA-II）
    - expand_to_full: z -> x 的映射
    - reduced_bounds: 降维边界
    - pca_model, samples_info: 额外信息
    """
    # 采样原空间自变量
    dim = base_problem.dimension
    ordered_bounds = [tuple(base_problem.bounds[v]) for v in base_problem.variables]
    if sampling_method == 'lhs':
        X = np.zeros((initial_samples, dim))
        for i in range(dim):
            X[:, i] = np.random.permutation(initial_samples) + np.random.uniform(0, 1, initial_samples)
            X[:, i] = X[:, i] / initial_samples
        for i, (lo, hi) in enumerate(ordered_bounds):
            X[:, i] = lo + X[:, i] * (hi - lo)
    elif sampling_method == 'random':
        X = np.random.uniform(0, 1, (initial_samples, dim))
        for i, (lo, hi) in enumerate(ordered_bounds):
            X[:, i] = lo + X[:, i] * (hi - lo)
    else:
        raise ValueError('不支持的采样方法')

    reducer = PCAReducer(n_components=n_components, scale=scale).fit(X, ordered_bounds)
    Z = reducer.encode(X)

    # 用编码样本确定降维边界
    reduced_bounds: List[Tuple[float, float]] = []
    for j in range(n_components):
        z_min, z_max = float(np.min(Z[:, j])), float(np.max(Z[:, j]))
        span = z_max - z_min
        pad = max(1e-6, pad_ratio * span)
        reduced_bounds.append((z_min - pad, z_max + pad))

    def expand_to_full(z_vec: np.ndarray) -> np.ndarray:
        z = np.asarray(z_vec, dtype=float)
        if z.ndim == 1:
            z = z.reshape(1, -1)
            Xfull = reducer.decode(z)
            return Xfull[0]
        else:
            Xfull = reducer.decode(z)
            return Xfull

    reduced_problem = ReducedMultiObjectiveProblem(
        base_problem=base_problem,
        reduced_bounds=reduced_bounds,
        expand_to_full=expand_to_full,
        name=f"PCA降维-{base_problem.name}"
    )

    return {
        'problem': reduced_problem,
        'expand_to_full': expand_to_full,
        'reduced_bounds': reduced_bounds,
        'pca_model': reducer,
        'samples_info': {'X': X, 'Z': Z}
    }
