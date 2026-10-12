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
