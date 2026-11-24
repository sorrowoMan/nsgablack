"""Problem-level inner-runtime evaluation contract (not L4 provider)."""

from __future__ import annotations

import inspect
import operator
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

import numpy as np

from blackbase.project import (
    CaseInvocationError,
    CaseRunResult,
    CaseStage,
    CaseStageRunner,
    ChildCaseCall,
)
from blackbase.resources import TerminationPolicy
from blackbase.types import Feedback


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
CaseResultProjector = Callable[[Any, np.ndarray, CaseRunResult], tuple[np.ndarray, float] | Feedback]
CaseOverridesFactory = Callable[[Any, np.ndarray, Mapping[str, Any]], Mapping[str, Any]]


class ChildCaseExecutionError(CaseInvocationError):
    """Raised when a complete child Case returns a failed result envelope."""

    def __init__(self, result: CaseRunResult) -> None:
        super().__init__(result, message="inner Solver Case failed")


class CaseInnerRuntimeEvaluator:
    """Evaluate an outer candidate by invoking one complete standard child Case.

    This is the lineage/resource/budget/cancellation-safe path.  Projection is
    deliberately mandatory because child Solver objectives are not implicitly
    equivalent to the outer problem's objectives.
    """

    def __init__(
        self,
        *,
        case_name: str,
        projector: CaseResultProjector,
        case_kind: str = "solver",
        stage_name: str = "inner_evaluation",
        candidate_input: str = "candidate",
        resource_request: Mapping[str, Any] | None = None,
        budget_request: Mapping[str, int] | None = None,
        component_overrides: Mapping[str, Any] | None = None,
        component_overrides_factory: CaseOverridesFactory | None = None,
        timeout_seconds: float | None = None,
        termination: TerminationPolicy | Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        max_workers: int = 1,
        artifact_bindings: Mapping[str, str] | None = None,
    ) -> None:
        if not str(case_name or "").strip():
            raise ValueError("CaseInnerRuntimeEvaluator case_name must be non-empty")
        if not callable(projector):
            raise TypeError("CaseInnerRuntimeEvaluator requires an explicit projector")
        if component_overrides_factory is not None and not callable(component_overrides_factory):
            raise TypeError("component_overrides_factory must be callable")
        if artifact_bindings is not None and not isinstance(artifact_bindings, Mapping):
            raise TypeError("artifact_bindings must map child input names to parent input names")
        bindings = dict(artifact_bindings or {})
        if any(not isinstance(value, str) or not value.strip()
               for pair in bindings.items() for value in pair):
            raise ValueError("artifact_bindings requires non-empty string input names")
        if isinstance(max_workers, bool):
            raise ValueError("max_workers must be a positive integer")
        try:
            workers = operator.index(max_workers)
        except TypeError as exc:
            raise ValueError("max_workers must be a positive integer") from exc
        if workers < 1:
            raise ValueError("max_workers must be a positive integer")
        self.case_name = str(case_name)
        self.projector = projector
        self.case_kind = str(case_kind or "solver")
        self.stage_name = str(stage_name or "inner_evaluation")
        self.candidate_input = str(candidate_input or "candidate")
        self.resource_request = dict(resource_request or {})
        self.budget_request = {str(key): int(value) for key, value in dict(budget_request or {}).items()}
        self.component_overrides = dict(component_overrides or {})
        self.component_overrides_factory = component_overrides_factory
        self.timeout_seconds = timeout_seconds
        self.termination = (
            None if termination is None else termination
            if isinstance(termination, TerminationPolicy)
            else TerminationPolicy.from_dict(termination)
        )
        self.metadata = dict(metadata or {})
        self.max_workers = workers
        self.artifact_bindings = bindings
        self.stats: Dict[str, Any] = {
            "calls": 0,
            "success": 0,
            "failures": 0,
            "last_case_run_id": "",
        }
        self.last_result: CaseRunResult | None = None
        self.last_batch_results: tuple[CaseRunResult, ...] = ()

    def can_handle(self, *, solver: Any, x: np.ndarray) -> bool:
        del x
        runtime = getattr(solver, "case_runtime", None)
        return callable(getattr(runtime, "invoke", None)) and callable(
            getattr(runtime, "checkpoint", None)
        )

    def evaluate(
        self,
        *,
        solver: Any,
        x: np.ndarray,
        individual_id: int,
        context: Mapping[str, Any] | None = None,
    ) -> tuple[np.ndarray, float] | Feedback:
        runtime = getattr(solver, "case_runtime", None)
        candidate, call = self._prepare_call(solver, x, individual_id, context)
        stage_result = CaseStageRunner(
            runtime,
            (CaseStage(self.stage_name, (call,)),),
            artifact_bindings=runtime.request.input_artifact_bindings,
        ).run()[0]
        result = stage_result.results[call.name]
        self.last_batch_results = (result,)
        return self._project_case_result(solver, candidate, result)

    def evaluate_batch(
        self,
        *,
        solver: Any,
        population: np.ndarray,
        contexts: Sequence[Mapping[str, Any]] | None = None,
    ) -> tuple[tuple[np.ndarray, float] | Feedback, ...]:
        """Dispatch standard child Cases together and project in input order.

        Project L0 owns effective concurrency and local/external placement. Only
        child execution is concurrent; configuration factories and projectors
        run on the caller thread. No partial batch is delivered on failure.
        """
        values = np.asarray(population, dtype=float)
        if values.ndim != 2:
            raise ValueError("inner Case batch population must be a 2-D array")
        if contexts is not None and len(contexts) != len(values):
            raise ValueError("inner Case batch contexts must align with population")
        self.last_batch_results = ()
        if not len(values):
            return ()
        prepared = tuple(
            self._prepare_call(
                solver, row, index, None if contexts is None else contexts[index]
            )
            for index, row in enumerate(values)
        )
        runtime = getattr(solver, "case_runtime", None)
        stage = CaseStage(
            self.stage_name,
            tuple(call for _candidate, call in prepared),
            policy="parallel" if self.max_workers > 1 else "serial",
            max_workers=self.max_workers,
        )
        stage_result = CaseStageRunner(
            runtime, (stage,), artifact_bindings=runtime.request.input_artifact_bindings,
        ).run()[0]
        self.last_batch_results = tuple(
            stage_result.results[call.name]
            for _candidate, call in prepared if call.name in stage_result.results
        )
        # Validate the complete execution barrier before invoking user
        # projectors, which may themselves record observations.
        for result in self.last_batch_results:
            if not result.ok:
                self.last_result = result
                self.stats["calls"] += len(self.last_batch_results)
                self.stats["failures"] += sum(
                    not item.ok for item in self.last_batch_results
                )
                self.stats["last_case_run_id"] = result.identity.case_run_id
                raise ChildCaseExecutionError(result)
        if len(self.last_batch_results) != len(prepared):
            raise RuntimeError("inner Case batch did not return every requested result")
        return tuple(
            self._project_case_result(solver, candidate, result)
            for (candidate, _call), result in zip(prepared, self.last_batch_results)
        )

    def _prepare_call(
        self,
        solver: Any,
        x: np.ndarray,
        individual_id: int,
        context: Mapping[str, Any] | None,
    ) -> tuple[np.ndarray, ChildCaseCall]:
        if not self.can_handle(solver=solver, x=x):
            raise RuntimeError(
                "CaseInnerRuntimeEvaluator requires a Solver executed through the "
                "standard Project/Case substrate"
            )
        candidate = np.asarray(x, dtype=float).reshape(-1)
        ctx = dict(context or {})
        inputs = {
            self.candidate_input: candidate.tolist(),
            "outer_generation": int(getattr(solver, "generation", 0)),
            "outer_individual_id": int(individual_id),
            "context": ctx,
        }
        # Preserve an already-bound identity; a row index or equal values must
        # never be used to infer which proposal is being evaluated.
        provenance_getter = getattr(solver, "candidate_provenance_for", None)
        provenance = provenance_getter(x) if callable(provenance_getter) else None
        factory_context = dict(ctx)
        if provenance is not None:
            inputs["candidate_provenance"] = provenance.as_dict()
            factory_context["_candidate_provenance"] = provenance.as_dict()
        overrides = dict(self.component_overrides)
        if self.component_overrides_factory is not None:
            readonly = np.frombuffer(candidate.tobytes(), dtype=candidate.dtype).reshape(candidate.shape)
            dynamic = self.component_overrides_factory(solver, readonly, factory_context)
            if not isinstance(dynamic, Mapping):
                raise TypeError("component_overrides_factory must return a Mapping")
            overrides.update(dict(dynamic))
        call = ChildCaseCall(
            name=f"candidate_{int(individual_id)}",
            case_name=self.case_name,
            case_kind=self.case_kind,
            resource_request=self.resource_request,
            budget_request=self.budget_request,
            component_overrides=overrides,
            artifact_bindings=self.artifact_bindings,
            inputs=inputs,
            timeout_seconds=self.timeout_seconds,
            termination=self.termination,
            metadata={
                **self.metadata,
                "source": "nsgablack.CaseInnerRuntimeEvaluator",
            },
        )
        return candidate, call

    def _project_case_result(
        self, solver: Any, candidate: np.ndarray, result: CaseRunResult
    ) -> tuple[np.ndarray, float] | Feedback:
        self.last_result = result
        self.stats["calls"] = int(self.stats["calls"]) + 1
        self.stats["last_case_run_id"] = result.identity.case_run_id
        if not result.ok:
            self.stats["failures"] = int(self.stats["failures"]) + 1
            raise ChildCaseExecutionError(result)
        projected = self.projector(solver, candidate, result)
        if isinstance(projected, Feedback):
            self.stats["success"] = int(self.stats["success"]) + 1
            return projected
        if not isinstance(projected, tuple) or len(projected) != 2:
            raise TypeError("CaseInnerRuntimeEvaluator projector must return (objectives, violation) or Feedback")
        objectives = np.asarray(projected[0], dtype=float).reshape(-1)
        violation = float(projected[1])
        self.stats["success"] = int(self.stats["success"]) + 1
        return objectives, violation


class InnerRuntimeEvaluator:
    """Low-level in-process component evaluator for nested solve semantics.

    It is not a complete child Case boundary.  Standard child Cases must use
    :class:`CaseInnerRuntimeEvaluator` so Project lineage and L0 grants remain
    authoritative.
    """

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
    """Low-level component evaluator for a problem's ``build_inner_task`` pipeline."""

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
        eval_ctx: Dict[str, Any] = dict(context or {})
        eval_ctx.update({
            "solver": solver,
            "candidate": candidate,
            "individual_id": int(individual_id),
            "generation": int(getattr(solver, "generation", 0)),
            "scope": "inner",
            "source_layer": self.cfg.source_layer,
            "target_layer": self.cfg.target_layer,
        })
        if not any(key in eval_ctx for key in ("resource_context", "resource.context", "resource")):
            getter = getattr(solver, "get_resource_context", None)
            resource_context = getter() if callable(getter) else getattr(solver, "resource_context", None)
            as_dict = getattr(resource_context, "as_dict", None)
            if callable(as_dict):
                eval_ctx["resource_context"] = dict(as_dict())
            elif isinstance(resource_context, Mapping):
                eval_ctx["resource_context"] = dict(resource_context)
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
            from ..plugins.domain_backends.backend_contract import BackendSolveRequest, normalize_backend_output

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
            from ..plugins.domain_backends.backend_contract import BackendSolveRequest, normalize_backend_output

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
        except (ValueError, TypeError):
            pass
        raw = run(return_dict=True) if supports_return_dict else run()
        return dict(raw) if isinstance(raw, Mapping) else {"status": "completed", "raw": raw}

    def _run_task_with_timeout(self, task: Dict[str, Any], eval_ctx: Dict[str, Any]) -> Dict[str, Any]:
        timeout_ms = self.cfg.per_call_timeout_ms
        if timeout_ms is None or float(timeout_ms) <= 0:
            return self._run_task(task, eval_ctx)
        timeout_s = float(timeout_ms) / 1000.0
        pool = ThreadPoolExecutor(max_workers=1)
        fut = pool.submit(self._run_task, task, eval_ctx)
        timed_out = False
        try:
            return fut.result(timeout=timeout_s)
        except FutureTimeoutError as exc:
            timed_out = True
            fut.cancel()
            self.stats["timeouts"] = float(self.stats.get("timeouts", 0.0) or 0.0) + 1.0
            raise TimeoutError(f"inner task timeout after {timeout_ms} ms") from exc
        finally:
            # Threads cannot be force-killed. On deadline, stop waiting and let a
            # cooperative/backend cancellation mechanism finish cleanup.
            pool.shutdown(wait=not timed_out, cancel_futures=True)

    def _fallback(self, solver: Any) -> tuple[np.ndarray, float]:
        n_obj = int(getattr(solver, "num_objectives", 1))
        penalty = float(self.cfg.fallback_penalty)
        return np.full((n_obj,), penalty, dtype=float), penalty
