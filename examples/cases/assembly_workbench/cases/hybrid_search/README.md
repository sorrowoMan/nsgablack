# hybrid_search：配方搜索、精英池与局部精修

这个 Case 用一个两维约束配方问题串起完整装配：问题管线生成并修复候选，GA 维护带年龄的种群，把最终生存成员中的精英引用放入普通子池；VNS 从精英池逐成员精修，最后把选中的结果交回 GA 竞争。整个流程重复两轮。

它没有自建运行循环，也没有通过 Plugin 编写搜索。`SearchPlanAdapter` 只编排现成 Adapter，候选身份、修复通知、硬接纳、池成员发布、步骤回滚、L0 和结果发布继续使用框架正式路径。

## 运行

在本 Project 根目录 `examples/cases/assembly_workbench/`：

```powershell
python run_project.py --group hybrid
python run_project.py --group provider
```

`hybrid` 使用 `Problem.evaluate`；`provider` 通过同一求值仲裁面注册等价向量化 Provider。两种模式在默认配置下都提交 14 个逻辑步骤、消耗 36 次候选求值。Provider 模式的 `Problem.evaluation_count` 为 0，Solver 的预算计数仍为 36。

默认输出为 Project 内 `results/hybrid_search/trace.json` 和 `checkpoints/`。`output_dir` 可以通过正式 `component_overrides={"config": {"output_dir": ...}}` 改到独立位置。完整 Project 的 `default` / `dag` 组还会把本 Case 的 `summary` Artifact 交给后续 Case；跨 Case 输入读取 Artifact，不读取这个观察文件。

## 先看这些文件

- `build_solver.py`：唯一装配入口，接收 `config`、`resource_context` 和 `component_overrides`。
- `problem/recipe.py`：成本和原始约束。
- `pipeline/main.py`：初始化、共享变异、问题修复与显式管线状态 codec。
- `pipeline/population.py`：自定义种群 Unit 的成员年龄；文件放在 pipeline 区不意味着由问题管线创建 Unit。
- `adapter/composition.py`：GA / VNS / PoolTask / SearchPlan 的组合。
- `adapter/operations.py`：普通 Python 函数表达交叉后变异、生存选择和精英集合。
- `bias/__init__.py`：候选级软评分。
- `evaluation/provider.py`：可选等价求值 Provider。
- `plugins/trace.py`：观察、发布前否决检查、summary Artifact 暂存。
- `catalog/entries/components.toml`：本 Case 私有组件的发现信息。

## 问题与反馈

候选 `x=[a,b]` 表示两种原料的量：

```text
minimize (a-0.85)^2 + 1.6*(b-0.65)^2 + 0.03*(a+b)
subject to 0 <= a,b <= 1 and a+b <= 1.2
```

`RecipeRepair` 先裁剪坐标，再在总量超过 1.2 时等比缩小。它不选择成员、不调用求值，也不改 Unit。`FeasibleEvaluationAcceptance` 使用 Problem 的原始违反量作硬接纳。

`BalancedMixBias` 在选择评分中增加 `weight*(a-b)^2`。它表达更均衡的配比偏好。母池原始目标与约束保留，GA 与 VNS 消费当前选择视图。观察报告同时给出成员的 `raw_objectives` 和 `selection_objectives`。这里不挂 Pareto 档案：同 Project 的 `directions` Case 用无 Bias 的双目标问题单独展示原始 Pareto 语义。

## 候选从哪里来

建 Solver 时 SolutionPool 已存在，但没有候选，`ga.algorithm_unit` 也未创建。首次 GA 提案时，GA 按需建立空 Unit 容器并走 Solver / Pipeline 的初始化入口。`UniformInitializer(-0.2, 1.2)` 有意产生边界外值，使修复能在结果中被核对。

候选经过问题管线、控制面身份绑定和求值，只有接纳并提交后才成为可读的准确池版本和算法成员。空 Unit 容器可以先存在；这不代表它已经持有已求值成员，也不代表 Unit 构建是候选编码。

`population_size=6` 限制的是 GA 的工作种群，不是母池历史容量。精英池也只保存准确引用，没有复制另一个可写候选矩阵。

## 一轮实际做什么

装配入口表达的核心计划是：

```python
repeat(times=2, body=serial(
    stage("ga", steps=2, label="ga"),
    stage("vns", label="vns"),
    stage("ga", label="return"),
))
```

1. GA 首次阶段先评估 6 个初始候选，接下来一次普通完整 change 交付后代。`crossover_then_mutate` 接收精确父代副本，先算两名互补交叉孩子，再各自添加高斯扰动，一次返回至多两个 `ChangeResult`。控制面逐孩子派生身份，预算裁剪后统一 repair / evaluate。
2. GA 的普通生存函数接收当前 offered Pool，按硬违反量优先、选择成本次之选出 6 个成员。它从这些成员中再选 2 个精英，通过 `Pool(parent=members, name="elite")` 与 `inject(..., replace=True)` 交付具名集合。主成员和副集合在同一提交事务发布；精英是最终成员的子集，不是所有刚被接纳后代的子集。
3. VNS 的 `PoolTaskSpec` 使用选择函数读取准确 `elite` 引用，`count="all"` 明确逐成员处理。每个种子精修 2 个实际步骤；终点优于起点时保留改进，否则可仍交付起点。
4. 返回阶段用 `get_pool_task_results(..., "vns")` 取得本轮明确选中的最终结果，让 GA 重新评价并竞争。它不把 `refined` 累积试探档案当作最终结果；不是把 VNS 的 Unit 或数值评分直接塞进 GA。
5. 第二轮继续原 GA Unit 和成员年龄，重新启动本轮 VNS 任务请求。阶段名相同也由 SearchPlan 的稳定激活身份区分请求。

默认完整流程合计 14 个提交与 36 次求值。`max_steps` 留出一次空控制尝试来报告计划完成，该尝试不制造额外逻辑代。若 `evaluation_budget=11`，实际运行只消耗 11 次求值、提交 2 步，计划仍未完成；预算终止不会伪装成所有阶段已经结束。

## Unit 扩展不改 GA 源码

`RecipePopulation` 继承 `PopulationUnit`，仅增加 `member_age` 行字段和 `on_members_changed(change)`。对新成员赋 0，对原成员按 `previous_member_indices` 找回旧年龄；环境选择保留下来的旧成员加 1。GA 不需要知道年龄字段的维护规则。

`RecipePopulationBuilder` 复用标准 Unit builder 的显式数据 codec；`UnitBinding` 在所属 Adapter 实际需要时构建。checkpoint 恢复已有 Unit 时走 codec，不重新调用初始化器来凑出相同数值。

## 谁负责什么

`BudgetController` 负责运行求值预算；只有 Project 传入的 `ResourceContext` 提供 L0 授权。Case 不自行创建全局线程租约。

`RecipeProvider.can_handle_*` 命中意味着它承诺交付合法结果；它按相同公式向量求值，不调用 `Problem.evaluate`。Provider 本身是正式评估提供者，不是为了演示而改写 Plugin 生命周期。

`WorkbenchTrace` 观察已提交步骤，不调用 `ensure_unit()`。它声明 `ParticipationContract(vetoes=("finalization",))`，在最终事务提交前核对 Authority 引用的池 manifest 与当前池一致，并检查最终候选满足问题约束。检查失败会阻止整组最终产物发布。

通过正式 Case 运行、存在 Artifact publisher 时，它在既有 `case_finalization` 事务中暂存 `summary`。这个 Artifact 的报告字段 `raw_objective_recomputed` 是纯公式重算，`raw_objective_source` 明确标成 `analytical_recomputation_for_report`；它不是 durable raw receipt。准确成员原始证据来自 `SolutionPool.read_raw_feedback(refs)`，保存在 trace 观察记录中。

## 检查点与观察计数

`CheckpointResumePlugin` 定期保存并在结束时发布最终检查点。本例保存路径属于本地 trusted roots，默认不启用需要 HMAC 配置的 strict 认证模式；不要把本例文件当作可任意接收的不可信输入。

`RecipePipeline` 显式序列化实际使用的 initializer / mutator RNG 和 repair 计数，`WorkbenchTrace` 序列化有界 JSON 观察，Adapter / Unit / Pool 使用框架自己的恢复协议。这是本例声明的 codec，不是框架自动递归保存任意 Python 对象图。

默认 `repair.calls=42`：6 次发生在 Pipeline 初始化入口自带修复，36 次发生在规范的送评前修复；`changed>0`。这些计数仅用于观察，不参与算法选择。正式恢复测试校验了随机状态、计数、Unit 年龄和后续候选/目标轨迹一致；恢复不重放初始化和既有求值。

## 可复现验证

仓库根目录运行：

```powershell
python -m pytest tests/test_assembly_workbench_hybrid.py -q
```

测试覆盖 Problem / Provider 两种模式、真实阶段与精确引用、偏好和 raw 分离、硬预算截断、显式管线 codec 恢复，以及复制 Project 后通过正式 L0 / Case 执行获得带权威发布收据的 summary。测试输出进入临时目录，不覆盖默认示例结果。
