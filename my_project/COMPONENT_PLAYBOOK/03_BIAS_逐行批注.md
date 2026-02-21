# Bias 组件（逐行批注版）

目标：只表达“偏好强弱”，不实现完整算法过程。

---

## 文件位置
`bias/my_bias.py`

## 直接可复制模板（每行解释）
```python
from __future__ import annotations  # 现代注解

import numpy as np  # 数值计算

from nsgablack.bias.core.base import Bias  # 偏置基类
from nsgablack.utils.context.context_keys import KEY_GENERATION, KEY_METRICS_MC_STD  # 统一 key


class FrontloadPenaltyBias(Bias):  # 示例1：惩罚“提前太多”
    name = "frontload_penalty"  # bias 名称，日志和权重匹配依赖它

    context_requires = (KEY_GENERATION,)  # 依赖字段：代数
    context_provides = ()  # 不提供字段
    context_mutates = ()  # 不改 context
    context_cache = ()  # 不写缓存
    context_notes = ("Penalize large front-load moves in late stage.",)  # 说明

    requires_metrics = ()  # 这个 bias 不依赖 metrics 子字段
    metrics_fallback = "neutral"  # 缺指标时中性处理

    def __init__(self, weight: float = 1.0, pivot: float = 5.0):  # 参数
        super().__init__()  # 父类初始化
        self.weight = float(weight)  # 权重
        self.pivot = float(pivot)  # 阈值

    def compute(self, x, context=None):  # 核心：返回偏好标量
        arr = np.asarray(x, dtype=float).reshape(-1)  # 标准化输入
        gen = int((context or {}).get(KEY_GENERATION, 0))  # 读取代数
        front_part = arr[: max(1, arr.size // 3)]  # 示例：前 1/3 视为前移相关变量
        avg_shift = float(np.mean(np.maximum(front_part, 0.0)))  # 只统计前移（正值）
        stage_gain = 1.0 + 0.02 * gen  # 代数越后惩罚越强
        penalty = max(0.0, avg_shift - self.pivot)  # 超过阈值才惩罚
        return self.weight * stage_gain * penalty  # 输出偏置值


class UncertaintyExplorationBias(Bias):  # 示例2：鼓励高不确定区域探索
    name = "uncertainty_exploration"  # bias 名称

    context_requires = ()  # 不强依赖 context 主字段
    context_provides = ()  # 不提供字段
    context_mutates = ()  # 不改 context
    context_cache = ()  # 不缓存
    context_notes = ("Encourage exploration with high MC uncertainty.",)  # 说明

    requires_metrics = (KEY_METRICS_MC_STD,)  # 依赖指标字段
    metrics_fallback = "neutral"  # 缺失指标时中性

    def __init__(self, weight: float = 0.5):  # 参数
        super().__init__()  # 父类初始化
        self.weight = float(weight)  # 权重

    def compute(self, x, context=None):  # 返回偏置值
        _ = x  # 这个 bias 不直接用 x
        metrics = (context or {}).get("metrics", {})  # 读取指标容器
        std = float(metrics.get("mc_std", 0.0))  # 读取不确定性
        return -self.weight * std  # 示例：负值代表鼓励（看你总目标聚合约定）
```

---

## build_solver 接线
```python
from bias.my_bias import FrontloadPenaltyBias, UncertaintyExplorationBias  # 导入

solver.bias_module.add(FrontloadPenaltyBias(weight=1.2, pivot=4.0))  # 添加偏好1
solver.bias_module.add(UncertaintyExplorationBias(weight=0.3))  # 添加偏好2
```

---

## 什么时候放 bias，什么时候放 adapter
- 放 bias：你只是要表达“倾向”（更平滑、更稳健、少前移）
- 放 adapter：你要表达“完整过程”（选择、更新、邻域、协同）

一句话：**bias 是信号，adapter 是流程。**
