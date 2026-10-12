"""Algorithm-pipeline construction for compound search structures.

Builders are stateless. They transform explicit construction inputs; scheduling,
selection, acceptance and objective/gradient evaluation stay in Adapters.
"""
from __future__ import annotations

from dataclasses import fields
from typing import Any, Mapping
import numpy as np
from blackbase.types import UnknownState
from ..units.collections import (
    TrajectoryUnit, PollUnit, ParameterUnit, PopulationUnit,
    ReferencePopulationUnit, DifferentialPopulationUnit, DecompositionUnit,
    RegionUnit, ModelSearchUnit, ArchiveUnit, NeighborhoodUnit,
)


def encode_unit_value(value: Any) -> Any:
    """Closed data codec: no pickle, arbitrary services or object-graph copies."""
    if isinstance(value, UnknownState):
        return {"type": "semantic", "value": value.as_dict()}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": value.hex()}
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "biuf":
            raise TypeError("Unit arrays must be real numeric")
        return {"type": "array", "dtype": str(value.dtype), "shape": list(value.shape), "value": value.tolist()}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (tuple, list)):
        return {"type": "tuple" if isinstance(value, tuple) else "list", "value": [encode_unit_value(v) for v in value]}
    if isinstance(value, Mapping):
        return {"type": "mapping", "value": [[encode_unit_value(k), encode_unit_value(v)] for k, v in value.items()]}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"Unit codec does not serialize runtime objects: {type(value).__name__}")


def decode_unit_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    kind, data = value["type"], value["value"]
    if kind == "bytes":
        return bytes.fromhex(data)
    if kind == "semantic":
        return UnknownState.from_protocol_payload(data)
    if kind == "array":
        return np.asarray(data, dtype=value["dtype"]).reshape(value["shape"])
    if kind in {"tuple", "list"}:
        out = [decode_unit_value(v) for v in data]
        return tuple(out) if kind == "tuple" else out
    if kind == "mapping":
        return {decode_unit_value(k): decode_unit_value(v) for k, v in data}
    raise ValueError(f"Unknown Unit value tag: {kind}")


class StructureUnitBuilder:
    unit_type = TrajectoryUnit
    supported_operations = ("initialize",)
    compatible_schemas = ()

    @property
    def schema(self):
        return self.unit_type.schema

    def build(self, request, context=None):
        values = decode_unit_value(encode_unit_value(request.parameters.get("values", {})))
        self.construct(values, request.operation, request.parameters, context or {})
        return self.unit_type(unit_id=request.unit_id, **values)

    def construct(self, values, operation, parameters, context):
        if operation != "initialize":
            raise ValueError(f"Unsupported structure operation: {operation}")

    def dump(self, unit):
        return {f.name: encode_unit_value(getattr(unit, f.name)) for f in fields(unit)}

    def restore(self, payload):
        # No build(), fitting, geometry sampling or Provider side effects here.
        return self.unit_type(**{k: decode_unit_value(v) for k, v in payload.items()})


class TrajectoryUnitBuilder(StructureUnitBuilder):
    unit_type = TrajectoryUnit


class PollUnitBuilder(StructureUnitBuilder):
    unit_type = PollUnit
    supported_operations = ("initialize", "poll")

    def construct(self, values, operation, parameters, context):
        if operation == "poll":
            center = np.asarray(values["current"], dtype=float)
            dims = tuple(int(d) for d in parameters["dimensions"])
            directions = []
            probes = []
            for d in dims:
                if not 0 <= d < len(center):
                    raise ValueError("Poll coordinate is outside the state")
                for sign in (1, -1):
                    direction = np.zeros_like(center)
                    direction[d] = sign
                    directions.append(direction)
                    probes.append((d, sign))
            values["directions"] = np.asarray(directions)
            values["probes"] = probes
            values["displacements"] = None
            return
        super().construct(values, operation, parameters, context)


class ParameterUnitBuilder(StructureUnitBuilder):
    unit_type = ParameterUnit
    supported_operations = ("initialize", "optimizer_slots")

    def construct(self, values, operation, parameters, context):
        if operation == "optimizer_slots":
            shape = tuple(parameters["shape"])
            values["first_moment"] = np.zeros(shape, dtype=float)
            values["second_moment"] = np.zeros(shape, dtype=float)
            return
        super().construct(values, operation, parameters, context)


class PopulationUnitBuilder(StructureUnitBuilder):
    unit_type = PopulationUnit


def simplex_points(n_objectives: int, divisions: int, *, positive=False):
    if n_objectives < 1 or divisions < 1:
        raise ValueError("Simplex dimensions/divisions must be positive")
    points = []
    def visit(prefix, left):
        if len(prefix) == n_objectives - 1:
            points.append([*prefix, left])
        else:
            for i in range(left + 1):
                visit([*prefix, i], left - i)
    visit([], divisions)
    out = np.asarray(points, dtype=float) / float(divisions)
    if positive:
        out = np.clip(out, 1e-12, None)
        out /= np.sum(out, axis=1, keepdims=True)
    return out


class ReferencePopulationBuilder(StructureUnitBuilder):
    unit_type = ReferencePopulationUnit
    supported_operations = ("initialize", "reference_directions")
    compatible_schemas = (PopulationUnit.schema,)

    def construct(self, values, operation, parameters, context):
        if operation == "reference_directions":
            values["reference_points"] = simplex_points(int(parameters["objectives"]), int(parameters["divisions"]))
            return
        super().construct(values, operation, parameters, context)


class DifferentialPopulationBuilder(StructureUnitBuilder):
    unit_type = DifferentialPopulationUnit


class DecompositionUnitBuilder(StructureUnitBuilder):
    unit_type = DecompositionUnit
    supported_operations = ("initialize", "decomposition")

    def construct(self, values, operation, parameters, context):
        if operation == "decomposition":
            weights = np.array(parameters["weights"], dtype=float, copy=True)
            t = int(parameters["neighbors"])
            delta = weights[:, None, :] - weights[None, :, :]
            distances = np.sqrt(np.sum(delta * delta, axis=2))
            values["weights"] = weights
            values["neighbors"] = np.argsort(distances, axis=1)[:, :t]
            values["ideal"] = np.full(weights.shape[1], np.inf)
            return
        super().construct(values, operation, parameters, context)


class RegionUnitBuilder(StructureUnitBuilder):
    unit_type = RegionUnit
    supported_operations = ("initialize", "basis")

    def construct(self, values, operation, parameters, context):
        if operation == "basis":
            values["basis"], values["basis_method"] = self.make_basis(parameters)
            return
        super().construct(values, operation, parameters, context)

    def make_basis(self, parameters):
        # Adapter provides fallback random draws only if a fallback is needed.
        method = parameters["method"]
        k = int(parameters["rank"])
        x = np.asarray(parameters["samples"], dtype=float)
        if method == "random":
            return np.linalg.qr(x)[0][:, :k], "random"
        if method == "sparse_pca":
            from sklearn.decomposition import SparsePCA
            model = SparsePCA(n_components=k, random_state=parameters.get("seed"))
            model.fit(x)
            return np.asarray(model.components_, dtype=float).T, method
        if method == "cluster":
            from sklearn.cluster import KMeans
            model = KMeans(n_clusters=min(max(2, k), len(x)), random_state=parameters.get("seed"), n_init=5)
            model.fit(x)
            x = model.cluster_centers_
        x = x - np.mean(x, axis=0, keepdims=True)
        return np.linalg.svd(x, full_matrices=False)[2][:k].T, method


class ModelSearchUnitBuilder(StructureUnitBuilder):
    unit_type = ModelSearchUnit

    def create_model(self, *, num_objectives, model_type):
        from ..utils.surrogate.vector_surrogate import VectorSurrogate
        return VectorSurrogate(num_objectives=num_objectives, model_type=model_type)


class ArchiveUnitBuilder(StructureUnitBuilder):
    unit_type = ArchiveUnit


class NeighborhoodUnitBuilder(StructureUnitBuilder):
    unit_type = NeighborhoodUnit

    def construct(self, values, operation, parameters, context):
        super().construct(values, operation, parameters, context)
        if not values.get("scales"):
            values["scales"] = tuple(min(float(parameters["max_sigma"]),
                float(parameters["base_sigma"]) * float(parameters["scale"]) ** k)
                for k in range(int(parameters["k_max"]) + 1))
