"""Companion problem orchestration plugin (level-set mode).

This plugin adds a blocking companion phase that can be triggered multiple
times during a run. It keeps existing problem/adapter/pipeline semantics and
only changes acceptance and selection policy inside the companion phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..base import Plugin
from ...utils.context.context_keys import (
    KEY_COMPANION_NEXT_ELIGIBLE_GENERATION,
    KEY_COMPANION_PHASE_COUNT_USED,
    KEY_COMPANION_PHASE_INDEX,
    KEY_COMPANION_TRIGGER_REASON,
)
from ...utils.context.snapshot_store import make_snapshot_key


@dataclass
class CompanionEventRules:
    enable_stagnation: bool = True
    stagnation_window: int = 10
    improvement_epsilon: float = 1e-6
    enable_diversity_drop: bool = True
    diversity_threshold: Optional[float] = None


@dataclass
class CompanionOrchestratorConfig:
    trigger_mode: str = "mixed"  # "periodic" | "event" | "mixed"
    period_generations: int = 20
    phase_min_generation: int = 30
    phase_max_count: int = 3
    phase_cooldown_generations: int = 15
    phase_blocking: bool = True

    # companion phase execution
    per_task_budget: int = 5
    global_budget: int = 200
    levelset_eps: float = 1e-3
    accept_metric: str = "linf"  # "linf" | "l2" | "weighted"
    weighted_accept_weights: Optional[Sequence[float]] = None
    include_infeasible_anchors: bool = False

    # injection
    max_accepted_per_task: int = 4
    max_injected_per_phase: int = 64

    # storage
    store_prefix: str = "companion"
    event_rules: CompanionEventRules = field(default_factory=CompanionEventRules)


@dataclass
class CompanionTask:
    task_id: str
    anchor_id: str
    target_f: np.ndarray
    budget_max: int
    budget_used: int = 0
    accepted_x: List[np.ndarray] = field(default_factory=list)
    accepted_f: List[np.ndarray] = field(default_factory=list)
    accepted_v: List[float] = field(default_factory=list)
    accepted_d: List[float] = field(default_factory=list)
    status: str = "pending"
    snapshot_key: Optional[str] = None


@dataclass
class CompanionPhaseRun:
    phase_index: int
    trigger_reason: str
    generation: int
    cooldown_applied: bool
    return_generation: int
    anchor_count_m: int
    global_budget: int
    global_budget_used: int
    success_count: int
    task_count: int
    injected_count: int
    phase_snapshot_key: Optional[str]


class CompanionPhaseScheduler:
    """Decides if a companion phase should be triggered."""

    def __init__(self, config: CompanionOrchestratorConfig) -> None:
        self.cfg = config

    def should_trigger(
        self,
        *,
        generation: int,
        phase_count_used: int,
        last_return_generation: Optional[int],
        event_due: bool,
    ) -> Tuple[bool, str, bool]:
        if phase_count_used >= int(self.cfg.phase_max_count):
            return False, "none", False
        if int(generation) < int(self.cfg.phase_min_generation):
            return False, "none", False

        cooldown_applied = False
        last = None if last_return_generation is None else int(last_return_generation)
        cooldown = max(0, int(self.cfg.phase_cooldown_generations))
        if last is not None and int(generation) < (last + cooldown):
            return False, "none", True

        mode = str(self.cfg.trigger_mode or "mixed").strip().lower()
        period = max(1, int(self.cfg.period_generations))
        periodic_due = ((int(generation) - int(self.cfg.phase_min_generation)) % period) == 0

        if mode == "periodic":
            return bool(periodic_due), "periodic", cooldown_applied
        if mode == "event":
            return bool(event_due), "event", cooldown_applied
        # mixed mode: event has priority
        if bool(event_due):
            return True, "event", cooldown_applied
        if bool(periodic_due):
            return True, "periodic", cooldown_applied
        return False, "none", cooldown_applied


class CompanionOrchestratorPlugin(Plugin):
    """Multi-phase level-set companion problem orchestrator."""

    is_algorithmic = True
    context_requires = ()
    context_provides = (
        KEY_COMPANION_PHASE_INDEX,
        KEY_COMPANION_TRIGGER_REASON,
        KEY_COMPANION_NEXT_ELIGIBLE_GENERATION,
        KEY_COMPANION_PHASE_COUNT_USED,
    )
    context_mutates = (
        KEY_COMPANION_PHASE_INDEX,
        KEY_COMPANION_TRIGGER_REASON,
        KEY_COMPANION_NEXT_ELIGIBLE_GENERATION,
        KEY_COMPANION_PHASE_COUNT_USED,
    )
    context_cache = ()
    context_notes = (
        "Blocking companion phase scheduler. Supports mixed periodic/event triggers, "
        "cooldown/max-count governance, append-only phase/task records, and phase-end injection."
    )

    def __init__(
        self,
        name: str = "companion_orchestrator",
        *,
        config: Optional[CompanionOrchestratorConfig] = None,
    ) -> None:
        super().__init__(name=name)
        self.cfg = config or CompanionOrchestratorConfig()
        self.scheduler = CompanionPhaseScheduler(self.cfg)

        self.phase_count_used: int = 0
        self.next_eligible_generation: int = int(self.cfg.phase_min_generation)
        self.last_return_generation: Optional[int] = None
        self.last_trigger_reason: str = ""

        self.phase_runs: List[CompanionPhaseRun] = []
        self.lineage_index: Dict[str, List[Dict[str, Any]]] = {}

        self._best_score: Optional[float] = None
        self._stagnation_count: int = 0

    def on_solver_init(self, solver) -> None:
        self.phase_count_used = 0
        self.next_eligible_generation = int(self.cfg.phase_min_generation)
        self.last_return_generation = None
        self.last_trigger_reason = ""
        self.phase_runs = []
        self.lineage_index = {}
        self._best_score = None
        self._stagnation_count = 0
        self._sync_runtime_state(solver)

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context[KEY_COMPANION_PHASE_INDEX] = int(self.phase_count_used)
        context[KEY_COMPANION_TRIGGER_REASON] = str(self.last_trigger_reason or "")
        context[KEY_COMPANION_NEXT_ELIGIBLE_GENERATION] = int(self.next_eligible_generation)
        context[KEY_COMPANION_PHASE_COUNT_USED] = int(self.phase_count_used)
        return context

    def on_generation_end(self, generation: int) -> None:
        solver = self.solver
        if solver is None or not bool(self.cfg.phase_blocking):
            return None

        pop, obj, vio = self.resolve_population_snapshot(solver)
        event_due = False
        event_reason = "none"
        if obj.size > 0:
            event_due, event_reason = self._check_event_trigger(obj, vio)

        should_trigger, trigger_reason, cooldown_applied = self.scheduler.should_trigger(
            generation=int(generation),
            phase_count_used=int(self.phase_count_used),
            last_return_generation=self.last_return_generation,
            event_due=bool(event_due),
        )
        if not should_trigger:
            if cooldown_applied and self.last_return_generation is not None:
                self.next_eligible_generation = int(self.last_return_generation) + int(self.cfg.phase_cooldown_generations)
            self._sync_runtime_state(solver)
            return None

        if trigger_reason == "event" and event_reason != "none":
            trigger_reason = event_reason
        self.last_trigger_reason = str(trigger_reason)
        phase_index = int(self.phase_count_used) + 1
        phase_run = self._execute_phase(
            solver=solver,
            generation=int(generation),
            phase_index=phase_index,
            trigger_reason=str(trigger_reason),
            cooldown_applied=bool(cooldown_applied),
        )
        self.phase_runs.append(phase_run)
        self.phase_count_used = int(phase_index)
        self.last_return_generation = int(generation)
        self.next_eligible_generation = int(generation) + int(self.cfg.phase_cooldown_generations)
        self._persist_phase_summary(solver, phase_run)
        self._sync_runtime_state(solver)
        return None

    def get_report(self) -> Optional[Dict[str, Any]]:
        out = super().get_report() or {}
        out.update(
            {
                "phase_count_used": int(self.phase_count_used),
                "next_eligible_generation": int(self.next_eligible_generation),
                "last_trigger_reason": str(self.last_trigger_reason or ""),
                "phase_runs": [
                    {
                        "phase_index": int(p.phase_index),
                        "trigger_reason": str(p.trigger_reason),
                        "generation": int(p.generation),
                        "return_generation": int(p.return_generation),
                        "anchor_count_m": int(p.anchor_count_m),
                        "task_count": int(p.task_count),
                        "success_count": int(p.success_count),
                        "injected_count": int(p.injected_count),
                    }
                    for p in self.phase_runs
                ],
            }
        )
        return out

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _sync_runtime_state(self, solver: Any) -> None:
        setattr(solver, "companion_phase_count_used", int(self.phase_count_used))
        setattr(solver, "companion_next_eligible_generation", int(self.next_eligible_generation))
        setattr(solver, "companion_last_trigger_reason", str(self.last_trigger_reason or ""))

    def _score_population(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1) if obj.size > 0 else obj.reshape(0, 0)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if obj.shape[0] == 0:
            return np.zeros((0,), dtype=float)
        penalty = np.maximum(vio, 0.0) * 1e6
        return np.sum(obj, axis=1) + penalty

    def _check_event_trigger(self, objectives: np.ndarray, violations: np.ndarray) -> Tuple[bool, str]:
        cfg = self.cfg.event_rules
        scores = self._score_population(objectives, violations)
        if scores.size == 0:
            return False, "none"
        best_now = float(np.min(scores))
        if self._best_score is None or (float(self._best_score) - best_now) > float(cfg.improvement_epsilon):
            self._best_score = best_now
            self._stagnation_count = 0
        else:
            self._stagnation_count += 1

        if bool(cfg.enable_stagnation) and self._stagnation_count >= int(max(1, cfg.stagnation_window)):
            return True, "event.stagnation"

        if bool(cfg.enable_diversity_drop) and cfg.diversity_threshold is not None:
            obj = np.asarray(objectives, dtype=float)
            if obj.ndim == 1:
                obj = obj.reshape(-1, 1) if obj.size > 0 else obj.reshape(0, 0)
            if obj.shape[0] > 1:
                div = float(np.mean(np.std(obj, axis=0)))
                if div <= float(cfg.diversity_threshold):
                    return True, "event.diversity"
        return False, "none"

    @staticmethod
    def _nondominated_mask(F: np.ndarray) -> np.ndarray:
        arr = np.asarray(F, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1) if arr.size > 0 else arr.reshape(0, 0)
        n = int(arr.shape[0])
        dominated = np.zeros((n,), dtype=bool)
        for i in range(n):
            if dominated[i]:
                continue
            fi = arr[i]
            for j in range(n):
                if i == j or dominated[i]:
                    continue
                fj = arr[j]
                if np.all(fj <= fi) and np.any(fj < fi):
                    dominated[i] = True
        return ~dominated

    @staticmethod
    def _anchor_id(x: np.ndarray, f: np.ndarray) -> str:
        hx = hashlib.sha1(np.asarray(x, dtype=float).tobytes()).hexdigest()[:12]
        hf = hashlib.sha1(np.asarray(f, dtype=float).tobytes()).hexdigest()[:12]
        return f"a_{hx}_{hf}"

    def _build_anchors(self, pop: np.ndarray, obj: np.ndarray, vio: np.ndarray) -> List[Dict[str, Any]]:
        X = np.asarray(pop, dtype=float)
        F = np.asarray(obj, dtype=float)
        V = np.asarray(vio, dtype=float).reshape(-1)
        if X.ndim == 1:
            X = X.reshape(1, -1) if X.size > 0 else X.reshape(0, 0)
        if F.ndim == 1:
            F = F.reshape(-1, 1) if F.size > 0 else F.reshape(0, 0)
        if X.shape[0] == 0 or F.shape[0] == 0:
            return []
        if not bool(self.cfg.include_infeasible_anchors):
            feas = V <= 0.0
            X = X[feas]
            F = F[feas]
            V = V[feas]
        if X.shape[0] == 0:
            return []
        nd = self._nondominated_mask(F)
        Xn = X[nd]
        Fn = F[nd]
        anchors: List[Dict[str, Any]] = []
        for i in range(int(Xn.shape[0])):
            ax = np.asarray(Xn[i], dtype=float).reshape(-1)
            af = np.asarray(Fn[i], dtype=float).reshape(-1)
            anchors.append(
                {
                    "anchor_id": self._anchor_id(ax, af),
                    "x": ax,
                    "f": af,
                }
            )
        return anchors

    def _distance(self, fx: np.ndarray, target: np.ndarray) -> float:
        diff = np.abs(np.asarray(fx, dtype=float).reshape(-1) - np.asarray(target, dtype=float).reshape(-1))
        metric = str(self.cfg.accept_metric or "linf").strip().lower()
        if metric == "l2":
            return float(np.linalg.norm(diff, ord=2))
        if metric == "weighted":
            w = self.cfg.weighted_accept_weights
            if w is None:
                return float(np.sum(diff))
            ww = np.asarray(w, dtype=float).reshape(-1)
            if ww.size < diff.size:
                ww = np.pad(ww, (0, diff.size - ww.size), mode="edge")
            elif ww.size > diff.size:
                ww = ww[: diff.size]
            return float(np.sum(ww * diff))
        return float(np.max(diff)) if diff.size > 0 else 0.0

    def _accept(self, fx: np.ndarray, target: np.ndarray) -> Tuple[bool, float]:
        d = self._distance(fx, target)
        return bool(d <= float(self.cfg.levelset_eps)), float(d)

    def _coerce_candidates(self, value: Any) -> List[np.ndarray]:
        if value is None:
            return []
        if isinstance(value, np.ndarray):
            arr = np.asarray(value, dtype=float)
            if arr.ndim <= 1:
                return [arr.reshape(-1)]
            return [np.asarray(row, dtype=float).reshape(-1) for row in arr]
        out: List[np.ndarray] = []
        try:
            for item in value:
                out.append(np.asarray(item, dtype=float).reshape(-1))
        except Exception:
            return []
        return out

    def _pick_candidate(self, candidates: List[np.ndarray], *, rng: np.random.Generator) -> Optional[np.ndarray]:
        if not candidates:
            return None
        idx = int(rng.integers(0, len(candidates)))
        return np.asarray(candidates[idx], dtype=float).reshape(-1)

    def _task_attempt(
        self,
        *,
        solver: Any,
        task: CompanionTask,
        phase_index: int,
        task_index: int,
        rng: np.random.Generator,
    ) -> None:
        adapter = getattr(solver, "adapter", None)
        if adapter is None:
            task.status = "adapter_missing"
            task.budget_used += 1
            return None

        ctx = solver.build_context()
        ctx[KEY_COMPANION_PHASE_INDEX] = int(phase_index)
        ctx[KEY_COMPANION_TRIGGER_REASON] = str(self.last_trigger_reason or "")
        ctx[KEY_COMPANION_PHASE_COUNT_USED] = int(self.phase_count_used)

        proposed = self._coerce_candidates(adapter.propose(solver, ctx))
        candidate = self._pick_candidate(proposed, rng=rng)
        if candidate is None:
            fallback = getattr(solver, "_random_candidate", None)
            if callable(fallback):
                try:
                    candidate = np.asarray(fallback(), dtype=float).reshape(-1)
                except Exception:
                    candidate = None
        if candidate is None:
            task.status = "proposal_empty"
            task.budget_used += 1
            return None

        repair = getattr(solver, "repair_candidate", None)
        if callable(repair):
            try:
                candidate = np.asarray(repair(candidate, ctx), dtype=float).reshape(-1)
            except Exception:
                candidate = np.asarray(candidate, dtype=float).reshape(-1)

        pop = np.asarray(candidate, dtype=float).reshape(1, -1)
        obj, vio = solver.evaluate_population(pop)
        fx = np.asarray(obj[0], dtype=float).reshape(-1)
        vv = float(np.asarray(vio, dtype=float).reshape(-1)[0])

        adapter.update(
            solver,
            pop,
            np.asarray(obj, dtype=float),
            np.asarray(vio, dtype=float).reshape(-1),
            ctx,
        )

        accepted, dist = self._accept(fx, task.target_f)
        task.budget_used += 1
        if accepted:
            task.accepted_x.append(np.asarray(candidate, dtype=float).reshape(-1))
            task.accepted_f.append(np.asarray(fx, dtype=float).reshape(-1))
            task.accepted_v.append(float(vv))
            task.accepted_d.append(float(dist))
            task.status = "accepted"
            if len(task.accepted_x) >= int(self.cfg.max_accepted_per_task):
                task.status = "accepted_capped"
        elif task.status == "pending":
            task.status = "searching"

    def _persist_task_result(
        self,
        *,
        solver: Any,
        phase_index: int,
        generation: int,
        task: CompanionTask,
    ) -> Optional[str]:
        if not task.accepted_x:
            return None
        x = np.asarray(task.accepted_x, dtype=float)
        f = np.asarray(task.accepted_f, dtype=float)
        v = np.asarray(task.accepted_v, dtype=float).reshape(-1)
        d = np.asarray(task.accepted_d, dtype=float).reshape(-1)
        payload = {
            "companion_population": x,
            "companion_objectives": f,
            "companion_violations": v,
            "companion_distances": d,
            "anchor_id": str(task.anchor_id),
            "task_id": str(task.task_id),
            "phase_index": int(phase_index),
        }
        key = make_snapshot_key(
            prefix=str(self.cfg.store_prefix or "companion"),
            generation=int(generation),
            step=int(phase_index),
            suffix=f"task_{task.task_id}",
        )
        handle = solver.snapshot_store.write(
            payload,
            key=key,
            meta={
                "kind": "companion_task",
                "phase_index": int(phase_index),
                "task_id": str(task.task_id),
                "anchor_id": str(task.anchor_id),
                "accepted_count": int(x.shape[0]),
            },
            schema="companion_task_v1",
            ttl_seconds=getattr(solver, "snapshot_store_ttl_seconds", None),
        )
        return str(handle.key)

    def _inject_phase_candidates(
        self,
        *,
        solver: Any,
        base_x: np.ndarray,
        base_f: np.ndarray,
        base_v: np.ndarray,
        tasks: List[CompanionTask],
    ) -> Dict[str, Any]:
        selected: List[Tuple[float, np.ndarray, np.ndarray, float, str]] = []
        for task in tasks:
            if not task.accepted_x:
                continue
            order = np.argsort(np.asarray(task.accepted_d, dtype=float))
            best_idx = int(order[0])
            selected.append(
                (
                    float(task.accepted_d[best_idx]),
                    np.asarray(task.accepted_x[best_idx], dtype=float).reshape(-1),
                    np.asarray(task.accepted_f[best_idx], dtype=float).reshape(-1),
                    float(task.accepted_v[best_idx]),
                    str(task.task_id),
                )
            )
        selected.sort(key=lambda t: float(t[0]))
        cap = max(0, int(self.cfg.max_injected_per_phase))
        if cap > 0:
            selected = selected[:cap]
        if not selected:
            self.commit_population_snapshot(base_x, base_f, base_v, solver)
            return {"selected_count": 0, "task_ids": []}

        add_x = np.vstack([item[1] for item in selected]).astype(float, copy=False)
        add_f = np.vstack([item[2] for item in selected]).astype(float, copy=False)
        add_v = np.asarray([item[3] for item in selected], dtype=float).reshape(-1)

        if base_x.size == 0:
            new_x = add_x
            new_f = add_f
            new_v = add_v
        else:
            new_x = np.vstack([np.asarray(base_x, dtype=float), add_x])
            new_f = np.vstack([np.asarray(base_f, dtype=float), add_f])
            new_v = np.concatenate([np.asarray(base_v, dtype=float).reshape(-1), add_v])
        self.commit_population_snapshot(new_x, new_f, new_v, solver)

        return {
            "selected_count": int(len(selected)),
            "task_ids": [str(item[4]) for item in selected],
        }

    def _update_lineage(self, *, phase_index: int, anchors: List[Dict[str, Any]], tasks: List[CompanionTask]) -> None:
        task_by_anchor = {str(t.anchor_id): t for t in tasks}
        active_anchor_ids = {str(a["anchor_id"]) for a in anchors}
        for anchor_id, entries in self.lineage_index.items():
            if anchor_id in active_anchor_ids:
                continue
            for entry in entries:
                if str(entry.get("validity", "")) == "active":
                    entry["validity"] = "invalidated"
                    entry["invalidated_in_phase"] = int(phase_index)

        for anchor in anchors:
            anchor_id = str(anchor["anchor_id"])
            entry = {
                "phase_index": int(phase_index),
                "anchor_id": anchor_id,
                "target_f": np.asarray(anchor["f"], dtype=float).tolist(),
                "validity": "active",
                "status": str(task_by_anchor.get(anchor_id, CompanionTask("", "", np.zeros((0,)), 0)).status),
                "accepted_count": int(len(task_by_anchor.get(anchor_id, CompanionTask("", "", np.zeros((0,)), 0)).accepted_x)),
                "task_id": str(task_by_anchor.get(anchor_id, CompanionTask("", "", np.zeros((0,)), 0)).task_id),
                "task_snapshot_key": task_by_anchor.get(anchor_id, CompanionTask("", "", np.zeros((0,)), 0)).snapshot_key,
            }
            self.lineage_index.setdefault(anchor_id, []).append(entry)

    def _execute_phase(
        self,
        *,
        solver: Any,
        generation: int,
        phase_index: int,
        trigger_reason: str,
        cooldown_applied: bool,
    ) -> CompanionPhaseRun:
        base_x, base_f, base_v = self.resolve_population_snapshot(solver)
        anchors = self._build_anchors(base_x, base_f, base_v)
        tasks: List[CompanionTask] = []
        for i, anchor in enumerate(anchors):
            tasks.append(
                CompanionTask(
                    task_id=f"{phase_index}_{i}",
                    anchor_id=str(anchor["anchor_id"]),
                    target_f=np.asarray(anchor["f"], dtype=float).reshape(-1),
                    budget_max=max(1, int(self.cfg.per_task_budget)),
                )
            )

        rng = self.create_local_rng(solver=solver)
        global_budget = int(self.cfg.global_budget)
        if global_budget <= 0:
            global_budget = max(1, int(self.cfg.per_task_budget)) * max(1, len(tasks))
        global_budget_used = 0
        active = {int(i) for i in range(len(tasks))}
        while active and global_budget_used < global_budget:
            for idx in list(active):
                task = tasks[idx]
                if task.budget_used >= int(task.budget_max):
                    if task.status == "pending":
                        task.status = "exhausted"
                    active.discard(idx)
                    continue
                self._task_attempt(
                    solver=solver,
                    task=task,
                    phase_index=int(phase_index),
                    task_index=int(idx),
                    rng=rng,
                )
                global_budget_used += 1
                if task.budget_used >= int(task.budget_max):
                    if not task.accepted_x and task.status in {"pending", "searching"}:
                        task.status = "exhausted"
                    active.discard(idx)
                if global_budget_used >= global_budget:
                    break

        if global_budget_used >= global_budget:
            for idx in list(active):
                if tasks[idx].status in {"pending", "searching"}:
                    tasks[idx].status = "budget_exhausted"
                active.discard(idx)

        for task in tasks:
            task.snapshot_key = self._persist_task_result(
                solver=solver,
                phase_index=int(phase_index),
                generation=int(generation),
                task=task,
            )

        inject = self._inject_phase_candidates(
            solver=solver,
            base_x=base_x,
            base_f=base_f,
            base_v=base_v,
            tasks=tasks,
        )

        phase_payload = {
            "phase_index": int(phase_index),
            "trigger_reason": str(trigger_reason),
            "generation": int(generation),
            "task_refs": {str(t.task_id): str(t.snapshot_key or "") for t in tasks},
            "lineage_keys": list(self.lineage_index.keys()),
            "injected_task_ids": list(inject.get("task_ids", [])),
        }
        phase_key = make_snapshot_key(
            prefix=str(self.cfg.store_prefix or "companion"),
            generation=int(generation),
            step=int(phase_index),
            suffix="phase",
        )
        phase_handle = solver.snapshot_store.write(
            phase_payload,
            key=phase_key,
            meta={
                "kind": "companion_phase",
                "phase_index": int(phase_index),
                "generation": int(generation),
                "task_count": int(len(tasks)),
            },
            schema="companion_phase_v1",
            ttl_seconds=getattr(solver, "snapshot_store_ttl_seconds", None),
        )

        self._update_lineage(phase_index=int(phase_index), anchors=anchors, tasks=tasks)

        success_count = int(sum(1 for t in tasks if len(t.accepted_x) > 0))
        return CompanionPhaseRun(
            phase_index=int(phase_index),
            trigger_reason=str(trigger_reason),
            generation=int(generation),
            cooldown_applied=bool(cooldown_applied),
            return_generation=int(generation),
            anchor_count_m=int(len(anchors)),
            global_budget=int(global_budget),
            global_budget_used=int(global_budget_used),
            success_count=int(success_count),
            task_count=int(len(tasks)),
            injected_count=int(inject.get("selected_count", 0)),
            phase_snapshot_key=str(phase_handle.key),
        )

    def _persist_phase_summary(self, solver: Any, phase_run: CompanionPhaseRun) -> None:
        phase_key = f"{self.cfg.store_prefix}.phase.{int(phase_run.phase_index)}.summary"
        inj_key = f"{self.cfg.store_prefix}.phase.{int(phase_run.phase_index)}.injection"
        lin_key = f"{self.cfg.store_prefix}.phase.{int(phase_run.phase_index)}.lineage"

        summary = {
            "phase_index": int(phase_run.phase_index),
            "trigger_reason": str(phase_run.trigger_reason),
            "generation": int(phase_run.generation),
            "cooldown_applied": bool(phase_run.cooldown_applied),
            "return_generation": int(phase_run.return_generation),
            "anchor_count_m": int(phase_run.anchor_count_m),
            "task_count": int(phase_run.task_count),
            "success_count": int(phase_run.success_count),
            "global_budget": int(phase_run.global_budget),
            "global_budget_used": int(phase_run.global_budget_used),
            "injected_count": int(phase_run.injected_count),
            "phase_snapshot_key": str(phase_run.phase_snapshot_key or ""),
        }
        injection = {
            "phase_index": int(phase_run.phase_index),
            "injected_count": int(phase_run.injected_count),
            "phase_snapshot_key": str(phase_run.phase_snapshot_key or ""),
        }
        lineage = {
            "phase_index": int(phase_run.phase_index),
            "anchor_keys": list(self.lineage_index.keys()),
            "lineage_count": int(sum(len(v) for v in self.lineage_index.values())),
        }
        ttl = getattr(solver, "context_store_ttl_seconds", None)
        solver.context_store.set(str(phase_key), summary, ttl_seconds=ttl)
        solver.context_store.set(str(inj_key), injection, ttl_seconds=ttl)
        solver.context_store.set(str(lin_key), lineage, ttl_seconds=ttl)
