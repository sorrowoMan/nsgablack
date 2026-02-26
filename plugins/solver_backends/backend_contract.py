from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol

import numpy as np


@dataclass
class BackendSolveRequest:
    candidate: np.ndarray
    eval_context: Dict[str, Any]
    inner_problem: Any = None
    inner_solver: Any = None
    payload: Dict[str, Any] = field(default_factory=dict)


class BackendSolver(Protocol):
    def solve(self, request: BackendSolveRequest) -> Mapping[str, Any]:
        ...


def normalize_backend_output(raw: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(raw)
    out.setdefault("status", "ok")
    if "objectives" not in out and "objective" not in out:
        raise ValueError("backend result must include 'objective' or 'objectives'")
    out.setdefault("violation", 0.0)
    metrics = out.get("metrics")
    if metrics is None:
        out["metrics"] = {}
    elif not isinstance(metrics, Mapping):
        raise TypeError("backend result 'metrics' must be mapping")
    return out

