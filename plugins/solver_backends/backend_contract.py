from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence

import numpy as np


@dataclass
class WarmStartSpec:
    """Warm-start configuration for backend solvers."""

    data: Any = None
    snapshot_ref: Optional[str] = None
    apply_fn: Optional[Callable[[Any, Any, "WarmStartSpec"], Any]] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SolutionPoolSpec:
    """Solution pool configuration for backend solvers."""

    max_solutions: Optional[int] = None
    params: Dict[str, Any] = field(default_factory=dict)
    extract_fn: Optional[Callable[[Any, Any, "SolutionPoolSpec"], Mapping[str, Any]]] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallbackSpec:
    """Callback registration configuration for backend solvers."""

    events: Sequence[str] = ()
    handler: Optional[Callable[..., Any]] = None
    register_fn: Optional[Callable[[Any, Any, "CallbackSpec"], Any]] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticSpec:
    """Diagnostics (IIS/feas-relax/log) configuration for backend solvers."""

    iis: bool = False
    feas_relax: bool = False
    apply_fn: Optional[Callable[[Any, Any, "DiagnosticSpec"], Mapping[str, Any]]] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BackendCapabilities:
    warm_start: bool = False
    solution_pool: bool = False
    callback: bool = False
    diagnostics: bool = False
    tuning: bool = False


@dataclass
class BackendSolveRequest:
    candidate: np.ndarray
    eval_context: Dict[str, Any]
    inner_problem: Any = None
    inner_solver: Any = None
    payload: Dict[str, Any] = field(default_factory=dict)
    warm_start: Optional[WarmStartSpec] = None
    solution_pool: Optional[SolutionPoolSpec] = None
    callback: Optional[CallbackSpec] = None
    diagnostics: Optional[DiagnosticSpec] = None


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
