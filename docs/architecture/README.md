# Architecture Overview

这份文档只回答一件事：  
**现在这套框架里，谁做什么，谁通过谁做什么。**

我用“责任边界”来讲，不讲花哨术语。

---

## 1. 控制层

文件：

- `core/blank_solver.py`
- `core/composable_solver.py`
- `core/evolution_solver.py`

职责：

- 生命周期调度
- 控制面 API
- 组件装配编排

边界：

- 只做控制与调度，不承载具体策略算法细节

---

## 2. 策略层

文件：

- `adapters/*`

职责：

- 搜索流程核心（`propose/update`）

边界：

- Adapter 不直接写 solver 私有运行态
- Adapter 通过 `solver.*` 控制面协作

---

## 3. 表示与偏好层

文件：

- `representation/*`
- `bias/*`

职责：

- `representation`：初始化、变异、修复、编码解码
- `bias`：软偏好、策略倾向

边界：

- 硬约束优先留在 pipeline
- bias 不替代硬约束机制

---

## 4. 能力层

文件：

- `plugins/*`

职责：

- 并行、日志、checkpoint、trace、报告、评估短路

边界：

- Plugin 是横切能力层，不做策略内核决策

---

## 5. 数据层

文件：

- `utils/context/context_store.py`
- `utils/context/snapshot_store.py`

职责：

- `ContextStore`：小字段、信号、引用
- `SnapshotStore`：大对象快照

这是我认为最关键的稳定器：

- context 轻量、可传播
- snapshot 重载、可存储

---

## 6. 治理层

文件：

- `catalog/*`
- `project/doctor.py`
- `tests/*`

职责：

- Catalog：可发现、可装配
- Doctor：结构误用拦截
- Tests：回归与行为保护

---

## 7. 三条流

### 工作流

`Problem -> Pipeline -> Adapter -> Bias -> Plugin -> Run -> Doctor/Test`

### 数据流

- 大对象：`SnapshotStore`
- 小字段：`ContextStore`

统一接口：

- `solver.read_snapshot()`
- `Plugin.resolve_population_snapshot()`
- `Plugin.commit_population_snapshot()`

### 组件流

- Solver 调度
- Adapter 搜索
- Pipeline 可行化
- Bias 偏好
- Plugin 能力

---

## 8. 状态写入责任

允许：

- 通过 `solver.*` 控制面写状态
- 通过 context/snapshot 正确分层写数据

禁止：

- 组件直接写 `solver.population/objectives/constraint_violations/...`
- 组件绕过控制面写私有运行态

---

## 9. 健康检查标准

我用三个标准判断架构是否健康：

1. 路径唯一  
状态更新路径不分叉，不出现双轨。  

2. 职责单一  
Adapter/Plugin/Solver 各司其职。  

3. 治理闭环有效  
`doctor --strict` 与测试长期稳定。  

---

## 10. 快速自检命令

```powershell
python -m nsgablack project doctor --path . --strict
python -m pytest -q
```

如果这两条能稳定通过，说明这套架构不仅“概念正确”，而且“工程上可持续”。
