# Case B（TSP）- Bias 逐行批注

这个文件给的是**可直接接入的 TSP 偏好示例**（不是模板空壳）。

```python
from nsgablack.bias.core.base import Bias  # 偏置基类
import numpy as np  # 数值工具


class RouteEdgeDiversityBias(Bias):  # 鼓励路径边结构多样性
    name = "route_edge_diversity"  # 偏置名

    context_requires = ("edge_archive",)  # 需要已有边档案（可选）
    context_provides = ()  # 不提供字段
    context_mutates = ()  # 不修改字段
    context_cache = ()  # 不缓存
    context_notes = ("Penalize edge-overlap with archive routes.",)  # 说明

    requires_metrics = ()  # 不依赖 metrics
    metrics_fallback = "neutral"  # 缺失时中性

    def __init__(self, weight: float = 0.2):  # 初始化
        super().__init__()  # 父类初始化
        self.weight = float(weight)  # 权重

    def compute(self, x, context=None):  # 核心评分函数
        route = np.asarray(x, dtype=int).reshape(-1)  # 当前路径
        edges = {(int(route[i]), int(route[(i + 1) % route.size])) for i in range(route.size)}  # 当前边集合
        archive = (context or {}).get("edge_archive", [])  # 历史边集合列表
        if not archive:  # 没档案就不惩罚
            return 0.0
        overlap = 0  # 重叠边计数
        for old_edges in archive:  # 遍历历史边集合
            overlap += len(edges & set(old_edges))  # 计算交集大小
        return self.weight * float(overlap)  # 重叠越多惩罚越大
```

## 重点
- TSP 里 bias 适合表达“结构偏好”（如边重复少、局部多样性）。
- 不建议把完整 2-opt/3-opt 过程塞进 bias，流程类逻辑放 adapter。
