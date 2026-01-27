# ML Framework Integration

本项目不把“代理模型/ML”当成框架目标，而是把它当成一种能力：需要时接入，不需要时不污染底座。

这一页讲的是工程集成思路：你怎么把 PyTorch / TensorFlow / Optuna / Ray Tune 这类工具接进来，并且仍然遵守 NSGABlack 的解耦原则。

## 1. 总原则

- Problem 只负责 `evaluate(x)`：给定解 x，返回 objectives/constraints
- 表示/修复走 `RepresentationPipeline`
- 业务倾向/软约束走 `BiasModule`
- 并行/记录/短路评估/缓存/代理模型走 Plugin
- 容易漏配的组合收敛成 Suite

你会发现：ML/代理模型天然更像 Plugin，而不是算法策略本身。

## 2. 典型集成场景

### 2.1 用深度学习当评估函数的一部分（最常见）

例如：你的 `evaluate(x)` 内部会跑一个模型前向，或用模型预测某个指标。

建议做法：
- 模型加载放在 Problem 的 `__init__`（一次加载，多次复用）
- `evaluate(x)` 保持“无副作用 + 可并行”（不要在里面写文件/画图）
- 统计/日志交给 Plugin（避免并行时输出混乱）

### 2.2 用 Optuna/Ray Tune 做“外层超参搜索”

把 NSGABlack 视作一个“可调用的求解器”，外层工具负责调参/调组合。

建议做法：
- 把 solver 的关键参数抽成 config（seed/budget/adapter/bias/suites）
- 外层只改 config，不改算法代码
- 每次 trial 统一挂 BenchmarkHarnessPlugin，输出到独立 run_id 目录

### 2.3 用代理模型做评估短路（surrogate / cache）

这类能力更适合放在 Plugin，因为它属于“评估过程的能力层”：
- 命中缓存/代理模型时：短路返回预测值
- 否则：走真实评估，并把真实数据回写缓存/训练集

建议做法：
- 使用框架提供的“评估短路插槽”接口（只扩展接口，不内置 surrogate 逻辑）
- 将“训练/更新/持久化”也放在 Plugin/Suite 中组织

## 3. 推荐的落地路径

1) 先把纯 `evaluate(x)` 跑通（见 `WORKFLOW_END_TO_END.md`）
2) 再加 BenchmarkHarnessPlugin 统一实验口径（CSV/JSON）
3) 再加并行评估（如果慢）
4) 最后再考虑 surrogate/ML（可选能力）

## 4. 参考入口

- 端到端流程：`WORKFLOW_END_TO_END.md`
- Catalog/Suites：`docs/user_guide/catalog.md`
- 插件系统：`docs/user_guide/PLUGIN_SYSTEM.md`
- 核心边界：`docs/CORE_STABILITY.md`

