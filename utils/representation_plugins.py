"""
Compatibility re-exports for legacy imports.
"""

from .representation.continuous import ClipRepair, GaussianMutation, UniformInitializer
from .representation.integer import IntegerInitializer, IntegerMutation, IntegerRepair
from .representation.permutation import (
    PermutationInitializer,
    PermutationRepair,
    PermutationFixRepair,
    PermutationSwapMutation,
    PermutationInversionMutation,
    TwoOptMutation,
    OrderCrossover,
    PMXCrossover,
    RandomKeyInitializer,
    RandomKeyMutation,
    RandomKeyPermutationDecoder,
)
from .representation.binary import BinaryInitializer, BinaryRepair, BitFlipMutation, BinaryCapacityRepair
from .representation.graph import GraphEdgeInitializer, GraphEdgeMutation, GraphConnectivityRepair, GraphDegreeRepair
from .representation.matrix import (
    IntegerMatrixInitializer,
    IntegerMatrixMutation,
    MatrixRowColSumRepair,
    MatrixSparsityRepair,
    MatrixBlockSumRepair,
)

__all__ = [
    "ClipRepair",
    "GaussianMutation",
    "UniformInitializer",
    "IntegerInitializer",
    "IntegerMutation",
    "IntegerRepair",
    "PermutationInitializer",
    "PermutationRepair",
    "PermutationFixRepair",
    "PermutationSwapMutation",
    "PermutationInversionMutation",
    "TwoOptMutation",
    "OrderCrossover",
    "PMXCrossover",
    "RandomKeyInitializer",
    "RandomKeyMutation",
    "RandomKeyPermutationDecoder",
    "BinaryInitializer",
    "BinaryRepair",
    "BitFlipMutation",
    "BinaryCapacityRepair",
    "GraphEdgeInitializer",
    "GraphEdgeMutation",
    "GraphConnectivityRepair",
    "GraphDegreeRepair",
    "IntegerMatrixInitializer",
    "IntegerMatrixMutation",
    "MatrixRowColSumRepair",
    "MatrixSparsityRepair",
    "MatrixBlockSumRepair",
]
