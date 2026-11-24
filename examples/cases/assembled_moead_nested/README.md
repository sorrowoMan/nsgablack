# 完整 Project：MOEA/D 方向视图 → 粗 VNS → 细 VNS → MOEA/D 返回竞争

详细代码阅读：[项目全部源码](PROJECT_CODE.md) · [框架组件源码索引](COMPONENTS.md) · [四种完整装配对照](../ASSEMBLED_PROJECTS_GUIDE_CN.md)。

这个例子专门回答：**MOEA/D 自动建立的方向，如何变成另一个算法能消费的搜索任务？精修结果如何再次精修，最后怎样交回 MOEA/D？**

它是可运行的标准 Project，不是伪代码，也没有把 MOEA/D 或 VNS 的实现复制进项目。默认真实运行完成 **29 步、63 次求值**；完整结果见 [RESULTS.md](RESULTS.md)。

## 1. 从哪里读

推荐顺序：

1. [问题定义](cases/direction_refinement/problem/two_targets.py)：候选是什么、两个原始目标是什么。
2. [算法组合](cases/direction_refinement/adapter/composition.py)：三个实际算法实例、两次 `subpools.all(...)`、阶段完成屏障。
3. [Case 装配入口](cases/direction_refinement/build_solver.py)：Problem、共享问题 Pipeline、Router 和 Plugin 进入一个 Solver。
4. [Project 配置](project_config.py)：Case 执行与 L0 授权。
5. [真实结果](RESULTS.md)、[精简 JSON](results/summary.json)。
6. [观察组件](cases/direction_refinement/plugins/trace.py) 和 [报告程序](run_and_report.py)：每项结论如何由实际运行数据核对。

## 2. 完整目录

```text
assembled_moead_nested/
  .gitignore
  _bootstrap.py
  project_config.py
  run_project.py
  run_and_report.py
  README.md
  RESULTS.md
  results/
    project_result.json
    trace.json
    summary.json
  cases/
    __init__.py
    direction_refinement/
      .case
      __init__.py
      build_solver.py
      build_trainer.py
      run_solver.py
      run_trainer.py
      config.py
      catalog/entries/
        problem.toml
        plugin.toml
      problem/
        __init__.py
        two_targets.py
      pipeline/
        __init__.py
        main.py
      adapter/
        __init__.py
        composition.py
      plugins/
        __init__.py
        trace.py
      bias/__init__.py
      evaluation/__init__.py
      runtime/__init__.py
      solver/__init__.py
```

`.case` 声明 `kind=solver` 与 `framework=nsgablack`。`build_solver.py` 是唯一装配入口；Trainer 命名入口只是标准薄别名。本例没有 ML Trainer，别名文件存在不代表运行了训练。

`bias/`、`evaluation/`、`runtime/`、`solver/` 保留标准扩展位置，本例没有为填满目录而新增组件。没有额外 Bias，没有外部 Evaluation Provider，没有另写求解器循环，也没有 ML 依赖。

`.blackbase/` 保存标准 Project 的执行、资源与 Artifact 数据，已忽略进 Git。`results/` 保留本例的小型教学报告；复制这些报告并不等于搬运了每个权威引用的全部底层存储。

## 3. 先把数学问题看清

候选只有一个数 `x`，边界是 `[-2, 2]`。Problem 返回两个要最小化的目标：

```python
f1 = (x - 1) ** 2
f2 = (x + 1) ** 2
```

例如：

- `x=-1`：原始目标是 `[4, 0]`。
- `x=0`：原始目标是 `[1, 1]`。
- `x=1`：原始目标是 `[0, 4]`。

这不是一个只有单一最优点的问题。整个区间 `[-1,1]` 上的点都处在解析 Pareto 前沿上：向一个目标改善会损害另一个目标。区间之外的点被边界处的前沿点支配。

本例取 MOEA/D 的六个权重方向。用权重 `[w1,w2]` 看一个方向时，比较函数是：

```python
g(x) = w1 * (x - 1)**2 + w2 * (x + 1)**2
```

该方向的解析最优点是：

```python
x_star = (w1 - w2) / (w1 + w2)
```

所以 `[0.2,0.8]` 偏好 `x=-0.6`，`[0.8,0.2]` 偏好 `x=0.6`。报告给出这些解析最优点，方便核对方向语义；很少的邻域尝试并不保证已经找到它们。

MOEA/D 对极端权重做了数值保护，所以实际记录的端点约为 `[1e-12,1]` 与 `[1,1e-12]`，不能在身份或结果核对时擅自改写成另一个精确值。

## 4. Problem 与‘方向问题’没有混在一起

`TwoTargets.evaluate()` 永远返回原始二维目标。

方向视图携带 `ObjectiveProjection(method="weighted_sum", weights=..., reference=[])`。本例不用 Tchebycheff，因而没有 ideal/reference 向量参与标量化；这也是元数据中的 `reference` 为空列表的原因。

粗 VNS、细 VNS 在自己的任务边界消费投影后的选择分数。池和评估证据仍保存 `[f1,f2]`，原始约束违反量也不变。

这里没有把 Problem 替换成另一个持久 Problem 对象，也没有把母池中的二维目标覆盖成一列标量。**同一候选可以在多个方向下被解释，各方向共享候选值与身份引用，比较坐标分别冻结。**

## 5. 全部实际组件及代码在哪里

本项目自定义内容都在上述目录中；复用组件直接链接到框架的权威实现：

- `TwoTargets`：[problem/two_targets.py](cases/direction_refinement/problem/two_targets.py)。只定义目标与约束。
- `RepresentationPipeline`：[representation/base.py](../../../representation/base.py)。共享问题管线门面。
- `ClipRepair`：[representation/continuous.py](../../../representation/continuous.py)。所有角色统一裁剪到 `[-2,2]`；不做方向选择。
- `UniformInitializer`、`GaussianMutation`、`ContextGaussianMutation`：同一 [continuous.py](../../../representation/continuous.py)。初始化/变化在实际叶 Adapter 上装配。
- `MOEADAdapter`：[adapters/moead/adapter.py](../../../adapters/moead/adapter.py)。拥有权重、邻居、ideal、种群和替换决策。
- `VNSAdapter`：[adapters/vns/adapter.py](../../../adapters/vns/adapter.py)。粗、细是两个独立实例，分别维护当前候选及邻域状态。
- `DecompositionUnitBuilder`、候选/邻域 Unit builder：[representation/structure_builders.py](../../../representation/structure_builders.py)。由算法默认 `UnitBinding` 使用，不在 Project 提前构造运行结构。
- `StrategyRouterAdapter`、`RoleSpec`、`MultiStrategyConfig`：[adapters/multi_strategy/adapter.py](../../../adapters/multi_strategy/adapter.py)。阶段、激活角色、每次提案预算与反馈路由。
- `PoolTaskSpec`、`PoolTaskAdapter`：[adapters/pool_tasks.py](../../../adapters/pool_tasks.py)。冻结输入、逐起点任务、重启、结果视图和返回交付。
- `subpools`：[adapters/subpools.py](../../../adapters/subpools.py)。按实际实例所有权路径选择发布视图。
- `SolutionPool`：[core/state/solution_pool.py](../../../core/state/solution_pool.py)。候选版本、精确引用与命名视图。
- `ObjectiveProjection`：[core/state/pool_views.py](../../../core/state/pool_views.py)。将同一份新反馈解释为任务的选择分数，并保留 raw。
- `ComposableSolver`：[core/composable_solver.py](../../../core/composable_solver.py)。正式控制面、评估和提交。
- `ParetoArchivePlugin`：[plugins/runtime/pareto_archive.py](../../../plugins/runtime/pareto_archive.py)。归档已提交种群；不替 MOEA/D/VNS 决策。
- `NestedTrace`：[plugins/trace.py](cases/direction_refinement/plugins/trace.py)。读取实际任务、Unit 与视图状态，最终输出观察 JSON。
- Project façade：[project/project_runner.py](../../../project/project_runner.py)。委托共享 BlackBase Project/L0，不在示例重新实现编排。

`adapter/composition.py` 只是把这些组件连接起来，不包含 MOEA/D 或 VNS 的算法实现副本。

## 6. 三个算法实例如何装配

MOEA/D 的关键配置：

```python
MOEADAdapter(
    name="directions", population_size=6, batch_size=3,
    neighborhood_size=3, decomposition="weighted_sum", random_seed=23,
    initializer=UniformInitializer(low=-2.0, high=2.0),
    mutator=GaussianMutation(sigma=0.3),
)
```

六个槽位就是六个方向。种群容量属于这个算法，不是母池容量。`batch_size=3` 是 MOEA/D 正常搜索时一次处理的子问题数，也不是线程数。

两个 VNS 分别使用 `base_sigma=0.35` 和 `0.08`，都设置 `batch_size=2` 与 `restart_on_stagnation=False`。

直接变异组件是 `ContextGaussianMutation`：它消费 VNS 当前邻域提供的上下文。两个 VNS 各持自己的组件对象；没有把一个有状态算子交给两个不同所有者共享。

本例不需要自定义 Unit。MOEA/D 默认的分解 Unit、VNS 默认的候选和邻域 Unit 已表达所需状态。配置实例和 builder 可以先存在；运行 Unit 在算法真正使用时创建。

## 7. 第一次 all：选 MOEA/D 生成的方向

```python
RoleSpec("coarse", coarse_vns, pool_task=PoolTaskSpec(
    subpools.all(moead), count=1, steps=2,
    output="coarse_proposals", shuffle=False,
))
```

`subpools.all(moead)` 的主语是“由这个 MOEA/D 实例发布的视图”。本例选六个方向视图。

`count=1` 的主语是“每个被选视图中的起点”。每个方向有一个槽位候选，本例每方向启动一项任务，所以共有六项粗搜任务。

一个 VNS 实例按队列逐项处理，不是瞬间创建六个独立 Solver。池任务每次显式重启它的算法搜索状态，以当前起点建立所需 Unit，生命周期与资源仍属于外层同一个 Solver/Case。

请求开始时冻结候选的 token+版本引用、方向权重及视图身份。后续 MOEA/D 方向视图发布新 revision，不会悄悄替换已排队任务的输入。

这里没有按类型名找算法，也没有把候选的生产者当成视图创建者。真实 `created_by` 是所有权路径，例如：

```text
nested_directions / 0:pool_task:moead:0 / 0:directions
```

路径中的位置和名字共同区分实例。两个 MOEA/D 同类型实例可以发布不同来源的视图。

## 8. 第二次 all：选粗搜的最终结果视图

```python
RoleSpec("fine", fine_vns, pool_task=PoolTaskSpec(
    subpools.all(coarse_vns), count=1, steps=2,
    output="fine_proposals", shuffle=False,
))
```

这是递归精修的关键：第二层读的是粗搜每项任务的**最终选择**，不是粗搜最后一次试探解，也不是 `coarse_proposals` 中的全部途中候选。

每个粗搜结果视图携带父方向的身份、revision 与投影。细搜继承这套比较坐标，对本层新求值反馈应用一次。不能把已经标量化的一列数据再次按双目标权重投影。

细搜结果的父描述符指向粗搜结果，其祖先列表再保留 MOEA/D 方向。最终 `trace.json` 记录这条链，而不是只输出“嵌套成功”几个字。

子视图保存引用与解释，不复制整个候选数据树。父级在这里表示派生来源，不要求子视图的候选仍是父集合成员；细搜产生新解正是正常情况。

## 9. 为什么先后执行不是 all 自动决定

`subpools.all(...)` 只选择请求开始时已提交的视图，不会自动等待上游把所有任务做完。

因此本例在 `phase_policy` 明确设置屏障：

1. 前两步是 bootstrap，并且 MOEA/D 必须完成完整初始化。
2. 粗搜的池任务状态为 `done` 后才进入细搜。
3. 细搜为 `done` 后才允许 MOEA/D 返回竞争。
4. 返回任务为 `done` 后不再启动新任务。

`phase_roles` 保证每次只启用对应角色。这里是一个 Case 内的算法调度，不是 Project 多 Case DAG，也不是线程并行。

## 10. 两种输出必须分开看

每层 VNS 任务都有两类交付：

- **具名聚合集合** `coarse_proposals` / `fine_proposals`：保存本层过程中通过正式接纳的提案，包括重新评估的起点及邻域候选。
- **逐任务结果视图**：通过算法的 `get_pool_refinement_results` 取得该任务最后选中的候选；本例每层六个视图，每个有一个精确候选引用。

默认接纳策略接受所有合法求值行，所以每层六任务、每任务三次求值，共有 18 个聚合输出成员。局部算法最后可以只保留其中一个。

因此 `all(coarse_vns)` 选六个任务最终结果视图，而 `"coarse_proposals"` 是 18 个过程提案的集合。两者不是同义词，不能互换后还声称算法不变。

## 11. 结果如何交回 MOEA/D

```python
RoleSpec("moead", moead, pool_task=PoolTaskSpec(
    "fine_proposals", mode="compete", phases=("return",), shuffle=False,
))
```

bootstrap 阶段这个包装不拦截正常 MOEA/D 提案；到 return 阶段才开始取 `fine_proposals`。

返回不是直接覆盖某个方向槽位，也不是“x 找到了 y，所以把 y 的分数写给 x”。被交付的是实际候选版本。MOEA/D 对它重新执行正常修复、评估和自己的分解替换规则，按当前比较条件决定哪些槽位更新。

本例明确选择**把细搜的全部 18 个接纳提案返回竞争**。这包含中间提案，并不宣称只返回六个局部最终赢家。

当前接口要求创建者选择器 `SubpoolSelection` 使用 `mode="refine"`，所以不能把这段竞争输入直接改成 `subpools.all(fine_vns)`。若只想让六个最终结果竞争，需要显式收集这些已发布视图的精确引用，另定义清楚输入选择；不能靠改变 mode 静默绕过能力校验。

## 12. 每一步实际走什么路径

每次正式 Solver 步骤都沿同一条控制面路径：

```text
Router 选择角色与预算
→ PoolTask 冻结/推进输入，或让 MOEA/D 正常提案
→ 实际叶 Adapter 提案
→ 候选绑定 token / provenance
→ 预算裁剪
→ 共享问题 ClipRepair
→ ProposalRepair 回到原所有者对账
→ TwoTargets 求值
→ raw 双目标证据与任务选择投影分别保留
→ BatchDisposition
→ 原 Adapter 更新自己的 Unit
→ 池索引和 Authority Snapshot 提交
→ 提交观察与归档
```

失败路径由已有事务负责，已发生评估消耗不会因为 Unit 回滚而消失。示例没有用观察 Plugin 修改这些流程。

## 13. 默认预算如何算出 29 步与 63 次求值

`DemoConfig` 中的默认值是六方向、两步 bootstrap、每层每方向两步、每个邻域两个候选、Router 提案预算六。

实际运行的对账如下：

- bootstrap：第 1 步初始化六个候选，第 2 步 MOEA/D 变化三个候选，所以是 **2 步、9 次求值**。
- coarse：每方向第 1 步重新评估起点，第 2 步评估两个邻域，所以每任务 2 步/3 次求值；六方向共 **12 步、18 次求值**。
- fine：同样是 **12 步、18 次求值**。
- return：18 个细搜接纳提案，每步预算六，分三批交回，所以是 **3 步、18 次求值**。

合计 `2+12+12+3=29` 步，`9+18+18+18=63` 次求值。

`router_budget=6` 是每次分发的候选上限，不是解池容量，也不是把 VNS 的邻域强行补成六个候选。VNS 每次只生成自己配置的两个邻域候选。

## 14. 真实结果说明什么

这次固定种子 23 的运行中，细搜在六个方向上都没有比粗搜最终选择更差，其中五个方向严格改善，一个方向保留了粗搜结果。

例如：

- 接近 `[0,1]` 的方向：粗搜 x 约 `-0.955894`，细搜 x 约 `-1.029197`；方向分数从 `0.00194535` 降到 `0.000852448`。
- `[0.4,0.6]` 的方向：粗搜 x 约 `-0.985011`，细搜 x 约 `-0.890410`；方向分数从 `1.57624` 降到 `1.43667`。
- `[0.2,0.8]` 的方向：细搜保留 x 约 `0.963484`，远离解析方向最优点 `-0.6`。
- 方向 5 接近 `[1,0]`：细搜 x 约 `-0.652368`，同样明显偏离该方向解析最优点 `1`。这如实说明本例的极短搜索预算不保证收敛，也不证明 Pareto 前沿质量。

这些都是本次运行的结果，不是框架承诺的固定数值，也不是性能优越性的实验。

`RESULTS.md` 与 `summary.json` 保存所有方向；`trace.json` 保存更完整的身份与父子证据，最终 MOEA/D 种群也保留了二维 raw 目标。

## 15. 观察组件如何避免污染运行

`NestedTrace` 只读取已有对象，从不调用 `ensure_unit()`。初始化观察中三个算法都没有运行 Unit；bootstrap 时粗、细 VNS 仍未创建结构；coarse 阶段 fine 仍未创建。

每次 committed hook 记录：逻辑步数、累计求值数、phase、三个角色的 task_status、Unit 是否存在以及已提交结果视图名字。

最终发布后导出：

- 每个方向/任务的 `view_id/revision/created_by/parent/ancestors/projection`。
- 每个结果的完整 `SolutionRef`、候选数值与存储的 raw 反馈。
- 具名聚合输出的成员数。
- 最终 MOEA/D 有序成员的精确引用与 Adapter 内目标矩阵。

报告程序核对这些记录属于同一次正式 Case；不按数值相等反猜身份。解析重算只用于检查 raw 数据是否仍符合问题函数，不冒充新评估证据，也不增加求解器计数。

观察 JSON 是有界教学记录，其容量按本次 `settings.max_steps` 装配并纳入 codec 身份，不把可运行规模暗中限制在固定 128 步。它不替代权威 Snapshot、完整 Journal 或 Artifact 收据。Plugin 采用显式 JSON 数据 codec，不复制 Solver/Adapter 对象图。

## 16. 怎么运行与复核

在当前目录执行：

```powershell
python run_project.py --check --build-check
python run_and_report.py
python run_and_report.py --report-only
```

第一条只装配检查，第二条经正式 `execute_project()` 运行并生成报告，第三条核对上次正式返回和轨迹，不重新求解。

仅运行原始正式 Project 入口也可以：

```powershell
python run_project.py
```

但这条不会由报告程序额外保存 `project_result.json` 或重写 `summary.json`；随后要生成本例完整报告请运行 `run_and_report.py`，不要把旧正式返回与新轨迹混用。

Case 也保留独立标准入口：

```powershell
python cases/direction_refinement/run_solver.py --check
```

已实际执行并成功的验证：

- `python run_project.py --check --build-check`：退出 0，L0 绑定生效，实际组件树包含 MOEA/D 和两个 VNS。
- `python run_and_report.py`：退出 0，完成 29 次提交/63 次求值，报告内跨层核对全部通过，包括逐任务的基准/邻域实际求值增量。
- 仓库根执行 `python -m nsgablack project doctor --path examples/cases/assembled_moead_nested --strict --build --catalog-audit --profile framework-core --format json`：退出 0，**0 error、0 warning、10 info；19 completed、0 skipped**。完整诊断保存在 [doctor.json](results/doctor.json)。本地 Catalog 只索引本例自定义的 Problem 与观察 Plugin；内置组件继续使用框架索引，没有在 Case 重复注册。

标准 `--check` 的 initializer/mutator 字段目前主要展示 Pipeline slot。本例搜索组件直接绑定在叶 Adapter 上，所以这些顶层字段显示 `None`；不表示 MOEA/D/VNS 没有搜索组件。直接装配见 composition.py；严谨观察应读取实际 Adapter 的 operation contract。没有为了展示文本去把搜索组件重复装入共享 Pipeline。

## 17. 可修改点与明确边界

只改方向数、每层步数等规模参数，应改 `DemoConfig`，预算属性会重新计算；本例报告使用默认配置，若通过外部覆盖换配置，须同步让报告读取该次配置，不能沿用旧默认值宣称通过。

想改粗搜/细搜思想，先看接收算法是否声明池初始化、显式重启、最终结果交付和目标投影能力；不能因为算法有 Unit 就假定它能消费投影任务。

想加第三层，在细搜后新增一个实际实例，让它 `subpools.all(fine_vns)`，再明确增加完成屏障、输出、返回集合及逻辑步数。不是给路径字符串随便追加一级就自动获得正确调度。

想采用 Tchebycheff，可改 MOEA/D decomposition，但报告必须同时核对冻结 ideal/reference 并改用相应标量公式。这里的 weighted_sum 解析最优式不能照搬。

想让多个精修实例处理方向，使用 RoleSpec 的工厂与 n_units，并明确 partition/shared。实例数是算法分工，不自动获得线程或 GPU。

本例不提供跨机器池共享、外部 Provider、失败注入或完整 checkpoint 恢复实验；框架已有这些相关契约不意味着这一次演示执行了所有路径。它检验的是方向视图、递归精修、实际候选交付、raw 保留与标准 Project 装配这一条完整路径。
