# NSGABlack

为什么复杂优化实验会“悄悄退化”，以及我如何试图让它变得可见。

这是一个 **仍在快速演化中的实验性框架**。

我分享它是为了讨论思想，而不是作为已完成的产品。

算法解构的优化生态框架：把“问题/表示/偏好/策略/工程能力”解耦，让你能更快、更稳地把新点子落地到真实问题上。

如果你和我一样，做优化项目时最怕的是这些情况：

- 代码能跑，但每次结果都像“玄学”。
- 想加并行、日志、checkpoint，最后把算法主循环写乱。
- 改了很多东西，却说不清到底是哪一层带来了变化。

我做 NSGABlack 的目的很直接：

> 让优化项目从“脚本堆叠”变成“可分层、可治理、可复现”的工程系统。

---

## 你先知道这三件事

1. 这不是只比“算法数量”的框架，它更重视“工程可控性”。
2. 你不用一次学完全部概念，先跑通一个最小闭环就行。
3. 跑通后再迭代 Adapter、Bias、Plugin，效率会明显提高。

---

## 我怎么理解这套架构

### 组件分工

- `Solver`：调度和控制面，只负责“组织流程”。
- `Adapter`：搜索策略内核，只负责“怎么搜索”。
- `Pipeline`：初始化、变异、修复，优先承载硬约束。
- `Bias`：软偏好和倾向，不替代硬约束。
- `Plugin`：并行、观测、checkpoint、报告等工程能力。

### 数据分层

- `ContextStore`：小字段、运行信号、引用。
- `SnapshotStore`：population/objectives/violations 等大对象。

### 统一读写入口

- `solver.read_snapshot()`
- `Plugin.resolve_population_snapshot()`
- `Plugin.commit_population_snapshot()`

---

## 2 分钟跑通

先不要想“最优解”，先拿到一次可控运行。

```powershell
python -m pip install -U pip
python -m pip install -e .[dev]
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

我建议你跑完后立刻检查：

1. `build_solver.py` 能否稳定实例化 solver。
2. `doctor --build --strict` 是否没有 error。
3. 能否完整跑完一轮并拿到可读输出。

---

## 按这条顺序迭代

这是我自己长期验证过最稳的顺序：

1. 先定 `Problem`（定义你到底在优化什么）。
2. 再定 `Pipeline`（先保证可行解链路）。
3. 再挂 `Adapter`（先单策略跑通）。
4. 再加 `Bias`（做可解释偏好）。
5. 最后加 `Plugin`（工程能力外置）。

这个顺序的价值是：你每轮都能清楚归因，不会“多处同时变更导致不可解释”。

---

## 我强烈建议你守住的三条规则

1. 组件状态写入统一走 `solver.*` 控制面。
2. 不要直接写 `solver.population/objectives/constraint_violations/...`。
3. 大对象不进 context，context 只存小字段和 refs。

---

## 三条主线（你可以拿它当日常检查表）

### 工作流

`Problem -> Pipeline -> Adapter -> Bias -> Plugin -> Run -> Doctor/Test`

### 数据流

- 大对象走 snapshot
- 小字段走 context
- 访问统一走标准接口

### 组件流

- Solver 调度
- Adapter 搜索
- Pipeline 可行化
- Bias 偏好
- Plugin 能力

---

## 常用命令（我每天都在用）

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show suite.multi_strategy
python -m nsgablack project doctor --path . --strict
python -m pytest -q
```

---

## 文档阅读顺序（按投入产出比）

1. `START_HERE.md`
2. `WORKFLOW_END_TO_END.md`
3. `docs/architecture/README.md`
4. `docs/user_guide/RUN_INSPECTOR.md`
5. `docs/user_guide/DEPTH_BREADTH_WORKFLOW.md`

---

## 最后一句

如果你现在感觉“概念很多”，完全正常。
你先把最小闭环跑通，我再陪你往下拆到多策略协同、深层嵌套、能力治理那一层。
