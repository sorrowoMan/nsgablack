# Plugin System

Plugin 是 NSGABlack 的能力层：它负责并行、记录、监控、缓存等工程能力；它不承载算法策略过程，不写业务规则。

这一页讲的是：
- 什么时候该写 Plugin
- Plugin 读写什么（context keys）
- 如何把“容易漏配的伙伴组件”收敛成 Wiring

## 1. 什么时候用 Plugin

适合 Plugin 的事：
- 并行评估、批处理、线程/进程安全保护
- 统一实验口径输出（progress.csv + summary.json）
- 运行审计与“模块贡献可查”（modules.json + bias.json/bias.md）
- 统计信号写回 context（供 signal-driven bias 使用）
- 观测与治理（日志、追踪、审计、恢复）

不适合 Plugin 的事：
- 策略过程（那是 Adapter：propose/update）
- 硬约束可行化（优先在 RepresentationPipeline：init/mutate/repair）
- 业务偏好/软约束（优先在 BiasModule）

## 2. Plugin 如何通信：context keys

框架把“运行中的事实”都放在 `context`：
- Plugin 读取事实做统计/输出
- Plugin 也可以把新事实写回 context（例如 metrics），供后续组件使用

建议你优先复用 `core/state/context_keys.py` 里的规范 key，避免不同组件各写一套。

## 3. 避免漏配：用 Wiring

真实开发最容易犯的错不是“不会写”，而是“漏配”：
- 少挂一个记录插件 -> 没有可对比数据
- 少挂一个 mutator -> 算法退化但不报错
- 少写一个 context key -> signal-driven bias 失效

因此推荐把“必配组合”收敛成 Wiring，例如：
- `plugin.benchmark_harness`：统一实验口径输出
- `plugin.module_report`：模块清单 + 偏置贡献报告（自动把 artifacts 注入 benchmark summary）
- `adapter.vns` + `repr.context_gaussian` / `repr.context_switch`：VNS 相关的必配伙伴契约

补充：若通过 Run Inspector（`utils/viz/visualizer_tk.py`）启动，ModuleReport 会自动写入 `ui_snapshot`（包含 wiring 快照与路径），便于复盘“运行前到底勾选了什么”。

## 4. Catalog：发现你有哪些 Plugin/Wiring

```powershell
python -m nsgablack catalog search plugin
python -m nsgablack catalog search plugin
python -m nsgablack catalog show plugin.benchmark_harness
python -m nsgablack catalog show plugin.module_report
```

如果你遇到 `No module named nsgablack`：

```powershell
python -m pip install -e .
```

或快速试用：

```powershell
$env:PYTHONPATH=".."
python -m nsgablack catalog search plugin
```

## 5. Bias 统一 apply 规则（L4 provider 必读）

核心原则：**Bias 在每个候选解的评估生命周期中只 apply 一次。**

对于普通插件，Bias 由求解器主循环统一 apply（NSGA-II 在 `_evaluate_individual` 内部、ComposableSolver 在 evaluate step）。

对于 L4 `EvaluationProvider`（如 surrogate provider），由于 provider 进入评估中介链，关键约束是：

- `_true_evaluate()` 内部**不得** apply bias，只返回 raw objectives
- 调用并行评估器时传入 `enable_bias=False, bias_module=None`
- 训练代理模型的数据必须存储 raw objectives（未偏置）
- Bias apply 只发生在统一评估链中，且**仅此一次**

这样保证无论走原生 problem 评估还是 L4 provider，bias 都恰好 apply 一次，不会 double-bias。

> 参考：`docs/development/DEVELOPER_CONVENTIONS.md` 第 3 节

## 6. 参考入口

- 端到端流程：`WORKFLOW_END_TO_END.md`
- Catalog/Wiring Helpers：`docs/user_guide/catalog.md`
- 解耦导读：`docs/guides/DECOUPLING_CAPABILITIES.md`

## 7. OpenTelemetry tracing 插件（可选）

用于把关键运行路径变成 trace span（`evaluate` / `adapter` / `plugin event`），快速定位慢点和失败链路。

```python
from nsgablack.plugins import OpenTelemetryTracingPlugin, OpenTelemetryTracingConfig

solver.add_plugin(
    OpenTelemetryTracingPlugin(
        config=OpenTelemetryTracingConfig(
            service_name="nsgablack-exp",
            console_export=True,              # 本地调试
            otlp_http_endpoint="",            # 例如 http://127.0.0.1:4318/v1/traces
        )
    )
)
```

可检索：

```powershell
python -m nsgablack catalog show plugin.otel_tracing
```
