"""扩展成员年龄；Adapter 不猜测新增字段的更新规则。"""
from dataclasses import dataclass, field

import numpy as np
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units import PopulationUnit, UnitSchema


@dataclass
class RecipePopulation(PopulationUnit):
    member_age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("member_age",)
    schema = UnitSchema("assembly_workbench.recipe_population",
        required_fields=(*PopulationUnit.schema.required_fields, "member_age"),
        candidate_projection=False)

    def on_members_changed(self, change):
        increment = int(change.operation == "selection")
        return {"member_age": np.asarray([0 if index is None else self.member_age[index] + increment
            for index in change.previous_member_indices], dtype=int)}

    def validate(self):
        super().validate()
        if self.member_age.dtype.kind not in "iu" or np.any(self.member_age < 0):
            raise ValueError("member ages must be nonnegative integers")


class RecipePopulationBuilder(PopulationUnitBuilder):
    unit_type = RecipePopulation
    compatible_schemas = (PopulationUnit.schema,)
