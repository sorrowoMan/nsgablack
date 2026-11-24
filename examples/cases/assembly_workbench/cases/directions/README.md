# directions：方向投影 → VNS → Pattern Search → MOEA/D

这个 Case 演示同一个解池内的算法装配。MOEA/D 自动创建三份方向视图；VNS 按各自冻结的方向精修；Pattern Search 再从 VNS 的最终选择出发；最后由原来的 MOEA/D 实例重新求值、按自己当前的方向规则竞争替换。

它没有创建内层 Case、额外 Solver 或额外资源授权。Project 负责 Case 与 L0；Case 内的 `SearchPlanAdapter` 只安排算法实例何时工作。

## 最值得看的装配

`adapter/composition.py` 中，流程只有四个位置：

```python
serial(
    stage("moead", steps=2, label="search"),
    stage("coarse"),
    stage("fine"),
    stage("moead", label="return"),
)
```

`moead` 两次出现仍是同一个算法实例、同一个 Unit。第一次完成种群初始化和一次原生搜索；第二次消费外部精修结果，执行自己的比较替换。

VNS 与 Pattern Search 共同使用 `PoolTaskSpec(..., count=1, steps=2, output=None)`。每个起点先实际评估基准，再完成一次邻域更新；这里的 `steps=2` 是每个起点的任务预算。外层精修位置不写固定 steps，它等整批方向任务完成。

两层任务的输入分别是：

```python
subpools.all(moead)       # MOEA/D 实例创建的方向视图
subpools.all(coarse)      # VNS 实例创建的最终选择视图
```

`direction_sample=2` 时，第一个输入改为 `subpools.random(2, moead)`。这里随机取的是两份方向视图，每份再取一个起点；它不是从根池随便取两个候选，也不会把另一个同类型算法创建的视图混进来。

## 问题、投影和结果是什么

Problem 的原始目标始终是 `[(x-1)^2, (x+1)^2]`。问题管线只有边界修复 `ClipRepair(-2, 2)`。MOEA/D 的初始化和变异、VNS 的高斯邻域、Pattern Search 的坐标轮询都由各自算法实例拥有。

本例使用 Tchebycheff 分解。每份方向视图携带 `weights` 与 `reference`。任务开始时冻结它们，VNS 的基准和邻域使用同一比较框架；Pattern Search 继承相同投影，不对已经标量化的反馈再投影。池里的 raw feedback 始终保留两个目标。

`output=None` 表示不另建一个累计保存全部接纳试探的聚合历史池。每个精修任务仍发布最终选择视图；`fine_results()` 通过正式接口：

```python
control.adapter.get_pool_task_results(control, "fine")
```

取得本轮最终候选的精确 `SolutionRef`，交给 MOEA/D 的 `compete` 输入。结果 getter 核对任务的视图身份、修订、解释和有序成员。它不按名字猜结果，也不把某次未被局部算法选中的试探当作最终精修结果。

## 可直接改的地方

- 修改 `direction_sample`，选择全部方向或抽样方向。
- 修改 `local_steps`，改变每个起点的局部更新预算。
- 修改 coarse 实例的 `ContextGaussianMutation`，改变 VNS 邻域。
- 用另一个支持投影精修的 Adapter 替换 fine 实例，保留相同的池任务与返回装配。
- 修改 Problem 或共享问题修复；不必为每个 Adapter 复制一条 Pipeline。

共享任务装配不等于共享变异接口。VNS 支持装配普通变化函数或 mutator；本例的 Pattern Search 使用自己 Unit 中的坐标轮询结构，没有声明通用 `change` 绑定。替换算法时保留的是输入、结果和调度契约，各算法仍明确自己支持的操作。

本例只安排一轮。`subpools.all(coarse)` 的含义是该实例所有当前已发布视图；如果以后把全段放入 repeat，必须明确旧结果视图的保留与本轮选择范围，不能把 `all` 误解为“自动只取本轮”。

## 标准入口与参数

`build_solver.py` 是唯一装配入口：

```python
build_solver(
    config={"direction_sample": 2, "output_dir": "..."},
    resource_context=project_grant,
    component_overrides={...},
)
```

Project 通过正常配置注入资源，Case 不创建 lease。独立 Case 使用同目录 `run_solver.py` 的标准 CLI，`build_trainer.py` / `run_trainer.py` 只是别名。Project 级运行方式见上层 README。

默认观察文件位于 Project 的 `results/directions/`；可通过 `config.output_dir` 改写。`trace.json` 顶层记录实际 Solver run_id，用来同 Project Case 身份对账。`summary.json` 同级输出精简后的最终证据。

## 运行后逐项看什么

默认全部三方向应完成 **15 次提交、24 次实际求值**：

- MOEA/D 搜索 2 次提交，3 个初始化候选和 3 个原生变化候选，共 6 次求值。
- coarse VNS 共 6 次提交，每方向基准 1 次、邻域 1 次，共 6 次求值。
- fine Pattern Search 共 6 次提交，每方向基准 1 次、正负轮询 2 次，共 9 次求值。
- 返回同一个 MOEA/D，3 个最终选择在 1 次提交中重新求值，共 3 次。

`direction_sample=2` 时应完成 **11 次提交、18 次求值**。这些数字适用于本例默认其它参数，不是框架通用配额。

## 同一套接口的并行变体

`refinement_layout="parallel"` 把两层精修改为 `multi(stage("coarse"), stage("fine"))`。VNS 与 Pattern Search 都从 MOEA/D 的方向视图取起点，分别冻结相同来源的方向比较；它们互不消费对方的结果。待两个任务都完成，返回函数按 coarse、fine 顺序合并双方的精确最终引用，交给原 MOEA/D 实例竞争。

这是同一 Solver 内并行推进两个搜索分支，不是声明两个线程或新申请资源。默认 `router_budget=6` 容纳两分支的完整提案和六个最终返回；每个真实候选仍各自实际求值。默认三方向并行变体完成 **9 次提交、27 次求值**：bootstrap 6 次、VNS 6 次、Pattern Search 9 次、六个最终结果返回重评 6 次。它与默认串行场景表达不同算法，不是同一结果的加速运行。

串行 fine 的 parent 是 coarse 最终视图，ancestors 含 MOEA/D 方向身份；并行 coarse 与 fine 的 parent 都直接是 MOEA/D 方向。`summary.refinement_layout`、`returned_roles` 和每步 `phases` 明确区分这两种关系。

轨迹还包括：

- 激活前各 Unit 仍未创建；方向视图、coarse 与 fine 各自不同的实例来源路径。
- 每个已提交步骤的实际阶段、求值增量、逻辑时钟和精确接纳引用。
- 最终视图的 parent、ancestors、view_id、revision，以及冻结投影。
- coarse 与 fine 的任务结果收据；fine 最终返回引用。
- 最终 MOEA/D 成员与原始双目标反馈，以及 `ParetoArchivePlugin` 的档案。

在正式 Case Runtime 中，DirectionTrace 的 `on_solver_finalization_prepare` 还会把同一份精简汇总暂存到共享 `case_finalization` 事务，名称为 `summary`。全部严格发布检查通过并完成 Case 封印后，Project 才获得可交给其他 Case 的 `directions.summary` ArtifactBinding。它复用现有事务与结果收集机制；没有额外 wrapper 或独立提交。

本地 JSON 文件仍是观察报告，不替代这个 Artifact 或发布收据。直接构造 Solver、没有 Case Runtime 时只输出本地观察，不假装存在权威跨 Case 发布。定向行为测试还会解析重算双目标、核对层间投影不漂移、fine 结果不劣于同方向 coarse 起点。小规模运行用于核对装配与交接，不证明算法性能优越性。
