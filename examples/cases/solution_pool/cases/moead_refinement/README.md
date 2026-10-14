# MOEA/D 方向子池与 VNS 精修

本例装配 MOEA/D + GA + VNS：MOEA/D 自动产生 100 个方向投影子池，四个 VNS 实例合计随机处理其中 20 个方向，然后结果返回 MOEA/D 竞争。GA 的种群独立，不在 adapter1 的方向选择范围内。

组件包括 TwoCenters 双目标 Problem、共享 UniformInitializer / ContextGaussianMutation / ClipRepair、StrategyRouterAdapter、MOEADAdapter、NSGA2Adapter、VNSAdapter 和 Solver 自带 SolutionPool。不额外装配 Bias、Evaluation Provider 或 Plugin。Case 消费 Project 提供的资源授权。

```powershell
python examples/cases/solution_pool/cases/moead_refinement/run_solver.py --check
python examples/cases/solution_pool/cases/moead_refinement/run_solver.py
```

主要装配见 `adapter/refinement.py`：

```python
moead = MOEADAdapter(name="adapter1", population_size=100)
selection = subpools.random(20, moead)  # 替换为 subpools.all(moead) 选择全部
task = PoolTaskSpec(selection, steps=3, output="refined")
```

`build_solver(config={"view_count": None})` 使用全部方向；directions、workers、local_steps、max_steps、seed 可配置。默认提交预算按初始化、所选方向数、工作实例、精修步数和返回批次估算。steps 包含起点基准评估后的更新，每步可能评估多个邻域候选。

`local_algorithm` 可选 `vns`、`sa`、`pattern`，使用相同来源选择、输出和返回装配。SA 可以探索较差当前点，但派生视图交付任务内最好已评估解。MOEA/D setup 不生成或评估候选；阶段先等待 pool_views_ready，再初始化 GA 和启动精修，不以固定第一步假定方向已经存在。

每个任务固定起点版本、方向权重与参考点，起点和邻域均通过原 Problem 求双目标，再投影供 VNS 比较。母池保存原始双目标；返回候选由 MOEA/D 按当前方向与替换上限决定成员。输出包含已接纳提案，不保证全部都是局部改进。本例验证装配机制，不宣称融合优于单算法。

同一候选可以占据多个方向，不复制候选身份；20 是方向数量，不是 VNS 实例数或并发资源数。任务的随机选择、比较参数和进度随现有事务/checkpoint 保存。

## 子视图再精修：VNS 的结果交给另一个 VNS

同一标准 Case 还提供两层精修装配：

```python
from examples.cases.solution_pool.cases.moead_refinement.build_solver import build_solver

solver = build_solver({
    "nested_refinement": True,
    "directions": 8,
    "view_count": 4,
    "local_steps": 2,
    "fine_steps": 2,
})
solver.run()
```

它依次完成 MOEA/D 正式初始化、GA 初始化、VNS 粗搜、VNS 细搜、MOEA/D 返回竞争，然后继续搜索。
粗搜与细搜各使用一个 VNS 实例，分别采用 `base_sigma=0.2` 和 `0.05`；`workers` 只用于上面的单层装配。
未给 `max_steps` 时，两层模式按所选方向数和两层步数分配运行预算，包含各方向的起点基准评估、
细搜聚合输出返回竞争所需批次，以及两个继续搜索步骤。
这是针对本例默认接纳策略与每步两个 VNS 邻域提案的预算估算；若装配拒绝策略或修改提案数量，应显式调整预算。

关键装配只有来源选择和输出声明：

```python
coarse_task = PoolTaskSpec(subpools.random(4, moead), steps=2, output="coarse_results")
fine_task = PoolTaskSpec(subpools.all(coarse_vns), steps=2, output="refined")
```

粗搜为每个完成的方向任务发布一份结果视图，其中只有该 VNS 的最终当前解。
细搜从这些当前解启动，沿用粗搜冻结的方向权重与参考点；每次新提案仍通过原 Problem 求双目标，再投影一次。
因此细搜不会从粗搜最后一个被拒绝的试探解启动，也不会把上一层的标量再做一次标量化。
如果继续加第三层，可为新 VNS 选择 `subpools.all(fine_vns)`；Router 的阶段策略决定何时启动它。

视图保留创建者和父视图的身份、版本及祖先信息。方向视图、粗搜结果视图、细搜结果视图共享母池中的候选版本引用，
不复制整套候选值或目标矩阵。每层仍需要自己的成员引用、元数据和 VNS 状态，因此层数与任务数增加时并非零存储成本。
父视图后来更新或关闭不改变已经冻结的任务输入与比较规则。

普通具名输出 `coarse_results` / `refined` 仍汇集该阶段被接纳的提案，供竞争或分析；
`subpools.all(coarse_vns)` 选择的是逐任务的当前解视图，两者用途不同。
MOEA/D 从 `refined` 接收候选，读取原始双目标并按自己的当前规则决定替换，不把 VNS 的标量写回原始目标。

行为验证入口：

```powershell
python -m pytest tests/test_nested_refinement.py -q
```

本阶段验证（2026-10-13，递归视图）：上述 3 项行为测试通过，覆盖粗搜当前解交接、
细搜在对应方向继续改进、原始双目标返回、三层视图的父级身份与引用共享、以及细搜中途正式 checkpoint 恢复。
标准 Case 的小规模两层模式实际执行 12 个提交步，粗搜、细搜、返回竞争和 GA 初始化全部完成。
默认两层配置也实际运行完成：100 个方向中选择 20 个，粗搜与细搜各发布 20 个结果视图，
100 个细搜接纳提案分 7 个步骤返回竞争；共 130 个提交步、428 次评估，四个角色任务全部完成，
MOEA/D 的原始反馈维度保持 `(100, 2)`。这验证了默认预算覆盖交接流程，不是算法性能比较。

最终汇总回归 245 项通过，其中本阶段新增 39 项：池视图 19 项、正向嵌套 3 项、异常/接纳/恢复/精确版本交付 17 项。
覆盖既有单层投影、普通子池、解池回收、MOEA/D/VNS、步骤事务、checkpoint、评估证据与 Bias/硬准入边界。
33 条运行警告来自例子未装 ParetoArchive，以及既有的缺失变异能力负例；没有测试失败。未执行全仓测试或性能 benchmark。
Windows 本次验证给 NUMBA_CACHE_DIR 指定可写临时目录，并为 pytest 使用独立 basetemp，避免旧缓存目录的权限干扰。

上一阶段验证（2026-10-13，单层装配）：默认装配实际运行 25 个提交步、328 次评估，保留 100 个方向视图，选择 20 个不同方向，MOEA/D 返回任务、GA 初始化和四个 VNS 队列均完成，MOEA/D 反馈仍为双目标。18 项投影测试包含在 283 项通过的相关回归中；较慢的 300→30×100 分配测试在此前一轮通过，汇总复验未重复执行。未运行全仓全部测试，也未进行算法优越性 benchmark。

```powershell
python -m nsgablack project doctor --path . --strict --catalog-audit --profile framework-core --format json
python -m nsgablack project doctor --path examples/cases/solution_pool --strict --build --format json
```

两条 Doctor 均为 0 error、0 warning。根检查不执行全部 Case 的 build；上述 Project 的三个 Case 均已完成 build 检查。moead_refinement 没有独立 Case Catalog TOML，该项按明确作用域跳过，公开组件与例子登记在框架 Catalog；default 可见例子，framework-core 保留组件并过滤例子。

本阶段复验的根覆盖为 completed=463、skipped=90（62 个 build 未在根检查启用、27 个 Case 无本地 Catalog、1 个框架 registry 改走 Catalog 审计）；Project 覆盖 completed=30、skipped=3（2 个 Case 无本地 Catalog、1 个 Project Catalog audit 未开启）。根检查已单独开启 framework-core Catalog audit；default/framework-core 的组件与示例过滤分别通过核对。
