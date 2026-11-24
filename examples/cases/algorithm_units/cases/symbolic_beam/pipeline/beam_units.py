"""特征池掩码结构，构建时不执行残差排序或 Beam 选择。"""
from dataclasses import dataclass, field
from typing import Any, ClassVar
import numpy as np
from nsgablack.units.collections import structure_schema
from nsgablack.representation.structure_builders import StructureUnitBuilder


@dataclass
class BeamUnit:
    unit_id: str
    masks: list = field(default_factory=list)
    feature_indices: Any = None
    empty_mask: Any = None
    schema: ClassVar = structure_schema("symbolic_beam", "masks", "feature_indices", "empty_mask")

    def validate(self):
        if self.empty_mask is not None and any(np.shape(mask) != np.shape(self.empty_mask) for mask in self.masks):
            raise ValueError("Beam 掩码必须与特征池布局对齐")


class BeamUnitBuilder(StructureUnitBuilder):
    unit_type = BeamUnit
    supported_operations = ("initialize", "layout")

    def construct(self, values, operation, parameters, context):
        if operation == "layout":
            dimension = int(parameters["dimension"])
            values["feature_indices"] = np.arange(dimension)
            values["empty_mask"] = np.zeros(dimension, dtype=bool)
            return
        super().construct(values, operation, parameters, context)
