# TAGGED_INDEX — 标签化可搜索目录

用法建议：
- 在 IDE 里搜索 `layer:` / `goal:` / `var:` / `role:` / `cap:`  
- 命令行可用：`rg "layer:multi_agent" docs/indexes/TAGGED_INDEX.md`

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
- `docs/INDEX_MANUAL.md` — 极详细说明书 [layer:docs] [goal:overview]

---

## 核心问题与求解器内核

- `core/base.py` — 黑箱问题接口 [layer:core] [goal:problem]
- `core/solver.py` — NSGA-II 内核 + 偏置注入 [layer:core] [goal:nsga2] [cap:convergence]
- `core/config.py` — 求解器配置 schema（稳定） [layer:core] [goal:config]
- `core/diversity.py` — 多样性初始化 + 历史去重 [layer:core] [cap:diversity] [cap:history]
- `core/elite.py` — 精英保留 + 智能历史 [layer:core] [cap:elite] [cap:history]
- `core/convergence.py` — 收敛检测工具 [layer:core] [cap:convergence]
- `deprecated/legacy/core/problems.py` — 基准问题集合（已归档） [layer:legacy] [goal:benchmark]

---

## 偏置系统（Bias）

- `bias/bias_module.py` — 偏置模块（奖惩 + 约束） [layer:bias] [bias:domain]
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
- `representation/binary.py` — 二进制变量 [layer:representation] [var:binary]
- `representation/permutation.py` — 排列变量 [layer:representation] [var:permutation]
- `representation/matrix.py` — 矩阵变量 [layer:representation] [var:matrix]
- `representation/graph.py` — 图结构变量 [layer:representation] [var:graph]
- `docs/indexes/REPRESENTATION_INDEX.md` — 表征索引 [layer:docs] [goal:index]
- `docs/architecture/representation_pipeline.md` — 表征流水线详解 [layer:docs] [goal:tutorial]

---

## 求解器入口（Core / Experimental / Legacy）

Core（推荐）

- `core/solver.py` — NSGA-II 底座（`BlackBoxSolverNSGAII`）[layer:core] [goal:nsga2]
- `core/blank_solver.py` — 空白底座（`BlankSolverBase`）[layer:core] [goal:custom_workflow]
- `core/composable_solver.py` — Adapter 驱动底座（`ComposableSolver`）[layer:core] [goal:composition]
- `core/adapters/` — 策略内核（VNS/MOEA-D/SA/角色控制等）[layer:core] [goal:adapter]
- `utils/suites/` — 权威组合（attach_* 一键装配）[layer:utils] [goal:suite]

历史/实验目录已清理（降低维护成本）。如需追溯请查看 git 历史。

---

## 多策略并行协同（Multi-Strategy Cooperation / Core）

- `core/adapters/multi_strategy.py` — 多策略主协调 adapter（phase/regions/seeds/共享事实）[layer:core] [goal:multi_strategy]
- `core/adapters/role_adapters.py` — 角色/策略包装（用于给子 adapter 打标签与护栏）[layer:core] [goal:role_adapter]
- `utils/suites/multi_strategy.py` — 权威组合：`attach_multi_strategy_coop` [layer:utils] [goal:suite]

---

## 代理系统（Surrogate / Optional）

推荐：作为“能力层”接入，不污染底座

- `plugins/evaluation/surrogate_evaluation.py` — 代理评估短路插件（`SurrogateEvaluationPlugin`）[layer:utils] [goal:surrogate]
- `utils/surrogate/` — 轻量代理工具（训练/管理/策略的最小实现）[layer:utils] [goal:surrogate]

文档

- `docs/user_guide/surrogate_workflow.md` — 代理流程 [layer:docs] [goal:tutorial]
- `docs/user_guide/surrogate_cheatsheet.md` — 代理速查 [layer:docs] [goal:index]

---

## 工程与性能工具（Utils）

- `utils/parallel/evaluator.py` — 并行评估器 [layer:utils] [cap:parallel]
- `utils/performance/memory_manager.py` — 内存优化器 [layer:utils] [cap:memory]
- `utils/performance/fast_non_dominated_sort.py` — 非支配排序加速 [layer:utils] [cap:performance]
- `utils/engineering/experiment.py` — 实验结果容器 [layer:utils] [cap:tracking]
- `utils/viz/matplotlib.py` — 交互式可视化 [layer:utils] [cap:visualization]
- `utils/analysis/metrics.py` — IGD/HV 指标工具 [layer:utils] [cap:metrics]

---

## 工具脚本（Tools）

- `tools/build_catalog.py` — 目录索引生成 [layer:tools] [goal:index]
- `tools/generate_api_docs.py` — API 文档生成 [layer:tools] [goal:docs]

---

## 示例（Examples）


---

## 其它文档索引

- `docs/indexes/TOOLS_INDEX.md` — 工具索引 [layer:docs] [goal:index]
- `docs/user_guide/bias_system.md` — 偏置系统指南 [layer:docs] [goal:index]
- `docs/concepts/FRAMEWORK_OVERVIEW.md` — 框架总览（当前）[layer:docs] [goal:overview]
- `docs/INDEX_MANUAL.md` — 极详细说明书 [layer:docs] [goal:overview]
