# 难题案例 C：不确定性稳健优化（逐行版）

目标：
- 昂贵评估场景可落地
- 插件链支持缓存/代理/多保真/容错
- 结果可审计（每次评估走了哪条路径）

---

## 1) 推荐统一字段
- `metrics.mc_mean`
- `metrics.mc_std`
- `metrics.surrogate_std`
- `evaluation_count`

---

## 2) Plugin：评估路径归因
```python
class EvalPathTracePlugin(Plugin):  # 评估路径追踪插件
    name = "eval_path_trace"  # 插件名

    context_requires = ()  # 不强依赖字段
    context_provides = ("metrics.eval_path",)  # 声明提供路径字段
    context_mutates = ("metrics.eval_path",)  # 声明会更新该字段
    context_cache = ()  # 不缓存
    context_notes = ("Track cache/surrogate/fidelity path per evaluation.",)  # 说明

    def on_evaluation_end(self, solver, x, value, context=None):  # 每次评估后触发
        _ = solver  # 当前示例不直接使用 solver
        _ = x  # 当前示例不直接用 x
        _ = value  # 当前示例不直接用 value
        ctx = context or {}  # 防御空 context
        metrics = dict(ctx.get("metrics", {}))  # 复制 metrics
        path = metrics.get("eval_path", [])  # 读取路径
        if not isinstance(path, list):  # 类型兜底
            path = []  # 重建列表
        path.append({"node": "fidelity_high", "reason": "fallback"})  # 追加路径节点（示例）
        metrics["eval_path"] = path  # 回写
        return {"metrics": metrics}  # 返回 context 增量
```

---

## 3) Bias：稳健偏好（惩罚高方差）
```python
class RobustnessBias(Bias):  # 稳健偏置
    name = "robustness_penalty"  # 名称

    requires_metrics = ("metrics.mc_std",)  # 指标依赖
    metrics_fallback = "neutral"  # 缺失指标时不加偏置

    def compute(self, x, context=None):  # 计算偏置
        _ = x  # 当前示例不直接看 x
        metrics = (context or {}).get("metrics", {})  # 读取 metrics
        std = float(metrics.get("mc_std", 0.0))  # 方差指标
        return 0.8 * std  # 方差越大惩罚越重
```

---

## 4) 接线顺序
1. 先挂评估链插件（缓存/代理/多保真）
2. 再挂路径归因插件（可审计）
3. 最后挂稳健偏置（消费 metrics）

---

## 5) 验收标准
- `project doctor --build` 无契约告警
- Context 页面能看到 `metrics.*`
- Catalog 能按字段反查 provider / consumer
