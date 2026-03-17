# Context Schema & 生命周期分类

本文档说明 `context` 字典的结构设计、生命周期分类规则、以及组件合同声明约定。
核心原则：**所有组件通过 context 交换数据，通过合同声明读写边界。**

---

## 设计决策（核心问答）

### 1) context 怎么分层？什么是 cache / runtime / input？

**每个字段都有一个生命周期分类，区分后可以精确控制序列化和 replay 行为。**

`cache` 类字段（如 legacy population/objectives）是大数组快照，序列化时应丢弃。
现在大对象不再直接进 context，而是写入 SnapshotStore，再通过 `snapshot_key / population_ref` 之类的引用访问。

- 用 `strip_context_for_replay()` 丢弃 **cache 类字段**
- 用 `replay_context(base, events)` 重建

这样保证序列化后的快照可 replay，同时不携带大数组负担。

### 2) context 的字段应该放到哪个分类？不同分类的读写规则不同吗？

**是的，按三种生命周期分类：**

- `cache`：可丢弃快照，replay 时不保留
- `runtime`：运行时动态状态（generation/step/phase）
- `input`：问题/场景的静态输入

### 3) context 字段分类有没有正式的生命周期定义？**有。**

在 `core/state/context_schema.py` 中定义了：
```
input / runtime / derived / cache / output / event
```

可以通过 `get_context_lifecycle()` 查询每个字段的生命周期分类。

---

## 生命周期分类（总览）

| 分类 | 含义 | 示例 |
|------|------|------|
| input | 问题/场景的静态输入 | bounds / constraints / metadata |
| runtime | 运行时动态状态 | generation / step / phase_id |
| derived | 计算得出的中间量 | metrics / convergence_rate |
| cache | 可丢弃快照（不进 replay/序列化） | legacy population / objectives |
| output | 最终产出/引用 | snapshot_key / population_ref / pareto_solutions_ref / sequence_graph_ref |
| event | 事件流记录 | history_ref / context_events |

---

## 常用 API

```python
from nsgablack.core.state import (
    RUNTIME_CONTEXT_SCHEMA,
    validate_context,
    get_context_lifecycle,
    strip_context_for_replay,
    replay_context,
    record_context_event,
)
```

### 1) 验证 context 结构
```python
warnings = validate_context(ctx)
```

### 2) 生命周期分类查询
```python
lifecycle = get_context_lifecycle(ctx)
```

### 3) 事件记录 + replay
```python
record_context_event(ctx, kind="set", key="phase_id", value=2, source="dynamic_switch")
replayed = replay_context(strip_context_for_replay(ctx), ctx.get("context_events", []))
```

---

## 关键约定

- **快照数据应归入 cache 分类**，不要放入 input/runtime。
- **事件应可重放**，不要依赖随机数，要保证 replay 后状态一致。
- 如果组件只需要极简 context，可以使用 `MinimalEvaluationContext`。

---

## State Governance 与 Context 的关系

Context 内的 `population` / `objectives` 字段属于 legacy `cache` 分类（已弃用）。
读写大对象应通过 SnapshotStore + State Governance 函数，而不是直接操作 context：

```python
data = solver.read_snapshot() or {}
pop = data.get("population", [])
obj = data.get("objectives", [])
vio = data.get("constraint_violations", [])
```

详见 `docs/development/DEVELOPER_CONVENTIONS.md`。

---

## 总结

`context` 不只是一个"随便塞东西的 dict"。
它是组件间的**唯一通信介质**。
遵守生命周期分类和合同声明，就能保证：

1. 可 replay（丢弃 cache，保留 runtime）
2. 可审计（Doctor 检查合同完整性）
3. 可组合（组件只依赖声明的字段，不隐式耦合）

