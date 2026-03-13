"""Core modules exposed by NSGABlack."""

from __future__ import annotations

from .base import BlackBoxProblem
from .blank_solver import SolverBase
from .composable_solver import ComposableSolver
from .config import StorageConfig, _apply_storage_config
from .evolution_solver import EvolutionSolver
from ..adapters import AlgorithmAdapter, CompositeAdapter, RoleAdapter, MultiRoleControllerAdapter
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
    "StorageConfig",
    "AlgorithmAdapter",
    "CompositeAdapter",
    "ComposableSolver",
    "RoleAdapter",
    "MultiRoleControllerAdapter",
    "BiasInterface",
    "RepresentationInterface",
    "VisualizationInterface",
    "PluginInterface",
    "OptimizationContext",
    "has_bias_module",
    "has_representation_module",
    "has_visualization_module",
    "has_numba",
    "load_bias_module",
    "load_representation_pipeline",
    "create_bias_context",
]
