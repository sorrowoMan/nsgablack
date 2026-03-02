from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from ..utils.context.context_store import ContextStore, create_context_store
from ..utils.context.snapshot_store import SnapshotStore, create_snapshot_store
from ..utils.engineering.error_policy import report_soft_error

logger = logging.getLogger(__name__)


class SolverRuntime:
    """Compatibility facade that forwards runtime state operations to SolverBase."""

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
            self.set_context_store(context_store)
        elif getattr(self.solver, "context_store", None) is None:
            try:
                self.set_context_store(
                    create_context_store(
                        backend=context_store_backend,
                        ttl_seconds=context_store_ttl_seconds,
                        redis_url=context_store_redis_url,
                        key_prefix=context_store_key_prefix,
                    )
                )
            except Exception as exc:
                report_soft_error(
                    component="SolverRuntime",
                    event="init_context_store",
                    exc=exc,
                    logger=logger,
                    context_store=None,
                    strict=False,
                )
                self.set_context_store(create_context_store(backend="memory", ttl_seconds=context_store_ttl_seconds))

        if snapshot_store is not None:
            self.set_snapshot_store(snapshot_store)
        elif getattr(self.solver, "snapshot_store", None) is None:
            try:
                base_dir = snapshot_store_dir or "runs/snapshots"
                self.set_snapshot_store(
                    create_snapshot_store(
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
                )
            except Exception as exc:
                report_soft_error(
                    component="SolverRuntime",
                    event="init_snapshot_store",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(self.solver, "context_store", None),
                    strict=False,
                )
                self.set_snapshot_store(
                    create_snapshot_store(backend="memory", ttl_seconds=snapshot_store_ttl_seconds)
                )

        if not getattr(self.solver, "snapshot_schema", None):
            setattr(self.solver, "snapshot_schema", str(snapshot_schema or "population_snapshot_v1"))

    @property
    def context_store(self) -> Optional[ContextStore]:
        return getattr(self.solver, "context_store", None)

    @property
    def snapshot_store(self) -> Optional[SnapshotStore]:
        return getattr(self.solver, "snapshot_store", None)

    @property
    def snapshot_schema(self) -> str:
        return str(getattr(self.solver, "snapshot_schema", "population_snapshot_v1"))

    def set_context_store(self, store: ContextStore) -> None:
        setter = getattr(self.solver, "set_context_store", None)
        if callable(setter):
            setter(store)
        else:
            setattr(self.solver, "context_store", store)

    def set_snapshot_store(self, store: SnapshotStore) -> None:
        setter = getattr(self.solver, "set_snapshot_store", None)
        if callable(setter):
            setter(store)
        else:
            setattr(self.solver, "snapshot_store", store)

    def _invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        fn = getattr(self.solver, str(name), None)
        if not callable(fn):
            raise AttributeError(f"solver missing callable method: {name}")
        return fn(*args, **kwargs)

    def write_population_snapshot(self, population: Any, objectives: Any, violations: Any) -> bool:
        try:
            return bool(self._invoke("write_population_snapshot", population, objectives, violations))
        except AttributeError:
            try:
                setattr(self.solver, "population", population)
                setattr(self.solver, "objectives", objectives)
                setattr(self.solver, "constraint_violations", violations)
            except Exception:
                return False
            return True

    def read_snapshot(self, key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            payload = self._invoke("read_snapshot", key)
        except AttributeError:
            return None
        return payload if isinstance(payload, dict) else payload

    def set_best_snapshot(self, best_x: Any, best_objective: Any) -> None:
        try:
            self._invoke("set_best_snapshot", best_x, best_objective)
            return
        except AttributeError:
            pass
        setattr(self.solver, "best_x", best_x)
        setattr(self.solver, "best_objective", best_objective)

    def increment_evaluation_count(self, delta: int = 1) -> int:
        try:
            return int(self._invoke("increment_evaluation_count", int(delta)))
        except AttributeError:
            current = int(getattr(self.solver, "evaluation_count", 0) or 0) + int(delta)
            setattr(self.solver, "evaluation_count", current)
            return current

    def set_generation(self, generation: int) -> int:
        try:
            return int(self._invoke("set_generation", int(generation)))
        except AttributeError:
            value = int(generation)
            setattr(self.solver, "generation", value)
            return value

    def set_pareto_snapshot(self, solutions: Any, objectives: Any) -> None:
        try:
            self._invoke("set_pareto_snapshot", solutions, objectives)
            return
        except AttributeError:
            pass
        setattr(self.solver, "pareto_solutions", solutions)
        setattr(self.solver, "pareto_objectives", objectives)

    def resolve_best_snapshot(self) -> Tuple[Any, Any]:
        try:
            out = self._invoke("resolve_best_snapshot")
            if isinstance(out, tuple) and len(out) == 2:
                return out
        except AttributeError:
            pass

        helper = getattr(self.solver, "_resolve_best_snapshot", None)
        if callable(helper):
            out = helper()
            if isinstance(out, tuple) and len(out) == 2:
                return out
        return getattr(self.solver, "best_x", None), getattr(self.solver, "best_objective", None)

    def get_context(self) -> Dict[str, Any]:
        try:
            ctx = self._invoke("get_context")
            return dict(ctx) if isinstance(ctx, dict) else {}
        except AttributeError:
            best_x, best_obj = self.resolve_best_snapshot()
            return {
                "generation": int(getattr(self.solver, "generation", 0) or 0),
                "evaluation_count": int(getattr(self.solver, "evaluation_count", 0) or 0),
                "best_x": best_x,
                "best_objective": best_obj,
            }

    def _ensure_snapshot_readable(self, ctx: Dict[str, Any]) -> None:
        checker = getattr(self.solver, "_ensure_snapshot_readable", None)
        if callable(checker):
            checker(ctx)
            return
        key = ctx.get("snapshot_key") if isinstance(ctx, dict) else None
        if key is None:
            return
        if self.read_snapshot(str(key)) is None:
            raise RuntimeError("snapshot_key present but snapshot_store returned None")
