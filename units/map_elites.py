"""One authority for a quality-diversity archive; candidates remain Pool versions."""
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

from .features import FeatureUnit
from .collections import structure_schema
from ..core.state.solution_pool import SolutionRef


@dataclass
class MapElitesUnit(FeatureUnit):
    unit_id: str
    entries: list = field(default_factory=list)
    evaluations: int = 0
    replacements: int = 0
    schema: ClassVar = structure_schema("map_elites_archive", "entries", "evaluations", "replacements")

    def validate(self):
        cells = []
        for entry in self.entries:
            if set(entry) != {"cell", "descriptor", "candidate", "objectives", "violation", "quality", "solution_ref"}:
                raise ValueError("invalid MAP-Elites archive entry")
            cell = tuple(entry["cell"])
            if not cell or any(type(i) is not int or i < 0 for i in cell):
                raise ValueError("archive cell requires nonnegative integer coordinates")
            cells.append(cell)
            if len(entry["descriptor"]) != len(cell):
                raise ValueError("archive descriptor/cell dimensions differ")
            for key in ("descriptor", "candidate", "objectives"):
                if not np.all(np.isfinite(np.asarray(entry[key], dtype=float))):
                    raise ValueError("archive values must be finite")
            if not np.isfinite(entry["quality"]) or not np.isfinite(entry["violation"]):
                raise ValueError("archive quality and violation must be finite")
            SolutionRef.from_dict(entry["solution_ref"])
        if cells != sorted(set(cells)):
            raise ValueError("archive cells must be unique and ordered")
        if type(self.evaluations) is not int or type(self.replacements) is not int or not 0 <= self.replacements <= self.evaluations:
            raise ValueError("invalid archive observation counts")
