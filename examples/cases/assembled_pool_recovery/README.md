# 完整 Project：SA 准备解 → NSGA-II 与 SPEA2 → 停滞唤醒 SA → 返回竞争

详细代码阅读：[项目全部源码](PROJECT_CODE.md) · [框架组件源码索引](COMPONENTS.md) · [四种完整装配对照](../ASSEMBLED_PROJECTS_GUIDE_CN.md)。

这个项目专门回答三个实际装配问题：起始候选由另一个算法产生时怎样分给两个种群；两个种群怎样维护自己的 Unit；停滞后如何重新启动单轨迹算法，并把它的候选交回种群选择。

它是真正的标准 Project，只有一个独立 Case。算法状态机直接复用框架的 `PoolSearchAdapter`，没有在运行脚本里编写另一套搜索循环。

**本例用于验证交接与恢复流程，不用于证明优化收益。初始点就在目标值为零的最优平坦区，后续停滞是目标度量不再严格改善。SA 被唤醒不等于跳出了次优局部极小，也不保证最终解质量提高。**

## 1. 从哪里开始看

建议先顺着以下四个文件阅读，再打开轨迹：

1. [Project 的阶段与 L0](project_config.py)：唯一资源授权入口。
2. [Case 装配入口](cases/pool_recovery/build_solver.py)：把 Problem、问题 Pipeline、Adapter 和观察 Plugin 组装进 `ComposableSolver`。
3. [算法装配](cases/pool_recovery/adapter/composition.py)：真正决定 SA、两个种群、起点配额、停滞阈值与恢复长度。
4. [实际运行结果](RESULTS.md)：真实的八次提交与二十九次求值。

[全部代码快照](PROJECT_CODE.md) 与 [组件源码索引](COMPONENTS.md) 供按组件检查。可执行文件始终是事实源，快照是阅读附件。

## 2. 运行命令

在本 Project 根目录执行：

```powershell
python run_project.py --check --build-check
python run_and_report.py
python run_and_report.py --report-only
```

第一条只装配检查，不求解；第二条调用正式 `execute_project` 并生成报告；第三条只核对已经保存的正式结果与同一运行的轨迹。

正式 Case 自己也保留独立入口：

```powershell
python cases/pool_recovery/run_solver.py
```

独立入口走共享标准 Case CLI。若要生成本 Project 的正式 `project_result.json` 和教学报告，使用 `run_and_report.py`；直接运行 Case 后留下的轨迹不能冒充之前的 Project 结果，本例用运行身份拒绝混用。

在框架仓库根目录检查：

```powershell
python -m nsgablack project doctor --path examples/cases/assembled_pool_recovery --strict --build --catalog-audit --profile framework-core --format json
```

Doctor 检查装配与受支持契约，不能证明搜索算法数学性质；真实运行轨迹是另一份验证。

## 3. 标准目录

```text
assembled_pool_recovery/
  project_config.py
  run_project.py
  run_and_report.py
  _bootstrap.py
  README.md
  RESULTS.md
  results/
    project_result.json
    summary.json
    trace.json
    trace.csv
    doctor.json
  cases/
    __init__.py
    pool_recovery/
      __init__.py
      build_solver.py
      build_trainer.py
      run_solver.py
      run_trainer.py
      config.py
      problem/
        plateau.py
      pipeline/
        main.py
      adapter/
        composition.py
      plugins/
        trace.py
      catalog/entries/
        components.toml
      bias/__init__.py
      evaluation/__init__.py
      runtime/__init__.py
      solver/__init__.py
```

所有实际自定义组件都在本 Case 内。没有从其他 example 导入胶水，也没有复制框架的 PoolSearch 状态机或通用运行时实现。空包只保留标准职责位置，不表示装了一个无效 Bias 或 Provider。

`build_trainer.py` 与 `run_trainer.py` 是规范的薄别名；本 Case 的语义仍然是 solver。正式装配只在 `build_solver.py` 一处。

## 4. Problem：为什么选平坦区

[PlateauProblem](cases/pool_recovery/problem/plateau.py) 定义二维候选 `x=[x0,x1]`：

```text
minimize f(x) = max(0, x0² + x1² - 1)
subject to -2 <= x0,x1 <= 2
```

单位圆内部的点均为全局最优点，原始目标是零；圆外原始目标增加。问题的可行域是整个盒子，不能把“在单位圆外”误叫不可行。盒约束由独立的 `evaluate_constraints` 定义原始违反量。

初始 SA 使用 `UniformInitializer(-0.15,0.15)`，所以初始点位于最优平坦区域。变化尺度只有 `0.04`。这让小配置在固定随机种子下稳定出现真实的零改善度量，从而演示恢复机制。

没有自定义常量 metric，没有把“到了第五步”伪装成停滞，也没有让 Plugin 强制切换阶段。状态机消费真实反馈。

这里不装 Bias；因此没有额外软评分。报告仍按正式接口使用 `best_selection_objectives` 命名，避免以后加入 Bias 后把选择视图误标成 raw evidence。

## 5. Pipeline 只负责共同的问题修复

[pipeline/main.py](cases/pool_recovery/pipeline/main.py) 只有：

```python
RepresentationPipeline(repair=ClipRepair(low=-2.0, high=2.0))
```

`ClipRepair` 是框架现有组件，负责把候选夹回问题盒约束。它不创建 Unit，不决定种群成员，不负责 SA 接纳，也不触发恢复。

初始化和变化方法直接装在各自的实际叶 Adapter 上：SA 拥有自己的 initializer 与 context-aware mutator；两个种群各自拥有独立 GaussianMutation。三个有状态算子实例没有复用同一 RNG 对象。

`--check --build-check` 的顶层 `initializer`／`mutator` 字段仅概括问题 Pipeline，所以这里可以显示 `None`。这不表示叶 Adapter 未装算子；实际绑定见 composition.py 和各叶的 `get_operation_contract()`。检查输出中的 Adapter 树会列出 SA、NSGA-II、SPEA2。

## 6. Adapter 树与 Unit 归属

```text
PoolSearchAdapter(name="pooled_search")
  SimulatedAnnealingAdapter(name="seed_and_recovery_sa")
  NSGA2Adapter(name="population_a")
  SPEA2Adapter(name="population_b")
```

SA 持有自己的 TrajectoryUnit；NSGA-II 和 SPEA2 各持有自己的 PopulationUnit。即使两个算法使用兼容的 PopulationUnit 类型，它们也不是共享同一个可写种群，更不共享排名。

配置阶段先构造 Adapter 实例。Solver 先建立 SolutionPool，再执行 Adapter 初始化／候选操作。builder 在装配时只是构建能力，实际 Unit 在首次使用时创建。

初始轨迹中三者都没有 Unit。准备种子时只有 SA 被调用，所以两个种群继续保持未创建。直到它们第一次消费池输入才创建种群 Unit。

根 Adapter 使用 partitioned population authority；不能把两群拼成一个六行矩阵后声称那就是一个算法的种群。

## 7. 默认参数各自控制什么

[DemoConfig](cases/pool_recovery/config.py) 默认参数为：

- `seed=23`：搜索与独立叶随机流的可复现起点。
- `max_steps=8`：只限制成功提交的逻辑步。
- `initial_count_per_population=3`：每个搜索器第一次从准备结果取三个起点。
- `population_size=3`：每个种群 Unit 最多保留三个成员。
- `offspring_size=2`：正常搜索时每个种群生成两个后代。
- `producer_batch_size=3`：SA 已建立基准后每次提出三个邻域候选。
- `stagnation_steps=1`：已有最佳度量后，连续一次搜索提交没有严格改善即唤醒恢复。
- `recovery_steps=2`：一次起点基准送评，再一次邻域搜索。
- `sigma=0.04`：本例局部变化尺度。

这几个数不能合并成“池容量”。母池没有被限制成六个或三个解。初始取解配额、算法容量、后代批量和求值数是不同概念；本例恰好将两个取解配额设置为与各自容量相等，便于手算。

## 8. preparing：SA 怎样产生六个可分配起点

目标是准备至少 `3+3=6` 个已接纳候选。SA 第一次先送评自己的起点，不能把邻居的分数借给起点。

因此前三次提交实际分别求值：

```text
step 1: 1 个 baseline       累计 prepared_count=1
step 2: 3 个邻域候选        累计 prepared_count=4
step 3: 3 个邻域候选        累计 prepared_count=7
```

SA 每次可以只选择一个当前点，但三个已评估、被控制面接纳的提案都会进入池。准备数量统计接纳提案，不是“SA 最后走过几个 current”。

达到至少六个后切到 search。最后一批完整接纳造成七个准备候选，这是允许的超额；不伪装成严格只有六个。第七个没有被这次初始配额使用，仍在池中。

## 9. search：两个种群如何获得不同输入

`PoolSearchAdapter` 在第一次 search 时固定准备时点，并从自己的来源候选按记录位置分配：前三个给 population_a，随后三个给 population_b。不同种群的初始源引用不重叠。

池读取保留源版本，跨算法输入产生新提案身份并携带 `solution_source_ref`／parent_token。接收算法正常执行问题 repair、求值和接纳，而不是直接相信 SA 的选择评分。

`trace.json` 保存第一次种群安装后的精确成员引用及其 provenance；`summary.json.initial_source_allocations` 提取六个源版本，并实际核对互不重复。这是引用对账，不是按数值相等猜身份。

第四步两个种群各评估三个种子，共六次求值。两者此时建立各自 Unit，分别选择成员。

第五步两个种群各生成两个后代，共四次求值。NSGA-II 继续自己的非支配排序／拥挤度逻辑；SPEA2 继续 strength＋density 选择。共享池不替代这两套生存选择规则。

“两个算法同一轮搜索”在这里是逻辑组合。根 Adapter 依次收集提案并路由反馈，不自动创建两个线程；本 Project 的 L0 授权为一个线程、一个 worker。

## 10. 停滞条件与恢复入口

本例不传自定义 metric，所以使用框架默认值：

```text
本次搜索批次度量 = min(sum(raw_objectives) + 1e6 * raw_violation)
```

它不是全局历史最优的重新计算，也不是数学上的局部最优证明。首次完整搜索输入结算后建立 `best_metric=0`；下一批仍为零，不能严格小于历史最佳，于是 `stagnation=1` 达到声明阈值。

第五步提交后，根 phase 变成 recovery。阶段转换本身属于算法状态机，不由观察 Plugin 决定。

默认恢复种子是根池区域当前来源中最后发布的候选。它不是自动取全局最优点，也不是自动取 SA 原来的 current。如要指定精英、特定分区或业务选择，应给正式 `recovery_selector(pool, timestamp)` 返回一个精确引用。

## 11. recovery：复用同一个 SA 实例，但重启它的搜索

`restart_recovery=True` 意味着复用已经装配的 SA 对象并调用其正式 `restart_search`。不会重放整个 Solver 生命周期，也不会新建另一个资源授权者。

SA 的 current／分数／任务结果状态重置，温度重新设为 `0.4`；运行内随机流继续向前，不倒回初始种子。

第六步先把选中的池种子重新送评，建立这个恢复任务自己的基准。真实轨迹中此时温度仍为 `0.4`。第七步才提出三个邻域候选，并执行 Metropolis／降温。

本例的 `recovery_steps=2` 包含 baseline 这一步，所以不是“两次邻域搜索”。第七步提交后 phase 变成 return。

## 12. return：返回什么，由谁决定替换

根 Adapter 取恢复开始时间之后由本组合发布的候选版本。本轮是一个 baseline 加三个邻域提案，共四个。

它们不保证每个都比起点更好；也不只限 SA 的最终 current 或 task-best。这是 PoolSearch 当前的恢复返回策略：将恢复期间产生的候选交给种群竞争。

第八步把同一组四个来源候选分别以 compete 输入交给两个搜索器。两个接收方都重新评估，所以本步是 `4+4=8` 次求值。它们产生各自的新提案身份，并以各自生存规则与旧成员竞争。

返回不会强制覆盖某个成员，不保证 SA 候选成为最终成员，也不要求两个算法作出相同选择。双方最终仍各保留三个成员。

第八步提交后 phase 回到 search；`max_steps=8` 恰好结束这次演示。因此最后一行 `executed_phase="return"`，而 `phase_after="search"`，两者并不矛盾。

## 13. 二十九次求值逐步对账

```text
step   executed_phase   evaluation increment   total
1      preparing        1                      1
2      preparing        3                      4
3      preparing        3                      7
4      search           6                     13
5      search           4                     17
6      recovery         1                     18
7      recovery         3                     21
8      return           8                     29
```

返回阶段的八次求值不能省略不报；共享候选值不意味着可以把另一个算法的选择反馈直接挪过来。报告对账使用正式 Case 的 evaluation_count 和提交轨迹，发生不一致就失败。

## 14. Plugin 与报告分别做什么

[PoolTracePlugin](cases/pool_recovery/plugins/trace.py) 只观察：

- `on_solver_init`：记录尚未激活的 Unit。
- `on_step_attempt_start`：捕获本次真正要执行的 phase。
- `on_generation_committed`：记录成功提交后的 phase、度量、温度、Unit、精确成员引用与来源。
- `on_solver_finalized`：在结果权威发布后写出 trace JSON／CSV。

只读观察不调用 `ensure_unit()`。记录容量显式绑定 `max_steps`；codec 只保存 JSON 数据，不复制锁、Provider session 或 Adapter 对象图。

[run_and_report.py](run_and_report.py) 通过 `execute_project(ROOT)` 获取正式结果，检查 Case 成功、运行身份、八步执行顺序、冷态 Unit、停滞触发、SA 基准、独立初始分配、最终容量、二十九次求值与有效 L0 绑定。它只整理结果，不参与搜索控制。

这份报告器刻意验收默认教学配置；更改步骤和配额后应相应调整验收预期。想运行其他合法参数可直接用标准 Case 入口／builder，不应把旧的固定二十九次验收当作框架限制。

## 15. 状态、持久化与证据的实际边界

SolutionPool 存不可原位改写的候选版本和原始反馈；Unit 存当前算法工作投影与关系。PoolSearch 保存自己的 phase、配额输入、停滞计数和恢复开始逻辑时间。三个子 Adapter 作为独立事务子参与者保存各自状态。

本例复用已有步骤事务与共享 SnapshotStore，没有实现第二套回滚。失败后已发生的求值成本不会假装未发生。

观察 Plugin 有显式状态 codec，但本例没有额外装 checkpoint Plugin，也没有声称实际演示过崩溃恢复。`restart_search` 是算法搜索重启，不是进程 checkpoint 恢复，两者须分开理解。

轻量报告保存在 results；Project 的完整运行元数据／Artifact authority 放在 `.blackbase/`，由 `.gitignore` 排除。只复制 summary.json 无法保证别的机器能读取所有历史 Snapshot 引用。

本例没有显式启用 PoolRetentionPolicy，因此不演示闲置候选物理回收。不能仅因为池支持回收就声称本运行测量了回收效果。

## 16. 如何修改组合

换搜索器：修改 composition.py 的 searches。PoolSearchSpec 要求搜索器明确支持 initialize 与 compete；NSGA-III 可沿此路径替换，DE 当前不能直接替换，因为其外部候选要定义 target 配对。

换恢复算法：producer 同时承担 preparing 和 recovery，须显式支持 initialize 与 search restart。VNS 等满足声明的算法可作为候选，但它的 batch 与 neighborhood 含义不同，要重新计算演示预算。

换恢复起点：给 PoolSearchAdapter 传 recovery_selector，返回一个准确 SolutionRef。默认“最新”不是精英选择。

换停滞口径：传 metric(feedback)，明确使用 raw 还是 selection，保证有限返回值，文档说明它测量的是哪种改善。不要把容差比较、分桶分数和原始目标严格改善混为一谈。

延长运行：提高 max_steps 后状态机会再次经历 search／recovery／return，不是运行到八步就永久禁用 SA。观察器容量随 max_steps 调整，报告器默认阶段断言需要同步调整。

需要 MOEA/D 方向投影精修时，应看专门的投影子池 Project，而不是把本例 latest-seed recovery 解释成方向任务。

## 17. 本例能够证明与不能证明的内容

本例真实验证：正式 Project L0 生效；SA 提案作为初始池来源；两个种群读取不重叠的初始源版本；Unit 按需创建；真实 raw 度量触发恢复；同一个 SA 对象重启后基准先送评；恢复提案由两个种群分别竞争；结果与求值计数可对账。

本例不证明：性能优于单算法；SA 跳出了次优局部极小；所有算法均支持任意池竞争；逻辑多算法就是线程并发；所有历史存储都可以无限保留且零成本；实际执行过 checkpoint 恢复或故障回滚。

完整源码链接和结果保留了这些边界，方便你按“我要换哪个组件”判断实际修改面。
