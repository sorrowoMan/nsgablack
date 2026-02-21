import time
import math
import random
import numpy as np
from scipy.spatial.distance import cdist
import json
import os
import logging
from typing import Optional, Any, List

from ..utils.context.context_keys import KEY_BEST_OBJECTIVE, KEY_BEST_X, KEY_CONSTRAINT_VIOLATION

# ============================================================================
# 基础依赖
# ============================================================================
from .base import BlackBoxProblem
from ..plugins import PluginManager

# ============================================================================
# 接口与能力探测
# ============================================================================
from .interfaces import (
    BiasInterface,
    RepresentationInterface,
    VisualizationInterface,
    PluginInterface,
    # 能力探测与工厂函数
    has_bias_module,
    has_representation_module,
    has_visualization_module,
    has_numba,
    load_bias_module,
    load_representation_pipeline,
    create_bias_context,
)

ensure_dependencies = None

# ============================================================================
# 可选依赖与懒加载占位
# ============================================================================

# 可视化混入（可选）
try:
    from ..utils.viz import SolverVisualizationMixin as _SolverVisualizationMixin
except ImportError:
    class _SolverVisualizationMixin:
        def _init_visualization(self):
            pass

# 偏置模块类缓存
_BiasModule = None

# Numba 加速函数缓存
_fast_is_dominated = None
_NUMBA_AVAILABLE = False

# 实验结果类缓存
_ExperimentResult = None

# 模块级日志器
logger = logging.getLogger(__name__)

# 表示管线类缓存
_RepresentationPipeline = None


# ============================================================================
# 懒加载工厂函数
# ============================================================================

def _get_bias_module():
    """bias"""
    global _BiasModule
    if _BiasModule is None:
        try:
            from ..bias import BiasModule
            _BiasModule = BiasModule
        except ImportError:
            _BiasModule = None
    return _BiasModule


def _get_numba_helpers():
    """懒加载 Numba 辅助函数与可用标记。"""
    global _fast_is_dominated, _NUMBA_AVAILABLE
    if _fast_is_dominated is None:
        try:
            from ..utils.performance.numba_helpers import fast_is_dominated, NUMBA_AVAILABLE
            _fast_is_dominated = fast_is_dominated
            _NUMBA_AVAILABLE = NUMBA_AVAILABLE
        except Exception:
            _fast_is_dominated = None
            _NUMBA_AVAILABLE = False
    return _fast_is_dominated, _NUMBA_AVAILABLE


def _get_experiment_result():
    """懒加载 ExperimentResult 类。"""
    global _ExperimentResult
    if _ExperimentResult is None:
        try:
            from ..utils.engineering.experiment import ExperimentResult
            _ExperimentResult = ExperimentResult
        except ImportError as e:
            logger.warning("ExperimentResult unavailable: %s", e)
            _ExperimentResult = None
    return _ExperimentResult


def _get_representation_pipeline():
    """懒加载 RepresentationPipeline 类。"""
    global _RepresentationPipeline
    if _RepresentationPipeline is None:
        try:
            from ..representation import RepresentationPipeline
            _RepresentationPipeline = RepresentationPipeline
        except ImportError:
            _RepresentationPipeline = None
    return _RepresentationPipeline


SolverVisualizationMixin = _SolverVisualizationMixin


class BlackBoxSolverNSGAII(_SolverVisualizationMixin):
    """
    NSGA-II 黑盒求解器（支持解耦扩展）。

    参数:
        problem: 黑盒优化问题实例。
        bias_module: 可选偏置模块，用于软偏好与搜索引导。
        representation_pipeline: 可选表示管线，负责初始化/变异/修复。
        **kwargs: 运行参数与工程开关。

    示例:
        # 先构造再挂载偏置
        solver = BlackBoxSolverNSGAII(problem)
        solver.bias_module = BiasModule()

        # 显式注入偏置模块
        from nsgablack.bias import BiasModule
        bias = BiasModule()
        solver = BlackBoxSolverNSGAII(problem, bias_module=bias)
    """

    def __init__(self,
                 problem: BlackBoxProblem,
                 bias_module: Optional[BiasInterface] = None,
                 representation_pipeline: Optional[RepresentationInterface] = None,
                 **kwargs):
        config = kwargs.pop("config", None)
        config_path = kwargs.pop("config_path", None)
        config_section = kwargs.pop("config_section", "solver")
        config_strict = kwargs.pop("config_strict", False)
        log_config = kwargs.pop("log_config", None)

        config_data = self._load_solver_config(
            config=config,
            config_path=config_path,
            config_section=config_section,
        )

        if log_config:
            try:
                from ..utils.engineering.logging_config import configure_logging
                configure_logging(**log_config)
            except Exception as exc:
                logger.warning("Logging config failed: %s", exc)
        # 基础开关
        self.enable_diversity_init = False
        self.use_history = False
        # Optional flag; prefer Suite + plugins for wiring.
        self.enable_elite_retention = False
        self.problem = problem
        self.variables = problem.variables
        self.num_objectives = problem.get_num_objectives()
        self.dimension = problem.dimension

        # 约束由 problem.evaluate_constraints / constraint_utils 统一计算。
        self.constraints = []  # 兼容旧接口的占位字段

        # Memory management
        self.memory_optimizer = None
        self.enable_memory_optimization = True
        self.temp_data = {}  # For temporary data that can be cleared
        self.constraint_violations = None
        self.var_bounds = problem.bounds

        # Parallel evaluation (optional)
        self.enable_parallel_evaluation = False
        self.parallel_backend = "process"
        self.parallel_max_workers = None
        self.parallel_chunk_size = None
        self.parallel_load_balancing = True
        self.parallel_retry_errors = True
        self.parallel_max_retries = 3
        self.parallel_verbose = False
        # Engineering safeguards (optional)
        self.parallel_precheck = True
        self.parallel_strict = False
        self.parallel_fallback_backend = "thread"
        self.parallel_problem_factory = None
        self.parallel_context_builder = None
        self.parallel_extra_context = None
        self.parallel_evaluator = None

        # 可选依赖检查报告
        self.dependency_report = None
        validate_dependencies = kwargs.pop('validate_dependencies', False)
        if validate_dependencies:
            try:
                from ..utils.runtime.dependencies import ensure_dependencies as _ensure_dependencies
            except Exception:
                _ensure_dependencies = None
            if _ensure_dependencies is not None:
                try:
                    self.dependency_report = _ensure_dependencies(
                        required=[('numpy', None), ('numba', None)],
                        raise_on_missing=False,
                        logger=logger,
                    )
                except Exception as exc:
                    logger.warning("Dependency validation failed: %s", exc)

        # ====================================================================
        # 模块句柄与功能开关
        # ====================================================================
        self._bias_module_internal: Optional[BiasInterface] = None
        self.bias_module = bias_module  # optional bias setter
        self.enable_bias = (bias_module is not None)
        # If True, constraint violations will be ignored (set to 0) when bias is enabled.
        # Use only when constraints are fully handled by representation repair and/or bias penalties.
        self.ignore_constraint_violation_when_bias = bool(kwargs.pop("ignore_constraint_violation_when_bias", False))

        # Visualization is optional and should not run during normal solver construction.
        # Enable it explicitly (e.g. enable_visualization=True) if you want the UI.
        self.enable_visualization = bool(kwargs.pop("enable_visualization", False))
        self.plot_enabled = False

        self._representation_internal: Optional[RepresentationInterface] = None
        self.representation_pipeline = representation_pipeline

        # NSGA-II 默认参数
        self.pop_size = 80
        self.max_generations = 150
        self.crossover_rate = 0.85
        self.mutation_rate = 0.15
        self.sbx_eta_c = 15.0
        self.initial_mutation_range = 0.8
        self.mutation_range = self.initial_mutation_range
        self.max_pareto_solutions = 50
        self.tol = 1e-5
        self.elite_retention_prob = 0.9
        self.random_seed = None
        self._rng = np.random.default_rng()
        self._rng_streams = {}

        # 多样性初始化参数（可由插件或配置覆盖）
        self.diversity_params = {
            'candidate_size': 500,
            'similarity_threshold': 0.05,
            'rejection_prob': 0.6,
            'sampling_method': 'lhs',
            'save_history': True
        }

        self._apply_solver_config(config_data, strict=config_strict)
        self._apply_solver_overrides(kwargs)
        self.set_random_seed(self.random_seed)
        self.mutation_range = self.initial_mutation_range
        if self.enable_parallel_evaluation:
            self._init_parallel_evaluator()

        # 运行时状态
        self.population = None
        self.objectives = None
        self.pareto_solutions = None
        self.pareto_objectives = None
        self.generation = 0
        self.history = []
        self.running = False
        self.start_time = 0

        # 插件系统（支持短路事件）
        # - evaluate_population / evaluate_individual 可被代理模块接管
        # - surrogate / 缓存 / 并行策略通常在插件层接入
        self.plugin_manager = PluginManager(
            short_circuit=True,
            short_circuit_events=["evaluate_population", "evaluate_individual", "initialize_population"],
        )

        # 其余初始化逻辑放在二阶段，避免 __init__ 过长
        self._complete_initialization()

    # --------------------------------------------------------------------
    # Plugin helpers (optional)
    # --------------------------------------------------------------------
    def add_plugin(self, plugin: Any) -> "BlackBoxSolverNSGAII":
        self.plugin_manager.register(plugin)
        try:
            plugin.attach(self)
        except Exception:
            pass
        try:
            if hasattr(plugin, "on_solver_init"):
                plugin.on_solver_init(self)
        except Exception as exc:
            strict_init = bool(getattr(plugin, "raise_on_init_error", False)) or bool(
                getattr(plugin, "strict_init", False)
            )
            if strict_init:
                raise
            logger.warning("Plugin '%s' init failed: %s", getattr(plugin, "name", plugin.__class__.__name__), exc)
        return self

    def remove_plugin(self, plugin_name: str) -> None:
        plugin = self.plugin_manager.get(plugin_name)
        if plugin is not None:
            try:
                plugin.detach()
            except Exception:
                pass
        self.plugin_manager.unregister(plugin_name)

    def get_plugin(self, plugin_name: str) -> Any:
        return self.plugin_manager.get(plugin_name)

    # --------------------------------------------------------------------
    # Control-plane wiring helpers (preferred over direct attribute writes)
    # --------------------------------------------------------------------
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
            self.pop_size = int(pop_size)
        if max_generations is not None:
            self.max_generations = int(max_generations)
        if mutation_rate is not None:
            self.mutation_rate = float(mutation_rate)
        if crossover_rate is not None:
            self.crossover_rate = float(crossover_rate)

    def write_population_snapshot(self, population, objectives, violations) -> bool:
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

    def get_rng_state(self):
        return {"bit_generator_state": self._rng.bit_generator.state}

    def set_rng_state(self, state) -> None:
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

    def get_context(self) -> dict:
        """Return a snapshot context for visualization/monitoring."""
        best_x, best_obj = self._resolve_best_snapshot()
        ctx = {
            "generation": int(getattr(self, "generation", 0)),
            "population": self.population if self.population is not None else [],
            "objectives": self.objectives if self.objectives is not None else [],
            KEY_BEST_X: best_x,
            KEY_BEST_OBJECTIVE: best_obj,
            "constraint_violations": self.constraint_violations if self.constraint_violations is not None else [],
            "pareto_objectives": self.pareto_objectives if self.pareto_objectives is not None else [],
            "pareto_solutions": self.pareto_solutions if self.pareto_solutions is not None else {},
            "evaluation_count": int(getattr(self, "evaluation_count", 0)),
            "history": self.history if self.history is not None else [],
        }
        dynamic = getattr(self, "dynamic_signals", None)
        if dynamic is not None:
            ctx["dynamic"] = dynamic
        phase_id = getattr(self, "dynamic_phase_id", None)
        if phase_id is not None:
            ctx["phase_id"] = phase_id
        return ctx

    def _resolve_best_snapshot(self):
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
                if self.num_objectives == 1:
                    idx = int(np.argmin(self.objectives[:, 0]))
                    best_obj = float(self.objectives[idx, 0])
                else:
                    scores = np.sum(self.objectives, axis=1)
                    if self.constraint_violations is not None:
                        vio = np.asarray(self.constraint_violations, dtype=float).reshape(-1)
                        if vio.shape[0] == scores.shape[0]:
                            scores = scores + vio * 1e6
                    idx = int(np.argmin(scores))
                    best_obj = float(scores[idx])
                if best_x is None and self.population is not None:
                    pop = np.asarray(self.population)
                    if pop.ndim >= 2 and idx < pop.shape[0]:
                        best_x = pop[idx]
            except Exception:
                pass

        return best_x, best_obj

    # ========================================================================
    # 模块属性访问器（支持依赖注入 + 惰性创建）
    # ========================================================================

    @property
    def bias_module(self) -> Optional[BiasInterface]:
        """
        获取当前偏置模块。

        规则:
        1. 若显式注入了偏置模块，优先返回注入实例。
        2. 若启用了偏置但未注入，则尝试惰性创建默认 BiasModule。
        """
        if self._bias_module_internal is not None:
            return self._bias_module_internal

        # 尝试惰性创建默认 BiasModule
        BiasModuleClass = _get_bias_module()
        if BiasModuleClass is not None and self.enable_bias:
            # 创建默认实例并缓存
            if not hasattr(self, '_bias_module_cached'):
                self._bias_module_cached = BiasModuleClass()
            return self._bias_module_cached

        return None

    @bias_module.setter
    def bias_module(self, value: Optional[BiasInterface]):
        """
        设置偏置模块实例，并同步功能开关与缓存状态。
        """
        self._bias_module_internal = value
        if value is not None:
            self.enable_bias = True
            # 注入后清理旧缓存
            if hasattr(self, '_bias_module_cached'):
                delattr(self, '_bias_module_cached')

    @property
    def representation_pipeline(self) -> Optional[RepresentationInterface]:
        """
        获取当前表示管线。

        规则:
        1. 若显式注入了管线，优先返回注入实例。
        2. 若未注入，则尝试惰性创建默认 RepresentationPipeline。
        """
        if self._representation_internal is not None:
            return self._representation_internal

        # 尝试惰性创建默认 RepresentationPipeline
        RepresentationPipelineClass = _get_representation_pipeline()
        if RepresentationPipelineClass is not None:
            if not hasattr(self, '_representation_cached'):
                self._representation_cached = RepresentationPipelineClass()
            return self._representation_cached

        return None

    @representation_pipeline.setter
    def representation_pipeline(self, value: Optional[RepresentationInterface]):
        """
        设置表示管线实例，并清理惰性缓存。
        """
        self._representation_internal = value
        if value is not None:
            # 注入后清理旧缓存
            if hasattr(self, '_representation_cached'):
                delattr(self, '_representation_cached')

    def _load_solver_config(
        self,
        *,
        config: Optional[Any],
        config_path: Optional[Any],
        config_section: Optional[str],
    ) -> dict:
        from ..utils.engineering.config_loader import ConfigError, load_config, merge_dicts, select_section

        data = {}
        if config_path:
            try:
                data = load_config(config_path)
            except ConfigError as exc:
                logger.warning("Config load failed (%s): %s", config_path, exc)
        if config:
            try:
                override = load_config(config)
                data = merge_dicts(data, override)
            except ConfigError as exc:
                logger.warning("Config load failed (%s): %s", config, exc)
        return select_section(data, config_section)

    def _apply_solver_config(self, config_data: dict, *, strict: bool = False) -> None:
        if not config_data:
            return
        try:
            if "parallel" in config_data and "enable_parallel_evaluation" not in config_data:
                config_data = dict(config_data)
                config_data["enable_parallel_evaluation"] = bool(config_data.get("parallel"))
            if "enable_parallel" in config_data and "enable_parallel_evaluation" not in config_data:
                config_data = dict(config_data)
                config_data["enable_parallel_evaluation"] = bool(config_data.get("enable_parallel"))
            from ..utils.engineering.config_loader import ConfigError, apply_config
            unknown = apply_config(self, config_data, allow_unknown=not strict)
            if unknown:
                logger.warning("Unknown solver config keys: %s", ", ".join(sorted(unknown)))
        except ConfigError as exc:
            logger.warning("Failed to apply solver config: %s", exc)

    def _apply_solver_overrides(self, overrides: dict) -> None:
        if not overrides:
            return
        from ..utils.engineering.config_loader import merge_dicts
        known_keys = {
            "enable_diversity_init",
            "use_history",
            "enable_elite_retention",
            "pop_size",
            "max_generations",
            "crossover_rate",
            "mutation_rate",
            "sbx_eta_c",
            "initial_mutation_range",
            "max_pareto_solutions",
            "tol",
            "elite_retention_prob",
            "random_seed",
            "diversity_params",
            "enable_parallel_evaluation",
            "parallel_backend",
            "parallel_max_workers",
            "parallel_chunk_size",
            "parallel_load_balancing",
            "parallel_retry_errors",
            "parallel_max_retries",
            "parallel_verbose",
            "parallel_precheck",
            "parallel_strict",
            "parallel_fallback_backend",
            "parallel_problem_factory",
            "parallel_context_builder",
            "parallel_extra_context",
        }
        if "parallel" in overrides:
            self.enable_parallel_evaluation = bool(overrides.get("parallel"))
        if "enable_parallel" in overrides:
            self.enable_parallel_evaluation = bool(overrides.get("enable_parallel"))
        for key in known_keys:
            if key not in overrides:
                continue
            value = overrides.get(key)
            if key == "diversity_params" and isinstance(value, dict):
                self.diversity_params = merge_dicts(self.diversity_params, value)
            else:
                setattr(self, key, value)

    def _init_parallel_evaluator(self) -> None:
        if self.parallel_evaluator is not None:
            return
        try:
            from ..utils.parallel import ParallelEvaluator, SmartEvaluatorSelector
        except Exception as exc:
            logger.warning("Parallel evaluator unavailable: %s", exc)
            self.enable_parallel_evaluation = False
            return

        if self.parallel_backend == "auto":
            self.parallel_evaluator = SmartEvaluatorSelector.select_evaluator(
                self.problem, self.pop_size
            )
            if hasattr(self.parallel_evaluator, "precheck"):
                try:
                    self.parallel_evaluator.precheck = bool(self.parallel_precheck)
                    self.parallel_evaluator.strict = bool(self.parallel_strict)
                    self.parallel_evaluator.fallback_backend = self.parallel_fallback_backend
                    self.parallel_evaluator.problem_factory = self.parallel_problem_factory
                    self.parallel_evaluator.context_builder = self.parallel_context_builder
                    self.parallel_evaluator.extra_context = dict(self.parallel_extra_context or {})
                except Exception:
                    pass
            return

        self.parallel_evaluator = ParallelEvaluator(
            backend=self.parallel_backend,
            max_workers=self.parallel_max_workers,
            chunk_size=self.parallel_chunk_size,
            enable_load_balancing=self.parallel_load_balancing,
            retry_errors=self.parallel_retry_errors,
            max_retries=self.parallel_max_retries,
            verbose=self.parallel_verbose,
            precheck=self.parallel_precheck,
            strict=self.parallel_strict,
            fallback_backend=self.parallel_fallback_backend,
            problem_factory=self.parallel_problem_factory,
            context_builder=self.parallel_context_builder,
            extra_context=self.parallel_extra_context,
        )

    # ========================================================================
    # 能力探测
    # ========================================================================

    def has_bias_support(self) -> bool:
        """是否可用偏置模块。"""
        return self.bias_module is not None

    def has_representation_support(self) -> bool:
        """是否可用表示管线。"""
        return self.representation_pipeline is not None

    def has_numba_support(self) -> bool:
        """是否可用 Numba 加速。"""
        _, numba_available = _get_numba_helpers()
        return numba_available

    # ========================================================================
    # 偏置模块开关与反射
    # ========================================================================

    def enable_bias_module(self, enable: bool = True):
        """
        启用或禁用偏置模块。

        当启用但当前无实例时，尝试懒加载默认 BiasModule。
        """
        self.enable_bias = enable
        if enable and self.bias_module is None:
            # 尝试自动创建默认实例
            BiasModuleClass = _get_bias_module()
            if BiasModuleClass is not None:
                self._bias_module_internal = BiasModuleClass()

    def get_bias_module_class(self):
        """
        获取 BiasModule 类对象（若不可用则返回 None）。
        """
        return _get_bias_module()

    # ========================================================================
    # 二阶段初始化
    # ========================================================================
    def _complete_initialization(self):
        """
        完成运行期状态初始化。

        该步骤从 __init__ 抽离，减少构造函数复杂度并提升可读性。
        """
        self.run_count = 0
        self.evaluation_count = 0
        self.enable_progress_log = True
        self.report_interval = 100
        self._maximize_report = False
        self.enable_selection_trace = False
        self.selection_trace_path = None
        self.selection_trace_mode = "full"
        self.selection_trace_limit = None
        self.selection_trace_stride = 1
        self.selection_trace_flush_interval = 1
        self.selection_trace_buffer = []
        # core 仅保留句柄；具体能力由 Plugin / Suite 组装。
        self.diversity_initializer = None
        self.elite_manager = None
        self.history_file = f"blackbox_{self.problem.name.replace(' ', '_')}_history.json"
        self.convergence_params = None
        self.convergence_state = None
        if self.enable_visualization:
            self._init_visualization()

    def update_candidate_size(self, text):
        try:
            self.diversity_params['candidate_size'] = int(text)
        except Exception:
            pass

    def update_similarity_threshold(self, text):
        try:
            value = float(text)
            self.diversity_params['similarity_threshold'] = value
            if getattr(self, "diversity_initializer", None) is not None:
                self.diversity_initializer.similarity_threshold = value
        except Exception:
            pass

    def update_rejection_prob(self, text):
        try:
            value = float(text)
            self.diversity_params['rejection_prob'] = value
            if getattr(self, "diversity_initializer", None) is not None:
                self.diversity_initializer.rejection_prob = value
        except Exception:
            pass

    def update_pop_size(self, text):
        try:
            pop_size = int(text)
            adjusted = pop_size if pop_size % 2 == 0 else pop_size + 1
            self.pop_size = max(adjusted, 2 * self.num_objectives)
        except Exception:
            pass

    def update_max_generations(self, text):
        try:
            self.max_generations = int(text)
            if getattr(self, "elite_manager", None) is not None:
                self.elite_manager.max_generations = self.max_generations
        except Exception:
            pass

    def update_mutation_rate(self, value):
        self.mutation_rate = value

    def update_var_bound(self, var, bound_type, text):
        try:
            value = float(text)
            if bound_type == 'min':
                if value < self.var_bounds[var][1]:
                    self.var_bounds[var][0] = value
                else:
                    self.var_bounds[var][1] = value + 0.1
                    self.bound_textboxes[(var, 'max')].set_val(str(self.var_bounds[var][1]))
            else:
                if value > self.var_bounds[var][0]:
                    self.var_bounds[var][1] = value
                else:
                    self.var_bounds[var][0] = value - 0.1
                    self.bound_textboxes[(var, 'min')].set_val(str(self.var_bounds[var][0]))
            self.problem.bounds = self.var_bounds
            if self.plot_enabled:
                self.redraw_static_elements()
        except Exception:
            pass

    def run_algorithm(self, event):
        if not self.running:
            self.running = True
            self.start_time = time.time()
            self.evaluation_count = 0
            if self.population is None:
                self.initialize_population()
            self.update_pareto_solutions()
            if not self.history:
                self.record_history()
            self.start_animation()

    def stop_algorithm(self, event):
        self.running = False
        self.stop_animation()
        # 保存求解历史
        try:
            self.save_history()
        except Exception:
            pass
        try:
            self.plugin_manager.on_solver_finish(
                {
                    "generation": self.generation,
                    "eval_count": self.evaluation_count,
                    "best_x": getattr(self, "best_x", None),
                    "best_f": getattr(self, "best_f", None),
                }
            )
        except Exception:
            pass
        self._flush_selection_trace()

    def enable_selection_tracing(self, path=None, mode="full", max_records=None, stride=1, flush_interval=1):
        """Enable selection tracing and write per-generation decisions to a JSONL file."""
        self.enable_selection_trace = True
        self.selection_trace_mode = mode
        self.selection_trace_limit = max_records
        self.selection_trace_stride = max(1, int(stride))
        self.selection_trace_flush_interval = max(1, int(flush_interval))
        self.selection_trace_buffer = []
        if path is None:
            safe_name = getattr(self.problem, "name", "problem").replace(" ", "_")
            trace_dir = os.path.join("reports", "selection_trace")
            os.makedirs(trace_dir, exist_ok=True)
            path = os.path.join(trace_dir, f"selection_trace_{safe_name}.jsonl")
        else:
            trace_dir = os.path.dirname(path)
            if trace_dir:
                os.makedirs(trace_dir, exist_ok=True)
        self.selection_trace_path = path
        try:
            with open(self.selection_trace_path, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

    def disable_selection_tracing(self):
        """Disable selection tracing."""
        self._flush_selection_trace()
        self.enable_selection_trace = False

    def _should_trace_selection(self):
        if not self.enable_selection_trace:
            return False
        stride = max(1, int(self.selection_trace_stride))
        return (self.generation % stride) == 0

    def _flush_selection_trace(self):
        if not self.selection_trace_path or not self.selection_trace_buffer:
            return
        try:
            with open(self.selection_trace_path, "a", encoding="utf-8") as f:
                for record in self.selection_trace_buffer:
                    f.write(json.dumps(record, ensure_ascii=False))
                    f.write("\n")
            self.selection_trace_buffer = []
        except Exception:
            pass

    def _append_selection_trace(self, record):
        if not self.selection_trace_path:
            return
        if self.selection_trace_flush_interval <= 1:
            try:
                with open(self.selection_trace_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False))
                    f.write("\n")
            except Exception:
                pass
            return
        self.selection_trace_buffer.append(record)
        if len(self.selection_trace_buffer) >= self.selection_trace_flush_interval:
            self._flush_selection_trace()

    def _record_selection_trace(
        self,
        combined_obj,
        combined_violations,
        combined_rank,
        combined_crowding,
        sorted_indices
    ):
        if not self._should_trace_selection():
            return

        selected_indices = sorted_indices[:self.pop_size]
        eliminated_indices = sorted_indices[self.pop_size:]
        if selected_indices.size == 0:
            return

        cutoff_idx = int(selected_indices[-1])
        cutoff_rank = int(combined_rank[cutoff_idx])
        cutoff_crowding = float(combined_crowding[cutoff_idx])
        parent_count = min(self.pop_size, len(combined_rank))

        def _obj_list(idx):
            return [float(v) for v in np.atleast_1d(combined_obj[idx]).tolist()]

        def _entry(idx, reason):
            return {
                "index": int(idx),
                "source": "parent" if idx < parent_count else "offspring",
                "rank": int(combined_rank[idx]),
                "crowding": float(combined_crowding[idx]),
                "violation": float(combined_violations[idx]),
                "feasible": bool(combined_violations[idx] <= 1e-10),
                "objectives": _obj_list(idx),
                "reason": reason
            }

        def _selected_reason(idx):
            rank = int(combined_rank[idx])
            crowd = float(combined_crowding[idx])
            if rank < cutoff_rank:
                return "better_rank"
            if rank > cutoff_rank:
                return "selected_by_order"
            if crowd > cutoff_crowding:
                return "higher_crowding"
            if crowd < cutoff_crowding:
                return "selected_by_order"
            return "tie_break"

        def _eliminated_reason(idx):
            rank = int(combined_rank[idx])
            crowd = float(combined_crowding[idx])
            if rank > cutoff_rank:
                return "worse_rank"
            if rank < cutoff_rank:
                return "eliminated_by_order"
            if crowd < cutoff_crowding:
                return "lower_crowding"
            if crowd > cutoff_crowding:
                return "eliminated_by_order"
            return "tie_break"

        def _limit_list(items):
            if self.selection_trace_limit is None:
                return items
            limit = int(self.selection_trace_limit)
            if limit <= 0:
                return []
            return items[:limit]
        mode = self.selection_trace_mode
        selected_entries = []
        eliminated_entries = []
        if mode != "stats":
            selected_entries = [_entry(idx, _selected_reason(idx)) for idx in selected_indices]
            eliminated_entries = [_entry(idx, _eliminated_reason(idx)) for idx in eliminated_indices]

        def _rank_hist(indices):
            if indices.size == 0:
                return {}
            ranks = combined_rank[indices]
            unique, counts = np.unique(ranks, return_counts=True)
            return {str(int(r)): int(c) for r, c in zip(unique, counts)}

        def _summary(indices):
            if indices.size == 0:
                return {
                    "feasible": 0,
                    "mean_violation": 0.0,
                    "rank_hist": {}
                }
            violations = combined_violations[indices]
            feasible = int(np.sum(violations <= 1e-10))
            mean_violation = float(np.mean(violations)) if violations.size > 0 else 0.0
            return {
                "feasible": feasible,
                "mean_violation": mean_violation,
                "rank_hist": _rank_hist(indices)
            }

        record = {
            "generation": int(self.generation),
            "population_size": int(self.pop_size),
            "combined_size": int(len(combined_rank)),
            "cutoff": {
                "rank": cutoff_rank,
                "crowding": cutoff_crowding
            },
            "selected_count": int(len(selected_indices)),
            "eliminated_count": int(len(eliminated_indices))
        }
        if mode == "stats":
            record["summary"] = {
                "selected": _summary(selected_indices),
                "eliminated": _summary(eliminated_indices)
            }
        else:
            record["selected"] = _limit_list(selected_entries) if mode == "full" else _limit_list(selected_entries[:10])
            record["eliminated"] = _limit_list(eliminated_entries) if mode == "full" else _limit_list(eliminated_entries[:10])
        self._append_selection_trace(record)

    def reset(self, event):
        self.stop_algorithm(None)
        self.generation = 0
        self.population = None
        self.objectives = None
        self.constraint_violations = None
        self.pareto_solutions = None
        self.history = []
        self.mutation_range = self.initial_mutation_range
        self.evaluation_count = 0
        self.elite_manager = None
        if self.plot_enabled:
            self.update_plot_dynamic()
        self.update_info_text()

    # ---- 个体/种群评估 ----
    def _evaluate_individual(self, x, individual_id=None):
        """
        评估单个个体并返回 (objectives, violation)。

        - 目标值来自 problem.evaluate(x)
        - 约束违反度 violation 基于 g(x) <= 0 规则累计
        """
        overridden = self.plugin_manager.trigger("evaluate_individual", self, x, individual_id)
        if overridden is not None:
            try:
                obj, violation = overridden
            except Exception as exc:
                raise ValueError("evaluate_individual  (objectives, violation)") from exc
            obj = np.asarray(obj, dtype=float).flatten()
            return obj, float(violation)

        val = self.problem.evaluate(x)
        obj = np.asarray(val, dtype=float).flatten()
        from ..utils.constraints.constraint_utils import evaluate_constraints_safe
        cons_arr, violation = evaluate_constraints_safe(self.problem, x)

        from ..utils.context.context_schema import build_minimal_context
        extra_context = {
            "problem": self.problem,
            "bounds": getattr(self, "var_bounds", None),
        }
        dynamic = getattr(self, "dynamic_signals", None)
        if dynamic is not None:
            extra_context["dynamic"] = dynamic
        phase_id = getattr(self, "dynamic_phase_id", None)
        if phase_id is not None:
            extra_context["phase_id"] = phase_id

        context = build_minimal_context(
            generation=getattr(self, "generation", None),
            individual_id=0 if individual_id is None else int(individual_id),
            constraints=cons_arr.tolist() if cons_arr.size > 0 else [],
            constraint_violation=float(violation),
            extra=extra_context,
        )

        # 偏置模块后处理
        if self.enable_bias and self.bias_module is not None:
            if self.num_objectives == 1:
                f_biased = self.bias_module.compute_bias(x, float(obj[0]), individual_id, context=context)
                obj = np.array([f_biased])
                if self.ignore_constraint_violation_when_bias:
                    violation = 0.0
            else:
                # 多目标优先走向量偏置接口
                if callable(getattr(self.bias_module, "compute_bias_vector", None)):
                    obj = np.asarray(
                        self.bias_module.compute_bias_vector(x, obj, individual_id, context=context),
                        dtype=float,
                    ).reshape(-1)
                else:
                    obj_biased = []
                    for i in range(len(obj)):
                        f_biased = self.bias_module.compute_bias(x, float(obj[i]), individual_id, context=context)
                        obj_biased.append(f_biased)
                    obj = np.array(obj_biased)
                if self.ignore_constraint_violation_when_bias:
                    violation = 0.0
        else:
            # 未启用 bias 时，保留原始 violation
            if cons_arr.size == 0 and KEY_CONSTRAINT_VIOLATION in context:
                violation = float(context[KEY_CONSTRAINT_VIOLATION])

        return obj, violation

    def evaluate_population(self, population):
        """
        评估种群并返回 (objectives, constraint_violations)。
        """
        if not hasattr(population, "shape"):
            try:
                population = np.asarray(population)
            except Exception:
                pass
        # If a representation pipeline is attached, enforce a repair pass so
        # all candidates go through the main pipeline before evaluation.
        if self.representation_pipeline is not None and getattr(self.representation_pipeline, "repair", None) is not None:
            context_base = {
                "generation": self.generation,
                "bounds": self.var_bounds,
            }
            if hasattr(self.representation_pipeline, "repair_batch") and callable(getattr(self.representation_pipeline, "repair_batch")):
                contexts = [context_base] * len(population)
                population = self.representation_pipeline.repair_batch(population, contexts=contexts)
                if not hasattr(population, "shape"):
                    try:
                        population = np.asarray(population)
                    except Exception:
                        pass
            else:
                repaired = []
                for i in range(len(population)):
                    repaired.append(self.representation_pipeline.repair.repair(population[i], dict(context_base)))
                population = np.asarray(repaired)

        overridden = self.plugin_manager.trigger("evaluate_population", self, population)
        if overridden is not None:
            try:
                objectives, violations = overridden
            except Exception as exc:
                raise ValueError("evaluate_population  (objectives, violations)") from exc
            objectives = np.asarray(objectives, dtype=float)
            violations = np.asarray(violations, dtype=float).ravel()
            # 插件接管评估时仍累计评估次数
            try:
                self.evaluation_count += int(getattr(population, "shape", [len(population)])[0])
            except Exception:
                pass
            if self.enable_bias and self.ignore_constraint_violation_when_bias:
                violations = np.zeros_like(np.asarray(violations, dtype=float))
            return objectives, violations

        if self.enable_parallel_evaluation:
            if self.parallel_evaluator is None:
                self._init_parallel_evaluator()
            if self.parallel_evaluator is not None:
                try:
                    objectives, violations = self.parallel_evaluator.evaluate_population(
                        population=population,
                        problem=self.problem,
                        enable_bias=self.enable_bias,
                        bias_module=self.bias_module,
                        return_detailed=False,
                    )
                    # 并行评估路径同样累计评估次数
                    try:
                        self.evaluation_count += int(getattr(population, "shape", [len(population)])[0])
                    except Exception:
                        pass
                    if self.enable_bias and self.ignore_constraint_violation_when_bias:
                        violations = np.zeros_like(np.asarray(violations, dtype=float))
                    return objectives, violations
                except Exception as exc:
                    if getattr(self, "parallel_strict", False):
                        raise
                    logger.warning("Parallel evaluation failed; fallback to serial: %s", exc)
        pop_size = population.shape[0]
        objectives = np.zeros((pop_size, self.num_objectives))
        constraint_violations = np.zeros(pop_size, dtype=float)

        for i in range(pop_size):
            obj, vio = self._evaluate_individual(population[i], individual_id=i)
            if obj.size == self.num_objectives:
                objectives[i] = obj
            elif obj.size > self.num_objectives:
                objectives[i] = obj[: self.num_objectives]
            else:
                objectives[i, : obj.size] = obj
            constraint_violations[i] = vio
            self.evaluation_count += 1

        return objectives, constraint_violations

    def initialize_population(self):
        overridden = self.plugin_manager.trigger("initialize_population", self)
        if overridden is not None:
            pop, obj, vio = overridden
            self.population = pop
            self.objectives = obj
            self.constraint_violations = vio
            if not hasattr(self.population, "shape"):
                try:
                    self.population = np.asarray(self.population)
                except Exception:
                    pass
        else:
            if self.representation_pipeline is not None and self.representation_pipeline.initializer is not None:
                # 先用一个样本推断初始化结果的 dtype
                context = {
                    'generation': self.generation,
                    'bounds': self.var_bounds
                }
                sample = self.representation_pipeline.init(self.problem, context)

                # 按样本 dtype 创建种群数组
                if hasattr(sample, 'dtype'):
                    population_dtype = sample.dtype
                else:
                    population_dtype = type(sample[0]) if hasattr(sample, '__getitem__') else float

                # 写入首个样本
                self.population = np.zeros((self.pop_size, self.dimension), dtype=population_dtype)
                self.population[0] = sample

                # 继续生成其余个体
                for i in range(1, self.pop_size):
                    context = {'generation': self.generation, 'bounds': self.var_bounds}
                    self.population[i] = self.representation_pipeline.init(self.problem, context)
            else:
                # 无 Pipeline 时回退到浮点随机初始化
                self.population = np.zeros((self.pop_size, self.dimension))
                if isinstance(self.var_bounds, dict):
                    for i, var in enumerate(self.variables):
                        min_val, max_val = self.var_bounds[var]
                        self.population[:, i] = self._rng.uniform(min_val, max_val, self.pop_size)
                else:
                    for i in range(self.dimension):
                        min_val, max_val = self.var_bounds[i]
                        self.population[:, i] = self._rng.uniform(min_val, max_val, self.pop_size)
            if not hasattr(self.population, "shape"):
                try:
                    self.population = np.asarray(self.population)
                except Exception:
                    pass
            self.objectives, self.constraint_violations = self.evaluate_population(self.population)

        try:
            self.plugin_manager.on_population_init(self.population, self.objectives, self.constraint_violations)
        except Exception:
            pass

    def is_dominated_vectorized(self, obj_matrix):
        """优先使用 Numba，加速失败时回退到 NumPy。"""
        if obj_matrix.ndim == 1:
            obj = obj_matrix.reshape(-1, 1)
        else:
            obj = obj_matrix

        # 尝试 Numba 路径
        fast, numba = _get_numba_helpers()
        if numba and fast is not None:
            try:
                return fast(obj)
            except Exception:
                #  numba 
                pass

        pop_size = obj.shape[0]
        dominated = np.zeros(pop_size, dtype=bool)
        for i in range(pop_size):
            less_equal = obj <= obj[i]
            strictly_less = obj < obj[i]
            dominates_mask = np.all(less_equal, axis=1) & np.any(strictly_less, axis=1)
            dominated[i] = np.any(dominates_mask)
        return dominated

    def non_dominated_sorting(self):
        """Optimized non-dominated sorting using O(MN^2) algorithm"""
        from ..utils.performance.fast_non_dominated_sort import (
            fast_non_dominated_sort_optimized,
            FastNonDominatedSort,
        )

        fronts, rank = fast_non_dominated_sort_optimized(
            self.objectives[:self.pop_size],
            self.constraint_violations[:self.pop_size],
        )

        crowding_distance = np.zeros(self.pop_size)
        for front in fronts:
            if len(front) > 1:
                front_distances = FastNonDominatedSort.calculate_crowding_distance(
                    self.objectives[:self.pop_size], front
                )
                for i, idx in enumerate(front):
                    if idx < self.pop_size:
                        crowding_distance[idx] = front_distances[idx]

        if len(rank) < self.pop_size:
            rank = np.pad(rank, (0, self.pop_size - len(rank)), 'constant', constant_values=len(fronts))

        return rank[:self.pop_size], crowding_distance[:self.pop_size], fronts

    def selection(self):
        parent_indices = np.zeros(self.pop_size, dtype=int)
        rank, crowding_distance, _ = self.non_dominated_sorting()
        i = self._rng.integers(0, self.pop_size, self.pop_size)
        j = self._rng.integers(0, self.pop_size, self.pop_size)
        mask = i == j
        j[mask] = self._rng.integers(0, self.pop_size, np.sum(mask))
        rank_i = rank[i]
        rank_j = rank[j]
        crowd_i = crowding_distance[i]
        crowd_j = crowding_distance[j]
        parent_indices = np.where(
            rank_i < rank_j, i,
            np.where(rank_i > rank_j, j,
                     np.where(crowd_i >= crowd_j, i, j))
        )
        return self.population[parent_indices]

    def crossover(self, parents):
        pop_size = parents.shape[0]
        offspring = parents.copy()

        # 优先使用 Pipeline 提供的交叉算子
        if self.representation_pipeline is not None and self.representation_pipeline.crossover is not None:
            context = {
                'generation': self.generation,
                'bounds': self.var_bounds
            }
            for i in range(0, pop_size, 2):
                if i + 1 >= pop_size:
                    break
                if self._rng.random() < self.crossover_rate:
                    child1, child2 = self.representation_pipeline.crossover.crossover(
                        parents[i], parents[i+1]
                    )
                    offspring[i] = child1
                    offspring[i+1] = child2
        else:
            # Simulated Binary Crossover (SBX)
            crossover_mask = self._rng.random(pop_size // 2) < self.crossover_rate
            sbx_u = self._rng.random((np.sum(crossover_mask), self.dimension))
            eta_c = max(1e-8, float(self.sbx_eta_c))
            beta = np.where(
                sbx_u <= 0.5,
                (2.0 * sbx_u) ** (1.0 / (eta_c + 1.0)),
                (1.0 / (2.0 * (1.0 - sbx_u))) ** (1.0 / (eta_c + 1.0)),
            )
            idx = 0
            for i in range(0, pop_size, 2):
                if i + 1 >= pop_size:
                    break
                if crossover_mask[i // 2]:
                    p1 = parents[i]
                    p2 = parents[i + 1]
                    b = beta[idx]
                    offspring[i] = 0.5 * ((1.0 + b) * p1 + (1.0 - b) * p2)
                    offspring[i + 1] = 0.5 * ((1.0 - b) * p1 + (1.0 + b) * p2)
                    idx += 1

        return offspring

    def mutate(self, offspring):
        pop_size = offspring.shape[0]
        if self.representation_pipeline is not None and self.representation_pipeline.mutator is not None:
            for i in range(pop_size):
                context = {
                    'generation': self.generation,
                    'bounds': self.var_bounds
                }
                offspring[i] = self.representation_pipeline.mutate(offspring[i], context)
        else:
            mutation_mask = self._rng.random(pop_size) < self.mutation_rate
            mutation = self._rng.uniform(-self.mutation_range, self.mutation_range, (pop_size, self.dimension))
            offspring[mutation_mask] += mutation[mutation_mask]
            if isinstance(self.var_bounds, dict):
                for j, var in enumerate(self.variables):
                    min_val, max_val = self.var_bounds[var]
                    offspring[:, j] = np.clip(offspring[:, j], min_val, max_val)
            else:
                for j in range(self.dimension):
                    min_val, max_val = self.var_bounds[j]
                    offspring[:, j] = np.clip(offspring[:, j], min_val, max_val)
            if self.representation_pipeline is not None and self.representation_pipeline.repair is not None:
                for i in range(pop_size):
                    context = {
                        'generation': self.generation,
                        'bounds': self.var_bounds
                    }
                    offspring[i] = self.representation_pipeline.repair.repair(offspring[i], context)
        return offspring

    def set_representation_pipeline(self, pipeline):
        """Attach a representation pipeline for encoding/repair/init/mutation."""
        self.representation_pipeline = pipeline

    def update_pareto_solutions(self):
        if self.objectives is None:
            return
        rank, crowding_distance, _ = self.non_dominated_sorting()
        pareto_indices = np.where(rank == 0)[0]
        if len(pareto_indices) > 0:
            valid_indices = pareto_indices
            max_keep = max(1, int(getattr(self, "max_pareto_solutions", 50)))
            if len(valid_indices) > max_keep:
                pareto_crowding = np.asarray(crowding_distance[valid_indices], dtype=float)
                # Keep boundary/diverse points first and use index as deterministic tie-breaker.
                order = np.lexsort((valid_indices, -pareto_crowding))
                valid_indices = valid_indices[order[:max_keep]]
            self.pareto_solutions = {
                'individuals': self.population[valid_indices],
                'objectives': self.objectives[valid_indices]
            }
            self.pareto_objectives = self.objectives[valid_indices]
        else:
            self.pareto_solutions = {'individuals': np.array([]), 'objectives': np.array([])}
            self.pareto_objectives = np.array([])

    def record_history(self):
        rank, _, _ = self.non_dominated_sorting()
        max_rank = min(2, np.max(rank) + 1)
        avg_objectives = []
        for r in range(max_rank):
            front_indices = np.where(rank == r)[0]
            if len(front_indices) == 0:
                avg_objectives.append(np.full(self.num_objectives, np.nan))
            else:
                avg_obj = np.mean(self.objectives[front_indices], axis=0)
                avg_objectives.append(avg_obj)
        self.history.append((self.generation, avg_objectives))

    def save_history(self):
        try:
            # Prepare serializable structure
            out = {
                'problem': getattr(self.problem, 'name', None),
                'generations': []
            }
            for gen, avg_objs in self.history:
                gen_entry = {'generation': int(gen), 'avg_objectives': []}
                for arr in avg_objs:
                    # arr may be numpy array or list
                    a = np.atleast_1d(arr)
                    vals = []
                    for v in a.tolist():
                        try:
                            if v is None:
                                vals.append(None)
                            else:
                                # convert nan to None
                                if isinstance(v, float) and np.isnan(v):
                                    vals.append(None)
                                else:
                                    vals.append(float(v))
                        except Exception:
                            vals.append(None)
                    gen_entry['avg_objectives'].append(vals)
                out['generations'].append(gen_entry)

            # Ensure directory exists if path contains one
            dirname = os.path.dirname(self.history_file)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            from ..utils.engineering.file_io import atomic_write_json
            atomic_write_json(self.history_file, out, ensure_ascii=False, indent=2, encoding="utf-8")
        except Exception:
            # Don't raise for save failures; keep running
            pass

    # Legacy convergence helpers used to live in core, but are now expected to be
    # implemented via plugins (e.g. plugins/runtime/convergence.py) + suites.

    def _log_progress(self):
        if self.objectives is None or self.population is None:
            return
        try:
            if self.num_objectives == 1:
                best_idx = int(np.argmin(self.objectives[:, 0]))
                best_f = float(self.objectives[best_idx, 0])
                if getattr(self, "_maximize_report", False):
                    best_f_display = -best_f
                else:
                    best_f_display = best_f
                best_x = self.population[best_idx]
                print(
                    f"[progress] gen={self.generation} | best={best_f_display:.6f} "
                    f"| best_x={np.array2string(best_x, precision=6, separator=', ')}"
                )
            else:
                rank, _, _ = self.non_dominated_sorting()
                pareto_idx = np.where(rank == 0)[0]
                if len(pareto_idx) > 0:
                    sums = np.sum(self.objectives[pareto_idx], axis=1)
                    rep_rel = int(np.argmin(sums))
                    rep_idx = int(pareto_idx[rep_rel])
                    rep_obj = self.objectives[rep_idx]
                    rep_x = self.population[rep_idx]
                    print(
                        f"[progress] gen={self.generation} | pareto={len(pareto_idx)} "
                        f"| rep_obj={np.array2string(rep_obj, precision=6, separator=', ')} "
                        f"| rep_x={np.array2string(rep_x, precision=6, separator=', ')}"
                    )
                else:
                    print(f"[progress] gen={self.generation} | pareto=0")
        except Exception:
            pass

    def environmental_selection(self, combined_pop, combined_obj, combined_violations):
        from ..utils.performance.fast_non_dominated_sort import (
            FastNonDominatedSort,
            fast_non_dominated_sort_optimized,
        )

        fronts, combined_rank = fast_non_dominated_sort_optimized(
            np.asarray(combined_obj, dtype=float),
            np.asarray(combined_violations, dtype=float),
        )
        combined_crowding = np.zeros(len(combined_pop), dtype=float)
        for front in fronts:
            if not front:
                continue
            # Returns global-length distance array; accumulate front contribution.
            combined_crowding += FastNonDominatedSort.calculate_crowding_distance(
                np.asarray(combined_obj, dtype=float),
                list(front),
            )
        sorted_indices = np.lexsort((-combined_crowding, combined_rank))
        self._record_selection_trace(
            combined_obj,
            combined_violations,
            combined_rank,
            combined_crowding,
            sorted_indices
        )
        self.population = combined_pop[sorted_indices[:self.pop_size]]
        self.objectives = combined_obj[sorted_indices[:self.pop_size]]
        self.constraint_violations = combined_violations[sorted_indices[:self.pop_size]]
        self.update_pareto_solutions()
        self.record_history()

    def evolve_one_generation(self):
        max_g = max(1, int(self.max_generations))
        progress = min(1.0, max(0.0, float(self.generation) / float(max_g)))
        self.mutation_range = max(0.01, float(self.initial_mutation_range) * (1.0 - progress))
        parents = self.selection()
        offspring = self.crossover(parents)
        offspring = self.mutate(offspring)
        offspring_objectives, offspring_violations = self.evaluate_population(offspring)
        combined_pop = np.vstack([self.population, offspring])
        combined_obj = np.vstack([self.objectives, offspring_objectives])
        if self.constraint_violations is None:
            base_vio = np.zeros(self.population.shape[0], dtype=float)
        else:
            base_vio = np.asarray(self.constraint_violations, dtype=float)
        combined_violations = np.concatenate([base_vio, offspring_violations])
        self.environmental_selection(combined_pop, combined_obj, combined_violations)
        self.generation += 1
        if self.enable_progress_log and self.report_interval > 0 and (self.generation % self.report_interval == 0):
            self._log_progress()

    def _generate_random_individual(self):
        """按变量边界生成一个随机个体。"""
        new_individual = np.zeros(self.dimension)
        if isinstance(self.var_bounds, dict):
            var_keys = list(self.var_bounds.keys())
            for j, var in enumerate(var_keys):
                min_val, max_val = self.var_bounds[var]
                new_individual[j] = self._rng.uniform(min_val, max_val)
        else:
            for j in range(self.dimension):
                min_val, max_val = self.var_bounds[j]
                new_individual[j] = self._rng.uniform(min_val, max_val)
        return new_individual

    def animate(self, frame):
        if not self.running or self.generation >= self.max_generations:
            self.running = False
            try:
                self.save_history()
            except Exception:
                pass
            try:
                self.plugin_manager.on_solver_finish(
                    {
                        "generation": self.generation,
                        "eval_count": self.evaluation_count,
                        "best_x": getattr(self, "best_x", None),
                        "best_f": getattr(self, "best_f", None),
                    }
                )
            except Exception:
                pass
            self._flush_selection_trace()
            return

        try:
            self.plugin_manager.on_generation_start(self.generation)
        except Exception:
            pass
        self.evolve_one_generation()
        try:
            self.plugin_manager.on_generation_end(self.generation)
        except Exception:
            pass
        
        if self.plot_enabled and (self.generation - self.last_viz_update >= self.visualization_update_frequency):
            self.update_plot_dynamic()
            self.last_viz_update = self.generation
        self.update_info_text()
        if self.generation >= self.max_generations:
            self.run_count += 1

    def run(self, return_experiment=False, return_dict=False):
        """命令行/脚本模式运行求解器（非 GUI）。

        Args:
            return_experiment: 为 True 时，返回 ExperimentResult（若可用）。
            return_dict: 为 True 时，返回字典结果而非 (best_x, best_f)。
        """
        # Initialize memory optimization
        if self.enable_memory_optimization and self.memory_optimizer is None:
            try:
                from ..utils.performance.memory_manager import OptimizationMemoryOptimizer
                self.memory_optimizer = OptimizationMemoryOptimizer(self)
                if self.enable_progress_log:
                    print("Memory optimization enabled")
            except ImportError:
                if self.enable_progress_log:
                    print("Memory optimization module not available")
                self.enable_memory_optimization = False

        self.running = True
        self.start_time = time.time()
        resume_loaded = bool(getattr(self, "_resume_loaded", False))

        if not resume_loaded:
            self.evaluation_count = 0
            if self.random_seed is None:
                try:
                    self.random_seed = int(random.SystemRandom().randrange(0, 2**32 - 1))
                except Exception:
                    self.random_seed = 0
            try:
                self.set_random_seed(self.random_seed)
            except Exception:
                pass
        else:
            try:
                self.evaluation_count = int(getattr(self, "evaluation_count", 0))
            except Exception:
                self.evaluation_count = 0
            rng_state = getattr(self, "_resume_rng_state", None)
            if isinstance(rng_state, dict):
                np_state = rng_state.get("solver_numpy")
                if np_state is None:
                    np_state = rng_state.get("numpy")
                py_state = rng_state.get("python")
                if np_state is not None:
                    try:
                        self.set_rng_state(np_state)
                    except Exception:
                        pass
                if py_state is not None:
                    try:
                        random.setstate(py_state)
                    except Exception:
                        pass

        setattr(self, "_resume_loaded", False)
        setattr(self, "_resume_rng_state", None)
        if self.population is None:
            self.initialize_population()
        self.update_pareto_solutions()
        if not self.history:
            self.record_history()

        while self.running and self.generation < self.max_generations:
            try:
                self.plugin_manager.on_generation_start(self.generation)
            except Exception:
                pass
            self.evolve_one_generation()
            try:
                self.plugin_manager.on_generation_end(self.generation)
            except Exception:
                pass

            # Memory optimization every 10 generations
            if self.enable_memory_optimization and self.memory_optimizer and self.generation % 10 == 0:
                if self.generation % 50 == 0:  # Detailed optimization every 50 generations
                    self.memory_optimizer.auto_optimize()
                else:  # Light cleanup every 10 generations
                    self.memory_optimizer.memory_manager.cleanup_memory()

        self.running = False
        try:
            self.save_history()
        except Exception:
            pass
        try:
            self.plugin_manager.on_solver_finish(
                {
                    "generation": self.generation,
                    "eval_count": self.evaluation_count,
                    "best_x": getattr(self, "best_x", None),
                    "best_f": getattr(self, "best_f", None),
                }
            )
        except Exception:
            pass
        self._flush_selection_trace()

        # Final memory cleanup
        if self.enable_memory_optimization and self.memory_optimizer:
            self.memory_optimizer.optimize_history_storage()
            self.memory_optimizer.clear_temporary_data()
        self.run_count += 1

        ExperimentResult = _get_experiment_result()
        if return_experiment and ExperimentResult is not None:
            result = ExperimentResult(
                problem_name=getattr(self.problem, 'name', 'unknown'),
                config={
                    'pop_size': self.pop_size,
                    'max_generations': self.max_generations,
                    'crossover_rate': self.crossover_rate,
                    'mutation_rate': self.mutation_rate
                }
            )
            result.set_results(
                self.pareto_solutions['individuals'] if self.pareto_solutions else None,
                self.pareto_objectives,
                self.generation,
                self.evaluation_count,
                time.time() - self.start_time,
                self.history,
                None
            )
            return result
        result = {
            'pareto_solutions': self.pareto_solutions,
            'pareto_objectives': self.pareto_objectives,
            'generation': self.generation
        }
        self.last_result = result

        if return_dict:
            return result

        best_x, best_f = self._get_best_solution()
        return best_x, best_f

    def _get_best_solution(self):
        if self.population is None or self.objectives is None:
            return None, None
        if self.num_objectives == 1:
            idx = int(np.argmin(self.objectives[:, 0]))
            return self.population[idx], float(self.objectives[idx, 0])
        scores = np.sum(self.objectives, axis=1)
        idx = int(np.argmin(scores))
        return self.population[idx], self.objectives[idx]


