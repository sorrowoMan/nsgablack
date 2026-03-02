# ALGORITHM_DECOMPOSITION_HANDS_ON: 手把手教你把一个问题接入框架

这篇文档是“跟着做就能跑起来”的版本。  
目标不是讲概念，而是回答这几个实际问题：

1. 一个问题进入框架后，到底要做什么。
2. 每一层应该放什么，不应该放什么。
3. 运行后会产出什么，以及怎么验证。
4. 出问题时先查哪里。

如果你只有 20 分钟，请先看：

- `START_HERE.md`
- `WORKFLOW_END_TO_END.md`
- `docs/user_guide/RUN_INSPECTOR.md`

---

## 0. 先定“你要交付什么”

不要一上来就写算法。先定交付物：

1. 可运行的求解入口（`build_solver()` + 可执行脚本）
2. 可审计的组件接线（Catalog/Doctor 可识别）
3. 可解释的运行产物（run 快照、报告、序列/时序）
4. 可复现的实验条件（参数、种子、版本）

如果你能稳定产出这四个，框架就算接入成功。

---

## 1. 脑内地图：六层结构（你现在最需要记住这个）

1. `Problem`：目标与约束定义。
2. `Pipeline`：初始化、变异、修复（硬约束）。
3. `Adapter`：搜索流程（`propose/update`）。
4. `Bias`：软偏好（奖励/惩罚/方向性）。
5. `Plugin`：工程能力（日志、报告、追踪、并行、恢复）。
6. `Data Plane`：`Context` + `Snapshot`。

放错层会直接带来维护灾难。下面是最常见的错法：

- 把修复写进 Adapter。
- 把偏好写进 evaluate 或算法循环。
- 把统计 I/O 写进核心搜索代码。
- 把大对象塞进 Context。

---

## 2. 一次完整接入的标准步骤（按顺序做，不跳步）

### 2.1 初始化项目骨架

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
```

先过 `doctor --build --strict`，再写业务代码。

### 2.2 定义 Problem（只做语义，不做流程）

你至少要明确：

- 决策变量维度与边界。
- `evaluate(x)` 的目标值定义。
- `evaluate_constraints(x)` 的硬约束定义。

注意：

- `evaluate` 不要做修复。
- `evaluate` 不要夹杂偏好惩罚。
- `evaluate` 不要做外部 I/O。

### 2.3 搭 Pipeline（硬约束只放这里）

至少实现三件事：

- `initializer`：初始解生成。
- `mutator`：邻域/扰动。
- `repair`：合法域修复。

原则：

- 同一问题的硬约束修复只写一份，所有 Adapter 共用。

### 2.4 选择 Adapter（搜索过程只放这里）

先选一个你能解释清楚的 Adapter：

- NSGA2 / SA / VNS / Multi-Strategy 等。

Adapter 只做流程决策，不负责业务偏好与修复细节。

### 2.5 挂 Bias（软偏好，不动硬约束）

如果你有“更偏向某类解”的需求，用 Bias 表达。  
不要把偏好散落在 Adapter 和 evaluate 里。

### 2.6 挂 Plugin（可观测 + 可审计）

建议默认挂：

- benchmark/module_report/decision_trace/sequence_graph

这样你后续排障有证据链，不靠猜。

### 2.7 组装 `build_solver()`（只做装配）

`build_solver()` 里只做 wiring，不做重计算。  
特别是 UI 场景，`Load` 会调用 `build_solver()`。

重任务应该延迟到：

- `run()`
- 首次 `evaluate()`

---

## 3. 运行前检查：你应该看哪些信号

### 3.1 Contract / Catalog 检查

```powershell
python -m nsgablack project doctor --path . --strict
python -m nsgablack catalog search <keyword>
```

你要确认：

- 组件已注册且可加载。
- 关键字段契约明确（requires/provides/mutates）。

### 3.2 Run Inspector 检查

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

你要重点看：

- 接线是否齐全。
- Health 是否有 WARN。
- Context 字段提供方/消费方是否一致。

---

## 4. 运行后你会得到什么（产物分层）

### 4.1 控制面小字段：Context

适合放：

- 小状态、信号、引用键、契约字段。

不适合放：

- `population/objectives/violations` 这类大对象。

### 4.2 数据面大对象：Snapshot

适合放：

- 大体量与高频读写数据。

读取方式：

- `solver.read_snapshot()`
- `Plugin.resolve_population_snapshot()`

写回方式：

- `Plugin.commit_population_snapshot()`

### 4.3 观测产物

你应能看到：

- run 快照（组件接线与结构）
- module/benchmark 报告
- decision trace
- sequence graph（`List/Trie/Trace`）

---

## 5. 为什么要 `Context` 和 `Snapshot` 分层

1. 性能：Context 小字段高频，Snapshot 大对象专门优化。
2. 清晰：契约通信与数据载体分离，边界明确。
3. 复现：Snapshot 按 key 回读，更容易做回放与审计。
4. 协作：团队只通过契约键交互，不直接耦合内部状态。

一句话：

- `Context` 管“谁要什么信号”。
- `Snapshot` 管“真实大数据放哪里”。

---

## 6. 最容易踩的坑（按严重度）

1. `build_solver()` 里做重计算，导致 UI Load 卡死。
2. 插件直接写 `solver.population` 等镜像字段。
3. 把惩罚写进 Adapter，导致“换算法就重写”。
4. 把修复写进 evaluate，导致口径漂移。
5. 有 `snapshot_key` 但后端数据已过期，读取失败。

对应排查入口：

- `Doctor --strict`
- Run Inspector 的 `Context/Doctor/Sequence/Trace`
- run 产物中的 schema/version 与 key 引用

---

## 7. 一套你可以直接照抄的接入节奏

1. 先只接 `Problem + Pipeline + 一个 Adapter`，不加 Bias。
2. 跑通并记录 baseline。
3. 再逐个加 Bias，每次只加一个。
4. 最后加 Plugin 观测套件，固定输出口径。
5. 用 Inspector 比较结构差异，确认“只改了你计划改的部分”。

这个节奏的核心价值：

- 你能回答“变好到底是谁带来的”。

---

## 8. 进阶：什么时候考虑数据资产化

当你出现这些信号，就该进入数据治理阶段：

- run 数量明显增多，结果难追踪。
- 团队共享实验结论时频繁“对不上版本”。
- 复现实验需要人工拼文件。

这时你再引入：

- Artifact Manifest
- schema version + migration
- 元数据索引与血缘关系

不要过早重工程，也不要过晚补治理。

---

## 9. 你每次接入都要回答的 10 个问题

1. 这个问题的硬约束在哪里定义并修复？
2. 这个算法核心动作属于哪个层？
3. 偏好是否与算法流程解耦？
4. 大对象是否都通过 Snapshot 流转？
5. Context 字段是否都是 canonical key？
6. `build_solver()` 是否只做 wiring？
7. 运行后是否有完整观测证据链？
8. 是否能在不改其他层的前提下替换 Adapter？
9. 是否能在固定 Adapter 时单独验证 Bias 效果？
10. 你的改动是否能被 Inspector/Doctor 清楚解释？

能稳定答出这 10 条，你就不是“会跑框架”，而是“会用框架做研究”。

---

## 10. 参考阅读顺序

1. `START_HERE.md`
2. `WORKFLOW_END_TO_END.md`
3. `docs/user_guide/CONTEXT_CONTRACTS.md`
4. `docs/user_guide/REDIS_CONTEXT_SNAPSHOT_WORKFLOW.md`
5. `docs/user_guide/RUN_INSPECTOR.md`
6. `docs/guides/DECOUPLING_*.md`

最后一句：

你不是在“接入一个算法”，你是在构建“可复现、可比较、可演进”的实验系统。  
只要你坚持层次边界，框架会越用越顺。
