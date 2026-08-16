# 11. 自定义 Plugin：10 钩子完整实战（nsgablack）

本章是“能直接抄”的插件说明书，覆盖 10 个统一钩子与一个可运行样例。

## 0. 插件定位

Plugin 是能力层，不是算法层。

Plugin 负责：

- 观测
- 审计
- 持久化
- 报告

Plugin 不负责：

- 改写 Adapter 的 propose/update 语义
- 接管 Project 编排

---

## 1. 10 个统一钩子

按生命周期顺序：

1. `on_solver_init(self, solver)`
2. `on_population_init(self, population, objectives, violations)`
3. `on_generation_start(self, generation)`
4. `on_evaluate_start(self, candidate, context=None)`
5. `on_evaluate_end(self, candidate, feedback, context=None)`
6. `on_step(self, solver, generation)`
7. `on_generation_end(self, generation)`
8. `on_solver_finish(self, result)`
9. `on_error(self, error, context=None)`
10. `on_context_build(self, context) -> context`

---

## 2. 创建 Plugin 文件

```powershell
python -m nsgablack project add-component --case my_solver --kind plugin --name trace_audit_plugin
```

---

## 3. 可运行完整样例（10 钩子全实现）

```python
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from nsgablack.plugins.base import Plugin


class TraceAuditPlugin(Plugin):
    context_requires = ()
    context_provides = ("plugin.trace.events",)
    context_mutates = ("metrics.plugin_trace_count",)
    context_cache = ()
    context_notes = "记录关键生命周期事件，并输出轻量审计统计。"

    def __init__(self, name: str = "trace_audit_plugin"):
        super().__init__(name=name, priority=100)
        self.events = []
        self._t0 = None

    def _push(self, event: str, payload: Optional[Dict[str, Any]] = None):
        self.events.append(
            {
                "ts": time.time(),
                "event": event,
                "payload": dict(payload or {}),
            }
        )

    def on_solver_init(self, solver):
        self._t0 = time.time()
        self._push("on_solver_init", {"solver": type(solver).__name__})

    def on_population_init(self, population, objectives, violations):
        n = len(population) if population is not None else 0
        self._push("on_population_init", {"population_size": int(n)})

    def on_generation_start(self, generation: int):
        self._push("on_generation_start", {"generation": int(generation)})

    def on_evaluate_start(self, candidate, context: Optional[Dict[str, Any]] = None):
        self._push("on_evaluate_start", {"has_context": isinstance(context, dict)})

    def on_evaluate_end(self, candidate, feedback, context: Optional[Dict[str, Any]] = None):
        self._push("on_evaluate_end", {"feedback_type": type(feedback).__name__})

    def on_step(self, solver, generation: int):
        self._push("on_step", {"generation": int(generation)})

    def on_generation_end(self, generation: int):
        self._push("on_generation_end", {"generation": int(generation)})

    def on_solver_finish(self, result: Dict[str, Any]):
        elapsed = 0.0 if self._t0 is None else time.time() - self._t0
        self._push("on_solver_finish", {"elapsed_s": float(elapsed)})

    def on_error(self, error: BaseException, context: Optional[Dict[str, Any]] = None):
        self._push("on_error", {"error": f"{type(error).__name__}: {error}"})

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(context or {})
        out.setdefault("plugin.trace.events", len(self.events))
        metrics = dict(out.get("metrics", {}) or {})
        metrics["plugin_trace_count"] = int(len(self.events))
        out["metrics"] = metrics
        return out

    def get_report(self):
        return {
            "events_total": len(self.events),
            "last_event": None if not self.events else self.events[-1]["event"],
        }
```

---

## 4. 在 build_solver 中挂载

```python
from .plugins.trace_audit_plugin import TraceAuditPlugin

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config, resource_context, component_overrides
    solver = make_solver_somehow()
    solver.add_plugin(TraceAuditPlugin())
    return solver
```

---

## 5. 三类插件实战模式

### 5.1 观测型

- trace
- module report
- profiler

重点在低开销与结构化输出。

### 5.2 控制型

- early-stop/budget guard
- timeout guard

重点在严格失败策略与可审计原因。

### 5.3 存储型

- checkpoint
- artifact exporter
- experiment logger

重点在 snapshot/artifact 边界清晰。

---

## 6. 必须遵守的安全线

1. 短路评估必须保证返回 shape 合法。  
2. plugin 异常默认 soft-error，除非显式 strict。  
3. 不把大对象直接写 context。  
4. 不在 plugin 中私建全局资源池。  

---

## 7. 快速自检命令

```powershell
python run_project.py --check --build-check
python -m nsgablack project doctor --path . --build --strict --format problem
```

若是评估链相关 plugin，务必补测：

- 单点评估路径
- 批量评估路径
- plugin 短路路径
