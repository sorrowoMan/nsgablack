# 表征索引

生成时间: 2026-02-17 (手动更新)

## representation（表征/编码）

- representation/base.py
  - RepresentationPipeline, ParallelRepair, ContextSwitchMutator
- representation/constraints.py
  - BoundConstraint（边界约束检查/修复，re-exported from base）
- representation/continuous.py
  - ClipRepair, ProjectionRepair, GaussianMutation, ContextGaussianMutation, UniformInitializer
- representation/dynamic.py
  - DynamicRepair
- representation/integer.py
  - IntegerInitializer, IntegerMutation, IntegerRepair
- representation/binary.py
  - BinaryInitializer, BinaryRepair, BitFlipMutation, BinaryCapacityRepair
- representation/permutation.py
  - PermutationInitializer, PermutationRepair, PermutationFixRepair, PermutationSwapMutation, PermutationInversionMutation, TwoOptMutation, OrderCrossover, PMXCrossover, RandomKeyInitializer, RandomKeyMutation, RandomKeyPermutationDecoder
- representation/matrix.py
  - IntegerMatrixInitializer, IntegerMatrixMutation, MatrixRowColSumRepair, MatrixSparsityRepair, MatrixBlockSumRepair
- representation/graph.py
  - GraphEdgeInitializer, GraphEdgeMutation, GraphConnectivityRepair, GraphDegreeRepair
- representation/context_mutators.py
  - 按 context 切换/调参的 mutator wrapper（VNS/SA 的"阶段信号"）

## 工程规范

所有 representation 模块使用 **实例级 RNG**（`self._rng = np.random.default_rng()`），禁止全局 `np.random`。

> 参考：`docs/development/DEVELOPER_CONVENTIONS.md` 第 2 节

## 入口

- Catalog 搜索：`python -m nsgablack catalog search representation`
- 解耦指南：`docs/guides/DECOUPLING_REPRESENTATION.md`
- API 索引：`docs/indexes/API_INDEX.md` §3
