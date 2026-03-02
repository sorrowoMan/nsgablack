from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..utils.context.context_keys import (
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_CONSTRAINT_VIOLATIONS_REF,
    KEY_DECISION_TRACE,
    KEY_DECISION_TRACE_REF,
    KEY_EVALUATION_COUNT,
    KEY_GENERATION,
    KEY_HISTORY,
    KEY_HISTORY_REF,
    KEY_OBJECTIVES,
    KEY_OBJECTIVES_REF,
    KEY_PARETO_OBJECTIVES,
    KEY_PARETO_OBJECTIVES_REF,
    KEY_PARETO_SOLUTIONS,
    KEY_PARETO_SOLUTIONS_REF,
    KEY_POPULATION,
    KEY_POPULATION_REF,
    KEY_SNAPSHOT_BACKEND,
    KEY_SNAPSHOT_KEY,
    KEY_SNAPSHOT_META,
    KEY_SNAPSHOT_SCHEMA,
)
from ..utils.context.context_store import ContextStore, create_context_store
from ..utils.context.snapshot_store import SnapshotStore, create_snapshot_store, make_snapshot_key
from ..utils.engineering.error_policy import report_soft_error

logger = logging.getLogger(__name__)


class SolverRuntime:
    """Runtime state hub for solver snapshots (runtime-first access path)."""

    def __init__(
        self,
        solver: Any,
        context_store: Optional[ContextStore] = None,
        snapshot_store: Optional[SnapshotStore] = None,
        *,
        context_store_backend: str = "memory",
        context_store_ttl_seconds: Optional[float] = None,
        context_store_redis_url: str = "redis://localhost:6379/0",
        context_store_key_prefix: str = "nsgablack:context",
        snapshot_store_backend: str = "memory",
        snapshot_store_ttl_seconds: Optional[float] = None,
        snapshot_store_redis_url: str = "redis://localhost:6379/0",
        snapshot_store_key_prefix: str = "nsgablack:snapshot",
        snapshot_store_dir: Optional[str] = None,
        snapshot_store_serializer: str = "safe",
        snapshot_store_hmac_env_var: str = "NSGABLACK_SNAPSHOT_HMAC_KEY",
        snapshot_store_unsafe_allow_unsigned: bool = False,
        snapshot_store_max_payload_bytes: int = 8_388_608,
        snapshot_schema: str = "population_snapshot_v1",
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
        if snapshot_store is not None:
            self.snapshot_store = snapshot_store
        else:
            base_dir = snapshot_store_dir or "runs/snapshots"
            self.snapshot_store = create_snapshot_store(
                backend=snapshot_store_backend,
                ttl_seconds=snapshot_store_ttl_seconds,
                redis_url=snapshot_store_redis_url,
                key_prefix=snapshot_store_key_prefix,
                base_dir=base_dir,
                serializer=snapshot_store_serializer,
                hmac_env_var=snapshot_store_hmac_env_var,
                unsafe_allow_unsigned=snapshot_store_unsafe_allow_unsigned,
                max_payload_bytes=snapshot_store_max_payload_bytes,
            )
        self.snapshot_schema = str(snapshot_schema or "population_snapshot_v1")
        self._latest_snapshot_handle = None
        self._snapshot_generation = None

    def set_context_store(self, store: ContextStore) -> None:
        self.context_store = store

    def set_snapshot_store(self, store: SnapshotStore) -> None:
        self.snapshot_store = store

    def write_population_snapshot(self, population: Any, objectives: Any, violations: Any) -> bool:
        try:
            pop = np.asarray(population, dtype=float)
            obj = np.asarray(objectives, dtype=float)
            vio = np.asarray(violations, dtype=float).reshape(-1)
        except Exception as exc:
            report_soft_error(
                component="SolverRuntime",
                event="write_population_snapshot_cast",
                exc=exc,
                logger=logger,
                context_store=getattr(self, "context_store", None),
                strict=False,
            )
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
        self._persist_snapshot(
            population=pop,
            objectives=obj,
            violations=vio,
            include_pareto=True,
            include_history=True,
            include_decision_trace=True,
            complete=True,
        )
        return True

    def _snapshot_run_id(self) -> Optional[str]:
        for attr in ("run_id", "_run_id", "experiment_id"):
            rid = getattr(self.solver, attr, None)
            if rid:
                return str(rid)
        return None

    def _build_snapshot_key(self) -> str:
        run_id = self._snapshot_run_id()
        generation = getattr(self.solver, "generation", None)
        step = getattr(self.solver, "step_count", None)
        prefix = run_id or "snapshot"
        return make_snapshot_key(prefix=prefix, generation=generation, step=step)

    def _snapshot_meta(
        self,
        population: Optional[np.ndarray],
        objectives: Optional[np.ndarray],
        violations: Optional[np.ndarray],
        *,
        pareto_solutions: Optional[np.ndarray] = None,
        pareto_objectives: Optional[np.ndarray] = None,
        complete: bool = True,
    ) -> Dict[str, Any]:
        meta: Dict[str, Any] = {"complete": bool(complete)}
        if population is not None:
            meta["population_shape"] = list(np.asarray(population).shape)
            meta["population_size"] = int(np.asarray(population).shape[0]) if np.asarray(population).ndim >= 1 else 0
        if objectives is not None:
            meta["objectives_shape"] = list(np.asarray(objectives).shape)
        if violations is not None:
            meta["violations_shape"] = list(np.asarray(violations).shape)
        if pareto_solutions is not None:
            try:
                meta["pareto_solutions_shape"] = list(np.asarray(pareto_solutions).shape)
            except Exception:
                meta["pareto_solutions_shape"] = []
        if pareto_objectives is not None:
            try:
                meta["pareto_objectives_shape"] = list(np.asarray(pareto_objectives).shape)
            except Exception:
                meta["pareto_objectives_shape"] = []
        return meta

    def _prepare_snapshot_payload(
        self,
        population: Optional[np.ndarray],
        objectives: Optional[np.ndarray],
        violations: Optional[np.ndarray],
        *,
        pareto_solutions: Optional[np.ndarray] = None,
        pareto_objectives: Optional[np.ndarray] = None,
        history: Optional[Any] = None,
        decision_trace: Optional[Any] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        pop_arr = None
        if population is not None:
            pop_arr = np.asarray(population, dtype=float)
            if pop_arr.ndim == 1:
                pop_arr = pop_arr.reshape(1, -1) if pop_arr.size > 0 else pop_arr.reshape(0, 0)
            data[KEY_POPULATION] = pop_arr

        obj_arr = None
        if objectives is not None:
            obj_arr = np.asarray(objectives, dtype=float)
            if obj_arr.ndim == 1:
                obj_arr = obj_arr.reshape(-1, 1) if obj_arr.size > 0 else obj_arr.reshape(0, 0)
            data[KEY_OBJECTIVES] = obj_arr
        elif pop_arr is not None:
            data[KEY_OBJECTIVES] = np.zeros((int(pop_arr.shape[0]), 0), dtype=float)

        if violations is not None:
            vio_arr = np.asarray(violations, dtype=float).reshape(-1)
            data[KEY_CONSTRAINT_VIOLATIONS] = vio_arr
        elif pop_arr is not None:
            data[KEY_CONSTRAINT_VIOLATIONS] = np.zeros((int(pop_arr.shape[0]),), dtype=float)

        if pareto_solutions is not None:
            try:
                data[KEY_PARETO_SOLUTIONS] = np.asarray(pareto_solutions, dtype=float)
            except Exception:
                data[KEY_PARETO_SOLUTIONS] = pareto_solutions
        if pareto_objectives is not None:
            try:
                data[KEY_PARETO_OBJECTIVES] = np.asarray(pareto_objectives, dtype=float)
            except Exception:
                data[KEY_PARETO_OBJECTIVES] = pareto_objectives
        if history is not None:
            data[KEY_HISTORY] = history
        if decision_trace is not None:
            data[KEY_DECISION_TRACE] = decision_trace
        return data

    def _persist_snapshot(
        self,
        *,
        population: Optional[np.ndarray] = None,
        objectives: Optional[np.ndarray] = None,
        violations: Optional[np.ndarray] = None,
        include_pareto: bool = False,
        include_history: bool = False,
        include_decision_trace: bool = False,
        force_key: Optional[str] = None,
        complete: Optional[bool] = None,
    ) -> None:
        store = getattr(self, "snapshot_store", None)
        if store is None:
            return
        if population is None:
            population = getattr(self.solver, "population", None)
        if objectives is None:
            objectives = getattr(self.solver, "objectives", None)
        if violations is None:
            violations = getattr(self.solver, "constraint_violations", None)

        pareto_solutions = getattr(self.solver, "pareto_solutions", None) if include_pareto else None
        pareto_objectives = getattr(self.solver, "pareto_objectives", None) if include_pareto else None
        history = getattr(self.solver, "history", None) if include_history else None
        decision_trace = getattr(self.solver, "decision_trace", None) if include_decision_trace else None

        is_complete = complete
        if is_complete is None:
            is_complete = objectives is not None and violations is not None

        meta = self._snapshot_meta(
            population=np.asarray(population) if population is not None else None,
            objectives=np.asarray(objectives) if objectives is not None else None,
            violations=np.asarray(violations) if violations is not None else None,
            pareto_solutions=np.asarray(pareto_solutions) if pareto_solutions is not None else None,
            pareto_objectives=np.asarray(pareto_objectives) if pareto_objectives is not None else None,
            complete=bool(is_complete),
        )

        key = force_key
        gen = getattr(self.solver, "generation", None)
        if key is None and self._latest_snapshot_handle is not None:
            if self._snapshot_generation == gen:
                key = self._latest_snapshot_handle.key
        if key is None:
            key = self._build_snapshot_key()

        payload = self._prepare_snapshot_payload(
            population=population,
            objectives=objectives,
            violations=violations,
            pareto_solutions=pareto_solutions,
            pareto_objectives=pareto_objectives,
            history=history,
            decision_trace=decision_trace,
        )
        try:
            handle = store.write(
                payload,
                key=key,
                meta=meta,
                schema=self.snapshot_schema,
                ttl_seconds=getattr(self.solver, "snapshot_store_ttl_seconds", None),
            )
        except Exception as exc:
            report_soft_error(
                component="SolverRuntime",
                event="snapshot_store_write",
                exc=exc,
                logger=logger,
                context_store=getattr(self, "context_store", None),
                strict=bool(getattr(self.solver, "snapshot_strict", False)),
            )
            return
        self._latest_snapshot_handle = handle
        self._snapshot_generation = gen

    def read_snapshot(self, key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        store = getattr(self, "snapshot_store", None)
        if store is None:
            return None
        snap_key = key
        if snap_key is None and self._latest_snapshot_handle is not None:
            snap_key = self._latest_snapshot_handle.key
        if not snap_key:
            return None
        try:
            record = store.read(str(snap_key))
        except Exception as exc:
            report_soft_error(
                component="SolverRuntime",
                event="snapshot_store_read",
                exc=exc,
                logger=logger,
                context_store=getattr(self, "context_store", None),
                strict=bool(getattr(self.solver, "snapshot_strict", False)),
            )
            return None
        if record is None:
            return None
        return dict(record.data)

    def set_best_snapshot(self, best_x: Any, best_objective: Any) -> None:
        self.solver.best_x = best_x
        try:
            self.solver.best_objective = None if best_objective is None else float(best_objective)
        except Exception as exc:
            report_soft_error(
                component="SolverRuntime",
                event="set_best_snapshot_cast",
                exc=exc,
                logger=logger,
                context_store=getattr(self, "context_store", None),
                strict=False,
                level="debug",
            )
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
            except Exception as exc:
                report_soft_error(
                    component="SolverRuntime",
                    event="resolve_best_snapshot",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(self, "context_store", None),
                    strict=False,
                    level="debug",
                )
        return best_x, best_obj

    def get_context(self) -> Dict[str, Any]:
        best_x, best_obj = self.resolve_best_snapshot()
        ctx: Dict[str, Any] = {
            KEY_GENERATION: int(getattr(self.solver, "generation", 0)),
            KEY_BEST_X: best_x,
            KEY_BEST_OBJECTIVE: best_obj,
            KEY_EVALUATION_COUNT: int(getattr(self.solver, "evaluation_count", 0)),
        }
        pop = getattr(self.solver, "population", None)
        obj = getattr(self.solver, "objectives", None)
        vio = getattr(self.solver, "constraint_violations", None)
        if pop is not None or obj is not None or vio is not None:
            self._persist_snapshot(
                population=pop,
                objectives=obj,
                violations=vio,
                include_pareto=True,
                include_history=True,
                include_decision_trace=True,
                complete=obj is not None and vio is not None,
            )
        handle = self._latest_snapshot_handle
        if handle is not None:
            ctx[KEY_SNAPSHOT_KEY] = handle.key
            ctx[KEY_SNAPSHOT_BACKEND] = handle.backend
            ctx[KEY_SNAPSHOT_SCHEMA] = handle.schema
            ctx[KEY_SNAPSHOT_META] = dict(handle.meta or {})
            ctx[KEY_POPULATION_REF] = handle.key
            ctx[KEY_OBJECTIVES_REF] = handle.key
            ctx[KEY_CONSTRAINT_VIOLATIONS_REF] = handle.key
            if getattr(self.solver, "pareto_solutions", None) is not None:
                ctx[KEY_PARETO_SOLUTIONS_REF] = handle.key
            if getattr(self.solver, "pareto_objectives", None) is not None:
                ctx[KEY_PARETO_OBJECTIVES_REF] = handle.key
            if getattr(self.solver, "history", None) is not None:
                ctx[KEY_HISTORY_REF] = handle.key
            if getattr(self.solver, "decision_trace", None) is not None:
                ctx[KEY_DECISION_TRACE_REF] = handle.key
        if bool(getattr(self.solver, "snapshot_strict", False)):
            self._ensure_snapshot_readable(ctx)
        dynamic = getattr(self.solver, "dynamic_signals", None)
        if dynamic is not None:
            ctx["dynamic"] = dynamic
        phase_id = getattr(self.solver, "dynamic_phase_id", None)
        if phase_id is not None:
            ctx["phase_id"] = phase_id
        try:
            self.context_store.update(ctx)
        except Exception as exc:
            report_soft_error(
                component="SolverRuntime",
                event="context_store_update",
                exc=exc,
                logger=logger,
                context_store=getattr(self, "context_store", None),
                strict=False,
                level="debug",
            )
        return ctx

    def _ensure_snapshot_readable(self, ctx: Dict[str, Any]) -> None:
        key = ctx.get(KEY_SNAPSHOT_KEY)
        if key is None or str(key).strip() == "":
            has_state = any(
                getattr(self.solver, attr, None) is not None
                for attr in ("population", "objectives", "constraint_violations")
            )
            if has_state:
                raise RuntimeError("snapshot_key missing while solver has population/objectives/violations")
            return
        payload = self.read_snapshot(str(key))
        if payload is None:
            raise RuntimeError("snapshot_key present but snapshot_store returned None")
