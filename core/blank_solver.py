"""
Blank solver scaffold for custom workflows.

This class provides optional bias + representation integration without
enforcing any specific optimization loop.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .base import BlackBoxProblem
from .interfaces import BiasInterface, RepresentationInterface, load_bias_module, load_representation_pipeline
from ..utils.constraints.constraint_utils import evaluate_constraints_safe
from ..utils.extension_contracts import (
    ContractError,
    normalize_bias_output,
    normalize_candidate,
    normalize_objectives,
    normalize_violation,
    stack_population,
)
from ..plugins import PluginManager


class BlankSolverBase:
    """
    A minimal solver base that keeps the framework contracts intact.

    - Uses BlackBoxProblem for evaluation.
    - Optional bias_module and representation_pipeline.
    - No built-in optimization loop (step() is user/plugin defined).
    """

    def __init__(
        self,
        problem: BlackBoxProblem,
        bias_module: Optional[BiasInterface] = None,
        representation_pipeline: Optional[RepresentationInterface] = None,
        ignore_constraint_violation_when_bias: bool = False,
    ) -> None:
        self.problem = problem
        self.dimension = problem.dimension
        self.num_objectives = problem.get_num_objectives()
        self.var_bounds = problem.bounds

        self._bias_module_internal: Optional[BiasInterface] = None
        self.bias_module = bias_module
        self.enable_bias = bias_module is not None
        # If True, constraint violations will be ignored (set to 0) when bias is enabled.
        # Use only when constraints are fully handled by representation repair and/or bias penalties.
        self.ignore_constraint_violation_when_bias = bool(ignore_constraint_violation_when_bias)

        self._representation_internal: Optional[RepresentationInterface] = None
        self.representation_pipeline = representation_pipeline

        # 为“能力层”预留短路事件：
        # - evaluate_population: 允许插件接管评估（例如 surrogate/缓存/分层评估）
        # - evaluate_individual: 允许单点评估覆盖（更细粒度）
        self.plugin_manager = PluginManager(
            short_circuit=True,
            short_circuit_events=["evaluate_population", "evaluate_individual"],
        )

        self.population = None
        self.objectives = None
        self.constraint_violations = None

        self.generation = 0
        self.evaluation_count = 0
        self.running = False
        self.stop_requested = False
        self.max_steps = 1
        self.start_time = 0.0

    # ------------------------------------------------------------------
    # Optional dependency accessors (mirrors core solver behavior)
    # ------------------------------------------------------------------
    @property
    def bias_module(self) -> Optional[BiasInterface]:
        if self._bias_module_internal is not None:
            return self._bias_module_internal
        if self.enable_bias:
            if not hasattr(self, "_bias_module_cached"):
                self._bias_module_cached = load_bias_module()
            return self._bias_module_cached
        return None

    @bias_module.setter
    def bias_module(self, value: Optional[BiasInterface]) -> None:
        self._bias_module_internal = value
        if value is not None:
            self.enable_bias = True
            if hasattr(self, "_bias_module_cached"):
                delattr(self, "_bias_module_cached")

    @property
    def representation_pipeline(self) -> Optional[RepresentationInterface]:
        if self._representation_internal is not None:
            return self._representation_internal
        if not hasattr(self, "_representation_cached"):
            self._representation_cached = load_representation_pipeline()
        return self._representation_cached

    @representation_pipeline.setter
    def representation_pipeline(self, value: Optional[RepresentationInterface]) -> None:
        self._representation_internal = value
        if value is not None and hasattr(self, "_representation_cached"):
            delattr(self, "_representation_cached")

    def enable_bias_module(self, enable: bool = True) -> None:
        self.enable_bias = enable
        if enable and self._bias_module_internal is None:
            self._bias_module_internal = load_bias_module()

    # ------------------------------------------------------------------
    # Plugin helpers
    # ------------------------------------------------------------------
    def add_plugin(self, plugin: Any) -> "BlankSolverBase":
        self.plugin_manager.register(plugin)
        return self

    def remove_plugin(self, plugin_name: str) -> None:
        self.plugin_manager.unregister(plugin_name)

    def get_plugin(self, plugin_name: str) -> Any:
        return self.plugin_manager.get(plugin_name)

    # ------------------------------------------------------------------
    # Representation helpers (optional)
    # ------------------------------------------------------------------
    def init_candidate(self, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        pipeline = self.representation_pipeline
        if pipeline is not None:
            cand = pipeline.init(self.problem, context)
        else:
            cand = self._random_candidate()
        return normalize_candidate(cand, dimension=self.dimension, name="init_candidate")

    def mutate_candidate(self, x: np.ndarray, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        pipeline = self.representation_pipeline
        if pipeline is not None and getattr(pipeline, "mutator", None) is not None:
            out = pipeline.mutate(x, context)
        else:
            out = x
        return normalize_candidate(out, dimension=self.dimension, name="mutate_candidate")

    def repair_candidate(self, x: np.ndarray, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        pipeline = self.representation_pipeline
        if pipeline is not None and getattr(pipeline, "repair", None) is not None:
            out = pipeline.repair.repair(x, context)
        else:
            out = x
        return normalize_candidate(out, dimension=self.dimension, name="repair_candidate")

    def encode_candidate(self, x: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        pipeline = self.representation_pipeline
        if pipeline is not None and getattr(pipeline, "encoder", None) is not None:
            return pipeline.encode(x, context)
        return x

    def decode_candidate(self, x: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        pipeline = self.representation_pipeline
        if pipeline is not None and getattr(pipeline, "encoder", None) is not None:
            return pipeline.decode(x, context)
        return x

    def initialize_population(
        self,
        pop_size: Optional[int] = None,
        evaluate: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        size = int(pop_size or getattr(self, "pop_size", 0) or self.max_steps)
        population = []
        for _ in range(size):
            population.append(self.init_candidate(context))
        self.population = stack_population(population, name="initialize_population.population")

        if evaluate:
            self.objectives, self.constraint_violations = self.evaluate_population(self.population)
            self.plugin_manager.on_population_init(
                self.population, self.objectives, self.constraint_violations
            )
        return self.population

    # ------------------------------------------------------------------
    # Evaluation helpers
    # ------------------------------------------------------------------
    def build_context(
        self,
        individual_id: Optional[int] = None,
        constraints: Optional[np.ndarray] = None,
        violation: Optional[float] = None,
        individual: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        ctx = {
            "problem": self.problem,
            "generation": self.generation,
            "population": self.population if self.population is not None else [],
            "objectives": self.objectives if self.objectives is not None else [],
            "constraints": (constraints.tolist() if constraints is not None else []),
            "constraint_violation": float(violation or 0.0),
            "individual_id": individual_id,
        }
        if individual is not None:
            ctx["individual"] = individual
        dynamic = getattr(self, "dynamic_signals", None)
        if dynamic is not None:
            ctx["dynamic"] = dynamic
        phase_id = getattr(self, "dynamic_phase_id", None)
        if phase_id is not None:
            ctx["phase_id"] = phase_id
        # allow plugins to inject extra context fields
        if getattr(self, "plugin_manager", None) is not None:
            try:
                ctx = self.plugin_manager.dispatch("on_context_build", ctx) or ctx
            except Exception:
                pass
        return ctx

    def get_context(self) -> Dict[str, Any]:
        """Return a snapshot context for visualization/monitoring."""
        ctx = self.build_context()
        ctx["population"] = self.population if self.population is not None else []
        ctx["objectives"] = self.objectives if self.objectives is not None else []
        ctx["constraint_violations"] = self.constraint_violations if self.constraint_violations is not None else []
        ctx["evaluation_count"] = int(getattr(self, "evaluation_count", 0))
        return ctx

    def evaluate_individual(self, x: np.ndarray, individual_id: Optional[int] = None) -> Tuple[np.ndarray, float]:
        overridden = self.plugin_manager.trigger("evaluate_individual", self, x, individual_id)
        if overridden is not None:
            try:
                obj, vio = overridden
            except Exception as exc:  # pragma: no cover
                raise ContractError("evaluate_individual 插件返回值必须是 (objectives, violation)") from exc
            obj = normalize_objectives(obj, num_objectives=self.num_objectives, name="plugin.evaluate_individual.objectives")
            vio = normalize_violation(vio, name="plugin.evaluate_individual.violation")
            self.evaluation_count += 1
            return obj, vio

        x = normalize_candidate(x, dimension=self.dimension, name="evaluate_individual.x")
        val = self.problem.evaluate(x)
        obj = normalize_objectives(val, num_objectives=self.num_objectives, name="problem.evaluate")
        cons_arr, violation = evaluate_constraints_safe(self.problem, x)
        violation = normalize_violation(violation, name="constraint_violation")
        context = self.build_context(
            individual_id=individual_id,
            constraints=cons_arr,
            violation=violation,
            individual=x,
        )

        if self.enable_bias and self.bias_module is not None:
            obj = self._apply_bias(obj, x, individual_id, context)
            if self.ignore_constraint_violation_when_bias:
                violation = 0.0

        self.evaluation_count += 1
        return obj, violation

    def evaluate_population(self, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        overridden = self.plugin_manager.trigger("evaluate_population", self, population)
        if overridden is not None:
            try:
                objectives, violations = overridden
            except Exception as exc:  # pragma: no cover
                raise ContractError("evaluate_population 插件返回值必须是 (objectives, violations)") from exc
            objectives = np.asarray(objectives, dtype=float)
            violations = np.asarray(violations, dtype=float).ravel()
            if objectives.ndim != 2 or objectives.shape[1] != self.num_objectives:
                raise ContractError(
                    f"plugin.evaluate_population.objectives shape 错误: got {tuple(objectives.shape)} expected (N, {self.num_objectives})"
                )
            if violations.shape[0] != objectives.shape[0]:
                raise ContractError(
                    f"plugin.evaluate_population.violations 长度不匹配: got {int(violations.shape[0])} expected {int(objectives.shape[0])}"
                )
            return objectives, violations

        if population is None:
            raise ContractError("evaluate_population.population 不能为空")
        population = np.asarray(population)
        if population.ndim == 1:
            population = population.reshape(1, -1)
        if population.ndim != 2 or population.shape[1] != self.dimension:
            raise ContractError(
                f"evaluate_population.population shape 错误: got {tuple(population.shape)} expected (N, {self.dimension})"
            )
        pop_size = int(population.shape[0])
        objectives = np.zeros((pop_size, self.num_objectives))
        violations = np.zeros(pop_size, dtype=float)

        for i in range(pop_size):
            obj, vio = self.evaluate_individual(population[i], individual_id=i)
            if obj.size == self.num_objectives:
                objectives[i] = obj
            elif obj.size > self.num_objectives:
                objectives[i] = obj[: self.num_objectives]
            else:
                objectives[i, : obj.size] = obj
            violations[i] = vio

        return objectives, violations

    def _apply_bias(
        self,
        obj: np.ndarray,
        x: np.ndarray,
        individual_id: Optional[int],
        context: Dict[str, Any],
    ) -> np.ndarray:
        bias_module = self.bias_module
        if bias_module is None:
            return obj
        if hasattr(bias_module, "compute_bias"):
            if obj.size == 1:
                biased = bias_module.compute_bias(x, float(obj[0]), individual_id, context=context)
                return np.array([normalize_bias_output(biased, name="bias.compute_bias")], dtype=float)
            out = []
            for i in range(obj.size):
                out.append(
                    normalize_bias_output(
                        bias_module.compute_bias(x, float(obj[i]), individual_id, context=context),
                        name="bias.compute_bias",
                    )
                )
            return np.asarray(out, dtype=float)
        return obj

    # ------------------------------------------------------------------
    # Minimal runtime loop (override step() for custom logic)
    # ------------------------------------------------------------------
    def request_stop(self) -> None:
        self.stop_requested = True

    def setup(self) -> None:
        return None

    def step(self) -> None:
        self.plugin_manager.on_step(self, self.generation)
        return None

    def teardown(self) -> None:
        return None

    def run(self, max_steps: Optional[int] = None) -> Dict[str, Any]:
        steps = int(max_steps if max_steps is not None else self.max_steps)
        self.running = True
        self.stop_requested = False
        self.start_time = time.time()

        self.plugin_manager.on_solver_init(self)
        self.setup()

        for step_idx in range(steps):
            if self.stop_requested:
                break
            self.generation = step_idx
            self.plugin_manager.on_generation_start(self.generation)
            self.step()
            self.plugin_manager.on_generation_end(self.generation)

        self.teardown()
        elapsed = time.time() - self.start_time
        result = {
            "status": "stopped" if self.stop_requested else "completed",
            "steps": self.generation + 1 if steps > 0 else 0,
            "elapsed_sec": elapsed,
        }
        self.plugin_manager.on_solver_finish(result)
        self.running = False
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _random_candidate(self) -> np.ndarray:
        if isinstance(self.var_bounds, dict):
            var_names = list(getattr(self.problem, "variables", self.var_bounds.keys()))
            lows = np.array([self.var_bounds[n][0] for n in var_names], dtype=float)
            highs = np.array([self.var_bounds[n][1] for n in var_names], dtype=float)
        else:
            bounds = np.asarray(self.var_bounds, dtype=float)
            lows = bounds[:, 0]
            highs = bounds[:, 1]
        return np.random.uniform(lows, highs, size=self.dimension)
