# 00. 统一装配 API 参考

本页定义共享 Project/Case substrate 的正式装配面。

## 1）Case 唯一规范入口

| `.case kind` | 规范装配入口 | 规范运行入口 |
| --- | --- | --- |
| `solver` | `build_solver.py:build_solver()` | `run_solver.py` |
| `trainer` | `build_solver.py:build_solver()` | `run_solver.py` |

规则：
- 每个 Case 只有一个规范 builder 和一个规范 CLI/debug 入口。
- `.case kind` 只区分领域语义和结果投影，不改变入口解析。
- `build_trainer.py` 与 `run_trainer.py` 如存在，只能是薄别名。
- Doctor 必须拒绝包含第二份装配逻辑的别名文件。

## 2) Pipeline contract (new baseline)

- Case 只有一个 pipeline 入口：`pipeline/main.py`。
- `pipeline` is a flow-level assembly surface, not a flat component list.
- Fine-grained logic (mutate/repair/codec/head/etc.) is implemented as internal operators and assembled by the pipeline entry.

Recommended structure:

```text
pipeline/
  main.py
  operators/
    mutate/
    repair/
    codec/
    head/
    ...
```

## 3) Project entry

| File | Role |
| --- | --- |
| `project_config.py` | stages/groups/resource requests |
| `run_project.py` | formal project runner entry (orchestration + L0 grants) |

## 4) Standard build signatures

```python
def build_solver(config=None, *, resource_context=None, component_overrides=None): ...
def build_trainer(config=None, *, resource_context=None, component_overrides=None): ...
```

## 5) Resource rule

- Case may declare resource request.
- Project-level L0 grants the effective `ResourceContext`.
- Case does not own global lease or allocator.
