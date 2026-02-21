# NSGABlack

> 先看概览：`OVERVIEW.md`（中文）

为什么复杂优化实验会“悄悄退化”，以及我如何试图让它变得可见。

这是一个 **仍在快速演化中的实验性框架**。

我分享它是为了讨论思想，而不是作为已完成的产品。

算法解构的优化生态框架：把“问题/表示/偏好/策略/工程能力”解耦，让你能更快、更稳地把新点子落地到真实问题上。

你可以把它当成一套工程化的优化搭积木：

- 新业务约束/偏好来了：加 Bias，不动算法
- 评估太慢/要并行/要统一输出口径：加 Plugin，不动算法
- 想换搜索策略/做阶段式融合：换/加 Adapter，不动问题定义
- 容易漏配的组合：用 Suite 一键装配
- 不知道有哪些组件：用 Catalog 搜索

这套解耦带来的直接收益是：扩展更“自然”。你可以把新增功能落在最合适的层级，而不是改主循环；因此组件可复用、组合代价低、回归风险可控。

## 快速开始（推荐）

推荐路径：先创建项目骨架，再开始建模。

```powershell
python -m pip install -e .
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build
python build_solver.py
```

这样做的好处：
- 目录结构固定（problem/pipeline/bias/adapter/plugins）
- 本地组件自动进入 project catalog
- `doctor` 能提前暴露接线与契约问题

如果你只想快速浏览命令和下一步，请看：`QUICKSTART.md`。  
如果你要从零创建新项目，请看：`docs/user_guide/PROJECT_SCAFFOLD.md`。  
如果你想从真实问题落地，请看：`WORKFLOW_END_TO_END.md`。  
如果你想理解并扩展框架，请看：`START_HERE.md`。

## 框架核心组件

这些是一切组合的地基：

- `Problem`：问题本体（目标/约束/评估函数）
- `Solver`：运行容器与生命周期
- `RepresentationPipeline`：初始化/变异/修复/编码解码（硬约束优先放这里）
- `BiasModule`：软约束/偏好/算法倾向
- `Adapter`：策略内核 (propose/update)，ComposableSolver 体系的搜索引擎；BlackBoxSolverNSGAII 已内建搜索逻辑
- `Plugin`：能力层（并行/记录/监控/短路评估等），也支持对接外部存储/数据库（用于实验资产沉淀与检索）

在此之上：

- `Suite`：权威组合（把必配伙伴组件一次装配好）

## Catalog：可发现性

命令行搜索（必须掌握）：

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show suite.multi_strategy
python -m nsgablack catalog search context_requires --field context --kind plugin
python -m nsgablack catalog search add_plugin --field usage --kind plugin
python -m nsgablack catalog add --key bias.my_rule --title MyRule --kind bias --import-path nsgablack.bias.domain.constraint:ConstraintBias --summary "Domain bias: custom rule"
```

项目内搜索（本地 + 全局）：

```powershell
python -m nsgablack project catalog search context_mutates --field context --path . --global
```

UI 搜索（更推荐日常使用）：
- 打开 Run Inspector，切到 `Catalog` Tab
- `Scope` 可选 `all / project / framework`（分别看全部、本地项目组件、框架内组件）
- 在 `Match` 选择 `context`
- 输入关键词（如 `context_requires`、`visualization prior`、`可视化先验`）再选组件

## 权威示例（事实标准）

- `examples/end_to_end_workflow_demo.py`：端到端闭环 + 统一实验口径输出
- `examples/composable_solver_fusion_demo.py`：组合式求解器与阶段式融合
- `examples/multi_strategy_coop_demo.py`：多策略协同/角色化思路的最小演示（本质是“多策略提案者 + 统一评估/归档”的编排）
- `examples/benchmark_harness_demo.py`：BenchmarkHarnessPlugin（统一实验口径：CSV + summary JSON）
- `examples/surrogate_plugin_demo.py`：SurrogateEvaluationPlugin（减少真实评估次数的能力层演示）

## 文档入口

- `docs/INDEX_MANUAL.md`：组件说明书（单文件索引）
- `START_HERE.md`：入口地图
- `QUICKSTART.md`：最短上手
- `docs/user_guide/PROJECT_SCAFFOLD.md`：创建项目骨架（project init / doctor / 本地 catalog）
- `WORKFLOW_END_TO_END.md`：手把手把真实问题落地
- `docs/user_guide/CONTEXT_CONTRACTS.md`：Context 契约（requires/provides/mutates）
- `docs/user_guide/CONTEXT_FIELD_RULES.md`：Context 字段命名与新增规则（命名/注册/生命周期/写入来源）
- `docs/user_guide/PLUGIN_SELECTION.md`：插件选择指南（按场景选插件）
- `docs/user_guide/DB_EVENT_LOGGING.md`：MySQL 事件日志分层与三表 schema（runs/snapshots/context_events）
- `docs/guides/DECOUPLING_PROBLEM.md`：解耦对象导读 - Problem/评估/约束
- `docs/guides/DECOUPLING_REPRESENTATION.md`：解耦对象导读 - 表示/算子/修复（硬约束）
- `docs/guides/DECOUPLING_ADAPTER.md` 解耦对象导读- Adapter（策略内核）
- `docs/guides/DECOUPLING_BIAS.md`：解耦对象导读 - 偏置系统（domain/algorithmic/signal-driven）
- `docs/guides/DECOUPLING_CAPABILITIES.md`：解耦对象导读 - Plugin/Suite/Catalog（能力层）
- `docs/AUTHORITATIVE_EXAMPLES.md`：权威示例与参数/命名事实标准
- `docs/CORE_STABILITY.md`：哪些是核心承诺，哪些可变
- `docs/FEATURES_OVERVIEW.md`：功能总览（一页版）
- `docs/evidence/ONE_PAGE_COMPARISON.md`：一页对比（框架写法 vs 传统写法）
- `docs/evidence/MIN_REPRO_10MIN.md`：10 分钟最小可复现实验包
- `docs/evidence/BASELINE_PROTOCOL.md`：固定基准协议（small/medium/large）
- `docs/changelog/RUN_INSPECTOR_CHANGELOG.md`：Run Inspector UI 变更日志
- `docs/TODO.md`：待办清单

## 开发与验证

```powershell
pytest -q
python tools/catalog_integrity_checker.py --check-usage --strict-usage
python tools/context_field_guard.py --strict
python tools/release/make_v010_repro_package.py --tag v0.10.0
```

### Run Inspector（UI）

Run Inspector 是 NSGABlack 的“结构审计”界面：不是画曲线，而是让你在运行前就看见组件结构与缺失伙伴。

适用场景：
- 多算法/多偏置/多插件组合时，避免“跑完才发现漏配”
- 实验对比时，快速确认两次实验的结构差异
- 运行后复盘：看清楚“当时到底勾选了什么”

界面结构：
- 左侧：Solver/Adapter/Pipeline/Bias/Plugin 的 wiring 列表（可开关）
- 中间：History（实验记录、run_id、结构 hash）
- 右侧：Details/Run/Contribution/Trajectory/Catalog/Context 功能 Tab
- 顶部 `View`：一键切换 `Build(装配)` / `Run(实验)` / `Audit(审计)`（分工视图，非累加）

推荐用法：
- 优先在 `Catalog` Tab 里搜索组件与契约（不用频繁切回命令行）
- 需要脚本化或批处理时，再用命令行 `catalog` 搜索

启动方式：
```powershell
python -m nsgablack run_inspector --entry examples/dynamic_multi_strategy_demo.py:build_solver
```

空启动（先搜索/选组件，再 Load 文件）：
```powershell
python -m nsgablack run_inspector --empty --workspace .
```

详见：`docs/user_guide/RUN_INSPECTOR.md`

