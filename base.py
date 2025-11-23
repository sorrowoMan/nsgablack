class BlackBoxProblem:
    """黑箱问题基类

    约定：
    - ``evaluate(x)`` 返回目标值（标量或 ndarray）
    - ``evaluate_constraints(x)`` 返回约束违背度数组 g(x) >= 0
      （<=0 视为满足约束，>0 为违反约束的程度）。
    """

    def __init__(self, name="黑箱问题", dimension=2, bounds=None):
        self.name = name
        self.dimension = dimension
        self.variables = [f'x{i}' for i in range(dimension)]
        if bounds is None:
            self.bounds = {var: [-5, 5] for var in self.variables}
        else:
            self.bounds = bounds

    def evaluate(self, x):
        raise NotImplementedError("子类必须实现evaluate方法")

    # ---- 约束相关统一接口 ----
    def evaluate_constraints(self, x):
        """返回约束违背度数组。

        约定：g(x) <= 0 表示满足约束，g(x) > 0 表示违反约束的程度。
        默认无约束，返回全零；子类可按需重写。
        支持单点 (d,) 或批量 (n,d) 输入。
        """
        import numpy as np

        if hasattr(x, "shape") and len(x.shape) > 1:
            # 批量输入：返回 (n, 0) 形状，方便后续 sum(axis=1)
            n = x.shape[0]
            return np.zeros((n, 0), dtype=float)
        # 单点：返回长度 0 的一维向量
        return np.zeros(0, dtype=float)

    def get_num_objectives(self):
        return 1

    def is_multiobjective(self):
        return self.get_num_objectives() > 1
