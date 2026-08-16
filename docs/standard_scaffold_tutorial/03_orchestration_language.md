# 03. Orchestration Language

This chapter defines orchestration ownership and vocabulary.

## 1) Ownership Boundary

| Concern | Owner |
| --- | --- |
| Project stages/groups/parallel fanout | shared Project substrate |
| global resource grants | shared Project L0 substrate |
| search strategy semantics | `nsgablack` case semantics |
| ML training/data/model semantics | `mlblack` case semantics |

So: orchestration is shared substrate capability, not private framework logic.

## 2) Case-Level Flow vs Project-Level Orchestration

Case-level pipeline flow:

- defined in one `pipeline/main.py`
- composed by internal slot operators
- can be `serial/parallel/router` inside pipeline

Project-level orchestration:

- stage order
- multi-case dependencies
- nested case invocation
- resource grant and namespace

## 3) Entry Resolution By `.case kind`

- `solver` -> `build_solver.py` + `run_solver.py`
- `trainer` -> `build_trainer.py` + `run_trainer.py`

No fallback guessing.

## 4) Nested Standard Case Contract

Outer case calls inner case with structured payload:

- candidate / input payload
- budget hints
- component overrides
- child resource context

Inner case returns structured result:

- objectives/violations or trainer metrics
- artifact refs
- audit/resource effective context

## 5) Pipeline Slot 语言（跳转到第 08 章）

Slot-level orchestration modes:

- `serial`
- `parallel`
- `router`

可运行的详细 spec 在 `08_slot_kernel_minimal_spec.md`。
