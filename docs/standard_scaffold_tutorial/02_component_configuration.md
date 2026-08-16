# 02. Component Configuration

## 1) Layer boundary

`pipeline` is a flow container. Operators are internal units.

| Layer | Responsibility |
| --- | --- |
| `problem/` | objective/constraint semantics |
| `pipeline/main.py` | one flow entry, slot orchestration |
| `pipeline/operators/*` | fine-grained operators (mutate/repair/codec/head/...) |
| `adapter/` | propose/update strategy |
| `plugins/` | checkpoint/trace/audit/report hooks |
| `runtime/` | requirement/profile/audit (no global allocation) |

## 2) Single pipeline entry rule

- One case keeps one pipeline primary entry.
- Build entry references the pipeline entry, not scattered operator files.
- Operator replacement should be done by pipeline slot wiring/config.

## 3) Resource rule

- Cases can declare resource request intent.
- Project L0 grants final `ResourceContext`.
- Nested cases consume parent-derived context.
