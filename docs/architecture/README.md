# 架构概览

[自然搜索编排：已实现接口](NATURAL_SEARCH_PLANS_CN.md) 用 stage/serial/multi/repeat 表达局部额度和有限循环，
保留同一算法实例；精修等本次 PoolTask 完成，再把当前轮最终结果交回竞争，复用原 Router 与事务。
第 7 节记录反向审计后的修复：组合重入、旧组合完成／取消传递、动态权重回滚、最终视图身份与无累计历史交付；精修器提前正常终止仍明确拒绝，不把已测组合推广为任意 Python 组件保证。

[自然编排场景草案，第 39 节](ORCHESTRATION_WITH_INCREMENTAL_UNITS_DISCUSSION_CN.md#39-自然编排先确定场景再决定写法)
先用十三类场景明确嵌套循环、局部额度、并行汇合、触发重入、Pool 输入时点和恢复；39.6—39.10 保留设计推演，有限首版接口及当前限制见上方自然搜索编排文档。

[Pool 数据结构与基础操作](POOL_DATA_MODEL_AND_OPERATIONS_CN.md) 对照统一 Pool 接口的设计与实现：第 16.7 节的 partition 已实现，第 17 节按 26 类场景核查阶段交接，第 18 节接通复杂选择的主成员与命名副结果；18.5 给出精英父代、GA→VNS 与同批历史成员档案三个用途，复用原成员计划和提交事务。Store 门面等未来签名仍明确标为设计。

[Pool 与 Adapter 接口手册](POOL_API_REFERENCE_CN.md) 按真实调用位置列出现有方法、返回值与示例；核对 Pareto、精英、多样性、禁忌、指标与结果的接入状态，区分现有能力和建议 API。
第 0 节新增可运行的 chosen／空草稿／inject 语法：先选解，再声明普通目标成员，复用原事务；当前只接入 survivor 与成员维护，不另建调度语言。
0.5 接通 multi/serial 的 working_pool 绑定：子任务继承最近区域，显式来源仍优先，新接纳候选归属最近组合；标准 Case 验证来源隔离与恢复。

[Pool 与 Adapter 的最小完善方案](POOL_MINIMAL_EVOLUTION_PLAN_CN.md) 记录已落地的事务内池成员决策与批量后代两个闭环，以及必要约束、暂缓范围和验收标准。

[Pool 集合操作](POOL_COLLECTION_OPERATIONS_CN.md) 补齐过滤、显式排序、交差与分组，以及保留池身份的成员替换/移除/裁剪；普通函数通过 PoolEdit 提交成员变更计划。

[池驱动变化编排](POOL_CHANGE_ORCHESTRATION_CN.md) 开放 VNS/MOEA-D 完整变化的池来源、操作顺序和接纳后输出，保留输入声明、候选身份与原算法比较规则。

[池输入与普通函数算法试作：VNS / MOEA-D](POOL_WORKFLOW_PILOT_CN.md) 将已有算法的 Initiate、Chose、Change、Return 位置显式化，用普通函数组合完整变化；记录已运行 Project 和后续 Pool 改造缺口，不提前引入池 DSL。

[Adapter 行为装配边界](ADAPTER_OPERATION_BOUNDARIES_CN.md) 按算法族解释初始化、变化、选择和修复的真实接缝，区分可装配角色、原生结构操作、Provider 与组合限制；四类是职责分类，不是固定时序。

[Adapter 局部算子装配](ADAPTER_OPERATOR_BINDINGS_CN.md) 用 NSGA-II/III、SPEA2 的独立父代选择与 mutator，验证更换池来源不必改写算法流程；同时说明身份、Unit 输入与恢复边界。

[前沿算法拆解试验：CDM-PSL](FRONTIER_ALGORITHM_DECOMPOSITION_PILOT_CN.md) 对照原论文检查四类能力的操作边界、数据与模型依赖，并区分测试重放、正式接入和性能复现的证据范围。

[Unit 契约职责与组合验收](UNIT_CONTRACT_MAP_CN.md) 列出现有 18 个职责组的用途、消费者、坐标和状态生命周期，并记录修复、接纳、成员维护、Provider 清理与恢复的组合验证范围。

[Adapter 决策与 Unit 成员维护](UNIT_MEMBER_OPERATIONS_CN.md) 用 age 示例说明继承扩展、成员来源映射、草稿校验与恢复。

[ProblemRepair 与 UnitRepair 共同验收](JOINT_REPAIR_CN.md) 定义独立修复、临时 Unit、版本验证与失败决策。

[算子 Unit 输入与 repair 顺序](UNIT_OPERATOR_INPUTS_CN.md) 说明如何声明变异依赖，以及预算、修复、结构校验的职责。

Unit 保留候选本体并扩展算法特征、关系和状态，构建与取出候选不隐含编解码。当前特征维护、缓存与反馈阶段说明见 [Unit 特征维护](UNIT_FEATURES_CN.md)。

理解当前框架优先沿 **Problem → Pipeline → Unit → Adapter → Bias → Plugin** 的职责关系阅读。Unit 是算法结构核心；旧“四层”只是扩展面的概括。[Unit 与偏好契约](UNIT_PREFERENCE_CONTRACT_CN.md) 说明不同评价范围、实例依赖与状态更新。

最后按代码核对：2026-10-08。当前运行所有权、Unit、能力声明、参与度和偏好证据的规范入口为 [运行所有权与显式扩展契约](RUNTIME_CONTRACTS_CN.md)。以下四层是装配视角；Solver 内部运行状态由 RunSession、PopulationAuthority 等对象持有。

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
- 问题管线处理候选，UnitBinding 提供结构构建规则；所属 Adapter 按需创建并操作 Unit
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
