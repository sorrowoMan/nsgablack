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
from .repair_contracts import ProblemRepair, UnitRepair, JointRepairPolicy, JointRepairRejected
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
from .pipeline_kernel import (
    PipelineSlotSpec,
    PipelineSpec,
    RepresentationPipelineKernelBuild,
    build_pipeline_kernel,
)
from .structure_builders import (
    TrajectoryUnitBuilder, PollUnitBuilder, ParameterUnitBuilder, PopulationUnitBuilder, ReferencePopulationBuilder, DifferentialPopulationBuilder, DecompositionUnitBuilder, RegionUnitBuilder, ModelSearchUnitBuilder, ArchiveUnitBuilder, NeighborhoodUnitBuilder
)
from .unit_builders import CandidateUnitBuilder, SearchNodeBuilder, ParetoLabelBuilder
from .bayesian_builder import BayesianUnitBuilder
from .cmaes_builder import CMAUnitBuilder
from .map_elites_builder import MapElitesUnitBuilder

__all__ = [
    "BayesianUnitBuilder", "CMAUnitBuilder", "MapElitesUnitBuilder",
    "ProblemRepair", "UnitRepair", "JointRepairPolicy", "JointRepairRejected",
    'TrajectoryUnitBuilder', 'PollUnitBuilder', 'ParameterUnitBuilder', 'PopulationUnitBuilder', 'ReferencePopulationBuilder', 'DifferentialPopulationBuilder', 'DecompositionUnitBuilder', 'RegionUnitBuilder', 'ModelSearchUnitBuilder', 'ArchiveUnitBuilder', 'NeighborhoodUnitBuilder', 'ParetoLabelBuilder',
    "CandidateUnitBuilder",
    "SearchNodeBuilder",
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
    "RepresentationPipelineKernelBuild",
    "PipelineSlotSpec",
    "PipelineSpec",
    "build_pipeline_kernel",
    "OrchestrationPolicy",
    "PipelineOrchestrator",
    "DynamicRepair",
]
