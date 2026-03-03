"""
Variable Neighborhood Search (VNS) as an AlgorithmAdapter.

This adapter keeps the framework's philosophy:
- Strategy logic in adapter (propose/update)
- Operators (mutation/repair) in RepresentationPipeline where possible
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import numpy as np

from .algorithm_adapter import AlgorithmAdapter
import warnings

from ..utils.context.context_keys import KEY_MUTATION_SIGMA, KEY_VNS_K


@dataclass
class VNSConfig:
    # number of candidates proposed per step
    batch_size: int = 32

    # neighborhood index range: k in [0, k_max]
    k_max: int = 5

    # sigma schedule: sigma = base_sigma * (scale ** k)
    base_sigma: float = 0.2
    scale: float = 1.6
    max_sigma: float = 10.0

    # accept if strictly better (with constraint penalty)
    accept_tolerance: float = 0.0

    # restart if no improvement after k_max neighborhoods
    restart_on_stagnation: bool = True

    # objective aggregation for multi-objective fallback scoring
    objective_aggregation: str = "sum"  # "sum" or "first"


class VNSAdapter(AlgorithmAdapter):
    """VNS adapter for ComposableSolver."""
    context_requires = ("generation",)
    context_provides = (KEY_VNS_K, KEY_MUTATION_SIGMA)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "VNS writes neighborhood index/sigma into per-step context for mutator consumption.",
        "Use context-aware mutator to make neighborhood switching effective.",
    )

    # Soft partner contracts (informational; no hard dependency).
    #
    # VNS itself is representation-agnostic. It communicates neighborhood changes
    # via `context` and expects the representation pipeline's mutator (or a wrapper)
    # to consume these keys.
    requires_context_keys = {KEY_VNS_K, KEY_MUTATION_SIGMA}
    recommended_mutators = ["ContextGaussianMutation", "ContextSwitchMutator"]

    def __init__(self, config: Optional[VNSConfig] = None, name: str = "vns", priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or VNSConfig()
        self.k = 0
        self.current_x: Optional[np.ndarray] = None
        self.current_score: Optional[float] = None
        self._warned_missing_operator = False
        self._last_context_projection: Dict[str, Any] = {}

    def setup(self, solver: Any) -> None:
        self.k = 0
        self.current_x = None
        self.current_score = None
        self._warn_if_pipeline_does_not_consume_context(solver)
        self._last_context_projection = {
            KEY_VNS_K: int(self.k),
            KEY_MUTATION_SIGMA: float(self._current_sigma()),
        }

    def _warn_if_pipeline_does_not_consume_context(self, solver: Any) -> None:
        if self._warned_missing_operator:
            return

        pipeline = getattr(solver, "representation_pipeline", None)
        mutator = getattr(pipeline, "mutator", None) if pipeline is not None else None
        if mutator is None:
            warnings.warn(
                "VNSAdapter 未检测到 representation_pipeline.mutator；VNS 只能产生固定邻域或直接失败。"
                "请配置 RepresentationPipeline(mutator=...)，连续变量推荐 ContextGaussianMutation，"
                "离散/排列推荐 ContextSwitchMutator。",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_missing_operator = True
            return

        # Heuristic detection: if a mutator exposes a context key it consumes,
        # it's likely context-aware. Otherwise, VNS still runs but neighborhood
        # switching may silently degrade.
        consumes = False
        for attr in ("sigma_key", "k_key", "context_key", "key"):
            if hasattr(mutator, attr):
                consumes = True
                break

        if not consumes:
            warnings.warn(
                "VNSAdapter 检测到当前 mutator 可能不会消费 context（未发现 sigma_key/k_key 等属性）。"
                "这会导致 VNS 的 k 邻域变化退化为“固定扰动”。"
                "建议：连续变量用 ContextGaussianMutation(sigma_key='mutation_sigma')；"
                "非连续/多邻域用 ContextSwitchMutator(k_key='vns_k') 或自定义可读 context 的 mutator。",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_missing_operator = True

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.current_x is None:
            self.current_x = np.asarray(solver.init_candidate(context))

        sigma = float(self._current_sigma())
        ctx = dict(context)
        ctx[KEY_VNS_K] = int(self.k)
        ctx[KEY_MUTATION_SIGMA] = float(sigma)
        self._last_context_projection = {
            KEY_VNS_K: int(self.k),
            KEY_MUTATION_SIGMA: float(sigma),
        }

        out = []
        for _ in range(int(self.cfg.batch_size)):
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

        scores = self._scores(objectives, violations)
        best_idx = int(np.argmin(scores))
        best_score = float(scores[best_idx])

        if self.current_score is None:
            self.current_score = best_score
            self.current_x = np.asarray(candidates[best_idx])
            self.k = 0
            return

        improved = (best_score + float(self.cfg.accept_tolerance)) < float(self.current_score)
        if improved:
            self.current_score = best_score
            self.current_x = np.asarray(candidates[best_idx])
            self.k = 0
            self._last_context_projection = {
                KEY_VNS_K: int(self.k),
                KEY_MUTATION_SIGMA: float(self._current_sigma()),
            }
            return

        # no improvement: move to next neighborhood
        self.k += 1
        if self.k > int(self.cfg.k_max):
            if bool(self.cfg.restart_on_stagnation):
                self.k = 0
                self.current_x = np.asarray(solver.init_candidate(context))
                self.current_score = None
            else:
                self.k = int(self.cfg.k_max)
        self._last_context_projection = {
            KEY_VNS_K: int(self.k),
            KEY_MUTATION_SIGMA: float(self._current_sigma()),
        }

    def _current_sigma(self) -> float:
        sigma = float(self.cfg.base_sigma) * (float(self.cfg.scale) ** int(self.k))
        return min(float(self.cfg.max_sigma), sigma)

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return dict(self._last_context_projection)

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {str(k): source for k in self._last_context_projection.keys()}

    def _scores(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        mode = str(self.cfg.objective_aggregation).lower().strip()
        if mode == "first":
            agg = obj[:, 0]
        else:
            agg = np.sum(obj, axis=1)
        return agg + (1e6 * vio)

    def get_state(self) -> Dict[str, Any]:
        return {
            "k": int(self.k),
            "current_x": None if self.current_x is None else np.asarray(self.current_x, dtype=float).tolist(),
            "current_score": None if self.current_score is None else float(self.current_score),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if "k" in state:
            self.k = int(state["k"])
        if "current_x" in state and state["current_x"] is not None:
            self.current_x = np.asarray(state["current_x"], dtype=float)
        if "current_score" in state:
            self.current_score = state["current_score"]
