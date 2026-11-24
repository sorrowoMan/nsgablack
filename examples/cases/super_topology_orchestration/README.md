# 超级拓扑编排示例

这个正式 Project 用一个小规模、可真实运行的链路展示统一框架的组合能力：

环境使用工作区中的 BlackBase、NSGABlack 与 MLBlack 0.4 系列。

```text
Project
└─ workflow（DAG，自动从 Artifact 输入推导依赖）
   ├─ baseline_solver（Solver Case） ──┐
   ├─ baseline_trainer（Trainer Case）─┤ 并行就绪节点
   └─ 两个权威 Artifact 发布后 ───────┘
   └─ outer_search（Solver Case）
      ├─ exploration：多 role / 多 unit 路由
      ├─ refinement：VNS → Trust Region → DE 串行策略链
      └─ 每个候选 → nested_trainer（Trainer Case）
         └─ inner_solver（Solver Case）
```

L0 统一授权线程、worker、CPU 设备、共享评估预算和 Artifact authority。嵌套 Case
通过 `CaseRunRequest` 派生资源、预算、deadline/cancellation 和父子 lineage；未消费预算
自动向父级结算。最终 `topology_report` Artifact 保存所有嵌套调用的身份与资源证据。

两个 Trainer 都继承 MLBlack `LearningSolver`，通过正式 `FixedCandidateAdapter`
提交一次训练评估。闭式拟合、内层 Solver 调用位于各自的 `evaluation/`，由
`LearningProblem.prepare_model_for_evaluation()` 调用；步提交、预算扣减、teardown 和
结果发布遵守 NSGABlack/BlackBase 的统一生命周期。

实际组件组合：

- `baseline_solver`：`VNSAdapter` 与标准 `RepresentationPipeline`。
- `baseline_trainer`：`FixedCandidateAdapter`、`ClosedFormDataPipeline`，以及
  `linear.least_squares.closed_form` 拟合 Provider。
- `outer_search`：`StrategyChainAdapter`，其中探索阶段为多角色、多单元路由。
- `nested_trainer`：`FixedCandidateAdapter`、`NestedModelCodec`，以及
  `fit.with_nested_solver/v1` Provider。

两个训练 Case 的 `--check` 管线显示为正式 `MLRepresentationBridge`，内部包装上述
ModelRepresentation。自定义 Artifact Provider 在 `plugins/artifacts.py`，它们使用
`LearningSolver` 的 finalization session；模型和 summary 在同一事务发布。

`best_state` 表示训练规格：基线为是否拟合截距，嵌套训练为 capacity/regularization。
拟合后的权重与 calibration 属于 `best_model` Artifact，不混入搜索规格。
每次嵌套 Trainer 的评估预算上限为 3，实际扣除自身评估 1 次和子 Solver 评估 1 次，
剩余 1 次结算返还；内层 Solver 的上限为 2，实际使用 1 次。

`topology_report` 使用 `nsgablack.super_topology_audit/v2`。各项 invariant 从运行证据
重新计算，包含权威输入收据及内容校验、父子身份、授权资源上界与 lease、预算结算、
取消链摘要和 deadline。缺失证据、空调用列表或不一致字段会返回 `false`。
`project_dag_dependencies` 验证依赖关系；基线任务确实重叠运行由端到端测试的时间证据验证，
不再在 Case 报告中写死“并行成功”。

运行：

```powershell
python run_project.py --check --build-check
python run_project.py
```

本例同时使用 Project 静态 DAG 与 Case 动态嵌套调用。DAG 自动从
`baseline_solver.summary`、`baseline_trainer.summary` 推导 `outer_search` 的两个上游，
而候选数量运行前未知的 Trainer/内层 Solver 调用继续形成动态调用树。

## Pool 改造后的三级交互

各次 Case 运行拥有自己的 Pool、run_id、候选 token 和逻辑时钟。外层的二维配置进入
Trainer 的二维模型规格；Trainer 生成内层目标，由最内层搜索一维 calibration。
内层返回值参与外层评分，不把一维候选混进外层二维池。

`topology_report` 现增加有界的只读 Pool 证据：外层为 `solution_pool`，每条调用的
中层为 `trainer_pool`，最内层为 `inner.inner_pool`。证据包含各层身份、提交步数、
真实求值次数，以及最多 128 条接纳成员的准确引用、逻辑时间、数值与 raw feedback；
`evidence_complete` 明确表示是否覆盖全部成员。读取不生成候选、不求值、不构建 Unit，
也不把这些数组写入 Context。详细证据通过已有 Case 结果与 Artifact 跨进程交付。

当前 smoke profile 的四个外层提交实际求值数为 `3 + 1 + 1 + 4 = 9`：
探索阶段三个候选、VNS 基准一个、信赖域基准一个、DE 初始种群四个。
DE 的 `batch_size=1` 只控制后续 trial，不意味着初始种群只评一个。
因而三级动态链包含一个外层 Pool、九个 Trainer Pool、九个内层 Solver Pool。
两个独立基线 Case 不计入这个十九池计数。

### 可选：给外层组合绑定工作池

在 `project_config.py` 的同一 Stage 增加：

```python
STAGES[0]["component_overrides"] = {
    "outer_search": {"working_pool": "case_workspace"},
}
```

外层 builder 使用现有 `set_working_pool` 装配，启动 Plugin 只创建空普通集合，
不额外生成候选。外层接纳的九个版本随原事务进入该集合；子 Case 不继承其名字、
可写 Pool 或 context 绑定。默认配置仍不绑定工作池。

### 验证范围

`tests/test_super_topology_orchestration.py` 分别实际运行默认模式和外层工作池模式，
从正式返回的跨进程证据检查 Pool 隔离与 x→target→calibration→外层 raw 目标的对应关系。
原来的资源、预算返还、deadline 与 Artifact 验证保留。

默认内层 profile 只提交一次基准。`tests/test_nested_case_pool_progress.py` 在临时 Project
副本把内层改为两次提交，在原有内层预算 2、Trainer 预算 3 内执行实际邻域变异，
验证新 token、parent_token、选中校准值、Pool 原始目标与外层评分。
除原生邻域外，还通过现有 `change=普通函数` 装配一个确定改善的变化，检查内层选中后继后，
Trainer 和外层使用的确实是后继反馈，而不是旧基准的分数。
该配置是交互验收，不是算法效果 benchmark。

关于可选暖启动与跨 Case 候选输入的边界，见
[嵌套教程第 8 节](../../../docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md#8-pool-与三级-case-的边界)。

2026-10-21 实跑：默认/外层工作池模式及内层求值入口测试共 31 项通过，
上述两个内层两步变体均通过，已有内层运行、控制与工作池契约组 35 项通过，合计 68 项。
每个两步变体的三级动态链实际消耗为
外层 9 次求值、Trainer 9 次、内层 Solver 18 次，十九个本地 Pool 身份各自独立。
默认 Project 与启用外层工作池的 Project 副本分别执行 strict Doctor
（含 build 与 framework-core Catalog audit），均为 0 error、0 warning、33 info；
42 项 completed，5 项因 Case 没有本地 Catalog TOML 而明确 skipped。

复核命令（仓库根目录）：

```powershell
python -m pytest tests/test_super_topology_orchestration.py tests/test_case_inner_runtime_evaluator.py -q -o addopts=
python -m pytest tests/test_nested_case_pool_progress.py -q -o addopts=
python -m pytest tests/test_inner_solver_backend_contract.py tests/test_inner_solver_fullstack_stack.py tests/test_case_runtime_control.py tests/test_composite_working_pool.py -q -o addopts=
python -m nsgablack project doctor --path examples/cases/super_topology_orchestration --strict --build --catalog-audit --profile framework-core --format json
```
