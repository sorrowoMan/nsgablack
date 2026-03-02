# Run Inspector 使用说明（可视化先验 / 运行前审查）

Run Inspector 是 NSGABlack 的“结构审计”界面。
它不是画曲线的 UI，而是让你在运行前就看见 **算法结构、组件搭配、缺失伙伴、实验快照**。
UI 变更记录见：`docs/changelog/RUN_INSPECTOR_CHANGELOG.md`（每次界面行为变化都会追加）。

> 适用场景：
> - 多算法/多偏置/多插件组合时，避免“跑完才发现漏配”
> - 实验对比时，快速确认两次实验的结构差异
> - 运行后复盘：看清楚“当时到底勾选了什么”

---

## 1. 启动方式

```bash
python utils/viz/visualizer_tk.py --entry examples/dynamic_multi_strategy_demo.py:build_solver
```

- `--entry` 指向你的 `build_solver()` 函数。
- 运行后，会读取当前 solver wiring，并展示可开关的组件。

Run Inspector 的 Load 会直接调用 `build_solver()` 构建 wiring。
为避免 UI 加载触发重计算，`build_solver()` 必须只做装配，重任务延迟到 `run()` / `evaluate()`。

空启动模式（先用 Catalog 搜索，再 Load 文件）：

```bash
python -m nsgablack run_inspector --empty --workspace .
```

在 UI 顶部可直接：
- `Load`：选择/输入 `*.py` + 函数名（默认 `build_solver`）后加载
- `Refresh`：代码改动后重新读取当前 entry
- `View`：一键切换工作视图（单击按钮即可）
  - `Build(装配)`：Details / Catalog / Context（找组件与字段对齐）
  - `Run(实验)`：Run / Decision / Sequence / Repro / Contribution / Trajectory / Catalog（执行、回放、复现与对比）
  - `Audit(审计)`：Details / Decision / Sequence / Repro / Context / Doctor / Contribution（排障与治理）
  - 注意：三种视图是**分工视图，不是层层累加**

---

## 2. 界面总览（你会看到什么）

左侧：**结构清单（wiring）**
- Solver / Adapter / Pipeline / Bias / Plugin
- 每个条目可勾选启用/禁用（固定项会灰显）

中间：**History（实验记录）**
- 每次 Run 会写入一条记录
- 自动显示 run_id、状态、结果、结构 hash

右侧：**功能面板（Tabs）**
- Details：单个组件详情 + Health
- Run：运行控制 + Run ID
- Decision：决策路径回放（why/when）
- Sequence：交互顺序图（序列去重，只看结构，不看数值）
- Repro：复现包加载/对比/按包重跑
- Contribution：模块贡献、对比、结构 hash 图谱
- Trajectory：策略权重轨迹（dynamic_switch）
- Catalog：组件搜索入口
- Context：上下文字段生命周期与归因
- Doctor：项目结构/契约体检
  - `Strict` 模式下会额外显示守卫计数：`mirror`（solver 镜像写入）与 `plugin-state`（插件直接访问 solver population/objectives/violations）

---

## 3. 结构清单（wiring）怎么用

### 3.1 勾选 / 取消勾选
- Bias、Pipeline、Plugin 通常可开关
- Adapter 本体通常固定（灰显）
- 多策略协同会显示 `strategy: xxx`

### 3.2 缺失伙伴提示
- 缺失伙伴不会污染列表文本
- 进入 Details 时会显示 **Health: WARN**
- Health 仅在 Details 面板显示（避免噪音）

> 例：Signal-driven bias 没有挂评估插件时，会提示 WARN

---

## 4. 运行与快照

### 4.1 Run ID
- 默认：时间戳
- 也可手动输入，用于区分实验

### 4.2 Seed Override（可选）
- Run 页支持输入 `Seed Override`（可留空）
- 留空：沿用 solver 当前 seed 策略（例如 `seed=None` 的随机模式）
- 填整数：在点击 Run 时先调用 `solver.set_random_seed(seed)` 再开始运行

### 4.3 Snapshot（结构快照）
每次运行会写入：
```
runs/visualizer/<run_id>.json
```
包含：
- adapter / pipeline / bias / plugins
- enabled 状态
- strategies / weights
- structure_hash（结构哈希）

---

## 5. Delta-first 对比（核心功能）

在 Contribution 页 → Compare：
1. 选择两个 run_id
2. 点击 Diff
3. 左侧列表会 **高亮差异项**（淡蓝底）
4. Diff 面板会显示具体差异

这可以直接回答：
> “这两次实验到底差在哪？”

---

## 6. 结构哈希图谱（Structure Hash Map）

Contribution 页新增：
- 按结构 hash 分组
- 快速判断哪些 run 是 **结构等价** 的

用途：
- 发现“重复实验”
- 找出结构相同但结果不同的 run

---

## 7. 交互顺序图（Sequence）

Sequence 页展示“组件交互顺序图”，只关注 **调用顺序**，不关心数值输出。

- 去重逻辑：相同顺序只累计 `count`
- 典型用途：发现短路路径、分支路径、插件抢占导致的流程偏移
- 输出文件：`runs/<run_id>.sequence_graph.json`
- 子标签：`List`（序列列表）、`Trie`（前缀树视图）、`Trace`（并发时序明细）
- Trace 模式：`off/sample/full`（默认 `off`），建议测试/诊断时开启
- Trace 内部视图：`Events`（逐事件）与 `By Thread/Task`（线程/任务聚合）

前置条件：
- 启用 `SequenceGraphPlugin`（默认 observability suite 已包含）

---

## 8. Bias 贡献与趋势

Contribution 页还会显示：
- 每个 bias 的 total / count / avg
- 点击 bias 可查看 per-call / per-generation 细节

这用于回答：
> “是哪个偏置主导了结果？”

---

## 9. 策略权重轨迹（Trajectory）

如果启用了 `dynamic_switch`：
- Trajectory 页会绘制权重变化曲线
- 支持多策略自动扩展

用途：
- 观察策略切换是否合理
- 验证动态协同逻辑

---

## 10. Catalog 搜索（可发现性）

Catalog 页：
- 支持关键词搜索
- 可过滤 kind（suite / bias / adapter / example 等）
- `Scope` 支持 `all / project / framework`（全部 / 本地项目组件 / 框架内组件）
- 选中条目会显示 `How to Use`（适用场景、最小接线、必配组件、配置键、示例入口）
- 选中条目会显示 `Context Contract`（requires/provides/mutates/cache/notes；为空也会显示 `(none)`）
- Context 选中字段后可直接联动：
  - `Providers`：默认打开字段小窗并聚焦提供者（`context_provides + context_mutates`）
  - `Consumers`：默认打开字段小窗并聚焦需求者（`context_requires`）
- Context 还支持 `Window`（非模态），可连续查看字段归因
- 字段小窗支持组件交互：选中组件可查看 `Contract + Catalog Intro`，双击组件可打开主界面 `Details`
- 小窗底部不放操作按钮（保持轻量）；需要搜索时直接回主界面 Catalog
- 字段小窗右侧会显示组件 `Contract + Catalog Intro`（摘要/用途/最小接线），便于不翻源码快速理解

用于快速回答：
> “这个功能到底有没有？”

---

## 11. Context 字段治理（本轮重点）

Context 页现在按 canonical key 做统一显示与联动。重点字段包括：

- 协同调度：`candidate_roles`、`candidate_units`、`unit_tasks`
- 运行状态：`running`、`evaluation_count`
- 参数自适应：`mutation_rate`、`crossover_rate`
- 快照字段：`individual`、`metadata`、`pareto_solutions`、`pareto_objectives`

建议用法：

- 先在 Context 页选字段，看 `declared_by / last_writer`
- 再点 `Providers / Consumers / Window` 做字段级追踪
- 对同一字段做 Catalog 联动，检查是否缺必要组件

配套门禁：

- `project doctor --strict`：结构与契约体检
- `python -m tools.context_field_guard`：非 canonical key 守卫

---

## 12. 常见问题

**Q1：为什么结构哈希为空？**
- 旧快照可能没有 `structure_hash`，现在会自动计算

**Q2：我禁用了某策略，但动态权重还在变？**
- dynamic_switch 输出的是“运行中权重轨迹”
- 如果禁用了 strategy，权重应显示为 off / 0

**Q3：为什么提示 missing suite？**
- Suite 是权威组合入口
- 如果插件本体已启用，不会再提示 suite 缺失

---

## 13. 最重要的正确理解

Run Inspector 不是“好看 UI”，而是：

> **优化实验的结构审计与差异解释系统**

如果你能在运行前确认结构正确，运行后确认结构差异，
你的实验就不再是“凭感觉调参”，而是 **可解释的结构实验**。

---

## 14. 推荐阅读顺序（完整学习路径）

建议按下面顺序看，避免“只会点 UI，不理解结构”：

1. `docs/user_guide/DEPTH_BREADTH_WORKFLOW.md`
   - 先建立框架总图：深度（嵌套层级）+ 广度（多策略协同）。
2. `docs/user_guide/INNER_SOLVER_BACKENDS.md`
   - 再理解内层编排：`InnerSolverPlugin` / `ContractBridgePlugin` / `TimeoutBudgetPlugin`。
3. `docs/user_guide/NUMERICAL_SOLVER_PLUGINS.md`
   - 再看数值求解：`NewtonSolverPlugin` / `BroydenSolverPlugin`。
4. `docs/user_guide/REDIS_CONTEXT_BACKEND.md`
   - 理解 context 后端切换：memory / redis、TTL、容器工作流与常见错误。
5. `examples/nested_three_layer_demo.py` + `examples/nested_three_layer_demo.md`
   - 最后跑通三层示例（L1 -> L2 -> L3，bridge 直写回 L1）。
6. 回到本页（Run Inspector）
   - 用 Catalog/Context/Doctor 验证你的装配是否与契约一致。
