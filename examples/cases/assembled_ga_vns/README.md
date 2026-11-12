# 一个完整的装配示例：GA 搜索 → VNS 逐成员精修 → GA 接纳

这个 Project 展示问题管线、Unit 构建规则、算法行为、偏好与观察插件如何一起装配。它复用框架中的 NSGA-II、VNS 和 Router；项目只定义自己的问题、盒约束修复、扩展种群字段、软偏好和轨迹观察。

需要从目录、装配一路读到每次提交和结果核对时，看 [Project 全过程详解](PROJECT_DEEP_DIVE_CN.md)：逐段讲解源码、候选身份、解池交接、Unit 按需创建、81 步／600 次求值，以及修改和扩展时的边界。

其它算法和组合的完整例子见 [四个 Project 阅读指南](../ASSEMBLED_PROJECTS_GUIDE_CN.md)，包含 MOEA/D 双层精修、SA 池恢复和 DE／SA 真正跨 Case 并发。

现在也可在这个 Case 中选择 `schedule="plan"`：显式重复两轮“GA→VNS→原GA返回竞争”，
不用按全局代数手算阶段。每轮交还当前 VNS 请求的最终选择，历史接纳池另行保留。
真实装配、14 次提交／36 次求值与恢复验证见 [自然循环编排](PLAN_CN.md)。

建议依次阅读 [Case 装配入口](cases/hybrid_search/build_solver.py)、[算法组合](cases/hybrid_search/adapter/composition.py)、[项目源码全文](PROJECT_CODE.md)、[组件源码索引](COMPONENTS.md)，最后查看 [运行报告入口](run_and_report.py)。

## 要解的问题

候选为二维向量 `x = [x0, x1]`，原始问题是：

```text
minimize f(x) = (x0 - 2)^2 + (x1 + 1)^2
subject to -4 <= x0 <= 4, -4 <= x1 <= 4
```

已知最优点为 `[2, -1]`，原始目标为 `0`。这个简单问题便于逐项核对候选和反馈；该运行展示装配与身份交接，不用于证明算法性能优于其他方法。

偏好另行定义：当 `x0 < 0` 时，在选择视图中增加 `0.1 * (-x0)`。它不修改 `Problem.evaluate()` 的返回值，也不改变原始约束。最优点位于不受惩罚的半平面，因此偏好不改变这个问题的已知最优点。

## 项目脚手架

```text
assembled_ga_vns/
  project_config.py                 # Project 编排和 L0 授权
  run_project.py                    # 正式 Project CLI
  run_and_report.py                 # 调正式 Project API，整理本例报告
  _bootstrap.py                     # 本地源码开发环境引导
  README.md
  COMPONENTS.md                     # 所用组件的实际源文件
  PROJECT_CODE.md                   # 本项目运行源码的阅读快照
  cases/
    __init__.py
    hybrid_search/
      .case                         # solver Case 身份声明
      config.py                     # 本例参数与 Case 声明
      build_solver.py               # 唯一正式装配入口
      build_trainer.py              # build_solver 的薄别名
      run_solver.py                 # 标准 Case CLI
      run_trainer.py                # run_solver 的薄别名
      problem/quadratic.py          # 原始目标和约束
      pipeline/main.py              # 问题候选处理管线
      pipeline/operators.py         # BoxRepair
      pipeline/population.py        # 扩展种群 Unit 与 Builder
      adapter/composition.py        # GA、VNS、池任务和 Router
      bias/preference.py            # 软评分偏好
      plugins/trace.py              # 已提交轨迹观察
      catalog/entries/*.toml        # 本地组件的可发现性声明
      evaluation/                   # 本例无需定制 Provider
      runtime/                      # 本例消费 Project 授权
      solver/                       # 本例复用 ComposableSolver
```

空包和薄导出文件仍属于完整脚手架；它们不用承载重复的框架实现。本例没有纳入与运行无关的生成器教学模板。

## 装配后的行为

本例安排 81 个逻辑提交步骤：

1. **GA 阶段，8 步。** NSGA-II 的种群大小和每次后代数均为 12。它通过自己绑定的初始化器和变化算子提出候选，问题管线修复后统一求值。NSGA-II 使用自身环境选择规则，将准确成员版本发布为普通 `population` 视图。
2. **VNS 阶段，72 步。** `subpools.all(ga)` 按这个 GA 实例的来源路径选择它发布的视图；`count="all"` 把冻结视图内的 12 个成员逐个交给 VNS。每个成员执行 6 步，其中第 1 步重新评估起点，后 5 步提出邻域候选。
3. **返回阶段，1 步。** GA 通过 `PoolTaskSpec("refined", mode="compete")` 取得精修阶段的接纳提案，重新走正式修复和评估路径，再由自己的环境选择决定保留哪些成员。

默认 `total_batch_size=252` 是 Router 每次分配提案的上限，来自 `max(12, 12 * (1 + 5 * 4))`：允许最后一次竞争读完整局部接纳提案集合。**它不是母池容量，也不是要求存在 252 个候选**。GA 的 12 个成员、VNS 的邻域批量、池内历史版本是三种不同数量。

默认 `refinement_source="population"` 精修 GA 当前种群中的**全部成员**。`subpools.all(ga)` 选择视图；`count="all"` 选择其中全部成员。这个默认模式及原81步／600次求值报告保持不变。

## 可选闭环：只精修GA发布的20个精英

同一个标准Case也支持显式 `refinement_source="elite"`。Project的`elite`分组通过正式`component_overrides`配置种群24、GA2步、精英20、每项VNS2步、邻域批量1，以及128次求值预算；不复制Case或手写运行循环：

```powershell
python run_project.py --group elite --check --build-check
python run_elite_and_report.py
python run_elite_and_report.py --report-only
```

这个模式的完整闭环是：

1. GA的普通choose沿用约束支配排序与末层拥挤度，返回全部24个生存成员，并从其中按本例单目标选择反馈选出20个精英。它一次返回 `members, {"ga_elite": elite}`，由同一步事务创建或精确替换普通集合。
2. VNS使用命名函数 `select_elite_refs` 调用 `control.solution_pool.subpool_refs("ga_elite")`，准确读取这个公开池名。这里使用回调，是因为 `PoolTaskSpec("ga_elite")` 的字符串会按任务命名空间解释，并不等于choose输出的公共准确名。
3. 请求开始时冻结20个SolutionRef。每个起点先重新求值，再进行一次邻域变化和求值。VNS不直接修改GA成员、排名或成员年龄。
4. 任务完成后进入return阶段；40个聚合接纳提案经正常修复、重新求值与硬接纳，交给原GA环境选择竞争，成员扩展字段由PopulationUnit同步维护。

20个任务会各自发布最终选择视图；`ga_vns/refined`则保存40个接纳提案，包括20个基准与20个邻域候选。**本例返回的是这个聚合集合，不把它冒充20个最终精选结果。** 接收方重新评估只发生在正式返回阶段；取精英引用本身不调用Problem，也不把精修结果的分数写回原起点。

本配置共43次逻辑提交、128次求值：GA48次，VNS40次，返回GA40次。观察核对精英属于GA最终成员、冻结引用逐项一致、原始反馈保留与GA实际返回竞争。结果独立写入 [ELITE_RESULTS.md](ELITE_RESULTS.md) 与 `results/elite/`，原默认运行文件不覆盖。`PROJECT_CODE.md`保留早期默认模式的源码阅读快照；本可选模式以当前 [config.py](cases/hybrid_search/config.py)、[composition.py](cases/hybrid_search/adapter/composition.py) 和 [Project配置](project_config.py) 为准。

## Unit 何时出现

装配 `UnitBinding(AgePopulationBuilder())` 只提供构建和恢复规则，不创建种群。运行开始时 SolutionPool 已建立，GA 的种群 Unit、VNS 的当前点 Unit、VNS 的邻域 Unit 都可以尚未创建。

- GA 首次提案时建立自己的种群结构，之后继续使用并更新它。
- GA 阶段 VNS 没有被调度；读取观察和 Doctor 都不应替它创建 Unit。
- VNS 第一次得到池内起点时建立自己的候选结构；需要邻域几何时再建立邻域结构。
- 同一个 VNS 逐个处理独立精修任务，默认模式为12个、elite分组为20个；每次显式 `restart_search` 建立下一任务的搜索状态。这与同一任务每一步重复初始化不同。
- GA 返回阶段使用自己保留的种群 Unit。VNS 不会直接改写 GA 的排名、成员或 Unit。

`AgePopulationUnit.member_age` 额外记录成员在环境选择中连续存活的次数。NSGA-II 仍只决定选哪些成员；扩展字段由 Unit 的 `on_members_changed()` 根据来源索引更新，Adapter 不猜未知字段的含义。

## 行为与问题管线的边界

- **初始化：** GA 绑定 `UniformInitializer`；VNS 任务起点来自冻结的 SolutionRef，不重新随机生成起点。
- **变化：** GA 绑定 `GaussianMutation`；VNS 绑定 `ContextGaussianMutation`，消费该 VNS 局部上下文里的邻域尺度。两者不替对方改共享默认算子。
- **选择：** 默认模式保留NSGA-II原生selector；elite模式通过普通choose显式复用其约束支配／拥挤度规则，再从最终成员发布精英副结果。VNS继续执行自己的比较与接纳规则。
- **修复：** `BoxRepair` 是 ProblemRepair，放在问题管线中，由控制面在评估前调用。本例没有额外 UnitRepair，也没有开启多轮 JointRepair。

候选进入 VNS 不需要解码 GA 的种群 Unit：池内保存候选版本，两个 Adapter 各自建立自己的算法结构。返回 GA 的也是候选与对应反馈，而不是“原候选的分数等于精修结果的分数”。

## 解池交接与结果含义

GA发布的视图和精英集合只引用准确成员版本，不另复制候选值。VNS请求开始时冻结输入引用；后续母池变化不会把正在处理的起点偷偷换成新版本。

每个 VNS 精修任务有两种输出：

- 每任务发布的结果视图：来自 `get_pool_refinement_results()`，明确表达该任务最后选择的候选。
- `refined` 聚合子池：保存该任务接纳的提案，可能包含起点、途中候选和最后选择；本例把这个集合交给 GA 竞争。

因此，聚合 `refined` 的成员数不能直接解释成“精修成功的个体数”。轨迹中的 `pool_records` 统计池内批次记录数，也不是候选总数。已有引用进入另一个算法仍需按接收方的语义重新评估，且失败尝试消耗的实际评估不随事务回滚。

## 运行

运行前提是 Python 能导入本例对应的 nsgablack 与 BlackBase 开发版本，以及它们的正式依赖；本次实测使用本机已安装／可导入的开发源码。Python 版本与依赖范围以仓库 [pyproject.toml](../../../pyproject.toml) 为准，当前声明 Python `>=3.10`。

这个 Project 不捆绑框架库实现。将目录复制到其他位置或机器时，须先安装相应框架版本和依赖；`_bootstrap.py` 只提供局部路径引导，不能在任意目录自动发现尚未安装的框架。源代码链接指向当前仓库及相邻 BlackBase 源码，独立复制时应保留源码位置或相应调整链接。

在此目录的 PowerShell 中执行：

```powershell
python run_project.py --check --build-check
python run_and_report.py
```

第一条通过 Project 的 L0 配置构建 Case 并检查生效组件与资源绑定，不执行搜索。第二条调用正式 `execute_project()`，运行后整理候选、选择反馈、原始目标的独立解析核对、Unit 创建时点和资源审计。报告中的 `raw_objective_recomputed` 不来自持久求值证据，也不计入 Solver 的求值次数；报告没有导出每个候选的完整 raw evidence。

当前通用 CLI 的 `runtime_state.initializer`、`runtime_state.mutator` 只展示共享问题 Pipeline 中的槽位。本例 Pipeline 只装 BoxRepair，因此这两个字段为 `None`，不能据此推断 GA/VNS 没有绑定行为。实际直属绑定见 [composition.py](cases/hybrid_search/adapter/composition.py)，运行中的公开摘要见 `results/trace.json` 的 `initial.operation_contracts`。

只运行、不整理本例额外报告时，也可以使用标准入口：

```powershell
python run_project.py
```

本例不需要数据库、服务器、外部 Provider 或 ML 后端。Project 发放资源授权，Case 消费 `resource_context`。

## 实际运行记录

2026-10-19，固定种子 `7`，已通过正式 Project API 实跑，结果为：

- 最终候选：`[2.0003622890074766, -1.003468343542692]`。
- 最好选择目标：`1.2160660255072348e-05`；独立解析重算的原始目标相同，原始盒约束可行。
- 共 `81` 个逻辑提交、`600` 次 Solver 求值：GA `96` 次，VNS `252` 次，返回 GA `252` 次。
- GA 阶段结束时仍未创建 VNS 的当前点和邻域 Unit；最终有 `12` 个对齐的 GA 成员和 `12` 个 VNS 任务结果视图。
- 正式 Case 结果与观察轨迹的候选 token、选择目标和求值计数一致；生效资源授权为 CPU、`threads=1`、`workers=1`、`gpus=0`。

完整数值与核对项见 [RESULTS.md](RESULTS.md) 和 [results/summary.json](results/summary.json)。逐提交观察位于 [results/trace.csv](results/trace.csv) 和 [results/trace.json](results/trace.json)，正式 Project 返回值位于 [results/project_result.json](results/project_result.json)。原始目标重算是报告阶段的独立解析核对，不是持久 raw evidence 的读取；候选身份和快照 key 随运行变化。

GA 阶段结束时的成员年龄为 `[2, 5, 5, 4, 1, 0, 2, 0, 3, 2, 2, 0]`，已有成员年龄达到 5，说明更新 hook 确实执行。年龄按 `PopulationChange.previous_member_indices` 维护；返回竞争中选入的 incoming 行年龄为 0，不按数值相同反推旧成员。最终年龄均为 0 只说明本次成员更新的结果，不能据此推断所有候选身份都是新的。

本例还通过严格构建与 Catalog 审计 Doctor，`0 error / 0 warning / 10 info`，读取到 `6` 个本地条目，报告见 [results/doctor.json](results/doctor.json)。它验证受支持的结构、声明、资源和实际构建表面，不能据此宣称数学性质或任意副作用已经证明。

## 本地 Catalog

[catalog/entries](cases/hybrid_search/catalog/entries) 用 4 个 TOML 文件登记本例的 6 个自定义组件：QuadraticProblem、BoxRepair、AgePopulationUnit、AgePopulationBuilder、NegativeHalfPlaneBias 和 CommittedTracePlugin。声明包含准确导入路径、配置键、轻量上下文契约与最小装配提示。

Catalog 用于发现与核对；真正的装配仍以 `build_solver.py` 及其调用的工厂为准。库中的 NSGA-II、VNS、Router 和通用算子复用已有框架条目，不在本例重复登记一份框架实现。

本例额外展示了自定义成员年龄、软偏好和生命周期核对，因此包含相应组件与报告代码。它们分别用于检验扩展字段维护、评估边界和按需创建；算法作者接入其他问题时按需要装配，不必重新实现这些观察和底座能力。

## 阅读时值得检查的地方

先看 `build_solver.py` 是否清楚地表达组件组合，再看 `adapter/composition.py` 是否只表达算法调度和交接。然后检查：自定义种群字段能否在不修改 NSGA-II 的情况下维护；VNS 未调度时是否没有结构；原始目标和软偏好是否分开；报告是否只在正式提交后记录成功。

这几个问题比类和目录是否齐全更能判断这套装配是否合理。
