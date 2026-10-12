"""种群成员扩展示例；由 Case build_solver 显式选择此 binding。"""
from dataclasses import dataclass, field

import numpy as np

from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units import PopulationUnit, UnitSchema


@dataclass
class AgePopulationUnit(PopulationUnit):
    # age 计数本成员连续参与并存活的环境选择次数；初始化为 0。
    # 局部替换不代表一轮环境选择，因此不增加未替换成员的 age。
    age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("age",)
    schema = UnitSchema("case.age_population", required_fields=(
        *PopulationUnit.schema.required_fields, "age"), candidate_projection=False)

    def on_members_changed(self, change):
        # 如需新成员标签/父代，按 incoming_member_indices 读取
        # change.incoming_metadata / incoming_provenance；不从 context 猜来源。
        increment = int(change.operation == "selection")
        return {"age": np.asarray([
            0 if i is None else self.age[i] + increment
            for i in change.previous_member_indices
        ], dtype=int)}


class AgePopulationBuilder(PopulationUnitBuilder):
    unit_type = AgePopulationUnit
    compatible_schemas = (PopulationUnit.schema,)
