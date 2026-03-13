"""Population-based evolutionary solver built on ComposableSolver + adapters."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np

from ..adapters import NSGA2Adapter, NSGA2Config
from .composable_solver import ComposableSolver
from ..utils.engineering.error_policy import report_soft_error
from ..utils.parallel.evaluator import ParallelEvaluator
from ..utils.performance.fast_non_dominated_sort import FastNonDominatedSort

_MIN_POP_FOR_PARALLEL = 1
logger = logging.getLogger(__name__)


class EvolutionSolver(ComposableSolver):
    """Canonical evolutionary solver with adapter-driven NSGA-II flow."""

    def __init__(
        self,
        problem: Any,
        *,
        bias_module: Any = None,
        representation_pipeline: Any = None,
        ignore_constraint_violation_when_bias: bool = False,
        plugin_strict: bool = False,
        snapshot_strict: bool = False,
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
        pop_size: int = 80,
        max_generations: int = 150,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.85,
        objective_aggregation: str = "sum",
        random_seed: Optional[int] = None,
        sbx_eta_c: float = 15.0,
        initial_mutation_range: float = 0.8,
        max_pareto_solutions: int = 50,
        enable_progress_log: bool = False,
        report_interval: int = 10,
        # Optional parallel options (kept for runtime ergonomics).
        enable_parallel: Optional[bool] = None,
        parallel: Optional[bool] = None,
        enable_parallel_evaluation: Optional[bool] = None,
        parallel_backend: Literal["process", "thread", "ray", "auto"] = "process",
        parallel_max_workers: Optional[int] = None,
        parallel_chunk_size: Optional[int] = None,
        parallel_load_balancing: bool = True,
        parallel_retry_errors: bool = True,
        parallel_max_retries: int = 3,
        parallel_verbose: bool = False,
        parallel_precheck: bool = True,
        parallel_strict: bool = False,
        parallel_fallback_backend: Literal["process", "thread", "ray"] = "thread",
        parallel_thread_bias_isolation: Literal["deepcopy", "disable_cache", "off"] = "deepcopy",
        parallel_problem_factory: Any = None,
        parallel_context_builder: Any = None,
        parallel_extra_context: Optional[Dict[str, Any]] = None,
        adapter: Optional[Any] = None,
        **_: Any,
    ) -> None:
        self.pop_size = int(pop_size)
        self.max_generations = int(max_generations)
        self.max_steps = int(max_generations)
        self.mutation_rate = float(mutation_rate)
        self.crossover_rate = float(crossover_rate)
        self.sbx_eta_c = float(sbx_eta_c)
        self.initial_mutation_range = float(initial_mutation_range)
        self.mutation_range = float(initial_mutation_range)
        self.max_pareto_solutions = int(max_pareto_solutions)
        self.enable_progress_log = bool(enable_progress_log)
        self.report_interval = int(report_interval)

        nsga2_cfg = NSGA2Config(
            population_size=self.pop_size,
            offspring_size=self.pop_size,
            crossover_rate=self.crossover_rate,
            objective_aggregation=str(objective_aggregation),
        )
        self._default_nsga2_adapter = NSGA2Adapter(config=nsga2_cfg)
        self._objective_aggregation = str(objective_aggregation)

        super().__init__(
            problem=problem,
            adapter=adapter if adapter is not None else self._default_nsga2_adapter,
            bias_module=bias_module,
            representation_pipeline=representation_pipeline,
            ignore_constraint_violation_when_bias=ignore_constraint_violation_when_bias,
            plugin_strict=bool(plugin_strict),
            snapshot_strict=bool(snapshot_strict),
            context_store_backend=context_store_backend,
            context_store_ttl_seconds=context_store_ttl_seconds,
            context_store_redis_url=context_store_redis_url,
            context_store_key_prefix=context_store_key_prefix,
            snapshot_store_backend=snapshot_store_backend,
            snapshot_store_ttl_seconds=snapshot_store_ttl_seconds,
            snapshot_store_redis_url=snapshot_store_redis_url,
            snapshot_store_key_prefix=snapshot_store_key_prefix,
            snapshot_store_dir=snapshot_store_dir,
            snapshot_store_serializer=snapshot_store_serializer,
            snapshot_store_hmac_env_var=snapshot_store_hmac_env_var,
            snapshot_store_unsafe_allow_unsigned=snapshot_store_unsafe_allow_unsigned,
            snapshot_store_max_payload_bytes=snapshot_store_max_payload_bytes,
            snapshot_schema=snapshot_schema,
        )

        self.history: List[Tuple[int, List[np.ndarray]]] = []
        self.pareto_solutions: Optional[Dict[str, np.ndarray]] = None
        self.pareto_objectives: Optional[np.ndarray] = None
        self.best_f: Optional[float] = None
        self.last_result: Dict[str, Any] = {}
        self.run_count: int = 0

        enabled_parallel = enable_parallel
        if enabled_parallel is None:
            enabled_parallel = parallel
        if enabled_parallel is None:
            enabled_parallel = enable_parallel_evaluation
        self.enable_parallel_evaluation = bool(enabled_parallel)
        self.parallel_evaluator: Optional[ParallelEvaluator] = None
        self._parallel_cfg = {
            "backend": parallel_backend,
            "max_workers": parallel_max_workers,
            "chunk_size": parallel_chunk_size,
            "enable_load_balancing": bool(parallel_load_balancing),
            "retry_errors": bool(parallel_retry_errors),
            "max_retries": int(parallel_max_retries),
            "verbose": bool(parallel_verbose),
            "precheck": bool(parallel_precheck),
            "strict": bool(parallel_strict),
            "fallback_backend": parallel_fallback_backend,
            "thread_bias_isolation": parallel_thread_bias_isolation,
            "problem_factory": parallel_problem_factory,
            "context_builder": parallel_context_builder,
            "extra_context": parallel_extra_context,
        }

        self.set_random_seed(random_seed)
        if bias_module is None:
            self.enable_bias = bool(getattr(self, "enable_bias", False))
        self._sync_nsga2_adapter_config()

    @property
    def representation_pipeline(self):
        """Use explicitly injected pipeline only; do not auto-load defaults."""
        return getattr(self, "_representation_internal", None)

    @representation_pipeline.setter
    def representation_pipeline(self, value):
        self._representation_internal = value

    def _sync_nsga2_adapter_config(self) -> None:
        adapter = getattr(self, "adapter", None)
        if not isinstance(adapter, NSGA2Adapter):
            return
        adapter.cfg.population_size = int(self.pop_size)
        adapter.cfg.offspring_size = int(self.pop_size)
        adapter.cfg.crossover_rate = float(self.crossover_rate)
        adapter.cfg.objective_aggregation = str(self._objective_aggregation)

    def set_adapter(self, adapter: Any) -> None:
        super().set_adapter(adapter)
        self._sync_nsga2_adapter_config()

    def set_solver_hyperparams(
        self,
        *,
        pop_size: Optional[int] = None,
        max_generations: Optional[int] = None,
        mutation_rate: Optional[float] = None,
        crossover_rate: Optional[float] = None,
    ) -> None:
        super().set_solver_hyperparams(
            pop_size=pop_size,
            max_generations=max_generations,
            mutation_rate=mutation_rate,
            crossover_rate=crossover_rate,
        )
        if pop_size is not None:
            self.pop_size = int(pop_size)
        if max_generations is not None:
            self.max_generations = int(max_generations)
            self.max_steps = int(max_generations)
        if mutation_rate is not None:
            self.mutation_rate = float(mutation_rate)
        if crossover_rate is not None:
            self.crossover_rate = float(crossover_rate)
        self._sync_nsga2_adapter_config()

    def set_context_store(self, store: Any) -> None:
        super().set_context_store(store)

    def set_snapshot_store(self, store: Any) -> None:
        super().set_snapshot_store(store)

    def set_context_store_backend(
        self,
        backend: str,
        *,
        ttl_seconds: Optional[float] = None,
        redis_url: Optional[str] = None,
        key_prefix: Optional[str] = None,
    ) -> None:
        super().set_context_store_backend(
            backend,
            ttl_seconds=ttl_seconds,
            redis_url=redis_url,
            key_prefix=key_prefix,
        )

    def set_snapshot_store_backend(
        self,
        backend: str,
        *,
        ttl_seconds: Optional[float] = None,
        redis_url: Optional[str] = None,
        key_prefix: Optional[str] = None,
        base_dir: Optional[str] = None,
        serializer: Optional[str] = None,
        hmac_env_var: Optional[str] = None,
        unsafe_allow_unsigned: Optional[bool] = None,
        max_payload_bytes: Optional[int] = None,
    ) -> None:
        super().set_snapshot_store_backend(
            backend,
            ttl_seconds=ttl_seconds,
            redis_url=redis_url,
            key_prefix=key_prefix,
            base_dir=base_dir,
            serializer=serializer,
            hmac_env_var=hmac_env_var,
            unsafe_allow_unsigned=unsafe_allow_unsigned,
            max_payload_bytes=max_payload_bytes,
        )

    def _ensure_parallel_evaluator(self) -> Optional[ParallelEvaluator]:
        if not self.enable_parallel_evaluation:
            return None
        if self.parallel_evaluator is not None:
            return self.parallel_evaluator
        cfg = self._parallel_cfg
        backend = cfg["backend"]
        if backend == "auto":
            from ..utils.parallel.evaluator import SmartEvaluatorSelector

            self.parallel_evaluator = SmartEvaluatorSelector.select_evaluator(
                getattr(self, "problem", None),
                getattr(self, "pop_size", 0) or 0,
            )
            for key, attr in (
                ("precheck", "precheck"),
                ("strict", "strict"),
                ("fallback_backend", "fallback_backend"),
                ("thread_bias_isolation", "thread_bias_isolation"),
                ("problem_factory", "problem_factory"),
                ("context_builder", "context_builder"),
                ("extra_context", "extra_context"),
            ):
                if hasattr(self.parallel_evaluator, attr):
                    try:
                        setattr(self.parallel_evaluator, attr, cfg[key])
                    except Exception as exc:
                        report_soft_error(
                            component="EvolutionSolver",
                            event=f"configure_parallel_evaluator.{attr}",
                            exc=exc,
                            logger=logger,
                            context_store=self.context_store,
                            strict=False,
                            level="debug",
                        )
            return self.parallel_evaluator

        self.parallel_evaluator = ParallelEvaluator(
            backend=backend,
            max_workers=cfg["max_workers"],
            chunk_size=cfg["chunk_size"],
            enable_load_balancing=cfg["enable_load_balancing"],
            retry_errors=cfg["retry_errors"],
            max_retries=cfg["max_retries"],
            verbose=cfg["verbose"],
            precheck=cfg["precheck"],
            strict=cfg["strict"],
            fallback_backend=cfg["fallback_backend"],
            thread_bias_isolation=cfg["thread_bias_isolation"],
            problem_factory=cfg["problem_factory"],
            context_builder=cfg["context_builder"],
            extra_context=cfg["extra_context"],
        )
        return self.parallel_evaluator

    def evaluate_population(self, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        evaluator = self._ensure_parallel_evaluator()
        if evaluator is not None:
            pop = np.asarray(population)
            if pop.ndim == 1:
                pop = pop.reshape(1, -1)
            if pop.shape[0] >= int(_MIN_POP_FOR_PARALLEL):
                objectives, violations = evaluator.evaluate_population(
                    population=pop,
                    problem=self.problem,
                    enable_bias=bool(getattr(self, "enable_bias", False)),
                    bias_module=getattr(self, "bias_module", None),
                    return_detailed=False,
                )
                return np.asarray(objectives, dtype=float), np.asarray(violations, dtype=float).reshape(-1)
        return super().evaluate_population(population)

    def initialize_population(
        self,
        pop_size: Optional[int] = None,
        evaluate: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        if pop_size is not None:
            self.pop_size = int(pop_size)
        self._sync_nsga2_adapter_config()
        population = super().initialize_population(pop_size=self.pop_size, evaluate=evaluate, context=context)
        if evaluate:
            self._sync_adapter_from_solver()
            self.update_pareto_solutions()
            if not self.history:
                self.record_history()
            self._refresh_best()
        return population

    def step(self) -> None:
        self._sync_nsga2_adapter_config()
        super().step()
        self._sync_solver_from_adapter()
        self.update_pareto_solutions()
        self.record_history()
        self._refresh_best()

    def _sync_adapter_from_solver(self) -> None:
        adapter = getattr(self, "adapter", None)
        if adapter is None:
            return
        setter = getattr(adapter, "set_population", None)
        if not callable(setter):
            return
        if self.population is None or self.objectives is None or self.constraint_violations is None:
            return
        try:
            setter(self.population, self.objectives, self.constraint_violations)
        except Exception as exc:
            report_soft_error(
                component="EvolutionSolver",
                event="sync_adapter_from_solver",
                exc=exc,
                logger=logger,
                context_store=self.context_store,
                strict=False,
            )
            return

    def _sync_solver_from_adapter(self) -> None:
        adapter = getattr(self, "adapter", None)
        if adapter is None:
            return
        getter = getattr(adapter, "get_population", None)
        if not callable(getter):
            return
        try:
            pop, obj, vio = getter()
        except Exception as exc:
            report_soft_error(
                component="EvolutionSolver",
                event="sync_solver_from_adapter",
                exc=exc,
                logger=logger,
                context_store=self.context_store,
                strict=False,
            )
            return
        pop_arr = np.asarray(pop, dtype=float)
        obj_arr = np.asarray(obj, dtype=float)
        vio_arr = np.asarray(vio, dtype=float).reshape(-1)
        if pop_arr.ndim != 2 or pop_arr.shape[0] == 0:
            return
        if obj_arr.ndim == 1:
            obj_arr = obj_arr.reshape(-1, 1)
        if obj_arr.shape[0] != pop_arr.shape[0] or vio_arr.shape[0] != pop_arr.shape[0]:
            return
        self.population = pop_arr
        self.objectives = obj_arr
        self.constraint_violations = vio_arr

    def non_dominated_sorting(self) -> Tuple[np.ndarray, np.ndarray, List[List[int]]]:
        if self.objectives is None:
            return np.zeros((0,), dtype=int), np.zeros((0,), dtype=float), []
        obj = np.asarray(self.objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        n = int(obj.shape[0])
        vio = np.asarray(
            self.constraint_violations if self.constraint_violations is not None else np.zeros((n,), dtype=float),
            dtype=float,
        ).reshape(-1)
        if vio.shape[0] != n:
            vio = np.zeros((n,), dtype=float)
        fronts, rank = FastNonDominatedSort.sort(obj, vio)
        crowding = np.zeros((n,), dtype=float)
        for front in fronts:
            if len(front) == 0:
                continue
            dist = FastNonDominatedSort.calculate_crowding_distance(obj, list(front))
            crowding += np.asarray(dist, dtype=float)
        return np.asarray(rank, dtype=int), crowding, [list(front) for front in fronts]

    def selection(self) -> np.ndarray:
        if self.population is None:
            return np.zeros((0, self.dimension), dtype=float)
        pop = np.asarray(self.population, dtype=float)
        n = int(pop.shape[0])
        if n == 0:
            return pop
        rank, crowding, _ = self.non_dominated_sorting()
        parents = np.zeros_like(pop)
        for i in range(n):
            a = int(self._rng.integers(0, n))
            b = int(self._rng.integers(0, n))
            if rank[a] < rank[b]:
                w = a
            elif rank[b] < rank[a]:
                w = b
            else:
                w = a if crowding[a] >= crowding[b] else b
            parents[i] = pop[w]
        return parents

    def crossover(self, parents: np.ndarray) -> np.ndarray:
        pop = np.asarray(parents, dtype=float)
        if pop.ndim != 2 or pop.shape[0] == 0:
            return pop
        offspring = pop.copy()
        pipeline = getattr(self, "representation_pipeline", None)
        crossover = getattr(pipeline, "crossover", None) if pipeline is not None else None

        for i in range(0, pop.shape[0], 2):
            if i + 1 >= pop.shape[0]:
                break
            if float(self._rng.random()) >= float(self.crossover_rate):
                continue
            p1 = pop[i]
            p2 = pop[i + 1]
            if crossover is not None and hasattr(crossover, "crossover"):
                try:
                    c1, c2 = crossover.crossover(p1, p2, {"generation": self.generation, "bounds": self.var_bounds})
                except TypeError:
                    c1, c2 = crossover.crossover(p1, p2)
                offspring[i] = np.asarray(c1, dtype=float)
                offspring[i + 1] = np.asarray(c2, dtype=float)
                continue

            eta_c = max(1e-8, float(self.sbx_eta_c))
            u = self._rng.random(self.dimension)
            beta = np.where(
                u <= 0.5,
                (2.0 * u) ** (1.0 / (eta_c + 1.0)),
                (1.0 / (2.0 * (1.0 - u))) ** (1.0 / (eta_c + 1.0)),
            )
            offspring[i] = 0.5 * ((1.0 + beta) * p1 + (1.0 - beta) * p2)
            offspring[i + 1] = 0.5 * ((1.0 - beta) * p1 + (1.0 + beta) * p2)
        return offspring

    def mutate(self, offspring: np.ndarray) -> np.ndarray:
        pop = np.asarray(offspring, dtype=float)
        if pop.ndim != 2 or pop.shape[0] == 0:
            return pop

        if self.representation_pipeline is not None and getattr(self.representation_pipeline, "mutator", None) is not None:
            out = np.zeros_like(pop)
            for i in range(pop.shape[0]):
                out[i] = np.asarray(
                    self.mutate_candidate(pop[i], {"generation": self.generation, "bounds": self.var_bounds}),
                    dtype=float,
                )
            return out

        delta = self._rng.uniform(-self.mutation_range, self.mutation_range, size=pop.shape)
        mask = self._rng.random(pop.shape) < float(self.mutation_rate)
        pop = pop + (mask * delta)
        return self._clip_to_bounds(pop)

    def _clip_to_bounds(self, population: np.ndarray) -> np.ndarray:
        pop = np.asarray(population, dtype=float)
        if isinstance(self.var_bounds, dict):
            keys = list(getattr(self.problem, "variables", self.var_bounds.keys()))
            for j, key in enumerate(keys):
                low, high = self.var_bounds[key]
                pop[:, j] = np.clip(pop[:, j], float(low), float(high))
            return pop
        bounds = np.asarray(self.var_bounds, dtype=float)
        if bounds.ndim == 2 and bounds.shape[0] == pop.shape[1]:
            for j in range(pop.shape[1]):
                pop[:, j] = np.clip(pop[:, j], float(bounds[j, 0]), float(bounds[j, 1]))
        return pop

    def environmental_selection(
        self,
        combined_pop: np.ndarray,
        combined_obj: np.ndarray,
        combined_violations: np.ndarray,
    ) -> None:
        pop = np.asarray(combined_pop, dtype=float)
        obj = np.asarray(combined_obj, dtype=float)
        vio = np.asarray(combined_violations, dtype=float).reshape(-1)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        if pop.shape[0] == 0:
            self.population = pop
            self.objectives = obj
            self.constraint_violations = vio
            return
        if vio.shape[0] != pop.shape[0]:
            vio = np.zeros((pop.shape[0],), dtype=float)

        fronts, _ = FastNonDominatedSort.sort(obj, vio)
        selected: List[int] = []
        for front in fronts:
            front_list = list(front)
            if len(selected) + len(front_list) <= int(self.pop_size):
                selected.extend(front_list)
                continue
            dist = FastNonDominatedSort.calculate_crowding_distance(obj, front_list)
            ranked = sorted(front_list, key=lambda idx: float(dist[idx]), reverse=True)
            remain = max(0, int(self.pop_size) - len(selected))
            selected.extend(ranked[:remain])
            break

        keep = np.asarray(selected, dtype=int)
        self.population = pop[keep]
        self.objectives = obj[keep]
        self.constraint_violations = vio[keep]
        self._sync_adapter_from_solver()
        self.update_pareto_solutions()
        self.record_history()
        self._refresh_best()

    def update_pareto_solutions(self) -> None:
        if self.population is None or self.objectives is None:
            self.pareto_solutions = {"individuals": np.array([]), "objectives": np.array([])}
            self.pareto_objectives = np.array([])
            return
        rank, crowding, _ = self.non_dominated_sorting()
        if rank.size == 0:
            self.pareto_solutions = {"individuals": np.array([]), "objectives": np.array([])}
            self.pareto_objectives = np.array([])
            return
        front0 = np.where(rank == 0)[0]
        if front0.size == 0:
            self.pareto_solutions = {"individuals": np.array([]), "objectives": np.array([])}
            self.pareto_objectives = np.array([])
            return
        keep = front0
        limit = max(1, int(self.max_pareto_solutions))
        if keep.size > limit:
            order = np.lexsort((keep, -crowding[keep]))
            keep = keep[order[:limit]]
        self.pareto_solutions = {
            "individuals": np.asarray(self.population, dtype=float)[keep],
            "objectives": np.asarray(self.objectives, dtype=float)[keep],
        }
        self.pareto_objectives = np.asarray(self.objectives, dtype=float)[keep]

    def record_history(self) -> None:
        if self.objectives is None:
            return
        rank, _, _ = self.non_dominated_sorting()
        if rank.size == 0:
            return
        max_rank = min(2, int(np.max(rank)) + 1)
        avg_objectives: List[np.ndarray] = []
        for r in range(max_rank):
            indices = np.where(rank == r)[0]
            if indices.size == 0:
                avg_objectives.append(np.full((self.num_objectives,), np.nan))
            else:
                avg_objectives.append(np.mean(np.asarray(self.objectives, dtype=float)[indices], axis=0))
        self.history.append((int(self.generation), avg_objectives))

    def _refresh_best(self) -> None:
        best_x, best_f = self._get_best_solution()
        if best_x is None:
            return
        self.best_x = np.asarray(best_x, dtype=float)
        if best_f is not None:
            self.best_f = float(best_f)
            self.best_objective = float(best_f)

    def _get_best_solution(self) -> Tuple[Optional[np.ndarray], Optional[float]]:
        if self.population is None or self.objectives is None:
            return None, None
        pop = np.asarray(self.population, dtype=float)
        obj = np.asarray(self.objectives, dtype=float)
        if pop.ndim != 2 or obj.size == 0:
            return None, None
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(
            self.constraint_violations if self.constraint_violations is not None else np.zeros((obj.shape[0],), dtype=float),
            dtype=float,
        ).reshape(-1)
        if vio.shape[0] != obj.shape[0]:
            vio = np.zeros((obj.shape[0],), dtype=float)
        score = np.sum(obj, axis=1) + (1e6 * vio)
        idx = int(np.argmin(score))
        return pop[idx], float(score[idx])

    def run(self, return_experiment: bool = False, return_dict: bool = False):
        self._sync_nsga2_adapter_config()
        if hasattr(self, "validate_plugin_order"):
            self.validate_plugin_order()
        self.running = True
        self.stop_requested = False
        self.start_time = time.time()

        self.plugin_manager.on_solver_init(self)
        resume_loaded = bool(getattr(self, "_resume_loaded", False))
        if not resume_loaded:
            if getattr(self, "random_seed", None) is None:
                try:
                    self.random_seed = int(np.random.randint(0, 2**32 - 1))
                except Exception as exc:
                    report_soft_error(
                        component="EvolutionSolver",
                        event="auto_seed_generate",
                        exc=exc,
                        logger=logger,
                        context_store=self.context_store,
                        strict=False,
                        level="debug",
                    )
                    self.random_seed = 0
            self.set_random_seed(getattr(self, "random_seed", None))
            self.mutation_range = float(self.initial_mutation_range)

        self.setup()

        if resume_loaded:
            start_generation = int(getattr(self, "_resume_cursor", getattr(self, "generation", 0)))
            start_generation = max(0, start_generation)
            self.generation = start_generation
            try:
                self.evaluation_count = int(getattr(self, "evaluation_count", 0))
            except Exception as exc:
                report_soft_error(
                    component="EvolutionSolver",
                    event="resume_evaluation_count_cast",
                    exc=exc,
                    logger=logger,
                    context_store=self.context_store,
                    strict=False,
                    level="debug",
                )
                self.evaluation_count = 0
        else:
            start_generation = 0
            self.generation = 0
            self.evaluation_count = 0
            self.history = []
            if self.population is None or self.objectives is None or self.constraint_violations is None:
                self.initialize_population(pop_size=self.pop_size, evaluate=True)
            else:
                self._sync_adapter_from_solver()
                self.update_pareto_solutions()
                if not self.history:
                    self.record_history()
                self._refresh_best()

        setattr(self, "_resume_loaded", False)
        setattr(self, "_resume_cursor", 0)
        setattr(self, "_resume_rng_state", None)

        max_generations = max(0, int(self.max_generations))
        for gen in range(start_generation, max_generations):
            if self.stop_requested:
                break
            self.generation = int(gen)
            apply_pending_order = getattr(self, "_apply_pending_plugin_order_updates", None)
            if callable(apply_pending_order):
                apply_pending_order()
            self.plugin_manager.on_generation_start(self.generation)
            self.plugin_manager.on_step(self, self.generation)

            max_g = max(1, int(self.max_generations))
            progress = min(1.0, max(0.0, float(gen) / float(max_g)))
            self.mutation_range = max(0.01, float(self.initial_mutation_range) * (1.0 - progress))

            self.step()

            self.plugin_manager.on_generation_end(self.generation)
            self.generation = int(gen + 1)
            if self.enable_progress_log and self.report_interval > 0 and (self.generation % self.report_interval == 0):
                self._log_progress()

        self.teardown()
        self.running = False
        self.run_count += 1

        result = {
            "pareto_solutions": self.pareto_solutions,
            "pareto_objectives": self.pareto_objectives,
            "generation": int(self.generation),
            "evaluation_count": int(getattr(self, "evaluation_count", 0)),
            "elapsed_sec": float(time.time() - self.start_time),
        }
        self.last_result = result
        self.plugin_manager.on_solver_finish(result)

        if return_experiment:
            experiment_cls = self._experiment_result_class()
            if experiment_cls is not None:
                exp = experiment_cls(
                    problem_name=getattr(self.problem, "name", "unknown"),
                    config={
                        "pop_size": int(self.pop_size),
                        "max_generations": int(self.max_generations),
                        "crossover_rate": float(self.crossover_rate),
                        "mutation_rate": float(self.mutation_rate),
                    },
                )
                exp.set_results(
                    self.pareto_solutions["individuals"] if self.pareto_solutions else None,
                    self.pareto_objectives,
                    int(self.generation),
                    int(getattr(self, "evaluation_count", 0)),
                    float(time.time() - self.start_time),
                    self.history,
                    None,
                )
                return exp

        if return_dict:
            return result

        best_x, best_f = self._get_best_solution()
        return best_x, best_f

    def _log_progress(self) -> None:
        if self.objectives is None:
            return
        best_x, best_f = self._get_best_solution()
        if best_x is None or best_f is None:
            return
        print(
            f"[progress] gen={int(self.generation)} | best={float(best_f):.6f} "
            f"| best_x={np.array2string(np.asarray(best_x), precision=6, separator=', ')}"
        )

    @staticmethod
    def _experiment_result_class():
        try:
            from ..utils.engineering.experiment import ExperimentResult

            return ExperimentResult
        except Exception as exc:
            report_soft_error(
                component="EvolutionSolver",
                event="load_experiment_result_class",
                exc=exc,
                logger=logger,
                context_store=None,
                strict=False,
                level="debug",
            )
            return None


__all__ = ["EvolutionSolver"]
