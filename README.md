# NSGABlack

Why complex optimization experiments silently degrade - and how I try to make that visible.

This is an **experimental framework under active design**.
I'm sharing it to discuss ideas, not as a finished product.

算法解构的优化生态框架：把“问题/表示/倾向/策略/工程能力”解耦，让你能更快、更稳地把新点子落地到真实问题上。



你可以把它当成一套工程化的优化搭积木：

- 新业务约束/偏好来了：加 Bias，不动算法
- 评估太慢/要并行/要统一输出口径：加 Plugin，不动算法
- 想换搜索策略/做阶段式融合：换/串 Adapter，不动问题定义
- 容易漏配的组合：用 Suite 一键装配
- 不知道有哪些组件：用 Catalog 搜索

这套解耦带来的直接收益是：扩展更“自然”。你可以把新增功能落在最合适的层级，
而不是改主循环；因此组件可复用、组合代价低、回归风险可控。

## 三条最短路径

1) 只想先跑起来

- `QUICKSTART.md`
- `examples/end_to_end_workflow_demo.py`

2) 想把一个真实问题从 0 到 1 落地（推荐）

- `WORKFLOW_END_TO_END.md`
- `examples/notebooks/workflow_end_to_end_portfolio.ipynb`（Notebook：更像真实问题的可运行示例）

3) 想理解框架并开始扩展（开发者路线）

- `START_HERE.md`
- `docs/concepts/FRAMEWORK_OVERVIEW.md`
- `docs/CORE_STABILITY.md`
- `docs/user_guide/EXTENSION_CONTRACTS.md`

提示：工程高级功能的一页总览在 `START_HERE.md` 的“工程能力地图”。

## 安装与运行（Windows/开发环境）

最推荐：安装为可编辑包（之后你在哪个目录运行都能 import 到）

```powershell
python -m pip install -e .
```

如果你遇到：`No module named nsgablack`

这通常不是框架坏了，而是你当前 `cwd` 让 Python 找不到包。任选一种解决：

1) 仍然推荐：`pip install -e .`（见上）
2) 不安装、快速试用：把父目录加到 `PYTHONPATH`

```powershell
$env:PYTHONPATH=".."
python -m nsgablack catalog search vns
```

3) 直接在父目录运行

```powershell
cd ..
python -m nsgablack catalog search vns
```

## 框架最小闭环（四件套）

这四个是一切组合的地基：

- `Solver`：运行容器与生命周期
- `RepresentationPipeline`：初始化/变异/修复/编码解码（硬约束优先放这里）
- `BiasModule`：软约束/偏好/算法倾向
- `Plugin`：能力层（并行、记录、监控、短路评估等）

在此之上：

- `Adapter`：策略内核（propose/update）
- `Suite`：权威组合（把必配伙伴组件一次装好）

## Catalog：可发现性

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show suite.vns
```

## 权威示例（事实标准）

- `examples/end_to_end_workflow_demo.py`：端到端闭环 + 统一实验口径输出
- `examples/composable_solver_fusion_demo.py`：组合式求解器与阶段式融合
- `examples/multi_strategy_coop_demo.py`：多策略协同/角色化思路的最小演示
- `examples/benchmark_harness_demo.py`：BenchmarkHarnessPlugin（统一实验口径：CSV + summary JSON）
- `examples/surrogate_plugin_demo.py`：SurrogateEvaluationPlugin（减少真实评估次数的能力层演示）

## 文档入口

- `START_HERE.md`：入口地图
- `QUICKSTART.md`：最短上手
- `WORKFLOW_END_TO_END.md`：手把手把真实问题落地
- `docs/guides/DECOUPLING_PROBLEM.md`：解耦对象导读 - Problem/评估/约束
- `docs/guides/DECOUPLING_REPRESENTATION.md`：解耦对象导读 - 表示/算子/修复（硬约束）
- `docs/guides/DECOUPLING_BIAS.md`：解耦对象导读 - 偏置系统（domain/algorithmic/signal-driven）
- `docs/guides/DECOUPLING_CAPABILITIES.md`：解耦对象导读 - Plugin/Suite/Catalog（能力层）
- `docs/AUTHORITATIVE_EXAMPLES.md`：权威示例与参数/命名事实标准
- `docs/CORE_STABILITY.md`：哪些是核心承诺，哪些可变
- `docs/FINAL_DOCUMENTATION_SUMMARY.md`：当前文档收敛摘要
- `docs/FEATURES_OVERVIEW.md`：功能总览（一页版）
- `docs/TODO.md`：待办清单

## 开发与验证

```powershell
pytest -q
```

### Run Inspector（Tk）

用于“运行前审查/开关”的轻量界面（不改算法脚本）：

```powershell
python utils/viz/visualizer_tk.py --entry examples/dynamic_multi_strategy_demo.py:build_solver
```

- 统一入口：`python -m nsgablack run_inspector --entry examples/dynamic_multi_strategy_demo.py:build_solver`
- 缺少必配伙伴组件会高亮提示（不自动装配）
- 使用 Run Inspector 启动时，`ModuleReport` 会写入 `ui_snapshot` 方便复盘
- 详细说明：`docs/user_guide/RUN_INSPECTOR.md`

## 历史与设计故事

如果你想看“为什么会走到今天这套拆分”，原始长文保存在：

- `docs/FRAMEWORK_ORIGIN_STORY.md`

# Catalog search language support

Catalog search supports bilingual (CN/EN) keywords via a lightweight alias map in `catalog/registry.py` (`_expand_token_groups`).
If you add new categories or want better Chinese search hits, update that alias map alongside the catalog entries.
This keeps `python -m nsgablack catalog search <query>` consistent for both Chinese and English users.