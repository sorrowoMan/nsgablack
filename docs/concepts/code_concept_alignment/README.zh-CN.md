# 代码机制概念对齐总览

本目录只保留当前架构口径下的概念对齐。旧草案中把编排、资源、示例落点分散到某个语义层的描述已经废弃。

当前第一原则：

- `nsgablack` 与 `mlblack` 共享 Project / Case / Scaffold / L0 substrate。
- 编排与资源授权属于 substrate。
- `nsgablack` 是优化搜索语义层。
- `mlblack` 是机器学习语义层。
- 任意标准 Case 都可以作为外层或内层；嵌套运行是 Case 调用 Case。

## 阅读顺序

1. `01_nsgablack_control_plane.zh-CN.md`
2. `02_nsgablack_strategy_representation_bias.zh-CN.md`
3. `03_nsgablack_runtime_catalog_project.zh-CN.md`
4. `04_mlblack_learning_flow.zh-CN.md`
5. `05_mlblack_symbolic_and_mechanisms.zh-CN.md`
6. `06_cross_framework_prediction_decision.zh-CN.md`
7. `07_deep_dive_backlog.zh-CN.md`

## 对齐方式

| 层 | nsgablack 语义 | mlblack 语义 | substrate 职责 |
| --- | --- | --- | --- |
| Project | 搜索实验集合 | 学习实验集合 | 跨 Case 顺序、并行、资源池、顶层入口 |
| Case | 一个 Solver | 一个 Trainer 或 ML evaluator | 独立标准脚手架、可单独检查与调试 |
| Scaffold | problem/pipeline/adapter/plugin | data/spec/codec/head/trainer/artifact | `build_solver.py` 与 `run_solver.py` 的统一入口形态 |
| L0 | 搜索任务的资源请求 | 训练/评估任务的资源请求 | Project 授权、Case 消费、审计生效上下文 |

## 文档边界

本目录解释“代码对象对应什么机制”。正式使用教程以 `docs/standard_scaffold_tutorial/README.md` 为准；项目创建与运行以 `docs/user_guide/PROJECT_SCAFFOLD.md` 为准。
