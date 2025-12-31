import numpy as np
import random

try:
    # 当作为包导入时使用相对导入
    from ..core.base import BlackBoxProblem
except ImportError:
    # 当作为脚本运行时使用绝对导入
    try:
        from nsgablack.core.base import BlackBoxProblem
    except ImportError:
        # 直接从core目录导入
        import sys
        import os
        core_path = os.path.join(os.path.dirname(__file__), '..', 'core')
        if core_path not in sys.path:
            sys.path.insert(0, core_path)
        from base import BlackBoxProblem


class BlackBoxSolverVNS:
    """简单的 Variable Neighborhood Search (VNS) 实现。

    说明：
    - 针对单目标问题直接优化；对于多目标问题使用等权重线性标量化。
    - 支持在给定迭代次数内搜索并返回找到的最优解。

    该实现支持多种“邻域类型”和变尺度策略：
    - `neighborhood_type`: `"gaussian"` / `"coordinate"` / `"uniform"`
    - `scale_schedule`: `"linear"` / `"geometric"`
    - `base_step`: 基础步长（针对坐标/均匀扰动）
    """

    def __init__(self, problem: BlackBoxProblem):
        self.problem = problem
        self.dimension = problem.dimension
        self.variables = problem.variables
        self.bounds = problem.bounds
        # 外层循环与邻域层数
        self.max_iterations = 200
        self.k_max = 5
        # 基础扰动尺度（高斯）
        self.shake_scale = 0.2
        # 多种邻域策略
        self.neighborhood_type = "gaussian"  # "gaussian" | "coordinate" | "uniform"
        self.scale_schedule = "linear"       # "linear" | "geometric"
        self.base_step = 0.1                 # 对坐标/均匀扰动的基础步长
        # 局部搜索步数
        self.local_search_iters = 30
        # 统计与结果
        self.evaluation_count = 0
        self.best_x = None
        self.best_f = None
        self.history = []
        # bias 模块
        self.bias_module = None
        self.enable_bias = False

    def _random_within_bounds(self):
        x = np.zeros(self.dimension)
        for i, var in enumerate(self.variables):
            lo, hi = self.bounds[var]
            x[i] = random.uniform(lo, hi)
        return x

    def _clip(self, x):
        x2 = x.copy()
        for i, var in enumerate(self.variables):
            lo, hi = self.bounds[var]
            x2[i] = float(np.clip(x2[i], lo, hi))
        return x2

    def _scalarize(self, obj):
        arr = np.atleast_1d(obj)
        if arr.size == 1:
            return float(arr[0])
        # equal weights linear scalarization
        weights = np.ones(arr.size) / float(arr.size)
        return float(np.sum(arr * weights))

    def _evaluate(self, x):
        val = self.problem.evaluate(x)
        f = self._scalarize(val)

        # 应用 bias 模块
        if self.enable_bias and self.bias_module is not None:
            f = self.bias_module.compute_bias(x, f, individual_id=self.evaluation_count)

        self.evaluation_count += 1
        return f

    def _neighborhood_scale(self, k):
        """根据 k 计算本轮扰动尺度。"""
        if self.scale_schedule == "geometric":
            return self.shake_scale * (1.3 ** (k - 1))
        # 默认线性增长
        return self.shake_scale * (1.0 + 0.8 * (k - 1))

    def _shake(self, x, k):
        """在第 k 个邻域下生成新的候选点。"""
        scale = self._neighborhood_scale(k)
        if self.neighborhood_type == "coordinate":
            # 随机选若干坐标进行扰动
            x_new = x.copy()
            # 受扰动坐标数与 k 相关，但不超过维数
            num_coords = min(self.dimension, max(1, k))
            idx = np.random.choice(self.dimension, num_coords, replace=False)
            for j in idx:
                var = self.variables[j]
                lo, hi = self.bounds[var]
                step = self.base_step * scale * (hi - lo)
                x_new[j] += np.random.uniform(-step, step)
            return self._clip(x_new)
        elif self.neighborhood_type == "uniform":
            # 在以 x 为中心的超立方体内均匀采样
            x_new = x.copy()
            for j, var in enumerate(self.variables):
                lo, hi = self.bounds[var]
                step = self.base_step * scale * (hi - lo)
                x_new[j] += np.random.uniform(-step, step)
            return self._clip(x_new)
        # 默认：各维高斯扰动
        noise = np.random.normal(0, scale, size=self.dimension)
        return self._clip(x + noise)

    def _local_search(self, x0):
        x = x0.copy()
        f = self._evaluate(x)
        for _ in range(self.local_search_iters):
            cand = self._shake(x, k=1)
            fc = self._evaluate(cand)
            if fc < f:
                x, f = cand, fc
        return x, f

    def run(self):
        # 初始化
        self.evaluation_count = 0
        current_x = self._random_within_bounds()
        current_f = self._evaluate(current_x)
        self.best_x = current_x.copy()
        self.best_f = current_f
        self.history = [(0, current_f)]

        iter_no = 0
        while iter_no < self.max_iterations:
            k = 1
            improved = False
            while k <= self.k_max:
                # Shake
                x_shaken = self._shake(current_x, k)
                # Local search from shaken point
                x_local, f_local = self._local_search(x_shaken)
                # 接受准则（最小化）
                if f_local < current_f:
                    current_x, current_f = x_local, f_local
                    if f_local < self.best_f:
                        self.best_x, self.best_f = x_local.copy(), f_local
                    improved = True
                    # 回到 k=1
                    k = 1
                else:
                    k += 1
                # 限制总迭代计数
                iter_no += 1
                self.history.append((iter_no, current_f))
                if iter_no >= self.max_iterations:
                    break
            if not improved:
                # 若在所有邻域没有改进，可尝试重启一次小概率
                if random.random() < 0.1:
                    current_x = self._random_within_bounds()
                    current_f = self._evaluate(current_x)
                    if current_f < self.best_f:
                        self.best_x, self.best_f = current_x.copy(), current_f
                else:
                    # 否则结束搜索
                    break

        return {
            'best_x': self.best_x,
            'best_f': self.best_f,
            'evaluations': self.evaluation_count,
            'history': self.history,
        }


__all__ = ['BlackBoxSolverVNS']
