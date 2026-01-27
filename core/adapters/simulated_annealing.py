"""
Simulated Annealing (SA) as an AlgorithmAdapter.

This is the "algorithm-core" decomposition of SA:
- propose(): generate neighbor candidates (via RepresentationPipeline mutator)
- update(): accept/reject via Metropolis rule + temperature schedule

Notes:
- SA is naturally sequential; this adapter proposes a small batch and processes
  it in order. Batch > 1 is mainly for better throughput when evaluation is
  expensive / parallelized.
- Multi-objective fallback scoring uses sum(objectives) + violation*1e6, aligned
  with ComposableSolver.select_best().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence
import math
import warnings

import numpy as np

from .algorithm_adapter import AlgorithmAdapter
from ...utils.context.context_keys import KEY_MUTATION_SIGMA, KEY_TEMPERATURE


@dataclass
class SAConfig:
    # number of candidates per step (processed sequentially)
    batch_size: int = 1

    # temperature schedule: T <- max(min_temperature, T * cooling_rate)
    initial_temperature: float = 10.0
    cooling_rate: float = 0.98
    min_temperature: float = 1e-6

    # optional coupling to representation mutator:
    # - if your mutator consumes "mutation_sigma", SA will write it based on T
    base_sigma: float = 0.2
    sigma_temperature_scale: float = 1.0  # sigma = base_sigma * (T/T0)**scale

    # objective aggregation for multi-objective fallback scoring
    objective_aggregation: str = "sum"  # "sum" or "first"


class SimulatedAnnealingAdapter(AlgorithmAdapter):
    """Simulated annealing adapter for ComposableSolver."""

    # Soft partner contracts: SA communicates temperature and (optionally)
    # mutation scale via context. Representation mutator may consume these keys.
    requires_context_keys = {KEY_TEMPERATURE}
    recommended_mutators = ["ContextGaussianMutation", "ContextSwitchMutator"]

    def __init__(self, config: Optional[SAConfig] = None, name: str = "sa", priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or SAConfig()
        self.t0 = float(self.cfg.initial_temperature)
        self.temperature = float(self.cfg.initial_temperature)
        self.current_x: Optional[np.ndarray] = None
        self.current_score: Optional[float] = None
        self._warned_missing_operator = False

    def setup(self, solver: Any) -> None:
        self.t0 = float(self.cfg.initial_temperature)
        self.temperature = float(self.cfg.initial_temperature)
        self.current_x = None
        self.current_score = None
        self._warn_if_pipeline_has_no_mutator(solver)

    def _warn_if_pipeline_has_no_mutator(self, solver: Any) -> None:
        if self._warned_missing_operator:
            return

        pipeline = getattr(solver, "representation_pipeline", None)
        mutator = getattr(pipeline, "mutator", None) if pipeline is not None else None
        if mutator is None:
            warnings.warn(
                "SimulatedAnnealingAdapter 未检测到 representation_pipeline.mutator；"
                "SA 将无法产生邻域候选（会退化为几乎不移动）。"
                "建议：连续变量用 GaussianMutation/ContextGaussianMutation；"
                "离散/多邻域用 ContextSwitchMutator 或自定义 mutator。",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_missing_operator = True

    def _score(self, objectives_row: np.ndarray, violation: float) -> float:
        if self.cfg.objective_aggregation == "first":
            obj = float(objectives_row[0])
        else:
            obj = float(np.sum(objectives_row))
        return float(violation) * 1e6 + obj

    def _build_sa_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        ctx = dict(context)
        ctx[KEY_TEMPERATURE] = float(self.temperature)

        # Optional: couple temperature to neighborhood scale.
        # If the representation mutator consumes mutation_sigma, SA can "cool"
        # its step size naturally.
        if self.t0 > 0 and self.cfg.sigma_temperature_scale != 0.0:
            ratio = max(0.0, float(self.temperature) / float(self.t0))
            sigma = float(self.cfg.base_sigma) * (ratio ** float(self.cfg.sigma_temperature_scale))
            ctx[KEY_MUTATION_SIGMA] = float(sigma)
        return ctx

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.current_x is None:
            self.current_x = np.asarray(solver.init_candidate(context))

        ctx = self._build_sa_context(context)

        out = []
        for _ in range(max(1, int(self.cfg.batch_size))):
            cand = solver.mutate_candidate(self.current_x, ctx)
            cand = solver.repair_candidate(cand, ctx)
            out.append(np.asarray(cand))
        return out

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        if candidates is None or len(candidates) == 0:
            return
        if objectives is None or len(objectives) == 0:
            return

        # initialize score from first evaluation if needed
        if self.current_x is None:
            self.current_x = np.asarray(candidates[0])
        if self.current_score is None:
            v0 = float(violations[0]) if violations is not None else 0.0
            self.current_score = self._score(objectives[0], v0)

        # process batch sequentially; accept the first accepted move
        accepted_any = False
        for idx, cand in enumerate(candidates):
            vio = float(violations[idx]) if violations is not None else 0.0
            cand_score = self._score(objectives[idx], vio)

            delta = float(cand_score) - float(self.current_score)
            accept = False
            if delta <= 0:
                accept = True
            else:
                T = max(float(self.temperature), float(self.cfg.min_temperature))
                if T > 0:
                    p = math.exp(-delta / T)
                    accept = (np.random.random() < p)

            if accept:
                self.current_x = np.asarray(cand)
                self.current_score = float(cand_score)
                accepted_any = True
                break

        # cool down once per step (not per candidate)
        self.temperature = max(float(self.cfg.min_temperature), float(self.temperature) * float(self.cfg.cooling_rate))

        # expose current accepted state (optional convenience for plugins)
        solver.current_x = self.current_x
        solver.current_score = self.current_score
        solver.sa_temperature = float(self.temperature)
        solver.sa_accepted = bool(accepted_any)
