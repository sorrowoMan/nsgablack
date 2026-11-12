"""Stateless closed-data codec; restoration does not run a random builder."""
from .structure_builders import StructureUnitBuilder
from ..units.bayesian import BayesianOptimizationUnit


class BayesianUnitBuilder(StructureUnitBuilder):
    unit_type = BayesianOptimizationUnit
