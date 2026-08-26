# 超级拓扑编排示例

这个正式 Project 用一个小规模、可真实运行的链路展示统一框架的组合能力：

环境需要 `blackbase>=0.3.23`；两个 Trainer 的语义组件来自当前 MLBlack 0.4 系列。

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

两个 Trainer 不是只靠命名模拟 ML：它们实际复用 MLBlack 的 `LearningProblem`、
`ModelRepresentation`、`NumericDataView`、`Feedback` 和 `TrainerResult` 语义组件；运行控制、
资源与嵌套编排仍由 NSGABlack/BlackBase 的统一控制面承担。

运行：

```powershell
python run_project.py --check --build-check
python run_project.py
```

本例同时使用 Project 静态 DAG 与 Case 动态嵌套调用。DAG 自动从
`baseline_solver.summary`、`baseline_trainer.summary` 推导 `outer_search` 的两个上游，
而候选数量运行前未知的 Trainer/内层 Solver 调用继续形成动态调用树。
