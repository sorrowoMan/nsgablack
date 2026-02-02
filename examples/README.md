# 示例（现代基准）

本目录只保留少量“权威可运行”的现代示例，用作工程对齐基准：

- `examples/blank_solver_plugin_demo.py`：BlankSolverBase + Plugin + 表示管线 + 偏置（快速落地路径）
- `examples/blank_vs_composable_demo.py`：BlankSolverBase(插件流程) vs ComposableSolver(Adapter模块) 对比（迁移/抽象路径）
- `examples/composable_solver_fusion_demo.py`：ComposableSolver + CompositeAdapter 融合多个策略模块（算法融合路径）
- `examples/monte_carlo_dp_robust_demo.py`：Monte Carlo + DP 鲁棒性测试（随机环境 + CVaR 评估）
- `examples/dynamic_multi_strategy_demo.py`：动态切换 + 多策略协同（信号驱动切换 + 权威输出口径）
- `examples/trust_region_dfo_demo.py`：信赖域 DFO 局部搜索示例
- `examples/trust_region_subspace_demo.py`：子空间信赖域示例（CUATRO_PLS 风格）
- `examples/trust_region_subspace_frontier_demo.py`：子空间信赖域 + 学习子空间（前沿路径）
- `examples/trust_region_nonsmooth_demo.py`：非光滑信赖域示例
- `examples/mas_demo.py`：MAS（Model-and-Search）示例
- `examples/trust_region_mo_dfo_demo.py`：多目标信赖域 DFO（前沿组合）
- `examples/active_learning_surrogate_demo.py`：主动学习式 surrogate 评估示例
- `examples/robust_dfo_demo.py`：不确定环境 DFO + MC 鲁棒性
- `examples/surrogate_assisted_ea_demo.py`：代理辅助进化搜索
- `examples/surrogate_model_lab_demo.py`：代理模型“家族/范式”对比
- `examples/structure_prior_mo_demo.py`：结构先验 + 多目标（对称性/结构偏置）
- `examples/multi_fidelity_demo.py`：多保真评估插件示例（低保真筛选 + 高保真验证）
- `examples/risk_bias_demo.py`：风险偏置（CVaR 风格）示例
- `examples/bias_gallery_demo.py`：偏置画廊（按 catalog key 选择偏置）
- `examples/plugin_gallery_demo.py`：插件画廊（按 catalog key 选择插件）
- `examples/role_adapters_demo.py`：角色适配器 + 多角色控制器
- `examples/astar_demo.py`：A* 搜索适配器（网格路径）
- `examples/moa_star_demo.py`：多目标 A*（Pareto A*）
- `examples/parallel_repair_demo.py`：并行修复（ParallelRepair）
- `examples/dynamic_repair_demo.py`：动态修复管线（分阶段 repair）
- `examples/dynamic_penalty_projection_demo.py`：动态惩罚偏置 + 投影修复（纯偏置化/纯管线化示例）
- `examples/nsga2_solver_demo.py`：BlackBoxSolverNSGAII + 工程套件（NSGA-II 底座示例）
- `examples/parallel_evaluator_demo.py`：ParallelEvaluator 并行评估示例
- `examples/context_keys_demo.py`：Context keys 常量示例
- `examples/context_schema_demo.py`：最小化评估上下文构建示例
- `examples/logging_demo.py`：日志配置工具示例
- `examples/metrics_demo.py`：Pareto/超体积/IGD 指标示例
- `examples/dynamic_cli_signal_demo.py`：命令行动态信号输入示例

## 常用问题类型模板

这些是“开箱即用”的常见问题类型模板，可直接运行/改造：

- `examples/template_continuous_constrained.py`：连续变量 + 软约束（动态惩罚偏置）
- `examples/template_knapsack_binary.py`：0/1 背包（BinaryRepair + CapacityRepair）
- `examples/template_tsp_permutation.py`：TSP 路径规划（Permutation + 2-opt）
- `examples/template_multiobjective_pareto.py`：多目标 Pareto（MOEA/D + archive）
- `examples/template_assignment_matrix.py`：指派/匹配矩阵（行列和约束修复）
- `examples/template_graph_path.py`：图路径/连通子图（Graph 修复）
- `examples/template_production_schedule_simple.py`：生产排程简化版（矩阵 + 需求列约束）
- `examples/template_portfolio_pareto.py`：投资组合 Pareto（风险 vs 收益 + Simplex 修复）

历史示例已从仓库清理（降低维护成本）；如需追溯请查看 git 历史。
