# Memory — 跨会话持久知识 (nsgablack 侧)

## 框架组合规则（强制）

### 核心原则：组件组合 > 从头手写

所有案例应优先复用框架现有组件。只在以下情况自定义：
- **Problem**：领域特定的损失函数/评估逻辑（框架不可能穷举）

### 禁止手写的内容
- Adapter：框架有 23 个（de, sa, vns, nsga2/3, spea2, moead, pattern_search, trust_region*, astar, gradient_descent, strategy_chain, strategy_router, async_event_driven）
- Bias：框架有 66 个（graph 约束/算法/局部精修/domain）
- 只在框架组件确实不满足需求时才自定义

## nsgablack 组件速查

| 类别 | 数量 | 关键组件 |
|---|---|---|
| Adapter | 23 | de, sa, vns, nsga2, nsga3, spea2, moead, pattern_search, trust_region_dfo/mo_dfo/nonsmooth/subspace, astar, moa_star, mas, gradient_descent, pso, strategy_chain, strategy_router, async_event_driven, single_trajectory_adaptive, multi_role_controller, composite |
| Bias | 66 | **graph**: tsp_constraint, hamiltonian_path, coloring, connectivity, matching, max_flow, shortest_path, sparsity, community, tree, path_constraint, degree_distribution, composite_constraint |
| | | **algorithmic**: cmaes, cmaes_adaptive, pso, pso_adaptive, tabu, levy, convergence*, diversity*, crowding, niche, sharing |
| | | **local**: gradient_descent, line_search, nelder_mead, newton, quasi_newton, trust_region |
| | | **domain**: constraint, feasibility, dynamic_penalty, production*, scheduling, engineering*, risk, safety, time_window, resource_constraint, rule_based, structure_prior, preference |
| | | **surrogate**: surrogate_control, surrogate_phase_schedule, surrogate_uncertainty_budget |
| | | **bayesian**: bayesian_convergence, bayesian_exploration, bayesian_guidance |
| | | **other**: callable, uncertainty_exploration, robustness |

## 案例设计模式

### 标准组合
```text
自定义 Problem 
  + nsgablack RepresentationPipeline (或内置 continuous/permutation)
  + 框架 Adapter (de/sa/vns/nsga2/strategy_chain...)
  + 框架 Bias 组合 (graph + algorithmic + local)
  = 完整案例
```

### 组合案例速查
- **TSP/VRP**: adapter.sa + bias.graph_tsp_constraint + bias.graph_hamiltonian_constraint
- **图着色**: adapter.de + bias.graph_coloring + bias.graph_coloring_constraint
- **因果发现**: adapter.de + bias.graph_sparsity + bias.graph_connectivity + bias.constraint
- **聚类**: adapter.de + ClipRepair/UniformInitializer (内置 representation)
- **GMM**: adapter.de (chain) + bias.local_nelder_mead
- **RANSAC**: adapter.de + bias.callable + bias.constraint (inlier ratio)
- **变点检测**: adapter.de + bias.constraint (sparsity)
- **特征选择**: adapter.de + bias.graph_sparsity

## 关键约定
1. **开工前先查 catalog**：`python -m nsgablack catalog search <关键词>` — 必须首先执行，避免重复造轮子
2. 查看组件详情 + companion：`python -m nsgablack catalog show <key> --profile framework-core`
3. 新案例用：`python -m nsgablack project init examples\cases\<name> --force`
4. **注册到 catalog DB**：编辑 `_default_entries()` 后，`get_catalog(refresh=True)` 自动写入 DB。**禁止只写 `entries.toml`，WebUI 只读 DB。**
5. 不要删除脚手架生成的模板文件，只添加新文件
6. mlblack 侧组件查询：`cd C:\Users\hp\Desktop\mlblack; python -m mlblack catalog search <query>`

## 已有案例 (22个)
| 案例 | 状态 |
|---|---|
| clustering (k-means/k-medians/多目标) | ✅ |
| wrapper_fs (特征选择) | ✅ |
| ransac (稳健回归) | ✅ |
| changepoint_detection (变点检测) | ✅ |
| graph_coloring (图着色) | ✅ |
| automl (自动学习) | ✅ |
| shap (模型解释) | ✅ |
| production_scheduling (生产调度) | ✅ |
| supply_adjustment_nested (嵌套编排) | ✅ |
| l0_distributed_worker (基础设施) | ✅ |
| classification_threshold_calibration | ✅ |
| etf_lane_outer_search | ✅ |
| residual_boosting | ✅ |
| learnable_conv_component_search | ✅ |
| symbolic_kernel_digits_outer_search | ✅ |
| phi_bundle_image_search | ✅ |
| mlblack_nested_scaffold | ✅ |
| mlblack_symbolic_consensus_scaffold | ✅ |
| gmm_em_vs_de | ✅ 已注册 catalog |
| causal_discovery | ✅ 已注册 catalog |
| anomaly_detection | ✅ 已注册 catalog |
| tsp_vrp | ✅ 已注册 catalog |
| arima_order_search | ✅ 已注册 catalog |

## 常用命令
```powershell
# 在 C:\Users\hp\Desktop\nsgablack
python -m nsgablack catalog list --kind <kind> --profile framework-core
python -m nsgablack catalog search <query> --profile framework-core --show-import
python -m nsgablack catalog show <key> --profile framework-core
python -m nsgablack project init examples\cases\<name> --force
python -m nsgablack project doctor --path . --strict --format problem

# 在 C:\Users\hp\Desktop\mlblack
python -m mlblack catalog list --kind <kind>
python -m mlblack catalog search <query> --show-import
python -m mlblack catalog show <key>
python -m mlblack project init examples\cases\<name> --force
python -m compileall -q .
```
