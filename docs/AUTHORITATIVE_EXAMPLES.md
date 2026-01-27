# 权威现代示例（事实标准）

这不是教程，而是“可运行的事实标准”：

- 作为框架主线的基准实现
- 用来对齐后续新功能（参数命名 / context keys / 组合方式）
- 任何回归/重构都必须保证这些示例仍能跑通

## 1) BlankSolverBase：特殊流程 / 非进化类快速原型

- 文件：`examples/blank_solver_plugin_demo.py`
- 目的：证明“底座纯净 + 插件驱动流程”能跑通，并且可自然接入 Pipeline/Bias/Plugin

## 2) Blank vs Composable：同一策略两种落地方式对比

- 文件：`examples/blank_vs_composable_demo.py`
- 目的：说明什么时候用插件化（先跑起来），什么时候抽象成 Adapter（可复用/可融合）

## 3) ComposableSolver + CompositeAdapter：策略融合事实标准

- 文件：`examples/composable_solver_fusion_demo.py`
- 目的：说明“融合”在框架里是什么：把策略内核拆成多个 adapter，再用组合器融合

## 4) End-to-end workflow：统一实验口径 + 最短路径落地

- 文件：`examples/end_to_end_workflow_demo.py`
- 目的：同一问题/同一 Pipeline 下，对比单策略 vs 多策略协同，并输出 BenchmarkHarness CSV/JSON 用于公平比较/消融实验

## 运行方式

建议在项目上一级目录运行（或 `pip install -e .`）：

```bash
python examples/blank_solver_plugin_demo.py
python examples/blank_vs_composable_demo.py
python examples/composable_solver_fusion_demo.py
```
