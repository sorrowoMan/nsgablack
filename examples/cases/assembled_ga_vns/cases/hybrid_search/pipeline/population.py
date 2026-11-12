"""扩展算法结构；NSGA-II 无需知道 member_age 如何维护。"""
from dataclasses import dataclass, field

import numpy as np

from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units import PopulationUnit, UnitSchema


@dataclass
class AgePopulationUnit(PopulationUnit):
    member_age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("member_age",)
    schema = UnitSchema(
        "assembled_ga_vns.age_population",
        required_fields=(*PopulationUnit.schema.required_fields, "member_age"),
        candidate_projection=False,
    )

    def on_members_changed(self, change):
        # 年龄 = 此成员连续存活的环境选择次数。新成员为 0；局部替换
        # 不算整轮环境选择。按来源索引维护，数值相同也不猜身份。
        increment = int(change.operation == "selection")
        return {"member_age": np.asarray([
            0 if previous is None else self.member_age[previous] + increment
            for previous in change.previous_member_indices
        ], dtype=int)}

    def validate(self):
        super().validate()
        if self.member_age.dtype.kind not in "iu" or np.any(self.member_age < 0):
            raise ValueError("member_age must contain nonnegative integers")


class AgePopulationBuilder(PopulationUnitBuilder):
    # 继承标准纯数据 codec；恢复只恢复字段，不重跑构建。
    unit_type = AgePopulationUnit
    compatible_schemas = (PopulationUnit.schema,)
