# TAGGED_INDEX — 标签化可搜索目录

用法建议：
- 在 IDE 里搜索 `layer:` / `goal:` / `var:` / `role:` / `cap:`  
- 命令行可用：`rg "layer:multi_agent" docs/TAGGED_INDEX.md`

标签说明（非穷尽）：
- layer: 入口层级，如 `core` / `bias` / `representation` / `solver` / `multi_agent` / `surrogate` / `utils` / `tools` / `docs` / `examples`
- goal: 使用目的，如 `nsga2` / `surrogate` / `multi_agent` / `representation` / `bias` / `validation` / `tutorial` / `index`
- var: 变量类型，如 `continuous` / `integer` / `binary` / `permutation` / `matrix` / `graph`
- role: 角色，如 `explorer` / `exploiter` / `waiter` / `advisor` / `coordinator`
- bias: 偏置类型，如 `algorithmic` / `domain` / `surrogate` / `template`
- cap: 能力点，如 `diversity` / `archive` / `history` / `convergence` / `parallel` / `memory` / `visualization` / `scoring` / `region` / `metrics`

---

## 入口与导览

- `START_HERE.md` — 入口地图 [layer:docs] [goal:index]
- `README.md` — 项目总览 [layer:docs] [goal:overview]
- `__init__.py` — 对外入口聚合 [layer:entry] [goal:api]
- `__main__.py` — 脚本入口 [layer:entry] [goal:cli]
- `docs/user_guide/external_api_navigation.md` — 外部入口清单 [layer:docs] [goal:api]
- `docs/PROJECT_DETAILED_OVERVIEW.md` — 极详细说明书 [layer:docs] [goal:overview]

---

## 核心问题与求解器内核

- `core/base.py` — 黑箱问题接口 [layer:core] [goal:problem]
- `core/solver.py` — NSGA-II 内核 + 偏置注入 [layer:core] [goal:nsga2] [cap:convergence]
- `core/base_solver.py` — 求解器基础流程 [layer:core] [goal:solver]
- `core/diversity.py` — 多样性初始化 + 历史去重 [layer:core] [cap:diversity] [cap:history]
- `core/elite.py` — 精英保留 + 智能历史 [layer:core] [cap:elite] [cap:history]
- `core/convergence.py` — 收敛检测工具 [layer:core] [cap:convergence]
- `core/problems.py` — 基准问题集合 [layer:core] [goal:benchmark]

---

## 偏置系统（Bias）

- `bias/bias.py` — 偏置模块（奖惩 + 约束） [layer:bias] [bias:domain]
- `bias/bias_base.py` — 偏置基类 [layer:bias] [bias:base]
- `bias/bias_v2.py` — 新版偏置接口 [layer:bias] [bias:base]
- `bias/core/base.py` — OptimizationContext 与偏置协议 [layer:bias] [cap:context]
- `bias/algorithmic/` — 算法偏置库 [layer:bias] [bias:algorithmic]
- `bias/domain/` — 业务偏置库 [layer:bias] [bias:domain]
- `bias/surrogate/` — 代理控制偏置 [layer:bias] [bias:surrogate]
- `bias/template_function_bias.py` — 函数偏置模板 [layer:bias] [bias:template]
- `bias/algorithmic/template_algorithmic_bias.py` — 算法偏置模板 [layer:bias] [bias:template]
- `bias/domain/template_domain_bias.py` — 业务偏置模板 [layer:bias] [bias:template]
- `bias/surrogate/template_surrogate_bias.py` — 代理偏置模板 [layer:bias] [bias:template]

---

## 表征系统（Representation）

- `utils/representation/base.py` — RepresentationPipeline [layer:representation] [goal:representation]
- `utils/representation/continuous.py` — 连续变量 [layer:representation] [var:continuous]
- `utils/representation/integer.py` — 整数变量 [layer:representation] [var:integer]
- `utils/representation/binary.py` — 二进制变量 [layer:representation] [var:binary]
- `utils/representation/permutation.py` — 排列变量 [layer:representation] [var:permutation]
- `utils/representation/matrix.py` — 矩阵变量 [layer:representation] [var:matrix]
- `utils/representation/graph.py` — 图结构变量 [layer:representation] [var:graph]
- `docs/REPRESENTATION_INDEX.md` — 表征索引 [layer:docs] [goal:index]
- `docs/architecture/representation_pipeline.md` — 表征流水线详解 [layer:docs] [goal:tutorial]

---

## 求解器入口（Solvers）

- `solvers/nsga2.py` — NSGA-II 实现 [layer:solver] [goal:nsga2]
- `solvers/surrogate.py` — 代理辅助 NSGA-II [layer:solver] [goal:surrogate]
- `solvers/surrogate_interface.py` — 预筛选/评分偏置/替代评估统一接口 [layer:solver] [goal:surrogate]
- `solvers/multi_agent.py` — 多智能体求解器入口 [layer:solver] [goal:multi_agent]
- `solvers/moead.py` — MOEA/D [layer:solver] [goal:multi_objective]
- `solvers/monte_carlo.py` — Monte Carlo [layer:solver] [goal:search]
- `solvers/vns.py` — 变邻域搜索 [layer:solver] [goal:search]
- `solvers/bayesian_optimizer.py` — 贝叶斯优化 [layer:solver] [goal:bayesian]
- `solvers/hybrid_bo.py` — 混合贝叶斯策略 [layer:solver] [goal:bayesian]

---

## 多智能体（Multi-Agent）

- `multi_agent/README.md` — 多智能体说明 [layer:multi_agent] [goal:overview]
- `multi_agent/core/role.py` — 角色定义 [layer:multi_agent] [role:explorer] [role:advisor]
- `multi_agent/components/communication.py` — 信息共享 [layer:multi_agent] [cap:communication]
- `multi_agent/components/archive.py` — 多层档案 [layer:multi_agent] [cap:archive]
- `multi_agent/components/scoring.py` — 角色评分 [layer:multi_agent] [cap:scoring]
- `multi_agent/components/advisor.py` — Advisor 候选生成 [layer:multi_agent] [role:advisor]
- `multi_agent/components/region.py` — 区域划分 [layer:multi_agent] [cap:region]
- `multi_agent/strategies/` — 搜索策略模块 [layer:multi_agent] [goal:strategy]
- `multi_agent/bias/` — 多智能体偏置 [layer:multi_agent] [bias:algorithmic]

---

## 代理系统（Surrogate）

- `surrogate/base.py` — 代理基础接口 [layer:surrogate] [goal:surrogate]
- `surrogate/trainer.py` — 训练/复训 [layer:surrogate] [cap:training]
- `surrogate/evaluators.py` — 评估/筛选 [layer:surrogate] [cap:evaluation]
- `surrogate/strategies.py` — 采样/更新策略 [layer:surrogate] [cap:strategy]
- `surrogate/manager.py` — 生命周期管理 [layer:surrogate] [cap:manager]
- `surrogate/features.py` — 特征处理 [layer:surrogate] [cap:features]
- `docs/user_guide/surrogate_workflow.md` — 代理流程 [layer:docs] [goal:tutorial]
- `docs/user_guide/surrogate_cheatsheet.md` — 代理速查 [layer:docs] [goal:index]

---

## 工程与性能工具（Utils）

- `utils/parallel_evaluator.py` — 并行评估器 [layer:utils] [cap:parallel]
- `utils/memory_manager.py` — 内存优化器 [layer:utils] [cap:memory]
- `utils/fast_non_dominated_sort.py` — 非支配排序加速 [layer:utils] [cap:performance]
- `utils/experiment.py` — 实验结果容器 [layer:utils] [cap:tracking]
- `utils/visualization.py` — 交互式可视化 [layer:utils] [cap:visualization]
- `utils/metrics.py` — IGD/HV 指标工具 [layer:utils] [cap:metrics]

---

## 工具脚本（Tools）

- `tools/build_catalog.py` — 目录索引生成 [layer:tools] [goal:index]
- `tools/generate_api_docs.py` — API 文档生成 [layer:tools] [goal:docs]

---

## 示例（Examples）

- `examples/validation_smoke_suite.py` — 全模块冒烟验证 [layer:examples] [goal:validation]
- `examples/representation_comprehensive_demo.py` — 表征全集 [layer:examples] [goal:representation]
- `examples/tsp_representation_pipeline_demo.py` — TSP 表征 [layer:examples] [var:permutation]
- `examples/multi_agent_bias_quickstart.py` — 多智能体快速入门 [layer:examples] [goal:multi_agent]
- `examples/benchmark_zdt_dtlz_igd_hv.py` — ZDT/DTLZ 基准 + IGD/HV [layer:examples] [goal:benchmark]
- `examples/bayesian_optimization_example.py` — 贝叶斯优化示例 [layer:examples] [goal:bayesian]

---

## 其它文档索引

- `docs/PROJECT_CATALOG.md` — 项目目录索引 [layer:docs] [goal:index]
- `docs/TOOLS_INDEX.md` — 工具索引 [layer:docs] [goal:index]
- `docs/BIAS_INDEX.md` — 偏置索引 [layer:docs] [goal:index]
- `docs/EXAMPLES_INDEX.md` — 示例索引 [layer:docs] [goal:index]
- `docs/FRAMEWORK_OVERVIEW.md` — 框架总览 [layer:docs] [goal:overview]
- `docs/PROJECT_DETAILED_OVERVIEW.md` — 极详细说明书 [layer:docs] [goal:overview]
