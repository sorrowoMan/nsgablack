# 架构概览

这份文档回答一个问题：  
**在统一框架栈中，substrate 和语义层分别负责什么。**

当前第一原则：

```text
Shared substrate:
  Project / Case / Scaffold / L0 / Context / Snapshot / Artifact refs / Doctor / Catalog

nsgablack semantic layer:
  Solver / Adapter / Representation / Bias / Plugin / Pareto / objective-constraint optimization

mlblack semantic extension:
  DataView / Spec / Codec / Head / LearningProblem / Evaluation Provider / ML Artifact
```

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

## 七、Project / Case / Scaffold / L0 substrate

```text
project_root/
  project_config.py      # stages, groups, dependencies, Project L0 offer/policy/request
  run_project.py         # formal project entry and ResourceContext grant
  cases/
    case_a/
      build_solver.py    # canonical case assembly
      run_solver.py      # case debug only
      problem/
      pipeline/
      adapter/
      plugins/
      runtime/           # requirement/profile/audit, not global lease ownership
```

规则：

- 多 solver、多 trainer、多混合 case 编排都属于 substrate。
- `nsgablack` 和 `mlblack` case 都可以作为外层或内层。
- Project L0 发放 `ResourceContext`；case 只声明需求和消费 grant。

---

## 八、相关文档

- `docs/standard_scaffold_tutorial/README.md`：标准 Project / Case / Scaffold 教程。
- `docs/architecture/SOLVER_ORCHESTRATION.md`：多 case 编排与资源契约。
- `docs/architecture/L0_RESOURCE_ORCHESTRATION.md`：Project L0 与 ResourceContext 规则。
- `docs/architecture/L0_TASK_RESOURCE_BACKEND_ARCHITECTURE.md`：task / resource / backend / transport 分层。
- `docs/architecture/ADAPTER_CONTRACT_CARDS.md`：adapter 恢复等级与 context 契约。
- `docs/architecture/module_structure.md`：当前代码目录职责速查。
- `docs/guides/MULTI_STRATEGY_COOPERATION.md`：多策略与多 case 协作的使用层说明。
- `docs/integrations/COPT_INTEGRATION.md`：数值求解器作为 inner case / provider / plugin 的集成边界。
- 已删除设计通过 Git 历史查阅，不在现行文档树内维护第二套口径。

---

## 典型架构拓扑（启发式 + 数值求解）

示例：

外层使用启发式/多目标策略做全局搜索；  
内层使用 COPT 等数值求解器做局部精修与可行性验证；  
内层应优先作为标准 case 或 L4 评估 provider 被外层 case 调用；不要把完整内层流程私下塞进 Adapter。
