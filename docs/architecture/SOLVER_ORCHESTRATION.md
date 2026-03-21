# 求解器编排与资源契约（规范）

本规范定义“多 solver 编排”的最小契约与资源计算规则，避免架构侵入与资源超载。

---

## 1) 适用范围

- 多 solver 编排（并行/串行）
- 与嵌套求解器并存
- 管理器**只做调度与资源校验**，不做策略

---

## 2) 角色语义（避免混淆）

### Solver 编排（Regime Orchestration）
- 目的：管理多套 solver 并行或串行运行  
- 行为：调度、资源校验、结果汇总  
- 不做：策略逻辑、评估接管  

### 嵌套求解（Nested Evaluation）
- 目的：外层评估调用内层求解器  
- 语义：评估实现方式（L4/问题侧内层）  
- 不走 Solver 编排入口  

---

## 3) 资源声明（最小契约）

管理器只读取**资源声明**，不干预 solver 内部实现。

```python
ResourceRequest(
  threads=4,
  gpus=0,
  backend="local",
)
```

管理器提供资源上限：

```python
ResourceOffer(
  threads=8,
  gpus=1,
  backend="local",
)
```

**硬约束规则**：
- 超预算 **直接报错**
- 不降级、不排队

---

## 4) 资源计算规则

### 4.1 并行 / 串行

- **并行**：同一 phase 的资源需求求和  
- **串行**：phase 之间不叠加  

### 4.2 嵌套资源叠加（核心）

如果外层 solver 在评估阶段触发内层求解器：

外层资源 = **a**  
内层资源 = **b**  

**总资源上界**：

```
total = a + a * b
```

解释：  
外层并行 `a` 个 worker，每个 worker 调用一次内层，内层消耗 `b`。

---

## 5) 内层求解器识别（默认）

管理器通过以下方式识别内层求解器（优先级顺序）：

1. `problem.inner_runtime_evaluator`（若为 InnerRuntimeEvaluator）  
2. `solver.inner_solver` 或 `problem.build_inner_solver(...)`  

若无法识别，则视为**无内层**（b=0）。

建议内层 solver 提供 `resource_request()` 以便精确计算。

---

## 6) 默认行为（最小侵入）

- 单 solver：与旧流程完全一致  
- 多 solver：进入编排入口（Manager）  
- Manager 只做：**调度 + 资源校验 + 结果汇总**  

---

## 7) 典型场景

### 并行体制
```
Phase 0: Solver A || Solver B
```

资源需求 = `A_total + B_total`

### 串行接力
```
Phase 0: Solver A
Phase 1: Solver B
```

资源需求 = `max(A_total, B_total)`

---

## 8) 错误示例

Offer = 8 threads  
Outer = 4  
Inner = 2  

total = 4 + 4*2 = 12 > 8 → **报错**

---

## 9) 设计原则

- 管理器不参与策略  
- 资源硬约束  
- 不增加用户负担  
- 兼容未来多后端  

