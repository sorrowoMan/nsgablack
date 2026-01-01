# 表征索引

生成时间: 2026-01-01 18:53:55

## representation（表征/编码）

- utils/representation/base.py
  - 类: EncodingPlugin (L11), RepairPlugin (L19), InitPlugin (L24), MutationPlugin (L29), RepresentationPipeline (L35)
- utils/representation/binary.py
  - 类: BinaryInitializer (L14), BitFlipMutation (L22), BinaryRepair (L33), BinaryCapacityRepair (L41)
- utils/representation/continuous.py
  - 类: UniformInitializer (L14), GaussianMutation (L23), ClipRepair (L36)
- utils/representation/graph.py
  - 类: GraphEdgeInitializer (L14), GraphEdgeMutation (L33), GraphConnectivityRepair (L66), GraphDegreeRepair (L111)
- utils/representation/integer.py
  - 类: IntegerInitializer (L39), IntegerRepair (L57), IntegerMutation (L81)
- utils/representation/matrix.py
  - 类: IntegerMatrixInitializer (L25), IntegerMatrixMutation (L41), MatrixRowColSumRepair (L53), MatrixSparsityRepair (L92), MatrixBlockSumRepair (L117)
- utils/representation/permutation.py
  - 类: RandomKeyPermutationDecoder (L13), RandomKeyInitializer (L22), RandomKeyMutation (L31), PermutationInitializer (L42), PermutationSwapMutation (L51), PermutationInversionMutation (L62), PermutationRepair (L73), PermutationFixRepair (L84), TwoOptMutation (L102), OrderCrossover (L127), PMXCrossover (L137)
