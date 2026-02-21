# Case C（稳健优化）- Pipeline 逐行批注

目标：给稳健优化提供“稳定搜索空间”，避免无意义极端解。

```python
class RobustInit(RepresentationComponentContract):  # 初始化器
    def initialize(self, problem, context=None):  # 生成初始解
        _ = context  # 当前不用 context
        dim = int(problem.dimension)  # 维度
        rng = np.random.default_rng()  # 局部 RNG
        return rng.uniform(-1.0, 1.0, size=(dim,))  # 初始解在较小区间，降低早期风险


class RobustMutation(RepresentationComponentContract):  # 变异器
    def mutate(self, x, context=None):  # 变异
        arr = np.asarray(x, dtype=float).copy()  # 复制
        sigma = float((context or {}).get("mutation_sigma", 0.15))  # 支持 context 覆盖
        rng = np.random.default_rng()  # 局部 RNG
        return arr + rng.normal(0.0, sigma, size=arr.shape)  # 高斯扰动


class BudgetRepair(RepresentationComponentContract):  # 预算修复器
    def repair(self, x, context=None):  # 修复
        _ = context  # 当前不用 context
        arr = np.asarray(x, dtype=float).copy()  # 复制
        arr = np.clip(arr, -3.0, 3.0)  # 先做边界修复
        l1 = float(np.sum(np.abs(arr)))  # 当前 L1 范数
        if l1 > 15.0:  # 超预算
            arr = arr * (15.0 / (l1 + 1e-12))  # 等比例缩放回预算边界
        return arr  # 返回可行解
```

## 重点
- 稳健场景尤其要避免无界扰动，repair 必须稳定。
- `repair` 是硬约束兜底，不承担偏好表达。
