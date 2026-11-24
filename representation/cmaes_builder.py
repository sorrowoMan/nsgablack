"""CMA structure construction and its explicit, service-free codec."""
from .structure_builders import StructureUnitBuilder
from ..units.cmaes import CMAUnit


class CMAUnitBuilder(StructureUnitBuilder):
    unit_type = CMAUnit
