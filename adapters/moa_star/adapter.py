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
import copy

import numpy as np

from blackbase.contracts import BatchDisposition

from ..algorithm_adapter import AlgorithmAdapter
from ...units import UnitBinding, UnitBuildRequest
from ...units.structures import ParetoLabelUnit, PARETO_LABEL_SCHEMA
from ...representation.unit_builders import ParetoLabelBuilder
from ...representation.structure_builders import encode_unit_value, decode_unit_value
from ...core.state import StepOutcome
from ...context_keys import KEY_SOLUTION_INPUT_REF
from ...units.contracts import candidate_array
from ..astar.pool_support import (capture_receipt, derive_neighbor, project_root, receipt_ref, receipt_selection,
                                  validate_receipt_map, validate_pending_receipts)


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
    repair_policy: str = "reject"  # reject | recompute
    pool_start_policy: Optional[str] = None  # None | "new_root"; never imports a path label.

    def __post_init__(self):
        if self.repair_policy not in {"reject", "recompute"}:
            raise ValueError("MOA* repair_policy must be reject or recompute")
        if self.pool_start_policy not in {None, "new_root"}:
            raise ValueError("MOA* pool_start_policy must be None or 'new_root'")


class MOAStarAdapter(AlgorithmAdapter):
    """Pareto A* adapter with dominance pruning per state."""
    unit_build_operations = ("fresh",)
    unit_schema = PARETO_LABEL_SCHEMA
    unit_contract_mode = "owned"
    accepts_proposal_replacement = False
    context_requires = ("generation",)
    context_optional = (KEY_SOLUTION_INPUT_REF,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Consumes context for neighbor expansion / heuristic / goal callbacks in multi-objective A*.",
    )
    state_recovery_level = "L1"
    state_recovery_notes = "Restores Pareto labels, frontier, pending parent identities and goals through the Unit codec."

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
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.set_unit_binding(config_kwargs.pop("unit_binding", None) or UnitBinding(ParetoLabelBuilder()))
        self.config = self.resolve_config(
            config=config,
            config_cls=MOAStarConfig,
            config_kwargs=config_kwargs,
            adapter_name="MOAStarAdapter",
        )
        self.cfg = self.config
        self.neighbors = neighbors
        self.goal_test = goal_test
        self.heuristic = heuristic
        self.edge_cost = edge_cost
        self.start_state = start_state
        self.state_key = state_key or self._default_state_key

        self._open: List[Tuple[float, int, int]] = []
        self._labels: Dict[int, ParetoLabelUnit] = {}
        self._state_labels: Dict[Any, List[int]] = {}
        self._counter = 0

        self._pending: List[Dict[str, Any]] = []
        self.num_objectives: Optional[int] = None

        self.found = False
        self.goal_states: List[State] = []
        self.pareto_states: List[State] = []
        self.pareto_costs: List[np.ndarray] = []
        self._root_initialized = False
        self._node_receipts = {}
        self._pareto_receipts = []
        self._goal_receipts = []

    @property
    def pool_input_modes(self):
        return ("initialize",) if self.cfg.pool_start_policy == "new_root" else ()

    def default_pool_input_count(self):
        return 1

    def setup(self, control: Any) -> None:
        self.validate_unit_bindings()
        self._open = []
        self._labels = {}
        self._state_labels = {}
        self._counter = 0
        self._pending = []
        self.found = False
        self.goal_states = []
        self.pareto_states = []
        self.pareto_costs = []
        self._root_initialized = False
        self._node_receipts = {}
        self._pareto_receipts = []
        self._goal_receipts = []

        try:
            self.num_objectives = int(getattr(control, "num_objectives", None) or 1)
        except Exception:
            self.num_objectives = 1

        if self.cfg.pool_start_policy is None:
            start = self._resolve_start_state(control, {})
            if start is not None:
                g0 = np.zeros(self.num_objectives, dtype=float)
                h0 = self._heuristic_vec(start, {})
                self._push_open(start, g=g0, h=h0, parent_key=None)

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        input_ref = context.get(KEY_SOLUTION_INPUT_REF)
        if input_ref is not None:
            if self.cfg.pool_start_policy != "new_root":
                raise ValueError("MOA* pool intake requires explicit pool_start_policy='new_root'")
            if self._root_initialized or self._open or self._labels:
                raise ValueError("MOA* pool intake starts a new tree; cannot replace an active search path")
            if control.solution_pool.input_remaining(input_ref) != 1:
                raise ValueError("MOA* requires exactly one root per pool initialization")
        if self.cfg.pool_start_policy == "new_root" and not self._root_initialized:
            start = control.init_candidate(context) if input_ref is not None else self._resolve_start_state(control, context)
            if start is None:
                return []
            start = project_root(control, start)
            values = candidate_array(start)
            zero = np.zeros(self.num_objectives or 1, dtype=float)
            self._pending = [dict(is_root=True, parent_key=None, parent_id=None,
                parent_state=None, parent_g=zero.copy(), base_g=zero.copy(), proposed_state=values.copy())]
            return [start]
        if self.found and self.cfg.stop_on_goal:
            return []

        if not self._open:
            if self.cfg.pool_start_policy == "new_root":
                return []
            start = self._resolve_start_state(control, context)
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
                self._goal_receipts.append(copy.deepcopy(self._node_receipts.get(label.unit_id)))
                if self.cfg.stop_on_goal:
                    self._pending = []
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
                self._pending.append({"parent_key": key, "base_g": np.array(base_g, copy=True),
                                      "parent_id": label.unit_id, "parent_state": label.state,
                                      "parent_g": label.g.copy(), "proposed_state": child_arr.copy(),
                                      "parent_receipt": copy.deepcopy(self._node_receipts.get(label.unit_id))})
                candidates.append(derive_neighbor(control, child_arr, self._node_receipts.get(label.unit_id), stage="moa_star_neighbor"))

            if len(candidates) >= int(self.cfg.max_candidates_per_step):
                break

        return candidates

    def get_empty_proposal_outcome(
        self,
        control: Any,
        context: Dict[str, Any],
    ) -> StepOutcome | None:
        _ = (control, context)
        if self.found and self.cfg.stop_on_goal:
            return StepOutcome(
                status="terminal",
                reason="goal_reached",
                metadata={"adapter": self.name, "completion": "success"},
            )
        if not self._open:
            return StepOutcome(
                status="terminal",
                reason="search_exhausted",
                metadata={"adapter": self.name, "completion": "exhausted"},
            )
        return None

    def on_proposal_repair(self, control, repair, context):
        if repair.proposed_count != len(self._pending):
            raise ValueError("MOA* repair does not align with pending paths")
        for row in repair.changed_rows:
            index = repair.proposal_indices[row]
            meta = self._pending[index]
            if not np.array_equal(repair.before.numeric_matrix[row], meta["proposed_state"], equal_nan=True):
                raise ValueError("MOA* repair source differs from pending path")
            if self.cfg.repair_policy == "reject" and not meta.get("is_root"):
                raise ValueError("MOA* candidate changed after proposal; repair_policy='reject'")
            candidate = repair.after.numeric_matrix[row]
            updated = dict(meta)
            if self.cfg.path_cost_mode == "edge" and not meta.get("is_root"):
                updated["base_g"] = meta["parent_g"] + self._edge_cost_vec(meta["parent_state"], candidate, context)
            # Heuristic and dominance are rebuilt from this candidate in update.
            updated["proposed_state"] = candidate.copy()
            self._pending[index] = updated

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        del control, context
        if disposition.proposed_count != len(self._pending):
            raise ValueError(
                "MOA* proposal disposition does not match pending path metadata: "
                f"proposed_count={disposition.proposed_count}, "
                f"pending_count={len(self._pending)}"
            )
        self._pending = [self._pending[index] for index in disposition.accepted_indices]

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        if getattr(feedback, "metadata", {}).get("subpool_projection") is not None:
            raise ValueError("MOA* does not accept objective projection feedback as graph cost")
        objectives, violations = feedback
        candidate_count = len(candidates)
        if candidate_count <= 0:
            return
        if candidate_count != len(self._pending):
            raise ValueError("MOA* feedback must align with pending path metadata")

        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if obj.shape[0] != candidate_count or vio.shape[0] != candidate_count:
            raise ValueError("MOA* candidate, objective, and violation counts must match")

        if self.num_objectives is None:
            self.num_objectives = int(obj.shape[1])

        for i, cand in enumerate(candidates):
            meta = self._pending[i]
            cand_arr = np.asarray(cand)
            changed = not np.array_equal(cand_arr, meta["proposed_state"], equal_nan=True)
            if changed and self.cfg.repair_policy == "reject" and not meta.get("is_root"):
                raise ValueError("MOA* repair changed the proposed state; opt into repair_policy='recompute'")

            obj_vec = obj[i]
            penalty = float(self.cfg.violation_penalty) * float(vio[i])
            pen_vec = np.full(obj_vec.shape, penalty, dtype=float)

            if meta.get("is_root") and self.cfg.path_cost_mode == "edge":
                g_vec = np.zeros_like(obj_vec)  # A new root has no inherited edge cost.
            elif self.cfg.path_cost_mode == "objective":
                g_vec = np.asarray(obj_vec + pen_vec, dtype=float)
            else:
                base_g = np.asarray(meta.get("base_g", np.zeros_like(obj_vec)), dtype=float)
                if changed:
                    base_g = meta["parent_g"] + self._edge_cost_vec(meta["parent_state"], cand_arr, context)
                g_vec = base_g + (float(self.cfg.objective_weight) * obj_vec) + pen_vec

            h_vec = self._heuristic_vec(cand_arr, context)
            receipt = capture_receipt(control, candidates, feedback, i, float(np.sum(obj_vec)) + penalty, vio[i])
            if self.cfg.pool_start_policy == "new_root" and receipt is None:
                raise ValueError("pool-root MOA* requires exact accepted feedback")
            self._try_add_label(cand_arr, g_vec, h_vec, meta.get("parent_key"), meta.get("parent_id"), context, receipt=receipt)
            if meta.get("is_root"):
                self._root_initialized = True
            # Existing path-label output excludes the zero-edge starting node.
            if not meta.get("is_root") or self.cfg.path_cost_mode == "objective":
                self._update_pareto(cand_arr, g_vec, receipt=receipt)
        self._pending = []
        self._prune_receipts()

    def _try_add_label(self, state: State, g: np.ndarray, h: np.ndarray, parent_key: Optional[Any], parent_id=None, context=None, *, receipt=None) -> None:
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

        label_id = self._counter + 1
        f = g + h
        label = self.unit_binding.build(UnitBuildRequest(
            f"{self.name}:label:{label_id}", state, parameters={
                "g": g, "h": h, "f": f, "parent_key": parent_key, "parent_id": parent_id}), context)
        if any(not np.array_equal(getattr(label, key), value) for key, value in (("g", g), ("h", h), ("f", f))):
            raise ValueError("MOA* builder changed Adapter-owned costs")

        for lbl_id in to_remove:
            lbl = self._labels.get(lbl_id)
            if lbl is not None:
                lbl.valid = False
            # Purge from dict to prevent unbounded memory growth (N-04).
            self._labels.pop(lbl_id, None)
        current = [i for i in current if i not in to_remove]

        self._counter = label_id
        self._labels[label_id] = label
        self._node_receipts[label.unit_id] = copy.deepcopy(receipt)
        current.append(label_id)
        self._state_labels[key] = current

        priority = self._priority(label.f)
        heapq.heappush(self._open, (priority, label_id, label_id))
        self._trim_open()
        self._prune_receipts()

    def _update_pareto(self, state: State, cost: np.ndarray, *, receipt=None) -> None:
        if not self.pareto_costs:
            self.pareto_costs = [cost]
            self.pareto_states = [np.asarray(state)]
            self._pareto_receipts = [copy.deepcopy(receipt)]
            return

        dominated = False
        new_costs: List[np.ndarray] = []
        new_states: List[State] = []
        new_receipts = []
        for c, s, previous in zip(self.pareto_costs, self.pareto_states, self._pareto_receipts, strict=True):
            if self._dominates(c, cost):
                dominated = True
                break
            if not self._dominates(cost, c):
                new_costs.append(c)
                new_states.append(s)
                new_receipts.append(previous)
        if dominated:
            return
        new_costs.append(cost)
        new_states.append(np.asarray(state))
        self.pareto_costs = new_costs
        self.pareto_states = new_states
        self._pareto_receipts = [*new_receipts, copy.deepcopy(receipt)]

    def _prune_receipts(self):
        live = {node.unit_id for node in self._labels.values()}
        self._node_receipts = {key: value for key, value in self._node_receipts.items() if key in live}

    def get_solution_pool_roots(self, control):
        values = [(self._node_receipts.get(node.unit_id), node.state) for node in self._labels.values()]
        values.extend((item.get("parent_receipt"), item["parent_state"])
                      for item in self._pending if item.get("parent_id") is not None)
        values.extend(zip(self._pareto_receipts, self.pareto_states, strict=True))
        values.extend(zip(self._goal_receipts, self.goal_states, strict=True))
        if any(receipt is None for receipt, _ in values):
            return None
        return tuple(dict.fromkeys(receipt_ref(receipt, control, candidate=candidate) for receipt, candidate in values))

    def get_pool_refinement_results(self, control):
        """Deliver nondominated_path_labels, using this search's existing g order.

        Costs are not raw Problem objectives or an objective projection. This
        accessor does not advertise bounded PoolTask refine/restart support.
        """
        return tuple(dict.fromkeys(receipt_ref(receipt, control, candidate=candidate)
            for receipt, candidate in zip(self._pareto_receipts, self.pareto_states, strict=True)))

    def _resolve_start_state(self, control: Any, context: Dict[str, Any]) -> Optional[State]:
        start = (self.start_state(context) if callable(self.start_state) else self.start_state
                 if self.start_state is not None else control.init_candidate(context))
        return start if self.cfg.pool_start_policy == "new_root" else np.asarray(start)

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
        except (TypeError, ValueError, OverflowError):
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
            "schema": "nsgablack.moa_star_state/v2",
            "unit_contract": self.get_unit_contract(),
            "found": bool(self.found),
            "pool_start_policy": self.cfg.pool_start_policy,
            "labels": [[key, self.unit_binding.dump(label)] for key, label in self._labels.items()],
            "runtime": encode_unit_value({"open": self._open, "state_labels": self._state_labels,
                "counter": self._counter, "pending": self._pending, "num_objectives": self.num_objectives,
                "goal_states": self.goal_states, "pareto_states": self.pareto_states, "pareto_costs": self.pareto_costs,
                "root_initialized": self._root_initialized, "node_receipts": self._node_receipts,
                "pareto_receipts": self._pareto_receipts, "goal_receipts": self._goal_receipts}),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if state.get("pool_start_policy") != self.cfg.pool_start_policy:
            raise ValueError("MOA* checkpoint pool root interpretation differs")
        if "unit_contract" not in state:  # Legacy summary-only checkpoint.
            self.found = bool(state.get("found", False))
            return
        if state["unit_contract"] != self.get_unit_contract():
            raise ValueError("MOA* checkpoint Unit binding mismatch")
        labels = {int(key): self.unit_binding.restore(payload) for key, payload in state["labels"]}
        data = decode_unit_value(state["runtime"])
        required = self.cfg.pool_start_policy == "new_root"
        nodes = {node.unit_id: node for node in labels.values()}
        receipts = validate_receipt_map(data.get("node_receipts", {key: None for key in nodes}), nodes, require=required)
        restored_results = {}
        for key, values in (("pareto_receipts", data["pareto_states"]), ("goal_receipts", data["goal_states"])):
            entries = data.get(key, [None] * len(values))
            if not isinstance(entries, list) or len(entries) != len(values):
                raise ValueError("MOA* result references must align with saved candidates")
            for entry, candidate in zip(entries, values):
                if entry is not None:
                    receipt_selection(entry, candidate=candidate)
                elif required:
                    raise ValueError("pool-root MOA* checkpoint requires exact result references")
            restored_results[key] = entries
        if required and type(data.get("root_initialized")) is not bool:
            raise ValueError("pool-root MOA* checkpoint requires its root admission state")
        validate_pending_receipts(data["pending"], require=required)
        if required and not data["root_initialized"] and labels:
            raise ValueError("uninitialized MOA* root cannot own existing labels")
        if required and data["root_initialized"] and any(item.get("is_root") for item in data["pending"]):
            raise ValueError("admitted MOA* root cannot be pending initialization")
        self._labels = labels
        self._open = data["open"]
        self._state_labels = data["state_labels"]
        self._counter = data["counter"]
        self._pending = data["pending"]
        self.num_objectives = data["num_objectives"]
        self.goal_states = data["goal_states"]
        self.pareto_states = data["pareto_states"]
        self.pareto_costs = data["pareto_costs"]
        self.found = bool(state["found"])
        self._root_initialized = data.get("root_initialized", False)
        self._node_receipts = receipts
        self._pareto_receipts = restored_results["pareto_receipts"]
        self._goal_receipts = restored_results["goal_receipts"]
