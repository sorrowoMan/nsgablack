import time
import math
import random
import numpy as np
from scipy.spatial.distance import cdist
import json
import os
import logging
from typing import Optional, Any, List

# ============================================================================
# 核心导入（必需）
# ============================================================================
from .base import BlackBoxProblem
from ..utils.plugins import PluginManager

# ============================================================================
# 接口定义（用于类型提示和依赖注入）
# ============================================================================
from .interfaces import (
    BiasInterface,
    RepresentationInterface,
    VisualizationInterface,
    PluginInterface,
    # 工厂函数
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
# 可选模块导入（延迟加载）
# ============================================================================

# 可视化混入类
try:
    from ..utils.viz import SolverVisualizationMixin as _SolverVisualizationMixin
except ImportError:
    class _SolverVisualizationMixin:
        def _init_visualization(self):
            pass

# 偏置模块（延迟导入，通过属性访问）
_BiasModule = None

# Numba加速（延迟导入）
_fast_is_dominated = None
_NUMBA_AVAILABLE = False

# 实验结果（延迟导入）
_ExperimentResult = None

# 日志器
logger = logging.getLogger(__name__)

# 表示管道（延迟导入）
_RepresentationPipeline = None


# ============================================================================
# 辅助函数：安全加载可选模块
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
    """延迟加载 numba 辅助函数"""
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
    """延迟加载实验结果类"""
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
    """管线"""
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
    NSGA-II 黑箱求解器（支持依赖注入）

    参数:
        problem: 优化问题实例
        bias_module: 可选的偏置模块（支持依赖注入）
        representation_pipeline: 可选的表示管道（支持依赖注入）
        **kwargs: 其他配置参数

    示例:
        # 传统用法（向后兼容）
        solver = BlackBoxSolverNSGAII(problem)
        solver.bias_module = BiasModule()  # 之后设置

        # 新用法（依赖注入）
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
        # 基本配置
        self.enable_diversity_init = False
        self.use_history = False
        # Optional flag; prefer Suite + plugins for wiring.
        self.enable_elite_retention = False
        self.problem = problem
        self.variables = problem.variables
        self.num_objectives = problem.get_num_objectives()
        self.dimension = problem.dimension

        # 约束相关：通过 problem.evaluate_constraints 统一计算违背度
        self.constraints = []  # 保留占位，兼容旧用法

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

        # 依赖检查（可选）
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
        # 依赖注入：支持外部传入的模块
        # ====================================================================
        self._bias_module_internal: Optional[BiasInterface] = None
        self.bias_module = bias_module  # 使用属性setter处理
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

        # 标准NSGA-II参数
        self.pop_size = 80
        self.max_generations = 150
        self.crossover_rate = 0.85
        self.mutation_rate = 0.15
        self.initial_mutation_range = 0.8
        self.mutation_range = self.initial_mutation_range
        self.tol = 1e-5
        self.elite_retention_prob = 0.9
        self.random_seed = None

        # 多样性参数
        self.diversity_params = {
            'candidate_size': 500,
            'similarity_threshold': 0.05,
            'rejection_prob': 0.6,
            'sampling_method': 'lhs',
            'save_history': True
        }

        self._apply_solver_config(config_data, strict=config_strict)
        self._apply_solver_overrides(kwargs)
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

        # 插件系统（能力层）
        # - 不强制使用；默认不影响现有流程
        # - 提供评估短路插槽：允许插件接管评估（surrogate/缓存/远程评估等）
        self.plugin_manager = PluginManager(
            short_circuit=True,
            short_circuit_events=["evaluate_population", "evaluate_individual", "initialize_population"],
        )

        # 完成初始化（向后兼容）
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
        except Exception:
            pass
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

    def get_context(self) -> dict:
        """Return a snapshot context for visualization/monitoring."""
        ctx = {
            "generation": int(getattr(self, "generation", 0)),
            "population": self.population if self.population is not None else [],
            "objectives": self.objectives if self.objectives is not None else [],
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

    # ========================================================================
    # 属性访问器：支持延迟加载和依赖注入
    # ========================================================================

    @property
    def bias_module(self) -> Optional[BiasInterface]:
        """
        获取偏置模块

        支持：
        1. 依赖注入的外部模块
        2. 延迟加载的内部模块
        """
        if self._bias_module_internal is not None:
            return self._bias_module_internal

        # 延迟加载（向后兼容）
        BiasModuleClass = _get_bias_module()
        if BiasModuleClass is not None and self.enable_bias:
            # 创建默认实例
            if not hasattr(self, '_bias_module_cached'):
                self._bias_module_cached = BiasModuleClass()
            return self._bias_module_cached

        return None

    @bias_module.setter
    def bias_module(self, value: Optional[BiasInterface]):
        """
        设置偏置模块

        支持依赖注入和向后兼容。
        """
        self._bias_module_internal = value
        if value is not None:
            self.enable_bias = True
            # 清除缓存
            if hasattr(self, '_bias_module_cached'):
                delattr(self, '_bias_module_cached')

    @property
    def representation_pipeline(self) -> Optional[RepresentationInterface]:
        """
        获取表示管道

        支持：
        1. 依赖注入的外部管道
        2. 延迟加载的内部管道
        """
        if self._representation_internal is not None:
            return self._representation_internal

        # 延迟加载（向后兼容）
        RepresentationPipelineClass = _get_representation_pipeline()
        if RepresentationPipelineClass is not None:
            if not hasattr(self, '_representation_cached'):
                self._representation_cached = RepresentationPipelineClass()
            return self._representation_cached

        return None

    @representation_pipeline.setter
    def representation_pipeline(self, value: Optional[RepresentationInterface]):
        """
        设置表示管道

        支持依赖注入和向后兼容。
        """
        self._representation_internal = value
        if value is not None:
            # 清除缓存
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
            "initial_mutation_range",
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
    # 便捷方法：检查模块可用性
    # ========================================================================

    def has_bias_support(self) -> bool:
        """检查偏置系统是否可用"""
        return self.bias_module is not None

    def has_representation_support(self) -> bool:
        """检查表示管道是否可用"""
        return self.representation_pipeline is not None

    def has_numba_support(self) -> bool:
        """检查numba加速是否可用"""
        _, numba_available = _get_numba_helpers()
        return numba_available

    # ========================================================================
    # 兼容性方法：支持旧代码
    # ========================================================================

    def enable_bias_module(self, enable: bool = True):
        """
        启用或禁用偏置模块

        向后兼容方法。
        """
        self.enable_bias = enable
        if enable and self.bias_module is None:
            # 尝试自动创建
            BiasModuleClass = _get_bias_module()
            if BiasModuleClass is not None:
                self._bias_module_internal = BiasModuleClass()

    def get_bias_module_class(self):
        """
        获取BiasModule类（向后兼容）

        返回:
            BiasModule类或None
        """
        return _get_bias_module()

    # ========================================================================
    # 其余初始化（保持原有逻辑）
    # ========================================================================
    def _complete_initialization(self):
        """
        完成初始化（向后兼容）

        这个方法包含原 __init__ 的后续部分，
        保持与旧代码的兼容性。
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
        # core 不负责“能力装配”：多样性初始化/精英保留/收敛检测应通过 Plugin + Suite 接入。
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
        # 保存求解历史（包含每代的平均目标值）
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

    # ---- 约束与目标评估 ----
    def _evaluate_individual(self, x, individual_id=None):
        """评估单个个体的目标和约束违背度标量。

        目标来自 problem.evaluate(x)，约束来自 problem.evaluate_constraints(x)。
        约定 g(x) <= 0 为可行，g(x) > 0 为违反程度，这里将所有正违背度求和。
        """
        overridden = self.plugin_manager.trigger("evaluate_individual", self, x, individual_id)
        if overridden is not None:
            try:
                obj, violation = overridden
            except Exception as exc:
                raise ValueError("evaluate_individual 插件返回值必须是 (objectives, violation)") from exc
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

        # 应用 bias 模块
        if self.enable_bias and self.bias_module is not None:
            if self.num_objectives == 1:
                f_biased = self.bias_module.compute_bias(x, float(obj[0]), individual_id, context=context)
                obj = np.array([f_biased])
                if self.ignore_constraint_violation_when_bias:
                    violation = 0.0
            else:
                # 多目标：优先一次性批量应用 bias（减少重复开销）
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
            # 没有bias时，使用原始violation进行约束排序
            if cons_arr.size == 0 and "constraint_violation" in context:
                violation = float(context["constraint_violation"])

        return obj, violation

    def evaluate_population(self, population):
        """评估整个种群的目标和约束违背度。

        返回 (objectives, constraint_violations)。
        """
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
                raise ValueError("evaluate_population 插件返回值必须是 (objectives, violations)") from exc
            objectives = np.asarray(objectives, dtype=float)
            violations = np.asarray(violations, dtype=float).ravel()
            # 保持与原先一致：把“评估过的个体数”计入 evaluation_count（真实评估次数见 problem.evaluation_count）
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
                    # 保持与串行路径一致的统计与语义
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
        else:
            if self.representation_pipeline is not None and self.representation_pipeline.initializer is not None:
                # 先初始化一个样本，检查返回类型
                context = {
                    'generation': self.generation,
                    'bounds': self.var_bounds
                }
                sample = self.representation_pipeline.init(self.problem, context)

                # 根据Pipeline返回类型创建population
                if hasattr(sample, 'dtype'):
                    population_dtype = sample.dtype
                else:
                    population_dtype = type(sample[0]) if hasattr(sample, '__getitem__') else float

                # 创建指定类型的数组
                self.population = np.zeros((self.pop_size, self.dimension), dtype=population_dtype)
                self.population[0] = sample

                # 初始化剩余个体
                for i in range(1, self.pop_size):
                    context = {'generation': self.generation, 'bounds': self.var_bounds}
                    self.population[i] = self.representation_pipeline.init(self.problem, context)
            else:
                # 没有Pipeline时使用float
                self.population = np.zeros((self.pop_size, self.dimension))
                if isinstance(self.var_bounds, dict):
                    for i, var in enumerate(self.variables):
                        min_val, max_val = self.var_bounds[var]
                        self.population[:, i] = np.random.uniform(min_val, max_val, self.pop_size)
                else:
                    for i in range(self.dimension):
                        min_val, max_val = self.var_bounds[i]
                        self.population[:, i] = np.random.uniform(min_val, max_val, self.pop_size)
            self.objectives, self.constraint_violations = self.evaluate_population(self.population)

        try:
            self.plugin_manager.on_population_init(self.population, self.objectives, self.constraint_violations)
        except Exception:
            pass

    def is_dominated_vectorized(self, obj_matrix):
        """非支配判定：优先使用 numba 加速版本，失败时回退到 numpy 实现。"""
        if obj_matrix.ndim == 1:
            obj = obj_matrix.reshape(-1, 1)
        else:
            obj = obj_matrix

        # 优先尝试 numba 加速实现
        fast, numba = _get_numba_helpers()
        if numba and fast is not None:
            try:
                return fast(obj)
            except Exception:
                # 任意 numba 相关错误一律回退
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
        i = np.random.randint(0, self.pop_size, self.pop_size)
        j = np.random.randint(0, self.pop_size, self.pop_size)
        mask = i == j
        j[mask] = np.random.randint(0, self.pop_size, np.sum(mask))
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

        # 如果Pipeline有crossover，使用Pipeline的crossover
        if self.representation_pipeline is not None and self.representation_pipeline.crossover is not None:
            context = {
                'generation': self.generation,
                'bounds': self.var_bounds
            }
            for i in range(0, pop_size, 2):
                if i + 1 >= pop_size:
                    break
                if np.random.rand() < self.crossover_rate:
                    child1, child2 = self.representation_pipeline.crossover.crossover(
                        parents[i], parents[i+1]
                    )
                    offspring[i] = child1
                    offspring[i+1] = child2
        else:
            # 否则使用标准SBX crossover
            crossover_mask = np.random.rand(pop_size // 2) < self.crossover_rate
            alpha = np.random.rand(np.sum(crossover_mask), self.dimension)
            idx = 0
            for i in range(0, pop_size, 2):
                if i + 1 >= pop_size:
                    break
                if crossover_mask[i // 2]:
                    offspring[i] = alpha[idx] * parents[i] + (1 - alpha[idx]) * parents[i+1]
                    offspring[i+1] = (1 - alpha[idx]) * parents[i] + alpha[idx] * parents[i+1]
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
            mutation_mask = np.random.rand(pop_size) < self.mutation_rate
            mutation = np.random.uniform(-self.mutation_range, self.mutation_range, (pop_size, self.dimension))
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
        rank, _, _ = self.non_dominated_sorting()
        pareto_indices = np.where(rank == 0)[0]
        if len(pareto_indices) > 0:
            valid_indices = pareto_indices
            if len(valid_indices) > 50:
                valid_indices = valid_indices[:50]
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
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
        except Exception:
            # Don't raise for save failures; keep running
            pass

    # Legacy convergence helpers used to live in core, but are now expected to be
    # implemented via plugins (e.g. utils/plugins/convergence.py) + suites.

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
                    f"[进度] 第{self.generation}代 | 最优适应度: {best_f_display:.6f} | 最优解: {np.array2string(best_x, precision=6, separator=', ')}"
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
                        f"[进度] 第{self.generation}代 | Pareto解数: {len(pareto_idx)} | 代表目标: {np.array2string(rep_obj, precision=6, separator=', ')} | 解: {np.array2string(rep_x, precision=6, separator=', ')}"
                    )
                else:
                    print(f"[进度] 第{self.generation}代 | 暂无Pareto解")
        except Exception:
            pass

    def environmental_selection(self, combined_pop, combined_obj, combined_violations):
        combined_rank = np.zeros(len(combined_pop), dtype=int)
        feasible_mask = combined_violations <= 1e-10
        combined_rank[~feasible_mask] = 1
        if np.any(feasible_mask):
            feasible_objs = combined_obj[feasible_mask]
            dominated = self.is_dominated_vectorized(feasible_objs)
            combined_rank[feasible_mask] = np.where(dominated, 1, 0)
        combined_crowding = np.zeros(len(combined_pop))
        for r in [0, 1]:
            rank_mask = combined_rank == r
            if np.any(rank_mask):
                for obj_idx in range(self.num_objectives):
                    sorted_idx = np.argsort(combined_obj[rank_mask, obj_idx])
                    if len(sorted_idx) > 1:
                        obj_range = combined_obj[rank_mask, obj_idx][sorted_idx[-1]] - combined_obj[rank_mask, obj_idx][sorted_idx[0]]
                        if obj_range > 1e-10 and len(sorted_idx) > 2:
                            # Safe crowding distance calculation
                            rank_indices = np.where(rank_mask)[0]
                            for i in range(1, len(sorted_idx) - 1):
                                original_idx = rank_indices[sorted_idx[i]]
                                prev_obj = combined_obj[rank_mask, obj_idx][sorted_idx[i - 1]]
                                next_obj = combined_obj[rank_mask, obj_idx][sorted_idx[i + 1]]
                                combined_crowding[original_idx] += (next_obj - prev_obj) / obj_range
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
        self.mutation_range = self.initial_mutation_range * (1 - self.generation / self.max_generations)
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
        """生成随机个体"""
        new_individual = np.zeros(self.dimension)
        if isinstance(self.var_bounds, dict):
            var_keys = list(self.var_bounds.keys())
            for j, var in enumerate(var_keys):
                min_val, max_val = self.var_bounds[var]
                new_individual[j] = np.random.uniform(min_val, max_val)
        else:
            for j in range(self.dimension):
                min_val, max_val = self.var_bounds[j]
                new_individual[j] = np.random.uniform(min_val, max_val)
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
        """非 GUI 模式运行

        Args:
            return_experiment: 如果为 True，返回 ExperimentResult 对象；否则返回字典
            return_dict: 如果为 True，返回结果字典；否则返回 (best_x, best_f)
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
        self.evaluation_count = 0
        if self.random_seed is None:
            try:
                self.random_seed = int(np.random.randint(0, 2**32 - 1))
            except Exception:
                self.random_seed = 0
        try:
            np.random.seed(self.random_seed)
            random.seed(self.random_seed)
        except Exception:
            pass
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
