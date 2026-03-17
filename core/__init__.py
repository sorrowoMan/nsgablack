"""Core modules exposed by NSGABlack."""

from __future__ import annotations

from .acceleration import (
    AccelerationError,
    AccelerationFacade,
    AccelerationRegistry,
    AsyncHandle,
    ExecutionResult,
    GpuBackend,
    ProcessPoolBackend,
    ThreadPoolBackend,
)
from .acceleration_helpers import maybe_accel_map, maybe_accel_run
from .base import BlackBoxProblem
from .blank_solver import SolverBase
from .composable_solver import ComposableSolver
from .config import StorageConfig, _apply_storage_config
from .control_plane import BaseController, ControlArbiter, ControlDecision, RuntimeController
from .evolution_solver import EvolutionSolver
from .evaluation_runtime import EvaluationMediator, EvaluationMediatorConfig, EvaluationProvider
from .nested_solver import (
    InnerRuntimeConfig,
    InnerRuntimeEvaluator,
    InnerSolveRequest,
    InnerSolveResult,
    TaskInnerRuntimeEvaluator,
)
from ..adapters import AlgorithmAdapter, CompositeAdapter, RoleAdapter, RoleRouterAdapter
from .interfaces import (
    BiasInterface,
    PluginInterface,
    OptimizationContext,
    RepresentationInterface,
    VisualizationInterface,
    create_bias_context,
    has_bias_module,
    has_numba,
    has_representation_module,
    has_visualization_module,
    load_bias_module,
    load_representation_pipeline,
)

__all__ = [
    "BlackBoxProblem",
    "EvolutionSolver",
    "SolverBase",
    "AccelerationRegistry",
    "AccelerationFacade",
    "ExecutionResult",
    "AccelerationError",
    "AsyncHandle",
    "ThreadPoolBackend",
    "ProcessPoolBackend",
    "GpuBackend",
    "maybe_accel_run",
    "maybe_accel_map",
    "StorageConfig",
    "AlgorithmAdapter",
    "CompositeAdapter",
    "ComposableSolver",
    "RoleAdapter",
    "RoleRouterAdapter",
    "BiasInterface",
    "RepresentationInterface",
    "VisualizationInterface",
    "PluginInterface",
    "BaseController",
    "ControlDecision",
    "ControlArbiter",
    "RuntimeController",
    "EvaluationMediator",
    "EvaluationMediatorConfig",
    "EvaluationProvider",
    "InnerSolveRequest",
    "InnerSolveResult",
    "InnerRuntimeEvaluator",
    "TaskInnerRuntimeEvaluator",
    "InnerRuntimeConfig",
    "OptimizationContext",
    "has_bias_module",
    "has_representation_module",
    "has_visualization_module",
    "has_numba",
    "load_bias_module",
    "load_representation_pipeline",
    "create_bias_context",
]
