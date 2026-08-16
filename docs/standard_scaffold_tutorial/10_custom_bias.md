# 10. 自定义 Bias（nsgablack 详细实战）

本章讲如何在不破坏边界的前提下，做“可解释的软引导”。

## 1. Bias 的职责

Bias 负责：

- 偏好引导
- 先验注入
- 软约束倾向

Bias 不负责：

- 重写 objective/constraint 定义（Problem 负责）
- 取代 Adapter 搜索策略（Adapter 负责）
- 全局编排与资源发放（Project substrate / L0 负责）

---

## 2. 创建 Bias 文件

```powershell
python -m nsgablack project add-component --case my_solver --kind bias --name my_bias
```

---

## 3. 最小 Bias 示例

```python
class MyBias:
    def __init__(self, alpha: float = 0.1):
        self.alpha = float(alpha)

    def apply(self, candidates, context=None):
        # 示例：轻微收缩，避免过大步长
        return candidates * (1.0 - self.alpha)
```

---

## 4. 三种常见 Bias 设计

### 4.1 初始化偏置

- 影响初始群体分布
- 不影响 objective 定义

### 4.2 候选排序偏置

- 在同质量候选中优先某类结构
- 例如更平滑、更稀疏、更低成本

### 4.3 探索-开发偏置

- 根据 `phase` 改变偏好
- 例如 `explore` 增强多样性，`exploit` 增强局部收敛

---

## 5. 挂载建议

常见做法：

- 在 adapter 内读取 bias manager（推荐）
- 或在 solver propose/update 前后显式调用

关键是：Bias 影响路径必须可审计，不能“静默生效”。

---

## 6. 审计字段建议

每次运行至少记录：

- bias key
- bias 参数
- 启用阶段（哪些 generation/phase）
- 与无 bias 基线差异（最好有指标）

---

## 7. 常见坑

1. Bias 做成硬约束替代  
   修复：硬约束仍在 Problem/repair。

2. Bias 逻辑写进 repair 导致边界混乱  
   修复：repair 仅做可行性兜底，策略偏好放 bias/adapter。

3. Bias 改写 context 大对象  
   修复：只写轻量元数据，重对象走 snapshot/artifact。
