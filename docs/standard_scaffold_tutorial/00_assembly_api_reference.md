# 00. Assembly API Reference

This page defines the formal assembly surface for the shared Project/Case substrate.

## 1) Case primary entry

| `.case kind` | Primary assembly | Primary run |
| --- | --- | --- |
| `solver` | `build_solver.py:build_solver()` | `run_solver.py` |
| `trainer` | `build_trainer.py:build_trainer()` | `run_trainer.py` |

Rules:
- One case exposes exactly one primary build entry and one primary run entry.
- Project runner resolves entry by `.case kind` (no fallback guessing).
- Doctor reports dual primary entries as errors.

## 2) Pipeline contract (new baseline)

- A case has one pipeline entry: `pipeline/main.py` (or legacy `pipeline.py`).
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
