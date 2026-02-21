# Case C（稳健优化）- Problem 逐行批注

场景：目标函数含噪声，需要“均值好 + 方差小”。

```python
class RobustQuadraticProblem(BlackBoxProblem):  # 稳健二次问题示例
    def __init__(self, dimension: int = 20):  # 初始化
        bounds = {f"x{i}": [-3.0, 3.0] for i in range(dimension)}  # 变量边界
        super().__init__(name="RobustQuadratic", dimension=dimension, bounds=bounds, objectives=["mean_loss", "risk"])  # 双目标

    def evaluate(self, x: np.ndarray) -> np.ndarray:  # 目标评估
        arr = np.asarray(x, dtype=float).reshape(-1)  # 标准化
        base = float(np.sum(arr ** 2))  # 基础损失
        # 注意：真正的随机评估通常在 evaluator/plugin 中做，这里仅放一个静态占位
        return np.array([base, 0.0], dtype=float)  # 目标0=损失均值（占位），目标1=风险（占位）

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:  # 约束
        arr = np.asarray(x, dtype=float).reshape(-1)  # 标准化
        g0 = max(0.0, float(np.sum(np.abs(arr)) - 15.0))  # L1 预算约束
        return np.array([g0], dtype=float)  # 违背向量
```

## 重点
- 稳健问题里 `problem` 通常定义“结构目标”，随机部分交给插件链计算并写回 metrics。
- 这样可以把昂贵评估与问题定义解耦。
