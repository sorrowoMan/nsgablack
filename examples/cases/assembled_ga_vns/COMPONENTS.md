# 本例实际组件与完整源码

本文索引本项目定义的组件，以及运行中复用的框架实现。点击文件即可看到完整真实代码；库代码没有复制进 Case 形成第二份实现。本项目自有运行代码另见 [PROJECT_CODE.md](PROJECT_CODE.md)。

## 本项目定义的组件

### Project 与 Case 入口

- [project_config.py](project_config.py)：Project 的 `L0`、`STAGES`、`GROUPS`，负责 Case 编排与资源授权声明。
- [run_project.py](run_project.py)：标准 Project CLI 的薄入口。
- [_bootstrap.py](_bootstrap.py)：本地开发时使当前框架源码可导入。
- [run_and_report.py](run_and_report.py)：调用正式 Project API，核对观察报告，并独立解析重算最终候选的目标；该重算不是从持久 raw evidence 提取，也不计入 Solver 求值次数。它不自行实现搜索循环或资源分配。
- [config.py](cases/hybrid_search/config.py)：本例可复现参数与 Case 声明。
- [build_solver.py](cases/hybrid_search/build_solver.py)：组装问题、问题管线、组合 Adapter、Bias 和 Plugin，接收 Project 的资源上下文。
- [run_solver.py](cases/hybrid_search/run_solver.py)：标准 Case CLI；`build_trainer.py`、`run_trainer.py` 只作薄别名。
- [.case](cases/hybrid_search/.case)：声明 solver Case 身份；[.gitignore](.gitignore) 排除本地运行归档和 Python 缓存。

### 本地可发现性声明

- [problem.toml](cases/hybrid_search/catalog/entries/problem.toml)：QuadraticProblem。
- [pipeline.toml](cases/hybrid_search/catalog/entries/pipeline.toml)：BoxRepair、AgePopulationBuilder、AgePopulationUnit。
- [bias.toml](cases/hybrid_search/catalog/entries/bias.toml)：NegativeHalfPlaneBias。
- [plugin.toml](cases/hybrid_search/catalog/entries/plugin.toml)：CommittedTracePlugin。

这些 TOML 登记 6 个真实本地组件；运行行为由正式工厂装配，不由 Catalog 另建搜索流程。

### Problem：评估是什么意思

[QuadraticProblem](cases/hybrid_search/problem/quadratic.py) 定义二维二次目标与盒约束。它不读取 GA 排名、VNS 邻域、Router 阶段或 Bias 分数。最优点 `[2, -1]` 是问题本身的性质。

### 问题 Pipeline：评估前处理

- [build_pipeline](cases/hybrid_search/pipeline/main.py)：装配问题候选管线。
- [BoxRepair](cases/hybrid_search/pipeline/operators.py)：将坐标裁剪到问题边界；`validate()` 只读检查。

BoxRepair 不初始化 Unit、不调用评估、不决定候选存活。直接初始化器和变化算子绑定在实际使用的 Adapter 上；本例没有为每个 Adapter 复制一份问题管线。

### Unit：自定义字段维护

[AgePopulationUnit / AgePopulationBuilder](cases/hybrid_search/pipeline/population.py) 增加 `member_age`，通过 `member_fields` 和 `on_members_changed()` 维护对齐；Builder 继承标准纯数据 codec。

`pipeline/population.py` 是脚手架中构建组件的源文件位置；**文件位置不决定 Unit 的运行归属**。实际 Unit 由 GA 按需创建和持有。

### Adapter：行为装配与调度

[composition.py](cases/hybrid_search/adapter/composition.py) 显式创建两个 Adapter 实例，绑定各自行为和 Unit 构建规则，再声明角色、池任务、阶段和提案预算。

本例没有重新实现 NSGA-II 环境选择、VNS 邻域切换、池任务事务或 Project 生命周期。

### Bias 与 Plugin

- [NegativeHalfPlaneBias / build_bias](cases/hybrid_search/bias/preference.py)：仅为 `x0 < 0` 产生软惩罚，原始目标和约束留在评估证据中。
- [CommittedTracePlugin](cases/hybrid_search/plugins/trace.py)：记录已提交步骤、计数、权威游标和现存 Unit，只观察、不调用 `ensure_unit()`。导出文件是观察报告，没有冒充带权威发布收据的 Artifact。

## 直接装配的框架组件

### NSGA-II、VNS 与 Router

- [NSGA2Adapter](../../../adapters/nsga2/adapter.py)：种群初始化、提案、父代和环境选择、准确成员引用与视图发布。
- [VNSAdapter](../../../adapters/vns/adapter.py)：当前点、邻域结构、尺度、改进接纳、任务重启与明确的精修结果。
- [StrategyRouterAdapter / MultiStrategyConfig / RoleSpec](../../../adapters/multi_strategy/adapter.py)：角色实例化、阶段、预算、提案及反馈路由。
- [PoolTaskSpec / PoolTaskAdapter](../../../adapters/pool_tasks.py)：冻结源引用、逐成员精修、输入游标、进度、输出与事务恢复。
- [subpools / adapter_path](../../../adapters/subpools.py)：按实例的稳定所有权路径选择发布视图。
- [PoolRefinementState](../../../adapters/pool_results.py)：精修起点、当前点、选择结果与对应反馈。

`RoleSpec` 表达哪个实例处理任务；`subpools.all(ga)` 表达读哪个实例的视图。它们不按类名猜测所有者。

### 初始化和变化组件

[UniformInitializer、GaussianMutation、ContextGaussianMutation](../../../representation/continuous.py) 是本例直接复用的三个行为组件：

- `UniformInitializer.initialize(problem, context)`：GA 的候选来源。
- `GaussianMutation.mutate(candidate, context)`：GA 变化。
- `ContextGaussianMutation.mutate(candidate, context)`：VNS 变化，消费本次调用的邻域尺度。

组件具有显式身份和 RNG 状态 codec，随拥有它们的 Adapter 恢复，不拥有 Solver 或 Project 运行循环。

实际直属绑定的运行摘要位于 `results/trace.json` 的 `initial.operation_contracts`。通用 CLI 中的 initializer/mutator 只看共享 Pipeline 槽位，本例在那里显示 `None`，不表示 Adapter 没有自己的绑定。

### Unit 构建、按需创建和成员维护

- [UnitBinding、UnitBuildRequest、StructureBuildRequest](../../../units/contracts.py)：构建规则、schema、操作要求和显式恢复。
- [UnitBackedAdapter](../../../adapters/unit_backed.py)：Unit 按需建立、保存与恢复；未创建状态为 `None`。
- [PopulationUnit](../../../units/collections.py)：统一维护 X/F/V/token 和声明的扩展成员字段。
- [PopulationChange](../../../units/population_operations.py)：成员变更的只读来源与身份对齐输入。
- [PopulationUnitBuilder / NeighborhoodUnitBuilder](../../../representation/structure_builders.py)：种群和 VNS 邻域结构构建规则。
- [CandidateUnitBuilder](../../../representation/unit_builders.py)：VNS 单候选结构构建和恢复。
- [CandidateUnit](../../../units/structures.py)：带身份的候选算法结构。

恢复已有 Unit 使用 codec；查看契约和读取状态不应触发 builder。

### 行为绑定

- [AdapterOperationsMixin](../../../adapters/operations.py)：消费角色声明、直接绑定、RNG 和绑定状态恢复。
- [OperatorBinding](../../../adapters/operator_binding.py)：组件身份、方法和状态 codec 契约。
- [SelectionRequest](../../../adapters/selection.py)：不同用途的只读选择输入；本例没有另装通用 selector。
- [AlgorithmAdapter](../../../adapters/algorithm_adapter.py)：提案、修复对账、处置、反馈与事务子项。

## 共享执行和数据基础设施

### Solver、评估和偏好

- [ComposableSolver](../../../core/composable_solver.py)：提案／反馈桥接、步骤事务和提交。
- [SolverBase](../../../core/blank_solver.py)：生命周期、候选操作、评估门面与共享服务。
- [BlackBoxProblem](../../../core/base.py)：问题定义基础接口。
- [BiasModule](../../../bias/bias_module.py)：偏好组合和选择视图。
- [DomainBias](../../../bias/core/base.py)：领域偏好基类。
- [Plugin](../../../plugins/base.py)：优化 Plugin 门面；共享生命周期由 BlackBase 提供。
- [evaluation_helpers.py](../../../core/solver_helpers/evaluation_helpers.py)：求值、反馈对齐和偏好投影的实际路径。
- [bias_helpers.py](../../../core/solver_helpers/bias_helpers.py)：原始证据与选择投影的分工。

### 解池与权威状态

- [SolutionPool / SolutionRef / SolutionStamp](../../../core/state/solution_pool.py)：候选版本、逻辑时间、引用集合、任务输入和提交可见性。
- [pool_views.py](../../../core/state/pool_views.py)：视图和目标投影；本例使用普通视图。
- [PopulationAuthority](../../../core/state/population_authority.py)：种群投影与权威快照游标。
- [RunSession](../../../core/state/run.py)：运行身份、进度与结果引用。

这些是复用的基础设施，不是用户需要在每个 Case 里重新实现的组件。

### 正式 Project 与 L0

- [nsgablack Project 入口](../../../project/project_runner.py)：正式 `execute_project()` 与 CLI 入口。
- [BlackBase Project runner](../../../../blackbase/src/blackbase/project/project_runner.py)：Project 执行、Case 调用、清单和结果。
- [BlackBase runtime](../../../../blackbase/src/blackbase/project/runtime.py)：资源分配、Case 发现和构建。
- [BlackBase Case binding](../../../../blackbase/src/blackbase/project/case_binding.py)：验证 Case 消费了有效资源授权。
- [BlackBase Case CLI](../../../../blackbase/src/blackbase/project/case_cli.py)：标准 Case 运行入口。
- [BlackBase execution](../../../../blackbase/src/blackbase/project/execution.py)：CaseRunResult 与 ProjectRunResult。

本例不引入第二套资源分配器、Adapter 主循环或证据提交器。

## 示例范围

这是二维、单目标、单 Case、串行阶段的装配例子；不据此验证 NSGA-II 的多目标 Pareto 表现。没有启用数据库、外部评估 Provider、ML Case、并行 L0 fanout、多轮 JointRepair 或自定义 UnitRepair。

核心交接是：**候选值和版本在池中，算法结构由各 Adapter 持有，评估在正式控制路径完成。**
