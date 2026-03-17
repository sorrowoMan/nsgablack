"""
Representation pipeline and common plugins.
"""

from .base import (
    RepresentationPipeline,
    ParallelRepair,
    ContinuousRepresentation,
    IntegerRepresentation,
    PermutationRepresentation,
    MixedRepresentation,
)
from .continuous import (
    ClipRepair,
    ProjectionRepair,
    GaussianMutation,
    ContextGaussianMutation,
    PolynomialMutation,
    SBXCrossover,
    UniformInitializer,
)
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
from .constraints import BoundConstraint
from .context_mutators import ContextSelectMutator, SerialMutator, ContextDispatchMutator
from .dynamic import DynamicRepair
from .orchestrator import OrchestrationPolicy, PipelineOrchestrator

__all__ = [
    "RepresentationPipeline",
    "ParallelRepair",
    "ContinuousRepresentation",
    "IntegerRepresentation",
    "PermutationRepresentation",
    "MixedRepresentation",
    "ClipRepair",
    "ProjectionRepair",
    "GaussianMutation",
    "ContextGaussianMutation",
    "PolynomialMutation",
    "SBXCrossover",
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
    "BoundConstraint",
    "ContextSelectMutator",
    "SerialMutator",
    "ContextDispatchMutator",
    "OrchestrationPolicy",
    "PipelineOrchestrator",
    "DynamicRepair",
]
