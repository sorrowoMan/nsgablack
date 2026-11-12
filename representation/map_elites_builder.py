"""Stateless construction and closed data codec for MAP-Elites archives."""
from .structure_builders import StructureUnitBuilder
from ..units.map_elites import MapElitesUnit


class MapElitesUnitBuilder(StructureUnitBuilder):
    unit_type = MapElitesUnit
