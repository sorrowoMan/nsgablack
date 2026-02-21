# Problem 组件（逐行批注版）

目标：让你在**不看源码细节**的前提下，也能写出一个可运行、可审计的问题类。

---

## 文件位置
`problem/my_problem.py`

## 直接可复制模板（每一行都解释）
```python
from __future__ import annotations  # 允许现代类型注解写法，避免前向引用带来的导入问题

import numpy as np  # 全部数值都统一用 numpy，避免 list/tuple 形状不一致

from nsgablack.core.base import BlackBoxProblem  # 框架标准问题基类，solver 按它的接口调用


class MyProblem(BlackBoxProblem):  # 你的问题类，必须继承 BlackBoxProblem
    def __init__(self, dimension: int = 8) -> None:  # 构造函数：定义规模和边界
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}  # 每个变量的上下界
        super().__init__(  # 把元信息注册给父类
            name="MyProblem",  # 问题名字，日志和导出会看到
            dimension=dimension,  # 决策向量长度
            bounds=bounds,  # 每个变量的边界
            objectives=["obj_0", "obj_1"],  # 目标标签，仅用于显示和解释
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:  # 目标函数：输入一个解，输出目标向量
        arr = np.asarray(x, dtype=float).reshape(-1)  # 强制变成一维 float，防止 shape 错
        if arr.size != self.dimension:  # 维度防御：早报错比静默错更好排查
            raise ValueError(f"x size {arr.size} != dimension {self.dimension}")  # 明确报错信息
        obj_0 = float(np.sum(arr ** 2))  # 目标1示例：平方和
        obj_1 = float(np.sum(np.abs(arr)))  # 目标2示例：绝对值和
        return np.array([obj_0, obj_1], dtype=float)  # 必须返回 numpy 向量，不要返回 list

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:  # 约束违背向量接口
        _ = x  # 示例无约束，先占位
        return np.zeros(0, dtype=float)  # 无硬约束时返回空向量，不要返回 None
```

---

## 你只需要改这 4 块
1. `dimension`（变量个数）
2. `bounds`（每个变量范围）
3. `evaluate()`（你的业务目标）
4. `evaluate_constraints()`（你的硬约束）

---

## 约束写法（有硬约束时）
```python
def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:  # 约束接口
    arr = np.asarray(x, dtype=float).reshape(-1)  # 标准化输入
    g0 = max(0.0, float(np.sum(arr) - 10.0))  # 约束1：sum(x)<=10，超出的部分就是违背量
    g1 = max(0.0, float(arr[0] - arr[1]))  # 约束2：x0<=x1，超出就是违背量
    return np.array([g0, g1], dtype=float)  # 0 表示可行，>0 表示违背
```

---

## 最容易错的点
- `evaluate()` 返回 Python list（错）  
  正确：`np.array([...], dtype=float)`
- 目标个数与 `objectives` 标签个数不一致
- `evaluate_constraints()` 返回 `None`（错）
- 在 `evaluate()` 内读写全局状态，导致不可复现

---

## 自检
- `python -m nsgablack project doctor --path . --build`
- Run Inspector 打开 Context，确认 `problem/objectives/constraint_violations` 都正常出现
