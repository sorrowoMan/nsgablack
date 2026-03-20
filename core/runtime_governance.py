from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..utils.context.context_keys import (
    KEY_COMPANION_NEXT_ELIGIBLE_GENERATION,
    KEY_COMPANION_PHASE_COUNT_USED,
    KEY_COMPANION_PHASE_INDEX,
    KEY_COMPANION_TRIGGER_REASON,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_CROSSOVER_RATE,
    KEY_MUTATION_RATE,
    KEY_OBJECTIVES,
    KEY_POPULATION,
    KEY_POPULATION_REF,
    KEY_RUNNING,
    KEY_SNAPSHOT_KEY,
)
from ..utils.context.snapshot_store import make_snapshot_key
from ..utils.engineering.error_policy import report_soft_error

logger = logging.getLogger(__name__)


def _create_local_rng(*, solver: Any, stream: str, seed: Optional[int] = None) -> np.random.Generator:
    if seed is not None:
        return np.random.default_rng(int(seed))
    if solver is not None:
        fork = getattr(solver, "fork_rng", None)
        if callable(fork):
            try:
                rng = fork(str(stream or "runtime_governance"))
                if isinstance(rng, np.random.Generator):
                    return rng
            except Exception as exc:
                report_soft_error(
                    component="RuntimeGovernance",
                    event="create_local_rng",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(solver, "context_store", None),
                    strict=False,
                    level="debug",
                )
    return np.random.default_rng()

def resolve_population_snapshot(solver: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if solver is None:
        return np.zeros((0, 0), dtype=float), np.zeros((0, 0), dtype=float), np.zeros((0,), dtype=float)

    reader = getattr(solver, "read_snapshot", None)
    if callable(reader):
        payload = None
        try:
            payload = reader()
        except Exception as exc:
            report_soft_error(
                component="RuntimeGovernance",
                event="resolve_population_snapshot.reader_default",
                exc=exc,
                logger=logger,
                context_store=getattr(solver, "context_store", None),
                strict=False,
                level="debug",
            )
            payload = None
        if payload is None:
            getter = getattr(solver, "get_context", None)
            if callable(getter):
                try:
                    ctx = getter()
                except Exception as exc:
                    report_soft_error(
                        component="RuntimeGovernance",
                        event="resolve_population_snapshot.get_context",
                        exc=exc,
                        logger=logger,
                        context_store=getattr(solver, "context_store", None),
                        strict=False,
                        level="debug",
                    )
                    ctx = None
                if isinstance(ctx, dict):
                    key = ctx.get(KEY_POPULATION_REF) or ctx.get(KEY_SNAPSHOT_KEY)
                    if key:
                        try:
                            payload = reader(key)
                        except Exception as exc:
                            report_soft_error(
                                component="RuntimeGovernance",
                                event="resolve_population_snapshot.reader_with_key",
                                exc=exc,
                                logger=logger,
                                context_store=getattr(solver, "context_store", None),
                                strict=False,
                                level="debug",
                            )
                            payload = None
        if payload is not None:
            data = payload.data if hasattr(payload, "data") else payload
            if isinstance(data, dict):
                try:
                    x = np.asarray(data.get(KEY_POPULATION, np.zeros((0, 0))), dtype=float)
                    f = np.asarray(data.get(KEY_OBJECTIVES, np.zeros((0, 0))), dtype=float)
                    v = np.asarray(data.get(KEY_CONSTRAINT_VIOLATIONS, np.zeros((0,))), dtype=float).reshape(-1)
                    if x.ndim == 1:
                        x = x.reshape(1, -1) if x.size > 0 else x.reshape(0, 0)
                    if f.ndim == 1:
                        f = f.reshape(-1, 1) if f.size > 0 else f.reshape(0, 0)
                    if x.size > 0 or f.size > 0:
                        return x, f, v
                except Exception as exc:
                    report_soft_error(
                        component="RuntimeGovernance",
                        event="resolve_population_snapshot.payload_cast",
                        exc=exc,
                        logger=logger,
                        context_store=getattr(solver, "context_store", None),
                        strict=False,
                        level="debug",
                    )

    adapter = getattr(solver, "adapter", None)
    if adapter is not None:
        getter = getattr(adapter, "get_population", None)
        if callable(getter):
            try:
                x, f, v = getter()
                x_arr = np.asarray(x, dtype=float)
                f_arr = np.asarray(f, dtype=float)
                v_arr = np.asarray(v, dtype=float).reshape(-1)
                if x_arr.ndim == 1:
                    x_arr = x_arr.reshape(1, -1) if x_arr.size > 0 else x_arr.reshape(0, 0)
                if f_arr.ndim == 1:
                    f_arr = f_arr.reshape(-1, 1) if f_arr.size > 0 else f_arr.reshape(0, 0)
                return x_arr, f_arr, v_arr
            except Exception as exc:
                report_soft_error(
                    component="RuntimeGovernance",
                    event="resolve_population_snapshot.adapter_get_population",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(solver, "context_store", None),
                    strict=False,
                    level="debug",
                )
    x = np.asarray(getattr(solver, "population", np.zeros((0, 0))), dtype=float)
    f = np.asarray(getattr(solver, "objectives", np.zeros((0, 0))), dtype=float)
    v = np.asarray(getattr(solver, "constraint_violations", np.zeros((0,))), dtype=float).reshape(-1)
    if x.ndim == 1:
        x = x.reshape(1, -1) if x.size > 0 else x.reshape(0, 0)
    if f.ndim == 1:
        f = f.reshape(-1, 1) if f.size > 0 else f.reshape(0, 0)
    return x, f, v

def commit_population_snapshot(
    solver: Any,
    population: np.ndarray,
    objectives: np.ndarray,
    violations: np.ndarray,
) -> bool:
    if solver is None:
        return False

    try:
        x_arr = np.asarray(population, dtype=float)
        f_arr = np.asarray(objectives, dtype=float)
        v_arr = np.asarray(violations, dtype=float).reshape(-1)
    except Exception as exc:
        report_soft_error(
            component="RuntimeGovernance",
            event="commit_population_snapshot.cast",
            exc=exc,
            logger=logger,
            context_store=getattr(solver, "context_store", None),
            strict=False,
            level="debug",
        )
        return False

    if x_arr.ndim == 1:
        x_arr = x_arr.reshape(1, -1) if x_arr.size > 0 else x_arr.reshape(0, 0)
    if f_arr.ndim == 1:
        f_arr = f_arr.reshape(-1, 1) if f_arr.size > 0 else f_arr.reshape(0, 0)

    adapter = getattr(solver, "adapter", None)
    if adapter is not None:
        for method_name in ("set_population", "set_population_snapshot", "update_population"):
            setter = getattr(adapter, method_name, None)
            if not callable(setter):
                continue
            try:
                handled = setter(x_arr, f_arr, v_arr)
            except TypeError:
                try:
                    handled = setter(solver, x_arr, f_arr, v_arr)
                except Exception as exc:
                    report_soft_error(
                        component="RuntimeGovernance",
                        event=f"commit_population_snapshot.{method_name}.call_with_solver",
                        exc=exc,
                        logger=logger,
                        context_store=getattr(solver, "context_store", None),
                        strict=False,
                        level="debug",
                    )
                    handled = False
            except Exception as exc:
                report_soft_error(
                    component="RuntimeGovernance",
                    event=f"commit_population_snapshot.{method_name}",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(solver, "context_store", None),
                    strict=False,
                    level="debug",
                )
                handled = False
            if handled is not False:
                return True

    writer = getattr(solver, "write_population_snapshot", None)
    if callable(writer):
        try:
            return bool(writer(x_arr, f_arr, v_arr))
        except Exception as exc:
            report_soft_error(
                component="RuntimeGovernance",
                event="commit_population_snapshot.writer",
                exc=exc,
                logger=logger,
                context_store=getattr(solver, "context_store", None),
                strict=False,
                level="debug",
            )
            return False
    return False


def _best_fitness(objectives: np.ndarray) -> float:
    if objectives.size == 0:
        return float("inf")
    obj = np.asarray(objectives, dtype=float)
    if obj.ndim == 1:
        obj = obj.reshape(-1, 1)
    if obj.shape[1] == 1:
        return float(np.min(obj[:, 0]))
    return float(np.min(np.sum(obj, axis=1)))

@dataclass(frozen=True)
class ConvergenceConfig:
    stagnation_window: int = 20
    improvement_epsilon: float = 1e-4
    diversity_threshold: float = 0.05
    min_generations: int = 30
    enable_early_stop: bool = False


class ConvergenceMonitor:
    def __init__(self, config: Optional[ConvergenceConfig] = None, *, enabled: bool = True) -> None:
        self.cfg = config or ConvergenceConfig()
        self.enabled = bool(enabled)
        self.best_fitness_history: List[float] = []
        self.diversity_history: List[float] = []
        self.stagnation_count = 0
        self.is_converged = False
        self.convergence_generation: Optional[int] = None
        self._rng = np.random.default_rng()

    def on_solver_init(self, solver: Any) -> None:
        if not self.enabled:
            return None
        self._rng = _create_local_rng(solver=solver, stream="convergence")
        self.best_fitness_history = []
        self.diversity_history = []
        self.stagnation_count = 0
        self.is_converged = False
        self.convergence_generation = None
        return None

    def on_population_init(self, population: np.ndarray, objectives: np.ndarray, violations: np.ndarray) -> None:
        if not self.enabled:
            return None
        if objectives is None or len(objectives) == 0:
            return None
        best_fitness = _best_fitness(np.asarray(objectives, dtype=float))
        self.best_fitness_history.append(best_fitness)
        self._update_diversity(np.asarray(population, dtype=float))
        return None

    def on_context_build(self, solver: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return context
        context[KEY_RUNNING] = bool(getattr(solver, "running", False))
        return context

    def on_generation_end(self, solver: Any, generation: int) -> None:
        if not self.enabled:
            return None
        pop, objectives, _ = resolve_population_snapshot(solver)
        if objectives.size == 0:
            return None

        best_fitness = _best_fitness(objectives)
        self.best_fitness_history.append(best_fitness)
        self._update_diversity(pop)

        if len(self.best_fitness_history) >= int(self.cfg.stagnation_window):
            recent = self.best_fitness_history[-int(self.cfg.stagnation_window) :]
            improvement = recent[0] - recent[-1]
            if abs(improvement) < float(self.cfg.improvement_epsilon) * abs(recent[0]):
                self.stagnation_count += 1
            else:
                self.stagnation_count = 0

        current_diversity = self.diversity_history[-1] if self.diversity_history else 1.0
        if (
            int(generation) >= int(self.cfg.min_generations)
            and self.stagnation_count >= int(self.cfg.stagnation_window)
            and float(current_diversity) < float(self.cfg.diversity_threshold)
        ):
            self.is_converged = True
            self.convergence_generation = int(generation)
            if bool(self.cfg.enable_early_stop):
                request_stop = getattr(solver, "request_stop", None)
                if callable(request_stop):
                    request_stop()
                else:
                    setattr(solver, "stop_requested", True)
                setattr(solver, "running", False)
        return None

    def on_solver_finish(self, solver: Any, result: Dict[str, Any]) -> None:
        if not self.enabled:
            return None
        result["convergence_detected"] = bool(self.is_converged)
        result["convergence_generation"] = self.convergence_generation
        result["final_diversity"] = self.diversity_history[-1] if self.diversity_history else None
        result["stagnation_count"] = int(self.stagnation_count)
        return None

    def get_convergence_info(self) -> Dict[str, Any]:
        return {
            "is_converged": bool(self.is_converged),
            "convergence_generation": self.convergence_generation,
            "stagnation_count": int(self.stagnation_count),
            "current_diversity": self.diversity_history[-1] if self.diversity_history else None,
            "best_fitness_history": list(self.best_fitness_history),
            "diversity_history": list(self.diversity_history),
        }

    def _update_diversity(self, population: np.ndarray) -> None:
        if population is None or len(population) < 2:
            self.diversity_history.append(0.0)
            return None

        pop_min = population.min(axis=0)
        pop_max = population.max(axis=0)
        pop_range = pop_max - pop_min + 1e-10
        pop_norm = (population - pop_min) / pop_range

        n_samples = min(30, len(pop_norm))
        indices = self._rng.choice(len(pop_norm), n_samples, replace=False)
        samples = pop_norm[indices]

        distances = []
        for i in range(n_samples):
            for j in range(i + 1, n_samples):
                distances.append(float(np.linalg.norm(samples[i] - samples[j])))

        diversity = float(np.mean(distances)) if distances else 0.0
        self.diversity_history.append(diversity)
        return None

@dataclass(frozen=True)
class AdaptiveParametersConfig:
    stagnation_window: int = 10
    improvement_threshold: float = 0.001
    min_mutation_rate: float = 0.05
    max_mutation_rate: float = 0.4
    min_crossover_rate: float = 0.5
    max_crossover_rate: float = 0.95


class AdaptiveParametersGovernor:
    def __init__(self, config: Optional[AdaptiveParametersConfig] = None, *, enabled: bool = True) -> None:
        self.cfg = config or AdaptiveParametersConfig()
        self.enabled = bool(enabled)
        self.best_fitness_history: List[float] = []
        self.stagnation_count = 0
        self.initial_crossover_rate: Optional[float] = None
        self.initial_mutation_rate: Optional[float] = None
        self.adaptation_history: List[Dict[str, Any]] = []

    def on_solver_init(self, solver: Any) -> None:
        if not self.enabled:
            return None
        self.best_fitness_history = []
        self.stagnation_count = 0
        self.adaptation_history = []
        self.initial_crossover_rate = float(getattr(solver, "crossover_rate", 0.0))
        self.initial_mutation_rate = float(getattr(solver, "mutation_rate", 0.0))
        return None

    def on_population_init(self, population: np.ndarray, objectives: np.ndarray, violations: np.ndarray) -> None:
        if not self.enabled:
            return None
        if objectives is None or len(objectives) == 0:
            return None
        self.best_fitness_history.append(_best_fitness(np.asarray(objectives, dtype=float)))
        return None

    def on_context_build(self, solver: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return context
        context[KEY_MUTATION_RATE] = float(getattr(solver, "mutation_rate", 0.0))
        context[KEY_CROSSOVER_RATE] = float(getattr(solver, "crossover_rate", 0.0))
        return context

    def on_generation_end(self, solver: Any, generation: int) -> None:
        if not self.enabled:
            return None
        _, objectives, _ = resolve_population_snapshot(solver)
        if objectives.size == 0:
            return None
        current_best = _best_fitness(objectives)
        self.best_fitness_history.append(current_best)

        if len(self.best_fitness_history) < 2:
            return None

        improvement = self.best_fitness_history[-2] - current_best
        if improvement > float(self.cfg.improvement_threshold):
            self.stagnation_count = 0
            self._adjust_parameters(solver, "improving", generation)
            return None

        self.stagnation_count += 1
        if self.stagnation_count >= int(self.cfg.stagnation_window):
            self._adjust_parameters(solver, "stagnant", generation)
            self.stagnation_count = 0
        return None

    def on_solver_finish(self, solver: Any, result: Dict[str, Any]) -> None:
        if not self.enabled:
            return None
        result["adaptation_history"] = self.adaptation_history
        result["final_crossover_rate"] = float(getattr(solver, "crossover_rate", 0.0))
        result["final_mutation_rate"] = float(getattr(solver, "mutation_rate", 0.0))
        return None

    def _adjust_parameters(self, solver: Any, state: str, generation: int) -> None:
        old_mutation = float(getattr(solver, "mutation_rate", 0.0))
        old_crossover = float(getattr(solver, "crossover_rate", 0.0))

        if state == "stagnant":
            new_mutation = min(float(self.cfg.max_mutation_rate), old_mutation + 0.05)
            new_crossover = max(float(self.cfg.min_crossover_rate), old_crossover - 0.03)
            action = "stagnant"
        elif state == "improving":
            new_mutation = max(float(self.cfg.min_mutation_rate), old_mutation - 0.02)
            new_crossover = min(float(self.cfg.max_crossover_rate), old_crossover + 0.03)
            action = "improving"
        else:
            return None

        setattr(solver, "mutation_rate", float(new_mutation))
        setattr(solver, "crossover_rate", float(new_crossover))

        self.adaptation_history.append(
            {
                "generation": int(generation),
                "action": action,
                "old_mutation_rate": float(old_mutation),
                "new_mutation_rate": float(new_mutation),
                "old_crossover_rate": float(old_crossover),
                "new_crossover_rate": float(new_crossover),
            }
        )
        return None

@dataclass
class CompanionEventRules:
    enable_stagnation: bool = True
    stagnation_window: int = 10
    improvement_epsilon: float = 1e-6
    enable_diversity_drop: bool = True
    diversity_threshold: Optional[float] = None


@dataclass
class CompanionOrchestratorConfig:
    trigger_mode: str = "mixed"  # periodic | event | mixed
    period_generations: int = 20
    phase_min_generation: int = 30
    phase_max_count: int = 3
    phase_cooldown_generations: int = 15
    phase_blocking: bool = True

    per_task_budget: int = 5
    global_budget: int = 200
    levelset_eps: float = 1e-3
    accept_metric: str = "linf"  # linf | l2 | weighted
    weighted_accept_weights: Optional[Sequence[float]] = None
    include_infeasible_anchors: bool = False

    max_accepted_per_task: int = 4
    max_injected_per_phase: int = 64

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
        if bool(event_due):
            return True, "event", cooldown_applied
        if bool(periodic_due):
            return True, "periodic", cooldown_applied
        return False, "none", cooldown_applied

class CompanionOrchestrator:
    def __init__(self, config: Optional[CompanionOrchestratorConfig] = None, *, enabled: bool = True) -> None:
        self.cfg = config or CompanionOrchestratorConfig()
        self.enabled = bool(enabled)
        self.scheduler = CompanionPhaseScheduler(self.cfg)

        self.phase_count_used: int = 0
        self.next_eligible_generation: int = int(self.cfg.phase_min_generation)
        self.last_return_generation: Optional[int] = None
        self.last_trigger_reason: str = ""

        self.phase_runs: List[CompanionPhaseRun] = []
        self.lineage_index: Dict[str, List[Dict[str, Any]]] = {}

        self._best_score: Optional[float] = None
        self._stagnation_count: int = 0

    def on_solver_init(self, solver: Any) -> None:
        if not self.enabled:
            return None
        self.phase_count_used = 0
        self.next_eligible_generation = int(self.cfg.phase_min_generation)
        self.last_return_generation = None
        self.last_trigger_reason = ""
        self.phase_runs = []
        self.lineage_index = {}
        self._best_score = None
        self._stagnation_count = 0
        self._sync_runtime_state(solver)
        return None

    def on_context_build(self, solver: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return context
        context[KEY_COMPANION_PHASE_INDEX] = int(self.phase_count_used)
        context[KEY_COMPANION_TRIGGER_REASON] = str(self.last_trigger_reason or "")
        context[KEY_COMPANION_NEXT_ELIGIBLE_GENERATION] = int(self.next_eligible_generation)
        context[KEY_COMPANION_PHASE_COUNT_USED] = int(self.phase_count_used)
        return context

    def on_generation_end(self, solver: Any, generation: int) -> bool:
        if not self.enabled:
            return False
        if solver is None or not bool(self.cfg.phase_blocking):
            return False

        pop, obj, vio = resolve_population_snapshot(solver)
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
            return False

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
        return bool(int(phase_run.injected_count) > 0)

    def get_report(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
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

    @staticmethod
    def _coerce_candidates(value: Any) -> List[np.ndarray]:
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

    @staticmethod
    def _pick_candidate(candidates: List[np.ndarray], *, rng: np.random.Generator) -> Optional[np.ndarray]:
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
            commit_population_snapshot(solver, base_x, base_f, base_v)
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
        commit_population_snapshot(solver, new_x, new_f, new_v)

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
            fallback_task = CompanionTask("", "", np.zeros((0,)), 0)
            task = task_by_anchor.get(anchor_id, fallback_task)
            entry = {
                "phase_index": int(phase_index),
                "anchor_id": anchor_id,
                "target_f": np.asarray(anchor["f"], dtype=float).tolist(),
                "validity": "active",
                "status": str(task.status),
                "accepted_count": int(len(task.accepted_x)),
                "task_id": str(task.task_id),
                "task_snapshot_key": task.snapshot_key,
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
        base_x, base_f, base_v = resolve_population_snapshot(solver)
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

        rng = _create_local_rng(solver=solver, stream="companion")
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
