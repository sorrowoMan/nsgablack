# DECOUPLING_REPRESENTATION: RepresentationPipeline 该负责什么

如果 Problem 是“现实世界给反馈”，那 RepresentationPipeline 就是“你如何合法地产生候选解”。

这一页讲清楚：为什么硬约束优先放在表示层，以及你换问题/换算法时怎样最省心。

## RepresentationPipeline 的职责（应该做）

- `init`：初始化候选解（尽量生成可行解）
- `mutate`：邻域变异（连续/整数/排列/图/矩阵等）
- `repair`（可选）：修复越界/不可行（让硬约束在这里被兜住）
- `codec`（可选）：编码/解码（内部表示 != 评估表示时）

一句话：RepresentationPipeline 负责“把搜索空间变成算法能安全操作的空间”。

## 为什么硬约束要优先放这里

你当然可以把“可行性处理”写进算法里，但你很快会遇到：
- 你换一个算法，就要复制一份可行性逻辑
- 算法主循环被 if/else 淹没，维护成本指数上升
- 并行时更容易出现隐性 bug（不同分支写出不同副作用）

把硬约束前置到 pipeline 的收益是立刻的：
- 算法只关心“搜索策略”，不关心“怎么修回去”
- 你可以自由替换/串联 Adapter，而不必重写可行性处理

## 漏配最常见的坑：VNS/邻域切换

邻域搜索（如 VNS）经常需要“上下文切换/邻域切换” mutator。
如果你忘了加，算法仍然能跑，但会退化（悄悄变差）。

建议做法：
- 优先使用 `suite.vns` 等权威组合（它会把伙伴组件一起装好）
- 手搓时，至少写一个自检：init 是否大多可行、mutate 是否总被 repair 拉回

## 你应该看哪里

- 表示与算子索引：`docs/indexes/REPRESENTATION_INDEX.md`
- 表示实现：`representation/`
- VNS 相关：`core/adapters/vns.py`、`representation/`（ContextSwitchMutator 等）
