"""
Multi-objective A* (Pareto A*) adapter for ComposableSolver.

This is a lightweight, generic implementation:
- Maintains a Pareto set of cost labels per state (dominance pruning).
- Uses a scalar priority for the open list while keeping nondominated labels.
- Delegates evaluation to solver (pipeline + constraints + bias).
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
HeuristicFn = Callable[[State, Dict[str, Any]], Union[float, Sequence[float], np.ndarray]]
EdgeCostFn = Callable[[State, State, Dict[str, Any]], Union[float, Sequence[float], np.ndarray]]
StateKeyFn = Callable[[State], Any]


@dataclass
class MOAStarConfig:
    # number of nodes to expand per step
    max_expand_per_step: int = 1

    # cap the number of candidates proposed per step (avoid explosion)
    max_candidates_per_step: int = 128

    # path cost mode:
    # - "edge": g accumulates edge cost (+ objective_weight * objective)
    # - "objective": g uses objectives directly (best-first with heuristic)
    path_cost_mode: str = "objective"  # "edge" | "objective"

    # objective contribution when path_cost_mode="edge"
    objective_weight: float = 1.0

    # constraint violation penalty added into each objective
    violation_penalty: float = 1e6

    # allow re-opening nodes if a better g is found
    allow_reopen: bool = False

    # optional cap for open list size (None = unlimited)
    max_open_size: Optional[int] = None

    # default rounding for state key (float vectors)
    key_rounding: int = 8

    # priority scalarization for the open list
    priority_mode: str = "sum"  # "sum" | "first" | "weighted"
    priority_weights: Optional[Sequence[float]] = None

    # heuristic scaling (applied to h vector)
    heuristic_scale: float = 1.0

    # stop when a goal is found (multi-objective default: False)
    stop_on_goal: bool = False


class _Label:
    __slots__ = ("state", "g", "h", "f", "parent_key", "valid")

    def __init__(self, state: State, g: np.ndarray, h: np.ndarray, parent_key: Optional[Any]):
        self.state = state
        self.g = g
        self.h = h
        self.f = g + h
        self.parent_key = parent_key
        self.valid = True


class MOAStarAdapter(AlgorithmAdapter):
    """Pareto A* adapter with dominance pruning per state."""
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Consumes context for neighbor expansion / heuristic / goal callbacks in multi-objective A*.",
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
        config: Optional[MOAStarConfig] = None,
        name: str = "moa_star",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or MOAStarConfig()
        self.neighbors = neighbors
        self.goal_test = goal_test
        self.heuristic = heuristic
        self.edge_cost = edge_cost
        self.start_state = start_state
        self.state_key = state_key or self._default_state_key

        self._open: List[Tuple[float, int, int]] = []
        self._labels: Dict[int, _Label] = {}
        self._state_labels: Dict[Any, List[int]] = {}
        self._counter = 0

        self._pending: List[Dict[str, Any]] = []
        self.num_objectives: Optional[int] = None

        self.found = False
        self.goal_states: List[State] = []
        self.pareto_states: List[State] = []
        self.pareto_costs: List[np.ndarray] = []

    def setup(self, solver: Any) -> None:
        self._open = []
        self._labels = {}
        self._state_labels = {}
        self._counter = 0
        self._pending = []
        self.found = False
        self.goal_states = []
        self.pareto_states = []
        self.pareto_costs = []

        try:
            self.num_objectives = int(getattr(solver, "num_objectives", None) or 1)
        except Exception:
            self.num_objectives = 1

        start = self._resolve_start_state(solver, {})
        if start is not None:
            g0 = np.zeros(self.num_objectives, dtype=float)
            h0 = self._heuristic_vec(start, {})
            self._push_open(start, g=g0, h=h0, parent_key=None)

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.found and self.cfg.stop_on_goal:
            return []

        if not self._open:
            start = self._resolve_start_state(solver, context)
            if start is not None:
                g0 = np.zeros(self.num_objectives or 1, dtype=float)
                h0 = self._heuristic_vec(start, context)
                self._push_open(start, g=g0, h=h0, parent_key=None)
            if not self._open:
                return []

        candidates: List[np.ndarray] = []
        self._pending = []

        expanded = 0
        while self._open and expanded < int(self.cfg.max_expand_per_step):
            _, _, label_id = heapq.heappop(self._open)
            label = self._labels.get(label_id)
            if label is None or not label.valid:
                continue

            key = self.state_key(label.state)
            if self.goal_test is not None and self.goal_test(label.state, context):
                self.found = True
                self.goal_states.append(np.asarray(label.state))
                if self.cfg.stop_on_goal:
                    return []

            expanded += 1

            neighbors = self.neighbors(label.state, context)
            if neighbors is None:
                neighbors = []
            for child in neighbors:
                if len(candidates) >= int(self.cfg.max_candidates_per_step):
                    break
                child_arr = np.asarray(child)
                base_g = label.g
                if self.cfg.path_cost_mode == "edge":
                    base_g = base_g + self._edge_cost_vec(label.state, child_arr, context)
                self._pending.append({"parent_key": key, "base_g": base_g})
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

        if self.num_objectives is None:
            self.num_objectives = int(obj.shape[1])

        for i, cand in enumerate(candidates):
            meta = self._pending[i] if i < len(self._pending) else {}
            cand_arr = np.asarray(cand)

            obj_vec = obj[i]
            penalty = float(self.cfg.violation_penalty) * float(vio[i]) if i < len(vio) else 0.0
            pen_vec = np.full(obj_vec.shape, penalty, dtype=float)

            if self.cfg.path_cost_mode == "objective":
                g_vec = np.asarray(obj_vec + pen_vec, dtype=float)
            else:
                base_g = np.asarray(meta.get("base_g", np.zeros_like(obj_vec)), dtype=float)
                g_vec = base_g + (float(self.cfg.objective_weight) * obj_vec) + pen_vec

            h_vec = self._heuristic_vec(cand_arr, context)
            self._try_add_label(cand_arr, g_vec, h_vec, meta.get("parent_key"))
            self._update_pareto(cand_arr, g_vec)

    def _try_add_label(self, state: State, g: np.ndarray, h: np.ndarray, parent_key: Optional[Any]) -> None:
        key = self.state_key(state)
        current = self._state_labels.get(key, [])

        # dominance checks against existing labels for this state
        dominated_by_existing = False
        to_remove: List[int] = []
        for lbl_id in current:
            lbl = self._labels.get(lbl_id)
            if lbl is None or not lbl.valid:
                continue
            if self._dominates(lbl.g, g):
                dominated_by_existing = True
                break
            if self._dominates(g, lbl.g):
                to_remove.append(lbl_id)

        if dominated_by_existing:
            return

        for lbl_id in to_remove:
            lbl = self._labels.get(lbl_id)
            if lbl is not None:
                lbl.valid = False
            # Purge from dict to prevent unbounded memory growth (N-04).
            self._labels.pop(lbl_id, None)
        current = [i for i in current if i not in to_remove]

        self._counter += 1
        label_id = self._counter
        label = _Label(state=state, g=g, h=h, parent_key=parent_key)
        self._labels[label_id] = label
        current.append(label_id)
        self._state_labels[key] = current

        priority = self._priority(label.f)
        heapq.heappush(self._open, (priority, label_id, label_id))
        self._trim_open()

    def _update_pareto(self, state: State, cost: np.ndarray) -> None:
        if not self.pareto_costs:
            self.pareto_costs = [cost]
            self.pareto_states = [np.asarray(state)]
            return

        dominated = False
        new_costs: List[np.ndarray] = []
        new_states: List[State] = []
        for c, s in zip(self.pareto_costs, self.pareto_states):
            if self._dominates(c, cost):
                dominated = True
                break
            if not self._dominates(cost, c):
                new_costs.append(c)
                new_states.append(s)
        if dominated:
            return
        new_costs.append(cost)
        new_states.append(np.asarray(state))
        self.pareto_costs = new_costs
        self.pareto_states = new_states

    def _resolve_start_state(self, solver: Any, context: Dict[str, Any]) -> Optional[State]:
        if callable(self.start_state):
            return np.asarray(self.start_state(context))
        if self.start_state is not None:
            return np.asarray(self.start_state)
        try:
            return np.asarray(solver.init_candidate(context))
        except Exception:
            return None

    def _edge_cost_vec(self, parent: State, child: State, context: Dict[str, Any]) -> np.ndarray:
        if self.edge_cost is None:
            return np.zeros(self.num_objectives or 1, dtype=float)
        raw = self.edge_cost(parent, child, context)
        return self._as_vec(raw)

    def _heuristic_vec(self, state: State, context: Dict[str, Any]) -> np.ndarray:
        if self.heuristic is None:
            return np.zeros(self.num_objectives or 1, dtype=float)
        raw = self.heuristic(state, context)
        vec = self._as_vec(raw)
        return vec * float(self.cfg.heuristic_scale)

    def _as_vec(self, value: Union[float, Sequence[float], np.ndarray]) -> np.ndarray:
        if np.isscalar(value):
            size = int(self.num_objectives or 1)
            return np.full(size, float(value), dtype=float)
        arr = np.asarray(value, dtype=float).ravel()
        size = int(self.num_objectives or arr.size or 1)
        if arr.size < size:
            out = np.zeros(size, dtype=float)
            out[: arr.size] = arr
            return out
        if arr.size > size:
            return arr[:size]
        return arr

    def _priority(self, f_vec: np.ndarray) -> float:
        mode = str(self.cfg.priority_mode).lower().strip()
        if mode == "first":
            return float(f_vec[0])
        if mode == "weighted":
            weights = self.cfg.priority_weights
            if weights is None:
                return float(np.sum(f_vec))
            w = np.asarray(list(weights), dtype=float).ravel()
            if w.size < f_vec.size:
                w = np.pad(w, (0, f_vec.size - w.size), constant_values=1.0)
            if w.size > f_vec.size:
                w = w[: f_vec.size]
            return float(np.sum(f_vec * w))
        return float(np.sum(f_vec))

    def _dominates(self, a: np.ndarray, b: np.ndarray) -> bool:
        a = np.asarray(a, dtype=float).ravel()
        b = np.asarray(b, dtype=float).ravel()
        return bool(np.all(a <= b) and np.any(a < b))

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
        g: np.ndarray,
        h: np.ndarray,
        parent_key: Optional[Any],
    ) -> None:
        self._try_add_label(state, g, h, parent_key)

    def _trim_open(self) -> None:
        max_open = self.cfg.max_open_size
        if max_open is None:
            return
        max_open = int(max_open)
        if max_open <= 0:
            return
        if len(self._open) <= max_open:
            return
        self._open = heapq.nsmallest(max_open, self._open)
        heapq.heapify(self._open)

    def get_state(self) -> Dict[str, Any]:
        return {
            "found": bool(self.found),
            "goal_states": len(self.goal_states),
            "pareto_size": len(self.pareto_states),
            "open_size": int(len(self._open)),
            "labels": int(len(self._labels)),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if "found" in state:
            self.found = bool(state["found"])
