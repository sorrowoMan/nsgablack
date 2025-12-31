"""
Representation pipeline and common plugins.
"""

from .base import RepresentationPipeline
from .continuous import ClipRepair, GaussianMutation, UniformInitializer
from .integer import IntegerInitializer, IntegerMutation, IntegerRepair
from .permutation import (
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
from .binary import BinaryInitializer, BinaryRepair, BitFlipMutation, BinaryCapacityRepair
from .graph import GraphEdgeInitializer, GraphEdgeMutation, GraphConnectivityRepair, GraphDegreeRepair
from .matrix import (
    IntegerMatrixInitializer,
    IntegerMatrixMutation,
    MatrixRowColSumRepair,
    MatrixSparsityRepair,
    MatrixBlockSumRepair,
)

__all__ = [
    "RepresentationPipeline",
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
