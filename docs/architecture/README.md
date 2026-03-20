# 架构概览

这份文档回答一个问题：  
**在 NSGABlack 中，谁负责什么，谁通过谁完成什么。**

---

## 一、四层正交架构

- **Solver**：控制平面与生命周期（调度、评估入口、状态管理）
- **Adapter**：算法策略平面（`propose/update`）
- **Representation**：表示平面（init/mutate/repair/encode/decode）
- **Plugin**：能力平面（日志、评估短路、checkpoint、审计）

边界原则：
- Solver 不承载具体搜索策略  
- Adapter 不直接改写 solver 私有状态  
- Representation 只处理“可行解管线”  
- Plugin 只做工程能力增强，不替代策略逻辑

---

## 二、架构总览图（文字版）

```
                 +--------------------+
                 |       Solver       |
                 |  lifecycle/control |
                 +---------+----------+
                           |
                 +---------v----------+
                 |      Adapter       |
                 | propose / update   |
                 +---------+----------+
                           |
                 +---------v----------+
                 |  Representation    |
                 | init/mutate/repair |
                 +---------+----------+
                           |
                 +---------v----------+
                 |    Evaluation      |
                 | exact / approximate|
                 +---------+----------+
                           |
                 +---------v----------+
                 |      Plugin        |
                 | log/trace/checkpt  |
                 +--------------------+
```

> 评估路径可被 L4 provider 短路（代理评估/近似评估）。

---

## 三、运行数据流（标准一代）

`adapter.propose -> representation -> evaluate_population -> adapter.update -> plugin hooks`

---

## 四、Context / Snapshot 分层

- **ContextStore**：小字段与引用  
- **SnapshotStore**：大对象（population/objectives/violations）

统一入口：
- `solver.read_snapshot()`
- `Plugin.get_population_snapshot()`
- `Plugin.commit_population_snapshot()`

---

## 五、评估链路（L4）

- 支持 `individual` 与 `population` 两条路径  
- 近似评估默认关闭（可通过 `EvaluationMediatorConfig.allow_approximate=True` 开启）  
- Provider 通过优先级仲裁（priority）  

---

## 六、治理与发现

- **Catalog**：可发现性索引与双口径统计  
  - `default`：完整口径（含 example/doc）  
  - `framework-core`：主干口径（排除 example/doc）
- **Project Doctor**：结构与契约检查  
- **Tests**：回归与行为保护  

---

## 七、相关文档

- `START_HERE.md`
- `WORKFLOW_END_TO_END.md`
- `docs/architecture/COPT_INTEGRATION.md`

---

## 典型架构拓扑（启发式 + 数值求解）

示例：

外层使用启发式/多目标策略做全局搜索；  
内层使用 COPT 等数值求解器做局部精修与可行性验证；  
内层既可以作为 L4 评估 provider，也可以作为子求解器嵌入 Adapter 编排。
