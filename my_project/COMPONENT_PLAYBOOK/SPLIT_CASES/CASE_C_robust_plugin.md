# Case C（稳健优化）- Plugin 逐行批注

目标：把“评估路径归因”做成一等输出，便于审计。

```python
class EvalPathAuditPlugin(Plugin):  # 评估路径审计插件
    name = "eval_path_audit"  # 名称

    context_requires = ()  # 不强依赖
    context_provides = ("metrics.eval_path", "metrics.eval_counters")  # 提供路径和计数器
    context_mutates = ("metrics.eval_path", "metrics.eval_counters")  # 会更新这两个字段
    context_cache = ()  # 不缓存
    context_notes = ("Track guard/cache/surrogate/fidelity decision path and counters.",)  # 说明

    def __init__(self):  # 初始化
        super().__init__(name=self.name)  # 父类初始化
        self._path = []  # 最近路径
        self._counter = {"cache_hit": 0, "surrogate": 0, "fidelity_low": 0, "fidelity_high": 0}  # 计数器

    def on_custom_event(self, event_name: str, payload: dict | None = None):  # 事件钩子（由评估链触发）
        payload = payload or {}  # 防御空 payload
        if event_name == "eval.cache_hit":  # 缓存命中
            self._counter["cache_hit"] += 1  # 计数+1
            self._path.append({"node": "cache_hit", "reason": payload.get("reason", "hit")})  # 记录路径
        elif event_name == "eval.surrogate":  # 走 surrogate
            self._counter["surrogate"] += 1  # 计数+1
            self._path.append({"node": "surrogate", "reason": payload.get("reason", "cheap_estimate")})  # 记录
        elif event_name == "eval.fidelity_low":  # 低保真
            self._counter["fidelity_low"] += 1  # 计数+1
            self._path.append({"node": "fidelity_low", "reason": payload.get("reason", "budget_gate")})  # 记录
        elif event_name == "eval.fidelity_high":  # 高保真
            self._counter["fidelity_high"] += 1  # 计数+1
            self._path.append({"node": "fidelity_high", "reason": payload.get("reason", "fallback")})  # 记录

    def on_context_build(self, context: dict) -> dict:  # context 构建时投影
        metrics = dict(context.get("metrics", {}))  # 复制 metrics
        metrics["eval_path"] = list(self._path[-50:])  # 最近 50 条路径
        metrics["eval_counters"] = dict(self._counter)  # 当前计数器
        context["metrics"] = metrics  # 回写 metrics
        return context  # 返回 context
```

## 重点
- 稳健场景里插件应输出“路径证据”，不只输出最终目标值。
- Run Inspector 可直接看 `metrics.eval_path / metrics.eval_counters`。
