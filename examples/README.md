# 示例（现代基准）

本目录只保留少量“权威可运行”的现代示例，用作工程对齐基准：

- `examples/blank_solver_plugin_demo.py`：BlankSolverBase + Plugin + 表示管线 + 偏置（探索/快速落地路径）
- `examples/blank_vs_composable_demo.py`：BlankSolverBase(插件流程) vs ComposableSolver(Adapter模块) 对比（迁移/抽象路径）
- `examples/composable_solver_fusion_demo.py`：ComposableSolver + CompositeAdapter 融合多个策略模块（算法融合路径）

历史示例已从仓库清理（降低维护成本）；如需追溯请查看 git 历史。

