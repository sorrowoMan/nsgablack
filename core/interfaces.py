"""
Core interfaces for NSGABlack components.

This module defines the core interfaces and re-exports from blackbase.
"""

from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional, Sequence

from blackbase.context import (
    ContextContract,
    ContextStore,
    SnapshotStore,
)
from blackbase.resources import (
    ResourceRequirement,
    WorkerDescriptor,
    TaskEnvelope,
    TaskResult,
)
from blackbase.plugin import PluginBase as PluginInterface
from blackbase.kernel import PipelineKernelBuild as OrchestrationInterface


class OptimizationContext(ABC):
    """Abstract optimization context."""
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        pass
    
    @abstractmethod
    def snapshot(self) -> Mapping[str, Any]:
        pass


class BiasInterface(ABC):
    """Abstract bias module interface."""
    
    @abstractmethod
    def apply(self, objectives: Any, context: Mapping[str, Any] | None = None) -> Any:
        pass


class RepresentationInterface(ABC):
    """Abstract representation interface."""
    
    @abstractmethod
    def initialize(self, problem: Any, context: Mapping[str, Any] | None = None) -> Any:
        pass
    
    @abstractmethod
    def mutate(self, value: Any, context: Mapping[str, Any] | None = None) -> Any:
        pass
    
    @abstractmethod
    def repair(self, value: Any, context: Mapping[str, Any] | None = None) -> Any:
        pass
    
    @abstractmethod
    def encode(self, value: Any, context: Mapping[str, Any] | None = None) -> Any:
        pass
    
    @abstractmethod
    def decode(self, value: Any, context: Mapping[str, Any] | None = None) -> Any:
        pass


def has_bias_module() -> bool:
    """Check if bias module is available."""
    try:
        import importlib
        importlib.import_module("nsgablack.bias")
        return True
    except ImportError:
        return False


def has_representation_module() -> bool:
    """Check if representation module is available."""
    try:
        import importlib
        importlib.import_module("nsgablack.representation")
        return True
    except ImportError:
        return False


def has_visualization_module() -> bool:
    """Check if visualization module is available."""
    try:
        import importlib
        importlib.import_module("nsgablack.visualization")
        return True
    except ImportError:
        return False


def has_numba() -> bool:
    """Check if numba is available."""
    try:
        import numba
        return True
    except Exception:
        return False


def create_bias_context() -> Mapping[str, Any]:
    """Create a default bias context."""
    return {}


def load_bias_module():
    """Load and return the bias module."""
    try:
        import importlib
        return importlib.import_module("nsgablack.bias")
    except ImportError:
        return None


def load_representation_module():
    """Load and return the representation module."""
    try:
        import importlib
        return importlib.import_module("nsgablack.representation")
    except ImportError:
        return None


def load_representation_pipeline():
    """Load and return the representation pipeline."""
    try:
        from nsgablack.representation import RepresentationPipeline
        return RepresentationPipeline
    except ImportError:
        return None


class VisualizationInterface(ABC):
    """Abstract visualization interface."""
    
    @abstractmethod
    def visualize(self, data: Any, context: Mapping[str, Any] | None = None) -> Any:
        pass


class BaseController(ABC):
    """Abstract base controller."""
    
    @abstractmethod
    def run(self) -> Any:
        pass


def decode_resource(ref: Any, context: Mapping[str, Any] | None = None) -> Any:
    """Decode a resource reference."""
    return ref


def encode_resource(obj: Any, context: Mapping[str, Any] | None = None) -> Any:
    """Encode an object as a resource reference."""
    return obj


def create_resource_context(**kwargs) -> Mapping[str, Any]:
    """Create a resource context."""
    return dict(kwargs)


__all__ = [
    "ContextContract",
    "ContextStore",
    "SnapshotStore",
    "ResourceRequirement",
    "WorkerDescriptor",
    "TaskEnvelope",
    "TaskResult",
    "OptimizationContext",
    "BiasInterface",
    "RepresentationInterface",
    "OrchestrationInterface",
    "VisualizationInterface",
    "PluginInterface",
    "BaseController",
    "has_bias_module",
    "has_representation_module",
    "has_visualization_module",
    "has_numba",
    "create_bias_context",
    "load_bias_module",
    "load_representation_module",
    "load_representation_pipeline",
    "decode_resource",
    "encode_resource",
    "create_resource_context",
]
