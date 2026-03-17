# Context 字段命名与新增规则

> context_field_schema_name: context_field_schema  
> context_field_schema_version: 2

本规范用于约束 Context 字段治理，避免同义字段漂移、隐式写入和不可审计状态。

## 1. 目标

- 字段可读：看到 key 就能理解语义。
- 字段可追：能定位声明者、写入者、读取者。
- 字段可演进：新增字段不破坏既有组件。

## 2. 命名规则（必须）

- 使用小写蛇形，优先复用 `core/state/context_keys.py` 常量。
- 不允许同义词并存（例如 `obj` 与 `objectives` 同时存在）。
- 不允许随意缩写进入长期代码。
- 新 key 必须先声明常量，再进入组件契约。

## 3. 生命周期规则（必须）

字段需明确生命周期：

- `input`：问题输入或静态配置
- `runtime`：运行时状态
- `cache`：性能缓存，不保证可重放
- `custom`：临时/扩展字段（后续应收敛）

## 3.1 Context vs Snapshot 决策表（必须）

| 数据类型 | 放置位置 | 典型例子 | 说明 |
|---|---|---|---|
| 小字段、控制信号、契约依赖 | Context | `generation`、`phase_id`、`snapshot_key`、`population_ref` | 组件协作与可审计主通道 |
| 大对象、频繁读写数组 | SnapshotStore | `population`、`objectives`、`constraint_violations`、`pareto_*` | 不直接塞入 Context，避免膨胀和后端压力 |
| 需要跨组件共享的大对象 | Context 放引用 + Snapshot 放实体 | `population_ref -> snapshot_key` | Context 只传指针，读取走 `read_snapshot()` |
| 组件私有临时变量 | 组件内部 | 局部缓存、单次中间值 | 不写 Context，不写 Snapshot |

## 4. 组件契约规则（必须）

所有涉及字段读写的组件都要显式声明：

- `context_requires`
- `context_provides`
- `context_mutates`
- `context_cache`
- `context_notes`

`doctor --strict` 与 Run Inspector 会据此审计。

最低模板要求（建议直接复制）：

```python
class MyComponent:
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Explain what/why for context interactions.",)
```

其中 `context_requires/context_provides/context_mutates` 是核心三字段，必须明确写出（可以为空元组）。

## 5. 写入来源规则（必须）

- `last_writer` 必须来自可追踪证据（事件流/投影/构建写入记录）。
- `declared_by` 仅表示“声明写入者”，不能替代真实写入来源。

## 6. 新字段接入流程

1. 在 `context_keys.py` 增加 `KEY_XXX`。
2. 在相关组件补齐 `context_*` 契约。
3. 在 Run Inspector 校验字段可见性与归因。
4. 运行 `project doctor --strict` 与测试。
5. 更新文档/变更记录。

## 7. CI 门禁

CI 需至少包含：

- `tests/test_context_key_alignment.py`
- `tests/test_schema_version.py`
- `python tools/context_field_guard.py --strict`

---

# Context Field Naming and Evolution Rules

This document defines hard governance rules for Context key lifecycle and compatibility.

## Required controls

- Canonical keys must come from `context_keys.py`.
- Every component that touches context must declare explicit contracts.
- Field provenance must be evidence-based (declared vs actual writer separated).
- CI must reject non-canonical key drift.

## Versioning

- `context_field_schema_name = context_field_schema`
- `context_field_schema_version = 2`

When semantics break compatibility, bump schema version and provide migration guidance.
