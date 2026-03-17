# 权威可运行示例（事实标准）

这里不是教程，而是“可运行的事实标准”：

- 作为框架主路径的基准实现（推荐入口）
- 用来对齐后续新能力（参数命名 / context keys / 组合方式）
- 任何重构/回归都应该保证这些示例仍能运行

## 1) SolverBase：底座 + 插件驱动的最小闭环

- 文件：`examples/_misc_examples/blank_solver_plugin_demo.py`
- 目的：证明“底座尽量纯净 + 插件做装配”能跑通，并且可以自然接入 Pipeline/Bias/Plugins

## 2) Blank vs Composable：同一策略两种落地方式对比

- 文件：`examples/_misc_examples/blank_vs_composable_demo.py`
- 目的：说明什么时候用“插件化快速落地”，什么时候抽象成 Adapter（可复用/可融合）

## 3) ComposableSolver + CompositeAdapter：策略融合的事实标准

- 文件：`examples/_misc_examples/composable_solver_fusion_demo.py`
- 目的：把策略内核拆成多个 adapter，再用组合器融合（这才是“生态”的核心能力）

## 4) End-to-end workflow：统一实验口径 + 可审计证据链

- 文件：`examples/_misc_examples/end_to_end_workflow_demo.py`
- 目的：同一 Problem + Pipeline 下，对比单策略 vs 多策略协同，并输出 BenchmarkHarness CSV/JSON 作为可比对证据

## 5) Real-world case：生产调度（复杂约束 + 管线修复 + 并行评估）

- 文档：`docs/cases/production_scheduling.md`
- 主脚本：`examples/cases/production_scheduling/working_integrated_optimizer.py`
- 目的：把“工程价值”落到可运行事实：模块化约束、可复现证据链、并行/分布式评估路径

## 运行方式

建议在仓库上一级目录运行（或先 `pip install -e .`）：

```bash
python nsgablack/examples/_misc_examples/blank_solver_plugin_demo.py
python nsgablack/examples/_misc_examples/blank_vs_composable_demo.py
python nsgablack/examples/_misc_examples/composable_solver_fusion_demo.py
python nsgablack/examples/_misc_examples/end_to_end_workflow_demo.py
python nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py --no-export --generations 2 --pop-size 20
```


## 6) Dynamic + Multi-Strategy：动态协同的事实标准

- 文件：`examples/_misc_examples/dynamic_multi_strategy_demo.py`
- 目的：展示动态信号驱动的软切换、策略权重调整，以及多策略协同的可复现输出口径
