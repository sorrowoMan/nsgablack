# Plugin System

Plugin 是 NSGABlack 的能力层：它负责并行、记录、监控、短路评估、缓存等工程能力；它不承载算法策略过程，不写业务规则。

这一页讲的是：
- 什么时候该写 Plugin
- Plugin 读写什么（context keys）
- 如何把“容易漏配的伙伴组件”收敛成 Suite

## 1. 什么时候用 Plugin

适合 Plugin 的事：
- 并行评估、批处理、线程/进程安全保护
- 统一实验口径输出（progress.csv + summary.json）
- 运行审计与“模块贡献可查”（modules.json + bias.json/bias.md）
- 统计信号写回 context（供 signal-driven bias 使用）
- 评估短路（缓存命中 / surrogate 命中 / 快速可行性筛选）

不适合 Plugin 的事：
- 策略过程（那是 Adapter：propose/update）
- 硬约束可行化（优先在 RepresentationPipeline：init/mutate/repair）
- 业务偏好/软约束（优先在 BiasModule）

## 2. Plugin 如何通信：context keys

框架把“运行中的事实”都放在 `context`：
- Plugin 读取事实做统计/输出
- Plugin 也可以把新事实写回 context（例如 metrics），供后续组件使用

建议你优先复用 `utils/context/context_keys.py` 里的规范 key，避免不同组件各写一套。

## 3. 避免漏配：用 Suite

真实开发最容易犯的错不是“不会写”，而是“漏配”：
- 少挂一个记录插件 -> 没有可对比数据
- 少挂一个 mutator -> 算法退化但不报错
- 少写一个 context key -> signal-driven bias 失效

因此推荐把“必配组合”收敛成 Suite，例如：
- `suite.benchmark_harness`：统一实验口径输出
- `suite.module_report`：模块清单 + 偏置贡献报告（自动把 artifacts 注入 benchmark summary）
- `suite.vns`：VNS 相关的必配伙伴组件

## 4. Catalog：发现你有哪些 Plugin/Suite

```powershell
python -m nsgablack catalog search plugin
python -m nsgablack catalog search suite
python -m nsgablack catalog show suite.benchmark_harness
python -m nsgablack catalog show suite.module_report
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

## 5. 参考入口

- 端到端流程：`WORKFLOW_END_TO_END.md`
- Catalog/Suites：`docs/user_guide/catalog.md`
- 解耦导读：`docs/guides/DECOUPLING_CAPABILITIES.md`
