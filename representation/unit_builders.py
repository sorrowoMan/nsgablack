"""Stateless algorithm-pipeline builders. No scoring, selection or transitions."""

from __future__ import annotations

import copy
from typing import Any, Mapping
import numpy as np
from blackbase.types import UnknownState

from ..units import CandidateUnit, SearchNodeUnit, CANDIDATE_SCHEMA, SEARCH_NODE_SCHEMA
from ..units.structures import ParetoLabelUnit, PARETO_LABEL_SCHEMA
from .structure_builders import encode_unit_value, decode_unit_value


def _dump_candidate(candidate: Any) -> dict[str, Any]:
    if isinstance(candidate, UnknownState):
        return {"semantic": True, "state": candidate.as_dict()}
    values = np.asarray(candidate)
    return {"semantic": False, "values": values.tolist(), "dtype": str(values.dtype)}


def _restore_candidate(payload: Mapping[str, Any]) -> Any:
    if payload["semantic"]:
        return UnknownState.from_protocol_payload(payload["state"])
    return np.asarray(payload["values"], dtype=payload["dtype"])


class CandidateUnitBuilder:
    schema = CANDIDATE_SCHEMA
    supported_operations = ("fresh", "spawn", "refresh")
    compatible_schemas = ()

    def build(self, request, context=None) -> CandidateUnit:
        return CandidateUnit(request.unit_id, request.candidate)

    def dump(self, unit: CandidateUnit) -> dict[str, Any]:
        return {"unit_id": unit.unit_id, "candidate": _dump_candidate(unit.to_candidate())}

    def restore(self, payload: Mapping[str, Any]) -> CandidateUnit:
        return CandidateUnit(str(payload["unit_id"]), _restore_candidate(payload["candidate"]))


class SearchNodeBuilder(CandidateUnitBuilder):
    schema = SEARCH_NODE_SCHEMA

    def build(self, request, context=None) -> SearchNodeUnit:
        p = request.parameters
        # Priority and costs are supplied by the Adapter; the builder does not
        # impose f=g+h or call a heuristic/evaluator.
        return SearchNodeUnit(request.unit_id, request.candidate,
                              g=float(p["g"]), h=float(p["h"]), f=float(p["f"]),
                              parent_key=copy.deepcopy(p.get("parent_key")),
                              parent_id=p.get("parent_id"))

    def dump(self, unit: SearchNodeUnit) -> dict[str, Any]:
        return {**super().dump(unit), "g": unit.g, "h": unit.h, "f": unit.f,
                "parent_key": encode_unit_value(unit.parent_key), "parent_id": unit.parent_id}

    def restore(self, payload: Mapping[str, Any]) -> SearchNodeUnit:
        return SearchNodeUnit(str(payload["unit_id"]), _restore_candidate(payload["candidate"]),
                              g=float(payload["g"]), h=float(payload["h"]), f=float(payload["f"]),
                              parent_key=decode_unit_value(payload.get("parent_key")),
                              parent_id=payload.get("parent_id"))


class ParetoLabelBuilder(CandidateUnitBuilder):
    schema = PARETO_LABEL_SCHEMA

    def build(self, request, context=None):
        p = request.parameters
        return ParetoLabelUnit(request.unit_id, request.candidate, p["g"], p["h"], p["f"],
                               copy.deepcopy(p.get("parent_key")), p.get("parent_id"))

    def dump(self, unit):
        return {**super().dump(unit), "g": unit.g.tolist(), "h": unit.h.tolist(), "f": unit.f.tolist(),
                "parent_key": encode_unit_value(unit.parent_key), "parent_id": unit.parent_id, "valid": unit.valid}

    def restore(self, payload):
        return ParetoLabelUnit(str(payload["unit_id"]), _restore_candidate(payload["candidate"]),
                               payload["g"], payload["h"], payload["f"], decode_unit_value(payload.get("parent_key")),
                               payload.get("parent_id"), bool(payload["valid"]))
