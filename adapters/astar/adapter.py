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
import copy

import numpy as np

from blackbase.contracts import BatchDisposition

from ..algorithm_adapter import AlgorithmAdapter
from ...representation.structure_builders import encode_unit_value, decode_unit_value
from ...core.state import StepOutcome
from ...units import UnitBinding, UnitBuildRequest, SearchNodeUnit, SEARCH_NODE_SCHEMA
from ...representation.unit_builders import SearchNodeBuilder
from ...context_keys import KEY_SOLUTION_INPUT_REF
from ...units.contracts import candidate_array
from .pool_support import (capture_receipt, derive_neighbor, project_root, receipt_ref, receipt_selection,
                           validate_receipt_map, validate_pending_receipts)


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

    # A repaired child is no longer necessarily adjacent to its recorded parent.
    # Recompute is opt-in for domains whose edge_cost accepts the repaired edge.
    repair_policy: str = "reject"  # reject | recompute
    # Explicitly interpret a pool seed as a new root, never an imported path.
    pool_start_policy: Optional[str] = None  # None | "new_root"


class AStarAdapter(AlgorithmAdapter):
    """Generic A* adapter driven by neighbor expansion and heuristic search."""
    unit_build_operations = ("fresh", "spawn")
    context_requires = ("generation",)
    context_optional = (KEY_SOLUTION_INPUT_REF,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Consumes context for neighbor expansion / heuristic / goal callbacks.",
    )
    state_recovery_level = "L1"
    state_recovery_notes = "Restores node Units, open/closed frontier and pending parent identities."
    unit_schema = SEARCH_NODE_SCHEMA
    unit_contract_mode = "owned"
    accepts_proposal_replacement = False

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
        unit_binding: Optional[UnitBinding] = None,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=AStarConfig,
            config_kwargs=config_kwargs,
            adapter_name="AStarAdapter",
        )
        self.cfg = self.config
        if self.cfg.repair_policy not in {"reject", "recompute"}:
            raise ValueError("A* repair_policy must be reject or recompute")
        if self.cfg.pool_start_policy not in {None, "new_root"}:
            raise ValueError("A* pool_start_policy must be None or 'new_root'")
        self.set_unit_binding(unit_binding or UnitBinding(SearchNodeBuilder()))
        self.neighbors = neighbors
        self.goal_test = goal_test
        self.heuristic = heuristic
        self.edge_cost = edge_cost
        self.start_state = start_state
        self.state_key = state_key or self._default_state_key

        self._open: List[Tuple[float, int, SearchNodeUnit]] = []
        self._closed: Dict[Any, float] = {}
        self._pending: List[Dict[str, Any]] = []
        self._counter = 0

        self.found = False
        self.solution: Optional[State] = None
        self.best_score: Optional[float] = None
        self.best_state: Optional[State] = None
        self._root_initialized = False
        self._node_receipts = {}
        self._best_receipt = None
        self._solution_receipt = None

    @property
    def pool_input_modes(self):
        return ("initialize",) if self.cfg.pool_start_policy == "new_root" else ()

    def default_pool_input_count(self):
        return 1

    def setup(self, control: Any) -> None:
        self.validate_unit_bindings()
        self._open = []
        self._closed = {}
        self._pending = []
        self._counter = 0
        self.found = False
        self.solution = None
        self.best_score = None
        self.best_state = None
        self._root_initialized = False
        self._node_receipts = {}
        self._best_receipt = self._solution_receipt = None

        if self.cfg.pool_start_policy is None:
            start = self._resolve_start_state(control, {})
            if start is not None:
                self._push_open(start, g=0.0, context={})

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        input_ref = context.get(KEY_SOLUTION_INPUT_REF)
        if input_ref is not None:
            if self.cfg.pool_start_policy != "new_root":
                raise ValueError("A* pool intake requires explicit pool_start_policy='new_root'")
            if self._root_initialized or self._open or self._closed:
                raise ValueError("A* pool intake starts a new tree; cannot replace an active search path")
            if control.solution_pool.input_remaining(input_ref) != 1:
                raise ValueError("A* requires exactly one root per pool initialization")
        if self.cfg.pool_start_policy == "new_root" and not self._root_initialized:
            start = control.init_candidate(context) if input_ref is not None else self._resolve_start_state(control, context)
            if start is None:
                return []
            start = project_root(control, start)
            values = candidate_array(start)
            self._pending = [dict(is_root=True, parent_key=None, parent_id=None,
                parent_state=None, parent_g=0., base_g=0., proposed_state=values.copy())]
            return [start]
        if self.found:
            return []

        if not self._open:
            if self.cfg.pool_start_policy == "new_root":
                return []
            start = self._resolve_start_state(control, context)
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
                self._solution_receipt = self._node_receipts.get(node.unit_id)
                self._pending = []
                self._prune_receipts()
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
                        "parent_g": float(node.g),
                        "parent_state": node.state.copy(),
                        "parent_id": node.unit_id,
                        "proposed_state": child_arr.copy(),
                        "parent_receipt": copy.deepcopy(self._node_receipts.get(node.unit_id)),
                    }
                )
                candidates.append(derive_neighbor(control, child_arr, self._node_receipts.get(node.unit_id), stage="astar_neighbor"))

            if len(candidates) >= int(self.cfg.max_candidates_per_step):
                break

        self._prune_receipts()
        return candidates

    def get_empty_proposal_outcome(
        self,
        control: Any,
        context: Dict[str, Any],
    ) -> StepOutcome | None:
        _ = (control, context)
        if self.found:
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
            raise ValueError("A* repair does not align with pending paths")
        for row in repair.changed_rows:
            index = repair.proposal_indices[row]
            meta = self._pending[index]
            if not np.array_equal(repair.before.numeric_matrix[row], meta["proposed_state"], equal_nan=True):
                raise ValueError("A* repair source differs from pending path")
            if self.cfg.repair_policy == "reject" and not meta.get("is_root"):
                raise ValueError("A* candidate changed after proposal; repair_policy='reject'")
            candidate = repair.after.numeric_matrix[row]
            updated = dict(meta)
            if self.cfg.path_cost_mode == "edge" and not meta.get("is_root"):
                updated["base_g"] = float(meta["parent_g"]) + self._edge_cost(meta["parent_state"], candidate, context)
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
                "A* proposal disposition does not match pending path metadata: "
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
            raise ValueError("A* does not accept objective projection feedback as graph cost")
        objectives, violations = feedback
        candidate_count = len(candidates)
        if candidate_count <= 0:
            return
        if candidate_count != len(self._pending):
            raise ValueError("A* feedback must align with pending path metadata")

        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if obj.shape[0] != candidate_count or vio.shape[0] != candidate_count:
            raise ValueError("A* candidate, objective, and violation counts must match")

        for i, cand in enumerate(candidates):
            meta = self._pending[i]
            cand_arr = np.asarray(cand)
            key = self.state_key(cand_arr)

            changed = not np.array_equal(cand_arr, meta["proposed_state"], equal_nan=True)
            if changed and self.cfg.repair_policy == "reject" and not meta.get("is_root"):
                raise ValueError("A* candidate changed after proposal; repair_policy='reject' "
                                 "protects the parent edge. Use recompute only for compatible edges.")

            if (key in self._closed) and (not self.cfg.allow_reopen):
                continue

            obj_cost = self._aggregate_objective(obj[i])
            penalty = float(self.cfg.violation_penalty) * float(vio[i])

            if meta.get("is_root") and self.cfg.path_cost_mode == "edge":
                g = 0.0  # No parent edge exists; seed evaluation is not accumulated path cost.
            elif self.cfg.path_cost_mode == "objective":
                g = float(obj_cost) + penalty
            else:
                base_g = float(meta.get("base_g", 0.0))
                if changed:
                    base_g = float(meta["parent_g"]) + self._edge_cost(meta["parent_state"], cand_arr, context)
                g = base_g + penalty + (float(self.cfg.objective_weight) * float(obj_cost))

            h = float(self._heuristic(cand_arr, context))
            score = float(obj_cost) + penalty
            receipt = capture_receipt(control, candidates, feedback, i, score, vio[i])
            if self.cfg.pool_start_policy == "new_root" and receipt is None:
                raise ValueError("pool-root A* requires exact accepted feedback")
            self._push_open(cand_arr, g=g, h=h, parent_key=meta.get("parent_key"),
                            parent_id=meta.get("parent_id"), context=context, receipt=receipt)
            if meta.get("is_root"):
                self._root_initialized = True

            # track best (by objective + penalty)
            if self.best_score is None or score < self.best_score:
                self.best_score = score
                self.best_state = np.asarray(cand_arr)
                self._best_receipt = receipt
        self._pending = []
        self._prune_receipts()

    def _resolve_start_state(self, control: Any, context: Dict[str, Any]) -> Optional[State]:
        start = (self.start_state(context) if callable(self.start_state) else self.start_state
                 if self.start_state is not None else control.init_candidate(context))
        # A lazily admitted root retains semantic metadata and source identity.
        return start if self.cfg.pool_start_policy == "new_root" else np.asarray(start)

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
            raise

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
        except (TypeError, ValueError, OverflowError):
            return tuple(arr.ravel().tolist())

    def _push_open(
        self,
        state: State,
        *,
        g: float,
        h: Optional[float] = None,
        parent_key: Optional[Any] = None,
        parent_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        receipt=None,
    ) -> None:
        if h is None:
            h = self._heuristic(state, context or {})
        next_id = self._counter + 1
        node = self.unit_binding.build(UnitBuildRequest(
            unit_id=f"{self.name}:node:{next_id}", candidate=state,
            purpose="fresh" if parent_id is None else "spawn",
            parameters={"g": float(g), "h": float(h), "f": float(g) + float(h),
                        "parent_key": parent_key, "parent_id": parent_id},
        ), context)
        if (node.g, node.h, node.f) != (float(g), float(h), float(g) + float(h)):
            raise ValueError("A* Unit builder must preserve Adapter-supplied costs and priority")
        self._counter = next_id
        heapq.heappush(self._open, (node.f, self._counter, node))
        self._node_receipts[node.unit_id] = copy.deepcopy(receipt)
        self._trim_open()
        self._prune_receipts()

    def _prune_receipts(self):
        live = {node.unit_id for _, _, node in self._open}
        self._node_receipts = {key: value for key, value in self._node_receipts.items() if key in live}

    def get_solution_pool_roots(self, control):
        values = [(self._node_receipts.get(node.unit_id), node.state) for _, _, node in self._open]
        values.extend((item.get("parent_receipt"), item["parent_state"])
                      for item in self._pending if item.get("parent_id") is not None)
        values.extend((receipt, candidate) for receipt, candidate in (
            (self._best_receipt, self.best_state), (self._solution_receipt, self.solution)) if candidate is not None)
        if any(receipt is None for receipt, _ in values):
            return None
        return tuple(dict.fromkeys(receipt_ref(receipt, control, candidate=candidate) for receipt, candidate in values))

    def get_pool_refinement_results(self, control):
        """Deliver best_evaluated (objective aggregation plus penalty), not path g.

        This result accessor does not promise bounded PoolTask refine/restart.
        Goal-path import and objective projections require separate semantics.
        """
        return () if self.best_state is None else (receipt_ref(self._best_receipt, control, candidate=self.best_state),)

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

    def _summary_state(self) -> Dict[str, Any]:
        return {
            "unit_contract": self.get_unit_contract(),
            "found": bool(self.found),
            "best_score": None if self.best_score is None else float(self.best_score),
            "best_state": None if self.best_state is None else np.asarray(self.best_state).tolist(),
            "open_size": int(len(self._open)),
            "closed_size": int(len(self._closed)),
            "pool_start_policy": self.cfg.pool_start_policy,
        }

    def _restore_summary(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if "unit_contract" in state and state["unit_contract"] != self.get_unit_contract():
            raise ValueError("A* checkpoint Unit binding mismatch")
        if state.get("pool_start_policy") != self.cfg.pool_start_policy:
            raise ValueError("A* checkpoint pool root interpretation differs")
        if "found" in state:
            self.found = bool(state["found"])
        if "best_score" in state:
            self.best_score = state["best_score"]
        bs = state.get("best_state")
        if bs is not None:
            self.best_state = np.asarray(bs, dtype=float)

    def snapshot_step_state(self) -> Dict[str, Any]:
        # Capture detached node payloads; construction pipelines are never replayed.
        return copy.deepcopy({
            "summary": self._summary_state(),
            "open": [(priority, order, self.unit_binding.dump(node))
                     for priority, order, node in self._open],
            "closed": self._closed, "pending": self._pending, "counter": self._counter,
            "solution": self.solution,
            "root_initialized": self._root_initialized, "node_receipts": self._node_receipts,
            "best_receipt": self._best_receipt, "solution_receipt": self._solution_receipt,
        })

    def restore_step_state(self, state) -> None:
        restored = copy.deepcopy(dict(state))
        if restored["summary"].get("pool_start_policy") != self.cfg.pool_start_policy:
            raise ValueError("A* checkpoint pool root interpretation differs")
        frontier = [(priority, order, self.unit_binding.restore(payload))
                    for priority, order, payload in restored["open"]]
        required = self.cfg.pool_start_policy == "new_root"
        nodes = {node.unit_id: node for _, _, node in frontier}
        receipts = validate_receipt_map(restored.get("node_receipts", {key: None for key in nodes}), nodes, require=required)
        for key, candidate in (("best_receipt", restored["summary"].get("best_state")),
                               ("solution_receipt", restored["solution"])):
            value = restored.get(key)
            if value is not None:
                receipt_selection(value, candidate=candidate)
            elif required and candidate is not None:
                raise ValueError("pool-root A* checkpoint requires exact result references")
        if required and type(restored.get("root_initialized")) is not bool:
            raise ValueError("pool-root A* checkpoint requires its root admission state")
        validate_pending_receipts(restored["pending"], require=required)
        if required and not restored["root_initialized"] and (frontier or restored["closed"]):
            raise ValueError("uninitialized A* root cannot own an existing tree")
        if required and restored["root_initialized"] and any(item.get("is_root") for item in restored["pending"]):
            raise ValueError("admitted A* root cannot be pending initialization")
        self._restore_summary(restored["summary"])
        self.best_state = (None if restored["summary"]["best_state"] is None
                           else np.asarray(restored["summary"]["best_state"]))
        self._open = frontier
        self._closed = restored["closed"]
        self._pending = restored["pending"]
        self._counter = restored["counter"]
        self.solution = restored["solution"]
        self._root_initialized = restored.get("root_initialized", False)
        self._node_receipts = receipts
        self._best_receipt = restored.get("best_receipt")
        self._solution_receipt = restored.get("solution_receipt")

    def get_state(self) -> Dict[str, Any]:
        return {**self._summary_state(), "frontier_state": encode_unit_value(self.snapshot_step_state())}

    def set_state(self, state: Dict[str, Any]) -> None:
        if "frontier_state" in state:
            self.restore_step_state(decode_unit_value(state["frontier_state"]))
        else:
            self._restore_summary(state)
