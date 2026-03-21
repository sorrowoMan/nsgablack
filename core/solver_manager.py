# -*- coding: utf-8 -*-
"""Multi-solver orchestration with hard resource checks (manager only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .nested_solver import InnerRuntimeEvaluator, InnerSolveRequest


@dataclass(frozen=True)
class ResourceOffer:
    """Offered resources from manager (single backend)."""

    threads: int = 1
    gpus: int = 0
    backend: str = "local"


@dataclass(frozen=True)
class ResourceRequest:
    """Requested resources by a solver."""

    threads: int = 1
    gpus: int = 0
    backend: str = "local"
    label: str = ""


@dataclass(frozen=True)
class RegimeSpec:
    name: str
    build_solver: Callable[[], Any]


@dataclass(frozen=True)
class PhaseSpec:
    name: str
    regime_names: tuple[str, ...]


class ResourceBudgetError(RuntimeError):
    pass


def _coerce_request(value: Any, *, label: str = "") -> ResourceRequest:
    if isinstance(value, ResourceRequest):
        if label and not value.label:
            return ResourceRequest(
                threads=int(value.threads),
                gpus=int(value.gpus),
                backend=str(value.backend),
                label=str(label),
            )
        return value
    if isinstance(value, Mapping):
        return ResourceRequest(
            threads=int(value.get("threads", 1) or 1),
            gpus=int(value.get("gpus", 0) or 0),
            backend=str(value.get("backend", "local")),
            label=str(value.get("label", label)),
        )
    if isinstance(value, (int, float)):
        return ResourceRequest(threads=int(value), gpus=0, backend="local", label=str(label))
    return ResourceRequest(threads=1, gpus=0, backend="local", label=str(label))


def _infer_request(solver: Any, *, label: str = "") -> ResourceRequest:
    getter = getattr(solver, "resource_request", None)
    if callable(getter):
        try:
            return _coerce_request(getter(), label=label)
        except Exception:
            pass
    value = getattr(solver, "resource_request", None)
    if value is not None and not callable(value):
        try:
            return _coerce_request(value, label=label)
        except Exception:
            pass
    # Conservative default
    return ResourceRequest(threads=1, gpus=0, backend="local", label=str(label))


def _detect_inner_solver(solver: Any) -> Optional[Any]:
    problem = getattr(solver, "problem", None)
    evaluator = getattr(problem, "inner_runtime_evaluator", None) if problem is not None else None
    if isinstance(evaluator, InnerRuntimeEvaluator):
        dim = int(getattr(solver, "dimension", 1) or 1)
        candidate = np.zeros((dim,), dtype=float)
        request = InnerSolveRequest(
            candidate=candidate,
            outer_generation=0,
            outer_individual_id=0,
            budget_units=1.0,
            parent_contract="",
            metadata={},
        )
        try:
            inner_solver = evaluator._build_inner_solver(solver, request)
            if inner_solver is not None:
                return inner_solver
        except Exception:
            return None
    # Fallback: look for explicit hooks on solver/problem
    inner = getattr(solver, "inner_solver", None)
    if inner is not None:
        return inner
    build_inner = getattr(problem, "build_inner_solver", None) if problem is not None else None
    if callable(build_inner):
        try:
            dim = int(getattr(solver, "dimension", 1) or 1)
            candidate = np.zeros((dim,), dtype=float)
            return build_inner(candidate, {"solver": solver, "candidate": candidate})
        except Exception:
            return None
    return None


def _nested_total(request: ResourceRequest, inner: Optional[ResourceRequest]) -> ResourceRequest:
    if inner is None:
        return request
    total_threads = int(request.threads) + int(request.threads) * int(inner.threads)
    total_gpus = int(request.gpus) + int(request.gpus) * int(inner.gpus)
    return ResourceRequest(
        threads=total_threads,
        gpus=total_gpus,
        backend=str(request.backend),
        label=str(request.label),
    )


def _merge_results(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    # Minimal merge: keep per-regime results
    return {"regimes": list(results)}


class SolverManager:
    """Orchestrate multiple solvers with hard resource checks."""

    def __init__(
        self,
        *,
        regimes: Sequence[RegimeSpec],
        offer: ResourceOffer,
        phases: Optional[Sequence[PhaseSpec]] = None,
        mode: str = "parallel",
    ) -> None:
        self.offer = offer
        self.regimes = {r.name: r for r in regimes}
        if phases is None:
            names = tuple(self.regimes.keys())
            if str(mode).lower() == "serial":
                self.phases = [PhaseSpec(name=f"phase_{i}", regime_names=(n,)) for i, n in enumerate(names)]
            else:
                self.phases = [PhaseSpec(name="phase_parallel", regime_names=names)]
        else:
            self.phases = list(phases)

    def _check_offer(self, req: ResourceRequest) -> None:
        if str(req.backend).strip().lower() != str(self.offer.backend).strip().lower():
            raise ResourceBudgetError(
                f"backend mismatch: request={req.backend}, offer={self.offer.backend}"
            )
        if int(req.threads) > int(self.offer.threads):
            raise ResourceBudgetError(
                f"threads over budget: request={req.threads}, offer={self.offer.threads}"
            )
        if int(req.gpus) > int(self.offer.gpus):
            raise ResourceBudgetError(
                f"gpus over budget: request={req.gpus}, offer={self.offer.gpus}"
            )

    def _check_phase(self, solvers: Sequence[Any]) -> None:
        total_threads = 0
        total_gpus = 0
        for solver in solvers:
            outer = _infer_request(solver, label=getattr(solver, "name", "") or type(solver).__name__)
            inner_solver = _detect_inner_solver(solver)
            inner = _infer_request(inner_solver, label="inner") if inner_solver is not None else None
            total = _nested_total(outer, inner)
            total_threads += int(total.threads)
            total_gpus += int(total.gpus)
        if total_threads > int(self.offer.threads):
            raise ResourceBudgetError(
                f"phase threads over budget: need={total_threads}, offer={self.offer.threads}"
            )
        if total_gpus > int(self.offer.gpus):
            raise ResourceBudgetError(
                f"phase gpus over budget: need={total_gpus}, offer={self.offer.gpus}"
            )

    def run(self, *, return_dict: bool = True) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for phase in self.phases:
            solvers = [self.regimes[name].build_solver() for name in phase.regime_names]
            self._check_phase(solvers)
            for solver in solvers:
                out = solver.run(return_dict=True) if hasattr(solver, "run") else {}
                results.append(
                    {
                        "regime": getattr(solver, "name", type(solver).__name__),
                        "phase": phase.name,
                        "result": out,
                    }
                )
        merged = _merge_results(results)
        return merged if return_dict else merged
