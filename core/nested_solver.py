"""Problem-level inner-runtime evaluation contract (not L4 provider)."""

from __future__ import annotations

import inspect
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

import numpy as np


@dataclass(frozen=True)
class InnerSolveRequest:
    candidate: np.ndarray
    outer_generation: int
    outer_individual_id: int
    budget_units: float = 1.0
    parent_contract: str = ""
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class InnerSolveResult:
    objectives: np.ndarray
    violation: float
    status: str
    cost_units: float
    payload: Mapping[str, Any] | None = None


InnerSolverFactory = Callable[[Any, InnerSolveRequest], Any]
InnerResultProjector = Callable[[Any, np.ndarray, InnerSolveResult], tuple[np.ndarray, float]]
InnerProblemFactory = Callable[[np.ndarray, Dict[str, Any]], Any]
InnerBackendFactory = Callable[[Any, Dict[str, Any]], Any]
InnerRunner = Callable[[Any, Any, Dict[str, Any]], Mapping[str, Any]]


class InnerRuntimeEvaluator:
    """Problem-level evaluator for nested solve semantics."""

    def __init__(
        self,
        *,
        solver_factory: Optional[InnerSolverFactory] = None,
        result_projector: Optional[InnerResultProjector] = None,
        parent_contract: str = "",
        accepted_parent_contracts: Optional[tuple[str, ...]] = None,
        default_budget_units: float = 1.0,
        max_total_budget_units: Optional[float] = None,
    ) -> None:
        self.solver_factory = solver_factory
        self.result_projector = result_projector
        self.parent_contract = str(parent_contract or "")
        self.accepted_parent_contracts = tuple(str(x) for x in (accepted_parent_contracts or ()))
        self.default_budget_units = float(default_budget_units)
        self.max_total_budget_units = (
            None if max_total_budget_units is None else float(max_total_budget_units)
        )
        self.stats = {
            "calls": 0.0,
            "budget_spent": 0.0,
            "last_cost": 0.0,
            "failures": 0.0,
        }

    def can_handle(self, *, solver: Any, x: np.ndarray) -> bool:
        if callable(self.solver_factory):
            return True
        problem = getattr(solver, "problem", None)
        return callable(getattr(problem, "build_inner_solver", None))

    def evaluate(
        self,
        *,
        solver: Any,
        x: np.ndarray,
        individual_id: int,
        context: Mapping[str, Any] | None = None,
    ) -> Optional[tuple[np.ndarray, float]]:
        if not self.can_handle(solver=solver, x=x):
            return None
        ctx = dict(context or {})
        budget_units = float(ctx.get("inner_budget_units", self.default_budget_units))
        current_spent = float(self.stats.get("budget_spent", 0.0) or 0.0)
        if self.max_total_budget_units is not None and current_spent + budget_units > self.max_total_budget_units:
            return None

        request = InnerSolveRequest(
            candidate=np.asarray(x, dtype=float).reshape(-1),
            outer_generation=int(getattr(solver, "generation", 0)),
            outer_individual_id=int(individual_id),
            budget_units=budget_units,
            parent_contract=self.parent_contract,
            metadata=ctx,
        )
        inner_solver = self._build_inner_solver(solver, request)
        self._validate_parent_contract(inner_solver)
        try:
            result = self._run_inner_solver(inner_solver, request)
        except Exception:
            self.stats["failures"] = float(self.stats.get("failures", 0.0) or 0.0) + 1.0
            raise
        self.stats["calls"] = float(self.stats.get("calls", 0.0) or 0.0) + 1.0
        self.stats["budget_spent"] = current_spent + float(result.cost_units)
        self.stats["last_cost"] = float(result.cost_units)
        return self._project_result(solver, request.candidate, result)

    def _build_inner_solver(self, outer_solver: Any, request: InnerSolveRequest) -> Any:
        if callable(self.solver_factory):
            return self.solver_factory(outer_solver, request)
        problem = getattr(outer_solver, "problem", None)
        hook = getattr(problem, "build_inner_solver", None) if problem is not None else None
        if callable(hook):
            return hook(request.candidate, {"request": request, "solver": outer_solver})
        return None

    def _validate_parent_contract(self, inner_solver: Any) -> None:
        if inner_solver is None:
            return
        expected = set(self.accepted_parent_contracts)
        if self.parent_contract:
            expected.add(self.parent_contract)
        if not expected:
            return
        declared = getattr(inner_solver, "accepted_parent_contracts", None)
        if declared is None:
            raise ValueError("Inner solver missing accepted_parent_contracts declaration")
        declared_set = {str(x) for x in declared}
        if expected.isdisjoint(declared_set):
            raise ValueError(
                "Inner solver parent contract mismatch: "
                f"expected one of {sorted(expected)}, got {sorted(declared_set)}"
            )

    @staticmethod
    def _run_inner_solver(inner_solver: Any, request: InnerSolveRequest) -> InnerSolveResult:
        if inner_solver is None:
            raise RuntimeError("Inner solver factory returned None")
        run = getattr(inner_solver, "run", None)
        if not callable(run):
            raise RuntimeError("Inner solver has no callable run()")
        supports_return_dict = False
        try:
            supports_return_dict = "return_dict" in inspect.signature(run).parameters
        except Exception:
            supports_return_dict = False
        raw = run(return_dict=True) if supports_return_dict else run()
        if isinstance(raw, Mapping):
            obj = raw.get("objectives", raw.get("objective"))
            if obj is None:
                raise RuntimeError("Inner solver result missing objectives/objective")
            return InnerSolveResult(
                objectives=np.asarray(obj, dtype=float).reshape(-1),
                violation=float(raw.get("violation", 0.0)),
                status=str(raw.get("status", "ok")),
                cost_units=float(raw.get("cost_units", request.budget_units)),
                payload=dict(raw),
            )
        return InnerSolveResult(
            objectives=np.asarray(raw, dtype=float).reshape(-1),
            violation=0.0,
            status="ok",
            cost_units=float(request.budget_units),
            payload={"raw": raw},
        )

    def _project_result(self, outer_solver: Any, x: np.ndarray, result: InnerSolveResult) -> tuple[np.ndarray, float]:
        if callable(self.result_projector):
            return self.result_projector(outer_solver, x, result)
        problem = getattr(outer_solver, "problem", None)
        mapper = getattr(problem, "evaluate_from_inner_result", None) if problem is not None else None
        if callable(mapper):
            mapped = mapper(x, dict(result.payload or {}), {"status": result.status, "cost_units": result.cost_units})
            if isinstance(mapped, tuple) and len(mapped) == 2:
                return np.asarray(mapped[0], dtype=float).reshape(-1), float(mapped[1])
            return np.asarray(mapped, dtype=float).reshape(-1), float(result.violation)
        return result.objectives, float(result.violation)


@dataclass(frozen=True)
class InnerRuntimeConfig:
    source_layer: str = "L2"
    target_layer: str = "L1"
    fallback_penalty: float = 1e6
    warn_on_failure: bool = True
    per_call_timeout_ms: Optional[int] = None
    max_retries: int = 0
    retry_backoff_ms: float = 0.0


class TaskInnerRuntimeEvaluator(InnerRuntimeEvaluator):
    """Problem-side evaluator compatible with legacy build_inner_task pipeline."""

    def __init__(
        self,
        *,
        config: Optional[InnerRuntimeConfig] = None,
        inner_problem_factory: Optional[InnerProblemFactory] = None,
        inner_solver_factory: Optional[InnerSolverFactory] = None,
        inner_backend_factory: Optional[InnerBackendFactory] = None,
        inner_runner: Optional[InnerRunner] = None,
    ) -> None:
        cfg = config or InnerRuntimeConfig()
        super().__init__(
            solver_factory=inner_solver_factory,
            parent_contract="outer.default",
            accepted_parent_contracts=("outer.default",),
            default_budget_units=1.0,
        )
        self.cfg = cfg
        self.inner_problem_factory = inner_problem_factory
        self.inner_solver_factory = inner_solver_factory
        self.inner_backend_factory = inner_backend_factory
        self.inner_runner = inner_runner
        self.stats.update({"success": 0.0, "failure": 0.0, "blocked": 0.0, "fallback": 0.0, "retries": 0.0, "timeouts": 0.0})

    def can_handle(self, *, solver: Any, x: np.ndarray) -> bool:
        problem = getattr(solver, "problem", None)
        if problem is None:
            return False
        if callable(getattr(problem, "build_inner_task", None)):
            return True
        if callable(self.inner_problem_factory):
            return True
        return callable(getattr(problem, "build_inner_problem", None)) or callable(getattr(problem, "build_inner_solver", None))

    def evaluate(
        self,
        *,
        solver: Any,
        x: np.ndarray,
        individual_id: int,
        context: Mapping[str, Any] | None = None,
    ) -> Optional[tuple[np.ndarray, float]]:
        if not self.can_handle(solver=solver, x=x):
            return None
        candidate = np.asarray(x, dtype=float).reshape(-1)
        eval_ctx: Dict[str, Any] = {
            "solver": solver,
            "candidate": candidate,
            "individual_id": int(individual_id),
            "generation": int(getattr(solver, "generation", 0)),
            "scope": "inner",
            "source_layer": self.cfg.source_layer,
            "target_layer": self.cfg.target_layer,
        }
        task = self._build_task(solver, candidate, eval_ctx)
        if not task:
            return None

        self.stats["calls"] = float(self.stats.get("calls", 0.0) or 0.0) + 1.0
        guard = solver.plugin_manager.dispatch("on_inner_guard", solver, dict(eval_ctx))
        if isinstance(guard, Mapping) and not bool(guard.get("allow", True)):
            self.stats["blocked"] = float(self.stats.get("blocked", 0.0) or 0.0) + 1.0
            return self._fallback(solver)

        attempts = max(1, int(self.cfg.max_retries) + 1)
        inner_result: Optional[Dict[str, Any]] = None
        last_exc: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                inner_result = self._run_task_with_timeout(task, eval_ctx)
                break
            except Exception as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    self.stats["retries"] = float(self.stats.get("retries", 0.0) or 0.0) + 1.0
                    backoff_ms = float(self.cfg.retry_backoff_ms)
                    if backoff_ms > 0:
                        time.sleep(backoff_ms / 1000.0)
        if inner_result is None:
            self.stats["failure"] = float(self.stats.get("failure", 0.0) or 0.0) + 1.0
            if self.cfg.warn_on_failure:
                print(f"[inner-runtime] failed: {last_exc}")
            self.stats["fallback"] = float(self.stats.get("fallback", 0.0) or 0.0) + 1.0
            return self._fallback(solver)

        status = str(inner_result.get("status", "ok"))
        success = status.lower() in {"ok", "success", "completed"}
        if success:
            self.stats["success"] = float(self.stats.get("success", 0.0) or 0.0) + 1.0
        else:
            self.stats["failure"] = float(self.stats.get("failure", 0.0) or 0.0) + 1.0

        packet = {
            "source_layer": self.cfg.source_layer,
            "target_layer": self.cfg.target_layer,
            "candidate_id": int(individual_id),
            "generation": int(getattr(solver, "generation", 0)),
            "result": dict(inner_result),
            "status": status,
        }
        solver.plugin_manager.dispatch("on_inner_result", solver, packet)
        problem = getattr(solver, "problem", None)
        mapper = getattr(problem, "evaluate_from_inner_result", None) if problem is not None else None
        if callable(mapper):
            mapped = mapper(candidate, inner_result, eval_ctx)
        else:
            mapped = inner_result.get("objectives", inner_result.get("objective", self.cfg.fallback_penalty))
        if isinstance(mapped, tuple) and len(mapped) == 2:
            return np.asarray(mapped[0], dtype=float).reshape(-1), float(mapped[1])
        violation = float(inner_result.get("violation", 0.0))
        return np.asarray(mapped, dtype=float).reshape(-1), violation

    def _build_task(self, solver: Any, x: np.ndarray, eval_ctx: Dict[str, Any]) -> Dict[str, Any]:
        task: Dict[str, Any] = {}
        problem = getattr(solver, "problem", None)
        if callable(self.inner_problem_factory):
            task["inner_problem"] = self.inner_problem_factory(x, eval_ctx)
        else:
            hook = getattr(problem, "build_inner_problem", None) if problem is not None else None
            if callable(hook):
                task["inner_problem"] = hook(x, eval_ctx)
        if "inner_problem" in task:
            if callable(self.inner_solver_factory):
                task["inner_solver"] = self.inner_solver_factory(solver, InnerSolveRequest(candidate=x, outer_generation=int(eval_ctx["generation"]), outer_individual_id=int(eval_ctx["individual_id"])))
            else:
                hook = getattr(problem, "build_inner_solver", None) if problem is not None else None
                if callable(hook):
                    task["inner_solver"] = hook(task["inner_problem"], eval_ctx)
            if callable(self.inner_backend_factory):
                task["inner_backend"] = self.inner_backend_factory(task["inner_problem"], eval_ctx)
            else:
                hook = getattr(problem, "build_inner_backend", None) if problem is not None else None
                if callable(hook):
                    task["inner_backend"] = hook(task["inner_problem"], eval_ctx)
        if callable(self.inner_runner):
            task["run_inner"] = self.inner_runner
        else:
            hook = getattr(problem, "run_inner_solver", None) if problem is not None else None
            if callable(hook):
                task["run_inner"] = lambda p, s, c: hook(p, s, c)
        direct = getattr(problem, "build_inner_task", None) if problem is not None else None
        if callable(direct):
            payload = direct(x, eval_ctx)
            if isinstance(payload, Mapping):
                task.update(dict(payload))
        return task

    def _run_task(self, task: Dict[str, Any], eval_ctx: Dict[str, Any]) -> Dict[str, Any]:
        solver = eval_ctx["solver"]
        evaluator = task.get("evaluation_model")
        if evaluator is None:
            mediator = getattr(solver, "evaluation_mediator", None)
            providers = getattr(mediator, "list_providers", None) if mediator is not None else None
            if callable(providers):
                try:
                    for provider in providers():
                        if callable(getattr(provider, "evaluate_model", None)) and bool(
                            getattr(provider, "allow_inner", False)
                        ):
                            evaluator = provider
                            break
                except Exception:
                    evaluator = None
        if evaluator is None:
            pm = getattr(solver, "plugin_manager", None)
            if pm is not None and hasattr(pm, "list_plugins"):
                for plugin in pm.list_plugins(enabled_only=True):
                    if callable(getattr(plugin, "evaluate_model", None)) and bool(getattr(plugin, "allow_inner", False)):
                        evaluator = plugin
                        break
        if evaluator is not None and callable(getattr(evaluator, "evaluate_model", None)):
            from ..plugins.solver_backends.backend_contract import BackendSolveRequest, normalize_backend_output

            req = BackendSolveRequest(
                candidate=np.asarray(eval_ctx["candidate"], dtype=float).reshape(-1),
                eval_context=dict(eval_ctx),
                inner_problem=task.get("inner_problem"),
                inner_solver=task.get("inner_solver"),
                payload=dict(task),
            )
            out = evaluator.evaluate_model(solver, req)
            return dict(normalize_backend_output(out))
        backend = task.get("inner_backend")
        if backend is not None and callable(getattr(backend, "solve", None)):
            from ..plugins.solver_backends.backend_contract import BackendSolveRequest, normalize_backend_output

            req = BackendSolveRequest(
                candidate=np.asarray(eval_ctx["candidate"], dtype=float).reshape(-1),
                eval_context=dict(eval_ctx),
                inner_problem=task.get("inner_problem"),
                inner_solver=task.get("inner_solver"),
                payload=dict(task),
            )
            out = backend.solve(req)
            return dict(normalize_backend_output(out))
        run_inner = task.get("run_inner")
        if callable(run_inner):
            out = run_inner(task.get("inner_problem"), task.get("inner_solver"), eval_ctx)
            if isinstance(out, Mapping):
                return dict(out)
            raise TypeError("run_inner must return mapping")
        inner_solver = task.get("inner_solver")
        if inner_solver is None or not callable(getattr(inner_solver, "run", None)):
            raise RuntimeError("inner solver is not runnable")
        run = getattr(inner_solver, "run")
        supports_return_dict = False
        try:
            supports_return_dict = "return_dict" in inspect.signature(run).parameters
        except Exception:
            pass
        raw = run(return_dict=True) if supports_return_dict else run()
        return dict(raw) if isinstance(raw, Mapping) else {"status": "completed", "raw": raw}

    def _run_task_with_timeout(self, task: Dict[str, Any], eval_ctx: Dict[str, Any]) -> Dict[str, Any]:
        timeout_ms = self.cfg.per_call_timeout_ms
        if timeout_ms is None or float(timeout_ms) <= 0:
            return self._run_task(task, eval_ctx)
        timeout_s = float(timeout_ms) / 1000.0
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(self._run_task, task, eval_ctx)
            try:
                return fut.result(timeout=timeout_s)
            except FutureTimeoutError as exc:
                self.stats["timeouts"] = float(self.stats.get("timeouts", 0.0) or 0.0) + 1.0
                raise TimeoutError(f"inner task timeout after {timeout_ms} ms") from exc

    def _fallback(self, solver: Any) -> tuple[np.ndarray, float]:
        n_obj = int(getattr(solver, "num_objectives", 1))
        penalty = float(self.cfg.fallback_penalty)
        return np.full((n_obj,), penalty, dtype=float), penalty
