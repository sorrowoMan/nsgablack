"""Algorithm operation structures; construction belongs to algorithm pipelines."""

from .contracts import UnitSchema, UnitBuildRequest, StructureBuildRequest, UnitBinding
from .views import UnitView, PopulationView
from .features import UnitFeature, FeatureUnit, FeatureContractError
from .operator_inputs import UnitInputSpec, UnitInputs
from .population_operations import PopulationChange
from .population_features import POPULATION_DISTANCES, SELECTION_RANKING
from .collections import (
    TrajectoryUnit, PollUnit, ParameterUnit, PopulationUnit,
    ReferencePopulationUnit, DifferentialPopulationUnit, DecompositionUnit,
    RegionUnit, ModelSearchUnit, ArchiveUnit, NeighborhoodUnit,
)
from .structures import CandidateUnit, SearchNodeUnit, ParetoLabelUnit, CANDIDATE_SCHEMA, SEARCH_NODE_SCHEMA, PARETO_LABEL_SCHEMA
from .bayesian import BayesianOptimizationUnit
from .cmaes import CMAUnit
from .map_elites import MapElitesUnit

__all__ = [
    "BayesianOptimizationUnit", "CMAUnit", "MapElitesUnit",
    "PopulationChange",
    "UnitInputSpec", "UnitInputs",
    "UnitFeature", "FeatureUnit", "FeatureContractError", "POPULATION_DISTANCES", "SELECTION_RANKING",
    "UnitView", "PopulationView",
    "UnitSchema", "UnitBuildRequest", "UnitBinding", "CandidateUnit",
    "SearchNodeUnit", "CANDIDATE_SCHEMA", "SEARCH_NODE_SCHEMA",
    "StructureBuildRequest", "TrajectoryUnit", "PollUnit", "ParameterUnit",
    "PopulationUnit", "ReferencePopulationUnit", "DifferentialPopulationUnit",
    "DecompositionUnit", "RegionUnit", "ModelSearchUnit", "ArchiveUnit",
    "NeighborhoodUnit", "ParetoLabelUnit", "PARETO_LABEL_SCHEMA",
]
