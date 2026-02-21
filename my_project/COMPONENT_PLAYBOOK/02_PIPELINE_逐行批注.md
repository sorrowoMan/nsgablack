# Pipeline 组件（逐行批注版）

目标：定义“解怎么来、怎么变、怎么修”。

---

## 文件位置
`pipeline/my_pipeline.py`

## 直接可复制模板（initializer / mutator / repair）
```python
from __future__ import annotations  # 现代注解写法

import numpy as np  # 向量运算

from nsgablack.representation.base import RepresentationComponentContract  # 管线组件契约基类
from nsgablack.utils.context.context_keys import KEY_GENERATION, KEY_MUTATION_SIGMA  # 标准 context key


class MyInitializer(RepresentationComponentContract):  # 初始化器：生成初始解
    context_requires = ()  # 不依赖 context 字段
    context_provides = ()  # 不声明产出字段
    context_mutates = ()  # 不改 context
    context_cache = ()  # 不写缓存
    context_notes = ("Generate random initial solution in bounds.",)  # 说明

    def initialize(self, problem, context=None):  # 框架会在初始化种群时调用
        _ = context  # 当前不用 context
        dim = int(problem.dimension)  # 变量维度
        lower = np.array([problem.bounds[f"x{i}"][0] for i in range(dim)], dtype=float)  # 下界向量
        upper = np.array([problem.bounds[f"x{i}"][1] for i in range(dim)], dtype=float)  # 上界向量
        rng = np.random.default_rng()  # 局部随机数生成器，避免污染全局 RNG
        return rng.uniform(lower, upper)  # 在边界内均匀采样


class MyMutation(RepresentationComponentContract):  # 变异器：对解做扰动
    context_requires = (KEY_GENERATION,)  # 依赖当前代数（做动态强度）
    context_provides = ()  # 不提供新字段
    context_mutates = ()  # 不改 context
    context_cache = ()  # 不写缓存
    context_notes = ("Gaussian mutation with generation-aware sigma.",)  # 说明

    def __init__(self, base_sigma: float = 0.2):  # 基础噪声强度
        self.base_sigma = float(base_sigma)  # 存参数

    def mutate(self, x, context=None):  # 输入一个解，输出变异后的解
        arr = np.asarray(x, dtype=float).copy()  # 复制，避免原地改坏输入
        gen = int((context or {}).get(KEY_GENERATION, 0))  # 读取代数
        sigma = float((context or {}).get(KEY_MUTATION_SIGMA, self.base_sigma))  # 允许 context 覆盖 sigma
        sigma = max(1e-6, sigma / (1.0 + 0.01 * gen))  # 简单退火：后期变异减弱
        rng = np.random.default_rng()  # 局部 RNG
        noise = rng.normal(0.0, sigma, size=arr.shape)  # 高斯噪声
        return arr + noise  # 返回新解


class MyRepair(RepresentationComponentContract):  # 修复器：硬约束回拉
    context_requires = ()  # 不依赖额外字段
    context_provides = ()  # 不产出字段
    context_mutates = ()  # 不改 context
    context_cache = ()  # 不缓存
    context_notes = ("Clip solution to legal range.",)  # 说明

    def __init__(self, lower: float = -5.0, upper: float = 5.0):  # 示例边界
        self.lower = float(lower)  # 下界
        self.upper = float(upper)  # 上界

    def repair(self, x, context=None):  # 修复函数
        _ = context  # 当前不用 context
        arr = np.asarray(x, dtype=float).copy()  # 复制
        return np.clip(arr, self.lower, self.upper)  # 回拉到合法区间
```

---

## build_solver 接线（最小版）
```python
from pipeline.my_pipeline import MyInitializer, MyMutation, MyRepair  # 导入组件

solver.add_initializer(MyInitializer())  # 加初始化器
solver.add_mutator(MyMutation(base_sigma=0.2))  # 加变异器
solver.add_repair(MyRepair(lower=-5.0, upper=5.0))  # 加修复器
```

---

## 组件边界（必须遵守）
- Pipeline 处理“解的结构与可行性”
- Problem 处理“目标与约束评价”
- Bias 处理“偏好倾向”
- Adapter 处理“完整算法流程”
