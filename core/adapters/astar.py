"""
A* adapter for ComposableSolver.

This adapter is intentionally generic:
- States are represented as 1D vectors (candidates).
- Neighbor generation, heuristic, and goal test are user-provided callables.
- Evaluation is still done by the solver (pipeline + constraints + bias).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union
import heapq

import numpy as np

from .algorithm_adapter import AlgorithmAdapter


State = np.ndarray
NeighborFn = Callable[[State, Dict[str, Any]], Iterable[State]]
GoalFn = Callable[[State, Dict[str, Any]], bool]
HeuristicFn = Callable[[State, Dict[str, Any]], float]
EdgeCostFn = Callable[[State, State, Dict[str, Any]], float]
StateKeyFn = Callable[[State], Any]


@dataclass
class AStarConfig:
    # number of nodes to expand per step
    max_expand_per_step: int = 1

    # cap the number of candidates proposed per step (avoid explosion)
    max_candidates_per_step: int = 128

    # how to aggregate multi-objective values into a scalar
    objective_aggregation: str = "sum"  # "sum" or "first"

    # path cost mode:
    # - "edge": g accumulates edge cost (optionally + objective_weight * objective)
    # - "objective": g uses objective directly (best-first with heuristic)
    path_cost_mode: str = "edge"  # "edge" | "objective"

    # objective contribution when path_cost_mode="edge"
    objective_weight: float = 1.0

    # constraint violation penalty added into g
    violation_penalty: float = 1e6

    # allow re-opening nodes if a better g is found
    allow_reopen: bool = False

    # optional cap for open list size (None = unlimited)
    max_open_size: Optional[int] = None

    # default rounding for state key (float vectors)
    key_rounding: int = 8


class _Node:
    __slots__ = ("state", "g", "h", "f", "parent_key")

    def __init__(self, state: State, g: float, h: float, parent_key: Optional[Any]):
        self.state = state
        self.g = float(g)
        self.h = float(h)
        self.f = float(g) + float(h)
        self.parent_key = parent_key


class AStarAdapter(AlgorithmAdapter):
    """Generic A* adapter driven by neighbor expansion and heuristic search."""
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Consumes context for neighbor expansion / heuristic / goal callbacks.",
    )

    def __init__(
        self,
        *,
        neighbors: NeighborFn,
        goal_test: Optional[GoalFn] = None,
        heuristic: Optional[HeuristicFn] = None,
        edge_cost: Optional[EdgeCostFn] = None,
        start_state: Optional[Union[Callable[[Dict[str, Any]], State], State]] = None,
        state_key: Optional[StateKeyFn] = None,
        config: Optional[AStarConfig] = None,
        name: str = "astar",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or AStarConfig()
        self.neighbors = neighbors
        self.goal_test = goal_test
        self.heuristic = heuristic
        self.edge_cost = edge_cost
        self.start_state = start_state
        self.state_key = state_key or self._default_state_key

        self._open: List[Tuple[float, int, _Node]] = []
        self._closed: Dict[Any, float] = {}
        self._pending: List[Dict[str, Any]] = []
        self._counter = 0

        self.found = False
        self.solution: Optional[State] = None
        self.best_score: Optional[float] = None
        self.best_state: Optional[State] = None

    def setup(self, solver: Any) -> None:
        self._open = []
        self._closed = {}
        self._pending = []
        self._counter = 0
        self.found = False
        self.solution = None
        self.best_score = None
        self.best_state = None

        start = self._resolve_start_state(solver, {})
        if start is not None:
            self._push_open(start, g=0.0, context={})

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.found:
            return []

        if not self._open:
            start = self._resolve_start_state(solver, context)
            if start is not None:
                self._push_open(start, g=0.0, context=context)
            if not self._open:
                return []

        candidates: List[np.ndarray] = []
        self._pending = []

        expanded = 0
        while self._open and expanded < int(self.cfg.max_expand_per_step):
            _, _, node = heapq.heappop(self._open)
            key = self.state_key(node.state)
            if key in self._closed and not self.cfg.allow_reopen:
                continue

            if self.goal_test is not None and self.goal_test(node.state, context):
                self.found = True
                self.solution = np.asarray(node.state)
                return []

            self._closed[key] = float(node.g)
            expanded += 1

            neighbors = self.neighbors(node.state, context)
            if neighbors is None:
                neighbors = []
            for child in neighbors:
                if len(candidates) >= int(self.cfg.max_candidates_per_step):
                    break
                child_arr = np.asarray(child)
                child_key = self.state_key(child_arr)
                if (child_key in self._closed) and (not self.cfg.allow_reopen):
                    continue
                base_g = float(node.g)
                if self.cfg.path_cost_mode == "edge":
                    base_g += float(self._edge_cost(node.state, child_arr, context))
                self._pending.append(
                    {
                        "parent_key": key,
                        "base_g": float(base_g),
                    }
                )
                candidates.append(child_arr)

            if len(candidates) >= int(self.cfg.max_candidates_per_step):
                break

        return candidates

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        if candidates is None:
            return
        try:
            candidate_count = len(candidates)
        except Exception:
            candidates = [candidates]  # type: ignore[list-item]
            candidate_count = 1
        if candidate_count <= 0:
            return

        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)

        for i, cand in enumerate(candidates):
            meta = self._pending[i] if i < len(self._pending) else {}
            cand_arr = np.asarray(cand)
            key = self.state_key(cand_arr)

            if (key in self._closed) and (not self.cfg.allow_reopen):
                continue

            obj_cost = self._aggregate_objective(obj[i])
            penalty = float(self.cfg.violation_penalty) * float(vio[i]) if i < len(vio) else 0.0

            if self.cfg.path_cost_mode == "objective":
                g = float(obj_cost) + penalty
            else:
                base_g = float(meta.get("base_g", 0.0))
                g = base_g + penalty + (float(self.cfg.objective_weight) * float(obj_cost))

            h = float(self._heuristic(cand_arr, context))
            self._push_open(cand_arr, g=g, h=h, parent_key=meta.get("parent_key"))

            # track best (by objective + penalty)
            score = float(obj_cost) + penalty
            if self.best_score is None or score < self.best_score:
                self.best_score = score
                self.best_state = np.asarray(cand_arr)

    def _resolve_start_state(self, solver: Any, context: Dict[str, Any]) -> Optional[State]:
        if callable(self.start_state):
            return np.asarray(self.start_state(context))
        if self.start_state is not None:
            return np.asarray(self.start_state)
        try:
            return np.asarray(solver.init_candidate(context))
        except Exception:
            return None

    def _edge_cost(self, parent: State, child: State, context: Dict[str, Any]) -> float:
        if self.edge_cost is not None:
            return float(self.edge_cost(parent, child, context))
        return 1.0

    def _heuristic(self, state: State, context: Dict[str, Any]) -> float:
        if self.heuristic is None:
            return 0.0
        try:
            return float(self.heuristic(state, context))
        except Exception:
            return 0.0

    def _aggregate_objective(self, obj_row: np.ndarray) -> float:
        mode = str(self.cfg.objective_aggregation).lower().strip()
        if mode == "first":
            return float(obj_row[0])
        return float(np.sum(obj_row))

    def _default_state_key(self, state: State) -> Any:
        arr = np.asarray(state)
        if arr.ndim == 0:
            return float(arr)
        try:
            rounded = np.round(arr.astype(float), int(self.cfg.key_rounding))
            return tuple(rounded.tolist())
        except Exception:
            return tuple(arr.ravel().tolist())

    def _push_open(
        self,
        state: State,
        *,
        g: float,
        h: Optional[float] = None,
        parent_key: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if h is None:
            h = self._heuristic(state, context or {})
        node = _Node(state=state, g=float(g), h=float(h), parent_key=parent_key)
        self._counter += 1
        heapq.heappush(self._open, (node.f, self._counter, node))
        self._trim_open()

    def _trim_open(self) -> None:
        max_open = self.cfg.max_open_size
        if max_open is None:
            return
        max_open = int(max_open)
        if max_open <= 0:
            return
        if len(self._open) <= max_open:
            return
        # keep the best N by f
        self._open = heapq.nsmallest(max_open, self._open)
        heapq.heapify(self._open)

    def get_state(self) -> Dict[str, Any]:
        return {
            "found": bool(self.found),
            "best_score": None if self.best_score is None else float(self.best_score),
            "best_state": None if self.best_state is None else np.asarray(self.best_state).tolist(),
            "open_size": int(len(self._open)),
            "closed_size": int(len(self._closed)),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if "found" in state:
            self.found = bool(state["found"])
        if "best_score" in state:
            self.best_score = state["best_score"]
        bs = state.get("best_state")
        if bs is not None:
            self.best_state = np.asarray(bs, dtype=float)
