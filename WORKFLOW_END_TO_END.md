# WORKFLOW_END_TO_END：我在你旁边，带你从 0 到 1 跑通一次

你现在打开这份文档，通常说明一件事：
你已经有优化问题了，但还没有把它做成“可复现、可对比、可持续迭代”的工程流。

我先把目标说清楚：

- 这一轮先不追最优值。
- 先追求闭环可控。
- 闭环稳了，再追性能和效果。

---

## 0. 开始前先对齐目标

我会先让你拿到三个结果：

1. 能稳定启动并跑完。
2. 能复现同一轮结果。
3. 能解释改动来自哪一层。

如果这三件事没有，后面再复杂的策略都会“看起来很努力，实际不可控”。

---

## 1. 第一步：先让项目“能启动”

先直接执行：

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

这一步我会陪你看三个信号：

- `build_solver.py` 能否实例化 solver。
- `doctor --build --strict` 是否无 error。
- 入口脚本是否在 import 阶段做了重计算。

如果失败，不要急着改算法，先把启动链路修干净。

---

## 2. 第二步：先把 Problem 做稳定

现在只做一件事：把 `evaluate(x)` 变成稳定函数。

我的建议（你照做就好）：

- 不在 `evaluate` 里写文件。
- 不在 `evaluate` 里做可视化。
- 不在 `evaluate` 里引入全局副作用。

为什么这么严格：

- 并行时更稳。
- 复现时更稳。
- 后续替换策略不会牵连评估逻辑。

完成标准：

- 同样输入，输出稳定。
- 异常行为可预测。

---

## 3. 第三步：组装 Pipeline（先可行，再优化）

现在上 `initializer / mutator / repair`。

我通常会让你先做两个小检查：

1. 初始化可行率是否足够高。
2. 变异后是否能被 repair 稳定拉回。

这一步要先稳，因为“不可行解泛滥”会让后面所有算法对比失真。

---

## 4. 第四步：挂 Adapter（先单策略）

这一步先不要多策略协同，先接一个策略跑通。

```python
solver.set_adapter(my_adapter)
```

我先看流程正确性，不看最优值：

- `propose -> evaluate -> update` 是否形成闭环。
- 每轮状态变化是否可解释。

闭环成立后，再考虑策略组合。

---

## 5. 第五步：再上 Bias（软偏好）

Bias 建议在策略跑通后再加。
原因很简单：这样你能做清晰归因。

原则始终不变：

- 硬约束放 Pipeline。
- 软偏好放 Bias。

这样后面你换 Adapter，Bias 仍可复用。

---

## 6. 第六步：最后加 Plugin（工程能力层）

到这里再挂工程能力最稳：

- checkpoint
- trace/report
- parallel
- benchmark harness

我为什么放最后：

- 你能确定问题来自能力层还是策略层。
- 算法主逻辑不会被工程细节污染。

---

## 7. 第七步：固定数据路径（关键）

请你和我一起把这条约束固定下来：

- 大对象走 `SnapshotStore`。
- 小字段与信号走 `ContextStore`。

统一读写入口：

- `solver.read_snapshot()`
- `Plugin.resolve_population_snapshot()`
- `Plugin.commit_population_snapshot()`

这条守住了，后续扩展会轻松很多。

---

## 8. 第八步：运行 + 审查 + 回归

按这个顺序执行：

```powershell
python build_solver.py
python -m nsgablack project doctor --path . --strict
python -m pytest -q
```

顺序理由：

- 先看运行行为。
- 再看结构审计。
- 最后看回归稳定。

---

## 9. 你最常见的卡点（我提前给答案）

### 卡点 A：能跑，但结果很飘

优先检查：

- seed 是否固定。
- `evaluate` 是否有隐式副作用。
- 并行是否引入共享状态污染。

### 卡点 B：doctor 报状态写入违规

优先检查：

- 是否直接写了 `solver.population/objectives/...`。
- 是否绕过了 `solver.*` 控制面。

### 卡点 C：改动太多，无法归因

处理方式：

- 回到“一次只改一层”。
- 每轮只改 Adapter 或 Bias 或 Pipeline 其中之一。

---

## 10. 第二轮迭代模板（直接可用）

我自己常用这个节奏：

1. 固定一份基线配置。
2. 每轮只改一个维度。
3. 完整复跑并记录。
4. 再跑 doctor + pytest 复核。
5. 确认无回归后再改下一维。

这样你就能一直保持“结果可解释”。

---

## 最后一句

如果你现在只记住一句话，就记住这句：

> 先让系统可控，再让结果更优。

这不是保守，这是最快的工程路径。
