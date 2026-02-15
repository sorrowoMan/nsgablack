# 插件选择指南（何时用哪个）

这份指南回答一个现实问题：**知道有插件，但不知道先用哪个。**

定位：
- 框架负责提供可复用能力与可审计组合；
- 具体策略选择仍由问题目标决定，不替代建模思考。

## 1) 快速决策（先看场景）

- 需要统一实验输出与对比：`plugin.benchmark_harness`
- 需要组件归因/消融证据：`plugin.module_report`
- 需要先查性能瓶颈：`plugin.profiler`
- 多目标前沿需要稳定档案：`plugin.pareto_archive`
- 评估有不确定性/扰动：`plugin.monte_carlo_eval`
- 真实评估太贵：`plugin.surrogate_eval` 或 `plugin.multi_fidelity_eval`
- 需要运行中动态切换：`plugin.dynamic_switch`
- 有异步时序语义：`plugin.async_event_hub`
- 需要集中化实验资产：`plugin.mysql_run_logger`

## 2) 推荐组合（最小可用）

### 基础工程三件套

- `plugin.benchmark_harness`
- `plugin.module_report`
- `plugin.pareto_archive`（多目标时）

用途：先确保“可复现 + 可审计 + 可对比”。

### 评估成本控制

- `plugin.surrogate_eval` 或 `plugin.multi_fidelity_eval`
- 配合 `plugin.profiler`

用途：先量化瓶颈，再引入近似/低保真能力。

### 异步协同

- `adapter.async_event_driven`
- `plugin.async_event_hub`
- `plugin.pareto_archive`

用途：保证异步编排下的事件边界与可回放性。

## 3) 不建议的接法

- 一上来同时开启过多插件再调参（难以归因）。
- 在没有基准输出时直接引入 surrogate/multi-fidelity（难比较收益）。
- 异步流程不设提交边界（可能读取半状态）。

## 4) 上手顺序（建议）

1. 先跑 `benchmark_harness + module_report`，建立基线。  
2. 加一个目标插件（例如 MC 或 surrogate），只改一个变量。  
3. 用 Run Inspector 的 Catalog/Context 检查契约与字段变化。  
4. 通过对照 run 决定是否保留该插件。

## 5) 命令与入口

命令行：

```powershell
python -m nsgablack catalog search plugin --kind plugin
python -m nsgablack catalog search mc --kind plugin --field usage
python -m nsgablack catalog show plugin.monte_carlo_eval
```

UI：
- 打开 Run Inspector
- 进入 `Catalog` tab
- `Kind=plugin`，`Match=usage/context`
- 搜索关键词（如 `robust`, `async`, `profile`, `mysql`）

