# 功能总览（NSGABlack）

本文档汇总当前框架的主要功能与能力边界，便于快速对外说明与团队协作。

---

## 1. 核心架构能力

- **Problem 接口**：统一问题定义与评估接口（evaluate / bounds / objectives）
- **RepresentationPipeline**：初始化 / 变异 / 修复 / 编码解码（硬约束优先）
- **BiasModule**：软约束与偏好驱动（domain / algorithmic / signal-driven）
- **Adapter**：策略内核（可替换、可组合）
- **Plugin**：能力层（并行、统计、监控、短路、归档）

---

## 2. 可组合与协同能力

- **多策略协同**：MultiStrategyControllerAdapter（本质是“多策略提案者 + 统一评估/归档/调度”，共享状态 + 动态预算）
- **多算法并行/阶段协作**：支持探索-精修阶段调度
- **Suite 权威组合**：必配组件一键装配，避免漏配
- **Catalog 可发现性**：search/show/list + companions 伙伴提示

---

## 3. 运行前/运行中/运行后闭环

- **Run Inspector（Tk）**：运行前审查 wiring，开关偏置/管线/插件
- **ModuleReport**：输出模块清单与偏置贡献报告
- **BenchmarkHarness**：统一实验口径（progress.csv / summary.json）
- **快照审计**：UI snapshot 写入报告，便于复盘配置
- **Run Inspector 说明书**：`docs/user_guide/RUN_INSPECTOR.md`

---

## 4. 偏置系统（Bias）

- **领域偏置（Domain）**：软约束/业务规则/可行性偏好
- **算法偏置（Algorithmic）**：退火/多样性/收敛/搜索倾向等
- **信号驱动偏置**：依赖统计信号（需配评估/统计插件）
- **可开关/可组合**：支持运行时启用/禁用与权重调节

---

## 5. 插件系统（Plugins）

- **并行评估**：多后端并行（含 Ray）
- **统计评估**：MonteCarloEvaluationPlugin
- **Pareto 归档**：全局非支配解集维护
- **Profiler**：性能剖析
- **Adaptive / Convergence / Elite**：自适应、收敛监控、精英保留
- **Dynamic Switch**：动态切换（软/硬切换基类）

---

## 6. 表征与约束能力

- 支持连续 / 整数 / 二进制 / 排列 / 图 / 矩阵等表征
- 约束优先前置到 pipeline（repair/init/mutate）
- 支持上下文驱动 mutation / repair

---

## 7. 工程与可扩展能力

- **扩展契约**：Extension Contracts 保证 API 一致性
- **工程基础设施**：配置/日志/运行结构化输出
- **工具集**：Catalog 构建、API 文档生成、清理脚本

---

## 8. 示例与案例

- 动态多策略协同示例（多策略提案者 + 统一评估/归档/调度）
- 端到端 workflow 示例
- 鲁棒性评估示例（MonteCarlo + DP）
- 生产调度案例

---

## 9. 统一入口（便于使用）

- Run Inspector：
  - `python utils/viz/visualizer_tk.py --entry path/to/script.py:build_solver`
  - `python -m nsgablack run_inspector --entry path/to/script.py:build_solver`
- Catalog：
  - `python -m nsgablack catalog search <query>`
  - `python -m nsgablack catalog show <key>`

---

## 10. 完全自由的扩展性

只要遵循扩展契约，你可以自己开发任何想要的组件：

- 新的 Adapter（策略内核）
- 新的 Pipeline 组件（初始化 / 变异 / 修复 / 编码）
- 新的 Bias（软约束 / 偏好 / 信号驱动）
- 新的 Plugin（评估 / 并行 / 统计 / 监控 / 报告）

框架鼓励“自定义能力”，而不是被固定算法绑住。

---

## 11. 模块 API / 默认配置速查（更细粒度）

以下为“常用入口 + 关键默认值”的速查，便于快速定位和复现。  
（完整细节以源码为准）

### Problem（问题接口）

- 核心接口：`problem.evaluate(x)`  
- 典型属性：`bounds`、`dimension`、`objectives`  
- 说明：建议保持 evaluate 纯函数；约束优先放进 pipeline 的 repair

对应实现参考：`core/base.py`

### RepresentationPipeline（表征管线）

- 核心方法：`init(problem, context)`、`mutate(x, context)`、`repair(x, context)`  
- 默认值（`representation/base.py`）：  
  - `encoder=None`, `repair=None`, `initializer=None`, `initializers=None`  
  - `max_init_attempts=5`  
  - `validate_constraints=False`, `log_validation_failures=False`  
  - `mutator=None`, `crossover=None`  
  - 工程保护开关：`transactional=False`, `protect_input=False`, `copy_context=False`, `threadsafe=False`

### BiasModule（偏置系统）

- 常用 API：`add(bias, weight=1.0)`、`compute_bias(...)`、`compute_bias_vector(...)`  
- 默认值（`bias/bias_module.py`）：  
  - `enable=True`  
  - `cache_enabled=True`, `cache_max_items=128`  
  - `history_best_f=inf`, `history_best_x=None`

### Solver 入口（两大主入口）

- 传统 NSGA-II：`core/solver.py` → `BlackBoxSolverNSGAII`  
- 组合求解器：`core/composable_solver.py` → `ComposableSolver`  
  - `adapter` 可替换、支持多策略协同  
  - 默认会调用 pipeline repair（若设置）

### Adapter（策略内核）

- 典型接口：`setup(solver)` / `propose(solver, context)` / `update(...)`  
- 多策略协同：`core/adapters/multi_strategy.py`（Strategy/Adapter 的编排框架）  
  - `StrategySpec(name, adapter, weight, enabled=True)`  
  - `MultiStrategyConfig(total_batch_size, adapt_weights, phase_schedule, ...)`

### Plugin（能力层）

- 基类：`utils/plugins/base.py` → `Plugin`  
- 核心生命周期：`on_solver_init` / `on_generation_end` / `on_solver_finish`

常用插件默认配置：

- `BenchmarkHarnessPlugin`（`utils/plugins/benchmark_harness.py`）  
  - `output_dir="runs"`  
  - `run_id="run"`  
  - `log_every=1`, `flush_every=10`, `overwrite=False`

- `ModuleReportPlugin`（`utils/plugins/module_report.py`）  
  - `output_dir="runs"`  
  - `run_id="run"`  
  - `write_bias_markdown=True`

- `SensitivityAnalysisPlugin`（`utils/plugins/sensitivity_analysis.py`）  
  - `output_dir="runs/sensitivity"`  
  - `run_id="sensitivity"`  
  - `patch_benchmark_run_id=True`

### Run Inspector（运行前审查）

- `utils/viz/visualizer_tk.py`  
  - 开关偏置 / 管线 / 插件  
  - 缺失伙伴提示（companions）  
  - 运行结果快照（ui_snapshot）
  - 详细说明：`docs/user_guide/RUN_INSPECTOR.md`

---

如果需要“更严格的 API 索引版”，可进一步拆出：  
`docs/indexes/` + `docs/user_guide/` 专门对应每类模块。  
已提供严格索引：`docs/indexes/API_INDEX.md`。

