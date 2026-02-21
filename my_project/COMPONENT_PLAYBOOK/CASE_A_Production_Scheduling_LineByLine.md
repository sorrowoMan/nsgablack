# 难题案例 A：排产约束问题（逐行版）

目标：
- 供应计划允许前移，不允许后移
- 尽量减少改动事件数
- 同时兼顾产出目标

---

## 1) Problem（目标 + 硬约束）
```python
class ProductionProblem(BlackBoxProblem):  # 排产问题定义
    def evaluate(self, x):  # 目标函数
        arr = np.asarray(x, dtype=float).reshape(-1)  # 解向量
        obj_shift_count = float(np.sum(arr > 0.5))  # 示例目标1：改动事件数量
        obj_capacity_loss = float(np.sum(np.maximum(0.0, 1.0 - arr)))  # 示例目标2：产出损失
        return np.array([obj_shift_count, obj_capacity_loss], dtype=float)  # 双目标输出

    def evaluate_constraints(self, x):  # 硬约束违背
        arr = np.asarray(x, dtype=float).reshape(-1)  # 解向量
        violate_backward = float(np.sum(arr < 0.0))  # 约束：不允许后移（<0 算违背）
        return np.array([violate_backward], dtype=float)  # 违背向量
```

## 2) Pipeline Repair（硬约束入口）
```python
class SupplyAwareScheduleRepair(RepresentationComponentContract):  # 修复器
    def repair(self, x, context=None):  # 修复函数
        _ = context  # 当前不用 context
        arr = np.asarray(x, dtype=float).copy()  # 复制
        arr[arr < 0.0] = 0.0  # 把所有后移值拉回 0（仅允许前移）
        return arr  # 返回可行解
```

## 3) Bias（软偏好：少提前）
```python
class FrontloadPenaltyBias(Bias):  # 前移惩罚偏置
    name = "frontload_penalty"  # 偏置名

    def compute(self, x, context=None):  # 偏好评分
        _ = context  # 当前示例不依赖 context
        arr = np.asarray(x, dtype=float).reshape(-1)  # 解向量
        days_advance = np.maximum(arr, 0.0)  # 前移量
        return float(np.sum(days_advance))  # 前移越多惩罚越大
```

## 4) 接线顺序建议
1. 先写 `Problem + Repair`（保证可行）
2. 再加 `Bias`（表达业务偏好）
3. 最后调 `Adapter`（优化过程效率）

一句话：硬约束归 repair，软偏好归 bias，不混层。
