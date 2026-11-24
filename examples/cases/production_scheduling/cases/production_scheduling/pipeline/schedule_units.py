"""排程算法结构；不包含机器选择、蒸发或沉积策略。"""
from dataclasses import dataclass, field
from typing import ClassVar, Any
import numpy as np
from nsgablack.units.collections import structure_schema
from nsgablack.representation.structure_builders import StructureUnitBuilder


@dataclass
class ScheduleUnit:
    unit_id: str
    machines: int = 0
    days: int = 0
    bom: Any = None
    supply: Any = None
    weights: Any = None
    required_materials: list = field(default_factory=list)
    constraints: dict = field(default_factory=dict)
    pheromone: Any = None
    schema: ClassVar = structure_schema("schedule", "machines", "days", "bom", "supply", "pheromone")

    def validate(self):
        if self.machines and (self.pheromone is None or np.shape(self.pheromone) != (self.machines, self.days)):
            raise ValueError("排程信息素矩阵必须与机器和日期对齐")


class ScheduleUnitBuilder(StructureUnitBuilder):
    unit_type = ScheduleUnit
    supported_operations = ("initialize", "layout")

    def construct(self, values, operation, parameters, context):
        if operation != "layout":
            return super().construct(values, operation, parameters, context)
        machines, days = int(parameters["machines"]), int(parameters["days"])
        bom = np.array(parameters["bom"], dtype=float, copy=True)
        values.update(machines=machines, days=days, bom=bom,
            supply=np.array(parameters["supply"], dtype=float, copy=True),
            weights=np.clip(np.array(parameters["weights"], dtype=float, copy=True), 1e-6, None),
            required_materials=[np.where(bom[m] > 0)[0] for m in range(machines)],
            constraints=dict(parameters["constraints"]),
            pheromone=np.ones((machines, days)))


def schedule_parameters(problem):
    """从领域模型读取布局数据；不把 Problem/服务对象放进 Unit 请求。"""
    data, constraints = problem.data, problem.constraints
    machines = int(getattr(problem, "machines", data.machines))
    return dict(machines=machines, days=int(getattr(problem, "days", data.days)),
        bom=data.bom_matrix, supply=data.supply_matrix,
        weights=getattr(problem, "machine_weights", np.ones(machines)),
        constraints={k: int(getattr(constraints, k)) for k in ("max_machines_per_day", "min_machines_per_day",
            "min_production_per_machine", "max_production_per_machine")})
