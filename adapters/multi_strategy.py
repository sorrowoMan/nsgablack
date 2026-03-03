"""
Multi-strategy controller adapter (cooperative parallel algorithms).

This is the "fully-decomposed" home for:
- multi-algorithm parallel cooperation
- role-like strategy orchestration
- shared information broadcast (archive / best / metrics) via context

Design goals:
- Keep solver bases pure: no special loops, just Adapter propose/update.
- Keep strategies isolated: each child adapter owns its internal state.
- Enable communication: controller publishes shared state into context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
import math

import numpy as np

from .algorithm_adapter import AlgorithmAdapter
from ..utils.context.context_keys import (
    KEY_CANDIDATE_ROLES,
    KEY_CANDIDATE_UNITS,
    KEY_ROLE,
    KEY_ROLE_ADAPTER,
    KEY_ROLE_INDEX,
    KEY_ROLE_REPORTS,
    KEY_SHARED,
    KEY_STRATEGY,
    KEY_STRATEGY_ID,
    KEY_TASK,
    KEY_PHASE,
    KEY_REGION_BOUNDS,
    KEY_REGION_ID,
    KEY_SEEDS,
    KEY_UNIT_TASKS,
)


@dataclass
class StrategySpec:
    """One cooperating strategy (role) in the controller."""

    adapter: AlgorithmAdapter
    name: str
    weight: float = 1.0
    enabled: bool = True


@dataclass
class RoleSpec:
    """
    One role with multiple independent units.

    This is the recommended shape for "many agents per role":
    - each unit gets its own adapter instance (private internal state)
    - controller allocates budget at role-level, then splits to units
    """

    name: str
    adapter: Union[AlgorithmAdapter, Callable[[int], AlgorithmAdapter], Callable[[], AlgorithmAdapter]]
    n_units: int = 1
    weight: float = 1.0
    enabled: bool = True


@dataclass
class UnitSpec:
    role: str
    unit_id: int
    adapter: AlgorithmAdapter
    enabled: bool = True


@dataclass
class MultiStrategyConfig:
    # Total candidates per step across all strategies.
    total_batch_size: int = 64

    # How to aggregate multi-objective into a scalar score (fallback).
    objective_aggregation: str = "sum"  # "sum" or "first"

    # Constraint penalty scale for scalar score.
    violation_penalty: float = 1e6

    # Dynamic scheduling: adapt weights based on recent improvements.
    adapt_weights: bool = True
    adapt_momentum: float = 0.2  # EMA update rate for scores
    stagnation_boost: float = 0.5  # boost exploration for stagnant strategies
    stagnation_window: int = 10  # steps without improvement to consider stagnant
    min_weight: float = 0.05
    max_weight: float = 10.0

    # ------------------------------------------------------------
    # Phase scheduling (macro-serial, micro-parallel)
    #
    # Example: [("explore", 30), ("exploit", -1)]
    # - step 0..29: explore
    # - step 30..end: exploit
    phase_schedule: Tuple[Tuple[str, int], ...] = (("explore", 10), ("exploit", -1))

    # Optional: restrict enabled roles per phase.
    # Example: {"explore": ["ga"], "exploit": ["vns", "sa"]}
    phase_roles: Optional[Dict[str, List[str]]] = None

    # Optional: multiply role weights per phase (before budget allocation).
    # Example: {"exploit": {"vns": 2.0}}
    phase_weight_multipliers: Optional[Dict[str, Dict[str, float]]] = None

    # ------------------------------------------------------------
    # Region partitioning + task assignment
    enable_regions: bool = False
    n_regions: int = 8
    region_overlap: float = 0.1  # fraction of region length to overlap on split axis
    region_update_interval: int = 10  # recompute regions every N steps (0 disables)

    # ------------------------------------------------------------
    # Seeding for exploit/deepen phases
    seeds_per_task: int = 1
    seeds_source: str = "pareto"  # "pareto" or "best"


class MultiStrategyControllerAdapter(AlgorithmAdapter):
    """
    Controller adapter that orchestrates multiple child adapters.

    Each step:
    - Allocate budget to each enabled strategy by weight.
    - Call child.propose() with strategy-scoped context (adds KEY_STRATEGY/ID).
    - Evaluate all candidates together (solver does that).
    - Split feedback and call child.update().
    - Update shared state (best solution, per-strategy metrics) for communication.
    """
    context_requires = ("generation",)
    context_provides = (
        KEY_SHARED,
        KEY_STRATEGY,
        KEY_STRATEGY_ID,
        KEY_ROLE,
        KEY_ROLE_INDEX,
        KEY_ROLE_ADAPTER,
        KEY_TASK,
        KEY_PHASE,
        KEY_REGION_ID,
        KEY_REGION_BOUNDS,
        KEY_SEEDS,
        KEY_ROLE_REPORTS,
        KEY_CANDIDATE_ROLES,
        KEY_CANDIDATE_UNITS,
        KEY_UNIT_TASKS,
    )
    context_mutates = (KEY_SHARED, KEY_ROLE_REPORTS, KEY_CANDIDATE_ROLES, KEY_CANDIDATE_UNITS, KEY_UNIT_TASKS)
    context_cache = ()
    context_notes = (
        "Orchestrates multi-strategy/multi-role cooperation and injects strategy task context.",
        "Shared state is updated every step and exposed via runtime context projection.",
    )

    def __init__(
        self,
        strategies: Optional[Sequence[StrategySpec]] = None,
        *,
        roles: Optional[Sequence[RoleSpec]] = None,
        config: Optional[MultiStrategyConfig] = None,
        name: str = "multi_strategy_controller",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or MultiStrategyConfig()
        self.strategies: List[StrategySpec] = list(strategies or [])
        self.roles: List[RoleSpec] = list(roles or [])
        self.units: List[UnitSpec] = []
        self._step = 0

        # Per-strategy bookkeeping
        self._best_score: Dict[str, float] = {}
        self._ema_score: Dict[str, float] = {}
        self._last_improve_step: Dict[str, int] = {}
        # allocations are per unit: (role, unit_id, start, end)
        self._last_allocations: List[Tuple[str, int, int, int]] = []

        # Shared state broadcast to children (also mirrored to solver.*)
        self.shared_state: Dict[str, Any] = {}

        # Unit-level reports (exposed via runtime context projection).
        self.unit_reports: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self._unit_tasks: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self._last_task_projection: Dict[str, Any] = {}
        self._last_projection_writers: Dict[str, str] = {}
        self._runtime_shared_projection: Dict[str, Any] = {}
        self._runtime_meta_projection: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

        self._current_phase_name: str = "explore"
        self._phase_step: int = 0

        self._regions: List[Dict[str, Any]] = []
        self._unit_region: Dict[Tuple[str, int], int] = {}

        if self.roles and self.strategies:
            raise ValueError("MultiStrategyControllerAdapter: provide either strategies=... or roles=..., not both.")

    def setup(self, solver: Any) -> None:
        self._rng = self.create_local_rng(solver)
        self._step = 0
        self._best_score.clear()
        self._ema_score.clear()
        self._last_improve_step.clear()
        self._last_allocations.clear()
        self.unit_reports.clear()
        self._unit_tasks.clear()
        self._last_task_projection = {}
        self._last_projection_writers = {}
        self._runtime_shared_projection = {}
        self._runtime_meta_projection = {}
        self._unit_region.clear()
        self._regions = []
        self._current_phase_name = self._phase_for_step(0)[0]
        self._phase_step = 0
        self.units = self._build_units()

        # keep the shared schema stable
        self.shared_state = {
            "best_x": None,
            "best_score": None,
            "strategies": {},
            "units": {},
            "phase": self._current_phase_name,
            "regions": [],
        }

        for unit in self.units:
            unit.adapter.setup(solver)

    def teardown(self, solver: Any) -> None:
        for unit in self.units:
            unit.adapter.teardown(solver)

    def _build_units(self) -> List[UnitSpec]:
        # StrategySpec mode
        if self.strategies:
            out: List[UnitSpec] = []
            for idx, spec in enumerate(self.strategies):
                out.append(UnitSpec(role=str(spec.name), unit_id=int(idx), adapter=spec.adapter, enabled=spec.enabled))
            return out

        # RoleSpec mode
        out = []
        for role in self.roles:
            n = int(max(1, int(role.n_units)))
            for uid in range(n):
                adapter = self._instantiate_role_adapter(role.adapter, uid)
                out.append(UnitSpec(role=str(role.name), unit_id=int(uid), adapter=adapter, enabled=role.enabled))
        return out

    def _instantiate_role_adapter(
        self,
        adapter: Union[AlgorithmAdapter, Callable[[int], AlgorithmAdapter], Callable[[], AlgorithmAdapter]],
        unit_id: int,
    ) -> AlgorithmAdapter:
        if isinstance(adapter, AlgorithmAdapter):
            # best-effort: share adapter instance only when n_units==1
            if int(unit_id) == 0:
                return adapter
            raise ValueError(
                "RoleSpec.adapter is an instance, but n_units>1. Provide a factory callable so each unit gets "
                "its own adapter state."
            )
        # factory callable
        try:
            return adapter(int(unit_id))  # type: ignore[misc]
        except TypeError:
            return adapter()  # type: ignore[misc]

    def _score(self, objectives_row: np.ndarray, violation: float) -> float:
        if self.cfg.objective_aggregation == "first":
            obj = float(objectives_row[0])
        else:
            obj = float(np.sum(objectives_row))
        return float(violation) * float(self.cfg.violation_penalty) + obj

    def _role_specs(self) -> List[Tuple[str, float, bool]]:
        # unify to role-level weights
        if self.strategies:
            return [(s.name, float(s.weight), bool(s.enabled)) for s in self.strategies]
        return [(r.name, float(r.weight), bool(r.enabled)) for r in self.roles]

    def _phase_for_step(self, step: int) -> Tuple[str, int]:
        # returns (phase_name, phase_step)
        cursor = 0
        for name, span in tuple(self.cfg.phase_schedule):
            span = int(span)
            if span < 0:
                return str(name), int(step - cursor)
            if step < cursor + span:
                return str(name), int(step - cursor)
            cursor += span
        # fallback to last
        if self.cfg.phase_schedule:
            last = str(self.cfg.phase_schedule[-1][0])
            return last, int(step - cursor)
        return "default", int(step)

    def _enabled_roles_for_phase(self, phase: str) -> Optional[set[str]]:
        if not isinstance(self.cfg.phase_roles, dict):
            return None
        roles = self.cfg.phase_roles.get(str(phase))
        if not roles:
            return set()
        return {str(r) for r in roles}

    def _effective_weight(self, role: str, base_weight: float, phase: str) -> float:
        w = float(base_weight)
        if isinstance(self.cfg.phase_weight_multipliers, dict):
            mult = self.cfg.phase_weight_multipliers.get(str(phase), {}).get(str(role))
            if mult is not None:
                w *= float(mult)
        return w

    def _allocate_role_budgets(self) -> Dict[str, int]:
        phase = self._current_phase_name
        allowed = self._enabled_roles_for_phase(phase)
        enabled = []
        for (name, w, en) in self._role_specs():
            if not en:
                continue
            if allowed is not None and name not in allowed:
                continue
            w_eff = self._effective_weight(name, float(w), phase)
            if w_eff <= 0:
                continue
            enabled.append((name, w_eff))
        if not enabled:
            return {}

        weights = np.asarray([max(float(w), 0.0) for (_, w) in enabled], dtype=float)
        total = int(max(1, int(self.cfg.total_batch_size)))
        probs = weights / max(1e-12, float(np.sum(weights)))

        raw = probs * float(total)
        budgets = np.floor(raw).astype(int)
        remain = total - int(np.sum(budgets))
        if remain > 0:
            frac = raw - budgets
            order = list(np.argsort(-frac))
            for idx in order[:remain]:
                budgets[idx] += 1

        out = {enabled[i][0]: int(max(0, budgets[i])) for i in range(len(enabled))}
        # ensure at least 1 for each enabled role when total allows
        if total >= len(enabled):
            for name, _w in enabled:
                if out.get(name, 0) == 0:
                    out[name] = 1
        return out

    def _split_to_units(self, role_budgets: Dict[str, int]) -> Dict[Tuple[str, int], int]:
        # role -> unit_ids
        role_to_units: Dict[str, List[int]] = {}
        for unit in self.units:
            if not unit.enabled:
                continue
            role_to_units.setdefault(unit.role, []).append(int(unit.unit_id))

        out: Dict[Tuple[str, int], int] = {}
        for role, k in role_budgets.items():
            uids = role_to_units.get(role, [])
            if not uids:
                continue
            k = int(max(0, int(k)))
            base = k // len(uids)
            rem = k - base * len(uids)
            for i, uid in enumerate(uids):
                out[(role, uid)] = int(base + (1 if i < rem else 0))
        return out

    def _maybe_refresh_regions(self, solver: Any) -> None:
        if not self.cfg.enable_regions:
            self._regions = []
            return
        interval = int(max(0, int(self.cfg.region_update_interval)))
        if self._regions and interval > 0 and (int(self._step) % interval) != 0:
            return
        self._regions = self._default_region_partition(solver, int(max(1, int(self.cfg.n_regions))))

    def _default_region_partition(self, solver: Any, n_regions: int) -> List[Dict[str, Any]]:
        # Minimal, representation-agnostic default:
        # - If problem bounds are available, split along the first variable into N intervals (+ overlap).
        # - Otherwise return N empty region descriptors (still usable as tags/ids).
        problem = getattr(solver, "problem", None)
        bounds = getattr(problem, "bounds", None)
        if not isinstance(bounds, dict) or not bounds:
            return [{"id": i, "bounds": None} for i in range(int(n_regions))]

        keys = list(bounds.keys())
        lows = []
        highs = []
        for k in keys:
            lo_hi = bounds.get(k)
            if lo_hi is None or len(lo_hi) < 2:
                return [{"id": i, "bounds": None} for i in range(int(n_regions))]
            lows.append(float(lo_hi[0]))
            highs.append(float(lo_hi[1]))
        low = np.asarray(lows, dtype=float)
        high = np.asarray(highs, dtype=float)

        axis = 0
        lo = float(low[axis])
        hi = float(high[axis])
        span = float(hi - lo) if hi > lo else 1.0
        step = span / float(max(1, int(n_regions)))
        overlap = float(max(0.0, min(0.49, float(self.cfg.region_overlap))))
        pad = step * overlap

        regions = []
        for i in range(int(n_regions)):
            r_low = low.copy()
            r_high = high.copy()
            a0 = lo + step * float(i) - pad
            a1 = lo + step * float(i + 1) + pad
            r_low[axis] = max(lo, a0)
            r_high[axis] = min(hi, a1)
            regions.append({"id": i, "bounds": np.stack([r_low, r_high], axis=1), "split_axis": axis})
        return regions

    def _assign_regions_to_units(self) -> None:
        self._unit_region.clear()
        if not self._regions:
            return
        # round-robin assignment within each role
        by_role: Dict[str, List[Tuple[str, int]]] = {}
        for unit in self.units:
            if unit.enabled:
                by_role.setdefault(unit.role, []).append((unit.role, int(unit.unit_id)))
        for role, unit_keys in by_role.items():
            for i, key in enumerate(unit_keys):
                self._unit_region[key] = int(i % len(self._regions))

    def _select_seeds(self, solver: Any, k: int) -> List[np.ndarray]:
        k = int(max(0, int(k)))
        if k <= 0:
            return []
        if str(self.cfg.seeds_source) == "pareto":
            X = getattr(solver, "pareto_solutions", None)
            if X is not None:
                X = np.asarray(X)
                if X.ndim == 1:
                    X = X.reshape(1, -1)
                if X.size > 0:
                    idx = self._rng.choice(X.shape[0], size=min(k, X.shape[0]), replace=False)
                    return [np.asarray(X[i]) for i in idx]
        best = self.shared_state.get("best_x")
        if best is None:
            return []
        return [np.asarray(best) for _ in range(int(k))]

    def _broadcast_state(self, solver: Any) -> None:
        _ = solver
        self._runtime_shared_projection = {
            KEY_SHARED: self.shared_state,
            KEY_ROLE_REPORTS: self.shared_state.get(KEY_ROLE_REPORTS),
            KEY_PHASE: self.shared_state.get(KEY_PHASE),
        }

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        # phase bookkeeping
        phase, phase_step = self._phase_for_step(int(self._step))
        self._current_phase_name = str(phase)
        self._phase_step = int(phase_step)

        self._maybe_refresh_regions(solver)
        self._assign_regions_to_units()

        role_budgets = self._allocate_role_budgets()
        unit_budgets = self._split_to_units(role_budgets)
        if not unit_budgets:
            return []

        # Shared context visible to all strategies
        shared = {
            "best_x": self.shared_state.get("best_x"),
            "best_score": self.shared_state.get("best_score"),
            "strategy_stats": self.shared_state.get("strategies", {}),
            "step": int(self._step),
            "phase": self._current_phase_name,
            "phase_step": int(self._phase_step),
        }

        candidates: List[np.ndarray] = []
        allocations: List[Tuple[str, int, int, int]] = []
        cursor = 0

        # Build a stable role index mapping for this step
        role_names = sorted({u.role for u in self.units})
        role_index = {name: i for i, name in enumerate(role_names)}

        self._unit_tasks = {}
        for sid, unit in enumerate(self.units):
            if not unit.enabled:
                continue
            k = int(unit_budgets.get((unit.role, int(unit.unit_id)), 0))
            if k <= 0:
                continue

            ctx = dict(context)
            ctx[KEY_SHARED] = shared
            # Strategy keys (strategy == role)
            ctx[KEY_STRATEGY] = unit.role
            ctx[KEY_STRATEGY_ID] = int(sid)
            # Role keys
            ctx[KEY_ROLE] = unit.role
            ctx[KEY_ROLE_INDEX] = int(role_index.get(unit.role, 0))
            ctx[KEY_ROLE_ADAPTER] = getattr(unit.adapter, "name", f"{unit.role}:{unit.unit_id}")
            region_id = self._unit_region.get((unit.role, int(unit.unit_id)))
            region_bounds = None
            if region_id is not None and 0 <= int(region_id) < len(self._regions):
                region_bounds = self._regions[int(region_id)].get("bounds")

            seeds = []
            if self._current_phase_name != "explore":
                seeds = self._select_seeds(solver, int(self.cfg.seeds_per_task))

            task = {
                "budget": int(k),
                "unit_id": int(unit.unit_id),
                "role": unit.role,
                "step": int(self._step),
                "phase": self._current_phase_name,
                "phase_step": int(self._phase_step),
                "region_id": None if region_id is None else int(region_id),
                "region_bounds": region_bounds,
                "seeds": seeds,
            }
            ctx[KEY_PHASE] = self._current_phase_name
            ctx[KEY_REGION_ID] = task["region_id"]
            ctx[KEY_REGION_BOUNDS] = region_bounds
            ctx[KEY_SEEDS] = seeds
            ctx[KEY_TASK] = task
            self._unit_tasks[(unit.role, int(unit.unit_id))] = dict(task)
            self._last_task_projection = {
                KEY_ROLE: unit.role,
                KEY_ROLE_INDEX: int(role_index.get(unit.role, 0)),
                KEY_ROLE_ADAPTER: getattr(unit.adapter, "name", f"{unit.role}:{unit.unit_id}"),
                KEY_STRATEGY: unit.role,
                KEY_STRATEGY_ID: int(sid),
                KEY_PHASE: self._current_phase_name,
                KEY_REGION_ID: task["region_id"],
                KEY_REGION_BOUNDS: region_bounds,
                KEY_SEEDS: seeds,
                KEY_TASK: dict(task),
            }

            proposed = self.coerce_candidates(unit.adapter.propose(solver, ctx))
            if not proposed:
                continue

            # budget is a hint; strategies may return more/less
            start = cursor
            for cand in proposed[:k]:
                candidates.append(np.asarray(cand))
                cursor += 1
            end = cursor
            allocations.append((unit.role, int(unit.unit_id), start, end))

        self._last_allocations = allocations
        self._runtime_meta_projection = {
            KEY_CANDIDATE_ROLES: [r for (r, _uid, s, e) in allocations for _ in range(e - s)],
            KEY_CANDIDATE_UNITS: [int(uid) for (_r, uid, s, e) in allocations for _ in range(e - s)],
            KEY_UNIT_TASKS: dict(self._unit_tasks),
        }
        self._broadcast_state(solver)
        return candidates

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        # Update per-strategy + global best
        global_best_score = self.shared_state.get("best_score")
        global_best_x = self.shared_state.get("best_x")

        if candidates is None or len(candidates) == 0:
            self._step += 1
            return

        # compute scalar scores for each candidate
        scores = []
        for i in range(len(candidates)):
            vio = float(violations[i]) if violations is not None else 0.0
            scores.append(self._score(objectives[i], vio))
        scores_arr = np.asarray(scores, dtype=float)

        best_idx = int(np.argmin(scores_arr))
        best_score = float(scores_arr[best_idx])
        if global_best_score is None or best_score < float(global_best_score):
            global_best_score = float(best_score)
            global_best_x = np.asarray(candidates[best_idx])

        # split feedback to each unit
        by_key = {(u.role, int(u.unit_id)): u for u in self.units}
        for role, unit_id, start, end in list(self._last_allocations):
            unit = by_key.get((role, int(unit_id)))
            if unit is None:
                continue
            sub_cands = candidates[start:end]
            sub_obj = objectives[start:end]
            sub_vio = violations[start:end]

            sub_best = float(np.min(scores_arr[start:end])) if end > start else math.inf
            prev = self._best_score.get(role)
            improved = prev is None or sub_best < float(prev)
            if improved:
                self._best_score[role] = float(sub_best)
                self._last_improve_step[role] = int(self._step)

            ema = self._ema_score.get(role)
            if ema is None:
                self._ema_score[role] = float(sub_best)
            else:
                a = float(self.cfg.adapt_momentum)
                self._ema_score[role] = float((1.0 - a) * float(ema) + a * float(sub_best))

            # role/unit-scoped context for update
            ctx = dict(context)
            ctx[KEY_SHARED] = {
                "best_x": global_best_x,
                "best_score": global_best_score,
                "strategy_stats": self.shared_state.get("strategies", {}),
                "step": int(self._step),
            }
            ctx[KEY_STRATEGY] = role
            ctx[KEY_ROLE] = role
            ctx[KEY_STRATEGY_ID] = int(unit_id)
            ctx[KEY_TASK] = {"unit_id": int(unit_id), "role": role, "step": int(self._step)}

            unit.adapter.update(solver, sub_cands, sub_obj, sub_vio, ctx)
            self._record_unit_report(role, int(unit_id), sub_cands, sub_obj, sub_vio, scores_arr[start:end])

        # decision: adapt strategy weights
        if self.cfg.adapt_weights:
            self._adapt_weights()

        # update shared state
        self.shared_state["best_x"] = global_best_x
        self.shared_state["best_score"] = global_best_score
        self.shared_state["strategies"] = self._build_strategy_stats()
        self.shared_state["units"] = self._build_unit_stats()
        self.shared_state[KEY_ROLE_REPORTS] = self._collect_role_reports(solver)
        self.shared_state["phase"] = self._current_phase_name
        self.shared_state["regions"] = self._build_region_stats()
        self._broadcast_state(solver)

        self._step += 1

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        out: Dict[str, Any] = {}
        writers: Dict[str, str] = {}
        self_source = f"adapter.{self.__class__.__name__}"
        for key, value in self._runtime_shared_projection.items():
            if value is None:
                continue
            out[str(key)] = value
            writers[str(key)] = self_source

        for key, value in self._last_task_projection.items():
            if value is None:
                continue
            out[key] = value
            writers[str(key)] = self_source
        for key, value in self._runtime_meta_projection.items():
            if value is None:
                continue
            out[str(key)] = value
            writers[str(key)] = self_source

        # Pull child adapter projection to make role-local runtime fields visible
        # in global context snapshots (e.g., moead_* / vns_*).
        for unit in self.units:
            adapter = getattr(unit, "adapter", None)
            if adapter is None:
                continue
            unit_source = f"adapter.unit.{unit.role}#{int(unit.unit_id)}:{adapter.__class__.__name__}"
            getter = getattr(adapter, "get_runtime_context_projection", None)
            if not callable(getter):
                continue
            try:
                proj = getter(solver)
            except Exception:
                proj = None
            if not isinstance(proj, dict):
                continue
            for key, value in proj.items():
                if key is None or value is None:
                    continue
                key_str = str(key)
                if key_str not in out:
                    out[key_str] = value
                    writers[key_str] = unit_source
        self._last_projection_writers = writers
        return out

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        return dict(self._last_projection_writers)

    def _record_unit_report(
        self,
        role: str,
        unit_id: int,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        scores: np.ndarray,
    ) -> None:
        if candidates is None or len(candidates) == 0:
            self.unit_reports[(role, unit_id)] = {
                "role": role,
                "unit_id": int(unit_id),
                "n_candidates": 0,
                "best_score": None,
            }
            return
        best_idx = int(np.argmin(scores))
        best_score = float(scores[best_idx])
        self.unit_reports[(role, unit_id)] = {
            "role": role,
            "unit_id": int(unit_id),
            "n_candidates": int(len(candidates)),
            "best_score": best_score,
        }

    def _collect_role_reports(self, solver: Any) -> Dict[str, Any]:
        # Prefer RoleAdapter reports if present (more informative).
        reports = getattr(solver, "role_reports", None)
        if isinstance(reports, dict):
            return reports
        # Otherwise summarize from unit reports.
        out: Dict[str, Any] = {}
        for (role, _uid), rep in self.unit_reports.items():
            cur = out.get(role)
            if cur is None:
                out[role] = dict(rep)
                continue
            # keep best_score min
            if rep.get("best_score") is None:
                continue
            if cur.get("best_score") is None or float(rep["best_score"]) < float(cur["best_score"]):
                out[role] = dict(rep)
        return out

    def _build_strategy_stats(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.strategies:
            items = [(s.name, s.weight, s.enabled) for s in self.strategies]
        else:
            items = [(r.name, r.weight, r.enabled) for r in self.roles]

        for name, weight, enabled in items:
            out[name] = {
                "weight": float(weight),
                "enabled": bool(enabled),
                "best_score": self._best_score.get(name),
                "ema_score": self._ema_score.get(name),
                "last_improve_step": self._last_improve_step.get(name),
            }
        return out

    def _build_unit_stats(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for unit in self.units:
            key = f"{unit.role}#{unit.unit_id}"
            rep = self.unit_reports.get((unit.role, int(unit.unit_id)), {})
            out[key] = {
                "role": unit.role,
                "unit_id": int(unit.unit_id),
                "enabled": bool(unit.enabled),
                "last_report": rep,
            }
        return out

    def _build_region_stats(self) -> List[Dict[str, Any]]:
        if not self._regions:
            return []
        # Aggregate unit reports by region_id
        by_region: Dict[int, List[Dict[str, Any]]] = {}
        for (role, uid), rep in self.unit_reports.items():
            rid = self._unit_region.get((role, int(uid)))
            if rid is None:
                continue
            by_region.setdefault(int(rid), []).append(rep)

        out = []
        for reg in self._regions:
            rid = int(reg.get("id", -1))
            reps = by_region.get(rid, [])
            best = None
            for r in reps:
                sc = r.get("best_score")
                if sc is None:
                    continue
                if best is None or float(sc) < float(best):
                    best = float(sc)
            out.append(
                {
                    "id": rid,
                    "bounds": reg.get("bounds"),
                    "split_axis": reg.get("split_axis"),
                    "n_unit_reports": int(len(reps)),
                    "best_score": best,
                }
            )
        return out

    def _adapt_weights(self) -> None:
        # Simple heuristic:
        # - If a strategy hasn't improved for stagnation_window steps, boost its weight a bit
        #   (exploration escape hatch).
        # - Otherwise, softly prefer lower EMA score (better).
        scores = []
        names = []
        if self.strategies:
            enabled_specs = [(s.name, s.enabled) for s in self.strategies]
        else:
            enabled_specs = [(r.name, r.enabled) for r in self.roles]

        for name, en in enabled_specs:
            if not en:
                continue
            ema = self._ema_score.get(name)
            if ema is None:
                continue
            scores.append(float(ema))
            names.append(name)
        if len(scores) == 0:
            return

        scores_arr = np.asarray(scores, dtype=float)
        # convert "lower is better" to weights via inverse normalization
        s_min = float(np.min(scores_arr))
        scaled = 1.0 / (1e-9 + (scores_arr - s_min + 1.0))
        scaled = scaled / max(1e-12, float(np.sum(scaled)))

        base = {names[i]: float(scaled[i]) for i in range(len(names))}
        if self.strategies:
            specs: List[Any] = list(self.strategies)
        else:
            specs = list(self.roles)

        for spec in specs:
            if not spec.enabled:
                continue
            w = float(base.get(spec.name, 0.0))
            last = self._last_improve_step.get(spec.name, 0)
            stagnant = (int(self._step) - int(last)) >= int(self.cfg.stagnation_window)
            if stagnant:
                w = w * (1.0 + float(self.cfg.stagnation_boost))
            spec.weight = float(min(self.cfg.max_weight, max(self.cfg.min_weight, w)))

    def get_context_contract(self) -> Dict[str, Any]:
        contract = super().get_context_contract()
        requires = list(contract.get("requires", ()) or ())
        provides = list(contract.get("provides", ()) or ())
        mutates = list(contract.get("mutates", ()) or ())
        cache = list(contract.get("cache", ()) or ())

        for spec in self.strategies:
            sub = spec.adapter.get_context_contract() if spec.adapter is not None else {}
            requires.extend(list(sub.get("requires", ()) or ()))
            provides.extend(list(sub.get("provides", ()) or ()))
            mutates.extend(list(sub.get("mutates", ()) or ()))
            cache.extend(list(sub.get("cache", ()) or ()))

        for role in self.roles:
            role_adapter = getattr(role, "adapter", None)
            if isinstance(role_adapter, AlgorithmAdapter):
                sub = role_adapter.get_context_contract()
                requires.extend(list(sub.get("requires", ()) or ()))
                provides.extend(list(sub.get("provides", ()) or ()))
                mutates.extend(list(sub.get("mutates", ()) or ()))
                cache.extend(list(sub.get("cache", ()) or ()))

        return {
            "requires": requires,
            "provides": provides,
            "mutates": mutates,
            "cache": cache,
            "notes": contract.get("notes"),
        }
