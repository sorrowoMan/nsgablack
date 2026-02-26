from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..utils.context.context_keys import (
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_EVALUATION_COUNT,
    KEY_GENERATION,
    KEY_HISTORY,
    KEY_OBJECTIVES,
    KEY_PARETO_OBJECTIVES,
    KEY_PARETO_SOLUTIONS,
    KEY_POPULATION,
)
from ..utils.context.context_store import ContextStore, create_context_store


class SolverRuntime:
    """Runtime state hub for solver snapshots (runtime-first access path)."""

    def __init__(
        self,
        solver: Any,
        context_store: Optional[ContextStore] = None,
        *,
        context_store_backend: str = "memory",
        context_store_ttl_seconds: Optional[float] = None,
        context_store_redis_url: str = "redis://localhost:6379/0",
        context_store_key_prefix: str = "nsgablack:context",
    ) -> None:
        self.solver = solver
        if context_store is not None:
            self.context_store = context_store
        else:
            self.context_store = create_context_store(
                backend=context_store_backend,
                ttl_seconds=context_store_ttl_seconds,
                redis_url=context_store_redis_url,
                key_prefix=context_store_key_prefix,
            )

    def set_context_store(self, store: ContextStore) -> None:
        self.context_store = store

    def write_population_snapshot(self, population: Any, objectives: Any, violations: Any) -> bool:
        try:
            pop = np.asarray(population, dtype=float)
            obj = np.asarray(objectives, dtype=float)
            vio = np.asarray(violations, dtype=float).reshape(-1)
        except Exception:
            return False
        if pop.ndim == 1:
            pop = pop.reshape(1, -1) if pop.size > 0 else pop.reshape(0, 0)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1) if obj.size > 0 else obj.reshape(0, 0)
        if obj.shape[0] != pop.shape[0] or vio.shape[0] != pop.shape[0]:
            return False
        self.solver.population = pop
        self.solver.objectives = obj
        self.solver.constraint_violations = vio
        return True

    def set_best_snapshot(self, best_x: Any, best_objective: Any) -> None:
        self.solver.best_x = best_x
        try:
            self.solver.best_objective = None if best_objective is None else float(best_objective)
        except Exception:
            self.solver.best_objective = best_objective

    def increment_evaluation_count(self, delta: int = 1) -> int:
        current = int(getattr(self.solver, "evaluation_count", 0) or 0)
        current += int(delta)
        self.solver.evaluation_count = current
        return current

    def set_generation(self, generation: int) -> int:
        value = int(generation)
        self.solver.generation = value
        return value

    def set_pareto_snapshot(self, solutions: Any, objectives: Any) -> None:
        self.solver.pareto_solutions = None if solutions is None else np.asarray(solutions)
        self.solver.pareto_objectives = None if objectives is None else np.asarray(objectives)

    def resolve_best_snapshot(self) -> Tuple[Any, Any]:
        best_x = getattr(self.solver, "best_x", None)
        best_obj = getattr(self.solver, "best_objective", None)

        if best_obj is None:
            best_f = getattr(self.solver, "best_f", None)
            if best_f is not None:
                try:
                    best_obj = float(best_f)
                except Exception:
                    best_obj = None

        objectives = getattr(self.solver, "objectives", None)
        if best_obj is None and objectives is not None:
            try:
                obj = np.asarray(objectives, dtype=float)
                if obj.size > 0:
                    if obj.ndim == 1 or int(getattr(self.solver, "num_objectives", 1)) == 1:
                        idx = int(np.argmin(obj.reshape(-1)))
                        best_obj = float(obj.reshape(-1)[idx])
                    else:
                        scores = np.sum(obj, axis=1)
                        vio = getattr(self.solver, "constraint_violations", None)
                        if vio is not None:
                            vio_arr = np.asarray(vio, dtype=float).reshape(-1)
                            if vio_arr.shape[0] == scores.shape[0]:
                                scores = scores + vio_arr * 1e6
                        idx = int(np.argmin(scores))
                        best_obj = float(scores[idx])
                    if best_x is None:
                        pop = getattr(self.solver, "population", None)
                        if pop is not None:
                            pop_arr = np.asarray(pop)
                            if pop_arr.ndim >= 2 and idx < pop_arr.shape[0]:
                                best_x = pop_arr[idx]
            except Exception:
                pass
        return best_x, best_obj

    def get_context(self) -> Dict[str, Any]:
        best_x, best_obj = self.resolve_best_snapshot()
        ctx: Dict[str, Any] = {
            KEY_GENERATION: int(getattr(self.solver, "generation", 0)),
            KEY_POPULATION: getattr(self.solver, "population", None) if getattr(self.solver, "population", None) is not None else [],
            KEY_OBJECTIVES: getattr(self.solver, "objectives", None) if getattr(self.solver, "objectives", None) is not None else [],
            KEY_BEST_X: best_x,
            KEY_BEST_OBJECTIVE: best_obj,
            KEY_CONSTRAINT_VIOLATIONS: getattr(self.solver, "constraint_violations", None)
            if getattr(self.solver, "constraint_violations", None) is not None
            else [],
            KEY_PARETO_OBJECTIVES: getattr(self.solver, "pareto_objectives", None)
            if getattr(self.solver, "pareto_objectives", None) is not None
            else [],
            KEY_PARETO_SOLUTIONS: getattr(self.solver, "pareto_solutions", None)
            if getattr(self.solver, "pareto_solutions", None) is not None
            else {},
            KEY_EVALUATION_COUNT: int(getattr(self.solver, "evaluation_count", 0)),
            KEY_HISTORY: getattr(self.solver, "history", None) if getattr(self.solver, "history", None) is not None else [],
        }
        dynamic = getattr(self.solver, "dynamic_signals", None)
        if dynamic is not None:
            ctx["dynamic"] = dynamic
        phase_id = getattr(self.solver, "dynamic_phase_id", None)
        if phase_id is not None:
            ctx["phase_id"] = phase_id
        try:
            self.context_store.update(ctx)
        except Exception:
            pass
        return ctx
