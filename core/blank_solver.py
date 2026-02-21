"""
Blank solver scaffold for custom workflows.

This class provides optional bias + representation integration without
enforcing any specific optimization loop.
"""

from __future__ import annotations

import time
import random
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .base import BlackBoxProblem
from .interfaces import BiasInterface, RepresentationInterface, load_bias_module, load_representation_pipeline
from ..utils.constraints.constraint_utils import evaluate_constraints_safe
from ..utils.context.context_keys import KEY_BEST_OBJECTIVE, KEY_BEST_X
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

        # Keep short-circuit hooks in capability layer.
        # - evaluate_population: plugin takeover (surrogate/cache/layered eval)
        # - evaluate_individual: per-candidate override
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
        self.random_seed: Optional[int] = None
        self._rng = np.random.default_rng()
        self._rng_streams: Dict[str, np.random.Generator] = {}

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
    # Control-plane wiring helpers (preferred over direct attribute writes)
    # ------------------------------------------------------------------
    def set_adapter(self, adapter: Any) -> None:
        setattr(self, "adapter", adapter)

    def set_bias_module(self, bias_module: Optional[BiasInterface], enable: Optional[bool] = None) -> None:
        self.bias_module = bias_module
        if enable is not None:
            self.enable_bias = bool(enable)
        elif bias_module is not None:
            self.enable_bias = True

    def set_enable_bias(self, enable: bool) -> None:
        self.enable_bias = bool(enable)

    def set_max_steps(self, max_steps: int) -> None:
        self.max_steps = int(max_steps)

    def set_solver_hyperparams(
        self,
        *,
        pop_size: Optional[int] = None,
        max_generations: Optional[int] = None,
        mutation_rate: Optional[float] = None,
        crossover_rate: Optional[float] = None,
    ) -> None:
        if pop_size is not None:
            setattr(self, "pop_size", int(pop_size))
        if max_generations is not None:
            setattr(self, "max_generations", int(max_generations))
        if mutation_rate is not None:
            setattr(self, "mutation_rate", float(mutation_rate))
        if crossover_rate is not None:
            setattr(self, "crossover_rate", float(crossover_rate))

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

    def write_population_snapshot(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> bool:
        pop = np.asarray(population, dtype=float)
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1) if pop.size > 0 else pop.reshape(0, 0)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1) if obj.size > 0 else obj.reshape(0, 0)
        if obj.shape[0] != pop.shape[0] or vio.shape[0] != pop.shape[0]:
            return False
        self.population = pop
        self.objectives = obj
        self.constraint_violations = vio
        return True

    def set_random_seed(self, seed: Optional[int]) -> None:
        self.random_seed = None if seed is None else int(seed)
        self._rng = np.random.default_rng(self.random_seed)
        self._rng_streams = {}
        if self.random_seed is not None:
            try:
                random.seed(self.random_seed)
            except Exception:
                pass

    def fork_rng(self, stream: str = "") -> np.random.Generator:
        key = str(stream or "_default")
        existing = self._rng_streams.get(key)
        if existing is not None:
            return existing
        child_seed = int(self._rng.integers(0, 2**63 - 1))
        child = np.random.default_rng(child_seed)
        self._rng_streams[key] = child
        return child

    def get_rng_state(self) -> Dict[str, Any]:
        return {"bit_generator_state": self._rng.bit_generator.state}

    def set_rng_state(self, state: Dict[str, Any]) -> None:
        if not isinstance(state, dict):
            return
        bit_state = state.get("bit_generator_state")
        if bit_state is None:
            return
        try:
            self._rng.bit_generator.state = bit_state
        except Exception:
            return
        self._rng_streams = {}

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
        best_x, best_obj = self._resolve_best_snapshot()
        ctx[KEY_BEST_X] = best_x
        ctx[KEY_BEST_OBJECTIVE] = best_obj
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
        for key, value in self._collect_runtime_context_projection().items():
            if value is None:
                continue
            ctx[key] = value
        best_x, best_obj = self._resolve_best_snapshot()
        ctx[KEY_BEST_X] = best_x
        ctx[KEY_BEST_OBJECTIVE] = best_obj
        return ctx

    def _resolve_best_snapshot(self) -> Tuple[Optional[Any], Optional[float]]:
        best_x = getattr(self, "best_x", None)
        best_obj = getattr(self, "best_objective", None)

        if best_obj is None:
            best_f = getattr(self, "best_f", None)
            if best_f is not None:
                try:
                    best_obj = float(best_f)
                except Exception:
                    best_obj = None

        if best_obj is None and self.objectives is not None:
            try:
                obj = np.asarray(self.objectives, dtype=float)
                if obj.size > 0:
                    if obj.ndim == 1:
                        best_obj = float(np.min(obj))
                    else:
                        scores = np.sum(obj, axis=1)
                        if self.constraint_violations is not None:
                            vio = np.asarray(self.constraint_violations, dtype=float).reshape(-1)
                            if vio.shape[0] == scores.shape[0]:
                                scores = scores + vio * 1e6
                        best_idx = int(np.argmin(scores))
                        best_obj = float(scores[best_idx])
                        if best_x is None and self.population is not None:
                            pop = np.asarray(self.population)
                            if pop.ndim >= 2 and best_idx < pop.shape[0]:
                                best_x = pop[best_idx]
            except Exception:
                pass

        return best_x, best_obj

    def _collect_runtime_context_projection(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        projection_writers: Dict[str, str] = {}

        adapter = getattr(self, "adapter", None)
        if adapter is not None:
            projector = getattr(adapter, "get_runtime_context_projection", None)
            source_getter = getattr(adapter, "get_runtime_context_projection_sources", None)
            if callable(projector):
                try:
                    proj = projector(self)
                except Exception:
                    proj = None
                try:
                    proj_sources = source_getter(self) if callable(source_getter) else {}
                except Exception:
                    proj_sources = {}
                if not isinstance(proj_sources, dict):
                    proj_sources = {}
                if isinstance(proj, dict):
                    for key, value in proj.items():
                        if key is None or value is None:
                            continue
                        key_str = str(key)
                        out[key_str] = value
                        source = proj_sources.get(key_str)
                        if source:
                            projection_writers[key_str] = str(source)
                        else:
                            projection_writers[key_str] = f"adapter.{adapter.__class__.__name__}"

        setattr(self, "_runtime_projection_writers", projection_writers)
        return out

    def evaluate_individual(self, x: np.ndarray, individual_id: Optional[int] = None) -> Tuple[np.ndarray, float]:
        overridden = self.plugin_manager.trigger("evaluate_individual", self, x, individual_id)
        if overridden is not None:
            try:
                obj, vio = overridden
            except Exception as exc:  # pragma: no cover
                raise ContractError("evaluate_individual plugin return must be (objectives, violation)") from exc
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
                raise ContractError("evaluate_population plugin return must be (objectives, violations)") from exc
            objectives = np.asarray(objectives, dtype=float)
            violations = np.asarray(violations, dtype=float).ravel()
            if objectives.ndim != 2 or objectives.shape[1] != self.num_objectives:
                raise ContractError(
                    f"plugin.evaluate_population.objectives shape mismatch: got {tuple(objectives.shape)} expected (N, {self.num_objectives})"
                )
            if violations.shape[0] != objectives.shape[0]:
                raise ContractError(
                    f"plugin.evaluate_population.violations length mismatch: got {int(violations.shape[0])} expected {int(objectives.shape[0])}"
                )
            return objectives, violations

        if population is None:
            raise ContractError("evaluate_population.population cannot be empty")
        population = np.asarray(population)
        if population.ndim == 1:
            population = population.reshape(1, -1)
        if population.ndim != 2 or population.shape[1] != self.dimension:
            raise ContractError(
                f"evaluate_population.population shape mismatch: got {tuple(population.shape)} expected (N, {self.dimension})"
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

        resume_loaded = bool(getattr(self, "_resume_loaded", False))
        if resume_loaded:
            start_step = int(getattr(self, "_resume_cursor", getattr(self, "generation", 0)))
            start_step = max(0, start_step)
            try:
                self.evaluation_count = int(getattr(self, "evaluation_count", 0))
            except Exception:
                self.evaluation_count = 0
        else:
            start_step = 0
            self.generation = 0
            self.evaluation_count = 0
        setattr(self, "_resume_loaded", False)
        setattr(self, "_resume_cursor", 0)

        executed_steps = 0
        for step_idx in range(start_step, steps):
            if self.stop_requested:
                break
            self.generation = step_idx
            self.plugin_manager.on_generation_start(self.generation)
            self.step()
            self.plugin_manager.on_generation_end(self.generation)
            executed_steps += 1

        self.teardown()
        elapsed = time.time() - self.start_time
        if executed_steps > 0:
            total_steps = int(self.generation + 1)
        else:
            total_steps = int(start_step)
        result = {
            "status": "stopped" if self.stop_requested else "completed",
            "steps": total_steps,
            "steps_executed": int(executed_steps),
            "resume_from": int(start_step) if resume_loaded else 0,
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
        return self._rng.uniform(lows, highs, size=self.dimension)
