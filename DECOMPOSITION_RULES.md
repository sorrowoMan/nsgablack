# 算法拆解原则（Adapter / Plugin / Bias / Pipeline / Suite）

这一页是“可快速查找”的总纲：你不需要记住所有文件在哪，但需要记住**拆解边界**与**配套规则**，这样无论你怎么拆，都不会把系统拆坏。

如果你只记一条：**底座保持纯净；能力通过扩展点组合进来；成套能力必须提供 Suite。**

## 1. 四类扩展点 + 一个权威组合

### RepresentationPipeline（表示与算子）
- 负责：编码/解码、初始化、变异、修复（以及可行性构造这类“硬约束”）
- 特点：更像“数据流管线”，可复用性极强
- 典型问题：VNS/邻域类方法需要随阶段切换邻域算子，可用 `ContextSwitchMutator` 这类 wrapper

### Bias（偏好/倾向/软约束）
- 负责：把“方向性策略”表达成可叠加的评分/惩罚/调度；典型是软约束、偏好、阶段权重
- 不负责：复杂流程控制、候选生成主循环（否则会把 bias 变成隐形算法）
- 特例：**信号驱动偏置**（需要插件/套件提供 metrics），见 `docs/user_guide/signal_driven_bias.md`

### Adapter（策略内核）
- 负责：搜索策略的“最小闭环”—— `propose()` 提候选、`update()` 吃反馈
- 目标：把“算法核心”沉淀成可复用模块，并可用 `CompositeAdapter` 做融合/嵌套
- 不负责：并行、日志、实验追踪等横切能力（这些应留给 Plugin）

### Plugin（胶水/调度/横切能力）
- 负责：日志、监控、早停、阶段切换、动态调参、统计信号注入、并行评估调用、实验记录……
- 特点：最灵活、也最容易“长成上帝对象”，所以要靠契约/护栏约束副作用边界

### Suite（权威组合 / Recipe）
- 负责：把“必须成套才有意义”的能力做成一键装配入口，避免漏配导致隐性 bug
- 例子：`MonteCarloEvaluationPlugin` + `RobustnessBias` 就应该用 suite 固化（事实标准）

## 2. 伙伴组件（companions）是什么

当一个能力“单独存在意义不大”或“漏配会退化/报错”时，需要明确它的伙伴组件：

- `Bias` 依赖某些 metrics：推荐对应的 Plugin/Suite
- `Adapter` 依赖某个 representation 的 context 变异：推荐对应的 mutator wrapper
- `Plugin` 与某个 adapter/bias 形成权威组合：推荐对应的 Suite

伙伴信息有两层：

1) 运行期护栏：缺配件时给出 `RuntimeWarning`（warn-once / strict 可选）
2) 可发现性：在 catalog 里用 `companions` 软链接，让用户“搜到一个就能顺藤摸瓜”

## 3. 接口级护栏（必须遵守）

扩展点的“输入/输出/副作用边界”不是口头约定，而是工程契约：

- 见 `docs/user_guide/EXTENSION_CONTRACTS.md`
- 对于新拆解的组件，推荐至少写一个最小测试用例（import + 运行 + 关键字段/shape 校验）

## 4. 新拆一个算法：如何让它可发现

框架提供 catalog/recipes 作为“可发现性层”：

- 使用说明：`docs/user_guide/catalog.md`
- 不想改源码：把条目写进 `catalog/entries.toml` 或 `NSGABLACK_CATALOG_PATH`

## 5. 更细的工程检查清单

如果你要“按规范落地一个新拆解算法”，用这份逐项 checklist：

- `docs/development/DECOMPOSITION_CHECKLIST.md`

